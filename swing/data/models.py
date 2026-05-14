"""Dataclass representations of DB rows."""
from __future__ import annotations

import re
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
    """Phase 7 Sub-A T3 — Trade dataclass.

    `status` (legacy 'open'|'closed') is dropped in this task; `state` is now
    the required lifecycle field ('entered'|'managing'|'partial_exited'|
    'closed'|'reviewed'). Migration 0014 (Phase 7 T2) drops the corresponding
    SQL column and adds the 24 fields below. Production consumers
    (repos.trades, web view models, journal.* etc.) still reference the dropped
    column and will be rewritten in Sub-A T6.
    """
    id: int | None
    ticker: str
    entry_date: str
    entry_price: float
    initial_shares: int
    initial_stop: float
    current_stop: float
    state: str  # 'entered'|'managing'|'partial_exited'|'closed'|'reviewed'
    watchlist_entry_target: float | None
    watchlist_initial_stop: float | None
    notes: str | None
    # Operator-frozen pre-trade hypothesis (free-text, optional). Captured at
    # entry time and never mutated — same anti-rationalization discipline as
    # research-study pre-registration. Migration 0007.
    hypothesis_label: str | None = None
    # Chart pattern columns (migration 0010). All four NULL unless the
    # pipeline classification step ran for this ticker's pipeline run.
    chart_pattern_algo: str | None = None
    chart_pattern_algo_confidence: float | None = None
    chart_pattern_operator: str | None = None
    chart_pattern_classification_pipeline_run_id: int | None = None
    # Migration 0012 — Finviz Sector + Industry, frozen-at-entry.
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
    # Phase 7 (migration 0014) — lifecycle fields atomic with `state`.
    # Schema enforces NOT NULL on trade_origin, pre_trade_locked_at,
    # current_size; the entry service in Sub-B will set them atomically.
    # current_avg_cost and last_fill_at are NULLABLE (no fills yet).
    trade_origin: str = "manual_off_pipeline"
    pre_trade_locked_at: str = ""
    current_size: float = 0.0
    current_avg_cost: float | None = None
    last_fill_at: str | None = None
    # Phase 7 (migration 0014) — pre-trade decision fields. All NULLABLE;
    # legacy rows persist NULL. Captured at entry-form lock time; immutable
    # afterward.
    thesis: str | None = None
    why_now: str | None = None
    invalidation_condition: str | None = None
    expected_scenario: str | None = None
    premortem_technical: str | None = None
    premortem_market_sector: str | None = None
    premortem_execution: str | None = None
    premortem_additional: str | None = None
    event_risk_present: int | None = None  # 0|1
    event_handling: str | None = None
    event_type: str | None = None
    event_date: str | None = None
    gap_risk_present: int | None = None  # 0|1
    gap_risk_handling: str | None = None
    emotional_state_pre_trade: str | None = None  # JSON-list TEXT
    market_regime: str | None = None
    catalyst: str | None = None
    catalyst_other_description: str | None = None
    # Phase 8 (migration 0016) — pre-trade-locked R-multiple target. NULL for
    # legacy rows + non-target trades. CHECK constraint enforces > 0 when set.
    planned_target_R: float | None = None  # noqa: N815


@dataclass(frozen=True)
class Fill:
    """Phase 7 Sub-A T3 — Fill dataclass mirroring the fills schema.

    Migration 0014 created `fills` and migrated existing `exits` rows into it
    (action='exit'). Future entries/trims/stops also write here. The 4-action
    enum is enforced by SQL CHECK; fee/reason/rule_based/manual_entry_confidence
    are nullable.
    """
    fill_id: int | None
    trade_id: int
    fill_datetime: str  # ISO-8601
    action: str  # 'entry'|'trim'|'exit'|'stop'
    quantity: float
    price: float
    reason: str | None = None
    rule_based: int | None = None  # 0|1
    fees: float | None = None
    manual_entry_confidence: str | None = None  # 'high'|'normal'|'low'
    reconciliation_status: str = "unreconciled"
    tos_match_id: str | None = None


# Exit dataclass DELETED in Phase 7 Sub-C C.14. Data lives in Fill (migration
# 0014). All consumers migrated to per-module ``_list_all_exitshape_via_fills``
# adapters that wrap ``swing/trades/derived_metrics.py`` (single source of math
# truth). Importing ``Exit`` from this module now correctly raises ImportError;
# regression test in ``tests/data/test_phase7_shim_removal.py``.


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


