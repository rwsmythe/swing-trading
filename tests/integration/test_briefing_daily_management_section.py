"""Spec §7.4 LOCKED: briefing.md + briefing.html gain a 'Daily Management
Snapshot' subsection per open trade after Phase 8.

R2 Major #1 fix: tests assert EXACT markdown structure, not loose
substring containment.
"""
from __future__ import annotations

from typing import Any

from swing.data.models import DailyManagementRecord, Trade, WeatherRun
from swing.rendering.briefing import BriefingInputs, build_briefing_view_model
from swing.rendering.briefing_md import render_briefing_md
from swing.rendering.html_renderer import render_briefing_html


# --- helpers ----------------------------------------------------------------


def _wr() -> WeatherRun:
    return WeatherRun(
        id=1, run_ts="2026-05-07T08:00:00", asof_date="2026-05-07",
        ticker="QQQ", status="Bullish", close=480.0,
        sma10=475.0, sma20=470.0, sma50=460.0,
        slope20_5bar=0.5, slope10_5bar=0.7,
        rationale="20MA rising; 10>20.",
    )


def _open_trade_for(*, ticker: str, trade_id: int = 1, **fields: Any) -> Trade:
    """Build a Trade with sensible defaults; tests override fields as needed.

    Phase 8 daily-management snapshots resolve ticker via JOIN against
    inputs.open_trades by trade_id (Codex R4 M5: snapshots have no ticker
    column).
    """
    base: dict[str, Any] = {
        "id": trade_id,
        "ticker": ticker,
        "entry_date": "2026-05-01",
        "entry_price": 100.0,
        "initial_shares": 10,
        "initial_stop": 95.0,
        "current_stop": 95.0,
        "state": "managing",
        "watchlist_entry_target": None,
        "watchlist_initial_stop": None,
        "notes": None,
    }
    base.update(fields)
    return Trade(**base)


def _make_snapshot_row(
    *,
    trade_id: int,
    data_asof_session: str = "2026-05-07",
    open_MFE_R_to_date: float | None = 0.0,  # noqa: N803
    open_MAE_R_to_date: float | None = 0.0,  # noqa: N803
    maturity_stage: str | None = "0R_to_+1R",
    trail_MA_eligibility_flag: int | None = 0,  # noqa: N803
    **fields: Any,
) -> DailyManagementRecord:
    """Construct a DailyManagementRecord without a ticker column (Codex R4 M5)."""
    base: dict[str, Any] = {
        "management_record_id": trade_id,
        "trade_id": trade_id,
        "record_type": "daily_snapshot",
        "review_date": data_asof_session,
        "data_asof_session": data_asof_session,
        "created_at": f"{data_asof_session}T08:00:00",
        "mfe_mae_precision_level": "daily_approximate",
        "pipeline_run_id": None,
        "is_superseded": 0,
        "superseded_by_record_id": None,
        "current_price": 110.0,
        "current_stop": 95.0,
        "current_size": 10.0,
        "current_avg_cost": 100.0,
        "open_R_effective": 2.0,
        "open_MFE_R_to_date": open_MFE_R_to_date,
        "open_MAE_R_to_date": open_MAE_R_to_date,
        "intraday_high": None,
        "intraday_low": None,
        "position_capital_utilization_pct": 10.0,
        "position_capital_denominator_dollars": 10000.0,
        "position_portfolio_heat_contribution_dollars": 50.0,
        "maturity_stage": maturity_stage,
        "trail_MA_candidate_price": None,
        "trail_MA_period_days": 21,
        "trail_MA_eligibility_flag": trail_MA_eligibility_flag,
        "thesis_status": None,
        "prior_stop": None,
        "new_stop": None,
        "linked_trade_event_id": None,
        "stop_changed": None,
        "stop_change_reason": None,
        "volume_behavior": None,
        "relative_strength_status": None,
        "market_regime_change": None,
        "sector_condition_change": None,
        "news_or_event_update": None,
        "action_taken": None,
        "action_reason": None,
        "emotional_state": None,
        "rule_violation_suspected": None,
        "management_notes": None,
    }
    base.update(fields)
    return DailyManagementRecord(**base)


def _build_inputs_with_snapshots(
    *,
    open_trades: list[Trade],
    active_snapshots: list[DailyManagementRecord],
) -> BriefingInputs:
    return BriefingInputs(
        action_session_date="2026-05-07",
        data_asof_date="2026-05-07",
        generated_at="2026-05-07T08:00:00",
        weather=_wr(),
        weather_is_stale=False,
        equity=10000.0,
        open_count=len(open_trades),
        soft_warn=4,
        hard_cap=6,
        last_pipeline_ts="2026-05-07T08:00:00",
        pipeline_is_stale=False,
        current_session_match=True,
        recommendations=[],
        open_trades=open_trades,
        open_trade_advisories={},
        open_trade_last_prices={},
        watchlist=[],
        watchlist_last_prices={},
        candidates_by_ticker={},
        chart_b64s={},
        daily_management_active_snapshots=active_snapshots,
    )


# --- tests ------------------------------------------------------------------


