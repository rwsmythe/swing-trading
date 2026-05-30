# Phase 14 Sub-bundle 3 — Chart-Surface Uniformity Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. Adversarial review is via `copowers:executing-plans` (SINGLE Codex chain per OQ-chain LOCK).

**Goal:** Adopt mplfinance OHLC candlesticks across the 4 detail SVG renderers via one shared helper, rename the `hyprec_detail` surface to `ticker_detail` (v23 schema migration), add BULZ entry/stop/target shaded zones, compute the REAL weather trend-state at all 3 render sites, and reposition the S6 duration text — closing V2.G1 + V2.G2 + P14.N1 + P14.N2 + P14.N4 + P14.N8 + S6.

**Architecture:** A new `_render_candles_fig` helper in `swing/web/charts.py` mirrors the battle-tested mplfinance pattern at `swing/rendering/charts.py:render_chart`; the 4 detail renderers (`ticker_detail`, `position_detail`, `market_weather`, `theme2_annotated`) call it and overlay surface-specific annotations through a single `_x_for_date` coordinate helper. The `hyprec_detail`→`ticker_detail` rename lands as an atomic table-rebuild migration (`0023`) plus all Python/template/test mirrors in ONE task. BULZ zones derive an absolute target from `planned_target_R` (R-multiple). Weather trend-state is computed via the read-only `current_stage(conn, ticker, asof_date)`.

**Tech Stack:** Python 3.14, matplotlib (Agg), mplfinance ≥0.12 (already a declared dep), SQLite, FastAPI + HTMX (Starlette 1.0), pytest (`-m "not slow"`), ruff.

---

## §A Goals / non-goals

### A.1 Goals (the 7 in-scope items, L1)

| Item | Outcome |
|---|---|
| **V2.G1 + P14.N2** | The 4 detail surfaces render OHLC candlesticks (additive: today they ALL plot a close-line — see §A.4 correction). |
| **V2.G2** | `hyprec_detail` surface enum + `render_hyprec_detail_svg` function + VM field + template var + CSS class + size constant renamed to `ticker_detail`; v23 migration renames existing rows. The leaked "hyp-rec detail" chart title becomes a neutral, cache-safe title. |
| **P14.N1** | The `watchlist_row` thumbnail renderer is confirmed reusable as the substrate for open-position / hyp-rec table thumbnails via the JIT path (substrate-only; consuming-surface wiring deferred to Sub-bundle 4). |
| **P14.N4** | `render_position_detail_svg` draws a risk zone (entry→stop) and a reward zone (entry→target) with an ASCII legend; target derived from `planned_target_R`, drawn only when present. |
| **P14.N8** | The weather chart shows the REAL `current_stage` trend-state at the **2 LIVE render sites** (pipeline + interactive-refresh) — not a hardcoded `"stage_2"` / `"n/a"`. The 3rd site (the `chart_jit` default) is dead/defensive today (§A.4 correction 5: no live `market_weather` JIT caller); its fix is an **honest `"undefined"` fallback** (a future SB4 JIT caller MUST compute+pass real state). Gridlines uniform. |
| **S6** | The `flat_base` (and the whole `_annotate_*` family) duration text no longer overlaps the upper-left legend (moved to the upper-right annotation stack). |
| **Schema** | v23 migration (`hyprec_detail`→`ticker_detail` table rebuild); `EXPECTED_SCHEMA_VERSION = 23`; STRICT `pre_version == 22` backup gate. |

### A.2 Non-goals (see §D for the full out-of-scope list)
Review+journal UX (SB4); metrics overview (SB5); P14.N1 consuming-surface row TEMPLATE wiring (SB4); candlestick THUMBNAILS (thumbnails stay close-line per OD-2); any schema beyond v23; JS charting; historical chart re-render/backfill; Schwab API changes (L2).

### A.3 Definition of done
- Fast suite green (`python -m pytest -m "not slow" -q`); `ruff check swing/` 0 E501.
- v23 applied on a real v22 DB: `schema_version == 23`; `chart_renders` rows migrated; backup file written; `PRAGMA foreign_key_check` clean.
- Zero orphaned `hyprec_detail` / `render_hyprec_detail_svg` / `hyprec-detail-chart` / `_HYPREC_DETAIL_SIZE_PX` tokens in runtime-forbidden paths (L5 two-tier grep gate).
- L2 LOCK source-grep test still green.
- **Operator-witnessed visual gate (§I) PASS on every changed surface** — this is the BINDING correctness check (L4); byte/string tests are INSUFFICIENT.

### A.4 Brief-vs-production corrections carried forward (verified at main HEAD `69efa80`, 2026-05-29)

The brainstorm spec verified these at `fd59ece`; this plan re-verified them at `69efa80`. Three corrections from the spec §1.2 **plus two new corrections from this re-grep**:

1. **No renderer draws candles today.** All 5 plot a close-line via `ax.plot(...)`. V2.G1 + P14.N2 are **additive** (introduce candlesticks), not divergence-repair. The "only open positions show candlesticks" operator report most plausibly reflects (a) loose terminology, and/or (b) a template/CSS embedding gap (the §C.2 T-3.2-step-0 browser diagnosis investigates this FIRST).
2. **The 3 partial unique indexes do NOT reference `'hyprec_detail'`** (verified `0020_*.sql:208-221`: `surface != 'theme2_annotated'`, `surface = 'position_detail'`, `surface = 'theme2_annotated'`). The only SQL `hyprec_detail` literal is the `surface` CHECK enum. The rebuild recreates the indexes verbatim (no value edit).
3. **"gridlines" is not a kwarg today** — no renderer calls `ax.grid()`. Fix = add `price_ax.grid(...)` uniformly inside `_render_candles_fig`.
4. **(NEW) The spec's cited `current_stage` caller `review_form.py:454` does NOT exist** in the tree at `69efa80`. The canonical caller pattern is the pattern detectors: `swing/patterns/vcp.py:500` (and `flat_base.py:456`, `cup_with_handle.py:680`, `double_bottom_w.py:529`, `high_tight_flag.py`), all calling `current_stage(conn, ticker, asof_date)` where `asof_date` is a `datetime.date`. The real signature is `current_stage(conn: sqlite3.Connection, ticker: str, asof_date: date) -> _StageLabel` at `swing/patterns/foundation.py:745`. **In V1 it returns ONLY `"stage_2"` or `"undefined"`** (full 4-stage labeling is V2-deferred; verified `foundation.py:788-790` + `double_bottom_w.py:644-645`). So the weather badge will read `trend: stage_2` or `trend: undefined`. It is read-only (SELECT only; L2 preserved, `foundation.py:759-760`).
5. **(NEW) The dashboard build path reads `market_weather` from CACHE only**, never via the JIT. `view_models/dashboard.py:874-879` calls `get_cached_chart_svg(conn, ticker=cfg.rs.benchmark_ticker, surface="market_weather", pipeline_run_id=...)`. No production caller invokes `get_or_render_surface(surface="market_weather", ...)` (the only `get_or_render_surface` callers are `routes/watchlist.py:98` for `watchlist_row` and `view_models/dashboard.py:767` for `hyprec_detail`). Therefore `chart_jit.py:157-158`'s `trend_template_state` default `"stage_2"` is **dead/defensive** — no production path hits it. P14.N8's "3 sites" are: (i) pipeline `runner.py:2883`, (ii) interactive refresh `routes/dashboard.py:117`, (iii) the JIT default `chart_jit.py:158`. The JIT-default fix is to change it to the honest `"undefined"` fallback (a real caller would compute+pass), NOT a fake `"stage_2"`. This is recorded so T-3.4 does not chase a nonexistent live JIT market_weather render.

---

## §B File map

> All paths relative to repo root. Line numbers are from main HEAD `69efa80`; re-grep at implementation per Expansion #2 (they will shift as edits land).

### B.1 Production code — modified