@dataclass(frozen=True)
class DailyManagementRecord:
    """One row of daily_management_records (migration 0016 — Phase 8).

    Single-table-with-discriminator: ``record_type`` is either
    ``'daily_snapshot'`` (pipeline-emitted; UPSERT-keyed on
    ``(trade_id, data_asof_session, mfe_mae_precision_level)``) or
    ``'event_log'`` (operator-discretionary). Position-state fields are
    NULLABLE on the schema; the validator enforces presence per
    ``OPERATION_REQUIRED_FIELDS`` for ``snapshot_emit`` (all required) but
    not for ``event_log_emit`` (all optional).

    The 42 fields below mirror spec §3.1 column order: 10 metadata + 14
    position-state + 2 trail-MA stamp/cache + 16 operator-input.
    """
    # Metadata (10):
    management_record_id: int | None
    trade_id: int
    record_type: str  # 'daily_snapshot' | 'event_log'
    review_date: str
    data_asof_session: str
    created_at: str
    mfe_mae_precision_level: str  # 'daily_approximate' | 'intraday_estimated' | 'intraday_exact'
    pipeline_run_id: int | None
    is_superseded: int  # 0|1
    superseded_by_record_id: int | None
    # Position-state (14):
    current_price: float | None
    current_stop: float | None
    current_size: float | None
    current_avg_cost: float | None
    open_R_effective: float | None  # noqa: N815
    open_MFE_R_to_date: float | None  # noqa: N815
    open_MAE_R_to_date: float | None  # noqa: N815
    intraday_high: float | None
    intraday_low: float | None
    position_capital_utilization_pct: float | None
    position_capital_denominator_dollars: float | None
    position_portfolio_heat_contribution_dollars: float | None
    maturity_stage: str | None
    trail_MA_candidate_price: float | None  # noqa: N815
    # Trail-MA per-row stamp + cached eligibility (2):
    trail_MA_period_days: int | None  # noqa: N815
    trail_MA_eligibility_flag: int | None  # noqa: N815  # 0|1
    # Operator-input (16):
    thesis_status: str | None
    prior_stop: float | None
    new_stop: float | None
    linked_trade_event_id: int | None
    stop_changed: int | None  # 0|1
    stop_change_reason: str | None
    volume_behavior: str | None
    relative_strength_status: str | None
    market_regime_change: int | None  # 0|1
    sector_condition_change: int | None  # 0|1
    news_or_event_update: str | None
    action_taken: str | None
    action_reason: str | None
    emotional_state: str | None  # JSON-list TEXT
    rule_violation_suspected: int | None  # 0|1
    management_notes: str | None


@dataclass(frozen=True)
class FinvizApiCall:
    """Audit row for one Finviz Elite API fetch attempt.

    `signature_hash` is None for skipped/error rows; populated only on status='ok'.
    `rate_limit_remaining` is best-effort — Finviz does not document a
    standardized rate-limit header; absent → None.
    """
    call_id: int | None
    ts: str  # ISO 8601, naive datetime per Phase 7 Sub-B convention
    screen_query: str
    status: str  # 'ok' | 'error' | 'skipped_manual_override'
    row_count: int | None
    response_time_ms: int | None
    rate_limit_remaining: int | None
    signature_hash: str | None
    error_message: str | None


# ============================================================================
# Phase 9 — risk_policy / reconciliation / hypothesis_status_history /
# account_equity_snapshots dataclass models.
# ============================================================================


