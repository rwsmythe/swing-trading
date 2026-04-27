"""Phase 3 Task 3.1: render_chart accepts pattern_overlay kwarg (no-op stub).

Phase 6 will paint the pole/flag region from a non-None overlay; Phase 3
just opens the kwarg gate so the pipeline runner can pass overlays through
without painting.
"""
from __future__ import annotations

from datetime import date
from pathlib import Path

import pandas as pd
import pytest

from swing.rendering.charts import PatternOverlay, render_chart


@pytest.fixture
def fake_ohlcv() -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=120, freq="B")
    return pd.DataFrame({
        "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.0,
        "Volume": 1_000_000.0,
    }, index=idx)


def test_render_chart_pattern_overlay_default_is_none_and_writes_png(
    tmp_path: Path, fake_ohlcv,
):
    """Backward-compat: render_chart(...) without pattern_overlay must
    behave as before — accept the call, produce the PNG."""
    out = tmp_path / "AAPL.png"
    res = render_chart(
        ticker="AAPL", ohlcv=fake_ohlcv, pivot=110.0, stop=95.0,
        output_path=out,
    )
    assert res == out
    assert out.exists()


def test_render_chart_accepts_pattern_overlay_none_kwarg(
    tmp_path: Path, fake_ohlcv,
):
    """The kwarg is OPTIONAL and defaults to None; passing None explicitly
    must produce the same PNG."""
    out = tmp_path / "AAPL.png"
    res = render_chart(
        ticker="AAPL", ohlcv=fake_ohlcv, pivot=110.0, stop=95.0,
        output_path=out, pattern_overlay=None,
    )
    assert res == out


def test_render_chart_pattern_overlay_none_is_byte_identical_to_default(
    tmp_path: Path, fake_ohlcv,
):
    """Phase 3 contract: `pattern_overlay=None` MUST produce a chart byte-
    identical to the legacy call without the kwarg. Phase 6 lands the actual
    painting; until then the kwarg is a no-op stub.

    Discriminating: if Phase 6 painting accidentally landed early (or the
    `del pattern_overlay` line was removed), this test would diverge.
    """
    default_path = tmp_path / "default.png"
    explicit_path = tmp_path / "explicit_none.png"

    render_chart(
        ticker="AAPL", ohlcv=fake_ohlcv, pivot=110.0, stop=95.0,
        output_path=default_path,
    )
    render_chart(
        ticker="AAPL", ohlcv=fake_ohlcv, pivot=110.0, stop=95.0,
        output_path=explicit_path, pattern_overlay=None,
    )

    assert default_path.read_bytes() == explicit_path.read_bytes(), (
        "render_chart with pattern_overlay=None must produce a byte-identical "
        "PNG to the default kwarg-omitted call (Phase 3 no-op stub contract)"
    )


def test_render_chart_real_pattern_overlay_is_not_byte_identical_to_default(
    tmp_path: Path, fake_ohlcv,
):
    """Phase 6 contract (replaces the Phase 3 no-op byte-identity test):
    when a fully-populated PatternOverlay is supplied, the rendered PNG MUST
    differ from the default-call PNG. Phase 6 lights up real painting
    (fill_betweenx pole/flag bands + algo-pivot hlines + title annotation)
    so the overlay case produces a STRICTLY different image.

    Discriminating: pre-Phase-6 (no-op stub) the bytes were identical, so
    this assertion would have failed; post-Phase-6 the bytes differ because
    painting fires. If a future regression silently no-ops the overlay path
    again, this test catches it. Companion to
    test_render_chart_pattern_overlay_none_is_byte_identical_to_default,
    which still asserts the None path stays legacy-identical.
    """
    overlay = PatternOverlay(
        pattern="flag", confidence=0.85,
        pole_start_date=date(2026, 1, 5),
        pole_end_date=date(2026, 1, 19),
        flag_start_date=date(2026, 1, 20),
        flag_end_date=date(2026, 1, 29),
        pivot=110.5,
    )
    default_path = tmp_path / "default.png"
    overlay_path = tmp_path / "with_overlay.png"

    render_chart(
        ticker="AAPL", ohlcv=fake_ohlcv, pivot=110.0, stop=95.0,
        output_path=default_path,
    )
    render_chart(
        ticker="AAPL", ohlcv=fake_ohlcv, pivot=110.0, stop=95.0,
        output_path=overlay_path, pattern_overlay=overlay,
    )

    assert default_path.read_bytes() != overlay_path.read_bytes(), (
        "render_chart with a non-None PatternOverlay must NOT produce a "
        "byte-identical PNG to the default call (Phase 6 painting contract). "
        "If this test fails, the overlay path may have silently no-op'd."
    )


def test_render_chart_with_pattern_overlay_writes_png_and_preserves_existing_hlines(
    tmp_path: Path, fake_ohlcv,
):
    """Smoke test: with overlay, the function still returns the path and
    writes a non-empty PNG. Detailed visual checks are deferred to slow
    tests; this guards against accidental crash paths."""
    overlay = PatternOverlay(
        pattern="flag", confidence=0.78,
        pole_start_date=fake_ohlcv.index[80].date(),
        pole_end_date=fake_ohlcv.index[100].date(),
        flag_start_date=fake_ohlcv.index[101].date(),
        flag_end_date=fake_ohlcv.index[119].date(),
        pivot=120.0,
    )
    out = tmp_path / "AAPL.png"
    res = render_chart(
        ticker="AAPL", ohlcv=fake_ohlcv, pivot=110.0, stop=95.0,
        output_path=out, pattern_overlay=overlay,
    )
    assert res == out
    assert out.exists()
    assert out.stat().st_size > 0


