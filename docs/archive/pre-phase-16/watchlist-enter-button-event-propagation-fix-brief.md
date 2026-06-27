# Watchlist Enter-Button Event-Propagation Fix — Bug 1 Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Fix Bug 1 reported by operator (2026-04-25): clicking the Enter button on a watchlist row sometimes shows the expanded view (with no actionable inputs) instead of the trade entry form. Root cause is HTMX click-event propagation — the button click bubbles to the parent `<tr>` which has its OWN `hx-get="/watchlist/<ticker>/expand"` handler, triggering both requests simultaneously and racing on which response wins the `outerHTML` swap. Single-file fix: stop the Enter button's click from bubbling. Phase 3 only — no Phase 2 carve-out needed.
**Expected duration:** ~30-45 minutes.
**Prepared:** 2026-04-25 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions (conventional commits, no-amend, no `--no-verify`, no Claude co-author footer, Phase isolation, TDD, fast suite must stay green). Particularly the HTMX OOB-swap gotcha and HTMX `responseHandling` config override.
2. `swing/web/templates/partials/watchlist_row.html.j2` — the file you're editing (28 lines). Read end-to-end. Notice that the row `<tr>` (lines 2-4) has `hx-get="/watchlist/<ticker>/expand"` configured; this fires on click (HTMX default trigger). The Enter button (lines 24-26) has its own `hx-get="/trades/entry/form?ticker=<ticker>"`. **Both target `closest tr` with `outerHTML` swap.** When the operator clicks the button, the click event ALSO bubbles to the parent `<tr>`, triggering its `hx-get` simultaneously.
3. `swing/web/templates/partials/watchlist_expanded.html.j2` — the partial returned by `/watchlist/<ticker>/expand`. Notice it produces a `<tr id="watchlist-row-<ticker>" class="expanded">` with no actionable inputs (just a "Log entry (CLI — 3b adds button)" placeholder text on line 33).
4. `swing/web/templates/partials/trade_entry_form.html.j2` — the partial returned by `/trades/entry/form`. Produces a `<tr id="entry-form-<ticker>">` containing the form. This is what the operator wants to see when they click Enter.
5. `swing/web/routes/trades.py` — to verify the `/trades/entry/form` route returns the entry form partial. (Read-only check; no modification.)
6. `swing/web/routes/watchlist.py` (or wherever the `/watchlist/<ticker>/expand` route lives) — to verify the expand route returns the expanded partial. (Read-only check; no modification.)

**Skill posture.**
- DO invoke `superpowers:verification-before-completion` before declaring done.
- DO invoke `copowers:adversarial-critic` after the fix commit lands. Standing convention; even small fixes get one adversarial pass. Iterate to `NO_NEW_CRITICAL_MAJOR`. Watch items in §5.
- Do NOT invoke `copowers:brainstorming` or `copowers:writing-plans` — scope is fully specified by this brief.

---

## 1. Strategic context (compressed)

The operator (2026-04-25) reported being unable to enter trades from either the dashboard or the standalone `/watchlist` page. Symptoms: clicking the row's Enter button sometimes shows an expanded view (chart + criteria + "Log entry CLI" placeholder) instead of the entry form. The expanded view has no input fields, so the operator can't proceed with the trade.

