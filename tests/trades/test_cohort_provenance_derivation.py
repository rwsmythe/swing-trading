"""Task 6 -- value derivation: the AS-OF registry, the matcher, label, origin.

The registry `status` is MUTABLE, and `match_candidate_to_hypotheses` filters
on it -- so passing today's `list_hypotheses(conn)` would make the derived
hypothesis a function of PRESENT-DAY state, which is what the binding rule
forbids one level up from the values themselves. The failure is
two-directional and both directions are wrong, so both are tested.
"""
from __future__ import annotations

import inspect
import pathlib
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.metrics.funnel import APLUS_TRADE_ORIGIN
from swing.metrics.label_match import label_matches_hypothesis
from swing.trades.cohort_provenance_correction import (
    DERIVATION_RULE_SOURCE_SHA256,
    DERIVATION_RULE_VERSION,
    CohortProvenanceCorrectionError,
    preview_cohort_provenance_correction,
)
from tests.trades._cohort_provenance_fixtures import (
    CADL_LABEL,
    CADL_PIPELINE_FINISHED_LOCAL,
    CADL_RUN_TS_LOCAL,
    CLEAN_APLUS_LABEL,
    H1_ID,
    H1_NAME,
    build_cadl_case,
    seed_pipeline_run,
)

REASON = "the framework's own contemporaneous record"
RUN_TS_UTC = "2026-08-11T03:30:26"
UPPER_UTC = "2026-08-11T03:44:45"


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = ensure_schema(tmp_path / "swing.db")
    try:
        yield c
    finally:
        c.close()


def _preview(conn, ids):
    return preview_cohort_provenance_correction(
        conn,
        trade_id=ids["trade_id"],
        cited_candidate_id=ids["candidate_id"],
        cited_recommendation_id=ids["daily_recommendation_id"],
        reason=REASON,
    )


def _set_history(conn, hypothesis_id, rows) -> None:
    """Replace one hypothesis's history with `(status, from, to, recorded)`."""
    conn.execute(
        "DELETE FROM hypothesis_status_history WHERE hypothesis_id = ?",
        (hypothesis_id,))
    for status, eff_from, eff_to, recorded in rows:
        conn.execute(
            "INSERT INTO hypothesis_status_history (hypothesis_id, status, "
            "effective_from, effective_to, change_reason, recorded_at) "
            "VALUES (?, ?, ?, ?, NULL, ?)",
            (hypothesis_id, status, eff_from, eff_to, recorded))


# ------------------------------------------------------------ the label itself


def test_the_derived_label_is_the_FAITHFUL_string_with_its_suffix(conn) -> None:
    """RD-ruled: candidate 12341 carries `TT8_rs_rank='na'` and
    `_non_pass_criterion_names` counts `na` as non-pass, so the suffix is TRUE
    of the CITED candidate. The clean sibling string is NOT wanted -- reading
    it off trades 17/18 would be reading the label off SIBLING TRADES, the
    composition the evidence rule forbids."""
    ids = build_cadl_case(conn)
    p = _preview(conn, ids)
    assert p.post_values["trades.hypothesis_label"] == CADL_LABEL
    assert p.post_values["trades.candidate_id"] == ids["candidate_id"]
    assert p.post_values["trades.trade_origin"] == APLUS_TRADE_ORIGIN


def test_the_suffix_is_a_function_of_the_record_not_a_constant(conn) -> None:
    """An all-`pass` candidate produces the clean string, so the suffix cannot
    be a hard-coded decoration."""
    ids = build_cadl_case(conn, non_pass={}, ticker="VSTS")
    p = _preview(conn, ids)
    assert p.post_values["trades.hypothesis_label"] == CLEAN_APLUS_LABEL


def test_the_na_suffix_is_NAMED_in_the_preview_not_hidden(conn) -> None:
    ids = build_cadl_case(conn)
    p = _preview(conn, ids)
    assert p.na_criterion_suffix_note is not None
    assert "TT8_rs_rank" in p.na_criterion_suffix_note
    assert "`na`" in p.na_criterion_suffix_note
    clean = build_cadl_case(conn, non_pass={}, ticker="VSTS")
    assert _preview(conn, clean).na_criterion_suffix_note is None


