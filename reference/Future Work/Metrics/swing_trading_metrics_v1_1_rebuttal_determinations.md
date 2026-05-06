---
title: "Swing Trading Performance Metrics v1.1 — Findings Rebuttal and Determinations"
version: "determinations-1.0"
document_type: "review_rebuttal_and_traceability"
source_documents:
  - "swing_trading_metrics_v1_1_findings.md"
  - "swing_trading_performance_metrics_v1_1.md"
created_date: "2026-05-05"
created_for:
  - AI orchestrator review
  - Python swing trading tool implementation planning
  - deterministic metrics/rules engine design
purpose: "Confirm, contest, or modify each finding from the v1.0 → v1.1 findings document, and record the authorial determinations used to produce an alternate v1.1 specification."
production_assumption: "Swing trading, stock-focused, long-only default, fewer than 10 concurrent open positions, holding periods measured in days to weeks, deterministic metrics and rule triggers preferred over inference."
not_financial_advice: true
---

# Swing Trading Performance Metrics v1.1 — Findings Rebuttal and Determinations

## 0. Executive Determination

The findings document is broadly strong. Most findings identify real implementation risks: undefined formulas, cash-flow ambiguity, missing edge-case behavior, missing audit/versioning semantics, and metric reliability issues that would matter in a production swing-trading tool.

The proposed v1.1 specification is also directionally correct: it is portfolio-first, deterministic, low-volume-aware, and explicit that LLM inference should not be required in the production path.

However, I would not accept the v1.1 file completely as written. I would produce an alternate v1.1 with the following changes:

```yaml
major_determinations:
  accept_most_findings: true
  core_changes_to_supplied_v1_1:
    - "Use dual/triple risk denominators instead of a single ambiguous initial_risk_dollars convention."
    - "Replace entry_slippage_R sign convention with an adverse-slippage convention where positive means worse execution."
    - "Keep long-only scope in v1.1; do not add full short-side formula support until shorting is in scope."
    - "Treat corporate actions as required-to-log, but allow manual reconciliation for MVP rather than requiring full automated adjustment immediately."
    - "Replace the proposed mistake_cost_R formula with plan-counterfactual math that handles both losses and opportunity-cost errors."
    - "Avoid duplicate cash-flow truth by making Cash_Flows canonical and Account_Equity_Snapshots derived/imported broker facts."
```

## 1. Determination Legend

```yaml
determination_values:
  confirm: "Finding is correct and its proposed resolution is acceptable."
  confirm_with_modification: "Finding is correct, but the proposed v1.1 resolution should be adjusted."
  contest: "Finding identifies a real concern, but the proposed resolution or severity/scope is not accepted."
  defer: "Finding is valid but should be treated as future enhancement rather than v1.1 core."
```

## 2. Finding-by-Finding Determinations

