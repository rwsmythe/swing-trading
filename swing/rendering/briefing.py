"""Build BriefingViewModel from primitive inputs (DB rows + computed values).

Caller (pipeline.runner or CLI) does the queries; this module is pure-logic
view-model construction with no I/O.
"""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field

from swing.data.models import (
    Candidate,
    DailyManagementRecord,
    DailyRecommendation,
    Trade,
    WatchlistEntry,
    WeatherRun,
)
from swing.rendering.view_models import (
    AccountTileVM,
    AdvisorySuggestionVM,
    BriefingViewModel,
    CriterionVM,
    DailyManagementSnapshotRowVM,
    OpenPositionVM,
    PipelineTileVM,
    StatusStripVM,
    TickerExpansionVM,
    TodaysDecisionVM,
    WatchlistRowVM,
    WeatherTileVM,
)


@dataclass(frozen=True)
class BriefingInputs:
    action_session_date: str
    data_asof_date: str
    generated_at: str
    weather: WeatherRun | None
    weather_is_stale: bool
    equity: float
    open_count: int
    soft_warn: int
    hard_cap: int
    last_pipeline_ts: str
    pipeline_is_stale: bool
    current_session_match: bool
    recommendations: list[DailyRecommendation]
    open_trades: list[Trade]
    open_trade_advisories: Mapping[int, list[AdvisorySuggestionVM]] = field(default_factory=dict)
    open_trade_last_prices: Mapping[str, float] = field(default_factory=dict)
    watchlist: list[WatchlistEntry] = field(default_factory=list)
    watchlist_last_prices: Mapping[str, float] = field(default_factory=dict)
    candidates_by_ticker: Mapping[str, Candidate] = field(default_factory=dict)
    chart_b64s: Mapping[str, str] = field(default_factory=dict)
    near_trigger_above_pct: float = 0.5
    near_trigger_below_pct: float = 1.0
    # Phase 8 §7.4 — per-open-trade daily-management active snapshots.
    # Sourced from list_open_position_active_snapshots(conn). Default empty
    # tuple keeps the existing call sites back-compatible.
    daily_management_active_snapshots: list[DailyManagementRecord] = field(
        default_factory=list
    )
    # Schwab API arc-closer Sub-bundle D Task T-D.5 — degraded banner input.
    # When non-None, the markdown renderer emits the spec §3.4.4 / §7.2
    # "Schwab integration: degraded" banner citing this endpoint name. The
    # pipeline runner's `_step_export` populates this from
    # `swing.data.repos.schwab_api_calls.is_schwab_degraded(conn)`.
    schwab_degraded_endpoint: str | None = None


def _sizing_implication(status: str) -> str:
    return {
        "Bullish": "Full sizing OK",
        "Caution": "Tighten stops; consider half sizing on new entries",
        "Bearish": "Avoid new longs; tighten stops on opens",
    }.get(status, "Sizing implication unknown")


def _weather_tile(inputs: BriefingInputs) -> WeatherTileVM:
    if inputs.weather is None or inputs.weather_is_stale:
        return WeatherTileVM(
            status="STALE", rationale="Weather data unavailable \u2014 verify before sizing",
            sizing_implication="Caution: verify weather before sizing",
        )
    return WeatherTileVM(
        status=inputs.weather.status,
        rationale=inputs.weather.rationale or "",
        sizing_implication=_sizing_implication(inputs.weather.status),
    )


def _decisions(inputs: BriefingInputs) -> list[TodaysDecisionVM]:
    out: list[TodaysDecisionVM] = []
    for r in inputs.recommendations:
        if r.recommendation != "today_decision":
            continue
        c = inputs.candidates_by_ticker.get(r.ticker)
        tt_score = ""
        vcp_score = ""
        if c is not None:
            tt_pass = sum(1 for cr in c.criteria if cr.layer == "trend_template" and cr.result == "pass")
            tt_total = sum(1 for cr in c.criteria if cr.layer == "trend_template")
            vcp_pass = sum(1 for cr in c.criteria if cr.layer == "vcp" and cr.result == "pass")
            vcp_total = sum(1 for cr in c.criteria if cr.layer == "vcp")
            tt_score = f"{tt_pass}/{tt_total}"
            vcp_score = f"{vcp_pass}/{vcp_total}"
        out.append(TodaysDecisionVM(
            ticker=r.ticker,
            action_text=r.action_text or "",
            entry_target=r.entry_target or 0.0,
            stop_target=r.stop_target or 0.0,
            shares=r.shares or 0,
            risk_dollars=r.risk_dollars or 0.0,
            risk_pct=r.risk_pct or 0.0,
            rationale=r.rationale or "",
            tt_score=tt_score, vcp_score=vcp_score,
            chart_b64=inputs.chart_b64s.get(r.ticker),
        ))
    return out


