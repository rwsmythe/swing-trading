"""Phase 13 T2.SB6 T-A.6.1 — swing/web/charts.py renderer tests.

Per plan §G.9 T-A.6.1 Step 1: 10+ discriminating tests covering 5 chart
surfaces + per-pattern annotations + mathtext defense-in-depth.

Coverage:
  - 1 test per renderer (5 surfaces) asserting valid SVG bytes output.
  - 5 tests covering theme2-annotated per-pattern annotation shape
    (VCP + flat_base + cup_with_handle + high_tight_flag + double_bottom_w).
  - ASCII-only invariant defense (test_charts_ascii_only_text_no_mathtext_metacharacters).
  - No-mathtext-metacharacters defense (test_charts_no_dollar_or_caret_or_underscore_in_titles).

The 5-pattern theme2 test also covers cross-bundle pin
``test_theme1_theme2_shared_renderer_handles_5_v1_patterns`` per plan §H.3
row 10 (un-skipped at T-A.6.7 closer).
"""
from __future__ import annotations

import json
from datetime import date

import matplotlib.pyplot as plt
import pandas as pd
import pytest

import swing.web.charts as charts
from swing.data.models import Fill, PatternEvaluation, Trade
from swing.web.charts import (
    OhlcNormalizationError,
    _bulz_target_price,
    _normalize_ohlc_for_mpf,
    _render_candles_fig,
    _resolve_volume_ax,
    _x_for_date,
    render_market_weather_svg,
    render_position_detail_svg,
    render_theme2_annotated_svg,
    render_ticker_detail_svg,
    render_watchlist_thumbnail_svg,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_bars(n: int = 90, *, start: str = "2024-01-01") -> pd.DataFrame:
    """Build a deterministic OHLCV DataFrame for renderer tests."""
    idx = pd.bdate_range(start=start, periods=n)
    close = [100.0 + 0.5 * i + (i % 7) * 0.1 for i in range(n)]
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


def _make_pattern_eval(
    pattern_class: str = "vcp",
    structural_evidence: dict | None = None,
    *,
    bars: pd.DataFrame | None = None,
) -> PatternEvaluation:
    if structural_evidence is None:
        structural_evidence = {}
    if bars is not None:
        start = str(bars.index[10].date())
        end = str(bars.index[80].date())
    else:
        start = "2024-01-10"
        end = "2024-04-01"
    return PatternEvaluation(
        id=None,
        pipeline_run_id=1,
        ticker="ABC",
        pattern_class=pattern_class,
        detector_version="t2.sb3-v1",
        geometric_score=0.72,
        geometric_score_json="{}",
        composite_score=0.81,
        structural_evidence_json=json.dumps(structural_evidence),
        feature_distribution_log_json="{}",
        window_start_date=start,
        window_end_date=end,
        created_at="2024-04-02T00:00:00.000",
    )


def _make_trade(
    ticker: str = "ABC",
    *,
    entry_price: float = 120.50,
    initial_stop: float = 115.00,
    current_stop: float = 118.00,
    planned_target_R: float | None = None,
) -> Trade:
    return Trade(
        id=1,
        ticker=ticker,
        entry_date="2024-02-10",
        entry_price=entry_price,
        initial_shares=100,
        initial_stop=initial_stop,
        current_stop=current_stop,
        state="managing",
        watchlist_entry_target=None,
        watchlist_initial_stop=None,
        notes=None,
        planned_target_R=planned_target_R,
    )


def _make_fill(
    *, action: str = "entry", price: float = 120.50,
    fill_datetime: str = "2024-02-10T09:30:00",
) -> Fill:
    return Fill(
        fill_id=None,
        trade_id=1,
        fill_datetime=fill_datetime,
        action=action,
        quantity=100,
        price=price,
    )


# ---------------------------------------------------------------------------
# Renderer-shape tests (one per surface)
# ---------------------------------------------------------------------------


def test_render_watchlist_thumbnail_svg_returns_valid_svg_bytes():
    bars = _make_bars(90)
    out = render_watchlist_thumbnail_svg(
        ticker="ABC", bars=bars, ma_lines=[50, 200],
    )
    assert isinstance(out, bytes)
    assert out.startswith(b"<?xml") or out.startswith(b"<svg")
    assert b"</svg>" in out


def test_render_ticker_detail_svg_with_pattern_evaluation_renders_pattern_boundaries():
    bars = _make_bars(180)
    pe = _make_pattern_eval(pattern_class="vcp", bars=bars)
    out = render_ticker_detail_svg(
        ticker="ABC", bars=bars, pattern_evaluation=pe,
    )
    assert isinstance(out, bytes)
    assert b"</svg>" in out
    # Pattern window vertical band rendered (matplotlib emits <path> for
    # axvspan; we just confirm the chart is non-trivial via SVG size).
    assert len(out) > 1000


def test_render_position_detail_svg_with_fills_renders_fill_markers():
    bars = _make_bars(90)
    trade = _make_trade()
    fills = [
        _make_fill(action="entry", price=120.50,
                   fill_datetime="2024-02-10T09:30:00"),
        _make_fill(action="trim", price=125.00,
                   fill_datetime="2024-03-01T10:00:00"),
    ]
    out = render_position_detail_svg(
        ticker="ABC", bars=bars, trade=trade,
        fills=fills, current_stop=118.00,
    )
    assert isinstance(out, bytes)
    assert b"</svg>" in out


def test_render_market_weather_svg_renders_trend_template_badge():
    bars = _make_bars(90)
    out = render_market_weather_svg(
        bars=bars, trend_template_state="Stage 2",
    )
    assert isinstance(out, bytes)
    # Badge text must literally appear (matplotlib emits ax.text as a
    # <text> SVG element with the literal string).
    assert b"trend: Stage 2" in out


# ---------------------------------------------------------------------------
# Theme 2 annotated chart — 5 separate tests per pattern (plan §G.9 step 1
# + cross-bundle pin row 10 closure)
# ---------------------------------------------------------------------------


def test_render_theme2_annotated_svg_vcp():
    bars = _make_bars(150)
    evidence = {
        "pivot_price": 130.0,
        "contractions": [
            {"depth_pct": 15.0},
            {"depth_pct": 10.0},
            {"depth_pct": 6.0},
        ],
    }
    pe = _make_pattern_eval(pattern_class="vcp",
                            structural_evidence=evidence, bars=bars)
    out = render_theme2_annotated_svg(
        ticker="ABC", bars=bars, pattern_evaluation=pe,
    )
    assert b"</svg>" in out
    assert b"vcp" in out
    assert b"contraction 1" in out


def test_render_theme2_annotated_svg_flat_base():
    bars = _make_bars(150)
    # Phase 14 Sub-bundle 2 (T-2.4 sec. C.6 evidence-key repair): the annotator
    # now reads the ACTUAL FlatBaseEvidence field names
    # (range_top_price / range_bottom_price / base_duration_days), not the
    # pre-repair stale keys (top_of_range / bottom_of_range / duration_days).
    evidence = {
        "range_top_price": 130.0, "range_bottom_price": 118.0,
        "base_duration_days": 28,
    }
    pe = _make_pattern_eval(pattern_class="flat_base",
                            structural_evidence=evidence, bars=bars)
    out = render_theme2_annotated_svg(
        ticker="ABC", bars=bars, pattern_evaluation=pe,
    )
    assert b"flat_base" in out
    assert b"duration: 28 days" in out


def test_render_theme2_annotated_svg_cup_with_handle():
    bars = _make_bars(180)
    # Phase 14 Sub-bundle 2 (T-2.4 sec. C.6 evidence-key repair): the annotator
    # now reads the ACTUAL CupWithHandleEvidence field name (cup_depth_pct),
    # not the pre-repair stale key (depth_ratio). cup_bottom_price already
    # matched. The label renders the value with %.2f.
    evidence = {"cup_depth_pct": 0.28, "cup_bottom_price": 95.0}
    pe = _make_pattern_eval(pattern_class="cup_with_handle",
                            structural_evidence=evidence, bars=bars)
    out = render_theme2_annotated_svg(
        ticker="ABC", bars=bars, pattern_evaluation=pe,
    )
    assert b"cup_with_handle" in out
    assert b"depth ratio: 0.28" in out


def test_render_theme2_annotated_svg_high_tight_flag():
    bars = _make_bars(120)
    # Phase 14 Sub-bundle 2 (T-2.4 sec. C.6 evidence-key repair): the annotator
    # now reads the ACTUAL HighTightFlagEvidence field name (pole_pct), not
    # the pre-repair stale key (pole_advance_pct). consolidation_duration_days
    # already matched.
    evidence = {
        "consolidation_duration_days": 21,
        "pole_pct": 105.5,
    }
    pe = _make_pattern_eval(pattern_class="high_tight_flag",
                            structural_evidence=evidence, bars=bars)
    out = render_theme2_annotated_svg(
        ticker="ABC", bars=bars, pattern_evaluation=pe,
    )
    assert b"high_tight_flag" in out
    assert b"days tight: 21" in out
    assert b"pole advance: 105.5pct" in out


def test_render_theme2_annotated_svg_double_bottom_w():
    bars = _make_bars(150)
    evidence = {
        "trough_1_price": 95.0, "center_peak_price": 110.0,
        "trough_2_price": 96.5, "undercut": False,
    }
    pe = _make_pattern_eval(pattern_class="double_bottom_w",
                            structural_evidence=evidence, bars=bars)
    out = render_theme2_annotated_svg(
        ticker="ABC", bars=bars, pattern_evaluation=pe,
    )
    assert b"double_bottom_w" in out


# ---------------------------------------------------------------------------
# Phase 14 SB3 T-3.5 (plan §C.5a) — S6 annotation reposition. The
# `_annotate_*` body-text stack moved from the upper-LEFT (x=0.02, colliding
# with the upper-left legend) to the upper-RIGHT edge (x=0.98, ha="right"),
# co-located with the right-aligned pattern slug + exemplar footnote. These
# tests capture each ``ax.text`` call's (x, y, ha) by monkeypatching
# ``matplotlib.axes.Axes.text`` so they pin coordinates, not just the
# rendered string.
# ---------------------------------------------------------------------------

# Annotation body strings the `_annotate_*` family emits — used to filter the
# captured ax.text calls down to the annotate family (excluding the slug,
# footnote, and watchlist ticker badge).
_ANNOTATE_BODY_PREFIXES = (
    "contraction ", "duration: ", "depth ratio: ",
    "days tight: ", "pole advance: ", "undercut: ",
)


def _capture_annotate_text_coords(monkeypatch, *, pattern, evidence):
    """Render render_theme2_annotated_svg for ``pattern`` and capture each
    ``ax.text`` call as (x, y, ha, body), filtered to the _annotate_* family.

    Returns a list of (x, y, ha) tuples for the body-text annotations the
    per-pattern annotator emitted.
    """
    import matplotlib.axes

    captured: list[tuple] = []
    real_text = matplotlib.axes.Axes.text

    def spy_text(self, *args, **kwargs):
        if len(args) >= 3:
            x, y, body = args[0], args[1], args[2]
            if isinstance(body, str) and any(
                body.startswith(p) for p in _ANNOTATE_BODY_PREFIXES
            ):
                captured.append((x, y, kwargs.get("ha"), body))
        return real_text(self, *args, **kwargs)

    monkeypatch.setattr(matplotlib.axes.Axes, "text", spy_text)
    bars = _make_bars(150)
    pe = _make_pattern_eval(
        pattern_class=pattern, structural_evidence=evidence, bars=bars,
    )
    render_theme2_annotated_svg(
        ticker="ABC", bars=bars, pattern_evaluation=pe,
    )
    return captured


def test_theme2_annotation_text_anchored_upper_right_not_upper_left(monkeypatch):
    captured = _capture_annotate_text_coords(
        monkeypatch, pattern="flat_base",
        evidence={
            "range_top_price": 130.0, "range_bottom_price": 118.0,
            "base_duration_days": 28,
        },
    )
    assert captured, "expected at least one _annotate_* body text"
    assert all(x >= 0.9 for (x, _y, _ha, _b) in captured)
    assert all(ha == "right" for (_x, _y, ha, _b) in captured)


def test_theme2_flat_base_duration_text_ascii(monkeypatch):
    captured = _capture_annotate_text_coords(
        monkeypatch, pattern="flat_base",
        evidence={
            "range_top_price": 130.0, "range_bottom_price": 118.0,
            "base_duration_days": 28,
        },
    )
    bodies = [b for (_x, _y, _ha, b) in captured]
    assert any(b.startswith("duration: ") for b in bodies)
    for b in bodies:
        b.encode("ascii")  # raises UnicodeEncodeError on non-ASCII


def test_theme2_annotation_stack_descends_from_092(monkeypatch):
    captured = _capture_annotate_text_coords(
        monkeypatch, pattern="vcp",
        evidence={
            "pivot_price": 130.0,
            "contractions": [
                {"depth_pct": 15.0},
                {"depth_pct": 10.0},
                {"depth_pct": 6.0},
            ],
        },
    )
    ys = [y for (_x, y, _ha, _b) in captured]
    assert len(ys) == 3
    # Stack starts at 0.92 and descends by 0.05 per line.
    assert ys == pytest.approx([0.92, 0.87, 0.82])
    assert all(x >= 0.9 for (x, _y, _ha, _b) in captured)


def test_theme2_high_tight_flag_second_line_at_087(monkeypatch):
    captured = _capture_annotate_text_coords(
        monkeypatch, pattern="high_tight_flag",
        evidence={
            "consolidation_duration_days": 21,
            "pole_pct": 105.5,
        },
    )
    by_body = {b.split(":")[0]: (x, y, ha) for (x, y, ha, b) in captured}
    assert by_body["days tight"][1] == pytest.approx(0.92)
    assert by_body["pole advance"][1] == pytest.approx(0.87)
    assert all(x >= 0.9 for (x, _y, _ha) in by_body.values())
    assert all(ha == "right" for (_x, _y, ha) in by_body.values())


# ---------------------------------------------------------------------------
# Cross-bundle pin (plan §H.3 row 10) — shared renderer handles 5 V1 patterns.
# ---------------------------------------------------------------------------


def test_theme1_theme2_shared_renderer_handles_5_v1_patterns():
    """Cross-bundle pin per plan §H.3 row 10 (planted at T2.SB6 T-A.6.1;
    un-skips at T-A.6.7 closer — but lands GREEN here as the renderer
    landed in this very task).
    """
    bars = _make_bars(180)
    patterns = (
        "vcp", "flat_base", "cup_with_handle",
        "high_tight_flag", "double_bottom_w",
    )
    for pc in patterns:
        pe = _make_pattern_eval(pattern_class=pc, bars=bars)
        out = render_theme2_annotated_svg(
            ticker="ABC", bars=bars, pattern_evaluation=pe,
        )
        assert isinstance(out, bytes)
        assert b"</svg>" in out
        assert pc.encode() in out


# ---------------------------------------------------------------------------
# Mathtext defense-in-depth (L7 LOCK + spec §A.9 + CLAUDE.md gotcha)
# ---------------------------------------------------------------------------


def test_charts_ascii_only_text_no_mathtext_metacharacters():
    """Per L7 LOCK + spec §A.9: ASCII-only enforcement at construction.

    A non-ASCII ticker must raise immediately (rather than mathtext-render
    silently).
    """
    bars = _make_bars(90)
    with pytest.raises(ValueError, match="ASCII-only"):
        render_watchlist_thumbnail_svg(
            ticker="ABC→", bars=bars, ma_lines=[50],
        )


def test_charts_no_dollar_or_caret_or_underscore_in_titles():
    """Per L7 LOCK + CLAUDE.md matplotlib mathtext gotcha: ``$`` / ``^`` /
    ``_`` / ``\\`` cannot appear in chart text (would trigger mathtext
    parsing + silently italicize / consume glyphs).
    """
    bars = _make_bars(90)
    for forbidden in ("$ABC", "ABC^2", "ABC_1", "ABC\\NA"):
        with pytest.raises(ValueError, match="mathtext"):
            render_watchlist_thumbnail_svg(
                ticker=forbidden, bars=bars, ma_lines=[50],
            )


def test_charts_market_weather_rejects_non_ascii_trend_state():
    bars = _make_bars(90)
    with pytest.raises(ValueError, match="ASCII-only"):
        render_market_weather_svg(
            bars=bars, trend_template_state="Stáge 2",
        )


# ---------------------------------------------------------------------------
# Codex R1 MAJOR #3 — plan §C.5 lines 449 + 452 BINDING: watchlist + market
# weather mini-charts MUST render volume bars (per spec §4.2 inventory).
# ---------------------------------------------------------------------------


def _capture_ax_bar_calls(monkeypatch):
    """Return a list that collects every Axes.bar call's data-point count.

    Used to discriminate "volume bars rendered" vs "no volume axis at all"
    without depending on SVG-byte regex (matplotlib's bar() emits a
    variable number of <path> elements depending on data length).
    """
    import matplotlib.axes
    calls: list[int] = []
    real_bar = matplotlib.axes.Axes.bar

    def spy_bar(self, x, height, *args, **kwargs):
        try:
            calls.append(len(list(x)))
        except TypeError:
            calls.append(-1)
        return real_bar(self, x, height, *args, **kwargs)

    monkeypatch.setattr(matplotlib.axes.Axes, "bar", spy_bar)
    return calls


def test_render_watchlist_thumbnail_svg_renders_volume_bars_per_spec_c5(
    monkeypatch,
):
    """Per plan §C.5 line 449: watchlist row chart renders 'volume bars'.
    Pre-fix: renderer plotted close + MAs only on a single axes; no bar()
    call. Closes Codex R1 MAJOR #3 (first surface).
    """
    bars = _make_bars(90)
    calls = _capture_ax_bar_calls(monkeypatch)
    out = render_watchlist_thumbnail_svg(
        ticker="ABC", bars=bars, ma_lines=[50, 200],
    )
    assert isinstance(out, bytes)
    assert b"</svg>" in out
    assert calls, "volume bars must render (no ax.bar invoked)"
    assert max(calls) == 90, "volume bar count must match input bars"


def test_render_market_weather_svg_renders_volume_bars_per_spec_c5(monkeypatch):
    """Per plan §C.5 line 452: market weather mini-chart renders volume
    bars. Pre-fix: renderer plotted close + MAs + badge text only on a
    single axes; no bar() call. Closes Codex R1 MAJOR #3 (second surface).
    """
    bars = _make_bars(90)
    calls = _capture_ax_bar_calls(monkeypatch)
    out = render_market_weather_svg(
        bars=bars, trend_template_state="Stage 2",
    )
    assert isinstance(out, bytes)
    assert calls, "volume bars must render (no ax.bar invoked)"
    assert max(calls) == 90, "volume bar count must match input bars"
    # Trend badge still rendered post-volume-axis-split.
    assert b"trend: Stage 2" in out


def test_charts_suptitle_uses_parse_math_false():
    """Defense-in-depth: even if a future change introduces ``$`` in a
    title, ``parse_math=False`` on suptitle prevents mathtext interpretation.

    Verify by inspecting the rendered SVG: a literal ``$`` would survive
    when parse_math=False is honored. Here we plant a ticker-detail render
    then confirm the suptitle text round-trips ASCII-only (the ASCII
    assertion already gates the construction; this test confirms the title
    is actually present in output).
    """
    bars = _make_bars(90)
    pe = _make_pattern_eval(pattern_class="vcp", bars=bars)
    out = render_ticker_detail_svg(
        ticker="ABC", bars=bars, pattern_evaluation=pe,
    )
    # Neutral, caller-agnostic suptitle: ticker + bar count present.
    assert b"ABC" in out


def test_ticker_detail_title_is_neutral_no_surface_descriptor():
    """The single cached ticker_detail row is read by BOTH the hyp-rec-expand
    caller AND the watchlist-expand caller, so the suptitle must be
    caller-agnostic -- no 'hyp-rec detail' surface descriptor (Phase 14 SB3
    T-3.1)."""
    bars = _make_bars(90)
    out = render_ticker_detail_svg(ticker="ABC", bars=bars)
    assert b"hyp-rec detail" not in out
    assert b"ABC" in out


# ===========================================================================
# Phase 14 SB3 T-3.2 — shared mplfinance candlestick infrastructure tests.
# ===========================================================================


# ---------------------------------------------------------------------------
# Step 2: _MA_COLORS / _normalize_ohlc_for_mpf / _x_for_date /
# _render_candles_fig.
# ---------------------------------------------------------------------------


def test_ma_colors_cover_all_surface_windows_and_are_unique():
    used = {10, 20, 50, 150, 200}
    assert used <= set(charts._MA_COLORS)
    values = list(charts._MA_COLORS.values())
    assert len(values) == len(set(values))


def test_normalize_ohlc_sorts_dedups_tznaive_and_squeezes_multiindex():
    idx = pd.to_datetime(
        ["2026-05-28", "2026-05-26", "2026-05-27", "2026-05-27"], utc=True,
    )
    frame = pd.DataFrame(
        {
            "Open": [1.0, 2.0, 3.0, 9.0],
            "High": [1.0, 2.0, 3.0, 9.0],
            "Low": [1.0, 2.0, 3.0, 9.0],
            "Close": [1.0, 2.0, 3.0, 9.0],
        },
        index=idx,
    )
    out = _normalize_ohlc_for_mpf(frame)
    assert list(out.index) == sorted(out.index)
    assert out.index.tz is None
    assert len(out) == 3
    assert out.loc[pd.Timestamp("2026-05-27"), "Close"] == 9.0


def test_normalize_ohlc_raises_on_missing_column():
    idx = pd.to_datetime(["2026-05-26", "2026-05-27"])
    frame = pd.DataFrame(
        {"Open": [1.0, 2.0], "Low": [1.0, 2.0], "Close": [1.0, 2.0]},
        index=idx,
    )
    with pytest.raises(OhlcNormalizationError):
        _normalize_ohlc_for_mpf(frame)


def test_normalize_ohlc_raises_on_titlecase_collision():
    idx = pd.to_datetime(["2026-05-26", "2026-05-27"])
    frame = pd.DataFrame(
        {
            "Open": [1.0, 2.0],
            "High": [1.0, 2.0],
            "Low": [1.0, 2.0],
            "close": [1.0, 2.0],
            "Close": [3.0, 4.0],
        },
        index=idx,
    )
    with pytest.raises(OhlcNormalizationError):
        _normalize_ohlc_for_mpf(frame)


def test_normalize_ohlc_flattens_single_ticker_multiindex():
    idx = pd.to_datetime(["2026-05-26", "2026-05-27"])
    cols = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close", "Volume"], ["AAPL"]],
    )
    frame = pd.DataFrame(
        [[1.0] * 5, [2.0] * 5], index=idx, columns=cols,
    )
    out = _normalize_ohlc_for_mpf(frame)
    assert {"Open", "High", "Low", "Close"} <= set(out.columns)


