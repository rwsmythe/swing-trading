---
title: "AI-Ready Swing Trading Journal Layout Research and Execution Specification"
version: "1.2"
prior_version: "1.1"
document_type: "research_to_execution_spec"
created_for: "AI evaluation, planning, orchestration, and Python swing trading tool implementation"
created_date: "2026-05-01"
timezone_context: "Pacific/Honolulu"
not_financial_advice: true
primary_design_goal: "Capture swing-trading decision quality before outcome knowledge, normalize performance by risk, enforce capital-protection rules, and preserve trader usability by distinguishing hard gates from soft analytics."
changes_from_v1_1_summary: "v1.2 preserves v1.1 architecture but softens over-gated areas: trade_origin is required while parent_watchlist_id is conditional; Screen_Definitions version screen criteria; post-trade reviews can be provisional before reconciliation; process grading uses weighted stages with disqualifying floors; pre-trade gates remain binary while quality scoring permits partial credit; MFE/MAE uses a precision hierarchy; portfolio heat caps negative risk at zero; pyramiding reports multiple R views; drawdown breaker is opt-in; consecutive-loss reset requires review completion."
intended_use:
  - evaluate_existing_trading_journal
  - design_new_swing_trading_journal
  - plan_python_tool_implementation
  - generate_claude_code_orchestrator_briefs
  - coordinate_sub_agents_for_schema_validation_reconciliation_market_data_dashboard_and_scoring
  - execute_pre_trade_in_trade_post_trade_review_workflows
---

# AI-Ready Swing Trading Journal Layout Research and Execution Specification (v1.2)

## 0. Operating Instruction for AI Orchestrators

Use this document as the **canonical v1.2 specification** for a Python-based swing trading journal tool.

This document is written for an AI orchestrator that will evaluate the specification, decompose it into implementation briefs, and coordinate sub-agents that build the tool.

The orchestrator should prioritize these objectives in order:

```yaml
orchestrator_priority_order:
  1_preserve_decision_integrity:
    description: "Capture thesis, risk, invalidation, planned management, and emotional state before outcome knowledge. Lock pre-trade fields after first fill."
  2_protect_capital:
    description: "Enforce risk definition, position sizing, max positions, portfolio heat, and the consecutive-loss pause rule."
  3_normalize_results_by_risk:
    description: "Compute R-multiple outcomes using clearly defined denominators, including multiple R views for pyramided trades."
  4_separate_process_from_outcome:
    description: "Grade decision quality independently from P&L. Profitable rule violations remain process failures."
  5_reduce_journaling_friction:
    description: "Use low-friction defaults, provisional workflows, automation, and conditional requirements to preserve trader compliance."
  6_measure_behavioral_leakage:
    description: "Tag mistakes, estimate mistake cost when valid, track lucky violations separately, and aggregate process leakage."
  7_maintain_data_truth:
    description: "Use Fills as execution source of truth and reconcile weekly against thinkorswim CSV exports."
  8_generate_actionable_feedback:
    description: "Dashboard metrics should support setup refinement, risk control, behavioral improvement, and review discipline."
```

### 0.1 Hard Gates vs. Soft Analytics vs. Provisional Workflows

v1.2 explicitly distinguishes three categories.

```yaml
classification_model:
  hard_gates:
    definition: "conditions that block approval, state transition, or finalization"
    examples:
      - risk_defined
      - stop_or_invalidation_defined
      - position_size_within_policy
      - pre_trade_lock_after_first_fill
      - consecutive_loss_pause_review_required
      - required_state_fields_complete
  soft_analytics:
    definition: "fields and metrics that improve learning but do not block legitimate trades by themselves"
    examples:
      - source_screen
      - time_on_watchlist_days
      - missed_trades
      - MFE_MAE_precision
      - self_score_calibration
      - watchlist_conversion_rate
  provisional_workflows:
    definition: "workflows that can proceed with provisional status before final data is available"
    examples:
      - post_trade_review_before_broker_reconciliation
      - MFE_MAE_estimates_before_intraday_precision_available
      - initial manual fills before TOS CSV reconciliation
```

The orchestrator must not convert every useful analytic into a hard gate. Enforce what protects decision integrity and capital. Measure the rest.

---

## 1. Scope and Constraints

```yaml
scope_in:
  trading_mode: live
  account_count: 1
  instrument_scope: stock_only
  primary_holding_horizon: "days to weeks"
  intended_style: "momentum / trend continuation / breakout / episodic pivot swing trading"
  position_count_cap: 6
  broker: thinkorswim
  broker_export_format: "TOS CSV"
  primary_screener: Finviz
  screener_export_format: CSV
  market_data_initial_provider: yfinance
  runtime_target: "Python swing trading tool"
  ai_consumer: "AI orchestrator coordinating implementation agents"

scope_out:
  options: false
  futures: false
  forex: false
  crypto: false
  paper_trading: false
  multi_account: false
  intraday_day_trading: false
```

---

## 2. System Architecture

```yaml
required_entities:
  - Setup_Playbook
  - Screen_Definitions
  - Daily_Screener_Log
  - Watchlist
  - Trade_Log
  - Fills
  - Daily_Management
  - Risk_Policy
  - Reconciliation_Log
  - Mistake_Tags
  - Review_Log
  - Rule_Change_Queue
  - Dashboard

recommended_entities:
  - Screenshots
  - Missed_Trades
  - Pre_Trade_Edit_Audit
  - Market_Regime_Log
  - Sector_Theme_Log

optional_advanced_entities:
  - Backtest_Comparison
  - Stop_History_View
  - Campaign_View
```

### 2.1 Minimal Viable Product

The MVP should support a full lifecycle from screen/import to reviewed trade.

```yaml
minimum_viable_product:
  must_implement:
    - Setup_Playbook
    - Screen_Definitions
    - Daily_Screener_Log
    - Watchlist
    - Trade_Log_with_state_machine
    - Fills
    - Risk_Policy
    - pre_trade_gate
    - pre_trade_lock
    - realized_R_effective
    - weekly_reconciliation_manual_import_stub
  can_defer:
    - advanced_dashboard_segmentation
    - missed_trade_analysis
    - screenshots_library
    - campaign_view
    - backtest_comparison
```

---

## 3. Entity Relationship Model

```yaml
entities:
  Setup:
    primary_key: setup_id
    relationship: "one setup maps to many trades"

  Screen_Definition:
    primary_key: screen_id
    relationship: "one screen definition version can produce many screener runs"

  Screener_Run:
    primary_key: screener_run_id
    foreign_keys: [screen_id]
    relationship: "one run produces many screener ticker entries"

  Screener_Ticker_Entry:
    primary_key: screener_ticker_entry_id
    foreign_keys: [screener_run_id]
    relationship: "one ticker entry may become a watchlist entry or direct trade source"

  Watchlist_Entry:
    primary_key: watchlist_entry_id
    foreign_keys: [screener_ticker_entry_id, screen_id]
    relationship: "one watchlist entry can produce zero, one, or multiple linked trades"

  Trade:
    primary_key: trade_id
    foreign_keys:
      - setup_id
      - parent_watchlist_id_nullable
      - parent_trade_id_nullable
      - screener_ticker_entry_id_nullable
    relationship: "one trade has many fills, many management records, many screenshots, and reconciliation status"

  Fill:
    primary_key: fill_id
    foreign_keys: [trade_id]
    relationship: "many fills belong to one trade; Fills is source of truth for execution"

  Daily_Management_Record:
    primary_key: management_record_id
    foreign_keys: [trade_id]
    record_type_enum: [daily_snapshot, event_log]

  Risk_Policy:
    primary_key: policy_id
    relationship: "one active policy at a time; historical policies retained"

  Reconciliation_Run:
    primary_key: reconciliation_id
    relationship: "one weekly run has many discrepancy rows"

  Reconciliation_Discrepancy:
    primary_key: discrepancy_id
    foreign_keys: [reconciliation_id, trade_id, fill_id]

  Review_Record:
    primary_key: review_id
    relationship: "periodic reviews aggregate trades, mistakes, and reconciliation events"

  Rule_Change_Candidate:
    primary_key: rule_change_id
    relationship: "rule changes cite supporting trade ids and sample-size evidence"
```

