# Phase 14 Sub-bundle 3 -- Chart-Surface Uniformity -- Design Spec

**Status:** Brainstorming design spec (draft for Codex adversarial review).
**Date:** 2026-05-29.
**Phase:** 14 Sub-bundle 3 (chart-surface uniformity); SERIAL after Sub-bundle 2 (temporal log v22) SHIPPED at `27f8007`.
**Branch:** `phase14-sub-bundle-3-chart-surface-uniformity-brainstorming` (cut from main HEAD `fd59ece`).
**Brief:** `docs/phase14-sub-bundle-3-chart-surface-uniformity-brainstorming-dispatch-brief.md`.
**Scope items:** V2.G1 + V2.G2 (`hyprec_detail`->`ticker_detail` v23 rename) + P14.N1 + P14.N2 + P14.N4 + P14.N8 + S6 cosmetic.

> This is a **docs-only brainstorming artifact**. No `swing/` code is modified in this phase. Schema v22 stays LOCKED; v23 is DESIGNED here and APPLIED only at executing-plans. The rendered chart is the BINDING operator-witnessed visual gate (CLAUDE.md matplotlib mathtext gotcha + L4 LOCK); byte/string-equality tests are explicitly INSUFFICIENT for chart-render correctness.

---

## §1 Architecture overview

The five SVG renderers in `swing/web/charts.py` have drifted across three axes: (a) **chart type** -- all five currently plot a close-LINE via `ax.plot(close.values)`, none render OHLC candlesticks, contradicting operator expectation (V2.G1 + P14.N2); (b) **annotation placement** -- the `flat_base` duration text collides with the legend (S6); and (c) **per-call-site kwargs** -- `render_market_weather_svg` is invoked from three call sites with a divergent `trend_template_state` literal (P14.N8). One surface additionally carries a semantic-leakage name (`hyprec_detail`) that surfaces verbatim in operator-visible chart titles (V2.G2), requiring a v23 schema rename.

This sub-bundle is a **renderer-uniformity pass** plus a **v23 surface-enum rename** plus three targeted fixes. The unifying mechanism is to **adopt the codebase's existing mplfinance candlestick pattern** -- already implemented and battle-tested at `swing/rendering/charts.py:render_chart` (the pipeline-time PNG renderer) -- for the detail surfaces, factored into a shared helper so the candlestick + MA + volume + gridline conventions cannot drift again.

