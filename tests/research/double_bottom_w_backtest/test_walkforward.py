"""Tests for walkforward.py: entry trigger, R-multiple, open/untriggered."""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest

from research.harness.double_bottom_w_backtest.cohort import PrimaryVerdict
from research.harness.double_bottom_w_backtest.rulesets import RulesetA
from research.harness.double_bottom_w_backtest.walkforward import (
    _trigger_search_upper_bound,
    find_trigger_index,
    walk_forward,
)


def _verdict(
    *,
    ticker: str = "ABC",
    asof: str = "2026-05-01",
    trough_1: str = "2026-04-01",
    trough_2: str = "2026-04-20",
    trough_2_price: float = 95.0,
    center_peak_price: float = 100.0,
    pivot_price: float = 99.0,
    composite: float = 0.85,
) -> PrimaryVerdict:
    return PrimaryVerdict(
        ticker=ticker,
        anchor_asof_date=date.fromisoformat(asof),
        trough_1_date=date.fromisoformat(trough_1),
        trough_1_price=trough_2_price + 1.0,
        center_peak_date=date.fromisoformat(trough_1) + pd.Timedelta(days=5).to_pytimedelta(),
        center_peak_price=center_peak_price,
        trough_2_date=date.fromisoformat(trough_2),
        trough_2_price=trough_2_price,
        pivot_price=pivot_price,
        composite_score=composite,
        geometric_score=composite,
        template_match_score=None,
    )


def _bars(closes: list[float], *, start_date: str = "2026-04-25") -> pd.DataFrame:
    """Build synthetic bars: Open=Close-0.1; High=Close+0.5; Low=Close-0.5.

    Business-day index starting at start_date.
    """
    idx = pd.bdate_range(start=start_date, periods=len(closes))
    return pd.DataFrame(
        {
            "Open": [c - 0.1 for c in closes],
            "High": [c + 0.5 for c in closes],
            "Low": [c - 0.5 for c in closes],
            "Close": closes,
            "Volume": [1000.0] * len(closes),
        },
        index=idx,
    )


# ---- _trigger_search_upper_bound ---------------------------------------


def test_trigger_search_upper_bound_60_business_days() -> None:
    """asof=2026-05-22 (Fri) + 60 BD ≈ 2026-08-14 (Fri)."""
    ub = _trigger_search_upper_bound(date(2026, 5, 22), max_business_days=60)
    assert ub == date(2026, 8, 14)


# ---- find_trigger_index ------------------------------------------------


def test_find_trigger_skips_bars_at_or_before_lower_bound() -> None:
    """Lower bound exclusive: bars at lower_bound or earlier do NOT qualify."""
    bars = _bars([95.0, 98.0, 101.0, 102.0], start_date="2026-04-25")  # Sat-skip; Mon=04-27
    # The 04-27 bar (idx 0) closes at 95; 04-28 (idx 1) closes at 98; 04-29 (idx 2)
    # closes at 101 > peak=100. lower_bound = 2026-04-27 (exclusive) - so idx 0 skipped.
    idx = find_trigger_index(
        bars, trigger_threshold=100.0,
        lower_bound_exclusive=date(2026, 4, 27),
        upper_bound_inclusive=date(2026, 5, 30),
    )
    assert idx == 2


def test_find_trigger_returns_none_beyond_upper_bound() -> None:
    """Trigger candidate AFTER upper_bound returns None."""
    bars = _bars([95.0, 95.0, 95.0, 101.0, 102.0], start_date="2026-04-27")
    idx = find_trigger_index(
        bars, trigger_threshold=100.0,
        lower_bound_exclusive=date(2026, 4, 26),
        upper_bound_inclusive=date(2026, 4, 29),  # too tight
    )
    assert idx is None


def test_find_trigger_requires_next_session_for_entry() -> None:
    """If trigger fires on the LAST bar (no i+1), returns None."""
    bars = _bars([95.0, 95.0, 101.0], start_date="2026-04-27")  # idx 2 = last
    idx = find_trigger_index(
        bars, trigger_threshold=100.0,
        lower_bound_exclusive=date(2026, 4, 26),
        upper_bound_inclusive=date(2026, 5, 30),
    )
    assert idx is None


# ---- walk_forward ------------------------------------------------------


def test_walk_forward_untriggered_when_no_close_above_peak() -> None:
    bars = _bars([95.0] * 10, start_date="2026-05-04")
    v = _verdict(asof="2026-05-01", center_peak_price=100.0, trough_2_price=92.0)
    trade = walk_forward(v, bars, RulesetA())
    assert trade.status == "untriggered"
    assert trade.exit_reason == "untriggered"
    assert trade.r_multiple is None
    assert trade.entry_price is None
    assert trade.days_t2_to_asof == (date(2026, 5, 1) - date(2026, 4, 20)).days