---

## 4. Controlled Vocabularies

Central enums should be centralized in code and referenced by validation logic.

### 4.1 `trade_origin`

```yaml
trade_origin:
  finviz_screen: "originated directly from a Finviz screen result"
  watchlist: "originated from a previously tracked watchlist entry"
  price_alert: "originated from a configured alert"
  earnings_gap: "originated from earnings-driven gap or reaction"
  news_event: "originated from breaking or scheduled news"
  manual_discovery: "manually discovered outside screener/watchlist pipeline"
  prior_trade_reentry: "re-entry related to prior stopped or closed trade"
```

### 4.2 `market_regime`

```yaml
market_regime:
  bull_trending: "broad market in confirmed uptrend"
  bull_pullback: "uptrend intact but pulling back"
  distribution_top: "leadership weakening, distribution visible"
  bear_trending: "confirmed downtrend"
  bear_rally: "countertrend rally in larger downtrend"
  range_compression: "tight range, low volatility"
  range_choppy: "wide directionless range"
  transition_unclear: "mixed signals; caution default"
```

### 4.3 `setup_family`

```yaml
setup_family:
  breakout: "breakout from base or consolidation"
  pullback: "pullback within uptrend"
  episodic_pivot: "high-volume earnings or news pivot"
  gap_continuation: "gap with continuation setup"
  reversal: "reversal from prior trend"
  trend_continuation: "mid-trend continuation entry"
  vcp_pivot: "volatility contraction pattern pivot"
  reclaim: "reclaim of lost support/resistance"
```

### 4.4 `entry_trigger_type`

```yaml
entry_trigger_type:
  breakout_pivot: "break above defined pivot"
  pullback_to_ma: "entry near moving-average support"
  pullback_to_pivot: "entry near prior breakout level"
  gap_and_go: "gap-up continuation"
  reclaim_level: "reclaim of key level"
  opening_range: "opening-range break"
  reversal_signal: "reversal candle or signal"
  bounce_off_support: "bounce from defined support"
```

### 4.5 `stop_type`

```yaml
stop_type:
  chart_swing_low_high: "below swing low or above swing high"
  chart_consolidation_break: "break of consolidation boundary"
  atr_multiple: "ATR-based stop"
  percentage_below_entry: "fixed percentage stop"
  prior_day_low_high: "prior day low/high"
  moving_average: "moving-average based stop"
  time_stop_only: "time stop without price stop; flagged as lower quality"
  volatility_band: "volatility-band stop"
  discretionary: "not objective; allowed only with downgrade/flag"
```

### 4.6 `catalyst`

```yaml
catalyst:
  earnings_beat
  earnings_miss
  guidance_raise
  guidance_cut
  ma_announcement
  secondary_offering
  analyst_action
  sector_rotation
  macro_event
  sympathy_move
  technical_only
  product_news
  other
```

### 4.7 `thesis_status`, `thesis_accuracy`, and `setup_validity_after_review`

```yaml
thesis_status:
  valid
  strengthening
  weakening
  invalidated
  unclear

thesis_accuracy:
  correct
  partially_correct
  incorrect
  unclear

setup_validity_after_review:
  valid
  marginal
  invalid
  lucky
```

### 4.8 `reconciliation_status`

```yaml
reconciliation_status:
  unreconciled
  reconciled_match
  reconciled_discrepancy
  reconciled_discrepancy_resolved
  manual_override
```

### 4.9 `post_trade_review_status`

```yaml
post_trade_review_status:
  provisional
  final_reconciled
  reopened_due_to_reconciliation_discrepancy
```

### 4.10 `MFE_MAE_precision_level`

```yaml
MFE_MAE_precision_level:
  intraday_exact
  intraday_estimated
  daily_approximate
```

---

## 5. Trade Lifecycle State Machine

```yaml
trade_states:
  planned: "idea exists; no trigger/fill yet"
  triggered: "entry condition met; no fill recorded"
  entered: "first fill recorded; pre-trade fields locked"
  managing: "open position under management"
  partial_exited: "one or more trims/partials recorded; still open"
  closed: "net position flat"
  reviewed: "post-trade review completed, provisional or final"
  canceled: "idea abandoned before entry"

allowed_transitions:
  planned: [triggered, entered, canceled]
  triggered: [entered, canceled]
  entered: [managing]
  managing: [partial_exited, closed]
  partial_exited: [managing, closed]
  closed: [reviewed]
  reviewed: []
  canceled: []
```

### 5.1 Required Fields by State

```yaml
required_fields_by_state:
  planned:
    - trade_id
    - state
    - ticker
    - trade_origin
    - setup_id
    - direction
    - planned_date
    - market_regime
    - catalyst
    - thesis
    - why_now
    - expected_scenario
    - invalidation_condition
    - premortem_failure_reasons_structured
    - planned_entry
    - initial_stop
    - stop_type
    - planned_position_size
    - planned_risk_dollars
    - event_risk_present
    - event_handling
    - gap_risk_present
    - gap_risk_handling
    - emotional_state_pre_trade
    - pre_trade_quality_score
    - final_pre_trade_decision
    - manual_entry_confidence

  conditional_planned:
    parent_watchlist_id:
      required_when: "trade_origin in [finviz_screen, watchlist]"
    trade_origin_detail:
      required_when: "parent_watchlist_id is null"
    screener_ticker_entry_id:
      required_when: "trade_origin == finviz_screen"
    parent_trade_id:
      required_when: "trade_origin == prior_trade_reentry"

  triggered:
    inherits_from: planned
    additional:
      - trigger_observed_datetime

  entered:
    inherits_from: triggered_or_planned
    additional:
      - actual_entry_date
      - actual_entry_price
      - actual_position_size
      - initial_risk_dollars_first_tranche
      - pre_trade_locked_at
      - entry_trigger_type
      - entry_trigger_followed
      - reconciliation_status

  managing:
    inherits_from: entered
    additional:
      - current_stop
      - current_size
      - current_avg_cost
      - raw_current_at_risk_dollars
      - portfolio_heat_contribution_dollars
      - daily_management_records

  closed:
    inherits_from: managing_or_partial_exited
    additional:
      - exit_date
      - exit_price_avg
      - exit_reason
      - planned_exit_followed
      - net_pnl_dollars
      - realized_R_initial
      - realized_R_effective
      - MFE_R
      - MAE_R
      - MFE_MAE_precision_level
      - holding_period_days

  reviewed:
    inherits_from: closed
    additional:
      - post_trade_review_status
      - thesis_accuracy
      - setup_validity_after_review
      - entry_grade
      - management_grade
      - exit_grade
      - process_grade
      - disqualifying_process_violation
      - mistake_tags
      - mistake_cost_R
      - lucky_violation_R
      - mistake_cost_confidence
      - lesson_learned
      - rule_change_candidate
      - reviewed_at
```

---

## 6. Field Source and Latency Taxonomy

```yaml
source_categories:
  manual_pre_trade:
    immutable_after: pre_trade_locked_at
    examples:
      - thesis
      - why_now
      - invalidation_condition
      - planned_entry
      - initial_stop
      - premortem_failure_reasons_structured
      - emotional_state_pre_trade

  manual_in_trade:
    examples:
      - current_stop
      - thesis_status
      - action_taken
      - action_reason
      - emotional_state

  manual_post_trade:
    examples:
      - thesis_accuracy
      - setup_validity_after_review
      - stage_grades
      - lesson_learned

  finviz_import:
    examples:
      - raw_screen_columns
      - screener_ticker_entries

  screen_definition_reference:
    examples:
      - screen_id
      - screen_version
      - criteria_snapshot_materialized

  tos_export_reconciled:
    examples:
      - actual_fill_price
      - actual_fill_size
      - actual_fill_datetime
      - fees
      - broker_realized_pnl

  yfinance_query:
    examples:
      - current_price
      - daily_high_low
      - ATR_inputs
      - market_data_for_MFE_MAE_fallback

  computed:
    examples:
      - risk_per_share
      - planned_position_size
      - R_views
      - portfolio_heat
      - process_grade
      - data_quality_score
```

