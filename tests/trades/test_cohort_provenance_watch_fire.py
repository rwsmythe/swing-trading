"""D104 T1.2 -- the watch-fire relabel service (kind 2, ``last_fire``).

Plan `docs/superpowers/plans/2026-11-11-sg-label-correction.md` T1.6/T1.7,
tests 1a, 1n, 1o, 1p, 1r. Every case runs on ``build_sg_case`` -- trade 29's
LIVE shape -- or a variant of it whose single knob is named in the test; no
value is chosen to make a test pass.

Every refusal case asserts the COUNTERFACTUAL as well as the message: zero
audit rows, and the trade's label and ``candidate_id`` unchanged.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import (
    PROVENANCE_ADMISSION_TIER_LAST_FIRE,
    PROVENANCE_CORRECTION_KIND_FILL_UNSET,
    PROVENANCE_CORRECTION_KIND_WATCH_FIRE,
    PROVENANCE_WATCH_FIRE_CORRECTED_FIELDS,
)
from swing.data.repos.provenance_corrections import get_correction_for_trade
from swing.trades import cohort_provenance_correction as cpc
from swing.trades.cohort_provenance_correction import (
    CITATION_DRIFT,
    DERIVATION_RULE_VERSION,
    CallerHeldTransactionError,
    CohortProvenanceCorrectionError,
    correct_cohort_provenance,
    correct_watch_fire_label,
    preview_watch_fire_label,
    read_provenance_corrections,
)
from tests.trades._cohort_provenance_fixtures import (
    SG_BASELINE_LABEL,
    SG_FIRE_CANDIDATE_ID,
    SG_FIRE_LABEL,
    SG_LAST_WORD_CANDIDATE_ID,
    SG_OLDER_CANDIDATE_ID,
    SG_TRADE_ID,
    SG_WATCH_MANUAL_ORIGIN,
    build_cadl_case,
    build_sg_case,
)

REASON = "D104: the SG fire was eval 193 (RD-witnessed)"


def _sg(tmp_path: Path, name: str = "sg", **case) -> sqlite3.Connection:
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    conn = ensure_schema(root / "swing.db", backup_dir=root / "bak")
    build_sg_case(conn, **case)
    conn.commit()
    return conn


def _trade_keys(conn: sqlite3.Connection) -> tuple:
    return conn.execute(
        "SELECT hypothesis_label, candidate_id, trade_origin, entry_intent "
        "FROM trades WHERE id = ?", (SG_TRADE_ID,)).fetchone()


def _row_count(conn: sqlite3.Connection) -> int:
    return conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0]


# ---------------------------------------------------------------------------
# 1a -- the SG case, applied
# ---------------------------------------------------------------------------
def test_1a_the_sg_fire_relabel_writes_the_witnessed_label(tmp_path) -> None:
    conn = _sg(tmp_path)
    result = correct_watch_fire_label(
        conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
        reason=REASON)
    # The label RD witnessed in the 2026-11-05 briefing -- spelled here, not
    # read off the fixture constant, so a fixture edit cannot carry it.
    witnessed = ("Near-A+ defensible: extension test (watch); "
                 "failed: proximity_20ma")
    assert witnessed == SG_FIRE_LABEL
    label, cid, origin, intent = _trade_keys(conn)
    assert (label, cid, origin) == (witnessed, 15901, "pipeline_watch_manual")
    assert intent == "hypothesis_test_by_design"
    assert result.already_applied is False
    assert result.correction_kind == PROVENANCE_CORRECTION_KIND_WATCH_FIRE
    assert result.admission_tier == PROVENANCE_ADMISSION_TIER_LAST_FIRE
    assert result.cited_daily_recommendation_id is None
    row = get_correction_for_trade(conn, SG_TRADE_ID)
    assert row.provenance_correction_id == result.correction_id
    assert row.correction_kind == "watch_fire_relabel"
    assert row.admission_tier == "last_fire"
    assert row.cited_candidate_id == 15901
    assert row.cited_evaluation_run_id == 193
    assert row.cited_pipeline_run_id == 207
    assert row.cited_hypothesis_id == 2
    assert row.cited_hypothesis_status_history_id == 6
    assert row.cited_run_ts_utc == "2026-11-05T03:30:04"
    assert row.cited_status_window_upper_utc == "2026-11-05T03:34:17"
    assert row.cited_daily_recommendation_id is None
    assert row.cited_recommendation_action_session_date is None
    assert row.cited_recommendation_snapshot_json is None
    assert row.cited_candidate_action_session_date == "2026-11-05"
    assert row.entry_fill_session_date == "2026-11-06"
    assert row.derivation_rule_version == DERIVATION_RULE_VERSION
    assert json.loads(row.corrected_fields_json) == list(
        PROVENANCE_WATCH_FIRE_CORRECTED_FIELDS)
    assert json.loads(row.pre_value_json) == {
        "trades.hypothesis_label": SG_BASELINE_LABEL,
        "trades.candidate_id": 15980,
        "trades.trade_origin": "pipeline_watch_manual",
    }
    assert json.loads(row.applied_value_json) == {
        "trades.hypothesis_label": witnessed,
        "trades.candidate_id": 15901,
        "trades.trade_origin": "pipeline_watch_manual",
    }
    assert row.correction_reason.startswith(REASON)
    assert "watch-fire relabel" in row.correction_reason
    assert not conn.in_transaction
    conn.close()


def test_1a_the_dry_run_shows_the_same_values_and_writes_nothing(
        tmp_path) -> None:
    """The dry run requires ``--reason`` exactly as the kind-1 dry run does:
    ONE authorization ladder, two entry points."""
    conn = _sg(tmp_path)
    with pytest.raises(CohortProvenanceCorrectionError, match="--reason"):
        preview_watch_fire_label(
            conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID)
    preview = preview_watch_fire_label(
        conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
        reason=REASON)
    assert preview.correction_kind == PROVENANCE_CORRECTION_KIND_WATCH_FIRE
    assert preview.admission_tier == "last_fire"
    assert preview.cited_daily_recommendation_id is None
    assert preview.recommendation_action_session_date is None
    assert preview.post_values["trades.hypothesis_label"] == SG_FIRE_LABEL
    assert preview.post_values["trades.candidate_id"] == 15901
    assert preview.pre_values["trades.candidate_id"] == 15980
    assert preview.cited_evaluation_run_id == 193
    assert preview.already_applied_correction_id is None
    assert _row_count(conn) == 0
    assert _trade_keys(conn)[:2] == (SG_BASELINE_LABEL, 15980)
    assert not conn.in_transaction
    conn.close()


# ---------------------------------------------------------------------------
# 1n -- refusals, each with its counterfactual
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("case,fragments", [
    ({"trade_origin": "manual_off_pipeline"},
     ("eligibility (a)", "manual_off_pipeline", "pipeline_watch_manual")),
    ({"entry_intent": "standard"},
     ("eligibility (b)", "'standard'", "fixes the LABEL, never the INTENT",
      "H5 practice")),
    ({"hypothesis_label": None}, ("eligibility (c)",)),
    ({"candidate_id": SG_OLDER_CANDIDATE_ID},
     ("eligibility (e)", "last-word", "15980")),
])
def test_1n_eligibility_refusals(tmp_path, case, fragments) -> None:
    conn = _sg(tmp_path, **case)
    before = _trade_keys(conn)
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        correct_watch_fire_label(
            conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
            reason=REASON)
    for fragment in fragments:
        assert fragment in str(exc.value), (fragment, str(exc.value))
    assert _row_count(conn) == 0
    assert _trade_keys(conn) == before
    conn.close()


def test_1n_a_null_candidate_is_refused_by_eligibility_d(tmp_path) -> None:
    conn = _sg(tmp_path, candidate_id=None)
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        correct_watch_fire_label(
            conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
            reason=REASON)
    assert "eligibility (d)" in str(exc.value)
    assert _row_count(conn) == 0
    assert _trade_keys(conn)[1] is None
    conn.close()


def test_1n_the_by_design_pair_runs_both_modes(tmp_path) -> None:
    """The SAME fixture, intent the only difference: standard refuses (b),
    by-design applies -- so the intent gate is what decides."""
    standard = _sg(tmp_path, "standard", entry_intent="standard")
    with pytest.raises(CohortProvenanceCorrectionError):
        correct_watch_fire_label(
            standard, trade_id=SG_TRADE_ID,
            fire_candidate_id=SG_FIRE_CANDIDATE_ID, reason=REASON)
    assert _row_count(standard) == 0
    standard.close()
    by_design = _sg(tmp_path, "by_design")
    correct_watch_fire_label(
        by_design, trade_id=SG_TRADE_ID,
        fire_candidate_id=SG_FIRE_CANDIDATE_ID, reason=REASON)
    assert _row_count(by_design) == 1
    by_design.close()


def test_1n_a_latched_trade_is_refused(tmp_path, monkeypatch) -> None:
    """The latch ladder is the authority for a latched fill. Seeding a whole
    accepted latch order is the 22-A suites' job; here the ladder's verdict
    is substituted at the ONE name the service resolves at call time, so
    the test pins what the relabel does WITH an admission."""
    conn = _sg(tmp_path)
    citation = cpc._LatchCitation(
        link_id=7, validity_intent_id=8, place_intent_id=9,
        broker_order_id="1008560562620", fire_candidate_id=15901,
        probe_json="{}")
    monkeypatch.setattr(cpc, "_resolve_latch_citation",
                        lambda *a, **k: citation)
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        correct_watch_fire_label(
            conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
            reason=REASON)
    assert "latch" in str(exc.value)
    assert "1008560562620" in str(exc.value)
    assert _row_count(conn) == 0
    assert _trade_keys(conn)[:2] == (SG_BASELINE_LABEL, 15980)
    conn.close()


def test_1n_citing_an_older_row_names_both_ids(tmp_path) -> None:
    conn = _sg(tmp_path)
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        correct_watch_fire_label(
            conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_OLDER_CANDIDATE_ID,
            reason=REASON)
    message = str(exc.value)
    assert "cited 15811" in message
    assert "the derived last fire is 15901" in message
    assert _row_count(conn) == 0
    assert _trade_keys(conn)[:2] == (SG_BASELINE_LABEL, 15980)
    conn.close()


def test_1n_no_single_match_row_in_the_window_refuses(tmp_path) -> None:
    """15901 planted with `tightness` failing too: every window row then has
    the batch-night shape and zero narrow matches."""
    conn = _sg(tmp_path, criteria_results={15901: {"tightness": "fail"}})
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        correct_watch_fire_label(
            conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
            reason=REASON)
    assert "exactly one narrow hypothesis match" in str(exc.value)
    assert _row_count(conn) == 0
    assert _trade_keys(conn)[:2] == (SG_BASELINE_LABEL, 15980)
    conn.close()


def test_1n_a_newer_ambiguous_row_is_refused_not_passed_over(
        tmp_path, monkeypatch) -> None:
    """E3. 15980 planted with the fire's criteria (it then matches H2), and
    a scratch capital-blocked rule matching that row too -- so the NEWEST
    window row matches TWO narrow hypotheses. It is refused, never passed
    over to reach 15901, and the message names the row, its run and the
    match set."""
    import swing.recommendations.hypothesis as hyp

    conn = _sg(tmp_path, criteria_results={15980: {"tightness": "pass"}})
    newest_close = 11.550000190734863
    monkeypatch.setattr(
        hyp, "_capital_blocked_match",
        lambda c: abs(float(c.close) - newest_close) < 1e-9)
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        correct_watch_fire_label(
            conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
            reason=REASON)
    message = str(exc.value)
    assert "AMBIGUOUS" in message
    assert "candidate 15980" in message and "evaluation run 194" in message
    assert "Near-A+ defensible: extension test" in message
    assert _row_count(conn) == 0
    assert _trade_keys(conn)[:2] == (SG_BASELINE_LABEL, 15980)
    conn.close()


def test_1n_an_older_unreadable_row_does_not_block_the_derivation(
        tmp_path) -> None:
    """CHARC's plan-stage amendment: 15811 (eval 192) has no pipeline bound,
    so its as-of registry cannot be built -- but it is OLDER than the
    derived fire, so the walk never reads it."""
    conn = _sg(tmp_path, pipeline_complete={192: False})
    correct_watch_fire_label(
        conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
        reason=REASON)
    assert _trade_keys(conn)[:2] == (SG_FIRE_LABEL, 15901)
    conn.close()


def test_1n_a_newer_unreadable_row_refuses(tmp_path) -> None:
    conn = _sg(tmp_path, pipeline_complete={194: False})
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        correct_watch_fire_label(
            conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
            reason=REASON)
    message = str(exc.value)
    assert "candidate 15980" in message
    assert "cannot be passed over" in message
    assert "no single COMPLETE pipeline_runs row" in message
    assert _row_count(conn) == 0
    assert _trade_keys(conn)[:2] == (SG_BASELINE_LABEL, 15980)
    conn.close()


def test_1n_an_aplus_citation_is_refused_at_the_fire_anchor(tmp_path) -> None:
    conn = _sg(tmp_path, buckets={15901: "aplus"})
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        correct_watch_fire_label(
            conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
            reason=REASON)
    assert "bucket 'aplus', not 'watch'" in str(exc.value)
    assert _row_count(conn) == 0
    conn.close()


def test_1n_a_non_int_fire_candidate_is_a_typed_refusal(tmp_path) -> None:
    conn = _sg(tmp_path)
    for bad in (True, "15901", 15901.0, None):
        with pytest.raises(CohortProvenanceCorrectionError):
            correct_watch_fire_label(
                conn, trade_id=SG_TRADE_ID, fire_candidate_id=bad,
                reason=REASON)
    assert _row_count(conn) == 0
    conn.close()


def test_1n_replay_is_already_applied_even_with_no_reason(tmp_path) -> None:
    conn = _sg(tmp_path)
    first = correct_watch_fire_label(
        conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
        reason=REASON)
    again = correct_watch_fire_label(
        conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
        reason=None)
    assert again.already_applied is True
    assert again.correction_id == first.correction_id
    assert again.correction_kind == PROVENANCE_CORRECTION_KIND_WATCH_FIRE
    assert again.cited_daily_recommendation_id is None
    preview = preview_watch_fire_label(
        conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID)
    assert preview.already_applied_correction_id == first.correction_id
    assert preview.cited_daily_recommendation_id is None
    assert _row_count(conn) == 1
    # A DIFFERENT fire on the already-corrected trade is refused by name.
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        correct_watch_fire_label(
            conn, trade_id=SG_TRADE_ID,
            fire_candidate_id=SG_OLDER_CANDIDATE_ID, reason=REASON)
    assert "watch_fire_relabel" in str(exc.value)
    assert _row_count(conn) == 1
    conn.close()


def test_1n_a_kind1_call_on_a_kind2_trade_refuses_by_message(
        tmp_path) -> None:
    """The mirror-closure item at `_authorize`: the existing row's
    recommendation id is NULL on a kind-2 row, and the kind-1 replay
    comparison used to `int()` it -- a TypeError, not a refusal."""
    conn = _sg(tmp_path)
    correct_watch_fire_label(
        conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
        reason=REASON)
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        correct_cohort_provenance(
            conn, trade_id=SG_TRADE_ID, cited_candidate_id=15901,
            cited_recommendation_id=1, reason=REASON)
    assert "watch_fire_relabel" in str(exc.value)
    assert _row_count(conn) == 1
    conn.close()


def test_1n_a_kind2_call_on_a_kind1_trade_refuses_by_message(
        tmp_path) -> None:
    root = tmp_path / "cadl"
    root.mkdir()
    conn = ensure_schema(root / "swing.db", backup_dir=root / "bak")
    ids = build_cadl_case(conn)
    conn.commit()
    correct_cohort_provenance(
        conn, trade_id=ids["trade_id"], cited_candidate_id=ids["candidate_id"],
        cited_recommendation_id=ids["daily_recommendation_id"], reason=REASON)
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        correct_watch_fire_label(
            conn, trade_id=ids["trade_id"],
            fire_candidate_id=ids["candidate_id"], reason=REASON)
    assert PROVENANCE_CORRECTION_KIND_FILL_UNSET in str(exc.value)
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 1
    conn.close()


def test_1n_an_empty_reason_is_refused_after_eligibility(tmp_path) -> None:
    conn = _sg(tmp_path)
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        correct_watch_fire_label(
            conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
            reason="  ")
    assert "--reason" in str(exc.value)
    assert _row_count(conn) == 0
    conn.close()


# ---------------------------------------------------------------------------
# 1o -- the transaction contract
# ---------------------------------------------------------------------------
def test_1o_a_caller_held_transaction_is_rejected(tmp_path) -> None:
    conn = _sg(tmp_path)
    conn.execute("BEGIN")
    with pytest.raises(CallerHeldTransactionError):
        correct_watch_fire_label(
            conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
            reason=REASON)
    conn.rollback()
    assert _row_count(conn) == 0
    conn.close()


def test_1o_a_failure_after_the_trade_update_rolls_back_both(
        tmp_path, monkeypatch) -> None:
    import swing.data.repos.provenance_corrections as repo

    conn = _sg(tmp_path)

    def boom(*_a, **_k):
        raise RuntimeError("insert failed after the trade UPDATE")

    monkeypatch.setattr(repo, "insert_provenance_correction", boom)
    with pytest.raises(RuntimeError):
        correct_watch_fire_label(
            conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
            reason=REASON)
    assert not conn.in_transaction
    assert _row_count(conn) == 0
    assert _trade_keys(conn)[:2] == (SG_BASELINE_LABEL, 15980)
    conn.close()


# ---------------------------------------------------------------------------
# 1p -- the reader
# ---------------------------------------------------------------------------
def test_1p_a_kind2_row_reads_clean(tmp_path) -> None:
    conn = _sg(tmp_path)
    correct_watch_fire_label(
        conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
        reason=REASON)
    (report,) = read_provenance_corrections(conn, trade_id=SG_TRADE_ID)
    assert report.correction.correction_kind == "watch_fire_relabel"
    assert report.drift_lines == ()
    conn.close()


def _plant_criterion(conn, candidate_id: int, name: str, **cols) -> None:
    """Guard-seam kind 1: plant a HISTORICAL rewrite of a criteria row the
    schema now forbids, to test the reader's DETECTION of it."""
    from tests._22i_guard_seam import guards_dropped

    sets = ", ".join(f"{k} = ?" for k in cols)
    with guards_dropped(conn, "trg_cc_no_update"):
        conn.execute(
            f"UPDATE candidate_criteria SET {sets} "
            "WHERE candidate_id = ? AND criterion_name = ?",
            (*cols.values(), candidate_id, name))
    conn.commit()


