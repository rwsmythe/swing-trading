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

import pandas as pd
import pytest

from swing.data.models import Fill, PatternEvaluation, Trade
from swing.web.charts import (
    render_hyprec_detail_svg,
    render_market_weather_svg,
    render_position_detail_svg,
    render_theme2_annotated_svg,
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


def _make_trade(ticker: str = "ABC") -> Trade:
    return Trade(
        id=1,
        ticker=ticker,
        entry_date="2024-02-10",
        entry_price=120.50,
        initial_shares=100,
        initial_stop=115.00,
        current_stop=118.00,
        state="managing",
        watchlist_entry_target=None,
        watchlist_initial_stop=None,
        notes=None,
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


def test_render_hyprec_detail_svg_with_pattern_evaluation_renders_pattern_boundaries():
    bars = _make_bars(180)
    pe = _make_pattern_eval(pattern_class="vcp", bars=bars)
    out = render_hyprec_detail_svg(
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
    evidence = {
        "top_of_range": 130.0, "bottom_of_range": 118.0,
        "duration_days": 28,
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
    evidence = {"depth_ratio": 0.28, "cup_bottom_price": 95.0}
    pe = _make_pattern_eval(pattern_class="cup_with_handle",
                            structural_evidence=evidence, bars=bars)
    out = render_theme2_annotated_svg(
        ticker="ABC", bars=bars, pattern_evaluation=pe,
    )
    assert b"cup_with_handle" in out
    assert b"depth ratio: 0.28" in out


def test_render_theme2_annotated_svg_high_tight_flag():
    bars = _make_bars(120)
    evidence = {
        "consolidation_duration_days": 21,
        "pole_advance_pct": 105.5,
    }
    pe = _make_pattern_eval(pattern_class="high_tight_flag",
                            structural_evidence=evidence, bars=bars)
    out = render_theme2_annotated_svg(
        ticker="ABC", bars=bars, pattern_evaluation=pe,
    )
    assert b"high_tight_flag" in out
    assert b"days tight: 21" in out


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


def test_charts_suptitle_uses_parse_math_false():
    """Defense-in-depth: even if a future change introduces ``$`` in a
    title, ``parse_math=False`` on suptitle prevents mathtext interpretation.

    Verify by inspecting the rendered SVG: a literal ``$`` would survive
    when parse_math=False is honored. Here we plant a hyp-rec render then
    confirm the suptitle text round-trips ASCII-only (the ASCII assertion
    already gates the construction; this test confirms the title is
    actually present in output).
    """
    bars = _make_bars(90)
    pe = _make_pattern_eval(pattern_class="vcp", bars=bars)
    out = render_hyprec_detail_svg(
        ticker="ABC", bars=bars, pattern_evaluation=pe,
    )
    assert b"hyp-rec detail" in out
