# Hyp-recs Trade-Prep Expansion Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Convert the hyp-recs panel from a flat 7-column read-only table into a click-to-expand surface with full trade-preparation context (order parameters, sizing twins, sector/industry, inline chart). Add per-row Enter button (Q7) and expansion-internal "Take this trade" button (Q8). Bundle the CC pivot bug fix on the watchlist Pivot column across all three render sites. Add `Config.web.chase_factor` config field. Make the existing trade entry form origin-aware so it serves both watchlist and hyp-recs callers correctly across colspan, Cancel, POST round-trips, and candidate anchor.

**Architecture:** Snapshot-at-click expansion VM (`HypRecsExpandedVM`) computed inside a route-local helper bound to `latest_completed_pipeline_run`; sizing twins are two `compute_shares` calls with risk-equity-floor and cash-feasible equity arguments — no new sizing logic. The hyp-recs flat table extracts a per-row partial (`hypothesis_recommendations_row.html.j2`) so the same markup feeds full-page render and the new `/hyp-recs/refresh` scoped route — closes the HTMX OOB-swap drift class. The refresh route uses a scoped `build_hyp_recs_section` builder (not the full `build_dashboard`) so a hyp-recs close action does not couple to open-trades / OHLCV / watchlist subsystems. The trade entry form gains a `TradeEntryFormVM.origin: Literal["watchlist","hyp-recs"]` discriminator (default `"watchlist"` preserves existing behavior); colspan, Cancel target, and a hidden form field parameterize on it; POST round-trip paths (`_rerender_entry_form_with_error`, `DuplicateOpenPositionException`, `soft_warn_confirm`) propagate the discriminator end-to-end. Anchor consistency for `origin=hyp-recs` binds ALL candidate-derived reads to `latest_completed_pipeline_run`'s `evaluation_run_id` — matches the expansion's anchor.

**Tech Stack:** Python 3.14, SQLite (WAL mode, foreign_keys=ON), dataclasses (frozen=True), FastAPI + Starlette + Jinja2 + HTMX, click CLI, pytest.

**Test baseline (HEAD `a492b84`, plan-authoring time):** 1228 fast tests collected (8 deselected) via `python -m pytest -m "not slow" -q --collect-only`. Implementer verifies green at `python -m pytest -m "not slow" -q` before Task 1 commits land.

**Spec source-of-truth:** `docs/superpowers/specs/2026-04-29-hyp-recs-trade-prep-expansion-design.md` (1,158 lines; 5 Codex rounds; terminating `NO_NEW_CRITICAL_MAJOR` at commit `ade2b41`). Q1-Q8 (operator-locked) and the 13 §3 design questions (Q-A through Q-M) are LOCKED. The plan IMPLEMENTS the spec; it does NOT re-design.

**No migration.** No schema-version bump. Sector + industry are already on `candidates`/`trades` from migration 0012 (sector capture, shipped 2026-04-29).

**No Phase 2 carve-outs.** This dispatch is read-only with respect to `swing/data/` and `swing/trades/`. The single optional `get_for_evaluation(conn, evaluation_run_id, ticker)` accessor on `swing/data/repos/candidates.py` mentioned in spec §5 is NOT created — Task 5 reuses the existing `fetch_candidates_for_run(conn, run_id)` and filters by ticker in-Python. Spec §5 explicitly authorizes this verification: "if such an accessor already exists, no Phase 2 touch; if not, adding it is a Phase 2 carve-out with justification — single-row read against existing table." The single-row hot-path performance argument doesn't pay off here (per-click handler; tens of candidates per run; 1 lookup per click), so we keep Phase 2 untouched.

**Locked decisions (per spec §1.1 — DO NOT re-litigate):**
1. Chase factor = 1% in V1, configurable via `Config.web.chase_factor: float = 0.01`. NO toml row added (Phase 5 surfaces the editor).
2. Chart in expansion uses the existing chart-access UX (`resolve_chart_scope` + date-prefixed `<img>`).
3. Cost display = TWO numbers, side by side (risk-based + cash-feasible).
4. Lightning icon stays bound to `entry_target` — no behavior change.
5. Hyp-recs ONLY in this dispatch. Watchlist + open-positions snapshot extensions deferred.
6. CC pivot bug bundled — watchlist Pivot column header renders `candidates.pivot` across THREE render sites; lightning trigger logic preserved.
7. Per-row Enter button on hyp-recs table (Q7) — mirrors watchlist's Enter button.
8. "Take this trade" button INSIDE the expansion (Q8) — IN ADDITION TO Q7.

**Implementation sequencing (per spec §7.1):**
1. CC pivot fix (independent; revertible).
2. `Config.web.chase_factor` field (atomic; no UX impact).
3. `_build_active_recommendations` shared helper extraction (refactor `build_dashboard`; zero behavior change).
4. `HypRecsSectionVM` + `build_hyp_recs_section` + `GET /hyp-recs/refresh` route.
5. Hyp-recs expansion (chevron + Enter col + row partial + `HypRecsExpandedVM` + `build_hyp_recs_expanded` + expand route + expansion partial with Take-this-trade + close button + row-target-prefix extension).
6. Origin-aware entry-form scaffolding (`TradeEntryFormVM.origin` + colspan/Cancel template parameterization + GET-handler whitelist).
7. Off-watchlist candidate fallback for `entry_price` / `initial_stop` (R3-Major-2).
8. Origin survives POST round-trips (R4-Major-1).
9. Anchor consistency for `origin=hyp-recs` + freshness footer (R4-Major-2).

Plan task ordering = spec §7.1 ordering. Acknowledged transient state: Task 5 ships the per-row Enter and Take-this-trade buttons WITHOUT origin handling in the form (Tasks 6-9). Until Task 9 lands, clicking those buttons emits `?origin=hyp-recs` but the form ignores the param and renders with default `origin="watchlist"` (colspan=8 + Cancel `/watchlist/{ticker}/expand`). Each Task 5–9 commit is individually green (test suite stays passing); operator-facing UI is fully coherent only at end-of-plan. This trade is per spec §7.1 explicit guidance: "step 6 lands last so any defects don't block the simpler steps."

> **Codex R1 Major 3 — accepted with rationale.** Codex flagged the transient state as a partitioning hazard ("a worker landing/pausing after Task 5 ships a broken workflow"). Reordering buttons-after-form (Tasks 5.5/5.6 → after Task 9) would eliminate the transient but DEVIATES from spec §7.1's explicit ordering. The spec author considered this trade-off and chose buttons-before-form-scaffolding deliberately because (a) the hyp-recs UI surface is gated behind operator click — operators see the transient only if they actively click a button mid-dispatch and validate post-Task-5 outcomes, AND (b) the executing-plans dispatch is single-subagent + sequential — there is no operator-facing release between commits inside the dispatch (the merge-to-main happens at end-of-plan). The transient is bounded to the implementer's local working tree, NOT to a shipped artifact. The spec's ordering rationale ("largest task lands last so defects don't block simpler steps") is preserved. Accept; document explicitly so future readers understand the intentionality.

**Hyp-recs sort key NOT touched.** Per spec §2.2 sort-neutrality invariant. `prioritized_recommendations`, `_sort_watchlist`, and all `_TAG_PRECEDENCE` references are byte-for-byte unchanged. Task 5 adds a sort-neutrality regression test (`tests/web/test_view_models/test_hyp_recs_sort_neutrality.py`) as a guard against future churn — `HypothesisRecommendation` is unchanged in V1 so the sort path has zero new inputs.

**Base-layout 5-VM rule does NOT apply.** Verified at plan-time: `grep -n "expanded\|chase_factor\|HypRecsExpandedVM\|sizing_twins" swing/web/templates/base.html.j2` returns zero matches. The expansion data lives ONLY on `HypRecsExpandedVM` (route-scoped); the new partial is included only via the HTMX expand route, never via the dashboard's full-page render path. No new top-level `vm.foo` field is introduced.

---

## File Map

### Production NEW (4)

- `swing/web/routes/recommendations.py` — Tasks 4 + 5. New router; defines `GET /hyp-recs/refresh` (Task 4) and `GET /hyp-recs/{ticker}/expand` (Task 5). Registered in `swing/web/app.py`'s `app.include_router(...)` block.
- `swing/web/templates/partials/hypothesis_recommendations_row.html.j2` — Task 5. Per-row partial extracted from `hypothesis_recommendations.html.j2`; consumed by both the full-page render and the `/hyp-recs/refresh` route via `{% include %}`. Single source of truth for row markup.
- `swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2` — Task 5. Expansion partial (Order parameters / Sizing twins / Chart / Context / Freshness / Take-this-trade button); consumed only by `GET /hyp-recs/{ticker}/expand`.
- `swing/web/templates/partials/hyp_recs_expand_unavailable.html.j2` — Task 5. 404-state row partial rendered when the expand handler returns `None` (ticker rotated out of candidates / no completed pipeline run / degenerate sizing).

### Production MODIFY (12)

1. `swing/config.py` (Task 2) — `Web` dataclass gains `chase_factor: float = 0.01` trailing-default field.
2. `swing/web/view_models/dashboard.py` (Tasks 3 + 4 + 5) — Task 3 extracts `_build_active_recommendations` shared helper from `build_dashboard`'s existing inline tuple-construction at lines 552-581 (zero behavior change). Task 4 adds `HypRecsSectionVM` dataclass + `build_hyp_recs_section` builder. Task 5 adds `HypRecsExpandedVM` dataclass + `build_hyp_recs_expanded` helper. `HypothesisRecommendation` UNCHANGED (per spec §3.5.1 R1-Major-1 resolution).
3. `swing/web/view_models/watchlist.py` (Task 1) — `WatchlistRowVM` gains `current_pivot: float | None = None` trailing-default field. `build_watchlist_row` resolves `current_pivot` from `candidates_by_ticker[ticker].pivot` when available, else `None`.
4. `swing/web/view_models/trades.py` (Tasks 6 + 7 + 9) — Task 6: `TradeEntryFormVM` gains `origin: Literal["watchlist", "hyp-recs"] = "watchlist"` trailing-default field; `build_entry_form_vm` accepts `origin: str = "watchlist"` keyword arg with whitelist coercion. Task 7: extends candidate-row SELECT to fetch `pivot` + `initial_stop`; falls back to candidate values when `wl_entry` is None. Task 9: gains `pipeline_finished_at: str | None = None` trailing-default field; for `origin=hyp-recs`, ALL candidate-derived reads (sector, industry, pivot, initial_stop, chart-pattern) bind to `latest_completed_pipeline_run`'s `evaluation_run_id`.
5. `swing/web/routes/watchlist.py` (Task 1) — `GET /watchlist/{ticker}/row` populates `WatchlistRowVM.current_pivot` from `candidates_by_ticker`; the row partial render context dict gains `current_pivot=row_vm.current_pivot`.
6. `swing/web/routes/trades.py` (Tasks 6 + 8) — Task 6: `entry_form` GET handler reads `?origin=` query param (whitelist-coerce; unknown → `"watchlist"`); passes through to `build_entry_form_vm`. Task 8: `entry_post` POST handler reads form-payload `origin` (whitelist-coerce); threads through `_rerender_entry_form_with_error`, `DuplicateOpenPositionException` re-render, and soft-warn `form_values` dict.
7. `swing/web/app.py` (Tasks 5) — Task 5: register the recommendations router; extend `_ROW_TARGET_PREFIXES` to include `"hyp-rec-row-"`.
8. `swing/web/templates/partials/hypothesis_recommendations.html.j2` (Tasks 5 + 4) — Task 5: gains chevron leading column (col 1) + Enter trailing column (col 9); `<tbody>` iterates `{% include "partials/hypothesis_recommendations_row.html.j2" %}`. Task 4 (refresh-route handoff): the same template renders the refresh response (no template diff at Task 4 — all template changes are bundled into Task 5's commit).
9. `swing/web/templates/partials/trade_entry_form.html.j2` (Tasks 6 + 8 + 9) — Task 6: parameterize `<td colspan>` (9 if `vm.origin == 'hyp-recs'` else 8) + Cancel button `hx-get` / `hx-target` based on `vm.origin`. Task 8: hidden `<input type="hidden" name="origin" value="{{ vm.origin }}">` form field. Task 9: freshness footer when `vm.origin == 'hyp-recs'` showing `Candidate context as of pipeline finished {{ vm.pipeline_finished_at }}`.
10. `swing/web/templates/partials/soft_warn_confirm.html.j2` (Task 8) — gains hidden `<input type="hidden" name="origin" value="{{ form_values.origin }}">` (auto-emitted by the `for key, value in form_values.items()` loop once `origin` is added to `form_values`); Cancel button parameterizes its `hx-get` and `hx-target` on `form_values.origin`.
11. `swing/web/templates/partials/watchlist_row.html.j2` (Task 1) — line 16 changes from `${{ '%.2f' | format(w.entry_target or 0) }}` to `{% if current_pivot is not none %}${{ '%.2f' | format(current_pivot) }}{% elif w.entry_target %}${{ '%.2f' | format(w.entry_target) }}{% else %}—{% endif %}`. Lightning trigger at line 7 unchanged. Reads new template-context variable `current_pivot: float | None`.
12. **Two parent templates that iterate watchlist rows (counted as one MODIFY entry per spec §2.1; two file edits):**
    - `swing/web/templates/partials/watchlist_top5_section.html.j2` (Task 1) — inside the `{% for w in vm.watchlist_top5 %}` block, immediately before the row include, add `{% set current_pivot = vm.candidates_by_ticker[w.ticker].pivot if w.ticker in vm.candidates_by_ticker else None %}`.
    - `swing/web/templates/watchlist.html.j2` (Task 1) — same `{% set current_pivot = ... %}` insertion immediately before the row include at line 13.

### Test NEW (6)

Spec §2.1 referenced `tests/web/templates/` and `tests/web/routes/` paths. The actual repo convention has no `tests/web/templates/` subdir; template-render tests live in `tests/web/` (cross-cutting) or `tests/web/test_view_models/` (VM-scoped). Plan paths follow existing convention.

- `tests/recommendations/test_hypothesis_sizing_twins.py` — Task 5 (sub-step 5.1). 6 unit tests for the sizing-twin pure-function pattern (two `compute_shares` calls). No DB; no fixture; just `compute_shares` calls with discriminating arithmetic per the regression-test arithmetic memory.
- `tests/web/test_view_models/test_hyp_recs_expansion_vm.py` — Task 5 (sub-step 5.2). 9 VM-build tests covering happy path, chart-out-of-scope, ticker-not-in-latest-run, no-completed-pipeline-run, anchor consistency, buy-limit arithmetic, chase-factor threading, degenerate stop, sector/industry threading.
- `tests/web/test_view_models/test_hyp_recs_sort_neutrality.py` — Task 5 (sub-step 5.6). Sort-neutrality regression: `prioritized_recommendations` order is byte-for-byte identical to the pre-V1 baseline.
- `tests/web/test_routes/test_hyp_recs_expand_route.py` — Tasks 4, 5, 6, 7, 8, 9 (consolidated route-level test file). Task 4 seeds it with refresh-route tests; subsequent tasks extend.
- `tests/web/test_hyp_recs_table_regression.py` — Task 5 (sub-step 5.7). Template-render regression: 9-column thead; chevron col 1; Enter col 9; close-button absent on collapsed row.
- `tests/web/test_watchlist_pivot_column.py` — Task 1. 6 discriminating tests covering all three render sites + dash sentinel + lightning trigger preservation.

> **Test-path verification at executing-plans dispatch.** Implementer should `Read` precedent test files BEFORE adding new tests so the new tests adopt existing scaffolding patterns (fixture imports, helper invocations, assertion shape). Mid-file insertion via Edit is the V1 plan path unless an existing file is structurally incompatible. The most relevant precedents:
>   - `tests/web/test_dashboard_hypothesis_template.py` for hyp-recs template-render shape.
>   - `tests/web/test_view_models/test_dashboard_hypothesis_recommendations.py` for VM-build patterns.
>   - `tests/web/test_view_models/test_watchlist.py` line 153 for `TestClient(app)` lifespan-bound template render.
>   - `tests/web/test_routes/test_trade_entry_chart_pattern.py` for entry-form POST + soft-warn round-trip patterns.

### Total

**22 files** (4 production NEW + 12 production MODIFY + 6 test NEW). Matches spec §2.1 file map.

---

## Compounding-Confound + Discriminating-Test Discipline (binding for ALL tasks)

Per orchestrator-context lessons (Phase 4 R1 + R2; Phase 6 monkeypatch-capture; chart-scope policy v2 R3 + R4; sector capture 2026-04-28 + 2026-04-29 multi-path-ingestion lesson): every task with a discriminating test in this plan includes a **"would this test fail if the implementation never actually called the new code?" sanity-check** sentence in the task body. Where applicable, setups INVERT default sort orders, alphabetical tiebreakers, or fallback values so the bug's output diverges from the correct output. Specific watch items per the writing-plans dispatch brief §5:

- **CC pivot three-site fix (Task 1).** Test setup MUST use a candidate where `entry_target` ≠ `candidates.pivot`. The canonical CC bug screenshot values are `entry_target=$24.13, candidates.pivot=$26.98` — use those (or equivalently distinct values with a wide gap) so a test asserting `$26.98` fails when the implementation renders `$24.13`. Hard-coded "0.00" or "—" defaults are FORBIDDEN as discriminators.

- **Action-button URL distinction (Task 5 / Q7+Q8).** Per-row Enter button URL = `/trades/entry/form?ticker=<X>&origin=hyp-recs`; expansion-internal "Take this trade" URL = `/trades/entry/form?ticker=<X>&origin=hyp-recs` (same URL — they differ in placement, label, and styling per spec §3.7 D.3, NOT in target URL). The discriminating test for Q7 vs the watchlist Enter is the `&origin=hyp-recs` query param — watchlist Enter does NOT carry it; hyp-recs Enter DOES. Test setup must include both surfaces in the same render to discriminate.

- **Origin-aware entry form (Tasks 6 + 7 + 8 + 9).** Tests MUST use distinct `origin` values across cases (`watchlist` vs `hyp-recs`) and assert on the SPECIFIC rendered value, NOT just "origin field is present." For round-trip tests (Task 8), the assertion must be on the FINAL rendered form's colspan + Cancel target, NOT just on the presence of the hidden field — a hidden field that's read back into a default-coerced value would still pass a "presence" check.

- **Lightning trigger preservation (Task 1).** The lightning trigger fixture must be chosen so the trigger fires under the `entry_target` binding but would NOT fire under the `current_pivot` binding. Spec §4.5 specifies `entry_target=$42.00, current_pivot=$100.00, price=$41.60` — under entry_target binding `41.60 ≥ 0.99 × 42 = 41.58` → fires; under current_pivot binding `41.60 ≥ 0.99 × 100 = 99` → would NOT fire. The test asserts lightning DOES fire after the column-display change, proving the trigger binding survives.

- **HTMX OOB-swap drift (Task 4).** The refresh-route response body MUST be byte-comparable (or structurally-comparable for whitespace) to the full-page render's hyp-recs section HTML. A test that asserts only "response is 200" or "contains a `<table>` tag" is vacuous — the drift bug class is "rendered HTML diverges."

- **Anchor consistency for `origin=hyp-recs` (Task 9).** Test setup MUST insert TWO eval rows: a pipeline-bound completed eval (eval_id=N) + a newer standalone eval (eval_id=N+1) with DIFFERENT sector/industry/pivot/initial_stop values for the same ticker. Build the hyp-recs-origin entry form VM and assert it picks N's values, NOT N+1's. A test using only one eval row cannot discriminate between `latest_completed_pipeline_run` and `latest_evaluation_run_id`.

- **Off-watchlist candidate fallback (Task 7).** Test setup MUST use a ticker NOT on the active watchlist with a candidate row that has non-zero `pivot` and `initial_stop`. The test asserts the form's `entry_price` and `initial_stop` are populated from the candidate values, NOT zero. A test using on-watchlist tickers cannot discriminate (the watchlist always wins; fallback never fires).

- **Test-fixture ticker uniqueness across multi-origin tests.** Per the chart-pattern flag-v1 Phase 4 ticker-symmetry-vacuousness lesson — invert ticker setups so default-sort doesn't accidentally produce the correct-output by coincidence. Use `"AAPL"` for watchlist origin and `"NVDA"` for hyp-recs-origin (different tickers; different alphabetical positions; no overlap). Or use the canonical operator-screenshot pair `"PYPL"` / `"NEM"`.

---

## Per-Task Observable-Verification Subject-Only Grep (binding per orchestrator-context)

Before each task implementation commit, run:

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task <N>'
```

Replace `<N>` with the task number (e.g., `'Task 1'`, `'Task 2'`). The `-E` flag is REQUIRED — git's default BRE treats `+` as literal, returning empty even when matches exist (the "expected empty" output then matches for the wrong reason; see 2026-04-27 ERE refinement lesson). Include the command's output (which should be empty for a fresh task) in the commit body. If the grep returns ANY existing commit subjects with the same task ID, ABORT — a prior subagent or session has already implemented the task.

For Codex/internal-Codex round labels use `'^[a-z]+\([a-z]+\): Codex R[0-9]'` (POSIX `[0-9]` instead of `\d`).

**Cross-plan grep aliasing awareness (per writing-plans brief Appendix B).** Flat `Task N` numbering aliases across plans — `Task 1` matches both this plan's CC pivot fix AND the sector capture plan's migration 0012 task. Executing-plans phase implementer disambiguates by inspecting the matched commits' bodies for the plan-specific subject text. No mitigation needed in this plan.

---

## Commit-Message Convention (4-tier, binding per orchestrator-context)

- **Task implementations:** `feat(<area>): Task N — <description>` or `feat(<area>): Task N.M — <description>`.
- **Internal code-review fix commits:** `fix(<area>): code-review I<n> — <description>` (Phase 5 precedent).
- **Internal-Codex within-task fix commits:** `fix(<area>): Codex R<n> Major <m> (internal) — <description>`.
- **Adversarial review-fix commits (orchestrator wrapper):** `fix(<area>): Codex R<n> Major <m> — <description>`.
- **Format-only / cleanup commits:** `style(<area>): <description>` (no task ID).

No Claude co-author footer. No `--no-verify`. No amending. Conventional-commits subject prefix MUST match the regex above so the observable-verification grep finds exactly one match per task after commit.

---

## Task 1: CC pivot bug fix — three render sites + WatchlistRowVM

**Why first.** Per spec §7.1 step 1: "Touches `partials/watchlist_row.html.j2`, `partials/watchlist_top5_section.html.j2`, `watchlist.html.j2`, `view_models/watchlist.py`, `routes/watchlist.py`. No coupling to the rest of this dispatch. Land + verify cross-surface consistency before any hyp-recs work begins. Single-task revert if anything breaks."

**Bug.** `partials/watchlist_row.html.j2:16` renders `{{ '%.2f' | format(w.entry_target or 0) }}` under a column header that says "Pivot." `WatchlistEntry.entry_target` is the value frozen when the operator added the ticker to the watchlist; `candidates.pivot` is the current pipeline-eval pivot. After a pivot rebase / VCP re-evaluation, the ticker shows a stale value under "Pivot." The hyp-recs flat table already renders the current pivot via `candidates_by_ticker[ticker].pivot` (`pivot_price` field on `HypothesisRecommendation`); the trade-entry form's existing behavior is to read sector/industry from candidates but to derive `entry_price` and `initial_stop` from the live PriceCache + watchlist values, NOT from the candidate pivot. (Task 7 of THIS plan extends the entry form to also fall back to `candidate.pivot` for off-watchlist hyp-recs origin, gated tightly so default/watchlist origin is unchanged.) The cross-surface inconsistency the CC pivot fix closes is between the watchlist's "Pivot" column (stale `entry_target`) and the hyp-recs flat table's "Pivot" column (current `candidates.pivot`) — the fix renders `candidates.pivot` on watchlist's column too, across ALL THREE render sites; lightning trigger logic (line 7) stays bound to `entry_target` per locked decision §1.1 #4.

**Three render sites (per spec §3.9, R1-Major-3 + R2-Major-1 resolutions):**
1. `partials/watchlist_top5_section.html.j2` — dashboard top-5 path (`dashboard.html.j2:15` includes this section; it's where the `<tbody>` iteration over `vm.watchlist_top5` happens).
2. `templates/watchlist.html.j2` — standalone watchlist page (iterates rows at line 13).
3. `WatchlistRowVM` at `swing/web/view_models/watchlist.py` + `swing/web/routes/watchlist.py` `/watchlist/{ticker}/row` close-path. Without this, the watchlist's expand-then-close cycle would revert the Pivot column to `entry_target` exactly when the operator most needs the current value.

**Files:**
- Modify: `swing/web/templates/partials/watchlist_row.html.j2:16` — change render expression; preserve lightning trigger at line 7.
- Modify: `swing/web/templates/partials/watchlist_top5_section.html.j2` — add `{% set current_pivot %}` before row include.
- Modify: `swing/web/templates/watchlist.html.j2` — add `{% set current_pivot %}` before row include.
- Modify: `swing/web/view_models/watchlist.py` — `WatchlistRowVM` gains `current_pivot: float | None = None`; `build_watchlist_row` populates it.
- Modify: `swing/web/routes/watchlist.py` — `/watchlist/{ticker}/row` template-context dict gains `current_pivot=row_vm.current_pivot`.
- Test (NEW): `tests/web/test_watchlist_pivot_column.py` — 6 discriminating tests covering all three render sites + dash sentinel + lightning trigger preservation.

**Discriminating-test sanity-check.** Each test uses a candidate where `entry_target=$42.00` and `candidates.pivot=$44.50` so a pre-fix renderer (which uses `entry_target`) would emit `$42.00` and a post-fix renderer (which uses `current_pivot`) would emit `$44.50` — the assertion targets `$44.50` and FAILS pre-fix. **Would this test fail if the implementation never actually called the new code?** Yes — pre-fix render path returns `$42.00`; the assertion `assert "$44.50" in body` fails explicitly. Lightning trigger fixture chosen so the trigger fires under `entry_target` binding but would NOT fire under `current_pivot` binding (per §"Discriminating-Test Discipline" above): `entry_target=$42.00, current_pivot=$100.00, price=$41.60` → `41.60 ≥ 0.99 × 42 = 41.58` (fires); `41.60 ≥ 0.99 × 100 = 99` (would NOT fire). Test asserts the lightning glyph IS present after the column-display change.

- [ ] **Step 1.1: Verify current state.**

```bash
cd c:/Users/rwsmy/swing-trading
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 1' | head -20
git status --short
```

Expected: `git log` returns prior plans' Task 1 subjects (cross-plan aliasing — read each commit body to confirm it's a different plan's Task 1, NOT this plan's). Specifically the sector capture plan's `Task 1 — migration 0012 adds sector + industry to candidates + trades` is expected; if any commit subject matches `Task 1` AND the body references this hyp-recs plan, ABORT (a prior subagent ran the task).

`git status` should be clean.

- [ ] **Step 1.2: Verify the bug exists.** Read `swing/web/templates/partials/watchlist_row.html.j2` and confirm line 16 renders `{{ '%.2f' | format(w.entry_target or 0) }}` (NOT `current_pivot`). Read `swing/web/templates/partials/watchlist_top5_section.html.j2` and confirm there is NO `{% set current_pivot %}` line before the row include. Read `swing/web/templates/watchlist.html.j2` and confirm same. Read `swing/web/view_models/watchlist.py` and confirm `WatchlistRowVM` has fields `(w, price, tags, pattern_tag)` only — no `current_pivot`.

If any verification fails, ABORT — the bug state has changed since plan-authoring; surface in the executing-plans dispatch return report.

- [ ] **Step 1.3: Write the failing tests.**

Create `tests/web/test_watchlist_pivot_column.py`:

```python
"""CC pivot bug fix — discriminating regression across all three render sites.

Spec §3.9 — Q-G resolution; R1-Major-3 + R2-Major-1.

Each test uses entry_target=$42.00 vs candidates.pivot=$44.50 so the
pre-fix path (entry_target binding) and post-fix path (current_pivot
binding) produce visually distinct output. Lightning trigger fixture
asserts the trigger DOES fire under the entry_target binding even
after the column display switches to current_pivot — proving the
trigger binding survives the column-display change.
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import Config
from swing.web.app import create_app


# Tests inject the `sample_config` fixture from tests/conftest.py:41
# (verified at plan-authoring time). All test functions take
# `sample_config` as a parameter; assign `cfg = sample_config`.


from swing.data.models import WatchlistEntry


def _make_watchlist_entry(
    *,
    ticker: str,
    entry_target: float | None = None,
    initial_stop_target: float | None = None,
    last_close: float | None = None,
    last_adr_pct: float = 2.0,
) -> WatchlistEntry:
    """Factory matching swing/data/models.py:130-145 dataclass shape."""
    return WatchlistEntry(
        ticker=ticker, added_date="2026-04-29",
        last_qualified_date="2026-04-29", status="watch",
        qualification_count=1, not_qualified_streak=0,
        last_data_asof_date="2026-04-28",
        entry_target=entry_target, initial_stop_target=initial_stop_target,
        last_close=last_close, last_pivot=None, last_stop=None,
        last_adr_pct=last_adr_pct, missing_criteria=None, notes=None,
    )


def _seed_watchlist_and_candidate(
    cfg: Config, *, ticker: str, entry_target: float, candidate_pivot: float | None,
    price: float | None,
) -> None:
    """Seed an active watchlist row + an evaluation_run + (optionally) a
    candidate row with `pivot=candidate_pivot`. When `candidate_pivot is
    None`, no candidate row exists for the ticker (fallback path)."""
    from swing.data.db import connect, ensure_schema
    from swing.data.repos.watchlist import upsert_watchlist_entry

    ensure_schema(cfg.paths.db_path)
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(
                conn,
                _make_watchlist_entry(
                    ticker=ticker,
                    entry_target=entry_target,
                    initial_stop_target=entry_target * 0.95,
                    last_close=price,
                ),
            )
            # Insert a completed pipeline_run + evaluation_run so the
            # build_watchlist's pipeline-bound anchor can resolve
            # candidates_by_ticker.
            conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count)
                   VALUES ('2026-04-29T09:00:00','2026-04-28','2026-04-29',
                           NULL, 1, 0, 1, 0, 0, 0)"""
            )
            eval_run_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """INSERT INTO pipeline_runs
                   (state, started_ts, finished_ts, action_session_date,
                    data_asof_date, evaluation_run_id, charts_status)
                   VALUES ('complete','2026-04-29T08:00:00',
                           '2026-04-29T09:00:00','2026-04-29','2026-04-28',?,'ok')""",
                (eval_run_id,),
            )
            if candidate_pivot is not None:
                conn.execute(
                    """INSERT INTO candidates
                       (evaluation_run_id, ticker, bucket, close, pivot,
                        initial_stop, adr_pct, tight_streak, pullback_pct,
                        prior_trend_pct, rs_rank, rs_return_12w_vs_spy,
                        rs_method, pattern_tag, notes, sector, industry)
                       VALUES (?, ?, 'watch', ?, ?, ?, 2.0, 5, NULL, NULL,
                               NULL, NULL, 'fallback_spy', NULL, NULL,
                               'Technology', 'Software—Application')""",
                    (eval_run_id, ticker, candidate_pivot,
                     candidate_pivot, candidate_pivot * 0.95),
                )
    finally:
        conn.close()


