# Phase 10 Metrics Dashboard — Design Spec (Brainstorm Output)

**Baseline:** `main` at commit `26c110f`; ~1940 fast tests green; schema_version = 15.

**Goal:** Lock metric DEFINITIONS + dashboard SURFACE SKETCHES + low-sample-size honesty POLICY for the Phase 10 metrics dashboard. Surface capture-needs feedback for Phase 8 + Phase 9 brainstorms. Lock the mistake-cost formula. RESEARCH-POSTURE: NO schema, NO code, NO task decomposition.

**Brief:** `docs/phase10-metrics-brainstorm-brief.md` (commit `3ad5ea2`).

**Sequencing:** Phase 10 brainstorm runs FIRST (research-only); Phase 8 brainstorm follows + consumes §2.4 capture-needs; Phase 9 brainstorm follows Phase 8; execution order is 8 → 9 → 10. Sample state at write-time: n=2 closed, n=3 open (5 total trades) — metric stability is the binding constraint, not ship velocity.

---

## 1. Background, framing, and binding constraints

### 1.1 What this spec produces

A locked set of metric definitions (§3), dashboard surface sketches (§4), a single low-sample-size honesty policy applied uniformly across both (§5), capture-needs feedback for the upcoming Phase 8 + Phase 9 + Phase 10+ brainstorms (§6), the mistake-cost formula determination (§7), and an enumerated open-question set for orchestrator triage (§8).

### 1.2 What this spec does NOT produce (out of scope)

Schema layouts, table definitions, CHECK constraints, indexes, view-model classes, query implementations, Jinja templates, route handlers, task decompositions, dispatch briefs. Schema is deferred to Phase 10 writing-plans AFTER Phases 8+9 ship the underlying capture infrastructure. Re-litigation of §1.4 DROP rules or §1.2 framework-fit gap analysis from the brief is also out of scope — those are accepted as given.

### 1.3 Binding constraints (orchestrator-distilled, not re-derived)

Per brief §1, the following are accepted as design inputs without re-justification:

1. **Hypothesis_label is the PRIMARY aggregation axis**, not a filter tag. Every trade-process metric exposes a per-cohort view.
2. **4 pre-registered hypothesis cohorts** are migration-locked at `swing/data/migrations/0008_hypothesis_registry.sql`: A+ baseline (target 20); Near-A+ defensible-extension (target 10); Sub-A+ VCP-not-formed (target 5); Capital-blocked smaller-position (target 10). Migration-locked fields: `target_sample_size`, `consecutive_loss_tripwire`, `absolute_loss_tripwire_pct`, `decision_criteria`. CLI-mutable fields: `status` (4-value enum) + `status_changed_at` + `status_change_reason` + `notes`.
3. **Capital tie-up is the primary constraint**, not identification rate. $7,500 capital floor for sizing; ~50-trade/year ceiling at full deployment.
4. **Sub-A+ trade-taking is doctrine deviation BY DESIGN.** Operational branch is an evidence-generation surface; sub-optimal trades within risk discipline are cost-of-development.
5. **v1.1-alternate is the structural baseline** for trade-process metrics (per rebuttal §4 final determination).
6. **DROP rules from `docs/phase3e-todo.md` "2026-05-01 Journal v1.2 incorporation"** apply to this design without re-litigation: Setup_Playbook-as-DB-entity DROP; pyramiding R-views (R_initial / R_effective / R_campaign) DROP — collapse to single `planned_risk_budget_dollars`; self-rated `pre_trade_quality_score` DROP; `UNPLANNED_ADD` mistake tag + `risk_added_after_initial_R` DROP; v1.2's 7-value `trade_origin` DROP — replaced by shipped 4-value pipeline-aware enum (`pipeline_aplus`, `pipeline_watch_hyp_recs`, `pipeline_watch_manual`, `manual_off_pipeline`); drawdown circuit breaker DEFAULT opt-in disabled.
7. **Mistake-cost formula triage is the ONE design decision opened to brainstorm** — see §7.

### 1.4 Surprise discovered during research (single deviation from brief premise)

The brief's §1.5 stated that Phase 6 ships v1.1-main's `mistake_cost_R = max(0, abs(realized_R) - plan_followed_R)`. **This is incorrect.** Phase 6's actual code at `swing/trades/review.py:157-174` already implements the v1.1-alternate / v1.2 §8.8 formula:

```python
def compute_mistake_cost_R(*, realized_R_if_plan_followed, actual_realized_R_effective):
    """v1.2 §8.8: max(0, plan - actual). Never netted with lucky."""
    return max(0.0, realized_R_if_plan_followed - actual_realized_R_effective)

def compute_lucky_violation_R(*, realized_R_if_plan_followed, actual_realized_R_effective):
    """v1.2 §8.8: max(0, actual - plan). Never netted with cost."""
    return max(0.0, actual_realized_R_effective - realized_R_if_plan_followed)
```

Both `mistake_cost_R` and the symmetric `lucky_violation_R` are in code. The Phase 6 review_log even persists `total_lucky_violation_R` as a frozen-at-review aggregate (`migrations/0013_phase6_post_trade_review.sql:57`). The brainstorm's mistake-cost triage therefore **affirms** the shipped formula rather than replacing it (see §7). The actionable open question that remains is whether the Phase 6 review surface should display `lucky_violation_R` on the per-trade review form (currently computed but not surfaced — captured as §8 open question).

---

## 2. Vocabulary anchored against shipped surfaces

To avoid drift, this spec uses the field names already shipped in the production schema (post-Phase 7 migration 0014):

| Concept | Shipped name | Source |
|---|---|---|
| Pre-registered hypothesis | `trades.hypothesis_label` (free-text, migration 0007) + `hypothesis_registry.name` (migration 0008) | shipped |
| Pipeline classification origin | `trades.trade_origin` (4-value enum: `pipeline_aplus` / `pipeline_watch_hyp_recs` / `pipeline_watch_manual` / `manual_off_pipeline`) | shipped (migration 0014) |
| Trade lifecycle stage | `trades.state` (5-value: `entered` / `managing` / `partial_exited` / `closed` / `reviewed`) | shipped |
| Counterfactual P&L | `trades.realized_R_if_plan_followed` (REAL) | shipped (migration 0013) |
| Process grading | `trades.entry_grade` / `management_grade` / `exit_grade` / `process_grade` (A/B/C/D/F CHECK) | shipped |
| Disqualifying violation | `trades.disqualifying_process_violation` (0/1 CHECK) | shipped |
| Mistake taxonomy | `trades.mistake_tags` (JSON-text, validated at repo) | shipped |
| Review aggregates | `review_log.total_mistake_cost_R` / `total_lucky_violation_R` / `net_R_effective` / `expectancy_R_effective` / `win_rate` / `avg_win_R` / `avg_loss_R` / `profit_factor` / `max_drawdown_R` (frozen-at-review) | shipped (migration 0013) |
| Fill action | `fills.action` (4-value: `entry` / `trim` / `exit` / `stop`) | shipped (migration 0014); `add` NOT in enum — see §8.1 |
| Pipeline run anchor | `pipeline_runs.evaluation_run_id` → `pipeline_run_id` (Bug 7 family discipline) | shipped |

