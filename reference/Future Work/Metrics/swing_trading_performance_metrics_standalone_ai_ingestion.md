---
title: "Swing Trading Performance Metrics Specification"
version: "standalone-1.0"
document_type: "performance_metrics_execution_specification"
created_for:
  - AI orchestrator review
  - Python swing trading tool implementation
  - deterministic metrics engine design
  - deterministic rules engine design
created_date: "2026-05-05"
timezone_context: "Pacific/Honolulu"
not_financial_advice: true
primary_design_goal: "Define the fundamental data, derived facts, metrics, dashboards, and deterministic rule triggers required to convert a swing trading journal into performance-related information."
production_assumption: "The production path should rely on structured data, deterministic formulas, and explicit rules. LLM inference is optional for summaries and research, not required for core performance evaluation."
trading_style_context:
  style: "swing trading"
  instrument_scope_default: "stocks"
  expected_concurrent_open_positions: "fewer than 10"
  expected_holding_period: "days to weeks"
  expected_trade_frequency: "low to moderate"
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
    allowed_interpretation: "Early signal; create review task if concerning, but do not retire setup."
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
    - realized and unrealized P&L
    - fees and commissions
  position_data:
    - open position size
    - average cost
    - market value
    - current stop
    - current at-risk dollars
    - unrealized P&L
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
    - exit price
    - net P&L
    - realized R
    - MFE_R
    - MAE_R
    - capture ratio
  process_data:
    - process grade
    - entry grade
    - management grade
    - exit grade
    - mistake tags
    - mistake_cost_R
    - lucky_violation_R
  context_data:
    - setup family
    - source screen or trade origin
    - market regime
    - sector / theme
    - benchmark prices
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
| `snapshot_date` | date | yes | Trading day represented by the snapshot |
| `account_equity` | numeric | yes | Account value / net liquidation value at snapshot time |
| `net_liquidation_value` | numeric | yes | Broker-reported total account value; may equal account_equity |
| `cash_balance` | numeric | yes | Cash available at snapshot time |
| `long_market_value` | numeric | yes | Total market value of long positions |
| `short_market_value` | numeric | no | Total market value of short positions; default 0 for long-only stock scope |
| `gross_exposure` | numeric | yes | Sum of absolute market values of open positions |
| `net_exposure` | numeric | yes | Long market value minus short market value |
| `realized_pnl_day` | numeric | no | Broker-reported realized P&L for the day |
| `unrealized_pnl_day` | numeric | no | Change in unrealized P&L for the day |
| `total_pnl_day` | numeric | no | Realized plus unrealized P&L for the day |
| `deposits_day` | numeric | yes | External deposits credited that day; default 0 |
| `withdrawals_day` | numeric | yes | External withdrawals debited that day; default 0 |
| `fees_commissions_day` | numeric | no | Fees and commissions charged that day |
| `reconciliation_status` | enum | yes | `unreconciled`, `reconciled_match`, `reconciled_discrepancy`, `manual_override` |
| `data_source` | enum | yes | `broker_export`, `manual`, `computed`, `imported` |

### 3.2 `Cash_Flows`

Purpose: Separate trading performance from deposits, withdrawals, dividends, interest, and transfers.