def test_dashboard_top5_pivot_column_renders_current_pivot(tmp_path: Path):
    """R1-Major-3 site 1: dashboard top-5 watchlist row.

    Discriminating fixture: entry_target=$42.00 vs candidates.pivot=$44.50.
    Pre-fix render emits $42.00; post-fix emits $44.50.
    """
    cfg = _make_cfg(tmp_path)
    _seed_watchlist_and_candidate(
        cfg, ticker="PYPL", entry_target=42.00, candidate_pivot=44.50, price=43.00,
    )
    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    # The Pivot column for PYPL must render $44.50 (current_pivot), NOT $42.00.
    # Use a strong assertion shape: the cell's $44.50 appears AND $42.00 (pre-fix)
    # does NOT appear in any cell of the row.
    assert "$44.50" in body, "post-fix Pivot column must render candidates.pivot"
    assert "$42.00" not in body, (
        "pre-fix Pivot column rendered entry_target — fix did not apply to "
        "watchlist_top5_section.html.j2"
    )


def test_standalone_watchlist_pivot_column_renders_current_pivot(tmp_path: Path):
    """R1-Major-3 site 2: standalone /watchlist page."""
    cfg = _make_cfg(tmp_path)
    _seed_watchlist_and_candidate(
        cfg, ticker="PYPL", entry_target=42.00, candidate_pivot=44.50, price=43.00,
    )
    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.get("/watchlist")
    assert resp.status_code == 200
    body = resp.text
    assert "$44.50" in body
    assert "$42.00" not in body


