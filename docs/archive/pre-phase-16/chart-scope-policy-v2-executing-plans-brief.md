# Chart-Scope Policy v2 — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute the chart-scope policy v2 implementation plan (`docs/superpowers/plans/2026-04-27-chart-scope-policy-v2-plan.md`) — 10 tasks, single phase. Per-task TDD (RED test → GREEN implementation → commit), 4-tier commit convention, adversarial Codex review on the full diff after all task commits land. Output: chart-scope policy v2 shipped on `main` with all spec invariants verified.

**Expected duration:** 3-5 hours including TDD per task + 2-4 rounds Codex review on the combined diff.

---

## §0 Read first

In this order:

1. `docs/superpowers/plans/2026-04-27-chart-scope-policy-v2-plan.md` — **the plan is your primary input.** 3082 lines, 10 tasks. Read end-to-end. The plan went through 5 rounds of adversarial Codex review (all 11 majors RESOLVED, 0 ACCEPTED-with-rationale); test fixtures, signatures, code paths are pinned against actual codebase state.

2. `docs/superpowers/specs/2026-04-27-chart-scope-policy-v2-design.md` — **the spec is the binding contract.** Approved at commit `c52835f` after 4 rounds of adversarial Codex review. The plan implements the spec verbatim. If the plan and spec disagree on any decision, the SPEC wins; flag the disagreement in your return report and stop.

3. `docs/orchestrator-context.md`:
   - **§"Binding conventions"** — 4-tier commit convention with `(internal)` qualifier; ERE grep observable verification with `-E` flag + POSIX `[0-9]` class.
   - **§"Lessons captured"** — the chart-pattern flag-v1 phase lessons applicable to executing-plans:
     - "Single-subagent dispatch + observable verification successfully prevents rogue duplicates" (Phase 4-7 vindication; 7-phase ZERO-rogue track record)
     - "Internal code-review BEFORE Codex saves a round" (Phase 5)
     - "Codex's contextual advantage at finding cross-feature interactions vs internal review" (Phase 5)
     - "Manual visual verification is not optional for rendering work" (Phase 6 + Tier-1 mathtext) — applies to Task 6 (chart-title rendering with stop-hline omission)
     - "Subsequent-phase tests can surface earlier-phase contract bugs" (Phase 3) — relevant if Task 5's `_step_charts` rewrite surfaces a Task 3 contract bug
     - "Compounding-confound test fixtures can pass despite a vacuous primary discriminator" (Phase 4 + Bug 7 + chart-scope-v2 plan R3+R4) — discriminating-verification language is mandatory
   - **§"Recent decisions and framings"** — particularly the 4-tier commit convention with `(internal)` qualifier from Phase 6, and the orchestrator-vs-implementer brainstorm pattern decision.

4. `CLAUDE.md` for project-wide gotchas — particularly:
   - HTMX OOB-swap drift (preserved by single-include guarantee)
   - Base-layout 5-VM rule (apply only when `base.html.j2` dereferences the new field)
   - yfinance rate-limit (binding constraint for budget validation)
   - Matplotlib mathtext metacharacters (relevant to Task 6 chart-title rendering)

5. **Recent precedent** (read for shape, not content):
   - The chart-pattern flag-v1 Phase 6 implementer chain (commit chain `0a0f7e8..2fd0ecc`) — most-recent precedent for an executing-plans dispatch with rendering work + Codex review.
   - The Tier-2 #2/#3 chart-access UX dispatch (commit chain `c52835f..a5fdc75`) — recent precedent for a smaller-scope executing dispatch.

---

## §0.1 Skill posture