**Design principles:**
- **Reuse, do not reinvent.** `swing/rendering/charts.py` already renders mplfinance candlesticks with `mav` SMA overlays, a volume panel, and `hlines`/`vlines`. The web SVG renderers mirror that call pattern via a new shared helper rather than hand-rolling candle geometry.
- **One shared helper for the drift-prone conventions.** Candle rendering, MA-line set, volume-panel y-tick stripping, and gridlines move into `_render_candles_fig(...)`; per-surface renderers call it then overlay surface-specific annotations.
- **Atomic rename (#11).** The `hyprec_detail`->`ticker_detail` rename lands schema CHECK + Python constants + dataclass validator surface + read-path mapper + renderer function name + routes + view-models + templates + tests in ONE task, with zero residual `hyprec_detail` tokens (L5).
- **Visual gate is binding (L4).** Every changed renderer gets an operator-witnessed browser/PNG gate. Tests defend wiring + signatures + ASCII discipline + cache-key shape; they do NOT certify visual correctness.

### §1.1 The 5 renderers (real signatures, verified at `fd59ece`)

| Renderer | Size (px) | Current chart type | Candlestick adopter (V1)? |
|---|---|---|---|
| `render_watchlist_thumbnail_svg(*, ticker, bars, ma_lines)` | 200x100 | close-line + vol bars | **No** (illegible at thumbnail scale) |
| `render_hyprec_detail_svg(*, ticker, bars, pattern_evaluation=None)` -> RENAME `render_ticker_detail_svg` | 800x500 | close-line + MA + vol | **Yes** |
| `render_position_detail_svg(*, ticker, bars, trade, fills, current_stop)` | 800x500 | close-line + MA50 + fill markers + stop hline | **Yes** |
| `render_market_weather_svg(*, bars, trend_template_state)` | 400x150 | close-line + MA50/200 + vol + trend badge | **Yes** |
| `render_theme2_annotated_svg(*, ticker, bars, pattern_evaluation, exemplar_thumbnails=None)` | 800x600 | close-line + MA + per-pattern annotations | **Yes** |

Shared helpers (verified): `_close_series`, `_volume_series`, `_figsize_inches`, `_svg_bytes_from_fig`, `_assert_ascii_only`, `_assert_ticker_safe`, `_assert_title_no_math`, `_set_suptitle_no_math`, and the `_annotate_{vcp,flat_base,cup_with_handle,high_tight_flag,double_bottom_w}` family + `_ANNOTATORS` dispatch dict + `_AnnotationContext`.

### §1.2 Brief-vs-production corrections (Expansion #2 / #4 -- verified before drafting)

The brief and phase3e-todo carry three claims that the production read corrects. The spec records these so writing-plans does not re-derive a wrong premise:

1. **"only open-positions table shows candlesticks" (V2.G1 framing) is inaccurate.** `render_position_detail_svg` plots `ax.plot(range(len(close)), close.values)` -- a close-LINE, identical in *type* to the other renderers. NONE of the five draw OHLC candles today. V2.G1 + P14.N2 are therefore **additive** (introduce candlesticks), not a *divergence repair*. The operator's "the only candlestick graphs I see are in open positions" most plausibly reflects (a) loose terminology for "a chart that renders" vs the hyp-rec/watchlist surfaces *failing to render visibly* in the browser, and/or (b) a template/CSS embedding gap. The candlestick adoption closes the type expectation; the "not rendering at all" sub-symptom is carried as an explicit writing-plans investigation item (§4.5) since it is browser-only.
2. **The 3 partial unique indexes do NOT reference the literal `'hyprec_detail'`.** They reference `surface != 'theme2_annotated'`, `surface = 'position_detail'`, and `surface = 'theme2_annotated'` (verified at `0020_*.sql:208-221`). The ONLY literal `hyprec_detail` in SQL is the `surface` CHECK enum (`0020_*.sql:180`). The v23 rebuild still recreates the indexes (dropping the table drops them), but no index *value* edit is needed -- the brief's "partial unique indexes referencing hyprec_detail" is imprecise.
3. **"gridlines" is not a renderer kwarg.** `render_market_weather_svg` never calls `ax.grid()`; there is no per-call-site gridline difference today. P14.N8's "gridlines disappeared post-refresh" is best explained by the operator comparing a pre-existing pipeline-time chart (which historically may have rendered with mpl default gridlines under a different style) against the current line-chart render. "Restore gridlines" is implemented as adding `ax.grid()` to the renderer **uniformly** (it then appears on every call site), not as threading a kwarg.

Additionally: **the pipeline-time weather render itself hardcodes `trend_template_state="stage_2"`** (`runner.py:2883`), as does the JIT default (`chart_jit.py:158`). So "match the pipeline-time render" (L7) taken literally means copying a hardcoded `"stage_2"`. Per operator decision (§2.2 OD-3) the spec instead computes the REAL state at all three sites.

---

## §2 Pre-locked operator decisions

### §2.1 Sec 9.1 commissioning LOCKs (binding for all Phase 14 sub-bundles)
- **Q1** sequencing: data-wiring (SHIPPED) -> temporal log (SHIPPED) -> **charts (THIS)** -> review+journal -> metrics.
- **Q2** execution = SERIAL.
- **Q4** V2.G2 rename ships in THIS sub-bundle as a **v23 migration** with data-migration discipline for existing `chart_renders` rows.
- **Q5** matplotlib SVG only; no JS charting library. (mplfinance is a matplotlib/Python wrapper -- COMPATIBLE; see §4.1.)
- **Q6** close-out = operator browser-witnessed verification at merge (the rendered chart is the binding gate).
- **Q7** Codex chain count = SINGLE chain for THIS brainstorming (pure UX/chart; gotcha #36 caveat). Reconsider at writing-plans if the v23 migration surfaces substrate risk.

### §2.2 Operator decisions captured at this brainstorming (2026-05-29)

| # | Decision | Locked value |
|---|---|---|
| **OD-1** | Candlestick implementation | **Adopt mplfinance** (the existing `swing/rendering/charts.py` pattern). NOT hand-rolled. |
| **OD-2** | Candlestick surface scope (V1) | **Detail surfaces only**: `ticker_detail`, `position_detail`, `theme2_annotated`, `market_weather`. Thumbnails (`watchlist_row` + future P14.N1) stay close-line (illegible at 200x100). |
| **OD-3** | Weather `trend_template_state` source | **Compute the REAL state via `current_stage(conn, benchmark, asof)` at all 3 call sites** (pipeline, JIT, refresh). Closes the V2-banked `"stage_2"` literal simplification (T2.SB6c return report §4.1 row 5). |
| **OD-4** | Rename blast radius | **Full rename**: surface enum value + `render_hyprec_detail_svg`->`render_ticker_detail_svg` + VM field `hyprec_detail_chart_svg_bytes`->`ticker_detail_chart_svg_bytes` + template var + `.hyprec-detail-chart` CSS class + all comments. Zero residual `hyprec_detail` tokens (L5). |

### §2.3 Sub-bundle 3 phase LOCKs (this brief, restated)
- **L1** Scope = V2.G1 + V2.G2 + P14.N1 + P14.N2 + P14.N4 + P14.N8 + S6 ONLY. No review+journal / metrics / Phase 15+.
- **L2** v23 migration: gotcha #11 paired discipline (CHECK enum + Python constants + dataclass validator surface + read-path `_row_to_*` mapper, ALL in one task) + gotcha #9 explicit BEGIN/COMMIT/ROLLBACK + backup-gate STRICT `pre_version == 22`. Migrate the CHECK enum + recreate partial indexes + `UPDATE` existing rows.
- **L3** Renderer-kwargs uniformity LOCK (Expansion #10c): multi-call-site renderers pass identical kwargs; cache-collision discriminating tests at reused surfaces.
- **L4** Matplotlib visual-gate discipline: byte/format/string tests INSUFFICIENT; operator-witnessed visual gate per changed renderer; ASCII-only annotation text.
- **L5** Backwards-compat: zero orphaned `hyprec_detail` references after V2.G2.
- **L6** L2 LOCK preserved: zero new `schwabdev.Client.*` call sites; source-grep test still passes.
- **L7** P14.N8 is a pre-existing Phase 13 regression (revealed, not introduced, by Sub-bundle 1's V2.G4 fix); fix by matching the canonical render, NOT by suppressing it. (Per OD-3, "canonical" = the REAL `current_stage` value.)

---

## §3 Module touch list

**Production code (modified at executing-plans; LISTED here, not touched in brainstorming):**

| File | Change |
|---|---|
| `swing/web/charts.py` | NEW `_render_candles_fig` helper; convert 4 detail renderers to candlesticks; rename `render_hyprec_detail_svg`->`render_ticker_detail_svg`; caller-context title; BULZ zones in `render_position_detail_svg`; `ax.grid()` uniform; S6 annotation reposition; uniform MA set. |
| `swing/data/models.py` | `_CHART_SURFACE_VALUES` tuple value `hyprec_detail`->`ticker_detail` (the `ChartRender.__post_init__` validator reads this tuple -- gotcha #11 dataclass-validator surface). |
| `swing/data/migrations/0023_phase14_sb3_chart_surface_rename.sql` | NEW v23 migration: table-rebuild `chart_renders` with new CHECK; `INSERT...SELECT` with CASE rename preserving `id`; recreate 3 partial indexes + cross-column CHECK; `UPDATE schema_version SET version=23`. |
| `swing/data/db.py` | `EXPECTED_SCHEMA_VERSION = 23`; NEW `_phase14_sb3_backup_gate` (fires `current==22 AND target>=23` STRICT); wire into `run_migrations`. |
| `swing/data/repos/chart_renders.py` | Comments `hyprec_detail`->`ticker_detail`; the `refresh_chart_render` run-bound branch comment. (No logic change -- it already treats non-theme2/non-position surfaces uniformly.) |
| `swing/web/chart_jit.py` | `_RENDERERS` key + import + dispatch branch `hyprec_detail`->`ticker_detail`; `render_market_weather_svg` JIT branch threads real `trend_template_state`; comments. |
| `swing/web/routes/watchlist.py` | `surface="hyprec_detail"`->`"ticker_detail"` literal + comments. |
| `swing/web/routes/dashboard.py` | Refresh handler: compute `current_stage(...)` instead of `"n/a"` literal. |
| `swing/web/view_models/dashboard.py` | VM field `hyprec_detail_chart_svg_bytes`->`ticker_detail_chart_svg_bytes`; `surface="hyprec_detail"`->`"ticker_detail"` literals; `get_or_render_surface` surface arg. |
| `swing/web/view_models/watchlist.py` | Comment rename. |
| `swing/pipeline/runner.py` | `_step_charts`: pipeline weather render threads real `trend_template_state`; `hyprec_detail` comment + (if any) surface literal -> `ticker_detail`. |
| `swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2` | Template var `expanded.hyprec_detail_chart_svg_bytes`->`...ticker_detail...`; CSS class `hyprec-detail-chart`->`ticker-detail-chart`. |
| `pyproject.toml` | Add `"mplfinance>=0.12"` to the `web` extra (currently in `dev`+`charts` only; `swing/web/charts.py` will import it at runtime). |

**Tests (NEW/updated):** `tests/web/test_charts.py`, `tests/web/test_charts_volume_yticks_stripped.py`, `tests/web/test_chart_jit.py`, `tests/data/repos/test_chart_renders_repo.py`, `tests/data/test_v20_migration.py` (+ NEW `test_v23_*`), route/VM tests referencing the renamed surface, `tests/integration/test_l2_lock_source_grep.py` (unchanged-but-verified).

---

## §4 Renderer-uniformity audit (V2.G1 + P14.N2)

### §4.1 mplfinance compatibility + the shared helper

mplfinance is a pure-Python matplotlib wrapper that emits matplotlib Figures (serializable to SVG) -- it satisfies Sec 9.1 Q5 ("matplotlib SVG only; no JS"). It is **already a declared dependency** (`pyproject.toml` `dev` + `charts` extras; installed `0.12.10b0`) and **already used in production** at `swing/rendering/charts.py:render_chart`. The only packaging change is adding it to the `web` extra so a `pip install -e ".[web]"`-only deployment of `swing web` has it (the documented profile `[dev,web]` already includes it transitively via `dev`).

**Canonical pattern to mirror (`swing/rendering/charts.py:124-159`):**
```python
plot_kwargs = dict(
    type="candle", volume=True, style="yahoo",
    figsize=..., title=..., ylabel_lower="Volume",
    addplot=[mpf.make_addplot(sma, color=c, width=1.0) for ...],
    hlines=dict(hlines=[...], colors=[...], linestyle="--"),
)
fig, axes = mpf.plot(df, returnfig=True, **plot_kwargs)
price_ax = axes[0]   # volume panel is a later axis
```

**Three mpf gotchas inherited verbatim (already documented in `rendering/charts.py`):**
1. **Title renders as `fig.suptitle`, NOT `axes[0].title`.** Do not also `set_title` (duplicate title). Our `_set_suptitle_no_math` ASCII gate must run on whatever string we hand to mpf's `title=` (or we suppress mpf's title and set our own suptitle post-`returnfig`).
2. **mpf candle plots use a POSITIONAL integer x-axis** (bar 0..N-1), even with a DatetimeIndex. This is exactly what the existing web overlays assume -- `bars.index.get_loc(pd.Timestamp(...))` already returns an integer position fed to `axvspan`/`axhline`/`scatter`. Overlays port without coordinate changes. **This must be pinned by tests** (integer-extent assertions), and is a forward-binding coupling: an mpf upgrade that switches candles to date coordinates breaks overlays + tests together.
3. **`$`/mathtext discipline** -- mpf forwards `title=`/`ylabel=` to matplotlib text; the `$`/`^`/`_`/`\` gates still apply. Pattern slugs (`flat_base` etc.) stay out of titles and render via `ax.text` on the returned price axis (literal `_` outside math mode).

**Proposed helper:**
```python
def _render_candles_fig(df, *, ma_windows, figsize, volume=True, style="yahoo"):
    """Return (fig, price_ax, vol_ax_or_None) for an OHLC candlestick chart.

    df MUST carry Open/High/Low/Close[/Volume] columns + a DatetimeIndex
    (OhlcvCache output shape; same as render_chart consumes). MA overlays
    via mpf.make_addplot on the close rolling-mean. Volume y-tick labels
    stripped (T4.SB Item 3) on the returned volume axis. Gridlines on the
    price axis via price_ax.grid(...) for uniformity (P14.N8).
    """
```
Per-surface renderers call this, then overlay annotations on `price_ax` using integer bar positions, then run the ASCII-gated suptitle, then `_svg_bytes_from_fig(fig)`.

### §4.1b mpf axes structure + per-renderer conversion mechanics

**mpf axes layout (with `volume=True`).** `mpf.plot(df, returnfig=True, volume=True, ...)` returns `(fig, axes)` where `axes` is a list; `axes[0]` is the price (candle) panel and `axes[2]` is the volume panel (mpf inserts a twin y-axis at `axes[1]`/`axes[3]` for right-side labels). The helper returns an explicit `(fig, price_ax, vol_ax)` triple rather than leaking mpf's index convention to callers -- it resolves `vol_ax` from the returned list and hands back named handles. The T4.SB Item 3 volume y-tick strip becomes `vol_ax.set_yticks([])` on that resolved axis (the old code stripped a `plt.subplots`-created `ax_vol`; under mpf the target is the mpf-created volume panel). **Pin test:** assert the helper returns a non-None `vol_ax` when `volume=True` and that its y-tick labels are empty.

**Per-renderer conversion (close-line -> candlestick):**

- **`render_ticker_detail_svg`** (renamed): replace the `plt.subplots(nrows=2, height_ratios=[3,1])` + `ax_price.plot(close)` + manual `ax_vol.bar(volume)` block with `fig, price_ax, vol_ax = _render_candles_fig(df, ma_windows=(10,20,50,150,200), figsize=_figsize_inches(_TICKER_DETAIL_SIZE_PX), volume=True)`. Port the optional `pattern_evaluation` window band: `price_ax.axvspan(window_start, window_end, ...)` via the existing `bars.index.get_loc(pd.Timestamp(...))` integer-position lookup (aligns with mpf positional x-axis). Caller-context title (§5.6) via `_set_suptitle_no_math`.
- **`render_position_detail_svg`**: `_render_candles_fig(df, ma_windows=(10,20,50), volume=True)`; re-attach fill markers via `price_ax.scatter([x],[price], marker=..., zorder=5)` (x is the existing integer bar position); `price_ax.axhline(current_stop, ...)`; add the BULZ `axhspan` zones (§7).
- **`render_market_weather_svg`**: `_render_candles_fig(df, ma_windows=(50,200), volume=True, figsize=_figsize_inches(_MARKET_WEATHER_SIZE_PX))`; re-attach the trend badge `price_ax.text(0.02, 0.88, f"trend: {state}", transform=price_ax.transAxes, ...)` (state now real per §8); gridlines come from the helper.
- **`render_theme2_annotated_svg`**: `_render_candles_fig(df, ma_windows=(10,20,50,150,200), volume=False)` (this surface has no volume panel today -- keep it volume-less to preserve the 800x600 single-axis layout the `_annotate_*` family draws into); the `_ANNOTATORS` dispatch + window band + slug + exemplar footnote re-attach to the returned `price_ax`; S6 reposition (§9).
- **`render_watchlist_thumbnail_svg`**: UNCHANGED (line chart per OD-2).

**Figure DPI / sizing.** mpf accepts `figsize` (inches) -- pass `_figsize_inches(_<SURFACE>_SIZE_PX)` so pixel dimensions match today's surfaces. `_svg_bytes_from_fig(fig)` (with `bbox_inches="tight"`) serializes the mpf-returned fig unchanged; `plt.close(fig)` discipline preserved.

### §4.2 Data-shape precondition (no escalation)

mpf requires `Open/High/Low/Close` columns + a DatetimeIndex. The `bars` DataFrame is `OhlcvCache.get_or_fetch` / `_bars_or_none` output -- the SAME archive shape `render_chart` already consumes successfully. So **no OHLCV-bar-shape change is forced** (the brief §7 escalation trigger does NOT fire). Writing-plans MUST add a discriminating test asserting the bars fixture carries OHLC columns + DatetimeIndex (defends against a future cache shape that drops them, which would silently fall back / raise inside mpf). The `_close_series`/`_volume_series` MultiIndex-squeeze helpers remain for the thumbnail (line) renderers and as defense; mpf consumes the full OHLC frame directly.

### §4.3 Uniform MA set

Operator: "Potentially also should 10 and 20 MAs." Locked per-surface MA table (writing-plans pins exact windows):

| Surface | MA windows (V1) |
|---|---|
| `ticker_detail` (800x500) | 10, 20, 50, 150, 200 |
| `position_detail` (800x500) | 10, 20, 50 (trail context) |
| `theme2_annotated` (800x600) | 10, 20, 50, 150, 200 |
| `market_weather` (400x150) | 50, 200 (index trend; 10/20 too noisy at 400px -- OQ-6) |
| `watchlist_row` thumbnail | unchanged (caller `ma_lines`; line chart) |

MA windows are skipped when `window > len(close)` (existing guard preserved). Each MA is an `mpf.make_addplot` entry; the color set is centralized in the helper so it is identical across surfaces (Expansion #10c kwargs uniformity).

### §4.4 ASCII / mathtext discipline (L4)

All title/label/annotation text routes through the existing `_assert_*` gates. Candlestick adoption introduces no new user-facing strings except the BULZ zone legend (§7) and any axis labels mpf adds -- all ASCII, no `$`/`^`/`_`/`\`. Manual visual verification of rendered text is non-optional (operator-witnessed gate).

### §4.5 V2.G1 "not rendering" sub-symptom (writing-plans investigation item)

The candlestick adoption closes the *type* expectation. The orthogonal "hyp-rec/watchlist expanded charts do not display while position_detail does" sub-symptom (V2.G1 detail block bucket (c): template CSS/sizing clipping) is browser-only and not reproducible in TestClient. Writing-plans carries an explicit investigation step: diff the embedding of `ticker_detail`/`watchlist_expanded` SVG (in `hypothesis_recommendations_expanded.html.j2` + watchlist expanded partial) against the position_detail embedding; the operator-witnessed gate at executing-plans is the verdict. (Not designed-away here -- flagged so it is not lost.)

---

## §5 V2.G2 v23 rename `hyprec_detail` -> `ticker_detail`

### §5.1 Why a table rebuild

SQLite cannot `ALTER` a CHECK constraint in place. The `surface` column's CHECK enumerates `'hyprec_detail'`; after the rename, existing rows must hold `'ticker_detail'`, which would VIOLATE the old CHECK. The canonical SQLite path (and the codebase precedent at migration `0014`) is **CREATE-COPY-DROP-RENAME**:

```sql
BEGIN;
-- 1. New table with the renamed CHECK enum + identical cross-column CHECK.
CREATE TABLE chart_renders_new (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    surface TEXT NOT NULL CHECK (surface IN (
        'watchlist_row', 'ticker_detail', 'position_detail',
        'market_weather', 'theme2_annotated'
    )),
    pipeline_run_id INTEGER REFERENCES pipeline_runs(id) ON DELETE CASCADE,
    pattern_class TEXT CHECK (pattern_class IS NULL OR pattern_class IN (...)),
    chart_svg_bytes BLOB NOT NULL,
    source_data_hash TEXT NOT NULL,
    rendered_at TEXT NOT NULL,
    data_asof_date TEXT NOT NULL,
    CHECK ( (surface = 'theme2_annotated' AND pattern_class IS NOT NULL AND pipeline_run_id IS NOT NULL)
         OR (surface != 'theme2_annotated' AND pattern_class IS NULL) )
);
-- 2. Copy ALL columns INCLUDING id (preserve PKs so FK refs survive), renaming the value.
INSERT INTO chart_renders_new (id, ticker, surface, pipeline_run_id, pattern_class,
        chart_svg_bytes, source_data_hash, rendered_at, data_asof_date)
    SELECT id, ticker,
        CASE WHEN surface = 'hyprec_detail' THEN 'ticker_detail' ELSE surface END,
        pipeline_run_id, pattern_class, chart_svg_bytes, source_data_hash,
        rendered_at, data_asof_date
    FROM chart_renders;
-- 3. Drop old, rename new.
DROP TABLE chart_renders;
ALTER TABLE chart_renders_new RENAME TO chart_renders;
-- 4. Recreate the 3 partial unique indexes (verbatim from 0020; none contain 'hyprec_detail').
CREATE UNIQUE INDEX idx_chart_renders_run_bound ON chart_renders(ticker, surface, pipeline_run_id)
    WHERE pipeline_run_id IS NOT NULL AND surface != 'theme2_annotated';
CREATE UNIQUE INDEX idx_chart_renders_position_detail ON chart_renders(ticker, surface)
    WHERE pipeline_run_id IS NULL AND surface = 'position_detail';
CREATE UNIQUE INDEX idx_chart_renders_theme2_annotated ON chart_renders(ticker, surface, pipeline_run_id, pattern_class)
    WHERE surface = 'theme2_annotated' AND pipeline_run_id IS NOT NULL;
UPDATE schema_version SET version = 23;   -- MUST be final DML before COMMIT
COMMIT;
```

### §5.2 FK-safety during the rebuild

`pattern_detection_events.chart_render_id` (v22) `REFERENCES chart_renders(id) ON DELETE SET NULL`. The migration runner `_apply_migration` sets `PRAGMA foreign_keys=OFF` for the script's duration (verified at `db.py:215-216`), so dropping `chart_renders` does NOT cascade/SET-NULL the referencing rows. Because we copy `id` explicitly (step 2), the new table's PKs match the old -- so after the rebuild, every `pattern_detection_events.chart_render_id` still resolves to a valid `chart_renders.id`. **Test:** plant a `pattern_detection_events` row referencing a `chart_renders` row (surface `hyprec_detail`), run the v23 migration, assert (a) the chart_renders row now has surface `ticker_detail` with the SAME id, (b) the FK reference still resolves. (FK integrity check post-migration via `PRAGMA foreign_key_check`.)

### §5.3 Backup gate (gotcha #11 STRICT)

NEW `_phase14_sb3_backup_gate(conn, *, current_version, target_version, backup_dir)`:
- Fires ONLY when `current_version == 22 AND target_version >= 23` (STRICT equality, NOT `<=`; mirror the `_phase14_backup_gate` shape at `db.py:820-860` which gates `== 21`).
- Backup filename: `swing-pre-phase14-sb3-migration-<ISO>.db`.
- `expected_tables` integrity set includes `chart_renders` + `pattern_detection_events` + `pattern_forward_observations`.
- Multi-version walks from pre-v22 baselines bypass the gate by design (matches precedent).
- Wire into `run_migrations` after `_phase14_backup_gate`.
- **Test:** run-migrate-twice no-op (idempotent; the v23 migration does not re-fire on a v23 DB); rollback-through-runner test (force a failure mid-script, assert rollback leaves v22 intact -- gotcha #9).

### §5.4 EXPECTED_SCHEMA_VERSION bump

`EXPECTED_SCHEMA_VERSION = 22` -> `23` (`db.py:46`). This is the single source the `ensure_schema` / version-mismatch guards read.

### §5.5 Atomic Python/template/test rename (gotcha #11 paired + OD-4 full)

ALL in ONE task:
- `swing/data/models.py:99` -- `_CHART_SURFACE_VALUES` value (the `ChartRender.__post_init__:1949` validator reads this tuple -- the dataclass-validator surface).
- `swing/web/charts.py` -- `render_hyprec_detail_svg` -> `render_ticker_detail_svg` (def + docstring + module header bullet).
- `swing/web/chart_jit.py` -- import, `_RENDERERS["hyprec_detail"]` key, `if surface == "hyprec_detail"` dispatch, comments.
- `swing/web/routes/watchlist.py:216` -- `surface="hyprec_detail"` literal + comments.
- `swing/web/view_models/dashboard.py` -- field `hyprec_detail_chart_svg_bytes` -> `ticker_detail_chart_svg_bytes` (def + constructor kwarg + the `get_cached_chart_svg`/`get_or_render_surface` `surface=` literals + comments).
- `swing/web/view_models/watchlist.py:125` -- comment.
- `swing/pipeline/runner.py` -- `_step_charts` `hyprec_detail` comment (+ any surface literal).
- `swing/web/templates/partials/hypothesis_recommendations_expanded.html.j2` -- `expanded.hyprec_detail_chart_svg_bytes` -> `...ticker_detail...`; CSS class `hyprec-detail-chart` -> `ticker-detail-chart` (+ any CSS rule targeting it).
- `swing/data/repos/chart_renders.py` -- comments only.
- Tests: every fixture/assertion referencing `hyprec_detail` or `render_hyprec_detail_svg`.

**L5 gate:** `grep -rn 'hyprec_detail\|render_hyprec_detail_svg\|hyprec-detail-chart' swing/ tests/` returns ZERO matches after the rename (excluding historical docs/migrations -- the `0020_*.sql` file is immutable history and still contains `hyprec_detail`; the NEW `0023` migration is what rewrites live rows. The L5 grep scope is `swing/` runtime + templates + tests, NOT the frozen `0020` migration text).

### §5.6 Caller-context title (kills the leakage)

V2.G2 root cause: `render_hyprec_detail_svg` builds `suptitle = f"{ticker} | hyp-rec detail | last {len(close)} bars"` (`charts.py:275`), and this surface is reused for the watchlist-expanded chart -- so a watchlist expand shows "hyp-rec detail". Fix: the renamed `render_ticker_detail_svg` takes the descriptive context from the CALLER (a `subtitle`/`context_label` kwarg, default neutral e.g. `"detail"`), not the surface enum. Watchlist-expand passes its own label; hyp-rec passes its own. Title becomes `f"{ticker} | {context_label} | last {N} bars"`. ASCII-gated. (Renderer-kwargs uniformity still holds: both callers pass the SAME other kwargs; only the cosmetic label differs and is NOT part of the cache key.)

> **Cache-key caution (L3):** the title label must NOT enter `source_data_hash` or the cache key, or the two callers would thrash the cache row. The cache key stays `(ticker, surface, pipeline_run_id)` for the run-bound `ticker_detail` surface. Discriminating test: two callers, identical bars, assert one cached row (call_count parity).

---

## §6 P14.N1 chart thumbnail substrate

**V1 scope (substrate only).** P14.N1 wants watchlist-style thumbnails on the open-positions + hyp-rec tables. Per commissioning Sec 2.3, the *consuming* surfaces (open-positions row + hyp-rec row VMs/templates) couple with Sub-bundle 4 (review+journal UX). Sub-bundle 3 ships the **renderer substrate** and the cache-key decision, not the row wiring.

- **Reuse `render_watchlist_thumbnail_svg`** (line chart, 200x100, per OD-2 thumbnails stay line). No new renderer function needed for V1.
- **Cache-key decision:** do NOT add new surface enum values (`open_position_thumbnail`/`hyprec_thumbnail`) in V1 -- that would require a SECOND v-bump and widen the rename blast radius. Reuse the `watchlist_row` surface with the existing run-bound key `(ticker, surface, pipeline_run_id)`. The same ticker's thumbnail is identical regardless of which table renders it, so cache reuse is correct and avoids duplicate renders (Expansion #10c). Document this as the V1 contract; Sub-bundle 4 may introduce distinct surfaces if the tables need different dimensions/overlays.
- **Deliverable:** the thumbnail renderer is confirmed reusable + the `get_or_render_surface(surface="watchlist_row", ...)` JIT path is the substrate the row VMs will call in Sub-bundle 4. Sub-bundle 3 adds a test proving a non-watchlist ticker renders + caches a `watchlist_row` thumbnail via the JIT path.

> **OQ-4** (carried): ship consuming-surface wiring now (small) or defer fully to Sub-bundle 4? Recommendation: defer the row templates to Sub-bundle 4; ship only the substrate proof here, to keep Sub-bundle 3 focused on uniformity + rename.

---

## §7 P14.N4 BULZ entry/stop/target shaded zones

In `render_position_detail_svg` (BULZ is an open position; the renderer is per-open-trade):

- **Zones (horizontal price bands via `axhspan`):**
  - **Risk zone** `axhspan(stop, entry, color="#d62728", alpha=0.10)` -- entry-down-to-stop (the capital-at-risk band). Drawn only when `current_stop` and entry are both present and `stop < entry`.
  - **Reward zone** `axhspan(entry, target, color="#2ca02c", alpha=0.10)` -- entry-up-to-target. Drawn only when a target is available and `target > entry`.
- **Data source (open-trade row):** entry = average entry fill price (or `trade.entry_price` if denormalized); stop = `current_stop` (already a renderer param); target = the trade's target/objective field. **Writing-plans MUST verify the exact `Trade`/`Fill` field names** (#4 SQL/field verification) -- candidates: `trade.target_price` / a derived R-multiple target / `trade.entry_price`. If no target field exists, V1 draws only the risk zone + documents target-zone as deferred (do NOT invent a target).
- **Legend (the operator complaint -- "no description of what that means"):** add ASCII legend entries `"risk zone (entry->stop)"` and `"reward zone (entry->target)"` via the band's `label=` or a proxy patch in the legend. No `$`/`^`/`_`. The existing `ax.legend(loc="upper left")` renders them.
- **Color rationale:** the operator saw "green and yellow". The spec uses green (reward) + red-tinted (risk); the writing-plans phase confirms the exact hues at the operator-witnessed gate (the operator's "yellow" may map to a low-alpha red/orange risk band). The semantic (which band is which) is the binding requirement, not the precise hue.
- **Verify regression-test arithmetic (memory):** the zone-boundary test plants entry/stop/target and asserts the `axhspan` y-bounds equal those values under the post-fix path AND would NOT under a swapped/absent-zone path (so the test distinguishes).

---

## §8 P14.N8 weather-chart refresh-handler uniformity fix

Three call sites render `market_weather`; today they pass divergent literals:
- `runner.py:2883` (pipeline): `trend_template_state="stage_2"` (literal).
- `chart_jit.py:158` (JIT default): `"stage_2"` (literal default).
- `dashboard.py:117` (refresh handler): `"n/a"` (literal).

**Per OD-3, all three compute the REAL state** via `current_stage(conn, benchmark, asof_date)` (the same function `review_form._compute_trend_template_state` uses at `review_form.py:454`):
- **asof_date** = `last_completed_session(datetime.now())` (backward-looking; the writer anchor -- aligns with the refresh handler's existing `data_asof_date` write at `dashboard.py:127`). Honors the "Weather lookup must NOT query by action_session" + "session-anchor read/write" gotchas.
- **benchmark** = `cfg.rs.benchmark_ticker` (the same ticker the pipeline + dashboard reader use; divergence silently invisibles the chart per the existing `runner.py:2876` note).
- **Fail-soft:** wrap in try/except mirroring `_compute_trend_template_state` -> fall back to `"undefined"` (ASCII; not `"n/a"`) + WARN log; never 500 the refresh.
- **Gridlines:** add `price_ax.grid(...)` inside `_render_candles_fig` so weather (a candlestick adopter per OD-2) shows gridlines uniformly at every call site.

**Discriminating test (Expansion #10c):** assert all three call sites derive `trend_template_state` from `current_stage` (mock `current_stage` -> sentinel; assert the sentinel reaches the renderer at each call site). A pure byte-parity test is INSUFFICIENT (it would pass against a hardcoded literal if the literal happened to match); the test must prove the *derivation path*, per gotcha "byte-parity tests insufficient when fixtures bypass the production derivation path."

> **OQ-5** (resolved by OD-3): real source = `current_stage(conn, benchmark, last_completed_session(now()))`. Pipeline + JIT also switch to this (closing the V2-banked literal); confirm `current_stage` is import-safe in the pipeline/runner context (it reads weather rows; no Schwab/yfinance call -- L6 preserved).

---

## §9 S6 cosmetic (flat_base duration-text / legend overlap)

In `render_theme2_annotated_svg`, `_annotate_flat_base` writes `"duration: N days"` at axes `(0.02, 0.92)` (`charts.py:421`), colliding with the upper-left legend (`ax.legend(loc="upper left")`). Multiple `_annotate_*` functions write text at `(0.02, 0.92-)` (vcp contractions, cwh depth, htf days-tight, dbw undercut) -- so this is a family fix, not just flat_base.

**Fix:** centralize annotation text placement to a non-colliding anchor. Options: (a) move annotation text block to lower-left `(0.02, 0.06)` stacking upward; (b) move the legend to `loc="upper right"`; (c) reserve upper-left for the legend and put all `_annotate_*` text at upper-right `(0.98, 0.92-, ha="right")` (consistent with the existing pattern-class slug + exemplar footnote already at `ha="right"`). **Recommend (c)** -- it co-locates all body annotations on the right, away from the upper-left legend, and matches the existing right-aligned slug placement. ASCII-only; visual gate confirms no overlap. Applies uniformly across the `_annotate_*` family.

---

## §10 Sub-bundle decomposition recommendation

**Single `copowers:executing-plans` dispatch**, decomposed into ~5-7 tasks (the five items cohere on the `charts.py` + `chart_renders` + `chart_jit` substrate; commissioning Sec 2.1 predicted a single cycle):

| Task | Content | Notes |
|---|---|---|
| **T1** | v23 migration + EXPECTED_SCHEMA_VERSION + backup gate + atomic Python/template rename + L5 grep gate | Lands FIRST (schema + rename are the foundation; everything else builds on the renamed surface). Gotcha #11 + #9 paired. |
| **T2** | `_render_candles_fig` shared helper + convert `ticker_detail` + `theme2_annotated` to candlesticks + uniform MA set + ASCII | Depends on T1 (uses the renamed function). |
| **T3** | `position_detail` candlesticks + BULZ zones + legend | Depends on T2 helper. |
| **T4** | `market_weather` candlesticks + `current_stage` trend-state at all 3 sites + gridlines | Expansion #10c uniformity tests. |
| **T5** | S6 annotation-placement family fix | Small; in `theme2_annotated`. |
| **T6** | P14.N1 thumbnail substrate proof (JIT path for non-watchlist ticker) | Substrate only. |
| **T7** | Closer: pyproject `web`-extra mplfinance + full-suite + ruff + L2 source-grep verify + operator-witnessed visual gate enumeration | |

Estimated ~15-25 commits + ~40-80 tests (commissioning Sec 2.1 estimate). T2-T6 could partially parallelize but SERIAL is safest given the shared `charts.py` file (merge-conflict surface).

---

## §11 Test fixture strategy + visual-gate enumeration

### §11.1 Fixtures
- **OHLC bars fixture** with DatetimeIndex + Open/High/Low/Close/Volume (mpf precondition); reuse/extend the existing `tests/web/test_charts.py` synthetic bars. Add a fixture-shape assertion test (§4.2).
- **v23 migration fixtures:** a v22 DB with `chart_renders` rows across all 5 surfaces (incl. `hyprec_detail`) + a `pattern_detection_events` row referencing one (FK-survival test §5.2). Schema-version-aware INSERT per gotcha #11 (detect via `PRAGMA table_info` or migrate fixtures).
- **Cache-collision fixture:** two callers of `ticker_detail` (hyp-rec + watchlist-expand) with identical bars -> assert one cached row (L3).
- **BULZ zone fixture:** a `Trade` + `Fill`s with known entry/stop/target -> assert `axhspan` bounds (verify-arithmetic memory: distinguishes post-fix from swapped/absent).
- **trend-state derivation fixture:** mock `current_stage` -> sentinel; assert sentinel reaches the renderer at all 3 call sites.

### §11.2 What tests CAN and CANNOT certify (L4)
- **CAN:** function signatures + import wiring; surface-enum rename atomicity (grep gate); cache-key shape + call_count parity; ASCII-only assertion on all text fields; `axhspan`/`axhline` numeric bounds; `current_stage` derivation-path; FK survival across the rebuild; migration rollback + idempotency.
- **CANNOT (operator-witnessed gate required):** that the SVG visually renders candlesticks (not lines); that BULZ zones are legible + correctly colored; that the weather chart shows the trend badge + gridlines; that the S6 duration text no longer overlaps the legend; that V2.G1's "not rendering in browser" sub-symptom is resolved.

### §11.2b Concrete test enumeration (writing-plans pins exact names)

Per-task discriminating tests (names indicative; writing-plans finalizes):

- **T1 (v23 + rename):** `test_v23_migration_renames_existing_chart_renders_rows` (plant `hyprec_detail` rows -> assert `ticker_detail` post-migrate, same `id`); `test_v23_migration_preserves_chart_render_fk_from_detection_events` (FK survival §5.2 + `PRAGMA foreign_key_check` clean); `test_v23_backup_gate_fires_strict_pre_version_22` + `test_v23_backup_gate_skips_from_pre_v22`; `test_run_migrations_twice_v23_no_op`; `test_v23_migration_rollback_through_runner_leaves_v22` (#9); `test_chart_render_dataclass_rejects_hyprec_detail` (validator now rejects the old value); `test_no_orphaned_hyprec_detail_tokens` (L5 grep gate over `swing/`+templates+tests); `test_render_ticker_detail_svg_importable` (rename wiring).
- **T2 (candle helper + ticker_detail/theme2):** `test_render_candles_fig_returns_price_and_volume_axes`; `test_render_candles_fig_strips_volume_yticks`; `test_render_candles_fig_grid_enabled`; `test_ticker_detail_svg_overlays_pattern_window_band`; `test_ticker_detail_title_uses_caller_context_not_surface` (V2.G2 leakage); `test_ticker_detail_cache_single_row_across_two_callers` (L3 call_count parity); `test_charts_bars_fixture_has_ohlc_columns_and_datetimeindex` (§4.2 precondition); ASCII-field assertions on every title/label.
- **T3 (position_detail + BULZ):** `test_position_detail_renders_risk_zone_axhspan_bounds` (entry/stop bounds; distinguishes from absent/swapped per verify-arithmetic memory); `test_position_detail_renders_reward_zone_when_target_present`; `test_position_detail_risk_zone_only_when_no_target`; `test_position_detail_zone_legend_ascii`.
- **T4 (weather uniformity):** `test_weather_refresh_handler_computes_real_trend_state` (mock `current_stage` -> sentinel reaches renderer); `test_pipeline_weather_render_computes_real_trend_state`; `test_chart_jit_weather_computes_real_trend_state`; `test_weather_trend_state_failsoft_to_undefined`; `test_weather_three_callsites_identical_kwarg_derivation` (Expansion #10c).
- **T5 (S6):** `test_theme2_annotation_text_not_at_upper_left` (placement anchor moved); `test_theme2_flat_base_duration_text_ascii`.
- **T6 (P14.N1 substrate):** `test_jit_renders_watchlist_thumbnail_for_non_watchlist_ticker` (substrate proof + cache write-through).
- **T7 (closer):** L2 source-grep test verified green; full fast suite; `ruff check swing/` 0 E501; `pyproject` `web` extra includes mplfinance.

### §11.3 Operator-witnessed gate ladder (Sec 9.1 Q6)
- **S1** fast suite (`pytest -m "not slow"`) green + `ruff check swing/` 0 E501.
- **S2** v23 applied on a real v22 DB: `schema_version == 23`; `chart_renders` rows migrated `hyprec_detail`->`ticker_detail`; backup file written; `PRAGMA foreign_key_check` clean.
- **S3** (browser) `ticker_detail` (hyp-rec expand + watchlist expand): candlesticks render; title reads the caller context (NOT "hyp-rec detail" on watchlist); 10/20/50/150/200 MAs present.
- **S4** (browser) `position_detail` (BULZ): candlesticks + risk/reward shaded zones + legend describing them.
- **S5** (browser) `market_weather` (dashboard + after "Refresh weather chart"): candlesticks + REAL trend badge (not "n/a") + gridlines; pre/post-refresh visually equivalent.
- **S6** (browser) `theme2_annotated` flat_base: duration text no longer overlaps the legend.
- **S7** L2 LOCK source-grep test green; L5 `hyprec_detail` grep returns zero in `swing/`+templates+tests.

---

## §12 Schema impact analysis (v23)

- **Migration:** `0023_phase14_sb3_chart_surface_rename.sql` -- single-table rebuild of `chart_renders`; no other tables touched.
- **Version:** 22 -> 23. `EXPECTED_SCHEMA_VERSION = 23`.
- **Backup gate:** `_phase14_sb3_backup_gate` STRICT `== 22`.
- **Data migration:** in-migration `INSERT...SELECT` CASE-rename of existing rows (recommend in-migration over a separate backfill -- it is a pure value rename, atomic with the schema change; brief OQ-7).
- **FK impact:** `pattern_detection_events.chart_render_id` (ON DELETE SET NULL) preserved via id-preserving copy + FK-off-during-rebuild (§5.2).
- **Indexes:** 3 partial unique indexes recreated verbatim (no value change; correction §1.2.2). Cross-column CHECK recreated verbatim.
- **No new columns, no new tables, no enum *widening* (a same-cardinality value rename).** The pattern_class CHECK + all other constraints are unchanged.
- **Forward-compat:** v22 temporal-log tables (`pattern_detection_events`, `pattern_forward_observations`) are NOT modified (Sub-bundle 2 substrate LOCKED).

---

## §13 V1 simplifications + V2 candidates

**V1 simplifications (banked with V2 dependency):**
1. **Thumbnails stay close-line** (OD-2) -- candlestick thumbnails deferred (V2: a legible micro-candle renderer if operator wants candles at 200x100).
2. **P14.N1 reuses `watchlist_row` surface** -- no distinct `open_position_thumbnail`/`hyprec_thumbnail` surfaces in V1 (V2/Sub-bundle 4: distinct surfaces if tables need different dimensions/overlays).
3. **market_weather MA set = 50/200 only** (not 10/20) -- 10/20 too noisy at 400px (V2: operator-tunable MA set per surface).
4. **BULZ target-zone drawn only if a target field exists** -- if absent, risk-zone only (V2: derived R-multiple target / objective field on the trade row).
5. **P14.N1 consuming-surface wiring deferred to Sub-bundle 4** -- substrate-only in V1 (OQ-4).
6. **No chart_renders retention/eviction** -- unchanged from Phase 13 (V2: retention policy; pre-existing banked candidate, out of scope here).

**V2 candidates surfaced:**
- Candlestick thumbnails (micro-candle legibility study).
- Per-surface operator-configurable MA windows + style.
- mpf style theming (dark mode / project palette) centralized in the helper.
- Distinct thumbnail surfaces with table-specific overlays (Sub-bundle 4).

---

## §14 Operator decision items (OQs)

Resolved at this brainstorming (OD-1..OD-4 in §2.2). Remaining for writing-plans triage:

| OQ | Question | Recommendation |
|---|---|---|
| **OQ-4** | P14.N1: ship consuming-surface row wiring now or defer to Sub-bundle 4? | Defer; ship substrate-only in Sub-bundle 3. |
| **OQ-6** | market_weather MA set: 50/200 only, or also 10/20? | 50/200 (10/20 noisy at 400px). |
| **OQ-7** | v23 row rename: in-migration `UPDATE`/`INSERT...SELECT` or separate backfill? | In-migration (pure value rename). |
| **OQ-N4-target** | BULZ target source: which `Trade` field? Draw target-zone only if present? | Verify field at writing-plans (#4); risk-zone-only fallback if absent. |
| **OQ-N4-color** | Exact zone hues (operator saw "green and yellow")? | Confirm at operator-witnessed gate; semantic binding, hue cosmetic. |
| **OQ-S6** | S6 placement: move text (upper-right) or move legend? | Move annotation text to upper-right (matches existing slug placement). |
| **OQ-mav-color** | Centralized MA color set -- which 5 colors? | Pin in helper at writing-plans; ASCII-safe; distinct + colorblind-aware. |
| **OQ-chain** | Codex chain count at writing-plans: single (UX) or two (v23 substrate)? | Reconsider at writing-plans; the v23 rebuild may justify two-chain (gotcha #36 default). |

---

## §15 Cumulative discipline compliance summary

| Discipline | Application in this spec |
|---|---|
| **Matplotlib mathtext** | All text via `_assert_*` gates; no `$`/`^`/`_`/`\`; pattern slugs via `ax.text`; mpf title->suptitle gotcha inherited; visual gate binding (L4). |
| **#11 paired** | v23 CHECK + `_CHART_SURFACE_VALUES` + `ChartRender.__post_init__` validator + `_row_to_chart_render` mapper + renderer name + routes + VMs + templates + tests in ONE task (T1). |
| **#9 migration runner** | Explicit `BEGIN`...`COMMIT`; rollback-through-runner test; FK-off during rebuild (inherited from `_apply_migration`). |
| **#11 backup gate STRICT** | `_phase14_sb3_backup_gate` `== 22`; run-migrate-twice no-op test. |
| **Expansion #10c kwargs uniformity** | `_render_candles_fig` centralizes candle/MA/volume/gridline kwargs; multi-call-site `market_weather` + `ticker_detail` pass identical kwargs; cache-collision discriminating tests. |
| **#11 taxonomy propagation (L5)** | `hyprec_detail`->`ticker_detail` propagates to schema + constants + renderer + routes + VMs + templates + CSS + tests; zero-orphan grep gate. |
| **byte-parity insufficiency** | trend-state test proves the `current_stage` derivation path, not a literal match; visual gate for chart correctness. |
| **Session-anchor read/write** | weather `current_stage` uses `last_completed_session` (backward-looking writer anchor); fail-soft to `"undefined"`. |
| **#4 SQL/field verification** | BULZ target field verified at writing-plans; partial-index correction (§1.2.2) recorded. |
| **#27 silent-skip audit** | renderers already per-ticker isolate + WARN-log; preserved. |
| **L2 LOCK / #16,#32 ASCII** | zero new `schwabdev.Client.*`; source-grep test verified; all new text ASCII; mplfinance is matplotlib/Python (Q5-compatible) + already declared. |
| **Windows cp1252 stdout** | no new CLI `print` paths; renderers return bytes (no stdout). |
| **ZERO Co-Authored-By** | all commits clean; final `-m` paragraph plain prose; `%(trailers)` verified `[]` before push. |

---

*End of design spec. Phase 14 Sub-bundle 3 -- chart-surface uniformity: adopt the existing mplfinance candlestick pattern across the 4 detail renderers via a shared helper; v23 atomic `hyprec_detail`->`ticker_detail` rename (table rebuild + id-preserving row migration + STRICT backup gate); BULZ risk/reward zones; weather trend-state computed real at all 3 call sites + uniform gridlines; S6 annotation reposition; P14.N1 thumbnail substrate. The rendered chart is the BINDING operator-witnessed visual gate. Output: a spec the writing-plans phase derives an implementation plan from.*