def test_watchlist_row_close_path_pivot_column_renders_current_pivot(tmp_path: Path):
    """R1-Major-3 site 3: GET /watchlist/{ticker}/row close-path.

    Without the WatchlistRowVM.current_pivot extension, this would revert
    to $42.00 (entry_target) post-close, recreating the bug exactly when
    the operator most needs the current value.
    """
    cfg = _make_cfg(tmp_path)
    _seed_watchlist_and_candidate(
        cfg, ticker="PYPL", entry_target=42.00, candidate_pivot=44.50, price=43.00,
    )
    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.get(
            "/watchlist/PYPL/row",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200
    body = resp.text
    assert "$44.50" in body, (
        "WatchlistRowVM.current_pivot did not propagate to the row-collapse "
        "render path"
    )
    assert "$42.00" not in body


def test_pivot_column_falls_back_to_entry_target_when_no_candidate(tmp_path: Path):
    """When candidates_by_ticker has no row for the ticker (rotated out
    of finviz; not an open trade), the Pivot column falls back to
    entry_target — the fix should not REGRESS this path."""
    cfg = _make_cfg(tmp_path)
    _seed_watchlist_and_candidate(
        cfg, ticker="NEM", entry_target=42.00, candidate_pivot=None, price=43.00,
    )
    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    # Falls back to entry_target.
    assert "$42.00" in body


def test_pivot_column_dash_when_both_absent(tmp_path: Path):
    """R1-Minor-3 dash sentinel: when candidate_pivot is absent AND
    entry_target is None, the cell renders '—' (NOT $0.00)."""
    cfg = _make_cfg(tmp_path)
    # entry_target=None requires a watchlist row with NULL entry_target;
    # construct directly via SQL since upsert_watchlist_entry does not
    # accept None.
    from swing.data.db import connect, ensure_schema
    ensure_schema(cfg.paths.db_path)
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO watchlist_entries
                   (ticker, entry_target, initial_stop_target, last_close,
                    last_adr_pct, added_session, removed_session)
                   VALUES ('NEM', NULL, NULL, 43.00, 2.0, NULL, NULL)"""
            )
            # No evaluation_run / candidate so candidates_by_ticker is empty.
    finally:
        conn.close()
    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    # The Pivot cell for NEM renders '—', NOT '$0.00'.
    assert "$0.00" not in body, (
        "R1-Minor-3 dash sentinel: missing pivot must render '—', not '$0.00'"
    )


def test_lightning_trigger_unchanged_uses_entry_target(tmp_path: Path):
    """Q4 + spec §3.8 — lightning trigger stays bound to entry_target.

    Discriminating fixture chosen so the trigger fires under entry_target
    binding but would NOT fire under current_pivot binding:
      - entry_target = $42.00; current_pivot = $100.00; price = $41.60.
      - 41.60 ≥ 0.99 × 42 = 41.58 → lightning fires (entry_target binding).
      - 41.60 ≥ 0.99 × 100 = 99   → would NOT fire (current_pivot binding).
    Asserting the lightning glyph IS present proves the trigger binding
    survives the column-display change.
    """
    cfg = _make_cfg(tmp_path)
    _seed_watchlist_and_candidate(
        cfg, ticker="PYPL", entry_target=42.00, candidate_pivot=100.00, price=41.60,
    )
    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    body = resp.text
    assert "⚡" in body, (
        "Lightning trigger must remain bound to entry_target after CC pivot "
        "fix — fired at $41.60 ≥ 0.99 × $42.00"
    )
    # Sanity: the column itself shows current_pivot ($100.00).
    assert "$100.00" in body
```

> **Test-helper bootstrap (R3-Major-2 Codex fix).** The plan's `_make_cfg(tmp_path)` calls assume a `tests.conftest.minimal_config_for_tests` helper that does NOT exist. The actual helper in `tests/conftest.py` is the `sample_config(tmp_path)` **fixture** (line 41) — see verification at plan-time:
>   ```bash
>   grep -n "^def\|^class\|^@" tests/conftest.py
>   # → tmp_db, ohlcv_factory, sample_config (NO minimal_config_for_tests)
>   ```
> Two binding substitutions for every test in this plan:
>   1. **Replace `_make_cfg(tmp_path)` calls with the `sample_config` fixture.** Tests should take `sample_config` as a parameter:
>      ```python
>      def test_foo(sample_config, tmp_path):  # use sample_config directly
>          cfg = sample_config
>          # ... existing test body ...
>      ```
>      OR (when an existing test already takes `tmp_path`) reuse `sample_config` and drop the `_make_cfg` call.
>   2. **Replace `from tests.conftest import minimal_config_for_tests` imports** with NO import (the fixture is auto-discovered by pytest).

> **WatchlistEntry constructor + watchlist table — pseudocode → factory substitution (R2-Major-1 Codex fix).** The actual `WatchlistEntry` dataclass at `swing/data/models.py:130-145` has more required fields than the simplified test snippets in this plan use. Required fields include: `added_date`, `last_qualified_date`, `status`, `qualification_count`, `not_qualified_streak`, `last_data_asof_date`, `last_pivot`, `last_stop`, `missing_criteria`, `notes`. There is NO `added_session` / `removed_session` field; the actual table is `watchlist`, NOT `watchlist_entries`.
>
> **Wherever this plan's test-code blocks call `WatchlistEntry(...)` directly OR show direct SQL against `watchlist_entries`, treat those as PSEUDOCODE.** The implementer MUST:
>   1. Locate an existing `WatchlistEntry` factory in the test suite (search: `grep -rn "WatchlistEntry(" tests/` — the factory likely lives in `tests/conftest.py` or `tests/web/test_view_models/test_watchlist.py`). If none exists, define a local `_make_watchlist_entry(*, ticker, entry_target=None, initial_stop_target=None, last_close=None, last_adr_pct=2.0)` helper at the top of each test file. Helper body:
>      ```python
>      def _make_watchlist_entry(*, ticker, entry_target=None, initial_stop_target=None,
>                                 last_close=None, last_adr_pct=2.0):
>          return WatchlistEntry(
>              ticker=ticker, added_date="2026-04-29",
>              last_qualified_date="2026-04-29", status="watch",
>              qualification_count=1, not_qualified_streak=0,
>              last_data_asof_date="2026-04-28",
>              entry_target=entry_target, initial_stop_target=initial_stop_target,
>              last_close=last_close, last_pivot=None, last_stop=None,
>              last_adr_pct=last_adr_pct, missing_criteria=None, notes=None,
>          )
>      ```
>   2. Use `upsert_watchlist_entry(conn, _make_watchlist_entry(ticker=..., entry_target=..., initial_stop_target=..., last_close=...))` everywhere this plan calls `WatchlistEntry(...)` directly or shows direct INSERT SQL against `watchlist_entries`.
>   3. The plan's `test_pivot_column_dash_when_both_absent` (Task 1) currently shows `INSERT INTO watchlist_entries (ticker, entry_target, ...)` — the actual table is `watchlist` and the column set is much wider. Replace the direct SQL with `upsert_watchlist_entry(conn, _make_watchlist_entry(ticker="NEM", entry_target=None, initial_stop_target=None, last_close=43.00))` (NULL `entry_target` is the discriminating fixture for the dash-sentinel test).
>
> This substitution is binding for EVERY `WatchlistEntry(...)` call and every `INSERT INTO watchlist_entries` SQL block in the plan, including those in Tasks 1, 5, 6, 7, 8, 9. The plan's pseudocode is for documentation clarity; the implementer compiles it through the factory.

- [ ] **Step 1.4: Run the failing tests.**

```bash
cd c:/Users/rwsmy/swing-trading
python -m pytest tests/web/test_watchlist_pivot_column.py -v
```

Expected: All 6 tests FAIL — pre-fix the watchlist Pivot column renders `$42.00` (entry_target), the assertions on `$44.50` fail across `test_dashboard_top5_pivot_column_renders_current_pivot`, `test_standalone_watchlist_pivot_column_renders_current_pivot`, `test_watchlist_row_close_path_pivot_column_renders_current_pivot`. `test_pivot_column_falls_back_to_entry_target_when_no_candidate` may pass pre-fix (the pre-fix render is also `$42.00` from `entry_target`). `test_pivot_column_dash_when_both_absent` fails pre-fix (renders `$0.00`). `test_lightning_trigger_unchanged_uses_entry_target` may pass or fail pre-fix depending on `$100.00` cell render — it serves as a forward-regression guard. Implementer documents observed FAIL list in commit body.

- [ ] **Step 1.5: Modify `swing/web/templates/partials/watchlist_row.html.j2:16`.**

```jinja
{# OLD line 16: -#}
{# <td>${{ '%.2f' | format(w.entry_target or 0) }}</td> -#}

{# NEW line 16: -#}
<td>{% if current_pivot is not none %}${{ '%.2f' | format(current_pivot) }}{% elif w.entry_target %}${{ '%.2f' | format(w.entry_target) }}{% else %}—{% endif %}</td>
```

Lightning trigger at line 7 is **unchanged**:

```jinja
{% if price and w.entry_target and price.price >= w.entry_target * 0.99 %}⚡{% endif %}
```

- [ ] **Step 1.6: Modify `swing/web/templates/partials/watchlist_top5_section.html.j2`.**

Insert `{% set current_pivot %}` immediately before the row include:

```jinja
{% for w in vm.watchlist_top5 %}
  {% set price = vm.watchlist_last_prices.get(w.ticker) %}
  {% set tags = vm.flag_tags.get(w.ticker, ()) %}
  {% set pattern_tag = vm.pattern_tags.get(w.ticker) %}
  {% set current_pivot = vm.candidates_by_ticker[w.ticker].pivot if w.ticker in vm.candidates_by_ticker else None %}
  {% include "partials/watchlist_row.html.j2" %}
{% endfor %}
```

- [ ] **Step 1.7: Modify `swing/web/templates/watchlist.html.j2`.**

Insert `{% set current_pivot %}` immediately before the row include at line 13:

```jinja
{% for w in vm.rows %}
  {% set price = vm.watchlist_last_prices.get(w.ticker) %}
  {% set tags = vm.flag_tags.get(w.ticker, ()) %}
  {% set pattern_tag = vm.pattern_tags.get(w.ticker) %}
  {% set current_pivot = vm.candidates_by_ticker[w.ticker].pivot if w.ticker in vm.candidates_by_ticker else None %}
  {% include "partials/watchlist_row.html.j2" %}
{% endfor %}
```

- [ ] **Step 1.8: Modify `WatchlistRowVM` in `swing/web/view_models/watchlist.py`.**

```python
@dataclass(frozen=True)
class WatchlistRowVM:
    """Compact-row context for the /watchlist/<ticker>/row collapse path.

    Mirrors the (w, price, tags) shape `partials/watchlist_row.html.j2`
    expects so the route handler can render that partial directly.

    Phase 4 Task 4.4: `pattern_tag` is a parallel field — independent of
    `tags` so the sort surface (which the row VM does not participate
    in) cannot drift. Default None matches the template's
    `{% if pattern_tag %}` guard.

    CC-pivot R1-Major-3 (this plan, Task 1): `current_pivot` carries the
    candidates.pivot value for the row's ticker so the close-path render
    surfaces the same value the dashboard top-5 and standalone watchlist
    surface — without this field, expand-then-close would revert the
    Pivot column to entry_target.
    """
    w: WatchlistEntry
    price: PriceSnapshot | None
    tags: tuple[str, ...]
    pattern_tag: str | None = None
    current_pivot: float | None = None
```

Update `build_watchlist_row` to populate `current_pivot`. The function already builds `by_ticker = {c.ticker: c for c in candidates}` (verified at the existing implementation circa line 216). Add `current_pivot=by_ticker[ticker].pivot if ticker in by_ticker else None` to the returned `WatchlistRowVM`:

```python
return WatchlistRowVM(
    w=row, price=snap, tags=tags, pattern_tag=pattern_tag,
    current_pivot=(by_ticker[ticker].pivot if ticker in by_ticker else None),
)
```

- [ ] **Step 1.9: Modify `swing/web/routes/watchlist.py`** to pass `current_pivot` into the row template-context dict:

```python
return request.app.state.templates.TemplateResponse(
    request, "partials/watchlist_row.html.j2",
    {
        "w": row_vm.w,
        "price": row_vm.price,
        "tags": row_vm.tags,
        "pattern_tag": row_vm.pattern_tag,
        "current_pivot": row_vm.current_pivot,
    },
)
```

- [ ] **Step 1.10: Run the tests; expect all 6 to PASS.**

```bash
cd c:/Users/rwsmy/swing-trading
python -m pytest tests/web/test_watchlist_pivot_column.py -v
```

Expected: 6 PASS.

- [ ] **Step 1.11: Run the full fast suite.**

```bash
python -m pytest -m "not slow" -q
```

Expected: 1228 + 6 = 1234 passing (8 deselected). Test-count drift gotcha: trust pytest output, not plan-pinned counts.

- [ ] **Step 1.12: Observable-verification grep.**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 1' | head -20
```

Inspect each match. Sector capture plan's `Task 1` is expected to match — confirm the body references the sector plan, NOT this hyp-recs plan. If any match references this plan, ABORT (a prior subagent ran the task).

- [ ] **Step 1.13: Commit.**

```bash
git add tests/web/test_watchlist_pivot_column.py \
  swing/web/templates/partials/watchlist_row.html.j2 \
  swing/web/templates/partials/watchlist_top5_section.html.j2 \
  swing/web/templates/watchlist.html.j2 \
  swing/web/view_models/watchlist.py \
  swing/web/routes/watchlist.py
git commit -m "$(cat <<'EOF'
feat(web): Task 1 — CC pivot bug fix across 3 watchlist render sites

Fixes the watchlist Pivot column rendering frozen-at-add entry_target
under a header that says Pivot. Now renders candidates.pivot from the
latest evaluation across all three render sites: dashboard top-5
(watchlist_top5_section.html.j2), standalone /watchlist page, and
/watchlist/{ticker}/row close-path (WatchlistRowVM.current_pivot).

Lightning trigger at watchlist_row.html.j2:7 unchanged — stays bound
to entry_target per Q4 lock + Tier-3 #5 future-decision reminder.

Discriminating regression test uses entry_target=$42.00 vs
candidates.pivot=$44.50 across all three sites; lightning-trigger
fixture asserts the trigger fires at $41.60 ≥ 0.99 × $42.00 (which
would NOT fire under a current_pivot binding at $100.00) so the
trigger binding is verified to survive the column-display change.

Spec §3.9 — Q-G resolution; R1-Major-3 + R2-Major-1 + R1-Minor-3.
EOF
)"
```

---

## Task 2: `Config.web.chase_factor` field

**Why second.** Per spec §7.1 step 2: "Pure config addition. Lands without any template change; consumed only by §3.5.3's `build_hyp_recs_expanded`."

**Files:**
- Modify: `swing/config.py:140-162` — `Web` dataclass gains `chase_factor: float = 0.01` trailing-default field.
- Test: extend `tests/web/test_config_web.py` (existing file with `Config.web.*` attribute tests). Add a single discriminating test — full unit-test layer is overkill for a one-line dataclass field, BUT the test must discriminate "field exists" from "field has correct default."

**Discriminating-test sanity-check.** The test asserts both `hasattr(cfg.web, "chase_factor")` AND `cfg.web.chase_factor == 0.01`. A test that only checks `hasattr` would pass under any default (including `0.0`); a test that checks `0.01` discriminates default-correctness. **Would this test fail if the implementation never actually set the field?** Yes — `getattr(cfg.web, "chase_factor")` raises `AttributeError`.

**Toml-shadowing audit (binding per writing-plans brief §4 criterion 9 + spec §3.1).** Before implementing, run:

```bash
cd c:/Users/rwsmy/swing-trading
grep -rn "chase_factor" --include="*.toml" .
```

**Expected output: zero hits** (verified at plan-authoring time: `chase_factor` appears only in docs and the spec, NEVER in any tracked toml). If the grep returns ANY hits in tracked toml files, ABORT — the multi-path-ingestion failure class would activate. Phase 5 (Configuration page) is the proper surface for toml override; until then, operators wanting an override write the value into their local toml as a deliberate opt-in.

- [ ] **Step 2.1: Verify current state.**

```bash
cd c:/Users/rwsmy/swing-trading
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 2' | head -20
git status --short
grep -rn "chase_factor" --include="*.toml" .
grep -n "chase_factor" swing/config.py
```

Expected:
- `git log` returns prior plans' Task 2 subjects (cross-plan aliasing); confirm none reference this hyp-recs plan.
- `git status` clean (Task 1 committed).
- toml grep: empty.
- `swing/config.py` grep: empty (the field doesn't exist yet).

If any check fails, ABORT.

- [ ] **Step 2.2: Write the failing test.**

Open `tests/web/test_config_web.py` and append (or insert near similar `Config.web.*` tests):

```python
def test_config_web_chase_factor_default_is_one_percent():
    """Spec §3.1 — Config.web.chase_factor default = 0.01 (1%).

    Sourced from the 2026-04-25 entry-discipline framing: 'wait for pivot,
    don't chase >1% above pivot'. The hyp-recs trade-prep expansion's
    buy_limit = pivot × (1 + chase_factor). Phase 5 surfaces an editor;
    this dispatch ships the storage + read path only.

    Discriminating-test: asserts both attribute existence AND the specific
    0.01 value, so a default of 0.0 or 0.02 would fail.
    """
    from swing.config import Web

    web = Web()
    assert hasattr(web, "chase_factor"), (
        "spec §3.1 requires Config.web.chase_factor field"
    )
    assert web.chase_factor == 0.01, (
        f"chase_factor default must be 0.01 (1%); got {web.chase_factor}"
    )


def test_config_web_chase_factor_no_toml_shadow():
    """Spec §3.1 — toml-shadowing audit.

    Per the 2026-04-29 multi-path-ingestion lesson + the prior aeb2084
    lesson, the field MUST NOT have a row in any GIT-TRACKED toml file
    in V1. Phase 5 (configuration page) surfaces all Web overrides
    together; until then, operators write the value into their local
    untracked toml as a deliberate opt-in (NOT scanned by this audit).

    R1-Major-4 + R3-Minor-1 (Codex) — implemented in pure Python rather
    than shelling out to `grep` (portable Win/Unix; no PATH dependency)
    AND scoped strictly to git-tracked files via `git ls-files` (a
    developer's local untracked `swing.config.toml` override is NOT
    a shadowing concern; the audit catches only what's committed to
    the repo).
    """
    import subprocess
    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    # Use git ls-files to enumerate tracked toml files. Falls back to
    # an empty set if git is unavailable (the assertion is then
    # vacuously true — surface in CI logs that the audit was skipped).
    try:
        result = subprocess.run(
            ["git", "ls-files", "*.toml"],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        pytest.skip("git unavailable; toml-shadowing audit skipped")
        return
    tracked_tomls = [
        repo_root / line.strip()
        for line in result.stdout.splitlines()
        if line.strip()
    ]
    offenders: list[tuple[Path, int, str]] = []
    for tomlfile in tracked_tomls:
        if not tomlfile.exists():
            continue
        try:
            lines = tomlfile.read_text(encoding="utf-8").splitlines()
        except (UnicodeDecodeError, OSError):
            continue
        for lineno, line in enumerate(lines, start=1):
            if "chase_factor" in line:
                offenders.append((tomlfile, lineno, line))
    # docs/ matches are in the spec + brief documents; those are NOT
    # toml shadowing. (No tracked toml under docs/ at plan-time, but
    # filter defensively.)
    offenders = [
        (p, ln, line) for (p, ln, line) in offenders
        if "docs" not in p.parts
    ]
    assert offenders == [], (
        "chase_factor must not appear in any GIT-TRACKED toml file"
        " (multi-path-ingestion lesson). Offenders:\n"
        + "\n".join(f"  {p}:{ln}: {line}" for p, ln, line in offenders)
    )
```

> **Test placement.** If `tests/web/test_config_web.py` already imports `Web` and has similar `test_config_web_*_default` tests, append to that file. Otherwise (only if the file's structure is incompatible), create `tests/test_config_web_chase_factor.py` at the project root tests/ — but the test file convention is `tests/web/test_config_web.py`; prefer extension.

- [ ] **Step 2.3: Run the failing test.**

```bash
cd c:/Users/rwsmy/swing-trading
python -m pytest tests/web/test_config_web.py::test_config_web_chase_factor_default_is_one_percent tests/web/test_config_web.py::test_config_web_chase_factor_no_toml_shadow -v
```

Expected: `test_config_web_chase_factor_default_is_one_percent` FAILS (AttributeError: `Web` object has no attribute `chase_factor`). `test_config_web_chase_factor_no_toml_shadow` PASSES (toml grep is already clean).

- [ ] **Step 2.4: Add the field to `swing/config.py`.**

Edit `swing/config.py` `Web` dataclass (after line 162 `flag_pattern_display_threshold: float = 0.0`):

```python
@dataclass(frozen=True)
class Web:
    # ... existing fields preserved ...
    flag_pattern_display_threshold: float = 0.0
    # Spec §3.1 (hyp-recs trade-prep expansion 2026-04-29): chase factor
    # used by HypRecsExpandedVM.buy_limit = pivot × (1 + chase_factor).
    # Operator's pure-trigger discipline (2026-04-25): wait for pivot,
    # don't chase >1% above pivot. Phase 5 surfaces an editor; this
    # dispatch ships the storage + read path. Toml-shadowing audit
    # (Q-F resolution): no row in swing.config.toml — the field is
    # CODE-ONLY in V1.
    chase_factor: float = 0.01
```

- [ ] **Step 2.5: Run the test; expect PASS.**

```bash
python -m pytest tests/web/test_config_web.py -v
```

Expected: existing tests + 2 new tests all pass.

- [ ] **Step 2.6: Run the full fast suite.**

```bash
python -m pytest -m "not slow" -q
```

Expected: 1234 + 2 = 1236 passing (8 deselected).

- [ ] **Step 2.7: Observable-verification grep.**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 2' | head -20
```

Confirm no match references this hyp-recs plan.

- [ ] **Step 2.8: Commit.**

```bash
git add tests/web/test_config_web.py swing/config.py
git commit -m "$(cat <<'EOF'
feat(config): Task 2 — Config.web.chase_factor field default 0.01

Adds the chase factor configuration field consumed by the hyp-recs
trade-prep expansion (HypRecsExpandedVM.buy_limit = pivot × (1 +
chase_factor)). Default 0.01 sourced from the 2026-04-25
entry-discipline framing: 'wait for pivot, don't chase >1% above
pivot'.

Toml-shadowing audit (Q-F resolution; multi-path-ingestion lesson):
clean — no row in swing.config.toml. Phase 5 surfaces an editor
for all Web-scoped operator-tunable fields together; this dispatch
ships only the storage + read path.

Spec §3.1.
EOF
)"
```

---

## Task 3: Extract `_build_active_recommendations` shared helper

**Why third.** Per spec §7.1 step 4 (re-ordered to land before the refresh route so the shared helper is available when Task 4 introduces `build_hyp_recs_section`). Pure refactor; ZERO behavior change. Sets up Task 4 (`/hyp-recs/refresh`) and Task 5 (`build_hyp_recs_expanded`'s peers in `dashboard.py`) to consume a single source of truth for `active_recommendations` construction.

**The refactor.** `swing/web/view_models/dashboard.py:552-581` currently inlines the `HypothesisRecommendation` tuple construction inside `build_dashboard`. Extract it into a module-level `_build_active_recommendations(*, conn, cfg, prices, candidates_by_ticker, top_recommendations, progress_by_id, target_by_id) -> tuple[HypothesisRecommendation, ...]` helper. `build_dashboard` keeps its existing `top_recommendations + progress_by_id + target_by_id` resolution and calls `_build_active_recommendations(...)` to construct the tuple.

**Files:**
- Modify: `swing/web/view_models/dashboard.py` — extract helper; `build_dashboard` calls it.
- Test: extend `tests/web/test_view_models/test_dashboard_hypothesis_recommendations.py` — add a regression test that asserts `build_dashboard`'s `active_recommendations` output is byte-identical to a baseline (precondition: existing passing tests in this file already cover the dashboard-level happy path; the new test confirms the refactor doesn't perturb the tuple).

**Discriminating-test sanity-check.** The refactor is a pure code-motion (no semantic change). The discriminating test confirms the extracted helper's output equals `build_dashboard`'s `active_recommendations` field for an identical fixture — if the implementation accidentally drops a field or reorders the tuple, the byte-equality assertion fails. **Would this test fail if the implementation never actually called the new code?** The "did this fail if not called" framing doesn't directly apply — Task 3 is a refactor, not a feature. The discriminating signal is "tuple is byte-identical pre-refactor and post-refactor"; an implementation that introduces a regression in the helper (e.g. swaps `progress_n` and `progress_target` field positions) would fail the assertion.

- [ ] **Step 3.1: Verify current state.**

```bash
cd c:/Users/rwsmy/swing-trading
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 3' | head -20
git status --short
grep -n "_build_active_recommendations\|active_recommendations = tuple" swing/web/view_models/dashboard.py
```

Expected:
- `git log` returns prior plans' Task 3 subjects (sector capture had Task 3 = pipeline runner sector/industry plumbing); confirm none reference this hyp-recs plan.
- `git status` clean.
- `grep` returns the existing `active_recommendations = tuple(...)` line (~552) and NO existing `_build_active_recommendations` definition.

- [ ] **Step 3.2: Read the current implementation.** Confirm `swing/web/view_models/dashboard.py:552-581` matches the spec's reference text:

```python
active_recommendations = tuple(
    HypothesisRecommendation(
        ticker=r.candidate_ticker,
        current_price=(
            prices[r.candidate_ticker].price
            if r.candidate_ticker in prices else None
        ),
        pivot_price=(
            candidates_by_ticker[r.candidate_ticker].pivot
            if r.candidate_ticker in candidates_by_ticker else None
        ),
        hypothesis_id=r.hypothesis_id,
        hypothesis_name=r.hypothesis_name,
        hypothesis_progress_n=(
            progress_by_id[r.hypothesis_id].current_sample
            if r.hypothesis_id in progress_by_id else 0
        ),
        hypothesis_progress_target=(
            progress_by_id[r.hypothesis_id].target_sample
            if r.hypothesis_id in progress_by_id
            else target_by_id.get(r.hypothesis_id, 0)
        ),
        tripwire_fired=r.tripwire_fired,
        tripwire_reason=_tripwire_reason_text(
            progress_by_id.get(r.hypothesis_id),
        ),
        suggested_label=r.suggested_label_descriptive,
    )
    for r in top_recommendations
)
```

If lines have drifted from this text, ABORT and surface in return report — the plan was authored against a specific code state.

- [ ] **Step 3.3: Write the failing regression test.**

Open `tests/web/test_view_models/test_dashboard_hypothesis_recommendations.py` and append (or create the file if it doesn't yet exist — verify with `ls tests/web/test_view_models/test_dashboard_hypothesis_recommendations.py` first):

```python
def test_build_active_recommendations_helper_extracted_matches_build_dashboard(
    seeded_db, monkeypatch, tmp_path,
):
    """Task 3 — pure refactor regression: extract _build_active_recommendations
    helper; the helper's output MUST equal build_dashboard's
    active_recommendations field byte-for-byte.

    Discriminating: if the helper extraction reorders fields, drops a
    field, or swaps progress_n/progress_target, the tuple equality
    fails. The fixture seeds a multi-row scenario so the equality is
    not vacuous on a one-element tuple.
    """
    from swing.web.view_models.dashboard import (
        _build_active_recommendations,
        build_dashboard,
    )
    # The seeded_db fixture from this file's existing scaffolding seeds
    # candidates + watchlist + hypotheses sufficient to populate
    # active_recommendations with at least 2 rows. If the helper does not
    # exist (pre-refactor), the import raises ImportError and the test
    # fails — which is the failing-test state we want before
    # implementing the extraction.
    cfg, cache, executor, ohlcv_cache = _build_test_dependencies(seeded_db, tmp_path)
    full_vm = build_dashboard(
        cfg=cfg, cache=cache, executor=executor, ohlcv_cache=ohlcv_cache,
    )
    expected = full_vm.active_recommendations
    assert len(expected) >= 1, "fixture seeds insufficient data for a discriminating test"

    # Now call the helper directly, threading the same intermediate
    # state. The helper signature is documented in Task 3.4 below.
    from swing.data.db import connect
    from swing.data.repos.hypothesis import list_hypotheses
    from swing.recommendations.hypothesis import (
        match_candidate_to_hypotheses, prioritize_recommendations,
    )
    from swing.web.view_models.dashboard import build_recommendation_progress
    from swing.data.repos.candidates import fetch_candidates_for_run

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            pipe_row = conn.execute(
                """SELECT id, evaluation_run_id FROM pipeline_runs
                   WHERE state='complete'
                   ORDER BY finished_ts DESC, id DESC LIMIT 1"""
            ).fetchone()
            assert pipe_row is not None
            eval_id = pipe_row[1]
            candidates = fetch_candidates_for_run(conn, eval_id)
            candidates_by_ticker = {c.ticker: c for c in candidates}
            registry = list_hypotheses(conn)
            target_by_id = {h.id: h.target_sample_size for h in registry}
            progress_by_id, progress_summaries = (
                build_recommendation_progress(
                    conn, registry,
                    starting_equity=cfg.account.starting_equity,
                )
            )
            all_matches = []
            for c in candidates:
                all_matches.extend(
                    match_candidate_to_hypotheses(c, registry=registry)
                )
            prioritized = prioritize_recommendations(
                all_matches, registry=registry, progress=progress_summaries,
            )
            from swing.web.view_models.dashboard import (
                _RECOMMENDATIONS_TOP_N,
            )
            top_recommendations = list(prioritized[:_RECOMMENDATIONS_TOP_N])
    finally:
        conn.close()
    prices = cache.get_many(
        [r.candidate_ticker for r in top_recommendations],
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )
    helper_result = _build_active_recommendations(
        prices=prices,
        candidates_by_ticker=candidates_by_ticker,
        top_recommendations=top_recommendations,
        progress_by_id=progress_by_id,
        target_by_id=target_by_id,
    )
    assert helper_result == expected, (
        "_build_active_recommendations helper output must equal "
        "build_dashboard's active_recommendations field byte-for-byte"
    )
```

> **Fixture bootstrap.** If `seeded_db` and `_build_test_dependencies` are not already shared in this file, copy from the most-similar existing fixture in `tests/web/test_view_models/test_dashboard_hypothesis_recommendations.py` or `tests/web/test_view_models/test_dashboard.py`. The fixture must seed at least 1 candidate + 1 hypothesis + 1 active_watchlist_entry so `active_recommendations` is non-empty.

- [ ] **Step 3.4: Run the failing test.**

```bash
cd c:/Users/rwsmy/swing-trading
python -m pytest tests/web/test_view_models/test_dashboard_hypothesis_recommendations.py -v -k "extracted_matches_build_dashboard"
```

Expected: FAIL with `ImportError: cannot import name '_build_active_recommendations' from 'swing.web.view_models.dashboard'`.

- [ ] **Step 3.5: Extract the helper.** Edit `swing/web/view_models/dashboard.py`. Define `_build_active_recommendations` at module level (above `build_dashboard`):

```python
def _build_active_recommendations(
    *,
    prices: Mapping[str, "PriceSnapshot"],
    candidates_by_ticker: Mapping[str, "Candidate"],
    top_recommendations: list,
    progress_by_id: Mapping[int, "HypothesisProgress"],
    target_by_id: Mapping[int, int],
) -> tuple["HypothesisRecommendation", ...]:
    """Construct the hyp-recs `active_recommendations` tuple from
    prerequisites. Single source of truth — consumed by:
      - `build_dashboard` (full-page render path);
      - `build_hyp_recs_section` (Task 4: /hyp-recs/refresh route).

    Code motion only — no semantic change vs the inlined tuple
    construction at swing/web/view_models/dashboard.py:552-581 prior
    to this refactor.
    """
    return tuple(
        HypothesisRecommendation(
            ticker=r.candidate_ticker,
            current_price=(
                prices[r.candidate_ticker].price
                if r.candidate_ticker in prices else None
            ),
            pivot_price=(
                candidates_by_ticker[r.candidate_ticker].pivot
                if r.candidate_ticker in candidates_by_ticker else None
            ),
            hypothesis_id=r.hypothesis_id,
            hypothesis_name=r.hypothesis_name,
            hypothesis_progress_n=(
                progress_by_id[r.hypothesis_id].current_sample
                if r.hypothesis_id in progress_by_id else 0
            ),
            hypothesis_progress_target=(
                progress_by_id[r.hypothesis_id].target_sample
                if r.hypothesis_id in progress_by_id
                else target_by_id.get(r.hypothesis_id, 0)
            ),
            tripwire_fired=r.tripwire_fired,
            tripwire_reason=_tripwire_reason_text(
                progress_by_id.get(r.hypothesis_id),
            ),
            suggested_label=r.suggested_label_descriptive,
        )
        for r in top_recommendations
    )
```

> **Type forward-references.** Use string-quoted forward references (`"PriceSnapshot"`, `"Candidate"`, `"HypothesisRecommendation"`, `"HypothesisProgress"`) if the helper definition is placed BEFORE the imported types' definitions in the module. If the existing module imports those types at the top, drop the quotes. Implementer judgment.

Replace the inlined construction in `build_dashboard` (lines 552-581 region):

```python
active_recommendations = _build_active_recommendations(
    prices=prices,
    candidates_by_ticker=candidates_by_ticker,
    top_recommendations=top_recommendations,
    progress_by_id=progress_by_id,
    target_by_id=target_by_id,
)
```

- [ ] **Step 3.6: Run the test; expect PASS.**

```bash
python -m pytest tests/web/test_view_models/test_dashboard_hypothesis_recommendations.py -v -k "extracted_matches_build_dashboard"
```

Expected: PASS.

- [ ] **Step 3.7: Run the full fast suite.**

```bash
python -m pytest -m "not slow" -q
```

Expected: 1236 + 1 = 1237 passing (8 deselected). All previously-passing dashboard tests must remain green — refactor is byte-equivalent.

- [ ] **Step 3.8: Observable-verification grep.**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 3' | head -20
```

Confirm no match references this hyp-recs plan.

- [ ] **Step 3.9: Commit.**

```bash
git add tests/web/test_view_models/test_dashboard_hypothesis_recommendations.py \
  swing/web/view_models/dashboard.py
git commit -m "$(cat <<'EOF'
refactor(web): Task 3 — extract _build_active_recommendations helper

Pure code-motion: extracts swing/web/view_models/dashboard.py:552-581's
inlined HypothesisRecommendation tuple construction into a module-level
_build_active_recommendations(*, prices, candidates_by_ticker,
top_recommendations, progress_by_id, target_by_id) helper. build_dashboard
calls the helper. Zero semantic change — discriminating regression test
asserts byte-equivalence of the active_recommendations tuple before and
after the refactor.

Sets up Task 4 (/hyp-recs/refresh route's build_hyp_recs_section) and
Task 5 (build_hyp_recs_expanded's adjacency in dashboard.py) to consume
the same single source of truth for recommendation construction —
closes the HTMX OOB-swap drift class for the new refresh route per
CLAUDE.md gotcha.

Spec §3.5.4 + §4.6 (R2-Major-2 resolution).
EOF
)"
```

---

## Task 4: `HypRecsSectionVM` + `build_hyp_recs_section` + `GET /hyp-recs/refresh`

**Why fourth.** Per spec §7.1 step 4. Sets up the refresh route the close button (Task 5) and the Cancel button on hyp-recs-origin entry forms (Task 6) will target. Re-ordered ahead of Task 5 (the expansion partial) so the close button has a working target at commit time.

**The shape.** `GET /hyp-recs/refresh` returns the freshly-rendered hyp-recs section (`partials/hypothesis_recommendations.html.j2`) — used by the expansion close button and the hyp-recs-origin entry-form Cancel button (Task 6). The route uses a SCOPED builder (`build_hyp_recs_section`) that resolves ONLY the data needed for hyp-recs (candidates_by_ticker for `pivot_price`; prices for the recommended tickers; progress/registry for the prioritizer). It does NOT call `build_dashboard` — open-trade OHLCV, watchlist top-5, advisories, and status strip are UNTOUCHED on refresh per spec §3.5.4 + §4.6 (R2-Major-2 resolution).

**Cross-panel snapshot consistency caveat (per spec §3.5.4).** The swap target is `#hypothesis-recommendations` only — other dashboard sections retain their full-page-render snapshot. This is inherent to the partial-swap UX and is the intentional V1 trade.

**Files:**
- Create: `swing/web/routes/recommendations.py` — new router, defines `GET /hyp-recs/refresh` (Task 4) and `GET /hyp-recs/{ticker}/expand` (Task 5; just the refresh route here).
- Modify: `swing/web/view_models/dashboard.py` — add `HypRecsSectionVM` dataclass + `build_hyp_recs_section(*, cfg, cache, executor) -> HypRecsSectionVM` builder.
- Modify: `swing/web/app.py` — register the new router (`from swing.web.routes import recommendations as recommendations_route`; `app.include_router(recommendations_route.router)`). `_ROW_TARGET_PREFIXES` extension is deferred to Task 5 (no row-target hyp-rec-row- yet at refresh-route-only stage).
- Test (NEW): `tests/web/test_routes/test_hyp_recs_expand_route.py` — Task 4 seeds with refresh-route tests; subsequent tasks extend.

**Discriminating-test sanity-check.** Tests must catch both correctness (refresh returns the right HTML) AND scoping (refresh does NOT trigger open-trades / OHLCV / watchlist subsystem builds). The scoping test uses monkeypatch sentinels on `build_dashboard` and on the open-trades repo to assert they are NOT called — discriminating because a regression where the refresh handler accidentally re-routes through `build_dashboard` would call those paths. **Would this test fail if the implementation never actually called the new code?** If the implementer stubs the route to return an empty body, the "rendered hyp-recs HTML" assertion fails. If the implementer leaks `build_dashboard` into the route, the sentinel assertion fails.

**HTMX OOB-swap drift discriminating test (per writing-plans brief §5 watch item 3).** A test asserts the refresh-route response body contains the SAME hyp-recs section markup as the full-page dashboard render — confirms `build_hyp_recs_section` and `build_dashboard` produce drift-equivalent hyp-recs HTML. Implementation MUST go through the same `{% include %}` chain (the `partials/hypothesis_recommendations.html.j2` template); the test asserts the section's `<table>`, `<thead>`, and `<tbody>` shape match between the two renders.

- [ ] **Step 4.1: Verify current state.**

```bash
cd c:/Users/rwsmy/swing-trading
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 4' | head -20
git status --short
ls swing/web/routes/recommendations.py 2>&1 | head -5
ls tests/web/test_routes/test_hyp_recs_expand_route.py 2>&1 | head -5
```

Expected:
- `git log` returns prior plans' Task 4 subjects (sector capture had Task 4 = trades repo plumbing); confirm none reference this hyp-recs plan.
- `git status` clean.
- Both `ls` calls report "No such file" — neither file exists yet.

- [ ] **Step 4.2: Write the failing tests.**

Create `tests/web/test_routes/test_hyp_recs_expand_route.py`:

```python
"""GET /hyp-recs/refresh + /hyp-recs/{ticker}/expand route tests.

Tasks 4 + 5 + 6 + 7 + 8 + 9 contribute. Task 4 seeds refresh-route
tests; subsequent tasks extend.

Spec §3.5.4 + §4.6 (R2-Major-2 scoped refresh builder).
Spec §3.5.3 + §3.5.4 + §4.3 (expand route).
"""
from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from swing.config import Config
from swing.web.app import create_app


from swing.data.models import WatchlistEntry


def _make_watchlist_entry(
    *,
    ticker: str,
    entry_target: float | None = None,
    initial_stop_target: float | None = None,
    last_close: float | None = None,
    last_adr_pct: float = 2.0,
) -> WatchlistEntry:
    """Factory matching the actual WatchlistEntry dataclass shape at
    swing/data/models.py:130-145. Populates the boilerplate fields
    (added_date, last_qualified_date, status, qualification_count,
    not_qualified_streak, last_data_asof_date, last_pivot, last_stop,
    missing_criteria, notes) with sensible defaults; tests pass only
    the discriminating fields as overrides.
    """
    return WatchlistEntry(
        ticker=ticker,
        added_date="2026-04-29",
        last_qualified_date="2026-04-29",
        status="watch",
        qualification_count=1,
        not_qualified_streak=0,
        last_data_asof_date="2026-04-28",
        entry_target=entry_target,
        initial_stop_target=initial_stop_target,
        last_close=last_close,
        last_pivot=None,
        last_stop=None,
        last_adr_pct=last_adr_pct,
        missing_criteria=None,
        notes=None,
    )


# Tests inject the `sample_config` fixture from tests/conftest.py:41
# (verified at plan-authoring time). All test functions below take
# `sample_config` as the first parameter; `cfg = sample_config`.


def _seed_hyp_recs_fixture(
    cfg: Config,
    *,
    tickers: list[str] | None = None,
) -> None:
    """Seed enough state for hyp-recs to render at least 1 active
    recommendation. Each ticker gets a candidate row with bucket='aplus'
    + a registered hypothesis + a watchlist row.
    """
    from swing.data.db import connect, ensure_schema
    from swing.data.repos.watchlist import upsert_watchlist_entry

    tickers = tickers or ["NVDA", "AMD"]
    ensure_schema(cfg.paths.db_path)
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # evaluation_run + pipeline_run.
            conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count)
                   VALUES ('2026-04-29T09:00:00','2026-04-28','2026-04-29',
                           NULL, 2, 2, 0, 0, 0, 0)"""
            )
            eval_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """INSERT INTO pipeline_runs
                   (state, started_ts, finished_ts, action_session_date,
                    data_asof_date, evaluation_run_id, charts_status)
                   VALUES ('complete','2026-04-29T08:00:00',
                           '2026-04-29T09:00:00','2026-04-29','2026-04-28',?,'ok')""",
                (eval_id,),
            )
            for tk in tickers:
                upsert_watchlist_entry(
                    conn,
                    _make_watchlist_entry(
                        ticker=tk, entry_target=100.0,
                        initial_stop_target=95.0, last_close=99.0,
                    ),
                )
                conn.execute(
                    """INSERT INTO candidates
                       (evaluation_run_id, ticker, bucket, close, pivot,
                        initial_stop, adr_pct, tight_streak, pullback_pct,
                        prior_trend_pct, rs_rank, rs_return_12w_vs_spy,
                        rs_method, pattern_tag, notes, sector, industry)
                       VALUES (?, ?, 'aplus', 99.0, 100.0, 95.0, 2.0, 5,
                               NULL, NULL, NULL, NULL, 'fallback_spy',
                               NULL, NULL, 'Technology', 'Semiconductors')""",
                    (eval_id, tk),
                )
            # Register one minimal hypothesis matching aplus candidates.
            # NOTE: the actual table is `hypothesis_registry` (NOT
            # `hypotheses`) — verified against
            # swing/data/migrations/0008_hypothesis_registry.sql.
            # Implementer should locate the existing seeding helper used
            # by other dashboard tests:
            # `grep -rn "INSERT INTO hypothesis_registry" tests/`
            # (a known-good fixture lives in
            # tests/web/test_view_models/test_dashboard_hypothesis_recommendations.py).
            # If no shared helper is available, inline the canonical
            # INSERT below — column set matches the migration's CREATE
            # TABLE.
            conn.execute(
                """INSERT INTO hypothesis_registry
                   (id, name, statement, target_sample_size,
                    decision_criteria, status,
                    consecutive_loss_tripwire,
                    absolute_loss_tripwire_pct, created_at)
                   VALUES (1, 'Test hypothesis',
                           'aplus candidates produce R-multiple > 0',
                           30,
                           '{"buckets":["aplus"]}',
                           'active', 5, 0.10,
                           '2026-04-29T09:00:00')"""
            )
    finally:
        conn.close()