- Standard `superpowers:using-superpowers` skill at session start.
- **Primary skill:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development` with adversarial Codex review on the combined diff after all task commits land). Follow the skill's workflow:
  - Single subagent per task (per Phase 4-7 ZERO-rogue track record discipline).
  - Per-task TDD red-green-commit cycle.
  - Adversarial Codex review on the COMBINED diff after Tasks 1-10 all commit (not per-task).
  - Iterate to `NO_NEW_CRITICAL_MAJOR`.
- DO NOT invoke `copowers:brainstorming` or `copowers:writing-plans` (already done; spec at `c52835f`, plan at `d1dc4e4`).
- DO NOT dispatch sub-subagents to other implementer tasks. Single implementer chain owns Tasks 1-10.
- `superpowers:test-driven-development` — implicit per task. The plan has explicit RED/GREEN steps per task.
- `superpowers:verification-before-completion` — MANDATORY before producing the return report.

---

## §1 Strategic context (compressed)

The plan executes the chart-scope policy v2 spec end-to-end. Three coupled changes ship together:

1. **Schema migration `0011`** (Task 1) extends `pipeline_chart_targets.source` CHECK to allow `'open_position'` and `'tag_aware_top_n'`; legacy `'near_proximity'` retained.
2. **Resolver signature change** (Tasks 2 + 3) introduces `PipelineRunBinding` + `latest_completed_pipeline_run` helper; `resolve_chart_scope` now requires a binding parameter; 3 caller sites migrate.
3. **Pipeline policy rewrite** (Tasks 4 + 5) extracts `_tag_aware_sort_key` shared helper and rewrites `_step_charts` to use 3-tier composition with deduplication + ticker canonicalization.

Plus auxiliary tasks:
- Task 6: stop-hline omission for None/0 stops (Codex R2 Major 3 from spec phase).
- Task 7: chart-step wall-time monitoring (60s WARN / 120s ERROR) with log-capture test.
- Task 8: config knob `chart_top_n_watch` default 5 → 10.
- Task 9: manual verification doc post-rollout note.
- Task 10: phase checkpoint with reviewer call-site audit (Codex R4 Minor 2).

The plan is structurally complete. Your job is to faithfully execute it — not to redesign or re-spec.

**Plan baseline drift note:** the plan header states `1145` as the fast-suite baseline. Actual baseline at HEAD is **1163** (per the Tier-2 #2/#3 dispatch which added 18 tests post-spec). This is a documentation drift in the plan, not a load-bearing constraint. **Trust pytest output over the plan-stated number** per the project test-count-drift gotcha. The executing implementer's return report should report the actual delta from real measurement.

---

## §2 Scope

### In scope

- Implement Tasks 1-10 from the plan, in order, per TDD discipline.
- Adversarial Codex review on the combined diff after all task commits land.
- Manual visual verification on Task 6 (chart-title rendering — per the Phase 6 + Tier-1 mathtext lesson "Manual visual verification is not optional for rendering work").
- Return report per §6 of this brief.

### Out of scope

- Plan amendments. The plan is approved at commit `d1dc4e4`; deviations require operator approval + plan amendment + plan re-review (NOT in this dispatch).
- Spec amendments. The spec is approved at `c52835f`; same discipline applies.
- Mid-session scope expansion. If adversarial review surfaces a finding outside scope, document in "Open follow-ups" — do NOT expand mid-session per the orchestrator-context anti-pattern.
- Task reordering, merging, or skipping. Tasks 1-10 are sequenced by dependencies; execute in plan order.
- Parallel subagent dispatching. Single implementer chain owns Tasks 1-10 sequentially.
- Other code paths not enumerated in the plan (e.g., CLI / journal / advisories / Phase 2 `swing/trades/` repos) — UNTOUCHED.

---

## §3 Binding conventions

- **Branch:** `main`. Commit conventionally; no Claude co-author footer; no `--no-verify`; no amending.
- **Commit-message convention** (4-tier per orchestrator-context):
  - **Task implementation commits:** `feat(area): Task N — <description>` for the primary commit per task. Sub-task commits within a task: `feat(area): Task N (sub) — <description>`.
  - **Adversarial review-fix commits** (after combined-diff Codex review): `fix(area): Codex R<N> Major <M> — <description>`.
  - **Internal-Codex review-fix commits** (subagent-driven within-task review BEFORE orchestrator-Codex round): `fix(area): Codex R<N> Major <M> (internal) — <description>`.
  - **Format-only cleanup commits:** `style(area): ...` (no task ID).
- **Subject-only ERE grep observable verification** before each task implementation commit: `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task <N>'`. The `-E` flag is required (BRE treats `+` as literal).
- **TDD per task:** failing test → run pytest to see RED → minimal implementation → run pytest to see GREEN → commit. Per the plan's per-task structure.
- **Fast suite must stay green** at every task commit boundary: `python -m pytest -m "not slow" -q`. Baseline at start: 1163 (trust pytest, not plan-stated 1145). Post-dispatch: 1163 + N (N = sum of new tests across Tasks 1-10; plan estimate ~30-40 net new tests).
- **Ruff baseline 81 errors;** do not introduce new violations.
- **Phase isolation:** plan §"Phase isolation" calls out the migration + `EXPECTED_SCHEMA_VERSION` bump as a Phase 2 carve-out (`swing/data/migrations/` + `swing/data/db.py:EXPECTED_SCHEMA_VERSION`); `swing/trades/` is NOT modified. Honor this carve-out boundary.
- **Manual visual verification on Task 6** is BLOCKING (per Phase 6 lesson). Render real PNGs (overlay + non-overlay paths, with stop=None/0 + with stop>0 cases); confirm visually that stop hlines are omitted when stop ≤ 0 and rendered when stop > 0. Include PNG paths + 4-point visual confirmation in the return report.

