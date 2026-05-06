---
title: "AI-Ready Swing Trading Journal Layout Research and Execution Specification"
version: "1.0"
document_type: "research_to_execution_spec"
created_for: "AI evaluation, planning, and execution"
created_date: "2026-04-30"
timezone_context: "Pacific/Honolulu"
intended_use:
  - evaluate_existing_trading_journal
  - design_new_swing_trading_journal
  - plan_spreadsheet_or_database_implementation
  - execute_pre_trade_in_trade_post_trade_review_workflows
  - generate_metrics_and_process_feedback
not_financial_advice: true
primary_design_goal: "Capture decision quality before outcome knowledge, normalize performance by initial risk, and make behavioral/process errors measurable."
---

# AI-Ready Swing Trading Journal Layout Research and Execution Specification

## 0. Operating Instruction for AI Systems

Use this document as a structured specification for designing, evaluating, or operating a swing trading journal.

The AI should prioritize the following objectives in order:

1. **Preserve pre-trade decision integrity.** Record the thesis, invalidation point, risk, planned management, and emotional state before the outcome is known.
2. **Normalize all trade outcomes in R-multiples.** Dollars alone are insufficient because position size varies.
3. **Separate process quality from outcome quality.** A profitable rule violation is still a process failure; a losing trade can still be a good decision.
4. **Measure behavioral leakage.** Mistakes should be tagged, counted, and converted into R-cost where possible.
5. **Connect every trade to a defined setup.** The system must be able to evaluate expectancy by setup, regime, sector, catalyst, entry type, and exit type.
6. **Support execution, review, and iteration.** The journal should produce daily, weekly, monthly, and quarterly decision outputs.

Recommended output style for AI using this document:

```yaml
ai_response_mode:
  when_evaluating_a_journal: "score_against_required_fields_and_quality_gates"
  when_designing_a_journal: "produce_schema_tabs_fields_formulas_and_workflows"
  when_reviewing_trades: "grade_process_separate_from_pnl"
  when_planning_improvements: "prioritize_high_R_cost_errors_and_low_expectancy_setups"
```

---

## 1. Research-Informed Design Thesis

An effective swing trading journal is not merely a trade ledger. It is a **decision-quality measurement system**.

Swing trades usually last days to weeks, so the journal must capture:

- overnight risk
- changing market regime
- changing sector conditions
- thesis decay or confirmation
- partial exits
- stop movement
- risk normalization
- psychological state
- process adherence
- post-trade pattern recognition

The journal should answer four core questions:

```text
1. Did the trader have a valid, predefined edge?
2. Was the trade sized and executed according to plan?
3. Was the trade managed according to objective evidence rather than emotion?
4. Did the result reveal an edge, a weakness, random variance, or behavioral leakage?
```

---

## 2. Evidence Map

The following research and practitioner concepts inform the journal structure.

| Source / Concept | Journal Design Implication | Implementation Requirement |
|---|---|---|
| Decision journaling / Kahneman-style decision capture | Capture beliefs, expectations, and reasoning before outcome knowledge changes memory | Mandatory `pre_trade_thesis`, `expected_scenario`, `invalidation_condition`, `premortem` |
| Gary Klein premortem | Imagine the trade failed before entry to surface hidden risks | Mandatory `premortem_failure_reasons` field |
| Van Tharp R-multiple framework | Normalize wins/losses by initial risk rather than dollars | Mandatory `initial_risk_dollars`, `realized_R`, `MFE_R`, `MAE_R` |
| Van Tharp expectancy framework | Evaluate systems as distributions of R outcomes | Dashboard must calculate `expectancy_R` and setup-level expectancy |
| Behavioral finance / CFA bias framework | Biases such as loss aversion, anchoring, confirmation bias, and overconfidence distort decisions | Mandatory emotion and mistake tags |
| Barber & Odean overtrading research | Excessive trading can reduce net returns, especially under overconfidence | Track `trade_frequency`, `revenge_trade`, `no_setup`, and `overtrading_periods` |
| Swing trading risk characteristics | Overnight holds create gap risk and regime-change risk | Mandatory `gap_risk_plan`, `event_risk`, and `overnight_hold_rationale` |
| Practitioner setup systems such as CANSLIM, Minervini, Qullamaggie, Weinstein, Darvas, Morales & Kacher | Trades must reference codeable setups, triggers, invalidation points, and management rules | Mandatory `setup_id`, `entry_trigger`, `stop_rule`, `exit_rule`, `market_regime` |

---

## 3. System Architecture

Recommended journal architecture:

```yaml
journal_architecture:
  required_tabs:
    - Setup_Playbook
    - Trade_Log
    - Dashboard
  strongly_recommended_tabs:
    - Fills
    - Daily_Management
    - Screenshots
    - Mistake_Tags
    - Review_Log
    - Rule_Change_Queue
  optional_advanced_tabs:
    - Missed_Trades
    - Watchlist_Context
    - Market_Regime_Log
    - Sector_Theme_Log
    - Backtest_Comparison
```

Minimum viable journal:

```yaml
minimum_viable_journal:
  must_have:
    - setup_id
    - entry_date
    - ticker
    - direction
    - planned_entry
    - actual_entry
    - initial_stop
    - position_size
    - initial_risk_dollars
    - thesis
    - invalidation_condition
    - planned_exit
    - actual_exit
    - exit_reason
    - realized_R
    - process_grade
    - mistake_tags
```

---

## 4. Entity Relationship Model