def test_the_written_label_satisfies_the_cohort_join_predicate(conn) -> None:
    """The property the cohort read actually depends on, asserted SEPARATELY
    from the exact string -- so a future `_descriptive_label` change breaks
    the string test loudly instead of breaking cohort membership silently."""
    ids = build_cadl_case(conn)
    p = _preview(conn, ids)
    label = p.post_values["trades.hypothesis_label"]
    assert label_matches_hypothesis(label, H1_NAME)
    registry_name = conn.execute(
        "SELECT name FROM hypothesis_registry WHERE id = ?",
        (p.cited_hypothesis_id,)).fetchone()[0]
    assert p.cited_hypothesis_name == registry_name
    assert label_matches_hypothesis(label, registry_name)


def test_the_origin_literal_is_imported_not_a_third_copy() -> None:
    """`APLUS_TRADE_ORIGIN` is the EXISTING constant; asserting object
    identity is what stops a third spelling of `pipeline_aplus`."""
    from swing.trades import cohort_provenance_correction as svc
    src = inspect.getsource(svc)
    assert "APLUS_TRADE_ORIGIN" in src
    assert '"pipeline_aplus"' not in src and "'pipeline_aplus'" not in src


def test_origin_mapping_does_not_drift_from_derive_trade_origin(conn) -> None:
    """For EVERY EntryPath member, `derive_trade_origin` on a DB whose latest
    complete run holds an `aplus` row returns the same literal this surface
    writes -- so the two mappings cannot drift apart silently."""
    from swing.trades.origin import EntryPath, derive_trade_origin

    ids = build_cadl_case(conn)
    conn.commit()
    for path in EntryPath:
        assert derive_trade_origin(conn, "CADL", path) == APLUS_TRADE_ORIGIN
    assert _preview(conn, ids).post_values[
        "trades.trade_origin"] == APLUS_TRADE_ORIGIN


def test_derivation_rule_version_is_pinned_to_the_source_sha(conn) -> None:
    """A pin, not a promise. `_descriptive_label`'s own docstring invites the
    drift ("the descriptive suffix may evolve"), so a version constant that is
    "bumped by hand" is gotcha #31. Changing either function fails HERE until
    the hash and the version move in the same commit."""
    from swing.trades.cohort_provenance_correction import (
        derivation_rule_digest,
    )

    # THE ENUMERATED DEPENDENCY MANIFEST, not a function list. Hashing function
    # SOURCE cannot see a value the source merely NAMES, so `H_APLUS_BASELINE`
    # could be re-spelled -- selecting a different registry row -- without
    # moving a source-only digest by one bit.
    digest = derivation_rule_digest()
    assert digest == DERIVATION_RULE_SOURCE_SHA256, (
        "swing.recommendations.hypothesis._descriptive_label or "
        "_non_pass_criterion_names changed. BUMP DERIVATION_RULE_VERSION "
        f"(currently {DERIVATION_RULE_VERSION!r}) AND update "
        "DERIVATION_RULE_SOURCE_SHA256 in the SAME commit, or two corrections "
        "will claim one derivation version while using different rules."
    )


# ------------------------------------------------------- the as-of registry


def test_paused_over_the_window_but_active_today_REFUSES(conn) -> None:
    """The whole point of the as-of fix. An implementation passing
    `list_hypotheses(conn)` straight through sees `status='active'` (today's
    value) and ACCEPTS."""
    ids = build_cadl_case(conn)
    _set_history(conn, H1_ID, [
        ("active", "2026-04-25T00:00:00.000", "2026-06-01T00:00:00.000",
         "2026-04-25T00:00:00.000"),
        ("paused", "2026-06-01T00:00:00.000", None,
         "2026-06-01T00:00:00.000"),
    ])
    assert conn.execute(
        "SELECT status FROM hypothesis_registry WHERE id = 1",
    ).fetchone()[0] == "active"  # today's mutable value says active
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert "matcher returned 0 hypothesis matches" in str(exc.value)