```yaml
table: Cash_Flows
grain: one_row_per_external_cash_flow
required_for:
  - adjusted daily P&L
  - time-weighted return
  - money-weighted return / IRR
  - accurate portfolio return reporting
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `cash_flow_id` | string | yes | Unique identifier |
| `date` | date | yes | Date of cash flow |
| `amount` | numeric | yes | Positive for inflow, negative for outflow |
| `type` | enum | yes | `deposit`, `withdrawal`, `dividend`, `interest`, `fee_adjustment`, `transfer`, `other` |
| `external_to_trading` | boolean | yes | True for deposits/withdrawals/transfers; false for dividends/interest if treated as return |
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
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `snapshot_date` | date | yes | Trading day represented |
| `trade_id` | string | yes | Linked trade |
| `ticker` | string | yes | Symbol |
| `quantity_open` | numeric | yes | Current open share quantity |
| `avg_cost` | numeric | yes | Current average cost |
| `close_price` | numeric | yes | End-of-day price |
| `market_value` | numeric | yes | `quantity_open * close_price` |
| `unrealized_pnl_dollars` | numeric | yes | Open P&L in dollars |
| `unrealized_R` | numeric | yes | Open P&L normalized by initial risk |
| `current_stop` | numeric | yes | Current stop level |
| `raw_current_at_risk_dollars` | numeric | yes | Risk to current stop before floor |
| `portfolio_heat_contribution_dollars` | numeric | yes | `max(0, raw_current_at_risk_dollars)` |
| `locked_in_profit_at_stop_dollars` | numeric | yes | `max(0, -raw_current_at_risk_dollars)` |
| `current_at_risk_R` | numeric | yes | Raw current at-risk dollars / initial risk dollars |
| `thesis_status` | enum | no | `valid`, `strengthening`, `weakening`, `invalidated`, `unclear` |
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
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `trade_id` | string | yes | Unique trade ID |
| `ticker` | string | yes | Symbol |
| `direction` | enum | yes | `long` or `short`; long-only tools may restrict to `long` |
| `setup_id` | string | yes | Linked setup |
| `trade_origin` | enum | yes | `watchlist`, `screen`, `price_alert`, `earnings_gap`, `news_event`, `manual_discovery`, `reentry` |
| `source_screen` | string | conditional | Required when trade_origin is `screen` or `watchlist` derived from a screen |
| `planned_date` | date | yes | Planning date |
| `planned_entry` | numeric | yes | Intended entry price |
| `initial_stop` | numeric | yes | Planned initial stop |
| `risk_per_share` | numeric | yes | `abs(planned_entry - initial_stop)` |
| `planned_position_size` | numeric | yes | Planned shares |
| `planned_risk_dollars` | numeric | yes | Risk in dollars at initial stop |
| `planned_reward_risk_ratio` | numeric | no | Planned target reward divided by initial risk |
| `target_1` | numeric | no | First target |
| `target_2` | numeric | no | Second target |
| `market_regime` | enum | yes | Trader-selected or deterministic model output |
| `sector_condition` | enum | no | `leading`, `improving`, `neutral`, `weakening`, `lagging` |
| `catalyst` | enum | yes | Catalyst classification; may be `technical_only` |
| `thesis` | text | yes | Why trade should work |
| `invalidation_condition` | text | yes | What proves the thesis wrong |
| `premortem_failure_reasons` | list[text] | yes | Recommended minimum 3 reasons |
| `pre_trade_quality_score` | numeric | yes | 0-10 score or equivalent |
| `emotional_state_pre_trade` | list[enum] | yes | Structured tags such as `calm`, `FOMO`, `revenge`, `tired` |
| `pre_trade_locked_at` | datetime | conditional | Set at first fill; protects hindsight integrity |

### 3.5 `Fills`

Purpose: Represent actual broker execution. Fills are the source of truth for entries, exits, partials, position size, and realized P&L.

```yaml
table: Fills
grain: one_row_per_broker_fill
required_for:
  - actual entry price
  - actual exit price
  - actual position size
  - slippage
  - realized P&L
  - reconciliation
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `fill_id` | string | yes | Unique fill ID |
| `trade_id` | string | yes | Linked trade |
| `fill_datetime` | datetime | yes | Fill timestamp |
| `ticker` | string | yes | Symbol |
| `action` | enum | yes | `entry`, `add`, `trim`, `exit`, `stop`, `cover` |
| `quantity` | numeric | yes | Filled quantity |
| `price` | numeric | yes | Fill price |
| `fees` | numeric | no | Fees or commissions |
| `order_type` | enum | no | `market`, `limit`, `stop`, `stop_limit`, `other` |
| `rule_based` | boolean | yes | Whether fill followed the plan |
| `manual_entry_confidence` | enum | no | `high`, `normal`, `low` |
| `reconciliation_status` | enum | yes | Status against broker export |

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
| `reviewed_at` | datetime | yes | Review timestamp |
| `thesis_accuracy` | enum | yes | `correct`, `partially_correct`, `incorrect`, `unclear` |
| `setup_validity_after_review` | enum | yes | `valid`, `marginal`, `invalid`, `lucky` |
| `entry_grade` | enum | yes | A-F or numeric equivalent |
| `management_grade` | enum | yes | A-F or numeric equivalent |
| `exit_grade` | enum | yes | A-F or numeric equivalent |
| `process_grade` | enum | yes | Overall process grade |
| `mistake_tags` | list[enum] | yes | Structured mistake tags; use `none_observed` when none apply |
| `mistake_cost_R` | numeric | yes | Non-negative R harm from rule violations |
| `lucky_violation_R` | numeric | yes | Non-negative R benefit from profitable rule violation |
| `mistake_cost_confidence` | enum | yes | `high`, `medium`, `low` |
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
| `date` | date | yes | Trading day |
| `market_regime` | enum | yes | Manual or deterministic classification |
| `benchmark_symbol` | string | yes | Example: SPY, QQQ, IWM |
| `benchmark_close` | numeric | yes | Benchmark close |
| `benchmark_daily_return_pct` | numeric | yes | Benchmark daily return |
| `index_above_50dma` | boolean | no | Optional deterministic regime input |
| `index_above_200dma` | boolean | no | Optional deterministic regime input |
| `breadth_metric` | numeric | no | Optional breadth input |
| `volatility_regime` | enum | no | `low`, `normal`, `high`, `extreme` |