def test_refresh_route_returns_section_partial(tmp_path: Path):
    """Spec §3.5.4 R2-Major-2 — refresh route returns the rendered
    hypothesis_recommendations.html.j2 section."""
    cfg = _make_cfg(tmp_path)
    _seed_hyp_recs_fixture(cfg)
    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.get(
            "/hyp-recs/refresh",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200
    body = resp.text
    # The section root element is <section id="hypothesis-recommendations">.
    assert 'id="hypothesis-recommendations"' in body, (
        "refresh route must render the section partial (root element"
        " '<section id=\"hypothesis-recommendations\">')"
    )
    # The section MUST include the rendered table head.
    assert "<thead>" in body
    assert ">Pivot<" in body, (
        "refresh route's rendered section must include the existing Pivot column"
    )


def test_refresh_route_does_not_invoke_full_dashboard_build(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
):
    """R2-Major-2 regression: GET /hyp-recs/refresh must NOT call
    build_dashboard. Discriminating sentinel — a regression where the
    refresh handler reverts to build_dashboard would trip the sentinel.
    """
    cfg = _make_cfg(tmp_path)
    _seed_hyp_recs_fixture(cfg)

    # Replace build_dashboard with a sentinel that raises if called. The
    # refresh route must NOT call it.
    sentinel_calls: list[str] = []
    from swing.web import view_models as _vm_pkg
    from swing.web.view_models import dashboard as dashboard_mod
    original = dashboard_mod.build_dashboard

    def _sentinel(*args, **kwargs):
        sentinel_calls.append("build_dashboard")
        # Defensive: still return a value so a regression-path doesn't
        # crash mid-test — sentinel_calls capture is the assertion.
        return original(*args, **kwargs)

    monkeypatch.setattr(dashboard_mod, "build_dashboard", _sentinel)
    # Also patch the route module's already-bound import (FastAPI may
    # have imported the symbol into the route module's namespace).
    from swing.web.routes import trades as trades_route
    if hasattr(trades_route, "build_dashboard"):
        monkeypatch.setattr(trades_route, "build_dashboard", _sentinel)

    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.get(
            "/hyp-recs/refresh", headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200
    assert sentinel_calls == [], (
        "refresh route must use scoped build_hyp_recs_section, not"
        f" build_dashboard. Sentinel was called: {sentinel_calls}"
    )


def test_refresh_route_renders_drift_equivalent_html_to_full_page(tmp_path: Path):
    """HTMX OOB-swap drift discriminating test (writing-plans brief §5
    watch item 3). The refresh route's hyp-recs section HTML must match
    the full-page render's hyp-recs section HTML — both go through the
    SAME `{% include %}` chain (`partials/hypothesis_recommendations.html.j2`).

    Discriminating: compares the section's structural shape (table head
    column count + each <th> text) between the two renders. A drift
    bug (e.g. refresh adds an extra <th>) would diverge.
    """
    cfg = _make_cfg(tmp_path)
    _seed_hyp_recs_fixture(cfg)
    app = create_app(cfg)
    with TestClient(app) as client:
        full_resp = client.get("/")
        refresh_resp = client.get(
            "/hyp-recs/refresh", headers={"HX-Request": "true"},
        )
    assert full_resp.status_code == 200
    assert refresh_resp.status_code == 200
    # Extract the <thead> region from each. (Simple shape-match —
    # full-page also renders other thead's so we anchor on the
    # hypothesis-recommendations section.)
    import re
    pattern = re.compile(
        r'<section[^>]*id="hypothesis-recommendations"[^>]*>.*?</thead>',
        flags=re.DOTALL,
    )
    full_thead = pattern.search(full_resp.text)
    refresh_thead = pattern.search(refresh_resp.text)
    assert full_thead is not None and refresh_thead is not None, (
        "both renders must contain the hypothesis-recommendations section's"
        " thead — a regression that drops the section entirely fails here"
    )
    # Compare column-header text sequences. Both renders must produce the
    # same ordered list of <th> contents.
    th_pattern = re.compile(r"<th[^>]*>(.*?)</th>", flags=re.DOTALL)
    full_cols = [t.strip() for t in th_pattern.findall(full_thead.group(0))]
    refresh_cols = [t.strip() for t in th_pattern.findall(refresh_thead.group(0))]
    assert full_cols == refresh_cols, (
        "Hyp-recs section's thead column sequence drifts between full-page"
        f" and refresh-route renders. full={full_cols} refresh={refresh_cols}"
    )
```

> **Hypothesis registry seeding.** The minimal `INSERT INTO hypotheses` SQL above is a placeholder; the actual schema may include columns the placeholder omits. Implementer should `Read` `swing/data/migrations/0007_phase3_hypothesis_records.sql` (or whichever migration introduces the `hypotheses` table) AND read the existing fixture `tests/web/test_view_models/test_dashboard_hypothesis_recommendations.py`'s seed pattern, then port the seed verbatim. The discriminating test does NOT depend on the hypothesis content — only on `active_recommendations` being non-empty after the seed.

- [ ] **Step 4.3: Run the failing tests.**

```bash
cd c:/Users/rwsmy/swing-trading
python -m pytest tests/web/test_routes/test_hyp_recs_expand_route.py -v -k "refresh_"
```

Expected: All three FAIL with `404 Not Found` from `client.get("/hyp-recs/refresh")` — the route does not exist.

- [ ] **Step 4.4: Add `HypRecsSectionVM` + `build_hyp_recs_section` to `swing/web/view_models/dashboard.py`.**

```python
@dataclass(frozen=True)
class HypRecsSectionVM:
    """Sub-VM shaped exactly as the hypothesis_recommendations.html.j2
    partial expects (`vm.active_recommendations`). Returned by
    GET /hyp-recs/refresh; renders the same flat-table chevron + Enter
    column markup the full-page render produces.

    Spec §3.5.4 (R2-Major-2 resolution).
    """
    active_recommendations: tuple["HypothesisRecommendation", ...]


def build_hyp_recs_section(
    *, cfg: Config, cache: PriceCache, executor,
) -> HypRecsSectionVM:
    """Refresh-route VM builder. Resolves ONLY the data needed for the
    hyp-recs section: candidates_by_ticker (for pivot_price), prices for
    the recommended tickers (subset, NOT the full watchlist), and the
    progress/registry data the prioritizer needs. Does NOT touch
    open-trade OHLCV, watchlist top-5, advisories, status strip.

    R2-Major-2 motivation: a hyp-recs close-button refresh MUST NOT
    depend on subsystems unrelated to hyp-recs — open-trade OHLCV
    breaker tripping or watchlist sort-anchor mis-alignment must not
    break the close action.

    Spec §3.5.4.
    """
    # Note: build_recommendation_progress is defined in this same
    # module (dashboard.py) so it is already in scope — no import.
    from swing.data.db import connect
    from swing.data.repos.candidates import fetch_candidates_for_run
    from swing.data.repos.hypothesis import list_hypotheses
    from swing.recommendations.hypothesis import (
        match_candidate_to_hypotheses,
        prioritize_recommendations,
    )

    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Anchor on the latest completed pipeline run's evaluation
            # — same anchor build_dashboard uses for candidates_by_ticker.
            pipe_row = conn.execute(
                """SELECT id, evaluation_run_id FROM pipeline_runs
                   WHERE state='complete'
                   ORDER BY finished_ts DESC, id DESC LIMIT 1"""
            ).fetchone()
            if pipe_row is None or pipe_row[1] is None:
                # No completed pipeline yet — return empty section.
                return HypRecsSectionVM(active_recommendations=())
            eval_id = pipe_row[1]
            candidates = fetch_candidates_for_run(conn, eval_id)
            candidates_by_ticker = {c.ticker: c for c in candidates}
            registry = list_hypotheses(conn)
            target_by_id = {h.id: h.target_sample_size for h in registry}
            progress_by_id, progress_summaries = (
                build_recommendation_progress(
                    conn, registry,
                    starting_equity=cfg.account.starting_equity,
                )
            )
            all_matches = []
            for c in candidates:
                all_matches.extend(
                    match_candidate_to_hypotheses(c, registry=registry)
                )
            prioritized = prioritize_recommendations(
                all_matches, registry=registry, progress=progress_summaries,
            )
            top_recommendations = list(prioritized[:_RECOMMENDATIONS_TOP_N])
    finally:
        conn.close()
    recommended_tickers = sorted(
        {r.candidate_ticker for r in top_recommendations}
    )
    prices = cache.get_many(
        recommended_tickers,
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )
    active_recommendations = _build_active_recommendations(
        prices=prices,
        candidates_by_ticker=candidates_by_ticker,
        top_recommendations=top_recommendations,
        progress_by_id=progress_by_id,
        target_by_id=target_by_id,
    )
    return HypRecsSectionVM(active_recommendations=active_recommendations)
```

> **Type-import alignment.** `_RECOMMENDATIONS_TOP_N`, `_build_active_recommendations`, `HypothesisRecommendation`, `Config`, `PriceCache` are already in scope in `swing/web/view_models/dashboard.py`. The new function reuses them — no new top-level imports needed beyond those already present.

- [ ] **Step 4.5: Create `swing/web/routes/recommendations.py`.**

```python
"""Hyp-recs trade-prep expansion routes.

Spec §3.5.4: GET /hyp-recs/refresh (close-button target / hyp-recs-origin
entry-form Cancel target).
Spec §3.5.4: GET /hyp-recs/{ticker}/expand (Task 5; defined here as a
placeholder docstring at Task 4 stage).

Both routes are HTMX-driven; under strict OriginGuard the GET routes
do NOT require HX-Request (only writes do), but the templates expect
the request to come from the dashboard so they include HTMX-specific
markup unconditionally.
"""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from swing.web.view_models.dashboard import build_hyp_recs_section

router = APIRouter()


@router.get("/hyp-recs/refresh", response_class=HTMLResponse)
def hyp_recs_refresh(request: Request):
    """Close-button target. Returns ONLY the freshly-rendered hyp-recs section
    so the closing operator sees current hyp-recs values without rebuilding
    open-trades, watchlist top-5, prices for non-recommended tickers, or
    OHLCV (R2-Major-2 — scoped builder, NOT a full build_dashboard call).

    Cross-panel snapshot consistency caveat: the swap target is
    #hypothesis-recommendations only — other dashboard sections retain
    their full-page-render snapshot. Inherent to the partial-swap UX
    and the intentional V1 trade.
    """
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = request.app.state.templates
    section_vm = build_hyp_recs_section(cfg=cfg, cache=cache, executor=executor)
    return templates.TemplateResponse(
        request,
        "partials/hypothesis_recommendations.html.j2",
        {"vm": section_vm},
    )
```

- [ ] **Step 4.6: Register the router in `swing/web/app.py`.**

Edit the existing import block (currently `from swing.web.routes import (dashboard, journal, pipeline, trades, watchlist)`) and add `recommendations`:

```python
from swing.web.routes import (
    dashboard as dashboard_route,
    journal as journal_route,
    pipeline as pipeline_route,
    recommendations as recommendations_route,
    trades as trades_route,
    watchlist as watchlist_route,
)
app.include_router(dashboard_route.router)
app.include_router(watchlist_route.router)
app.include_router(journal_route.router)
app.include_router(pipeline_route.router)
app.include_router(trades_route.router)
app.include_router(recommendations_route.router)
```

`_ROW_TARGET_PREFIXES` is NOT extended at Task 4 — the prefix `hyp-rec-row-` is added in Task 5 (when row-target swap targets first appear). Until Task 5, no HTMX request will carry `HX-Target: hyp-rec-row-...` so the existing prefix tuple is sufficient.

- [ ] **Step 4.7: Run the tests; expect PASS.**

```bash
python -m pytest tests/web/test_routes/test_hyp_recs_expand_route.py -v -k "refresh_"
```

Expected: 3 PASS.

- [ ] **Step 4.8: Run the full fast suite.**

```bash
python -m pytest -m "not slow" -q
```

Expected: 1237 + 3 = 1240 passing (8 deselected).

- [ ] **Step 4.9: Observable-verification grep.**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 4' | head -20
```

Confirm no match references this hyp-recs plan.

- [ ] **Step 4.10: Commit.**

```bash
git add tests/web/test_routes/test_hyp_recs_expand_route.py \
  swing/web/routes/recommendations.py \
  swing/web/view_models/dashboard.py \
  swing/web/app.py
git commit -m "$(cat <<'EOF'
feat(web): Task 4 — GET /hyp-recs/refresh + scoped build_hyp_recs_section

Adds the refresh route the hyp-recs expansion close button (Task 5) and
the hyp-recs-origin entry-form Cancel button (Task 6) will target.

build_hyp_recs_section is a SCOPED builder — resolves only candidates,
prioritizer state, and prices for the recommended tickers (typically
1-10). It does NOT call build_dashboard (R2-Major-2 resolution); open-
trade OHLCV, watchlist top-5, advisories, and status strip are
untouched on refresh, isolating the close action from unrelated
subsystem failures and avoiding wasted work.

HTMX OOB-swap drift discriminating regression test asserts the refresh
route's section thead column sequence equals the full-page render's
thead column sequence — both go through the SAME
partials/hypothesis_recommendations.html.j2 include chain.

Spec §3.5.4 + §4.6 (R2-Major-2 resolution).
EOF
)"
```

---

## Task 5: Hyp-recs expansion (chevron + Enter col + expansion partial + expand route + Take-this-trade button)

**Why fifth.** Per spec §7.1 step 3 (re-numbered to land after the refresh-route scaffolding so the close button has a working target). This is the largest task; it is split into sub-tasks 5.1–5.7 below. Each sub-task is individually atomic with its own TDD cycle and own commit.

**Scope of Task 5.**
- Sub-task 5.1: `tests/recommendations/test_hypothesis_sizing_twins.py` — sizing-twin pure-function unit tests + commit (no production code yet).
- Sub-task 5.2: `HypRecsExpandedVM` dataclass + `build_hyp_recs_expanded` helper — VM-build tests + commit.
- Sub-task 5.3: `GET /hyp-recs/{ticker}/expand` route + new partials (`hypothesis_recommendations_expanded.html.j2`, `hyp_recs_expand_unavailable.html.j2`) + `_ROW_TARGET_PREFIXES` extension — route + partial tests + commit.
- Sub-task 5.4: Chevron column on flat-table + row-partial extraction (`hypothesis_recommendations_row.html.j2`) — template-render tests + commit.
- Sub-task 5.5: Per-row Enter button (Q7) on the row partial — button-render tests + commit.
- Sub-task 5.6: Take-this-trade button (Q8) on the expansion partial + close button — button-render tests + commit.
- Sub-task 5.7: Sort-neutrality regression test + commit (test-only — sort path is untouched).

**Acknowledged transient state.** Sub-task 5.5 ships the per-row Enter button which emits `?origin=hyp-recs` to the entry-form route. Until Task 6 lands, the GET handler ignores `?origin=` and renders the form with default `origin="watchlist"` (colspan=8 + Cancel `/watchlist/{ticker}/expand`). Each Task 5.x commit is individually green; operator-facing UI is fully coherent only at end-of-plan. Plan-level test fixtures for Q7/Q8 buttons (sub-tasks 5.5, 5.6) assert the BUTTON markup (URL contains `&origin=hyp-recs`), NOT the post-click form-render correctness — the form-render correctness is asserted in Tasks 6-9.

> **Sub-task TDD detail.** Each Task 5.x sub-task follows the same per-task discipline as Tasks 1-4: write failing test → run + observe FAIL → minimal implementation → run + observe PASS → run full fast suite → observable-verification grep → commit. The full step-by-step expansion is omitted here for plan-length budget; the sub-task SCOPE (files / behavior / discriminating-test design) above is binding. Each sub-task commit subject follows the convention `feat(web): Task 5.N — <description>`. Implementer is explicitly authorized to draft step-by-step TDD scaffolding using the Task 1-4 patterns as templates; deviations from spec §3.5 / §3.7 / §4.x require return-report surfacing.

> **Critical sub-task contracts** (binding regardless of how implementer drafts the steps):
>
> **Sub-task 5.1 — Sizing-twin tests (NEW file `tests/recommendations/test_hypothesis_sizing_twins.py`):** at least 6 tests; the discriminating-test pair `test_risk_based_uses_max_floor_when_balance_below_floor` (balance=$1,200 < floor=$7,500 → 18 shares from sizing_equity floor) and `test_cash_feasible_uses_balance_only_not_floor` (same inputs → 3 shares; sizing_equity NOT applied) is mandatory. Plus `test_balance_above_floor_uses_balance_for_both`, `test_infeasible_when_one_share_exceeds_max_risk` (entry=$1000, stop=$999, max_risk_pct=0.0001), `test_no_equity_path` (equity=0 → no_equity), `test_position_cap_actually_binds` (entry=$10, stop=$9.50, max_risk_pct=0.05 → 15 shares; constraint='position_cap'). Tests use only existing `compute_shares` + `sizing_equity`; no new production code. Per spec §3.3.
>
> **Sub-task 5.2 — `HypRecsExpandedVM` + `build_hyp_recs_expanded`** (`swing/web/view_models/dashboard.py`): dataclass shape per spec §3.5.2 (frozen=True; ticker, buy_stop, buy_limit, sell_stop, chase_factor, current_balance, risk_equity, sizing_risk: SizingResult, sizing_cash: SizingResult, sector, industry, data_asof_date, chart_reason, chart_reason_message, pipeline_finished_at). Helper signature: `def build_hyp_recs_expanded(*, conn, cfg: Config, ticker: str, current_balance: float) -> HypRecsExpandedVM | None`. Body per spec §3.5.3: resolves binding via `latest_completed_pipeline_run`; returns None on (no completed pipeline) OR (ticker not in candidates) OR (candidate.pivot is None) OR (compute_shares raises ValueError). Sector/industry coerced to `""` (preserves the empty-string convention; template's `or "—"` fallback fires consistently). At least 9 VM-build tests in NEW file `tests/web/test_view_models/test_hyp_recs_expansion_vm.py` covering: happy path, buy_limit arithmetic, chase_factor threading from config, ticker-not-in-latest-run, no-completed-pipeline-run, anchor consistency (NULL-finished_ts in-flight row must NOT win), degenerate stop returns None, sector/industry threading, sizing twins discriminate (sizing_risk.shares > sizing_cash.shares when balance < floor).
>
> **Sub-task 5.3 — Expand route + partials + `_ROW_TARGET_PREFIXES` extension:**
>   - `swing/web/routes/recommendations.py` gains `GET /hyp-recs/{ticker}/expand` handler (verbatim from spec §3.5.4).
>   - Create `swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2` (verbatim from spec §3.5.6 EXCEPT: omit the Take-this-trade button at this sub-step — Task 5.6 inserts it).
>   - Create `swing/web/templates/partials/hyp_recs_expand_unavailable.html.j2` — `<tr id="hyp-rec-row-{ticker}" class="expand-unavailable"><td colspan="9"><span>{{ message }}</span><button hx-get="/hyp-recs/refresh" hx-target="#hypothesis-recommendations" hx-swap="outerHTML" hx-headers='{"HX-Request": "true"}'>Close</button></td></tr>`.
>   - Extend `swing/web/app.py:31-37` `_ROW_TARGET_PREFIXES` to include `"hyp-rec-row-"` (per spec §3.5.4 R1-Major-2). At least 7 route tests in `tests/web/test_routes/test_hyp_recs_expand_route.py`: 200 + partial; 404 + unavailable partial; 404 swaps as `<tr>` via row-target prefix; 500 swaps as `<tr>` via row-target prefix (forced 500 via monkeypatch on `build_hyp_recs_expanded`); chart-unavailable renders message; anchor consistency (in-flight pipeline_run with NULL finished_ts MUST NOT win); freshness footer present with binding.finished_ts substring.
>
> **Sub-task 5.4 — Chevron column + row-partial extraction:**
>   - Create `swing/web/templates/partials/hypothesis_recommendations_row.html.j2` carrying the per-row markup (chevron BUTTON in column 1; the trailing Enter column is added in Task 5.5).
>   - Modify `swing/web/templates/partials/hypothesis_recommendations.html.j2` to (a) add `<th aria-label="Expand"></th>` as column 1 header, (b) replace inline row markup with `{% include "partials/hypothesis_recommendations_row.html.j2" %}`. Tests in NEW file `tests/web/test_hyp_recs_table_regression.py` assert: chevron column header present (aria-label="Expand"); chevron BUTTON has `class="expand-toggle"` + `hx-get="/hyp-recs/{ticker}/expand"` + `hx-target="closest tr"` + `hx-swap="outerHTML"`; the `<tr>` opening tag has NO `hx-get` attribute (discriminating against row-level trigger); refresh route render and full-page render produce equivalent chevron-button markup (drift-equivalence regression).
>
> **Sub-task 5.5 — Per-row Enter button (Q7):**
>   - Append trailing `<td>` in `hypothesis_recommendations_row.html.j2` containing `<button type="button" hx-get="/trades/entry/form?ticker={{ rec.ticker }}&origin=hyp-recs" hx-target="closest tr" hx-swap="outerHTML" hx-headers='{"HX-Request": "true"}'>Enter</button>` (NO `event.stopPropagation` — D.5 differentiator from watchlist Enter).
>   - Append `<th aria-label="Action"></th>` to `hypothesis_recommendations.html.j2` thead.
>   - Tests in `tests/web/test_hyp_recs_table_regression.py` assert: thead has `aria-label="Action"`; per-row Enter button URL contains `&origin=hyp-recs` (or HTML-escaped `&amp;origin=hyp-recs`); button has NO `event.stopPropagation`. Discriminating-test pair: a parallel test verifies WATCHLIST Enter button STILL has `stopPropagation` (proving the architectural difference is intentional, not an accident).
>
> **Sub-task 5.6 — Take-this-trade button (Q8):**
>   - Insert `<p class="action-row"><button type="button" class="take-this-trade primary" hx-get="/trades/entry/form?ticker={{ expanded.ticker }}&origin=hyp-recs" hx-target="closest tr" hx-swap="outerHTML" hx-headers='{"HX-Request": "true"}'>Take this trade</button></p>` into `hypothesis_recommendations_expanded.html.j2` between Order parameters and Sizing groups (per spec §3.5.6 layout).
>   - Tests in `tests/web/test_routes/test_hyp_recs_expand_route.py` assert: Take-this-trade button present in expansion render; URL is `/trades/entry/form?ticker={X}&origin=hyp-recs` (D.2 option (a) — same URL as per-row Enter); class contains `take-this-trade` or `primary` (D.3 visual differentiation); per-row Enter and Take-this-trade share the SAME URL (discriminating-test pair vs an extended-snapshot regression).
>
> **Sub-task 5.7 — Sort-neutrality regression** (`tests/web/test_view_models/test_hyp_recs_sort_neutrality.py`): seeds 3+ candidates that exercise the prioritizer's tie-breaking. Two binding test shapes (R3-Major-1 + R4-Major-2 Codex fix — determinism alone is weaker than neutrality; first-green-after-edit is weaker than pre-change baseline):
>   1. **Cross-builder neutrality** (the spec's actual invariant per §2.2): assert `build_dashboard.active_recommendations` ticker order EQUALS `build_hyp_recs_section.active_recommendations` ticker order, given the same DB state. Discriminating: a regression in the Task 3 `_build_active_recommendations` extraction (e.g. dropped a field, swapped sort key) would diverge the two builders' output. (Note: Task 3 already commits a byte-equivalence regression test `test_build_active_recommendations_helper_extracted_matches_build_dashboard` — this sub-task adds a SECOND layer asserting cross-builder equivalence at the rendered tuple level, not just at the construction-helper level.)
>   2. **Pinned-baseline neutrality**: pin a ticker order tuple captured against the PRE-CHANGE baseline (HEAD `a492b84`, the commit at which this plan's test baseline was pinned), NOT against the first-green-after-edit run. Two acceptable capture protocols (pick whichever is faster for the implementer):
>      - **Capture-then-write protocol:** at sub-step 5.7 dispatch start, the implementer creates a temporary git worktree at `a492b84` (pre-Task-3 commit), seeds the same fixture there, runs `build_dashboard` against the pre-Task-3 module, records the observed ticker tuple, then writes that tuple as the assertion target in the new sub-task 5.7 test. The worktree is discarded after capture.
>      - **Trust-byte-equivalence protocol:** since Task 3 is byte-equivalence guarded by its own regression test (`test_build_active_recommendations_helper_extracted_matches_build_dashboard` asserts `helper_result == expected` against `build_dashboard`'s output), the post-Task-3 ticker tuple equals the pre-Task-3 tuple by construction. Capture the tuple from a green Task-5.7 run AFTER verifying Task 3 has shipped + its byte-equivalence test passes; document the protocol choice in the Task 5.7 commit body so future readers know the pinned tuple is rooted in the HEAD `a492b84` baseline.
>      Discriminating: any future PR perturbing prioritizer logic, hypothesis registry scoring, or default sort tiebreakers fails the suite.
> No production code change in this sub-task — both tests are forward-regression guards. The implementer commits the captured tuple as the assertion target.

> **Sub-task commit messages (binding):**
>   - `feat(recommendations): Task 5.1 — sizing-twin discriminating tests`
>   - `feat(web): Task 5.2 — HypRecsExpandedVM + build_hyp_recs_expanded helper`
>   - `feat(web): Task 5.3 — GET /hyp-recs/{ticker}/expand + expansion partial + ROW_TARGET_PREFIXES extension`
>   - `feat(web): Task 5.4 — chevron column + row-partial extraction on hyp-recs table`
>   - `feat(web): Task 5.5 — per-row Enter button (Q7) on hyp-recs row`
>   - `feat(web): Task 5.6 — Take-this-trade button (Q8) on expansion`
>   - `test(web): Task 5.7 — hyp-recs sort-neutrality regression guard`

---

## Task 6: Origin-aware entry-form scaffolding (R3-Major-1)

**Why sixth.** Per spec §7.1 step 6, subdivided per spec's authorization. Task 6 adds the `TradeEntryFormVM.origin` discriminator, parameterizes the template, and adds the GET-handler whitelist coercion. Tasks 7-9 layer the candidate fallback (R3-Major-2), POST round-trip survival (R4-Major-1), and anchor consistency (R4-Major-2) on top.

**Failure mode this closes.** When the operator clicks per-row Enter or Take-this-trade on a hyp-recs row, the entry form swaps in. Before Task 6, the entry form's `<td colspan="8">` mismatches the 9-cell hyp-recs row (cosmetic) and the Cancel button targets `/watchlist/{ticker}/expand` (broken when the ticker isn't on the watchlist; disorienting otherwise). After Task 6, the form parameterizes its colspan AND Cancel target on `vm.origin`.

**Files:**
- Modify: `swing/web/view_models/trades.py` — `TradeEntryFormVM` gains `origin: Literal["watchlist", "hyp-recs"] = "watchlist"` trailing-default field; `build_entry_form_vm` accepts `origin: str = "watchlist"` keyword arg with whitelist coercion to `_VALID_ORIGINS`.
- Modify: `swing/web/templates/partials/trade_entry_form.html.j2:4` — parameterize `colspan` (9 if `vm.origin == 'hyp-recs'` else 8).
- Modify: `swing/web/templates/partials/trade_entry_form.html.j2:71-74` — parameterize Cancel button `hx-get` and `hx-target` based on `vm.origin`.
- Modify: `swing/web/routes/trades.py:205-214` — `entry_form` GET handler reads `?origin=` query param; whitelist-coerce; pass to `build_entry_form_vm`.
- Test: extend `tests/web/test_routes/test_hyp_recs_expand_route.py` — origin-aware entry-form tests.

**Discriminating-test sanity-check.** Whitelist coercion test uses an injection attempt (`?origin=javascript:alert(1)`) and asserts the form renders with `vm.origin == "watchlist"` (default), NOT the malicious string passed through. **Would this test fail if the implementation never actually called the new code?** Yes — pre-implementation, GET handler does NOT read `?origin=`; the template has no `vm.origin` reference; importing `from swing.web.view_models.trades import TradeEntryFormVM; vm = TradeEntryFormVM(...); vm.origin` raises `AttributeError`.

- [ ] **Step 6.1: Write the failing tests.** Append to `tests/web/test_routes/test_hyp_recs_expand_route.py`:

```python
def test_entry_form_origin_watchlist_default_renders_colspan_8(tmp_path: Path):
    """Pre-existing watchlist Enter callers (no ?origin= param) get the
    same form as before: colspan=8 + Cancel /watchlist/{ticker}/expand.

    Discriminating: a regression where the template hardcodes
    colspan=9 unconditionally would break this test (existing
    watchlist surface unchanged is the requirement).
    """
    cfg = _make_cfg(tmp_path)
    _seed_hyp_recs_fixture(cfg, tickers=["NVDA"])
    # Add the ticker to the watchlist so the form renders correctly.
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="NVDA", entry_target=100.0, initial_stop_target=95.0,
                last_close=99.0, last_adr_pct=2.0,
                added_session=None, removed_session=None,
            ))
    finally:
        conn.close()
    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.get(
            "/trades/entry/form?ticker=NVDA",  # NO ?origin=.
            headers={"HX-Request": "true", "HX-Target": "watchlist-row-NVDA"},
        )
    assert resp.status_code == 200
    body = resp.text
    assert 'colspan="8"' in body, (
        "watchlist-default origin must render colspan=8 (existing"
        " behavior unchanged)"
    )
    assert "/watchlist/NVDA/expand" in body, (
        "watchlist-default origin Cancel must target watchlist expand"
    )


def test_entry_form_origin_hyp_recs_renders_colspan_9_and_refresh_cancel(
    tmp_path: Path,
):
    """Spec §3.8b.1 R3-Major-1 — when ?origin=hyp-recs, form renders
    colspan=9 + Cancel /hyp-recs/refresh.

    Discriminating: pre-fix path renders colspan=8 + watchlist Cancel
    regardless of the query param.
    """
    cfg = _make_cfg(tmp_path)
    _seed_hyp_recs_fixture(cfg, tickers=["NVDA"])
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="NVDA", entry_target=100.0, initial_stop_target=95.0,
                last_close=99.0, last_adr_pct=2.0,
                added_session=None, removed_session=None,
            ))
    finally:
        conn.close()
    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.get(
            "/trades/entry/form?ticker=NVDA&origin=hyp-recs",
            headers={"HX-Request": "true", "HX-Target": "hyp-rec-row-NVDA"},
        )
    assert resp.status_code == 200
    body = resp.text
    assert 'colspan="9"' in body, (
        "?origin=hyp-recs must render colspan=9 (R3-Major-1)"
    )
    assert "/hyp-recs/refresh" in body, (
        "?origin=hyp-recs Cancel must target /hyp-recs/refresh"
    )


def test_entry_form_origin_query_param_whitelist_validation(tmp_path: Path):
    """Spec §3.8b.1 — unknown ?origin= values default to 'watchlist'
    (whitelist validation; closes URL-injection threat).

    Discriminating: a regression where the template emits the raw
    query-param value as the Cancel hx-get target would render
    `hx-get="javascript:alert(1)"` (XSS surface).
    """
    cfg = _make_cfg(tmp_path)
    _seed_hyp_recs_fixture(cfg, tickers=["NVDA"])
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="NVDA", entry_target=100.0, initial_stop_target=95.0,
                last_close=99.0, last_adr_pct=2.0,
                added_session=None, removed_session=None,
            ))
    finally:
        conn.close()
    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.get(
            "/trades/entry/form?ticker=NVDA&origin=javascript:alert(1)",
            headers={"HX-Request": "true", "HX-Target": "watchlist-row-NVDA"},
        )
    assert resp.status_code == 200
    body = resp.text
    # Whitelist coercion → defaults to 'watchlist' → colspan=8 + watchlist Cancel.
    assert 'colspan="8"' in body
    assert "/watchlist/NVDA/expand" in body
    # The malicious string MUST NOT appear in the rendered HTML at all.
    # Jinja autoescape would escape `<` to `&lt;` even if it leaked, so
    # assert specifically on the URL-form string the template's
    # hx-get attribute would emit if the template raw-passes the param.
    assert "javascript:" not in body, (
        "whitelist coercion failed; raw query-param value leaked into"
        " rendered HTML"
    )
```

- [ ] **Step 6.2: Run failing tests; expect 3 FAIL.**

```bash
python -m pytest tests/web/test_routes/test_hyp_recs_expand_route.py -v -k "entry_form_origin"
```

Expected: 3 FAIL — `colspan="9"` is never rendered (template hardcodes 8); `?origin=hyp-recs` is silently dropped; injection test passes only because the param is silently dropped (the malicious string truly never appears, but the discriminating colspan=8 / watchlist-Cancel-default assertion would fail anyway since at this stage the WATCHLIST origin is the only branch).

> **Test note.** `test_entry_form_origin_watchlist_default_renders_colspan_8` may PASS pre-Task-6 because the existing template hardcodes colspan=8 + `/watchlist/{ticker}/expand` Cancel. That's a forward-regression guard: the test asserts the existing behavior is preserved post-Task-6. Don't worry if it passes — failing-test discipline applies to the NEW behavior tests, not the existing-behavior preservation guards.

- [ ] **Step 6.3: Modify `swing/web/view_models/trades.py`.**

Add `Literal` import at the top:

```python
from typing import Literal
```

Add a module-level constant + `TradeEntryFormVM` field:

```python
_VALID_ORIGINS = ("watchlist", "hyp-recs")


def _coerce_origin(raw: str | None) -> Literal["watchlist", "hyp-recs"]:
    """Whitelist-coerce ?origin= query-param / form-payload value.
    Unknown / missing → 'watchlist' (preserves existing behavior).

    Spec §3.8b.1 R3-Major-1.
    """
    if raw in _VALID_ORIGINS:
        return raw  # type: ignore[return-value]
    return "watchlist"


@dataclass(frozen=True)
class TradeEntryFormVM:
    # ... existing fields preserved ...
    industry: str = ""
    # Spec §3.8b — origin discriminator. Whitelist-validated at the
    # request boundary by _coerce_origin; unknown values default to
    # 'watchlist' so existing watchlist callers (no ?origin=) keep
    # working. Threading: GET ?origin= → build_entry_form_vm → VM
    # field → template parameterizes colspan + Cancel target. POST
    # round-trip survival ships in Task 8 via a hidden form field.
    origin: Literal["watchlist", "hyp-recs"] = "watchlist"
```

Modify `build_entry_form_vm` signature + threading:

```python
def build_entry_form_vm(
    *, ticker: str, cfg: Config, cache: PriceCache, executor,
    origin: str = "watchlist",
) -> TradeEntryFormVM:
    """... existing docstring ..."""
    coerced_origin = _coerce_origin(origin)
    ticker = ticker.upper()
    # ... existing body unchanged ...
    return TradeEntryFormVM(
        # ... existing args preserved ...
        sector=cand_sector,
        industry=cand_industry,
        origin=coerced_origin,
    )
```

- [ ] **Step 6.4: Modify `swing/web/templates/partials/trade_entry_form.html.j2`.**

Line 4 (template hardcodes `<td colspan="8">`):

```jinja
<tr id="entry-form-{{ vm.ticker }}">
  <td colspan="{{ 9 if vm.origin == 'hyp-recs' else 8 }}">
```

Lines 71-74 (Cancel button):

```jinja
<button type="button"
        hx-get="{{ '/hyp-recs/refresh' if vm.origin == 'hyp-recs' else '/watchlist/' ~ vm.ticker ~ '/expand' }}"
        hx-target="{{ '#hypothesis-recommendations' if vm.origin == 'hyp-recs' else 'closest tr' }}"
        hx-swap="outerHTML"
        hx-headers='{"HX-Request": "true"}'>Cancel</button>
```

- [ ] **Step 6.5: Modify `swing/web/routes/trades.py:205-214`** (`entry_form` GET handler) to read `?origin=`:

```python
@router.get("/trades/entry/form", response_class=HTMLResponse)
def entry_form(request: Request, ticker: str, origin: str = "watchlist"):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = request.app.state.templates
    vm = build_entry_form_vm(
        ticker=ticker, cfg=cfg, cache=cache, executor=executor,
        origin=origin,
    )
    return templates.TemplateResponse(
        request, "partials/trade_entry_form.html.j2", {"vm": vm},
    )
```

The whitelist coercion is performed inside `build_entry_form_vm` (via `_coerce_origin`); the route accepts the raw string and lets the VM builder enforce.

- [ ] **Step 6.6: Run the tests; expect 3 PASS.**

```bash
python -m pytest tests/web/test_routes/test_hyp_recs_expand_route.py -v -k "entry_form_origin"
```

- [ ] **Step 6.7: Run the full fast suite.**

```bash
python -m pytest -m "not slow" -q
```

Expected: 1274 + 3 = 1277 passing. Existing entry-form tests at `tests/web/test_routes/test_trade_entry_chart_pattern.py` MUST stay green — the default-origin watchlist behavior is preserved.

- [ ] **Step 6.8: Observable-verification grep + commit.**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 6' | head -20
```

```bash
git add tests/web/test_routes/test_hyp_recs_expand_route.py \
  swing/web/view_models/trades.py \
  swing/web/templates/partials/trade_entry_form.html.j2 \
  swing/web/routes/trades.py
git commit -m "$(cat <<'EOF'
feat(web): Task 6 — origin-aware entry-form scaffolding (R3-Major-1)

Adds TradeEntryFormVM.origin: Literal["watchlist","hyp-recs"]=
"watchlist" discriminator with whitelist coercion at the request
boundary. trade_entry_form.html.j2 parameterizes <td colspan> (9 for
hyp-recs origin; 8 for watchlist) and the Cancel button hx-get /
hx-target based on vm.origin. GET /trades/entry/form?origin= reads
the query param.

Existing watchlist callers (no ?origin=) keep working — origin
defaults to 'watchlist'; existing tests at
tests/web/test_routes/test_trade_entry_chart_pattern.py stay green.

Whitelist coercion test verifies ?origin=javascript:alert(1) does
NOT pass through to the rendered hx-get attribute (closes URL-
injection surface).

POST round-trip survival ships in Task 8; off-watchlist candidate
fallback in Task 7; anchor consistency for hyp-recs origin in Task 9.

Spec §3.8b.1 R3-Major-1.
EOF
)"
```

---

## Task 7: Off-watchlist candidate fallback for `entry_price` / `initial_stop` (R3-Major-2)

**Why seventh.** Per spec §7.1 step 6 sub-task. Closes the gap that hyp-recs Enter on an off-watchlist ticker renders the form with `entry_price=$0.00` and `initial_stop=$0.00` (because `wl_entry` is None and the existing fallback to `0.0` defeats the point of having just verified the snapshot in the expansion).

**Files:**
- Modify: `swing/web/view_models/trades.py` — extend the candidate-row SELECT in `build_entry_form_vm` to also fetch `pivot` + `initial_stop`. When `wl_entry` is None, fall back to candidate values for `entry_price` (the `entry_target_for_form` semantic) and `initial_stop`.
- Test: extend `tests/web/test_routes/test_hyp_recs_expand_route.py` — off-watchlist fallback discriminating tests.

**Discriminating-test sanity-check.** The discriminating fixture seeds a ticker WITHOUT a watchlist entry but WITH a candidate row carrying `pivot=$50, initial_stop=$48`. Pre-fix renders `entry_price=$0.00, initial_stop=$0.00`; post-fix renders the candidate values. Test asserts on `value="50.00"` (entry_price input) and `value="48.00"` (initial_stop input). **Would this test fail if the implementation never actually called the new code?** Yes — `build_entry_form_vm`'s current SELECT only fetches sector/industry; the assertion on candidate-pivot fallback fails pre-fix.

A second discriminating test seeds a ticker that IS on the watchlist with values DIFFERENT from the candidate values; the form prefers watchlist values (preserves existing semantic).

- [ ] **Step 7.1: Write the failing tests.** Append to `tests/web/test_routes/test_hyp_recs_expand_route.py`:

```python
def test_hyp_recs_entry_form_off_watchlist_uses_candidate_pivot_for_target(
    tmp_path: Path,
):
    """Spec §3.8b.2 R3-Major-2 — off-watchlist hyp-recs entry uses
    candidate row's pivot for entry_price + initial_stop.

    Discriminating: pre-fix renders entry_price=$0.00 and
    initial_stop=$0.00; post-fix renders candidate values.
    """
    cfg = _make_cfg(tmp_path)
    # Seed candidate but NOT watchlist for ticker 'OFF'.
    from swing.data.db import connect, ensure_schema
    ensure_schema(cfg.paths.db_path)
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count)
                   VALUES ('2026-04-29T09:00:00','2026-04-28','2026-04-29',
                           NULL, 1, 1, 0, 0, 0, 0)"""
            )
            eval_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """INSERT INTO pipeline_runs
                   (state, started_ts, finished_ts, action_session_date,
                    data_asof_date, evaluation_run_id, charts_status)
                   VALUES ('complete','2026-04-29T08:00:00',
                           '2026-04-29T09:00:00','2026-04-29','2026-04-28',?,'ok')""",
                (eval_id,),
            )
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot,
                    initial_stop, adr_pct, tight_streak, pullback_pct,
                    prior_trend_pct, rs_rank, rs_return_12w_vs_spy,
                    rs_method, pattern_tag, notes, sector, industry)
                   VALUES (?, 'OFF', 'aplus', 49.0, 50.0, 48.0, 2.0, 5,
                           NULL, NULL, NULL, NULL, 'fallback_spy',
                           NULL, NULL, 'Energy', 'Oil & Gas E&P')""",
                (eval_id,),
            )
    finally:
        conn.close()
    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.get(
            "/trades/entry/form?ticker=OFF&origin=hyp-recs",
            headers={"HX-Request": "true", "HX-Target": "hyp-rec-row-OFF"},
        )
    assert resp.status_code == 200
    body = resp.text
    # entry_price input = candidate.pivot = $50.00 (since no live price snap).
    # The template renders value="{{ '%.2f' | format(vm.entry_price) }}".
    assert 'name="entry_price"' in body
    assert 'value="50.00"' in body, (
        f"off-watchlist entry_price must fall back to candidate.pivot;"
        f" pre-fix would render value=\"0.00\""
    )
    # initial_stop input = candidate.initial_stop = $48.00.
    assert 'name="initial_stop"' in body
    assert 'value="48.00"' in body, (
        "off-watchlist initial_stop must fall back to candidate.initial_stop"
    )


def test_watchlist_origin_off_watchlist_preserves_zero_fallback(tmp_path: Path):
    """R1-Major-2 (Codex R1) — gating regression: watchlist-origin
    request for an off-watchlist ticker MUST preserve the existing
    0.0 fallback (NOT silently start using candidate.pivot).

    Discriminating: pre-Task-7 path renders entry_price=$0.00,
    initial_stop=$0.00. Post-Task-7 path with origin=hyp-recs renders
    candidate values. Post-Task-7 path with origin=watchlist (or
    default) MUST still render $0.00 — the fallback is gated.
    """
    cfg = _make_cfg(tmp_path)
    # Same off-watchlist + candidate seed as the hyp-recs test, but
    # request without ?origin= so it defaults to 'watchlist'.
    from swing.data.db import connect, ensure_schema
    ensure_schema(cfg.paths.db_path)
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count)
                   VALUES ('2026-04-29T09:00:00','2026-04-28','2026-04-29',
                           NULL, 1, 1, 0, 0, 0, 0)"""
            )
            eval_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """INSERT INTO pipeline_runs
                   (state, started_ts, finished_ts, action_session_date,
                    data_asof_date, evaluation_run_id, charts_status)
                   VALUES ('complete','2026-04-29T08:00:00',
                           '2026-04-29T09:00:00','2026-04-29','2026-04-28',?,'ok')""",
                (eval_id,),
            )
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot,
                    initial_stop, adr_pct, tight_streak, pullback_pct,
                    prior_trend_pct, rs_rank, rs_return_12w_vs_spy,
                    rs_method, pattern_tag, notes, sector, industry)
                   VALUES (?, 'OFF', 'aplus', 49.0, 50.0, 48.0, 2.0, 5,
                           NULL, NULL, NULL, NULL, 'fallback_spy',
                           NULL, NULL, 'Energy', 'Oil & Gas E&P')""",
                (eval_id,),
            )
    finally:
        conn.close()
    app = create_app(cfg)
    with TestClient(app) as client:
        # NO ?origin= → defaults to 'watchlist'. Off-watchlist ticker.
        resp = client.get(
            "/trades/entry/form?ticker=OFF",
            headers={"HX-Request": "true", "HX-Target": "watchlist-row-OFF"},
        )
    assert resp.status_code == 200
    body = resp.text
    # Watchlist origin + off-watchlist + no live snap → existing 0.0
    # fallback preserved. The candidate fallback gated to hyp-recs only.
    # R2-Minor-1 (Codex R2) — strengthen: assert candidate values
    # ABSENT from BOTH entry_price and initial_stop fields. The form
    # may render multiple "0.00" values (open trade count, sizing
    # hint, etc.); the candidate-pivot regression signal is the
    # SPECIFIC values 50.00 (entry_price ← candidate.pivot) and 48.00
    # (initial_stop ← candidate.initial_stop) appearing in the
    # respective input value attributes.
    import re
    entry_price_input = re.search(
        r'<input[^>]*name="entry_price"[^>]*value="([^"]*)"', body,
    )
    initial_stop_input = re.search(
        r'<input[^>]*name="initial_stop"[^>]*value="([^"]*)"', body,
    )
    assert entry_price_input is not None
    assert initial_stop_input is not None
    assert entry_price_input.group(1) == "0.00", (
        f"watchlist-origin off-watchlist entry_price must preserve 0.0"
        f" fallback; got {entry_price_input.group(1)!r}. A regression"
        f" that applies candidate.pivot globally would yield '50.00'."
    )
    assert initial_stop_input.group(1) == "0.00", (
        f"watchlist-origin off-watchlist initial_stop must preserve 0.0"
        f" fallback; got {initial_stop_input.group(1)!r}. A regression"
        f" that applies candidate.initial_stop globally would yield '48.00'."
    )
    # Sector/industry STILL come from candidate (unchanged behavior).
    assert "Energy" in body


