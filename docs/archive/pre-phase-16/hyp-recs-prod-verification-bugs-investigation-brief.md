# Hyp-recs Production Verification Bugs — Investigation-First Bug-Fix Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Investigate three production-confirmed bug classes from operator's Phase 2 manual verification (2026-04-29). For each bug, reproduce deterministically, identify the actual mechanism via empirical evidence (NOT static-read plausibility), then submit a "mechanism candidate" message for **operator-confirmation gate** BEFORE designing fixes. After operator confirms each mechanism, design + ship fixes via standard TDD discipline + adversarial Codex review.

**Dispatch type:** Investigation-first bug-fix per `docs/orchestrator-context.md` §"Bug-fix briefs and operator-confirmation gate". NOT a copowers wrapper dispatch — the operator-confirmation gate replaces the brainstorm/spec/plan ceremony for confirmed-bug-fix scope.

**Expected duration:** ~2-3 hr investigation phase + operator-confirmation gate (async; could be hours-to-day for operator's confirmation availability) + ~3-5 hr fix implementation + 2-4 Codex rounds = ~8-12 hr total work, paced to operator's confirmation availability.

---

## §0 Read first

1. **`CLAUDE.md`** — particularly:
   - HTMX OOB-swap partial drift gotcha (load-bearing for Bug B investigation).
   - HTMX 4xx swap config override note (different concern but signals HTMX's parser/swap idiosyncrasies are non-trivial).
   - Stale-server failure mode after code changes (relevant if testing in dev environment).

2. **`docs/orchestrator-context.md`** — read these sections:
   - §"Bug-fix briefs and operator-confirmation gate" — defines the binding gate template; this brief follows the protocol.
   - §"Anti-patterns to avoid" — particularly "Bug-fix investigation that tests plausible mechanisms instead of operator's actual reproduction" (Bug 2 anti-pattern, 2026-04-25). The plausible static-read mechanisms in §2 of this brief are STARTING HYPOTHESES — DO NOT design fixes against them without empirical confirmation.
   - §"Lessons captured" — particularly:
     - **JS-execution test harness gap matters more than weighted** (just-captured 2026-04-29; this dispatch's bugs are exactly the failure mode that lesson describes).
     - **ACCEPTED-with-rationale on production-facing surfaces are conditional acceptance** (just-captured 2026-04-29).
     - **Spec/plan silence on form-driven success-path** (2026-04-29; parent dispatch's failure mode).
     - Multi-path-ingestion (2026-04-29; relevant to the `exclude_tickers` invariant breadth).

3. **The just-shipped success-path fix dispatch chain:** commits `c03a01c → d2c10cc → f9e4560 → ba575e8 → 39ff313` on `main`. Particularly commit `39ff313` (Task 5; the entry_post change introducing `#hypothesis-recommendations` OOB swap).

4. **Source files (read in full):**
   - `swing/web/routes/trades.py` `entry_post` function (approximately lines 568-637 — the response-shape construction).
   - `swing/web/templates/partials/open_positions_row.html.j2` — the row partial; note no `hx-swap-oob` attribute (relevant to Bug A).
   - `swing/web/templates/partials/watchlist_top5_section.html.j2` — the watchlist OOB swap target.
   - `swing/web/templates/partials/hypothesis_recommendations.html.j2` — the hyp-recs OOB swap target with `oob` kwarg branch (commit `ba575e8`).
   - `swing/web/view_models/dashboard.py` — `build_dashboard`, `build_hyp_recs_section`, `latest_evaluation_run_id`. Particularly relevant for Bug B (mid-request anchor state).

5. **The just-shipped success-path fix plan** at `docs/superpowers/plans/2026-04-29-hyp-recs-success-path-fix-plan.md` — context for the recently-shipped fixes that the bugs persist alongside.

If any file path doesn't resolve, surface in return report — do NOT silently proceed against a stale path.

---

## §0 Skill posture

- **DO NOT INVOKE** `copowers:brainstorming`, `copowers:writing-plans`, `copowers:executing-plans`. This is a bug-fix dispatch with operator-confirmation gate; no copowers wrapper is required.
- **DO use TDD discipline** (failing test first → minimal implementation → passing test → commit) on the fix phase per §5.
- **DO invoke `copowers:adversarial-critic`** on the fix-phase combined diff. Iterate to `NO_NEW_CRITICAL_MAJOR`.
- **Operator-confirmation gate is BINDING** — do NOT proceed to design fixes until operator confirms each bug's mechanism.

---

## §1 Strategic context

**Phase 2 production verification surfaced three bugs.** The just-shipped hyp-recs success-path fix dispatch (commits `c03a01c → 39ff313`) shipped 1309 fast tests passing including 5 integration + 1 structural-guard for the new entry_post OOB-swap behavior — but operator's manual verification revealed the tests miss real production failure modes.

**Phase 2 production verification is BLOCKED** until these bugs are fixed. Phase 3 (OHLCV archive consolidation) is held until Phase 2 closes.

**Operator's verification report (verbatim, 2026-04-29):**

| Test step | Operator's report |
|---|---|
| 4. Click per-row Enter on hyp-rec; submit (success) | "The hyp-rec table and watchlist table in dashboard lost all entries. New entry did NOT appear in open-positions. Clicking on watchlist link, then back to dashboard repopulated the tables, including the new open position. New open position is still present in the hyp-rec table." |
| 5. Watchlist-origin entry submit | "From the watchlist in dashboard, the watchlist entries all disappeared and the open positions table was not updated. Hard refreshing the page showed correct entries in both open position tables and watchlist." |
| 7. CC pivot bug | "Bug looks fixed by spot checking" |
| 8. Origin survival on validation error | "not sure how to test this" |

---

## §2 The three bug classes

### Bug A: Open-positions table never updates from entry_post (pre-existing structural)

**Symptom:** submitting any entry (watchlist OR hyp-recs origin) does NOT cause the new open-position row to appear in the `#open-positions` table. Operator hard-refresh fixes (the trade IS persisted; the IN-PLACE swap path is broken).

**Static-read mechanism (orchestrator hypothesis; STARTING HYPOTHESIS — empirically confirm):**
- entry_post response (lines 631-637 of `swing/web/routes/trades.py`) contains `{row_html}` as the primary response (an open-positions `<tr>`), plus OOB swaps for `#status-strip`, `#watchlist-top5`, and (new) `#hypothesis-recommendations`.
- The form's `hx-target="closest tr" hx-swap="outerHTML"` directs the primary swap to replace the form's `<tr>` (which is in the source tbody — watchlist OR hyp-recs).
- `partials/open_positions_row.html.j2` has NO `hx-swap-oob` attribute, so HTMX treats the response's `<tr>` as primary content.
- Net effect: the new open-position row briefly lands in the source tbody, then gets nuked when the source tbody's OOB swap rebuilds the section. **Nothing places the new row in the actual `#open-positions` table.**

**Investigation tasks for Bug A:**
1. Reproduce deterministically via TestClient: submit a watchlist-origin entry; assert response body and verify the open-positions row markup is present BUT has no OOB swap target.
2. Render the response in a real browser (operator-witnessed OR via headless browser instrumentation if available). Inspect DOM after submit. Confirm:
   - `#open-positions` `<tbody>` does NOT contain the new row.
   - Source tbody briefly contained the row, then was rebuilt empty-of-it.
3. Confirm pre-existing nature: check git history of `entry_post` for any prior `#open-positions` OOB swap that may have been removed.

### Bug B: Watchlist disappears on hyp-recs origin entry submit (mechanism unknown)

**Symptom (operator's bug 4):** submitting a hyp-recs origin entry causes BOTH the hyp-recs table AND the watchlist table to lose all entries. Hard navigation away and back repopulates correctly.

**Symptom (operator's bug 5):** submitting a watchlist origin entry causes the watchlist entries to disappear AND the open-positions table is not updated. Hard refresh fixes.

**Mechanism: UNKNOWN.** Static-read suggests several possible mechanisms; investigation must identify which is actually firing:

Possible mechanisms (NON-exhaustive; do NOT design fixes against any without empirical confirmation):
- (a) `dashboard_vm.watchlist` returning empty during entry_post execution due to mid-request anchor state (e.g., `latest_evaluation_run_id` resolving to a different run mid-request).
- (b) OOB markup malformed for watchlist OR hyp-recs section; HTMX failing to parse and silently replacing target with empty content.
- (c) HTMX swap-order interaction: primary swap fires first (replacing form `<tr>` with open-positions `<tr>` in source tbody); OOB swap fires second (rebuilding source tbody, which removes orphan AND any pre-existing watchlist content).
- (d) The `dashboard_vm.watchlist` field is correctly populated, but the rebuilt watchlist content is structurally different from the page-load watchlist content (different VM build path?). The `build_dashboard` call inside entry_post may use different anchor logic than the dashboard route handler does at `/`.
- (e) Some cross-section interaction between the new `#hypothesis-recommendations` OOB swap and the existing `#watchlist-top5` OOB swap — e.g., a missing `<section>` close tag in one OOB chunk causing HTMX to misinterpret subsequent chunks.
- (f) The watchlist OOB content correctly excludes the just-traded ticker (which is the intent), but the operator's watchlist had only one or two entries pre-trade and the rebuild produced an empty section that was correct-by-design but visually identical to the bug.

**Investigation tasks for Bug B:**
1. Reproduce deterministically: TestClient submission with multiple watchlist tickers seeded; capture full response body; assert the `#watchlist-top5` OOB chunk content matches expectation.
2. If TestClient response body is correctly populated but operator's browser shows empty: the bug is in HTMX parsing/swap behavior, NOT in the response shape. Manual browser DevTools network/DOM inspection is required.
3. Add logging instrumentation to entry_post: log `len(dashboard_vm.watchlist)` post-build; log the rendered `watchlist_section_html` length. Compare to page-load equivalent.
4. **Critical:** if the static-read mechanism (c) HTMX swap-order is the actual mechanism, the fix isn't trivial — primary swap and OOB swap interaction with the same tbody is a known HTMX gotcha. May need to rethink the response architecture (e.g., omit primary `closest tr` swap entirely; rely solely on OOB swaps).

### Bug C: exclude_tickers invariant too narrow (Codex R1 M1 confirmed in production)

**Symptom (from operator's bug 4):** "New open position is still present in the hyp-rec table" after navigation refresh repopulated the dashboard. The just-traded ticker should have been excluded from the hyp-recs panel.

**Static-read mechanism (orchestrator hypothesis; HIGH-CONFIDENCE — empirically confirm):**
- The just-shipped fix's `exclude_tickers` kwarg on `build_hyp_recs_section` is consumed only by `entry_post`'s OOB rebuild path.
- The full dashboard render path (`/` route handler → `build_dashboard` → `build_hyp_recs_section`) calls `build_hyp_recs_section` WITHOUT `exclude_tickers`.
- The `/hyp-recs/refresh` route similarly calls `build_hyp_recs_section` WITHOUT `exclude_tickers`.
- Net effect: hard-navigating to dashboard renders hyp-recs INCLUDING the just-traded ticker (because the open-trade exclusion is only applied during entry_post's OOB rebuild).

**Investigation tasks for Bug C:**
1. Confirm via grep: enumerate all `build_hyp_recs_section` call sites; verify which pass `exclude_tickers` and which don't.
2. Empirical reproduction: TestClient submit a hyp-recs entry; confirm OOB rebuild excludes ticker. Then GET `/`; confirm hyp-recs section INCLUDES the ticker. Discriminating: hyp-recs section content in the OOB chunk vs in the page-load response should DIFFER.

---

## §3 Investigation phase

For each bug class:

1. **Reproduce deterministically.** TestClient + assertions where possible; manual browser-DOM verification where TestClient is insufficient (Bug B is the likely candidate). Use logging instrumentation if needed.
2. **Capture evidence.** Response body, DOM state, intermediate variables, log lines. Each bug's evidence pinned to the return report.
3. **Identify mechanism.** Based on EMPIRICAL reproduction, NOT static-read plausibility. The hypothesis in §2 is starting input, NOT conclusion.
4. **Draft mechanism candidate message** per §4 template.

**Per the Bug 2 anti-pattern lesson (2026-04-25):** if static-read suggests mechanism X but empirical reproduction shows mechanism Y, the empirical evidence wins. Do NOT design fixes against the static-read hypothesis.

---

## §4 Operator-confirmation gate (BINDING)

After investigation phase completes for ALL THREE bugs, draft a return message containing the following per bug:

```
## Bug <X>: <name>

**Mechanism identified:** <concise; one paragraph>

**Reproduction sequence:** <step-by-step that triggers the bug>

**Evidence:**
  - Response body excerpt (relevant chunks).
  - DOM state before and after swap (if browser-verified).
  - Log lines / instrumentation output.
  - Any other empirical artifact.

**Confirmation request:** Does this match what you saw in production? Specifically:
  - <symptom 1>: <how mechanism explains it>
  - <symptom 2>: <how mechanism explains it>
  - <any anomaly that mechanism does NOT fully explain — flag explicitly>

If this matches, I'll proceed to design the fix. If your symptoms differ from what I describe, please clarify and I'll repeat investigation.
```

**Wait for operator confirmation before proceeding to fix phase.** If operator says "that's not what I see" for any bug, repeat investigation with new information. Do NOT design fixes until ALL THREE mechanisms are operator-confirmed.

---

## §5 Fix phase (after operator confirmation)

Standard TDD discipline. Each bug's fix in a separate task (or bundled where they share files; per implementer judgment + plan-rigor compounds discipline).

**Per-task TDD per orchestrator-context Binding conventions:**
- Failing test first → minimal implementation → passing test → commit.
- Discriminating-test discipline (per the canonical compounding-confound failure modes).
- Observable-verification subject-only grep BEFORE each task implementation commit:
  ```
  git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): bug-fix-<bug>'
  ```
- 4-tier commit-message convention. Bug-fix commits: `fix(area): <bug-id> — <description>`. Adversarial review-fix commits: `fix(area): Codex R<round> Major <id> — <description>`. Internal-Codex within-task: `(internal)` qualifier.
- Ruff baseline 91 unchanged; do NOT introduce new violations.

**After all fixes land**, invoke `copowers:adversarial-critic` on the combined diff. Iterate to `NO_NEW_CRITICAL_MAJOR`. Per the chart-pattern flag-v1 Phase 7 induced-bug pattern + 2026-04-29 hyp-recs writing-plans MAX_ROUNDS lesson, if final round produces findings that resolve, run ONE additional verification round.

**Critical discipline (per the just-captured 2026-04-29 JS-test-harness lesson):**
- TestClient assertions on response body are necessary BUT INSUFFICIENT.
- For Bug B specifically (HTMX swap-order / parsing): the fix MUST be verified by actually rendering the response in a browser AND observing post-swap DOM state. Either:
  - (a) Operator-witnessed manual verification before this dispatch declares "shippable" — surface in return report as an explicit operator-action item; OR
  - (b) Add a Playwright/Selenium browser-driven test for the affected paths (per the Bug 1 follow-up "JS-execution test harness gap"). Likely out-of-scope for this dispatch (would expand scope significantly); option (a) is more realistic.

---

## §6 Done criteria

- All three bugs operator-confirmed via §4 gate.
- All three bugs RESOLVED in fix phase.
- Adversarial Codex review terminates `NO_NEW_CRITICAL_MAJOR` with verification round if final round had findings.
- Per-bug discriminating tests added.
- **Operator-witnessed manual verification of the fixed workflow** (per the just-captured 2026-04-29 JS-test-harness lesson). Operator runs the same Phase 2 verification steps; reports clean. This dispatch is NOT considered shippable until operator-witnessed verification passes.
- Return report posted per §7.

---

## §7 Return report format

Post as final message:

```
## Hyp-recs Production Verification Bugs — Investigation-First Bug-Fix Return Report

### Investigation phase

**Bug A: Open-positions table never updates**
- Mechanism: <one paragraph>
- Reproduction: <step-by-step>
- Evidence: <pinned artifacts>
- Operator confirmation: <when received>

**Bug B: Watchlist disappears on entry submit**
- Mechanism: <one paragraph>
- Reproduction: <step-by-step>
- Evidence: <pinned artifacts>
- Operator confirmation: <when received>

**Bug C: exclude_tickers invariant too narrow**
- Mechanism: <one paragraph>
- Reproduction: <step-by-step>
- Evidence: <pinned artifacts>
- Operator confirmation: <when received>

### Fix phase

**Commit chain:** <first SHA> → <last SHA> on origin/main
**Total commits:** N (M task implementations + K Codex review-fixes + L cleanup)
**Codex rounds:** N rounds, terminating at NO_NEW_CRITICAL_MAJOR
**Fast-test count:** <count> at HEAD <SHA> (delta: +N from baseline 1309)

**Tasks completed:**
1. Bug A fix — <summary> (commit <SHA>)
2. Bug B fix — <summary> (commit <SHA>)
3. Bug C fix — <summary> (commit <SHA>)
... (per task; bundled tasks enumerated)

**Codex findings dispositioned:**
- R1: <count> Critical, <count> Major, <count> Minor — <breakdown>
- R2: ...
... (per round)

### Operator-action items

- Run `swing pipeline run` (so candidates + hyp-recs panel are populated).
- Click "Take this trade" on a hyp-rec; submit.
- Verify:
  1. Open-positions row appears in #open-positions table (NOT in hyp-recs <tbody>).
  2. Hyp-recs section refreshes; just-traded ticker is removed.
  3. Watchlist section persists correctly (entries do NOT disappear).
  4. Status-strip + open-positions + hyp-recs + watchlist all correctly populated.
  5. Hard-refresh dashboard; verify just-traded ticker is STILL absent from hyp-recs (Bug C fix).
- Repeat with watchlist-origin entry; verify same.
- Reply with PASS/FAIL per step.

**Open questions for orchestrator triage:**
- <any items the implementer flagged as needing operator/orchestrator decision>

**Recommended next step:** operator-witnessed manual verification per above. After PASS, Phase 2 closes; Phase 3 (OHLCV archive consolidation) becomes next dispatch.
```

---

## §8 If you get stuck

- **TestClient insufficient for reproducing Bug B** → use logging instrumentation in entry_post + manual browser DevTools verification. Operator can run the local web server and capture DevTools network/DOM state if needed.
- **Codex round count exceeds 5 without convergence** → STOP, surface in return report with the unresolved finding. Do NOT iterate indefinitely.
- **Final Codex round produces findings that resolve** → run ONE verification round to confirm clean before terminating (per induced-bug pattern + MAX_ROUNDS lesson).
- **Mechanism candidate doesn't reproduce empirically** → BACK to investigation; do NOT proceed. Per Bug 2 anti-pattern: testing plausible mechanisms instead of operator's actual reproduction is the canonical failure mode.
- **Bug B's mechanism turns out to require response-architecture rethink** (e.g., HTMX primary+OOB swap-order interaction is fundamentally incompatible with current response shape) → STOP, surface in return report with the architectural concern; operator decides whether to dispatch the rethink as separate scope.
- **Operator unavailable for confirmation gate within reasonable window** → pause investigation; flag in return report; resume when operator confirms.

---

## Appendix A: Why investigation-first

Per orchestrator-context "Anti-patterns": **"Bug-fix investigation that tests plausible mechanisms instead of operator's actual reproduction"** is a known failure mode. Bug 2 (2026-04-25) demonstrated this — implementer assumed a plausible form-submission ValueError mechanism, built a fix that was internally correct but addressed a different path than operator was hitting; required follow-up to fix the actual mechanism (sizing-hint span hx-target inheritance).

This dispatch carries three bugs with multiple plausible mechanisms each. Static-read suggestions in §2 are STARTING HYPOTHESES, not conclusions. Investigation-first protects against the Bug 2 failure mode.

## Appendix B: Cross-references

- **Just-shipped success-path fix executing-plans report** (in conversation history) — context for the bugs.
- **Just-shipped success-path fix plan:** `docs/superpowers/plans/2026-04-29-hyp-recs-success-path-fix-plan.md` (commit `844ed46`).
- **Bug 7 mixed-anchor family** (orchestrator-context Recent decisions 2026-04-25) — relevant to Bug B mechanism (e) cross-section interaction.
- **JS-execution test harness gap** (Bug 1 follow-up, orchestrator-context 2026-04-25) — this dispatch's bugs are the third occurrence of TestClient missing HTMX-driven UX failure.
- **Bug 2 anti-pattern** (orchestrator-context Anti-patterns) — directly applicable; protects against testing-plausible-mechanisms failure.
- **JS-test-harness-weighting lesson** (just-captured 2026-04-29) — generalization: HTMX-driven workflow plans need operator-witnessed verification OR browser-driven test harness.
- **ACCEPTED-with-rationale on production-facing surfaces lesson** (just-captured 2026-04-29) — Bug C is the canonical example.
- **HTMX OOB-swap partial drift gotcha** (CLAUDE.md) — relevant to Bug B mechanism investigation.
