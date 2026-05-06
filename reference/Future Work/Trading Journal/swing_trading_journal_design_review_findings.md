---
title: "Swing Trading Journal Specification — Design Review Findings"
version: "1.0"
document_type: "design_review_findings"
created_date: "2026-05-01"
review_target: "swing_trading_journal_ai_ingestion.md v1.0"
review_outcome: "Substantial revisions recommended; v1.1 produced as companion deliverable"
intended_use:
  - record_findings_from_design_review
  - capture_implementation_context_clarifications
  - document_decisions_made_for_v1_1
  - serve_as_traceability_artifact_between_v1_0_and_v1_1
---

# Swing Trading Journal Specification — Design Review Findings

## 1. Executive Summary

This document captures the findings from a structured design review of the v1.0
swing trading journal specification. The review was conducted across four
iterative passes: an initial scoping exchange, a primary findings pass on
methodology / consistency / practicality, an implementation-context revision
pass, and a final clarification pass on reconciliation cadence, screening
workflow, and behavioral-rule scope.

The v1.0 specification is well above average for a personal trading journal in
several respects: it explicitly separates decision quality from outcome,
normalizes outcomes in R-multiples throughout, includes a rule-change queue
with sample-size thresholds, and treats the journal as a decision-quality
measurement system rather than a trade ledger. These design choices are
preserved unchanged in v1.1.

The findings below are organized into four series:

- **M-series** — methodology and completeness gaps
- **C-series** — internal consistency and logical issues
- **P-series** — practicality and friction concerns
- **N-series** — gaps revealed by clarified implementation context

A separate section captures concerns raised about specific approaches the
author proposed during the review (monthly reconciliation cadence and the
Finviz CSV-only context capture). A final section enumerates decisions made
where author judgment was required to produce v1.1 without further consultation.

The companion deliverable, `swing_trading_journal_ai_ingestion_v1.1.md`,
incorporates all findings and decisions documented here.

---

## 2. Implementation Context (As Clarified)

The v1.0 specification was deliberately implementation-agnostic. The following
context was clarified during the review and is now baked into v1.1.

```yaml
implementation_context:
  trading_mode: live
  account_count: 1
  instrument_scope: stock_only
  options_in_scope: false
  futures_in_scope: false
  paper_trading_in_scope: false

  trading_platform:
    broker: "thinkorswim (TOS)"
    fill_data_source: "TOS CSV export"
    reconciliation_cadence: weekly

  screening_pipeline:
    primary_screener: "Finviz"
    screener_export_format: csv
    screener_metadata_capture: "manual annotation in daily screener log"
    secondary_data_source: "yfinance for OHLCV and analytics"

  position_constraints:
    max_concurrent_positions: 6
    intended_holding_period: "days to weeks"
    minimum_holding_period_rule: false
    minimum_holding_period_intent: "holding less than ~2 days repeatedly is treated as a signal of poor selection, not a rule"

  behavioral_circuit_breakers:
    consecutive_losses_pause_threshold: 3
    pause_action: "review required before next trade"
    streak_reset_condition: "review_completed"

  journal_implementation_target:
    runtime: "python_based_swing_trading_tool"
    delivery_method: "claude_code_orchestrated_implementation_briefs"
    detailed_implementation_choice: "deferred to implementation phase"

  ai_consumer:
    primary: "claude_code_orchestrator"
    role: "evaluate spec, plan implementation, generate briefs for sub-agents"
```

These constraints were used to simplify v1.1 (removing options, multi-account,
and paper-trading language) and to define data-flow specifics that v1.0 left
abstract (reconciliation workflow, source/latency annotation, screen-of-origin
flow-through).

---

## 3. Findings

### 3.1 Methodology / Completeness (M-series)

**M1. Position state machine is implicit.**
Trade_Log mixes pre-trade, execution, and post-trade fields in a single row
with informal `Required: conditional` markers. A real trade transitions
through states (`planned → triggered → entered → managing → partial_exited
→ closed`), and each state has a different mandatory field-set and
validation rule. Making the state model explicit lets AI gate logic become
deterministic and prevents partially-filled rows from passing checks.
**Disposition: addressed in v1.1 §6 (Trade Lifecycle State Machine).**

