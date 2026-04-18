"""Short-MA stack (10>20>50) + all three MAs rising over 5 bars."""
from __future__ import annotations

from swing.evaluation.context import CandidateContext
from swing.evaluation.criteria._base import Result, sma

STACK_NAME = "ma_stack_10_20_50"
RISING_NAME = "ma_short_rising"
LAYER = "vcp"


def evaluate(ctx: CandidateContext) -> tuple[Result, Result]:
    closes = ctx.ohlcv["Close"]
    if len(closes) < 55:
        na = Result.na_(f"need 55 bars, have {len(closes)}", name=STACK_NAME, layer=LAYER)
        return na, na.with_identity(RISING_NAME, LAYER)

    ma10 = sma(closes, 10)
    ma20 = sma(closes, 20)
    ma50 = sma(closes, 50)

    a, b, c = float(ma10.iloc[-1]), float(ma20.iloc[-1]), float(ma50.iloc[-1])
    stack_value = f"10MA={a:.2f} 20MA={b:.2f} 50MA={c:.2f}"
    stack_rule = "10MA > 20MA > 50MA"
    stack_result = (
        Result.pass_(stack_value, stack_rule, name=STACK_NAME, layer=LAYER)
        if a > b > c
        else Result.fail_(stack_value, stack_rule, name=STACK_NAME, layer=LAYER)
    )

    def _rising(s):
        if len(s.dropna()) < 6:
            return None
        return float(s.iloc[-1]) > float(s.iloc[-6])

    r10 = _rising(ma10)
    r20 = _rising(ma20)
    r50 = _rising(ma50)
    rising_rule = "all three short MAs rising over 5 bars"
    rising_value = f"10:{r10} 20:{r20} 50:{r50}"
    if r10 and r20 and r50:
        rising_result = Result.pass_(rising_value, rising_rule, name=RISING_NAME, layer=LAYER)
    else:
        rising_result = Result.fail_(rising_value, rising_rule, name=RISING_NAME, layer=LAYER)

    return stack_result, rising_result
