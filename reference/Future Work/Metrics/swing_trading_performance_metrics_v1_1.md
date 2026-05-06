---
title: "Swing Trading Performance Metrics Specification"
version: "standalone-1.1"
document_type: "performance_metrics_execution_specification"
prior_version: "standalone-1.0"
companion_document: "swing_trading_metrics_v1_1_findings.md"
created_for:
  - AI orchestrator review
  - Python swing trading tool implementation
  - deterministic metrics engine design
  - deterministic rules engine design
created_date: "2026-05-05"
revised_date: "2026-05-05"
timezone_context: "Pacific/Honolulu"
storage_timezone: "UTC"
trading_calendar: "NYSE"
not_financial_advice: true
primary_design_goal: "Define the fundamental data, derived facts, metrics, dashboards, and deterministic rule triggers required to convert a swing trading journal into performance-related information."
production_assumption: "The production path should rely on structured data, deterministic formulas, and explicit rules. LLM inference is optional for summaries and research, not required for core performance evaluation."
trading_style_context:
  style: "swing trading"
  instrument_scope_default: "stocks"
  direction_scope: "long_only"
  expected_concurrent_open_positions: "fewer than 10"
  expected_holding_period: "days to weeks"
  expected_trade_frequency: "low to moderate"
  account_currency_default: "USD"
  design_implications:
    - "Portfolio-level unrealized P&L and open risk matter because positions remain open across days or weeks."
    - "Sample sizes accumulate slowly, so all aggregate metrics require reliability labels."
    - "The system should favor review tasks and recommendation candidates over automatic strategic conclusions."
    - "Dashboards should emphasize clarity, exposure, concentration, drawdown, and process quality rather than high-frequency statistics."
---

# Swing Trading Performance Metrics Specification

## 0. Purpose

This document defines a standalone performance metrics layer for a swing trading journal or Python-based swing trading tool.

The journal records trade plans, fills, trade management events, account snapshots, and reviews. The performance layer converts that raw data into measurable information about:

```yaml
performance_domains:
  portfolio_performance:
    question: "Is the account growing efficiently and survivably?"
  trade_performance:
    question: "Are individual trades profitable per unit of risk?"
  setup_performance:
    question: "Which setups have measurable edge?"
  process_performance:
    question: "Is execution behavior helping or hurting results?"
  risk_performance:
    question: "Is risk appropriate for the return achieved?"
  data_quality:
    question: "Are the metrics trustworthy enough to act on?"
```

The production system should not require AI inference to generate metrics, alerts, review tasks, or recommendation candidates. Those outputs should be generated from structured data and deterministic rules.

```yaml
production_model:
  metrics_engine:
    responsibility:
      - compute derived trade, portfolio, setup, process, and risk facts
      - aggregate metrics across time windows and dimensions
      - label metric reliability based on sample size and data quality
  rules_engine:
    responsibility:
      - evaluate explicit rule conditions
      - trigger warnings, hard blocks, review tasks, and recommendation candidates
      - attach evidence to every triggered output
  human_review:
    responsibility:
      - interpret ambiguous causes
      - approve strategy rule changes
      - decide whether recommendation candidates become actual changes
  optional_ai_assist:
    allowed_use:
      - summarize results
      - draft weekly/monthly reports
      - explain metrics
      - help review evidence
    prohibited_as_required_production_dependency:
      - deciding whether a setup visually qualifies from a chart
      - inferring psychology from prose
      - making automatic rule changes
      - approving automatic size increases
```

### 0.1 Scope and Conventions

This specification covers **long-only stock swing trading** with a default account currency of **USD**. Short-side coverage is intentionally out of scope for v1.1; see §22 for the formal direction-conventions stub.

**Sign and timing conventions used throughout:**

```yaml
core_conventions:
  drawdown:
    sign: "always <= 0; thresholds in Risk_Policy must be expressed as negative"
  raw_current_at_risk_dollars:
    sign: "positive = at risk vs entry; negative = locked-in profit at stop"
  cash_flow_timing_in_TWR:
    convention: "external cash flows treated as posting at start-of-day; start_equity is cash-flow-adjusted"
  fees_in_realized_pnl:
    convention: "net_pnl_dollars and realized_R are net of fees and commissions"
  trading_day:
    definition: "NYSE trading day; non-trading days produce no snapshot row; half-days count as full snapshot days"
  storage_timezone:
    convention: "all stored timestamps in UTC; user-facing display in Pacific/Honolulu is presentation-only"
  scratch_trade:
    definition: "abs(realized_R) < scratch_epsilon (default 0.10, configurable in Risk_Policy)"
  initial_risk_dollars:
    convention: "locked at first fill from Trade_Plans.planned_risk_dollars; immutable for life of trade"
```

---

## 1. Swing Trading Design Constraints

This specification is designed for swing trading rather than intraday trading.

```yaml
swing_trading_constraints:
  concurrent_open_positions:
    expected: "<10"
    metric_implication: "Open-position table can be human-readable and position-specific; no need for high-frequency aggregation UX."
  holding_period:
    expected: "days_to_weeks"
    metric_implication: "Daily account snapshots and end-of-day open trade metrics are sufficient for the minimum viable production system."
  trade_frequency:
    expected: "low_to_moderate"
    metric_implication: "Setup-level conclusions require sample-size guards. A month may not provide enough trades for strong strategy conclusions."
  open_risk:
    expected: "material"
    metric_implication: "Portfolio performance must include unrealized P&L, portfolio heat, exposure, and thesis status of open positions."
```

### 1.1 Low-Volume Guardrails

Because swing trading produces relatively few trades, the system must avoid overconfident conclusions from small samples.

```yaml
sample_size_policy:
  individual_trade_review:
    minimum_sample_size: 1
    allowed_interpretation: "Valid for reviewing that one trade only."
  early_setup_signal:
    minimum_sample_size: 10
    allowed_interpretation: "Early signal in either direction; create review task if concerning, but do not pause or retire setup."
  setup_review_candidate:
    minimum_sample_size: 20
    allowed_interpretation: "Enough to trigger structured review or pause candidate."
  setup_retirement_candidate:
    minimum_sample_size: 30
    allowed_interpretation: "Minimum for retire candidate if process quality is acceptable and data quality is high."
  portfolio_trend_initial:
    minimum_trading_days: 20
    allowed_interpretation: "Initial account trend only."
  benchmark_comparison_candidate:
    minimum_trading_days: 60
    allowed_interpretation: "Enough to begin benchmark-relative review."
  pre_trade_score_calibration:
    minimum_trades: 30
    allowed_interpretation: "Provisional score calibration; stronger after 50+ trades."
  risk_adjusted_return_provisional:
    minimum_monthly_returns: 12
    allowed_interpretation: "Sharpe/Sortino computable but provisional only."
  risk_adjusted_return_actionable:
    minimum_monthly_returns: 24
    allowed_interpretation: "Sharpe/Sortino actionable."
```

### 1.2 Metric Reliability Labels

Every aggregate metric should include a reliability label.

```yaml
metric_reliability_labels:
  insufficient_sample:
    condition: "sample_size below required minimum"
    behavior: "display metric but suppress strong conclusions"
  provisional:
    condition: "sample_size meets early threshold but not action threshold"
    behavior: "allow review task; suppress pause/retire candidate"
  actionable:
    condition: "sample_size meets action threshold and data_quality_score >= required minimum"
    behavior: "allow recommendation candidate"
  high_confidence:
    condition: "sample_size materially exceeds action threshold and result persists across multiple windows"
    behavior: "allow stronger recommendation candidate such as pause, retire, or risk policy review"
```

---

## 2. Fundamental Data Required

Performance metrics are only as good as the underlying data. The system must collect or derive the following data categories.

```yaml
required_data_categories:
  account_data:
    - daily account equity / net liquidation value
    - cash balance
    - deposits and withdrawals
    - dividends and interest received
    - realized and unrealized P&L
    - fees and commissions
  position_data:
    - open position size
    - average cost
    - market value
    - current stop
    - current at-risk dollars (relative to entry)
    - unrealized P&L
    - open MFE/MAE to date
  trade_plan_data:
    - setup_id
    - planned entry
    - initial stop
    - planned risk dollars
    - planned position size
    - thesis and invalidation
    - pre-trade quality score
    - market regime and catalyst
  execution_data:
    - fills
    - fill timestamps
    - fill prices
    - fill quantities
    - order actions
    - fees
  trade_outcome_data:
    - exit date
    - exit price (volume-weighted across exit fills)
    - net P&L (net of fees)
    - realized R
    - MFE_R
    - MAE_R
    - capture ratio
    - giveback variants
  process_data:
    - process grade
    - entry grade
    - management grade
    - exit grade
    - mistake tags
    - mistake_cost_R
    - mistake_cost_method
    - lucky_violation_R
  context_data:
    - setup family
    - source screen or trade origin
    - market regime
    - sector / theme
    - benchmark prices
  corporate_action_data:
    - splits, reverse splits, stock dividends
    - cash dividends
    - ticker changes, mergers, spinoffs
  data_quality_data:
    - reconciliation status
    - completeness score
    - unresolved discrepancies
    - stale open trade count
```

The minimum viable production system should prioritize account equity snapshots, fills, trade plan fields, open position snapshots, and reconciliation status before building advanced analytics.

---

## 3. Required Source Tables

The following tables define the fundamental data needed to support performance metrics. Table names are suggestions; an implementation may use database tables, files, dataframes, or ORM models as long as the fields are represented.

### 3.1 `Account_Equity_Snapshots`

Purpose: Capture daily account-level truth. This table powers portfolio performance, drawdown, returns, exposure, and benchmark comparisons.