Use this data model when implementing in a spreadsheet, Airtable, Notion database, SQL database, or custom application.

```yaml
entities:
  Setup:
    primary_key: setup_id
    relationship: "one setup can map to many trades"
  Trade:
    primary_key: trade_id
    foreign_keys:
      - setup_id
    relationship: "one trade can have many fills and many management updates"
  Fill:
    primary_key: fill_id
    foreign_keys:
      - trade_id
    relationship: "many fills belong to one trade"
  Daily_Management_Record:
    primary_key: management_record_id
    foreign_keys:
      - trade_id
    relationship: "many management records belong to one open trade"
  Screenshot:
    primary_key: screenshot_id
    foreign_keys:
      - trade_id
      - setup_id
  Mistake_Tag:
    primary_key: mistake_tag
    relationship: "many trades can have many mistake tags"
  Review_Record:
    primary_key: review_id
    relationship: "weekly/monthly/quarterly reviews aggregate trades"
  Rule_Change_Candidate:
    primary_key: rule_change_id
    relationship: "rule changes must cite evidence from multiple trades"
```

---

# 5. Tab Specifications

## 5.1 `Setup_Playbook`

Purpose: Define each strategy/setup before trades are taken so that trades can be evaluated by repeatable rules.

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

| Field | Type | Required | Description | AI Evaluation Use |
|---|---:|---:|---|---|
| `setup_id` | string | yes | Unique identifier, e.g. `BO_HTF_01`, `PULLBACK_10EMA`, `EP_GAP_01` | Link trades to setup performance |
| `setup_name` | string | yes | Human-readable name | Reporting |
| `setup_family` | enum | yes | `breakout`, `pullback`, `episodic_pivot`, `gap`, `reversal`, `short`, `trend_continuation` | Group analysis |
| `direction_allowed` | enum | yes | `long`, `short`, `both` | Validate direction |
| `market_regime_allowed` | list | yes | Regimes where this setup is valid | Detect invalid context |
| `instrument_universe` | list | yes | Stocks, ETFs, options, futures, crypto | Validate instrument fit |
| `timeframe` | string | yes | Daily, weekly/daily, 4H/daily | Validate setup horizon |
| `liquidity_minimum` | numeric/string | yes | Minimum dollar volume or spread requirement | Risk quality |
| `volatility_requirement` | string | no | ADR%, ATR%, beta, range expansion | Setup qualification |
| `relative_strength_requirement` | string | no | RS rank, RS new high, sector leadership | Setup qualification |
| `fundamental_requirement` | string | no | Earnings/sales growth, catalyst, no requirement | Context filter |
| `technical_structure` | text | yes | Base, flag, VCP, reclaim, box, pullback | Pattern verification |
| `entry_trigger_rule` | text | yes | Objective entry condition | Validate entry |
| `initial_stop_rule` | text | yes | Objective invalidation point | Validate risk |
| `profit_taking_rule` | text | yes | Target, partial, trailing rule | Validate management |
| `time_stop_rule` | text | yes | Max hold if thesis does not progress | Validate duration |
| `add_on_rule` | text | no | Conditions for pyramiding | Validate adds |
| `disqualifiers` | list | yes | Conditions that invalidate setup | Pre-trade gate |
| `ideal_example_link` | url | no | Screenshot or annotated chart | Training data |
| `failed_example_link` | url | no | Failed setup example | Pattern improvement |
| `status` | enum | yes | `active`, `testing`, `paused`, `retired` | Prevent unsupported trades |

Recommended setup status rules:

```yaml
setup_status_rules:
  active:
    requirement: "defined rules and sufficient confidence to risk capital"
  testing:
    requirement: "paper trading, backtesting, or reduced size only"
  paused:
    requirement: "temporarily disabled due to poor regime or recent underperformance"
  retired:
    requirement: "removed after evidence of negative expectancy or poor fit"
```

---

## 5.2 `Trade_Log`

Purpose: Main trade-level table. One row per trade idea from entry to final close.

```yaml
tab: Trade_Log
row_granularity: "one row per complete trade"
primary_key: trade_id
ai_use:
  - calculate_performance
  - grade_process
  - detect_rule_violations
  - identify_high_value_improvements
```

### Required Pre-Trade Fields