### 3.8 `Setup_Playbook`

Purpose: Define setups so performance can be segmented by actual strategy.

| Field | Type | Required | Description |
|---|---:|---:|---|
| `setup_id` | string | yes | Unique setup ID |
| `setup_name` | string | yes | Human-readable setup name |
| `setup_family` | enum | yes | Example: `breakout`, `pullback`, `episodic_pivot`, `trend_continuation` |
| `status` | enum | yes | `active`, `pilot`, `paused`, `retired` |
| `market_regime_allowed` | list[enum] | no | Regimes where setup is allowed |
| `entry_rule` | text | yes | Objective entry definition |
| `stop_rule` | text | yes | Objective stop definition |
| `exit_rule` | text | yes | Objective exit definition |

### 3.9 `Risk_Policy`

Purpose: Define account-level limits used by metrics and deterministic rules.

| Field | Type | Required | Description |
|---|---:|---:|---|
| `policy_id` | string | yes | Active risk policy ID |
| `max_concurrent_positions` | numeric | yes | For this swing trading context, expected below 10 |
| `max_account_risk_per_trade_pct` | numeric | yes | Max initial risk per trade |
| `max_portfolio_heat_pct` | numeric | yes | Max total open risk as percentage of equity |
| `max_single_position_pct` | numeric | no | Max market value in one position |
| `max_sector_exposure_pct` | numeric | no | Max exposure to one sector/theme |
| `consecutive_losses_pause_threshold` | numeric | no | Loss streak pause threshold |
| `drawdown_pause_threshold_R` | numeric | no | Optional drawdown risk threshold |
| `drawdown_pause_action` | enum | no | `reduce_size`, `halt`, `review_required` |

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
| `date` | date | Trading day |
| `start_equity` | numeric | Prior day ending equity or same-day start equity |
| `end_equity` | numeric | End-of-day account equity |
| `external_cash_flow` | numeric | Deposits minus withdrawals and other external flows |
| `adjusted_daily_pnl` | numeric | End equity minus start equity minus external cash flow |
| `daily_return_pct` | numeric | Adjusted daily P&L / start equity |
| `cumulative_return_pct` | numeric | Cumulative adjusted portfolio return |
| `time_weighted_return_pct` | numeric | Linked daily returns, cash-flow adjusted |
| `cumulative_pnl_dollars` | numeric | Cumulative trading P&L excluding external cash flows |
| `cumulative_R` | numeric | Sum of closed realized R to date |
| `open_unrealized_R` | numeric | Sum of open unrealized R |
| `total_R_including_open` | numeric | Closed cumulative R plus open unrealized R |
| `portfolio_heat_dollars` | numeric | Sum of open risk contributions floored at zero |
| `portfolio_heat_pct` | numeric | Portfolio heat / account equity |
| `gross_exposure_pct` | numeric | Gross exposure / account equity |
| `net_exposure_pct` | numeric | Net exposure / account equity |
| `cash_pct` | numeric | Cash / account equity |
| `open_position_count` | numeric | Count of open trades |
| `largest_position_pct` | numeric | Largest position value / account equity |
| `top_3_positions_pct` | numeric | Top 3 position values / account equity |
| `largest_sector_exposure_pct` | numeric | Largest sector exposure / account equity |
| `drawdown_dollars` | numeric | Current equity minus equity peak |
| `drawdown_pct` | numeric | Drawdown dollars / equity peak |
| `drawdown_R` | numeric | Current cumulative R minus peak cumulative R |
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
```

| Field | Type | Description |
|---|---:|---|
| `trade_id` | string | Trade ID |
| `ticker` | string | Symbol |
| `setup_id` | string | Setup ID |
| `setup_family` | enum | Setup family |
| `trade_origin` | enum | Origin of trade idea |
| `source_screen` | string | Source screen when applicable |
| `market_regime` | enum | Regime at entry |
| `entry_date` | date | First fill date |
| `exit_date` | date | Final exit date |
| `holding_period_days` | numeric | Days from entry to exit |
| `initial_risk_dollars` | numeric | Immutable initial risk |
| `net_pnl_dollars` | numeric | Net realized P&L |
| `realized_R` | numeric | Net P&L / initial risk |
| `MFE_R` | numeric | Maximum favorable excursion in R |
| `MAE_R` | numeric | Maximum adverse excursion in R |
| `capture_ratio` | numeric/null | Realized R / MFE_R when applicable |
| `giveback_R` | numeric | MFE_R minus realized_R |
| `entry_slippage_R` | numeric | Entry slippage normalized by initial risk |
| `process_grade` | enum | Overall process grade |
| `entry_grade` | enum | Entry grade |
| `management_grade` | enum | Management grade |
| `exit_grade` | enum | Exit grade |
| `mistake_tags` | list | Mistake tags |
| `mistake_cost_R` | numeric | Non-negative cost of mistakes |
| `lucky_violation_R` | numeric | Non-negative benefit from rule violation |
| `pre_trade_quality_score` | numeric | Pre-trade score |
| `thesis_accuracy` | enum | Post-trade thesis outcome |
| `setup_validity_after_review` | enum | Post-trade setup validity |
| `reconciliation_status` | enum | Broker reconciliation status |
| `mfe_mae_precision_level` | enum | `intraday_exact`, `intraday_estimated`, `daily_approximate` |

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

Fields should include sample size, net R, expectancy, win rate, average win/loss, profit factor, payoff ratio, max drawdown R, MFE/MAE, capture ratio, mistake rate, process adherence, reliability label, and recommended setup status candidate.

### 4.4 `Process_Performance_Summary`

Purpose: Aggregate process and behavior quality.

Fields:

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
```

