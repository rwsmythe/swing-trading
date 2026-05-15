# Phase 12 Sub-sub-bundle C.A (Foundation) — executing-plans dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Sub-sub-bundle C.A (schema + minimal repos + tests; ZERO behavioral changes to existing surfaces) of the Phase 12 Sub-bundle C implementation plan via `copowers:executing-plans`. Plan is `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` §A (C.A scope per plan §C decomposition table; 9 tasks T-A.1 … T-A.8 + T-A.7 cross-bundle pin). All per-task acceptance criteria + tests + commit shapes are in the plan; this dispatch brief is a worktree-config + scope wrapper, NOT a duplicate spec.

**Expected duration:** ~8-12 hr implementation + ~2-4 hr Codex convergence. Total ~10-16 hr. C.A is the foundation sub-sub-bundle (bottom of dependency stack; lands migration 0019 + new repos). Sub-sub-bundles C.B/C.C/C.D all depend on C.A's schema.

**Skill posture:**
- Invoke `copowers:executing-plans` against the plan path scoped to Sub-sub-bundle C.A (`PLAN_PATH=docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md`, `SCOPE=Sub-sub-bundle C.A (T-A.1..T-A.8 + T-A.7 only)`).
- The skill wraps `superpowers:subagent-driven-development` + adversarial Codex review.
- Adversarial review runs after all 9 tasks land. Expected 3-5 Codex rounds (matches Phase 9 Sub-bundle A + Phase 11 Sub-bundle A precedent for similar schema-foundation scope; 9-round high-water mark was Sub-bundle C brainstorm — execution rounds typically fewer than brainstorm/writing-plans).

---

## §0 Inputs

### §0.1 Plan

- **PLAN_PATH:** `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` (3621 lines; Codex R6 confirmation NO_NEW_CRITICAL_MAJOR; LOCKED at `008dfe4`).
- **Sub-sub-bundle C.A section** is in plan §D (or equivalent per writing-plans-author section numbering). Self-contained per-task spec with TDD checkboxes (`- [ ]`).
- **Plan §A pre-verification items:** read all 8 §15.3 + Lesson #5 pre-verifications at plan §A BEFORE starting tasks. ZERO divergences found between spec §3 and shipped state on CHECK enums per writing-plans return report §15.3 (5-value resolution; 5-value fills.reconciliation_status; 6-value trade_events.event_type). C.A inherits the empirical verification; do NOT re-grep at C.A dispatch time.
- **Plan §C cross-bundle dependency matrix:** lines TBD per writing-plans-author section numbering; the F-1..F-10 pin matrix names which sub-sub-bundle each lock is consumed by. C.A creates the schema; C.B/C.C/C.D consume it.

### §0.2 Spec

- **SPEC_PATH:** `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md` (1444 lines; Codex R9 confirmation NO_NEW_CRITICAL_MAJOR; LOCKED at `d682c25`).
- **Read for §3 schema sketches (BINDING — 20 columns on `reconciliation_corrections` table; column-count drift §I.16 documented in plan).**
- **Read §1.3 four operator-locked architectural constraints** + **§1.5 binding integrations** + **§3 all schema sketches** for background.
- **§14 open questions all triaged** per the writing-plans return-report disposition table (5 operator-resolved + 4 LOCKED-in-spec + 4 writing-plans-decides + 2 V2-banked + 1 newly-added OQ-20 `custom` audit-only narrowing accepted).

### §0.3 Project state at dispatch time

- **HEAD on `main`:** `657b8a0` (post-OQ-20 acceptance + 2 NEW Sub-bundle C writing-plans lessons banked + push). Brief commit lands at HEAD+1 pre-dispatch.
- **Test count:** **3862 fast passing on main** + 4 pre-existing failures (3 phase8 walkthrough + 1 schwab_setup_cli sentinel — banked separately) + 1 skipped. Verified inline at writing-plans-return-triage.
- **Ruff baseline:** **18** (E501 only; unchanged across Phase 11 + Phase 12 Sub-bundle A + B + C brainstorm + C writing-plans).
- **Schema version:** **v18.** C.A bumps v18 → v19 in T-A.1 via migration `0019_phase12_bundle_c_auto_correct_reconciliation.sql` (exact filename verifiable in plan §A.1).
- **Production discrepancy state:** 3 unresolved-material (39 DHC + 40 VSAT + 41 CVGI) + 30+ resolved historical (mostly `acknowledged_immaterial`). LEFT UNRESOLVED BY DESIGN pending Sub-bundle C.D ship. C.A is foundation; does NOT touch existing discrepancy rows.
- **Production refresh-token clock:** fresh 7-day clock issued 2026-05-15T17:05:00+00:00; expires 2026-05-22T17:05:00+00:00. C.A does NOT exercise Schwab API; refresh clock irrelevant to C.A gate.

