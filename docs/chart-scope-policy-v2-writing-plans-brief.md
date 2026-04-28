# Chart-Scope Policy v2 — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Run the `copowers:writing-plans` workflow against the approved chart-scope policy v2 design spec (`docs/superpowers/specs/2026-04-27-chart-scope-policy-v2-design.md`) to produce an implementation plan at `docs/superpowers/plans/2026-04-27-chart-scope-policy-v2-plan.md`. The plan is per-task, TDD-disciplined, single-task-per-commit, with explicit acceptance criteria + adversarial-review watch items. Adversarial Codex review on the plan is wrapped by `copowers:writing-plans` (target: `NO_NEW_CRITICAL_MAJOR`).

**Expected duration:** 2-4 hours including 2-3 rounds of adversarial review on the plan.

---

## §0 Read first

In this order:

1. `docs/superpowers/specs/2026-04-27-chart-scope-policy-v2-design.md` — **the spec is the source of truth.** Read end-to-end. Every plan task must trace back to a spec section. The spec already enumerates: tier model + selection (§A), schema migration (§B), resolver signature change (§C), config + rollout (§D), test coverage areas (§E), out-of-scope (§F).

2. `docs/orchestrator-context.md` — **§"Binding conventions (project-wide)"** for commit-message convention (4-tier with `(internal)` qualifier; ERE grep observable verification with `-E` flag + `[0-9]` POSIX class), no-amend / no-`--no-verify`, single-subagent dispatch + observable verification pattern (Phase 4-7 vindicated). **§"Lessons captured"** — particularly the chart-pattern flag-v1 phase lessons applicable to writing-plans:
   - "Plan-supplied test code can have plan-internal contradictions that surface only at implementation time" (Phase 6 internal-review-caught)
   - "Plan-spec test text with literal FK references can render ValueError tests vacuous when PRAGMA foreign_keys=ON" (Phase 2)
   - "Cross-column biconditional invariants need exhaustive truth-table enumeration" (Phase 2)
   - "Compounding-confound test fixtures can pass despite a vacuous primary discriminator" (Phase 4 + Bug 7)
   - "Reference-enumeration test patterns address determinism + correctness simultaneously" (Phase 1)
   - "Synthetic test fixtures must verify parameter→measurement 1:1 mapping empirically before threshold-pair tests" (Phase 1)
   - "Brief-drafting refinement: distinguish discriminating assertions from coupled text updates" (Tier-1)

3. `CLAUDE.md` at repo root — for project-wide gotchas (HTMX OOB-swap drift, base-layout 5-VM rule, yfinance rate-limit, matplotlib mathtext metacharacters, etc.). The plan must NOT introduce gotcha-class regressions.

4. **Recent precedent plans** (read for shape, not content):
   - `docs/superpowers/plans/2026-04-26-chart-pattern-flag-v1-plan.md` — most recent precedent. Per-phase task breakdown, TDD discipline, acceptance criteria, watch items per task. **Mirror the structural shape** (header, per-phase task list, per-task spec with red/green/commit, return report format).
   - The precedent plan has 7 phases × 4-12 tasks each. Chart-scope policy v2 is much smaller scope — likely 1 phase × 6-10 tasks total.

5. Reference files for the affected code surfaces (read selectively as needed during plan drafting):
   - `swing/web/chart_scope.py` (current resolver implementation)
   - `swing/pipeline/runner.py:541-700` (current `_step_charts`)
   - `swing/web/view_models/watchlist.py` (current `_sort_watchlist`)
   - `swing/web/view_models/open_positions_row.py` (current `build_open_positions_expanded`)
   - `swing/web/routes/charts.py` (current chart-redirect route)
   - `swing/data/migrations/0006_pipeline_chart_linkage.sql` (the schema migration this spec extends)

---

## §0.1 Skill posture

