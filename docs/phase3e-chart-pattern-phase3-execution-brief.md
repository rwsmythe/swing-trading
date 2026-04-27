# Phase 3e — Chart-Pattern Flag-V1: Phase 3 Execution Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Execute **Phase 3 ONLY** (Tasks 3.1 through 3.4) of the chart-pattern flag-v1 implementation plan via `copowers:executing-plans`. Wire `_step_charts` to call `classify_flag` per ticker and persist the classification row in the same `lease.fenced_write()` block as the chart_target update; handle classifier exceptions per spec §3.3; add `pattern_overlay` kwarg to `render_chart` as a no-op stub (actual painting is Phase 6). Stop at the Phase 3 checkpoint — do NOT proceed to Phase 4 or beyond.
**Expected duration:** ~1 session (~4 tasks).
**Output:** Phase 3 commits landed on `main`; fast suite green; classifier rows persist per pipeline run for chart-scope tickers; classifier-exception path persists `pattern=NULL` rows per spec §3.3 contract; adversarial Codex review on the combined Phase 3 diff reaches `NO_NEW_CRITICAL_MAJOR`.

---

## §0 Read first

In this order:

1. **`docs/superpowers/plans/2026-04-26-chart-pattern-flag-v1-plan.md`** — THE plan. Phase 3 is at lines 1901-2363 (Tasks 3.1 through 3.4). Read Phase 3 in full; skim Phases 1-2 (lines 36-1900) for context on the algorithm and persistence layer that Phase 3 wires together; do NOT execute later phases.
2. **`docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`** — the source-of-truth design. Phase 3 implements spec §3.3 (pipeline integration). Especially binding: spec §3.3 lines 396-401 prescribe that classifier-error rows MUST be constructed with `components={"error": repr(exc)}` — Phase 3's `_step_charts` exception handler is the SOLE owner of this contract (the repo does NOT enforce it; Codex R1 Minor 1 ACCEPTED rationale per Phase 2 retro).
3. **`docs/orchestrator-context.md`** — project framing, lessons captured (especially the 2026-04-26 lesson on subagent-driven-development self-collision and the disjoint-task-partitioning mitigation; the discriminating-test discipline; the audit-anchors-must-be-persisted lesson; the Bug-7-mixed-anchor family lesson). Phase 3 dispatch discipline is binding (see §3 below).
4. **`CLAUDE.md`** at repo root — gotchas, conventions. **Phase 3 touches `swing/pipeline/runner.py` and `swing/rendering/charts.py` — these are NOT Phase 2 carve-outs; they are Phase 3 territory by default per CLAUDE.md.** Phase 3 does NOT touch `swing/data/`, `swing/web/`, `swing/trades/`, or `swing/cli.py` (those are Phases 4-5 territory). Especially relevant gotchas: yfinance API regression patterns, OhlcvCache breaker semantics, `fenced_write` lease discipline, mid-run `started_ts DESC` ordering trap.
5. **`docs/phase3e-todo.md`** — particularly the "2026-04-26 chart-pattern flag-v1 Phase 2 → Phase 3 handoff items" section at the bottom for design points and constraints surfaced from Phase 2.
6. **`docs/phase3e-chart-pattern-phase1-execution-brief.md`** (briefly) — context for the Phase 1 algorithm ground state (the Phase 2 brief was lost; the Phase 1 brief preserves the project conventions that Phase 2 inherited).

---

## §0 Skill posture

**INVOKE:**

- `copowers:executing-plans` — wraps `superpowers:subagent-driven-development` with adversarial Codex review on the combined Phase 3 diff after task commits land. Iterates rounds to `NO_NEW_CRITICAL_MAJOR`.

**DO NOT INVOKE:**

- `copowers:writing-plans` / `superpowers:writing-plans` — plan is settled.
- `copowers:brainstorming` / `superpowers:brainstorming` — design is settled.
- `superpowers:executing-plans` directly — use the copowers wrapper for adversarial review per project standing convention.
- `superpowers:using-git-worktrees` — explicitly NOT required for Phase 3 (operator decision 2026-04-26: try disjoint-task-partitioning brief discipline first; worktree isolation is the fallback if collision recurs in Phase 3+).

