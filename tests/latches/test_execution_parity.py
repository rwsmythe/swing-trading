"""Telemetry health (B5) + the away rate + the parity report - PURE (Task 5).

THE BUCKET PARTITION IS OVER CELLS, NOT OVER DISPOSITIONS. Since the terminality
gate landed, a disposition no longer HAS one bucket: `accepted` is `decision_r`
when terminal and `pending_r` when not. A test phrased as "every member of
LATCH_DISPOSITIONS appears in exactly one of the five sets" is therefore either
FALSE or silently testing the PRE-GATE model, and is FORBIDDEN here.
"""
from __future__ import annotations

from datetime import date, timedelta

import pytest

from swing.latches.classification import (
    DECISION_SUBKIND,
    CoverageVerdict,
    LatchDisposition,
    ParityObservation,
    TelemetryHealth,
    assess_telemetry_health,
    compute_away_rate,
    compute_execution_parity,
    r_bucket_for,
)
from swing.latches.constants import (
    ATTESTED_AWAY_DISPOSITIONS,
    AWAY_RATE_COUNTED_DISPOSITIONS,
    DECISION_DISPOSITIONS,
    LATCH_DISPOSITIONS,
    LATCH_TELEMETRY_DARK_SESSIONS_THRESHOLD,
    LATCH_TELEMETRY_EPOCH_SESSION,
    PENDING_DISPOSITIONS,
    R_BUCKETS,
    UNATTRIBUTABLE_DISPOSITIONS,
    _RULED_DISPOSITIONS,
)
from swing.latches.identity import LatchIdentity
from swing.latches.models import Latch

EPOCH = LATCH_TELEMETRY_EPOCH_SESSION
THRESHOLD = LATCH_TELEMETRY_DARK_SESSIONS_THRESHOLD
_OK = TelemetryHealth(verdict="ok", covered_sessions=5)
_COV = CoverageVerdict(
    coverage="full", observation_recorded=True,
    table_disposition="__classify_normally__",
    covered_from=EPOCH, covered_through=EPOCH)


def _disp(disposition: str, *, is_terminal: bool = True, candidate_id: int = 1,
          execution_outcome: str = "not_applicable") -> LatchDisposition:
    from swing.latches.classification import PROMPT_DISPOSITIONS
    return LatchDisposition(
        candidate_id=candidate_id, disposition=disposition,
        execution_outcome=execution_outcome,
        prompt_required=disposition in PROMPT_DISPOSITIONS,
        is_terminal=is_terminal, coverage=_COV)


def _obs(disposition: str, **kw) -> ParityObservation:
    r = kw.pop("r_multiple", None)
    framework = kw.pop("framework", None)
    actual = kw.pop("actual", None)
    return ParityObservation(
        disposition=_disp(disposition, **kw), framework=framework, actual=actual,
        r_multiple=r)


# ==========================================================================
# THE BUCKET PARTITION
# ==========================================================================
def test_the_five_bucket_sets_are_pairwise_disjoint():
    sets = {
        "away": AWAY_RATE_COUNTED_DISPOSITIONS,
        "attested_away": ATTESTED_AWAY_DISPOSITIONS,
        "unattributable": UNATTRIBUTABLE_DISPOSITIONS,
        "decision": DECISION_DISPOSITIONS,
        "pending": PENDING_DISPOSITIONS,
    }
    names = sorted(sets)
    for i, a in enumerate(names):
        for b in names[i + 1:]:
            assert not (sets[a] & sets[b]), f"{a} overlaps {b}"


def test_the_ruled_union_EQUALS_the_disposition_enum():
    """THE CONCLUSION, NEVER THE CHECK. `r_bucket_for` validates membership
    against the UNION OF THE FIVE SETS, not against LATCH_DISPOSITIONS: the enum
    says only that the CLASSIFIER may emit a value, not that anyone RULED its
    bucket, so a disposition added to the enum without a ruling would pass a
    LATCH_DISPOSITIONS check and fall through the terminality gate into
    `pending_r` -- silently scored as "not an observation yet" rather than raising.

    This equality catches the REVERSE omission: a set member that is not a legal
    disposition (a typo, not a design)."""
    assert _RULED_DISPOSITIONS == LATCH_DISPOSITIONS


