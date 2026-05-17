# Phase 13 Scope Brainstorm — Strategic Conversation Doc

**Status:** IN PROGRESS — formal scope development while post-Phase-12 Sub-bundle 1 implementer is in execution. Operator-paced. NOT a dispatch brief; NOT a binding scope LOCK. This doc enumerates candidate categories + dependencies + leverage analysis + discriminating questions to inform the operator-decided Phase 13 scope lock.

**Sequencing:** Phase 13 dispatch is queued AFTER (a) post-Phase-12 Schwab mapper execution-grain widening arc (Sub-bundle 1 + 2) ships; (b) Phase 12.5 4-item bundle ships per `docs/phase3e-todo.md` 2026-05-17 entry. Phase 13 is the **strategic conversation** that re-anchors the next architectural arc; Phase 12.5 is the **tactical closure** that ships the queued V2 candidates from Phase 9/10/12 arc.

**Audience:** Operator + orchestrator. Read this when you (a) want to think about Phase 13 scope; (b) want to challenge any of the enumerated candidate categories; (c) want to add a category I missed.

---

## §0 Context

### §0.1 Project state entering Phase 13 candidate triage

By Phase 13 dispatch time, the following will have shipped:

- **Phase 11 Schwab API integration** (4 sub-bundles A+B+C+D; CLOSED 2026-05-15)
- **Phase 12 Schwab operational depth** (Sub-bundle A operational pain + Sub-bundle B web UI + Sub-bundle C 4 sub-sub-bundles auto-correct reconciliation; CLOSED 2026-05-17)
- **Post-Phase-12 V2 mapper widening** (Sub-bundle 1 + 2; in progress at this doc's drafting; expected ship within days)
- **Phase 12.5 4-item bundle** (OQ-F multi-leg tier-1 auto-redirect + fill auto-population at entry + web Tier-2 surface + CLAUDE.md/orchestrator-context maintenance pass; queued per phase3e-todo 2026-05-17)

This closes the **reconciliation + Schwab integration architectural arc** end-to-end. Phase 13 starts the next arc.

### §0.2 Strategic anchor

Per project CLAUDE.md + V2.1 strategy at `reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md`:

- **Branch B (operational trader-facing)** has been the work focus through Phase 11 + 12. V2.1 §VI priority stack: B1 ranking + B2 trigger explanation + B3 risk support + B4 journaling + B5 dashboarding + B6 UX polish + B7 error/degradation + B8 override/offboarding.
- **Phase 10 metrics dashboard SHIPPED B5.** Phase 11+12 deepened B4 (reconciliation audit trail) + B7 (Schwab degraded UX). B1 + B2 + B3 + B6 + B8 have varying coverage; B8 is **explicitly NOT YET TOUCHED** (per V2.1 §VI.B8 wording).
- **Branch A (research and verification)** at `research/` has Phase 0 tasks in progress (study harness build + earnings-proximity study execution + evidence summary). Operational adoption rules (V2.1 §VI.C) gate promotion of any research-branch method into operational use.

### §0.3 Cumulative V2.1 §VII.F amendments banked

~17 amendments pending operator-paced batch processing across Phase 9 + Phase 10 + Phase 12 + post-Phase-12 arc. These flow through the V2.1 source-of-truth correction protocol; not Phase 13 work directly, but **may benefit from being folded into Phase 12.5 #4 maintenance pass** OR scheduled as Phase 13 housekeeping.

---

## §1 Candidate Phase 13 categories surveyed

For each category: short description + dependencies + V2.1 priority-stack mapping + leverage estimate + operator-fit assessment.

### §1.A — Branch B priority-stack continuation (operational)

#### §1.A.1 B1 polish — Candidate ranking + focus management

V2.1 §VI.B1 "highest near-term value." Phase 1-4 shipped a basic ranking surface; could deepen with:
- Tunable ranking weights (operator-locked vs config-locked)
- Near-miss surfaces explicitly visible in operator workflow
- Stable focus-ordering across pipeline runs (currently subject to fluctuating ATR/RSI/volume calcs)
- Decision-quality feedback loop (Phase 6 review_log already captures; B1 could surface "your reviews favor X over Y; ranking algorithm should know")

**Dependencies:** None blocking. Could ship standalone.
**Leverage:** HIGH. V2.1 names this as "highest near-term value." Direct decision-quality win.
**Operator-fit:** HIGH. Matches "improve daily decisions" framing.
**Estimated scope:** 1-2 sub-bundles; schema potentially v20 (if ranking weights persist as policy-versioned config).

#### §1.A.2 B2 polish — Trigger and setup explanation deepening

V2.1 §VI.B2 wants:
- Exact actionable level (Phase 3+4 ships this; could refine across edge cases)
- Stop basis (Phase 7 + Phase 9 risk_policy LOCKED; coverage is partial)
- Distance-to-trigger + distance-to-stop (Phase 8 daily_management captures; surface could be richer)
- Short narrative explanation (Phase 3e chart pattern hyp-rec; could extend to non-chart-pattern setups)
- Quality flags (Phase 9 risk_policy at-lock-time policy stamp; integrated)

**Dependencies:** None blocking.
**Leverage:** MEDIUM-HIGH. Already partially shipped; deepening adds polish.
**Operator-fit:** HIGH. Matches operator workflow daily friction.
**Estimated scope:** 1 sub-bundle; schema unchanged.

#### §1.A.3 B3 polish — Risk and trade-construction support

V2.1 §VI.B3 wants:
- Risk-budget-aware share suggestions (Phase 5 `compute_shares` + Phase 9 risk_policy ships this)
- Exposure caps + warnings (Phase 9 risk_policy + Phase 10 dashboard ships partial; could deepen)
- Earnings proximity warnings (Phase 3 has `earnings-proximity-exclusion` research study; not promoted yet)
- Gap-risk warnings (NOT YET SHIPPED)
- Better stop-adjustment guidance (Phase 7 + Phase 8 daily_management + Phase 3e.8 advisory bundles cover; could deepen for active-trade reactive stop tightening)

**Dependencies:** Earnings-proximity warning blocks on research-branch Phase 0 study completion (Branch A → Branch B promotion package per V2.1 §VII.A); gap-risk warnings are greenfield.
**Leverage:** MEDIUM-HIGH. Earnings-proximity is research-branch first-promotion candidate; would establish the V2.1 §VII promotion pipeline.
**Operator-fit:** HIGH if research-branch promotion lands; HIGH-MEDIUM if standalone gap-risk only.
**Estimated scope:** 1-2 sub-bundles; depends on whether research-branch promotion folds in.

#### §1.A.4 B8 NEW — Override and offboarding UX

V2.1 §VI.B8 — **NOT YET TOUCHED.** Greenfield. Operator-facing workflow for:
- "I'm exiting this trade manually outside the recommended workflow" (already partial via Phase 7 exit fills; could ergonomize)
- "I want to stop using this strategy / cohort for now" (currently requires CLI policy edits)
- "I'm going on vacation; pause active recommendations for 2 weeks" (NOT YET POSSIBLE)
- "Mark this open trade as 'managing manually'; suppress all advisories" (NOT YET POSSIBLE)
- "Offboard from this entire trading approach for 6 months without losing audit trail" (NOT YET POSSIBLE)

**Dependencies:** None blocking. Operator's pause-state would need new schema (`operator_state` table OR `system_state` row with active/paused/offboarded enum) — potentially schema v20.
**Leverage:** MEDIUM. Not daily-friction-improving like B1; matters when operator is stressed/tired/away.
**Operator-fit:** MEDIUM-HIGH. Operator explicitly cited "I'm going on vacation" + "I'm sick + can't focus + need to pause everything for a week" scenarios in prior conversations.
**Estimated scope:** 1-2 sub-bundles + schema migration.

### §1.B — Research branch activation (Branch A operational)

#### §1.B.1 Earnings-proximity study completion + first promotion package

Per V2.1 §V.D candidate first studies + `research/phase-0-tasks.md`:

- "Next" tasks: build study harness; run study; write evidence summary.
- First study triggers V2.1 §VII promotion pipeline (`method record + implementation sketch + evidence summary + operator-facing explanation + decision recommendation`).
- If accepted → earnings-proximity exclusion ships as Branch B operational advisory (B3-aligned).
- If rejected → Branch A "rejection is a first-class outcome" (V2.1 §VII.D); banks rejection rationale + retains the data + tooling.

**Dependencies:** Operator-paired time-budget allocation; V2.1 §X tranche-1 said 4-8 hours/week total, 70/30 production/research = ~1-2 hours/week on research. Has been DEFERRED through Phase 11+12 because operational arc consumed bandwidth.
**Leverage:** HIGH IF it establishes the promotion pipeline operationally (first promotion = template for all subsequent research → operational hand-offs).
**Operator-fit:** MEDIUM. Requires operator engagement on research-branch posture rather than operational tool usage; competes with operational polish for attention.
**Estimated scope:** 1 standalone sub-bundle on Branch A (study harness + run + evidence summary; ~10-20 hr); 1 sub-bundle on Branch B if promotion accepted (advisory ship; ~5-10 hr).

#### §1.B.2 Second method record + study

Per `research/phase-0-tasks.md` "Later (deferred)": second method record TBD; orchestrator chooses based on first-study outcomes + operator-branch priorities.

**Dependencies:** §1.B.1 first. Sequencing locked.
**Leverage:** Compounds with §1.B.1.
**Estimated scope:** Same shape as §1.B.1.

#### §1.B.3 Reference-methodology completion

V2.1 §VII.F source-of-truth correction protocol routes through `reference/methodology/`. Currently includes:
- `dst-take-profit-and-trail.md` (Disciplined Swing Trader)
- `minervini-sell-side-rules.md` (Minervini SEPA sell-side; note: was MISSING per Sub-bundle C investigation 2026-05-10 but appears to have been added since — verify before locking)
- `minervini-trend-template.md` (Minervini entry criteria)

V2.1 strategy suggests methodology corpus may grow as research-branch studies mature. Candidate additions:
- Realsimpleariel doctrine (Qullamaggie successor; referenced in Phase 3e.8 advisory bundles)
- Bencharris doctrine (Qullamaggie successor; mentioned in commentary KB)
- Volatility-contraction-pattern (VCP) detailed mechanics (Minervini Trend Template references VCP; full mechanics not yet transcribed)
- Pivot point detection mechanics
- Re-entry rules after stop-out (currently operator-improvised; doctrine likely exists in cited works)

**Dependencies:** None blocking; pure docs work; but V2.1 §VII.F routes corrections through this protocol.
**Leverage:** LOW direct; HIGH downstream (methodology corpus underpins V2.1 amendment routing + research-branch method-record citations).
**Operator-fit:** LOW direct (no daily-friction win); HIGH if combined with V2.1 amendment batch (Phase 12.5 #4 maintenance pass candidate).
**Estimated scope:** Standalone docs-only dispatches; sized per methodology source.

### §1.C — Live-trading + intraday integration (architectural)

Currently the project runs on **daily-close cadence** — pipeline reads end-of-day data; operator decides next-session actions during pre-market or evening. Live-trading integration would add:

- Intraday OHLCV cache (currently yfinance + Schwab Market Data API for daily; intraday would need Schwab streaming OR pollable intraday endpoints)
- Intraday trigger detection (chart pattern + trend template + stop violation real-time)
- Pre-market gap detection + advisory
- Real-time degradation detection (operator-facing "Schwab API is down RIGHT NOW")
- Live position monitoring vs scheduled-pipeline review

**Dependencies:** Schwab Market Data API quota assessment (research required); operator-paired session for streaming OAuth setup; large schema impact (intraday tables; cache layer).
**Leverage:** HIGH for active-trading operator workflow; MEDIUM if operator is mostly end-of-day-focused (which has been the project's posture to date).
**Operator-fit:** UNCLEAR — depends on operator's intent to shift to active intraday management.
**Estimated scope:** 3-5 sub-bundles; significant architectural pivot; schema impact.

### §1.D — Tax-lot accounting + cost-basis tracking (operational; greenfield)

Currently the project tracks fills + trades + P/L at portfolio level. Tax-lot accounting (FIFO/LIFO/specific-lot identification + wash-sale rules + holding-period categorization) is COMPLETELY MISSING. Phase 13 could add:

- `tax_lots` table linking fills to cost-basis lots
- Wash-sale rule detection (30-day rule)
- Long-term vs short-term capital gains categorization (>1yr holding)
- 1099-B reconciliation (compare Schwab year-end tax forms to journal)
- Operator-facing year-end tax summary export

**Dependencies:** None blocking (could ship without Schwab integration, but Schwab 1099-B reconciliation is a natural fit); schema v20+ likely required.
**Leverage:** SEASONAL (annual tax season); HIGH then; LOW most of the year.
**Operator-fit:** UNCLEAR — depends on operator's tax-preparation workflow current state. If operator currently exports raw fills to a CPA / tax software, this could replace that with native tracking.
**Estimated scope:** 2-3 sub-bundles; schema impact; cohort-aligned testing.

### §1.E — Backtest framework operationalized in research branch

V2.1 §V research branch currently has Phase 0 study harness scope (synthetic-replay against historical candidates per `research/notes/historical-candidate-source-decision.md` Option B). A full backtest framework would:

- Replay historical candidate data through current SEPA + DST advisory rules
- Measure expectancy + win rate + max drawdown per advisory rule across N-year backtests
- Compare alternative parameter values (e.g., trail-MA period; ADR thresholds; entry-stop ratios)
- Feed back into Branch B operational refinement (V2.1 §VII promotion pipeline)

**Dependencies:** Phase 0 study harness completion (§1.B.1); 2-year historical-candidate data source decision.
**Leverage:** HIGH compounding. Backtest framework is the V2.1 §V research engine; without it, research branch is study-by-study artisanal.
**Operator-fit:** MEDIUM. Operator gets benefit indirectly through improved Branch B rules; direct usage is research-branch-side.
**Estimated scope:** 3-5 sub-bundles on Branch A; significant scope.

### §1.F — Phase 10 metrics dashboard deepening (operational; B5 polish)

Phase 10 shipped 8 metric surfaces + 6 base-layout VMs. Deepening candidates:
- Predictive metrics (current is descriptive; could add expectancy-projection per cohort + winsorized P/L scenarios)
- Cohort-relative-to-A+ ratio in time series (currently snapshot; could trend)
- Process-grade auto-evaluation (Phase 10 §3.7 R1 M4 LOCK is manual-only V1; auto-evaluation against decision-criteria evaluation text could be Phase 13)
- Anomaly detection on reconciliation_runs (pattern-match unusual outcomes like "this run had 5× the normal discrepancy count")
- Per-trade trajectory visualization (entry → reviews → exits as a timeline chart)

**Dependencies:** Mostly consumer-side over Phase 10 schema; no schema impact.
**Leverage:** MEDIUM. Polish on already-shipped surface.
**Operator-fit:** MEDIUM-HIGH. Operator uses Phase 10 dashboard daily; richer metrics improve decision quality.
**Estimated scope:** 1-2 sub-bundles.

### §1.G — Multi-strategy / multi-cohort architectural deepening

Current project supports cohort-based strategy variants (A+ / B / etc.) via Phase 9 hypothesis_status + Phase 10 cohort metrics. Deepening:
- Per-cohort risk policy (currently global)
- Per-cohort capital allocation
- Per-cohort independent state machine
- Cohort-conditional advisory rules

**Dependencies:** Phase 9 risk_policy schema design considered single-cohort V1; widening requires schema work + service-layer refactor.
**Leverage:** MEDIUM. Useful if operator's strategy diversifies; less useful for single-strategy focus.
**Operator-fit:** UNCLEAR — depends on operator's strategic intent.
**Estimated scope:** 2-4 sub-bundles; schema + service-layer pivot.

---

## §2 Candidate Phase 13 scope options

Based on §1 surveying + V2.1 strategic ordering + operator-fit assessment, here are 4 candidate Phase 13 scope options ranging from focused to ambitious:

### §2.A Option A — V2.1 Branch B priority-stack continuation (focused; operational; 2-3 sub-bundles)

**Scope:** §1.A.1 B1 ranking polish + §1.A.2 B2 trigger explanation deepening + §1.A.3 B3 risk support (without research-branch promotion gate; just gap-risk + better stop-adjustment).

**Pros:** Matches V2.1 named-priority ordering verbatim; smaller scope; consumes shipped architecture; high operator-fit (daily-friction improvements).

**Cons:** Doesn't tackle B8 override/offboarding (still NOT YET TOUCHED); doesn't establish V2.1 §VII research-branch promotion pipeline; doesn't address big architectural pivots (intraday; tax-lot; multi-cohort).

**Estimated duration:** 4-6 weeks operator-paced.

### §2.B Option B — Research-branch activation + first promotion (V2.1 §V + §VII pipeline establishment; 3-4 sub-bundles)

**Scope:** §1.B.1 earnings-proximity study completion + first promotion package + §1.B.2 second method record (TBD; orchestrator-chosen based on first-study outcomes) + V2.1 §VII promotion pipeline operationalized.

**Pros:** Activates Branch A operationally; establishes promotion-pipeline template; rejection-as-first-class-outcome practice. V2.1 §V "near-term" framing.

**Cons:** Slower wall-clock per V2.1 §X 1-2 hours/week research budget; not direct daily-friction improvement; may compete with operational polish for operator attention.

**Estimated duration:** 8-12 weeks operator-paced.

### §2.C Option C — B8 override/offboarding UX + Phase 10 deepening (operational; 2-3 sub-bundles)

**Scope:** §1.A.4 B8 override/offboarding (operator-paused state + manual-management flag + offboarding workflow) + §1.F Phase 10 metrics dashboard deepening (predictive metrics + process-grade auto-evaluation).

**Pros:** Closes B8 (last V2.1 §VI priority-stack item NOT YET TOUCHED); deepens Phase 10's daily-review surface; bounded scope; schema impact contained to B8.

**Cons:** Doesn't tackle research-branch activation; doesn't tackle big architectural pivots.

**Estimated duration:** 5-7 weeks operator-paced.

### §2.D Option D — Architectural pivot (intraday OR tax-lot OR multi-cohort; 3-5 sub-bundles)

**Scope:** Pick ONE of §1.C intraday integration / §1.D tax-lot accounting / §1.G multi-strategy deepening.

**Pros:** Major architectural progress on a deferred dimension; opens new operational capability.

**Cons:** Significant scope + schema impact + operator-paired-session-heavy + risk of consuming bandwidth that could fix daily friction first.

**Estimated duration:** 10-16 weeks operator-paced.

---

## §3 Discriminating questions for operator triage

To lock Phase 13 scope, the operator + orchestrator conversation should resolve:

1. **What's the operator's actual workflow pain entering Phase 13?** Is it (a) daily decision-making friction (favors §2.A or §2.C); (b) "I want the tool to learn / refine itself" (favors §2.B research-branch); (c) "I need a new capability the tool doesn't have today" (favors §2.D pivot)?

2. **What's the operator's strategic intent over the next 6 months?** Is it (a) deepening existing SEPA+DST single-strategy workflow (favors §2.A or §2.C); (b) evaluating other strategies / cohorts (favors §1.G multi-strategy in §2.D); (c) intraday/active management (favors §1.C intraday in §2.D); (d) tax-year preparation (favors §1.D tax-lot in §2.D)?

3. **What's the operator's research-vs-operational time-budget split going forward?** V2.1 §X said 70/30 production/research; if research-branch promotion never lands, the 30% is dead weight. Phase 13 is a natural triage point: ACTIVATE research-branch (favors §2.B) OR re-allocate 100% to operational (favors §2.A or §2.C).

4. **What's the operator's appetite for schema work in Phase 13?** §2.A is mostly consumer-side; §2.C requires schema v20 for B8; §2.D requires significant schema impact. Phase 11+12+post-12 has done a lot of schema work; operator may want a schema-light phase next.

5. **Has the operator's mental model of the tool's "completeness" changed entering Phase 13?** If Phase 12.5 closes feel like "the tool now does everything I need daily," Phase 13 may pivot research/strategic (§2.B). If it feels "still has friction," Phase 13 stays operational (§2.A/§2.C).

6. **Should Phase 13 fold in V2.1 §VII.F amendment batch processing?** ~17 cumulative amendments pending. Phase 12.5 #4 maintenance pass is the natural fold-in candidate; if scheduled there, Phase 13 doesn't need to.

---

## §4 Recommendation (orchestrator-side; operator overrides)

**Tentative recommendation: Option A (V2.1 Branch B priority-stack continuation) with research-branch-activation TIME-BOXED as a sidecar.**

Rationale:
- V2.1 §VI explicitly ordered B1-B8 by leverage; not advancing through the stack systematically loses the strategic anchor.
- B1 + B2 + B3 + B8 cumulative coverage closes Branch B priority-stack near-completely (B6+B7 already have partial coverage from polish bundles + Phase 11/12 degradation UX).
- Time-boxing research-branch activation (e.g., 1 study completion or 1 promotion package per Phase 13 quarter) preserves V2.1 §X 70/30 split without consuming Phase 13 bandwidth.
- Schema-light Phase 13 lets the next architectural pivot (intraday OR tax-lot OR multi-cohort) be Phase 14 with full bandwidth.

But this is orchestrator-tentative; the operator's answers to §3 questions should lock the actual scope.

---

## §5 Out of scope for this doc (not Phase 13 candidates)

- **Phase 12.5 4-item bundle** — separately banked per phase3e-todo 2026-05-17; sequenced BEFORE Phase 13.
- **V2.1 §VII.F amendment batch processing** — operationally folded into Phase 12.5 #4 maintenance pass OR Phase 13 housekeeping; not standalone Phase 13 scope.
- **Operational maintenance items** (refresh-token re-auth; husk cleanup; editable install recovery) — ongoing operator-action; not a Phase.
- **Sub-bundle 1 + 2 close-out housekeeping** — orchestrator-side after each sub-bundle ships.
- **CLAUDE.md status-line + orchestrator-context.md archive splits** — folded into Phase 12.5 #4 maintenance pass.

---

## §6 Next steps

1. **Operator reviews this doc** at convenience (sometime after Sub-bundle 1 implementer returns OR async).
2. **Operator + orchestrator discuss §3 discriminating questions** to lock Phase 13 scope.
3. **Orchestrator drafts Phase 13 brainstorm dispatch brief** once scope is operator-locked (mirrors `docs/post-phase12-schwab-mapper-execution-grain-widening-brainstorm-dispatch-brief.md` structure).
4. **Phase 13 brainstorm → writing-plans → executing-plans** standard 3-phase dispatch chain.

---

*End of Phase 13 scope-brainstorm doc. Operator-paced. Re-anchor as needed when Sub-bundle 1+2 ships expose new constraints OR when Phase 12.5 dispatches change the strategic context.*