def test_active_over_the_window_but_CLOSED_today_ACCEPTS(conn) -> None:
    """The other direction: an implementation reading today's status REFUSES
    a correction the record itself authorizes."""
    ids = build_cadl_case(conn)
    _set_history(conn, H1_ID, [
        ("active", "2026-04-25T00:00:00.000", "2026-08-20T00:00:00.000",
         "2026-04-25T00:00:00.000"),
        ("closed-target-met", "2026-08-20T00:00:00.000", None,
         "2026-08-20T00:00:00.000"),
    ])
    conn.execute(
        "UPDATE hypothesis_registry SET status = 'closed-target-met' "
        "WHERE id = 1")
    p = _preview(conn, ids)
    assert p.cited_hypothesis_id == H1_ID
    interval_status = conn.execute(
        "SELECT status FROM hypothesis_status_history WHERE history_id = ?",
        (p.cited_hypothesis_status_history_id,)).fetchone()[0]
    assert interval_status == "active"


def test_a_mid_window_transition_REFUSES_with_its_own_message(conn) -> None:
    """Built the way the PRODUCTION writer builds one: close the predecessor,
    then insert the successor, both at the same instant `t`, with
    `run_ts < t < finished_ts`. That yields two ADJACENT half-open intervals
    NEITHER of which covers the window -- so a rule counting only COVERING
    intervals gets ZERO, not two, and would silently EXCLUDE the hypothesis
    instead of refusing. The assertion is on the SPECIFIC message, because a
    generic refusal assertion would pass through the absence branch and prove
    nothing."""
    ids = build_cadl_case(conn)
    t = "2026-08-11T03:35:00.000"  # inside [03:30:26, 03:44:45] UTC
    _set_history(conn, H1_ID, [
        ("active", "2026-04-25T00:00:00.000", t, "2026-04-25T00:00:00.000"),
        ("paused", t, None, "2026-04-25T00:00:00.000"),
    ])
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    msg = str(exc.value)
    assert "CHANGED INSIDE the window" in msg
    assert "2 intersecting interval(s)" in msg


def test_a_gap_over_the_window_REFUSES_with_a_DISTINCT_message(conn) -> None:
    ids = build_cadl_case(conn)
    _set_history(conn, H1_ID, [
        ("active", "2026-04-25T00:00:00.000", "2026-05-01T00:00:00.000",
         "2026-04-25T00:00:00.000"),
    ])
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    msg = str(exc.value)
    assert "has a GAP over the window" in msg
    assert "CHANGED INSIDE" not in msg


def test_a_hypothesis_whose_history_POSTDATES_the_window_is_EXCLUDED(
    conn,
) -> None:
    """H5's real shape: migration 0026 created it on 2026-06-09, so a cited
    record from May must still succeed with H5 merely absent from the as-of
    registry. Refusing on absence would make every citation older than an
    unrelated FUTURE hypothesis uncorrectable."""
    ids = build_cadl_case(
        conn,
        data_asof_date="2026-05-04",
        action_session_date="2026-05-05",
        run_ts="2026-05-04T17:30:26",
        pipeline_finished_ts="2026-05-04T17:44:45",
        fill_datetime="2026-05-05T16:00:00",
        entry_date="2026-05-05",
    )
    _set_history(conn, 5, [
        ("active", "2026-06-09T00:00:00.000", None,
         "2026-06-09T00:00:00.000"),
    ])
    p = _preview(conn, ids)
    assert p.cited_hypothesis_id == H1_ID


def test_a_hypothesis_with_no_history_rows_at_all_REFUSES(conn) -> None:
    ids = build_cadl_case(conn)
    conn.execute("DELETE FROM hypothesis_status_history WHERE hypothesis_id=3")
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert "NO status-history rows at all" in str(exc.value)


# ------------------------------------------------------------ retrospective


def test_a_retrospective_interval_REFUSES_and_names_0017(conn) -> None:
    """Migration 0017's real seed shape: `effective_from` backdated to the
    registry's created_at, `recorded_at` = migration apply time. Disclosure is
    not authorization."""
    ids = build_cadl_case(conn, contemporaneous_history=False)
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    msg = str(exc.value)
    assert "RETROSPECTIVE assertion" in msg
    assert "0017" in msg