| Field | Type | Required | Description | Validation Rule |
|---|---:|---:|---|---|
| `trade_id` | string | yes | Unique trade identifier | Must be unique |
| `planned_date` | date | yes | Date trade was planned | Must precede or equal entry date |
| `ticker` | string | yes | Instrument symbol | Non-empty |
| `instrument_type` | enum | yes | `stock`, `ETF`, `option`, `future`, `crypto`, `other` | Must match allowed universe |
| `direction` | enum | yes | `long` or `short` | Must match setup |
| `setup_id` | string | yes | Links to `Setup_Playbook` | Must exist in playbook |
| `market_regime` | enum | yes | Market condition at entry | Must be defined |
| `sector_theme` | string | no | Sector, industry, or theme | Useful for correlation |
| `sector_condition` | enum | no | `leading`, `improving`, `neutral`, `weakening`, `lagging` | Optional but recommended |
| `catalyst` | text | no | Earnings, guidance, news, macro, technical only | Context |
| `thesis` | text | yes | Why the trade should work | Must be specific |
| `why_now` | text | yes | Why entry is timely today | Must cite trigger/context |
| `expected_scenario` | text | yes | What should happen if right | Required for later comparison |
| `invalidation_condition` | text | yes | What proves thesis wrong | Must map to stop or exit |
| `premortem_failure_reasons` | list/text | yes | Assume failure; why did it happen? | At least one reason |
| `planned_entry` | numeric | yes | Intended entry price | Positive number |
| `initial_stop` | numeric | yes | Initial protective stop | Positive number |
| `target_1` | numeric | no | First target | Recommended |
| `target_2` | numeric | no | Second target or stretch target | Optional |
| `planned_exit_strategy` | text | yes | Stop, partials, trailing, time stop | Must be explicit |
| `planned_holding_period_days` | numeric | yes | Expected duration | Must be > 0 |
| `event_risk` | text | yes | Earnings/Fed/CPI/FDA/etc. | Use `none_known` if none |
| `gap_risk_plan` | text | yes | Overnight/event gap plan | Required for swing trades |
| `confidence_score` | numeric | no | 0–100 or 1–5 | Use consistently |
| `pre_trade_quality_score` | numeric | yes | 0–10 checklist score | See scoring section |
| `emotional_state_pre_trade` | enum/list | yes | `calm`, `FOMO`, `revenge`, `tired`, `impatient`, etc. | Behavioral tracking |
| `final_pre_trade_decision` | enum | yes | `take`, `pass`, `wait`, `reduce_size`, `paper_trade` | Must be logged before entry |

### Required Risk Fields

| Field | Type | Required | Description | Formula / Validation |
|---|---:|---:|---|---|
| `account_equity_pre_trade` | numeric | yes | Account value before trade | Positive number |
| `max_account_risk_pct` | numeric | yes | Planned risk percentage | Example: 0.25%, 0.50%, 1.00% |
| `planned_risk_dollars` | numeric | yes | Max intended loss | `account_equity_pre_trade * max_account_risk_pct` |
| `risk_per_share_or_unit` | numeric | yes | Price risk per unit | `abs(planned_entry - initial_stop)` |
| `planned_position_size` | numeric | yes | Units/shares/contracts | `planned_risk_dollars / risk_per_share_or_unit` |
| `planned_gross_exposure` | numeric | yes | Position size × entry | `planned_position_size * planned_entry` |
| `portfolio_heat_pre_trade` | numeric | yes | Total open risk before trade | Sum of open risks |
| `correlated_exposure` | text/numeric | yes | Sector/theme overlap | Required for concentration risk |
| `planned_reward_risk_ratio` | numeric | no | Target reward divided by initial risk | `(target - planned_entry) / risk_per_share` for longs |
| `position_size_override_reason` | text | no | Why size differs from formula | Required if override exists |

### Required Execution Fields

| Field | Type | Required | Description | AI Use |
|---|---:|---:|---|---|
| `actual_entry_date` | date | conditional | Actual entry date | Required if trade taken |
| `actual_entry_time` | time | no | Actual entry time | Time-of-day analysis |
| `actual_entry_price` | numeric | conditional | Average filled entry | Slippage calculation |
| `actual_position_size` | numeric | conditional | Actual size | Risk compliance |
| `entry_order_type` | enum | no | `market`, `limit`, `stop`, `stop_limit`, `other` | Execution analysis |
| `entry_trigger_followed` | boolean | yes | Did actual entry match trigger? | Process grade |
| `entry_slippage` | numeric | no | Actual vs planned | Execution quality |
| `entry_quality_grade` | enum | yes | `A`, `B`, `C`, `D`, `F` | Process analysis |
| `execution_notes` | text | no | Any fill issues | Context |

### Required Exit/Post-Trade Fields

| Field | Type | Required | Description | AI Use |
|---|---:|---:|---|---|
| `exit_date` | date | conditional | Final close date | Holding period |
| `exit_price_avg` | numeric | conditional | Average exit price | P&L |
| `exit_reason` | enum | conditional | `stop`, `target`, `trail`, `time_stop`, `thesis_invalid`, `discretionary`, `risk_reduction`, `other` | Exit analysis |
| `planned_exit_followed` | boolean | yes | Did exit match plan? | Process grade |
| `gross_pnl_dollars` | numeric | conditional | Before fees | Performance |
| `fees_commissions` | numeric | no | Costs | Net P&L |
| `net_pnl_dollars` | numeric | conditional | After costs | Performance |
| `initial_risk_dollars` | numeric | yes | Actual initial risk | Denominator for R |
| `realized_R` | numeric | conditional | Net P&L ÷ initial risk | Primary result metric |
| `MFE_R` | numeric | conditional | Max favorable excursion in R | Exit efficiency |
| `MAE_R` | numeric | conditional | Max adverse excursion in R | Stop quality |
| `capture_ratio` | numeric | conditional | Realized R ÷ MFE_R | Profit capture |
| `holding_period_days` | numeric | conditional | Exit date − entry date | Style consistency |
| `thesis_accuracy` | enum | yes | `correct`, `partially_correct`, `incorrect`, `unclear` | Forecast quality |
| `setup_validity_after_review` | enum | yes | `valid`, `invalid`, `marginal`, `lucky` | Edge quality |
| `process_grade` | enum | yes | `A`, `B`, `C`, `D`, `F` | Main behavior score |
| `mistake_tags` | list | no | Controlled vocabulary | Behavioral analytics |
| `lesson_learned` | text | yes | One clear lesson | Review quality |
| `rule_change_candidate` | boolean | yes | Should rule be reviewed? | Do not auto-change rules |
| `post_trade_screenshot_link` | url | no | Final annotated chart | Pattern library |

---

## 5.3 `Fills`

