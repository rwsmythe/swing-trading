from __future__ import annotations

from dataclasses import dataclass

from research.harness.shadow_expectancy.collapse import (
    collapse_detections, normalize_tick,
)


@dataclass
class _Det:  # minimal detection view the collapser needs
    detection_id: int
    pivot: float
    forward_series_key: tuple   # (session, o, h, l, c) tuple-of-tuples
    first_trigger_session: str | None


def _det(did, pivot, series=(("2026-06-01", 9.6, 10.2, 9.5, 10.1),), trig="2026-06-01"):
    return _Det(did, pivot, tuple(series), trig)


def test_canonical_is_pivot_match_and_collapses_ALL_non_canonical():
    # Codex C4: the group is ALL detections for (run, ticker). The canonical is the
    # pivot-matching one (tie-broken by lowest id); collapsed_ids covers EVERY other
    # detection in the group -- INCLUDING the non-pivot-matching det 9 -- as long as the
    # whole group shares an identical frozen series + first trigger.
    dets = [_det(5, 10.0), _det(2, 10.0), _det(9, 11.0)]
    res = collapse_detections(dets, candidate_pivot=10.0)
    assert res.canonical.detection_id == 2
    assert sorted(res.collapsed_ids) == [5, 9]   # group_size - 1 (C4)
    assert res.exclusion_reason is None


def test_pivot_mismatch_yields_no_canonical_detection():
    # C-review M4: a candidate EXISTS (candidate_pivot=10.0) but NO detection pivot matches
    # it -> a canonical-detection integrity fault, distinct from a missing candidate row.
    dets = [_det(1, 11.0)]
    res = collapse_detections(dets, candidate_pivot=10.0)
    assert res.canonical is None and res.exclusion_reason == "no_canonical_detection"


def test_missing_candidate_yields_no_candidate_join():
    # No candidate row at all (candidate_pivot is None) -> no_candidate_join (NOT
    # no_canonical_detection -- that reason is reserved for a present-but-unmatchable pivot).
    dets = [_det(1, 11.0)]
    res = collapse_detections(dets, candidate_pivot=None)
    assert res.canonical is None and res.exclusion_reason == "no_candidate_join"


def test_tick_normalized_pivot_match():
    dets = [_det(1, 10.00004)]
    res = collapse_detections(dets, candidate_pivot=10.00001)  # equal at 4 decimals
    assert res.canonical is not None and res.exclusion_reason is None


def test_divergent_forward_series_excludes():
    a = _det(1, 10.0, series=(("2026-06-01", 9.6, 10.2, 9.5, 10.1),))
    b = _det(2, 10.0, series=(("2026-06-01", 9.6, 10.9, 9.5, 10.1),))  # diff high
    res = collapse_detections([a, b], candidate_pivot=10.0)
    assert res.exclusion_reason == "inconsistent_detection_series"


def test_NON_pivot_matching_divergent_series_still_excludes():
    # Codex C4: a non-pivot-matching detection whose frozen series DIVERGES from the
    # canonical's MUST exclude the whole signal -- the old code only checked the pivot-
    # matching subset and would have missed this.
    canonical = _det(1, 10.0, series=(("2026-06-01", 9.6, 10.2, 9.5, 10.1),))
    other = _det(2, 11.0, series=(("2026-06-01", 9.6, 10.9, 9.5, 10.1),))  # diff pivot AND high
    res = collapse_detections([canonical, other], candidate_pivot=10.0)
    assert res.exclusion_reason == "inconsistent_detection_series"


def test_divergent_trigger_session_excludes():
    a = _det(1, 10.0, trig="2026-06-01")
    b = _det(2, 10.0, trig="2026-06-02")  # same series shape but diff trigger
    b.forward_series_key = a.forward_series_key
    res = collapse_detections([a, b], candidate_pivot=10.0)
    assert res.exclusion_reason == "inconsistent_trigger_state"
