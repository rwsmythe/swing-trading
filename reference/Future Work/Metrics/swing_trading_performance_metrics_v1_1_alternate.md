---
title: "Swing Trading Performance Metrics Specification — Alternate v1.1"
version: "standalone-1.1-alt"
document_type: "performance_metrics_execution_specification"
prior_version: "standalone-1.0"
companion_documents:
  - "swing_trading_metrics_v1_1_findings.md"
  - "swing_trading_performance_metrics_v1_1.md"
  - "swing_trading_metrics_v1_1_rebuttal_determinations.md"
created_for:
  - AI orchestrator review
  - Python swing trading tool implementation
  - deterministic metrics engine design
  - deterministic rules engine design
created_date: "2026-05-05"
timezone_context: "Pacific/Honolulu"
storage_timezone: "UTC"
trading_calendar: "NYSE"
not_financial_advice: true
primary_design_goal: "Define the data, derived facts, formulas, dashboards, and deterministic rule triggers required to convert a low-volume swing trading journal into portfolio, trade, setup, process, and risk performance information."
production_assumption: "Core production evaluation uses structured data, deterministic formulas, explicit rule thresholds, and human review for ambiguous causes. AI/LLM inference is optional for summaries and explanations, not required for core performance decisions."
trading_style_context:
  style: "swing trading"
  instrument_scope_default: "stocks"
  direction_scope: "long_only"
  expected_concurrent_open_positions: "fewer than 10"
  expected_holding_period: "days to weeks"
  expected_trade_frequency: "low to moderate"
  account_currency_default: "USD"
---

# Swing Trading Performance Metrics Specification — Alternate v1.1

## 0. Purpose

This document is a standalone production specification for converting a swing trading journal into performance-related information. It is designed for a Python swing trading tool with a deterministic metrics engine and deterministic rules engine.

The system must answer six questions:

```yaml
performance_domains:
  portfolio_performance:
    question: "Is the account growing efficiently and survivably after cash flows, exposure, open risk, and drawdown are considered?"
  trade_performance:
    question: "Are individual trades profitable per unit of planned and executed risk?"
  setup_performance:
    question: "Which repeatable setups have measurable edge?"
  process_performance:
    question: "Is behavior and execution discipline helping or hurting results?"
  risk_performance:
    question: "Is the account taking appropriate risk for the return achieved?"
  data_quality:
    question: "Are the metrics trustworthy enough to act on?"
```

Production outputs should be generated from structured data:

```yaml
production_model:
  metrics_engine:
    outputs:
      - derived portfolio facts
      - derived trade facts
      - setup summaries
      - process summaries
      - risk summaries
      - metric reliability labels
  rules_engine:
    outputs:
      - hard blocks
      - warnings
      - review tasks
      - recommendation candidates
      - rule-change candidates
  human_review:
    role:
      - determine ambiguous causes
      - approve setup status changes
      - approve risk policy changes
      - approve any strategy rule changes
  optional_ai_assist:
    allowed:
      - summarization
      - report drafting
      - explanation of metrics
      - evidence organization
    not_allowed_as_required_dependency:
      - automatic strategy changes
      - automatic size increases
      - psychological inference from prose
      - chart-pattern validation from images
```

## 1. Scope and Core Conventions

```yaml
scope:
  trading_style: swing_trading
  instrument_default: stocks
  direction_default: long_only
  concurrent_open_positions_expected: "<10"
  holding_period_expected: "days_to_weeks"
  account_currency_default: USD
  storage_timezone: UTC
  user_display_timezone: Pacific/Honolulu
  trading_calendar: NYSE
```

### 1.1 Sign, Timing, and Reliability Conventions

```yaml
core_conventions:
  drawdown:
    sign: "always <= 0"
    threshold_rule: "drawdown thresholds must be negative numbers"
  cash_flow_timing:
    default: start_of_day
    alternatives_allowed:
      - end_of_day
      - intraday_known
    note: "Cash flow effective timing is stored on each Cash_Flows row."
  fees:
    default_metric: "net of fees and commissions"
    optional_metric: "gross metrics retained for cost impact analysis"
  trading_day:
    definition: "NYSE trading day; no rows required for non-trading days; half-days count as trading days"
  scratch_trade:
    definition: "abs(realized_R_budget) < scratch_epsilon"
    default_scratch_epsilon: 0.10
  inference:
    production_required: false
    deterministic_rules_required: true
```

## 2. Low-Volume Swing Trading Guardrails

Because swing trading produces small samples, the system must suppress overconfident conclusions.

```yaml
sample_size_policy:
  individual_trade_review:
    minimum_sample_size: 1
    allowed: "single-trade review only"
  early_setup_signal:
    minimum_sample_size: 10
    allowed: "informational review task only"
  setup_review_candidate:
    minimum_sample_size: 20
    allowed: "structured setup review or pause candidate"
  setup_retirement_candidate:
    minimum_sample_size: 30
    allowed: "retire candidate only if process quality and data quality are acceptable"
  benchmark_comparison_candidate:
    minimum_trading_days: 60
    allowed: "benchmark-relative review candidate"
  risk_adjusted_return_provisional:
    minimum_monthly_returns: 12
    allowed: "Sharpe/Sortino provisional only"
  risk_adjusted_return_actionable:
    minimum_monthly_returns: 24
    allowed: "Sharpe/Sortino actionable"
```