```yaml
table: Account_Equity_Snapshots
grain: one_row_per_trading_day
recommended_source: broker_export_or_manual_then_reconciled
required_for:
  - portfolio equity curve
  - daily return
  - drawdown
  - exposure
  - cash allocation
  - portfolio heat percentage
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `snapshot_date` | date | yes | NYSE trading day represented by the snapshot |
| `account_currency` | string | yes | ISO 4217 code; default `USD` |
| `account_equity` | numeric | yes | Account value / net liquidation value at snapshot time |
| `net_liquidation_value` | numeric | yes | Broker-reported total account value; may equal account_equity |
| `cash_balance` | numeric | yes | Cash available at snapshot time |
| `long_market_value` | numeric | yes | Total market value of long positions |
| `short_market_value` | numeric | no | Reserved for future short-side support; default 0 in v1.1 |
| `gross_exposure` | numeric | yes | Sum of absolute market values of open positions |
| `net_exposure` | numeric | yes | Long market value minus short market value (= long_market_value in v1.1) |
| `realized_pnl_day` | numeric | no | Broker-reported realized P&L for the day |
| `unrealized_pnl_day` | numeric | no | Change in unrealized P&L for the day |
| `total_pnl_day` | numeric | no | Realized plus unrealized P&L for the day |
| `deposits_day` | numeric | yes | External deposits credited that day; default 0 |
| `withdrawals_day` | numeric | yes | External withdrawals debited that day; default 0 |
| `dividends_day` | numeric | no | Cash dividends received that day; counts as trading return |
| `interest_day` | numeric | no | Interest received that day; counts as trading return |
| `fees_commissions_day` | numeric | no | Fees and commissions charged that day |
| `reconciliation_status` | enum | yes | See §21 |
| `data_source` | enum | yes | See §21 |

### 3.2 `Cash_Flows`

Purpose: Separate trading performance from deposits, withdrawals, and transfers. Dividends and interest are recorded here as well, but they count as trading return (`external_to_trading=false`) and are excluded from the cash-flow adjustment in §5.2.

```yaml
table: Cash_Flows
grain: one_row_per_external_cash_flow
required_for:
  - adjusted daily P&L
  - time-weighted return
  - accurate portfolio return reporting
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `cash_flow_id` | string | yes | Unique identifier |
| `date` | date | yes | Date of cash flow |
| `amount` | numeric | yes | Positive for inflow, negative for outflow |
| `currency` | string | yes | ISO 4217; default `USD` |
| `type` | enum | yes | See §21 |
| `external_to_trading` | boolean | yes | True for deposits/withdrawals/transfers; false for dividends/interest |
| `notes` | text | no | Explanation or broker reference |
| `reconciliation_status` | enum | yes | Status against broker truth |

### 3.3 `Positions_Daily_Snapshots`

Purpose: Capture open positions at end of day. This is essential for swing trading because open positions may remain active for days or weeks.

```yaml
table: Positions_Daily_Snapshots
grain: one_row_per_open_position_per_trading_day
required_for:
  - unrealized P&L
  - exposure
  - concentration
  - current at-risk capital
  - open thesis review
  - portfolio heat
  - open MFE/MAE tracking
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `snapshot_date` | date | yes | NYSE trading day represented |
| `trade_id` | string | yes | Linked trade |
| `ticker` | string | yes | Symbol (current; ticker changes tracked in `Corporate_Actions`) |
| `instrument_currency` | string | no | ISO 4217; null implies same as account_currency |
| `quantity_open` | numeric | yes | Current open share quantity (positive integer; long-only in v1.1) |
| `avg_cost` | numeric | yes | Current average cost per share, after corporate-action adjustments |
| `close_price` | numeric | yes | End-of-day price |
| `market_value` | numeric | yes | `quantity_open * close_price` (in account currency after FX if applicable) |
| `unrealized_pnl_dollars` | numeric | yes | Open P&L in account currency |
| `unrealized_R` | numeric | yes | Open P&L normalized by initial risk |
| `current_stop` | numeric | yes | Current stop level |
| `raw_current_at_risk_dollars` | numeric | yes | `(avg_cost - current_stop) * quantity_open`; positive = at risk vs entry, negative = locked-in profit at stop |
| `portfolio_heat_contribution_dollars` | numeric | yes | `max(0, raw_current_at_risk_dollars)` |
| `locked_in_profit_at_stop_dollars` | numeric | yes | `max(0, -raw_current_at_risk_dollars)` |
| `current_at_risk_R` | numeric | yes | `raw_current_at_risk_dollars / initial_risk_dollars` |
| `open_MFE_to_date_R` | numeric | yes | Highest unrealized_R observed since first fill |
| `open_MAE_to_date_R` | numeric | yes | Lowest unrealized_R observed since first fill |
| `mfe_mae_precision_level` | enum | yes | See §21 and §8.2 |
| `thesis_status` | enum | no | See §21 |
| `sector` | string | no | Sector or industry group |
| `setup_id` | string | yes | Setup linked to the trade |

### 3.4 `Trade_Plans`

Purpose: Capture the intended trade before outcome knowledge. This supports R normalization, process evaluation, and planned-versus-actual analysis.

```yaml
table: Trade_Plans
grain: one_row_per_planned_trade
required_for:
  - planned risk
  - planned reward/risk
  - process review
  - pre-trade quality scoring
  - planned versus actual analysis
locked_field_set:
  description: "Fields locked at first fill via pre_trade_locked_at; subsequent edits require explicit override and audit row"
  fields:
    - planned_entry
    - initial_stop
    - risk_per_share
    - planned_position_size
    - planned_risk_dollars
    - planned_reward_risk_ratio
    - target_1
    - target_2
    - setup_id
    - market_regime
    - catalyst
    - thesis
    - invalidation_condition
    - premortem_failure_reasons
    - pre_trade_quality_score
    - emotional_state_pre_trade
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `trade_id` | string | yes | Unique trade ID |
| `ticker` | string | yes | Symbol at time of planning |
| `direction` | enum | yes | `long` only in v1.1 |
| `instrument_currency` | string | no | ISO 4217; null implies same as account_currency |
| `fx_rate_at_entry` | numeric | no | Required when instrument_currency != account_currency |
| `setup_id` | string | yes | Linked setup |
| `trade_origin` | enum | yes | See §21 |
| `source_screen` | string | conditional | Required when trade_origin is `screen` or `watchlist` derived from a screen |
| `planned_date` | date | yes | Planning date; used for risk-policy lookup |
| `planned_entry` | numeric | yes | Intended entry price |
| `initial_stop` | numeric | yes | Planned initial stop |
| `risk_per_share` | numeric | yes | `planned_entry - initial_stop` (long-only convention; positive value) |
| `planned_position_size` | numeric | yes | Planned shares (full intended position, including any planned scale-ins) |
| `planned_risk_dollars` | numeric | yes | Risk in dollars at initial stop for the full planned position |
| `planned_reward_risk_ratio` | numeric | no | Planned target reward divided by initial risk |
| `target_1` | numeric | no | First target |
| `target_2` | numeric | no | Second target |
| `market_regime` | enum | yes | See §21; locked at first fill |
| `sector_condition` | enum | no | See §21 |
| `catalyst` | enum | yes | See §21; may be `technical_only` |
| `thesis` | text | yes | Why trade should work |
| `invalidation_condition` | text | yes | What proves the thesis wrong |
| `premortem_failure_reasons` | list[text] | yes | Recommended minimum 3 reasons |
| `pre_trade_quality_score` | numeric | yes | 0-10 score or equivalent |
| `emotional_state_pre_trade` | list[enum] | yes | See §21 |
| `pre_trade_locked_at` | datetime | conditional | Set at first fill; protects hindsight integrity |
| `risk_policy_version` | integer | yes | Snapshot of `Risk_Policy.policy_version` effective on `planned_date` |

### 3.5 `Fills`

Purpose: Represent actual broker execution. Fills are the source of truth for entries, exits, partials, position size, and realized P&L.

```yaml
table: Fills
grain: one_row_per_broker_fill
required_for:
  - actual entry price (volume-weighted)
  - actual exit price (volume-weighted)
  - actual position size
  - slippage
  - realized P&L
  - reconciliation
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `fill_id` | string | yes | Unique fill ID |
| `trade_id` | string | yes | Linked trade |
| `fill_datetime` | datetime | yes | Fill timestamp (UTC) |
| `ticker` | string | yes | Symbol at time of fill |
| `action` | enum | yes | See §21 |
| `quantity` | numeric | yes | Filled quantity |
| `price` | numeric | yes | Fill price in instrument currency |
| `fees` | numeric | no | Fees or commissions for this fill |
| `order_type` | enum | no | See §21 |
| `rule_based` | boolean | yes | Whether fill followed the plan |
| `manual_entry_confidence` | enum | no | `high`, `normal`, `low` |
| `reconciliation_status` | enum | yes | Status against broker export |
| `corporate_action_id` | string | no | Set when fill is the result of a corporate action (e.g., merger cash-out) |

### 3.6 `Trade_Reviews`

Purpose: Capture post-trade process and behavioral information.

```yaml
table: Trade_Reviews
grain: one_row_per_closed_trade_review
required_for:
  - process performance
  - mistake cost
  - lucky violation tracking
  - setup validity review
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `trade_id` | string | yes | Linked trade |
| `reviewed_at` | datetime | yes | Review timestamp (UTC) |
| `thesis_accuracy` | enum | yes | See §21 |
| `setup_validity_after_review` | enum | yes | See §21 |
| `entry_grade` | enum | yes | A-F or numeric equivalent |
| `management_grade` | enum | yes | A-F or numeric equivalent |
| `exit_grade` | enum | yes | A-F or numeric equivalent |
| `process_grade` | enum | yes | Overall process grade |
| `mistake_tags` | list[enum] | yes | See §21; use `none_observed` when none apply |
| `mistake_cost_R` | numeric | yes | Non-negative R harm from rule violations; see §10.2 for methodology |
| `mistake_cost_method` | enum | yes | `direct_measurement`, `counterfactual_estimate`, `bracketed_range` |
| `mistake_cost_confidence` | enum | yes | `high`, `medium`, `low` |
| `lucky_violation_R` | numeric | yes | Non-negative R benefit from profitable rule violation |
| `lesson_learned` | text | no | Human-readable note |

### 3.7 `Market_Context_Daily`

Purpose: Store market and benchmark context for regime-aware performance analysis.

