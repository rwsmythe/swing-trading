---
title: "Swing Trading Performance Metrics — v1.0 → v1.1 Findings"
version: "findings-1.0"
document_type: "review_findings_driving_v1_1_changes"
source_document: "swing_trading_performance_metrics_standalone_ai_ingestion.md (standalone-1.0)"
created_date: "2026-05-05"
purpose: "Capture every issue identified in v1.0 that will drive v1.1 changes, with location, severity, and proposed resolution. This document is the audit trail for v1.1; the v1.1 spec itself will be generated separately."
---

# Swing Trading Performance Metrics — v1.0 → v1.1 Findings

## 0. How This Document Is Structured

Each finding has a stable ID (`F-NNN`), a section reference into v1.0, a severity, and a proposed v1.1 resolution. Severities:

- **Critical** — foundational; downstream metrics are wrong or undefined without it.
- **High** — meaningful semantic gap or undefined behavior that an implementer must invent.
- **Medium** — edge case, inconsistency, or process gap that will bite eventually.
- **Low** — minor ambiguity, optional enhancement, or scope-dependent.
- **Editorial** — naming, versioning, formatting, or housekeeping.

Findings are grouped by category. The v1.1 spec resolves all findings tagged Critical and High; Medium findings are resolved unless explicitly deferred; Low and Editorial are addressed where they don't expand scope.

---

## 1. Mathematical / Formula Errors and Edge Cases

### F-001 — Cumulative return formula references undefined "adjusted_equity"

- **Source:** §5.5
- **Severity:** High
- **Issue:** The formula `cumulative_return_pct = current_adjusted_equity / starting_adjusted_equity - 1` uses the term `adjusted_equity`, which is never defined. Even with a sensible interpretation (subtract net cash flows from current equity), it produces incorrect results when multiple cash flows occur at different equity levels.
- **Resolution (v1.1):** Replace with `cumulative_return_pct = product(1 + daily_return_pct) - 1` — a direct extension of the time-weighted return defined in §5.4. Remove `adjusted_equity` terminology entirely.

### F-002 — Time-weighted return cash-flow timing unspecified

- **Source:** §5.4
- **Severity:** High
- **Issue:** The formula `time_weighted_return = product(1 + daily_return_pct) - 1` linked through `daily_return_pct = adjusted_daily_pnl / start_equity` is only correct under a specific assumption about when external cash flows post within the day. v1.0 does not state the assumption.
- **Resolution (v1.1):** Define the convention explicitly: external cash flows are treated as occurring at the **start of day**. `start_equity` for day `D` is the prior end-of-day equity **plus** day-`D` external cash flow. This makes `adjusted_daily_pnl = end_equity - start_equity` (with start_equity already cash-flow-adjusted) and avoids double-counting. Add an optional Modified Dietz alternative for users with intra-day cash flow timing data.

### F-003 — Profit factor undefined when no losing trades exist

- **Source:** §6.5
- **Severity:** Medium
- **Issue:** Denominator `abs(sum(realized_R where realized_R < 0))` is zero when no losing trades exist in the window, producing division by zero.
- **Resolution (v1.1):** Return `null` with reliability flag `no_losing_trades_in_window`. Display as "—" in dashboards. Never return `+inf`. Same treatment for the inverse case (no winners) where applicable.

### F-004 — Recovery factor undefined when max_drawdown is zero

- **Source:** §11.1
- **Severity:** Medium
- **Issue:** `recovery_factor = net_profit / abs(max_drawdown_dollars)` divides by zero when no drawdown has occurred. `R_recovery_factor` has the same issue.
- **Resolution (v1.1):** Return `null` and display as "—" with note "no drawdown recorded yet." `return_over_max_drawdown` (§11.2) gets the same treatment.

### F-005 — Breakeven win rate undefined for empty / scratch-only samples

