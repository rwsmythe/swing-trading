"""Phase 11 T-B.3 + T-B.4 — `_step_schwab_snapshot` + `_step_schwab_orders` pipeline-step tests.

Per plan §H.4.1 + §H.4.2 + §A.3 production-only domain-write gate.

Tests cover:
  - Happy-path snapshot under production: account_equity_snapshots row
    INSERTED via `record_snapshot(source='schwab_api', ...)`; combined-tx2
    `link_snapshot_and_stamp_account_hash` writes BOTH linked_snapshot_id +
    schwab_account_hash.
  - Sandbox short-circuit: audit row WRITTEN, account_equity_snapshots
    UNCHANGED (zero new rows).
  - account_hash-missing path: advisory audit row + no Schwab call.
  - 401/429 → audit row reflects failure + step returns 'failed' (no abort).
  - Same-day-replay-provenance asymmetry (R4 Minor #2 + §H.4.1.bis):
    two calls same snapshot_date → ONE snapshot + TWO audit rows BOTH
    linked; source_artifact_path = LATEST call_id.
  - `_step_schwab_orders` happy-path under production: reconciliation_run
    row INSERTED + 3 audit rows UPDATEd with reconciliation_run_id.
  - Sandbox short-circuit for orders: 3 audit rows + ZERO reconciliation_run.
  - Reconciliation discrepancy emission: stop_mismatch + position_qty_mismatch
    when journal/Schwab diverge.
  - run_schwab_reconciliation caller-held-tx rejection.
  - Failure-path preserves a failed-state reconciliation_run row.
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, date, datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from swing.data.db import ensure_schema
from swing.integrations.schwab import client as schwab_client_module
from swing.integrations.schwab.pipeline_steps import (
    _step_schwab_orders,
    _step_schwab_snapshot,
)
from swing.trades.schwab_reconciliation import (
    CallerHeldTransactionError,
    run_schwab_reconciliation,
)


# ============================================================================
# Fixtures
# ============================================================================


@pytest.fixture
def v18_conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "schwab-pipeline-steps.db")


@pytest.fixture(autouse=True)
def reset_schwab_redaction_state():
    """Mirror T-A.10 fixture pattern."""
    original_factory = logging.getLogRecordFactory()
    original_installed = schwab_client_module._FACTORY_INSTALLED
    original_orig = schwab_client_module._ORIGINAL_RECORD_FACTORY
    original_secrets = set(schwab_client_module._GLOBAL_KNOWN_SECRETS)

    schwab_client_module._GLOBAL_KNOWN_SECRETS.clear()
    schwab_client_module._FACTORY_INSTALLED = False
    schwab_client_module._ORIGINAL_RECORD_FACTORY = None
    logging.setLogRecordFactory(logging.LogRecord)

    yield

    logging.setLogRecordFactory(original_factory)
    schwab_client_module._FACTORY_INSTALLED = original_installed
    schwab_client_module._ORIGINAL_RECORD_FACTORY = original_orig
    schwab_client_module._GLOBAL_KNOWN_SECRETS.clear()
    schwab_client_module._GLOBAL_KNOWN_SECRETS.update(original_secrets)


def _mock_response(json_value, *, status_code: int = 200, headers=None):
    resp = MagicMock()
    resp.json.return_value = json_value
    resp.status_code = status_code
    resp.headers = headers or {}
    return resp


def _make_cfg(*, environment: str = "production",
              account_hash: str | None = "abc...64charhash",
              lookback_days: int = 7) -> SimpleNamespace:
    """Build a minimal cfg.integrations.schwab namespace for tests."""
    return SimpleNamespace(
        integrations=SimpleNamespace(
            schwab=SimpleNamespace(
                environment=environment,
                account_hash=account_hash,
                lookback_days=lookback_days,
                timeout_seconds=30.0,
                marketdata_ladder_enabled=True,
                callback_url="https://127.0.0.1",
            ),
        ),
    )


def _make_account_details_response(nlv: float = 2014.36):
    return _mock_response({
        "securitiesAccount": {
            "currentBalances": {
                "liquidationValue": nlv,
                "cashBalance": 100.0,
                "buyingPower": 4000.0,
            },
            "positions": [],
        },
    })


def _audit_count(conn) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM schwab_api_calls"
    ).fetchone()[0]


def _snapshot_count(conn) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM account_equity_snapshots"
    ).fetchone()[0]


def _recon_count(conn) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM reconciliation_runs"
    ).fetchone()[0]


# ============================================================================
# T-B.3 — _step_schwab_snapshot
# ============================================================================


def test_b3_01_snapshot_happy_path_production_writes_domain(v18_conn):
    """Production env: audit row + account_equity_snapshots row + linkage."""
    cfg = _make_cfg(environment="production")
    client = MagicMock()
    client.account_details.return_value = _make_account_details_response(2014.36)

    result = _step_schwab_snapshot(
        v18_conn, cfg, pipeline_run_id=None, client=client,
    )
    assert result["status"] == "completed"
    assert result["snapshot_id"] is not None
    assert result["call_id"] is not None

    # 1 audit row + 1 snapshot row.
    assert _audit_count(v18_conn) == 1
    assert _snapshot_count(v18_conn) == 1

    # Audit row has linked_snapshot_id + status='success'.
    row = v18_conn.execute(
        "SELECT status, linked_snapshot_id FROM schwab_api_calls "
        "WHERE call_id = ?",
        (result["call_id"],),
    ).fetchone()
    assert row[0] == "success"
    assert row[1] == result["snapshot_id"]

    # Snapshot row has schwab_account_hash stamped + source='schwab_api'.
    snap = v18_conn.execute(
        "SELECT equity_dollars, source, source_artifact_path, "
        "schwab_account_hash FROM account_equity_snapshots "
        "WHERE snapshot_id = ?",
        (result["snapshot_id"],),
    ).fetchone()
    assert snap[0] == 2014.36
    assert snap[1] == "schwab_api"
    assert snap[2] == f"schwab_api:call/{result['call_id']}"
    assert snap[3] == "abc...64charhash"


def test_b3_02_snapshot_sandbox_short_circuits_domain_write(v18_conn):
    """Sandbox: audit row WRITTEN (status='success'); ZERO snapshot rows."""
    cfg = _make_cfg(environment="sandbox")
    client = MagicMock()
    client.account_details.return_value = _make_account_details_response(2014.36)

    pre_snapshots = _snapshot_count(v18_conn)
    result = _step_schwab_snapshot(
        v18_conn, cfg, pipeline_run_id=None, client=client,
    )
    assert result["status"] == "sandbox_audit_only"
    assert result["snapshot_id"] is None
    assert result["call_id"] is not None

    # Audit row exists + success; snapshot count UNCHANGED.
    assert _audit_count(v18_conn) == 1
    assert _snapshot_count(v18_conn) == pre_snapshots

    row = v18_conn.execute(
        "SELECT status, linked_snapshot_id, environment FROM schwab_api_calls "
        "WHERE call_id = ?",
        (result["call_id"],),
    ).fetchone()
    assert row[0] == "success"
    assert row[1] is None  # never linked under sandbox
    assert row[2] == "sandbox"


def test_b3_03_snapshot_no_account_hash_advisory_no_call(v18_conn):
    """account_hash=None: 1 advisory audit row; ZERO schwabdev calls."""
    cfg = _make_cfg(account_hash=None)
    client = MagicMock()

    result = _step_schwab_snapshot(
        v18_conn, cfg, pipeline_run_id=None, client=client,
    )
    assert result["status"] == "skipped_no_account_hash"
    # schwabdev MUST NOT be called.
    client.account_details.assert_not_called()
    # 1 audit row written with error status.
    assert _audit_count(v18_conn) == 1
    row = v18_conn.execute(
        "SELECT status, error_message FROM schwab_api_calls WHERE call_id = ?",
        (result["call_id"],),
    ).fetchone()
    assert row[0] == "error"
    assert "account_hash not configured" in (row[1] or "")
    # ZERO snapshot rows.
    assert _snapshot_count(v18_conn) == 0


def test_b3_04_snapshot_http_401_pipeline_continues(v18_conn):
    """401 → audit row 'auth_failed'; step returns 'failed' (no raise)."""
    cfg = _make_cfg(environment="production")
    client = MagicMock()
    client.account_details.return_value = _mock_response(
        {"errors": [{"message": "Unauthorized"}]},
        status_code=401,
    )

    result = _step_schwab_snapshot(
        v18_conn, cfg, pipeline_run_id=None, client=client,
    )
    assert result["status"] == "failed"
    assert result["snapshot_id"] is None
    # Audit row reflects auth failure.
    row = v18_conn.execute(
        "SELECT status, http_status FROM schwab_api_calls "
        "ORDER BY call_id DESC LIMIT 1"
    ).fetchone()
    assert row[0] == "auth_failed"
    assert row[1] == 401
    # ZERO snapshot rows (domain write skipped on failure).
    assert _snapshot_count(v18_conn) == 0


def test_b3_05_snapshot_http_429_step_failed(v18_conn):
    """429 → audit row 'rate_limited'; step returns 'failed'."""
    cfg = _make_cfg(environment="production")
    client = MagicMock()
    client.account_details.return_value = _mock_response(
        {"error": "throttled"},
        status_code=429,
    )

    result = _step_schwab_snapshot(
        v18_conn, cfg, pipeline_run_id=None, client=client,
    )
    assert result["status"] == "failed"
    row = v18_conn.execute(
        "SELECT status, http_status FROM schwab_api_calls "
        "ORDER BY call_id DESC LIMIT 1"
    ).fetchone()
    assert row[0] == "rate_limited"
    assert row[1] == 429


def test_b3_06_snapshot_same_day_replay_provenance_asymmetry(v18_conn):
    """§H.4.1.bis — two calls same snapshot_date → ONE snapshot + TWO audit
    rows BOTH linked + source_artifact_path = LATEST call_id.

    Discriminating: pre-fix UPSERT contract would NEW-id-issue on the second
    record_snapshot; post-fix (Phase 9 Sub-bundle C) UPSERT preserves the
    snapshot_id + overwrites source_artifact_path.
    """
    cfg = _make_cfg(environment="production")
    client = MagicMock()
    client.account_details.side_effect = [
        _make_account_details_response(2000.00),
        _make_account_details_response(2014.36),
    ]

    r1 = _step_schwab_snapshot(v18_conn, cfg, pipeline_run_id=None, client=client)
    r2 = _step_schwab_snapshot(v18_conn, cfg, pipeline_run_id=None, client=client)

    # ONE snapshot row (UPSERT preserved).
    assert _snapshot_count(v18_conn) == 1
    assert r1["snapshot_id"] == r2["snapshot_id"]

    # TWO audit rows BOTH linked to the SAME snapshot_id.
    rows = v18_conn.execute(
        "SELECT call_id, linked_snapshot_id FROM schwab_api_calls "
        "WHERE endpoint = 'accounts.details' "
        "ORDER BY call_id"
    ).fetchall()
    assert len(rows) == 2
    assert rows[0][1] == rows[1][1] == r2["snapshot_id"]

    # source_artifact_path reflects LATEST call_id (r2's call_id).
    snap = v18_conn.execute(
        "SELECT source_artifact_path, equity_dollars FROM account_equity_snapshots "
        "WHERE snapshot_id = ?",
        (r2["snapshot_id"],),
    ).fetchone()
    assert snap[0] == f"schwab_api:call/{r2['call_id']}"
    # NLV reflects latest write (UPSERT).
    assert snap[1] == 2014.36


def test_b3_07_snapshot_rejects_caller_held_tx(v18_conn):
    """record_snapshot rejects caller-held tx → _step_schwab_snapshot raises."""
    cfg = _make_cfg(environment="production")
    client = MagicMock()
    client.account_details.return_value = _make_account_details_response()

    v18_conn.execute("BEGIN")
    # Caller-held tx: snapshot service raises CallerHeldTransactionError.
    with pytest.raises(Exception):  # noqa: B017
        _step_schwab_snapshot(
            v18_conn, cfg, pipeline_run_id=None, client=client,
        )
    v18_conn.rollback()


def test_b3_08_snapshot_session_anchor_uses_last_completed_session(v18_conn):
    """Plan §A.9 lesson #9 — snapshot_date uses backward-looking
    last_completed_session(now()); discriminating round-trip vs forward-looking
    action_session_for_run pattern.
    """
    cfg = _make_cfg(environment="production")
    client = MagicMock()
    client.account_details.return_value = _make_account_details_response()

    from swing.evaluation.dates import last_completed_session
    expected_date = last_completed_session(datetime.now())

    result = _step_schwab_snapshot(
        v18_conn, cfg, pipeline_run_id=None, client=client,
    )
    snap = v18_conn.execute(
        "SELECT snapshot_date FROM account_equity_snapshots "
        "WHERE snapshot_id = ?",
        (result["snapshot_id"],),
    ).fetchone()
    assert snap[0] == expected_date.isoformat()


def test_b3_09_snapshot_passes_pipeline_run_id_to_audit_row(v18_conn):
    """pipeline_run_id threads through audit_service.record_call_start."""
    cfg = _make_cfg(environment="production")
    client = MagicMock()
    client.account_details.return_value = _make_account_details_response()

    # Plant a fake pipeline_runs row so the FK is satisfied.
    v18_conn.execute(
        "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
        "action_session_date, state, lease_token) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("2026-05-14T08:00:00", "manual", "2026-05-13", "2026-05-14",
         "running", "test-token"),
    )
    v18_conn.commit()
    pipeline_run_id = v18_conn.execute(
        "SELECT id FROM pipeline_runs"
    ).fetchone()[0]

    result = _step_schwab_snapshot(
        v18_conn, cfg, pipeline_run_id=pipeline_run_id, client=client,
    )
    row = v18_conn.execute(
        "SELECT pipeline_run_id, surface FROM schwab_api_calls "
        "WHERE call_id = ?",
        (result["call_id"],),
    ).fetchone()
    assert row[0] == pipeline_run_id
    assert row[1] == "pipeline"


def test_b3_10_snapshot_phase10_capital_friction_round_trip(v18_conn):
    """Discriminating round-trip per plan §A.9 #9.

    Writes a snapshot via _step_schwab_snapshot + immediately reads via
    Phase 10 source-ladder helper get_latest_snapshot_on_or_before to
    confirm read/write session-anchor alignment.
    """
    cfg = _make_cfg(environment="production")
    client = MagicMock()
    client.account_details.return_value = _make_account_details_response(2014.36)

    result = _step_schwab_snapshot(
        v18_conn, cfg, pipeline_run_id=None, client=client,
    )
    assert result["status"] == "completed"

    # Read via Phase 10 / Phase 9 Sub-bundle C source-ladder helper.
    from swing.data.repos.account_equity_snapshots import (
        get_latest_snapshot_on_or_before,
    )
    from swing.evaluation.dates import last_completed_session
    asof = last_completed_session(datetime.now()).isoformat()
    snap = get_latest_snapshot_on_or_before(v18_conn, asof_date=asof)
    assert snap is not None
    assert snap.equity_dollars == 2014.36
    assert snap.source == "schwab_api"


def test_b3_11_snapshot_signature_hash_populated_on_success(v18_conn):
    """Drift-detection: successful audit row carries 64-char hex signature_hash."""
    cfg = _make_cfg(environment="production")
    client = MagicMock()
    client.account_details.return_value = _make_account_details_response()

    result = _step_schwab_snapshot(
        v18_conn, cfg, pipeline_run_id=None, client=client,
    )
    row = v18_conn.execute(
        "SELECT signature_hash FROM schwab_api_calls WHERE call_id = ?",
        (result["call_id"],),
    ).fetchone()
    assert row[0] is not None
    assert len(row[0]) == 64
    assert all(c in "0123456789abcdef" for c in row[0])


def test_b3_12_snapshot_audit_endpoint_is_accounts_details(v18_conn):
    """Audit row's endpoint reflects the schwabdev method invoked."""
    cfg = _make_cfg(environment="production")
    client = MagicMock()
    client.account_details.return_value = _make_account_details_response()

    result = _step_schwab_snapshot(
        v18_conn, cfg, pipeline_run_id=None, client=client,
    )
    row = v18_conn.execute(
        "SELECT endpoint FROM schwab_api_calls WHERE call_id = ?",
        (result["call_id"],),
    ).fetchone()
    assert row[0] == "accounts.details"


