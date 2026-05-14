"""Phase 9 Task B.1 — reconciliation repo CRUD + dataclass validators.

Per plan §E T-B.1 acceptance criteria:
- Repo functions match file map signatures (insert/update/get/list).
- ``list_recent_runs`` companion two-read pattern via
  ``most_recent_completed_run`` + ``most_recent_started_run`` per CLAUDE.md
  gotcha.
- ``list_unresolved_material_for_active_trades`` matches spec §5.1
  CANONICAL #1 (active-trade states only).
- ``list_unresolved_material_for_closed_trades`` matches spec §5.1
  CANONICAL #2 (closed/reviewed states only).
- ``count_runs_for_artifact_sha256`` advisory for re-run detection.
- Repo functions do NOT call ``conn.commit()`` (Finviz I1 lesson; grep
  in the implementation file already enforces).
- Dataclass ``__post_init__`` validators reject invalid enums / NaN / inf
  / cross-field invariants.
"""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path

import pytest

from swing.data.datetime_helpers import now_ms
from swing.data.db import ensure_schema
from swing.data.models import (
    ReconciliationDiscrepancy,
    ReconciliationRun,
)
from swing.data.repos import reconciliation as repo


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    return ensure_schema(tmp_path / "phase9_b1.db")


# ---------------------------------------------------------------------------
# Test helpers
# ---------------------------------------------------------------------------


def _insert_trade(
    conn: sqlite3.Connection,
    *,
    ticker: str = "ABC",
    state: str = "entered",
    entry_date: str = "2026-05-12",
    initial_shares: int = 10,
    current_size: int | None = None,
) -> int:
    """Mirrors the helper in test_phase9_reconciliation_schema_verification.py."""
    if current_size is None:
        current_size = initial_shares
    conn.execute(
        "INSERT INTO trades ("
        "ticker, entry_date, entry_price, initial_shares, initial_stop, "
        "current_stop, state, sector, industry, trade_origin, "
        "pre_trade_locked_at, current_size"
        ") VALUES ("
        "?, ?, 100.0, ?, 95.0, 95.0, ?, "
        "'Tech', 'Software', 'manual_off_pipeline', "
        "?, ?)",
        (ticker, entry_date, initial_shares, state, now_ms(), current_size),
    )
    return conn.execute(
        "SELECT id FROM trades WHERE ticker = ? AND entry_date = ?",
        (ticker, entry_date),
    ).fetchone()[0]


def _insert_run(
    conn: sqlite3.Connection,
    *,
    source: str = "tos_csv",
    state: str = "running",
    started_ts: str | None = None,
    finished_ts: str | None = None,
    source_artifact_sha256: str | None = None,
    **kwargs,
) -> int:
    if started_ts is None:
        started_ts = now_ms()
    return repo.insert_run(
        conn,
        source=source,
        state=state,
        started_ts=started_ts,
        finished_ts=finished_ts,
        source_artifact_sha256=source_artifact_sha256,
        **kwargs,
    )


def _insert_discrepancy(
    conn: sqlite3.Connection,
    *,
    run_id: int,
    discrepancy_type: str = "close_price_mismatch",
    field_name: str = "price",
    material_to_review: int = 1,
    trade_id: int | None = None,
    **kwargs,
) -> int:
    return repo.insert_discrepancy(
        conn,
        run_id=run_id,
        discrepancy_type=discrepancy_type,
        field_name=field_name,
        material_to_review=material_to_review,
        created_at=now_ms(),
        trade_id=trade_id,
        **kwargs,
    )


# ===========================================================================
# §1 — ReconciliationRun dataclass validator
# ===========================================================================


def _make_run(**overrides) -> ReconciliationRun:
    base = dict(
        run_id=None,
        source="tos_csv",
        source_artifact_path=None,
        source_artifact_sha256=None,
        period_start=None,
        period_end=None,
        started_ts="2026-05-12T08:00:00.000",
        finished_ts=None,
        state="running",
        account_equity_journal_dollars=None,
        account_equity_source_dollars=None,
        equity_delta_dollars=None,
        trades_reconciled_count=None,
        fills_reconciled_count=None,
        discrepancies_count=None,
        unresolved_discrepancies_count=None,
        summary_json=None,
        error_message=None,
        notes=None,
    )
    base.update(overrides)
    return ReconciliationRun(**base)