```yaml
table: Market_Context_Daily
grain: one_row_per_trading_day
required_for:
  - benchmark comparison
  - regime segmentation
  - exposure-in-regime rules
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `date` | date | yes | NYSE trading day |
| `market_regime` | enum | yes | Manual or deterministic classification |
| `regime_classified_at` | datetime | yes | Timestamp (UTC) when classification was logged |
| `regime_classified_post_close` | boolean | yes | True if `regime_classified_at` is after the NYSE close of `date`; flags hindsight risk |
| `benchmark_symbol` | string | yes | Example: SPY, QQQ, IWM |
| `benchmark_close` | numeric | yes | Benchmark close |
| `benchmark_daily_return_pct` | numeric | yes | Benchmark daily return |
| `index_above_50dma` | boolean | no | Optional deterministic regime input |
| `index_above_200dma` | boolean | no | Optional deterministic regime input |
| `breadth_metric` | numeric | no | Optional breadth input |
| `volatility_regime` | enum | no | `low`, `normal`, `high`, `extreme` |

### 3.8 `Setup_Playbook`

Purpose: Define setups so performance can be segmented by actual strategy. The current `status` is a derived view of the most recent row in `Setup_Status_History` (§3.11).

| Field | Type | Required | Description |
|---|---:|---:|---|
| `setup_id` | string | yes | Unique setup ID |
| `setup_name` | string | yes | Human-readable setup name |
| `setup_family` | enum | yes | See §21 |
| `status` | enum | yes | Derived from `Setup_Status_History`; see §21 |
| `market_regime_allowed` | list[enum] | no | Regimes where setup is allowed |
| `entry_rule` | text | yes | Objective entry definition |
| `stop_rule` | text | yes | Objective stop definition |
| `exit_rule` | text | yes | Objective exit definition |

### 3.9 `Risk_Policy`

Purpose: Define account-level limits used by metrics and deterministic rules. Versioned: each `Trade_Plans` row records the policy version effective on its `planned_date`, so historical metric evaluations remain stable when the policy changes.

```yaml
table: Risk_Policy
grain: one_row_per_policy_version
versioning:
  rule: "exactly one row may have a null effective_to (the currently active policy)"
  evaluation: "rules engine looks up policy by Trade_Plans.risk_policy_version"
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `policy_id` | string | yes | Stable identifier across versions |
| `policy_version` | integer | yes | Monotonic version counter |
| `effective_from` | date | yes | First date this version applies |
| `effective_to` | date | no | Last date this version applies; null for currently active |
| `change_reason` | text | yes for v >= 2 | Why the policy was revised |
| `max_concurrent_positions` | numeric | yes | For this swing trading context, expected below 10 |
| `max_account_risk_per_trade_pct` | numeric | yes | Max initial risk per trade |
| `max_portfolio_heat_pct` | numeric | yes | Max total open risk as percentage of equity |
| `max_single_position_pct` | numeric | no | Max market value in one position |
| `max_sector_exposure_pct` | numeric | no | Max exposure to one sector/theme |
| `consecutive_losses_pause_threshold` | numeric | no | Loss streak pause threshold |
| `drawdown_pause_threshold_R` | numeric | no | Optional drawdown threshold (must be negative) |
| `drawdown_pause_action` | enum | no | `reduce_size`, `halt`, `review_required` |
| `scratch_epsilon` | numeric | yes | Default 0.10; defines scratch trades (see §6) |
| `review_lag_threshold_days` | numeric | yes | Default 7; drives `missing_review` and `review_completed_late` |

### 3.10 `Corporate_Actions`

Purpose: Adjust open positions, MFE/MAE, and avg_cost when corporate actions occur during a holding period.

```yaml
table: Corporate_Actions
grain: one_row_per_corporate_action
required_for:
  - avg_cost adjustment for splits
  - quantity_open adjustment for splits
  - MFE/MAE recomputation on adjusted price series
  - dividend booking via Cash_Flows
  - ticker continuity across renames
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `action_id` | string | yes | Unique identifier |
| `effective_date` | date | yes | Ex-date / effective date |
| `ticker_before` | string | yes | Ticker prior to action |
| `ticker_after` | string | yes | Ticker after action (equal to `ticker_before` for splits/dividends) |
| `action_type` | enum | yes | See §21 |
| `ratio_or_amount` | numeric | yes | Split ratio (e.g., 2.0 for 2-for-1), dividend per share, etc. |
| `cash_flow_id` | string | no | Set for cash dividends; links to `Cash_Flows` row with `external_to_trading=false` |
| `notes` | text | no | Source / broker reference |

**Adjustment rules (long-only):**

```yaml
adjustment_rules:
  forward_split:
    avg_cost_after: "avg_cost_before / ratio"
    quantity_after: "quantity_before * ratio"
    mfe_mae_recompute: "rebase historical price series by ratio before recomputing"
  reverse_split:
    avg_cost_after: "avg_cost_before * ratio"
    quantity_after: "quantity_before / ratio"
    mfe_mae_recompute: "rebase historical price series by ratio before recomputing"
  cash_dividend:
    avg_cost_after: "unchanged"
    quantity_after: "unchanged"
    cash_flow_treatment: "log Cash_Flows row with type=dividend, external_to_trading=false"
  stock_dividend:
    quantity_after: "quantity_before * (1 + ratio)"
    avg_cost_after: "avg_cost_before / (1 + ratio)"
  ticker_change:
    avg_cost_after: "unchanged"
    quantity_after: "unchanged"
    continuity: "Positions_Daily_Snapshots uses ticker_after going forward"
  spinoff_or_merger:
    treatment: "out of MVP scope; flag trade for manual reconciliation"
```

If the broker export is pre-adjusted, `Corporate_Actions` rows still need to be logged for audit and MFE/MAE consistency, but `avg_cost` and `quantity_open` may not require manual adjustment.

### 3.11 `Setup_Status_History`

Purpose: Audit trail for `Setup_Playbook.status` changes.

| Field | Type | Required | Description |
|---|---:|---:|---|
| `history_id` | string | yes | Unique identifier |
| `setup_id` | string | yes | Linked setup |
| `status` | enum | yes | See §21 |
| `effective_from` | datetime | yes | Timestamp of status change (UTC) |
| `effective_to` | datetime | no | Null for currently active status |
| `change_reason` | text | yes | Why the status changed |
| `triggering_recommendation_id` | string | no | Links to recommendation candidate that drove the change |

---

## 4. Derived Fact Tables

### 4.1 `Portfolio_Daily_Facts`

Purpose: Canonical daily portfolio metrics table.

```yaml
table: Portfolio_Daily_Facts
grain: one_row_per_trading_day
derived_from:
  - Account_Equity_Snapshots
  - Cash_Flows
  - Positions_Daily_Snapshots
  - Market_Context_Daily
```

| Field | Type | Description |
|---|---:|---|
| `date` | date | NYSE trading day |
| `start_equity` | numeric | Prior day ending equity plus today's external cash flows (start-of-day cash flow convention) |
| `end_equity` | numeric | End-of-day account equity |
| `external_cash_flow` | numeric | Sum of `Cash_Flows.amount` where `external_to_trading=true` for the day |
| `adjusted_daily_pnl` | numeric | `end_equity - start_equity` (start_equity already cash-flow-adjusted) |
| `daily_return_pct` | numeric | `adjusted_daily_pnl / start_equity`; 0 on the first trading day if no prior equity |
| `cumulative_return_pct` | numeric | `product(1 + daily_return_pct) - 1` over all trading days to date |
| `time_weighted_return_pct` | numeric | Equivalent to `cumulative_return_pct` for a given window; daily-linked |
| `cumulative_pnl_dollars` | numeric | Cumulative trading P&L excluding external cash flows |
| `cumulative_R` | numeric | Sum of closed realized R to date |
| `open_unrealized_R` | numeric | Sum of unrealized_R across open positions |
| `total_R_including_open` | numeric | `cumulative_R + open_unrealized_R` |
| `portfolio_heat_dollars` | numeric | Sum of `portfolio_heat_contribution_dollars` across open positions |
| `portfolio_heat_pct` | numeric | `portfolio_heat_dollars / account_equity` |
| `gross_exposure_pct` | numeric | `gross_exposure / account_equity` |
| `net_exposure_pct` | numeric | `net_exposure / account_equity` (= gross in long-only v1.1) |
| `cash_pct` | numeric | `cash_balance / account_equity` |
| `open_position_count` | numeric | Count of open trades |
| `largest_position_pct` | numeric | Largest position market value / account equity |
| `top_3_positions_pct` | numeric | Top 3 position market values / account equity |
| `largest_sector_exposure_pct` | numeric | Largest sector exposure / account equity |
| `drawdown_dollars` | numeric | `account_equity - equity_peak_to_date` (always <= 0) |
| `drawdown_pct` | numeric | `drawdown_dollars / equity_peak_to_date` (always <= 0) |
| `drawdown_R` | numeric | `cumulative_R - peak_cumulative_R` (always <= 0) |
| `benchmark_return_pct` | numeric | Benchmark return for matching period |
| `excess_return_pct` | numeric | Portfolio return minus benchmark return |
| `data_quality_score` | numeric | Portfolio data completeness and reconciliation quality |

### 4.2 `Trade_Performance_Facts`

Purpose: Canonical closed-trade analytics table.

```yaml
table: Trade_Performance_Facts
grain: one_row_per_closed_trade
derived_from:
  - Trade_Plans
  - Fills
  - Trade_Reviews
  - Positions_Daily_Snapshots
  - Corporate_Actions
