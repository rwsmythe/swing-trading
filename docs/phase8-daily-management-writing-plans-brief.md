# Phase 8 Daily_Management Writing-Plans Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 8 writing-plans implementer. No prior conversation context.

**Mission:** Convert the Phase 8 daily-management design spec into a task-decomposed implementation plan. The plan ENUMERATES tasks; each task is an atomic unit (~1-3 commits) with TDD discipline (failing test first → minimal implementation → pass → commit). Plan is the binding contract executing-plans dispatch consumes; correctness of the plan is the gating quality. **NO code changes** — plan is a docs artifact landed at `docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md`.

**Brief:** `docs/phase8-daily-management-writing-plans-brief.md` (this file).

**Sequencing:** Phase 8 brainstorm SHIPPED 2026-05-06 at `c954eef` (875-line spec at `docs/superpowers/specs/2026-05-06-phase8-daily-management-design.md`). Phase 9 brainstorm SHIPPED 2026-05-06 at `31ee51c` (1090-line spec). Phase 10 brainstorm SHIPPED 2026-05-06 at `fe6cb45` (641-line spec). **Execution order locked: 8 → 9 → 10.** This dispatch is the FIRST execution-track step for Phase 8. Phase 8 writing-plans → Phase 8 executing-plans → Phase 9 writing-plans → Phase 9 executing-plans → Phase 10 writing-plans → Phase 10 executing-plans.

**Expected duration:** 90–180 minutes including 3–5 adversarial Codex rounds. Phase 6 writing-plans saw 5 rounds (5 Codex rounds → NO_NEW_CRITICAL_MAJOR; 1 R1 Critical fix added Task 12b cadence-completion path). Phase 7 writing-plans saw 4 rounds (13 substantive issues across R1+R2+R3, 2 advisory minors at R4). Convergent chain expected per Phase 7 Sub-B + Phase 8/9 brainstorm lesson family.

---

## §0 Read first

In this order:

1. **`CLAUDE.md`** at repo root — project conventions + gotchas. **Especially the SQLite `INSERT OR REPLACE` gotcha (added 2026-05-06)** — Phase 8's UPSERT pattern MUST use SELECT-then-UPDATE-or-INSERT; reject any plan task that proposes REPLACE.
2. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Recent decisions and framings" + "Lessons captured" — 35+ active lessons including 12+ Phase 7 lessons + 5+ Phase 8 lessons + 5 Phase 9 lessons that bind plan-task-specifications.
3. **`docs/phase3e-todo.md`** sections "2026-05-01 Journal v1.2 incorporation" (Phase 8 SHIPPED brainstorm marker; original-queued content retained for historical reference) + "2026-05-04 Schwab API integration" (Phase B data-source replaces yfinance; Phase 8 OHLCV consumption is yfinance V1) + "2026-05-04 Future schema migration: trade.entry_date datetime promotion" (Phase 8's `data_asof_session` consumer of `trades.entry_date` — date-only TEXT; not affected by future promotion).
4. **`docs/superpowers/specs/2026-05-06-phase8-daily-management-design.md`** — **THE BINDING SPEC.** All locked design decisions are here. Plan tasks implement what the spec specifies; plan-author MUST NOT re-litigate or modify spec decisions. If a spec ambiguity surfaces during plan-drafting that genuinely requires design clarification, ACCEPT-WITH-RATIONALE per round + flag as orchestrator triage in return report — do NOT silently amend the spec.
5. **`docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md`** §11 capture-needs feedback FOR PHASE 10 — context for Phase 8's downstream consumers (which Phase 8 fields Phase 10 dashboard reads at-render-time vs at-trade-time).
6. **`docs/superpowers/specs/2026-05-06-phase10-metrics-design.md`** §6.1 capture-needs FOR PHASE 8 — re-read for plan-task field-completeness check (every Phase 10 §6.1 listed field has a target column in Phase 8's locked schema; if not, that's an issue to surface).
7. **`swing/data/migrations/0014_phase7_state_machine_and_fills.sql`** — already-shipped Phase 7 schema; Phase 8's `daily_management_records.trade_id` FK targets `trades(id)`. Don't propose anything that conflicts.
8. **`swing/data/migrations/0013_phase6_post_trade_review.sql`** — already-shipped Phase 6 schema; review_log table (cadence-period grain).
9. **`swing/data/db.py:_apply_migration`** — current migration runner; Phase 7 hotfix `283d4fa` added foreign_keys=OFF discipline + executescript() partial-failure rollback. Phase 8 plan tasks inherit these patterns.
10. **`swing/data/ohlcv_archive.py`** + **`swing/data/repos/ohlcv_archive.py`** — Phase 3 OHLCV consolidated archive; Phase 8 V1 reads from this for `daily_approximate` MFE/MAE precision tier.
11. **`swing/pipeline/runner.py`** + per-step modules — for `_step_daily_management` integration (insert after `_step_evaluate`).
12. **One prior writing-plans plan for format reference** — `docs/superpowers/plans/2026-05-02-phase6-post-trade-review-plan.md` (Phase 6 plan; commit chain `1be4622..e976d64`; 5 Codex rounds → NO_NEW_CRITICAL_MAJOR; canonical writing-plans-output format).

---

## §0 Skill posture

- Invoke **`copowers:writing-plans`** (which wraps `superpowers:writing-plans` with adversarial Codex review). Iterate to `NO_NEW_CRITICAL_MAJOR`.
- DO NOT invoke `superpowers:executing-plans` — plan is design-only; no code changes.
- DO NOT invoke `superpowers:test-driven-development` — that's executing-plans territory; the plan SPECIFIES the test+impl pattern but doesn't write code.
- DO NOT invoke `superpowers:using-git-worktrees` — no code changes; spec/plan doc commits only.
- DO NOT invoke `superpowers:brainstorming` — design is locked; do not re-litigate.

---

## §1 Strategic context (ORCHESTRATOR-DISTILLED — what's NOT in the spec)

The following are accepted as **BINDING design constraints** without re-justification.

### §1.1 Spec is the binding contract

The Phase 8 spec at `docs/superpowers/specs/2026-05-06-phase8-daily-management-design.md` is the binding source of truth for all design decisions. Plan tasks IMPLEMENT what the spec specifies. Plan-author MUST NOT modify the spec OR introduce design alternatives.

If plan-drafting surfaces a genuine spec ambiguity (e.g., a field's CHECK constraint isn't fully specified in spec, OR an integration point isn't enumerated), the plan-author flags via:
1. Codex round adjudication if the ambiguity surfaces during review (ACCEPT-WITH-RATIONALE; flag in return report)
2. Orchestrator triage in the §7 return report's "open questions" section — do NOT silently amend

### §1.2 Phase 7 + Phase 8 + Phase 9 lessons are binding

The orchestrator-context "Lessons captured" section has 35+ active lessons. The following are PARTICULARLY binding for Phase 8 plan-task-specifications:

**Schema migration discipline (Phase 7 + Phase 8 lesson family):**
- SQLite `executescript()` partial-failure rollback wrapper (Phase 7 R1 Major 3) — already in `_apply_migration` per hotfix `283d4fa`; plan inherits.
- `foreign_keys=OFF` discipline at runner level for any table-rebuild (Phase 7 hotfix `283d4fa`) — already in `_apply_migration`; plan task inherits.
- Backup-gate condition: fires only on `current_version == 15 AND target >= 16` (Phase 7 Sub-A code-review I1).
- Test fixture PRAGMA discipline: every Phase 8 migration test fixture sets `foreign_keys=ON` to mirror production (Phase 7 hotfix `283d4fa`).
- Schema-rebuild constraint preservation (Phase 7 Sub-C R1 M1): if Phase 8 modifies `trades` table to add `planned_target_R`, ALL existing CHECK + FK constraints on `trades` must be enumerated + carried forward in the rebuild SQL (or the column-add must use `ALTER TABLE ADD COLUMN` if SQLite supports it for the target column type — single-column ADD likely OK without rebuild; plan-author verifies SQLite ALTER TABLE syntax limits).

**Audit-trail + UPSERT discipline (Phase 8 lesson family):**
- SQLite `INSERT OR REPLACE` is `DELETE + INSERT` semantically — REJECT in plan tasks. SELECT-then-UPDATE-or-INSERT only (CLAUDE.md gotcha 2026-05-06).
- `is_superseded` flag column + `superseded_by_record_id` FK pattern decouples uniqueness slot from audit pointer (Phase 8 R2 lesson) — already in spec §3.1; plan implements.
- Per-row policy-versioned value stamping prevents historical-row reinterpretation (Phase 8 R1 M5 lesson) — already in spec for `trail_MA_period_days`; plan implements.

**Datetime + ordering discipline (Phase 7 Sub-B lesson family):**
- Datetime impedance mismatch: `data_asof_session` (operator-meaningful date) vs creation-timestamp fields (system wall-clock) MUST be specified per-column.
- Lexicographic ordering on TEXT datetime columns: validator policy MUST be specified for every new TEXT datetime column with `ORDER BY` consumers.

**State-machine + integration discipline (Phase 9 lesson family):**
- State-machine integration via query-side JOIN, not schema flag, when grain mismatches (Phase 9 R1 Major #4 lesson) — Phase 8's `daily_management_records` is per-trade-per-session-per-precision-tier grain; integrates with Phase 7 `trades.state` via FK + query-side JOINs, NOT via flag columns on Phase 7 tables.

**Plan-authoring discipline (Phase 6 + Phase 7 lesson family):**
- Brief-premise empirical-verification (Phase 10 + 2026-05-04 lesson family): if the plan asserts shipped-code state, the plan-author verifies against actual code/migration files before encoding as task acceptance criteria.
- "Illustrative" placeholders in discriminating-test plan tasks are vacuous tests in disguise (Phase 7 R3 Major 3) — every discriminating test in plan tasks must specify the EXACT field + EXACT pre-fix expected value + EXACT post-fix expected value at plan-authoring time. NO `# TODO: pick real field` comments. NO labels like "illustrative" or "see task body for actual field."
- Adding a `cfg.X` field is a 3-edit cascade in `swing/config.py:load()` (Phase 6 R1 M3) — Phase 8 may not need this (no new cfg fields per spec); plan-author confirms.
- State-bearing entities require enumeration of ALL state-transition UI surfaces (Phase 6 R1 Critical 1) — Phase 8 spec §2.3 already enumerates lifecycle integration with Phase 7 state machine; plan inherits.

**Convergent-chain expectation (Phase 7 Sub-B + Phase 8 R2-R5 + Phase 9 R1-R4 lesson family):**
- Codex round count likely 4-5 rounds + 1 confirmation pass; convergent chain shape (each round catches fix-introduced regressions or freshly-exposed gaps) is healthy.
- Test count projections should bias high when discriminating-test discipline is in play (Phase 6 deviation observation; ~3x naive estimate). Phase 8 brainstorm spec at §4 + §6.2 calls for several discriminating tests; Phase 8 plan should project +30-60 tests (range, NOT a single number).

### §1.3 Spec compliance summary (binding for plan tasks)

The plan's tasks must collectively implement (NOT a deviation list — plan COMPLETES the following):

1. **Schema bump v15 → v16:** new `daily_management_records` table per spec §3.1 + ADD column `planned_target_R REAL` on `trades` per spec §1.2 carry-over decision.
2. **Migration discipline** per Phase 7 lessons (already in `_apply_migration` + plan-author confirms).
3. **Repo-layer:** new `swing/data/repos/daily_management.py` with insert + select + upsert (SELECT-then-UPDATE-or-INSERT — NOT REPLACE) functions + the §3.3 6-step transactional tier-upgrade sequence; SupersededRowImmutableException for write attempts on superseded rows.
4. **Service-layer:** new module(s) for snapshot computation (MFE/MAE from OHLCV archive for `daily_approximate` tier; spec §1.5 + §6); tier-upgrade logic (spec §6.1 audit-stability contract); event_log emission helper.
5. **Pipeline-step:** new `_step_daily_management` integrated after `_step_evaluate` per spec §2.2; idempotent UPSERT key `(trade_id, data_asof_session, mfe_mae_precision_level)`; GAP-FLAGGED no-auto-back-fill policy.
6. **Web POST `/trades/{id}/daily-management/event`** for event_log emission per spec §7.3 (writing-plans territory: locks the route shape + view-model + acceptance criteria).
7. **Dashboard tile** — per-open-position MFE/MAE-to-date + maturity_stage badge + trail_MA_eligibility_flag (spec §7.1; Phase 10 sketches the eventual full dashboard surface).
8. **CLI `swing trade event-log`** scope — locked decision per spec §10.3 ("writing-plans-decides scope"). Plan-author DECIDES (V1 web-only OR include CLI) + records rationale in return report.
9. **Tests** — discriminating tests per Phase 6 lesson; PRAGMA discipline; cross-tier upgrade tests; SupersededRow immutability tests; UPSERT same-tier-reflow tests; back-recorded-trade lookup tests.

### §1.4 What the plan must NOT do

- **NOT propose schema-level changes beyond what spec §3.1 specifies.** If plan-author finds a column nullable when it should be NOT NULL (or vice versa), accept-with-rationale + flag as spec ambiguity in return report.
- **NOT propose code-style alternatives** to spec-locked decisions (e.g., spec locks `is_superseded INTEGER` flag; plan does NOT propose `BOOLEAN`; SQLite's affinity is INTEGER).
- **NOT introduce new cfg fields** (per spec §1.4 carry-over: spec doesn't add new cfg; plan inherits).
- **NOT modify Phase 7 state machine** (per spec §2.3 + Phase 9 lesson; query-side JOIN is the integration pattern).
- **NOT propose intraday data ingestion** (spec §3 OUT OF SCOPE: V1 ships `daily_approximate` only).
- **NOT propose multi-precision tier ingestion** (V1 ships single tier; plan reserves enum values for V2+).

### §1.5 Plan-task-discipline binding conventions

Per orchestrator-context §"Binding conventions":

**Commit-message format (binding):**
- Task implementation commits: `feat(area): Task X.Y — <description>`
- Adversarial review-fix commits: `fix(area): Codex R1 Major 2 — <description>`
- Internal-Codex review-fix commits: `fix(area): Codex R1 Major 1 (internal) — <description>`
- Code-review fix commits: `fix(area): code-review I1 — <description>`
- Format-only cleanup commits: `style(area): ruff UP037 cleanup` (no task ID)

**Subject-only grep observable verification (Phase 4+ binding):**
- Subagent invokes `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'` BEFORE each task implementation commit.
- Returns empty: task hasn't been committed yet — proceed.
- Returns non-empty: task IS committed — abort + report duplicate.
- The `-E` flag is REQUIRED (BRE doesn't support `+` as quantifier per Phase 7 implementer-side discovery).

**TDD discipline (per task):**
- Failing test FIRST → see fail (run pytest; capture output) → minimal implementation → see pass → commit.
- Discriminating test specifications: EXACT field + EXACT pre-fix expected value + EXACT post-fix expected value.

**Worktree discipline (executing-plans phase, NOT writing-plans):**
- Plan SPECIFIES that executing-plans dispatch uses worktree isolation (per 2026-05-02 binding convention).
- Plan does NOT itself create a worktree (plan-drafting is doc-only).
- Plan's §"Done criteria" includes "worktree branch merged via `git merge --no-ff` to main."

---

## §2 Plan-drafting scope (in scope)

Produce a plan at `docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md` covering:

### §2.1 — Task decomposition

Each task specifies:
- **Task ID** (e.g., `1.0`, `2.1`, `4.0a` — see Phase 4 carve-out lesson family for sub-letter conventions when a task has carve-outs).
- **Title** — short noun-phrase + verb describing the deliverable.
- **Files touched** — explicit list (in scope) + implicit list (test files; verify-command outputs).
- **TDD specification:**
  - Discriminating test(s) FIRST: filename + test name + EXACT pre-impl expected value (e.g., "raises NotImplementedError" or "returns None") + EXACT post-impl expected value.
  - Implementation: minimal code path to flip the test from RED to GREEN.
- **Acceptance criteria:** what must be true after this task lands (e.g., "all existing tests still pass; new test {test_name} passes; ruff check baseline preserved").
- **Verify command(s):** specific shell command(s) the implementer runs after task lands.
- **Estimated test count delta:** new tests added by this task.

Recommended task ordering (plan-author refines):
- T1.0 — Migration 0015 SQL drafted (CREATE TABLE daily_management_records + ALTER TABLE trades ADD planned_target_R) + migration test (`test_migration_0015.py`) verifying table exists + correct columns + CHECK constraints + FK targets.
- T1.1 — `_apply_migration` invocation test (verify foreign_keys=OFF discipline + executescript rollback per Phase 7 hotfix patterns; backup-gate fires on v15 → v16 only).
- T1.2 — Test fixture PRAGMA discipline (every fixture connection sets foreign_keys=ON to mirror production).
- T2.0 — Repo-layer `swing/data/repos/daily_management.py:insert_snapshot` + tests.
- T2.1 — `select_active_snapshot` (returns row where is_superseded = 0) + tests.
- T2.2 — `select_history` (returns full chain including superseded rows) + tests.
- T2.3 — `upsert_snapshot` SELECT-then-UPDATE-or-INSERT pattern + tests (same-tier reflow updates active row in place; rejects REPLACE) + SupersededRowImmutableException test.
- T3.0 — Service-layer `swing/services/daily_management.py:compute_daily_approximate_snapshot` (consumes OHLCV archive; produces snapshot row) + tests.
- T3.1 — Tier-upgrade transactional 6-step sequence per spec §3.3 + tests (exact-PK predecessor capture; concurrent-write rejection on superseded rows; cross-tier insert as additive row).
- T3.2 — `record_event_log` single-transaction contract per spec §3.4 + tests (operator-discretionary event emission; minimal required fields per validator).
- T4.0 — Pipeline-step `_step_daily_management` (post-`_step_evaluate`; idempotent same-day re-run; GAP-FLAGGED no-auto-back-fill) + tests.
- T4.1 — Pipeline integration test (full run including new step; verify snapshots emitted for open trades only).
- T5.0 — Web POST `/trades/{id}/daily-management/event` route + view-model + tests (operator submits event_log entry; HX-Redirect or OOB swap target per Phase 6/7 patterns).
- T5.1 — Dashboard tile per-open-position rendering + tests (maturity_stage badge; trail_MA_eligibility_flag; Phase 10 placeholder fields render as "[Phase 8 capture pending]" until §6.1 captures land — actually they're now ALL captured, so render real values).
- T6.0 — CLI `swing trade event-log` (if plan-author decides V1-include) + tests.
- T7.0 — Cleanup: ruff check; full test suite; documentation refresh (CLAUDE.md gotchas if Phase 8 surfaces any new code-failure-prevention pattern; `docs/cycle-checklist.md` if operator workflow changes).

### §2.2 — Per-task acceptance criteria (binding format)

Every task in §2.1 specifies acceptance criteria using this format:

```
ACCEPTANCE:
- All existing fast tests pass (target: 1940 + N where N = task-incremental count).
- New test(s) pass: {test_name_1}, {test_name_2}, ...
- ruff check baseline preserved (78 pre-existing as of 2026-05-06).
- {Task-specific criterion 1}
- {Task-specific criterion 2}
- Subject-only grep returns empty before commit; non-empty after commit.

VERIFY COMMAND(S):
$ python -m pytest tests/data/test_migration_0015.py -q
$ ruff check swing/
$ git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 1\.0'
```

### §2.3 — Schema migration task discipline (T1.x)

Per Phase 7 hotfix `283d4fa` lesson family — the migration runner already has the discipline; plan-tasks INHERIT but VERIFY:

- `_apply_migration` saves + sets foreign_keys=OFF before executescript; restores after (try/finally).
- `_apply_migration` wraps executescript+commit in try/except; rollback + re-raise on partial failure.
- Test: malformed migration with deliberate fail-mid-sequence; verify probe table doesn't exist post-failure AND `conn.in_transaction == False`.
- Test: backup gate fires ONLY on `current_version == 15 AND target >= 16` (NOT on fresh DB / mid-walk).

### §2.4 — Test count projection

Plan §"Test count projection" enumerates expected new tests per task with subtotal + total. Bias high per Phase 6 lesson (~3x naive task-count × tests-per-task when discriminating-test discipline binding). Phase 8 expected delta range: **+30 to +60 fast tests**. Don't tighten plan dispatch acceptance criteria around the optimistic projection; bake the range into the projected test count.

### §2.5 — CLI scope decision (per spec §10.3)

Plan-author DECIDES whether V1 includes CLI `swing trade event-log` OR ships web-only. Either decision is defensible:
- **V1-include:** consistent with Phase 6/7 CLI parity precedent; small additional task; no other surface affected.
- **V1-defer:** consistent with Phase 6 review surface's web-only-V1 precedent (CLI parity for review_log added separately later); reduces task count.

Plan-author documents the decision + rationale in §"Three highest-leverage plan decisions" of return report.

### §2.6 — Open questions for orchestrator triage

Per Phase 6 + Phase 7 + Phase 8 + Phase 9 brainstorm pattern (open questions enumerated; not blocking on executing-plans dispatch).

Likely categories:
- Spec ambiguities surfaced during plan-drafting that genuinely need orchestrator clarification.
- Test-fixture data design choices (e.g., mock OHLCV archive vs use Phase 3 archive).
- Worktree branch name (Phase 8 dispatch convention).
- Migration test discipline edge cases (e.g., what if v15 → v16 backup gate fires on a fresh DB during testing? plan tests both happy-path AND edge-case).

---

## §3 OUT OF SCOPE (do not do)

- **Schema design changes** — spec is binding. If plan-author wants to add/remove a column, accept-with-rationale + flag as spec ambiguity in §2.6.
- **Code drafting** — plan SPECIFIES tests + implementation patterns; doesn't write the actual code. Executing-plans dispatch consumes the plan.
- **Worktree creation** — that's executing-plans territory.
- **Migration SQL drafting** — plan T1.0 SPECIFIES the migration SQL shape (column list + types + CHECK constraints + FK targets) but the actual migration file lands in executing-plans phase.
- **Re-litigating spec decisions** — accept as given.
- **Phase 9 / Phase 10 design** — Phase 9/10 specs ALREADY shipped; their writing-plans dispatches happen later per locked sequencing.
- **Schwab API Phase A coordination** — Phase 8 is yfinance-only; Schwab is a separate brainstorm/writing-plans/executing-plans chain.

---

## §4 Binding conventions

- **Branch:** `main`. Single commit OR landing+fixes split per Phase 6/7/8/9 brainstorm precedent if Codex finds substantive issues.
- **Commit message:** `docs(phase8): Phase 8 daily-management writing-plans plan`. No Claude co-author footer. No `--no-verify`. No amending.
- **Plan format:** mirror `docs/superpowers/plans/2026-05-02-phase6-post-trade-review-plan.md` (Phase 6 plan) + `docs/superpowers/plans/2026-05-04-phase7-trade-state-machine-plan.md` (if it exists; reference for state-machine plan format) — section-numbered; per-task TDD specifications; orchestrator-triage open questions enumerated.
- **Plan line target:** ~600–1100 lines (Phase 6 plan was canonical writing-plans output; Phase 8 spec is 875 lines so plan likely 800-1100 lines; if exceeding 1100, re-scope per task-decomposition discipline).
- **Adversarial review:** mandatory; iterate to `NO_NEW_CRITICAL_MAJOR`. Budget 4–5 substantive rounds + 1 confirmation pass per Phase 7/8/9 brainstorm-chain expectation.

---

## §5 Adversarial review watch items

For Codex rounds — pass these as targeted prompts to `copowers:adversarial-critic`:

1. **Spec compliance.** Every spec §3-§7 locked decision is implemented by exactly one plan task (or explicitly out-of-scope-with-rationale per §2.6). Cross-check spec § index against plan-task index.
2. **Phase 7 schema-rebuild constraint preservation (lesson 2026-05-05).** If plan T1.0 modifies `trades` for `planned_target_R` via TABLE REBUILD (not ADD COLUMN), the migration SQL enumerates EVERY existing CHECK + FK on `trades` + carries them forward. Plan task spec calls this out.
3. **SQLite `INSERT OR REPLACE` prohibition (CLAUDE.md gotcha 2026-05-06).** No plan task proposes REPLACE against any FK-referenced or audit-trail table. SELECT-then-UPDATE-or-INSERT only. Audit T2.3 + T3.1 + T4.0 specs.
4. **`is_superseded` flag pattern (Phase 8 R2 lesson).** Plan T2.3 + T3.1 implement the dual-column pattern correctly per spec §3.3 6-step transactional sequence. Predecessor capture by exact PK. SupersededRowImmutableException for write attempts on superseded rows.
5. **Per-row policy-versioned value stamping (Phase 8 R1 M5 lesson).** Plan T1.0 schema includes `trail_MA_period_days INTEGER` per-row stamp; T3.0 writes it at snapshot-emit-time using current default (21).
6. **Datetime impedance + lexicographic ordering (Phase 7 Sub-B lesson).** Plan T1.0 specifies validator policy for every TEXT datetime column. `data_asof_session` (operator-meaningful date) is naive-only; creation-timestamp (system wall-clock) is naive-UTC.
7. **Discriminating-test specifications (Phase 7 R3 Major 3 lesson).** EVERY task's discriminating test specifies EXACT field + EXACT pre-impl expected value + EXACT post-impl expected value. NO `# TODO`. NO "illustrative." Codex rejects vacuous tests.
8. **Test count projection biased high (Phase 6 lesson).** Plan §"Test count projection" projects +30 to +60 fast tests (range, not single number). NOT optimistic projection that constrains executing-plans acceptance.
9. **PRAGMA test-fixture discipline (Phase 7 hotfix `283d4fa` lesson).** Every Phase 8 migration-test fixture sets `foreign_keys=ON` to mirror production. Plan T1.2 calls out + implements.
10. **Backup-gate condition (Phase 7 Sub-A I1 lesson).** Plan T1.1 verifies backup gate fires ONLY on `current_version == 15 AND target >= 16`. NOT on fresh DB. NOT on mid-walk.
11. **State-machine integration via JOIN (Phase 9 R1 M4 lesson).** Plan T5.1 dashboard tile reads Phase 8 snapshot + Phase 7 trade state via query-side JOIN. NO modifications to Phase 7 state machine OR `trades` table flag columns.
12. **Phase 10 §6.1 capture-need completeness.** Cross-check plan T1.0 schema column list against Phase 10 §6.1 binding capture list. Every Phase 10-listed field has a target column. If a field is NOT captured by Phase 8, plan flags as Phase 10+ NEW capture (per Phase 8 spec §11 hand-off).
13. **CLI scope decision documented (§2.5).** Plan §"Three highest-leverage plan decisions" includes the CLI scope decision + rationale. Codex catches if absent.
14. **Subject-only grep regex (Phase 4+ binding convention).** Every task's verify command includes the `-E` flag for subject-only grep. Codex catches if regex form is BRE.
15. **Convergent-chain expectation (Phase 7 Sub-B + Phase 8 R2-R5 + Phase 9 R1-R4).** Implementer's return report documents fix-introduced-regression vs adversarial-thrash distinction.
16. **Plan-task acceptance criteria binding format (§2.2).** Every task's ACCEPTANCE block specifies: existing tests pass + new test(s) pass + ruff baseline preserved + task-specific criteria + subject-only grep behavior.
17. **Operator-actionability test (Phase 10 watch-item 11 inheritance).** T5.1 dashboard tile + T5.0 web POST surfaces answer "what action does the operator take?" Plan flags any surface that's monitoring-only.
18. **Brief-premise empirical-verification (Phase 10 + 2026-05-04 lesson family).** Plan-author verifies any code-state assertion against actual code/migration files. If brief or spec asserts shipped-state X, plan-author confirms.

---

## §6 Done criteria

1. Plan at `docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md` covering §2.1–§2.6.
2. Plan went through ≥3 Codex rounds reaching `NO_NEW_CRITICAL_MAJOR`.
3. Plan section structure mirrors prior writing-plans-output format; tasks numbered + per-task TDD specifications + acceptance criteria + verify commands explicitly delimited.
4. Single commit OR landing+fixes split landed: `docs(phase8): Phase 8 daily-management writing-plans plan` (and follow-up commits `docs(phase8): Phase 8 daily-management plan — Codex R1-R<N> fixes` if applicable).
5. Return report covers items in §7.

---

## §7 Return report format

```
## Return report — Phase 8 daily-management writing-plans

### Plan location
`docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md` ({line count} lines)
Commits on main:
- {sha} `docs(phase8): Phase 8 daily-management writing-plans plan` (initial)
- (optional) {sha} `docs(phase8): Phase 8 daily-management plan — Codex R1-R<N> fixes` (post-review)

### Codex review history
- R1: {C/M/m findings; verdict; FIXED/ACCEPTED counts}
- R2: ...
- ...
- Final verdict: NO_NEW_CRITICAL_MAJOR
- Convergent chain documented (per Phase 7 Sub-B + Phase 8/9 lesson family).

### Three highest-leverage plan decisions
1. ...
2. ...
3. ...

### CLI scope decision (§2.5)
Locked: V1-include / V1-defer.
Rationale: ...

### Task count + test count projection
- Total tasks: N
- Test count projection: +X to +Y fast tests (range, not single number, per Phase 6 lesson)
- Estimated executing-plans dispatch effort: M-N hours

### Open questions for orchestrator triage
1. ...
2. ...

### Spec ambiguities surfaced (deferred via accept-with-rationale)
- ...

### Capture-need completeness check (Phase 10 §6.1 cross-reference)
- ...
```

---

## §8 If you get stuck

- If §1 strategic-context constraints conflict with what the spec proposes, §1 wins.
- If the spec genuinely surfaces an ambiguity that plan-drafting cannot resolve, ACCEPT-with-rationale + flag as orchestrator triage in §2.6 + return report. Do NOT silently amend the spec.
- If the plan exceeds ~1100 lines, re-scope task decomposition (likely some tasks are too granular OR too many sub-letters).
- DO NOT modify the spec. DO NOT propose schema changes. DO NOT write code. If you start drafting `CREATE TABLE ...` or `class FooVM`, stop — that's executing-plans territory.
- If a Phase 7/8/9 lesson conflicts with a plan-task proposal, the prior lesson wins. Surface the conflict.
- If you encounter the JS-test-harness gap pattern in T5.1 dashboard tile or T5.0 web POST, flag for executing-plans operator-witnessed verification gate.
- If the discriminating-test specifications in §2.1 require concrete fields that aren't yet shipped (e.g., something Phase 10 will add), flag in §2.6 — Phase 8 plan tests should NOT depend on Phase 10 schema.