- Standard `superpowers:using-superpowers` skill at session start.
- **Primary skill:** `copowers:writing-plans` (wraps `superpowers:writing-plans` with adversarial Codex review on the resulting plan). Follow that workflow end-to-end. The skill drives:
  - Reading the spec.
  - Drafting the per-task implementation plan.
  - Spec-vs-plan completeness checks.
  - Adversarial Codex review (target: `NO_NEW_CRITICAL_MAJOR`).
  - Plan committed + verdict logged.
- DO NOT invoke `copowers:brainstorming` (already done; spec is approved at `c52835f`).
- DO NOT invoke `copowers:executing-plans` (the next phase after this one; out-of-scope for this dispatch).
- DO NOT invoke `superpowers:subagent-driven-development` or any subagent-dispatching skill — single implementer; no sub-dispatches.

---

## §1 Strategic context (compressed)

The spec reflects 4 rounds of adversarial Codex review (`NO_NEW_CRITICAL_MAJOR` after R4). All 11 major findings across R1-R3 were resolved via spec edits; 9 minors split between resolved and accepted-with-rationale. The spec is the binding contract — do NOT re-litigate decisions captured in §"Operator decisions captured" or in the inline `(Codex R<N> Major <M>)` markers.

**The plan's job** is to translate the spec into per-task TDD-disciplined work units, with explicit:

- Per-task RED-test before implementation.
- Per-task GREEN-implementation after RED.
- Per-task acceptance criteria (what the test verifies + what code change makes it pass).
- Per-task commit message (4-tier convention; task-implementation prefix `feat(...)` / `fix(...)` / `test(...)`).
- Adversarial-review watch items per task (concerns the writing-plans implementer can pre-empt).

**Suggested task breakdown** (writing-plans implementer should refine):

1. Schema migration `0011` + migration test (per spec §B).
2. `PipelineRunBinding` dataclass + `latest_completed_pipeline_run` helper (per spec §C).
3. `resolve_chart_scope` signature change + caller updates (3 sites) (per spec §C).
4. `_step_charts` policy rewrite (3-tier composition + dedup with canonicalization + tag-aware sort) (per spec §A).
5. Open-position pivot/stop sourcing + stop-hline omission for None/0 stops (per spec §A).
6. Wall-time monitoring + log-capture test (per spec §A acceptance threshold).
7. Config knob default change (5 → 10) (per spec §D).
8. Verification doc updates (post-rollout note in `docs/chart-pattern-flag-v1-manual-verification.md`).

The writing-plans implementer may sub-divide or merge these tasks per their judgment of TDD coherence; what matters is each task is independently RED-testable and the cumulative work covers the spec.

---

## §2 Scope

### In scope

- Drafting a per-task implementation plan at `docs/superpowers/plans/2026-04-27-chart-scope-policy-v2-plan.md`.
- Adversarial Codex review on the plan (via `copowers:writing-plans` wrapper).
- Plan committed to git; spec status updated if appropriate.

### Out of scope

- Implementation. The plan is a deliverable; executing it happens in a SEPARATE `copowers:executing-plans` dispatch.
- Re-litigating spec decisions. The spec is approved; deviations require operator approval + spec amendment + spec re-review (NOT in this dispatch).
- Modifying any production code (`swing/`, `tests/`).
- Modifying any other docs except the plan + this brief's status notes.

---

## §3 Binding conventions

- **Branch:** `main`. Commit conventionally; no Claude co-author footer; no `--no-verify`; no amending.
- **Plan path:** `docs/superpowers/plans/2026-04-27-chart-scope-policy-v2-plan.md`. Mirror the shape of `docs/superpowers/plans/2026-04-26-chart-pattern-flag-v1-plan.md` (headers, per-task structure, return report format).
- **Plan committed at the end of the writing-plans workflow** with subject `docs(superpowers): chart-scope policy v2 implementation plan`. Adversarial-fix commits (if Codex review surfaces issues requiring plan edits) use `docs(superpowers): chart-scope policy v2 plan — Codex R<N> Major <M> — <description>`.
- **Subject-only ERE grep observable verification** for the plan commit: `git log -E --pretty='%s' --grep='^docs\(superpowers\): chart-scope policy v2'` (the `-E` flag is required per the 2026-04-27 ERE refinement).