def test_normalize_ohlc_raises_on_multi_ticker_multiindex():
    idx = pd.to_datetime(["2026-05-26", "2026-05-27"])
    cols = pd.MultiIndex.from_product(
        [["Open", "High", "Low", "Close"], ["AAPL", "MSFT"]],
    )
    frame = pd.DataFrame(
        [[1.0] * 8, [2.0] * 8], index=idx, columns=cols,
    )
    with pytest.raises(OhlcNormalizationError):
        _normalize_ohlc_for_mpf(frame)


def test_x_for_date_returns_integer_bar_position(known_bars):
    df = _normalize_ohlc_for_mpf(known_bars)
    fig, price_ax, _vol = _render_candles_fig(
        df, ma_windows=(10,), figsize=(6, 4), volume=False,
    )
    try:
        pos = _x_for_date(price_ax, df, date(2026, 5, 29))
        assert pos == 3
    finally:
        plt.close(fig)


def test_x_for_date_uses_normalized_order_not_raw(known_bars):
    reversed_bars = known_bars.iloc[::-1]
    df = _normalize_ohlc_for_mpf(reversed_bars)
    fig, price_ax, _vol = _render_candles_fig(
        df, ma_windows=(10,), figsize=(6, 4), volume=False,
    )
    try:
        pos = _x_for_date(price_ax, df, date(2026, 5, 29))
        assert pos == 3
    finally:
        plt.close(fig)


