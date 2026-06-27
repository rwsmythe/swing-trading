# Phase 10 Metrics Design Brainstorm — Implementer Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 10 metrics-design brainstorm implementer. No prior conversation context.

**Mission:** Produce a metrics-framework design spec for the Swing Trading project's Phase 10 metrics dashboard roll-out. The brainstorm is **RESEARCH-POSTURE** — design-lock metric definitions + dashboard surface sketches + low-sample-size honesty policy, but do NOT lock schema. Schema decisions are deferred to Phase 10 writing-plans, AFTER Phases 8 + 9 ship the underlying capture infrastructure. Capture-need feedback the brainstorm surfaces will inform the upcoming Phase 8 + Phase 9 brainstorms.

**Expected duration:** 90–180 minutes including 3–5 adversarial Codex rounds. The framework-evaluation metric layer is largely NEW DESIGN with no doc baseline; expect Codex rounds to catch low-sample-size honesty + per-cohort statistical-validity issues.

**Sequencing context:** Phase 10 brainstorm runs FIRST (research-only); Phase 8 brainstorm follows + consumes this spec's §2.4 capture-needs feedback; Phase 9 brainstorm follows Phase 8; execution order is 8 → 9 → 10. No ship-velocity pressure; operator confirmed n=2 closed / n=3 open trades (5 total) means metric stability is the binding constraint.

---

## §0 Read first

In this order:

1. **`CLAUDE.md`** at repo root — project conventions + gotchas.
2. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Recent decisions and framings" (especially all 2026-04-25 hypothesis-engine entries) + "Lessons captured."
3. **`docs/phase3e-todo.md`** sections "2026-05-01 Journal v1.2 incorporation" + "2026-05-04 Schwab API integration" + "2026-05-05 Sector/industry tamper hardening" + "2026-05-04 Future schema migration: trade.entry_date datetime promotion" + "2026-05-05 Fill.quantity fractional-share forward-compat."
4. **`reference/Future Work/Metrics/swing_trading_metrics_v1_1_findings.md`** + **`swing_trading_metrics_v1_1_rebuttal_determinations.md`** — design-evolution + arbitration docs. Read these BEFORE the long specs to orient on what was settled.
5. **`reference/Future Work/Metrics/swing_trading_performance_metrics_v1_1.md`** + **`swing_trading_performance_metrics_v1_1_alternate.md`** — the two competing v1.1 designs. Per rebuttal + orchestrator-thread analysis: **v1.1-alternate is the structural baseline.**
6. **`reference/Future Work/Trading Journal/swing_trading_journal_ai_ingestion_v1.2.md`** — upstream journal spec; metrics docs are downstream.
7. **`swing/data/migrations/0013_phase6_post_trade_review.sql`** + **`swing/data/migrations/0014_phase7_state_machine_and_fills.sql`** — already-shipped Phase 6 + Phase 7 schema. Don't propose anything that conflicts.
8. **One prior brainstorm spec for format reference** — `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md` (`081f689`). Mirror its section-numbered + lock-decisions-vs-open-questions structure.

---

## §0 Skill posture

- Invoke **`copowers:brainstorming`** (which wraps `superpowers:brainstorming` with adversarial Codex review). Iterate to `NO_NEW_CRITICAL_MAJOR`.
- DO NOT invoke `superpowers:writing-plans` — schema-locking is out of scope (see §3).
- DO NOT invoke `superpowers:executing-plans` — design-only.
- DO NOT invoke `superpowers:test-driven-development` — no code changes.
- DO NOT invoke `superpowers:using-git-worktrees` — no code changes; spec doc commit only.

---

## §1 Strategic context (ORCHESTRATOR-DISTILLED — what's NOT in the docs)

The metrics docs were authored without project-specific context. Orchestrator-thread analysis surfaced significant framework-fit gaps. Treat the following as **BINDING design constraints** — they are not derivable from the metrics docs alone.

### §1.1 Distinguishing characteristics of our trading plan

