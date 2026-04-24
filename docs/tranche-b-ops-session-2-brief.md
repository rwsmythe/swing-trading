# Tranche B-ops session 2 — Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Execute tasks T1, T2, T3 from the Tranche B-ops session-1 design spec, plus a housekeeping commit tracking the remaining untracked dispatch brief. Four commits on `main`.
**Expected duration:** 4–6 hours of implementer work.
**Prepared:** 2026-04-24 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions, gotchas, Phase isolation rule, TDD discipline. Note the template-duplication gotcha (Tranche B-cleanup) — relevant to T3 which adds a new template rendering path.
2. `docs/superpowers/specs/2026-04-23-tranche-b-ops-session-1-design.md` — the authoritative design for this session's work. §1 covers T1, §2 covers T2, §4 covers T3. §7 contains the full implementation task list. **This spec is your contract; the brief below adds only sequencing, housekeeping, and orchestrator-resolved judgment calls.**
3. `docs/tranche-a-brief.md` and the existing Tranche B briefs for precedent on brief/commit style.

**Skill posture.** Do NOT invoke the `copowers:*` wrapper skills. This is execution of an already-reviewed design, not new design work. Invoke `superpowers:test-driven-development` per CLAUDE.md's TDD convention. Invoke `superpowers:verification-before-completion` before declaring done. `superpowers:systematic-debugging` only if a failure is non-obvious.

---

## 1. Session scope — exactly four commits

| # | Commit | Source |
|---|--------|--------|
| C0 | Housekeeping: track remaining dispatch brief | Orchestrator — see §2 |
| C1 | Bug 5 label rename | Spec §1 |
| C2 | Open-risk tile (Bug 6) | Spec §2 |
| C3 | Chart-unavailable reason resolver (Bug 4) | Spec §4 |

### Explicitly out of scope

- T4, T5, T6, T7 (rationale-taxonomy cluster + stop-form preservation) — these are Session 3.
- Any §8 deferred-item work (pipeline-linkage bundle, book-equity denominator, ExitRationale split, etc.).
- Any change outside what the spec §1 / §2 / §4 actually specify.
- Any refactor tempting adjacent code cleanup.

If during implementation you find a tempting adjacent improvement, flag it in the return report rather than doing it.

---

## 2. Housekeeping commit (C0) — track the session-1 dispatch brief

`docs/tranche-b-ops-brief.md` is currently untracked (confirmed at the end of Tranche B-ops session 1 return report). It was the dispatch brief that produced the design spec. Following the Tranche B-cleanup precedent (commit `4f74493`), dispatch briefs land in their own tracking commits.

**Also check:** `docs/tranche-b-ops-session-2-brief.md` (this file) is also untracked. Include it in C0.

**Steps:**

```bash
git status
# verify: docs/tranche-b-ops-brief.md and docs/tranche-b-ops-session-2-brief.md are untracked
git add docs/tranche-b-ops-brief.md docs/tranche-b-ops-session-2-brief.md
git status  # confirm both staged
```

Commit message:

```
docs: track tranche B-ops dispatch briefs

- tranche-b-ops-brief.md dispatched the session-1 design work
  (commit 971ad36).
- tranche-b-ops-session-2-brief.md dispatches this session.
```

**Ship C0 first**, before any code changes. Keeps the session's history clean.

---

## 3. Orchestrator-resolved judgment calls

The design spec §9 left two non-blocking judgment calls for implementers. Resolved here so you don't have to re-decide:

### JC-a — `other` validation layer placement (relevant for Session 3, but noting here)

Not applicable to C1/C2/C3 (no `other` dropdown ships this session). For your awareness: Session 3 will follow the existing `TradeEntryFormVM` validation pattern.

### JC-b — T3 chart-scope resolver as pure helper vs inline

**Pure helper function.** Six states with branching — inline kills diffability and makes per-state testing awkward. Helper lives in a new module (e.g., `swing/web/chart_scope.py` or similar — match sibling module naming) or extends an existing module if one is an obvious fit. Do NOT create a subpackage just for this one helper.

Helper signature follows the spec §4 signature (verify against the spec; if the spec is underspecified on signature shape, match the pattern of sibling helpers in `swing/web/`).

---

## 4. Task notes — orchestrator additions to the spec