```yaml
metric_reliability_labels:
  insufficient_sample:
    rule: "sample below threshold"
    behavior: "show metric, suppress conclusions"
  provisional:
    rule: "sample meets early threshold but not action threshold"
    behavior: "allow review task, suppress major action"
  actionable:
    rule: "sample meets action threshold and data_quality_score is acceptable"
    behavior: "allow recommendation candidate"
  high_confidence:
    rule: "finding persists across multiple windows with high data quality"
    behavior: "allow stronger recommendation candidate"
```

## 3. Fundamental Data Model

### 3.1 `Account_Equity_Snapshots`

Purpose: daily account-level state, preferably from broker export.

```yaml
table: Account_Equity_Snapshots
grain: one_row_per_nyse_trading_day
required: true
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `snapshot_date` | date | yes | NYSE trading day |
| `account_currency` | string | yes | Default `USD` |
| `account_equity` | numeric | yes | Account equity / net liquidation value |
| `cash_balance` | numeric | yes | Cash at end of day |
| `long_market_value` | numeric | yes | Total long market value |
| `gross_exposure` | numeric | yes | Sum absolute market value of positions |
| `net_exposure` | numeric | yes | Long-only default equals long market value |
| `realized_pnl_day` | numeric | no | Broker-reported realized P&L |
| `unrealized_pnl_day` | numeric | no | Broker-reported unrealized P&L change |
| `fees_commissions_day` | numeric | no | Total costs |
| `reconciliation_status` | enum | yes | See §17 |
| `data_source` | enum | yes | broker_export, manual, computed, imported |

**Implementation note:** `Account_Equity_Snapshots` may include broker-reported cash movements, but `Cash_Flows` is the canonical table for classifying external versus trading-related flows.

### 3.2 `Cash_Flows`

Purpose: identify deposits/withdrawals separately from trading return.

```yaml
table: Cash_Flows
grain: one_row_per_cash_flow
canonical_for: "cash-flow classification"
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `cash_flow_id` | string | yes | Unique ID |
| `date` | date | yes | NYSE trading day |
| `amount` | numeric | yes | Positive inflow, negative outflow |
| `currency` | string | yes | Default USD |
| `type` | enum | yes | deposit, withdrawal, dividend, interest, transfer, fee_adjustment, other |
| `external_to_trading` | boolean | yes | True for deposits/withdrawals/transfers; false for dividends/interest |
| `cash_flow_effective_timing` | enum | yes | start_of_day, end_of_day, intraday_known |
| `effective_timestamp` | datetime | conditional | Required when timing is intraday_known |
| `reconciliation_status` | enum | yes | Broker reconciliation status |
| `notes` | text | no | Optional explanation |

### 3.3 `Trade_Plans`

Purpose: locked pre-trade plan and risk budget.

```yaml
table: Trade_Plans
grain: one_row_per_planned_trade
locked_at: first_fill
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `trade_id` | string | yes | Unique trade ID |
| `ticker` | string | yes | Symbol at planning |
| `direction` | enum | yes | `long` in this version |
| `setup_id` | string | yes | Linked setup |
| `trade_origin` | enum | yes | watchlist, screen, price_alert, earnings_gap, news_event, manual_discovery, reentry |
| `source_screen` | string | conditional | Required for screen/watchlist-derived ideas |
| `planned_date` | date | yes | Planning date |
| `planned_entry` | numeric | yes | Intended entry price |
| `initial_stop` | numeric | yes | Initial stop |
| `risk_per_share` | numeric | yes | `planned_entry - initial_stop`; must be positive for long trades |
| `planned_position_size` | numeric | yes | Planned full position size, including planned scale-ins |
| `planned_risk_budget_dollars` | numeric | yes | Maximum intended risk for the full planned trade |
| `target_1` | numeric | no | First target |
| `target_2` | numeric | no | Second target |
| `planned_reward_risk_ratio` | numeric | no | Planned reward/risk |
| `market_regime` | enum | yes | Locked at first fill |
| `sector_condition` | enum | no | leading, improving, neutral, weakening, lagging |
| `catalyst` | enum | yes | See §17 |
| `thesis` | text | yes | Why trade should work |
| `invalidation_condition` | text | yes | What proves the thesis wrong |
| `premortem_failure_reasons` | list[text] | yes | Recommended minimum 3 |
| `pre_trade_quality_score` | numeric | yes | 0–10 or equivalent |
| `emotional_state_pre_trade` | list[enum] | yes | See §17 |
| `pre_trade_locked_at` | datetime | conditional | Set at first fill |
| `risk_policy_version` | integer | yes | Version effective on planned date |

Locked field set after `pre_trade_locked_at`:

```yaml
pre_trade_locked_fields:
  - planned_entry
  - initial_stop
  - risk_per_share
  - planned_position_size
  - planned_risk_budget_dollars
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

Post-lock edits require an audit row and never silently rewrite performance calculations.

### 3.4 `Fills`

Purpose: execution source of truth.