@dataclass(frozen=True)
class RiskPolicy:
    """Versioned snapshot of operator-tunable risk constants (spec §3.1; 34 fields).

    Per spec §3.1 + plan §A.0.1 reconciliation: 34 columns, NOT 28 — the spec's
    "28 columns" subtotal is a brainstorm-phase miscount; the column LIST is the
    binding artifact (Codex R1 Major #2 fix).

    ``__post_init__`` validates beyond what SQL CHECK can enforce (NaN/inf
    rejection on REAL fields per Bundle 2/3 pattern; cross-field drawdown
    enable invariants per spec §3.1 R1 Major #7; sum-to-1.0 process_grade_weight
    cross-field per spec §3.1 R1 Minor #4). This is defense-in-depth on top of
    the schema-level CHECKs in 0017 — the dataclass is the binding artifact for
    service-layer construction.
    """

    # Metadata (7):
    policy_id: int
    effective_from: str
    effective_to: str | None
    is_active: int
    superseded_by_policy_id: int | None
    created_at: str
    policy_notes: str | None

    # Trading-risk (7):
    max_account_risk_per_trade_pct: float
    max_concurrent_positions: int
    max_portfolio_heat_pct: float
    max_sector_concentration_positions: int
    consecutive_losses_pause_threshold: int
    consecutive_losses_pause_action: str
    consecutive_losses_streak_reset: str

    # Drawdown circuit breaker (5; default opt-in disabled per spec §1.4):
    drawdown_circuit_breaker_enabled: int
    drawdown_pause_threshold_R: float | None  # noqa: N815  -- spec column name
    drawdown_pause_action: str | None
    drawdown_size_reduction_pct: float | None
    drawdown_recovery_threshold_R: float | None  # noqa: N815  -- spec column name

    # Capital + sizing (1):
    capital_floor_constant_dollars: float

    # Statistics-methodology (8):
    scratch_epsilon_R: float  # noqa: N815  -- spec column name
    review_lag_threshold_days: int
    low_sample_size_threshold_class_a_n: int
    low_sample_size_threshold_class_b_n: int
    low_sample_size_threshold_class_c_n: int
    low_sample_size_threshold_class_d_n: int
    global_confidence_floor_n: int
    bootstrap_resample_count: int

    # Process-grade weights (3; sum to 1.0):
    process_grade_weight_entry: float
    process_grade_weight_management: float
    process_grade_weight_exit: float

    # MFE/MAE + trail-MA (3):
    mfe_mae_default_precision_level: str
    trail_MA_period_days: int  # noqa: N815  -- spec column name
    trail_MA_post_2R_period_days: int | None  # noqa: N815  -- spec column name

    _DRAWDOWN_ACTIONS = ("halt_new_entries", "reduce_size")
    _MFE_PRECISION = ("daily_approximate", "intraday_estimated", "intraday_exact")
    _CONSEC_PAUSE = ("review_required",)
    _CONSEC_RESET = ("review_completed",)

    def __post_init__(self) -> None:
        import math

        # NaN / inf rejection on every REAL field that's bound non-None.
        _real_fields = (
            ("max_account_risk_per_trade_pct", self.max_account_risk_per_trade_pct),
            ("max_portfolio_heat_pct", self.max_portfolio_heat_pct),
            ("drawdown_pause_threshold_R", self.drawdown_pause_threshold_R),
            ("drawdown_size_reduction_pct", self.drawdown_size_reduction_pct),
            ("drawdown_recovery_threshold_R", self.drawdown_recovery_threshold_R),
            ("capital_floor_constant_dollars", self.capital_floor_constant_dollars),
            ("scratch_epsilon_R", self.scratch_epsilon_R),
            ("process_grade_weight_entry", self.process_grade_weight_entry),
            ("process_grade_weight_management", self.process_grade_weight_management),
            ("process_grade_weight_exit", self.process_grade_weight_exit),
        )
        for name, value in _real_fields:
            if value is None:
                continue
            if not math.isfinite(value):
                raise ValueError(
                    f"{name} not finite (NaN/inf rejected); got {value!r}"
                )

        # Range checks (mirror SQL CHECKs but with clearer error messages).
        if self.max_account_risk_per_trade_pct <= 0:
            raise ValueError(
                "max_account_risk_per_trade_pct must be > 0; got "
                f"{self.max_account_risk_per_trade_pct}"
            )
        if self.max_concurrent_positions <= 0:
            raise ValueError(
                f"max_concurrent_positions must be > 0; got "
                f"{self.max_concurrent_positions}"
            )
        if self.max_portfolio_heat_pct <= 0:
            raise ValueError(
                f"max_portfolio_heat_pct must be > 0; got "
                f"{self.max_portfolio_heat_pct}"
            )
        if self.max_sector_concentration_positions <= 0:
            raise ValueError(
                "max_sector_concentration_positions must be > 0; got "
                f"{self.max_sector_concentration_positions}"
            )
        if self.consecutive_losses_pause_threshold <= 0:
            raise ValueError(
                "consecutive_losses_pause_threshold must be > 0; got "
                f"{self.consecutive_losses_pause_threshold}"
            )
        if self.capital_floor_constant_dollars <= 0:
            raise ValueError(
                "capital_floor_constant_dollars must be > 0; got "
                f"{self.capital_floor_constant_dollars}"
            )
        if self.scratch_epsilon_R <= 0:
            raise ValueError(
                f"scratch_epsilon_R must be > 0; got {self.scratch_epsilon_R}"
            )
        if self.review_lag_threshold_days <= 0:
            raise ValueError(
                "review_lag_threshold_days must be > 0; got "
                f"{self.review_lag_threshold_days}"
            )
        for fname, fval in (
            ("low_sample_size_threshold_class_a_n", self.low_sample_size_threshold_class_a_n),
            ("low_sample_size_threshold_class_b_n", self.low_sample_size_threshold_class_b_n),
            ("low_sample_size_threshold_class_c_n", self.low_sample_size_threshold_class_c_n),
            ("low_sample_size_threshold_class_d_n", self.low_sample_size_threshold_class_d_n),
            ("global_confidence_floor_n", self.global_confidence_floor_n),
            ("bootstrap_resample_count", self.bootstrap_resample_count),
            ("trail_MA_period_days", self.trail_MA_period_days),
        ):
            if fval <= 0:
                raise ValueError(f"{fname} must be > 0; got {fval}")
        if (
            self.trail_MA_post_2R_period_days is not None
            and self.trail_MA_post_2R_period_days <= 0
        ):
            raise ValueError(
                "trail_MA_post_2R_period_days must be > 0 or None; got "
                f"{self.trail_MA_post_2R_period_days}"
            )

        # Enum validation.
        if self.consecutive_losses_pause_action not in self._CONSEC_PAUSE:
            raise ValueError(
                f"consecutive_losses_pause_action must be in {self._CONSEC_PAUSE}; "
                f"got {self.consecutive_losses_pause_action!r}"
            )
        if self.consecutive_losses_streak_reset not in self._CONSEC_RESET:
            raise ValueError(
                f"consecutive_losses_streak_reset must be in {self._CONSEC_RESET}; "
                f"got {self.consecutive_losses_streak_reset!r}"
            )
        if self.mfe_mae_default_precision_level not in self._MFE_PRECISION:
            raise ValueError(
                "mfe_mae_default_precision_level must be in "
                f"{self._MFE_PRECISION}; got "
                f"{self.mfe_mae_default_precision_level!r}"
            )

        # Process-grade weights: each in (0, 1) AND sum to 1.0 ±1e-9.
        for fname, fval in (
            ("process_grade_weight_entry", self.process_grade_weight_entry),
            ("process_grade_weight_management", self.process_grade_weight_management),
            ("process_grade_weight_exit", self.process_grade_weight_exit),
        ):
            if not (0.0 < fval < 1.0):
                raise ValueError(f"{fname} must be in (0, 1); got {fval}")
        weight_sum = (
            self.process_grade_weight_entry
            + self.process_grade_weight_management
            + self.process_grade_weight_exit
        )
        if abs(weight_sum - 1.0) >= 1e-9:
            raise ValueError(
                "process_grade_weight_{entry,management,exit} must sum to 1.0 "
                f"(±1e-9); got {weight_sum} from "
                f"({self.process_grade_weight_entry}, "
                f"{self.process_grade_weight_management}, "
                f"{self.process_grade_weight_exit})"
            )

        # Drawdown sign convention (Phase 10 §2 + spec §3.1 R1 Major #7).
        if (
            self.drawdown_pause_threshold_R is not None
            and self.drawdown_pause_threshold_R >= 0
        ):
            raise ValueError(
                "drawdown_pause_threshold_R must be < 0 or None (Phase 10 sign "
                f"convention); got {self.drawdown_pause_threshold_R}"
            )
        if (
            self.drawdown_recovery_threshold_R is not None
            and self.drawdown_recovery_threshold_R >= 0
        ):
            raise ValueError(
                "drawdown_recovery_threshold_R must be < 0 or None (Phase 10 sign "
                f"convention); got {self.drawdown_recovery_threshold_R}"
            )
        if self.drawdown_pause_action is not None and (
            self.drawdown_pause_action not in self._DRAWDOWN_ACTIONS
        ):
            raise ValueError(
                f"drawdown_pause_action must be in {self._DRAWDOWN_ACTIONS} or "
                f"None; got {self.drawdown_pause_action!r}"
            )
        if self.drawdown_size_reduction_pct is not None and not (
            0.0 < self.drawdown_size_reduction_pct <= 1.0
        ):
            raise ValueError(
                "drawdown_size_reduction_pct must be in (0, 1] or None; got "
                f"{self.drawdown_size_reduction_pct}"
            )

        # Cross-field: when drawdown_circuit_breaker_enabled, all conditional
        # fields must be set (spec §3.1 enforce-when-enabled validator path).
        if self.drawdown_circuit_breaker_enabled == 1:
            missing = []
            if self.drawdown_pause_threshold_R is None:
                missing.append("drawdown_pause_threshold_R")
            if self.drawdown_pause_action is None:
                missing.append("drawdown_pause_action")
            if self.drawdown_recovery_threshold_R is None:
                missing.append("drawdown_recovery_threshold_R")
            if missing:
                raise ValueError(
                    "drawdown_circuit_breaker_enabled=1 requires non-null "
                    f"fields: {missing}"
                )
            if (
                self.drawdown_pause_action == "reduce_size"
                and self.drawdown_size_reduction_pct is None
            ):
                raise ValueError(
                    "drawdown_size_reduction_pct is required when "
                    "drawdown_pause_action='reduce_size'"
                )

    def field_copy_excluding_pk_and_timeline(self) -> dict:
        """Return a dict of all non-PK / non-timeline fields for a copy-with-overrides
        successor INSERT during supersession.

        Excludes: ``policy_id`` (auto-assigned by INSERT), ``effective_from``
        (set by service to ``now_ms``), ``effective_to`` (NULL on successor),
        ``is_active`` (1 on successor), ``superseded_by_policy_id`` (NULL on
        successor; set in step 5 of the 6-step supersession sequence per
        spec §4.1), ``created_at`` (set by service to ``now_ms``).

        Used by ``swing/trades/risk_policy.py:supersede_active_policy`` to
        copy predecessor field values then apply the operator's
        ``field_updates`` overlay.
        """
        excluded = {
            "policy_id",
            "effective_from",
            "effective_to",
            "is_active",
            "superseded_by_policy_id",
            "created_at",
        }
        return {
            f: getattr(self, f)
            for f in (
                # All 28 non-PK / non-timeline fields preserved on copy.
                "policy_notes",
                "max_account_risk_per_trade_pct",
                "max_concurrent_positions",
                "max_portfolio_heat_pct",
                "max_sector_concentration_positions",
                "consecutive_losses_pause_threshold",
                "consecutive_losses_pause_action",
                "consecutive_losses_streak_reset",
                "drawdown_circuit_breaker_enabled",
                "drawdown_pause_threshold_R",
                "drawdown_pause_action",
                "drawdown_size_reduction_pct",
                "drawdown_recovery_threshold_R",
                "capital_floor_constant_dollars",
                "scratch_epsilon_R",
                "review_lag_threshold_days",
                "low_sample_size_threshold_class_a_n",
                "low_sample_size_threshold_class_b_n",
                "low_sample_size_threshold_class_c_n",
                "low_sample_size_threshold_class_d_n",
                "global_confidence_floor_n",
                "bootstrap_resample_count",
                "process_grade_weight_entry",
                "process_grade_weight_management",
                "process_grade_weight_exit",
                "mfe_mae_default_precision_level",
                "trail_MA_period_days",
                "trail_MA_post_2R_period_days",
            )
            if f not in excluded  # safety: keep the excluded list authoritative
        }