Purpose: Record partial entries, adds, trims, and exits.

```yaml
tab: Fills
row_granularity: "one row per fill"
primary_key: fill_id
foreign_key: trade_id
ai_use:
  - reconstruct_trade
  - calculate_weighted_average_entry_exit
  - analyze_partial_exit_quality
  - detect_rule_violating_adds
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `fill_id` | string | yes | Unique fill identifier |
| `trade_id` | string | yes | Links fill to trade |
| `fill_datetime` | datetime | yes | Time of fill |
| `action` | enum | yes | `entry`, `add`, `trim`, `exit`, `stop`, `cover` |
| `quantity` | numeric | yes | Units filled |
| `price` | numeric | yes | Fill price |
| `order_type` | enum | no | Market, limit, stop, stop-limit |
| `reason` | text | yes | Why fill happened |
| `rule_based` | boolean | yes | Was this fill allowed by plan? |
| `fees` | numeric | no | Commission/slippage estimate |

---

## 5.4 `Daily_Management`

Purpose: Track thesis quality and management decisions while the trade is open.

```yaml
tab: Daily_Management
row_granularity: "one row per open trade per review day or event"
primary_key: management_record_id
foreign_key: trade_id
ai_use:
  - evaluate_hold_vs_exit_decisions
  - detect thesis deterioration
  - measure stop discipline
  - identify emotional management errors
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `management_record_id` | string | yes | Unique row ID |
| `trade_id` | string | yes | Links to trade |
| `review_date` | date | yes | Review date |
| `current_price` | numeric | yes | Price at review |
| `open_R` | numeric | yes | Unrealized R |
| `current_stop` | numeric | yes | Stop at review |
| `stop_changed` | boolean | yes | Whether stop moved |
| `stop_change_reason` | text | conditional | Required if stop changed |
| `MFE_to_date_R` | numeric | yes | Best unrealized R so far |
| `MAE_to_date_R` | numeric | yes | Worst unrealized R so far |
| `volume_behavior` | enum | no | `confirming`, `neutral`, `distribution`, `fading` |
| `relative_strength_status` | enum | no | `improving`, `flat`, `weakening` |
| `market_regime_change` | boolean | yes | Did broad market context change? |
| `sector_condition_change` | boolean | yes | Did sector context change? |
| `news_or_event_update` | text | no | New catalyst or risk |
| `thesis_status` | enum | yes | `valid`, `strengthening`, `weakening`, `invalid`, `unclear` |
| `action_taken` | enum | yes | `hold`, `trim`, `add`, `exit`, `move_stop`, `no_action` |
| `action_reason` | text | yes | Must explain decision |
| `emotional_state` | enum/list | yes | Emotional condition during hold |
| `rule_violation` | boolean | yes | Was any rule violated? |
| `management_notes` | text | no | Additional context |

---

## 5.5 `Mistake_Tags`

Purpose: Create a controlled vocabulary so behavioral errors can be counted and costed.

```yaml
tab: Mistake_Tags
row_granularity: "one row per mistake type"
primary_key: mistake_tag
ai_use:
  - normalize_error_labels
  - calculate_R_cost_by_error
  - identify recurring process leaks
```

### Entry Mistakes

| Tag | Category | Definition |
|---|---|---|
| `CHASED` | entry | Entered meaningfully above planned level after risk/reward deteriorated |
| `EARLY_ENTRY` | entry | Entered before trigger confirmed |
| `LATE_ENTRY` | entry | Entered too late relative to planned pivot/trigger |
| `NO_SETUP` | entry | Trade did not match active setup playbook |
| `LOW_LIQUIDITY` | entry | Instrument had poor spread/volume relative to plan |
| `EVENT_IGNORED` | entry | Ignored known earnings/macro/news risk |

### Risk Mistakes

| Tag | Category | Definition |
|---|---|---|
| `OVERSIZED` | risk | Actual size exceeded risk plan |
| `NO_STOP` | risk | No valid initial stop or invalidation point |
| `STOP_TOO_WIDE` | risk | Stop made reward/risk unacceptable or arbitrary |
| `STOP_TOO_TIGHT` | risk | Stop was inside normal noise for setup |
| `CORRELATION_IGNORED` | risk | Too much same-sector/theme exposure |
| `GAP_RISK_IGNORED` | risk | Overnight/event gap risk not considered |

### Management Mistakes

| Tag | Category | Definition |
|---|---|---|
| `MOVED_STOP_AWAY` | management | Increased risk after entry without valid rule |
| `SOLD_TOO_EARLY` | management | Exited winner without rule-based reason |
| `HELD_AFTER_INVALIDATION` | management | Stayed in trade after thesis failed |
| `FAILED_TO_SCALE` | management | Failed to take planned partial or reduce risk |
| `ADDED_TO_LOSER` | management | Averaged down against rules |
| `MISSED_TIME_STOP` | management | Held beyond planned window without renewed thesis |

### Psychology Mistakes

| Tag | Category | Definition |
|---|---|---|
| `FOMO` | psychology | Trade driven by fear of missing out |
| `REVENGE` | psychology | Trade taken to recover recent loss |
| `BOREDOM` | psychology | Trade taken without sufficient opportunity quality |
| `EGO` | psychology | Refusal to accept invalidation |
| `ANCHORING` | psychology | Fixation on entry, prior high, target, or unrealized P&L |
| `CONFIRMATION_BIAS` | psychology | Ignored disconfirming evidence |
| `LOSS_AVERSION` | psychology | Held loser to avoid realizing loss |
| `OVERCONFIDENCE` | psychology | Increased frequency/size after wins without evidence |