def test_1p_a_moved_cited_criterion_reports_citation_drift(tmp_path) -> None:
    conn = _sg(tmp_path)
    correct_watch_fire_label(
        conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
        reason=REASON)
    _plant_criterion(conn, SG_FIRE_CANDIDATE_ID, "adr", value="9.99%")
    (report,) = read_provenance_corrections(conn, trade_id=SG_TRADE_ID)
    assert any(line.startswith(f"{CITATION_DRIFT}: candidates.criteria")
               for line in report.drift_lines), report.drift_lines
    conn.close()


def test_1p_a_newer_row_becoming_the_last_fire_reports_drift(
        tmp_path) -> None:
    """The kind-2 re-derivation includes the last-fire RANKING: 15980 is
    re-planted with the fire's criteria, so it becomes the newest single
    match and the cited 15901 is no longer the last fire."""
    conn = _sg(tmp_path)
    correct_watch_fire_label(
        conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
        reason=REASON)
    _plant_criterion(conn, SG_LAST_WORD_CANDIDATE_ID, "tightness",
                     result="pass")
    (report,) = read_provenance_corrections(conn, trade_id=SG_TRADE_ID)
    assert any("last fire" in line and "15980" in line
               and line.startswith(CITATION_DRIFT)
               for line in report.drift_lines), report.drift_lines
    conn.close()


