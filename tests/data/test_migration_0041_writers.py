"""22-I -- every production writer of a newly guarded table, at v41 (plan
sections 4.2 per-table extras and 3 T6-T10).

A guard that aborts a PRODUCTION writer is a FINDING (plan T16), never a
reason to narrow the barrier; these tests are the positive half of the
discriminating set: each writer site's own statement, on the seeded world at
v41, is ADMITTED. Where the writer is a repo function it is CALLED; where it
is a statement inside a larger service it is its LITERAL SQL, cited by
file:line (read at 22-I executing round 0).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from tests.data._22i_seed import migrated, outcome

NOW = "2026-09-24T12:00:00.000"


def _world(tmp_path: Path):
    return migrated(tmp_path, 41, world=True)


# ---------------------------------------------------------------------------
# reconciliation_runs / reconciliation_discrepancies -- the twelve sites
# (plan ledger S3-2)
# ---------------------------------------------------------------------------
def _repo_sites():
    from swing.data.repos import reconciliation as repo

    return {
        "repo:191 update_run_completed": lambda c: repo.update_run_completed(
            c, run_id=1, finished_ts=NOW, account_equity_journal_dollars=1.0,
            account_equity_source_dollars=1.0, equity_delta_dollars=0.0,
            trades_reconciled_count=1, fills_reconciled_count=1,
            discrepancies_count=2, unresolved_discrepancies_count=2,
            summary_json="{}", notes="n"),
        "repo:235 update_run_failed": lambda c: repo.update_run_failed(
            c, run_id=1, finished_ts=NOW, error_message="boom"),
        "repo:399 resolve (clear ambiguity)": lambda c: repo.update_discrepancy_resolution(
            c, discrepancy_id=1, resolution="acknowledged_immaterial",
            resolution_reason="r", resolved_by="operator", resolved_at=NOW,
            clear_ambiguity_kind=True),
        "repo:412 resolve": lambda c: repo.update_discrepancy_resolution(
            c, discrepancy_id=1, resolution="journal_corrected",
            resolution_reason="r", resolved_by="operator", resolved_at=NOW,
            mistake_tag_assigned="tag"),
        "repo:442 material": lambda c: repo.update_discrepancy_material(
            c, discrepancy_id=1, material_to_review=0),
    }


_LITERAL_SITES = {
    "trades/reconciliation.py:721": (
        "UPDATE reconciliation_runs SET unresolved_discrepancies_count = "
        "  MAX(0, COALESCE(unresolved_discrepancies_count, 0) - 1) WHERE run_id = ?",
        (1,)),
    "reconciliation_auto_correct.py:996": (
        "UPDATE reconciliation_discrepancies SET resolution=?, "
        "ambiguity_kind=NULL, resolution_reason=?, resolved_at=?, "
        "resolved_by='operator' WHERE discrepancy_id=?",
        ("acknowledged_immaterial", "r", NOW, 1)),
    "reconciliation_auto_correct.py:1002": (
        "UPDATE reconciliation_discrepancies SET resolution=?, "
        "resolution_reason=?, resolved_at=?, resolved_by='operator' "
        "WHERE discrepancy_id=?",
        ("acknowledged_immaterial", "r", NOW, 1)),
    "reconciliation_auto_correct.py:1583": (
        "UPDATE reconciliation_discrepancies SET resolution = ?, "
        "resolution_reason = ?, resolved_at = ?, resolved_by = ? "
        "WHERE discrepancy_id = ?",
        ("auto_corrected_from_schwab", "r", NOW, "auto", 1)),
    "reconciliation_auto_correct.py:1976": (
        "UPDATE reconciliation_discrepancies SET resolution = ?, "
        "resolution_reason = ?, resolved_at = ?, resolved_by = ? "
        "WHERE discrepancy_id = ?",
        ("operator_overridden", "r", NOW, "operator", 1)),
    "reconciliation_auto_correct.py:2053": (
        "UPDATE reconciliation_discrepancies SET resolution = ?, "
        "ambiguity_kind = ?, resolution_reason = ? WHERE discrepancy_id = ?",
        ("pending_ambiguity_resolution", "unsupported", "r", 1)),
    "reconciliation_auto_correct.py:2623": (
        "UPDATE reconciliation_discrepancies SET resolution = ?, "
        "resolution_reason = ?, resolved_at = ?, resolved_by = ? "
        "WHERE discrepancy_id = ?",
        ("operator_resolved_ambiguity", "r", NOW, "operator", 1)),
}


@pytest.mark.parametrize("site", [
    "repo:191 update_run_completed", "repo:235 update_run_failed",
    "repo:399 resolve (clear ambiguity)", "repo:412 resolve", "repo:442 material"])
def test_reconciliation_repo_writer_site_admitted_at_41(tmp_path: Path, site: str) -> None:
    c = _world(tmp_path)
    try:
        assert outcome(c, _repo_sites()[site]) == "OK"
    finally:
        c.close()


@pytest.mark.parametrize("site", sorted(_LITERAL_SITES))
def test_reconciliation_literal_writer_site_admitted_at_41(tmp_path: Path,
                                                           site: str) -> None:
    c = _world(tmp_path)
    try:
        sql, params = _LITERAL_SITES[site]
        setup = []
        if site.endswith(":2623"):
            # the operator-resolved-ambiguity transition starts from pending
            setup = [_LITERAL_SITES["reconciliation_auto_correct.py:2053"]]
        assert outcome(c, sql, params, setup=setup) == "OK"
    finally:
        c.close()


def test_the_twelve_sites_are_all_rostered() -> None:
    assert len(_repo_sites()) + len(_LITERAL_SITES) == 12


# ---------------------------------------------------------------------------
# reconciliation_corrections (T7; RD S3-F1 as amended)
# ---------------------------------------------------------------------------
RC_TWIN = "TRIGGER:trg_rc_immutable"


def test_rc_anchor_self_reference_3251_admitted(tmp_path: Path) -> None:
    """reconciliation_auto_correct.py:3251 -- the anchor's correction_set_id
    NULL -> self (write-once W: admitted); value -> other then refused."""
    c = _world(tmp_path)
    try:
        stmt = ("UPDATE reconciliation_corrections SET correction_set_id = ? "
                "WHERE correction_id = ?")
        assert outcome(c, stmt, (1, 1)) == "OK"
        assert outcome(c, stmt, (2, 1), setup=[(stmt, (1, 1))]) == RC_TWIN
    finally:
        c.close()


def test_rc_supersede_repo_208(tmp_path: Path) -> None:
    """repos/reconciliation_corrections.py:208 (update_superseded_by): NULL ->
    value admitted; value -> NULL and value -> other refused (no SET-NULL
    exemption on the self-FK, RD S3-F1 amendment)."""
    from swing.data.repos.reconciliation_corrections import update_superseded_by

    c = _world(tmp_path)
    try:
        assert outcome(c, lambda k: update_superseded_by(k, 1, 2)) == "OK"
        first = [("UPDATE reconciliation_corrections SET superseded_by_correction_id = 2 "
                  "WHERE correction_id = 1",)]
        assert outcome(c, lambda k: update_superseded_by(k, 1, 1),
                       setup=first) == RC_TWIN
        assert outcome(c, "UPDATE reconciliation_corrections SET "
                          "superseded_by_correction_id = NULL WHERE correction_id = 1",
                       setup=first) == RC_TWIN
    finally:
        c.close()


def test_rc_entry_date_correction_1543(tmp_path: Path) -> None:
    """swing/trades/entry_date_correction.py:1543 -- the literal statement."""
    c = _world(tmp_path)
    try:
        assert outcome(c, "UPDATE reconciliation_corrections SET "
                          "superseded_by_correction_id = ? WHERE correction_id = ?",
                       (2, 1)) == "OK"
    finally:
        c.close()


def test_rc_split_into_partials_end_to_end(tmp_path: Path) -> None:
    """The production split handler at v41: DELETE the consolidated fill, the
    anchor row, its self-reference (:3251), N partial rows under one set."""
    from swing.data.db import EXPECTED_SCHEMA_VERSION, ensure_schema
    from swing.trades.reconciliation_auto_correct import apply_tier2_resolution
    from tests.trades.test_apply_tier2_resolution import _seed_dhc_pending

    assert EXPECTED_SCHEMA_VERSION == 41
    conn = ensure_schema(tmp_path / "split.db")
    try:
        assert conn.execute("SELECT 1 FROM sqlite_master WHERE name = "
                            "'trg_rc_immutable'").fetchone() == (1,)
        world = _seed_dhc_pending(conn)
        apply_tier2_resolution(
            conn, discrepancy_id=world["discrepancy_id"],
            choice_code="split_into_partials",
            operator_custom_payload=[
                {"qty": 20, "price": 7.57, "fill_datetime": "2026-04-27T14:23:00"},
                {"qty": 19, "price": 7.59, "fill_datetime": "2026-04-27T14:23:42"},
            ],
            operator_reason="two partial executions")
        rows = conn.execute(
            "SELECT correction_id, correction_set_id FROM reconciliation_corrections "
            "WHERE discrepancy_id = ? ORDER BY correction_id",
            (world["discrepancy_id"],)).fetchall()
    finally:
        conn.close()
    assert len(rows) == 3
    anchor = rows[0][0]
    assert {r[1] for r in rows} == {anchor}


# ---------------------------------------------------------------------------
# schwab_api_calls / yfinance_calls (T8): the audit-row lifecycle
# ---------------------------------------------------------------------------
def test_audit_row_lifecycle_at_41(tmp_path: Path) -> None:
    """Every writer of both audit tables, through its repo function: the
    in-flight INSERT, the outcome close, and the three schwab link stamps."""
    from swing.data.repos import schwab_api_calls as sac
    from swing.data.repos import yfinance_calls as yfc

    def lifecycle(k):
        cid = sac.insert_in_flight(k, ts=NOW, endpoint="accounts.details",
                                   pipeline_run_id=1, surface="pipeline",
                                   environment="production")
        sac.update_call_outcome(k, call_id=cid, http_status=200, response_time_ms=5,
                                rate_limit_remaining=None, signature_hash="s",
                                status="success", error_message=None)
        sac.update_call_linked_snapshot(k, call_id=cid, snapshot_id=1)
        sac.update_call_linked_reconciliation_run(k, call_id=cid, reconciliation_run_id=1)
        sac.update_call_linked_correction(k, call_id=cid, correction_id=1)
        yid = yfc.insert_in_flight(k, ts=NOW, call_type="download_single",
                                   ticker="AMN", ticker_count=None,
                                   pipeline_run_id=1, surface="pipeline")
        yfc.update_call_outcome(k, call_id=yid, response_time_ms=5, status="success",
                                rows_returned=3, error_message=None)

    c = _world(tmp_path)
    try:
        assert outcome(c, lifecycle) == "OK"
    finally:
        c.close()


def test_reconciliation_auto_correct_2370_link_admitted(tmp_path: Path) -> None:
    """reconciliation_auto_correct.py:2370 -- the literal link stamp."""
    c = _world(tmp_path)
    try:
        assert outcome(c, "UPDATE schwab_api_calls SET linked_correction_id = ? "
                          "WHERE call_id = ?", (1, 1)) == "OK"
    finally:
        c.close()


def test_fix_phase2_script_statement_admitted(tmp_path: Path) -> None:
    """scripts/fix_phase2_misleading_audit_rows.py:102 -- the one writer
    outside swing/ (status + error_message: both mutable)."""
    c = _world(tmp_path)
    try:
        assert outcome(c, "UPDATE schwab_api_calls SET status = 'auth_failed', "
                          "error_message = ? WHERE call_id = ?", ("e", 1)) == "OK"
    finally:
        c.close()
