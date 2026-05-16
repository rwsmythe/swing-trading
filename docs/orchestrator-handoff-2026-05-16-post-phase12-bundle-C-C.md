# Orchestrator handoff — 2026-05-16 (post-Phase-12-Sub-sub-bundle-C-C-merge; Phase 12 Sub-bundle C 75% shipped; C.D dispatch readiness)

You are taking over as orchestrator for the Swing Trading project at the **post-Phase-12-Sub-sub-bundle-C-C-merge** breakpoint. Sub-bundle C arc is 75% shipped: C.A (foundation; schema v18→v19) + C.B (classifier + validator-shim) + C.C (auto-correction service + reconciliation flow pivot at both `run_schwab_reconciliation` + `run_tos_reconciliation`) all DONE. Sub-sub-bundle C.D (Tier-2 CLI + backfill + Phase 10 banner widening — CLOSES Sub-bundle C) is UNBLOCKED + queued as your first major deliverable when operator commissions.

The prior orchestrator is handing off NOW because:

1. **C.D is the BIG closer.** 16 tasks (T-D.1..T-D.14 + T-D.6.1 + T-D.11); **10-surface operator-witnessed gate per plan §G.4** (largest in project history); 4-6 Codex rounds expected; production-write operation against operator's REAL discrepancies 39/40/41 at S3+S4; **synthetic-fixture-only acceptance test (S6a)** for `--custom-value` payload contract LOCKED post-Codex R6+R7+R8; **operator-real-disposition (S6b)** for DHC 39 production case without contortion; Phase 10 dashboard banner predicate widening retrofits 10 base-layout VMs at S8. Fresh orchestrator gets full token budget for the entire C.D cycle (brief → dispatch → 10-surface gate → merge → housekeeping → Sub-bundle C arc-closer aggregate).
2. **Clean post-merge breakpoint.** C.C SHIPPED + housekeeping pushed + worktree torn down. ZERO in-flight state. 4 NEW C.C code-failure-prevention gotchas promoted to CLAUDE.md (sandbox-at-inner / SELECT-first idempotency / counter staleness / schema-coverage-constant-vs-manual-allowlist). 7 fresh C.D-binding lessons folded into `orchestrator-context.md` from C.C return report §10.
3. **Sub-sub-bundle C.D dispatch is well-defined** — plan at `008dfe4` LOCKED post-6-round writing-plans; C.D section (plan §E lines 2573+) has per-task acceptance criteria + tests + commit shapes; implementer-dispatch-ready when operator commissions.

## ⚠ Critical bootstrap framing

**claude-mem may still be DISABLED** for the operator's evaluation window (started 2026-05-10). You will NOT see SessionStart claude-mem injection blocks. Do NOT attempt `mcp__plugin_claude-mem_mcp-search__*`. Auto-memory dir (`~/.claude/projects/c--Users-rwsmy-swing-trading/memory/MEMORY.md` + linked files) IS still loaded.

**Chrome MCP is AVAILABLE** for browser-driven gates (relevant for C.D S8 — Phase 10 banner predicate widening operator-witnessed verification via `/dashboard` browser walkthrough).

**Fast suite runs `-n auto` by default** at ~88s wall-clock post-Phase-12-Sub-sub-bundle-C-C (4200 fast tests on C.C branch; ~4203 main HEAD post-merge).

**Operator dispatches implementers themselves** (per durable preference `feedback_orchestrator_vs_implementer_execution.md`). Orchestrator drafts the brief + provides inline dispatch prompt as fenced code block; operator dispatches when ready.

**Always provide an inline dispatch prompt** with every brief (per durable preference `feedback_always_provide_inline_dispatch_prompt.md`).

**Commit brief BEFORE inline dispatch prompt** (per durable lesson at `effb995` + auto-memory `feedback_commit_brief_before_inline_prompt.md`). Workflow: Write brief → `git add` + `git commit` SAME orchestrator turn → ONLY THEN provide inline prompt.

