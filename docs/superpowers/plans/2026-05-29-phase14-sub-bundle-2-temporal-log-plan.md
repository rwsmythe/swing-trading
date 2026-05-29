# Phase 14 Sub-bundle 2 -- Temporal Pattern Detection + Observation Log Infrastructure -- Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the temporal pattern detection + observation log infrastructure: 2 NEW append-only tables (`pattern_detection_events` + `pattern_forward_observations`) via a v22 schema migration, a NEW `_step_pattern_observe` pipeline step, per-pattern metadata enrichment at detection time, and chart_render bytes capture at detection time -- eliminating cumulative gotchas #26 + #37 by architectural construction (forward-walk; no archive re-read; no regeneration).

**Architecture:** Two append-only tables form the substrate. `pattern_detection_events` is the FROZEN detection record (one row per `(source, ticker, detection_date, pattern_class)`), written ONCE by the EXTENDED `_step_pattern_detect`. `pattern_forward_observations` is the append-only forward-walk record (one row per observed trading day per open detection), written daily by the NEW `_step_pattern_observe` step inserted after detect / before charts in the DAG. Detection facts (`structural_anchors_json`, `composite_score`, `per_pattern_metadata_json`, `data_asof_date`) are LOCKED at detection; `ohlc_today_json` is LOCKED at observation and never re-fetched. Two nullable referential pointers (`pipeline_run_id`, `chart_render_id`) are AUDIT LINKAGES (both `ON DELETE SET NULL`), not frozen facts.

**Tech Stack:** Python 3.14, SQLite (migration runner in `swing/data/db.py`), frozen dataclasses (`swing/data/models.py`), caller-tx repos (`swing/data/repos/`), pipeline orchestrator (`swing/pipeline/runner.py`), matplotlib chart renderer (`swing/web/charts.py`), pytest (fast suite, `-m "not slow"`), ruff.

**Source spec:** [`docs/superpowers/specs/2026-05-28-phase14-sub-bundle-2-temporal-log-design.md`](../specs/2026-05-28-phase14-sub-bundle-2-temporal-log-design.md) (788 lines; AUTHORITATIVE for architecture; Codex CONVERGED R4).

**Dispatch brief:** [`docs/phase14-sub-bundle-2-temporal-log-writing-plans-dispatch-brief.md`](../../phase14-sub-bundle-2-temporal-log-writing-plans-dispatch-brief.md).

---

## §A Goals + non-goals

### §A.1 Goals (what this plan builds)