| ID | Determination | Rationale | Alternate v1.1 Action |
|---|---|---|---|
| F-001 | confirm | `adjusted_equity` is undefined and unreliable with multiple cash flows at different equity levels. | Use daily-linked return: `product(1 + daily_return_pct) - 1`. |
| F-002 | confirm_with_modification | TWR cash-flow timing must be explicit. Start-of-day is acceptable for MVP but should not be the only representable model. | Add `cash_flow_effective_timing` and permit `start_of_day`, `end_of_day`, or `intraday_known`; default to start-of-day. Add optional Modified Dietz field for future use. |
| F-003 | confirm | Profit factor division by zero should not return infinity. | Return null plus reliability flag. |
| F-004 | confirm | Recovery factor and return/max-drawdown are undefined with zero drawdown. | Return null plus explanatory flag. |
| F-005 | confirm | Breakeven win rate needs both wins and losses. | Require at least one win and one loss; otherwise null. |
| F-006 | confirm | Capture ratio should remain a winner-only metric, while winners-to-losers need separate diagnostics. | Winner-only capture ratio; separate `winner_to_loser_flag`. |
| F-007 | confirm | Unbounded giveback on losers conflates surrendered profit with realized loss magnitude. | Split winner giveback and winner-to-loser giveback. |
| F-008 | confirm | First-day daily return must be defined. | Set day-one return to 0 when prior equity does not exist. |
| F-009 | confirm | Drawdown sign convention must be explicit for rule thresholds. | Drawdowns always <= 0; thresholds expressed as negative values. |
| F-010 | confirm | Scratch trades break decomposed expectancy if ignored. | Add scratch rate and average scratch R. |
| F-011 | confirm | Current-at-risk must be anchored to cost/entry, not current price, to support heat flooring and locked-in profit. | Explicit formulas for raw risk, heat contribution, and locked-in profit. |
| F-012 | contest | The finding is correct that slippage needed a formula, but the proposed sign convention is backwards for many operators: negative=worse is unintuitive for risk dashboards. | Use `entry_adverse_slippage_R = (vwap_entry_price - planned_entry) / risk_per_share` for longs, where positive=worse. Optional signed `entry_price_improvement_R` can be derived as the inverse. |
| F-013 | confirm | Pre-trade lock scope must be explicit. | Lock defined plan/risk/thesis/context fields at first fill. |
| F-014 | confirm | Scratch trades need explicit classification. | Use configurable `scratch_epsilon`, default 0.10R. |
| F-015 | confirm_with_modification | Scale-ins do make risk anchoring ambiguous. But using only planned risk as `initial_risk_dollars` hides actual risk deployed and distorts partial-fill or unused-scale-in trades. | Replace single denominator with `planned_risk_budget_dollars`, `initial_executed_risk_dollars`, and `max_executed_risk_dollars`; compute planned, initial, and effective R. |
| F-016 | contest | If v1.1 scope is explicitly long-only, full short-side support is not required. Adding short variants now increases maintenance burden without production need. | Keep long-only formulas in v1.1; include a direction-conventions stub for future short support. |
| F-017 | confirm | Fills support multi-leg actions, so metrics must handle partials/adds/exits. | Add VWAP/FIFO multi-leg math and open/closed split. |
| F-018 | confirm | Realized R must be net of fees. | Define gross and net R separately; dashboards default to net. |
| F-019 | confirm_with_modification | Corporate actions matter, but full automated handling is heavy for MVP. | Require corporate-action logging and manual reconciliation flag; automate splits/dividends first, defer complex spinoffs/mergers. |
| F-020 | confirm | MWR/IRR mention is dangling and not needed for low-volume swing MVP. | Remove from default v1.1; future enhancement only. |
| F-021 | confirm | Risk policy versioning is necessary for historical auditability. | Add version/effective dates and trade-level policy snapshot. |
| F-022 | confirm | Setup status affects metrics and must have an audit trail. | Add `Setup_Status_History`. |
| F-023 | confirm_with_modification | Currency fields are not needed in the default USD-only MVP but are harmless if nullable. | State USD-only assumption; nullable FX fields are optional. |
| F-024 | confirm | Trading-day and timezone semantics affect daily snapshots. | Use NYSE trading day, UTC storage, local display only. |
| F-025 | confirm | Open MFE/MAE is required because swing trades remain open for days/weeks. | Define open MFE/MAE using the same precision hierarchy as closed trades. |
| F-026 | confirm_with_modification | Mistake cost is subjective and needs method/confidence, but the proposed formula using `abs()` is not robust. It fails for opportunity-cost mistakes such as sold-too-early winners. | Use `mistake_cost_R = max(0, plan_followed_R - actual_realized_R)` and `lucky_violation_R = max(0, actual_realized_R - plan_followed_R)`, with method/confidence fields. |
| F-027 | confirm | Cumulative R and dollar P&L answer different questions. | Add interpretive guardrail wherever both appear. |
| F-028 | confirm | Sharpe/Sortino are not default metrics for low-frequency swing trading. | Optional, reliability-labeled after enough monthly returns. |
| F-029 | confirm | Terminology should distinguish position-level and portfolio-level unrealized R. | Standardize `unrealized_R` vs `open_unrealized_R`. |
| F-030 | confirm | Enums should be centralized. | Add enumeration reference. |
| F-031 | confirm | Dividends/interest should not be treated as external deposits. | Mark `external_to_trading=false` and include in trading return. |
| F-032 | confirm | Missing review needs a deterministic definition. | Define by `review_lag_threshold_days`. |
| F-033 | confirm | Manual regime classification can create hindsight bias. | Lock trade-entry regime and timestamp daily regime classifications. |
| F-034 | confirm | Late reviews degrade reliability. | Add overdue and late-review rules. |
| F-035 | confirm | Version should be bumped. | Use `standalone-1.1-alt`. |
| F-036 | confirm | Cleaner filename is preferable but not substantive. | Use `swing_trading_performance_metrics_v1_1_alternate.md`. |
| F-037 | confirm | Early negative signal should exist symmetrically with early positive signal. | Add early-negative informational review rule. |

