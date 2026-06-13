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

import matplotlib.pyplot as plt
import pandas as pd


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


def _market_weather_vol_ax():
    """Phase 14 SB3 T-3.4: market_weather is now an mplfinance candlestick
    chart (not a plt.subplots line chart), so the volume axis is resolved by
    ROLE via the shared helper rather than by ``axes[1]`` positional index.
    Mirrors the production renderer's MA windows (50, 200) + volume=True.
    """
    from swing.web.charts import (
        _normalize_ohlc_for_mpf,
        _render_candles_fig,
        _resolve_volume_ax,
    )

    bars = _make_bars()
    df = _normalize_ohlc_for_mpf(bars)
    fig, price_ax, vol_ax = _render_candles_fig(
        df, ma_windows=(50, 200), figsize=(4, 1.5), volume=True,
    )
    resolved = _resolve_volume_ax(fig, price_ax)
    return fig, resolved


def test_render_market_weather_volume_y_tick_labels_stripped():
    """Item 3 (Phase 14 SB3 T-3.4): volume y-tick labels empty on the
    candlestick market_weather chart; volume axis resolved by ROLE.

    Signature: ``render_market_weather_svg(*, bars, trend_template_state)``
    -- no ``ticker`` parameter. The renderer routes through
    ``_render_candles_fig`` which strips volume tick labels on the
    role-resolved volume axis.
    """
    fig, ax_vol = _market_weather_vol_ax()
    try:
        assert ax_vol is not None
        labels = [t.get_text() for t in ax_vol.get_yticklabels()]
        assert labels == [] or all(not lbl for lbl in labels), (
            f"Item 3: ax_vol y-tick labels must be empty; got {labels!r}"
        )
    finally:
        plt.close(fig)


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


# ---------------------------------------------------------------------------
# Phase 17 — 17-D.5: weather mini-chart declutter (drop the mpf-default
# "Price"/"Volume  $10^{6}$" ylabels that overlap the rotated date ticks)
# + add the 20MA line. PRODUCTION-PATH tests: they spy on the renderer's
# final serialize hook (_svg_bytes_from_fig) to capture the REAL fig built
# by render_market_weather_svg, NOT a _render_candles_fig rebuild (which
# still carries the mpf-default labels + the pre-fix 50/200 MA set and would
# FALSE-PASS per the brief §3 LOCK).
# ---------------------------------------------------------------------------


def _capture_fig_via_serialize_spy(monkeypatch, render_call):
    """Run a production renderer, capturing the fig at its serialize boundary.

    Monkeypatches ``swing.web.charts._svg_bytes_from_fig`` (the module-level
    name the renderer resolves at call time) with a spy that snapshots the
    fig's axis ylabels + price-axis line count BEFORE delegating to the real
    impl (which serializes and ``plt.close``s the fig). This exercises the
    actual production wiring inside ``render_*_svg``.
    """
    import swing.web.charts as charts

    captured: dict = {}
    real = charts._svg_bytes_from_fig

    def _spy(fig):
        price_ax = fig.axes[0]
        vol_ax = charts._resolve_volume_ax(fig, price_ax)
        captured["price_ylabel"] = price_ax.get_ylabel()
        captured["vol_ylabel"] = (
            vol_ax.get_ylabel() if vol_ax is not None else None
        )
        captured["n_price_lines"] = len(price_ax.get_lines())
        return real(fig)

    monkeypatch.setattr(charts, "_svg_bytes_from_fig", _spy)
    out = render_call(charts)
    assert isinstance(out, bytes) and out, "renderer must return SVG bytes"
    assert "price_ylabel" in captured, "serialize spy did not fire"
    return captured


def test_render_market_weather_strips_axis_ylabels_production_path(monkeypatch):
    """17-D.5: production render_market_weather_svg clears BOTH the price
    ('Price') and volume ('Volume  $10^{6}$') mpf-default ylabels.

    FAILS pre-fix: the renderer set no ylabels, so the price panel carried
    mpf's default "Price" and the volume panel "Volume  $10^{6}$".
    """
    captured = _capture_fig_via_serialize_spy(
        monkeypatch,
        lambda charts: charts.render_market_weather_svg(
            bars=_make_bars(n=220), trend_template_state="stage_2",
        ),
    )
    assert captured["price_ylabel"] == "", (
        "17-D.5: weather price ylabel must be cleared; got "
        f"{captured['price_ylabel']!r}"
    )
    assert captured["vol_ylabel"] == "", (
        "17-D.5: weather volume ylabel must be cleared; got "
        f"{captured['vol_ylabel']!r}"
    )
    # Belt-and-suspenders: the volume label must no longer start with "Volume"
    # (the mpf default + its $10^{6}$ scale-factor suffix).
    assert not (captured["vol_ylabel"] or "").startswith("Volume")


def test_render_market_weather_draws_three_ma_lines_production_path(monkeypatch):
    """17-D.5: production render_market_weather_svg now draws THREE MA
    addplots (20/50/200) on the price axis.

    FAILS pre-fix: the renderer passed ma_windows=(50, 200) -> 2 MA lines.
    With >=200 bars none are skipped, so post-fix the price axis carries
    exactly 3 Line2D artists (candles are drawn as collections, not lines).
    """
    captured = _capture_fig_via_serialize_spy(
        monkeypatch,
        lambda charts: charts.render_market_weather_svg(
            bars=_make_bars(n=220), trend_template_state="stage_2",
        ),
    )
    assert captured["n_price_lines"] == 3, (
        "17-D.5: weather chart must draw 3 MA lines (20/50/200); got "
        f"{captured['n_price_lines']}"
    )


def test_render_ticker_detail_preserves_ylabels_production_path(monkeypatch):
    """17-D.5 scope LOCK: the weather-only declutter must NOT bleed into
    render_ticker_detail_svg, which keeps its explicit 'Price (USD)' /
    'Volume' ylabels. Production-path guard (passes pre- and post-fix).
    """
    captured = _capture_fig_via_serialize_spy(
        monkeypatch,
        lambda charts: charts.render_ticker_detail_svg(
            ticker="AAPL", bars=_make_bars(n=220),
        ),
    )
    assert captured["price_ylabel"] == "Price (USD)"
    assert captured["vol_ylabel"] == "Volume"