- **Source:** §6.7
- **Severity:** Low
- **Issue:** `breakeven_win_rate = abs(avg_loss_R) / (avg_win_R + abs(avg_loss_R))` is undefined when both `avg_win_R` and `avg_loss_R` are zero (e.g., scratch-only window).
- **Resolution (v1.1):** Require sample to contain ≥1 winner AND ≥1 loser. Otherwise return `null` with reliability flag `insufficient_outcome_diversity`.

### F-006 — Capture ratio validity gap

- **Source:** §8.3
- **Severity:** Medium
- **Issue:** v1.0 specifies validity as `realized_R > 0 AND MFE_R > 0`, but does not address losing trades that had positive MFE before turning into losers — these are diagnostically important (winners-to-losers) but capture ratio as defined excludes them.
- **Resolution (v1.1):** Restrict capture ratio to winning trades only (`realized_R > 0 AND MFE_R > 0`). For losing trades with `MFE_R > 0`, compute `giveback_R` (see F-007) instead and tag the trade as `winner_to_loser` if `MFE_R >= 1.0`.

### F-007 — Giveback formula unconstrained on losers

- **Source:** §8.4
- **Severity:** Medium
- **Issue:** `giveback_R = MFE_R - realized_R` for a losing trade with MFE = 0.5R and realized = -1R produces giveback = 1.5R. This conflates two effects (giveback of available profit + magnitude of loss) and pollutes aggregate giveback metrics.
- **Resolution (v1.1):** Define giveback only when `MFE_R > 0` and split into two reportable quantities:
  - `giveback_R_winners` (winners only): how much profit was surrendered before exit.
  - `giveback_R_winners_to_losers` (losers with MFE_R > 0): how much available profit was converted to a loss.
  - Aggregate `average_giveback_R` over winners only by default; expose the winners-to-losers variant separately.

### F-008 — Daily return undefined on first trading day

- **Source:** §5.3
- **Severity:** Low
- **Issue:** If `start_equity` is zero on day one (account opened that day with first deposit), `daily_return_pct` is undefined.
- **Resolution (v1.1):** Define first-day rule: if the account has no prior trading day, `daily_return_pct = 0` and `start_equity` is set to the opening deposit. Document this in §5.3.

### F-009 — Drawdown sign convention not stated explicitly

- **Source:** §5.6, §11
- **Severity:** Low (clarity)
- **Issue:** v1.0 states "drawdown should be zero or negative" once but does not propagate that convention into the rules engine, where `current_drawdown_R <= policy.drawdown_pause_threshold_R` only makes sense if both sides are negative.
- **Resolution (v1.1):** Add an explicit sign convention paragraph at the top of §5.6: drawdown values are always ≤ 0; thresholds in `Risk_Policy` must be expressed as negative numbers. Update §13.4 examples accordingly.

### F-010 — Decomposed expectancy ignores scratch trades

- **Source:** §6.4
- **Severity:** Medium
- **Issue:** `expectancy_R = (win_rate * avg_win_R) + (loss_rate * avg_loss_R)` only equals `average(realized_R)` if every trade is a win or a loss. Scratch trades (realized_R ≈ 0) cause the two formulas in §6.3 and §6.4 to diverge.
- **Resolution (v1.1):** See F-014 for scratch definition. Decomposed form becomes:
  ```
  expectancy_R = win_rate * avg_win_R + loss_rate * avg_loss_R + scratch_rate * avg_scratch_R
  ```
  where `win_rate + loss_rate + scratch_rate = 1`. `avg_scratch_R` will be near zero by definition but should be reported, not assumed.

---

## 2. Undefined or Ambiguous Semantics

### F-011 — `raw_current_at_risk_dollars` reference point not defined

- **Source:** §3.3, §5.7
- **Severity:** Critical
- **Issue:** Field described only as "Risk to current stop before floor." The downstream floor logic (`max(0, raw)` for heat, `max(0, -raw)` for locked-in profit) only works if `raw` can be negative — implying anchor to entry, not current price. v1.0 leaves the reader to infer this.
- **Resolution (v1.1):** State explicit formulas:
  ```
  Long:  raw_current_at_risk_dollars = (avg_cost - current_stop) * quantity_open
  Short: raw_current_at_risk_dollars = (current_stop - avg_cost) * quantity_open
  ```
  Both produce: positive = at risk relative to entry; negative = locked-in profit at stop. Add a worked example showing the floor behavior for a stop moved above breakeven.

