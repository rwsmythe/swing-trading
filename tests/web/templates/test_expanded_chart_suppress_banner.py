"""Phase 13 T-T4.SB.3 (Item 5) — inline-SVG-suppresses-PNG-banner cascade tests.

Per plan §B.3 Sub-task 3D + spec §B.5: when an expanded view has cached SVG
bytes, the template MUST render the SVG and SUPPRESS both the PNG fallback
(legacy <img>) and the chart-unavailable banner (single source of truth —
operator sees ONE chart artifact, not duplicate visuals).
"""
from __future__ import annotations

from swing.data.models import WatchlistEntry
from swing.recommendations.sizing import SizingResult
from swing.web.app import _build_templates, _templates_dir
from swing.web.view_models.dashboard import HypRecsExpandedVM
from swing.web.view_models.watchlist import WatchlistExpandedVM


def _render(template_name: str, **ctx) -> str:
    templates = _build_templates(_templates_dir())
    template = templates.env.get_template(template_name)
    return template.render(**ctx)


def _make_sizing(feasible: bool = True) -> SizingResult:
    return SizingResult(
        feasible=feasible, shares=10, notional=2000.0,
        risk_dollars=100.0, risk_pct=1.0, notional_pct=20.0,
        constraint="ok" if feasible else "low_balance",
    )


def _make_hyp_vm(*, svg_bytes: bytes | None,
                 chart_reason: str | None,
                 chart_reason_message: str | None,
                 data_asof_date: str | None = "2026-04-28") -> HypRecsExpandedVM:
    return HypRecsExpandedVM(
        ticker="UCTT",
        buy_stop=200.0, buy_limit=210.0, sell_stop=190.0,
        chase_factor=0.05,
        current_balance=10_000.0, risk_equity=10_000.0,
        sizing_risk=_make_sizing(),
        sizing_cash=_make_sizing(),
        sector="Technology", industry="Semiconductors",
        data_asof_date=data_asof_date,
        chart_reason=chart_reason, chart_reason_message=chart_reason_message,
        pipeline_finished_at="2026-04-29T16:00:00",
        ticker_detail_chart_svg_bytes=svg_bytes,
    )


def test_hyprec_expanded_inline_svg_suppresses_banner_and_png():
    """When SVG bytes present + chart_reason set: SVG renders; PNG + banner
    are SUPPRESSED (cascade)."""
    vm = _make_hyp_vm(
        svg_bytes=b"<svg>jit-here</svg>",
        chart_reason="out-of-scope",
        chart_reason_message="Chart unavailable - ticker out of scope.",
    )
    out = _render(
        "partials/hypothesis_recommendations_expanded.html.j2",
        expanded=vm,
    )
    # SVG inline.
    assert "<svg>jit-here</svg>" in out
    # PNG fallback NOT rendered (chart_reason is not none).
    assert "/charts/2026-04-28/UCTT.png" not in out
    # Banner NOT rendered (suppressed by SVG branch).
    assert 'class="chart-unavailable"' not in out


def test_hyprec_expanded_no_svg_falls_through_to_png_when_in_scope():
    """No SVG + chart_reason None + asof date → render PNG fallback."""
    vm = _make_hyp_vm(
        svg_bytes=None,
        chart_reason=None, chart_reason_message=None,
    )
    out = _render(
        "partials/hypothesis_recommendations_expanded.html.j2",
        expanded=vm,
    )
    assert "/charts/2026-04-28/UCTT.png" in out
    assert 'class="chart-unavailable"' not in out


def test_hyprec_expanded_no_svg_renders_banner_when_out_of_scope():
    """No SVG + chart_reason set → banner renders."""
    vm = _make_hyp_vm(
        svg_bytes=None,
        chart_reason="out-of-scope",
        chart_reason_message="Chart unavailable - ticker out of scope.",
    )
    out = _render(
        "partials/hypothesis_recommendations_expanded.html.j2",
        expanded=vm,
    )
    assert 'class="chart-unavailable"' in out
    assert "/charts/2026-04-28/UCTT.png" not in out


def _make_watchlist_vm(*, svg_bytes: bytes | None,
                       chart_reason: str | None,
                       chart_reason_message: str | None,
                       data_asof_date: str | None = "2026-04-28",
                       ) -> WatchlistExpandedVM:
    entry = WatchlistEntry(
        ticker="UCTT", added_date="2026-04-29",
        last_qualified_date="2026-04-29", status="watch",
        qualification_count=1, not_qualified_streak=0,
        last_data_asof_date="2026-04-28",
        entry_target=42.0, initial_stop_target=39.0,
        last_close=43.0, last_pivot=None, last_stop=None,
        last_adr_pct=2.0, missing_criteria=None, notes=None,
    )
    return WatchlistExpandedVM(
        ticker="UCTT", entry=entry, candidate=None,
        last_price=None, data_asof_date=data_asof_date,
        chart_reason=chart_reason, chart_reason_message=chart_reason_message,
        watchlist_expanded_chart_svg_bytes=svg_bytes,
    )


def test_watchlist_expanded_inline_svg_suppresses_banner_and_png():
    """Symmetric to the hyp-rec test: SVG present + reason set →
    SVG renders; PNG + banner suppressed."""
    vm = _make_watchlist_vm(
        svg_bytes=b"<svg>wl-jit</svg>",
        chart_reason="out-of-scope",
        chart_reason_message="Chart unavailable - ticker out of scope.",
    )
    out = _render("partials/watchlist_expanded.html.j2", expanded=vm)
    assert "<svg>wl-jit</svg>" in out
    assert "/charts/2026-04-28/UCTT.png" not in out
    assert 'class="chart-unavailable"' not in out


def test_watchlist_expanded_no_svg_falls_through_to_png_when_in_scope():
    vm = _make_watchlist_vm(
        svg_bytes=None,
        chart_reason=None, chart_reason_message=None,
    )
    out = _render("partials/watchlist_expanded.html.j2", expanded=vm)
    assert "/charts/2026-04-28/UCTT.png" in out
    assert 'class="chart-unavailable"' not in out


def test_watchlist_expanded_no_svg_renders_banner_when_out_of_scope():
    vm = _make_watchlist_vm(
        svg_bytes=None,
        chart_reason="out-of-scope",
        chart_reason_message="Chart unavailable - ticker out of scope.",
    )
    out = _render("partials/watchlist_expanded.html.j2", expanded=vm)
    assert 'class="chart-unavailable"' in out
    assert "/charts/2026-04-28/UCTT.png" not in out