The root cause was diagnosed in conversation: HTMX click-event propagation. Both surfaces (`partials/watchlist_top5_section.html.j2` for the dashboard's embedded top-5, and `templates/watchlist.html.j2` for the standalone page) include `partials/watchlist_row.html.j2`. Fixing this one file fixes both surfaces simultaneously.

**This is operationally urgent** — operator has Monday market opening and is taking hypothesis-tagged trades (per `docs/orchestrator-context.md` 2026-04-25 framework framing). The CLI-direct workaround works (`swing trade entry --ticker XYZ ...`) but adds friction to the workflow that the dashboard surface was supposed to eliminate.

A separate Bug 2 (entry form vanishes mid-typing when entry_price ≈ initial_stop) was also reported but is OUT OF SCOPE for this brief. Bug 2 may share root cause (event propagation) or may have a different mechanism; needs separate investigation. Do NOT attempt to fix Bug 2 here.

---

## 2. Scope

### In scope (Phase 3 only)

- **Single-file edit:** `swing/web/templates/partials/watchlist_row.html.j2`. Add an event-propagation stop to the Enter button (lines 24-26) so clicking it does NOT also trigger the parent `<tr>`'s `hx-get` for expand.
- **Single test:** add a unit/template test that asserts the rendered Enter button HTML contains the event-propagation-stop attribute. Filename: `tests/web/test_templates_watchlist_row.py` (new) OR add to an existing test file if there's a natural home for watchlist-template tests.
- **Manual verification:** operator will manually verify in browser post-merge; document the verification steps in the return report.

### Out of scope

- **Bug 2 (entry form vanishes mid-typing).** Different symptom; may share root cause or may not. Separate investigation. If you discover during this fix that the same propagation issue causes Bug 2, FLAG in the return report — do NOT silently expand scope.
- Any changes to `watchlist_expanded.html.j2`, `trade_entry_form.html.j2`, or any route handler.
- Any changes to other event-propagation patterns elsewhere in the codebase. If you find similar nested-clickable patterns, FLAG in return report.
- Any HTMX configuration changes in `base.html.j2`.
- The pre-existing "Log entry (CLI — 3b adds button)" placeholder in `watchlist_expanded.html.j2` line 33 is a known UX gap (Phase 3e §3e.5); leave it alone.

---

## 3. Binding conventions

- **Branch:** `main`. No feature branch.
- **Commits:** conventional. **No Claude co-author footer. No `--no-verify`. No amending.**
- **TDD:** failing test first → see fail → minimal implementation → see pass → commit.
- **Tests:** `python -m pytest -m "not slow" -q` must stay green. Baseline is 969 passing as of `7ab5497`. Trust pytest output.
- **Phase isolation:** Touch `swing/web/templates/partials/watchlist_row.html.j2` and the new test file ONLY. No other file modification.

---

## 4. Task specification

### 4.1 Failing test first

Create `tests/web/test_templates_watchlist_row.py` (or extend a relevant existing test if one exists for watchlist row rendering). The test should:

- Render the `partials/watchlist_row.html.j2` template with a synthetic `WatchlistEntry` and minimal context (no real DB needed).
- Assert that the Enter button HTML contains a click-event-propagation-stop attribute.

Acceptable patterns for the stop (either is fine; pick one and document the choice):

**Option A (vanilla JS attribute):**
```html
<button onclick="event.stopPropagation()"
        hx-get="/trades/entry/form?ticker={{ w.ticker }}"
        ...>Enter</button>
```

**Option B (HTMX-native event handler):**
```html
<button hx-on:click="event.stopPropagation()"
        hx-get="/trades/entry/form?ticker={{ w.ticker }}"
        ...>Enter</button>
```

I'd lean toward Option A (vanilla JS, more universally understood, doesn't require HTMX knowledge to read) but Option B is also defensible (HTMX-native, consistent with the rest of the row's HTMX-heavy markup). Implementer's call; document the choice in the test assertion.

The test assertion should look for the literal string `stopPropagation` in the rendered button HTML. That's strict enough to catch the fix being present and loose enough to accept either Option A or Option B.

**Verify the test fails on the unmodified template before implementing the fix.** Per `feedback_regression_test_arithmetic.md` discipline.

### 4.2 Minimal implementation

Edit `swing/web/templates/partials/watchlist_row.html.j2` lines 24-26. Add the event-propagation-stop attribute to the Enter button. Keep all existing attributes intact (`hx-get`, `hx-target`, `hx-swap`, `hx-headers`).

Run the test → it should pass.

Run the full fast suite: `python -m pytest -m "not slow" -q` → no regressions.

### 4.3 Commit

```
fix(web): stop Enter button click from bubbling to parent watchlist row

Bug 1 reported by operator (2026-04-25): clicking the Enter button on
a watchlist row sometimes showed the expanded view instead of the trade
entry form. Root cause: the row <tr> has hx-get="/watchlist/<ticker>/expand"
configured (default click trigger); the Enter button's click bubbled to
the parent, triggering both HTMX requests simultaneously and racing on
which response wins the outerHTML swap. The expanded partial has no
actionable inputs, so when it won the race the operator was blocked
from completing the trade entry.

Fix: add event-propagation-stop to the Enter button so its click does
not also trigger the row's expand handler. Single-file change in
swing/web/templates/partials/watchlist_row.html.j2; affects both
dashboard top-5 and standalone /watchlist page (both include the same
partial).

Operator manually verified post-merge.
```

(Adjust commit body wording if Option B was chosen instead.)

---

## 5. Adversarial review

After the fix commit lands, invoke `copowers:adversarial-critic` on the diff. Iterate to `NO_NEW_CRITICAL_MAJOR`. **Specific watch items:**

- **Cross-surface coverage.** Verify both `partials/watchlist_top5_section.html.j2` (dashboard embedded) and `templates/watchlist.html.j2` (standalone) include `partials/watchlist_row.html.j2`. The single-file fix should resolve the bug on both surfaces. If either surface uses a different row template, the fix is incomplete — FLAG.
- **Other event-propagation patterns.** Check the codebase for other nested-clickable patterns (`grep -rn 'hx-get' swing/web/templates/` and look for `<tr>`s with hx-get that contain `<button>`s with hx-get). If others exist, FLAG in return report — do NOT fix in this commit (out of scope per §2). The watchlist_row pattern is the one operator hit; others may need similar fixes but are separate dispatches.
- **HTMX request behavior verification.** With the fix in place, clicking Enter should fire ONLY the button's hx-get (form fetch), not the row's hx-get (expand fetch). Verify by reading HTMX docs or by reasoning about event propagation — the fix's correctness should be self-evident from the code change, but worth verifying mentally.
- **Test correctness per feedback_regression_test_arithmetic.md.** Verify the test FAILS on pre-fix code and PASSES on post-fix code. The assertion should distinguish the two states meaningfully.
- **Existing test impact.** No existing tests should break. If any do, the fix has unintended consequences worth investigating.

If review finds major issues, fix in NEW commit per no-amend rule. Minor findings either fix in same follow-up or `ACCEPT-with-rationale`.

---

## 6. Done criteria

- New test asserts event-propagation-stop is present in the Enter button HTML.
- `swing/web/templates/partials/watchlist_row.html.j2` Enter button now has `onclick="event.stopPropagation()"` OR `hx-on:click="event.stopPropagation()"` attribute.
- Test passes on post-fix code; verified to fail on pre-fix code.
- Fast suite green at 970+ passing (969 baseline + 1 new test). No regressions.
- Adversarial review verdict `NO_NEW_CRITICAL_MAJOR` (or fixes landed for any majors).
- Conventional commit on `main` (no amend, no co-author).
- Return report produced per §7.

---

## 7. Return report format

```
## Watchlist Enter-button event-propagation fix — return report

### Commit landed
- <SHA1> fix(web): stop Enter button click from bubbling to parent watchlist row
- <SHA2+> (if any) adversarial review fixes

### Implementation choice
- Option A (vanilla onclick) | Option B (hx-on:click) — chose <X> because <reasoning>

### Tests
- Before: 969 passing
- After: <N> passing, 0 failing. New tests: 1 (event-propagation-stop assertion).
- Pre-fix verification: confirmed the new test FAILS on the unmodified template; PASSES post-fix.

### Adversarial review verdict
- <NO_NEW_CRITICAL_MAJOR | findings summary if any>

### Cross-surface coverage check
- partials/watchlist_top5_section.html.j2 includes watchlist_row.html.j2: <yes/no>
- templates/watchlist.html.j2 includes watchlist_row.html.j2: <yes/no>
- (If either is no, the fix is incomplete; flag.)

### Other event-propagation patterns discovered
- (List any other `<tr hx-get="...">` containing `<button hx-get="...">` patterns elsewhere in templates. Do NOT fix in this commit; flag for separate dispatch.)

### Manual verification steps for operator
- Open dashboard at http://127.0.0.1:8080/
- Locate a watchlist top-5 row
- Click the Enter button
- Expected: trade entry form (`<tr id="entry-form-<ticker>">` with input fields) replaces the row consistently
- Repeat 3-5 times to verify the race condition is gone (pre-fix, sometimes the expanded view showed; post-fix, only the entry form should show)
- Repeat on the standalone /watchlist page

### Deviations from brief
- <Empty if none.>

### Open questions for orchestrator
- <Empty if none. Operator may still hit Bug 2 (entry form vanishes mid-typing); that's a separate dispatch.>
```

---

## 8. If you get stuck

- **If `tests/web/test_templates_*.py` doesn't exist as a pattern in the codebase:** check `tests/web/test_view_models/` and `tests/web/test_routes/` to see how watchlist tests are structured. Place the new test in the most natural location; document the choice. If creating a new file, follow the project's test-naming convention.
- **If you find that the test framework can't render the partial in isolation** (e.g., it requires a full FastAPI test client + route): use the test client and assert against the rendered HTML response from the route that includes the row. Less ideal but functional.
- **If `hx-on:click` syntax (Option B) doesn't work as expected:** Option A (`onclick="event.stopPropagation()"`) is the safer fallback. HTMX 2.x supports `hx-on:click` but requires correct quoting; vanilla `onclick` works universally.
- **If Bug 2 surfaces during your testing** (e.g., you happen to type a value into the entry form during manual verification and the form vanishes): note in the return report but do NOT fix. Bug 2 is a separate dispatch.
- **If you find that the fix doesn't resolve the operator's reported symptom on manual test:** the diagnosis may be incomplete. Flag in return report with the specifics of what you observed; do NOT speculate-fix or scope-expand.