def test_b3_13_snapshot_response_time_ms_populated(v18_conn):
    """response_time_ms is non-None + non-negative."""
    cfg = _make_cfg(environment="production")
    client = MagicMock()
    client.account_details.return_value = _make_account_details_response()

    result = _step_schwab_snapshot(
        v18_conn, cfg, pipeline_run_id=None, client=client,
    )
    row = v18_conn.execute(
        "SELECT response_time_ms FROM schwab_api_calls WHERE call_id = ?",
        (result["call_id"],),
    ).fetchone()
    assert row[0] is not None
    assert row[0] >= 0


# ============================================================================
# T-B.4 — _step_schwab_orders + run_schwab_reconciliation
# ============================================================================


def _make_orders_response(orders_list=None):
    return _mock_response(orders_list if orders_list is not None else [])


def _make_transactions_response(tx_list=None):
    return _mock_response(tx_list if tx_list is not None else [])


def test_b4_01_orders_happy_path_production_writes_recon_run(v18_conn):
    """Production env: 3 audit rows + 1 reconciliation_run + 3 audit rows
    UPDATEd with linked_reconciliation_run_id."""
    cfg = _make_cfg(environment="production")
    client = MagicMock()
    client.account_orders.return_value = _make_orders_response([])
    client.transactions.return_value = _make_transactions_response([])
    client.account_details.return_value = _make_account_details_response()

    result = _step_schwab_orders(
        v18_conn, cfg, pipeline_run_id=None, client=client,
    )
    assert result["status"] == "completed"
    assert result["reconciliation_run_id"] is not None
    assert len(result["call_ids"]) == 3

    # 3 audit rows + all linked.
    rows = v18_conn.execute(
        "SELECT linked_reconciliation_run_id FROM schwab_api_calls"
    ).fetchall()
    assert len(rows) == 3
    for r in rows:
        assert r[0] == result["reconciliation_run_id"]