# ============================================================================
# Phase 9 Sub-bundle B — reconciliation_runs + reconciliation_discrepancies
# ============================================================================
#
# Spec §3.2 / §3.3 / §3.3.1 / §3.3.2 / §3.3.3 + plan §B file map (T-B.1).
# Migration 0017 landed both tables (19 cols + 19 cols per LIST; plan-text
# "17 + 18" subtotals are stale brainstorm miscounts — Codex R1 Major #2
# precedent from Sub-bundle A's risk_policy 28-vs-34 reconciliation).
#
# Both dataclasses are frozen and carry ``__post_init__`` validators that
# defend beyond schema-level CHECKs (NaN/inf rejection on REAL fields, enum
# validation on TEXT fields, cross-field invariants like
# ``finished_ts >= started_ts`` and resolution-vs-resolved_at consistency).
# This is defense-in-depth on top of migration 0017's SQL CHECK constraints.


_RECONCILIATION_SOURCES = ("tos_csv", "schwab_api", "manual", "system_audit")
_RECONCILIATION_STATES = ("running", "completed", "failed")

_DISCREPANCY_TYPES = (
    "close_price_mismatch",
    "stop_mismatch",
    "position_qty_mismatch",
    "cash_movement_mismatch",
    "sector_tamper",
    "snapshot_mismatch",
    "unmatched_open_fill",
    "unmatched_close_fill",
    "entry_price_mismatch",
    "equity_delta",
)
_RESOLUTION_VALUES = (
    "journal_corrected",
    "source_treated_canonical",
    "manual_override",
    "unresolved",
    "acknowledged_immaterial",
)