**M2. Pyramiding / scaling-in semantics are underspecified.**
Setup_Playbook has `add_on_rule` and Fills has an `add` action, but
Trade_Log treats `initial_risk_dollars` as a single fixed value. With
Minervini-style progressive add-ons, "initial risk" can mean first-tranche
risk, planned-full-position risk, or current at-risk capital — and
R-multiple denominators behave very differently across these conventions.
**Disposition: addressed in v1.1 §10 with explicit conventions; see §6 of this
findings document for the chosen convention.**

**M3. Risk after partials and breakeven moves is not modeled.**
Once a position is trimmed and stop is moved to breakeven, the trade is
effectively "free" — current at-risk capital is zero or negative. `MAE_R`
and `open_R` are still computed against fixed `initial_risk_dollars`, which
is fine for outcome attribution, but it leaves "current heat on this open
position" unmeasured.
**Disposition: addressed in v1.1 by introducing `current_at_risk_dollars`
and `current_at_risk_R` as live computed fields, distinct from
`initial_risk_dollars`.**

**M4. `market_regime` enum is referenced but never defined.**
§5.2 of v1.0 says it must be defined; §11.1 has a step to define it; the
dashboard segments by it; the pre-trade gate validates against it. Without
a canonical enum, every implementation will diverge and AI evaluation rules
cannot operate uniformly.
**Disposition: addressed in v1.1 §8 (Controlled Vocabularies) with
canonical enum.**

**M5. Catalyst and stop-type taxonomies are free-text where controlled
vocabularies would unlock analytics.**
`catalyst` is required text but a controlled enum is what makes
catalyst-segmented expectancy possible. `initial_stop_rule` is text but
stops have meaningful types whose distribution drives the MAE profile.
**Disposition: addressed in v1.1 §8 — both elevated to enum + optional
free-text annotation.**

**M6. Hindsight integrity has no architectural enforcement.**
v1.0 §13.2 lists "hindsight rewrite" as a failure mode but the only
mitigation is "timestamp pre-trade ticket." Pre-trade fields should be
immutable once the entry fill is recorded.
**Disposition: addressed in v1.1 with a `pre_trade_locked_at` timestamp
that locks pre-trade fields on first fill, plus an audit-log requirement
for any subsequent edits.**

**M7. Counterfactual measurement (`mistake_cost_R`) needs rigor or honest
demotion.**
The formula `realized_R_if_plan_followed - actual_realized_R` requires
knowing what would have happened. For a chased entry the counterfactual is
"you would have passed" (collapses to `-actual_R`); for a moved stop the
counterfactual is reconstructable from chart data; for revenge sizing it is
not measurable at all.
**Disposition: addressed in v1.1 with per-mistake-category counterfactual
procedures and confidence tagging; metric is split into `mistake_cost_R`
(harm only) and `lucky_violation_R` (benefit only) — see C5 below.**

**M8. Sequence and streak effects are not captured.**
v1.0 captures per-trade emotional state but not trade-sequence context —
trades_since_last_loss, loss_streak_length, equity_drawdown_at_entry,
realized_R_last_5_trades. These are more than analytics: the author has a
"pause after 3 consecutive losses" rule that requires streak state to be a
first-class operational input, not derived dashboard output.
**Disposition: addressed in v1.1 §9.9 (Risk_Policy / circuit breakers) and
the pre-trade gate.**

**M9. "Trade" is undefined for re-entries.**
If a setup gets stopped out and re-enters the next day on a new pivot, is
that one trade or two? Affects sample sizes, expectancy, and process
grading.
**Disposition: addressed in v1.1 — re-entries are discrete trades with a
`parent_trade_id` linkage, preserving clean per-entry R-multiple math
while allowing campaign-level grouping.**

**M10. Account-level controls are referenced but not parameterized.**
The pre-trade gate validates `account_risk_within_limit` but the limits
themselves (max concurrent positions, max sector exposure, max portfolio
heat, max single-trade risk) are not fields anywhere.
**Disposition: addressed in v1.1 §9.9 (Risk_Policy entity) with explicit
parameterization including the author's six-position cap.**