def test_recon_run_accepts_minimal_valid_running() -> None:
    r = _make_run()
    assert r.state == "running"


def test_recon_run_rejects_invalid_source() -> None:
    with pytest.raises(ValueError, match="source must be one of"):
        _make_run(source="csv_import")


def test_recon_run_rejects_invalid_state() -> None:
    with pytest.raises(ValueError, match="state must be one of"):
        _make_run(state="aborted")


def test_recon_run_rejects_nan_equity() -> None:
    with pytest.raises(ValueError, match="must be finite"):
        _make_run(account_equity_journal_dollars=float("nan"))


def test_recon_run_rejects_inf_equity_delta() -> None:
    with pytest.raises(ValueError, match="must be finite"):
        _make_run(equity_delta_dollars=float("inf"))


def test_recon_run_rejects_negative_count() -> None:
    with pytest.raises(ValueError, match="trades_reconciled_count.*>= 0"):
        _make_run(trades_reconciled_count=-1)


def test_recon_run_rejects_finished_before_started() -> None:
    with pytest.raises(ValueError, match="finished_ts.*>= "):
        _make_run(
            state="completed",
            started_ts="2026-05-12T10:00:00.000",
            finished_ts="2026-05-12T09:00:00.000",
        )


def test_recon_run_rejects_running_with_finished() -> None:
    with pytest.raises(ValueError, match="state='running' requires finished_ts"):
        _make_run(
            state="running",
            finished_ts="2026-05-12T10:00:00.000",
        )


def test_recon_run_rejects_completed_without_finished() -> None:
    with pytest.raises(ValueError, match="requires finished_ts set"):
        _make_run(state="completed", finished_ts=None)


def test_recon_run_rejects_failed_without_error_message() -> None:
    with pytest.raises(ValueError, match="error_message"):
        _make_run(
            state="failed",
            finished_ts="2026-05-12T09:00:00.000",
            error_message=None,
        )


def test_recon_run_accepts_completed_with_finished_and_summary() -> None:
    r = _make_run(
        state="completed",
        finished_ts="2026-05-12T09:00:00.000",
        discrepancies_count=3,
        unresolved_discrepancies_count=2,
    )
    assert r.state == "completed"
    assert r.discrepancies_count == 3


# ---------------------------------------------------------------------------
# Codex R1 Major #5 — schwab_api_call_id field validator + round-trip
# ---------------------------------------------------------------------------


def test_recon_run_schwab_api_call_id_defaults_to_none() -> None:
    """schwab_api_call_id is an optional trailing field; default None
    preserves backward-compat with tos_csv runs.
    """
    r = _make_run()
    assert r.schwab_api_call_id is None


def test_recon_run_accepts_positive_schwab_api_call_id() -> None:
    r = _make_run(schwab_api_call_id=42)
    assert r.schwab_api_call_id == 42


def test_recon_run_rejects_zero_negative_or_non_int_schwab_api_call_id() -> None:
    """Codex R1 Major #5: zero / negative / non-int / bool rejected."""
    with pytest.raises(ValueError, match="schwab_api_call_id"):
        _make_run(schwab_api_call_id=0)
    with pytest.raises(ValueError, match="schwab_api_call_id"):
        _make_run(schwab_api_call_id=-1)
    with pytest.raises(ValueError, match="schwab_api_call_id"):
        _make_run(schwab_api_call_id="1")
    with pytest.raises(ValueError, match="schwab_api_call_id"):
        _make_run(schwab_api_call_id=True)


