# Phase 13 T4.SB — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the T4.SB executing-plans implementer. No prior conversation context.

**Mission:** Execute the 6 sub-bundle tasks T-T4.SB.1..T-T4.SB.6 per the writing-plans plan, ship per-task commits + Codex MCP fix bundles + 1 return report; preserve all cumulative streaks; close out the Phase 13 closer arc at T-T4.SB.6 with FULLY CLOSED marker per spec §K + post-T4.SB triage-agenda artifact per §1.5.2 amendment.

**Plan (BINDING substrate):** [`docs/superpowers/plans/2026-05-22-phase13-t4-sb-closer-plan.md`](superpowers/plans/2026-05-22-phase13-t4-sb-closer-plan.md) at main HEAD `9b2a4db` (4184 lines; 14 sections §A-§N with §A-§L per writing-plans dispatch-brief done criteria + §M references + §N self-review; 6 sub-bundle tasks T-T4.SB.1..T-T4.SB.6 with 149 bite-sized TDD step-checkboxes). **READ END-TO-END before dispatching first task.**

**Brainstorming spec (REFERENCE substrate):** [`docs/superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md`](superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md) at `f7dec0e` (1045 lines; 13 sections §A-§M). Already encoded into plan; consult when plan section references "spec §X".

**Writing-plans dispatch brief (REFERENCE; predecessor):** [`docs/phase13-t4-sb-writing-plans-dispatch-brief.md`](phase13-t4-sb-writing-plans-dispatch-brief.md) at `4690933`. Already encoded into plan as §J amendments. Consult only for amendment rationale.

**Writing-plans return report (REFERENCE):** [`docs/phase13-t4-sb-writing-plans-return-report.md`](phase13-t4-sb-writing-plans-return-report.md) at branch `c8d21b9` (merged to main at `9b2a4db`) — captures Codex chain shape + 10 V1 simplifications banked + 5 forward-binding lessons + NEW Expansion #11 candidate banking.

**Brief:** `docs/phase13-t4-sb-executing-plans-dispatch-brief.md` (this file).

**Sequencing:** T4.SB writing-plans SHIPPED 2026-05-22 PM #3 at `9b2a4db` + housekeeping at `6ce7561` + this brief commit. Output completes the Phase 13 closer arc + flips Phase 13 to FULLY CLOSED at T-T4.SB.6.

**Branch:** `phase13-t4-sb-executing-plans` (single integration branch for all 6 tasks via sequential commits) — OR per-task branches if the implementer opts for concurrent dispatch per plan §H.2. Per cumulative precedent (T2.SB6c executing-plans `phase13-t2-sb6c-executing-plans`), single integration branch is the default; per-task branches add merge complexity for marginal benefit when tasks have sequential dependencies. **Implementer decides at dispatch time; default to single branch.**

**Worktree:** `git worktree add .worktrees/phase13-t4-sb-executing-plans phase13-t4-sb-executing-plans`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Workflow:** `copowers:executing-plans` skill (wraps `superpowers:subagent-driven-development` with adversarial Codex MCP review after all tasks complete). Expected 3-5 Codex rounds across the cumulative implementation.

**Expected duration:** ~6-8 hours operator-paced (largest T4.SB dispatch by scope — 6 tasks + investigation harness + cosmetic fixes + architectural rewrite + closer). Plan target test bump: baseline 5670 → ~5760-5805 fast + 1 fast E2E per plan §F.

---

## §0 Read first (in this order)