**M11. Watchlist context demoted to optional but has predictive value.**
A trade that sat on a stalk list for three weeks before triggering
systematically differs from a same-day surfacing.
**Disposition: addressed in v1.1 — Watchlist promoted to required tab
(§9.5); `time_on_watchlist_days` and `source_screen` propagate from
watchlist entry through to trade record.**

**M12. Missed_Trades demoted to advanced but is not really.**
Passing on trades that subsequently work is one of the highest-yield
behavioral signals. Without it, you cannot distinguish a well-disciplined
trader who screened correctly from a fearful trader who missed the obvious.
**Disposition: addressed in v1.1 — Missed_Trades is a recommended (not
optional) tab, populated as part of the weekly review.**

### 3.2 Internal Consistency / Logical Issues (C-series)

**C1. Pre-Trade Quality Score arithmetic is visually misleading.**
v1.0 §7.1 lists nine components but sums to 10 because "valid setup" is
worth 2. Component scoring (binary vs. partial) is unspecified.
**Disposition: addressed in v1.1 — components are explicitly binary;
"valid setup" worth-2 is annotated in the table.**

**C2. A-grade requires `post_trade_review_completed`, but grading is the
review.**
Circular dependency.
**Disposition: addressed in v1.1 — replaced with "review must occur within
N days of close" requirement (default N=7).**

**C3. `process_grade` (A–F) and `entry_quality_grade` (A–F) overlap
without composition rules.**
If entry was C and management was A, what is overall process grade?
**Disposition: addressed in v1.1 — overall `process_grade` defined as the
*worst* of per-stage grades (entry / management / exit). Worst-component
defended on the principle that one major rule break should not be diluted
by good behavior elsewhere.**

**C4. `capture_ratio = realized_R / MFE_R` has undefined edge cases.**
Undefined when `MFE_R = 0`; semantically meaningless when `realized_R < 0`.
**Disposition: addressed in v1.1 — defined only when trade is closed,
`MFE_R > 0`, and `realized_R > 0`. Otherwise `n/a`. Excluded from
`average_capture_ratio`.**

**C5. `mistake_cost_R` sign convention mathematically rewards lucky
violations.**
The formula `realized_R_if_plan_followed - actual_realized_R` is negative
when the violation paid off, which would aggregate as a "negative cost"
(benefit). The framework correctly flags `lucky_violation` as dangerous,
but the central metric for behavioral leakage is currently mis-shaped for
that case.
**Disposition: addressed in v1.1 — split into two non-negative metrics:
`mistake_cost_R = max(0, realized_R_if_plan_followed - actual_realized_R)`
captures harm only; `lucky_violation_R = max(0, actual_realized_R -
realized_R_if_plan_followed)` captures unearned benefit. They never net
against each other in aggregations.**

**C6. `setup_family` and `by_entry_type` enums do not match.**
v1.0 §5.1: `breakout, pullback, episodic_pivot, gap, reversal, short,
trend_continuation`. v1.0 §9.2 by_entry_type: `breakout, pullback,
reclaim, gap, opening_range`. Different vocabularies for what should be
one taxonomy. Also `short` is a direction, not a family.
**Disposition: addressed in v1.1 §8 — `setup_family` describes the
*pattern type* and `entry_trigger_type` describes *how the entry was
actually executed*. Both are reconciled enums; `short` removed (handled
via `direction` field).**

**C7. `thesis_accuracy`, `thesis_status`, and `setup_validity_after_review`
overlap and are not disambiguated.**
**Disposition: addressed in v1.1 — explicit definitions:
- `thesis_status` is in-the-moment (Daily_Management): is the thesis still
  unfolding as expected?
- `thesis_accuracy` is post-trade outcome judgment: did the thesis prove
  correct?
- `setup_validity_after_review` is edge judgment: was this a valid instance
  of the setup family, or did it not actually qualify on review?**

