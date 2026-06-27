# 3e.8 Bundle 1 — Advisory parity (§4.E + §4.F) dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Wire existing advisory rules from `swing/trades/advisory.py` into TWO surfaces that don't render advisories today:
1. **§4.E** — Pipeline-emitted briefing (`exports/<session>/briefing.md` + `briefing.html`) — fix `swing/pipeline/runner.py:921` `open_trade_advisories={}` hard-code.
2. **§4.F** — Trade detail page (`/trades/{id}`) + open-positions expanded HTMX partial — VMs already carry data; templates need to consume it.

NO new advisory rules. NO doctrine implications. Pure parity work — surfaces that should render advisories already (per VM/data layer) but don't (per template layer).

**Expected duration:** ~5-6 hr implementation + ~30-45 min dispatch overhead. Total ~6-7 hr.

**Skill posture:**
- Invoke `superpowers:subagent-driven-development` directly (NOT via `copowers:executing-plans` wrapper).
- DO NOT invoke `superpowers:writing-plans` or `copowers:brainstorming` — design is locked in §0.3 below.
- Adversarial review via `copowers:adversarial-critic` after task families land. Iterate to NO_NEW_CRITICAL_MAJOR. Expected 1-2 Codex rounds (small surface; pure wire-through; risks concentrated on template-rendering correctness).

---

## §0 Read first

### §0.1 Backlog entry
- `docs/phase3e-todo.md` 2026-05-10 §3e.8 disposition section "Bundle 1 — Advisory-parity (§4.E + §4.F)"
- `docs/3e8-sell-side-advisories-investigation.md` §4.E + §4.F + §3.E + §3.F

### §0.2 Code surface

**For §4.E (briefing):**
- `swing/pipeline/runner.py:921` — current `open_trade_advisories={}` hard-code. Search nearby for the briefing-render call.
- `swing/rendering/briefing.py:51` — per-open-position rendering already has `advisory: list` field; just receives empty list today.
- `swing/trades/advisory.py` — current advisory rule surface. Read end-to-end. Provides `AdvisoryContext` + the seven advisory functions (`suggest_breakeven`, `suggest_trail_ma_10`, `suggest_trail_ma_20`, `suggest_exit_close_below_10ma`, `suggest_exit_close_below_20ma`, `suggest_exit_close_below_50ma`, `suggest_weather`, `suggest_time_stop`). Identify the public function call signature the dashboard uses to compose advisories per open trade.
- `swing/web/view_models/dashboard.py` (or `swing/web/view_models/open_positions_row.py`) — find the call site that builds `OpenPositionsRowVM.advisories: tuple[AdvisorySuggestionVM, ...]`. The pipeline runner needs to mirror this composition.

**For §4.F (trade detail + expanded row):**
- `swing/web/templates/trades/detail.html.j2` — current trade detail template. NO advisory column today.
- `swing/web/templates/partials/open_positions_expanded.html.j2:5` — explicit "no advisories list" exclusion comment. Remove the exclusion + add the rendering.
- `swing/web/view_models/trades.py` — `TradeDetailVM` (Phase 7 Sub-C T1). Verify whether `advisories` field exists OR needs to be added. If added, mirror `OpenPositionsRowVM.advisories` shape exactly.
- `swing/web/routes/trades.py` — trade-detail route handler. May need to thread `cache` + `executor` if VM construction needs them for advisory computation.

### §0.3 LOCKED DESIGN DECISIONS (DO NOT re-litigate)

Locked by orchestrator + operator in-thread design lock 2026-05-10:

1. **NO new advisory rules.** This dispatch wires EXISTING `swing/trades/advisory.py` rules into NEW surfaces. The advisory composition logic (which rules fire, in what order, with what messages) is already established by the dashboard path; this dispatch mirrors it.

2. **Briefing-side advisory composition** (§4.E):
   - In `_step_briefing` (or wherever the briefing-render call lives in `runner.py`): for each open trade, build an `AdvisoryContext` using the OHLCV data already loaded for the chart-render step (do NOT add new yfinance calls).
   - Compose advisories using the same public function the dashboard uses (identify it during recon).
   - Pass the resulting `tuple[AdvisorySuggestion, ...]` per trade as `open_trade_advisories[trade_id] = (...)` to the briefing renderer.
   - Briefing-side `AdvisoryContext` may differ slightly from web-side (no live PriceCache; uses pipeline-loaded OHLCV close + last_close from candidates table). Document the divergence in code comment.