Suggested mistake severity scale:

```yaml
mistake_severity:
  1: "minor documentation or execution issue; little R impact"
  2: "minor process violation; limited R impact"
  3: "material process violation; measurable R impact"
  4: "major rule violation; large or repeated R impact"
  5: "critical violation; threatens account discipline or strategy validity"
```

---

## 5.6 `Review_Log`

Purpose: Convert trade data into improvement decisions.

```yaml
tab: Review_Log
row_granularity: "one row per daily, weekly, monthly, or quarterly review"
primary_key: review_id
ai_use:
  - summarize performance
  - detect recurring behavior patterns
  - recommend process improvements
  - prevent overfitting from small sample sizes
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `review_id` | string | yes | Unique review identifier |
| `review_type` | enum | yes | `daily`, `weekly`, `monthly`, `quarterly` |
| `period_start` | date | yes | Start of review period |
| `period_end` | date | yes | End of review period |
| `number_of_trades` | numeric | yes | Closed trades reviewed |
| `net_R` | numeric | yes | Sum of realized R |
| `expectancy_R` | numeric | yes | Average R per trade |
| `win_rate` | numeric | yes | % profitable trades |
| `avg_win_R` | numeric | yes | Average winning trade in R |
| `avg_loss_R` | numeric | yes | Average losing trade in R |
| `profit_factor` | numeric | yes | Gross wins ÷ gross losses |
| `max_drawdown_R` | numeric | yes | Largest peak-to-trough R drawdown |
| `best_trade_R` | numeric | yes | Best trade |
| `worst_trade_R` | numeric | yes | Worst trade |
| `top_performing_setup` | string | no | Best setup by expectancy/sample |
| `worst_performing_setup` | string | no | Weakest setup by expectancy/sample |
| `highest_cost_mistake` | string | no | Mistake with largest R leakage |
| `primary_lesson` | text | yes | Main takeaway |
| `next_period_focus` | text | yes | Specific execution focus |
| `rule_change_candidates` | list | no | Candidate changes requiring more evidence |

---

## 5.7 `Rule_Change_Queue`

Purpose: Prevent impulsive rule changes after one trade.

```yaml
tab: Rule_Change_Queue
row_granularity: "one row per proposed rule change"
primary_key: rule_change_id
ai_use:
  - prevent overfitting
  - require evidence threshold
  - document system evolution
```

| Field | Type | Required | Description |
|---|---:|---:|---|
| `rule_change_id` | string | yes | Unique ID |
| `date_proposed` | date | yes | Date candidate was created |
| `affected_setup_id` | string | no | Setup affected |
| `current_rule` | text | yes | Existing rule |
| `proposed_rule` | text | yes | Proposed change |
| `reason` | text | yes | Why change is being considered |
| `supporting_trade_ids` | list | yes | Evidence set |
| `sample_size` | numeric | yes | Number of trades supporting change |
| `estimated_R_impact` | numeric | no | Historical R improvement estimate |
| `overfitting_risk` | enum | yes | `low`, `medium`, `high` |
| `decision` | enum | yes | `monitor`, `test`, `accept`, `reject`, `defer` |
| `review_date` | date | yes | When to revisit |

Recommended evidence threshold:

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

# 6. Core Formulas

Use the following formulas consistently.

```text
initial_risk_per_share = abs(planned_entry - initial_stop)
```

```text
planned_risk_dollars = account_equity_pre_trade * max_account_risk_pct
```

```text
planned_position_size = planned_risk_dollars / initial_risk_per_share
```

```text
actual_initial_risk_dollars = abs(actual_entry_price - initial_stop) * actual_position_size
```

```text
net_pnl_dollars = gross_pnl_dollars - fees_commissions
```

```text
realized_R = net_pnl_dollars / actual_initial_risk_dollars
```

```text
MFE_R = maximum_favorable_excursion_dollars / actual_initial_risk_dollars
```

```text
MAE_R = maximum_adverse_excursion_dollars / actual_initial_risk_dollars
```

```text
capture_ratio = realized_R / MFE_R
```

```text
expectancy_R = average(realized_R)
```

```text
profit_factor = sum(winning_trade_R) / abs(sum(losing_trade_R))
```

```text
avg_win_R = average(realized_R where realized_R > 0)
```

```text
avg_loss_R = average(realized_R where realized_R < 0)
```

```text
win_rate = count(realized_R > 0) / count(all_closed_trades)
```

```text
loss_rate = 1 - win_rate
```

```text
expectancy_decomposed = (win_rate * avg_win_R) + (loss_rate * avg_loss_R)
```

```text
mistake_cost_R = realized_R_if_plan_followed - actual_realized_R
```

If `realized_R_if_plan_followed` is not objectively measurable, classify mistake cost as estimated and mark confidence.

```yaml
mistake_cost_confidence:
  high: "planned stop/target rule provides objective alternative"
  medium: "reasonable reconstruction from chart and plan"
  low: "subjective estimate; use only for qualitative review"