```yaml
table: Fills
grain: one_row_per_broker_fill
canonical_for:
  - execution prices
  - execution quantities
  - fees
  - realized P&L reconstruction
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `fill_id` | string | yes | Unique fill ID |
| `trade_id` | string | yes | Linked trade |
| `fill_datetime` | datetime | yes | Stored UTC |
| `ticker` | string | yes | Symbol at fill |
| `action` | enum | yes | entry, add, trim, exit, stop |
| `quantity` | numeric | yes | Filled shares |
| `price` | numeric | yes | Fill price |
| `fees` | numeric | no | Fees/commissions |
| `order_type` | enum | no | market, limit, stop, stop_limit, other |
| `rule_based` | boolean | yes | Whether fill followed plan |
| `planned_scale_in` | boolean | no | True if add was in original plan |
| `reconciliation_status` | enum | yes | Broker reconciliation status |

### 3.5 `Positions_Daily_Snapshots`

Purpose: open-position state for swing trades held days/weeks.

```yaml
table: Positions_Daily_Snapshots
grain: one_row_per_open_position_per_nyse_trading_day
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `snapshot_date` | date | yes | NYSE trading day |
| `trade_id` | string | yes | Linked trade |
| `ticker` | string | yes | Current symbol |
| `quantity_open` | numeric | yes | Open shares, positive for longs |
| `avg_cost` | numeric | yes | Current cost basis per share |
| `close_price` | numeric | yes | End-of-day close |
| `high_price_used` | numeric | no | High used for MFE update, if available |
| `low_price_used` | numeric | no | Low used for MAE update, if available |
| `market_value` | numeric | yes | `quantity_open * close_price` |
| `unrealized_pnl_dollars` | numeric | yes | `(close_price - avg_cost) * quantity_open` |
| `unrealized_R_budget` | numeric | yes | Open P&L / planned risk budget |
| `current_stop` | numeric | yes | Current stop |
| `raw_current_at_risk_dollars` | numeric | yes | `(avg_cost - current_stop) * quantity_open` |
| `portfolio_heat_contribution_dollars` | numeric | yes | `max(0, raw_current_at_risk_dollars)` |
| `locked_in_profit_at_stop_dollars` | numeric | yes | `max(0, -raw_current_at_risk_dollars)` |
| `open_MFE_to_date_R` | numeric | yes | Highest favorable excursion to date using precision hierarchy |
| `open_MAE_to_date_R` | numeric | yes | Largest adverse excursion to date using precision hierarchy |
| `mfe_mae_precision_level` | enum | yes | intraday_exact, intraday_estimated, daily_approximate |
| `thesis_status` | enum | no | valid, strengthening, weakening, invalidated, unclear |
| `sector` | string | no | Sector/theme |
| `setup_id` | string | yes | Setup ID |

### 3.6 `Trade_Reviews`

Purpose: process and behavioral review after trade closure.

| Field | Type | Required | Description |
|---|---:|---:|---|
| `trade_id` | string | yes | Linked trade |
| `reviewed_at` | datetime | yes | UTC review timestamp |
| `thesis_accuracy` | enum | yes | correct, partially_correct, incorrect, unclear |
| `setup_validity_after_review` | enum | yes | valid, marginal, invalid, lucky |
| `entry_grade` | enum | yes | A-F |
| `management_grade` | enum | yes | A-F |
| `exit_grade` | enum | yes | A-F |
| `process_grade` | enum | yes | Overall process grade |
| `mistake_tags` | list[enum] | yes | `none_observed` when none apply |
| `plan_followed_R` | numeric | conditional | Counterfactual R if plan had been followed; required when mistake cost is computed |
| `mistake_cost_R` | numeric | yes | `max(0, plan_followed_R - actual_realized_R_budget)` |
| `lucky_violation_R` | numeric | yes | `max(0, actual_realized_R_budget - plan_followed_R)` |
| `mistake_cost_method` | enum | yes | direct_measurement, counterfactual_estimate, bracketed_range |
| `mistake_cost_confidence` | enum | yes | high, medium, low |
| `lesson_learned` | text | no | Human note |

### 3.7 Supporting Tables

```yaml
supporting_tables:
  Market_Context_Daily:
    purpose: "market regime, benchmark, hindsight-risk timestamp"
    key_fields:
      - date
      - market_regime
      - regime_classified_at
      - regime_classified_post_close
      - benchmark_symbol
      - benchmark_close
      - benchmark_daily_return_pct
  Setup_Playbook:
    purpose: "setup definition and current status view"
    key_fields:
      - setup_id
      - setup_name
      - setup_family
      - status
      - entry_rule
      - stop_rule
      - exit_rule
  Setup_Status_History:
    purpose: "audit trail for setup status changes"
    key_fields:
      - history_id
      - setup_id
      - status
      - effective_from
      - effective_to
      - change_reason
      - triggering_recommendation_id
  Risk_Policy:
    purpose: "versioned account-level limits and metric thresholds"
    key_fields:
      - policy_id
      - policy_version
      - effective_from
      - effective_to
      - max_concurrent_positions
      - max_account_risk_per_trade_pct
      - max_portfolio_heat_pct
      - max_single_position_pct
      - max_sector_exposure_pct
      - scratch_epsilon
      - review_lag_threshold_days
  Corporate_Actions:
    purpose: "audit and adjustment for splits/dividends/ticker changes"
    mvp_behavior: "log all events; automate common splits/dividends; flag mergers/spinoffs for manual reconciliation"
```

## 4. Derived Fact Tables