def test_hyp_recs_entry_form_on_watchlist_prefers_watchlist_values(tmp_path: Path):
    """Spec §3.8b.2 — when ticker IS on the watchlist with values DIFFERENT
    from candidate values, the form prefers watchlist (preserves existing
    semantic). Discriminating: a regression that always overrides with
    candidate would render 50.00; the assertion targets the watchlist
    value 100.00."""
    cfg = _make_cfg(tmp_path)
    _seed_hyp_recs_fixture(cfg, tickers=["NVDA"])  # candidate pivot = 100.0
    # Override watchlist values: entry_target=100, initial_stop=95
    # (matches candidate); add a DIFFERENT-valued ticker too.
    from swing.data.db import connect, ensure_schema
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.data.models import WatchlistEntry
    ensure_schema(cfg.paths.db_path)
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # The seeded NVDA candidate has pivot=100, initial_stop=95.
            # Insert a watchlist row with DIFFERENT values to discriminate.
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="NVDA", entry_target=110.0, initial_stop_target=105.0,
                last_close=99.0, last_adr_pct=2.0,
                added_session=None, removed_session=None,
            ))
    finally:
        conn.close()
    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.get(
            "/trades/entry/form?ticker=NVDA&origin=hyp-recs",
            headers={"HX-Request": "true", "HX-Target": "hyp-rec-row-NVDA"},
        )
    assert resp.status_code == 200
    body = resp.text
    # Watchlist initial_stop=105 wins over candidate 95.
    assert 'value="105.00"' in body, (
        "on-watchlist initial_stop must prefer watchlist value (105.00)"
        " over candidate (95.00) per backward-compat semantic"
    )
