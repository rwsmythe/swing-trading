# Phase 14 Sub-bundle 4 — Review + Journal UX — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Enrich the existing closeout-review surface (CR.1) with exit-data + a render-direct closed-trade chart, redesign the journal into a browse-the-database surface (P14.N6: rich rows + sort/filter + candlestick thumbnails + drill-down chronology + annotated chart), and rewire the dashboard BULZ row-expand to the SB3 `position_detail` SVG — all read-mostly over already-shipped data, with **no schema change** (v23 held) and **no new trade-mutation path**.

**Architecture:** Closed-trade charts reuse the SB3 *renderer* (`render_position_detail_svg` / `_render_candles_fig`) **render-direct over a trade-window archive slice** (NOT the ticker-keyed, trailing-today `position_detail` *cache*, which is wrong on both window-anchoring and key-collision axes for closed trades — §1.2 of the spec). Open-trade BULZ row-expand reuses the cache (window + key are both correct for an open position). A single new read-only chart helper (`swing/web/trade_charts.py`) serves CR.1 + the journal drill-down + thumbnails; a single new read-only chronology assembly (`swing/web/view_models/trade_chronology.py`) serves only the drill-down. A **process-wide matplotlib render lock** is added at the shared `charts.py` render boundary because pyplot global state is not thread-safe and the journal's lazy thumbnails introduce high-concurrency rendering.

**Tech Stack:** Python 3.14, FastAPI + Starlette 1.0, Jinja2 + HTMX 2.x, matplotlib/mplfinance SVG (no JS charting), SQLite (read-only here), pytest (+ xdist), ruff.

**Spec (AUTHORITATIVE):** `docs/superpowers/specs/2026-05-30-phase14-sub-bundle-4-review-journal-ux-design.md` (1278 lines; copowers v2.0.2 WSL Codex CONVERGED Re-R4). **Brief:** `docs/phase14-sub-bundle-4-review-journal-ux-writing-plans-dispatch-brief.md`. **Findings:** `.copowers-findings.md` (8 production-truth corrections, all honored below).

**Branch:** `phase14-sub-bundle-4-review-journal-ux-writing-plans` (writing-plans worktree). Executing-plans will branch fresh from main HEAD at dispatch. **CLI in worktree:** `python -m swing.cli` (NOT bare `swing`).

---

## §A Goals / Non-goals

### §A.1 Goals (L1 scope — exactly three deliverables)

1. **CR.1 — closeout-review enrichment.** On the EXISTING `GET /trades/{id}/review` surface, add (a) exit-data display fields derived from non-entry fills (per-leg exit table, share-weighted exit VWAP, last exit date, dollar total-risk-at-open), surfacing the already-present `actual_realized_R_effective` prominently; and (b) a render-direct closed-trade candlestick chart over the trade window (`entry-30d .. exit+10d`), lazy-loaded via `GET /trades/{id}/review/chart` so a slow/flaky render never degrades the write-adjacent form.
2. **P14.N6 — browse-the-database journal.** Redesign `GET /journal` from a 3-column table into a paginated rich table (open price, shares, dollar total-risk, closing price, final R, entry-time flags), add HTMX server-side sort/filter (whole-`<table>` `outerHTML` swap), add lazy-loaded per-row **candlestick** thumbnails (on-scroll), and add a drill-down (`GET /journal/trades/{id}`) with a unified per-trade chronology + an annotated full chart.
3. **BULZ row-expand rewire.** Replace the legacy static `<img src="/charts/{date}/{ticker}.png">` in `partials/open_positions_expanded.html.j2` with the SB3 `position_detail` SVG, read from the EXISTING cache via the same read-only `get_cached_chart_svg(... surface='position_detail', pipeline_run_id=None)` path `build_trade_detail_vm` uses (no JIT, no write).

### §A.2 Cross-cutting goals (infrastructure the slices share)

4. **Shared chart helper** `swing/web/trade_charts.py` — `_trade_window_bars`, `render_trade_window_position_svg`, `render_trade_window_thumbnail_svg`. Read-only; reuses the SB3 renderers; never writes `chart_renders`.
5. **Process-wide matplotlib render lock** at the shared `charts.py` boundary — every web render path serializes; single outer acquisition per render; `RLock` if nesting is unavoidable; a no-deadlock test per chart path (HIGHEST-RISK item, §2.4 of the brief).
6. **Tested chronology assembly** `swing/web/view_models/trade_chronology.py` — the one genuinely-new domain surface; per-source field-map + supersession + timestamp-normalization + malformed-payload isolation, each with dedicated tests (the substantive Codex Re-R1..R3 artifact).

### §A.3 Non-goals (OUT of scope — do NOT design into the plan)

