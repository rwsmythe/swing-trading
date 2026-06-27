# Paste-ready dispatch prompt — chart-pattern flag-v1 chart-access UX (#2 + #3)

Copy everything below the line into the new Claude Code instance.

---

You are dispatched as the chart-pattern flag-v1 chart-access UX implementer for the Swing Trading project in this repo. HEAD at dispatch time is `84dac00` on `main`. This is a coupled dual-feature dispatch (#2 date-less chart URL + #3 open-positions row HTMX expand) — single implementer, no multi-task plan, no subagent dispatching.

**Step 1 — Read `docs/chart-pattern-flag-v1-chart-access-ux-brief.md` in full.** It contains scope, per-task specs, manual visual verification procedure, and return report format. The brief is self-contained — no prior conversation context needed beyond what it points at.

**Step 2 — Read the §0 "Read first" references**, particularly:
- `docs/chart-pattern-flag-v1-manual-verification-results.md` §"#2" + §"#3" — the user-facing problem statements + verification-round-1 empirical evidence.
- `docs/orchestrator-context.md` §"Currently in-flight work" + §"Lessons captured" (Phases 4+5+6+7 single-subagent + observable verification + 4-tier commit convention; HTMX OOB-swap drift; base-layout 5-VM rule per Phase 4 lesson) + §"Binding conventions."
- `CLAUDE.md` gotchas — particularly **HTMX OOB-swap partials must go through the SAME `{% include %}` target** and the **base-layout 5-VM rule** (apply only when `base.html.j2` actually dereferences the new field).
- **The model-to-mirror watchlist expand pattern**: `swing/web/routes/watchlist.py:27-67` (routes), `swing/web/view_models/watchlist.py:227-296` (builder + VM), `swing/web/templates/partials/watchlist_expanded.html.j2` (full partial, esp. lines 33-40 for chart-display logic).
- **The existing infrastructure to reuse**: `swing/web/app.py:234-238` (StaticFiles `/charts/<date>/<ticker>.png` mount — already exists, do NOT replace), `swing/web/chart_scope.py` (resolver + reason messages — reuse as-is, do NOT modify).
- **The existing surfaces to extend**: `swing/web/view_models/open_positions_row.py` + `swing/web/templates/partials/open_positions_row.html.j2` + `open_positions.html.j2`.

Do NOT read the chart-pattern flag-v1 design spec or implementation plan — those documents pre-date this UX work.

**Step 3 — Execute the brief directly.** Skill posture per brief §0.1: standard `superpowers:using-superpowers` + `superpowers:test-driven-development` (multiple red-green cycles, one per logical chunk) + `superpowers:verification-before-completion` (mandatory) + `copowers:adversarial-critic` once at end. Do NOT invoke `superpowers:writing-plans`, `superpowers:executing-plans`, or any subagent-dispatching skill. Single-implementer dispatch; brief is the plan.

**Critical disciplines:**

1. **The /charts route order matters.** `/charts/{ticker}.png` (dynamic) MUST be registered BEFORE `app.mount("/charts", StaticFiles(...))`. Verify empirically — write the test FIRST. If the dynamic handler doesn't fire, you'll get StaticFiles' built-in 404 instead of your operator-facing reason message; route order is the most likely culprit.

2. **Trade_id is the route key for #3, not ticker.** Mirrors watchlist's ticker-keyed routes but uses trade_id because it's unambiguous across a closed/reopened-position edge case. Brief §4.2 has the rationale.

3. **Reuse `chart_scope.resolve_chart_status` as-is.** Do NOT modify; do NOT add new chart_reason types. If existing messages are awkward in the open-positions context, flag in Open follow-ups.

4. **Do NOT hand-duplicate chart-display markup.** Per CLAUDE.md HTMX OOB-swap drift gotcha: the chart-display block in `watchlist_expanded.html.j2:33-40` and the new equivalent in `open_positions_expanded.html.j2` should ideally `{% include %}` a shared chart-display partial, OR (if the conditional branching makes that awkward) duplicate verbatim with a comment noting the intentional duplication. The drift failure is a matter of when, not if.

5. **V1 expanded-row scope is chart-only.** No P&L breakdown, no advisories list, no recent events. Operator can request additional fields as a separate post-V1 dispatch if useful. Brief §2 marks this explicitly out-of-scope.

6. **HTMX click-to-expand requires stopPropagation on interactive children.** Per Bug-1 lesson — any button/link inside the row needs `onclick="event.stopPropagation()"` to avoid triggering the row expand. Mirror watchlist_row.html.j2's pattern.

7. **Manual visual verification is BLOCKING (brief §4.4).** TestClient + asserted HTML strings verify structure, NOT runtime DOM/HTMX behavior — there's no JS test harness in this project (per `docs/phase3e-todo.md` known gap). Operator-witnessed browser verification is the actual confidence source. Include screenshot or operator-witnessed-PASS confirmation in the return report.

8. **Out-of-scope discipline.** Brief §2 enumerates exactly what NOT to touch. If adversarial review surfaces a finding outside scope, flag it in "Open follow-ups" — do NOT expand mid-session.

9. **Commit convention** (4-tier, per orchestrator-context Binding conventions). Production task commits split as TDD-discipline dictates (suggested: one commit per logical chunk). Adversarial review-fix commits use `fix(web): Codex R<N> Major <M> — <description>`. No `(internal)` qualifier — single end-of-task Codex round.

**Step 4 — Produce the return report per brief §6 as your final message.** Format is specified verbatim. Required sections: commits + SHAs, fast suite delta, adversarial verdict, TDD evidence, **PASS/FAIL per visual-verification check + screenshot or operator-witnessed confirmation**, adversarial findings table, open follow-ups, out-of-scope confirmation.

The operator will independently exercise the dashboard after your return report to confirm the UX. They are the final acceptance authority — your job is to produce a clean, verified deliverable + clear evidence.

If you get stuck per brief §7 escape hatches — do NOT improvise; produce the return report with the blocker explicitly flagged and stop.