```

| Field | Type | Description |
|---|---:|---|
| `trade_id` | string | Trade ID |
| `ticker_at_entry` | string | Symbol at first fill (may differ from final ticker after a ticker change) |
| `ticker_at_exit` | string | Symbol at final exit fill |
| `setup_id` | string | Setup ID |
| `setup_family` | enum | Setup family |
| `trade_origin` | enum | Origin of trade idea |
| `source_screen` | string | Source screen when applicable |
| `market_regime` | enum | Regime at entry (locked) |
| `entry_date` | date | First entry fill date |
| `exit_date` | date | Final exit fill date |
| `holding_period_days` | numeric | Calendar days from entry to exit |
| `vwap_entry_price` | numeric | Volume-weighted average of all entry/add fills |
| `vwap_exit_price` | numeric | Volume-weighted average of all exit/trim/stop fills |
| `initial_risk_dollars` | numeric | Immutable initial risk; equals `Trade_Plans.planned_risk_dollars` at first fill |
| `risk_added_after_initial_R` | numeric | Sum of risk added by unplanned scale-ins, expressed in initial-risk units |
| `gross_pnl_dollars` | numeric | Gross realized P&L (before fees) |
| `total_fees_dollars` | numeric | Sum of fees across all fills |
| `net_pnl_dollars` | numeric | `gross_pnl_dollars - total_fees_dollars` |
| `realized_R` | numeric | `net_pnl_dollars / initial_risk_dollars` |
| `gross_realized_R` | numeric | `gross_pnl_dollars / initial_risk_dollars` (cost-impact analysis) |
| `MFE_R` | numeric | Maximum favorable excursion in R, computed across full holding window on corporate-action-adjusted price series |
| `MAE_R` | numeric | Maximum adverse excursion in R, same basis |
| `mfe_mae_precision_level` | enum | See §21 |
| `outcome_class` | enum | `win`, `loss`, `scratch` per §6.0 |
| `capture_ratio` | numeric/null | `realized_R / MFE_R` when `outcome_class=win` AND `MFE_R > 0`; else null |
| `giveback_R_winner` | numeric/null | `MFE_R - realized_R` when `outcome_class=win` AND `MFE_R > 0`; else null |
| `giveback_R_winner_to_loser` | numeric/null | `MFE_R - realized_R` when `outcome_class=loss` AND `MFE_R > 0`; else null |
| `winner_to_loser_flag` | boolean | True when `outcome_class=loss` AND `MFE_R >= 1.0` |
| `entry_slippage_R` | numeric | `(planned_entry - vwap_entry_price) / risk_per_share`; negative = paid worse than planned |
| `process_grade` | enum | Overall process grade |
| `entry_grade` | enum | Entry grade |
| `management_grade` | enum | Management grade |
| `exit_grade` | enum | Exit grade |
| `mistake_tags` | list | Mistake tags |
| `mistake_cost_R` | numeric | Non-negative cost of mistakes |
| `mistake_cost_method` | enum | See §3.6 |
| `lucky_violation_R` | numeric | Non-negative benefit from rule violation |
| `pre_trade_quality_score` | numeric | Pre-trade score |
| `thesis_accuracy` | enum | Post-trade thesis outcome |
| `setup_validity_after_review` | enum | Post-trade setup validity |
| `reconciliation_status` | enum | Broker reconciliation status |
| `risk_policy_version` | integer | Policy version this trade was evaluated against |

### 4.3 `Setup_Performance_Summary`

Purpose: Aggregate trade facts by setup and period.

```yaml
table: Setup_Performance_Summary
grain: one_row_per_setup_per_period
periods:
  - all_time
  - year_to_date
  - quarter_to_date
  - month_to_date
  - rolling_90_days
  - rolling_20_closed_trades_for_setup
```

Fields should include sample size, net R, expectancy, win rate, scratch rate, average win/loss, profit factor, payoff ratio, max drawdown R, MFE/MAE, capture ratio (winners only), giveback variants, mistake rate, process adherence, reliability label, and recommended setup status candidate.

### 4.4 `Process_Performance_Summary`

Purpose: Aggregate process and behavior quality.

```yaml
process_performance_summary_fields:
  - period
  - reviewed_trade_count
  - percent_A_grade
  - percent_rule_followed
  - A_grade_expectancy_R
  - B_or_worse_expectancy_R
  - rule_followed_expectancy_R
  - rule_violated_expectancy_R
  - total_mistake_cost_R
  - total_lucky_violation_R
  - top_mistake_tag_by_cost
  - repeated_mistake_tags
  - review_compliance_rate
  - review_completed_late_count
```

### 4.5 `Performance_Alerts`

Purpose: Store deterministic rules engine outputs.

| Field | Type | Description |
|---|---:|---|
| `alert_id` | string | Unique ID |
| `generated_at` | datetime | Timestamp (UTC) |
| `rule_id` | string | Rule that triggered |
| `severity` | enum | See §21 |
| `scope` | enum | See §21 |
| `subject_id` | string | Setup ID, trade ID, or portfolio |
| `message` | text | Human-readable alert |
| `evidence_json` | json | Metric values and thresholds |
| `linked_trade_ids` | list | Supporting trades |
| `status` | enum | See §21 |

---

## 5. Portfolio Performance Metrics

Portfolio performance should be evaluated before setup and trade performance because it answers whether the account is actually improving after open risk, drawdown, exposure, and cash flows are considered.

**Sign convention:** drawdown values are always less than or equal to zero. Risk-policy thresholds for drawdown must be expressed as negative numbers.

**Cash-flow timing convention:** external cash flows are treated as posting at the start of day. `start_equity` for day D = prior-day `end_equity` + day-D `external_cash_flow`. This makes the daily P&L expression below correct without subtracting cash flows again.

### 5.1 Net Liquidation Value

```text
net_liquidation_value = cash_balance + market_value_of_open_positions
```

### 5.2 Adjusted Daily P&L

```text
external_cash_flow = sum(Cash_Flows.amount where external_to_trading = true and date = D)
start_equity_D = end_equity_{D-1} + external_cash_flow_D
adjusted_daily_pnl_D = end_equity_D - start_equity_D
```

Dividends and interest are recorded in `Cash_Flows` with `external_to_trading=false` and are therefore part of `adjusted_daily_pnl` rather than being subtracted out.

### 5.3 Daily Return

```text
daily_return_pct_D = adjusted_daily_pnl_D / start_equity_D
```

**First-day rule:** if D is the first trading day in the account history and `end_equity_{D-1}` does not exist, set `daily_return_pct_D = 0` and `start_equity_D` equal to the opening deposit. Trading begins to compound from day 2.

### 5.4 Time-Weighted Return

```text
time_weighted_return_window = product(1 + daily_return_pct) over window - 1
```

Use TWR as the main portfolio return metric when external deposits or withdrawals occur.

### 5.5 Cumulative Return

```text
cumulative_return_pct = product(1 + daily_return_pct) - 1   over all trading days to date
```

This is the same construction as TWR over the full history. The v1.0 formula referencing `current_adjusted_equity / starting_adjusted_equity` is removed because it is incorrect when multiple cash flows occur at different equity levels.

### 5.6 Portfolio Drawdown

```text
equity_peak_to_date = max(account_equity from start through current_date)
drawdown_dollars = account_equity - equity_peak_to_date         # always <= 0
drawdown_pct    = drawdown_dollars / equity_peak_to_date         # always <= 0
```

### 5.7 Portfolio Heat

Portfolio heat measures open risk to stops, **not** market value exposure. Heat is computed from entry-anchored at-risk dollars (see §3.3), which can be negative when a stop has been moved above entry. Locked-in profit must not offset risk in other positions, hence the floor:

```text
portfolio_heat_dollars = sum(max(0, raw_current_at_risk_dollars))   over open positions
portfolio_heat_pct     = portfolio_heat_dollars / account_equity
```

### 5.8 Exposure

```text
gross_exposure     = sum(abs(position_market_value))
gross_exposure_pct = gross_exposure / account_equity
net_exposure       = long_market_value - short_market_value     # = long_market_value in v1.1
net_exposure_pct   = net_exposure / account_equity
```

### 5.9 Cash Allocation

```text
cash_pct = cash_balance / account_equity
```

High cash is not automatically bad. It should be interpreted relative to market regime, setup availability, and recent performance.

### 5.10 Concentration

```text
position_weight       = position_market_value / account_equity
largest_position_pct  = max(position_weight)
top_3_positions_pct   = sum(top_3_position_weights)
```

Optional:

```text
effective_number_of_positions = 1 / sum(position_weight^2)
```

### 5.11 Benchmark-Relative Return

```text
excess_return_pct = portfolio_return_pct - benchmark_return_pct
```

Use configurable benchmarks such as SPY, QQQ, or IWM. For a stock swing trading system, QQQ may be more relevant for growth/momentum trades, while SPY may be better for broad comparison.

```yaml
benchmark_interpretation:
  portfolio_positive_benchmark_negative:
    meaning: "positive absolute and relative performance"
  portfolio_negative_benchmark_more_negative:
    meaning: "absolute loss but relative outperformance"
  portfolio_positive_benchmark_more_positive:
    meaning: "absolute gain but underperformance versus passive benchmark"
  portfolio_negative_benchmark_positive:
    meaning: "poor absolute and relative performance"
```

### 5.12 Optional Risk-Adjusted Return Ratios

For low-frequency swing trading, traditional Sharpe and Sortino ratios are noisy at small sample sizes. They are available as **optional** metrics with reliability labels and are not on default dashboards.

```yaml
optional_risk_adjusted_returns:
  monthly_sharpe:
    formula: "(mean(monthly_return) - monthly_risk_free) / stdev(monthly_return)"
    reliability:
      provisional: "12 to 23 monthly returns"
      actionable: "24+ monthly returns"
  monthly_sortino:
    formula: "(mean(monthly_return) - monthly_risk_free) / downside_deviation(monthly_return)"
    reliability:
      provisional: "12 to 23 monthly returns"
      actionable: "24+ monthly returns"
```

---

## 6. Trade Performance Metrics

All trade-level metrics should be normalized in R where possible.

```text
1R = initial_risk_dollars (immutable, locked at first fill)
```

### 6.0 Outcome Classification (Scratch Trades)

```yaml
outcome_classification:
  scratch_epsilon: "Risk_Policy.scratch_epsilon (default 0.10)"
  rule:
    - "win:     realized_R >=  scratch_epsilon"
    - "loss:    realized_R <= -scratch_epsilon"
    - "scratch: abs(realized_R) < scratch_epsilon"
  invariant: "win_rate + loss_rate + scratch_rate == 1"
```

### 6.1 Realized R

```text
realized_R = net_pnl_dollars / initial_risk_dollars
```

`net_pnl_dollars` is net of all fees and commissions. For multi-leg trades, `net_pnl_dollars = sum(per-leg P&L) - sum(fees)` with FIFO matching of exit fills against entry fills.

### 6.2 Net R

```text
net_R = sum(realized_R) over closed trades in window
```

### 6.3 Expectancy

```text
expectancy_R = average(realized_R) over closed trades in window
```

### 6.4 Decomposed Expectancy

```text
expectancy_R = win_rate * avg_win_R
             + loss_rate * avg_loss_R
             + scratch_rate * avg_scratch_R
```

Where `avg_loss_R` is stored as a negative number and `avg_scratch_R` is near zero by definition.

### 6.5 Profit Factor

```text
profit_factor = sum(realized_R where realized_R > 0)
              / abs(sum(realized_R where realized_R < 0))
