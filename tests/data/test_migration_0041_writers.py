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


# ---------------------------------------------------------------------------
# account_equity_snapshots (T9)
# ---------------------------------------------------------------------------
def test_aes_upsert_at_41(tmp_path: Path) -> None:
    """repos/account_equity_snapshots.py:77 (insert) + :121 (the re-record
    UPDATE of the mutable columns): SELECT-then-UPDATE-or-INSERT, so no
    conflict-resolution INSERT ever meets trg_aes_no_replace."""
    from swing.data.repos.account_equity_snapshots import upsert_snapshot

    def both(k):
        new = upsert_snapshot(k, snapshot_date="2026-08-12", equity_dollars=1.0,
                              source="manual", source_artifact_path=None,
                              recorded_at=NOW, recorded_by="op", notes=None,
                              basis="net_liq")
        same = upsert_snapshot(k, snapshot_date="2026-08-10", equity_dollars=2.0,
                               source="schwab_api", source_artifact_path="p",
                               recorded_at=NOW, recorded_by="pipeline", notes="n",
                               basis="net_liq")
        assert new != 1 and same == 1

    c = _world(tmp_path)
    try:
        assert outcome(c, both) == "OK"
    finally:
        c.close()


def test_aes_account_hash_stamp_at_41(tmp_path: Path) -> None:
    """swing/integrations/schwab/audit_service.py:339 -- the literal stamp."""
    c = _world(tmp_path)
    try:
        assert outcome(c, "UPDATE account_equity_snapshots SET schwab_account_hash = ? "
                          "WHERE snapshot_id = ?", ("h", 1)) == "OK"
    finally:
        c.close()


def _disc(**kw):
    from swing.trades.reconciliation_auto_correct import _DiscrepancyInfo

    base = dict(discrepancy_id=9, run_id=1, discrepancy_type="equity_delta",
                trade_id=None, fill_id=None, cash_movement_id=None,
                field_name="equity_dollars", resolution="unresolved",
                ambiguity_kind=None, expected_value_json=None)
    base.update(kw)
    return _DiscrepancyInfo(**base)


@pytest.mark.parametrize("kw,expected", [
    ({"fill_id": 41, "trade_id": 20}, ("fills", 41)),
    ({"cash_movement_id": 1, "trade_id": 20}, ("cash_movements", 1)),
    ({"trade_id": 20}, ("trades", 20)),
    ({"discrepancy_type": "equity_delta"}, ValueError),
    ({"discrepancy_type": "snapshot_mismatch"}, ValueError),
])
def test_corrector_snapshot_branch_unreachable(tmp_path: Path, kw, expected) -> None:
    """AL-7's SERVICE prevention, pinned: `_resolve_affected_target`
    (reconciliation_auto_correct.py:2182-2205) has THREE returning branches
    (fills, cash_movements, trades) and otherwise RAISES -- its docstring
    (:2188-2193) names a snapshot branch the code does not implement -- so the
    corrector's dynamic `SET {field_name}` on account_equity_snapshots
    (:2325-2328) has no caller path from a discrepancy. A snapshot-typed
    discrepancy with no FK raises ValueError, and no UPDATE is issued (a
    sqlite3 trace callback on a live connection records none)."""
    from swing.trades.reconciliation_auto_correct import _resolve_affected_target

    c = _world(tmp_path)
    seen: list[str] = []
    c.set_trace_callback(seen.append)
    try:
        if expected is ValueError:
            with pytest.raises(ValueError, match="no resolvable"):
                _resolve_affected_target(_disc(**kw))
        else:
            assert _resolve_affected_target(_disc(**kw)) == expected
        assert "account_equity_snapshots" not in _resolve_targets_seen(kw)
    finally:
        c.set_trace_callback(None)
        c.close()
    assert not [s for s in seen if s.lstrip().upper().startswith("UPDATE")]


def _resolve_targets_seen(kw) -> set[str]:
    from swing.trades.reconciliation_auto_correct import _resolve_affected_target

    try:
        return {_resolve_affected_target(_disc(**kw))[0]}
    except ValueError:
        return set()