---

## §4 Per-task execution discipline

The plan has explicit RED/GREEN/commit structure per task. Your job is to faithfully execute it.

**Per-task workflow:**

1. Read the plan task end-to-end before starting.
2. Verify against the actual codebase state (file paths, signatures, fixtures) — the plan's references are pinned at writing-plans time but the codebase may have drifted (unlikely; HEAD is `63036cf` as of plan commit `d1dc4e4`).
3. Add the failing test per the plan's RED step. Run pytest; see RED. Capture the AssertionError output (operator may want it in the return report for high-impact tasks).
4. Implement the minimal code change per the plan's GREEN step.
5. Run pytest; see GREEN. Run the full fast suite; verify 0 regressions.
6. Run subject-only ERE grep verification: `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task <N>'`. If matches exist for the same task, abort + report (rogue duplicate detection per Phase 3-4 lesson).
7. Commit with the prescribed subject.

**Per-task internal review (per Phase 5 lesson):** before invoking the orchestrator-Codex round, run an internal manual code-review pass on the diff per task. Catches plan-anticipated misses + spec-skeleton drift cheaply. The Phase 5 + Phase 7 ZERO-rogue track record was partly attributable to this internal review pass.

**Per-task internal-Codex round** (per Phase 6 lesson, optional but recommended): subagent-dispatched internal-Codex round on the per-task diff BEFORE the orchestrator-wrapper Codex round. Use the `(internal)` qualifier on any review-fix commits. Saves orchestrator round budget if it catches issues that orchestrator's Codex would find.

**Cross-task interaction watch:** Tasks 1-3 form the schema + signature foundation; Tasks 4-7 build on it. If Task 4-7 surfaces a contract bug in Tasks 1-3 (per Phase 3 lesson "Subsequent-phase tests can surface earlier-phase contract bugs"), do NOT silently fix earlier task in-place — instead, add the fix as a Task <N> follow-up commit with explicit cross-reference, OR flag in return report for orchestrator triage if the fix would expand scope.

---

## §5 Done criteria

1. ✅ All 10 tasks committed with proper subject convention; subject-only ERE grep returns the expected 10 matches (one per task).
2. ✅ Fast suite green at HEAD: `python -m pytest -m "not slow" -q` — actual delta reported (1163 + N).
3. ✅ Adversarial Codex review on combined diff → `NO_NEW_CRITICAL_MAJOR`; any review-fix commits landed with `Codex R<N> ...` subject convention.
4. ✅ Manual visual verification on Task 6 done; PNG paths + 4-point confirmation in return report.
5. ✅ Reviewer call-site audit per Task 10 Step 3 done; the docstring + code-review checklist enforcement for `resolve_chart_scope` is verified in code.
6. ✅ Migration `0011` applied; `schema_version = 11` post-dispatch; existing rows preserved.
7. ✅ Working tree clean (only `.tmp-*/` scratch dirs untracked).
8. ✅ Out-of-scope items confirmed untouched in return report.

