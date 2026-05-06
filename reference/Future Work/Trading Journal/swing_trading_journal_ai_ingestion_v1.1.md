---
title: "AI-Ready Swing Trading Journal Layout Research and Execution Specification"
version: "1.1"
prior_version: "1.0"
document_type: "research_to_execution_spec"
created_for: "AI evaluation, planning, and execution"
created_date: "2026-04-30"
revised_date: "2026-05-01"
timezone_context: "Pacific/Honolulu"
intended_use:
  - evaluate_existing_trading_journal
  - design_new_swing_trading_journal
  - plan_python_tool_implementation
  - execute_pre_trade_in_trade_post_trade_review_workflows
  - generate_metrics_and_process_feedback
  - drive_claude_code_implementation_briefs
not_financial_advice: true
primary_design_goal: "Capture decision quality before outcome knowledge, normalize performance by initial risk, and make behavioral / process errors measurable and operationally enforceable."
changes_from_v1_0_summary: "Added trade lifecycle state machine, controlled vocabularies, source/latency taxonomy, Watchlist as required tab, Risk_Policy entity with circuit breakers, Reconciliation_Log entity, Daily_Screener_Log entity, pre-trade immutability semantics, MFE/MAE measurement convention, two-tier Daily_Management records, mistake_cost / lucky_violation split, current_at_risk_R distinct from initial_risk_R, and consistency cleanup across enums and overlapping fields. Removed options, multi-account, and paper-trading language. See §21 for full changelog."
---

# AI-Ready Swing Trading Journal Layout Research and Execution Specification (v1.1)

## 0. Operating Instruction for AI Systems

Use this document as a structured specification for designing, evaluating, or
operating a swing trading journal.

The AI should prioritize the following objectives in order:

1. **Preserve pre-trade decision integrity.** Record the thesis, invalidation
   point, risk, planned management, and emotional state before the outcome
   is known. Pre-trade fields are write-locked once the first fill is
   recorded; subsequent edits require an audit trail.
2. **Normalize all trade outcomes in R-multiples.** Dollars alone are
   insufficient because position size varies. The R-multiple denominator is
   `initial_risk_dollars`, which is itself fixed at first fill.
3. **Distinguish initial risk from current at-risk capital.** `initial_risk`
   is the immutable denominator for outcome math. `current_at_risk` is a
   live metric for portfolio heat and management decisions. They are not
   the same number after the first stop adjustment.
4. **Separate process quality from outcome quality.** A profitable rule
   violation is still a process failure; a losing trade can still be a good
   decision. `mistake_cost_R` and `lucky_violation_R` are tracked separately
   and never net against each other.
5. **Measure behavioral leakage.** Mistakes are tagged from a controlled
   vocabulary, counted, and converted to R-cost where the counterfactual is
   measurable.
6. **Connect every trade to a defined setup *and* a defined screen of
   origin.** The system evaluates expectancy by setup, regime, sector,
   catalyst, entry trigger type, exit reason, and source screen.
7. **Enforce account-level circuit breakers operationally.** Consecutive-loss
   and drawdown thresholds gate the pre-trade approval flow; they are not
   merely dashboard metrics.
8. **Reconcile manual journal data against broker exports weekly.**
   Manual fields are flagged with `reconciliation_status` until validated
   against ToS CSV.
9. **Support execution, review, and iteration.** The journal produces daily,
   weekly (combined with reconciliation), monthly, and quarterly decision
   outputs.

Recommended output style for AI using this document:

```yaml
ai_response_mode:
  when_evaluating_a_journal: "score_against_required_fields_quality_gates_and_state_machine"
  when_designing_a_journal: "produce_schema_tabs_fields_formulas_workflows_and_state_transitions"
  when_reviewing_trades: "grade_process_separately_from_pnl_and_distinguish_mistakes_from_lucky_violations"
  when_planning_improvements: "prioritize_high_R_cost_errors_and_low_expectancy_setups_subject_to_sample_size_thresholds"
  when_generating_implementation_briefs: "anchor_briefs_to_state_machine_states_and_source_taxonomy"
```

---

## 1. Research-Informed Design Thesis

An effective swing trading journal is not merely a trade ledger. It is a
**decision-quality measurement system with operational enforcement**.

Swing trades typically last days to weeks, so the journal must capture:

- overnight risk
- changing market regime
- changing sector conditions
- thesis decay or confirmation
- partial exits and stop movement (with full history)
- risk normalization and live at-risk capital
- psychological state including streak and drawdown context
- process adherence
- post-trade pattern recognition
- reconciliation against broker truth

The journal must answer four core questions:

```text
1. Did the trader have a valid, predefined edge?
2. Was the trade sized and executed according to plan?
3. Was the trade managed according to objective evidence rather than emotion?
4. Did the result reveal an edge, a weakness, random variance, or behavioral
   leakage?
```

A fifth question is added in v1.1 because operational enforcement is now
a first-class concern:

```text
5. Was the trader allowed to take this trade given current account state
   (open positions, recent loss streak, drawdown, halt rules)?
```

---

## 2. Evidence Map

The following research and practitioner concepts inform the journal structure.

| Source / Concept | Journal Design Implication | Implementation Requirement |
|---|---|---|
| Decision journaling / Kahneman-style decision capture | Capture beliefs, expectations, and reasoning before outcome knowledge changes memory | Mandatory `pre_trade_thesis`, `expected_scenario`, `invalidation_condition`, `premortem`; pre-trade lock on first fill |
| Gary Klein premortem | Imagine the trade failed before entry to surface hidden risks | Mandatory `premortem_failure_reasons` field, minimum 3 reasons |
| Van Tharp R-multiple framework | Normalize wins / losses by initial risk rather than dollars | Mandatory `initial_risk_dollars`, `realized_R`, `MFE_R`, `MAE_R`; `initial_risk_dollars` is immutable post first fill |
| Van Tharp expectancy framework | Evaluate systems as distributions of R outcomes | Dashboard calculates `expectancy_R` and setup-level expectancy with sample-size guards |
| Behavioral finance / CFA bias framework | Biases such as loss aversion, anchoring, confirmation bias, and overconfidence distort decisions | Mandatory emotion and mistake tags; mistake tags are required-with-`none_observed`-default |
| Barber & Odean overtrading research | Excessive trading can reduce net returns, especially under overconfidence | Track `trade_frequency`, `revenge_trade`, `no_setup`, and `overtrading_periods`; circuit breakers gate new trades |
| Swing trading risk characteristics | Overnight holds create gap risk and regime-change risk | Structured `event_risk_*` fields, structured `gap_risk_plan_*` fields |
| Practitioner setup systems (CANSLIM, Minervini, Qullamaggie, Weinstein, Darvas, Morales & Kacher) | Trades must reference codeable setups, triggers, invalidation points, and management rules | Mandatory `setup_id`, `entry_trigger_type`, `stop_type`, `exit_rule`, `market_regime`; controlled vocabularies for each |
| Forensic / audit-trail principle | Hindsight rewriting corrupts decision-quality measurement | `pre_trade_locked_at` timestamp; `Pre_Trade_Edit_Audit` log for any post-lock changes |
| Reconciliation discipline (general accounting practice) | Manual records drift from broker truth | Weekly reconciliation against ToS CSV; `Reconciliation_Log` entity; `reconciliation_status` field |

---

## 3. Scope and Constraints (NEW in v1.1)

This section makes implementation context explicit so v1.1 can drop options,
multi-account, and paper-trading language that v1.0 carried as
defensive optionality.

```yaml
scope_in:
  trading_mode: live
  account_count: 1
  instrument_scope: stock_only
  primary_holding_horizon: "days to weeks"
  intended_setups: "momentum / trend continuation / breakout (Minervini-aligned)"
  position_count_cap: 6

scope_out:
  options_in_scope: false
  futures_in_scope: false
  forex_in_scope: false
  crypto_in_scope: false
  paper_trading_in_scope: false
  multi_account_in_scope: false
  intraday_day_trading_in_scope: false

implementation_target:
  runtime: "python_based_swing_trading_tool"
  ai_consumer: "claude_code_orchestrator"
  detailed_implementation_choice: deferred_to_implementation_phase

data_sources:
  broker: thinkorswim
  broker_export: "TOS CSV"
  broker_export_cadence: weekly
  primary_screener: finviz
  screener_export: csv
  market_data: yfinance
  market_data_granularity: "daily OHLCV canonical; intraday best-effort within yfinance lookback"
```

---

## 4. System Architecture

```yaml
journal_architecture:
  required_tabs:
    - Setup_Playbook
    - Trade_Log
    - Fills
    - Daily_Management
    - Watchlist
    - Daily_Screener_Log
    - Risk_Policy
    - Reconciliation_Log
    - Mistake_Tags
    - Review_Log
    - Rule_Change_Queue
    - Dashboard
  recommended_tabs:
    - Screenshots
    - Missed_Trades
    - Pre_Trade_Edit_Audit
  optional_advanced_tabs:
    - Market_Regime_Log
    - Sector_Theme_Log
    - Backtest_Comparison
    - Stop_History_View
```

Several tabs that were "strongly recommended" or "optional" in v1.0 are
required in v1.1 because the findings established their operational role:

- **Watchlist** — required because `time_on_watchlist_days` is a documented
  predictive signal and because Finviz workflow naturally produces watchlist
  events before trade entry.
- **Daily_Screener_Log** — required to capture `source_screen` at time of
  ticker discovery, since Finviz CSV export does not embed the screen
  definition.
- **Risk_Policy** — required to encode account-level limits and circuit
  breakers operationally rather than as dashboard analytics.
- **Reconciliation_Log** — required to track weekly reconciliation events
  and discrepancies between manual journal and ToS CSV.

Minimum viable journal (v1.1):

```yaml
minimum_viable_journal:
  must_have_tables:
    - Setup_Playbook
    - Trade_Log
    - Fills
    - Risk_Policy
    - Daily_Screener_Log
    - Watchlist
  must_have_fields_on_trade_log:
    - trade_id
    - parent_watchlist_id
    - parent_trade_id      # null unless re-entry
    - state                # see §6 state machine
    - setup_id
    - direction            # long only in v1.1 by scope
    - planned_entry
    - actual_entry_price   # null until first fill
    - initial_stop
    - position_size
    - initial_risk_dollars # locked at first fill
    - thesis
    - invalidation_condition
    - premortem_failure_reasons  # min 3
    - planned_exit_strategy
    - actual_exit_avg      # null until exit
    - exit_reason
    - realized_R           # null until exit
    - process_grade        # null until review
    - mistake_tags         # required, default 'none_observed'
    - reconciliation_status
    - pre_trade_locked_at
```

---

## 5. Entity Relationship Model

```yaml
entities:
  Setup:
    primary_key: setup_id
    relationship: "one setup maps to many trades"

  Daily_Screener_Run:
    primary_key: screener_run_id
    fields_summary: ["screen_name", "screen_criteria_snapshot", "run_date"]
    relationship: "one run produces many ticker entries"

  Watchlist_Entry:
    primary_key: watchlist_entry_id
    foreign_keys: [screener_run_id]
    fields_summary: ["ticker", "added_date", "source_screen"]
    relationship: "one watchlist entry can produce zero or one (or more, on re-entry) trades"

  Trade:
    primary_key: trade_id
    foreign_keys:
      - setup_id
      - parent_watchlist_id   # required for traceability
      - parent_trade_id       # nullable; set if re-entry
    relationship: "one trade has many fills, many management records, many screenshots, optionally many reconciliation entries"

  Fill:
    primary_key: fill_id
    foreign_keys: [trade_id]
    relationship: "many fills belong to one trade; Fills is the source of truth for execution data"

  Daily_Management_Record:
    primary_key: management_record_id
    foreign_keys: [trade_id]
    relationship: "many records belong to one open trade"
    record_type_enum: [daily_snapshot, event_log]

  Pre_Trade_Edit_Audit:
    primary_key: audit_id
    foreign_keys: [trade_id]
    relationship: "every edit to pre-trade fields after pre_trade_locked_at creates one row"

  Reconciliation_Run:
    primary_key: reconciliation_id
    relationship: "one weekly run produces many discrepancy records"

  Reconciliation_Discrepancy:
    primary_key: discrepancy_id
    foreign_keys: [reconciliation_id, trade_id, fill_id]

  Risk_Policy:
    primary_key: policy_id
    relationship: "one active policy at a time; historical policies retained for audit"

  Screenshot:
    primary_key: screenshot_id
    foreign_keys: [trade_id, setup_id]

  Mistake_Tag:
    primary_key: mistake_tag
    relationship: "many trades can have many mistake tags"

  Review_Record:
    primary_key: review_id
    relationship: "weekly / monthly / quarterly reviews aggregate trades and reconciliation events"

  Rule_Change_Candidate:
    primary_key: rule_change_id
    relationship: "rule changes must cite evidence from multiple trades"
```

---

## 6. Trade Lifecycle State Machine (NEW in v1.1)

Every trade has a `state` field. Required-set, validation rules, and AI gate
behavior are all keyed on state. This addresses M1 (implicit state) and
provides the foundation for deterministic AI evaluation.

```yaml
trade_states:
  - planned          # idea exists; entry not yet triggered
  - triggered        # entry condition met but no fill yet recorded
  - entered          # first fill recorded; pre-trade fields now locked
  - managing         # one or more fills, no exit fills yet
  - partial_exited   # at least one trim or partial exit recorded
  - closed           # net position is flat (all units exited)
  - reviewed         # closed + post-trade review complete
  - canceled         # never entered; idea abandoned

allowed_transitions:
  planned: [triggered, canceled]
  triggered: [entered, canceled]
  entered: [managing]                      # automatic immediately after first fill
  managing: [partial_exited, closed]
  partial_exited: [managing, closed]       # can trim, then ride remaining; or exit fully
  closed: [reviewed]
  reviewed: []                             # terminal
  canceled: []                             # terminal
```

Required-field set per state:

```yaml
required_fields_by_state:
  planned:
    - setup_id
    - parent_watchlist_id
    - direction
    - thesis
    - why_now
    - invalidation_condition
    - premortem_failure_reasons   # min 3
    - planned_entry
    - initial_stop
    - planned_position_size
    - planned_risk_dollars
    - market_regime
    - event_risk_present
    - event_handling
    - gap_risk_present
    - gap_risk_handling
    - emotional_state_pre_trade
    - pre_trade_quality_score
    - final_pre_trade_decision

  triggered:
    inherits_from: planned
    additional: [trigger_observed_datetime]

  entered:
    inherits_from: triggered
    additional:
      - actual_entry_date         # derived from Fills first entry fill
      - actual_entry_price        # derived from Fills first entry fill
      - actual_position_size      # derived from Fills aggregate of entry/add fills
      - initial_risk_dollars      # locked here, never changes
      - pre_trade_locked_at       # timestamp written here, never overwritten
      - entry_trigger_type
      - entry_trigger_followed
      - manual_entry_confidence
      - reconciliation_status

  managing:
    inherits_from: entered
    additional_per_review:
      - daily_management_records  # one per review_date

  partial_exited:
    inherits_from: managing
    additional: []  # state change recorded via Fills with action=trim or exit

  closed:
    inherits_from: managing
    additional:
      - exit_date
      - exit_price_avg            # derived from Fills
      - exit_reason
      - planned_exit_followed
      - gross_pnl_dollars
      - net_pnl_dollars
      - realized_R
      - MFE_R
      - MAE_R
      - capture_ratio             # null if MFE_R<=0 or realized_R<=0
      - holding_period_days

  reviewed:
    inherits_from: closed
    additional:
      - thesis_accuracy
      - setup_validity_after_review
      - process_grade
      - entry_grade
      - management_grade
      - exit_grade
      - mistake_tags              # required; 'none_observed' acceptable
      - mistake_cost_R            # >=0
      - lucky_violation_R         # >=0
      - lesson_learned
      - rule_change_candidate
      - rule_change_id            # required if rule_change_candidate=true
      - reviewed_at
```

State transitions are AI-checkable. The pre-trade gate (§12.1), in-trade
gate (§12.2), and post-trade gate (§12.3) operate on the state field.
A trade cannot advance state if its state-specific required fields are
missing or fail validation.

---

## 7. Field Source and Latency Taxonomy (NEW in v1.1)

Every field carries a `source` and an `availability_latency` annotation.
This drives:

- AI trust decisions (does this number need re-pull / reconciliation?)
- Implementation effort estimation (manual vs. automatable)
- Reconciliation logic (which fields are subject to weekly reconcile)

```yaml
source_categories:
  manual_pre_trade:
    description: "trader enters at planning time, before entry fill"
    examples: [thesis, why_now, invalidation_condition, premortem_failure_reasons,
               planned_entry, initial_stop, emotional_state_pre_trade,
               pre_trade_quality_score, final_pre_trade_decision]
    immutable_after: pre_trade_locked_at

  manual_in_trade:
    description: "trader enters during open-trade reviews or on management events"
    examples: [thesis_status, action_taken, action_reason,
               emotional_state, market_regime_change, sector_condition_change,
               news_or_event_update]
    mutable: true

  manual_post_trade:
    description: "trader enters during post-trade review"
    examples: [thesis_accuracy, setup_validity_after_review, process_grade,
               mistake_tags, lesson_learned, rule_change_candidate]
    mutable_until: reviewed_at

  finviz_import:
    description: "captured at daily screener processing"
    cadence: daily_per_run
    examples: [source_screen, screen_criteria_snapshot, screen_run_date,
               raw_screen_columns]

  tos_export_reconciled:
    description: "broker truth, available only after weekly CSV export"
    cadence: weekly
    examples: [actual_fill_price, actual_fill_size, actual_fill_datetime,
               commissions_fees, realized_pnl_broker, account_equity_close]
    reconciliation_required: true

  yfinance_query:
    description: "market data pull, end-of-day daily bars canonical"
    cadence: daily_eod
    examples: [current_price, open_R, MFE_to_date_R, MAE_to_date_R, MFE_R,
               MAE_R, market_regime_inputs]
    cacheable_idempotent: true
    outage_tolerance: "high; field staleness flagged but does not block journaling"

  computed:
    description: "derived from other fields by deterministic formula"
    examples: [realized_R, capture_ratio, expectancy_R, profit_factor,
               current_at_risk_dollars, current_at_risk_R,
               portfolio_heat_pre_trade, completeness_score, holding_period_days]
    recompute_trigger: "any change to dependency fields"
```

Latency tiers:

```yaml
availability_latency:
  immediate:
    description: "available the moment the field is logged"
    sources: [manual_pre_trade, manual_in_trade, manual_post_trade, finviz_import]

  end_of_day:
    description: "available after EOD yfinance pull"
    sources: [yfinance_query, computed_from_yfinance]

  weekly_reconciled:
    description: "reliable only after weekly TOS reconciliation"
    sources: [tos_export_reconciled]
    pre_reconciliation_value: "trader manual entry, flagged as unreconciled"
```

Each field table in §9 carries a `source` column. AI evaluation rules
treat unreconciled values as provisional and may issue alerts but cannot
issue final process grades until `reconciliation_status = reconciled_match`
or `reconciled_discrepancy_resolved`.

---

## 8. Controlled Vocabularies (NEW in v1.1)

Centralizing enums here addresses M4, M5, and C6. All free-text fields in
v1.0 that drive segmentation analytics or AI gate decisions are upgraded to
enum + optional free-text annotation.

### 8.1 `market_regime`

```yaml
market_regime:
  bull_trending:
    description: "broad index in confirmed uptrend, leadership clear, breadth healthy"
  bull_pullback:
    description: "uptrend intact but in orderly pullback; high-quality breakouts often pause"
  distribution_top:
    description: "leadership breaking down, distribution days clustered, prior leaders failing"
  bear_trending:
    description: "broad index in confirmed downtrend, leadership broken"
  bear_rally:
    description: "countertrend rally inside larger downtrend; failure-prone"
  range_compression:
    description: "tight range, low volatility, building energy in either direction"
  range_choppy:
    description: "wide directionless range with frequent reversals"
  transition_unclear:
    description: "regime shifting; signals conflict; default to caution"
```

### 8.2 `catalyst`

```yaml
catalyst:
  earnings_beat:           "reported earnings exceeded consensus"
  earnings_miss:           "reported earnings missed consensus"
  guidance_raise:          "forward guidance raised"
  guidance_cut:            "forward guidance cut"
  ma_announcement:         "merger or acquisition news"
  secondary_offering:      "stock offering announcement"
  analyst_action:          "upgrade / downgrade / price target change"
  sector_rotation:         "sector-level relative-strength shift"
  macro_event:             "Fed / CPI / employment / geopolitical"
  sympathy_move:           "moving in sympathy with sector or peer"
  technical_only:          "no fundamental catalyst; pure pattern / RS"
  product_news:            "product launch, FDA, partnership, contract win"
  other:                   "free-text required in catalyst_other_description"
```

### 8.3 `stop_type`

```yaml
stop_type:
  chart_swing_low_high:        "below recent swing low (long) or above recent swing high (short)"
  chart_consolidation_break:   "below consolidation base or above consolidation top"
  atr_multiple:                "n × ATR from entry; specify multiple in stop_parameter"
  percentage_below_entry:      "fixed percent from entry; specify percent in stop_parameter"
  prior_day_low_high:          "below prior session low or above prior session high"
  moving_average:              "below specified MA (e.g. 10-day, 21-day); specify MA in stop_parameter"
  time_stop_only:              "no price stop; exit if no progress within N days"
  volatility_band:             "band-based; specify band in stop_parameter"
  discretionary:               "no objective rule; flagged for review and downgrades pre_trade_quality_score"
```

### 8.4 `setup_family`

`setup_family` describes the pattern type. `direction` is a separate field
(short removed from this enum per C6).

```yaml
setup_family:
  breakout:                "breakout from a tightening base or consolidation"
  pullback:                "pullback to a defined support level within an uptrend"
  episodic_pivot:          "high-volume earnings / news pivot reset"
  gap_continuation:        "gap up at open with continuation"
  reversal:                "reversal pattern from prior trend"
  trend_continuation:      "ongoing trend, mid-trend entry"
  vcp_pivot:               "Minervini-style VCP pivot point breakout"
  reclaim:                 "reclaim of broken level"
```

### 8.5 `entry_trigger_type`

`entry_trigger_type` describes how the entry was actually executed.
Distinct from `setup_family` so a single setup family (e.g. `breakout`) can
be entered via different trigger types (e.g. `breakout_pivot` vs. `pullback_to_pivot`).

```yaml
entry_trigger_type:
  breakout_pivot:          "entered on break above defined pivot price"
  pullback_to_ma:          "entered on pullback to a moving average"
  pullback_to_pivot:       "entered on pullback to prior breakout level"
  gap_and_go:              "entered on gap-up open with confirmation"
  reclaim_level:           "entered on reclaim of broken support / resistance"
  opening_range:           "entered on break of opening range"
  reversal_signal:         "entered on reversal candle / divergence signal"
  bounce_off_support:      "entered on bounce off a defined support level"
```

### 8.6 `exit_reason`

```yaml
exit_reason:
  stop_hit:                "initial or trailing stop triggered"
  target_hit:              "planned target reached"
  trailing_stop:           "trailing stop algorithm triggered"
  time_stop:               "time stop hit; no progress within window"
  thesis_invalidated:      "thesis broke before stop or target"
  risk_reduction:          "trimmed for portfolio risk reasons unrelated to single trade"
  discretionary:           "exited without rule basis; flagged for review"
  other:                   "free-text required"
```

### 8.7 `thesis_status` (in-trade)

```yaml
thesis_status:
  valid:                   "trade unfolding as expected"
  strengthening:           "thesis is being confirmed by additional evidence"
  weakening:               "thesis is being undermined but not invalidated"
  invalidated:             "thesis has failed; stop should be honored or position exited"
  unclear:                 "evidence ambiguous; flagged for follow-up"
```

### 8.8 `thesis_accuracy` (post-trade)

```yaml
thesis_accuracy:
  correct:                 "thesis proved out as expected"
  partially_correct:       "directional thesis correct but magnitude / timing off"
  incorrect:               "thesis was wrong"
  unclear:                 "outcome ambiguous; insufficient evidence to judge"
```

### 8.9 `setup_validity_after_review` (post-trade)

```yaml
setup_validity_after_review:
  valid:                   "this was a clean instance of the setup family"
  marginal:                "setup criteria partially met"
  invalid:                 "this should not have been classified as this setup"
  lucky:                   "outcome favorable but setup did not meet criteria"
```

### 8.10 `reconciliation_status`

```yaml
reconciliation_status:
  unreconciled:                 "manual entry only; no broker comparison yet"
  reconciled_match:             "manual matches broker within tolerance"
  reconciled_discrepancy:       "broker disagrees; discrepancy logged but not yet resolved"
  reconciled_discrepancy_resolved: "discrepancy investigated and resolved"
  manual_override:              "broker data unavailable or wrong; manual treated as canonical with audit"
```

### 8.11 `manual_entry_confidence`

```yaml
manual_entry_confidence:
  high:    "logged in real time with full attention; expect to match broker"
  normal:  "logged shortly after the action; minor errors possible"
  low:     "logged in a hurry or after delay; verify on next reconciliation"
```

### 8.12 `mistake_cost_confidence`

```yaml
mistake_cost_confidence:
  high:     "planned stop / target rule provides objective counterfactual"
  medium:   "reasonable reconstruction from chart and plan"
  low:      "subjective estimate; use only for qualitative review; excluded from hard portfolio totals"
```

---

## 9. Tab Specifications

### 9.1 `Setup_Playbook`

Purpose: Define each strategy / setup before trades are taken so trades
can be evaluated by repeatable rules.

```yaml
tab: Setup_Playbook
row_granularity: "one row per setup"
primary_key: setup_id
ai_use:
  - verify_trade_matches_setup
  - calculate_expectancy_by_setup
  - detect_setup_drift
  - recommend_setup_retirement_or_refinement
```

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `setup_id` | string | yes | manual | Unique identifier, e.g. `BO_HTF_01`, `PULLBACK_10EMA`, `EP_GAP_01` |
| `setup_name` | string | yes | manual | Human-readable name |
| `setup_family` | enum | yes | manual | See §8.4 |
| `direction_allowed` | enum | yes | manual | `long`, `short`, `both` (v1.1 scope: long-only currently) |
| `market_regime_allowed` | list | yes | manual | Regimes from §8.1 where setup is valid |
| `timeframe` | string | yes | manual | Daily, weekly / daily, 4H / daily |
| `liquidity_minimum` | numeric | yes | manual | Minimum dollar volume |
| `volatility_requirement` | string | no | manual | ADR%, ATR%, range expansion |
| `relative_strength_requirement` | string | no | manual | RS rank, RS new high, sector leadership |
| `fundamental_requirement` | string | no | manual | Earnings / sales growth, catalyst, none |
| `technical_structure` | text | yes | manual | Base, flag, VCP, reclaim, box, pullback |
| `entry_trigger_type_default` | enum | yes | manual | See §8.5 |
| `entry_trigger_rule` | text | yes | manual | Objective entry condition |
| `initial_stop_type` | enum | yes | manual | See §8.3 |
| `initial_stop_rule` | text | yes | manual | Objective stop placement rule |
| `initial_stop_parameter` | string | conditional | manual | Required when stop_type takes a parameter (e.g. ATR multiple) |
| `profit_taking_rule` | text | yes | manual | Target, partial, trailing rule |
| `time_stop_rule` | text | yes | manual | Max hold if thesis does not progress |
| `add_on_rule` | text | no | manual | Conditions for pyramiding; if defined, governs Fills with action=add |
| `disqualifiers` | list | yes | manual | Conditions that invalidate setup |
| `ideal_example_link` | url | no | manual | Annotated chart |
| `failed_example_link` | url | no | manual | Failed setup example |
| `status` | enum | yes | manual | `active`, `pilot`, `paused`, `retired` |

Setup status definitions (v1.1 — `testing` repurposed since paper trading
is out of scope):

```yaml
setup_status_rules:
  active:
    requirement: "defined rules and sufficient confidence to risk full capital allocation"
  pilot:
    requirement: "reduced-size only (max 50% of normal risk allocation); exit pilot when 20+ trades reach consistent expectancy"
  paused:
    requirement: "temporarily disabled due to poor regime fit or recent underperformance; revisit on monthly cadence"
  retired:
    requirement: "removed after evidence of negative expectancy across 30+ trades or repeated regime conflict"
```

---

### 9.2 `Trade_Log`

Purpose: Main trade-level table. One row per trade idea from planning to
final review.

```yaml
tab: Trade_Log
row_granularity: "one row per discrete trade (re-entries are new rows linked via parent_trade_id)"
primary_key: trade_id
ai_use:
  - calculate_performance
  - grade_process
  - detect_rule_violations
  - identify_high_value_improvements
  - drive_state_machine_transitions
```