### 4.5 `Performance_Alerts`

Purpose: Store deterministic rules engine outputs.

| Field | Type | Description |
|---|---:|---|
| `alert_id` | string | Unique ID |
| `generated_at` | datetime | Timestamp |
| `rule_id` | string | Rule that triggered |
| `severity` | enum | `info`, `warning`, `critical`, `blocking` |
| `scope` | enum | `portfolio`, `trade`, `setup`, `process`, `risk`, `data_quality` |
| `subject_id` | string | Setup ID, trade ID, or portfolio |
| `message` | text | Human-readable alert |
| `evidence_json` | json | Metric values and thresholds |
| `linked_trade_ids` | list | Supporting trades |
| `status` | enum | `open`, `acknowledged`, `dismissed`, `resolved`, `converted_to_task` |

---

## 5. Portfolio Performance Metrics

Portfolio performance should be evaluated before setup and trade performance because it answers whether the account is actually improving after open risk, drawdown, exposure, and cash flows are considered.

### 5.1 Net Liquidation Value

```text
net_liquidation_value = cash_balance + market_value_of_open_positions
```

Primary use: account equity curve.

### 5.2 Adjusted Daily P&L

```text
adjusted_daily_pnl = end_equity - start_equity - external_cash_flow
```

This prevents deposits from being counted as trading gains.

### 5.3 Daily Return

```text
daily_return_pct = adjusted_daily_pnl / start_equity
```

### 5.4 Time-Weighted Return

```text
time_weighted_return = product(1 + daily_return_pct) - 1
```

Use time-weighted return as the main portfolio return metric when external deposits or withdrawals occur.

### 5.5 Cumulative Return

```text
cumulative_return_pct = current_adjusted_equity / starting_adjusted_equity - 1
```

### 5.6 Portfolio Drawdown

```text
equity_peak_to_date = max(account_equity from start through current_date)
```

```text
drawdown_dollars = account_equity - equity_peak_to_date
```

```text
drawdown_pct = drawdown_dollars / equity_peak_to_date
```

Drawdown should be zero or negative.

### 5.7 Portfolio Heat

Portfolio heat measures open risk to stops, not market value exposure.

```text
portfolio_heat_dollars = sum(max(0, raw_current_at_risk_dollars) across open positions)
```

