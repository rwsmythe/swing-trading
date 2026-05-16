"""Phase 9 Task B.6 — reconciliation service tests.

Per plan §E T-B.6 + spec §3.3.3 + plan §A.2 acceptance criteria:
- ``run_tos_reconciliation`` rejects caller-held transaction.
- Happy path: INSERTs run row with state='running' then transitions to
  'completed' with summary fields; discrepancies emitted via the seam.
- Failure path: exception during reconcile_tos UPDATEs state='failed'
  on the EXISTING row (NOT a rollback-new-row); discrepancies emitted
  prior to the failure are PRESERVED alongside the failed-state UPDATE
  in the same commit. ``conn.in_transaction == False`` post-call.
- Within-run dedup via in-memory tuple set.
- ``MATERIAL_BY_TYPE`` lookup correctness — emitter writes the default
  material classification from the lookup when caller doesn't override.
- ``source_artifact_sha256`` computed at run-start.
- ``resolve_discrepancy`` updates lifecycle fields + decrements parent
  run's unresolved counter.
"""
from __future__ import annotations

import json
import sqlite3
import sys
from pathlib import Path

import pytest

from swing.data.datetime_helpers import now_ms
from swing.data.db import ensure_schema
from swing.data.models import Fill, Trade
from swing.data.repos import reconciliation as recon_repo
from swing.data.repos.fills import insert_fill_with_event
from swing.data.repos.trades import insert_trade_with_event
from swing.trades.reconciliation import (
    CallerHeldTransactionError,
    DISCREPANCY_TYPES,
    MATERIAL_BY_TYPE,
    RESOLUTION_TYPES,
    resolve_discrepancy,
    run_tos_reconciliation,
)


@pytest.fixture
def db_path(tmp_path: Path) -> Path:
    db = tmp_path / "swing.db"
    ensure_schema(db).close()
    return db


@pytest.fixture
def conn(db_path: Path):
    c = sqlite3.connect(db_path)
    c.execute("PRAGMA foreign_keys = ON")
    try:
        yield c
    finally:
        c.close()


def _seed_entry(
    conn: sqlite3.Connection,
    *,
    ticker: str,
    entry_date: str,
    entry_price: float,
    shares: int,
    initial_stop: float,
) -> int:
    event_ts = f"{entry_date}T09:30:00"
    trade = Trade(
        id=None, ticker=ticker, entry_date=entry_date,
        entry_price=entry_price, initial_shares=shares,
        initial_stop=initial_stop, current_stop=initial_stop,
        state="entered",
        watchlist_entry_target=None, watchlist_initial_stop=None, notes=None,
        trade_origin="manual_off_pipeline", pre_trade_locked_at=event_ts,
    )
    with conn:
        tid = insert_trade_with_event(
            conn, trade, event_ts=event_ts, rationale="seed",
        )
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=tid, fill_datetime=event_ts,
                action="entry", quantity=float(shares), price=entry_price,
            ),
            event_ts=event_ts,
        )
    return tid


_SIMPLE_TOS_CSV = """\
Account Trade History
Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,Price,Net Price,Order Type
2026-05-12 10:00:00,STOCK,BUY,+10,OPENING,ABC,,,,10.0500,10.0500,MKT
"""


# ===========================================================================
# §1 — Constants are well-formed (spec §3.3 + §3.3.1).
# ===========================================================================


def test_discrepancy_types_match_check_enum() -> None:
    assert "close_price_mismatch" in DISCREPANCY_TYPES
    assert "cash_movement_mismatch" in DISCREPANCY_TYPES
    assert "sector_tamper" in DISCREPANCY_TYPES
    assert len(DISCREPANCY_TYPES) == 10


def test_resolution_types_match_check_enum() -> None:
    assert "unresolved" in RESOLUTION_TYPES
    assert "journal_corrected" in RESOLUTION_TYPES
    assert "acknowledged_immaterial" in RESOLUTION_TYPES
    assert len(RESOLUTION_TYPES) == 5


def test_material_by_type_covers_all_discrepancy_types() -> None:
    """Spec §3.3.1 default material classification per type."""
    for t in DISCREPANCY_TYPES:
        assert t in MATERIAL_BY_TYPE, f"missing material default for {t}"
    # Spec §3.3.1: cash_movement_mismatch + sector_tamper + snapshot_mismatch
    # + equity_delta default to 0 (FALSE).
    assert MATERIAL_BY_TYPE["cash_movement_mismatch"] == 0
    assert MATERIAL_BY_TYPE["sector_tamper"] == 0
    assert MATERIAL_BY_TYPE["snapshot_mismatch"] == 0
    assert MATERIAL_BY_TYPE["equity_delta"] == 0
    # Others default to 1 (TRUE).
    assert MATERIAL_BY_TYPE["close_price_mismatch"] == 1
    assert MATERIAL_BY_TYPE["entry_price_mismatch"] == 1
    assert MATERIAL_BY_TYPE["stop_mismatch"] == 1
    assert MATERIAL_BY_TYPE["position_qty_mismatch"] == 1
    assert MATERIAL_BY_TYPE["unmatched_open_fill"] == 1
    assert MATERIAL_BY_TYPE["unmatched_close_fill"] == 1


# ===========================================================================
# §2 — Caller-held-transaction rejection (spec + Phase 8 R3→R4 lesson).
# ===========================================================================