Required-field set varies by `state` per §6. Tables below mirror that
structure.

#### 9.2.1 Identity and Linkage Fields (required from `planned`)

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `trade_id` | string | yes | computed | Unique trade identifier |
| `parent_watchlist_id` | string | yes | linkage | Links to Watchlist_Entry that surfaced this idea |
| `parent_trade_id` | string | conditional | linkage | Required if this is a re-entry of a stopped-out prior trade within 30 days |
| `state` | enum | yes | computed | See §6 trade_states |
| `instrument_type` | enum | yes | manual | `stock` (only valid value in v1.1) |
| `ticker` | string | yes | manual | Instrument symbol |
| `direction` | enum | yes | manual | `long` (only valid value while v1.1 scope is long-only) |
| `setup_id` | string | yes | manual | Links to Setup_Playbook |

#### 9.2.2 Pre-Trade Decision Fields (required from `planned`; locked at `entered`)

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `planned_date` | date | yes | manual_pre_trade | Date trade was planned |
| `market_regime` | enum | yes | manual_pre_trade | See §8.1 |
| `sector_theme` | string | no | manual_pre_trade | Sector / industry / theme |
| `sector_condition` | enum | no | manual_pre_trade | `leading`, `improving`, `neutral`, `weakening`, `lagging` |
| `catalyst` | enum | yes | manual_pre_trade | See §8.2 |
| `catalyst_other_description` | text | conditional | manual_pre_trade | Required if catalyst=`other` |
| `thesis` | text | yes | manual_pre_trade | Why the trade should work |
| `why_now` | text | yes | manual_pre_trade | Why entry is timely today |
| `expected_scenario` | text | yes | manual_pre_trade | What should happen if right |
| `invalidation_condition` | text | yes | manual_pre_trade | What proves thesis wrong; must map to stop or exit |
| `premortem_failure_reasons` | list[text] | yes | manual_pre_trade | Min 3 distinct failure modes |
| `confidence_score` | numeric | no | manual_pre_trade | 1–5 |
| `pre_trade_quality_score` | numeric | yes | manual_pre_trade | 0–10, see §11.1 |
| `emotional_state_pre_trade` | list[enum] | yes | manual_pre_trade | `calm`, `FOMO`, `revenge`, `tired`, `impatient`, `anxious`, `confident`, `bored` |
| `final_pre_trade_decision` | enum | yes | manual_pre_trade | `take`, `pass`, `wait`, `reduce_size` |

#### 9.2.3 Risk Plan Fields (required from `planned`)

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `account_equity_pre_trade` | numeric | yes | manual_pre_trade | Account value before trade (TOS-confirmable on reconcile) |
| `max_account_risk_pct` | numeric | yes | manual_pre_trade | Planned risk percentage; bounded by Risk_Policy |
| `planned_risk_dollars` | numeric | yes | computed | `account_equity_pre_trade × max_account_risk_pct` |
| `planned_entry` | numeric | yes | manual_pre_trade | Intended entry price |
| `initial_stop` | numeric | yes | manual_pre_trade | Initial protective stop |
| `risk_per_share` | numeric | yes | computed | `abs(planned_entry − initial_stop)` |
| `target_1` | numeric | no | manual_pre_trade | First target |
| `target_2` | numeric | no | manual_pre_trade | Second / stretch target |
| `planned_position_size` | numeric | yes | computed | `planned_risk_dollars / risk_per_share` |
| `planned_gross_exposure` | numeric | yes | computed | `planned_position_size × planned_entry` |
| `portfolio_heat_pre_trade` | numeric | yes | computed | Sum of `current_at_risk_dollars` across open positions immediately prior |
| `correlated_exposure` | text | yes | manual_pre_trade | Sector / theme overlap with other open positions |
| `planned_reward_risk_ratio` | numeric | no | computed | `(target_1 − planned_entry) / risk_per_share` for longs |
| `position_size_override_reason` | text | conditional | manual_pre_trade | Required if size differs from formula |
| `planned_holding_period_days` | numeric | yes | manual_pre_trade | Expected duration |
| `event_risk_present` | boolean | yes | manual_pre_trade | Whether known event risk exists in planned hold window |
| `event_type` | enum | conditional | manual_pre_trade | Required if event_risk_present=true; values: `earnings`, `fed`, `cpi`, `employment`, `fda`, `other` |
| `event_date` | date | conditional | manual_pre_trade | Required if event_risk_present=true |
| `event_handling` | enum | yes | manual_pre_trade | `avoid_event`, `hold_through`, `reduce_before`, `exit_before` |
| `gap_risk_present` | boolean | yes | manual_pre_trade | Overnight gap risk acknowledged |
| `gap_risk_handling` | enum | yes | manual_pre_trade | `accept`, `reduce_size`, `tight_stop`, `exit_before_close` |

#### 9.2.4 Execution Fields (required from `entered`)

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `trigger_observed_datetime` | datetime | yes (in `triggered`) | manual_in_trade | When entry trigger was observed |
| `actual_entry_date` | date | yes (in `entered`) | derived from Fills | First entry fill date |
| `actual_entry_time` | time | no | derived from Fills | First entry fill time |
| `actual_entry_price` | numeric | yes (in `entered`) | derived from Fills | Quantity-weighted average of entry-tagged fills |
| `actual_position_size` | numeric | yes (in `entered`) | derived from Fills | Sum of entry / add fills minus trim / exit fills |
| `entry_order_type` | enum | no | manual_in_trade | `market`, `limit`, `stop`, `stop_limit`, `other` |
| `entry_trigger_type` | enum | yes | manual_in_trade | See §8.5 |
| `entry_trigger_followed` | boolean | yes | manual_in_trade | Did actual entry match trigger rule? |
| `entry_slippage` | numeric | no | computed | `actual_entry_price − planned_entry` (sign-adjusted by direction) |
| `entry_grade` | enum | conditional (required in `reviewed`) | manual_post_trade | `A` … `F`; see §11.2 |
| `execution_notes` | text | no | manual_in_trade | Any fill issues |
| `pre_trade_locked_at` | datetime | yes (in `entered`) | computed | Timestamp at which pre-trade fields were locked; written once |
| `initial_risk_dollars` | numeric | yes (in `entered`) | computed | `risk_per_share × actual_position_size_at_first_fill`; immutable thereafter |
| `manual_entry_confidence` | enum | yes | manual_pre_trade | See §8.11 |
| `reconciliation_status` | enum | yes | computed | See §8.10; default `unreconciled` |

#### 9.2.5 Live Risk Fields (computed during `managing` / `partial_exited`)

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `current_avg_cost` | numeric | computed | computed | Quantity-weighted average cost of open shares |
| `current_size` | numeric | computed | computed | Net open size |
| `current_stop` | numeric | yes during open states | manual_in_trade | Latest stop level |
| `current_at_risk_dollars` | numeric | computed | computed | `(current_avg_cost − current_stop) × current_size` for longs |
| `current_at_risk_R` | numeric | computed | computed | `current_at_risk_dollars / initial_risk_dollars` |
| `open_R` | numeric | computed | computed | `(current_price − actual_entry_price) × actual_position_size / initial_risk_dollars` for longs |

#### 9.2.6 Exit and Outcome Fields (required from `closed`)

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `exit_date` | date | yes | derived from Fills | Final close date |
| `exit_price_avg` | numeric | yes | derived from Fills | Quantity-weighted exit price |
| `exit_reason` | enum | yes | manual_post_trade | See §8.6 |
| `planned_exit_followed` | boolean | yes | manual_post_trade | Did exit match plan? |
| `gross_pnl_dollars` | numeric | yes | computed | Before fees |
| `fees_commissions` | numeric | yes | tos_export_reconciled | Costs |
| `net_pnl_dollars` | numeric | yes | computed | After costs |
| `realized_R` | numeric | yes | computed | `net_pnl_dollars / initial_risk_dollars` |
| `MFE_R` | numeric | yes | computed | See §10 measurement convention |
| `MAE_R` | numeric | yes | computed | See §10 measurement convention |
| `capture_ratio` | numeric | conditional | computed | `realized_R / MFE_R` only if `realized_R > 0` and `MFE_R > 0`; else `n/a` |
| `holding_period_days` | numeric | yes | computed | `exit_date − actual_entry_date` |

#### 9.2.7 Review Fields (required from `reviewed`)

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `thesis_accuracy` | enum | yes | manual_post_trade | See §8.8 |
| `setup_validity_after_review` | enum | yes | manual_post_trade | See §8.9 |
| `entry_grade` | enum | yes | manual_post_trade | `A` … `F` |
| `management_grade` | enum | yes | manual_post_trade | `A` … `F` |
| `exit_grade` | enum | yes | manual_post_trade | `A` … `F` |
| `process_grade` | enum | yes | computed | Worst of the three per-stage grades; see §11.2 |
| `mistake_tags` | list | yes | manual_post_trade | From §9.6; `[none_observed]` is a valid value |
| `mistake_cost_R` | numeric | yes | computed/manual | `>= 0`; harm only |
| `lucky_violation_R` | numeric | yes | computed/manual | `>= 0`; unearned benefit only |
| `mistake_cost_confidence` | enum | yes | manual_post_trade | See §8.12 |
| `lesson_learned` | text | yes | manual_post_trade | One clear lesson |
| `rule_change_candidate` | boolean | yes | manual_post_trade | Should rule be reviewed? |
| `rule_change_id` | string | conditional | linkage | Required if rule_change_candidate=true; creates Rule_Change_Queue stub |
| `post_trade_screenshot_link` | url | no | manual_post_trade | Final annotated chart |
| `reviewed_at` | datetime | yes | computed | Timestamp when review was completed |

---

### 9.3 `Fills`

Purpose: Canonical broker record. Source of truth for execution data
(C11). Trade_Log execution fields are derived from Fills.

```yaml
tab: Fills
row_granularity: "one row per fill"
primary_key: fill_id
foreign_key: trade_id
canonical_for: ["actual_entry_price", "actual_exit_price", "actual_position_size", "fees_commissions", "gross_pnl_dollars"]
ai_use:
  - reconstruct_trade
  - compute_weighted_average_entry_exit
  - analyze_partial_exit_quality
  - detect_rule_violating_adds
  - drive_state_transitions_to_managing_partial_exited_closed
```

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `fill_id` | string | yes | computed | Unique fill identifier |
| `trade_id` | string | yes | linkage | Links fill to trade |
| `fill_datetime` | datetime | yes | manual_in_trade then tos_export_reconciled | Time of fill |
| `action` | enum | yes | manual_in_trade | `entry`, `add`, `trim`, `exit`, `stop`, `cover` |
| `quantity` | numeric | yes | manual_in_trade then tos_export_reconciled | Units filled |
| `price` | numeric | yes | manual_in_trade then tos_export_reconciled | Fill price |
| `order_type` | enum | no | manual_in_trade | Market, limit, stop, stop_limit |
| `reason` | text | yes | manual_in_trade | Why fill happened (rule reference if rule-based) |
| `rule_based` | boolean | yes | manual_in_trade | Was this fill allowed by plan? |
| `fees` | numeric | conditional | tos_export_reconciled | Required after reconciliation |
| `manual_entry_confidence` | enum | yes | manual_in_trade | See §8.11 |
| `reconciliation_status` | enum | yes | computed | See §8.10 |
| `tos_match_id` | string | conditional | tos_export_reconciled | TOS row identifier after reconciliation |

---

### 9.4 `Daily_Management`

Purpose: Track thesis quality and management decisions while the trade is
open. Two record types reduce friction (P2 disposition).

```yaml
tab: Daily_Management
row_granularity: "one row per open trade per review_date OR one row per material event"
primary_key: management_record_id
foreign_key: trade_id
record_type_enum: [daily_snapshot, event_log]
ai_use:
  - evaluate_hold_vs_exit_decisions
  - detect_thesis_deterioration
  - measure_stop_discipline
  - identify_emotional_management_errors
  - score_review_compliance
```

#### 9.4.1 `daily_snapshot` record (low-friction; permitted on no-change days)

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `management_record_id` | string | yes | computed | Unique row ID |
| `trade_id` | string | yes | linkage | Links to trade |
| `record_type` | enum | yes | computed | `daily_snapshot` |
| `review_date` | date | yes | computed | Review date |
| `current_price` | numeric | yes | yfinance_query | Daily close |
| `current_stop` | numeric | yes | manual_in_trade | Stop at review |
| `open_R` | numeric | yes | computed | Unrealized R |
| `current_at_risk_R` | numeric | yes | computed | Live at-risk R (M3) |
| `MFE_to_date_R` | numeric | yes | computed (yfinance) | Best unrealized R so far |
| `MAE_to_date_R` | numeric | yes | computed (yfinance) | Worst unrealized R so far |
| `thesis_status` | enum | yes | manual_in_trade | See §8.7 |

A `daily_snapshot` is allowed only when:
- `current_stop` unchanged from prior record
- No `action_taken` other than `no_action`
- `thesis_status` unchanged or both prior and current are `valid`
- No suspected rule violation

If any of those fail, the record must be an `event_log` record.

#### 9.4.2 `event_log` record (full-friction; required on any material event)

In addition to all `daily_snapshot` fields:

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `prior_stop` | numeric | yes | computed from prior record | Stop before this event |
| `stop_changed` | boolean | yes | computed | `current_stop != prior_stop` |
| `stop_change_reason` | text | conditional | manual_in_trade | Required if `stop_changed` |
| `volume_behavior` | enum | no | manual_in_trade or yfinance | `confirming`, `neutral`, `distribution`, `fading` |
| `relative_strength_status` | enum | no | manual_in_trade | `improving`, `flat`, `weakening` |
| `market_regime_change` | boolean | yes | manual_in_trade | Did broad market context change? |
| `sector_condition_change` | boolean | yes | manual_in_trade | Did sector context change? |
| `news_or_event_update` | text | no | manual_in_trade | New catalyst or risk |
| `action_taken` | enum | yes | manual_in_trade | `hold`, `trim`, `add`, `exit`, `move_stop`, `no_action` |
| `action_reason` | text | yes | manual_in_trade | Must explain decision and reference plan rule if rule-based |
| `emotional_state` | list[enum] | yes | manual_in_trade | Emotional condition during hold |
| `rule_violation_suspected` | boolean | yes | manual_in_trade | Was any rule violated? |
| `management_notes` | text | no | manual_in_trade | Additional context |

