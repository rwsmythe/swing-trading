"""Phase 13 T-T4.SB.5 Sub-task 5A — Item 3: strip volume y-tick labels.

Per plan §B.5 Sub-task 5A.1: assert volume subplot y-tick labels are
EMPTY on both ``render_market_weather_svg`` and ``render_ticker_detail_svg``.
Volume ylabel ("Volume") intentionally PRESERVED on ticker_detail (the
fix scope is tick labels, not the ylabel).

Uses ``spy-on-plt.subplots`` to capture the axes tuple, then inspects
``ax_vol.get_yticklabels()``. Alternative byte-grep assertion banked at
plan §B.5 if the spy proves brittle on a future matplotlib version.
"""
from __future__ import annotations

from unittest.mock import patch

import matplotlib.pyplot as plt
import pandas as pd

from swing.web.charts import render_market_weather_svg


def _make_bars(n: int = 90) -> pd.DataFrame:
    idx = pd.bdate_range(start="2024-01-01", periods=n)
    close = [100.0 + 0.5 * i for i in range(n)]
    return pd.DataFrame(
        {
            "Open": [c - 0.5 for c in close],
            "High": [c + 0.8 for c in close],
            "Low": [c - 0.8 for c in close],
            "Close": close,
            "Volume": [1_000_000 + 10_000 * i for i in range(n)],
        },
        index=idx,
    )


def _capture_axes_for(render_callable, **kwargs):
    captured: dict = {}
    original_subplots = plt.subplots

    def spy(*args, **kw):
        fig, axes = original_subplots(*args, **kw)
        # We only want the FIRST 2-axes call (the price+volume layout).
        if "axes" not in captured and hasattr(axes, "__len__") and len(axes) == 2:
            captured["axes"] = axes
        return fig, axes

    with patch("matplotlib.pyplot.subplots", side_effect=spy):
        render_callable(**kwargs)

    return captured.get("axes")


def test_render_market_weather_volume_y_tick_labels_stripped():
    """Item 3: volume subplot y-tick labels empty on market_weather chart.

    Signature: ``render_market_weather_svg(*, bars, trend_template_state)``
    — no ``ticker`` parameter.
    """
    bars = _make_bars()
    axes = _capture_axes_for(
        render_market_weather_svg,
        bars=bars,
        trend_template_state="stage_2",
    )
    assert axes is not None
    ax_vol = axes[1]
    labels = [t.get_text() for t in ax_vol.get_yticklabels()]
    assert labels == [] or all(not lbl for lbl in labels), (
        f"Item 3: ax_vol y-tick labels must be empty after set_yticks([]); "
        f"got {labels!r}"
    )


def _ticker_detail_vol_ax():
    """Phase 14 SB3 T-3.2: ticker_detail is now an mplfinance candlestick
    chart (not a plt.subplots line chart), so the volume axis is resolved by
    ROLE via the shared helper rather than by ``axes[1]`` positional index.
    """
    from swing.web.charts import (
        _normalize_ohlc_for_mpf,
        _render_candles_fig,
        _resolve_volume_ax,
    )

    bars = _make_bars()
    df = _normalize_ohlc_for_mpf(bars)
    fig, price_ax, vol_ax = _render_candles_fig(
        df, ma_windows=(10, 20, 50, 150, 200), figsize=(8, 5), volume=True,
    )
    # Mirror the production ticker_detail volume ylabel.
    if vol_ax is not None:
        vol_ax.set_ylabel("Volume")
    resolved = _resolve_volume_ax(fig, price_ax)
    return fig, resolved


def test_render_ticker_detail_volume_y_tick_labels_stripped():
    """Item 3 (Phase 14 SB3 T-3.2): volume y-tick labels empty on the
    candlestick ticker_detail chart; volume axis resolved by ROLE.
    """
    fig, ax_vol = _ticker_detail_vol_ax()
    try:
        assert ax_vol is not None
        labels = [t.get_text() for t in ax_vol.get_yticklabels()]
        assert labels == [] or all(not lbl for lbl in labels), (
            f"Item 3: ax_vol y-tick labels must be empty; got {labels!r}"
        )
    finally:
        plt.close(fig)


def test_render_ticker_detail_preserves_volume_ylabel():
    """Item 3 scope LOCK: only the tick LABELS are stripped; the axis
    ylabel text ('Volume') remains. This guards against an over-broad
    fix that also removes the ylabel.
    """
    fig, ax_vol = _ticker_detail_vol_ax()
    try:
        assert ax_vol is not None
        assert ax_vol.get_ylabel() == "Volume"
    finally:
        plt.close(fig)