### 4.1 `Portfolio_Daily_Facts`

```yaml
table: Portfolio_Daily_Facts
grain: one_row_per_trading_day
derived_from:
  - Account_Equity_Snapshots
  - Cash_Flows
  - Positions_Daily_Snapshots
  - Market_Context_Daily
```

| Field | Description |
|---|---|
| `date` | NYSE trading day |
| `start_equity` | Prior end equity plus start-of-day external cash flows |
| `end_equity` | End-of-day account equity |
| `external_cash_flow` | Sum of `Cash_Flows.amount` where `external_to_trading=true` |
| `adjusted_daily_pnl` | End equity minus cash-flow-adjusted start equity |
| `daily_return_pct` | Adjusted daily P&L / start equity |
| `cumulative_return_pct` | Daily-linked return from inception/window start |
| `time_weighted_return_pct` | Daily-linked return for chosen window |
| `cumulative_pnl_dollars` | Cumulative trading P&L excluding external flows |
| `cumulative_R_budget` | Sum of closed `realized_R_budget` |
| `open_unrealized_R_budget` | Sum of open unrealized R budget |
| `total_R_budget_including_open` | Closed R plus open unrealized R |
| `portfolio_heat_dollars` | Sum of floored open risk |
| `portfolio_heat_pct` | Heat / account equity |
| `gross_exposure_pct` | Gross exposure / account equity |
| `net_exposure_pct` | Net exposure / account equity |
| `cash_pct` | Cash / account equity |
| `open_position_count` | Count open trades |
| `largest_position_pct` | Largest position / equity |
| `top_3_positions_pct` | Top 3 positions / equity |
| `largest_sector_exposure_pct` | Largest sector/theme exposure / equity |
| `drawdown_dollars` | Equity - equity peak, <= 0 |
| `drawdown_pct` | Drawdown dollars / equity peak, <= 0 |
| `drawdown_R_budget` | Cumulative R - peak cumulative R, <= 0 |
| `benchmark_return_pct` | Benchmark return over same window |
| `excess_return_pct` | Portfolio return - benchmark return |
| `data_quality_score` | Completeness/reconciliation score |

### 4.2 `Trade_Performance_Facts`

```yaml
table: Trade_Performance_Facts
grain: one_row_per_closed_trade
derived_from:
  - Trade_Plans
  - Fills
  - Positions_Daily_Snapshots
  - Trade_Reviews
  - Corporate_Actions
```

| Field | Description |
|---|---|
| `trade_id` | Trade ID |
| `ticker_at_entry` | Symbol at first entry fill |
| `ticker_at_exit` | Symbol at final exit fill |
| `setup_id` | Setup ID |
| `setup_family` | Setup family |
| `trade_origin` | Origin of idea |
| `market_regime` | Locked entry regime |
| `entry_date` | First entry fill date |
| `exit_date` | Final exit fill date |
| `holding_period_days` | Calendar days from entry to exit |
| `vwap_entry_price` | VWAP of entry/add fills |
| `vwap_exit_price` | VWAP of exit/trim/stop fills |
| `planned_risk_budget_dollars` | Locked intended risk budget |
| `initial_executed_risk_dollars` | Risk actually deployed by first opening tranche |
| `max_executed_risk_dollars` | Maximum positive risk deployed during trade |
| `gross_pnl_dollars` | Gross realized P&L |
| `total_fees_dollars` | Sum fees/commissions |
| `net_pnl_dollars` | Gross P&L minus fees |
| `realized_R_budget` | Net P&L / planned risk budget |
| `realized_R_initial` | Net P&L / initial executed risk |
| `realized_R_effective` | Net P&L / max executed risk |
| `gross_realized_R_budget` | Gross P&L / planned risk budget |
| `MFE_R_budget` | MFE in planned-risk units |
| `MAE_R_budget` | MAE in planned-risk units |
| `mfe_mae_precision_level` | Precision label |
| `outcome_class` | win, loss, scratch based on `realized_R_budget` |
| `capture_ratio` | Winners only: `realized_R_budget / MFE_R_budget` |
| `giveback_R_winner` | Winners only: `MFE_R_budget - realized_R_budget` |
| `giveback_R_winner_to_loser` | Losers with MFE>0: `MFE_R_budget - realized_R_budget` |
| `winner_to_loser_flag` | True if loss after MFE >= 1R |
| `entry_adverse_slippage_R` | Positive means worse entry than planned |
| `risk_added_after_initial_R` | Risk from unplanned adds / planned risk budget |
| `process_grade` | Overall process grade |
| `mistake_tags` | Process mistake tags |
| `mistake_cost_R` | Non-negative plan-following opportunity/harm cost |
| `lucky_violation_R` | Non-negative benefit from rule violation |
| `reconciliation_status` | Broker reconciliation status |

## 5. Portfolio Metrics

### 5.1 Daily Cash-Flow Adjusted P&L

Default start-of-day convention:

```text
external_cash_flow_D = sum(Cash_Flows.amount where external_to_trading = true and date = D)
start_equity_D = end_equity_{D-1} + external_cash_flow_D
adjusted_daily_pnl_D = end_equity_D - start_equity_D
```

When `cash_flow_effective_timing = intraday_known`, the implementation may compute Modified Dietz or subperiod-linked returns. If not implemented, label the affected return window `cash_flow_timing_approximate`.

