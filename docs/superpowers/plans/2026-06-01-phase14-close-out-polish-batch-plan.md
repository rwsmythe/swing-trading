# Phase 14 Close-Out Polish Batch — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Use `python -m swing.cli` (NOT bare `swing`) in the worktree.

**Goal:** Ship the Phase-14 close-out polish batch — one executing-plans bundle, 5 serial slices on already-shipped surfaces (A-7 Schwab badge UNKNOWN render, P14.N1 dashboard-table thumbnails on BOTH tables, A-1 market_weather ≥200-bar fetch window, A-2/A-4/A-6 cosmetics, group-(a) minors) — read-mostly, NO schema change (v23 held), L2-LOCK green.

**Architecture:** Pure web view-model / template / route / CSS edits plus a pipeline-constant widening and test hardening. The one design fix (A-7) makes the existing-but-dead `UNKNOWN` badge branch reachable, gated on a pure config read (`_is_ladder_active`). P14.N1 reuses two existing thumbnail renderers via a shared lazy-render cap; no new renderer. No swing-domain writes; no `chart_renders` writes on the dashboard thumbnail path.

**Tech Stack:** FastAPI + HTMX + Jinja2, matplotlib SVG thumbnails, SQLite (read-only this batch), pytest (+xdist), ruff.

**Source spec:** `docs/superpowers/specs/2026-06-01-phase14-close-out-polish-batch-design.md` (AUTHORITATIVE except the OQ-5 hyp-rec deferral, REVERSED per the writing-plans brief §1.1 — hyp-rec thumbnails ARE in scope via the EXISTING `render_watchlist_thumbnail_svg`).
**Dispatch brief:** `docs/phase14-close-out-polish-batch-writing-plans-dispatch-brief.md`.

---

## §A Goals / Non-Goals

### Goals
1. **A-7** — render a visible `UNKNOWN` (`Schwab?`, warn) badge when the Schwab checker is EXPECTED (`_is_ladder_active(cfg)` True) and no usable liveness sidecar exists, instead of hiding the badge; refine the misleading reason text; keep hiding when Schwab is not expected (sandbox / ladder-disabled / no cfg).
2. **P14.N1** — lazy candlestick thumbnails on BOTH dashboard tables: open-positions rows (trade-window thumbnail, reusing the journal route) and hyp-rec rows (ticker-window thumbnail via the watchlist renderer, render-direct). Column counts stay aligned (compact == header == expanded) on both tables.
3. **A-1** — widen the benchmark/market_weather OHLCV fetch window to ≥200 trading bars (~300 calendar days) via a named shared constant, at both live sites + the JIT path.
4. **A-2 / A-4 / A-6** — reposition the VCP contraction labels off the price-tick column; rename `_bulz_*` → general risk/reward names (behavior-neutral); make the process-grade-trend chart visible in dark mode (and actually drawn in both themes).
5. **group-(a)** — C-1/C-2/C-3/C-5/C-19 (and a DOCUMENTED DEFERRAL of C-6; see §E and Slice E).

### Non-Goals (binding — L1)
- NO B-7, NO Phase-14 close-out review, NO Phase 15+ items, NO A-5 (styled 404 — CLOSED).
- NO schema change (v23 held). NO new `schwabdev.Client.*` call site. NO new chart renderer. NO swing-domain or `chart_renders` write on the dashboard thumbnail path.
- NO schwabdev v2.5.1→3.0.5 upgrade (Phase 15). NO granular A-7 client-failure taxonomy (Phase 15).
- NO hyp-rec candidate-chart re-implementation (we REUSE `render_watchlist_thumbnail_svg`).

---

## §B File map (per slice)

