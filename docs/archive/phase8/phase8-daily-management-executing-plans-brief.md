# Phase 8 Daily_Management Executing-Plans Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 8 executing-plans implementer. No prior conversation context.

**Mission:** Execute the Phase 8 daily-management implementation plan to ship production code. New `daily_management_records` table + `_step_daily_management` pipeline step + repo+service+web surfaces + dashboard tile + briefing extension. Plan is the binding contract; implementer follows tasks in order with TDD discipline (RED test → minimal impl → GREEN → commit per task). Final deliverable: integration merge from worktree branch `phase8-daily-management` to `main` after operator-witnessed verification gate PASS.

**Sequencing:** Phase 8 brainstorm SHIPPED 2026-05-06 at `c954eef`; Phase 8 writing-plans SHIPPED 2026-05-07 at `17b1845`. **THIS DISPATCH consumes the writing-plans plan.** Phase 9 writing-plans → Phase 9 executing-plans → Phase 10 writing-plans → Phase 10 executing-plans follow per locked sequencing (8 → 9 → 10).

**BASELINE_SHA:** `17b1845` (the writing-plans plan landing commit; worktree branch `phase8-daily-management` branches from this).

**Expected duration:** ~13–15 hours of subagent-driven development per writing-plans return-report estimate. ~1 day with buffer for the operator-witnessed verification gate.

---

## §0 Read first

In this order:

1. **`CLAUDE.md`** at repo root — project conventions + gotchas. **All gotchas binding for executing-plans**, especially: SQLite `INSERT OR REPLACE` prohibition (2026-05-06 — Phase 8 plan tasks T2.3/T3.1 already enforce; verify in implementation); HTMX failure surfaces (T5.0/T5.1 dashboard tile + web POST); Windows ACL gotchas (worktree teardown discipline); Starlette 1.0 signature; TestClient lifespan.
2. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Recent decisions and framings" + "Lessons captured" + **§"Binding conventions (project-wide)"** — 35+ active lessons including 17+ Phase 7/8/9 schema/transactional/integration lessons binding. Pay special attention to **§"Executing-plans dispatch convention (formalized 2026-05-02 post-Phase-5)"** — describes the EXACT 7-step workflow.
3. **`docs/phase3e-todo.md`** Phase 8 SHIPPED markers — full historical context.
4. **`docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md`** — **THE BINDING PLAN.** 4140 lines, 15 tasks. This is the implementation contract. Execute tasks in order; do NOT re-litigate plan decisions; do NOT skip tasks; do NOT introduce new tasks (flag in return report if you discover a gap).
5. **`docs/superpowers/specs/2026-05-06-phase8-daily-management-design.md`** — design spec (875 lines). Plan implements; spec governs. If plan-spec divergence appears mid-implementation, accept-with-rationale + flag.
6. **`docs/phase8-daily-management-writing-plans-brief.md`** — the brief that produced the plan; useful context for understanding plan-author intent.
7. **`swing/data/migrations/0014_phase7_state_machine_and_fills.sql`** + **`0015_finviz_api_calls.sql`** — already-shipped schemas immediately preceding Phase 8's 0016 migration.
8. **`swing/data/db.py:_apply_migration`** + **`_phase7_backup_gate`** — current migration runner with foreign_keys=OFF discipline + executescript() partial-failure rollback (per Phase 7 hotfix `283d4fa`). Plan T1.1 adds `_phase8_backup_gate` alongside.
9. **One prior executing-plans-output for format reference** — see Phase 6's commit chain `1be4622..e976d64` (24 commits incl 16 task-impl + Codex fixes + mid-verification fixes; demonstrates the worktree+marker-file workflow + adversarial-review iteration).

---

## §0 Skill posture

**Workflow per `docs/orchestrator-context.md` §"Binding conventions" 2026-05-02 entry — this is BINDING:**

- Invoke **`superpowers:using-git-worktrees`** FIRST to create the isolated worktree branch.
- Invoke **`superpowers:subagent-driven-development`** to execute the plan tasks via subagent dispatch.
- Invoke **`copowers:adversarial-critic`** DIRECTLY (not via the `copowers:executing-plans` wrapper) with explicit `PHASE/SPEC_PATH/PLAN_PATH/BASELINE_SHA` parameters AFTER all subagent tasks complete.
- DO NOT invoke `copowers:executing-plans` (the wrapper bundles both phases without marker-file management).
- DO NOT invoke `superpowers:writing-plans` — plan is locked; do not re-draft.
- DO NOT invoke `superpowers:brainstorming` — design is locked.