```yaml
availability_latency:
  immediate: [manual_pre_trade, manual_in_trade, manual_post_trade, finviz_import, screen_definition_reference]
  end_of_day: [yfinance_query, computed_from_eod_data]
  weekly_reconciled: [tos_export_reconciled]
```

---

## 7. Tab Specifications

## 7.1 `Setup_Playbook`

```yaml
tab: Setup_Playbook
row_granularity: "one row per setup"
primary_key: setup_id
ai_use:
  - validate_trade_matches_setup
  - segment_expectancy_by_setup
  - detect_setup_drift
  - generate_setup_refinement_briefs
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `setup_id` | string | yes | Unique identifier |
| `setup_name` | string | yes | Human-readable setup name |
| `setup_family` | enum | yes | See §4.3 |
| `direction_allowed` | enum | yes | `long`, `short`, `both`; v1.2 implementation uses `long` |
| `market_regime_allowed` | list | yes | Allowed regimes |
| `timeframe` | string | yes | Daily, weekly/daily, etc. |
| `liquidity_minimum` | numeric | yes | Minimum dollar volume |
| `relative_strength_requirement` | text | no | RS requirement |
| `technical_structure` | text | yes | Pattern definition |
| `entry_trigger_type_default` | enum | yes | See §4.4 |
| `entry_trigger_rule` | text | yes | Objective trigger |
| `initial_stop_type` | enum | yes | See §4.5 |
| `initial_stop_rule` | text | yes | Objective stop rule |
| `profit_taking_rule` | text | yes | Exit/partial rule |
| `time_stop_rule` | text | yes | Max hold if no progress |
| `add_on_rule` | text | no | Pyramiding rule if applicable |
| `disqualifiers` | list | yes | Conditions that invalidate setup |
| `status` | enum | yes | `active`, `pilot`, `paused`, `retired` |

---

## 7.2 `Screen_Definitions`

Purpose: Version Finviz screens so daily imports do not require repeated manual criteria entry.

```yaml
tab: Screen_Definitions
row_granularity: "one row per screen version"
primary_key: screen_id
ai_use:
  - screen_level_expectancy
  - screen_to_watchlist_conversion
  - screen_version_audit
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `screen_id` | string | yes | Unique screen version ID |
| `screen_name` | string | yes | Human-readable screen name |
| `version` | string | yes | Version label |
| `criteria_json` | json | yes | Structured Finviz criteria |
| `criteria_human_readable` | text | yes | Trader-readable criteria |
| `effective_from` | date | yes | Start date |
| `effective_to` | date | no | End date if replaced |
| `is_active` | boolean | yes | Current active status |
| `notes` | text | no | Rationale / changes |

---

## 7.3 `Daily_Screener_Log`

Purpose: Record Finviz CSV imports and preserve source-of-origin attribution.

```yaml
tab: Daily_Screener_Log
parent_entity: Screener_Run
child_entity: Screener_Ticker_Entry
```

### `Screener_Run`

| Field | Type | Required | Description |
|---|---:|---:|---|
| `screener_run_id` | string | yes | Unique run ID |
| `run_date` | date | yes | Import date |
| `screen_id` | string | yes | Links to Screen_Definitions |
| `criteria_snapshot_materialized` | json/text | yes | Snapshot copied from active screen version at import |
| `csv_export_filename` | string | yes | Source CSV filename |
| `tickers_returned_count` | numeric | yes | Count |
| `notes` | text | no | Context |

### `Screener_Ticker_Entry`

| Field | Type | Required | Description |
|---|---:|---:|---|
| `screener_ticker_entry_id` | string | yes | Unique ticker entry ID |
| `screener_run_id` | string | yes | Parent run |
| `ticker` | string | yes | Symbol |
| `raw_screen_columns` | json/text | no | Original CSV columns |
| `promoted_to_watchlist` | boolean | yes | Whether promoted |
| `watchlist_entry_id` | string | conditional | Required if promoted |
| `direct_trade_id` | string | conditional | Set if trade originates directly from screen |

---

## 7.4 `Watchlist`

Purpose: Track stalk-list candidates, but do not force every trade to come from watchlist.