**C8. `mistake_tags` is `Required: no` on Trade_Log.**
Behavioral measurement is a primary objective; making this optional means
missing data and "no mistake" are indistinguishable.
**Disposition: addressed in v1.1 — required, with `none_observed` as a
valid value.**

**C9. `rule_change_candidate: boolean` does not link to Rule_Change_Queue.**
Setting it true should create a stub row.
**Disposition: addressed in v1.1 — flagging this field is required to
generate a `rule_change_id` reference, validated on save.**

**C10. MVP and full-spec field names disagree.**
v1.0 §3 minimum_viable lists `planned_exit` and `actual_exit`; §5.2 has
`planned_exit_strategy`, `target_1`, `target_2`, `exit_price_avg`.
**Disposition: addressed in v1.1 — MVP rewritten to use the canonical
field names from the full spec.**

**C11. Source-of-truth ambiguity between Fills and Trade_Log.**
`actual_entry_price`, `actual_position_size`, `exit_price_avg`, and
`gross_pnl_dollars` should be derived from Fills when Fills is in use.
**Disposition: addressed in v1.1 — Fills declared as canonical broker
record; Trade_Log execution fields are derived/computed and recomputed on
any Fills change. Pre-reconciliation manual values flagged with
`reconciliation_status` until reconciliation closes.**

**C12. `stop_changed: boolean` loses history.**
Only the most recent change is recorded.
**Disposition: addressed in v1.1 — every Daily_Management record captures
prior-and-new stop pair; recommended optional `Stop_History` derived view.**

**C13. `expectancy_decomposed` sign convention not stated.**
**Disposition: addressed in v1.1 §10 — `avg_loss_R` declared natively
negative; formula stated as `(win_rate × avg_win_R) + (loss_rate ×
avg_loss_R)`.**

**C14. `setup_status_rules.testing` references paper trading.**
Author confirmed paper trading is out of scope.
**Disposition: addressed in v1.1 — `testing` repurposed as
"reduced-size pilot."**

**C15. `portfolio_heat_pre_trade` calculation is undefined.**
Sum of original risks vs. sum of current at-risk capital.
**Disposition: addressed in v1.1 — `portfolio_heat_pre_trade` defined as
the sum of `current_at_risk_dollars` across open positions immediately
prior to the new trade (M3-aware definition).**

### 3.3 Practicality / Friction (P-series)

**P1. Field count is heavy and poorly tiered by lifecycle.**
Trade_Log has roughly 50 fields. `Required` / `Conditional` / `No` does
not distinguish "must enter at planning time" from "must complete
post-fill" from "must complete during post-trade review."
**Disposition: addressed in v1.1 — required-set tiered by lifecycle stage,
aligned with the state machine (M1).**

**P2. Daily_Management is the highest-friction part of the spec.**
With 6 open swings, ~15 fields per position per day will get skipped.
**Disposition: addressed in v1.1 — two record types: `daily_snapshot`
(minimal, allowed when no change occurred) and `event_log` (full row,
required on stop change, action taken, thesis status change, or rule
violation). Auto-population from yfinance specified for snapshot fields.**

**P3. No `source` annotation on fields.**
Roughly 15 fields are auto-populatable from market/broker data.
**Disposition: addressed in v1.1 §7 (Field Source and Latency Taxonomy)
with seven source categories. Updated for the actual data flow:
ToS CSV (not Alpaca API), yfinance (not real-time API), Finviz CSV (not
API), with explicit reconciliation-status semantics.**

**P4. Self-rated quality scores need calibration tracking.**
`pre_trade_quality_score` and `confidence_score` drift into reassurance
rituals if not validated.
**Disposition: addressed in v1.1 dashboard — score-vs-realized-R
correlation tracked; alert when self-scoring loses predictive power.**

**P5. Premortem floor of "at least one reason" is too low.**
Klein's premortem typically produces 3–5 distinct failure modes.
**Disposition: addressed in v1.1 — minimum raised to 3.**

**P6. No data-quality / completeness metric on the dashboard.**
**Disposition: addressed in v1.1 — `completeness_score` per trade and
period-level `data_quality_score` added to Review_Log and Dashboard.**

