"""22-I guard spec -- the ONE declarative source the 0041 tests read.

PURE DATA: this module imports nothing from ``swing`` (and nothing outside the
standard library), because ``scripts/probe_22i_guard_census.py --post-migrate``
loads it BY FILE PATH and must never import ``swing`` (a path that reaches
``ensure_schema`` would auto-migrate the file it opened).

Per guarded table: its F-I1 class (RD's partition, plan section 1), its PK, its
conflict keys, and every column's class (plan section 1.1):

    I  immutable            NEW.c IS OLD.c
    W  write-once           NULL -> value admitted; value -> anything refused
    F  a17 SET-NULL FK      value -> NULL admitted only with the parent GONE
    D  directional          risk_policy.is_active 1 -> 0 only
    M  mutable              the writer's measured UPDATE set (absent from the predicate)
    S  state-frozen         review_log: frozen once OLD.completed_date IS NOT NULL
    DATA                    daily_management_records: the reflow SET list
    STATE                   daily_management_records: is_superseded, superseded_by_record_id

The (a) tables carry a blanket ``no_update``, so every non-F column is I. The
column sets are the spec; ``test_migration_0041_twins.py`` C8 asserts them
against ``PRAGMA table_info`` and against the stored trigger text (the
comparator -- CLAUDE.md #11 as amended: the only mirror that defends the set).
"""
from __future__ import annotations

from dataclasses import dataclass

REACHABLE = "REACHABLE"
DELETABLE = "DELETABLE-NO-PRODUCTION-DELETER"
DEAD = "DEAD-BY-PARENT-GUARD"


@dataclass(frozen=True)
class FCol:
    col: str
    parent: str
    ppk: str
    state: str


@dataclass(frozen=True)
class GuardSpec:
    table: str
    abbr: str
    klass: str  # "a" (the triple) | "c" (no_delete + no_replace + twin) | "c-notwin"
    pk: tuple[str, ...]
    integer_pk: bool
    conflict_keys: tuple[tuple[str, ...], ...] = ()  # plain UNIQUE keys besides the PK
    special_conflict: str | None = None  # partial-UNIQUE clause text (rp, hsh, dmr)
    I: tuple[str, ...] = ()  # noqa: E741
    W: tuple[str, ...] = ()
    F: tuple[FCol, ...] = ()
    D: tuple[str, ...] = ()
    M: tuple[str, ...] = ()
    S: tuple[str, ...] = ()
    DATA: tuple[str, ...] = ()
    STATE: tuple[str, ...] = ()

    @property
    def triggers(self) -> tuple[str, ...]:
        a = self.abbr
        if self.klass == "a":
            return (f"trg_{a}_no_update", f"trg_{a}_no_delete", f"trg_{a}_no_replace")
        if self.klass == "c":
            return (f"trg_{a}_no_delete", f"trg_{a}_no_replace", f"trg_{a}_immutable")
        return (f"trg_{a}_no_delete", f"trg_{a}_no_replace", f"trg_{a}_pk_immutable")

    @property
    def pk_trigger(self) -> str | None:
        """The (c) no-twin tables' PK freeze (Reviewer B B2, CHARC Branch A): a
        BLANKET BEFORE UPDATE whose WHEN compares the rowid's VALUE, so every
        spelling of the key (<pk>, rowid, oid, _rowid_) is refused. The PK is
        therefore NOT in the table's M tuple."""
        return f"trg_{self.abbr}_pk_immutable" if self.klass == "c-notwin" else None

    @property
    def update_trigger(self) -> str | None:
        if self.klass == "a":
            return f"trg_{self.abbr}_no_update"
        if self.klass == "c":
            return f"trg_{self.abbr}_immutable"
        return None

    @property
    def f_cols(self) -> tuple[str, ...]:
        return tuple(f.col for f in self.F)

    def all_columns(self) -> tuple[str, ...]:
        return (self.I + self.W + self.f_cols + self.D + self.M + self.S
                + self.DATA + self.STATE)


def _f(col: str, parent: str, ppk: str, state: str) -> FCol:
    return FCol(col, parent, ppk, state)


_PR = ("pipeline_runs", "id")

SPEC: dict[str, GuardSpec] = {}


def _add(s: GuardSpec) -> None:
    SPEC[s.table] = s


# ---------------------------------------------------------------------------
# (a) THE TRIPLE -- seven tables (RD F-I1 rows 1, 2, 3, 5, 13, 14 + er)
# ---------------------------------------------------------------------------
_add(GuardSpec(
    "pattern_forward_observations", "pfo", "a", ("observation_id",), True,
    conflict_keys=(("detection_id", "observation_date"),),
    I=("observation_id", "detection_id", "observation_date", "ohlc_today_json",
       "status", "status_change_event", "sessions_since_detection", "created_at")))