def test_run_tos_reconciliation_rejects_caller_held_transaction(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    csv = tmp_path / "tos.csv"
    csv.write_text(_SIMPLE_TOS_CSV, encoding="utf-8")
    conn.execute("BEGIN")
    try:
        with pytest.raises(CallerHeldTransactionError):
            run_tos_reconciliation(conn, csv_path=csv)
    finally:
        conn.rollback()


def test_resolve_discrepancy_rejects_caller_held_transaction(
    conn: sqlite3.Connection,
) -> None:
    conn.execute("BEGIN")
    try:
        with pytest.raises(CallerHeldTransactionError):
            resolve_discrepancy(
                conn, discrepancy_id=1, resolution="journal_corrected",
                resolution_reason="x",
            )
    finally:
        conn.rollback()


# ===========================================================================
# §3 — Happy path: state='running' → 'completed' with summary.
# ===========================================================================


def test_run_tos_reconciliation_happy_path_completes(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    # Seed an open trade so the open-fill TOS row matches.
    _seed_entry(
        conn, ticker="ABC", entry_date="2026-05-12",
        entry_price=10.05, shares=10, initial_stop=9.00,
    )
    csv = tmp_path / "tos.csv"
    csv.write_text(_SIMPLE_TOS_CSV, encoding="utf-8")
    out = run_tos_reconciliation(
        conn,
        csv_path=csv,
        period_end="2026-05-12",
        notes="happy-path test",
    )
    assert out.state == "completed"
    assert out.source == "tos_csv"
    assert out.source_artifact_path == str(csv)
    assert out.source_artifact_sha256 is not None
    assert len(out.source_artifact_sha256) == 64
    assert out.notes == "happy-path test"
    assert out.period_end == "2026-05-12"
    assert out.finished_ts is not None
    assert out.summary_json is not None
    summary = json.loads(out.summary_json)
    assert "matched_fills" in summary
    # Caller's conn should be back to autocommit-mode (no open tx).
    assert not conn.in_transaction


def test_run_tos_reconciliation_emits_discrepancies_inside_transaction(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Open-trade-without-broker-stop fires stop_mismatch which the
    service persists via the emitter. Verifies the seam is wired all
    the way through (T-B.2 seam + T-B.4 detection + T-B.6 service).
    """
    _seed_entry(
        conn, ticker="ABC", entry_date="2026-05-12",
        entry_price=10.05, shares=10, initial_stop=9.00,
    )
    csv = tmp_path / "tos.csv"
    csv.write_text(_SIMPLE_TOS_CSV, encoding="utf-8")
    out = run_tos_reconciliation(conn, csv_path=csv)
    ds = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    types = {d.discrepancy_type for d in ds}
    assert "stop_mismatch" in types
    # discrepancies_count + unresolved counters populated.
    assert out.discrepancies_count >= 1
    assert out.unresolved_discrepancies_count == out.discrepancies_count


# ===========================================================================
# §4 — Failure path PRESERVES the run row per spec §3.3.3 + plan §A.2.1.
# ===========================================================================


def test_run_tos_reconciliation_failure_preserves_row(
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch,
) -> None:
    """Inject a synthetic exception AFTER reconcile_tos has emitted at
    least one discrepancy. Assert (a) the run row exists with
    state='failed', (b) error_message populated, (c) discrepancies
    emitted prior to failure ARE preserved, (d) conn.in_transaction
    is False post-call.

    This is the discriminating distinction vs the pre-fix design
    (which would have rolled back the whole transaction including
    the run row + all emitted discrepancies).
    """
    _seed_entry(
        conn, ticker="ABC", entry_date="2026-05-12",
        entry_price=10.05, shares=10, initial_stop=9.00,
    )
    csv = tmp_path / "tos.csv"
    csv.write_text(_SIMPLE_TOS_CSV, encoding="utf-8")

    # Monkeypatch reconcile_tos to emit one discrepancy then raise.
    import swing.trades.reconciliation as svc

    original_recon = svc.reconcile_tos

    def _faulty_reconcile(*, conn, tos_text, price_tolerance, run_id, emitter):
        emitter(
            discrepancy_type="stop_mismatch",
            run_id=run_id,
            trade_id=None,
            ticker="ABC",
            field_name="current_stop",
            expected_value_json='{"current_stop": 9.0}',
            actual_value_json='{"working_stop_price": null, "order_id": null}',
            delta_text="injected pre-failure",
            material_to_review=1,
        )
        raise RuntimeError("synthetic parse-error at row 17")

    monkeypatch.setattr(svc, "reconcile_tos", _faulty_reconcile)

    with pytest.raises(RuntimeError, match="synthetic parse-error"):
        run_tos_reconciliation(conn, csv_path=csv)

    # (a) row PRESENT with state='failed'.
    runs = recon_repo.list_recent_runs(conn, limit=10)
    assert len(runs) == 1
    r = runs[0]
    assert r.state == "failed"
    # (b) error_message populated.
    assert r.error_message is not None
    assert "synthetic parse-error" in r.error_message
    # (c) discrepancy emitted PRIOR to failure is preserved.
    ds = recon_repo.list_discrepancies_for_run(conn, r.run_id)
    assert len(ds) == 1
    assert ds[0].discrepancy_type == "stop_mismatch"
    assert ds[0].delta_text == "injected pre-failure"
    # (d) conn no longer in transaction.
    assert not conn.in_transaction


# ===========================================================================
# §5 — Within-run dedup (spec §5.1 R3 Major #4).
# ===========================================================================


def test_run_tos_reconciliation_within_run_dedup(
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch,
) -> None:
    """Two identical emitter calls in one run produce ONE discrepancy row."""
    csv = tmp_path / "tos.csv"
    csv.write_text(_SIMPLE_TOS_CSV, encoding="utf-8")

    import swing.trades.reconciliation as svc

    def _dup_recon(*, conn, tos_text, price_tolerance, run_id, emitter):
        for _ in range(2):
            emitter(
                discrepancy_type="stop_mismatch",
                run_id=run_id,
                trade_id=None,  # orphan (no FK target needed)
                ticker="ABC",
                fill_id=None,
                cash_movement_id=None,
                field_name="current_stop",
                expected_value_json='{"current_stop": 9.0}',
                actual_value_json='{"working_stop_price": null, "order_id": null}',
                delta_text="dup",
                material_to_review=1,
            )
        from swing.journal.tos_import import ReconciliationReport
        return ReconciliationReport()

    monkeypatch.setattr(svc, "reconcile_tos", _dup_recon)
    out = run_tos_reconciliation(conn, csv_path=csv)
    ds = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    assert len(ds) == 1  # dedup'd
    assert out.discrepancies_count == 1


# ===========================================================================
# §6 — Source-artifact SHA256 + count_runs_for_artifact_sha256 advisory.
# ===========================================================================


def test_run_tos_reconciliation_sha256_is_content_hash(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    import hashlib

    csv = tmp_path / "tos.csv"
    payload = _SIMPLE_TOS_CSV.encode("utf-8")
    csv.write_bytes(payload)
    out = run_tos_reconciliation(conn, csv_path=csv)
    assert out.source_artifact_sha256 == hashlib.sha256(payload).hexdigest()


def test_count_runs_for_artifact_sha256_increments_across_reruns(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    csv = tmp_path / "tos.csv"
    csv.write_text(_SIMPLE_TOS_CSV, encoding="utf-8")
    out1 = run_tos_reconciliation(conn, csv_path=csv)
    out2 = run_tos_reconciliation(conn, csv_path=csv)
    assert out1.source_artifact_sha256 == out2.source_artifact_sha256
    n = recon_repo.count_runs_for_artifact_sha256(
        conn, out1.source_artifact_sha256,
    )
    assert n == 2


def test_empty_csv_does_not_crash(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Empty file edge case: SHA256 of '' is e3b0c442...; run completes."""
    csv = tmp_path / "tos.csv"
    csv.write_bytes(b"")
    out = run_tos_reconciliation(conn, csv_path=csv)
    assert out.state == "completed"
    assert out.source_artifact_sha256 == (
        "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
    )


# ===========================================================================
# §7 — resolve_discrepancy lifecycle.
# ===========================================================================


def test_resolve_discrepancy_updates_lifecycle(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    _seed_entry(
        conn, ticker="ABC", entry_date="2026-05-12",
        entry_price=10.05, shares=10, initial_stop=9.00,
    )
    csv = tmp_path / "tos.csv"
    csv.write_text(_SIMPLE_TOS_CSV, encoding="utf-8")
    # Phase 12 C.C T-C.6: bypass the auto-correct pivot so this legacy
    # test exercises ``resolve_discrepancy`` against the pre-pivot
    # ``resolution='unresolved'`` state. The pivot is exercised end-to-end
    # in tests/trades/test_run_tos_reconciliation_pivot.py.
    out = run_tos_reconciliation(conn, csv_path=csv, environment="sandbox")
    ds = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    assert len(ds) >= 1
    target = ds[0]
    assert target.resolution == "unresolved"

    resolve_discrepancy(
        conn,
        discrepancy_id=target.discrepancy_id,
        resolution="journal_corrected",
        resolution_reason="fixed via journal update",
    )

    reloaded = recon_repo.get_discrepancy(conn, target.discrepancy_id)
    assert reloaded.resolution == "journal_corrected"
    assert reloaded.resolution_reason == "fixed via journal update"
    assert reloaded.resolved_at is not None
    assert reloaded.resolved_by == "operator"

    # Parent run's unresolved counter decremented.
    r = recon_repo.get_run(conn, out.run_id)
    assert r.unresolved_discrepancies_count == out.discrepancies_count - 1


def test_resolve_discrepancy_rejects_invalid_resolution(
    conn: sqlite3.Connection,
) -> None:
    with pytest.raises(ValueError, match="resolution must be one of"):
        resolve_discrepancy(
            conn, discrepancy_id=1, resolution="pending",
            resolution_reason="x",
        )


def test_resolve_discrepancy_requires_reason_for_journal_corrected(
    conn: sqlite3.Connection,
) -> None:
    with pytest.raises(ValueError, match="requires non-empty resolution_reason"):
        resolve_discrepancy(
            conn, discrepancy_id=1, resolution="journal_corrected",
        )


def test_resolve_discrepancy_acknowledged_immaterial_allows_null_reason(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    _seed_entry(
        conn, ticker="ABC", entry_date="2026-05-12",
        entry_price=10.05, shares=10, initial_stop=9.00,
    )
    csv = tmp_path / "tos.csv"
    csv.write_text(_SIMPLE_TOS_CSV, encoding="utf-8")
    # Phase 12 C.C T-C.6: bypass the auto-correct pivot so the test's
    # ``acknowledged_immaterial`` resolution transition is valid (the
    # pivot otherwise leaves the row in ``pending_ambiguity_resolution``,
    # whose schema cross-CHECK invariant forbids transitioning directly
    # to ``acknowledged_immaterial`` while ambiguity_kind IS NOT NULL).
    out = run_tos_reconciliation(conn, csv_path=csv, environment="sandbox")
    ds = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    target = ds[0]
    # Should not raise.
    resolve_discrepancy(
        conn,
        discrepancy_id=target.discrepancy_id,
        resolution="acknowledged_immaterial",
        resolution_reason=None,
    )
    reloaded = recon_repo.get_discrepancy(conn, target.discrepancy_id)
    assert reloaded.resolution == "acknowledged_immaterial"


def test_resolve_discrepancy_unknown_id_raises(
    conn: sqlite3.Connection,
) -> None:
    with pytest.raises(ValueError, match="not found"):
        resolve_discrepancy(
            conn, discrepancy_id=99999, resolution="journal_corrected",
            resolution_reason="x",
        )


# ===========================================================================
# §8 — cash_movement_mismatch end-to-end (T-B.6 + tos_import detection).
# ===========================================================================


_CASH_DUP_TOS_CSV = """\
Cash Balance
DATE,TIME,TYPE,REF #,DESCRIPTION,MISC FEES,COMMISSIONS & FEES,AMOUNT,BALANCE
2026-05-12,10:00:00,DEP,="REF-001",ACH deposit,,,500.00,5500.00
"""


def _insert_journal_cash(conn: sqlite3.Connection, *, ref: str,
                         kind: str, amount: float) -> None:
    from swing.data.models import CashMovement
    from swing.data.repos.cash import insert_cash
    insert_cash(
        conn,
        CashMovement(
            id=None, date="2026-05-12", kind=kind, amount=amount,
            ref=ref, note="journal entry",
        ),
    )


def test_cash_movement_mismatch_amount_delta_emits(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    # Journal: REF-001 deposit $400.
    with conn:
        _insert_journal_cash(conn, ref="REF-001", kind="deposit", amount=400.00)
    csv = tmp_path / "tos.csv"
    csv.write_text(_CASH_DUP_TOS_CSV, encoding="utf-8")
    out = run_tos_reconciliation(conn, csv_path=csv)
    ds = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    cmms = [d for d in ds if d.discrepancy_type == "cash_movement_mismatch"]
    assert len(cmms) == 1
    d = cmms[0]
    assert d.material_to_review == 0  # spec §3.3.1
    assert d.field_name == "amount"
    expected = json.loads(d.expected_value_json)
    actual = json.loads(d.actual_value_json)
    assert expected == {"amount": 400.00, "kind": "deposit", "ref": "REF-001"}
    assert actual == {"amount": 500.00, "kind": "deposit", "ref": "REF-001"}
    assert d.cash_movement_id is not None


def test_cash_movement_mismatch_no_emit_when_amounts_match(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    with conn:
        _insert_journal_cash(conn, ref="REF-001", kind="deposit", amount=500.00)
    csv = tmp_path / "tos.csv"
    csv.write_text(_CASH_DUP_TOS_CSV, encoding="utf-8")
    out = run_tos_reconciliation(conn, csv_path=csv)
    ds = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    cmms = [d for d in ds if d.discrepancy_type == "cash_movement_mismatch"]
    assert cmms == []


# ===========================================================================
# §9 — Codex R1 fixes: spec §6.5 unmatched fill emits + MATERIAL_BY_TYPE
#       authoritative + NaN-JSON rejection + absolute source_artifact_path.
# ===========================================================================


_UNMATCHED_OPEN_FILL_CSV = """\
Account Trade History
Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,Price,Net Price,Order Type
2026-05-12 10:00:00,STOCK,BUY,+5,OPENING,GHOST,,,,42.0000,42.0000,MKT
"""


_UNMATCHED_CLOSE_FILL_CSV = """\
Account Trade History
Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,Price,Net Price,Order Type
2026-05-12 15:30:00,STOCK,SELL,-5,CLOSING,ZOMBIE,,,,99.0000,99.0000,MKT
"""


def test_unmatched_open_fill_emits_per_spec_6_5(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Codex R1 M#1 — spec §6.5 + §3.3.1 binding for unmatched_open_fill."""
    csv = tmp_path / "tos.csv"
    csv.write_text(_UNMATCHED_OPEN_FILL_CSV, encoding="utf-8")
    out = run_tos_reconciliation(conn, csv_path=csv)
    ds = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    uof = [d for d in ds if d.discrepancy_type == "unmatched_open_fill"]
    assert len(uof) == 1
    e = uof[0]
    assert e.trade_id is None
    assert e.ticker == "GHOST"
    # spec §3.3.1: expected={}, actual={"price", "qty", "ticker", "fill_date"}
    import json as _json
    actual = _json.loads(e.actual_value_json)
    assert actual["ticker"] == "GHOST"
    assert actual["qty"] == 5
    assert actual["price"] == 42.0
    assert e.material_to_review == 1  # MATERIAL_BY_TYPE["unmatched_open_fill"]


def test_unmatched_close_fill_emits_per_spec_6_5(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Codex R1 M#1 — unmatched_close_fill emit (no matching journal trade)."""
    csv = tmp_path / "tos.csv"
    csv.write_text(_UNMATCHED_CLOSE_FILL_CSV, encoding="utf-8")
    out = run_tos_reconciliation(conn, csv_path=csv)
    ds = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    ucf = [d for d in ds if d.discrepancy_type == "unmatched_close_fill"]
    assert len(ucf) == 1
    e = ucf[0]
    assert e.trade_id is None
    assert e.ticker == "ZOMBIE"
    assert e.material_to_review == 1


def test_material_by_type_authoritative_at_insert(
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch,
) -> None:
    """Codex R1 M#2 — caller-supplied material_to_review hint is IGNORED;
    service derives from MATERIAL_BY_TYPE lookup at INSERT time. Operator
    override is post-INSERT via update_discrepancy_material.
    """
    csv = tmp_path / "tos.csv"
    csv.write_text(_UNMATCHED_OPEN_FILL_CSV, encoding="utf-8")

    import swing.trades.reconciliation as svc

    def _evil_recon(*, conn, tos_text, price_tolerance, run_id, emitter):
        # Try to persist cash_movement_mismatch as material=1 (spec default 0).
        emitter(
            discrepancy_type="cash_movement_mismatch",
            run_id=run_id,
            trade_id=None,
            ticker=None,
            fill_id=None,
            cash_movement_id=None,
            field_name="amount",
            expected_value_json='{"amount": 100}',
            actual_value_json='{"amount": 200}',
            delta_text="$100",
            material_to_review=1,  # caller tries to lie
        )
        from swing.journal.tos_import import ReconciliationReport
        return ReconciliationReport()

    monkeypatch.setattr(svc, "reconcile_tos", _evil_recon)
    out = run_tos_reconciliation(conn, csv_path=csv)
    ds = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    cmms = [d for d in ds if d.discrepancy_type == "cash_movement_mismatch"]
    assert len(cmms) == 1
    # Service forced material=0 per MATERIAL_BY_TYPE, ignoring caller hint.
    assert cmms[0].material_to_review == 0


def test_nan_json_rejected_by_dataclass(
    conn: sqlite3.Connection,
) -> None:
    """Codex R1 M#3 — non-standard JSON constants (NaN, Infinity) rejected
    by ReconciliationDiscrepancy.__post_init__ even though Python's
    default json.loads accepts them.
    """
    from swing.data.models import ReconciliationDiscrepancy
    with pytest.raises(ValueError, match="non-standard JSON constant"):
        ReconciliationDiscrepancy(
            discrepancy_id=None, run_id=1,
            discrepancy_type="close_price_mismatch",
            trade_id=None, fill_id=None, cash_movement_id=None,
            linked_daily_management_record_id=None,
            ticker="ABC", field_name="price",
            expected_value_json='{"price": NaN}',
            actual_value_json=None,
            delta_text=None,
            material_to_review=1, resolution="unresolved",
            resolution_reason=None, resolved_at=None, resolved_by=None,
            mistake_tag_assigned=None,
            created_at="2026-05-12T08:00:00.000",
        )


def test_source_artifact_path_normalized_to_absolute(
    conn: sqlite3.Connection, tmp_path: Path, monkeypatch,
) -> None:
    """Codex R1 M#4 — source_artifact_path stored as absolute path per
    spec §3.2 even when caller passes a relative Path.
    """
    csv = tmp_path / "tos.csv"
    csv.write_text(_SIMPLE_TOS_CSV, encoding="utf-8")
    # Run from tmp_path so the relative path "tos.csv" is meaningful.
    monkeypatch.chdir(tmp_path)
    out = run_tos_reconciliation(conn, csv_path=Path("tos.csv"))
    assert out.source_artifact_path is not None
    p = Path(out.source_artifact_path)
    assert p.is_absolute(), (
        f"source_artifact_path must be absolute per spec §3.2; "
        f"got {out.source_artifact_path!r}"
    )


# ===========================================================================
# §10 — Codex R2 fixes: orphan-fill dedup collision + overfill-close
#       trade attribution.
# ===========================================================================


def test_orphan_unmatched_open_fills_distinct_payloads_dedup_separately(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Codex R2 M#1 — two real orphan fills for the same ticker but
    different (date, qty, price) MUST produce TWO discrepancy rows,
    not one. Pre-fix, the dedup key collapsed trade_id=None + fill_id
    =None + ticker=X across distinct payloads.
    """
    csv = tmp_path / "tos.csv"
    # Two GHOST OPEN fills, different qty/price.
    csv.write_text(
        "Account Trade History\n"
        "Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,"
        "Price,Net Price,Order Type\n"
        "2026-05-12 10:00:00,STOCK,BUY,+5,OPENING,GHOST,,,,42.0000,42.0000,MKT\n"
        "2026-05-12 11:00:00,STOCK,BUY,+7,OPENING,GHOST,,,,43.0000,43.0000,MKT\n",
        encoding="utf-8",
    )
    out = run_tos_reconciliation(conn, csv_path=csv)
    ds = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    uof = [d for d in ds if d.discrepancy_type == "unmatched_open_fill"]
    assert len(uof) == 2, (
        f"distinct orphan fills must produce 2 rows, not be deduped to 1; "
        f"got {len(uof)}"
    )
    qtys = sorted(json.loads(d.actual_value_json)["qty"] for d in uof)
    assert qtys == [5, 7]


def test_multiple_overfill_close_distinct_payloads_dedup_separately(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Codex R3 M#1 — multiple overfill CLOSE fills on the same trade
    with distinct (date, qty, price) must produce DISTINCT discrepancy
    rows. Pre-fix, the orphan payload disambiguator only applied when
    ALL THREE id slots were None; after R2 fix shifted trade_id=t.id
    on the overfill branch, the disambiguator stopped applying and
    distinct excess fills shared the dedup key.
    """
    from swing.data.models import Fill, Trade
    from swing.data.repos.fills import insert_fill_with_event
    from swing.data.repos.trades import insert_trade_with_event

    entry_ts = "2026-05-10T09:30:00"
    with conn:
        tid = insert_trade_with_event(
            conn,
            Trade(
                id=None, ticker="OVR2", entry_date="2026-05-10",
                entry_price=10.0, initial_shares=5,
                initial_stop=9.0, current_stop=9.0,
                state="entered",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None, trade_origin="manual_off_pipeline",
                pre_trade_locked_at=entry_ts,
            ),
            event_ts=entry_ts, rationale="seed",
        )
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=tid, fill_datetime=entry_ts,
                action="entry", quantity=5.0, price=10.0,
            ),
            event_ts=entry_ts,
        )

    # Two distinct CLOSE fills, each individually exceeding remaining
    # open size after within-batch cumulative reaches the cap.
    csv = tmp_path / "tos.csv"
    csv.write_text(
        "Account Trade History\n"
        "Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,"
        "Price,Net Price,Order Type\n"
        # First close fills the cap (5 shares); second overfills.
        "2026-05-12 10:00:00,STOCK,SELL,-5,CLOSING,OVR2,,,,11.0000,11.0000,MKT\n"
        "2026-05-12 11:00:00,STOCK,SELL,-3,CLOSING,OVR2,,,,11.5000,11.5000,MKT\n"
        "2026-05-12 12:00:00,STOCK,SELL,-2,CLOSING,OVR2,,,,12.0000,12.0000,MKT\n",
        encoding="utf-8",
    )
    out = run_tos_reconciliation(conn, csv_path=csv)
    ds = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    ucf = [d for d in ds
           if d.discrepancy_type == "unmatched_close_fill"
           and d.trade_id == tid]
    # Both overfill fills (3 + 2 shares at different prices) must
    # produce DISTINCT discrepancies, not collapse to one.
    assert len(ucf) == 2, (
        f"distinct overfill CLOSE fills on same trade must produce 2 "
        f"rows; got {len(ucf)}"
    )
    qtys = sorted(json.loads(d.actual_value_json)["qty"] for d in ucf)
    assert qtys == [2, 3]


def test_period_end_defaults_to_max_fill_date(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Codex R4 M#1 — when CLI omits --period-end, the service defaults
    period_end to the max fill date in the parsed CSV per plan §A.10 +
    spec §10.6 (filename is operator-controlled; last-fill-date is the
    meaningful data-derived default).
    """
    csv = tmp_path / "tos.csv"
    csv.write_text(
        "Account Trade History\n"
        "Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,"
        "Price,Net Price,Order Type\n"
        "2026-05-10 10:00:00,STOCK,BUY,+5,OPENING,A,,,,40.0000,40.0000,MKT\n"
        "2026-05-12 11:00:00,STOCK,BUY,+5,OPENING,B,,,,50.0000,50.0000,MKT\n"
        "2026-05-11 12:00:00,STOCK,BUY,+5,OPENING,C,,,,60.0000,60.0000,MKT\n",
        encoding="utf-8",
    )
    out = run_tos_reconciliation(conn, csv_path=csv)
    assert out.period_end == "2026-05-12"


def test_period_end_omitted_no_fills_stays_none(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Degenerate input: CSV with no fills → period_end stays None."""
    csv = tmp_path / "tos.csv"
    csv.write_text("", encoding="utf-8")
    out = run_tos_reconciliation(conn, csv_path=csv)
    assert out.period_end is None


def test_period_end_explicit_wins_over_default(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Operator-supplied --period-end overrides the data-derived default."""
    csv = tmp_path / "tos.csv"
    csv.write_text(
        "Account Trade History\n"
        "Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,"
        "Price,Net Price,Order Type\n"
        "2026-05-12 11:00:00,STOCK,BUY,+5,OPENING,X,,,,50.0000,50.0000,MKT\n",
        encoding="utf-8",
    )
    out = run_tos_reconciliation(
        conn, csv_path=csv, period_end="2026-05-30",
    )
    assert out.period_end == "2026-05-30"


def test_overfill_close_attributes_to_trade_id(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Codex R2 M#2 — when a TOS CLOSE fill exceeds remaining open size
    on a known journal trade, the unmatched_close_fill emit MUST set
    trade_id=t.id so the active-trade attention query surfaces it.
    """
    # Seed an open trade with current_size=5 (10 initial - 5 already
    # exited recorded as a non-entry fill).
    from swing.data.models import Fill, Trade
    from swing.data.repos.fills import insert_fill_with_event
    from swing.data.repos.trades import insert_trade_with_event

    entry_ts = "2026-05-10T09:30:00"
    with conn:
        tid = insert_trade_with_event(
            conn,
            Trade(
                id=None, ticker="OVR", entry_date="2026-05-10",
                entry_price=10.0, initial_shares=10,
                initial_stop=9.0, current_stop=9.0,
                state="partial_exited",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None, trade_origin="manual_off_pipeline",
                pre_trade_locked_at=entry_ts,
            ),
            event_ts=entry_ts, rationale="seed",
        )
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=tid, fill_datetime=entry_ts,
                action="entry", quantity=10.0, price=10.0,
            ),
            event_ts=entry_ts,
        )
        # Already sold 5 shares per journal.
        exit_ts = "2026-05-11T15:30:00"
        insert_fill_with_event(
            conn,
            Fill(
                fill_id=None, trade_id=tid, fill_datetime=exit_ts,
                action="exit", quantity=5.0, price=11.0, reason="target",
            ),
            event_ts=exit_ts,
        )
        conn.execute(
            "UPDATE trades SET current_size=5 WHERE id=?", (tid,),
        )

    # TOS reports a CLOSE for 8 more shares → cumulative would be 5+8=13
    # > 10 initial_shares → overfill branch.
    csv = tmp_path / "tos.csv"
    csv.write_text(
        "Account Trade History\n"
        "Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,"
        "Price,Net Price,Order Type\n"
        "2026-05-12 15:30:00,STOCK,SELL,-8,CLOSING,OVR,,,,12.0000,12.0000,MKT\n",
        encoding="utf-8",
    )
    # Phase 12 C.C T-C.6: bypass the auto-correct pivot so the
    # ``list_unresolved_material_for_active_trades`` canonical query
    # (filters on resolution='unresolved') still surfaces the row. The
    # pivot otherwise stamps it ``pending_ambiguity_resolution`` —
    # C.D widens the canonical queries.
    out = run_tos_reconciliation(conn, csv_path=csv, environment="sandbox")
    ds = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    ucf = [d for d in ds if d.discrepancy_type == "unmatched_close_fill"]
    assert len(ucf) == 1
    e = ucf[0]
    # Must attribute to the live trade so CANONICAL #1 surfaces it.
    assert e.trade_id == tid, (
        f"overfill close MUST attribute to known trade.id={tid}; got "
        f"trade_id={e.trade_id}"
    )
    # Confirm the canonical query picks it up.
    active = recon_repo.list_unresolved_material_for_active_trades(conn)
    assert any(d.discrepancy_id == e.discrepancy_id for d in active)


# ============================================================================
# §10 — T-C.6 equity_delta cross-bundle wiring
# ============================================================================
#
# Per dispatch brief §0.5 #5 + spec §3.3.1 + §3.5. After the existing
# emitter loop + before update_run_completed, the service computes
# source-side net-liq (Account Summary section) + journal-side equity
# (account_equity_snapshots.get_latest_snapshot_on_or_before(period_end))
# and emits an equity_delta discrepancy when BOTH sides are available AND
# abs(delta) > $10.00 (strict GT; boundary at exactly $10.00 is NOT-emit).


_TOS_CSV_WITH_ACCOUNT_SUMMARY = """\
Account Trade History
Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,Price,Net Price,Order Type
2026-05-12 10:00:00,STOCK,BUY,+10,OPENING,ABC,,,,10.0500,10.0500,MKT

Account Summary
Net Liquidating Value,"$1,400.00"
Stock Buying Power,"$1,000.00"
"""


def _seed_equity_snapshot(
    conn: sqlite3.Connection, *, snapshot_date: str, equity: float,
) -> None:
    """Seed a manual equity snapshot for source-ladder fallback testing."""
    from swing.data.repos.account_equity_snapshots import insert_snapshot

    insert_snapshot(
        conn,
        snapshot_date=snapshot_date,
        equity_dollars=equity,
        source="manual",
        source_artifact_path=None,
        recorded_at=now_ms(),
        recorded_by="operator",
        notes=None,
    )
    conn.commit()


def test_equity_delta_emit_when_both_sides_available_and_above_threshold(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Source net-liq $1400; journal snapshot $1300 → delta = -$100 → emit."""
    _seed_entry(
        conn, ticker="ABC", entry_date="2026-05-12",
        entry_price=10.05, shares=10, initial_stop=9.00,
    )
    _seed_equity_snapshot(conn, snapshot_date="2026-05-12", equity=1300.0)

    csv = tmp_path / "tos_with_summary.csv"
    csv.write_text(_TOS_CSV_WITH_ACCOUNT_SUMMARY, encoding="utf-8")
    out = run_tos_reconciliation(
        conn, csv_path=csv, period_end="2026-05-12",
    )
    assert out.state == "completed"
    # Both sides populated on the run row.
    assert out.account_equity_source_dollars == 1400.0
    assert out.account_equity_journal_dollars == 1300.0
    assert out.equity_delta_dollars == pytest.approx(-100.0)
    # equity_delta discrepancy row exists for this run.
    rows = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    eqd = [r for r in rows if r.discrepancy_type == "equity_delta"]
    assert len(eqd) == 1
    e = eqd[0]
    # Run-grain: no trade_id / fill_id / cash_movement_id / ticker.
    assert e.trade_id is None
    assert e.fill_id is None
    assert e.cash_movement_id is None
    assert e.ticker is None
    assert e.field_name == "net_liquidating_value"
    assert e.material_to_review == 0  # spec §3.3.1
    # JSON shapes per spec §3.3.1.
    expected = json.loads(e.expected_value_json)
    actual = json.loads(e.actual_value_json)
    assert expected == {"equity_dollars": 1300.0}
    assert actual == {"equity_dollars": 1400.0}


def test_equity_delta_not_emit_when_journal_snapshot_missing(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """No snapshot for period_end → run.equity_journal NULL → no emit."""
    _seed_entry(
        conn, ticker="ABC", entry_date="2026-05-12",
        entry_price=10.05, shares=10, initial_stop=9.00,
    )
    # NOTE: no snapshot seeded.
    csv = tmp_path / "tos_with_summary.csv"
    csv.write_text(_TOS_CSV_WITH_ACCOUNT_SUMMARY, encoding="utf-8")
    out = run_tos_reconciliation(
        conn, csv_path=csv, period_end="2026-05-12",
    )
    assert out.state == "completed"
    assert out.account_equity_source_dollars == 1400.0
    assert out.account_equity_journal_dollars is None
    assert out.equity_delta_dollars is None
    rows = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    assert not any(r.discrepancy_type == "equity_delta" for r in rows)


def test_equity_delta_not_emit_when_source_section_missing(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """CSV with no Account Summary section → no emit + journal NULL."""
    _seed_entry(
        conn, ticker="ABC", entry_date="2026-05-12",
        entry_price=10.05, shares=10, initial_stop=9.00,
    )
    _seed_equity_snapshot(conn, snapshot_date="2026-05-12", equity=1300.0)
    # Use the simple CSV (no Account Summary).
    csv = tmp_path / "tos_simple.csv"
    csv.write_text(_SIMPLE_TOS_CSV, encoding="utf-8")
    out = run_tos_reconciliation(
        conn, csv_path=csv, period_end="2026-05-12",
    )
    assert out.state == "completed"
    assert out.account_equity_source_dollars is None
    # journal side IS computable but the spec persists journal-side
    # independently. T-C.6 contract: both columns + delta wired together;
    # NULL on one side implies NULL on delta + no emit.
    assert out.equity_delta_dollars is None
    rows = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    assert not any(r.discrepancy_type == "equity_delta" for r in rows)


def test_equity_delta_boundary_strictly_above_ten_dollars_emits(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """abs(delta) = $10.01 → EMIT (strict GT)."""
    _seed_entry(
        conn, ticker="ABC", entry_date="2026-05-12",
        entry_price=10.05, shares=10, initial_stop=9.00,
    )
    _seed_equity_snapshot(conn, snapshot_date="2026-05-12", equity=1389.99)

    csv_text = _TOS_CSV_WITH_ACCOUNT_SUMMARY  # source = $1400.00
    # delta = journal 1389.99 - source 1400.00 = -10.01 → |delta|=10.01 → emit
    csv = tmp_path / "tos.csv"
    csv.write_text(csv_text, encoding="utf-8")
    out = run_tos_reconciliation(
        conn, csv_path=csv, period_end="2026-05-12",
    )
    assert out.equity_delta_dollars == pytest.approx(-10.01)
    rows = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    assert any(r.discrepancy_type == "equity_delta" for r in rows)


def test_equity_delta_boundary_at_exactly_ten_dollars_does_not_emit(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """abs(delta) = $10.00 → NO emit (strict GT)."""
    _seed_entry(
        conn, ticker="ABC", entry_date="2026-05-12",
        entry_price=10.05, shares=10, initial_stop=9.00,
    )
    _seed_equity_snapshot(conn, snapshot_date="2026-05-12", equity=1390.0)

    csv_text = _TOS_CSV_WITH_ACCOUNT_SUMMARY  # source = $1400.00
    # delta = 1390 - 1400 = -10.00 → |delta|=10.00 → NOT-emit
    csv = tmp_path / "tos.csv"
    csv.write_text(csv_text, encoding="utf-8")
    out = run_tos_reconciliation(
        conn, csv_path=csv, period_end="2026-05-12",
    )
    assert out.equity_delta_dollars == pytest.approx(-10.0)
    rows = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    assert not any(r.discrepancy_type == "equity_delta" for r in rows)


def test_equity_delta_boundary_below_threshold_does_not_emit(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """abs(delta) = $9.99 → NO emit."""
    _seed_entry(
        conn, ticker="ABC", entry_date="2026-05-12",
        entry_price=10.05, shares=10, initial_stop=9.00,
    )
    _seed_equity_snapshot(conn, snapshot_date="2026-05-12", equity=1390.01)
    csv_text = _TOS_CSV_WITH_ACCOUNT_SUMMARY  # source = $1400.00
    # delta = 1390.01 - 1400.00 = -9.99 → no emit
    csv = tmp_path / "tos.csv"
    csv.write_text(csv_text, encoding="utf-8")
    out = run_tos_reconciliation(
        conn, csv_path=csv, period_end="2026-05-12",
    )
    assert out.equity_delta_dollars == pytest.approx(-9.99)
    rows = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    assert not any(r.discrepancy_type == "equity_delta" for r in rows)


def test_equity_delta_uses_source_ladder_for_journal_snapshot(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Journal-side equity uses get_latest_snapshot_on_or_before with
    source-ladder precedence (schwab_api > tos_csv > manual)."""
    from swing.data.repos.account_equity_snapshots import insert_snapshot

    _seed_entry(
        conn, ticker="ABC", entry_date="2026-05-12",
        entry_price=10.05, shares=10, initial_stop=9.00,
    )
    # Three snapshots same date: manual $1300, tos_csv $1320, schwab_api
    # $1350. The schwab_api row must win.
    insert_snapshot(
        conn, snapshot_date="2026-05-12", equity_dollars=1300.0,
        source="manual", source_artifact_path=None,
        recorded_at=now_ms(), recorded_by="operator", notes=None,
    )
    insert_snapshot(
        conn, snapshot_date="2026-05-12", equity_dollars=1320.0,
        source="tos_csv", source_artifact_path=None,
        recorded_at=now_ms(), recorded_by="operator", notes=None,
    )
    insert_snapshot(
        conn, snapshot_date="2026-05-12", equity_dollars=1350.0,
        source="schwab_api", source_artifact_path=None,
        recorded_at=now_ms(), recorded_by="operator", notes=None,
    )
    conn.commit()

    csv = tmp_path / "tos.csv"
    csv.write_text(_TOS_CSV_WITH_ACCOUNT_SUMMARY, encoding="utf-8")  # source $1400
    out = run_tos_reconciliation(
        conn, csv_path=csv, period_end="2026-05-12",
    )
    assert out.account_equity_journal_dollars == 1350.0  # schwab_api wins
    assert out.equity_delta_dollars == pytest.approx(1350.0 - 1400.0)


def test_equity_delta_uses_snapshot_on_or_before_period_end(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Period_end 2026-05-15 + snapshot dated 2026-05-12 → journal = $1300."""
    _seed_entry(
        conn, ticker="ABC", entry_date="2026-05-12",
        entry_price=10.05, shares=10, initial_stop=9.00,
    )
    _seed_equity_snapshot(conn, snapshot_date="2026-05-12", equity=1300.0)
    csv = tmp_path / "tos.csv"
    csv.write_text(_TOS_CSV_WITH_ACCOUNT_SUMMARY, encoding="utf-8")  # source $1400
    out = run_tos_reconciliation(
        conn, csv_path=csv, period_end="2026-05-15",
    )
    assert out.account_equity_journal_dollars == 1300.0  # 5/12 snap <= 5/15
    assert out.equity_delta_dollars == pytest.approx(-100.0)


def test_equity_delta_skips_snapshot_dated_after_period_end(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Snapshot dated AFTER period_end → not consumed → journal NULL → no emit."""
    _seed_entry(
        conn, ticker="ABC", entry_date="2026-05-12",
        entry_price=10.05, shares=10, initial_stop=9.00,
    )
    _seed_equity_snapshot(conn, snapshot_date="2026-05-20", equity=1300.0)
    csv = tmp_path / "tos.csv"
    csv.write_text(_TOS_CSV_WITH_ACCOUNT_SUMMARY, encoding="utf-8")
    out = run_tos_reconciliation(
        conn, csv_path=csv, period_end="2026-05-12",
    )
    assert out.account_equity_journal_dollars is None
    assert out.equity_delta_dollars is None
    rows = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    assert not any(r.discrepancy_type == "equity_delta" for r in rows)


def test_equity_delta_dedup_single_row_per_run(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Even though the equity_delta computation runs once per run, the
    within-run dedup tuple shape (All-None) MUST emit exactly one row.

    This guards against any future code path that might invoke the
    emitter twice (e.g., Schwab-API + TOS-CSV co-emission in V2).
    """
    _seed_entry(
        conn, ticker="ABC", entry_date="2026-05-12",
        entry_price=10.05, shares=10, initial_stop=9.00,
    )
    _seed_equity_snapshot(conn, snapshot_date="2026-05-12", equity=1300.0)
    csv = tmp_path / "tos.csv"
    csv.write_text(_TOS_CSV_WITH_ACCOUNT_SUMMARY, encoding="utf-8")
    out = run_tos_reconciliation(
        conn, csv_path=csv, period_end="2026-05-12",
    )
    rows = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    eqd = [r for r in rows if r.discrepancy_type == "equity_delta"]
    assert len(eqd) == 1, (
        f"expected exactly one equity_delta row per run; got {len(eqd)}"
    )


def test_equity_delta_not_emit_when_source_is_nan_or_inf(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Codex R2 Major #1 regression: a corrupted Net Liquidating Value
    (NaN / inf literal) MUST NOT poison the run row or emit a discrepancy.

    The parser-level fix returns None on non-finite; the service-level
    consequence is the same as 'source-side unavailable' — both equity
    columns + delta stay NULL + no equity_delta emit.
    """
    _seed_entry(
        conn, ticker="ABC", entry_date="2026-05-12",
        entry_price=10.05, shares=10, initial_stop=9.00,
    )
    _seed_equity_snapshot(conn, snapshot_date="2026-05-12", equity=1300.0)
    poisoned_csv = (
        "Account Trade History\n"
        "Exec Time,Spread,Side,Qty,Pos Effect,Symbol,Exp,Strike,Type,Price,Net Price,Order Type\n"
        "2026-05-12 10:00:00,STOCK,BUY,+10,OPENING,ABC,,,,10.0500,10.0500,MKT\n"
        "\n"
        "Account Summary\n"
        "Net Liquidating Value,NaN\n"
    )
    csv = tmp_path / "tos_nan.csv"
    csv.write_text(poisoned_csv, encoding="utf-8")
    out = run_tos_reconciliation(
        conn, csv_path=csv, period_end="2026-05-12",
    )
    assert out.state == "completed"
    assert out.account_equity_source_dollars is None
    assert out.equity_delta_dollars is None
    rows = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    assert not any(r.discrepancy_type == "equity_delta" for r in rows)


def test_equity_delta_path_does_not_affect_non_equity_runs(
    conn: sqlite3.Connection, tmp_path: Path,
) -> None:
    """Regression-clean: a CSV without Account Summary + no snapshot
    produces the same 4-or-fewer discrepancies as before T-C.6 wiring.

    The Bundle B operator-witnessed gate used the operator's real-world
    Schwab/TOS export (5 stop_mismatch rows). Bundle C MUST NOT regress
    that path. We verify with a fixture that BOTH lacks the Account
    Summary section AND has no journal-side snapshot.
    """
    _seed_entry(
        conn, ticker="ABC", entry_date="2026-05-12",
        entry_price=10.05, shares=10, initial_stop=9.00,
    )
    csv = tmp_path / "tos_simple.csv"
    csv.write_text(_SIMPLE_TOS_CSV, encoding="utf-8")
    out = run_tos_reconciliation(
        conn, csv_path=csv, period_end="2026-05-12",
    )
    assert out.state == "completed"
    rows = recon_repo.list_discrepancies_for_run(conn, out.run_id)
    assert not any(r.discrepancy_type == "equity_delta" for r in rows)
    # And the run-row equity columns are NULL.
    assert out.account_equity_source_dollars is None
    assert out.account_equity_journal_dollars is None
    assert out.equity_delta_dollars is None
