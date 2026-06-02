"""F-2: structural_checks / structural_stage + evaluate() byte-identical
regression. The evaluate() 8-criterion output MUST NOT change after the
TT1-TT5 extraction (OQ-3a; the two-tier helper is reuse, not behavior change).

The _GOLDEN_* constants below were captured from the PRE-refactor evaluate()
via repr(tuple(evaluate(ctx))) over four canonical fixtures (all-pass uptrend,
fail downtrend, TT3-NA boundary at 205 bars, <200 early-return). String-repr
equality is exact (Result is a frozen dataclass) and needs no eval scope."""
from __future__ import annotations

import numpy as np
import pandas as pd

from swing.evaluation.context import BatchContext, CandidateContext, MarketContext
from swing.evaluation.criteria.trend_template import (
    CHECK_NAMES,
    StructuralCheck,
    evaluate,
    structural_checks,
    structural_stage,
)


def _closes(n: int, lo: float, hi: float) -> pd.Series:
    idx = pd.date_range("2024-01-01", periods=n, freq="B")
    return pd.Series(np.linspace(lo, hi, n), index=idx, name="Close")


def _uptrend_closes(n: int) -> pd.Series:
    return _closes(n, 100.0, 300.0)


def _make_ctx(closes_list, sample_config):
    """Mirror the golden-capture ctx construction EXACTLY (same index anchor +
    batch) so the byte-identical repr goldens match."""
    idx = pd.bdate_range(end="2026-04-17", periods=len(closes_list))
    df = pd.DataFrame(
        {"Open": closes_list, "High": [c * 1.01 for c in closes_list],
         "Low": [c * 0.99 for c in closes_list], "Close": closes_list,
         "Volume": [1_000_000] * len(closes_list)},
        index=idx,
    )
    return CandidateContext(
        ticker="T", ohlcv=df, config=sample_config,
        batch=BatchContext(
            returns_12w_by_ticker={"T": 0.50},
            universe_tickers=("T",),
            universe_version="test-v1",
            universe_hash="deadbeef",
            spy_return_12w=0.0,
        ),
        market=MarketContext(),
        current_equity=1000.0,
    )


# ---------------------------------------------------------------------------
# structural_checks / structural_stage unit tests
# ---------------------------------------------------------------------------


def test_structural_checks_uptrend_all_pass():
    closes = _uptrend_closes(260)
    checks = structural_checks(closes, rising_period=21)
    assert len(checks) == 5
    assert all(isinstance(c, StructuralCheck) for c in checks)
    assert [c.name for c in checks] == list(CHECK_NAMES[:5])
    assert all(c.status == "pass" for c in checks)


def test_structural_stage_uptrend_is_stage_2():
    closes = _uptrend_closes(260)
    assert structural_stage(closes, rising_period=21) == "stage_2"


def test_structural_stage_short_history_is_undefined():
    closes = _uptrend_closes(150)  # < 200 -> TT1-TT5 NA -> undefined
    assert structural_stage(closes, rising_period=21) == "undefined"


def test_structural_stage_downtrend_is_undefined():
    closes = _closes(260, 300.0, 100.0)  # fails -> undefined
    assert structural_stage(closes, rising_period=21) == "undefined"


def test_structural_stage_semantic_is_tt1_tt5_only_acceptance():
    """ACCEPTANCE GUARDRAIL (Codex R1 Major #6; OQ-3a LOCK): market-weather
    'stage_2' means the structural TT1-TT5 checks pass -- a DIFFERENT rule than
    current_stage's 8/8 trend_template definition. TT6/TT7 (52w high/low) + TT8
    (RS rank) are stock-selection criteria, not meaningful for the index
    benchmark vs itself. This pins the documented divergence: structural_stage
    consults EXACTLY the 5 structural checks (TT1-TT5), never the 8."""
    closes = _uptrend_closes(260)
    checks = structural_checks(closes, rising_period=21)
    assert len(checks) == 5
    assert [c.name for c in checks] == list(CHECK_NAMES[:5])
    assert all(c.name not in CHECK_NAMES[5:] for c in checks)
    assert structural_stage(closes, rising_period=21) == "stage_2"


def test_structural_checks_tt3_na_boundary():
    # 205 bars: >=200 (not the early-return) but < rising_period+1 200MA points
    # -> TT3 NA via the "not enough 200MA history" path.
    checks = structural_checks(_uptrend_closes(205), rising_period=21)
    tt3 = checks[2]
    assert tt3.name == "TT3_200_rising"
    assert tt3.status == "na"
    assert tt3.value == "not enough 200MA history"


# ---------------------------------------------------------------------------
# evaluate() byte-identical full-tuple golden (MANDATORY; Codex R1 Major #3)
# ---------------------------------------------------------------------------

_GOLDEN_A = "(Result(name='TT1_above_150_200', layer='trend_template', result='pass', value='close=300.00 150MA=242.47 200MA=223.17', rule='close > 150MA AND close > 200MA', metrics=()), Result(name='TT2_150_above_200', layer='trend_template', result='pass', value='150MA=242.47 200MA=223.17', rule='150MA > 200MA', metrics=()), Result(name='TT3_200_rising', layer='trend_template', result='pass', value='200MA now=223.17 vs 21bars ago=206.95', rule='200MA rising over 21 bars', metrics=()), Result(name='TT4_50_above_150_200', layer='trend_template', result='pass', value='50MA=281.08 150MA=242.47 200MA=223.17', rule='50MA > 150MA AND 50MA > 200MA', metrics=()), Result(name='TT5_above_50', layer='trend_template', result='pass', value='close=300.00 50MA=281.08', rule='close > 50MA', metrics=()), Result(name='TT6_above_52w_low_30pct', layer='trend_template', result='pass', value='+182.5% above 52w low', rule='>= 30.0% above 52w low', metrics=()), Result(name='TT7_within_52w_high_25pct', layer='trend_template', result='pass', value='-0.0% from 52w high', rule='<= 25.0% below 52w high', metrics=()), Result(name='TT8_rs_rank', layer='trend_template', result='fail', value='RS rank 0 (universe vtest-v1)', rule='RS rank >= 70', metrics=()))"