def test_a_contemporaneous_interval_ACCEPTS(conn) -> None:
    """Both directions asserted -- a refusal-only pair proves nothing about
    which side of the comparison the code is on."""
    ids = build_cadl_case(conn, contemporaneous_history=True)
    assert _preview(conn, ids).cited_hypothesis_id == H1_ID


def test_an_empty_recorded_at_is_REFUSED_not_lexically_accepted(conn) -> None:
    """`recorded_at=''` sorts before EVERY valid run_ts and satisfies the
    retrospective guard lexically, while being a recording time nobody can
    know. It is decisive precisely because it was the newest column, and it
    was the one omission from the first validation manifest."""
    ids = build_cadl_case(conn)
    conn.execute(
        "UPDATE hypothesis_status_history SET recorded_at = '' "
        "WHERE hypothesis_id = 1")
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert "recorded_at" in str(exc.value)


@pytest.mark.parametrize("bad", ["20260425T000000", "2026-04-25T00:00:00Z"])
def test_a_basic_or_offset_recorded_at_is_refused(conn, bad) -> None:
    ids = build_cadl_case(conn)
    conn.execute(
        "UPDATE hypothesis_status_history SET recorded_at = ? "
        "WHERE hypothesis_id = 1", (bad,))
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert "recorded_at" in str(exc.value)


def test_a_malformed_interval_that_OVERLAPS_is_refused(conn) -> None:
    """The selection-rule discriminator for intervals: a valid covering
    interval PLUS a malformed basic-form interval that genuinely overlaps the
    window. A lexical SQL `WHERE` excludes the malformed one and the guard
    then sees ONE covering interval and ACCEPTS."""
    ids = build_cadl_case(conn)
    # The valid interval keeps the single open slot (the partial-unique index
    # `ux_hypothesis_status_history_current` permits exactly one per
    # hypothesis); the malformed one is closed, written in basic form on BOTH
    # bounds so it hydrates cleanly, and genuinely overlaps the window.
    _set_history(conn, H1_ID, [
        ("active", "2026-04-25T00:00:00.000", None,
         "2026-04-25T00:00:00.000"),
        ("paused", "20260811T033500", "20260812T000000",
         "2026-04-25T00:00:00.000"),
    ])
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert "effective_from" in str(exc.value)


def test_a_bound_that_breaks_MODEL_hydration_is_a_typed_refusal(conn) -> None:
    """`HypothesisStatusHistory.__post_init__` compares the two bounds
    LEXICALLY, so a mixed basic/extended pair makes the READER raise while
    hydrating. Left bare that escapes as an untyped ValueError with no
    'Nothing was written' and no hypothesis named -- a refusal the operator
    cannot act on."""
    ids = build_cadl_case(conn)
    _set_history(conn, H1_ID, [
        ("active", "2026-04-25T00:00:00.000", None,
         "2026-04-25T00:00:00.000"),
        ("paused", "20260811T033500", "2026-08-12T00:00:00.000",
         "2026-04-25T00:00:00.000"),
    ])
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    msg = str(exc.value)
    assert f"hypothesis {H1_ID}'s status history could not be read" in msg
    assert msg.endswith("Nothing was written.")


# ----------------------------------------------------- the window + the clock


def test_the_window_is_a_WINDOW_not_an_instant(conn) -> None:
    """A status flip strictly BETWEEN run_ts and pipeline finished_ts. An
    instant-only implementation reading run_ts alone ACCEPTS."""
    ids = build_cadl_case(conn)
    _set_history(conn, H1_ID, [
        ("active", "2026-04-25T00:00:00.000", "2026-08-11T03:40:00.000",
         "2026-04-25T00:00:00.000"),
        ("paused", "2026-08-11T03:40:00.000", None,
         "2026-04-25T00:00:00.000"),
    ])
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert "CHANGED INSIDE the window" in str(exc.value)


