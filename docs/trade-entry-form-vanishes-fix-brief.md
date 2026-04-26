# Trade Entry Form Vanishes Mid-Typing — Bug 2 Investigation + Fix Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Diagnose and fix Bug 2 reported by operator (2026-04-25, recurrence confirmed post-Bug-1-fix on commit `9aabe8b`): on the standalone `/watchlist` page (and, per architecture, also on the dashboard's embedded watchlist top-5 section), clicking a row's Enter button correctly shows the trade entry form, BUT when the operator adjusts the entry_price input to approximately the initial_stop value, the row collapses and the entry form disappears from the watchlist table until the page is refreshed. **The mechanism is not fully diagnosed yet** — Bug 1 (event propagation) is now fixed and confirmed; Bug 2 has a different root cause. **Investigation comes first; fix comes second.** Phase 3 only — no Phase 2 carve-out anticipated.
**Expected duration:** ~1 session (2-4 hours; majority is investigation, fix is likely small).
**Prepared:** 2026-04-25 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions (conventional commits, no-amend, no `--no-verify`, no Claude co-author footer, Phase isolation, TDD, fast suite must stay green). Particularly the HTMX OOB-swap gotcha and HTMX `responseHandling` config override (`base.html.j2:15-19` enables 4xx swapping via `[45]..` rule).
2. `docs/watchlist-enter-button-event-propagation-fix-brief.md` — the just-shipped Bug 1 brief. Contextual; explains the click-event-propagation issue that was the FIRST symptom but is now resolved. Bug 2 is a SEPARATE mechanism.
3. `swing/web/templates/partials/trade_entry_form.html.j2` — the form template you'll be debugging. Read end-to-end (68 lines). Pay particular attention to:
   - Lines 6-8: form's `hx-post="/trades/entry"`, `hx-target="closest tr"`, `hx-swap="outerHTML"` (no explicit `hx-trigger`; defaults to `submit`).
   - Lines 14-16: entry_price input (`type="number" step="0.01" min="0" name="entry_price"`).
   - Lines 20-32: sizing-hint span with `hx-get="/trades/entry/sizing-hint"`, `hx-trigger="change from:input[name=entry_price],input[name=initial_stop] delay:200ms"`, `hx-include="closest form"`, `hx-swap="outerHTML"`.
   - Lines 33-35: initial_stop input.
4. `swing/web/templates/partials/sizing_hint.html.j2` — the partial returned by `/trades/entry/sizing-hint`. Renders `<span id="sizing-hint" class="sizing-hint">...</span>` with three modes (numbers / dim guidance / fallback). Should swap into the sizing-hint span only.
5. `swing/web/routes/trades.py` — the route handlers. Especially `sizing_hint()` at line 135-198 (always returns 200 with sizing_hint partial), and the entry POST handler (further down — find it via grep). Verify what the entry POST returns under various conditions; rule-out theory: maybe the form's hx-post is firing unexpectedly somehow, returning an error fragment that replaces the form.
6. `swing/web/templates/partials/trade_form_error.html.j2` — the fallback error fragment. What does it look like? Could it be returning markup that "collapses" the row?
7. `swing/web/templates/base.html.j2` — review the `htmx.config.responseHandling` override (lines 15-19). Particularly the `[45]..` rule that enables swap on 4xx/5xx responses.

**Skill posture.**
- DO invoke `superpowers:systematic-debugging` — Bug 2 is a "bug, test failure, or unexpected behavior" with unclear mechanism; the skill is designed for exactly this scenario.
- DO invoke `superpowers:verification-before-completion` before declaring done.
- DO invoke `copowers:adversarial-critic` after the fix commit lands. Watch items in §6.
- Do NOT invoke `copowers:brainstorming` or `copowers:writing-plans` — scope is fully specified by this brief.

---

## 1. Symptom (verbatim from operator)

> "I am in the watchlist and click the enter button, the correct fields show, but when I adjust the price to what the stop value is, the row collapses and that entry disappears from the watchlist table until I refresh."

**Recurrence confirmed 2026-04-25 post-Bug-1-fix** — Bug 1's fix (`onclick="event.stopPropagation()"` on the Enter button) resolved the click-event-propagation race that caused operator to sometimes see the expanded view instead of the entry form. Bug 2 is a separate mechanism: entry form does correctly appear, but vanishes when entry_price is adjusted to approximately the initial_stop value.

**Specific reproduction conditions:**
- Click Enter on a watchlist row → entry form appears (post-Bug-1-fix; reliably now)
- In the entry_price input field, type/adjust the value to approximately equal the initial_stop value
- Wait briefly (sizing-hint trigger has `delay:200ms`)
- Form vanishes; row is gone from the watchlist table; refresh restores the watchlist row