```

---

# 7. Scoring Models

## 7.1 Pre-Trade Quality Score

Score each planned trade from 0 to 10 before entry.

| Component | Points | Description |
|---|---:|---|
| Valid setup from active playbook | 2 | Setup exists and status is active/testing as appropriate |
| Market regime supportive | 1 | Broad market supports setup direction |
| Sector/theme supportive | 1 | Sector is leading or improving |
| Clear catalyst or technical reason | 1 | Trade has specific reason, not vague hope |
| Precise entry trigger | 1 | Trigger is observable and objective |
| Valid initial stop | 1 | Stop maps to thesis invalidation |
| Acceptable reward/risk | 1 | Expected payoff justifies risk |
| Correct position size | 1 | Size follows risk formula |
| Emotional state acceptable | 1 | No FOMO, revenge, exhaustion, or urgency override |

Decision rule:

```yaml
pre_trade_score_policy:
  score_8_to_10:
    action: "full planned risk allowed"
  score_6_to_7:
    action: "reduce size, wait for confirmation, or paper trade"
  score_0_to_5:
    action: "do not take trade"
```

## 7.2 Process Grade

Grade process separately from outcome.

| Grade | Definition | Example |
|---|---|---|
| `A` | Followed plan fully; decision quality high regardless of outcome | Valid setup, correct size, clean execution, rule-based exit |
| `B` | Minor deviation with little impact | Slight slippage or minor documentation gap |
| `C` | Several deviations; review required | Early entry, partial plan ambiguity, mild emotional influence |
| `D` | Major rule break | Oversized, chased, moved stop away, ignored invalidation |
| `F` | Impulsive or uncontrolled trade | No setup, revenge trade, no stop, severe risk violation |

AI process classification:

```yaml
process_outcome_matrix:
  followed_plan_and_won: "disciplined_win"
  followed_plan_and_lost: "disciplined_loss"
  violated_plan_and_won: "lucky_violation"
  violated_plan_and_lost: "execution_loss"
```

The AI should flag `lucky_violation` as dangerous because it positively reinforces bad process.

---

# 8. AI Evaluation Rules

## 8.1 Pre-Trade Gate

Before accepting a trade as journal-ready, the AI should verify:

```yaml
pre_trade_gate:
  required_checks:
    - setup_id_exists
    - setup_status_allows_trade
    - direction_matches_setup
    - market_regime_allowed_or_exception_explained
    - thesis_is_specific
    - why_now_is_specific
    - invalidation_condition_exists
    - planned_entry_exists
    - initial_stop_exists
    - risk_per_share_positive
    - planned_position_size_calculated
    - account_risk_within_limit
    - gap_risk_plan_exists
    - event_risk_checked
    - premortem_completed
    - emotional_state_logged
  fail_action: "mark trade incomplete; do not classify as A-grade process"
```

## 8.2 In-Trade Gate

For every open trade review, the AI should ask:

```yaml
in_trade_gate:
  questions:
    - "Is the original thesis still valid?"
    - "Has price action confirmed, weakened, or invalidated the thesis?"
    - "Has the market or sector regime changed?"
    - "Is the stop still logical based on the original plan?"
    - "Was any stop movement rule-based?"
    - "Is the trader reacting to evidence or emotion?"
    - "Has MFE become large enough that risk should be reduced under the plan?"
    - "Has the time stop been reached?"
```

## 8.3 Post-Trade Gate

After closing a trade, the AI should classify:

```yaml
post_trade_gate:
  classifications:
    - setup_validity_after_review
    - thesis_accuracy
    - execution_quality
    - management_quality
    - emotional_discipline
    - process_outcome_matrix_class
    - primary_mistake_if_any
    - repeatable_lesson
```

The AI should not recommend a rule change after one trade unless the trade exposed a critical operational risk.

---

# 9. Dashboard Requirements

The dashboard must calculate metrics at the total portfolio level and by segmented cohorts.

## 9.1 Required Portfolio Metrics

```yaml
dashboard_metrics:
  core:
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
    - percent_trades_following_plan
    - mistake_count
    - mistake_cost_R
```

## 9.2 Required Breakdowns

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
  by_market_regime:
    - net_R
    - expectancy_R
    - drawdown_R
  by_direction:
    - long
    - short
  by_sector_theme:
    - net_R
    - concentration_risk
  by_entry_type:
    - breakout
    - pullback
    - reclaim
    - gap
    - opening_range
  by_exit_reason:
    - stop
    - target
    - trailing_stop
    - time_stop
    - discretionary
  by_trade_quality_score:
    - score_8_to_10
    - score_6_to_7
    - score_0_to_5
  by_emotional_state:
    - calm
    - FOMO
    - revenge
    - tired
    - impatient
```

## 9.3 Dashboard Interpretation Rules

```yaml
interpretation_rules:
  positive_edge_candidate:
    condition: "expectancy_R > 0 with sufficient sample size and acceptable drawdown"
  process_leak_candidate:
    condition: "profitable setup but low percent_trades_following_plan"
  setup_retirement_candidate:
    condition: "negative expectancy_R across sufficient sample size with no regime-specific explanation"
  emotional_leak_candidate:
    condition: "specific emotional state has materially worse expectancy or higher mistake cost"
  exit_problem_candidate:
    condition: "high average_MFE_R but low average_capture_ratio"
  stop_problem_candidate:
    condition: "large average_MAE_R or frequent stop-outs before setup works"
```

---

# 10. Review Cadence

## 10.1 Daily Review

```yaml
daily_review:
  time_required: "5-10 minutes"
  required_actions:
    - update_open_trade_prices
    - update_current_stops
    - classify_thesis_status
    - log_market_and_sector_changes
    - record_any_management_action
    - record_emotional_state
    - check_for_rule_violations
  output:
    - open_trade_action_list
    - risk_exposure_summary
    - process_alerts
```

