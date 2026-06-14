"""Phase 18 Arc 18-A — the shared OHLC finiteness predicate (C1).

ONE predicate consumed by BOTH write barriers (ohlcv_archive._trim_trailing_ragged
and temporal_metadata.build_ohlc_today_json + its caller). Uses math.isfinite
(NaN AND inf), matching the engine gate validate_bars; volume-exempt by
construction (callers omit it)."""
from __future__ import annotations

import numpy as np

from swing.data.ohlcv_finiteness import is_finite_ohlc

NAN = float("nan")
INF = float("inf")


def test_all_finite_returns_true():
    assert is_finite_ohlc(10.0, 11.0, 9.0, 10.5) is True


def test_nan_anywhere_returns_false():
    # the 2026-06-10 Close=NaN shape, plus NaN in the leading position.
    assert is_finite_ohlc(10.0, 11.0, 9.0, NAN) is False
    assert is_finite_ohlc(NAN, 11.0, 9.0, 10.5) is False


def test_inf_returns_false():
    # matches the engine gate's math.isfinite: +/-inf is non-finite too.
    assert is_finite_ohlc(10.0, INF, 9.0, 10.5) is False
    assert is_finite_ohlc(10.0, 11.0, -INF, 10.5) is False


def test_numpy_float_nan_returns_false():
    # the archive path passes numpy float64 values out of a DataFrame row.
    assert is_finite_ohlc(np.float64(10.0), np.float64("nan")) is False
    assert is_finite_ohlc(np.float64(10.0), np.float64(11.0)) is True


def test_empty_call_returns_true():
    # no values to reject -> True (matches "no OHLC columns -> no-op").
    assert is_finite_ohlc() is True


def test_finiteness_only_does_not_reject_negative():
    # LOCK 4 / no over-rejection: a negative value is FINITE -> True here.
    # Non-negativity stays the engine gate's job (validate_bars `>= 0`), NOT
    # this write barrier. Distinguishes a finiteness-only predicate from a
    # validate_bars copy.
    assert is_finite_ohlc(-5.0, 11.0, 9.0, 10.5) is True
