# Orchestrator handoff — 2026-05-15 (post-Phase-12-Sub-sub-bundle-C-A-merge; Phase 12 Sub-bundle C 33% shipped; C.B/C.C/C.D dispatch readiness)

You are taking over as orchestrator for the Swing Trading project at the **post-Phase-12-Sub-sub-bundle-C-A-merge** breakpoint. The architectural-pivot brainstorm + writing-plans for Sub-bundle C are LOCKED + shipped; Sub-sub-bundle C.A foundation (schema migration 0019 atomic v18→v19) is SHIPPED + integrated + production-migrated. Sub-sub-bundle C.B (classifier + validator-shim modules) is UNBLOCKED + queued as your first major deliverable when operator commissions. C.C (auto-correction service + reconciliation flow pivot) + C.D (Tier-2 CLI + backfill + Phase 10 banner predicate widening) queued behind C.B.

The prior orchestrator is handing off NOW because:
1. **Context budget management** — the prior session executed 8 sub-bundle/sub-sub-bundle artifacts (Sub-bundle B brief→dispatch→gate→merge; Sub-bundle C brainstorm→triage; Sub-bundle C writing-plans→triage; Sub-sub-bundle C.A brief→dispatch→merge); fresh-context-budget orchestrator handles the remaining C.B + C.C + C.D dispatches (especially C.D with its 10-surface gate + synthetic-fixture-only acceptance test discipline).
2. **Clean breakpoint** — Sub-sub-bundle C.A SHIPPED + integrated + production-migrated; matches the post-12A handoff state precedent (which itself triggered the prior orchestrator's session).
3. **Sub-sub-bundle C.B dispatch is well-defined** — plan at `008dfe4` LOCKED post-6-round writing-plans; C.B section in plan has per-task acceptance criteria + tests + commit shapes; implementer-dispatch-ready when operator commissions.

## ⚠ Critical bootstrap framing

**claude-mem may still be DISABLED** for the operator's evaluation window (started 2026-05-10). You will NOT see SessionStart claude-mem injection blocks. Do NOT attempt `mcp__plugin_claude-mem_mcp-search__*`. Auto-memory dir (`~/.claude/projects/c--Users-rwsmy-swing-trading/memory/MEMORY.md` + linked files) IS still loaded.

**Chrome MCP is AVAILABLE** for browser-driven gates (relevant for C.D `/schwab/setup` workflows if banner predicate widening surfaces require browser verification).

**Fast suite runs `-n auto` by default** at ~74s wall-clock post-Phase-12-Sub-sub-bundle-C-A (3966 fast tests on main HEAD).

**Operator dispatches implementers themselves** (per durable preference `feedback_orchestrator_vs_implementer_execution.md`). Orchestrator drafts the brief + provides inline dispatch prompt as fenced code block; operator dispatches when ready.

**Always provide an inline dispatch prompt** with every brief (per durable preference `feedback_always_provide_inline_dispatch_prompt.md`).

**Commit brief BEFORE inline dispatch prompt** (per durable lesson at `effb995` + auto-memory `feedback_commit_brief_before_inline_prompt.md`). Workflow: Write brief → `git add` + `git commit` SAME orchestrator turn → ONLY THEN provide inline prompt. Worktrees branch from local main HEAD at `git worktree add` time; untracked briefs don't propagate.

**Operator-paired gate driving — one command at a time** (operator's stated preference 2026-05-15). When driving a gate, send ONE command per orchestrator turn, wait for output, verify, send the next. Don't batch.

**Once operator-witnessed gate passes, integration merge is orchestrator action.** Do NOT ask "shall I proceed with merge."

## Step 1 — Read these in order

1. **This brief end-to-end** — captures post-C.A-merge state + C.B/C.C/C.D dispatch readiness + 44 cumulative forward-binding lessons inheritance.

2. **`CLAUDE.md` status line** — single-paragraph; updated through Phase 12 Sub-sub-bundle C.A SHIPPED at `354b6c0` + housekeeping at `b24e9e2` + `4a390a4`. **Authoritative current-state summary.** Includes the 5 V2.1 §VII.F amendment candidates banked from C.A.

3. **`docs/phase3e-todo.md`** top entries in TOP-DOWN order:
   - **Phase 12 Sub-sub-bundle C.A SHIPPED entry** (just-shipped 354b6c0; 5 V2.1 amendments + 7 forward-binding lessons for C.B + production migration confirmed schema v19).
   - **Phase 12 Sub-bundle B SHIPPED entry** (predecessor; web-UI-friendliness; 12 forward-binding lessons for C dispatch inheritance).
   - **Sub-bundle B-related fulfilled entries** (web-UI OAuth + credentials-in-file — now retained one-phase-cooldown per retention discipline).
   - **ARCHITECTURAL: reconciliation must auto-correct journal-from-Schwab** (Sub-bundle C HEADLINE; entry at `28a7d01` + `75b876c`; spec §1.3 binding constraints inherit verbatim).
   - **Phase 12 Sub-bundle A SHIPPED entry** + **Phase 11 CLOSED entry**.

4. **`docs/orchestrator-context.md`** — durable orchestrator-role conventions. Section "Lessons captured" updated 2026-05-15 with:
   - 5 NEW Sub-bundle C brainstorm lessons (at `effb995`): 9-round high-water mark; composition-source empirical verification; Pass-2-tier-1-FORBIDDEN asymmetry; synthetic-fixture acceptance test for production-write-contracts; CHECK-enum brief-vs-shipped grep.
   - 2 NEW Sub-bundle C writing-plans lessons (at `657b8a0`): plan-author schema additions need pre-dispatch escalation; plan-size budget for architectural-pivot writing-plans (3000-3700 lines).
   - (NEW lesson candidate from C.A — not yet folded; see §3.4 below): R1 ACCEPT-WITH-RATIONALE on backup-gate narrowness pattern + 7 C.B forward-binding lessons.

5. **`docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md`** (`d682c25`; 1444 lines; LOCKED post-9-round brainstorm) — the BINDING design input for all of Sub-bundle C. Read §1.3 four operator-locked constraints + §3 schema design + §4 classifier + §5 service architecture + §10 three discriminating examples (CVGI 41 + DHC 39 + VSAT 40) + §14 15 OQs (all triaged; 5 operator-resolved + 4 LOCKED-in-spec + 4 writing-plans-decides + 2 V2-banked + OQ-20 writing-plans-author flagged ACCEPTED V1 audit-only narrowing).

6. **`docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md`** (`008dfe4`; 3621 lines; LOCKED post-6-round writing-plans) — the BINDING plan input. Per-task acceptance criteria for all 51 tasks across C.A/C.B/C.C/C.D. **C.A section already shipped + integrated**; you dispatch C.B section next.

7. **`docs/phase12-bundle-C-A-return-report.md`** (`56e6993`; on main post-merge) — implementer return report from C.A; §11 + §15 contain the 7 forward-binding lessons for C.B + per-task LOCKs + V2.1 §VII.F amendment candidates.

8. **`docs/phase12-bundle-C-A-foundation-executing-plans-dispatch-brief.md`** (`3cb334d`) — most recent dispatch brief; format precedent for C.B brief drafting.

## Step 2 — Standard bootstrap verification

```bash
git log --oneline -10                    # expect 4a390a4 at HEAD (or later if operator landed follow-on commits)
git status                               # expect clean (some untracked operator artifact dirs OK)
git worktree list                        # expect main + 1 husk (.worktrees/phase12-bundle-A-schwab-operational-pain) — operator cleanup-script pending; C.A worktree cleaned at handoff
python -m pytest -m "not slow" -q | tail -5     # expect ~3966 fast pass + 3 pre-existing test_phase8_pipeline_walkthrough failures + 3 skipped (flag-classifier + C.A cross-bundle pin + 1 other)
ruff check swing/ --statistics | tail -3        # expect 18 E501
python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"   # expect 19
```

Expected state on main HEAD (`4a390a4` or later):
- Phase 12 Sub-sub-bundle C.A SHIPPED at `354b6c0`. Migration 0019 atomic v18→v19 (1 new table `reconciliation_corrections` + 3 ALTER ADD columns + 2 CHECK enum widenings via table-rebuild). 16 commits / 2 Codex rounds / +104 fast tests / ZERO Critical / 1 ACCEPT-WITH-RATIONALE banked (backup-gate narrowness; matches Phase 9 A precedent). Production DB at schema v19 confirmed via `swing db-migrate` 2026-05-15T18:52:43 with backup at `swing-20260515T185243.db`.
- Schema v19.

## Step 3 — Phase 12 Sub-bundle C state at handoff

### §3.1 Commit chain since prior orchestrator handoff (`4ed1892` baseline at session start)

```
4a390a4 docs(phase3e-todo): Phase 12 Sub-sub-bundle C.A SHIPPED entry + 5 V2.1 §VII.F amendments banked + 7 forward-binding lessons for C.B
b24e9e2 docs(CLAUDE): refresh status line with Phase 12 Sub-sub-bundle C.A SHIPPED at 354b6c0
354b6c0 Merge phase12-bundle-C-A-foundation into main: Phase 12 Sub-sub-bundle C.A SHIPPED — Schema foundation for auto-correct reconciliation (migration 0019 atomic v18→v19; 1 new table reconciliation_corrections + 3 ALTER ADDs + 2 CHECK enum widenings; ZERO behavioral changes; 2 Codex rounds NO_NEW_CRITICAL_MAJOR; 16 commits)
3cb334d docs(phase12): Phase 12 Sub-sub-bundle C.A foundation executing-plans dispatch brief
657b8a0 docs(orchestrator-context): fold 2 new lessons from Phase 12 Sub-bundle C writing-plans
008dfe4 docs(phase12): Phase 12 Sub-bundle C plan — Codex R1-R6 fixes (NO_NEW_CRITICAL_MAJOR converged)
d3fc073 docs(phase12): Phase 12 Sub-bundle C auto-correct reconciliation writing-plans plan
93ceb8c docs(phase12): Phase 12 Sub-bundle C writing-plans dispatch brief
effb995 docs(orchestrator-context): fold 5 new lessons from Phase 12 Sub-bundle C brainstorm 9-round chain
d682c25 docs(phase12): Phase 12 Sub-bundle C spec — Codex R9 minor cleanups (NO_NEW_CRITICAL_MAJOR converged)
... (8 prior Codex-fix commits in spec chain + 8 prior commits in Sub-bundle B + C brainstorm chain)
```

### §3.2 Sub-sub-bundle C status

| Sub-sub-bundle | Status | Branch / Merge SHA | Tasks | Tests delta | Codex rounds | Notes |
|---|---|---|---|---:|---:|---|
| **C.A** Foundation | ✅ SHIPPED 2026-05-15 | `354b6c0` | 9 (T-A.1..T-A.8 + T-A.7) | +104 net | 2 | Schema v19; 1 new table + 5 schema deltas; ZERO behavioral changes; production-migrated 2026-05-15T18:52:43 |
| **C.B** Classifier + validator-shim | 🟡 UNBLOCKED — your first dispatch | TBD | 14 (T-B.1..T-B.14) | +55..+95 projected | 3-5 estimated | Pure logic; no journal mutations; un-skips 2 cross-bundle pin tests at T-B.1 + T-B.2; classifier output shape locked in spec §4 |
| **C.C** Auto-correction service + flow pivot | ⏸ BLOCKED on C.B | TBD | 12 (T-C.1..T-C.11 + T-C.3.1) | +65..+115 projected | 4-6 estimated | Transactional discipline (reject caller-held tx); pivots `run_schwab_reconciliation` AND `run_tos_reconciliation` from emit+wait to classify+dispatch+apply |
| **C.D** Tier-2 CLI + backfill + banner widening (CLOSES Sub-bundle C) | ⏸ BLOCKED on C.A+C.B+C.C | TBD | 16 (T-D.1..T-D.14 + T-D.6.1 + T-D.11) | +55..+80 projected | 4-6 estimated | Operator-facing surface; 10-surface gate including synthetic-fixture-only acceptance test for `--custom-value` payload contract; Phase 10 banner predicate widening retrofits 10 base-layout VMs |

Recommended dispatch sequencing per spec §12 + plan §C: **C.A → C.B → C.C → C.D strictly sequential** (cross-bundle dependencies enumerated in plan §F pin matrix F-1..F-10).

### §3.3 Production state at handoff

- **Schema:** v19 (production-migrated 2026-05-15T18:52:43; backup at `swing-20260515T185243.db`).
- **Tests:** 3966 fast passing on main; 3 pre-existing phase8 walkthrough failures (`tests/integration/test_phase8_pipeline_walkthrough.py`); 3 skipped (flag-classifier Task 7.3 operator-only + C.A cross-bundle pin un-skips at C.B T-B.2 + 1 other).
- **Production tokens DB:** refresh-token clock from Sub-bundle B S5 issuance (2026-05-15T17:05:00+00:00); expires 2026-05-22T17:05:00+00:00. **~6 days remaining at handoff.** C.B dispatch likely consumes 2-3 days; C.C 3-5 days; C.D 4-7 days. **Operator may need re-auth via `/schwab/setup` web form OR `swing schwab setup` CLI before C.D gate session.** T-A.2 self-healing means recovery is one CLI/web invocation now.
- **Production discrepancy state:** 30+ resolved historical (mostly `acknowledged_immaterial` from operator's manual triage during 11 + 12A gates) + 3 unresolved-material (39 DHC + 40 VSAT + 41 CVGI from pipeline #63 reconciliation_run #10). **LEFT UNRESOLVED BY DESIGN pending Sub-sub-bundle C.D ship** (C.D backfill operation classifies 39/40/41 + auto-applies CVGI 41 tier-1 + sets DHC 39 + VSAT 40 to `pending_ambiguity_resolution`; operator then dispositions via Tier-2 CLI).
- **`reconciliation_corrections` table:** present (schema v19) but EMPTY at handoff. Populated by C.C auto-correction service + C.D backfill.
- **Worktree husks:** likely 1 pending (`.worktrees/phase12-bundle-A-schwab-operational-pain/` from 12A); C.A worktree cleaned at handoff (operator's PowerShell shell may have been inside the deleted dir; they should `cd ..` to recover); operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` regex matches `phase12-*` cleanly.

### §3.4 Forward-binding lessons inherited (44 cumulative through C.A)

- Phase 11 Schwab arc: 5 A + 7 B + 5 C + 0 D = 17 lessons
- Phase 12 Sub-bundle A: 5 lessons (env-var cascade + setup self-healing + camelCase kwarg etc.)
- Phase 12 Sub-bundle B: 12 lessons (return report §10; especially #6 `apply_overrides` discipline + #12 T-A.3 gap pre-emption pattern)
- Phase 12 Sub-bundle C brainstorm: 5 NEW lessons at `effb995` (9-round chain + composition-source empirical verification + Pass-2-tier-1-FORBIDDEN asymmetry + synthetic-fixture acceptance test + CHECK-enum brief-vs-shipped grep)
- Phase 12 Sub-bundle C writing-plans: 2 NEW lessons at `657b8a0` (plan-author schema additions need pre-dispatch escalation + plan-size budget 3000-3700 lines for architectural-pivot)
- Phase 12 Sub-sub-bundle C.A: 3 NEW lessons (from C.A return report §11; not yet folded — orchestrator may bank if relevant for C.B/C/D):
  1. **Backup-gate equality form** — `pre_version == (target - 1)` strict equality NOT `pre_version <= (target - 1)`. Match Phase 9 Sub-bundle A precedent verbatim.
  2. **Schema-CHECK + Python-validator paired work** — any new column with CHECK enum at schema time + Python constant + validator in dataclass MUST land in same task for atomic consistency.
  3. **Cross-column CHECK precedence** — schema CHECK is defense-in-depth; app-layer enforcement in service-time (C.C scope) is primary path. C.A schema-defended; C.C service-defended.

**Recommendation:** fold C.A lessons #1+#2+#3 into orchestrator-context.md as part of post-handoff housekeeping (mirrors the prior orchestrator's lesson-folding pattern at `effb995` + `657b8a0`).

### §3.5 Cross-bundle pin status

**1 cross-bundle pin pending** at `tests/integration/test_phase12_bundle_c_cross_bundle_pin.py` (skip-decorated; un-skips at C.B T-B.1 + T-B.2 landing — validator-shim module ships in Sub-sub-bundle C.B). Plan §B.F pin matrix enumerates the cross-bundle dependencies; F-1..F-10 covers classifier interfaces (C.B exposes; C.C consumes), audit-row shapes (C.A defined; C.C populates), and VM mixin signatures (C.A schema underpins; C.D retrofits).

### §3.6 V2.1 §VII.F amendment candidates banked from C.A + writing-plans

**5 NEW amendments from C.A return report:**
1. Spec §3.1 column-count header drift (header text "19 columns" vs table-row enumeration 20; §I.16 in plan).
2. Plan §A.12 Phase 11 backup-gate precedent claim (no such gate exists; actual precedent is Phase 9 Sub-bundle A).
3. Plan §B.4 SHA256 byte-equality impossibility with SQLite `Connection.backup` (Codex R2 Minor #1 correction at `0e26d2b`).
4. Dispatch brief §0.5 `pre_version <= 18` vs `== 18` equality form.
5. Plan §B.2 `_RESOLUTION_VALUES` widening fold-into T-A.2 (atomic-consistency improvement).

**21 V2 candidates from Sub-bundle C brainstorm + writing-plans + Sub-bundle B** (per plan §I.1..§I.21 + Sub-bundle B SHIPPED entry + Sub-bundle A V2 candidate list). Most prominent:
- **§I.1 V2 mapper widening + auto-VWAP classifier path** — operator-locked next-architectural-dispatch slot (post-C.D ship). Mandatory carry-forward.
- T-B.7 `/schwab/status` web counterpart (Sub-bundle B deferred).
- `surface='web'` CHECK enum widening (v19→v20 schema migration).
- Web Tier-2 surface (OQ-3 V1 CLI-only lock).

### §3.7 Sub-bundle C arc projected aggregate

Per plan §E + writing-plans return report:
- 4 sub-sub-bundles C.A/C.B/C.C/C.D = 51 tasks total
- Codex rounds projected: C.A 2 (actual) + C.B 3-5 + C.C 4-6 + C.D 4-6 = 13-19 substantive rounds
- Tests projected: +104 (C.A actual) + 55-95 (C.B) + 65-115 (C.C) + 55-80 (C.D) = +279-394 fast tests
- Final test count: 3966 (C.A actual) + 175-290 (C.B+C+D projected) = **~4141-4256 fast tests** post-Sub-bundle-C ship.
- ACCEPT-WITH-RATIONALE: 1 already banked (C.A R1 M#1 backup-gate); C.B/C/D may add more.

## Step 4 — Sub-sub-bundle C.B dispatch brief drafting (your first major deliverable)

C.B is the **Classifier + validator-shim modules** sub-sub-bundle. Per plan §B C.B section + spec §4 + §5.5:

### What the C.B dispatch brief MUST include

Mirror `docs/phase12-bundle-C-A-foundation-executing-plans-dispatch-brief.md` structure (244 lines; 8 sections). Brief is a worktree-config + scope wrapper; plan §B section is the BINDING input.

1. **§0.1 PLAN_PATH:** `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` (`008dfe4`); SCOPE = Sub-sub-bundle C.B (T-B.1..T-B.14 per writing-plans return report; 14 tasks total).
2. **§0.2 SPEC_PATH:** same as C.A (`d682c25`); read §4 classifier + §5.5 validator-shim module + §10 discriminating examples.
3. **§0.3 Project state:** HEAD = `4a390a4` (current main HEAD post-C.A merge + housekeeping); 3966 fast pass baseline; ruff 18 E501; schema v19.
4. **§0.4 Sub-sub-bundle C.B scope:** 14 tasks; plan author's return report lists them per plan §B; brief enumerates task table mirroring C.A brief §0.4.
5. **§0.5 BINDING contracts from plan §B (DO NOT re-litigate):** validator-shim module location at `swing/trades/reconciliation_validators.py` (per spec §5.5 LOCK + OQ-14 LOCK); per-discrepancy-type sub-classifier architecture; determinism principle (when in doubt, tier-2); validator-respecting downgrade rule; Pass-2-tier-1-FORBIDDEN lock for Pass-2 re-fetched data (per spec §8.4 + V1 mapper limitation).
6. **§0.6 Forward-binding lessons inherited:** 44 cumulative + 3 from C.A return report; especially the determinism principle + composition-source empirical verification + Pass-2-tier-1-FORBIDDEN asymmetry.
7. **§0.7 Test projection:** +55-95 fast tests; final main HEAD post-C.B-merge: ~4021-4061 fast tests.
8. **§1 Worktree + binding conventions:** branch `phase12-bundle-C-B-classifier-and-validator-shim`; worktree `.worktrees/phase12-bundle-C-B-classifier-and-validator-shim/`; BASELINE_SHA = `4a390a4` (current main HEAD).
9. **§2 Adversarial review watch items (C.B-specific):** classifier output shape per spec §4; validator-shim 4 callable predicates per spec §5.5; determinism principle binding discriminator (when in doubt, tier-2); Pass-2-tier-1-FORBIDDEN classifier-side enforcement; discriminating tests against CVGI 41 + DHC 39 + VSAT 40 fixtures (per spec §10).
10. **§3 Operator-witnessed gate (C.B 3 surfaces per spec §15.5 + plan §G):** S1 inline pytest pass at +55-95; S2 classifier against 39/40/41 fixtures emits expected ClassificationResult shapes; S3 ruff baseline unchanged.

### Pre-empt the analogous Sub-bundle B T-A.3 implementer gap class

Per writing-plans plan §J forward-binding lesson #12 + Sub-bundle B's gate-caught defect precedent: C.B is pure logic (no journal mutations); the analogous "implementer gap class" risk is the **classifier emitting tier-1 for cases that should be tier-2 due to V1 mapper limitations**. Brief MUST mandate discriminating tests that EXPLICITLY exercise the V1 mapper boundary cases:
- CVGI 41 with persisted Pass-1 JSON → tier-1 (works; CVGI is the operator-locked tier-1 path).
- DHC 39 + VSAT 40 re-fetched via Pass-2 `get_account_orders` → MUST emit tier-2 even when payload superficially looks like a tier-1 case (multi-partial structure could naively redirect to tier-1; classifier MUST downgrade to tier-2 due to mapper exposing only order-level not execution-level data).

Discriminating-test pattern: plant a Pass-2 response where naive tier-1 redirect would compute a target value; assert classifier emits `(tier=2, ambiguity_kind='multi_partial_vs_consolidated', correction_target=None)` regardless.

## Step 5 — Sub-sub-bundle C.C + C.D dispatches (FUTURE)

C.C is auto-correction service + reconciliation flow pivot. Will need: transactional discipline review (reject caller-held tx; BEGIN IMMEDIATE / COMMIT / ROLLBACK); validator chain composition (NEW `swing/trades/reconciliation_validators.py` shim module shipped at C.B as 4 callable predicates); idempotency contract; surface-aware audit attribution; flow pivot at `run_schwab_reconciliation` AND `run_tos_reconciliation` callsites.

C.D is Tier-2 CLI + backfill + Phase 10 banner predicate widening. Will need:
- **Synthetic-fixture-only acceptance test for `--custom-value` payload contract** (per orchestrator-context.md NEW lesson at `effb995` + plan §G C.D gate-section LOCKED revised mechanic). DO NOT exercise payload-required CLI contract against operator's REAL production DHC 39 / VSAT 40 cases; isolated synthetic-fixture DB pathway.
- **Phase 10 dashboard banner predicate widening** to include `'pending_ambiguity_resolution'` alongside `'unresolved'` (per OQ-7 operator-resolved). Plan §G C.D notes 3 shared helper functions widen transitively; T-D.10 includes 14 VM-instance regression tests for defense-in-depth.
- **Backfill against production 39/40/41** at gate (per spec §10 worked examples; per plan §G C.D gate S3+S4+S6+S7). CVGI 41 → auto-correct tier-1; DHC 39 + VSAT 40 → pending_ambiguity_resolution; operator dispositions per real data without contortion.
- **Tier-3 override CLI** with confirmation prompt + `--force` flag (per OQ-8 operator-resolved).

## Step 6 — Operator preferences (durable; carry over)

- **Implementer-dispatch is the default** per `feedback_orchestrator_vs_implementer_execution.md`.
- **Once operator-witnessed gate passes, integration merge is orchestrator action.** Do NOT ask "shall I proceed with merge."
- **Worktree-isolated dispatch briefs MUST specify `.worktrees/<branch>/` path explicitly** (binding convention).
- **Implementer runs adversarial-critic via `copowers:executing-plans` wrapper.**
- **Multi-choice format for design questions** (AskUserQuestion preferred).
- **Spec is canonical over brief on cosmetic typos.**
- **Production-write classifier soft-block** — `swing db-migrate` (C.A) + `reconcile-backfill --apply` (C.D) all are production-write actions. Operator pre-authorizes via gate-path AskUserQuestion or plain-chat "yes" if classifier blocks.
- **Always provide an inline dispatch prompt** (per `feedback_always_provide_inline_dispatch_prompt.md`).
- **Commit brief BEFORE inline dispatch prompt** (per `feedback_commit_brief_before_inline_prompt.md` + orchestrator-context lesson at `effb995`). Mandatory discipline.
- **Operator-paired gate driving — one command at a time.** When driving a gate, send ONE command per turn, wait for output, verify, send the next. Don't batch.

## Step 7 — When C.B dispatch brief gets drafted

Threading reminders:

1. **Plan §B (C.B section) is BINDING** — per-task acceptance criteria locked; brief is a worktree-config + scope wrapper.
2. **NEW lesson at `657b8a0`: plan-author schema additions during executing-plans need pre-dispatch escalation.** If C.B implementer encounters a need for a schema element NOT in plan + spec, STOP + escalate. C.B should NOT touch schema (C.A already shipped; C.B is pure logic).
3. **Cross-bundle pin un-skip:** test at `tests/integration/test_phase12_bundle_c_cross_bundle_pin.py` un-skips at C.B T-B.1 + T-B.2 landing per the C.A return report.
4. **Determinism principle is binding discriminator** — classifier emits tier-2 when in doubt. False-positive tier-2 just defers to operator; false-positive tier-1 silently corrupts journal.
5. **CVGI 41 + DHC 39 + VSAT 40 discriminating examples** — spec §10 walks each through end-to-end; C.B classifier tests MUST exercise all three.
6. **NO journal mutations in C.B** — pure logic only. Classifier produces `ClassificationResult`; auto-correction is C.C scope.

## Step 8 — When C.D dispatch fires (FUTURE)

Threading reminders for the C.D dispatch brief:

1. **Synthetic-fixture-only acceptance test for `--custom-value` payload contract** is BINDING (per `effb995` lesson + plan §G C.D gate-section LOCKED revised mechanic). Production DHC 39 + VSAT 40 dispositions per operator's REAL data without contortion.
2. **Phase 10 banner predicate widening** retrofits 10 base-layout VMs (per OQ-7 operator-resolved). 14 VM-instance regression tests for defense-in-depth (per spec §A.5 / writing-plans §I.10).
3. **OQ-20 `custom` choice V1 audit-only narrowing** ACCEPTED by operator 2026-05-15. Payload-shape `{"audit_only": true, "operator_intent": "..."}`; no journal mutation. Spec §6.2.1 amendment banked at plan §I.20 as V2.1 §VII.F entry. C.D ships V1 audit-only; V2 widening banked.
4. **Backfill is explicit-only** (per OQ-5 operator-resolved). NO auto-fire at C.D ship; C.D gate plays operator-witnessed walkthrough role for 39/40/41.
5. **Tier-3 override CLI confirmation + `--force` flag** (per OQ-8 operator-resolved; mirrors `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst`).
6. **HTMX gotcha trinity** — N/A V1 (OQ-3 CLI-only lock); banks for V2 web surface.
7. **`apply_overrides` discipline at Schwab entry points** (per Sub-bundle B lesson #6) — if C.D backfill constructs `schwabdev.Client(...)` directly, MUST `apply_overrides(cfg)` at entry; route-level test asserts cascade-resolved credentials threaded through.
8. **Production refresh-token clock awareness** — expires 2026-05-22; C.D gate may need re-auth via `/schwab/setup` web form first.

## Step 9 — Quick reference summary

| Artifact | Path / commit |
|---|---|
| Spec (BINDING) | `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md` (`d682c25`; 1444 lines; NO_NEW_CRITICAL_MAJOR after 9 rounds) |
| Plan (BINDING) | `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` (`008dfe4`; 3621 lines; NO_NEW_CRITICAL_MAJOR after 6 rounds) |
| Brainstorm dispatch brief | `docs/phase12-bundle-C-auto-correct-reconciliation-brainstorm-brief.md` (`0f89022`) |
| Writing-plans dispatch brief | `docs/phase12-bundle-C-writing-plans-dispatch-brief.md` (`93ceb8c`) |
| C.A executing-plans dispatch brief | `docs/phase12-bundle-C-A-foundation-executing-plans-dispatch-brief.md` (`3cb334d`) |
| C.A return report | `docs/phase12-bundle-C-A-return-report.md` (`56e6993`; on main post-merge) |
| C.A integration merge | `354b6c0` |
| C.A SHIPPED entry | phase3e-todo top SHIPPED-band entry @ `4a390a4` |
| C.B executing-plans dispatch brief | TBD (your first deliverable) |
| C.C executing-plans dispatch brief | TBD (deferred to post-C.B-ship) |
| C.D executing-plans dispatch brief | TBD (deferred to post-C.C-ship) |
| Cross-phase backlog | `docs/phase3e-todo.md` (active; archive at `docs/phase3e-todo-archive.md`) |
| Orchestrator-role context | `docs/orchestrator-context.md` (updated 2026-05-15 with 7 NEW lessons from Sub-bundle C brainstorm + writing-plans) |

## Step 10 — Closing note from prior orchestrator

This handoff caps a productive session that drove **8 sub-bundle/sub-sub-bundle artifacts** across the Phase 12 arc:

1. **Sub-bundle B** brief→dispatch→7-surface gate (including orchestrator-inline gate-fix `7b75d4a` for the operator-surfaced UX gap)→merge `b09eb06`→housekeeping;
2. **Sub-bundle C brainstorm** dispatch→9-round return triage→5 lessons banked at `effb995`;
3. **Sub-bundle C writing-plans** dispatch→6-round return triage→2 lessons banked at `657b8a0`→OQ-4 VWAP+schwabdev exploration→OQ-20 triage;
4. **Sub-sub-bundle C.A** brief→dispatch→2-round return→integration merge `354b6c0`→housekeeping `b24e9e2`+`4a390a4`→production migration confirmed schema v19.

**Key story arcs of this session:**

1. **Sub-bundle B's operator-paired gate caught a UX gap** — `/schwab/setup` was reachable only by typing the URL. Orchestrator-inline gate-fix at `7b75d4a` added "External integrations" section on `/config` page; **inline gate-fix precedent now at 3 instances cumulatively** (11B `34be84e` + 12A `e2c0384` + 12B `7b75d4a`). Lesson family extension: discoverable-UX-gap variant.

2. **OQ-4 VWAP exploration revealed Schwab API does expose execution-leg detail** (`orderActivityCollection[].executionLegs[]`) and schwabdev's `account_orders` + `order_details` endpoints DO pass it through without stripping. The constraint is purely V1 mapper coverage at `swing/integrations/schwab/trader.py`. Operator confirmed Option C: ship Sub-bundle C with V1 mapper as-is + bank V2 mapper widening + auto-VWAP as the next-architectural-dispatch slot post-C.D ship.

3. **Sub-bundle C brainstorm at 9 substantive Codex rounds is the new project high-water mark.** Healthy convergent chain shape; ZERO Critical findings; ZERO ACCEPT-WITH-RATIONALE. Architectural-pivot brainstorms have more wording-precision surface than schema-design brainstorms.

4. **Sub-bundle C writing-plans at 3621 lines is the new arc-scale plan high.** Substantial: 4 sub-sub-bundles × 51 tasks + 21 gate surfaces total. Plan-size budget for architectural-pivot writing-plans updated to 3000-3700 lines (was 2200-2900 in my projection).

5. **R3 architectural-revert during writing-plans** — plan-author LOCKED a `metadata_json` column at R2, Codex caught at R3 framing as violation of spec §15.1 schema-design lock. NEW LESSON at `657b8a0`: plan-author schema additions DURING executing-plans cycle need pre-dispatch orchestrator escalation, NOT bank-after-write. Pattern complement to existing brief-empirical-verification lesson family.

Sub-sub-bundle C.B is well-defined as a 14-task pure-logic dispatch (~+55-95 fast tests + 3-5 Codex rounds + 3-surface gate). Sub-sub-bundle C.C is substantial (auto-correction service + flow pivot; 12 tasks + 4-6 Codex rounds expected). Sub-sub-bundle C.D is the big one (16 tasks + 10-surface gate + synthetic-fixture-only acceptance test discipline + Phase 10 banner predicate widening retrofitting 10 base-layout VMs + production backfill of 39/40/41).

**Operator preference reaffirmed via this session:** the "commit brief BEFORE inline dispatch prompt" lesson is now durable + folded into both auto-memory + orchestrator-context.md. Discipline pinned via `git log --oneline -1 | Select-String <bundle>-brief` verifier between Write and inline-prompt steps.

Good luck.

---

*End of handoff brief. Post-Phase-12-Sub-sub-bundle-C-A-merge orchestrator transition. Phase 12 Sub-bundle C 33% shipped (C.A foundation only). Sub-sub-bundle C.B (classifier + validator-shim) UNBLOCKED — your first dispatch. C.C + C.D queued behind C.B. Operator-paced.*