def test_every_COHERENT_cell_maps_to_exactly_one_bucket_and_the_one_incoherent_RAISES():
    """The FULL (disposition, is_terminal) PRODUCT."""
    coherent = 0
    seen_buckets = set()
    histogram = dict.fromkeys(sorted(R_BUCKETS), 0)
    raised = []
    for disposition in sorted(LATCH_DISPOSITIONS):
        for is_terminal in (True, False):
            try:
                bucket = r_bucket_for(disposition, is_terminal=is_terminal)
            except ValueError:
                raised.append((disposition, is_terminal))
                continue
            assert bucket in R_BUCKETS
            coherent += 1
            histogram[bucket] += 1
            seen_buckets.add(bucket)
    assert raised == [("pending_live", True)], (
        "exactly ONE incoherent cell: pending_live means the latch is LIVE, so "
        "is_terminal=True is not a state the classifier can produce, and silently "
        "bucketing it would HIDE a classifier bug in the very report layer built "
        "to stop silent absorption")
    # STATED CELL COUNTS, so an implementation that quietly drops the membership
    # guard or mis-populates DECISION_DISPOSITIONS produces a DIFFERENT histogram
    # and fails VISIBLY instead of passing a property test that no longer means
    # what it says.
    assert coherent == 2 * len(LATCH_DISPOSITIONS) - 1
    assert histogram["pending_r"] == len(LATCH_DISPOSITIONS)
    assert histogram["decision_r"] == len(DECISION_DISPOSITIONS)
    assert histogram["unattributable_r"] == len(UNATTRIBUTABLE_DISPOSITIONS)
    assert histogram["away_r"] == len(AWAY_RATE_COUNTED_DISPOSITIONS)
    assert histogram["attested_away_r"] == len(ATTESTED_AWAY_DISPOSITIONS)
    # ...and the roster is HONEST rather than aspirational: the set of values
    # r_bucket_for actually RETURNS over the whole coherent product EQUALS
    # R_BUCKETS.
    assert seen_buckets == R_BUCKETS


@pytest.mark.parametrize("is_terminal", [True, False])
def test_r_bucket_for_RAISES_on_a_disposition_absent_from_the_RULED_UNION(
        monkeypatch, is_terminal):
    """THE `False` CASE IS THE LOAD-BEARING ONE. An earlier revision explicitly
    SKIPPED it, reasoning that the terminality gate would return `pending_r`
    first -- which is not a reason to omit the test, it is the DEFECT the test
    detects (a default RELOCATED, not removed).

    A fake disposition is added to LATCH_DISPOSITIONS ONLY, not to any bucket set.
    """
    from swing.latches import classification as mod
    monkeypatch.setattr(
        mod, "LATCH_DISPOSITIONS", LATCH_DISPOSITIONS | {"fake_disposition"})
    # The scenario, stated: the enum now ADMITS the value, and no bucket set does.
    assert "fake_disposition" in mod.LATCH_DISPOSITIONS
    assert "fake_disposition" not in _RULED_DISPOSITIONS
    with pytest.raises(ValueError, match="no ruled R bucket"):
        r_bucket_for("fake_disposition", is_terminal=is_terminal)


def test_the_decision_subkind_map_covers_exactly_the_decision_set():
    """`decision_r` sums THREE DIFFERENT KINDS OF EVIDENCE -- directly logged
    decisions, self-attestation and a telemetry-INFERRED lapse -- and the
    governing principle forbids merging categories that differ in evidence kind.
    The distinction is preserved upstream, so the remedy is at the REPORT."""
    assert set(DECISION_SUBKIND) == set(DECISION_DISPOSITIONS)
    assert set(DECISION_SUBKIND.values()) == {"logged", "attested", "inferred"}


# ==========================================================================
# RULING 1 -- pending_live is REPORTED, NEVER SCORED, and terminality GATES
# ==========================================================================
def test_adding_a_pending_live_latch_leaves_both_away_rates_UNCHANGED():
    base = [_obs("away_unseen", candidate_id=1),
            _obs("accepted", candidate_id=2)]
    with_pending = [*base, _obs("pending_live", is_terminal=False,
                                candidate_id=3)]
    a = compute_execution_parity(base, health=_OK)
    b = compute_execution_parity(with_pending, health=_OK)
    assert a.away.objective_rate == b.away.objective_rate
    assert a.away.attested_rate == b.away.attested_rate
    assert a.away.classifiable_fires == b.away.classifiable_fires == 2
    assert b.away.pending_fires == 1


