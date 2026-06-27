# QoL UI-Polish Bundle Brief

**Audience:** Fresh Claude Code instance with no prior conversation context. You are the implementer; the orchestrator drafted this brief and will receive your return report.

**Mission:** Ship seven small UI / UX fixes as a single sequential session. All items are bounded, well-scoped, and individually low-risk. They are bundled to amortize startup cost — but each task gets its own TDD red-green-commit cycle.

**Expected duration:** ~4–5 hours including TDD + adversarial review.

---

## §0 — Read first

Read these in order before touching code:

1. **`CLAUDE.md`** at repo root — current-state context, conventions, gotchas. **Pay particular attention to:**
   - HTMX OOB-swap partial drift gotcha (relevant for 3e.4)
   - Base-layout shared-VM gotcha (relevant for 3e.1 if you add fields to `StatusStripVM`)
   - HTMX 4xx fragments need explicit config override (relevant context for Bug 2 task)
2. **`docs/phase3e-todo.md`** §"2026-04-25 Bug 2 follow-ups" — the `_handle_any` defense-in-depth context. The Bug 2 root-cause fix-history note explains why this defense matters.
3. **`swing/web/app.py`** — read `_register_exception_handlers`, `_handle_http_exc`, `_handle_any`, and `_is_row_swap_target`. The Bug 2 task mirrors the row-target awareness `_handle_http_exc` already has.
4. **`swing/web/view_models/dashboard.py`** — `DashboardVM`, `StatusStripVM`, `HypothesisRecommendation`, `build_dashboard`. Multiple tasks touch these.

## §0 — Skill posture

- **Use** `superpowers:test-driven-development` for each task — failing test first, minimal implementation, pass, commit.
- **Use** `copowers:adversarial-critic` on the combined diff after all tasks commit, iterate to `NO_NEW_CRITICAL_MAJOR`, fix findings in new commits per no-amend rule. Standing convention.
- **Do NOT use** `superpowers:brainstorming` — scope is fully specified.
- **Do NOT use** `superpowers:writing-plans` — this brief IS the plan.

---

## Strategic context (compressed)

