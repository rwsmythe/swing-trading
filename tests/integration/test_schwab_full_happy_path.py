"""Schwab API arc-closer Sub-bundle D Task T-D.3 — combined SERVICE-COMPOSITION
end-to-end happy path (NOT CLI-driven E2E).

Codex R1 Major #4 ACCEPT-WITH-RATIONALE clarification: this test exercises
the SERVICE-COMPOSITION chain (snapshot → orders → reconciliation →
market-data → briefing render) in one connection — which the per-CLI
tests do NOT cover. It deliberately bypasses the `swing schwab` CLI surface
+ pipeline composition; that coverage is provided elsewhere by:

  - `tests/cli/test_schwab_status_d_full_surface.py` — `swing schwab status`
    CLI surface (T-D.1 + Codex R1 fixes).
  - `tests/integrations/test_cli_schwab_fetch_verify_marketdata.py` —
    `swing schwab fetch --verify-marketdata` CLI surface (T-C.5).
  - `tests/integrations/test_schwab_setup_cli.py` — `swing schwab setup`
    CLI surface (T-A.4 + Codex R1 M#3 message fix).
  - `tests/integrations/test_schwab_pipeline_steps.py` — pipeline-internal
    `_step_schwab_*` invocation under lease.

Adding CLI-level happy-path coverage here would duplicate those tests
without adding new defect-detection capability. The asymmetry is
intentional + must be preserved: this test owns the service-composition
contract; the per-CLI tests own the per-command UX contract.

Plan §Tasks-D T-D.3 + dispatch brief §0.9 + §5.2 T-D.3 row: a SINGLE
test that exercises the operator's natural workflow across all of the
shipped Schwab API sub-bundles (A + B + C) in one
test/connection.

Five surfaces covered (mirrors `tests/integration/test_phase9_full_happy_path.py`
shape — single test/connection, isolated DB, USERPROFILE+HOME monkeypatch
per CLAUDE.md gotcha):

  §1 (Sub-bundle A — OAuth bootstrap surface) — schema migrate +
      verify NO live OAuth round-trip is required (this test never
      touches schwabdev.Client constructor; it injects pre-built
      MagicMock clients into the pipeline-step entry points instead).
      Pattern matches `tests/integrations/test_schwab_pipeline_steps.py`
      which is the canonical mock-driven coverage for the OAuth-derived
      Client surface.

  §2 (Sub-bundle B — _step_schwab_snapshot) — production env writes
      `account_equity_snapshots(source='schwab_api')` row + paired
      `schwab_api_calls` audit row with `linked_snapshot_id` populated
      via the combined-tx2 link helper.

  §3 (Sub-bundle B — _step_schwab_orders) — production env writes
      `reconciliation_runs(source='schwab_api')` row + at least one
      `reconciliation_discrepancies` row (stop_mismatch + position
      qty mismatch from a planted open trade vs Schwab WORKING stop)
      + 3 paired `schwab_api_calls` audit rows with
      `linked_reconciliation_run_id` populated.

  §4 (Sub-bundle C — market-data ladder fill) — direct invocation of
      `get_quotes_batch` + `get_price_history` (the two endpoints the
      `swing schwab fetch --verify-marketdata` CLI exercises) writes
      `marketdata.quotes` + `marketdata.pricehistory` audit rows. Note
      that the verification path does NOT install the ladder hook into
      PriceCache/OhlcvCache + does NOT write OHLCV archive — verified
      by the `test_cli_schwab_fetch_verify_marketdata.py:c5_01` peer
      test. We assert the audit-row contract here.

  §5 (briefing render — happy path / no degraded banner) — call the
      `build_briefing_view_model` + `render_briefing_md` path directly
      with a minimal `BriefingInputs` and assert the rendered briefing.md
      string is non-empty + carries the expected weather + open-position
      sections. T-D.5 (degraded banner) is OUT OF SCOPE for this test
      — the binding criterion here is that the happy path renders
      without surfacing a banner.

Cassette/mock approach (per dispatch brief §5.2 T-D.3 binding):
  - FULLY mock-driven (no recorded cassettes — cassette-recording for
    Schwab requires operator-paired Task 0.b sessions which have NOT
    landed; pattern matches existing `test_schwab_pipeline_steps.py`).
  - tmp_path DB (isolated; never inherits operator production state).
  - USERPROFILE+HOME monkeypatch (CLAUDE.md gotcha — Schwab service
    paths invoke `_user_home()` for tokens DB resolution; without
    monkeypatch any leakage would clobber operator's real
    `~/swing-data/`).
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from click.testing import CliRunner

from swing.cli import main
from swing.data.db import EXPECTED_SCHEMA_VERSION, ensure_schema
from swing.evaluation.dates import last_completed_session
from swing.integrations.schwab import client as schwab_client_module
from swing.integrations.schwab.marketdata import (
    get_price_history,
    get_quotes_batch,
)
from swing.integrations.schwab.pipeline_steps import (
    _step_schwab_orders,
    _step_schwab_snapshot,
)
from swing.rendering.briefing import BriefingInputs, build_briefing_view_model
from swing.rendering.briefing_md import render_briefing_md
from tests.cli.test_cli_eval import _minimal_config

# ============================================================================
# Fixtures + helpers (mirror tests/integrations/test_schwab_pipeline_steps.py)
# ============================================================================


@pytest.fixture(autouse=True)
def reset_schwab_redaction_state():
    """Token-redaction logging factory cleanup (mirror T-A.10 fixture)."""
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


def _make_cfg(*, environment: str = "production",
              account_hash: str = "abc...64charhash") -> SimpleNamespace:
    """Minimal cfg.integrations.schwab namespace for the pipeline-step entry points."""
    return SimpleNamespace(
        integrations=SimpleNamespace(
            schwab=SimpleNamespace(
                environment=environment,
                account_hash=account_hash,
                lookback_days=7,
                timeout_seconds=30.0,
                marketdata_ladder_enabled=True,
                callback_url="https://127.0.0.1",
            ),
        ),
    )


def _mock_response(json_value, *, status_code: int = 200, headers=None):
    resp = MagicMock()
    resp.json.return_value = json_value
    resp.status_code = status_code
    resp.headers = headers or {}
    return resp


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


def _make_quotes_response(symbols: list[str]):
    """Schwab-style quotes payload — one entry per symbol, all OK."""
    return _mock_response({
        s: {
            "quote": {
                "lastPrice": 100.0 + i,
                "bidPrice": 99.0 + i,
                "askPrice": 101.0 + i,
                "mark": 100.0 + i,
                "quoteTime": "2026-05-14T15:30:00Z",
                "delayed": False,
            },
        }
        for i, s in enumerate(symbols)
    })


def _make_price_history_response(symbol: str = "AAPL"):
    """Schwab-style price_history payload — 3 daily bars."""
    return _mock_response({
        "empty": False,
        "symbol": symbol,
        "candles": [
            {
                "datetime": 1747094400000,
                "open": 100.0, "high": 101.0, "low": 99.0,
                "close": 100.5, "volume": 1_000_000,
            },
            {
                "datetime": 1747180800000,
                "open": 100.5, "high": 102.0, "low": 100.0,
                "close": 101.5, "volume": 1_100_000,
            },
            {
                "datetime": 1747267200000,
                "open": 101.5, "high": 103.0, "low": 101.0,
                "close": 102.5, "volume": 1_200_000,
            },
        ],
    })


def _seed_open_trade(
    conn: sqlite3.Connection,
    *,
    ticker: str = "AAPL",
    shares: int = 10,
    entry_price: float = 100.0,
    current_stop: float = 95.0,
) -> int:
    """Seed an open trade + entry fill.

    Mirrors `_seed_open_trade` from tests/integrations/test_schwab_pipeline_steps.py
    so the orders step has a target for stop_mismatch/position_qty_mismatch
    discriminating discrepancies.
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
    conn.execute(
        "INSERT INTO fills ("
        "trade_id, fill_datetime, action, quantity, price, fees"
        ") VALUES (?, ?, ?, ?, ?, ?)",
        (trade_id, "2026-05-10T10:00:00", "entry", shares, entry_price, 0.0),
    )
    conn.commit()
    return trade_id