```

**Edge case:** if the denominator is zero (no losing trades in window), return null with reliability flag `no_losing_trades_in_window` and display as "—". Never return positive infinity.

### 6.6 Payoff Ratio

```text
payoff_ratio = avg_win_R / abs(avg_loss_R)
```

Edge case: if there are no winners, no losers, or both, return null with appropriate reliability flag.

### 6.7 Breakeven Win Rate

```text
breakeven_win_rate = abs(avg_loss_R) / (avg_win_R + abs(avg_loss_R))
```

Requires sample to contain at least one winner and at least one loser. Otherwise return null with reliability flag `insufficient_outcome_diversity`.

### 6.8 Holding Period

```text
holding_period_days = exit_date - entry_date     # calendar days
```

```yaml
holding_period_buckets:
  very_short:        "0-2 days"
  normal_short_swing: "3-7 days"
  normal_swing:      "8-21 days"
  extended_swing:    "22+ days"
```

### 6.9 Multi-Leg Trade Math

```yaml
multi_leg_trade_rules:
  vwap_entry_price:
    formula: "sum(price * quantity) over [entry, add] fills / sum(quantity) over [entry, add] fills"
  vwap_exit_price:
    formula: "sum(price * quantity) over [trim, exit, stop] fills / sum(quantity) over [trim, exit, stop] fills"
  net_pnl_dollars:
    formula: "FIFO-matched leg P&L summed across all matched lots, minus sum(fees)"
  realized_R:
    formula: "net_pnl_dollars / initial_risk_dollars  (initial_risk immutable)"
  partial_exits_in_progress:
    closed_portion: "P&L realized; included in cumulative_R once Trade_Performance_Facts row exists"
    remaining_portion: "tracked as open position; unrealized_R reported on Positions_Daily_Snapshots"
  unplanned_scale_in:
    detection: "fill with action='add' that is not part of Trade_Plans.planned_position_size"
    treatment:
      - "increment risk_added_after_initial_R = (price - current_stop) * added_quantity / initial_risk_dollars"
      - "tag mistake: UNPLANNED_ADD or UNPLANNED_SCALE_IN"
      - "do not change initial_risk_dollars"
```

---

## 7. Open Position Performance Metrics

Because swing trades remain open for days or weeks, open-position metrics must be visible before trade closure.

```yaml
open_position_metrics:
  - open_unrealized_pnl_dollars
  - open_unrealized_R
  - open_MFE_to_date_R
  - open_MAE_to_date_R
  - current_at_risk_R
  - portfolio_heat_contribution_dollars
  - locked_in_profit_at_stop_dollars
  - thesis_status
  - days_held
  - distance_to_stop_pct
  - distance_to_target_pct
  - mfe_mae_precision_level
```

Useful formulas (long-only):

```text
open_unrealized_R    = unrealized_pnl_dollars / initial_risk_dollars
distance_to_stop_pct = (current_price - current_stop) / current_price
open_MFE_to_date_R   = max over snapshots since first fill of unrealized_R
open_MAE_to_date_R   = min over snapshots since first fill of unrealized_R
```

`open_MFE_to_date_R` and `open_MAE_to_date_R` are computed using the same precision rules as closed-trade MFE/MAE (§8.2) and updated at each daily snapshot. When the trade closes, the final values become the trade's `MFE_R` / `MAE_R` on `Trade_Performance_Facts`.

If `distance_to_stop_pct` is small and `thesis_status` is `weakening`, the system should flag the position for review.

---

## 8. Trade Management and Exit Efficiency Metrics

### 8.1 MFE and MAE

```yaml
MFE_R:
  meaning: "Maximum favorable excursion in R."
  question: "How much profit did the trade offer at its best?"
MAE_R:
  meaning: "Maximum adverse excursion in R."
  question: "How much pain did the trade require?"
basis: "Computed across the full holding window from first entry to final exit, on price series adjusted for any corporate actions during the holding period."
```

### 8.2 MFE/MAE Precision Level

```yaml
mfe_mae_precision_level:
  intraday_exact:
    meaning: "Computed using intraday data after entry and before exit."
  intraday_estimated:
    meaning: "Computed using partial intraday data or approximate fill-time windows."
  daily_approximate:
    meaning: "Computed from daily high/low bars; acceptable for swing trading MVP but less precise."
```

### 8.3 Capture Ratio (Winners Only)

```text
capture_ratio = realized_R / MFE_R
```

```yaml
capture_ratio_valid_when:
  - outcome_class == win
  - MFE_R > 0
otherwise: null
```

### 8.4 Giveback (Two Variants)

```yaml
giveback_R_winner:
  formula: "MFE_R - realized_R"
  computed_when:
    - outcome_class == win
    - MFE_R > 0
  meaning: "Profit available at MFE that was surrendered before exit (winners only)."

giveback_R_winner_to_loser:
  formula: "MFE_R - realized_R"
  computed_when:
    - outcome_class == loss
    - MFE_R > 0
  meaning: "Profit that was available at MFE and converted into a loss."

winner_to_loser_flag:
  formula: "outcome_class == loss AND MFE_R >= 1.0"
  meaning: "Trade reached >=1R favorable excursion before turning into a loss."
```

Aggregate `average_giveback_R` over winners only by default. Expose `average_giveback_R_winner_to_loser` separately for diagnostic dashboards.

### 8.5 Exit Efficiency Diagnostics

```yaml
exit_efficiency_metrics:
  average_capture_ratio: "winners only"
  median_capture_ratio: "winners only"
  average_giveback_R_winner: number
  average_giveback_R_winner_to_loser: number
  winners_to_losers_count: number
  trades_hit_1R_MFE_but_closed_negative_count: number
  trades_hit_2R_MFE_but_closed_under_1R_count: number
```

```yaml
exit_diagnostics:
  high_MFE_low_realized_R:
    likely_signal: "exit management or profit protection needs review"
  low_MFE_high_MAE:
    likely_signal: "entry quality or setup selection needs review"
  frequent_winners_to_losers:
    likely_signal: "profit protection rule may be missing or not followed"
```

---

## 9. Setup Performance Metrics

For each setup, compute:

```yaml
setup_metrics:
  - sample_size
  - net_R
  - expectancy_R
  - win_rate
  - loss_rate
  - scratch_rate
  - avg_win_R
  - avg_loss_R
  - avg_scratch_R
  - profit_factor
  - payoff_ratio
  - max_drawdown_R
  - average_MFE_R
  - average_MAE_R
  - average_capture_ratio
  - average_holding_period_days
  - mistake_rate
  - process_adherence_rate
  - A_grade_expectancy_R
  - reliability_label
```

### 9.1 Setup Classification Rules

```yaml
setup_classification_rules:
  insufficient_data:
    condition: "sample_size < 10"
    output: "display metrics only; no setup conclusion"
  early_positive_signal:
    condition: "sample_size >= 10 and expectancy_R > 0"
    output: "monitor; do not increase size based on this alone"
  early_negative_signal:
    condition: "sample_size >= 10 and expectancy_R < 0"
    output: "create informational review task; do not pause or retire"
  review_candidate:
    condition: "sample_size >= 20 and expectancy_R < 0"
    output: "create setup review task"
  pause_candidate:
    condition: "sample_size >= 20 and expectancy_R < 0 and recent_expectancy_R < 0"
    output: "pause candidate, subject to human review"
  retire_candidate:
    condition: "sample_size >= 30 and expectancy_R < 0 and process_adherence_rate >= 0.80"
    output: "retire candidate, subject to review"
  emphasize_candidate:
    condition: "sample_size >= 30 and expectancy_R > portfolio_expectancy_R and profit_factor >= 1.50 and process_adherence_rate >= 0.80"
    output: "emphasize candidate, not automatic size increase"
```

### 9.2 Setup Diagnosis Matrix

```yaml
setup_diagnosis_matrix:
  positive_expectancy_high_process_quality:
    diagnosis: "setup likely has edge"
    action: "continue; consider review for increased focus only after sufficient sample"
  positive_expectancy_low_process_quality:
    diagnosis: "profits may be fragile or luck-reinforced"
    action: "do not increase size; repair process first"
  negative_expectancy_high_process_quality:
    diagnosis: "setup or regime may lack edge"
    action: "pause, refine, or retire candidate depending on sample size"
  negative_expectancy_low_process_quality:
    diagnosis: "strategy performance contaminated by execution errors"
    action: "do not retire setup yet; reduce size or focus on process adherence"
```

---

## 10. Process and Behavioral Performance Metrics

Process metrics determine whether results came from disciplined execution or contaminated behavior.

### 10.1 Plan Adherence

```text
plan_adherence_rate = trades_followed_plan / reviewed_trades
```

```yaml
plan_adherence_breakdown:
  - entry_adherence_rate
  - sizing_adherence_rate
  - stop_adherence_rate
  - management_adherence_rate
  - exit_adherence_rate
```

### 10.2 Mistake Cost (Methodology)

```text
mistake_cost_R = max(0, abs(realized_R) - abs(hypothetical_R_if_plan_followed))
                 when realized_R is worse than the plan would have produced
               = 0
                 otherwise
```

```yaml
mistake_cost_method:
  direct_measurement:
    use_when: "the plan exit was a defined price (target or stop) and the violation produced a measurable difference"
    confidence: "high"
  counterfactual_estimate:
    use_when: "the plan was rule-based but exit price under the rule must be inferred from the post-trade chart"
    confidence: "medium"
  bracketed_range:
    use_when: "outcome under the plan is uncertain; record midpoint and store min/max as a range"
    confidence: "low"
```

```text
total_mistake_cost_R = sum(mistake_cost_R) over reviewed trades
```

Break down by mistake tag:

```yaml
mistake_cost_by_tag:
  CHASED: number
  SOLD_TOO_EARLY: number
  MOVED_STOP_AWAY: number
  HELD_AFTER_INVALIDATION: number
  UNPLANNED_ADD: number
  UNPLANNED_SCALE_IN: number