# ---------------------------------------------------------------------------
# 1r -- the fill against the pivot is RECORDED, never a gate
# ---------------------------------------------------------------------------
@pytest.mark.parametrize("fill_price", [11.95, 12.60])
def test_1r_the_gap_is_recorded_not_refused(tmp_path, fill_price) -> None:
    conn = _sg(tmp_path, fill_price=fill_price)
    correct_watch_fire_label(
        conn, trade_id=SG_TRADE_ID, fire_candidate_id=SG_FIRE_CANDIDATE_ID,
        reason=REASON)
    row = get_correction_for_trade(conn, SG_TRADE_ID)
    assert json.loads(row.entry_fill_snapshot_json)["price"] == fill_price
    pivot = conn.execute(
        "SELECT pivot FROM candidates WHERE id = ?",
        (row.cited_candidate_id,)).fetchone()[0]
    assert round(pivot, 3) == 11.949
    assert _trade_keys(conn)[2] == SG_WATCH_MANUAL_ORIGIN
    conn.close()


# ---------------------------------------------------------------------------
# F9 = A -- the kind-2 decision is inside the derivation pin
# ---------------------------------------------------------------------------
def test_the_kind2_closure_is_fully_accounted_for() -> None:
    """A SECOND root for the closure check: ``_derive_watch_fire`` decides
    which row a kind-2 correction cites, and kind 2 writes the head version,
    so everything it reaches is manifested or excluded with a reason --
    the same check `_derive` gets."""
    from swing.trades.cohort_provenance_correction import (
        DERIVATION_RULE_DEPENDENCIES,
    )
    from tests.trades.test_cohort_provenance_derivation import (
        DERIVATION_CLOSURE_EXCLUSIONS,
        _derivation_closure,
    )

    root = "swing.trades.cohort_provenance_correction:_derive_watch_fire"
    manifested = {spec for _kind, spec in DERIVATION_RULE_DEPENDENCIES}
    closure = _derivation_closure(root)
    assert "swing.trades.cohort_provenance_correction:_derive_last_fire" in (
        closure)
    assert ("swing.recommendations.hypothesis_prefill:WATCH_FIRE_WINDOW_ROWS"
            in closure)
    unaccounted = sorted(
        closure - manifested - set(DERIVATION_CLOSURE_EXCLUSIONS))
    assert not unaccounted, unaccounted


def test_the_window_constant_is_the_one_the_prefill_owns() -> None:
    """ONE N for T2's offer and T1's walk (N = 5, ruled)."""
    from swing.recommendations import hypothesis_prefill

    assert hypothesis_prefill.WATCH_FIRE_WINDOW_ROWS == 5
    import inspect

    src = inspect.getsource(cpc._derive_last_fire)
    assert "WATCH_FIRE_WINDOW_ROWS" in src
