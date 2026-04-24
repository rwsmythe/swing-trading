"""Trade-outcome simulator for the earnings-proximity replay.

Simulates forward from an :class:`AplusSignal` against a ticker's OHLCV
history. Deterministic, no DB I/O, no persistence.

Behavioral contract (from the session 2b brief §D4)
----------------------------------------------------
- **Trigger scan** starts on the bar AFTER ``signal.date`` and runs for at
  most ``time_cap_days`` bars. A trigger fires on the first bar where
  ``High >= entry_target``; entry fills at ``entry_target`` exactly
  (slippage ignored — it's common-mode across variants).
- **Same-bar stop on trigger day** is NOT checked. Daily bars don't tell
  us whether the high came before the low; documenting this simplification
  rather than modeling it. Stop scan starts on the bar AFTER the trigger.
- **Stop scan** starts on the bar AFTER the trigger and runs for at most
  ``time_cap_days`` bars:
    - If ``Open <= initial_stop``: gap-through. Fill at ``Open`` (worse
      than stop); ``gap_through=True``.
    - Elif ``Low <= initial_stop`` and ``Open > initial_stop``: clean
      stop. Fill at ``initial_stop``.
- **Time cap**: if neither a stop nor the end-of-history is reached within
  ``time_cap_days`` bars, exit at the close of the cap bar. ``time_capped=True``.
- **Never-triggered**: signal is dropped; the returned outcome has
  ``triggered=False`` and ``r_multiple=None``.
- **No earnings-based exit**: study is about ENTRY-time earnings proximity.
  Mid-trade earnings are held through.
- **No pyramiding, no scaling**: one entry, one exit, full position.

R-multiple
----------
``r_multiple = (exit_price - entry_price) / (entry_price - initial_stop)``.
``gap_magnitude_r = (initial_stop - exit_price) / (entry_price - initial_stop)``
(only populated when ``gap_through=True``; always non-negative).
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

import pandas as pd

from research.harness.earnings_proximity.replay import AplusSignal


@dataclass(frozen=True)
class TradeOutcome:
    ticker: str
    signal_date: date
    triggered: bool
    trigger_date: date | None
    entry_price: float | None
    exit_date: date | None
    exit_price: float | None
    r_multiple: float | None
    gap_through: bool
    gap_magnitude_r: float | None
    time_capped: bool


def _dropped(signal: AplusSignal) -> TradeOutcome:
    return TradeOutcome(
        ticker=signal.ticker,
        signal_date=signal.date,
        triggered=False,
        trigger_date=None,
        entry_price=None,
        exit_date=None,
        exit_price=None,
        r_multiple=None,
        gap_through=False,
        gap_magnitude_r=None,
        time_capped=False,
    )


def _find_signal_pos(ohlcv: pd.DataFrame, signal_date: date) -> int | None:
    """Return the positional index of ``signal_date`` in ``ohlcv``, or None."""
    target = pd.Timestamp(signal_date)
    # Exact-day match; non-session dates (weekends/holidays) should not appear
    # as signal dates since replay drives off the NYSE calendar.
    matches = [i for i, ts in enumerate(ohlcv.index) if ts.normalize() == target]
    return matches[0] if matches else None


def simulate_trade(
    signal: AplusSignal,
    ohlcv: pd.DataFrame,
    *,
    time_cap_days: int = 10,
) -> TradeOutcome:
    """Simulate forward from ``signal`` against ``ohlcv``.

    ``ohlcv`` must be indexed by DatetimeIndex with Open/High/Low/Close columns.
    Bars before and after ``signal.date`` should be present (the simulator
    uses only bars AFTER the signal bar for trigger/stop scans).
    """
    rps = signal.entry_target - signal.initial_stop
    if rps <= 0:
        raise ValueError(
            f"entry_target must exceed initial_stop; "
            f"got entry={signal.entry_target}, stop={signal.initial_stop}"
        )

    s_pos = _find_signal_pos(ohlcv, signal.date)
    if s_pos is None:
        return _dropped(signal)

    n = len(ohlcv.index)

    # ---- Trigger scan: bars (s_pos+1) .. (s_pos+time_cap_days) inclusive. ----
    trigger_end = min(s_pos + 1 + time_cap_days, n)
    trigger_pos: int | None = None
    for t in range(s_pos + 1, trigger_end):
        if float(ohlcv.iloc[t]["High"]) >= signal.entry_target:
            trigger_pos = t
            break

    if trigger_pos is None:
        return _dropped(signal)

    trigger_date = ohlcv.index[trigger_pos].date()
    entry_price = signal.entry_target

    # ---- Stop scan: bars (trigger_pos+1) .. (trigger_pos+time_cap_days) inclusive. ----
    stop_end = min(trigger_pos + 1 + time_cap_days, n)
    for t in range(trigger_pos + 1, stop_end):
        bar = ohlcv.iloc[t]
        open_ = float(bar["Open"])
        low_ = float(bar["Low"])

        if open_ <= signal.initial_stop:
            # Gap-through: fill at open (worse than stop).
            exit_price = open_
            r = (exit_price - entry_price) / rps
            gap_mag = (signal.initial_stop - exit_price) / rps
            return TradeOutcome(
                ticker=signal.ticker,
                signal_date=signal.date,
                triggered=True,
                trigger_date=trigger_date,
                entry_price=entry_price,
                exit_date=ohlcv.index[t].date(),
                exit_price=exit_price,
                r_multiple=r,
                gap_through=True,
                gap_magnitude_r=gap_mag,
                time_capped=False,
            )
        if low_ <= signal.initial_stop:
            # Clean stop: fill at stop price.
            exit_price = signal.initial_stop
            r = (exit_price - entry_price) / rps  # exactly -1.0
            return TradeOutcome(
                ticker=signal.ticker,
                signal_date=signal.date,
                triggered=True,
                trigger_date=trigger_date,
                entry_price=entry_price,
                exit_date=ohlcv.index[t].date(),
                exit_price=exit_price,
                r_multiple=r,
                gap_through=False,
                gap_magnitude_r=None,
                time_capped=False,
            )

    # ---- Time cap: exit at close of the cap bar (or last available bar). ----
    cap_pos = min(trigger_pos + time_cap_days, n - 1)
    exit_price = float(ohlcv.iloc[cap_pos]["Close"])
    r = (exit_price - entry_price) / rps
    return TradeOutcome(
        ticker=signal.ticker,
        signal_date=signal.date,
        triggered=True,
        trigger_date=trigger_date,
        entry_price=entry_price,
        exit_date=ohlcv.index[cap_pos].date(),
        exit_price=exit_price,
        r_multiple=r,
        gap_through=False,
        gap_magnitude_r=None,
        time_capped=True,
    )