# ============================================================================
# THE single E2E happy-path test
# ============================================================================


def test_schwab_full_happy_path_across_all_sub_bundles(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Single test exercising A+B+C surfaces in one connection.

    Discriminating arithmetic per §3 (orders step):
      - 1 open trade planted (AAPL @ shares=10, current_stop=95.0).
      - Schwab WORKING stop reports price=95.50 → stop_mismatch (material=1).
      - Schwab `account_details.positions` returns empty → position_qty_mismatch
        emitted for AAPL (journal_qty=10 vs source_qty=0).
      - Therefore the orders run produces ≥2 discrepancy rows; the assertion
        below uses `>= 1` to stay robust to future emit-set changes (a
        peer test in `test_schwab_pipeline_steps.py` pins the exact
        emit set for stop+qty independently).
    """
    # CLAUDE.md gotcha: USERPROFILE+HOME monkeypatch — Schwab service paths
    # invoke `_user_home()` for tokens DB resolution. Without this leak the
    # test would touch the operator's real `~/swing-data/`.
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("USERPROFILE", str(home))
    monkeypatch.setenv("HOME", str(home))
    project = tmp_path / "project"
    project.mkdir()
    cfg_path = _minimal_config(project, home)
    runner = CliRunner()

    # ===========================================================================
    # §1: OAuth setup (substituted by schema bootstrap + mock-client injection).
    #
    # Real OAuth requires browser paste-back — incompatible with automated
    # tests. We mirror the canonical pattern from
    # tests/integrations/test_schwab_pipeline_steps.py: ensure_schema lands
    # the v18 schema (Schwab tables included), then later sub-sections inject
    # MagicMock clients directly into the pipeline-step entry points so the
    # schwabdev.Client constructor + token paste-back are NEVER invoked.
    # ===========================================================================
    r_init = runner.invoke(main, ["--config", str(cfg_path), "db-migrate"])
    assert r_init.exit_code == 0, r_init.output
    db_path = home / "swing-data" / "swing.db"
    assert db_path.exists()

    # Verify schema landed at expected version.
    bootstrap_conn = sqlite3.connect(db_path)
    try:
        version = bootstrap_conn.execute(
            "SELECT version FROM schema_version"
        ).fetchone()[0]
        assert version == EXPECTED_SCHEMA_VERSION
        # Schwab tables present.
        tables = {
            r[0] for r in bootstrap_conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        assert "schwab_api_calls" in tables
        assert "account_equity_snapshots" in tables
        assert "reconciliation_runs" in tables
    finally:
        bootstrap_conn.close()

    cfg = _make_cfg(environment="production")

    # ===========================================================================
    # §2: snapshot pipeline step — production env, mock client.
    # Discriminating: 1 audit row + 1 snapshot row + linkage stamped.
    # ===========================================================================
    snap_conn = ensure_schema(db_path)  # reopen for the step entry point
    try:
        snap_client = MagicMock()
        snap_client.account_details.return_value = _make_account_details_response(2014.36)

        snap_result = _step_schwab_snapshot(
            snap_conn, cfg, pipeline_run_id=None, client=snap_client,
        )
        assert snap_result["status"] == "completed", snap_result
        assert snap_result["snapshot_id"] is not None
        assert snap_result["call_id"] is not None

        # Pair: audit row + snapshot row.
        audit_count = snap_conn.execute(
            "SELECT COUNT(*) FROM schwab_api_calls"
        ).fetchone()[0]
        snap_count = snap_conn.execute(
            "SELECT COUNT(*) FROM account_equity_snapshots WHERE source='schwab_api'"
        ).fetchone()[0]
        assert audit_count == 1, f"expected 1 audit row, got {audit_count}"
        assert snap_count == 1, f"expected 1 schwab_api snapshot, got {snap_count}"

        # Linkage on the audit row.
        link_row = snap_conn.execute(
            "SELECT status, linked_snapshot_id FROM schwab_api_calls "
            "WHERE call_id = ?",
            (snap_result["call_id"],),
        ).fetchone()
        assert link_row[0] == "success"
        assert link_row[1] == snap_result["snapshot_id"]

        # snapshot_date matches backward-looking last_completed_session
        # (CLAUDE.md gotcha — read/write session-anchor alignment).
        expected_date = last_completed_session(datetime.now()).isoformat()
        snap_date = snap_conn.execute(
            "SELECT snapshot_date FROM account_equity_snapshots "
            "WHERE snapshot_id = ?",
            (snap_result["snapshot_id"],),
        ).fetchone()[0]
        assert snap_date == expected_date

        # ===========================================================================
        # §3: orders pipeline step — production env, mock client + planted trade.
        # Discriminating: ≥1 discrepancy emitted; 3 audit rows linked to the run.
        # ===========================================================================
        # Plant 1 open trade so the reconciliation has a target.
        _seed_open_trade(
            snap_conn, ticker="AAPL", shares=10,
            entry_price=100.0, current_stop=95.0,
        )

        # Stub a Schwab WORKING stop at 95.50 so stop_mismatch fires; positions=[]
        # so position_qty_mismatch fires for AAPL too.
        from swing.integrations.schwab.models import (  # noqa: PLC0415
            SchwabOrderResponse,
        )
        orders_client = MagicMock()
        orders_payload_raw = {
            "orderId": 1001, "status": "WORKING",
            "enteredTime": "2026-05-12T10:00:00Z",
            "orderType": "STOP",
            "price": 95.50,
            "orderLegCollection": [{
                "instruction": "SELL", "quantity": 10,
                "instrument": {"symbol": "AAPL"},
            }],
        }
        orders_client.account_orders.return_value = _mock_response([orders_payload_raw])
        orders_client.transactions.return_value = _mock_response([])
        orders_client.account_details.return_value = _make_account_details_response(2014.36)

        # Reuse SchwabOrderResponse to check our mocked payload would map cleanly;
        # imported here only to mirror the canonical pipeline-steps test pattern.
        _ = SchwabOrderResponse  # noqa: B018 (referenced for forward-compat parity)

        orders_result = _step_schwab_orders(
            snap_conn, cfg, pipeline_run_id=None, client=orders_client,
        )
        assert orders_result["status"] == "completed", orders_result
        assert orders_result["reconciliation_run_id"] is not None
        assert len(orders_result["call_ids"]) == 3

        # Reconciliation run row exists, source='schwab_api'.
        run_row = snap_conn.execute(
            "SELECT source, state FROM reconciliation_runs WHERE run_id = ?",
            (orders_result["reconciliation_run_id"],),
        ).fetchone()
        assert run_row == ("schwab_api", "completed")

        # All 3 audit rows linked to this run.
        link_rows = snap_conn.execute(
            "SELECT linked_reconciliation_run_id FROM schwab_api_calls "
            "WHERE call_id IN (?, ?, ?)",
            tuple(orders_result["call_ids"]),
        ).fetchall()
        assert len(link_rows) == 3
        for r in link_rows:
            assert r[0] == orders_result["reconciliation_run_id"]

        # At least one discrepancy row written.
        discrep_rows = snap_conn.execute(
            "SELECT discrepancy_type, ticker FROM reconciliation_discrepancies "
            "WHERE run_id = ?",
            (orders_result["reconciliation_run_id"],),
        ).fetchall()
        assert len(discrep_rows) >= 1, (
            f"expected ≥1 discrepancy from mismatched stop+positions; got "
            f"{discrep_rows}"
        )
        types = {r[0] for r in discrep_rows}
        # Either stop_mismatch (from WORKING stop at 95.50 vs current_stop=95.0)
        # OR position_qty_mismatch (from journal qty=10 vs source qty=0).
        # Both are MAT=1 per MATERIAL_BY_TYPE; happy path here is "discrepancy
        # surfacing works end-to-end" — pin tests for exact emits live in
        # tests/integrations/test_schwab_pipeline_steps.py.
        assert types & {"stop_mismatch", "position_qty_mismatch"}, types

        # ===========================================================================
        # §4: market-data cache fill via direct get_quotes_batch + get_price_history.
        # The CLI surface `swing schwab fetch --verify-marketdata` invokes the
        # same two endpoints; we exercise them directly here to keep the test
        # focused + fast.
        # Discriminating: +2 audit rows (marketdata.quotes + marketdata.pricehistory)
        # both with status='success', surface='cli', environment='production'.
        # ===========================================================================
        md_audit_pre = snap_conn.execute(
            "SELECT COUNT(*) FROM schwab_api_calls WHERE endpoint LIKE 'marketdata.%'"
        ).fetchone()[0]
        assert md_audit_pre == 0  # nothing yet

        md_client = MagicMock()
        md_client.quotes.return_value = _make_quotes_response(["AAPL"])
        md_client.price_history.return_value = _make_price_history_response("AAPL")

        quotes = get_quotes_batch(
            md_client, snap_conn, ["AAPL"],
            surface="cli", environment="production", pipeline_run_id=None,
        )
        assert "AAPL" in quotes

        history = get_price_history(
            md_client, snap_conn, "AAPL",
            period_type="day", period=10,
            frequency_type="daily", frequency=1,
            surface="cli", environment="production", pipeline_run_id=None,
        )
        assert history is not None

        md_audit_rows = snap_conn.execute(
            "SELECT endpoint, surface, environment, status, "
            "linked_snapshot_id, linked_reconciliation_run_id "
            "FROM schwab_api_calls WHERE endpoint LIKE 'marketdata.%' "
            "ORDER BY call_id ASC"
        ).fetchall()
        assert len(md_audit_rows) == 2
        endpoints_md = {r[0] for r in md_audit_rows}
        assert endpoints_md == {"marketdata.quotes", "marketdata.pricehistory"}
        for r in md_audit_rows:
            assert r[1] == "cli"
            assert r[2] == "production"
            assert r[3] == "success"
            # market-data verify path does NOT link snapshot/recon.
            assert r[4] is None
            assert r[5] is None

        # ===========================================================================
        # §5: briefing render — happy path. Build a minimal BriefingInputs +
        # render via the markdown path. Assert non-empty + carries expected
        # structural sections; T-D.5 (degraded banner) is OUT OF SCOPE so the
        # banner string MUST NOT appear here.
        # ===========================================================================
        # Read open trades for the briefing inputs (we seeded AAPL above).
        from swing.data.repos.trades import list_open_trades  # noqa: PLC0415
        open_trades = list_open_trades(snap_conn)
        assert any(t.ticker == "AAPL" for t in open_trades)

        action_session_iso = "2026-05-14"
        data_asof_iso = "2026-05-13"
        inputs = BriefingInputs(
            action_session_date=action_session_iso,
            data_asof_date=data_asof_iso,
            generated_at="2026-05-14T08:00:00",
            weather=None, weather_is_stale=True,
            equity=2014.36, open_count=len(open_trades),
            soft_warn=4, hard_cap=6,
            last_pipeline_ts="2026-05-14T08:00:00",
            pipeline_is_stale=False, current_session_match=True,
            recommendations=[], open_trades=open_trades,
        )
        vm = build_briefing_view_model(inputs)
        md = render_briefing_md(vm)
        assert isinstance(md, str)
        assert md.strip() != ""
        # Structural sections from the canonical briefing_md template.
        assert action_session_iso in md
        # Open positions section surfaces the planted ticker.
        assert "AAPL" in md
        # Banner from T-D.5 (degraded) MUST NOT fire on the happy path.
        # T-D.5 shipped the spec §3.4.4 / §7.2 verbatim copy
        # "Schwab integration: degraded" (with colon); this assertion
        # serves as the cross-bundle pin discriminating regression test
        # — the happy path MUST NOT emit the degraded banner because
        # `is_schwab_degraded` returns (False, None) when there are no
        # `schwab_api_calls` rows OR when the most-recent row is
        # `status='success'` (this test plants only success rows).
        assert "Schwab integration: degraded" not in md

    finally:
        snap_conn.close()