1. **`docs/superpowers/plans/2026-05-22-phase13-t4-sb-closer-plan.md`** at HEAD `9b2a4db` — PRIMARY SUBSTRATE. 14 sections §A-§N. ESPECIALLY:
   - §A Status + scope (7 triage items + 18 OQ dispositions + 4 §1.5 amendments encoded + complete file map)
   - §B Per-task design (6 sub-bundle tasks with bite-sized TDD step-checkboxes; 149 total)
   - §C Cross-task dependencies + concurrent-dispatch graph
   - §D Investigation outputs format (Item 1 sensitivity matrix CSV + markdown analysis; Item 7 audit table)
   - §E Cross-bundle pin row 13 (4-surface parametrize + plant/promote schedule)
   - §F Test scope projection (baseline 5670 → ~5760-5805 fast + 1 fast E2E)
   - §G Per-task acceptance criteria (BINDING for implementer)
   - §H Dispatch sequence + concurrent-dispatch graph (sequential default; concurrent alternative saves ~1.5h; operator-witnessed S1-S5 gates)
   - §I Forward-binding lessons inherited (14 cumulative gotchas applied per task; 7 expansions + 4 NEW refinements BINDING)
   - §J §1.5 amendments encoded (4 amendments)
   - §K Research-branch coordination (V2.1 §IV.D + §VII.C lifecycle posture)
   - §L Phase 13 closure procedure (T-T4.SB.6 acceptance criteria including triage-agenda artifact stub)
   - §M references; §N self-review