```

### 10.3 Lucky Violation

```text
total_lucky_violation_R = sum(lucky_violation_R)
```

Lucky violation R must never be netted against mistake cost. It is a warning that bad process produced a favorable outcome.

### 10.4 Process-Adjusted Performance

```yaml
process_adjusted_metrics:
  all_trades_expectancy_R: number
  A_grade_expectancy_R: number
  B_or_worse_expectancy_R: number
  rule_followed_expectancy_R: number
  rule_violated_expectancy_R: number
  C_or_worse_trade_pct: number
```

```yaml
process_interpretation:
  A_grade_positive_C_grade_negative:
    meaning: "edge exists when process is followed"
  all_grades_negative:
    meaning: "strategy or regime may lack edge"
  C_grade_positive_due_to_lucky_violations:
    meaning: "bad process is being rewarded; do not increase size"
```

---

## 11. Risk Performance Metrics

Risk metrics answer whether the account is taking appropriate risk relative to return and drawdown.

```yaml
risk_metrics:
  portfolio_heat_pct: number
  max_portfolio_heat_pct: number
  current_drawdown_pct: number      # always <= 0
  max_drawdown_pct: number          # always <= 0
  current_drawdown_R: number        # always <= 0
  max_drawdown_R: number            # always <= 0
  max_consecutive_losses: number
  current_consecutive_losses: number
  largest_position_pct: number
  largest_sector_exposure_pct: number
  recovery_factor: number
  return_over_max_drawdown: number
  monthly_sharpe: number   # optional, reliability-labeled
  monthly_sortino: number  # optional, reliability-labeled
```

### 11.1 Recovery Factor

```text
recovery_factor   = net_profit / abs(max_drawdown_dollars)
R_recovery_factor = net_R     / abs(max_drawdown_R)
```

**Edge case:** if `max_drawdown_dollars` (or `max_drawdown_R`) is zero, return null and display as "—" with note "no drawdown recorded yet."

### 11.2 Return Over Max Drawdown

```text
return_over_max_drawdown = cumulative_return_pct / abs(max_drawdown_pct)
```

Edge case: same null treatment as recovery factor when `max_drawdown_pct` is zero.

### 11.3 Loss Streak Metrics

```yaml
loss_streak_metrics:
  current_consecutive_losses: number
  max_consecutive_losses: number
  R_lost_during_worst_streak: number
  review_completed_after_streak: boolean
notes:
  - "Scratch trades neither extend nor break a loss streak."
```

Loss streaks should trigger review tasks or hard blocks only if the active risk policy defines such behavior.

---

## 12. Data Quality and Metric Validity

Performance metrics should be labeled by data quality.

```yaml
data_quality_metrics:
  trade_completeness_score: number
  portfolio_snapshot_completeness_score: number
  percent_trades_reconciled: number
  percent_account_snapshots_reconciled: number
  unresolved_discrepancy_count: number
  missing_fill_count: number
  missing_review_count: number
  stale_open_trade_count: number
  missing_cash_flow_count: number
  corporate_action_unadjusted_count: number
  mfe_mae_precision_distribution:
    - intraday_exact
    - intraday_estimated
    - daily_approximate
```

### 12.1 Missing Review Definition

```yaml
missing_review:
  definition: "A closed trade has missing_review = true when no Trade_Reviews row exists with reviewed_at within Risk_Policy.review_lag_threshold_days (default 7) of the trade's exit_date."
```

### 12.2 Metric Validity Rules

```yaml
metric_validity_rules:
  final_portfolio_return_metrics:
    require:
      - account_equity_snapshots_complete
      - cash_flows_recorded
      - account_reconciliation_status acceptable
  provisional_portfolio_return_metrics:
    allowed_when: "some snapshots are unreconciled"
    display_label: "provisional"
  final_trade_pnl_metrics:
    require: "trade reconciliation_status in [reconciled_match, reconciled_discrepancy_resolved, manual_override]"
  process_metrics:
    allowed_before_reconciliation: true
    reason: "process review is memory-sensitive"
  MFE_MAE_metrics:
    require: "mfe_mae_precision_level present"
  setup_conclusions:
    require:
      - minimum_sample_size_met
      - data_quality_score >= threshold
  risk_adjusted_returns:
    require:
      - "monthly returns sample meets reliability threshold"
```

---

## 13. Deterministic Rules Engine

The rules engine converts metrics into blocks, warnings, review tasks, and recommendation candidates.

### 13.1 Rule Schema

```yaml
rule_schema:
  rule_id: string
  enabled: boolean
  scope:
    enum:
      - portfolio
      - trade
      - setup
      - process
      - risk
      - data_quality
      - reconciliation
  lookback:
    type:
      enum:
        - last_n_trades
        - last_n_days
        - month_to_date
        - quarter_to_date
        - year_to_date
        - all_time
    value: number
  minimum_sample_size: number
  data_quality_minimum: number
  condition_expression: string
  severity:
    enum:
      - info
      - warning
      - critical
      - blocking
  action:
    enum:
      - notify
      - create_review_task
      - create_rule_change_candidate
      - block_trade
      - reduce_size_candidate
      - pause_setup_candidate
      - retire_setup_candidate
  evidence_fields:
    - metric_name
    - metric_value
    - threshold
    - linked_trade_ids
  cooldown_period_days: number
```

### 13.2 Recommendation Output Schema

```yaml
recommendation_output:
  recommendation_id: string
  generated_at: datetime
  rule_id: string
  severity: enum
  scope: enum
  subject_id: string
  recommendation: string
  reason: string
  evidence:
    metric_values: object
    thresholds: object
    sample_size: number
    lookback_window: string
    linked_trade_ids: list
  status:
    enum:
      - open
      - acknowledged
      - dismissed
      - converted_to_rule_change
      - resolved
```

### 13.3 Hard Blocks

Hard blocks enforce account risk policy.

```yaml
hard_block_rules:
  max_positions:
    condition: "current_open_positions >= policy.max_concurrent_positions"
    action: block_new_trade
  portfolio_heat:
    condition: "portfolio_heat_after_trade_pct > policy.max_portfolio_heat_pct"
    action: block_new_trade
  missing_risk:
    condition: "planned_entry is null or initial_stop is null or planned_risk_dollars is null"
    action: block_new_trade
  loss_streak_pause:
    condition: "current_consecutive_losses >= policy.consecutive_losses_pause_threshold and review_completed_since_last_loss == false"
    action: block_new_trade
```

### 13.4 Portfolio Rules

```yaml
portfolio_rules:
  excessive_drawdown:
    condition: "current_drawdown_R <= policy.drawdown_pause_threshold_R and policy.drawdown_pause_threshold_R is not null"
    note: "both sides negative; threshold must be expressed as a negative number"
    action: reduce_size_or_halt_per_policy
  portfolio_heat_exceeded:
    condition: "portfolio_heat_pct > policy.max_portfolio_heat_pct"
    action: block_new_trades_and_review_open_risk
  concentration_too_high:
    condition: "largest_position_pct > policy.max_single_position_pct"
    action: create_concentration_review_task
  sector_concentration_too_high:
    condition: "largest_sector_exposure_pct > policy.max_sector_exposure_pct"
    action: create_sector_concentration_review_task
  benchmark_underperformance:
    condition: "portfolio_return_pct < benchmark_return_pct and sample_days >= 60"
    action: create_benchmark_underperformance_review_task
  overexposed_in_bad_regime:
    condition: "gross_exposure_pct > 0.70 and market_regime in [distribution_top, bear_trending, range_choppy]"
    action: create_exposure_reduction_review_task
```

### 13.5 Setup Rules

```yaml
setup_rules:
  insufficient_sample:
    condition: "setup_sample_size < 10"
    action: display_only_no_conclusion
  early_negative_signal:
    condition: "setup_sample_size >= 10 and setup_expectancy_R < 0 and setup_sample_size < 20"
    action: create_informational_review_task
  setup_review_candidate:
    condition: "setup_sample_size >= 20 and setup_expectancy_R < 0"
    action: create_setup_review_task
  setup_pause_candidate:
    condition: "setup_sample_size >= 20 and setup_expectancy_R < 0 and recent_expectancy_R < 0"
    action: pause_setup_candidate
  setup_retire_candidate:
    condition: "setup_sample_size >= 30 and setup_expectancy_R < 0 and process_adherence_rate >= 0.80"
    action: retire_setup_candidate
  setup_emphasize_candidate:
    condition: "setup_sample_size >= 30 and setup_expectancy_R > portfolio_expectancy_R and profit_factor >= 1.50"
    action: emphasize_setup_candidate
```

### 13.6 Process Rules

```yaml
process_rules:
  high_mistake_cost:
    condition: "mistake_cost_R_last_20_trades >= 3.0"
    action: create_behavioral_review_task
  lucky_violation_cluster:
    condition: "lucky_violation_count_last_10_trades >= 2"
    action: warn_bad_process_reinforced
  repeated_same_error:
    condition: "any_mistake_tag_count >= 3 over last_20_trades"
    action: set_next_review_focus_to_that_tag
  strategy_contaminated_by_process:
    condition: "setup_expectancy_R < 0 and process_adherence_rate < 0.70"
    action: do_not_retire_setup_yet_focus_on_process
  unplanned_scale_in_pattern:
    condition: "UNPLANNED_ADD or UNPLANNED_SCALE_IN tag count >= 2 over last_20_trades"
    action: create_sizing_discipline_review_task
```

### 13.7 Exit Efficiency Rules

```yaml
exit_efficiency_rules:
  poor_capture:
    condition: "winning_trade_sample_size >= 10 and average_MFE_R >= 1.5 and average_capture_ratio < 0.40"
    action: create_exit_management_review_task
  excessive_giveback:
    condition: "winning_trade_sample_size >= 10 and average_giveback_R_winner > 1.0"
    action: create_profit_protection_review_task
  winners_to_losers:
    condition: "trades_hit_1R_MFE_but_closed_negative_count >= 2 over last_20_trades"
    action: create_exit_rule_review_task
```

### 13.8 Data Quality Rules

```yaml
data_quality_rules:
  unresolved_discrepancies:
    condition: "unresolved_discrepancy_count > 0"
    action: repair_data_quality_before_final_metrics
  stale_open_trade:
    condition: "open_trade_without_snapshot_days >= 2"
    action: create_open_trade_update_task
  unreconciled_account_snapshots:
    condition: "account_snapshots_unreconciled_days > 5"
    action: create_account_reconciliation_task
  missing_cash_flows:
    condition: "cash_flow_detected_in_broker_but_not_logged == true"
    action: create_cash_flow_reconciliation_task
  unadjusted_corporate_action:
    condition: "open_position has corporate_action effective during hold and avg_cost not adjusted"
    action: create_corporate_action_reconciliation_task