@dataclass(frozen=True)
class ReconciliationRun:
    """One reconciliation pass — TOS CSV or future Schwab API or ad-hoc audit.

    Spec §3.2 (19 fields per migration 0017 LIST; plan-text "17 cols" subtotal
    is a stale brainstorm miscount). Lifecycle ``running`` → ``completed`` |
    ``failed`` (state column). Failure path PRESERVES the row + UPDATEs
    ``state='failed'`` per spec §3.3.3 + plan §A.2.1 (Codex R1 Major #1 in
    writing-plans).
    """

    run_id: int | None  # None pre-INSERT; set by lastrowid after insert_run
    source: str
    source_artifact_path: str | None
    source_artifact_sha256: str | None
    period_start: str | None
    period_end: str | None
    started_ts: str
    finished_ts: str | None
    state: str
    account_equity_journal_dollars: float | None
    account_equity_source_dollars: float | None
    equity_delta_dollars: float | None
    trades_reconciled_count: int | None
    fills_reconciled_count: int | None
    discrepancies_count: int | None
    unresolved_discrepancies_count: int | None
    summary_json: str | None
    error_message: str | None
    notes: str | None
    # Codex R1 Major #5 — schwab_api_call_id ALTER added by migration 0018
    # (FK ON DELETE SET NULL → schwab_api_calls.call_id). Bundle B+
    # `run_tos_reconciliation` writes via the new Schwab transactions
    # endpoint will populate this; tos_csv runs leave NULL. Field ordered
    # LAST (Phase 9 §H.4 positional-instantiation preservation precedent).
    schwab_api_call_id: int | None = None

    def __post_init__(self) -> None:
        import math

        if self.source not in _RECONCILIATION_SOURCES:
            raise ValueError(
                f"source must be one of {_RECONCILIATION_SOURCES}; "
                f"got {self.source!r}"
            )
        if self.state not in _RECONCILIATION_STATES:
            raise ValueError(
                f"state must be one of {_RECONCILIATION_STATES}; "
                f"got {self.state!r}"
            )

        # NaN/inf rejection on REAL fields (Bundle 2/3 pattern; spec
        # §3.2 numeric defense-in-depth on top of SQL).
        for fname, fval in (
            ("account_equity_journal_dollars", self.account_equity_journal_dollars),
            ("account_equity_source_dollars", self.account_equity_source_dollars),
            ("equity_delta_dollars", self.equity_delta_dollars),
        ):
            if fval is not None and (math.isnan(fval) or math.isinf(fval)):
                raise ValueError(f"{fname} must be finite; got {fval}")

        # Counts must be non-negative when present.
        for fname, fval in (
            ("trades_reconciled_count", self.trades_reconciled_count),
            ("fills_reconciled_count", self.fills_reconciled_count),
            ("discrepancies_count", self.discrepancies_count),
            ("unresolved_discrepancies_count", self.unresolved_discrepancies_count),
        ):
            if fval is not None and fval < 0:
                raise ValueError(f"{fname} must be >= 0 or None; got {fval}")

        # Cross-field: when both timestamps present, finished_ts >= started_ts
        # (TEXT lexicographic ordering preserves chronology under naive-UTC
        # millisecond-precision per Phase 9 spec §9.3 + §3.1.3 R3 Major #1).
        if (
            self.finished_ts is not None
            and self.finished_ts < self.started_ts
        ):
            raise ValueError(
                f"finished_ts ({self.finished_ts!r}) must be >= "
                f"started_ts ({self.started_ts!r})"
            )

        # Cross-field: state == 'running' implies finished_ts IS NULL.
        if self.state == "running" and self.finished_ts is not None:
            raise ValueError(
                "state='running' requires finished_ts is NULL; got "
                f"finished_ts={self.finished_ts!r}"
            )
        # Cross-field: state in ('completed','failed') implies finished_ts NOT NULL.
        if (
            self.state in ("completed", "failed")
            and self.finished_ts is None
        ):
            raise ValueError(
                f"state={self.state!r} requires finished_ts set; got NULL"
            )
        # Cross-field: state='failed' should have error_message (defensible UX,
        # not strictly required by spec §3.2 which marks error_message
        # nullable; we enforce at the dataclass for run-row construction
        # symmetry. The service layer always populates error_message on the
        # failure-UPDATE path per plan §A.2 step 9).
        if self.state == "failed" and not self.error_message:
            raise ValueError(
                "state='failed' requires non-empty error_message"
            )

        # Codex R1 Major #5 — schwab_api_call_id validator (None or
        # positive int). FK is enforced at SQL layer; this catches
        # construction-time slip (zero / negative / wrong type).
        if self.schwab_api_call_id is not None and (
            isinstance(self.schwab_api_call_id, bool)
            or not isinstance(self.schwab_api_call_id, int)
            or self.schwab_api_call_id <= 0
        ):
            raise ValueError(
                "schwab_api_call_id must be None or positive int, "
                f"got {self.schwab_api_call_id!r}"
            )