---

## §1 Strategic context (ORCHESTRATOR-DISTILLED — what's NOT in the plan/spec)

The following are accepted as **BINDING** without re-justification.

### §1.1 Plan + spec are the binding contracts

- **Plan governs implementation order + acceptance criteria + verify commands** per task.
- **Spec governs design decisions** that the plan implements.
- If plan-spec divergence surfaces mid-implementation, accept-with-rationale + flag in return report. Do NOT silently amend either.
- If plan task spec is unimplementable as-written (e.g., shipped-code state changed since plan-drafting), accept-with-rationale + propose a corrected approach in return report.

### §1.2 Phase 7 + Phase 8 + Phase 9 lessons binding for implementation

The 17+ active lessons in orchestrator-context "Lessons captured" — particular call-outs for Phase 8 implementation:

**Migration runner (already in `_apply_migration` per Phase 7 hotfix `283d4fa`):**
- foreign_keys=OFF before executescript; restore after (try/finally).
- try/except wrap executescript+commit; rollback + re-raise on partial failure.
- Backup gate fires only on `current_version == (target - 1)` AND target is gated.
- Test fixtures set `foreign_keys=ON` to mirror production.

**UPSERT discipline (Phase 8 R4 lesson + CLAUDE.md gotcha 2026-05-06):**
- NO `INSERT OR REPLACE` against any FK-referenced or audit-trail table.
- SELECT-then-UPDATE-or-INSERT only.
- Plan T2.3 + T3.1 implement; verify implementation matches plan.

**Audit-trail dual-column pattern (Phase 8 R2 lesson):**
- `is_superseded INTEGER` flag + `superseded_by_record_id INTEGER REFERENCES daily_management_records(...)` FK.
- 6-step transactional tier-upgrade sequence per spec §3.3 + plan §A.x.
- `SupersededRowImmutableException` for write attempts on superseded rows.

**Per-row policy-versioned value stamping (Phase 8 R1 M5 lesson):**
- `trail_MA_period_days INTEGER` per-row stamp for `trail_MA_candidate_price`.
- Phase 9 risk_policy versioning will change the DEFAULT for new rows but cannot retroactively change historical rows.

**State-machine integration via JOIN, not flag (Phase 9 R1 M4 lesson):**
- Phase 8 dashboard tile reads `daily_management_records` JOIN `trades.state` for per-open-position rendering.
- NO modifications to Phase 7 state machine OR `trades` table flag columns (beyond the spec-locked `planned_target_R` ADD column).

**Service-call-inside-transaction (Phase 8 plan §A.1 lesson 2026-05-07):**
- Phase 8 `record_event_log` calls **REPO-level** `swing/data/repos/trades.py:update_stop_with_event` (NOT service-level `swing/trades/stop_adjust.py:update_stop_with_event:105` which opens its own `with conn:` block).
- `linked_trade_event_id` resolved via TRADE-SCOPED max-id-after-insert pattern (NOT `last_insert_rowid()`).
- Defense-in-depth validators inside transaction: reject no-op stops (`new_stop == current_stop`) AND stale `prior_stop` (re-read live state inside transaction).

**Datetime + ordering discipline (Phase 7 Sub-B lesson):**
- TEXT datetime columns specify validator policy (naive-only OR canonicalized-to-UTC).
- Plan T1.0 schema specifies; implementation matches.

**HTMX dashboard discipline (CLAUDE.md gotcha family):**
- T5.0 web POST: `hx-headers='{"HX-Request": "true"}'` on embedded forms; success-path response is 204 + `HX-Redirect: <url>` (NOT 303 → swap-target).
- HX-Redirect target route MUST be verified to exist (Phase 6 I3 lesson).
- T5.1 dashboard tile: pure-OOB response architecture (no `<tr>`-leading fragment per Phase 2-Bug B `makeFragment` lesson).
- Reliability flags render as text badges, not color-only (per JS-test-harness gap awareness).

### §1.3 Worktree+editable-install verify-command discipline (Phase 5 lesson 2026-05-02)