```text
portfolio_heat_pct = portfolio_heat_dollars / account_equity
```

Important rule: if a stop has been moved above breakeven, locked-in profit should not offset risk in other positions. Therefore portfolio heat uses the floored risk contribution.

### 5.8 Exposure

```text
gross_exposure = sum(abs(position_market_value))
```

```text
gross_exposure_pct = gross_exposure / account_equity
```

```text
net_exposure = long_market_value - short_market_value
```

```text
net_exposure_pct = net_exposure / account_equity
```

For long-only stock swing trading, net exposure usually equals long exposure.

### 5.9 Cash Allocation

```text
cash_pct = cash_balance / account_equity
```

High cash is not automatically bad. It should be interpreted relative to market regime, setup availability, and recent performance.

### 5.10 Concentration

```text
position_weight = position_market_value / account_equity
```

```text
largest_position_pct = max(position_weight)
```

```text
top_3_positions_pct = sum(top_3_position_weights)
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

Benchmark interpretation should distinguish absolute and relative results:

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

---

## 6. Trade Performance Metrics

All trade-level metrics should be normalized in R where possible.

```text
1R = initial planned risk on the trade
```

### 6.1 Realized R

```text
realized_R = net_pnl_dollars / initial_risk_dollars
```

### 6.2 Net R

```text
net_R = sum(realized_R)
```

### 6.3 Expectancy

```text
expectancy_R = average(realized_R)
```

### 6.4 Decomposed Expectancy

```text
expectancy_R = (win_rate * avg_win_R) + (loss_rate * avg_loss_R)
```

Where `avg_loss_R` is stored as a negative number.

### 6.5 Profit Factor

```text
profit_factor = sum(realized_R where realized_R > 0) / abs(sum(realized_R where realized_R < 0))
```

### 6.6 Payoff Ratio

```text
payoff_ratio = avg_win_R / abs(avg_loss_R)
```

### 6.7 Breakeven Win Rate

```text
breakeven_win_rate = abs(avg_loss_R) / (avg_win_R + abs(avg_loss_R))
```

### 6.8 Holding Period

```text
holding_period_days = exit_date - entry_date
```

For swing trading, report holding period in days and bucket it:

```yaml
holding_period_buckets:
  very_short: "0-2 days"
  normal_short_swing: "3-7 days"
  normal_swing: "8-21 days"
  extended_swing: "22+ days"
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
```

Useful formulas:

```text
open_unrealized_R = unrealized_pnl_dollars / initial_risk_dollars
```

```text
distance_to_stop_pct = (current_price - current_stop) / current_price
```

For longs, if distance_to_stop is small and thesis_status is weakening, the system should flag the position for review.

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

### 8.3 Capture Ratio

```text
capture_ratio = realized_R / MFE_R
```

Only compute when:

```yaml
capture_ratio_valid_when:
  - realized_R > 0
  - MFE_R > 0
```

Otherwise set to null / not applicable.

### 8.4 Giveback

```text
giveback_R = MFE_R - realized_R
```

For winning trades, giveback measures how much available open profit was surrendered.

### 8.5 Exit Efficiency Diagnostics

```yaml
exit_efficiency_metrics:
  average_capture_ratio: number
  median_capture_ratio: number
  average_giveback_R: number
  winners_that_became_losers_count: number
  trades_hit_1R_MFE_but_closed_negative_count: number
  trades_hit_2R_MFE_but_closed_under_1R_count: number
```

Interpretation:

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
  - avg_win_R
  - avg_loss_R
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

Break down by stage:

```yaml
plan_adherence_breakdown:
  - entry_adherence_rate
  - sizing_adherence_rate
  - stop_adherence_rate
  - management_adherence_rate
  - exit_adherence_rate
```

### 10.2 Mistake Cost

```text
total_mistake_cost_R = sum(mistake_cost_R)
```

Break down by mistake tag:

```yaml
mistake_cost_by_tag:
  CHASED: number
  SOLD_TOO_EARLY: number
  MOVED_STOP_AWAY: number
  HELD_AFTER_INVALIDATION: number
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

Interpretation:

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
  current_drawdown_pct: number
  max_drawdown_pct: number
  current_drawdown_R: number
  max_drawdown_R: number
  max_consecutive_losses: number
  current_consecutive_losses: number
  largest_position_pct: number
  largest_sector_exposure_pct: number
  recovery_factor: number
  return_over_max_drawdown: number