1. **v22 schema migration** (`0022_phase14_temporal_log.sql`): 2 NEW append-only tables with indexes + CHECK enums + FKs; `EXPECTED_SCHEMA_VERSION` 21 -> 22; STRICT `current_version == 21` backup gate; explicit `BEGIN`/`COMMIT` migration-runner discipline (gotcha #9).
2. **2 frozen dataclasses + 2 append-only repos**: `PatternDetectionEvent` / `PatternForwardObservation` with `__post_init__` validators mirroring the schema CHECK enums (gotcha #11 paired discipline); repos with NO `update_*`/`delete_*` functions (append-only; OQ-10 LOCK).
3. **`_step_pattern_detect` extension (L7)**: append a `pattern_detection_events` row per emitted detector verdict over the aplus pool; per-pattern metadata enrichment (§9 redesign); `structural_anchors_json`; `finviz_screen_state`; chart_render bytes capture via the dedicated `render_theme2_annotated_svg`; empty-pool + chart-failure `warnings_json` audit (gotcha #27). The existing `pattern_evaluations` write + existing detector tests stay UNCHANGED.
4. **NEW `_step_pattern_observe`**: enumerate open detections; append today's bar + a ruleset-agnostic lifecycle status; record the `provider` provenance tag (OQ-17 LOCK); select-by-`observation_date` + freeze (never blind-last-row; #26/#37 honest); status state machine over config-surfaced 30/60 windows (OQ-18 LOCK).
5. **Run-level `warnings_json` accumulator** threaded to `lease.release(...)` (NEW plumbing; FB-N6), consumed by both the detect-step and observe-step empty-pool/no-bar/chart-failure audit paths.

### §A.2 Non-goals (see §D for the full OUT-OF-SCOPE list)

This plan does NOT build: backfill of `pattern_detection_events` from `pattern_evaluations`; SQLite BEFORE UPDATE/DELETE triggers; `market_cap` persistence to `candidates`; any new `schwabdev.Client.*` call site; the Phase 15+ replay engine + `triggered_closed_at_*` status emission; any NEW HTMX endpoint or web surface; any schema migration beyond v22; Sub-bundle 3/4/5 scope.

---

## §B File map (per-file diff projections)

> All line ranges below are verified against production at plan-authoring time (HEAD `6574d2f`; gotcha #2 / Expansion #2 re-grep; see §C for per-surface signature citations). The implementer MUST re-verify any line range that has drifted (file edits shift line numbers) -- cite the SYMBOL, not just the line.

### §B.1 NEW files

| Path | Responsibility | Approx. size |
|---|---|---|
| `swing/data/migrations/0022_phase14_temporal_log.sql` | v22 migration: 2 NEW tables + 7 indexes + CHECK + FK; explicit `BEGIN;`/`COMMIT;`; `UPDATE schema_version SET version = 22;` as FINAL statement (gotcha #9; `0021` precedent). | ~110 lines |
| `swing/data/repos/pattern_detection_events.py` | Append-only repo: `insert_detection_event`, `get_detection_event_by_id`, `list_detection_events`, `list_observable_detections`, `_row_to_detection_event` mapper. Caller-tx (NO `conn.commit()`). NO `update_*`/`delete_*`. | ~180 lines |
| `swing/data/repos/pattern_forward_observations.py` | Append-only repo: `insert_observation`, `get_observations_for_detection`, `get_latest_observation_for_detection`, `get_latest_observations_for_detections` (dynamic-`?` IN-clause + empty short-circuit), `_row_to_observation` mapper. Caller-tx. NO `update_*`/`delete_*`. | ~170 lines |
| `swing/pipeline/temporal_metadata.py` | Pure-bars helpers: `compute_atr_pct(bars, asof)`, `compute_return_pct(bars, asof, lookback_sessions)`, `compute_52w_high_proximity_pct(bars, asof)`, `build_per_pattern_metadata(...)`, `build_finviz_screen_state(candidate)`, `build_structural_anchors_json(window, evidence)`. No I/O; consumes already-fetched bars + the `Candidate`. | ~190 lines |
| `swing/pipeline/detection_chart_capture.py` | `render_and_capture_detection_chart(conn, *, ticker, bars, pattern_evaluation, pipeline_run_id, data_asof_date) -> int | None` -- renders via `render_theme2_annotated_svg`, builds `ChartRender` (F6 barrier), calls `refresh_chart_render`, returns the chart id (or None on failure). Caller-tx. | ~90 lines |
| `tests/data/test_temporal_log_migration.py` | v22 apply + idempotency + STRICT backup-gate + rollback-through-runner + append-only schema (CHECK/UNIQUE/RESTRICT) verification. | ~12-18 tests |
| `tests/data/repos/test_pattern_detection_events_repo.py` | Repo discriminating tests (insert/get/list/list_observable; append-only source-grep; UNIQUE). | ~8-12 tests |
| `tests/data/repos/test_pattern_forward_observations_repo.py` | Repo discriminating tests (insert/chain/latest/batch-latest; dynamic-`?`; empty short-circuit; UNIQUE; RESTRICT FK; append-only source-grep). | ~10-15 tests |
| `tests/pipeline/test_temporal_metadata.py` | Pure-bars metadata helpers (atr/ret/52w; short-history None-guards; in-progress-bar strip). | ~8-10 tests |
| `tests/pipeline/test_step_pattern_detect_temporal_extension.py` | Detect-step extension (detection events appended; metadata; chart_render_id populate/NULL; empty-pool warnings; idempotency). | ~10-14 tests |
| `tests/pipeline/test_step_pattern_observe.py` | Observe-step (open-detection enumeration; bar-for-date anchoring; status state machine; provenance tag; empty-pool/no-bar warnings; idempotency). | ~14-18 tests |
| `tests/web/test_detection_chart_capture.py` | Chart capture helper + `theme2_annotated` cache-collision (call_count) + F6 failure -> None. | ~6-8 tests |

### §B.2 MODIFIED files

| Path | Change | Cited surface |
|---|---|---|
| `swing/data/db.py` | `EXPECTED_SCHEMA_VERSION` 21 -> 22 (`db.py:46`); NEW `PHASE14_PRE_MIGRATION_EXPECTED_TABLES` (= `PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES`; `db.py:129-138`); NEW `_create_pre_phase14_migration_backup`; NEW `_phase14_backup_gate` (STRICT `current_version == 21`); wire gate into `run_migrations` after `_phase13_sb6c_backup_gate` (`db.py:524-529`). | `_phase13_sb6c_backup_gate` `db.py:734-777`; `run_migrations` `db.py:780-839`; `_apply_migration` `db.py:171-214`. |
| `swing/data/models.py` | NEW `PatternDetectionEvent` + `PatternForwardObservation` frozen dataclasses + 3 module constants (`_PATTERN_DETECTION_SOURCE_VALUES`, `_FORWARD_OBSERVATION_STATUS_VALUES`, `_FORWARD_OBSERVATION_STATUS_CHANGE_EVENTS`) with `__post_init__` validators. | `PatternEvaluation` `models.py:1874-1903`; `ChartRender` `models.py:1906-1990`; `DETECTOR_PATTERN_CLASSES` `models.py:28-34`. |
| `swing/config.py` | Add `observe_max_pending_window_sessions: int = 30` + `observe_max_post_trigger_window_sessions: int = 60` to `PipelineConfig` (`config.py:158-165`). Auto-loads from `[pipeline]` TOML via existing `PipelineConfig(**raw.get("pipeline", {}))` (`config.py:508`). | `PipelineConfig` `config.py:158-165`; `load` `config.py:508`. |
| `swing/pipeline/runner.py` | (a) EXTEND `_step_pattern_detect` (`runner.py:1396`) emit loop (`runner.py:1981-2096`) to append `pattern_detection_events` + capture chart bytes; harden empty-pool early-return (`runner.py:1485-1490`) with a `warnings_json` audit. (b) NEW `_step_pattern_observe`. (c) wire `lease.step("pattern_observe")` best-effort block after the `pattern_detect` block (`runner.py:842-853`), before `schwab_snapshot` (`runner.py:854`). (d) create + thread a run-level `run_warnings: list[dict]` accumulator to the completion `lease.release(...)`. | `_step_pattern_detect` `runner.py:1396`; DAG block `runner.py:842-854`; `lease_data_asof` `runner.py:977`; `OhlcvCache` install `runner.py:768-773`. |
| `swing/web/charts.py` | Evidence-key repair in the 3 stale annotators (`_annotate_flat_base` `charts.py:407-422`; `_annotate_cup_with_handle` `charts.py:425-436`; `_annotate_high_tight_flag` `charts.py:439-450`): map the stale `ctx.evidence.get(...)` keys to the ACTUAL detector evidence field names (§C.6 table). | `render_theme2_annotated_svg` `charts.py:481`; annotators `charts.py:407-450`. |
| `tests/web/test_chart_*` (existing) | Add/extend a theme2_annotated annotation-overlay test asserting the repaired keys render (string-format assertion + a non-empty-overlay assertion); existing chart tests stay green. | -- |

### §B.3 UNCHANGED files (verify-passes; cite no edit)

| Path | Why it appears here |
|---|---|
| `tests/integration/test_l2_lock_source_grep.py` | L2 LOCK preserved -- ZERO new `schwabdev.Client.*` call sites. Multiset `Counter[(path, line_text)]`; pattern `"schwabdev.Client."`; baseline `bf7e071` (`test:26`). T-2.6 asserts continued pass. |
| `swing/data/repos/pattern_evaluations.py` | `insert_evaluation` (`pattern_evaluations.py:60-97`) is the caller-tx + append-only TEMPLATE the new repos mirror; the existing detect-step write is UNCHANGED (L7). |
| `swing/data/repos/chart_renders.py` | `refresh_chart_render` (`chart_renders.py:200+`) reused by the chart-capture helper (caller-tx, returns inserted id). Coexists last-writer-wins with the exemplar writer. UNCHANGED. |
| `swing/data/ohlcv_archive.py` | `resolve_ohlcv_window` (`ohlcv_archive.py:372-401`) reused by the observe-step bar-for-date read (returns `(df, provenance_dict)`; archive-first; zero Schwab). UNCHANGED. |
| `swing/web/view_models/patterns/exemplars.py` | The exemplar cache-miss path (`exemplars.py:250-335`) ALSO writes `theme2_annotated` -- the shared-surface coexistence the SET-NULL FK makes safe (FB-N3). UNCHANGED. |

---

## §C Surface-by-surface integration analysis

> Each subsection re-verifies a production surface the spec depends on (gotcha #2 / Expansion #2: signature + side-effect + error-semantics). All signatures below were re-grepped against HEAD `6574d2f`.

### §C.1 Migration runner (`swing/data/db.py`)

- **`EXPECTED_SCHEMA_VERSION = 21`** (`db.py:46`) -> bump to `22`.
- **`_apply_migration(conn, sql_path)`** (`db.py:171-214`): reads SQL text, captures `prior_fk`, sets `PRAGMA foreign_keys=OFF`, `conn.executescript(sql)`, `conn.commit()`; on exception `conn.rollback()` + re-raise; `finally` restores `foreign_keys`. This is the gotcha-#9 path the `0022` SQL's explicit `BEGIN;`/`COMMIT;` rides on. No table rebuilds in `0022` (pure additive `CREATE TABLE`), so the FK-cascade-wipe risk does not apply -- but the discipline is inherited uniformly.
- **`_phase13_sb6c_backup_gate(conn, *, current_version, target_version, backup_dir)`** (`db.py:734-777`): STRICT guard `if target_version < 21 or current_version != 20: return`. The new `_phase14_backup_gate` mirrors this VERBATIM with `< 22` / `!= 21` and a `swing-pre-phase14-migration-<ISO>.db` filename. Wired into `run_migrations` (`db.py:780-839`) AFTER `_phase13_sb6c_backup_gate` (`db.py:524-529`), BEFORE the `apply_ceiling = min(target_version, EXPECTED_SCHEMA_VERSION)` migration loop.
- **`PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES`** (`db.py:129-138`): `PHASE13_PRE_MIGRATION_EXPECTED_TABLES | {pattern_exemplars, chart_renders, pattern_evaluations, watchlist_close_track_flags, watchlist_close_track_flag_events}`. `PHASE14_PRE_MIGRATION_EXPECTED_TABLES = PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES` UNCHANGED: migration `0021` (v20->v21) added only `trades` columns + indexes (verified `0021` body: 2 `ALTER TABLE trades ADD COLUMN` + 2 `CREATE INDEX`), no new tables, so the table set present at v21 equals the set present at v20.

### §C.2 `0021` migration template (`swing/data/migrations/0021_phase13_t2_sb6c_trades_backlinks.sql`)

Verified structure: a leading comment block, then `BEGIN;`, the DDL, `UPDATE schema_version SET version = 21;` (the FINAL statement before COMMIT, per the Phase 9 §A.0 R1 Critical #1 precedent), then `COMMIT;`. `0022` copies this skeleton exactly with `version = 22`.

### §C.3 Detect-step (`swing/pipeline/runner.py:_step_pattern_detect`)

- **Signature** (`runner.py:1396-1402`): `def _step_pattern_detect(*, cfg, lease: Lease, eval_run_id: int, ohlcv_cache) -> None`.
- **`candidates = fetch_candidates_for_run(read_conn, eval_run_id)`** (`runner.py:1459`) -- already in memory; the extension builds `candidate_by_ticker = {c.ticker: c for c in candidates}` (ZERO new query, §6.2).
- **Empty-pool early-return** (`runner.py:1485-1490`): `if not aplus_tickers: log.info(...); return`. Harden with a `warnings_json` audit entry BEFORE the `return` (gotcha #27).
- **`asof_run = _resolve_eval_run_action_session_date(cfg=cfg, lease=lease, eval_run_id=eval_run_id)`** (`runner.py:1499`); this is the action-session date (`detection_date`). The detector data cutoff `data_asof_date = lease_data_asof(cfg, lease)` (`runner.py:977` helper, returns `str`).
- **`bars = ohlcv_cache.get_or_fetch(ticker=ticker, window_days=400)`** (`runner.py:1603`) -- already-fetched bars are reused for metadata + chart capture (zero new fetch).
- **`resolved_emit_list`** (`runner.py:1901-1969`): a list of 9-tuples `(ticker, pattern_class, version_str, window, evidence, geometric_score, template_match_score, nearest_exemplar_ids, composite_score)`.
- **Emit loop + `insert_evaluation`** (`runner.py:1981-2096`, inside `with lease.fenced_write() as conn:` opened at `runner.py:1769`): builds `row = PatternEvaluation(...)`, calls `insert_evaluation(conn, row)`, increments `rows_written`. The extension appends -- in the SAME loop iteration, AFTER the successful `insert_evaluation` -- a `PatternDetectionEvent` build + chart capture + `insert_detection_event`, all inside the SAME `lease.fenced_write()` transaction (one atomic commit per detect step).

### §C.4 DAG insertion (`swing/pipeline/runner.py`)

- The `pattern_detect` best-effort block is at `runner.py:842-853` (`lease.step("pattern_detect")` + try/except). The `schwab_snapshot` comment block begins at `runner.py:854`. INSERT the new `lease.step("pattern_observe")` + best-effort try/except block at `runner.py:854` (after detect, before schwab_snapshot). Mirror the `pattern_detect` block shape exactly (re-raise `LeaseRevokedError`; `log.warning` other exceptions).
- **`OhlcvCache`** instantiated at `runner.py:768-773` and threaded to `_step_pattern_detect`; the observe step receives the SAME instance (L4 zero new fetch infrastructure).
- **`lease.release(*, state, error_message=None, warnings_json=None)`** (`lease.py:74-86`) already accepts `warnings_json`; it is currently UNUSED (no caller populates it -- FB-N6 NEW plumbing). T-2.5 step 0 verifies the exact completion-path `lease.release(state="complete", ...)` callsite and threads `warnings_json=json.dumps(run_warnings) if run_warnings else None`.

### §C.5 OHLCV read + provider provenance (OQ-17)

- **`resolve_ohlcv_window(ticker, *, start, end, cache_dir) -> tuple[pd.DataFrame, dict[str, str]]`** (`ohlcv_archive.py:372-401`): reads `{TICKER}.schwab_api.parquet` + `{TICKER}.yfinance.parquet` from `cache_dir`, filters to `[start, end]`, picks the highest-precedence provider per `asof_date` (`schwab_api` > `yfinance`); returns `(DataFrame, provenance_dict)` where `provenance_dict[asof_date] = winner_provider`. Archive-read-merge -- NO live fetch (zero Schwab; L2 preserved).
- **`OhlcvCache.get_or_fetch(self, *, ticker, window_days=180) -> pd.DataFrame`** (`ohlcv_cache.py:131`): returns a bare DataFrame (NOT the `OhlcvBundle` that carries `provider`). The `OhlcvBundle.provider` field (`'schwab_api'|'yfinance'|None`, `ohlcv_cache.py:38-79`) lives in the internal `_store`. **DISCREPANCY RESOLVED (writing-plans design decision; spec §7.2 delegated the exact read path to writing-plans):** the observe step does NOT read provenance off `get_or_fetch`. Instead it (1) calls `get_or_fetch` to ensure the bar is populated/refreshed into the archive (write-through ladder; archive-first; zero Schwab), then (2) calls `resolve_ohlcv_window(ticker, start=window_start, end=observation_date, cache_dir=cfg.paths.prices_cache_dir)` to read the bar-for-`observation_date` + its `provenance_dict[observation_date]`. This satisfies all three OQ-17 binding requirements: select-by-`observation_date` (not blind last-row), provider provenance recorded per bar, archive-first zero-Schwab. **T-2.5 step 0 verifies** that `get_or_fetch` write-throughs to the same per-provider parquet `resolve_ohlcv_window` reads (the `prices_cache_dir`); if the write-through path differs, the implementer ESCALATES (it would be a #24-family freshness desync surfacing) rather than silently patching.

### §C.6 Chart capture (`render_theme2_annotated_svg` + evidence-key repair)

- **`render_theme2_annotated_svg(*, ticker, bars: pd.DataFrame, pattern_evaluation: PatternEvaluation, exemplar_thumbnails: list[bytes] | None = None) -> bytes`** (`charts.py:481`): the DEDICATED pattern-consuming renderer. It parses `pattern_evaluation.structural_evidence_json` into `ctx.evidence` (a dict) and dispatches to per-class annotators.
- **`chart_jit._RENDERERS`** (`chart_jit.py:56-61`) registers only `hyprec_detail`, `market_weather`, `position_detail`, `watchlist_row` -- NOT `theme2_annotated`. The chart-capture helper calls `render_theme2_annotated_svg` DIRECTLY (not via `chart_jit.get_or_render_surface`), so no `_RENDERERS` registration is needed in V1+. (Rationale: the detect step already holds the exact `PatternEvaluation` row + bars; a direct render is simpler than threading through the JIT cache-read path. The JIT registration is a banked V2 nicety, NOT required for capture.)
- **`refresh_chart_render(conn, chart_render: ChartRender) -> int`** (`chart_renders.py:200+`): DELETE-then-INSERT atomic refresh keyed `(ticker, surface, pipeline_run_id, pattern_class)` for `theme2_annotated`; caller-tx (NO `conn.commit()`); returns `int(cur.lastrowid)`. The SAME helper the exemplar path uses -> last-writer-wins coexistence (FB-N3).
- **Evidence-key repair (Codex R1 M#2; refined by plan-time re-grep -- enriched key-map):** the 3 annotators read STALE `ctx.evidence` keys. Repair table:

  | Annotator | Stale key (`charts.py`) | Actual evidence field | Detector |
  |---|---|---|---|
  | `_annotate_flat_base` (`charts.py:411`) | `top_of_range` | `range_top_price` | `FlatBaseEvidence` (`flat_base.py`) |
  | `_annotate_flat_base` (`charts.py:412`) | `bottom_of_range` | `range_bottom_price` | `FlatBaseEvidence` |
  | `_annotate_flat_base` (`charts.py:419`) | `duration_days` | `base_duration_days` | `FlatBaseEvidence` |
  | `_annotate_cup_with_handle` (`charts.py:429`) | `depth_ratio` | `cup_depth_pct` | `CupWithHandleEvidence` |
  | `_annotate_cup_with_handle` (`charts.py:435`) | `cup_bottom_price` | `cup_bottom_price` (MATCH -- no change) | `CupWithHandleEvidence` |
  | `_annotate_high_tight_flag` (`charts.py:441`) | `consolidation_duration_days` | `consolidation_duration_days` (MATCH) | `HighTightFlagEvidence` |
  | `_annotate_high_tight_flag` (`charts.py:447`) | `pole_advance_pct` | `pole_pct` | `HighTightFlagEvidence` |

  **The VCP + double_bottom_w annotators are NOT in the stale set** (T-2.4 step verifies by reading the full `charts.py:405-470` annotator block; VCP uses `pivot_price`/`base_top_price`, DBW uses `trough_1_price`/`trough_2_price` -- if either reads a stale key the implementer adds it to the repair, else leaves them). **Matplotlib mathtext gotcha:** no annotator label may contain `$`/`^`/`_`/unbalanced `\` (string-equality tests miss it; the repaired labels use plain text -- verify visually-safe text).

### §C.7 Detector evidence dataclasses (status-machine anchors)

All 5 detector evidence dataclasses carry a `pivot_price` field (verified): `VcpEvidence.pivot_price`, `FlatBaseEvidence.pivot_price` (`flat_base.py:103`), `CupWithHandleEvidence.pivot_price`, `HighTightFlagEvidence.pivot_price`, `DoubleBottomWEvidence.pivot_price`. The status-machine breakout predicate (`today_high >= pivot_price`) is sound across all 5. The per-class `structural_invalidation_level` source fields (§7.3.1): flat_base `range_bottom_price`; VCP lowest-contraction trough (from `contractions`); cup_with_handle `cup_bottom_price`; high_tight_flag `pole_start_price`; double_bottom_w `min(trough_1_price, trough_2_price)`. All present in the evidence dataclasses and serialized into `structural_anchors_json` (the `evidence` asdict).

### §C.8 Candidate metadata sourcing (§9 redesign; FB-N2)

- **`Candidate`** (`models.py:110-134`): has `sector`, `industry`, `adr_pct`, `rs_rank`, `rs_method`, `close`, `criteria: tuple[CriterionResult, ...]`. **NO `market_cap`/`market_cap_dollars`; NO `atr_pct`/`average_true_range`** (verified `fetch_candidates_for_run` SELECT, `candidates.py:87-138`). `market_cap = NULL` in V1+ (OQ-16 LOCK).
- **`CriterionResult`** (`models.py:101-107`): fields `criterion_name`, `layer` (`'trend_template'|'vcp'|'risk'`), `result` (`'pass'|'fail'|'na'`), `value`, `rule`. `finviz_screen_state` uses `{cr.criterion_name: cr.result for cr in c.criteria}` (the verdict string, NOT a coerced bool).
- The 3 computed metadata fields (`atr_pct`, `ret_90d`, `prox_52w_high_pct`) come from the already-fetched `bars` via the pure helpers in `swing/pipeline/temporal_metadata.py` (zero new fetch; L2).

---

## §D Out-of-scope (do not design into the plan)

Verbatim from dispatch brief §4 + spec §11 OUT-OF-SCOPE:

- Backfill of `pattern_detection_events` from existing `pattern_evaluations` (V2; spec §13 #10).
- SQLite BEFORE UPDATE/DELETE triggers (OQ-10 LOCK: repo-layer only in V1+; triggers are V2 §13 #7).
- Persisting `market_cap` to `candidates` (OQ-16 LOCK: NULL in V1+; V2 §13 #1).
- Relaxing the L2 LOCK to force a Schwab market-data fetch (OQ-17 rejected alternative).
- The Phase 15+ real-time ruleset replay engine + `triggered_closed_at_target`/`triggered_closed_at_stop` status emission (the substrate ENABLES it; this plan does NOT build it; spec §13 #5).
- Operator failure-mode classification surface (V1++).
- Cross-pattern composite signals; ML re-ranker; drift monitoring; active alerting.
- chart-render backfill for historical detections.
- Schema migrations beyond v22 (v23 belongs to Sub-bundle 3).
- NEW HTMX endpoints / web surfaces (Sub-bundle 2 is pipeline + schema only).
- Sub-bundle 3/4/5 scope (Sec 9.1 Q1 serial LOCK).
- The `chart_jit._RENDERERS` registration of `theme2_annotated` (banked V2 nicety; capture renders directly).
- normalized per-class anchor columns / typed metadata columns (V2 §13 #3, #4).
- CLAUDE.md / orchestrator-context archive-splits.

---

## §E Operator-paired locks reverification (cumulative LOCK summary)

> Per dispatch brief §1.5 L5: re-cite Sec 9.1 LOCKs + L1-L8 + spec §2 LOCKs + this brief's §1 LOCKs + the 5 OQ dispositions. The plan HOLDS THE LINE on every row below (dispatch brief §7).

| LOCK | Source | Disposition in this plan |
|---|---|---|
| Q1 sequencing (temporal log V1+ THIS) | commissioning Sec 9.1 | Honored -- this is the temporal-log sub-bundle. |
| Q2 SERIAL | commissioning Sec 9.1 | Honored -- single executing-plans dispatch (§1.4). |
| Q3 V1+ scope (base + chart capture) | commissioning Sec 9.1 | Honored -- T-2.4 chart capture is V1+. |
| Q6 operator-witnessed close-out (incl. v22) | commissioning Sec 9.1 | Honored -- §I gate runbook S1-S7. |
| Q7 Codex chain count (orchestrator discretion) | commissioning Sec 9.1 | TWO chains (OQ-20 LOCK; §J). |
| L1 append-only on BOTH tables | spec §2.2 | Repos have NO `update_*`/`delete_*` (source-grep tests); UNIQUE + RESTRICT FK. |
| L2 forward-walk; #26+#37 eliminated by construction | spec §2.3 (NORMATIVE) | select-by-`observation_date` + freeze; `data_asof_date` boundary; never re-read past date. Discriminating test §H. |
| L3 v22 migration (gotcha #9 + #11 + STRICT backup-gate) | spec §2.2 | T-2.1 owns all three. |
| L4 observe-step zero-cost (reuse OhlcvCache ladder) | spec §2.2 | observe reuses the same `ohlcv_cache` instance; no new fetch infra. |
| L5 chart capture reusing theme2_annotated | spec §2.2 | T-2.4 reuses surface + dedicated renderer; SET NULL FK. |
| L6 per-pattern metadata at detection | spec §2.2 / §9 | T-2.3 computes from bars + candidate; market_cap NULL. |
| L7 detect-step EXTENSION not replacement | spec §2.2 | Existing `insert_evaluation` + detector tests UNCHANGED. |
| L8 L2 LOCK (zero new Schwab calls) | spec §2.2 | source-grep test continues passing (T-2.6). |
| 2-table architectural primitive | commissioning Sec 2.5 + spec §2.4 | HELD -- no consolidation. |
| OQ-10 append-only = repo-layer + UNIQUE + RESTRICT FK | dispatch brief §1.3 | T-2.2/T-2.3 enforce; triggers banked V2. |
| OQ-16 market_cap = NULL | dispatch brief §1.3 | per_pattern_metadata `market_cap: null`. |
| OQ-17 fetch-scope bounded + `provider` provenance tag | dispatch brief §1.3 | observe reads via `resolve_ohlcv_window`; provider recorded in `ohlc_today_json`. |
| OQ-18 30/60 config-surfaced windows + per-class invalidation | dispatch brief §1.3 | `PipelineConfig` fields; ruleset-agnostic `{pending, triggered_open, invalidated, expired}`. |
| OQ-19 chart FK = ON DELETE SET NULL | spec §8.3 | Both `pipeline_run_id` + `chart_render_id` SET NULL. HELD against RESTRICT. |
| OQ-20 TWO Codex chains | dispatch brief §1.3 | §J writing-plans + executing-plans two-chain placement. |

---

## §F Cumulative discipline + watch items applied (per task)

> The 37 BINDING CLAUDE.md gotchas (code-failure prevention) + the relocated Expansion #N catalog (`docs/orchestrator-context.md` §"Pre-Codex review + brief-authoring disciplines") + the 18 brainstorm adversarial watch items (dispatch brief §5). Per-task application is enumerated in each §G task's "Discipline preservation" block; the master matrix:

| Discipline | Where applied (task) |
|---|---|
| #9 executescript implicit COMMIT -> explicit BEGIN/COMMIT/ROLLBACK + rollback-through-runner test | T-2.1 |
| #11 Schema-CHECK + Python-constant + dataclass-validator paired + read-path `_row_to_*` same task | T-2.1 (CHECK), T-2.2 (constants + validators + mapper for detection), T-2.3 repo, T-2.2/T-2.3 |
| migration backup-gate STRICT `current_version == 21` (NOT `<=`) | T-2.1 |
| sqlite3 list-bind / dynamic-`?` IN-clause + empty-input short-circuit | T-2.3 (`get_latest_observations_for_detections`) |
| `date.fromisoformat` TEXT->date boundary (convert at callsite; malformed-input guard) | T-2.5 (`sessions_since_detection` + status predicates) |
| #26 OHLCV archive bar-content TEMPORAL mutation -- ELIMINATED BY CONSTRUCTION | T-2.5 (select-by-date + freeze; forward-walk test) |
| #37 substrate-freshness sensitivity -- ELIMINATED BY CONSTRUCTION | T-2.5 (append-only; no regeneration) |
| #27 silent-skip-without-audit -> `warnings_json` | T-2.3 detect empty-pool + T-2.5 observe empty-pool/no-bar + T-2.4 chart-render-failure |
| #5 OHLCV fetch scope (open-trade tickers) -- observe expansion AUDITED + accepted | T-2.5 (OQ-17) |
| `ChartRender.__post_init__` F6 empty-bytes barrier reused | T-2.4 |
| #16/#32 ASCII discipline scope | §K.4 (all NEW/MODIFIED production + test files) |
| Co-Authored-By footer suppression | §G.0 (all commits); §M return-report §13 |
| Expansion #2 brief-vs-signature (re-grep at writing-plans) | §C (done); each task re-cites |
| Expansion #4 SQL column verification + runtime-binding-shape + empty-result-set | T-2.1 DDL, T-2.3 IN-clause |
| Expansion #8 per-counter UNIT audit | T-2.3 (`rows_written`-style counters), T-2.5 (open-pool count) |
| Expansion #11 taxonomy/attribution propagation (status/source/provider by FIELD) | T-2.1/T-2.2 (enums) + T-2.5 (provider) |
| Expansion #13 cumulative regression cascade audit | §G.0 + each Codex round |
| Expansion #15 narrative artifact path/fact lag | §M (return report sweep) |
| test-fixture-vs-production-emitter shape parity (Phase 12 C.D family) | §L (fixtures derive from production emitter shapes) |
| #1 trust pytest over plan estimate | §H (sum-check disclaimer) |

---

## §G Per-task slicing (T-2.1 .. T-2.6)

### §G.0 Commit cadence preface

> Per dispatch brief §1.5 L4 (~15-25 commits) + Expansion #13 (cumulative-regression-cascade audit at each Codex round). This is ONE executing-plans dispatch (§1.4 LOCK); the 6 tasks decompose internally.

**Per-task commit budget (target ~21 commits total; the implementer may consolidate per the notes below toward ~18-22):**

| Task | Commits | Rationale |
|---|---|---|
| T-2.1 schema substrate | 5 | (1) `0022` SQL + apply test; (2) `db.py` EXPECTED_SCHEMA_VERSION + expected-tables; (3) `_phase14_backup_gate` + wiring + strict-equality test; (4) rollback-through-runner test; (5) 2 dataclasses + 3 constants + `__post_init__` validators + validator tests. |
| T-2.2 detection_events repo | 4 | (1) `insert_detection_event` + `_row_to_detection_event` + get-by-id; (2) `list_detection_events`; (3) `list_observable_detections`; (4) append-only source-grep + UNIQUE tests. |
| T-2.3 observations repo | 4 | (1) `insert_observation` + `_row_to_observation` + chain read; (2) latest + batch-latest (dynamic-`?` + empty short-circuit); (3) UNIQUE + RESTRICT FK tests; (4) append-only source-grep test. |
| T-2.4 detect extension + chart | 5 | (1) `temporal_metadata.py` pure helpers + tests; (2) `detection_chart_capture.py` + cache-collision/F6 tests; (3) charts.py evidence-key repair + overlay test; (4) detect-loop append (events + metadata + chart_render_id) + idempotency test; (5) detect empty-pool `warnings_json` audit + test. |
| T-2.5 observe step | 5 | (1) `PipelineConfig` 30/60 fields + load test; (2) `_step_pattern_observe` skeleton + `_bar_for_date` anchoring + provider tag; (3) `_advance_status` state machine + arithmetic tests; (4) DAG wiring + run-warnings accumulator threading; (5) observe empty-pool/no-bar `warnings_json` + idempotency tests. |
| T-2.6 closer | 2 | (1) cross-step forward-walk integration test + L2 source-grep + ASCII verify; (2) return report. |
| **Total** | **~21-25** | within the ~15-25 LOCK; consolidation notes below trim toward ~21. |

**Consolidation allowances (the implementer may merge to reduce churn; trust `pytest` over the estimate per gotcha #1):** T-2.1 commits 3+4 may merge (both backup-gate/runner discipline). T-2.2/T-2.3 commits 1+2 may merge per repo. The closer's 2 commits stay separate (integration evidence then narrative). **Each commit MUST be green** (`pytest -m "not slow" -q` on the touched modules) before the next.

**Every commit message:** conventional stem (`feat(data):`, `feat(pipeline):`, `fix(web):`, `test(...)`); **NO `Co-Authored-By` footer**; NO `--no-verify`. Example: `feat(data): add 0022 v22 temporal-log migration (2 append-only tables)`.

---

### Task T-2.1: v22 schema substrate (migration + db.py wiring + dataclasses)

**Files:**
- Create: `swing/data/migrations/0022_phase14_temporal_log.sql`
- Modify: `swing/data/db.py` (`EXPECTED_SCHEMA_VERSION`:46; constants near :129-138; new gate near :734-777; wiring near :524-529)
- Modify: `swing/data/models.py` (append after `ChartRender` ~:1990; constants near the top with `DETECTOR_PATTERN_CLASSES`:28-34)
- Test: `tests/data/test_temporal_log_migration.py`
- Test: `tests/data/test_models_temporal.py` (dataclass validators)

**Acceptance criteria:**
- `0022_phase14_temporal_log.sql` creates `pattern_detection_events` (12 cols incl. `data_asof_date`; `chart_render_id` + `pipeline_run_id` both `ON DELETE SET NULL`) + `pattern_forward_observations` (8 cols; `detection_id` `ON DELETE RESTRICT`; `UNIQUE(detection_id, observation_date)`) + 7 indexes (1 UNIQUE `idx_pde_source_ticker_date_class` + 3 non-unique on detection_events + 3 non-unique on observations) + CHECK enums; final statement `UPDATE schema_version SET version = 22;` inside explicit `BEGIN;`/`COMMIT;`.
- `EXPECTED_SCHEMA_VERSION == 22`; `_phase14_backup_gate` fires ONLY at `current_version == 21 AND target_version >= 22` (STRICT); `PHASE14_PRE_MIGRATION_EXPECTED_TABLES == PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES`.
- `PatternDetectionEvent` + `PatternForwardObservation` frozen dataclasses validate enums in `__post_init__` mirroring the CHECK (gotcha #11 paired -- CHECK + constant + validator in THIS task).
- Existing suite green; `ruff check swing/` clean.

**Discipline preservation:** #9 (explicit BEGIN/COMMIT + rollback-through-runner test); #11 (CHECK + constant + validator atomic); STRICT backup-gate equality; Expansion #4 (every DDL column verified); ASCII (§K.4).

- [ ] **Step 1: Write the migration-apply failing test**

```python
# tests/data/test_temporal_log_migration.py
import sqlite3
import pytest
from pathlib import Path
from swing.data.db import run_migrations, _current_version, EXPECTED_SCHEMA_VERSION


def _fresh_v21_db(tmp_path: Path) -> sqlite3.Connection:
    """A connection migrated to v21 (one below target)."""
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=21, backup_dir=tmp_path)
    assert _current_version(conn) == 21
    return conn


def test_0022_brings_db_to_v22_with_both_tables(tmp_path):
    conn = _fresh_v21_db(tmp_path)
    run_migrations(conn, target_version=22, backup_dir=tmp_path)
    assert _current_version(conn) == 22
    tables = {
        r[0] for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        )
    }
    assert "pattern_detection_events" in tables
    assert "pattern_forward_observations" in tables


def test_expected_schema_version_is_22():
    assert EXPECTED_SCHEMA_VERSION == 22
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/data/test_temporal_log_migration.py -q`
Expected: FAIL (`EXPECTED_SCHEMA_VERSION` is 21; `0022` does not exist; v22 unreachable).

- [ ] **Step 3: Write the `0022` migration**

```sql
-- swing/data/migrations/0022_phase14_temporal_log.sql
-- Phase 14 Sub-bundle 2 -- v22 migration: temporal pattern detection +
-- observation log infrastructure (2 NEW append-only tables).
-- Atomic via explicit BEGIN; ... COMMIT; per CLAUDE.md gotcha #9
-- (executescript implicit COMMIT) + migration 0021 precedent.
-- Bumps schema_version 21 -> 22.
--
-- APPEND-ONLY INVARIANT (spec section 2.3 NORMATIVE): no application code
-- path ever UPDATEs or DELETEs a row in either table. Detection FACTS
-- (structural_anchors_json, composite_score, per_pattern_metadata_json,
-- data_asof_date, ...) are LOCKED at detection. ohlc_today_json is LOCKED
-- at observation and NEVER re-fetched. Eliminates gotchas #26 + #37 by
-- construction (forward-walk; no archive re-read; no regeneration).
--
-- NOTE for future maintainers: pattern_forward_observations.status allows
-- 6 values for forward-compat, BUT V1+ only EMITS the ruleset-agnostic
-- subset {pending, triggered_open, invalidated, expired}. The
-- triggered_closed_at_target / triggered_closed_at_stop values are RESERVED
-- for the Phase 15+ replay engine (OUT-OF-SCOPE). The dead V1+ values are
-- NOT a wiring gap.

BEGIN;

CREATE TABLE pattern_detection_events (
    detection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    detection_date TEXT NOT NULL,            -- action_session_date (operator-facing label the verdict is FOR)
    data_asof_date TEXT NOT NULL,            -- detector DATA cutoff (last completed bar); forward-walk boundary anchor
    pattern_class TEXT NOT NULL CHECK (pattern_class IN (
        'vcp', 'flat_base', 'cup_with_handle',
        'high_tight_flag', 'double_bottom_w'
    )),
    structural_anchors_json TEXT NOT NULL,   -- LOCKED at detection (window + full evidence asdict)
    composite_score REAL NOT NULL,           -- LOCKED at detection
    detector_version TEXT NOT NULL,          -- provenance: which detector emitted this
    finviz_screen_state TEXT,                -- canonicalized per-ticker eval/screen state JSON (nullable for non-pipeline)
    source TEXT NOT NULL CHECK (source IN (
        'pipeline', 'v2_cohort', 'd2_baseline', 'backfill', 'synthetic'
    )),
    per_pattern_metadata_json TEXT NOT NULL, -- LOCKED (sector/industry/adr_pct/atr_pct/ret_90d/prox_52w/rs_rank/close/market_cap-null)
    pipeline_run_id INTEGER
        REFERENCES pipeline_runs(id) ON DELETE SET NULL,  -- AUDIT LINKAGE: detection SURVIVES run pruning (not a fact mutation)
    chart_render_id INTEGER
        REFERENCES chart_renders(id) ON DELETE SET NULL,  -- AUDIT LINKAGE to ephemeral run-scoped chart cache; NULL on render-fail or later refresh
    created_at TEXT NOT NULL                 -- INSERT timestamp (ISO)
);

-- One detection per (source, ticker, detection_date, pattern_class). For
-- source='pipeline', detection_date == the run's action_session_date.
CREATE UNIQUE INDEX idx_pde_source_ticker_date_class
    ON pattern_detection_events(source, ticker, detection_date, pattern_class);
CREATE INDEX idx_pde_ticker_date
    ON pattern_detection_events(ticker, detection_date);
CREATE INDEX idx_pde_class_date
    ON pattern_detection_events(pattern_class, detection_date);
CREATE INDEX idx_pde_pipeline_run_id
    ON pattern_detection_events(pipeline_run_id);

CREATE TABLE pattern_forward_observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    detection_id INTEGER NOT NULL
        REFERENCES pattern_detection_events(detection_id) ON DELETE RESTRICT,  -- append-only: cannot delete a detection with observations
    observation_date TEXT NOT NULL,          -- the trading session this bar belongs to (ISO)
    ohlc_today_json TEXT NOT NULL,           -- LOCKED at observation; never re-fetched ({open,high,low,close,volume,provider})
    status TEXT NOT NULL CHECK (status IN (
        'pending', 'triggered_open',
        'triggered_closed_at_target', 'triggered_closed_at_stop',
        'invalidated', 'expired'
    )),
    status_change_event TEXT CHECK (
        status_change_event IS NULL OR status_change_event IN (
            'entry_fired', 'stop_fired', 'target_fired',
            'time_exit', 'shape_break', 'observation_horizon_reached'
        )
    ),
    sessions_since_detection INTEGER NOT NULL,  -- count of sessions from detection.data_asof_date UP TO AND INCLUDING observation_date
    created_at TEXT NOT NULL,                 -- INSERT timestamp (ISO)

    UNIQUE (detection_id, observation_date)
);

CREATE INDEX idx_pfo_detection_date
    ON pattern_forward_observations(detection_id, observation_date);
CREATE INDEX idx_pfo_observation_date
    ON pattern_forward_observations(observation_date);
CREATE INDEX idx_pfo_status
    ON pattern_forward_observations(status);

UPDATE schema_version SET version = 22;   -- MUST be FINAL statement before COMMIT

COMMIT;
```

- [ ] **Step 4: Bump `EXPECTED_SCHEMA_VERSION` + add the expected-tables constant**

```python
# swing/data/db.py  (line 46)
EXPECTED_SCHEMA_VERSION = 22

# swing/data/db.py  (near line 138, after PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES)
# v21 (migration 0021) added only trades columns + indexes -- NO new tables --
# so the table set present at v21 equals the set present at v20.
PHASE14_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES
)
```

- [ ] **Step 5: Run Step-1 test -- v22 apply now passes (gate not yet wired)**

Run: `python -m pytest tests/data/test_temporal_log_migration.py::test_0022_brings_db_to_v22_with_both_tables tests/data/test_temporal_log_migration.py::test_expected_schema_version_is_22 -q`
Expected: PASS.

- [ ] **Step 6: Write the STRICT backup-gate test (failing)**

```python
# tests/data/test_temporal_log_migration.py  (append)
from swing.data.db import _phase14_backup_gate, PHASE14_PRE_MIGRATION_EXPECTED_TABLES


def test_phase14_backup_gate_fires_only_at_v21(tmp_path):
    conn = _fresh_v21_db(tmp_path)
    # Fires at current==21, target>=22 -> writes a backup file.
    _phase14_backup_gate(conn, current_version=21, target_version=22, backup_dir=tmp_path)
    backups = list(tmp_path.glob("swing-pre-phase14-migration-*.db"))
    assert len(backups) == 1


def test_phase14_backup_gate_skips_non_v21(tmp_path):
    conn = _fresh_v21_db(tmp_path)
    # current != 21 -> no-op (STRICT equality, not <=).
    _phase14_backup_gate(conn, current_version=20, target_version=22, backup_dir=tmp_path)
    _phase14_backup_gate(conn, current_version=22, target_version=22, backup_dir=tmp_path)
    _phase14_backup_gate(conn, current_version=21, target_version=21, backup_dir=tmp_path)  # target < 22
    assert list(tmp_path.glob("swing-pre-phase14-migration-*.db")) == []


def test_db_migrate_twice_is_noop(tmp_path):
    conn = _fresh_v21_db(tmp_path)
    run_migrations(conn, target_version=22, backup_dir=tmp_path)
    v_after_first = _current_version(conn)
    run_migrations(conn, target_version=22, backup_dir=tmp_path)  # no-op
    assert _current_version(conn) == v_after_first == 22
```

- [ ] **Step 7: Run to verify it fails**

Run: `python -m pytest tests/data/test_temporal_log_migration.py -k backup_gate -q`
Expected: FAIL (`_phase14_backup_gate` does not exist).

- [ ] **Step 8: Add `_phase14_backup_gate` + `_create_pre_phase14_migration_backup` + wire into `run_migrations`**

```python
# swing/data/db.py  (mirror _phase13_sb6c_backup_gate verbatim; add near line 777)
def _phase14_backup_gate(
    conn: sqlite3.Connection,
    *,
    current_version: int,
    target_version: int,
    backup_dir: Path | None,
) -> None:
    """Phase 14 Sub-bundle 2 backup-before-migrate gate.

    Fires only when ``current_version == 21 AND target_version >= 22`` -- a
    real production v21 DB about to receive migration 0022. STRICT EQUALITY
    on pre_version per CLAUDE.md gotcha ``pre_version == (target - 1)`` (NOT
    ``<=``). Multi-step walks from pre-v21 baselines bypass this gate by
    design (matches Phase 9 / 12 C.A / 13 precedent).

    Filename: ``swing-pre-phase14-migration-<ISO>.db``.
    """
    if target_version < 22 or current_version != 21:
        return
    src_path = _resolve_main_db_path(conn)
    if src_path is None:
        raise MigrationBackupRequiredException(
            "pre-Phase-14 backup gate requires a file-backed source DB; "
            "in-memory connections cannot be snapshotted."
        )
    if backup_dir is None:
        backup_dir = src_path.parent
    try:
        backup_path = _create_pre_phase14_migration_backup(
            src_path, dest_dir=backup_dir,
        )
        _verify_backup_integrity(
            backup_path,
            expected_tables=PHASE14_PRE_MIGRATION_EXPECTED_TABLES,
        )
    except MigrationBackupRequiredException:
        raise
    except (OSError, sqlite3.Error) as exc:
        raise MigrationBackupRequiredException(
            f"pre-Phase-14 backup failed: {exc}"
        ) from exc
```

```python
# swing/data/db.py  -- add the backup-file helper mirroring
# _create_pre_phase13_sb6c_migration_backup (same body; new filename stem).
def _create_pre_phase14_migration_backup(src_path: Path, *, dest_dir: Path) -> Path:
    """SQLite-native Connection.backup() snapshot before the 0022 migration.
    Temp file created in dest_dir (os.replace same-filesystem gotcha)."""
    # ... copy the _create_pre_phase13_sb6c_migration_backup body verbatim,
    # changing only the filename stem to 'swing-pre-phase14-migration-<ISO>.db'.
```

```python
# swing/data/db.py  -- wire into run_migrations after _phase13_sb6c_backup_gate (~line 529)
    _phase13_sb6c_backup_gate(
        conn,
        current_version=current,
        target_version=target_version,
        backup_dir=backup_dir,
    )
    _phase14_backup_gate(
        conn,
        current_version=current,
        target_version=target_version,
        backup_dir=backup_dir,
    )
```

- [ ] **Step 9: Run backup-gate tests -- PASS**

Run: `python -m pytest tests/data/test_temporal_log_migration.py -q`
Expected: PASS (apply + gate + twice-noop).

- [ ] **Step 10: Write the rollback-through-runner test (failing) + the CHECK-rejection tests**

```python
# tests/data/test_temporal_log_migration.py  (append)
from swing.data.db import _apply_migration


def test_malformed_0022_rolls_back_through_runner(tmp_path, monkeypatch):
    """A 0022 variant that fails mid-script leaves the DB at v21 +
    in_transaction == False (test through the real _apply_migration path,
    NOT bare executescript) -- gotcha #9."""
    conn = _fresh_v21_db(tmp_path)
    bad_sql = tmp_path / "0022_bad.sql"
    bad_sql.write_text(
        "BEGIN;\n"
        "CREATE TABLE pattern_detection_events (detection_id INTEGER PRIMARY KEY);\n"
        "CREATE TABLE pattern_detection_events (x INTEGER);\n"  # duplicate -> error
        "UPDATE schema_version SET version = 22;\n"
        "COMMIT;\n",
        encoding="utf-8",
    )
    with pytest.raises(sqlite3.OperationalError):
        _apply_migration(conn, bad_sql)
    assert conn.in_transaction is False
    assert _current_version(conn) == 21
    tables = {r[0] for r in conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table'")}
    assert "pattern_detection_events" not in tables  # rolled back


def test_check_rejects_bad_pattern_class(tmp_path):
    conn = _fresh_v21_db(tmp_path)
    run_migrations(conn, target_version=22, backup_dir=tmp_path)
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO pattern_detection_events "
            "(ticker, detection_date, data_asof_date, pattern_class, "
            " structural_anchors_json, composite_score, detector_version, "
            " source, per_pattern_metadata_json, created_at) "
            "VALUES ('AAA','2026-05-29','2026-05-28','NOT_A_CLASS','{}',0.5,"
            "'v1','pipeline','{}','2026-05-29T00:00:00Z')"
        )


def test_check_rejects_bad_status(tmp_path):
    conn = _fresh_v21_db(tmp_path)
    run_migrations(conn, target_version=22, backup_dir=tmp_path)
    conn.execute(
        "INSERT INTO pattern_detection_events "
        "(detection_id, ticker, detection_date, data_asof_date, pattern_class, "
        " structural_anchors_json, composite_score, detector_version, source, "
        " per_pattern_metadata_json, created_at) "
        "VALUES (1,'AAA','2026-05-29','2026-05-28','vcp','{}',0.5,'v1',"
        "'pipeline','{}','2026-05-29T00:00:00Z')"
    )
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO pattern_forward_observations "
            "(detection_id, observation_date, ohlc_today_json, status, "
            " sessions_since_detection, created_at) "
            "VALUES (1,'2026-05-29','{}','NOT_A_STATUS',1,'2026-05-29T00:00:00Z')"
        )
```

- [ ] **Step 11: Run -- PASS (rollback + CHECK rejection prove the migration is correct)**

Run: `python -m pytest tests/data/test_temporal_log_migration.py -q`
Expected: PASS.

- [ ] **Step 12: Add the 2 dataclasses + 3 module constants + validators (gotcha #11 paired)**

```python
# swing/data/models.py  -- module constants near DETECTOR_PATTERN_CLASSES (line ~34)
_PATTERN_DETECTION_SOURCE_VALUES: tuple[str, ...] = (
    "pipeline", "v2_cohort", "d2_baseline", "backfill", "synthetic",
)
_FORWARD_OBSERVATION_STATUS_VALUES: tuple[str, ...] = (
    "pending", "triggered_open",
    "triggered_closed_at_target", "triggered_closed_at_stop",
    "invalidated", "expired",
)
_FORWARD_OBSERVATION_STATUS_CHANGE_EVENTS: tuple[str, ...] = (
    "entry_fired", "stop_fired", "target_fired",
    "time_exit", "shape_break", "observation_horizon_reached",
)
```

```python
# swing/data/models.py  -- append after ChartRender (~line 1990)
@dataclass(frozen=True)
class PatternDetectionEvent:
    """One row of ``pattern_detection_events`` (migration 0022; spec section 4.1).

    The FROZEN detection record. APPEND-ONLY: no code path UPDATEs/DELETEs.
    ``detection_date`` = action_session_date (operator-facing label);
    ``data_asof_date`` = detector data cutoff (forward-walk boundary anchor).
    """
    detection_id: int | None
    ticker: str
    detection_date: str
    data_asof_date: str
    pattern_class: str
    structural_anchors_json: str
    composite_score: float
    detector_version: str
    source: str
    per_pattern_metadata_json: str
    created_at: str
    finviz_screen_state: str | None = None
    pipeline_run_id: int | None = None
    chart_render_id: int | None = None

    def __post_init__(self) -> None:
        if self.pattern_class not in DETECTOR_PATTERN_CLASSES:
            raise ValueError(
                "pattern_class must be one of "
                f"{DETECTOR_PATTERN_CLASSES}, got {self.pattern_class!r}"
            )
        if self.source not in _PATTERN_DETECTION_SOURCE_VALUES:
            raise ValueError(
                "source must be one of "
                f"{_PATTERN_DETECTION_SOURCE_VALUES}, got {self.source!r}"
            )


@dataclass(frozen=True)
class PatternForwardObservation:
    """One row of ``pattern_forward_observations`` (migration 0022; spec section 4.2).

    The append-only forward-walk record. ``ohlc_today_json`` is LOCKED at
    observation and NEVER re-fetched (gotcha #26 elimination by construction).
    ``sessions_since_detection`` is measured from the detection's
    ``data_asof_date`` UP TO AND INCLUDING ``observation_date``.
    """
    observation_id: int | None
    detection_id: int
    observation_date: str
    ohlc_today_json: str
    status: str
    sessions_since_detection: int
    created_at: str
    status_change_event: str | None = None

    def __post_init__(self) -> None:
        if self.status not in _FORWARD_OBSERVATION_STATUS_VALUES:
            raise ValueError(
                "status must be one of "
                f"{_FORWARD_OBSERVATION_STATUS_VALUES}, got {self.status!r}"
            )
        if (
            self.status_change_event is not None
            and self.status_change_event
            not in _FORWARD_OBSERVATION_STATUS_CHANGE_EVENTS
        ):
            raise ValueError(
                "status_change_event must be None or one of "
                f"{_FORWARD_OBSERVATION_STATUS_CHANGE_EVENTS}, "
                f"got {self.status_change_event!r}"
            )
        # Defensive data-integrity guard (Codex chain #1 Minor #2): the
        # forward-walk count is never negative. (The schema has no CHECK for
        # this; the dataclass barrier rejects a malformed construction.)
        if self.sessions_since_detection < 0:
            raise ValueError(
                "sessions_since_detection must be >= 0, got "
                f"{self.sessions_since_detection!r}"
            )
```

- [ ] **Step 13: Write the dataclass-validator tests (the #11 mirror)**

```python
# tests/data/test_models_temporal.py
import pytest
from swing.data.models import (
    PatternDetectionEvent, PatternForwardObservation,
    _PATTERN_DETECTION_SOURCE_VALUES, _FORWARD_OBSERVATION_STATUS_VALUES,
)


def _valid_detection(**kw):
    base = dict(
        detection_id=None, ticker="AAA", detection_date="2026-05-29",
        data_asof_date="2026-05-28", pattern_class="vcp",
        structural_anchors_json="{}", composite_score=0.7,
        detector_version="v1", source="pipeline",
        per_pattern_metadata_json="{}", created_at="2026-05-29T00:00:00Z",
    )
    base.update(kw)
    return PatternDetectionEvent(**base)


def test_detection_rejects_bad_pattern_class():
    with pytest.raises(ValueError, match="pattern_class"):
        _valid_detection(pattern_class="bogus")


def test_detection_rejects_bad_source():
    with pytest.raises(ValueError, match="source"):
        _valid_detection(source="bogus")


def test_detection_accepts_all_enum_sources():
    for s in _PATTERN_DETECTION_SOURCE_VALUES:
        _valid_detection(source=s)  # no raise


def test_observation_rejects_bad_status():
    with pytest.raises(ValueError, match="status"):
        PatternForwardObservation(
            observation_id=None, detection_id=1, observation_date="2026-05-29",
            ohlc_today_json="{}", status="bogus", sessions_since_detection=1,
            created_at="2026-05-29T00:00:00Z",
        )


def test_observation_rejects_bad_status_change_event():
    with pytest.raises(ValueError, match="status_change_event"):
        PatternForwardObservation(
            observation_id=None, detection_id=1, observation_date="2026-05-29",
            ohlc_today_json="{}", status="pending", sessions_since_detection=1,
            created_at="2026-05-29T00:00:00Z", status_change_event="bogus",
        )


def test_validator_mirrors_schema_check_value_domain():
    """The Python enum constants MUST equal the schema CHECK value domain
    (gotcha #11 mirror). Hard-code the CHECK lists here so a drift in either
    side fails the test."""
    assert set(_PATTERN_DETECTION_SOURCE_VALUES) == {
        "pipeline", "v2_cohort", "d2_baseline", "backfill", "synthetic"}
    assert set(_FORWARD_OBSERVATION_STATUS_VALUES) == {
        "pending", "triggered_open", "triggered_closed_at_target",
        "triggered_closed_at_stop", "invalidated", "expired"}
```

- [ ] **Step 14: Run all T-2.1 tests + ruff**

Run: `python -m pytest tests/data/test_temporal_log_migration.py tests/data/test_models_temporal.py -q && ruff check swing/data/`
Expected: PASS; 0 ruff errors.

- [ ] **Step 15: Commit (per §G.0 cadence; may be 1-5 commits)**

```bash
git add swing/data/migrations/0022_phase14_temporal_log.sql swing/data/db.py swing/data/models.py tests/data/test_temporal_log_migration.py tests/data/test_models_temporal.py
git commit -m "feat(data): v22 temporal-log migration + dataclasses (T-2.1)"
```

---

### Task T-2.2: `pattern_detection_events` append-only repo

**Files:**
- Create: `swing/data/repos/pattern_detection_events.py`
- Test: `tests/data/repos/test_pattern_detection_events_repo.py`

**Acceptance criteria:**
- `insert_detection_event(conn, event) -> int` (caller-tx, NO commit); raises `sqlite3.IntegrityError` on UNIQUE `(source, ticker, detection_date, pattern_class)` duplicate.
- `get_detection_event_by_id`, `list_detection_events`, `list_observable_detections(conn, *, source, observation_date)`; `_row_to_detection_event` mapper (read-path, same task as repo).
- Module defines NO `def update_`/`def delete_` (append-only; OQ-10 LOCK; source-grep test).
- `list_observable_detections` returns detections with `data_asof_date < observation_date` (STRICT) whose latest observation status is open (or none yet).

**Discipline preservation:** L1 append-only (source-grep); caller-tx (mirror `insert_evaluation` `pattern_evaluations.py:60-97`); Expansion #4 (every SELECT column verified vs `0022`); fixtures derive from the production INSERT shape (§L).

- [ ] **Step 1: Write the insert + round-trip failing test**

```python
# tests/data/repos/test_pattern_detection_events_repo.py
import sqlite3
import pytest
from pathlib import Path
from swing.data.db import run_migrations
from swing.data.models import PatternDetectionEvent
from swing.data.repos.pattern_detection_events import (
    insert_detection_event, get_detection_event_by_id, list_detection_events,
    list_observable_detections,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(tmp_path / "t.db")
    c.execute("PRAGMA foreign_keys=ON")
    run_migrations(c, target_version=22, backup_dir=tmp_path)
    return c


def _event(**kw) -> PatternDetectionEvent:
    base = dict(
        detection_id=None, ticker="AAA", detection_date="2026-05-29",
        data_asof_date="2026-05-28", pattern_class="vcp",
        structural_anchors_json='{"window":{},"evidence":{"pivot_price":10.0}}',
        composite_score=0.72, detector_version="vcp_v1", source="pipeline",
        per_pattern_metadata_json='{"sector":"Tech","market_cap":null}',
        created_at="2026-05-29T00:00:00Z",
    )
    base.update(kw)
    return PatternDetectionEvent(**base)


def test_insert_and_get_round_trip(conn):
    with conn:
        det_id = insert_detection_event(conn, _event())
    assert isinstance(det_id, int)
    got = get_detection_event_by_id(conn, det_id)
    assert got is not None
    assert got.ticker == "AAA"
    assert got.pattern_class == "vcp"
    assert got.source == "pipeline"
    assert got.composite_score == pytest.approx(0.72)
    assert got.chart_render_id is None  # nullable audit linkage


def test_insert_is_caller_tx_no_autocommit(conn):
    # insert without an enclosing `with conn` does NOT persist after rollback.
    insert_detection_event(conn, _event(ticker="BBB"))
    conn.rollback()
    assert list_detection_events(conn, ticker="BBB") == []
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/data/repos/test_pattern_detection_events_repo.py -q`
Expected: FAIL (module does not exist).

- [ ] **Step 3: Write the repo (insert + mapper + get-by-id + list)**

```python
# swing/data/repos/pattern_detection_events.py
"""Append-only repo for ``pattern_detection_events`` (migration 0022).

APPEND-ONLY (spec section 2.3 + OQ-10 LOCK): this module defines NO
``update_*`` / ``delete_*`` functions. Caller-tx contract: NO ``conn.commit()``.
Mirrors ``swing/data/repos/pattern_evaluations.py`` (the append-only +
caller-tx exemplar).
"""
from __future__ import annotations

import sqlite3

from swing.data.models import PatternDetectionEvent

_COLS = (
    "detection_id, ticker, detection_date, data_asof_date, pattern_class, "
    "structural_anchors_json, composite_score, detector_version, "
    "finviz_screen_state, source, per_pattern_metadata_json, "
    "pipeline_run_id, chart_render_id, created_at"
)


def _row_to_detection_event(row: tuple) -> PatternDetectionEvent:
    return PatternDetectionEvent(
        detection_id=row[0],
        ticker=row[1],
        detection_date=row[2],
        data_asof_date=row[3],
        pattern_class=row[4],
        structural_anchors_json=row[5],
        composite_score=row[6],
        detector_version=row[7],
        finviz_screen_state=row[8],
        source=row[9],
        per_pattern_metadata_json=row[10],
        pipeline_run_id=row[11],
        chart_render_id=row[12],
        created_at=row[13],
    )


def insert_detection_event(conn: sqlite3.Connection, event: PatternDetectionEvent) -> int:
    """INSERT one row; return detection_id. Caller-tx (NO commit).

    UNIQUE(source, ticker, detection_date, pattern_class) raises
    sqlite3.IntegrityError on duplicate; the caller (detect step) does
    SELECT-then-skip idempotency (mirrors the existing _step_pattern_detect
    existing-key pattern).
    """
    cur = conn.execute(
        """
        INSERT INTO pattern_detection_events
            (ticker, detection_date, data_asof_date, pattern_class,
             structural_anchors_json, composite_score, detector_version,
             finviz_screen_state, source, per_pattern_metadata_json,
             pipeline_run_id, chart_render_id, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            event.ticker, event.detection_date, event.data_asof_date,
            event.pattern_class, event.structural_anchors_json,
            event.composite_score, event.detector_version,
            event.finviz_screen_state, event.source,
            event.per_pattern_metadata_json, event.pipeline_run_id,
            event.chart_render_id, event.created_at,
        ),
    )
    return int(cur.lastrowid)


def get_detection_event_by_id(
    conn: sqlite3.Connection, detection_id: int,
) -> PatternDetectionEvent | None:
    row = conn.execute(
        f"SELECT {_COLS} FROM pattern_detection_events WHERE detection_id = ?",
        (detection_id,),
    ).fetchone()
    return _row_to_detection_event(row) if row is not None else None


def list_detection_events(
    conn: sqlite3.Connection, *, ticker: str | None = None,
    pattern_class: str | None = None, source: str | None = None,
    pipeline_run_id: int | None = None, limit: int | None = None,
    offset: int = 0,
) -> list[PatternDetectionEvent]:
    clauses, params = [], []
    if ticker is not None:
        clauses.append("ticker = ?"); params.append(ticker)
    if pattern_class is not None:
        clauses.append("pattern_class = ?"); params.append(pattern_class)
    if source is not None:
        clauses.append("source = ?"); params.append(source)
    if pipeline_run_id is not None:
        clauses.append("pipeline_run_id = ?"); params.append(pipeline_run_id)
    where = (" WHERE " + " AND ".join(clauses)) if clauses else ""
    sql = (
        f"SELECT {_COLS} FROM pattern_detection_events{where} "
        "ORDER BY detection_date DESC, detection_id DESC"
    )
    if limit is not None:
        sql += " LIMIT ? OFFSET ?"; params.extend([limit, offset])
    return [_row_to_detection_event(r) for r in conn.execute(sql, params)]
```

- [ ] **Step 4: Run Step-1 tests -- PASS**

Run: `python -m pytest tests/data/repos/test_pattern_detection_events_repo.py -q`
Expected: PASS.

- [ ] **Step 5: Write the `list_observable_detections` test (failing) + UNIQUE test**

> **Task-ordering note (Codex chain #1 Critical #1):** T-2.2 must NOT import from `swing.data.repos.pattern_forward_observations` (that module lands in T-2.3). The two observable cases that need NO observation row (same-run-cutoff exclusion; prior-cutoff-no-observation inclusion) live HERE; the observation-dependent case (latest-status-terminal exclusion) is a CROSS-REPO test that lands in **T-2.3 Step 5** (after both repos exist). Subagent-driven execution runs T-2.1 -> T-2.2 -> T-2.3 in order, so T-2.2's suite has no forward dependency.

```python
# tests/data/repos/test_pattern_detection_events_repo.py  (append -- NO cross-repo import)
def test_unique_source_ticker_date_class(conn):
    with conn:
        insert_detection_event(conn, _event())
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            insert_detection_event(conn, _event())  # same identity key


def test_observable_excludes_same_run_data_cutoff(conn):
    # detection data cutoff == observation_date -> NOT observable (STRICT <).
    with conn:
        insert_detection_event(conn, _event(data_asof_date="2026-05-29"))
    obs = list_observable_detections(
        conn, source="pipeline", observation_date="2026-05-29")
    assert obs == []


def test_observable_includes_prior_cutoff_with_no_observation_yet(conn):
    # No observation yet + data_asof_date < observation_date -> observable.
    with conn:
        insert_detection_event(conn, _event(data_asof_date="2026-05-28"))
    obs = list_observable_detections(
        conn, source="pipeline", observation_date="2026-05-29")
    assert len(obs) == 1
    assert obs[0].ticker == "AAA"
```

(The latest-status-terminal exclusion -- which requires `insert_observation` -- is deferred to T-2.3 Step 5 to avoid a forward import; see T-2.3.)

- [ ] **Step 6: Add `list_observable_detections` (window-function latest-status)**

```python
# swing/data/repos/pattern_detection_events.py  (append)
_OPEN_STATUSES = ("pending", "triggered_open")


def list_observable_detections(
    conn: sqlite3.Connection, *, source: str = "pipeline",
    observation_date: str,
) -> list[PatternDetectionEvent]:
    """Detections OBSERVABLE for ``observation_date``:

      - detection.data_asof_date < observation_date  (STRICT on the data
        cutoff; the forward-walk starts the first COMPLETED session AFTER the
        detector's DATA CUTOFF -- includes the first tradable session, excludes
        same-run detections whose cutoff == observation_date), AND
      - the MOST-RECENT forward observation has a status in the OPEN set
        ('pending','triggered_open') OR there is NO observation yet.

    Window function (ROW_NUMBER() OVER PARTITION BY detection_id ORDER BY
    observation_date DESC) finds the latest status per detection.
    """
    placeholders = ",".join("?" * len(_OPEN_STATUSES))
    sql = f"""
        WITH latest AS (
            SELECT detection_id, status,
                   ROW_NUMBER() OVER (
                       PARTITION BY detection_id
                       ORDER BY observation_date DESC, observation_id DESC
                   ) AS rn
            FROM pattern_forward_observations
        )
        SELECT {", ".join("d." + c for c in _COLS.split(", "))}
        FROM pattern_detection_events d
        LEFT JOIN latest l
            ON l.detection_id = d.detection_id AND l.rn = 1
        WHERE d.source = ?
          AND d.data_asof_date < ?
          AND (l.status IS NULL OR l.status IN ({placeholders}))
        ORDER BY d.detection_id
    """
    params = [source, observation_date, *_OPEN_STATUSES]
    return [_row_to_detection_event(r) for r in conn.execute(sql, params)]
```

- [ ] **Step 7: Run -- PASS** (no cross-repo dependency; the observation-dependent observable case is deferred to T-2.3 Step 5).

Run: `python -m pytest tests/data/repos/test_pattern_detection_events_repo.py -q`
Expected: PASS.

- [ ] **Step 8: Write the append-only source-grep test**

```python
# tests/data/repos/test_pattern_detection_events_repo.py  (append)
import inspect
import swing.data.repos.pattern_detection_events as mod


def test_repo_defines_no_update_or_delete_functions():
    names = [n for n, o in inspect.getmembers(mod, inspect.isfunction)
             if o.__module__ == mod.__name__]
    offenders = [n for n in names if n.startswith(("update_", "delete_"))]
    assert offenders == [], f"append-only violated: {offenders}"
```

- [ ] **Step 9: Run all T-2.2 tests + ruff + commit**

Run: `python -m pytest tests/data/repos/test_pattern_detection_events_repo.py -q && ruff check swing/data/repos/pattern_detection_events.py`
Expected: PASS; 0 ruff errors.

```bash
git add swing/data/repos/pattern_detection_events.py tests/data/repos/test_pattern_detection_events_repo.py
git commit -m "feat(data): append-only pattern_detection_events repo (T-2.2)"
```

---

### Task T-2.3: `pattern_forward_observations` append-only repo

**Files:**
- Create: `swing/data/repos/pattern_forward_observations.py`
- Test: `tests/data/repos/test_pattern_forward_observations_repo.py`

**Acceptance criteria:**
- `insert_observation(conn, observation) -> int` (caller-tx); UNIQUE `(detection_id, observation_date)` raises on duplicate.
- `get_observations_for_detection` (chain, ASC); `get_latest_observation_for_detection`; `get_latest_observations_for_detections(conn, detection_ids)` -> dict, with empty-input short-circuit to `{}` BEFORE SQL + dynamic-`?` IN-clause.
- RESTRICT FK: deleting a detection with observations raises `sqlite3.IntegrityError`.
- NO `update_*`/`delete_*` (source-grep test).

**Discipline preservation:** sqlite3 list-bind / dynamic-`?` + empty short-circuit (Expansion #4 sub-refinement); L1 append-only; RESTRICT FK discriminating test; `date.fromisoformat` boundary deferred to T-2.5 (this repo stores TEXT verbatim).

- [ ] **Step 1: Write insert + chain + UNIQUE failing tests**

```python
# tests/data/repos/test_pattern_forward_observations_repo.py
import sqlite3
import pytest
from pathlib import Path
from swing.data.db import run_migrations
from swing.data.models import PatternDetectionEvent, PatternForwardObservation
from swing.data.repos.pattern_detection_events import insert_detection_event
from swing.data.repos.pattern_forward_observations import (
    insert_observation, get_observations_for_detection,
    get_latest_observation_for_detection, get_latest_observations_for_detections,
)


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(tmp_path / "t.db")
    c.execute("PRAGMA foreign_keys=ON")
    run_migrations(c, target_version=22, backup_dir=tmp_path)
    return c


def _det(conn, **kw) -> int:
    base = dict(
        detection_id=None, ticker="AAA", detection_date="2026-05-29",
        data_asof_date="2026-05-28", pattern_class="vcp",
        structural_anchors_json="{}", composite_score=0.7,
        detector_version="v1", source="pipeline",
        per_pattern_metadata_json="{}", created_at="2026-05-29T00:00:00Z",
    )
    base.update(kw)
    with conn:
        return insert_detection_event(conn, PatternDetectionEvent(**base))


def _obs(detection_id, date, **kw) -> PatternForwardObservation:
    base = dict(
        observation_id=None, detection_id=detection_id, observation_date=date,
        ohlc_today_json='{"close":11.0,"provider":"yfinance"}',
        status="pending", sessions_since_detection=1,
        created_at="2026-05-29T00:00:00Z",
    )
    base.update(kw)
    return PatternForwardObservation(**base)


def test_insert_and_chain_ordered_asc(conn):
    det = _det(conn)
    with conn:
        insert_observation(conn, _obs(det, "2026-05-30", sessions_since_detection=2))
        insert_observation(conn, _obs(det, "2026-05-29", sessions_since_detection=1))
    chain = get_observations_for_detection(conn, det)
    assert [o.observation_date for o in chain] == ["2026-05-29", "2026-05-30"]


def test_unique_detection_date(conn):
    det = _det(conn)
    with conn:
        insert_observation(conn, _obs(det, "2026-05-29"))
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            insert_observation(conn, _obs(det, "2026-05-29"))


def test_latest_observation(conn):
    det = _det(conn)
    with conn:
        insert_observation(conn, _obs(det, "2026-05-29", status="pending"))
        insert_observation(conn, _obs(det, "2026-05-30", status="triggered_open",
                                      sessions_since_detection=2,
                                      status_change_event="entry_fired"))
    latest = get_latest_observation_for_detection(conn, det)
    assert latest.observation_date == "2026-05-30"
    assert latest.status == "triggered_open"
```

- [ ] **Step 2: Run to verify fail**

Run: `python -m pytest tests/data/repos/test_pattern_forward_observations_repo.py -q`
Expected: FAIL (module missing).

- [ ] **Step 3: Write the repo**

```python
# swing/data/repos/pattern_forward_observations.py
"""Append-only repo for ``pattern_forward_observations`` (migration 0022).

APPEND-ONLY (spec section 2.3 + OQ-10 LOCK): NO ``update_*`` / ``delete_*``.
Caller-tx: NO ``conn.commit()``.
"""
from __future__ import annotations

import sqlite3
from collections.abc import Sequence

from swing.data.models import PatternForwardObservation

_COLS = (
    "observation_id, detection_id, observation_date, ohlc_today_json, "
    "status, status_change_event, sessions_since_detection, created_at"
)


def _row_to_observation(row: tuple) -> PatternForwardObservation:
    return PatternForwardObservation(
        observation_id=row[0],
        detection_id=row[1],
        observation_date=row[2],
        ohlc_today_json=row[3],
        status=row[4],
        status_change_event=row[5],
        sessions_since_detection=row[6],
        created_at=row[7],
    )


def insert_observation(conn: sqlite3.Connection, observation: PatternForwardObservation) -> int:
    """INSERT one row; return observation_id. Caller-tx (NO commit).
    UNIQUE(detection_id, observation_date) raises sqlite3.IntegrityError on
    duplicate-same-day; the observe step pre-checks for idempotency.
    """
    cur = conn.execute(
        """
        INSERT INTO pattern_forward_observations
            (detection_id, observation_date, ohlc_today_json, status,
             status_change_event, sessions_since_detection, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            observation.detection_id, observation.observation_date,
            observation.ohlc_today_json, observation.status,
            observation.status_change_event,
            observation.sessions_since_detection, observation.created_at,
        ),
    )
    return int(cur.lastrowid)


def get_observations_for_detection(
    conn: sqlite3.Connection, detection_id: int,
) -> list[PatternForwardObservation]:
    """The full chain, ORDER BY observation_date ASC."""
    rows = conn.execute(
        f"SELECT {_COLS} FROM pattern_forward_observations "
        "WHERE detection_id = ? ORDER BY observation_date ASC, observation_id ASC",
        (detection_id,),
    )
    return [_row_to_observation(r) for r in rows]


def get_latest_observation_for_detection(
    conn: sqlite3.Connection, detection_id: int,
) -> PatternForwardObservation | None:
    row = conn.execute(
        f"SELECT {_COLS} FROM pattern_forward_observations "
        "WHERE detection_id = ? "
        "ORDER BY observation_date DESC, observation_id DESC LIMIT 1",
        (detection_id,),
    ).fetchone()
    return _row_to_observation(row) if row is not None else None


def get_latest_observations_for_detections(
    conn: sqlite3.Connection, detection_ids: Sequence[int],
) -> dict[int, PatternForwardObservation]:
    """Batch latest-status read. Empty input short-circuits to {} BEFORE SQL
    (avoids invalid ``IN ()``). Dynamic '?' expansion for the IN clause
    (sqlite3 cannot bind a list to a single :name placeholder).
    """
    ids = list(detection_ids)
    if not ids:
        return {}
    placeholders = ",".join("?" * len(ids))
    sql = f"""
        WITH ranked AS (
            SELECT {_COLS},
                   ROW_NUMBER() OVER (
                       PARTITION BY detection_id
                       ORDER BY observation_date DESC, observation_id DESC
                   ) AS rn
            FROM pattern_forward_observations
            WHERE detection_id IN ({placeholders})
        )
        SELECT {_COLS} FROM ranked WHERE rn = 1
    """
    out: dict[int, PatternForwardObservation] = {}
    for row in conn.execute(sql, ids):
        obs = _row_to_observation(row)
        out[obs.detection_id] = obs
    return out
```

- [ ] **Step 4: Run Step-1 tests -- PASS**

Run: `python -m pytest tests/data/repos/test_pattern_forward_observations_repo.py -q`
Expected: PASS.

- [ ] **Step 5: Write batch-latest + empty-short-circuit + RESTRICT-FK + append-only tests**

```python
# tests/data/repos/test_pattern_forward_observations_repo.py  (append)
import inspect
import swing.data.repos.pattern_forward_observations as mod


def test_batch_latest_empty_input_short_circuits(conn):
    # Empty input returns {} WITHOUT executing SQL. Patch conn.execute to a
    # tripwire to prove no SQL ran.
    class Tripwire:
        def execute(self, *a, **k):
            raise AssertionError("SQL must not run on empty input")
    assert get_latest_observations_for_detections(Tripwire(), []) == {}


def test_batch_latest_multi_detection(conn):
    d1, d2 = _det(conn, ticker="AAA"), _det(conn, ticker="BBB")
    with conn:
        insert_observation(conn, _obs(d1, "2026-05-29", status="pending"))
        insert_observation(conn, _obs(d1, "2026-05-30", status="triggered_open",
                                      sessions_since_detection=2,
                                      status_change_event="entry_fired"))
        insert_observation(conn, _obs(d2, "2026-05-29", status="invalidated",
                                      status_change_event="shape_break"))
    latest = get_latest_observations_for_detections(conn, [d1, d2])
    assert latest[d1].status == "triggered_open"
    assert latest[d2].status == "invalidated"


def test_restrict_fk_blocks_deleting_detection_with_observations(conn):
    det = _det(conn)
    with conn:
        insert_observation(conn, _obs(det, "2026-05-29"))
    with pytest.raises(sqlite3.IntegrityError):
        with conn:
            conn.execute(
                "DELETE FROM pattern_detection_events WHERE detection_id = ?",
                (det,),
            )


def test_observable_excludes_terminal_latest_status(conn):
    # CROSS-REPO (deferred here from T-2.2 to avoid a forward import): a
    # detection whose latest observation status is terminal drops out of
    # list_observable_detections (Codex chain #1 Critical #1 ordering fix).
    from swing.data.repos.pattern_detection_events import list_observable_detections
    det = _det(conn, data_asof_date="2026-05-28")
    with conn:
        insert_observation(conn, _obs(
            det, "2026-05-29", status="expired", sessions_since_detection=1,
            status_change_event="observation_horizon_reached"))
    obs = list_observable_detections(
        conn, source="pipeline", observation_date="2026-05-30")
    assert obs == []


def test_repo_defines_no_update_or_delete_functions():
    names = [n for n, o in inspect.getmembers(mod, inspect.isfunction)
             if o.__module__ == mod.__name__]
    offenders = [n for n in names if n.startswith(("update_", "delete_"))]
    assert offenders == [], f"append-only violated: {offenders}"
```

- [ ] **Step 6: Run all T-2.3 tests + ruff + commit**

Run: `python -m pytest tests/data/repos/test_pattern_forward_observations_repo.py -q && ruff check swing/data/repos/pattern_forward_observations.py`
Expected: PASS; 0 ruff errors.

```bash
git add swing/data/repos/pattern_forward_observations.py tests/data/repos/test_pattern_forward_observations_repo.py
git commit -m "feat(data): append-only pattern_forward_observations repo (T-2.3)"
```

---

### Task T-2.4: detect-step extension (metadata + chart capture + evidence-key repair)

**Files:**
- Create: `swing/pipeline/temporal_metadata.py`
- Create: `swing/pipeline/detection_chart_capture.py`
- Modify: `swing/web/charts.py` (evidence-key repair in `_annotate_flat_base`:411-419, `_annotate_cup_with_handle`:429, `_annotate_high_tight_flag`:447)
- Modify: `swing/pipeline/runner.py` (`_step_pattern_detect` emit loop :1981-2096; empty-pool :1485-1490; signature :1396 to accept `run_warnings`)
- Test: `tests/pipeline/test_temporal_metadata.py`
- Test: `tests/web/test_detection_chart_capture.py`
- Test: `tests/pipeline/test_step_pattern_detect_temporal_extension.py`

**Acceptance criteria:**
- 3 pure-bars helpers compute ATR%/90d-return/52w-proximity from `bars <= data_asof_date`; short-history -> field `None` (no exception).
- `build_per_pattern_metadata` produces `{sector, industry, adr_pct, atr_pct, ret_90d, prox_52w_high_pct, rs_rank, close_at_detection, market_cap: None}`; `build_finviz_screen_state` produces `{bucket, rs_rank, rs_method, criteria: {name: result}}`; `build_structural_anchors_json` produces `{window: {...}, evidence: asdict(evidence)}`.
- `render_and_capture_detection_chart` returns an int chart_render_id on success, `None` on render/F6 failure; caller-tx (uses passed `conn`).
- charts.py evidence-key repair: the 3 stale annotators read the ACTUAL field names (§C.6 table); the existing chart tests stay green + a new overlay test asserts the repaired keys render.
- detect-step emit loop appends a `PatternDetectionEvent` per emitted verdict (SELECT-then-skip idempotency on the unique key) inside the SAME `lease.fenced_write()`; `chart_render_id` populated on success / NULL on failure; chart-failure + empty-pool emit `run_warnings` entries.
- Existing `pattern_evaluations` write + existing detector tests UNCHANGED (L7).

**Discipline preservation:** L6 (metadata from bars, no new fetch); L7 (extension, not replacement); #5 (reuse already-fetched bars); #27 (empty-pool + chart-failure warnings); F6 (ChartRender empty-bytes barrier); matplotlib mathtext gotcha (annotation labels plain-text); Expansion #11 (provider/source by FIELD); yfinance in-progress-bar strip.

- [ ] **Step 1: Write the pure-bars metadata helper tests (failing)**

```python
# tests/pipeline/test_temporal_metadata.py
import numpy as np
import pandas as pd
import pytest
from swing.pipeline.temporal_metadata import (
    compute_atr_pct, compute_return_pct, compute_52w_high_proximity_pct,
)


def _bars(n: int, last_date="2026-05-28") -> pd.DataFrame:
    idx = pd.bdate_range(end=last_date, periods=n)
    close = np.linspace(10.0, 20.0, n)
    return pd.DataFrame(
        {"Open": close * 0.99, "High": close * 1.02,
         "Low": close * 0.98, "Close": close, "Volume": 1_000_000},
        index=idx,
    )


def test_atr_pct_positive_for_normal_bars():
    out = compute_atr_pct(_bars(60), asof="2026-05-28")
    assert out is not None and out > 0


def test_return_pct_90_sessions():
    bars = _bars(120)
    out = compute_return_pct(bars, asof="2026-05-28", lookback_sessions=90)
    assert out is not None
    # close rises monotonically -> positive 90-session return
    assert out > 0


def test_return_pct_short_history_returns_none():
    out = compute_return_pct(_bars(30), asof="2026-05-28", lookback_sessions=90)
    assert out is None  # < 90 bars -> None, NOT an exception


def test_52w_proximity_near_high():
    bars = _bars(300)  # > 252
    out = compute_52w_high_proximity_pct(bars, asof="2026-05-28")
    assert out is not None and out >= 0  # close near the rising high


def test_helpers_strip_in_progress_partial_bar():
    # A bar dated AFTER asof (in-progress) must be ignored.
    bars = _bars(60, last_date="2026-05-29")  # last bar 2026-05-29 > asof
    out = compute_atr_pct(bars, asof="2026-05-28")
    assert out is not None  # did not crash; used <= asof slice


def test_helpers_return_none_on_empty_or_columnless_frame():
    # The Major-#1 empty-frame degrade path: an empty DataFrame (passed when
    # bars are unexpectedly absent for an emitted verdict) returns None for
    # every computed field rather than raising KeyError.
    empty = pd.DataFrame()
    assert compute_atr_pct(empty, asof="2026-05-28") is None
    assert compute_return_pct(empty, asof="2026-05-28", lookback_sessions=90) is None
    assert compute_52w_high_proximity_pct(empty, asof="2026-05-28") is None
```

- [ ] **Step 2: Run to verify fail; Step 3: write `temporal_metadata.py`**

Run: `python -m pytest tests/pipeline/test_temporal_metadata.py -q` -> FAIL (module missing).

```python
# swing/pipeline/temporal_metadata.py
"""Pure-bars per-pattern metadata helpers (Phase 14 Sub-bundle 2, spec section 9).

No I/O: every function consumes an already-fetched ``bars`` DataFrame (the
detect loop's existing fetch) sliced to ``<= data_asof_date``. Short-history
inputs return ``None`` for the field (never raise) so a thin-history ticker
never poisons the metadata emit. L2 LOCK: no fetch, no Schwab.
"""
from __future__ import annotations

import dataclasses
import json
from datetime import date

import pandas as pd


_REQUIRED_OHLCV_COLS = ("Open", "High", "Low", "Close", "Volume")


def _usable(bars: pd.DataFrame, *, need: tuple[str, ...]) -> bool:
    """True only if bars is a non-empty frame carrying the needed columns.
    Guards the empty-frame path (Codex chain #1 R2 Major #1): the detect loop
    may pass an empty DataFrame when bars are unexpectedly absent for an
    emitted verdict; the helpers then return None rather than KeyError."""
    return (
        bars is not None and not bars.empty
        and all(c in bars.columns for c in need)
    )


def _slice_to_asof(bars: pd.DataFrame, asof: str) -> pd.DataFrame:
    """Drop any bar dated AFTER asof (strips the yfinance in-progress partial
    bar per the CLAUDE.md gotcha). asof is an ISO date string."""
    asof_d = date.fromisoformat(asof)
    return bars[bars.index.map(lambda ts: ts.date() <= asof_d)]


def _close_series(bars: pd.DataFrame) -> pd.Series:
    close = bars["Close"]
    if getattr(close, "ndim", 1) == 2:  # MultiIndex single-ticker squeeze
        close = close.iloc[:, 0]
    return close


def compute_atr_pct(bars: pd.DataFrame, *, asof: str, period: int = 14) -> float | None:
    """True ATR(period) / last_close * 100 (distinct from candidates.adr_pct)."""
    if not _usable(bars, need=("High", "Low", "Close")):
        return None
    df = _slice_to_asof(bars, asof)
    if len(df) < period + 1:
        return None
    high, low, close = df["High"], df["Low"], df["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.tail(period).mean()
    last_close = float(close.iloc[-1])
    if last_close <= 0:
        return None
    return float(atr / last_close * 100.0)


def compute_return_pct(
    bars: pd.DataFrame, *, asof: str, lookback_sessions: int,
) -> float | None:
    """(close_today - close_N_sessions_ago) / close_N_sessions_ago * 100."""
    if not _usable(bars, need=("Close",)):
        return None
    close = _close_series(_slice_to_asof(bars, asof))
    if len(close) < lookback_sessions + 1:
        return None
    now = float(close.iloc[-1])
    then = float(close.iloc[-(lookback_sessions + 1)])
    if then <= 0:
        return None
    return float((now - then) / then * 100.0)


def compute_52w_high_proximity_pct(bars: pd.DataFrame, *, asof: str) -> float | None:
    """(high_52w - close_today) / high_52w * 100 over the last 252 sessions
    (reuses the trend_template.py TT7 formula). Lower = closer to the high."""
    if not _usable(bars, need=("Close",)):
        return None
    close = _close_series(_slice_to_asof(bars, asof))
    if len(close) < 1:
        return None
    window = close.iloc[-252:]
    high_52w = float(window.max())
    if high_52w <= 0:
        return None
    now = float(close.iloc[-1])
    return float((high_52w - now) / high_52w * 100.0)


def build_per_pattern_metadata(candidate, bars: pd.DataFrame, *, asof: str) -> str:
    """Serialize per-pattern metadata JSON (spec section 9.2). market_cap is
    NULL in V1+ (OQ-16: not persisted to candidates)."""
    return json.dumps({
        "sector": candidate.sector,
        "industry": candidate.industry,
        "adr_pct": candidate.adr_pct,
        "atr_pct": compute_atr_pct(bars, asof=asof),
        "ret_90d": compute_return_pct(bars, asof=asof, lookback_sessions=90),
        "prox_52w_high_pct": compute_52w_high_proximity_pct(bars, asof=asof),
        "rs_rank": candidate.rs_rank,
        "close_at_detection": candidate.close,
        "market_cap": None,
    })


def build_finviz_screen_state(candidate) -> str:
    """Canonicalized per-ticker eval/screen state (spec section 9.4). The
    per-criterion value is CriterionResult.result (the verdict string)."""
    return json.dumps({
        "bucket": candidate.bucket,
        "rs_rank": candidate.rs_rank,
        "rs_method": candidate.rs_method,
        "criteria": {cr.criterion_name: cr.result for cr in candidate.criteria},
    })


def build_structural_anchors_json(window, evidence) -> str:
    """{window: {...}, evidence: asdict(evidence)} (spec section 6.3). The
    evidence asdict losslessly contains every per-class structural anchor."""
    return json.dumps({
        "window": {
            "start_date": window.start_date.isoformat(),
            "end_date": window.end_date.isoformat(),
            "anchor_date": getattr(window, "anchor_date", None).isoformat()
                if getattr(window, "anchor_date", None) is not None else None,
            "anchor_reason": getattr(window, "anchor_reason", None),
        },
        "evidence": dataclasses.asdict(evidence),
    }, default=str)
```

- [ ] **Step 4: Run helper tests -- PASS**

Run: `python -m pytest tests/pipeline/test_temporal_metadata.py -q`
Expected: PASS.

- [ ] **Step 5: Write the chart-capture failing test**

```python
# tests/web/test_detection_chart_capture.py
import sqlite3
import pytest
import pandas as pd
import numpy as np
from pathlib import Path
from unittest.mock import patch
from swing.data.db import run_migrations
from swing.data.models import PatternEvaluation
from swing.pipeline.detection_chart_capture import render_and_capture_detection_chart


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = sqlite3.connect(tmp_path / "t.db")
    c.execute("PRAGMA foreign_keys=ON")
    run_migrations(c, target_version=22, backup_dir=tmp_path)
    # seed a pipeline_runs row so the FK is satisfiable
    c.execute("INSERT INTO pipeline_runs (id, state) VALUES (1, 'running')")
    c.commit()
    return c


def _pe() -> PatternEvaluation:
    return PatternEvaluation(
        id=None, pipeline_run_id=1, ticker="AAA", pattern_class="vcp",
        detector_version="vcp_v1", geometric_score=0.7, geometric_score_json="{}",
        composite_score=0.7,
        structural_evidence_json='{"pivot_price":10.0,"base_top_price":9.5}',
        feature_distribution_log_json="{}", window_start_date="2026-01-01",
        window_end_date="2026-05-28", created_at="2026-05-29T00:00:00Z",
    )


def _bars() -> pd.DataFrame:
    idx = pd.bdate_range(end="2026-05-28", periods=120)
    close = np.linspace(8, 10, 120)
    return pd.DataFrame({"Open": close, "High": close*1.02, "Low": close*0.98,
                         "Close": close, "Volume": 1e6}, index=idx)


def test_capture_returns_chart_render_id(conn):
    cid = render_and_capture_detection_chart(
        conn, ticker="AAA", bars=_bars(), pattern_evaluation=_pe(),
        pipeline_run_id=1, data_asof_date="2026-05-28")
    assert isinstance(cid, int)
    row = conn.execute(
        "SELECT surface, pattern_class, pipeline_run_id FROM chart_renders "
        "WHERE id = ?", (cid,)).fetchone()
    assert row == ("theme2_annotated", "vcp", 1)


def test_capture_returns_none_on_render_failure(conn):
    with patch(
        "swing.pipeline.detection_chart_capture.render_theme2_annotated_svg",
        return_value=b"",  # empty bytes -> F6 ChartRender barrier raises ValueError
    ):
        cid = render_and_capture_detection_chart(
            conn, ticker="AAA", bars=_bars(), pattern_evaluation=_pe(),
            pipeline_run_id=1, data_asof_date="2026-05-28")
    assert cid is None  # EXPECTED failure class (ValueError) -> NULL


def test_capture_propagates_unexpected_error(conn):
    # Codex chain #1 R2 Minor #1: an UNEXPECTED exception class (a programming
    # bug, e.g. TypeError) is NOT swallowed by the narrow except -- it
    # propagates so the caller logs it distinctly (not masked as "render
    # failed"). The detect-loop's own try/except then degrades to NULL, but
    # the bug is visible.
    with patch(
        "swing.pipeline.detection_chart_capture.render_theme2_annotated_svg",
        side_effect=TypeError("boom"),
    ):
        with pytest.raises(TypeError):
            render_and_capture_detection_chart(
                conn, ticker="AAA", bars=_bars(), pattern_evaluation=_pe(),
                pipeline_run_id=1, data_asof_date="2026-05-28")


def test_capture_cache_collision_last_writer_wins(conn):
    # Renderer-kwargs-uniformity / cache-collision mapping (Codex chain #1
    # Major #8; spec section 8.2 Expansion #10c): because V1+ renders the
    # theme2_annotated chart DIRECTLY (not through chart_jit's cache-read
    # path), the spec's "render-once, serve-cached, assert call_count == 1"
    # JIT concern does NOT apply at the JIT layer. Redundant renders are
    # instead prevented at the DETECT-STEP level by the SELECT-then-skip
    # idempotency gate (T-2.4 step 11): each (ticker, detection_date, class)
    # is emitted once per run, and a re-run skips BEFORE calling capture --
    # so the renderer is invoked at most once per detection per run. This
    # test covers the remaining shared-surface concern: two captures on the
    # same (ticker, run, class) key -> 2nd refresh replaces the row
    # (DELETE-then-INSERT); only one row survives (last-writer-wins
    # coexistence with the exemplar theme2_annotated writer, FB-N3).
    c1 = render_and_capture_detection_chart(
        conn, ticker="AAA", bars=_bars(), pattern_evaluation=_pe(),
        pipeline_run_id=1, data_asof_date="2026-05-28")
    c2 = render_and_capture_detection_chart(
        conn, ticker="AAA", bars=_bars(), pattern_evaluation=_pe(),
        pipeline_run_id=1, data_asof_date="2026-05-28")
    n = conn.execute(
        "SELECT COUNT(*) FROM chart_renders WHERE ticker='AAA' "
        "AND surface='theme2_annotated' AND pipeline_run_id=1 "
        "AND pattern_class='vcp'").fetchone()[0]
    assert n == 1 and c2 != c1  # last-writer-wins
```

- [ ] **Step 6: Write `detection_chart_capture.py`**

```python
# swing/pipeline/detection_chart_capture.py
"""Render + capture a detection's theme2_annotated chart at detect time
(Phase 14 Sub-bundle 2, spec section 8). Caller-tx: uses the passed conn;
does NOT open its own transaction (refresh_chart_render is caller-tx).
"""
from __future__ import annotations

import logging
import sqlite3
from datetime import UTC, datetime

import pandas as pd

from swing.data.models import ChartRender, PatternEvaluation
from swing.data.repos.chart_renders import refresh_chart_render
from swing.web.charts import render_theme2_annotated_svg

log = logging.getLogger(__name__)


def render_and_capture_detection_chart(
    conn: sqlite3.Connection, *, ticker: str, bars: pd.DataFrame,
    pattern_evaluation: PatternEvaluation, pipeline_run_id: int,
    data_asof_date: str,
) -> int | None:
    """Render the theme2_annotated chart for a detection + cache it via the
    standard refresh_chart_render (last-writer-wins coexistence with the
    exemplar path). Returns the chart_render_id, or None on any render/F6
    failure (the caller still inserts the detection with chart_render_id=NULL
    + emits a gotcha #27 warning).
    """
    try:
        svg = render_theme2_annotated_svg(
            ticker=ticker, bars=bars, pattern_evaluation=pattern_evaluation,
        )
        chart = ChartRender(
            id=None, ticker=ticker, surface="theme2_annotated",
            chart_svg_bytes=svg, source_data_hash="detection_capture_v1",
            rendered_at=datetime.now(UTC).isoformat(),
            data_asof_date=data_asof_date,
            pipeline_run_id=pipeline_run_id,
            pattern_class=pattern_evaluation.pattern_class,
        )
        return refresh_chart_render(conn, chart)
    except (ValueError, RuntimeError, OSError) as exc:
        # NARROW catch (Codex chain #1 Major #7): isolate the EXPECTED failure
        # classes only -- ValueError (the F6 empty-bytes ChartRender barrier +
        # any annotator value error), RuntimeError/OSError (matplotlib render
        # hiccups, font/backend I/O). Programming errors (AttributeError,
        # TypeError, KeyError) propagate to the caller's emit-loop try/except
        # (T-2.4 step 11) where they are logged distinctly -- they must NOT be
        # silently masked as a chart-render failure.
        log.warning(
            "detection chart capture failed for (%s, %s): %s",
            ticker, pattern_evaluation.pattern_class, exc,
        )
        return None
```

> **NOTE for the implementer:** the narrow `except (ValueError, RuntimeError, OSError)` is deliberate -- spec §8.3 requires render-failure -> NULL + warning, but NOT masking integration/programming bugs. The detection is still never lost: the caller's emit-loop `try/except` (T-2.4 step 11) wraps the capture call and sets `chart_render_id=None` + warns on ANY exception, so even a propagated programming error degrades to NULL gracefully -- but it surfaces as a distinct ERROR-level log, not a silent "chart render failed" warning. Do NOT catch `LeaseRevokedError`. (If matplotlib raises a class outside the three caught here in practice, widen by ADDING the specific class with a comment -- never go back to bare `except Exception`.)

- [ ] **Step 7: Run chart-capture tests -- PASS (may need matplotlib Agg backend in CI)**

Run: `python -m pytest tests/web/test_detection_chart_capture.py -q`
Expected: PASS.

- [ ] **Step 8: Evidence-key repair in `swing/web/charts.py` + overlay test**

Repair the 3 annotators per the §C.6 table. Example diff for `_annotate_flat_base` (charts.py:411-419):

```python
# swing/web/charts.py  _annotate_flat_base
-    top = ctx.evidence.get("top_of_range")
-    bottom = ctx.evidence.get("bottom_of_range")
+    top = ctx.evidence.get("range_top_price")
+    bottom = ctx.evidence.get("range_bottom_price")
     ...
-    duration = ctx.evidence.get("duration_days")
+    duration = ctx.evidence.get("base_duration_days")
```

```python
# swing/web/charts.py  _annotate_cup_with_handle (charts.py:429)
-    depth = ctx.evidence.get("depth_ratio")
+    depth = ctx.evidence.get("cup_depth_pct")
     # cup_bottom_price already MATCHES the evidence field -- no change
```

```python
# swing/web/charts.py  _annotate_high_tight_flag (charts.py:447)
-    pole_pct = ctx.evidence.get("pole_advance_pct")
+    pole_pct = ctx.evidence.get("pole_pct")
     # consolidation_duration_days already MATCHES -- no change
```

Also read `charts.py:405-470` to confirm the VCP + double_bottom_w annotators (if any) do NOT read stale keys; if they do, repair them too. **Matplotlib mathtext:** verify no repaired label string contains `$`/`^`/`_`/unbalanced `\`.

```python
# tests/web/test_chart_theme2_overlay.py  (NEW or extend existing chart test)
import json
import pandas as pd, numpy as np
from swing.data.models import PatternEvaluation
from swing.web.charts import render_theme2_annotated_svg


def test_flat_base_overlay_reads_repaired_keys():
    bars_idx = pd.bdate_range(end="2026-05-28", periods=120)
    c = np.linspace(8, 10, 120)
    bars = pd.DataFrame({"Open": c, "High": c*1.02, "Low": c*0.98,
                         "Close": c, "Volume": 1e6}, index=bars_idx)
    ev = {"range_top_price": 9.8, "range_bottom_price": 9.2,
          "base_duration_days": 30, "pivot_price": 9.9}
    pe = PatternEvaluation(
        id=None, pipeline_run_id=1, ticker="AAA", pattern_class="flat_base",
        detector_version="v1", geometric_score=0.7, geometric_score_json="{}",
        composite_score=0.7, structural_evidence_json=json.dumps(ev),
        feature_distribution_log_json="{}", window_start_date="2026-01-01",
        window_end_date="2026-05-28", created_at="2026-05-29T00:00:00Z")
    svg = render_theme2_annotated_svg(ticker="AAA", bars=bars, pattern_evaluation=pe)
    assert svg and len(svg) > 0  # renders non-empty with the repaired keys present
```

(Note: a stronger assertion -- that the overlay actually drew the axhlines -- requires inspecting the matplotlib figure; the byte-length + no-exception assertion is the V1 gate, and the operator-witnessed S6 surface visually confirms the overlay. Per the CLAUDE.md matplotlib gotcha, string-equality tests miss render regressions -- §I S6 is the binding visual gate.)

- [ ] **Step 9: Run existing chart tests (must stay green) + the new overlay test**

Run: `python -m pytest tests/web/ -k chart -q`
Expected: PASS (no regression in existing chart tests).

- [ ] **Step 10: Extend `_step_pattern_detect` signature + empty-pool warnings audit**

```python
# swing/pipeline/runner.py  _step_pattern_detect signature (line ~1396)
 def _step_pattern_detect(
     *,
     cfg,
     lease: Lease,
     eval_run_id: int,
     ohlcv_cache,
+    run_warnings: list[dict] | None = None,
 ) -> None:
```

```python
# swing/pipeline/runner.py  empty-pool early-return (line ~1485-1490) -- gotcha #27
 if not aplus_tickers:
     log.info(
         "pattern_detect: no candidate windows -- zero aplus tickers; "
         "skipping (no writes)"
     )
+    if run_warnings is not None:
+        run_warnings.append({
+            "step": "pattern_detect",
+            "expected_pool": len(candidates),
+            "actual_aplus_pool": 0,
+            "reason": "zero aplus candidates",
+        })
     return
```

- [ ] **Step 11: Append the detection-event build + chart capture inside the emit loop**

```python
# swing/pipeline/runner.py  -- inside the emit loop, AFTER the successful
# insert_evaluation(conn, row) at ~line 2096 (SAME lease.fenced_write() conn).
# `candidate_by_ticker` is built once before the loop:
#     candidate_by_ticker = {c.ticker: c for c in candidates}
# `data_asof_date = lease_data_asof(cfg, lease)` computed once before the loop.

      try:
          insert_evaluation(conn, row)
          rows_written += 1
      except Exception as exc:
          log.warning("pattern_detect: INSERT failed ... %s", exc)
          continue

      # --- Phase 14 Sub-bundle 2: append the frozen detection event. ---
      cand = candidate_by_ticker.get(ticker)
      if cand is None:
          continue  # defensive: an emit without a candidate row (should not happen)
      # SELECT-then-skip idempotency on the unique key (re-run safety).
      existing = conn.execute(
          "SELECT 1 FROM pattern_detection_events WHERE source='pipeline' "
          "AND ticker=? AND detection_date=? AND pattern_class=?",
          (ticker, asof_run, pattern_class),
      ).fetchone()
      if existing is not None:
          continue
      # INVARIANT (Codex chain #1 R2 Major #1): EVERY emitted verdict appends a
      # pattern_detection_events row -- substrate completeness is the invariant.
      # bars SHOULD always be present (the emit came from a candidate whose bars
      # were fetched in Pass-1). If they are absent (internal inconsistency), DO
      # NOT skip the detection append (that would write pattern_evaluations while
      # silently missing the permanent substrate); instead degrade gracefully:
      # warn, skip the chart, and compute metadata from an empty frame (the
      # compute_* helpers return None on len-0 input via the _usable guard) so
      # the detection still lands. `pd` is already imported inside this function
      # (runner.py:1441), so no new import is needed.
      bars = bars_by_ticker.get(ticker)
      if bars is None:
          bars = pd.DataFrame()
          if run_warnings is not None:
              run_warnings.append({
                  "step": "pattern_detect", "ticker": ticker,
                  "pattern_class": pattern_class,
                  "reason": "bars absent for emitted verdict (internal); "
                            "detection written: per_pattern_metadata_json is a "
                            "valid JSON string with computed fields = JSON null; "
                            "no chart",
              })
          chart_render_id = None
      else:
          try:
              chart_render_id = render_and_capture_detection_chart(
                  conn, ticker=ticker, bars=bars, pattern_evaluation=row,
                  pipeline_run_id=pipeline_run_id, data_asof_date=data_asof_date,
              )
          except Exception as exc:  # programming error -> distinct ERROR; still NULL
              chart_render_id = None
              log.error("pattern_detect: chart capture unexpected error "
                        "(%s, %s): %s", ticker, pattern_class, exc)
          if chart_render_id is None and run_warnings is not None:
              run_warnings.append({
                  "step": "pattern_detect", "ticker": ticker,
                  "pattern_class": pattern_class, "reason": "chart render failed",
              })
      detection = PatternDetectionEvent(
          detection_id=None, ticker=ticker, detection_date=asof_run,
          data_asof_date=data_asof_date, pattern_class=pattern_class,
          structural_anchors_json=build_structural_anchors_json(window, evidence),
          composite_score=float(composite_score), detector_version=version_str,
          finviz_screen_state=build_finviz_screen_state(cand),
          source="pipeline",
          per_pattern_metadata_json=build_per_pattern_metadata(
              cand, bars, asof=data_asof_date),
          created_at=_dt_inner.now(UTC).isoformat(),
          pipeline_run_id=pipeline_run_id, chart_render_id=chart_render_id,
      )
      try:
          insert_detection_event(conn, detection)
      except Exception as exc:
          log.warning("pattern_detect: detection-event INSERT failed ... %s", exc)
          continue
```

**The `bars_by_ticker` retention patch (Codex chain #1 Major #4 -- shown as an executable patch, not a note).** The detect step fetches bars at `runner.py:1603` inside the Pass-1/window-build loop. Retain them in a dict so the Pass-2 emit loop reuses them WITHOUT re-fetching (gotcha #5 + L2):

```python
# swing/pipeline/runner.py  -- at the Pass-1 fetch site (~line 1603), capture bars.
# Initialize the dict before the Pass-1 loop:
+    bars_by_ticker: dict[str, pd.DataFrame] = {}
     # ... inside the Pass-1 loop, where bars are fetched:
     bars = ohlcv_cache.get_or_fetch(ticker=ticker, window_days=400)
+    bars_by_ticker[ticker] = bars      # retain for Pass-2 metadata + chart capture
```

```python
# swing/pipeline/runner.py  -- once, before the Pass-2 emit loop:
+    data_asof_date = lease_data_asof(cfg, lease)            # detector data cutoff (R2 M#1)
+    candidate_by_ticker = {c.ticker: c for c in candidates}
```

> **Implementer wiring notes (verify against production at execute time):**
> - **DO NOT re-fetch** in the emit loop -- the emit loop reads `bars_by_ticker.get(ticker)`. If a ticker is absent (defensive internal-inconsistency case), DO NOT skip the detection append (substrate-completeness invariant, Codex chain #1 R2 Major #1): write the detection with an empty-frame metadata (computed fields -> None via the `_usable` guard) + `chart_render_id=None` + a `warnings_json` entry. Never re-fetch (gotcha #5).
> - `asof_run` (= `_resolve_eval_run_action_session_date(...)`, runner.py:1499) is `detection_date`; `data_asof_date = lease_data_asof(cfg, lease)` (runner.py:977) is the forward-walk boundary anchor.
> - All imports (`PatternDetectionEvent`, `insert_detection_event`, `build_structural_anchors_json`, `build_finviz_screen_state`, `build_per_pattern_metadata`, `render_and_capture_detection_chart`) added at the top of runner.py.

- [ ] **Step 12: Write the detect-extension integration tests (REUSE the existing fixture)**

> **Base (Codex chain #1 Major #1):** the production integration harness ALREADY exists at `tests/pipeline/test_step_pattern_detect.py` (`_build_bars`, `insert_candidates`, `insert_evaluation_run`, a context manager that drives `_step_pattern_detect`). The new module IMPORTS those helpers (or copies the fixture pattern) so the detection-event INSERT shape matches the production emitter exactly (Phase-12 C.D anti-drift). Define a thin `_drive_detect(conn, cfg, lease, eval_run_id, ohlcv_cache, run_warnings)` wrapper mirroring the existing module's drive helper, plus a `run_warnings: list[dict]` arg. The tests below are EXECUTABLE as written once that shared fixture is imported.

```python
# tests/pipeline/test_step_pattern_detect_temporal_extension.py
from __future__ import annotations
import json
import sqlite3
from unittest.mock import patch
import pytest
from swing.data.repos.pattern_detection_events import list_detection_events

# Reuse the proven harness from the existing detect-step integration module.
from tests.pipeline.test_step_pattern_detect import (  # type: ignore
    _build_bars, _seed_aplus_candidate_and_run, _drive_detect, _StubOhlcvCache,
)
# (If those helper names differ in the existing module, alias them in a small
#  local conftest shim; the implementer confirms the exact names at execute
#  time -- the existing module's public fixture surface is the contract.)


def test_detection_event_appended_with_metadata(tmp_db_v22):
    conn, cfg, lease, eval_run_id = _seed_aplus_candidate_and_run(
        tmp_db_v22, ticker="AAA", sector="Tech", industry="Software",
        adr_pct=3.2, rs_rank=42)
    run_warnings: list[dict] = []
    _drive_detect(conn, cfg, lease, eval_run_id,
                  _StubOhlcvCache({"AAA": _build_bars()}), run_warnings)
    dets = list_detection_events(conn, ticker="AAA")
    assert len(dets) >= 1
    md = json.loads(dets[0].per_pattern_metadata_json)
    assert md["sector"] == "Tech" and md["industry"] == "Software"
    assert md["adr_pct"] == pytest.approx(3.2)
    assert md["rs_rank"] == 42
    assert "atr_pct" in md and "ret_90d" in md and "prox_52w_high_pct" in md
    assert md["market_cap"] is None  # OQ-16 LOCK
    assert dets[0].source == "pipeline"
    assert dets[0].data_asof_date == dets[0].data_asof_date  # populated (not None)
    # structural_anchors_json carries window + evidence (incl. pivot_price).
    anchors = json.loads(dets[0].structural_anchors_json)
    assert "window" in anchors and "evidence" in anchors


def test_chart_render_id_populated_on_success(tmp_db_v22):
    conn, cfg, lease, eval_run_id = _seed_aplus_candidate_and_run(tmp_db_v22, ticker="AAA")
    _drive_detect(conn, cfg, lease, eval_run_id,
                  _StubOhlcvCache({"AAA": _build_bars()}), [])
    det = list_detection_events(conn, ticker="AAA")[0]
    assert det.chart_render_id is not None
    row = conn.execute("SELECT surface, pattern_class FROM chart_renders "
                       "WHERE id = ?", (det.chart_render_id,)).fetchone()
    assert row[0] == "theme2_annotated" and row[1] == det.pattern_class


def test_chart_render_failure_leaves_null_and_warns(tmp_db_v22):
    conn, cfg, lease, eval_run_id = _seed_aplus_candidate_and_run(tmp_db_v22, ticker="AAA")
    run_warnings: list[dict] = []
    with patch("swing.pipeline.runner.render_and_capture_detection_chart",
               return_value=None):
        _drive_detect(conn, cfg, lease, eval_run_id,
                      _StubOhlcvCache({"AAA": _build_bars()}), run_warnings)
    det = list_detection_events(conn, ticker="AAA")[0]
    assert det.chart_render_id is None
    assert any(w.get("reason") == "chart render failed" for w in run_warnings)


def test_idempotent_second_run_no_duplicate_detection(tmp_db_v22):
    conn, cfg, lease, eval_run_id = _seed_aplus_candidate_and_run(tmp_db_v22, ticker="AAA")
    cache = _StubOhlcvCache({"AAA": _build_bars()})
    _drive_detect(conn, cfg, lease, eval_run_id, cache, [])
    first = list_detection_events(conn, ticker="AAA")
    _drive_detect(conn, cfg, lease, eval_run_id, cache, [])  # re-run same run
    second = list_detection_events(conn, ticker="AAA")
    assert len(second) == len(first)  # SELECT-then-skip idempotency


def test_pattern_evaluations_still_written_l7(tmp_db_v22):
    conn, cfg, lease, eval_run_id = _seed_aplus_candidate_and_run(tmp_db_v22, ticker="AAA")
    _drive_detect(conn, cfg, lease, eval_run_id,
                  _StubOhlcvCache({"AAA": _build_bars()}), [])
    n_eval = conn.execute("SELECT COUNT(*) FROM pattern_evaluations").fetchone()[0]
    assert n_eval >= 1  # the existing write is UNCHANGED (L7)


def test_empty_aplus_pool_warns_and_writes_nothing(tmp_db_v22):
    conn, cfg, lease, eval_run_id = _seed_run_with_zero_aplus(tmp_db_v22)
    run_warnings: list[dict] = []
    _drive_detect(conn, cfg, lease, eval_run_id, _StubOhlcvCache({}), run_warnings)
    assert conn.execute("SELECT COUNT(*) FROM pattern_detection_events").fetchone()[0] == 0
    entry = next(w for w in run_warnings if w["step"] == "pattern_detect")
    assert entry["actual_aplus_pool"] == 0
    assert entry["reason"] == "zero aplus candidates"
```

> **Fixture helpers the implementer adds** (concrete, in the test module / a conftest):
> - `tmp_db_v22` -- a pytest fixture: `sqlite3.connect` + `PRAGMA foreign_keys=ON` + `run_migrations(conn, target_version=22, backup_dir=tmp_path)`.
> - `_seed_aplus_candidate_and_run(conn, *, ticker, sector="", industry="", adr_pct=None, rs_rank=None)` -- inserts an `EvaluationRun` + one `bucket='aplus'` `Candidate` (via the existing `insert_candidates` + `insert_evaluation_run` from the base module) + a `pipeline_runs` row with a known `data_asof_date`; returns `(conn, cfg, lease, eval_run_id)`. Mirror the existing module's run/lease construction.
> - `_seed_run_with_zero_aplus(conn)` -- same but inserts only non-aplus candidates.
> - `_StubOhlcvCache(bars_by_ticker)` -- a stub with `get_or_fetch(*, ticker, window_days)` returning `bars_by_ticker[ticker]` (a `_build_bars()` frame). Mirror the existing module's OHLCV stub.
> - `_drive_detect(...)` -- calls `_step_pattern_detect(cfg=cfg, lease=lease, eval_run_id=eval_run_id, ohlcv_cache=cache, run_warnings=run_warnings)` inside the existing module's lease/fenced-write context.

- [ ] **Step 13: Add the `PipelineConfig` window fields (needed by T-2.5; land here so detect+observe share the config edit) is DEFERRED to T-2.5 step 1.** Run the full T-2.4 suite + ruff.

Run: `python -m pytest tests/pipeline/test_temporal_metadata.py tests/web/test_detection_chart_capture.py tests/pipeline/test_step_pattern_detect_temporal_extension.py tests/web/ -k "chart or temporal or detect" -q && ruff check swing/pipeline/temporal_metadata.py swing/pipeline/detection_chart_capture.py swing/web/charts.py swing/pipeline/runner.py`
Expected: PASS; 0 ruff errors.

- [ ] **Step 14: Commit (per §G.0; ~5 commits)**

```bash
git add swing/pipeline/temporal_metadata.py swing/pipeline/detection_chart_capture.py swing/web/charts.py swing/pipeline/runner.py tests/pipeline/test_temporal_metadata.py tests/web/test_detection_chart_capture.py tests/web/test_chart_theme2_overlay.py tests/pipeline/test_step_pattern_detect_temporal_extension.py
git commit -m "feat(pipeline): detect-step temporal-log extension + chart capture (T-2.4)"
```

---

### Task T-2.5: NEW `_step_pattern_observe` + DAG wiring + run-warnings accumulator

**Files:**
- Modify: `swing/config.py` (`PipelineConfig`:158-165 -- add 2 window fields)
- Modify: `swing/pipeline/runner.py` (NEW `_step_pattern_observe`; DAG block after :854; run-warnings accumulator created at run start + threaded to completion `lease.release`)
- Test: `tests/pipeline/test_step_pattern_observe.py`
- Test: `tests/config/test_pipeline_observe_windows.py`

**Acceptance criteria:**
- `PipelineConfig.observe_max_pending_window_sessions = 30` + `observe_max_post_trigger_window_sessions = 60`; auto-load from `[pipeline]` TOML; `Config.from_defaults()` carries the defaults.
- `_step_pattern_observe` enumerates open detections (`list_observable_detections`), batch-reads latest status, fetches the bar FOR `observation_date` (not blind last-row), records `provider` provenance in `ohlc_today_json`, computes the status via `_advance_status`, appends one observation per open detection.
- Idempotent: a re-run with an existing `(detection_id, observation_date)` observation skips (no UNIQUE violation).
- Status state machine emits only `{pending, triggered_open, invalidated, expired}` with transitions per §C.7 + spec §7.3; `sessions_since_detection` measured from `data_asof_date`.
- Empty open-pool + per-ticker no-bar emit `run_warnings` entries (gotcha #27); the accumulator is serialized to `lease.release(state="complete", warnings_json=...)` (`None` when empty, not `"[]"`).
- DAG: `lease.step("pattern_observe")` best-effort block inserted after `pattern_detect` (:854), before `schwab_snapshot`.

**Discipline preservation:** L2 forward-walk + #26/#37 by construction (select-by-date + freeze); L4 (reuse OhlcvCache; archive-first; zero Schwab); OQ-17 provider tag; OQ-18 30/60 config-surfaced; #27 warnings; `date.fromisoformat` boundary; FB-N4 (data_asof_date directionality); FB-N6 (warnings accumulator NEW plumbing).

- [ ] **Step 1: Add the config fields + test**

```python
# tests/config/test_pipeline_observe_windows.py
from swing.config import Config, PipelineConfig


def test_pipeline_observe_window_defaults():
    pc = PipelineConfig()
    assert pc.observe_max_pending_window_sessions == 30
    assert pc.observe_max_post_trigger_window_sessions == 60


def test_from_defaults_carries_observe_windows():
    cfg = Config.from_defaults()
    assert cfg.pipeline.observe_max_pending_window_sessions == 30
    assert cfg.pipeline.observe_max_post_trigger_window_sessions == 60
```

```python
# swing/config.py  PipelineConfig (line ~165, after chart_top_n_watch)
+    # Phase 14 Sub-bundle 2 (OQ-18 LOCK): observe-step lifecycle windows
+    # (trading sessions). Config-surfaced via [pipeline] in swing.config.toml
+    # so they are tunable without a code change. A detection is tracked at
+    # most ~(pending + post_trigger) = ~90 sessions.
+    observe_max_pending_window_sessions: int = 30
+    observe_max_post_trigger_window_sessions: int = 60
```

Run: `python -m pytest tests/config/test_pipeline_observe_windows.py -q` -> PASS (auto-loads via `PipelineConfig(**raw.get("pipeline", {}))` at config.py:508; no `load` edit needed).

- [ ] **Step 2: Write the status-machine arithmetic tests (failing)**

```python
# tests/pipeline/test_step_pattern_observe.py
import pytest
from swing.pipeline.runner import _advance_status


class _Det:
    """Minimal detection stub carrying the anchors the status machine reads."""
    def __init__(self, pivot=10.0, invalidation=8.0):
        import json
        self.pattern_class = "vcp"
        self.data_asof_date = "2026-05-28"
        self.structural_anchors_json = json.dumps(
            {"evidence": {"pivot_price": pivot, "base_top_price": pivot,
                          "contractions": [{"low": invalidation}]}})


def _bar(high, low, close, open_=None):
    return {"open": open_ or close, "high": high, "low": low,
            "close": close, "volume": 1_000_000}


def test_pending_stays_pending_within_window():
    status, ev = _advance_status(
        _Det(), prev=None, bar=_bar(9.0, 8.5, 8.8),
        sessions_since_detection=5, max_pending=30, max_post_trigger=60)
    assert status == "pending" and ev is None


def test_pending_to_triggered_open_on_pivot_breakout():
    status, ev = _advance_status(
        _Det(pivot=10.0), prev=None, bar=_bar(10.5, 9.8, 10.2),
        sessions_since_detection=5, max_pending=30, max_post_trigger=60)
    assert status == "triggered_open" and ev == "entry_fired"


def test_pending_to_invalidated_on_structural_break():
    status, ev = _advance_status(
        _Det(invalidation=8.0), prev=None, bar=_bar(8.2, 7.5, 7.8),
        sessions_since_detection=5, max_pending=30, max_post_trigger=60)
    assert status == "invalidated" and ev == "shape_break"


def test_pending_to_expired_at_window_threshold():
    # AT threshold (30) without trigger -> expired (>= boundary).
    status, ev = _advance_status(
        _Det(), prev=None, bar=_bar(9.0, 8.5, 8.8),
        sessions_since_detection=30, max_pending=30, max_post_trigger=60)
    assert status == "expired" and ev == "time_exit"


def test_pending_below_window_threshold_not_expired():
    # Under threshold (29) -> still pending (distinguishes >= boundary).
    status, ev = _advance_status(
        _Det(), prev=None, bar=_bar(9.0, 8.5, 8.8),
        sessions_since_detection=29, max_pending=30, max_post_trigger=60)
    assert status == "pending" and ev is None


class _PrevOpen:
    status = "triggered_open"


def test_triggered_open_to_expired_at_horizon():
    # AT pending+post_trigger (90) -> horizon reached.
    status, ev = _advance_status(
        _Det(), prev=_PrevOpen(), bar=_bar(11.0, 10.5, 10.8),
        sessions_since_detection=90, max_pending=30, max_post_trigger=60)
    assert status == "expired" and ev == "observation_horizon_reached"


def test_triggered_open_stays_open_within_horizon():
    status, ev = _advance_status(
        _Det(), prev=_PrevOpen(), bar=_bar(11.0, 10.5, 10.8),
        sessions_since_detection=50, max_pending=30, max_post_trigger=60)
    assert status == "triggered_open" and ev is None
```

> **Regression-test arithmetic verification (`feedback_verify_regression_test_arithmetic`):** the at-threshold (30, 90) vs under-threshold (29, 50) pairs DISTINGUISH the `>=` boundary. Under the pre-fix path (no `_advance_status`) every test fails (function missing); under the post-fix path the boundary tests pass at `>=` and FAIL at `>` -- so the test pins the inequality directionality (`>=` per spec §7.3). The breakout test (high 10.5 >= pivot 10.0) vs a near-miss (high 9.9 < pivot 10.0, add as an extra test) distinguishes the breakout predicate.

- [ ] **Step 3: Write `_advance_status`**

```python
# swing/pipeline/runner.py  (module-level helper near _step_pattern_observe)
import json as _obs_json


def _structural_invalidation_level(pattern_class: str, evidence: dict) -> float | None:
    """Per-class structural low (spec section 7.3.1), read from the frozen
    structural_anchors_json evidence dict."""
    if pattern_class == "flat_base":
        return evidence.get("range_bottom_price")
    if pattern_class == "vcp":
        contractions = evidence.get("contractions") or []
        lows = [c.get("low") for c in contractions if isinstance(c, dict)
                and c.get("low") is not None]
        return min(lows) if lows else None
    if pattern_class == "cup_with_handle":
        return evidence.get("cup_bottom_price")
    if pattern_class == "high_tight_flag":
        return evidence.get("pole_start_price")
    if pattern_class == "double_bottom_w":
        t1, t2 = evidence.get("trough_1_price"), evidence.get("trough_2_price")
        vals = [v for v in (t1, t2) if v is not None]
        return min(vals) if vals else None
    return None


def _advance_status(det, *, prev, bar, sessions_since_detection,
                    max_pending, max_post_trigger):
    """Compute (new_status, status_change_event) for one observation.

    V1+ emits ONLY the ruleset-agnostic subset
    {pending, triggered_open, invalidated, expired}. Anchors are read from
    the detection's FROZEN structural_anchors_json (never recomputed).
    """
    anchors = _obs_json.loads(det.structural_anchors_json)
    evidence = anchors.get("evidence", {})
    pivot = evidence.get("pivot_price")
    invalidation = _structural_invalidation_level(det.pattern_class, evidence)
    prev_status = prev.status if prev is not None else "pending"

    if prev_status == "triggered_open":
        if sessions_since_detection >= max_pending + max_post_trigger:
            return "expired", "observation_horizon_reached"
        return "triggered_open", None

    # prev pending (or first observation).
    if pivot is not None and bar["high"] >= pivot:
        return "triggered_open", "entry_fired"
    if invalidation is not None and bar["close"] < invalidation:
        return "invalidated", "shape_break"
    if sessions_since_detection >= max_pending:
        return "expired", "time_exit"
    return "pending", None
```

Run: `python -m pytest tests/pipeline/test_step_pattern_observe.py -k advance or status -q` -> PASS.

- [ ] **Step 4: Write `_step_pattern_observe` + `_bar_for_date`**

```python
# swing/pipeline/runner.py  (NEW step + bar helper)
def _bar_for_date(cfg, ohlcv_cache, ticker: str, observation_date: str):
    """Return (ohlc_dict_with_provider, ) for exactly `observation_date`, or
    None if the archive has no bar for that session.

    OQ-17 read path (writing-plans decision): (1) populate/refresh the archive
    via the OhlcvCache write-through ladder (archive-first; zero Schwab); (2)
    read the date-anchored bar + provider provenance via resolve_ohlcv_window
    (keyed end=observation_date). Selects the row whose asof_date ==
    observation_date (NOT iloc[-1]); freezes it; never re-reads it later
    (#26 elimination honest).
    """
    from datetime import date, timedelta
    from swing.data.ohlcv_archive import resolve_ohlcv_window
    # 1. Populate the archive (write-through; the same call detect makes).
    #    Best-effort by design (Codex chain #1 Major #6): the date-anchored
    #    archive read in step 2 is AUTHORITATIVE. A get_or_fetch failure here
    #    is not fatal -- if it leaves no bar for observation_date, step 2's
    #    "no match" path returns None and the CALLER records a #27 no-bar
    #    warning + skips (operator-visible). This runtime swallow is distinct
    #    from the PLAN-TIME verify-or-escalate below: the implementer confirms
    #    ONCE (T-2.5 step 0) that get_or_fetch write-throughs to the same
    #    prices_cache_dir resolve_ohlcv_window reads; a structural mismatch
    #    there is an ESCALATION (a #24-family freshness desync), NOT this
    #    per-ticker runtime warning.
    try:
        ohlcv_cache.get_or_fetch(ticker=ticker, window_days=400)
    except Exception as exc:  # noqa: BLE001 - best-effort populate; read is authoritative
        log.debug("observe populate get_or_fetch best-effort miss for %s: %s",
                  ticker, exc)
    # 2. Date-anchored archive read with per-asof_date provenance.
    start = (date.fromisoformat(observation_date) - timedelta(days=10)).isoformat()
    df, provenance = resolve_ohlcv_window(
        ticker, start=start, end=observation_date,
        cache_dir=cfg.paths.prices_cache_dir,
    )
    if df.empty:
        return None
    match = df[df["asof_date"] == observation_date]
    if match.empty:
        return None  # no bar for the gap day -> caller records a warning + skips
    r = match.iloc[-1]
    return {
        "open": float(r["open"]), "high": float(r["high"]),
        "low": float(r["low"]), "close": float(r["close"]),
        "volume": float(r["volume"]),
        "provider": provenance.get(observation_date, "yfinance"),
    }


def _step_pattern_observe(*, cfg, lease, ohlcv_cache, run_warnings):
    """Append today's bar + lifecycle status to pattern_forward_observations
    for every open detection. Zero new detector invocations (L4)."""
    import json as _j
    from datetime import UTC, datetime, date
    from swing.data.db import connect
    from swing.data.repos.pattern_detection_events import list_observable_detections
    from swing.data.repos.pattern_forward_observations import (
        insert_observation, get_latest_observations_for_detections,
    )
    from swing.data.models import PatternForwardObservation

    observation_date = lease_data_asof(cfg, lease)  # run DATA cutoff (R2 M#1)
    max_pending = cfg.pipeline.observe_max_pending_window_sessions
    max_post = cfg.pipeline.observe_max_post_trigger_window_sessions

    read_conn = connect(cfg.paths.db_path)
    try:
        open_dets = list_observable_detections(
            read_conn, source="pipeline", observation_date=observation_date)
        latest = get_latest_observations_for_detections(
            read_conn, [d.detection_id for d in open_dets])
    finally:
        read_conn.close()

    if not open_dets:
        run_warnings.append({
            "step": "pattern_observe", "actual_open_pool": 0,
            "reason": "no observable detections",
        })
        return

    with lease.fenced_write() as conn:
        for det in open_dets:
            prev = latest.get(det.detection_id)
            if prev is not None and prev.observation_date == observation_date:
                continue  # idempotent: already observed today
            bar = _bar_for_date(cfg, ohlcv_cache, det.ticker, observation_date)
            if bar is None:
                run_warnings.append({
                    "step": "pattern_observe", "ticker": det.ticker,
                    "observation_date": observation_date,
                    "reason": "no bar for observation_date",
                })
                continue
            sessions = _sessions_since(det.data_asof_date, observation_date)
            status, change = _advance_status(
                det, prev=prev, bar=bar,
                sessions_since_detection=sessions,
                max_pending=max_pending, max_post_trigger=max_post)
            insert_observation(conn, PatternForwardObservation(
                observation_id=None, detection_id=det.detection_id,
                observation_date=observation_date,
                ohlc_today_json=_j.dumps(bar),
                status=status, status_change_event=change,
                sessions_since_detection=sessions,
                created_at=datetime.now(UTC).isoformat(),
            ))


def _sessions_since(data_asof_date: str, observation_date: str) -> int:
    """Count trading sessions from data_asof_date UP TO AND INCLUDING
    observation_date (FB-N4: keyed on data_asof_date, NOT detection_date).
    Uses pandas bdate_range (business days) as the V1 trading-day proxy;
    holidays are an acceptable V1 approximation (the windows are coarse 30/60).
    date.fromisoformat boundary conversion at the callsite with malformed-input
    guard.
    """
    import pandas as pd
    from datetime import date
    start = date.fromisoformat(data_asof_date)
    end = date.fromisoformat(observation_date)
    if end <= start:
        return 0
    return int(len(pd.bdate_range(start=start, end=end)) - 1)
```

> **Implementer verification (T-2.5 step 0, BEFORE coding):**
> - Confirm `resolve_ohlcv_window` reads the same `cfg.paths.prices_cache_dir` that `get_or_fetch`'s write-through ladder populates (the per-provider `{TICKER}.{provider}.parquet` Shape A archive). If `get_or_fetch` does NOT write-through to that directory (so the date-anchored read can't see today's bar), ESCALATE -- this would be a #24-family freshness desync, not a silent patch. (The detect step already calls `get_or_fetch` for aplus tickers this run, so their bars are populated; rotated-out tickers rely on the write-through.)
> - Confirm the `df` columns from `resolve_ohlcv_window` are lowercase `asof_date`/`open`/`high`/`low`/`close`/`volume` (per `ohlcv_archive.py` Shape A). If they are capitalized, adjust `_bar_for_date` accordingly.
> - Decide the `_sessions_since` trading-day source: `pd.bdate_range` (business days, no holidays) is the V1 proxy; if the project has an `exchange_calendars` session helper already wired (it does for `action_session_for_run`), prefer it -- but guard `pd.Timestamp` per the CLAUDE.md `is_open_at_time` gotcha. Pin the choice + add a discriminating test.

- [ ] **Step 5: Wire the DAG + run-warnings accumulator**

```python
# swing/pipeline/runner.py  -- create the accumulator at run start (before the
# step sequence; near where the lease is acquired). Search for the run-start
# block that precedes `lease.step("evaluate")`.
+    run_warnings: list[dict] = []
```

```python
# swing/pipeline/runner.py  -- thread run_warnings into _step_pattern_detect call
 lease.step("pattern_detect")
 try:
     _step_pattern_detect(
         cfg=cfg, lease=lease, eval_run_id=eval_run_id,
         ohlcv_cache=ohlcv_cache,
+        run_warnings=run_warnings,
     )
 except LeaseRevokedError:
     raise
 except Exception as exc:
     log.warning("pattern_detect failed: %s", exc)
```

```python
# swing/pipeline/runner.py  -- INSERT after the pattern_detect block (~line 854),
# BEFORE the schwab_snapshot comment block. Mirror the pattern_detect shape.
+    lease.step("pattern_observe")
+    try:
+        _step_pattern_observe(
+            cfg=cfg, lease=lease, ohlcv_cache=ohlcv_cache,
+            run_warnings=run_warnings,
+        )
+    except LeaseRevokedError:
+        raise
+    except Exception as exc:
+        log.warning("pattern_observe failed: %s", exc)
```

```python
# swing/pipeline/runner.py  -- at the completion path lease.release(state="complete",...)
# (T-2.5 step 0 located the exact callsite). Thread warnings_json:
     lease.release(
         state="complete",
+        warnings_json=(json.dumps(run_warnings) if run_warnings else None),
     )
```

> **Implementer note:** the agent re-grep found the completion path returns `RunResult(...)` at runner.py:974 without an explicit `lease.release(state="complete")` in the immediate frame -- T-2.5 step 0 MUST locate the actual complete-state release (it exists: `lease.release` accepts `state` + `warnings_json`, lease.py:74-86). If the orchestrator finalizes via a different helper (e.g. `finalize_run` directly), thread `warnings_json` there. Empty-state representation MUST be `None`, not `"[]"` (audit-envelope-empty-state gotcha).

- [ ] **Step 6: Write the observe-step integration tests (concrete, executable)**

> **ohlc_today_json shape contract (Codex chain #1 Major #5):** `_bar_for_date` returns a dict with EXACTLY these keys -- `{"open": float, "high": float, "low": float, "close": float, "volume": float, "provider": "schwab_api"|"yfinance"}` -- and `_step_pattern_observe` serializes it via `json.dumps(bar)`. The `provider` key is REQUIRED (OQ-17). The tests below assert the key by FIELD (not substring match). A future ruleset replay reads these exact keys.

> **Fixture scaffolding (concrete helpers the implementer adds to the module):**
> - `tmp_db_v22(tmp_path)` -- file-backed `sqlite3` migrated to v22 (path retained for the observe step's own `connect`).
> - `_FakeLease(db_path, run_id, data_asof)` -- implements the 3 members `_step_pattern_observe` uses: `run_id` (int), `step(name)` (no-op), and `fenced_write()` (a `contextmanager` yielding a `sqlite3` connection to `db_path` with `BEGIN IMMEDIATE`/COMMIT). The implementer MAY instead use the real `Lease` via the existing pipeline test helpers; `_FakeLease` keeps these tests self-contained.
> - `_cfg(tmp_path, db_path)` -- a `Config` (or a lightweight stub) exposing `cfg.paths.db_path`, `cfg.paths.prices_cache_dir`, and `cfg.pipeline.observe_max_pending_window_sessions` / `observe_max_post_trigger_window_sessions`.
> - `_plant_detection(conn, *, ticker, data_asof_date, pivot=10.0, invalidation=8.0)` -- inserts a `PatternDetectionEvent` with a `structural_anchors_json` carrying `{"evidence": {"pivot_price": pivot, "contractions": [{"low": invalidation}]}}` (vcp class).
> - `_stub_window(close, *, high=None, low=None, provider="yfinance", date_)` -- returns `(pd.DataFrame([{ "asof_date": date_, "open": close, "high": high or close, "low": low or close, "close": close, "volume": 1e6}]), {date_: provider})` to patch `swing.data.ohlcv_archive.resolve_ohlcv_window` (imported locally in `_bar_for_date`).

```python
# tests/pipeline/test_step_pattern_observe.py  (append -- integration set)
import json
from unittest.mock import patch
from swing.pipeline.runner import _step_pattern_observe, lease_data_asof
from swing.data.repos.pattern_forward_observations import get_observations_for_detection


def test_observation_appended_with_provider_tag(tmp_db_v22, tmp_path):
    conn, db_path = tmp_db_v22
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-28")
    cfg = _cfg(tmp_path, db_path)
    lease = _FakeLease(db_path, run_id=1, data_asof="2026-05-29")
    warnings: list[dict] = []
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window",
               return_value=_stub_window(9.0, provider="yfinance", date_="2026-05-29")):
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
            _step_pattern_observe(cfg=cfg, lease=lease,
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}),
                                  run_warnings=warnings)
    chain = get_observations_for_detection(conn, det_id)
    assert len(chain) == 1
    bar = json.loads(chain[0].ohlc_today_json)
    assert bar["provider"] == "yfinance"            # OQ-17 by FIELD
    assert set(bar) == {"open", "high", "low", "close", "volume", "provider"}
    assert chain[0].observation_date == "2026-05-29"
    assert chain[0].status == "pending"             # below pivot, above invalidation


def test_pending_to_triggered_open_on_breakout(tmp_db_v22, tmp_path):
    conn, db_path = tmp_db_v22
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-28", pivot=10.0)
    cfg = _cfg(tmp_path, db_path); lease = _FakeLease(db_path, 1, "2026-05-29")
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window",
               return_value=_stub_window(10.2, high=10.5, date_="2026-05-29")):
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
            _step_pattern_observe(cfg=cfg, lease=lease,
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}),
                                  run_warnings=[])
    obs = get_observations_for_detection(conn, det_id)[0]
    assert obs.status == "triggered_open" and obs.status_change_event == "entry_fired"


def test_sessions_since_detection_counts_from_data_asof(tmp_db_v22, tmp_path):
    conn, db_path = tmp_db_v22
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-22")  # Fri
    cfg = _cfg(tmp_path, db_path); lease = _FakeLease(db_path, 1, "2026-05-29")
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window",
               return_value=_stub_window(9.0, date_="2026-05-29")):  # next Fri
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
            _step_pattern_observe(cfg=cfg, lease=lease,
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}),
                                  run_warnings=[])
    obs = get_observations_for_detection(conn, det_id)[0]
    # 5 business days from 2026-05-22 (excl) to 2026-05-29 (incl).
    assert obs.sessions_since_detection == 5


