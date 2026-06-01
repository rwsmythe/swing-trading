# Phase 14 Close-Out Polish Batch — Brainstorming Design Spec

**Date:** 2026-06-01
**Phase:** 14 close-out tail (first item after SB5.5 SHIPPED `16b3366`)
**Branch (brainstorm):** `phase14-close-out-polish-batch-brainstorming` from main HEAD `e26803f`
**Dispatch brief:** `docs/phase14-close-out-polish-batch-brainstorming-dispatch-brief.md` (committed `42eaafd`)
**Anchors verified against:** `e26803f` (re-grep exact line numbers at writing-plans per discipline #2)

---

## §1 Overview

The close-out polish batch is a heterogeneous set of small, well-specified, Phase-14-scope
cleanups banked across SB1–SB5.5. It is a **read-mostly UX / wiring / cosmetic + test-hardening
batch on already-shipped surfaces** — NOT a new-feature, new-metric, or new-schema bundle. It is
the FIRST item of the close-out tail proper; the sequence after it is **B-7 (operator failure-mode
classification, the final touch) → Phase 14 close-out review (Sec 9.1 Q6) → CLAUDE.md "Phase 14
CLOSED" at v23.**

Batch items (operator-LOCKed list, `docs/phase3e-todo.md` `#5`):

| ID | Item | Kind | Depth |
|----|------|------|-------|
| P14.N1-dash | open-positions + hyp-rec table thumbnails (orphaned dashboard bit; journal-listing shipped SB4) | wiring/render | medium |
| A-1 | market_weather benchmark fetch-window too short for a 200-day MA | wiring | small |
| A-2 | theme2_annotated VCP 5-contraction label crowding | cosmetic | light |
| A-4 | `_bulz_*` → general rename (the zones are a general open-long feature) | cosmetic | light |
| A-6 | process-grade-trend drill-down chart invisible in dark mode | cosmetic | light |
| A-7 | Schwab web health badge does not render in normal operation (hides instead of UNKNOWN) | **wiring/design investigation** | **deep** |
| group (a) | C-1/C-2/C-3/C-5/C-6/C-19 (six SB1-era advisories + xdist flake) | test/advisory | light |

**The two load-bearing deliverables** are (1) the per-item IN/OUT triage + sub-bundle
decomposition (§9 + §12), and (2) the A-7 design-vs-wiring investigation (§4). The cosmetics
(A-2/A-4/A-6/group-(a)) are deliberately light — a paragraph each.

**Expected outcome:** NO schema change (v23 held); L2-LOCK green (A-7 adds zero new
`schwabdev.Client.*` call sites vs `bf7e071`); reuse not re-implement; read-mostly. The
operator-witnessed gate witnesses the **UNSEEDED/default state** (esp. A-7).

---

## §2 Pre-locked decisions (DO NOT re-litigate)

### §2.1 Sec 9.1 LOCKs (commissioning brief)
- **Q2 SERIAL** — the close-out polish batch is its own cycle, AFTER SB5.5 (SHIPPED), BEFORE B-7.
- **Q6 operator-witnessed verification at merge** — render-bearing items get an operator-witnessed
  browser gate; test-only items (group-(a)) are mechanically gated. Per
  `feedback_seeded_gate_masks_default_state`, the gate MUST witness the UNSEEDED/default state,
  not a seeded one (esp. A-7 — witness the genuine no-sidecar badge render).
- **Q7 Codex chain count = orchestrator discretion** → SINGLE chain for this brainstorming.

### §2.2 Phase-specific LOCKs (this brief, L1–L8)
- **L1** Scope = the `#5` items ONLY. NO B-7, NO close-out review, NO Phase 15+. **A-5 (styled 404)
  is CLOSED** (operator "no intention to revisit") — do NOT design it.
- **L2** Expected NO schema change (v23 held; `EXPECTED_SCHEMA_VERSION = 23` at `swing/data/db.py:51`).
  If ANY item appears to need a persisted row/column → STOP + escalate; do NOT design a v24.
- **L3 (L2-LOCK, Schwab)** A-7 keeps `tests/integration/test_l2_lock_source_grep.py` GREEN (baseline
  `L2_LOCK_BASELINE_SHA = "bf7e071"`; ZERO new `schwabdev.Client.*` call sites). The A-7 fix is a
  pure web view-model change — no Schwab API calls, no new client-construction path.
- **L4 REUSE, do not re-implement.** P14.N1 reuses `render_trade_window_thumbnail_svg` + the SB4
  journal route/VM/partial pattern; A-6 reuses `var(--accent)`; A-7 reuses `evaluate_liveness_state`
  (the UNKNOWN branch already exists) + `_BADGE_MAP`.
- **L5 Read-mostly.** ZERO swing-domain writes from any item. The chart helpers are render-direct
  (no `chart_renders` write on the thumbnail path).
- **L6 Production-path test discipline (#15).** P14.N1's wiring test, A-1's ≥200-bar regression, and
  A-7's badge test MUST exercise the REAL production derivation path (the actual VM/route/cache
  construction), NOT a stub.
- **L7 ASCII + redaction discipline.** Any new/changed CLI/stdout text stays ASCII (#16/#32). A-7
  must not regress the `setLogRecordFactory` redaction or leak tokens; the badge title stays ASCII.
- **L8 Decomposition is an operator decision at brainstorm** (§9). If A-7's wiring investigation
  found a REAL checker-non-start bug under valid tokens, that remediation could split into its own
  cycle — see §4.2 for the verdict (no split needed).

---

## §3 Per-item design (cosmetics SHORT)

### §3.1 P14.N1 — dashboard-table thumbnails

**Goal:** wire lazy-loaded candlestick thumbnails onto the dashboard tables, mirroring the SB4
journal-listing pattern (which shipped the VM→row-template lazy-load via a route serving SVG bytes).

**SB4 precedent (the pattern to reuse), verified:**
- Helper: `swing/web/trade_charts.py:88` `render_trade_window_thumbnail_svg(*, trade, fills, cfg)
  -> bytes | None` — no markers, no title (no mathtext risk), `None` on no-coverage, render-direct
  (no `chart_renders` write).
- Route: `swing/web/routes/journal.py:80` `GET /journal/trades/{trade_id}/thumbnail` — four
  contracts (200+SVG / 200+unavailable / 200+not-found+WARN / 200+busy+self-retry), a
  `BoundedSemaphore(2)` render cap (`:34`), distinct `Cache-Control` per contract, render exceptions
  isolated.
- Partial: `swing/web/templates/partials/journal_thumbnail.html.j2` — fragment root is `<svg>`/`<span>`
  (never bare `<tr>`, so the HTMX synthetic-table-wrap hazard does not apply).
- Row cell: `journal_row.html.j2:14-18` — a `<td>` with `hx-get=.../thumbnail`,
  `hx-trigger="revealed"`, `hx-swap="innerHTML"`, `hx-headers='{"HX-Request":"true"}'`.

**Critical finding — the two install targets are NOT symmetric:**
- **Open-positions rows** (`open_positions_row.html.j2`) carry `row.trade.id` — they ARE real
  `Trade` objects (with `current_stop`, `entry_date`, fills). `render_trade_window_thumbnail_svg`
  applies directly (open trade → `exit_date=None` → trailing window). The existing journal
  thumbnail route already renders any `trade_id`'s trade-window thumbnail, so an open-positions
  thumbnail is a **clean reuse** (reuse the journal route OR add a thin parallel
  `/trades/open/{trade_id}/thumbnail` route — recommend reuse to avoid a duplicate semaphore/route;
  see OQ-5).
- **Hyp-rec rows** (`hypothesis_recommendations_row.html.j2`) are ticker-keyed `rec` objects
  (`rec.ticker`, `rec.current_price`, `rec.pivot_price`) with **NO underlying `Trade`** — they are
  CANDIDATES that have not been entered (no entry_date, no fills, no trade window). The trade-window
  thumbnail helper does NOT apply. A hyp-rec thumbnail would need a **new ticker-window renderer**
  keyed by ticker (a recent-N-bar candidate chart), which is a re-implementation, not a reuse —
  **conflicts with L4.**

**Recommendation (HOLD for operator at OQ-5):** P14.N1 V1 = **open-positions thumbnails ONLY**
(clean reuse). DEFER hyp-rec thumbnails: they require a new ticker-window renderer + a ticker-keyed
route (out of the "reuse" envelope; arguably its own small slice or a banked follow-up). This keeps
the batch within L4 and avoids inventing a candidate-chart surface during a close-out polish pass.

**Open-positions V1 design (if approved):**
- VM: add a boolean/flag to `OpenPositionsRowVM` only if the template needs it; simplest is no VM
  change — the template emits the lazy `<td>` referencing `row.trade.id` directly (mirror
  `journal_row.html.j2`). Re-grep `swing/web/view_models/open_positions_row.py` at writing-plans.
- **Table-shape update (load-bearing — the new `<td>` changes the row 10→11 cells):** the
  open-positions table is a FIXED 10-column layout — `partials/open_positions.html.j2:8` has 10
  `<th>` (Ticker, Entry date, Entry price, Shares, Current stop, Last, Sector, Industry, Advisory,
  Actions) and `partials/open_positions_expanded.html.j2:27` hard-codes `<td colspan="10">` (with a
  comment at `:5` that it MUST match the compact row). Adding a thumbnail cell REQUIRES: (1) a
  `<th>Chart</th>` in the header (mirror the journal precedent `journal_table.html.j2:100`), (2) the
  expanded `colspan` 10→11 + its comment, and (3) a regression asserting the compact-row cell count
  == header `<th>` count == expanded `colspan`. Decide column position (recommend leading `Chart`
  column, mirroring journal).
- Route: reuse `GET /journal/trades/{trade_id}/thumbnail` (open trades have trade_ids; the helper
  handles open trades). If route-namespacing is a concern, add a thin
  `/trades/open/{trade_id}/thumbnail` that calls the SAME helper + SAME semaphore constant.
- No-coverage / no-open-trades behavior: helper returns `None` → "Chart unavailable." span (the
  partial's existing `else` branch); zero open trades → no rows → no thumbnails (no crash).
- **Gate precondition:** needs real open trades in the live DB to witness (S4).

### §3.2 A-1 — market_weather 200-day-MA fetch window

**Root cause:** the benchmark bars feeding `render_market_weather_svg` (`charts.py:777`, MA50+MA200
via `_render_candles_fig(ma_windows=(50,200))`) are fetched with `ohlcv_cache.get_or_fetch(...,
window_days=200)`. **`window_days=200` is CALENDAR days (~138 trading bars) — insufficient for a
200-trading-bar SMA200.** The MA200 line is computed on too few bars (or silently truncated),
producing an incomplete/absent 200-MA.

**Two live production sites (verified):**
- Pipeline: `swing/pipeline/runner.py:2761` `_bars_or_none(ticker)` →
  `ohlcv_cache.get_or_fetch(ticker=ticker, window_days=200)`; called for the benchmark at `:2884`
  (`bars = _bars_or_none(benchmark_ticker)`).
- Web refresh handler: `swing/web/routes/dashboard.py:94` `bars =
  ohlcv_cache.get_or_fetch(ticker=benchmark)` — passes NO `window_days`, so it uses
  `OhlcvCache.get_or_fetch`'s **default `window_days=180`** (`swing/web/ohlcv_cache.py:131`), i.e.
  ~124 trading bars — even shorter than the pipeline's 200. These bars feed
  `render_market_weather_svg(bars=bars, ...)` at `dashboard.py:141`.

**Fix:** widen the benchmark fetch window to **≥200 trading bars**. 200 trading bars ≈ 200 × 365/252
≈ **290 calendar days**; with margin use **`window_days=300`** (recommend a named constant, e.g.
`_MIN_CALENDAR_DAYS_FOR_MA200 = 300`, so the intent is self-documenting and shared). Apply at BOTH
sites — the pipeline `_bars_or_none` (replace the literal `200`) AND the dashboard refresh
(`dashboard.py:94`, which today passes NO `window_days` and inherits the 180 default → must pass the
constant explicitly). Widening is monotonic-safe (more bars only; downstream consumers slice — per
the "return full archive; consumers slice" gotcha).

**Regression (production-path, L6):** assert that ≥200 bars reach `render_market_weather_svg` via
the real fetch path (not a stub) at both the pipeline and refresh sites.

**JIT-path scope (OQ-6):** `swing/web/chart_jit.py:117` also uses `get_or_fetch(window_days=200)` for
the JIT cache-miss path. It serves `ticker_detail`/`watchlist_row`/`position_detail`/`market_weather`.
The `market_weather` JIT branch is **dead today** (the module comment at `:154-161` states no
production caller routes market_weather through the JIT — the two live sites compute the state
explicitly). **Recommendation:** widen the JIT constant too for uniformity + correctness of any
MA200-bearing surface (low risk, more bars only), flagged as belt-and-suspenders since the
market_weather JIT branch is currently unreached. HOLD at OQ-6 (market-weather sites only vs include
JIT).

### §3.3 A-2 — VCP contraction-label crowding (cosmetic; LIGHT)

`charts.py:836-841` (`_annotate_vcp`, in `render_theme2_annotated_svg`): the contraction loop emits
`f"contraction {i+1}: {depth:.1f}pct"` labels at `transAxes` `x=0.98, ha="right"`,
`y=0.92 - i*0.05` — the right-edge labels crowd the price y-axis tick column (mpf renders the price
axis on the right for candlesticks). **Fix:** reposition off the price-tick column — move to the
LEFT inset (`x=0.02, ha="left"`) OR shift the right anchor inward (`x≈0.74`). No mathtext
metacharacters (`pct` not `%`, `:` is safe in body text). A render-format-string test suffices; the
binding check is the operator's eyes at the gate (S6).

### §3.4 A-4 — `_bulz_*` → general rename (cosmetic; LIGHT)

Pure rename — the zones are a GENERAL open-long-position risk/reward feature (operator-confirmed at
the SB4 gate), NOT BULZ-special-cased. Verified anchors: `charts.py:632` `_bulz_target_price(trade)`
(called `:756`); `charts.py:725` `_draw_bulz_zones(...)` (called `:708`). (Note: `phase3e-todo.md`
`#5` line 166 cites stale `:609,701` — the verified lines are `:632/:725`; the §0.5 brief anchors
are correct.) Rename to general names (e.g. `_rr_target_price` / `_draw_risk_reward_zones`); update
all comments + WARN-log text ("skipping BULZ risk zone" → "skipping risk zone"). Grep ALL `_bulz` /
`bulz` tokens across `swing/` + `tests/` and rename atomically — behavior-neutral; tests stay green.

### §3.5 A-6 — process-grade-trend dark-mode chart (cosmetic; LIGHT)

`swing/web/templates/metrics/process_grade_trend.html.j2:39-60`. Two distinct SVG-default failures
(both fixed by the same CSS rule):
- the per-trade `<circle ... class="process-grade-marker">` (`:40-49`) has NO explicit `fill=` →
  SVG initial `fill` is **black** → visible in light mode, INVISIBLE against the dark background
  (the dark-mode-only symptom that was reported);
- the per-metric `<polyline ... fill="none" stroke-width="1.5" ... class="process-grade-rolling-line
  metric-{name}">` (`:56-60`) has `stroke-width` but NO `stroke=` → SVG initial `stroke` is **`none`**
  (NOT black) → the rolling line is **invisible in BOTH themes** (it was never actually drawn). There
  is NO CSS rule anywhere for `.process-grade-rolling-line` / `.process-grade-marker`.

**Fix (CSS rule, recommend — OQ-7):** add to `swing/web/static/app.css` theme-aware stroke/fill via
the existing accent token (`--accent` = `#0066cc` light `:35` / `#6ab0ff` dark `:122`):
```css
.process-grade-rolling-line { stroke: var(--accent); }
.process-grade-marker { fill: var(--accent); }
```
This resolves per theme automatically (no template edit needed). Mirrors the SB5 overview sparkline
precedent (`app.css:331` `.metrics-card__sparkline { color: var(--accent); }` +
`index.html.j2:34` `stroke="currentColor"`). CSS-rule preferred over inline `stroke=` so light+dark
both resolve via tokens. V1 single accent color is acceptable; per-series palette (the
`metric-{name}` classes) is a V2 candidate. Binding check: operator views `/metrics/process-grade-trend`
in DARK mode at the gate (S6).

---

## §4 A-7 — Schwab web badge design-vs-wiring investigation (THE deep section)

### §4.0 Symptom

The topbar checker-health badge is invisible in normal browser use. `base.html.j2:81-85` renders the
badge inside `{% if vm.schwab_checker_badge %}`; when the VM is `None` the badge silently disappears.
`build_schwab_checker_badge(cfg)` (`schwab_checker_badge.py:30`) returns `None` whenever
`read_liveness_sidecar(...)` is `None` (`:42-43`) — i.e. whenever no liveness sidecar file exists.
**NET: the badge vanishes exactly when Schwab is DOWN, defeating its purpose.**

### §4.1 Question (i) — DESIGN: render a visible UNKNOWN instead of hiding

The infrastructure to render UNKNOWN **already exists and is currently unreachable from the web path:**
- `evaluate_liveness_state(None, now_ts=...)` returns `("UNKNOWN", "web server not running, or
  pre-N7 build")` (`checker_resilience.py:228-229`).
- `read_liveness_sidecar`'s own comment (`:188-190`) says a non-/absent-dict result means "caller
  renders UNKNOWN."
- `_BADGE_MAP["UNKNOWN"] = ("Schwab?", "warn")` (`schwab_checker_badge.py:26`) exists.

But `build_schwab_checker_badge` returns `None` at `:42-43` **before** ever calling the state
machine, so the UNKNOWN branch is dead from the web side. The SB5.5 ruling was "UNKNOWN is
CLI-only by design" — which predates the operator discovering the badge vanishes when most needed.

**Fix (≈3-line web-VM change):** pass `data` through to `evaluate_liveness_state` regardless of
`None`, then map the resulting state through `_BADGE_MAP`. Concretely, replace the early
`if data is None: return None` with calling `evaluate_liveness_state(data, ...)` (the state machine
already handles `data is None` → UNKNOWN) and rendering the badge. The `cfg is None → return None`
guard (`:38-39`, render-safe for cfg-less callers / broad VM population) **stays** — the badge is
truly hidden only when there is no `Config` at all.

**The decided design (the deliverable; OQ-1 is operator RATIFICATION, not an open choice).** The
badge appears in the topbar of EVERY page (it is populated across all base-layout VMs). For an
operator who does NOT use Schwab (sandbox / no creds / ladder disabled), a permanent `Schwab?` warn
badge would be misleading noise — Schwab is not expected, so "unknown health" is "n/a," not a
warning. Therefore the V1 design is: **render the UNKNOWN (`Schwab?`, warn) badge when Schwab
checker health is EXPECTED and no usable sidecar exists; otherwise return `None` (hide).**

**The "Schwab is expected" predicate = `_is_ladder_active(cfg)`** (`marketdata_ladder.py:221-236`:
`environment == "production" AND marketdata_ladder_enabled`). This is the EXACT gate that decides
whether the checker is installed at all (`_construct_web_schwab_client` →
`_install_web_marketdata_caches` install the checker only when `_is_ladder_active`), so it is the
precisely-correct "checker is expected to be running" signal — a production-but-ladder-disabled
config gets no checker AND no noisy badge. `_is_ladder_active` is a **pure config read** (env +
enabled flag; NO API call, NO client construction, NO token inspection) → L3-safe. Concretely,
`build_schwab_checker_badge` becomes: `if cfg is None: return None` (unchanged); `if not
_is_ladder_active(cfg): return None`; else `state, reason = evaluate_liveness_state(data,
now_ts=...)` where `data = read_liveness_sidecar(...)` (which is `None` when absent → UNKNOWN), then
map through `_BADGE_MAP`. **Pure web-VM change; L3 green (no Schwab API call).**

*(Operator alternative at OQ-1, one-line difference: blanket always-render UNKNOWN whenever `cfg`
present and no sidecar — simpler, but lights a perpetual warn badge in sandbox/non-Schwab sessions.
Recommend the `_is_ladder_active`-gated design above.)*

**Reason-text refinement (recommend, low cost):** when `cfg` is present + production + no sidecar,
the state machine's hardcoded UNKNOWN reason ("web server not running, or pre-N7 build") is now
**misleading** — the web server IS running; the real reason is "Schwab client unavailable (no
checker running — check credentials/tokens)." The badge VM should supply a more accurate `title` in
the no-sidecar-but-expected case (the state stays UNKNOWN/warn; only the hover text improves). ASCII
only (L7).

### §4.2 Question (ii) — WIRING: should the checker be running under valid production tokens?

**Investigation (traced from the lifespan to the sidecar write):**

1. `swing/web/app.py:406-407` — in `create_app(...)` state construction (after
   `app.state.ohlcv_cache = OhlcvCache(cfg)`), NOT inside the async lifespan function:
   `app.state.schwab_client = _install_web_marketdata_caches(cfg, ...)`.
2. `_install_web_marketdata_caches` (`:251`) → `_construct_web_schwab_client(cfg)` (`:258`); if that
   returns `None`, returns early (yfinance-only; **no checker, no sidecar**).
3. `_construct_web_schwab_client` (`:148`) is gated **FIRST** on `_is_ladder_active(cfg)`
   (`marketdata_ladder.py:221-236` → `env == "production" AND marketdata_ladder_enabled`); returns
   `None` for sandbox/test/disabled. Then it resolves credentials (`None` on
   `SchwabConfigMissingError` or missing creds) and calls `construct_authenticated_client(...)`,
   returning `None` on ANY construction exception (graceful-degradation boundary).
4. Only when a non-`None` client is returned does `_install_web_marketdata_caches` (`:262-274`)
   install the resilient checker AND call `client.tokens.update_tokens()` to **seed** one refresh
   (origin='seed' → `record_tick("seed")` → `write=True` → **sidecar written synchronously before
   serving**).

**Verdict:** **There is NO checker-non-start bug under VALID production tokens.** When
`_construct_web_schwab_client` succeeds (production + ladder enabled + valid creds + constructible
tokens), the checker installs, the seed runs synchronously during lifespan startup, and the sidecar
is written before the first request is served → the badge renders STARTING then ALIVE. The
operator-reported "no badge" is the **by-design hide manifesting**, and it happens in exactly three
cases:
- **sandbox / ladder disabled / no creds** — no client by design (Schwab not in use); and
- **production + creds present but DEGRADED tokens** (e.g. expired 7-day refresh token →
  `construct_authenticated_client` raises → returns `None`) — **the operator-reported-compatible
  (likely) case**: the client cannot construct, so no checker runs, so no sidecar, so (today) no
  badge. (The code proves construction-failure → no sidecar; it does not by itself prove the
  operator's live case was specifically expired tokens — that is the most likely fit.)

So question (ii) resolves to "working as intended; the checker correctly does not run when the
client cannot construct — but that failure is currently SILENT in the UI." The fix is question (i):
**render UNKNOWN so the silent failure becomes visible.** **No A-7-wiring remediation cycle-split is
needed** (L8 contingency does not fire). The DESIGN fix (i) fully addresses the symptom.

**Secondary observation (NOT a new feature; flag only):** the degraded-token case (production +
creds + expired refresh) is logged only as a `log.warning` at `app.py:178-182`. The UNKNOWN badge
(question i) is the right surface for it. A future enhancement (Phase 15, with the schwabdev v3
upgrade that obviates P14.N7) could distinguish "checker construction failed (tokens?)" from "no
checker (not configured)" more granularly — but V1 should NOT add that; the UNKNOWN badge + improved
reason text is sufficient and stays within L3/L5.

### §4.3 The SB5.5-seeded-gate caveat (the lesson A-7 proves)

The SB5.5 S6 gate witnessed the badge ONLY via orchestrator-SEEDED sidecars (cleaned up post-gate),
which MASKED the live no-checker-no-badge behavior (`feedback_seeded_gate_masks_default_state`).
A-7's own gate (S7) MUST witness the **UNSEEDED** state: with NO sidecar present, the topbar shows
the `Schwab?` UNKNOWN (warn) badge instead of nothing. A-7's regression test asserts the badge
renders UNKNOWN when no sidecar exists (the exact regression the SB5.5 seeded gate missed), via the
real `build_schwab_checker_badge` derivation path (L6).

---

## §5 Group-(a) minors enumeration (operator triages IN/OUT — OQ-4)

Sources: `phase3e-todo.md` `#5` line 169 + the SB1 executing-plans return report §2 + the cross-SB
flake note. One paragraph each; the brainstorm does NOT design these deeply.

| ID | Trigger | Proposed fix | Source | Recommend |
|----|---------|--------------|--------|-----------|
| C-1 | `DailyManagementTileVM` PROVISIONAL flag defaults `=True` (candidate anchors `view_models/trades.py:2153`, `view_models/metrics/shared.py:142`) | flip to `False` or make the field required | SB1 | IN (1-line) |
| C-2 | daily-management tooltip "covers today" is misleading | "covers today" → "covers this row's session date" | SB1 | IN (text) |
| C-3 | backfill CLI artifact-write `OSError` surfaces as a raw traceback | wrap to `click.ClickException` (CLI-boundary discipline) | SB1 | IN (small) |
| C-5 | `BEGIN IMMEDIATE` ordering regression test does not assert lock-vs-SELECT/UPDATE order | strengthen the test to assert ordering | SB1 | IN (test) |
| C-6 | backfill apply-path write-lock held during the restore-artifact filesystem write | narrow the write-lock so it is NOT held during the FS write | SB1 | IN (small, but touches tx discipline — review carefully) |
| C-19 | `test_ohlcv_reader_re_export_identity` xdist co-residency flake (passes in isolation; `tests/research/test_pattern_cohort_evaluator_reader.py`) | harden via `@pytest.mark.xdist_group` (or serialize) | cross-SB flake | IN (test) |

**Recommendation:** all six are small and in-Phase-14-scope; recommend including C-1/C-2/C-3/C-5/C-19
(trivial) and reviewing C-6 carefully (it touches transaction/lock discipline — verify it does not
reopen a TOCTOU the original lock closed; if risk surfaces, defer C-6 to its own follow-up). Operator
triages the final IN/OUT set at OQ-4.

---

## §6 Module touch list (per item)

- **P14.N1 (open-positions V1):** `swing/web/templates/partials/open_positions_row.html.j2` (add the
  lazy `<td>`); `swing/web/templates/partials/open_positions.html.j2` (header `<th>Chart</th>`);
  `swing/web/templates/partials/open_positions_expanded.html.j2` (`colspan` 10→11 + comment); reuse
  `swing/web/routes/journal.py` thumbnail route (or thin new route under
  `routes/trades.py`/`routes/dashboard.py`); `swing/web/trade_charts.py` (unchanged — reuse helper);
  open-positions VM only if a flag is needed. Tests: `tests/web/`.
- **A-1:** `swing/pipeline/runner.py` (`_bars_or_none` literal 200 → constant);
  `swing/web/routes/dashboard.py:94` (benchmark `get_or_fetch` — pass the constant explicitly; today
  inherits the 180 default); a shared constant (e.g. in `swing/web/ohlcv_cache.py` or a charts
  module); optionally `swing/web/chart_jit.py:117` (OQ-6). Tests: `tests/pipeline/` + `tests/web/`.
- **A-2:** `swing/web/charts.py` (`_annotate_vcp`). Tests: `tests/web/` (render-format-string).
- **A-4:** `swing/web/charts.py` (rename) + every `_bulz`/`bulz` reference in `swing/` + `tests/`.
- **A-6:** `swing/web/static/app.css` (CSS rules). Optional: the template if inline `currentColor`
  chosen (OQ-7). Tests: a CSS-presence assertion is weak; the binding check is the operator gate.
- **A-7:** `swing/web/view_models/schwab_checker_badge.py` (the build function). No Schwab module
  touched. Tests: `tests/web/` (badge renders UNKNOWN when no sidecar — production-path).
- **group (a):** `swing/web/view_models/...` (C-1/C-2), `swing/cli_*`/backfill CLI (C-3),
  `tests/...` (C-5/C-19), backfill repo/service (C-6).

---

## §7 Schema impact

**NO schema change. v23 held.** Every item is cosmetic / wiring / render / test. No new migration,
no `EXPECTED_SCHEMA_VERSION` bump (stays 23 at `swing/data/db.py:51`). Confirmed across ALL items —
including A-7, which is a pure web-VM change (reads the existing ephemeral sidecar file, not the DB).
S2 asserts v23 + NO migration.

---

## §8 L2-LOCK analysis (A-7; zero new call sites)

A-7 is the only Schwab-touching item. The fix (render UNKNOWN instead of hiding) modifies
`build_schwab_checker_badge`, which calls `read_liveness_sidecar` + `evaluate_liveness_state` +
`_BADGE_MAP` — all pure file-read / pure-function helpers — plus the new `_is_ladder_active(cfg)`
gate, which is a **pure config read** (`marketdata_ladder.py:221-236`: env + `marketdata_ladder_enabled`;
NO API call, NO client construction). It adds **ZERO new `schwabdev.Client.*` call sites** and no
new client-construction path. The reason-text refinement is string formatting.
`tests/integration/test_l2_lock_source_grep.py` (baseline `bf7e071`) stays GREEN. S3 asserts this.

---

## §9 Sub-bundle decomposition recommendation (OQ-3)

**Recommend ONE executing-plans bundle with the following slices** (serial within the bundle; the
A-7 slice first as the highest-value + the only investigation-bearing item):

1. **Slice A — A-7 badge** (the substantive design fix; production-path test for the UNSEEDED
   UNKNOWN render; S3/S7 gate).
2. **Slice B — P14.N1 open-positions thumbnails** (reuse the SB4 pattern; S4 gate). Hyp-rec deferred
   per §3.1/OQ-5.
3. **Slice C — A-1 market_weather fetch-window** (the ≥200-bar widening + regression; S5 gate).
4. **Slice D — cosmetics A-2 + A-4 + A-6** (label reposition + rename + dark-mode CSS; S6 gate).
5. **Slice E — group-(a)** (the operator-triaged subset; mechanical gate).

**A-7-split contingency (L8):** the §4.2 wiring verdict found NO real checker-non-start bug under
valid tokens, so **A-7 does NOT split into its own cycle** — it stays Slice A. (If the operator's
live production session at the S7 gate reveals the checker fails to start even under valid tokens —
contradicting the static trace — that would re-open the split; not expected.)

Single Codex chain at each phase (OQ-8; orchestrator discretion, recommend single).

---

## §10 Test + gate strategy (production-path; UNSEEDED-state witness)

**Mechanical (S1-S3, S8):**
- **S1** `python -m pytest -m "not slow" -q` green + `ruff check swing/` clean.
- **S2** schema unchanged (assert v23; NO migration).
- **S3** `tests/integration/test_l2_lock_source_grep.py` green (A-7 adds no `schwabdev.Client.*` site).
- **S8** trailers `[]`; ZERO Co-Authored-By.

**Production-path tests (L6 / #15):**
- P14.N1: a test driving the real route + the real `render_trade_window_thumbnail_svg` derivation
  (open trade present → SVG bytes; no-coverage → unavailable), NOT a stub. PLUS a column-count
  alignment regression (compact-row cells == header `<th>` == expanded `colspan`).
- A-1: assert ≥200 bars reach `render_market_weather_svg` via the real `get_or_fetch` path at BOTH
  sites (the pipeline `_bars_or_none` and the dashboard refresh `dashboard.py:94`).
- **A-7 (the regression the SB5.5 seeded gate missed) — at TWO levels:** (1) a VM-level test that
  `build_schwab_checker_badge` returns a VM with `state="UNKNOWN"`, `label="Schwab?"`,
  `css_class="warn"` when **no sidecar exists** under a production+ladder-enabled cfg; AND (2) — the
  binding one — a **TestClient route test** (production+ladder-enabled cfg, NO seeded sidecar) that
  asserts the RENDERED topbar HTML contains `schwab-health-badge` + `Schwab?` + the warn class. The
  observed bug is the topbar disappearing through `base.html.j2`'s `{% if vm.schwab_checker_badge %}`
  guard, which a VM-only test cannot catch (#15 production-path discipline). Also assert the badge is
  ABSENT (VM `None`) under a sandbox/ladder-disabled cfg (the `_is_ladder_active` guard → no
  sandbox noise).

**Operator-witnessed browser gate (Q6; UNSEEDED/default-state witness):**
- **S4 (P14.N1)** open-positions table thumbnails render with real open trades; no-coverage rows
  degrade cleanly.
- **S5 (A-1)** the market-weather widget's 200-MA renders (full line).
- **S6 (A-2/A-4/A-6)** VCP labels uncrowded; the rename is behavior-neutral (tests green); the
  process-grade-trend chart visible in DARK mode.
- **S7 (A-7 — the default-state witness)** operator browser with **NO seeded sidecar**: the topbar
  shows the `Schwab?` UNKNOWN (warn) badge instead of nothing. (Optional/feasibility-gated: if the
  operator has a live production session with valid tokens, confirm the badge shows ALIVE/STARTING —
  validating the §4.2 wiring verdict end-to-end.)

---

## §11 V1 simplifications + V2 candidates

**V1 simplifications:**
- P14.N1 = open-positions ONLY (hyp-rec deferred — no Trade, needs a new renderer).
- A-7 = render UNKNOWN + improved reason text; NO new granular client-failure taxonomy.
- A-6 = single accent color for all series (not a per-series palette).
- A-1 = a single calendar-day constant (≥300) — no exchange-calendar-aware exact-bar computation.

**V2 candidates:**
- Hyp-rec (candidate) thumbnails via a ticker-window renderer keyed by ticker.
- A-6 per-series color palette (the `metric-{name}` classes already exist).
- A-7: granular "checker construction failed (tokens) vs not configured" distinction (Phase 15, with
  the schwabdev v3 upgrade that deletes P14.N7).
- A-1: an exchange-calendar-aware "fetch exactly N trading bars" helper (vs the calendar-day
  approximation).

---

## §12 Operator decision items (OQs — triaged at writing-plans dispatch)

1. **OQ-1 (A-7 design RATIFICATION) — CENTRAL:** the spec DECIDES the design (§4.1): render the
   UNKNOWN (`Schwab?`, warn) badge when Schwab is expected, gated on **`_is_ladder_active(cfg)`**
   (production AND ladder enabled — the exact "checker is expected" predicate), else hide. Operator
   ratifies, or chooses the one-line alternative (blanket always-render whenever cfg present + no
   sidecar). Plus the reason-text refinement (recommend yes). This replaces the SB5.5 "UNKNOWN is
   CLI-only" ruling, which predates the operator discovering the badge vanishes when most needed.
2. **OQ-2 (A-7 wiring verdict):** the §4.2 trace concludes there is **no real checker-non-start bug
   under valid tokens** — no-badge is the by-design hide manifesting under degraded tokens / failed
   client construction. Operator confirms the verdict + that A-7 does NOT split into its own cycle.
3. **OQ-3 (batch decomposition):** ONE bundle, slices A-7 / P14.N1 / A-1 / cosmetics / group-(a)
   (recommend). Confirm.
4. **OQ-4 (group-(a) triage):** which of C-1/C-2/C-3/C-5/C-6/C-19 are IN. Recommend all but review
   C-6 (tx-lock) carefully.
5. **OQ-5 (P14.N1 scope):** **Recommend open-positions ONLY for V1; defer hyp-rec** (no Trade → would
   re-implement a ticker-window renderer, conflicts L4). Confirm. Also: reuse the journal thumbnail
   route vs add a thin parallel route (recommend reuse).
6. **OQ-6 (A-1 JIT-path scope):** widen `chart_jit.py:117 window_days=200` too (recommend, uniformity)
   vs market-weather sites only. Note the market_weather JIT branch is dead today. (Both live sites
   are widened regardless: pipeline `_bars_or_none` and the dashboard refresh `dashboard.py:94`,
   which currently inherits the 180 default.)
7. **OQ-7 (A-6 mechanism):** CSS rule (recommend) vs inline `stroke=`/`currentColor`.
8. **OQ-8 (Codex chain count at writing-plans/executing-plans):** single chain (recommend).

---

## §13 Cumulative discipline compliance

- **Web/HTMX gotchas:** P14.N1's lazy partial keeps the fragment root `<svg>`/`<span>` (no bare
  `<tr>` → no synthetic-table-wrap); embedded HTMX cell carries `hx-headers HX-Request`; reuses the
  shared partial (no OOB hand-duplication drift).
- **Matplotlib-mathtext (#):** A-2 label text + the thumbnail (no title) carry no `$`/`^`/`_`; A-6 is
  CSS/SVG (no matplotlib).
- **base.html.j2 shared-VM-field hazard:** A-7 does NOT add a new `vm.*` field — `schwab_checker_badge`
  already exists on all base-layout VMs; the change only alters whether it is `None` vs a VM.
- **#15 production-path tests:** P14.N1/A-1/A-7 tests hit the real derivation path (L6).
- **#16/#32 ASCII:** A-7 badge/title text + C-2/C-3 CLI text stay ASCII.
- **L2-LOCK + redaction:** A-7 adds no Schwab call site; no `setLogRecordFactory` change.
- **No Co-Authored-By; final `-m` paragraph plain prose** (`feedback_commit_message_trailer_parse_hazard`).
- **`feedback_seeded_gate_masks_default_state`:** the S7 gate + A-7 test witness the UNSEEDED state.

---

## §14 Phase 14 close-out position note

This batch is the FIRST item of the Phase 14 close-out tail proper (SB1–SB5.5 all SHIPPED
end-to-end). After it ships: **B-7 (operator failure-mode classification, the final touch — NEXT
cycle, may add a nullable review column → v24, OUT of this batch) → Phase 14 close-out review (Sec
9.1 Q6: all sub-bundles merged + operator browser-witnessed cross-sub-bundle integration) → CLAUDE.md
"Phase 14 CLOSED" at v23.** The schwabdev v2.5.1→3.0.5 upgrade (which deletes P14.N7's checker
guard) remains a Phase 15 item. This batch holds v23, holds L2-LOCK, and stays read-mostly.