2. **`CLAUDE.md`** at repo root — project conventions + 15 cumulative gotchas (gotcha #15 NEW Expansion #11 candidate appended this housekeeping). ESPECIALLY relevant for T4.SB executing-plans phase:
   - **Taxonomy propagation audit (NEW gotcha #15; Expansion #11 candidate BINDING)** — surfaced via R1+R3+R4 `kind` enum propagation 3-instance lesson during writing-plans Codex chain. Apply when extending dataclasses or serializers with enum-typed fields.
   - **Architecture-location audit + 4 sub-disciplines (gotcha #14; Expansion #10 candidate BINDING)** — apply at T-T4.SB.3 (chart_jit.py NEW module; chart_scope LOCKED read-only) + T-T4.SB.2 (count_per_cohort orphan-preservation + SQL LIKE binding asymmetry) + T-T4.SB.4 (envelope alias `narrative` key triangulation).
   - **Form-render anchor lifecycle audit (gotcha #13; Expansion #9 candidate BINDING)** — apply if any task introduces NEW hidden form anchors driving POST-time validation (T4.SB SHOULD NOT — but verify).
   - **SQL aggregation UNIT audit (gotcha #9; Expansion #8 candidate BINDING)** — apply at T-T4.SB.2 (metrics-wiring audit SQL helpers).
   - **Brief-vs-actual schema reality check + SQL skeleton column verification (Expansion #4 refinement BINDING)** — apply when implementing fixture INSERTs against `swing/data/migrations/*.sql`.
   - **Grouping-key fields need canonicalization-at-persistence-boundary** — DIRECTLY APPLIES to Item 7 Option 7C READ-time delimiter-aware match (per OQ-7.3 LOCK; preserves per-trade suffix; NO schema change).
   - **HTMX OOB-swap partial drift** — DIRECTLY APPLIES to Item 6 (watchlist expand-collapse loses thumbnail; canonical pattern per CLAUDE.md gotcha).
   - **Matplotlib mathtext fires on `$`/`^`/`_`/unbalanced `\`** — applies to Item 3 chart rendering (volume y-axis label strip).
   - **F6 transient-empty defense at construction barrier** — applies to Item 5 chart_jit cache writes (if write-through helper accepts dataclass parameter).

3. **`docs/phase13-t4-sb-writing-plans-return-report.md`** — Codex chain shape (5 rounds; 2C+14M+12m); 10 V1 simplifications banked with V2 dependency cited; 5 forward-binding lessons; NEW Expansion #11 candidate banking.

4. **`docs/superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md`** at `f7dec0e` — reference only; plan §J encodes all amendments + plan §B encodes the per-task design.

5. **`docs/orchestrator-context.md`** "Currently in-flight work" — current state reflects T4.SB writing-plans SHIPPED + Prior #1 = T4.SB brainstorming SHIPPED.

6. **`research/phase-0-tasks.md`** "Next" section — A+-like-indicators applied-research question; **CRITICAL**: per OQ-1.4 + §1.5.4, T-T4.SB.1 sensitivity harness IS the first piece of this work. Update "Next" section accordingly per plan §K research-branch coordination.

7. **`research/method-records/_template.md`** + **`research/harness/earnings_proximity/`** + **`research/studies/earnings-proximity-exclusion.md`** — research-branch precedents to mirror for T-T4.SB.1 placement at `research/harness/aplus_sensitivity/` + first method-record stub at `research/method-records/aplus-criteria-calibration.md`.

---

## §1 OQ dispositions (BINDING; inherited verbatim from writing-plans brief)

Per operator-paired triage 2026-05-22 PM #2 (post-brainstorming): all 18 OQs from spec §J are LOCKED. The plan §A encodes them verbatim. ABSOLUTELY DO NOT re-litigate.

Highlights (full enumeration in plan §A + writing-plans dispatch brief §1):
- **Item 1 (4 OQs)** — OQ-1.1 CLI subcommand + markdown/CSV; OQ-1.2 `--eval-runs N=20` default max=100; **OQ-1.3 REVISED per §1.5.1** 1D parameter-sweep sensitivity harness; **OQ-1.4 REVISED per §1.5.4** research-branch placement.
- **Item 2 (3 OQs)** — OQ-2.1 `rule_criteria` shape + envelope `narrative` alias; OQ-2.2 two-pronged ship; OQ-2.3 KEEP Path C backfill as fallback.
- **Item 5 (5 OQs)** — OQ-5.1 R4 manual prune + R1 unbounded; OQ-5.2 sync-JIT-no-timeout V1; OQ-5.3 pre-gen scope LOCKED to market_weather + position_detail + dashboard-top-5 watchlist; **OQ-5.4 Option A LOCKED per §1.5.3** dashboard reader binds to one pipeline_run anchor; OQ-5.5 KEEP chart-unavailable banner.
- **Item 7 (3 OQs)** — OQ-7.1 diagnostic FIRST + fix SECOND; OQ-7.2 broader audit enumerates `swing/metrics/` + `swing/web/view_models/metrics/` + `swing/journal/stats.py` + dashboard cards; OQ-7.3 Option 7C READ-time delimiter-aware.
- **Phase 13 closure (3 OQs)** — OQ-CL.1 CLAUDE.md + orchestrator-context updates at T-T4.SB.6 closer; **OQ-CL.2 REVISED per §1.5.2** deferred-until-diagnostic; OQ-CL.3 research-branch first-method-record selection scheduled post-T4.SB-SHIPPED.
- **Cross-item (1 OQ)** — OQ-X.1 Items 3+4+6 bundled in ONE Codex round (T-T4.SB.5).

---

## §1.5 Amendments (BINDING; inherited verbatim from writing-plans brief §1.5)

Per writing-plans dispatch brief 2026-05-22 PM #3 — all 4 §1.5 amendments are LOCKED and encoded in plan §J:

- **§1.5.1** — OQ-1.3 SCOPE EXPANSION — parameter-sweep sensitivity harness (NOT snapshot diagnostic). T-T4.SB.1 ships `research/harness/aplus_sensitivity/sweep.py` with `_bucket_for_substituted` per-criterion threshold sweep; sensitivity matrix CSV (9 columns including Kind taxonomy `{additive, gate, threshold}`) + markdown analysis (Kind column + V1-LIMITATION paragraph). Test budget bumped to ~30-40 per plan §F T-T4.SB.1 row.
- **§1.5.2** — OQ-CL.2 deferred-until-diagnostic disposition. T-T4.SB.6 closer ships `docs/phase13-closer-next-phase-triage.md` triage-agenda artifact stub; operator-paired post-T4.SB-SHIPPED triage picks Phase 14 trigger / Applied Research focus / idle monitoring based on Item 1 diagnostic output.
- **§1.5.3** — OQ-5.4 Option A LOCKED. T-T4.SB.3 implements dashboard reader binds to ONE pipeline_run anchor; chart_jit helper reads/writes chart_renders rows keyed on (surface, ticker, pipeline_run_id). Re-run collision benign — first-read-wins anchor; old run_id cache rows accumulate (bounded growth acceptable V1 per OQ-5.1).
- **§1.5.4** — OQ-1.4 REVISED to research-branch placement. T-T4.SB.1 places sensitivity harness under `research/harness/aplus_sensitivity/` mirroring `research/harness/earnings_proximity/` precedent; first method-record stub at `research/method-records/aplus-criteria-calibration.md` per V2.1 §IV.D + §VII.C lifecycle posture (method record `status` starts at `research`).

**If executing-plans phase surfaces NEW amendments (operator decisions mid-implementation, e.g., during Codex cycles): encode as §1.5.5+ in the return report; do NOT modify the writing-plans brief or plan in-place.** Mirror T2.SB6c writing-plans precedent.

---

## §2 Scope inheritance from writing-plans plan §G (BINDING)

Per plan §G is the BINDING substrate for per-task acceptance criteria. DO NOT re-derive task structure — reference plan §G as authoritative.

### §2.1 Per-task scope summary (plan §G is BINDING)

| Task | Plan §G ref | Brief description |
|---|---|---|
| T-T4.SB.1 | §G.1 | Item 1 sensitivity harness under `research/harness/aplus_sensitivity/` (Steps 1A-1N per plan §B.1) + Item 7 specific-defect diagnostic at `swing/diagnostics/hyp_progress_root_cause.py` (Steps 1O-1Q per plan §B.1) + first research-branch method-record stub. ~30-40 fast tests. |
| T-T4.SB.2 | §G.2 | Item 7 broader metrics-wiring audit at `swing/diagnostics/metrics_wiring_audit.py` + Option 7C READ-time delimiter-aware match for `count_per_cohort` helper + cross-bundle pin row 13 parametrize over 4 metric surfaces. ~15-25 fast tests. |
| T-T4.SB.3 | §G.3 | Item 5 architecture work with NEW `swing/web/chart_jit.py:get_or_render_surface` module + `chart_scope.py` LOCKED read-only + dashboard reader binds to ONE pipeline_run anchor per OQ-5.4 Option A LOCK + pre-gen scope reduced to market_weather + position_detail + dashboard-top-5 watchlist per OQ-5.3 LOCK. ~25-40 fast tests. |
| T-T4.SB.4 | §G.4 | Item 2 additive `rule_criteria` shape `{name, status, evidence_value, threshold, tolerance}` matching `_parse_criterion_rows:110-160` + envelope ALIAS key `narrative` (persists both `geometric_evidence_narrative` AND `narrative` keys so `_parse_narrative_text` lights up). ~10-15 fast tests. |
| T-T4.SB.5 | §G.5 | Items 3 + 4 + 6 cosmetic/UX bundled per OQ-X.1 LOCK: Item 3 strip market_weather volume y-axis labels (matplotlib safe per CLAUDE.md mathtext gotcha); Item 4 remove lightning glyph from watchlist row template; Item 6 HTMX expand-collapse thumbnail preservation via canonical `{% include %}` per CLAUDE.md OOB-swap gotcha. ~8-12 fast tests. |
| T-T4.SB.6 | §G.6 | Closer + Phase 13 FULLY CLOSED marker per spec §K + post-T4.SB triage-agenda artifact at `docs/phase13-closer-next-phase-triage.md` per §1.5.2 + 1 NEW fast E2E. ~1-3 fast tests + 1 fast E2E. |

### §2.2 Dispatch sequence options

**Default (sequential)** per plan §H.1:
```
T-T4.SB.1 → T-T4.SB.2 → T-T4.SB.3 → T-T4.SB.4 → T-T4.SB.5 → T-T4.SB.6
```
~6 hours operator-paced.

**Alternative (concurrent)** per plan §H.2 (saves ~1.5h):
```
T-T4.SB.1 ─┐
           ├─ T-T4.SB.2  ─┐
           ├─ T-T4.SB.3  ─┼─→ T-T4.SB.5 → T-T4.SB.6
           └─ T-T4.SB.4  ─┘
```
T-T4.SB.4 + T-T4.SB.3 + T-T4.SB.2 dispatchable concurrent after T-T4.SB.1; T-T4.SB.5 sequential after T-T4.SB.3 (Item 6 invokes chart_jit JIT helper from T-T4.SB.3); T-T4.SB.6 sequential last.

Implementer chooses at dispatch time. Per `feedback_orchestrator_vs_implementer_execution` BINDING memory, default to sequential single-branch dispatch unless concurrent dispatch is materially faster + the dependency graph is honored.

---

## §3 Watch items + cumulative discipline (BINDING for executing-plans phase)

### §3.1 Pre-Codex 7-expansion + 4 NEW candidate refinements + NEW Expansion #11 (30th cumulative C.C lesson #6 validation expected)

Executing-plans phase pre-Codex review applies ALL 7 expansions + 4 NEW candidate refinements + Expansion #11 candidate:

1. **Expansion #1** — hardcoded-duplicate audit (T3.SB2 hotfix `cf3c489`)
2. **Expansion #2** — brief-vs-spec + brief-vs-actual schema (T2.SB6c brainstorm)
3. **Expansion #3** — schema-CHECK-vs-semantic-contract gap (T2.SB6a R1 CRITICAL #1)
4. **Expansion #4** — specific-scenario gotcha trace + SQL skeleton column verification (T2.SB6c brainstorm + writing-plans) — **EXTENDED at T4.SB writing-plans R1 to test fixture INSERT shape verification** (`hypothesis_registry.description` non-existent column lesson; refinement BINDING for writing-plans-phase test scaffolds too)
5. **Expansion #5** — cross-section spec inventory grep (T2.SB6a R1 MAJOR #3)
6. **Expansion #6** — content-completeness audit (T2.SB6b lessons)
7. **Expansion #7** — cross-row semantic SCOPE audit + scope-vs-unit boundary (T2.SB6b + T2.SB6c bankings)
8. **Expansion #8 candidate** — per-aggregation-function UNIT audit on SQL skeletons (T2.SB6c writing-plans)
9. **Expansion #9 candidate** — form-render anchor lifecycle 4-dimension audit (T2.SB6c executing-plans)
10. **Expansion #10 candidate** — Architecture-location audit + 5 sub-disciplines (T4.SB brainstorming) — confirmed CLEAN at writing-plans tier (FIRST clean-on-arrival validation)
11. **Expansion #11 CANDIDATE (NEW BINDING for 30th cumulative validation onwards)** — Taxonomy propagation audit (T4.SB writing-plans) — when an enum-typed field (`kind`/`status`/`type`) is added to one dataclass, audit all downstream dataclasses + serializers + test fixtures for consumption. Banked from R1+R3+R4 `kind` enum propagation 3-instance lesson. **Apply at executing-plans phase to any task that adds NEW enum-typed dataclass fields (T-T4.SB.1 SweepEntry kind + any T-T4.SB.2 audit-result kind/status if introduced)**.

### §3.2 Cumulative gotcha set (15 cumulative; 1 NEW from T4.SB writing-plans)

Per CLAUDE.md updates through `6ce7561`:
- (9) SQL aggregation UNIT audit (Expansion #8)
- (10) Existing-field reuse audit before claiming new dataclass fields
- (11) Template-rendering surface audit before claiming "no template edit needed"
- (12) `date.fromisoformat()` discipline for cross-type-boundary calls
- (13) Form-render anchor lifecycle audit (Expansion #9)
- (14) Architecture-location audit + 4 sub-disciplines (Expansion #10)
- (15) **NEW** Taxonomy propagation audit (Expansion #11) — appended at this housekeeping per writing-plans return report §5 lesson #3

All 7 NEW gotchas (#9-#15) BINDING for executing-plans-phase pre-Codex discipline.

### §3.3 Cumulative process discipline

- **NO Co-Authored-By footer** — ~386+ cumulative streak through housekeeping at `6ce7561`. Cite per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15) in every commit message.
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing`
- **ASCII-only on runtime CLI paths** + template narrative text (Windows cp1252 stdout safety per CLAUDE.md gotcha)
- **TDD per task** via `superpowers:test-driven-development`
- **Edit tool for per-file edits**
- **Cite the discipline in commit messages** per cumulative precedent

### §3.4 Schema discipline (T4.SB is schema-UNCHANGED)

T4.SB SHOULD NOT touch schema per brainstorming spec §A.2 LOCK. v21 is the locked schema for this dispatch. If investigation surfaces an absolute necessity (e.g., chart_renders retention-policy table per OQ-5.1 R4 manual prune — likely fits within existing schema or as a CLI), §A.14 paired discipline applies + backup-gate strict-equality + migration runner discipline all apply per cumulative precedent.

### §3.5 Research-branch coordination per plan §K

T-T4.SB.1 places NEW work under `research/`:
- **NEW harness module** at `research/harness/aplus_sensitivity/` (mirror `research/harness/earnings_proximity/` structure)
- **NEW study at** `research/studies/aplus-criterion-sensitivity-2026-05-22.md` (mirror `research/studies/earnings-proximity-exclusion.md` format)
- **NEW method-record stub** at `research/method-records/aplus-criteria-calibration.md` (mirror `research/method-records/_template.md` template; status `research`)
- **Update `research/phase-0-tasks.md`** "Next" section: move A+-like-indicators applied-research entry from "Later (deferred)" to "Next" with note that the sensitivity harness shipped under T4.SB IS the first piece of this work.

Per V2.1 §IV.D + §VII.C: method record `status` field starts at `research`; promotion to `shadow` or `production` requires evidence summary + operator decision (NOT in T4.SB scope).

---

## §4 Per-task summary (REFERENCE; plan §G is BINDING substrate)

Implementer reads plan §G + §B for each task before dispatching. The per-task acceptance criteria are encoded in plan §G; the bite-sized TDD step-checkboxes are in plan §B (Steps 1A-1Q, 2A-2J, 3A-3M, 4A-4F, 5A-5G, 6A-6E; 149 total).

DO NOT mirror plan §G in this brief — it would create drift risk. Use the plan as authoritative.

---

## §5 Done criteria for executing-plans output

The executing-plans dispatch MUST produce:

- [ ] **6 task commits** T-T4.SB.1..T-T4.SB.6 on `phase13-t4-sb-executing-plans` branch (or per-task branches if concurrent dispatch chosen per plan §H.2; merged via `--no-ff` to integration branch)
- [ ] **0-5 Codex MCP fix bundles** depending on Codex chain shape (chain expected 3-5 rounds per plan §H.3)
- [ ] **1 return report** at `docs/phase13-t4-sb-executing-plans-return-report.md` per cumulative precedent (commit chain + per-expansion verdict + Codex chain shape + forward-binding lessons + V2 candidates banked + cumulative streaks + S1-S5 operator-witnessed gate disposition)
- [ ] **Plan-projected test budget**: baseline 5670 → ~5760-5805 fast (+90 to +135 net) + 1 NEW fast E2E at T-T4.SB.6 closer per plan §F.1 table
- [ ] **Schema v21 UNCHANGED** through executing-plans phase (T4.SB schema-UNCHANGED per spec §A.2 LOCK)
- [ ] **Ruff `swing/` 0 E501** preserved (verify at T-T4.SB.6 sub-task 6D.5 final sweep per plan §F.3)
- [ ] **ZERO new Schwab API calls** (L2 LOCK preserved)
- [ ] **ZERO Co-Authored-By footer** across all branch commits + return report
- [ ] **Phase 13 FULLY CLOSED marker** at T-T4.SB.6: CLAUDE.md line-3 + orchestrator-context current-state updates per spec §K + plan §L closure procedure (NOT in executing-plans return report; orchestrator does this at post-merge housekeeping)
- [ ] **Triage-agenda artifact stub** at `docs/phase13-closer-next-phase-triage.md` per §1.5.2 amendment + plan §L
- [ ] **Research-branch artifacts** at `research/harness/aplus_sensitivity/` + `research/studies/aplus-criterion-sensitivity-2026-05-22.md` + `research/method-records/aplus-criteria-calibration.md` per plan §K
- [ ] **Cross-bundle pin row 13 PLANTED + GREEN** per plan §E (4-surface parametrize)
- [ ] **All 7 expansions + Expansion #11 candidate verdict** captured in return report (30th cumulative C.C lesson #6 validation)

---

## §6 References

- **Plan (BINDING)**: [`docs/superpowers/plans/2026-05-22-phase13-t4-sb-closer-plan.md`](superpowers/plans/2026-05-22-phase13-t4-sb-closer-plan.md) at HEAD `9b2a4db`
- **Brainstorming spec (REFERENCE)**: [`docs/superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md`](superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md) at `f7dec0e`
- **Writing-plans dispatch brief (REFERENCE)**: [`docs/phase13-t4-sb-writing-plans-dispatch-brief.md`](phase13-t4-sb-writing-plans-dispatch-brief.md) at `4690933`
- **Writing-plans return report (REFERENCE)**: [`docs/phase13-t4-sb-writing-plans-return-report.md`](phase13-t4-sb-writing-plans-return-report.md) at `9b2a4db`
- **Brainstorming dispatch brief (REFERENCE)**: [`docs/phase13-t4-sb-brainstorming-dispatch-brief.md`](phase13-t4-sb-brainstorming-dispatch-brief.md) at `e75f743`
- **Brainstorming return report (REFERENCE)**: [`docs/phase13-t4-sb-brainstorm-return-report.md`](phase13-t4-sb-brainstorm-return-report.md) at `4299340`
- **T4.SB triage items**: [`docs/phase3e-todo.md:15-101`](phase3e-todo.md)
- **Phase 13 main plan**: [`docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md`](superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md)
- **Phase 13 main spec**: [`docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`](superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md)
- **Research-branch precedents**: [`research/harness/earnings_proximity/`](research/harness/earnings_proximity/) + [`research/studies/earnings-proximity-exclusion.md`](research/studies/earnings-proximity-exclusion.md) + [`research/method-records/earnings-proximity-exclusion.md`](research/method-records/earnings-proximity-exclusion.md) + [`research/method-records/_template.md`](research/method-records/_template.md)
- **Research-branch question (banked)**: [`research/phase-0-tasks.md`](research/phase-0-tasks.md) "Later (deferred)" — A+-like-indicators applied-research entry
- **CLAUDE.md** at repo root (15 cumulative gotchas; #9-#15 BINDING for 30th cumulative validation)

---

## §7 NON-scope (V2 / future arc; explicitly out of T4.SB)

- **Phase 14 dispatch** — deferred per §1.5.2; T-T4.SB.6 closer ships triage-agenda artifact stub, NOT Phase 14 commissioning
- **Research-branch method-record selection meeting** — OQ-CL.3 schedules this post-T4.SB-SHIPPED as separate operator-paired session
- **Schema changes** — T4.SB is schema-UNCHANGED per spec §A.2 LOCK; v21 preserved through executing-plans phase
- **ZERO new Schwab API calls** (L2 LOCK preserved)
- **V2-banked items per writing-plans return report §4** — 10 V1 simplifications banked at writing-plans + inherited V2 candidates from T2.SB6c arc + 14 V1 simplifications from T4.SB brainstorming + Phase 13 main spec §7.4
- **Item 1 V2 enhanced sensitivity diagnostic** — OHLCV criterion-evaluator harness consuming original bars at `candidate.data_asof_date` + substituting per-criterion thresholds + recomputing `bucket_for` end-to-end (per writing-plans return report §4 V1 simplification #1; deferred to V2 per spec V2-DEFERRED operator decision)
- **Item 5 V2 automated retention policy** — R2 (N pipeline_runs) OR R3 (>60 days) automated chart_renders pruning; V1 ships R4 manual prune CLI only (per OQ-5.1 LOCK)
- **Item 5 V2 async-JIT** — HTMX placeholder swap on slow first-render; V1 ships sync JIT no-timeout (per OQ-5.2 LOCK)

---

## §8 Post-executing-plans handback

When executing-plans Codex chain converges to NO_NEW_CRITICAL_MAJOR:

1. **Write return report** at `docs/phase13-t4-sb-executing-plans-return-report.md` per cumulative precedent. Cover:
   - Commit chain shape (6 task commits + 0-5 Codex fix bundles)
   - Per-task Codex chain shape (R1+R2+...+Rn with C/M/m counts; resolution commits)
   - 30th cumulative C.C lesson #6 validation result per-expansion (7 expansions + 4 NEW refinements + Expansion #11 candidate)
   - Forward-binding lessons banked (for future T4-style closer arcs OR future phases)
   - V1 simplifications + V2 candidates banked (with V2 dependency cited)
   - Cumulative streaks (ZERO Co-Authored-By; schema v21 LOCKED; baseline 5670 → ~5760-5805 fast achieved)
   - S1-S5 operator-witnessed gate disposition (per plan §H.4)
   - Triage-agenda artifact disposition (`docs/phase13-closer-next-phase-triage.md` shipped at T-T4.SB.6)
2. **Inline self-verification**:
   - Ruff check (`ruff check swing/` returns clean)
   - Schema unchanged at v21 (verify via `python -c "import sqlite3; ...PRAGMA user_version"` against operator DB OR via `grep -n 'schema_version SET version' swing/data/migrations/*.sql` to confirm no new v22 migration)
   - Test baseline matches plan §F projection (~5760-5805 fast)
   - All operator-witnessed gates either PASS or scheduled for post-merge operator-paired session
3. **Hand back to operator** with summary.

### §8.1 Orchestrator-side next steps post-executing-plans (Turn C or Turn B continuation)

Turn B may continue OR Turn C orchestrator handoff fires per handoff brief `docs/orchestrator-handoff-2026-05-22-PM3-post-T4-SB-writing-plans-dispatch.md` §3.6 context-budget watch.

Whichever instance is active:
- **QA implementer product** per `feedback_orchestrator_qa_implementer_product` (verify file:line + shipped-behavior + locks-preserved against reality on disk; verify per-task acceptance criteria from plan §G)
- **Operator-witnessed S2-S5 gates** per plan §H.4 (S2 browser DOM verification; S3-S5 CLI invocations) — operator-paired browser/CLI session post-merge
- **Merge** `phase13-t4-sb-executing-plans` `--no-ff` to `main`; push
- **Post-merge housekeeping bundle** (CLAUDE.md line 3 refresh **with Phase 13 FULLY CLOSED marker per spec §K** + any NEW gotchas if any + phase3e-todo.md NEW top entry + orchestrator-context.md current state refresh + Prior demote + archive-split per size-check trigger)
- **Phase 13 main plan §H.3 row 13 GREEN** per plan §H.5
- **Cycle-checklist updated** per plan §H.5
- **Post-T4.SB-SHIPPED operator-paired triage meeting** (Phase 14 trigger / Applied Research focus / idle monitoring decision per §1.5.2 amendment) — agenda at `docs/phase13-closer-next-phase-triage.md` (shipped at T-T4.SB.6 closer)
- **Project-cumulative streak update** — count after T-T4.SB.6 closer + housekeeping is ~395-400 commits cumulative ZERO Co-Authored-By trailer drift; cite in commit messages

---

*End of T4.SB executing-plans dispatch brief. 18 OQs operator-locked + 4 §1.5 amendments encoded + plan at `9b2a4db` is BINDING substrate. ~386+ ZERO Co-Authored-By footer streak preserved through writing-plans housekeeping. T4.SB closer arc IN-FLIGHT (brainstorming + writing-plans both SHIPPED; executing-plans FINAL phase before Phase 13 FULLY CLOSED at T-T4.SB.6 closer per spec §K + §1.5.2 amendment triage-agenda artifact). 30th cumulative C.C lesson #6 validation expected at executing-plans handback with all 7 expansions + 4 NEW refinements + Expansion #11 candidate + 15 cumulative gotchas BINDING.*
