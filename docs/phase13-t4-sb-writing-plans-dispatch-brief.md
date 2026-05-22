# Phase 13 T4.SB — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the T4.SB writing-plans implementer. No prior conversation context.

**Mission:** Produce an implementation plan that decomposes the T4.SB 6-task scope (T-T4.SB.1..T-T4.SB.6) per the operator-confirmed brainstorming spec + 18 OQ dispositions (ALL locked per operator triage 2026-05-22 PM #2) + 4 §1.5 amendments (parameter-sweep sensitivity diagnostic + research-branch placement + Option A re-run collision + OQ-CL.2 deferred disposition).

**Brainstorming spec (BINDING substrate):** [`docs/superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md`](superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md) at main HEAD `f7dec0e` (1045 lines; 13 sections §A-§M; Codex R5 NO_NEW_CRITICAL_MAJOR; 17 MAJOR all RESOLVED). **READ END-TO-END.**

**Brief:** `docs/phase13-t4-sb-writing-plans-dispatch-brief.md` (this file).

**Sequencing:** T4.SB brainstorming SHIPPED 2026-05-22 PM #2 at `4299340` + housekeeping at `f7dec0e` + this brief commit. Output feeds the executing-plans dispatch (6 sub-bundles T-T4.SB.1..T-T4.SB.6).

**Branch:** `phase13-t4-sb-writing-plans` — branches from main HEAD after this brief lands.

**Worktree:** `git worktree add .worktrees/phase13-t4-sb-writing-plans phase13-t4-sb-writing-plans`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Workflow:** `copowers:writing-plans` skill (wraps `superpowers:writing-plans` with adversarial Codex MCP review). Expected 2-5 Codex rounds.

**Expected duration:** ~3-6 hours operator-paced. Plan target: ~1000-1500 lines (T2.SB6c writing-plans plan was 1820 lines; T4.SB scope is wider but per-task simpler so probably ~1200 lines).

---

## §0 Read first (in this order)

1. **`docs/superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md`** at HEAD `f7dec0e` — PRIMARY SUBSTRATE. 13 sections §A-§M. Especially:
   - §A status + scope (7 operator-confirmed triage items)
   - §B per-item investigation + design (Items 1-7 with code surfaces + decisions)
   - §C cross-item couplings
   - §D investigation outputs format
   - §E cross-bundle pin row 13 (4-surface parametrize)
   - §F test scope projection
   - §G sub-bundle decomposition T-T4.SB.1..T-T4.SB.6 (BINDING for this plan's task structure)
   - §H dispatch sequence
   - §I forward-binding lessons inherited
   - §J 18 OQs (now ALL operator-triaged per §1 below)
   - §K Phase 13 closure marker
   - §L references
   - §M closing notes

2. **`docs/phase3e-todo.md` T4.SB triage items (lines 11-101)** — 7 items with operator-confirmed severity + verbatim framing.

3. **`docs/phase13-t4-sb-brainstorm-return-report.md`** — Codex chain shape; 14 V1 simplifications banked; 6 forward-binding lessons; NEW Expansion #10 candidate banking.

4. **`docs/phase13-t4-sb-brainstorming-dispatch-brief.md`** at `e75f743` — predecessor brief that drove the brainstorming dispatch (reference-only; supplanted by spec).

5. **`CLAUDE.md`** at repo root — project conventions + 14 cumulative gotchas. ESPECIALLY relevant for T4.SB writing-plans phase:
   - **Architecture-location audit + 4 sub-disciplines (NEW Expansion #10 candidate BINDING)** — banked at T4.SB brainstorming 2026-05-22 PM #2. 5 sub-disciplines: (a) wrong-module helper placement; (b) template-vs-VM-parser-vs-emitter triangulation; (c) cache-key + renderer-kwargs uniformity LOCK; (d) SQL LIKE wildcard-escape + raw-vs-escaped binding-param asymmetry; (e) orphan-label preservation under refactor.
   - **Form-render anchor lifecycle audit (Expansion #9 candidate BINDING)** — T2.SB6c executing-plans banking
   - **SQL aggregation UNIT audit (Expansion #8 candidate BINDING)** — T2.SB6c writing-plans banking
   - **Brief-vs-actual schema reality check + SQL skeleton column verification (Expansion #4 refinement BINDING)** — T2.SB6c brainstorming banking
   - **Grouping-key canonicalization-at-persistence-boundary** — DIRECTLY APPLIES to Item 7 fix
   - **HTMX OOB-swap partials hand-duplicate full-page markup drift** — DIRECTLY APPLIES to Item 6
   - **Matplotlib mathtext fires on `$`/`^`/`_`/unbalanced `\`** — applies to Item 3 chart-rendering work
   - **F6 transient-empty defense at construction barrier** — applies to Item 5 cache-renderer work
   - **§A.14 paired discipline** — T4.SB SHOULD NOT touch schema (per brainstorming spec); BUT if any retention-policy table is proposed, §A.14 applies

6. **`docs/orchestrator-context.md`** "Currently in-flight work" — current state reflects T4.SB brainstorming SHIPPED + 18-OQ triage complete.

7. **`research/phase-0-tasks.md`** "Later (deferred)" — A+-like-indicators applied-research question banked. **CRITICAL**: per OQ-1.3 + OQ-1.4 amendments (§1.5.1 + §1.5.4 below), the parameter-sweep sensitivity diagnostic in T-T4.SB.1 now LANDS UNDER `research/` (research-branch placement), which means T-T4.SB.1's output IS the first piece of the applied-research first-method-record work. Update `research/phase-0-tasks.md` "Next" section accordingly during the plan-write phase.

---

## §1 OQ dispositions (BINDING for writing-plans phase)

Per operator-paired triage 2026-05-22 PM #2 (post-brainstorming): all 18 OQs from spec §J are LOCKED. Highlights:

### §1.1 Item 1 (4 OQs)
- **OQ-1.1**: CLI subcommand emitting markdown + CSV sidecar to `exports/diagnostics/` (LOCKED concur)
- **OQ-1.2**: `--eval-runs N` parameter, default N=20, max N=100 (LOCKED concur)
- **OQ-1.3**: **REVISED** per §1.5.1 amendment — 1D parameter-sweep sensitivity harness (NOT snapshot diagnostic). Operator framing: "comprehensive sweep through a reasonable range of each variable in isolation … provide us with a reasonable basis to estimate desired change rather than just guessing."
- **OQ-1.4**: **REVISED** per §1.5.4 amendment — research branch placement (`research/harness/aplus_sensitivity/`), NOT production (per V2.1 §V branch-posture + research-study shape mirroring `research/harness/earnings_proximity/` precedent)

### §1.2 Item 2 (3 OQs)
- **OQ-2.1**: LOCKED `rule_criteria` shape `{name, status, evidence_value, threshold, tolerance}` matching `_parse_criterion_rows:110-160`. `geometric_evidence_narrative` PRESERVED VERBATIM; persistence envelope adds `"narrative"` ALIAS key (same value) so `_parse_narrative_text` lights up for fresh silver rows.
- **OQ-2.2**: two-pronged ship + operator decides at execution time
- **OQ-2.3**: KEEP Path C backfill script as fallback

### §1.3 Item 5 (5 OQs)
- **OQ-5.1**: R4 (manual prune CLI) + R1 default unbounded; defer R2/R3 automated retention to V2 if growth observed
- **OQ-5.2**: Synchronous-JIT-no-timeout V1 default; measured-timing diagnostic ships as part of T-T4.SB.1 or T-T4.SB.3
- **OQ-5.3**: Pre-gen scope LOCKED to "market_weather + position_detail + dashboard-top-5 watchlist ONLY"
- **OQ-5.4**: **Option A LOCKED** — dashboard reader binds to one pipeline_run anchor; JIT writes match anchor (see §1.5.3 below)
- **OQ-5.5**: KEEP chart-unavailable banner as fallback for genuine errors

### §1.4 Item 7 (3 OQs)
- **OQ-7.1**: Diagnostic FIRST (T-T4.SB.1) + fix SECOND (T-T4.SB.2). Sequential.
- **OQ-7.2**: Broader audit enumerates `swing/metrics/` + `swing/web/view_models/metrics/` + `swing/journal/stats.py` + dashboard cards
- **OQ-7.3**: Option 7C (READ-time delimiter-aware prefix-match; NO schema change; preserves per-trade suffix)

### §1.5 Phase 13 closure (3 OQs)
- **OQ-CL.1**: CLAUDE.md + orchestrator-context updates at T-T4.SB.6 closer announcing "Phase 13 FULLY CLOSED — 12 of 12 sub-bundles SHIPPED"
- **OQ-CL.2**: **REVISED** per §1.5.2 amendment — deferred until T-T4.SB.1 diagnostic ships. Becomes an explicit "Phase 13 closure → next-phase triage" gate; operator-paired triage post-T4.SB-SHIPPED picks Phase 14 (operational) vs Applied Research focus vs idle monitoring based on diagnostic findings.
- **OQ-CL.3**: Schedule research-branch first-method-record selection immediately post-T4.SB-SHIPPED. **NOTE**: per §1.5.1, the parameter-sweep harness IS already the first piece of research-branch work; OQ-CL.3 disposition still applies for the formal method-record selection meeting.

### §1.6 Cross-item (1 OQ)
- **OQ-X.1**: Items 3+4+6 bundled in ONE Codex round (T-T4.SB.5)

---

## §1.5 Amendments (BINDING; executed alongside spec-encoded scope)

### §1.5.1 OQ-1.3 SCOPE EXPANSION — parameter-sweep sensitivity harness (NOT snapshot diagnostic)

**Operator framing 2026-05-22 PM #2 (verbatim):** "Is it possible to do an initial analysis on the output sensitivity to variable adjustment by performing a comprehensive sweep through a reasonable range of each variable in isolation? Understanding there may be some cross-coupling between variables, but this would provide us with a reasonable basis to estimate desired change rather than just guessing."

**Decision:** YES. Expand T-T4.SB.1 Item 1 diagnostic from snapshot shape to **1D parameter-sweep sensitivity harness**.

**Harness shape:**
- **Data source**: persisted `candidate_criteria` rows for the last N eval_runs (N default per OQ-1.2 = 20). Already locked at spec R1.M1 closure: "rescoped to consume persisted candidate_criteria per migration `0001_phase1_initial.sql:48-56`."
- **Variables**: enumerate all per-criterion thresholds in `bucket_for` (per `swing/evaluation/scoring.py`; implementer reads + lists at recon time). Expected ~10-20 variables.
- **Sweep range per variable**: reasonable range; orchestrator suggests `{0.5×, 0.75×, current, 1.25×, 1.5×}` OR `{-2σ, -1σ, current, +1σ, +2σ}` — implementer picks per variable nature (multiplicative for thresholds; std-dev for distribution-bounded). Document the choice.
- **Sweep mode**: 1D, one variable at a time, others held at current. Cross-coupling caveat acknowledged (first-order approximation).
- **For each (variable v_i, sweep point p_j)**: substitute v_i = p_j; hold others at current; recompute `bucket_for` on each candidate_criteria row; count (A+ count, watch count, skip count, excluded count).
- **Output**: sensitivity matrix CSV (rows = variables; columns = sweep points; cells = "A+/watch/skip" tuple OR three matrices stacked) + markdown summary with interpretation.

**Compute cost (acceptable):** ~10-20 variables × 5-7 sweep points × ~5000 candidate_criteria rows × N=20 eval_runs = ~5-14M bucket_for recomputations. Pure Python arithmetic against pre-stored criterion values; ~seconds-to-minutes total. No DB writes; no yfinance fetches; no full pipeline runs.

**Plan-task implication:** T-T4.SB.1 sub-task structure SHOULD expand from "instrument bucket_for + capture blocking distribution" to "build sensitivity harness + run sweep + emit sensitivity matrix + markdown analysis". Likely splits into:
- T-T4.SB.1a: Item 1 sensitivity-harness build (read variable list; sweep machinery; output formatter)
- T-T4.SB.1b: Item 1 run sweep against operator DB + emit sensitivity matrix + markdown analysis
- T-T4.SB.1c: Item 7 specific-defect diagnostic (was T-T4.SB.1 original second task; preserves spec §G structure)

OR fold sensitivity-harness into one task with bite-sized step structure per T2.SB6c precedent. Implementer decides at plan-write time.

**Discriminating tests:** synthetic candidate_criteria fixture + assert harness produces correct sweep matrix for a known variable; assert independent-axis sweep correctness; assert markdown output formatter renders correctly.

### §1.5.2 OQ-CL.2 deferred-until-diagnostic disposition

**Operator decision 2026-05-22 PM #2:** Defer the Phase 14 trigger decision until T-T4.SB.1 sensitivity harness ships its output. Becomes a "Phase 13 closure → next-phase triage" gate.

**Plan implication:** T-T4.SB.6 closer SHOULD include in its acceptance criteria a discrete artifact "post-T4.SB triage meeting agenda" — a markdown stub at `docs/phase13-closer-next-phase-triage.md` that the operator + next orchestrator instance use to drive the path-A/B/C decision based on Item 1 diagnostic output. The closer commit message MUST cite the deferred-decision artifact + the dependency chain (T-T4.SB.1 diagnostic → triage agenda → next-phase decision).

### §1.5.3 OQ-5.4 Option A LOCKED

**Operator decision 2026-05-22 PM #2:** Re-run collision semantics = Option A — dashboard reader binds to ONE pipeline_run anchor; JIT writes match anchor.

**Plan implication:** T-T4.SB.3 Item 5 architecture work LOCKS Option A. Implementation details:
- Dashboard reader resolves "latest completed pipeline_run" once per render; passes pipeline_run_id to chart_jit helper
- chart_jit helper reads/writes chart_renders rows keyed on (surface, ticker, pipeline_run_id) per Option A
- Re-run during dashboard view: dashboard sees stable cache for the run_id it anchored to; subsequent dashboard render picks up the newer run_id + may JIT-render against the newer run
- Old run_id cache rows accumulate (per OQ-5.1 R4 manual prune CLI; bounded growth acceptable V1)
- Discriminating test: render dashboard A at pipeline_run_id=N; concurrently insert new pipeline_run_id=N+1 rows + new chart_renders rows for N+1; assert dashboard A still reads N's cache (anchored at first read).

### §1.5.4 OQ-1.4 REVISED to research-branch placement

**Operator decision 2026-05-22 PM #2 (paired with §1.5.1):** Item 1 diagnostic → sensitivity harness shape → research-branch placement.

**Decision:** Implement under `research/harness/aplus_sensitivity/` mirroring `research/harness/earnings_proximity/` precedent (existing harness pattern + CSV output format).

**Plan implication:**
- T-T4.SB.1 ships TWO categories of artifact:
  - Production: instrumentation (if any) to capture variable thresholds; CLI to invoke (`swing diagnose aplus-sensitivity` OR similar; placement TBD per implementer judgment — could live under `swing/cli.py` invoking research/ harness, OR under `python -m research.harness.aplus_sensitivity` standalone)
  - Research: harness module at `research/harness/aplus_sensitivity/` (mirror earnings_proximity); first study at `research/studies/aplus-criterion-sensitivity-2026-05-22.md`; method record stub at `research/method-records/aplus-criteria-calibration.md` (NEW; per `research/method-records/_template.md`)
- Update `research/phase-0-tasks.md` "Next" section: move "Evaluate which A+-like indicators..." entry from "Later (deferred)" to "Next" with note that the sensitivity harness shipped under T4.SB IS the first piece of this work
- Per V2.1 §IV.D + §VII.C: method record `status` field starts at `research`; promotion to `shadow` or `production` requires evidence summary + operator decision (NOT in T4.SB scope)

### §1.5.5 Test count impact

Spec §F baseline projection was ~50-150 fast tests. §1.5.1 sensitivity-harness expansion adds ~8-12 tests (harness build + sweep + output formatter + discriminating cross-coupling-acknowledgment test). New T-T4.SB.1 test budget: ~30-40 tests (was ~15-20). Total T4.SB projection: **~60-160 fast + 1 fast E2E** (within original brainstorm range).

Schema v21 UNCHANGED (sensitivity harness consumes existing `candidate_criteria` schema; no migration).

---

## §2 Scope inheritance from brainstorming spec (BINDING)

Per OQ-X.1 LOCK + brainstorming spec §G: 6-task decomposition T-T4.SB.1..T-T4.SB.6. Writing-plans plan MUST encode per-task acceptance criteria + commit message templates + per-task test budget. Do NOT re-derive the task structure; reference spec §G as authoritative.

### §2.1 Per-task scope summary (spec §G is BINDING)

| Task | Spec §G ref | Brief description | §1.5 amendments |
|---|---|---|---|
| T-T4.SB.1 | §G.1 | Item 1 + Item 7 specific-defect diagnostics combined | §1.5.1 EXPANDS Item 1 portion to sensitivity harness + §1.5.4 PLACES under research/ |
| T-T4.SB.2 | §G.2 | Item 7 broader metrics audit + cross-bundle pin row 13 parametrize 4 surfaces | None |
| T-T4.SB.3 | §G.3 | Item 5 architecture (NEW `swing/web/chart_jit.py` + chart_scope LOCKED read-only) | §1.5.3 LOCKS Option A for OQ-5.4 |
| T-T4.SB.4 | §G.4 | Item 2 additive `rule_criteria` + envelope alias `narrative` key | None |
| T-T4.SB.5 | §G.5 | Items 3 + 4 + 6 cosmetic/UX bundled | None |
| T-T4.SB.6 | §G.6 | Closer + Phase 13 FULLY CLOSED marker + post-T4.SB triage agenda stub (§1.5.2) | §1.5.2 ADDS triage-agenda artifact requirement |

### §2.2 Concurrent dispatch potential

Per spec §H: T-T4.SB.4 (labeler) + T-T4.SB.5 (cosmetic) can run concurrent with the investigation tasks (T-T4.SB.1 + T-T4.SB.2). T-T4.SB.3 sequential after substrate decisions in T-T4.SB.1 ship. T-T4.SB.6 closer sequential after all.

Plan should explicitly enumerate the concurrent-dispatch graph per spec §H + add wall-clock-savings estimate.

---

## §3 Watch items + cumulative discipline (BINDING for writing-plans phase)

### §3.1 Pre-Codex 7-expansion + 4 NEW candidate refinements (29th cumulative C.C lesson #6 validation expected)

Writing-plans phase pre-Codex review applies ALL 7 expansions + 4 NEW candidate refinements:

1. **Expansion #1** — hardcoded-duplicate audit (T3.SB2 hotfix `cf3c489`)
2. **Expansion #2** — brief-vs-spec + brief-vs-actual schema (T2.SB6c brainstorm)
3. **Expansion #3** — schema-CHECK-vs-semantic-contract gap (T2.SB6a R1 CRITICAL #1)
4. **Expansion #4** — specific-scenario gotcha trace + SQL skeleton column verification (T2.SB6c brainstorm + writing-plans)
5. **Expansion #5** — cross-section spec inventory grep (T2.SB6a R1 MAJOR #3)
6. **Expansion #6** — content-completeness audit (T2.SB6b lessons)
7. **Expansion #7** — cross-row semantic SCOPE audit + scope-vs-unit boundary (T2.SB6b + T2.SB6c bankings)
8. **Expansion #8 candidate** — per-aggregation-function UNIT audit on SQL skeletons (T2.SB6c writing-plans)
9. **Expansion #9 candidate** — form-render anchor lifecycle 4-dimension audit (T2.SB6c executing-plans)
10. **Expansion #10 candidate (NEW BINDING)** — Architecture-location audit + 4 sub-disciplines (T4.SB brainstorming 2026-05-22 PM #2) — 5 sub-disciplines: (a) wrong-module helper placement; (b) template-vs-VM-parser-vs-emitter triangulation; (c) cache-key + renderer-kwargs uniformity LOCK; (d) SQL LIKE binding-param asymmetry; (e) orphan-label preservation under refactor

### §3.2 Cumulative gotcha set (14 cumulative; 5 NEW from T2.SB6c + T4.SB)

Per CLAUDE.md updates through `f7dec0e`:
- (9) SQL aggregation UNIT audit (Expansion #8)
- (10) Existing-field reuse audit before claiming new dataclass fields
- (11) Template-rendering surface audit before claiming "no template edit needed"
- (12) `date.fromisoformat()` discipline for cross-type-boundary calls
- (13) Form-render anchor lifecycle audit (Expansion #9)
- (14) Architecture-location audit + 4 sub-disciplines (Expansion #10)

All 6 NEW gotchas BINDING for writing-plans-phase pre-Codex discipline.

### §3.3 Cumulative process discipline

- **NO Co-Authored-By footer** — ~378+ cumulative streak through T4.SB brainstorming housekeeping at `f7dec0e`. Cite per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15) in every commit message.
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing`
- **ASCII-only on runtime CLI paths** + template narrative text (Windows cp1252 stdout safety)
- **TDD per task** via `superpowers:test-driven-development`
- **Edit tool for per-file edits**
- **Cite the discipline in commit messages** per cumulative precedent

### §3.4 Schema discipline (T4.SB is schema-UNCHANGED)

T4.SB SHOULD NOT touch schema per brainstorming spec §A.2 LOCK. v21 is the locked schema for this dispatch. If investigation surfaces an absolute necessity (e.g., chart_renders retention-policy table per OQ-5.1 R4 manual prune — likely fits within existing schema or as a CLI), §A.14 paired discipline applies + backup-gate strict-equality + migration runner discipline all apply per cumulative precedent.

---

## §4 Done criteria for writing-plans output

The plan at `docs/superpowers/plans/2026-05-22-phase13-t4-sb-closer-plan.md` (or operator-paired-named equivalent) MUST cover:

- [ ] **§A Status + scope** — 7 triage items + 18 OQ dispositions verbatim + 4 §1.5 amendments encoded
- [ ] **§B Per-task design** — for each of T-T4.SB.1..T-T4.SB.6: (i) bite-sized step structure (Step 1a-1N); (ii) per-step acceptance criteria; (iii) discriminating test list; (iv) commit message template
- [ ] **§C Cross-task dependencies** — explicit graph; concurrent dispatch sequencing per spec §H
- [ ] **§D Investigation outputs format** — Item 1 sensitivity matrix CSV shape + markdown analysis structure + Item 7 specific-defect diagnostic format + Item 7 broader audit format
- [ ] **§E Cross-bundle pin row 13** — parametrize over 4 metric surfaces per spec §E LOCK; planting + un-skip schedule
- [ ] **§F Test scope projection** — per-task test budget; baseline 5670 → ~5730-5830 fast expected (+§1.5.5 bump)
- [ ] **§G Per-task acceptance criteria** — same as §B but lifted to dispatchable-task granularity
- [ ] **§H Dispatch sequence + concurrent-dispatch graph**
- [ ] **§I Forward-binding lessons inherited** — from brainstorming spec §I + cumulative gotcha set
- [ ] **§J §1.5 amendments encoded** — explicitly per amendment with rationale + scope impact
- [ ] **§K Research-branch coordination** — note T-T4.SB.1 sensitivity harness placement under `research/`; update `research/phase-0-tasks.md` "Next" section as part of T-T4.SB.1; first method-record stub at `research/method-records/aplus-criteria-calibration.md`
- [ ] **§L Phase 13 closure procedure** — T-T4.SB.6 acceptance criteria include CLAUDE.md + orchestrator-context updates per spec §K + triage-agenda artifact stub per §1.5.2

Plan-phase Codex chain expected 2-5 rounds. Pre-Codex 7-expansion + 4 NEW candidate refinements + 6 NEW gotchas (#9-#14) discipline BINDING; verdict per expansion captured in plan-phase return report.

---

## §5 References

- **Brainstorming spec (BINDING)**: [`docs/superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md`](superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md) at HEAD `f7dec0e`
- **Brainstorming return report**: [`docs/phase13-t4-sb-brainstorm-return-report.md`](phase13-t4-sb-brainstorm-return-report.md)
- **Brainstorming dispatch brief**: [`docs/phase13-t4-sb-brainstorming-dispatch-brief.md`](phase13-t4-sb-brainstorming-dispatch-brief.md) at `e75f743`
- **T4.SB triage items**: [`docs/phase3e-todo.md:15-101`](phase3e-todo.md)
- **Phase 13 main plan**: [`docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md`](superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md)
- **Phase 13 main spec**: [`docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`](superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md)
- **Research branch precedent**: [`research/harness/earnings_proximity/`](research/harness/earnings_proximity/) + [`research/studies/earnings-proximity-exclusion.md`](research/studies/earnings-proximity-exclusion.md) + [`research/method-records/earnings-proximity-exclusion.md`](research/method-records/earnings-proximity-exclusion.md) + [`research/method-records/_template.md`](research/method-records/_template.md)
- **Research branch question (banked)**: [`research/phase-0-tasks.md`](research/phase-0-tasks.md) "Later (deferred)" — A+-like-indicators applied-research entry
- **CLAUDE.md** at repo root (14 NEW gotchas; #9-#14 BINDING for 29th cumulative validation)

---

## §6 NON-scope (V2 / future arc; explicitly out of T4.SB)

- **Phase 14 dispatch** — deferred per §1.5.2; T-T4.SB.6 closer ships triage-agenda artifact, NOT Phase 14 commissioning
- **Research-branch method-record selection meeting** — OQ-CL.3 schedules this post-T4.SB-SHIPPED as separate operator-paired session
- **Schema changes** — T4.SB is schema-UNCHANGED per spec §A.2 LOCK
- **ZERO new Schwab API calls** (L2 LOCK preserved)
- **V2-banked items per spec §4.1** — 14 V1 simplifications banked at brainstorming + inherited V2 candidates from T2.SB6c arc + Phase 13 main spec §7.4

---

## §7 Post-writing-plans handback

When writing-plans Codex chain converges to NO_NEW_CRITICAL_MAJOR:

1. Write return report at `docs/phase13-t4-sb-writing-plans-return-report.md` per cumulative precedent (commit chain + per-expansion verdict + Codex chain shape + forward-binding lessons + V2 candidates banked + cumulative streaks).
2. Inline self-verification: ruff check; schema unchanged at v21 (writing-plans touches docs only); baseline 5670 fast tests UNCHANGED.
3. Hand back to operator with summary.

Orchestrator-side next steps post-writing-plans (Turn B):
- QA implementer product per `feedback_orchestrator_qa_implementer_product` (verify file:line + shipped-behavior + locks-preserved against reality on disk)
- Merge writing-plans branch `--no-ff` to main; push
- Post-merge housekeeping bundle (CLAUDE.md line 3 refresh + any NEW gotchas + phase3e-todo.md NEW top entry + orchestrator-context.md current state refresh + Prior demote + archive-split per size-check trigger)
- Draft T4.SB executing-plans dispatch brief + amendments if any
- Provide inline implementer dispatch prompt for executing-plans
- Note: Turn B may or may not finish executing-plans in same orchestrator turn depending on context budget; another shift may be needed before T-T4.SB.6 ships

---

*End of T4.SB writing-plans dispatch brief. 18 OQs operator-locked + 4 §1.5 amendments encoded (parameter-sweep sensitivity harness + research-branch placement + Option A re-run collision + OQ-CL.2 deferred-until-diagnostic). ~378+ ZERO Co-Authored-By footer streak preserved. T4.SB closer arc IN-FLIGHT (brainstorming SHIPPED; writing-plans next; executing-plans + T-T4.SB.6 closer remain). Phase 13 FULLY CLOSED marker fires at T-T4.SB.6 executing-plans SHIPPED per spec §K + §1.5.2 amendment triage-agenda artifact.*