_add(GuardSpec(
    "pattern_detection_events", "pde", "a", ("detection_id",), True,
    conflict_keys=(("source", "ticker", "detection_date", "pattern_class"),),
    I=("detection_id", "ticker", "detection_date", "data_asof_date",
       "pattern_class", "structural_anchors_json", "composite_score",
       "detector_version", "finviz_screen_state", "source",
       "per_pattern_metadata_json", "created_at"),
    F=(_f("chart_render_id", "chart_renders", "id", REACHABLE),
       _f("pipeline_run_id", *_PR, DELETABLE))))
_add(GuardSpec(
    "candidate_criteria", "cc", "a", ("candidate_id", "criterion_name"), False,
    I=("candidate_id", "criterion_name", "layer", "result", "value", "rule")))
_add(GuardSpec(
    "trade_events", "te", "a", ("id",), True,
    I=("id", "trade_id", "ts", "event_type", "payload_json", "rationale", "notes")))
_add(GuardSpec(
    "finviz_api_calls", "fac", "a", ("call_id",), True,
    I=("call_id", "ts", "screen_query", "status", "row_count", "response_time_ms",
       "rate_limit_remaining", "signature_hash", "error_message")))
_add(GuardSpec(
    "pattern_evaluations", "pev", "a", ("id",), True,
    conflict_keys=(("pipeline_run_id", "ticker", "pattern_class"),),
    I=("id", "pipeline_run_id", "ticker", "pattern_class", "detector_version",
       "geometric_score", "geometric_score_json", "template_match_score",
       "template_match_nearest_exemplar_ids_json", "composite_score",
       "structural_evidence_json", "feature_distribution_log_json",
       "window_start_date", "window_end_date", "created_at")))
_add(GuardSpec(
    "evaluation_runs", "er", "a", ("id",), True,
    I=("id", "run_ts", "data_asof_date", "action_session_date", "finviz_csv_path",
       "tickers_evaluated", "aplus_count", "watch_count", "skip_count",
       "excluded_count", "error_count", "rs_universe_version", "rs_universe_hash")))

# ---------------------------------------------------------------------------
# (c) no_delete + no_replace + a column-scoped immutability twin
# ---------------------------------------------------------------------------
_add(GuardSpec(
    "reconciliation_corrections", "rc", "c", ("correction_id",), True,
    I=("correction_id", "discrepancy_id", "correction_action", "correction_choice",
       "affected_table", "affected_row_id", "field_name",
       "pre_correction_value_json", "source_canonical_value_json",
       "applied_value_json", "operator_truth_value_json", "applied_at",
       "applied_by", "reconciliation_run_id", "correction_reason", "notes"),
    W=("correction_set_id", "superseded_by_correction_id"),
    F=(_f("risk_policy_id_at_correction", "risk_policy", "policy_id", DEAD),
       _f("schwab_api_call_id", "schwab_api_calls", "call_id", DEAD))))
_add(GuardSpec(
    "risk_policy", "rp", "c", ("policy_id",), True,
    special_conflict="(NEW.is_active = 1 AND is_active = 1)",
    D=("is_active",),
    W=("effective_to", "superseded_by_policy_id"),
    I=("policy_id", "effective_from", "created_at", "policy_notes",
       "max_account_risk_per_trade_pct", "max_concurrent_positions",
       "max_portfolio_heat_pct", "max_sector_concentration_positions",
       "consecutive_losses_pause_threshold", "consecutive_losses_pause_action",
       "consecutive_losses_streak_reset", "drawdown_circuit_breaker_enabled",
       "drawdown_pause_threshold_R", "drawdown_pause_action",
       "drawdown_size_reduction_pct", "drawdown_recovery_threshold_R",
       "capital_floor_constant_dollars", "scratch_epsilon_R",
       "review_lag_threshold_days", "low_sample_size_threshold_class_a_n",
       "low_sample_size_threshold_class_b_n", "low_sample_size_threshold_class_c_n",
       "low_sample_size_threshold_class_d_n", "global_confidence_floor_n",
       "bootstrap_resample_count", "process_grade_weight_entry",
       "process_grade_weight_management", "process_grade_weight_exit",
       "mfe_mae_default_precision_level", "trail_MA_period_days",
       "trail_MA_post_2R_period_days")))
_add(GuardSpec(
    "hypothesis_registry", "hr", "c", ("id",), True,
    conflict_keys=(("name",),),
    M=("status", "status_changed_at", "status_change_reason"),
    I=("id", "name", "statement", "target_sample_size", "decision_criteria",
       "consecutive_loss_tripwire", "absolute_loss_tripwire_pct", "created_at",
       "notes", "preregistered_decision_criteria")))
