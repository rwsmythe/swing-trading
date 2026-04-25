"""Trade-outcome simulator tests.

Covers the four canonical paths (clean trigger→stop, trigger→gap-stop,
trigger→time-cap, never-triggered) plus hand-computed R-multiple and
gap-magnitude math.
"""
from __future__ import annotations

from datetime import date

import pandas as pd
import pytest


def _ohlcv(rows: list[tuple[str, float, float, float, float]]) -> pd.DataFrame:
    """rows: list of (date_iso, open, high, low, close)."""
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d, _, _, _, _ in rows])
    return pd.DataFrame(
        {
            "Open": [o for _, o, _, _, _ in rows],
            "High": [h for _, _, h, _, _ in rows],
            "Low": [lo for _, _, _, lo, _ in rows],
            "Close": [c for _, _, _, _, c in rows],
            "Volume": [1_000_000] * len(rows),
        },
        index=idx,
    )


def _signal(ticker="AAPL", d=date(2026, 4, 20), entry=100.0, stop=95.0):
    from research.harness.earnings_proximity.replay import AplusSignal

    return AplusSignal(
        ticker=ticker,
        date=d,
        entry_target=entry,
        initial_stop=stop,
        next_earnings_date=None,
        absent_earnings_data=False,
    )


# ----------------------------------------------------------------------------


def test_simulate_clean_trigger_then_clean_stop():
    """Trigger on day+1 (high crosses entry), stopped on day+3 (low crosses
    stop but open > stop). R = -1 exactly (priced at the stop)."""
    from research.harness.earnings_proximity.simulator import simulate_trade

    df = _ohlcv([
        # signal bar
        ("2026-04-20", 99.0, 99.5, 98.5, 99.0),
        # day+1: trigger (high 100.5 >= 100)
        ("2026-04-21", 99.5, 100.5, 99.0, 100.2),
        # day+2: hold
        ("2026-04-22", 100.0, 101.0, 99.0, 100.5),
        # day+3: stopped — open 99 > stop 95 and low 94 < stop
        ("2026-04-23", 99.0, 99.5, 94.0, 94.5),
    ])
    signal = _signal(entry=100.0, stop=95.0)
    out = simulate_trade(signal, df, time_cap_days=10)

    assert out.triggered is True
    assert out.trigger_date == date(2026, 4, 21)
    assert out.entry_price == pytest.approx(100.0)
    assert out.exit_date == date(2026, 4, 23)
    assert out.exit_price == pytest.approx(95.0)  # stop fill
    assert out.r_multiple == pytest.approx(-1.0)
    assert out.gap_through is False
    assert out.gap_magnitude_r is None
    assert out.time_capped is False


def test_simulate_trigger_then_gap_stop():
    """Gap-down through the stop: open <= stop, so fill at open (not stop).
    R worse than -1; gap_magnitude_r = (stop - open) / (entry - stop)."""
    from research.harness.earnings_proximity.simulator import simulate_trade

    df = _ohlcv([
        ("2026-04-20", 99.0, 99.5, 98.5, 99.0),
        ("2026-04-21", 99.5, 100.5, 99.0, 100.2),   # trigger @ 100.0
        ("2026-04-22", 100.0, 100.5, 99.0, 99.5),   # hold
        ("2026-04-23", 92.0, 93.0, 91.0, 92.5),     # gap through stop 95 → fill @ 92
    ])
    signal = _signal(entry=100.0, stop=95.0)
    out = simulate_trade(signal, df, time_cap_days=10)

    # rps = 100-95 = 5. Exit 92. R = (92 - 100)/5 = -1.6.
    # gap_magnitude_r = (95 - 92)/5 = 0.6.
    assert out.triggered is True
    assert out.gap_through is True
    assert out.exit_price == pytest.approx(92.0)
    assert out.r_multiple == pytest.approx(-1.6)
    assert out.gap_magnitude_r == pytest.approx(0.6)


def test_simulate_trigger_then_time_cap_winner():
    """Trigger, no stop hit within cap; exit at close of the cap bar.
    R is positive for a winner."""
    from research.harness.earnings_proximity.simulator import simulate_trade

    df = _ohlcv([
        ("2026-04-20", 99.0, 99.5, 98.5, 99.0),
        ("2026-04-21", 99.5, 100.5, 99.0, 100.0),  # trigger
        ("2026-04-22", 100.0, 101.0, 99.5, 100.5),
        ("2026-04-23", 100.5, 102.0, 100.0, 101.5),
        # time_cap_days=2 from trigger → cap bar is 2026-04-23 (close 101.5)
    ])
    signal = _signal(entry=100.0, stop=95.0)
    out = simulate_trade(signal, df, time_cap_days=2)

    # rps = 5. Exit close 101.5. R = (101.5 - 100)/5 = 0.3.
    assert out.triggered is True
    assert out.time_capped is True
    assert out.exit_price == pytest.approx(101.5)
    assert out.r_multiple == pytest.approx(0.3)
    assert out.gap_through is False


def test_simulate_never_triggered_within_window_is_dropped():
    """High never crosses entry during time_cap_days after signal → signal dropped.
    Returned outcome has triggered=False and r_multiple=None."""
    from research.harness.earnings_proximity.simulator import simulate_trade

    df = _ohlcv([
        ("2026-04-20", 99.0, 99.5, 98.5, 99.0),
        ("2026-04-21", 99.0, 99.8, 98.5, 99.2),
        ("2026-04-22", 99.0, 99.9, 98.0, 99.1),
        ("2026-04-23", 99.0, 99.6, 98.5, 99.0),
    ])
    signal = _signal(entry=100.0, stop=95.0)
    out = simulate_trade(signal, df, time_cap_days=3)

    assert out.triggered is False
    assert out.trigger_date is None
    assert out.entry_price is None
    assert out.exit_price is None
    assert out.r_multiple is None
    assert out.gap_through is False


