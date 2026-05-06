# Finviz Elite API Integration — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute `docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md` end-to-end on a worktree-isolated branch via the marker-file Codex-blocking workflow + post-execution adversarial Codex review; iterate to `NO_NEW_CRITICAL_MAJOR`. Operator-witnessed verification gate is BINDING before main-merge. **The plan is the binding spec** — every §A-K binding-spec section + §"Tasks" specification + §K verification gate + §Z done criteria + §AA test-count band + §CC notable risks have already been Codex-reviewed across 5 rounds → `NO_NEW_CRITICAL_MAJOR`. Your job is implementation, not re-design.

**Expected duration:** ~6-10 hours TDD work + ~3 Codex rounds → `NO_NEW_CRITICAL_MAJOR` on the executing-plans diff. ~12 tasks; +53 fast tests projected (+30 to +60 band; biased high per Phase 6 lesson on test-count projection).

**Critical pre-condition:** operator must have populated `%USERPROFILE%/swing-data/user-config.toml` `[integrations.finviz]` section with valid `token` + `screen_query` BEFORE this dispatch starts. Plan §D codifies this as binding for Task 0.b live verification. If user-config is missing or values are placeholders, halt at Task 0.b and surface to operator.

---

## §0 — Read first

In this order:

1. **`docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md`** — full plan; binding spec. Pay particular attention to §A (research findings + design decisions), §B (file map), §C (migration SQL canonical reference), §D (open question — Task 0.b operator-gate), §E (synthesized endpoint reference; verify at Task 0.b), §F (filename anchor convention), §G (cassette runbook), §H (`_step_finviz_fetch` algorithm), §I/§J (cycle-checklist + CLAUDE.md updates), §K (verification gates), §"Tasks", §Z (done criteria), §AA (test-count projection), §CC (notable risks).
2. **`docs/finviz-api-integration-writing-plans-brief.md`** — the brief that produced the plan. Strategic context + locked V1 design + adversarial-review watch items context. The plan is the binding spec; this brief is background.
3. **`docs/orchestrator-context.md`** §"Binding conventions" + §"Anti-patterns" + §"Lessons captured" (most-recent 30) + §"Maintenance: retention discipline" — binding for execution discipline. Especially relevant: cfg.X 3-edit cascade; plan templates assertion errors; closed_date is derived not stored; test count projections bias high; HX-Redirect (N/A here); foreign_keys=ON test fixture; documented-but-unimplemented handoff items; subprocess cfg-propagation (newest discipline; Codex R2 caught this in writing-plans review and the plan addresses it at Task 2.5 — verify implementation).
4. **`CLAUDE.md`** — project conventions + gotchas. Especially relevant: Finviz inbox section; pipeline lease semantics; SQLite WAL-mode `Connection.backup()` discipline; ruff baseline (78 errors at HEAD `808b693` per writing-plans return report; verify at Task 0 pre-flight).
5. **`docs/phase5-configuration-page-executing-plans-brief.md`** — canonical executing-plans brief template (worktree-isolated + marker-file workflow). Reference for skill invocation order, NOT for content.
6. **`docs/phase7-sub-c-web-executing-plans-brief.md`** — most-recent executing-plans brief; reference for verification-gate style + Codex review chain.

After reading, you should have full context for: what the plan binds, what the brief allows you to do, and how the worktree+marker-file workflow operates.

---

## §0 — Skill posture (binding workflow)

The standing executing-plans dispatch convention since 2026-05-02 (Phase 5 lesson: extended-time-window subagent self-collision; archived). Worktree isolation is REQUIRED, not optional, for any plan with sub-task commits + intermediate state mutations to shared files.

**Workflow:**