def test_the_clock_domains_are_normalized_before_comparison(conn) -> None:
    """The production-shaped case: the pipeline window is naive LOCAL
    (17:30:26 -> 17:44:45 HST) and the status transition is naive UTC
    (2026-08-11T03:35:00.000). A TEXT-comparing implementation sees the old
    interval covering the whole textual window and ACCEPTS, because
    '2026-08-11T03:35:00.000' is not between '2026-08-10T17:30:26' and
    '2026-08-10T17:44:45'."""
    assert not ("2026-08-10T17:30:26" <= "2026-08-11T03:35:00.000"
                <= "2026-08-10T17:44:45")
    ids = build_cadl_case(conn)
    _set_history(conn, H1_ID, [
        ("active", "2026-04-25T00:00:00.000", "2026-08-11T03:35:00.000",
         "2026-04-25T00:00:00.000"),
        ("paused", "2026-08-11T03:35:00.000", None,
         "2026-04-25T00:00:00.000"),
    ])
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert "CHANGED INSIDE the window" in str(exc.value)


def test_an_interval_boundary_12_hours_away_REFUSES_on_the_margin(conn) -> None:
    ids = build_cadl_case(conn)
    _set_history(conn, H1_ID, [
        ("active", "2026-08-10T15:35:00.000", None,
         "2026-04-25T00:00:00.000"),
    ])
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    msg = str(exc.value)
    assert "within 24 hours of the" in msg
    assert "naive LOCAL" in msg


def test_the_live_107_day_distance_does_NOT_trip_the_margin(conn) -> None:
    ids = build_cadl_case(conn)
    p = _preview(conn, ids)
    assert p.cited_hypothesis_id == H1_ID


def test_the_stored_window_bounds_are_normalized_POSITIVELY(conn) -> None:
    """The margin refusal fires whether or not the bounds were converted, so a
    refusal-only suite passes an implementation that never normalized. On the
    ACCEPTING case the exact values are asserted, and the DATE ROLLS."""
    ids = build_cadl_case(conn)
    p = _preview(conn, ids)
    assert p.run_ts_raw == CADL_RUN_TS_LOCAL == "2026-08-10T17:30:26"
    assert p.run_ts_utc == RUN_TS_UTC == "2026-08-11T03:30:26"
    assert p.pipeline_finished_ts_raw == CADL_PIPELINE_FINISHED_LOCAL
    assert p.status_window_upper_utc == UPPER_UTC == "2026-08-11T03:44:45"
    assert p.run_ts_utc != p.run_ts_raw
    assert p.status_window_upper_utc != p.pipeline_finished_ts_raw
    assert p.run_ts_utc[:10] != p.run_ts_raw[:10]  # midnight crossed


# ------------------------------------------------------ the persistence bound


def test_zero_two_or_incomplete_pipeline_rows_REFUSE(conn) -> None:
    none_ids = build_cadl_case(conn, pipeline_rows=0)
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, none_ids)
    assert "UNBOUNDED ABOVE" in str(exc.value)

    two = build_cadl_case(conn, pipeline_rows=2, ticker="TWO")
    with pytest.raises(CohortProvenanceCorrectionError):
        _preview(conn, two)

    running = build_cadl_case(
        conn, ticker="RUN", pipeline_state="running",
        pipeline_finished_ts=None)
    with pytest.raises(CohortProvenanceCorrectionError):
        _preview(conn, running)


def test_a_pipeline_row_owning_a_DIFFERENT_run_does_not_bound_this_one(
    conn,
) -> None:
    """`pipeline_runs.evaluation_run_id` is a NULLABLE, NON-UNIQUE FK, so
    ownership must be established rather than assumed."""
    ids = build_cadl_case(conn, pipeline_rows=0)
    other = build_cadl_case(conn, ticker="OTH")
    seed_pipeline_run(
        conn, evaluation_run_id=other["evaluation_run_id"],
        data_asof_date="2026-08-10", action_session_date="2026-08-11")
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert "UNBOUNDED ABOVE" in str(exc.value)


def test_an_inverted_window_is_refused(conn) -> None:
    ids = build_cadl_case(conn, pipeline_finished_ts="2026-08-10T17:00:00")
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert "inverted" in str(exc.value)


def test_a_malformed_pipeline_finished_ts_is_refused(conn) -> None:
    ids = build_cadl_case(conn)
    conn.execute(
        "UPDATE pipeline_runs SET finished_ts = 'garbage' WHERE id = ?",
        (ids["pipeline_run_id"],))
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert "finished_ts" in str(exc.value)