def test_insert_run_round_trips_schwab_api_call_id_when_set(
    conn: sqlite3.Connection,
) -> None:
    """Codex R1 Major #5: insert_run accepts schwab_api_call_id, persists
    to DB, get_run returns it on the dataclass.

    To satisfy the FK ON DELETE SET NULL constraint, first seed a real
    schwab_api_calls row + use its call_id.
    """
    # Seed a pipeline_runs row + schwab_api_calls row to satisfy FKs.
    cur = conn.execute(
        "INSERT INTO pipeline_runs ("
        "started_ts, trigger, data_asof_date, action_session_date, "
        "state, lease_token"
        ") VALUES (?, ?, ?, ?, ?, ?)",
        ("2026-05-13T08:00:00", "manual", "2026-05-12", "2026-05-13",
         "running", "test-token"),
    )
    pipeline_run_id = int(cur.lastrowid)
    cur = conn.execute(
        "INSERT INTO schwab_api_calls ("
        "ts, endpoint, status, pipeline_run_id, surface, environment"
        ") VALUES (?, ?, ?, ?, ?, ?)",
        ("2026-05-13T12:00:00", "accounts.transactions.list", "success",
         pipeline_run_id, "pipeline", "sandbox"),
    )
    call_id = int(cur.lastrowid)

    rid = repo.insert_run(
        conn,
        source="schwab_api",
        started_ts="2026-05-13T12:00:00",
        schwab_api_call_id=call_id,
    )
    r = repo.get_run(conn, rid)
    assert r is not None
    assert r.schwab_api_call_id == call_id


def test_insert_run_round_trips_schwab_api_call_id_none_when_omitted(
    conn: sqlite3.Connection,
) -> None:
    """Codex R1 Major #5: insert_run with schwab_api_call_id omitted
    persists NULL + round-trips as None.
    """
    rid = repo.insert_run(
        conn,
        source="tos_csv",
        started_ts="2026-05-13T12:00:00",
    )
    r = repo.get_run(conn, rid)
    assert r is not None
    assert r.schwab_api_call_id is None


def test_insert_run_schwab_api_call_id_fk_set_null_on_delete(
    conn: sqlite3.Connection,
) -> None:
    """Codex R1 Major #5: FK ON DELETE SET NULL per migration 0018.
    When the parent schwab_api_calls row is deleted, the reconciliation
    run's schwab_api_call_id flips to NULL (not the run row itself).
    """
    # Seed parent rows.
    cur = conn.execute(
        "INSERT INTO pipeline_runs ("
        "started_ts, trigger, data_asof_date, action_session_date, "
        "state, lease_token"
        ") VALUES (?, ?, ?, ?, ?, ?)",
        ("2026-05-13T08:00:00", "manual", "2026-05-12", "2026-05-13",
         "running", "test-token"),
    )
    pipeline_run_id = int(cur.lastrowid)
    cur = conn.execute(
        "INSERT INTO schwab_api_calls ("
        "ts, endpoint, status, pipeline_run_id, surface, environment"
        ") VALUES (?, ?, ?, ?, ?, ?)",
        ("2026-05-13T12:00:00", "accounts.transactions.list", "success",
         pipeline_run_id, "pipeline", "sandbox"),
    )
    call_id = int(cur.lastrowid)

    rid = repo.insert_run(
        conn,
        source="schwab_api",
        started_ts="2026-05-13T12:00:00",
        schwab_api_call_id=call_id,
    )
    # Delete the parent schwab_api_calls row.
    conn.execute("DELETE FROM schwab_api_calls WHERE call_id = ?", (call_id,))
    # Reconciliation run still exists; schwab_api_call_id is now NULL.
    r = repo.get_run(conn, rid)
    assert r is not None, "reconciliation run MUST survive parent delete"
    assert r.schwab_api_call_id is None, (
        "FK ON DELETE SET NULL should have nulled the link"
    )


# ===========================================================================
# §2 — ReconciliationDiscrepancy dataclass validator
# ===========================================================================


def _make_discrepancy(**overrides) -> ReconciliationDiscrepancy:
    base = dict(
        discrepancy_id=None,
        run_id=1,
        discrepancy_type="close_price_mismatch",
        trade_id=None,
        fill_id=None,
        cash_movement_id=None,
        linked_daily_management_record_id=None,
        ticker="ABC",
        field_name="price",
        expected_value_json='{"price": 10.0}',
        actual_value_json='{"price": 10.5}',
        delta_text="$0.50 price difference",
        material_to_review=1,
        resolution="unresolved",
        resolution_reason=None,
        resolved_at=None,
        resolved_by=None,
        mistake_tag_assigned=None,
        created_at="2026-05-12T08:00:00.000",
    )
    base.update(overrides)
    return ReconciliationDiscrepancy(**base)