Auto-populatable fields (`current_price`, `open_R`, `current_at_risk_R`,
`MFE_to_date_R`, `MAE_to_date_R`) are filled by a nightly batch from
yfinance daily bars. The trader is responsible only for `current_stop`,
`thesis_status`, and (on event_log records) the management decision fields.

---

### 9.5 `Watchlist` (NEW required tab in v1.1)

Purpose: Capture ideas before trade entry. `time_on_watchlist_days` and
`source_screen` are predictive (M11, N4) and propagate to the Trade_Log.

```yaml
tab: Watchlist
row_granularity: "one row per ticker watch instance"
primary_key: watchlist_entry_id
ai_use:
  - track_time_on_watchlist
  - measure_screen_to_trade_conversion_rate
  - support_screen_level_expectancy_attribution
  - support_missed_trade_analysis
```

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `watchlist_entry_id` | string | yes | computed | Unique ID |
| `screener_run_id` | string | yes | linkage | Links to Daily_Screener_Log |
| `ticker` | string | yes | finviz_import | Symbol |
| `added_date` | date | yes | computed | When ticker first appeared on watchlist |
| `source_screen` | string | yes | finviz_import | Screen name from Daily_Screener_Log |
| `setup_id_candidate` | string | no | manual | Likely setup family if known |
| `pivot_price_candidate` | numeric | no | manual | Anticipated entry trigger price |
| `notes` | text | no | manual | Stalk-list commentary |
| `removed_date` | date | conditional | computed | Set when removed without trading |
| `removal_reason` | enum | conditional | manual | `traded`, `failed_pattern`, `regime_changed`, `no_trigger`, `other` |
| `resulting_trade_id` | string | conditional | linkage | Set when this watchlist entry produces a trade |

When a Trade_Log row is created, its `parent_watchlist_id` MUST point to a
Watchlist_Entry; `time_on_watchlist_days` is computed as
`actual_entry_date − added_date` and stored on Trade_Log.

---

### 9.6 `Mistake_Tags`

Purpose: Controlled vocabulary so behavioral errors can be counted, costed,
and aggregated. Updated in v1.1 to add reconciliation-revealed errors.

```yaml
tab: Mistake_Tags
row_granularity: "one row per mistake type"
primary_key: mistake_tag
ai_use:
  - normalize_error_labels
  - calculate_R_cost_by_error
  - identify_recurring_process_leaks
```

#### Entry Mistakes
| Tag | Category | Definition |
|---|---|---|
| `CHASED` | entry | Entered meaningfully above planned level after risk / reward deteriorated |
| `EARLY_ENTRY` | entry | Entered before trigger confirmed |
| `LATE_ENTRY` | entry | Entered too late relative to planned pivot / trigger |
| `NO_SETUP` | entry | Trade did not match active setup playbook |
| `LOW_LIQUIDITY` | entry | Instrument had poor spread / volume relative to plan |
| `EVENT_IGNORED` | entry | Ignored known earnings / macro / news risk |

#### Risk Mistakes
| Tag | Category | Definition |
|---|---|---|
| `OVERSIZED` | risk | Actual size exceeded risk plan |
| `NO_STOP` | risk | No valid initial stop or invalidation point |
| `STOP_TOO_WIDE` | risk | Stop made reward / risk unacceptable or arbitrary |
| `STOP_TOO_TIGHT` | risk | Stop was inside normal noise for setup |
| `CORRELATION_IGNORED` | risk | Too much same-sector / theme exposure |
| `GAP_RISK_IGNORED` | risk | Overnight / event gap risk not considered |
| `HEAT_OVERAGE` | risk | Total portfolio heat exceeded Risk_Policy at entry |
| `CIRCUIT_BREAKER_OVERRIDDEN` | risk | Took trade despite active halt rule |

#### Management Mistakes
| Tag | Category | Definition |
|---|---|---|
| `MOVED_STOP_AWAY` | management | Increased risk after entry without valid rule |
| `SOLD_TOO_EARLY` | management | Exited winner without rule-based reason |
| `HELD_AFTER_INVALIDATION` | management | Stayed in trade after thesis failed |
| `FAILED_TO_SCALE` | management | Failed to take planned partial or reduce risk |
| `ADDED_TO_LOSER` | management | Averaged down against rules |
| `MISSED_TIME_STOP` | management | Held beyond planned window without renewed thesis |

#### Psychology Mistakes
| Tag | Category | Definition |
|---|---|---|
| `FOMO` | psychology | Trade driven by fear of missing out |
| `REVENGE` | psychology | Trade taken to recover recent loss |
| `BOREDOM` | psychology | Trade taken without sufficient opportunity quality |
| `EGO` | psychology | Refusal to accept invalidation |
| `ANCHORING` | psychology | Fixation on entry, prior high, target, or unrealized P&L |
| `CONFIRMATION_BIAS` | psychology | Ignored disconfirming evidence |
| `LOSS_AVERSION` | psychology | Held loser to avoid realizing loss |
| `OVERCONFIDENCE` | psychology | Increased frequency / size after wins without evidence |

#### Reconciliation-Revealed Mistakes (NEW in v1.1)
| Tag | Category | Definition |
|---|---|---|
| `SIZE_MISCOUNTED` | reconciliation | Journal size did not match TOS fill size |
| `WRONG_TICKER_ENTERED` | reconciliation | Journal logged different ticker than executed |
| `FILL_NOT_LOGGED` | reconciliation | Broker shows fill not present in journal |
| `PARTIAL_NOT_LOGGED` | reconciliation | Trim or partial exit missed in journal |
| `STOP_NOT_PLACED` | reconciliation | Journal indicated stop set, broker shows none |

#### Special Tag
| Tag | Category | Definition |
|---|---|---|
| `none_observed` | none | Affirmative declaration that no mistake was made; required default |

Mistake severity scale:

```yaml
mistake_severity:
  1: "minor documentation or execution issue; little R impact"
  2: "minor process violation; limited R impact"
  3: "material process violation; measurable R impact"
  4: "major rule violation; large or repeated R impact"
  5: "critical violation; threatens account discipline or strategy validity"
```

---

### 9.7 `Review_Log`

Purpose: Convert trade data into improvement decisions. Updated in v1.1 to
include review-compliance and data-quality metrics (P6, P7).

```yaml
tab: Review_Log
row_granularity: "one row per daily, weekly (with reconciliation), monthly, or quarterly review"
primary_key: review_id
ai_use:
  - summarize_performance
  - detect_recurring_behavior_patterns
  - recommend_process_improvements
  - prevent_overfitting_from_small_sample_sizes
  - score_review_compliance
```

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `review_id` | string | yes | computed | Unique review identifier |
| `review_type` | enum | yes | manual | `daily`, `weekly`, `monthly`, `quarterly` |
| `period_start` | date | yes | computed | Start of review period |
| `period_end` | date | yes | computed | End of review period |
| `scheduled_date` | date | yes | computed | When this review was due |
| `completed_date` | date | conditional | computed | When the review was actually completed |
| `skipped` | boolean | yes | computed | True if completed_date > scheduled_date + grace_period |
| `duration_minutes` | numeric | conditional | manual | Required if completed |
| `number_of_trades` | numeric | yes | computed | Closed trades reviewed |
| `net_R` | numeric | yes | computed | Sum of realized R |
| `expectancy_R` | numeric | yes | computed | Average R per trade |
| `win_rate` | numeric | yes | computed | % profitable trades |
| `avg_win_R` | numeric | yes | computed | Average winning trade in R |
| `avg_loss_R` | numeric | yes | computed | Average losing trade in R (natively negative) |
| `profit_factor` | numeric | yes | computed | Gross wins / abs(gross losses) |
| `max_drawdown_R` | numeric | yes | computed | Largest peak-to-trough R drawdown |
| `best_trade_R` | numeric | yes | computed | Best trade |
| `worst_trade_R` | numeric | yes | computed | Worst trade |
| `top_performing_setup` | string | no | computed | Best setup by expectancy with sample threshold |
| `worst_performing_setup` | string | no | computed | Weakest setup by expectancy with sample threshold |
| `highest_cost_mistake_tag` | string | no | computed | Mistake tag with largest aggregate R leakage |
| `total_mistake_cost_R` | numeric | yes | computed | Sum of mistake_cost_R across reviewed trades |
| `total_lucky_violation_R` | numeric | yes | computed | Sum of lucky_violation_R; reported alongside but never netted against mistake_cost_R |
| `data_quality_score` | numeric | yes | computed | 0–100; see §10 |
| `review_compliance_rate` | numeric | yes | computed | % of scheduled daily reviews completed in period |
| `reconciliation_compliance_rate` | numeric | yes | computed | % of scheduled weekly reconciliations completed |
| `circuit_breaker_activations` | numeric | yes | computed | Count of halt rule activations in period |
| `primary_lesson` | text | yes | manual | Main takeaway |
| `next_period_focus` | text | yes | manual | Specific execution focus |
| `rule_change_candidates` | list | no | linkage | Candidate changes requiring more evidence |

---

### 9.8 `Rule_Change_Queue`

Purpose: Prevent impulsive rule changes after one trade.

Largely unchanged from v1.0. Updated in v1.1 only for C9 (rule_change_id is
now a reference target from Trade_Log).

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `rule_change_id` | string | yes | computed | Unique ID |
| `date_proposed` | date | yes | computed | Date candidate was created |
| `affected_setup_id` | string | no | linkage | Setup affected |
| `current_rule` | text | yes | manual | Existing rule |
| `proposed_rule` | text | yes | manual | Proposed change |
| `reason` | text | yes | manual | Why change is being considered |
| `supporting_trade_ids` | list | yes | linkage | Evidence set; populated automatically when trades flag rule_change_candidate=true |
| `sample_size` | numeric | yes | computed | Number of supporting trades |
| `estimated_R_impact` | numeric | no | manual | Historical R improvement estimate |
| `overfitting_risk` | enum | yes | manual | `low`, `medium`, `high` |
| `decision` | enum | yes | manual | `monitor`, `test`, `accept`, `reject`, `defer` |
| `review_date` | date | yes | manual | When to revisit |

Evidence thresholds (unchanged from v1.0):

```yaml
rule_change_threshold:
  minor_operational_rule:
    minimum_trades: 5
    requirement: "clear recurring process issue"
  setup_rule_change:
    minimum_trades: 20
    requirement: "consistent pattern across market contexts or strong supporting backtest"
  position_sizing_rule_change:
    minimum_trades: 30
    requirement: "drawdown and expectancy analysis required"
  strategy_retirement:
    minimum_trades: 30
    requirement: "negative expectancy, poor fit, or repeated rule conflict"
```

---

### 9.9 `Risk_Policy` (NEW required tab in v1.1)

Purpose: Encode account-level limits and circuit breakers operationally.
Addresses M10 (account-level controls not parameterized) and M8 / §4.3
(streak-based behavioral rules).

```yaml
tab: Risk_Policy
row_granularity: "one active policy at a time; historical policies retained for audit"
primary_key: policy_id
ai_use:
  - gate_pre_trade_approvals
  - enforce_circuit_breakers
  - audit_account_level_compliance
```

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `policy_id` | string | yes | computed | Unique policy ID |
| `effective_from` | date | yes | manual | Policy start date |
| `effective_to` | date | conditional | manual | Set when policy is superseded |
| `is_active` | boolean | yes | computed | True if today between effective_from and effective_to |
| `max_account_risk_per_trade_pct` | numeric | yes | manual | Default 0.50% |
| `max_concurrent_positions` | numeric | yes | manual | Default 6 (per scope) |
| `max_portfolio_heat_pct` | numeric | yes | manual | Sum of current_at_risk as % of equity; default 3.0% |
| `max_sector_concentration_positions` | numeric | yes | manual | Default 3 |
| `consecutive_losses_pause_threshold` | numeric | yes | manual | Default 3 |
| `consecutive_losses_pause_action` | enum | yes | manual | `review_required`, `reduce_size`, `halt` |
| `consecutive_losses_streak_reset` | enum | yes | manual | `any_winning_trade`, `review_completed`, `n_days_elapsed` |
| `drawdown_pause_threshold_R` | numeric | yes | manual | Default −6 |
| `drawdown_pause_action` | enum | yes | manual | `reduce_size`, `halt` |
| `drawdown_size_reduction_pct` | numeric | conditional | manual | Required if drawdown_pause_action=reduce_size; default 50% |
| `drawdown_recovery_threshold_R` | numeric | yes | manual | R level at which drawdown action lifts; default −2 |
| `policy_notes` | text | no | manual | Free-text rationale |

Live computed fields (read by pre-trade gate):

```yaml
risk_policy_runtime_state:
  current_consecutive_loss_count:
    formula: "count of last N closed trades where realized_R < 0, walking back from most recent until first realized_R > 0"
  current_drawdown_R:
    formula: "running peak-to-current R drawdown over rolling 30-trade window"
  current_portfolio_heat_R:
    formula: "sum of current_at_risk_R across all open trades"
  current_open_position_count:
    formula: "count of trades in state in {entered, managing, partial_exited}"
  trading_halt_active:
    formula: "current_consecutive_loss_count >= consecutive_losses_pause_threshold AND no review record since last loss; OR current_drawdown_R <= drawdown_pause_threshold_R"
  size_reduction_active:
    formula: "drawdown_pause_action = reduce_size AND current_drawdown_R <= drawdown_pause_threshold_R AND current_drawdown_R < drawdown_recovery_threshold_R"
```

Pre-trade gate (§12.1) blocks new trade approval if `trading_halt_active`,
and forces size reduction per `drawdown_size_reduction_pct` if
`size_reduction_active`.

---

### 9.10 `Reconciliation_Log` (NEW required tab in v1.1)

Purpose: Track weekly reconciliation events between manual journal and
TOS CSV. Addresses N1.

```yaml
tab: Reconciliation_Log
parent_entity: Reconciliation_Run
child_entity: Reconciliation_Discrepancy
row_granularity: "one Reconciliation_Run row per weekly reconciliation; many Reconciliation_Discrepancy rows per run"
ai_use:
  - track_reconciliation_compliance
  - identify_recurring_data_quality_issues
  - flag_systemic_journaling_errors
  - drive_reconciliation_revealed_mistake_tags
```

