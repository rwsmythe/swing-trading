"""Minervini Trend Template — 8 structural checks (spec §4.1)."""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result, sma
from swing.evaluation.rs import compute_rs

LAYER = "trend_template"

CHECK_NAMES = (
    "TT1_above_150_200",
    "TT2_150_above_200",
    "TT3_200_rising",
    "TT4_50_above_150_200",
    "TT5_above_50",
    "TT6_above_52w_low_30pct",
    "TT7_within_52w_high_25pct",
    "TT8_rs_rank",
)


def evaluate(ctx: CandidateContext) -> tuple[Result, ...]:
    closes = ctx.ohlcv["Close"]
    if len(closes) < 200:
        na = [
            Result.na_(f"need 200 bars, have {len(closes)}", name=n, layer=LAYER)
            for n in CHECK_NAMES
        ]
        return tuple(na)

    last_close = float(closes.iloc[-1])
    sma50 = sma(closes, 50)
    sma150 = sma(closes, 150)
    sma200 = sma(closes, 200)
    s50 = float(sma50.iloc[-1])
    s150 = float(sma150.iloc[-1])
    s200 = float(sma200.iloc[-1])

    results: list[Result] = []

    # TT1: close > 150MA and close > 200MA
    v = f"close={last_close:.2f} 150MA={s150:.2f} 200MA={s200:.2f}"
    r = (last_close > s150) and (last_close > s200)
    results.append(
        Result.pass_(v, "close > 150MA AND close > 200MA", name=CHECK_NAMES[0], layer=LAYER)
        if r else Result.fail_(v, "close > 150MA AND close > 200MA", name=CHECK_NAMES[0], layer=LAYER)
    )

    # TT2: 150MA > 200MA
    v = f"150MA={s150:.2f} 200MA={s200:.2f}"
    r = s150 > s200
    results.append(
        Result.pass_(v, "150MA > 200MA", name=CHECK_NAMES[1], layer=LAYER)
        if r else Result.fail_(v, "150MA > 200MA", name=CHECK_NAMES[1], layer=LAYER)
    )

    # TT3: 200MA trending up
    period = ctx.config.trend_template.rising_ma_period_days
    if len(sma200.dropna()) < period + 1:
        results.append(Result.na_("not enough 200MA history", name=CHECK_NAMES[2], layer=LAYER))
    else:
        past = float(sma200.iloc[-(period + 1)])
        v = f"200MA now={s200:.2f} vs {period}bars ago={past:.2f}"
        rising = s200 > past
        results.append(
            Result.pass_(v, f"200MA rising over {period} bars", name=CHECK_NAMES[2], layer=LAYER)
            if rising
            else Result.fail_(v, f"200MA rising over {period} bars", name=CHECK_NAMES[2], layer=LAYER)
        )

    # TT4: 50MA > 150MA and 50MA > 200MA
    v = f"50MA={s50:.2f} 150MA={s150:.2f} 200MA={s200:.2f}"
    r = (s50 > s150) and (s50 > s200)
    results.append(
        Result.pass_(v, "50MA > 150MA AND 50MA > 200MA", name=CHECK_NAMES[3], layer=LAYER)
        if r
        else Result.fail_(v, "50MA > 150MA AND 50MA > 200MA", name=CHECK_NAMES[3], layer=LAYER)
    )

    # TT5: close > 50MA
    v = f"close={last_close:.2f} 50MA={s50:.2f}"
    r = last_close > s50
    results.append(
        Result.pass_(v, "close > 50MA", name=CHECK_NAMES[4], layer=LAYER)
        if r else Result.fail_(v, "close > 50MA", name=CHECK_NAMES[4], layer=LAYER)
    )

    # TT6/TT7: 52-week high/low (use last 252 bars = 1 trading year)
    lookback_52w = min(252, len(closes))
    window = closes.iloc[-lookback_52w:]
    low_52w = float(window.min())
    high_52w = float(window.max())

    # TT6: price >= 30% above 52w low
    if low_52w <= 0:
        results.append(Result.na_("52w low non-positive", name=CHECK_NAMES[5], layer=LAYER))
    else:
        above_pct = (last_close - low_52w) / low_52w * 100
        threshold = ctx.config.trend_template.low_52w_min_pct
        v = f"+{above_pct:.1f}% above 52w low"
        rule = f">= {threshold}% above 52w low"
        results.append(
            Result.pass_(v, rule, name=CHECK_NAMES[5], layer=LAYER)
            if above_pct >= threshold
            else Result.fail_(v, rule, name=CHECK_NAMES[5], layer=LAYER)
        )

    # TT7: price within 25% of 52w high
    if high_52w <= 0:
        results.append(Result.na_("52w high non-positive", name=CHECK_NAMES[6], layer=LAYER))
    else:
        below_pct = (high_52w - last_close) / high_52w * 100
        threshold = ctx.config.trend_template.high_52w_margin_pct
        v = f"-{below_pct:.1f}% from 52w high"
        rule = f"<= {threshold}% below 52w high"
        results.append(
            Result.pass_(v, rule, name=CHECK_NAMES[6], layer=LAYER)
            if below_pct <= threshold
            else Result.fail_(v, rule, name=CHECK_NAMES[6], layer=LAYER)
        )

    # TT8: RS rank >= threshold (or fallback excess return)
    # Delegates ranking math to swing.evaluation.rs.compute_rs — one source of truth.
    threshold = ctx.config.rs.rs_rank_min_pass
    extreme = ctx.config.rs.fallback_extreme_pct / 100
    rs = compute_rs(
        ctx.ticker,
        ctx.batch.returns_12w_by_ticker,
        ctx.batch.universe_tickers,
        spy_return=ctx.batch.spy_return_12w,
    )

    if rs.method == "unavailable":
        results.append(Result.na_("no 12w return available", name=CHECK_NAMES[7], layer=LAYER))
    elif rs.method == "universe":
        assert rs.rank is not None  # guaranteed by compute_rs contract
        v = f"RS rank {rs.rank} (universe v{ctx.batch.universe_version})"
        rule = f"RS rank >= {threshold}"
        results.append(
            Result.pass_(v, rule, name=CHECK_NAMES[7], layer=LAYER)
            if rs.rank >= threshold
            else Result.fail_(v, rule, name=CHECK_NAMES[7], layer=LAYER)
        )
    else:  # method == "fallback_spy"
        assert rs.return_vs_spy is not None
        v = f"fallback, excess={rs.return_vs_spy:+.2%} vs SPY 12w"
        rule = f"outside universe; pass if excess >= +{extreme:.0%}"
        if rs.return_vs_spy >= extreme:
            results.append(Result.pass_(v, rule, name=CHECK_NAMES[7], layer=LAYER))
        elif rs.return_vs_spy <= -extreme:
            results.append(Result.fail_(v, rule, name=CHECK_NAMES[7], layer=LAYER))
        else:
            results.append(Result.na_(v, name=CHECK_NAMES[7], layer=LAYER))

    return tuple(results)