def test_simulate_signal_on_last_bar_drops_signal():
    """Boundary: if signal.date is the last bar in OHLCV, no forward bars
    exist for trigger scan → signal dropped."""
    from research.harness.earnings_proximity.simulator import simulate_trade

    df = _ohlcv([
        ("2026-04-20", 99.0, 99.5, 98.5, 99.0),
    ])
    signal = _signal(d=date(2026, 4, 20), entry=100.0, stop=95.0)
    out = simulate_trade(signal, df, time_cap_days=10)

    assert out.triggered is False
    assert out.trigger_date is None


def test_simulate_gap_through_on_entry_trigger_day_does_not_double_count():
    """Entry bar: high crosses entry so trigger fires at entry_target exactly.
    Same-bar low breach of stop is NOT checked on the trigger bar (stop scan
    starts next bar). Document this common-mode simplification."""
    from research.harness.earnings_proximity.simulator import simulate_trade

    df = _ohlcv([
        ("2026-04-20", 99.0, 99.5, 98.5, 99.0),
        # trigger bar: high 101 >= entry 100 AND low 94 < stop 95 — we ignore
        # the same-bar stop and enter at entry cleanly.
        ("2026-04-21", 99.5, 101.0, 94.0, 95.5),
        ("2026-04-22", 95.5, 96.0, 94.5, 95.5),  # stop on day+2
    ])
    signal = _signal(entry=100.0, stop=95.0)
    out = simulate_trade(signal, df, time_cap_days=10)

    assert out.triggered is True
    assert out.trigger_date == date(2026, 4, 21)
    assert out.entry_price == pytest.approx(100.0)
    # Day+2: open 95.5 > stop 95, low 94.5 <= stop → clean stop at 95.
    assert out.exit_date == date(2026, 4, 22)
    assert out.exit_price == pytest.approx(95.0)
    assert out.r_multiple == pytest.approx(-1.0)
    assert out.gap_through is False


def test_simulate_positive_r_clean_stop_after_rally():
    """Sanity: R computation is (exit - entry) / (entry - stop). Verify on
    a rally-then-give-back path."""
    from research.harness.earnings_proximity.simulator import simulate_trade

    df = _ohlcv([
        ("2026-04-20", 99.0, 99.5, 98.5, 99.0),
        ("2026-04-21", 99.5, 100.5, 99.0, 100.0),   # trigger
        ("2026-04-22", 100.0, 103.0, 100.0, 102.5),
        ("2026-04-23", 102.0, 104.0, 101.0, 103.5),
        ("2026-04-24", 103.0, 103.5, 94.5, 95.0),   # stops — close well below stop
    ])
    signal = _signal(entry=100.0, stop=95.0)
    out = simulate_trade(signal, df, time_cap_days=10)

    # Clean stop (open 103 > 95, low 94.5 <= 95).
    assert out.r_multiple == pytest.approx(-1.0)


def test_simulate_open_exactly_at_stop_is_clean_stop_not_gap():
    """Boundary: Open == initial_stop is a clean stop fill, NOT a gap-through.

    Strict-less-than gap convention prevents zero-magnitude "gaps" from
    polluting the gap_through_rate metric. The fill is still at the stop
    price, and r_multiple = -1 exactly."""
    from research.harness.earnings_proximity.simulator import simulate_trade

    df = _ohlcv([
        ("2026-04-20", 99.0, 99.5, 98.5, 99.0),
        ("2026-04-21", 99.5, 100.5, 99.0, 100.0),  # trigger
        # Day+2: open 95 == stop 95, low 94 <= stop. Clean stop, NOT gap.
        ("2026-04-22", 95.0, 96.0, 94.0, 94.5),
    ])
    signal = _signal(entry=100.0, stop=95.0)
    out = simulate_trade(signal, df, time_cap_days=10)

    assert out.triggered is True
    assert out.exit_price == pytest.approx(95.0)  # stop fill, not open fill
    assert out.r_multiple == pytest.approx(-1.0)
    assert out.gap_through is False
    assert out.gap_magnitude_r is None


def test_simulate_records_bar_dates_via_index():
    """Simulator must locate the signal bar via OHLCV index (DatetimeIndex),
    not by assuming position 0."""
    from research.harness.earnings_proximity.simulator import simulate_trade

    df = _ohlcv([
        ("2026-04-15", 90.0, 91.0, 89.0, 90.5),
        ("2026-04-16", 90.5, 91.5, 90.0, 91.0),
        ("2026-04-20", 99.0, 99.5, 98.5, 99.0),     # signal bar (not first)
        ("2026-04-21", 99.5, 100.5, 99.0, 100.0),   # trigger
        ("2026-04-22", 100.0, 101.0, 94.0, 94.5),   # stop
    ])
    signal = _signal(d=date(2026, 4, 20), entry=100.0, stop=95.0)
    out = simulate_trade(signal, df, time_cap_days=10)

    assert out.triggered is True
    assert out.trigger_date == date(2026, 4, 21)
    assert out.exit_date == date(2026, 4, 22)