**P7. Review compliance not measured.**
**Disposition: addressed in v1.1 — Review_Log captures `scheduled_date`,
`completed_date`, `duration_minutes`, `skipped: boolean`, with dashboard
tracking review-on-time rate.**

**P8. `event_risk` and `gap_risk_plan` as required text invite checkbox
compliance.**
**Disposition: addressed in v1.1 — `event_risk` decomposed into
`event_risk_present: boolean`, `event_type: enum`, `event_date: date`,
`event_handling: enum`. `gap_risk_plan` decomposed similarly.**

**P9. Screenshot tab is referenced but missing from §5.**
**Disposition: addressed in v1.1 — Screenshots tab fully specified in §9.11.**

**P10. Pre-trade gate vs. pre-trade quality score relationship is unclear.**
**Disposition: addressed in v1.1 — gate is a prerequisite (binary
required-fields check); quality score is a downstream qualifier
(threshold-based size policy). Gate-fail short-circuits scoring.**

---

### 3.4 Findings Revealed by Implementation Context (N-series)

**N1. Reconciliation workflow is missing entirely from v1.0.**
The architecture has a fundamental two-source pattern: real-time manual
journal entry, batch broker reconciliation via TOS CSV exports.
**Disposition: addressed in v1.1 §9.10 (Reconciliation_Log entity),
§14 (cadence), and `reconciliation_status` field on Trade_Log and Fills.
Cadence default is weekly (see §4 of this findings document for rationale
against the originally proposed monthly).**

**N2. yfinance precision constraints affect MFE/MAE measurement.**
Intraday history is bounded; daily H/L is the only consistently available
source for swing horizons.
**Disposition: addressed in v1.1 §10 — explicit measurement convention:
daily H/L as canonical; entry-day MFE/MAE measured against entry-day
H/L from entry forward; intraday precision is best-effort within yfinance
lookback.**

**N3. yfinance is an unofficial dependency.**
Rate limits, ticker drift, intermittent breakage are known operational
risks.
**Disposition: addressed in v1.1 §7 — yfinance-sourced fields are flagged
as cacheable / idempotent / re-pullable. Outage delays auto-population
but does not block journaling.**

**N4. Finviz screen-of-origin is high-value attribution signal.**
Knowing which screen produced a ticker enables screen-level expectancy
analysis.
**Disposition: addressed in v1.1 — new `Daily_Screener_Log` tab (§9.12)
captures `source_screen`, `screen_criteria_snapshot`, and `screen_run_date`
at import time. `source_screen` flows watchlist → trade through the
`parent_watchlist_id` linkage; the trade record carries the *original*
screen of origin even if the ticker sat on the watchlist for weeks.**

**N5. Latency model should be explicit.**
Three latency tiers (real-time manual, end-of-day yfinance, post-week
ToS reconciliation) imply different trust levels at different times.
**Disposition: addressed in v1.1 §7 — each field carries
`source` and `availability_latency` annotations; AI evaluation rules can
trust or defer accordingly.**

---

## 4. Concerns Raised About Stated Approach

Two clarifications offered during the review raised concerns that warrant
explicit recording, separate from the v1.0 findings.

### 4.1 Monthly reconciliation cadence is too long

The author initially proposed monthly reconciliation on the grounds that
position count is low (max 6) and intended holding periods are weeks.

This reasons from trade frequency, but reconciliation cadence should be
set by error-cost and memory-decay, not trade count. Three problems:

- *Memory decay on manual fields.* A fill price discrepancy on day 3 of
  the month is reconstructable; the same discrepancy on day 28 cannot be
  reliably attributed to journal error vs. confirmation misread vs. routing
  artifact.
- *Compounding errors.* A mis-logged entry size invalidates every
  dependent calculation for that trade — open_R, MFE/MAE_R,
  portfolio_heat_pre_trade for any *next* trade taken while it is open.
- *Behavioral signal latency.* Reconciliation-revealed mistakes
  (`SIZE_MISCOUNTED`, `PARTIAL_NOT_LOGGED`) are themselves process errors;
  discovering one 25 days late means the same error pattern may have
  repeated several times before notice.