### §0.4 Sub-sub-bundle C.A scope (9 tasks per writing-plans return report)

Per plan §C decomposition + return report:

| Task | Title | Files (illustrative; plan §A locks) |
|---|---|---|
| **T-A.1** | Migration 0019 atomic landing (5 schema deltas + version bump v18 → v19) | NEW `swing/data/migrations/0019_*.sql` + migration runner discipline tests |
| **T-A.2** | `ReconciliationCorrection` dataclass (frozen; `__post_init__` validators) | NEW `swing/data/models.py` extension OR new module + tests |
| **T-A.3** | `reconciliation_corrections` repo (CRUD + chain queries + `__delete__`/`__insert__` sentinels per OQ-9 lock) | NEW `swing/data/repos/reconciliation_corrections.py` + tests |
| **T-A.4** | `reconciliation_discrepancies.ambiguity_kind` column read/write path extension (existing repo) | MODIFY `swing/data/repos/reconciliation.py` + tests |
| **T-A.5** | `review_log.superseded_by_correction_id` column read/write path extension | MODIFY `swing/data/repos/review_log.py` + tests |
| **T-A.6** | `schwab_api_calls.linked_correction_id` FK column read/write path extension | MODIFY `swing/data/repos/schwab_api_calls.py` + tests |
| **T-A.7** | Cross-bundle pin (C.B/C.C/C.D consumers will compose over T-A.1..T-A.6 surfaces) | Test file marker; un-skip at consumer-bundle landing |
| **T-A.8** | `trade_events.event_type` enum widening read path (event-type `'reconciliation_auto_correct'` accepted by repo) | MODIFY `swing/data/repos/trade_events.py` + tests |
| **T-A.7 (cross-bundle pin)** | Pin test asserting C.B/C.C/C.D will be able to compose over T-A.1..T-A.6 (skip-decorated until consumer-bundle landing) | NEW test file with `@pytest.mark.skip(reason="cross-bundle pin; un-skips at C.X landing")` |

**Cross-bundle dependencies:** NONE for C.A inputs (C.A is foundation). C.B/C.C/C.D all depend on C.A's migration + repo surfaces.

**Migration atomicity (BINDING per spec §11 + plan §A.1 + Phase 7 hotfix `283d4fa` discipline):** the SINGLE migration file `0019_*.sql` lands ALL 5 schema deltas + `UPDATE schema_version SET version = 19` ATOMICALLY in T-A.1 via `BEGIN IMMEDIATE; ... COMMIT;` envelope under the `_apply_migration` wrapper. `EXPECTED_SCHEMA_VERSION = 19` is bumped in T-A.1 same commit. Sub-bundles C.B/C.C/C.D DO NOT modify the migration; they ship code that consumes the schema.

### §0.5 BINDING contracts from plan §A (DO NOT re-litigate)

Per writing-plans return report + plan §A:

1. **Migration filename: `0019_phase12_bundle_c_auto_correct_reconciliation.sql`** (or as plan §A.1 LOCKS). Backup file: `swing-pre-phase12-bundle-c-migration-<ISO>.db` per Phase 9/11 backup-naming precedent.
2. **`reconciliation_corrections` has 20 columns** (plan §A locks; spec §3.1 header text "19 columns" is brief-vs-spec drift documented at §I.16). All DDL + dataclass + tests assert 20.
3. **5 schema deltas under one atomic envelope:**
   - CREATE TABLE `reconciliation_corrections` (20 columns; per spec §3.1).
   - ALTER TABLE `reconciliation_discrepancies` ADD COLUMN `ambiguity_kind` TEXT NULL CHECK + cross-column CHECK with `resolution`.
   - **Table-rebuild #1:** widen `reconciliation_discrepancies.resolution` CHECK enum 5 → 9 values (SQLite ALTER does NOT support CHECK widening; full table rebuild required; preserves existing 30+ rows; PRAGMA foreign_keys=OFF during rebuild per Phase 7 hotfix `283d4fa` discipline).
   - ALTER TABLE `review_log` ADD COLUMN `superseded_by_correction_id` INTEGER NULL FK → `reconciliation_corrections(correction_id)` ON DELETE SET NULL.
   - **Table-rebuild #2:** widen `trade_events.event_type` CHECK enum +`'reconciliation_auto_correct'` (full table rebuild required for CHECK widening).
   - ALTER TABLE `schwab_api_calls` ADD COLUMN `linked_correction_id` INTEGER NULL FK → `reconciliation_corrections(correction_id)` ON DELETE SET NULL.