### F-012 — `entry_slippage_R` referenced but never formulated

- **Source:** §4.2
- **Severity:** Medium
- **Issue:** Field appears in `Trade_Performance_Facts` with no formula.
- **Resolution (v1.1):**
  ```
  Long:  entry_slippage_R = (planned_entry - actual_entry_price_vwap) / risk_per_share
  Short: entry_slippage_R = (actual_entry_price_vwap - planned_entry) / risk_per_share
  ```
  In both cases negative = paid worse than planned. `actual_entry_price_vwap` is the volume-weighted average of all `action='entry'` and `action='add'` fills before the first exit/trim/stop fill. Anchored to the planned trade, not subsequent re-plans.

### F-013 — `pre_trade_locked_at` scope undefined

- **Source:** §3.4
- **Severity:** High (data integrity)
- **Issue:** Field exists "to protect hindsight integrity" but v1.0 never says which fields are locked.
- **Resolution (v1.1):** Define the locked field set explicitly:
  - `planned_entry`, `initial_stop`, `risk_per_share`, `planned_position_size`, `planned_risk_dollars`, `planned_reward_risk_ratio`, `target_1`, `target_2`
  - `setup_id`, `market_regime`, `catalyst`, `thesis`, `invalidation_condition`, `premortem_failure_reasons`
  - `pre_trade_quality_score`, `emotional_state_pre_trade`
  
  Subsequent edits to any of these post-fill require an explicit `override_reason` and produce a `pre_trade_field_modified_after_lock` audit row. Mistake_cost computations always use the locked values.

### F-014 — Scratch trade treatment undefined

- **Source:** §6.3–6.5, §6.7, §9
- **Severity:** Medium
- **Issue:** A trade with `realized_R = 0` (or near-zero) is implicitly classified as a loss in some formulas (`profit_factor` denominator could include it) and a non-event in others. v1.0 never defines the boundary.
- **Resolution (v1.1):** Define:
  ```
  scratch_trade: abs(realized_R) < scratch_epsilon
  default scratch_epsilon = 0.10  (configurable in Risk_Policy)
  ```
  - Wins: `realized_R >= scratch_epsilon`
  - Losses: `realized_R <= -scratch_epsilon`
  - Scratches: `abs(realized_R) < scratch_epsilon`
  
  Profit factor uses positive vs absolute-negative sums, so scratches contribute approximately zero to both. Win rate, loss rate, and scratch rate sum to 1.

### F-015 — Initial risk anchoring with scale-ins ambiguous

- **Source:** §4.2, §6
- **Severity:** High
- **Issue:** v1.0 does not state whether `initial_risk_dollars` re-anchors when a position is added to.
- **Resolution (v1.1):** `initial_risk_dollars` is locked at first fill from `Trade_Plans.planned_risk_dollars` (which already reflects the full planned position, including planned scale-ins). It is immutable for the life of the trade. Discretionary adds outside the plan are flagged as process deviations:
  - New mistake tag: `UNPLANNED_ADD` (or `UNPLANNED_SCALE_IN`).
  - New derived field on `Trade_Performance_Facts`: `risk_added_after_initial_R` = (sum of risk added by unplanned adds, in R units of initial risk).
  - The R denominator is never changed by adds. This preserves cross-trade comparability.

---

## 3. Missing Specifications

### F-016 — Short-side formulas missing throughout

- **Source:** Pervasive (§5, §6, §7, §8)
- **Severity:** High (when shorts allowed)
- **Issue:** v1.0 declares `direction: long or short` in §3.4 but specifies long-only formulas everywhere. Long-only deployments are fine; mixed deployments will silently produce wrong numbers for shorts.
- **Resolution (v1.1):** For every direction-dependent formula, add the short variant. Sign convention: `quantity_open` is stored as a positive number; `direction` ∈ {long, short} drives sign in formulas. Add a single canonical "Direction Conventions" subsection (§5.0 or §6.0) so subsequent formulas can reference it instead of repeating.