_GOLDEN_B = "(Result(name='TT1_above_150_200', layer='trend_template', result='fail', value='close=100.00 150MA=157.53 200MA=176.83', rule='close > 150MA AND close > 200MA', metrics=()), Result(name='TT2_150_above_200', layer='trend_template', result='fail', value='150MA=157.53 200MA=176.83', rule='150MA > 200MA', metrics=()), Result(name='TT3_200_rising', layer='trend_template', result='fail', value='200MA now=176.83 vs 21bars ago=193.05', rule='200MA rising over 21 bars', metrics=()), Result(name='TT4_50_above_150_200', layer='trend_template', result='fail', value='50MA=118.92 150MA=157.53 200MA=176.83', rule='50MA > 150MA AND 50MA > 200MA', metrics=()), Result(name='TT5_above_50', layer='trend_template', result='fail', value='close=100.00 50MA=118.92', rule='close > 50MA', metrics=()), Result(name='TT6_above_52w_low_30pct', layer='trend_template', result='fail', value='+0.0% above 52w low', rule='>= 30.0% above 52w low', metrics=()), Result(name='TT7_within_52w_high_25pct', layer='trend_template', result='fail', value='-66.0% from 52w high', rule='<= 25.0% below 52w high', metrics=()), Result(name='TT8_rs_rank', layer='trend_template', result='fail', value='RS rank 0 (universe vtest-v1)', rule='RS rank >= 70', metrics=()))"

_GOLDEN_C = "(Result(name='TT1_above_150_200', layer='trend_template', result='pass', value='close=300.00 150MA=226.96 200MA=202.45', rule='close > 150MA AND close > 200MA', metrics=()), Result(name='TT2_150_above_200', layer='trend_template', result='pass', value='150MA=226.96 200MA=202.45', rule='150MA > 200MA', metrics=()), Result(name='TT3_200_rising', layer='trend_template', result='na', value='not enough 200MA history', rule='', metrics=()), Result(name='TT4_50_above_150_200', layer='trend_template', result='pass', value='50MA=275.98 150MA=226.96 200MA=202.45', rule='50MA > 150MA AND 50MA > 200MA', metrics=()), Result(name='TT5_above_50', layer='trend_template', result='pass', value='close=300.00 50MA=275.98', rule='close > 50MA', metrics=()), Result(name='TT6_above_52w_low_30pct', layer='trend_template', result='pass', value='+200.0% above 52w low', rule='>= 30.0% above 52w low', metrics=()), Result(name='TT7_within_52w_high_25pct', layer='trend_template', result='pass', value='-0.0% from 52w high', rule='<= 25.0% below 52w high', metrics=()), Result(name='TT8_rs_rank', layer='trend_template', result='fail', value='RS rank 0 (universe vtest-v1)', rule='RS rank >= 70', metrics=()))"

_GOLDEN_D = "(Result(name='TT1_above_150_200', layer='trend_template', result='na', value='need 200 bars, have 150', rule='', metrics=()), Result(name='TT2_150_above_200', layer='trend_template', result='na', value='need 200 bars, have 150', rule='', metrics=()), Result(name='TT3_200_rising', layer='trend_template', result='na', value='need 200 bars, have 150', rule='', metrics=()), Result(name='TT4_50_above_150_200', layer='trend_template', result='na', value='need 200 bars, have 150', rule='', metrics=()), Result(name='TT5_above_50', layer='trend_template', result='na', value='need 200 bars, have 150', rule='', metrics=()), Result(name='TT6_above_52w_low_30pct', layer='trend_template', result='na', value='need 200 bars, have 150', rule='', metrics=()), Result(name='TT7_within_52w_high_25pct', layer='trend_template', result='na', value='need 200 bars, have 150', rule='', metrics=()), Result(name='TT8_rs_rank', layer='trend_template', result='na', value='need 200 bars, have 150', rule='', metrics=()))"


def test_evaluate_full_tuple_byte_identical_fixture_a(sample_config):
    ctx = _make_ctx(list(np.linspace(100.0, 300.0, 260)), sample_config)
    assert repr(tuple(evaluate(ctx))) == _GOLDEN_A


def test_evaluate_full_tuple_byte_identical_fixture_b(sample_config):
    ctx = _make_ctx(list(np.linspace(300.0, 100.0, 260)), sample_config)
    assert repr(tuple(evaluate(ctx))) == _GOLDEN_B


def test_evaluate_full_tuple_byte_identical_fixture_c_tt3_na(sample_config):
    ctx = _make_ctx(list(np.linspace(100.0, 300.0, 205)), sample_config)
    assert repr(tuple(evaluate(ctx))) == _GOLDEN_C


def test_evaluate_full_tuple_byte_identical_fixture_d_under_200(sample_config):
    ctx = _make_ctx(list(np.linspace(100.0, 300.0, 150)), sample_config)
    assert repr(tuple(evaluate(ctx))) == _GOLDEN_D


def test_evaluate_under_200_bars_all_na_unchanged(sample_config):
    ctx = _make_ctx(list(np.linspace(100.0, 300.0, 150)), sample_config)
    results = evaluate(ctx)
    assert len(results) == 8
    assert all(r.result == "na" for r in results)
    assert all(r.value == "need 200 bars, have 150" for r in results)
    assert [r.name for r in results] == list(CHECK_NAMES)