```yaml
tab: Watchlist
row_granularity: "one row per ticker watch instance"
primary_key: watchlist_entry_id
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `watchlist_entry_id` | string | yes | Unique ID |
| `screener_ticker_entry_id` | string | conditional | Source screen ticker if applicable |
| `screen_id` | string | conditional | Original screen source if applicable |
| `ticker` | string | yes | Symbol |
| `added_date` | date | yes | Date added |
| `source_screen` | string | conditional | Materialized from screen definition if applicable |
| `setup_id_candidate` | string | no | Candidate setup |
| `pivot_price_candidate` | numeric | no | Candidate trigger |
| `notes` | text | no | Stalk notes |
| `removed_date` | date | conditional | Date removed |
| `removal_reason` | enum | conditional | `traded`, `failed_pattern`, `regime_changed`, `no_trigger`, `other` |
| `resulting_trade_id` | string | conditional | If traded |

---

## 7.5 `Trade_Log`

Purpose: Main trade-level table. One row per discrete trade decision. Re-entries are new trades linked through `parent_trade_id`.

### Identity and Provenance

| Field | Type | Required | Description |
|---|---:|---:|---|
| `trade_id` | string | yes | Unique trade identifier |
| `state` | enum | yes | State machine value |
| `ticker` | string | yes | Symbol |
| `instrument_type` | enum | yes | `stock` |
| `direction` | enum | yes | `long` for current scope |
| `trade_origin` | enum | yes | See §4.1 |
| `parent_watchlist_id` | string | conditional | Required if origin is watchlist/screener-derived |
| `screener_ticker_entry_id` | string | conditional | Required if origin is Finviz screen direct |
| `parent_trade_id` | string | conditional | Required if origin is prior_trade_reentry |
| `trade_origin_detail` | text | conditional | Required when no watchlist/screener linkage exists |
| `setup_id` | string | yes | Links to Setup_Playbook |

### Pre-Trade Decision Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `planned_date` | date | yes | Date planned |
| `market_regime` | enum | yes | See §4.2 |
| `sector_theme` | string | no | Sector/theme |
| `sector_condition` | enum | no | `leading`, `improving`, `neutral`, `weakening`, `lagging` |
| `catalyst` | enum | yes | See §4.6 |
| `catalyst_other_description` | text | conditional | Required if `other` |
| `thesis` | text | yes | Why trade should work |
| `why_now` | text | yes | Why entry is timely |
| `expected_scenario` | text | yes | What should happen if right |
| `invalidation_condition` | text | yes | What proves thesis wrong |
| `premortem_technical_failure_reason` | text | yes | Technical failure mode |
| `premortem_market_or_sector_failure_reason` | text | yes | Market/sector failure mode |
| `premortem_execution_or_behavior_failure_reason` | text | yes | Execution/behavior failure mode |
| `additional_premortem_reasons` | list[text] | no | Optional extra reasons |
| `confidence_score` | numeric | no | 1–5 |
| `pre_trade_quality_score` | numeric | yes | 0–10; partial credit allowed |
| `emotional_state_pre_trade` | list[enum] | yes | Emotional condition |
| `final_pre_trade_decision` | enum | yes | `take`, `pass`, `wait`, `reduce_size` |

### Risk Plan Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `account_equity_pre_trade` | numeric | yes | Account equity before trade |
| `max_account_risk_pct` | numeric | yes | Risk percent |
| `planned_risk_dollars` | numeric | yes | Computed |
| `planned_entry` | numeric | yes | Intended entry |
| `initial_stop` | numeric | yes | Initial stop |
| `stop_type` | enum | yes | See §4.5 |
| `risk_per_share` | numeric | yes | Computed |
| `target_1` | numeric | recommended | First target |
| `target_2` | numeric | no | Secondary target |
| `planned_position_size` | numeric | yes | Computed |
| `planned_gross_exposure` | numeric | yes | Computed |
| `portfolio_heat_pre_trade` | numeric | yes | Existing heat before trade |
| `correlated_exposure` | text | yes | Sector/theme overlap |
| `planned_reward_risk_ratio` | numeric | recommended | R/R to target 1 |
| `position_size_override_reason` | text | conditional | Required if formula overridden |
| `planned_holding_period_days` | numeric | yes | Expected duration |
| `event_risk_present` | boolean | yes | Known event risk exists |
| `event_type` | enum | conditional | Required if event_risk_present |
| `event_date` | date | conditional | Required if event_risk_present |
| `event_handling` | enum | yes | `avoid_event`, `hold_through`, `reduce_before`, `exit_before`, `not_applicable` |
| `gap_risk_present` | boolean | yes | Overnight gap risk acknowledged |
| `gap_risk_handling` | enum | yes | `accept`, `reduce_size`, `tight_stop`, `exit_before_close`, `not_applicable` |

### Execution Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `trigger_observed_datetime` | datetime | conditional | Required in triggered state |
| `actual_entry_date` | date | entered+ | Derived from Fills |
| `actual_entry_time` | time | no | Derived from Fills |
| `actual_entry_price` | numeric | entered+ | Weighted average from Fills |
| `actual_position_size` | numeric | entered+ | Derived from Fills |
| `entry_order_type` | enum | no | Order type |
| `entry_trigger_type` | enum | entered+ | See §4.4 |
| `entry_trigger_followed` | boolean | entered+ | Trigger compliance |
| `entry_slippage` | numeric | no | Computed |
| `pre_trade_locked_at` | datetime | entered+ | Written once at first fill |
| `initial_risk_dollars_first_tranche` | numeric | entered+ | Initial denominator |
| `manual_entry_confidence` | enum | yes | `high`, `normal`, `low` |
| `reconciliation_status` | enum | yes | Default `unreconciled` |

### Live Risk Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `current_avg_cost` | numeric | open states | Computed from Fills |
| `current_size` | numeric | open states | Net open size |
| `current_stop` | numeric | open states | Latest stop |
| `raw_current_at_risk_dollars` | numeric | open states | Can be negative |
| `portfolio_heat_contribution_dollars` | numeric | open states | `max(0, raw_current_at_risk_dollars)` |
| `locked_in_profit_at_stop_dollars` | numeric | open states | `max(0, -raw_current_at_risk_dollars)` |
| `open_R_initial` | numeric | open states | Unrealized R vs first tranche denominator |
| `open_R_effective` | numeric | open states | Unrealized R vs effective risk denominator if available |

### Exit and Review Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `exit_date` | date | closed+ | Derived from Fills |
| `exit_price_avg` | numeric | closed+ | Derived from Fills |
| `exit_reason` | enum | closed+ | Exit classification |
| `planned_exit_followed` | boolean | closed+ | Exit compliance |
| `gross_pnl_dollars` | numeric | closed+ | Computed |
| `fees_commissions` | numeric | final | TOS reconciled |
| `net_pnl_dollars` | numeric | closed+ | Computed, provisional until reconciled |
| `realized_R_initial` | numeric | closed+ | See formulas |
| `realized_R_effective` | numeric | closed+ | Primary dashboard R |
| `realized_R_campaign` | numeric | conditional | Required if pyramiding/campaign applicable |
| `MFE_R` | numeric | closed+ | Computed |
| `MAE_R` | numeric | closed+ | Computed |
| `MFE_MAE_precision_level` | enum | closed+ | Precision level |
| `capture_ratio` | numeric | conditional | Only when realized_R > 0 and MFE_R > 0 |
| `holding_period_days` | numeric | closed+ | Computed |
| `post_trade_review_status` | enum | reviewed+ | `provisional`, `final_reconciled`, `reopened_due_to_reconciliation_discrepancy` |
| `thesis_accuracy` | enum | reviewed+ | See §4.7 |
| `setup_validity_after_review` | enum | reviewed+ | See §4.7 |
| `entry_grade` | enum | reviewed+ | A/B/C/D/F |
| `management_grade` | enum | reviewed+ | A/B/C/D/F |
| `exit_grade` | enum | reviewed+ | A/B/C/D/F |
| `disqualifying_process_violation` | boolean | reviewed+ | Hard severity flag |
| `process_grade` | enum | reviewed+ | Computed using §10.2 |
| `mistake_tags` | list | reviewed+ | Required; `none_observed` acceptable |
| `mistake_cost_R` | numeric | reviewed+ | Harm only |
| `lucky_violation_R` | numeric | reviewed+ | Unearned benefit only |
| `mistake_cost_confidence` | enum | reviewed+ | `high`, `medium`, `low` |
| `lesson_learned` | text | reviewed+ | One clear lesson |
| `rule_change_candidate` | boolean | reviewed+ | Candidate flag |
| `rule_change_id` | string | conditional | Required if candidate true |
| `reviewed_at` | datetime | reviewed+ | Review timestamp |

---

## 7.6 `Fills`

Fills are canonical for execution. Trade_Log execution fields derive from this table.

| Field | Type | Required | Description |
|---|---:|---:|---|
| `fill_id` | string | yes | Unique fill ID |
| `trade_id` | string | yes | Parent trade |
| `fill_datetime` | datetime | yes | Fill time |
| `action` | enum | yes | `entry`, `add`, `trim`, `exit`, `stop`, `cover` |
| `quantity` | numeric | yes | Filled quantity |
| `price` | numeric | yes | Fill price |
| `order_type` | enum | no | Order type |
| `reason` | text | yes | Why fill happened |
| `rule_based` | boolean | yes | Whether fill complied with plan |
| `fees` | numeric | conditional | Required after reconciliation |
| `manual_entry_confidence` | enum | yes | `high`, `normal`, `low` |
| `reconciliation_status` | enum | yes | See §4.8 |
| `tos_match_id` | string | conditional | TOS row identifier after reconciliation |

---

## 7.7 `Daily_Management`

Two record types reduce friction while preserving management history.

```yaml
record_types:
  daily_snapshot:
    use_when: "no stop change, no action, thesis unchanged, no suspected rule violation"
  event_log:
    use_when: "stop change, action taken, thesis status changed, rule violation suspected, major market/sector update"