### F-017 — Multiple fills, partial exits, and scale-ins not handled

- **Source:** §6, §8
- **Severity:** High
- **Issue:** The `Fills` table supports `entry`, `add`, `trim`, `exit`, `stop`, `cover` but the metric formulas treat trades as single-entry, single-exit.
- **Resolution (v1.1):** Add an explicit "Multi-leg trade math" subsection:
  - **Entry price:** volume-weighted average of all `entry` and `add` fills.
  - **Exit price:** volume-weighted average of all `trim`, `exit`, `stop`, `cover` fills, weighted by quantity exited.
  - **Net P&L (long):** `sum_over_exit_fills((exit_price - vwap_entry_at_time_of_exit) * exit_qty) - sum(fees)`. For matched-lot accuracy, FIFO match exit fills against entry fills.
  - **Realized_R:** `net_pnl_dollars / initial_risk_dollars`, denominator immutable per F-015.
  - **MFE_R / MAE_R:** computed across the full holding window from first entry to final exit.
  - **Partial exits in progress:** treat the closed portion's P&L as realized, the remaining portion as open; report both separately on dashboards.

### F-018 — Fees treatment in realized_R not stated

- **Source:** §3.5, §4.2, §6.1
- **Severity:** Medium
- **Issue:** `net_pnl_dollars` is described as "net realized P&L" but v1.0 never says fees are subtracted.
- **Resolution (v1.1):** State explicitly: `net_pnl_dollars` is net of all fees and commissions (`Fills.fees`) recorded against the trade. `realized_R = net_pnl_dollars / initial_risk_dollars` is therefore net-of-fee. Optionally expose `gross_realized_R` as a separate field for cost-impact analysis.

### F-019 — Corporate actions during open trades not addressed

- **Source:** Throughout
- **Severity:** Medium
- **Issue:** Splits, dividends, ticker changes, and mergers can break MFE/MAE, avg_cost, and quantity_open continuity for swing trades that span the action date.
- **Resolution (v1.1):** Add `Corporate_Actions` table with fields: `action_id`, `ticker`, `effective_date`, `action_type` ∈ {split, reverse_split, cash_dividend, stock_dividend, spinoff, merger, ticker_change}, `ratio_or_amount`, `notes`. Rules:
  - Splits/reverse splits: adjust `avg_cost` and `quantity_open` preserving total dollar basis. Recompute MFE/MAE on adjusted price series.
  - Cash dividends: log as `Cash_Flows` with `type=dividend`, `external_to_trading=false`. Counts as trading return; does not change `avg_cost`.
  - Ticker changes: maintain trade continuity by linking old and new tickers via `Corporate_Actions`.
  - For MVP scope, document that corporate actions during open positions require manual reconciliation if the broker export does not auto-adjust.

### F-020 — Money-weighted return / IRR mentioned but never defined

- **Source:** §3.2 (Cash_Flows purpose), referenced nowhere else
- **Severity:** Low
- **Issue:** Listed as a use of `Cash_Flows` data but no formula or table field exists.
- **Resolution (v1.1):** Remove the MWR/IRR mention from the `Cash_Flows` purpose block. For swing trading, TWR plus cumulative return is sufficient. If MWR is wanted later, add it as a separate enhancement; do not leave it dangling in v1.1.

### F-021 — Risk policy versioning missing

- **Source:** §3.9
- **Severity:** High
- **Issue:** `Risk_Policy` has a `policy_id` but no `effective_from` / `effective_to`. If the policy is updated, historical metric evaluations would silently shift to the new policy, breaking the audit trail.
- **Resolution (v1.1):** Add fields: `effective_from` (date, required), `effective_to` (date, nullable for currently-active policy), `policy_version` (integer, monotonic), `change_reason` (text). Rules engine evaluates each trade against the policy effective on `Trade_Plans.planned_date`. Only one policy may have a null `effective_to` at any moment.