def test_render_candles_fig_returns_price_and_volume_axes(ohlc_bars):
    df = _normalize_ohlc_for_mpf(ohlc_bars)
    fig, price_ax, vol_ax = _render_candles_fig(
        df, ma_windows=(10, 20, 50), figsize=(8, 5), volume=True,
    )
    try:
        assert vol_ax is not None
        assert vol_ax is not price_ax
        # SECONDARY geometry guard: volume panel sits below the price panel.
        assert vol_ax.get_position().y0 < price_ax.get_position().y0
    finally:
        plt.close(fig)


def test_resolve_volume_ax_matches_volume_ylabel_role(ohlc_bars):
    """T-3.2: the ROLE branch must actually fire on the real mpf panel.

    mplfinance labels the volume panel ``"Volume  $10^{6}$"`` (auto
    scale-factor suffix), so resolution must match on a normalized Volume
    PREFIX, not exact equality. Assert the resolved axis is the one whose
    configured y-label (BEFORE any stripping) starts with "Volume" — i.e.
    the role mechanism selected it, not the geometry fallback.
    """
    df = _normalize_ohlc_for_mpf(ohlc_bars)
    fig, price_ax, _vol = _render_candles_fig(
        df, ma_windows=(10, 20, 50), figsize=(8, 5), volume=True,
    )
    try:
        # Identify the labelled volume panel independently of the helper.
        labelled = [
            ax for ax in fig.axes
            if ax is not price_ax
            and ax.get_ylabel().strip().lower().startswith("volume")
        ]
        assert labelled, (
            "expected mpf to label the volume panel with a 'Volume' prefix; "
            f"got ylabels {[ax.get_ylabel() for ax in fig.axes]!r}"
        )
        resolved = _resolve_volume_ax(fig, price_ax)
        assert resolved in labelled
        # The suffix proves the exact-equality check would have been DEAD.
        assert resolved.get_ylabel().strip().lower().startswith("volume")
    finally:
        plt.close(fig)