@pytest.mark.parametrize("disposition,label", [
    ("accepted", "a place intent"),
    ("declined", "a decline intent"),
    ("attested_chose_not_to_act", "an attest intent"),
    ("away_unseen", "no views at all"),
    ("never_actionable", "withheld-only views"),
])
def test_the_five_NON_TERMINAL_cells_bucket_to_pending_r_and_score_nothing(
        disposition, label):
    """THE FIVE CELLS A DISPOSITION-ONLY IMPLEMENTATION FAILS. A `r_bucket_for`
    taking only a disposition scores these as accepted / declined / attested_* /
    away_unseen / never_actionable respectively -- five NON-TERMINAL observations
    entering SCORED buckets, which is the exact corruption RD's ruling forbids."""
    assert r_bucket_for(disposition, is_terminal=False) == "pending_r"
    base = [_obs("away_unseen", candidate_id=1),
            _obs("accepted", candidate_id=2)]
    ref = compute_execution_parity(base, health=_OK)
    got = compute_execution_parity(
        [*base, _obs(disposition, is_terminal=False, candidate_id=9)],
        health=_OK)
    assert got.away.objective_rate == ref.away.objective_rate, label
    assert got.away.classifiable_fires == ref.away.classifiable_fires
    assert got.bucket_counts["pending_r"] == 1


def test_a_non_terminal_decision_does_NOT_move_the_decision_subcounts():
    """The sub-counts are REFINEMENTS OF TERMINAL `decision_r`, computed AFTER
    bucketing. Counting by disposition NAME instead would let a LIVE `accepted`
    into `decision_r_logged` while its R correctly sat in `pending_r` -- so the
    sub-counts would stop summing to the total, and the tempting 'fix' is to make
    `decision_r` wrong too."""
    base = [_obs("accepted", candidate_id=1), _obs("declined", candidate_id=2),
            _obs("attested_chose_not_to_act", candidate_id=3)]
    ref = compute_execution_parity(base, health=_OK)
    live = [_obs("accepted", is_terminal=False, candidate_id=11),
            _obs("declined", is_terminal=False, candidate_id=12),
            _obs("attested_chose_not_to_act", is_terminal=False,
                 candidate_id=13)]
    got = compute_execution_parity([*base, *live], health=_OK)
    assert (got.decision_r_logged, got.decision_r_attested,
            got.decision_r_inferred) == (
        ref.decision_r_logged, ref.decision_r_attested, ref.decision_r_inferred)
    assert (got.decision_r_logged + got.decision_r_attested
            + got.decision_r_inferred) == got.bucket_counts["decision_r"]


# ==========================================================================
# RULING 2 -- attested_was_away is a THIRD terminal category
# ==========================================================================
def test_attested_was_away_lands_in_its_OWN_bucket_and_in_the_denominator():
    """NEITHER existing bucket. `decision_r` is clearly wrong (separating exactly
    this is what the away bucket is for), but merging into `away_r` would
    reintroduce, through the ATTESTATION door, the flattering path closed at the
    DEFAULT door -- a self-report about one's own diligence is systematically
    biased toward the more comfortable explanation, and this is THE number that
    would justify automating his entries.

    A corpus with one of each discriminates all THREE wrong implementations:
    merged-into-away, left-in-decision, and computed-over-different-denominators.
    """
    obs = [_obs("away_unseen", candidate_id=1),
           _obs("attested_was_away", candidate_id=2),
           _obs("accepted", candidate_id=3)]
    rep = compute_execution_parity(obs, health=_OK)
    assert rep.bucket_counts == {
        "away_r": 1, "attested_away_r": 1, "decision_r": 1,
        "unattributable_r": 0, "pending_r": 0}
    assert rep.away.classifiable_fires == 3
    # the OBJECTIVE rate counts away_unseen ONLY
    assert rep.away.objective_rate == pytest.approx(1 / 3)
    # the ATTESTED rate adds attested_was_away over the SAME denominator
    assert rep.away.attested_rate == pytest.approx(2 / 3)
    assert rep.away.attested_rate >= rep.away.objective_rate
    # ...and it is EXCLUDED from the discipline signal (it is not decision_r)
    assert rep.decision_r_attested == 0
    assert rep.decision_r_logged == 1


def test_the_attested_rate_is_ALWAYS_at_or_above_the_objective_rate():
    for extra in ([], [_obs("attested_was_away", candidate_id=9)]):
        rep = compute_execution_parity(
            [_obs("away_unseen", candidate_id=1),
             _obs("accepted", candidate_id=2), *extra], health=_OK)
        assert rep.away.attested_rate >= rep.away.objective_rate