### 5.2 Daily and Cumulative Return

```text
daily_return_pct_D = adjusted_daily_pnl_D / start_equity_D
cumulative_return_pct = product(1 + daily_return_pct) - 1
```

First-day rule:

```yaml
first_day_rule:
  if_no_prior_equity: "daily_return_pct = 0; start_equity = opening deposit"
```

### 5.3 Portfolio Drawdown

```text
equity_peak_to_date = max(account_equity from start through current_date)
drawdown_dollars = account_equity - equity_peak_to_date       # <= 0
drawdown_pct = drawdown_dollars / equity_peak_to_date          # <= 0
```

### 5.4 Portfolio Heat and Exposure

```text
raw_current_at_risk_dollars = (avg_cost - current_stop) * quantity_open
portfolio_heat_contribution_dollars = max(0, raw_current_at_risk_dollars)
locked_in_profit_at_stop_dollars = max(0, -raw_current_at_risk_dollars)
portfolio_heat_pct = sum(portfolio_heat_contribution_dollars) / account_equity
```

```text
gross_exposure_pct = gross_exposure / account_equity
net_exposure_pct = net_exposure / account_equity
cash_pct = cash_balance / account_equity
```

### 5.5 Concentration

```text
position_weight = position_market_value / account_equity
largest_position_pct = max(position_weight)
top_3_positions_pct = sum(top 3 position_weights)
effective_number_of_positions = 1 / sum(position_weight^2)    # optional
```

### 5.6 Benchmark Comparison

```text
excess_return_pct = portfolio_return_pct - benchmark_return_pct
```

Benchmark comparison is informational until at least 60 trading days are available.

## 6. Trade Metrics

### 6.1 R Denominators

This alternate v1.1 uses three R denominators to prevent scale-in distortion.

```yaml
R_denominators:
  planned_risk_budget_dollars:
    definition: "locked pre-trade maximum intended risk for the complete trade"
    primary_use: "portfolio-aligned expectancy and setup summaries"
  initial_executed_risk_dollars:
    definition: "risk actually deployed by the first opening tranche at the initial stop"
    primary_use: "entry/tranche efficiency"
  max_executed_risk_dollars:
    definition: "maximum positive risk actually deployed during the trade"
    primary_use: "pyramiding and effective-risk evaluation"
```

```text
realized_R_budget = net_pnl_dollars / planned_risk_budget_dollars
realized_R_initial = net_pnl_dollars / initial_executed_risk_dollars
realized_R_effective = net_pnl_dollars / max_executed_risk_dollars
```

Default dashboard expectancy uses `realized_R_budget` because it aligns outcomes with the intended risk budget. Advanced diagnostics also show the other two.

### 6.2 Outcome Classification

```yaml
outcome_classification:
  win: "realized_R_budget >= scratch_epsilon"
  loss: "realized_R_budget <= -scratch_epsilon"
  scratch: "abs(realized_R_budget) < scratch_epsilon"
  invariant: "win_rate + loss_rate + scratch_rate = 1"
```

### 6.3 Expectancy

```text
expectancy_R = average(realized_R_budget)
```

Decomposed:

```text
expectancy_R = win_rate * avg_win_R
             + loss_rate * avg_loss_R
             + scratch_rate * avg_scratch_R
```

### 6.4 Profit Factor and Edge Cases

```text
profit_factor = sum(realized_R_budget where realized_R_budget > 0)
              / abs(sum(realized_R_budget where realized_R_budget < 0))
```

If denominator is zero, return null with `no_losing_trades_in_window`. Never return `+inf`.

### 6.5 Payoff and Breakeven Win Rate

```text
payoff_ratio = avg_win_R / abs(avg_loss_R)
breakeven_win_rate = abs(avg_loss_R) / (avg_win_R + abs(avg_loss_R))
```

Both require at least one win and one loss.

### 6.6 Multi-Leg Trade Math

```yaml
multi_leg_rules:
  entry_vwap: "sum(price * quantity) over entry/add fills / sum(quantity) over entry/add fills"
  exit_vwap: "sum(price * quantity) over trim/exit/stop fills / sum(quantity) over trim/exit/stop fills"
  pnl_method: "FIFO matched lots preferred; VWAP approximation acceptable if lot matching unavailable"
  fees: "net_pnl is gross_pnl minus all trade-linked fees"
  unplanned_adds: "flag and compute risk_added_after_initial_R; do not rewrite planned risk budget"
```

### 6.7 Entry Slippage

For longs:

```text
entry_adverse_slippage_R = (vwap_entry_price - planned_entry) / risk_per_share
```

Interpretation:

```yaml
entry_adverse_slippage_R_interpretation:
  positive: "entered worse than planned"
  zero: "entered at planned price"
  negative: "entered better than planned"
```

### 6.8 MFE, MAE, Capture, and Giveback

```yaml
mfe_mae_precision_hierarchy:
  1_intraday_exact: "best available; after entry and before exit only"
  2_intraday_estimated: "partial intraday data"
  3_daily_approximate: "daily high/low; acceptable MVP fallback"
```

```text
capture_ratio = realized_R_budget / MFE_R_budget
```

Valid only for winning trades with `MFE_R_budget > 0`.