@dataclass(frozen=True)
class ReconciliationDiscrepancy:
    """One reconciliation discrepancy — emitted by reconcile_tos via the seam.

    Spec §3.3 (19 fields per migration 0017 LIST; plan-text "18 cols" subtotal
    is a stale brainstorm miscount). Emitted inside the same transaction as
    the parent ``reconciliation_runs`` row per spec §3.3.3 single-transaction
    contract.

    Resolution lifecycle: starts at ``'unresolved'`` with resolved_at /
    resolved_by NULL; operator dispositions move resolution off
    ``'unresolved'`` and SET resolved_at + resolved_by. ``resolution_reason``
    is required at the app-layer when resolution is one of
    {journal_corrected, source_treated_canonical, manual_override} per
    spec §3.3.
    """

    discrepancy_id: int | None  # None pre-INSERT
    run_id: int
    discrepancy_type: str
    trade_id: int | None
    fill_id: int | None
    cash_movement_id: int | None
    linked_daily_management_record_id: int | None
    ticker: str | None
    field_name: str
    expected_value_json: str | None
    actual_value_json: str | None
    delta_text: str | None
    material_to_review: int
    resolution: str
    resolution_reason: str | None
    resolved_at: str | None
    resolved_by: str | None
    mistake_tag_assigned: str | None
    created_at: str

    def __post_init__(self) -> None:
        import json

        if self.discrepancy_type not in _DISCREPANCY_TYPES:
            raise ValueError(
                f"discrepancy_type must be one of {_DISCREPANCY_TYPES}; "
                f"got {self.discrepancy_type!r}"
            )
        if self.resolution not in _RESOLUTION_VALUES:
            raise ValueError(
                f"resolution must be one of {_RESOLUTION_VALUES}; "
                f"got {self.resolution!r}"
            )
        if self.material_to_review not in (0, 1):
            raise ValueError(
                f"material_to_review must be 0 or 1; got {self.material_to_review}"
            )
        if not self.field_name:
            raise ValueError("field_name must be non-empty")

        # JSON well-formedness on the two payload fields. Per-type SHAPE
        # validation is enforced at the emitter call site (writing-plans
        # T-B.6 codifies the MATERIAL_BY_TYPE + shape contracts); the
        # dataclass enforces "must parse as STRICT JSON" so a stored row
        # is never structurally malformed AND no non-standard JSON
        # constants (NaN / Infinity / -Infinity) slip through. Python's
        # default ``json.loads`` accepts these despite RFC 7159 banning
        # them; the parse_constant callback rejects them explicitly
        # (Codex R1 M#3 fix).
        def _reject_non_standard_constant(token: str) -> None:
            raise ValueError(
                f"non-standard JSON constant {token!r} rejected"
            )
        for fname, fval in (
            ("expected_value_json", self.expected_value_json),
            ("actual_value_json", self.actual_value_json),
        ):
            if fval is not None:
                try:
                    json.loads(
                        fval, parse_constant=_reject_non_standard_constant,
                    )
                except (ValueError, TypeError) as e:
                    raise ValueError(
                        f"{fname} must be valid JSON or None; got {fval!r} "
                        f"({e})"
                    ) from None

        # Resolution-lifecycle invariants.
        if self.resolution == "unresolved":
            # When unresolved, resolved_at + resolved_by typically NULL.
            # We don't strictly enforce NULL (operator could correct
            # mid-workflow) but we DO reject non-null resolved_at without
            # resolved_by or vice versa (asymmetry is a sign of bug).
            if (self.resolved_at is None) != (self.resolved_by is None):
                raise ValueError(
                    "resolved_at and resolved_by must both be NULL or both "
                    f"set; got resolved_at={self.resolved_at!r}, "
                    f"resolved_by={self.resolved_by!r}"
                )
        else:
            # Resolved-off-unresolved: BOTH resolved_at + resolved_by must
            # be populated.
            if self.resolved_at is None:
                raise ValueError(
                    f"resolution={self.resolution!r} requires resolved_at set"
                )
            if self.resolved_by is None:
                raise ValueError(
                    f"resolution={self.resolution!r} requires resolved_by set"
                )
            # resolution_reason required for these three (spec §3.3
            # nullability rule; acknowledged_immaterial is the explicit
            # opt-out where reason is allowed to be NULL but the operator's
            # acknowledgment IS the reason).
            if (
                self.resolution
                in ("journal_corrected", "source_treated_canonical", "manual_override")
                and not self.resolution_reason
            ):
                raise ValueError(
                    f"resolution={self.resolution!r} requires non-empty "
                    "resolution_reason"
                )