**Single risk denominator (per §1.3 DROP rule):** `planned_risk_budget_dollars` is the ONE denominator. v1.1-alternate's triple-denominator model (`planned_risk_budget` / `initial_executed_risk` / `max_executed_risk`) collapses to the single value because no pyramiding plan exists. Where this spec writes "R" without qualification, it means realized_R against `planned_risk_budget_dollars`.

**Slippage convention (per v1.1-alternate / rebuttal F-012):** `entry_adverse_slippage_R = (vwap_entry_price - planned_entry) / risk_per_share`; positive = worse than planned. Adverse-positive convention preserved across all slippage metrics.

**Drawdown sign convention:** drawdowns are always ≤ 0; thresholds in `Risk_Policy` (Phase 9) expressed as negative numbers (per v1.1-alternate F-009).

---

## 3. Metric inventory (DEFINITIONS, not schema)

For each metric: definition + unit + inputs + aggregation + low-sample-size disposition. Inputs labeled `[shipped]` / `[Phase 8]` / `[Phase 9]` / `[Phase 10+]` / `[derived]`.

### 3.1 Trade-process metrics (closed-trade scope)

These are the v1.1-alternate baseline metrics with the §1.3 collapses applied. Every metric in this category is presentable per-hypothesis-cohort.

| Metric | Definition | Unit | Inputs | Aggregation |
|---|---|---|---|---|
| `realized_R` | `net_pnl_dollars / planned_risk_budget_dollars`; net of fees | R | `[shipped]` | per-trade; cohort mean |
| `gross_realized_R` | `gross_pnl_dollars / planned_risk_budget_dollars`; before fees | R | `[shipped]` | per-trade; cohort mean (advanced) |
| `expectancy_R` | `mean(realized_R)` over closed trades in cohort | R | `[derived]` | cohort mean |
| `win_rate` | `count(realized_R ≥ scratch_epsilon) / count(closed)` | proportion | `[derived]` + `[Phase 9]` scratch_epsilon | cohort rate |
| `loss_rate` | `count(realized_R ≤ -scratch_epsilon) / count(closed)` | proportion | same | cohort rate |
| `scratch_rate` | `count(abs(realized_R) < scratch_epsilon) / count(closed)` | proportion | same; default `scratch_epsilon = 0.10R` | cohort rate |
| `avg_win_R` | mean of `realized_R` over wins | R | `[derived]` | cohort mean |
| `avg_loss_R` | mean of `realized_R` over losses (negative number) | R | `[derived]` | cohort mean |
| `profit_factor` | `sum(R where R>0) / abs(sum(R where R<0))` | ratio | `[derived]` | cohort ratio; null when no losers |
| `payoff_ratio` | `avg_win_R / abs(avg_loss_R)` | ratio | `[derived]` | cohort ratio; requires ≥1 win + ≥1 loss |
| `MFE_R` (closed) | max favorable excursion / planned_risk_budget_dollars | R | `[Phase 8]` daily_management_records | per-trade; cohort mean |
| `MAE_R` (closed) | max adverse excursion / planned_risk_budget_dollars | R | `[Phase 8]` daily_management_records | per-trade; cohort mean |
| `capture_ratio` | `realized_R / MFE_R`; winners only | proportion | `[Phase 8]` + `[derived]` | cohort mean (winners) |
| `giveback_R_winner` | `MFE_R - realized_R`; winners with MFE>0 | R | `[Phase 8]` + `[derived]` | cohort mean (winners) |
| `giveback_R_winner_to_loser` | `MFE_R - realized_R`; losers with MFE>0 | R | same | cohort mean (subset) |
| `entry_adverse_slippage_R` | `(vwap_entry - planned_entry) / risk_per_share`; positive = worse | R | `[shipped]` (fills + trades) | per-trade; cohort mean |
| `mistake_cost_R` | `max(0, realized_R_if_plan_followed - actual_realized_R_effective)` | R (≥0) | `[shipped]` | per-trade; cohort sum |
| `lucky_violation_R` | `max(0, actual_realized_R_effective - realized_R_if_plan_followed)` | R (≥0) | `[shipped]` | per-trade; cohort sum |
| `process_grade` | weighted A/B/C/D/F per Phase 6 (entry 0.40 + management 0.35 + exit 0.25; F-floor; D-cap on disqualifying) | grade | `[shipped]` | per-trade; cohort distribution |
| `disqualifying_process_violation_rate` | `count(disqualifying_process_violation=1) / count(reviewed)` | proportion | `[shipped]` | cohort rate |
| `holding_period_days` | `last_fill_at - pre_trade_locked_at`, in trading days | days | `[shipped]` | per-trade; cohort mean |
| `mistake_tag_frequency` | per-tag count / total reviewed | proportion | `[shipped]` mistake_tags JSON | cohort rate per tag |

### 3.2 Per-hypothesis cohort metrics (NEW — primary axis)

Aggregations of §3.1 metrics keyed on `trades.hypothesis_label` joined to `hypothesis_registry`. Plus governance metrics specific to pre-registration discipline.

| Metric | Definition | Unit | Inputs | Aggregation |
|---|---|---|---|---|
| `cohort_n_closed` | count of closed trades for this hypothesis_label | count | `[shipped]` | per-cohort |
| `cohort_progress_pct` | `cohort_n_closed / hypothesis_registry.target_sample_size` | proportion | `[shipped]` | per-cohort |
| `cohort_expectancy_R` | mean realized_R over cohort closed trades | R | `[derived]` | per-cohort |
| `consecutive_loss_run` | length of current consecutive-loss streak ending on most-recent closed trade | count | `[shipped]` | per-cohort |
| `distance_to_loss_tripwire` | `consecutive_loss_tripwire - consecutive_loss_run` | count (≥0) | `[shipped]` | per-cohort |
| `cumulative_R_pct_of_capital` | sum of cohort realized P&L / capital floor (`max($7,500, actual_balance)`) | proportion | `[shipped]` | per-cohort |
| `distance_to_absolute_loss_tripwire` | `absolute_loss_tripwire_pct - abs(min(0, cumulative_R_pct_of_capital))` | proportion (≥0) | `[shipped]` | per-cohort |
| `cohort_status` | passthrough of `hypothesis_registry.status` (4-value: active / paused / closed-escaped / closed-target-met) | enum | `[shipped]` | per-cohort |
| `decision_criteria_evaluation` | rendered text from `hypothesis_registry.decision_criteria` paired with current cohort metric values (no automated pass/fail in V1) | text | `[shipped]` | per-cohort |
| `cohort_status_change_log` | history of `status_changed_at` + `status_change_reason` | timeline | `[shipped]` | per-cohort |

**Tripwire-distance integrity (brief watch-item 3):** `consecutive_loss_tripwire` and `absolute_loss_tripwire_pct` are migration-locked. The metric reads them from `hypothesis_registry`, never from a settable Risk_Policy field. If Risk_Policy (Phase 9) introduces a settable mirror, the metric MUST source from the migration table, not the Phase 9 mirror.

### 3.3 Tier-comparison metrics (NEW)

