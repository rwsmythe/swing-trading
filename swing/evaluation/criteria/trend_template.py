"""Minervini Trend Template — 8 structural checks (spec §4.1)."""
from __future__ import annotations

from dataclasses import dataclass

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


@dataclass(frozen=True)
class StructuralCheck:
    """One TT1-TT5 structural check result (status + display strings).

    status: 'pass' | 'fail' | 'na'. For 'na', `value` carries the reason and
    `rule` is "" (mirrors Result.na_).
    """

    name: str
    status: str
    value: str
    rule: str


def structural_checks(closes, *, rising_period: int) -> tuple[StructuralCheck, ...]:
    """Compute the TT1-TT5 structural Trend-Template checks from `closes`.

    ONE source of truth for the TT1-TT5 math, shared by evaluate() (which
    converts these to Result rows -- byte-identical) and structural_stage()
    (which maps them to a regime label). TT6-TT8 stay in evaluate() (they need
    52w-window / batch-RS context not available at the live render sites).
    """
    if len(closes) < 200:
        reason = f"need 200 bars, have {len(closes)}"
        return tuple(
            StructuralCheck(name=n, status="na", value=reason, rule="")
            for n in CHECK_NAMES[:5]
        )

    last_close = float(closes.iloc[-1])
    sma50 = sma(closes, 50)
    sma150 = sma(closes, 150)
    sma200 = sma(closes, 200)
    s50 = float(sma50.iloc[-1])
    s150 = float(sma150.iloc[-1])
    s200 = float(sma200.iloc[-1])

    checks: list[StructuralCheck] = []

    # TT1: close > 150MA and close > 200MA
    v = f"close={last_close:.2f} 150MA={s150:.2f} 200MA={s200:.2f}"
    ok = (last_close > s150) and (last_close > s200)
    checks.append(StructuralCheck(
        name=CHECK_NAMES[0], status="pass" if ok else "fail",
        value=v, rule="close > 150MA AND close > 200MA",
    ))

    # TT2: 150MA > 200MA
    v = f"150MA={s150:.2f} 200MA={s200:.2f}"
    ok = s150 > s200
    checks.append(StructuralCheck(
        name=CHECK_NAMES[1], status="pass" if ok else "fail",
        value=v, rule="150MA > 200MA",
    ))

    # TT3: 200MA trending up over `rising_period` bars
    if len(sma200.dropna()) < rising_period + 1:
        checks.append(StructuralCheck(
            name=CHECK_NAMES[2], status="na",
            value="not enough 200MA history", rule="",
        ))
    else:
        past = float(sma200.iloc[-(rising_period + 1)])
        v = f"200MA now={s200:.2f} vs {rising_period}bars ago={past:.2f}"
        ok = s200 > past
        checks.append(StructuralCheck(
            name=CHECK_NAMES[2], status="pass" if ok else "fail",
            value=v, rule=f"200MA rising over {rising_period} bars",
        ))

    # TT4: 50MA > 150MA and 50MA > 200MA
    v = f"50MA={s50:.2f} 150MA={s150:.2f} 200MA={s200:.2f}"
    ok = (s50 > s150) and (s50 > s200)
    checks.append(StructuralCheck(
        name=CHECK_NAMES[3], status="pass" if ok else "fail",
        value=v, rule="50MA > 150MA AND 50MA > 200MA",
    ))

    # TT5: close > 50MA
    v = f"close={last_close:.2f} 50MA={s50:.2f}"
    ok = last_close > s50
    checks.append(StructuralCheck(
        name=CHECK_NAMES[4], status="pass" if ok else "fail",
        value=v, rule="close > 50MA",
    ))

    return tuple(checks)


def structural_stage(closes, *, rising_period: int) -> str:
    """Map the TT1-TT5 structural checks to a regime label.

    All five pass -> 'stage_2'; any fail/NA (incl. insufficient bars) ->
    'undefined'. TT6/TT7 (52w high/low) + TT8 (RS rank) are stock-selection
    criteria, not meaningful for the index benchmark vs itself, so the live
    market-weather regime uses the structural TT1-TT5 set (OQ-3a).
    """
    checks = structural_checks(closes, rising_period=rising_period)
    return "stage_2" if all(c.status == "pass" for c in checks) else "undefined"


def _check_to_result(c: StructuralCheck) -> Result:
    if c.status == "pass":
        return Result.pass_(c.value, c.rule, name=c.name, layer=LAYER)
    if c.status == "fail":
        return Result.fail_(c.value, c.rule, name=c.name, layer=LAYER)
    return Result.na_(c.value, name=c.name, layer=LAYER)


def evaluate(ctx: CandidateContext) -> tuple[Result, ...]:
    closes = ctx.ohlcv["Close"]
    period = ctx.config.trend_template.rising_ma_period_days

    # TT1-TT5 via the shared structural helper (ONE source of truth).
    results: list[Result] = [
        _check_to_result(c)
        for c in structural_checks(closes, rising_period=period)
    ]

    if len(closes) < 200:
        # TT6-TT8 also NA with the legacy message (byte-identical pre-refactor).
        results += [
            Result.na_(f"need 200 bars, have {len(closes)}", name=n, layer=LAYER)
            for n in CHECK_NAMES[5:]
        ]
        return tuple(results)

    last_close = float(closes.iloc[-1])

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