# ===========================================================================
# Phase 9 Sub-bundle C — hypothesis_status_history + account_equity_snapshots.
# Per plan §B file map (T-C.2 + T-C.3) + spec §3.4 / §3.5.
#
# Both dataclasses are frozen and carry ``__post_init__`` validators that
# defend beyond schema-level CHECKs (per plan §I item #7 + Bundle 2/3 +
# Bundle A/B precedent):
#
#   - enum validation on TEXT fields
#   - NaN/inf rejection on REAL fields
#   - cross-field invariants (effective_to >= effective_from when both set)
#
# Defense-in-depth on top of migration 0017's SQL CHECK constraints.
# ===========================================================================


_AES_SOURCES = ("manual", "tos_csv", "schwab_api")

# Mirror of `hypothesis_registry.status` enum + migration 0017 CHECK.
_HYPOTHESIS_STATUSES = (
    "active",
    "paused",
    "closed-escaped",
    "closed-target-met",
)


@dataclass(frozen=True)
class AccountEquitySnapshot:
    """One operator-recorded account net-liquidation snapshot.

    Spec §3.5 (8 columns). UPSERT semantics keyed on ``(snapshot_date,
    source)`` via SELECT-then-UPDATE-or-INSERT in the repo (NOT
    ``INSERT OR REPLACE`` per CLAUDE.md SQLite REPLACE gotcha — PK must be
    preserved across re-record so any future FK referrers stay intact).
    """

    snapshot_id: int | None  # None pre-INSERT
    snapshot_date: str  # ISO date YYYY-MM-DD
    equity_dollars: float
    source: str
    source_artifact_path: str | None
    recorded_at: str  # ISO datetime, naive-UTC, ms-precision
    recorded_by: str
    notes: str | None

    def __post_init__(self) -> None:
        import math

        if self.source not in _AES_SOURCES:
            raise ValueError(
                f"source must be one of {_AES_SOURCES}; got {self.source!r}"
            )
        if math.isnan(self.equity_dollars) or math.isinf(self.equity_dollars):
            raise ValueError(
                f"equity_dollars must be finite; got {self.equity_dollars}"
            )
        if self.equity_dollars <= 0:
            raise ValueError(
                f"equity_dollars must be > 0 (matches SQL CHECK); "
                f"got {self.equity_dollars}"
            )
        if not self.recorded_by or not self.recorded_by.strip():
            raise ValueError("recorded_by must be a non-empty identifier")
        # snapshot_date format: YYYY-MM-DD (loose check; the SQL column is
        # TEXT NOT NULL with no format CHECK, so the dataclass enforces the
        # operator-meaningful shape).
        if (
            len(self.snapshot_date) != 10
            or self.snapshot_date[4] != "-"
            or self.snapshot_date[7] != "-"
        ):
            raise ValueError(
                f"snapshot_date must be YYYY-MM-DD; got {self.snapshot_date!r}"
            )


@dataclass(frozen=True)
class HypothesisStatusHistory:
    """One row of the append-only hypothesis_status_history audit trail.

    Spec §3.4 (7 columns). Append-only via service helper
    ``swing/trades/hypothesis.py:update_hypothesis_status_with_audit`` which
    closes the prior open-interval row (``effective_to = now_ms``) then
    INSERTs the new row in a single transaction.

    Invariants:

      - ``effective_to >= effective_from`` when both non-NULL (chronology).
      - Open intervals have ``effective_to IS NULL`` (partial-unique index
        enforces ONE such row per hypothesis at SQL level; the dataclass
        does NOT re-derive that — it's row-grain validation only).
    """

    history_id: int | None  # None pre-INSERT
    hypothesis_id: int
    status: str
    effective_from: str  # ISO datetime, ms-precision
    effective_to: str | None  # ISO datetime, ms-precision; NULL = open
    change_reason: str | None
    recorded_at: str  # ISO datetime, ms-precision

    def __post_init__(self) -> None:
        if self.status not in _HYPOTHESIS_STATUSES:
            raise ValueError(
                f"status must be one of {_HYPOTHESIS_STATUSES}; "
                f"got {self.status!r}"
            )
        if (
            self.effective_to is not None
            and self.effective_to < self.effective_from
        ):
            raise ValueError(
                f"effective_to ({self.effective_to!r}) must be >= "
                f"effective_from ({self.effective_from!r}) "
                "(TEXT lexicographic ordering preserves chronology under "
                "naive-UTC millisecond-precision per spec §9.3)"
            )


# ============================================================================
# Phase 11 — Schwab API integration audit row (migration 0018).
# ============================================================================


_SCHWAB_VALID_ENDPOINTS = frozenset({
    "oauth.code_exchange", "oauth.refresh", "oauth.revoke",
    "accounts.linked", "accounts.details",
    "accounts.orders.list", "accounts.transactions.list",
    "marketdata.quotes", "marketdata.pricehistory",
})

_SCHWAB_VALID_STATUSES = frozenset({
    "in_flight", "success", "error",
    "auth_failed", "rate_limited", "concurrent_refresh",
})

_SCHWAB_SIGNATURE_HASH_RE = re.compile(r"^[0-9a-f]{64}$")