```

### Daily Snapshot Minimum

| Field | Type | Required | Description |
|---|---:|---:|---|
| `management_record_id` | string | yes | Unique row |
| `trade_id` | string | yes | Parent trade |
| `record_type` | enum | yes | `daily_snapshot` |
| `review_date` | date | yes | Review date |
| `current_price` | numeric | yes | yfinance/broker data |
| `current_stop` | numeric | yes | Manual confirm |
| `open_R_effective` | numeric | yes | Computed |
| `portfolio_heat_contribution_dollars` | numeric | yes | Computed |
| `MFE_to_date_R` | numeric | yes | Computed |
| `MAE_to_date_R` | numeric | yes | Computed |
| `thesis_status` | enum | yes | See §4.7 |

### Event Log Additional Fields

| Field | Type | Required | Description |
|---|---:|---:|---|
| `prior_stop` | numeric | yes | Previous stop |
| `stop_changed` | boolean | yes | Stop change flag |
| `stop_change_reason` | text | conditional | Required if stop_changed |
| `volume_behavior` | enum | no | `confirming`, `neutral`, `distribution`, `fading` |
| `relative_strength_status` | enum | no | `improving`, `flat`, `weakening` |
| `market_regime_change` | boolean | yes | Regime change flag |
| `sector_condition_change` | boolean | yes | Sector change flag |
| `news_or_event_update` | text | no | New info |
| `action_taken` | enum | yes | `hold`, `trim`, `add`, `exit`, `move_stop`, `no_action` |
| `action_reason` | text | yes | Explain decision |
| `emotional_state` | list[enum] | yes | Emotional condition |
| `rule_violation_suspected` | boolean | yes | Suspected violation |
| `management_notes` | text | no | Extra context |

---

## 7.8 `Risk_Policy`

Risk_Policy enforces known rules and supports optional rules.

| Field | Type | Required | Default | Description |
|---|---:|---:|---:|---|
| `policy_id` | string | yes | — | Unique policy ID |
| `effective_from` | date | yes | — | Start date |
| `effective_to` | date | no | null | End date |
| `is_active` | boolean | yes | true | Active policy flag |
| `max_account_risk_per_trade_pct` | numeric | yes | 0.50 | Max risk per trade |
| `max_concurrent_positions` | numeric | yes | 6 | Max open positions |
| `max_portfolio_heat_pct` | numeric | yes | 3.0 | Max total heat |
| `max_sector_concentration_positions` | numeric | yes | 3 | Max positions in one sector/theme |
| `consecutive_losses_pause_threshold` | numeric | yes | 3 | Known rule |
| `consecutive_losses_pause_action` | enum | yes | review_required | Required review before next trade |
| `consecutive_losses_streak_reset` | enum | yes | review_completed | Reset only after review |
| `drawdown_circuit_breaker_enabled` | boolean | yes | false | Optional policy disabled by default |
| `drawdown_pause_threshold_R` | numeric | conditional | null | Required only if enabled |
| `drawdown_pause_action` | enum | conditional | null | Required only if enabled |
| `drawdown_size_reduction_pct` | numeric | conditional | null | Required if action reduce_size |
| `drawdown_recovery_threshold_R` | numeric | conditional | null | Required only if enabled |
| `policy_notes` | text | no | — | Rationale |

### Runtime State

```yaml
risk_policy_runtime_state:
  current_consecutive_loss_count:
    formula: "walk back from most recent closed/reviewed trades until positive realized_R_effective; count negatives"
  consecutive_loss_pause_active:
    formula: "current_consecutive_loss_count >= threshold AND no review_completed after triggering loss"
  current_portfolio_heat_pct:
    formula: "sum(portfolio_heat_contribution_dollars across open trades) / account_equity_now"
  current_open_position_count:
    formula: "count states in [entered, managing, partial_exited]"
  drawdown_pause_active:
    formula: "enabled and current_drawdown_R <= drawdown_pause_threshold_R"
```

---

## 7.9 `Reconciliation_Log`

Weekly reconciliation is required, but post-trade review can occur provisionally before reconciliation.

### Reconciliation_Run

| Field | Type | Required | Description |
|---|---:|---:|---|
| `reconciliation_id` | string | yes | Unique run ID |
| `period_start` | date | yes | Start period |
| `period_end` | date | yes | End period |
| `scheduled_date` | date | yes | Due date |
| `completed_date` | date | yes | Completion date |
| `tos_export_filename` | string | yes | Source CSV |
| `trades_reconciled_count` | numeric | yes | Count |
| `fills_reconciled_count` | numeric | yes | Count |
| `discrepancies_count` | numeric | yes | Count |
| `unresolved_discrepancies_count` | numeric | yes | Count |
| `account_equity_journal` | numeric | yes | Journal equity |
| `account_equity_tos` | numeric | yes | Broker equity |
| `equity_delta_dollars` | numeric | yes | Computed |
| `notes` | text | no | Context |

### Reconciliation_Discrepancy

| Field | Type | Required | Description |
|---|---:|---:|---|
| `discrepancy_id` | string | yes | Unique ID |
| `reconciliation_id` | string | yes | Parent run |
| `trade_id` | string | conditional | Trade discrepancy |
| `fill_id` | string | conditional | Fill discrepancy |
| `field_name` | string | yes | Field that differs |
| `journal_value` | text | yes | Journal value |
| `tos_value` | text | yes | TOS value |
| `delta` | text | conditional | Difference |
| `resolution` | enum | yes | `journal_corrected`, `tos_treated_canonical`, `manual_override`, `unresolved` |
| `resolution_reason` | text | yes | Reason |
| `resolved_date` | date | conditional | Date resolved |
| `mistake_tag_assigned` | string | conditional | Reconciliation mistake tag |
| `material_to_review` | boolean | yes | Whether post-trade review must reopen |

---

## 7.10 `Mistake_Tags`

Mistake tags are required at reviewed state. Use `none_observed` if no mistakes are found.

```yaml
mistake_categories:
  entry:
    - CHASED
    - EARLY_ENTRY
    - LATE_ENTRY
    - NO_SETUP
    - LOW_LIQUIDITY
    - EVENT_IGNORED
  risk:
    - OVERSIZED
    - NO_STOP
    - STOP_TOO_WIDE
    - STOP_TOO_TIGHT
    - CORRELATION_IGNORED
    - GAP_RISK_IGNORED
    - HEAT_OVERAGE
    - CIRCUIT_BREAKER_OVERRIDDEN
  management:
    - MOVED_STOP_AWAY
    - SOLD_TOO_EARLY
    - HELD_AFTER_INVALIDATION
    - FAILED_TO_SCALE
    - ADDED_TO_LOSER
    - MISSED_TIME_STOP
  psychology:
    - FOMO
    - REVENGE
    - BOREDOM
    - EGO
    - ANCHORING
    - CONFIRMATION_BIAS
    - LOSS_AVERSION
    - OVERCONFIDENCE
  reconciliation:
    - SIZE_MISCOUNTED
    - WRONG_TICKER_ENTERED
    - FILL_NOT_LOGGED
    - PARTIAL_NOT_LOGGED
    - STOP_NOT_PLACED
  none:
    - none_observed
```

---

## 7.11 `Review_Log`

Review_Log tracks daily, weekly, monthly, and quarterly reviews.

| Field | Type | Required | Description |
|---|---:|---:|---|
| `review_id` | string | yes | Unique ID |
| `review_type` | enum | yes | `daily`, `weekly`, `monthly`, `quarterly`, `circuit_breaker` |
| `period_start` | date | yes | Start |
| `period_end` | date | yes | End |
| `scheduled_date` | date | yes | Due date |
| `completed_date` | date | conditional | Completion |
| `skipped` | boolean | yes | Compliance flag |
| `duration_minutes` | numeric | conditional | Required if completed |
| `number_of_trades` | numeric | yes | Count |
| `net_R_effective` | numeric | yes | Sum effective R |
| `expectancy_R_effective` | numeric | yes | Average effective R |
| `win_rate` | numeric | yes | Win rate |
| `avg_win_R` | numeric | yes | Positive average |
| `avg_loss_R` | numeric | yes | Natively negative |
| `profit_factor` | numeric | yes | Gross wins / abs(losses) |
| `max_drawdown_R` | numeric | yes | Peak-to-trough |
| `total_mistake_cost_R` | numeric | yes | Harm only |
| `total_lucky_violation_R` | numeric | yes | Separate metric |
| `data_quality_score` | numeric | yes | Completeness |
| `review_compliance_rate` | numeric | yes | Timeliness |
| `reconciliation_compliance_rate` | numeric | yes | Weekly reconcile |
| `primary_lesson` | text | yes | Key lesson |
| `next_period_focus` | text | yes | Focus |

---

## 8. Core Formulas

### 8.1 Planned Risk

```text
risk_per_share = abs(planned_entry - initial_stop)
planned_risk_dollars = account_equity_pre_trade * max_account_risk_pct
planned_position_size = floor(planned_risk_dollars / risk_per_share)
planned_gross_exposure = planned_position_size * planned_entry
```

### 8.2 Initial and Effective Risk

```text
initial_risk_dollars_first_tranche = abs(actual_entry_price_first_fill - initial_stop)
                                     * actual_position_size_at_first_fill