def test_R2m6_a_new_digest_cannot_reuse_an_existing_version() -> None:
    """A lone constant plus a lone digest let a maintainer change the builder
    and update ONLY the digest: the sha test goes green while two different
    rules claim one audit version -- the exact failure the pin exists to
    prevent. The history makes a new digest require a new version."""
    from swing.trades.cohort_provenance_correction import (
        DERIVATION_RULE_HISTORY,
    )

    versions = [v for v, _d in DERIVATION_RULE_HISTORY]
    digests = [d for _v, d in DERIVATION_RULE_HISTORY]
    assert len(set(versions)) == len(versions), (
        "two entries claim the same DERIVATION_RULE_VERSION")
    assert len(set(digests)) == len(digests), (
        "two entries claim the same source digest")
    assert DERIVATION_RULE_VERSION == versions[-1]
    assert DERIVATION_RULE_SOURCE_SHA256 == digests[-1]
    for version, digest in DERIVATION_RULE_HISTORY:
        assert version.strip() and len(digest) == 64
        assert all(ch in "0123456789abcdef" for ch in digest)


def test_R5M4_a_CONSTANT_only_change_moves_the_digest() -> None:
    """The pin's SHAPE, not its coverage. Hashing function SOURCE cannot see a
    value the source merely NAMES: `H_APLUS_BASELINE` could be re-spelled --
    selecting a different registry row and changing every stored label -- and a
    source-only digest would not move by one bit. Mutating the constant here
    proves the manifest sees it."""
    import swing.recommendations.hypothesis as hyp
    from swing.trades.cohort_provenance_correction import (
        derivation_rule_digest,
    )

    before = derivation_rule_digest()
    original = hyp.H_APLUS_BASELINE
    try:
        hyp.H_APLUS_BASELINE = "A+ baseline (renamed)"
        assert derivation_rule_digest() != before, (
            "a constant-only rule change did not move the digest -- the "
            "manifest is not seeing its own dependencies")
    finally:
        hyp.H_APLUS_BASELINE = original
    assert derivation_rule_digest() == before


def test_R5M4_the_digest_is_STABLE_across_processes() -> None:
    """`repr(frozenset)` follows SET ITERATION ORDER, which for str elements
    depends on PYTHONHASHSEED -- so a repr-based digest differed across
    subprocesses and would have been a FLAKY pin: green locally, red
    intermittently, and the fix a maintainer reaches for under that pressure
    is to weaken the assertion. Run in fresh interpreters, because a
    same-process check cannot see hash randomization at all."""
    import subprocess
    import sys

    code = ("from swing.trades.cohort_provenance_correction import "
            "derivation_rule_digest as d; print(d())")
    seen = {
        subprocess.run(
            [sys.executable, "-c", code], capture_output=True, text=True,
            cwd=str(pathlib.Path(__file__).resolve().parents[2]),
        ).stdout.strip()
        for _ in range(4)
    }
    assert len(seen) == 1, f"digest is not process-stable: {seen}"
    assert seen == {DERIVATION_RULE_SOURCE_SHA256}


def test_R5M4_the_manifest_covers_the_constants_the_rule_reads() -> None:
    """A roster is only as good as its membership, so the members are READ."""
    from swing.trades.cohort_provenance_correction import (
        DERIVATION_RULE_DEPENDENCIES,
    )

    specs = {spec for _kind, spec in DERIVATION_RULE_DEPENDENCIES}
    for required in (
        "swing.recommendations.hypothesis:_descriptive_label",
        "swing.recommendations.hypothesis:_non_pass_criterion_names",
        "swing.recommendations.hypothesis:match_candidate_to_hypotheses",
        "swing.trades.entry:canonicalize_hypothesis_label",
        "swing.recommendations.hypothesis:H_APLUS_BASELINE",
        "swing.recommendations.hypothesis:DOCTRINE_DEFENSIBLE_MISS_SET",
        "swing.metrics.funnel:APLUS_TRADE_ORIGIN",
    ):
        assert required in specs, required
    kinds = {kind for kind, _spec in DERIVATION_RULE_DEPENDENCIES}
    assert kinds == {"function", "constant"}