def test_discrepancy_accepts_minimal_unresolved() -> None:
    d = _make_discrepancy()
    assert d.resolution == "unresolved"


def test_discrepancy_rejects_invalid_type() -> None:
    with pytest.raises(ValueError, match="discrepancy_type must be one of"):
        _make_discrepancy(discrepancy_type="price_drift")


def test_discrepancy_rejects_invalid_resolution() -> None:
    with pytest.raises(ValueError, match="resolution must be one of"):
        _make_discrepancy(resolution="pending")


def test_discrepancy_rejects_invalid_material_to_review() -> None:
    with pytest.raises(ValueError, match="material_to_review must be 0 or 1"):
        _make_discrepancy(material_to_review=2)


def test_discrepancy_rejects_empty_field_name() -> None:
    with pytest.raises(ValueError, match="field_name"):
        _make_discrepancy(field_name="")


def test_discrepancy_rejects_invalid_json_expected() -> None:
    with pytest.raises(ValueError, match="expected_value_json must be valid JSON"):
        _make_discrepancy(expected_value_json="not-json{")


def test_discrepancy_rejects_invalid_json_actual() -> None:
    with pytest.raises(ValueError, match="actual_value_json must be valid JSON"):
        _make_discrepancy(actual_value_json="{not json")


def test_discrepancy_accepts_json_null_payloads() -> None:
    d = _make_discrepancy(expected_value_json=None, actual_value_json=None)
    assert d.expected_value_json is None


def test_discrepancy_unresolved_with_asymmetric_resolved_fields_rejected() -> None:
    with pytest.raises(ValueError, match="both be NULL or both set"):
        _make_discrepancy(
            resolution="unresolved",
            resolved_at="2026-05-12T08:00:00.000",
            resolved_by=None,
        )


def test_discrepancy_resolved_requires_resolved_at() -> None:
    with pytest.raises(ValueError, match="requires resolved_at"):
        _make_discrepancy(
            resolution="journal_corrected",
            resolution_reason="fixed via swing trade fix-fill",
            resolved_at=None,
            resolved_by="operator",
        )


def test_discrepancy_resolved_requires_resolved_by() -> None:
    with pytest.raises(ValueError, match="requires resolved_by"):
        _make_discrepancy(
            resolution="journal_corrected",
            resolution_reason="fixed via swing trade fix-fill",
            resolved_at="2026-05-12T08:00:00.000",
            resolved_by=None,
        )


def test_discrepancy_journal_corrected_requires_reason() -> None:
    with pytest.raises(ValueError, match="requires non-empty resolution_reason"):
        _make_discrepancy(
            resolution="journal_corrected",
            resolution_reason=None,
            resolved_at="2026-05-12T08:00:00.000",
            resolved_by="operator",
        )


def test_discrepancy_acknowledged_immaterial_allows_null_reason() -> None:
    d = _make_discrepancy(
        resolution="acknowledged_immaterial",
        resolution_reason=None,
        resolved_at="2026-05-12T08:00:00.000",
        resolved_by="operator",
    )
    assert d.resolution == "acknowledged_immaterial"


# ===========================================================================
# §3 — repo insert_run / get_run / update_run_completed / update_run_failed
# ===========================================================================


def test_insert_run_returns_run_id(conn: sqlite3.Connection) -> None:
    rid = _insert_run(conn)
    assert isinstance(rid, int) and rid > 0


def test_get_run_returns_dataclass(conn: sqlite3.Connection) -> None:
    sha = "a" * 64
    rid = _insert_run(conn, source_artifact_sha256=sha, notes="op test")
    r = repo.get_run(conn, rid)
    assert r is not None
    assert r.run_id == rid
    assert r.source == "tos_csv"
    assert r.state == "running"
    assert r.source_artifact_sha256 == sha
    assert r.notes == "op test"


def test_get_run_returns_none_for_unknown_id(conn: sqlite3.Connection) -> None:
    assert repo.get_run(conn, 9999) is None