def test_render_candles_fig_strips_only_volume_yticks(ohlc_bars):
    df = _normalize_ohlc_for_mpf(ohlc_bars)
    fig, price_ax, vol_ax = _render_candles_fig(
        df, ma_windows=(10, 20, 50), figsize=(8, 5), volume=True,
    )
    try:
        vol_labels = [t.get_text() for t in vol_ax.get_yticklabels()]
        assert all(not lbl for lbl in vol_labels)
        price_labels = [t.get_text() for t in price_ax.get_yticklabels()]
        assert any(lbl for lbl in price_labels)
    finally:
        plt.close(fig)


def test_render_candles_fig_grid_enabled(ohlc_bars):
    df = _normalize_ohlc_for_mpf(ohlc_bars)
    fig, price_ax, _vol = _render_candles_fig(
        df, ma_windows=(10, 20, 50), figsize=(8, 5), volume=True,
    )
    try:
        # At least one gridline visible on the price axis.
        gridlines = price_ax.get_xgridlines() + price_ax.get_ygridlines()
        assert any(gl.get_visible() for gl in gridlines)
    finally:
        plt.close(fig)


def test_render_candles_fig_volume_false_returns_none_vol_ax(ohlc_bars):
    df = _normalize_ohlc_for_mpf(ohlc_bars)
    fig, price_ax, vol_ax = _render_candles_fig(
        df, ma_windows=(10, 20, 50), figsize=(8, 5), volume=False,
    )
    try:
        assert vol_ax is None
    finally:
        plt.close(fig)