This is operational polish, not strategic work. The Swing Trading project's hypothesis-investigation engine shipped 2026-04-25; the operator is now using the dashboard daily. These items address small UX gaps the operator surfaced during real-world use. Bug 2 `_handle_any` is defense-in-depth following yesterday's investigation lesson (the Bug 2 root-cause was sizing-hint hx-target inheritance, but the original investigation found a parallel `_handle_any` gap that's worth closing now while the context is fresh).

Project baseline as of brief drafting: `4614049` on `main`, **969 fast tests passing**.

---

## Scope

### In scope (7 tasks)

| ID | Item | Est. |
|---|---|---|
| T1 | QoL #1 — Alternating row backgrounds (CSS) | ~15 min |
| T2 | 3e.5 — Remove stale "Log entry (CLI — 3b adds button)" placeholder | ~10 min |
| T3 | QoL #3 — Pivot price column in hypothesis-recommendations table | ~30–45 min |
| T4 | 3e.1 — Mark-to-market unrealized P&L on Account card | ~45 min |
| T5 | 3e.3 — `POST /prices/refresh` also resets OHLCV breaker | ~30 min |
| T6 | 3e.4 — Watchlist row collapse via dedicated close button | ~45 min |
| T7 | Bug 2 `_handle_any` HX-Target-aware fragment selection | ~45 min |

### Out of scope

- **Watchlist sort-order change.** That is dispatched as a separate session immediately after this one returns. Do NOT modify `_sort_by_proximity` or `flag_tags` ordering.
- **Hypothesis-recommendations table sort.** Untouched in both this session AND the follow-up — operator decision recorded.
- **Phase 2 carve-outs.** None of these tasks should touch `swing/trades/` or `swing/data/`. If you find yourself wanting to, stop and flag — your task is mis-scoped.
- **Watchlist row HTMX trigger architecture refactor** (Bug 1 follow-up Option A/B). Out of scope; logged in `phase3e-todo.md`.
- **Sizing-hint hx-trigger parsing bug** (Bug 2 follow-up). Out of scope.
- **Tag precedence ordering for sort** — that is Session 2's concern.

---

## Binding conventions

- **Branch:** `main`. No feature branches.
- **Commits:** conventional. **No Claude co-author footer. No `--no-verify`. No amending.** One commit per task (red-green-commit), plus separate commits for adversarial-review fixes.
- **TDD:** failing test first → see fail → minimal implementation → see pass → commit. Per task.
- **Tests:** `python -m pytest -m "not slow" -q` — must stay green at end. The full suite is currently 969 passing.
- **Ruff:** `ruff check swing/` baseline is 81 errors (pre-existing). Don't introduce new violations; don't try to fix the baseline incidentally.
- **Phase 2 isolation:** `swing/trades/` and `swing/data/` are read-only for this session.
- **Adversarial review:** mandatory on the combined diff after T1–T7 commit. See §"Adversarial review" below.

---

## Per-task specifications

### T1 — QoL #1: Alternating row backgrounds

**File:** `swing/web/static/app.css`

**Change:** Add a single CSS rule that gives every `<tbody>` row even/odd visual distinction. The rule must NOT defeat the existing `tr.tripwire-fired td` rule which already paints hypothesis-recommendation rows red.

**Implementation:**
```css
/* Visual distinction for alternating rows in any table. Source order matters:
   the tripwire-fired rule below this declaration wins on equal specificity. */
tbody tr:nth-child(even) td { background: #f7f7f7; }
```

Place this rule **above** the existing `tr.tripwire-fired td { background: #ffe6e6; ... }` block (currently lines 28–29). Source-order resolution at equal specificity means tripwire-fired rows still render red.

**Acceptance criteria:**
- Visit dashboard in a browser; alternating rows on the watchlist top-5, open positions, hypothesis-recommendations, and today-decisions tables all have distinct backgrounds.
- A tripwire-fired hypothesis row is still painted red, not light gray.
- No new ruff or test failures.

**Test:** No automated test required (pure cosmetic; project lacks a JS / DOM-rendering test harness — see `phase3e-todo.md` Bug 1 follow-ups). **Briefly verify in a running `swing web` session; document this in the return report.**

**Commit message:** `style(web): alternating row backgrounds for visual distinction`

---

### T2 — 3e.5: Remove stale "Log entry" placeholder

**File:** `swing/web/templates/partials/watchlist_expanded.html.j2`

**Change:** Remove the literal placeholder text `Log entry (CLI — 3b adds button)` (line 33) and its surrounding `<div class="actions">` wrapper (which is now empty after removal). The CLI command is documented elsewhere; the placeholder hasn't shipped its button and is misleading.

**Acceptance criteria:**
- Expanded watchlist row no longer renders the placeholder string.
- Existing tests still pass; no test should specifically assert on the placeholder string (verify via grep before deleting).

**Test:** Grep the test suite for the placeholder string before deletion (`grep -rn "Log entry (CLI" tests/`). If a test asserts on this string, update or delete the test alongside the template change.

**Commit message:** `refactor(web): remove stale Log entry placeholder from expanded watchlist`

---

### T3 — QoL #3: Pivot price column in hypothesis-recommendations table

**Files:**
- `swing/web/view_models/dashboard.py` — extend `HypothesisRecommendation` with `pivot_price: float | None`
- `swing/web/templates/partials/hypothesis_recommendations.html.j2` — add `<th>Pivot</th>` column between Price and Hypothesis
- `tests/web/` — extend the hypothesis-recommendations VM/render test to cover pivot.

**Pivot source:** `swing.data.models.Candidate.pivot` (line 21 of `swing/data/models.py`). The dashboard's `build_dashboard` already populates `candidates_by_ticker: Mapping[str, Candidate]` in scope; look up `candidates_by_ticker.get(r.candidate_ticker).pivot` when constructing each `HypothesisRecommendation`. Default to `None` when the candidate isn't found (degenerate; should not happen in practice but matches the existing `current_price` defensive lookup pattern).

**VM change (dashboard.py:145-171):**
```python
@dataclass(frozen=True)
class HypothesisRecommendation:
    ticker: str
    current_price: float | None
    pivot_price: float | None      # NEW — Candidate.pivot
    hypothesis_id: int
    # ... rest unchanged
```

**Builder change (dashboard.py:474–499):** Add `pivot_price=candidates_by_ticker[r.candidate_ticker].pivot if r.candidate_ticker in candidates_by_ticker else None` to the `HypothesisRecommendation(...)` construction.

**Template change** (insert between current Price `<th>`/`<td>` and Hypothesis `<th>`/`<td>`):
```jinja
<th>Pivot</th>
...
<td>{% if rec.pivot_price is not none %}${{ "%.2f"|format(rec.pivot_price) }}{% else %}—{% endif %}</td>
```

**Acceptance criteria:**
- Test asserts pivot_price renders `$X.XX` when Candidate.pivot is set.
- Test asserts pivot_price renders `—` when Candidate.pivot is None.
- Test verifies pivot column appears between Price and Hypothesis columns.

**TDD discipline:** Write the failing test first (assertion on `$` followed by formatted price + `—` fallback). See it fail. Implement. See it pass. Commit.

**Commit message:** `feat(web): pivot price column in hypothesis-recommendations table`

---

### T4 — 3e.1: Mark-to-market unrealized P&L on Account card

**Files:**
- `swing/web/view_models/dashboard.py` — extend `StatusStripVM` with `unrealized_pnl: float | None` and `unrealized_priced_count: int`
- `swing/web/templates/partials/status_strip.html.j2` — add unrealized-P&L line under existing rationale on the account-tile
- `tests/web/test_dashboard.py` (or wherever StatusStripVM tests live) — extend tests

**Computation:** In `build_dashboard`, after `open_trade_last_prices` is populated, compute:

```python
unrealized = 0.0
priced_count = 0
for t in open_trades:
    snap = open_trade_last_prices.get(t.ticker)
    if snap is None:
        continue
    remaining = t.initial_shares - sum(e.shares for e in exits_by_trade.get(t.id, []))
    unrealized += (snap.price - t.entry_price) * remaining
    priced_count += 1
unrealized_pnl = unrealized if priced_count > 0 else None
```

Set on `StatusStripVM`:
- `unrealized_pnl=unrealized_pnl`
- `unrealized_priced_count=priced_count`

**Display behavior** (per operator confirmation in orchestrator session):
- When `unrealized_pnl is None` (no priced positions): no line rendered.
- When `priced_count == len(open_trades)`: render `Unrealized: ${X.XX}` (positive) or `Unrealized: -${X.XX}` (negative). Use sign convention consistent with rest of UI.
- When `priced_count < len(open_trades)`: render `Unrealized: ${X.XX} ({N} of {M} priced)` so the operator knows it's partial.

**Template change** (in `status_strip.html.j2`, inside the `account-tile` `<div>`, after existing `rationale`):
```jinja
{% if vm.status_strip.unrealized_pnl is not none %}
  <div class="unrealized">
    Unrealized: ${{ '%.2f' | format(vm.status_strip.unrealized_pnl) }}
    {% if vm.status_strip.unrealized_priced_count < vm.status_strip.open_count %}
      ({{ vm.status_strip.unrealized_priced_count }} of {{ vm.status_strip.open_count }} priced)
    {% endif %}
  </div>
{% endif %}
```

**CRITICAL — base-layout shared-VM gotcha:** `StatusStripVM` is consumed by `base.html.j2` indirectly via `dashboard.html.j2` extending it. **Re-read CLAUDE.md's gotcha** about every base-layout VM needing new fields. The `StatusStripVM` is referenced from `vm.status_strip` inside the dashboard page, NOT directly from base. **Verify** that the `unrealized_pnl` and `unrealized_priced_count` fields are added with safe defaults (`None` and `0` respectively) on the dataclass, AND that no other route's VM bypasses this field set. (Pipeline / journal / watchlist VMs don't carry `status_strip` — the gotcha doesn't bite here, but verify.)

**Acceptance criteria:**
- Test asserts unrealized line absent when 0 open trades.
- Test asserts unrealized line absent when open trades but no snapshots (degenerate; shouldn't happen but guarded).
- Test asserts unrealized renders `$X.XX` for fully-priced positions.
- Test asserts `(N of M priced)` suffix renders when partial.
- Verify regression-test arithmetic distinguishes pre-fix from post-fix per `feedback_regression_test_arithmetic.md` (the `(N of M priced)` text must not appear in pre-fix code; the new line must not appear in pre-fix code).

**Commit message:** `feat(web): unrealized P&L line on Account card`

---

### T5 — 3e.3: Prices-refresh also clears OHLCV breaker

**File:** `swing/web/routes/pipeline.py` — extend the `POST /prices/refresh` handler (line 289).

**Current behavior:** The handler clears the `PriceCache` circuit breaker. Operator-facing impact: if the OHLCV breaker is also tripped, SMA advisories remain unavailable and the operator has no UI affordance to retry.

**Required change:** After the existing PriceCache reset call, also call `app.state.ohlcv_cache.reset_circuit_breaker()` (or whatever the equivalent method is — confirm method name by reading `swing/web/ohlcv_cache.py`). If `app.state.ohlcv_cache` is None (test-only scenario), skip gracefully.

**Acceptance criteria:**
- Test asserts `POST /prices/refresh` calls `ohlcv_cache.reset_circuit_breaker()`.
- Existing PriceCache reset behavior is preserved.
- 200 response contract is preserved.

**TDD discipline:** Read `ohlcv_cache.py` to confirm the actual reset method name. Mock the OhlcvCache in your test; assert the method was called.

**Commit message:** `feat(web): prices-refresh also resets OHLCV breaker`

---

### T6 — 3e.4: Watchlist row collapse via dedicated close button

**Files:**
- `swing/web/templates/partials/watchlist_expanded.html.j2` — add a close-button affordance
- `swing/web/routes/watchlist.py` (or wherever `/watchlist/<ticker>/expand` lives) — confirm an existing route or add a new `/watchlist/<ticker>/collapse` (or reuse compact-row render path) that returns the compact `watchlist_row.html.j2`
- Tests for the collapse round-trip

**Operator decision:** Dedicated close button (✕) inside the expanded panel — NOT a click-row-to-toggle. More discoverable, single affordance, no event-propagation gotchas.

**Implementation pattern:**

Add to `watchlist_expanded.html.j2` (inside the `<td colspan="7">` panel, near the top or in a dedicated header row):

```jinja
<button class="close-expanded"
        onclick="event.stopPropagation()"
        hx-get="/watchlist/{{ expanded.ticker }}/row"
        hx-target="closest tr"
        hx-swap="outerHTML"
        hx-headers='{"HX-Request": "true"}'
        title="Close">✕</button>
```

The `event.stopPropagation()` is mandatory — this expanded `<tr>` itself does not have an `hx-get` (the compact row does), but defense-in-depth: future row-level HTMX additions won't accidentally bubble.

**Route — choose one of:**

**Option A:** Add a new `GET /watchlist/<ticker>/row` route that returns the compact row partial. Symmetric naming with `/expand`. Recommended.

**Option B:** Reuse an existing compact-render route if one exists (search the routes module before adding).

For Option A, the route handler builds a `WatchlistEntry` for the ticker (use existing `list_active_watchlist` + filter), looks up the price snapshot, looks up `flag_tags` for the ticker, and renders `partials/watchlist_row.html.j2` with the same expected context: `w`, `price`, `tags`. Reuse the same VM-build pattern as `/watchlist/<ticker>/expand` for consistency.

**Acceptance criteria:**
- Test asserts `GET /watchlist/<ticker>/row` returns the compact `<tr>` shape (starts with `<tr` and contains the ticker).
- Test asserts the route returns 404 for unknown ticker (defensive — match `/expand` behavior).
- Test asserts the close button HTML is present in the expanded partial.
- Manual verification (document in return report): clicking ✕ collapses the expanded row back to compact form.

**TDD discipline:** Failing test first asserting compact-row shape. Then implement route + template button. Verify pre-fix code returns 404 (the route doesn't exist yet) — that distinguishes pre-fix from post-fix per the regression-arithmetic feedback memory.

**Commit message:** `feat(web): close button to collapse expanded watchlist row`

---

### T7 — Bug 2 `_handle_any` HX-Target-aware fragment selection

**File:** `swing/web/app.py` — modify `_handle_any` (lines 69–85).

**Current behavior:** When an unhandled non-HTTPException fires inside an HTMX request, the handler returns `partials/error_fragment.html.j2` regardless of HX-Target. For row-target requests (entry/exit/stop forms, watchlist Enter button), the bare `<div>` gets hoisted out of `<tbody>` by the HTML parser, leaving an empty row position. This is the structural cause of the original Bug 2 misdiagnosis — the operator's Bug 2 reproduction was caused by a different mechanism (sizing-hint hx-target inheritance, fixed in `2a167d1`), but the `_handle_any` gap remains as a latent risk for any future row-target route that raises an unrelated exception.

**Required change:** Mirror the row-target awareness pattern that `_handle_http_exc` already implements (lines 143–160). When `_is_row_swap_target(request)` returns True AND the request is HTMX, return `partials/trade_form_error.html.j2` instead of `partials/error_fragment.html.j2`.

**Implementation** (replace the existing `_handle_any` body's template-selection logic):

```python
@app.exception_handler(Exception)
async def _handle_any(request: Request, exc: Exception) -> HTMLResponse:
    if isinstance(exc, (HTTPException, StarletteHTTPException)):
        return await http_exception_handler(request, exc)
    rid = getattr(request.state, "request_id", "-")
    log.exception("unhandled error (request_id=%s)", rid)
    tpls = _build_templates(app.state.templates_dir)
    is_htmx = request.headers.get("HX-Request", "").lower() == "true"
    if is_htmx and _is_row_swap_target(request):
        return tpls.TemplateResponse(
            request, "partials/trade_form_error.html.j2",
            {"error_message": str(exc)},
            status_code=500,
        )
    template = "partials/error_fragment.html.j2" if is_htmx else "error.html.j2"
    return tpls.TemplateResponse(
        request, template,
        {"request_id": rid, "error_message": str(exc)},
        status_code=500,
    )
```

**Acceptance criteria — regression test:**

Following the `feedback_regression_test_arithmetic.md` discipline, the test must distinguish pre-fix from post-fix:

- Set up a test app where a row-target route (e.g., monkey-patched `entry_post`) raises a plain `RuntimeError("simulated")`.
- Issue a POST with `HX-Request: true` and `HX-Target: entry-form-watchlist-row-FOO` (or any row-prefix value matching `_ROW_TARGET_PREFIXES`).
- Assert response body **starts with `<tr`** and does NOT start with `<div`.
- **Pre-fix:** body starts with `<div class="banner banner-degraded">` (error_fragment) — assertion fails.
- **Post-fix:** body starts with `<tr id=...>` (trade_form_error) — assertion passes.

This is the discriminator: `<div` vs `<tr` as the first-tag signature.

**Watch item:** confirm `partials/trade_form_error.html.j2` accepts an `error_message` context variable (read the template to verify) and produces `<tr>` shape. If the existing template already takes `error_message`, the call site above is correct as-written.

**Commit message:** `fix(web): _handle_any returns row-shaped fragment for row-target HTMX requests`

---

## Adversarial review

After T1–T7 land, run `copowers:adversarial-critic` on the combined diff. Iterate until the verdict is `NO_NEW_CRITICAL_MAJOR`. Fix findings in NEW commits per no-amend rule.

**Standing watch items to pass to the critic:**

- Did each task's regression test arithmetic distinguish pre-fix from post-fix per `feedback_regression_test_arithmetic.md`? (Especially T7 — `<div` vs `<tr` discriminator.)
- For T1: does the alternating-row CSS rule survive the existing `tr.tripwire-fired` rule? Source-order at equal specificity matters.
- For T3: does pivot_price source from `Candidate.pivot` match the canonical pivot field? Don't accept a fallback that pulls from elsewhere if the canonical source exists.
- For T4: does `(N of M priced)` text discriminate fully-priced from partial-priced cases in the test? The line render must not appear identical in both paths.
- For T4: did adding `unrealized_pnl` and `unrealized_priced_count` to `StatusStripVM` break any non-dashboard route? Watchlist/journal/pipeline VMs don't carry `status_strip`, but verify nothing else references the dataclass with positional args.
- For T6: does the close-button include `event.stopPropagation()`? The expanded row is currently click-passive but defense-in-depth applies.
- For T7: does the test reproduce the operator's failure mode (a `RuntimeError` from a row-target route producing `<div` pre-fix vs `<tr` post-fix)?
- **Did the investigation empirically reproduce each bug's symptom?** This is the standing post-Bug-2 watch item. For T1–T6 there is no "bug" per se (these are enhancements), but for T7 the regression test IS the empirical reproduction — verify it actually fires the path it claims to.
- For UI-only changes (T1, T2, T6): the project lacks a JS test harness. String-match assertions on rendered HTML confirm structure but not runtime behavior. Manual verification is the actual confidence source. Document the verification steps you ran in the return report.

---

## Done criteria

- All 7 tasks committed as separate commits, conventional-commits style, no `--no-verify`, no amends, no Claude co-author footer.
- `python -m pytest -m "not slow" -q` passes — expected count: 969 + N where N = number of new tests added (track this).
- `ruff check swing/` shows no NEW violations beyond the pre-existing baseline of 81.
- Adversarial-review verdict on the combined T1–T7 diff: `NO_NEW_CRITICAL_MAJOR`.
- Manual verification documented in return report for cosmetic / JS-behavior tasks (T1, T2, T6).

---

## Return report format

Return a single message structured as follows:

```
## QoL UI-Polish Bundle Return Report

### Tasks shipped
- T1 (commit <sha>): [outcome + new test count + manual-verify status]
- T2 (commit <sha>): [outcome]
- T3 (commit <sha>): [outcome + new test count]
- T4 (commit <sha>): [outcome + new test count]
- T5 (commit <sha>): [outcome + new test count]
- T6 (commit <sha>): [outcome + new test count + manual-verify status]
- T7 (commit <sha>): [outcome + new test count]

### Final test count
<N> passing, 0 failing.

### Adversarial review summary
- Round 1: <findings>; addressed in commit <sha>
- Round 2 (if needed): ...
- Final verdict: NO_NEW_CRITICAL_MAJOR after R<N>.

### Judgment calls / deviations from brief
[Anything you decided differently than the brief specified, with rationale.]

### Manual-verification notes
[For T1, T2, T6: what you did to confirm the change works in a browser.]

### Follow-ups flagged (NOT fixed inline)
[Anything you noticed that's outside scope. Goes to phase3e-todo.md at next housekeeping.]
```

---

## If you get stuck

- **Test fails for a reason you don't understand:** read the test's assertion arithmetic; verify pre-fix and post-fix paths are actually distinguished. The `feedback_regression_test_arithmetic.md` memory file documents the canonical failure mode.
- **A task touches code outside the brief's scope:** stop. Flag in return report. Do not expand scope mid-session.
- **Adversarial reviewer flags something architecturally larger:** triage. If it's a clear cross-cutting concern, capture as a follow-up; don't try to fix mid-session.
- **The OHLCV breaker reset method name is different from `reset_circuit_breaker()`:** read the actual `swing/web/ohlcv_cache.py` to find the correct method. Don't guess.
- **HTMX runtime behavior verification:** the project lacks a JS test harness. Run `swing web` locally, exercise the surface manually, document the observed behavior in the return report. Manual verification is the JS-behavior confidence source.
- **`partials/trade_form_error.html.j2` doesn't accept `error_message`:** read the template; adapt the context dict to match what it expects. If it doesn't take an error message at all, that's a finding worth flagging.
