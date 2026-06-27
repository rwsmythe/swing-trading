# Paste-ready dispatch prompt — chart-scope policy v2 executing-plans

Copy everything below the line into the new Claude Code instance.

**Note:** dispatch a FRESH instance (not the writing-plans implementer). Project precedent favors author-vs-executor separation per phase; fresh-eyes catches bugs an author-implementer would paper over with implicit context.

---

You are dispatched as the chart-scope policy v2 executing-plans implementer for the Swing Trading project. HEAD at dispatch time is `d1dc4e4` on `main` (will advance as you commit). This is a single-implementer chain owning Tasks 1-10 sequentially — no parallel subagent dispatching.

**Step 1 — Read `docs/chart-scope-policy-v2-executing-plans-brief.md` in full.** It contains scope, skill posture, per-task discipline, return report format. Brief is self-contained.

**Step 2 — Read the §0 "Read first" references**, in order:
1. `docs/superpowers/plans/2026-04-27-chart-scope-policy-v2-plan.md` — **the plan is your primary input.** 3082 lines, 10 tasks. Plan went through 5 rounds of adversarial Codex review (all 11 majors RESOLVED, 0 ACCEPTED-with-rationale). Test fixtures, signatures, code paths are pinned against actual codebase state.
2. `docs/superpowers/specs/2026-04-27-chart-scope-policy-v2-design.md` — **the spec is the binding contract.** Approved at `c52835f` after 4 rounds of Codex review. If plan and spec disagree on any decision, SPEC wins; flag the disagreement and stop.
3. `docs/orchestrator-context.md` §"Binding conventions" + §"Lessons captured" + §"Recent decisions and framings" — particularly the chart-pattern flag-v1 phase lessons on single-subagent dispatch + observable verification + 4-tier commit convention; manual visual verification for Task 6; compounding-confound test fixtures recurring concern.
4. `CLAUDE.md` for project-wide gotchas.
5. **Recent precedent** (read for shape, not content): chart-pattern flag-v1 Phase 6 implementer chain (commit chain `0a0f7e8..2fd0ecc`); Tier-2 #2/#3 chart-access UX dispatch (commit chain `c52835f..a5fdc75`).

**Step 3 — Execute the brief directly.** Skill posture per brief §0.1: standard `superpowers:using-superpowers` + `copowers:executing-plans` (the primary skill — wraps `superpowers:subagent-driven-development` with adversarial Codex review on the combined diff after all task commits land). Do NOT invoke `copowers:brainstorming` or `copowers:writing-plans` (already done). Single subagent per task; no parallel dispatch.

**Critical disciplines:**

1. **The plan is the contract.** Every task executed faithfully per the plan's RED/GREEN/commit structure. If plan-vs-codebase drift exists (rare; HEAD was `63036cf` at plan-drafting time, has only advanced via this dispatch chain), flag in return report under "Plan amendment recommendations." Do NOT silently adapt the plan.

2. **TDD per task.** RED test FIRST → run pytest → see RED → minimal GREEN implementation → run pytest → see GREEN → commit. Per Phase 4 + Bug 7 lessons: every test must be discriminating — would this test actually fail under pre-fix code? The plan has explicit discriminating-verification language; honor it.

3. **Subject-only ERE grep before each task commit.** `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task <N>'`. The `-E` flag is required (BRE treats `+` as literal). If matches exist for the same task, abort + report — rogue duplicate detection per Phase 3-4 lesson.

4. **4-tier commit convention.** Task implementation: `feat(area): Task N — <description>`. Adversarial review-fix: `fix(area): Codex R<N> Major <M> — <description>`. Internal-Codex review-fix (subagent-driven within-task before orchestrator-Codex round): `fix(area): Codex R<N> Major <M> (internal) — <description>`. Format-only cleanup: `style(area): ...`.

5. **Internal review BEFORE Codex (Phase 5 lesson).** Per task: run a manual code-review pass on the diff before invoking Codex. Catches plan-anticipated misses + spec-skeleton drift cheaply. Optional but recommended internal-Codex round on per-task diff if the task touches multiple surfaces.

6. **Manual visual verification on Task 6 is BLOCKING (per Phase 6 + Tier-1 mathtext lessons).** Render real PNGs (overlay + non-overlay paths × stop=None/0/positive cases). Open via `Read` tool (multimodal). Confirm visually that stop hlines are omitted when stop ≤ 0 and rendered correctly when stop > 0. Include PNG paths + 4-point confirmation in return report.

7. **Plan baseline drift note.** Plan header states fast-suite baseline = 1145; actual at HEAD is **1163** (per Tier-2 #2/#3 dispatch's +18 tests post-spec). Trust pytest output over plan-stated number per project test-count-drift gotcha. Report actual delta.

8. **Adversarial Codex on COMBINED diff after Tasks 1-10.** Not per-task; once at end. Iterate to `NO_NEW_CRITICAL_MAJOR`. Fix-commits use `Codex R<N> ...` subject convention.

9. **Out-of-scope discipline.** Brief §2 enumerates what NOT to touch. If adversarial review surfaces a finding outside scope, document in "Open follow-ups." Do NOT expand mid-session.

10. **No mid-session plan or spec amendments.** Both are approved; deviations require operator approval + amendment + re-review (NOT in this dispatch).

**Step 4 — Produce the return report per brief §6 as your final message.** Required sections: final HEAD, tasks executed (10 of 10 or partial), fast suite delta (real numbers), schema version transition, adversarial Codex verdict, per-task commit table, visual verification (Task 6) PNG paths + 4-point confirmation, adversarial findings table, open follow-ups, out-of-scope confirmations, production rollout state.

The orchestrator will triage your return report; operator independently exercises the dashboard post-dispatch to confirm chart-scope-policy v2 production behavior (open positions appearing in chart-scope, watchlist tag-aware sort alignment, etc.).

If you get stuck per brief §7 escape hatches — do NOT improvise; produce the return report with the blocker explicitly flagged and stop.