```

### 13.9 Review Lifecycle Rules

```yaml
review_lifecycle_rules:
  review_overdue:
    condition: "closed_trade has no Trade_Reviews row and (today - exit_date) > policy.review_lag_threshold_days"
    severity: warning
    action: create_review_task
  review_completed_late:
    condition: "Trade_Reviews.reviewed_at - exit_date > policy.review_lag_threshold_days"
    severity: info
    action: notify_and_flag_review_reliability
```

### 13.10 Hindsight-Risk Rules

```yaml
hindsight_risk_rules:
  regime_classified_post_close:
    condition: "Market_Context_Daily.regime_classified_post_close == true for any day in lookback window"
    severity: info
    action: flag_regime_segmented_metrics_with_hindsight_risk
```

---

## 14. What Requires Inference vs. What Does Not

### 14.1 Does Not Require Inference

The following can be generated algorithmically:

```yaml
algorithmic_outputs:
  - portfolio returns
  - drawdown
  - exposure
  - concentration
  - portfolio heat
  - realized_R
  - expectancy_R
  - profit factor
  - win rate / loss rate / scratch rate
  - average win / loss / scratch
  - MFE_R
  - MAE_R
  - capture ratio (winners only)
  - giveback (both variants)
  - setup performance summaries
  - process grade distributions
  - mistake cost by tag
  - lucky violation counts
  - review tasks
  - hard blocks
  - warnings
  - setup pause candidates
  - setup retire candidates
  - corporate-action adjustments per defined rules
```

### 14.2 Requires Human Judgment or Optional AI Assistance

```yaml
inference_or_judgment_required:
  - visual chart pattern validation
  - determining whether a base was constructive from an image
  - identifying exact psychological cause from free-text notes
  - creating a brand-new trading rule
  - deciding whether a setup should actually be retired
  - approving a size increase
  - determining causal explanation from small samples
  - mistake_cost counterfactual estimation when method is bracketed_range
```

Safe production stance:

```yaml
safe_output_pattern:
  signal: "Low capture ratio detected."
  evidence: "average_MFE_R=2.1, average_capture_ratio=0.32, sample_size=12"
  action: "Create exit management review task."
  avoid: "You are afraid to hold winners."
```

---

## 15. Dashboard Requirements

### 15.1 Portfolio Dashboard

```yaml
portfolio_dashboard:
  headline:
    - account_equity
    - cumulative_return_pct
    - time_weighted_return_pct
    - cumulative_pnl_dollars
    - cumulative_R           # see interpretive note below
    - total_R_including_open
    - benchmark_return_pct
    - excess_return_pct
  risk:
    - current_drawdown_pct
    - max_drawdown_pct
    - current_drawdown_R
    - max_drawdown_R
    - recovery_factor
    - portfolio_heat_pct
  exposure:
    - cash_pct
    - gross_exposure_pct
    - net_exposure_pct
    - open_position_count
    - largest_position_pct
    - top_3_positions_pct
    - largest_sector_exposure_pct
  open_positions:
    - unrealized_pnl_dollars
    - open_unrealized_R
    - open_risk_dollars
    - positions_with_weakening_thesis
    - stale_open_trade_count
  returns:
    - daily_return_pct
    - weekly_return_pct
    - monthly_return_pct
    - quarter_to_date_return_pct
    - year_to_date_return_pct
  data_quality:
    - equity_snapshot_reconciled_through
    - unresolved_account_discrepancies
    - cash_flow_adjustment_status
    - corporate_action_unadjusted_count
interpretive_notes:
  cumulative_R:
    note: "cumulative_R measures strategy edge in normalized risk units. It is not interchangeable with cumulative_pnl_dollars. Always pair them on this dashboard to avoid misreading edge as growth."
```

### 15.2 Trade Dashboard

```yaml
trade_dashboard:
  - total_closed_trades
  - net_R
  - expectancy_R
  - win_rate
  - loss_rate
  - scratch_rate
  - avg_win_R
  - avg_loss_R
  - profit_factor
  - payoff_ratio
  - breakeven_win_rate
  - average_holding_period_days
  - average_MFE_R
  - average_MAE_R
  - average_capture_ratio
  - average_giveback_R_winner
  - average_giveback_R_winner_to_loser
```

### 15.3 Setup Dashboard

```yaml
setup_dashboard:
  by_setup_id:
    - sample_size
    - reliability_label
    - expectancy_R
    - profit_factor
    - win_rate
    - scratch_rate
    - avg_win_R
    - avg_loss_R
    - average_MFE_R
    - average_capture_ratio
    - mistake_rate
    - process_adherence_rate
    - setup_status_candidate
```

### 15.4 Process Dashboard

```yaml
process_dashboard:
  - percent_A_grade
  - plan_adherence_rate
  - A_grade_expectancy_R
  - B_or_worse_expectancy_R
  - rule_followed_expectancy_R
  - rule_violated_expectancy_R
  - total_mistake_cost_R
  - total_lucky_violation_R
  - top_mistake_tag_by_cost
  - repeated_mistake_tag_alerts
  - review_completed_late_count
```

---

## 16. Weekly Performance Report

Weekly reports are tactical. For swing trading, weekly reports may include few or no closed trades, so they must include open-position and portfolio state.

```yaml
weekly_performance_report:
  period:
    start_date:
    end_date:
  portfolio_summary:
    account_equity:
    weekly_return_pct:
    time_weighted_return_pct:
    cumulative_return_pct:
    benchmark_return_pct:
    excess_return_pct:
    current_drawdown_pct:
    portfolio_heat_pct:
    gross_exposure_pct:
    cash_pct:
  open_position_summary:
    open_position_count:
    open_unrealized_R:
    total_R_including_open:
    positions_with_weakening_thesis:
    largest_position_pct:
    largest_sector_exposure_pct:
  closed_trade_summary:
    closed_trades:
    net_R:
    expectancy_R:
    win_rate:
    scratch_rate:
    profit_factor:
  trade_management:
    average_MFE_R:
    average_capture_ratio:
    winners_to_losers_count:
    stale_open_trade_count:
  process_summary:
    A_grade_trade_pct:
    total_mistake_cost_R:
    total_lucky_violation_R:
    top_mistake_tag:
  data_quality:
    reconciliation_status:
    unresolved_discrepancies:
    missing_reviews:
    data_quality_score:
  rule_triggered_outputs:
    hard_blocks_active:
    warnings:
    review_tasks_created:
    recommendation_candidates:
```

---

## 17. Monthly Performance Report

Monthly reports are strategic, but swing trading sample sizes may still be small. The report must label reliability.

```yaml
monthly_performance_report:
  primary_questions:
    - "Did portfolio equity improve after cash-flow adjustment?"
    - "Was drawdown acceptable relative to return?"
    - "Was exposure appropriate for the market regime?"
    - "Which setups show early or actionable edge?"
    - "Which mistakes cost the most R?"
    - "Are exit rules capturing enough favorable excursion?"
    - "Is data quality sufficient for conclusions?"
  required_sections:
    - portfolio_return_and_drawdown
    - benchmark_relative_performance
    - exposure_and_concentration
    - open_position_carryover
    - closed_trade_R_summary
    - setup_expectancy_table_with_reliability_labels
    - regime_performance_table
    - mistake_cost_table
    - process_grade_distribution
    - MFE_MAE_exit_efficiency
    - deterministic_rule_triggers
    - corporate_action_summary
    - next_month_review_tasks
  optional_sections:
    - risk_adjusted_returns_with_reliability_label
```

---

## 18. Implementation Priority

```yaml
implementation_priority:
  stage_1_fundamental_data:
    - Account_Equity_Snapshots
    - Cash_Flows
    - Positions_Daily_Snapshots
    - Trade_Plans
    - Fills
    - Trade_Reviews
    - Setup_Playbook
    - Setup_Status_History
    - Risk_Policy (versioned)
    - Corporate_Actions
  stage_2_portfolio_metrics:
    - adjusted_daily_pnl
    - daily_return_pct
    - time_weighted_return_pct
    - cumulative_return_pct
    - drawdown_pct
    - portfolio_heat_pct
    - gross_exposure_pct
    - cash_pct
    - concentration metrics
  stage_3_trade_metrics:
    - outcome_class (win/loss/scratch)
    - realized_R
    - MFE_R / MAE_R
    - capture_ratio (winners only)
    - giveback variants
    - holding_period_days
    - entry_slippage_R
  stage_4_aggregate_metrics:
    - setup summaries
    - process summaries
    - risk summaries
    - benchmark comparison
  stage_5_deterministic_rules_engine:
    - hard blocks
    - warnings
    - review tasks
    - recommendation candidates
    - review lifecycle rules
  stage_6_reporting:
    - portfolio dashboard
    - trade dashboard
    - setup dashboard
    - process dashboard
    - weekly report
    - monthly report
  stage_7_optional_enhancements:
    - monthly Sharpe / Sortino with reliability labels
    - multi-currency FX handling