# ---------------------------------------------------------------------------
# risk_policy / hypothesis_registry / hypothesis_status_history (T10)
# ---------------------------------------------------------------------------
PAIR = pytest.mark.parametrize("version", [40, 41])


def _pair_world(tmp_path: Path, version: int):
    return migrated(tmp_path, version, world=True)


def _rp_row(c, **kw) -> dict:
    from tests.data._22i_seed import row_of

    row = row_of(c, "risk_policy")
    del row["policy_id"]
    row.update(kw)
    return row


@PAIR
def test_rp_append_and_the_partial_unique_barrier(tmp_path: Path, version: int) -> None:
    """A1 on risk_policy: an INACTIVE policy appends at both versions. A2/A3 on
    the partial UNIQUE ux_risk_policy_active: a second ACTIVE policy under
    INSERT OR REPLACE replaces policy 1 at v40 and is refused at v41; INSERT
    OR IGNORE is a silent no-op at v40 and refused at v41 (the priced cost)."""
    from tests.data._22i_seed import insert_copy_sql

    c = _pair_world(tmp_path, version)
    try:
        assert outcome(c, *insert_copy_sql(c, "risk_policy", _rp_row(c, is_active=0))) == "OK"
        active = _rp_row(c, is_active=1, policy_notes="new")
        rep = outcome(c, *insert_copy_sql(c, "risk_policy", active, verb="INSERT OR REPLACE"))
        ign = outcome(c, *insert_copy_sql(c, "risk_policy", active, verb="INSERT OR IGNORE"))
    finally:
        c.close()
    if version == 40:
        assert (rep, ign) == ("OK", "OK")
    else:
        assert rep == ign == "TRIGGER:trg_rp_no_replace"


@PAIR
@pytest.mark.parametrize("step", ["one_to_zero", "zero_to_one"])
def test_c5_rp_is_active_directional(tmp_path: Path, step: str, version: int) -> None:
    c = _pair_world(tmp_path, version)
    try:
        off = ("UPDATE risk_policy SET is_active = 0 WHERE policy_id = 1",)
        if step == "one_to_zero":
            verdict = outcome(c, *off)
        else:
            verdict = outcome(c, "UPDATE risk_policy SET is_active = 1 WHERE policy_id = 1",
                              setup=[off])
    finally:
        c.close()
    if step == "one_to_zero" or version == 40:
        assert verdict == "OK", verdict
    else:
        assert verdict == "TRIGGER:trg_rp_immutable"


@PAIR
def test_hsh_append_and_the_partial_unique_barrier(tmp_path: Path, version: int) -> None:
    """A1: a CLOSED interval appends at both versions. A2/A3 on the partial
    UNIQUE ux_hypothesis_status_history_current: a second OPEN interval for
    hypothesis 1 replaces / ignores at v40 and is refused at v41."""
    from tests.data._22i_seed import insert_copy_sql

    c = _pair_world(tmp_path, version)
    try:
        closed = dict(hypothesis_id=1, status="paused",
                      effective_from="2026-01-01T00:00:00.000",
                      effective_to="2026-02-01T00:00:00.000", change_reason="r",
                      recorded_at=NOW)
        assert outcome(c, *insert_copy_sql(c, "hypothesis_status_history", closed)) == "OK"
        open_ = dict(closed, effective_to=None)
        rep = outcome(c, *insert_copy_sql(c, "hypothesis_status_history", open_,
                                          verb="INSERT OR REPLACE"))
        ign = outcome(c, *insert_copy_sql(c, "hypothesis_status_history", open_,
                                          verb="INSERT OR IGNORE"))
    finally:
        c.close()
    if version == 40:
        assert (rep, ign) == ("OK", "OK")
    else:
        assert rep == ign == "TRIGGER:trg_hsh_no_replace"