_add(GuardSpec(
    "hypothesis_status_history", "hsh", "c", ("history_id",), True,
    special_conflict=("(NEW.effective_to IS NULL AND effective_to IS NULL "
                      "AND hypothesis_id = NEW.hypothesis_id)"),
    W=("effective_to",),
    I=("history_id", "hypothesis_id", "status", "effective_from", "change_reason",
       "recorded_at")))
_add(GuardSpec(
    "reconciliation_runs", "rr", "c", ("run_id",), True,
    M=("state", "finished_ts", "account_equity_journal_dollars",
       "account_equity_source_dollars", "equity_delta_dollars",
       "trades_reconciled_count", "fills_reconciled_count", "discrepancies_count",
       "unresolved_discrepancies_count", "summary_json", "notes", "error_message"),
    F=(_f("schwab_api_call_id", "schwab_api_calls", "call_id", DEAD),),
    I=("run_id", "source", "source_artifact_path", "source_artifact_sha256",
       "period_start", "period_end", "started_ts")))
_add(GuardSpec(
    "reconciliation_discrepancies", "rd", "c", ("discrepancy_id",), True,
    M=("resolution", "resolution_reason", "resolved_at", "resolved_by",
       "ambiguity_kind", "mistake_tag_assigned", "material_to_review"),
    F=(_f("trade_id", "trades", "id", DELETABLE),
       _f("fill_id", "fills", "fill_id", REACHABLE),
       _f("cash_movement_id", "cash_movements", "id", DELETABLE),
       _f("linked_daily_management_record_id", "daily_management_records",
          "management_record_id", DEAD)),
    I=("discrepancy_id", "run_id", "discrepancy_type", "ticker", "field_name",
       "expected_value_json", "actual_value_json", "delta_text", "created_at")))
_add(GuardSpec(
    "schwab_api_calls", "sac", "c", ("call_id",), True,
    M=("http_status", "response_time_ms", "rate_limit_remaining", "signature_hash",
       "status", "error_message", "linked_snapshot_id",
       "linked_reconciliation_run_id", "linked_correction_id"),
    F=(_f("pipeline_run_id", *_PR, DELETABLE),),
    I=("call_id", "ts", "endpoint", "surface", "environment")))
_add(GuardSpec(
    "yfinance_calls", "yfc", "c", ("call_id",), True,
    M=("response_time_ms", "status", "rows_returned", "error_message"),
    F=(_f("pipeline_run_id", *_PR, DELETABLE),),
    I=("call_id", "ts", "call_type", "ticker", "ticker_count", "surface")))
_add(GuardSpec(
    "account_equity_snapshots", "aes", "c", ("snapshot_id",), True,
    conflict_keys=(("snapshot_date", "source", "basis"),),
    M=("equity_dollars", "source_artifact_path", "recorded_at", "recorded_by",
       "notes", "schwab_account_hash"),
    I=("snapshot_id", "snapshot_date", "source", "basis")))
_add(GuardSpec(
    "daily_management_records", "dmr", "c", ("management_record_id",), True,
    special_conflict=(
        "(record_type = 'daily_snapshot' AND NEW.record_type = 'daily_snapshot' "
        "AND trade_id = NEW.trade_id AND data_asof_session = NEW.data_asof_session "
        "AND ((is_superseded = 0 AND NEW.is_superseded = 0) "
        "OR mfe_mae_precision_level = NEW.mfe_mae_precision_level))"),
    DATA=("current_price", "current_stop", "current_size", "current_avg_cost",
          "open_R_effective", "open_MFE_R_to_date", "open_MAE_R_to_date",
          "intraday_high", "intraday_low", "position_capital_utilization_pct",
          "position_capital_denominator_dollars",
          "position_portfolio_heat_contribution_dollars", "maturity_stage",
          "trail_MA_candidate_price", "trail_MA_period_days",
          "trail_MA_eligibility_flag", "pipeline_run_id", "created_at"),
    I=("management_record_id", "trade_id", "record_type", "review_date",
       "data_asof_session", "mfe_mae_precision_level", "thesis_status",
       "prior_stop", "new_stop", "stop_changed", "stop_change_reason",
       "volume_behavior", "relative_strength_status", "market_regime_change",
       "sector_condition_change", "news_or_event_update", "action_taken",
       "action_reason", "emotional_state", "rule_violation_suspected",
       "management_notes"),
    F=(_f("linked_trade_event_id", "trade_events", "id", DEAD),),
    STATE=("is_superseded", "superseded_by_record_id")))
# dmr's FROZEN_FK clause nulls pipeline_run_id (a DATA column) on a superseded
# row under the a17 shape; its parent is pipeline_runs (DELETABLE).
DMR_FROZEN_FK = _f("pipeline_run_id", *_PR, DELETABLE)