```text
giveback_R_winner = MFE_R_budget - realized_R_budget               # winners only
giveback_R_winner_to_loser = MFE_R_budget - realized_R_budget      # losers with MFE>0
winner_to_loser_flag = outcome_class == loss and MFE_R_budget >= 1.0
```

## 7. Open Position Metrics

Swing trading requires open-position visibility.

```yaml
open_position_metrics:
  - unrealized_pnl_dollars
  - unrealized_R_budget
  - open_MFE_to_date_R
  - open_MAE_to_date_R
  - current_stop
  - raw_current_at_risk_dollars
  - portfolio_heat_contribution_dollars
  - locked_in_profit_at_stop_dollars
  - thesis_status
  - days_held
  - distance_to_stop_pct
```

Open MFE/MAE must use available high/low or intraday data, not close-only when better data is present. If only close snapshots are available, label precision accordingly.

## 8. Setup Metrics

```yaml
setup_metrics:
  - sample_size
  - reliability_label
  - net_R_budget
  - expectancy_R_budget
  - win_rate
  - loss_rate
  - scratch_rate
  - avg_win_R
  - avg_loss_R
  - profit_factor
  - payoff_ratio
  - max_drawdown_R_budget
  - average_MFE_R_budget
  - average_MAE_R_budget
  - average_capture_ratio
  - average_giveback_R_winner
  - winner_to_loser_count
  - average_holding_period_days
  - mistake_rate
  - process_adherence_rate
  - A_grade_expectancy_R
```

### 8.1 Setup Classification Rules

```yaml
setup_classification_rules:
  insufficient_data:
    condition: "sample_size < 10"
    output: "display only; no conclusion"
  early_positive_signal:
    condition: "sample_size >= 10 and expectancy_R_budget > 0 and sample_size < 20"
    output: "informational positive review task"
  early_negative_signal:
    condition: "sample_size >= 10 and expectancy_R_budget < 0 and sample_size < 20"
    output: "informational negative review task"
  setup_review_candidate:
    condition: "sample_size >= 20 and expectancy_R_budget < 0"
    output: "create setup review task"
  pause_candidate:
    condition: "sample_size >= 20 and expectancy_R_budget < 0 and recent_expectancy_R_budget < 0"
    output: "pause candidate, human review required"
  retire_candidate:
    condition: "sample_size >= 30 and expectancy_R_budget < 0 and process_adherence_rate >= 0.80"
    output: "retire candidate, human review required"
  emphasize_candidate:
    condition: "sample_size >= 30 and expectancy_R_budget > portfolio_expectancy_R_budget and profit_factor >= 1.50 and process_adherence_rate >= 0.80"
    output: "emphasize candidate, not automatic size increase"
```

## 9. Process Metrics

```yaml
process_metrics:
  - plan_adherence_rate
  - entry_adherence_rate
  - sizing_adherence_rate
  - stop_adherence_rate
  - management_adherence_rate
  - exit_adherence_rate
  - percent_A_grade
  - A_grade_expectancy_R_budget
  - B_or_worse_expectancy_R_budget
  - rule_followed_expectancy_R_budget
  - rule_violated_expectancy_R_budget
  - total_mistake_cost_R
  - total_lucky_violation_R
  - top_mistake_tag_by_cost
  - repeated_mistake_tags
```

Mistake model:

```text
mistake_cost_R = max(0, plan_followed_R - actual_realized_R_budget)
lucky_violation_R = max(0, actual_realized_R_budget - plan_followed_R)
```

The two metrics are never netted.

## 10. Risk Metrics

```yaml
risk_metrics:
  - portfolio_heat_pct
  - max_portfolio_heat_pct
  - current_drawdown_pct
  - max_drawdown_pct
  - current_drawdown_R_budget
  - max_drawdown_R_budget
  - current_consecutive_losses
  - max_consecutive_losses
  - R_lost_during_worst_streak
  - largest_position_pct
  - largest_sector_exposure_pct
  - return_over_max_drawdown
  - recovery_factor
```

```text
recovery_factor = cumulative_pnl_dollars / abs(max_drawdown_dollars)
R_recovery_factor = cumulative_R_budget / abs(max_drawdown_R_budget)
```

If denominator is zero, return null with reliability flag `no_drawdown_recorded`.

## 11. Data Quality and Validity

```yaml
data_quality_metrics:
  - trade_completeness_score
  - portfolio_snapshot_completeness_score
  - percent_trades_reconciled
  - percent_account_snapshots_reconciled
  - unresolved_discrepancy_count
  - missing_fill_count
  - missing_review_count
  - stale_open_trade_count
  - missing_cash_flow_count
  - corporate_action_unadjusted_count
  - mfe_mae_precision_distribution
```

```yaml
missing_review_definition:
  condition: "closed trade has no Trade_Reviews row within Risk_Policy.review_lag_threshold_days after exit_date"
  default_threshold_days: 7
```

Metric validity:

```yaml
metric_validity_rules:
  final_portfolio_return_metrics:
    require:
      - account_snapshots_complete
      - cash_flows_classified
      - reconciliation_status_acceptable
  final_trade_pnl_metrics:
    require: "trade reconciliation_status in [reconciled_match, reconciled_discrepancy_resolved, manual_override]"
  process_metrics:
    allowed_before_reconciliation: true
    reason: "review memory decays"
  setup_conclusions:
    require:
      - sample_size_threshold_met
      - data_quality_score_sufficient
```