The spec is authoritative. Notes here cover only sequencing, test-expectations delta, and items the spec may have under-specified.

### C1 — Bug 5 label rename (spec §1)

- One-line edit in [swing/recommendations/build.py:32](swing/recommendations/build.py#L32) per spec §1 "Decision."
- The spec notes 6 test files assert substring variations. Update any that assert `"Buy-stop limit"` to the new `"Buy-stop"` form. Do NOT rewrite any test beyond the substring replacement unless the test's assertion semantics break.
- Add one regression test explicitly asserting `action_text` does NOT contain the substring `"limit"` for a buy-stop recommendation. This catches accidental label regression in future edits.
- Run full fast suite (`python -m pytest -m "not slow" -q`). Must be green before commit.

**Commit message:**

```
fix(recommendations): rename A+ action label "Buy-stop limit" to "Buy-stop"

The persisted recommendation carries only a stop price; the broker-side
limit price is operator-supplied at order entry. The prior label
implied a two-price buy-stop-limit order which the system never
produces. Spec §1.
```

### C2 — Open-risk tile (spec §2)

- Read `swing/trades/equity.py` (confirmed to exist) for the realized-equity helper. The denominator for the percentage must match whatever the per-trade sizing-hint calculation currently uses. Do NOT compute equity a second way.
- VM field placement per spec §2 ("new tile in status strip: Weather → Account → Open risk → Last pipeline"). Check the existing `StatusStripVM` (status strip view model) and match its field-naming conventions — likely `open_risk_dollars: float` and `open_risk_pct: float` but follow the sibling-field style.
- Template edit in `swing/web/templates/partials/status_strip.html.j2` — add tile between Account and Last pipeline.
- **Gotcha preview:** CLAUDE.md documents that `base.html.j2` is shared across pages and every base-layout VM must gain any new field. If the status strip is rendered from multiple base-layout VMs (DashboardVM, PipelineVM, JournalVM, WatchlistVM, PageErrorVM per CLAUDE.md), every one of them needs the new fields with safe defaults. This is the same failure pattern as `price_source_degraded` / `ohlcv_source_degraded` noted in CLAUDE.md. Verify and populate all base-layout VMs, not just DashboardVM.
- Tests: (a) VM-calculation tests covering empty book (0/0.00%), mixed-direction stops (positions where stop ≥ entry contribute 0, not negative), multiple positions with real R calculations, and a single-position sanity case; (b) template-render test for the status strip asserting the tile appears with correct formatting; (c) cross-VM test confirming all base-layout VMs carry the fields (paralleling however the existing `price_source_degraded` cross-VM test is structured — likely `tests/web/test_view_models/`).

**Commit message:**

```
feat(web): open-risk tile in dashboard status strip

Adds Σ max(0, shares_remaining × (entry_price − current_stop)) across
open positions, both dollar value and percent of realized equity.
Surfaced as a new tile between Account and Last pipeline per spec §2.
Denominator matches per-trade sizing-hint convention for cross-UI
consistency.
```

### C3 — Chart-unavailable reason resolver (spec §4)

- Per JC-b above: pure helper function.
- Six states per spec §4. Read the spec's state enumeration and decision tree carefully — the adversarial review resolved a drift-mode concern, so the resolver's scope (against persisted A+ candidates + live watchlist top-N-by-proximity) is load-bearing. Do not simplify it back to a direct pipeline-state lookup.
- The resolver is framed as a best-effort heuristic with documented drift modes. The template rendering must not imply false precision. If the spec's state strings are worded "Chart unavailable (insufficient data)" vs "Chart could not be generated (ticker out of scope)", match the spec's copy exactly — don't paraphrase.
- Template edit in whichever partial renders the expanded watchlist entry. When the resolver returns an `available` state, render the chart normally; otherwise render the reason message in place of the chart image.
- Tests: (a) resolver tests — one per state, covering the state machine exhaustively; (b) VM-integration test — `WatchlistExpandedVM` carries the resolved reason; (c) template-render test — expanded entry shows the correct message for each non-`available` state.
- Note the CLAUDE.md template-duplication gotcha: if the expanded-watchlist render is reached via both a full-page path and an HTMX partial-swap path, both must render through the same `{% include %}`. Verify before committing.

**Commit message:**

```
feat(web): chart-unavailable reason on expanded watchlist entries

Adds a six-state chart-scope resolver (swing/web/chart_scope.py) that
classifies why a chart is not available for a given ticker-session
pair: insufficient data, ticker rotation, fetch error, etc. Resolver
is framed as a best-effort heuristic with drift modes documented in
spec §4. Replaces the prior silent omission with an explicit reason
string in WatchlistExpandedVM; template renders the message in place
of the missing chart.
```

(Adjust the helper module path in the commit body to match what you actually create.)

---

## 5. Binding conventions

- **Branch:** `main`.
- **Commits:** conventional-commits. No Claude co-author footer. No `--no-verify`. No amending.
- **TDD:** per CLAUDE.md — failing test first, minimal impl, pass, commit. One red-green-refactor cycle per logical change.
- **Tests:** fast suite green after every commit. Baseline going into this session is 514 passing; every new test adds to that count, zero failures.
- **Ruff:** `ruff check swing/` introduces no new violations beyond the 81-error baseline CLAUDE.md documents.
- **Phase isolation:** not triggered — `swing/recommendations/` and `swing/web/` are not in the read-only list. `swing/trades/equity.py` is consumed read-only (import only, no modifications).

---

## 6. Commit sequencing

1. **C0** — housekeeping (no code, no tests, no ruff impact).
2. **C1** — Bug 5 label rename (smallest code change, lowest risk; fast-suite check).
3. **C2** — Open-risk tile (moderate change; base-VM gotcha is the main risk).
4. **C3** — Chart-scope resolver (largest change; template + VM + new helper + state-machine tests).

Run `python -m pytest -m "not slow" -q` and `ruff check swing/` after each code commit.

---

## 7. Done criteria

- Four commits on `main` (C0 + C1 + C2 + C3).
- Fast suite passes with no failures.
- No new ruff violations.
- Spec §1, §2, §4 fully implemented (all "Decision" sub-sections land as code).
- Return report produced.

---

## 8. Return report format

```
## Tranche B-ops session 2 return report

### Commits landed
- <SHA> docs: track tranche B-ops dispatch briefs
- <SHA> fix(recommendations): rename A+ action label "Buy-stop limit" to "Buy-stop"
- <SHA> feat(web): open-risk tile in dashboard status strip
- <SHA> feat(web): chart-unavailable reason on expanded watchlist entries

### Tests
- Before: 514 passing, 0 failing (fast suite).
- After: <N> passing, 0 failing. New tests: <M>.
  - C1: <N> new tests (label regression + snapshot updates).
  - C2: <N> new tests (VM calc, template render, cross-VM base-layout coverage).
  - C3: <N> new tests (per-state resolver, VM integration, template render).

### Ruff
- No new violations (baseline 81 unchanged).

### Deviations from brief / spec
<Anything different from the brief or spec, and why. Empty if none.>

### Items flagged but not done (scope discipline)
<Any adjacent cleanup or enhancement noticed but deliberately not touched.>

### Base-layout VM coverage (C2)
<Which base-layout VMs gained open_risk_dollars / open_risk_pct (or chosen field names). Confirm all five — DashboardVM, PipelineVM, JournalVM, WatchlistVM, PageErrorVM — have the field.>

### Helper module path (C3)
<Confirm final path of the chart-scope resolver helper.>

### Open questions for orchestrator
<Anything the brief or spec under-specified; judgment calls made. Empty if none.>
```

---

## 9. If you get stuck

- If a spec section feels under-specified on an implementation detail, match the pattern of existing sibling code first (established conventions beat inventing new ones). If no sibling pattern is obvious, flag in the return report and pick the smallest reasonable option.
- If a test you write passes against BOTH the pre-change and post-change code, rewrite the test — it's vacuous (see `memory/feedback_regression_test_arithmetic.md` for the cautionary precedent).
- If the base-layout VM update pattern surprises you (e.g., there's a sixth VM that isn't in CLAUDE.md's list), add the field to it anyway and flag the discovery in the return report.
- If the Open-risk calculation produces negative values in any edge case (which it shouldn't per the `max(0, ...)` wrapper), verify the wrapper is in the right place — per-position, not just on the sum.
- If the chart-scope resolver's state machine hits an input the spec didn't enumerate, flag in the return report and pick the most-conservative state (prefer "unavailable: unknown reason" over "available").