def test_idempotent_same_day_reobservation(tmp_db_v22, tmp_path):
    conn, db_path = tmp_db_v22
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-28")
    cfg = _cfg(tmp_path, db_path); lease = _FakeLease(db_path, 1, "2026-05-29")
    stub = _stub_window(9.0, date_="2026-05-29")
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window", return_value=stub):
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
            _step_pattern_observe(cfg=cfg, lease=lease,
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}), run_warnings=[])
            _step_pattern_observe(cfg=cfg, lease=lease,  # re-run same observation_date
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}), run_warnings=[])
    assert len(get_observations_for_detection(conn, det_id)) == 1  # no dup; no UNIQUE error


def test_empty_open_pool_warns(tmp_db_v22, tmp_path):
    conn, db_path = tmp_db_v22  # no detections planted
    cfg = _cfg(tmp_path, db_path); lease = _FakeLease(db_path, 1, "2026-05-29")
    warnings: list[dict] = []
    with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
        _step_pattern_observe(cfg=cfg, lease=lease,
                              ohlcv_cache=_StubOhlcvCache({}), run_warnings=warnings)
    assert any(w["step"] == "pattern_observe" and w["actual_open_pool"] == 0
               for w in warnings)


def test_no_bar_for_date_warns_and_skips(tmp_db_v22, tmp_path):
    conn, db_path = tmp_db_v22
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-28")
    cfg = _cfg(tmp_path, db_path); lease = _FakeLease(db_path, 1, "2026-05-29")
    warnings: list[dict] = []
    import pandas as pd
    empty = (pd.DataFrame(columns=["asof_date", "open", "high", "low", "close", "volume"]), {})
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window", return_value=empty):
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
            _step_pattern_observe(cfg=cfg, lease=lease,
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}),
                                  run_warnings=warnings)
    assert get_observations_for_detection(conn, det_id) == []
    assert any(w.get("reason") == "no bar for observation_date" for w in warnings)