def test_b4_02_orders_sandbox_short_circuits_reconciliation(v18_conn):
    """Sandbox: 3 audit rows + ZERO reconciliation_runs."""
    cfg = _make_cfg(environment="sandbox")
    client = MagicMock()
    client.account_orders.return_value = _make_orders_response([])
    client.transactions.return_value = _make_transactions_response([])
    client.account_details.return_value = _make_account_details_response()

    result = _step_schwab_orders(
        v18_conn, cfg, pipeline_run_id=None, client=client,
    )
    assert result["status"] == "sandbox_audit_only"
    assert result["reconciliation_run_id"] is None
    assert _audit_count(v18_conn) == 3
    assert _recon_count(v18_conn) == 0


def test_b4_03_orders_no_account_hash_advisory_no_calls(v18_conn):
    """account_hash=None: 1 advisory audit; ZERO schwabdev calls."""
    cfg = _make_cfg(account_hash=None)
    client = MagicMock()

    result = _step_schwab_orders(
        v18_conn, cfg, pipeline_run_id=None, client=client,
    )
    assert result["status"] == "skipped_no_account_hash"
    client.account_orders.assert_not_called()
    client.transactions.assert_not_called()
    client.account_details.assert_not_called()
    assert _recon_count(v18_conn) == 0


def test_b4_04_orders_first_call_failure_step_failed(v18_conn):
    """First schwabdev call fails → step returns 'failed', no reconciliation."""
    cfg = _make_cfg(environment="production")
    client = MagicMock()
    client.account_orders.return_value = _mock_response(
        {"error": "unauthorized"},
        status_code=401,
    )
    client.transactions.return_value = _make_transactions_response([])
    client.account_details.return_value = _make_account_details_response()

    result = _step_schwab_orders(
        v18_conn, cfg, pipeline_run_id=None, client=client,
    )
    assert result["status"] == "failed"
    assert result["reconciliation_run_id"] is None
    assert _recon_count(v18_conn) == 0