---

## 2. Hypotheses to investigate

These are starting hypotheses derived from code reading. The implementer should test each, RULE IN or RULE OUT, and report findings. Do NOT assume a hypothesis is correct without empirical verification per `superpowers:systematic-debugging` discipline.

### Hypothesis A: sizing-hint response somehow replaces the entire form, not just the sizing-hint span

- **Mechanism:** `<span id="sizing-hint" hx-get="/trades/entry/sizing-hint" hx-swap="outerHTML">`. The default `hx-target` (when not specified) is the element itself. So outerHTML should replace just the span. UNLESS HTMX targeting is being misled (e.g., by hx-include or by some response header).
- **How to investigate:** open browser dev tools → Network tab. Click Enter button. Adjust entry_price to match initial_stop. Observe the sizing-hint XHR request and its response. Verify response is the expected `<span id="sizing-hint">...</span>`. Then verify in the Elements tab whether the swap targets the span only or the whole form/tr.
- **What rule-out looks like:** the network request shows the expected response body AND the swap correctly replaces only the span.
- **What rule-in looks like:** the request response has unexpected content OR swaps an unintended target.

### Hypothesis B: form submission fires unexpectedly (entry POST is being triggered by input change)

- **Mechanism:** form has `hx-post="/trades/entry"` with no explicit `hx-trigger`. HTMX default for forms is `submit`. Change events on inputs SHOULD NOT trigger form submission. UNLESS the operator hits Enter while in an input field (HTML default behavior submits the form) OR some other path fires the submit event.
- **How to investigate:** open dev tools → Network tab. Click Enter button. Adjust entry_price slowly. Watch for any `POST /trades/entry` request firing. If it fires, examine its response — likely a 400 with `_rerender_entry_form_with_error` OR the `trade_form_error.html.j2` fallback, which might "collapse" the row visually.
- **What rule-out looks like:** no POST `/trades/entry` request fires during input adjustment.
- **What rule-in looks like:** a POST fires unexpectedly. Investigate WHY — possibly a form-level event handler, possibly browser-specific Enter-key behavior, possibly an HTMX trigger configuration issue.

### Hypothesis C: sizing-hint endpoint returns 4xx/5xx that gets swapped per the responseHandling override

- **Mechanism:** `base.html.j2` has `htmx.config.responseHandling = [..., {code: "[45]..", swap: true, error: true}]`. If the sizing-hint endpoint somehow returns a 4xx/5xx status when entry_price ≈ initial_stop, the response body (which might be empty or malformed) would swap into the sizing-hint span — possibly leading to broken DOM that effectively "collapses" the form.
- **How to investigate:** check the sizing-hint route handler at `swing/web/routes/trades.py:135-198`. Verify all return paths use status_code=200 (the default for `templates.TemplateResponse`). The route's docstring says "Always 200" — verify this is empirically true under all input conditions, especially `stop >= entry`.
- **What rule-out looks like:** sizing-hint always returns 200 with the sizing_hint partial.
- **What rule-in looks like:** under specific input conditions, sizing-hint returns 4xx/5xx.

### Hypothesis D: hx-include="closest form" leaks form data including unexpected fields

- **Mechanism:** sizing-hint span has `hx-include="closest form"`. This includes ALL form fields' current values in the GET request to sizing-hint. The route only consumes `entry_price` and `initial_stop`, but the request URL would contain everything (entry_date, ticker, shares, rationale, notes, watchlist_target, watchlist_stop, hidden inputs).
- **How to investigate:** in dev tools Network tab, examine the GET request URL/params when sizing-hint fires. Check if any field has a value that might cause server-side issues (e.g., empty rationale, malformed entry_date).
- **What rule-out looks like:** form data is well-formed; sizing-hint route consumes only entry_price/initial_stop and ignores the rest.
- **What rule-in looks like:** the route mishandles unexpected fields somehow.

### Hypothesis E: race or timing issue between the sizing-hint request and a later interaction

- **Mechanism:** the sizing-hint hx-trigger has `delay:200ms`. If the operator changes the price field, the timer starts. If they change again within 200ms, the timer resets. Once 200ms passes with no further changes, the request fires. The request then takes some network time. During that window, the operator might be doing other things that interact unexpectedly.
- **How to investigate:** observe the sequence of events in dev tools. Look for overlapping requests, delayed responses, or unexpected event handlers firing.
- **What rule-out looks like:** event sequence is well-behaved.
- **What rule-in looks like:** specific timing pattern reproducibly causes the bug.