When verifying T5.0/T5.1 web surfaces from inside the worktree, the verify-command MUST point at the worktree's package, not the editable-install path. PowerShell:
```
$env:PYTHONPATH = "."; python -m swing.cli web
```
Bash: `PYTHONPATH=. python -m swing.cli web`. Pytest is unaffected (cwd-based discovery); CLI entry points ARE affected (editable-install resolver).

### §1.4 Phase 8 specifics

**Migration:** `swing/data/migrations/0016_phase8_daily_management.sql` (NOT 0015 — that's Finviz V1 already shipped per plan §A.0). Schema bump v15 → v16. New `_phase8_backup_gate` function with condition `current_version == 15 AND target_version >= 16`. Pre-Phase-8 expected table set: `(PHASE7_EXPECTED_TABLES - {"exits"}) | {"fills", "finviz_api_calls"}`.

**Worktree branch:** `phase8-daily-management` (mirrors Phase 6 `phase6-post-trade-review` + Phase 7 `phase7-sub-c-web` naming convention).

**Test count target:** 1996-2041 fast tests post-merge (current baseline 1940 + planner-projected +55 to +100). Don't tighten acceptance criteria around the optimistic projection.

**Ruff baseline:** 78 errors pre-existing as of 2026-05-06 (per CLAUDE.md). Don't introduce new violations; don't try to fix the baseline incidentally.

**CLI scope:** V1-defer per plan §A.2. Do NOT implement `swing trade event-log` CLI in this dispatch. V2 follow-up queued separately.

**T7.0 operator-witnessed verification gate is BINDING.** Subagent-driven dispatch returns when all tasks T1.0-T6.0 complete green; T7.0 = operator browser verification of T5.0 (web POST) + T5.1 (dashboard tile + timeline). Operator may surface mid-verification fixes (per Phase 6 I3 + Phase 7 hotfix precedents); fix in worktree before merge.

---

## §2 Workflow (the binding 7-step sequence per 2026-05-02 convention)

### Step 1 — Worktree creation

Invoke `superpowers:using-git-worktrees`. Create worktree at `.worktrees/phase8-daily-management/` from base `17b1845` (BASELINE_SHA). Branch name: `phase8-daily-management`.

Verify:
```
git worktree list
git -C .worktrees/phase8-daily-management/ log --oneline -3
```

### Step 2 — Activate marker file (block subagent-side Codex)

```
cd .worktrees/phase8-daily-management
touch .copowers-subagent-active
```

This activates the global PreToolUse Codex-blocking hook at `~/.claude/hooks/block-copowers-during-subagent.sh` (registered in `~/.claude/settings.json`). The hook physically prevents subagents from invoking `copowers:adversarial-critic`, `copowers:review`, or `mcp__plugin_copowers_codex__codex*`. Subagent-driven dispatch operates in the worktree only.

### Step 3 — Subagent-driven development

Invoke `superpowers:subagent-driven-development`. Pass it the plan at `docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md`. Subagent executes tasks T1.0 through T6.0 in order with TDD discipline per task specification.

**Per-task discipline (binding):**
- RED test FIRST → see fail (capture pytest output) → minimal impl → GREEN → commit.
- Commit message format: `feat(area): Task X.Y — <description>` for impl; `fix(area): Codex R<N> Major <K> — <description>` for review fixes; `style(area): ...` for ruff cleanup (no task ID).
- Subject-only grep observable verification BEFORE each task commit: `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'` returns empty before; non-empty after.
- Per-task acceptance criteria from plan §2.1 binding.
- ruff check baseline preserved (78 errors pre-existing).
- Test count target: 1996-2041 fast tests post-T6.0.

**If a task surfaces a plan-vs-shipped-code divergence** (e.g., a function signature changed since plan-drafting), accept-with-rationale + propose corrected approach in commit body + flag in return report's "Plan deviations" section. Do NOT silently amend the plan.

### Step 4 — Deactivate marker file (allow Codex)

After all tasks complete green:
```
rm .copowers-subagent-active
```

### Step 5 — Adversarial Codex review

Invoke `copowers:adversarial-critic` directly with these parameters:

```
PHASE: executing-plans
SPEC_PATH: docs/superpowers/specs/2026-05-06-phase8-daily-management-design.md
PLAN_PATH: docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md
BASELINE_SHA: 17b1845
```

Iterate Codex review rounds to `NO_NEW_CRITICAL_MAJOR`. Each Codex finding: ACCEPT-with-rationale (in commit body) OR FIX (in new commit). Convergent chain expected per Phase 7 Sub-B + Phase 8/9 brainstorm + Phase 8 writing-plans lesson family — budget 4-6 rounds.

### Step 6 — Operator-witnessed verification gate (BINDING)

After Codex review reaches NO_NEW_CRITICAL_MAJOR:

1. Worktree-aware web start: `$env:PYTHONPATH = "."; python -m swing.cli web` from inside `.worktrees/phase8-daily-management/`.
2. Operator browser-verifies T5.0 web POST + T5.1 dashboard tile + timeline against open positions.
3. Operator surfaces any mid-verification defects (per Phase 6 I3 + Phase 7 hotfix family). Fix in worktree as `fix(area): code-review I<N> — <description>` commits BEFORE merge.
4. T7.0 PASS = operator confirms all T5.0/T5.1 surfaces work end-to-end in real browser.

### Step 7 — Integration merge

After T7.0 PASS:
```
git checkout main
git merge --no-ff phase8-daily-management
git push origin main
```

If `git merge --no-ff` produces a fast-forward warning, that's expected when no docs-on-main commits land between BASELINE_SHA and merge-time. Per Phase 6/7 precedent, multiple docs commits often land on main during executing-plans dispatches; `--no-ff` preserves the merge-commit-as-feature-marker pattern.

After merge:
- Worktree teardown: `git worktree remove .worktrees/phase8-daily-management/`. May need `Remove-Item -Force` on Windows ACL-locked subdirs (per Phase 6 + Phase 7 cleanup-script-extension lesson). If teardown fails on `pytest-of-rwsmy/` ACL pattern, run elevated cleanup script.
- Branch deletion: `git branch -D phase8-daily-management`.
- Verify worktree gone: `git worktree list` shows no entry.
- Verify production DB: `swing db-migrate` (explicit) bumps `swing-data/swing.db` to schema_version 16 (per memory `feedback_swing_db_migrate_explicit.md`).

---

## §3 OUT OF SCOPE (do not do)

- **Re-litigating plan decisions** — plan is locked.
- **Re-litigating spec decisions** — spec is locked.
- **Adding tasks beyond plan §2.1's 15 tasks** — flag plan gap in return report; don't silently extend.
- **Implementing CLI `swing trade event-log`** — V1-defer per plan §A.2; queued separately.
- **Modifying Phase 7 state machine** — query-side JOIN integration only.
- **Implementing intraday MFE/MAE precision tiers** — V1 ships `daily_approximate` only; tier 2+3 enum values reserved without emitter.
- **Schwab API Phase A coordination work** — separate dispatch chain.
- **Updating CLAUDE.md gotchas inline mid-dispatch** — orchestrator handles in housekeeping batch post-merge.
- **Updating `docs/orchestrator-context.md` mid-dispatch** — orchestrator handles in housekeeping batch post-merge (per 2026-05-04 "no main-side commits during executing-plans" lesson; worktree-side is fine).

---

## §4 Binding conventions (project-wide; from orchestrator-context §"Binding conventions")

- **Branch:** `main` for ship; `phase8-daily-management` worktree branch for dispatch.
- **Commits:** conventional. **No Claude co-author footer. No `--no-verify`. No amending.**
- **Commit-message format** (from §"Binding conventions"):
  - Task impl: `feat(area): Task X.Y — <description>`
  - Codex review fix: `fix(area): Codex R<N> Major <K> — <description>` (or `Minor <K>` for minors)
  - Internal-Codex fix: `fix(area): Codex R<N> Major <K> (internal) — <description>`
  - Code-review fix (operator-witnessed gate findings): `fix(area): code-review I<N> — <description>`
  - Format-only: `style(area): ruff <rule-id> cleanup` (no task ID)
- **Subject-only grep observable verification:** `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'` (the `-E` flag is REQUIRED — BRE doesn't support `+` as quantifier per Phase 7 implementer-side discovery).
- **TDD discipline:** RED test FIRST → see fail → minimal impl → GREEN → commit.
- **Phase isolation:** plan §"Files touched" enumerates in-scope paths per task. Out-of-scope paths require carve-out justification.
- **DB location:** `%USERPROFILE%/swing-data/swing.db` — outside Drive. NEVER violate.
- **Ruff:** baseline 78 (per CLAUDE.md). Don't introduce new violations.
- **`swing db-migrate` is EXPLICIT** (not auto-applied by `swing web`); per memory `feedback_swing_db_migrate_explicit.md`. Operator runs after merge.

---

## §5 Adversarial review parameters (Step 5)

```
PHASE: executing-plans
SPEC_PATH: docs/superpowers/specs/2026-05-06-phase8-daily-management-design.md
PLAN_PATH: docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md
BASELINE_SHA: 17b1845
DIFF: <auto-computed by Codex via git diff 17b1845..HEAD>
```

Watch items for Codex rounds (in addition to default DEVIL'S ADVOCATE / RED TEAM / STEELMAN):

1. **Plan compliance:** every task T1.0–T6.0 implemented; commit message format matches binding conventions; observable-verification grep returns expected.
2. **Spec compliance:** every spec §3-§7 locked decision is implemented as plan task; no silent design changes.
3. **Phase 7 lessons applied:** foreign_keys=OFF + executescript rollback + backup-gate condition + test fixture PRAGMA + table-rebuild constraint preservation.
4. **Phase 8 lessons applied:** SQLite REPLACE prohibition + `is_superseded` dual-column + per-row policy stamping.
5. **Phase 9 lesson applied:** state-machine integration via JOIN (no Phase 7 schema modifications beyond spec-locked column ADD).
6. **Phase 8 §A.1 lesson applied:** repo-level `update_stop_with_event` routing + TRADE-SCOPED max-id-after-insert + defense-in-depth validators.
7. **HTMX failure surfaces guarded** (T5.0/T5.1).
8. **Worktree-aware verify-command** specified for T5.0/T5.1 manual verification.
9. **Test count delta** falls within +55 to +100 range; ruff baseline preserved.
10. **Migration filename + backup gate function** wired correctly per plan §A.0.
11. **CLI V1-defer respected** — no `swing trade event-log` CLI shipped.
12. **No main-side commits during dispatch** (per 2026-05-04 lesson; orchestrator may have landed docs commits on main concurrent — those don't count; subagent-side commits all on worktree).

---

## §6 Operator-witnessed verification gate (Step 6) — BINDING

Per Phase 5/6/7 lesson family, T7.0 operator browser verification is BINDING for HTMX dispatches. TestClient-based tests verify response body structure; they do NOT verify runtime browser behavior (HTMX swap mechanics, HX-Redirect target resolution, OOB swap content delivery — see CLAUDE.md gotchas: `<tr>`-leading `makeFragment`; HX-Redirect-target-unrouted; embedded-form HX-Request propagation).

**Gate surfaces** (operator browser verification checklist):

1. **T5.1 dashboard tile** — open `/`. For each open position (state ∈ `{entered, managing, partial_exited}`), verify per-position tile renders: maturity_stage badge (text, not color-only), trail_MA_eligibility_flag (boolean text), open_MFE_R_to_date / open_MAE_R_to_date in R units, position_capital_utilization_pct (PROVISIONAL badge present), trail_MA_candidate_price displayed.
2. **T5.0 web POST `/trades/{id}/daily-management/event`** — submit an event_log entry via the web form. Verify: HX-Request header propagation (no 403 OriginGuard rejection); HX-Redirect target resolves (no 404 on landing); audit row written with correct prior_stop / new_stop / linked_trade_event_id values.
3. **T4.2 briefing extension** — verify briefing.md + briefing.html include the new daily_management section per spec §7.4 (closed in T4.2 from R1 fix; was deferred initially, brought into V1 scope).
4. **T4.0 pipeline-step idempotency** — run `swing pipeline run` twice in same session. Verify: second run is idempotent (same-day re-run no-ops on snapshot row; or updates active row in place per UPSERT; doesn't duplicate snapshots).
5. **T4.0 pipeline-step gap behavior** — skip a day. On next pipeline run, verify: missed-day flagged in §7.2 timeline as "(no snapshot — pipeline did not run)"; NO auto back-fill.
6. **End-to-end audit chain** — from a real open trade: verify event_log emit → audit row written → daily snapshot UPSERT → dashboard tile reflects current state. Cross-table FK chain intact.

**Mid-verification fixes** (per Phase 6 I3 + Phase 7 hotfix precedents): if any gate surface fails, fix in worktree as `fix(area): code-review I<N> — <description>` commits BEFORE merge. Pattern: same dispatch, additional commits; final integration merge happens AFTER all gate surfaces PASS.

---

## §7 Done criteria + Return report format

### Done criteria

1. Worktree branch `phase8-daily-management` exists from BASELINE_SHA `17b1845`.
2. All 15 plan tasks T1.0–T6.0 committed with per-task TDD discipline + observable-verification grep + plan-acceptance-criteria PASS.
3. Codex adversarial review reached `NO_NEW_CRITICAL_MAJOR`.
4. T7.0 operator-witnessed verification gate PASS (all 6 gate surfaces above).
5. Integration merge `git merge --no-ff phase8-daily-management` to main + push to origin.
6. Worktree teardown + branch deletion.
7. Production DB at schema_version 16 verified post-merge (`swing db-migrate`).
8. Fast-suite count: 1996-2041 tests; ruff baseline 78 preserved.

### Return report format

```
## Return report — Phase 8 daily-management executing-plans

### Worktree branch + integration merge
Worktree: `phase8-daily-management` (created from BASELINE_SHA `17b1845`)
Integration merge: `<sha>` to main on 2026-05-XX
Push: pushed to origin; main HEAD `<sha>`

### Task commit chain
T1.0 — `<sha>` `feat(data): Task 1.0 — migration 0016_phase8_daily_management`
T1.1 — `<sha>` `...`
[... all 15 tasks with sha + commit subject ...]

### Codex review history (Step 5)
- R1: {C/M/m findings; verdict; FIXED/ACCEPTED counts}
- R2: ...
- ...
- Final verdict: NO_NEW_CRITICAL_MAJOR
- Convergent chain documented per Phase 7 Sub-B + Phase 8/9 brainstorm + Phase 8 writing-plans lesson family.

### Operator-witnessed verification gate (Step 6)
- T5.1 dashboard tile: PASS / FAIL + mid-verification fixes
- T5.0 web POST: PASS / FAIL
- T4.2 briefing extension: PASS / FAIL
- T4.0 pipeline-step idempotency: PASS / FAIL
- T4.0 pipeline-step gap behavior: PASS / FAIL
- End-to-end audit chain: PASS / FAIL

### Mid-verification fixes (if any)
- `<sha>` `fix(area): code-review I<N> — <description>`

### Test count delta + ruff baseline
- Pre-dispatch: 1940 fast tests; ruff baseline 78
- Post-dispatch: <N> fast tests (+<delta>); ruff baseline <preserved/changed>

### Plan deviations (accept-with-rationale)
- ...

### Spec deviations (accept-with-rationale)
- ...

### Three highest-leverage implementation decisions
1. ...
2. ...
3. ...

### Worktree teardown
- Status: clean / locked-files-remain (with details)

### Production DB migration
- swing db-migrate output: schema_version v15 → v16 verified
```

---

## §8 If you get stuck

- If §1 strategic-context constraints conflict with what plan or spec proposes, §1 wins.
- If a plan task surfaces a shipped-code divergence that requires a non-plan-aligned approach, accept-with-rationale + propose corrected approach in commit body + flag in "Plan deviations" — do NOT silently amend the plan.
- If Codex Step 5 finds substantive issues (Critical or Major), iterate. Don't terminate at MAX_ROUNDS without operator escalation.
- If T7.0 gate fails on a surface, fix in worktree before merge. Don't merge a known-broken state.
- If worktree teardown fails on Windows ACL pattern (`pytest-of-rwsmy/`), run elevated cleanup script `cleanup-locked-scratch-dirs.ps1` per Phase 6/7 precedent. Don't force-delete; lose information.
- If migration runner discipline (foreign_keys=OFF, executescript rollback) appears missing in `_apply_migration` (shouldn't be — Phase 7 hotfix `283d4fa` landed it), STOP — flag as orchestrator-attention. Don't ship a migration that bypasses Phase 7's hard-won discipline.
- If two `update_stop_with_event` functions (Phase 8 §A.1 lesson) trip you — repo-level is the right call. NEVER route to service-level (`swing/trades/stop_adjust.py:105`) for Phase 8's `record_event_log` — service-level opens its own `with conn:` block which prematurely commits the outer transaction.