# ---------------------------------------------------------------------------
# Step 4: render_ticker_detail_svg candlestick conversion.
# ---------------------------------------------------------------------------


def _assert_renders_candles(monkeypatch, render_callable, **kwargs):
    """Spy swing.web.charts.mpf.plot and assert type='candle' was passed."""
    captured: dict = {}
    real_plot = charts.mpf.plot

    def spy_plot(df, **kw):
        captured["kw"] = kw
        return real_plot(df, **kw)

    monkeypatch.setattr(charts.mpf, "plot", spy_plot)
    render_callable(**kwargs)
    assert captured, "mpf.plot was not invoked"
    assert captured["kw"].get("type") == "candle"


def test_ticker_detail_renders_candles_not_line(monkeypatch):
    bars = _make_bars(120)
    _assert_renders_candles(
        monkeypatch, render_ticker_detail_svg, ticker="ABC", bars=bars,
    )


def test_ticker_detail_title_is_neutral_no_surface_descriptor_candles():
    bars = _make_bars(120)
    out = render_ticker_detail_svg(ticker="ABC", bars=bars)
    assert b"hyp-rec detail" not in out


def test_ticker_detail_overlays_pattern_window_band():
    bars = _make_bars(180)
    pe = _make_pattern_eval(pattern_class="vcp", bars=bars)
    out = render_ticker_detail_svg(
        ticker="ABC", bars=bars, pattern_evaluation=pe,
    )
    assert b"</svg>" in out
    # axvspan emits a <path>; chart is non-trivial.
    assert len(out) > 1000


