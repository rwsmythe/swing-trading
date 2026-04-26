import pandas as pd
import numpy as np
from swing.evaluation.patterns.flag_classifier import classify_flag


def _flat_bars(n: int, start_close: float = 100.0) -> pd.DataFrame:
    """Build n bars with constant OHLCV — used as a no-detect baseline."""
    idx = pd.date_range("2026-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": start_close, "High": start_close, "Low": start_close,
         "Close": start_close, "Volume": 1_000_000.0}, index=idx,
    )


def test_module_imports():
    from swing.evaluation.patterns.flag_classifier import (
        FlagClassificationResult,
        classify_flag,
    )

    assert callable(classify_flag)
    assert FlagClassificationResult is not None


def test_data_window_gate_below_threshold_returns_none():
    res = classify_flag(_flat_bars(35))
    assert res.detected is False
    assert res.pattern == "none"


def test_data_window_gate_at_threshold_enters_search():
    # 36 bars — minimum. Flat bars still fail later gates, but classify_flag
    # MUST run the search instead of short-circuiting.
    res = classify_flag(_flat_bars(36))
    assert res.detected is False
    # components_json must populate (best-attempted baseline) — proof the
    # search ran and was not short-circuited by data_window.
    assert "pole_M" in res.components


from tests.evaluation.patterns._synthetic import make_flag_bars


def test_default_synthetic_flag_is_detected():
    bars = make_flag_bars()
    res = classify_flag(bars)
    assert res.detected is True
    assert res.pattern == "flag"
    assert 0.0 < res.confidence <= 1.0


def test_pole_gain_gate_at_threshold_below_rejects():
    bars = make_flag_bars(pole_gain_pct=0.299)
    res = classify_flag(bars)
    assert res.detected is False
    assert res.pattern == "none"


def test_pole_gain_gate_at_threshold_above_passes():
    bars = make_flag_bars(pole_gain_pct=0.301)
    res = classify_flag(bars)
    assert res.detected is True
    assert res.pattern == "flag"


def test_pole_gain_gate_is_threshold_sensitive():
    """Discriminating-test discipline: passing a tightened threshold via
    cfg argument must flip a previously-passing fixture to rejection.
    Proves the test pair is actually sensitive to the threshold value."""
    from swing.config import ClassifierConfig
    bars = make_flag_bars(pole_gain_pct=0.31)
    # Default cfg → passes.
    assert classify_flag(bars).detected is True
    # Tightened cfg → rejects.
    cfg = ClassifierConfig(flag_pole_gain_min=0.40)
    assert classify_flag(bars, cfg=cfg).detected is False


def test_pullback_depth_gate_above_threshold_rejects():
    bars = make_flag_bars(pullback_pct=0.151)
    res = classify_flag(bars)
    assert res.detected is False


def test_pullback_depth_gate_below_threshold_passes():
    bars = make_flag_bars(pullback_pct=0.149)
    res = classify_flag(bars)
    assert res.detected is True


# tightness_ratio gate threshold = 0.6 (cfg.flag_tightness_ratio_max).
# Empirical mapping: measured tightness_ratio = flag_tightness_factor *
# (pole_close_avg / flag_close_avg) ≈ flag_tightness_factor * 0.9 in this
# fixture (pole avg close ≈ 117.5, flag avg close ≈ 130 at default pullback).
# So flag_tightness_factor ≈ 0.667 lands measured tightness ≈ 0.5998 (passes
# 0.6 gate) and 0.668 lands measured ≈ 0.5892 but search shifts to a window
# that fails (rejected). Verified at the REPL across [0.65, 0.70].
def test_tightness_ratio_gate_above_threshold_rejects():
    bars = make_flag_bars(flag_tightness_factor=0.668)
    res = classify_flag(bars)
    assert res.detected is False


def test_tightness_ratio_gate_below_threshold_passes():
    bars = make_flag_bars(flag_tightness_factor=0.667)
    res = classify_flag(bars)
    assert res.detected is True


def test_volume_contraction_gate_above_threshold_rejects():
    bars = make_flag_bars(flag_volume_factor=0.701)
    res = classify_flag(bars)
    assert res.detected is False


def test_volume_contraction_gate_below_threshold_passes():
    bars = make_flag_bars(flag_volume_factor=0.699)
    res = classify_flag(bars)
    assert res.detected is True


def test_ma_structure_not_stacked_rejects():
    # Override the full pre-run window (50 bars) with a steep downtrend so
    # SMA50 dominates and prevents SMA10 > SMA20 > SMA50 stacking. Plan's
    # n_pre=30 leaves 20 flat bars at start_close which preserves stacking;
    # n_pre=50 + linspace(180, 100, 50) flips the order at flag_start.
    bars = make_flag_bars()
    closes = bars["Close"].to_numpy().copy()
    n_pre = 50
    closes[:n_pre] = np.linspace(180.0, 100.0, n_pre)  # downtrend into pole
    bars = bars.assign(Close=closes, Open=closes)
    res = classify_flag(bars)
    assert res.detected is False


def test_ma_structure_stacked_and_rising_passes():
    bars = make_flag_bars()
    res = classify_flag(bars)
    assert res.detected is True