Compares outcome distributions across the 4 cohorts. Tests the framework's own classification quality (A+ should outperform Sub-A+; Near-A+ within 25% of A+).

| Metric | Definition | Unit | Inputs | Aggregation |
|---|---|---|---|---|
| `cohort_win_rate_with_CI` | per-cohort win_rate with Wilson CI bounds | proportion + lower/upper | `[derived]` | 4-cohort comparison |
| `cohort_expectancy_with_CI` | per-cohort expectancy_R with bootstrap-CI bounds (1000 resamples) | R + lower/upper | `[derived]` | 4-cohort comparison |
| `cohort_relative_to_aplus` | `cohort_expectancy_R / aplus_expectancy_R - 1` | proportion | `[derived]` | per-cohort vs A+ baseline |
| `classification_quality_flag` | informational: does A+ cohort's lower CI bound exceed Sub-A+ cohort's upper CI bound? | boolean | `[derived]` | framework-wide |

**No pass/fail rule** is defined on `classification_quality_flag` — it is a research-posture diagnostic. Operator interprets in context. Brief watch-item 4 satisfied: every output is paired with a CI; no point-estimate-only presentation; suppression policy (§5) applies before CI rendering.

### 3.4 Capital-friction metrics (NEW — capture-need-heavy)

Measures the operational constraint the brief calls primary. Most inputs require Phase 10+ NEW capture (per §6.3).

| Metric | Definition | Unit | Inputs | Aggregation |
|---|---|---|---|---|
| `risk_feasibility_blocked_rate` | `count(candidates with risk_feasibility=False) / count(candidates with all_other_criteria=True)` per pipeline run | proportion | `[Phase 10+]` per-run aggregate | per-run; multi-run trend |
| `current_capital_utilization_pct` | `sum(open_position_avg_cost × current_size) / capital_floor` | proportion | `[shipped]` | point-in-time |
| `current_portfolio_heat_pct` | `sum(portfolio_heat_contribution_dollars) / capital_floor` (per-position contribution from §3.5) | proportion | `[Phase 8]` daily_management_records | point-in-time |
| `capital_cycle_time_days` | mean(`closed_trade.last_fill_at - closed_trade.pre_trade_locked_at`) over closed cohort | days | `[shipped]` | cohort mean |
| `concurrent_open_positions` | count of trades in state ∈ {entered, managing, partial_exited} | count | `[shipped]` | point-in-time |
| `capital_feasibility_pressure_index` | `risk_feasibility_blocked_rate × current_capital_utilization_pct` (composite indicator) | proportion | `[derived]` | per-run |

`capital_floor = max($7,500, actual_account_balance)` per the user-memory `project_capital_risk_floor` convention.

### 3.5 Maturity-stage metrics (NEW — open-position scope)

Operationally urgent for currently-open trades. Maps each open position to a discrete stage based on `open_MFE_R_to_date`. Drives operator action surface.

| Metric | Definition | Unit | Inputs | Aggregation |
|---|---|---|---|---|
| `maturity_stage` | classification: `pre_+1.5R` / `+1.5R_to_+2R` / `≥+2R_trail_eligible` / `closed` | enum | `[Phase 8]` daily_management_records | per-position |
| `open_MFE_R_to_date` | max favorable excursion since `pre_trade_locked_at`, in R | R | `[Phase 8]` | per-position |
| `open_MAE_R_to_date` | max adverse excursion since `pre_trade_locked_at`, in R | R | `[Phase 8]` | per-position |
| `trail_MA_eligibility_flag` | `open_MFE_R_to_date ≥ +2.0R` AND `current_stop < trail_MA_candidate_price` | boolean | `[Phase 8]` | per-position |
| `position_capital_utilization_pct` | `current_avg_cost × current_size / capital_floor` | proportion | `[shipped]` | per-position |
| `position_portfolio_heat_contribution_dollars` | `max(0, (current_avg_cost - current_stop) × current_size)` | $ | `[shipped]` | per-position; sums to portfolio-heat |

Stage thresholds (`+1.5R`, `+2.0R`) are anchored on Tier-3 doctrine (brief §1.2) and are NOT operator-configurable in V1. If the trail-MA gating threshold becomes operator-configurable later, version-stamping happens via Risk_Policy (Phase 9).

### 3.6 Identification-vs-trade-funnel metrics (NEW)

Tests the divergence between candidate identification rate and trade-take rate (capital-utilization the bottleneck, not identification).

| Metric | Definition | Unit | Inputs | Aggregation |
|---|---|---|---|---|
| `aplus_identifications_per_run` | count of A+ candidates per pipeline_run | count | `[shipped]` candidates table | per-run |
| `aplus_trades_taken_per_run` | count of trades with `trade_origin='pipeline_aplus'` AND `pre_trade_locked_at` falls in run's session date | count | `[shipped]` | per-run |
| `aplus_take_rate_per_run` | `aplus_trades_taken_per_run / aplus_identifications_per_run` | proportion | `[derived]` | per-run; multi-run trend |
| `watch_identifications_per_run` | count of watch-bucket candidates per run | count | `[shipped]` | per-run |
| `watch_trades_taken_per_run` | count of trades with `trade_origin ∈ {pipeline_watch_hyp_recs, pipeline_watch_manual}` AND session-date match | count | `[shipped]` | per-run |
| `aplus_funnel_30d_trend` | rolling 30-trading-day trend of `aplus_take_rate_per_run` | proportion + slope | `[derived]` | trend |

### 3.7 Deviation-outcome metrics (NEW)

Tests the §1.3 framing that sub-A+ trades are evidence-generation. Per-cohort: how does deviation from A+ doctrine map to outcome distributions?

| Metric | Definition | Unit | Inputs | Aggregation |
|---|---|---|---|---|
| `cohort_doctrine_deviation_class` | classification by hypothesis: A+ baseline = 0; Near-A+ = "missing_proximity_20ma"; Sub-A+ = "missing_tightness_or_vcp_volume_contraction"; Capital-blocked = "smaller_than_standard_position" | enum (4 values) | `[shipped]` `hypothesis_registry.statement` | per-cohort |
| `cohort_expectancy_relative_to_aplus_pct` | (= `cohort_relative_to_aplus` from §3.3, surfaced here as deviation-outcome lens) | proportion | `[derived]` | per-cohort vs A+ |
| `cohort_consistency_rate` | proportion of cohort trades with sign-of-realized_R matching the hypothesis prediction (positive for A+/Near-A+/Capital-blocked; negative for Sub-A+) | proportion | `[derived]` | per-cohort |

### 3.8 Process-grade-trend metrics (NEW)