1. **Framework-research-loop posture (NOT discretionary).** Pipeline asserts thesis via bucket + criteria + hypothesis_label. Pre-trade quality is computed by pipeline, not self-rated by operator.
2. **Hypothesis-driven trade attribution.** 4 pre-registered hypotheses (migration 0008): A+ baseline (target n=20); Near-A+ defensible-extension (n=10); Sub-A+ VCP-not-formed (n=5); Capital-blocked smaller-position (n=10). Each carries armed tripwires (consecutive-loss-N + cumulative-R-percent). Pre-registration is binding — `target_sample`, `tripwire_*`, `decision_criteria` are migration-locked; only `status` is CLI-mutable.
3. **Capital tie-up = primary constraint** (NOT identification rate). $7,500 capital floor for sizing population (~$1,300 actual); ~50-trade/year ceiling at full deployment (5 concurrent × ~14% per position × ~10 cycles/year).
4. **Sample size: n=2 closed, n=3 open (5 total) as of 2026-05-06.** Any time-series or distributional metric will be noise for years.
5. **Sub-A+ trade-taking IS doctrine deviation by design.** 2026-04-25 framing: operational branch as evidence-generation surface; hypothesis-tagged sub-optimal trades within risk discipline; losses are cost-of-development, not investment loss.
6. **Capital-utilization vs identification-rate divergence.** A+ identifications ≠ trades; identification rate ~40-100/year on Finviz pool, but capital ceiling caps trade-take at ~50/year.

### §1.2 What our plan needs to measure (categories beyond what docs propose)

**THE PRIMARY AXIS: `hypothesis_label` as first-class aggregation dimension**, not a filter tag. Standard "expectancy = +0.4R" averaged across A+ + watch + sub-A+ tests is meaningless to our framework. EVERY trade-process metric MUST be presentable per-cohort.

Categories the metrics docs MISS or weakly address (these are the framework-specific NEW design surface):

