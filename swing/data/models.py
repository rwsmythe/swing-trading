"""Dataclass representations of DB rows."""
from __future__ import annotations

from dataclasses import dataclass


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
    status: str  # 'open' | 'closed'
    watchlist_entry_target: float | None
    watchlist_initial_stop: float | None
    notes: str | None
    # Operator-frozen pre-trade hypothesis (free-text, optional). Captured at
    # entry time and never mutated — same anti-rationalization discipline as
    # research-study pre-registration. Default None preserves existing call
    # sites that construct Trade(...) without the new field. Migration 0007.
    hypothesis_label: str | None = None


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
    source: str        # 'aplus' | 'near_proximity'
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


@dataclass(frozen=True, init=False, slots=True)
class PipelinePatternClassification:
    """One row of `pipeline_pattern_classifications` (migration 0009).

    NULL semantics — spec §3.2.1:
      - pattern='flag', confidence=0.0–1.0 → detection.
      - pattern='none', confidence=NULL    → evaluated negative.
      - pattern=NULL,   confidence=NULL    → classifier error
        (components_json carries an "error" key).
    """
    _id: int | None
    _pipeline_run_id: int
    _ticker: str
    _pattern: str | None
    _confidence: float | None
    _components_json: str
    _pivot: float | None
    _pole_high: float | None
    _flag_low: float | None
    _pole_start_date: str | None
    _pole_end_date: str | None
    _flag_start_date: str | None
    _flag_end_date: str | None
    _computed_at: str

    def __init__(
        self,
        id: int | None,
        pipeline_run_id: int,
        ticker: str,
        pattern: str | None,
        confidence: float | None,
        components_json: str,
        pivot: float | None,
        pole_high: float | None,
        flag_low: float | None,
        pole_start_date: str | None,
        pole_end_date: str | None,
        flag_start_date: str | None,
        flag_end_date: str | None,
        computed_at: str,
    ) -> None:
        object.__setattr__(self, "_id", id)
        object.__setattr__(self, "_pipeline_run_id", pipeline_run_id)
        object.__setattr__(self, "_ticker", ticker)
        object.__setattr__(self, "_pattern", pattern)
        object.__setattr__(self, "_confidence", confidence)
        object.__setattr__(self, "_components_json", components_json)
        object.__setattr__(self, "_pivot", pivot)
        object.__setattr__(self, "_pole_high", pole_high)
        object.__setattr__(self, "_flag_low", flag_low)
        object.__setattr__(self, "_pole_start_date", pole_start_date)
        object.__setattr__(self, "_pole_end_date", pole_end_date)
        object.__setattr__(self, "_flag_start_date", flag_start_date)
        object.__setattr__(self, "_flag_end_date", flag_end_date)
        object.__setattr__(self, "_computed_at", computed_at)

    @property
    def id(self) -> int | None:
        return self._id

    @property
    def pipeline_run_id(self) -> int:
        return self._pipeline_run_id

    @property
    def ticker(self) -> str:
        return self._ticker

    @property
    def pattern(self) -> str | None:
        return self._pattern

    @property
    def confidence(self) -> float | None:
        return self._confidence

    @property
    def components_json(self) -> str:
        return self._components_json

    @property
    def pivot(self) -> float | None:
        return self._pivot

    @property
    def pole_high(self) -> float | None:
        return self._pole_high

    @property
    def flag_low(self) -> float | None:
        return self._flag_low

    @property
    def pole_start_date(self) -> str | None:
        return self._pole_start_date

    @property
    def pole_end_date(self) -> str | None:
        return self._pole_end_date

    @property
    def flag_start_date(self) -> str | None:
        return self._flag_start_date

    @property
    def flag_end_date(self) -> str | None:
        return self._flag_end_date

    @property
    def computed_at(self) -> str:
        return self._computed_at