## 10.2 Weekly Review

```yaml
weekly_review:
  time_required: "30-60 minutes"
  required_actions:
    - review_closed_trades
    - calculate_net_R
    - calculate_expectancy_R
    - review_best_and_worst_trades
    - identify_top_mistake_tags
    - review_missed_trades
    - update_screenshot_library
    - define_next_week_execution_focus
  output:
    - weekly_scorecard
    - top_3_lessons
    - top_1_behavioral_focus
```

## 10.3 Monthly Review

```yaml
monthly_review:
  time_required: "60-120 minutes"
  required_actions:
    - evaluate_expectancy_by_setup
    - evaluate_expectancy_by_market_regime
    - compare_A_trades_vs_B_C_trades
    - review_drawdown_and_losing_streaks
    - quantify_mistake_cost_R
    - review_rule_change_candidates
  output:
    - setup_keep_pause_retire_recommendations
    - risk_sizing_recommendation
    - process_improvement_plan
```

## 10.4 Quarterly Review

```yaml
quarterly_review:
  required_actions:
    - evaluate_strategy_fit
    - decide_active_testing_paused_retired_setups
    - review_position_sizing_rules
    - review data quality and journaling compliance
    - compare live results against backtest or expectations if available
  output:
    - quarterly_strategy_memo
    - setup_playbook_update
    - next_quarter_constraints
```

---

# 11. AI Execution Workflows

## 11.1 Workflow: Create a New Journal

```yaml
workflow_create_new_journal:
  steps:
    - create_tabs:
        - Setup_Playbook
        - Trade_Log
        - Fills
        - Daily_Management
        - Mistake_Tags
        - Review_Log
        - Dashboard
        - Rule_Change_Queue
    - populate_mistake_tags
    - define_market_regime_enum
    - define_setup_ids
    - add_formula_columns
    - add_validation_rules
    - create_dashboard_pivots
    - test_with_sample_trade
  acceptance_criteria:
    - every_trade_can_compute_realized_R
    - every_trade_links_to_setup_id
    - every_closed_trade_has_process_grade
    - dashboard_can_segment_by_setup_and_regime
```

## 11.2 Workflow: Evaluate a Proposed Trade

```yaml
workflow_evaluate_proposed_trade:
  input_required:
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
    - event_risk
    - emotional_state
  steps:
    - verify_setup_exists
    - verify_setup_active_or_testing
    - calculate_risk_per_share
    - calculate_position_size
    - compute_pre_trade_quality_score
    - run_premortem_check
    - classify_trade_decision
  output:
    - approve_reduce_wait_or_reject
    - position_size
    - missing_fields
    - process_risks
```

## 11.3 Workflow: Review an Open Trade

```yaml
workflow_review_open_trade:
  input_required:
    - trade_id
    - current_price
    - current_stop
    - market_regime
    - sector_condition
    - thesis_status
    - emotional_state
  steps:
    - calculate_open_R
    - update_MFE_R_and_MAE_R
    - compare_current_action_to_plan
    - detect_stop_rule_violation
    - check_time_stop
    - classify_hold_trim_add_exit
  output:
    - recommended_journal_action
    - rule_violation_flags
    - updated_management_record
```

## 11.4 Workflow: Review a Closed Trade

```yaml
workflow_review_closed_trade:
  input_required:
    - trade_id
    - fills
    - exit_reason
    - final_chart
    - notes
  steps:
    - calculate_net_pnl
    - calculate_realized_R
    - calculate_MFE_R
    - calculate_MAE_R
    - calculate_capture_ratio
    - classify_process_outcome_matrix
    - assign_process_grade
    - assign_mistake_tags
    - generate_lesson
  output:
    - completed_trade_log_row
    - trade_review_summary
    - possible_rule_change_candidate
```

## 11.5 Workflow: Weekly Performance Review

```yaml
workflow_weekly_review:
  steps:
    - filter_closed_trades_for_week
    - calculate_weekly_metrics
    - rank_mistakes_by_R_cost
    - rank_setups_by_expectancy
    - identify_lucky_violations
    - identify_disciplined_losses
    - generate_next_week_focus
  output:
    - weekly_review_record
    - behavioral_priority
    - setup_priority
    - risk_adjustment_if_needed
```

---

# 12. AI Evaluation Rubric for an Existing Journal

Use this rubric to score an existing swing trading journal from 0 to 100.

| Category | Weight | Criteria |
|---|---:|---|
| Pre-trade decision capture | 20 | Thesis, why now, invalidation, premortem, planned exit, emotional state |
| Risk normalization | 20 | Initial risk, position sizing, R-multiple, MFE_R, MAE_R |
| Setup linkage | 15 | Setup IDs, playbook rules, setup-level performance |
| Execution tracking | 10 | Planned vs actual entry, slippage, order type, trigger compliance |
| In-trade management | 10 | Daily thesis status, stop changes, market/sector updates |
| Post-trade review | 10 | Process grade, lesson, mistake tags, thesis accuracy |
| Analytics dashboard | 10 | Expectancy, win/loss stats, segmentation, mistake cost |
| Review cadence | 5 | Daily/weekly/monthly/quarterly review records |

Score interpretation:

```yaml
journal_score_interpretation:
  90_to_100: "institutional-quality personal process system"
  75_to_89: "strong journal with minor gaps"
  60_to_74: "functional trade log but weak feedback loop"
  40_to_59: "basic recordkeeping; insufficient for performance improvement"
  below_40: "not yet a decision-quality journal"
```

