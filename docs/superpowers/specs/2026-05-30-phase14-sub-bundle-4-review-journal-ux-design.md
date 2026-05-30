# Phase 14 Sub-bundle 4 -- Review + Journal UX -- Design Spec

**Status:** brainstorming draft (pre-Codex). Authored 2026-05-30 from
`docs/phase14-sub-bundle-4-review-journal-ux-brainstorming-dispatch-brief.md`.
Branch `phase14-sub-bundle-4-review-journal-ux-brainstorming` off main HEAD
`f4fe825`. Schema substrate v23 (LOCKED). Single Codex chain at end (Sec 9.1
Q7; pure UX/wiring).

**Scope (L1):** CR.1 (closeout-review surface exit-data + chart-snapshot
enhancement) + P14.N6 (journal browse-the-database redesign) + the in-scope
BULZ row-expand wiring (SB3 banked follow-up #1). Read-mostly over
already-shipped data; **no new trade-mutation path; no schema change** (verdict
in §11).

---

## §1 Architecture overview

### §1.1 The three deliverables and their shared spine

All three surfaces consume **already-shipped data** (trades, fills,
review_log, trade_events, daily_management_records, candidates,
pattern_evaluations) and the **SB3 candlestick renderers** in
`swing/web/charts.py`. None requires a new write path or a new analytical
artifact. The unifying technical spine is a single new **read-only,
trade-window chart helper** (§4.2) that CR.1 and P14.N6's drill-down both
reuse, plus a single new **per-trade chronology assembly** (§5.4) that only
the drill-down needs.

| Deliverable | Surface(s) | New code center of gravity | Chart source |
|---|---|---|---|
| CR.1 | `GET /trades/{id}/review` (EXISTS) | `ReviewVM` field delta + `review.html.j2` block | trade-window render-direct (§4.2) |
| P14.N6 listing | `GET /journal` (EXISTS, minimal) | `JournalVM` enrichment + redesigned `journal.html.j2` + new row partial | lazy-load candlestick thumbnail (§5.3) |
| P14.N6 drill-down | `GET /journal/trades/{id}` (NEW route) | new VM + chronology helper + template | trade-window render-direct (§4.2) |
| BULZ row-expand | `GET /trades/open/{id}/expand` (EXISTS) | `OpenPositionsExpandedVM` field + template swap | **cached** `position_detail` SVG (§6) |

### §1.2 The central technical finding (drives §4, §7, §11)

The naive plan -- "reuse the cached `position_detail` SVG for the review and
journal charts" -- is **wrong for closed trades** on two independent axes,
both verified in production code at draft time:

1. **Window anchoring.** `OhlcvCache.get_or_fetch(ticker, window_days=180)`
   (`swing/web/ohlcv_cache.py:131`) is *backward-looking, anchored on
   `last_completed_session(now())`* (docstring lines 143-146). The
   `position_detail` JIT (`swing/web/chart_jit.py:117`) calls it with
   `window_days=200`. So the rendered window always ends at *today*, never at
   the trade's exit date. For a trade closed more than ~200 calendar days ago
   the chart contains **none of the trade's bars**; the fill markers clamp to
   the last bar (`_x_for_fill_date` nearest-forward clamp,
   `swing/web/charts.py`) and render a misleading chart. This is the #29
   historical-depth / window-anchoring failure mode in full.
2. **Cache-key collision.** The `position_detail` cache key is
   `(ticker, surface='position_detail', pipeline_run_id IS NULL)` -- *ticker
   only, run-agnostic* (`get_cached_chart_svg` lines 170-197; v20 §3.2 LOCK).
   There is exactly one cached `position_detail` row per ticker. A ticker that
   was traded, closed, and re-entered has two `Trade` rows but one cache slot;
   serving the journal drill-down for the *old* closed trade from that slot
   shows the *current* open trade's chart (different fills, different stop).

**Resolution (no schema):** closed-trade charts (CR.1, journal drill-down,
journal thumbnails) **reuse the SB3 _renderer_ `render_position_detail_svg`
(and the shared `_render_candles_fig` helper), NOT the `chart_renders`
_cache_.** They render direct over a **trade-window archive slice** keyed
conceptually by `trade_id` (immutable closed trades), with an optional
in-process memo. The `position_detail` *cache* stays the property of the
pipeline/dashboard surfaces, where it is correct (open tickers, current run,
trailing window). The **BULZ row-expand (open trades only) keeps using the
cache** because for an open position the trailing-today window and the
ticker-only key are both correct. This asymmetry -- *open trades use the
cache, closed trades render-direct* -- is the load-bearing decision of the
sub-bundle.

### §1.3 Brief-vs-production corrections (Expansion #2 / #4; verified at f4fe825)

1. **CR.1 form already exists (CONFIRMED).** `GET`/`POST /trades/{id}/review`
   at `swing/web/routes/trades.py:2589`/`:2609`; `build_review_vm` +
   `ReviewVM` at `swing/web/view_models/trades.py:1183`/`:1106`; templates
   `review.html.j2` + `partials/review_form.html.j2`. CR.1 is the
   exit-data + chart-snapshot **delta**, not a greenfield form. ReviewVM
   already carries `actual_realized_R_effective`, `mfe_pct`, `mae_pct`,
   priors. It does **not** carry exit_price/exit_date or any chart bytes ->
   that is the delta.
2. **`Trade` has no `exit_price`/`exit_date` column (CORRECTION).** Exit data
   is derived from non-entry `fills` (`swing/data/repos/fills.py`
   `list_fills_for_trade:168`). `_fill_to_exit_like` + the existing
   `compute_actual_realized_R_effective` path already consume them. CR.1's
   "exit price" is a **derivation**, not a column read.
3. **The `position_detail` JIT window is anchored on today, not the trade
   (CORRECTION to the brief's "reuse the cached position_detail SVG"
   recommendation).** See §1.2. Reuse the renderer, not the cache, for closed
   trades.
4. **Entry-flag column sources (#4 verification, partial).** chart shapes:
   `Trade.chart_pattern_algo` / `Trade.chart_pattern_operator`
   (`models.py:206-208`) + `pattern_evaluations.pattern_class` via
   `Trade.pattern_evaluation_id` (`models.py:265`; `pattern_class` CHECK enum
   = vcp/flat_base/cup_with_handle/high_tight_flag/double_bottom_w at
   `0020_*.sql`). A+ tier: `candidates.bucket`
   (aplus/watch/skip/error/excluded, `0001_phase1_initial.sql:28`) via
   `Trade.candidate_id` (`models.py:264`). Hypothesis: `Trade.hypothesis_label`
   free-text (`models.py:203`). **The "hyp-rec (and which)" linkage has NO
   direct FK on `trades`** -- see OQ-4 (§13). `planned_target_R`
   (`models.py:256`) drives the BULZ target via `_bulz_target_price`
   (`charts.py:609`).
5. **A `journal_trade_chart` cache surface (the brief's hypothetical v24
   trigger) would need a new `trade_id` COLUMN + partial unique index, not
   merely a CHECK-enum value** -- because closed trades are neither run-bound
   nor safely ticker-keyed. That is heavier than the brief assumed and is
   unnecessary under the render-direct resolution. Schema stays v23 (§11).

---

## §2 Pre-locked operator decisions

### §2.1 Sec 9.1 commissioning LOCKs (binding for all Phase 14 sub-bundles)

- **Q1** sequencing: data-wiring (SHIPPED) -> temporal log (SHIPPED) ->
  chart-surface uniformity (SHIPPED) -> **review + journal UX (THIS)** ->
  metrics overview. Confirmed.
- **Q2** execution = SERIAL. Confirmed.
- **Q5** graphics = matplotlib SVG. **No JS charting library.** Every chart /
  thumbnail in this sub-bundle uses the SB3 mplfinance renderers. Confirmed.
- **Q6** close-out = operator browser-witnessed verification at merge.
  Confirmed; gate ladder in §10.
- **Q7** Codex chain count = orchestrator discretion; **SINGLE chain** for
  this brainstorming (pure UX/wiring). Reconsider at writing-plans only if the
  chronology assembly (§5.4) is judged a substantive analytical artifact
  (recommend: still single -- it is a read-only merge, not analysis).

### §2.2 Operator decisions captured / assumed at this brainstorming (2026-05-30)

These are the brainstorm's own resolutions of the brief's §3 OQs. They are
**recommendations for operator triage at writing-plans dispatch**, NOT
operator-confirmed locks (no live operator in this dispatch):

- **OD-1 (chart surface):** reuse SB3 renderer, render-direct, no cache, no
  schema for closed-trade charts (§1.2). Open-trade BULZ row-expand reuses the
  cache.
- **OD-2 (thumbnails):** candlestick (not the watchlist line thumbnail),
  lazy-loaded per row (§5.3).
- **OD-3 (thumbnail breadth):** journal listing ONLY in this sub-bundle. The
  broader dashboard open-positions / hyp-rec thumbnail wiring (P14.N1) stays
  banked (OQ-3, §13).
- **OD-4 (total_risk):** dollar risk at open = `initial_shares *
  (entry_price - initial_stop)`; capital-floor memory applies only if a
  %-of-capital column is added (OQ-6).
- **OD-5 (decomposition):** 6 writing-plans slices (§9).
- **OD-6 (banked rider #2):** bank the market_weather 200MA fetch-window fix
  standalone; do NOT fold into SB4 (L8).

### §2.3 Sub-bundle 4 phase LOCKs (this brief, restated)

- **L1** scope = CR.1 + P14.N6 + BULZ row-expand wiring ONLY.
- **L2** read-mostly; NO new trade-mutation path. The review POST +
  `complete_trade_review` (`swing/trades/review.py:550`) write contract is
  **unchanged**. Journal + drill-down + all charts perform NO trade-domain
  writes. Escalate if a trade write seems required (none does). **Scope
  clarification (Codex R1 M#1):** "read-mostly" governs the *trade domain*. The
  OHLCV archive (`read_or_fetch_archive` -> parquet) is the app's existing
  shared read-through cache, already exercised by every chart surface and the
  pipeline; SB4 chart helpers invoke it on the SAME terms (read existing;
  refresh on the existing weekly cadence; degrade to chart-unavailable on
  empty per F6). That archive I/O is **permitted and pre-existing**, not a new
  mutation path. SB4 writes ZERO new `chart_renders` rows (render-direct, §4.2)
  and ZERO trade/fill/review rows.
- **L3** no schema change expected; verdict v23-unchanged (§11). A v24 would
  only arise from a new chart cache surface, which §1.2 eliminates.
- **L4** HTMX browser-only failure-surface trinity applies to journal
  sort/filter/drill-down/thumbnail (§8).
- **L5** matplotlib visual-gate discipline; ASCII-only annotations; reuse SB3
  renderers, no candlestick re-implementation (§4, §10).
- **L6** L2 Schwab LOCK preserved; ZERO new `schwabdev.Client.*` call sites;
  source-grep test stays green. The Schwab daily-bar wiring (banked #4) stays
  OUT (§12).
- **L7** record the chart-access UX brief §2 reversal when the row-expand
  inlines the `position_detail` SVG (§6).
- **L8** market_weather 200MA fix banked standalone (OD-6).

---

## §3 Module touch list

**Read-only assemblies / VMs (new or extended):**
- `swing/web/view_models/trades.py` -- `ReviewVM` (+ exit-data fields +
  `position_chart_svg_bytes`); `build_review_vm` (derive exit legs + render
  closed-trade chart).
- `swing/web/view_models/journal.py` -- `JournalVM` (+ rich per-trade row
  list `rows: tuple[JournalRowVM, ...]`); `build_journal` (enrich each trade);
  NEW `JournalRowVM` dataclass; NEW `build_trade_drilldown_vm` +
  `TradeDrilldownVM`.
- NEW `swing/web/view_models/trade_chronology.py` (sibling-module strategy) --
  `TradeChronology`, `ChronologyEntry`, `build_trade_chronology(conn,
  trade_id)` (§5.4).
- `swing/web/view_models/open_positions_row.py` --
  `OpenPositionsExpandedVM` (+ `position_chart_svg_bytes`);
  `build_open_positions_expanded` (read the `position_detail` cache via the
  read-only `get_cached_chart_svg`, mirroring `build_trade_detail_vm`; no JIT,
  no write -- §6).

**Shared chart substrate (small carve-out, Codex R4 M#1):**
- `swing/web/charts.py` -- add a module-level **matplotlib render lock** at the
  shared render boundary (`_svg_bytes_from_fig` + the `mpf.plot`/`plt.subplots`
  sites) so EVERY web render path serializes (pyplot global-state safety, §4.2).
  This is the one in-scope edit to the SB3-created shared helper; it is a
  correctness fix SB4 owns because it introduces the high-concurrency rendering
  (the journal listing) that makes the latent hazard acute. No behavior change
  to existing renderers beyond serialization.

**Chart helper (new, read-only):**
- NEW `swing/web/trade_charts.py` (sibling to `charts.py`) --
  `render_trade_window_position_svg(...)` + `render_trade_window_thumbnail_svg(...)`
  + `_trade_window_bars(...)` (§4.2). Reuses `charts.render_position_detail_svg`
  and `charts._render_candles_fig`; NO candlestick re-implementation.

**Routes:**
- `swing/web/routes/journal.py` -- extend `GET /journal` (sort/filter query
  params); NEW `GET /journal/trades/{trade_id}` (drill-down); NEW
  `GET /journal/trades/{trade_id}/thumbnail` (lazy thumbnail fragment).
- `swing/web/routes/trades.py` -- `review_form_page` passes the new
  `ohlcv`/archive plumbing (already passes `ohlcv_cache`); `open_position_expand`
  unchanged signature (VM does the work).

**Templates:**
- `swing/web/templates/review.html.j2` + `partials/review_form.html.j2` --
  exit-data block + chart block.
- `swing/web/templates/journal.html.j2` -- full redesign (rich table).
- NEW `partials/journal_row.html.j2`, NEW `partials/journal_thumbnail.html.j2`,
  NEW `journal_trade_detail.html.j2`, NEW
  `partials/trade_chronology.html.j2`.
- `partials/open_positions_expanded.html.j2` -- swap legacy `<img>` for SVG.

**Repos consumed (read-only, no change):** `repos/fills.py`
(`list_fills_for_trade`, `list_all_fills`, `get_authoritative_entry_fill`);
`repos/trades.py` (`get_trade`, `list_open_trades`, `list_closed_trades`);
`repos/review_log.py`; `repos/chart_renders.py` (`get_cached_chart_svg`);
`data/ohlcv_archive.py` (`read_or_fetch_archive`); `trade_events` +
`daily_management_records` via inline SELECTs in the chronology helper.

**NO schema files touched.** `EXPECTED_SCHEMA_VERSION` stays 23
(`swing/data/db.py:51`). No `0024_*.sql`.

---

## §4 CR.1 design (exit data + chart snapshot)

### §4.1 Exit-data delta

CR.1 is a read-surface enrichment of the EXISTING review form. `build_review_vm`
already loads `non_entry_fills` (`trades.py:1232`). Add to `ReviewVM`:

- `exit_legs: tuple[ExitLegVM, ...]` -- per-leg `(action, fill_datetime[:10],
  price, quantity, reason)` from the non-entry fills (sorted by datetime ASC).
- `exit_price_vwap: float | None` -- share-weighted average exit price.
  **Exit-fill classification (Codex R1 M#4):** the reducing fills =
  `action in {exit, trim, stop}` (i.e. `action != 'entry'`); this matches the
  existing `build_review_vm` filter (`f.action != "entry"`, `trades.py:1232`)
  and the `_fill_to_exit_like` per-leg path. Quantities in the `fills` schema
  are positive magnitudes (V1 is **long-only** -- consistent with the BULZ
  long-only `_draw_bulz_zones` skip+WARN); VWAP = `sum(price*qty)/sum(qty)`
  over those fills, zero-qty fills skipped, `None` when the denominator is 0 or
  no reducing fill exists (defensive). Entry add-ons are excluded by the
  `action != 'entry'` filter. Shorts are explicitly out of V1 scope (escalate
  if a non-long trade appears). Mirrors `_compute_execution_price`'s
  execution-grain VWAP discipline.
- `exit_date_last: str | None` -- the final reducing fill's `fill_datetime[:10]`
  (date component). **(Codex R1 m#2)** this is the fill's recorded date, not a
  re-derived exchange session; after-hours / tz nuances are out of V1 scope
  (the fill datetime is taken as authoritative, matching every other
  fill-date consumer).
- `total_risk_dollars: float | None` -- the dollar risk taken at open (OD-4),
  display-only. **(Codex R1 M#5)** guarded, not a blind product: returns
  `initial_shares * (entry_price - initial_stop)` ONLY when `initial_stop` is
  present AND `entry_price > initial_stop` (valid long shape); otherwise `None`
  (template shows "n/a"). Never displays a negative or inverted risk. Long-only
  V1 (same invariant as the BULZ zones).

`actual_realized_R_effective` (final R) is ALREADY on the VM -- surface it
prominently in the exit block; no new computation.

All four are pure derivations inside the existing `with conn:` block in
`build_review_vm`; no new query against trade-mutation tables, no write.

**chart_renders write-contract precision (Codex R2 M#1 -- resolves an apparent
contradiction between R1 M#1 and R1 M#12).** The "ZERO new `chart_renders`
rows" claim is precise per surface class:
- **Closed-trade surfaces (CR.1 chart, journal thumbnail, journal drill-down):**
  render-direct; touch `chart_renders` not at all (zero reads, zero writes).
- **Open-position BULZ row-expand (§6):** reads the EXISTING `position_detail`
  cache via the SAME read-only call `build_trade_detail_vm` uses
  (`get_cached_chart_svg(conn, ticker=, surface='position_detail',
  pipeline_run_id=None)`, `trades.py:1771` -- verified read-only, NO JIT, NO
  write-through). SB4 adds no new surface enum, key, column, or migration, and
  the row-expand performs **ZERO `chart_renders` writes** -- it is purely a new
  *reader* of the cache the pipeline `_step_charts` already refreshes each run.
  So ALL of SB4 is write-free against `chart_renders`. (Correction to an
  earlier draft that implied a JIT write-through fallback: `build_trade_detail_vm`
  does not JIT; the row-expand mirrors that exactly.)

### §4.2 Chart snapshot -- the trade-window render-direct helper

NEW `swing/web/trade_charts.py`:

```
def _trade_window_bars(*, ticker, entry_date: date, exit_date: date | None,
                       cfg, pad_before_days=30, pad_after_days=10) -> pd.DataFrame | None:
    """Archive slice [entry_date - pad_before, (exit_date or today) + pad_after].
    Reads read_or_fetch_archive(ticker, end_date=window_end,
    cache_dir=cfg.paths.prices_cache_dir,
    archive_history_days=cfg.archive.archive_history_days) -> full archive
    rows <= end_date; then slices the lower bound locally (consumer-slices
    per the 'return FULL archive; consumers slice' gotcha). Returns None when
    the archive lacks coverage for the window (older than archive depth) or
    yfinance is empty (F6 transient -> None, never blank)."""

def render_trade_window_position_svg(*, trade, fills, cfg) -> bytes | None:
    """Full 800x500 candlestick trade chart. Reuses
    charts.render_position_detail_svg(ticker=, bars=<window>, trade=, fills=,
    current_stop=trade.current_stop). Returns None on no-coverage ->
    caller renders a chart-unavailable state (reuse the open_positions
    chart_reason pattern)."""

def render_trade_window_thumbnail_svg(*, trade, fills, cfg) -> bytes | None:
    """Small candlestick thumbnail via charts._render_candles_fig at thumbnail
    figsize (ma_windows=(10, 20)). Same window as the full chart. No
    fill markers (thumbnail). Returns None on no-coverage."""
```

**Archive depth is ample (mitigates #29):** `cfg.archive.archive_history_days
= 1260` (`swing/config.py:205`) -- ~1260 trading days (~5 calendar years). The
on-disk archive always extends to today (`read_or_fetch_archive` docstring:
the archive "always extends to `_last_completed_session_today()` regardless")
with ~5y of depth, so most recently-closed trades (held days-to-weeks, closed
within the last few years) have full window coverage. Trades older than the
archive depth degrade to a first-class chart-unavailable state (§4.2; NOT a
misleading clamped chart) -- and since a journal invites historical browsing,
that state is treated as a real surface, not an edge case (Codex R1 M#6). This
is precisely why render-direct over the archive (vs the trailing-200d
`position_detail` JIT) is both correct AND practical.

**Why render-direct, not cache:** §1.2. The helper is pure-read; **do NOT
write through to `chart_renders`** (would collide the ticker-keyed
`position_detail` slot).

**Memo freshness (Codex R1 M#3):** "closed trades are immutable" is only
*mostly* true -- a Phase 12 reconciliation correction, a fills repair, or a
re-review can mutate a closed trade's fills/stop after close. A cross-request
memo keyed by `trade_id` ALONE would then serve a stale chart. **Resolution
(R1 M#3 / R2 M#3) -- request-lifetime memo is the V1 DEFAULT.** The render
output depends on MANY fields (ticker, entry_date, entry_price, initial_stop,
current_stop, planned_target_R, and every fill's price/qty/action/datetime), so
any *partial* freshness token (e.g. `(trade_id, last_fill_at, current_stop)`)
risks missing a render-affecting change -- exactly the trap R2 M#3 flags.
Therefore V1 uses a **request-lifetime memo only** (a dict scoped to the single
request, deduping the rare case where one request renders the same trade's
chart twice; no cross-request retention -> ZERO cross-request staleness risk).
A cross-request memo is permitted ONLY with a *deterministic fingerprint over
ALL render-affecting trade + fill fields* (a cheap hash), never a partial
token. The spec forbids both a bare `trade_id` memo AND a partial-token memo.

**matplotlib renders MUST be serialized (Codex R3 M#2).** `swing/web/charts.py`
uses pyplot GLOBAL state (`matplotlib.pyplot as plt`, `mpf.plot(...)`,
`plt.subplots(...)`, `plt.close(fig)`) -- which is NOT thread-safe -- and there
is NO existing render lock today. A single concurrent chart request is a latent
risk already; the journal listing's up-to-`page_size` lazy thumbnail renders
make it acute. Resolution: SB4 introduces a **process-wide matplotlib render lock acquired
ONCE per render at a SINGLE outer boundary** -- each top-level `render_*_svg`
function (and the new `trade_charts.py` helpers) acquires the module-level lock
around its WHOLE body, exactly once, covering the `mpf.plot` / `plt.subplots` /
`_svg_bytes_from_fig` sequence. **(Codex R5 M#1)** the lock must NOT be acquired
at BOTH an inner `mpf.plot` site AND again at `_svg_bytes_from_fig` with a
non-reentrant `threading.Lock` -- that self-deadlocks a single render. The spec
mandates: ONE acquisition per render (outer boundary); if any nesting is
genuinely unavoidable, use `threading.RLock` (reentrant); and the writing-plans
slice adds a no-deadlock test that exercises EACH chart path under the lock.
The lock covers EVERY web renderer (existing + SB4), NOT only the SB4 paths. **(Codex R4 M#1):** the pyplot hazard is process-global, so
a lock that wrapped only SB4 renders would still let an existing render
(trade-detail JIT, watchlist thumbnail, weather) run concurrently with an SB4
render and corrupt pyplot state. Centralizing the lock at the shared boundary
makes EVERY web matplotlib render path acquire it with one change. This is a
small, deliberate carve-out into the SB3-created `charts.py` shared helper
(§3) -- justified because SB4 is the surface that introduces the high-concurrency
rendering that makes the pre-existing latent hazard acute, and the shared helper
is the correct single home. It simultaneously (a) fixes the pyplot
thread-safety hazard globally and (b) is the "explicit render-concurrency bound"
R2 M#2 called for. If writing-plans instead PROVES the renderers are fully
figure-local / Agg-safe (OO `Figure`/`FigureCanvasAgg`, no pyplot global state),
the lock may relax to a pure load bound -- but the pyplot evidence above says
assume serialize until proven otherwise.

**No-coverage is a first-class state (Codex R1 M#6):** a journal explicitly
invites historical browsing, so a trade older than the ~5y archive depth is NOT
a rare edge case to wave away. When `_trade_window_bars` returns `None`
(archive lacks the window, or yfinance empty), the surface renders an explicit
"chart unavailable -- trade predates the chart archive" state (reuse the
`chart_reason`/`chart_reason_message` pattern from `open_positions_expanded`),
and ALL non-chart data (rich row, entry flags, exit data, chronology) still
renders fully. The depth fact (~5y) explains why this state is uncommon in
practice; it does NOT excuse omitting the state. (The earlier "virtually every"
framing is corrected to: "most recently-closed trades have coverage; older
trades degrade cleanly to the unavailable state.")

**Window correctness for open trades:** when `exit_date is None` (open trade,
relevant only in the journal path, not CR.1 which is closed-only), the window
end is today -> the live trailing window. So the single helper is correct for
both states; CR.1 only ever calls it on closed trades.

### §4.3 ReviewVM chart field

The chart renders the candlesticks + the trade's fill markers (entry ^, exit v,
stop x) + current-stop line + BULZ risk/reward zones -- exactly what the
operator needs to "identify notes to add to the journal" (CR.1 framing).

**Render isolation + lazy-load (Codex R1 M#2 / m#7):** the review page is a
write-adjacent workflow (the POST submits the review); a slow/flaky matplotlib
render or archive fetch must NEVER degrade the form. Two protections, both
required:
1. **Failure isolation:** the chart render is wrapped so any exception /
   no-coverage returns `None` -> chart-unavailable state; the form ALWAYS
   renders. The chart is never on the form's critical path.
2. **Lazy-load (recommended V1):** rather than rendering synchronously inside
   `build_review_vm` (which would block the GET), the review page emits a
   placeholder cell that self-loads the chart via
   `GET /trades/{id}/review/chart` (`hx-trigger="load"`), identical to the
   journal thumbnail pattern (§5.3). This keeps the form instant and confines
   the render cost/failure to a separate request. The `ReviewVM` therefore does
   NOT need to carry chart bytes; it carries only the lazy-load target. (If the
   operator prefers the chart inline-at-render, the failure-isolation guard
   alone is the fallback -- but lazy-load is the recommended default for a
   write-adjacent page.)

**Lazy chart-route response contract (Codex R2 M#4 / m#3).** `GET
/trades/{id}/review/chart` (and the structurally-identical `GET
/journal/trades/{id}/thumbnail` + the drill-down chart fragment) share one
contract: (a) success -> `200` with the `<svg>` (the matplotlib-generated bytes
are the ONLY `| safe` content -- minor #3); (b) no-coverage / 404-trade /
render exception -> `200` with the chart-unavailable `<span>` fragment (NOT a
bare 4xx the HTMX swap renders as blank); (c) these GET fragments load via
`hx-trigger="load"` and carry `hx-headers='{"HX-Request":"true"}'` so
OriginGuard strict-mode does not 403 the lazy load (same as every other
embedded HTMX control, §8); (d) direct (non-HX) browser access returns the same
fragment harmlessly. **`Cache-Control` (m#3):** these endpoints serve trading
data -> set `private, max-age=<short>` (browser-private only; never a
shared/proxy cache). Low-risk on a single-operator localhost app, but specified
explicitly rather than left to framework default. **(Codex R3 m#1/m#2)** the
`200 + chart-unavailable` fallback must NOT hide regressions: every exception
fallback logs a structured WARNING with context (trade_id, ticker, window,
exception), and a missing-trade (404 row) is distinguished in BOTH the fragment
text ("trade not found" vs "chart unavailable") and the log, so broken
drill-down links remain detectable even though the browser-visible response
stays non-blank.

### §4.4 ASCII / mathtext (L5)

No new title/label strings beyond what `render_position_detail_svg` already
emits (ASCII-clean, verified SB3). The thumbnail renderer passes NO title
(thumbnails are unlabeled). `_assert_ascii_only` already guards the reused
renderer's labels.

---

## §5 P14.N6 design (browse-the-database journal)

### §5.1 Main listing -- rich rows

Redesign `journal.html.j2`'s trade table (currently 3 columns:
Ticker/Entry/Status, lines 36-43) into a rich, sortable/filterable table.
`build_journal` already loads `list_open_trades + list_closed_trades` and the
`_ExitShape` adapter. Build a per-trade `JournalRowVM`:

```
@dataclass(frozen=True)
class JournalRowVM:
    trade_id: int
    ticker: str
    entry_date: str
    state: str
    open_price: float            # trade.entry_price
    shares: int                  # trade.initial_shares
    total_risk_dollars: float    # initial_shares*(entry_price-initial_stop)
    closing_price: float | None  # VWAP exit (None for open trades)
    final_r: float | None        # compute_actual_realized_R_effective (None=open)
    # entry-time flags (all None-safe):
    chart_pattern: str | None    # chart_pattern_operator or _algo or pattern_evaluations.pattern_class
    aplus_bucket: str | None     # candidates.bucket via candidate_id
    hypothesis_label: str | None # trade.hypothesis_label
    has_hyprec_link: bool        # candidate_id is not None (see OQ-4 for "which")
```

`closing_price` + `final_r` reuse the SAME `_ExitShape` / VWAP /
`compute_actual_realized_R_effective` derivations as CR.1 (§4.1) -- factor a
shared `swing/trades/derived_metrics`-adjacent helper or call the review
helpers directly; do NOT duplicate the math (single source of math truth per
the existing `derived_metrics` discipline). **(Codex R2 m#2)** when a value is
unavailable (`total_risk_dollars` / `final_r` / `closing_price` is `None` --
open trade, missing stop, or unsupported short), the cell renders explicit text
("n/a", or "open" for an in-flight trade), never a blank that reads as zero or
an error.

`total_risk_dollars` reuses the guarded derivation from §4.1 (long-only,
None on invalid/missing stop). `open_price`/`shares` are direct trade columns.

Entry-flag joins: a single batched read of `candidates.bucket` /
`candidates.pattern_tag` (by the set of `candidate_id`s) and
`pattern_evaluations.pattern_class` (by the set of `pattern_evaluation_id`s)
inside the existing `with conn:` block -- avoid N+1 per-row queries.

**Pagination / windowing (Codex R1 M#7):** the listing MUST be paginated (V1
default page size ~50 rows; `page=` / `page_size=` query params validated
against a max). This bounds the per-page thumbnail render count (§5.3),
bounds the entry-flag join sizes, and keeps the table usable as the trade
history grows. The period filter already narrows the set; pagination is the
hard cap on top of it.

### §5.2 Database-browsing affordance -- sort + filter

The "browse the database" ask = a sortable + filterable table. V1 columns
sortable: entry_date, ticker, final_r, total_risk_dollars, state. Filters:
state, period (existing), has-A+ flag, chart-pattern class. **(Codex R1 m#10)**
the `state` filter values map directly to the `Trade.state` enum
(`entered`/`managing`/`partial_exited`/`closed`/`reviewed`) -- "reviewed" means
`state == 'reviewed'`. **(Codex R2 M#6 -- confirmed against the write
contract):** `complete_trade_review` (`swing/trades/review.py`) requires the
trade in `closed` state and atomically sets `new_state="reviewed"` AND
`reviewed_at` in the same write. So `state == 'reviewed'` and "a completed
review exists" are COUPLED by the single write path -- they cannot diverge;
filtering on `state == 'reviewed'` is equivalent to "has a completed review"
and hides nothing. (If a future write path ever set `reviewed_at` without the
state transition, escalate -- it does not today.) A coarse open-vs-closed
toggle maps `{entered, managing, partial_exited}` -> open and
`{closed, reviewed}` -> closed. **HTMX-driven, no full reload** -- the table `<tbody>` swaps via an
OOB-safe fragment (§8). Server-side sort/filter (the dataset is small,
single-operator); the route accepts `sort=`, `dir=`, `filter_state=`,
`filter_pattern=` query params, validates against allowlists (frozenset, reject
unknown -> 400 + clear, mirroring `_ALLOWED_PERIODS`), and re-renders the
`<tbody>` partial.

### §5.3 Candlestick thumbnails -- lazy-loaded per row

Operator ask: "the small charts ... except using candlesticks." The watchlist
thumbnail is a LINE chart (`render_watchlist_thumbnail_svg`); SB3 left it line.
So the journal thumbnail is a NEW small **candlestick** via
`render_trade_window_thumbnail_svg` (§4.2), NOT a reuse of the `watchlist_row`
cache surface.

**Lazy-load ON SCROLL to keep the listing fast AND bound the render queue
(Codex R4 M#2):** rendering all rows' thumbnails at once -- even lazily -- would
queue up to `page_size` renders behind the process-wide render lock (§4.2),
creating multi-second tail latency and occupying workers. Instead each row's
thumbnail loads only when scrolled into view, via `hx-trigger="revealed"`
(HTMX's intersection-observer trigger), so the lock queue is naturally bounded
to the handful of rows actually on screen:

```
<td class="journal-thumb"
    hx-get="/journal/trades/{{ row.trade_id }}/thumbnail"
    hx-trigger="revealed" hx-swap="innerHTML"
    hx-headers='{"HX-Request": "true"}'></td>
```

Combined with a **smaller default page size for the thumbnail-bearing listing
(~20-25 rows, not 50)**, this keeps the concurrent render demand low even on a
fast scroll. The render lock + on-scroll trigger + freshness memo together
prevent a single journal page from becoming a self-inflicted DoS.

**`revealed` requires window scrolling (Codex R5 M#2).** HTMX `revealed` keys
off the element scrolling within the WINDOW viewport; if the journal table sits
inside an `overflow:auto/scroll` container, `revealed` may never fire and
thumbnails never load. The writing-plans slice MUST verify the journal listing
uses normal window scrolling (the existing `base.html.j2` page layout does NOT
wrap content in an overflow-scroll container -- confirm at implementation), OR
switch to `hx-trigger="intersect"` with an explicit `root`/`threshold`
configured to the actual scroll container. The operator-witnessed gate (§10 S4)
explicitly verifies thumbnails DO load as the operator scrolls the real page.

`GET /journal/trades/{id}/thumbnail` returns the `<svg>` (or a
chart-unavailable `<span>`), memoized via the freshness-keyed memo (§4.2; NOT
bare `trade_id`). SVG content is not a table element -> no synthetic-table-wrap
hazard (§8). For open trades the thumbnail uses today's trailing window; for
closed trades the trade window.

**Request-storm control (Codex R1 M#7 / R2 M#2):** with pagination (§5.1) the
page fires at most `page_size` (~50) thumbnail requests on load. Bounds:
(a) the freshness-keyed memo means a re-sort / re-filter of the SAME rows does
NOT re-render (cache hit); (b) **fetch side -- corrected (R2 M#2):** the
closed-trade helper uses `read_or_fetch_archive` (module-level), NOT
`OhlcvCache.get_or_fetch`, so the OhlcvCache `max_concurrent_ohlcv_fetches`
semaphore does NOT bound it. The mitigation is instead that
`read_or_fetch_archive` reads the on-disk parquet for the common case and only
hits yfinance on its per-ticker WEEKLY full-refresh cadence -- so concurrent
thumbnail loads are mostly warm parquet reads + matplotlib renders, not a
network stampede; (c) **render side:** matplotlib renders are CPU-bound -- the
thumbnail route renders synchronously per request, and the writing-plans slice
adds an explicit render-concurrency bound (a small semaphore, or reuse
`app.state.price_fetch_executor`) so ~50 simultaneous loads do not saturate the
box; (d) the thumbnail endpoint is GET-cacheable + idempotent. If ~50
concurrent renders still prove heavy, the escalation is the v24 persisted
trade-keyed cache (§12 tripwire), not an undocumented silent cap.

### §5.4 Click-through drill-down -- chronology + annotated chart

NEW `GET /journal/trades/{trade_id}` -> `journal_trade_detail.html.j2`. Two
panels:

**(a) Per-trade chronology** (NEW read-only assembly,
`swing/web/view_models/trade_chronology.py`). There is **no existing
chronology helper** -- this is the only genuinely new assembly logic. Merge,
into one timestamp-sorted list of `ChronologyEntry(ts, source, kind, summary,
detail)`:
- `fills` (entry/exit/trim/stop -- `list_fills_for_trade`),
- `trade_events` (event_type rows -- inline SELECT, best-effort JSON payload
  parse with None fallbacks per the `_load_audit_entries` precedent),
- `daily_management_records` (Phase 8 daily snapshots / stop adjusts --
  inline SELECT, active rows `is_superseded=0`),
- `review_log` (the post-trade review entry, if any -- via
  `repos/review_log.py`).

Ordering: ascending by ISO timestamp; ties broken by a fixed source-precedence
(fill < daily_management < trade_event < review) so the merge is
deterministic. Malformed/missing timestamps sort last with a flag, never
raise (read-only over operator data). **Per-source sub-sections are an
alternative** (OQ-5) but a unified chronology better serves "browse the
database / how the trade went."

**The chronology is a substantive domain surface, not mere wiring (Codex R1
M#9).** It synthesizes a new authoritative narrative across four heterogeneous
sources, and its source-contract decisions materially shape operator
interpretation. The writing-plans slice (Slice 5) MUST pin, as explicit
contracts with dedicated tests (not incidental template assertions):
- **per-source field map** -- which column supplies `ts`, `kind`, `summary`,
  `detail` for each of fills / trade_events / daily_management_records /
  review_log;
- **supersession** -- `daily_management_records.is_superseded=0` only (active
  rows); superseded snapshots excluded (or shown struck-through -- decide);
- **timestamp normalization** -- the source timestamp formats differ
  (`fill_datetime`, event `ts`, record dates, `reviewed_at`); normalize to a
  common ISO key, document the precision (date vs datetime) per source;
- **malformed-payload behavior** -- best-effort JSON parse with None
  fallbacks (the `_load_audit_entries` precedent), entry flagged not dropped;
- **empty-source behavior** -- a trade with no daily_management / no review
  renders those sections empty, never errors.
This elevates Slice 5 from "wiring" to a tested domain assembly and is the one
place OQ-8 (writing-plans Codex chain count) could tip toward two chains.

The "entries filled out at opening" the operator references = the entry fill +
the pre-trade decision fields already on the `Trade` row (`thesis`, `why_now`,
`invalidation_condition`, premortem_*, etc., `models.py:236-253`) -- surface
those as a static "trade thesis at open" block above the chronology
(read-only; no new data).

**(b) Annotated full chart** = `render_trade_window_position_svg` (§4.2) --
candlesticks + entry/stop/target (BULZ zones) + fill markers over the trade
window. Same helper CR.1 uses (built once in CR.1 slice, reused here).

### §5.5 ASCII / mathtext (L5)

New template text is HTML, not matplotlib -- mathtext N/A. **(Codex R1 m#8)**
the ASCII discipline (#16/#32) governs *generated / code-authored* strings --
matplotlib labels (reused `render_position_detail_svg`, ASCII-clean), CLI
output, source literals. It does NOT constrain *operator-entered* data
(hypothesis_label, lesson_learned, review notes, chronology summaries derived
from operator text): that is rendered as stored, Jinja-auto-escaped (NOT
`| safe`), and may contain any Unicode. So: generated labels ASCII-only;
operator text escaped-and-displayed-as-is. The `| safe` boundary is reserved
for the matplotlib-generated SVG bytes ONLY (minor #3).

---

## §6 BULZ row-expand wiring (in-scope rider)

`partials/open_positions_expanded.html.j2:38-40` embeds the legacy static
`<img src="/charts/{date}/{ticker}.png">`. Replace with the SB3
`position_detail` SVG -- candlesticks + BULZ zones (P14.N4) -- so the operator's
PRIMARY dashboard workflow shows the same chart as the trade-detail page.

**This row-expand reuses the `position_detail` CACHE (not render-direct)**
because the row only exists for OPEN trades (`open_position_expand` 404s
closed trades, `routes/trades.py:2556-2582`): the trailing-today window and
ticker-only key are both correct for an open position. Plumb
`position_chart_svg_bytes: bytes | None` onto `OpenPositionsExpandedVM`,
populated in `build_open_positions_expanded` via the SAME read-only call
`build_trade_detail_vm` uses: `get_cached_chart_svg(conn, ticker=trade.ticker,
surface='position_detail', pipeline_run_id=None)` (`trades.py:1771`).

**Freshness = identical to the trade-detail page (Codex R3 M#1).** This is a
plain read of the run-agnostic `position_detail` row that the pipeline
`_step_charts` refreshes each run; the row-expand inherits EXACTLY the
trade-detail page's freshness semantics (both read the same row; both can lag
intraday fills/stop changes until the next pipeline run). SB4 introduces **no
new staleness** -- it makes the row-expand CONSISTENT with the already-shipped
trade-detail page, which is the desired outcome (the operator currently sees a
stale static PNG; after SB4 they see the same SVG the detail page shows). There
is deliberately NO JIT re-render here (that would be a write); if the cache row
is absent the row-expand shows the chart-unavailable state, exactly as the
detail page does.

Template (SVG INSIDE the existing `<td colspan="10">`, fragment still leads
with `<tr>` per the synthetic-table-wrap rule -- gotcha preserved):

```
{% if expanded.position_chart_svg_bytes %}
  <div class="position-detail-chart">{{ expanded.position_chart_svg_bytes.decode('utf-8') | safe }}</div>
{% elif expanded.chart_reason_message %}
  <div class="chart-unavailable" ...>{{ expanded.chart_reason_message }}</div>
{% endif %}
```

**Reopened-ticker cache safety (Codex R1 M#12):** the `position_detail` cache
is ticker-keyed/run-agnostic, so in principle a reopened ticker could surface a
stale chart from an earlier open trade. This is safe here because of a system
invariant: **at most ONE open trade exists per ticker** (the open-positions
list is per-ticker; the `open_position_expand` comment at `trades.py:2550-2552`
notes the trade_id route key defends only the *closed*-then-reopened case,
i.e. one closed + one open, never two simultaneously open). So the ticker key
is unambiguous for the open row-expand: the single `position_detail` row for
that ticker IS this open trade's chart, refreshed each pipeline run by
`_step_charts`. (Because the row-expand is now read-only -- mirroring
`build_trade_detail_vm`, no JIT, R3 M#1 -- the freshness is exactly the
trade-detail page's; SB4 adds no write.) Slice 1 adds a test asserting the
row-expand chart reflects the current open trade's fills. **Escalate** if the
data model is ever found to permit two concurrently-open trades per ticker (it
does not today).

**L7 reversal record:** the chart-access UX brief §2 deliberately put
position-detail on a SEPARATE page; inlining it into the row-expand reverses
that. Add a dated note to that brief in the BULZ-wiring slice commit.

**Discriminating test:** assert `GET /trades/open/{id}/expand` response body
contains `<svg` (or `position-detail-chart`) and does NOT contain
`<img src="/charts/`.

---

## §7 Chart-surface reuse-vs-new-enum decision (schema impact)

| Surface | Trades | Window correct? | Key correct? | Decision |
|---|---|---|---|---|
| `position_detail` cache (existing) | open | yes (trailing today) | yes (ticker, current run) | **reuse cache** -> BULZ row-expand (§6) |
| `position_detail` cache for CLOSED | closed | **NO** (anchored today) | **NO** (ticker collides) | reject -> render-direct |
| NEW `journal_trade_chart` cache | closed | needs trade_id col | needs trade_id col + index | reject (heavier than enum; v24+) |
| render-direct trade-window (NEW helper) | both | yes (explicit window) | yes (trade_id memo) | **adopt** for CR.1 + journal (§4.2) |

**Verdict: reuse the SB3 _renderer_, NOT a cache surface, for closed-trade
charts. No new `chart_renders` surface enum. No v24 migration. Schema stays
v23.** (Full schema analysis §11.)

---

## §8 HTMX surface disciplines applied (L4)

Every new HTMX interaction inherits the binding trinity + shared-VM discipline:

1. **Sort/filter swap -- DECIDED (Codex R1 M#10): whole-`<table>` `outerHTML`
   swap.** The sort/filter endpoint targets `#journal-table` with
   `hx-swap="outerHTML"` and returns a fragment whose ROOT is the `<table>`
   element (the `<table>` wrapper is present, so there is no bare `<tr>` at the
   fragment root -> the synthetic-table-wrap gotcha cannot fire). This is
   chosen over OOB-into-`<tbody>` because it is simpler, keeps the full table
   (header sort-state + rows) in one render, and is the most robust against the
   browser-only wrap hazard. (OOB-into-tbody is recorded only as the rejected
   alternative.) The operator-witnessed browser gate remains binding
   (TestClient cannot see the wrap behavior either way). **(Codex R2 m#1)** a
   whole-`<table>` `outerHTML` swap can reset focus / scroll / selected
   filter-control state; the gate (§10 S4) MUST verify repeated sort/filter
   cycles leave controls usable (sort indicator + selected filter persist in
   the re-rendered header; scroll not jarringly reset). If annoying, narrowing
   to a `<tbody>` swap + OOB header update is the noted fallback.
2. **Lazy thumbnail (`hx-trigger="load"`):** returns `<svg>`/`<span>` (not a
   table element) -> no wrap hazard; `innerHTML` swap into the `<td>`.
3. **Drill-down link:** a plain `<a href="/journal/trades/{id}">` full
   navigation (not HTMX) -- simplest; the drill-down is a full page. If made
   HTMX, the HX-Redirect/204 disciplines would apply, but a plain link avoids
   them entirely (recommended V1).
4. **Embedded controls** (sort headers, filter `<select>`) inside HTMX
   fragments carry `hx-headers='{"HX-Request":"true"}'` so OriginGuard
   strict-mode does not 403 them. **(Codex R1 m#4)** an out-of-allowlist
   `sort=`/`filter_*=` value returns an in-page error *fragment* (a
   `<table>`-rooted fragment showing the unfiltered set + a visible "invalid
   filter, showing all" notice), NOT a bare 400 the operator cannot recover
   from inside the HTMX swap. The allowlist rejection is still logged.
5. **No new POST** -> no 204/HX-Redirect-vs-303 surface in this sub-bundle
   (read-only; L2). If any control is a form, success stays GET-render.
6. **Shared `base.html.j2` VM fields:** `JournalRowVM` is NOT a base-layout VM,
   but `JournalVM` and the new `TradeDrilldownVM` ARE (both extend base). Any
   NEW `vm.foo` referenced in `base.html.j2` must be added with a safe default
   to ALL base VMs (`DashboardVM`, `PipelineVM`, `JournalVM`, `WatchlistVM`,
   `PageErrorVM`) -- this sub-bundle adds none to base. The new
   `TradeDrilldownVM` (a base-layout page) MUST carry the full base banner
   field set (`session_date`, `stale_banner`, `*_degraded`,
   `unresolved_material_discrepancies_count`,
   `recent_multi_leg_auto_correction_count`, `banner_resolve_link`).
   **(Codex R1 M#11)** to avoid hand-copying defaults (a 500-risk if a base
   field is later added and one VM is missed), the drill-down builder MUST
   populate those banner fields through the SAME path the other page VMs use --
   the existing `count_*` / `fetch_first_pending_ambiguity_resolve_link_path` /
   `last_completed_session` reads that `build_review_vm` and
   `build_trade_detail_vm` already perform. If no shared base-banner helper
   exists today, Slice 5 factors one (`_base_banner_fields(conn, cfg) -> dict`)
   and the drill-down + (opportunistically) the other page builders consume it;
   the new page does NOT independently re-list the base fields by hand.

---

## §9 Sub-bundle decomposition recommendation (writing-plans slices)

P14.N6 is the largest item; CR.1 establishes the shared chart helper. Six
slices, ordered so each lands testable and reuses the prior:

- **Slice 0 -- CR.1 (exit-data + chart snapshot).** Builds the shared
  `trade_charts.py` helper (`_trade_window_bars` +
  `render_trade_window_position_svg`) + `ReviewVM` exit fields + chart field +
  `review.html.j2` blocks. Smallest; lands the helper Slice 4 reuses.
  (~3-5 commits, ~10-15 tests.)
- **Slice 1 -- BULZ row-expand wiring.** Independent; `OpenPositionsExpandedVM`
  field + cache plumbing + template swap + L7 reversal note. (~2-3 commits,
  ~5-8 tests.)
- **Slice 2 -- Journal listing substrate.** `JournalRowVM` + `build_journal`
  enrichment (open_price/shares/total_risk/closing_price/final_r/entry-flags) +
  redesigned `journal.html.j2` + `journal_row.html.j2`. No charts, no
  sort/filter yet -- pure data + template (testable without matplotlib).
  (~4-6 commits, ~15-20 tests.)
- **Slice 3 -- Sort/filter (database-browsing).** Query-param sort/filter +
  HTMX `<tbody>` swap (§8). (~3-4 commits, ~10-15 tests; operator browser gate.)
- **Slice 4 -- Candlestick thumbnails.** `render_trade_window_thumbnail_svg` +
  `GET /journal/trades/{id}/thumbnail` + lazy-load cell. (~2-4 commits,
  ~8-12 tests; matplotlib visual gate.)
- **Slice 5 -- Drill-down.** `GET /journal/trades/{id}` +
  `build_trade_drilldown_vm` + `trade_chronology.py` assembly + annotated
  chart (reuses Slice 0 helper) + templates. Largest. (~5-8 commits,
  ~20-30 tests; matplotlib + chronology gate.)

Total estimate ~19-30 commits + ~70-100 tests (aligns with the commissioning
brief's ~20-35 commits / ~50-100 tests for this sub-bundle). Slices 0-1 are
independent of 2-5 and could parallelize at executing-plans; 2->3->4->5 are
serial (each builds on the listing).

---

## §10 Test fixture strategy + visual-gate enumeration

### §10.1 Fixtures
- A closed single-leg trade + its entry/exit fills + a recent exit date
  (within archive depth) -> trade-window chart has coverage.
- A closed multi-leg trade (2 exit fills) -> VWAP exit price + multi-marker
  chart.
- An OLD closed trade (exit date older than archive depth) -> helper returns
  None -> chart-unavailable state asserted.
- An open trade -> thumbnail uses trailing window; final_r/closing_price None.
- A reopened ticker (two trades, same ticker) -> proves render-direct serves
  the correct per-trade chart (the cache-collision regression test).
- Trades with / without candidate_id + pattern_evaluation_id -> entry-flag
  None-safety.
- A trade with fills + trade_events + daily_management_records + review_log ->
  chronology merge ordering + malformed-payload best-effort.

### §10.2 What tests CAN and CANNOT certify (L4 / L5)
- **CAN:** VM field values; derivation arithmetic (exit VWAP, total_risk,
  final_r -- compute under both single + multi-leg per the
  `feedback_regression_test_arithmetic` discipline); route status codes; body
  contains `<svg`/absence of legacy `<img>`; chronology ordering; sort/filter
  allowlist rejection; OHLCV-window slice bounds; None-on-no-coverage.
- **CANNOT (operator-witnessed gate required):** that the candlestick chart
  renders correctly (matplotlib geometry, not string equality -- L5); that the
  HTMX `<tbody>` swap / lazy thumbnail / drill-down navigation work in a REAL
  browser (synthetic-table-wrap + OriginGuard are browser-only -- L4).
  Byte/string-equality tests are declared INSUFFICIENT for chart correctness.

### §10.3 Operator-witnessed gate ladder (Sec 9.1 Q6)
- **S1** fast suite (`pytest -m "not slow"`) + `ruff check swing/` clean.
- **S2** schema probe: `EXPECTED_SCHEMA_VERSION == 23`; NO new `00XX_*.sql`;
  live DB untouched (no migration runs).
- **S3** CR.1: operator opens a real closed trade's review page -> exit
  price/date/legs + final R visible + candlestick chart with fills/zones over
  the TRADE window (not a trailing-today window).
- **S4** journal listing: rich rows render with all flag columns; candlestick
  thumbnails lazy-load; sort + filter work without full reload.
- **S5** drill-down: chronology renders in order; annotated chart shows
  entry/stop/target/fills over the trade window.
- **S6** BULZ row-expand: dashboard open-position row-expand shows the SB3
  candlestick + BULZ zones SVG, NOT the legacy PNG.
- **Fallback** for surfaces with no live data (e.g. no eligible closed trade
  with in-depth archive): orchestrator render-to-PNG + Read inspection, per
  the SB3 S6 documented substitute. Re-confirm the
  `feedback_visual_gate_both_render_and_browser` operator-driven-browser
  preference for SB4 at the gate.

---

## §11 Schema impact analysis

**Verdict: NO schema change. Schema stays v23.**

- No new table, column, CHECK, or index. `EXPECTED_SCHEMA_VERSION = 23`
  unchanged; no `0024_*.sql`.
- The only candidate trigger (a new `chart_renders` surface enum for closed-
  trade charts) is **eliminated** by the render-direct decision (§1.2, §7).
  Closed-trade charts hold no cache row.
- Because no schema changes, gotcha #11 (CHECK + constant + dataclass +
  `_row_to_*` paired) and #9 (executescript BEGIN/COMMIT/ROLLBACK) and the
  STRICT `pre_version==23` backup gate are **not invoked** -- and the spec must
  ASSERT zero migration (S2 gate). The v22 (temporal-log) and v23 (chart-
  surface-rename) substrates are untouched.
- If writing-plans or Codex later argues for a persisted closed-trade chart
  cache (performance), that is a v24 with a NEW `trade_id` column + partial
  unique index (NOT a bare enum value) -- flagged as a V2 candidate (§12), not
  V1.

---

## §12 V1 simplifications + V2 candidates

**Performance acceptance budget + escalation tripwire (Codex R1 M#8).** The
render-direct decision is V1 with a MEASURED tripwire, not a permanent
lockout of caching/schema work:
- *Budget (operationalized -- Codex R2 M#5):* the targets are **local,
  warm-archive (parquet present, the steady-state after the weekly refresh),
  operator-box medians at the operator's real trade count**, observed at the
  operator-witnessed gate (§10) -- NOT cold-start, NOT a CI/p95 number. Initial
  paginated-listing HTML (~50 rows, thumbnails lazy/deferred) well under ~1s;
  each lazy thumbnail render under ~250ms warm; the drill-down / review chart
  under ~500ms warm. **Evidence that trips the v24 escalation:** the operator
  perceiving sluggishness at the gate, OR a measured warm median exceeding the
  budget at their trade count. Cold-archive first-loads (post-weekly-refresh
  yfinance fetch) are exempt from the budget (one-off). **(Codex R3 m#3)** the
  observed warm medians at the gate are RECORDED in the merge notes so future
  regressions have a baseline to compare against.
- *Tripwire -> escalation:* if those budgets are missed in practice, the
  pre-designed escalation is the **v24 persisted trade-keyed chart cache** (a
  `trade_id` column + partial unique index on `chart_renders`, §7/§11) -- a
  clean, already-scoped follow-on, NOT a redesign. Render-direct is chosen
  because it is correct + schema-free + collision-free; the cache is the known
  lever if profiling demands it.

**V1 simplifications (deliberate, documented):**
- Closed-trade charts render-direct (freshness-keyed or request-lifetime memo
  only); no persisted cache. Acceptable for a single operator within the
  budget above; the v24 cache is the escalation if the budget is missed.
- "Total risk" = dollar risk at open; no %-of-capital column (OD-4 / OQ-6).
- "hyp-rec (and which)" surfaces `has_hyprec_link` (candidate_id present) +
  `hypothesis_label`; the specific hyp-rec registry row is deferred (OQ-4) --
  no direct FK exists on `trades`.
- Drill-down is a full page navigation (plain `<a>`), not an HTMX in-place
  expand -- avoids the 204/HX-Redirect surface entirely.
- Sort/filter is server-side full-`<tbody>` re-render, not client-side.
- Thumbnails lazy-load one render at a time (no batch executor parallelism).

**V2 candidates (banked, NOT designed here):**
- Persisted closed-trade chart cache (v24: `trade_id` column + index) if
  render-direct latency becomes a problem.
- %-of-capital risk column (capital-floor-aware per
  `project_capital_risk_floor`).
- Formal hyp-rec registry linkage (a `trades.hypothesis_recommendation_id` FK)
  if the operator wants "which hyp-rec" precisely.
- Broader P14.N1 thumbnail wiring to dashboard open-positions + hyp-rec rows
  (OQ-3) -- outside the review+journal L1 LOCK.
- Operator failure-mode classification surface (Tier 4; commissioning brief
  Sec 6) -- explicitly Phase 15 / later sub-bundle.
- market_weather 200MA fetch-window fix (banked rider #2; OD-6).

---

## §13 Operator decision items (OQs)

Surfaced for operator triage at writing-plans dispatch (Codex should pressure-
test the recommendations):

1. **OQ-1 CR.1 chart window:** confirm the trade-window render-direct chart
   (entry-30d .. exit+10d) over a reused cached `position_detail` (trailing
   today). **Recommend render-direct** (§1.2). Padding days (30/10)
   operator-tunable.
2. **OQ-2 chart surface / schema:** confirm NO new `chart_renders` surface
   enum; reuse the SB3 renderer render-direct. **Recommend confirm** (§7,
   §11).
3. **OQ-3 thumbnail breadth:** journal listing ONLY (recommend), or also
   dashboard open-positions + hyp-rec rows (broader P14.N1)? The BULZ
   row-expand already touches the dashboard -- does that widen the door?
   **Recommend keep surgical** (journal only); bank P14.N1 dashboard breadth.
4. **OQ-4 entry-flag "hyp-rec (and which)":** no direct FK on `trades`. V1 =
   `has_hyprec_link` + `hypothesis_label` + pattern_class + A+ bucket. Confirm
   that suffices, or scope a hyp-rec FK (would be a schema change -> defers).
5. **OQ-5 chronology shape:** unified timestamp-merged chronology (recommend)
   vs per-source sections? Confirm the source-precedence tiebreak order.
6. **OQ-6 total_risk semantics:** dollar risk at open (recommend) vs
   %-of-capital (needs the capital floor) vs both?
7. **OQ-7 banked rider #2:** market_weather 200MA fetch-window -- bank
   standalone (recommend, OD-6) vs fold into SB4?
8. **OQ-8 Codex chain count at writing-plans:** single (pure-UX, recommend)
   vs two-chain if the chronology assembly is judged substantive?
9. **OQ-9 sort/filter fragment shape:** DECIDED at this brainstorm (Codex R1
   M#10) -- whole-`<table>` `outerHTML` swap (§8). Listed here as confirm-only;
   operator may override at writing-plans, but the spec no longer punts it.

---

## §14 Cumulative discipline compliance summary

| Discipline | Application in this design |
|---|---|
| #2 brief-vs-signature | All routes/VMs/renderers/repos re-grepped at f4fe825 (§1.3); re-grep again at writing-plans. CR.1-form-exists CONFIRMED; `Trade` has no exit_price/date CORRECTED; position_detail-window CORRECTED. |
| #4 SQL-column | Entry-flag sources verified (chart_pattern_*, candidates.bucket, pattern_evaluations.pattern_class, hypothesis_label); hyp-rec FK absence flagged (OQ-4). |
| #9 / #11 / backup-gate | NOT invoked -- no schema change; spec ASSERTS zero migration (S2). |
| #16 / #32 ASCII | Declared across all NEW files/templates/view-model; reused renderer labels ASCII-clean. |
| L4 HTMX trinity | §8 -- table-row-free fragment root / OOB tbody; hx-headers HX-Request; no new POST (no 204/303 surface); base-VM safe defaults on the new drill-down page. |
| L5 matplotlib visual-gate | §10 -- byte/string tests INSUFFICIENT; per-surface operator-witnessed gate; reuse SB3 renderers (no candlestick re-implementation). |
| #10c renderer-kwargs uniformity | BULZ row-expand reads the cache via the SAME read-only `get_cached_chart_svg(surface='position_detail', pipeline_run_id=None)` call as `build_trade_detail_vm` (cache-collision-free; no JIT/write). |
| F6 / full-archive-slice / OHLCV-scope | `_trade_window_bars` returns None on empty (never blanks); consumes the FULL archive and slices locally; render-direct so closed-trade fetch does not pollute the open-trade OHLCV scope. |
| #28 / #29 exemplar/historical-depth | The #29 window-anchoring failure is the CENTRAL finding (§1.2); old-trade no-coverage -> chart-unavailable state (S4/S5 fixture). |
| L2 Schwab LOCK | ZERO new `schwabdev.Client.*`; source-grep test stays green; Schwab daily-bar wiring stays OUT (§12). |
| Co-Authored-By / trailer | NO footer; final `-m` paragraph plain prose; `%(trailers)` verified empty before push. |
| capital risk floor | total_risk = dollar-risk-at-open (OD-4); floor applies only to a future %-of-capital column (OQ-6 / V2). |

---

## §15 Adversarial review (Codex) round log

Single chain (Sec 9.1 Q7; pure UX/wiring), `codex exec` CLI backstop (MCP
off-purview per FB-N1), read-only sandbox, spec pasted inline.

**Round 1 -- 0 critical / 12 major / 10 minor (verdict ISSUES_FOUND).** All 12
majors resolved in-spec (none accepted-without-fix):
- M#1 OHLCV-archive-I/O vs read-mostly -> §2.3 scope clarification (trade-domain
  reads; archive is the existing shared read-through cache; ZERO new
  chart_renders/trade rows).
- M#2 review-page render slowness/flakiness -> §4.3 failure-isolation + lazy-load
  (`GET /trades/{id}/review/chart`).
- M#3 closed-trade-immutability / memo staleness -> §4.2 freshness-keyed (or
  request-lifetime) memo; bare-`trade_id` cross-request memo forbidden.
- M#4 exit VWAP underspecified -> §4.1 explicit reducing-fill classification +
  long-only positive-qty semantics.
- M#5 total_risk unsafe formula -> §4.1 guarded (long-only; None on
  missing/invalid stop); §5.1 reuse.
- M#6 "archive depth ample" too optimistic -> §1.2/§4.2 softened; no-coverage
  is a first-class state.
- M#7 thumbnail request-storms -> §5.1 pagination + §5.3 freshness-memo /
  semaphore / cacheable-GET bounds.
- M#8 cache-rejected-without-profiling -> §12 performance budget + v24 tripwire.
- M#9 chronology is substantive -> §5.4 elevated to a tested domain surface
  with explicit per-source contracts.
- M#10 sort/filter swap unresolved -> §8 DECIDED whole-`<table>` `outerHTML`;
  OQ-9 de-punted.
- M#11 TradeDrilldownVM base fields -> §8 shared `_base_banner_fields` helper,
  no hand-copy.
- M#12 reopened-ticker stale cache -> §6 one-open-trade-per-ticker invariant +
  write-through refresh + Slice-1 test.

High-value minors folded in: m#2 (exit-date source), m#3 (`| safe` reserved for
generated SVG only), m#4 (in-page error fragment, not bare 400), m#8 (ASCII
governs generated strings only; operator text escaped-and-displayed), m#10
(`filter_state` "reviewed" = `state=='reviewed'`).

**Round 2 -- 0 critical / 6 major / 4 minor (verdict ISSUES_FOUND).** All 6
majors were refinements of R1 resolutions; all resolved in-spec:
- R2 M#1 chart_renders write contradiction -> §4.1 write-contract precision
  (closed-trade surfaces zero-touch; open-position row-expand reuses the
  pre-existing `position_detail` cache, no new row type).
- R2 M#2 wrong concurrency control -> §5.3 corrected (archive path bypasses the
  OhlcvCache semaphore; warm-parquet common case + explicit render-concurrency
  bound).
- R2 M#3 partial freshness token -> §4.2 request-lifetime memo is the V1
  default; cross-request requires a full deterministic fingerprint.
- R2 M#4 lazy-route HTMX disciplines -> §4.3 explicit response contract
  (200+SVG / 200+unavailable / HX-Request header / non-HX access).
- R2 M#5 vague tripwire -> §12 operationalized (local warm-archive operator-box
  medians; specified escalation evidence).
- R2 M#6 "reviewed" semantics -> §5.1 confirmed coupled via
  `complete_trade_review` (state + reviewed_at set atomically; cannot diverge).
Minors folded: m#1 (gate check for focus/scroll/control persistence on swap),
m#3 (`Cache-Control: private` on chart endpoints), m#4 (exit-date = stored fill
date prefix). m#2 (n/a display text for unavailable risk) -> §10.2.

**Round 3 -- 0 critical / 2 major / 3 minor (verdict ISSUES_FOUND).** Both
majors resolved in-spec (issues now narrowing 12 -> 6 -> 2):
- R3 M#1 BULZ row-expand staleness -> §4.1/§6 corrected to the SAME read-only
  `get_cached_chart_svg` path `build_trade_detail_vm` uses (NO JIT, NO write);
  freshness is identical to the already-shipped trade-detail page; SB4 is fully
  write-free against `chart_renders`.
- R3 M#2 matplotlib thread-safety -> §4.2 process-wide matplotlib render lock
  (charts.py uses pyplot global state, verified; no existing lock); unifies
  with the R2 M#2 render bound.
Minors folded: m#1 structured WARNING on every exception fallback; m#2
distinguish missing-trade in fragment text + logs; m#3 record warm medians in
merge notes as a baseline.

**Round 4 -- 0 critical / 2 major / 0 minor (verdict ISSUES_FOUND).** Both
majors were follow-ons of the R3 render-lock decision; resolved in-spec:
- R4 M#1 lock must be global, not SB4-only -> §3/§4.2 the render lock lives at
  the SHARED `charts.py` render boundary so every web render path serializes (a
  small, justified carve-out into the SB3 shared helper).
- R4 M#2 lock could queue ~50 renders / DoS -> §5.3 thumbnails load on scroll
  via `hx-trigger="revealed"` (intersection-observer) + a smaller default page
  size (~20-25), bounding the lock queue to on-screen rows.

**Round 5 -- 0 critical / 2 major / 0 minor (verdict ISSUES_FOUND).** Both R5
majors were narrow implementation-detail catches on the R4 render-lock/lazy-load
resolutions; both resolved in-spec:
- R5 M#1 lock self-deadlock risk -> §4.2 single outer acquisition per render
  (not inner + outer); `RLock` if nesting unavoidable; writing-plans no-deadlock
  test per chart path.
- R5 M#2 `revealed` in overflow containers -> §5.3 verify window-scroll layout
  or use `hx-trigger="intersect"` with explicit root; gate verifies thumbnails
  load on scroll.

**Round 6 -- 0 critical / 0 major / 0 minor (verdict NO_NEW_CRITICAL_MAJOR).
CONVERGED.** The R5 resolutions drew no new findings; the chain reached a clean
terminal verdict.

**Chain close:** R1 0C/12M/10m -> R2 0C/6M/4m -> R3 0C/2M/3m -> R4 0C/2M/0m ->
R5 0C/2M/0m -> R6 CLEAN. The config MAX_ROUNDS default (5) was extended by
operator direction ("continue the chain until a clean terminal verdict, per
project precedence"); R6 delivered it. **Cumulative 0 critical / 24 major / 17
minor across R1-R6; ALL 24 majors resolved-via-code, ZERO accepted-without-fix,
ZERO unresolved at close.** Each round's findings narrowed from design-level
(R1) to implementation-detail (R5) to none (R6). Ran via the `codex exec` CLI +
`resume --last` read-only backstop (MCP off-purview, FB-N1).

---

*End of design spec. Phase 14 Sub-bundle 4 -- review + journal UX. CR.1
(exit-data + chart-snapshot delta on the EXISTING review form) + P14.N6
(browse-the-database journal: rich rows + sort/filter + candlestick thumbnails
+ drill-down chronology + annotated chart) + the BULZ row-expand wiring.
Read-mostly; NO schema change (v23 held); NO new trade-mutation path. The
load-bearing decision: closed-trade charts reuse the SB3 renderer render-
direct over a trade-window archive slice (NOT the ticker-keyed,
trailing-today `position_detail` cache); open-trade BULZ row-expand reuses the
cache. The rendered surface in a real browser is the binding operator-witnessed
gate.*