The author accepted weekly cadence after this concern was raised. **v1.1
adopts weekly reconciliation, ideally co-located with the existing weekly
review (§14).**

### 4.2 Finviz CSV export does not capture screen definition

Finviz CSV export contains result rows and visible columns but not the
screen preset / saved screen / filter set that produced the list. That
metadata is required for screen-level expectancy attribution.

The author accepted that the Finviz filter used would be recorded as a
field during daily screener processing.

**v1.1 adopts manual annotation at import time** (`source_screen` and
`screen_criteria_snapshot` in `Daily_Screener_Log`). The annotation flows
forward through the watchlist to the trade record; the trade carries the
*original* screen of origin, not whatever screen happens to be running on
entry day.

### 4.3 No rule against rapid open-and-close cycles

The author clarified that intent to hold for days-to-weeks is a *description*
of swing-trading discipline, not a rule, and that the existing "pause after
3 consecutive losses" rule already prevents drift into high-turnover
behavior. **v1.1 does not encode a minimum holding period.** It does encode
the consecutive-losses circuit breaker (§9.9) which the v1.0 spec omitted —
this is itself a gap that the clarification surfaced.

---

## 5. Priority-Ordered Remediation Summary

The following ordering reflects expected leverage. v1.1 addresses all items;
this ordering is provided so future revisions can be triaged consistently.

```yaml
priority_tier_1_architectural:
  - M1_state_machine
  - M6_hindsight_immutability
  - N1_reconciliation_workflow
  - M10_risk_policy_circuit_breakers

priority_tier_2_semantic:
  - M4_market_regime_enum
  - M5_catalyst_and_stop_type_enums
  - C6_setup_family_vs_entry_type_reconciliation
  - M2_pyramiding_risk_convention
  - M3_current_at_risk_separated_from_initial_risk
  - C15_portfolio_heat_definition
  - C5_mistake_cost_sign_convention
  - M7_counterfactual_rigor

priority_tier_3_data_flow:
  - P3_source_and_latency_annotation
  - N5_latency_model_explicit
  - M11_watchlist_promoted_required
  - N4_screen_of_origin_flow
  - C11_fills_as_source_of_truth

priority_tier_4_friction_and_quality:
  - P2_daily_management_two_record_types
  - N2_mfe_mae_measurement_convention
  - P6_data_quality_dashboard_metric
  - P7_review_compliance_tracking
  - P5_premortem_floor_three
  - P4_self_rating_calibration_tracking

priority_tier_5_consistency_cleanup:
  - C1_pre_trade_score_arithmetic
  - C2_circular_a_grade_requirement
  - C3_process_grade_composition_rule
  - C4_capture_ratio_edge_cases
  - C7_thesis_field_disambiguation
  - C8_mistake_tags_required
  - C9_rule_change_candidate_link
  - C10_mvp_field_name_alignment
  - C12_stop_history
  - C13_expectancy_sign_convention
  - C14_paper_trading_language_removed
  - P8_event_risk_structured
  - P9_screenshot_tab_specified
  - P10_gate_vs_score_relationship

priority_tier_6_scope_simplification:
  - stock_only_strip_options_language
  - single_account_no_account_id
  - paper_trading_language_removed
  - simplified_portfolio_heat_for_six_position_cap

priority_tier_7_completeness:
  - M8_streak_state_first_class
  - M9_re_entry_parent_trade_linkage
  - M12_missed_trades_recommended_not_optional
```

---

## 6. Decisions Adopted for v1.1

The author authorized v1.1 to be drafted without further consultation. The
following decisions were made on the author's behalf where v1.0 left them
open or where the findings required a definitive choice. Each decision is
justified in line with the author's stated preference for determinism and
non-AI fallback paths.

### 6.1 Pyramiding / risk convention (M2, M3, C15)