def test_rp_supersede_end_to_end(tmp_path: Path) -> None:
    """supersede_active_policy at 41: the predecessor flag written TWICE
    (update_policy_active_flag, trades/risk_policy.py:162 then :203), the
    successor INSERT passing the partial-unique barrier."""
    from swing.data.db import ensure_schema
    from swing.trades.risk_policy import supersede_active_policy

    conn = ensure_schema(tmp_path / "rp.db")
    try:
        new_id = supersede_active_policy(
            conn, field_updates={"max_concurrent_positions": 7}, notes="22-I")
        rows = conn.execute("SELECT policy_id, is_active, effective_to IS NOT NULL, "
                            "superseded_by_policy_id FROM risk_policy ORDER BY policy_id"
                            ).fetchall()
    finally:
        conn.close()
    assert rows == [(1, 0, 1, new_id), (new_id, 1, 0, None)]


def test_rp_ratification_after_0041(tmp_path: Path) -> None:
    """The v17 ratification runs AFTER every migration of a fresh walk, i.e.
    with 0041's triggers already installed; its supersession is admitted."""
    import dataclasses

    from swing.config import load as load_cfg
    from swing.data.db import ensure_schema
    from swing.trades.risk_policy import ratify_seed_from_cfg_on_v17_landing
    from tests.cli.test_cli_eval import _minimal_config

    project, home = tmp_path / "project", tmp_path / "home"
    project.mkdir()
    home.mkdir()
    cfg = load_cfg(_minimal_config(project, home))
    conn = ensure_schema(cfg.paths.db_path)
    try:
        assert conn.execute("SELECT COUNT(*) FROM sqlite_master WHERE name IN "
                            "('trg_rp_immutable','trg_rp_no_replace')").fetchone() == (2,)
        divergent = dataclasses.replace(
            cfg, account=dataclasses.replace(cfg.account, risk_equity_floor=8500.0))
        new_id = ratify_seed_from_cfg_on_v17_landing(conn, divergent)
    finally:
        conn.close()
    assert new_id is not None and new_id != 1


def test_hr_transition_end_to_end(tmp_path: Path) -> None:
    """update_hypothesis_status_with_audit (trades/hypothesis.py:145) at 41:
    close the open interval (NULL -> value), append the successor, and the
    registry's three writer columns move."""
    from swing.data.db import ensure_schema
    from swing.trades.hypothesis import update_hypothesis_status_with_audit

    conn = ensure_schema(tmp_path / "hr.db")
    try:
        r = update_hypothesis_status_with_audit(
            conn, hypothesis_id=1, new_status="paused", change_reason="22-I")
        status = conn.execute("SELECT status FROM hypothesis_registry WHERE id = 1"
                              ).fetchone()
        open_rows = conn.execute("SELECT status FROM hypothesis_status_history "
                                 "WHERE hypothesis_id = 1 AND effective_to IS NULL"
                                 ).fetchall()
    finally:
        conn.close()
    assert r == "transition"
    assert status == ("paused",)
    assert open_rows == [("paused",)]


@PAIR
def test_hr_preregistered_criteria_frozen(tmp_path: Path, version: int) -> None:
    """The 0034 preserved-original column is covered BY EXCLUSION: an in-place
    edit is refused at 41; an amendment is a migration that DROP/CREATEs the
    twin (the 0034 precedent)."""
    c = _pair_world(tmp_path, version)
    try:
        verdict = outcome(c, "UPDATE hypothesis_registry SET "
                             "preregistered_decision_criteria = 'rewritten' WHERE id = 1")
        dc = outcome(c, "UPDATE hypothesis_registry SET decision_criteria = 'x' "
                        "WHERE id = 1")
    finally:
        c.close()
    if version == 40:
        assert (verdict, dc) == ("OK", "OK")
    else:
        assert verdict == dc == "TRIGGER:trg_hr_immutable"


def test_hsh_update_close_open_interval(tmp_path: Path) -> None:
    """repos/hypothesis_status_history.py:80 at 41: effective_to NULL -> value."""
    from swing.data.repos.hypothesis_status_history import update_close_open_interval

    c = _world(tmp_path)
    try:
        assert outcome(c, lambda k: update_close_open_interval(
            k, hypothesis_id=1, effective_to=NOW)) == "OK"
    finally:
        c.close()
