# Paste-ready dispatch prompt — chart-pattern flag-v1 mathtext fix

Copy everything below the line into the new Claude Code instance.

---

You are dispatched as the chart-pattern flag-v1 mathtext title fix implementer for the Swing Trading project in this repo. HEAD at dispatch time is `05528a0` on `main`. This is a single-task small fix — no multi-task plan, no subagent dispatching.

**Step 1 — Read `docs/chart-pattern-flag-v1-mathtext-fix-brief.md` in full.** It contains the complete scope, per-task specs, manual visual verification procedure, and return report format. The brief is self-contained — no prior conversation context needed beyond what it points at.

**Step 2 — Read the §0 "Read first" references the brief lists**, particularly:
- `docs/chart-pattern-flag-v1-manual-verification-results.md` §"#1 — Mathtext title fix regression" — the failure mode technical detail.
- `docs/orchestrator-context.md` §"Lessons captured" — the entries on "Manual visual verification is not optional for rendering work" (Phase 6) and "Manual visual verification IS load-bearing — string-equality tests are not enough for rendered output" (2026-04-27 reinforcement). These lessons are *the reason* this fix is being dispatched as a brief instead of a quick orchestrator-thread edit; honor them.
- `docs/orchestrator-context.md` §"Binding conventions (project-wide)" — commit-message convention, no-amend / no-`--no-verify` rules.
- `swing/rendering/charts.py:75-100` and `tests/rendering/test_chart_overlay.py:260-300` — the surfaces being changed.

Do NOT read the chart-pattern flag-v1 design spec or implementation plan — they reference the historical (broken) title format and are explicitly out-of-scope.

**Step 3 — Execute the brief directly.** Skill posture per brief §0.1: standard `superpowers:using-superpowers` + `superpowers:test-driven-development` (one red-green-commit cycle: assertions updated first → red against unfixed code → production fix → green) + `superpowers:verification-before-completion` (mandatory) + `copowers:adversarial-critic` once at end (iterate to `NO_NEW_CRITICAL_MAJOR`). Do NOT invoke `superpowers:writing-plans`, `superpowers:executing-plans`, or any subagent-dispatching skill — the brief is the plan and the work is single-task.

**Critical disciplines:**

1. **Manual visual verification (brief §4.4) is BLOCKING.** Render two PNGs (non-overlay + overlay paths), open them via `Read`, and confirm visually that "stop" is not italicized, no `$` glyphs are in the title, and spacing is preserved. The original `2fd0ecc` regression slipped through because string-equality tests passed while the rendered PNG was still broken — do not repeat that failure mode.

2. **TDD red-phase is load-bearing.** Update test assertions FIRST, run pytest, capture the `AssertionError` output, include it in the return report. This is the discriminating-test evidence that the change actually flips the test's verdict. Then apply the production fix; run pytest again; tests go GREEN.

3. **Out-of-scope discipline.** Brief §2 enumerates exactly what NOT to touch (3 spec/plan historical records, other Tier-4 doc fixes, Tier-2/Tier-3 items, any other production code touching titles). If adversarial review surfaces a finding outside scope, flag it in "Open follow-ups" — do NOT expand mid-session.

4. **Commit convention.** Production fix is `fix(rendering): mathtext title regression — drop $ from chart title format` (no Task X.Y prefix; precedent set by `2fd0ecc` itself). Adversarial review-fix commits use `fix(rendering): Codex R<N> Major <M> — <description>`. No `(internal)` qualifier — this brief uses a single end-of-task Codex round, not within-task internal-Codex.

**Step 4 — Produce the return report per brief §6 as your final message.** Format is specified verbatim. Required sections: commits landed + SHAs + subjects, fast suite delta, adversarial verdict, **red-phase pytest evidence**, **PNG paths + 4-point visual confirmation**, adversarial findings table, open follow-ups, out-of-scope confirmation.

The operator will independently open the verification PNGs after your return report to confirm the visual fix. They are the final acceptance authority — your job is to produce a clean, verified deliverable + clear evidence; theirs is to look at the rendered chart and say "yes, fixed" or "no, still broken."

If you get stuck per brief §7 escape hatches — do NOT improvise; produce the return report with the blocker explicitly flagged and stop.