```yaml
decision_pyramiding_risk:
  initial_risk_dollars:
    definition: "first-tranche risk, locked at first fill"
    formula: "(actual_entry_price_first_fill - initial_stop) * actual_position_size_first_fill"
    immutable: true
    purpose: "denominator for all R-multiple calculations on this trade"
  current_at_risk_dollars:
    definition: "live capital at risk at this moment"
    formula: "(current_avg_cost - current_stop) * current_size for longs; sign-flipped for shorts"
    recomputed_on: "any fill change, any stop change"
    purpose: "portfolio heat aggregation; 'is this trade still risky?'"
  current_at_risk_R:
    formula: "current_at_risk_dollars / initial_risk_dollars"
    interpretation: "negative or near-zero means stop has been pulled to or beyond breakeven"
  rationale: "Tharp-consistent. R-denominator is fixed at first commitment so all subsequent outcomes are comparable. Live risk is tracked separately for portfolio heat and management decisions."
```

### 6.2 mistake_cost_R sign convention (C5, M7)

```yaml
decision_mistake_cost_sign:
  mistake_cost_R:
    formula: "max(0, realized_R_if_plan_followed - actual_realized_R)"
    range: "always >= 0"
    interpretation: "harm done by violating the plan"
  lucky_violation_R:
    formula: "max(0, actual_realized_R - realized_R_if_plan_followed)"
    range: "always >= 0"
    interpretation: "unearned benefit from violating the plan"
  aggregation_rule: "the two metrics are never netted against each other; lucky_violation_R is reported alongside mistake_cost_R as a separate flag, never as a benefit"
  counterfactual_procedures:
    chased_entry: "counterfactual = passed (R = 0)"
    moved_stop_away: "counterfactual = exit at original stop level on the bar it was first hit"
    sold_too_early: "counterfactual = exit per planned rule (target / trailing / time stop)"
    held_after_invalidation: "counterfactual = exit at close of bar where invalidation triggered"
    oversized: "counterfactual = same outcome scaled to planned size"
    no_setup_or_revenge: "counterfactual not measurable; mark mistake_cost_R as 'estimated' and exclude from hard portfolio totals"
  confidence_tag_required: true
```

### 6.3 Process grade composition (C3)

```yaml
decision_process_grade_composition:
  rule: "overall process_grade = worst of (entry_grade, management_grade, exit_grade)"
  rationale: "one major rule break should not be diluted by good behavior elsewhere; this is consistent with treating the journal as a discipline-measurement system rather than an averaging system"
  exception: "if any per-stage grade is F, overall is F regardless of others"
```

### 6.4 Re-entry semantics (M9)

```yaml
decision_re_entry:
  rule: "each entry is a discrete trade with its own trade_id and its own R-multiple math"
  linkage: "if the new entry is a re-entry of a stopped-out setup on the same ticker within 30 days, it carries parent_trade_id pointing at the prior trade"
  campaign_view: "dashboard offers a 'campaign' aggregation that groups parent and child trades for context, but expectancy and process metrics use discrete trades as the unit of analysis"
  rationale: "preserves clean per-decision math while allowing the trader to ask 'how did this campaign go overall?'"
```

### 6.5 Pre-trade quality score components are binary (C1)

```yaml
decision_pre_trade_score_components:
  scoring: "each component is 0 or its full point value; no partial credit"
  worth_2_component: "valid_setup_from_active_playbook (the only 2-point item)"
  rationale: "binary scoring is harder to game and produces sharper feedback signal"
```

### 6.6 Premortem floor (P5)

```yaml
decision_premortem_floor:
  minimum_failure_reasons: 3
  rationale: "consistent with practitioner premortem methodology; one reason is checkbox compliance"
```

### 6.7 Reconciliation cadence (N1, §4.1)

```yaml
decision_reconciliation_cadence:
  default: weekly
  scheduling: "co-located with weekly review per §10.2 of v1.0"
  fallback_max: "no longer than two weeks"
  manual_entry_confidence_field: "low | normal | high"
  trigger_for_immediate_reconciliation: "any field marked low confidence on a closed trade"
```

### 6.8 Daily_Management record types (P2)