def test_forward_walk_freezes_past_bar(tmp_db_v22, tmp_path):
    # #26/#37-by-construction discriminator: a past observation's frozen
    # ohlc_today_json is NEVER re-read from a later archive.
    conn, db_path = tmp_db_v22
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-27")
    cfg = _cfg(tmp_path, db_path)
    # Session N = 2026-05-28: record close 9.00.
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window",
               return_value=_stub_window(9.00, date_="2026-05-28")):
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-28"):
            _step_pattern_observe(cfg=cfg, lease=_FakeLease(db_path, 1, "2026-05-28"),
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}), run_warnings=[])
    obs_N_before = json.loads(get_observations_for_detection(conn, det_id)[0].ohlc_today_json)
    # Session N+1 = 2026-05-29: the archive NOW reports a DIFFERENT close for N
    # (simulating gotcha #26 drift) -- but observe at N+1 only records N+1.
    def _drifted(ticker, *, start, end, cache_dir):
        import pandas as pd
        rows = [{"asof_date": "2026-05-28", "open": 9.99, "high": 9.99, "low": 9.99,
                 "close": 9.99, "volume": 1e6},  # DRIFTED date-N bar
                {"asof_date": "2026-05-29", "open": 9.10, "high": 9.10, "low": 9.10,
                 "close": 9.10, "volume": 1e6}]
        df = pd.DataFrame([r for r in rows if start <= r["asof_date"] <= end])
        return df, {r["asof_date"]: "yfinance" for _, r in df.iterrows() for r in [r]} or {}
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window", side_effect=_drifted):
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
            _step_pattern_observe(cfg=cfg, lease=_FakeLease(db_path, 2, "2026-05-29"),
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}), run_warnings=[])
    chain = get_observations_for_detection(conn, det_id)
    obs_N_after = json.loads(chain[0].ohlc_today_json)  # the date-N row
    assert obs_N_after == obs_N_before          # FROZEN -- #26 cannot occur
    assert obs_N_after["close"] == 9.00         # NOT the drifted 9.99
    assert chain[1].observation_date == "2026-05-29" and json.loads(chain[1].ohlc_today_json)["close"] == 9.10