The execution wrapper drives task-by-task implementation per the plan's TDD discipline, then runs Codex review on the cumulative Phase 3 diff. Fix findings as new commits (no amending).

---

## §1 Scope (Phase 3 ONLY)

**EXECUTE these tasks (in plan order; sequential dependencies — see §3 below):**

- **Task 3.1** — `render_chart` gains `pattern_overlay` kwarg + `PatternOverlay` dataclass (API surface only; no painting; Phase 6 implements actual overlay rendering)
- **Task 3.2** — `_step_charts` calls `classify_flag` + persists row in same `fenced_write` (depends on Task 3.1's API surface for the `pattern_overlay` kwarg in `render_chart` calls; depends on the existing Phase 2 `insert_classification` repo function)
- **Task 3.3** — Classifier exception → log + persist `pattern=NULL`; chart proceeds without overlay (depends on Task 3.2's call structure)
- **Task 3.4** — Phase 3 checkpoint (validation; fast suite green; ruff clean)

**DO NOT EXECUTE (out of scope; STOP here):**

- Phase 4 (watchlist / dashboard read paths: VM extension, sort-neutrality regression test, template flag-tag rendering)
- Phase 5 (trade-entry form + CLI: TradeEntryFormVM extension, EntryRequest extension, override UI)
- Phase 6 (chart overlay painting: the actual `fill_betweenx` / pole-flag bands / algo-pivot segment / title annotation — Phase 3 only adds the kwarg as a no-op stub)
- Phase 7 (integration tests + operator-labeled fixtures)
- ANY modification to `swing/data/`, `swing/web/`, `swing/trades/`, `swing/cli.py`
- ANY modification to `swing/evaluation/patterns/` beyond what's needed to consume the existing `classify_flag` function (Phase 1 + Phase 2 already established the algorithm + persistence; Phase 3 wires them)

If Phase 3 reveals a problem that requires touching out-of-scope code, STOP and surface to orchestrator under "OPEN QUESTIONS" in the return report.

---

## §2 Locked constraints + Phase 1 / Phase 2 handoff items

The spec's six locked constraints (spec §1.1) and the plan's settled design decisions are binding. Phase 3 in particular must respect:

### Pipeline integration discipline (spec §3.3)

- **`_step_charts` per-ticker loop** calls `classify_flag(ohlcv.tail(60))` for each chart-scope ticker. The OHLCV is already in hand (chart-step-scoped fetch) — no new yfinance pull.
- **Same fenced_write transaction.** The `insert_classification(conn, pipeline_run_id=run.id, ticker=t, result=classification, computed_at=...)` call MUST happen INSIDE the same `lease.fenced_write()` block as the chart_target update for that ticker. Atomicity matters: either both the chart and the classification row land, or neither does.
- **Classifier exception handler (spec §3.3 sole-owner contract).** When `classify_flag` raises, the handler:
  - Logs `logger.warning` per-ticker including the exception repr.
  - Constructs a `FlagClassificationResult(pattern=None, ...)` synthesized result for persistence.
  - Persists the row with `components_json` containing `{"error": repr(exc), ...}` (the `"error"` key is the spec §3.3 contract).
  - Allows the chart step to continue WITHOUT overlay (chart still renders; just no pattern overlay).
- **End-of-step error count summary log line.** After the per-ticker loop completes, log a summary line: `"Pipeline N: X classifier errors out of Y chart-scope tickers"`. This is the operational visibility surface for Phase 3 (dashboard banner is V2 per spec).

### `render_chart` kwarg (Task 3.1) — API surface only

- Signature change: `render_chart(..., pattern_overlay: PatternOverlay | None = None)`.
- `PatternOverlay` dataclass: per spec §3.4, fields include pole/flag boundary indices, pivot, label, confidence. The dataclass is defined and the kwarg is wired through the call signature, but Phase 3 does NOT paint the overlay — the kwarg is a no-op stub.
- Existing `pivot` hline (candidate-pivot) is preserved; the algo-pivot painting is Phase 6.
- All existing `render_chart` callers must continue to work (default `pattern_overlay=None` — backwards compatible).

### Phase 1 → Phase 3 handoff items

- **Pure-function discipline verified for Phase 1.** `classify_flag(bars)` does NOT mutate the input DataFrame. Phase 3 can safely reuse the same `bars` object for both `render_chart` and `classify_flag` without copy-on-write concerns.
- **(M=5, N=5) literal fallback in `flag_classifier.py`** is unreachable under MIN_BARS=36. Documented inline. Phase 3 does NOT need to design around the (5,5) case.
- **Performance budget (deferred to Phase 5).** Classifier hot loop measured ~44-49ms per call on 250-bar DataFrame, ~700ms for a 15-ticker batch in Phase 1 review. Phase 3 should NOT optimize this loop; Phase 5 measures end-to-end pipeline overhead and tunes if total >1.5s.

### Phase 2 → Phase 3 handoff items

- **`_serialize_components` handles NaN sanitization at the persistence boundary** (Phase 2 commit `115c96b`). Phase 3 can pass any `FlagClassificationResult.components` dict (including those from `_enrich_components` with NaN SMAs) without pre-processing.
- **Repo's `insert_classification` does NOT enforce the `"error"` key contract** for `pattern=NULL` rows. Phase 3's `_step_charts` exception handler is the SOLE owner of this invariant (spec §3.3 + Codex R1 Minor 1 ACCEPTED rationale: V1 trust model).
- **Cross-table FK reference: `pipeline_pattern_classifications.pipeline_run_id REFERENCES pipeline_runs(id)`.** PRAGMA foreign_keys=ON is the project default. Phase 3 must `insert_classification` AFTER the `pipeline_runs` row exists (typically after `lease.fenced_write()` opens — `run.id` should be set by then). Verify this ordering in tests.

If anything in Phase 3 conflicts with the spec or the locked constraints, STOP and surface to orchestrator. Do NOT redesign.

---

## §3 Subagent task partitioning discipline (BINDING — operator decision 2026-04-26)

**Background.** Phase 2 execution surfaced internal subagent collision: `subagent-driven-development` parallel subagents picked up the same task (Tasks 2.4, 2.5, 2.7) and produced redundant commits requiring cleanup (~30% of the 16-commit chain was cleanup overhead). See orchestrator-context "Lessons captured" entry on `copowers:executing-plans` self-collision.

**Phase 3 dispatch discipline (operator decision 2026-04-26): try task-partitioning at the brief level FIRST as a cheaper mitigation than worktree isolation. If collision recurs in Phase 3, escalate to worktree isolation in Phase 4+.**

### Required partitioning rules

1. **Each task assigned to exactly one subagent.** Multiple tasks per subagent are allowed; task sets across agents MUST be DISJOINT. No task is assigned to more than one subagent.
2. **Pre-task verification.** Before starting any task's implementation:
   - The assigned subagent MUST verify the task's deliverable does NOT already exist (e.g., grep for the function/class/import; read the relevant file to check current state).
   - If the deliverable exists OR is partially started, the subagent MUST abort and report ("Task N.M deliverable X already exists at Y; aborting per partitioning discipline; surface to orchestrator-thread").
   - Do NOT duplicate-implement. Do NOT "improve" an existing implementation. Do NOT re-do work.
3. **Sequential dependencies (Phase 3 specifically).** Phase 3's tasks have natural sequential dependencies:
   - Task 3.1 (`render_chart` kwarg) is independent (can start first).
   - Task 3.2 (`_step_charts` calls classifier) depends on Task 3.1's `render_chart` API surface — assign to a subagent that can wait for 3.1's commit OR sequence them in the same subagent.
   - Task 3.3 (exception path) depends on Task 3.2's call structure — same subagent or sequenced after 3.2's commit.
   - Task 3.4 (checkpoint) depends on all prior tasks landing.
   - **Recommended partitioning:** ONE subagent handles Tasks 3.1 → 3.2 → 3.3 → 3.4 sequentially (no parallelization needed for 4 sequential tasks). Alternatively, split into two subagents: Agent A handles 3.1 (independent); Agent B waits for A's commit, then handles 3.2 → 3.3 → 3.4. NO subagent should be assigned 3.1 + 3.2 simultaneously.
4. **Commit signature discipline.** Conventional-commit message MUST include the task ID (e.g., `feat(pipeline): Task 3.2 — _step_charts calls classify_flag and persists classification row`). This makes redundant-commit detection trivial in code review.
5. **Pre-commit existence check.** Before `git commit`, the subagent verifies `git log --oneline -10` does NOT contain a commit message with the same task ID and same primary deliverable. If a duplicate task-ID commit is found, the subagent MUST NOT commit; instead, abort and report.

### Watch items for adversarial review

The Codex review wrapper should treat ANY of the following as a finding:

- **Duplicate task implementations** (two commits with overlapping task IDs OR redundant content for the same plan task).
- **Missing pre-task verification.** Any commit body that doesn't acknowledge the deliverable-existence check OR any task whose implementation didn't include a "Step 0: verify deliverable doesn't exist" check.
- **Mixed-task commits** (a single commit implementing two non-trivially-related tasks). Indicates partitioning discipline failure even if the work is correct.
- **Scratch directory pollution.** Any pytest scratch directories left in repo root after task completion (`.tmp_*/`, `task*_pytest_*/`, etc.). Subagents should clean their scratch dirs before reporting completion.

If Phase 3 collision recurs DESPITE these rules, document the failure mode in the return report under "LESSONS WORTH CAPTURING" and the orchestrator will escalate to worktree isolation in Phase 4+.

---

## §4 Conventions

- **Branch:** `main`. No feature branches.
- **TDD discipline (rigid):** failing test → run to see RED → minimal implementation → run to see GREEN → commit. One red-green cycle per logical change. Per-task commit boundaries per the plan. Phase 3's tasks are integration-style (not tightly-coupled measurement code like Phase 1) — strict per-task TDD applies cleanly.
- **Commits:** Conventional Commits (`feat(pipeline):`, `feat(rendering):`, `test(pipeline):`, etc.). **No Claude co-author footer. No `--no-verify`. No amending — every fix is a NEW commit.** Commit messages MUST include the task ID per §3 rule 4.
- **Discriminating-test discipline:** every test must produce a different outcome under post-fix code than under pre-fix code (per `feedback_regression_test_arithmetic` memory and the 2026-04-26 lessons). For pipeline integration tests: assert specific persistence behavior (cache row exists with expected fields; FK reference is valid; both chart_target and classification land atomically OR neither does).
- **Compounding-confound discipline (per 2026-04-26 lesson):** for any test asserting on a primary key behavior, also include a "delete the keyed-on element and confirm the test now fails differently" check. Especially relevant for the spec §3.3 classifier-error contract: deleting the `"error"` key construction should fail the test verifying the contract.
- **Tests:** `python -m pytest -m "not slow" -q` MUST be green at the Phase 3 checkpoint. Plan does NOT require it green between every task, but Task 3.4 checkpoint is mandatory. Baseline at start of Phase 3: 1052 fast tests.
- **Ruff:** baseline 81 errors per CLAUDE.md. Phase 3 must NOT introduce new violations in `swing/pipeline/` or `swing/rendering/`. Run `ruff check swing/pipeline/ swing/rendering/` after Task 3.3 and before Task 3.4 commit.
- **Phase 3 scope boundary:** every modified file MUST be in `swing/pipeline/`, `swing/rendering/`, OR `tests/pipeline/`, `tests/rendering/`. If you find yourself touching `swing/data/`, `swing/web/`, `swing/trades/`, `swing/evaluation/`, or `swing/cli.py`, STOP — it's out of scope.
- **Scratch directory hygiene.** Pytest scratch directories (the `.tmp_*/`, `task*_pytest_*/` artifacts from Phase 2) MUST be cleaned from repo root after any test runs. Use `pytest --basetemp` to direct scratch to a project-gitignored location, OR explicitly `rm -rf` after the task's test cycle.

---

## §5 Adversarial review (handled by copowers wrapper)

The `copowers:executing-plans` wrapper invokes Codex MCP review on the combined Phase 3 diff after Task 3.4 lands. Pass these specific watch items:

- **Spec fidelity.** Phase 3 implements spec §3.3 verbatim — pipeline integration, exception handler, `components={"error": repr(exc)}` contract, end-of-step summary log line. Any deviation from the spec is a finding.
- **Plan fidelity.** Tasks executed in plan order; no skipped tasks; no tasks added beyond the plan; commit messages include task IDs per §3 rule 4.
- **TDD integrity.** Each implementation commit has a preceding failing-test commit. No "implement first, test after."
- **Subagent partitioning (per §3).** Any duplicate task implementations, missing pre-task verification, mixed-task commits, or scratch-directory pollution is a finding.
- **Atomicity.** `_step_charts` per-ticker loop persists chart_target update + classification row in the SAME `lease.fenced_write()` block. Test verifies: simulate a database error mid-block → BOTH writes roll back (or BOTH commit) — not one without the other.
- **Classifier-exception contract.** Test verifies: when `classify_flag` raises, the persisted row has `pattern=NULL` AND `components_json` contains `{"error": ...}` key. Compounding-confound check: delete the `"error"` key construction; test should now FAIL.
- **End-of-step log line.** Test verifies: after a pipeline run with N classifier errors, the log contains the summary line with the correct count.
- **OHLCV reuse.** Test verifies: `classify_flag` is called with the SAME `bars` object that `render_chart` consumes (no separate fetch). Pure-function discipline (verified in Phase 1) means `bars` is unchanged after `classify_flag`.
- **`render_chart` no-op kwarg.** Test verifies: `render_chart(..., pattern_overlay=None)` produces an identical chart to `render_chart(...)` without the kwarg (backwards-compatible). `render_chart(..., pattern_overlay=PatternOverlay(...))` produces an IDENTICAL chart for now (no-op stub; Phase 6 changes this).
- **Discriminating tests.** Per `feedback_regression_test_arithmetic` and 2026-04-26 lessons, every test must produce different outcomes pre-fix vs post-fix. Vacuous tests are findings.
- **Mixed-anchor risk.** Phase 3 reads `pipeline_runs.id` to populate the `pipeline_run_id` audit anchor on classification rows. Verify the read does NOT use `MAX(run_ts) FROM pipeline_runs` or similar mixed-anchor patterns; bind to the in-flight `run` object directly.
- **Cross-table FK reference timing.** Verify `insert_classification` is called AFTER the `pipeline_runs` row exists (typically `run.id` is set by `lease.fenced_write()` open).
- **Out-of-scope creep.** No modification to `swing/data/`, `swing/web/`, `swing/trades/`, `swing/cli.py`, or `swing/evaluation/`.

---

## §6 Done criteria

Phase 3 execution is done when ALL of the following hold:

- [ ] All 4 tasks (3.1 through 3.4) have landed commits on `main`.
- [ ] Each commit message includes the task ID per §3 rule 4.
- [ ] No duplicate task implementations; no mixed-task commits.
- [ ] `python -m pytest -m "not slow" -q` green (full fast suite); baseline + new tests on `_step_charts` + classifier-exception path + `render_chart` kwarg.
- [ ] `ruff check swing/pipeline/ swing/rendering/` clean (no new violations).
- [ ] Pipeline runs successfully end-to-end with the live classifier active for chart-scope tickers (manual verification or integration test).
- [ ] Classifier-exception path persists `pattern=NULL` rows with `components_json` containing `{"error": ...}` key per spec §3.3 contract.
- [ ] End-of-step summary log line appears in pipeline logs with correct error count.
- [ ] Chart rendering is unchanged (no overlay painting yet — Phase 6 territory).
- [ ] No scratch pytest directories left in repo root.
- [ ] Adversarial Codex review on combined Phase 3 diff reaches `NO_NEW_CRITICAL_MAJOR`.
- [ ] Phase 3 implementation does NOT touch `swing/data/`, `swing/web/`, `swing/trades/`, `swing/cli.py`, OR `swing/evaluation/`.

---

## §7 Return report format

Final message to orchestrator (via operator) MUST include:

```
PHASE: 3 (Pipeline integration) of chart-pattern flag-v1 plan
COMMIT CHAIN: <first SHA>..<last SHA> (N commits)
FAST SUITE: 1052 → <new count> tests (Δ +<count>)
ADVERSARIAL ROUNDS: <N>; FINAL VERDICT: NO_NEW_CRITICAL_MAJOR

TASKS COMPLETED:
- Task 3.1 — <one-line summary, commit SHA>
- Task 3.2 — <one-line summary, commit SHA>
- Task 3.3 — <one-line summary, commit SHA>
- Task 3.4 — <one-line summary, commit SHA>

PARTITIONING DISCIPLINE OUTCOME:
- Subagent count: <N>
- Task assignments: <list which tasks went to which subagent>
- Collisions detected: <none / list any with details>
- Pre-task deliverable-existence checks: <how many fired; how many aborted>
- Scratch directories: <cleaned / list any remaining>

PIPELINE INTEGRATION SUMMARY:
- _step_charts per-ticker loop: classify_flag + insert_classification in same fenced_write
- Classifier-exception path: <verified contract; sample log line>
- End-of-step summary log: <sample format>
- render_chart kwarg: pattern_overlay added; no-op stub (Phase 6 paints)

ADVERSARIAL FINDINGS (each with disposition):
- <finding>: FIXED in commit <SHA> / ACCEPTED with rationale: <text>

OPEN QUESTIONS FOR ORCHESTRATOR:
- <any plan/spec contradiction surfaced; otherwise "None">

LESSONS WORTH CAPTURING (process insights from execution):
- <bullet list, including any partitioning-discipline observations>

PHASE 3 → PHASE 4 HANDOFF NOTES:
- <anything Phase 4 implementer needs to know that isn't in the plan>
```

---

## §8 If you get stuck

- **Plan/spec contradictions.** Surface in return report under "OPEN QUESTIONS." Do NOT amend the plan or spec; do NOT re-design.
- **TDD ordering uncertainty.** Failing-test-first. Phase 3's tasks are integration-style — strict per-task TDD applies cleanly.
- **Codex finding contradicts plan.** Apply receiving-code-review discipline. If finding correct AND plan wrong, surface to orchestrator. If finding wrong, document why with rationale.
- **Out-of-scope pull.** If a Phase 3 task seems to require touching out-of-scope code (Phase 4-7 territory), STOP. Surface as "OPEN QUESTIONS." Do NOT silently expand scope.
- **Subagent collision detected mid-execution.** STOP, surface to orchestrator immediately. Document the collision details (task ID, subagent IDs, commit SHAs, redundancy nature). The orchestrator may escalate to worktree isolation for the remainder of Phase 3.
- **`fenced_write` lease semantics.** If unclear, read `swing/pipeline/runner.py` for existing patterns; Tranche B-ops + Tranche C work established the lease discipline.
- **OhlcvCache breaker fires.** If the breaker trips during Phase 3 testing, classifier won't get OHLCV for some tickers — chart and classification both should be skipped for those tickers (no error row needed; ticker is just absent from the run). Verify this matches spec §3.3.

---

## §9 Anti-patterns specific to this execution

- **Scope creep into Phase 4 / Phase 5 / Phase 6.** The classification rows have no consumer at end of Phase 3 (Phase 4 wires watchlist read; Phase 5 wires trade-entry form; Phase 6 paints chart overlay). That's correct. Adding even small "while I'm here" consumer wiring is out of scope.
- **Painting the chart overlay in Phase 3.** Spec §3.4 + plan Phase 6 is the actual painting work. Phase 3 only adds the kwarg as a no-op stub.
- **Bypassing the classifier-exception contract.** Spec §3.3 prescribes `components={"error": repr(exc)}` literal key; Phase 3 is the SOLE owner of this contract. Do NOT use a different key name or structure.
- **OHLCV double-fetch.** `_step_charts` already fetches OHLCV for chart rendering; classifier reuses the same `bars` object. Do NOT add a separate fetch path.
- **Subagent task collision (per §3).** If the partitioning discipline fails (e.g., two subagents pick up Task 3.2), STOP and report rather than racing to commit.
- **Scratch directory pollution.** Use `pytest --basetemp` to direct scratch to a gitignored location, OR clean up after each task's test cycle. Do NOT leave artifacts in repo root.
- **Vacuous regression tests.** Per the 2026-04-26 lessons: every test must produce different outcomes pre-fix vs post-fix; for compounding-confound, deleting the keyed-on element must change test behavior.
- **Mixed-anchor mistakes.** Bind to in-flight `run.id` directly; do NOT read "latest pipeline_runs by run_ts" — Bug-7 family.
