"""HTML renderer — produces self-contained briefing.html from a view model."""
from __future__ import annotations

from swing.rendering.html_renderer import render_briefing_html
from swing.rendering.view_models import (
    AccountTileVM, BriefingViewModel, PipelineTileVM, StatusStripVM,
    TodaysDecisionVM, WeatherTileVM,
)


def _vm(decisions=None, status="Bullish") -> BriefingViewModel:
    return BriefingViewModel(
        action_session_date="2026-04-16", data_asof_date="2026-04-15",
        generated_at="2026-04-15T21:49:00",
        status_strip=StatusStripVM(
            weather=WeatherTileVM(status=status, rationale="r", sizing_implication="OK"),
            account=AccountTileVM(equity=1284.50, open_count=0, soft_warn=4, hard_cap=6),
            pipeline=PipelineTileVM(last_run_ts="2026-04-15T21:49:00",
                                    is_stale=False, current_session_match=True),
        ),
        todays_decisions=decisions or [],
        open_positions=[], watchlist=[], expansions=[],
    )


def test_empty_renders():
    html = render_briefing_html(_vm())
    assert "<html" in html.lower()
    assert "Bullish" in html
    assert "No decisions today" in html


def test_with_decision_renders_action_text():
    vm = _vm(decisions=[
        TodaysDecisionVM(
            ticker="NVDA", action_text="Buy-stop $850 \u00b7 2 sh",
            entry_target=850.0, stop_target=820.0, shares=2,
            risk_dollars=60.0, risk_pct=4.7, rationale="VCP coil",
            tt_score="7/8", vcp_score="10/10", chart_b64=None,
        ),
    ])
    html = render_briefing_html(vm)
    assert "NVDA" in html
    assert "Buy-stop $850" in html


def test_self_contained_no_external_links():
    """Spec §6.4: HTML is portable, all CSS inline, no external <link> or <script src>."""
    vm = _vm()
    html = render_briefing_html(vm)
    assert "<link" not in html.lower() or "rel=\"stylesheet\"" not in html.lower()
    assert "<script src" not in html.lower()


def test_action_session_date_in_title():
    html = render_briefing_html(_vm())
    assert "2026-04-16" in html


def test_the_risk_line_does_NOT_contradict_an_exact_action_line():
    """CODEX R3 MAJOR, the HTML half. The markdown and the HTML renderer print
    the same secondary risk figure and both had to move to two decimals; a fix
    applied to one leaves the other contradicting the action line."""
    vm = _vm(decisions=[
        TodaysDecisionVM(
            ticker="AMN",
            action_text=(
                "Buy-stop $36.27 · 5 sh · $32.50 risk "
                "= 5 x ($37.35 cap - $30.85 stop)"),
            entry_target=36.27, stop_target=30.85, shares=5,
            risk_dollars=32.50, risk_pct=0.4333, rationale="A+ setup",
            tt_score="8/8", vcp_score="9/10", chart_b64=None,
        ),
    ])
    out = render_briefing_html(vm)
    assert "$32.50 risk" in out
    assert "Risk $32.50" in out
    assert "Risk $32 " not in out