```

```text
max_capital_at_risk_dollars_during_trade = max(raw_current_at_risk_dollars observed while trade open)
```

```text
max_planned_campaign_risk_dollars = maximum total planned risk permitted by setup add_on_rule
```

For non-pyramided trades, `max_capital_at_risk_dollars_during_trade` usually equals or closely approximates `initial_risk_dollars_first_tranche`.

### 8.3 Live Risk and Portfolio Heat

```text
raw_current_at_risk_dollars_long = (current_avg_cost - current_stop) * current_size
portfolio_heat_contribution_dollars = max(0, raw_current_at_risk_dollars)
locked_in_profit_at_stop_dollars = max(0, -raw_current_at_risk_dollars)
portfolio_heat_dollars = sum(portfolio_heat_contribution_dollars across open trades)
portfolio_heat_pct = portfolio_heat_dollars / account_equity_now
```

Negative raw at-risk values must not reduce total portfolio heat.

### 8.4 R Views

```text
realized_R_initial = net_pnl_dollars / initial_risk_dollars_first_tranche
```

```text
realized_R_effective = net_pnl_dollars / max_capital_at_risk_dollars_during_trade
```

```text
realized_R_campaign = net_pnl_dollars / max_planned_campaign_risk_dollars
```

```yaml
R_view_policy:
  primary_dashboard_R: realized_R_effective
  decision_attribution_R: realized_R_initial
  pyramiding_analysis_R: realized_R_campaign
```

### 8.5 P&L

```text
gross_pnl_dollars = sum(exit/trim cash inflows) - sum(entry/add cash outflows)
net_pnl_dollars = gross_pnl_dollars - fees_commissions
```

Before reconciliation, fees may be provisional or estimated. After reconciliation, TOS values are canonical unless manual override is documented.

### 8.6 MFE / MAE Precision Hierarchy

```yaml
mfe_mae_precision_hierarchy:
  intraday_exact:
    preferred_sources:
      - broker_intraday_export
      - reliable_intraday_bar_source
    entry_day_rule: "ignore bars before fill time"
    exit_day_rule: "ignore bars after exit time"
  intraday_estimated:
    sources:
      - yfinance_intraday_when_available
    rule: "best effort with precision flag"
  daily_approximate:
    sources:
      - yfinance_daily_ohlcv
    rule: "use full daily high/low; flag as approximate"
```

For daily approximate long trades:

```text
mfe_dollars = max(highs from entry_date through exit_date) - actual_entry_price
mae_dollars = actual_entry_price - min(lows from entry_date through exit_date)
MFE_R = mfe_dollars / risk_per_share
MAE_R = mae_dollars / risk_per_share
```

For shorts, high/low roles swap. Current v1.2 scope is long-only, but formulas should be direction-ready.

### 8.7 Capture Ratio

```text
capture_ratio = realized_R_effective / MFE_R only when realized_R_effective > 0 and MFE_R > 0
capture_ratio = n/a otherwise
```

### 8.8 Mistake Cost and Lucky Violation

```text
mistake_cost_R = max(0, realized_R_if_plan_followed - actual_realized_R_effective)
lucky_violation_R = max(0, actual_realized_R_effective - realized_R_if_plan_followed)
```

They are never netted.

### 8.9 Expectancy

```text
expectancy_R_effective = mean(realized_R_effective over closed/reviewed trades)
profit_factor = sum(realized_R_effective where > 0) / abs(sum(realized_R_effective where < 0))
avg_loss_R = mean(realized_R_effective where < 0)  # natively negative
expectancy_decomposed = (win_rate * avg_win_R) + (loss_rate * avg_loss_R)
```

---

## 9. Scoring Models

## 9.1 Pre-Trade Gate vs. Quality Score

The pre-trade gate is binary. The quality score is ordinal.

```yaml
pre_trade_gate:
  purpose: "block unsafe or incomplete trades"
  component_values: [pass, fail]
  fail_action: "block trade approval"

pre_trade_quality_score:
  purpose: "measure setup quality and calibrate judgment"
  component_values: [0, 0.5, 1]
  total_score_range: "0 to 10"
```

### 9.1.1 Gate Components

```yaml
pre_trade_gate_required_checks:
  - setup_exists_or_exception_logged
  - trade_origin_valid
  - parent_watchlist_id_present_when_required
  - thesis_specific
  - why_now_specific
  - invalidation_condition_exists
  - structured_premortem_complete
  - planned_entry_present
  - initial_stop_present
  - risk_per_share_positive
  - planned_position_size_calculated
  - planned_risk_within_policy
  - event_risk_handled
  - gap_risk_handled
  - emotional_state_logged
  - no_active_consecutive_loss_pause
  - max_open_positions_not_exceeded
  - portfolio_heat_limit_not_exceeded
```

### 9.1.2 Quality Score Components

| Component | Points | Scoring |
|---|---:|---|
| Valid setup from active/pilot playbook | 2 | 0, 1, or 2 |
| Market regime supportive | 1 | 0, 0.5, 1 |
| Sector/theme supportive | 1 | 0, 0.5, 1 |
| Clear catalyst or technical reason | 1 | 0, 0.5, 1 |
| Precise entry trigger | 1 | 0, 0.5, 1 |
| Valid initial stop | 1 | 0, 0.5, 1 |
| Acceptable reward/risk | 1 | 0, 0.5, 1 |
| Correct position size | 1 | 0, 0.5, 1 |
| Emotional state acceptable | 1 | 0, 0.5, 1 |

```yaml
pre_trade_quality_score_policy:
  score_8_to_10:
    action: "full planned risk allowed, subject to Risk_Policy"
  score_6_to_7_5:
    action: "reduce size to 50% or wait for confirmation"
  score_below_6:
    action: "reject or wait"
```

---

## 9.2 Process Grade

v1.2 uses stage grades, weighted aggregation, and disqualifying floors.

```yaml
stage_grade_numeric_map:
  A: 4
  B: 3
  C: 2
  D: 1
  F: 0

weights:
  entry_grade: 0.40
  management_grade: 0.35
  exit_grade: 0.25

process_grade_rule:
  if_any_stage_F: F
  if_disqualifying_process_violation: "maximum grade D"
  otherwise: "weighted average mapped to grade"

numeric_to_grade:
  A: ">= 3.50"
  B: "2.75 to 3.49"
  C: "2.00 to 2.74"
  D: "1.00 to 1.99"
  F: "< 1.00"
```

Examples of disqualifying process violations:

```yaml
disqualifying_process_violations:
  - no_stop
  - oversized_beyond_policy
  - no_valid_setup
  - revenge_trade
  - circuit_breaker_override
  - held_after_invalidation_without_rule_basis
  - moved_stop_away_materially_increasing_risk
```

---

## 9.3 Process / Outcome Matrix

```yaml
process_outcome_matrix:
  followed_plan_and_won: disciplined_win
  followed_plan_and_lost: disciplined_loss
  violated_plan_and_won: lucky_violation
  violated_plan_and_lost: execution_loss
```

Profitable violations populate `lucky_violation_R`, not negative mistake cost.

---

## 9.4 Self-Score Calibration

Calibrate self-scoring primarily against process metrics, secondarily against outcomes.

```yaml
self_score_calibration:
  primary_targets:
    - process_grade
    - setup_validity_after_review
    - mistake_rate
    - rule_followed_boolean
  secondary_targets:
    - realized_R_effective
    - MFE_R
    - MAE_R
  warning_condition:
    - "quality score has low relationship to process_grade over rolling 50 trades"
    - "high score trades show high mistake rate"
  non_warning_condition:
    - "quality score has low realized_R correlation but strong process correlation"
```

---

## 10. AI Evaluation Rules

## 10.1 Pre-Trade Gate

```yaml
workflow_pre_trade_gate:
  input_state: planned
  hard_block_conditions:
    - missing_required_planned_fields
    - missing_stop_or_invalidation
    - risk_per_share <= 0
    - planned_risk_dollars > Risk_Policy.max_account_risk_per_trade_pct
    - current_open_position_count >= max_concurrent_positions
    - portfolio_heat_pct_after_trade > max_portfolio_heat_pct
    - consecutive_loss_pause_active == true
    - parent_watchlist_id_missing_when_required
  soft_warning_conditions:
    - trade_origin_detail_required_due_to_no_watchlist
    - market_regime_transition_unclear
    - stop_type_discretionary
    - quality_score_between_6_and_7_5
    - MFE_MAE_data_source_expected_daily_approximate
  output:
    - APPROVE
    - REDUCE_SIZE
    - WAIT
    - REJECT
    - MISSING_FIELDS
    - POLICY_BLOCK_REASON
