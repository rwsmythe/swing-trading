# Paste-ready dispatch prompt — chart-scope policy v2 writing-plans

Copy everything below the line into the new Claude Code instance.

---

You are dispatched as the chart-scope policy v2 writing-plans implementer for the Swing Trading project. HEAD at dispatch time is `c52835f` on `main`. This is a single-implementer dispatch — no multi-task plan, no subagent dispatching. You produce ONE deliverable: a per-task implementation plan at `docs/superpowers/plans/2026-04-27-chart-scope-policy-v2-plan.md`.

**Step 1 — Read `docs/chart-scope-policy-v2-writing-plans-brief.md` in full.** It contains scope, skill posture, plan-task template, return report format. Brief is self-contained.

**Step 2 — Read the §0 "Read first" references**, in order:
1. `docs/superpowers/specs/2026-04-27-chart-scope-policy-v2-design.md` — **the spec is the binding contract.** Approved by 4 rounds of adversarial Codex review. Do NOT re-litigate decisions captured in `(Codex R<N> Major <M>)` markers or in §"Operator decisions captured."
2. `docs/orchestrator-context.md` §"Binding conventions" + §"Lessons captured" — particularly the Phase 1-7 lessons on plan-drafting failure modes (synthetic-fixture mapping, threshold-pair vacuousness, FK-references, biconditional truth-tables, compounding-confound tests, reference-enumeration patterns).
3. `CLAUDE.md` for project-wide gotchas.
4. **Recent precedent:** `docs/superpowers/plans/2026-04-26-chart-pattern-flag-v1-plan.md` — read for STRUCTURAL SHAPE, not content. Mirror header style, per-task layout, return-report format.
5. Source files for the affected surfaces (read selectively as you draft each task).

**Step 3 — Execute the brief directly.** Skill posture per brief §0.1: standard `superpowers:using-superpowers` + `copowers:writing-plans` (the primary skill — wraps `superpowers:writing-plans` with adversarial Codex review on the resulting plan). Do NOT invoke `copowers:brainstorming` (already done) or `copowers:executing-plans` (next phase, separate dispatch). Do NOT dispatch sub-subagents.

**Critical disciplines:**

1. **The spec is binding.** Every plan task must trace to a spec section. Do NOT add implementation work the spec doesn't require. Do NOT omit work the spec requires.

2. **TDD per task.** Each task specifies a RED test first, GREEN implementation second, with EXPLICIT discriminating-verification language showing the test would have failed pre-fix. Per the Phase 1 + Phase 4 + Bug 7 lessons: avoid synthetic-fixture confounds, threshold-pair vacuousness, compounding-confound tests, monkeypatch-capture failures.

3. **Single task per commit, 4-tier convention.** Task implementation: `feat(area): Task N.M — <description>`. Adversarial review-fix: `fix(area): Codex R<N> Major <M> — <description>`. Subject-only ERE grep verification per project convention.

4. **Out-of-scope discipline.** Brief §2 enumerates what NOT to touch. If adversarial review surfaces a concern outside scope, document in "Open follow-ups for future dispatches." Do NOT expand mid-session.

5. **Plan length:** target ~600-1500 lines. The chart-pattern flag-v1 plan is ~7000 lines across 7 phases × 4-12 tasks each; chart-scope policy v2 is much smaller scope (1 phase × 6-10 tasks total).

6. **Spec ambiguity is NOT yours to resolve.** If a task needs a decision not in the spec, choose the conservative interpretation, document the ambiguity in the task's open-follow-ups, and surface it in the return report. Do NOT modify the spec.

**Step 4 — Produce the return report per brief §6 as your final message.** Required sections: plan path + commit SHA, task count, adversarial Codex verdict (target `NO_NEW_CRITICAL_MAJOR` after ≥2 rounds), per-task summary table, adversarial findings table, open follow-ups, out-of-scope confirmations.

The orchestrator will triage your return report + then operator approves or iterates before the next phase (`copowers:executing-plans` dispatch).

If you get stuck per brief §7 escape hatches — do NOT improvise; produce the return report with the blocker explicitly flagged and stop.