3. **Trade-detail advisory rendering** (§4.F):
   - Add `advisories: tuple[AdvisorySuggestionVM, ...]` field to `TradeDetailVM` with `field(default_factory=tuple)`.
   - Builder fetches advisories via the same path as `OpenPositionsRowVM` (mirror the call).
   - Template: append a new section (after fills + events; before chart) with `<h2>Advisories</h2>` + the same per-advisory rendering pattern as the dashboard `partials/open_positions_advisories.html.j2` (or wherever the dashboard's advisory column rendering lives).
   - When `vm.advisories` is empty: render `<p class="muted">No advisories.</p>` (or equivalent muted-text indicator).

4. **Open-positions expanded row** (§4.F second target):
   - Remove the "no advisories list" exclusion comment from `partials/open_positions_expanded.html.j2:5`.
   - Add advisory rendering to the expanded row's content area. Use the SAME include target as the dashboard list-view advisory rendering (per CLAUDE.md gotcha "HTMX OOB-swap partials that hand-duplicate full-page markup drift silently" — single canonical partial, not duplicated markup).
   - VMs already carry the advisory data per `swing/web/view_models/dashboard.py:967` (per investigation §4.F notes). Verify this is still accurate; the expand route should be receiving the existing per-row VM.

5. **Briefing renderer (snapshot test):** verify the briefing rendering pipeline has a snapshot test that catches the pre-refactor empty-advisory rendering vs the post-refactor populated rendering. If absent, ADD ONE.

6. **No schema changes; no new advisory rules; no V2.1 §VII.F routing.** Pure wire-through. Charts stay light per Bundle 0 (3e.10 dark theme); advisories rendered via existing CSS variables (the 3e.10 theme tokens cover this).

7. **HTMX safety:** the trade-detail page is a full page render (not HTMX swap target), so the `<tr>`-leading makeFragment gotcha does NOT apply. The open-positions expanded row IS an HTMX swap target — verify the response shape stays `<tr>...</tr>` per existing convention; the new advisory rendering goes INSIDE the existing `<tr>` content, not as a leading element.

8. **Per-row dedup with dashboard list view:** the open-positions expanded row currently shows different content than the dashboard list-view row (the expanded view adds context like sector/industry per `partials/open_positions_expanded.html.j2`). Adding advisories to the expanded row should NOT duplicate the dashboard list-view advisory column — the operator should see advisories in BOTH surfaces (list view + expanded). Mirror the dashboard rendering pattern; do NOT add divergent presentation.

---

## §1 Strategic context

This is the post-3e.8-investigation Bundle 1 commission. Pure parity-gap closure: existing advisory rules render correctly on the dashboard list view but are absent from briefing + trade detail + expanded row surfaces. Gap is structural (template-layer omission), not a doctrine question.

**Schema state (binding):** Production DB at schema_version 16 post-§4.G transcription completion at HEAD `a0d8d21`. No schema work in scope.

**What's NOT in scope:**
- Adding new advisory rules (Bundle 2 work)
- Maturity-stage gating (Bundle 3 work)
- Per-theme chart regeneration (Bundle 0 deferred V1.5)
- CSS scoping for advisory-column visual polish

---

## §2 Worktree + binding conventions

### §2.1 Worktree
- **Branch:** `3e8-bundle-1-advisory-parity`
- **Worktree directory:** `.worktrees/3e8-bundle-1-advisory-parity/` at repo root.
- **BASELINE_SHA:** `a0d8d21` (HEAD of `main` post-Minervini-transcription).

### §2.2 Marker-file workflow
- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all task families land + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §2.3 Commits
- Conventional prefix:
  - `feat(pipeline): Task A.X — <description>` for runner.py changes (§4.E)
  - `feat(rendering): Task A.X — <description>` for briefing renderer changes (§4.E)
  - `feat(web): Task B.X — <description>` for trade-detail VM + route changes (§4.F)
  - `feat(templates): Task B.X — <description>` for template additions (§4.F)
  - `test(...)` for test-only commits
  - `fix(area): Codex RN Major #X (internal) — <description>` for Codex-driven fixes
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.
- **TDD:** failing test first, minimal implementation, pass, commit. One red-green cycle per logical change OR cluster cycles when tests are essentially discriminators of one feature.

### §2.4 Branch isolation + ownership
- Commits on branch only; no push to origin from worktree.
- **Implementer owns:** task-family TDD commits → marker-file removal → adversarial-critic → return report.
- **Operator owns:** witnessed verification gate (§5).
- **Orchestrator owns:** integration merge to main + post-merge housekeeping.

### §2.5 Verify command
PowerShell from inside worktree:
```powershell
$env:PYTHONPATH = "."; python -m swing.cli web
```

---

## §3 Per-task implementation breakdown

### §3.1 Task family A — §4.E briefing advisory wire-through

**Acceptance criteria:**

- (A.AC.1) Pipeline `_step_briefing` (or equivalent) builds an `AdvisoryContext` per open trade using OHLCV data already loaded for the chart-render step (no new yfinance calls).
- (A.AC.2) Composes advisories via the same public function path the dashboard uses (identify during recon).
- (A.AC.3) Passes per-trade `tuple[AdvisorySuggestion, ...]` as `open_trade_advisories[trade_id] = (...)` to the briefing renderer.
- (A.AC.4) `briefing.md` and `briefing.html` per-open-position rendering populates the existing `advisory` field with the per-trade advisory list (no longer empty).
- (A.AC.5) Snapshot/golden test verifies the briefing populated-vs-empty path:
  - Pre-refactor baseline: `advisory: []` for every open trade
  - Post-refactor: `advisory: [...non-empty list...]` for trades with active advisory triggers
- (A.AC.6) When NO advisories trigger for an open trade (e.g., trade is at +0.1R with no MA crossings), the per-trade `advisory` field is `[]` (not absent) — operator sees explicit "no advisories" indicator.

**Suggested test names:**

- `test_step_briefing_populates_advisory_per_open_trade` — fixture: 2 open trades; one in trail-MA range, one at breakeven. Assert briefing rendering includes per-trade advisory text.
- `test_step_briefing_advisory_is_empty_when_no_triggers` — fixture: open trade with no advisory triggers. Assert `advisory: []` in render.
- `test_step_briefing_no_extra_yfinance_calls` — instrument the OHLCV fetch path; assert that `_step_briefing` does not introduce new fetches beyond the chart-step's existing fetches.

**Suggested commit shape:**
- A.1: extract advisory-composition helper (if not already centralized) — commit if needed
- A.2: pipeline runner change + RED+GREEN test — commit (`feat(pipeline): Task A.2 — populate open_trade_advisories per-trade in briefing render`)
- A.3: briefing-renderer snapshot test if helpful — commit

**Watch items:**
- The `AdvisoryContext` construction may need different arguments on the pipeline-side vs web-side (no live PriceCache on pipeline side; uses pipeline-loaded OHLCV `close` + `last_close` from candidates table). Document the divergence inline.
- Per CLAUDE.md gotcha "OHLCV fetch scope = open-trade tickers ONLY" — verify the chart-step's OHLCV fetch already covers all open trades; advisory composition should not require additional tickers.
- Per CLAUDE.md gotcha "yfinance `history(interval='1d')` includes the in-progress bar during market hours" — pipeline OHLCV is already last-completed-session-anchored per existing pipeline discipline; advisory composition should consume the same anchored OHLCV.

### §3.2 Task family B — §4.F trade-detail + expanded-row advisory rendering

**Acceptance criteria:**

- (B.AC.1) `TradeDetailVM` gains `advisories: tuple[AdvisorySuggestionVM, ...]` field with `field(default_factory=tuple)`.
- (B.AC.2) `TradeDetailVM` builder fetches advisories via the same path as `OpenPositionsRowVM` (mirror the call).
- (B.AC.3) `swing/web/templates/trades/detail.html.j2` renders the advisories section after fills + events + before chart, with the SAME per-advisory rendering pattern as the dashboard.
- (B.AC.4) When `vm.advisories` is empty, template renders `<p class="muted">No advisories.</p>`.
- (B.AC.5) `swing/web/templates/partials/open_positions_expanded.html.j2:5` "no advisories list" exclusion comment removed; advisories rendered in the expanded row using the SAME include target as the dashboard list view (per HTMX OOB-swap drift gotcha — single canonical partial).
- (B.AC.6) Trade-detail route handler threads `cache` + `executor` if needed for advisory composition (mirror dashboard route's pattern).

**Suggested test names:**

- `test_trade_detail_vm_has_advisories_field` — instantiate VM; assert field accessible.
- `test_trade_detail_vm_populates_advisories_when_open_trade` — fixture: open trade with active trail-MA condition; assert `vm.advisories` non-empty.
- `test_trade_detail_vm_advisories_empty_for_closed_trade` — fixture: closed trade; assert `vm.advisories` is empty.
- `test_trade_detail_route_renders_advisories_section` — TestClient GET `/trades/{id}`; assert response body contains advisory section heading + at least one rendered advisory.
- `test_trade_detail_route_renders_empty_state_when_no_advisories` — fixture: closed trade or open trade with no triggers; assert response body contains "No advisories." muted message.
- `test_open_positions_expanded_renders_advisories` — TestClient GET `/trades/open/{id}/expand`; assert response body contains advisory rendering (mirroring dashboard list-view content).

**Suggested commit shape:**
- B.1: VM extension + RED+GREEN tests — commit (`feat(web): Task B.1 — TradeDetailVM advisories field + builder`)
- B.2: trade-detail template addition + RED+GREEN tests — commit (`feat(templates): Task B.2 — render advisories section on trade detail page`)
- B.3: expanded-row template change + RED+GREEN tests — commit (`feat(templates): Task B.3 — render advisories in open-positions expanded row`)

**Watch items:**
- Per CLAUDE.md gotcha "`base.html.j2` is shared — new `vm.foo` field requires adding to EVERY base-layout VM" — `TradeDetailVM` is the page VM for `/trades/{id}` which extends `base.html.j2`. Adding `advisories` to `TradeDetailVM` does NOT require updating other base-layout VMs (DashboardVM / PipelineVM / etc.) because base.html.j2 doesn't dereference `vm.advisories` — it's only used by `trades/detail.html.j2`. But CHECK: does `base.html.j2` reference `vm.advisories` for any banner/badge feature? If yes (unlikely per current code), the gotcha applies and EVERY base-layout VM needs the field.
- Per CLAUDE.md gotcha "HTMX OOB-swap partials that hand-duplicate full-page markup drift silently" — the expanded-row template should INCLUDE the same canonical advisory-rendering partial the dashboard list view uses. Do NOT copy-paste markup.
- Per CLAUDE.md gotcha "TestClient lifespan" — tests touching `app.state.price_fetch_executor` MUST use `with TestClient(app) as client:` (enters lifespan).

---

## §4 Adversarial review (Codex)

### §4.1 Setup (IMPLEMENTER runs this — convention per orchestrator-context "Executing-plans dispatch convention" 2026-05-02)

After ALL task-family commits land + tests are GREEN at branch HEAD:

1. `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
2. Invoke `copowers:adversarial-critic` with:
   - `PHASE`: `3e8-bundle-1-advisory-parity`
   - `SPEC_PATH`: `docs/3e8-bundle-1-advisory-parity-brief.md`
   - `PLAN_PATH`: `docs/3e8-bundle-1-advisory-parity-brief.md`
   - `BASELINE_SHA`: `a0d8d21`
3. Iterate rounds until **NO_NEW_CRITICAL_MAJOR**.
4. Per-round fixes commit as `fix(area): Codex RN Major #X (internal) — <description>`.
5. Expected convergence: **1-2 rounds**.

### §4.2 Pre-empt list

Adversarial-review value-add concentrates on:

- **Briefing-side OHLCV scope.** Verify advisory composition does NOT add new yfinance calls (per A.AC.5). Cheap to verify — instrument the call count.
- **VM field default.** `TradeDetailVM.advisories` MUST default to empty tuple to avoid breaking existing callers. Same pattern as `OpenPositionsRowVM`.
- **Template OOB-swap drift.** The expanded-row template should INCLUDE the same canonical advisory-rendering partial as the dashboard list view. Hand-duplicated markup is a known failure mode.
- **Empty-state rendering.** Both the trade-detail page AND the expanded row must show the empty-state message when `vm.advisories` is empty (closed trade; trade with no triggers). Don't silently render nothing.
- **Briefing snapshot test discipline.** Pre-refactor (`advisory: []`) vs post-refactor (`advisory: [...]`) golden test catches future regressions where the refactor accidentally reverts.
- **HTMX expanded-row response shape.** Verify the response continues to start with `<tr>` (not the new advisory content); per CLAUDE.md gotcha "HTMX response leading with `<tr>` triggers `makeFragment` synthetic-table-wrap" the response shape pattern must be preserved.

---

## §5 Operator-witnessed verification surfaces

After NO_NEW_CRITICAL_MAJOR:

- **Surface 1 — Briefing populated.** Operator runs `swing pipeline run` (or waits for the next pipeline run); opens `exports/<session>/briefing.md` and `briefing.html`; verifies per-open-position rendering includes the advisory column with non-empty content for trades with active triggers (e.g., DHC if its trail-MA conditions trip).
- **Surface 2 — Trade detail advisories.** Operator navigates to `http://127.0.0.1:8080/trades/{id}` for an open trade; verifies advisories section renders after fills + events + before chart, with the same content as the dashboard list view.
- **Surface 3 — Expanded row advisories.** Operator clicks a row's expand action on the dashboard open-positions table; verifies advisories render inside the expanded view, matching the list-view advisory column content.
- **Surface 4 — Empty-state message.** Operator finds (or waits for) a trade with no active advisory triggers; verifies the trade-detail page + expanded row both show "No advisories." muted message.
- **Surface 5 — Existing dashboard list view intact.** No regressions on the dashboard advisory column. Same content, same rendering.
- **Surface 6 — pytest + ruff.** From worktree: `python -m pytest -m "not slow" -q` GREEN; `ruff check swing/ --statistics` shows 18 (no new violations).

**Expected test count delta:** +6-10 (Task A: 3 briefing tests; Task B: 4-7 VM + route + template tests).
**Expected ruff baseline:** 18 (no change).

---

## §6 Return report shape

After operator-gate PASS, draft a return report with:

1. Final HEAD on branch
2. Commit count breakdown (task-impl / Codex-fix / operator-gate-fix)
3. Codex round chain
4. Test count delta
5. Ruff baseline delta
6. Operator-gate surface results
7. Per-task-family deviations from the brief
8. Codex Major findings ACCEPTED with rationale
9. Watch items surfaced but not acted on
10. Worktree teardown status

---

## §7 First-step paste-ready prompt for the implementer

```
You are taking over as implementer for the swing-trading 3e8-bundle-1-advisory-parity dispatch.

WORKING DIRECTORY: c:\Users\rwsmy\swing-trading\.worktrees\3e8-bundle-1-advisory-parity
BRANCH: 3e8-bundle-1-advisory-parity
BASELINE_SHA: a0d8d21

Step 1 — Read the dispatch brief end-to-end:
  docs/3e8-bundle-1-advisory-parity-brief.md

It locks 8 design decisions (§0.3) that you do NOT re-litigate. Two task families:
  - Task A (§4.E): pipeline briefing advisory wire-through
  - Task B (§4.F): trade-detail + open-positions expanded-row advisory rendering

Step 2 — Read CLAUDE.md + docs/orchestrator-context.md (binding conventions).

Step 3 — Verify worktree state:
  git rev-parse HEAD                  # expect a0d8d21
  git status                          # expect clean
  python -m pytest -m "not slow" -q   # expect baseline GREEN (2183 passed)

Step 4 — Execute the brief via superpowers:subagent-driven-development. TDD discipline per task family.

Step 5 — After ALL task families land + GREEN, run the adversarial review YOURSELF (per §4.1):
  - Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active
  - Invoke copowers:adversarial-critic with PHASE=3e8-bundle-1-advisory-parity,
    SPEC_PATH=docs/3e8-bundle-1-advisory-parity-brief.md,
    PLAN_PATH=docs/3e8-bundle-1-advisory-parity-brief.md,
    BASELINE_SHA=a0d8d21
  - Iterate rounds + land Codex-fix commits until NO_NEW_CRITICAL_MAJOR.

Step 6 — Draft return report per §6 + signal orchestrator. Operator drives §5 witnessed verification gate; orchestrator handles integration merge.

DO NOT:
  - Push to origin from inside the worktree
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer to commits
  - Skip the marker-file removal before invoking copowers
  - Add new advisory rules (Bundle 2 work, separate dispatch)
  - Add maturity-stage gating (Bundle 3 work, separate dispatch)
```

---

## §8 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-10 (post-§4.G transcription).
- **Brief commit:** TBD.
- **Brief HEAD context:** `a0d8d21` on main.
- **Worktree path (binding):** `.worktrees/3e8-bundle-1-advisory-parity/`.
- **Baseline test count:** 2183 fast (1 skipped).
- **Baseline ruff count:** 18 (E501 only).
- **Expected post-dispatch test count:** ~2189-2193 (+6-10).
- **Expected post-dispatch ruff count:** 18 (no change).