```

## 10.2 Pre-Trade Lock

```yaml
workflow_pre_trade_lock:
  trigger: "first Fill with action=entry"
  actions:
    - write pre_trade_locked_at
    - mark manual_pre_trade fields read_only
    - compute initial_risk_dollars_first_tranche
    - transition state to entered
  override:
    allowed: true
    requires: Pre_Trade_Edit_Audit row
```

## 10.3 In-Trade Review

```yaml
workflow_in_trade_review:
  input_state: [managing, partial_exited]
  steps:
    - update current price from available market data
    - recompute current_avg_cost, current_size, raw_current_at_risk, portfolio_heat_contribution
    - classify thesis_status
    - decide daily_snapshot_vs_event_log
    - detect stop movement and rule compliance
    - check time stop
    - check MFE_to_date_R and planned partial rules
  output:
    - management_record
    - rule_violation_flags
    - recommended_action_if_any
```

## 10.4 Post-Trade Review

```yaml
workflow_post_trade_review:
  input_state: closed
  reconciliation_requirement: "not required for provisional review"
  steps:
    - compute provisional net_pnl and R views from Fills
    - compute MFE_R and MAE_R using best available precision level
    - assign thesis_accuracy
    - assign setup_validity_after_review
    - assign entry_management_exit_grades
    - compute process_grade
    - assign mistake_tags or none_observed
    - compute mistake_cost_R and lucky_violation_R where valid
    - produce lesson_learned
    - set post_trade_review_status = provisional if unreconciled else final_reconciled
    - transition state to reviewed
```

## 10.5 Reconciliation Workflow

```yaml
workflow_weekly_reconciliation:
  inputs:
    - tos_export_csv
    - period_start
    - period_end
  steps:
    - import TOS CSV
    - match fills by ticker, action, datetime, quantity, and price tolerance
    - flag unmatched broker fills
    - flag unmatched journal fills
    - compute field deltas
    - create discrepancy records
    - resolve discrepancies or mark unresolved
    - update reconciliation_status on Fills and Trade_Log
    - assign reconciliation mistake tags where applicable
    - reopen reviewed trades if discrepancy is material_to_review
    - finalize provisional reviews when no material discrepancy remains
```

## 10.6 Consecutive-Loss Pause

```yaml
workflow_consecutive_loss_pause:
  trigger: "current_consecutive_loss_count >= 3"
  action: "block new trade approval"
  required_resolution: "create Review_Log row with review_type=circuit_breaker"
  reset_condition: "review_completed"
  note: "winning trade alone does not clear required review"
```

---

## 11. Dashboard Requirements

### 11.1 Core Metrics

```yaml
dashboard_core_metrics:
  performance:
    - total_closed_trades
    - net_R_effective
    - expectancy_R_effective
    - win_rate
    - avg_win_R
    - avg_loss_R
    - profit_factor
    - median_R
    - max_drawdown_R
    - best_trade_R
    - worst_trade_R
    - average_holding_period_days
  R_views:
    - net_R_initial
    - net_R_effective
    - net_R_campaign
  process_quality:
    - percent_trades_following_plan
    - mistake_count_total
    - mistake_cost_R_total
    - lucky_violation_R_total
    - process_grade_distribution
    - disqualifying_violation_count
  risk_state:
    - current_open_position_count
    - portfolio_heat_pct
    - current_consecutive_loss_count
    - consecutive_loss_pause_active
    - drawdown_pause_active_if_enabled
  data_quality:
    - data_quality_score_period
    - review_compliance_rate_period
    - reconciliation_compliance_rate_period
    - unreconciled_trade_count
    - unresolved_discrepancy_count
  precision:
    - percent_MFE_MAE_intraday_exact
    - percent_MFE_MAE_intraday_estimated
    - percent_MFE_MAE_daily_approximate
```

### 11.2 Required Breakdowns

```yaml
dashboard_breakdowns:
  by_setup_id:
    - expectancy_R_effective
    - sample_size
    - mistake_rate
  by_setup_family:
    - expectancy_R_effective
    - sample_size
  by_trade_origin:
    - expectancy_R_effective
    - sample_size
    - process_grade_distribution
  by_source_screen:
    - expectancy_R_effective
    - watchlist_to_trade_conversion_rate
  by_time_on_watchlist:
    - bucket_0_to_2_days
    - bucket_3_to_7_days
    - bucket_8_to_21_days
    - bucket_22_plus_days
  by_market_regime:
    - net_R_effective
    - drawdown_R
  by_entry_trigger_type:
    - expectancy_R_effective
    - stop_hit_rate
  by_exit_reason:
    - expectancy_R_effective
    - capture_ratio
  by_emotional_state_pre_trade:
    - mistake_rate
    - process_grade_distribution
    - expectancy_R_effective
  by_MFE_MAE_precision_level:
    - average_MFE_R
    - average_MAE_R
    - caveat_flag
```

### 11.3 Interpretation Rules

```yaml
interpretation_rules:
  positive_edge_candidate:
    condition: "expectancy_R_effective > 0 with sample_size >= 20 and acceptable drawdown"
  process_leak_candidate:
    condition: "positive expectancy setup but high mistake_cost_R or low plan-follow rate"
  setup_retirement_candidate:
    condition: "negative expectancy over sample_size >= 30 with no regime explanation"
  source_screen_actionable:
    condition: "screen sample_size >= 15 trades and expectancy materially differs from portfolio average"
  exit_problem_candidate:
    condition: "high MFE_R but low capture_ratio"
  stop_problem_candidate:
    condition: "high MAE_R or stop_hit before thesis failure repeatedly"
  score_calibration_warning:
    condition: "pre_trade_quality_score has weak relationship to process targets, not merely weak realized_R correlation"
```

---

## 12. Review and Reconciliation Cadence

```yaml
daily_review:
  purpose: "open-trade management"
  required_actions:
    - update/confirm stops
    - classify thesis_status
    - create daily_snapshot_or_event_log
    - review portfolio heat

weekly_review:
  purpose: "performance, reconciliation, and behavioral feedback"
  required_actions:
    - perform TOS CSV reconciliation
    - resolve discrepancies or log unresolved
    - review provisional and final closed trades
    - update mistake cost and lucky violation totals
    - review missed trades if available
    - set next week focus

monthly_review:
  purpose: "setup, regime, and behavior analysis"
  required_actions:
    - evaluate expectancy by setup and origin
    - review process grade distribution
    - review rule change candidates
    - evaluate score calibration against process metrics

quarterly_review:
  purpose: "strategy fit and policy review"
  required_actions:
    - keep/pause/retire setups
    - review position sizing policy
    - decide whether to enable optional drawdown breaker
    - review data quality and reconciliation compliance
```

---

## 13. Implementation Order for Python Tool

```yaml
stage_1_schema_and_state_machine:
  build:
    - database models or dataframe schemas
    - controlled vocabularies
    - state machine
    - trade_origin conditional fields
    - Screen_Definitions
  acceptance:
    - state transitions validate required fields
    - parent_watchlist_id is conditional not universal

stage_2_risk_and_pre_trade_gate:
  build:
    - Risk_Policy
    - position sizing formulas
    - portfolio heat contribution logic
    - consecutive-loss pause
    - pre_trade_quality_score
  acceptance:
    - blocked trades return explicit reasons
    - negative raw risk does not reduce portfolio heat

stage_3_fills_and_pre_trade_lock:
  build:
    - Fills model
    - derived Trade_Log execution fields
    - pre_trade_locked_at
    - Pre_Trade_Edit_Audit
  acceptance:
    - first fill locks pre-trade fields
    - edits after lock require audit row

