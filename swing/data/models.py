"""Dataclass representations of DB rows."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class CriterionResult:
    criterion_name: str
    layer: str  # 'trend_template' | 'vcp' | 'risk'
    result: str  # 'pass' | 'fail' | 'na'
    value: str | None = None
    rule: str | None = None


@dataclass(frozen=True)
class Candidate:
    ticker: str
    bucket: str  # 'aplus' | 'watch' | 'skip' | 'error' | 'excluded'
    close: float | None
    pivot: float | None
    initial_stop: float | None
    adr_pct: float | None
    tight_streak: int | None
    pullback_pct: float | None
    prior_trend_pct: float | None
    rs_rank: int | None
    rs_return_12w_vs_spy: float | None
    rs_method: str  # 'universe' | 'fallback_spy' | 'unavailable'
    pattern_tag: str | None
    notes: str | None
    criteria: tuple[CriterionResult, ...]
    # Migration 0012 — Finviz Sector + Industry passthrough. Defaults to
    # empty string so any caller that constructs Candidate without these
    # fields (older test fixtures, ETF-blocklist / open-position synthesis
    # in _step_evaluate, classifier-error rows) continues to work; the
    # _step_evaluate path uses dataclasses.replace to populate from CSV.
    sector: str = ""
    industry: str = ""


@dataclass(frozen=True)
class EvaluationRun:
    id: int | None
    run_ts: str  # ISO 8601
    data_asof_date: str  # YYYY-MM-DD
    action_session_date: str  # YYYY-MM-DD
    finviz_csv_path: str | None
    tickers_evaluated: int
    aplus_count: int
    watch_count: int
    skip_count: int
    excluded_count: int
    error_count: int
    rs_universe_version: str | None = None
    rs_universe_hash: str | None = None


@dataclass(frozen=True)
class Trade:
    id: int | None
    ticker: str
    entry_date: str
    entry_price: float
    initial_shares: int
    initial_stop: float
    current_stop: float
    status: str  # 'open' | 'closed' — A.0–A.3 transition window; A.3 drops this field.
    # Phase 7 Sub-A T0 — pre-position the lifecycle state field alongside the
    # legacy status column. Default 'entered' is the active-trade analogue of
    # status='open'. Both fields coexist during the A.0–A.3 window; A.3 (Sub-A
    # T3) drops `status` from the dataclass. Migration 0014 will populate the
    # state column on existing rows.
    watchlist_entry_target: float | None
    watchlist_initial_stop: float | None
    notes: str | None
    # Operator-frozen pre-trade hypothesis (free-text, optional). Captured at
    # entry time and never mutated — same anti-rationalization discipline as
    # research-study pre-registration. Default None preserves existing call
    # sites that construct Trade(...) without the new field. Migration 0007.
    hypothesis_label: str | None = None
    # Phase 7 Sub-A T0 — lifecycle state field, pre-positioned alongside
    # legacy `status` (declared above as required, no default). Default
    # 'entered' is the active-trade analogue of status='open'; mapped per
    # plan §3 fixture-intent table (open→entered, closed→closed,
    # closed+reviewed_at→reviewed). Both fields coexist during the A.0–A.3
    # transition window; A.3 (Sub-A T3) drops `status`. Migration 0014 will
    # populate the state column on existing DB rows.
    state: str = "entered"
    # Chart pattern columns (migration 0010). All four NULL unless the
    # pipeline classification step ran for this ticker's pipeline run.
    # chart_pattern_operator is operator override (free-text, see spec §3.2.2).
    chart_pattern_algo: str | None = None
    chart_pattern_algo_confidence: float | None = None
    chart_pattern_operator: str | None = None
    chart_pattern_classification_pipeline_run_id: int | None = None
    # Migration 0012 — Finviz Sector + Industry, frozen-at-entry per the
    # snapshot-at-entry-surface pattern (precedents: hypothesis_label /
    # 0007; chart_pattern_* / 0010). Defaults to empty string so callers
    # that don't yet plumb these fields keep working; the entry surface
    # (web form + CLI) resolves the actual value from the candidate row
    # at form/CLI render time and persists AS-IS via record_entry.
    sector: str = ""
    industry: str = ""
    # Phase 6 (migration 0013) — review surface fields.
    reviewed_at: str | None = None
    mistake_tags: str | None = None
    entry_grade: str | None = None
    management_grade: str | None = None
    exit_grade: str | None = None
    process_grade: str | None = None
    disqualifying_process_violation: bool | None = None
    realized_R_if_plan_followed: float | None = None  # noqa: N815
    mistake_cost_confidence: str | None = None
    lesson_learned: str | None = None


@dataclass(frozen=True)
class Exit:
    id: int | None
    trade_id: int
    exit_date: str
    exit_price: float
    shares: int
    reason: str
    realized_pnl: float
    r_multiple: float
    notes: str | None


@dataclass(frozen=True)
class CashMovement:
    id: int | None
    date: str
    kind: str  # 'deposit' | 'withdraw'
    amount: float
    ref: str | None
    note: str | None


@dataclass(frozen=True)
class TradeEvent:
    id: int | None
    trade_id: int
    ts: str
    event_type: str  # 'entry' | 'stop_adjust' | 'note' | 'exit' | 'flag'
    payload_json: str
    rationale: str | None
    notes: str | None = None


@dataclass(frozen=True)
class WatchlistEntry:
    ticker: str
    added_date: str
    last_qualified_date: str
    status: str  # 'watch' | 'skip' | 'near_trigger'
    qualification_count: int
    not_qualified_streak: int
    last_data_asof_date: str
    entry_target: float | None
    initial_stop_target: float | None
    last_close: float | None
    last_pivot: float | None
    last_stop: float | None
    last_adr_pct: float | None
    missing_criteria: str | None
    notes: str | None


@dataclass(frozen=True)
class WatchlistArchiveEntry:
    id: int | None
    ticker: str
    added_date: str
    removed_date: str
    reason: str
    qualification_count: int | None
    last_data_asof_date: str | None
    notes: str | None


@dataclass(frozen=True)
class WeatherRun:
    id: int | None
    run_ts: str
    asof_date: str
    ticker: str
    status: str  # 'Bullish' | 'Caution' | 'Bearish'
    close: float
    sma10: float | None
    sma20: float | None
    sma50: float | None
    slope20_5bar: float | None
    slope10_5bar: float | None
    rationale: str | None


@dataclass(frozen=True)
class DailyRecommendation:
    id: int | None
    evaluation_run_id: int
    data_asof_date: str
    action_session_date: str
    ticker: str
    recommendation: str  # 'today_decision' | 'watchlist_watch' | 'watchlist_skip' | 'near_trigger'
    action_text: str | None
    entry_target: float | None
    stop_target: float | None
    shares: int | None
    risk_dollars: float | None
    risk_pct: float | None
    rationale: str | None


@dataclass(frozen=True)
class PipelineRun:
    id: int | None
    started_ts: str
    finished_ts: str | None
    trigger: str  # 'scheduled' | 'manual'
    data_asof_date: str
    action_session_date: str
    state: str  # 'running' | 'complete' | 'failed' | 'blocked' | 'force_cleared'
    lease_token: str
    lease_heartbeat_ts: str | None
    last_step_progress_ts: str | None
    current_step: str | None
    weather_status: str | None
    evaluation_status: str | None
    watchlist_status: str | None
    recommendations_status: str | None
    charts_status: str | None
    export_status: str | None
    rs_universe_version: str | None
    rs_universe_hash: str | None
    finviz_csv_path: str | None
    error_message: str | None
    warnings_json: str | None
    # Tranche C T1: structural FK to the pipeline's own evaluation_runs row.
    # NULL for legacy rows (pre-migration-0006); chart_scope resolver and
    # today_decisions retain heuristic fallbacks for those.
    evaluation_run_id: int | None = None


@dataclass(frozen=True)
class PipelineChartTarget:
    """One row in `pipeline_chart_targets` — Tranche C T1.

    Persists the per-pipeline-run set of chart-target tickers (A+ ∪ near-by-
    proximity watchlist top-N) and per-ticker chart-step outcome. Replaces the
    chart_scope resolver's prior live-watchlist re-derivation (drift mode B)
    and enables the chart-reason split (T5: fetcher_failed vs too_few_bars).
    """
    id: int | None
    pipeline_run_id: int
    ticker: str
    source: str        # 'aplus' | 'open_position' | 'tag_aware_top_n' | 'near_proximity' (legacy)
    chart_status: str  # 'pending' | 'ok' | 'fetcher_failed' | 'too_few_bars'


@dataclass(frozen=True)
class ConfigRevision:
    id: int | None
    ts: str
    payload_json: str
    source: str  # 'cli' | 'web'


@dataclass(frozen=True)
class HypothesisRegistryEntry:
    """One row of `hypothesis_registry` (migration 0008).

    Pre-registered investigation plan v0.1: the four seeded hypotheses,
    target sample sizes, and tripwire thresholds are FROZEN at the
    migration. CLI may flip `status` and record `status_change_reason`;
    everything else is mutated only via a NEW migration with explicit
    version bump (anti-rationalization discipline; brief §3 + §5).
    """
    id: int | None
    name: str
    statement: str
    target_sample_size: int
    decision_criteria: str
    status: str  # 'active' | 'paused' | 'closed-escaped' | 'closed-target-met'
    consecutive_loss_tripwire: int
    absolute_loss_tripwire_pct: float
    created_at: str
    status_changed_at: str | None = None
    status_change_reason: str | None = None
    notes: str | None = None


@dataclass(frozen=True)
class PipelinePatternClassification:
    """One row of `pipeline_pattern_classifications` (migration 0009).

    NULL semantics — spec §3.2.1:
      - pattern='flag', confidence=0.0–1.0 → detection.
      - pattern='none', confidence=NULL    → evaluated negative.
      - pattern=NULL,   confidence=NULL    → classifier error
        (components_json carries an "error" key).
    """
    id: int | None
    pipeline_run_id: int
    ticker: str
    pattern: str | None        # 'none' | 'flag' | None
    confidence: float | None
    components_json: str
    pivot: float | None
    pole_high: float | None
    flag_low: float | None
    pole_start_date: date | None
    pole_end_date: date | None
    flag_start_date: date | None
    flag_end_date: date | None
    computed_at: str


@dataclass(frozen=True)
class ReviewLog:
    """One row of the review_log table (migration 0013).
    Slim 14 + 7 persisted aggregates per Phase 6 locked decision §2.5."""
    review_id: int | None
    review_type: str  # daily/weekly/monthly/quarterly/circuit_breaker
    period_start: str
    period_end: str
    scheduled_date: str
    completed_date: str | None
    skipped: bool
    duration_minutes: int | None
    n_trades_reviewed: int
    total_mistake_cost_R: float  # noqa: N815
    total_lucky_violation_R: float  # noqa: N815
    primary_lesson: str | None
    next_period_focus: str | None
    created_at: str
    net_R_effective: float | None = None  # noqa: N815
    expectancy_R_effective: float | None = None  # noqa: N815
    win_rate: float | None = None
    avg_win_R: float | None = None  # noqa: N815
    avg_loss_R: float | None = None  # noqa: N815
    profit_factor: float | None = None
    max_drawdown_R: float | None = None  # noqa: N815