1. **Worktree creation:** invoke `superpowers:using-git-worktrees`. Branch name: `finviz-api-integration` (matches plan filename convention). Base from current `main` HEAD (BASELINE_SHA below). If a worktree at this branch already exists from a prior aborted dispatch, surface to operator before proceeding.
2. **Marker-file activation:** `touch .copowers-subagent-active` at worktree root. This activates the global PreToolUse hook at `~/.claude/hooks/block-copowers-during-subagent.sh` (registered in `~/.claude/settings.json`); subagents physically cannot invoke `copowers:adversarial-critic`, `copowers:review`, or `mcp__plugin_copowers_codex__codex*` while the marker file exists. Mid-task Codex invocation by subagents is the failure mode the marker prevents.
3. **Subagent-driven implementation:** invoke `superpowers:subagent-driven-development` to execute the plan's `## Tasks` section. Each task ships TDD red → green → commit per the plan's per-task spec.
4. **Marker-file deactivation:** `rm .copowers-subagent-active` after ALL plan tasks complete + all in-cycle review fixes (internal code-review I-prefix + internal-Codex `(internal)` qualifier — see binding conventions). Verify marker is removed before invoking adversarial-critic.
5. **Adversarial review:** invoke `copowers:adversarial-critic` directly with `PHASE=finviz-api-integration`, `SPEC_PATH=docs/finviz-api-integration-writing-plans-brief.md`, `PLAN_PATH=docs/superpowers/plans/2026-05-05-finviz-api-integration-plan.md`, `BASELINE_SHA=<see below>`. Iterate to `NO_NEW_CRITICAL_MAJOR`. Expected 2-4 rounds (writing-plans phase already absorbed 5 rounds of design-time review; executing-plans should be lower).
6. **Operator-witnessed verification gate:** plan §K specifies the BINDING verification gate. Surface to operator with the §K checklist when adversarial review reaches `NO_NEW_CRITICAL_MAJOR`; operator runs the gate and reports PASS / FAIL per surface. Operator MAY surface mid-verification fixes; land them inside the worktree as `code-review I<N>` commits before merge.
7. **Integration merge:** after operator-witnessed gate PASS, `git checkout main && git merge --no-ff finviz-api-integration -m "Merge finviz-api-integration into main"`. Push to origin.

**DO NOT INVOKE:**
- `superpowers:brainstorming` — design is locked.
- `superpowers:writing-plans` — plan is shipped.
- `copowers:executing-plans` (the wrapper) — bundles `subagent-driven-development` + `adversarial-critic` without marker-file management between them; physically incompatible with the binding convention.
- `copowers:adversarial-critic` MID-DISPATCH (i.e., during subagent execution; the marker file blocks this). Only invoke at end-of-dispatch per step 5 above.

**MARKER-FILE DISCIPLINE:** the `.copowers-subagent-active` marker file is the binding mechanism preventing extended-time-window subagent self-collision. If you find yourself invoking `copowers:adversarial-critic` and the marker is absent, halt + surface — the marker should be present from worktree creation through end of all task commits. If you find yourself executing tasks and the marker is somehow absent, halt + surface — re-create marker before continuing.

---

## §1 — BASELINE_SHA + worktree branch