#### 9.10.1 `Reconciliation_Run`

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `reconciliation_id` | string | yes | computed | Unique run ID |
| `period_start` | date | yes | manual | Start of reconciled period |
| `period_end` | date | yes | manual | End of reconciled period (typically last Sunday) |
| `scheduled_date` | date | yes | computed | When reconciliation was due |
| `completed_date` | date | yes | computed | When run was performed |
| `tos_export_filename` | string | yes | manual | TOS CSV filename for traceability |
| `trades_reconciled_count` | numeric | yes | computed | |
| `fills_reconciled_count` | numeric | yes | computed | |
| `discrepancies_count` | numeric | yes | computed | |
| `unresolved_discrepancies_count` | numeric | yes | computed | |
| `account_equity_journal` | numeric | yes | manual | Journal-tracked equity at period_end |
| `account_equity_tos` | numeric | yes | manual | TOS-reported equity at period_end |
| `equity_delta_dollars` | numeric | yes | computed | journal − tos |
| `equity_delta_pct` | numeric | yes | computed | |
| `notes` | text | no | manual | Run-level notes |

#### 9.10.2 `Reconciliation_Discrepancy`

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `discrepancy_id` | string | yes | computed | Unique ID |
| `reconciliation_id` | string | yes | linkage | Parent run |
| `trade_id` | string | conditional | linkage | If discrepancy is at trade level |
| `fill_id` | string | conditional | linkage | If discrepancy is at fill level |
| `field_name` | string | yes | manual | Which field disagrees |
| `journal_value` | text | yes | manual | What journal said |
| `tos_value` | text | yes | manual | What TOS shows |
| `delta` | text | conditional | computed | For numeric fields |
| `resolution` | enum | yes | manual | `journal_corrected`, `tos_treated_canonical`, `manual_override`, `unresolved` |
| `resolution_reason` | text | yes | manual | Why resolved this way |
| `resolved_date` | date | conditional | computed | When discrepancy was resolved |
| `mistake_tag_assigned` | string | conditional | linkage | Reconciliation-revealed mistake tag if applicable |
| `days_since_event` | numeric | yes | computed | Days between trade event and reconciliation discovery (memory-decay tracking) |

---

### 9.11 `Screenshots`

Purpose: Maintain a chart library indexed to trades and setups. Specified
in v1.1 (P9).

```yaml
tab: Screenshots
row_granularity: "one row per screenshot"
primary_key: screenshot_id
ai_use:
  - build_setup_pattern_library
  - support_post_trade_review
  - support_setup_drift_detection
```

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `screenshot_id` | string | yes | computed | Unique ID |
| `trade_id` | string | conditional | linkage | If screenshot is trade-specific |
| `setup_id` | string | conditional | linkage | If screenshot is a setup-library example |
| `capture_stage` | enum | yes | manual | `pre_trade`, `entered`, `mid_trade`, `exit`, `post_review`, `setup_library_ideal`, `setup_library_failed` |
| `capture_date` | date | yes | computed | |
| `image_path` | url | yes | manual | Path or URL |
| `annotations` | text | no | manual | What the screenshot demonstrates |
| `pattern_tags` | list | no | manual | Free-form tags for later retrieval |

---

### 9.12 `Daily_Screener_Log` (NEW required tab in v1.1)

Purpose: Capture Finviz screen runs and the tickers each screen produced.
Source of `source_screen` and `screen_criteria_snapshot` referenced by
Watchlist (N4).

```yaml
tab: Daily_Screener_Log
row_granularity: "one row per screener run (parent); many ticker entries per run (child)"
parent_entity: Screener_Run
child_entity: Screener_Ticker_Entry
ai_use:
  - source_attribution_for_watchlist
  - screen_to_trade_conversion_metrics
  - screen_level_expectancy_analysis
```

#### 9.12.1 `Screener_Run`

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `screener_run_id` | string | yes | computed | Unique run ID |
| `run_date` | date | yes | computed | Date of run |
| `screen_name` | string | yes | manual | Screen preset name (e.g. `RS_Leaders_Base`, `EP_Candidates`) |
| `screen_criteria_snapshot` | text | yes | manual | Free-text or JSON of filter criteria active when CSV was exported |
| `csv_export_filename` | string | yes | manual | Source filename for traceability |
| `tickers_returned_count` | numeric | yes | computed | |
| `notes` | text | no | manual | Free-text |

#### 9.12.2 `Screener_Ticker_Entry`

| Field | Type | Required | Source | Description |
|---|---:|---:|---|---|
| `screener_ticker_entry_id` | string | yes | computed | Unique ID |
| `screener_run_id` | string | yes | linkage | Parent run |
| `ticker` | string | yes | finviz_import | Symbol |
| `raw_screen_columns` | json/text | no | finviz_import | Captured columns from CSV (RS rank, market cap, ADR%, etc.) |
| `promoted_to_watchlist` | boolean | yes | computed | Whether trader added to Watchlist |
| `watchlist_entry_id` | string | conditional | linkage | If promoted |

Annotation pattern: at CSV import time, the trader either (a) supplies
`screen_name` and `screen_criteria_snapshot` interactively, or (b) names
the CSV file with a convention (e.g. `2026-05-01_RS_Leaders_Base.csv`)
that the import parser extracts. Either pattern is acceptable; the field
is required either way.

---

## 10. Core Formulas

Formulas updated in v1.1 to reflect the M2 / M3 / C5 / C13 / C15
dispositions and the N2 measurement convention.

### 10.1 Risk and Position Sizing

```text
risk_per_share = abs(planned_entry - initial_stop)
```

```text
planned_risk_dollars = account_equity_pre_trade * max_account_risk_pct
```

```text
planned_position_size = floor(planned_risk_dollars / risk_per_share)
```

```text
initial_risk_dollars = abs(actual_entry_price_first_fill - initial_stop)
                       * actual_position_size_at_first_fill
```

`initial_risk_dollars` is **immutable** after first fill. It is the
denominator for all R-multiple math on this trade.

### 10.2 Live At-Risk (NEW in v1.1; addresses M3)

```text
current_at_risk_dollars (longs) = (current_avg_cost - current_stop) * current_size
current_at_risk_dollars (shorts) = (current_stop - current_avg_cost) * current_size
```

```text
current_at_risk_R = current_at_risk_dollars / initial_risk_dollars
```

`current_at_risk_R` may be ≤ 0 once stop is moved to or beyond breakeven;
that is meaningful and should be displayed accordingly on the dashboard.

### 10.3 Portfolio Heat (M10, C15)

```text
portfolio_heat_dollars = sum(current_at_risk_dollars across open trades)
portfolio_heat_pct     = portfolio_heat_dollars / account_equity_now
```

`portfolio_heat_pre_trade` for a new trade is computed immediately before
its first fill, summing across already-open trades only.

### 10.4 P&L

```text
gross_pnl_dollars = sum over fills of (sign(action) * quantity * price)
                    where sign(entry|add) = -1 (cost out) and sign(trim|exit) = +1 (cash in)
                    plus net_position_market_value if not yet flat
```

```text
net_pnl_dollars = gross_pnl_dollars - fees_commissions
```

### 10.5 R-Multiples

```text
realized_R = net_pnl_dollars / initial_risk_dollars
```

#### MFE_R / MAE_R measurement convention (N2)

```text
entry_day_high = yfinance daily high on actual_entry_date
entry_day_low  = yfinance daily low  on actual_entry_date

entry_day_mfe_dollars (longs) = max(entry_day_high, actual_entry_price) - actual_entry_price
entry_day_mae_dollars (longs) = actual_entry_price - min(entry_day_low,  actual_entry_price)

mid_trade_mfe_dollars (longs) = max(daily_high) over (actual_entry_date+1 .. exit_date-1) - actual_entry_price
mid_trade_mae_dollars (longs) = actual_entry_price - min(daily_low) over same range

exit_day_mfe_dollars (longs) = max(daily_high_on_exit_date, exit_price_avg) - actual_entry_price
exit_day_mae_dollars (longs) = actual_entry_price - min(daily_low_on_exit_date,  exit_price_avg)

mfe_dollars = max(entry_day_mfe_dollars, mid_trade_mfe_dollars, exit_day_mfe_dollars)
mae_dollars = max(entry_day_mae_dollars, mid_trade_mae_dollars, exit_day_mae_dollars)

MFE_R = mfe_dollars / risk_per_share
MAE_R = mae_dollars / risk_per_share
```

(Sign convention: `MFE_R` and `MAE_R` are reported as non-negative
distances. Direction is implicit in the trade.)

For shorts, the high / low roles swap. The convention slightly overstates
entry-day MFE/MAE because intraday-before-fill bars cannot be excluded
without intraday data; this is acknowledged and accepted as the cost of
deterministic computation from public data.

#### Capture Ratio (C4)

```text
capture_ratio = realized_R / MFE_R    only when realized_R > 0 AND MFE_R > 0
              = n/a                    otherwise
```

`average_capture_ratio` excludes `n/a` rows.

### 10.6 Mistake Cost / Lucky Violation (C5)

```text
mistake_cost_R     = max(0, realized_R_if_plan_followed - actual_realized_R)
lucky_violation_R  = max(0, actual_realized_R           - realized_R_if_plan_followed)
```

Both are non-negative. Dashboard reports them separately and never nets
them. Counterfactual procedures per mistake category:

```yaml
counterfactual_procedures:
  CHASED:                     "plan: pass; counterfactual realized_R = 0"
  EARLY_ENTRY:                "plan: enter at trigger; reconstruct from charts"
  LATE_ENTRY:                 "plan: enter at trigger; reconstruct from charts"
  NO_SETUP:                   "plan: pass; counterfactual = 0"
  MOVED_STOP_AWAY:            "plan: exit at original stop on bar first hit; reconstruct"
  SOLD_TOO_EARLY:             "plan: exit per planned rule (target / trail / time); reconstruct"
  HELD_AFTER_INVALIDATION:    "plan: exit at close of invalidation bar; reconstruct"
  ADDED_TO_LOSER:             "plan: do not add; rerun P&L without the add"
  OVERSIZED:                  "plan: same outcome, scaled to planned size"
  REVENGE / FOMO / BOREDOM:   "counterfactual not measurable; tag mistake_cost_confidence=low"
```

When `mistake_cost_confidence = low`, the value is excluded from hard
portfolio totals and only used for qualitative review.

### 10.7 Aggregate Performance Metrics

```text
expectancy_R = mean(realized_R) over closed trades
```

```text
profit_factor = sum(realized_R | realized_R > 0) / abs(sum(realized_R | realized_R < 0))
```

```text
avg_win_R  = mean(realized_R | realized_R > 0)        # positive
avg_loss_R = mean(realized_R | realized_R < 0)        # natively negative

win_rate  = count(realized_R > 0) / count(closed_trades)
loss_rate = 1 - win_rate

expectancy_decomposed = (win_rate * avg_win_R) + (loss_rate * avg_loss_R)
```

Sign convention is explicit (C13): `avg_loss_R` is natively negative; do
not take absolute value.

### 10.8 Data Quality (P6)

```text
completeness_score(trade) =
  count(populated_required_fields_for_current_state) /
  count(required_fields_for_current_state)
  * 100
```

```text
data_quality_score(period) =
  mean(completeness_score across all trades active in period)
```

A trade in `closed` state with `process_grade` not yet assigned has
`completeness_score < 100`; this is the signal the post-trade review is
overdue.

### 10.9 Streak State (M8)

```text
current_consecutive_loss_count =
  walk back from most-recent closed trade until first realized_R > 0;
  count trades with realized_R < 0 along the way
```

```text
current_drawdown_R = peak_R_30_trade_window - cumulative_R_now
```

These feed Risk_Policy runtime state per §9.9.

---

## 11. Scoring Models

### 11.1 Pre-Trade Quality Score

Score each planned trade from 0 to 10 before entry. Components are
**binary** (C1) — a component is either fully met (its full point value)
or not met (0).

| Component | Points | Description |
|---|---:|---|
| Valid setup from active or pilot playbook | 2 | Setup exists and `status` is active or pilot |
| Market regime supportive | 1 | Broad market matches setup's `market_regime_allowed` |
| Sector / theme supportive | 1 | Sector is leading or improving |
| Clear catalyst or technical reason | 1 | Trade has a specific, named reason |
| Precise entry trigger | 1 | Trigger is observable and objective; `entry_trigger_type` chosen |
| Valid initial stop | 1 | Stop maps to thesis invalidation; `stop_type` is non-discretionary |
| Acceptable reward / risk | 1 | `planned_reward_risk_ratio >= 2.0` to first target |
| Correct position size | 1 | Size follows risk formula; no override or override is rule-based |
| Emotional state acceptable | 1 | `calm` or `confident`; not `FOMO`, `revenge`, `tired`, `impatient`, `anxious`, `bored` |

Decision rule:

```yaml
pre_trade_score_policy:
  score_8_to_10:
    action: "full planned risk allowed (subject to Risk_Policy runtime state)"
  score_6_to_7:
    action: "reduce size to 50% of planned, or wait for confirmation"
  score_0_to_5:
    action: "do not take trade"
```

Relationship to the pre-trade gate (P10): the gate (§12.1) is a *binary
prerequisite* — required fields populated, Risk_Policy runtime state
permitting. The quality score is a *downstream qualifier* that determines
size policy. Gate failure short-circuits scoring entirely; a trade that
fails the gate is never approved regardless of score.

### 11.2 Process Grade

Per-stage grades and overall composition (C3 disposition).

```yaml
per_stage_grades:
  entry_grade:
    A: "valid setup, correct size, clean execution, trigger followed"
    B: "minor deviation with little impact (slippage, minor doc gap)"
    C: "noticeable deviation (early or late entry, partial plan ambiguity)"
    D: "major rule break at entry (chased, oversized, no stop)"
    F: "no setup, revenge or FOMO entry, no risk plan"
  management_grade:
    A: "thesis tracked, stop discipline maintained, partials taken per plan"
    B: "minor management deviation; thesis-aligned"
    C: "ambiguous management; some emotional input"
    D: "moved stop away, ignored partial plan, added to loser"
    F: "abandoned plan entirely; emotional management"
  exit_grade:
    A: "exited per rule (stop, target, trail, time stop, thesis invalidation)"
    B: "minor exit deviation"
    C: "discretionary exit with weak rationale"
    D: "exited too early on emotion or held past invalidation"
    F: "panic or revenge exit"

overall_process_grade:
  rule: "worst of (entry_grade, management_grade, exit_grade)"
  if_any_F: "overall = F"
```

Process / outcome matrix:

```yaml
process_outcome_matrix:
  followed_plan_and_won:    disciplined_win
  followed_plan_and_lost:   disciplined_loss
  violated_plan_and_won:    lucky_violation        # populates lucky_violation_R
  violated_plan_and_lost:   execution_loss         # populates mistake_cost_R
```

The AI flags `lucky_violation` as dangerous because it positively
reinforces bad process. `lucky_violation_R` is reported alongside
`mistake_cost_R` but never as a benefit.

### 11.3 Self-Score Calibration (P4)

The dashboard tracks correlation between `pre_trade_quality_score` and
`realized_R` over rolling 50-trade windows. If correlation falls below
0.2 sustained across two windows, the AI flags the score as
non-predictive and recommends recalibrating component weights.

---

## 12. AI Evaluation Rules

### 12.1 Pre-Trade Gate

```yaml
pre_trade_gate:
  state_precondition: "trade in state planned"
  required_field_checks:
    - setup_id_exists_and_active_or_pilot
    - direction_matches_setup
    - market_regime_allowed_or_exception_explained
    - parent_watchlist_id_exists
    - thesis_specific
    - why_now_specific
    - invalidation_condition_exists
    - premortem_failure_reasons_count >= 3
    - planned_entry_present
    - initial_stop_present_and_type_non_discretionary_or_flagged
    - risk_per_share_positive
    - planned_position_size_calculated
    - planned_risk_dollars_within_max_account_risk_per_trade_pct
    - event_risk_present_with_handling
    - gap_risk_present_with_handling
    - emotional_state_pre_trade_logged
    - pre_trade_quality_score_present
  risk_policy_runtime_checks:
    - current_open_position_count < max_concurrent_positions
    - portfolio_heat_pct + planned_risk_dollars/equity <= max_portfolio_heat_pct
    - sector_concentration <= max_sector_concentration_positions
    - trading_halt_active == false
    - if size_reduction_active: planned_position_size <= size-reduced ceiling
  fail_action: "block state transition to triggered; mark trade incomplete; do not allow A-grade process"
```

### 12.2 In-Trade Gate

```yaml
in_trade_gate:
  state_precondition: "trade in state managing or partial_exited"
  questions:
    - "Is the original thesis still valid? (record thesis_status)"
    - "Has price action confirmed, weakened, or invalidated the thesis?"
    - "Has the market or sector regime changed?"
    - "Is the stop still logical based on the original plan?"
    - "If the stop moved, was the move rule-based?"
    - "Is the trader reacting to evidence or emotion?"
    - "Has MFE_to_date_R become large enough that the plan calls for a partial?"
    - "Has the time stop been reached?"
    - "Should this review record be daily_snapshot or event_log?"
  output:
    - thesis_status_classification
    - rule_violation_flags
    - recommended_record_type
    - recommended_action_if_any
```

### 12.3 Post-Trade Gate

```yaml
post_trade_gate:
  state_precondition: "trade in state closed; advancing to reviewed"
  required_outputs:
    - reconciliation_status_resolved
    - thesis_accuracy
    - setup_validity_after_review
    - entry_grade
    - management_grade
    - exit_grade
    - process_grade (computed: worst of three)
    - mistake_tags (with none_observed default)
    - mistake_cost_R (with confidence)
    - lucky_violation_R (with confidence)
    - lesson_learned
    - rule_change_candidate (with rule_change_id if true)
  guard_against_recommending_rule_changes:
    rule: "do not recommend a rule change after one trade unless the trade exposed a critical operational risk"
```

### 12.4 Reconciliation Gate (NEW in v1.1)

```yaml
reconciliation_gate:
  trigger: "weekly reconciliation run scheduled or initiated"
  inputs_required:
    - tos_export_csv
    - period_start
    - period_end
  steps:
    - import_tos_csv
    - match_fills_by_datetime_ticker_action
    - flag_unmatched_fills_on_either_side
    - compute_field_level_deltas
    - create_discrepancy_records_above_tolerance
    - update_reconciliation_status_on_each_fill_and_trade
    - assign_reconciliation_revealed_mistake_tags_where_applicable
    - update_account_equity_truth_from_tos
  output:
    - reconciliation_run_record
    - discrepancy_list
    - updated_trades_and_fills
    - mistake_tags_created
```

---

## 13. Dashboard Requirements

### 13.1 Required Portfolio Metrics

```yaml
dashboard_metrics:
  core_performance:
    - total_closed_trades
    - net_R
    - expectancy_R
    - win_rate
    - avg_win_R
    - avg_loss_R
    - profit_factor
    - median_R
    - max_drawdown_R
    - best_trade_R
    - worst_trade_R
    - average_holding_period_days
    - average_MFE_R
    - average_MAE_R
    - average_capture_ratio
  process_quality:
    - percent_trades_following_plan
    - mistake_count_total
    - mistake_cost_R_total
    - lucky_violation_R_total
    - process_grade_distribution
  account_state:
    - current_open_position_count
    - portfolio_heat_pct
    - current_consecutive_loss_count
    - current_drawdown_R
    - trading_halt_active
    - size_reduction_active
  data_quality:
    - data_quality_score_period
    - review_compliance_rate_period
    - reconciliation_compliance_rate_period
    - unreconciled_trade_count
    - unresolved_discrepancy_count
  self_score_calibration:
    - pre_trade_quality_score_vs_realized_R_correlation
    - confidence_score_vs_realized_R_correlation
```

### 13.2 Required Breakdowns

```yaml
dashboard_breakdowns:
  by_setup:
    - expectancy_R
    - sample_size
    - win_rate
    - avg_win_R
    - avg_loss_R
    - profit_factor
    - mistake_rate
  by_market_regime: [net_R, expectancy_R, drawdown_R]
  by_direction:     [long]   # short reserved for future scope expansion
  by_sector_theme:  [net_R, concentration_risk]
  by_setup_family:           [expectancy_R, sample_size]
  by_entry_trigger_type:     [expectancy_R, sample_size]
  by_exit_reason:            [stop_hit, target_hit, trailing_stop, time_stop, thesis_invalidated, discretionary]
  by_pre_trade_quality_score: [score_8_to_10, score_6_to_7, score_0_to_5]
  by_emotional_state_pre_trade: [calm, FOMO, revenge, tired, impatient, anxious, confident, bored]
  by_source_screen:          [expectancy_R, watchlist_to_trade_conversion_rate]
  by_time_on_watchlist:      [bucket_0_to_2_days, bucket_3_to_7_days, bucket_8_to_21_days, bucket_22_plus_days]
  by_catalyst:               [expectancy_R, sample_size]
  by_stop_type:              [average_MAE_R, stop_hit_rate]
```

### 13.3 Dashboard Interpretation Rules

```yaml
interpretation_rules:
  positive_edge_candidate:
    condition: "expectancy_R > 0 with sample_size >= 20 and acceptable drawdown"
  process_leak_candidate:
    condition: "profitable setup but percent_trades_following_plan < 0.7"
  setup_retirement_candidate:
    condition: "negative expectancy_R across sample_size >= 30 with no regime-specific explanation"
  emotional_leak_candidate:
    condition: "specific emotional state has materially worse expectancy_R or higher mistake_cost_R"
  exit_problem_candidate:
    condition: "high average_MFE_R but low average_capture_ratio"
  stop_problem_candidate:
    condition: "large average_MAE_R or frequent stop_hit before setup works"
  source_screen_attribution_actionable:
    condition: "screen has produced sample_size >= 15 trades with materially different expectancy from portfolio mean"
  self_score_uninformative:
    condition: "pre_trade_quality_score_vs_realized_R_correlation < 0.2 across two consecutive 50-trade windows"
  reconciliation_drifting:
    condition: "discrepancies_count trending up across last 4 reconciliation runs"
```

---

## 14. Review and Reconciliation Cadence

### 14.1 Daily Review

```yaml
daily_review:
  time_required: "5–10 minutes"
  required_actions:
    - update_open_trade_prices              # auto from yfinance batch
    - update_current_stops                   # manual confirm
    - classify_thesis_status                 # manual
    - log_market_and_sector_changes          # manual
    - record_any_management_action           # event_log if applicable
    - record_emotional_state                 # manual
    - check_for_rule_violations              # AI-assisted
  output:
    - open_trade_action_list
    - risk_exposure_summary
    - process_alerts
```

### 14.2 Weekly Review (Combined with Reconciliation)

```yaml
weekly_review:
  time_required: "60–90 minutes (includes reconciliation)"
  required_actions:
    - perform_weekly_reconciliation_against_tos_csv
    - resolve_or_log_discrepancies
    - assign_reconciliation_revealed_mistake_tags_where_applicable
    - review_closed_trades
    - calculate_net_R_and_expectancy_R
    - review_best_and_worst_trades
    - identify_top_mistake_tags_by_cost
    - review_missed_trades
    - update_screenshot_library
    - define_next_week_execution_focus
  output:
    - weekly_scorecard
    - reconciliation_run_record
    - top_3_lessons
    - top_1_behavioral_focus
    - rule_change_queue_updates
```

### 14.3 Monthly Review

```yaml
monthly_review:
  time_required: "60–120 minutes"
  required_actions:
    - evaluate_expectancy_by_setup_with_sample_size_thresholds
    - evaluate_expectancy_by_market_regime
    - compare_A_grade_trades_vs_others
    - review_drawdown_and_losing_streaks
    - quantify_total_mistake_cost_R
    - quantify_total_lucky_violation_R_for_awareness
    - review_circuit_breaker_activations
    - review_rule_change_candidates_meeting_threshold
    - audit_self_score_calibration
  output:
    - setup_keep_pause_retire_recommendations
    - risk_policy_review_recommendation
    - process_improvement_plan
```

### 14.4 Quarterly Review

```yaml
quarterly_review:
  required_actions:
    - evaluate_strategy_fit
    - decide_active_pilot_paused_retired_setups
    - review_position_sizing_rules
    - review_data_quality_and_journaling_compliance
    - review_reconciliation_compliance
    - compare_live_results_against_backtest_or_expectations_if_available
  output:
    - quarterly_strategy_memo
    - setup_playbook_update
    - risk_policy_update
    - next_quarter_constraints
```

---

## 15. AI Execution Workflows

### 15.1 Workflow: Create a New Journal

```yaml
workflow_create_new_journal:
  steps:
    - create_tabs:
        - Setup_Playbook
        - Trade_Log
        - Fills
        - Daily_Management
        - Watchlist
        - Daily_Screener_Log
        - Mistake_Tags
        - Review_Log
        - Rule_Change_Queue
        - Risk_Policy
        - Reconciliation_Log
        - Screenshots
        - Dashboard
    - define_controlled_vocabularies   # §8 enums seeded
    - populate_mistake_tags             # full v1.1 set including reconciliation tags
    - define_setup_ids                  # initial Setup_Playbook entries
    - establish_initial_risk_policy     # active row in Risk_Policy with author defaults
    - add_state_machine_validation
    - add_formula_columns
    - add_validation_rules
    - create_dashboard_pivots
    - test_with_sample_trade_through_full_state_machine
  acceptance_criteria:
    - every_trade_can_compute_realized_R
    - every_trade_links_to_setup_id_and_parent_watchlist_id
    - every_closed_trade_has_process_grade
    - dashboard_can_segment_by_setup_market_regime_and_source_screen
    - pre_trade_gate_blocks_trade_when_risk_policy_violated
    - reconciliation_run_can_complete_against_sample_tos_csv
    - pre_trade_lock_prevents_post_fill_edits_without_audit_entry
```

### 15.2 Workflow: Daily Screener Processing

```yaml
workflow_daily_screener_processing:
  input_required:
    - finviz_csv_export_files
    - screen_name_per_csv  # via filename convention or interactive prompt
  steps:
    - parse_each_csv
    - create_screener_run_record_per_csv
    - extract_screener_ticker_entries
    - prompt_trader_to_promote_tickers_to_watchlist
    - create_watchlist_entries_for_promoted_tickers
  output:
    - screener_run_records
    - watchlist_entries_created
```

### 15.3 Workflow: Evaluate a Proposed Trade

```yaml
workflow_evaluate_proposed_trade:
  input_required:
    - parent_watchlist_id
    - ticker
    - direction
    - setup_id
    - planned_entry
    - initial_stop
    - account_equity
    - max_risk_pct
    - thesis
    - invalidation_condition
    - market_regime
    - event_risk_present_and_handling
    - gap_risk_present_and_handling
    - emotional_state_pre_trade
  steps:
    - fetch_active_risk_policy
    - compute_risk_policy_runtime_state
    - run_pre_trade_gate
    - compute_pre_trade_quality_score
    - run_premortem_check
    - classify_trade_decision
  output:
    - approve_reduce_wait_or_reject
    - position_size  # respecting size_reduction_active
    - missing_fields
    - process_risks
    - trading_halt_active_with_reason_if_blocked
```

### 15.4 Workflow: Review an Open Trade

```yaml
workflow_review_open_trade:
  input_required:
    - trade_id
    - current_price                # auto from yfinance
    - current_stop
    - market_regime
    - sector_condition
    - thesis_status
    - emotional_state
  steps:
    - calculate_open_R
    - update_MFE_to_date_R_and_MAE_to_date_R   # from yfinance daily H/L since entry
    - compare_current_action_to_plan
    - detect_stop_rule_violation
    - check_time_stop
    - classify_record_type:  daily_snapshot or event_log
    - if_event_log: capture_full_event_fields
  output:
    - recommended_journal_action
    - rule_violation_flags
    - updated_management_record
```

### 15.5 Workflow: Review a Closed Trade

```yaml
workflow_review_closed_trade:
  input_required:
    - trade_id
    - fills (canonical)
    - exit_reason
    - final_chart
    - notes
  preconditions:
    - trade_state == closed
    - reconciliation_status in [reconciled_match, reconciled_discrepancy_resolved] OR
      explicit_unreconciled_review_acknowledgment == true
  steps:
    - calculate_net_pnl
    - calculate_realized_R
    - calculate_MFE_R_and_MAE_R_per_§10.5
    - calculate_capture_ratio_with_n/a_handling
    - classify_process_outcome_matrix
    - assign_entry_management_exit_grades
    - compute_overall_process_grade_as_worst_of_three
    - assign_mistake_tags_with_none_observed_default
    - compute_mistake_cost_R_and_lucky_violation_R_with_confidence
    - generate_lesson_learned
    - flag_rule_change_candidate_if_applicable
    - advance_state_to_reviewed
  output:
    - completed_trade_log_row_in_state_reviewed
    - trade_review_summary
    - possible_rule_change_candidate_with_id
```