- Metrics overview (SB5).
- Broader P14.N1 dashboard open-positions / hyp-rec thumbnail wiring (OQ-3 banked).
- market_weather 200MA fetch-window fix (OQ-7 banked standalone, L8).
- Schwab daily-bar web wiring (banked #4; L6 — ZERO new `schwabdev.Client.*` call sites).
- ANY new schema / migration (L3 — render-direct keeps SB4 schema-free; v23 held).
- ANY new trade-mutation path (L2 — review-write + fills-write contracts unchanged; ZERO trade/fill/review/`chart_renders` writes).
- A persisted closed-trade chart cache (v24 `trade_id` column + index) — banked V2 tripwire (§12 of spec), NOT V1.
- %-of-capital risk column (capital-floor-aware) — banked V2.
- A hyp-rec FK on `trades` — banked V2 (OQ-4 deferred-the-which).
- JS charting (Q5: matplotlib SVG only); per-source chronology sections (OQ-5 LOCKed unified); Phase 15+ failure-mode classification.

---

## §B File map

### §B.1 New files (read-only assemblies + helpers + templates)

| Path | Responsibility |
|---|---|
| `swing/web/trade_charts.py` | NEW read-only chart helper. `_trade_window_bars` (archive slice over trade window), `render_trade_window_position_svg` (full 800x500 candlestick via `render_position_detail_svg`), `render_trade_window_thumbnail_svg` (small candlestick via `_render_candles_fig`). Reuses SB3 renderers; NO candlestick re-impl; NO `chart_renders` write. |
| `swing/web/view_models/trade_chronology.py` | NEW read-only assembly. `ChronologyEntry` dataclass, `TradeChronology` dataclass, `build_trade_chronology(conn, trade_id)` merging fills + trade_events + daily_management_records (split by record_type) + the `trades` post-trade-review columns into one timestamp-sorted stream. |
| `swing/web/templates/partials/journal_row.html.j2` | NEW rich journal listing row partial (one `<tr>`). |
| `swing/web/templates/partials/journal_thumbnail.html.j2` | NEW lazy-thumbnail fragment (the `<svg>` or chart-unavailable `<span>`). |
| `swing/web/templates/journal_trade_detail.html.j2` | NEW drill-down full page (base-layout page: thesis-at-open block + chronology panel + annotated chart). |
| `swing/web/templates/partials/trade_chronology.html.j2` | NEW chronology list partial (rendered inside the drill-down page). |
| `swing/web/templates/partials/review_chart.html.j2` | NEW review-chart lazy fragment (`<svg>` or chart-unavailable `<span>`); shared response shape with the thumbnail fragment. |

### §B.2 Modified files

| Path | Change |
|---|---|
| `swing/web/charts.py` | Add a module-level **render lock** (`_RENDER_LOCK = threading.RLock()`) and acquire it ONCE per render at each top-level `render_*_svg` boundary (existing + reused). The single in-scope edit to the SB3 shared helper. No behavior change beyond serialization. |
| `swing/web/view_models/trades.py` | `ReviewVM`: add exit-data fields (`exit_legs`, `exit_price_vwap`, `exit_date_last`, `total_risk_dollars`) + `review_chart_url` (lazy-load target, NOT chart bytes). `build_review_vm`: derive exit legs/VWAP + the lazy target. |
| `swing/web/view_models/journal.py` | `JournalVM`: add `rows: tuple[JournalRowVM, ...]` + pagination/sort/filter fields. NEW `JournalRowVM` dataclass. `build_journal`: enrich rows + batched entry-flag joins + sort/filter/pagination. NEW `build_trade_drilldown_vm` + `TradeDrilldownVM`. NEW shared `_base_banner_fields(conn, cfg)` helper (factored; consumed by the drill-down page and opportunistically others). |
| `swing/web/view_models/open_positions_row.py` | `OpenPositionsExpandedVM`: add `position_chart_svg_bytes: bytes \| None`. `build_open_positions_expanded`: read the `position_detail` cache via `get_cached_chart_svg` (mirroring `build_trade_detail_vm`; no JIT, no write). |
| `swing/web/routes/journal.py` | Loosen `journal_page` `period` from `Literal[...]` to `str` + allowlist-check (Codex Re-R2 m#2). Add sort/filter query params (`sort`, `dir`, `filter_state`, `filter_pattern`, `page`, `page_size`) typed `str`/`int`, validated against frozensets. NEW `GET /journal/trades/{trade_id}` (drill-down full page; 404 on missing). NEW `GET /journal/trades/{trade_id}/thumbnail` (lazy fragment; 200+unavailable on missing). |
| `swing/web/routes/trades.py` | NEW `GET /trades/{trade_id}/review/chart` (lazy review-chart fragment; 200+unavailable on missing/no-coverage). `review_form_page` passes archive plumbing (already passes `ohlcv_cache`). `open_position_expand` signature unchanged (the VM does the cache read). |
| `swing/web/templates/review.html.j2` and/or `partials/review_form.html.j2` | Add exit-data block (per-leg table, VWAP, last exit date, total-risk-dollars, final R) + a lazy chart cell (`hx-trigger="load"`). |
| `swing/web/templates/journal.html.j2` | Full redesign: rich `<table id="journal-table">` including header sort controls + filter `<select>`s + `{% include journal_row %}` per row + pagination controls. |
| `swing/web/templates/partials/open_positions_expanded.html.j2` | Swap the legacy `<img src="/charts/...png">` for the `position_detail` SVG (inside the existing `<td colspan>`); keep the `chart_reason_message` unavailable branch. |
| `docs/chart-access-ux-brief.md` (or the actual chart-access UX brief path — verify at execution) | Add a dated L7 reversal note (row-expand now inlines `position_detail`). |

### §B.3 Repos / modules consumed read-only (NO change)

- `swing/data/repos/fills.py` — `list_fills_for_trade`, `list_all_fills`, `get_authoritative_entry_fill`.
- `swing/data/repos/trades.py` — `get_trade`, `list_open_trades`, `list_closed_trades`.
- `swing/data/repos/chart_renders.py` — `get_cached_chart_svg` (read-only).
- `swing/data/ohlcv_archive.py` — `read_or_fetch_archive(ticker, *, end_date, cache_dir, archive_history_days)`.
- `swing/trades/origin.py` — `derive_trade_origin` (for the `trade_origin` enum semantics).
- `swing/trades/review.py` — `compute_actual_realized_R_effective` (single math source).
- `swing/web/charts.py` — `render_position_detail_svg`, `_render_candles_fig`, `_svg_bytes_from_fig` (reused renderers).
- `trade_events` + `daily_management_records` via inline SELECTs in the chronology helper.

### §B.4 Files explicitly NOT touched

- `swing/data/migrations/*` — ZERO new migration. `EXPECTED_SCHEMA_VERSION` stays 23 (`swing/data/db.py:51`).
- `swing/trades/review.py` write path (`complete_trade_review`), `swing/trades/entry.py`, `swing/data/repos/*` write functions, `swing/integrations/schwab/*` — no edits.

### §B.5 Verified production anchors (re-grepped at plan time on this worktree; #2/#4)

| Anchor | Verified location | Note vs brief |
|---|---|---|
| `EXPECTED_SCHEMA_VERSION = 23` | `swing/data/db.py:51`; highest migration `0023_*` | matches |
| `journal_page` + `period: Literal[...]` | `swing/web/routes/journal.py:16` / `:18` | brief said `:15`; route def at `:16`, Literal at `:18` |
| `build_journal(*, cfg, period: str = "month")` + `_ALLOWED_PERIODS` | `swing/web/view_models/journal.py:136` / `:19` | the VM already types `period: str` + allowlists; only the ROUTE has `Literal` |
| `Fill.action`/`quantity`/`price`/`fill_datetime`/`reason`/`rule_based` | `swing/data/models.py:292-296`, `:291`, `:294` | NO `side`/`qty` — confirmed |
| `trade_origin == "pipeline_watch_hyp_recs"` | `swing/trades/origin.py:71` | confirmed |
| Trade cols: `entry_price:192`, `initial_shares:193`, `initial_stop:194`, `current_stop:195`, `state:196`, `hypothesis_label:203`, `chart_pattern_algo:206`, `chart_pattern_operator:208`, `reviewed_at:214`, `lesson_learned:223`, `trade_origin:228`, `planned_target_R:256`, `candidate_id:264`, `pattern_evaluation_id:265` | `swing/data/models.py` | confirmed |
| `ReviewVM` / `build_review_vm` | `swing/web/view_models/trades.py:1107` / `:1183` | brief said `:1106`; class at `:1107` |
| `non_entry_fills = [f for f in fills if f.action != "entry"]` | `swing/web/view_models/trades.py:1232` | confirmed; `mfe_pct`/`mae_pct` at `:1159-1160` |
| `build_trade_detail_vm` reads `get_cached_chart_svg(surface="position_detail", pipeline_run_id=None)` | `swing/web/view_models/trades.py:1722` / `:1771-1775` | confirmed |
| charts: `_svg_bytes_from_fig:90`, `_assert_ascii_only:98`, `_x_for_fill_date:352`, `_render_candles_fig:412` (`mpf.plot:462`), `render_watchlist_thumbnail_svg:492` (`plt.subplots:505`), `_bulz_target_price:609`, `render_position_detail_svg:628`, `_draw_bulz_zones:701` | `swing/web/charts.py` | `import matplotlib.pyplot as plt` at `:54`; **NO existing lock** — confirmed |
| `daily_management_records`: `record_type IN ('daily_snapshot','event_log'):31-32`, `review_date:33`, `is_superseded:40`, `open_MFE_R_to_date:51`, `open_MAE_R_to_date:52`, `thesis_status:75`, `prior_stop:77`, `new_stop:78`, `stop_changed:81`, `stop_change_reason:83`, `action_taken:95`, `management_notes:102`; index `(trade_id, review_date):119` | `swing/data/migrations/0016_phase8_daily_management.sql` | confirmed; `trade_id` present |
| `trade_events`: `id, trade_id, ts, event_type CHECK IN ('entry','stop_adjust','note','exit','flag'), payload_json (NOT NULL), rationale` | `swing/data/migrations/0003_phase2_pipeline_trades.sql:88-95` | **CORRECTION: columns are `payload_json` + `rationale`, NOT `notes`** (brief loosely said `payload_json`/`notes`) |
| `open_position_expand` / `review_form_page` / `review_post` | `swing/web/routes/trades.py:2556` / `:2590` / `:2610` | brief said `:2555`; route at `:2556` |
| legacy `<img src="/charts/{{ ... }}.png">` | `swing/web/templates/partials/open_positions_expanded.html.j2:~39` | gated by `expanded.chart_reason is none and expanded.data_asof_date` — confirmed |
| `read_or_fetch_archive(ticker, *, end_date: date, cache_dir: Path, archive_history_days: int) -> DataFrame \| None` | `swing/data/ohlcv_archive.py:172` | returns rows ≤ end_date; archive always extends to today; None on empty |
| `ArchiveConfig.archive_history_days = 1260`; `Paths.prices_cache_dir` | `swing/config.py:205` / `:17` | confirmed (~5y depth) |
| base VMs carry `session_date`/`stale_banner`/`banner_resolve_link` hand-rolled | `view_models/dashboard.py:320-321,373`, `config.py:39-40,55` | NO shared `_base_banner_fields` helper exists today → Slice 5 factors one (Codex R1 M#11) |

---

## §C Surface-by-surface integration

### §C.1 CR.1 review surface (`GET /trades/{id}/review`)

- `build_review_vm` (`view_models/trades.py:1183`) already loads `non_entry_fills` and computes `actual_realized_R_effective`. CR.1 adds: (a) `exit_legs` tuple from those fills; (b) `exit_price_vwap` (share-weighted over reducing fills); (c) `exit_date_last`; (d) `total_risk_dollars` (guarded long-only); (e) `review_chart_url` = `/trades/{id}/review/chart`. The ReviewVM does **not** carry chart bytes (lazy-load).
- The review template emits the exit block + a chart cell that self-loads via `hx-trigger="load"` against the new fragment route.
- `GET /trades/{id}/review/chart` renders the closed-trade chart render-direct (`render_trade_window_position_svg`) and returns `200`+`<svg>` on success or `200`+chart-unavailable `<span>` on no-coverage / render error / missing-trade (distinct copy + structured WARNING).

### §C.2 BULZ row-expand (`GET /trades/open/{id}/expand`)

- `open_position_expand` (`routes/trades.py:2556`) → `build_open_positions_expanded`. Add `position_chart_svg_bytes` populated via `get_cached_chart_svg(conn, ticker=trade.ticker, surface='position_detail', pipeline_run_id=None)` — the SAME read-only call `build_trade_detail_vm` uses. No JIT, no write.
- Template: swap the legacy `<img>` for the SVG inside the existing `<td colspan>`; the fragment still leads with `<tr>` (synthetic-table-wrap rule preserved); keep the `chart_reason_message` unavailable branch.

### §C.3 Journal listing (`GET /journal`)

- `build_journal` (`view_models/journal.py:136`) already loads `list_open_trades + list_closed_trades` + `_ExitShape`. Enrich to a `JournalRowVM` per trade; batched entry-flag joins (candidates.bucket / pattern_evaluations.pattern_class) inside the existing `with conn:`; pagination (default page_size ~20-25). Reuse the CR.1 VWAP/`compute_actual_realized_R_effective` math (single source).
- The route loosens `period` to `str`, adds sort/filter/pagination params (all `str`/`int`, frozenset-validated), and the sort/filter endpoint re-renders the whole `<table id="journal-table">` via `hx-swap="outerHTML"`.

### §C.4 Journal thumbnails (`GET /journal/trades/{id}/thumbnail`)

- Each listing row's `<td class="journal-thumb">` lazy-loads via `hx-trigger="revealed"` (on-scroll). The fragment route renders `render_trade_window_thumbnail_svg` (closed trades: trade window; open trades: trailing window) and returns `200`+`<svg>` or `200`+unavailable `<span>`. Memoized request-lifetime (NOT bare `trade_id`).

### §C.5 Journal drill-down (`GET /journal/trades/{id}`)

- NEW full-page route → `build_trade_drilldown_vm` → `journal_trade_detail.html.j2`. Panels: (a) thesis-at-open block (static `Trade` decision columns); (b) unified chronology (`build_trade_chronology`); (c) annotated full chart (`render_trade_window_position_svg`, same helper as CR.1; lazy via a chart fragment OR inline-with-failure-isolation — see §G.5). Missing trade → `404` (full-page contract).
- `TradeDrilldownVM` is a base-layout page → carries the full base-banner field set via the factored `_base_banner_fields` helper (no hand-copy).

### §C.6 Shared chart helper + render lock

- `trade_charts.py` is the single home for trade-window rendering; CR.1 + drill-down + thumbnails all call it. It calls the SB3 renderers, which acquire the process-wide render lock at their top-level boundary.

---

## §D Out of scope (restated for the executing engineer)

See §A.3. Additionally, during execution: do **not** add a `conn`-held outer transaction (all reads are within the existing `with conn:` autocommit-read pattern); do **not** introduce parallelism in the thumbnail executor beyond the documented render-concurrency bound; do **not** widen `complete_trade_review` or any write path; do **not** add a chart_renders surface enum. If any task appears to need a write or a schema change, **ESCALATE** (§7 of the brief).

---

## §E LOCK reverification (BINDING — confirm per task)

### §E.1 Sec 9.1 commissioning LOCKs
- **Q1** sequencing review+journal UX (THIS) after chart-surface uniformity. ✔ honored.
- **Q2** SERIAL execution. ✔ slices 2→3→4→5 serial; 0,1 independent.
- **Q5** matplotlib SVG only; reuse SB3 renderers; NO JS charting. ✔ every chart routes through `charts.py` renderers.
- **Q6** operator browser-witnessed verification at merge. ✔ §I gate ladder.
- **Q7** Codex chain count = orchestrator discretion → SINGLE chain (OQ-8). ✔ §J.

### §E.2 Brainstorm L1–L8
- **L1** scope = CR.1 + P14.N6 + BULZ row-expand ONLY. ✔ §A.
- **L2** read-mostly; NO new trade-mutation path; ZERO trade/fill/review/`chart_renders` writes; OHLCV archive read-through is the only permitted I/O. ✔ §B.4; per-task acceptance asserts zero writes.
- **L3** NO schema change; v23 held; §K asserts ZERO migration. ✔
- **L4** HTMX trinity on sort/filter/drill-down/thumbnail; operator-witnessed binding. ✔ §G.3/§G.4/§G.5 + §I.
- **L5** matplotlib visual-gate; ASCII-only annotations; reuse SB3 renderers. ✔ §G.0 + §I.
- **L6** L2 Schwab LOCK; ZERO new `schwabdev.Client.*`; source-grep stays green; Schwab daily-bar OUT. ✔ §H.9.
- **L7** record the chart-access UX brief §2 reversal in the BULZ slice. ✔ §G.1 final task.
- **L8** market_weather 200MA banked standalone. ✔ §A.3.

### §E.3 Operator-LOCKed OQ dispositions (§1.3 — HOLD THE LINE)
- **OQ-1** render-direct closed-trade chart over `entry-30d .. exit+10d`. ✔ §G.0/§G.5.
- **OQ-2** NO new `chart_renders` surface enum; NO schema. ✔ §K.
- **OQ-3** thumbnails journal listing ONLY; P14.N1 dashboard breadth banked. ✔ §A.3.
- **OQ-4** V1 derived entry flags (`has_hyprec_link` via `trade_origin`, `hypothesis_label`, pattern_class, A+ bucket); no hyp-rec FK. ✔ §G.2.
- **OQ-5** unified timestamp-merged chronology; source-precedence tiebreak LOCKed. ✔ §G.5.
- **OQ-6** total_risk = dollar risk at open = `initial_shares*(entry_price-initial_stop)`. ✔ §G.0/§G.2.
- **OQ-7** market_weather 200MA banked standalone. ✔ §A.3.
- **OQ-8** SINGLE Codex chain, run to convergence. ✔ §J.
- **OQ-9** whole-`<table>` `outerHTML` swap. ✔ §G.3.

---

## §F Discipline + watch items (per-task hooks)

Every task's acceptance carries the relevant subset:

| Discipline | Where it bites in this plan |
|---|---|
| **#2 signature verify** | All anchors re-grepped (§B.5); each task re-confirms the exact signature it touches before editing. |
| **#4 SQL-column verify** | Entry-flag joins (candidates.bucket, pattern_evaluations.pattern_class); chronology field-maps (Fill.action/quantity, daily_management record_type cols, trade_events payload_json/rationale, trades reviewed_at/lesson_learned). **trade_events has NO `notes` column** — use `payload_json`+`rationale`. |
| **#9/#11/backup-gate** | NOT invoked — no schema change. Each task asserts ZERO migration added (`schema_version==23`). |
| **#16/#32 ASCII** | All generated matplotlib labels ASCII (reused renderers already guarded by `_assert_ascii_only`); the thumbnail renderer passes NO title. Operator-entered text is Jinja-auto-escaped (NOT `\| safe`); `\| safe` reserved for the generated SVG bytes ONLY. |
| **F6 / full-archive-slice / OHLCV-scope** | `_trade_window_bars` returns `None` on empty (never blanks); reads the FULL archive ≤ end_date and slices the lower bound locally; render-direct so closed-trade fetch does not pollute the open-trade OHLCV scope. |
| **#28/#29 historical-depth/window-anchoring** | The #29 window-anchoring failure is the CENTRAL reason for render-direct; an old trade beyond archive depth → first-class chart-unavailable state (fixture + test). |
| **Cache+executor race / render lock** | Process-wide render lock at the shared boundary; single outer acquisition / `RLock`; no-deadlock test per chart path; thumbnail on-scroll + small page-size bounds the lock queue. |
| **HTMX trinity (L4)** | `hx-headers='{"HX-Request":"true"}'` on embedded controls; table-row-free fragment roots for non-table content (SVG/`<span>`); whole-`<table>`-rooted fragment for the sort/filter swap; NO new POST (no 204/HX-Redirect surface); HX-Redirect target N/A (drill-down is a plain `<a>`). |
| **Shared base.html.j2 VM defaults** | `TradeDrilldownVM` (base-layout page) carries the full base-banner set via `_base_banner_fields`; SB4 adds NO new `vm.foo` to `base.html.j2`. |
| **L6 Schwab grep** | ZERO new `schwabdev.Client.*`; the source-grep test stays green. |
| **Co-Authored-By / trailer** | NO footer; final `-m` paragraph plain prose; `git log -1 --format='%(trailers)'` empty verified before any push. |
| **feedback_verify_regression_test_arithmetic** | exit-VWAP / total_risk / final_R computed under BOTH single-leg AND multi-leg in tests (§H + §G.0/§G.2). |
| **Windows cp1252 stdout** | No new non-ASCII in any `print`/`click.echo` path (web-only sub-bundle; low risk, but ASCII discipline holds). |

---

## §G Per-slice tasks

### §G.0 Commit cadence + cross-slice preface (READ FIRST)

- **Cadence:** each Task below = one conventional commit (occasionally two when a test-commit precedes an impl-commit on a large surface). Commit stem: `feat(web): ...`, `refactor(web): ...`, `test(web): ...`, or `docs(...): ...`. The plan-doc commit itself uses `docs(phase14-sub-bundle-4-plan): ...`. **NO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph plain prose; verify `git log -1 --format='%(trailers)'` is `[]` before any push.**
- **TDD per task:** write the failing test → run it, SEE it fail → minimal implementation → run, SEE it pass → commit. Never write impl before a red test.
- **CLI in worktree:** `python -m swing.cli`. Fast suite: `python -m pytest -m "not slow" -q`. Lint: `ruff check swing/`.
- **Slice order:** Slice 0 and Slice 1 are independent of each other and of 2–5; Slices 2→3→4→5 are SERIAL (each builds on the listing). Slice 0 builds the shared `trade_charts.py` helper + the render lock that Slices 4 and 5 reuse — **do Slice 0 before 4/5**.
- **Padding constants (OQ-1):** `pad_before_days=30`, `pad_after_days=10` are module-level constants in `trade_charts.py`, operator-tunable. The chart window is `[entry_date - 30d .. (exit_date or today) + 10d]`.
- **Render-lock invariant (every chart task):** every top-level `render_*_svg` entry point (existing `charts.py` renderers AND the new `trade_charts.py` helpers) acquires the process-wide `charts._RENDER_LOCK` (an `RLock`) exactly once at its boundary; nested calls (e.g. `render_trade_window_position_svg` → `render_position_detail_svg`) are safe because the lock is reentrant. Each chart-producing task adds a no-deadlock test for its path.
- **`| safe` invariant:** the ONLY `| safe` Jinja content introduced anywhere in SB4 is matplotlib-generated SVG bytes (`.decode('utf-8') | safe`). Operator text is auto-escaped.
- **Zero-write invariant (every task):** no task issues an INSERT/UPDATE/DELETE against `trades`, `fills`, `review_log`, `chart_renders`, or any trade-domain table. The only I/O beyond reads is `read_or_fetch_archive` (the pre-existing shared OHLCV read-through cache). A per-slice test asserts no `chart_renders` rows are created by the SB4 paths.

---

### Slice 0 — CR.1 (exit-data + chart snapshot) + shared helper + render lock

**Outcome:** the review page shows exit legs / VWAP / last-exit-date / dollar total-risk / final R, plus a lazy-loaded render-direct closed-trade candlestick chart over the trade window. Builds `trade_charts.py` (`_trade_window_bars` + `render_trade_window_position_svg`) and the process-wide render lock.

#### Task 0.1 — Process-wide matplotlib render lock in `charts.py`

**Files:**
- Modify: `swing/web/charts.py` (add module-level lock + `_serialized_render` decorator; apply to top-level `render_*_svg`)
- Test: `tests/web/test_charts_render_lock.py` (NEW)

- [ ] **Step 1: Write the failing test** — assert the lock exists, is reentrant, and that re-entering on the same thread does NOT deadlock (the R5 M#1 self-deadlock guard).

```python
# tests/web/test_charts_render_lock.py
import swing.web.charts as charts


def test_render_lock_is_reentrant():
    lock = charts._RENDER_LOCK
    assert lock.acquire(blocking=False) is True
    assert lock.acquire(blocking=False) is True  # reentrant -> no deadlock
    lock.release()
    lock.release()


def test_serialized_render_decorator_runs_under_lock():
    seen = []

    @charts._serialized_render
    def fake_render():
        seen.append(charts._RENDER_LOCK.acquire(blocking=False))
        charts._RENDER_LOCK.release()
        return b"<svg/>"

    assert fake_render() == b"<svg/>"
    assert seen == [True]


# Codex R1 M#2: assert EVERY public renderer is wrapped (global coverage,
# R4 M#1) so a future renderer added without the decorator is caught.
_PUBLIC_RENDERERS = (
    "render_watchlist_thumbnail_svg", "render_ticker_detail_svg",
    "render_position_detail_svg", "render_market_weather_svg",
    "render_theme2_annotated_svg",
)  # verified at swing/web/charts.py:492/540/628/752/898 -- re-grep at impl


def test_all_public_renderers_are_serialized():
    import inspect
    # Each public render_*_svg must be wrapped by _serialized_render. The
    # decorator uses functools.wraps, so detect the marker we set on it.
    for name in _PUBLIC_RENDERERS:
        fn = getattr(charts, name)
        assert getattr(fn, "_is_serialized_render", False), \
            f"{name} is not wrapped by _serialized_render"


def test_no_public_renderer_left_undecorated():
    # Guard against a NEW public renderer added later without the decorator.
    import inspect
    for name, fn in inspect.getmembers(charts, inspect.isfunction):
        if name.startswith("render_") and name.endswith("_svg"):
            assert getattr(fn, "_is_serialized_render", False), \
                f"public renderer {name} must be @_serialized_render"
```

- [ ] **Step 2: Run, verify fail** — `python -m pytest tests/web/test_charts_render_lock.py -v` → FAIL (`AttributeError: ... '_RENDER_LOCK'`).

- [ ] **Step 3: Implement the lock + decorator and apply it.**

```python
# swing/web/charts.py  (near the top, after imports)
import functools
import threading

# Process-wide matplotlib render lock. charts.py renders through pyplot GLOBAL
# state (matplotlib.pyplot as plt, mpf.plot, plt.subplots, plt.close) which is
# NOT thread-safe and has no other serialization. Every top-level web render
# path acquires this ONCE at its boundary (Codex R3 M#2 / R4 M#1: process-wide,
# not SB4-only). RLock (reentrant) so a helper that delegates to another
# serialized renderer on the same thread cannot self-deadlock (Codex R5 M#1).
_RENDER_LOCK = threading.RLock()


def _serialized_render(fn):
    """Serialize a top-level SVG renderer under the process-wide render lock."""
    @functools.wraps(fn)
    def _wrapped(*args, **kwargs):
        with _RENDER_LOCK:
            return fn(*args, **kwargs)
    _wrapped._is_serialized_render = True  # marker for the coverage test
    return _wrapped
```

Apply `@_serialized_render` to **ALL FIVE** verified public top-level renderers (Codex R1 M#2): `render_watchlist_thumbnail_svg` (`:492`), `render_ticker_detail_svg` (`:540`), `render_position_detail_svg` (`:628`), `render_market_weather_svg` (`:752`), `render_theme2_annotated_svg` (`:898`) — and re-grep `^def render_.*_svg` at implementation to catch any added since. The two new `trade_charts.py` helpers are also decorated (Tasks 0.3/4.1). Do NOT decorate the private helpers `_render_candles_fig` / `_svg_bytes_from_fig` (they run inside an already-held lock; the single-outer-acquisition rule decorates only the public boundary; the RLock makes the nested `render_position_detail_svg` acquisition from `render_trade_window_position_svg` safe).

- [ ] **Step 3b: Add a parametrized held-lock no-deadlock test** for EVERY public renderer (Codex R1 M#2 — the §M highest-risk lesson demands per-path coverage, not just the decorator). Each renderer is invoked once with the lock ALREADY held on the same thread; it must complete (reentrancy), not block. Stub the matplotlib internals minimally OR feed each renderer a valid planted frame so it produces bytes.

```python
# tests/web/test_charts_render_lock.py  (append)
import pytest

@pytest.mark.parametrize("renderer_name", [
    "render_watchlist_thumbnail_svg", "render_ticker_detail_svg",
    "render_position_detail_svg", "render_market_weather_svg",
    "render_theme2_annotated_svg",
])
def test_public_renderer_no_deadlock_under_held_lock(renderer_name,
                                                     renderer_args_for):
    fn = getattr(charts, renderer_name)
    args, kwargs = renderer_args_for(renderer_name)  # valid planted inputs
    with charts._RENDER_LOCK:            # reentrant: must complete, not block
        out = fn(*args, **kwargs)
    assert out is not None
```

(`renderer_args_for` is a conftest helper returning valid minimal inputs per renderer — planted OHLCV frame + the trade/ticker each needs; grep the existing `tests/web/test_charts.py` for how each renderer is currently exercised and reuse those fixtures.)

- [ ] **Step 4: Run test + full charts suite** — `python -m pytest tests/web/test_charts_render_lock.py tests/web/test_charts.py -q` → PASS (incl. the all-wrapped + per-renderer no-deadlock tests); existing chart tests still green (serialization is behavior-preserving).

- [ ] **Step 5: Commit** — `git commit -m "feat(web): add process-wide matplotlib render lock at the charts.py boundary"`.

**Acceptance:** `_RENDER_LOCK` reentrant; `_serialized_render` (with the `_is_serialized_render` marker) decorates ALL FIVE public `render_*_svg` (the all-wrapped + no-undecorated-renderer tests prove global coverage — R4 M#1); a parametrized held-lock no-deadlock test passes for EVERY public renderer; existing chart tests green; ZERO behavior change beyond serialization; ZERO schema/write.

#### Task 0.2 — `_trade_window_bars` (trade-window archive slice)

**Files:**
- Create: `swing/web/trade_charts.py`
- Test: `tests/web/test_trade_charts_window.py` (NEW)

- [ ] **Step 1: Write the failing test** — coverage, lower-bound slice, no-coverage→None, F6 empty→None. Plant a DataFrame by monkeypatching `read_or_fetch_archive`.

```python
# tests/web/test_trade_charts_window.py
from datetime import date
import pandas as pd
import swing.web.trade_charts as tc


def _archive(idx_dates):
    idx = pd.DatetimeIndex([pd.Timestamp(d) for d in idx_dates])
    return pd.DataFrame(
        {"Open": 1.0, "High": 2.0, "Low": 0.5, "Close": 1.5, "Volume": 100},
        index=idx)


def test_window_slices_lower_bound_and_covers_entry(monkeypatch, cfg_fixture):
    days = pd.date_range("2026-01-01", "2026-03-31", freq="D")
    monkeypatch.setattr(tc, "read_or_fetch_archive", lambda *a, **k: _archive(days))
    out = tc._trade_window_bars(
        ticker="AAA", entry_date=date(2026, 2, 1), exit_date=date(2026, 2, 20),
        cfg=cfg_fixture)
    assert out is not None
    assert out.index.min().date() <= date(2026, 2, 1)   # entry covered
    assert out.index.max().date() <= date(2026, 3, 2)   # exit + 10d


def test_window_none_when_archive_predates_entry(monkeypatch, cfg_fixture):
    days = pd.date_range("2026-02-15", "2026-03-31", freq="D")  # starts after entry
    monkeypatch.setattr(tc, "read_or_fetch_archive", lambda *a, **k: _archive(days))
    assert tc._trade_window_bars(
        ticker="AAA", entry_date=date(2026, 2, 1), exit_date=date(2026, 2, 20),
        cfg=cfg_fixture) is None


def test_window_none_on_empty_archive(monkeypatch, cfg_fixture):
    monkeypatch.setattr(tc, "read_or_fetch_archive", lambda *a, **k: None)
    assert tc._trade_window_bars(
        ticker="AAA", entry_date=date(2026, 2, 1), exit_date=date(2026, 2, 20),
        cfg=cfg_fixture) is None
```

(`cfg_fixture` = a `Config` with a valid `paths.prices_cache_dir` + `archive.archive_history_days`; reuse the existing web conftest config fixture — grep `tests/web/conftest.py` for the established name.)

- [ ] **Step 2: Run, verify fail** — `ModuleNotFoundError: swing.web.trade_charts`.

- [ ] **Step 3: Implement `_trade_window_bars`.**

```python
# swing/web/trade_charts.py
"""Read-only trade-window chart helpers (CR.1 + journal drill-down/thumbnails).

Render-direct over a trade-window archive slice using the SB3 renderers; NEVER
writes chart_renders (closed-trade charts are neither run-bound nor safely
ticker-keyed -- spec §1.2). No candlestick re-implementation.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import TYPE_CHECKING

import pandas as pd

from swing.data.ohlcv_archive import read_or_fetch_archive
from swing.evaluation.dates import last_completed_session
from swing.web.charts import (
    _render_candles_fig,
    _serialized_render,
    _svg_bytes_from_fig,
    render_position_detail_svg,
)

if TYPE_CHECKING:
    from swing.config import Config
    from swing.data.models import Trade

PAD_BEFORE_DAYS = 30  # OQ-1: operator-tunable
PAD_AFTER_DAYS = 10   # OQ-1: operator-tunable


def _today() -> date:
    return last_completed_session(datetime.now())


def _exit_date_for(trade: "Trade", fills) -> date | None:
    """Last non-entry fill's date, or None (open trade / no reducing fill)."""
    reducing = [f for f in fills if f.action != "entry"]
    if not reducing:
        return None
    last = sorted(reducing, key=lambda f: f.fill_datetime)[-1]
    return date.fromisoformat(last.fill_datetime[:10])


def _trade_window_bars(*, ticker, entry_date: date, exit_date: date | None,
                       cfg: "Config",
                       pad_before_days: int = PAD_BEFORE_DAYS,
                       pad_after_days: int = PAD_AFTER_DAYS) -> pd.DataFrame | None:
    """Archive slice [entry-pad_before .. (exit or today)+pad_after].

    Returns FULL archive rows <= window_end (read_or_fetch_archive semantics)
    sliced locally to >= window_start. None when the archive lacks coverage of
    the entry (older than archive depth) or yfinance is empty (F6 -> None).
    """
    window_end = (exit_date or _today()) + timedelta(days=pad_after_days)
    window_start = entry_date - timedelta(days=pad_before_days)
    df = read_or_fetch_archive(
        ticker, end_date=window_end,
        cache_dir=cfg.paths.prices_cache_dir,
        archive_history_days=cfg.archive.archive_history_days)
    if df is None or df.empty:
        return None
    sliced = df[df.index.date >= window_start]
    if sliced.empty:
        return None
    if sliced.index.min().date() > entry_date:  # #29: entry must be visible
        return None
    return sliced
```

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat(web): add _trade_window_bars trade-window archive slice helper"`.

**Acceptance:** lower-bound slice computed locally; no-coverage (empty OR entry-not-covered) → `None`; F6 empty → `None`; reads FULL archive ≤ end_date; ZERO write.

#### Task 0.3 — `render_trade_window_position_svg` (full closed-trade chart, render-direct)

**Files:**
- Modify: `swing/web/trade_charts.py`
- Test: `tests/web/test_trade_charts_render.py` (NEW)

- [ ] **Step 1: Write the failing test** — coverage→`bytes` containing `<svg`; no-coverage→`None`; no-deadlock under held lock; reopened-ticker correctness (render-direct serves each trade's window).

```python
# tests/web/test_trade_charts_render.py
import swing.web.charts as charts
import swing.web.trade_charts as tc


def test_position_svg_returns_svg_bytes(monkeypatch, cfg_fixture,
                                        closed_single_leg_trade, its_fills,
                                        planted_archive):
    monkeypatch.setattr(tc, "read_or_fetch_archive", planted_archive)
    out = tc.render_trade_window_position_svg(
        trade=closed_single_leg_trade, fills=its_fills, cfg=cfg_fixture)
    assert out is not None and b"<svg" in out


def test_position_svg_none_on_no_coverage(monkeypatch, cfg_fixture,
                                          old_closed_trade, its_fills):
    monkeypatch.setattr(tc, "read_or_fetch_archive", lambda *a, **k: None)
    assert tc.render_trade_window_position_svg(
        trade=old_closed_trade, fills=its_fills, cfg=cfg_fixture) is None


def test_position_svg_no_deadlock_under_held_lock(monkeypatch, cfg_fixture,
        closed_single_leg_trade, its_fills, planted_archive):
    monkeypatch.setattr(tc, "read_or_fetch_archive", planted_archive)
    with charts._RENDER_LOCK:  # reentrant: render must complete, not block
        out = tc.render_trade_window_position_svg(
            trade=closed_single_leg_trade, fills=its_fills, cfg=cfg_fixture)
    assert out is not None
```

- [ ] **Step 2: Run, verify fail** — `AttributeError: ... render_trade_window_position_svg`.

- [ ] **Step 3: Implement.**

```python
# swing/web/trade_charts.py  (append)
@_serialized_render
def render_trade_window_position_svg(*, trade: "Trade", fills,
                                     cfg: "Config") -> bytes | None:
    """Full candlestick trade chart over the trade window. Reuses
    charts.render_position_detail_svg. None on no-coverage. Render-direct."""
    entry_date = date.fromisoformat(trade.entry_date[:10])
    exit_date = _exit_date_for(trade, fills)
    bars = _trade_window_bars(
        ticker=trade.ticker, entry_date=entry_date, exit_date=exit_date, cfg=cfg)
    if bars is None:
        return None
    return render_position_detail_svg(
        ticker=trade.ticker, bars=bars, trade=trade, fills=fills,
        current_stop=trade.current_stop)
```

**Re-verify** `render_position_detail_svg`'s exact kwargs at implementation time (`grep -n "def render_position_detail_svg" -A14 swing/web/charts.py`) and match precisely (#10c). If the real signature differs from `(ticker, bars, trade, fills, current_stop)`, adapt and note it in the commit body. (`trade.entry_date` field name — verify it is `entry_date` on `Trade`; grep `models.py`.)

- [ ] **Step 4: Run, verify pass** (incl. the no-deadlock + reopened-ticker assertions).

- [ ] **Step 5: Commit** — `git commit -m "feat(web): render_trade_window_position_svg render-direct closed-trade chart"`.

**Acceptance:** coverage→SVG; no-coverage→`None`; `@_serialized_render` applied (no-deadlock green); reopened-ticker green (cache-collision regression); renderer kwargs verified; ZERO `chart_renders` write.

#### Task 0.4 — ReviewVM exit-data fields + derivations (single + multi-leg arithmetic)

**Files:**
- Modify: `swing/web/view_models/trades.py` (`ReviewVM` + `build_review_vm`; new `ExitLegVM`)
- Test: `tests/web/test_review_vm_exit_data.py` (NEW)

- [ ] **Step 1: Write the failing test** — compute exit VWAP / total_risk / final_R under BOTH single-leg AND multi-leg (`feedback_verify_regression_test_arithmetic`); guard total_risk; exit_date_last.

```python
# tests/web/test_review_vm_exit_data.py
# Single-leg: 100 sh entry @10.00 stop 9.00; exit 100 @12.00
#   total_risk = 100*(10-9) = 100.00 ; exit_vwap = 12.00
# Multi-leg: same entry; exits 60 @11.00 + 40 @13.00
#   exit_vwap = (60*11 + 40*13)/100 = 1180/100 = 11.80 ; total_risk = 100.00
def test_exit_vwap_single_leg(build_review_vm_for, single_leg_closed):
    vm = build_review_vm_for(single_leg_closed)
    assert vm.exit_price_vwap == 12.00
    assert vm.total_risk_dollars == 100.00


def test_exit_vwap_multi_leg(build_review_vm_for, multi_leg_closed):
    vm = build_review_vm_for(multi_leg_closed)
    assert vm.exit_price_vwap == 11.80   # share-weighted, NOT naive mean 12.00
    assert vm.total_risk_dollars == 100.00
    assert len(vm.exit_legs) == 2
    assert (vm.exit_legs[0].quantity, vm.exit_legs[1].quantity) == (60, 40)


def test_total_risk_none_when_stop_inverted(build_review_vm_for, stop_above_entry):
    assert build_review_vm_for(stop_above_entry).total_risk_dollars is None


# Codex R1 M#4: build_review_vm returns None unless trade.state == 'closed'
# (swing/web/view_models/trades.py:1223). The review surface is CLOSED-ONLY, so
# the empty-exit case is tested on the helper directly, NOT via an open trade.
def test_exit_vwap_helper_none_on_empty():
    from swing.web.view_models.trades import _exit_vwap
    assert _exit_vwap([]) is None  # defensive: no reducing fill -> None
```

**CR.1 is closed-only (Codex R1 M#4):** `build_review_vm` returns `None` for any non-`closed` trade (and for already-reviewed trades). The review chart therefore always renders a closed trade — consistent with §4.2's "CR.1 only ever calls the helper on closed trades." Do NOT widen the review page to open trades; do NOT write a VM-level open-trade exit test (it would assert against a `None` VM).

- [ ] **Step 2: Run, verify fail** — attribute missing.

- [ ] **Step 3: Implement** `ExitLegVM` + the fields (safe defaults) + the derivations + the module-level math helpers.

```python
# swing/web/view_models/trades.py
@dataclass(frozen=True)
class ExitLegVM:
    action: str
    fill_date: str       # fill_datetime[:10]
    price: float
    quantity: float
    reason: str | None


# added to ReviewVM (with safe defaults):
    exit_legs: tuple[ExitLegVM, ...] = ()
    exit_price_vwap: float | None = None
    exit_date_last: str | None = None
    total_risk_dollars: float | None = None
    review_chart_url: str | None = None  # Task 0.6


def _exit_vwap(non_entry_fills) -> float | None:
    num = sum(f.price * f.quantity for f in non_entry_fills if f.quantity)
    den = sum(f.quantity for f in non_entry_fills if f.quantity)
    return round(num / den, 4) if den else None


def _total_risk_dollars(trade) -> float | None:
    stop = trade.initial_stop
    if stop is None or not (trade.entry_price > stop):
        return None  # long-only; None on missing/inverted stop
    return round(trade.initial_shares * (trade.entry_price - stop), 2)
```

In `build_review_vm`, after `non_entry_fills` (`:1232`), compute `exit_legs` (sorted by `fill_datetime` ASC), `exit_price_vwap`, `exit_date_last = non_entry_fills_sorted[-1].fill_datetime[:10] if any else None`, `total_risk_dollars`, and pass them to the `ReviewVM(...)` it RETURNS. There are construction sites at `:1293/:1297/:1312` — read `:1280-1325` and add the new kwargs to the returned site(s). (Defaults cover non-returned ones, but prefer explicit.)

- [ ] **Step 4: Run, verify pass.** Existing review tests green.

- [ ] **Step 5: Commit** — `git commit -m "feat(web): surface exit legs, exit VWAP, total-risk-at-open on ReviewVM"`.

**Acceptance:** exit VWAP correct under single+multi-leg (11.80 checks share-weighting); total_risk = dollar-risk-at-open, None on missing/inverted stop; the `_exit_vwap`/`_total_risk_dollars` helpers are the single math source reused in Slice 2; ZERO write.

#### Task 0.5 — Lazy review-chart route `GET /trades/{id}/review/chart`

**Files:**
- Modify: `swing/web/routes/trades.py` (NEW route)
- Create: `swing/web/templates/partials/review_chart.html.j2`
- Test: `tests/web/test_review_chart_route.py` (NEW)

- [ ] **Step 1: Write the failing test** — 200+`<svg`; 200+chart-unavailable; 200+"not found" distinct + WARNING; `Cache-Control: private`; non-HX returns the same fragment.

```python
def test_review_chart_200_svg(client, seeded_closed_trade, monkeypatch):
    monkeypatch.setattr("swing.web.routes.trades.render_trade_window_position_svg",
                        lambda **k: b"<svg></svg>")
    r = client.get(f"/trades/{seeded_closed_trade.id}/review/chart",
                   headers={"HX-Request": "true"})
    assert r.status_code == 200 and "<svg" in r.text
    assert "private" in r.headers.get("cache-control", "")


def test_review_chart_200_unavailable(client, seeded_closed_trade, monkeypatch):
    monkeypatch.setattr("swing.web.routes.trades.render_trade_window_position_svg",
                        lambda **k: None)
    r = client.get(f"/trades/{seeded_closed_trade.id}/review/chart")
    assert r.status_code == 200 and "unavailable" in r.text.lower()


def test_review_chart_200_not_found_distinct(client, caplog):
    r = client.get("/trades/999999/review/chart")
    assert r.status_code == 200 and "not found" in r.text.lower()
    assert any("999999" in rec.message for rec in caplog.records)
```

- [ ] **Step 2: Run, verify fail** — route unregistered / template missing.

- [ ] **Step 3: Implement** the fragment + route (mirror existing route/router/templates/logger names in `routes/trades.py`).

```jinja
{# swing/web/templates/partials/review_chart.html.j2 #}
{% if chart_svg_bytes %}
  <div class="review-chart">{{ chart_svg_bytes.decode('utf-8') | safe }}</div>
{% elif not_found %}
  <span class="chart-unavailable" data-chart-reason="trade-not-found">Trade not found.</span>
{% else %}
  <span class="chart-unavailable" data-chart-reason="no-coverage">Chart unavailable -- trade predates the chart archive.</span>
{% endif %}
```

```python
# swing/web/routes/trades.py  (NEW route)
@router.get("/trades/{trade_id}/review/chart")
def review_chart_fragment(request: Request, trade_id: int):
    cfg = request.app.state.cfg
    with get_conn(cfg) as conn:
        trade = get_trade(conn, trade_id)
        if trade is None:
            log.warning("review chart: trade not found trade_id=%s", trade_id)
            resp = templates.TemplateResponse(
                request, "partials/review_chart.html.j2",
                {"chart_svg_bytes": None, "not_found": True})
            resp.headers["Cache-Control"] = "private, max-age=60"
            return resp
        fills = list_fills_for_trade(conn, trade_id)
    try:
        svg = render_trade_window_position_svg(trade=trade, fills=fills, cfg=cfg)
    except Exception:
        log.warning("review chart render failed trade_id=%s ticker=%s",
                    trade_id, trade.ticker, exc_info=True)
        svg = None
    if svg is None:
        log.warning("review chart unavailable trade_id=%s ticker=%s",
                    trade_id, trade.ticker)
    resp = templates.TemplateResponse(
        request, "partials/review_chart.html.j2",
        {"chart_svg_bytes": svg, "not_found": False})
    resp.headers["Cache-Control"] = "private, max-age=60"
    return resp
```

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat(web): add lazy review-chart fragment route with failure isolation"`.

**Acceptance:** three response contracts (200+SVG / 200+unavailable / 200+not-found-distinct+WARNING); `Cache-Control: private`; render exception isolated (logged, never raised); ZERO write; ASCII-only copy.

#### Task 0.6 — Wire `review_chart_url` + review template chart cell + exit block

**Files:**
- Modify: `swing/web/view_models/trades.py` (`build_review_vm` sets `review_chart_url`)
- Modify: `swing/web/templates/review.html.j2` (or `partials/review_form.html.j2`)
- Test: `tests/web/test_review_page_chart_cell.py` (NEW)

- [ ] **Step 1: Write the failing test.**

```python
def test_review_page_has_lazy_chart_cell(client, seeded_closed_trade):
    r = client.get(f"/trades/{seeded_closed_trade.id}/review")
    assert r.status_code == 200
    assert f'hx-get="/trades/{seeded_closed_trade.id}/review/chart"' in r.text
    assert 'hx-trigger="load"' in r.text
    assert 'hx-headers=\'{"HX-Request": "true"}\'' in r.text
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement.** `build_review_vm`: `review_chart_url=f"/trades/{trade_id}/review/chart"`. Template: exit block + chart cell.

```jinja
{# review.html.j2 #}
<section class="review-exit-data">
  <h3>Exit</h3>
  <p>Final R: <strong>{{ '%.2f' % vm.actual_realized_R_effective }}</strong></p>
  <p>Exit VWAP: {{ ('%.2f' % vm.exit_price_vwap) if vm.exit_price_vwap is not none else 'n/a' }}</p>
  <p>Last exit: {{ vm.exit_date_last or 'open' }}</p>
  <p>Total risk at open: {{ ('$%.2f' % vm.total_risk_dollars) if vm.total_risk_dollars is not none else 'n/a' }}</p>
  <table class="exit-legs">
    <thead><tr><th>Action</th><th>Date</th><th>Qty</th><th>Price</th><th>Reason</th></tr></thead>
    <tbody>
    {% for leg in vm.exit_legs %}
      <tr><td>{{ leg.action }}</td><td>{{ leg.fill_date }}</td><td>{{ leg.quantity }}</td><td>{{ '%.2f' % leg.price }}</td><td>{{ leg.reason or '' }}</td></tr>
    {% endfor %}
    </tbody>
  </table>
  <div class="review-chart-cell" hx-get="{{ vm.review_chart_url }}"
       hx-trigger="load" hx-swap="innerHTML"
       hx-headers='{"HX-Request": "true"}'>
    <span class="chart-loading">Loading chart...</span>
  </div>
</section>
```

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat(web): exit-data block and lazy chart cell on the review page"`.

**Acceptance:** lazy cell with the HTMX trinity attributes; exit block renders all fields (n/a fallbacks); operator text auto-escaped; form renders fully even if the chart fragment fails. **Operator-witnessed gate S3 BINDING.**

**Slice 0 totals:** ~6 tasks, ~6–8 commits, ~14–18 tests (incl. render-lock no-deadlock + single/multi-leg arithmetic).

---

### Slice 1 — BULZ row-expand rewire (independent of 0 and 2–5)

**Outcome:** the dashboard open-position row-expand shows the SB3 `position_detail` candlestick+BULZ-zones SVG (read from the existing cache, mirroring the trade-detail page) instead of the legacy static PNG.

#### Task 1.1 — `position_chart_svg_bytes` on `OpenPositionsExpandedVM` + cache read

**Files:**
- Modify: `swing/web/view_models/open_positions_row.py`
- Test: `tests/web/test_open_positions_expand_chart.py` (NEW)

- [ ] **Step 1: Write the failing test** — VM carries the cached SVG when a `position_detail` row exists for the ticker; `None` when absent.

```python
def test_expand_vm_carries_cached_svg(conn, cfg, seeded_open_trade,
                                      seeded_position_detail_cache):
    vm = build_open_positions_expanded(conn, seeded_open_trade.id, cfg)
    assert vm.position_chart_svg_bytes is not None
    assert b"<svg" in vm.position_chart_svg_bytes


def test_expand_vm_none_when_no_cache_row(conn, cfg, seeded_open_trade):
    vm = build_open_positions_expanded(conn, seeded_open_trade.id, cfg)
    assert vm.position_chart_svg_bytes is None
```

- [ ] **Step 2: Run, verify fail** — attribute missing.

- [ ] **Step 3: Implement.** Add the field (default `None`) and the cache read mirroring `build_trade_detail_vm:1771-1775`:

```python
from swing.data.repos.chart_renders import get_cached_chart_svg
position_chart_svg_bytes = get_cached_chart_svg(
    conn, ticker=trade.ticker, surface="position_detail", pipeline_run_id=None)
```

(Verify `build_open_positions_expanded`'s actual signature — it may take `(conn, trade_id, cfg)` or `(request, trade_id)`; match the real one. No JIT, no write-through.)

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat(web): read position_detail SVG cache into the open-positions expand VM"`.

**Acceptance:** read-only cache read via the exact `build_trade_detail_vm` call (#10c); `None` when absent; ZERO JIT/write.

#### Task 1.2 — Swap the template `<img>` for the SVG

**Files:**
- Modify: `swing/web/templates/partials/open_positions_expanded.html.j2`
- Test: `tests/web/test_open_positions_expand_route.py` (extend / NEW)

- [ ] **Step 1: Write the failing test.**

```python
def test_expand_shows_svg_not_legacy_png(client, seeded_open_trade,
                                         seeded_position_detail_cache):
    r = client.get(f"/trades/open/{seeded_open_trade.id}/expand",
                   headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert ("<svg" in r.text) or ("position-detail-chart" in r.text)
    assert '<img src="/charts/' not in r.text
    assert r.text.lstrip().startswith("<tr")  # synthetic-table-wrap rule
```

- [ ] **Step 2: Run, verify fail** — legacy `<img>` still present.

- [ ] **Step 1b: Add the cache-miss no-blank test** (Codex R1 M#3) — the legacy `chart_reason`/`chart_reason_message` come from the static-PNG chart scope (`resolve_chart_scope`, `open_positions_row.py:368`), NOT the `position_detail` SVG cache. So `chart_reason is None` (PNG-scope says "available") can co-occur with `position_chart_svg_bytes is None` (no SVG cache row) → the naive `{% if svg %}{% elif chart_reason_message %}` would render BLANK. The template MUST have a terminal `{% else %}` fallback.

```python
def test_expand_no_blank_when_svg_cache_missing(client, seeded_open_trade):
    # chart_reason resolves "available" (PNG scope) but the position_detail
    # SVG cache row is absent -> must show a fallback, never blank.
    r = client.get(f"/trades/open/{seeded_open_trade.id}/expand",
                   headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert ("<svg" in r.text) or ("chart-unavailable" in r.text)  # never blank
```

- [ ] **Step 3: Implement** the template swap (inside the existing `<td colspan>`) with a TERMINAL else fallback so a cache miss never renders blank:

```jinja
{% if expanded.position_chart_svg_bytes %}
  <div class="position-detail-chart">{{ expanded.position_chart_svg_bytes.decode('utf-8') | safe }}</div>
{% elif expanded.chart_reason_message %}
  <div class="chart-unavailable" data-chart-reason="{{ expanded.chart_reason }}">{{ expanded.chart_reason_message }}</div>
{% else %}
  <div class="chart-unavailable" data-chart-reason="position-detail-cache-miss">Position chart unavailable.</div>
{% endif %}
```

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat(web): inline position_detail SVG in the open-positions row-expand"`.

**Acceptance:** SVG present, legacy `<img>` gone, fragment root still `<tr>`; **a cache miss shows the terminal fallback, never blank** (M#3); `| safe` only on generated SVG. **Operator-witnessed gate S6 BINDING.**

#### Task 1.3 — Reopened-ticker safety test + L7 reversal note

**Files:**
- Test: `tests/web/test_open_positions_expand_route.py` (extend)
- Modify: the chart-access UX brief (dated L7 reversal note)

- [ ] **Step 1: Write the test** — the row-expand reflects the CURRENT open trade's chart given a reopened ticker (one closed + one open, same ticker); the single `position_detail` row IS the open trade's chart (one-open-trade-per-ticker invariant, M#12).

```python
def test_reopened_ticker_expand_uses_open_trade_chart(client,
        closed_then_reopened_same_ticker, seeded_position_detail_cache_for_open):
    open_trade = closed_then_reopened_same_ticker.open
    r = client.get(f"/trades/open/{open_trade.id}/expand",
                   headers={"HX-Request": "true"})
    assert r.status_code == 200 and "<svg" in r.text
```

- [ ] **Step 2: Run, verify pass** (regression guard; no impl change).

- [ ] **Step 3: Add the L7 reversal note** to the chart-access UX brief (grep `docs/` for the brief that put position-detail on a separate page; add a dated note: "2026-05-30 (SB4): the open-positions row-expand now inlines the `position_detail` SVG, reversing the §2 separate-page decision for this surface").

- [ ] **Step 4: Commit** — `git commit -m "docs: record the L7 chart-access reversal for the BULZ row-expand"` (or fold the note into Task 1.2 and keep this task test-only).

**Acceptance:** reopened-ticker test green; L7 note dated + committed; **ESCALATE** if the data model is ever found to permit two concurrently-open trades per ticker (it does not today).

**Slice 1 totals:** ~3 tasks, ~3 commits, ~5–8 tests.

---

### Slice 2 — Journal listing substrate (SERIAL: 2→3→4→5)

**Outcome:** `GET /journal` renders a paginated rich table (open price, shares, dollar total-risk, closing price, final R, entry-time flags) per trade. No charts, no sort/filter yet — pure data + template, fully testable without matplotlib.

#### Task 2.1 — `JournalRowVM` dataclass + per-trade enrichment in `build_journal`

**Files:**
- Modify: `swing/web/view_models/journal.py` (`JournalRowVM` + `build_journal` enrichment; import the math helpers from `view_models/trades.py`)
- Test: `tests/web/test_journal_rows.py` (NEW)

**Math-source note (phase isolation):** reuse `_exit_vwap` + `_total_risk_dollars` from `swing/web/view_models/trades.py` (Task 0.4) and `compute_actual_realized_R_effective` from `swing/trades/review.py` (read-only consume). Do NOT add a helper under `swing/trades/` (that would be a phase-isolation carve-out); keep the new math in the web view-model layer.

- [ ] **Step 1: Write the failing test** — a `JournalRowVM` per trade with correct open_price/shares/total_risk (dollar)/closing_price (VWAP, None for open)/final_r (None for open)/entry flags; `has_hyprec_link` from `trade_origin`, NOT `candidate_id`.

```python
# tests/web/test_journal_rows.py
def test_journal_row_fields_closed_single_leg(build_journal_for, single_leg_closed):
    vm = build_journal_for(period="all")
    row = next(r for r in vm.rows if r.trade_id == single_leg_closed.id)
    assert row.open_price == 10.00
    assert row.shares == 100
    assert row.total_risk_dollars == 100.00
    assert row.closing_price == 12.00     # single-leg VWAP
    assert round(row.final_r, 4) is not None


def test_journal_row_open_trade_has_none_exit(build_journal_for, open_trade):
    vm = build_journal_for(period="all")
    row = next(r for r in vm.rows if r.trade_id == open_trade.id)
    assert row.closing_price is None and row.final_r is None


def test_has_hyprec_link_from_origin_not_candidate(build_journal_for,
        aplus_trade_with_candidate, hyprec_trade):
    vm = build_journal_for(period="all")
    aplus = next(r for r in vm.rows if r.trade_id == aplus_trade_with_candidate.id)
    hyp = next(r for r in vm.rows if r.trade_id == hyprec_trade.id)
    assert aplus.has_hyprec_link is False   # A+ is candidate-backed but NOT hyp-rec
    assert hyp.has_hyprec_link is True      # trade_origin == pipeline_watch_hyp_recs


def test_entry_flags_none_safe(build_journal_for, trade_no_candidate):
    vm = build_journal_for(period="all")
    row = next(r for r in vm.rows if r.trade_id == trade_no_candidate.id)
    assert row.aplus_bucket is None and row.chart_pattern is None
```

- [ ] **Step 2: Run, verify fail** — `JournalVM` has no `rows`.

- [ ] **Step 3: Implement.**

```python
# swing/web/view_models/journal.py
from swing.web.view_models.trades import _exit_vwap, _total_risk_dollars

@dataclass(frozen=True)
class JournalRowVM:
    trade_id: int
    ticker: str
    entry_date: str
    state: str
    open_price: float                 # trade.entry_price
    shares: int                       # trade.initial_shares
    total_risk_dollars: float | None  # initial_shares*(entry_price-initial_stop)
    closing_price: float | None       # VWAP exit (None for open trades)
    final_r: float | None             # compute_actual_realized_R_effective (None=open)
    chart_pattern: str | None         # chart_pattern_operator|_algo|pattern_class
    aplus_bucket: str | None          # candidates.bucket via candidate_id
    hypothesis_label: str | None      # trade.hypothesis_label
    has_hyprec_link: bool             # trade_origin == 'pipeline_watch_hyp_recs'
```

Add `rows: tuple[JournalRowVM, ...] = ()` to `JournalVM`. In `build_journal`, inside the existing `with conn:`: load `all_fills = list_all_fills(conn)` once, group non-entry fills by `trade_id` (dict). Batch the entry-flag joins: collect `{t.candidate_id for t in filtered if t.candidate_id}` → one SELECT `bucket, pattern_tag FROM candidates WHERE id IN (...)`; `{t.pattern_evaluation_id ...}` → one SELECT `pattern_class FROM pattern_evaluations WHERE id IN (...)`. Short-circuit empty IN sets (no `IN ()`). Build one `JournalRowVM` per filtered trade:

```python
def _row_for(trade, fills_by_trade, bucket_by_cid, pclass_by_peid):
    reducing = fills_by_trade.get(trade.id, [])
    exits = tuple(_fill_to_exit_like(f, trade) for f in reducing)  # reuse adapter
    closing = _exit_vwap(reducing)
    final_r = (compute_actual_realized_R_effective(trade, list(exits))
               if trade.state in ("closed", "reviewed") and reducing else None)
    chart_pattern = (trade.chart_pattern_operator or trade.chart_pattern_algo
                     or pclass_by_peid.get(trade.pattern_evaluation_id))
    return JournalRowVM(
        trade_id=trade.id, ticker=trade.ticker, entry_date=trade.entry_date,
        state=trade.state, open_price=trade.entry_price,
        shares=trade.initial_shares,
        total_risk_dollars=_total_risk_dollars(trade),
        closing_price=closing, final_r=final_r,
        chart_pattern=chart_pattern,
        aplus_bucket=bucket_by_cid.get(trade.candidate_id),
        hypothesis_label=trade.hypothesis_label,
        has_hyprec_link=(trade.trade_origin == "pipeline_watch_hyp_recs"))
```

Pass `rows=tuple(_row_for(t, ...) for t in filtered)` into `JournalVM(...)`. (`_fill_to_exit_like` is the existing review adapter — import it; or reuse `_ExitShape` grouping already present. Verify `list_all_fills` import + signature; verify `compute_actual_realized_R_effective` import path.)

- [ ] **Step 4: Run, verify pass.** Existing journal tests green.

- [ ] **Step 5: Commit** — `git commit -m "feat(web): build per-trade JournalRowVM rows with entry flags and exit derivations"`.

**Acceptance:** rows carry all fields; `has_hyprec_link` from `trade_origin` (A+/manual NOT mislabeled — the M#2 regression); entry flags None-safe; batched joins (no N+1); closing_price/final_r reuse the single math source; ZERO write; single+multi-leg closing_price covered (multi-leg fixture asserts VWAP).

#### Task 2.2 — Pagination in `build_journal` + route params

**Files:**
- Modify: `swing/web/view_models/journal.py` (`build_journal` accepts `page`/`page_size`; `JournalVM` carries pagination fields)
- Modify: `swing/web/routes/journal.py` (`journal_page` passes `page`/`page_size`; loosen `period` to `str`)
- Test: `tests/web/test_journal_pagination.py` (NEW)

- [ ] **Step 1: Write the failing test** — page_size bounds rows; page 2 returns the next slice; page_size clamped to a max; `period` out-of-allowlist no longer 422s (returns the in-page path).

```python
def test_pagination_bounds_rows(build_journal_for):
    vm = build_journal_for(period="all", page=1, page_size=20)
    assert len(vm.rows) <= 20
    assert vm.page == 1 and vm.page_size == 20


def test_page_size_clamped_to_max(build_journal_for):
    vm = build_journal_for(period="all", page=1, page_size=10_000)
    assert vm.page_size <= 50  # MAX_PAGE_SIZE


def test_period_str_not_literal_422(client):
    # An out-of-allowlist period reaches app code (no FastAPI 422), returning
    # the page with a corrected default rather than a framework 422.
    r = client.get("/journal?period=bogus")
    assert r.status_code == 200
```

- [ ] **Step 2: Run, verify fail** — `period=bogus` 422s (Literal) / `JournalVM` has no `page`.

- [ ] **Step 3: Implement.** Constants `DEFAULT_PAGE_SIZE = 22`, `MAX_PAGE_SIZE = 50` (the ~20-25 band; the single page-size figure governs §5.3). `build_journal(*, cfg, period="month", page=1, page_size=DEFAULT_PAGE_SIZE, sort=None, dir=None, filter_state=None, filter_pattern=None)`. Validate `period` against `_ALLOWED_PERIODS` and FALL BACK to `"month"` (do NOT raise — the route must not 500/422); clamp `page_size` to `MAX_PAGE_SIZE`; slice `rows` to the page window; add `page`, `page_size`, `total_rows`, `has_next` to `JournalVM`. In the route, type `period: str = Query("month")` (drop `Literal`), add `page: int`, `page_size: int`.

```python
# routes/journal.py
from typing import Optional  # (or builtin str | None)
def journal_page(request: Request, period: str = Query("month"),
                 page: int = Query(1), page_size: int = Query(DEFAULT_PAGE_SIZE)):
    cfg = request.app.state.cfg
    vm = build_journal(cfg=cfg, period=period, page=page, page_size=page_size)
    return templates.TemplateResponse(request, "journal.html.j2", {"vm": vm})
```

(Note: `build_journal` currently RAISES on an unknown period (`:137`). Change that to clamp-to-default so a bad `period` query renders the page, not a 500 — Codex Re-R2 m#2 intent extends to the listing route, not only sort/filter.)

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat(web): paginate the journal listing and loosen the period param to str"`.

**Acceptance:** page/page_size bound + clamp; bad `period` no longer 422s (clamps to default); default page size in the ~20-25 band; ZERO write.

#### Task 2.3 — Redesigned `journal.html.j2` rich table + `journal_row.html.j2`

**Files:**
- Modify: `swing/web/templates/journal.html.j2`
- Create: `swing/web/templates/partials/journal_row.html.j2`
- Test: `tests/web/test_journal_listing_render.py` (NEW)

- [ ] **Step 1: Write the failing test** — the listing renders a `<table id="journal-table">` with the rich columns + a drill-down `<a href="/journal/trades/{id}">` per row + dollar total-risk + the flag columns; pagination controls present.

```python
def test_journal_listing_rich_columns(client, seeded_mixed_trades):
    r = client.get("/journal?period=all")
    assert r.status_code == 200
    assert 'id="journal-table"' in r.text
    assert "Total risk" in r.text and "Final R" in r.text
    assert 'href="/journal/trades/' in r.text  # drill-down link
```

- [ ] **Step 2: Run, verify fail** — old 3-column table.

- [ ] **Step 3: Implement.** Replace the `<section class="trades">` table with a `<table id="journal-table">` whose `<thead>` carries sortable column headers (sort controls wired in Slice 3) + a filter control row, `<tbody>` includes `journal_row.html.j2` per `vm.rows`, plus pagination links. `journal_row.html.j2` renders one `<tr>` with a placeholder `<td class="journal-thumb">` (thumbnail wired in Slice 4) and the drill-down link. ALL operator/derived text auto-escaped; n/a fallbacks for `None`:

```jinja
{# partials/journal_row.html.j2 #}
{# Codex WP-R2 M#1: a macro imported in journal.html.j2 is NOT visible inside an
   {% include %}d partial -- the partial MUST import it itself (matches the
   existing journal.html.j2 import line). Verify the macro export name is
   `render` at implementation. #}
{% from "partials/state_badge.html.j2" import render as state_badge %}
<tr data-trade-id="{{ row.trade_id }}">
  <td class="journal-thumb" data-trade-id="{{ row.trade_id }}"></td>
  <td><a href="/journal/trades/{{ row.trade_id }}">{{ row.ticker }}</a></td>
  <td>{{ row.entry_date }}</td>
  <td>{{ state_badge(row.state) }}</td>
  <td>{{ '%.2f' % row.open_price }}</td>
  <td>{{ row.shares }}</td>
  <td>{{ ('$%.2f' % row.total_risk_dollars) if row.total_risk_dollars is not none else 'n/a' }}</td>
  <td>{{ ('%.2f' % row.closing_price) if row.closing_price is not none else 'open' }}</td>
  <td>{{ ('%.2f' % row.final_r) if row.final_r is not none else 'open' }}</td>
  <td>{{ row.chart_pattern or '' }}</td>
  <td>{{ row.aplus_bucket or '' }}</td>
  <td>{{ 'hyp-rec' if row.has_hyprec_link else '' }}{% if row.hypothesis_label %} ({{ row.hypothesis_label }}){% endif %}</td>
</tr>
```

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat(web): redesign the journal listing into a rich per-trade table"`.

**Acceptance:** rich columns render with n/a/open fallbacks; drill-down links present; thumbnail cell is a placeholder (Slice 4); operator text escaped; **Operator-witnessed gate S4 (rows + flags) is BINDING** (thumbnails/sort wired later).

**Slice 2 totals:** ~3 tasks, ~4–6 commits, ~12–18 tests.

---

### Slice 3 — Sort / filter (database-browsing; HTMX whole-`<table>` swap)

**Outcome:** the listing is sortable + filterable via HTMX server-side re-render of the whole `<table>` (`outerHTML` swap), with allowlist-validated params and an in-page error fragment on bad input.

#### Task 3.1 — Sort/filter in `build_journal` (server-side, allowlist-validated)

**Files:**
- Modify: `swing/web/view_models/journal.py` (`build_journal` applies sort + filter before pagination)
- Test: `tests/web/test_journal_sort_filter.py` (NEW)

- [ ] **Step 1: Write the failing test** — sort by `final_r` desc orders rows; `filter_state='reviewed'` returns only `state=='reviewed'`; `filter_pattern='vcp'` narrows; bad `sort`/`filter_*` falls back to default + sets an `invalid_filter` flag on the VM (no raise).

```python
def test_sort_by_final_r_desc(build_journal_for):
    vm = build_journal_for(period="all", sort="final_r", dir="desc")
    finals = [r.final_r for r in vm.rows if r.final_r is not None]
    assert finals == sorted(finals, reverse=True)


def test_filter_state_reviewed(build_journal_for):
    vm = build_journal_for(period="all", filter_state="reviewed")
    assert all(r.state == "reviewed" for r in vm.rows)


def test_bad_sort_falls_back_and_flags(build_journal_for):
    vm = build_journal_for(period="all", sort="; DROP TABLE")
    assert vm.invalid_filter is True
    assert vm.rows is not None  # unfiltered/default set still returned
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement.** Frozensets `_SORT_KEYS = frozenset({"entry_date","ticker","final_r","total_risk_dollars","state"})`, `_DIRS = frozenset({"asc","desc"})`, `_FILTER_STATES = frozenset({"entered","managing","partial_exited","closed","reviewed","open","closed_any"})` (where `open`→`{entered,managing,partial_exited}`, `closed_any`→`{closed,reviewed}`), `_FILTER_PATTERNS = frozenset({"vcp","flat_base","cup_with_handle","high_tight_flag","double_bottom_w"})`, and (Codex R1 M#5 — the spec §5.2 "has-A+ flag" filter) `_FILTER_APLUS = frozenset({"aplus","non_aplus"})` where `aplus`→`row.aplus_bucket == "aplus"` and `non_aplus`→`row.aplus_bucket != "aplus"`. In `build_journal`: validate each; on any out-of-allowlist value set `invalid_filter=True`, log a WARNING, and use the default (no raise). Apply filters (state, pattern, A+) to `filtered` rows, then sort (None-last for `final_r`/`total_risk_dollars`), then paginate. Add `invalid_filter: bool = False`, `sort`, `dir`, `filter_state`, `filter_pattern`, `filter_aplus`, and `query_state: dict` (the set-only current params, for URL preservation per WP-R2 M#5) to `JournalVM`.

  Add a has-A+ filter test:

```python
def test_filter_aplus_includes_excludes(build_journal_for, aplus_trade_with_candidate):
    incl = build_journal_for(period="all", filter_aplus="aplus")
    assert all(r.aplus_bucket == "aplus" for r in incl.rows)
    excl = build_journal_for(period="all", filter_aplus="non_aplus")
    assert all(r.aplus_bucket != "aplus" for r in excl.rows)
```

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat(web): server-side allowlist-validated sort and filter for the journal"`.

**Acceptance:** sort/filter correct; `filter_state='reviewed'` == `state=='reviewed'` (coupled to `complete_trade_review` per R2 M#6); bad input → default + `invalid_filter` flag + WARNING (no raise/500); ZERO write.

#### Task 3.2 — Sort/filter HTMX route (whole-`<table>` `outerHTML` swap) + in-page error fragment

**Files:**
- Modify: `swing/web/routes/journal.py` (`journal_page` accepts `sort`/`dir`/`filter_state`/`filter_pattern`/`filter_aplus` as `str | None`; renders the `<table>`-rooted fragment for HX requests)
- Modify: `swing/web/templates/journal.html.j2` (the `<table>` extracted into an includable partial OR a `{% if request_is_htmx %}` fragment branch; header sort controls + filter `<select>`s carry `hx-headers` HX-Request)
- Test: `tests/web/test_journal_sortfilter_route.py` (NEW)

- [ ] **Step 1: Write the failing test** — an HX GET with `sort`/`filter_*` returns a fragment whose root is `<table id="journal-table">` (NOT a bare `<tr>`); the sort controls carry `hx-get` + `hx-target="#journal-table"` + `hx-swap="outerHTML"` + `hx-headers` HX-Request; a bad `sort` returns the in-page table fragment with an "invalid filter" notice (NOT a bare 400).

```python
def test_sortfilter_returns_table_rooted_fragment(client, seeded_mixed_trades):
    r = client.get("/journal?sort=final_r&dir=desc",
                   headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert r.text.lstrip().startswith("<table")
    assert 'id="journal-table"' in r.text


def test_sort_controls_have_htmx_attrs(client, seeded_mixed_trades):
    r = client.get("/journal?period=all")
    assert 'hx-target="#journal-table"' in r.text
    assert 'hx-swap="outerHTML"' in r.text
    assert 'hx-headers=\'{"HX-Request": "true"}\'' in r.text


def test_bad_filter_returns_inpage_notice_not_400(client):
    r = client.get("/journal?sort=bogus", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "invalid filter" in r.text.lower()
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement.** Detect HX via the request header (the codebase's existing `HX-Request` check — grep for the established helper). For HX requests, render ONLY the `<table id="journal-table">...</table>` partial (a `journal_table.html.j2` extracted from `journal.html.j2`, included by both the full page and the fragment path) so the fragment root is the `<table>` (no bare `<tr>` → synthetic-table-wrap cannot fire). The full-page render `{% include "partials/journal_table.html.j2" %}`. Route params `sort/dir/filter_state/filter_pattern/filter_aplus: str | None = Query(None)` (M#5), passed to `build_journal`. When `vm.invalid_filter`, the table partial shows a visible "invalid filter, showing all" notice (driven by `vm.invalid_filter`).

**Query-state preservation (Codex WP-R2 M#5).** A sort link that carries only `sort`/`dir`/`period` would DROP the active `filter_state`/`filter_pattern`/`filter_aplus` on click — violating the S4 "selected filter persists" gate. Every sort/filter control URL MUST be built from the FULL current query state. Expose the current params on the VM as a `query_state: dict` (period, sort, dir, filter_state, filter_pattern, filter_aplus — only the set ones) and build each control's URL by overriding ONLY the one param it changes, carrying the rest. A small Jinja helper or a precomputed `sort_urls`/`filter_urls` dict on the VM is cleaner than string-concatenation in the template.

```jinja
{# header sort control example, inside journal_table.html.j2 -- carries ALL
   active filters via vm.query_state so sorting does not drop the filter set #}
{% set _q = vm.query_state %}
<th><a hx-get="/journal?period={{ _q.period }}&sort=final_r&dir=desc{% if _q.filter_state %}&filter_state={{ _q.filter_state }}{% endif %}{% if _q.filter_pattern %}&filter_pattern={{ _q.filter_pattern }}{% endif %}{% if _q.filter_aplus %}&filter_aplus={{ _q.filter_aplus }}{% endif %}"
       hx-target="#journal-table" hx-swap="outerHTML"
       hx-headers='{"HX-Request": "true"}'>Final R</a></th>
```

Add a test asserting sort-after-filter preserves the filter:

```python
def test_sort_link_preserves_active_filters(client, seeded_mixed_trades):
    r = client.get("/journal?filter_state=reviewed&filter_aplus=aplus",
                   headers={"HX-Request": "true"})
    # the rendered sort controls must carry the active filters forward
    assert "filter_state=reviewed" in r.text
    assert "filter_aplus=aplus" in r.text
```

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat(web): HTMX whole-table sort/filter swap for the journal listing"`.

**Acceptance:** fragment root is `<table>` (OQ-9 whole-`<table>` `outerHTML`; synthetic-table-wrap dodged); controls carry the HTMX trinity attrs; bad input → in-page notice (not bare 400); whole-page and fragment share the SAME `{% include %}` (no hand-duplicated markup — the OOB-drift gotcha); **Operator-witnessed gate S4 (sort/filter focus/scroll/control persistence) BINDING.**

**Slice 3 totals:** ~2 tasks, ~3–4 commits, ~10–14 tests.

---

### Slice 4 — Candlestick thumbnails (lazy, on-scroll)

**Outcome:** each journal listing row shows a small **candlestick** thumbnail that loads only when scrolled into view (`hx-trigger="revealed"`), bounding the render-lock queue.

#### Task 4.1 — `render_trade_window_thumbnail_svg`

**Files:**
- Modify: `swing/web/trade_charts.py`
- Test: `tests/web/test_trade_charts_thumbnail.py` (NEW)

- [ ] **Step 1: Write the failing test** — coverage→`<svg` bytes; no-coverage→`None`; no title (thumbnails unlabeled → ASCII-mathtext N/A); no-deadlock under held lock.

```python
import swing.web.charts as charts
import swing.web.trade_charts as tc


def test_thumbnail_returns_svg(monkeypatch, cfg_fixture, closed_single_leg_trade,
                               its_fills, planted_archive):
    monkeypatch.setattr(tc, "read_or_fetch_archive", planted_archive)
    out = tc.render_trade_window_thumbnail_svg(
        trade=closed_single_leg_trade, fills=its_fills, cfg=cfg_fixture)
    assert out is not None and b"<svg" in out


def test_thumbnail_none_on_no_coverage(monkeypatch, cfg_fixture, old_closed_trade,
                                       its_fills):
    monkeypatch.setattr(tc, "read_or_fetch_archive", lambda *a, **k: None)
    assert tc.render_trade_window_thumbnail_svg(
        trade=old_closed_trade, fills=its_fills, cfg=cfg_fixture) is None


def test_thumbnail_no_deadlock_under_lock(monkeypatch, cfg_fixture,
        closed_single_leg_trade, its_fills, planted_archive):
    monkeypatch.setattr(tc, "read_or_fetch_archive", planted_archive)
    with charts._RENDER_LOCK:
        out = tc.render_trade_window_thumbnail_svg(
            trade=closed_single_leg_trade, fills=its_fills, cfg=cfg_fixture)
    assert out is not None
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement.** Thumbnail uses `_render_candles_fig` at a small figsize, `ma_windows=(10, 20)`, NO fill markers; serialize the body under the lock. **The verified live signature (Codex R1 M#1) is `_render_candles_fig(df, *, ma_windows, figsize, volume=True, style="yahoo") -> (fig, price_ax, vol_ax)` (`swing/web/charts.py:412-419`) — there is NO `title` parameter and it returns a 3-TUPLE.** `df` MUST be `_normalize_ohlc_for_mpf` output (verify that helper at implementation and apply it to `bars` first); `ma_windows` values must exist in `_MA_COLORS` (10 and 20 are present — verify). Unpack the 3-tuple; pass only `fig` to `_svg_bytes_from_fig`.

```python
# swing/web/trade_charts.py  (append)
from swing.web.charts import _normalize_ohlc_for_mpf  # verify exact name/location

@_serialized_render
def render_trade_window_thumbnail_svg(*, trade: "Trade", fills,
                                      cfg: "Config") -> bytes | None:
    """Small candlestick thumbnail over the trade window (no markers). Open
    trades use the trailing window (exit_date None). None on no-coverage.
    Render-direct; no chart_renders write."""
    entry_date = date.fromisoformat(trade.entry_date[:10])
    exit_date = _exit_date_for(trade, fills)
    bars = _trade_window_bars(
        ticker=trade.ticker, entry_date=entry_date, exit_date=exit_date, cfg=cfg)
    if bars is None:
        return None
    norm = _normalize_ohlc_for_mpf(bars)               # mpf-ready frame
    fig, _price_ax, _vol_ax = _render_candles_fig(     # 3-tuple, NO title kwarg
        norm, ma_windows=(10, 20), figsize=(2.4, 1.4), volume=True)
    return _svg_bytes_from_fig(fig)
```

**Re-verify at implementation** the exact names `_render_candles_fig` / `_normalize_ohlc_for_mpf` / `_svg_bytes_from_fig` and that `figsize=(2.4, 1.4)` produces a usable thumbnail (mplfinance has a minimum sensible size; bump if it errors). The thumbnail is unlabeled because `_render_candles_fig` emits no title/axis labels of its own beyond the SB3 renderers' ASCII-clean ones — so there is no new mathtext surface. Do NOT introduce any non-ASCII label.

- [ ] **Step 4: Run, verify pass** (incl. no-deadlock).

- [ ] **Step 5: Commit** — `git commit -m "feat(web): render_trade_window_thumbnail_svg small candlestick thumbnail"`.

**Acceptance:** coverage→SVG; no-coverage→`None`; no title (mathtext N/A); `@_serialized_render` (no-deadlock green); ZERO write.

#### Task 4.2 — `GET /journal/trades/{id}/thumbnail` fragment route + memo

**Files:**
- Modify: `swing/web/routes/journal.py` (NEW route)
- Create: `swing/web/templates/partials/journal_thumbnail.html.j2`
- Test: `tests/web/test_journal_thumbnail_route.py` (NEW)

- [ ] **Step 1: Write the failing test** — 200+`<svg` on coverage; 200+unavailable `<span>` on no-coverage; 200+"not found" on missing trade (NOT a table element → no wrap hazard); `Cache-Control: private`; request-lifetime memo dedupes a double render in one request.

```python
def test_thumbnail_200_svg(client, seeded_closed_trade, monkeypatch):
    monkeypatch.setattr("swing.web.routes.journal.render_trade_window_thumbnail_svg",
                        lambda **k: b"<svg></svg>")
    r = client.get(f"/journal/trades/{seeded_closed_trade.id}/thumbnail",
                   headers={"HX-Request": "true"})
    assert r.status_code == 200 and "<svg" in r.text
    assert "private" in r.headers.get("cache-control", "")


def test_thumbnail_200_unavailable(client, seeded_closed_trade, monkeypatch):
    monkeypatch.setattr("swing.web.routes.journal.render_trade_window_thumbnail_svg",
                        lambda **k: None)
    r = client.get(f"/journal/trades/{seeded_closed_trade.id}/thumbnail")
    assert r.status_code == 200 and "unavailable" in r.text.lower()


def test_thumbnail_200_not_found(client, caplog):
    r = client.get("/journal/trades/999999/thumbnail")
    assert r.status_code == 200 and "not found" in r.text.lower()


def test_thumbnail_busy_when_semaphore_exhausted(client, seeded_closed_trade,
                                                 caplog):
    # Codex WP-R2 M#4: force the semaphore to time out by holding all permits,
    # then assert the 200+busy contract: busy body, no-store cache, self-retry
    # trigger, structured WARNING, and that permits are released afterward.
    import swing.web.routes.journal as J
    J._THUMBNAIL_RENDER_SEMAPHORE.acquire()
    J._THUMBNAIL_RENDER_SEMAPHORE.acquire()  # both permits held (BoundedSemaphore(2))
    try:
        r = client.get(f"/journal/trades/{seeded_closed_trade.id}/thumbnail",
                       headers={"HX-Request": "true"})
    finally:
        J._THUMBNAIL_RENDER_SEMAPHORE.release()
        J._THUMBNAIL_RENDER_SEMAPHORE.release()
    assert r.status_code == 200
    assert 'data-chart-reason="busy"' in r.text
    assert 'hx-trigger="load delay' in r.text          # self-retry present
    assert r.headers.get("cache-control") == "no-store"  # not cacheable
    assert any("busy" in rec.message for rec in caplog.records)
    # Permits fully released after the request (no leak).
    assert J._THUMBNAIL_RENDER_SEMAPHORE.acquire(blocking=False) is True
    J._THUMBNAIL_RENDER_SEMAPHORE.release()
```

(Use a short semaphore `timeout` in tests OR monkeypatch it down so the busy test does not wait 2s; the timeout value is a module constant.)

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement** the fragment + route (structurally identical to the review-chart route, §C.1).

  **Explicit render-concurrency bound (Codex R1 M#6 — the spec §5.3(c) contract).** The process-wide render LOCK serializes matplotlib but does NOT bound how many request workers PILE UP waiting behind it on a fast scroll — a burst of `revealed` triggers could queue many blocked workers. Add an explicit module-level **render semaphore** (`_THUMBNAIL_RENDER_SEMAPHORE = threading.BoundedSemaphore(2)`) acquired with a SHORT timeout around the render call; on timeout, return the 200+unavailable fragment with a `data-chart-reason="busy"` (the client may re-trigger on next reveal) rather than blocking a worker indefinitely. This caps concurrent thumbnail renders independent of the page-size/`revealed` bound and prevents the self-inflicted DoS the spec flags. (Reusing `app.state.price_fetch_executor` is the documented alternative; the bounded semaphore is simpler and sufficient for a single-operator box.)

  ```python
  import threading
  _THUMBNAIL_RENDER_SEMAPHORE = threading.BoundedSemaphore(2)
  # in the route, around the render:
  if not _THUMBNAIL_RENDER_SEMAPHORE.acquire(timeout=2.0):
      log.warning("thumbnail render busy trade_id=%s", trade_id)
      resp = templates.TemplateResponse(
          request, "partials/journal_thumbnail.html.j2",
          {"chart_svg_bytes": None, "not_found": False, "busy": True,
           "trade_id": trade_id})
      # Codex WP-R2 M#3: the busy state is transient backpressure -- it must NOT
      # be cached, or the browser would replay "busy" instead of retrying.
      resp.headers["Cache-Control"] = "no-store"
      return resp
  try:
      svg = render_trade_window_thumbnail_svg(trade=trade, fills=fills, cfg=cfg)
  finally:
      _THUMBNAIL_RENDER_SEMAPHORE.release()
  # success / unavailable / not-found responses keep Cache-Control: private, max-age=<short>
  ```

  **Memo scope (Codex R1 m#2 correction).** The thumbnail endpoint serves ONE trade per request, so a cross-request memo is NOT used (and the bare-`trade_id` cross-request memo is forbidden per R2 M#3). There is no meaningful within-request double-render to dedupe here either — so the thumbnail route carries NO memo; the freshness discipline note (no cross-request bare-`trade_id` cache) and the v24 persisted trade-keyed cache remain the banked escalation if profiling demands it. (The request-lifetime memo concept applies only where a single request renders the same trade's chart more than once — not this route.)

```jinja
{# partials/journal_thumbnail.html.j2 #}
{# Codex WP-R2 M#2: the `revealed` trigger already fired on the cell, so a busy
   fragment that does not re-trigger would strand the thumbnail until a full
   table rerender. The busy span SELF-RETRIES with a bounded backoff delay so it
   recovers to the SVG once the semaphore frees. #}
{% if chart_svg_bytes %}{{ chart_svg_bytes.decode('utf-8') | safe }}
{% elif not_found %}<span class="chart-unavailable" data-chart-reason="trade-not-found">Trade not found.</span>
{% elif busy %}<span class="chart-unavailable" data-chart-reason="busy"
      hx-get="/journal/trades/{{ trade_id }}/thumbnail"
      hx-trigger="load delay:1500ms" hx-swap="innerHTML"
      hx-headers='{"HX-Request": "true"}'>Chart loading...</span>
{% else %}<span class="chart-unavailable" data-chart-reason="no-coverage">Chart unavailable.</span>{% endif %}
```

(The busy branch needs `trade_id` in the fragment context — pass it from the route.)

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat(web): lazy journal thumbnail fragment route with a render-concurrency bound"`.

**Acceptance:** four response contracts (200+SVG / 200+unavailable / 200+not-found / 200+busy); `Cache-Control: private`; SVG/`<span>` is not a table element (no wrap hazard); render exception isolated + logged; **explicit `BoundedSemaphore(2)` render-concurrency bound** so a fast-scroll burst cannot pile up workers (M#6); NO memo on this one-trade-per-request route (m#2); ZERO write.

#### Task 4.3 — Wire the on-scroll thumbnail cell + verify window-scroll layout

**Files:**
- Modify: `swing/web/templates/partials/journal_row.html.j2` (the `<td class="journal-thumb">` lazy-loads)
- Test: `tests/web/test_journal_thumbnail_cell.py` (NEW)

- [ ] **Step 1: Write the failing test** — each row's thumbnail cell carries `hx-get="/journal/trades/{id}/thumbnail"` + `hx-trigger="revealed"` + `hx-swap="innerHTML"` + `hx-headers` HX-Request.

```python
def test_thumbnail_cell_lazy_attrs(client, seeded_mixed_trades):
    r = client.get("/journal?period=all")
    assert 'hx-trigger="revealed"' in r.text
    assert 'hx-get="/journal/trades/' in r.text and "/thumbnail" in r.text
    assert 'hx-headers=\'{"HX-Request": "true"}\'' in r.text
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement** the cell:

```jinja
<td class="journal-thumb"
    hx-get="/journal/trades/{{ row.trade_id }}/thumbnail"
    hx-trigger="revealed" hx-swap="innerHTML"
    hx-headers='{"HX-Request": "true"}'></td>
```

**Window-scroll verification (R5 M#2):** confirm at implementation that the journal listing scrolls in the WINDOW viewport — `base.html.j2` must NOT wrap `{% block content %}` in an `overflow:auto/scroll` container (grep the layout CSS). If it does, switch the trigger to `hx-trigger="intersect"` with an explicit `root`/`threshold` matching the scroll container. The operator-witnessed gate S4 verifies thumbnails DO load on scroll in a real browser (binding — TestClient cannot see `revealed`).

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat(web): lazy on-scroll candlestick thumbnails on the journal listing"`.

**Acceptance:** `revealed` trigger + HTMX trinity attrs; window-scroll layout confirmed (or `intersect` fallback documented); render queue bounded to on-screen rows + page-size; **Operator-witnessed gate S4 (thumbnails load on scroll) BINDING.**

**Slice 4 totals:** ~3 tasks, ~3–4 commits, ~8–12 tests.

---

### Slice 5 — Drill-down (unified chronology + annotated chart)

**Outcome:** `GET /journal/trades/{id}` renders a full page with (a) a thesis-at-open block, (b) a unified timestamp-merged per-trade chronology, and (c) an annotated full chart over the trade window. Missing trade → 404 (full-page contract). This slice contains the one genuinely-new domain assembly (the chronology) with dedicated contract tests.

#### Task 5.0 — Factor the shared `_base_banner_fields` helper (Codex R1 M#11)

**Files:**
- Modify: `swing/web/view_models/journal.py` (NEW `_base_banner_fields(conn, cfg) -> dict`)
- Test: `tests/web/test_base_banner_fields.py` (NEW)

- [ ] **Step 1: Write the failing test** — the helper returns every base-banner key (`session_date`, `stale_banner`, `price_source_degraded`, `price_source_degraded_until`, `ohlcv_source_degraded`, `unresolved_material_discrepancies_count`, `recent_multi_leg_auto_correction_count`, `banner_resolve_link`) so a base-layout page VM can splat it.

```python
def test_base_banner_fields_complete(conn, cfg):
    fields = _base_banner_fields(conn, cfg)
    required = {"session_date", "stale_banner", "price_source_degraded",
                "price_source_degraded_until", "ohlcv_source_degraded",
                "unresolved_material_discrepancies_count",
                "recent_multi_leg_auto_correction_count", "banner_resolve_link"}
    assert required <= set(fields)
```

- [ ] **Step 2: Run, verify fail** — helper absent.

- [ ] **Step 3: Implement** `_base_banner_fields` by lifting the reads `build_journal` / `build_review_vm` already perform (`count_unresolved_material`, `count_recent_multi_leg_auto_corrections`, `fetch_first_pending_ambiguity_resolve_link_path`, `last_completed_session`/`date.today()` for `session_date`, degraded flags). Return a dict. (Opportunistically, refactor `build_journal` to consume it — keeps one source; do NOT change its output.)

- [ ] **Step 4: Run, verify pass.** Existing journal tests green.

- [ ] **Step 5: Commit** — `git commit -m "refactor(web): factor a shared _base_banner_fields helper for base-layout page VMs"`.

**Acceptance:** the new drill-down page VM populates base-banner fields via this helper (no hand-copy → no 500 risk when a base field is later added — M#11); ZERO write.

#### Task 5.1 — `trade_chronology.py` dataclasses + fills source

**Files:**
- Create: `swing/web/view_models/trade_chronology.py`
- Test: `tests/web/test_trade_chronology.py` (NEW)

- [ ] **Step 1: Write the failing test** — `build_trade_chronology` over a fills-only trade returns `ChronologyEntry`s with `kind == f"fill:{action}"`, `summary == "{action} {quantity} @ {price}"`, sorted ascending by `ts`.

```python
def test_chronology_fills_only(conn, trade_with_two_fills):
    chron = build_trade_chronology(conn, trade_with_two_fills.id)
    kinds = [e.kind for e in chron.entries]
    assert kinds[0] == "fill:entry"
    assert all(chron.entries[i].ts <= chron.entries[i+1].ts
               for i in range(len(chron.entries) - 1))
    entry = chron.entries[0]
    assert entry.summary == f"entry {entry_qty} @ {entry_price}"  # field is quantity
```

- [ ] **Step 2: Run, verify fail** — module absent.

- [ ] **Step 3: Implement** the dataclasses + the fills source.

```python
# swing/web/view_models/trade_chronology.py
"""Read-only per-trade chronology assembly (journal drill-down only).

Merges fills + trade_events + daily_management_records (split by record_type)
+ the trades post-trade-review COLUMNS into one timestamp-sorted stream.
review_log is a CADENCE table with NO trade_id and is EXCLUDED (Codex Re-R1 M#1).
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field

from swing.data.repos.fills import list_fills_for_trade

# Tie-break source precedence: lower sorts first on equal timestamps (OQ-5).
_SOURCE_PRECEDENCE = {"fill": 0, "daily_management": 1, "trade_event": 2, "review": 3}


@dataclass(frozen=True)
class ChronologyEntry:
    ts: str                # normalized ISO key (date-only rows -> 'YYYY-MM-DD')
    source: str            # 'fill'|'trade_event'|'daily_management'|'review'
    kind: str
    summary: str
    detail: str | None = None
    ts_malformed: bool = False  # sorts last with a flag, never raises


@dataclass(frozen=True)
class TradeChronology:
    trade_id: int
    entries: tuple[ChronologyEntry, ...] = ()


def _fill_entries(conn, trade_id) -> list[ChronologyEntry]:
    out = []
    for f in list_fills_for_trade(conn, trade_id):
        out.append(ChronologyEntry(
            ts=f.fill_datetime, source="fill", kind=f"fill:{f.action}",
            summary=f"{f.action} {f.quantity} @ {f.price}",
            detail=(f.reason or None)))
    return out


def build_trade_chronology(conn, trade_id: int) -> TradeChronology:
    entries: list[ChronologyEntry] = []
    entries += _fill_entries(conn, trade_id)
    # Task 5.2 adds trade_events; Task 5.3 adds daily_management + review.
    return TradeChronology(trade_id=trade_id, entries=_sorted(entries))


def _sorted(entries) -> tuple[ChronologyEntry, ...]:
    def key(e):
        # Malformed timestamps sort last; then by ts, then source precedence.
        return (1 if e.ts_malformed else 0, e.ts or "",
                _SOURCE_PRECEDENCE.get(e.source, 99))
    return tuple(sorted(entries, key=key))
```

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat(web): trade chronology assembly scaffold with fills source"`.

**Acceptance:** fills → `fill:{action}` + `{action} {quantity} @ {price}` (field is `quantity`, NOT `qty`); ascending sort with malformed-last + source-precedence tiebreak (OQ-5); ZERO write.

#### Task 5.2 — Add the `trade_events` source (best-effort payload parse)

**Files:**
- Modify: `swing/web/view_models/trade_chronology.py`
- Test: `tests/web/test_trade_chronology.py` (extend)

- [ ] **Step 1: Write the failing test** — a `trade_events` row appears as `kind == f"event:{event_type}"`; a malformed `payload_json` does NOT raise (best-effort, None-fallback detail).

```python
def test_chronology_includes_trade_events(conn, trade_with_event):
    chron = build_trade_chronology(conn, trade_with_event.id)
    assert any(e.source == "trade_event" and e.kind.startswith("event:")
               for e in chron.entries)


def test_chronology_malformed_event_payload_does_not_raise(conn,
        trade_with_malformed_event_payload):
    chron = build_trade_chronology(conn, trade_with_malformed_event_payload.id)
    ev = next(e for e in chron.entries if e.source == "trade_event")
    assert ev is not None  # entry present despite unparseable payload_json
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement** an inline SELECT over `trade_events` (`id, ts, event_type, payload_json, rationale` — **NOTE: columns are `payload_json` + `rationale`, there is NO `notes` column**; verified `0003_phase2_pipeline_trades.sql:88-95`). Best-effort `json.loads(payload_json)` with a None fallback (the `_load_audit_entries` precedent); `event_type ∈ {entry,stop_adjust,note,exit,flag}`.

```python
def _trade_event_entries(conn, trade_id) -> list[ChronologyEntry]:
    rows = conn.execute(
        "SELECT ts, event_type, payload_json, rationale FROM trade_events "
        "WHERE trade_id = ? ORDER BY ts", (trade_id,)).fetchall()
    out = []
    for ts, event_type, payload_json, rationale in rows:
        try:
            payload = json.loads(payload_json) if payload_json else None
        except (ValueError, TypeError):
            payload = None  # best-effort; never raise on operator/legacy data
        detail = rationale or (json.dumps(payload) if payload else None)
        out.append(ChronologyEntry(
            ts=ts or "", source="trade_event", kind=f"event:{event_type}",
            summary=str(event_type), detail=detail,
            ts_malformed=not bool(ts)))
    return out
```

Call it from `build_trade_chronology`.

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat(web): add trade_events source to the trade chronology"`.

**Acceptance:** trade_events → `event:{event_type}`; malformed `payload_json` → None-fallback, entry retained (not dropped, not raised); uses `payload_json`+`rationale` (the #4 column correction); ZERO write.

#### Task 5.3 — Add `daily_management_records` (split by record_type) + the `trades` review source (the contract tests)

**Files:**
- Modify: `swing/web/view_models/trade_chronology.py`
- Test: `tests/web/test_trade_chronology_contracts.py` (NEW — the substantive per-source contract tests, Codex Re-R1..R3)

This is the substantive domain artifact. The field map (verified columns) is fixed:

| source | `ts` | `kind` | `summary` | `detail` |
|---|---|---|---|---|
| `daily_management_records` `daily_snapshot` | `review_date` (date) | `snapshot` | position-state one-liner | `open_MFE_R_to_date`/`open_MAE_R_to_date` (**R-multiples, NOT %**), trail-MA eligibility |
| `daily_management_records` `event_log` | `review_date` (date) | precedence: `stop_adjust` if `stop_changed==1`; else `action:{action_taken}` if `action_taken NOT IN (None,'no_action')`; else `thesis` if `thesis_status` set; else `management_event` | `"{prior_stop}->{new_stop}"` (stop_adjust) / `action_reason` / `thesis_status` | `stop_change_reason`, volume/RS/regime, `management_notes` |
| `trades` post-trade review | `reviewed_at` (datetime) | `review` | grade + one-line lesson | full lesson/tag fields |

Supersession (V1 DECIDED): include only `is_superseded=0`; superseded rows EXCLUDED outright (not struck-through). `review_log` is EXCLUDED entirely (cadence table, no `trade_id`).

- [ ] **Step 1: Write the failing contract tests** — one per source contract:

```python
# tests/web/test_trade_chronology_contracts.py
def test_daily_snapshot_field_map(conn, trade_with_daily_snapshot):
    chron = build_trade_chronology(conn, trade_with_daily_snapshot.id)
    snap = next(e for e in chron.entries if e.kind == "snapshot")
    assert "MFE" in (snap.detail or "") or "MAE" in (snap.detail or "")  # R-multiples


def test_event_log_stop_adjust_precedence(conn, trade_with_stop_adjust_event_log):
    chron = build_trade_chronology(conn, trade_with_stop_adjust_event_log.id)
    e = next(e for e in chron.entries if e.kind == "stop_adjust")
    assert "->" in e.summary  # "{prior_stop}->{new_stop}"


def test_superseded_daily_management_excluded(conn, trade_with_superseded_row):
    chron = build_trade_chronology(conn, trade_with_superseded_row.id)
    # the superseded snapshot/event_log row must NOT appear
    assert all(getattr(e, "_src_id", None) != trade_with_superseded_row.superseded_id
               for e in chron.entries)


def test_review_log_cadence_row_never_in_chronology(conn,
        trade_and_unrelated_review_log_row):
    # A cadence review_log row (no trade_id) must NOT leak into any trade's
    # chronology (M#1 / M#5 regression guard).
    chron = build_trade_chronology(conn, trade_and_unrelated_review_log_row.trade_id)
    assert all(e.source != "review_log" for e in chron.entries)


def test_trades_review_source(conn, trade_with_completed_review):
    chron = build_trade_chronology(conn, trade_with_completed_review.id)
    rev = next(e for e in chron.entries if e.source == "review")
    assert rev.kind == "review" and rev.ts  # reviewed_at


def test_empty_sources_no_error(conn, bare_trade_only_fills):
    chron = build_trade_chronology(conn, bare_trade_only_fills.id)
    assert chron.entries  # fills only; daily_management/review empty -> no error


def test_timestamp_precision_normalized_sortable(conn, trade_mixed_sources):
    chron = build_trade_chronology(conn, trade_mixed_sources.id)
    # date-only (daily_management) and datetime (fills/events/review) co-sort
    assert all(chron.entries[i].ts <= chron.entries[i+1].ts
               for i in range(len(chron.entries) - 1)
               if not chron.entries[i+1].ts_malformed)
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement** the two `daily_management_records` field maps (split on `record_type`, `is_superseded=0` only) + the `trades` review source. Normalize date-only `review_date` to a sortable ISO key (date-only sorts at start-of-day; keep the displayed precision). Use the verified columns.

```python
def _daily_management_entries(conn, trade_id) -> list[ChronologyEntry]:
    rows = conn.execute(
        "SELECT record_type, review_date, open_MFE_R_to_date, open_MAE_R_to_date, "
        "       stop_changed, prior_stop, new_stop, stop_change_reason, "
        "       action_taken, action_reason, thesis_status, management_notes "
        "FROM daily_management_records "
        "WHERE trade_id = ? AND is_superseded = 0 ORDER BY review_date",
        (trade_id,)).fetchall()
    out = []
    for r in rows:
        (rtype, rdate, mfe, mae, stop_changed, prior_stop, new_stop,
         stop_reason, action_taken, action_reason, thesis_status, notes) = r
        if rtype == "daily_snapshot":
            out.append(ChronologyEntry(
                ts=rdate or "", source="daily_management", kind="snapshot",
                summary=f"snapshot MFE {mfe}R / MAE {mae}R",
                detail=f"MFE={mfe}R MAE={mae}R", ts_malformed=not bool(rdate)))
        else:  # event_log -- precedence over the REAL columns
            if stop_changed == 1:
                kind, summary = "stop_adjust", f"{prior_stop}->{new_stop}"
            elif action_taken not in (None, "no_action"):
                kind, summary = f"action:{action_taken}", (action_reason or str(action_taken))
            elif thesis_status:
                kind, summary = "thesis", str(thesis_status)
            else:
                kind, summary = "management_event", "management event"
            out.append(ChronologyEntry(
                ts=rdate or "", source="daily_management", kind=kind,
                summary=summary,
                detail=(stop_change_reason or notes or None),
                ts_malformed=not bool(rdate)))
    return out


def _review_entry(conn, trade_id) -> list[ChronologyEntry]:
    row = conn.execute(
        "SELECT reviewed_at, process_grade, lesson_learned, mistake_tags "
        "FROM trades WHERE id = ? AND reviewed_at IS NOT NULL", (trade_id,)).fetchone()
    if not row:
        return []
    reviewed_at, grade, lesson, tags = row
    one_line = (lesson or "").splitlines()[0] if lesson else ""
    return [ChronologyEntry(
        ts=reviewed_at or "", source="review", kind="review",
        summary=f"review {grade or ''} {one_line}".strip(),
        detail=lesson, ts_malformed=not bool(reviewed_at))]
```

(Verify the EXACT `trades` review column names at implementation: `process_grade` / `mistake_tags` / `lesson_learned` — grep `models.py:213-223`; the spec cites `reviewed_at`/grade/tag/`lesson_learned`. Adjust the SELECT to the real column names.) Wire both into `build_trade_chronology`.

- [ ] **Step 4: Run, verify pass.** All contract tests green.

- [ ] **Step 5: Commit** — `git commit -m "feat(web): add daily_management and post-trade-review sources to the chronology"`.

**Acceptance:** daily_snapshot vs event_log split honored; event_log kind-precedence over the REAL columns (`stop_changed`/`prior_stop`/`new_stop`, not `action_taken`); MFE/MAE rendered as R-multiples; supersession excludes `is_superseded=1`; `review_log` NEVER appears (M#1/M#5 guard); review source = `trades` columns; empty-source = no error; timestamp precision normalized + co-sortable; ZERO write.

#### Task 5.4 — `TradeDrilldownVM` + `build_trade_drilldown_vm`

**Files:**
- Modify: `swing/web/view_models/journal.py` (`TradeDrilldownVM` + `build_trade_drilldown_vm`)
- Test: `tests/web/test_trade_drilldown_vm.py` (NEW)

- [ ] **Step 1: Write the failing test** — the VM carries the trade, the chronology, the thesis-at-open fields, base-banner fields (via `_base_banner_fields`), and a `chart_url` (lazy annotated chart); `None` (→ route 404) when the trade is missing.

```python
def test_drilldown_vm_assembles(conn, cfg, trade_mixed_sources):
    vm = build_trade_drilldown_vm(conn, cfg, trade_mixed_sources.id)
    assert vm is not None
    assert vm.trade.id == trade_mixed_sources.id
    assert vm.chronology.entries
    assert vm.session_date  # base-banner field present
    assert vm.chart_url == f"/journal/trades/{trade_mixed_sources.id}/chart" or \
           vm.chart_url.endswith("/chart")


def test_drilldown_vm_none_when_missing(conn, cfg):
    assert build_trade_drilldown_vm(conn, cfg, 999999) is None
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement.** `TradeDrilldownVM` is a base-layout page VM — carry the full base-banner field set (splat `_base_banner_fields`) + `trade`, `chronology`, `thesis_block` (static `Trade` decision columns: `thesis`, `why_now`, `invalidation_condition`, premortem_*, etc. — verify the names at `models.py:236-253`), `chart_url`. `build_trade_drilldown_vm` returns `None` when `get_trade` is `None`.

```python
@dataclass(frozen=True)
class TradeDrilldownVM:
    trade: Trade
    chronology: TradeChronology
    chart_url: str
    # thesis-at-open (static decision columns; read-only)
    thesis: str | None = None
    why_now: str | None = None
    invalidation_condition: str | None = None
    # base-banner fields (populated via _base_banner_fields):
    session_date: str = ""
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
    ohlcv_source_degraded: bool = False
    unresolved_material_discrepancies_count: int = 0
    recent_multi_leg_auto_correction_count: int = 0
    banner_resolve_link: str | None = None

    def __post_init__(self): ...  # mirror the JournalVM banner_resolve_link guard
```

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat(web): build the journal trade drill-down view model"`.

**Acceptance:** VM carries trade + chronology + thesis + base-banner (via the shared helper, no hand-copy — M#11) + lazy chart_url; `None` on missing (→ 404 in the route); ZERO write.

#### Task 5.5 — Drill-down route `GET /journal/trades/{id}` (404 on missing) + annotated-chart fragment + templates

**Files:**
- Modify: `swing/web/routes/journal.py` (NEW `GET /journal/trades/{id}` full page → 404 on missing; NEW `GET /journal/trades/{id}/chart` lazy annotated-chart fragment → 200+unavailable on missing)
- Create: `swing/web/templates/journal_trade_detail.html.j2`, `swing/web/templates/partials/trade_chronology.html.j2`
- Test: `tests/web/test_journal_drilldown_route.py` (NEW)

- [ ] **Step 1: Write the failing test** — full page 200 for an existing trade (renders chronology + thesis + a lazy chart cell); **404 for a missing trade** (full-page contract); the chart FRAGMENT returns 200+unavailable (not 404) for a missing trade (fragment contract — the two distinct contracts, Codex Re-R2 M#1).

```python
def test_drilldown_page_200(client, trade_mixed_sources):
    r = client.get(f"/journal/trades/{trade_mixed_sources.id}")
    assert r.status_code == 200
    assert "chronology" in r.text.lower()
    assert 'hx-get="/journal/trades/' in r.text and "/chart" in r.text


def test_drilldown_page_404_when_missing(client):
    r = client.get("/journal/trades/999999")
    assert r.status_code == 404


def test_drilldown_chart_fragment_200_unavailable_when_missing(client):
    r = client.get("/journal/trades/999999/chart", headers={"HX-Request": "true"})
    assert r.status_code == 200 and "not found" in r.text.lower()
```

- [ ] **Step 2: Run, verify fail.**

- [ ] **Step 3: Implement.** Full-page route: `vm = build_trade_drilldown_vm(...)`; if `None` → `raise HTTPException(status_code=404)` (mirror `routes/trades.py:2598-2602`). Render `journal_trade_detail.html.j2` (extends `base.html.j2`; includes `partials/trade_chronology.html.j2`; a lazy chart cell `hx-get="/journal/trades/{id}/chart" hx-trigger="load"`). The annotated-chart fragment route reuses `render_trade_window_position_svg` (same helper as CR.1) with the failure-isolation + 200-unavailable + 200-not-found contract (identical to the review-chart route, §C.1). The drill-down LINK from the listing is a plain `<a href>` (full navigation, NOT HTMX — avoids the 204/HX-Redirect surface entirely; §8 item 3).

```jinja
{# journal_trade_detail.html.j2 #}
{% extends "base.html.j2" %}
{% block content %}
  <h1>{{ vm.trade.ticker }} - trade detail</h1>{# ASCII hyphen (R1 m#1) #}
  <section class="thesis-at-open">
    <h2>Thesis at open</h2>
    <p>{{ vm.thesis or '' }}</p>
    <p>Why now: {{ vm.why_now or '' }}</p>
    <p>Invalidation: {{ vm.invalidation_condition or '' }}</p>
  </section>
  <section class="annotated-chart" hx-get="{{ vm.chart_url }}" hx-trigger="load"
           hx-swap="innerHTML" hx-headers='{"HX-Request": "true"}'>
    <span class="chart-loading">Loading chart...</span>
  </section>
  <section class="chronology">
    <h2>Chronology</h2>
    {% include "partials/trade_chronology.html.j2" %}
  </section>
{% endblock %}
```

```jinja
{# partials/trade_chronology.html.j2 #}
<ol class="chronology-list">
  {% for e in vm.chronology.entries %}
    <li class="chron-{{ e.source }}">
      <span class="chron-ts">{{ e.ts }}</span>
      <span class="chron-kind">{{ e.kind }}</span>
      <span class="chron-summary">{{ e.summary }}</span>
      {% if e.detail %}<span class="chron-detail">{{ e.detail }}</span>{% endif %}
    </li>
  {% else %}
    <li>No recorded events.</li>
  {% endfor %}
</ol>
```

- [ ] **Step 4: Run, verify pass.**

- [ ] **Step 5: Commit** — `git commit -m "feat(web): journal trade drill-down page with unified chronology and annotated chart"`.

**Acceptance:** full-page 200 / 404-on-missing (full-page contract); chart FRAGMENT 200+unavailable/200+not-found (fragment contract — the two distinct contracts); chronology renders in order; annotated chart reuses the CR.1 helper; drill-down link is a plain `<a>` (no 204/HX-Redirect surface); operator text auto-escaped (chronology summaries/details NOT `| safe`); `| safe` only on the chart SVG fragment; **Operator-witnessed gate S5 BINDING.**

**Slice 5 totals:** ~6 tasks, ~6–8 commits, ~20–30 tests (incl. the chronology per-source contract suite + the 404-vs-fragment split).

---

## §H Test surface (sum-check)

**Trust pytest, not the manual count (gotcha #1):** the figures below are the planning budget; the executing engineer re-runs the fast suite and reads the actual delta. The goal is a green `python -m pytest -m "not slow" -q` on the merged HEAD (`feedback_no_false_green_claim`: re-run ON the merged HEAD, never carry a branch count forward).

| Slice | Approx new tests | Mandatory discriminating tests |
|---|---|---|
| Slice 0 (CR.1 + helper + lock) | ~14–18 | render-lock reentrancy + no-deadlock-per-chart-path; `_trade_window_bars` coverage/no-coverage/empty; render-direct SVG/None; reopened-ticker correctness; **exit-VWAP + total_risk single-leg AND multi-leg** (`feedback_verify_regression_test_arithmetic`); review-chart route 200+SVG / 200+unavailable / 200+not-found-distinct + WARNING + `Cache-Control: private`; review-page lazy chart cell |
| Slice 1 (BULZ) | ~5–8 | expand VM carries cached SVG / None; route shows `<svg`, NOT legacy `<img>`, fragment root `<tr>`; reopened-ticker uses the open trade's chart |
| Slice 2 (listing) | ~12–18 | row fields single+multi-leg; `has_hyprec_link` from `trade_origin` (A+/manual NOT mislabeled); entry-flag None-safety; pagination bound+clamp; `period=bogus` no 422; rich-table render |
| Slice 3 (sort/filter) | ~10–14 | sort/filter correctness; `filter_state='reviewed'`==`state=='reviewed'`; bad input → default + `invalid_filter` (no 500); HX fragment root `<table>`; controls have HTMX trinity attrs; in-page notice (not 400); shared `{% include %}` (no markup drift) |
| Slice 4 (thumbnails) | ~8–12 | thumbnail SVG/None; no-deadlock; no title; route 200+SVG / 200+unavailable / 200+not-found; `Cache-Control: private`; cell `revealed` + HTMX attrs |
| Slice 5 (drill-down + chronology) | ~20–30 | **chronology per-source contract suite** (fills/trade_events/daily_snapshot/event_log-precedence/review field-maps; supersession-excluded; `review_log` never appears; malformed-payload best-effort; empty-source no-error; timestamp normalization); drill-down 200 / **404-on-missing (full page)** / **chart-fragment 200-unavailable (not 404)**; `_base_banner_fields` completeness; drill-down VM None-on-missing |
| Cross-cutting | ~2–4 | **per-slice "ZERO `chart_renders` rows created by SB4 paths"** assertion; the L6 Schwab source-grep test stays green; schema-version==23 probe |

**Planning total:** ~70–105 new tests across ~25–34 commits (aligns with the commissioning brief's ~20–35 commits / ~50–100 tests). **0 new slow tests** (charts render from planted fixture bars; assemblies from planted rows; no network).

**The two highest-risk test families (call out at executing-plans):**
1. **Render-lock no-deadlock per chart path** — every chart-producing entry point (`render_trade_window_position_svg`, `render_trade_window_thumbnail_svg`, and the existing `render_position_detail_svg`/`render_watchlist_thumbnail_svg` it nests into) has a test that renders while the lock is already held on the same thread and asserts completion (reentrancy).
2. **Chronology per-source contracts** — field-map per source, supersession exclusion, timestamp normalization, malformed-payload isolation, and the `review_log`-never-leaks guard — each a dedicated test, NOT an incidental template assertion.

---

## §I Operator-witnessed visual + HTMX gate runbook (Sec 9.1 Q6)

The BINDING gate is the RENDERED surface in a REAL browser (matplotlib geometry + the HTMX trinity; byte/string tests are declared INSUFFICIENT for chart correctness and CANNOT see synthetic-table-wrap / OriginGuard). Re-confirm the SB4 gate split with the operator at executing-plans (`feedback_visual_gate_both_render_and_browser`).

| Gate | Check | Driver |
|---|---|---|
| **S1** | `python -m pytest -m "not slow" -q` green on the merged HEAD + `ruff check swing/` clean | orchestrator (DB-scriptable) |
| **S2** | `EXPECTED_SCHEMA_VERSION == 23`; NO new `00XX_*.sql`; live DB untouched (no migration); **assert ZERO `chart_renders` rows created by SB4 paths** | orchestrator (DB-scriptable) |
| **S3** | CR.1: open a real CLOSED trade's review page → exit price/date/legs + final R visible + candlestick chart with fills/zones over the TRADE window (not trailing-today); the form renders even if the chart is unavailable | operator browser (BINDING) |
| **S4** | journal listing: rich rows + all flag columns + dollar total-risk; candlestick thumbnails lazy-load AS THE OPERATOR SCROLLS; sort + filter re-render without full reload; repeated sort/filter cycles leave controls usable (sort indicator + selected filter persist; scroll not jarringly reset) | operator browser (BINDING) |
| **S5** | drill-down: chronology renders in timestamp order; annotated chart shows entry/stop/target/fills over the trade window; a missing-trade URL 404s | operator browser (BINDING) |
| **S6** | BULZ row-expand: dashboard open-position row-expand shows the SB3 candlestick + BULZ zones SVG, NOT the legacy PNG | operator browser (BINDING) |
| **Fallback** | for surfaces with no live data (e.g. no eligible closed trade within archive depth): orchestrator render-to-PNG + `Read` inspection (the SB3 S6 documented substitute) | orchestrator |

**Teardown discipline:** if `swing web` / uvicorn is spawned for the gate, kill it via PID (`Get-NetTCPConnection -LocalPort`, `Stop-Process -Force`) and VERIFY the port is free before claiming teardown (`feedback_taskstop_does_not_kill_detached_server`). Record observed warm medians (listing < ~1s; thumbnail < ~250ms; drill-down/review chart < ~500ms) in the merge notes as a baseline (§12 budget, R3 m#3).

---

## §J Codex single-chain placement (run-to-convergence)

- **SINGLE chain** at the end of writing-plans (operator-LOCKed OQ-8 + Sec 9.1 Q7). The chronology is a read-only timestamp merge, not analysis — single chain is correct (the spec's own recommendation, confirmed at writing-plans).
- **Run to CONVERGENCE:** zero new criticals AND zero new majors is the stop criterion. The ~5-round cap is **suspended** (`feedback_codex_round_limit_suspended`); the chain may exceed 5 rounds; do NOT stop while majors surface; do NOT pad after convergence.
- **Transport:** the MCP `codex`/`codex-reply` tools are PERMANENTLY DEAD in the VS Code extension. copowers v2.0.2 auto-routes to the **WSL Codex CLI fallback** that reads the worktree FROM DISK (read-only; findings → `.copowers-findings.md`). Preferred: invoke `copowers:writing-plans` and let it drive the fallback. Direct invocation if needed: R1 `wsl -e bash -c 'export PATH="$HOME/.local/node22/bin:$PATH"; codex exec -s read-only --skip-git-repo-check -C /mnt/c/Users/rwsmy/swing-trading/.worktrees/phase14-sub-bundle-4-review-journal-ux-writing-plans - < <promptfile>'`; R2+ `... codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check -`.
- **Watch items for the chain (brief §5):** signature/column verify (#2/#4) — the 8 `.copowers-findings.md` corrections honored; read-mostly (ZERO new trade/fill/review/`chart_renders` writes); NO schema; render lock (process-wide, single outer / RLock, no-deadlock per path, thumbnail-DoS guard); HTMX trinity; matplotlib mathtext + visual-gate; chronology contracts; total_risk/exit-VWAP/final_R single- vs multi-leg; L6 Schwab grep; ASCII; Co-Authored-By suppression + trailer-parse hazard.
- The return report EVIDENCES the chain ran genuinely via WSL (cite the per-round `.copowers-findings.md` content) and to convergence (NOT a silent no-op, NOT a premature stop while majors remained).

---

## §K Schema impact (NO change)

**Verdict: NO schema change. Schema stays v23.**

- No new table, column, CHECK, or index. `EXPECTED_SCHEMA_VERSION = 23` (`swing/data/db.py:51`) unchanged; NO `0024_*.sql`.
- The ONLY candidate trigger — a new `chart_renders` surface enum for closed-trade charts — is **eliminated** by the render-direct decision (§1.2/§7 of the spec). Closed-trade charts hold no cache row; the open-trade BULZ row-expand REUSES the existing `position_detail` cache (no new surface/key/column). **All of SB4 is write-free against `chart_renders`.**
- Because no schema changes, gotcha #11 (CHECK + constant + dataclass + `_row_to_*` paired), #9 (executescript BEGIN/COMMIT/ROLLBACK), and the STRICT `pre_version==23` backup gate are **NOT invoked**. The S2 gate ASSERTS zero migration + zero `chart_renders` writes. The v22 (temporal-log) and v23 (chart-surface-rename) substrates are untouched.
- **Load-bearing linkage (document in the merge notes):** render-direct (OQ-1) over a trade-window archive slice is precisely what keeps SB4 schema-free — a persisted closed-trade chart cache would require a NEW `trade_id` column + partial unique index (a v24), which §1.2 eliminates. If executing-plans or a later profiling pass argues for the cache (the §12 tripwire), that is a scoped v24 follow-on, NOT a V1 change here. **If any task appears to need a migration, ESCALATE (L3 forbids it).**

---

## §L Test fixture strategy

Reuse the existing web conftest harness (grep `tests/web/conftest.py` for the established `cfg`/`client`/`conn`/seed-helper names and use them verbatim — do NOT invent parallel fixtures). New fixtures needed (planted rows, no network):

- **`closed_single_leg_trade`** + entry/exit fills + a recent exit date within archive depth → trade-window chart has coverage; closing_price = the single exit price.
- **`multi_leg_closed`** (2 exit fills, e.g. 60@11 + 40@13) → exit VWAP = 11.80 (the share-weighting check), 2 exit-marker chart.
- **`old_closed_trade`** (exit date older than archive depth) → `_trade_window_bars`/renderers return `None` → chart-unavailable asserted.
- **`open_trade`** → thumbnail uses trailing window; `final_r`/`closing_price` None.
- **`closed_then_reopened_same_ticker`** (two trades, same ticker) → render-direct serves the correct per-trade chart (cache-collision regression).
- **`aplus_trade_with_candidate`** (origin `pipeline_aplus`, candidate_id set) + **`hyprec_trade`** (origin `pipeline_watch_hyp_recs`) + **`trade_no_candidate`** → `has_hyprec_link` + entry-flag None-safety.
- **`trade_mixed_sources`** — fills + trade_events + daily_management (one `daily_snapshot` + one `event_log` + one `is_superseded=1` row) + a completed `trades` post-trade review + an UNRELATED cadence `review_log` row (no `trade_id`) present in the DB → chronology merge ordering + per-`record_type` field-maps + supersession exclusion + `review_log`-never-leaks + malformed-payload best-effort.
- **`stop_above_entry`** → `total_risk_dollars` None (inverted/missing stop guard).
- **`planted_archive`** — a callable returning a fixture OHLCV DataFrame spanning the trade window (monkeypatches `read_or_fetch_archive`); a sibling returning `None` for the no-coverage path.

**Arithmetic discipline (`feedback_verify_regression_test_arithmetic`):** every money/R fixture states its expected value computed under BOTH single-leg and multi-leg so a test that passes under one shape but not the other is caught (e.g. multi-leg exit VWAP 11.80 ≠ naive mean 12.00; total_risk unchanged at 100.00 because risk is at OPEN, not affected by leg count; `final_r` computed via `compute_actual_realized_R_effective` under both).

---

## §M Forward-binding lessons for executing-plans

1. **Render lock is the highest-risk item.** Build Task 0.1 FIRST and add the no-deadlock test for EVERY chart path (existing + new). The lock is an `RLock` at the SHARED `charts.py` boundary covering EVERY web render path (not SB4-only — R4 M#1); a single outer acquisition per render (R5 M#1). If a single render ever blocks in a test, the lock is being acquired twice with a non-reentrant primitive — fix the primitive, not the test.
2. **Chronology contracts are the substantive artifact.** Treat Task 5.3 as a tested DOMAIN assembly, not template wiring. The field-map table in §G.5 is the binding contract; the column names are production-verified (especially: `trade_events` = `payload_json`+`rationale` NOT `notes`; daily_management split on `record_type`; stop in `stop_changed`/`prior_stop`/`new_stop`; MFE/MAE are R-multiples; `review_log` has NO `trade_id` and is EXCLUDED).
3. **Two distinct missing-trade contracts.** Full-page drill-down → 404; HTMX fragments (review-chart, thumbnail, drill-down chart) → 200 + distinct "not found" copy + WARNING. Do NOT collapse them (Codex Re-R2 M#1 over-correction trap).
4. **`has_hyprec_link` is `trade_origin`-derived, NOT `candidate_id`-derived** — A+/manual-watch are also candidate-backed (M#2).
5. **Render-direct for closed trades; cache-reuse only for the open-trade BULZ row-expand** (OQ-1). Never write-through `chart_renders` for closed-trade charts (would collide the ticker-keyed `position_detail` slot).
6. **Single math source.** `_exit_vwap`/`_total_risk_dollars` live in `view_models/trades.py`; `compute_actual_realized_R_effective` in `swing/trades/review.py` (read-only). Do NOT duplicate the math; do NOT add a helper under `swing/trades/` (phase-isolation carve-out).
7. **HTMX gate is browser-binding.** TestClient cannot catch synthetic-table-wrap or OriginGuard; the operator-witnessed S3–S6 gates are binding before merge.
8. **`period` is now `str`+allowlist at the route** (and `build_journal` clamps to default instead of raising) — a bad `period`/`sort`/`filter` must render the page with a notice, never 422/500.
9. **ZERO `Co-Authored-By`; NO `--no-verify`; final `-m` paragraph plain prose; verify `git log -1 --format='%(trailers)'` is `[]`** before any push (`feedback_commit_message_trailer_parse_hazard`).
10. **Re-grep at execution (#2/#4).** Production may have drifted; re-confirm every signature a task touches before editing (the anchors here were verified on this worktree but executing-plans branches fresh from main HEAD at its dispatch).

---

## §N Self-review checklist (run before the Codex chain)

- [ ] **Spec coverage:** §4 CR.1 (exit data + chart) → Slice 0 ✔; §5.1 listing → Slice 2 ✔; §5.2 sort/filter → Slice 3 ✔; §5.3 thumbnails → Slice 4 ✔; §5.4 drill-down + chronology → Slice 5 ✔; §6 BULZ row-expand → Slice 1 ✔; §3 module touch list (trade_charts.py, trade_chronology.py, render lock, all routes/templates) → §B ✔; §8 HTMX disciplines → §F + per-slice ✔; §11 NO schema → §K ✔.
- [ ] **Placeholder scan:** no "TBD"/"handle edge cases"/"similar to Task N" — every code step shows real code; every test step shows real assertions.
- [ ] **Type consistency:** `JournalRowVM` fields identical across Slice 2 def + template + tests; `ChronologyEntry`/`TradeChronology` identical across Slice 5; `ExitLegVM` identical across Slice 0 + template; `render_trade_window_position_svg`/`render_trade_window_thumbnail_svg`/`_trade_window_bars`/`_exit_date_for` signatures identical across definition + callers; `_serialized_render`/`_RENDER_LOCK` names identical across charts.py + trade_charts.py.
- [ ] **OQ dispositions held:** OQ-1 render-direct ✔; OQ-2 no enum/schema ✔; OQ-3 journal-only thumbnails ✔; OQ-4 `trade_origin`-derived flags ✔; OQ-5 unified chronology + precedence ✔; OQ-6 dollar total_risk ✔; OQ-7/OQ-8/OQ-9 ✔.
- [ ] **8 findings corrections honored:** review_log excluded; `has_hyprec_link` via origin; whole-`<table>` swap; `Fill.action`/`quantity`; daily_management record_type split + R-multiples; `period` str; 404-vs-fragment; `{quantity}` not `{qty}`.
- [ ] **L2/L3/L6:** ZERO trade/fill/review/`chart_renders` writes; ZERO migration; ZERO new `schwabdev.Client.*`.
- [ ] **#4 column correction surfaced:** `trade_events` = `payload_json`+`rationale` (NOT `notes`).

---

## §O Execution handoff

Plan complete. **REQUIRED SUB-SKILL at executing-plans:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development` with a post-completion adversarial Codex chain) — recommended for this read-mostly UX/wiring sub-bundle (fresh subagent per task, two-stage review between tasks). Slices 0 and 1 are independent and may parallelize; Slices 2→3→4→5 are serial.

*End of plan. Phase 14 Sub-bundle 4 — review + journal UX. CR.1 (exit-data + render-direct chart) + P14.N6 (browse-the-database journal: rich rows + sort/filter + candlestick thumbnails + drill-down chronology + annotated chart) + the BULZ row-expand rewire. Read-mostly; NO schema change (v23 held); NO new trade-mutation path. The load-bearing decision: closed-trade charts reuse the SB3 renderer render-direct over a trade-window archive slice; open-trade BULZ row-expand reuses the cache; a process-wide matplotlib render lock serializes every web render path. The rendered surface in a real browser is the binding operator-witnessed gate.*