Phase 6 ships point-in-time grade. Trend over rolling-N closed trades is the actionable surface (operator's process improvement loop).

| Metric | Definition | Unit | Inputs | Aggregation |
|---|---|---|---|---|
| `process_grade_rolling_N` | rolling mean of process_grade (numeric A=4 / B=3 / C=2 / D=1 / F=0) over last N=10 closed trades | numeric grade | `[shipped]` | rolling window |
| `entry_grade_rolling_N` | per-stage rolling mean | numeric grade | `[shipped]` | rolling window |
| `management_grade_rolling_N` | per-stage rolling mean | numeric grade | `[shipped]` | rolling window |
| `exit_grade_rolling_N` | per-stage rolling mean | numeric grade | `[shipped]` | rolling window |
| `disqualifying_violation_rate_rolling_N` | rate of disqualifying_process_violation=1 over last N | proportion | `[shipped]` | rolling window |
| `mistake_cost_R_rolling_N_total` | sum over last N | R | `[shipped]` | rolling window |
| `mistake_cost_R_rolling_N_per_trade` | mean over last N | R | `[derived]` | rolling window |

`N=10` is the V1 default; matched to A+ target (20 / 2 = window granularity for trend). Operator-configurable via `swing.config.toml` is an open question (§8.5).

### 3.9 Metrics explicitly DEFERRED at our sample size

Per brief §1.3. Each is documented as deferred, not removed — when n threshold is met, they re-enter scope. The deferred set must NEVER appear in the default dashboard.

| Metric | Deferral threshold | Rationale |
|---|---|---|
| Sharpe ratio | ≥12 monthly returns of daily-equity capture | Phase 8/9 daily equity required first; n meaningless before |
| Sortino ratio | same | same |
| Time-weighted return | daily-equity capture (Phase 8/9) | computation requires capture |
| Cumulative return pct (equity-curve based) | daily-equity capture | same |
| Benchmark-relative excess return | ≥60 trading days of TWR + benchmark series | sample defensibility |
| Equity-curve drawdown_pct | daily-equity capture | prefer R-drawdown until then |
| Recovery factor | n≥20 closed trades | low-n noise dominates |
| Breakeven win rate | n≥20 + ≥1 win + ≥1 loss | low-n noise dominates |
| Maximum Adverse Drawdown (equity) | daily-equity capture | same as above |

`max_drawdown_R` over closed-trade cumulative R series IS computed in V1 (already in Phase 6 review_log) and is the V1 substitute for equity-curve drawdown until daily-equity capture lands.

### 3.10 Operator-actionability discipline (brief watch-item 11)

Every metric in §3 must answer: "what action does the operator take based on reading X vs Y?" Metrics that produce no action are deprecated to "monitoring-only" or removed.

| Metric class | Action surface |
|---|---|
| Trade-process metrics (§3.1) | Inform per-trade review (Phase 6 review surface); inform mistake-tag application; inform process-grade trend judgment |
| Per-hypothesis cohort (§3.2) | Drive `hypothesis_registry.status` change decision (active → paused → closed-escaped/closed-target-met) per `decision_criteria` text |
| Tier-comparison (§3.3) | Sub-A+ cohort that disconfirms its own hypothesis at sample-target → `closed-escaped` candidate; informs framework calibration (NOT bucket-rule changes — those route through V2.1 §VII.F) |
| Capital-friction (§3.4) | High `risk_feasibility_blocked_rate` + low `aplus_take_rate` together → operator decision to add capital, accept lower take-rate, or revisit position-size formula |
| Maturity-stage (§3.5) | `trail_MA_eligibility_flag=True` → operator considers stop-trail per Tier-3 #6 doctrine |
| Identification-vs-trade-funnel (§3.6) | Multi-run divergence trend → see capital-friction action above |
| Deviation-outcome (§3.7) | Sustained per-cohort consistency rate < 0.5 at sample-target → hypothesis closed-escaped candidate |
| Process-grade-trend (§3.8) | Declining rolling grade → operator focus area for next N trades; mistake-tag clustering analysis |

Metrics that fail this test in §3 inventory: NONE in V1 inventory. All metrics carry an explicit action surface. (Brief watch-item 11 satisfied.)

---

## 4. Dashboard surface sketches (NOT HTML/code)

For each surface: name + primary axis + composition + sample-size threshold + operator-actionability note.

### 4.1 Trade-process card (refined v1.1-alternate Trade Dashboard)

- **Primary axis:** per-hypothesis-cohort, with "all closed trades" as default toggle; never a non-cohort default.
- **Composition (§3.1 metrics):** `expectancy_R` + Wilson/bootstrap CI; `win_rate` / `loss_rate` / `scratch_rate` with CIs; `avg_win_R` / `avg_loss_R`; `profit_factor` (with null-handling); `payoff_ratio`; `MFE_R` / `MAE_R` (cohort means); `capture_ratio` (winners only); `holding_period_days` (cohort mean); `entry_adverse_slippage_R` (cohort mean); total `mistake_cost_R` + total `lucky_violation_R`; process_grade distribution histogram.
- **Sample-size threshold:** suppress cohort with n<3 (§5 policy); show point-estimate-with-warning at 3≤n<5; CI from n=5 onward.
- **Operator-actionability:** drives per-trade review backlog ranking (low process_grade trades reviewed first); mistake-tag clustering analysis.

### 4.2 Hypothesis-progress card (extends Phase 4.5 already shipped)

- **Primary axis:** per-cohort, all 4 displayed in row.
- **Composition (§3.2 metrics):** `cohort_n_closed / target_sample_size` progress bar; `cohort_status` badge; `consecutive_loss_run` / `distance_to_loss_tripwire` tripwire indicator; `cumulative_R_pct_of_capital` / `distance_to_absolute_loss_tripwire`; `decision_criteria` text rendered alongside current metric values; `cohort_status_change_log` mini-timeline.
- **Sample-size threshold:** ALWAYS shown (governance surface; no suppression). Tripwire indicator present from n=1.
- **Operator-actionability:** primary surface for `hypothesis_registry.status` mutation decision. The CLI mutation requires operator-supplied `status_change_reason` (per migration 0008 schema).

### 4.3 Tier-comparison view (NEW)

- **Primary axis:** 4 cohorts side-by-side.
- **Composition (§3.3):** `cohort_win_rate_with_CI` per cohort; `cohort_expectancy_with_CI` per cohort; `cohort_relative_to_aplus` per non-A+ cohort; `classification_quality_flag` framework diagnostic.
- **Sample-size threshold:** suppress an individual cohort's CI when its n<5; suppress the comparison flag entirely until BOTH A+ and Sub-A+ cohorts have n≥5. Worked example at our current state (n=2 closed total): all CIs suppressed; placeholder text "Insufficient cohort samples (need ≥5 per cohort for CI; current: A+: 0, Sub-A+: 0, ...)".
- **Operator-actionability:** classification calibration check; informs decision-criteria evaluation.

### 4.4 Capital-friction view (NEW)

- **Primary axis:** point-in-time + multi-run trend.
- **Composition (§3.4):** current `current_capital_utilization_pct` gauge; current `current_portfolio_heat_pct` gauge; `concurrent_open_positions / 5_max`; multi-run `risk_feasibility_blocked_rate` line; multi-run `capital_feasibility_pressure_index` line; cohort mean `capital_cycle_time_days`.
- **Sample-size threshold:** point-in-time gauges always shown; multi-run trends require ≥5 runs of post-Phase-10+-capture data; suppress trend until then.
- **Operator-actionability:** decision surface for capital-add-vs-take-rate-tradeoff.

### 4.5 Maturity-stage view (NEW)

- **Primary axis:** per-open-position.
- **Composition (§3.5):** position table sorted by `maturity_stage`; columns `ticker / open_MFE_R_to_date / current_stop / planned_target_R / trail_MA_eligibility_flag / position_portfolio_heat_contribution_dollars`. Aggregate: count by `maturity_stage`.
- **Sample-size threshold:** N/A (per-position, not aggregate).
- **Operator-actionability:** primary daily-management surface; `trail_MA_eligibility_flag=True` is a discrete operator action prompt.

### 4.6 Identification-vs-trade-funnel view (NEW)

- **Primary axis:** per-pipeline-run + multi-run trend.
- **Composition (§3.6):** stacked bar per run: `aplus_identifications_per_run` / `aplus_trades_taken_per_run` (the ratio = `aplus_take_rate_per_run`); rolling 30-trading-day trend line of take-rate.
- **Sample-size threshold:** point-in-time bar always shown; trend requires ≥10 runs.
- **Operator-actionability:** confirms or disconfirms the framework's "capital is the constraint" thesis at the operational layer; pairs with capital-friction view.

### 4.7 Deviation-outcome view (NEW)

- **Primary axis:** per-cohort table.
- **Composition (§3.7):** `cohort_doctrine_deviation_class` text; `cohort_expectancy_relative_to_aplus_pct` (when both cohorts have n≥5); `cohort_consistency_rate` with CI.
- **Sample-size threshold:** suppress individual cohort row until n≥5; show "n too low" placeholder otherwise.
- **Operator-actionability:** sustained low consistency rate informs `hypothesis_registry.status` mutation toward `closed-escaped`.

### 4.8 Process-grade-trend view (NEW)

- **Primary axis:** rolling-N closed trades (N=10 default).
- **Composition (§3.8):** line chart of `process_grade_rolling_N`; per-stage breakdown lines (entry / management / exit); `disqualifying_violation_rate_rolling_N` separate annotation; `mistake_cost_R_rolling_N_total` paired secondary axis.
- **Sample-size threshold:** suppress rolling line until rolling window has ≥5 effective samples; show point markers per closed trade always.
- **Operator-actionability:** focus-area-of-the-week selection; mistake-tag clustering during weekly/monthly review.

### 4.9 Cross-cutting surface conventions

- **Per-cohort drill is universal.** Trade-process card defaults to per-cohort tabs; "all closed trades" view is a non-default toggle. The other views display all cohorts where applicable.
- **CI rendering is paired with point estimate.** Whenever a CI is computable per §5, it is rendered. Hidden-by-default CI tooltips (per CLAUDE.md JS-test-harness gap awareness) are NOT used; CIs render inline as static text alongside the headline.
- **Reliability flags render as text badges, not color-only.** Color-only signals fail the JS-test-harness gap discipline.
- **No client-side compute.** All metric computations happen server-side in view-models. Surfaces are static-rendered HTML with HTMX OOB-swap refresh; no JavaScript logic on metric values. (Brief watch-item 12 satisfied: no runtime JS dependencies in V1 surfaces.)
- **Operator-witnessed verification gate is BINDING for all new surfaces.** Each Phase 10 surface, on first deploy, requires operator-witnessed browser verification — TestClient passes are necessary but not sufficient (per CLAUDE.md HTMX gotcha catalog). The Phase 10 writing-plans must enumerate this gate per-surface.

---

## 5. Low-sample-size honesty policy (cross-cutting; brief watch-item 2)

A SINGLE policy applies to every metric in §3 and every surface in §4. Three metric classes drive three threshold ladders.

### 5.1 Class A — Rate metrics (proportions)

Applies to: `win_rate`, `loss_rate`, `scratch_rate`, `disqualifying_process_violation_rate`, `aplus_take_rate_per_run`, `cohort_consistency_rate`, `mistake_tag_frequency`, `risk_feasibility_blocked_rate`, etc.

| n | Disposition | Rendering |
|---|---|---|
| n < 3 | Suppress | "n too low (need ≥3)" placeholder; no point estimate |
| 3 ≤ n < 5 | Point-estimate-with-warning | Point estimate rendered; "low confidence (n=3 or 4)" badge inline |
| 5 ≤ n < target_n | Wilson CI | Point estimate + Wilson [lower, upper] at α=0.05 |
| n ≥ target_n | Headline + Wilson CI | Same rendering; warning badge dropped |

`target_n` per cohort = `hypothesis_registry.target_sample_size`. For non-cohort rates (e.g., portfolio-wide `disqualifying_process_violation_rate`): `target_n = 20`.

### 5.2 Class B — Mean / sum-over-fixed-denominator metrics

Applies to: `expectancy_R`, `avg_win_R`, `avg_loss_R`, `MFE_R`, `MAE_R`, `capture_ratio` (mean over winners), `giveback_R_*`, `entry_adverse_slippage_R`, `mistake_cost_R_rolling_N_per_trade`, `holding_period_days` (cohort mean), `cohort_relative_to_aplus`, `cohort_expectancy_with_CI`.

| n | Disposition | Rendering |
|---|---|---|
| n < 3 | Suppress | "n too low (need ≥3)" placeholder |
| 3 ≤ n < 5 | Point-estimate-with-warning | Point estimate rendered; "low confidence (n=3 or 4)" badge |
| 5 ≤ n < 20 | Bootstrap CI (1000 resamples, percentile method, α=0.05) | Point estimate + bootstrap [lower, upper] |
| n ≥ 20 | Headline + bootstrap CI | Same rendering; warning badge dropped |

Bootstrap chosen over normal-approximation because R-distributions are typically heavy-tailed at small n (single-trade R ranges -3 to +5+ R typical), violating normal-approximation assumptions. 1000 resamples is the V1 default; configurable per Phase 9 risk_policy.

### 5.3 Class C — Ratio metrics requiring win-loss diversity

Applies to: `profit_factor`, `payoff_ratio`, `breakeven_win_rate` (deferred per §3.9 but covered for completeness).

| n | Disposition | Rendering |
|---|---|---|
| n < 5 OR <1 win OR <1 loss | Suppress | "Insufficient outcome diversity" placeholder; never +inf or undefined-numeric |
| 5 ≤ n < 20 (with ≥1 win + ≥1 loss) | Point estimate (no CI in V1) | Numeric value; "interpret with caution" badge inline |
| n ≥ 20 (with ≥1 win + ≥1 loss) | Headline | Numeric value; warning badge dropped |

Ratio-CI methods (e.g., Fieller's theorem, log-transform delta method) are V2 deferred — V1 ratio metrics show point estimates above the threshold; suppression is the V1 honesty mechanism.

### 5.4 Class D — Trend / rolling-window metrics

Applies to: `process_grade_rolling_N`, `*_rolling_N` per §3.8, `aplus_funnel_30d_trend`.

| Effective n in window | Disposition | Rendering |
|---|---|---|
| effective_n < 5 | Suppress rolling line; show per-trade points | Line absent; markers visible |
| 5 ≤ effective_n < N | Render rolling line + window-narrowing badge | Line drawn; "rolling window not yet at N" badge |
| effective_n = N | Render rolling line at full N | Standard rendering |

`effective_n` = count of closed trades in the rolling window. Per-trade point markers are always shown regardless of rolling-line state.

### 5.5 Per-pipeline-run metrics special case

Per-run metrics (`aplus_identifications_per_run`, `risk_feasibility_blocked_rate` per run) are rendered as point estimates even at run #1 — the metric is a per-run snapshot, not a sample mean. Multi-run trend lines apply Class A/B policy on the trend-window-n.

### 5.6 Suppression text format

Suppression is rendered as italic placeholder text, not a hidden field. Format: `"[metric_name]: n too low (current: X, need: ≥Y)"`. This makes the suppression an information-bearing surface (operator sees what would unlock the metric). Suppression NEVER renders as an empty cell, "—", or "N/A" — those formats are ambiguous between "computation failed" and "intentionally suppressed."

### 5.7 Coverage cross-check (brief watch-item 2)

Every metric in §3 has a class assignment per §5.1–§5.4. Every surface in §4 inherits the class disposition of its constituent metrics. The hypothesis-progress card §4.2 is the lone exception: it is governance, not metric — it always shows regardless of sample size.

---

## 6. Capture-needs feedback (cross-phase coordination)

The output that makes this brainstorm research-posture rather than schema-locking. Phase 8 + Phase 9 + Phase 10+ brainstorms consume this section; do NOT propose schema here, only capture-cadence + field-name suggestions.

### 6.1 For Phase 8 brainstorm (`daily_management_records`)

Per-snapshot fields the metrics dashboard needs. Cadence: one row per (open_trade_id, NYSE_session_date). Suggested field-name shape (Phase 8 brainstorm to refine):

- `maturity_stage` (enum: `pre_+1.5R` / `+1.5R_to_+2R` / `≥+2R_trail_eligible`) — drives §4.5.
- `trail_MA_eligibility_flag` (boolean) — derived but cached per snapshot for query simplicity.
- `open_MFE_R_to_date` (REAL, R units) — running max of favorable excursion / planned_risk_budget.
- `open_MAE_R_to_date` (REAL, R units) — running min (or abs of min) of adverse excursion.
- `position_capital_utilization_pct` (REAL, proportion) — `current_avg_cost × current_size / capital_floor`.
- `position_portfolio_heat_contribution_dollars` (REAL, $) — `max(0, (current_avg_cost - current_stop) × current_size)`.
- `intraday_high` / `intraday_low` (REAL) — for tomorrow's MFE/MAE compute.
- `data_asof_session` (TEXT, NYSE session date) — anchor.

**Cadence:** one row per (trade_id, session_date) per state ∈ {entered, managing, partial_exited}. Daily snapshot; not intraday. State `closed` → final row freezes at `last_fill_at`'s session.

**Phase 8 capture-need cross-check (brief watch-item 6):** every §3 metric whose `Inputs` column lists `[Phase 8]` is covered. Cross-checked: maturity_stage / trail_MA_eligibility / open_MFE_R / open_MAE_R / position_capital_utilization / position_portfolio_heat_contribution. NO §3 metric requires daily-tier capture not in this list. (Watch-item 6 satisfied.)

### 6.2 For Phase 9 brainstorm (`risk_policy` + `reconciliation_runs`)

Versioning needs for metric-config:

- `scratch_epsilon` (REAL, default 0.10R) — per v1.1-alternate F-014. Per-policy-version row; trade resolves the policy effective at `pre_trade_locked_at`. Without versioning, retroactive scratch_epsilon changes would silently re-classify historical wins/losses.
- `review_lag_threshold_days` (INTEGER, default 7) — per Phase 6 review window default; Phase 9 should externalize to risk_policy.
- `low_sample_size_thresholds_class_a / class_b / class_c / class_d` — per §5 thresholds. If V1 hardcodes them and V2 externalizes, version-stamping is the migration path.
- `bootstrap_resample_count` (INTEGER, default 1000) — per §5.2. Same versioning rationale.
- `process_grade_weights_entry / management / exit` (REAL, currently 0.40 / 0.35 / 0.25 per Phase 6) — Phase 6 hardcodes; Phase 9 risk_policy should externalize for forward-compat.

`reconciliation_runs` discrepancy surface for metrics-data-quality reporting:

- A new dashboard surface (not in §4 V1; future enhancement) consuming `reconciliation_runs` to flag metrics whose underlying data is unreconciled. Phase 9 brainstorm to scope; Phase 10+ writing-plans to incorporate as separate task post-Phase-9 ship.

### 6.3 For Phase 10+ brainstorm (NEW capture beyond Phase 8/9 plans)

Likely capture-needs not in Phase 8/9 scope:

1. **Per-pipeline-run capital-utilization aggregate** (`pipeline_runs_metrics_capital_aggregate`-shaped table OR extend `pipeline_runs` with new columns) — composition: `risk_feasibility_blocked_count` + `aplus_identifications_count` + `watch_identifications_count` + `aplus_taken_count` + `watch_taken_count` + `current_capital_utilization_at_run_start` + `concurrent_open_at_run_start`. Cadence: one row per pipeline_run. Drives §4.4 + §4.6.
2. **Per-pipeline-run identification-vs-trade-funnel snapshot** — covered by item 1's columns.
3. **Benchmark series capture** — currently UNCAPTURED. Two location options surfaced as §8.3 open question (extend `ohlcv_archive` for SPY/QQQ vs new `market_context_daily` table). Required for benchmark-relative metrics (§3.9 deferred).
4. **Corporate-action handling** — currently UNCAPTURED. Defensive (log only, manual reconcile, no automated adjustment) vs deferred (do nothing in V1) is §8.4 open question.
5. **Daily account equity capture** — currently UNCAPTURED. Manual entry vs Schwab API Phase A is §8.2 open question. Required for ALL deferred Class B (Sharpe/Sortino/TWR/cumulative-return-pct) metrics.

### 6.4 What this brainstorm does NOT propose for Phase 8/9 (creep prevention; brief watch-item 10)

- No schema for `daily_management_records` itself — Phase 8 designs that.
- No schema for `risk_policy` versioning — Phase 9 designs that.
- No schema for `reconciliation_runs` — Phase 9 designs that.
- No SQL CREATE TABLE statements anywhere in this spec (validated by self-review §10).

(Watch-item 10 satisfied.)

---

## 7. Mistake-cost formula determination

### 7.1 Decision

**LOCKED:** Affirm Phase 6's already-shipped formula. No code change required.

```
mistake_cost_R   = max(0, realized_R_if_plan_followed - actual_realized_R_effective)
lucky_violation_R = max(0, actual_realized_R_effective - realized_R_if_plan_followed)
```

Source: `swing/trades/review.py:157-174`. v1.1-alternate / v1.2 §8.8 form. Both functions are in code; both are persisted as frozen aggregates on review_log per migration 0013.

### 7.2 Rationale (against brief §1.5 evaluation criteria)

1. **Sold-too-early-winner capture (criterion 1):** YES. When the plan called for holding to a target the operator sold-too-early, `plan_followed_R > actual_realized_R` → `mistake_cost_R > 0` (correct surface). The opposite case (operator held longer than plan and got more) → `lucky_violation_R > 0` (correct symmetric surface).
2. **Operator-actionable signal (criterion 2):** YES. The framework explicitly wants "I left money on the table" as a surfaced cost. Sold-too-early is in the existing mistake_tags vocabulary (`SOLD_TOO_EARLY`); the formula must align.
3. **All outcome cases handled (criterion 3 + brief watch-item 5):**
   - **Stop-violation (operator violated stop):** `realized_R_if_plan_followed = -1.0R` (plan was to stop out at -1R); `actual_realized_R_effective = -1.5R` (worse than plan because operator held past stop). `mistake_cost_R = max(0, -1.0 - (-1.5)) = 0.5R` (correct).
   - **Sold-too-early winner:** `realized_R_if_plan_followed = +2.0R` (plan was to hold to target); `actual = +0.5R` (sold at first pullback). `mistake_cost_R = max(0, 2.0 - 0.5) = 1.5R` (correct).
   - **Plan-followed loss:** `plan_followed_R = -1.0R`; `actual = -1.0R`. `mistake_cost_R = 0` (correct: the loss was the plan).
   - **Plan-followed win:** `plan_followed_R = +2.0R`; `actual = +2.0R`. Both = 0 (correct).
   - **Scratch (|actual| < scratch_epsilon):** `plan_followed_R = +1.5R`; `actual = +0.05R`. `mistake_cost_R = 1.45R` (correct: opportunity cost surfaced even on scratch).
   - **Lucky-bigger-than-plan win:** `plan_followed_R = +1.5R`; `actual = +3.0R`. `mistake_cost_R = 0`; `lucky_violation_R = 1.5R` (correct symmetric surface).
   - **Lucky-violation-converts-loss-to-win:** `plan_followed_R = -1.0R` (operator was supposed to stop out); `actual = +1.0R` (operator violated stop and got lucky). `mistake_cost_R = 0`; `lucky_violation_R = 2.0R` (correct: the lucky outcome flagged).
4. **No netting (criterion 4 + v1.1-alternate §9):** The two metrics are NEVER netted to a single number. Total mistake cost over a window is `sum(mistake_cost_R)`; total lucky violation is `sum(lucky_violation_R)`; both are independently summed and surfaced separately on §4.1 + Phase 6 review_log.
5. **Backward-compat:** ZERO migrations; ZERO code changes. Both functions are already in code and tested.

### 7.3 Code change required

**None.** The brief's premise that Phase 6 ships v1.1-main was a documentation oversight (likely because the v1.1-main mistake-cost text was the most-recently-read material when the brief was authored). The correct v1.1-alternate / v1.2 formula has been in code since Phase 6 ship (commit `51c79ed`).

### 7.4 Open downstream question

Phase 6's review form does NOT currently surface `lucky_violation_R` to the operator at review time — only `mistake_cost_R` derived value is shown. Should the review surface display `lucky_violation_R` symmetrically? Captured as §8.6 open question for orchestrator triage.

---

## 8. Open questions for orchestrator triage

Each unresolved question that requires operator decision before Phase 10 writing-plans dispatch can scope. Question + tradeoff sketch + recommendation + decision-source.

### 8.1 `fills.action` enum gap — `'add'` value

**Question:** Should `fills.action` CHECK constraint widen to include `'add'` for single-trade scale-in tracking?

**Tradeoff:** Adding `'add'` supports v1.1-alternate's pyramiding R-views — but those R-views are DROPPED per §1.3. Not adding leaves the schema unable to distinguish a scale-in from a fresh entry on the same trade (currently both would route through `'entry'`, which is ambiguous). At our $7,500 capital + 5-concurrent-position constraint, scale-ins are effectively impossible (no capital headroom for a second tranche on an open trade), so the gap is theoretical at our cadence.

**Recommendation:** DEFER. Do NOT widen the enum in V1. If/when capital scales past $7,500 and a planned-scale-in trade design emerges, route through V2 schema migration alongside any new pyramiding-related metrics. Decision-source: capital-floor convention in user-memory `project_capital_risk_floor.md`.

### 8.2 Daily account equity capture — manual entry vs Schwab API Phase A

**Question:** Should V1 introduce a manual `account_equity_snapshot` capture surface (CLI + web form) so deferred Class B metrics (Sharpe/Sortino/TWR/cumulative-return-pct) can begin sample accumulation? OR should V1 wait for Schwab API Phase A (per `docs/phase3e-todo.md` 2026-05-04 entry)?

**Tradeoff:** Manual entry gates these metrics on operator daily discipline (high error rate; daily-friction increase). Schwab API Phase A is gated on Schwab Developer Portal production-access approval (days-weeks after submission) and a brainstorm + writing-plans + executing-plans cycle. Net delay = 2-4 weeks minimum. Manual entry could begin tomorrow but is unlikely to survive to the n=12-monthly threshold without dropouts.

**Recommendation:** WAIT for Schwab API Phase A. Sharpe/Sortino at our trade cadence won't meet the n=12-monthly threshold for ~12+ months regardless of when capture begins; the API delay does not bind the metric availability date. Phase 10 writing-plans should NOT include manual-entry surface scope. Decision-source: orchestrator + operator decision; cross-reference Phase 7 cadence post-mortem.

### 8.3 Benchmark series capture location — extend `ohlcv_archive` vs new `market_context_daily`

**Question:** Where should benchmark series (SPY / QQQ / IWM daily OHLCV) live?

**Tradeoff:** Extending `ohlcv_archive` re-uses existing infrastructure but mixes "tickers we trade" with "benchmark tickers we never trade" (semantic muddle; queries become more complex). New `market_context_daily` table is cleaner separation but adds schema surface area. v1.1-alternate proposes the `market_context_daily` route.

**Recommendation:** DEFER until benchmark-relative metrics activate (n≥60 trading days threshold; ≥3 months of post-Phase-10 capture). Per §3.9, those metrics are deferred at our sample anyway. Address in Phase 10+ follow-up brainstorm. Decision-source: rebuttal §3.4 + v1.1-alternate §3.7.

### 8.4 Corporate_Actions MVP — defensive vs deferred

**Question:** Should V1 capture corporate actions (splits / dividends / ticker changes) for open-trade integrity, or defer entirely?

**Tradeoff:** Defensive (log + manual-reconcile) costs minimal effort but adds a manual operator-input surface. Deferred (do nothing) means a split during an open trade silently corrupts MFE/MAE, avg_cost, and quantity_open — a known risk per v1.1-alternate F-019.

**Recommendation:** DEFENSIVE. Log corporate actions to a simple `corporate_actions` table (Phase 10+ scope, NOT this brainstorm); manual reconciliation in operator's daily review; no automated price-adjustment in V1. The capture surface costs ~30 minutes-of-design and prevents a class of silent data-corruption. Phase 10+ writing-plans should incorporate. Decision-source: rebuttal §3.5.

### 8.5 `process_grade_rolling_N` window size — V1 hardcode vs config

**Question:** Should the rolling-N window for §3.8 trend metrics be operator-configurable (`swing.config.toml` `[metrics] process_grade_rolling_window_n = 10`) or hardcoded `N=10`?

**Tradeoff:** Hardcoding is simpler and avoids the §6.2 versioning concern (operator changing N retroactively re-classifies historical aggregates). Config exposes a knob the operator might want to tune.

**Recommendation:** HARDCODE in V1. Externalize to Phase 9 risk_policy versioning later if operator demand emerges. Hardcoded N=10 matches A+ target_sample (20) / 2 — natural granularity. Decision-source: orchestrator preference for configuration restraint at our cadence.

### 8.6 Surface `lucky_violation_R` on Phase 6 review form?

**Question:** Phase 6's review surface displays `mistake_cost_R` derived value but NOT `lucky_violation_R` (per §7.4). Should the V1 review form be updated to surface `lucky_violation_R` symmetrically?

**Tradeoff:** Surfacing both is consistent with the formula's design (§7) and aligns operator's "what happened" view to the data-model. Adds one labeled field to the review form. Could prompt more thoughtful review (operator distinguishes "lucky violation" from "mistake cost" explicitly). Cost: one row in the review template + view-model field + 2-3 tests. Subagent-friendly scope.

**Recommendation:** YES, but as a small standalone follow-up dispatch (not bundled into Phase 10). Trivial executing-plans scope (1-task brief). Decision-source: orchestrator preference.

### 8.7 Hypothesis-cohort decision-criteria automation

**Question:** Should `hypothesis_registry.decision_criteria` text be parsed and auto-evaluated against current cohort metrics, OR rendered as text alongside metrics for operator manual evaluation?

**Tradeoff:** Auto-evaluation requires structured criteria (vs current free-text); parsing risks misinterpretation; manual evaluation defers the operator-discipline question. Currently free-text format: "Mean R-multiple > 0; lower-bound Wilson CI on win rate > 30%" (A+ baseline) — humanly readable, mechanically parsable in principle but fragile.

**Recommendation:** MANUAL. V1 surfaces the text + current metric values side-by-side; operator reads and judges. Auto-evaluation is V2+ scope post-cohort-completion when criteria-format-stability is demonstrated empirically. Decision-source: V2.1 §VII.F source-of-truth correction protocol — auto-evaluation against migration-locked criteria implies the criteria format is itself locked, which it is not yet.

---

## 9. Phasing relationship to 8 / 9 / 10+

Phase 10 design (this spec) is RESEARCH-POSTURE. It defines metric semantics + dashboard surfaces + honesty policy. Implementation is gated on Phase 8 + Phase 9 capture infrastructure. Sequencing:

```
[Phase 8: Daily_Management_Records]
   captures: maturity_stage, open_MFE_R/MAE_R, position_capital_utilization, position_portfolio_heat_contribution
   ↓
[Phase 9: Risk_Policy versioning + Reconciliation_Runs]
   externalizes: scratch_epsilon, review_lag, sample-size thresholds, process_grade_weights
   captures: reconciliation_runs discrepancy surface
   ↓
[Phase 10: Metrics dashboard implementation]
   consumes Phase 8 + Phase 9 capture
   implements §3 metric definitions as view-models
   implements §4 dashboard surfaces as routes + templates
   implements §5 honesty policy as shared utility module
   surfaces §8 open questions' resolutions per locked operator decisions
```

Phase 10 writing-plans (when it eventually runs) will carve §3 + §4 into discrete dispatch tasks per surface; operator-witnessed verification gate per surface.

---

## 10. Self-review checklist (pre-commit)

- [x] **Placeholders:** No "TBD" / "TODO" markers in normative sections.
- [x] **Internal consistency:** §3 inventory matches §4 surface compositions; §5 policy classes cover every §3 metric; §6 capture-needs match every `[Phase 8]` / `[Phase 9]` / `[Phase 10+]` input tag in §3.
- [x] **Scope check:** RESEARCH-POSTURE preserved — no schema (no CREATE TABLE / no ALTER), no code (no Python class definitions / no Jinja), no task decomposition. §6.4 explicit creep-prevention.
- [x] **Ambiguity check:** §5 honesty policy has explicit thresholds + rendering format; no "depends on..." dangling.
- [x] **Brief watch-item coverage:** all 13 watch items addressed:
  - 1 (cohort primary axis): §3 every metric exposes per-cohort; §4.1 default per-cohort.
  - 2 (low-sample-size consistency): §5 covers all §3 metrics + all §4 surfaces.
  - 3 (pre-registration discipline): §3.2 reads tripwire fields from migration-locked source (not Phase 9 mirror).
  - 4 (tier-comparison stat validity): §3.3 + §4.3 require Wilson CI; §4.3 explicit suppression.
  - 5 (mistake-cost formula coverage): §7.2 enumerates 7 outcome cases.
  - 6 (Phase 8 capture completeness): §6.1 cross-checked against §3 `[Phase 8]` tags.
  - 7 (DROP rules applied): §1.3 binding; spot-check no metric depends on Setup_Playbook / pyramiding R-views / self-rated quality / 7-value trade_origin.
  - 8 (v1.1-alternate baseline): §1.3 + §2 vocabulary cite v1.1-alternate; §7 deviation pre-existing in shipped code.
  - 9 (overweighted metrics deprioritized): §3.9 explicit deferral table.
  - 10 (Phase 8/9 coordination): §6.4 explicit creep-prevention.
  - 11 (operator-actionability): §3.10 enumeration table per metric class.
  - 12 (JS-test-harness gap awareness): §4.9 no client-side compute; static-rendered HTML; reliability flags as text not color-only.
  - 13 (capture-needs concreteness): §6.1 + §6.2 + §6.3 list field-name shapes + cadence + rationale.
- [x] **Single commit landing:** spec is the only artifact for this brainstorm session; no rogue commits.
- [x] **Line target:** ~700 lines (within 400-700 range; on the upper end given 13 watch-items + 7 open questions to address).

---

## 11. References

- Brief: `docs/phase10-metrics-brainstorm-brief.md` (commit `3ad5ea2`).
- v1.1-alternate (structural baseline): `reference/Future Work/Metrics/swing_trading_performance_metrics_v1_1_alternate.md`.
- v1.1-main (comparison source): `reference/Future Work/Metrics/swing_trading_performance_metrics_v1_1.md`.
- Findings + rebuttal: `reference/Future Work/Metrics/swing_trading_metrics_v1_1_findings.md` + `swing_trading_metrics_v1_1_rebuttal_determinations.md`.
- Journal v1.2 (upstream): `reference/Future Work/Trading Journal/swing_trading_journal_ai_ingestion_v1.2.md`.
- Hypothesis registry (migration-locked): `swing/data/migrations/0008_hypothesis_registry.sql`.
- Phase 6 review surface (mistake-cost shipped): `swing/data/migrations/0013_phase6_post_trade_review.sql`; `swing/trades/review.py:157-174`.
- Phase 7 state machine + Fills: `swing/data/migrations/0014_phase7_state_machine_and_fills.sql`.
- Orchestrator-context (hypothesis-engine framing): `docs/orchestrator-context.md` 2026-04-25 entries.
- Phase 8/9/10+ backlog: `docs/phase3e-todo.md` (2026-05-04 + 2026-05-05 entries).
- Format reference: `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`.
- Capital-floor convention: `~/.claude/projects/c--Users-rwsmy-swing-trading/memory/project_capital_risk_floor.md`.

---

*End of design spec. Adversarial Codex review pending.*