## 12. Deterministic Rules Engine

### 12.1 Rule Schema

```yaml
rule_schema:
  rule_id: string
  enabled: boolean
  scope: [portfolio, trade, setup, process, risk, data_quality, reconciliation]
  lookback_type: [last_n_trades, last_n_days, month_to_date, quarter_to_date, year_to_date, all_time]
  lookback_value: number
  minimum_sample_size: number
  data_quality_minimum: number
  condition_expression: string
  severity: [info, warning, critical, blocking]
  action: [notify, create_review_task, create_rule_change_candidate, block_trade, reduce_size_candidate, pause_setup_candidate, retire_setup_candidate]
  evidence_fields: list
  cooldown_period_days: number
```

### 12.2 Rule Outputs

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
  status: [open, acknowledged, dismissed, converted_to_rule_change, resolved]
```

### 12.3 Core Rule Set

```yaml
hard_blocks:
  max_positions:
    condition: "current_open_positions >= policy.max_concurrent_positions"
    action: block_trade
  portfolio_heat:
    condition: "portfolio_heat_after_trade_pct > policy.max_portfolio_heat_pct"
    action: block_trade
  missing_risk:
    condition: "planned_entry is null or initial_stop is null or planned_risk_budget_dollars is null"
    action: block_trade

portfolio_rules:
  excessive_drawdown:
    condition: "current_drawdown_R_budget <= policy.drawdown_pause_threshold_R and policy.drawdown_pause_threshold_R is not null"
    action: reduce_size_or_halt_per_policy
  concentration_too_high:
    condition: "largest_position_pct > policy.max_single_position_pct"
    action: create_concentration_review_task
  benchmark_underperformance:
    condition: "portfolio_return_pct < benchmark_return_pct and sample_days >= 60"
    action: create_benchmark_review_task

setup_rules:
  early_negative_signal:
    condition: "setup_sample_size >= 10 and setup_expectancy_R_budget < 0 and setup_sample_size < 20"
    action: create_informational_review_task
  setup_review_candidate:
    condition: "setup_sample_size >= 20 and setup_expectancy_R_budget < 0"
    action: create_setup_review_task
  setup_retire_candidate:
    condition: "setup_sample_size >= 30 and setup_expectancy_R_budget < 0 and process_adherence_rate >= 0.80"
    action: retire_setup_candidate

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

exit_efficiency_rules:
  poor_capture:
    condition: "winning_trade_sample_size >= 10 and average_MFE_R_budget >= 1.5 and average_capture_ratio < 0.40"
    action: create_exit_management_review_task
  winners_to_losers:
    condition: "trades_hit_1R_MFE_but_closed_negative_count >= 2 over last_20_trades"
    action: create_exit_rule_review_task

data_quality_rules:
  unresolved_discrepancies:
    condition: "unresolved_discrepancy_count > 0"
    action: repair_data_quality_before_final_metrics
  stale_open_trade:
    condition: "open_trade_without_snapshot_days >= 2"
    action: create_open_trade_update_task
  review_overdue:
    condition: "closed_trade has no review and today - exit_date > policy.review_lag_threshold_days"
    action: create_review_task
  review_completed_late:
    condition: "reviewed_at - exit_date > policy.review_lag_threshold_days"
    action: notify_and_flag_review_reliability
```

## 13. Dashboards

### 13.1 Portfolio Dashboard

```yaml
portfolio_dashboard:
  headline:
    - account_equity
    - cumulative_return_pct
    - time_weighted_return_pct
    - cumulative_pnl_dollars
    - cumulative_R_budget
    - total_R_budget_including_open
    - benchmark_return_pct
    - excess_return_pct
  risk:
    - current_drawdown_pct
    - max_drawdown_pct
    - current_drawdown_R_budget
    - max_drawdown_R_budget
    - portfolio_heat_pct
    - recovery_factor
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
    - open_unrealized_R_budget
    - open_risk_dollars
    - positions_with_weakening_thesis
    - stale_open_trade_count
  data_quality:
    - equity_snapshot_reconciled_through
    - unresolved_account_discrepancies
    - cash_flow_adjustment_status
    - corporate_action_unadjusted_count
```

**Interpretive note:** `cumulative_R_budget` measures normalized strategy performance. It is not a substitute for `cumulative_pnl_dollars` or cash-flow-adjusted portfolio return.

### 13.2 Trade, Setup, and Process Dashboards

```yaml
trade_dashboard:
  - total_closed_trades
  - net_R_budget
  - expectancy_R_budget
  - win_rate
  - loss_rate
  - scratch_rate
  - avg_win_R
  - avg_loss_R
  - profit_factor
  - payoff_ratio
  - average_holding_period_days
  - average_MFE_R_budget
  - average_MAE_R_budget
  - average_capture_ratio
  - average_giveback_R_winner
  - winners_to_losers_count

setup_dashboard:
  - setup_id
  - sample_size
  - reliability_label
  - expectancy_R_budget
  - profit_factor
  - win_rate
  - average_MFE_R_budget
  - average_capture_ratio
  - mistake_rate
  - process_adherence_rate
  - setup_status_candidate