### F-022 — Setup_Playbook audit trail missing

- **Source:** §3.8
- **Severity:** Medium
- **Issue:** `status` ∈ {active, pilot, paused, retired} but no history of changes. A retired setup whose status is later flipped back to active leaves no record of the transition.
- **Resolution (v1.1):** Add `Setup_Status_History` table: `setup_id`, `status`, `effective_from`, `effective_to`, `change_reason`, `triggering_recommendation_id` (nullable, links to a recommendation candidate that drove the change). The current `Setup_Playbook.status` field becomes a derived view of the most recent history row.

### F-023 — Currency / FX handling absent

- **Source:** Throughout
- **Severity:** Low (depends on use)
- **Issue:** No `currency` field anywhere. For US-only stock trading this is fine; for ADRs, foreign listings, or multi-account setups it breaks.
- **Resolution (v1.1):** Add `account_currency` to `Account_Equity_Snapshots` (default USD). Add `instrument_currency` and `fx_rate_at_entry` / `fx_rate_at_exit` to `Trade_Plans` and `Trade_Performance_Facts`, both nullable. For single-currency MVP deployments document the assumption explicitly: "all amounts assumed account_currency unless instrument_currency present."

### F-024 — Trading-day calendar and timezone unspecified

- **Source:** Frontmatter, §3.1
- **Severity:** Medium
- **Issue:** `timezone_context: Pacific/Honolulu` is given for the user, but `snapshot_date` semantics (is it the NYSE trading day or the local calendar day in HI?) are not stated. Holidays and half-days unhandled.
- **Resolution (v1.1):** Specify:
  - `snapshot_date` = the US market trading day (NYSE calendar). Half-days count as full snapshot days. Non-trading days produce no snapshot row.
  - All stored timestamps in UTC. User-facing display in `Pacific/Honolulu` is a presentation concern, not a storage concern.
  - Reference NYSE holiday calendar (or pluggable calendar source) for holiday handling.

### F-025 — Open-position MFE/MAE not specified

- **Source:** §7
- **Severity:** Medium
- **Issue:** `open_MFE_to_date_R` and `open_MAE_to_date_R` are listed as open-position metrics but the spec never says how they are computed for an in-flight trade.
- **Resolution (v1.1):** Computed using the same precision rules as closed-trade MFE/MAE (§8.2). Updated at each daily snapshot. Stored on `Positions_Daily_Snapshots`. When the trade closes, the final values become the trade's `MFE_R` / `MAE_R` on `Trade_Performance_Facts`.

### F-026 — `mistake_cost_R` subjectivity unaddressed

- **Source:** §3.6
- **Severity:** Medium
- **Issue:** "Non-negative R harm from rule violations" is highly subjective. Without guidance, the same trader may be inconsistent week to week, contaminating process metrics.
- **Resolution (v1.1):** Add a definition guidance subsection:
  ```
  mistake_cost_R = max(0, abs(realized_R) - hypothetical_R_if_plan_followed) when realized_R is worse than the plan,
                 = 0 otherwise
  ```
  Add `mistake_cost_method` field ∈ {`counterfactual_estimate`, `direct_measurement`, `bracketed_range`} alongside the existing `mistake_cost_confidence`. Direct measurement is preferred when the plan exit was a defined price; counterfactual estimation is for ambiguous cases.

### F-027 — `cumulative_R` vs dollar P&L conflation risk

- **Source:** §4.1, §15
- **Severity:** Medium
- **Issue:** `cumulative_R` is presented alongside dollar metrics on dashboards but is a strategy-edge measurement, not a dollar-performance measurement. If position sizing changed materially across the period (e.g., risking $200/trade then $500/trade), summed R is misleading as a portfolio-performance proxy.
- **Resolution (v1.1):** Add explicit interpretive note in §4.1 and again in §15.1:
  > `cumulative_R` measures strategy edge in normalized risk units. It is not interchangeable with `cumulative_pnl_dollars`. Always pair them on dashboards to avoid misreading edge as growth.

  No formula change; this is an interpretive guardrail.