def test_ticker_detail_cache_single_row_across_two_callers(tmp_path):
    """Two get_or_render_surface calls with identical bars -> byte-identical
    SVG + exactly ONE cached row (L3)."""
    import sqlite3
    from unittest.mock import MagicMock

    from swing.data.db import ensure_schema
    from swing.web.chart_jit import get_or_render_surface

    conn: sqlite3.Connection = ensure_schema(tmp_path / "two_callers.db")
    with conn:
        conn.execute(
            "INSERT INTO pipeline_runs (started_ts, trigger, "
            "data_asof_date, action_session_date, state, lease_token) "
            "VALUES ('2026-05-22T00:00:00.000', 'manual', '2026-05-22', "
            "'2026-05-22', 'complete', 'tok-two')"
        )
        run_id = int(
            conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        )
    bars = _make_bars(120)
    ohlcv_cache = MagicMock()
    ohlcv_cache.get_or_fetch.return_value = bars
    r1 = get_or_render_surface(
        conn=conn, ohlcv_cache=ohlcv_cache,
        surface="ticker_detail", ticker="UCTT",
        pipeline_run_id=run_id, data_asof_date="2026-05-22",
        pattern_evaluation=None,
    )
    r2 = get_or_render_surface(
        conn=conn, ohlcv_cache=ohlcv_cache,
        surface="ticker_detail", ticker="UCTT",
        pipeline_run_id=run_id, data_asof_date="2026-05-22",
        pattern_evaluation=None,
    )
    assert r1 == r2
    count = conn.execute(
        "SELECT COUNT(*) FROM chart_renders WHERE surface='ticker_detail' "
        "AND ticker='UCTT' AND pipeline_run_id=?",
        (run_id,),
    ).fetchone()[0]
    assert count == 1


def test_ticker_detail_svg_ascii_only():
    bars = _make_bars(120)
    out = render_ticker_detail_svg(ticker="ABC", bars=bars)
    out.decode("ascii")  # raises if non-ASCII present


# ---------------------------------------------------------------------------
# Step 5: render_theme2_annotated_svg candlestick conversion.
# ---------------------------------------------------------------------------


def test_theme2_annotated_renders_candles_not_line(monkeypatch):
    bars = _make_bars(150)
    pe = _make_pattern_eval(pattern_class="vcp", bars=bars)
    _assert_renders_candles(
        monkeypatch, render_theme2_annotated_svg,
        ticker="ABC", bars=bars, pattern_evaluation=pe,
    )


def test_theme2_annotated_volume_false_single_axis(monkeypatch):
    bars = _make_bars(150)
    pe = _make_pattern_eval(pattern_class="vcp", bars=bars)
    captured: dict = {}
    real_plot = charts.mpf.plot

    def spy_plot(df, **kw):
        captured["kw"] = kw
        return real_plot(df, **kw)

    monkeypatch.setattr(charts.mpf, "plot", spy_plot)
    render_theme2_annotated_svg(
        ticker="ABC", bars=bars, pattern_evaluation=pe,
    )
    assert captured["kw"].get("volume") is False


def test_theme2_annotated_ascii_only_all_text():
    bars = _make_bars(150)
    pe = _make_pattern_eval(pattern_class="flat_base", bars=bars)
    out = render_theme2_annotated_svg(
        ticker="ABC", bars=bars, pattern_evaluation=pe,
    )
    out.decode("ascii")


# ---------------------------------------------------------------------------
# Step 6: pin the mpf positional-x integer-extent contract.
# ---------------------------------------------------------------------------


def test_candles_use_integer_x_axis_positions(ohlc_bars):
    df = _normalize_ohlc_for_mpf(ohlc_bars)
    fig, price_ax, _vol = _render_candles_fig(
        df, ma_windows=(10, 20, 50), figsize=(8, 5), volume=True,
    )
    try:
        xmin, xmax = price_ax.get_xlim()
        assert (xmax - xmin) == pytest.approx(len(ohlc_bars) - 1, abs=2)
    finally:
        plt.close(fig)


# ---------------------------------------------------------------------------
# Step 7: bars-fixture precondition test.
# ---------------------------------------------------------------------------


def test_charts_bars_fixture_has_ohlc_columns_and_datetimeindex(ohlc_bars):
    assert {"Open", "High", "Low", "Close", "Volume"} <= set(ohlc_bars.columns)
    assert isinstance(ohlc_bars.index, pd.DatetimeIndex)


# ---------------------------------------------------------------------------
# Phase 14 SB3 T-3.3 — position_detail candlestick conversion + BULZ zones.
# ---------------------------------------------------------------------------


# --- Step 1/2: _bulz_target_price helper -----------------------------------


def test_bulz_target_price_from_planned_target_R():
    # entry=100, stop=90 -> R_unit=10; target = 100 + 2.0*10 = 120.0.
    # A swapped inverse (100 + 2*(90-100)=80) would FAIL this.
    trade = _make_trade(
        entry_price=100.0, initial_stop=90.0, planned_target_R=2.0,
    )
    assert _bulz_target_price(trade) == pytest.approx(120.0)


def test_bulz_target_price_none_when_planned_target_R_absent():
    trade = _make_trade(
        entry_price=100.0, initial_stop=90.0, planned_target_R=None,
    )
    assert _bulz_target_price(trade) is None


def test_bulz_target_price_none_when_risk_unit_nonpositive():
    # entry=90, stop=100 -> r_unit = 90-100 = -10 (<= 0) -> None.
    trade = _make_trade(
        entry_price=90.0, initial_stop=100.0, planned_target_R=2.0,
    )
    assert _bulz_target_price(trade) is None


# --- Step 3: candlestick conversion + stop axhline -------------------------


def test_position_detail_renders_candles_not_line(monkeypatch, ohlc_bars):
    trade = _make_trade(ticker="BULZ")
    _assert_renders_candles(
        monkeypatch, render_position_detail_svg,
        ticker="BULZ", bars=ohlc_bars, trade=trade,
        fills=[], current_stop=95.0,
    )


def test_position_detail_stop_axhline_present(monkeypatch, ohlc_bars):
    recorded: list[float] = []
    real_axhline = plt.matplotlib.axes.Axes.axhline

    def spy_axhline(self, y=0, *args, **kwargs):
        recorded.append(y)
        return real_axhline(self, y, *args, **kwargs)

    monkeypatch.setattr(plt.matplotlib.axes.Axes, "axhline", spy_axhline)
    trade = _make_trade(ticker="BULZ")
    render_position_detail_svg(
        ticker="BULZ", bars=ohlc_bars, trade=trade,
        fills=[], current_stop=95.0,
    )
    assert 95.0 in recorded


# --- Step 4/5: BULZ risk/reward zones (axhspan) ----------------------------