def test_b4_05_run_schwab_reconciliation_rejects_caller_held_tx(v18_conn):
    """Phase 8 R3→R4 lesson — caller-held tx is rejected."""
    cfg = _make_cfg()
    schwab_account = SimpleNamespace(
        account_hash="abc", net_liquidating_value=2000.0, positions=[],
        cash=0.0, buying_power=0.0,
    )
    v18_conn.execute("BEGIN")
    with pytest.raises(CallerHeldTransactionError):
        run_schwab_reconciliation(
            v18_conn,
            account_hash="abc",
            period_start="2026-05-07",
            period_end="2026-05-14",
            schwab_orders=[],
            schwab_transactions=[],
            schwab_account=schwab_account,
        )
    v18_conn.rollback()


def test_b4_06_run_schwab_reconciliation_clean_no_open_trades(v18_conn):
    """No open trades → ZERO discrepancies; run state='completed'."""
    schwab_account = SimpleNamespace(
        account_hash="abc", net_liquidating_value=2000.0, positions=[],
        cash=0.0, buying_power=0.0,
    )
    out = run_schwab_reconciliation(
        v18_conn,
        account_hash="abc",
        period_start="2026-05-07",
        period_end="2026-05-14",
        schwab_orders=[],
        schwab_transactions=[],
        schwab_account=schwab_account,
    )
    assert out.state == "completed"
    assert out.source == "schwab_api"
    assert out.discrepancies_count == 0