```

---

## 19. Acceptance Criteria

A production implementation satisfies this specification when:

```yaml
acceptance_criteria:
  data_foundation:
    - daily account equity snapshots can be stored and reconciled
    - external cash flows are captured separately from trading P&L (dividends/interest excluded)
    - open positions are snapshotted at least daily, including open MFE/MAE to date
    - fills are stored as execution source of truth
    - every closed trade can compute net_pnl_dollars (net of fees) and realized_R
    - corporate actions during open holds are logged and applied
    - Risk_Policy is versioned and lookups use the version effective at planned_date
    - pre_trade_locked_at locks the documented field set at first fill
  portfolio_metrics:
    - adjusted_daily_pnl computes correctly under start-of-day cash flow convention
    - daily_return_pct, time_weighted_return_pct, and cumulative_return_pct compute correctly via daily linking
    - current and max drawdown are available with correct sign convention
    - portfolio_heat_pct uses entry-anchored at-risk dollars floored at zero
    - gross exposure, cash percentage, and concentration are visible
  trade_metrics:
    - outcome_class assigned per scratch_epsilon
    - realized_R, MFE_R, MAE_R, capture_ratio (winners only), giveback variants are available
    - MFE/MAE precision is labeled
    - holding period is bucketed for swing trading analysis
    - multi-leg trades use VWAP entry/exit and FIFO matching
    - unplanned scale-ins are flagged but do not change initial_risk_dollars
  setup_and_process_metrics:
    - setup expectancy is sample-size labeled
    - process adherence and mistake cost are visible
    - mistake_cost_method is recorded alongside mistake_cost_R
    - lucky violations are tracked separately from mistake cost
  rules_engine:
    - hard blocks can be triggered by risk policy violations
    - review tasks can be triggered by metric thresholds
    - recommendation candidates include evidence and sample-size labels
    - review lifecycle rules trigger for missing or late reviews
    - no inference is required for production recommendations
  reports:
    - weekly report includes open positions and portfolio state
    - monthly report includes portfolio, setup, process, risk, and data quality sections
  data_quality:
    - missing_review and stale_open_trade are detectable via deterministic rules
    - corporate_action_unadjusted_count surfaces unadjusted positions
    - regime_classified_post_close flags hindsight-risk regime data
```

---

## 20. Final Production Position

The performance system should begin with portfolio truth and then drill down into trades, setups, process, and risk.

```yaml
final_performance_hierarchy:
  1_portfolio:
    question: "Is the account improving after cash flows, drawdown, exposure, and open risk are considered?"
  2_trade:
    question: "Are trades profitable per unit of initial risk?"
  3_setup:
    question: "Which repeatable setups produce edge?"
  4_process:
    question: "Is execution discipline helping or harming results?"
  5_risk:
    question: "Is the account taking appropriate risk for its return?"
  6_data_quality:
    question: "Are conclusions reliable enough to act on?"
```

For swing trading specifically, the system must not rely only on closed trades. It must include open-position performance, portfolio heat, unrealized R, account equity, and cash-flow-adjusted return because positions may stay open for days or weeks and fewer than ten open positions can still represent substantial account risk.

The safest production stance is:

```yaml
production_stance:
  use_algorithmic_metrics: true
  use_deterministic_rules: true
  require_evidence_for_every_recommendation: true
  label_small_sample_results: true
  avoid_automatic_strategy_changes: true
  avoid_required_ai_inference: true
  preserve_audit_trail_for_policy_and_setup_status_changes: true
  lock_pre_trade_fields_at_first_fill: true
  net_realized_R_of_fees: true
```

---

## 21. Enumeration Reference

This section centralizes all enums used throughout the specification. Inline mentions reference this section by name.

```yaml
reconciliation_status:
  - unreconciled
  - reconciled_match
  - reconciled_discrepancy
  - reconciled_discrepancy_resolved
  - manual_override

data_source:
  - broker_export
  - manual
  - computed
  - imported

cash_flow_type:
  - deposit
  - withdrawal
  - dividend
  - interest
  - fee_adjustment
  - transfer
  - other

direction:
  - long           # only allowed value in v1.1

trade_origin:
  - watchlist
  - screen
  - price_alert
  - earnings_gap
  - news_event
  - manual_discovery
  - reentry

market_regime:
  - uptrend_trending
  - uptrend_extended
  - distribution_top
  - bear_trending
  - bear_capitulation
  - range_choppy
  - bottom_basing
  - undefined

sector_condition:
  - leading
  - improving
  - neutral
  - weakening
  - lagging

catalyst:
  - earnings
  - product_news
  - sector_rotation
  - macro_event
  - technical_only
  - other

thesis_status:
  - valid
  - strengthening
  - weakening
  - invalidated
  - unclear

thesis_accuracy:
  - correct
  - partially_correct
  - incorrect
  - unclear

setup_validity_after_review:
  - valid
  - marginal
  - invalid
  - lucky

setup_status:
  - active
  - pilot
  - paused
  - retired

setup_family:
  - breakout
  - pullback
  - episodic_pivot
  - trend_continuation
  - reversal
  - other

mistake_tags:
  - none_observed
  - CHASED
  - SOLD_TOO_EARLY
  - MOVED_STOP_AWAY
  - HELD_AFTER_INVALIDATION
  - UNPLANNED_ADD
  - UNPLANNED_SCALE_IN
  - OVERSIZED
  - UNDERSIZED
  - SKIPPED_PLAN
  - REVENGE_TRADE
  - other

mistake_cost_method:
  - direct_measurement
  - counterfactual_estimate
  - bracketed_range

mistake_cost_confidence:
  - high
  - medium
  - low

emotional_state_pre_trade:
  - calm
  - confident
  - FOMO
  - revenge
  - tired
  - distracted
  - anxious
  - other

fill_action:
  - entry
  - add
  - trim
  - exit
  - stop
  - cover    # reserved for future short-side support; unused in v1.1

order_type:
  - market
  - limit
  - stop
  - stop_limit
  - other

manual_entry_confidence:
  - high
  - normal
  - low

corporate_action_type:
  - forward_split
  - reverse_split
  - cash_dividend
  - stock_dividend
  - spinoff
  - merger
  - ticker_change

mfe_mae_precision_level:
  - intraday_exact
  - intraday_estimated
  - daily_approximate

severity:
  - info
  - warning
  - critical
  - blocking

scope:
  - portfolio
  - trade
  - setup
  - process
  - risk
  - data_quality
  - reconciliation

alert_status:
  - open
  - acknowledged
  - dismissed
  - resolved
  - converted_to_task

recommendation_status:
  - open
  - acknowledged
  - dismissed
  - converted_to_rule_change
  - resolved

outcome_class:
  - win
  - loss
  - scratch

reliability_label:
  - insufficient_sample
  - provisional
  - actionable
  - high_confidence

drawdown_pause_action:
  - reduce_size
  - halt
  - review_required

volatility_regime:
  - low
  - normal
  - high
  - extreme
```

---

## 22. Direction Conventions (Long-Only Stub)

v1.1 supports long-only stock swing trading. Short-side coverage is intentionally out of scope. This section is a stub that documents the convention so a future v1.2 can extend it without reworking other sections.

```yaml
direction_conventions_v1_1:
  allowed_values:
    - long
  quantity_open:
    sign: "always positive"
  risk_per_share:
    formula: "planned_entry - initial_stop"   # positive for valid long plans
  raw_current_at_risk_dollars:
    formula: "(avg_cost - current_stop) * quantity_open"
  unrealized_pnl_dollars:
    formula: "(close_price - avg_cost) * quantity_open"
  distance_to_stop_pct:
    formula: "(current_price - current_stop) / current_price"
  distance_to_target_pct:
    formula: "(target_price - current_price) / current_price"
  entry_slippage_R:
    formula: "(planned_entry - vwap_entry_price) / risk_per_share"   # negative = paid worse than planned

future_extension_to_short:
  status: "out of scope for v1.1"
  notes: "Short-side support requires symmetric formulas with sign inversion based on direction, plus borrow-fee tracking, hard-to-borrow flagging, and unbounded-loss handling. To be addressed in a future version."
```

---

## 23. Changelog

```yaml
changelog:
  v1_1:
    date: "2026-05-05"
    summary: "Resolved 37 findings from the v1.0 review. See companion document swing_trading_metrics_v1_1_findings.md for the full audit trail."
    foundational_definitions_added:
      - F-011: avg_cost-anchored risk reference; explicit raw_current_at_risk_dollars formula
      - F-013: pre_trade_locked_at field set explicitly defined
      - F-014: scratch trade definition (default scratch_epsilon = 0.10)
      - F-015: initial_risk_dollars locked at first fill; unplanned scale-in handling
      - F-016: long-only direction conventions (short stubbed in §22)
    formula_corrections:
      - F-001: cumulative_return formula replaced with daily-linked TWR
      - F-002: TWR cash-flow timing convention specified (start-of-day)
      - F-003: profit_factor null on no losing trades
      - F-004: recovery_factor null on zero drawdown
      - F-005: breakeven_win_rate requires >=1 winner and >=1 loser
      - F-006: capture_ratio restricted to winners
      - F-007: giveback split into giveback_R_winner and giveback_R_winner_to_loser
      - F-008: first-day daily return rule
      - F-009: drawdown sign convention stated explicitly
      - F-010: decomposed expectancy includes scratch trades
    new_formulas_defined:
      - F-012: entry_slippage_R formula
      - F-017: multi-leg trade math with VWAP and FIFO matching
      - F-025: open MFE/MAE computation rules
    new_tables_and_fields:
      - F-019: Corporate_Actions table with adjustment rules
      - F-021: Risk_Policy versioning with effective_from / effective_to / policy_version
      - F-022: Setup_Status_History table
      - F-023: instrument_currency, fx_rate_at_entry, fx_rate_at_exit nullable fields (USD default)
      - F-026: mistake_cost_method enum field
      - F-033: regime_classified_at and regime_classified_post_close on Market_Context_Daily
    interpretive_guardrails:
      - F-027: cumulative_R vs cumulative_pnl_dollars distinction noted in dashboards
      - F-028: optional Sharpe / Sortino with reliability labels (not on default dashboards)
      - F-031: dividend / interest treatment clarified (not subtracted from adjusted_daily_pnl)
    rules_engine_additions:
      - F-037: early_negative_signal rule
      - F-034: review_overdue and review_completed_late rules
      - F-033: hindsight risk flagging rule
      - new: unplanned_scale_in_pattern rule
      - new: unadjusted_corporate_action data quality rule
    cleanup:
      - F-018: fees treatment in realized_R explicit
      - F-020: MWR / IRR reference removed
      - F-024: NYSE trading calendar and UTC storage timezone specified
      - F-029: unrealized_R vs open_unrealized_R terminology standardized
      - F-030: §21 Enumeration Reference added
      - F-032: missing_review defined
      - F-035: version bumped to standalone-1.1
      - F-036: filename suggestion noted
    deferred_from_v1_1:
      - money-weighted return / IRR (removed; future enhancement if needed)
      - Sharpe / Sortino on default dashboards (kept as optional only)
      - multi-currency as first-class concept (fields added; MVP assumes USD)
      - tax / wash-sale tracking (not in scope)
      - short-side direction support (stubbed in §22)
```

*End of standalone specification.*