def test_update_run_completed_transitions_state(conn: sqlite3.Connection) -> None:
    rid = _insert_run(conn, started_ts="2026-05-12T08:00:00.000")
    repo.update_run_completed(
        conn,
        run_id=rid,
        finished_ts="2026-05-12T09:00:00.000",
        trades_reconciled_count=4,
        fills_reconciled_count=12,
        discrepancies_count=2,
        unresolved_discrepancies_count=2,
        summary_json='{"unmatched_open": 0}',
    )
    r = repo.get_run(conn, rid)
    assert r is not None
    assert r.state == "completed"
    assert r.finished_ts == "2026-05-12T09:00:00.000"
    assert r.trades_reconciled_count == 4
    assert r.summary_json == '{"unmatched_open": 0}'


def test_update_run_failed_preserves_row_per_spec_3_3_3(
    conn: sqlite3.Connection,
) -> None:
    """Per spec §3.3.3 + plan §A.2.1: failure-path UPDATEs state='failed'
    on the EXISTING row (NOT a rollback-new-row). The discriminating
    distinction vs the pre-fix design is that the run row is PRESERVED
    after failure.
    """
    rid = _insert_run(conn, started_ts="2026-05-12T08:00:00.000")
    repo.update_run_failed(
        conn,
        run_id=rid,
        finished_ts="2026-05-12T09:00:00.000",
        error_message="parse error at row 17",
    )
    r = repo.get_run(conn, rid)
    assert r is not None
    assert r.state == "failed"
    assert r.error_message == "parse error at row 17"


def test_repo_does_not_call_conn_commit() -> None:
    """Caller-controlled transaction discipline per Finviz I1 lesson.

    AST guard: repo source MUST NOT contain a call expression
    ``conn.commit()`` — the service layer owns the transaction
    (BEGIN IMMEDIATE → ... → COMMIT). Docstring mentions of the
    forbidden pattern (like this test's own docstring) are allowed.
    """
    import ast

    from swing.data.repos import reconciliation as r
    src = open(r.__file__, encoding="utf-8").read()
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Call)
            and isinstance(node.func, ast.Attribute)
            and node.func.attr == "commit"
            and isinstance(node.func.value, ast.Name)
            and node.func.value.id == "conn"
        ):
            pytest.fail(
                f"swing/data/repos/reconciliation.py contains conn.commit() "
                f"at line {node.lineno}; repo must NOT commit "
                "(Finviz I1 lesson + caller-controlled transaction discipline)"
            )


# ===========================================================================
# §4 — two-read pattern: most_recent_completed_run vs most_recent_started_run
# ===========================================================================


def test_most_recent_completed_unaffected_by_in_flight_run(
    conn: sqlite3.Connection,
) -> None:
    """CLAUDE.md gotcha: ``started_ts DESC`` ORDER BY masks prior completes
    mid-run. Two-read pattern avoids the mask: most-recent-completed reads
    only ``state='completed'``; most-recent-started reads any state.
    """
    # Older completed run
    rid1 = _insert_run(
        conn, started_ts="2026-05-10T08:00:00.000",
    )
    repo.update_run_completed(
        conn, run_id=rid1, finished_ts="2026-05-10T08:30:00.000",
    )
    # Newer in-flight run (state='running')
    _insert_run(conn, started_ts="2026-05-12T08:00:00.000")

    last_completed = repo.most_recent_completed_run(conn)
    last_started = repo.most_recent_started_run(conn)
    assert last_completed is not None
    assert last_completed.run_id == rid1  # NOT masked by in-flight run
    assert last_completed.state == "completed"
    assert last_started is not None
    assert last_started.started_ts == "2026-05-12T08:00:00.000"
    assert last_started.state == "running"


def test_most_recent_completed_returns_none_when_no_completed(
    conn: sqlite3.Connection,
) -> None:
    _insert_run(conn)  # state='running'
    assert repo.most_recent_completed_run(conn) is None


def test_most_recent_started_returns_none_when_no_runs(
    conn: sqlite3.Connection,
) -> None:
    assert repo.most_recent_started_run(conn) is None


def test_list_recent_runs_orders_by_started_desc(
    conn: sqlite3.Connection,
) -> None:
    rid1 = _insert_run(conn, started_ts="2026-05-10T08:00:00.000")
    rid2 = _insert_run(conn, started_ts="2026-05-12T08:00:00.000")
    runs = repo.list_recent_runs(conn, limit=10)
    assert [r.run_id for r in runs] == [rid2, rid1]