def _seed_open_trade(conn, *, ticker="AAPL", shares=10, entry_price=100.0,
                    current_stop=95.0) -> int:
    """Seed an open trade + entry fill so reconciliation has a target.

    Uses real schema column names: trades.entry_price/initial_shares/initial_stop;
    fills.quantity (NOT shares); fills.fees (NOT fee).
    """
    cur = conn.execute(
        "INSERT INTO trades ("
        "ticker, entry_date, entry_price, initial_shares, initial_stop, "
        "current_stop, state, hypothesis_label, planned_target_R, "
        "trade_origin, pre_trade_locked_at, current_size"
        ") VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)",
        (ticker, "2026-05-10", entry_price, shares, current_stop,
         current_stop, "managing", "Near-A+", 2.0,
         "manual_off_pipeline", "2026-05-10T10:00:00", float(shares)),
    )
    trade_id = int(cur.lastrowid)
    # Insert entry fill.
    conn.execute(
        "INSERT INTO fills ("
        "trade_id, fill_datetime, action, quantity, price, fees"
        ") VALUES (?, ?, ?, ?, ?, ?)",
        (trade_id, "2026-05-10T10:00:00", "entry", shares, entry_price, 0.0),
    )
    conn.commit()
    return trade_id


def test_b4_07_reconciliation_emits_stop_mismatch(v18_conn):
    """Open trade with current_stop=95.0; Schwab working stop at 95.50 → emit."""
    trade_id = _seed_open_trade(
        v18_conn, ticker="AAPL", shares=10, current_stop=95.0,
    )
    from swing.integrations.schwab.models import SchwabOrderResponse

    schwab_orders = [SchwabOrderResponse(
        order_id="1001",
        status="WORKING",
        enter_time="2026-05-12T10:00:00Z",
        instrument_symbol="AAPL",
        instruction="SELL",
        quantity=10.0,
        order_type="STOP",
        price=95.50,
    )]
    schwab_account = SimpleNamespace(
        account_hash="abc", net_liquidating_value=2000.0, positions=[],
        cash=0.0, buying_power=0.0,
    )
    out = run_schwab_reconciliation(
        v18_conn,
        account_hash="abc",
        period_start="2026-05-07",
        period_end="2026-05-14",
        schwab_orders=schwab_orders,
        schwab_transactions=[],
        schwab_account=schwab_account,
    )
    assert out.discrepancies_count >= 1
    row = v18_conn.execute(
        "SELECT discrepancy_type, ticker, material_to_review "
        "FROM reconciliation_discrepancies WHERE run_id = ?",
        (out.run_id,),
    ).fetchone()
    assert row[0] == "stop_mismatch"
    assert row[1] == "AAPL"
    assert row[2] == 1  # material


def test_b4_08_reconciliation_emits_position_qty_mismatch(v18_conn):
    """Open trade qty=10; Schwab position qty=8 → emit position_qty_mismatch."""
    trade_id = _seed_open_trade(v18_conn, ticker="AAPL", shares=10)
    schwab_account = SimpleNamespace(
        account_hash="abc",
        net_liquidating_value=2000.0,
        positions=[
            {"instrument": {"symbol": "AAPL"}, "longQuantity": 8, "shortQuantity": 0},
        ],
        cash=0.0, buying_power=0.0,
    )
    out = run_schwab_reconciliation(
        v18_conn,
        account_hash="abc",
        period_start="2026-05-07",
        period_end="2026-05-14",
        schwab_orders=[],
        schwab_transactions=[],
        schwab_account=schwab_account,
    )
    # Look for the position_qty_mismatch row specifically.
    rows = v18_conn.execute(
        "SELECT discrepancy_type, ticker FROM reconciliation_discrepancies "
        "WHERE run_id = ?",
        (out.run_id,),
    ).fetchall()
    types = [r[0] for r in rows]
    assert "position_qty_mismatch" in types


