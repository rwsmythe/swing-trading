"""Markdown briefing renderer (transition output)."""
from __future__ import annotations

from swing.rendering.briefing_md import render_briefing_md
from swing.rendering.view_models import (
    AccountTileVM, BriefingViewModel, PipelineTileVM, StatusStripVM,
    TodaysDecisionVM, WeatherTileVM,
)


def _vm(decisions=None) -> BriefingViewModel:
    return BriefingViewModel(
        action_session_date="2026-04-16", data_asof_date="2026-04-15",
        generated_at="2026-04-15T21:49:00",
        status_strip=StatusStripVM(
            weather=WeatherTileVM(status="Bullish", rationale="r", sizing_implication="OK"),
            account=AccountTileVM(equity=1284.50, open_count=0, soft_warn=4, hard_cap=6),
            pipeline=PipelineTileVM(last_run_ts="2026-04-15T21:49:00",
                                    is_stale=False, current_session_match=True),
        ),
        todays_decisions=decisions or [],
        open_positions=[], watchlist=[], expansions=[],
    )


def test_empty_md():
    md = render_briefing_md(_vm())
    assert "# Swing Briefing \u2014 2026-04-16" in md
    assert "**Status:** Bullish" in md
    assert "No decisions" in md


def test_md_with_decision():
    vm = _vm(decisions=[
        TodaysDecisionVM(
            ticker="NVDA", action_text="Buy-stop $850 \u00b7 2 sh",
            entry_target=850.0, stop_target=820.0, shares=2,
            risk_dollars=60.0, risk_pct=4.7, rationale="VCP coil",
            tt_score="7/8", vcp_score="10/10", chart_b64=None,
        ),
    ])
    md = render_briefing_md(vm)
    assert "NVDA" in md
    assert "Buy-stop $850" in md
