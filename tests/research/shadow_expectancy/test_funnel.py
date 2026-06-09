from __future__ import annotations

import pytest

from research.harness.shadow_expectancy.collapse import collapse_detections
from research.harness.shadow_expectancy.exceptions import ShadowExpectancyError
from research.harness.shadow_expectancy.funnel import (
    DetectionLevel, SignalOutcome, build_funnel,
)


def test_detection_level_reconciles():
    det = DetectionLevel(total_detections=10, collapsed_duplicate=3, unique_signals=7)
    f = build_funnel(det, signal_outcomes=[])
    assert f["detection_level"]["total_detections"] == 10
    assert (f["detection_level"]["collapsed_duplicate_detection"]
            + f["detection_level"]["unique_signals"]) == 10


def test_unattributed_reasons_vs_per_hypothesis():
    # C-review M1/M4: ALL pre-/non-attribution states are per-reason counters INSIDE the
    # single `unattributed` bucket -- no_candidate_join, no_canonical_detection (candidate
    # present, no pivot match), inconsistent_*, AND matched_no_hypothesis (joined+valid but
    # zero hypotheses). matched_no_hypothesis is a REASON within unattributed, NOT a separate
    # top-level bucket. validate/simulate failures on an ATTRIBUTED signal (invalid_ohlc /
    # degenerate_risk) -> PER-HYPOTHESIS excluded.
    outs = [
        SignalOutcome(hypothesis=None, terminal="unattributed", reason="no_candidate_join"),
        SignalOutcome(hypothesis=None, terminal="unattributed",
                      reason="no_canonical_detection"),
        SignalOutcome(hypothesis=None, terminal="unattributed",
                      reason="inconsistent_detection_series"),
        SignalOutcome(hypothesis=None, terminal="unattributed",
                      reason="matched_no_hypothesis"),
        SignalOutcome(hypothesis=None, terminal="unattributed", reason="multi_match"),  # R3-M1
        SignalOutcome(hypothesis="A+ baseline", terminal="closed", reason=None),
        SignalOutcome(hypothesis="A+ baseline", terminal="excluded", reason="invalid_ohlc"),
        SignalOutcome(hypothesis="A+ baseline", terminal="excluded", reason="degenerate_risk"),
        SignalOutcome(hypothesis="A+ baseline", terminal="open_at_horizon", reason=None),
        SignalOutcome(hypothesis="A+ baseline", terminal="never_triggered",
                      reason="never_triggered"),
    ]
    det = DetectionLevel(total_detections=10, collapsed_duplicate=0, unique_signals=10)
    f = build_funnel(det, signal_outcomes=outs)
    # ONE unattributed bucket; matched_no_hypothesis + multi_match are counters WITHIN it (M1).
    assert f["unattributed"]["no_candidate_join"] == 1
    assert f["unattributed"]["no_canonical_detection"] == 1          # M4
    assert f["unattributed"]["inconsistent_detection_series"] == 1
    assert f["unattributed"]["matched_no_hypothesis"] == 1           # reason WITHIN unattributed
    assert f["unattributed"]["multi_match"] == 1                     # R3-M1 reason WITHIN unattributed
    assert "matched_no_hypothesis" not in f                          # NOT a top-level bucket (M1)
    assert "multi_match" not in f                                    # NOT a top-level bucket (R3-M1)
    h1 = f["per_hypothesis"]["A+ baseline"]
    assert h1["closed"] == 1 and h1["open_at_horizon"] == 1
    assert h1["excluded"]["degenerate_risk"] == 1
    assert h1["excluded"]["invalid_ohlc"] == 1   # M5: attributed validation failure is per-hyp
    assert h1["never_triggered"] == 1
    assert "no_candidate_join" not in h1.get("excluded", {})


def test_each_signal_lands_in_exactly_one_terminal_bucket():
    outs = [SignalOutcome(hypothesis="A+ baseline", terminal="closed", reason=None)]
    det = DetectionLevel(total_detections=1, collapsed_duplicate=0, unique_signals=1)
    f = build_funnel(det, signal_outcomes=outs)
    h1 = f["per_hypothesis"]["A+ baseline"]
    total = (h1["closed"] + h1["open_at_horizon"] + h1["never_triggered"]
             + sum(h1["excluded"].values()))
    assert total == 1


def test_multi_match_is_a_reason_within_unattributed():
    # R3-M1: a synthetic multi-match signal is excluded under the `multi_match` REASON within
    # the single `unattributed` bucket -- NOT a separate top-level bucket, NOT per-hypothesis.
    det = DetectionLevel(total_detections=1, collapsed_duplicate=0, unique_signals=1)
    f = build_funnel(det, signal_outcomes=[
        SignalOutcome(hypothesis=None, terminal="unattributed", reason="multi_match")])
    assert f["unattributed"]["multi_match"] == 1
    assert "multi_match" not in f          # not a top-level bucket
    assert f["per_hypothesis"] == {}       # no per-hypothesis contribution