```yaml
decision_daily_management_record_types:
  daily_snapshot:
    when_allowed: "no stop change, no action taken, thesis_status unchanged, no rule violation"
    required_fields: [management_record_id, trade_id, review_date, current_price, open_R, current_stop, thesis_status, MFE_to_date_R, MAE_to_date_R]
    auto_populatable_fields: [current_price, open_R, MFE_to_date_R, MAE_to_date_R]
    manual_fields: [thesis_status]
  event_log:
    when_required: "any of: stop changed, action_taken in {trim, add, exit, move_stop}, thesis_status changed, rule violation suspected"
    required_fields: "all daily_snapshot fields plus all v1.0 §5.4 fields"
```

### 6.9 MFE/MAE measurement convention (N2)

```yaml
decision_mfe_mae_convention:
  source: "yfinance daily OHLCV"
  entry_day:
    mfe_dollars: "max(entry_day_high, entry_price) - entry_price for longs"
    mae_dollars: "entry_price - min(entry_day_low, entry_price) for longs"
    note: "uses full daily H/L because intraday before-fill bars cannot count; this slightly overstates MFE/MAE on entry day but is reproducible from public data"
  subsequent_days:
    mfe_dollars: "max favorable distance from entry_price across all daily H/L from entry_day+1 to exit_day-1 inclusive"
    mae_dollars: "max adverse distance from entry_price across same range"
  exit_day:
    use: "daily H/L through the exit fill bar"
  R_normalization:
    mfe_R: "mfe_dollars / risk_per_share"
    mae_R: "mae_dollars / risk_per_share"
  best_effort_intraday: "if intraday bars are available within yfinance lookback, they may be used to refine entry-day measurement, but daily H/L is the contractual minimum"
```

### 6.10 Controlled vocabularies (M4, M5, C6)

Decisions for `market_regime`, `catalyst`, `stop_type`, `setup_family`, and
`entry_trigger_type` enums are authored in v1.1 §8 and not duplicated here.
Each enum was chosen to balance practitioner-recognizable terminology
(Minervini, Weinstein, Qullamaggie) with mutual exclusivity sufficient for
deterministic AI evaluation.

### 6.11 Circuit breakers (M8, §4.3)

```yaml
decision_circuit_breakers:
  consecutive_losses_pause_threshold: 3
  pause_action: review_required_before_next_trade
  pause_duration: until_review_completed
  streak_reset_condition: any_winning_trade_or_review_completed
  drawdown_pause_threshold_R: -6
  drawdown_pause_action: reduce_size_to_50pct_until_drawdown_recovers
  rationale: "encodes the author's stated rule (pause after 3 consecutive losses); adds a drawdown circuit breaker because a single -3R loss can be more diagnostic than three small ones, and the author indicated openness to drawdown-aware logic during review"
  authorial_note: "the drawdown threshold and action are author-tunable; defaults are conservative and consistent with the author's six-position max and stated preference for capital preservation"
```

### 6.12 Pre-trade lock semantics (M6)

```yaml
decision_pre_trade_lock:
  trigger: "first fill recorded on the trade"
  effect: "all pre-trade fields become read-only"
  override: "explicit override action with audit log entry capturing prior_value, new_value, reason, override_timestamp"
  audit_log_entity: "Pre_Trade_Edit_Audit"
  rationale: "addresses M6 hindsight integrity gap with deterministic enforcement rather than honor-system timestamping"
```

### 6.13 Setup status: testing repurposed (C14)

```yaml
decision_setup_status_testing:
  v1_0_definition: "paper trading, backtesting, or reduced size only"
  v1_1_definition: "reduced-size pilot only (max 50% of normal risk allocation)"
  rationale: "paper trading explicitly out of scope per author"
```

---

## 7. Companion Deliverable

The companion file `swing_trading_journal_ai_ingestion_v1.1.md` incorporates
all findings and decisions documented here. v1.1 preserves v1.0's section
numbering where unchanged, inserts new sections for the state machine,
controlled vocabularies, source/latency taxonomy, and adds new tabs
(Watchlist, Risk_Policy, Reconciliation_Log, Daily_Screener_Log) where the
findings required them.

A changelog is included as the final section of v1.1 listing every
substantive change relative to v1.0.

---