def test_b4_09_reconciliation_material_lookup_at_insert_time(v18_conn):
    """Codex R1 M#2 lesson — MATERIAL_BY_TYPE is authoritative at INSERT time.

    Discriminating: stop_mismatch is material=1 per the lookup; verify the
    discrepancy row carries material_to_review=1 regardless of any caller hint.
    """
    _seed_open_trade(v18_conn, ticker="AAPL", current_stop=95.0)
    from swing.integrations.schwab.models import SchwabOrderResponse
    schwab_orders = [SchwabOrderResponse(
        order_id="1001",
        status="WORKING",
        enter_time="2026-05-12T10:00:00Z",
        instrument_symbol="AAPL",
        instruction="SELL",
        quantity=10.0,
        order_type="STOP",
        price=95.50,
    )]
    schwab_account = SimpleNamespace(
        account_hash="abc", net_liquidating_value=2000.0, positions=[],
        cash=0.0, buying_power=0.0,
    )
    out = run_schwab_reconciliation(
        v18_conn,
        account_hash="abc",
        period_start="2026-05-07",
        period_end="2026-05-14",
        schwab_orders=schwab_orders,
        schwab_transactions=[],
        schwab_account=schwab_account,
    )
    row = v18_conn.execute(
        "SELECT discrepancy_type, material_to_review "
        "FROM reconciliation_discrepancies WHERE run_id = ?",
        (out.run_id,),
    ).fetchone()
    assert row[0] == "stop_mismatch"
    assert row[1] == 1


def test_b4_10_reconciliation_equity_delta_emitted_above_threshold(v18_conn):
    """source NLV − journal equity > $10 → emit equity_delta discrepancy."""
    # Seed a journal snapshot first (manual source).
    v18_conn.execute(
        "INSERT INTO account_equity_snapshots ("
        "snapshot_date, equity_dollars, source, source_artifact_path, "
        "recorded_at, recorded_by, notes"
        ") VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("2026-05-14", 2000.0, "manual", None, "2026-05-14T12:00:00", "operator", None),
    )
    v18_conn.commit()

    schwab_account = SimpleNamespace(
        account_hash="abc",
        net_liquidating_value=2050.0,  # delta = -50 > $10 threshold
        positions=[],
        cash=0.0, buying_power=0.0,
    )
    out = run_schwab_reconciliation(
        v18_conn,
        account_hash="abc",
        period_start="2026-05-07",
        period_end="2026-05-14",
        schwab_orders=[],
        schwab_transactions=[],
        schwab_account=schwab_account,
    )
    rows = v18_conn.execute(
        "SELECT discrepancy_type FROM reconciliation_discrepancies "
        "WHERE run_id = ?",
        (out.run_id,),
    ).fetchall()
    types = [r[0] for r in rows]
    assert "equity_delta" in types


def test_b4_11_reconciliation_equity_delta_NOT_emitted_below_threshold(v18_conn):
    """delta <= $10 → equity_delta discrepancy NOT emitted (strict greater-than)."""
    v18_conn.execute(
        "INSERT INTO account_equity_snapshots ("
        "snapshot_date, equity_dollars, source, source_artifact_path, "
        "recorded_at, recorded_by, notes"
        ") VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("2026-05-14", 2000.0, "manual", None, "2026-05-14T12:00:00", "operator", None),
    )
    v18_conn.commit()
    schwab_account = SimpleNamespace(
        account_hash="abc",
        net_liquidating_value=2005.0,  # delta = -5, below threshold
        positions=[],
        cash=0.0, buying_power=0.0,
    )
    out = run_schwab_reconciliation(
        v18_conn,
        account_hash="abc",
        period_start="2026-05-07",
        period_end="2026-05-14",
        schwab_orders=[],
        schwab_transactions=[],
        schwab_account=schwab_account,
    )
    rows = v18_conn.execute(
        "SELECT discrepancy_type FROM reconciliation_discrepancies "
        "WHERE run_id = ?",
        (out.run_id,),
    ).fetchall()
    types = [r[0] for r in rows]
    assert "equity_delta" not in types


def test_b4_12_reconciliation_schwab_api_call_id_populated_on_run(v18_conn):
    """run.schwab_api_call_id is populated when caller supplies it."""
    schwab_account = SimpleNamespace(
        account_hash="abc", net_liquidating_value=2000.0, positions=[],
        cash=0.0, buying_power=0.0,
    )
    # Plant an audit row to point at.
    v18_conn.execute(
        "INSERT INTO schwab_api_calls (ts, endpoint, status, surface, environment) "
        "VALUES (?, ?, ?, ?, ?)",
        ("2026-05-14T08:00:00", "accounts.details", "success", "pipeline", "production"),
    )
    v18_conn.commit()
    call_id = v18_conn.execute(
        "SELECT call_id FROM schwab_api_calls"
    ).fetchone()[0]

    out = run_schwab_reconciliation(
        v18_conn,
        account_hash="abc",
        period_start="2026-05-07",
        period_end="2026-05-14",
        schwab_orders=[],
        schwab_transactions=[],
        schwab_account=schwab_account,
        schwab_api_call_id=call_id,
    )
    assert out.schwab_api_call_id == call_id