# ==========================================================================
# THE AWAY RATE CANNOT BE OBTAINED WITHOUT ITS VERDICT
# ==========================================================================
def test_away_rate_result_cannot_be_constructed_without_health():
    with pytest.raises(TypeError):
        compute_away_rate(bucket_counts={"away_r": 1, "decision_r": 1})


def test_both_rates_are_None_and_the_reason_is_LABELLED_under_broken():
    """The gate applies to the PAIR: an unreliable beacon corrupts the objective
    numerator DIRECTLY and the bound derived from it CONSEQUENTLY."""
    broken = TelemetryHealth(
        verdict="broken", covered_sessions=1, uncovered_sessions=THRESHOLD)
    rep = compute_execution_parity(
        [_obs("away_unseen", candidate_id=1), _obs("accepted", candidate_id=2)],
        health=broken)
    assert rep.away.objective_rate is None
    assert rep.away.attested_rate is None
    assert "BROKEN" in rep.away.withheld_reason
    assert "covered=1" in rep.away.withheld_reason
    assert f"uncovered={THRESHOLD}" in rep.away.withheld_reason


def test_the_denominator_excludes_every_unattributable_disposition_and_pending():
    obs = [_obs("accepted", candidate_id=1)]
    for i, disposition in enumerate(sorted(UNATTRIBUTABLE_DISPOSITIONS), start=2):
        obs.append(_obs(disposition, candidate_id=i))
    obs.append(_obs("pending_live", is_terminal=False, candidate_id=99))
    rep = compute_execution_parity(obs, health=_OK)
    assert rep.away.classifiable_fires == 1
    assert rep.away.excluded_fires == len(UNATTRIBUTABLE_DISPOSITIONS)
    assert rep.away.pending_fires == 1


# ==========================================================================
# RD CARRY 1 -- THE DENOMINATORS ARE KEYED ON DISTINCT LATCH IDENTITY
# ==========================================================================
def test_three_observations_of_ONE_latch_count_ONCE_in_every_denominator():
    """RD CARRY 1 (2026-07-29). THE LEDGER'S UNIT IS THE LATCH (THE OPPORTUNITY),
    NOT THE FIRE.

    RD traced the property and found it correct today BY CONSTRUCTION -- but
    nothing PINNED it, and *"correct by construction with no pin is exactly how a
    ruling silently regresses, which is the entire reason I made it a ruling
    rather than an observation."*

    WHAT THIS CATCHES: if anything ever feeds MULTIPLE fire rows per latch into
    the classifier, three rows for ONE opportunity would TRIPLE-COUNT it and
    inflate EVERY denominator -- classifiable_fires, the per-bucket R totals, and
    therefore THE AWAY RATE, the number that will justify or kill stage-3
    auto-place. An implementation that iterates the observation list without
    deduping on latch identity counts 3 and FAILS.
    """
    one_latch = [
        _obs("away_unseen", candidate_id=11261, r_multiple=1.22),
        _obs("away_unseen", candidate_id=11261, r_multiple=1.22),
        _obs("away_unseen", candidate_id=11261, r_multiple=1.22),
    ]
    rep = compute_execution_parity(one_latch, health=_OK)
    assert rep.total_observations == 1
    assert rep.bucket_counts["away_r"] == 1
    assert rep.bucket_r["away_r"] == 1.22
    assert rep.away.classifiable_fires == 1
    assert rep.away.away_unseen_fires == 1
    assert rep.away.objective_rate == 1.0
    assert rep.disposition_counts == {"away_unseen": 1}
    # THE REDUCTION IS LABELLED, not silent -- an unlabelled reduction is a quiet
    # all-clear by omission.
    assert rep.duplicate_latch_observations == 2


def test_distinct_latches_are_NOT_deduped_so_the_pin_is_not_vacuous():
    """Without this cell, the CARRY-1 test would also pass against an
    implementation that collapsed the WHOLE corpus to one row."""
    rep = compute_execution_parity(
        [_obs("away_unseen", candidate_id=1),
         _obs("away_unseen", candidate_id=2),
         _obs("accepted", candidate_id=3)], health=_OK)
    assert rep.total_observations == 3
    assert rep.duplicate_latch_observations == 0
    assert rep.away.classifiable_fires == 3