```

### 11.1 Recovery Factor

```text
recovery_factor = net_profit / abs(max_drawdown_dollars)
```

R version:

```text
R_recovery_factor = net_R / abs(max_drawdown_R)
```

### 11.2 Return Over Max Drawdown

```text
return_over_max_drawdown = cumulative_return_pct / abs(max_drawdown_pct)
```

### 11.3 Loss Streak Metrics

```yaml
loss_streak_metrics:
  current_consecutive_losses: number
  max_consecutive_losses: number
  R_lost_during_worst_streak: number
  review_completed_after_streak: boolean
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
  mfe_mae_precision_distribution:
    - intraday_exact
    - intraday_estimated
    - daily_approximate
```

### 12.1 Metric Validity Rules

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
```

### 13.7 Exit Efficiency Rules

```yaml
exit_efficiency_rules:
  poor_capture:
    condition: "winning_trade_sample_size >= 10 and average_MFE_R >= 1.5 and average_capture_ratio < 0.40"
    action: create_exit_management_review_task
  excessive_giveback:
    condition: "winning_trade_sample_size >= 10 and average_giveback_R > 1.0"
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
  - win rate
  - average win/loss
  - MFE_R
  - MAE_R
  - capture ratio
  - giveback
  - setup performance summaries
  - process grade distributions
  - mistake cost by tag
  - lucky violation counts
  - review tasks
  - hard blocks
  - warnings
  - setup pause candidates
  - setup retire candidates
```

### 14.2 Requires Human Judgment or Optional AI Assistance

The following require human judgment or optional AI assistance unless the underlying inputs are fully structured:

```yaml
inference_or_judgment_required:
  - visual chart pattern validation
  - determining whether a base was constructive from an image
  - identifying exact psychological cause from free-text notes
  - creating a brand-new trading rule
  - deciding whether a setup should actually be retired
  - approving a size increase
  - determining causal explanation from small samples
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
    - cumulative_R
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
    - unrealized_R
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
```

### 15.2 Trade Dashboard

```yaml
trade_dashboard:
  - total_closed_trades
  - net_R
  - expectancy_R
  - win_rate
  - avg_win_R
  - avg_loss_R
  - profit_factor
  - payoff_ratio
  - breakeven_win_rate
  - average_holding_period_days
  - average_MFE_R
  - average_MAE_R
  - average_capture_ratio
  - average_giveback_R
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
    unrealized_R:
    total_R_including_open:
    positions_with_weakening_thesis:
    largest_position_pct:
    largest_sector_exposure_pct:
  closed_trade_summary:
    closed_trades:
    net_R:
    expectancy_R:
    win_rate:
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
    - next_month_review_tasks
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
    - Risk_Policy
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
    - realized_R
    - MFE_R
    - MAE_R
    - capture_ratio
    - giveback_R
    - holding_period_days
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
  stage_6_reporting:
    - portfolio dashboard
    - trade dashboard
    - setup dashboard
    - process dashboard
    - weekly report
    - monthly report
```

---

## 19. Acceptance Criteria

A production implementation satisfies this specification when:

```yaml
acceptance_criteria:
  data_foundation:
    - daily account equity snapshots can be stored and reconciled
    - external cash flows are captured separately from trading P&L
    - open positions are snapshotted at least daily
    - fills are stored as execution source of truth
    - every closed trade can compute net P&L and realized_R
  portfolio_metrics:
    - adjusted_daily_pnl computes correctly
    - daily_return_pct and time_weighted_return_pct compute correctly
    - current and max drawdown are available
    - portfolio_heat_pct uses floored open risk contributions
    - gross exposure, cash percentage, and concentration are visible
  trade_metrics:
    - realized_R, MFE_R, MAE_R, capture_ratio, and giveback_R are available
    - MFE/MAE precision is labeled
    - holding period is bucketed for swing trading analysis
  setup_and_process_metrics:
    - setup expectancy is sample-size labeled
    - process adherence and mistake cost are visible
    - lucky violations are tracked separately from mistake cost
  rules_engine:
    - hard blocks can be triggered by risk policy violations
    - review tasks can be triggered by metric thresholds
    - recommendation candidates include evidence and sample-size labels
    - no inference is required for production recommendations
  reports:
    - weekly report includes open positions and portfolio state
    - monthly report includes portfolio, setup, process, risk, and data quality sections
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
```

*End of standalone specification.*