4. **Backup gate ON `pre_version <= 18 AND post_version >= 19` only** (per Phase 7 Sub-A I1 lesson + Phase 9 Sub-bundle A backup discipline).
5. **Test fixture PRAGMA `foreign_keys=ON` discipline** — every C.A test fixture sets `foreign_keys=ON` to mirror production (per Phase 7 hotfix `283d4fa` lesson).
6. **Cross-column CHECK schema-defended** (between `ambiguity_kind` and `resolution`; per OQ-12 spec recommendation + plan §A.1 LOCK). App-layer enforcement at service-time is the secondary defense (C.C lands; not C.A scope).
7. **Per-row policy stamping** — `reconciliation_corrections.risk_policy_id_at_correction` is **NULLABLE** + `ON DELETE SET NULL` (per spec §3.1 Codex R1 Major #3 fix; matches Phase 9 §3.1.1 trades.risk_policy_id_at_lock precedent). App-layer SHOULD populate at write time but the column accepts NULL for V1 defensive forward-compat.
8. **`correction_set_id` mechanic (per OQ-6 plan-author lock):** inline two-step INSERT-then-UPDATE anchor pattern at T-A.3 + T-C.3.4 (the C.C consumer); C.A T-A.3 implements the repo helper; C.C consumes.
9. **`__delete__` + `__insert__` sentinels (per OQ-9 plan-author lock):** plan T-A.3 implements sentinel-aware repo + bytewise-equality marker for no-mutation cases (per R1 Major #8 fix). No `__no_mutation__` sentinel; use bytewise-equality marker.

### §0.6 Forward-binding lessons inherited (BINDING for C.A)

**44 cumulative lessons** through C.A (Phase 11 17 + Phase 12 A 5 + B 12 + C brainstorm 5 + C writing-plans 2 + Sub-bundle C plan §J 3 new lessons = 44):

Particularly load-bearing for C.A schema-foundation work:

1. **`executescript()` issues implicit COMMIT** (Phase 7 Sub-A R1 Major 3) — migration runner discipline inherited via `swing/data/db.py:_apply_migration` (`283d4fa` hotfix). C.A T-A.1 must use the wrapper, not bare `executescript()`.
2. **SQLite REPLACE prohibition** — NO `INSERT OR REPLACE` on FK-referenced or audit-trail tables. C.A `reconciliation_corrections` repo MUST use SELECT-then-UPDATE-or-INSERT pattern.
3. **NEW LESSON 2026-05-15 (`657b8a0`): plan-author schema additions DURING executing-plans cycle need pre-dispatch escalation, NOT bank-after-write.** If C.A implementer encounters a schema element NOT in plan §A + spec §3, STOP + escalate to orchestrator. Examples: missing column for a use case the plan didn't anticipate; new CHECK constraint that emerges from a Codex finding. Cost of bank-after-write: 2-3 Codex rounds of cascade cleanup. Cost of escalation: 1 chat round + spec-amendment-or-explicit-orchestrator-approval. The pattern complement to the existing brief-empirical-verification lesson family — applies at execution phase as well.
4. **Per-row policy stamping (Phase 8 R1 M5)** — `reconciliation_corrections.risk_policy_id_at_correction` populated at write-time. C.A T-A.3 repo helper signature accepts policy_id param.
5. **Cross-column CHECK at schema time + app-layer enforcement at service time** (Phase 9 §3.1 R1 Minor #4 precedent + spec §3.2 + Codex chain ratification) — schema CHECK between `(ambiguity_kind, resolution)` is schema-defended (C.A scope); app-layer enforcement is C.C scope.
6. **USERPROFILE+HOME monkeypatch discipline (Phase 9 Sub-bundle A gotcha)** — C.A test fixtures that touch `~/swing-data/` paths MUST monkeypatch both env vars to tmp_path. T-A.7 cross-bundle pin tests may touch this surface.
7. **Brief-vs-shipped-schema empirical verification (Lesson #5 from Sub-bundle C brainstorm)** — writing-plans return report §15.3 already verified ZERO divergences on shipped CHECK enums; C.A inherits + does NOT re-grep. If C.A implementer notices any divergence between plan §A.7 verbatim grep results and current shipped state (between writing-plans and C.A dispatch), STOP + escalate.
8. **Table-rebuild discipline (Phase 9 Sub-bundle B lesson)** — both `reconciliation_discrepancies.resolution` widening + `trade_events.event_type` widening require SQLite table-rebuild (CHECK enum can't be ALTERed in-place). T-A.1 includes verbatim REBUILD SQL in plan; preserves all existing rows.

### §0.7 Sub-sub-bundle C.A test projection

Per writing-plans return report: **+40-65 fast tests projected.** Likely upper half based on Sub-bundle A/B overshoot precedent (Sub-bundle A T-A.1..T-A.4 actual +35 vs projected +25; Sub-bundle B actual +66 vs projected +18-28). C.A actual likely **+50-80 fast tests**.

Final main HEAD post-C.A-merge: ~3902-3942 fast tests (was 3862 + +40-80).

---

## §1 Worktree + binding conventions

### §1.1 Worktree

- **Branch:** `phase12-bundle-C-A-foundation`
- **Worktree directory:** `.worktrees/phase12-bundle-C-A-foundation/`
- **BASELINE_SHA:** `657b8a0` (current main HEAD pre-brief-commit; resolve via `git rev-parse main` at worktree-creation time after this brief lands).
- **Branch naming intent:** `phase12-bundle-C-A-*` matches the cleanup-script `phase\d+[-_]` regex post 12A T-A.4 fix — operator's `-DeregisterFirst` pass should clean cleanly post-merge.

### §1.2 Marker-file workflow

- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all 9 tasks land + tests GREEN + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits

- Conventional prefixes:
  - `feat(data): T-A.1 — <description>` for migration 0019
  - `feat(data): T-A.2 — <description>` for ReconciliationCorrection dataclass
  - `feat(data): T-A.3 — <description>` for reconciliation_corrections repo
  - `feat(data): T-A.4/A.5/A.6/A.8 — <description>` for repo column-extensions
  - `test(data): T-A.7 — <description>` for cross-bundle pin
  - `fix(phase12-bundle-C-A): Codex RN <severity> #N — <description>` for Codex-driven fixes
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`** (per CLAUDE.md staging convention: prefer `git add <specific-files>` over `git add -A`).
- **TDD:** failing test first, minimal implementation, pass, commit. Per-task `- [ ]` checkboxes in plan §A mark per-step boundaries.

### §1.4 Branch isolation + ownership

- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** task-family TDD commits → marker-file removal → adversarial-critic → return report.
- **Operator owns:** witnessed verification gate (§3 surfaces below).
- **Orchestrator owns:** integration merge to main + post-merge housekeeping + Sub-sub-bundle C.B dispatch commissioning.

### §1.5 Verify command

PowerShell from inside worktree:

```powershell
git log --oneline HEAD~10..HEAD
python -m pytest -m "not slow" -q
ruff check swing/ --statistics
python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; assert EXPECTED_SCHEMA_VERSION == 19, f'Expected 19, got {EXPECTED_SCHEMA_VERSION}'"
```

---

## §2 Adversarial review (Codex)

Invoked automatically by `copowers:executing-plans` after all 9 tasks land + tests GREEN.

**Expected chain shape:** 3-5 substantive Codex rounds (matches Phase 9 Sub-bundle A 5 rounds + Phase 11 Sub-bundle A 4 rounds + Phase 12 Sub-bundle A 3 rounds for similar schema-foundation scope). Convergent tapering per Phase 8 R2-R5 + Phase 9/10/11/12 lesson family.

**Adversarial review watch items (C.A-specific; pass as targeted prompts to `copowers:adversarial-critic`):**

1. **Migration 0019 atomicity.** All 5 schema deltas + version bump under one `BEGIN IMMEDIATE; ... COMMIT;` envelope per `_apply_migration` wrapper. NO bare `executescript()` (Phase 7 R1 Major 3 lesson).
2. **Table-rebuild preservation.** Both rebuilds (`resolution` enum + `event_type` enum) preserve all existing rows; backup file written at correct schema-version boundary.
3. **Cross-column CHECK syntax.** SQLite executes the `(ambiguity_kind, resolution)` cross-column CHECK correctly under the runner (Phase 9 §3.1 R1 Minor #4 precedent verification).
4. **Test fixture PRAGMA foreign_keys=ON.** Every C.A migration test fixture sets `foreign_keys=ON` to mirror production (Phase 7 hotfix `283d4fa`).
5. **Backup gate condition.** Backup fires ONLY on `pre_version <= 18 AND post_version >= 19` (Phase 7 Sub-A I1 lesson).
6. **`INSERT OR REPLACE` prohibition.** C.A repo + service code MUST NOT use `INSERT OR REPLACE` on `reconciliation_corrections` or any FK-referenced table.
7. **20-column count assertion.** Test asserts the new table has exactly 20 columns per plan §A LOCK (deviation from spec §3.1 header "19" is documented at §I.16).
8. **`__delete__` + `__insert__` sentinel semantics.** Repo helper handles these correctly per OQ-9 plan-author lock; bytewise-equality marker for no-mutation cases.
9. **Per-row policy stamp NULL discipline.** `risk_policy_id_at_correction` is nullable + `ON DELETE SET NULL`; T-A.3 repo signature accepts None.
10. **`correction_set_id` inline two-step INSERT-then-UPDATE.** Anchor pattern works correctly for multi-column atomic corrections (T-A.3; consumed by C.C).
11. **USERPROFILE+HOME monkeypatch.** Any test fixture touching `~/swing-data/` paths monkeypatches both env vars (CLAUDE.md gotcha).
12. **NEW lesson 2026-05-15: plan-author schema additions.** If Codex surfaces a need for a schema element NOT in plan §A + spec §3, the implementer MUST STOP + escalate to orchestrator BEFORE adding inline. The cost of bank-after-write is 2-3 cascade-cleanup rounds; the cost of escalation is 1 chat round.

---

## §3 Operator-witnessed verification gate (Sub-sub-bundle C.A integration)

Per writing-plans return report §15.5 C.A gate plan + spec §15.5:

| Surface | Type | Acceptance |
|---|---|---|
| **S1** | Inline `pytest -m "not slow" -q` | GREEN at ~3902-3942 fast tests (worktree-side; +40-80 net from 3862 baseline); 4 pre-existing failures unchanged; 1 skipped. |
| **S2** | `swing db-migrate` against fresh empty DB | Lands `schema_version = 19`; all 5 schema deltas applied atomically; backup file NOT written (empty DB; pre-version not in [18,19) range). |
| **S3** | `swing db-migrate` against production-snapshot DB | Lands `schema_version = 19`; all 30+ existing discrepancy rows preserved (dynamic snapshot equality NOT fixed-count per plan §G.C.A.S3 LOCK; survives drift between plan-drafting and C.A integration-merge); backup file written at `swing-pre-phase12-bundle-c-migration-<ISO>.db`; 3 unresolved-material rows preserved by both `'unresolved'` AND new banner predicate (which becomes operational at C.D landing, but Phase 10 schema reads `'unresolved'` only V1 — count unchanged at C.A). |
| **S4** | `ruff check swing/ --statistics` | Reports 18 E501 unchanged. |

**Gate session ≤ 4 surfaces budget:** all 4 inline-or-CLI-driven. S1+S4 inline (2). S2+S3 operator-driven CLI (2 — within budget). No browser-driven surfaces in C.A scope (no HTMX form work; no web surfaces).

**Production state post-gate:** schema_version increments from 18 → 19 in operator's production DB. C.A is consumer-side passive (no behavioral changes); existing discrepancies + fills + trades + review_log + schwab_api_calls all preserved. The new schema elements are populated by C.B/C.C/C.D consumers; C.A schema sits idle until those bundles ship.

**Production-write classifier soft-block awareness:** S3 writes to operator's production DB (via `swing db-migrate`); operator pre-authorizes via gate-path. AskUserQuestion responses are NOT visible to the classifier — if soft-blocked, surface to operator for plain-chat "yes" confirmation per orchestrator-context.md "Lessons captured" 2026-05-12 entry.

---

## §4 OUT OF SCOPE (do not do)

- **C.B classifier scope** — `swing/trades/reconciliation_validators.py` shim module + classifier per-discrepancy-type sub-classifiers. Ships in Sub-sub-bundle C.B.
- **C.C auto-correction service scope** — `swing/trades/reconciliation_auto_correct.py` service module + `run_*_reconciliation` flow pivot. Ships in Sub-sub-bundle C.C.
- **C.D Tier-2 CLI surface scope** — `swing journal discrepancy show-ambiguity|resolve-ambiguity|override-correction` + `swing journal reconcile-backfill` CLIs + Phase 10 dashboard banner predicate widening. Ships in Sub-sub-bundle C.D.
- **Schema additions or material spec deviations** — per NEW lesson 2026-05-15 at `657b8a0`. If C.A implementer encounters a need for a schema element NOT in plan §A + spec §3, STOP + escalate to orchestrator BEFORE adding inline. Do NOT bank-after-write.
- **V2 mapper widening + auto-VWAP classifier path** — operator-locked next-architectural-dispatch slot (post-C.D ship). NOT C.A scope.
- **Fill auto-population at trade-entry time** — separate future sub-bundle (spec §13 lock). NOT C.A scope.
- **Re-litigating spec §1.3 four operator-locked architectural constraints** — accepted as given.
- **Behavioral changes to existing surfaces** — C.A is foundation; the new schema sits idle until C.B/C.C/C.D consumers ship. No existing code should change behavior in C.A.

---

## §5 Return report shape

After all 9 tasks land + Codex chain converges + before final return-report commit, draft a return report at `docs/phase12-bundle-C-A-return-report.md` (mirroring `docs/phase12-bundle-A-return-report.md` + `docs/phase9-bundle-A-return-report.md` shape):

1. Final HEAD on branch + commit count breakdown (9 task-impl + N Codex-fix + 1 return-report).
2. Codex round chain (R1-RN summary table + convergent shape).
3. Test count delta + ruff baseline delta + schema version delta (v18 → v19 atomic).
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate; 4 surfaces).
5. Per-task deviations from plan (if any) with rationale.
6. Codex Major findings ACCEPTED with rationale (if any).
7. Watch items for orchestrator (V2 candidates surfaced; Sub-sub-bundle C.B dispatch-readiness).
8. Worktree teardown status.
9. Per-task disposition LOCKS (any task-level decisions worth banking).
10. Forward-binding lessons for Sub-sub-bundle C.B (if commissioned).
11. CLAUDE.md status-line refresh draft text for orchestrator paste-in at integration-merge time.
12. Composition-surface verification via `^def` grep for new repo helpers.
13. Migration 0019 atomicity verification + table-rebuild preservation evidence.

---

## §6 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES — per §1.1.
- **Model:** defer to harness default.
- **Expected duration:** 8-12 hr implementation + 2-4 hr Codex; total ~10-16 hr.

---

## §7 If you get stuck

- If plan §A binding contracts conflict with what spec §3 says, **plan wins** (writing-plans Codex chain ratified plan §A; spec is upstream input).
- If a Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly in plan's "open questions" + return report.
- If you need a schema element NOT in plan §A + spec §3, **STOP + escalate** (NEW lesson 2026-05-15; bank-after-write costs 2-3 cascade-cleanup rounds).
- DO NOT propose mapper widening within C.A scope (§4 lock).
- DO NOT propose fill auto-population within C.A scope (§4 lock).
- DO NOT make behavioral changes to existing surfaces within C.A scope (§4 lock).
- If you find a brief-vs-shipped-schema divergence (writing-plans return report §15.3 verified ZERO at plan-drafting time; if state has shifted since), STOP + escalate.
- If you encounter a Phase 7/8/9/10/11/12-A/12-B brainstorm lesson that conflicts with a C.A implementation proposal, the prior-phase lesson wins (validated by ship-experience). Surface the conflict as a constraint.