# ==========================================================================
# TELEMETRY HEALTH
# ==========================================================================
def _live_latch(anchor: date, last: date, candidate_id: int = 1) -> Latch:
    return Latch(
        identity=LatchIdentity(
            candidate_id=candidate_id, evaluation_run_id=121, ticker="FTRE",
            detection_date=anchor.isoformat(), pipeline_run_id=None),
        latched_pivot=18.34, latched_initial_stop=14.88, zone_cap=18.8902,
        anchor=anchor, horizon_expiry=last, sessions_elapsed=1,
        sessions_to_horizon=1, state="armed")


def _sessions(start: date, n: int) -> list[date]:
    return [start + timedelta(days=i) for i in range(n)]


class _Row:
    """A minimal view-row stand-in: the health check reads only these two."""

    def __init__(self, session: date, *, surface: str = "latch_panel",
                 actionable: int = 1) -> None:
        self.view_session_date = session.isoformat()
        self.surface = surface
        self.actionable_ever_viewed = actionable


def test_sessions_before_the_epoch_are_UNINSTRUMENTED_not_uncovered():
    """Excluded from BOTH counts. Not "uncovered", UNINSTRUMENTED -- and the
    distinction is the whole point: an absence of apparatus must not masquerade as
    an observation about the operator."""
    latch = _live_latch(date(2026, 7, 20), date(2026, 8, 31))
    got = assess_telemetry_health(
        sessions=_sessions(date(2026, 7, 20), 12), latches=[latch], views=[])
    assert got.uninstrumented_sessions == 9      # 07-20 .. 07-28
    assert got.covered_sessions == 0
    assert got.uncovered_sessions == 3           # 07-29 .. 07-31


def test_a_row_of_EITHER_actionability_creates_a_COVERED_session():
    """`actionable` filters NEITHER counter: a row of either value proves the
    beacon FIRED, which is the only question this check asks."""
    latch = _live_latch(EPOCH, EPOCH + timedelta(days=5))
    sessions = _sessions(EPOCH, 3)
    withheld_only = assess_telemetry_health(
        sessions=sessions, latches=[latch],
        views=[_Row(s, actionable=0) for s in sessions])
    assert withheld_only.covered_sessions == 3
    assert withheld_only.uncovered_sessions == 0
    assert withheld_only.verdict == "ok"


def test_a_row_on_an_UNCOUNTED_surface_does_NOT_create_a_covered_session():
    """SURFACE filters BOTH counters: the check asks whether *the beacon we
    measure from* fired, so a row on an uncounted surface tells us nothing about
    it. Exercised through the PARAMETER over a valid row."""
    latch = _live_latch(EPOCH, EPOCH + timedelta(days=5))
    sessions = _sessions(EPOCH, 3)
    got = assess_telemetry_health(
        sessions=sessions, latches=[latch],
        views=[_Row(s) for s in sessions], counted_surfaces=frozenset())
    assert got.covered_sessions == 0
    assert got.uncovered_sessions == 3


def test_a_session_with_no_live_latch_counts_in_NEITHER_bucket():
    latch = _live_latch(EPOCH, EPOCH + timedelta(days=1))
    got = assess_telemetry_health(
        sessions=_sessions(EPOCH, 6), latches=[latch], views=[])
    assert got.covered_sessions == 0
    assert got.uncovered_sessions == 2


def test_the_DARK_count_binds_at_the_threshold_EVEN_WITH_covered_above_zero():
    """THE DISCRIMINATOR. Keying `broken` on `covered == 0` lets a window with ONE
    sibling view and many dark sessions verdict `ok` and hand `away_unseen` to the
    away rate -- manufacturing away-rate evidence out of an instrument that was
    dark for most of the window. One beacon hit proves the beacon existed ONCE; it
    does not make the window OBSERVED.

    Under the pre-fix `covered == 0` rule this substrate verdicts `ok` and the
    latch reaches `away_unseen`, so the cell discriminates.
    """
    n = THRESHOLD + 1
    latch = _live_latch(EPOCH, EPOCH + timedelta(days=n))
    sessions = _sessions(EPOCH, n)
    got = assess_telemetry_health(
        sessions=sessions, latches=[latch], views=[_Row(sessions[0])])
    assert got.covered_sessions == 1
    assert got.uncovered_sessions >= THRESHOLD
    assert got.verdict == "broken"


def test_zero_covered_below_the_threshold_is_INDETERMINATE():
    latch = _live_latch(EPOCH, EPOCH + timedelta(days=10))
    got = assess_telemetry_health(
        sessions=_sessions(EPOCH, THRESHOLD - 1), latches=[latch], views=[])
    assert got.covered_sessions == 0
    assert 0 < got.uncovered_sessions < THRESHOLD
    assert got.verdict == "indeterminate"


