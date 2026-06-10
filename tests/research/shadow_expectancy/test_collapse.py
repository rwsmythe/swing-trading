from __future__ import annotations

from dataclasses import dataclass

from research.harness.shadow_expectancy.collapse import collapse_detections


@dataclass
class _Det:  # minimal detection view the collapser needs: id + date-ascending bars
    detection_id: int
    bars: tuple   # ((observation_date, open, high, low, close), ...)


_B1 = ("2026-06-01", 9.6, 10.2, 9.5, 10.1)
_B2 = ("2026-06-02", 10.1, 10.5, 10.0, 10.4)
_B3 = ("2026-06-03", 10.4, 10.9, 10.3, 10.8)


def test_canonical_is_longest_chain_tie_low_id():
    # spec 2.3: canonical = the LONGEST frozen chain (most bars); collapsed_ids = every other
    # detection in the group (group_size - 1). The geometric pivot is NOT consulted.
    short = _Det(2, (_B1,))
    longest = _Det(5, (_B1, _B2, _B3))
    medium = _Det(9, (_B1, _B2))
    res = collapse_detections([short, longest, medium])
    assert res.canonical.detection_id == 5             # longest (3 bars)
    assert sorted(res.collapsed_ids) == [2, 9]
    assert res.exclusion_reason is None


def test_tie_break_is_lowest_detection_id():
    a = _Det(7, (_B1, _B2))
    b = _Det(3, (_B1, _B2))   # same length -> lowest id wins
    res = collapse_detections([a, b])
    assert res.canonical.detection_id == 3
    assert res.exclusion_reason is None


def test_single_detection_group_has_no_collapsed():
    res = collapse_detections([_Det(4, (_B1, _B2))])
    assert res.canonical.detection_id == 4
    assert res.collapsed_ids == []
    assert res.exclusion_reason is None


def test_strict_prefix_chain_is_accepted():
    # spec 2.3: a terminated chain that is a STRICT date-prefix of the longest is fine.
    longest = _Det(1, (_B1, _B2, _B3))
    prefix = _Det(2, (_B1, _B2))
    res = collapse_detections([longest, prefix])
    assert res.canonical.detection_id == 1
    assert res.exclusion_reason is None


def test_differing_first_trigger_session_is_accepted():
    # spec 1.3 regression: detections that (under the old observe-step) had DIFFERENT first
    # trigger sessions are NO LONGER excluded -- entry is recomputed, the trigger-state gate is
    # gone. Identical bars across distinct pattern classes collapse cleanly.
    a = _Det(1, (_B1, _B2))
    b = _Det(2, (_B1, _B2))
    res = collapse_detections([a, b])
    assert res.exclusion_reason is None
    assert res.canonical.detection_id == 1


def test_divergent_ohlc_on_shared_date_excludes():
    longest = _Det(1, (_B1, _B2))
    bad_high = ("2026-06-01", 9.6, 10.9, 9.5, 10.1)   # diverges from _B1 on the SAME date
    other = _Det(2, (bad_high,))
    res = collapse_detections([longest, other])
    assert res.exclusion_reason == "inconsistent_detection_series"


def test_gappy_interior_missing_chain_excludes():
    # spec 2.3 / Codex R1-#1: a gappy chain A=[d1,d3] vs B=[d1,d2,d3] (interior date missing)
    # is NOT a strict prefix -> excluded under inconsistent_detection_series, NOT silently
    # accepted with a truncated bar source (the overlap-only check would have missed this).
    full = _Det(1, (_B1, _B2, _B3))
    gappy = _Det(2, (_B1, _B3))   # _B2 (interior) missing
    res = collapse_detections([full, gappy])
    assert res.exclusion_reason == "inconsistent_detection_series"