### F-028 — Risk-adjusted return ratios (Sharpe / Sortino) absent

- **Source:** §5, §11
- **Severity:** Low
- **Issue:** The spec includes recovery factor and return-over-max-drawdown but no volatility-based ratios.
- **Resolution (v1.1):** Acknowledge the choice in §11 with a brief note: for low-frequency swing trading, monthly Sharpe / Sortino become reliable only after ~12 months of returns. Add them as **optional** metrics with reliability label `provisional` until 12+ monthly returns exist, `actionable` after 24+. Do not add them to default dashboards.

---

## 4. Inconsistencies and Terminology Drift

### F-029 — `unrealized_R` vs `open_unrealized_R` terminology

- **Source:** §3.3, §4.1, §7
- **Severity:** Editorial
- **Issue:** Both terms are used, sometimes for the same thing.
- **Resolution (v1.1):** Standardize:
  - `unrealized_R` = single open position (used in `Positions_Daily_Snapshots`).
  - `open_unrealized_R` = portfolio-level aggregate sum (used in `Portfolio_Daily_Facts`).
  Reflect this in all sections.

### F-030 — Centralized enum reference missing

- **Source:** Throughout
- **Severity:** Medium
- **Issue:** Enums for `reconciliation_status`, `data_source`, `market_regime`, `catalyst`, `thesis_status`, `setup_validity_after_review`, `severity`, `action`, `mistake_tags`, etc. are defined inline at first use, sometimes with subtle variations between sections.
- **Resolution (v1.1):** Add §21 ("Enumeration Reference") that defines every enum's allowed values once. Inline mentions become references. Add a `mistake_tags` reference list with the v1.0 examples (CHASED, SOLD_TOO_EARLY, MOVED_STOP_AWAY, HELD_AFTER_INVALIDATION) plus the new tags introduced in v1.1 (UNPLANNED_ADD, UNPLANNED_SCALE_IN per F-015).

### F-031 — Dividend / interest treatment in adjusted_daily_pnl

- **Source:** §3.2, §5.2
- **Severity:** Medium
- **Issue:** `Cash_Flows` allows dividends/interest with `external_to_trading=false`, but §5.2's `external_cash_flow` term in the adjusted daily P&L formula does not say it excludes those entries.
- **Resolution (v1.1):** State explicitly in §5.2:
  > `external_cash_flow` in this formula is the sum of `Cash_Flows` rows for the day where `external_to_trading = true` (deposits, withdrawals, transfers). Dividends and interest with `external_to_trading = false` are part of trading return and are not subtracted.

### F-037 — Asymmetric early-signal rules

- **Source:** §1.1, §9.1
- **Severity:** Low
- **Issue:** §9.1 defines `early_positive_signal` at sample_size ≥ 10 with positive expectancy, but no symmetric early-negative-signal rule. §1.1's `early_setup_signal` says "create review task if concerning" — implying negative — but is not realized in the rule set.
- **Resolution (v1.1):** Add `early_negative_signal`:
  ```
  condition: sample_size >= 10 and expectancy_R < 0
  output: create informational review task; suppress pause/retire candidate
  ```

---

## 5. Process and Governance Gaps

### F-032 — "Missing review" referenced but not defined

- **Source:** §16, §19
- **Severity:** Medium
- **Issue:** `missing_review_count` and `missing reviews` appear in dashboards and acceptance criteria with no definition.
- **Resolution (v1.1):** Define:
  > A closed trade has `missing_review = true` when no `Trade_Reviews` row exists with `reviewed_at` within `review_lag_threshold_days` (default 7) of the trade's `exit_date`. Configurable per `Risk_Policy`.

### F-033 — Manual `market_regime` hindsight risk