---

## §6 Return report format

Produce as your final message:

```markdown
## Chart-Scope Policy v2 Executing-Plans Return Report

**Final HEAD:** <SHA>
**Tasks executed:** 10 of 10 / N of 10 (if partial)
**Fast suite:** <baseline 1163> → <post-dispatch> (<delta> = N new tests)
**Schema version:** 10 → 11

**Adversarial Codex verdict:** <NO_NEW_CRITICAL_MAJOR after R<N> rounds>

### Task commits

| Task | Spec section | Commit SHA | Subject |
|---|---|---|---|
| 1 | §B | <SHA> | feat(data): Task 1 — Migration 0011 source-taxonomy expansion |
| 2 | §C | <SHA> | feat(web): Task 2 — PipelineRunBinding + latest_completed_pipeline_run |
| ... | ... | ... | ... |

(Sub-task commits listed under their parent task as applicable.)

### Visual verification (Task 6)

PNG paths:
- `<path>` — non-overlay, stop=None
- `<path>` — non-overlay, stop=0
- `<path>` — non-overlay, stop>0
- `<path>` — overlay, stop>0

**4-point visual confirmation** (operator-facing):
1. Stop hline OMITTED when stop is None: PASS / FAIL — <one sentence>
2. Stop hline OMITTED when stop is 0: PASS / FAIL — <one sentence>
3. Stop hline RENDERED at correct y when stop > 0: PASS / FAIL — <one sentence>
4. Title format consistent with existing chart titles: PASS / FAIL — <one sentence>

### Adversarial findings + dispositions

| Round | Finding | Severity | Disposition |
|---|---|---|---|
| R1 | <one line> | Critical/Major/Minor | RESOLVED in <SHA> / ACCEPTED <reason> |
| ... | ... | ... | ... |

### Open follow-ups

<items deferred per scope or surfaced for future work; align with plan §"Open follow-ups for future dispatches" 7-item list>

### Out-of-scope confirmations

- Plan amendments: NONE; plan executed as-is at d1dc4e4.
- Spec amendments: NONE; spec executed as-is at c52835f.
- Phase 2 (`swing/trades/`): UNTOUCHED.
- CLI / journal / advisories: UNTOUCHED.
- Other surfaces beyond plan scope: UNTOUCHED.

### Production rollout state

- Migration 0011 applied; legacy 'near_proximity' rows preserved.
- chart_top_n_watch default raised 5 → 10.
- Open positions enter chart-scope on next pipeline run.
- Operator can hit `/charts/<TICKER>.png` for any open position post-next-run.
```

---

## §7 If you get stuck

- **Plan-vs-codebase drift** (file paths, signatures, fixtures changed since plan was drafted) → check `git log` to see what landed since `d1dc4e4`; if real drift exists, flag in return report under "Plan amendment recommendations." Do NOT silently adapt the plan; the plan is the contract.
- **TDD red-phase doesn't go RED** as the plan predicts → either the test is non-discriminating (compounding-confound from Phase 4 lesson — verify the test would actually fail under pre-fix code), OR the implementation is already in place (rogue duplicate detection). Investigate; do NOT proceed silently.
- **Migration 0011 fails or produces unexpected schema state** → halt; do NOT proceed past Task 1. Migration failures cascade to Tasks 5+ (writes new source values).
- **Wall-time test is flaky despite the deterministic time-patch design** → check the test fixture's monkeypatch target; mplfinance import scope is the most common gotcha (per chart-scope-v2 plan R3 Major 2 — patched `mplfinance.plot` directly on upstream module, NOT via re-import).
- **Adversarial Codex round surfaces a finding outside the plan's scope** → flag in "Open follow-ups." Do NOT expand mid-session.
- **MAX_ROUNDS reached on adversarial review without resolution** → produce the return report with unresolved findings; operator decides whether to merge as-is or iterate.
- **Anything else** → produce the return report with what you have, mark the blocked item explicitly, and stop. Operator + orchestrator triage.