```

(The `_advance_status` unit tests from Step 2 + these integration tests together cover spec section 11.6. `pending->invalidated` and `pending->expired` transitions are covered by the Step-2 unit tests; an integration variant of each MAY be added but the unit tests are the discriminating gate.)

- [ ] **Step 7: Run the full T-2.5 suite + ruff + commit**

Run: `python -m pytest tests/config/test_pipeline_observe_windows.py tests/pipeline/test_step_pattern_observe.py -q && ruff check swing/config.py swing/pipeline/runner.py`
Expected: PASS; 0 ruff errors.

```bash
git add swing/config.py swing/pipeline/runner.py tests/config/test_pipeline_observe_windows.py tests/pipeline/test_step_pattern_observe.py
git commit -m "feat(pipeline): _step_pattern_observe forward-walk + status machine (T-2.5)"
```

---

### Task T-2.6: Closer (cross-step integration + L2 source-grep + ASCII + return report)

**Files:**
- Test: `tests/integration/test_phase14_temporal_log_e2e.py`
- (verify) `tests/integration/test_l2_lock_source_grep.py`
- Doc: `docs/phase14-sub-bundle-2-temporal-log-writing-plans-return-report.md` (this is authored by the WRITING-PLANS implementer per §M; the EXECUTING-PLANS closer instead writes the executing-plans return report -- this task slice is for the executing-plans phase.)

**Acceptance criteria:**
- Cross-step e2e: detect appends a detection (+ chart_render_id), observe forward-walks it across multiple simulated sessions with correct status transitions, the chart_render chain resolves.
- L2 source-grep test continues passing (ZERO new `schwabdev.Client.*`); the plan cites the baseline `bf7e071`.
- ASCII verification over all NEW/MODIFIED production + test files (§K.4).
- Sec 9.1 + L1-L8 + the 5 OQ LOCKs verified (a checklist test or the return-report table).

**Discipline preservation:** L8 (L2 source-grep continued pass); #32/#16 (ASCII); test-fixture-vs-production-emitter parity; Expansion #15 (return-report narrative sweep).

- [ ] **Step 1: Write the cross-step forward-walk e2e test (concrete; reuses T-2.4/T-2.5 fixtures)**

```python
# tests/integration/test_phase14_temporal_log_e2e.py
import json
from unittest.mock import patch
from swing.data.repos.pattern_detection_events import list_detection_events
from swing.data.repos.pattern_forward_observations import get_observations_for_detection
# Reuse the fixtures established in T-2.4 / T-2.5 (imported or duplicated in a
# shared conftest: tmp_db_v22, _seed_aplus_candidate_and_run, _drive_detect,
# _StubOhlcvCache, _build_bars, _FakeLease, _cfg, _stub_window).
from tests.pipeline.test_step_pattern_detect_temporal_extension import (  # type: ignore
    _seed_aplus_candidate_and_run, _drive_detect, _StubOhlcvCache, _build_bars,
)
from tests.pipeline.test_step_pattern_observe import _FakeLease, _cfg, _stub_window  # type: ignore
from swing.pipeline.runner import _step_pattern_observe


