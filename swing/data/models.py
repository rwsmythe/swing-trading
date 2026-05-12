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
    drawdown_pause_threshold_R: float | None
    drawdown_pause_action: str | None
    drawdown_size_reduction_pct: float | None
    drawdown_recovery_threshold_R: float | None

    # Capital + sizing (1):
    capital_floor_constant_dollars: float

    # Statistics-methodology (8):
    scratch_epsilon_R: float
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
    trail_MA_period_days: int
    trail_MA_post_2R_period_days: int | None

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
