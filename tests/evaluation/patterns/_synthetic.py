"""Synthetic OHLCV builders for pure-function classifier tests.

Discriminating-test discipline: each test varies ONE feature at the
gate threshold. Use these helpers as the baseline for those variations.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def make_flag_bars(
    *,
    pre_run_bars: int = 50,           # bars BEFORE the pole (uptrend setup
                                      # so SMA10/20/50 stack-and-rise at
                                      # flag start). MA-structure gate
                                      # (gate 5) requires flag_start_idx
                                      # >= 55; with pole_bars=10, flag_bars=8,
                                      # we need pre_run_bars >= 47 so the
                                      # rightmost flag anchor lands past
                                      # bar 55. Using 50 for headroom.
    pole_bars: int = 10,
    flag_bars: int = 8,
    pole_gain_pct: float = 0.40,      # pole_gain >= 0.30 default — passes gate 4
    pullback_pct: float = 0.10,       # pullback_depth — gate 6 default 0.15
    pole_atr_pct: float = 0.05,       # avg pole bar range / close
    flag_tightness_factor: float = 0.4,  # flag range / pole range — gate 7 ≤ 0.6
    flag_volume_factor: float = 0.5,  # flag avg vol / pole avg vol — gate 8 ≤ 0.7
    floor_holds: bool = True,         # gate 9
    pole_volume: float = 2_000_000.0,
    start_close: float = 100.0,
) -> pd.DataFrame:
    """Construct a synthetic 60-bar window: pre_run | pole | flag.

    Default parameters yield a detection-passing flag against the spec's
    default thresholds. Override one parameter per test to drive a single
    gate across its threshold.

    Geometry calibration (so synthetic params map 1:1 to measured values):
    - Pre-run: H = L = C = start_close (truly flat, no half-band). Bounds
      pole_low = start_close exactly when search M reaches into pre-run.
    - Pole: closes shifted by +pole_range/2 at start and -pole_range/2 at
      end so first-bar low = start_close and last-bar high = pole_top
      exactly. Result: measured pole_gain = pole_gain_pct exactly.
    - Flag: bottom-bar close shifted up by +flag_range/2 so the bottom
      bar's actual low = pole_top * (1 - pullback_pct). Result: measured
      pullback_depth = pullback_pct exactly.
    """
    n = pre_run_bars + pole_bars + flag_bars
    idx = pd.date_range("2026-01-01", periods=n, freq="B")
    closes = np.empty(n, dtype=float)

    # Pre-compute ranges (needed to offset closes for 1:1 mapping below).
    pole_top = start_close * (1.0 + pole_gain_pct)
    pole_range = pole_top * pole_atr_pct
    flag_range = pole_range * flag_tightness_factor

    # Pre-run: FLAT at start_close (H = L = C). Forces pole_low = start_close
    # for any M reaching into pre-run, so measured pole_gain matches the
    # synthetic pole_gain_pct exactly.
    closes[:pre_run_bars] = start_close

    # Pole: linear advance, but SHIFTED so first-bar low = start_close and
    # last-bar high = pole_top exactly. With H = C + pole_range/2 and
    # L = C - pole_range/2 (set below), this makes
    #   measured pole_gain = (pole_top - start_close) / start_close
    #                      = pole_gain_pct.
    closes[pre_run_bars:pre_run_bars + pole_bars] = np.linspace(
        start_close + pole_range / 2,
        pole_top - pole_range / 2,
        pole_bars,
    )

    # Flag: drift between pole_top and flag_low_target, with tightness driven
    # by flag_tightness_factor. Bottom-bar close shifted UP by flag_range/2
    # so the bottom bar's actual low (close - flag_range/2) equals
    # flag_low_target exactly. Result:
    #   measured pullback_depth = (pole_top - flag_low_target) / pole_top
    #                           = pullback_pct.
    flag_low_target = pole_top * (1.0 - pullback_pct)
    flag_idx_start = pre_run_bars + pole_bars
    half = flag_bars // 2
    flag_close = np.empty(flag_bars)
    bottom_close = flag_low_target + flag_range / 2
    if floor_holds:
        flag_close[:half] = np.linspace(pole_top * 0.99, bottom_close, half)
        flag_close[half:] = np.linspace(
            bottom_close * 1.005, pole_top * 0.985, flag_bars - half,
        )
    else:
        # Drifting-down floor — second-half min < first-half min.
        flag_close[:half] = np.linspace(pole_top * 0.99, bottom_close, half)
        flag_close[half:] = np.linspace(
            bottom_close * 0.99, bottom_close * 0.94, flag_bars - half,
        )
    closes[flag_idx_start:] = flag_close

    high = closes.copy()
    low = closes.copy()
    # Pre-run truly flat (no half-band) — see docstring.
    high[:pre_run_bars] = closes[:pre_run_bars]
    low[:pre_run_bars] = closes[:pre_run_bars]
    high[pre_run_bars:pre_run_bars + pole_bars] = (
        closes[pre_run_bars:pre_run_bars + pole_bars] + pole_range / 2
    )
    low[pre_run_bars:pre_run_bars + pole_bars] = (
        closes[pre_run_bars:pre_run_bars + pole_bars] - pole_range / 2
    )
    high[flag_idx_start:] = flag_close + flag_range / 2
    low[flag_idx_start:] = flag_close - flag_range / 2

    volume = np.empty(n)
    volume[:pre_run_bars] = pole_volume * 0.7
    volume[pre_run_bars:pre_run_bars + pole_bars] = pole_volume
    volume[flag_idx_start:] = pole_volume * flag_volume_factor

    return pd.DataFrame(
        {"Open": closes, "High": high, "Low": low, "Close": closes,
         "Volume": volume}, index=idx,
    )