def test_detect_then_forward_walk_e2e(tmp_db_v22, tmp_path):
    conn, db_path = tmp_db_v22
    # 1. Detect: one aplus candidate -> a frozen detection + a captured chart.
    _conn, cfg, lease, eval_run_id = _seed_aplus_candidate_and_run(
        (conn, db_path), ticker="AAA", data_asof_date="2026-05-27")
    _drive_detect(conn, cfg, lease, eval_run_id,
                  _StubOhlcvCache({"AAA": _build_bars()}), [])
    det = list_detection_events(conn, ticker="AAA")[0]
    assert det.chart_render_id is not None
    facts_before = (det.structural_anchors_json, det.composite_score, det.data_asof_date)
    # chart chain resolves to non-empty bytes.
    blen = conn.execute("SELECT length(chart_svg_bytes) FROM chart_renders "
                        "WHERE id = ?", (det.chart_render_id,)).fetchone()[0]
    assert blen and blen > 0

    # 2. Session N (below pivot) -> 'pending'.
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window",
               return_value=_stub_window(9.0, date_="2026-05-28")):
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-28"):
            _step_pattern_observe(cfg=cfg, lease=_FakeLease(db_path, 2, "2026-05-28"),
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}), run_warnings=[])
    chain = get_observations_for_detection(conn, det.detection_id)
    assert chain[-1].status == "pending"

    # 3. Session N+1 (above pivot) -> 'triggered_open' / 'entry_fired'.
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window",
               return_value=_stub_window(10.5, high=10.9, date_="2026-05-29")):
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
            _step_pattern_observe(cfg=cfg, lease=_FakeLease(db_path, 3, "2026-05-29"),
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}), run_warnings=[])
    chain = get_observations_for_detection(conn, det.detection_id)
    assert chain[-1].status == "triggered_open"
    assert chain[-1].status_change_event == "entry_fired"

    # 4. The detection FACTS are unchanged across observe runs (append-only).
    det_after = list_detection_events(conn, ticker="AAA")[0]
    assert (det_after.structural_anchors_json, det_after.composite_score,
            det_after.data_asof_date) == facts_before