# ===========================================================================
# §5 — count_runs_for_artifact_sha256 advisory
# ===========================================================================


def test_count_runs_for_artifact_sha256_zero_for_unknown(
    conn: sqlite3.Connection,
) -> None:
    assert repo.count_runs_for_artifact_sha256(conn, "deadbeef" * 8) == 0


def test_count_runs_for_artifact_sha256_increments(
    conn: sqlite3.Connection,
) -> None:
    sha = "1" + "0" * 63
    _insert_run(conn, source_artifact_sha256=sha)
    _insert_run(conn, source_artifact_sha256=sha)
    _insert_run(conn, source_artifact_sha256="2" + "0" * 63)
    assert repo.count_runs_for_artifact_sha256(conn, sha) == 2


# ===========================================================================
# §6 — discrepancy insert / get / list / update_resolution
# ===========================================================================


def test_insert_discrepancy_returns_id_and_row(conn: sqlite3.Connection) -> None:
    rid = _insert_run(conn)
    did = _insert_discrepancy(
        conn,
        run_id=rid,
        ticker="ABC",
        expected_value_json='{"price": 10.0}',
        actual_value_json='{"price": 10.5}',
    )
    d = repo.get_discrepancy(conn, did)
    assert d is not None
    assert d.run_id == rid
    assert d.discrepancy_type == "close_price_mismatch"
    assert d.material_to_review == 1
    assert d.resolution == "unresolved"


def test_get_discrepancy_returns_none_for_unknown(
    conn: sqlite3.Connection,
) -> None:
    assert repo.get_discrepancy(conn, 99999) is None


def test_list_discrepancies_for_run_returns_in_pk_order(
    conn: sqlite3.Connection,
) -> None:
    rid = _insert_run(conn)
    d1 = _insert_discrepancy(conn, run_id=rid, ticker="ABC")
    d2 = _insert_discrepancy(conn, run_id=rid, ticker="DEF")
    ds = repo.list_discrepancies_for_run(conn, rid)
    assert [d.discrepancy_id for d in ds] == [d1, d2]


def test_update_discrepancy_resolution_sets_audit_fields(
    conn: sqlite3.Connection,
) -> None:
    rid = _insert_run(conn)
    did = _insert_discrepancy(conn, run_id=rid)
    repo.update_discrepancy_resolution(
        conn,
        discrepancy_id=did,
        resolution="journal_corrected",
        resolution_reason="fixed via swing trade fix-fill",
        resolved_by="operator",
        resolved_at="2026-05-12T09:00:00.000",
    )
    d = repo.get_discrepancy(conn, did)
    assert d is not None
    assert d.resolution == "journal_corrected"
    assert d.resolution_reason == "fixed via swing trade fix-fill"
    assert d.resolved_by == "operator"
    assert d.resolved_at == "2026-05-12T09:00:00.000"


def test_update_discrepancy_material_flips_flag(
    conn: sqlite3.Connection,
) -> None:
    rid = _insert_run(conn)
    did = _insert_discrepancy(
        conn, run_id=rid, material_to_review=0,
    )
    repo.update_discrepancy_material(
        conn, discrepancy_id=did, material_to_review=1,
    )
    d = repo.get_discrepancy(conn, did)
    assert d is not None
    assert d.material_to_review == 1


def test_update_discrepancy_material_rejects_invalid(
    conn: sqlite3.Connection,
) -> None:
    rid = _insert_run(conn)
    did = _insert_discrepancy(conn, run_id=rid)
    with pytest.raises(ValueError, match="material_to_review"):
        repo.update_discrepancy_material(
            conn, discrepancy_id=did, material_to_review=2,
        )


# ===========================================================================
# §7 — Canonical queries (spec §5.1)
# ===========================================================================


