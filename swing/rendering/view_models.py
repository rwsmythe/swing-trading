"""View models for briefing rendering.

Frozen dataclasses — Jinja templates do presentation only, no computation.
Reused by Phase 3 for HTMX partials.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class WeatherTileVM:
    status: str  # 'Bullish' | 'Caution' | 'Bearish'
    rationale: str
    sizing_implication: str


@dataclass(frozen=True)
class AccountTileVM:
    equity: float
    open_count: int
    soft_warn: int
    hard_cap: int


@dataclass(frozen=True)
class PipelineTileVM:
    last_run_ts: str
    is_stale: bool
    current_session_match: bool


@dataclass(frozen=True)
class StatusStripVM:
    weather: WeatherTileVM
    account: AccountTileVM
    pipeline: PipelineTileVM


@dataclass(frozen=True)
class TodaysDecisionVM:
    ticker: str
    action_text: str
    entry_target: float
    stop_target: float
    shares: int
    risk_dollars: float
    risk_pct: float
    rationale: str
    tt_score: str
    vcp_score: str
    chart_b64: str | None
    chart_href: str | None = None


@dataclass(frozen=True)
class AdvisorySuggestionVM:
    rule: str
    message: str


@dataclass(frozen=True)
class OpenPositionVM:
    ticker: str
    entry_price: float
    current_stop: float
    last_close: float
    shares: int
    unrealized_pnl: float
    dist_to_stop_pct: float
    r_so_far: float
    days_open: int
    advisory: list[AdvisorySuggestionVM] = field(default_factory=list)


@dataclass(frozen=True)
class WatchlistRowVM:
    ticker: str
    entry_target: float
    current_close: float
    pct_to_pivot: float
    adr_pct: float | None
    current_stop: float
    is_near_trigger: bool
    status: str
    flag_tags: list[str] = field(default_factory=list)
    qualification_count: int = 0


@dataclass(frozen=True)
class CriterionVM:
    name: str
    result: str
    value: str | None
    rule: str | None


@dataclass(frozen=True)
class TickerExpansionVM:
    ticker: str
    narrative: str
    trend_template_grid: list[CriterionVM] = field(default_factory=list)
    vcp_grid: list[CriterionVM] = field(default_factory=list)
    chart_b64: str | None = None
    chart_href: str | None = None


@dataclass(frozen=True)
class DailyManagementSnapshotRowVM:
    """Phase 8 spec §7.4 — one row of the briefing's "Daily Management
    Snapshot" subsection. Ticker resolved by JOIN against open_trades by
    trade_id (DailyManagementRecord has no ticker column — Codex R4 M5)."""
    ticker: str
    data_asof_session: str
    open_MFE_R_to_date: float | None  # noqa: N815
    open_MAE_R_to_date: float | None  # noqa: N815
    maturity_stage: str | None
    trail_MA_eligibility_flag: int | None  # noqa: N815  # 0|1


@dataclass(frozen=True)
class BriefingViewModel:
    action_session_date: str
    data_asof_date: str
    generated_at: str
    status_strip: StatusStripVM
    todays_decisions: list[TodaysDecisionVM] = field(default_factory=list)
    open_positions: list[OpenPositionVM] = field(default_factory=list)
    watchlist: list[WatchlistRowVM] = field(default_factory=list)
    expansions: list[TickerExpansionVM] = field(default_factory=list)
    daily_management_snapshots: list[DailyManagementSnapshotRowVM] = field(default_factory=list)
    # Operator-actionable signal: open_trades count when no snapshots emitted.
    # Drives the "no daily-management snapshot available" marker per Codex R3 M3.
    daily_management_open_trade_count_without_snapshot: int = 0
    # Schwab API arc-closer Sub-bundle D Task T-D.5 — degraded banner.
    # When non-None, the markdown renderer emits the spec §3.4.4 / §7.2
    # "Schwab integration: degraded" banner citing this endpoint name.
    # Default None preserves call-site backwards compatibility (other
    # composition surfaces — TestClient web fixtures, ad-hoc CLI renders —
    # do not need to populate this field; only `_step_export` does).
    schwab_degraded_endpoint: str | None = None
    # Phase 12 Sub-bundle C T-C.8/T-C.9 — reconciliation status counters
    # threaded from `BriefingInputs`; rendered as a separate
    # "Reconciliation status" section by briefing_md.py when EITHER
    # field is > 0 (avoid noise on clean runs per spec §7.5).
    reconciliation_pending_count: int = 0
    reconciliation_tier1_recent_count: int = 0
    # Phase 12.5 #1 T-1.11 — multi-leg tier-1 auto-redirect counter
    # (latest completed reconciliation run, DISTINCT-discrepancy semantic
    # per F18; banner-clears semantic per spec §8.4 + §11.2). Briefing.md
    # renders a verbatim F22 line "- Multi-leg auto-redirects applied
    # this run: K" WHEN K > 0. Default 0 preserves back-compat with
    # existing call sites.
    reconciliation_tier1_multi_leg_redirected_count: int = 0