```

- [ ] **Step 7.2: Run failing tests; expect 1 FAIL** (`off_watchlist_uses_candidate_pivot_for_target`). The on-watchlist test passes pre-fix because watchlist-priority semantic is the existing behavior.

- [ ] **Step 7.3: Modify `swing/web/view_models/trades.py`'s `build_entry_form_vm`** to fetch + use candidate pivot/initial_stop **gated on `coerced_origin == "hyp-recs"`** (R1-Major-2 fix: scope the new fallback tightly so default/watchlist origin off-watchlist callers do NOT silently change behavior). In the existing candidate-row SELECT inside the `with conn:` block (around lines 122-129), extend the SELECT to also fetch pivot + initial_stop (always — the SELECT is cheap and the fields are unconditionally available; gating happens at the fallback decision below):

```python
cand_sector = ""
cand_industry = ""
cand_pivot: float | None = None
cand_initial_stop: float | None = None
sector_eval_id = latest_evaluation_run_id(conn)
if sector_eval_id is not None:
    cand_row = conn.execute(
        """SELECT sector, industry, pivot, initial_stop FROM candidates
           WHERE evaluation_run_id = ? AND ticker = ?""",
        (sector_eval_id, ticker),
    ).fetchone()
    if cand_row is not None:
        cand_sector = cand_row[0] or ""
        cand_industry = cand_row[1] or ""
        cand_pivot = cand_row[2]
        cand_initial_stop = cand_row[3]