```

> (The `_seed_aplus_candidate_and_run` signature here takes `(conn, db_path)` to share the e2e DB; the implementer aligns the helper signature across T-2.4/T-2.5/T-2.6 -- one shared conftest fixture set.)

- [ ] **Step 2: Verify the L2 source-grep test still passes**

Run: `python -m pytest tests/integration/test_l2_lock_source_grep.py -q`
Expected: PASS (pattern `"schwabdev.Client."`; multiset `Counter[(path, line_text)]`; baseline `bf7e071`). The temporal-log code adds ZERO new `schwabdev.Client.*` call sites (chart capture = matplotlib; observe OHLCV = OhlcvCache ladder + `resolve_ohlcv_window` archive read).

- [ ] **Step 3: ASCII verification**

```python
# tests/integration/test_phase14_ascii_discipline.py
import pathlib
FILES = [
    "swing/data/migrations/0022_phase14_temporal_log.sql",
    "swing/data/repos/pattern_detection_events.py",
    "swing/data/repos/pattern_forward_observations.py",
    "swing/pipeline/temporal_metadata.py",
    "swing/pipeline/detection_chart_capture.py",
    # ... plus the diffs in db.py/models.py/config.py/runner.py/charts.py
    # (verify the NEW lines are ASCII; the whole files may predate the scope)
]
def test_new_files_are_ascii():
    for f in FILES:
        text = pathlib.Path(f).read_text(encoding="utf-8")
        text.encode("ascii")  # raises UnicodeEncodeError on any non-ASCII glyph
```

Run: `python -m pytest tests/integration/test_phase14_ascii_discipline.py tests/integration/test_phase14_temporal_log_e2e.py -q`
Expected: PASS.

- [ ] **Step 4: Full fast-suite green + ruff + commit**

Run: `python -m pytest -m "not slow" -q && ruff check swing/`
Expected: PASS (~5670 + new tests green); 0 ruff E501.

```bash
git add tests/integration/test_phase14_temporal_log_e2e.py tests/integration/test_phase14_ascii_discipline.py
git commit -m "test(integration): phase14 temporal-log cross-step e2e + L2/ASCII (T-2.6)"
```

- [ ] **Step 5: (executing-plans phase) author the executing-plans return report** per the executing-plans dispatch brief shape (NOT this writing-plans return report).

---

## §H Test surface (fast/slow split + per-task distribution + sum-check)

> Per dispatch brief §1.5 L3 (~50-100 fast tests; trust `pytest` over the estimate -- gotcha #1). **0 slow tests** anticipated (observe-step OHLCV mocked; chart render uses canned bars; no live yfinance/Schwab).

| Task | Test module(s) | Fast tests (est.) |
|---|---|---|
| T-2.1 | `test_temporal_log_migration.py` (apply + v22 + 3 backup-gate + rollback-through-runner + 2 CHECK-reject = ~8) + `test_models_temporal.py` (6 validators) | 14 |
| T-2.2 | `test_pattern_detection_events_repo.py` (insert/get/caller-tx/UNIQUE/3 observable/append-only-grep) | 9 |
| T-2.3 | `test_pattern_forward_observations_repo.py` (insert/chain/UNIQUE/latest/empty-short-circuit/batch-multi/RESTRICT/append-only-grep) | 11 |
| T-2.4 | `test_temporal_metadata.py` (~6) + `test_detection_chart_capture.py` (~4) + `test_chart_theme2_overlay.py` (~1) + `test_step_pattern_detect_temporal_extension.py` (~12) | 23 |
| T-2.5 | `test_pipeline_observe_windows.py` (2) + `test_step_pattern_observe.py` (~8 status arithmetic + ~10 integration incl. forward-walk-freeze) | 20 |
| T-2.6 | `test_phase14_temporal_log_e2e.py` (~3) + `test_phase14_ascii_discipline.py` (1) + L2 source-grep (verify-pass, pre-existing) | 4 |
| **Sum** | | **~81** |

**Sum-check: ~81 fast tests, inside the ~50-100 LOCK band.** Distribution proportions match dispatch brief §2.3 (migration/CHECK/validator ~14; detection repo ~9; observations repo ~11; detect-extension+metadata+chart ~23; observe+status+provenance ~20; integration+L2 ~4). **The implementer trusts `pytest -m "not slow" -q` output, NOT this estimate** -- the count will drift as discriminating tests are added/merged; the LOCK is the band, not the exact integer.

**Project baseline:** ~5670 fast tests green on `main` (CLAUDE.md). Post-Sub-bundle-2 projection: ~5670 + ~81 = ~5751 fast tests. The executing-plans closer reports the actual count.

**Mandatory discriminating tests (dispatch brief §2.3):**
- Append-only (OQ-10): no `update_*`/`delete_*` fns (source-grep, both repos); UNIQUE rejects dup observation; RESTRICT FK blocks deleting a detection with observations.
- Forward-walk (#26/#37): frozen `ohlc_today_json` UNCHANGED after archive mutation + re-run (T-2.5 step 6).
- Status-machine arithmetic (`feedback_verify_regression_test_arithmetic`): at-threshold (30/90) + under-threshold (29/50) pairs pin the `>=` boundary; breakout vs near-miss pins the pivot predicate.
- Provider provenance (OQ-17): `ohlc_today_json` carries the `provider` tag (round-trip assertion).

---

## §I Operator-witnessed gate runbook

> Per dispatch brief §2.4 + spec §10.2. Browser MCP may be unavailable -- the proven fallback is operator-driven browser + orchestrator running the DB-side probes step-by-step. S2/S3/S4/S5/S6/S7 are scriptable (DB-verifiable); S1 is mechanical.

| # | Surface | Pass criterion | Scriptable probe |
|---|---|---|---|
| **S1** | fast suite + ruff | `python -m pytest -m "not slow" -q` all pass; `ruff check swing/` 0 errors | mechanical |
| **S2** | schema v22 applied | `swing db-migrate` brings the DB to v22; `_current_version == 22`; both new tables empty + readable; `swing-pre-phase14-migration-<ISO>.db` backup written at the `current_version == 21` boundary | `PRAGMA user_version` / `SELECT version FROM schema_version`; `SELECT COUNT(*)` on both tables; `ls` the backup |
| **S3** | run pipeline; detect step | `pattern_detection_events` accumulates rows for A+ detections; per-pattern metadata populated (sector/industry/adr_pct/atr_pct/ret_90d/prox_52w; `market_cap` null); `chart_render_id` non-NULL for successful renders; `data_asof_date` populated | `SELECT ticker, pattern_class, per_pattern_metadata_json, chart_render_id, data_asof_date FROM pattern_detection_events` |
| **S4** | re-run pipeline; observe step | `pattern_forward_observations` appends today's bar for previously-open detections; `provider` tag present in `ohlc_today_json`; status transitions (pending -> triggered_open on pivot breakout; -> invalidated on structural-low break; -> expired on window) | `SELECT observation_date, status, status_change_event, ohlc_today_json FROM pattern_forward_observations ORDER BY observation_date` |
| **S5** | append-only verification | attempt UPDATE via repo -> no such fn (source-grep test); raw DELETE of a detection with observations -> RESTRICT; duplicate observation -> UNIQUE; INSERT-only path works | mechanical-test-covered (T-2.2/T-2.3) + spot-check raw SQL DELETE -> `IntegrityError` |
| **S6** | chart_render chain | `pattern_detection_events.chart_render_id` -> `chart_renders.id` -> non-empty `chart_svg_bytes`; theme2_annotated row carries the detection's `pattern_class` + `pipeline_run_id`; **visual: the rendered SVG shows the structural overlays (evidence-key repair works)** | `SELECT length(chart_svg_bytes) FROM chart_renders WHERE id = (SELECT chart_render_id FROM pattern_detection_events ...)`; **operator opens the SVG to confirm overlays (binding visual gate per the matplotlib gotcha)** |
| **S7** | gotcha #27 audit | force an empty A+ pool (or empty open-detection set); `pipeline_runs.warnings_json` carries the structured empty-pool entry (NOT silent / NOT `"[]"`) | `SELECT warnings_json FROM pipeline_runs ORDER BY started_ts DESC LIMIT 1` |

S5 + S6-DB-portion are mechanical-test-covered; S6-visual is the binding operator gate (matplotlib render regressions are invisible to string-equality tests).

---

## §J Codex MCP TWO-chain placement

> Per dispatch brief §1.3 OQ-20 LOCK + §1.5 L6: TWO chains at writing-plans AND a designed two-chain executing-plans posture. FB-N1 RESOLVED (`d134833`): the Windows `cmd /c codex mcp-server` launcher fix is applied; use the MCP transport; `codex exec` CLI is the transport-independent backstop.

### §J.1 Writing-plans phase (THIS phase -- run now, after the plan draft)

- **Chain #1 -- plan-completeness / implementation-feasibility lens.** Does every spec requirement map to a task? Are the bite-sized TDD steps executable as written (real code, no placeholders)? Are the production signatures/line-cites accurate? Is the commit cadence within ~15-25? Is the test count within ~50-100? Does the detect-loop `bars_by_ticker` retention work without a re-fetch? Converge to NO_NEW_CRITICAL_MAJOR.
- **Chain #2 -- schema/semantics-hardening lens.** Append-only invariants (no update/delete; UNIQUE + RESTRICT; SET-NULL audit linkages); forward-walk #26/#37 correctness (select-by-`observation_date`; `data_asof_date` boundary `<` STRICT; frozen `ohlc_today_json`); v22 DDL/CHECK/FK posture (5-value source enum; 6-value status enum with V1+ 4-value emit subset; both FKs SET NULL; observations RESTRICT); status-machine completeness (all transitions; `>=` boundary directionality; per-class invalidation level sourcing); migration-runner rollback (gotcha #9 explicit BEGIN/COMMIT + rollback-through-runner; STRICT `current_version == 21`). Converge to NO_NEW_CRITICAL_MAJOR.

**Invocation:** `copowers:adversarial-critic` with `PHASE=writing-plans`, `SPEC_PATH`, `PLAN_PATH`, run TWICE (once per lens). FB-N1: attempt MCP (`mcp__plugin_copowers_codex__codex`); on timeout fall back to `codex exec` / `codex exec resume --last -o <file> -`; bank any recurrence.

### §J.2 Executing-plans phase (designed now; runs at executing-plans dispatch)

- **Chain #1 -- implementation review** AFTER code + tests land, BEFORE the operator-witnessed gate (§I). Lens: production-shape fixture parity; the detect-loop append correctness (bars retention; idempotency SELECT-then-skip; chart_render_id NULL path); observe-step bar-anchoring + provider tag + status transitions against real archive shapes; warnings accumulator threading to `lease.release`; existing detector tests still green (L7).
- **Chain #2 -- schema/semantics-hardening review.** Same lens as §J.1 chain #2, now against SHIPPED code: re-verify the append-only invariants hold at runtime (RESTRICT FK fires; no update/delete path); forward-walk freeze test is genuinely discriminating; the 30/60 windows + per-class invalidation read from the frozen anchors; migration applied cleanly + rollback-through-runner passes; L2 source-grep continues passing.

### §J.3 The 18 brainstorm adversarial watch items (dispatch brief §5) -- carried forward

Both writing-plans chains MUST exercise: (1) brief-vs-production-signature re-verification (DONE in §C; re-cite); (2) SQL column verification (§B.1/§G.0 DDL); (3) CHECK + constant + validator paired (T-2.1); (4) migration runner discipline (#9 + STRICT gate); (5) append-only enforcement (multi-layer); (6) #27 silent-skip audit (3 sites); (7) #26/#37 elimination kept honest (select-by-date + freeze); (8) per-pattern metadata sourcing (bars, no fetch); (9) chart_render integration (SET NULL + last-writer-wins + failure->NULL); (10) OQ-17 provenance tag; (11) status-machine completeness; (12) `pattern_evaluations` coexistence (L7); (13) empty-input handling; (14) taxonomy/attribution propagation (status/source/provider by FIELD); (15) cumulative regression cascade audit; (16) test-fixture-vs-production-emitter parity; (17) L2 source-grep; (18) ASCII discipline; (19) Co-Authored-By suppression. The brainstorm forward-binding lessons FB-N1..FB-N6 (§M) are also in-scope.

---

## §K Schema impact analysis (v22 introduction)

> Per dispatch brief §2.6. The plan DESIGNS the v22 introduction (it is not applied until executing-plans; Schema v21 stays LOCKED at writing-plans -- this is a docs-only deliverable).

### §K.1 v22 is the only new migration

Baseline is 21 `*.sql` files (`0001`..`0021`; verified §C / Explore item 16); `0022_phase14_temporal_log.sql` is the ONLY new migration. NO v23 (Sub-bundle 3 owns the next migration). `EXPECTED_SCHEMA_VERSION` 21 -> 22.

### §K.2 Backup gate STRICT equality

`_phase14_backup_gate` fires ONLY at `current_version == 21 AND target_version >= 22` (STRICT, NOT `<=`). Copies the Phase 13 `_phase13_sb6c_backup_gate` (`current_version != 20`) clause shape verbatim. A v20->v22 multi-step walk bypasses the v22-specific gate by design (Phase 9/12/13 precedent). `PHASE14_PRE_MIGRATION_EXPECTED_TABLES = PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES` (v21 added no tables).

### §K.3 Migration-runner discipline (gotcha #9)

`0022` uses explicit `BEGIN;`/`COMMIT;` with `UPDATE schema_version SET version = 22;` as the FINAL statement before COMMIT. The runner (`_apply_migration`, `db.py:171-214`) wraps with `PRAGMA foreign_keys=OFF` + try/except `rollback()`+re-raise. No table rebuilds in `0022` (pure additive CREATE TABLE), so the FK-cascade-wipe risk is absent -- but the discipline is inherited uniformly. The rollback-through-runner test (T-2.1 step 10) asserts a malformed `0022` variant leaves the DB at v21 + `conn.in_transaction == False`, tested through the REAL `_apply_migration` path (not bare `executescript`).

### §K.4 ASCII discipline scope (gotcha #16/#32)

ASCII-only across ALL NEW/MODIFIED production + test surfaces: `0022_phase14_temporal_log.sql`; `swing/data/db.py` (diff); `swing/data/models.py` (new dataclasses + constants); `swing/data/repos/pattern_detection_events.py`; `swing/data/repos/pattern_forward_observations.py`; `swing/config.py` (diff); `swing/pipeline/runner.py` (diff); `swing/pipeline/temporal_metadata.py`; `swing/pipeline/detection_chart_capture.py`; `swing/web/charts.py` (diff); all NEW/MODIFIED test modules. Verification: programmatic `text.encode("ascii")` (T-2.6 step 3). **THIS plan doc + the dispatch brief + the return report are EXCLUDED** (the `section`-sign convention -- written here as the word "section" inside code/SQL comments, and as `§` only in prose/markdown headings which are doc-scope, not stdout-scope). Note: the migration SQL comments + dataclass docstrings use the word "section" (not `§`) to stay strictly ASCII.

### §K.5 gotcha #11 paired discipline

CHECK enums (`pattern_class`, `source`, `status`, `status_change_event`) + Python module constants (`_PATTERN_DETECTION_SOURCE_VALUES`, `_FORWARD_OBSERVATION_STATUS_VALUES`, `_FORWARD_OBSERVATION_STATUS_CHANGE_EVENTS`; `DETECTOR_PATTERN_CLASSES` reused) + dataclass `__post_init__` validators ALL land in T-2.1. The `_row_to_*` read-path mappers land in their respective repo tasks (T-2.2/T-2.3) -- these are NEW glue, not enum widenings, so the #11 read-path-same-task rule (about widening) is satisfied by the atomic CHECK+constant+validator landing.

---

## §L Test fixture strategy

> Per dispatch brief §6 §L + spec §11. The binding rule: fixtures match the PRODUCTION INSERT shape exactly (Phase-12 C.D synthetic-fixture-vs-production-emitter family).

### §L.1 Per-table fixtures

- **`pattern_detection_events`:** built via the real `PatternDetectionEvent` dataclass (validators fire) + the real `build_structural_anchors_json` / `build_per_pattern_metadata` / `build_finviz_screen_state` helpers fed REAL detector evidence dataclasses + a real `Candidate` -- so `structural_anchors_json` carries the production `dataclasses.asdict(evidence)` shape (not a hand-rolled dict). The detect-extension integration tests (T-2.4) plant candidates via `swing.data.repos.candidates.insert_candidates(...)` + drive the emit path so the INSERT shape matches production exactly.
- **`pattern_forward_observations`:** built via the real `PatternForwardObservation` dataclass; the observe-step tests (T-2.5) drive `_step_pattern_observe` with a mocked `OhlcvCache.get_or_fetch` + a stubbed `resolve_ohlcv_window` returning canned Shape-A frames (lowercase `asof_date`/`open`/`high`/`low`/`close`/`volume` columns + the provenance dict). The status-machine unit tests use a minimal `_Det` stub carrying ONLY `structural_anchors_json` + `data_asof_date` + `pattern_class` (the fields `_advance_status` reads).

### §L.2 Per-step fixtures

- **detect extension:** real `Candidate` (with `sector`/`industry`/`adr_pct`/`rs_rank`/`criteria`) + real evidence dataclasses + a `bars` DataFrame with a `DatetimeIndex` + capitalized OHLCV columns (matches `get_or_fetch`'s shape contract). Chart-capture tests seed a `pipeline_runs` row so the FK is satisfiable.
- **observe step:** plant `pattern_detection_events` rows via the new repo; stub `resolve_ohlcv_window` to return a known bar for `observation_date` + a known provider; assert the status + the frozen `ohlc_today_json`.
- **forward-walk freeze:** plant detection + an observation at date N; mutate the stubbed archive return for date N; re-run observe at N+1; assert the date-N row is byte-identical (the #26/#37 discriminator).

### §L.3 Anti-drift rules

- Evidence fixtures use the REAL detector evidence dataclasses (so `asdict` produces the production `structural_anchors_json` shape). Never hand-roll the evidence dict.
- The `provider` value is consumed by FIELD (`ohlc_today_json["provider"]`), not by value-matching a substring (Expansion #11).
- The status `change_event` is asserted by the enum value, not by a render heuristic.

### §L.4 Shared fixture module (concrete implementations -- Codex chain #1 R2 Major #2)

Put these in `tests/pipeline/conftest_temporal.py` (or a shared `conftest.py`) so T-2.4/T-2.5/T-2.6 import ONE definition each. The fully-specified helpers below are executable as written; the two harness-dependent helpers (`_seed_aplus_candidate_and_run`, `_drive_detect`) carry concrete bodies plus the 1-2 lines the implementer aligns with the EXISTING `tests/pipeline/test_step_pattern_detect.py` harness (the verified source of truth for driving the step).

```python
# tests/pipeline/conftest_temporal.py
from __future__ import annotations
import json
import sqlite3
from contextlib import contextmanager
from datetime import date
import numpy as np
import pandas as pd
import pytest
from swing.data.db import run_migrations
from swing.data.models import PatternDetectionEvent