---

# 13. Quality Gates and Failure Modes

## 13.1 Mandatory Quality Gates

A trade should not receive an `A` process grade unless all are true:

```yaml
A_grade_requirements:
  - setup_id_valid
  - pre_trade_plan_completed_before_entry
  - risk_sizing_followed
  - initial_stop_defined
  - entry_trigger_followed
  - no_major_rule_violation
  - exit_or_management_action_rule_based
  - post_trade_review_completed
```

## 13.2 Common Journal Failure Modes

| Failure Mode | Symptom | Fix |
|---|---|---|
| Outcome-only journaling | Notes focus only on profit/loss | Add process grade and pre-trade plan |
| Hindsight rewrite | Thesis written after exit | Timestamp pre-trade ticket |
| Dollar-based evaluation | Large trades dominate results | Convert all outcomes to R |
| Undefined setups | Every trade is unique | Add setup playbook and setup IDs |
| Mistake ambiguity | Same error labeled many ways | Use controlled mistake tags |
| No management record | Cannot explain why exits happened | Add daily management tab |
| Overfitting | Rules change after each loss | Use rule change queue and sample thresholds |
| Emotional blind spot | Repeated impulsive trades | Mandatory emotional state and mistake tags |
| No regime context | Strategy judged without market conditions | Track market regime and sector condition |

---

# 14. Recommended Implementation Order

```yaml
implementation_order:
  phase_1_foundation:
    - define_setup_playbook
    - create_trade_log
    - add_R_multiple_formulas
    - create_mistake_tag_vocabulary
  phase_2_execution_quality:
    - add_fills_tab
    - add_daily_management_tab
    - add_process_grade
    - add_pre_trade_quality_score
  phase_3_analytics:
    - create_dashboard
    - segment_by_setup
    - segment_by_market_regime
    - track_mistake_cost_R
  phase_4_feedback_loop:
    - add_review_log
    - add_rule_change_queue
    - implement_weekly_monthly_quarterly_reviews
  phase_5_advanced:
    - add_missed_trades
    - add_watchlist_context
    - compare_live_trades_to_backtest_or_model_signals
```

---

# 15. Example AI Prompts for Operating the Journal

## 15.1 Pre-Trade Evaluation Prompt

```text
Evaluate this proposed swing trade using the journal specification. Verify setup validity, risk sizing, thesis clarity, invalidation condition, market regime fit, event risk, emotional state, and pre-trade quality score. Return: approve/reduce/wait/reject, missing fields, position size, and process risks.
```

## 15.2 Post-Trade Review Prompt

```text
Review this closed trade using the journal specification. Calculate realized R, MFE_R, MAE_R, capture ratio, classify the process-outcome matrix, assign process grade, identify mistake tags, and produce one repeatable lesson. Do not recommend a rule change unless evidence exceeds the rule-change threshold.
```

## 15.3 Weekly Review Prompt

```text
Perform a weekly review of the journal. Calculate net R, expectancy, win rate, avg win R, avg loss R, profit factor, mistake cost by tag, expectancy by setup, and process adherence. Identify the top behavioral leak and the highest-value improvement for next week.
```

## 15.4 Journal Audit Prompt

```text
Audit my current swing trading journal against the 100-point rubric. Identify missing fields, weak feedback loops, formula gaps, and implementation priorities. Produce a phased plan to upgrade the journal without adding unnecessary complexity.
```

---

# 16. Final Recommended Mandatory Fields

If forced to reduce the system to the smallest useful version, make these fields mandatory:

```yaml
mandatory_fields_minimal:
  identity:
    - trade_id
    - ticker
    - direction
    - setup_id
  context:
    - market_regime
    - sector_condition
    - catalyst
  pre_trade_decision:
    - thesis
    - why_now
    - invalidation_condition
    - premortem_failure_reasons
    - emotional_state_pre_trade
  risk:
    - planned_entry
    - initial_stop
    - account_equity_pre_trade
    - max_account_risk_pct
    - planned_risk_dollars
    - risk_per_share_or_unit
    - planned_position_size
  execution:
    - actual_entry_price
    - actual_position_size
    - entry_trigger_followed
  outcome:
    - exit_price_avg
    - exit_reason
    - net_pnl_dollars
    - realized_R
    - MFE_R
    - MAE_R
    - capture_ratio
  review:
    - thesis_accuracy
    - process_grade
    - mistake_tags
    - lesson_learned
```

Final design principle:

```text
The journal is successful if it can show whether profits and losses came from repeatable edge, disciplined execution, favorable variance, or avoidable behavioral leakage.
```

---

# 17. Reference List

This specification is based on the research themes and practitioner frameworks summarized below.

- Decision journaling and pre-outcome belief capture: Alliance for Decision Education, decision journal resources.
- Premortem analysis: Gary Klein, premortem decision method.
- R-multiples and expectancy: Van Tharp Institute, system quality and position sizing concepts.
- Behavioral bias mitigation: CFA Institute behavioral finance materials.
- Overconfidence and trading frequency: Barber and Odean, *Trading Is Hazardous to Your Wealth*, Quarterly Journal of Economics.
- Swing trading risk characteristics: Schwab, Fidelity, and Britannica educational materials on swing trading.
- Practitioner momentum/swing frameworks: William O'Neil CANSLIM, Mark Minervini, Qullamaggie, Stan Weinstein, Nicolas Darvas, Morales & Kacher, Andreas Clenow, Gray & Vogel.