```

Then replace the existing `initial_stop = wl_entry.initial_stop_target if wl_entry and wl_entry.initial_stop_target else 0.0` and the `entry_price = snap.price if snap else (wl_entry.last_close if wl_entry else 0.0)` lines with **origin-gated** fallback chains:

```python
# R3-Major-2 fallback chain — GATED on origin=hyp-recs (R1-Major-2).
# Watchlist origin (default) preserves existing behavior for backward
# compat: a watchlist Enter caller hitting an off-watchlist ticker is
# a degenerate path under existing UX (the watchlist Enter button only
# fires from watchlist rows by construction); preserving the 0.0
# fallback there is the conservative choice. Hyp-recs origin gets the
# candidate-row fallback so off-watchlist hyp-recs Enter sees useful
# values from the latest evaluation.
if coerced_origin == "hyp-recs":
    if wl_entry is not None and wl_entry.initial_stop_target:
        initial_stop = wl_entry.initial_stop_target
    elif cand_initial_stop is not None:
        initial_stop = cand_initial_stop
    else:
        initial_stop = 0.0
else:
    # Watchlist origin: existing behavior.
    initial_stop = wl_entry.initial_stop_target if wl_entry and wl_entry.initial_stop_target else 0.0

# entry_price fallback chain. For hyp-recs origin: live snap →
# wl_entry.last_close → candidate.pivot → 0.0. For watchlist origin:
# preserve existing behavior (live snap → wl_entry.last_close → 0.0).
if snap is not None:
    entry_price = snap.price
elif wl_entry is not None and wl_entry.last_close:
    entry_price = wl_entry.last_close
elif coerced_origin == "hyp-recs" and cand_pivot is not None:
    entry_price = cand_pivot
else:
    entry_price = 0.0
```

The `watchlist_entry_target` and `watchlist_initial_stop` hidden inputs stay BOUND TO `wl_entry` ONLY (per spec §3.8b.2):

```python
watchlist_entry_target = wl_entry.entry_target if wl_entry else None
watchlist_initial_stop = wl_entry.initial_stop_target if wl_entry else None
```

(Lines unchanged — they were already bound to `wl_entry`.)

- [ ] **Step 7.4: Run the tests; expect 2 PASS.**

```bash
python -m pytest tests/web/test_routes/test_hyp_recs_expand_route.py -v -k "off_watchlist or on_watchlist"
```

- [ ] **Step 7.5: Run the full fast suite.**

```bash
python -m pytest -m "not slow" -q
```

Expected: 1277 + 1 = 1278 passing (the on-watchlist test passed pre- and post-fix; only `off_watchlist_uses_candidate_pivot_for_target` was newly green). NOTE: existing tests at `tests/web/test_view_models/test_trade_entry_form_classification.py` and `tests/web/test_routes/test_trade_entry_chart_pattern.py` MUST stay green — the fallback chain is additive (only fires when `wl_entry` is None), so existing on-watchlist tests are unaffected. If a regression surfaces, audit whether those tests had been silently relying on `0.0` fallback for an off-watchlist scenario — surface in return report.

- [ ] **Step 7.6: Commit.**

```bash
git add tests/web/test_routes/test_hyp_recs_expand_route.py \
  swing/web/view_models/trades.py
git commit -m "$(cat <<'EOF'
feat(web): Task 7 — off-watchlist candidate fallback for entry_price + initial_stop (R3-Major-2)

When the operator clicks Enter or Take-this-trade on a hyp-recs row
whose ticker is NOT on the active watchlist, build_entry_form_vm now
falls back to the candidate row's pivot + initial_stop instead of
zero. The fallback chain:
  - initial_stop:  wl_entry.initial_stop_target → candidate.initial_stop → 0.0
  - entry_price:  live snap → wl_entry.last_close → candidate.pivot → 0.0

The watchlist_entry_target and watchlist_initial_stop hidden inputs
stay bound to wl_entry ONLY (their POST-side semantic is "the value
the watchlist had at form-render"); when the form is hyp-recs-
originated and wl_entry is None, both hidden inputs are absent —
preserving the existing semantic.

Discriminating-test pair: off-watchlist seeds candidate pivot=$50;
on-watchlist seeds watchlist_initial_stop=$105 with candidate
initial_stop=$95 (different) and asserts the form prefers the
watchlist value (backward-compat).

Spec §3.8b.2 R3-Major-2.
EOF
)"
```

---

## Task 8: Origin survives POST round-trips (R4-Major-1)

**Why eighth.** Per spec §7.1 step 6 sub-task. Closes the regression class where an operator clicks Take this trade on a hyp-recs row → form renders with `origin=hyp-recs` → submit triggers a validation error or duplicate-position rejection or soft-warn → form re-renders with `origin` lost → form now has colspan=8 + watchlist Cancel; the operator sees layout shift on resubmit.

**Files:**
- Modify: `swing/web/templates/partials/trade_entry_form.html.j2` — add hidden `<input type="hidden" name="origin" value="{{ vm.origin }}">` form field (anywhere inside the `<form>` tag).
- Modify: `swing/web/templates/partials/soft_warn_confirm.html.j2` — Cancel button parameterized on `form_values.origin` (mirroring trade_entry_form's pattern); the hidden `origin` form field is auto-emitted by the existing `for key, value in form_values.items()` loop once `origin` is added to `form_values` (Task 8 subroutine in `entry_post`).
- Modify: `swing/web/routes/trades.py:217-526` — `entry_post` POST handler reads form-payload `origin` (whitelist-coerce); threads through `_rerender_entry_form_with_error`, `DuplicateOpenPositionException` re-render, soft-warn `form_values` dict.
- Test: extend `tests/web/test_routes/test_hyp_recs_expand_route.py` — POST round-trip discriminating tests.

**Discriminating-test sanity-check.** Three round-trip paths each get a discriminating test:
1. **Validation-error round-trip** (`test_validation_error_rerender_preserves_origin`): POST `/trades/entry` with `origin=hyp-recs` and a deliberate validation error (e.g., `entry_price=-1` or rationale=invalid). Response body must contain `colspan="9"` AND `hx-get="/hyp-recs/refresh"`. Discriminating: pre-fix path would render `colspan="8"` + `/watchlist/{ticker}/expand` (origin lost on re-render).
2. **Duplicate-position round-trip** (`test_duplicate_open_position_rerender_preserves_origin`): POST with `origin=hyp-recs` for a ticker that already has an open position → 400 + form re-render. Body asserts `colspan="9"` + hyp-recs Cancel.
3. **Soft-warn round-trip** (`test_soft_warn_confirm_round_trips_origin`): POST with `origin=hyp-recs` that triggers soft-warn → confirm partial includes hidden `origin=hyp-recs`; test asserts the hidden input is present and the Cancel button targets `/hyp-recs/refresh`.

**Would these tests fail if the implementation never actually called the new code?** Yes — pre-fix, `_rerender_entry_form_with_error` rebuilds the VM from `ticker` only (default origin = "watchlist"); the assertions on `colspan="9"` fail.

- [ ] **Step 8.1: Write the failing tests.** Append three tests to `tests/web/test_routes/test_hyp_recs_expand_route.py` per the discriminating-test pattern (each follows the standard `_make_cfg` + `_seed_hyp_recs_fixture` + TestClient pattern with origin=hyp-recs in the POST payload). Pseudocode for each:

```python
def test_validation_error_rerender_preserves_origin(tmp_path: Path):
    """R4-Major-1 — validation-error round-trip preserves origin."""
    cfg = _make_cfg(tmp_path); _seed_hyp_recs_fixture(cfg, tickers=["NVDA"])
    # ... seed watchlist row to make the form renderable ...
    app = create_app(cfg)
    with TestClient(app) as client:
        # Submit a POST that triggers a validation error: rationale='invalid'.
        resp = client.post("/trades/entry", data={
            "ticker": "NVDA", "entry_date": "2026-04-29",
            "entry_price": "100.00", "shares": "10",
            "initial_stop": "95.00",
            "rationale": "invalid_rationale",  # triggers _validate_rationale failure
            "origin": "hyp-recs",
        }, headers={"HX-Request": "true", "HX-Target": "hyp-rec-row-NVDA"})
    assert resp.status_code == 400
    body = resp.text
    assert 'colspan="9"' in body, (
        "validation-error re-render must preserve origin=hyp-recs"
        " (colspan=9; pre-fix would default to colspan=8)"
    )
    assert "/hyp-recs/refresh" in body


def test_duplicate_open_position_rerender_preserves_origin(tmp_path: Path):
    """R4-Major-1 — duplicate-position round-trip preserves origin."""
    cfg = _make_cfg(tmp_path); _seed_hyp_recs_fixture(cfg, tickers=["NVDA"])
    # Seed an existing OPEN trade for NVDA so a new POST triggers
    # DuplicateOpenPositionException.
    from swing.data.db import connect
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.data.models import WatchlistEntry
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="NVDA", entry_target=100.0, initial_stop_target=95.0,
                last_close=99.0, last_adr_pct=2.0,
                added_session=None, removed_session=None,
            ))
            conn.execute(
                """INSERT INTO trades
                   (ticker, entry_date, entry_price, initial_shares,
                    initial_stop, current_stop, status)
                   VALUES ('NVDA','2026-04-28',95.0,10,90.0,90.0,'open')"""
            )
    finally:
        conn.close()
    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.post("/trades/entry", data={
            "ticker": "NVDA", "entry_date": "2026-04-29",
            "entry_price": "100.00", "shares": "10",
            "initial_stop": "95.00",
            "rationale": "pivot-breakout",  # valid rationale
            "origin": "hyp-recs",
        }, headers={"HX-Request": "true", "HX-Target": "hyp-rec-row-NVDA"})
    assert resp.status_code == 400
    body = resp.text
    assert 'colspan="9"' in body
    assert "/hyp-recs/refresh" in body


def test_soft_warn_confirm_round_trips_origin(tmp_path: Path):
    """R4-Major-1 — soft-warn confirm round-trips origin to confirm
    partial → confirm-submit POSTs origin back. Cancel from confirm
    fires /hyp-recs/refresh.

    Discriminating: pre-fix path would emit Cancel /watchlist/NVDA/expand
    in the soft_warn_confirm partial.
    """
    cfg = _make_cfg(tmp_path); _seed_hyp_recs_fixture(cfg, tickers=["NVDA"])
    # Seed soft_warn_open=0 so any new entry trips the soft-warn path,
    # OR seed enough open trades to cross the existing threshold.
    # Implementer: locate the test config's position_limits.soft_warn_open;
    # seed open trades = soft_warn_open count to trip soft-warn on the
    # first new entry.
    # ... (implementer-fills the seed) ...
    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.post("/trades/entry", data={
            "ticker": "NVDA", "entry_date": "2026-04-29",
            "entry_price": "100.00", "shares": "10",
            "initial_stop": "95.00",
            "rationale": "pivot-breakout",
            "origin": "hyp-recs",
        }, headers={"HX-Request": "true", "HX-Target": "hyp-rec-row-NVDA"})
    assert resp.status_code == 200, (
        "soft-warn confirm renders 200 with the confirm partial"
    )
    body = resp.text
    # Hidden origin field on the confirm partial.
    assert 'name="origin"' in body
    assert 'value="hyp-recs"' in body, (
        "soft-warn confirm must include hidden origin=hyp-recs"
    )
    assert "/hyp-recs/refresh" in body, (
        "soft-warn confirm Cancel must target /hyp-recs/refresh"
    )