**Re-grep verified at writing-plans STEP 0 against worktree HEAD `565f0a9`** (discipline #2). Lines below are the verified current anchors; re-grep again at executing-plans STEP 0.

### Slice A — A-7 badge
- Modify: `swing/web/view_models/schwab_checker_badge.py:30-49` (`build_schwab_checker_badge` — gate on `_is_ladder_active`, route through the existing `evaluate_liveness_state` UNKNOWN branch, refine reason text).
- Reuse (no change): `swing/integrations/schwab/marketdata_ladder.py:221` (`_is_ladder_active`), `swing/integrations/schwab/checker_resilience.py:154/180/218` (`checker_liveness_sidecar_path` / `read_liveness_sidecar` / `evaluate_liveness_state`), `swing/web/templates/base.html.j2:81-84` (badge render — unchanged).
- Test: `tests/web/test_schwab_checker_badge.py` (VM-level) + `tests/web/test_schwab_checker_badge_topbar.py` (NEW — TestClient route/topbar render).

### Slice B — P14.N1 dashboard thumbnails (BOTH tables)
- Create: `swing/web/thumbnail_render.py` (NEW — the shared render cap: `_THUMBNAIL_RENDER_SEMAPHORE`, `_THUMBNAIL_RENDER_TIMEOUT_S`, `_THUMBNAIL_CACHE_CONTROL`, extracted from `routes/journal.py` so both the journal route and the new hyp-rec route share ONE process-wide matplotlib render cap).
- Modify: `swing/web/routes/journal.py:34-39` (import the three constants from the new module instead of defining them; behavior-identical).
- Modify (open-positions, reuse journal route): `swing/web/templates/partials/open_positions.html.j2:8` (add `<th>Chart</th>` → 11 `<th>`), `swing/web/templates/partials/open_positions_row.html.j2` (add leading lazy `<td>` → 11 cells), `swing/web/templates/partials/open_positions_expanded.html.j2:17-19,27` (colspan 10→11 + the MUST-match comment).
- Create (hyp-rec, render-direct): route handler `GET /dashboard/hyprec/{ticker}/thumbnail` in `swing/web/routes/dashboard.py`; partial `swing/web/templates/partials/hyprec_thumbnail.html.j2` (ticker-keyed; svg / busy-self-retry / unavailable; fragment root `<svg>`/`<span>`).
- Modify (hyp-rec table): `swing/web/templates/partials/hypothesis_recommendations.html.j2:36-44` (add `<th>Chart</th>` after the expand `<th>` → 10 `<th>`), `swing/web/templates/partials/hypothesis_recommendations_row.html.j2:15-20` (add lazy `<td>` after the chevron `<td>` → 10 cells; the `<tr>` stays trigger-free), `swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2:10` (colspan 9→10).
- Reuse (no change): `swing/web/trade_charts.py:88` (`render_trade_window_thumbnail_svg`), `swing/web/charts.py:514` (`render_watchlist_thumbnail_svg`), `swing/web/routes/journal.py:80` (the journal thumbnail route — open-positions reuses it), `swing/web/templates/partials/journal_thumbnail.html.j2` (open-positions reuses it).
- Test: `tests/web/test_open_positions_thumbnail.py` (NEW), `tests/web/test_hyprec_thumbnail.py` (NEW), plus column-count regressions in each (see §H).

### Slice C — A-1 fetch-window widening
- Modify: `swing/web/ohlcv_cache.py` (add module constant `MIN_CALENDAR_DAYS_FOR_MA200 = 300` near the `get_or_fetch` default at `:131`).
- Modify: `swing/pipeline/runner.py:2763` (`_bars_or_none`: `window_days=200` → `MIN_CALENDAR_DAYS_FOR_MA200`) and `:2694` (the `_step_charts` per-ticker OHLCV-consume — SAME constant; re-grep finding, see §E.4).
- Modify: `swing/web/routes/dashboard.py:94` (pass `window_days=MIN_CALENDAR_DAYS_FOR_MA200` explicitly — today inherits the 180 default).
- Modify: `swing/web/chart_jit.py:117` (`window_days=200` → `MIN_CALENDAR_DAYS_FOR_MA200`; OQ-6).
- Test: `tests/web/test_market_weather_fetch_window.py` (NEW) + an assertion in `tests/pipeline/` for `_bars_or_none`.

### Slice D — cosmetics
- A-2 Modify: `swing/web/charts.py:836-841` (`_annotate_vcp` label position).
- A-4 Modify: `swing/web/charts.py:632,725` (rename `_bulz_target_price`→`_rr_target_price`, `_draw_bulz_zones`→`_draw_risk_reward_zones`) + comments/WARN at `:235,628,633,661,704,750,765` + calls at `:708,756`; `swing/web/view_models/open_positions_row.py:257` (comment); `swing/web/templates/partials/open_positions_expanded.html.j2:39` (comment); `tests/web/test_charts.py:30` (import) + test function names. **Do NOT rename `ticker="BULZ"` fixtures (BULZ is a real ticker symbol; see §E.5).**
- A-6 Modify: `swing/web/static/app.css` (add `.process-grade-rolling-line { stroke: var(--accent); }` + `.process-grade-marker { fill: var(--accent); }`).
- Test: `tests/web/test_charts.py` (A-2 format-string + A-4 rename), `tests/web/test_app_css_process_grade.py` (NEW, A-6 CSS-presence).

### Slice E — group-(a)
- C-1 Modify: `swing/web/view_models/trades.py:2153` (`position_capital_utilization_is_provisional: bool = True` → `= False`).
- C-2 Modify: `swing/web/templates/partials/daily_management_tile.html.j2:132` (tooltip wording).
- C-3 Modify: `swing/cli.py` (the `diagnose backfill-trades-sector-industry` command — wrap artifact-write `OSError` → `click.ClickException`).
- C-5 Modify: `tests/cli/test_diagnose_backfill_trades_sector_industry.py:546` (strengthen the BEGIN-IMMEDIATE test to assert ORDER, not just presence).
- C-19 Modify: `tests/research/test_pattern_cohort_evaluator_reader.py:37` (add `@pytest.mark.xdist_group(...)`).
- **C-6 DEFERRED — NOT implemented this batch** (TOCTOU + crash-safety reopen; see §E.6 and Slice E Task E.0).

---

## §C Surface integration

- **A-7:** The badge renders in the topbar of every page via `base.html.j2:81` `{% if vm.schwab_checker_badge %}`. `build_schwab_checker_badge(cfg)` is the SINGLE construction point, called by every base-layout VM builder (dashboard, journal, pipeline, watchlist, error, metrics, schwab, trades, config, reconcile). Changing the one function changes all surfaces — NO per-VM field change (the `schwab_checker_badge` field already exists on all base-layout VMs from SB5.5).
- **P14.N1 open-positions:** the lazy `<td>` `hx-get`s the existing journal route `/journal/trades/{trade_id}/thumbnail` (open trades have `trade_id`s; the helper renders open trades with `exit_date=None` → trailing window). No new route. Delivered via `hx-trigger="revealed"` + `innerHTML` swap into the cell.
- **P14.N1 hyp-rec:** hyp-rec rows are ticker-keyed candidates with NO underlying `Trade`. A NEW render-direct route `/dashboard/hyprec/{ticker}/thumbnail` fetches bars via `app.state.ohlcv_cache.get_or_fetch(...)` and calls `render_watchlist_thumbnail_svg(ticker=, bars=, ma_lines=)` under the SHARED render cap. **Render-direct — NO `chart_renders` write** (it does NOT route through `chart_jit.get_or_render_surface`, which writes the cache; L5). Delivered lazily like the journal cell.
- **A-1:** `MIN_CALENDAR_DAYS_FOR_MA200` feeds `OhlcvCache.get_or_fetch(window_days=...)` at every benchmark/chart fetch site so a 200-trading-bar SMA200 has enough bars. Widening is monotonic-safe (more bars only; consumers slice).
- **A-2/A-4/A-6:** in-place edits to existing chart annotation, helper names, and CSS; no new surface.

---

## §D Out-of-scope (escalate, do NOT silently expand)
- Any persisted row/column (would need v24 — STOP + escalate; L2).
- Any new `schwabdev.Client.*` call site or new client-construction path (L3 — STOP).
- A new hyp-rec candidate renderer (L4 — reuse `render_watchlist_thumbnail_svg`).
- A per-series A-6 color palette (V2). An exchange-calendar-aware exact-bar A-1 helper (V2). A-7 granular failure taxonomy (Phase 15).
- C-6 write-lock narrowing (deferred — §E.6).

---

## §E LOCK reverification + re-grep findings

### §E.1 OQ dispositions honored (operator-LOCKed 2026-06-01)
| OQ | Disposition in this plan |
|---|---|
| OQ-1 (A-7 design) | Slice A: UNKNOWN badge gated on `_is_ladder_active(cfg)`; reuse `evaluate_liveness_state` + `_BADGE_MAP`; keep `cfg is None → None`; reason-text refinement. |
| OQ-2 (A-7 wiring) | No checker-non-start bug under valid tokens; A-7 stays ONE slice; no cycle-split. |
| OQ-3 (decomposition) | ONE bundle, 5 slices A–E, serial, A-7 first. |
| OQ-4 (group-(a)) | C-1/C-2/C-3/C-5/C-19 IN; **C-6 DEFERRED** (TOCTOU; §E.6). |
| OQ-5 (P14.N1 scope) | BOTH tables; open-positions via `render_trade_window_thumbnail_svg` (reuse journal route), hyp-rec via `render_watchlist_thumbnail_svg` (render-direct route); both LAZY; NO new renderer. |
| OQ-6 (A-1 JIT) | JIT constant widened too (Slice C). |
| OQ-7 (A-6) | CSS rule via `var(--accent)` (not inline). |
| OQ-8 (Codex) | SINGLE chain to convergence (§J). |

### §E.2 Inherited LOCKs (L1–L7)
- **L1** scope = 5 slices only; no B-7 / close-out review / Phase 15+; A-5 CLOSED. ✓
- **L2** NO schema change; `EXPECTED_SCHEMA_VERSION = 23` at `swing/data/db.py:51` unchanged; no migration `0024`. ✓ (§K)
- **L3** A-7 adds ZERO new `schwabdev.Client.*` sites; `_is_ladder_active` is a pure config read (`marketdata_ladder.py:228-236` — `getattr` env + enabled, NO API/client). `tests/integration/test_l2_lock_source_grep.py` (baseline `bf7e071`) stays green. ✓ (§E.7)
- **L4** REUSE: A-7 reuses `evaluate_liveness_state`+`_BADGE_MAP`; P14.N1 reuses BOTH existing renderers + the SB4 lazy pattern; A-6 reuses `var(--accent)`. The ONE new module (`thumbnail_render.py`) is an EXTRACTION (DRY) of existing journal constants, not a re-implementation. ✓
- **L5** read-mostly: zero swing-domain writes. The open-positions path reuses the journal route (render-direct, no `chart_renders` write — confirmed `routes/journal.py:127` calls `render_trade_window_thumbnail_svg` directly). The hyp-rec route is render-direct (does NOT call `chart_jit.get_or_render_surface`, which is the ONLY `chart_renders`-writing path). ✓
- **L6** production-path tests: A-7 topbar test enters the lifespan and renders the real `base.html.j2`; P14.N1 tests drive the real routes + renderers; A-1 asserts ≥200 bars reach `render_market_weather_svg` via the real `get_or_fetch`. ✓ (§H)
- **L7** ASCII + redaction: the A-7 reason text is ASCII; no `setLogRecordFactory` change; C-2/C-3 text ASCII. ✓

### §E.3 Re-grep finding — A-7 anchors all matched
`build_schwab_checker_badge` :30, early-out `if data is None: return None` :42-43, `_BADGE_MAP["UNKNOWN"]=("Schwab?","warn")` :26, `_is_ladder_active` :221, `evaluate_liveness_state(None,...)→("UNKNOWN","web server not running, or pre-N7 build")` :228-229, `read_liveness_sidecar` :180, `checker_liveness_sidecar_path` :154. Badge markup `base.html.j2:82` class `schwab-health-badge schwab-health-badge--{css_class}`, label at `:84`. **All matched — no drift.**

### §E.4 Re-grep finding — A-1 has a THIRD `window_days=200` site
Beyond the two spec/brief sites (`_bars_or_none` `runner.py:2763`, dashboard refresh `dashboard.py:94`) and the JIT (`chart_jit.py:117`, OQ-6), STEP-0 re-grep found **`runner.py:2694`** — the `_step_charts` per-ticker OHLCV-consume feeding the classifier trend-template AND the per-ticker chart renders (which use `ma_windows` up to 200, e.g. `render_ticker_detail` `charts.py:584` `(10,20,50,150,200)`). This is ALSO an MA200-bearing surface with the identical too-few-bars defect. **This plan folds `:2694` into the same `MIN_CALENDAR_DAYS_FOR_MA200` constant** under the same monotonic-safe rationale as OQ-6's JIT widening (more bars only; the classifier 52-week / MA200 logic and per-ticker MA200 charts need ≥200 trading bars too). This is a re-grep-discovered site beyond the brief's enumerated list — flagged here and surfaced to Codex/operator; if the operator wants `:2694` excluded, drop that one edit (the rest stand).

### §E.5 Re-grep finding — A-4 `BULZ` is BOTH a feature nickname AND a real ticker
`swing/web/charts.py` + `tests/web/test_charts.py` are the only files with `bulz`/`BULZ` tokens. Two DISTINCT usages:
- **Feature name** (RENAME these): functions `_bulz_target_price`/`_draw_bulz_zones`, comments "BULZ risk/reward", WARN text "skipping BULZ risk zone", the test import + test function names `test_bulz_target_price_*`.
- **Ticker symbol** (DO NOT rename): `ticker="BULZ"` / `_make_trade(ticker="BULZ")` test fixtures — `BULZ` is a real ETF symbol used as fixture data. Renaming it is unnecessary churn and is NOT what A-4 asks. Leave all `ticker="BULZ"` strings as-is.

### §E.6 Re-grep finding — C-6 DEFERRED (genuine TOCTOU + crash-safety reopen)
`swing/diagnostics/backfill_trades_sector_industry.py:115-128`: the apply-path holds `BEGIN IMMEDIATE`, then under the lock (a) re-SELECTs rows, (b) `_emit_restore_sql(restore_path, update_rows)` (filesystem write), (c) `_apply_updates`, (d) COMMIT. C-6 wants the FS write OUTSIDE the lock. But the in-line comments (`:105-114` + `:123-124`) document TWO deliberate invariants:
1. **TOCTOU consistency** — re-SELECT + emit + UPDATE must see the same row set (a concurrent writer between SELECT and UPDATE could make the restore artifact clobber valid data).
2. **Crash-safety ordering** — the restore SQL must be ON DISK *before* the UPDATE commits (defense-in-depth against a crash mid-UPDATE leaving no restore artifact).

Narrowing the lock to exclude the FS write forces one of: (a) move the FS write AFTER COMMIT → breaks crash-safety (a crash between COMMIT and the file-write leaves an applied UPDATE with no restore artifact); or (b) move the SELECT+emit BEFORE `BEGIN IMMEDIATE` → reopens the exact TOCTOU the lock closed. The restore content is derived from an in-memory `update_rows` list (so the file *content* is consistent regardless of write timing), but the crash-safety ordering genuinely requires the write to complete before COMMIT, i.e. inside the lock window. For a single-operator local-SQLite V1 the lock-hold-during-a-few-ms-file-write is not a real contention problem. **Per OQ-4 + brief §6, C-6 reopens a TOCTOU and is DEFERRED to its own follow-up.** Slice E Task E.0 records this; the other five group-(a) items proceed.

### §E.7 L2-LOCK analysis (A-7)
A-7 modifies `build_schwab_checker_badge`, calling `read_liveness_sidecar` (file read) + `evaluate_liveness_state` (pure fn) + `_BADGE_MAP` (dict) + the NEW `_is_ladder_active(cfg)` (pure config read). ZERO new `schwabdev.Client.*` call sites; no client-construction path; no `setLogRecordFactory` change. `tests/integration/test_l2_lock_source_grep.py` (baseline `L2_LOCK_BASELINE_SHA="bf7e071"`, pattern `"schwabdev.Client."`) diffs call-site counts at HEAD vs baseline → unchanged → green (S3).

---

## §F Discipline hooks (cumulative gotchas applied)
- **HTMX `<tr>`-at-fragment-root synthetic-table-wrap:** the hyp-rec thumbnail partial root is `<svg>`/`<span>` (never bare `<tr>`); the journal_thumbnail partial (reused for open-positions) already complies. ✓
- **`hx-headers '{"HX-Request":"true"}'`:** every new lazy `<td>` carries it (OriginGuard strict-mode). ✓
- **hyp-rec `<tr>` must NOT carry hx-* (discriminator vs watchlist):** the new lazy thumbnail attrs go on the `<td>`, NOT the `<tr>`; `tests/web/test_hyp_recs_table_regression.py::test_tr_has_no_hx_get_attribute` extracts only the `<tr>` OPEN TAG, so a `<td>` hx-get is safe — re-run that test as a guard (§H). ✓
- **base.html.j2 shared-VM-field hazard:** A-7 adds NO new `vm.*` field. ✓
- **Matplotlib mathtext (`$`/`^`/`_`):** A-2 keeps `pct` (not `%`), no metachars; thumbnails carry no title. ✓
- **cp1252 / ASCII (#16/#32):** A-7 reason text + C-2/C-3 text ASCII-only (use `-` not em-dash in new strings). ✓
- **`USERPROFILE`+`HOME` monkeypatch:** the A-7 UNSEEDED fixture isolates HOME so no sidecar leaks to the real `~/swing-data` (§L). ✓
- **#15 production-path tests:** A-7 topbar render, P14.N1 real routes, A-1 real `get_or_fetch` (§H). ✓
- **TestClient lifespan:** topbar + thumbnail route tests use `with TestClient(app) as client:` (enter lifespan; `app.state.ohlcv_cache`/`price_fetch_executor`). ✓
- **No Co-Authored-By; final `-m` paragraph plain prose; verify `%(trailers)` `[]`** before finishing. ✓

---

## §G The 5 slices (bite-sized TDD tasks)

> Convention: each task is failing-test → see-fail → minimal-impl → see-pass → commit. Run the fast suite scoped to the touched test module per task; run the full `python -m pytest -m "not slow" -q` once per slice before the slice's final commit. Commit stem: `feat(web): ...` / `fix(web): ...` / `refactor(web): ...` / `test(...): ...` as appropriate — NO Co-Authored-By footer.

---

### Slice A — A-7 Schwab badge UNKNOWN render

#### Task A.1 — VM renders UNKNOWN when expected + no sidecar

**Files:**
- Modify: `swing/web/view_models/schwab_checker_badge.py:30-49`
- Test: `tests/web/test_schwab_checker_badge.py`

- [ ] **Step 1: Write the failing tests**

Add to `tests/web/test_schwab_checker_badge.py` (use a tiny cfg stub or the existing test cfg factory; the sidecar path must point at an empty tmp dir so `read_liveness_sidecar` returns None):

```python
def test_badge_unknown_when_ladder_active_and_no_sidecar(monkeypatch, tmp_path):
    # Isolate HOME so checker_liveness_sidecar_path resolves under tmp (no real sidecar).
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    cfg = _make_cfg(environment="production", marketdata_ladder_enabled=True)
    vm = build_schwab_checker_badge(cfg)
    assert vm is not None
    assert vm.state == "UNKNOWN"
    assert vm.label == "Schwab?"
    assert vm.css_class == "warn"
    # reason-text refinement: not the misleading default
    assert "web server not running" not in vm.title
    assert "check credentials/tokens" in vm.title
    assert vm.title.isascii()

def test_badge_hidden_when_ladder_disabled(monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path)); monkeypatch.setenv("HOME", str(tmp_path))
    cfg = _make_cfg(environment="production", marketdata_ladder_enabled=False)
    assert build_schwab_checker_badge(cfg) is None

def test_badge_hidden_in_sandbox(monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path)); monkeypatch.setenv("HOME", str(tmp_path))
    cfg = _make_cfg(environment="sandbox", marketdata_ladder_enabled=True)
    assert build_schwab_checker_badge(cfg) is None

def test_badge_hidden_when_cfg_none():
    assert build_schwab_checker_badge(None) is None
```

> If `_make_cfg` does not already exist in the test module, write a minimal helper that returns an object with `.integrations.schwab.environment` and `.integrations.schwab.marketdata_ladder_enabled` (a `types.SimpleNamespace` tree is sufficient — `_is_ladder_active` uses `getattr`).

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/web/test_schwab_checker_badge.py -v`
Expected: the two new UNKNOWN/reason assertions FAIL (current code returns `None` when `data is None`).

- [ ] **Step 3: Minimal implementation**

Replace `build_schwab_checker_badge` body in `swing/web/view_models/schwab_checker_badge.py`:

```python
from swing.integrations.schwab.checker_resilience import (
    checker_liveness_sidecar_path,
    evaluate_liveness_state,
    read_liveness_sidecar,
)
from swing.integrations.schwab.marketdata_ladder import _is_ladder_active


def build_schwab_checker_badge(cfg) -> SchwabCheckerBadgeVM | None:
    """Return the badge VM, or None when the badge must be hidden.

    Hidden when cfg is None (cfg-less callers) OR when the Schwab checker is
    not EXPECTED to be running -- i.e. NOT (production AND ladder enabled).
    When the checker IS expected, render the state from the SAME state machine
    as `swing schwab status`: a missing/unreadable sidecar maps to UNKNOWN
    (Schwab?, warn) rather than vanishing, so a silent checker failure is
    visible in the topbar. Pure config read + file read; no Schwab API call.
    ASCII-only.
    """
    import time
    if cfg is None:
        return None
    if not _is_ladder_active(cfg):
        return None
    env = cfg.integrations.schwab.environment
    data = read_liveness_sidecar(checker_liveness_sidecar_path(env))
    state, reason = evaluate_liveness_state(data, now_ts=time.time())
    if data is None:
        # The state machine's hardcoded UNKNOWN reason ("web server not
        # running, or pre-N7 build") is misleading here: the checker is
        # EXPECTED (production + ladder) but no sidecar exists, which means
        # the client could not be constructed (degraded/missing creds).
        reason = (
            "Schwab client unavailable - no checker running; "
            "check credentials/tokens"
        )
    label, css = _BADGE_MAP[state]
    return SchwabCheckerBadgeVM(
        state=state, label=label,
        title=f"Schwab checker: {state.lower()} ({reason})", css_class=css,
    )
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/web/test_schwab_checker_badge.py -v`
Expected: PASS (all, including any pre-existing seeded-sidecar tests — those pass a non-None `data` so the reason refinement is skipped and the existing ALIVE/DEGRADED/STARTING assertions hold).

- [ ] **Step 5: Commit**

```bash
git add swing/web/view_models/schwab_checker_badge.py tests/web/test_schwab_checker_badge.py
git commit -m "fix(web): render UNKNOWN Schwab badge when checker expected (A-7)"
```

#### Task A.2 — topbar render (production-path, UNSEEDED)

**Files:**
- Create: `tests/web/test_schwab_checker_badge_topbar.py`

- [ ] **Step 1: Write the failing test**

```python
from fastapi.testclient import TestClient

def test_topbar_shows_unknown_badge_unseeded(monkeypatch, tmp_path):
    # UNSEEDED precondition: production + ladder enabled, isolated HOME with NO
    # pre-existing sidecar, AND no constructible Schwab client (no creds), so
    # the app installs NO checker and writes NO sidecar at startup.
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    app = _build_app_production_ladder_no_creds(tmp_path)  # see §L
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        body = resp.text
        assert "schwab-health-badge--warn" in body
        assert "Schwab?" in body
    # No sidecar was created by the lifespan before the first rendered request.
    from swing.integrations.schwab.checker_resilience import checker_liveness_sidecar_path
    assert not checker_liveness_sidecar_path("production").exists()

def test_topbar_hides_badge_in_sandbox(monkeypatch, tmp_path):
    monkeypatch.setenv("USERPROFILE", str(tmp_path)); monkeypatch.setenv("HOME", str(tmp_path))
    app = _build_app_sandbox(tmp_path)  # see §L
    with TestClient(app) as client:
        resp = client.get("/")
        assert resp.status_code == 200
        assert "schwab-health-badge" not in resp.text
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/web/test_schwab_checker_badge_topbar.py -v`
Expected: `test_topbar_shows_unknown_badge_unseeded` FAILs against the pre-Task-A.1 code (no badge in body). After Task A.1 the VM logic is fixed, so this test guards the END-TO-END topbar render (the `{% if vm.schwab_checker_badge %}` guard) — if A.1 is already committed, write this test FIRST (it should pass once the app-builder fixture is correct) and treat a failure as a fixture bug.

- [ ] **Step 3: Implementation** — none (Task A.1 already supplies the VM logic); this task is the production-path guard + the §L fixture. If the fixture cannot construct an app in production mode without real creds, see §L for the `_construct_web_schwab_client`-returns-None monkeypatch approach.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/web/test_schwab_checker_badge_topbar.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add tests/web/test_schwab_checker_badge_topbar.py
git commit -m "test(web): topbar renders UNKNOWN Schwab badge in unseeded default state (A-7)"
```

#### Task A.3 — L2-LOCK + full-suite check for Slice A

- [ ] **Step 1:** Run `python -m pytest tests/integration/test_l2_lock_source_grep.py -v` → PASS (zero new `schwabdev.Client.` sites).
- [ ] **Step 2:** Run `python -m pytest -m "not slow" -q` → all green. Run `ruff check swing/` → clean.
- [ ] **Step 3:** (no commit if nothing changed) — proceed to Slice B.

---

### Slice B — P14.N1 dashboard thumbnails (BOTH tables)

#### Task B.1 — extract the shared render cap (DRY, behavior-neutral)

**Files:**
- Create: `swing/web/thumbnail_render.py`
- Modify: `swing/web/routes/journal.py:34-39`
- Test: `tests/web/test_thumbnail_render_shared.py` (NEW)

- [ ] **Step 1: Write the failing test**

```python
def test_shared_cap_constants_present_and_reused():
    import swing.web.thumbnail_render as tr
    import threading
    assert isinstance(tr._THUMBNAIL_RENDER_SEMAPHORE, type(threading.BoundedSemaphore(1)))
    assert tr._THUMBNAIL_RENDER_TIMEOUT_S == 2.0
    assert tr._THUMBNAIL_CACHE_CONTROL == "private, max-age=60"
    # journal route imports the SAME instance (one process-wide cap)
    import swing.web.routes.journal as j
    assert j._THUMBNAIL_RENDER_SEMAPHORE is tr._THUMBNAIL_RENDER_SEMAPHORE
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/web/test_thumbnail_render_shared.py -v`
Expected: FAIL (`swing.web.thumbnail_render` does not exist).

- [ ] **Step 3: Implementation**

Create `swing/web/thumbnail_render.py`:

```python
"""Shared lazy-thumbnail render cap (Phase 14 close-out P14.N1).

Extracted from routes/journal.py so the journal thumbnail route AND the
dashboard open-positions / hyp-rec thumbnail paths share ONE process-wide
matplotlib render cap. Behavior-identical to the SB4 journal constants.
"""
from __future__ import annotations

import threading

# Caps CONCURRENT thumbnail renders across ALL thumbnail routes; a burst that
# exhausts it returns a transient 200+busy fragment (self-retries) rather than
# piling workers behind the matplotlib render lock.
_THUMBNAIL_RENDER_SEMAPHORE = threading.BoundedSemaphore(2)
# Short acquire timeout (module constant so tests can shrink it).
_THUMBNAIL_RENDER_TIMEOUT_S = 2.0
# Short cache lifetime for cacheable (svg / unavailable / not-found) contracts.
# Busy is transient backpressure -> Cache-Control: no-store instead.
_THUMBNAIL_CACHE_CONTROL = "private, max-age=60"
```

Modify `swing/web/routes/journal.py:28-39` — replace the three local definitions with an import (keep the explanatory comment as a one-liner pointing at the shared module):

```python
# Phase 14 close-out (P14.N1): the render cap moved to swing/web/thumbnail_render
# so the dashboard thumbnail routes share ONE process-wide matplotlib cap.
from swing.web.thumbnail_render import (
    _THUMBNAIL_CACHE_CONTROL,
    _THUMBNAIL_RENDER_SEMAPHORE,
    _THUMBNAIL_RENDER_TIMEOUT_S,
)
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/web/test_thumbnail_render_shared.py swing -q -k "journal_thumbnail or thumbnail"` then the journal route tests: `python -m pytest tests/web/ -q -k journal`
Expected: PASS (journal thumbnail behavior unchanged).

- [ ] **Step 5: Commit**

```bash
git add swing/web/thumbnail_render.py swing/web/routes/journal.py tests/web/test_thumbnail_render_shared.py
git commit -m "refactor(web): extract shared thumbnail render cap for dashboard reuse (P14.N1)"
```

#### Task B.2 — open-positions table column shape (+ regression)

**Files:**
- Modify: `swing/web/templates/partials/open_positions.html.j2:8`
- Modify: `swing/web/templates/partials/open_positions_row.html.j2`
- Modify: `swing/web/templates/partials/open_positions_expanded.html.j2:17-19,27`
- Test: `tests/web/test_open_positions_thumbnail.py` (NEW)

- [ ] **Step 1: Write the failing test (column-count regression)**

```python
def test_open_positions_column_counts_align(seeded_open_trade_db, monkeypatch):
    # Render the dashboard with >=1 open trade; assert header <th> count ==
    # compact-row <td> count == expanded colspan.
    body = _render_dashboard(seeded_open_trade_db, monkeypatch)  # see §L helper
    header_th = _count_header_th(body, section="open-positions")   # parse the open-positions <thead>
    compact_td = _count_first_row_td(body, row_id_prefix="open-position-")
    assert header_th == 11
    assert compact_td == 11
    # expanded colspan
    expanded = _get_expanded_fragment("open-position", seeded_open_trade_db, monkeypatch)
    assert 'colspan="11"' in expanded

def test_open_positions_row_has_lazy_thumbnail_cell(seeded_open_trade_db, monkeypatch):
    body = _render_dashboard(seeded_open_trade_db, monkeypatch)
    assert 'hx-get="/journal/trades/' in body and "/thumbnail" in body
    assert 'hx-trigger="revealed"' in body
    assert 'hx-headers=\'{"HX-Request": "true"}\'' in body or "HX-Request" in body
```

> Use the existing dashboard-render test helpers / `seeded` fixtures already present in `tests/web/` for open positions (re-grep `tests/web/test_open_positions*.py` at executing-plans for the established fixture). The count helpers can be simple substring/regex parsers scoped to the `open-positions` `<section>`.

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/web/test_open_positions_thumbnail.py -v`
Expected: FAIL (header has 10 `<th>`, row has 10 `<td>`, colspan is 10, no thumbnail cell).

- [ ] **Step 3: Implementation**

`open_positions.html.j2:7-9` — add a leading `<th>Chart</th>`:

```html
      <thead><tr>
        <th>Chart</th><th>Ticker</th><th>Entry date</th><th>Entry price</th><th>Shares</th><th>Current stop</th><th>Last</th><th>Sector</th><th>Industry</th><th>Advisory</th><th>Actions</th>
      </tr></thead>
```

`open_positions_row.html.j2` — add the leading lazy thumbnail `<td>` as the FIRST cell inside the `<tr>` (mirror `journal_row.html.j2:14-18`; the cell-level `hx-trigger="revealed"` loads on scroll; clicking it still bubbles to the row's expand binding, which is the existing behavior for every cell):

```html
<tr id="open-position-{{ row.trade.id }}"
    hx-get="/trades/open/{{ row.trade.id }}/expand"
    hx-target="closest tr"
    hx-swap="outerHTML"
    hx-headers='{"HX-Request": "true"}'>
  <td class="open-position-thumb" data-trade-id="{{ row.trade.id }}"
      hx-get="/journal/trades/{{ row.trade.id }}/thumbnail"
      hx-trigger="revealed" hx-swap="innerHTML"
      hx-headers='{"HX-Request": "true"}'></td>
  <td>{{ row.trade.ticker }} {{ state_badge(row.trade.state) }}
  ...
```

`open_positions_expanded.html.j2:17-19,27` — bump the comment cell-count (10→11, add "Chart" to the list) and `colspan="10"` → `colspan="11"`:

```html
    Colspan must match the compact open_positions_row.html.j2 cell count
    (11 cells: Chart, Ticker, Entry date, Entry price, Shares, Current stop,
    Last, Sector, Industry, Advisory, Actions). A mismatch breaks the layout.
...
  <td colspan="11">
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/web/test_open_positions_thumbnail.py tests/web/ -q -k "open_position"`
Expected: PASS (including any pre-existing open-positions tests — update those that hard-assert a 10-cell/colspan-10 shape; re-grep `colspan="10"` / cell-count assertions in `tests/web/test_open_positions*` at executing-plans and update them in THIS task).

- [ ] **Step 5: Commit**

```bash
git add swing/web/templates/partials/open_positions*.html.j2 tests/web/test_open_positions_thumbnail.py
git commit -m "feat(web): lazy candlestick thumbnail on open-positions rows (P14.N1)"
```

#### Task B.3 — hyp-rec render-direct thumbnail route

**Files:**
- Modify: `swing/web/routes/dashboard.py` (add the route + a module MA-lines constant)
- Create: `swing/web/templates/partials/hyprec_thumbnail.html.j2`
- Test: `tests/web/test_hyprec_thumbnail.py` (NEW)

- [ ] **Step 1: Write the failing test (route contracts, production-path)**

```python
from fastapi.testclient import TestClient

def test_hyprec_thumbnail_returns_svg(monkeypatch, tmp_path):
    app = _build_app_with_ohlcv_cache_returning_bars(tmp_path)  # see §L
    with TestClient(app) as client:
        resp = client.get("/dashboard/hyprec/NVDA/thumbnail",
                          headers={"HX-Request": "true"})
        assert resp.status_code == 200
        assert "<svg" in resp.text
        assert resp.headers["Cache-Control"] == "private, max-age=60"

def test_hyprec_thumbnail_unavailable_on_no_bars(monkeypatch, tmp_path):
    app = _build_app_with_ohlcv_cache_empty(tmp_path)  # get_or_fetch -> None/empty
    with TestClient(app) as client:
        resp = client.get("/dashboard/hyprec/NVDA/thumbnail",
                          headers={"HX-Request": "true"})
        assert resp.status_code == 200
        assert "chart-unavailable" in resp.text
        assert "<tr" not in resp.text  # fragment root is span/svg, never bare <tr>

def test_hyprec_thumbnail_does_not_write_chart_renders(monkeypatch, tmp_path):
    app = _build_app_with_ohlcv_cache_returning_bars(tmp_path)
    with TestClient(app) as client:
        client.get("/dashboard/hyprec/NVDA/thumbnail", headers={"HX-Request": "true"})
    # assert zero rows in chart_renders for surface='watchlist_row' ticker NVDA
    assert _count_chart_renders(tmp_path, surface="watchlist_row", ticker="NVDA") == 0
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/web/test_hyprec_thumbnail.py -v`
Expected: FAIL (route 404 — not registered).

- [ ] **Step 3: Implementation**

In `swing/web/routes/dashboard.py` add the module constant + route (imports: `render_watchlist_thumbnail_svg` from `swing.web.charts`; the shared cap from `swing.web.thumbnail_render`; `apply_overrides`):

```python
from swing.web.charts import render_watchlist_thumbnail_svg
from swing.web.thumbnail_render import (
    _THUMBNAIL_CACHE_CONTROL,
    _THUMBNAIL_RENDER_SEMAPHORE,
    _THUMBNAIL_RENDER_TIMEOUT_S,
)

# Mirror chart_jit._WATCHLIST_THUMBNAIL_MA_LINES for cache/visual uniformity.
_HYPREC_THUMBNAIL_MA_LINES: list[int] = [20, 50]


@router.get("/dashboard/hyprec/{ticker}/thumbnail", response_class=HTMLResponse)
def hyprec_thumbnail_fragment(request: Request, ticker: str):
    """Phase 14 close-out (P14.N1): lazy ticker-window thumbnail for a hyp-rec
    candidate row. RENDER-DIRECT (no chart_renders write; L5) -- fetches bars
    via the OHLCV cache and calls render_watchlist_thumbnail_svg directly,
    NOT chart_jit.get_or_render_surface (which writes the cache). Three
    contracts: 200+SVG / 200+busy (self-retry) / 200+unavailable. Render
    exceptions isolated. Cache-Control distinct (busy = no-store)."""
    templates = request.app.state.templates
    ohlcv_cache = request.app.state.ohlcv_cache

    def _frag(*, svg, busy):
        resp = templates.TemplateResponse(
            request, "partials/hyprec_thumbnail.html.j2",
            {"chart_svg_bytes": svg, "busy": busy, "ticker": ticker},
        )
        resp.headers["Cache-Control"] = (
            "no-store" if busy else _THUMBNAIL_CACHE_CONTROL
        )
        return resp

    if ohlcv_cache is None:
        return _frag(svg=None, busy=False)
    if not _THUMBNAIL_RENDER_SEMAPHORE.acquire(
            timeout=_THUMBNAIL_RENDER_TIMEOUT_S):
        log.warning("hyp-rec thumbnail render busy ticker=%s", ticker)
        return _frag(svg=None, busy=True)
    try:
        bars = ohlcv_cache.get_or_fetch(ticker=ticker)
        if bars is None or len(bars) == 0:
            svg = None
        else:
            svg = render_watchlist_thumbnail_svg(
                ticker=ticker, bars=bars,
                ma_lines=_HYPREC_THUMBNAIL_MA_LINES,
            )
    except Exception:
        log.warning("hyp-rec thumbnail render failed ticker=%s",
                    ticker, exc_info=True)
        svg = None
    finally:
        _THUMBNAIL_RENDER_SEMAPHORE.release()
    return _frag(svg=svg, busy=False)
```

> Note: `render_watchlist_thumbnail_svg` raises on an unsafe ticker (`_assert_ticker_safe`) and `get_or_fetch` raises `ValueError` on empty-archive — both are caught by the broad `except` → unavailable fragment. The route does NOT pass `window_days` so the OHLCV cache uses its default; Slice C widens the default-bearing sites but this render-direct call can also pass `window_days=MIN_CALENDAR_DAYS_FOR_MA200` for a fuller MA200 thumbnail — add that explicit kwarg in Slice C Task C.3 for uniformity (the thumbnail MA lines are 20/50 so the default suffices for V1; documented).

Create `swing/web/templates/partials/hyprec_thumbnail.html.j2` (ticker-keyed; root `<svg>`/`<span>`; the busy branch self-retries the ticker route):

```html
{# Phase 14 close-out (P14.N1): lazy hyp-rec candidate thumbnail fragment. The
   ONLY | safe content is matplotlib-generated SVG bytes. Fragment root is
   <svg>/<span> (never a bare <tr>), so the HTMX synthetic-table-wrap hazard
   does not apply. Busy self-retries the ticker-keyed route. #}
{% if chart_svg_bytes %}{{ chart_svg_bytes.decode('utf-8') | safe }}
{% elif busy %}<span class="chart-unavailable" data-chart-reason="busy"
      hx-get="/dashboard/hyprec/{{ ticker }}/thumbnail"
      hx-trigger="load delay:1500ms" hx-target="this" hx-swap="outerHTML"
      hx-headers='{"HX-Request": "true"}'>Chart loading...</span>
{% else %}<span class="chart-unavailable" data-chart-reason="no-coverage">Chart unavailable.</span>{% endif %}
```

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/web/test_hyprec_thumbnail.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/routes/dashboard.py swing/web/templates/partials/hyprec_thumbnail.html.j2 tests/web/test_hyprec_thumbnail.py
git commit -m "feat(web): render-direct lazy thumbnail route for hyp-rec rows (P14.N1)"
```

#### Task B.4 — hyp-rec table column shape (+ regression; `<tr>` stays trigger-free)

**Files:**
- Modify: `swing/web/templates/partials/hypothesis_recommendations.html.j2:36-44`
- Modify: `swing/web/templates/partials/hypothesis_recommendations_row.html.j2:15-20`
- Modify: `swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2:10`
- Test: extend `tests/web/test_hyprec_thumbnail.py` + re-run `tests/web/test_hyp_recs_table_regression.py`

- [ ] **Step 1: Write the failing test**

```python
def test_hyprec_column_counts_align(seeded_hyprec_db, monkeypatch):
    body = _render_dashboard(seeded_hyprec_db, monkeypatch)
    header_th = _count_header_th(body, table_class="hypothesis-recommendations")
    compact_td = _count_first_row_td(body, row_id_prefix="hyp-rec-row-")
    assert header_th == 10
    assert compact_td == 10
    expanded = _get_hyprec_expanded_fragment("NVDA", seeded_hyprec_db, monkeypatch)
    assert 'colspan="10"' in expanded

def test_hyprec_row_lazy_cell_but_tr_trigger_free(seeded_hyprec_db, monkeypatch):
    body = _render_dashboard(seeded_hyprec_db, monkeypatch)
    # the lazy thumbnail cell hx-gets the ticker route
    assert 'hx-get="/dashboard/hyprec/' in body and "/thumbnail" in body
    assert 'hx-trigger="revealed"' in body
    # the <tr> OPEN TAG itself must remain trigger-free (discriminator)
    import re
    m = re.search(r'<tr\b[^>]*\bid="hyp-rec-row-NVDA"[^>]*>', body)
    assert m and "hx-get" not in m.group(0) and "hx-trigger" not in m.group(0)
```

- [ ] **Step 2: Run to verify failure**

Run: `python -m pytest tests/web/test_hyprec_thumbnail.py -v -k column_counts`
Expected: FAIL (9 `<th>`, 9 `<td>`, colspan 9).

- [ ] **Step 3: Implementation**

`hypothesis_recommendations.html.j2:35-45` — add `<th>Chart</th>` AFTER the expand `<th>` (keep the chevron leftmost):

```html
      <tr>
        <th aria-label="Expand"></th>
        <th>Chart</th>
        <th>Ticker</th>
        <th>Price</th>
        ...
```

`hypothesis_recommendations_row.html.j2` — add the lazy thumbnail `<td>` AFTER the chevron `<td>` (the `<tr>` stays trigger-free; only this `<td>` carries hx-*):

```html
<tr id="hyp-rec-row-{{ rec.ticker }}"{% if rec.tripwire_fired %} class="tripwire-fired"{% endif %}>
  <td><button class="expand-toggle" type="button"
              hx-get="/hyp-recs/{{ rec.ticker }}/expand"
              ...>▸</button></td>
  <td class="hyprec-thumb" data-ticker="{{ rec.ticker }}"
      hx-get="/dashboard/hyprec/{{ rec.ticker }}/thumbnail"
      hx-trigger="revealed" hx-swap="innerHTML"
      hx-headers='{"HX-Request": "true"}'></td>
  <td>{{ rec.ticker }}</td>
  ...
```

`hypothesis_recommendations_expanded.html.j2:10` — `colspan="9"` → `colspan="10"`.

- [ ] **Step 4: Run to verify pass**

Run: `python -m pytest tests/web/test_hyprec_thumbnail.py tests/web/test_hyp_recs_table_regression.py -v`
Expected: PASS (the regression test still passes — the `<tr>` open tag is unchanged; update any pre-existing hyp-rec colspan/cell-count assertions in this task).

- [ ] **Step 5: Commit**

```bash
git add swing/web/templates/partials/hypothesis_recommendations*.html.j2 tests/web/test_hyprec_thumbnail.py
git commit -m "feat(web): lazy ticker thumbnail on hyp-rec rows (P14.N1)"
```

#### Task B.5 — Slice B full-suite check

- [ ] Run `python -m pytest -m "not slow" -q` → green; `ruff check swing/` → clean. Fix any drift (esp. pre-existing column-count assertions on either table) in the owning task's commit.

---

### Slice C — A-1 market_weather ≥200-bar fetch window

#### Task C.1 — shared constant + pipeline `_bars_or_none` (+ regression)

**Files:**
- Modify: `swing/web/ohlcv_cache.py` (add `MIN_CALENDAR_DAYS_FOR_MA200 = 300`)
- Modify: `swing/pipeline/runner.py:2763` and `:2694`
- Test: `tests/pipeline/test_step_charts_fetch_window.py` (NEW or extend an existing `_step_charts` test)

- [ ] **Step 1: Write the failing test**

```python
def test_bars_or_none_uses_min_calendar_days_for_ma200(monkeypatch):
    from swing.web.ohlcv_cache import MIN_CALENDAR_DAYS_FOR_MA200
    assert MIN_CALENDAR_DAYS_FOR_MA200 >= 290  # >=200 trading bars
    captured = {}
    class FakeCache:
        def get_or_fetch(self, *, ticker, window_days):
            captured[ticker] = window_days
            return _fake_bars()  # >=200 rows
    # drive _bars_or_none (or _step_charts) with FakeCache; assert the window
    # passed for the benchmark ticker == MIN_CALENDAR_DAYS_FOR_MA200
    ...
    assert captured[BENCHMARK] == MIN_CALENDAR_DAYS_FOR_MA200
```

- [ ] **Step 2: Run to verify failure** — Run the new test → FAIL (constant absent / window is 200).

- [ ] **Step 3: Implementation**

`swing/web/ohlcv_cache.py` (module level, near the class / above `get_or_fetch`):

```python
# Phase 14 close-out (A-1): a 200-trading-bar SMA200 needs ~200 * 365/252 ~=
# 290 calendar days of lookback; use 300 with margin. CALENDAR-day window
# (get_or_fetch's window_days is a calendar lookback). Shared by the pipeline
# benchmark/chart fetch + the dashboard weather refresh + the JIT path so the
# 200-MA on any MA200-bearing surface has enough bars. Monotonic-safe (more
# bars only; consumers slice).
MIN_CALENDAR_DAYS_FOR_MA200 = 300
```

`runner.py:2763` (`_bars_or_none`) and `:2694` — import at module top `from swing.web.ohlcv_cache import MIN_CALENDAR_DAYS_FOR_MA200` (pipeline already imports from `swing.web.ohlcv_cache` at `:352` lazily; add a top-level import or a local import mirroring the existing lazy pattern), then replace `window_days=200` → `window_days=MIN_CALENDAR_DAYS_FOR_MA200` at both lines.

- [ ] **Step 4: Run to verify pass** — Run the new test → PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/ohlcv_cache.py swing/pipeline/runner.py tests/pipeline/test_step_charts_fetch_window.py
git commit -m "fix(pipeline): widen OHLCV fetch window to >=200 trading bars for MA200 (A-1)"
```

#### Task C.2 — dashboard weather refresh passes the constant (production-path)

**Files:**
- Modify: `swing/web/routes/dashboard.py:94`
- Test: `tests/web/test_market_weather_fetch_window.py` (NEW)

- [ ] **Step 1: Write the failing test**

```python
def test_weather_refresh_fetches_min_calendar_days(monkeypatch, tmp_path):
    from swing.web.ohlcv_cache import MIN_CALENDAR_DAYS_FOR_MA200
    captured = {}
    # patch app.state.ohlcv_cache with a fake recording window_days, seed a
    # completed pipeline_run, POST the weather refresh, assert >=200 bars reach
    # render_market_weather_svg via the REAL handler path.
    ...
    assert captured["window_days"] == MIN_CALENDAR_DAYS_FOR_MA200
```

- [ ] **Step 2: Run to verify failure** — FAIL (handler passes no `window_days` → 180).

- [ ] **Step 3: Implementation**

`dashboard.py:94`:

```python
            bars = ohlcv_cache.get_or_fetch(
                ticker=benchmark, window_days=MIN_CALENDAR_DAYS_FOR_MA200,
            )
```

Add the import at the top of `dashboard.py`: `from swing.web.ohlcv_cache import MIN_CALENDAR_DAYS_FOR_MA200`.

- [ ] **Step 4: Run to verify pass** — PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/routes/dashboard.py tests/web/test_market_weather_fetch_window.py
git commit -m "fix(web): weather-chart refresh fetches >=200 bars for MA200 (A-1)"
```

#### Task C.3 — JIT path + hyp-rec thumbnail window (OQ-6 uniformity)

**Files:**
- Modify: `swing/web/chart_jit.py:117`
- Modify: `swing/web/routes/dashboard.py` (the hyp-rec route `get_or_fetch` — pass the constant)
- Test: extend `tests/web/test_hyprec_thumbnail.py` / a `chart_jit` test

- [ ] **Step 1: Write the failing test** — assert `chart_jit.get_or_render_surface` calls `get_or_fetch(window_days=MIN_CALENDAR_DAYS_FOR_MA200)` (mock the cache) and the hyp-rec route passes the same.

- [ ] **Step 2: Run to verify failure** — FAIL (200 / default).

- [ ] **Step 3: Implementation**

`chart_jit.py:117`: `bars = ohlcv_cache.get_or_fetch(ticker=ticker, window_days=MIN_CALENDAR_DAYS_FOR_MA200)` (import the constant). In the hyp-rec route (Task B.3) change `ohlcv_cache.get_or_fetch(ticker=ticker)` → `ohlcv_cache.get_or_fetch(ticker=ticker, window_days=MIN_CALENDAR_DAYS_FOR_MA200)`.

- [ ] **Step 4: Run to verify pass** — PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/chart_jit.py swing/web/routes/dashboard.py tests/web/test_hyprec_thumbnail.py
git commit -m "fix(web): widen JIT + hyp-rec thumbnail fetch window for MA200 uniformity (A-1 OQ-6)"
```

#### Task C.4 — Slice C full-suite check
- [ ] `python -m pytest -m "not slow" -q` → green; `ruff check swing/` → clean.

---

### Slice D — cosmetics A-2 / A-4 / A-6

#### Task D.1 — A-2 VCP contraction-label reposition

**Files:**
- Modify: `swing/web/charts.py:836-841`
- Test: `tests/web/test_charts.py` (format-string + position assertion)

- [ ] **Step 1: Write the failing test**

```python
def test_vcp_contraction_labels_off_price_tick_column(monkeypatch):
    # Capture ax.text calls; assert the contraction label x-anchor/ha are NOT
    # the right-edge (0.98/right) that crowds the price y-axis tick column.
    calls = _capture_ax_text_calls_for_vcp(...)  # render_theme2_annotated_svg w/ VCP evidence
    contraction_calls = [c for c in calls if "contraction" in c.text]
    assert contraction_calls
    for c in contraction_calls:
        assert c.x <= 0.75  # moved inward / left, off the right tick column
        assert "pct" in c.text and "$" not in c.text and "^" not in c.text
```

- [ ] **Step 2: Run to verify failure** — FAIL (x=0.98, ha="right").

- [ ] **Step 3: Implementation**

`charts.py:836-841` — move inward to avoid the right price-tick column. **Caution (re-grep finding):** a top-LEFT inset at `(0.02, 0.92)` collides with the ticker label at `charts.py:543` (`0.02, 0.92, ticker`). Use the inward-right anchor to avoid BOTH the tick column and the ticker label:

```python
            ax.text(
                0.74, 0.92 - i * 0.05,
                f"contraction {i + 1}: {depth:.1f}pct",
                transform=ax.transAxes, fontsize=8, color="#222",
                ha="right",
            )
```

- [ ] **Step 4: Run to verify pass** — PASS. (Binding visual check is S6.)

- [ ] **Step 5: Commit**

```bash
git add swing/web/charts.py tests/web/test_charts.py
git commit -m "fix(web): reposition VCP contraction labels off the price-tick column (A-2)"
```

#### Task D.2 — A-4 `_bulz_*` → general rename (behavior-neutral)

**Files:**
- Modify: `swing/web/charts.py` (functions `_bulz_target_price`→`_rr_target_price`, `_draw_bulz_zones`→`_draw_risk_reward_zones`; comments at `:235,628,633,661,704`; WARN text at `:750,765`; calls at `:708,756`)
- Modify: `swing/web/view_models/open_positions_row.py:257` (comment), `swing/web/templates/partials/open_positions_expanded.html.j2:39` (comment)
- Test: `tests/web/test_charts.py:30` (import) + test function names

- [ ] **Step 1: Update the tests first (rename import + test names; keep `ticker="BULZ"` fixtures)**

In `tests/web/test_charts.py`: change `from swing.web.charts import (... _bulz_target_price ...)` → `_rr_target_price`; rename `test_bulz_target_price_*` → `test_rr_target_price_*`; update any direct `_draw_bulz_zones` references → `_draw_risk_reward_zones`. **Leave every `ticker="BULZ"` / `_make_trade(ticker="BULZ")` unchanged** (real ticker symbol — §E.5).

- [ ] **Step 2: Run to verify failure** — FAIL (`ImportError: cannot import name '_rr_target_price'`).

- [ ] **Step 3: Implementation**

Rename in `swing/web/charts.py`:
- `def _bulz_target_price(trade)` → `def _rr_target_price(trade)`; docstring "Absolute BULZ target price" → "Absolute risk/reward target price".
- `def _draw_bulz_zones(...)` → `def _draw_risk_reward_zones(...)`; docstring "Draw BULZ risk ... zones" → "Draw risk (entry->stop) + reward (entry->target) shaded zones".
- Call sites `:708` (`_draw_bulz_zones(...)` → `_draw_risk_reward_zones(...)`) and `:756` (`_bulz_target_price(trade)` → `_rr_target_price(trade)`).
- WARN strings `:750` "skipping BULZ risk zone for %s" → "skipping risk zone for %s"; `:765` "skipping BULZ reward zone for %s" → "skipping reward zone for %s".
- Comments `:235` ("reserved for BULZ risk/reward fills" → "reserved for risk/reward fills"), `:628,661,704` ("BULZ risk/reward zones" → "risk/reward zones").

Update the two doc-comment references in `open_positions_row.py:257` and `open_positions_expanded.html.j2:39` ("BULZ-zones" → "risk/reward zones").

- [ ] **Step 4: Run to verify pass** — Run `python -m pytest tests/web/test_charts.py -q` → PASS; `grep -rn "_bulz\|bulz" swing/` returns ONLY (if any) intentional remnants — expect ZERO `_bulz`/`bulz` tokens left in `swing/` (the `BULZ` ticker remnants live only in tests as fixture data).

- [ ] **Step 5: Commit**

```bash
git add swing/web/charts.py swing/web/view_models/open_positions_row.py swing/web/templates/partials/open_positions_expanded.html.j2 tests/web/test_charts.py
git commit -m "refactor(web): rename _bulz_* risk/reward helpers to general names (A-4)"
```

#### Task D.3 — A-6 process-grade-trend dark-mode CSS

**Files:**
- Modify: `swing/web/static/app.css`
- Test: `tests/web/test_app_css_process_grade.py` (NEW)

- [ ] **Step 1: Write the failing test**

```python
def test_process_grade_css_rules_present():
    css = (Path("swing/web/static/app.css")).read_text(encoding="utf-8")
    assert ".process-grade-rolling-line" in css
    assert ".process-grade-marker" in css
    # resolves via the theme-aware accent token (not a hardcoded hex)
    assert "stroke: var(--accent)" in css
    assert "fill: var(--accent)" in css
```

- [ ] **Step 2: Run to verify failure** — FAIL (no such rules).

- [ ] **Step 3: Implementation** — append to `swing/web/static/app.css` (near the sparkline precedent at `:331`):

```css
/* Phase 14 close-out (A-6): the process-grade-trend SVG marker has no fill=
   (SVG-default black -> invisible in dark mode) and the rolling polyline has
   no stroke= (SVG-default none -> invisible in BOTH themes). Resolve both via
   the theme-aware accent token (mirrors .metrics-card__sparkline). */
.process-grade-rolling-line { stroke: var(--accent); }
.process-grade-marker { fill: var(--accent); }
```

- [ ] **Step 4: Run to verify pass** — PASS. (Binding check: operator views `/metrics/process-grade-trend` in DARK mode at S6.)

- [ ] **Step 5: Commit**

```bash
git add swing/web/static/app.css tests/web/test_app_css_process_grade.py
git commit -m "fix(web): process-grade-trend chart visible via accent token in dark mode (A-6)"
```

#### Task D.4 — Slice D full-suite check
- [ ] `python -m pytest -m "not slow" -q` → green; `ruff check swing/` → clean.

---

### Slice E — group-(a) minors (C-1/C-2/C-3/C-5/C-19; C-6 DEFERRED)

#### Task E.0 — record the C-6 deferral (no code)
- [ ] Confirm the §E.6 analysis stands at executing-plans STEP 0 (re-read `backfill_trades_sector_industry.py:104-131`). C-6 is NOT implemented. Note the deferral in the return report's banked-follow-ups list. (No commit.)

#### Task E.1 — C-1 PROVISIONAL default flips to False

**Files:**
- Modify: `swing/web/view_models/trades.py:2153`
- Test: `tests/web/` (re-grep the owning DailyManagementTileVM test)

- [ ] **Step 1: Write/identify the failing test** — assert a freshly-constructed `DailyManagementTileVM` (or the builder default) has `position_capital_utilization_is_provisional == False` when not explicitly set.

```python
def test_daily_management_tile_provisional_defaults_false():
    vm = DailyManagementTileVM(...required fields...)  # omit the provisional kwarg
    assert vm.position_capital_utilization_is_provisional is False
```

- [ ] **Step 2: Run to verify failure** — FAIL (default is True).
- [ ] **Step 3: Implementation** — `trades.py:2153`: `position_capital_utilization_is_provisional: bool = True` → `= False`.
- [ ] **Step 4: Run to verify pass** — PASS (verify no builder relied on the True default to set the PROVISIONAL badge; re-grep callers of this field at executing-plans — the builder that resolves the real PROVISIONAL/LIVE state must set it explicitly, which it should already per `shared.py:135-142`).
- [ ] **Step 5: Commit**

```bash
git add swing/web/view_models/trades.py tests/web/...
git commit -m "fix(web): daily-management provisional flag defaults to False (C-1)"
```

#### Task E.2 — C-2 daily-management tooltip wording

**Files:**
- Modify: `swing/web/templates/partials/daily_management_tile.html.j2:132`
- Test: a template-render substring assertion (extend the tile's test)

- [ ] **Step 1: Write the failing test** — assert the rendered tile does NOT contain the misleading "covers today" and DOES contain the accurate "covers this row's session date".
- [ ] **Step 2: Run to verify failure** — FAIL.
- [ ] **Step 3: Implementation** — `:132`: "...account_equity_snapshots row covers today; PROVISIONAL otherwise." → "...account_equity_snapshots row covers this row's session date; PROVISIONAL otherwise." (ASCII).
- [ ] **Step 4: Run to verify pass** — PASS.
- [ ] **Step 5: Commit**

```bash
git add swing/web/templates/partials/daily_management_tile.html.j2 tests/web/...
git commit -m "fix(web): clarify daily-management LIVE/PROVISIONAL tooltip wording (C-2)"
```

#### Task E.3 — C-3 backfill artifact-write OSError → ClickException

**Files:**
- Modify: `swing/cli.py` (the `diagnose backfill-trades-sector-industry` command)
- Test: `tests/cli/test_diagnose_backfill_trades_sector_industry.py`

- [ ] **Step 1: Write the failing test**

```python
def test_artifact_write_oserror_raises_click_exception(tmp_path, monkeypatch):
    # Make _emit_restore_sql (or the output_dir.mkdir) raise OSError; invoke the
    # CLI; assert a clean ClickException (non-zero exit, no raw traceback), not
    # an unhandled OSError.
    monkeypatch.setattr(
        "swing.diagnostics.backfill_trades_sector_industry._emit_restore_sql",
        _raise_oserror,
    )
    result = runner.invoke(cli, ["diagnose", "backfill-trades-sector-industry", ...])
    assert result.exit_code != 0
    assert isinstance(result.exception, SystemExit) or "Error:" in result.output
    assert not isinstance(result.exception, OSError)
```

- [ ] **Step 2: Run to verify failure** — FAIL (raw OSError propagates).
- [ ] **Step 3: Implementation** — at the CLI command boundary in `swing/cli.py`, wrap the call into `run_backfill_*`/the diagnostics entrypoint:

```python
    try:
        summary = _run_backfill_trades_sector_industry(...)
    except OSError as exc:
        raise click.ClickException(
            f"failed to write backfill restore artifact: {exc}"
        ) from exc
```

> Re-grep the exact command function + the diagnostics call at executing-plans STEP 0; place the try/except at the CLI boundary (not inside the diagnostics module — preserve the service/CLI boundary discipline).

- [ ] **Step 4: Run to verify pass** — PASS.
- [ ] **Step 5: Commit**

```bash
git add swing/cli.py tests/cli/test_diagnose_backfill_trades_sector_industry.py
git commit -m "fix(cli): wrap backfill artifact-write OSError as ClickException (C-3)"
```

#### Task E.4 — C-5 strengthen the BEGIN-IMMEDIATE ordering test

**Files:**
- Modify: `tests/cli/test_diagnose_backfill_trades_sector_industry.py:546` (`test_apply_path_uses_begin_immediate_lock_for_toctou_safety`)

- [ ] **Step 1: Strengthen the assertion** — the test already records `executed_statements`. Add an ORDER assertion: `BEGIN IMMEDIATE` must appear BEFORE the first SELECT-of-trades and BEFORE the UPDATE:

```python
    statements_upper = [s.strip().upper() for s in executed_statements]
    bi = statements_upper.index("BEGIN IMMEDIATE")
    first_select = next(i for i, s in enumerate(statements_upper)
                        if s.startswith("SELECT") and "TRADES" in s)
    first_update = next(i for i, s in enumerate(statements_upper)
                        if s.startswith("UPDATE"))
    assert bi < first_select, "BEGIN IMMEDIATE must precede the re-SELECT"
    assert bi < first_update, "BEGIN IMMEDIATE must precede the UPDATE"
```

- [ ] **Step 2: Run to verify it passes against current production code** (the lock IS issued first) — Run: `python -m pytest tests/cli/test_diagnose_backfill_trades_sector_industry.py::test_apply_path_uses_begin_immediate_lock_for_toctou_safety -v` → PASS. (This is a test-hardening step; verify it would FAIL if the lock were moved after the SELECT by temporarily reordering — optional sanity check, then revert.)

> Per `feedback_regression_test_arithmetic`: confirm the strengthened assertion distinguishes — i.e. it would fail if `BEGIN IMMEDIATE` were emitted after the SELECT/UPDATE. The capture harness records statement order; if it does not capture SELECT/UPDATE text, extend the capture (re-grep the harness at executing-plans).

- [ ] **Step 3: Commit**

```bash
git add tests/cli/test_diagnose_backfill_trades_sector_industry.py
git commit -m "test(cli): assert BEGIN IMMEDIATE ordering vs SELECT/UPDATE in backfill apply path (C-5)"
```

#### Task E.5 — C-19 xdist co-residency flake guard

**Files:**
- Modify: `tests/research/test_pattern_cohort_evaluator_reader.py:37`

- [ ] **Step 1: Implementation** — add the xdist group marker so the test runs in a stable worker group (passes in isolation; flakes under co-residency):

```python
@pytest.mark.xdist_group(name="ohlcv_reader_re_export")
def test_ohlcv_reader_re_export_identity():
    ...
```

Ensure `import pytest` is present at the top of the module.

- [ ] **Step 2: Run to verify** — Run `python -m pytest tests/research/test_pattern_cohort_evaluator_reader.py -v` (in isolation) → PASS; run the full suite with xdist `python -m pytest -m "not slow" -q` → the flake no longer reproduces.

- [ ] **Step 3: Commit**

```bash
git add tests/research/test_pattern_cohort_evaluator_reader.py
git commit -m "test(research): pin ohlcv-reader re-export test to an xdist group (C-19)"
```

#### Task E.6 — Slice E full-suite check
- [ ] `python -m pytest -m "not slow" -q` → green; `ruff check swing/` → clean.

---

## §H Test surface (production-path; #15 / L6)

- **A-7:** VM-level (UNKNOWN/None branches) + a TestClient topbar render under the UNSEEDED fixture asserting `schwab-health-badge--warn` + `Schwab?` in the rendered `base.html.j2`, AND no sidecar created by the lifespan — the regression the SB5.5 seeded gate missed. Plus the L2-LOCK grep test.
- **P14.N1:** real-route tests (open-positions reuses `/journal/trades/{id}/thumbnail`; hyp-rec hits `/dashboard/hyprec/{ticker}/thumbnail`) driving the REAL renderers; the hyp-rec no-`chart_renders`-write assertion (L5); column-count regressions on BOTH tables (compact == header == expanded); the hyp-rec `<tr>`-trigger-free regression re-run.
- **A-1:** assert ≥200-calendar-day window reaches `get_or_fetch` via the REAL pipeline `_bars_or_none`/`_step_charts` path AND the REAL dashboard refresh handler (not a stub) + the JIT path.
- **A-2:** ax.text-capture (label x-anchor off the tick column; mathtext-free). **A-4:** import + rename completeness (zero `_bulz`/`bulz` tokens in `swing/`). **A-6:** CSS-presence (weak; the binding check is S6).
- **group-(a):** C-1 default; C-2 tooltip substring; C-3 ClickException; C-5 ordering; C-19 isolation.

---

## §I Operator gate (executing-plans; S1–S8; UNSEEDED/default-state witness)
- **S1** `python -m pytest -m "not slow" -q` green + `ruff check swing/` clean.
- **S2** schema unchanged (v23; no `0024`; no new domain/`chart_renders` write on the thumbnail path).
- **S3** `tests/integration/test_l2_lock_source_grep.py` green (A-7 zero new `schwabdev.Client.` sites).
- **S4 (P14.N1, browser)** open-positions AND hyp-rec thumbnails render with real rows in the live DB; no-coverage rows degrade cleanly; both tables' column counts align (compact == header == expanded).
- **S5 (A-1)** the ≥200-bar regression + operator confirms the market-weather widget's 200-MA renders as a full line.
- **S6 (A-2/A-4/A-6, browser)** VCP labels uncrowded; the rename is behavior-neutral (tests green); the process-grade-trend chart visible in DARK mode.
- **S7 (A-7, browser — THE default-state witness)** under the UNSEEDED precondition (production + ladder enabled, NO pre-existing sidecar, no constructible Schwab client at startup — the operator's degraded production tokens reproduce this naturally): the topbar shows the `Schwab?` UNKNOWN (warn) badge instead of nothing. Optional separate witness with valid tokens: badge shows ALIVE/STARTING.
- **S8** trailers `[]`; ZERO Co-Authored-By.

---

## §J Codex placement (OQ-8; SINGLE chain to convergence)
Run ONE WSL Codex chain after the plan is written + internally chunk-reviewed (writing-plans) and again after all tasks complete (executing-plans). Run to convergence (NO_NEW_CRITICAL_MAJOR; the ~5-round cap is suspended). Transport: copowers v2.0.3 WSL fallback (`wsl bash -ilc`; verify `command -v codex` → `/home/<wsluser>/.local/node22/bin/codex`; pre-generate the diff on Windows; tell Codex NOT to run git). PERSIST each round's prompt AND response to `.copowers-findings.md` (incl. the final `### Verdict`). **Watch items:** A-7 `_is_ladder_active` semantics + reason text + the UNSEEDED topbar test; the L2-LOCK (zero new `schwabdev.Client.` sites); P14.N1 dual-renderer LAZY delivery (the HTMX `<tr>`-root hazard; `hx-headers HX-Request`; column-count alignment on BOTH tables; the hyp-rec render-direct no-`chart_renders`-write; the shared semaphore); A-1 calendar-vs-trading-bar arithmetic + the third site (`runner.py:2694`) scoping; A-2 mathtext-free + the ticker-label collision; A-4 rename completeness (NOT the `BULZ` ticker); A-6 both-theme resolution; the C-6 deferral rationale; `USERPROFILE`+`HOME` monkeypatch; ASCII; production-path. If a finding needs a schema change or a new `schwabdev.Client.*` site, STOP + escalate.

---

## §K Schema impact
**NO schema change. v23 held.** `EXPECTED_SCHEMA_VERSION = 23` at `swing/data/db.py:51` unchanged; no migration `0024`. Every item is web-VM / template / route / CSS / pipeline-constant / test. A-7 reads the existing ephemeral sidecar file (not the DB). S2 asserts v23 + NO migration + no new `chart_renders` write on the thumbnail path.

---

## §L Fixtures

### A-7 UNSEEDED fixture (the binding one)
Goal: a TestClient app in PRODUCTION mode + ladder enabled (so `_is_ladder_active` is True and the badge gate passes) BUT with NO constructible Schwab client (so the lifespan installs no checker and writes no sidecar), AND an isolated HOME so no real sidecar leaks/exists.

- `monkeypatch.setenv("USERPROFILE", str(tmp_path))` + `monkeypatch.setenv("HOME", str(tmp_path))` (config-write gotcha — `checker_liveness_sidecar_path`/`_user_home` resolve under tmp).
- cfg: `environment="production"`, `marketdata_ladder_enabled=True`, but NO Schwab creds (or stub `construct_authenticated_client` / `_construct_web_schwab_client` to return `None`) so `_install_web_marketdata_caches` returns early (no checker, no seed → no sidecar). The cleanest seam: `monkeypatch.setattr("swing.web.app._construct_web_schwab_client", lambda cfg: None)` — exercises the real `create_app` lifespan and the real topbar render while guaranteeing no sidecar is written.
- Build the app via the project's existing `create_app(cfg)` helper (re-grep `swing/web/app.py` for the exact constructor + how tests build apps in `tests/web/`); enter the lifespan with `with TestClient(app) as client:`.
- Assert AFTER the first `client.get("/")`: `checker_liveness_sidecar_path("production").exists()` is False (no app-created sidecar) AND the body contains the warn badge.

### Sandbox/ladder-disabled fixture
Same shape but `environment="sandbox"` (or `marketdata_ladder_enabled=False`) → `build_schwab_checker_badge` returns None → no `schwab-health-badge` in the body.

### P14.N1 fixtures
- Open-positions: reuse the established seeded-open-trade dashboard fixture in `tests/web/test_open_positions*.py`; the thumbnail route reuse means the journal route's own tests already cover the SVG/unavailable/busy contracts.
- Hyp-rec: a fake `app.state.ohlcv_cache` whose `get_or_fetch` returns a ≥1-row OHLCV DataFrame (SVG path) or None/empty (unavailable path); a recording variant for the window-days assertion. Use an in-memory DB (`tmp_path`) and assert zero `chart_renders` rows for `surface='watchlist_row'`.

### A-1 fixture
A fake OHLCV cache recording `window_days` (Tasks C.1–C.3); seed a completed `pipeline_run` for the dashboard refresh handler path (C.2).

---

## §M Forward-binding lessons
- **A-7 proves the seeded-gate lesson** (`feedback_seeded_gate_masks_default_state`): the SB5.5 S6 gate validated the badge only via seeded sidecars, masking the real no-checker-no-badge behavior. The S7 gate + the UNSEEDED topbar test witness the genuine default state. Carry this: any operator-witnessed render gate must witness the UNSEEDED/default state, not only a seeded one.
- **Re-grep finds sites the brief enumerates incompletely** — A-1's `runner.py:2694` was beyond the brief's named sites; STEP-0 re-grep (#2) caught it. Always re-grep the *defect pattern* (`window_days=200`), not just the named anchors.
- **A rename brief can collide with a real identifier** — `BULZ` is both the feature nickname AND a real ticker; rename the feature, never the ticker. Disambiguate token usages before a blanket rename.
- **A "small" lock-narrowing (C-6) can reopen a closed invariant** — read the in-line comments documenting WHY a lock spans an operation before narrowing it; defer when the invariant is genuine.

---

## §N Self-review (run against the spec)

**Spec coverage:** P14.N1 (both tables — §G Slice B), A-1 (§G Slice C, incl. the third site + JIT), A-2/A-4/A-6 (§G Slice D), A-7 design + wiring verdict + UNSEEDED witness (§G Slice A + §L), group-(a) C-1/C-2/C-3/C-5/C-19 + C-6 deferral (§G Slice E). Every spec §3/§4/§5 item maps to a task. ✓

**Placeholder scan:** every code step shows the actual edit; test steps show real assertions. Re-grep-at-executing-plans notes are explicit pointers (not deferrals of design) for fixture/anchor confirmation per discipline #2. ✓

**Type/name consistency:** `MIN_CALENDAR_DAYS_FOR_MA200` (one name, used in C.1–C.3); `_THUMBNAIL_RENDER_SEMAPHORE`/`_THUMBNAIL_RENDER_TIMEOUT_S`/`_THUMBNAIL_CACHE_CONTROL` (shared module, imported by journal + hyp-rec route); `_rr_target_price`/`_draw_risk_reward_zones` (consistent across charts.py + tests); `hyprec_thumbnail.html.j2` context keys (`chart_svg_bytes`/`busy`/`ticker`) consistent between route and partial. ✓

**LOCK reverification:** L1–L7 + OQ-1..8 mapped in §E. NO schema (§K). L2-LOCK green (§E.7). C-6 deferred with documented rationale (§E.6). ✓

---

## §O Phase 14 close-out position
This batch is the FIRST close-out-tail item (SB1–SB5.5 all SHIPPED). After it merges: **B-7 (operator failure-mode classification — NEXT; may add a nullable review column → v24, OUT of this batch) → Phase 14 close-out review (Sec 9.1 Q6) → CLAUDE.md "Phase 14 CLOSED" at v23.** Banked follow-ups carried OUT of this batch: **C-6** (backfill write-lock narrowing — deferred, TOCTOU; §E.6) and (if the operator excludes it) the `runner.py:2694` A-1 widening. The schwabdev v2.5.1→3.0.5 upgrade (deletes P14.N7's checker guard) remains Phase 15. This batch holds v23, holds L2-LOCK, stays read-mostly.

---

*End of plan. Executing-plans: ONE bundle, 5 serial slices (A-7 → P14.N1 dual-table → A-1 → cosmetics → group-(a)). Single Codex chain to convergence at each phase (persist prompt+response). Operator gate S1–S8 incl. the A-7 UNSEEDED witness + the P14.N1/A-2/A-6 browser legs.*
