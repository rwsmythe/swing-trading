"""Seven stop-advisory rules (legacy parity).

Each rule is pure: (Trade, AdvisoryContext) → AdvisorySuggestion | None.
Aggregator returns the non-None list, ordered for display.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from swing.config import StopAdvisoryConfig
from swing.data.models import Trade
from swing.trades.equity import r_so_far


@dataclass(frozen=True)
class AdvisoryContext:
    as_of_date: str
    current_price: float
    sma10: float | None
    sma20: float | None
    weather_status: str
    config: StopAdvisoryConfig


@dataclass(frozen=True)
class AdvisorySuggestion:
    rule: str
    message: str


def suggest_breakeven(trade: Trade, ctx: AdvisoryContext) -> AdvisorySuggestion | None:
    if r_so_far(trade, ctx.current_price) < ctx.config.breakeven_r_trigger:
        return None
    if trade.current_stop >= trade.entry_price:
        return None
    return AdvisorySuggestion(
        rule="breakeven",
        message=f"Move stop to breakeven (${trade.entry_price:.2f})",
    )


def suggest_trail_ma(
    trade: Trade, ctx: AdvisoryContext, *,
    ma_value: float | None, ma_label: str, buffer_pct: float,
) -> AdvisorySuggestion | None:
    if ma_value is None or ctx.current_price < ma_value:
        return None
    proposed = ma_value * (1 - buffer_pct / 100)
    if proposed <= trade.current_stop:
        return None
    return AdvisorySuggestion(
        rule=f"trail_{ma_label.lower()}",
        message=f"Trail stop up to ${proposed:.2f} \u2014 {buffer_pct}% below {ma_label} (${ma_value:.2f})",
    )


def suggest_exit_close_below_ma(
    trade: Trade, ctx: AdvisoryContext, *,
    ma_value: float | None, ma_label: str,
) -> AdvisorySuggestion | None:
    if ma_value is None or ctx.current_price >= ma_value:
        return None
    return AdvisorySuggestion(
        rule=f"exit_below_{ma_label.lower()}",
        message=f"EXIT \u2014 close ${ctx.current_price:.2f} is below {ma_label} (${ma_value:.2f})",
    )


def suggest_weather_action(trade: Trade, ctx: AdvisoryContext) -> AdvisorySuggestion | None:
    s = (ctx.weather_status or "").lower()
    if s.startswith("bearish"):
        return AdvisorySuggestion(
            rule="weather",
            message="Bearish weather \u2014 tighten stops or exit longs",
        )
    if s.startswith("caution"):
        return AdvisorySuggestion(
            rule="weather",
            message="Caution weather \u2014 tighten stops; consider half sizing",
        )
    return None


def suggest_time_stop(trade: Trade, ctx: AdvisoryContext) -> AdvisorySuggestion | None:
    days_open = (date.fromisoformat(ctx.as_of_date) - date.fromisoformat(trade.entry_date)).days
    if days_open <= ctx.config.time_stop_days:
        return None
    if r_so_far(trade, ctx.current_price) >= ctx.config.time_stop_min_r:
        return None
    return AdvisorySuggestion(
        rule="time_stop",
        message=f"Time stop \u2014 {days_open} days open with only "
                f"+{r_so_far(trade, ctx.current_price):.2f}R; consider exit",
    )


def compute_all_suggestions(trade: Trade, ctx: AdvisoryContext) -> list[AdvisorySuggestion]:
    sugs: list[AdvisorySuggestion | None] = []
    sugs.append(suggest_breakeven(trade, ctx))
    sugs.append(suggest_trail_ma(trade, ctx, ma_value=ctx.sma10, ma_label="10MA",
                                  buffer_pct=ctx.config.trail_10ma_buffer_pct))
    sugs.append(suggest_trail_ma(trade, ctx, ma_value=ctx.sma20, ma_label="20MA",
                                  buffer_pct=ctx.config.trail_20ma_buffer_pct))
    sugs.append(suggest_exit_close_below_ma(trade, ctx, ma_value=ctx.sma10, ma_label="10MA"))
    sugs.append(suggest_exit_close_below_ma(trade, ctx, ma_value=ctx.sma20, ma_label="20MA"))
    sugs.append(suggest_weather_action(trade, ctx))
    sugs.append(suggest_time_stop(trade, ctx))
    return [s for s in sugs if s is not None]