stage_4_daily_management_and_market_data:
  build:
    - Daily_Management daily_snapshot/event_log
    - yfinance data integration
    - MFE_MAE precision hierarchy
  acceptance:
    - daily approximate MFE/MAE has precision flag
    - event logs required for stop/action/thesis changes

stage_5_post_trade_review:
  build:
    - provisional review workflow
    - stage grading
    - process grade weighted model
    - mistake tags
    - mistake_cost/lucky_violation logic
  acceptance:
    - review can complete provisionally before reconciliation
    - material reconciliation discrepancy can reopen review

stage_6_reconciliation:
  build:
    - TOS CSV parser
    - fill matching
    - discrepancy records
    - reconciliation status updates
  acceptance:
    - weekly run produces reconciliation summary
    - unmatched fills assign appropriate tags

stage_7_dashboard_and_reviews:
  build:
    - performance dashboard
    - process dashboard
    - review logs
    - source/screen analytics
  acceptance:
    - dashboard segments by setup, origin, regime, and screen
    - calibration uses process-first targets
```

---

## 14. Orchestrator Sub-Agent Briefs

```yaml
schema_agent:
  objective: "Create canonical data models and migrations"
  deliverables:
    - entity schemas
    - enum registry
    - required-field-by-state map
    - conditional-field rules

validation_agent:
  objective: "Implement gates and state transitions"
  deliverables:
    - pre_trade_gate
    - state_transition_validator
    - consecutive_loss_pause_gate
    - pre_trade_lock_validator

risk_agent:
  objective: "Implement position sizing and heat logic"
  deliverables:
    - planned risk formulas
    - raw_current_at_risk
    - portfolio_heat_contribution
    - R_views

market_data_agent:
  objective: "Fetch and classify market data precision"
  deliverables:
    - yfinance adapter
    - MFE_MAE calculator
    - precision flags
    - stale data handling

reconciliation_agent:
  objective: "Reconcile journal fills against TOS CSV"
  deliverables:
    - TOS CSV parser
    - fuzzy fill matcher
    - discrepancy logger
    - review reopen/finalize logic

scoring_agent:
  objective: "Implement scoring and behavioral analysis"
  deliverables:
    - pre_trade_quality_score
    - process_grade
    - mistake_cost_R
    - lucky_violation_R
    - self-score calibration metrics

dashboard_agent:
  objective: "Build analytics surfaces"
  deliverables:
    - core performance metrics
    - process quality metrics
    - R view summaries
    - source/screen breakdowns
    - review and reconciliation compliance
```

---

## 15. Acceptance Criteria

```yaml
acceptance_criteria:
  trade_lifecycle:
    - trade cannot enter invalid state transition
    - state-specific required fields are enforced
  provenance:
    - trade_origin is always populated
    - parent_watchlist_id is required only when applicable
  pre_trade_integrity:
    - pre_trade_locked_at is written on first fill
    - post-lock edit creates audit row
  risk:
    - position size computes from risk
    - portfolio heat uses nonnegative heat contribution
    - consecutive loss pause blocks new trades until review completed
  review:
    - closed trade can be reviewed provisionally before reconciliation
    - final numeric status requires reconciliation or manual override
  reconciliation:
    - TOS CSV import creates reconciliation run
    - unmatched fills create discrepancy records
    - material discrepancies reopen provisional/final reviews as needed
  analytics:
    - dashboard reports realized_R_initial, realized_R_effective, and realized_R_campaign when available
    - dashboard segments by setup, trade_origin, market_regime, source_screen, and emotional_state
    - quality score calibration prioritizes process metrics
```

---

## 16. Failure Modes and Preventive Controls

```yaml
failure_modes:
  hindsight_rewrite:
    prevention: "pre_trade_locked_at plus Pre_Trade_Edit_Audit"
  over_gating_legitimate_trades:
    prevention: "trade_origin required; parent_watchlist_id conditional"
  selective_journaling:
    prevention: "weekly TOS reconciliation and FILL_NOT_LOGGED tags"
  negative_risk_offsetting_portfolio_heat:
    prevention: "portfolio_heat_contribution_dollars = max(0, raw risk)"
  delayed_review_memory_decay:
    prevention: "provisional review allowed before reconciliation"
  noisy_outcome_calibration:
    prevention: "quality score calibrated primarily to process metrics"
  pyramiding_R_distortion:
    prevention: "multiple R views"
  daily_management_friction:
    prevention: "daily_snapshot vs event_log distinction"
  drawdown_policy_overreach:
    prevention: "drawdown breaker disabled by default until explicitly enabled"
  lucky_violation_reinforcement:
    prevention: "lucky_violation_R reported separately and never netted"
```

---

## 17. Example AI Prompts for Tool Operation

### 17.1 Proposed Trade Evaluation

```text
Evaluate this proposed trade under v1.2.
Run the binary pre-trade gate, calculate planned position size, calculate pre_trade_quality_score with partial-credit scoring, check Risk_Policy including consecutive-loss pause, and output APPROVE, REDUCE_SIZE, WAIT, or REJECT.
Explain hard blocks separately from soft warnings.
```

### 17.2 Open Trade Review

```text
Review this open trade under v1.2.
Classify thesis_status, compute current risk and portfolio heat contribution, decide whether the record is daily_snapshot or event_log, flag management rule violations, and recommend action if the plan requires one.
```

### 17.3 Closed Trade Review

```text
Review this closed trade provisionally under v1.2.
Compute R views, MFE/MAE with precision flag, stage grades, process grade, mistake tags, mistake_cost_R, lucky_violation_R, and lesson_learned.
Set post_trade_review_status to provisional unless reconciliation is already final.
```

### 17.4 Weekly Reconciliation

```text
Reconcile this week's TOS CSV against journal Fills.
Create a Reconciliation_Run, discrepancy rows, update reconciliation_status, assign reconciliation mistake tags, and reopen any reviewed trade where the discrepancy is material to review conclusions.
```

---

## 18. Changelog from v1.1

```yaml
v1_2_changes_from_v1_1:
  provenance:
    - added trade_origin enum
    - changed parent_watchlist_id from universal required to conditional
  screen_workflow:
    - added Screen_Definitions table
    - changed screen criteria capture from repeated manual field to versioned reference plus materialized snapshot
  premortem:
    - changed minimum 3 freeform reasons to structured technical / market-sector / execution-behavior reasons
  process_grade:
    - changed worst-of-three to weighted stage grades with disqualifying floors
  quality_score:
    - kept binary pre-trade gate
    - changed quality score to partial-credit 0/0.5/1 components
  review_reconciliation:
    - added provisional post-trade review status
    - allowed process review before reconciliation
    - final numeric status still depends on reconciliation or manual override
  current_risk:
    - split raw_current_at_risk from portfolio_heat_contribution
    - added locked_in_profit_at_stop
  pyramiding:
    - added realized_R_initial, realized_R_effective, realized_R_campaign
    - set realized_R_effective as primary dashboard R
  MFE_MAE:
    - changed yfinance daily from canonical to fallback approximate
    - added precision hierarchy and precision flag
  risk_policy:
    - retained 3-loss pause as hard rule
    - made drawdown circuit breaker optional and disabled by default
    - required review_completed to reset pause
  self_score_calibration:
    - changed primary calibration targets from realized_R to process metrics
```

---

## 19. Final Implementation Principle

The v1.2 tool should make unsafe behavior difficult and reflective behavior easy.

```yaml
final_principle:
  enforce:
    - decision_integrity
    - capital_risk_controls
    - state_completeness
    - reconciliation_eventual_truth
  measure:
    - setup_edge
    - behavioral_patterns
    - screen_quality
    - watchlist_quality
    - execution_drift
  allow_provisionally:
    - timely_review_before_reconciliation
    - approximate_market_data_before_precision_available
    - legitimate_non_watchlist_trade_origins
```

*End of v1.2 specification.*
