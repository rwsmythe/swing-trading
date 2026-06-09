from __future__ import annotations

from datetime import date

import pandas as pd

from research.harness.minervini_exemplar_recall.control_cohort import ControlAnchor
from research.harness.minervini_primary_base_recall import precision_control as pc
from research.harness.minervini_primary_base_recall.constants import (
    MAX_CONTROL_AGE_BARS,
    MIN_HISTORY_BARS,
)


def _frame(periods: int):
    idx = pd.bdate_range(start=date(2000, 1, 3), periods=periods)
    c = pd.Series([10.0 + i * 0.01 for i in range(periods)], index=idx, dtype=float)
    return pd.DataFrame(
        {"Open": c, "High": c, "Low": c, "Close": c, "Volume": 1_000_000.0}, index=idx
    )


def test_eligible_pool_is_prefiltered_young_window_minus_gap_and_sweep():
    # 900-bar archive; entry at pos 600; sweep [540, 605]; gap CONTROL_GAP_BARS=120.
    bars = _frame(900)
    entry_pos = 600
    sweep = (540, 605)
    pool = pc.eligible_control_positions(
        bars, entry_pos=entry_pos, sweep_start=sweep[0], sweep_end=sweep[1]
    )
    # RIGHT-PATH: positions are PRE-FILTERED to [39, 503]; then |p-600| >= 120 (all of [39,503]
    # satisfy, since max is 503 and 600-503=97 < 120 EXCLUDES 481..503) and outside [540,605]
    # (no overlap with [39,503]). So the gap band 481..503 is removed.
    assert min(pool) == MIN_HISTORY_BARS - 1            # 39
    assert max(pool) <= MAX_CONTROL_AGE_BARS - 1        # <= 503
    assert all(abs(p - entry_pos) >= 120 for p in pool)
    assert 480 in pool and 481 not in pool             # 600-481=119 < 120 -> excluded
    # WRONG-PATH (post-filter: sample full archive THEN clip to young) would include positions
    # > 503 before clipping and could yield far fewer/none for a deep-history name; assert none
    # exceed the young ceiling.
    assert all(p <= 503 for p in pool)


def test_position_beyond_max_age_is_never_eligible_prefilter_not_postfilter():
    bars = _frame(900)
    # Entry far in the future so the gap never touches the young window.
    pool = pc.eligible_control_positions(bars, entry_pos=850, sweep_start=800, sweep_end=860)
    assert max(pool) <= MAX_CONTROL_AGE_BARS - 1
    assert 504 not in pool and 700 not in pool


def test_sample_is_deterministic_and_capped_at_k():
    bars = _frame(900)
    anchors, eligible_count = pc.sample_young_controls(
        bars, entry_pos=600, sweep_start=540, sweep_end=605, k=5, base_seed=123, exemplar_index=0
    )
    again, _ = pc.sample_young_controls(
        bars, entry_pos=600, sweep_start=540, sweep_end=605, k=5, base_seed=123, exemplar_index=0
    )
    assert [a.session_pos for a in anchors] == [a.session_pos for a in again]  # deterministic
    assert len(anchors) == 5
    assert all(isinstance(a, ControlAnchor) for a in anchors)
    assert eligible_count >= 5  # reported BEFORE the k-cap (manifest field)


def test_single_session_per_anchor_is_the_primary_estimand():
    # screen_control_anchor returns BOTH a single-session fire and a window best-of fire; the
    # single-session per-anchor flag is the documented primary estimand (R1.M9), reported apart.
    bars = _frame(900)
    anchor = ControlAnchor(session=bars.index[300].date(), session_pos=300)
    res = pc.screen_control_anchor(bars, anchor, window_back=60, window_fwd=5)
    assert hasattr(res, "single_session_fired")
    assert hasattr(res, "window_fired")
    # A pure monotone uptrend never forms a primary base -> neither fires (specificity).
    assert res.single_session_fired is False
    assert res.window_fired is False


def test_month_precision_control_exclusion_uses_full_documented_month_window():
    # Codex WP-R1 M7: the control sampler must exclude the FULL documented-month sweep window for a
    # month-precision exemplar, NOT the parsed-first-of-month [entry-60bd, entry+5bd]. This ties the
    # composition run.py uses: timing.sweep_bounds(month) ->
    # precision_control.eligible_control_positions.
    from datetime import date

    from research.harness.minervini_primary_base_recall import timing

    # A frame straddling Sept 1997 (the AMZN-1997 documented month). Entry far enough out that the
    # young pool [39,503] is not fully eaten by the 120-bar gap.
    idx = pd.bdate_range(start=date(1996, 1, 2), periods=900)
    c = pd.Series([10.0 + i * 0.01 for i in range(900)], index=idx, dtype=float)
    bars = pd.DataFrame(
        {"Open": c, "High": c, "Low": c, "Close": c, "Volume": 1_000_000.0}, index=idx
    )
    anchor = date(1997, 9, 1)  # month-precision parsed first-of-month
    bounds = timing.sweep_bounds(bars, anchor, "month", window_back=60, window_fwd=5)
    assert bounds is not None
    sweep_start, sweep_end = bounds
    # A LATE-September-1997 position (the last documented-month trading day) -- this is INSIDE the
    # full-month window but OUTSIDE the WRONG-PATH parsed-first-of-month [first-60, first+5] tail.
    sept = [i for i, ts in enumerate(bars.index) if ts.year == 1997 and ts.month == 9]
    last_sept_pos = sept[-1]
    entry_pos = sept[0]  # first trading day of the documented month ~= the parsed-anchor position
    pool = pc.eligible_control_positions(
        bars, entry_pos=entry_pos, sweep_start=sweep_start, sweep_end=sweep_end
    )
    # RIGHT-PATH: last_sept_pos is within the full-month sweep window -> excluded from controls.
    assert last_sept_pos not in pool
    # And the full-month sweep end reaches past the WRONG-PATH parsed-first-of-month +5bd tail.
    assert sweep_end >= last_sept_pos > (entry_pos + 5)