def test_a_fully_witnessed_window_is_ok():
    latch = _live_latch(EPOCH, EPOCH + timedelta(days=5))
    sessions = _sessions(EPOCH, 4)
    got = assess_telemetry_health(
        sessions=sessions, latches=[latch], views=[_Row(s) for s in sessions])
    assert got.verdict == "ok"
    assert got.uncovered_sessions == 0


# ==========================================================================
# THE AGREEMENT RATE
# ==========================================================================
_FW = {"order_type": "LIMIT", "duration": "GOOD_TILL_CANCEL", "stop_price": None,
       "limit_price": 18.89, "quantity": 9}


def test_a_delta_clean_accepted_order_populates_the_numerator():
    rep = compute_execution_parity(
        [_obs("accepted", candidate_id=1,
              execution_outcome="accepted_by_broker",
              framework=_FW, actual=dict(_FW))], health=_OK)
    assert (rep.agreement_numerator, rep.agreement_denominator) == (1, 1)
    assert rep.agreement_rate == 1.0


def test_the_FTRE_divergence_ENTERS_the_denominator_and_FAILS_the_numerator():
    """A resting broker order is POSITIVE ACCEPTANCE EVIDENCE whether or not its
    quantity matches -- the broker accepted an order; the operator simply placed a
    DIFFERENT one from the prepared one. If the divergent row landed `unknown`
    instead, FTRE's delta would be VISIBLE in the ledger and yet EXCLUDED from the
    agreement denominator, so the arc's own worked example would still not reach
    the metric it exists to feed."""
    rep = compute_execution_parity(
        [_obs("accepted", candidate_id=1,
              execution_outcome="accepted_by_broker",
              framework=_FW, actual=dict(_FW, quantity=10))], health=_OK)
    assert rep.agreement_denominator == 1
    assert rep.agreement_numerator == 0
    assert rep.delta_totals["quantity_differs"] == 1
    assert rep.agreement_rate == 0.0


def test_a_broker_REJECTED_order_is_in_NEITHER_and_appears_in_validity_failed():
    """A FINDING, not an agreement and not a disagreement: the framework and the
    operator may have agreed PERFECTLY on an order the market would not accept,
    which is precisely the FTRE class stage 2's preview_order exists to kill.
    Reporting it in its OWN count is what makes it visible; folding it into either
    side would hide it."""
    rep = compute_execution_parity(
        [_obs("accepted", candidate_id=1,
              execution_outcome="rejected_by_broker", framework=_FW)],
        health=_OK)
    assert (rep.agreement_numerator, rep.agreement_denominator) == (0, 0)
    assert rep.validity_failed == 1
    assert rep.agreement_rate is None


def test_an_unobserved_validity_appears_in_validity_unknown_not_in_agreement():
    """V1 HONESTY: most rows will be `unknown` for a while, because the prompt only
    fires once a `place` intent has aged past its session."""
    rep = compute_execution_parity(
        [_obs("accepted", candidate_id=1, execution_outcome="unknown",
              framework=_FW)], health=_OK)
    assert rep.validity_unknown == 1
    assert rep.agreement_denominator == 0


def test_an_accepted_order_with_an_incomplete_actual_side_is_actual_side_unknown():
    rep = compute_execution_parity(
        [_obs("accepted", candidate_id=1,
              execution_outcome="accepted_by_broker",
              framework=_FW, actual=dict(_FW, quantity=None))], health=_OK)
    assert rep.actual_side_unknown == 1
    assert rep.agreement_denominator == 0


def test_the_report_carries_EVERY_bucket_in_the_roster():
    """Built BY ITERATING R_BUCKETS rather than by listing them, so a sixth bucket
    added to the resolver cannot be silently omitted from the report."""
    rep = compute_execution_parity([_obs("accepted", candidate_id=1)],
                                   health=_OK)
    assert set(rep.bucket_counts) == R_BUCKETS
    assert set(rep.bucket_r) == R_BUCKETS


def test_the_bucket_counts_reconcile_to_the_corpus_total():
    obs = [_obs("accepted", candidate_id=1), _obs("away_unseen", candidate_id=2),
           _obs("attested_was_away", candidate_id=3),
           _obs("pre_telemetry", candidate_id=4),
           _obs("pending_live", is_terminal=False, candidate_id=5)]
    rep = compute_execution_parity(obs, health=_OK)
    assert sum(rep.bucket_counts.values()) == rep.total_observations == 5