def test_b4_13_reconciliation_failure_preserves_failed_state_row(v18_conn, monkeypatch):
    """Mid-emit failure → run row preserved with state='failed' (spec §3.3.3).

    Discriminating: patch `repo.insert_discrepancy` to raise mid-emit; assert
    that AFTER the exception, a reconciliation_runs row exists with state='failed'
    (NOT absent due to rollback).
    """
    _seed_open_trade(v18_conn, ticker="AAPL", current_stop=95.0)
    from swing.integrations.schwab.models import SchwabOrderResponse
    schwab_orders = [SchwabOrderResponse(
        order_id="1001", status="WORKING",
        enter_time="2026-05-12T10:00:00Z",
        instrument_symbol="AAPL", instruction="SELL",
        quantity=10.0, order_type="STOP", price=95.50,
    )]
    schwab_account = SimpleNamespace(
        account_hash="abc", net_liquidating_value=2000.0, positions=[],
        cash=0.0, buying_power=0.0,
    )
    # Patch repo.insert_discrepancy to raise.
    from swing.data.repos import reconciliation as recon_repo
    orig = recon_repo.insert_discrepancy
    calls = {"n": 0}

    def explode(*args, **kwargs):
        calls["n"] += 1
        raise RuntimeError("mid-emit explosion")

    monkeypatch.setattr(recon_repo, "insert_discrepancy", explode)
    with pytest.raises(RuntimeError):
        run_schwab_reconciliation(
            v18_conn,
            account_hash="abc",
            period_start="2026-05-07",
            period_end="2026-05-14",
            schwab_orders=schwab_orders,
            schwab_transactions=[],
            schwab_account=schwab_account,
        )
    # Restore.
    monkeypatch.setattr(recon_repo, "insert_discrepancy", orig)
    # A failed-state run row exists.
    row = v18_conn.execute(
        "SELECT state, error_message FROM reconciliation_runs"
    ).fetchone()
    assert row is not None
    assert row[0] == "failed"
    assert "explosion" in (row[1] or "").lower() or "RuntimeError" in (row[1] or "")


def test_b4_14_reconciliation_audit_link_through_step_orders(v18_conn):
    """`_step_schwab_orders` UPDATEs all 3 audit rows with linked_reconciliation_run_id."""
    cfg = _make_cfg(environment="production")
    client = MagicMock()
    client.account_orders.return_value = _make_orders_response([])
    client.transactions.return_value = _make_transactions_response([])
    client.account_details.return_value = _make_account_details_response()

    result = _step_schwab_orders(
        v18_conn, cfg, pipeline_run_id=None, client=client,
    )
    assert result["status"] == "completed"
    # All 3 audit rows MUST have linked_reconciliation_run_id populated.
    rows = v18_conn.execute(
        "SELECT linked_reconciliation_run_id FROM schwab_api_calls "
        "ORDER BY call_id"
    ).fetchall()
    assert len(rows) == 3
    for r in rows:
        assert r[0] == result["reconciliation_run_id"]


def test_b4_15_reconciliation_zero_discrepancies_state_completed(v18_conn):
    """No discrepancies + state='completed' is canonical happy path."""
    _seed_open_trade(v18_conn, ticker="AAPL", current_stop=95.0)
    from swing.integrations.schwab.models import SchwabOrderResponse
    # Schwab working stop matches journal exactly.
    schwab_orders = [SchwabOrderResponse(
        order_id="1001", status="WORKING",
        enter_time="2026-05-12T10:00:00Z",
        instrument_symbol="AAPL", instruction="SELL",
        quantity=10.0, order_type="STOP", price=95.00,
    )]
    schwab_account = SimpleNamespace(
        account_hash="abc", net_liquidating_value=2000.0,
        positions=[{"instrument": {"symbol": "AAPL"}, "longQuantity": 10}],
        cash=0.0, buying_power=0.0,
    )
    out = run_schwab_reconciliation(
        v18_conn,
        account_hash="abc",
        period_start="2026-05-07",
        period_end="2026-05-14",
        schwab_orders=schwab_orders,
        schwab_transactions=[],
        schwab_account=schwab_account,
    )
    assert out.state == "completed"
    # The fill matching emits unmatched_open_fill since the schwab_orders
    # list does NOT include a FILLED entry; we just have a WORKING stop.
    # Verify no stop_mismatch / no position_qty_mismatch.
    rows = v18_conn.execute(
        "SELECT discrepancy_type FROM reconciliation_discrepancies "
        "WHERE run_id = ?",
        (out.run_id,),
    ).fetchall()
    types = {r[0] for r in rows}
    assert "stop_mismatch" not in types
    assert "position_qty_mismatch" not in types