@pytest.mark.parametrize("bad", [
    # m1: a hypothesis-None outcome whose reason is missing/None or not in UNATTRIBUTED_REASONS
    # is a producer-contract violation -- build_funnel RAISES rather than silently defaulting it
    # to no_candidate_join (which would mask the malformed outcome).
    SignalOutcome(hypothesis=None, terminal="unattributed", reason=None),
    SignalOutcome(hypothesis=None, terminal="unattributed", reason=""),
    # an exclusion reason that belongs to the PER-HYPOTHESIS path must never reach here with a
    # None hypothesis.
    SignalOutcome(hypothesis=None, terminal="unattributed", reason="invalid_ohlc"),
    SignalOutcome(hypothesis=None, terminal="unattributed", reason="degenerate_risk"),
    # a malformed terminal (not "unattributed") on a None-hypothesis outcome.
    SignalOutcome(hypothesis=None, terminal="closed", reason=None),
    # writing-plans R4-M1: a VALID unattributed reason but a mismatched terminal on a
    # None-hypothesis outcome must still raise (ALL THREE conditions are required).
    SignalOutcome(hypothesis=None, terminal="closed", reason="no_candidate_join"),
    # writing-plans R4-M1: terminal=="unattributed" but a hypothesis IS set -> raise.
    SignalOutcome(hypothesis="A+ baseline", terminal="unattributed", reason="multi_match"),
    # writing-plans R4-M1: an unknown terminal on an ATTRIBUTED signal -> raise.
    SignalOutcome(hypothesis="A+ baseline", terminal="bogus", reason=None),
])
def test_build_funnel_raises_on_malformed_unattributed_outcome(bad):
    det = DetectionLevel(total_detections=1, collapsed_duplicate=0, unique_signals=1)
    with pytest.raises(ShadowExpectancyError):
        build_funnel(det, signal_outcomes=[bad])


@pytest.mark.parametrize("bad", [
    # writing-plans R5: an ATTRIBUTED terminal must carry its producer-contract reason; a wrong
    # reason -- especially an UNATTRIBUTED_REASONS reason on a hypothesis -- must RAISE, never be
    # silently counted under that hypothesis.
    SignalOutcome(hypothesis="A+ baseline", terminal="closed", reason="invalid_ohlc"),
    SignalOutcome(hypothesis="A+ baseline", terminal="open_at_horizon", reason="lifecycle"),
    SignalOutcome(hypothesis="A+ baseline", terminal="never_triggered", reason=None),
    SignalOutcome(hypothesis="A+ baseline", terminal="excluded", reason="no_candidate_join"),
    SignalOutcome(hypothesis="A+ baseline", terminal="excluded", reason="multi_match"),
    SignalOutcome(hypothesis="A+ baseline", terminal="excluded", reason=None),
])
def test_build_funnel_raises_on_malformed_attributed_outcome(bad):
    det = DetectionLevel(total_detections=1, collapsed_duplicate=0, unique_signals=1)
    with pytest.raises(ShadowExpectancyError):
        build_funnel(det, signal_outcomes=[bad])


def test_build_funnel_accepts_valid_attributed_exclusion_reasons():
    # The five post-attribution per-hypothesis `excluded` reasons are accepted + counted.
    det = DetectionLevel(total_detections=5, collapsed_duplicate=0, unique_signals=5)
    outs = [SignalOutcome(hypothesis="A+ baseline", terminal="excluded", reason=r)
            for r in ("invalid_ohlc", "degenerate_risk", "insufficient_forward_depth",
                      "missing_observations", "lifecycle")]
    f = build_funnel(det, signal_outcomes=outs)
    assert dict(f["per_hypothesis"]["A+ baseline"]["excluded"]) == {
        "invalid_ohlc": 1, "degenerate_risk": 1, "insufficient_forward_depth": 1,
        "missing_observations": 1, "lifecycle": 1}


def test_detection_reconciliation_from_REAL_collapse_output():
    # Codex M8: drive the detection-level reconciliation from the REAL collapser over an
    # actual multi-detection group, NOT a hand-built consistent object, so a C4 undercount
    # would surface. Three detections for one (run,ticker): a pivot-10 canonical, a duplicate
    # pivot-10, and a non-pivot-matching pivot-11 -- all sharing an identical frozen series +
    # trigger -> 1 unique signal + 2 collapsed.
    from dataclasses import dataclass

    @dataclass
    class _Det:
        detection_id: int
        pivot: float
        forward_series_key: tuple
        first_trigger_session: str | None

    series = (("2026-06-01", 9.6, 10.2, 9.5, 10.1),)
    dets = [_Det(5, 10.0, series, "2026-06-01"),
            _Det(2, 10.0, series, "2026-06-01"),
            _Det(9, 11.0, series, "2026-06-01")]
    res = collapse_detections(dets, candidate_pivot=10.0)
    assert res.exclusion_reason is None
    total_detections = len(dets)
    collapsed_duplicate = len(res.collapsed_ids)
    unique_signals = 1   # this one (run,ticker) group collapsed to a single canonical signal
    det = DetectionLevel(total_detections, collapsed_duplicate, unique_signals)
    f = build_funnel(det, signal_outcomes=[
        SignalOutcome(hypothesis="A+ baseline", terminal="closed", reason=None)])
    dl = f["detection_level"]
    # the C4 reconciliation: total == unique + collapsed (the group fully reconciles).
    assert (dl["unique_signals"] + dl["collapsed_duplicate_detection"]
            == dl["total_detections"] == 3)
    assert collapsed_duplicate == 2   # group_size - 1 (C4), NOT just the pivot-matching subset