@dataclass(frozen=True)
class SchwabApiCall:
    """Audit row for one Schwab API call (migration 0018, plan §H.7).

    Captures the per-call observability surface required by spec §3 and the
    operator's dashboard / CLI surfaces. Validators are defense-in-depth on
    top of the SQL CHECK constraints in 0018 — the dataclass is the binding
    artifact for service-layer construction at T-A.9.

    ``signature_hash`` is None for in-flight / error rows; populated on
    completed-payload rows as a 64-char lowercase hex SHA-256 digest of the
    relevant response body slice (drift-detection consumer per Finviz
    precedent).

    ``http_status`` is None for never-reached cases (auth_failed before
    request, concurrent_refresh aborted, etc.); 100-599 inclusive when set
    per RFC 9110 status-code range.

    ``rate_limit_remaining`` is best-effort (None when Schwab does not
    include the header or response is unparseable); no constraint per plan
    §H.7.

    Caller-controlled tx discipline lives in the repo layer
    (``swing/data/repos/schwab_api_calls.py``); the service layer at T-A.9
    will own BEGIN IMMEDIATE / COMMIT / ROLLBACK.
    """

    call_id: int | None  # None pre-INSERT.
    ts: str  # ISO 8601, naive datetime per Finviz / Phase 9 convention.
    endpoint: str
    http_status: int | None
    response_time_ms: int | None
    rate_limit_remaining: int | None
    signature_hash: str | None
    status: str
    error_message: str | None
    linked_snapshot_id: int | None
    linked_reconciliation_run_id: int | None
    pipeline_run_id: int | None
    surface: str
    environment: str

    def __post_init__(self) -> None:
        if self.endpoint not in _SCHWAB_VALID_ENDPOINTS:
            raise ValueError(
                f"endpoint must be in {sorted(_SCHWAB_VALID_ENDPOINTS)}, "
                f"got {self.endpoint!r}"
            )
        if self.status not in _SCHWAB_VALID_STATUSES:
            raise ValueError(
                f"status must be in {sorted(_SCHWAB_VALID_STATUSES)}, "
                f"got {self.status!r}"
            )
        if self.surface not in ("pipeline", "cli"):
            raise ValueError(
                f"surface must be 'pipeline' or 'cli', got {self.surface!r}"
            )
        if self.environment not in ("sandbox", "production"):
            raise ValueError(
                "environment must be 'sandbox' or 'production', "
                f"got {self.environment!r}"
            )
        if self.http_status is not None and not (100 <= self.http_status < 600):
            raise ValueError(
                "http_status must be None or 100-599 (RFC 9110), "
                f"got {self.http_status}"
            )
        if self.response_time_ms is not None and self.response_time_ms < 0:
            raise ValueError(
                "response_time_ms must be None or >= 0, "
                f"got {self.response_time_ms}"
            )
        if (
            self.signature_hash is not None
            and not _SCHWAB_SIGNATURE_HASH_RE.fullmatch(self.signature_hash)
        ):
            raise ValueError(
                "signature_hash must be None or 64-char lowercase hex, "
                f"got {self.signature_hash!r}"
            )
        # Codex R1 Major #4 — close validator-coverage gap for the 7
        # remaining audit columns. Plan §B.1 + §H.7 specified validators
        # across all 14 audit columns; the prior implementation only
        # covered the 7 enum/range/regex ones. The remaining 7 columns
        # below enforce per-field defense-in-depth on top of the SQL
        # constraints in migration 0018.

        # call_id: None pre-INSERT; positive int post-INSERT.
        if self.call_id is not None and (
            isinstance(self.call_id, bool)
            or not isinstance(self.call_id, int)
            or self.call_id <= 0
        ):
            raise ValueError(
                f"call_id must be None or positive int, got {self.call_id!r}"
            )

        # ts: non-empty string parseable by datetime.fromisoformat
        # (permissive ISO 8601 acceptance; covers `YYYY-MM-DDTHH:MM:SS`
        # naked + microsecond-precision + ±HH:MM offsets per Phase 9
        # spec §9.3 timestamp convention).
        if not isinstance(self.ts, str) or not self.ts:
            raise ValueError(
                f"ts must be non-empty ISO 8601 string, got {self.ts!r}"
            )
        try:
            from datetime import datetime as _dt
            _dt.fromisoformat(self.ts)
        except (TypeError, ValueError) as exc:
            raise ValueError(
                f"ts must be ISO 8601 parseable, got {self.ts!r}"
            ) from exc

        # rate_limit_remaining: None or non-negative int. No upper bound
        # per plan §H.7 (best-effort header echo).
        if (
            self.rate_limit_remaining is not None
            and self.rate_limit_remaining < 0
        ):
            raise ValueError(
                "rate_limit_remaining must be None or >= 0, "
                f"got {self.rate_limit_remaining}"
            )

        # error_message: None or string. No length cap at this layer
        # (rendering layer truncates per redaction discipline).
        if (
            self.error_message is not None
            and not isinstance(self.error_message, str)
        ):
            raise ValueError(
                f"error_message must be None or str, "
                f"got {type(self.error_message).__name__}"
            )

        # linked_snapshot_id / linked_reconciliation_run_id /
        # pipeline_run_id: each None or positive int. FK satisfaction
        # is enforced at the SQL layer; per-field validator catches
        # construction-time slip (zero / negative / wrong type).
        for fname, fval in (
            ("linked_snapshot_id", self.linked_snapshot_id),
            ("linked_reconciliation_run_id", self.linked_reconciliation_run_id),
            ("pipeline_run_id", self.pipeline_run_id),
        ):
            if fval is not None and (
                isinstance(fval, bool) or not isinstance(fval, int) or fval <= 0
            ):
                raise ValueError(
                    f"{fname} must be None or positive int, got {fval!r}"
                )
