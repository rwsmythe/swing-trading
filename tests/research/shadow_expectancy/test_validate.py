from __future__ import annotations

import json

import pytest

from research.harness.shadow_expectancy.io import Bar, parse_bar
from research.harness.shadow_expectancy.validate import (
    validate_bars,
    validate_candidate_levels,
    validate_signal,
)


def _ohlc(o, h, l, c, v=1000.0, provider="yfinance"):  # noqa: E741
    return json.dumps({"open": o, "high": h, "low": l, "close": c,
                       "volume": v, "provider": provider})


def test_parse_bar_reads_lowercase_keys():
    b = parse_bar(_ohlc(10.0, 11.0, 9.5, 10.5), session="2026-05-29")
    assert (b.open, b.high, b.low, b.close, b.session) == (10.0, 11.0, 9.5, 10.5, "2026-05-29")


def test_candidate_levels_ok():
    assert validate_candidate_levels(pivot=10.0, initial_stop=9.0) is None


@pytest.mark.parametrize("pivot,stop", [
    (0.0, -1.0), (-5.0, -6.0), (float("nan"), 1.0), (10.0, 10.0), (9.0, 10.0),
])
def test_candidate_levels_reject(pivot, stop):
    assert validate_candidate_levels(pivot=pivot, initial_stop=stop) == "invalid_ohlc"


def test_bars_reject_high_lt_low():
    bars = [Bar("2026-05-29", 10.0, 9.0, 11.0, 9.5)]  # high < low
    assert validate_bars(bars) == "invalid_ohlc"


def test_bars_reject_nan_and_negative():
    assert validate_bars([Bar("2026-05-29", 10.0, 11.0, -1.0, 10.5)]) == "invalid_ohlc"
    assert validate_bars([Bar("2026-05-29", 10.0, float("inf"), 9.0, 10.5)]) == "invalid_ohlc"


def test_bars_reject_non_chronological_and_duplicate():
    a = Bar("2026-05-30", 10.0, 11.0, 9.5, 10.5)
    b = Bar("2026-05-29", 10.0, 11.0, 9.5, 10.5)
    assert validate_bars([a, b]) == "invalid_ohlc"
    assert validate_bars([b, b]) == "invalid_ohlc"


def test_validate_signal_chains_levels_then_bars():
    good = [Bar("2026-05-29", 10.0, 11.0, 9.5, 10.5)]
    assert validate_signal(pivot=10.0, initial_stop=9.0, bars=good) is None
    assert validate_signal(pivot=10.0, initial_stop=10.0, bars=good) == "invalid_ohlc"