process_dashboard:
  - percent_A_grade
  - plan_adherence_rate
  - A_grade_expectancy_R_budget
  - B_or_worse_expectancy_R_budget
  - rule_followed_expectancy_R_budget
  - rule_violated_expectancy_R_budget
  - total_mistake_cost_R
  - total_lucky_violation_R
  - top_mistake_tag_by_cost
  - review_completed_late_count
```

## 14. Reports

### 14.1 Weekly Report

For swing trading, weekly reports may have few or no closed trades, so open-position and portfolio state are mandatory.

```yaml
weekly_report:
  portfolio_summary:
    - account_equity
    - weekly_return_pct
    - benchmark_return_pct
    - current_drawdown_pct
    - portfolio_heat_pct
    - gross_exposure_pct
    - cash_pct
  open_position_summary:
    - open_position_count
    - open_unrealized_R_budget
    - total_R_budget_including_open
    - positions_with_weakening_thesis
    - largest_position_pct
  closed_trade_summary:
    - closed_trades
    - net_R_budget
    - expectancy_R_budget
    - win_rate
    - scratch_rate
  rule_triggered_outputs:
    - hard_blocks_active
    - warnings
    - review_tasks_created
    - recommendation_candidates
```

### 14.2 Monthly Report

```yaml
monthly_report:
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
    - exit_efficiency
    - deterministic_rule_triggers
    - data_quality_summary
```

## 15. Implementation Priority

```yaml
implementation_priority:
  stage_1_data_foundation:
    - Account_Equity_Snapshots
    - Cash_Flows
    - Trade_Plans
    - Fills
    - Positions_Daily_Snapshots
    - Trade_Reviews
    - Risk_Policy versioning
  stage_2_portfolio_metrics:
    - adjusted_daily_pnl
    - daily_return_pct
    - cumulative_return_pct
    - drawdown_pct
    - portfolio_heat_pct
    - exposure and concentration
  stage_3_trade_metrics:
    - realized_R_budget
    - realized_R_initial
    - realized_R_effective
    - MFE/MAE
    - capture/giveback
    - slippage
  stage_4_aggregate_metrics:
    - setup summaries
    - process summaries
    - risk summaries
  stage_5_rules_engine:
    - hard blocks
    - warnings
    - review tasks
    - recommendation candidates
  stage_6_reporting:
    - dashboards
    - weekly report
    - monthly report
  stage_7_optional_enhancements:
    - automated corporate-action adjustments beyond splits/dividends
    - Modified Dietz for intraday cash flows
    - Sharpe/Sortino after enough monthly returns
    - short-side support
```

## 16. Acceptance Criteria

```yaml
acceptance_criteria:
  data_foundation:
    - account snapshots can be stored/reconciled
    - cash flows are classified as external or trading-related
    - fills are the execution source of truth
    - every trade has a locked planned risk budget
    - open positions are snapshotted daily
  portfolio_metrics:
    - cash-flow-adjusted daily returns compute correctly
    - cumulative return is daily-linked
    - drawdowns use negative sign convention
    - heat floors locked-in profit at zero for portfolio risk
  trade_metrics:
    - realized_R_budget, realized_R_initial, realized_R_effective compute separately
    - outcome class handles scratches
    - multi-leg trades compute via FIFO or documented VWAP fallback
    - MFE/MAE precision is labeled
    - slippage uses adverse-positive convention
  process_metrics:
    - mistake_cost_R and lucky_violation_R are non-negative and never netted
    - mistake cost method/confidence are stored
  rules_engine:
    - hard blocks are deterministic
    - recommendation candidates include evidence and sample-size labels
    - no LLM inference is required for production outputs
```

## 17. Enumeration Reference

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

cash_flow_effective_timing:
  - start_of_day
  - end_of_day
  - intraday_known

direction:
  - long

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

mfe_mae_precision_level:
  - intraday_exact
  - intraday_estimated
  - daily_approximate

outcome_class:
  - win
  - loss
  - scratch

reliability_label:
  - insufficient_sample
  - provisional
  - actionable
  - high_confidence

severity:
  - info
  - warning
  - critical
  - blocking
```

## 18. Direction-Conventions Stub

This version is long-only. Short-side support is explicitly deferred.

```yaml
long_only_formulas:
  risk_per_share: "planned_entry - initial_stop"
  raw_current_at_risk_dollars: "(avg_cost - current_stop) * quantity_open"
  unrealized_pnl_dollars: "(close_price - avg_cost) * quantity_open"
  entry_adverse_slippage_R: "(vwap_entry_price - planned_entry) / risk_per_share"

future_short_support:
  status: deferred
  required_future_fields:
    - borrow_fee
    - hard_to_borrow_flag
    - short_locate_status
    - short_margin_requirement
```

## 19. Final Production Position

```yaml
production_stance:
  portfolio_first: true
  low_volume_guardrails: true
  open_positions_mandatory: true
  deterministic_rules_required: true
  inference_required: false
  risk_denominators:
    - planned_risk_budget_dollars
    - initial_executed_risk_dollars
    - max_executed_risk_dollars
  default_trade_R_for_dashboards: realized_R_budget
  corporate_actions:
    mvp: "log and flag; automate splits/dividends first"
  strategy_changes:
    automatic: false
    human_review_required: true
```

*End of alternate v1.1 specification.*
