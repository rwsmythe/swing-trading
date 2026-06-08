# tests/research/minervini_exemplar_recall/test_control_cohort.py
from __future__ import annotations

import pandas as pd


def _bars(n=800, start="2007-01-02"):
    idx = pd.bdate_range(start=start, periods=n)
    closes = [100.0 + i for i in range(n)]
    return pd.DataFrame({"Open": closes, "High": closes, "Low": closes, "Close": closes,
                         "Volume": [1_000] * n}, index=idx)


def test_sample_respects_gap_and_floor_and_window():
    from research.harness.minervini_exemplar_recall.control_cohort import sample_control_anchors

    bars = _bars()
    entry_pos = 500
    entry_anchor = bars.index[entry_pos].date()
    anchors = sample_control_anchors(
        bars, entry_anchor, k=5, window_back=60, window_fwd=5, screenable_floor=221,
        base_seed=20260608, exemplar_index=3,
    )
    assert len(anchors) == 5
    for a in anchors:
        # >=120bd gap from entry
        assert abs(a.session_pos - entry_pos) >= 120
        # >= screenable_floor preceding bars (so position index >= 220)
        assert a.session_pos >= 220
        # outside the sweep window
        assert not (entry_pos - 60 <= a.session_pos <= entry_pos + 5)


def test_sampling_is_deterministic():
    from research.harness.minervini_exemplar_recall.control_cohort import sample_control_anchors

    bars = _bars()
    entry_anchor = bars.index[500].date()
    kw = dict(k=5, window_back=60, window_fwd=5, screenable_floor=221, base_seed=20260608, exemplar_index=3)
    a1 = sample_control_anchors(bars, entry_anchor, **kw)
    a2 = sample_control_anchors(bars, entry_anchor, **kw)
    # WRONG-PATH (Random() unseeded): different sessions.  RIGHT-PATH: identical.
    assert [x.session_pos for x in a1] == [x.session_pos for x in a2]


def test_distinct_exemplar_index_changes_sample():
    from research.harness.minervini_exemplar_recall.control_cohort import sample_control_anchors

    bars = _bars()
    entry_anchor = bars.index[500].date()
    base = dict(k=5, window_back=60, window_fwd=5, screenable_floor=221, base_seed=20260608)
    a3 = sample_control_anchors(bars, entry_anchor, exemplar_index=3, **base)
    a4 = sample_control_anchors(bars, entry_anchor, exemplar_index=4, **base)
    assert [x.session_pos for x in a3] != [x.session_pos for x in a4]