| File | Responsibility / change | Task |
|---|---|---|
| `swing/data/migrations/0023_phase14_sb3_chart_surface_rename.sql` | **NEW.** v23 table-rebuild of `chart_renders`: new CHECK enum (`ticker_detail`), id-preserving `INSERT…SELECT` with `CASE` rename, recreate 3 partial indexes + cross-column CHECK, `UPDATE schema_version SET version=23`. Explicit `BEGIN;…COMMIT;`. | T-3.1 |
| `swing/data/db.py` | `EXPECTED_SCHEMA_VERSION = 22` → `23` (line 46); NEW `_phase14_sb3_backup_gate` (STRICT `current==22 AND target>=23`); wire into `run_migrations` after `_phase14_backup_gate`; `PHASE14_SB3_PRE_MIGRATION_EXPECTED_TABLES`. | T-3.1 |
| `swing/data/models.py` | `_CHART_SURFACE_VALUES` tuple value `"hyprec_detail"` → `"ticker_detail"` (line 99). The `ChartRender.__post_init__` validator (line ~1948) reads this tuple — dataclass-validator surface (#11). | T-3.1 |
| `swing/data/repos/chart_renders.py` | Comments `hyprec_detail` → `ticker_detail` (incl. the `refresh_chart_render` run-bound branch comment). `_row_to_chart_render` read-path mapper verified to carry no hardcoded literal (it maps the column value through). No logic change. | T-3.1 |
| `swing/web/charts.py` | Rename `render_hyprec_detail_svg` → `render_ticker_detail_svg` + `_HYPREC_DETAIL_SIZE_PX` → `_TICKER_DETAIL_SIZE_PX` (line 61) + module-header bullet + neutral suptitle (line 275). NEW `_render_candles_fig`, `_normalize_ohlc_for_mpf`, `_x_for_date`, `_MA_COLORS` palette. Convert 4 detail renderers to candlesticks; `price_ax.grid()` uniform; BULZ zones in position_detail; S6 annotation reposition; mplfinance import-guard. | T-3.1 (rename), T-3.2/3/4/5 (candles) |
| `swing/web/chart_jit.py` | `_RENDERERS` key + import + dispatch branch `hyprec_detail` → `ticker_detail` (lines 44, 57, 142); change `market_weather` default `"stage_2"` → `"undefined"` (line 158). | T-3.1 (rename), T-3.4 (default) |
| `swing/web/routes/watchlist.py` | `surface="hyprec_detail"` → `"ticker_detail"` literal (line ~216) + comments (line 199). | T-3.1 |
| `swing/web/routes/dashboard.py` | Refresh handler (line 117): compute `current_stage(conn, benchmark, last_completed_session(datetime.now()).date())` instead of `"n/a"`; fail-soft to `"undefined"`. | T-3.4 |
| `swing/web/view_models/dashboard.py` | VM field `hyprec_detail_chart_svg_bytes` → `ticker_detail_chart_svg_bytes` (lines 761, 767); `surface="hyprec_detail"` → `"ticker_detail"` literal (line 769). | T-3.1 |
| `swing/web/view_models/watchlist.py` | Comment rename (line 125). | T-3.1 |
| `swing/pipeline/runner.py` | `_step_charts`: `render_market_weather_svg` import (line 101) — function name unaffected; weather render (line 2883) threads real `current_stage`; any `hyprec_detail` comment → `ticker_detail`. | T-3.1 (comment), T-3.4 (state) |
| `swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2` | `expanded.hyprec_detail_chart_svg_bytes` → `…ticker_detail…` (lines 86-87); CSS class `hyprec-detail-chart` → `ticker-detail-chart` (line 87 + any CSS rule); comment (line 78). **The template FILENAME is unchanged** (it names the hyp-rec card, a real domain surface — L5 exemption §E.3). | T-3.1 |
| `pyproject.toml` | Add `"mplfinance>=0.12"` to the `web` extra (currently `dev`+`charts` only, lines ~40,42). | T-3.6 |

### B.2 Tests — new / updated

| File | Change | Task |
|---|---|---|
| `tests/data/test_v23_migration.py` | **NEW.** v23 rename/FK/backup-gate/rollback/idempotency/schema-parity. | T-3.1 |
| `tests/data/repos/test_chart_renders_repo.py` | Update fixtures referencing `hyprec_detail`; assert validator rejects old value. | T-3.1 |
| `tests/web/test_charts.py` | Rename references; candle-helper tests; ticker_detail neutral-title; BULZ zones; per-surface ASCII; `_x_for_date`/`_normalize_ohlc_for_mpf`. | T-3.1..T-3.5 |
| `tests/web/test_charts_volume_yticks_stripped.py` | Resolve volume axis by role (not index); strip y-ticks via the helper. | T-3.2 |
| `tests/web/test_chart_jit.py` | Rename dispatch key; weather default `"undefined"`; thumbnail-substrate proof. | T-3.1, T-3.4, T-3.5 |
| `tests/web/test_weather_trend_state.py` | **NEW.** 3-site `current_stage` derivation + fail-soft + uniformity (Expansion #10c). | T-3.4 |
| `tests/web/test_chart_renderer_rename_no_orphans.py` | **NEW.** L5 two-tier grep gate. | T-3.1 |
| `tests/integration/test_l2_lock_source_grep.py` | **Unchanged** — verified still green (no new `schwabdev.Client.*`). | T-3.6 |
| `tests/web/test_web_charts_import_smoke.py` | **NEW.** Import `swing.web.charts` + `swing.web.app` cleanly (packaging smoke, Codex R2 m#1). | T-3.6 |

---

## §C Surface-by-surface integration

### C.1 The shared candlestick helper (`_render_candles_fig`)

**Canonical pattern to mirror** (`swing/rendering/charts.py:85-100`, verified):
```python
try:
    import matplotlib.pyplot as plt
    import mplfinance as mpf
except ImportError as exc:
    raise ChartingUnavailableError("mplfinance not installed") from exc
# ...
addplots = []
closes = df["Close"]
for window, color in ((10, "blue"), (20, "orange"), (50, "red")):
    sma = closes.rolling(window).mean()
    if not sma.isna().all():
        addplots.append(mpf.make_addplot(sma, color=color, width=1.0))
```

**The web helper** (NEW in `swing/web/charts.py`):
```python
def _render_candles_fig(
    df,
    *,
    ma_windows,
    figsize,
    volume=True,
    style="yahoo",
):
    """Return (fig, price_ax, vol_ax) for an OHLC candlestick chart.

    df MUST be _normalize_ohlc_for_mpf output: Open/High/Low/Close[/Volume]
    columns + an ascending, tz-naive, deduped DatetimeIndex. MA overlays via
    mpf.make_addplot on the close rolling-mean, colored from _MA_COLORS so
    the set is identical across surfaces (Expansion #10c). Volume y-tick
    labels stripped on the resolved volume axis. Gridlines on price_ax
    (P14.N8 uniform). vol_ax is None when volume=False.
    """
```

Implementation contract (each pinned by a test, §H):
- **Import guard** mirrors `rendering/charts.py:85-89`: a `try: import mplfinance as mpf except ImportError: raise RuntimeError(...)` at the `swing/web/charts.py` module-import boundary (the module already does this for matplotlib at `charts.py:49-57`). Hard-fail at import (it is a declared runtime dep; silent line-chart degradation would mask the regression this sub-bundle fixes — Codex R1 M#10).
- **Volume axis resolved by ROLE, never a fixed index** (Codex R1 m#6). With `volume=True`, mpf returns `(fig, axes)` where the count/order shifts with style/panels. Resolve `vol_ax` by introspection — the lowest non-twin panel whose configured lower-ylabel is the volume label — and return an explicit named triple. Callers never touch `axes[i]`.
- **MA windows skipped when `window > len(close)`** (preserve existing guard); each surviving window is one `mpf.make_addplot(sma, color=_MA_COLORS[window], width=1.0)`.
- **`price_ax.grid(True, alpha=0.3)`** for uniform gridlines.
- Returns `(fig, price_ax, vol_ax_or_None)`.

**`_MA_COLORS` — the pinned colorblind-safe palette (OQ-mav-color, RESOLVED at writing-plans).** The Okabe-Ito / Wong (2011, *Nature Methods*) colorblind-safe qualitative set, chosen to (a) be distinguishable under deuteranopia/protanopia, (b) be ASCII hex, and (c) AVOID the pure matplotlib red `#d62728` / green `#2ca02c` used by the BULZ zone fills so MAs stay distinct from the shaded bands:
```python
# Okabe-Ito colorblind-safe palette, keyed by MA window. ASCII hex.
# Deliberately avoids #d62728/#2ca02c (reserved for BULZ risk/reward fills).
_MA_COLORS: dict[int, str] = {
    10:  "#0072B2",  # blue
    20:  "#E69F00",  # orange
    50:  "#009E73",  # bluish green
    150: "#CC79A7",  # reddish purple
    200: "#D55E00",  # vermillion
}
```
`market_weather` (50/200 only) → bluish-green + vermillion (maximally distinct at 400px). A test asserts every window used by any surface has a `_MA_COLORS` entry, and that the 5 hex values are unique.

### C.1b `_normalize_ohlc_for_mpf` (the pre-plot barrier, Codex R1 M#8 + R2 m#2)

mpf is shape-sensitive; cached bars can arrive unsorted, dup-timestamped, tz-aware, lowercase-columned, or as a `group_by='column'` MultiIndex. A shared barrier runs before EVERY `mpf.plot`:
```python
def _normalize_ohlc_for_mpf(bars):
    """Return an mpf-safe OHLC(V) frame or raise a typed ASCII error.

    (a) MultiIndex columns (the yfinance group_by='column' footgun, Price x
        Ticker): flatten ONLY a SINGLE-ticker MultiIndex (take level 0, the
        Price level) — raise OhlcNormalizationError if MORE THAN ONE ticker is
        present (ambiguous: never silently pick a ticker, Codex R1 M#11);
        (b) map/Title-case columns to Open/High/Low/Close/Volume — raise
        OhlcNormalizationError if Title-casing would COLLIDE (e.g. both 'close'
        and 'Close' present) rather than silently picking one;
        (c) sort index ascending; (d) drop duplicate timestamps keep='last'
        (archive write_window convention, gotcha #26 family); (e) make index
        tz-naive; (f) raise OhlcNormalizationError (ASCII, not a deep mpf
        KeyError) if any required OHLC column is absent.
    """
```
- `OhlcNormalizationError(ValueError)` — a NEW typed error in `swing/web/charts.py`, ASCII message.
- The thumbnail (line) renderer keeps `_close_series`/`_volume_series` — it does NOT route through this barrier.
- Tests: unsorted, duplicate-timestamp, tz-aware, MultiIndex, lowercase-column, collision (both `close`+`Close`), and missing-column inputs (last two assert the typed error).

### C.1c `_x_for_date` (single coordinate helper, Codex R1 M#7)

ALL date→x conversion for overlays routes through one helper so mpf's positional-x convention is coupled in ONE place:
```python
def _x_for_date(price_ax, df, target_date):
    """Return the integer bar position for target_date (mpf positional x-axis).

    CRITICAL (Codex R1 M#5): `df` MUST be the SAME normalized frame passed to
    _render_candles_fig — NOT the raw `bars`. mpf draws candles at positions
    0..N-1 of the NORMALIZED (sorted/deduped/tz-naive) frame; if overlays used
    raw `bars.index.get_loc`, an unsorted/duplicate/tz-aware input would place
    the band/marker at the wrong candle. V1: df.index.get_loc(pd.Timestamp(
    target_date)). The SINGLE place coupled to mpf's coordinate convention; an
    mpf upgrade to date-coordinates is a one-function change + its pin test.
    Used by axvspan window bands, fill markers, and any vline.
    """
```
- **Renderer contract (M#5):** each renderer normalizes ONCE — `df = _normalize_ohlc_for_mpf(bars)` — and passes that SAME `df` to BOTH `_render_candles_fig(df, ...)` AND every `_x_for_date(price_ax, df, ...)` call. Raw `bars` is never used for coordinate lookup after normalization. (Fill `fill_datetime` and `pattern_evaluation` window dates are looked up in `df`.)
- **Pin test:** `_x_for_date` returns the expected integer for a known date — AND a second test feeds an UNSORTED raw `bars`, normalizes it, and asserts `_x_for_date(price_ax, df, d)` returns the position in the SORTED frame (not the raw order). This couples to mpf positional x-axis; an upgrade that switches candles to date coords breaks this test + the helper together (intentional).

### C.2 `render_ticker_detail_svg` (renamed; 800×500; MA 10/20/50/150/200)

> **T-3.2-step-0 — browser-embedding diagnosis runs FIRST (Codex R1 M#15).** Before converting, the executing-plans operator captures the FAILING surface (`ticker_detail` hyp-rec-expand + watchlist-expand) in a real browser and diffs its embedding (container CSS `overflow`/`max-height`, SVG `width`/`height`/`viewBox`/`preserveAspectRatio` in `hypothesis_recommendations_expanded.html.j2` + the watchlist expanded partial) against the WORKING `position_detail` embedding. If a CSS/viewBox clipping bug is confirmed, FIX IT FIRST in a separate commit — mpf + `bbox_inches="tight"` will CHANGE the emitted `width`/`height`/`viewBox` (Codex R1 m#5), and converting onto a broken embedding would not fix (and could worsen) an invisible-chart symptom. This is browser-only; the operator-witnessed gate is the verdict.

Conversion: replace the `plt.subplots(nrows=2, height_ratios=[3,1])` + `ax_price.plot(close)` + manual `ax_vol.bar(volume)` block with:
```python
df = _normalize_ohlc_for_mpf(bars)
fig, price_ax, vol_ax = _render_candles_fig(
    df, ma_windows=(10, 20, 50, 150, 200),
    figsize=_figsize_inches(_TICKER_DETAIL_SIZE_PX), volume=True,
)
```
- Port the optional `pattern_evaluation` window band using the NORMALIZED `df` (M#5): `price_ax.axvspan(_x_for_date(price_ax, df, window_start), _x_for_date(price_ax, df, window_end), ...)`.
- **Neutral cache-safe title (V2.G2 fix, Codex R1 M#4).** The single cached `ticker_detail` SVG row is read by BOTH the hyp-rec-expand AND watchlist-expand callers (same `(ticker, surface, pipeline_run_id)` key). A per-caller title would either thrash the cache or show the wrong label. The title becomes caller-agnostic — drop the surface descriptor entirely:
  ```python
  _set_suptitle_no_math(fig, f"{ticker} | last {len(close)} bars")
  ```
  The renderer takes NO `context_label` kwarg (an earlier draft's `context_label` is REJECTED — incompatible with the single-cached-row contract).
- Legend stays `loc="upper left"`.

### C.3 `render_position_detail_svg` (800×500; MA 10/20/50) + BULZ zones (P14.N4)

Conversion + overlays:
```python
df = _normalize_ohlc_for_mpf(bars)
fig, price_ax, vol_ax = _render_candles_fig(
    df, ma_windows=(10, 20, 50),
    figsize=_figsize_inches(_POSITION_DETAIL_SIZE_PX), volume=True,
)
# Re-attach fill markers (integer bar position; NORMALIZED df, M#5):
for f in fills:
    x = _x_for_date(price_ax, df, date.fromisoformat(f.fill_datetime[:10]))
    price_ax.scatter([x], [f.price], marker=..., zorder=5)
price_ax.axhline(current_stop, ...)
# BULZ zones (§C.3a)
```

#### C.3a BULZ risk/reward zones (OQ-N4-target + OQ-N4-color RESOLVED)

**Target field — VERIFIED (#4).** There is NO absolute `target_price` column on `Trade`. The target field is **`planned_target_R: float | None`** (`swing/data/models.py:253`, an R-multiple, CHECK enforces `> 0` when set, nullable for legacy rows). The R-multiple convention is canonical at `swing/data/repos/trades.py:638,645`:
```python
risk_per_share = entry_price - initial_stop
r_mult = (price - entry_price) / risk_per_share
```
**Single entry basis = `trade.entry_price` (Codex R1 M#12 + R2 M#1).** Both bands and the target anchor on ONE entry value, and that value is the trade's LOCKED `entry_price` — NOT the avg-fill entry. Rationale: the planned target is a FIXED absolute price locked at trade open (`trade.entry_price + planned_target_R * (entry_price - initial_stop)`, the inverse of the canonical `r_mult` formula at `repos/trades.py:645`); anchoring the reward-zone lower bound on the same `trade.entry_price` keeps the band coherent with that locked target. Using avg-fill entry would either de-correlate the band from the planned R-multiple (R2 M#1) or force re-deriving the locked target — both rejected for V1.
```python
def _bulz_target_price(trade):
    """Absolute target = trade.entry_price + planned_target_R * (entry_price - initial_stop).

    The inverse of the canonical r_mult formula (repos/trades.py:645); a FIXED
    price locked at trade open. Returns None when planned_target_R is None or
    the locked risk-unit (entry_price - initial_stop) is non-positive (invalid
    long shape -> skip+log path).
    """
    if trade.planned_target_R is None:
        return None
    r_unit = trade.entry_price - trade.initial_stop
    if r_unit <= 0:
        return None
    return trade.entry_price + trade.planned_target_R * r_unit
```

**Zone entry basis** = `trade.entry_price` (the locked entry — single basis with the target above; `entry = trade.entry_price`). Risk band `[current_stop, entry]`; reward band `[entry, target]`.

> **EXPLICIT V1 SIMPLIFICATION — operator-surfaced (Codex R2 M#1 + R3 M#1).** The brainstorm spec §7 asked for the zone entry to be the **average entry-fill price** (fallback `trade.entry_price`). Writing-plans CHANGES this to `trade.entry_price` for the zone geometry, because the canonical locked target is anchored on `trade.entry_price` and a single coherent basis is required (R2 M#1). **This is a deliberate deviation from spec §7, banked to V2** (avg-fill-anchored zones + a re-derived target). It is surfaced HERE for operator awareness at the visual gate — if the operator wants avg-fill anchoring in V1, that is a one-line basis swap PLUS a target re-derivation (do NOT silently re-add only the entry without the target). The individual entry/exit *fill markers* ARE still scattered per-fill on the candles (so partial entries remain visible); only the ZONE GEOMETRY uses the locked entry. **No `_bulz_entry_price` avg-fill helper in V1.**

**Zones** (horizontal price bands via `axhspan`; `entry = trade.entry_price`, `stop = current_stop`, `target = _bulz_target_price(trade)`):
- **Risk zone** `price_ax.axhspan(stop, entry, color="#d62728", alpha=0.10, label="risk zone (entry->stop)")` — drawn only when `current_stop` and `entry` are both present and `stop < entry` (valid long).
- **Reward zone** `price_ax.axhspan(entry, target, color="#2ca02c", alpha=0.10, label="reward zone (entry->target)")` — drawn only when `target` is derivable AND `target > entry`.
- **Long-position-only V1 (Codex R1 M#12).** Zones assume `stop < entry < target` (long). For an invalid/unsupported shape — short, `stop >= entry`, `target <= entry`, or missing/zero entry/stop — SKIP that zone + WARN-log (per-ticker isolation; never raise; never draw an inverted band).
- **Off-range valid zones are DRAWN, not silently skipped (Codex R2 M#3).** A geometrically-valid zone whose level sits outside the visible close range (distant target, far stop) is NOT hidden — drawing `axhspan` autoscales the price y-axis to include it. **The binding rule: never silently drop valid long-only geometry; only invalid shapes are skipped+logged.** If the operator-witnessed gate finds autoscaling compresses the candles unacceptably, the fallback is an edge marker + a legend note (`"target above range: $X"`); writing-plans defers that aesthetic pick to the gate. **Default V1 implementation: draw the `axhspan` (autoscale).**
- **Legend** (the operator complaint "no description of what that means"): the ASCII `label=` strings above render via the existing `price_ax.legend(loc="upper left")`. No `$`/`^`/`_`.
- **Color rationale (OQ-N4-color):** green reward + red-tinted risk; the operator's recalled "green and yellow" maps acceptably to the low-alpha red/green. The SEMANTIC (which band is which) is binding; exact hue confirmed at the operator-witnessed gate (cosmetic).

### C.4 `render_market_weather_svg` (400×150; MA 50/200; P14.N8)

Conversion:
```python
df = _normalize_ohlc_for_mpf(bars)
fig, price_ax, vol_ax = _render_candles_fig(
    df, ma_windows=(50, 200),
    figsize=_figsize_inches(_MARKET_WEATHER_SIZE_PX), volume=True,
)
price_ax.text(0.02, 0.88, f"trend: {trend_template_state}",
              transform=price_ax.transAxes, fontsize=8)  # ASCII body text
```
- `trend_template_state` is now REAL (`"stage_2"`/`"undefined"`) per §C.4a; the badge reading `trend: undefined` is an honest "not computed", visibly distinct from `trend: stage_2` (Codex R1 m#3). The renderer signature `(*, bars, trend_template_state)` is unchanged — the state is computed at the call sites.
- Gridlines come from `_render_candles_fig`.
- MA 50/200 only (OQ-6; 10/20 too noisy at 400px).

#### C.4a Real `current_stage` at the weather sites (P14.N8, OD-3, Expansion #10c)

**2 LIVE compute sites + 1 dead/defensive default.** Only the pipeline render and the interactive-refresh handler are LIVE render paths that produce bytes today; both compute the REAL state. The JIT default is dead (§A.4 correction 5) — its fix is the honest `"undefined"` fallback, NOT a live derivation. "Real state at all 3 sites" elsewhere means: real at the 2 live sites; honest-undefined (not fake `"stage_2"`) at the defensive default.

`current_stage(conn, ticker, asof_date)` — `ticker` = `cfg.rs.benchmark_ticker` (the benchmark passed as the `ticker` arg); `asof_date` is a `datetime.date`. **asof anchored on the RENDER's data context, NOT wall-clock `now()`** (Codex R1 M#5) — a cached SVG must be consistent with the bars it draws + reproducible:

| Site | File:line | Today | Fix |
|---|---|---|---|
| **Pipeline** | `runner.py:2883` | `"stage_2"` literal | `current_stage(conn, benchmark_ticker, <run data_asof date>)`. The run's last-completed-session date — the same anchor the bars were fetched for (NOT `now()`). **Re-grep `_step_charts` scope at implementation (#2)** to bind the exact date variable (`benchmark_ticker` is at `runner.py:2878`; `conn` is in scope). |
| **Interactive refresh** | `routes/dashboard.py:117` | `"n/a"` literal | `current_stage(conn, benchmark, last_completed_session(datetime.now()).date())`. `last_completed_session` IS correct here (true interactive refresh, no better anchor; matches the handler's own `data_asof_date` write at `dashboard.py:127`). Honors "Weather lookup must NOT query by action_session" + "session-anchor read/write" gotchas (backward-looking writer anchor). |
| **JIT default** | `chart_jit.py:158` | `"stage_2"` default | Change default to `"undefined"`. **DEAD/defensive today** (§A.4 correction 5: no production caller routes `market_weather` through the JIT). The honest fallback prevents a fake real-looking stage if a future SB4 caller forgets to compute+pass. Forward note: any future JIT `market_weather` caller MUST compute `current_stage` in the caller and pass `trend_template_state` (keeps `chart_jit` surface-agnostic). |

**Fail-soft at every compute site:** wrap the `current_stage` call in `try/except Exception` → fall back to `"undefined"` (ASCII; NOT `"n/a"`) + WARN log carrying which precondition was missing. Never 500 the refresh / abort the pipeline step. Mirrors the detector usage pattern.

**Dependency contract:** `current_stage` needs `conn` + benchmark ticker + a populated candidates/evaluation_runs history (it reads `candidates`/`candidate_criteria`/`evaluation_runs`). Pipeline + refresh handler already hold `conn` + `cfg`. Tests for: missing benchmark, no candidate history (→ `"undefined"`, foundation.py:775-776), exception (→ `"undefined"` + WARN) — all yield `"undefined"`, never a crash.

**Discriminating test (Expansion #10c, byte-parity-insufficient):** mock `current_stage` → a sentinel string; assert the sentinel reaches `render_market_weather_svg`'s `trend_template_state` at EACH production compute site (pipeline + refresh handler). A pure byte-parity test would pass against a hardcoded literal that happened to match — the test must prove the DERIVATION PATH.

### C.5 `render_theme2_annotated_svg` (800×600; MA 10/20/50/150/200; volume-less) + S6

Conversion (volume-less to preserve the single-axis layout the `_annotate_*` family draws into):
```python
df = _normalize_ohlc_for_mpf(bars)
fig, price_ax, vol_ax = _render_candles_fig(
    df, ma_windows=(10, 20, 50, 150, 200),
    figsize=_figsize_inches(_THEME2_ANNOTATED_SIZE_PX), volume=False,
)  # vol_ax is None
```
The `_ANNOTATORS` dispatch + window band + slug + exemplar footnote re-attach to `price_ax` (window band via `_x_for_date`).

#### C.5a S6 annotation-layout policy (Codex R1 M#13, OQ-S6 RESOLVED → move text upper-right)

**Verified collision:** `_annotate_flat_base` writes `"duration: N days"` at `(0.02, 0.92)` (`charts.py:421`) under `ax.legend(loc="upper left")` (`charts.py:542`). The whole family collides: `_annotate_vcp` `(0.02, 0.92 - i*0.05)` (400-404), `_annotate_cup_with_handle` `(0.02, 0.92)` (431), `_annotate_high_tight_flag` `(0.02, 0.92)`+`(0.02, 0.86)` (445/449), `_annotate_double_bottom_w` `(0.02, 0.92)` (468).

**Fix — a per-surface reserved-region map, not an ad-hoc move:**
- **legend** = upper-left (`loc="upper left"`, unchanged).
- **pattern-class slug** = top-right corner (`0.98, 0.95`, `ha="right"`, existing).
- **`_annotate_*` text stack** = right-edge starting `(0.98, 0.92)` DESCENDING by `0.05` per line, `ha="right"` (co-located with the existing right-aligned slug, away from the upper-left legend).
- **exemplar footnote** = bottom-right (`0.98, 0.02`, existing).
- **Bounded line budget:** the stack has a max line count (the worst case is `_annotate_vcp`'s contraction list). The budget is confirmed at the operator-witnessed gate. **The `_annotate_*` stack only applies to `theme2_annotated`** (800×600 — the roomiest surface; it is the ONLY surface with the `_annotate_*` family), so the worst-case visual check is: vcp with the most contractions + longest labels + the full 5-MA set, on `theme2_annotated` (Codex R1 m#3 — earlier "smallest adopting surface" wording was wrong; the annotation stack is theme2-only). `market_weather` (400×150) is checked SEPARATELY for its OWN cramped layout (the trend badge + 2 MA legend entries; no `_annotate_*` stack).
- ASCII-only (`_assert_ascii_only`); body text via `ax.text` allows `_` (literal outside math mode) — see §F ASCII gate.

### C.6 P14.N1 thumbnail substrate (substrate-only, OQ-4 RESOLVED → defer wiring to SB4)

- **Reuse `render_watchlist_thumbnail_svg`** (line chart, 200×100; thumbnails stay line per OD-2). NO new renderer.
- **Cache-key:** reuse the `watchlist_row` surface with the existing run-bound key `(ticker, surface, pipeline_run_id)`. Do NOT add `open_position_thumbnail`/`hyprec_thumbnail` enums (would force a second v-bump + widen the rename blast radius; YAGNI — no operator requirement for divergent thumbnails today).
- **Thumbnail identity contract (Codex R1 M#11):** a `watchlist_row` thumbnail is defined SOLELY by `(ticker, pipeline_run_id)`; identical bytes regardless of embedding table. Dimensions 200×100; MA overlays = caller `ma_lines` (default `_WATCHLIST_THUMBNAIL_MA_LINES = [20, 50]`, `chart_jit.py:68` — both callers MUST pass identical `ma_lines`, Expansion #10c); chart type close-line; run-bound key; NO per-table badges/overlays. Divergence boundary: IF SB4 needs table-specific thumbnails it introduces distinct enum(s) THEN (a v24 rename); SB3 does NOT speculatively add them.
- **Deliverable (substrate proof):**
  1. A test proving a NON-watchlist ticker renders + caches a `watchlist_row` thumbnail via `get_or_render_surface(surface="watchlist_row", ...)` (renderer + cache reuse).
  2. A thin VM-level test asserting the open-position + hyp-rec row VMs expose (or can resolve) the `(ticker, pipeline_run_id)` the substrate needs — so SB4's row-template wiring is unblocked, not blocked on a missing VM field (Codex R1 m#9). **NO row TEMPLATE changes in V1.**

---

## §D Out of scope (do NOT design/implement)

- Review+journal UX (SB4); metrics overview (SB5).
- P14.N1 consuming-surface row TEMPLATE wiring (deferred to SB4) — substrate-only here.
- Candlestick THUMBNAILS (OD-2 — thumbnails stay close-line).
- **Avg-fill-anchored BULZ zone geometry** (deviation from spec §7; banked to V2 per Codex R2 M#1 + R3 M#1 — V1 zone entry is the locked `trade.entry_price`; operator-surfaced at §C.3a + the visual gate).
- Distinct `open_position_thumbnail`/`hyprec_thumbnail` surfaces (V2/SB4 + a v24 rename).
- Any schema beyond v23; the v22 temporal-log substrate (`pattern_detection_events`, `pattern_forward_observations`) — UNTOUCHED.
- JS charting (Q5 — matplotlib SVG only; mplfinance is matplotlib-based, compatible).
- Historical chart re-render / backfill.
- Schwab API changes (L2 LOCK — zero new `schwabdev.Client.*`).
- `chart_renders` retention/eviction (pre-existing banked candidate).
- Phase 15+.

---

## §E LOCK reverification (per task)

### E.1 Sec 9.1 commissioning LOCKs
- **Q1** sequencing (charts after temporal log) — this IS SB3. ✔
- **Q2** SERIAL — single executing-plans dispatch, serial tasks (shared `charts.py` merge surface). ✔
- **Q4** V2.G2 rename ships as a v23 migration THIS sub-bundle — T-3.1. ✔
- **Q5** matplotlib SVG only, no JS — mplfinance is matplotlib-based. ✔
- **Q6** operator browser-witnessed close-out — §I visual-gate ladder. ✔
- **Q7** SINGLE Codex chain — §J. ✔

### E.2 Brainstorm L1-L7
- **L1** scope = the 7 items only; no widening. ✔ (§A.1, §D)
- **L2** v23 #11 paired + #9 BEGIN/COMMIT + STRICT `pre_version==22` backup gate. ✔ (T-3.1, §K)
- **L3** renderer-kwargs uniformity + cache-collision tests. ✔ (`_render_candles_fig` centralizes; ticker_detail single-row test; weather 3-site test; thumbnail identical-`ma_lines` test)
- **L4** visual-gate binding; byte/string insufficient. ✔ (§I, §H.CANNOT)
- **L5** zero-orphan rename — two-tier grep gate. ✔ (T-3.1, §E.3)
- **L6** L2 LOCK preserved; `current_stage` reads weather/candidate rows only (no Schwab). ✔ (T-3.6 grep)
- **L7** P14.N8 matches the canonical render (computes real `current_stage`), does NOT suppress. ✔ (§C.4a)

### E.3 §1.3 operator-LOCKed OQ dispositions (all 11)
| OQ | Disposition | Where in plan |
|---|---|---|
| P14.N8 scope | real `current_stage` at the 2 LIVE sites (pipeline + refresh); 3rd (JIT default) is honest `"undefined"` (dead/defensive — §A.4 correction 5) | §C.4a |
| Candlestick scope | 4 detail surfaces; thumbnail stays line | §C.2-5, §C.6 |
| Codex chain | SINGLE | §J |
| OQ-4 (P14.N1) | substrate-only; wiring → SB4 | §C.6 |
| OQ-6 (weather MA) | 50/200 | §C.4 |
| OQ-7 (v23 row) | in-migration `UPDATE`/`CASE` | §K, T-3.1 |
| OQ-S6 | text → upper-right | §C.5a |
| OQ-mav-color | pinned Okabe-Ito palette | §C.1 `_MA_COLORS` |
| OQ-N4-target | `planned_target_R` derived; target-only-if-present | §C.3a |
| OQ-N4-color | semantics binding; hue at gate | §C.3a |
| Full rename | `render_hyprec_detail_svg`→`render_ticker_detail_svg` + ALL mirrors | T-3.1, §B.1 |

**L5 two-tier grep gate (Codex R1 M#14 + R2 M#3/M#4/m#2):**
- **Runtime-FORBIDDEN** (ZERO `hyprec_detail`/`render_hyprec_detail_svg`/`hyprec-detail-chart`/`_HYPREC_DETAIL_SIZE_PX`/ the prose `"hyp-rec detail"`): `swing/**/*.py` + `swing/**/*.sql` + `swing/web/templates/**` + `swing/web/static/**/*.css`/`*.js` (the CSS-class rename means static assets must be scanned), EXCEPT the GLOB-matched frozen migrations `swing/data/migrations/0020_*.sql` and `0023_*.sql` (the latter legitimately holds the old token in the `CASE WHEN surface='hyprec_detail'` clause).
- **ALLOWED/EXPECTED** (old token MAY appear): `0020`+`0023` migration SQL; tests asserting the migration renames the old value OR the validator rejects `'hyprec_detail'` (must reference the literal); historical `docs/**` (provenance, not rewritten).
- **Template-filename exemption:** `hypothesis_recommendations_expanded.html.j2` keeps its name (it names the hyp-rec card, a real domain surface, not the chart-surface enum). The gate targets the `hyprec_detail` SURFACE STRING + renderer name + CSS class + size constant, NOT the filename.

---

## §F Discipline + watch items (per task)

Applies to EVERY task unless noted:
- **Matplotlib mathtext (two gates, not one):** (a) TITLE/suptitle via `_assert_title_no_math` FORBIDS `$`/`^`/`_`/`\` — pattern slugs with `_` MUST NOT flow into titles; (b) BODY `ax.text(...)` via `_assert_ascii_only` only (ASCII; `_`/`^` are LITERAL outside `$..$`, verified `charts.py:90-98`). So `ax.text(0.98, 0.92, "flat_base")` is SAFE; `suptitle("… flat_base …")` is NOT. Manual visual verification of rendered text is non-optional (§I).
- **mpf title→suptitle gotcha:** mpf renders `title=` as `fig.suptitle`, not `axes[0].title`; do NOT also `set_title` (duplicate). Either suppress mpf's title and set our own via `_set_suptitle_no_math` post-`returnfig`, or pass the ASCII-gated string to mpf's `title=`. Pin the choice in T-3.2.
- **mpf positional integer x-axis:** candles use bar `0..N-1` even with a DatetimeIndex; overlays use `_x_for_date` (§C.1c). Integer-extent pin test.
- **#11 paired (T-3.1):** schema CHECK + `_CHART_SURFACE_VALUES` constant + `ChartRender.__post_init__` validator + `_row_to_chart_render` mapper + renderer name + routes + VMs + templates + tests — ALL in T-3.1.
- **#9 migration runner:** explicit `BEGIN;…COMMIT;`; rollback-through-runner test; FK-off during rebuild inherited from `_apply_migration`.
- **#11 backup gate STRICT** `pre_version == 22`; run-migrate-twice no-op test.
- **Expansion #10c kwargs uniformity:** `_render_candles_fig` centralizes candle/MA/volume/gridline kwargs; cache-collision discriminating tests at reused surfaces.
- **Windows cp1252 stdout:** renderers return bytes (no stdout); no new `print`/`click.echo` paths. ASCII everywhere.
- **ZERO Co-Authored-By; final `-m` paragraph plain prose** (a line starting `Word:` parses as a git trailer); verify `git log -1 --format='%(trailers)'` is `[]` before pushing. No `--no-verify`.
- **Per-ticker isolation (#27):** renderers already per-ticker try/except + WARN-log; preserved. Empty-pool/early-return inside best-effort try/except must still WARN (no silent skip).

---

## §G Per-task slicing (T-3.1 .. T-3.6)

### §G.0 Commit cadence preface (Expansion #13)
- TDD per step: failing test → see fail → minimal impl → see pass → commit.
- Each task = 3-5 commits max; conventional commit messages (`feat(web):`, `fix(web):`, `refactor(...)`, `test(...)`, `feat(data):`). Commit stem for the plan doc itself: `docs(phase14-sub-bundle-3-plan): …`.
- **Cascade audit each task:** after each task re-run the L5 grep gate (T-3.1+) + `ruff check swing/` + the relevant test subset. Verify `%(trailers)` is `[]` per commit.
- SERIAL execution (shared `charts.py` merge surface).

---

### Task T-3.1: v23 rename + migration + backup gate + atomic Python/template rename + L5 gate

**Lands FIRST** — schema + rename are the foundation; every later task builds on the renamed surface/function.

**Files:**
- Create: `swing/data/migrations/0023_phase14_sb3_chart_surface_rename.sql`
- Create: `tests/data/test_v23_migration.py`
- Create: `tests/web/test_chart_renderer_rename_no_orphans.py`
- Modify: `swing/data/db.py` (line 46 + new gate + wire-in)
- Modify: `swing/data/models.py:99`
- Modify: `swing/data/repos/chart_renders.py` (comments)
- Modify: `swing/web/charts.py` (rename `render_hyprec_detail_svg`→`render_ticker_detail_svg`, `_HYPREC_DETAIL_SIZE_PX`→`_TICKER_DETAIL_SIZE_PX`, module-header bullet — NO candlestick change yet)
- Modify: `swing/web/chart_jit.py:44,57,142`
- Modify: `swing/web/routes/watchlist.py:199,216`
- Modify: `swing/web/view_models/dashboard.py:761,767,769`
- Modify: `swing/web/view_models/watchlist.py:125`
- Modify: `swing/pipeline/runner.py` (comment only)
- Modify: `swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2:78,86,87`
- Modify: `tests/data/repos/test_chart_renders_repo.py`, `tests/web/test_charts.py`, `tests/web/test_chart_jit.py` (rename references)

- [ ] **Step 1: Derive the v23 DDL from a migrated-to-v22 fixture's live schema (authoring-time, Codex R1 M#1 + R2 M#2).** Run against a throwaway v22-migrated DB:
```bash
python -c "import sqlite3, swing.data.db as db; \
c=sqlite3.connect(':memory:'); db.run_migrations(c); \
print(c.execute(\"SELECT sql FROM sqlite_schema WHERE name='chart_renders'\").fetchone()[0]); \
[print(r[0]) for r in c.execute(\"SELECT sql FROM sqlite_schema WHERE type='index' AND tbl_name='chart_renders' AND sql IS NOT NULL\")]"
```
Expected: the live `CREATE TABLE chart_renders` + 3 `CREATE UNIQUE INDEX` statements. PASTE them into `0023_*.sql` changing ONLY the `surface` CHECK enum token `'hyprec_detail'`→`'ticker_detail'`. Do NOT hand-transcribe from the `0020` excerpt. The migration stays a STATIC SQL file (no apply-time introspection).

- [ ] **Step 2: Write `0023_phase14_sb3_chart_surface_rename.sql`** (illustrative shape — bind the table/index bodies to Step 1 output):
```sql
BEGIN;
CREATE TABLE chart_renders_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    surface TEXT NOT NULL CHECK (surface IN (
        'watchlist_row', 'ticker_detail', 'position_detail',
        'market_weather', 'theme2_annotated'
    )),
    pipeline_run_id INTEGER REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    pattern_class TEXT CHECK (
        pattern_class IS NULL OR pattern_class IN (
            'vcp', 'flat_base', 'cup_with_handle',
            'high_tight_flag', 'double_bottom_w'
        )
    ),
    chart_svg_bytes BLOB NOT NULL,
    source_data_hash TEXT NOT NULL,
    rendered_at TEXT NOT NULL,
    data_asof_date TEXT NOT NULL,
    CHECK (
        (surface = 'theme2_annotated' AND pattern_class IS NOT NULL AND pipeline_run_id IS NOT NULL)
        OR (surface != 'theme2_annotated' AND pattern_class IS NULL)
    )
);
INSERT INTO chart_renders_new (id, ticker, surface, pipeline_run_id, pattern_class,
        chart_svg_bytes, source_data_hash, rendered_at, data_asof_date)
    SELECT id, ticker,
        CASE WHEN surface = 'hyprec_detail' THEN 'ticker_detail' ELSE surface END,
        pipeline_run_id, pattern_class, chart_svg_bytes, source_data_hash,
        rendered_at, data_asof_date
    FROM chart_renders;
DROP TABLE chart_renders;
ALTER TABLE chart_renders_new RENAME TO chart_renders;
CREATE UNIQUE INDEX idx_chart_renders_run_bound ON chart_renders(ticker, surface, pipeline_run_id)
    WHERE pipeline_run_id IS NOT NULL AND surface != 'theme2_annotated';
CREATE UNIQUE INDEX idx_chart_renders_position_detail ON chart_renders(ticker, surface)
    WHERE pipeline_run_id IS NULL AND surface = 'position_detail';
CREATE UNIQUE INDEX idx_chart_renders_theme2_annotated ON chart_renders(ticker, surface, pipeline_run_id, pattern_class)
    WHERE surface = 'theme2_annotated' AND pipeline_run_id IS NOT NULL;
UPDATE schema_version SET version = 23;
COMMIT;
```

- [ ] **Step 3: Write the failing schema-parity + rename + FK tests** in `tests/data/test_v23_migration.py`:
```python
def test_v23_migration_renames_existing_chart_renders_rows(v22_db_with_chart_renders):
    conn = v22_db_with_chart_renders  # has a 'hyprec_detail' row with known id
    row_id = conn.execute(
        "SELECT id FROM chart_renders WHERE surface='hyprec_detail'").fetchone()[0]
    db.run_migrations(conn)
    assert db.schema_version(conn) == 23
    got = conn.execute("SELECT surface FROM chart_renders WHERE id=?", (row_id,)).fetchone()
    assert got[0] == "ticker_detail"  # same id preserved

def test_v23_migration_preserves_chart_render_fk_from_detection_events(v22_db_with_fk):
    # pattern_detection_events.chart_render_id -> chart_renders.id (ON DELETE SET NULL)
    conn = v22_db_with_fk
    cr_id = conn.execute("SELECT id FROM chart_renders WHERE surface='hyprec_detail'").fetchone()[0]
    ev_id = conn.execute("SELECT id FROM pattern_detection_events WHERE chart_render_id=?", (cr_id,)).fetchone()[0]
    db.run_migrations(conn)
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    # same id preserved -> the referencing row still resolves
    assert conn.execute("SELECT chart_render_id FROM pattern_detection_events WHERE id=?", (ev_id,)).fetchone()[0] == cr_id
    assert conn.execute("SELECT surface FROM chart_renders WHERE id=?", (cr_id,)).fetchone()[0] == "ticker_detail"

def test_v23_schema_parity_normalized_sql(v22_db):
    # Codex R2 M#1 — PRAGMAs miss CHECK text + partial-index WHERE; compare
    # normalized sqlite_schema.sql for chart_renders + 3 indexes; identical
    # EXCEPT the single hyprec_detail->ticker_detail enum token.
    def norm(sql):
        # Codex R1 M#9 — strip identifier quotes ("x" / [x] / `x`) + the
        # intermediate _new table name SQLite may emit after ALTER..RENAME, then
        # collapse whitespace + lowercase. Robust to SQLite re-quoting.
        s = " ".join(sql.split()).lower()
        s = s.replace('"', "").replace("[", "").replace("]", "").replace("`", "")
        s = s.replace("chart_renders_new", "chart_renders")
        return s
    def schema_sqls(conn):
        rows = conn.execute(
            "SELECT name, sql FROM sqlite_schema "
            "WHERE (name='chart_renders' OR tbl_name='chart_renders') AND sql IS NOT NULL"
        ).fetchall()
        return {name: norm(sql) for name, sql in rows}
    before = schema_sqls(v22_db)
    db.run_migrations(v22_db)
    after = schema_sqls(v22_db)
    assert set(before) == set(after)  # same objects (table + 3 indexes)
    for name in before:
        # identical EXCEPT the single enum-token rename
        assert before[name].replace("'hyprec_detail'", "'ticker_detail'") == after[name], name

def test_v23_backup_gate_fires_strict_pre_version_22(tmp_path, monkeypatch):
    # a real file-backed v22 DB -> v23 writes swing-pre-phase14-sb3-migration-*.db
    conn, db_path = _make_file_v22_db(tmp_path)
    db.run_migrations(conn, backup_dir=tmp_path)
    assert list(tmp_path.glob("swing-pre-phase14-sb3-migration-*.db"))

def test_v23_backup_gate_skips_from_pre_v22(tmp_path):
    # a v21 DB walked to v23 bypasses the SB3 gate (current_version != 22)
    conn, _ = _make_file_v21_db(tmp_path)
    db.run_migrations(conn, backup_dir=tmp_path)
    assert not list(tmp_path.glob("swing-pre-phase14-sb3-migration-*.db"))

def test_run_migrations_twice_v23_no_op(v23_db):
    db.run_migrations(v23_db)  # second run is a no-op
    assert db.schema_version(v23_db) == 23

def test_v23_migration_rollback_through_runner_leaves_v22(monkeypatch, v22_db):
    # #9 (Codex R1 M#3) — inject a failure WITHIN the 0023 script BEFORE
    # `UPDATE schema_version`/COMMIT so executescript() raises mid-script and
    # the runner's except->rollback path fires. _patch_0023_sql replaces the
    # 0023 file's read_text with valid DDL up to a deliberately-invalid stmt.
    _patch_0023_sql(monkeypatch, _BROKEN_0023_BEFORE_COMMIT)
    with pytest.raises(sqlite3.OperationalError):
        db.run_migrations(v22_db)
    assert db.schema_version(v22_db) == 22  # rolled back; not 23
    assert v22_db.execute(
        "SELECT surface FROM chart_renders WHERE surface='hyprec_detail'").fetchone() is not None

def test_apply_migration_restores_foreign_keys_after_v23(v22_db):
    # Codex R1 M#2 — finally-block restore on the SUCCESS path
    v22_db.execute("PRAGMA foreign_keys=ON")
    db.run_migrations(v22_db)
    assert v22_db.execute("PRAGMA foreign_keys").fetchone()[0] == 1

def test_apply_migration_restores_foreign_keys_after_rollback(monkeypatch, v22_db):
    # Codex R1 M#4 — exercise the EXCEPT/rollback restore path (not the success
    # path). Same mid-script-failure injection as the rollback test above.
    v22_db.execute("PRAGMA foreign_keys=ON")
    _patch_0023_sql(monkeypatch, _BROKEN_0023_BEFORE_COMMIT)
    with pytest.raises(sqlite3.OperationalError):
        db.run_migrations(v22_db)
    assert v22_db.execute("PRAGMA foreign_keys").fetchone()[0] == 1

def test_chart_render_dataclass_rejects_hyprec_detail():
    with pytest.raises(ValueError):
        ChartRender(id=None, ticker="AAPL", surface="hyprec_detail",
                    chart_svg_bytes=b"<svg/>", source_data_hash="h",
                    rendered_at="2026-05-30T00:00:00Z", data_asof_date="2026-05-29",
                    pipeline_run_id=1, pattern_class=None)
```
Run: `python -m pytest tests/data/test_v23_migration.py -v` → FAIL (migration/gate absent).

- [ ] **Step 4: Add `_phase14_sb3_backup_gate` to `db.py`** (mirror `_phase14_backup_gate` at db.py:820-860, gate `== 22`):
```python
PHASE14_SB3_PRE_MIGRATION_EXPECTED_TABLES = (
    "chart_renders", "pattern_detection_events", "pattern_forward_observations",
)

def _phase14_sb3_backup_gate(conn, *, current_version, target_version, backup_dir):
    """Fires only when current_version == 22 AND target_version >= 23 (STRICT).
    Filename: swing-pre-phase14-sb3-migration-<ISO>.db. Multi-version walks
    from pre-v22 baselines bypass by design (Phase 9/12/13/SB2 precedent).
    """
    if target_version < 23 or current_version != 22:
        return
    # ... mirror _phase14_backup_gate body: resolve src, backup, verify integrity
```
Set `EXPECTED_SCHEMA_VERSION = 23` (db.py:46). Wire `_phase14_sb3_backup_gate` into `run_migrations` AFTER `_phase14_backup_gate`.

- [ ] **Step 5: Flip `_CHART_SURFACE_VALUES`** (`models.py:99`) `"hyprec_detail"`→`"ticker_detail"`. Run: `python -m pytest tests/data/test_v23_migration.py -v` → PASS.

- [ ] **Step 6: Atomic Python/template/test rename (one commit-group, #11 paired):** `render_hyprec_detail_svg`→`render_ticker_detail_svg` (def + docstring + module-header bullet, `charts.py:226`); `_HYPREC_DETAIL_SIZE_PX`→`_TICKER_DETAIL_SIZE_PX` (`charts.py:61`); `chart_jit.py` import/`_RENDERERS` key/dispatch (44,57,142); `routes/watchlist.py` literal+comment (199,216); `view_models/dashboard.py` field `hyprec_detail_chart_svg_bytes`→`ticker_detail_chart_svg_bytes` + surface literal (761,767,769); `view_models/watchlist.py` comment (125); `runner.py` comment; template var + CSS class (`hypothesis_recommendations_expanded.html.j2:78,86,87`); all test references. **NEUTRAL TITLE lands HERE too (Codex R2 M#2):** change `charts.py:275` `f"{ticker} | hyp-rec detail | last {len(close)} bars"` → `f"{ticker} | last {len(close)} bars"` in the SAME atomic rename, so there is NO intermediate post-rename state that still emits the leaked `"hyp-rec detail"` prose. (The candlestick conversion in T-3.2 keeps this neutral title; it just changes the chart body.) Add a failing test `test_ticker_detail_title_is_neutral_no_surface_descriptor` here.

- [ ] **Step 7: Write + pass the L5 no-orphan grep gate** in `tests/web/test_chart_renderer_rename_no_orphans.py`:
```python
import pathlib, fnmatch
# Codex R2 M#4 — also forbid the operator-visible leaked PROSE "hyp-rec detail"
# (the actual title leak), not just the snake/kebab tokens.
FORBIDDEN = ("hyprec_detail", "render_hyprec_detail_svg", "hyprec-detail-chart",
             "_HYPREC_DETAIL_SIZE_PX", "hyp-rec detail")
# Codex R2 m#2 — GLOB allowlist (robust to exact migration filenames) for files
# that intentionally retain the old token (frozen 0020 + the 0023 CASE clause).
ALLOW_GLOBS = (
    "swing/data/migrations/0020_*.sql",
    "swing/data/migrations/0023_*.sql",
)
# Codex R2 M#3 — scan .py + .sql + templates AND static assets (.css/.js/.html)
# since the CSS class hyprec-detail-chart is renamed; a stale static ref would
# otherwise slip the gate.
SCAN = ["swing/**/*.py", "swing/**/*.sql",
        "swing/web/templates/**/*.j2", "swing/web/templates/**/*.html",
        "swing/web/static/**/*.css", "swing/web/static/**/*.js"]
def test_no_orphaned_hyprec_detail_tokens():
    root = pathlib.Path(__file__).resolve().parents[2]
    offenders = []
    for pattern in SCAN:
        for path in root.glob(pattern):
            rel = path.relative_to(root).as_posix()
            if any(fnmatch.fnmatch(rel, g) for g in ALLOW_GLOBS):
                continue
            text = path.read_text(encoding="utf-8")
            for tok in FORBIDDEN:
                if tok in text:
                    offenders.append(f"{rel}: {tok}")
    assert offenders == [], offenders
```
> The TEST FILES themselves legitimately contain the tokens (migration/validator negative assertions) — they live under `tests/**`, which `SCAN` does NOT cover, so they are not scanned. This matches the §E.3 two-tier allowlist: runtime-forbidden = `swing/**` (minus the migration globs) + templates + static; allowed = migration SQL + `tests/**` negative-assertions + `docs/**`.

Run: `python -m pytest tests/web/test_chart_renderer_rename_no_orphans.py -v` → PASS (after the rename); `ruff check swing/`.

- [ ] **Step 8: Full fast suite + commit.** `python -m pytest -m "not slow" -q`; fix any rename fallout. Commit (plain-prose final paragraph). Verify `git log -1 --format='%(trailers)'` → `[]`.

**Acceptance:** v23 applies on a real v22 DB (`schema_version==23`, rows renamed same-id, backup written, `PRAGMA foreign_key_check` clean, FK from `pattern_detection_events` resolves); `_apply_migration` restores `foreign_keys` on success AND rollback; validator rejects `'hyprec_detail'`; L5 grep zero in runtime-forbidden paths; rename does NOT touch candlestick logic. Locks: Q4, L2, L5, #11, #9.

---

### Task T-3.2: `_render_candles_fig` helper + `_normalize_ohlc_for_mpf` + `_x_for_date` + MA palette + convert `ticker_detail` & `theme2_annotated`

> **Step 0 (browser, operator-witnessed, BEFORE conversion):** the §C.2 embedding diagnosis. If a CSS/viewBox clipping bug is confirmed for `ticker_detail`/`watchlist-expand`, FIX IT FIRST in a separate `fix(web):` commit. Recorded in the executing-plans return report.

**Files:** Modify `swing/web/charts.py`; `tests/web/test_charts.py`; `tests/web/test_charts_volume_yticks_stripped.py`.

- [ ] **Step 1: Add the mplfinance import-guard** at the `charts.py` import boundary (mirror matplotlib guard at 49-57):
```python
try:
    import mplfinance as mpf
except ImportError as exc:  # pragma: no cover - install gate
    raise RuntimeError(
        "mplfinance is required for swing/web/charts.py candlestick rendering; "
        "install via pip install -e \".[web]\""
    ) from exc
```

- [ ] **Step 2: Write failing tests for `_MA_COLORS`, `_normalize_ohlc_for_mpf`, `_x_for_date`, `_render_candles_fig`:**
```python
def test_ma_colors_cover_all_surface_windows_and_are_unique():
    used = {10,20,50,150,200}
    assert used <= set(charts._MA_COLORS)
    assert len(set(charts._MA_COLORS.values())) == len(charts._MA_COLORS)

def test_normalize_ohlc_sorts_dedups_tznaive_and_squeezes_multiindex():
    idx = pd.to_datetime(["2026-05-28","2026-05-26","2026-05-27","2026-05-27"], utc=True)
    raw = pd.DataFrame({"Open":[1,2,3,4],"High":[1,2,3,4],"Low":[1,2,3,4],
                        "Close":[1,2,3,9],"Volume":[1,1,1,1]}, index=idx)
    out = charts._normalize_ohlc_for_mpf(raw)
    assert list(out.index) == sorted(out.index)          # ascending
    assert out.index.tz is None                          # tz-naive
    assert len(out) == 3                                  # dup 05-27 deduped keep=last
    assert out.loc[pd.Timestamp("2026-05-27"), "Close"] == 9  # keep='last'
def test_normalize_ohlc_raises_on_missing_column():
    bars_without_high = pd.DataFrame({"Open":[1],"Low":[1],"Close":[1]},
                                     index=pd.to_datetime(["2026-05-27"]))
    with pytest.raises(charts.OhlcNormalizationError):
        charts._normalize_ohlc_for_mpf(bars_without_high)
def test_normalize_ohlc_raises_on_titlecase_collision():
    # both 'close' and 'Close' present -> typed error, not silent pick
    raw = pd.DataFrame({"Open":[1],"High":[1],"Low":[1],"close":[1],"Close":[1]},
                       index=pd.to_datetime(["2026-05-27"]))
    with pytest.raises(charts.OhlcNormalizationError):
        charts._normalize_ohlc_for_mpf(raw)
def test_normalize_ohlc_flattens_single_ticker_multiindex():
    cols = pd.MultiIndex.from_product([["Open","High","Low","Close","Volume"],["AAPL"]])
    raw = pd.DataFrame([[1,2,0,1.5,1e6]], index=pd.to_datetime(["2026-05-27"]), columns=cols)
    out = charts._normalize_ohlc_for_mpf(raw)
    assert {"Open","High","Low","Close"} <= set(out.columns)  # flattened to Price level
def test_normalize_ohlc_raises_on_multi_ticker_multiindex():
    # ambiguous: never silently pick a ticker (Codex R1 M#11)
    cols = pd.MultiIndex.from_product([["Open","High","Low","Close"],["AAPL","MSFT"]])
    raw = pd.DataFrame([[1,1,2,2,0,0,1.5,1.5]], index=pd.to_datetime(["2026-05-27"]), columns=cols)
    with pytest.raises(charts.OhlcNormalizationError):
        charts._normalize_ohlc_for_mpf(raw)
def test_x_for_date_returns_integer_bar_position(known_bars):
    # known_bars index[3] == 2026-05-29 (M#5: look up in the NORMALIZED df)
    df = charts._normalize_ohlc_for_mpf(known_bars)
    fig, price_ax, _ = charts._render_candles_fig(df, ma_windows=(10,), figsize=(8,5), volume=True)
    assert charts._x_for_date(price_ax, df, date(2026,5,29)) == 3
    plt.close(fig)
def test_x_for_date_uses_normalized_order_not_raw(known_bars):
    # M#5 — feed an UNSORTED raw frame; the position is in the SORTED df.
    raw = known_bars.iloc[::-1]   # reversed
    df = charts._normalize_ohlc_for_mpf(raw)   # re-sorted ascending
    fig, price_ax, _ = charts._render_candles_fig(df, ma_windows=(10,), figsize=(8,5), volume=True)
    assert charts._x_for_date(price_ax, df, date(2026,5,29)) == 3  # sorted pos, not raw[1]
    plt.close(fig)
def test_render_candles_fig_returns_price_and_volume_axes(ohlc_bars):
    # Codex R1 M#7 — vol_ax resolved by ROLE. PRIMARY check: distinct from
    # price_ax (+ the strip test below confirms it is the volume panel by label).
    # SECONDARY guard: lower-panel geometry (Codex R2 m#1 — geometry alone is
    # layout-brittle, so it is only a secondary cross-check, not the sole proof).
    fig, price_ax, vol_ax = charts._render_candles_fig(
        charts._normalize_ohlc_for_mpf(ohlc_bars),
        ma_windows=(10,20,50), figsize=(8,5), volume=True)
    assert vol_ax is not None
    assert vol_ax is not price_ax                                  # PRIMARY: not the price panel
    assert vol_ax.get_position().y0 < price_ax.get_position().y0   # SECONDARY geometry guard
    plt.close(fig)
def test_render_candles_fig_strips_only_volume_yticks(ohlc_bars):
    # M#7 — ONLY vol_ax has stripped y-ticks; price_ax keeps its price ticks.
    fig, price_ax, vol_ax = charts._render_candles_fig(
        charts._normalize_ohlc_for_mpf(ohlc_bars), ma_windows=(10,), figsize=(8,5), volume=True)
    assert all(t.get_text()=="" for t in vol_ax.get_yticklabels())
    assert any(t.get_text()!="" for t in price_ax.get_yticklabels())  # price ticks intact
    plt.close(fig)
def test_render_candles_fig_grid_enabled(ohlc_bars):
    fig, price_ax, _ = charts._render_candles_fig(
        charts._normalize_ohlc_for_mpf(ohlc_bars), ma_windows=(10,), figsize=(8,5), volume=True)
    assert price_ax.xaxis._major_tick_kw.get("gridOn") or any(l.get_visible() for l in price_ax.get_xgridlines())
    plt.close(fig)
def test_render_candles_fig_volume_false_returns_none_vol_ax(ohlc_bars):
    fig, price_ax, vol_ax = charts._render_candles_fig(
        charts._normalize_ohlc_for_mpf(ohlc_bars), ma_windows=(10,), figsize=(8,6), volume=False)
    assert vol_ax is None
    plt.close(fig)
```
Run → FAIL.

- [ ] **Step 3: Implement `OhlcNormalizationError`, `_MA_COLORS`, `_normalize_ohlc_for_mpf`, `_x_for_date`, `_render_candles_fig`** per §C.1/C.1b/C.1c. Run Step-2 tests → PASS.

- [ ] **Step 4: Convert `render_ticker_detail_svg`** to candlesticks (§C.2) + the NEUTRAL title `f"{ticker} | last {len(close)} bars"`. Failing tests first:
```python
# Codex R1 M#6 — prove candles REPLACED lines (a renderer could still call
# ax.plot(close) and satisfy text/label checks). Spy mpf.plot per converted
# renderer and assert type="candle". Reusable across T-3.2/3.3/3.4.
def _assert_renders_candles(monkeypatch, render_callable, **kwargs):
    seen = {}
    import mplfinance as mpf
    real_plot = mpf.plot
    def spy(df, **kw):
        seen.update(kw)
        return real_plot(df, **kw)
    monkeypatch.setattr("swing.web.charts.mpf.plot", spy)
    render_callable(**kwargs)
    assert seen.get("type") == "candle"

def test_ticker_detail_renders_candles_not_line(monkeypatch, ohlc_bars):
    _assert_renders_candles(monkeypatch, charts.render_ticker_detail_svg,
                            ticker="AAPL", bars=ohlc_bars)
def test_ticker_detail_title_is_neutral_no_surface_descriptor(ohlc_bars):
    svg = charts.render_ticker_detail_svg(ticker="AAPL", bars=ohlc_bars)
    assert b"hyp-rec detail" not in svg
    # title carries ticker + bar count, no surface name
def test_ticker_detail_overlays_pattern_window_band(ohlc_bars, pattern_eval):
    # window band axvspan present at the _x_for_date positions for the eval window
    svg = charts.render_ticker_detail_svg(ticker="AAPL", bars=ohlc_bars, pattern_evaluation=pattern_eval)
    assert svg  # band rendered; positional assertion via captured axvspan in a helper
def test_ticker_detail_cache_single_row_across_two_callers(conn, ohlcv_cache):
    # L3 call_count parity — hyp-rec-expand + watchlist-expand, identical bars
    a = get_or_render_surface(conn=conn, ohlcv_cache=ohlcv_cache, surface="ticker_detail",
        ticker="AAPL", pipeline_run_id=1, data_asof_date="2026-05-29", pattern_evaluation=None)
    b = get_or_render_surface(conn=conn, ohlcv_cache=ohlcv_cache, surface="ticker_detail",
        ticker="AAPL", pipeline_run_id=1, data_asof_date="2026-05-29", pattern_evaluation=None)
    assert a == b  # byte-identical
    n = conn.execute("SELECT COUNT(*) FROM chart_renders WHERE surface='ticker_detail' AND ticker='AAPL'").fetchone()[0]
    assert n == 1  # ONE cached row
def test_ticker_detail_svg_ascii_only(ohlc_bars):
    svg = charts.render_ticker_detail_svg(ticker="AAPL", bars=ohlc_bars)
    svg.decode("ascii")  # raises UnicodeDecodeError if any non-ASCII
```
Implement → PASS.

- [ ] **Step 5: Convert `render_theme2_annotated_svg`** to candlesticks (`volume=False`, §C.5); `_ANNOTATORS`/window-band/slug/footnote re-attach to `price_ax`. (S6 reposition is T-3.5; here only the candle conversion + `_x_for_date` window band.) Tests:
```python
def test_theme2_annotated_renders_candles_not_line(monkeypatch, ohlc_bars, pattern_eval):
    _assert_renders_candles(monkeypatch, charts.render_theme2_annotated_svg,
                            ticker="AAPL", bars=ohlc_bars, pattern_evaluation=pattern_eval)
def test_theme2_annotated_volume_false_single_axis(ohlc_bars, pattern_eval):
    # vol_ax is None; single price axis preserved (the _annotate_* family draws here)
    svg = charts.render_theme2_annotated_svg(ticker="AAPL", bars=ohlc_bars, pattern_evaluation=pattern_eval)
    assert svg
def test_theme2_annotated_ascii_only_all_text(ohlc_bars, pattern_eval):
    charts.render_theme2_annotated_svg(ticker="AAPL", bars=ohlc_bars,
                                       pattern_evaluation=pattern_eval).decode("ascii")
```
Implement → PASS.

- [ ] **Step 6: Pin the mpf positional-x integer-extent contract:**
```python
def test_candles_use_integer_x_axis_positions(ohlc_bars):
    fig, price_ax, _ = charts._render_candles_fig(...)
    xmin, xmax = price_ax.get_xlim()
    assert xmax - xmin == pytest.approx(len(ohlc_bars) - 1, abs=2)  # positional, not date
```

- [ ] **Step 7: Bars fixture precondition test + commit.**
```python
def test_charts_bars_fixture_has_ohlc_columns_and_datetimeindex(ohlc_bars):
    assert {"Open","High","Low","Close"} <= set(ohlc_bars.columns)
    assert isinstance(ohlc_bars.index, pd.DatetimeIndex)
```
`python -m pytest tests/web/test_charts.py -q`; `ruff check swing/`. Commit; verify `%(trailers)` `[]`.

**Acceptance:** the helper resolves the volume axis by role; ticker_detail + theme2_annotated render candlesticks with the pinned MA palette; neutral cache-safe title (single row across both callers); overlays via `_x_for_date`; ASCII gates pass; normalization barrier rejects bad frames with a typed error. Locks: L3, L4, Expansion #10c.

---

### Task T-3.3: `render_position_detail_svg` candlesticks + BULZ risk/reward zones

**Files:** Modify `swing/web/charts.py`; `tests/web/test_charts.py`.

- [ ] **Step 1: Write failing BULZ helper tests** (verify-arithmetic memory — distinguishes from swapped/absent):
```python
def test_bulz_target_price_from_planned_target_R():
    trade = make_trade(entry_price=100.0, initial_stop=90.0, planned_target_R=2.0)
    # R_unit = 100-90 = 10; anchored on trade.entry_price -> target = 100 + 2.0*10 = 120.0
    assert charts._bulz_target_price(trade) == pytest.approx(120.0)
    # distinguishes: swapped R_unit 100 + 2.0*(90-100) = 80.0 would FAIL
def test_bulz_target_price_none_when_planned_target_R_absent():
    assert charts._bulz_target_price(make_trade(planned_target_R=None)) is None
def test_bulz_target_price_none_when_risk_unit_nonpositive():
    assert charts._bulz_target_price(
        make_trade(entry_price=90, initial_stop=100, planned_target_R=2.0)) is None
```
Run → FAIL.

- [ ] **Step 2: Implement `_bulz_target_price`** per §C.3a (single basis on `trade.entry_price`; NO avg-fill helper in V1). Run → PASS.

- [ ] **Step 3: Convert `render_position_detail_svg` to candlesticks** (§C.3, MA 10/20/50) + re-attach fill markers (`_x_for_date`) + `axhline(current_stop)`. Tests:
```python
def test_position_detail_renders_candles_not_line(monkeypatch, ohlc_bars):
    _assert_renders_candles(monkeypatch, charts.render_position_detail_svg,
        ticker="BULZ", bars=ohlc_bars, trade=make_trade(), fills=[], current_stop=95.0)
def test_position_detail_stop_axhline_present(monkeypatch, ohlc_bars):
    lines = []
    monkeypatch.setattr(mpl.axes.Axes, "axhline",
        lambda self, y=0, *a, **k: lines.append(y))
    charts.render_position_detail_svg(ticker="BULZ", bars=ohlc_bars,
        trade=make_trade(), fills=[], current_stop=95.0)
    assert 95.0 in lines
```
Implement → PASS.

- [ ] **Step 4: Write failing zone-bounds tests** (distinguish post-fix from absent/swapped):
```python
# Helper: render position_detail and capture every axhspan's (ymin, ymax) via a
# monkeypatched price_ax.axhspan that records the band bounds (matplotlib's
# axhspan(ymin, ymax, ...) — the first two positional args are the band).
def render_and_capture_axhspans(trade, fills, current_stop, monkeypatch, ohlc_bars):
    spans = []
    orig = mpl.axes.Axes.axhspan
    monkeypatch.setattr(mpl.axes.Axes, "axhspan",
        lambda self, ymin, ymax, *a, **k: (spans.append((ymin, ymax)), orig(self, ymin, ymax, *a, **k))[1])
    svg = charts.render_position_detail_svg(ticker="BULZ", bars=ohlc_bars,
                                            trade=trade, fills=fills, current_stop=current_stop)
    return svg, spans

def test_position_detail_renders_risk_zone_axhspan_bounds(monkeypatch, ohlc_bars):
    # zone entry = trade.entry_price = 100; stop = 95 -> risk axhspan spans (95, 100)
    trade = make_trade(entry_price=100.0, initial_stop=90.0, planned_target_R=None)
    _, spans = render_and_capture_axhspans(trade, [], 95.0, monkeypatch, ohlc_bars)
    assert (95.0, 100.0) in spans          # swapped (100,95) or absent ([]) -> FAIL
def test_position_detail_renders_reward_zone_when_target_present(monkeypatch, ohlc_bars):
    # single basis: entry=trade.entry_price=100; R_unit=(100-90)=10; R=2 -> target=120
    # reward axhspan spans (100, 120); risk band (95, 100)
    trade = make_trade(entry_price=100.0, initial_stop=90.0, planned_target_R=2.0)
    _, spans = render_and_capture_axhspans(trade, [], 95.0, monkeypatch, ohlc_bars)
    assert (100.0, 120.0) in spans
def test_position_detail_risk_zone_only_when_no_target(monkeypatch, ohlc_bars):
    trade = make_trade(entry_price=100.0, initial_stop=90.0, planned_target_R=None)
    _, spans = render_and_capture_axhspans(trade, [], 95.0, monkeypatch, ohlc_bars)
    assert len(spans) == 1                 # risk only; no reward band
def test_position_detail_skips_zones_on_invalid_long_shape_and_warns(monkeypatch, ohlc_bars, caplog):
    # stop >= entry (raised into profit) -> no risk band + WARN; never raises
    trade = make_trade(entry_price=100.0, initial_stop=90.0, planned_target_R=None)
    _, spans = render_and_capture_axhspans(trade, [], 105.0, monkeypatch, ohlc_bars)
    assert spans == []
    assert any("zone" in r.message.lower() for r in caplog.records)
def test_position_detail_off_range_valid_zone_is_drawn_not_hidden(monkeypatch, ohlc_bars):
    # Codex R3 M#2 — a geometrically-valid FAR target (above the visible close
    # range) must be DRAWN (axhspan autoscales the y-axis to include it), never
    # silently hidden. ohlc_bars Close maxes ~220; planned_target_R=20 -> target
    # = 100 + 20*10 = 300 (far above range). Assert the y-axis top reaches it.
    trade = make_trade(entry_price=100.0, initial_stop=90.0, planned_target_R=20.0)
    svg, spans = render_and_capture_axhspans(trade, [], 95.0, monkeypatch, ohlc_bars)
    assert (100.0, 300.0) in spans   # drawn (autoscale includes it), not dropped
    # (visual gate confirms autoscale-vs-edge-marker aesthetics; the band exists)
def test_position_detail_zone_legend_ascii(ohlc_bars):
    trade = make_trade(entry_price=100.0, initial_stop=90.0, planned_target_R=2.0)
    svg = charts.render_position_detail_svg(ticker="BULZ", bars=ohlc_bars,
                                            trade=trade, fills=[], current_stop=95.0)
    assert b"risk zone (entry-&gt;stop)" in svg or b"risk zone (entry->stop)" in svg
    assert b"reward zone (entry-&gt;target)" in svg or b"reward zone (entry->target)" in svg
```
Run → FAIL.

- [ ] **Step 5: Implement the zones** per §C.3a (`axhspan` risk `#d62728`/reward `#2ca02c` alpha 0.10; long-only skip+log; ASCII `label=`; legend `loc="upper left"`). Run → PASS.

- [ ] **Step 6: `ruff check swing/`; `python -m pytest tests/web/test_charts.py -q`; commit.** Verify `%(trailers)` `[]`.

**Acceptance:** risk zone (entry→stop) + reward zone (entry→target, only when `planned_target_R` present) with ASCII legend; invalid long shapes skip+log without raising; target derived from `planned_target_R` via the canonical R formula; zone-bounds tests distinguish from swapped/absent. Locks: P14.N4, L4, #4, verify-arithmetic.

---

### Task T-3.4: `render_market_weather_svg` candlesticks + real `current_stage` at 3 sites + gridlines

**Files:** Modify `swing/web/charts.py`, `swing/pipeline/runner.py:2883`, `swing/web/routes/dashboard.py:117`, `swing/web/chart_jit.py:158`; Create `tests/web/test_weather_trend_state.py`; Modify `tests/web/test_chart_jit.py`.

- [ ] **Step 1: Convert `render_market_weather_svg` to candlesticks** (§C.4, MA 50/200, gridlines via helper, ASCII `trend: {state}` body text). Failing tests:
```python
def test_market_weather_renders_candles_not_line(monkeypatch, ohlc_bars):
    _assert_renders_candles(monkeypatch, charts.render_market_weather_svg,
                            bars=ohlc_bars, trend_template_state="stage_2")
def test_market_weather_trend_badge_ascii_body_text(ohlc_bars):
    svg = charts.render_market_weather_svg(bars=ohlc_bars, trend_template_state="stage_2")
    assert b"trend: stage_2" in svg  # underscore LITERAL in body text (not title) — safe
    svg.decode("ascii")
def test_market_weather_grid_enabled(ohlc_bars):
    # gridlines come from _render_candles_fig (P14.N8 uniform)
    svg = charts.render_market_weather_svg(bars=ohlc_bars, trend_template_state="stage_2")
    assert svg  # grid asserted structurally in the helper test test_render_candles_fig_grid_enabled
```
Implement → PASS.

- [ ] **Step 2: Write the 3-site derivation + fail-soft + uniformity tests** (Expansion #10c; byte-parity-insufficient):
```python
# Sentinel is a NON-LITERAL value so the test cannot pass against the old
# hardcoded "stage_2"/"n/a" (Codex R1 M#2). current_stage only ever returns
# "stage_2"/"undefined" in production, but the MOCK returns this sentinel; the
# test proves the derivation PATH (the renderer received what current_stage
# returned), not a literal match.
_TREND_SENTINEL = "sentinel_stage_xyz"

def test_pipeline_weather_render_computes_real_trend_state(monkeypatch):
    monkeypatch.setattr("swing.pipeline.runner.current_stage", lambda *a, **k: _TREND_SENTINEL)
    captured = capture_render_market_weather_kwargs(monkeypatch)
    run_step_charts(...)
    assert captured["trend_template_state"] == _TREND_SENTINEL  # derivation path, not literal

def test_weather_refresh_handler_computes_real_trend_state(monkeypatch, client):
    monkeypatch.setattr("swing.web.routes.dashboard.current_stage", lambda *a, **k: _TREND_SENTINEL)
    captured = capture_render(monkeypatch)
    client.post("/dashboard/weather-chart/refresh", headers={"HX-Request":"true"})
    assert captured["trend_template_state"] == _TREND_SENTINEL

def test_weather_refresh_failsoft_to_undefined(monkeypatch, caplog, client):
    def boom(*a, **k):
        raise RuntimeError("weather rows missing")
    monkeypatch.setattr("swing.web.routes.dashboard.current_stage", boom)
    captured = capture_render(monkeypatch)
    client.post("/dashboard/weather-chart/refresh", headers={"HX-Request": "true"})
    assert captured["trend_template_state"] == "undefined"   # not "n/a", not a crash
    assert any("current_stage failed" in r.message for r in caplog.records)

def test_pipeline_weather_failsoft_to_undefined_does_not_abort_step(monkeypatch, caplog):
    # Codex R2 M#5 — a pipeline current_stage exception must NOT abort _step_charts;
    # the weather render proceeds with "undefined" + a WARN.
    monkeypatch.setattr("swing.pipeline.runner.current_stage",
                        lambda *a, **k: (_ for _ in ()).throw(RuntimeError("no weather rows")))
    captured = capture_render_market_weather_kwargs(monkeypatch)
    run_step_charts(...)   # completes; does not raise
    assert captured["trend_template_state"] == "undefined"
    assert any("current_stage failed" in r.message.lower() for r in caplog.records)

def test_chart_jit_market_weather_default_is_undefined(monkeypatch, conn, ohlcv_cache):
    # BEHAVIORAL (Codex R1 M#10) — a source-string check is brittle (the Step-5
    # comment would itself contain the word). Spy the renderer and assert the
    # JIT market_weather branch passes "undefined" when no trend_template_state
    # kwarg is supplied (the dead/defensive default).
    captured = {}
    monkeypatch.setattr("swing.web.chart_jit.render_market_weather_svg",
        lambda **kw: captured.update(kw) or b"<svg/>")
    get_or_render_surface(conn=conn, ohlcv_cache=ohlcv_cache, surface="market_weather",
        ticker="SPY", pipeline_run_id=1, data_asof_date="2026-05-29")  # no trend kwarg
    assert captured["trend_template_state"] == "undefined"  # not "stage_2"

def test_weather_three_callsites_identical_kwarg_derivation(monkeypatch):
    # the 2 LIVE compute sites derive trend_template_state from current_stage
    # (not a hardcoded literal). Non-literal sentinel proves the derivation path.
    monkeypatch.setattr("swing.pipeline.runner.current_stage", lambda *a, **k: _TREND_SENTINEL)
    monkeypatch.setattr("swing.web.routes.dashboard.current_stage", lambda *a, **k: _TREND_SENTINEL)
    pipe_kwargs = capture_render_via_runner(monkeypatch)
    refresh_kwargs = capture_render_via_refresh(monkeypatch, client)
    assert pipe_kwargs["trend_template_state"] == _TREND_SENTINEL
    assert refresh_kwargs["trend_template_state"] == _TREND_SENTINEL
```
Run → FAIL.

- [ ] **Step 3: Pipeline site (`runner.py:2883`).** The run asof is the run's persisted `data_asof_date` — use **`lease_data_asof(cfg, lease)`** (`runner.py:1014` — "Read back `data_asof_date` from the `pipeline_runs` row (single source of truth)"; it returns the ISO string), converted to a `date` via `date.fromisoformat(...)`. (Fallback if `lease_data_asof` is unavailable in that scope at implementation: `last_completed_session(run_now)` — the same anchor `_step_charts` uses at `runner.py:534`. Re-grep `_step_charts`'s in-scope vars at implementation per #2 to confirm `lease`/`run_now` availability.) Replace the literal:
```python
try:
    run_asof_date = date.fromisoformat(lease_data_asof(cfg, lease))
    weather_state = current_stage(conn, benchmark_ticker, run_asof_date)
except Exception as exc:  # noqa: BLE001 - fail-soft
    log.warning("market_weather current_stage failed for %s: %s", benchmark_ticker, exc)
    weather_state = "undefined"
svg_bytes = render_market_weather_svg(bars=bars, trend_template_state=weather_state)
```
Import `current_stage` from `swing.patterns.foundation` at the runner module level (verify it is import-safe in the pipeline context — it reads `candidates`/`candidate_criteria`/`evaluation_runs` rows only, no Schwab/yfinance; L6 preserved).

- [ ] **Step 4: Refresh handler (`routes/dashboard.py:117`).** Replace `"n/a"`:
```python
try:
    weather_state = current_stage(conn, benchmark,
                                  last_completed_session(datetime.now()).date())
except Exception as exc:  # noqa: BLE001
    logger.warning("weather refresh current_stage failed for %s: %s", benchmark, exc)
    weather_state = "undefined"
svg_bytes = render_market_weather_svg(bars=bars, trend_template_state=weather_state)
```
(`last_completed_session(...)` already used at line 127 for `data_asof_date` — reuse the same anchor. **Verify its return type at implementation (#2, Codex R1 m#2):** it is used at `dashboard.py:127` as `last_completed_session(datetime.now()).isoformat()`, so it returns a `date`-or-`datetime`. `current_stage` needs a `date` — call `.date()` only if it returns a `datetime`; pass it directly if it already returns a `date`. Confirm before locking the `.date()` suffix.)

- [ ] **Step 5: JIT default (`chart_jit.py:158`).** Change the `market_weather` branch default from the old fake stage literal to the honest `"undefined"`. Add a comment noting no production caller routes `market_weather` through the JIT today (dead/defensive default; a future SB4 caller MUST compute+pass real state). **Keep the word `stage_2` out of the comment** (the behavioral test in Step 2 is the gate, but avoid the literal to prevent any future source-string confusion). Run Step-2 tests → PASS.

- [ ] **Step 6: `ruff check swing/`; `python -m pytest tests/web/test_weather_trend_state.py tests/web/test_chart_jit.py -q`; commit.** Verify `%(trailers)` `[]`.

**Acceptance:** weather renders candlesticks + 50/200 MAs + gridlines + a REAL trend badge; pipeline + refresh handler derive `trend_template_state` from `current_stage` (sentinel-reaches-renderer test); fail-soft to `"undefined"` on any error; JIT default is the honest `"undefined"`; L6 preserved (no Schwab). Locks: P14.N8, L6, L7, Expansion #10c, byte-parity insufficiency, session-anchor read/write.

---

### Task T-3.5: P14.N1 thumbnail substrate proof + S6 annotation reposition

**Files:** Modify `swing/web/charts.py` (`_annotate_*` family); `tests/web/test_charts.py`; `tests/web/test_chart_jit.py`.

- [ ] **Step 1: Write failing S6 placement tests:**
```python
def test_theme2_annotation_text_anchored_upper_right_not_upper_left():
    # _annotate_flat_base (and family) write at x>=0.9, ha="right" (was 0.02 left)
    coords = capture_annotate_text_coords(pattern="flat_base")
    assert all(x >= 0.9 for (x, y, ha) in coords)
    assert all(ha == "right" for (x, y, ha) in coords)
def test_theme2_flat_base_duration_text_ascii(...): ...
def test_theme2_annotation_stack_descends_from_092(...):
    # multi-line vcp stack: y values 0.92, 0.87, 0.82, ... descending
    ...
```
Run → FAIL.

- [ ] **Step 2: Reposition the `_annotate_*` family** per §C.5a (right-edge `(0.98, 0.92 - i*0.05)`, `ha="right"`; legend stays upper-left). Apply uniformly to `_annotate_vcp`, `_annotate_flat_base`, `_annotate_cup_with_handle`, `_annotate_high_tight_flag`, `_annotate_double_bottom_w`. Run → PASS.

- [ ] **Step 3: Write failing P14.N1 substrate-proof tests:**
```python
def test_jit_renders_watchlist_thumbnail_for_non_watchlist_ticker(conn, ohlcv_cache):
    # a ticker NOT in the watchlist still renders + caches a watchlist_row thumbnail
    out = get_or_render_surface(conn=conn, ohlcv_cache=ohlcv_cache,
        surface="watchlist_row", ticker="ZZZZ", pipeline_run_id=RID,
        data_asof_date=ASOF, ma_lines=_WATCHLIST_THUMBNAIL_MA_LINES)
    assert out is not None
    # second call returns the cached row (write-through), byte-identical
def test_open_position_and_hyprec_row_vms_expose_thumbnail_binding(dashboard_vm):
    # Codex R1 m#9 — the row VMs can resolve (ticker, pipeline_run_id) the
    # substrate needs; SB4 wiring unblocked. NO row TEMPLATE change here.
    for row in dashboard_vm.open_positions:
        assert getattr(row, "ticker", None) is not None
    # the run binding the thumbnail needs is resolvable from the VM's run context
    assert dashboard_vm.pipeline_run_id is not None or dashboard_vm.binding is not None
```
Run → FAIL.

> If the row VM already exposes ticker + a resolvable run binding (likely — the dashboard VM holds `pipeline_run_id`), this test PASSES with no production change and documents the contract. If a field is genuinely missing, add ONLY the minimal VM field (no template change) to unblock SB4.

- [ ] **Step 4: Implement the substrate proof** (the renderer + JIT path already exist post-T-3.1 rename; this confirms reuse + adds the VM-binding resolution if a field is missing). Run → PASS.

- [ ] **Step 5: `ruff check swing/`; `python -m pytest tests/web/test_charts.py tests/web/test_chart_jit.py -q`; commit.** Verify `%(trailers)` `[]`.

**Acceptance:** the `_annotate_*` family renders at the upper-right (no upper-left legend overlap); a non-watchlist ticker renders+caches a `watchlist_row` thumbnail via the JIT; row VMs expose the thumbnail binding (substrate-only; no row templates). Locks: S6, P14.N1 (OQ-4 substrate-only), L4.

---

### Task T-3.6: Closer — pyproject web extra + import smoke + full suite + L2 grep + visual-gate runbook

**Files:** Modify `pyproject.toml`; Create `tests/web/test_web_charts_import_smoke.py`; verify `tests/integration/test_l2_lock_source_grep.py`.

- [ ] **Step 1: Add `"mplfinance>=0.12"` to the `web` extra** in `pyproject.toml` (it is imported at `swing/web/charts.py` module load post-T-3.2, so every `swing web` run profile needs it). Audit all supported install profiles (`[web]`, `[dev,web]`, any requirements/lock/container path) and add it wherever `swing web` launches.

- [ ] **Step 2: Write + pass the packaging import smoke test + the metadata test** (Codex R2 m#1 — a missing-mplfinance import breaks EVERY page importing `swing.web.charts`; Codex R2 M#6 — the import smoke can pass in a dev env that already has mplfinance via `dev`/`charts`, so ALSO assert `pyproject` `[web]` declares it):
```python
def test_web_charts_imports_cleanly():
    import importlib
    importlib.import_module("swing.web.charts")  # mplfinance present
def test_web_app_imports_cleanly():
    import importlib
    importlib.import_module("swing.web.app")
def test_web_extra_declares_mplfinance():
    # Codex R2 M#6 — the actual packaging guarantee, not just "it imports here".
    import tomllib, pathlib
    root = pathlib.Path(__file__).resolve().parents[2]
    data = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))
    web = data["project"]["optional-dependencies"]["web"]
    assert any(dep.replace(" ", "").startswith("mplfinance>=") for dep in web), web
```
> Also check any requirements/lock/container manifest the repo uses at implementation (#2) — add `mplfinance>=0.12` wherever `swing web` can be launched.

- [ ] **Step 3: Verify the L2 LOCK source-grep test green** (`tests/integration/test_l2_lock_source_grep.py` greps `schwabdev.Client.` via multiset comparison — confirm no new call site). Run: `python -m pytest tests/integration/test_l2_lock_source_grep.py -v` → PASS.

- [ ] **Step 4: Full fast suite + ruff.** `python -m pytest -m "not slow" -q` (0 failures); `ruff check swing/` (0 E501). 0 slow tests added (charts render from fixture bars).

- [ ] **Step 5: Produce the per-surface visual-gate artifacts + commands** (§I.2) — write the repro script + the SVG/PNG artifacts to `exports/diagnostics/phase14-sb3/` and record the exact regen commands + the per-surface acceptance checklist in the executing-plans return report. Commit. Verify `%(trailers)` `[]`.

**Acceptance:** mplfinance in every `swing web` profile; import smoke green; L2 grep green; full fast suite + ruff clean; visual-gate artifacts + commands recorded for the operator gate owner. Locks: L2, L4, L6.

---

## §H Test surface (sum-check)

| Task | Tests (indicative; names finalized at impl) | Count |
|---|---|---|
| T-3.1 | rename-renames-rows, FK-survival+`foreign_key_check`, schema-parity-normalized-sql, backup-gate-strict-22, backup-gate-skips-pre-v22, migrate-twice-no-op, rollback-through-runner, fk-restore-success, fk-restore-rollback, validator-rejects-hyprec, ticker_detail-importable, L5-no-orphan-grep | ~12-14 |
| T-3.2 | ma-colors-cover+unique, normalize(sort/dedup/tznaive/multiindex), normalize-missing-col, normalize-titlecase-collision, x-for-date-int, candles-returns-axes, strips-vol-yticks, grid-enabled, volume-false-none, ticker_detail-neutral-title, ticker_detail-window-band, ticker_detail-cache-single-row, theme2-candles-volume-false, theme2-window-band, integer-x-extent, bars-fixture-precondition, ASCII×N | ~16-20 |
| T-3.3 | bulz-target-from-R, bulz-target-none-absent, bulz-target-none-nonpos-rps, bulz-entry-avg, bulz-entry-fallback, position-candles+markers, stop-axhline, risk-zone-bounds, reward-zone-when-target, risk-only-no-target, skip-invalid-shape+warn, zone-legend-ascii | ~12 |
| T-3.4 | weather-candles-50-200, trend-badge-ascii, grid-enabled, pipeline-derives-real, refresh-derives-real, failsoft-undefined, jit-default-undefined, three-callsites-uniform | ~8 |
| T-3.5 | s6-upper-right, s6-ascii, s6-stack-descends, jit-thumbnail-non-watchlist, row-vm-thumbnail-binding | ~5 |
| T-3.6 | web-charts-import-smoke, web-app-import-smoke, l2-grep-verified | ~3 |
| **Sum** | | **~56-62 new/updated** |

Within the spec §10 indicative envelope (~40-80). **0 slow tests** (all render from fixture bars). Trust pytest's own count (gotcha #1) — this table is a planning estimate, not an assertion target.

**Mandatory discriminating tests** (must exist): the renderer-kwargs uniformity / cache-collision tests (ticker_detail single-row + weather 2-live-site, Expansion #10c); the atomic-rename no-orphan grep (L5); the **candlestick-render-vs-line `mpf.plot(type="candle")` spy per converted surface** (Codex R1 M#6, via `_assert_renders_candles`); the BULZ target-only-if-present branch + zone-bounds-distinguish (verify-arithmetic); the schema-parity normalized-SQL + FK-restore success+rollback (Codex R1 M#2/M#3/M#4/R2 M#1).

> **SVG text-assertion note (Codex R1 m#1):** matplotlib can render text as PATHS depending on `svg.fonttype`, which would defeat the `b"trend: stage_2" in svg` / legend byte checks. The existing `tests/web/test_charts.py` already asserts strings in serialized SVG (so the current renderers emit text-as-text), but executing-plans MUST confirm the SVG path keeps text-as-text (e.g. `plt.rcParams["svg.fonttype"] = "none"` or the renderers' existing config) — OR assert on the matplotlib text artists BEFORE serialization. Pin at implementation.

### §H.CANNOT — what tests do NOT certify (L4, operator-witnessed gate required)
That the SVG VISUALLY renders candlesticks (not lines); that BULZ zones are legible + correctly colored; that the weather chart shows the badge + gridlines; that the S6 text no longer overlaps the legend; that V2.G1's "not rendering in browser" sub-symptom is resolved. These are §I.

---

## §I Per-renderer operator-witnessed visual-gate runbook (BINDING — Sec 9.1 Q6, L4)

> Byte/string tests are INSUFFICIENT. The RENDERED chart is the binding correctness check. Browser-MCP is unavailable on this host (prior sub-bundles' fallback: operator-driven browser + orchestrator DB-side probes; OR orchestrator renders to PNG and reads it, as at SB2 S6). The operator is the named gate owner; merge is BLOCKED until each row is checked.

### §I.1 The ladder
- **S1** `python -m pytest -m "not slow" -q` green + `ruff check swing/` 0 E501.
- **S2** v23 applied on a real v22 DB: `schema_version == 23`; `chart_renders` rows migrated `hyprec_detail`→`ticker_detail`; backup file `swing-pre-phase14-sb3-migration-<ISO>.db` written; `PRAGMA foreign_key_check` clean.
- **S3** (browser) `ticker_detail` (hyp-rec expand + watchlist expand): candlesticks render; title reads `{ticker} | last N bars` (NOT "hyp-rec detail" on watchlist); 10/20/50/150/200 MAs present + distinguishable (Okabe-Ito palette).
- **S4** (browser) `position_detail` (BULZ): candlesticks + risk (entry→stop) + reward (entry→target) shaded zones + an ASCII legend describing them.
- **S5** (browser) `market_weather` (dashboard + after "Refresh weather chart"): candlesticks + REAL trend badge (`trend: stage_2`/`trend: undefined`, NOT `n/a`) + gridlines; pre/post-refresh visually equivalent.
- **S6** (browser) `theme2_annotated` flat_base (a `/patterns/{id}/review` flat_base case): duration text upper-right, no legend overlap; worst-case (vcp full contraction list + 5 MAs) no overrun.
- **S7** L2 LOCK source-grep test green; L5 grep gate green — zero `hyprec_detail`/`render_hyprec_detail_svg`/`hyprec-detail-chart`/`_HYPREC_DETAIL_SIZE_PX` in the **runtime-forbidden paths** (`swing/**` except the `0020`+`0023` migration SQL; `swing/web/templates/**`). The token MAY still appear (by design) in the `0020`/`0023` migration SQL and in migration/validator negative-assertion tests per the §E.3 two-tier allowlist — these are NOT failures.

### §I.2 Operationalizing (Codex R1 M#9 — artifacts + commands + ownership)
- **Artifacts:** rendered SVG (+ PNG for diffing) to `exports/diagnostics/phase14-sb3/<surface>-<ticker>.svg` for each changed surface (`ticker_detail`, `position_detail`, `market_weather`, `theme2_annotated` per pattern class, `watchlist_row` unchanged-baseline).
- **Command:** a documented repro one-liner/script calling each renderer on a fixed fixture ticker/bars — recorded in the executing-plans return report so the operator regenerates deterministically.
- **Route equivalents:** `/dashboard`, hyp-rec expand, watchlist expand, `POST /dashboard/weather-chart/refresh`, `/patterns/{id}/review` (flat_base).
- **Checklist + ownership:** the §I.1 ladder recorded in the executing-plans return report / PR with the operator as the named gate owner; merge BLOCKED until each row checked.
- **Baseline storage:** pre-change bytes are NOT a regression baseline (the change is intentional) — the artifacts are the post-change reference the operator signs off on.

---

## §J Codex single-chain placement (OQ-chain LOCK)

- **SINGLE Codex chain** at the END of writing-plans (this plan) AND at the end of executing-plans — operator-LOCKed (§1.3 + Sec 9.1 Q7), NOT orchestrator discretion. 2-4 round target.
- **Transport:** the Codex MCP times out at 1s on this host (FB-N1; operator investigating separately — do NOT attempt to fix it). Backstop = `codex exec` CLI + `resume --last` thread continuity, artifacts pasted INLINE (the `-s read-only` sandbox cannot spawn shells to read files on this host).
- **Watch items for the chain** (brief §5): signature verify (#2); v23 #11-paired all-layers + STRICT `pre_version==22` + rollback-through-runner; atomic-rename no-orphan (L5); renderer-kwargs uniformity (Expansion #10c) cache-collision; matplotlib mathtext + per-renderer visual gate; mplfinance deterministic+ASCII + thumbnail stays line; BULZ target-only-if-present branch; L2 grep continues passing + ASCII + Co-Authored-By/trailer-parse suppression.

---

## §K Schema impact (v23)

- **Migration:** `0023_phase14_sb3_chart_surface_rename.sql` — single-table rebuild of `chart_renders`; no other tables touched.
- **Version:** 22 → 23. `EXPECTED_SCHEMA_VERSION = 23`.
- **Backup gate:** `_phase14_sb3_backup_gate` STRICT `current_version == 22 AND target_version >= 23`.
- **Data migration:** in-migration `INSERT…SELECT` `CASE`-rename of existing rows (OQ-7 — pure value rename, atomic with the schema change; preferred over a separate backfill).
- **FK impact:** `pattern_detection_events.chart_render_id` (`ON DELETE SET NULL`, v22) preserved via id-preserving copy + FK-off-during-rebuild (`_apply_migration` sets `PRAGMA foreign_keys=OFF` for the script, restored in `finally` on BOTH success + rollback — verified `db.py:183-226`).
- **Indexes:** 3 partial unique indexes recreated verbatim (no value change — §A.4 correction 2). Cross-column CHECK recreated verbatim.
- **No new columns/tables; no enum widening** (same-cardinality value rename). `pattern_class` CHECK + all other constraints unchanged.
- **Forward-compat:** v22 temporal-log tables UNTOUCHED (SB2 substrate LOCKED).
- **Schema v22 stays LOCKED at writing-plans** — the v23 DDL is DESIGNED here, APPLIED at executing-plans.

---

## §L Test fixture strategy (+ visual-gate fixtures)

### L.1 Fixtures
- **OHLC bars fixture** — DatetimeIndex + Open/High/Low/Close/Volume (mpf precondition); reuse/extend `tests/web/test_charts.py` synthetic bars; add the §C.1b normalization-precondition tests. **Build malformed variants** (unsorted, dup-timestamp, tz-aware, MultiIndex, lowercase, title-case-collision, missing-column) for the `_normalize_ohlc_for_mpf` tests.
- **v23 migration fixtures:** a v22 DB with `chart_renders` rows across all 5 surfaces (incl. a `hyprec_detail` row with a known id) + a `pattern_detection_events` row referencing one (FK-survival). **Schema-version-aware INSERT** (gotcha #11): build the v22 fixture by running `run_migrations` to v22 then inserting, OR detect via `PRAGMA table_info` — do NOT hand-write the v23-shape INSERT into a v22 fixture.
- **Cache-collision fixture:** two callers of `ticker_detail` (hyp-rec + watchlist-expand) with identical bars → one cached row (L3).
- **BULZ zone fixture:** a `Trade` (`entry_price`, `initial_stop`, `planned_target_R`) + entry/exit `Fill`s with known values → assert `axhspan` bounds (distinguishes post-fix from swapped/absent).
- **trend-state derivation fixture:** mock `current_stage` → a sentinel; assert the sentinel reaches the renderer at each production compute site.

### L.2 Concrete fixture builders (referenced by §G tests)

```python
# tests/web/conftest.py (or local to test_charts.py)
import pandas as pd
from datetime import date

@pytest.fixture
def ohlc_bars():
    """120 deterministic daily OHLCV bars, DatetimeIndex, no network."""
    idx = pd.bdate_range("2026-01-02", periods=120)
    base = pd.Series(range(100, 220), index=idx, dtype=float)
    return pd.DataFrame({
        "Open": base, "High": base + 2.0, "Low": base - 2.0,
        "Close": base + 0.5, "Volume": [1_000_000] * 120,
    }, index=idx)

@pytest.fixture
def known_bars():
    """Short fixed window where index[3] == 2026-05-29 (for _x_for_date pin)."""
    idx = pd.to_datetime(["2026-05-26","2026-05-27","2026-05-28","2026-05-29","2026-05-30"])
    return pd.DataFrame({"Open":[1,2,3,4,5],"High":[2,3,4,5,6],"Low":[0,1,2,3,4],
                         "Close":[1.5,2.5,3.5,4.5,5.5],"Volume":[1e6]*5}, index=idx)
```

```python
# tests/data/conftest.py — migration fixtures (schema-version-aware, gotcha #11)
import sqlite3
import swing.data.db as db

def _make_file_v22_db(tmp_path):
    """A file-backed DB migrated to v22 with one hyprec_detail chart_renders row."""
    p = tmp_path / "swing.db"
    conn = sqlite3.connect(p)
    db.run_migrations_to_version(conn, 22)   # or run_migrations then assert ==22 if helper absent
    conn.execute(
        "INSERT INTO chart_renders (ticker, surface, pipeline_run_id, pattern_class, "
        "chart_svg_bytes, source_data_hash, rendered_at, data_asof_date) "
        "VALUES ('AAPL','hyprec_detail',1,NULL,?,?,?,?)",
        (b"<svg/>", "h", "2026-05-29T00:00:00Z", "2026-05-29"),
    )
    conn.commit()
    return conn, p

def _make_file_v21_db(tmp_path):
    p = tmp_path / "swing.db"
    conn = sqlite3.connect(p)
    db.run_migrations_to_version(conn, 21)
    return conn, p

# Codex R1 M#3/M#4 — inject a failure WITHIN the 0023 script (mid-executescript,
# BEFORE the final UPDATE/COMMIT) so the runner's except->rollback path fires.
# A valid DDL prefix followed by a deliberately-invalid statement.
_BROKEN_0023_BEFORE_COMMIT = """BEGIN;
CREATE TABLE chart_renders_new (id INTEGER PRIMARY KEY);
THIS IS NOT VALID SQL BEFORE COMMIT;
UPDATE schema_version SET version = 23;
COMMIT;
"""

def _patch_0023_sql(monkeypatch, broken_sql):
    """Make the runner read broken SQL for the 0023 file only (real read_text
    for every other migration). _apply_migration calls sql_path.read_text(...)."""
    import pathlib
    real_read = pathlib.Path.read_text
    def fake_read(self, *a, **k):
        if self.name.startswith("0023_"):
            return broken_sql
        return real_read(self, *a, **k)
    monkeypatch.setattr(pathlib.Path, "read_text", fake_read)
```
> If `run_migrations_to_version` does not exist, the fixture runs `run_migrations` on a DB pre-seeded to the target version-1 schema, OR migrates fully then is rejected for the gate tests — pin the exact helper at implementation (#2). The `v22_db`/`v23_db` fixtures wrap the file builders; `make_trade`/`make_fill` are thin factory helpers over the `Trade`/`Fill` dataclasses (`swing/data/models.py`) with the BULZ-relevant fields (`entry_price`, `initial_stop`, `current_stop`, `planned_target_R`; `action`, `price`, `quantity`).

### L.3 Visual-gate fixtures
- A fixed fixture ticker + deterministic bars (no network) the repro script (§I.2) renders each surface from. Stored under `tests/web/fixtures/` or generated in-test; the produced SVG/PNG go to `exports/diagnostics/phase14-sb3/`.

---

## §M Forward-binding lessons (for executing-plans)

1. **Re-grep all signatures at executing time (#2)** — the renderer names (post-T-3.1 they are `render_ticker_detail_svg` + `_TICKER_DETAIL_SIZE_PX`), `current_stage(conn, ticker, asof_date)` (`asof_date` is a `date`), the run's last-completed-session `date` variable in `_step_charts`, `Trade.planned_target_R`/`entry_price`/`initial_stop`, `Fill.action`/`price`/`quantity`. Line numbers WILL shift as edits land.
2. **Derive v23 DDL from a migrated-to-v22 fixture's `sqlite_schema`** (T-3.1 Step 1) — do NOT hand-transcribe from the `0020` excerpt.
3. **T-3.2-step-0 (browser-embedding diagnosis) runs BEFORE the candlestick conversion** — a viewBox/CSS clipping bug would otherwise survive the mpf swap (and mpf+`bbox_inches="tight"` CHANGES the SVG `width`/`height`/`viewBox`, so capture per-surface and reconcile with the template/CSS).
4. **The MA palette (`_MA_COLORS`) + the S6 reserved-region map are PINNED here** (§C.1, §C.5a) — visual-gate-critical; do not defer.
5. **The visual gate is BINDING** (§I) — enumerate per-surface SVG/PNG artifacts + exact regen commands in the executing-plans return report; the operator is the named gate owner.
6. **mplfinance must be in EVERY `swing web` run profile** + the import smoke test (T-3.6) — a missing dep breaks every page importing `swing.web.charts`.
7. **No live `market_weather` JIT caller exists today** (§A.4 correction 5) — the `chart_jit` default is a fail-soft `"undefined"`, not a live derivation path; any future SB4 JIT `market_weather` caller MUST compute+pass real state.
8. **The `current_stage` caller cited in the spec (`review_form.py:454`) does not exist** — use the detector pattern (`vcp.py:500`) as the reference; `current_stage` returns ONLY `"stage_2"`/`"undefined"` in V1.

---

## §N Self-review checklist (run by the plan author before commit)

- [ ] **Spec coverage:** every spec §1-§15 requirement maps to a task — §4 candlesticks→T-3.2/3/4/5; §5 v23 rename→T-3.1; §6 P14.N1→T-3.5; §7 BULZ→T-3.3; §8 weather→T-3.4; §9 S6→T-3.5; §10 decomposition→§G; §11 tests/visual gate→§H/§I; §12 schema→§K; §13 V1 simplifications→§D; §15 disciplines→§F.
- [ ] **Placeholder scan:** no "TBD"/"handle edge cases"/"similar to Task N"/"write tests for the above" without code.
- [ ] **Type consistency:** `render_ticker_detail_svg`, `_TICKER_DETAIL_SIZE_PX`, `_MA_COLORS`, `_normalize_ohlc_for_mpf`, `OhlcNormalizationError`, `_x_for_date(price_ax, df, target_date)`, `_render_candles_fig`, `_bulz_target_price(trade)`, `current_stage(conn, ticker, asof_date)`, `_phase14_sb3_backup_gate`, `ticker_detail_chart_svg_bytes` — used identically across all tasks. (No `_bulz_entry_price` — V1 zone entry is `trade.entry_price`.)
- [ ] **All 11 §1.3 OQ dispositions honored** (§E.3 table).
- [ ] **Sec 9.1 + L1-L7 reverified** (§E.1/E.2).
- [ ] **Schema v22 LOCKED at writing-plans** (v23 DESIGNED, applied at executing-plans).
- [ ] **ZERO Co-Authored-By; final `-m` paragraph plain prose; `%(trailers)` `[]`.**

---

*End of plan. Phase 14 Sub-bundle 3 — chart-surface uniformity: a shared mplfinance candlestick helper across 4 detail renderers; v23 atomic `hyprec_detail`→`ticker_detail` rename (id-preserving table rebuild + STRICT `pre_version==22` backup gate); BULZ risk/reward zones (target derived from `planned_target_R`); real `current_stage` weather trend-state at 3 sites; S6 annotation reposition; P14.N1 thumbnail substrate. The rendered chart is the BINDING operator-witnessed visual gate (matplotlib; byte/string tests insufficient). SINGLE Codex chain. Output: a per-task plan the executing-plans phase dispatches directly.*
