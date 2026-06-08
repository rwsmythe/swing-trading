# tests/research/minervini_exemplar_recall/test_timing.py
from __future__ import annotations

from datetime import date

import pandas as pd

from research.harness.minervini_exemplar_recall.exemplar_reader import ExemplarRow


def _bars(n=400, start="2009-01-02"):
    idx = pd.bdate_range(start=start, periods=n)
    closes = [100.0 + i for i in range(n)]
    return pd.DataFrame({"Open": closes, "High": closes, "Low": closes, "Close": closes,
                         "Volume": [1_000] * n}, index=idx)


def test_sweep_window_positional_and_inclusive():
    from research.harness.minervini_exemplar_recall.timing import sweep_sessions

    bars = _bars()
    entry_anchor = bars.index[100].date()  # entry_pos == 100
    sessions = sweep_sessions(bars, entry_anchor, window_back=60, window_fwd=5)
    # bars[40:106] -> 66 sessions (60 back + entry + 5 fwd).
    # WRONG-PATH (off-by-one / calendar-day window): not 66.  RIGHT-PATH: 66.
    assert len(sessions) == 66
    assert sessions[0] == bars.index[40].date()
    assert sessions[-1] == bars.index[105].date()


def test_sweep_clamps_start_for_young_name():
    from research.harness.minervini_exemplar_recall.timing import sweep_sessions

    bars = _bars()
    entry_anchor = bars.index[20].date()  # entry_pos 20 < window_back 60
    sessions = sweep_sessions(bars, entry_anchor, window_back=60, window_fwd=5)
    # max(0, 20-60)=0 -> bars[0:26]; NOT a tail-wrap.
    assert sessions[0] == bars.index[0].date()
    assert sessions[-1] == bars.index[25].date()
    assert len(sessions) == 26


def test_entry_anchor_beyond_last_bar_yields_empty():
    from research.harness.minervini_exemplar_recall.timing import sweep_sessions

    bars = _bars()
    sessions = sweep_sessions(bars, date(2099, 1, 1), window_back=60, window_fwd=5)
    assert sessions == []


def test_best_bucket_ordering():
    from research.harness.minervini_exemplar_recall.timing import best_bucket_of

    # aplus(2) > watch(1) > skip(0); no_data/insufficient map to skip-rank 0.
    assert best_bucket_of(["skip", "watch", "skip"]) == "watch"
    assert best_bucket_of(["watch", "aplus", "skip"]) == "aplus"
    assert best_bucket_of(["skip", "skip"]) == "skip"