### 15.6 Workflow: Weekly Reconciliation

```yaml
workflow_weekly_reconciliation:
  input_required:
    - tos_export_csv
    - period_start
    - period_end
  steps:
    - import_tos_csv
    - fuzzy_match_fills_by_ticker_action_datetime_quantity
    - flag_unmatched_fills_on_either_side
    - compute_field_level_deltas_against_journal_fills
    - create_discrepancy_records_above_tolerance
    - prompt_for_resolution_per_discrepancy
    - update_reconciliation_status_on_each_affected_fill_and_trade
    - assign_reconciliation_revealed_mistake_tags
    - reconcile_account_equity
  output:
    - reconciliation_run_record
    - updated_fills_and_trades
    - discrepancy_resolutions
    - new_mistake_tags_applied
```

### 15.7 Workflow: Weekly Performance Review

```yaml
workflow_weekly_review:
  preconditions:
    - workflow_weekly_reconciliation_completed_for_period
  steps:
    - filter_closed_trades_for_week
    - calculate_weekly_metrics
    - rank_mistakes_by_R_cost
    - rank_setups_by_expectancy
    - identify_lucky_violations
    - identify_disciplined_losses
    - check_circuit_breaker_state_history
    - generate_next_week_focus
  output:
    - weekly_review_record
    - behavioral_priority
    - setup_priority
    - risk_adjustment_if_needed
```

---

## 16. AI Evaluation Rubric for an Existing Journal

Use this rubric to score an existing swing trading journal from 0 to 100.

| Category | Weight | Criteria |
|---|---:|---|
| Pre-trade decision capture | 18 | Thesis, why now, invalidation, premortem (≥3), planned exit, emotional state, locked timestamp |
| Risk normalization | 18 | initial_risk_dollars (immutable), realized_R, MFE_R, MAE_R, current_at_risk_R distinct |
| Setup linkage | 12 | setup_id, playbook rules, setup-level performance |
| Source / origin tracing | 7 | parent_watchlist_id, source_screen propagation, time_on_watchlist_days |
| Execution tracking | 8 | Planned vs actual entry, slippage, order type, trigger compliance |
| In-trade management | 8 | Daily thesis status, stop changes (with prior-and-new), market / sector updates |
| Post-trade review | 8 | Process grade (worst-of-three), lesson, mistake tags, mistake_cost_R / lucky_violation_R distinction |
| Reconciliation | 6 | Weekly cadence, discrepancy log, reconciliation_status field |
| Operational enforcement | 5 | Risk_Policy with circuit breakers gating pre-trade approval |
| Analytics dashboard | 5 | Expectancy, win/loss stats, segmentation, mistake cost, data quality, calibration |
| Review cadence | 5 | Daily / weekly / monthly / quarterly review records with compliance tracking |

Score interpretation:

```yaml
journal_score_interpretation:
  90_to_100: "institutional-quality personal process system"
  75_to_89:  "strong journal with minor gaps"
  60_to_74:  "functional trade log but weak feedback loop"
  40_to_59:  "basic recordkeeping; insufficient for performance improvement"
  below_40:  "not yet a decision-quality journal"
```

---

## 17. Quality Gates and Failure Modes

### 17.1 Mandatory Conditions for an A-Grade Trade Process (revised in v1.1)

```yaml
A_grade_trade_process_requires:
  pre_trade:
    - thesis_specific_and_falsifiable
    - invalidation_condition_clear
    - initial_stop_present_and_non_discretionary
    - premortem_failure_reasons_count_at_least_3
    - planned_exit_strategy_present
    - position_size_correct_per_formula_or_rule_based_override
    - pre_trade_quality_score_recorded
    - emotional_state_pre_trade_logged
    - pre_trade_gate_passed_including_risk_policy_runtime_checks
    - pre_trade_locked_at_timestamp_written
  in_trade:
    - thesis_status_classified_at_each_review
    - stop_movements_have_prior_and_new_values_and_rule_based_reasons
    - daily_or_event_records_present_per_§9_4
    - emotional_state_logged
  post_trade:
    - exit_reason_categorized
    - process_grade_assigned_within_review_compliance_window  # see §17.2
    - mistake_tags_assigned_with_none_observed_default
    - mistake_cost_R_and_lucky_violation_R_assigned_with_confidence
    - lesson_learned_documented
  reconciliation:
    - reconciliation_status_in_[reconciled_match,reconciled_discrepancy_resolved,manual_override]
```

This replaces v1.0's circular `post_trade_review_completed` requirement
(C2): the requirement is now that the review occurs within a defined
window, not that it has occurred at all (which is what is being graded).

### 17.2 Review Compliance Window

```yaml
review_compliance_window:
  default_grace_period_days: 7
  requirement: "process_grade must be assigned within grace_period_days of exit_date"
  ai_behavior:
    - "warn at grace_period - 2 days"
    - "block A-grade after grace_period exceeded"
    - "track skipped reviews in Review_Log.skipped"
```

### 17.3 Common Journal Failure Modes (updated in v1.1)

```yaml
failure_modes:
  hindsight_rewrite:
    risk: "trader rewrites pre-trade fields after outcome is known"
    prevention: "pre_trade_locked_at timestamp; Pre_Trade_Edit_Audit log on any post-lock edit"
  outcome_bias_in_grading:
    risk: "process grade is unconsciously aligned to outcome"
    prevention: "process_grade composed from per-stage grades using worst-of rule; A-grade requires explicit rule-followed checklist"
  mistake_under_tagging:
    risk: "trader minimizes mistakes after profitable trades"
    prevention: "mistake_tags required with none_observed default; lucky_violation_R surfaces profitable rule violations explicitly"
  small_sample_rule_changes:
    risk: "rule changed after one or two trades"
    prevention: "minimum sample size required in Rule_Change_Queue; rule_change_id must be linked to supporting_trade_ids"
  selective_journaling:
    risk: "only memorable or impressive trades logged; routine wins / losses missed"
    prevention: "weekly reconciliation against TOS CSV produces FILL_NOT_LOGGED tags"
  missing_failed_setups:
    risk: "missed_trades not logged → bias toward only counting taken setups"
    prevention: "Missed_Trades captured in weekly review; review_compliance_rate metric"
  strategy_drift:
    risk: "subtle deviation from setup criteria over time"
    prevention: "setup_validity_after_review enum tracks marginal / invalid / lucky cases"
  reconciliation_drift:
    risk: "manual journal silently diverges from broker truth"
    prevention: "weekly reconciliation; discrepancies_count trend monitoring; account_equity reconcile"
  circuit_breaker_override_creep:
    risk: "trader overrides halt rules with weak rationale, normalizing deviation"
    prevention: "CIRCUIT_BREAKER_OVERRIDDEN mistake tag; Risk_Policy review on activation"
  gamed_self_scores:
    risk: "pre_trade_quality_score becomes reassurance ritual"
    prevention: "calibration tracking — score-vs-realized-R correlation must remain predictive"
  daily_management_friction_collapse:
    risk: "trader stops logging Daily_Management because field count is too high"
    prevention: "two-record-type model: daily_snapshot allowed on no-change days, event_log only when material event"
```

---

## 18. Recommended Implementation Order

Stages reflect the v1.1 architecture; each stage is shippable on its own.

### 18.1 Stage 1 — Architectural Foundation

```yaml
stage_1_foundation:
  build:
    - Setup_Playbook
    - Trade_Log with state machine fields
    - Fills as canonical execution source
    - Risk_Policy (active row with author defaults)
    - Watchlist
    - Daily_Screener_Log
  formulas:
    - risk_per_share, planned_position_size
    - initial_risk_dollars (locked at first fill)
    - current_at_risk_dollars, current_at_risk_R
    - portfolio_heat_pct
    - realized_R (closed trades)
  acceptance:
    - planned_to_entered_to_managing_to_closed_state_transitions_validate_required_fields
    - pre_trade_lock_writes_timestamp_at_first_fill
    - pre_trade_gate_blocks_when_risk_policy_violated
```

### 18.2 Stage 2 — Behavioral Capture

```yaml
stage_2_behavioral:
  build:
    - mistake_tags vocabulary
    - emotional_state_pre_trade and emotional_state in-trade
    - pre_trade_quality_score with binary components
    - premortem_failure_reasons (min 3)
    - process_grade with worst-of-three composition
    - mistake_cost_R / lucky_violation_R split with confidence
  acceptance:
    - profitable_rule_violation_correctly_increments_lucky_violation_R_not_mistake_cost_R
    - process_grade_F_when_any_stage_grade_F
    - none_observed_required_when_no_mistake_tags_apply
```

### 18.3 Stage 3 — Daily Management and Market Data

```yaml
stage_3_management:
  build:
    - Daily_Management with daily_snapshot and event_log record types
    - yfinance integration for current_price, MFE_to_date_R, MAE_to_date_R
    - stop_history via prior_stop / current_stop pair on every event_log record
  acceptance:
    - daily_snapshot_blocked_when_event_present
    - mfe_mae_R_compute_per_§10_5_convention
    - yfinance_outage_does_not_block_journaling
```

### 18.4 Stage 4 — Reconciliation

```yaml
stage_4_reconciliation:
  build:
    - Reconciliation_Log entity
    - TOS CSV import and matching
    - reconciliation_status on every fill and trade
    - reconciliation-revealed mistake tags
    - account_equity reconciliation
  acceptance:
    - sample_tos_csv_reconciles_against_seeded_journal
    - missing_fills_produce_FILL_NOT_LOGGED_tags
    - account_equity_delta_visible_on_dashboard
```

### 18.5 Stage 5 — Review and Dashboard

```yaml
stage_5_review_and_dashboard:
  build:
    - Review_Log with daily / weekly / monthly / quarterly types
    - dashboard metrics per §13
    - segmentation breakdowns per §13.2
    - data_quality_score and review_compliance_rate
    - self-score calibration tracking
  acceptance:
    - dashboard_segments_by_setup_market_regime_source_screen
    - review_skipped_flag_set_when_grace_period_exceeded
```

### 18.6 Stage 6 — Iteration and Tuning

```yaml
stage_6_iteration:
  build:
    - Rule_Change_Queue with sample-size enforcement
    - Missed_Trades capture in weekly review
    - Screenshots library
    - quarterly review automation
  acceptance:
    - rule_change_blocked_below_minimum_sample_size
    - missed_trade_expectancy_visible_alongside_taken_trade_expectancy
```

---

## 19. Example AI Prompts (updated for v1.1 vocabulary)

### 19.1 Pre-Trade Evaluation

```text
Evaluate this proposed trade against my journal v1.1 rules.

INPUT: ticker, parent_watchlist_id, setup_id, market_regime, planned_entry,
initial_stop, account_equity, max_risk_pct, thesis, why_now,
invalidation_condition, premortem_failure_reasons (list),
event_risk_present + handling, gap_risk_present + handling,
emotional_state_pre_trade.

DO:
- Run pre-trade gate including Risk_Policy runtime checks (open positions,
  portfolio heat, sector concentration, consecutive_losses, drawdown).
- Calculate planned_position_size and planned_risk_dollars.
- Score pre_trade_quality_score with binary components.
- Output one of: APPROVE | REDUCE_SIZE | WAIT | REJECT, with reasons.
- If REJECT or REDUCE due to circuit breaker, name the rule.
- List any missing required fields for state=planned.
```

### 19.2 In-Trade Review

```text
Given this trade in state managing, my plan, and the most recent
yfinance bar, classify thesis_status, recommend record_type
(daily_snapshot vs event_log), flag any rule violations (including
moved-stop-away), and produce the management record.
```

### 19.3 Post-Trade Review

```text
Given this closed trade with all Fills and a final chart, perform a
v1.1-compliant post-trade review:
- Verify reconciliation_status is reconciled or manual_override.
- Compute realized_R, MFE_R, MAE_R per the v1.1 measurement convention.
- Compute capture_ratio with n/a handling.
- Assign per-stage grades (entry, management, exit).
- Compute overall process_grade as worst of three.
- Assign mistake_tags (none_observed if no mistakes).
- Compute mistake_cost_R and lucky_violation_R separately, never netted.
- Tag mistake_cost_confidence per §8.12.
- Produce one lesson_learned and a rule_change_candidate flag with id if true.
- Advance state from closed to reviewed.
```

### 19.4 Weekly Reconciliation

```text
Reconcile this period's TOS CSV export against my journal Fills and
Trade_Log:
- Match fills by ticker, action, datetime, quantity within tolerance.
- Flag unmatched fills on either side.
- Create Reconciliation_Discrepancy rows for any field-level deltas.
- Assign reconciliation-revealed mistake tags where applicable.
- Reconcile account equity at period_end.
- Produce a Reconciliation_Run record and a discrepancy summary.
```

### 19.5 Weekly Performance Review (after Reconciliation)

```text
Given the past 7 days of closed and reviewed trades, produce:
- net_R, expectancy_R, win_rate, profit_factor, avg_win_R, avg_loss_R
- top 3 mistake tags by aggregate mistake_cost_R
- lucky_violation_R total, reported separately
- process_grade distribution
- circuit breaker activations
- review_compliance_rate and reconciliation_compliance_rate
- one behavioral focus and one setup focus for next week
```

### 19.6 Setup Performance Review

```text
For setup_id X over the last 90 days:
- expectancy_R, sample_size, win_rate
- average MFE_R and MAE_R
- average capture_ratio (excluding n/a rows)
- mistake_rate by mistake category
- breakdowns by market_regime, source_screen, time_on_watchlist bucket
- recommendation: keep | refine | pause | retire (subject to thresholds in §9.8)
```

### 19.7 Bias Detection Review

```text
Across the last 30 closed and reviewed trades, identify behavioral
patterns:
- Most expensive recurring mistake tag
- Correlation between emotional_state_pre_trade and realized_R
- pre_trade_quality_score vs realized_R correlation
- frequency of moved-stop-away and held-after-invalidation
- frequency of lucky_violation outcomes
- evidence of overtrading after losing streaks (CIRCUIT_BREAKER_OVERRIDDEN tag)
```

---

## 20. Final Recommended Mandatory Fields

This list is the canonical v1.1 required-set per state. It supersedes
v1.0 §16 and aligns with the canonical field names from §9.2 (C10 fix).

### 20.1 Trade_Log mandatory fields by state