---

## §4 Per-task plan structure (template the writing-plans implementer should follow)

Each task in the plan should specify:

```markdown
### Task N.M — <task title>

**Spec section:** §<X> <subsection>

**Goal:** <one sentence>

**RED phase:**
- Add failing test at `tests/<path>/test_<file>.py::<test_name>`
- Test asserts: <specific assertion>
- Discriminating verification: <what guarantees this test would have failed pre-fix>

**GREEN phase:**
- Implement at `swing/<path>/<file>.py:<line range>`
- Implementation note: <key decision reasoning>

**Acceptance:**
- Test passes; full fast suite green.
- <other acceptance criteria>

**Commit subject:** `<type>(<area>): Task N.M — <description>`

**Adversarial-review watch items:**
- <Concern 1 the writing-plans phase can pre-empt>
- <Concern 2>
```

---

## §5 Done criteria

1. ✅ Plan written at `docs/superpowers/plans/2026-04-27-chart-scope-policy-v2-plan.md`.
2. ✅ Every task in the plan traces to a spec section.
3. ✅ Adversarial Codex review completed (≥2 rounds) → `NO_NEW_CRITICAL_MAJOR`.
4. ✅ All adversarial findings RESOLVED (plan edits) or ACCEPTED-with-rationale (documented in plan).
5. ✅ Plan committed to git + commit subject conforms to convention.
6. ✅ copowers session state updated (per `copowers:writing-plans` wrapper step).
7. ✅ Return report produced per §6.

---

## §6 Return report format

Produce as your final message:

```markdown
## Chart-Scope Policy v2 Writing-Plans Return Report

**Plan path:** docs/superpowers/plans/2026-04-27-chart-scope-policy-v2-plan.md
**Plan commit:** <SHA>
**Tasks:** <count> total

**Adversarial Codex verdict:** <NO_NEW_CRITICAL_MAJOR after R<N>>

### Plan summary

| Task | Spec section | Brief description |
|---|---|---|
| 1.1 | §B | Migration 0011 + tests |
| 1.2 | §C | PipelineRunBinding + helper |
| ... | ... | ... |

### Adversarial findings + dispositions

| Round | Issue | Severity | Disposition |
|---|---|---|---|
| R1 | <one line> | Critical/Major/Minor | RESOLVED in <plan section> / ACCEPTED <reason> |
| ... | ... | ... | ... |

### Open follow-ups (none expected; flag if any)

<items deferred per spec or surfaced for future work>

### Out-of-scope confirmations

- Implementation: NOT done; executing-plans is a separate dispatch.
- Spec amendments: NONE; spec is approved as-is.
- Production / test code: UNTOUCHED.
```

---

## §7 If you get stuck

- **Spec ambiguity surfaces during plan drafting** → flag in plan; do NOT make a unilateral interpretive call. Suggest amendment in return report; orchestrator + operator decide.
- **Plan-spec mismatch (test cases need a fact the spec doesn't specify)** → choose the conservative interpretation; document the ambiguity in the plan task's "Open follow-ups for spec amendment" line; orchestrator triages post-dispatch.
- **Adversarial Codex review surfaces an issue with the SPEC (not the plan)** → flag in return report under "Spec amendment recommendations." Do NOT modify the spec mid-dispatch; spec amendments require explicit operator approval per orchestrator-context "Recent decisions and framings — Don't reopen them unless the developer does."
- **Plan task count grows beyond ~12** → consider whether to phase-split (e.g., schema-migration phase, resolver-signature phase, _step_charts-policy phase). Spec scope is ~6-10 tasks; >12 may indicate the writing-plans implementer is over-decomposing OR uncovering scope creep.
- **MAX_ROUNDS reached on adversarial review without resolution** → produce the return report with unresolved issues documented; operator decides whether to merge as-is or iterate.
- **Anything else** → produce the return report with what you have, mark the blocked item explicitly, and stop. Operator + orchestrator triage.