_add(GuardSpec(
    "review_log", "rl", "c", ("review_id",), True,
    conflict_keys=(("review_type", "period_start", "period_end"),),
    I=("review_id", "review_type", "period_start", "period_end", "scheduled_date",
       "skipped", "created_at"),
    S=("completed_date", "duration_minutes", "n_trades_reviewed", "primary_lesson",
       "next_period_focus", "total_mistake_cost_R", "total_lucky_violation_R",
       "net_R_effective", "expectancy_R_effective", "win_rate", "avg_win_R",
       "avg_loss_R", "profit_factor", "max_drawdown_R",
       "auto_populated_field_keys_json"),
    F=(_f("risk_policy_id_at_review_completion", "risk_policy", "policy_id", DEAD),),
    M=("superseded_by_correction_id",)))

# ---------------------------------------------------------------------------
# (c) no_delete + no_replace, NO twin (ruled: labels / removed_date edited in place)
# + trg_<abbr>_pk_immutable (Reviewer B B2, CHARC Branch A): every NON-PK column
# is mutable at the schema (plan AL-11); the PK is frozen, so it is not in M.
# ---------------------------------------------------------------------------
_add(GuardSpec(
    "pattern_exemplars", "pex", "c-notwin", ("id",), True,
    M=("ticker", "timeframe", "start_date", "end_date", "proposed_pattern_class",
       "final_decision", "final_pattern_class", "label_source", "ai_labeler_version",
       "gold_validated_at", "codex_reviewed", "codex_agreement",
       "geometric_score_json", "labeler_evidence_json", "structural_evidence_json",
       "quality_grade", "notes", "parent_exemplar_id", "created_at", "created_by")))
_add(GuardSpec(
    "watchlist_archive", "wla", "c-notwin", ("id",), True,
    M=("ticker", "added_date", "removed_date", "reason", "qualification_count",
       "last_data_asof_date", "notes")))

# ---------------------------------------------------------------------------
# F-I5: the latch_view_events first-view twin (an UPDATE OF trigger, no WHEN)
# ---------------------------------------------------------------------------
LVE_FIRST_VIEW_COLUMNS: tuple[str, ...] = (
    "candidate_id", "evaluation_run_id", "detection_date", "surface",
    "view_session_date", "latch_state_at_first_view", "actionable_at_first_view")
LVE_WRITER_COLUMNS: tuple[str, ...] = (
    "last_viewed_ts", "latch_state_at_last_view", "actionable_at_last_view",
    "view_count", "actionable_ever_viewed")
# view_event_id is frozen by trg_lve_pk_immutable (Reviewer B B2, CHARC Branch A);
# pipeline_run_id by the identity trigger; first_viewed_ts / ticker by the window twin.
LVE_OTHER_COLUMNS: tuple[str, ...] = (
    "view_event_id", "pipeline_run_id", "first_viewed_ts", "ticker")

# The three PK freezes 0041 adds for B2 (one per table whose update guards were
# all column-scoped): a blanket BEFORE UPDATE, WHEN NOT COALESCE(NEW.pk IS OLD.pk, 0).
PK_IMMUTABLE_22I: dict[str, tuple[str, str]] = {
    "pattern_exemplars": ("trg_pex_pk_immutable", "id"),
    "watchlist_archive": ("trg_wla_pk_immutable", "id"),
    "latch_view_events": ("trg_lve_pk_immutable", "view_event_id"),
}

REBUILT_22I: tuple[str, ...] = ("trg_provenance_corrections_append_only_update",)

A_TABLES = tuple(t for t, s in SPEC.items() if s.klass == "a")
C_TABLES = tuple(t for t, s in SPEC.items() if s.klass == "c")
C_NOTWIN_TABLES = tuple(t for t, s in SPEC.items() if s.klass == "c-notwin")

# The 62 names 0041 ADDS (plan section 1.4), spelled out rather than derived, so
# the spec's trigger naming and this list check each other.
GUARDS_22I_ADDED: tuple[str, ...] = (
    *(f"trg_{a}_{k}" for a in ("pfo", "pde", "cc", "te", "fac", "pev", "er")
      for k in ("no_update", "no_delete", "no_replace")),
    *(f"trg_{a}_{k}" for a in ("rc", "rp", "hr", "hsh", "rr", "rd", "sac", "yfc",
                                "aes", "dmr", "rl")
      for k in ("no_delete", "no_replace", "immutable")),
    *(f"trg_{a}_{k}" for a in ("pex", "wla") for k in ("no_delete", "no_replace")),
    "trg_lve_first_view_immutable",
    "trg_pex_pk_immutable", "trg_wla_pk_immutable", "trg_lve_pk_immutable",
)