### Hypothesis F: browser-specific behavior (e.g., autofill, autocomplete, validation popup)

- **Mechanism:** browser auto-features might fire unexpected events that interact with HTMX or form state.
- **How to investigate:** test in a clean browser session (incognito mode, no extensions) to rule out interference.
- **What rule-out looks like:** bug reproduces in clean session; not browser-specific.
- **What rule-in looks like:** bug doesn't reproduce in clean session; environmental.

---

## 3. Scope

### In scope (Phase 3 only)

- **Investigation:** systematic-debugging-skill driven diagnosis of Bug 2's mechanism. RULE IN or RULE OUT each hypothesis (A-F) above. Document findings in the return report.
- **Fix:** once mechanism is identified, the minimal fix to address it. Likely candidates:
  - HTMX configuration adjustment on the sizing-hint span (e.g., explicit `hx-target` to scope the swap)
  - Form structure adjustment (e.g., explicit `hx-trigger` on the form to prevent unintended submission)
  - Route handler adjustment (e.g., better handling of edge-case inputs)
  - Other (depends on findings)
- **Test:** failing test that reproduces the bug + passes after fix. May be a Python-level template test (assert specific HTML attributes are present) OR a route-level test (assert specific HTTP behavior). DO NOT add Playwright/Selenium — the project has no JS test harness and adding one for this is overkill (per Bug 1's adversarial review acceptance).

### Out of scope

- Structural refactor of the watchlist row architecture (per Bug 1's flagged Major 1 about "brittle parent-tr-as-catch-all-click-target" — that's a separate phase3e item).
- Adding a JS test harness (Playwright/Selenium) — out of scope per Bug 1's adversarial review.
- Any change to Bug 1's just-shipped fix (`9aabe8b`).
- Any change to other event-propagation patterns in the codebase.
- Modification of `base.html.j2`'s `responseHandling` config (unless investigation specifically identifies it as the root cause; if so, flag the change clearly).
- Any UI redesign of the entry form.

---

## 4. Binding conventions

- **Branch:** `main`. No feature branch.
- **Commits:** conventional. **No Claude co-author footer. No `--no-verify`. No amending.**
- **TDD:** failing test first → see fail → minimal implementation → see pass → commit. The test should empirically distinguish pre-fix from post-fix per `feedback_regression_test_arithmetic.md`.
- **Tests:** `python -m pytest -m "not slow" -q` must stay green. Baseline 970 passing as of `9aabe8b`. Trust pytest output.
- **Phase isolation:** Touch `swing/web/` only (templates and/or routes). NO Phase 2 modifications.
- **Investigation discipline (from `superpowers:systematic-debugging`):** form a hypothesis BEFORE testing; each test produces evidence that rules in or out a hypothesis; do not speculate-fix.

---

## 5. Task structure

### 5.1 Investigation phase

Before writing any code:

1. Reproduce the bug locally. Run `swing web` to start the dashboard. Open `http://127.0.0.1:8080/watchlist`. Click Enter on a row (DHC if present, or any other watchlist row). Observe the form. Adjust entry_price to approximately the initial_stop value. Observe the symptom.
2. Open browser dev tools (Network + Elements + Console tabs).
3. Walk through hypotheses A-F in §2; collect evidence for each.
4. Identify the actual mechanism with confidence (no speculation).
5. **Document findings before proceeding to fix.** This is the systematic-debugging discipline; the investigation log goes in the return report.

### 5.2 Fix phase

Once mechanism is identified:

1. Design the minimal fix. The fix should address the specific mechanism, not the surface symptom.
2. Write a failing test that reproduces the bug at whichever layer is appropriate (template assertion, route response assertion, etc.).
3. Implement the minimal fix.
4. Verify test passes; run full fast suite.
5. Commit.

Commit message format:
```
fix(web): <one-line summary of mechanism + fix>

Bug 2 reported by operator (2026-04-25, recurrence confirmed post-Bug-1
on 9aabe8b): <symptom description>.

Investigation identified <mechanism>. Fix: <description of fix>.

Operator manual verification post-merge.
```

### 5.3 Operator manual verification

After fix lands and adversarial review passes, document the manual-test steps for the operator in the return report. The pattern:

1. Open watchlist page
2. Click Enter on a row
3. Adjust entry_price to approximately the initial_stop value
4. Wait > 200ms
5. Expected: form remains visible; sizing-hint span shows dim guidance ("Enter a valid entry price and stop..."); operator can continue editing
6. Pre-fix: form vanished
7. Post-fix: form persists
8. Repeat on the dashboard's embedded watchlist top-5 section to verify cross-surface coverage

---

## 6. Adversarial review (post-fix)

After the fix commit lands, invoke `copowers:adversarial-critic` on the diff. Iterate to `NO_NEW_CRITICAL_MAJOR`. **Specific watch items:**

- **Mechanism vs symptom.** Verify the fix addresses the actual root cause identified in investigation, not just the surface symptom. A fix that "makes the bug go away" without understanding why is brittle.
- **Edge cases.** What other input patterns (entry_price > initial_stop normally; entry_price ≪ initial_stop; entry_price = 0; non-numeric input; etc.) interact with the fix? Verify no regressions introduced.
- **Cross-surface coverage.** Both the dashboard's embedded watchlist top-5 AND the standalone /watchlist page use the same entry form template. Verify the fix applies to both (it almost certainly does since the template is shared, but confirm).
- **Test correctness per feedback_regression_test_arithmetic.md.** Verify the failing test FAILS on pre-fix code and PASSES on post-fix code. The assertion should distinguish the two states meaningfully.
- **Bug 1 fix preservation.** Verify the just-shipped Bug 1 fix (`onclick="event.stopPropagation()"` on the Enter button) is unchanged.

If review finds major issues, fix in NEW commit per no-amend rule. Minor findings either fix in same follow-up or `ACCEPT-with-rationale`.

---

## 7. Done criteria

- Investigation phase complete; mechanism identified with empirical evidence.
- Fix designed to address root cause (not just surface symptom).
- Failing test verified to FAIL on pre-fix code; PASSES post-fix.
- Fix commit landed.
- Adversarial review verdict `NO_NEW_CRITICAL_MAJOR` (or fixes landed for any majors).
- Fast suite green (no regressions; new test count incremented appropriately).
- Operator manual verification steps documented in return report.
- Return report produced per §8.

---

## 8. Return report format

```
## Trade entry form vanishes mid-typing — return report

### Investigation findings
- Mechanism identified: <description of root cause with evidence>
- Hypotheses ruled IN: <list>
- Hypotheses ruled OUT: <list with brief reason for each>
- Browser dev-tools observations: <key network/dom observations>

### Commits landed
- <SHA1> fix(web): <summary>
- <SHA2+> (if any) adversarial review fixes

### Fix description
- What changed: <description>
- Why this addresses the root cause (not surface symptom): <reasoning>
- Edge cases considered: <list>

### Tests
- Before: 970 passing
- After: <N> passing, 0 failing. New tests: <count>.
- Pre-fix verification: confirmed the new test FAILS on the unmodified code; PASSES post-fix.

### Adversarial review verdict
- <NO_NEW_CRITICAL_MAJOR | findings summary if any>

### Manual verification steps for operator
- <Detailed step-by-step verification procedure for both /watchlist standalone page AND dashboard embedded top-5>

### Cross-surface coverage check
- Dashboard's embedded watchlist top-5 fix coverage: <yes/no, with reasoning>
- Standalone /watchlist page fix coverage: <yes/no, with reasoning>

### Deviations from brief
- <Empty if none.>

### Open questions for orchestrator
- <Empty if none.>
```

---

## 9. If you get stuck

- **If you can't reproduce the bug locally** despite trying multiple input patterns: do NOT assume the bug is fixed. Try a different browser, different entry-price values (e.g., exactly equal to initial_stop, slightly below, slightly above). Try different initial_stop values. Document all reproduction attempts in the return report. If genuinely cannot reproduce, return with detailed environment info and ask the operator for theirs.
- **If investigation reveals the mechanism is in `base.html.j2` `responseHandling` config:** that's a sensitive global; the fix may need to be a per-element override rather than a global change. Flag the design choice in the return report.
- **If the fix requires touching the sizing-hint route handler `swing/web/routes/trades.py`:** Phase 3 web-layer change is allowed; just confirm the route's contract docstring at line 141-148 ("Tolerant sizing-hint endpoint... Always 200") remains accurate post-fix.
- **If you discover the bug requires multi-file changes** that exceed reasonable single-fix scope: STOP and flag in return report. Do not silently expand to a multi-file refactor.
- **If browser dev tools show the bug is environmental (browser-specific, extension-related, etc.):** document the environment dependency. The fix may be "tighten HTMX usage to be more browser-agnostic" rather than addressing a server-side mechanism.
- **If the bug turns out to be a known HTMX issue or library quirk:** check HTMX's GitHub issues; document the upstream issue link in the return report. The fix may be a workaround rather than a cure.
