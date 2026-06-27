# Phase 3e — Chart-Pattern Flag-V1: Phase 4 Execution Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Execute **Phase 4 ONLY** (Task 4.0a Phase 2 carve-out extension + Tasks 4.0 through 4.8) of the chart-pattern flag-v1 implementation plan via `copowers:executing-plans`. Land the date deserialization fix in `_row_to_classification` (prerequisite); land `cfg.web.flag_pattern_display_threshold` config; add `_pattern_tags` helper as sibling to `_flag_tags`; extend `WatchlistVM` + `DashboardVM` + `WatchlistRowVM` with `pattern_tags` / `pattern_tag` parallel fields; load classifications by `pipeline_run_id` in `build_watchlist` + `build_dashboard`; render `flag (0.78)` tag in watchlist tags cell; sort-neutrality regression test (behavioral parity vector) + compounding-confound test. Stop at the Phase 4 checkpoint — do NOT proceed to Phase 5 or beyond.
**Expected duration:** ~1-2 sessions (~9 tasks: Task 4.0a + Tasks 4.0-4.8).
**Output:** Phase 4 commits landed on `main`; fast suite green; watchlist now displays `flag (0.78)` tags for chart-scope tickers with classified flag patterns; `_sort_watchlist` byte-for-byte UNCHANGED (sort-neutrality structurally guaranteed via parallel `pattern_tags` field); adversarial Codex review on the combined Phase 4 diff reaches `NO_NEW_CRITICAL_MAJOR`.

---

## §0 Read first

In this order:

1. **`docs/superpowers/plans/2026-04-26-chart-pattern-flag-v1-plan.md`** — THE plan. Phase 4 is at lines 2364-3117 (Tasks 4.0 through 4.8). Read Phase 4 in full; skim Phases 1-3 (lines 36-2363) for context on the algorithm + persistence + pipeline integration that Phase 4 consumes; do NOT execute later phases.
2. **`docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`** — the source-of-truth design. Phase 4 implements spec §3.5 (watchlist tag rendering — sort-neutrality structural guarantee via parallel `pattern_tags` VM field; `_sort_watchlist` byte-for-byte UNCHANGED).
3. **`docs/orchestrator-context.md`** — project framing, recent decisions (especially the 2026-04-26 Phase 3 triage decisions: Task 4.0a carve-out extension, Phase 4+ observable verification, review-fix commit convention formalization), Binding conventions (commit-message conventions formalized as 3-tier), 6 most-recent lessons captured (especially log-line discriminating-test discipline, single-subagent-doesn't-eliminate-self-collision, brief-task-ID-rule scope).
4. **`CLAUDE.md`** at repo root — gotchas, conventions. **Phase 4 touches `swing/web/`** (VM extensions + `build_watchlist` + `build_dashboard` + `WatchlistRowVM` + template + new `_pattern_tags` helper) AND **`swing/data/repos/pattern_classifications.py`** for Task 4.0a (Phase 2 carve-out extension). Especially relevant gotchas: **base-layout shared VM gotcha** (any new VM field needs adding to ALL base-layout VMs — `DashboardVM`, `PipelineVM`, `JournalVM`, `WatchlistVM`, `PageErrorVM`); HTMX OOB-swap partial drift (use `{% include %}` not hand-duplicated markup); `started_ts DESC` ordering trap.
5. **`docs/phase3e-todo.md`** — particularly the "2026-04-26 chart-pattern flag-v1 Phase 3 → Phase 4 handoff items" section at the bottom for design points and Task 4.0a fix specification.
6. **`docs/phase3e-chart-pattern-phase3-execution-brief.md`** (briefly) — context for the Phase 3 dispatch discipline that Phase 4 inherits + extends.

---

## §0 Skill posture

**INVOKE:**

- `copowers:executing-plans` — wraps `superpowers:subagent-driven-development` with adversarial Codex review on the combined Phase 4 diff after task commits land. Iterates rounds to `NO_NEW_CRITICAL_MAJOR`.

**DO NOT INVOKE:**

- `copowers:writing-plans` / `superpowers:writing-plans` — plan is settled.
- `copowers:brainstorming` / `superpowers:brainstorming` — design is settled.
- `superpowers:executing-plans` directly — use the copowers wrapper for adversarial review per project standing convention.
- `superpowers:using-git-worktrees` — explicitly NOT required for Phase 4 (operator decision 2026-04-26 post-Phase-3: continue brief discipline + ADD observable verification before escalating to worktree isolation; if Phase 4 sees a rogue task duplicate, escalate in Phase 5+).

The execution wrapper drives task-by-task implementation per the plan's TDD discipline, then runs Codex review on the cumulative Phase 4 diff. Fix findings as new commits (no amending).

---

## §1 Scope (Phase 4 ONLY + Task 4.0a Phase 2 carve-out extension)

**EXECUTE these tasks (in plan order; Task 4.0a FIRST as prerequisite):**

- **Task 4.0a** — **Date deserialization fix** in `swing/data/repos/pattern_classifications.py`. Phase 2 carve-out extension; Phase 4 prerequisite. See §2 below for the fix specification.
- **Task 4.0** — `cfg.web.flag_pattern_display_threshold` config field (default 0.0; permissive at V1)
- **Task 4.1** — `_pattern_tags` helper (sibling to `_flag_tags`; lives in `swing/web/view_models/dashboard.py` for now per plan)
- **Task 4.2** — `WatchlistVM` + `DashboardVM` gain `pattern_tags` field; verify ALL base-layout VMs (`DashboardVM`, `PipelineVM`, `JournalVM`, `WatchlistVM`, `PageErrorVM`) per CLAUDE.md gotcha
- **Task 4.3** — `build_watchlist` + `build_dashboard` load classifications by `pipeline_run_id` (Bug-7-family anchor discipline; bind to `pipeline_runs.evaluation_run_id → pipeline_run_id`)
- **Task 4.4** — `WatchlistRowVM` gains `pattern_tag`; `build_watchlist_row` populates it
- **Task 4.5** — Sort-neutrality regression: behavioral parity-vector test
- **Task 4.6** — Compounding-confound test (per 2026-04-26 lesson)
- **Task 4.7** — Template change: render flag tag in tags cell
- **Task 4.8** — Phase 4 checkpoint (validation; fast suite green; ruff clean)

**DO NOT EXECUTE (out of scope; STOP here):**

- Phase 5 (trade-entry form + CLI: TradeEntryFormVM extension, EntryRequest extension, override UI)
- Phase 6 (chart overlay painting: actual `fill_betweenx` / pole-flag bands / algo-pivot segment / title annotation)
- Phase 7 (integration tests + operator-labeled fixtures)
- ANY modification to `swing/data/` BEYOND Task 4.0a (the fix is the only Phase 2 carve-out extension)
- ANY modification to `swing/trades/`, `swing/cli.py`, `swing/pipeline/`, `swing/rendering/`, `swing/evaluation/`

If Phase 4 reveals a problem that requires touching out-of-scope code, STOP and surface to orchestrator under "OPEN QUESTIONS" in the return report.

---

## §2 Task 4.0a specification (Phase 2 carve-out extension)

**Context.** Codex Phase 3 R3 Major 1 surfaced that `_row_to_classification` returns ISO date strings instead of `date` objects despite the `PipelinePatternClassification` dataclass annotation being `date | None`. Phase 3 was scope-locked OUT of `swing/data/` so the fix was deferred to Phase 4 as a Phase 2 carve-out extension. Phase 4 cannot consume the dataclass correctly (template comparisons, downstream type assumptions) without this fix.

**Files (single Phase 2 carve-out extension):**

- Modify: `swing/data/repos/pattern_classifications.py`
- Modify: `tests/data/repos/test_pattern_classifications.py` (or wherever the existing pattern_classifications tests live)

**Fix specification:**

In `_row_to_classification`, parse the four anchor columns from ISO strings to `date` objects when present:

```python
from datetime import date

def _row_to_classification(row) -> PipelinePatternClassification:
    return PipelinePatternClassification(
        # ... other fields ...
        pole_start_date=date.fromisoformat(row["pole_start_date"]) if row["pole_start_date"] is not None else None,
        pole_end_date=date.fromisoformat(row["pole_end_date"]) if row["pole_end_date"] is not None else None,
        flag_start_date=date.fromisoformat(row["flag_start_date"]) if row["flag_start_date"] is not None else None,
        flag_end_date=date.fromisoformat(row["flag_end_date"]) if row["flag_end_date"] is not None else None,
        # ... other fields ...
    )
```

Apply the same parsing in `list_classifications_for_run` if it constructs `PipelinePatternClassification` instances directly (rather than calling `_row_to_classification`). If both functions call `_row_to_classification`, the fix in one place is sufficient.

**Tests:**

- TDD: failing test first asserting `cls.pole_start_date` is a `date` instance (not a string), then implement.
- Discriminating-test discipline: pre-fix returns `str`; post-fix returns `date`. The test `assert isinstance(cls.pole_start_date, date)` distinguishes both paths.
- Compounding-confound: verify the parsing actually happens by removing the `date.fromisoformat(...)` call and confirming the test fails.
- Round-trip test: insert a classification with `date(2026, 4, 26)` for `pole_start_date`; read it back; assert the value equals `date(2026, 4, 26)` (not the string `"2026-04-26"`).
- NULL preservation: insert a classification with `pole_start_date=None`; read it back; assert `cls.pole_start_date is None` (not `date.fromisoformat(None)` raising).

**Commit message:** `fix(data): Task 4.0a — parse anchor dates as date objects in _row_to_classification (Phase 2 carve-out extension; Phase 3 R3 M1)`

This is a one-task fix; Task 4.0a is committed standalone (not bundled with Task 4.0 or any later Phase 4 task) so the carve-out extension is auditable.

---

## §3 Locked constraints + Phase 1 / 2 / 3 handoff items

The spec's six locked constraints (spec §1.1) and the plan's settled design decisions are binding. Phase 4 in particular must respect:

### Sort-neutrality structural guarantee (binding spec §3.5)

- **`_sort_watchlist` MUST be byte-for-byte UNCHANGED.** This is the architectural fix from spec R1 M2. The flag tag does NOT enter the `tags` tuple consumed by `_sort_watchlist`. Sort-neutrality is structurally guaranteed by the parallel `pattern_tags` VM field design.
- **`_pattern_tags` is a SIBLING helper to `_flag_tags`**, NOT an extension of `_flag_tags`. It returns a separate dict keyed by ticker; consumers (templates, VMs) read both helpers' outputs and combine them at render time.
- **`pattern_tags` is a separate VM field**, NOT mixed into the existing `tags` tuple. The sort-input tuple stays frozen at the existing scoring vocabulary (TT✓/VCP✓/A+); the flag tag is parallel render-only data.

### Phase 4 task partitioning + sequential dependencies

Phase 4's tasks have a mix of independent and sequential dependencies:

- **Task 4.0a is independent** (Phase 2 carve-out fix; can be assigned standalone).
- **Task 4.0** (config field) is independent of Task 4.0a; depends on no other Phase 4 task.
- **Task 4.1** (`_pattern_tags` helper) depends on Task 4.0a (consumes `PipelinePatternClassification.pole_start_date` etc.) and Task 4.0 (consumes `cfg.web.flag_pattern_display_threshold`).
- **Task 4.2** (VM extensions) depends on Task 4.1's helper (consumes its output).
- **Task 4.3** (build_watchlist + build_dashboard load classifications) depends on Task 4.0a (date parsing) and Task 4.2 (VM has the field to populate).
- **Task 4.4** (WatchlistRowVM) depends on Task 4.2 (mirrors the field structure).
- **Task 4.5** (sort-neutrality regression) is independent of other Phase 4 tasks once Task 4.1 + Task 4.2 land (asserts `_sort_watchlist` is unchanged).
- **Task 4.6** (compounding-confound test) depends on Task 4.3 (uses `build_watchlist` E2E).
- **Task 4.7** (template change) depends on Task 4.4 (consumes `WatchlistRowVM.pattern_tag`).
- **Task 4.8** (checkpoint) depends on all prior.

**Recommended partitioning** (per §4 below):
- ONE subagent handles Task 4.0a → Task 4.0 → Task 4.1 → Task 4.2 → Task 4.3 → Task 4.4 → Task 4.5 → Task 4.6 → Task 4.7 → Task 4.8 sequentially.
- Alternatively, two subagents: Agent A handles Task 4.0a + Task 4.0 + Task 4.1 (foundation); Agent B waits for A's commits, then handles Tasks 4.2 → 4.8 (consumers).
- NO subagent should be assigned overlapping tasks. NO two subagents should claim the same task.

### Bug-7-family anchor discipline

- `build_watchlist` + `build_dashboard` MUST bind classification reads to `pipeline_runs.evaluation_run_id → pipeline_run_id`. Use the existing `latest_evaluation_run_id` helper (or extract one if it doesn't exist as such).
- DO NOT read "latest classification by computed_at" as a fallback — that re-introduces mixed-anchor risk.
- Adversarial review will catch any `MAX(run_ts)` patterns; pre-empt by using the canonical helper.

### Base-layout shared VM gotcha (CLAUDE.md)

Any new VM field MUST be added to ALL base-layout VMs:
- `DashboardVM` (Phase 4 adds `pattern_tags`)
- `PipelineVM`
- `JournalVM`
- `WatchlistVM` (Phase 4 adds `pattern_tags`)
- `PageErrorVM`

Add the field with a safe default (e.g., `pattern_tags: dict[str, str] = field(default_factory=dict)` or appropriate type) to VMs that don't naturally have classifications; the template gracefully renders nothing when the field is empty.

### Phase 1 → Phase 4 handoff items

- **Pure-function discipline verified for Phase 1.** `classify_flag(bars)` does NOT mutate the input DataFrame; Phase 4's reads from cache are pure data access.

### Phase 2 → Phase 4 handoff items

- **Repo-layer cross-column invariant** on `trades` is in place from Phase 2 (`insert_trade_with_event` raises `ValueError` for invalid combinations); Phase 4 doesn't touch this.
- **`_serialize_components`** at persistence boundary handles NaN sanitization; Phase 4 reads from cache (no NaN concerns; serialization happens at write time).
- **Cache table key** is `(pipeline_run_id, ticker)`; Phase 4's reads use this composite key.

### Phase 3 → Phase 4 handoff items

- **`_step_charts` per-ticker fenced_write** persists classification rows per pipeline run for chart-scope tickers; Phase 4 reads them.
- **End-of-step summary log line** `flag_classifier: {success}/{attempts} ok, {errors} errors` is the operator-facing visibility surface; Phase 4 doesn't add a UI surface for classifier-error count (V2 deferred per spec §3.3).
- **`PatternOverlay.from_classification(r)`** filtering rule: returns None when `not r.detected or r.pattern != 'flag'`. Phase 4 may need similar filtering logic when computing display tags (only render `flag (0.78)` tag when `pattern == 'flag'` AND confidence >= threshold).

If anything in Phase 4 conflicts with the spec or the locked constraints, STOP and surface to orchestrator. Do NOT redesign.

---

## §4 Subagent task partitioning + observable verification (BINDING — operator decisions 2026-04-26)

**Background.** Phase 2 surfaced subagent-driven-development self-collision (~30% noise). Phase 3 added disjoint-task-partitioning brief discipline; reduced noise to ~20% but produced one rogue task duplicate (`b080da9` + revert `132142c`). Operator decisions (2026-04-26 post-Phase-3): continue brief discipline; ADD observable verification; escalate to worktree isolation in Phase 5+ if Phase 4 also produces a rogue.

### Required partitioning rules (same as Phase 3 §3)

1. **Each task assigned to exactly one subagent.** Multiple tasks per subagent allowed; task sets across agents MUST be DISJOINT. No task is assigned to more than one subagent.
2. **Pre-task verification.** Before starting any task's implementation, the assigned subagent MUST verify the task's deliverable does NOT already exist (e.g., grep for the function/class/import; read the relevant file to check current state). If the deliverable exists OR is partially started, abort and report ("Task N.M deliverable X already exists at Y; aborting per partitioning discipline; surface to orchestrator-thread").
3. **Sequential dependencies (Phase 4 specifically).** See §3 above for the dependency map. Recommended partitioning: ONE subagent handles all Phase 4 tasks sequentially.
4. **Commit message conventions** (formalized 2026-04-26 in orchestrator-context "Binding conventions"):
   - **Task implementation commits** MUST include task ID: `feat(area): Task X.Y — <description>`.
   - **Adversarial review-fix commits** SHOULD include round + finding ID: `fix(area): Codex R1 Major 2 — <description>`.
   - **Format-only cleanup commits** (ruff, comment, whitespace) no task ID needed: `style(area): ruff UP037 cleanup`.

### NEW for Phase 4 — Observable verification (operator decision 2026-04-26)

5. **Subagent MUST include `git log --grep="Task X.Y" --oneline` output in the commit body BEFORE each task implementation commit.** If the grep returns ANY existing commits with the same task ID, the subagent MUST NOT commit that task (abort and report). Codex review will check the commit body for this evidence; absence is a finding.

   Example commit body format:
   ```
   Task 4.1 — _pattern_tags helper (sibling to _flag_tags)

   Pre-commit verification:
   $ git log --grep="Task 4.1" --oneline
   (no output — Task 4.1 not yet implemented)

   <rest of commit message>
   ```

   If the grep DOES return existing commits, the subagent's commit body documents the abort:
   ```
   Pre-commit verification:
   $ git log --grep="Task 4.1" --oneline
   abc1234 feat(web): Task 4.1 — _pattern_tags helper (sibling to _flag_tags)

   ABORTING: Task 4.1 already implemented in abc1234. Surfacing to orchestrator.
   ```

   This makes duplicate-detection observable to Codex review and to the human operator post-execution. The principle: rules without observable verification fail silently (Phase 3's pre-commit existence check was in §3 rule 5 but produced no audit trail; Phase 4 rules require observable evidence).

### Watch items for adversarial review

The Codex review wrapper should treat ANY of the following as a finding:

- **Duplicate task implementations** (two commits with overlapping task IDs OR redundant content for the same plan task).
- **Missing pre-task verification evidence in commit body** per rule 5 above. If a task implementation commit doesn't have the grep output in its body, that's a finding even if no duplicate exists.
- **Mixed-task commits** (a single commit implementing two non-trivially-related tasks).
- **Scratch directory pollution.** Pytest scratch directories left in repo root after task completion. Use `pytest --basetemp=<gitignored-relative-dir>` AND clean up explicitly. (Note: Windows ACL may block cleanup; document any blocked dirs in the return report so orchestrator-side privileged cleanup can address them in batch.)
- **Sort-neutrality violation.** ANY modification to `_sort_watchlist`, `_tag_precedence_score`, `_TAG_PRECEDENCE`, or the existing `_flag_tags` consumer logic. Phase 4's `_pattern_tags` is a SIBLING; existing sort logic stays frozen.

If Phase 4 collision recurs DESPITE these rules, document the failure mode in the return report under "LESSONS WORTH CAPTURING" and the orchestrator will escalate to worktree isolation in Phase 5+.

---

## §5 Conventions

- **Branch:** `main`. No feature branches.
- **TDD discipline (rigid):** failing test → run to see RED → minimal implementation → run to see GREEN → commit. One red-green cycle per logical change. Per-task commit boundaries per the plan. Phase 4's tasks are integration-style (VMs, build functions, helpers, templates) — strict per-task TDD applies cleanly.
- **Commit-message conventions** (formalized 2026-04-26): see §4 rule 4 above.
- **Discriminating-test discipline:** every test must produce a different outcome under post-fix code than under pre-fix code (per `feedback_regression_test_arithmetic` memory and the 2026-04-26 lessons). Especially relevant: **log-line and format assertions must use exact-equality, NOT substring matching** (per the discipline extension added 2026-04-26). When verifying VM field shape, JSON-key presence, or rendered template output, use exact-equality assertions.
- **Compounding-confound discipline (per 2026-04-26 lesson):** for any test asserting on a primary key behavior, also include a "delete the keyed-on element and confirm the test now fails differently" check.
- **Tests:** `python -m pytest -m "not slow" -q` MUST be green at the Phase 4 checkpoint. Plan does NOT require it green between every task, but Task 4.8 checkpoint is mandatory. Baseline at start of Phase 4: 1059 fast tests.
- **Ruff:** baseline 81 errors per CLAUDE.md. Phase 4 must NOT introduce new violations in `swing/web/` or `swing/data/` (Task 4.0a touches the latter). Run `ruff check swing/web/ swing/data/` after Task 4.7 and before Task 4.8 commit.
- **Phase 4 scope boundary:** every modified file MUST be in `swing/web/`, `swing/data/repos/pattern_classifications.py` (Task 4.0a only), `swing/config.py` (Task 4.0 only), OR `tests/web/`, `tests/data/`. If you find yourself touching `swing/trades/`, `swing/cli.py`, `swing/pipeline/`, `swing/rendering/`, `swing/evaluation/`, OR any other `swing/data/` file, STOP — it's out of scope.
- **Scratch directory hygiene.** Use `pytest --basetemp=<gitignored-relative-dir>` to direct scratch to a project-gitignored location. Clean up after each task's test cycle. Document any Windows-ACL-blocked dirs in return report.

---

## §6 Adversarial review (handled by copowers wrapper)

The `copowers:executing-plans` wrapper invokes Codex MCP review on the combined Phase 4 diff after Task 4.8 lands. Pass these specific watch items:

- **Spec fidelity.** Phase 4 implements spec §3.5 verbatim — `_pattern_tags` SIBLING to `_flag_tags`; `pattern_tags` parallel VM field; `_sort_watchlist` byte-for-byte UNCHANGED; flag tag rendered as `flag (0.78)` (or whatever format the spec specifies; verify against spec §3.5 + §3.7 display threshold semantics).
- **Plan fidelity.** Tasks executed in plan order (Task 4.0a FIRST as prerequisite); no skipped tasks; no tasks added beyond the plan + Task 4.0a; commit messages follow §4 rule 4 conventions.
- **Sort-neutrality structural guarantee.** Verify `_sort_watchlist` source code is byte-for-byte unchanged between baseline and Phase 4 HEAD. Behavioral parity-vector test (Task 4.5) catches behavioral drift; source-byte check catches structural drift.
- **Observable verification (per §4 rule 5).** Each task implementation commit body contains `git log --grep="Task X.Y" --oneline` output. Absence is a finding.
- **Base-layout VM coverage.** All 5 base-layout VMs (`DashboardVM`, `PipelineVM`, `JournalVM`, `WatchlistVM`, `PageErrorVM`) have the new `pattern_tags` field with safe default. Missing from any → 500 error on the corresponding page.
- **Bug-7-family anchor discipline.** `build_watchlist` + `build_dashboard` bind classification reads to `pipeline_runs.evaluation_run_id → pipeline_run_id`. NO `MAX(run_ts)` patterns; NO "latest by computed_at" fallback.
- **TDD integrity.** Each implementation commit has a preceding failing-test commit. No "implement first, test after."
- **Discriminating tests.** Per `feedback_regression_test_arithmetic` (extended 2026-04-26 to log-line / format assertions): every test must produce different outcomes pre-fix vs post-fix. Vacuous tests are findings. Especially: VM field shape assertions, template rendering assertions — use exact-equality, not substring matching.
- **Compounding-confound on sort-neutrality** (Task 4.6): if you delete the `_pattern_tags` call from `build_watchlist`, the test should still pass — that's the proof of sort-neutrality. If the test FAILS when `_pattern_tags` is removed, then the sort logic IS coupled to pattern tags and the structural guarantee is violated.
- **HTMX OOB-swap partial drift.** Any new template fragment for the flag tag MUST use `{% include %}` not hand-duplicated markup.
- **Out-of-scope creep.** No modification to `swing/trades/`, `swing/cli.py`, `swing/pipeline/`, `swing/rendering/`, `swing/evaluation/`, or any `swing/data/` file other than `pattern_classifications.py` (Task 4.0a).
- **Task 4.0a fix completeness.** All 4 anchor columns (`pole_start_date`, `pole_end_date`, `flag_start_date`, `flag_end_date`) parsed; NULL preserved correctly (no `date.fromisoformat(None)` raise); round-trip test verifies.

---

## §7 Done criteria

Phase 4 execution is done when ALL of the following hold:

- [ ] Task 4.0a + all Phase 4 tasks (4.0 through 4.8) have landed commits on `main`.
- [ ] Each task implementation commit message follows §4 rule 4 conventions; commit body contains §4 rule 5 observable verification evidence.
- [ ] No duplicate task implementations; no mixed-task commits.
- [ ] `python -m pytest -m "not slow" -q` green (full fast suite); baseline + new tests on Task 4.0a date parsing + `_pattern_tags` helper + VM extensions + sort-neutrality regression + compounding-confound + template rendering.
- [ ] `ruff check swing/web/ swing/data/` clean (no new violations).
- [ ] `_sort_watchlist` source code is byte-for-byte UNCHANGED between baseline and HEAD.
- [ ] All 5 base-layout VMs (`DashboardVM`, `PipelineVM`, `JournalVM`, `WatchlistVM`, `PageErrorVM`) have the `pattern_tags` field with safe default.
- [ ] Watchlist renders `flag (0.78)`-style tags for chart-scope tickers with classified flag patterns (operator-visible UI change; manual verification or integration test).
- [ ] No scratch pytest directories left in repo root (or any blocked dirs documented for orchestrator-side cleanup).
- [ ] Adversarial Codex review on combined Phase 4 diff reaches `NO_NEW_CRITICAL_MAJOR`.
- [ ] Phase 4 implementation does NOT touch `swing/trades/`, `swing/cli.py`, `swing/pipeline/`, `swing/rendering/`, `swing/evaluation/`, OR any `swing/data/` file other than `pattern_classifications.py` (Task 4.0a).

---

## §8 Return report format

Final message to orchestrator (via operator) MUST include:

```
PHASE: 4 (Watchlist + dashboard read paths) of chart-pattern flag-v1 plan
COMMIT CHAIN: <first SHA>..<last SHA> (N commits)
FAST SUITE: 1059 → <new count> tests (Δ +<count>)
ADVERSARIAL ROUNDS: <N>; FINAL VERDICT: NO_NEW_CRITICAL_MAJOR

TASKS COMPLETED:
- Task 4.0a — Date deserialization fix (Phase 2 carve-out extension), commit SHA
- Task 4.0 — cfg.web.flag_pattern_display_threshold config, commit SHA
- Task 4.1 — _pattern_tags helper, commit SHA
- Task 4.2 — VM extensions (5 base-layout VMs), commit SHA
- Task 4.3 — build_watchlist + build_dashboard load classifications, commit SHA
- Task 4.4 — WatchlistRowVM gains pattern_tag, commit SHA
- Task 4.5 — Sort-neutrality regression test, commit SHA
- Task 4.6 — Compounding-confound test, commit SHA
- Task 4.7 — Template change: render flag tag, commit SHA
- Task 4.8 — Phase 4 checkpoint, commit SHA

PARTITIONING DISCIPLINE OUTCOME:
- Subagent count: <N>
- Task assignments: <list which tasks went to which subagent>
- Collisions detected: <none / list any with details>
- Pre-task deliverable-existence checks: <how many fired; how many aborted>
- Observable verification (per §4 rule 5): <how many task commits included grep output; sample>
- Scratch directories: <cleaned / list any remaining + ACL state>

WATCHLIST + DASHBOARD INTEGRATION SUMMARY:
- _pattern_tags helper: <signature + lookup pattern>
- VM extensions: <which VMs got the field; default value>
- build_watchlist anchor: <pipeline_runs.evaluation_run_id → pipeline_run_id>
- Sort-neutrality verification: <byte-for-byte source check + behavioral parity vector + compounding-confound>
- Template flag tag: <rendered format; sample HTML>
- Operator-visible UI change: <screenshot or prose description>

ADVERSARIAL FINDINGS (each with disposition):
- <finding>: FIXED in commit <SHA> / ACCEPTED with rationale: <text>

OPEN QUESTIONS FOR ORCHESTRATOR:
- <any plan/spec contradiction surfaced; otherwise "None">

LESSONS WORTH CAPTURING (process insights from execution):
- <bullet list, including any partitioning-discipline observations>

PHASE 4 → PHASE 5 HANDOFF NOTES:
- <anything Phase 5 implementer needs to know that isn't in the plan>
```

---

## §9 If you get stuck

- **Plan/spec contradictions.** Surface in return report under "OPEN QUESTIONS." Do NOT amend the plan or spec; do NOT re-design.
- **TDD ordering uncertainty.** Failing-test-first. Phase 4's tasks are integration-style — strict per-task TDD applies cleanly.
- **Codex finding contradicts plan.** Apply receiving-code-review discipline. If finding correct AND plan wrong, surface to orchestrator. If finding wrong, document why with rationale.
- **Out-of-scope pull.** If a Phase 4 task seems to require touching out-of-scope code (Phase 5-7 territory or `swing/data/` beyond Task 4.0a), STOP. Surface as "OPEN QUESTIONS." Do NOT silently expand scope.
- **Subagent collision detected mid-execution.** STOP, surface to orchestrator immediately. Document the collision details (task ID, subagent IDs, commit SHAs, redundancy nature, pre-commit grep output that should have caught it). Per §4: if Phase 4 collides despite the partitioning + observable verification, the orchestrator will escalate to worktree isolation in Phase 5+.
- **Sort-neutrality concern.** If a task seems to require modifying `_sort_watchlist` or the existing `tags` tuple shape, STOP. Sort-neutrality is structurally guaranteed by the parallel `pattern_tags` field design; any modification to the existing sort surface contradicts the spec.
- **Base-layout VM update missing one.** If Jinja errors with `UndefinedError` on a non-watchlist page (pipeline, journal, page-error), it's because the VM for that page doesn't have the new field. Add it with safe default. CLAUDE.md gotcha is binding.

---

## §10 Anti-patterns specific to this execution

- **Scope creep into Phase 5 / Phase 6 / Phase 7.** The classification rows are now consumed by watchlist read at end of Phase 4. Trade-entry form (Phase 5), chart overlay painting (Phase 6), and integration tests (Phase 7) are NOT Phase 4 scope. Adding even small "while I'm here" wiring is out of scope.
- **Touching `_sort_watchlist`.** Sort-neutrality is structurally guaranteed via `_pattern_tags` SIBLING design. ANY modification to `_sort_watchlist`, `_tag_precedence_score`, `_TAG_PRECEDENCE`, or the `tags` tuple shape contradicts the spec and the architectural fix from spec R1 M2.
- **Skipping Task 4.0a.** Phase 4 prerequisite. If Task 4.0a doesn't land first, Phase 4's downstream tasks consume `cls.pole_start_date` as a string; type comparisons fail at runtime; tests that check `isinstance(..., date)` will fail.
- **Bundling Task 4.0a with Task 4.0 or other Phase 4 tasks in one commit.** Phase 2 carve-out extension MUST be auditable as a standalone commit per §2.
- **Touching `swing/data/` beyond `pattern_classifications.py`.** Task 4.0a is the SINGLE Phase 2 carve-out extension authorized for Phase 4. Any other `swing/data/` modification is out of scope.
- **Missing observable verification (per §4 rule 5).** EVERY task implementation commit body MUST contain the `git log --grep` output. Codex will flag missing evidence.
- **Substring-match assertions.** Per the 2026-04-26 lesson extension to discriminating-test discipline, log-line / format assertions use exact-equality. Substring matching almost never distinguishes pre-fix from post-fix.
- **Mixed-anchor mistakes.** Bind to `pipeline_runs.evaluation_run_id → pipeline_run_id`. Bug-7 family.
- **Hand-duplicated template markup.** New flag-tag rendering uses `{% include %}` for OOB-swap-safe partials.
- **Scratch directory pollution.** Use `pytest --basetemp=<gitignored-relative-dir>` AND clean up. Document any Windows-ACL-blocked dirs.
