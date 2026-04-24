"""Tests for the earnings-proximity variant applicator.

Boundary convention (fixed 2026-04-24 in this module's docstring):
    A signal is EXCLUDED from variant X iff there are STRICTLY FEWER
    than X NYSE trading sessions strictly after signal.date and up to
    and including next_earnings_date.

    - X=0: nothing excluded (baseline).
    - Signal Mon, earnings Fri (4 sessions out): excluded at X=5, X=6, …
      but NOT at X=0, X=1, X=2, X=3, X=4.

Absent-data (per method record): if `absent_earnings_data` is True, do NOT
exclude — flag for review downstream.
"""
from __future__ import annotations

from datetime import date


def _sig(
    ticker="AAPL",
    d=date(2025, 6, 2),  # Monday
    next_earn=None,
    absent=False,
):
    from research.harness.earnings_proximity.replay import AplusSignal

    return AplusSignal(
        ticker=ticker,
        date=d,
        entry_target=100.0,
        initial_stop=95.0,
        next_earnings_date=next_earn,
        absent_earnings_data=absent,
    )


def _cal():
    import exchange_calendars as xcals

    return xcals.get_calendar("XNYS")


# ----------------------------------------------------------------------------
# Variant filter — core boundary semantics
# ----------------------------------------------------------------------------


def test_variant_zero_is_baseline_nothing_excluded():
    from research.harness.earnings_proximity.variants import apply_variant

    signals = [
        _sig(d=date(2025, 6, 2), next_earn=date(2025, 6, 3)),  # 1 day out
        _sig(d=date(2025, 6, 2), next_earn=None),
        _sig(d=date(2025, 6, 2), absent=True),
    ]
    out = apply_variant(signals, blackout_trading_days=0, trading_calendar=_cal())
    assert out == signals


def test_variant_excludes_signals_within_blackout_window():
    """Mon signal, earnings Fri (4 sessions out): excluded at X=5, allowed at X=4."""
    from research.harness.earnings_proximity.variants import apply_variant

    signals = [_sig(d=date(2025, 6, 2), next_earn=date(2025, 6, 6))]  # Mon → Fri = 4 sessions

    assert apply_variant(signals, 5, _cal()) == []
    assert apply_variant(signals, 6, _cal()) == []
    assert apply_variant(signals, 4, _cal()) == signals  # boundary: 4 < 4 is False
    assert apply_variant(signals, 3, _cal()) == signals


def test_variant_strict_less_than_convention_brief_example():
    """Brief example: 3 days out → excluded at X=5, not at X=3 (on boundary)."""
    from research.harness.earnings_proximity.variants import apply_variant

    # Signal Mon 2025-06-02, earnings Thu 2025-06-05 = 3 sessions out
    signals = [_sig(d=date(2025, 6, 2), next_earn=date(2025, 6, 5))]

    assert apply_variant(signals, 5, _cal()) == []       # 3 < 5 → excluded
    assert apply_variant(signals, 3, _cal()) == signals  # 3 < 3 is False → kept


def test_variant_counts_weekends_and_holidays_correctly():
    """Trading-day gap must skip weekends. Signal Fri, earnings Mon = 1 session
    out (Fri close → next session is Mon), not 3 calendar days → 3."""
    from research.harness.earnings_proximity.variants import apply_variant

    # Fri 2025-06-06 → Mon 2025-06-09 — 1 NYSE session apart.
    signals = [_sig(d=date(2025, 6, 6), next_earn=date(2025, 6, 9))]

    assert apply_variant(signals, 2, _cal()) == []       # 1 < 2 → excluded
    assert apply_variant(signals, 1, _cal()) == signals  # 1 < 1 → kept
    # For reference: calendar days is 3, which would give the wrong answer.


def test_variant_does_not_exclude_absent_data_flagged_signals():
    """Per method record: absent earnings data → do NOT exclude, flag for review."""
    from research.harness.earnings_proximity.variants import apply_variant

    signal = _sig(d=date(2025, 6, 2), next_earn=None, absent=True)
    # Even at max X, absent-flagged signals pass through.
    assert apply_variant([signal], 21, _cal()) == [signal]


def test_variant_keeps_signals_with_no_upcoming_earnings_but_not_flagged():
    """Present data but no future earnings → next_earnings_date=None, absent=False.
    Keep (nothing to exclude against)."""
    from research.harness.earnings_proximity.variants import apply_variant

    signal = _sig(d=date(2025, 6, 2), next_earn=None, absent=False)
    assert apply_variant([signal], 5, _cal()) == [signal]


def test_variant_keeps_signals_with_earnings_on_signal_date_or_earlier():
    """Earnings already happened or is today → signal has no upcoming earnings
    within the forward window; keep it."""
    from research.harness.earnings_proximity.variants import apply_variant

    # Earnings on signal day (0 sessions strictly after): keep regardless of X.
    same = _sig(d=date(2025, 6, 2), next_earn=date(2025, 6, 2))
    assert apply_variant([same], 10, _cal()) == [same]

    # Earnings in past: keep.
    past = _sig(d=date(2025, 6, 2), next_earn=date(2025, 5, 28))
    assert apply_variant([past], 10, _cal()) == [past]


def test_variant_distinct_from_calendar_day_counting():
    """A 9 calendar-day gap with a 3-day holiday weekend should not count as
    a 6 trading-day gap if there's a real NYSE holiday. Smoke-check with a
    known holiday: Independence Day Jul 4 2025 (Friday)."""
    from research.harness.earnings_proximity.variants import apply_variant

    # Thu Jul 3 → Mon Jul 7. Jul 4 is a holiday (session closed).
    # Sessions strictly after Jul 3 up to Jul 7: just Mon Jul 7 = 1 session.
    signals = [_sig(d=date(2025, 7, 3), next_earn=date(2025, 7, 7))]
    assert apply_variant(signals, 2, _cal()) == []       # 1 < 2 → excluded
    assert apply_variant(signals, 1, _cal()) == signals


def test_variant_leaves_non_excluded_signals_intact_order_preserved():
    """Multi-signal input: preserve ordering and only drop excluded ones."""
    from research.harness.earnings_proximity.variants import apply_variant

    s1 = _sig(ticker="AAPL", d=date(2025, 6, 2), next_earn=date(2025, 6, 6))  # 4 out
    s2 = _sig(ticker="MSFT", d=date(2025, 6, 2), next_earn=date(2025, 6, 20))  # ~14 out
    s3 = _sig(ticker="NVDA", d=date(2025, 6, 2), next_earn=None)

    out = apply_variant([s1, s2, s3], 5, _cal())
    # s1 (4<5) excluded; s2 (>5) kept; s3 (no earnings) kept.
    assert [s.ticker for s in out] == ["MSFT", "NVDA"]