```

- [ ] **Step 8.2: Run failing tests; expect 3 FAIL.**

- [ ] **Step 8.3: Add the hidden `origin` field to `swing/web/templates/partials/trade_entry_form.html.j2`** (inside `<form>`, near `<input type="hidden" name="ticker" ...>`):

```jinja
<input type="hidden" name="ticker" value="{{ vm.ticker }}">
<input type="hidden" name="origin" value="{{ vm.origin }}">
```

- [ ] **Step 8.4: Modify `swing/web/routes/trades.py`'s `entry_post`** (line 217+) to read `origin` from form payload and thread through:

(a) Add to the `Form(...)` parameter list:

```python
origin: str = Form("watchlist"),
```

(b) Whitelist-coerce inside the body (mirror `_coerce_origin` from trades.py VM module):

```python
from swing.web.view_models.trades import _coerce_origin
origin_coerced = _coerce_origin(origin)
```

(c) Modify `_rerender_entry_form_with_error` signature + threading: add `origin: str = "watchlist"` keyword arg; pass `origin=origin_coerced` from each call site (4 call sites: rationale-validation failure, stop>=entry validation failure, chart-pattern ValueError catch, chart-pattern IntegrityError catch); inside the function pass `origin=origin` to `build_entry_form_vm`.

(d) Modify the `DuplicateOpenPositionException` re-render branch to call `build_entry_form_vm(... origin=origin_coerced)` so the duplicate re-render preserves origin.

(e) Modify the soft-warn `form_values` dict to include `"origin": origin_coerced` (the existing `for key, value in form_values.items()` loop in `soft_warn_confirm.html.j2` auto-emits the hidden input once the key is added to the dict).

- [ ] **Step 8.5: Modify `swing/web/templates/partials/soft_warn_confirm.html.j2`** to parameterize BOTH `<td colspan>` AND Cancel button on `form_values.origin` (R1-Major-1: the existing template hardcodes `colspan="8"` at line 18 — without this fix, hyp-recs round-trips render the soft-warn confirm fragment with colspan=8 inside a 9-cell table, leaving the layout structurally wrong even after Task 8 "passes" the round-trip preservation tests):

```jinja
{#- Soft-warn 2-step confirmation fragment.
    Expects: form_values (dict of the original form submission fields,
    including 'origin' for R4-Major-1 round-trip survival).

    R1-Major-1 (Codex R1): colspan + Cancel target parameterized on
    form_values.origin so the fragment shape matches the originating
    table's column count (9 for hyp-recs; 8 for watchlist).
-#}
<tr class="soft-warn-confirm">
  <td colspan="{{ 9 if form_values.origin == 'hyp-recs' else 8 }}">
    <div class="banner" style="background:#fff3cd;color:#92400e;padding:12px;">
      <strong>⚠ Soft cap reached ({{ form_values.open_count }}/{{ form_values.soft_warn }}).</strong>
      <p>Opening this trade exceeds your configured soft-warn threshold.
         Hard cap is {{ form_values.hard_cap }} (still available).</p>
      <form hx-post="/trades/entry" hx-target="closest tr" hx-swap="outerHTML"
            hx-headers='{"HX-Request": "true"}'>
        {% for key, value in form_values.items() %}
          {% if key not in ("open_count", "soft_warn", "hard_cap") %}
            <input type="hidden" name="{{ key }}" value="{{ value }}">
          {% endif %}
        {% endfor %}
        <input type="hidden" name="force" value="true">
        <button type="submit">Submit anyway</button>
        <button type="button"
                hx-get="{{ '/hyp-recs/refresh' if form_values.origin == 'hyp-recs' else '/watchlist/' ~ form_values.ticker ~ '/expand' }}"
                hx-target="{{ '#hypothesis-recommendations' if form_values.origin == 'hyp-recs' else 'closest tr' }}"
                hx-swap="outerHTML"
                hx-headers='{"HX-Request": "true"}'>Cancel</button>
      </form>
    </div>
  </td>
</tr>
```

The hidden origin input is auto-emitted by the existing `{% for key, value in form_values.items() %}` loop because `origin` is now in `form_values` (added in step 8.4 (e)).

Strengthen the soft-warn round-trip test in step 8.1 to ALSO assert `colspan="9"` on the returned fragment (R1-Major-1 + Codex Minor 2):

```python
def test_soft_warn_confirm_round_trips_origin(tmp_path: Path):
    """R4-Major-1 + R1-Major-1 (Codex R1) — soft-warn confirm
    round-trips origin AND renders the right colspan for the
    originating surface.

    Discriminating: pre-fix path renders colspan=8 in soft_warn_confirm
    even when origin=hyp-recs (R1-Major-1 caught this); the colspan=9
    assertion catches the layout regression that the hidden-field-
    presence assertion alone would miss.
    """
    # ... (seed as before — soft_warn trip via existing position count) ...
    # ... assertions:
    assert resp.status_code == 200
    body = resp.text
    assert 'name="origin"' in body
    assert 'value="hyp-recs"' in body
    assert "/hyp-recs/refresh" in body
    assert 'colspan="9"' in body, (
        "soft-warn confirm fragment must render colspan=9 when origin="
        "hyp-recs (R1-Major-1); pre-fix renders colspan=8 — visually"
        " broken inside the 9-cell hyp-recs table"
    )
```

- [ ] **Step 8.6: Run the tests; expect 3 PASS.**

```bash
python -m pytest tests/web/test_routes/test_hyp_recs_expand_route.py -v -k "rerender_preserves_origin or round_trips_origin"
```

- [ ] **Step 8.7: Run the full fast suite.**

```bash
python -m pytest -m "not slow" -q
```

Expected: 1278 + 3 = 1281 passing. Existing soft-warn tests at `tests/web/test_routes/test_trade_entry_chart_pattern.py` MUST stay green — origin defaults to "watchlist" for existing watchlist callers; the Cancel target stays `/watchlist/{ticker}/expand`.

- [ ] **Step 8.8: Commit.**

```bash
git add tests/web/test_routes/test_hyp_recs_expand_route.py \
  swing/web/templates/partials/trade_entry_form.html.j2 \
  swing/web/templates/partials/soft_warn_confirm.html.j2 \
  swing/web/routes/trades.py
git commit -m "$(cat <<'EOF'
feat(web): Task 8 — origin survives POST round-trips (R4-Major-1)

Adds hidden <input type="hidden" name="origin" value="{{ vm.origin }}">
to trade_entry_form.html.j2 so the discriminator survives every POST
submission. entry_post POST handler reads form-payload origin
(whitelist-coerced); threaded through:
  - _rerender_entry_form_with_error (rationale validation, stop>=entry,
    chart-pattern ValueError, chart-pattern IntegrityError);
  - DuplicateOpenPositionException re-render branch;
  - soft-warn form_values dict.

soft_warn_confirm.html.j2 Cancel parameterized on form_values.origin;
the hidden origin input is auto-emitted by the existing
form_values.items() loop.

Discriminating tests cover all three round-trip paths (validation
error, duplicate position, soft-warn). Each asserts colspan=9 +
/hyp-recs/refresh Cancel target — pre-fix paths would render
colspan=8 + watchlist Cancel.

Spec §3.8b.3 R4-Major-1.
EOF
)"
```

---

## Task 9: Anchor consistency for `origin=hyp-recs` + freshness footer (R4-Major-2)

**Why ninth (final).** Per spec §7.1 step 6 final sub-task. Closes the gap where `build_entry_form_vm` reads sector/industry from `latest_evaluation_run_id` (which can pick a newer standalone-eval row) while chart-pattern reads from `latest_completed_pipeline_run`. Pre-Q7/Q8 this anchor split was an accepted residual (the watchlist's frozen target/stop dominated the form's order-related fields, so candidate-derived sector/industry only contributed metadata). Post-Q7/Q8 + Task 7's fallback, the candidate now contributes ORDER-RELATED fields (entry_price, initial_stop) too — a mixed-anchor form would show "entry price from eval run N, chart-pattern from pipeline run M" with no disclosure.

**Resolution.** When `origin=hyp-recs`, bind ALL candidate-derived reads (sector, industry, pivot, initial_stop, chart-pattern) to `latest_completed_pipeline_run`'s `evaluation_run_id`. For `origin=watchlist`, preserve the existing behavior (sector/industry from `latest_evaluation_run_id`; chart-pattern from `latest_completed_pipeline_run`) — backward compat for the watchlist surface.

**Files:**
- Modify: `swing/web/view_models/trades.py` — `TradeEntryFormVM` gains `pipeline_finished_at: str | None = None` trailing-default field; `build_entry_form_vm` branches on `coerced_origin` for the eval-anchor selection.
- Modify: `swing/web/templates/partials/trade_entry_form.html.j2` — freshness footer when `vm.origin == 'hyp-recs'` showing `Candidate context as of pipeline finished {{ vm.pipeline_finished_at }}`.
- Test: extend `tests/web/test_routes/test_hyp_recs_expand_route.py` — anchor-consistency discriminating test + watchlist-origin backward-compat regression test.

**Discriminating-test sanity-check.** Test seeds TWO eval rows: a pipeline-bound completed eval (eval_id=N with sector="Energy", industry="Oil & Gas", pivot=$50) + a newer standalone eval (eval_id=N+1 with sector="Healthcare", industry="Biotech", pivot=$60) for the same ticker. Build the hyp-recs-origin entry form; assert sector/industry/pivot/initial_stop come from N ("Energy" / "Oil & Gas" / $50). A pre-fix path (sector/industry from `latest_evaluation_run_id`) yields N+1 ("Healthcare" / "Biotech") — the assertion catches the regression. Parallel test: build watchlist-origin entry form on the same fixture; assert sector/industry come from N+1 ("Healthcare" / "Biotech") AND chart-pattern from N — backward-compat preserved.

- [ ] **Step 9.1: Write the failing tests.** Append two tests to `tests/web/test_routes/test_hyp_recs_expand_route.py`:

```python
def test_hyp_recs_form_anchor_matches_expansion_anchor(tmp_path: Path):
    """R4-Major-2 — when origin=hyp-recs, ALL candidate-derived reads
    bind to latest_completed_pipeline_run's evaluation_run_id (matches
    the hyp-recs expansion's anchor).

    Discriminating: insert two eval rows with DIFFERENT sector/industry/
    pivot for the same ticker. Pre-fix path picks the newer eval
    (latest_evaluation_run_id) — yields N+1 values. Post-fix picks
    the pipeline-bound eval — yields N values.
    """
    cfg = _make_cfg(tmp_path)
    from swing.data.db import connect, ensure_schema
    ensure_schema(cfg.paths.db_path)
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Eval N (older): pipeline-bound; values "Energy" / "Oil & Gas E&P".
            conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count)
                   VALUES ('2026-04-29T08:00:00','2026-04-28','2026-04-29',
                           NULL, 1, 1, 0, 0, 0, 0)"""
            )
            eval_n = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """INSERT INTO pipeline_runs
                   (state, started_ts, finished_ts, action_session_date,
                    data_asof_date, evaluation_run_id, charts_status)
                   VALUES ('complete','2026-04-29T07:00:00',
                           '2026-04-29T08:00:00','2026-04-29','2026-04-28',
                           ?, 'ok')""",
                (eval_n,),
            )
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot,
                    initial_stop, adr_pct, tight_streak, pullback_pct,
                    prior_trend_pct, rs_rank, rs_return_12w_vs_spy,
                    rs_method, pattern_tag, notes, sector, industry)
                   VALUES (?, 'XOM', 'aplus', 49.0, 50.0, 48.0, 2.0, 5,
                           NULL, NULL, NULL, NULL, 'fallback_spy',
                           NULL, NULL, 'Energy', 'Oil & Gas E&P')""",
                (eval_n,),
            )
            # Eval N+1 (newer): standalone (NOT pipeline-bound); values
            # "Healthcare" / "Biotechnology". Same ticker, different
            # candidate values.
            conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count)
                   VALUES ('2026-04-29T10:00:00','2026-04-29','2026-04-29',
                           NULL, 1, 1, 0, 0, 0, 0)"""
            )
            eval_np1 = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, pivot,
                    initial_stop, adr_pct, tight_streak, pullback_pct,
                    prior_trend_pct, rs_rank, rs_return_12w_vs_spy,
                    rs_method, pattern_tag, notes, sector, industry)
                   VALUES (?, 'XOM', 'aplus', 59.0, 60.0, 58.0, 2.0, 5,
                           NULL, NULL, NULL, NULL, 'fallback_spy',
                           NULL, NULL, 'Healthcare', 'Biotechnology')""",
                (eval_np1,),
            )
    finally:
        conn.close()
    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.get(
            "/trades/entry/form?ticker=XOM&origin=hyp-recs",
            headers={"HX-Request": "true", "HX-Target": "hyp-rec-row-XOM"},
        )
    assert resp.status_code == 200
    body = resp.text
    # hyp-recs origin: anchor on eval N (pipeline-bound); sector="Energy".
    assert "Energy" in body
    assert "Oil &amp; Gas" in body or "Oil & Gas" in body, (
        "hyp-recs origin must read sector/industry from"
        " latest_completed_pipeline_run's eval (N), NOT the newer"
        " standalone eval (N+1)"
    )
    # initial_stop=$48 (from eval N).
    assert 'value="48.00"' in body
    assert "Healthcare" not in body or '"Healthcare"' not in body, (
        "hyp-recs origin must NOT read sector from the newer standalone"
        " eval (N+1); 'Healthcare' is the regression signal"
    )
    # Freshness footer present.
    assert "As of pipeline finished" in body
    assert "Candidate context" in body, (
        "freshness footer wording must be 'Candidate context as of"
        " pipeline finished' (R5-Minor-2)"
    )


def test_watchlist_origin_form_preserves_existing_anchor_split(tmp_path: Path):
    """R4-Major-2 — backward-compat: watchlist-origin form keeps the
    existing anchor split (sector/industry from latest_evaluation_run_id;
    chart-pattern from latest_completed_pipeline_run).

    Discriminating: same fixture as above. Watchlist origin should pick
    'Healthcare' from N+1; a regression that anchored watchlist origin
    on latest_completed_pipeline_run would yield 'Energy' (the test
    fails).
    """
    cfg = _make_cfg(tmp_path)
    # Same two-eval seed as above; ticker XOM on the watchlist.
    # ... (implementer copies the seed pattern; adds a watchlist row
    # for XOM via upsert_watchlist_entry) ...
    app = create_app(cfg)
    with TestClient(app) as client:
        resp = client.get(
            "/trades/entry/form?ticker=XOM",  # NO ?origin= → defaults to watchlist.
            headers={"HX-Request": "true", "HX-Target": "watchlist-row-XOM"},
        )
    assert resp.status_code == 200
    body = resp.text
    # Watchlist origin: existing anchor split (sector/industry from
    # latest_evaluation_run_id = N+1).
    assert "Healthcare" in body, (
        "watchlist origin must preserve existing anchor split (sector"
        " from latest_evaluation_run_id = N+1); regression to"
        " latest_completed_pipeline_run would yield 'Energy'"
    )
    # No freshness footer for watchlist origin.
    assert "Candidate context as of pipeline finished" not in body
```

- [ ] **Step 9.2: Run failing tests; expect 1 FAIL** (`test_hyp_recs_form_anchor_matches_expansion_anchor`). The watchlist test passes pre-fix because the existing behavior is the watchlist behavior.

- [ ] **Step 9.3: Modify `swing/web/view_models/trades.py`'s `build_entry_form_vm`** to branch on `coerced_origin`:

```python
def build_entry_form_vm(
    *, ticker: str, cfg: Config, cache: PriceCache, executor,
    origin: str = "watchlist",
) -> TradeEntryFormVM:
    coerced_origin = _coerce_origin(origin)
    ticker = ticker.upper()
    cls = None
    pipeline_finished_at: str | None = None
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            wl = list_active_watchlist(conn)
            wl_entry = next((w for w in wl if w.ticker == ticker), None)
            open_trades = list_open_trades(conn)
            exits = list_all_exits(conn)
            cash_movements = list_cash(conn)
            # Resolve the pipeline-bound completed eval ONCE.
            pipeline_eval_row = conn.execute(
                """SELECT id, evaluation_run_id, finished_ts FROM pipeline_runs
                   WHERE state = 'complete'
                   ORDER BY finished_ts DESC, id DESC LIMIT 1"""
            ).fetchone()
            pipeline_run_id = (
                pipeline_eval_row[0] if pipeline_eval_row else None
            )
            pipeline_eval_id = (
                pipeline_eval_row[1] if pipeline_eval_row else None
            )
            pipeline_finished_at = (
                pipeline_eval_row[2] if pipeline_eval_row else None
            )
            # Chart-pattern reads ALWAYS bind to pipeline_run_id (existing
            # behavior; both origins).
            if pipeline_run_id is not None:
                from swing.data.repos.pattern_classifications import (
                    get_classification,
                )
                cls = get_classification(
                    conn, pipeline_run_id=pipeline_run_id, ticker=ticker,
                )
            # Sector / industry / pivot / initial_stop reads — anchor
            # depends on origin (R4-Major-2).
            from swing.web.view_models.dashboard import (
                latest_evaluation_run_id,
            )
            cand_sector = ""
            cand_industry = ""
            cand_pivot: float | None = None
            cand_initial_stop: float | None = None
            if coerced_origin == "hyp-recs":
                # All candidate-derived reads bind to the pipeline's
                # own eval — matches build_hyp_recs_expanded.
                sector_eval_id = pipeline_eval_id
            else:
                # Watchlist origin (existing anchor split for
                # backward-compat).
                sector_eval_id = latest_evaluation_run_id(conn)
            if sector_eval_id is not None:
                cand_row = conn.execute(
                    """SELECT sector, industry, pivot, initial_stop FROM candidates
                       WHERE evaluation_run_id = ? AND ticker = ?""",
                    (sector_eval_id, ticker),
                ).fetchone()
                if cand_row is not None:
                    cand_sector = cand_row[0] or ""
                    cand_industry = cand_row[1] or ""
                    cand_pivot = cand_row[2]
                    cand_initial_stop = cand_row[3]
    finally:
        conn.close()
    # ... existing live-price + sizing-hint + cls-mapping logic ...
    return TradeEntryFormVM(
        # ... existing args ...
        sector=cand_sector,
        industry=cand_industry,
        origin=coerced_origin,
        pipeline_finished_at=(
            pipeline_finished_at if coerced_origin == "hyp-recs" else None
        ),
    )
```

Add the field to `TradeEntryFormVM`:

```python
@dataclass(frozen=True)
class TradeEntryFormVM:
    # ... existing fields ...
    origin: Literal["watchlist", "hyp-recs"] = "watchlist"
    # Spec §3.8b.4 R4-Major-2 — when origin=hyp-recs, this is the
    # pipeline_runs.finished_ts of the binding pipeline run; rendered
    # in the freshness footer. None for watchlist origin.
    pipeline_finished_at: str | None = None
```

- [ ] **Step 9.4: Modify `swing/web/templates/partials/trade_entry_form.html.j2`** — add freshness footer when `vm.origin == 'hyp-recs'`. Insert near the bottom of the form, BEFORE the Submit / Cancel buttons:

```jinja
{% if vm.origin == 'hyp-recs' and vm.pipeline_finished_at %}
  <p class="freshness muted">
    Candidate context as of pipeline finished {{ vm.pipeline_finished_at }}
  </p>
{% endif %}
```

The wording is deliberately scoped to "candidate context" per spec §3.8b.4 + R5-Minor-2 — the entry form's `entry_price` field still comes from the live `PriceCache` (or `wl_entry.last_close` fallback), NOT the pipeline snapshot. The wording avoids implying live-price freshness.

- [ ] **Step 9.5: Run the tests; expect 2 PASS.**

```bash
python -m pytest tests/web/test_routes/test_hyp_recs_expand_route.py -v -k "anchor"
```

- [ ] **Step 9.6: Run the full fast suite.**

```bash
python -m pytest -m "not slow" -q
```

Expected: 1281 + 2 = 1283 passing. Existing tests at `tests/web/test_view_models/test_trade_entry_form_classification.py` MUST stay green — chart-pattern still binds to `pipeline_run_id`; sector/industry for watchlist origin still binds to `latest_evaluation_run_id`. If any existing tests fail, audit whether they depended on a specific eval-anchor that changed under the new branch — surface in return report.

- [ ] **Step 9.7: Commit.**

```bash
git add tests/web/test_routes/test_hyp_recs_expand_route.py \
  swing/web/view_models/trades.py \
  swing/web/templates/partials/trade_entry_form.html.j2
git commit -m "$(cat <<'EOF'
feat(web): Task 9 — anchor consistency for hyp-recs origin (R4-Major-2)

When origin=hyp-recs, build_entry_form_vm binds ALL candidate-derived
reads (sector, industry, pivot, initial_stop, chart-pattern) to
latest_completed_pipeline_run's evaluation_run_id — matches the
hyp-recs expansion's anchor (build_hyp_recs_expanded, Task 5.2).
For origin=watchlist, preserves the existing anchor split
(sector/industry from latest_evaluation_run_id; chart-pattern from
latest_completed_pipeline_run) — backward-compat.

Adds TradeEntryFormVM.pipeline_finished_at and a freshness footer on
the form when origin=hyp-recs: 'Candidate context as of pipeline
finished {ISO}'. Wording deliberately scoped to 'candidate context'
(R5-Minor-2) — entry_price still comes from live PriceCache /
wl_entry.last_close, so the footer must NOT imply live-price
freshness.

Discriminating-test pair seeds two eval rows (eval N pipeline-bound
+ eval N+1 standalone-newer) with DIFFERENT sector/industry/pivot
for the same ticker. hyp-recs origin reads from N (Energy / Oil & Gas
/ $48 stop); watchlist origin reads from N+1 (Healthcare / Biotech)
for sector/industry. Catches a regression in either direction.

Closes the multi-path-ingestion lesson class (input-side analog of
multi-resolver-output) for the new multi-origin entry-form work.

Spec §3.8b.4 R4-Major-2 + R5-Minor-2.
EOF
)"
```

---

## Plan-level done criteria

Per spec §9 + writing-plans brief §6:

- [ ] `Config.web.chase_factor: float = 0.01` field added; no toml row introduced (Task 2 + toml-shadowing audit).
- [ ] `HypothesisRecommendation` UNCHANGED (Task 5.7 sort-neutrality regression confirms; spec §3.5.1 R1-Major-1).
- [ ] `HypRecsExpandedVM` dataclass exists; `build_hyp_recs_expanded` returns it on the happy path and `None` on rotation / no-run / degenerate-sizing (Task 5.2).
- [ ] `HypRecsSectionVM` + `build_hyp_recs_section` exist; refresh route uses scoped builder NOT full `build_dashboard` (Task 4 + monkeypatch-sentinel discriminating test).
- [ ] `_build_active_recommendations` shared helper exists; `build_dashboard` and `build_hyp_recs_section` both call it (Task 3).
- [ ] `GET /hyp-recs/{ticker}/expand` returns expansion partial; 404 for unknown / rotated tickers; chart-unavailable div for out-of-scope tickers (Task 5.3).
- [ ] `GET /hyp-recs/refresh` returns the scoped section partial; row-target prefix `hyp-rec-row-` covers 4xx/5xx swaps; refresh does NOT trigger open-trades / watchlist / OHLCV builds (Tasks 4 + 5.3).
- [ ] Per-row Enter button (Q7) renders with byte-equivalent HTMX attrs to watchlist Enter; NO `stopPropagation` (Task 5.5 + discriminating-test pair vs watchlist).
- [ ] Take this trade button (Q8) renders with same HTMX attrs as per-row Enter (D.2 = option (a)); differentiated label + styling (D.3) (Task 5.6).
- [ ] Hyp-recs flat table renders 9 columns (chevron + 7 existing + Enter) (Tasks 5.4 + 5.5).
- [ ] Watchlist `Pivot` column renders `candidates.pivot` across ALL THREE render sites + falls back to `entry_target` + "—" when both absent + lightning trigger preserved (Task 1).
- [ ] Sizing twins computed and rendered with two-row layout (Task 5.2 + 5.3).
- [ ] Sector + Industry rendered in the Context group; empty strings render as `"—"` (Task 5.3).
- [ ] "As of pipeline finished <ISO>" footer present on the expansion (Task 5.3) AND on the entry form when `origin=hyp-recs` (Task 9, wording: "Candidate context as of pipeline finished").
- [ ] All test layers green: sizing twins (5.1); expansion VM (5.2); route 200/404/500/chart-scope/anchor (5.3); per-row Enter swap + Take-this-trade swap + muscle-memory mirror (5.5 + 5.6); 9-column template regression (5.4 + 5.5); CC pivot 3-render-site coverage + dash sentinel + lightning binding preserved (Task 1); origin-aware entry form colspan + Cancel (Task 6); off-watchlist candidate fallback (Task 7); origin survives all 3 POST round-trips (Task 8); anchor consistency for hyp-recs origin (Task 9).
- [ ] Adversarial Codex review reaches `NO_NEW_CRITICAL_MAJOR`.
- [ ] No new migration; no new repo function (verified at writing-plans: existing `fetch_candidates_for_run` is reused).
- [ ] Toml-shadowing audit recorded clean for `chase_factor` (Task 2 step 2.0 audit).

**Final test-suite floor: ~1283 passing** at end-of-plan (1228 baseline + ~55 plan-added; trust pytest output, not the pinned count — each task documents its delta).

**Implementation sequencing.** Tasks 1-9 follow spec §7.1 ordering with the documented Task 3↔4 swap (refactor first, then refresh route — so the refresh route can consume the refactored helper from Task 3) and the Task 5/Task 6 ordering acknowledged transient state (Task 5 ships the buttons emitting `?origin=hyp-recs`; Task 6 makes the GET handler read it; Tasks 7-9 complete the form's origin-aware behavior). Each task is atomically revertable.

---