def _open_positions(inputs: BriefingInputs) -> list[OpenPositionVM]:
    from datetime import date as _date
    today = _date.fromisoformat(inputs.data_asof_date)
    out: list[OpenPositionVM] = []
    for t in inputs.open_trades:
        last = inputs.open_trade_last_prices.get(t.ticker, t.entry_price)
        rps = t.entry_price - t.initial_stop
        r_so_far = (last - t.entry_price) / rps if rps > 0 else 0.0
        unrl = (last - t.entry_price) * t.initial_shares
        dist_to_stop_pct = (last - t.current_stop) / last * 100 if last > 0 else 0.0
        days_open = (today - _date.fromisoformat(t.entry_date)).days
        out.append(OpenPositionVM(
            ticker=t.ticker, entry_price=t.entry_price, current_stop=t.current_stop,
            last_close=last, shares=t.initial_shares, unrealized_pnl=unrl,
            dist_to_stop_pct=dist_to_stop_pct, r_so_far=r_so_far,
            days_open=days_open,
            advisory=list(inputs.open_trade_advisories.get(t.id or 0, [])),
        ))
    return out


def _watchlist_rows(inputs: BriefingInputs) -> list[WatchlistRowVM]:
    out: list[WatchlistRowVM] = []
    for w in inputs.watchlist:
        last = inputs.watchlist_last_prices.get(w.ticker, w.last_close or 0.0)
        target = w.entry_target or 0.0
        if target > 0:
            pct = (last - target) / target * 100
            near = -inputs.near_trigger_below_pct <= pct <= inputs.near_trigger_above_pct
        else:
            pct = 0.0
            near = False
        out.append(WatchlistRowVM(
            ticker=w.ticker, entry_target=target, current_close=last,
            pct_to_pivot=pct, adr_pct=w.last_adr_pct,
            current_stop=w.initial_stop_target or 0.0,
            is_near_trigger=near, status=w.status,
            flag_tags=[],
            qualification_count=w.qualification_count,
        ))
    out.sort(key=lambda r: (not r.is_near_trigger, abs(r.pct_to_pivot)))
    return out


def _expansions(inputs: BriefingInputs) -> list[TickerExpansionVM]:
    out: list[TickerExpansionVM] = []
    for r in inputs.recommendations:
        if r.recommendation != "today_decision":
            continue
        c = inputs.candidates_by_ticker.get(r.ticker)
        if c is None:
            continue
        tt = [
            CriterionVM(name=cr.criterion_name, result=cr.result,
                        value=cr.value, rule=cr.rule)
            for cr in c.criteria if cr.layer == "trend_template"
        ]
        vcp = [
            CriterionVM(name=cr.criterion_name, result=cr.result,
                        value=cr.value, rule=cr.rule)
            for cr in c.criteria if cr.layer == "vcp"
        ]
        out.append(TickerExpansionVM(
            ticker=r.ticker,
            narrative=r.rationale or "",
            trend_template_grid=tt,
            vcp_grid=vcp,
            chart_b64=inputs.chart_b64s.get(r.ticker),
        ))
    return out


def _daily_management_snapshots(
    inputs: BriefingInputs,
) -> tuple[list[DailyManagementSnapshotRowVM], int]:
    """Resolve ticker via JOIN against inputs.open_trades by trade_id, filter
    out orphan snapshots whose trade_id is no longer in open_trades (closed
    trades belong to Phase 6 post-mortem surfaces, not Phase 8 briefing).

    Returns ``(rows, open_trade_count_without_snapshot)`` where the latter is
    populated only if open_trades is non-empty AND no snapshots match — drives
    the operator-actionable "no daily-management snapshot available" marker
    per Codex R3 M3.
    """
    open_by_id: dict[int, Trade] = {
        t.id: t for t in inputs.open_trades if t.id is not None
    }
    rows: list[DailyManagementSnapshotRowVM] = []
    for snap in inputs.daily_management_active_snapshots:
        trade = open_by_id.get(snap.trade_id)
        if trade is None:
            # Orphan: snapshot's trade_id not in open_trades — skip.
            continue
        rows.append(DailyManagementSnapshotRowVM(
            ticker=trade.ticker,
            data_asof_session=snap.data_asof_session,
            open_MFE_R_to_date=snap.open_MFE_R_to_date,
            open_MAE_R_to_date=snap.open_MAE_R_to_date,
            maturity_stage=snap.maturity_stage,
            trail_MA_eligibility_flag=snap.trail_MA_eligibility_flag,
        ))
    no_snapshot_count = 0
    if open_by_id and not rows:
        no_snapshot_count = len(open_by_id)
    return rows, no_snapshot_count


def build_briefing_view_model(inputs: BriefingInputs) -> BriefingViewModel:
    return BriefingViewModel(
        action_session_date=inputs.action_session_date,
        data_asof_date=inputs.data_asof_date,
        generated_at=inputs.generated_at,
        status_strip=StatusStripVM(
            weather=_weather_tile(inputs),
            account=AccountTileVM(
                equity=inputs.equity, open_count=inputs.open_count,
                soft_warn=inputs.soft_warn, hard_cap=inputs.hard_cap,
            ),
            pipeline=PipelineTileVM(
                last_run_ts=inputs.last_pipeline_ts,
                is_stale=inputs.pipeline_is_stale,
                current_session_match=inputs.current_session_match,
            ),
        ),
        todays_decisions=_decisions(inputs),
        open_positions=_open_positions(inputs),
        watchlist=_watchlist_rows(inputs),
        expansions=_expansions(inputs),
        daily_management_snapshots=_daily_management_snapshots(inputs)[0],
        daily_management_open_trade_count_without_snapshot=(
            _daily_management_snapshots(inputs)[1]
        ),
        schwab_degraded_endpoint=inputs.schwab_degraded_endpoint,
    )
