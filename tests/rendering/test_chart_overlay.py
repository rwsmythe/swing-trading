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


def test_render_chart_with_pattern_overlay_writes_nonempty_png(
    tmp_path: Path, fake_ohlcv,
):
    """Smoke test: with overlay, the function still returns the path and
    writes a non-empty PNG. This is purely a crash-resistance + non-empty-
    output guard; structural checks (band x-bounds, candidate-pivot
    preservation, algo-pivot segment) live in
    test_render_chart_with_overlay_paints_two_bands_and_separate_pivot_segment."""
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
    algo-pivot / accidental removal of the existing hline.

    Note: the integer-extent assertions (e.g., pole (80, 100), flag (101,
    119), candidate-pivot full-width 0..119) pin the V1 positional-x-axis
    contract documented in PatternOverlay's class docstring. mpf candle
    plots use integer bar positions, NOT a true date axis. If mpf changes
    this in a future release, both this test and `_bar_idx` must update
    together — the assertions are intentional contract pins, not
    accidental coupling to library internals.
    """
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

    # Bug guard (Codex R1 M2): each fill_betweenx band must occupy its
    # correct x-bounds. _bar_idx maps overlay dates to bar positions; the
    # fixture's overlay places pole at indices 80..100 and flag at 101..119.
    # A swap (pole at flag bounds, flag at pole bounds), an off-by-one, or
    # a wrong-bounds bug would silently slip past the count-only assertion.
    pole_bounds = None
    flag_bounds = None
    all_band_extents = []
    for poly in polys:
        for path in poly.get_paths():
            verts = path.vertices
            xs = [v[0] for v in verts]
            xmin, xmax = min(xs), max(xs)
            all_band_extents.append((xmin, xmax))
            # Identify which band by its x-range against the known overlay coords.
            if abs(xmin - 80) < 1.0 and abs(xmax - 100) < 1.0:
                pole_bounds = (xmin, xmax)
            elif abs(xmin - 101) < 1.0 and abs(xmax - 119) < 1.0:
                flag_bounds = (xmin, xmax)
    assert pole_bounds is not None, (
        f"pole band missing or wrong x-bounds; got polys with x-extents "
        f"{all_band_extents} (expected pole ~ (80, 100))"
    )
    assert flag_bounds is not None, (
        f"flag band missing or wrong x-bounds; got polys with x-extents "
        f"{all_band_extents} (expected flag ~ (101, 119))"
    )

    # Bug guard (Codex R1 M1): the candidate-pivot hline at y=110 must survive
    # Phase 6 painting — it spans the FULL chart width (distinct from the
    # flag-scoped algo-pivot at y=120). A regression that drops [pivot, stop]
    # from plot_kwargs would still leave the algo-pivot segment, masking the
    # loss. Walk every LineCollection segment and verify a full-width y=110
    # segment exists.
    candidate_pivot_y = 110.0
    last_x = len(fake_ohlcv.tail(120)) - 1  # mpf bar positions are 0..N-1
    overlay_lines_for_pivot_check = [
        c for c in price_ax.collections if isinstance(c, LineCollection)
    ]
    candidate_segments = []
    for lc in overlay_lines_for_pivot_check:
        for path in lc.get_paths():
            verts = path.vertices
            if len(verts) < 2:
                continue
            ys = [v[1] for v in verts]
            xs = [v[0] for v in verts]
            if all(abs(y - candidate_pivot_y) < 1e-6 for y in ys):
                candidate_segments.append((min(xs), max(xs)))
    # Must find at least one full-width candidate-pivot segment.
    assert any(
        xmin <= 1.0 and xmax >= last_x - 1.0
        for xmin, xmax in candidate_segments
    ), (
        "candidate-pivot hline at y=110 is missing or not full-width — "
        f"found segments {candidate_segments}; spec §3.4 requires existing "
        "candidate-pivot to be preserved as a SEPARATE element from the "
        "flag-scoped algo-pivot at y=120"
    )

    # Title annotation includes the confidence. mpf renders `title=` as a
    # figure suptitle (not on axes[0]); read it via fig._suptitle with a
    # tolerant fallback to fig.texts for any mpf version that uses
    # fig.text() instead of fig.suptitle().
    fig = captured["fig"]
    suptitle = fig._suptitle.get_text() if fig._suptitle is not None else ""
    if not suptitle:
        suptitle = "\n".join(t.get_text() for t in fig.texts)
    expected = "AAPL | pivot 110.00 | stop 95.00 | last 120 bars | flag (0.78)"
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
    baseline_title = "AAPL | pivot 110.00 stop 95.00 | last 120 bars"
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
    # At least one of the EXTRA segments must sit at y == overlay.pivot
    # AND span ONLY the flag region (xmin ≈ flag_start_i, xmax ≈ flag_end_i).
    # Bug guard (Codex R2 M1): a regression drawing the algo-pivot full-width
    # or across the pole region would silently pass a y-only check; the
    # x-bounds check binds spec §3.4 "drawn ONLY across the flag region".
    algo_pivot_y = overlay.pivot
    expected_flag_xmin = 101.0  # _bar_idx(fake_ohlcv.index[101].date()) per fixture
    expected_flag_xmax = 119.0  # _bar_idx(fake_ohlcv.index[119].date()) per fixture
    algo_pivot_segments = []
    for lc in overlay_lines:
        for path in lc.get_paths():
            verts = path.vertices
            if len(verts) < 2:
                continue
            ys = [v[1] for v in verts]
            xs = [v[0] for v in verts]
            if all(abs(y - algo_pivot_y) < 1e-6 for y in ys):
                algo_pivot_segments.append((min(xs), max(xs)))
    assert any(
        abs(xmin - expected_flag_xmin) < 1.0 and abs(xmax - expected_flag_xmax) < 1.0
        for xmin, xmax in algo_pivot_segments
    ), (
        f"algo-pivot at y={algo_pivot_y} must span ONLY the flag region "
        f"(x ≈ {expected_flag_xmin}..{expected_flag_xmax}); got segments "
        f"{algo_pivot_segments}; spec §3.4 algo-pivot is flag-scoped, distinct "
        f"from candidate-pivot which is full-width"
    )


def test_render_chart_overlay_left_out_of_window_truncates_to_chart_left_edge(
    tmp_path: Path, fake_ohlcv, monkeypatch,
):
    """Bug guard (Codex R2 M2): when an overlay's pole_start_date falls
    BEFORE the chart's first bar, _bar_idx clamps to index 0. The pole
    band must render starting at the chart's left edge (x ≈ 0), NOT be
    silently dropped. Symmetric with the right-edge clamp (out-of-window
    end date → zero-width band at right edge).

    The fixture spans 2026-01-01..2026-06-19 (120 business days). Setting
    pole_start_date to 2025-06-01 (well before the window) should render
    the pole band from x=0 to x=_bar_idx(pole_end_date).
    """
    overlay = PatternOverlay(
        pattern="flag", confidence=0.78,
        pole_start_date=date(2025, 6, 1),  # BEFORE the chart window
        pole_end_date=fake_ohlcv.index[20].date(),  # in-window
        flag_start_date=fake_ohlcv.index[21].date(),
        flag_end_date=fake_ohlcv.index[40].date(),
        pivot=120.0,
    )

    captured = {}
    import mplfinance as mpf
    real_plot = mpf.plot
    def _capture(df, **kw):
        result = real_plot(df, **kw)
        if kw.get("returnfig"):
            captured["axes"] = result[1]
        return result
    monkeypatch.setattr(mpf, "plot", _capture)

    out = tmp_path / "AAPL.png"
    render_chart(
        ticker="AAPL", ohlcv=fake_ohlcv, pivot=110.0, stop=95.0,
        output_path=out, pattern_overlay=overlay,
    )

    from matplotlib.collections import PolyCollection
    polys = [c for c in captured["axes"][0].collections
             if isinstance(c, PolyCollection)]
    # Find the pole band (xmin ≈ 0, xmax ≈ 20).
    pole_band_xmin = None
    for poly in polys:
        for path in poly.get_paths():
            xs = [v[0] for v in path.vertices]
            xmin, xmax = min(xs), max(xs)
            if abs(xmin - 0.0) < 1.0 and abs(xmax - 20.0) < 1.0:
                pole_band_xmin = xmin
                break
        if pole_band_xmin is not None:
            break
    all_extents = [
        (min(v[0] for v in path.vertices), max(v[0] for v in path.vertices))
        for poly in polys for path in poly.get_paths()
    ]
    assert pole_band_xmin is not None, (
        f"pole band starting at chart's left edge (x≈0) missing for "
        f"left-out-of-window pole_start_date; got polys with x-extents "
        f"{all_extents}; _bar_idx left-truncation contract broken"
    )