def _render_and_capture_axhspans(monkeypatch, ohlc_bars, **kwargs):
    """Capture every (ymin, ymax) passed to Axes.axhspan during render."""
    spans: list[tuple[float, float]] = []
    real_axhspan = plt.matplotlib.axes.Axes.axhspan

    def spy_axhspan(self, ymin, ymax, *args, **kw):
        spans.append((ymin, ymax))
        return real_axhspan(self, ymin, ymax, *args, **kw)

    monkeypatch.setattr(plt.matplotlib.axes.Axes, "axhspan", spy_axhspan)
    out = render_position_detail_svg(bars=ohlc_bars, fills=[], **kwargs)
    return spans, out


def test_position_detail_renders_risk_zone_axhspan_bounds(
    monkeypatch, ohlc_bars
):
    trade = _make_trade(
        ticker="BULZ", entry_price=100.0, initial_stop=90.0,
        planned_target_R=None,
    )
    spans, _ = _render_and_capture_axhspans(
        monkeypatch, ohlc_bars, ticker="BULZ", trade=trade,
        current_stop=95.0,
    )
    # Risk zone = (stop, entry) = (95.0, 100.0). A swapped (100, 95) FAILS.
    assert (95.0, 100.0) in spans


def test_position_detail_renders_reward_zone_when_target_present(
    monkeypatch, ohlc_bars
):
    trade = _make_trade(
        ticker="BULZ", entry_price=100.0, initial_stop=90.0,
        planned_target_R=2.0,
    )
    spans, _ = _render_and_capture_axhspans(
        monkeypatch, ohlc_bars, ticker="BULZ", trade=trade,
        current_stop=95.0,
    )
    # Reward zone = (entry, target) = (100.0, 120.0); risk band also present.
    assert (100.0, 120.0) in spans
    assert (95.0, 100.0) in spans


def test_position_detail_risk_zone_only_when_no_target(monkeypatch, ohlc_bars):
    trade = _make_trade(
        ticker="BULZ", entry_price=100.0, initial_stop=90.0,
        planned_target_R=None,
    )
    spans, _ = _render_and_capture_axhspans(
        monkeypatch, ohlc_bars, ticker="BULZ", trade=trade,
        current_stop=95.0,
    )
    assert len(spans) == 1
    assert (95.0, 100.0) in spans


# --- T-3.4: market_weather candlestick conversion (§C.4) -------------------


def test_market_weather_renders_candles_not_line(monkeypatch, ohlc_bars):
    """Per plan §C.4: market_weather routes through _render_candles_fig
    (type='candle'), not the legacy ax.plot close line."""
    _assert_renders_candles(
        monkeypatch, render_market_weather_svg,
        bars=ohlc_bars, trend_template_state="stage_2",
    )


def test_market_weather_trend_badge_ascii_body_text(ohlc_bars):
    """Trend badge renders as ASCII body text; underscore is LITERAL in
    ax.text body (NOT mathtext). `trend: stage_2` survives verbatim."""
    out = render_market_weather_svg(
        bars=ohlc_bars, trend_template_state="stage_2",
    )
    assert isinstance(out, bytes)
    assert b"trend: stage_2" in out
    out.decode("ascii")  # raises if any non-ASCII glyph present


def test_market_weather_grid_enabled(ohlc_bars):
    """Gridlines come from _render_candles_fig (P14.N8); the renderer
    produces a valid non-trivial SVG."""
    out = render_market_weather_svg(
        bars=ohlc_bars, trend_template_state="stage_2",
    )
    assert isinstance(out, bytes)
    assert b"</svg>" in out
    assert len(out) > 1000


def test_position_detail_skips_zones_on_invalid_long_shape_and_warns(
    monkeypatch, ohlc_bars, caplog
):
    # current_stop=105.0 >= entry=100.0 -> invalid long; skip + WARN, never raise.
    trade = _make_trade(
        ticker="BULZ", entry_price=100.0, initial_stop=90.0,
        planned_target_R=None,
    )
    with caplog.at_level("WARNING", logger="swing.web.charts"):
        spans, _ = _render_and_capture_axhspans(
            monkeypatch, ohlc_bars, ticker="BULZ", trade=trade,
            current_stop=105.0,
        )
    assert spans == []
    assert any("zone" in rec.message.lower() for rec in caplog.records)


def test_position_detail_off_range_valid_zone_is_drawn_not_hidden(
    monkeypatch, ohlc_bars
):
    # R=20.0 -> target = 100 + 20*10 = 300 (far above ohlc_bars range);
    # geometrically valid -> drawn (axhspan autoscales), NOT silently hidden.
    trade = _make_trade(
        ticker="BULZ", entry_price=100.0, initial_stop=90.0,
        planned_target_R=20.0,
    )
    spans, _ = _render_and_capture_axhspans(
        monkeypatch, ohlc_bars, ticker="BULZ", trade=trade,
        current_stop=95.0,
    )
    assert (100.0, 300.0) in spans


def test_position_detail_zone_legend_ascii(ohlc_bars):
    trade = _make_trade(
        ticker="BULZ", entry_price=100.0, initial_stop=90.0,
        planned_target_R=2.0,
    )
    out = render_position_detail_svg(
        ticker="BULZ", bars=ohlc_bars, trade=trade,
        fills=[], current_stop=95.0,
    )
    # matplotlib may HTML-escape > to &gt; in the SVG <text> element.
    assert (
        b"risk zone (entry-&gt;stop)" in out
        or b"risk zone (entry->stop)" in out
    )
    assert (
        b"reward zone (entry-&gt;target)" in out
        or b"reward zone (entry->target)" in out
    )


# ---------------------------------------------------------------------------
# Codex executing-plans review — FIX 1 (real regression): position-detail
# fill markers must land on the NEAREST-FORWARD trading bar, not be DROPPED
# when the fill date has no exact daily bar (weekend / holiday / tz shift).
# ---------------------------------------------------------------------------


def _capture_scatter_x(monkeypatch):
    """Capture every Axes.scatter call's x list during a render."""
    import matplotlib.axes
    calls: list[list] = []
    real_scatter = matplotlib.axes.Axes.scatter

    def spy_scatter(self, x, y, *args, **kwargs):
        try:
            calls.append(list(x))
        except TypeError:
            calls.append([x])
        return real_scatter(self, x, y, *args, **kwargs)

    monkeypatch.setattr(matplotlib.axes.Axes, "scatter", spy_scatter)
    return calls