- **Source:** §3.4, §3.7
- **Severity:** Medium
- **Issue:** `Trade_Plans.market_regime` is a planned input that should be locked pre-trade. `Market_Context_Daily.market_regime` is a daily classification that can be hindsight-biased if logged after the close.
- **Resolution (v1.1):**
  - `Trade_Plans.market_regime` is added to the `pre_trade_locked_at` lock set (F-013).
  - `Market_Context_Daily` gains a `regime_classified_at` timestamp. Records where `regime_classified_at` is after the close of the trading day are flagged `regime_classified_post_close = true`. Reports treat these with a hindsight-risk reliability flag.

### F-034 — Trade review lag not enforced

- **Source:** §3.6
- **Severity:** Low
- **Issue:** No mechanism flags reviews completed too long after the trade closed (recall decays).
- **Resolution (v1.1):** Add a deterministic rule:
  ```
  rule_id: review_overdue
  condition: closed_trade has no Trade_Reviews row and (today - exit_date) > review_lag_threshold_days
  action: create_review_task
  ```
  Add second rule for late-but-completed reviews:
  ```
  rule_id: review_completed_late
  condition: Trade_Reviews.reviewed_at - exit_date > review_lag_threshold_days
  action: notify (info severity); flag the review's reliability
  ```

---

## 6. Editorial and Versioning

### F-035 — Document version still says `standalone-1.0`

- **Source:** Frontmatter
- **Severity:** Editorial
- **Resolution (v1.1):** Bump version to `standalone-1.1`. Add a `changelog` block in the frontmatter listing the resolved findings by ID.

### F-036 — Filename retains `ai_ingestion` suffix

- **Source:** File metadata
- **Severity:** Editorial
- **Resolution (v1.1):** Suggested rename to `swing_trading_performance_metrics_v1_1.md`. The v1.1 spec output will use the cleaner filename; if the rename is undesirable, ignore.

---

## 7. Summary of v1.1 Changes Driven by These Findings

- **Foundational definitions added:** risk reference point with long/short formulas (F-011), initial risk anchoring with scale-in handling (F-015), `pre_trade_locked_at` lock set (F-013), scratch trade definition (F-014), direction conventions subsection (F-016).
- **Formula corrections:** cumulative return (F-001), TWR cash-flow timing (F-002), capture / giveback validity (F-006, F-007), decomposed expectancy with scratches (F-010), drawdown sign convention (F-009), edge-case handling for profit factor / recovery factor / breakeven win rate (F-003–F-005), first-day daily return (F-008).
- **New formulas defined:** `entry_slippage_R` (F-012), open-position MFE/MAE computation (F-025), multi-leg trade math (F-017), short-side variants of all directional formulas (F-016).
- **New tables and fields:** `Corporate_Actions` (F-019), `Setup_Status_History` (F-022), risk-policy versioning fields (F-021), `regime_classified_at` (F-033), `risk_added_after_initial_R` (F-015), `mistake_cost_method` (F-026), optional currency fields (F-023).
- **Interpretive guardrails:** `cumulative_R` vs dollar P&L distinction (F-027), Sharpe/Sortino reliability framing (F-028), dividend/interest in P&L (F-031).
- **Rules engine additions:** `early_negative_signal` (F-037), `review_overdue`, `review_completed_late` (F-034).
- **Cleanup:** centralized enum reference §21 (F-030), terminology standardization (F-029), MWR/IRR removed (F-020), missing_review defined (F-032), explicit calendar/timezone semantics (F-024), version bump and changelog (F-035, F-036).

## 8. Items Explicitly Deferred from v1.1

These were considered and intentionally not added in v1.1:

- Money-weighted return / IRR (F-020): removed rather than expanded; can return as enhancement.
- Sharpe / Sortino as default dashboard metrics (F-028): added as optional only; not in default dashboards.
- Multi-currency as a first-class concept (F-023): fields added, but MVP assumes single account currency.
- Tax / wash-sale tracking: not in scope.

---

*End of findings document.*