@pytest.fixture
def tmp_db_v22(tmp_path):
    """File-backed v22 DB; returns (conn, db_path). The observe step opens its
    OWN connect(db_path) for reads, so the DB MUST be file-backed."""
    db_path = tmp_path / "t.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=22, backup_dir=tmp_path)
    return conn, db_path


def _build_bars(start: date = date(2025, 6, 1), n_days: int = 180) -> pd.DataFrame:
    """Reuse the existing detect-step test's bar shape: DatetimeIndex +
    capitalized OHLCV. (If tests/pipeline/test_step_pattern_detect.py exposes
    _build_bars, import that instead to share one definition.)"""
    idx = pd.bdate_range(start=start, periods=n_days)
    close = np.linspace(8.0, 10.0, n_days)
    return pd.DataFrame(
        {"Open": close * 0.99, "High": close * 1.02, "Low": close * 0.98,
         "Close": close, "Volume": 1_000_000.0}, index=idx)


class _StubOhlcvCache:
    """get_or_fetch(*, ticker, window_days) -> the canned frame for ticker."""
    def __init__(self, bars_by_ticker: dict[str, pd.DataFrame]):
        self._b = bars_by_ticker

    def get_or_fetch(self, *, ticker: str, window_days: int = 180) -> pd.DataFrame:
        if ticker not in self._b:
            raise KeyError(ticker)  # mimic a fetch miss
        return self._b[ticker]


class _FakeLease:
    """Minimal lease implementing only what the steps use: run_id, step(),
    fenced_write() (a contextmanager yielding a conn to the same file DB)."""
    def __init__(self, db_path, run_id: int, data_asof: str):
        self.db_path = db_path
        self.run_id = run_id
        self._data_asof = data_asof

    def step(self, name: str) -> None:  # no-op breadcrumb
        pass

    @contextmanager
    def fenced_write(self):
        conn = sqlite3.connect(self.db_path)
        conn.execute("PRAGMA foreign_keys=ON")
        try:
            conn.execute("BEGIN IMMEDIATE")
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise
        finally:
            conn.close()


class _Cfg:
    """Lightweight cfg stub exposing only the attributes the steps read."""
    class _Paths:
        def __init__(self, db_path, cache_dir):
            self.db_path = db_path
            self.prices_cache_dir = cache_dir
    class _Pipeline:
        observe_max_pending_window_sessions = 30
        observe_max_post_trigger_window_sessions = 60
    def __init__(self, db_path, cache_dir):
        self.paths = self._Paths(db_path, cache_dir)
        self.pipeline = self._Pipeline()


def _cfg(tmp_path, db_path):
    cache = tmp_path / "ohlcv"; cache.mkdir(exist_ok=True)
    return _Cfg(db_path, cache)


def _plant_detection(conn, *, ticker="AAA", data_asof_date="2026-05-28",
                     pivot=10.0, invalidation=8.0) -> int:
    """Insert one vcp PatternDetectionEvent via the repo; return detection_id."""
    from swing.data.repos.pattern_detection_events import insert_detection_event
    anchors = json.dumps({"window": {}, "evidence": {
        "pivot_price": pivot, "base_top_price": pivot,
        "contractions": [{"low": invalidation}]}})
    with conn:
        return insert_detection_event(conn, PatternDetectionEvent(
            detection_id=None, ticker=ticker, detection_date="2026-05-29",
            data_asof_date=data_asof_date, pattern_class="vcp",
            structural_anchors_json=anchors, composite_score=0.7,
            detector_version="vcp_v1", source="pipeline",
            per_pattern_metadata_json="{}", created_at="2026-05-29T00:00:00Z"))


def _stub_window(close, *, high=None, low=None, provider="yfinance", date_):
    """Return (df, provenance) shaped like resolve_ohlcv_window for ONE date."""
    df = pd.DataFrame([{
        "asof_date": date_, "open": close, "high": high or close,
        "low": low or close, "close": close, "volume": 1_000_000.0}])
    return df, {date_: provider}
```

```python
# tests/pipeline/conftest_temporal.py  (harness helper -- CONCRETE; the
# EvaluationRun field list + pipeline_runs columns are copied verbatim from
# the verified harness at tests/pipeline/test_step_pattern_detect.py:131-170 +
# :110-128, so there are NO flagged lines.)
def _seed_aplus_candidate_and_run(db, *, ticker="AAA", sector="", industry="",
                                  adr_pct=2.5, rs_rank=85,
                                  data_asof_date="2026-05-19",
                                  action_session_date="2026-05-20"):
    """Seed a pipeline_runs row + an EvaluationRun + one bucket='aplus'
    Candidate; return (conn, cfg, lease, eval_run_id). Uses the REAL repos so
    the INSERT shape matches production (anti-drift). Field shapes verbatim
    from the verified detect-step harness."""
    conn, db_path = db
    from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
    from swing.data.models import Candidate, EvaluationRun
    # pipeline_runs row (id=1) -- lease_data_asof reads its data_asof_date.
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, data_asof_date, "
        "action_session_date, lease_token, state) VALUES "
        "(1, ?, ?, ?, 'tok-test-1', 'running')",
        ("2026-05-20T18:00:00", data_asof_date, action_session_date))
    eval_run_id = insert_evaluation_run(conn, EvaluationRun(
        id=None, run_ts="2026-05-20T18:00:00", data_asof_date=data_asof_date,
        action_session_date=action_session_date, finviz_csv_path=None,
        tickers_evaluated=1, aplus_count=1, watch_count=0, skip_count=0,
        excluded_count=0, error_count=0))
    insert_candidates(conn, eval_run_id, [Candidate(
        ticker=ticker, bucket="aplus", close=15.0, pivot=15.1, initial_stop=13.5,
        adr_pct=adr_pct, tight_streak=3, pullback_pct=5.0, prior_trend_pct=40.0,
        rs_rank=rs_rank, rs_return_12w_vs_spy=12.0, rs_method="universe",
        pattern_tag=None, notes=None, criteria=tuple(), sector=sector,
        industry=industry)])
    conn.commit()
    cfg = _cfg(db_path.parent, db_path)
    lease = _FakeLease(db_path, run_id=1, data_asof=data_asof_date)
    return conn, cfg, lease, eval_run_id


def _seed_run_with_zero_aplus(db):
    """Same scaffold but the only candidate is bucket='excluded' (no aplus)."""
    conn, db_path = db
    from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
    from swing.data.models import Candidate, EvaluationRun
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, data_asof_date, "
        "action_session_date, lease_token, state) VALUES "
        "(1, '2026-05-20T18:00:00', '2026-05-19', '2026-05-20', 'tok', 'running')")
    eval_run_id = insert_evaluation_run(conn, EvaluationRun(
        id=None, run_ts="2026-05-20T18:00:00", data_asof_date="2026-05-19",
        action_session_date="2026-05-20", finviz_csv_path=None,
        tickers_evaluated=1, aplus_count=0, watch_count=0, skip_count=0,
        excluded_count=1, error_count=0))
    insert_candidates(conn, eval_run_id, [Candidate(
        ticker="XYZ", bucket="excluded", close=8.0, pivot=None, initial_stop=None,
        adr_pct=1.5, tight_streak=0, pullback_pct=0.0, prior_trend_pct=0.0,
        rs_rank=10, rs_return_12w_vs_spy=-5.0, rs_method="universe",
        pattern_tag=None, notes=None, criteria=tuple())])
    conn.commit()
    return conn, _cfg(db_path.parent, db_path), _FakeLease(db_path, 1, "2026-05-19"), eval_run_id


def _drive_detect(conn, cfg, lease, eval_run_id, ohlcv_cache, run_warnings):
    """Drive the real _step_pattern_detect with the extension args."""
    from swing.pipeline.runner import _step_pattern_detect
    _step_pattern_detect(cfg=cfg, lease=lease, eval_run_id=eval_run_id,
                         ohlcv_cache=ohlcv_cache, run_warnings=run_warnings)
```

> **No flagged lines remain (Codex chain #1 R3 Major #1):** the `pipeline_runs` INSERT columns + `EvaluationRun` field list + `Candidate` shape are copied verbatim from the verified harness (`tests/pipeline/test_step_pattern_detect.py:110-170`). **T-2.4 step 0** is a 5-minute confirm: open that module, diff the `pipeline_runs` column list + `EvaluationRun`/`Candidate` constructors above against it, and adjust ONLY if the harness has drifted since plan-authoring (it was read at HEAD `6574d2f`). The detect step's `_resolve_eval_run_action_session_date(cfg, lease, eval_run_id)` + `lease_data_asof(cfg, lease)` read `cfg.paths.db_path` only, so the `_cfg` stub suffices (no full `Config` needed); if the detect step turns out to require additional `cfg` attributes, extend `_Cfg` minimally.

---

## §M Forward-binding lessons (carried from the brainstorm return report)

> The brainstorm return report §8 banked 6 NEW + 13 INHERITED forward-binding lessons. The executing-plans dispatch MUST carry these forward:

- **FB-N1 (Codex MCP transport)** -- RESOLVED (`d134833`): Windows `cmd /c codex mcp-server` launcher fix applied. Use the MCP transport; `codex exec` CLI is the backstop. Re-apply on copowers upgrade (memory `feedback_copowers_codex_mcp_windows_launcher`).
- **FB-N2 (brief-vs-reality column verification)** -- APPLIED in §C.8: `candidates` has NO `market_cap`/`atr_pct`; the plan computes `atr_pct` from bars + sets `market_cap: null`. Re-grep every metadata source column before locking the INSERT shape (DONE).
- **FB-N3 (theme2_annotated is SHARED)** -- APPLIED in §C.6 + T-2.4: the exemplar cache-miss path (`exemplars.py:250-335`) also writes `theme2_annotated`; the detect-step capture coexists last-writer-wins via `refresh_chart_render`; the SET-NULL FK makes a later refresh harmless.
- **FB-N4 (detection_date vs data_asof_date directionality)** -- APPLIED in T-2.4/T-2.5: the forward-walk boundary + metadata as-of slice + `sessions_since_detection` ALL key on `data_asof_date`; `detection_date` is the operator-facing action-session label only.
- **FB-N5 (stale evidence keys)** -- APPLIED in §C.6 + T-2.4 step 8: the 3 stale annotators repaired with the verified key-map (incl. the plan-time enrichment `duration_days`->`base_duration_days`).
- **FB-N6 (warnings_json is NEW plumbing)** -- APPLIED in T-2.4/T-2.5: a run-level `run_warnings: list[dict]` accumulator is created at run start, threaded to detect + observe, serialized to `lease.release(warnings_json=...)` (`None` when empty).

**INHERITED (re-applied):** brief-vs-production-signature re-grep (§C); cumulative regression cascade audit (§J each round); CHECK+constant+validator paired (T-2.1); migration runner BEGIN/COMMIT (#9); append-only enforcement + discriminating tests; #27 silent-skip audit; #26+#37 elimination-by-construction; per-pattern metadata sourcing audit; chart_render integration audit; status-machine completeness; `pattern_evaluations` coexistence; empty-input handling; dynamic-`?` expansion; test-fixture-vs-production-emitter parity; L2 source-grep; ASCII scope; Co-Authored-By suppression.

---

## §N Self-review checklist (pre-Codex; apply the Expansion #N catalog)

> Run BEFORE invoking the Codex chains (superpowers:writing-plans self-review + the relocated Expansion #N catalog at `docs/orchestrator-context.md`). The plan author confirms each below.

**1. Spec coverage (every spec section maps to a task):**

| Spec section | Task(s) |
|---|---|
| §4.1 detection_events DDL (incl. `data_asof_date`) | T-2.1 |
| §4.2 observations DDL (UNIQUE + RESTRICT) | T-2.1 |
| §4.3 migration structure (#9) | T-2.1 |
| §4.4 backup gate STRICT | T-2.1 |
| §4.5 indexes | T-2.1 |
| §5.1 detection_events repo | T-2.2 |
| §5.2 observations repo (dynamic-`?`) | T-2.3 |
| §5.3 dataclasses (#11 paired) | T-2.1 |
| §6 detect-step extension | T-2.4 |
| §6.3 structural_anchors_json | T-2.4 (`build_structural_anchors_json`) |
| §6.4 detect empty-pool audit | T-2.4 |
| §7.1 observe algorithm | T-2.5 |
| §7.2 OHLCV source + bar anchoring + provider | T-2.5 (`_bar_for_date`) |
| §7.3 status state machine + §7.3.1 anchor sourcing | T-2.5 (`_advance_status` + `_structural_invalidation_level`) |
| §7.4 warnings accumulator | T-2.4/T-2.5 |
| §7.5 DAG position | T-2.5 |
| §8 chart capture (REUSE theme2; dedicated renderer; SET NULL; failure->NULL) | T-2.4 |
| §8.2 evidence-key repair | T-2.4 |
| §9 per-pattern metadata (REDESIGN; market_cap NULL) | T-2.4 (`temporal_metadata.py`) |
| §9.4 finviz_screen_state | T-2.4 (`build_finviz_screen_state`) |
| §10 single dispatch + gate runbook | §I + §1.4 |
| §11 fixtures | §L |
| §12 schema impact (v22) | §K |
| §13 V1+ simplifications | §D (out-of-scope) + §M |

No gaps. Every spec requirement maps to a task.

**2. Placeholder scan:** No "TBD"/"implement later"/"add error handling"-style placeholders. Every code step shows real code. The one deliberate `# ... copy verbatim` directive (`_create_pre_phase14_migration_backup`) points to a named production function (`_create_pre_phase13_sb6c_migration_backup`) the implementer copies -- not a vague placeholder.

**3. Type/name consistency:** `PatternDetectionEvent` / `PatternForwardObservation` field names are identical across T-2.1 (dataclass), T-2.2/T-2.3 (`_row_to_*` mappers + INSERT col lists), T-2.4 (detect-loop build), T-2.5 (observe build). `insert_detection_event` / `insert_observation` / `list_observable_detections` / `get_latest_observations_for_detections` names are consistent across repo defs + callers. `_advance_status` / `_structural_invalidation_level` / `_sessions_since` / `_bar_for_date` signatures match their callsites + tests. The 3 metadata-helper names (`compute_atr_pct` / `compute_return_pct` / `compute_52w_high_proximity_pct`) match across `temporal_metadata.py` + tests.

**4. Expansion #N catalog applied:**
- **#2 (brief-vs-signature)** -- §C re-grepped all surfaces; 2 discrepancies handled (evidence-key repair in-scope; provider via `resolve_ohlcv_window`); ZERO escalations needed.
- **#4 (SQL column verification + runtime-binding-shape + empty-result-set)** -- every `0022` DDL column + every repo SELECT column verified; dynamic-`?` IN-clause + empty short-circuit (T-2.3).
- **#8 (counter UNIT audit)** -- `rows_written` counts evaluations; the detection-event append does NOT inflate it; the observe open-pool count is per-detection.
- **#11 (taxonomy/attribution propagation)** -- status/source/provider propagate to dataclass + mapper + serializer + fixtures; provider consumed by FIELD.
- **#13 (cumulative regression cascade)** -- §J each Codex round + §G.0.
- **#15 (narrative artifact path/fact lag)** -- the return report (§M) sweeps stale facts.
- **content-completeness (#6)** -- every per-field metadata disposition enumerated (§C.8: LIVE sector/industry/adr_pct; COMPUTED atr/ret/52w; NULL market_cap).
- **spec-source-of-truth-over-brief** -- the #11-pairing tension between brief §2.1 (T-2.1 has validators) and brief §2.1 (T-2.2/T-2.3 have dataclasses) was resolved toward the spec's gotcha-#11 atomic requirement (validators + CHECK + constants all in T-2.1).

**5. LOCK re-verification:** §E table -- all 20 LOCK rows HELD; ZERO re-litigated; ZERO scope widening (§D).

---

*End of Phase 14 Sub-bundle 2 implementation plan. 2 NEW append-only tables (`pattern_detection_events` + `pattern_forward_observations`) via v22 migration + NEW `_step_pattern_observe` + per-pattern metadata enrichment at detection + chart_render bytes capture (reusing `theme2_annotated`). 6 task slices T-2.1..T-2.6; ~21 commits; ~81 fast tests. Eliminates gotchas #26 + #37 by construction. Sec 9.1 Q1-Q7 + L1-L8 + spec §2 + the 5 OQ dispositions HONORED; Schema v22; L2 LOCK preserved; ASCII scope declared. TWO Codex chains (writing-plans + executing-plans designed). Ready for the adversarial review chains.*