- **Per-hypothesis cohort performance** — expectancy / win-rate / MFE-MAE / process-grade BY `hypothesis_label`.
- **Pre-registration adherence** — distance-to-tripwire (consecutive-loss + cumulative-R); sample-size progression rate; decision-criteria evaluation cadence per hypothesis.
- **Tier-comparison framework signal** — A+ vs watch vs skip cohort outcome distributions over enough samples to test classification quality.
- **Capital-feasibility friction** — % of A+ candidates blocked by `risk_feasibility` per pipeline run; current capital utilization; capital-cycle time over closed cohort.
- **Trade-maturity stage tracking** — open-trade MFE vs +1.5R / +2R thresholds (Tier-3 #6 trail-MA gating; operationally urgent for currently-open positions).
- **Identification ≠ trade rate divergence** — A+ identifications vs A+ trades-taken; multi-run trend.
- **Deviation-class outcome aggregation** — per-`hypothesis_label` cohort: deviation class vs Minervini doctrine; sample expectancy; relative-to-A+ comparison.
- **Process-grade trend over time** — Phase 6 ships point-in-time grade; trend over rolling-N closed trades is the actionable surface.

### §1.3 Metrics overweighted at our sample size (DEPRIORITIZE)

These are present in the docs but produce noise/misleading output at n<20:

- **Sharpe / Sortino** — needs ≥12 monthly returns; we'll be at 5–15 closed trades total in 12 months. DEFER until n threshold met.
- **Time-weighted return / cumulative return** — depend on daily equity capture (heavyweight). Total realized P&L is the clean metric at our cadence. DEFER.
- **Benchmark-relative excess return** — sample size too small to be defensible. DEFER.
- **Drawdown-pct (equity curve)** — at 5-concurrent-position max + n<20, max-drawdown-R over closed trades is more interpretable. PREFER R-drawdown; DEFER equity-curve-pct.
- **Recovery factor / breakeven win rate** — useful at scale; at our sample, noise. DEFER.
- **Profit factor** — show but flag low-confidence at n<20.

### §1.4 Apply existing v1.2 DROP rules

Both metrics designs include elements that should DROP per existing journal-incorporation policy in `docs/phase3e-todo.md` "2026-05-01 Journal v1.2 incorporation":

- **Setup_Playbook as DB entity** — DROP. Our setups are encoded in `swing/evaluation/scoring.py` + `criteria.py`; map to `hypothesis_id` instead.
- **Pyramiding R-views (R_initial / R_effective / R_campaign)** — DROP. Operator at $7,500 capital, 5 concurrent, no pyramiding plan. Collapse v1.1-alternate's triple risk denominators to single `planned_risk_budget_dollars`.
- **Self-rated `pre_trade_quality_score` (0-10)** — DROP. Pipeline classification surfaces this.
- **`UNPLANNED_ADD` mistake tag + `risk_added_after_initial_R`** — DROP per pyramiding rule.
- **v1.2's 7-value `trade_origin`** — REPLACE with our 4-value pipeline-aware enum (`pipeline_aplus`, `pipeline_watch_hyp_recs`, `pipeline_watch_manual`, `manual_off_pipeline`).
- **Drawdown circuit breaker default** — align with v1.2: opt-in disabled.

### §1.5 Mistake-cost formula triage (orchestrator-flagged for brainstorm decision)

Phase 6 SHIPPED `realized_R_if_plan_followed` storage with derive-on-read using **v1.1-main's formula**:

```
mistake_cost_R = max(0, abs(realized_R) - plan_followed_R)
```

v1.1-alternate uses:

```
mistake_cost_R = max(0, plan_followed_R - actual_realized_R)
```

The alternate formula **also catches sold-too-early winners** as `lucky_violation_R` (positive value when plan-followed return would have exceeded actual return). Phase 6's formula does not.

**Backward-compat:** Phase 6 derives cost on read (not stored), so changing formula is a one-line code change with re-derivation across all reviewed trades. No migration required.

**Brainstorm decision required:** lock ONE formula + present rationale. Per Codex round, evaluate:

1. Does the alternate's formula correctly capture sold-too-early as a process-violation surface?
2. Does it produce the right operator-actionable signal for our framework (i.e., does the operator want "I left money on the table" surfaced as a mistake cost)?
3. Does the unification preserve Phase 6's semantics for over-stop-violation + under-target-exit + scratch cases?
4. Output: locked formula + 1-line code-change identification + flag for operator triage if formula change is non-obvious.

---

## §2 Brainstorm scope (in scope)

Produce a design spec at `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md` covering:

### §2.1 — Metric inventory (per-metric DEFINITIONS, not schema)

For each proposed metric:

- **Definition** — formula in plain English + R-or-$-or-pct unit.
- **Inputs** — what fields it consumes from already-shipped Phase 6/7 vs queued Phase 8/9 vs new Phase 10+ capture.
- **Aggregation** — per-trade / per-hypothesis-cohort / per-tier / per-pipeline-run / per-day.
- **Low-sample-size honesty policy** — when to suppress, show with CI, point-estimate-with-warning (per §2.3).

Lean toward **v1.1-alternate as structural baseline** per rebuttal recommendation; deviate only where §1.4 DROP rules or §1.2 framework-fit gaps require.

Categories the inventory must cover:
- Trade-process metrics (closed-trade R; expectancy; profit factor; payoff ratio; slippage_R; mistake_cost_R; lucky_violation_R; process_grade aggregates).
- Per-hypothesis cohort metrics (per-hypothesis expectancy; sample-progression rate; tripwire-distance; status-change history).
- Tier-comparison metrics (A+ vs watch vs skip outcome distributions; classification-quality test).
- Capital-friction metrics (risk_feasibility blocking rate; capital-utilization; capital-cycle time).
- Maturity-stage metrics (open-trade MFE-vs-threshold; trail-MA-eligibility flags).
- Identification-vs-trade-funnel metrics (per-pipeline-run + multi-run trend).
- Deviation-outcome metrics (per-`hypothesis_label` cohort + relative-to-A+ comparison).
- Process-grade-trend metrics (rolling-N closed trades).

### §2.2 — Dashboard surface sketches (NOT HTML/code)

For each surface:

- **Name** + **primary axis** (hypothesis-cohort / per-trade / per-pipeline-run / per-day).
- **Composition** — which metrics from §2.1.
- **Sample-size threshold** for showing.
- **Operator-actionability test** — what action does the operator take based on this surface? (See §5 watch item 11.)

Surfaces likely needed (extend or refine — not exhaustive):
- Trade-process card.
- Hypothesis-progress card (Phase 4.5 already partly shipped; extend).
- Tier-comparison view (NEW).
- Capital-friction view (NEW).
- Maturity-stage view (NEW).
- Identification-vs-trade-funnel view (NEW).
- Deviation-outcome view (NEW).
- Process-grade-trend view (NEW).

### §2.3 — Low-sample-size honesty policy (cross-cutting)

Define a single policy that applies consistently across §2.1 + §2.2. Suggested structure (refine per Codex):

- **Suppress** ("n too low" placeholder) below some threshold (e.g., n<3).
- **Point-estimate-with-warning** at low n (e.g., 3 ≤ n < 5).
- **Wilson CI / proper CI** at moderate n (e.g., 5 ≤ n < 20).
- **Headline-without-CI** at high n (e.g., n ≥ 20).

Thresholds are illustrative; brainstorm picks defensible values per metric type (rate vs ratio vs mean).

### §2.4 — Capture-needs feedback for Phase 8 + Phase 9 brainstorms

The cross-phase coordination output. This is what makes the brainstorm research-posture rather than schema-locking. Enumerate:

1. **For Phase 8 (`daily_management_records`)** — per-snapshot fields the metrics dashboard needs (likely candidates: maturity-stage classification; trail-MA-eligibility flag; open-position MFE/MAE-to-date; per-position capital-utilization; per-position portfolio-heat-contribution).
2. **For Phase 9 (`risk_policy` + `reconciliation_runs`)** — versioning needs for metric-config storage (`scratch_epsilon`; `review_lag_threshold_days`; classification-quality CIs threshold); reconciliation-discrepancy surface for metrics-data-quality reporting.
3. **For Phase 10+ (NEW capture beyond Phase 8/9 plans)** — likely candidates: per-pipeline-run capital-utilization aggregate + risk_feasibility-blocked count; per-pipeline-run identification-vs-trade-funnel snapshot; benchmark series capture (location TBD); corporate-action handling (defensive vs deferred).

Each capture-need should be specific enough that Phase 8/9 brainstorms can pick it up without re-deriving (concrete field-name suggestions; concrete capture-cadence suggestions).

### §2.5 — Mistake-cost formula triage decision

Per §1.5. Lock ONE formula + rationale + flag code-change location.

### §2.6 — Open questions for orchestrator triage

Each unresolved question that would require operator decision before writing-plans dispatch can scope. Per orchestrator-context conventions: question + tradeoff sketch + your recommendation + which decision-source the operator needs to consult.

Likely categories for open questions (subagent-flagged in orchestrator triage):
- `fills.action` enum gap — `'add'` value not in migration 0014's CHECK; widen for single-trade-scale-in tracking?
- Daily account equity capture — manual entry vs wait for Schwab API Phase A.
- Benchmark series capture location — extend `ohlcv_archive` vs new `market_context_daily`.
- Corporate_Actions MVP — defensive build vs deferred.
- `scratch_epsilon` + `review_lag_threshold_days` — interim `swing.config.toml` vs wait for Phase 9.

---

## §3 OUT OF SCOPE (do not do)

- **Schema design** — table layouts, columns, CHECK constraints, FK relationships, indexes. That's writing-plans territory AFTER Phase 8/9 ship.
- **Code drafting** — view-model classes, query implementations, Jinja templates, route handlers.
- **Phase 10 task-decomposition into dispatches** — also writing-plans output.
- **Re-litigating decisions in §1** — DROP rules + framework-fit gap analysis are settled. Mistake-cost-formula is the ONE design decision opened to brainstorm.
- **Re-deriving framework-fit gap analysis** — accept §1 as given.
- **Designing for hypothesis-registry mutation** — pre-registration discipline is binding (formal migration only).
- **Designing for fractional shares** — see `docs/phase3e-todo.md` "2026-05-05 Fill.quantity fractional-share forward-compat" entry; gated on Schwab API Phase B.

---

## §4 Binding conventions

- **Branch:** `main`. Single commit for spec landing (no rogue commits; brainstorm session has no other artifacts).
- **Commit message:** `docs(metrics): Phase 10 metrics-design brainstorm spec`. No Claude co-author footer. No `--no-verify`. No amending.
- **Spec format:** mirror `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`. Section-numbered; locked decisions called out explicitly with rationale; open questions enumerated for orchestrator triage.
- **Spec line target:** ~400–700 lines. Tight is better than padded; if exceeding 700, re-scope.
- **Adversarial review:** mandatory; iterate to `NO_NEW_CRITICAL_MAJOR`.

---

## §5 Adversarial review watch items

For Codex rounds — pass these as targeted prompts to `copowers:adversarial-critic`:

1. **Hypothesis-cohort as primary axis discipline.** Does every trade-process metric in §2.1 expose a per-hypothesis aggregation? If any treats hypothesis as optional filter, justify or fix.
2. **Low-sample-size honesty consistency.** Does §2.3 policy actually apply across all §2.1 metrics + §2.2 surfaces? Look for metrics that ignore the policy or surfaces that show low-n point estimates without CI/warning.
3. **Pre-registration discipline preserved.** Tripwire-distance + sample-size-progression metrics computed against migration-locked values, not editable cfg fields.
4. **Tier-comparison statistical validity.** Does the tier-comparison view (§2.2) propose A+ vs watch vs skip outcome distributions WITH appropriate Wilson CIs + sample-size warnings + suppression-when-too-low? Or does it just present point estimates inviting overinterpretation?
5. **Mistake-cost formula coverage.** Does the locked formula (§2.5) correctly handle ALL outcome cases: stop-violation, sold-too-early-winner, plan-followed-loss, plan-followed-win, scratch trades?
6. **Capture-needs completeness for Phase 8.** Does §2.4 enumerate ALL capture needs the dashboard requires? Cross-check by reading `daily_management_records` scope from `docs/phase3e-todo.md` Phase 8 entry — flag any §2.1 metric that needs daily-tier capture not currently in Phase 8 scope.
7. **DROP rules applied.** No metric in §2.1 depends on Setup_Playbook-as-DB, pyramiding, self-rated quality, or 7-value `trade_origin` enum.
8. **v1.1-alternate baseline.** Where the spec borrows from metrics docs, does it cite v1.1-alternate (not v1.1-main) as default? Exceptions explicitly justified?
9. **Overweighted-at-sample metrics deprioritized.** Sharpe/Sortino/TWR/equity-curve-drawdown/recovery-factor/breakeven-win-rate either DROPPED or marked "deferred until n>=N" with explicit per-metric threshold.
10. **Phase 8/9 capture coordination.** Does §2.4 surface capture needs in time for Phase 8/9 brainstorms to consume? Or does it propose schema changes that should be Phase 8/9-internal scope (creep)?
11. **Operator-actionability test.** For each metric in §2.1: "what action does the operator take based on this metric reading X vs Y?" If no action emerges, deprecate as "monitoring-only" or DROP.
12. **JS-test-harness gap awareness.** §2.2 dashboard surfaces don't propose runtime-JS dependencies that would surface a JS-test-harness-gap regression (per existing CLAUDE.md gotcha + lesson 2026-04-25 Bug 1).
13. **Capture-needs concreteness.** §2.4 feedback is specific enough that Phase 8 brainstorm can pick it up without re-deriving — concrete field-name suggestions where applicable; concrete capture-cadence suggestions.

---

## §6 Done criteria

1. Spec at `docs/superpowers/specs/2026-05-06-phase10-metrics-design.md` covering §2.1–§2.6.
2. Brainstorm went through ≥3 Codex rounds reaching `NO_NEW_CRITICAL_MAJOR`.
3. Spec section structure mirrors prior brainstorm spec format; lock-decisions vs open-questions explicitly delimited.
4. Single commit landed: `docs(metrics): Phase 10 metrics-design brainstorm spec`.
5. Return report covers items in §7.

---

## §7 Return report format

```
## Return report — Phase 10 metrics-design brainstorm

### Spec location
`docs/superpowers/specs/2026-05-06-phase10-metrics-design.md` ({line count} lines)
Commit: {sha} `docs(metrics): Phase 10 metrics-design brainstorm spec`

### Codex review history
- R1: {C/M/m findings; verdict; FIXED/ACCEPTED counts}
- R2: ...
- ...
- Final verdict: NO_NEW_CRITICAL_MAJOR

### Three highest-leverage design decisions
1. ...
2. ...
3. ...

### Mistake-cost formula decision
Locked formula: `...`
Rationale: ...
Code change required: 1-line in `swing/trades/review.py:_compute_mistake_cost` (or wherever; identify location). Estimated effort: trivial.

### Open questions for orchestrator triage
1. ...
2. ...

### Capture-needs feedback FOR PHASE 8 BRAINSTORM
- ...

### Capture-needs feedback FOR PHASE 9 BRAINSTORM
- ...

### Capture-needs FOR PHASE 10+ (beyond Phase 8/9 plans)
- ...
```

---

## §8 If you get stuck

- If §1 strategic-context constraints conflict with what v1.1-alternate proposes, §1 wins.
- If a Codex round produces a finding you can't disposition without operator input, ACCEPT-with-rationale + flag explicitly in spec's "open questions" section + return report.
- If the spec exceeds ~700 lines, you're probably over-designing — re-scope.
- DO NOT propose schema. DO NOT write code. If you start drafting `CREATE TABLE ...` or `class FooVM`, stop.
- If you encounter the JS-test-harness gap pattern in dashboard sketches (real browser behavior unverifiable via TestClient), flag in the spec for operator-witnessed verification gate during Phase 10 execution — don't try to resolve here.