```yaml
state_planned_minimum:
  - trade_id
  - parent_watchlist_id
  - state
  - ticker
  - direction
  - setup_id
  - planned_date
  - market_regime
  - catalyst
  - thesis
  - why_now
  - invalidation_condition
  - premortem_failure_reasons      # min 3
  - planned_entry
  - initial_stop
  - target_1
  - planned_position_size
  - planned_risk_dollars
  - portfolio_heat_pre_trade
  - event_risk_present
  - event_handling
  - gap_risk_present
  - gap_risk_handling
  - emotional_state_pre_trade
  - pre_trade_quality_score
  - final_pre_trade_decision
  - manual_entry_confidence

state_entered_additional:
  - actual_entry_price             # derived from Fills
  - actual_entry_date
  - actual_position_size           # derived from Fills
  - initial_risk_dollars           # locked here
  - pre_trade_locked_at            # timestamp written here
  - entry_trigger_type
  - entry_trigger_followed
  - reconciliation_status

state_closed_additional:
  - exit_date
  - exit_price_avg                 # derived from Fills
  - exit_reason
  - planned_exit_followed
  - net_pnl_dollars
  - realized_R
  - MFE_R
  - MAE_R
  - holding_period_days

state_reviewed_additional:
  - thesis_accuracy
  - setup_validity_after_review
  - entry_grade
  - management_grade
  - exit_grade
  - process_grade                  # computed worst-of-three
  - mistake_tags                   # 'none_observed' acceptable
  - mistake_cost_R                 # >= 0
  - lucky_violation_R              # >= 0
  - mistake_cost_confidence
  - lesson_learned
  - rule_change_candidate
  - rule_change_id                 # required if rule_change_candidate=true
  - reviewed_at
```

### 20.2 Daily_Management mandatory fields by record type

```yaml
daily_snapshot_minimum:
  - management_record_id
  - trade_id
  - record_type=daily_snapshot
  - review_date
  - current_price                  # auto from yfinance
  - current_stop
  - open_R
  - current_at_risk_R
  - MFE_to_date_R
  - MAE_to_date_R
  - thesis_status

event_log_additional:
  - prior_stop
  - stop_changed
  - stop_change_reason             # required if stop_changed=true
  - market_regime_change
  - sector_condition_change
  - action_taken
  - action_reason
  - emotional_state
  - rule_violation_suspected
```

### 20.3 Fills mandatory fields

```yaml
fills_minimum:
  - fill_id
  - trade_id
  - fill_datetime
  - action
  - quantity
  - price
  - reason
  - rule_based
  - manual_entry_confidence
  - reconciliation_status
```

### 20.4 Watchlist mandatory fields

```yaml
watchlist_minimum:
  - watchlist_entry_id
  - screener_run_id
  - ticker
  - added_date
  - source_screen
```

### 20.5 Risk_Policy mandatory fields (active row)

```yaml
risk_policy_minimum:
  - policy_id
  - effective_from
  - is_active
  - max_account_risk_per_trade_pct
  - max_concurrent_positions
  - max_portfolio_heat_pct
  - max_sector_concentration_positions
  - consecutive_losses_pause_threshold
  - consecutive_losses_pause_action
  - drawdown_pause_threshold_R
  - drawdown_pause_action
  - drawdown_recovery_threshold_R
```

### 20.6 Reconciliation_Run mandatory fields

```yaml
reconciliation_run_minimum:
  - reconciliation_id
  - period_start
  - period_end
  - completed_date
  - tos_export_filename
  - trades_reconciled_count
  - fills_reconciled_count
  - discrepancies_count
  - account_equity_journal
  - account_equity_tos
  - equity_delta_dollars
```

---

## 21. Changelog from v1.0 (NEW)

This section enumerates every substantive change relative to v1.0. Editorial
or stylistic changes are not listed.

### 21.1 New sections

```yaml
new_sections:
  - "§3 Scope and Constraints (explicit stock-only / single-account / live-only)"
  - "§6 Trade Lifecycle State Machine (states, transitions, required-field set per state)"
  - "§7 Field Source and Latency Taxonomy (source categories, latency tiers)"
  - "§8 Controlled Vocabularies (centralized enums for market_regime, catalyst, stop_type, setup_family, entry_trigger_type, exit_reason, thesis_status, thesis_accuracy, setup_validity_after_review, reconciliation_status, manual_entry_confidence, mistake_cost_confidence)"
  - "§21 Changelog (this section)"
```

### 21.2 New required tabs

```yaml
new_required_tabs:
  - Watchlist (was optional in v1.0)
  - Daily_Screener_Log (NEW)
  - Risk_Policy (NEW)
  - Reconciliation_Log (NEW)
```

### 21.3 New / modified entities

```yaml
new_entities:
  - Daily_Screener_Run, Screener_Ticker_Entry
  - Watchlist_Entry (formalized)
  - Pre_Trade_Edit_Audit
  - Reconciliation_Run, Reconciliation_Discrepancy
  - Risk_Policy
modified_entities:
  - Trade: added parent_watchlist_id, parent_trade_id, state, pre_trade_locked_at, manual_entry_confidence, reconciliation_status
  - Fill: added manual_entry_confidence, reconciliation_status, tos_match_id
  - Daily_Management_Record: added record_type, prior_stop, current_at_risk_R; split into daily_snapshot and event_log forms
```

### 21.4 New fields

```yaml
new_fields_trade_log:
  identity_and_state:
    - parent_watchlist_id (required)
    - parent_trade_id (conditional; re-entry linkage)
    - state (enum; drives required-field validation)
    - pre_trade_locked_at (timestamp; written at first fill, immutable)
    - reconciliation_status (enum)
    - manual_entry_confidence (enum)
  pre_trade_decomposition:
    - event_risk_present, event_type, event_date, event_handling (replaces v1.0 free-text event_risk)
    - gap_risk_present, gap_risk_handling (replaces v1.0 free-text gap_risk_plan)
    - catalyst (enum; was free-text in v1.0)
    - catalyst_other_description (conditional)
  risk_semantics:
    - current_avg_cost
    - current_size
    - current_at_risk_dollars (computed)
    - current_at_risk_R (computed)
  review_split:
    - mistake_cost_R (>= 0; harm only)
    - lucky_violation_R (>= 0; benefit only; replaces v1.0 sign-confused mistake_cost_R)
    - mistake_cost_confidence (enum)
    - entry_grade, management_grade, exit_grade (per-stage; process_grade computed as worst-of-three)
    - reviewed_at (timestamp)
    - rule_change_id (linkage; required if rule_change_candidate=true)

new_fields_review_log:
  - scheduled_date, completed_date, skipped, duration_minutes (P7)
  - data_quality_score (P6)
  - review_compliance_rate
  - reconciliation_compliance_rate
  - circuit_breaker_activations
  - total_lucky_violation_R (reported alongside total_mistake_cost_R, never netted)

new_fields_daily_management:
  - record_type (daily_snapshot | event_log)
  - prior_stop, stop_changed, stop_change_reason (preserves stop history; C12)
  - current_at_risk_R
```

### 21.5 Removed / replaced fields

```yaml
removed:
  - "v1.0 §5.2 'mistake_cost_R' single-sign field — replaced by mistake_cost_R + lucky_violation_R split (C5)"
  - "v1.0 §5.4 free-text event_risk — replaced by structured event_risk_* fields (P8)"
  - "v1.0 free-text gap_risk_plan — replaced by structured gap_risk_* fields (P8)"
  - "v1.0 paper-trading references in setup_status_rules.testing — replaced by 'reduced-size pilot' (C14)"
  - "v1.0 'short' value in setup_family enum — moved to direction field (C6)"
```

### 21.6 Definitional changes

```yaml
definitions_revised:
  initial_risk_dollars:
    v1_0: "abs(actual_entry - initial_stop) * actual_position_size"
    v1_1: "abs(actual_entry_price_first_fill - initial_stop) * actual_position_size_at_first_fill; immutable after first fill"
    rationale: "M2; clarifies pyramiding semantics"
  mistake_cost_R:
    v1_0: "(realized_R_if_plan_followed - actual_realized_R) — sign-confused; rewards lucky violations"
    v1_1: "max(0, realized_R_if_plan_followed - actual_realized_R); always >= 0"
    rationale: "C5"
  process_grade:
    v1_0: "A–F overall; composition rule unspecified"
    v1_1: "worst of (entry_grade, management_grade, exit_grade); F if any stage F"
    rationale: "C3"
  capture_ratio:
    v1_0: "realized_R / MFE_R; edge cases undefined"
    v1_1: "n/a unless realized_R > 0 and MFE_R > 0; excluded from average"
    rationale: "C4"
  pre_trade_quality_score:
    v1_0: "components could be partially scored; arithmetic visually misleading"
    v1_1: "components binary (0 or full points); valid_setup worth 2 explicitly noted"
    rationale: "C1"
  premortem_failure_reasons:
    v1_0: "minimum 1 reason"
    v1_1: "minimum 3 distinct reasons"
    rationale: "P5"
  MFE_R / MAE_R:
    v1_0: "convention unspecified; intraday assumed"
    v1_1: "yfinance daily H/L canonical; entry-day uses full daily H/L; intraday best-effort within yfinance lookback"
    rationale: "N2"
  expectancy_decomposed_sign:
    v1_0: "sign of avg_loss_R unstated"
    v1_1: "avg_loss_R is natively negative; do not take absolute value"
    rationale: "C13"
  portfolio_heat_pre_trade:
    v1_0: "calculation undefined"
    v1_1: "sum of current_at_risk_dollars across open trades immediately prior to new trade"
    rationale: "C15"
  setup_status_testing:
    v1_0: "paper trading, backtesting, or reduced size only"
    v1_1: "reduced-size pilot only (max 50% normal risk allocation)"
    rationale: "C14; paper trading out of scope"
```

### 21.7 New behaviors

```yaml
new_behaviors:
  pre_trade_lock:
    description: "first fill writes pre_trade_locked_at and renders pre-trade fields read-only"
    enforcement: "explicit override action with audit log entry to Pre_Trade_Edit_Audit"
    rationale: "M6"
  state_machine_validation:
    description: "trade cannot advance to next state if state-specific required fields are missing or fail validation"
    rationale: "M1"
  risk_policy_runtime_enforcement:
    description: "pre_trade_gate consults Risk_Policy runtime state (open positions, portfolio heat, consecutive losses, drawdown) and may BLOCK or REDUCE_SIZE"
    rationale: "M8, M10, §4.3"
  weekly_reconciliation_workflow:
    description: "weekly TOS CSV import, fuzzy fill matching, discrepancy logging, reconciliation-revealed mistake tagging"
    rationale: "N1"
  source_screen_propagation:
    description: "source_screen captured at Daily_Screener_Log import flows through Watchlist to Trade"
    rationale: "N4"
  daily_management_record_typing:
    description: "daily_snapshot allowed only on no-change days; event_log required when material event occurs"
    rationale: "P2"
  re_entry_linkage:
    description: "re-entries are discrete trades with parent_trade_id linkage within 30-day window"
    rationale: "M9"
  mistake_tags_required_with_default:
    description: "mistake_tags required on every reviewed trade; none_observed is a valid value"
    rationale: "C8"
  rule_change_link:
    description: "rule_change_candidate=true requires creation of rule_change_id and population of supporting_trade_ids"
    rationale: "C9"
  review_compliance_window:
    description: "process_grade must be assigned within grace_period_days of exit_date"
    rationale: "C2 (replaces circular post_trade_review_completed requirement)"
  self_score_calibration:
    description: "dashboard tracks pre_trade_quality_score vs realized_R correlation; flags when score becomes non-predictive"
    rationale: "P4"
  data_quality_metric:
    description: "completeness_score per trade and data_quality_score per period drive dashboard alerts"
    rationale: "P6"
```

### 21.8 Scope simplifications

```yaml
scope_removed_in_v1_1:
  - options_workflow_language
  - futures_workflow_language
  - multi_account_account_id_segregation
  - paper_trading_workflow_language
  - intraday_day_trading_assumptions
rationale: "v1.0 carried defensive optionality for these; author confirmed all out of scope. Removal sharpens vocabulary and removes maintenance burden."
```

### 21.9 Concerns raised about author's stated approach

```yaml
concerns_addressed_in_v1_1:
  monthly_reconciliation_proposed:
    raised_concern: "memory decay, compounding errors, behavioral signal latency"
    v1_1_resolution: "weekly cadence adopted; co-located with weekly review"
  finviz_csv_lacks_screen_metadata:
    raised_concern: "screen-level expectancy attribution requires manual capture"
    v1_1_resolution: "Daily_Screener_Log requires screen_name and screen_criteria_snapshot at import"
  consecutive_losses_rule_not_in_spec:
    raised_concern: "author's stated 3-consecutive-losses pause rule had no operational hook in v1.0"
    v1_1_resolution: "Risk_Policy entity encodes the rule; pre_trade_gate enforces it"
```

---

## 22. Reference List

The following sources informed the design choices in this specification.
References are listed by author and topic; specific publications are not
fully cited because this is an internal design document, not a research
paper.

```yaml
references:
  decision_quality_and_journaling:
    - "Daniel Kahneman — Thinking, Fast and Slow (decision capture, hindsight bias)"
    - "Gary Klein — Sources of Power; The Power of Intuition (premortem methodology)"
    - "Annie Duke — Thinking in Bets (decision-quality vs outcome-quality framing)"
  risk_and_expectancy:
    - "Van K. Tharp — Trade Your Way to Financial Freedom (R-multiple framework, expectancy)"
    - "Ralph Vince — position sizing literature"
  behavioral_finance:
    - "Brad Barber and Terrance Odean — overtrading and overconfidence research"
    - "Hersh Shefrin — Beyond Greed and Fear"
    - "CFA Institute — behavioral finance curriculum"
  swing_trading_practitioners:
    - "Mark Minervini — Trade Like a Stock Market Wizard; Think and Trade Like a Champion (VCP, pivot points, progressive exposure, leadership criteria)"
    - "Stan Weinstein — Secrets for Profiting in Bull and Bear Markets (stage analysis)"
    - "William O'Neil — How to Make Money in Stocks (CANSLIM, base patterns)"
    - "Nicolas Darvas — How I Made $2,000,000 in the Stock Market (box theory)"
    - "Gil Morales and Chris Kacher — Trade Like an O'Neil Disciple"
    - "Kristjan Kullamäggi (Qullamaggie) — episodic pivot and high-tight-flag patterns"
  audit_and_reconciliation:
    - "General accounting practice — reconciliation cadence, source-of-truth designation, discrepancy logging"
```

---

*End of v1.1 specification.*