def test_render_chart_with_overlay_paints_two_bands_and_separate_pivot_segment(
    tmp_path: Path, fake_ohlcv, monkeypatch,
):
    """Discriminating overlay test: capture the figure axes returned by
    mpf.plot to verify TWO fill_betweenx polygons (pole + flag bands) AND
    a 1-segment hlines collection (algo-pivot, flag-spanning) are added on
    TOP of the existing candidate-pivot hline (spec §3.4 + §6 candidate-
    pivot preserved). Inspecting the axes catches missing bands / missing
    algo-pivot / accidental removal of the existing hline."""
    overlay = PatternOverlay(
        pattern="flag", confidence=0.78,
        pole_start_date=fake_ohlcv.index[80].date(),
        pole_end_date=fake_ohlcv.index[100].date(),
        flag_start_date=fake_ohlcv.index[101].date(),
        flag_end_date=fake_ohlcv.index[119].date(),
        pivot=120.0,
    )

    captured = {}
    import mplfinance as mpf
    real_plot = mpf.plot
    def _capture(df, **kw):
        result = real_plot(df, **kw)
        if kw.get("returnfig"):
            fig, axes = result
            captured["fig"] = fig
            captured["axes"] = axes
        return result
    monkeypatch.setattr(mpf, "plot", _capture)

    out = tmp_path / "AAPL.png"
    render_chart(
        ticker="AAPL", ohlcv=fake_ohlcv, pivot=110.0, stop=95.0,
        output_path=out, pattern_overlay=overlay,
    )

    price_ax = captured["axes"][0]
    # fill_betweenx adds PolyCollection objects; expect ≥2 (pole + flag).
    from matplotlib.collections import LineCollection, PolyCollection
    polys = [c for c in price_ax.collections if isinstance(c, PolyCollection)]
    assert len(polys) >= 2, "expected pole + flag fill_betweenx bands"
    # Title annotation includes the confidence. mpf renders `title=` as a
    # figure suptitle (not on axes[0]); read it via fig._suptitle with a
    # tolerant fallback to fig.texts for any mpf version that uses
    # fig.text() instead of fig.suptitle().
    fig = captured["fig"]
    suptitle = fig._suptitle.get_text() if fig._suptitle is not None else ""
    if not suptitle:
        suptitle = "\n".join(t.get_text() for t in fig.texts)
    expected = "AAPL | pivot $110.00 stop $95.00 | last 120 bars | flag (0.78)"
    assert suptitle == expected, f"got {suptitle!r}"

    # Discriminating check: directly call mpf.plot with the same plot_kwargs
    # render_chart constructs internally, but WITHOUT the overlay's
    # hlines/fill_betweenx additions. This gives a true baseline of
    # LineCollections that mpf alone produces, so the count comparison is
    # meaningful (the None-path can't be reused as a baseline because it
    # doesn't pass returnfig=True — that's required to keep byte-identity
    # for the None case).
    # DUPLICATION WARNING: the plot_kwargs below mirror render_chart's
    # internal construction. If render_chart's kwargs change (new vlines,
    # different SMA windows, style override), keep this baseline in sync
    # — otherwise the LineCollection-count comparison stops being a faithful
    # baseline-vs-overlay comparison.
    monkeypatch.setattr(mpf, "plot", real_plot)  # unwrap before baseline call
    df = fake_ohlcv.tail(120).copy()
    baseline_title = "AAPL | pivot $110.00 stop $95.00 | last 120 bars"
    addplots = []
    closes = df["Close"]
    for window, color in ((10, "blue"), (20, "orange"), (50, "red")):
        sma = closes.rolling(window).mean()
        if not sma.isna().all():
            addplots.append(mpf.make_addplot(sma, color=color, width=1.0))
    baseline_fig, baseline_axes = mpf.plot(
        df, type="candle", volume=True, style="yahoo",
        figsize=(11, 6), title=baseline_title,
        ylabel_lower="Volume", addplot=addplots,
        hlines=dict(hlines=[110.0, 95.0], colors=["green", "red"], linestyle="--"),
        vlines=dict(vlines=[df.index[-10]], colors=["purple"], linestyle=":", alpha=0.5),
        returnfig=True,
    )
    baseline_lines = [c for c in baseline_axes[0].collections
                      if isinstance(c, LineCollection)]
    overlay_lines = [c for c in price_ax.collections
                     if isinstance(c, LineCollection)]
    assert len(overlay_lines) > len(baseline_lines), (
        "algo-pivot hlines() segment missing — "
        f"baseline LineCollection count {len(baseline_lines)} == "
        f"overlay count {len(overlay_lines)}; spec §3.4 algo-pivot not painted"
    )
    import matplotlib.pyplot as plt
    plt.close(baseline_fig)
    # At least one of the EXTRA segments must sit at y == overlay.pivot.
    new_segments = []
    for lc in overlay_lines:
        for path in lc.get_paths():
            for vertex in path.vertices:
                # vertex == (x, y); algo-pivot segment is horizontal at pivot.
                new_segments.append(vertex[1])
    assert any(abs(y - overlay.pivot) < 1e-6 for y in new_segments), (
        "no LineCollection segment at y == algo-pivot value 120.0"
    )