def test_list_unresolved_material_for_active_trades_excludes_closed(
    conn: sqlite3.Connection,
) -> None:
    """Spec §5.1 CANONICAL #1: only ('entered','managing','partial_exited')."""
    tid_active = _insert_trade(conn, ticker="ACT", state="managing")
    tid_closed = _insert_trade(
        conn, ticker="CLS", state="closed", entry_date="2026-05-01",
    )
    rid = _insert_run(conn)
    did_active = _insert_discrepancy(
        conn, run_id=rid, trade_id=tid_active, ticker="ACT",
    )
    _insert_discrepancy(
        conn, run_id=rid, trade_id=tid_closed, ticker="CLS",
    )
    rows = repo.list_unresolved_material_for_active_trades(conn)
    ids = {r.discrepancy_id for r in rows}
    assert did_active in ids
    closed_ids = {r.discrepancy_id for r in rows
                  if r.trade_id == tid_closed}
    assert not closed_ids


def test_list_unresolved_material_for_active_trades_excludes_resolved(
    conn: sqlite3.Connection,
) -> None:
    tid = _insert_trade(conn, state="entered")
    rid = _insert_run(conn)
    did = _insert_discrepancy(conn, run_id=rid, trade_id=tid)
    repo.update_discrepancy_resolution(
        conn,
        discrepancy_id=did,
        resolution="journal_corrected",
        resolution_reason="fixed",
        resolved_by="operator",
        resolved_at=now_ms(),
    )
    rows = repo.list_unresolved_material_for_active_trades(conn)
    assert all(r.discrepancy_id != did for r in rows)


def test_list_unresolved_material_for_active_trades_excludes_immaterial(
    conn: sqlite3.Connection,
) -> None:
    tid = _insert_trade(conn, state="managing")
    rid = _insert_run(conn)
    did = _insert_discrepancy(
        conn,
        run_id=rid,
        trade_id=tid,
        material_to_review=0,
        discrepancy_type="cash_movement_mismatch",
    )
    rows = repo.list_unresolved_material_for_active_trades(conn)
    assert all(r.discrepancy_id != did for r in rows)


def test_list_unresolved_material_for_active_trades_excludes_orphan_trade_id(
    conn: sqlite3.Connection,
) -> None:
    """Discrepancies with trade_id IS NULL never appear (CANONICAL #1 JOINs trades)."""
    rid = _insert_run(conn)
    _insert_discrepancy(
        conn,
        run_id=rid,
        trade_id=None,
        ticker="ORPHAN",
        discrepancy_type="unmatched_open_fill",
    )
    rows = repo.list_unresolved_material_for_active_trades(conn)
    assert rows == []


def test_list_unresolved_material_for_closed_trades_only_closed_reviewed(
    conn: sqlite3.Connection,
) -> None:
    """Spec §5.1 CANONICAL #2: only ('closed','reviewed')."""
    tid_closed = _insert_trade(
        conn, ticker="CL1", state="closed", entry_date="2026-05-01",
    )
    tid_reviewed = _insert_trade(
        conn, ticker="REV", state="reviewed", entry_date="2026-05-02",
    )
    tid_active = _insert_trade(
        conn, ticker="ACT2", state="managing", entry_date="2026-05-03",
    )
    rid = _insert_run(conn)
    d_closed = _insert_discrepancy(conn, run_id=rid, trade_id=tid_closed)
    d_reviewed = _insert_discrepancy(conn, run_id=rid, trade_id=tid_reviewed)
    _insert_discrepancy(conn, run_id=rid, trade_id=tid_active)
    rows = repo.list_unresolved_material_for_closed_trades(conn)
    ids = {r.discrepancy_id for r in rows}
    assert d_closed in ids
    assert d_reviewed in ids
    active_ids = {r.discrepancy_id for r in rows
                  if r.trade_id == tid_active}
    assert not active_ids


def test_list_unresolved_material_for_closed_trades_orders_by_created_desc(
    conn: sqlite3.Connection,
) -> None:
    tid = _insert_trade(conn, state="closed")
    rid = _insert_run(conn)
    d1 = _insert_discrepancy(conn, run_id=rid, trade_id=tid)
    d2 = _insert_discrepancy(conn, run_id=rid, trade_id=tid)
    rows = repo.list_unresolved_material_for_closed_trades(conn)
    # PK monotonicity tiebreaks identical created_at; newest PK first.
    assert [r.discrepancy_id for r in rows] == [d2, d1]