def test_briefing_md_emits_section_heading_and_per_trade_row():
    """Output contains literal heading '## Daily Management Snapshot' followed
    by a markdown table with the §7.4 column header row + one data row per
    open trade."""
    snap = _make_snapshot_row(
        trade_id=1,
        data_asof_session="2026-05-07",
        open_MFE_R_to_date=1.50,
        open_MAE_R_to_date=0.20,
        maturity_stage="+1.5R_to_+2R",
        trail_MA_eligibility_flag=0,
    )
    inputs = _build_inputs_with_snapshots(
        open_trades=[_open_trade_for(ticker="DHC", trade_id=1)],
        active_snapshots=[snap],
    )
    vm = build_briefing_view_model(inputs)
    md = render_briefing_md(vm)

    assert "## Daily Management Snapshot" in md
    assert (
        "| Ticker | As-of session | MFE-to-date (R) | "
        "MAE-to-date (R) | Maturity stage | Trail-MA eligible |"
    ) in md
    assert "| DHC | 2026-05-07 | 1.50 | 0.20 | +1.5R_to_+2R | no |" in md


def test_briefing_md_subsection_renders_trail_MA_eligible_yes_when_flag_set():
    """When trail_MA_eligibility_flag=1 the data row contains '| yes |' in
    the trail-MA-eligible column."""
    snap = _make_snapshot_row(
        trade_id=1,
        data_asof_session="2026-05-07",
        open_MFE_R_to_date=2.50,
        open_MAE_R_to_date=0.30,
        maturity_stage=">=+2R_trail_eligible",
        trail_MA_eligibility_flag=1,
    )
    inputs = _build_inputs_with_snapshots(
        open_trades=[_open_trade_for(ticker="DHC", trade_id=1)],
        active_snapshots=[snap],
    )
    md = render_briefing_md(build_briefing_view_model(inputs))
    assert (
        "| DHC | 2026-05-07 | 2.50 | 0.30 | >=+2R_trail_eligible | yes |"
    ) in md


def test_briefing_md_emits_no_open_positions_marker_when_no_open_trades():
    """With NO open trades AND no snapshots, heading still appears (stable
    section anchor) followed by literal `_No open positions to manage._`."""
    inputs = _build_inputs_with_snapshots(
        open_trades=[], active_snapshots=[],
    )
    md = render_briefing_md(build_briefing_view_model(inputs))
    assert "## Daily Management Snapshot" in md
    assert "_No open positions to manage._" in md
    assert "| Ticker | As-of session" not in md


def test_briefing_md_distinguishes_open_trades_with_no_snapshots_emitted():
    """Codex R3 Major #3 fix: with open_trades=[DHC, ZZ] but
    daily_management_active_snapshots=[], the rendered MD contains the
    distinguishing marker — operator-actionable signal that something went
    wrong with the snapshot path."""
    inputs = _build_inputs_with_snapshots(
        open_trades=[
            _open_trade_for(ticker="DHC", trade_id=1),
            _open_trade_for(ticker="ZZ", trade_id=2),
        ],
        active_snapshots=[],
    )
    md = render_briefing_md(build_briefing_view_model(inputs))
    assert "## Daily Management Snapshot" in md
    assert (
        "_2 open positions; no daily-management snapshot available "
        "(pipeline step skipped or failed)._"
    ) in md
    assert "_No open positions to manage._" not in md


def test_briefing_md_renders_orphan_snapshot_disjoint_from_open_trades_safely():
    """Codex R3 Minor #2 follow-on: a snapshot row whose trade_id is NOT in
    open_trades (orphan — trade was just closed) MUST be filtered out of the
    rendered subsection."""
    snap_open = _make_snapshot_row(trade_id=1, maturity_stage="0R_to_+1R")
    snap_orphan = _make_snapshot_row(trade_id=99, maturity_stage="0R_to_+1R")
    inputs = _build_inputs_with_snapshots(
        open_trades=[_open_trade_for(ticker="DHC", trade_id=1)],  # only id=1 is open
        active_snapshots=[snap_open, snap_orphan],
    )
    md = render_briefing_md(build_briefing_view_model(inputs))
    assert "DHC" in md
    # Strict assertion: only 1 ticker rendered in the Daily Management
    # subsection table — orphan trade_id=99 produces no row because
    # DailyManagementRecord has no ticker column and no JOIN match exists.
    # Scope the count to the DM subsection (Open Positions section also
    # emits `| DHC |` for the same Trade — plan oversight; deviation
    # documented in return report).
    dm_section = md.split("## Daily Management Snapshot", 1)[1].split("##", 1)[0]
    assert dm_section.count("| DHC |") == 1


def test_briefing_html_emits_section_with_id_and_per_trade_row():
    """HTML output contains `<section id="daily-management-snapshot">` AND
    expected `<td>` cells for the open trade."""
    snap = _make_snapshot_row(
        trade_id=1,
        data_asof_session="2026-05-07",
        open_MFE_R_to_date=1.50,
        open_MAE_R_to_date=0.20,
        maturity_stage="+1.5R_to_+2R",
        trail_MA_eligibility_flag=0,
    )
    inputs = _build_inputs_with_snapshots(
        open_trades=[_open_trade_for(ticker="DHC", trade_id=1)],
        active_snapshots=[snap],
    )
    html = render_briefing_html(build_briefing_view_model(inputs))
    assert '<section id="daily-management-snapshot">' in html
    assert "<td>DHC</td>" in html
    assert "<td>2026-05-07</td>" in html
    assert "<td>+1.5R_to_+2R</td>" in html