def test_position_detail_fill_on_non_bar_date_lands_on_next_bar(
    monkeypatch, ohlc_bars
):
    """A fill stamped on a Saturday (no exact daily bar) must be placed on
    the NEXT trading bar, NOT silently dropped.

    ohlc_bars is business days from 2026-01-02; 2026-01-10 is a Saturday.
    The next trading bar is Monday 2026-01-12. Pre-fix (exact
    df.index.get_loc) the KeyError caused the fill to be skipped (zero
    scatter calls). Post-fix the fill lands on the bar position for
    2026-01-12.
    """
    from swing.web.charts import _normalize_ohlc_for_mpf

    df = _normalize_ohlc_for_mpf(ohlc_bars)
    # Expected bar index = first bar with date >= 2026-01-10 -> 2026-01-12.
    expected = next(
        i for i, ts in enumerate(df.index)
        if ts.date() >= date(2026, 1, 10)
    )
    trade = _make_trade(ticker="BULZ")
    fills = [
        _make_fill(action="entry", price=120.50,
                   fill_datetime="2026-01-10T09:30:00"),  # Saturday
    ]
    calls = _capture_scatter_x(monkeypatch)
    out = render_position_detail_svg(
        ticker="BULZ", bars=ohlc_bars, trade=trade,
        fills=fills, current_stop=95.0,
    )
    assert isinstance(out, bytes)
    # Exactly one scatter call (one fill) — NOT dropped.
    assert len(calls) == 1
    assert calls[0] == [expected]


def test_position_detail_fill_count_equals_fills_on_non_bar_dates(
    monkeypatch, ohlc_bars
):
    """Every fill produces a marker even when none of the fill dates match
    an exact bar; the marker count equals the number of fills."""
    trade = _make_trade(ticker="BULZ")
    fills = [
        _make_fill(action="entry", price=120.50,
                   fill_datetime="2026-01-10T09:30:00"),  # Saturday
        _make_fill(action="trim", price=130.00,
                   fill_datetime="2026-01-11T10:00:00"),  # Sunday
    ]
    calls = _capture_scatter_x(monkeypatch)
    render_position_detail_svg(
        ticker="BULZ", bars=ohlc_bars, trade=trade,
        fills=fills, current_stop=95.0,
    )
    assert len(calls) == len(fills)


def test_position_detail_fill_past_window_clamps_to_last_bar(
    monkeypatch, ohlc_bars
):
    """A fill dated AFTER the last bar clamps to the last bar position
    (preserving the pre-candlestick nearest-forward/clamp behavior), NOT
    dropped."""
    from swing.web.charts import _normalize_ohlc_for_mpf

    df = _normalize_ohlc_for_mpf(ohlc_bars)
    last_pos = len(df.index) - 1
    trade = _make_trade(ticker="BULZ")
    fills = [
        _make_fill(action="exit", price=200.0,
                   fill_datetime="2030-01-01T09:30:00"),  # far future
    ]
    calls = _capture_scatter_x(monkeypatch)
    render_position_detail_svg(
        ticker="BULZ", bars=ohlc_bars, trade=trade,
        fills=fills, current_stop=95.0,
    )
    assert len(calls) == 1
    assert calls[0] == [last_pos]


def test_position_detail_unparseable_fill_datetime_skipped(
    monkeypatch, ohlc_bars
):
    """A fill whose fill_datetime cannot be parsed is still skipped (parse
    guard preserved)."""
    trade = _make_trade(ticker="BULZ")
    fills = [
        _make_fill(action="entry", price=120.50,
                   fill_datetime="not-a-date"),
    ]
    calls = _capture_scatter_x(monkeypatch)
    render_position_detail_svg(
        ticker="BULZ", bars=ohlc_bars, trade=trade,
        fills=fills, current_stop=95.0,
    )
    assert calls == []


# ---------------------------------------------------------------------------
# FIX 2 (hardening): _normalize_ohlc_for_mpf coerces a non-DatetimeIndex.
# ---------------------------------------------------------------------------


def test_normalize_ohlc_coerces_string_index_to_datetime():
    """A string/object-indexed frame is coerced to a DatetimeIndex at the
    barrier (not failing deep in mpf/get_loc later)."""
    frame = pd.DataFrame(
        {
            "Open": [1.0, 2.0, 3.0],
            "High": [1.0, 2.0, 3.0],
            "Low": [1.0, 2.0, 3.0],
            "Close": [1.0, 2.0, 3.0],
        },
        index=["2026-05-26", "2026-05-27", "2026-05-28"],
    )
    out = _normalize_ohlc_for_mpf(frame)
    assert isinstance(out.index, pd.DatetimeIndex)
    assert list(out.index) == sorted(out.index)


def test_normalize_ohlc_raises_on_non_datetime_coercible_index():
    """A non-datetime-coercible index raises OhlcNormalizationError at the
    barrier rather than a deep mpf error."""
    frame = pd.DataFrame(
        {
            "Open": [1.0, 2.0],
            "High": [1.0, 2.0],
            "Low": [1.0, 2.0],
            "Close": [1.0, 2.0],
        },
        index=["alpha", "beta"],
    )
    with pytest.raises(OhlcNormalizationError):
        _normalize_ohlc_for_mpf(frame)


# ---------------------------------------------------------------------------
# FIX 3 (hardening): _render_candles_fig raises a clear error on an MA window
# that has no _MA_COLORS palette entry (not a bare KeyError deep in render).
# ---------------------------------------------------------------------------


def test_render_candles_fig_raises_clear_error_on_unpinned_ma_window(
    ohlc_bars,
):
    df = _normalize_ohlc_for_mpf(ohlc_bars)
    assert 30 not in charts._MA_COLORS
    with pytest.raises(ValueError, match="_MA_COLORS"):
        _render_candles_fig(
            df, ma_windows=(30,), figsize=(8, 5), volume=False,
        )