**BASELINE_SHA: `808b693`** (the writing-plans brief commit; plan file landed in subsequent commits `4e5c066..734ba6f`. The executing-plans dispatch baselines from `808b693` to include the brief but not the plan-fix-iteration history; alternative is `734ba6f` if implementer prefers latest plan HEAD as baseline. Per Phase 7 Sub-A precedent, plan-iteration commits are part of the writing-plans dispatch's scope; executing-plans baselines after them. Implementer may verify by inspecting `git log 808b693..734ba6f` — all 5 commits are docs/superpowers/plans/.).

**Recommended baseline: `734ba6f`** (latest plan HEAD; cleaner adversarial-critic invocation).

**Worktree branch name: `finviz-api-integration`** (mirrors plan filename convention; not phase-prefixed because Finviz API is standalone — not part of the journal-v1.2 phase sequence).

**Worktree path:** `.worktrees/finviz-api-integration/` (per project convention).

---

## §2 — Pre-condition: operator user-config check (Task 0.a addresses)

Plan Task 0.a runs ruff baseline + fast-test count + schema_version capture as standard pre-flight. Add to Task 0.a (or include as Task 0.a-prelim before any other work):

1. Verify `%USERPROFILE%/swing-data/user-config.toml` exists.
2. Verify the file contains `[integrations.finviz]` section with `token` and `screen_query` keys.
3. Verify neither value is the placeholder string from the brief (e.g., `REPLACE_WITH_YOUR_FINVIZ_ELITE_TOKEN`, `REPLACE_WITH_YOUR_SCREEN_QUERY_STRING`).
4. **DO NOT log token or screen_query content during this check** — only assert presence + non-placeholder.
5. If any check fails, halt + surface to operator: "user-config.toml at <path> is missing/incomplete; populate `[integrations.finviz]` section before dispatch resumes."

This pre-condition gate makes Task 0.b live verification operator-token-aware without blocking on operator activity mid-dispatch.

---

## §3 — Execution scope (cite plan)

The plan's `## Tasks` section is the binding scope. **Do NOT re-scope.** The plan's §B file map enumerates new + modified files; do NOT touch files outside this map without surfacing as scope deviation.

Task summary (per writing-plans return report; full specs in plan):

- **Task 0** — Pre-flight (ruff baseline, fast-test count, schema_version capture); user-config pre-condition check (this brief §2); Task 0.b one-time live API verification (BLOCKS Task 2 cassette recording until pass).
- **Task 1** — Migration 0015 (`finviz_api_calls` table) + `FinvizApiCall` dataclass + repo (`insert_call`, `list_recent_calls`, `get_latest_signature_hash`).
- **Task 2** — Cfg cascade for `[integrations.finviz]`. `load()` strips token + screen_query (security per §A.6); `apply_overrides()` reads from user-config via N-part-aware `_get`; FIELD_REGISTRY NOT extended in V1.
- **Task 3** — `FinvizClient` happy-path: token loading, `fetch_screen()`, normalize to canonical 13-column CSV, signature-hash; cassette-based tests; `_suppress_transport_debug_logs` context manager (per §A.12 Codex R1 Major-2 fix).
- **Task 4** — `FinvizClient` error paths: 4xx, 5xx, 429 retry-success, 429 give-up, 429-then-429, network errors; hand-crafted cassettes.
- **Task 5** — Signature-hash determinism + sensitivity tests (column-set / first-row-Ticker / first-row-Sector / row-order / column-order-invariance).
- **Task 6** — `_step_finviz_fetch(*, cfg, lease)` (pipeline) + `_perform_finviz_fetch_no_lease(*, cfg, conn)` (CLI) sharing `_finviz_fetch_core`; shadow-promote-then-audit ordering with downgrade-on-file-error; recovery sweep for stale `.api-pending` files; `_assert_no_active_pipeline_run` cross-surface exclusion. Two distinct lease-revoke discriminating tests (per §A.13 + §A.14).
- **Task 7** — Source-text inspection tests pinning ordering (`_step_finviz_fetch` before `_step_evaluate`) + try/except wiring contract.
- **Task 8** — `swing finviz fetch` + `swing finviz status` Click commands; CLI applies overrides via Phase 5 convention; `FinvizPipelineActiveError` translated to friendly `ClickException`.
- **Task 9** — Slow-marked live integration test pair (live happy-path + signature-stable-within-session); skip when token absent.
- **Task 10** — Token-leak sentinel audit covering logs / DB rows / committed cassettes / urllib3 DEBUG output.
- **Task 11** — CLAUDE.md gotchas (5 new) + cycle-checklist update + lessons captured update (subprocess cfg-propagation lesson — see §6 below).

Each task's RED phase test + GREEN phase implementation + commit are specified in the plan body verbatim. Implementer adapts wording to current line-numbers at edit time per writing-plans return report Open Question 3 ("doc updates: implementer adapts wording to current line-numbering at edit time").

---

## §4 — Binding conventions (cite project standards)

Per `docs/orchestrator-context.md` §"Binding conventions" — full text there. Salient items for this dispatch:

- **Branch:** worktree branch `finviz-api-integration`. Merge to `main` at end via `git merge --no-ff`.
- **Commits:** conventional-commits. **No Claude co-author footer. No `--no-verify`. No amending.**
  - Task implementations: `feat(area): Task X.Y — <description>`. ERE+POSIX subject-only grep observable verification before each task commit.
  - Adversarial review-fix commits: `fix(area): Codex R1 Major 2 — <description>` etc.
  - Internal-Codex commits (subagent-driven within-task): `fix(area): Codex R1 Major 1 (internal) — <description>`.
  - Internal code-review fix commits: `fix(area): code-review I1 — <description>`.
  - Format-only cleanup: `style(area): ruff UP037 cleanup`.
- **TDD:** failing test first, minimal implementation, pass, commit. One red-green cycle per logical change.
- **Phase isolation:** Finviz API is standalone — no carve-out beyond plan §B file map. Surface scope deviations.
- **DB location:** `%USERPROFILE%/swing-data/swing.db` outside Drive.
- **Tests:** `python -m pytest -m "not slow" -q` is the fast suite; must stay green at every task commit boundary. `python -m pytest -m slow` runs Task 9 live integration tests (requires populated user-config.toml).
- **Ruff:** baseline 78 errors at writing-plans baseline; verify at Task 0 pre-flight; do not introduce new violations; do not fix the baseline incidentally.
- **Schema migration runner discipline:** `_apply_migration` already toggles `foreign_keys=OFF` per Phase 7 hotfix `283d4fa`. Migration 0015 is additive (CREATE TABLE only); no FK CASCADE risk; test runs with `foreign_keys=ON` to mirror production per Phase 7 Sub-A lesson.
- **Worktree + editable-install verify-command:** for runtime verification (e.g., `swing finviz fetch` from CLI inside the worktree), use `$env:PYTHONPATH = "."; python -m swing.cli finviz fetch` to override the editable-install pointer. Pytest is unaffected (cwd-based discovery).

---

## §5 — Adversarial review (cite plan §CC + writing-plans watch items)

The writing-plans dispatch's adversarial-review watch items (brief §7) are addressed in the plan; do NOT re-litigate them. New executing-plans-phase watch items emerge at the implementation boundary:

1. **Plan-template assertion errors at fixture instantiation** (per Phase 6 lesson): plan-supplied test fixtures use `ensure_schema(db_path)` for fresh DBs, NOT `connect(db_path)`. Verify before running tests.
2. **`closed_date` is derived not stored** — N/A here (no trades touched in V1).
3. **Test count projections bias high** — plan projects +53 fast tests; if executing-plans produces materially fewer (e.g., +30 fast), surface in return report — likely indicates test-discipline gaps.
4. **Multi-path data ingestion** — plan addresses pipeline `_step_finviz_fetch` + standalone CLI `swing finviz fetch` both writing to `data/finviz-inbox/`. Verify both paths produce equivalent state (DB + filesystem) given identical inputs.
5. **Token-leak sentinel audit (Task 10)** — discriminating: introduce a known sentinel token in user-config; run full fetch + error paths; grep all log output + DB rows + committed cassettes for the sentinel. Test FAILS if found.
6. **Subprocess cfg-propagation (per writing-plans R2 finding)** — verify Task 2.5 implementation: web route `/pipeline/run` spawns `python -m swing.cli pipeline run`; the CHILD's CLI body MUST call `apply_overrides()` for the Finviz cfg fields to propagate. Discriminating test pinning the contract is in the plan; verify it actually exercises the subprocess boundary.
7. **Cassette token-redaction** — committed cassettes MUST have token redacted. Verify: a test reads each committed cassette and asserts `auth=<REDACTED>` (or equivalent) present, raw token absent. Use VCR's `filter_query_parameters=["auth"]` per plan §A.

Pass these to `copowers:adversarial-critic` as supplementary watch items. Critic verifies addressed in implementation; verdict at `NO_NEW_CRITICAL_MAJOR`.

---

## §6 — New lesson to capture in Task 11

In addition to plan §J's CLAUDE.md additions, add to `docs/orchestrator-context.md` §"Lessons captured" (after the existing 30-entry cap; oldest entry migrates to archive per retention discipline):

> **Subprocess cfg-propagation: child-process CLI body is the binding override point, NOT the parent process that spawns it.** Lesson from Finviz API integration writing-plans Codex R2 (2026-05-05). Web route `/pipeline/run` spawns `python -m swing.cli pipeline run`; cfg overrides applied to the web-route's process do NOT propagate to the child via in-memory state. Override-load must live in the child CLI's body. Plan Task 2.5 codifies the pattern; discriminating test pins the contract. **Forward-looking relevance:** Schwab API integration (queued at `docs/phase3e-todo.md` 2026-05-04 entry) will hit the same surface (web → CLI → broker API). Add to writing-plans phase as adversarial-review watch item: "any cfg override surfaced via web route that consumes a CLI subprocess MUST verify override is loaded in the child process, not assumed-inherited from parent."

Per retention discipline (`docs/orchestrator-context.md` §"Maintenance: retention discipline"): adding this lesson pushes total over 30; migrate the oldest active lesson ("Orchestrator briefs MUST NOT exclude documented skill requirements...") to archive. Do as part of Task 11's docs cleanup commit.

---

## §7 — Done criteria (cite plan §Z)

Plan §Z specifies done criteria. Recap for orchestrator triage clarity:

- All Task 0-11 commits land on worktree branch.
- All `## Tasks` per-task done-criteria pass.
- Fast suite green: `python -m pytest -m "not slow" -q` exits 0 with +53 (or band-acceptable) net new tests vs baseline.
- Slow suite passes when token populated: `python -m pytest -m slow -q tests/integrations/test_finviz_api_live.py` exits 0 OR all tests skip with reason "token unset" (skip is acceptable when operator's token gate is the only blocker).
- Ruff baseline preserved (no NEW violations; no INCIDENTAL fixes).
- `copowers:adversarial-critic` verdict = `NO_NEW_CRITICAL_MAJOR`.
- Marker file `.copowers-subagent-active` removed before adversarial review invocation; absent at end of dispatch.
- Operator-witnessed verification gate (plan §K) passes; operator reports PASS per surface.
- Plan §I cycle-checklist update + §J CLAUDE.md updates landed.
- §6 above lesson captured in `docs/orchestrator-context.md`.

---

## §8 — Operator-witnessed verification gate (cite plan §K)

Plan §K is the binding verification gate. After adversarial-review reaches `NO_NEW_CRITICAL_MAJOR`, surface to operator with the §K checklist. Operator runs each surface manually and reports PASS / FAIL.

**Surfaces (per plan §K — implementer cites verbatim):**

S1 — `swing finviz fetch` from worktree CLI: success path with operator's actual token + screen_query.
S2 — `swing finviz status` from worktree CLI: shows recent calls + rate-limit headroom.
S3 — Pipeline run with `swing pipeline run` from worktree CLI: `_step_finviz_fetch` runs before `_step_evaluate`; CSV emitted to `data/finviz-inbox/`; pipeline completes successfully.
S4 — Manual CSV override: operator drops a CSV in `data/finviz-inbox/` for today's session; pipeline run skips API fetch + processes manual CSV.
S5 — Signature-drift WARNING: operator edits saved-screen on Finviz UI; next pipeline run emits WARNING about signature change.
S6 — Token-leak sentinel sweep: operator greps logs / DB / cassettes for token sentinel; assert no occurrences.
S7 — Cassette replay (no live API): `python -m pytest tests/integrations/test_finviz_api.py` passes without network.
S8 — Slow-suite live integration: `python -m pytest -m slow tests/integrations/test_finviz_api_live.py` passes with operator's token.

(Plan §K may have refined this list; cite the plan, not this brief, as binding.)

If a surface FAILs, operator + implementer + orchestrator triage. Mid-verification fixes land as `code-review I<N>` commits in the worktree before merge.

---

## §9 — Return report format

When done (post operator-witnessed gate PASS), produce return report. Format:

```
# Finviz API Integration — Executing-Plans Dispatch Return Report

**Worktree branch:** finviz-api-integration
**Worktree HEAD:** <SHA>
**BASELINE_SHA:** 734ba6f (writing-plans terminal HEAD)
**Commit chain:** <SHA range; full count>
**Codex rounds:** N → NO_NEW_CRITICAL_MAJOR
**Test count delta:** +<N> fast, +<M> slow
**Ruff baseline:** preserved at <N> (was <N> at baseline)

## Findings disposition (per Codex round)

R1: <count critical>/<major>/<minor>; <one-line summary of fixes landed>
R2: ...

## Plan-task chain summary

<Task list with one-line per task: status (DONE / DEVIATED / OPEN); commit SHA>

## Operator-witnessed gate results (S1-S8)

<Per-surface PASS/FAIL with one-sentence evidence>

## Mid-verification fixes (if any)

<code-review I<N> commits + finding>

## §6 lesson captured

<commit SHA + summary>

## §3 plan deviations (if any)

<Surface any deviation from plan; rationale>

## Open questions for orchestrator

<Anything that needs operator/orchestrator decision before merge>

## Notable observations

<Anything worth capturing for future executing-plans dispatches>

## Merge readiness

READY / BLOCKED <reason>
```

Operator + orchestrator triage; if READY, merge worktree to main + push.

---

## §10 — If you get stuck

- **User-config missing token / screen_query:** halt at brief §2 pre-condition check; surface to operator with the paste-ready user-config snippet (orchestrator can re-provide).
- **Task 0.b live API verification fails (endpoint shape contradicts plan §E):** halt + surface. Do NOT silently re-design. Orchestrator dispatches a follow-up writing-plans iteration if material schema-shape change is required.
- **Cassette recording blocked by Finviz Elite auth requirements:** if API requires multi-step auth flow not anticipated in plan §E, halt at Task 2 + surface.
- **Subagent self-collision (rogue task duplicates):** verify marker file is present at worktree root throughout dispatch. If marker is missing, recreate. If rogue duplicates land despite marker, halt + force-reset + surface (Phase 5 first-attempt incident triage; archived lesson).
- **Subprocess cfg-propagation Task 2.5 implementation surfaces a deeper Phase 5 cfg-load architecture issue:** halt + surface. Plan Task 2.5 binds the contract; if architecture doesn't support it, that's an orchestrator-level decision.
- **Codex round count exceeds 4:** review chain-convergence shape per Phase 7 Sub-B lesson. Convergent (each round catches issue triggered by prior fix) → continue. Thrashing (each round catches unrelated issues) → halt + surface; likely indicates plan-discipline gap that should be addressed via plan-iteration dispatch.
- **Operator-witnessed gate FAIL on a surface:** depends on the failure mode. Halt + triage with operator + orchestrator. Do not merge until gate passes.
- **Editable-install vs worktree path mismatch causing CLI verification failure:** use `$env:PYTHONPATH = "."; python -m swing.cli ...` per binding-conventions.

---

## Final reminders

- The plan is the binding spec. Re-design is anti-pattern.
- Marker file `.copowers-subagent-active` MUST exist from worktree creation through end of all task commits + all internal-review fixes. Remove ONLY before invoking `copowers:adversarial-critic`.
- Operator-witnessed verification gate is BINDING. No skip.
- Token NEVER appears in any log / error / commit / cassette / DB row. Task 10 sentinel audit verifies.
- Plan §K verification surfaces are the canonical list; cite plan, not brief, as binding.
- Test-count projection: +53 fast biased high. Plan does NOT shrink acceptance criteria around the projection.
- Worktree merge to main is `git merge --no-ff` per project convention; preserves the dispatch-chain provenance.