def test_walk_forward_entry_at_next_session_open_after_trigger() -> None:
    # asof=2026-05-01. Bars at 05-04, 05-05, 05-06, 05-07.
    # idx 1 (05-05) closes at 101 > peak=100 (trigger). Entry at idx 2 (05-06) open.
    closes = [95.0, 101.0, 102.0, 102.5]
    bars = _bars(closes, start_date="2026-05-04")
    v = _verdict(asof="2026-05-01", center_peak_price=100.0, trough_2_price=92.0)
    trade = walk_forward(v, bars, RulesetA())
    # Should trigger at idx 1, entry at idx 2 open = 102 - 0.1 = 101.9
    assert trade.entry_date == date(2026, 5, 6)
    assert trade.entry_price == pytest.approx(101.9)


def test_walk_forward_open_at_data_tail_records_unrealized_R() -> None:
    """Position entered + walks to data tail without exit -> status=open with unrealized R."""
    # asof=2026-05-01. Trigger at idx 1 (close=101 > peak=100). Entry at idx 2 open=101.9.
    # Stop = 92*0.99 = 91.08. R = 101.9 - 91.08 = 10.82.
    # All subsequent closes 102+ never hit stop or +2R (=101.9 + 21.64 = 123.54).
    closes = [95.0, 101.0, 102.0, 103.0, 102.5, 103.0]
    bars = _bars(closes, start_date="2026-05-04")
    v = _verdict(asof="2026-05-01", center_peak_price=100.0, trough_2_price=92.0)
    trade = walk_forward(v, bars, RulesetA())
    assert trade.status == "open"
    assert trade.exit_reason == "open_at_data_tail"
    assert trade.r_multiple is not None
    # last_close=103.0; entry=101.9; R=10.82 -> (103 - 101.9) / 10.82 = ~0.10
    assert 0.05 < trade.r_multiple < 0.20


def test_walk_forward_search_window_60_business_days_cap() -> None:
    """Trigger after asof+60BD is untriggered (window expired)."""
    # asof=2026-05-01 + 60 BD = ~2026-07-27. Plant trigger at 2026-09-01 (way past).
    n_bars = 100
    closes = [95.0] * 90 + [101.0] * 10  # only the last 10 bars > peak; well past 60BD
    bars = _bars(closes, start_date="2026-05-04")
    v = _verdict(asof="2026-05-01", center_peak_price=100.0, trough_2_price=92.0)
    trade = walk_forward(v, bars, RulesetA())
    assert trade.status == "untriggered"


def test_walk_forward_records_max_close_pct_of_peak_diagnostic() -> None:
    """Near-miss diagnostic populated for untriggered (max forward close as % of peak)."""
    closes = [95.0, 98.0, 99.5, 99.0, 99.8]  # all below peak=100
    bars = _bars(closes, start_date="2026-05-04")
    v = _verdict(asof="2026-05-01", center_peak_price=100.0, trough_2_price=92.0)
    trade = walk_forward(v, bars, RulesetA())
    assert trade.status == "untriggered"
    assert trade.max_forward_close == pytest.approx(99.8)
    assert trade.max_close_pct_of_peak == pytest.approx(99.8)


def test_walk_forward_lower_bound_uses_max_of_three_anchors() -> None:
    """When trough_2 is AFTER asof, trough_2 wins; closes before trough_2 cannot trigger."""
    # asof=2026-05-01; trough_2_date=2026-05-10 (later). Even if close>peak at 05-05,
    # it should NOT trigger because we wait until trough_2 + 1 day.
    closes = [101.0, 102.0, 103.0, 104.0, 105.0, 106.0, 107.0, 108.0, 109.0, 110.0]
    bars = _bars(closes, start_date="2026-05-04")
    v = _verdict(
        asof="2026-05-01",
        trough_1="2026-04-01",
        trough_2="2026-05-10",
        center_peak_price=100.0,
        trough_2_price=92.0,
    )
    trade = walk_forward(v, bars, RulesetA())
    # Entry should NOT fire on 05-04, 05-05, ..., 05-10. First eligible trigger date
    # is 05-11. Index 5 = 05-11.
    assert trade.entry_date is not None
    assert trade.entry_date >= date(2026, 5, 12)  # next session AFTER trigger


def test_walk_forward_empty_bars_returns_untriggered() -> None:
    bars = _bars([])
    v = _verdict()
    trade = walk_forward(v, bars, RulesetA())
    assert trade.status == "untriggered"
    assert trade.exit_reason == "ohlcv_empty"
    assert trade.forward_bars_available == 0