## 3. Cross-Cutting Rebuttal Themes

### 3.1 Risk Denominator Requires More Than One Field

The supplied v1.1 collapses too much into `initial_risk_dollars`. Swing trading with scale-ins, partial fills, and planned pyramiding needs at least three related but distinct quantities:

```yaml
risk_denominator_model:
  planned_risk_budget_dollars:
    meaning: "maximum intended risk for the full planned trade before first fill"
    use: "portfolio planning, rule compliance, default setup expectancy"
  initial_executed_risk_dollars:
    meaning: "risk actually deployed by the first opening tranche at initial stop"
    use: "entry/tranche efficiency"
  max_executed_risk_dollars:
    meaning: "maximum risk actually deployed at any point during the trade"
    use: "effective risk and pyramiding evaluation"
```

The alternate v1.1 computes all three and reports:

```yaml
R_outputs:
  realized_R_budget: "net_pnl / planned_risk_budget_dollars"
  realized_R_initial: "net_pnl / initial_executed_risk_dollars"
  realized_R_effective: "net_pnl / max_executed_risk_dollars"
```

### 3.2 Slippage Should Be Adverse-Positive

The supplied findings propose a sign convention where negative means worse execution. For production dashboards and alert thresholds, adverse-positive is clearer:

```yaml
entry_adverse_slippage_R:
  long_formula: "(vwap_entry_price - planned_entry) / risk_per_share"
  interpretation: "positive = worse than planned; negative = better than planned"
```

### 3.3 Long-Only Scope Should Stay Long-Only

The findings document rates missing short-side formulas as High, but the v1.1 spec explicitly scopes production to long-only stocks. The alternate v1.1 keeps the implementation focused and adds a short-side extension stub rather than full formulas.

### 3.4 Mistake Cost Must Compare Actual to Plan-Counterfactual

The alternate v1.1 rejects `abs(realized_R) - hypothetical_R_if_plan_followed` as the general formula. The robust approach is:

```yaml
mistake_cost_model:
  mistake_cost_R: "max(0, plan_followed_R - actual_realized_R)"
  lucky_violation_R: "max(0, actual_realized_R - plan_followed_R)"
  note: "The two metrics are never netted."
```

This handles both harmful losses and opportunity-cost errors such as selling too early.

### 3.5 Corporate Actions Should Be Logged in MVP, Not Fully Automated on Day One

For a low-volume swing trading system, corporate action events are rare but disruptive. The alternate v1.1 requires logging and flags affected trades for reconciliation. Automated split/dividend handling is included; spinoffs and mergers are flagged for manual handling.

## 4. Final Determination

```yaml
final_determination:
  findings_document_quality: "high"
  supplied_v1_1_quality: "strong but should be modified before production"
  alternate_v1_1_needed: true
  production_baseline_recommendation: "Use alternate v1.1 generated from this rebuttal, not the supplied v1.1 verbatim."
```

*End of rebuttal determinations document.*