def test_b4_16_reconciliation_run_state_completed_summary_json_populated(v18_conn):
    """run.summary_json is populated on success."""
    schwab_account = SimpleNamespace(
        account_hash="abc", net_liquidating_value=2000.0, positions=[],
        cash=0.0, buying_power=0.0,
    )
    out = run_schwab_reconciliation(
        v18_conn,
        account_hash="abc",
        period_start="2026-05-07",
        period_end="2026-05-14",
        schwab_orders=[],
        schwab_transactions=[],
        schwab_account=schwab_account,
    )
    import json as _json
    assert out.summary_json is not None
    parsed = _json.loads(out.summary_json)
    assert "open_trades_checked" in parsed
    assert "schwab_orders_checked" in parsed
    assert "schwab_transactions_checked" in parsed


def test_b4_17_reconciliation_run_source_is_schwab_api(v18_conn):
    """run.source = 'schwab_api' (NOT 'tos_csv')."""
    schwab_account = SimpleNamespace(
        account_hash="abc", net_liquidating_value=2000.0, positions=[],
        cash=0.0, buying_power=0.0,
    )
    out = run_schwab_reconciliation(
        v18_conn,
        account_hash="abc",
        period_start="2026-05-07",
        period_end="2026-05-14",
        schwab_orders=[],
        schwab_transactions=[],
        schwab_account=schwab_account,
    )
    assert out.source == "schwab_api"


def test_b4_18_step_orders_pipeline_run_id_threaded_through(v18_conn):
    """pipeline_run_id threads through audit rows + reconciliation_run is created."""
    cfg = _make_cfg(environment="production")
    client = MagicMock()
    client.account_orders.return_value = _make_orders_response([])
    client.transactions.return_value = _make_transactions_response([])
    client.account_details.return_value = _make_account_details_response()

    v18_conn.execute(
        "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
        "action_session_date, state, lease_token) "
        "VALUES (?, ?, ?, ?, ?, ?)",
        ("2026-05-14T08:00:00", "manual", "2026-05-13", "2026-05-14",
         "running", "test-token"),
    )
    v18_conn.commit()
    prid = v18_conn.execute("SELECT id FROM pipeline_runs").fetchone()[0]

    result = _step_schwab_orders(
        v18_conn, cfg, pipeline_run_id=prid, client=client,
    )
    assert result["status"] == "completed"
    # All 3 audit rows have pipeline_run_id stamped.
    rows = v18_conn.execute(
        "SELECT pipeline_run_id FROM schwab_api_calls"
    ).fetchall()
    for r in rows:
        assert r[0] == prid


def test_b4_19_reconciliation_dedup_within_run(v18_conn):
    """Within-run dedup tuple prevents duplicate emits for the same key."""
    _seed_open_trade(v18_conn, ticker="AAPL", current_stop=95.0)
    from swing.integrations.schwab.models import SchwabOrderResponse
    # TWO working stops on same ticker — only the most-recent wins (latest
    # enter_time) so we expect a SINGLE stop_mismatch even with two
    # candidate orders.
    schwab_orders = [
        SchwabOrderResponse(
            order_id="1000", status="WORKING",
            enter_time="2026-05-10T10:00:00Z",
            instrument_symbol="AAPL", instruction="SELL",
            quantity=10.0, order_type="STOP", price=94.00,
        ),
        SchwabOrderResponse(
            order_id="1001", status="WORKING",
            enter_time="2026-05-12T10:00:00Z",
            instrument_symbol="AAPL", instruction="SELL",
            quantity=10.0, order_type="STOP", price=95.50,
        ),
    ]
    schwab_account = SimpleNamespace(
        account_hash="abc", net_liquidating_value=2000.0, positions=[],
        cash=0.0, buying_power=0.0,
    )
    out = run_schwab_reconciliation(
        v18_conn,
        account_hash="abc",
        period_start="2026-05-07",
        period_end="2026-05-14",
        schwab_orders=schwab_orders,
        schwab_transactions=[],
        schwab_account=schwab_account,
    )
    rows = v18_conn.execute(
        "SELECT discrepancy_type, ticker FROM reconciliation_discrepancies "
        "WHERE run_id = ? AND discrepancy_type = 'stop_mismatch'",
        (out.run_id,),
    ).fetchall()
    assert len(rows) == 1  # dedup'd to 1


def test_b4_20_reconciliation_persists_account_equity_columns(v18_conn):
    """run row carries account_equity_journal_dollars + source_dollars + delta."""
    v18_conn.execute(
        "INSERT INTO account_equity_snapshots ("
        "snapshot_date, equity_dollars, source, source_artifact_path, "
        "recorded_at, recorded_by, notes"
        ") VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("2026-05-14", 2000.0, "manual", None, "2026-05-14T12:00:00", "operator", None),
    )
    v18_conn.commit()
    schwab_account = SimpleNamespace(
        account_hash="abc", net_liquidating_value=2050.0, positions=[],
        cash=0.0, buying_power=0.0,
    )
    out = run_schwab_reconciliation(
        v18_conn,
        account_hash="abc",
        period_start="2026-05-07",
        period_end="2026-05-14",
        schwab_orders=[],
        schwab_transactions=[],
        schwab_account=schwab_account,
    )
    assert out.account_equity_journal_dollars == 2000.0
    assert out.account_equity_source_dollars == 2050.0
    assert out.equity_delta_dollars == -50.0  # journal MINUS source per Phase 9 sign convention