**Operator-paired gate driving — one command at a time** (operator's stated preference 2026-05-15). When driving a gate, send ONE command per orchestrator turn, wait for output, verify, send the next. Don't batch. **For C.D specifically: the 10-surface gate is large + production-write — expect a long-haul operator-paired session.**

**Explicit `Co-Authored-By` footer suppression in dispatch prompts** (NEW C.B forward-binding lesson #7; reinforced by C.C ZERO-drift outcome). The dispatch prompt MUST explicitly cite CLAUDE.md "No Claude co-author footer" convention with reference to the C.B R1 fix-bundle recurrence-prevention precedent. Subagent context is ISOLATED; passive CLAUDE.md inheritance is insufficient. C.C dispatch prompt's explicit suppression citation prevented drift — pattern works.

**Pre-Codex orchestrator-side review discipline** (NEW C.C forward-binding lesson #6; saved 1-2 Codex rounds on C.C). When the implementer's chain reports completion, dispatch a focused reviewer subagent with the plan acceptance criteria + brief BINDING contracts as anchors; ask for a deviation list ≤600 words. Pre-Codex review absorbed 2 Major findings on C.C (SC-1 + SC-2). Apply this to C.D — the 10-surface gate's stakes are higher.

**Once operator-witnessed gate passes, integration merge is orchestrator action.** Do NOT ask "shall I proceed with merge."

## Step 1 — Read these in order

1. **This brief end-to-end** — captures post-C.C-merge state + C.D dispatch readiness + 58 cumulative forward-binding lessons inheritance.

2. **`CLAUDE.md` status line** — single-paragraph; updated through Phase 12 Sub-sub-bundle C.C SHIPPED at `0b9d253` + housekeeping at `d92abf3` + gotcha promotions at `94e38ab`. **Authoritative current-state summary.** Includes the 6 V2.1 §VII.F amendment candidates banked from C.C + 4 NEW Gotchas section entries (sandbox-at-inner / SELECT-first idempotency / counter staleness / schema-coverage-constant-vs-manual-allowlist).

3. **`docs/phase3e-todo.md`** top entries in TOP-DOWN order:
   - **Phase 12 Sub-sub-bundle C.C SHIPPED entry** (just-shipped 0b9d253; 6 V2.1 amendments + 7 forward-binding lessons for C.D + 4-surface gate ALL PASS evidence).
   - **Phase 12 Sub-sub-bundle C.B SHIPPED entry** (predecessor; 7 forward-binding lessons for C.C inheritance — STILL load-bearing for C.D for some).
   - **Phase 12 Sub-sub-bundle C.A SHIPPED entry** + earlier entries.

4. **`docs/orchestrator-context.md`** — durable orchestrator-role conventions. Section "Lessons captured" updated 2026-05-16 with:
   - 7 NEW C.B-binding lessons folded post-C.B-ship (classifier→service boundary; validator chain re-invocation; functools.partial composition; `_pass_2_required` substring contract; shape predicate tightening; same-source-keys evidence convergence; Co-Authored-By footer drift suppression).
   - 7 NEW C.D-binding lessons folded post-C.C-ship (schema-coverage-constant ≠ manual-resolver allowlist; outer-tx uniform regardless of sandbox; SELECT-first before payload validation; counter staleness post-loop recompute; DRY helper extraction with lazy import; pre-Codex orchestrator review; implementer self-report accuracy gate).
   - "Currently in-flight work" CURRENT STATE POINTER refreshed to 2026-05-16 + cap-drift note (active section now ~44 entries vs ~30 cap; banked as maintenance-pass dispatch).

5. **`docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md`** (`d682c25`; 1444 lines; LOCKED post-9-round brainstorm) — the BINDING design input for all of Sub-bundle C. **For C.D specifically: read §6 Tier-2 CLI surface (LOCKED V1 CLI-only post-OQ-3); §6.2.1 per-(`ambiguity_kind`, `choice_code`) menu LOCKED post-Codex R5 M#2 + R7 M#2 (11 payload-required + 7 no-payload choices); §8 backfill mechanic (Pass 1 / Pass 2 LOCKED); §15.5 LOCKED revised C.D 10-surface gate mechanic with S6a synthetic-fixture-only + S6b operator-real-disposition.**

6. **`docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md`** (`008dfe4`; 3621 lines; LOCKED post-6-round writing-plans) — the BINDING plan input. Per-task acceptance criteria for all 51 tasks across C.A/C.B/C.C/C.D. **C.A + C.B + C.C sections already shipped + integrated**; you dispatch C.D section next (plan §E lines 2573+; 16 tasks T-D.1..T-D.14 + T-D.6.1 + T-D.11).

7. **`docs/phase12-bundle-C-C-return-report.md`** (`97fc8b9`; on main post-merge) — implementer return report from C.C; §10 contains the 7 forward-binding lessons for C.D + §11 contains the CLAUDE.md status-line refresh draft I already spliced + §5 contains 6 V2.1 §VII.F amendment candidates.

8. **`docs/phase12-bundle-C-C-auto-correction-service-and-flow-pivot-executing-plans-dispatch-brief.md`** (`5ed3e74`) — most recent dispatch brief; format precedent for C.D brief drafting (~320 lines).

9. **`docs/phase12-bundle-C-B-classifier-and-validator-shim-executing-plans-dispatch-brief.md`** (`fdb4276`) — second-most-recent dispatch brief; shows the 7-section format + forward-binding lesson citation pattern.

10. **`docs/phase12-bundle-C-A-foundation-executing-plans-dispatch-brief.md`** (`3cb334d`) — original C.A foundation brief; 245-line shorter shape for shorter bundles (reference only; C.D will be longer).

## Step 2 — Standard bootstrap verification

```bash
git log --oneline -10                    # expect 94e38ab at HEAD (or later if operator landed follow-on commits)
git status                               # expect clean (some untracked operator artifact dirs OK; possibly the 3 phase12-bundle-c-* husks at .worktrees/)
git worktree list                        # expect just main (3 phase12-bundle-c-* husks ACL-locked on disk pending cleanup-script)
python -m pytest -m "not slow" -q | tail -5     # expect ~4200 fast pass + 3 pre-existing phase8 walkthrough failures + 5 skipped
ruff check swing/ --statistics | tail -3        # expect 18 E501
python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"   # expect 19
python -c "from swing.trades.reconciliation_auto_correct import apply_tier1_correction, apply_tier2_resolution, apply_tier3_override, stamp_pending_ambiguity; print('C.C surface OK')"
python -c "from swing.trades.reconciliation_classifier import classify_discrepancy, ClassificationResult; from swing.trades.reconciliation_validators import default_validator_chain; print('C.B surface OK')"
```

Expected state on main HEAD (`94e38ab` or later):
- Phase 12 Sub-sub-bundle C.C SHIPPED at `0b9d253`. Auto-correction service module + flow pivot at both Schwab + TOS reconciliation entry points. 23 commits / 3 Codex rounds / +95 fast tests / ZERO Critical / ZERO ACCEPT-WITH-RATIONALE banked. ZERO Co-Authored-By footer drift (C.B lesson #7 carry-forward worked).
- 4 NEW C.C gotchas promoted to CLAUDE.md (sandbox-at-inner / SELECT-first idempotency / counter staleness / schema-coverage-constant-vs-manual-allowlist).
- Schema v19 (unchanged through C.B + C.C consumer-side).

## Step 3 — Phase 12 Sub-bundle C state at handoff

### §3.1 Commit chain since prior orchestrator handoff (`e52dda7` baseline at session start)

```
94e38ab docs(claude+orchestrator-context): promote 4 NEW C.C code-failure-prevention gotchas to CLAUDE.md + refresh in-flight state pointer pre-handoff
d92abf3 docs(claude+phase3e-todo+orchestrator-context): post-Phase-12-C.C housekeeping — status-line refresh + SHIPPED entry + fold 7 C.D-binding lessons
0b9d253 Merge phase12-bundle-C-C-auto-correction-service-and-flow-pivot into main: Phase 12 Sub-sub-bundle C.C SHIPPED — Auto-correction service + reconciliation flow pivot (...)
97fc8b9 docs(phase12-bundle-c-C): C.C executing-plans return report (3 Codex rounds → NO_NEW_CRITICAL_MAJOR; ZERO ACCEPT-WITH-RATIONALE; +95 fast tests)
8b39ab0 fix(phase12-bundle-c-C): Codex R3 Minor #1 — RESOLUTION_TYPES docstring no longer claims resolve_discrepancy accepts the 9-value widening
b51e083 fix(phase12-bundle-c-C): Codex R2 Major #1 — resolve_discrepancy rejects service-owned lifecycle states with routing hint
1b57327 fix(phase12-bundle-c-C): Codex R1 Major #4 — widen RESOLUTION_TYPES from 5 to 9 values
90d7e1e fix(phase12-bundle-c-C): Codex R1 Major #3 — recompute unresolved_discrepancies_count post-pivot
2055f25 fix(phase12-bundle-c-C): Codex R1 Major #2 — _apply_tier1_correction_inner is SELECT-first for idempotency
65f564f fix(phase12-bundle-c-C): Codex R1 Major #1 — outer apply_tier1_correction always opens BEGIN IMMEDIATE under sandbox
5ed3e74 docs(phase12-bundle-c-C): C.C auto-correction service + reconciliation flow pivot executing-plans dispatch brief
fdb4276 docs(phase12-bundle-c-B): C.B classifier + validator-shim executing-plans dispatch brief
e52dda7 docs(claude+orchestrator-context): fold 3 NEW lessons from Phase 12 Sub-sub-bundle C.A return report  ← SESSION START
... (prior orchestrator's session before this)
```

The full C.B branch chain (26 commits = 14 task-impl + 1 ruff + 4 R1-fix + 2 R2-fix + 1 R2-style + 2 R3-fix + 1 R4-fix + 1 return-report; 5 Codex rounds) folded in via the C.B integration merge `aacd1cd`.

The full C.C branch chain (23 commits = 12 task-impl + 1 ruff + 3 pre-Codex fixes + 4 R1-fix + 1 R2-fix + 1 R3-polish + 1 return-report; 3 Codex rounds) folded in via the C.C integration merge `0b9d253`.

### §3.2 Sub-sub-bundle C status

| Sub-sub-bundle | Status | Branch / Merge SHA | Tasks | Tests delta | Codex rounds | Notes |
|---|---|---|---|---:|---:|---|
| **C.A** Foundation | ✅ SHIPPED 2026-05-15 | `354b6c0` | 9 (T-A.1..T-A.8 + T-A.7) | +104 | 2 | Schema v19; 1 ACCEPT-WITH-RATIONALE banked (backup-gate narrowness) |
| **C.B** Classifier + validator-shim | ✅ SHIPPED 2026-05-15 | `aacd1cd` | 14 (T-B.1..T-B.14) | +139 | 5 | Pure logic; ZERO journal mutations; 4-commit Co-Authored-By footer drift resolved via orchestrator-side rebase pre-merge |
| **C.C** Auto-correction service + flow pivot | ✅ SHIPPED 2026-05-16 | `0b9d253` | 12 (T-C.1..T-C.11 + T-C.3.1) | +95 | 3 | Auto-correction service + flow pivot at BOTH Schwab + TOS; ZERO Codex footer drift (C.B lesson #7 worked); pre-Codex review absorbed 2 Majors |
| **C.D** Tier-2 CLI + backfill + banner widening (CLOSES Sub-bundle C) | 🟡 UNBLOCKED — your first dispatch | TBD | 16 (T-D.1..T-D.14 + T-D.6.1 + T-D.11) | +55..+80 projected | 4-6 estimated | Operator-facing surface; 10-surface gate (largest in project); S6a synthetic-fixture-only acceptance test + S6b operator-real-disposition; Phase 10 banner predicate widening retrofits 10 base-layout VMs |

Recommended dispatch sequencing per spec §12 + plan §C: **C.A → C.B → C.C → C.D strictly sequential** (cross-bundle dependencies enumerated in plan §F pin matrix F-1..F-10; F-2/F-4/F-5/F-6 all closed by C.C ship).

### §3.3 Production state at handoff

- **Schema:** v19 (unchanged since C.A T-A.1 production migration 2026-05-15T18:52:43; consumer-side only through C.B + C.C).
- **Tests:** ~4200 fast passing on main HEAD post-C.C-merge (4200 worktree-side; ~4203 main); 3 pre-existing phase8 walkthrough failures (`tests/integration/test_phase8_pipeline_walkthrough.py`); 5 skipped (Task 7.3 flag-classifier operator-only + 4 Schwab-fixture-not-present CSV-fixture-dependent skips).
- **Production tokens DB:** refresh-token clock from Sub-bundle B S5 issuance (2026-05-15T17:05:00+00:00); expires 2026-05-22T17:05:00+00:00. **~5-6 days remaining at handoff.** C.D dispatch likely consumes 4-7 days. **Operator may need re-auth via `/schwab/setup` web form OR `swing schwab setup` CLI before C.D gate session.** T-A.2 self-healing means recovery is one CLI/web invocation now.
- **Production discrepancy state:** 30+ resolved historical (mostly `acknowledged_immaterial` from operator's manual triage during prior gates) + **3 unresolved-material (39 DHC + 40 VSAT + 41 CVGI)** from pipeline #63 reconciliation_run #10. **LEFT UNRESOLVED BY DESIGN pending Sub-sub-bundle C.D ship** (C.D backfill operation classifies 39/40/41 + auto-applies CVGI 41 tier-1 + sets DHC 39 + VSAT 40 to `pending_ambiguity_resolution`; operator then dispositions via Tier-2 CLI at S6b/S7). **C.C flow pivot is now operationally live** — next pipeline run will dispatch tier-1/tier-2 inline on freshly-emitted discrepancies. The 3 stale discrepancies aren't re-classified by the pivot (it only acts on rows emitted within that run).
- **`reconciliation_corrections` table:** present (schema v19) but EMPTY at handoff. Populated by C.D backfill operation at S3 (CVGI 41 auto-correct).
- **Worktree husks:** **3 pending** at handoff (`.worktrees/phase12-bundle-C-A-foundation/` + `.worktrees/phase12-bundle-C-B-classifier-and-validator-shim/` + `.worktrees/phase12-bundle-C-C-auto-correction-service-and-flow-pivot/`); all ACL-locked; operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` regex `(phase\d+[-_]|schwab(?:-\w+)?-bundle-)` matches all 3 cleanly. Operator-driven cleanup pass.

### §3.4 Forward-binding lessons inherited (58 cumulative through C.C)

- Phase 11 Schwab arc: 5 A + 7 B + 5 C + 0 D = 17 lessons
- Phase 12 Sub-bundle A: 5 lessons (env-var cascade + setup self-healing + camelCase kwarg etc.)
- Phase 12 Sub-bundle B: 12 lessons (return report §10; especially #6 `apply_overrides` discipline + #12 T-A.3 gap pre-emption pattern)
- Phase 12 Sub-bundle C brainstorm: 5 lessons at `effb995` (9-round chain + composition-source empirical verification + Pass-2-tier-1-FORBIDDEN asymmetry + synthetic-fixture acceptance test + CHECK-enum brief-vs-shipped grep)
- Phase 12 Sub-bundle C writing-plans: 2 lessons at `657b8a0` (plan-author schema additions need pre-dispatch escalation + plan-size budget 3000-3700 lines for architectural-pivot)
- Phase 12 Sub-sub-bundle C.A: 3 lessons (backup-gate equality form; schema-CHECK + Python-validator paired work; cross-column CHECK precedence)
- Phase 12 Sub-sub-bundle C.B: 7 lessons (classifier→service boundary; validator chain re-invocation at apply time; `functools.partial` composition; `_pass_2_required` substring contract; shape predicate tightening; same-source-keys evidence convergence; **Co-Authored-By footer drift requires explicit dispatch-prompt suppression**)
- Phase 12 Sub-sub-bundle C.C: 7 lessons (schema-coverage-constant ≠ manual-resolver allowlist; outer-tx uniform regardless of sandbox; SELECT-first before payload validation; counter staleness post-loop recompute; DRY helper extraction across pivot mirrors with lazy import; **pre-Codex orchestrator review catches LOCK divergences cheaply**; implementer self-report accuracy gate)

**Particularly load-bearing for C.D dispatch:**
- **C.C lesson #6 (pre-Codex review)** — apply this to C.D's 10-surface gate stakes by dispatching a focused reviewer subagent before adversarial-critic. Saved 1-2 Codex rounds on C.C.
- **C.B lesson #7 (explicit Co-Authored-By suppression)** — dispatch prompt MUST explicitly cite the CLAUDE.md convention with reference to C.B R1 fix-bundle recurrence-prevention.
- **C.C lesson #1 (schema-coverage-constant ≠ manual-resolver allowlist)** — C.D adds NEW manual CLI surfaces (`resolve-ambiguity` with `--choice` + `--custom-value` flags); the per-(`ambiguity_kind`, `choice_code`) menu validation MUST use a tighter allowlist + reject service-owned states with routing hints.
- **C.C lesson #5 (DRY helper extraction)** — `swing journal discrepancy show-ambiguity` + `resolve-ambiguity` + `override-correction` all consume the C.C service entries; CLI-side helpers should extract common patterns rather than duplicate.

### §3.5 Cross-bundle pin status

**ZERO cross-bundle pins pending.** All C.A T-A.7 pins (`tests/integration/test_phase12_bundle_c_cross_bundle_pin.py` 2 tests) un-skipped at C.B T-B.14 + strengthened to discriminatingly pin classifier + validator-chain behavior end-to-end. Plan §F.1 F-1..F-6 pins all closed by C.B + C.C. F-7/F-8/F-9/F-10 are C.D-side (T-D.5/T-D.3/T-D.10/T-D.10 cross-VM pin).

### §3.6 V2.1 §VII.F amendment candidates banked

**6 NEW amendments from C.C return report §5** (Phase 12 Sub-sub-bundle C.C):
1. **D1 pivot helper relocation** — `_pivot_classify_and_dispatch_for_run` currently lives in `reconciliation_auto_correct.py` but is consumed by both `schwab_reconciliation.py` + `reconciliation.py` via lazy import; V2 candidate to relocate to neutral utility module.
2. **D2 sentinel rule wording** — spec §3.1.1 `__delete__`/`__insert__` sentinel handling could be clarified.
3. **D3 test-side adjustments dependency on C.D filter widening** — Phase 9 Sub-bundle B unresolved-material list filter currently keys on `resolution='unresolved'` only; C.D banner predicate widening to include `pending_ambiguity_resolution` cascades transitively.
4. **D4 SAVEPOINT-uniqueness test mechanic** — current uniqueness assertion relies on PK autoincrement; V2 candidate for explicit unique-name discriminating test.
5. **D5 inline SQL vs repo helpers** — `_step_export` uses inline SQL for the new counters rather than introducing repo helpers; V2 candidate to formalize as `count_discrepancies_pending_ambiguity` / `count_corrections_tier1_recent` repo functions.
6. **D6 T-C.11 scope** + **D7 view_models.py touch** — both scope-boundary clarifications for cross-bundle interaction with Phase 10 (deferred until C.D Phase 10 banner widening lands).

**Earlier banked amendments through C.B (6) + C.A (5) + Phase 9 + 10 + 11 (varies):** cumulative count ~38+ amendments pending V2.1 §VII.F routing. Operator-paced batch processing post-major-arc-closer.

**21 V2 candidates from Sub-bundle C brainstorm + writing-plans + Sub-bundles A+B+C.B+C.C** (per plan §I.1..§I.21 + Sub-bundle B + Sub-sub-bundle B+C return reports). Most prominent:
- **§I.1 V2 mapper widening + auto-VWAP classifier path** — operator-locked next-architectural-dispatch slot (post-C.D ship). Mandatory carry-forward.
- T-B.7 `/schwab/status` web counterpart (Sub-bundle B deferred).
- `surface='web'` CHECK enum widening (v19→v20 schema migration).
- Web Tier-2 surface (OQ-3 V1 CLI-only lock).
- Pivot helper relocation to neutral utility module (C.C D1).

### §3.7 Sub-bundle C arc projected aggregate

Per plan §E + writing-plans return report + actuals through C.C:
- 4 sub-sub-bundles C.A/C.B/C.C/C.D = 51 tasks total
- Codex rounds: C.A 2 (actual) + C.B 5 (actual) + C.C 3 (actual) + C.D 4-6 (projected) = 14-16 substantive rounds (vs writing-plans projection 13-19)
- Tests: +104 (C.A actual) + +139 (C.B actual) + +95 (C.C actual) + +55-80 (C.D projected) = +393-418 fast tests (within plan §H projection +285..+400)
- Final test count: ~4200 main HEAD + +55-80 (C.D) = **~4255-4280 fast tests** post-Sub-bundle-C ship.
- ACCEPT-WITH-RATIONALE: 1 banked (C.A R1 M#1 backup-gate); ZERO banked across C.B + C.C combined (cleanest 2-sub-sub-bundle stretch); C.D may add more given 10-surface gate stakes.

## Step 4 — Sub-sub-bundle C.D dispatch brief drafting (your first major deliverable)

C.D is the **Tier-2 CLI + backfill + Phase 10 banner widening — CLOSES Sub-bundle C** sub-sub-bundle. Per plan §E + spec §6 + §8 + §15.5:

### What the C.D dispatch brief MUST include

Mirror `docs/phase12-bundle-C-C-auto-correction-service-and-flow-pivot-executing-plans-dispatch-brief.md` structure (320 lines; 8 sections). Brief is a worktree-config + scope wrapper; plan §E section is the BINDING input. C.D brief should be longer (~350-400 lines) given the larger scope + 10-surface gate.

1. **§0.1 PLAN_PATH:** `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` (`008dfe4`); SCOPE = Sub-sub-bundle C.D (T-D.1..T-D.14 + T-D.6.1 + T-D.11 per writing-plans return report; 16 tasks total).
2. **§0.2 SPEC_PATH:** same as C.A/C.B/C.C (`d682c25`); read §6 Tier-2 CLI surface + §6.2.1 per-(`ambiguity_kind`, `choice_code`) menu LOCKED enumeration + §8 backfill mechanic (Pass 1 / Pass 2) + §15.5 LOCKED revised 10-surface gate mechanic.
3. **§0.3 Project state:** HEAD = `94e38ab` (current main HEAD post-C.C-merge + housekeeping + gotcha-promotion); ~4200 fast pass baseline; ruff 18 E501; schema v19.
4. **§0.4 Sub-sub-bundle C.D scope:** 16 tasks; plan §E enumerates them — `list-pending-ambiguities` + `show-ambiguity` + `resolve-ambiguity` + `override-correction` CLI + `reconcile-backfill` CLI with `--dry-run` + `--apply` + `--ticker <T>` + `--schwab-api-call-id` (per Codex R3 M#1 revision; operator-explicit not auto-thread); Pass 1 / Pass 2 backfill mechanic per spec §8.4 LOCKED; Phase 10 dashboard banner predicate widening retrofits 10 base-layout VMs per spec §A.5; cycle-checklist + CLAUDE.md gotcha additions.
5. **§0.5 BINDING contracts from plan §E (DO NOT re-litigate):** OQ-3 V1 CLI-only LOCK (web Tier-2 surface is V2 candidate); OQ-5 backfill explicit-only LOCK (NO auto-fire at C.D ship; C.D gate plays operator-witnessed walkthrough role for 39/40/41); OQ-7 Phase 10 banner predicate widening retrofits 10 base-layout VMs + 14 VM-instance regression tests for defense-in-depth; OQ-8 Tier-3 override CLI confirmation prompt + `--force` flag; OQ-20 `custom` choice V1 audit-only narrowing per spec §6.2.1 amendment; spec §15.5 LOCKED revised mechanic for S6a synthetic-fixture-only + S6b operator-real-disposition.
6. **§0.6 Forward-binding lessons inherited:** 58 cumulative + 7 fresh C.D-binding from C.C; especially C.C #1 (manual-resolver allowlist for service-owned states) + C.B #7 (footer suppression) + C.C #6 (pre-Codex review).
7. **§0.7 Test projection:** +55-80 fast tests; final main HEAD post-C.D-merge: ~4255-4280 fast tests.
8. **§1 Worktree + binding conventions:** branch `phase12-bundle-C-D-tier2-cli-and-backfill`; worktree `.worktrees/phase12-bundle-C-D-tier2-cli-and-backfill/`; BASELINE_SHA = `94e38ab` (current main HEAD).
9. **§2 Adversarial review watch items (C.D-specific):** Tier-2 CLI menu validation against tight allowlist (C.C lesson #1); per-choice payload-shape predicate tightening at handler entry (C.B lesson #5); backfill `--apply` production-write classifier soft-block awareness; Phase 10 banner widening retrofits ALL 10 base-layout VMs (per spec §A.5; defense-in-depth 14 regression tests); `surface='cli'` at v19 CHECK constraint preserved (V2 enum widening banked); production-state non-corruption invariants on backfill failure path; `apply_overrides` discipline at any CLI entry constructing Schwab client (C.B lesson #6).
10. **§3 Operator-witnessed gate (C.D 10 surfaces per spec §15.5 + plan §G.4):** S1 inline pytest pass at +55-80; S2 `reconcile-backfill --dry-run` against production projection; S3 `reconcile-backfill --apply --ticker CVGI` against production (tier-1 auto-correct CVGI 41); S4 `--apply --ticker DHC` + `--apply --ticker VSAT` (tier-2 pending ambiguity stamps); S5 `show-ambiguity 39` displays candidate choices; **S6a synthetic-fixture-only acceptance test for `--custom-value` payload contract** (isolated tmp-DB; exercises ALL 11 payload-required + 7 no-payload choices per spec §6.2.1 — per-class assertions for mutation-class / split-class / audit-only-class / no-payload-class); **S6b operator-REAL disposition of DHC 39** per actual data (NO contortion); S7 VSAT 40 disposition per actual data; **S8 Phase 10 dashboard banner clears to ZERO** (verifies banner predicate widening end-to-end); S9 ruff baseline unchanged; S10 cycle-checklist + CLAUDE.md gotcha additions verified.

### Pre-empt the C.D-specific implementer gap class

Per C.B lesson #5 (shape predicate tightening) + C.C lesson #1 (manual-resolver allowlist): C.D introduces MULTIPLE new manual operator-input surfaces (`resolve-ambiguity --choice <code> --custom-value <payload>` + `override-correction <correction_id> --truth-value <payload>`). The `--custom-value` + `--truth-value` payloads consume operator-supplied JSON. **The brief MUST mandate explicit shape predicate checks at handler entry for EACH per-(`ambiguity_kind`, `choice_code`) handler that consumes a payload-required choice:**
- Reject unrecognized keys
- Reject contradictory evidence within payload
- Reject missing-required-fields
- Reject NaN/inf on numeric fields (per C.B Codex R1 M#2 `math.isfinite()` family)

Per-handler discriminating-test pattern: per service-owned-choice, 4-case parametrize (correct-shape happy / unrecognized-key reject / contradictory-field reject / missing-required-field reject). This pre-empts the Codex round-2-round-3 cascade that C.B's `entry_price_mismatch` Shape A/B predicate took (R1 C#1 → R2 M#1 → R3 M#1 → R4 M#1) by designing defensively up-front.

### Pre-empt the synthetic-fixture acceptance test discipline

Per Sub-bundle C brainstorm lesson (synthetic-fixture-only acceptance test for production-write-contract surfaces; banked at `effb995`): the C.D gate S6a + S6b pair was LOCKED post-Codex R6 M#3 + R7 M#3 + R8 M#1+M#2 cascade. The brief MUST cite this LOCK explicitly + the rationale (audit-trail integrity of production DB is binding; forcing operator into contrived dispositions to exercise payload-required contract surfaces would contaminate the audit trail). S6a exercises the FULL payload-contract acceptance test surface in isolated tmp-DBs; S6b dispositions production DHC 39 per operator's REAL data. NO contortion on the real production case.

### Pre-empt the Phase 10 banner widening cross-bundle pin

Per OQ-7 (operator-resolved 2026-05-13 at Phase 10 electives amendment): widen banner predicate from `resolution='unresolved'` only to `resolution IN ('unresolved', 'pending_ambiguity_resolution')`. Three helper functions widen transitively: `count_unresolved_material(conn)` + `list_unresolved_material_for_active_trades(conn)` + `list_unresolved_material_for_trade(conn, trade_id)`. T-D.10 includes 14 VM-instance regression tests for defense-in-depth (per writing-plans §I.10 — 14 VMs across 9 files, NOT 10 as spec §A.5 wording asserts; banked V2.1 §VII.F amendment).

## Step 5 — Sub-sub-bundle C.D arc-closer + Phase 12 status decision (FUTURE)

After C.D ships + integration merge, the **Sub-bundle C arc-closer aggregate banking** is the next housekeeping cycle:
- Compose arc-closer aggregate per Phase 9 + Phase 10 + Phase 11 arc-closer precedents (commit count A+B+C+D; Codex rounds total; +cumulative fast tests; arc-cumulative ACCEPT-WITH-RATIONALE banked; CLAUDE.md gotchas promoted; V2.1 §VII.F amendments pending; V2 candidates banked).
- Bank cumulative forward-binding lessons (+7 C.D = 65 cumulative).
- Update CLAUDE.md status line with Sub-bundle C SHIPPED summary entry.
- Migrate C.A SHIPPED entry to phase3e-todo-archive.md per one-phase-cooldown discipline (C.B + C.C + C.D entries stay in active for cooldown).
- **Phase 12 status decision UNBLOCKED:** close Phase 12 with V2 mapper widening as next-architectural-dispatch slot (operator-locked per OQ-4 disposition 2026-05-15), OR continue with Phase 13 candidate triage.

The 3 production discrepancies (39 DHC + 40 VSAT + 41 CVGI) get dispositioned during C.D gate at S3+S4+S6+S7. **Post-C.D-ship: production discrepancy state is CLEAN** (CVGI 41 `auto_corrected_from_schwab`; DHC 39 + VSAT 40 `operator_resolved_ambiguity`); Phase 10 dashboard banner shows count=0.

## Step 6 — Operator preferences (durable; carry over)

- **Implementer-dispatch is the default** per `feedback_orchestrator_vs_implementer_execution.md`.
- **Once operator-witnessed gate passes, integration merge is orchestrator action.** Do NOT ask "shall I proceed with merge."
- **Worktree-isolated dispatch briefs MUST specify `.worktrees/<branch>/` path explicitly** (binding convention).
- **Implementer runs adversarial-critic via `copowers:executing-plans` wrapper.**
- **Multi-choice format for design questions** (AskUserQuestion preferred).
- **Spec is canonical over brief on cosmetic typos.**
- **Production-write classifier soft-block** — `reconcile-backfill --apply` (C.D) is production-write. Operator pre-authorizes via gate-path AskUserQuestion or plain-chat "yes" if classifier blocks.
- **Always provide an inline dispatch prompt** (per `feedback_always_provide_inline_dispatch_prompt.md`).
- **Commit brief BEFORE inline dispatch prompt** (per `feedback_commit_brief_before_inline_prompt.md` + orchestrator-context lesson at `effb995`).
- **Operator-paired gate driving — one command at a time.** For C.D 10-surface gate: expect a long-haul session.
- **Explicit `Co-Authored-By` footer suppression in dispatch prompts** (NEW C.B forward-binding lesson #7; reinforced by C.C ZERO-drift outcome). Subagent context is ISOLATED; passive CLAUDE.md inheritance is insufficient.
- **Pre-Codex orchestrator-side review** (NEW C.C forward-binding lesson #6) — when implementer chain reports completion, dispatch focused reviewer subagent with plan acceptance criteria + brief BINDING contracts as anchors; saves 1-2 Codex rounds.

## Step 7 — When C.D dispatch brief gets drafted

Threading reminders:

1. **Plan §E (C.D section) is BINDING** — per-task acceptance criteria locked; brief is a worktree-config + scope wrapper.
2. **Synthetic-fixture-only acceptance test (S6a)** is the canonical exercise for the `--custom-value` payload contract; DO NOT exercise the contract on operator's REAL DHC 39 / VSAT 40 production cases (banked brainstorm lesson; spec §15.5 LOCK).
3. **Phase 10 banner predicate widening** retrofits 10 base-layout VMs via 3 shared helper functions; 14 VM-instance regression tests for defense-in-depth.
4. **Backfill is explicit-only** (per OQ-5 LOCK) — NO auto-fire at C.D ship; C.D gate plays operator-witnessed walkthrough role for 39/40/41.
5. **Tier-3 override CLI** with confirmation prompt + `--force` flag (per OQ-8 LOCK; mirrors `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst`).
6. **HTMX gotcha trinity** — N/A V1 (CLI-only lock); banks for V2 web surface.
7. **`apply_overrides` discipline at Schwab entry points** (Sub-bundle B lesson #6) — if C.D backfill constructs `schwabdev.Client(...)` directly (Pass 2 path), MUST `apply_overrides(cfg)` at entry; route-level test asserts cascade-resolved credentials threaded through.
8. **Production refresh-token clock awareness** — expires 2026-05-22; C.D gate may need re-auth via `/schwab/setup` web form first.
9. **`Co-Authored-By` footer suppression** — dispatch prompt MUST cite the CLAUDE.md convention explicitly + reference C.B R1 fix-bundle recurrence-prevention precedent.
10. **Pre-Codex orchestrator-side review** — dispatch focused reviewer subagent BEFORE invoking adversarial-critic; absorb LOCK divergences pre-Codex; saved 1-2 rounds on C.C.

## Step 8 — Quick reference summary

| Artifact | Path / commit |
|---|---|
| Spec (BINDING) | `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md` (`d682c25`; 1444 lines; NO_NEW_CRITICAL_MAJOR after 9 rounds) |
| Plan (BINDING) | `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` (`008dfe4`; 3621 lines; NO_NEW_CRITICAL_MAJOR after 6 rounds) |
| C.A executing-plans dispatch brief | `docs/phase12-bundle-C-A-foundation-executing-plans-dispatch-brief.md` (`3cb334d`) |
| C.A return report | `docs/phase12-bundle-C-A-return-report.md` (`56e6993`) |
| C.A integration merge | `354b6c0` |
| C.B executing-plans dispatch brief | `docs/phase12-bundle-C-B-classifier-and-validator-shim-executing-plans-dispatch-brief.md` (`fdb4276`) |
| C.B return report | `docs/phase12-bundle-C-B-return-report.md` (`c48188a` post-rebase; on main post-merge `aacd1cd`) |
| C.B integration merge | `aacd1cd` |
| C.C executing-plans dispatch brief | `docs/phase12-bundle-C-C-auto-correction-service-and-flow-pivot-executing-plans-dispatch-brief.md` (`5ed3e74`) |
| C.C return report | `docs/phase12-bundle-C-C-return-report.md` (`97fc8b9`; on main post-merge `0b9d253`) |
| C.C integration merge | `0b9d253` |
| C.D executing-plans dispatch brief | TBD (your first deliverable) |
| Cross-phase backlog | `docs/phase3e-todo.md` (active; archive at `docs/phase3e-todo-archive.md`) |
| Orchestrator-role context | `docs/orchestrator-context.md` (updated 2026-05-16 with 14 NEW lessons from C.B + C.C return reports) |
| Previous handoff brief | `docs/orchestrator-handoff-2026-05-15-post-phase12-bundle-C-A.md` (`1156202`) |

## Step 9 — Closing note from prior orchestrator

This handoff caps a focused 2-sub-sub-bundle session that drove **2 substantive artifacts** across the Phase 12 Sub-bundle C arc:

1. **Sub-sub-bundle C.B** triage (operator-decision gate posture + 4-commit Co-Authored-By footer rebase-strip pre-merge) → 3-surface gate via Chrome MCP-equivalent (S1 fast suite + S2 explicit python -c CVGI/DHC/VSAT walkthrough + S3 ruff) → integration merge `aacd1cd` → housekeeping (status-line refresh + phase3e-todo SHIPPED entry + 7 forward-binding lessons folded into orchestrator-context.md) → C.C dispatch brief `5ed3e74`;
2. **Sub-sub-bundle C.C** triage (operator-decision gate posture + ZERO footer drift outcome) → 4-surface gate (S1 + S2 explicit production-env walkthrough exercising apply_tier1_correction service end-to-end + S3 explicit sandbox-env walkthrough verifying short-circuit + S4 ruff) → integration merge `0b9d253` → housekeeping (status-line refresh + phase3e-todo SHIPPED entry + 7 forward-binding lessons folded into orchestrator-context.md) → pre-handoff gotcha-promotion commit `94e38ab` (4 NEW C.C gotchas to CLAUDE.md).

**Key story arcs of this session:**

1. **C.B's Co-Authored-By footer drift caught + resolved via orchestrator-side rebase pre-merge.** R1 fix-bundle 4 commits accidentally carried the footer despite CLAUDE.md `No Claude co-author footer` convention. Subagent context is ISOLATED — passive CLAUDE.md inheritance is insufficient. **NEW lesson #7 banked**: explicit Co-Authored-By suppression in dispatch prompts. **C.C carry-forward worked** — dispatch prompt's explicit citation of CLAUDE.md convention + reference to C.B precedent prevented recurrence (ZERO drift across 23 commits).

2. **C.C's pre-Codex orchestrator-side review absorbed 2 Major findings** (SC-1 sandbox-threading + SC-2 T-C.11 E2E scope) saving an estimated 1-2 Codex rounds. **NEW lesson #6 banked**: pre-Codex review as a cheap orchestrator-side discipline. **Pattern is reusable**: dispatch focused reviewer subagent with plan acceptance criteria + brief BINDING contracts as anchors; ask for deviation list ≤600 words.

3. **Sub-bundle C arc is now 75% shipped with ZERO ACCEPT-WITH-RATIONALE banked across C.B + C.C combined** (only C.A had 1; cleanest 2-sub-sub-bundle stretch in the arc). The discipline is paying compound interest: 4 NEW Codex-promoted CLAUDE.md gotchas from C.C + 14 NEW orchestrator-context.md lessons from C.B + C.C reduce future Codex round burn.

4. **C.D handoff PRE-dispatch (not post-dispatch).** The prior precedent was hand off mid-arc; this handoff is at a CLEANER breakpoint (post-merge + housekeeping done + ZERO in-flight state). Operator's reasoning: C.D's 10-surface gate + production-write + 16-task scope is the heaviest single sub-sub-bundle; fresh orchestrator gets full token budget for the entire C.D cycle including arc-closer.

Sub-sub-bundle C.D is well-defined as a 16-task closer (Tier-2 CLI + backfill + Phase 10 banner widening) with the LARGEST gate in the project (10 surfaces including production backfill of operator's REAL discrepancies 39/40/41). Synthetic-fixture-only acceptance test discipline is LOCKED at S6a; operator-real-disposition at S6b without contortion. Brief should be ~350-400 lines (longer than C.C's 320) given the multi-CLI surface + Phase 10 banner predicate widening + 10-surface gate. Adversarial review expected 4-6 Codex rounds.

**Operator preference reaffirmed via this session:** the pre-Codex orchestrator-side review discipline (saved 1-2 Codex rounds on C.C) is now durable + folded into both `orchestrator-context.md` AND the C.D dispatch prompt template. Pattern complement to "Implementer self-report accuracy gate" lesson — both about distinguishing "tests pass" from "fix matches LOCK".

Good luck.

---

*End of handoff brief. Post-Phase-12-Sub-sub-bundle-C-C-merge orchestrator transition. Phase 12 Sub-bundle C 75% shipped (C.A + C.B + C.C done). Sub-sub-bundle C.D (Tier-2 CLI + backfill + Phase 10 banner widening — CLOSES Sub-bundle C) UNBLOCKED — your first dispatch. Operator-paced.*
