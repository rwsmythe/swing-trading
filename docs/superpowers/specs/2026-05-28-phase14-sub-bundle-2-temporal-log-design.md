# Phase 14 Sub-bundle 2 -- Temporal Pattern Detection + Observation Log Infrastructure -- Design Spec

**Status:** Brainstorm DRAFT. Per Phase 14 commissioning brief Sec 9.1 LOCKs (operator-paired 2026-05-27 PM #4) + Sub-bundle 2 dispatch brief §1 LOCKs (this sub-bundle).

**Phase 14 commissioning context:** Phase 14 commissioned at main `bf7e071`; Sec 9.1 LOCKs committed at `7a558e4`; Sub-bundle 1 (data-wiring) SHIPPED end-to-end at `e323339`; housekeeping at `a730a05`; CLAUDE.md compression at `665cab0`. THIS dispatch is Sub-bundle 2 (temporal log V1+) of 5 serial sub-bundles.

**Branch:** `phase14-sub-bundle-2-temporal-log-brainstorming` from main `665cab0`.

**Scope:** Ship the **temporal pattern detection + observation log infrastructure** -- 2 NEW append-only tables (`pattern_detection_events` + `pattern_forward_observations`) via a v22 schema migration, a NEW `_step_pattern_observe` pipeline step, per-pattern metadata enrichment at detection time, and chart_render bytes capture at detection time (V1+ scope per Sec 9.1 Q3 LOCK). This is the highest-leverage methodological improvement surfaced at the close of the applied research arc (Turn H 2026-05-27 PM #3): it **eliminates cumulative gotchas #26 (OHLCV archive bar-content TEMPORAL mutation) + #37 (substrate-freshness sensitivity) by architectural construction** -- forward-walk observation; no archive re-read; no regeneration.

**OUT-OF-SCOPE** (per dispatch brief §4): backfill of `pattern_detection_events` from existing `pattern_evaluations`; cross-pattern composite signals; the real-time ruleset replay engine (Phase 15+; the substrate ENABLES it but Sub-bundle 2 does not build it); operator failure-mode classification surface (V1++); ML re-ranker; sell-side / paper-trading hooks; drift monitoring; chart-render backfill for historical detections; multi-source same-detection-date dedupe; active monitoring/alerting; any other Phase 14 sub-bundle (chart-surface uniformity / review+journal / metrics); Phase 15+; Schwab API integration changes (L2 LOCK); NEW HTMX endpoints; schema migrations beyond v22.

---

## §0 Glossary

| Term | Definition |
|---|---|
| **Temporal log** | The 2-table append-only substrate (`pattern_detection_events` + `pattern_forward_observations`) that records pattern detections and their day-by-day forward price path. |
| **Forward-walk** | Each daily pipeline run records THAT DAY's bar against open detections; the log only ever appends; it is never regenerated from a current-archive read. This is the architectural property that eliminates gotchas #26 + #37. |
| **Detection event** | One row in `pattern_detection_events`: a pattern identified for a `(ticker, detection_date, pattern_class)` with its structural anchors + composite score + per-pattern metadata + finviz/screen state, all LOCKED at detection time. |
| **Forward observation** | One row in `pattern_forward_observations`: one trading day's OHLC for an open detection, LOCKED at observation, with a ruleset-agnostic lifecycle `status`. |
| **`_step_pattern_detect`** | Existing Phase 13 pipeline step at `swing/pipeline/runner.py:1396`; runs the 5 V1 geometric detectors over `bucket=='aplus'` candidates; writes `pattern_evaluations`. Sub-bundle 2 EXTENDS it to ALSO append `pattern_detection_events` (L7). |
| **`_step_pattern_observe`** | NEW pipeline step; enumerates open detections; appends today's bar + a lifecycle status to `pattern_forward_observations`. Positioned AFTER detect, BEFORE charts. |
| **DETECTOR_PATTERN_CLASSES** | `('vcp', 'flat_base', 'cup_with_handle', 'high_tight_flag', 'double_bottom_w')` -- the 5 V1 detector classes (migration `0020` line 70-73; `swing/data/models.py`). |
| **`theme2_annotated`** | Existing `chart_renders.surface` enum value (migration `0020` line 179-182); pattern-bound (CHECK requires `pattern_class` + `pipeline_run_id` non-NULL); cache key `(ticker, surface, pipeline_run_id, pattern_class)`. The V1+ chart capture surface (no chart_renders CHECK widening needed). |
| **L2 LOCK** | Project invariant -- ZERO new Schwab API calls (`schwabdev.Client.*`); the multiset-Counter source-grep test at `tests/integration/test_l2_lock_source_grep.py` (baseline `bf7e071`) MUST continue passing. |
| **Replay** | A FUTURE (Phase 15+) operation: apply a ruleset's stop/target/entry rules to the recorded `ohlc_today_json` path of an observation chain, deterministically + reproducibly, without re-fetching. Sub-bundle 2 produces the substrate; it does NOT build the replay engine. |

---

## §1 Architecture overview

### §1.1 The substrate + why it eliminates #26 and #37 by construction

The applied research arc (D1 -> D2 -> R2-A -> R2-D -> V2-mechanic -> G2) repeatedly hit two architectural failure modes when reconstructing forward outcomes retroactively from the OHLCV archive:

- **Gotcha #26 (OHLCV archive bar-content TEMPORAL mutation):** the legacy archive's `write_window` uses `drop_duplicates(keep='last')`; re-fetching from yfinance at a later date silently drifts historical bar content ~0.5-3% (late-reporting, volume corrections, split/dividend retroactive adjustment). Any metric reconstructed by reading the archive "as of" a past date is therefore non-reproducible.
- **Gotcha #37 (substrate-freshness sensitivity):** cohort fixtures regenerated across time shift their FILTERED membership (e.g., `max_observed_asof_date` recomputation moves patterns in/out of recency windows), so a prior-arc expectancy anchor may not reproduce against the same nominal cohort later.

**The temporal log eliminates both by construction:**

1. **No archive re-read.** Each daily pipeline run records THAT DAY's bar (`ohlc_today_json`) at observation time. The bar is captured once, frozen, never re-derived from a later archive read. (#26 cannot occur -- there is no time-travel read.)
2. **No regeneration.** The detection event's `structural_anchors_json` + `composite_score` + `per_pattern_metadata_json` are LOCKED at detection and never recomputed. The log only appends; it is never regenerated from current state. (#37 cannot occur -- there is no cohort-fixture re-derivation.)
3. **Append-only forward-walk.** The substrate grows organically: each day's Finviz screen produces a new batch of A+ candidates; detections accumulate; observations accumulate day by day. Multi-month accumulation routinely surfaces N>=200+ patterns, enabling robust statistical defensibility for FUTURE investigations -- without retroactive reconstruction.
4. **Backtest = replay.** A future ruleset is evaluated by REPLAYING the recorded observation path against the ruleset definition -- deterministic, reproducible, drift-free.

This invariant pair is **L2 of the Sub-bundle 2 phase-specific LOCKs** and is stated normatively at §2.3.

### §1.2 Two tables, separation of concerns (commissioning brief Sec 2.5 LOCK)

The substrate is **two** append-only tables, NOT one (LOCKED at commissioning brief Sec 2.5; HOLD against any Codex consolidation pushback per dispatch brief §7):

- `pattern_detection_events` -- the **frozen** detection record. One row per `(ticker, detection_date, pattern_class, source)` (V1+: source always `'pipeline'`, so effectively one per `(ticker, pipeline_run_id, pattern_class)`). Written ONCE by the extended `_step_pattern_detect`.
- `pattern_forward_observations` -- the **append-only forward-walk** record. Many rows per detection (one per observed trading day). Written daily by `_step_pattern_observe`.

The separation is load-bearing: detection events are immutable structural facts (frozen at detection); observations are an append-only time series (one new row per day). Conflating them into a single table would either denormalize the frozen detection fields across every observation row (waste + drift risk) or force UPDATE semantics on the detection row (violates append-only). The two-table shape is the correct normalization.

### §1.3 Coexistence with `pattern_evaluations` (L7)

`_step_pattern_detect` already writes `pattern_evaluations` (migration `0020`; the per-run detector-verdict cache, `ON DELETE CASCADE` on `pipeline_run_id`). Sub-bundle 2 **EXTENDS** the step to ALSO append `pattern_detection_events` from the SAME `resolved_emit_list` (zero additional detector invocations). The two coexist:

| | `pattern_evaluations` (existing) | `pattern_detection_events` (NEW) |
|---|---|---|
| Purpose | per-run detector-verdict cache | permanent forward-walk detection substrate |
| Cardinality | one per `(pipeline_run_id, ticker, pattern_class)` | one per `(source, ticker, detection_date, pattern_class)` |
| `pipeline_run_id` FK | `ON DELETE CASCADE` (verdict dies with the run) | `ON DELETE SET NULL` (detection SURVIVES run pruning) |
| Lifecycle | ephemeral (regenerated each run; CASCADE-prunable) | permanent (append-only; never cascade-deleted) |
| Extra metadata | none | per-pattern metadata + finviz screen state + chart_render_id |
| Forward observations | none | linked via `pattern_forward_observations` |

No deprecation of `pattern_evaluations` in V1+; both written in the same pass. The existing detector tests continue passing unchanged (L7 backwards-compat).

### §1.4 Daily pipeline integration (the DAG)

The pipeline orchestrator (`swing/pipeline/runner.py:775-961`) sequences best-effort steps. The current order:

```
evaluate -> daily_management -> watchlist -> recommendations -> pattern_detect
    -> schwab_snapshot -> schwab_orders -> charts -> export -> complete
```

Sub-bundle 2:
- **EXTENDS** `_step_pattern_detect` (already at `pattern_detect`) to append `pattern_detection_events` + capture chart bytes.
- **INSERTS** `_step_pattern_observe` AFTER `pattern_detect` and BEFORE `charts` (specifically right after the `pattern_detect` best-effort block at runner.py ~854, before `schwab_snapshot`). New `lease.step("pattern_observe")` breadcrumb + best-effort try/except mirroring the `pattern_detect` shape.

Both steps are zero-cost in DETECTOR terms (no new detector invocations beyond the 5 already run). The chart capture reuses bars already fetched in the detect loop; the observe step reuses the same `OhlcvCache` instance (§7.2 fetch-scope analysis).

### §1.5 Schema impact

**Sub-bundle 2 introduces Schema v22.** Exactly ONE migration file (`0022_phase14_temporal_log.sql`) adds the 2 NEW tables (+ indexes + CHECK constraints + FKs). `EXPECTED_SCHEMA_VERSION` bumps 21 -> 22. New `_phase14_backup_gate` with STRICT equality `current_version == 21`. NO other schema changes (the chart capture REUSES the existing `theme2_annotated` surface -- no `chart_renders` CHECK widening). Detail at §4 + §12.

### §1.6 L2 LOCK preservation

ZERO new `schwabdev.Client.*` call sites. The detect-step chart capture reuses already-fetched bars + the matplotlib renderer (no API). The observe step reads bars via the existing `OhlcvCache` ladder (archive + yfinance; never Schwab unless production+configured, which is the pre-existing gate). Discriminating source-grep test at §11.4 (existing `tests/integration/test_l2_lock_source_grep.py`).

---

## §2 Pre-locked operator decisions (verbatim per dispatch brief §1; BINDING)

### §2.1 Sec 9.1 LOCKs (commissioning-time; binding for all Phase 14 sub-bundles)

| # | Decision | LOCKed value |
|---|---|---|
| Q1 | Sub-bundle sequencing | data-wiring (SHIPPED) -> **temporal log V1+ (THIS SUB-BUNDLE)** -> charts -> review+journal -> metrics |
| Q2 | Execution mode | SERIAL (Sub-bundle 2 depends on Sub-bundle 1 merge) |
| Q3 | Temporal log V1 scope | **V1+** -- base (2 tables + `_step_pattern_observe` + per-pattern metadata) PLUS chart_render bytes capture at detection time (closes CR.1 dependency) |
| Q6 | Close-out | all 5 sub-bundles merged + operator browser-witnessed verification at each merge (incl. v22 schema verification) |
| Q7 | Codex chain count | SINGLE chain at end for THIS brainstorming phase; revisit at writing-plans phase if analytical-substrate-changing dimensions warrant gotcha #36 two-chain default (§15.5 evaluation) |

### §2.2 Sub-bundle 2 phase-specific LOCKs (dispatch brief §1.3)

- **L1** Append-only invariant on BOTH tables (INSERT-only; no UPDATE; no DELETE). Repo layer enforces (no `update_*`/`delete_*` functions); UNIQUE constraints + discriminating tests mirror.
- **L2** Forward-walk semantic ONLY -- gotchas #26 + #37 ELIMINATED BY CONSTRUCTION (no archive re-read; no regeneration). Stated normatively at §2.3.
- **L3** v22 schema migration -- gotcha #11 paired discipline (CHECK + Python constant + dataclass validator in the SAME task); gotcha #9 explicit `BEGIN`/`COMMIT`/`ROLLBACK`; backup-gate STRICT equality `pre_version == 21`.
- **L4** `_step_pattern_observe` is zero-cost beyond existing detector invocations: it reads the open-detection set + appends today's bar + status; no NEW fetch infrastructure (reuses the `OhlcvCache` ladder, archive-first). Fetch-scope nuance at §7.2 + OQ-17.
- **L5** Chart_render bytes capture at detection time (Sec 9.1 Q3 V1+ LOCK) -- integrates with the existing `chart_renders` table + `chart_jit` substrate; REUSES the `theme2_annotated` surface (§8).
- **L6** Per-pattern metadata at detection time -- captured (not reconstructed later) for future stratified analysis; per-field source-of-truth at §9 (NOTE: market_cap + true ATR are NOT persisted to `candidates` -- §9 redesign + OQ-16).
- **L7** `_step_pattern_detect` EXTENDED (not replaced); `pattern_evaluations` continues to receive rows; `pattern_detection_events` is ADDITIONAL substrate.
- **L8** L2 LOCK preserved -- ZERO new Schwab API calls; existing multiset source-grep test continues passing.

### §2.3 The forward-walk + append-only invariant (NORMATIVE; L1 + L2)

> **INVARIANT (L1 + L2):** `pattern_detection_events` and `pattern_forward_observations` are APPEND-ONLY. No application code path ever UPDATEs or DELETEs a row. The **immutable detection FACTS** -- `structural_anchors_json`, `composite_score`, `per_pattern_metadata_json`, `pattern_class`, `detection_date`, `data_asof_date`, `ticker`, `source`, `detector_version` -- are LOCKED at detection time and NEVER change. `pattern_forward_observations.ohlc_today_json` is LOCKED at observation time and is NEVER re-fetched from a later archive read. The substrate is never regenerated from current state. This is the architectural property that eliminates **gotcha #26 (OHLCV archive bar-content TEMPORAL mutation)** and **gotcha #37 (substrate-freshness sensitivity)** by construction.

> **Frozen-FACTS vs nullable-audit-linkage distinction (Codex R1 C#1 + M#4; REFINED at R2 C#1 + C#2):** the append-only / frozen invariant covers the detection FACTS above. The two NULLABLE referential-pointer columns -- `pipeline_run_id` and `chart_render_id` -- are AUDIT LINKAGES, not facts. A referential-integrity `ON DELETE SET NULL` that severs a dangling pointer when the referenced row is pruned is a referential action, NOT a semantic mutation of a frozen fact. **BOTH use `ON DELETE SET NULL`** (R2 resolution): (a) `pipeline_run_id` -- a pipeline_run row may be pruned (e.g., to cascade-clean its `pattern_evaluations`); the detection SURVIVES with the linkage degraded to NULL. (b) `chart_render_id` -- the chart bytes captured at detection live in the EPHEMERAL run-scoped `chart_renders` cache (whose own `pipeline_run_id` is `ON DELETE CASCADE`, migration `0020:183`); the captured chart is a BEST-EFFORT cache SNAPSHOT, not a frozen fact. Pinning a permanent detection to an ephemeral run-scoped cache row via `RESTRICT` was an over-reach (Codex R1 C#1 initially pushed there, but R2 C#2 showed RESTRICT deadlocks the run-prune CASCADE, and R2 C#1 showed the `theme2_annotated` surface is ALREADY written by the exemplar cache-miss path at `swing/web/view_models/patterns/exemplars.py:223-321`). With SET NULL, the detect step + the exemplar path coexist as last-writer-wins cache writers; the detection records whatever `chart_render_id` was current at detection; if a later refresh replaces that cache row, the pointer degrades to NULL gracefully -- the FACTS are untouched. A guaranteed-permanent immutable detection chart is a V2 candidate (a dedicated non-cache store; §13 #6). This is the deliberate, explicitly-accepted FK posture; §4.1 + §8.3 carry the rationale in-line.

This invariant is HELD against Codex pushback (dispatch brief §7): if Codex proposes an UPDATE path (e.g., "re-classify a detection's composite_score on a better detector version"), the answer is to INSERT a NEW detection event (a new detection_date / a new source / a new run), never to mutate the frozen row.

### §2.4 Architectural primitive (commissioning brief Sec 2.5 LOCK)

The 2-table shape is LOCKED at commissioning. This spec validates the primitive against the actual schema landscape + adjusts column types/FK semantics/indexes per code-read (§4), but does NOT re-litigate the 2-table design, the V1+ scope (chart capture), or the append-only invariant.

---

## §3 Module touch list

| Path | Type | Purpose |
|---|---|---|
| `swing/data/migrations/0022_phase14_temporal_log.sql` | NEW | v22 migration: 2 NEW tables + indexes + CHECK + FK. Explicit `BEGIN;`/`COMMIT;` + `UPDATE schema_version SET version = 22;` as FINAL statement (gotcha #9; migration `0021` precedent). |
| `swing/data/db.py` | MODIFIED | `EXPECTED_SCHEMA_VERSION` 21 -> 22; NEW `PHASE14_PRE_MIGRATION_EXPECTED_TABLES` (= `PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES`; v21 added no tables); NEW `_create_pre_phase14_migration_backup` (filename `swing-pre-phase14-migration-<ISO>.db`); NEW `_phase14_backup_gate` (STRICT `current_version == 21 AND target_version >= 22`); wire the gate into `run_migrations`; extend the module docstring comment block. |
| `swing/data/models.py` | MODIFIED | NEW `PatternDetectionEvent` + `PatternForwardObservation` frozen dataclasses (mirror `PatternEvaluation`/`ChartRender` shape) with `__post_init__` validators; NEW module constants `_PATTERN_DETECTION_SOURCE_VALUES`, `_FORWARD_OBSERVATION_STATUS_VALUES`, `_FORWARD_OBSERVATION_STATUS_CHANGE_EVENTS` (gotcha #11 paired discipline). |
| `swing/data/repos/pattern_detection_events.py` | NEW | Append-only repo: `insert_detection_event(conn, event) -> int`; `get_detection_event_by_id`; `list_detection_events(...)`; `list_observable_detections(conn, *, source='pipeline') -> list[...]` (open-status detections for the observe step). Caller-tx contract (NO `conn.commit()`). NO `update_*`/`delete_*`. |
| `swing/data/repos/pattern_forward_observations.py` | NEW | Append-only repo: `insert_observation(conn, observation) -> int`; `get_observations_for_detection(conn, detection_id) -> list[...]` (the chain, ordered by observation_date); `get_latest_observation_for_detection(conn, detection_id) -> ... | None`; `get_latest_observations_for_detections(conn, detection_ids) -> dict[int, ...]` (batch latest-status read for the observe step; dynamic `?` expansion per gotcha re: sqlite3 list-bind). Caller-tx. NO `update_*`/`delete_*`. |
| `swing/pipeline/runner.py` | MODIFIED | (a) EXTEND `_step_pattern_detect` Pass-2 loop to append a `pattern_detection_events` row per emitted verdict + capture chart bytes (chart_render_id FK); harden its empty-pool early-return (1485-1490) with a gotcha #27 warnings audit. (b) NEW `_step_pattern_observe`. (c) wire `lease.step("pattern_observe")` + best-effort block into the DAG after `pattern_detect`. (d) thread a run-level warnings accumulator to `lease.release(warnings_json=...)` (§7.4). |
| `swing/web/chart_jit.py` (+ a NEW `render_and_capture_detection_chart` helper; module decided at writing-plans -- chart_jit vs a new pipeline-side helper) | MODIFIED/NEW | Register `theme2_annotated` -> `render_theme2_annotated_svg` (the DEDICATED renderer at `swing/web/charts.py:481`; Codex R1 M#1) and add a caller-tx helper returning `(chart_render_id)` via the standard `refresh_chart_render` (Codex R1 m#2; R2 C#1 -- coexists last-writer-wins with the exemplar theme2_annotated writer). Renderer-kwargs uniformity LOCK (Expansion #10c). |
| `swing/web/charts.py` | MODIFIED (evidence-key repair) | Repair the annotation path's STALE evidence-key reads (`top_of_range`/`bottom_of_range`/`depth_ratio`/`pole_advance_pct` at charts.py:411-447) to the ACTUAL detector evidence field names (`range_top_price`/`range_bottom_price`/`cup_depth_pct`/`pole_pct`) so captured charts are correctly annotated (Codex R1 M#2). Writing-plans confirms the exact stale-key surface (hyprec vs theme2 renderer). |
| `swing/pipeline/temporal_metadata.py` (or inline in runner) | NEW (likely) | Pure-bars helpers `compute_atr_pct(bars, asof)`, `compute_return_pct(bars, asof, lookback_sessions)`, `compute_52w_high_proximity_pct(bars, asof)` for per-pattern metadata (§9). Writing-plans phase chooses module vs inline. |
| `tests/data/test_temporal_log_migration.py` | NEW | v22 migration apply + idempotency + backup-gate strict-equality + rollback-through-runner + append-only schema verification. |
| `tests/data/repos/test_pattern_detection_events_repo.py` | NEW | Repo discriminating tests (insert / get / list / list_observable; append-only -- no update/delete functions exist; UNIQUE constraint). |
| `tests/data/repos/test_pattern_forward_observations_repo.py` | NEW | Repo discriminating tests (insert / chain read / latest / batch-latest; append-only). |
| `tests/pipeline/test_step_pattern_detect_temporal_extension.py` | MODIFIED/NEW | detect-step extension: detection events appended; per-pattern metadata; chart_render_id populated/NULL-on-failure; empty-pool warnings audit. |
| `tests/pipeline/test_step_pattern_observe.py` | NEW | observe-step: open-detection enumeration; today's-bar append; status state machine transitions; empty-pool warnings audit; idempotency (no dupe observation for same `(detection_id, observation_date)`). |
| `tests/web/test_chart_jit_theme2_annotated.py` | NEW/MODIFIED | theme2_annotated dispatch + cache-key + renderer-kwargs uniformity + cache-collision (call_count). |
| `tests/integration/test_l2_lock_source_grep.py` | UNCHANGED (verify-passes) | L2 LOCK preserved; multiset baseline `bf7e071`. |

**Estimated footprint:** 1 NEW migration + ~2-3 swing/ source files MODIFIED + 2 NEW repos + 1-2 NEW helper module/functions + ~6-8 NEW/MODIFIED test modules. Per commissioning brief Sec 2.5 estimate: ~15-25 commits + ~50-100 tests; v22 migration. Sub-bundle decomposition at §10.

---

## §4 v22 schema migration design

### §4.1 `pattern_detection_events` DDL

```sql
CREATE TABLE pattern_detection_events (
    detection_id INTEGER PRIMARY KEY AUTOINCREMENT,
    ticker TEXT NOT NULL,
    detection_date TEXT NOT NULL,            -- action_session_date: the forward-looking session this detection was prepped FOR (the detect step's asof_run anchor; runner.py:1499)
    data_asof_date TEXT NOT NULL,            -- the detector's DATA cutoff = last completed bar the detector saw (the run's data_asof_date / lease_data_asof). Forward-walk boundary anchor (Codex R2 M#1).
    pattern_class TEXT NOT NULL CHECK (pattern_class IN (
        'vcp', 'flat_base', 'cup_with_handle',
        'high_tight_flag', 'double_bottom_w'
    )),
    structural_anchors_json TEXT NOT NULL,   -- LOCKED at detection (full evidence asdict; contains per-class anchors)
    composite_score REAL NOT NULL,           -- LOCKED at detection
    detector_version TEXT NOT NULL,          -- the detector version string (provenance)
    finviz_screen_state TEXT,                -- canonicalized screen/eval state JSON (nullable for non-pipeline sources)
    source TEXT NOT NULL CHECK (source IN (
        'pipeline', 'v2_cohort', 'd2_baseline', 'backfill', 'synthetic'
    )),
    per_pattern_metadata_json TEXT NOT NULL, -- LOCKED (sector/industry/adr_pct/atr_pct/ret_90d/prox_52w/market_cap-or-null)
    pipeline_run_id INTEGER
        REFERENCES pipeline_runs(id) ON DELETE SET NULL,  -- AUDIT LINKAGE: detection SURVIVES run pruning; SET NULL is a referential action, not a fact mutation (R1 M#4)
    chart_render_id INTEGER
        REFERENCES chart_renders(id) ON DELETE SET NULL,  -- AUDIT LINKAGE to the ephemeral run-scoped chart cache (R2 C#1+C#2): best-effort capture; NULL if render failed at capture (gotcha #27 audit) OR if a later cache refresh replaces the row
    created_at TEXT NOT NULL                 -- INSERT timestamp (ISO)
);

-- One detection per (source, ticker, detection_date, pattern_class). For
-- source='pipeline', detection_date == the run's action_session_date, so this
-- is effectively one per (ticker, pipeline_run_id, pattern_class) -- mirroring
-- the pattern_evaluations unique index, but keyed on detection_date (not run_id)
-- so non-pipeline sources (V2) with NULL run_id still get a stable key.
-- (data_asof_date is NOT in the unique key -- it is a function of the run; the
-- forward-walk boundary uses it but the identity key stays on detection_date.)
CREATE UNIQUE INDEX idx_pde_source_ticker_date_class
    ON pattern_detection_events(source, ticker, detection_date, pattern_class);

-- Per-ticker historical lookup (journal/metrics surfaces; future).
CREATE INDEX idx_pde_ticker_date
    ON pattern_detection_events(ticker, detection_date);

-- Per-pattern-class strata (future stratified analysis).
CREATE INDEX idx_pde_class_date
    ON pattern_detection_events(pattern_class, detection_date);

-- Run linkage lookup.
CREATE INDEX idx_pde_pipeline_run_id
    ON pattern_detection_events(pipeline_run_id);
```

**Design notes:**
- `source` CHECK enum LOCKed to 5 values; V1+ writes only `'pipeline'`. The other 4 reserve future ingestion paths (banked OUT-OF-SCOPE for V1+; the enum is forward-compat so a V2 backfill needs no further CHECK widening).
- `pipeline_run_id ON DELETE SET NULL` (NOT CASCADE): the detection is a PERMANENT record; pruning a `pipeline_runs` row must not delete the detection (only sever the audit linkage). This is the deliberate asymmetry vs `pattern_evaluations` (CASCADE). HOLD against any "make it consistent with pattern_evaluations" pushback -- the asymmetry is intentional + load-bearing for the append-only substrate. Per the §2.3 frozen-FACTS-vs-nullable-audit-linkage distinction, the SET NULL is a referential action on an audit pointer, not a mutation of a frozen fact.
- `chart_render_id ON DELETE SET NULL` (FINAL, Codex R2 C#1 + C#2; the R1 RESTRICT attempt was reverted): `chart_renders` is an EPHEMERAL run-scoped cache -- its own `pipeline_run_id` is `ON DELETE CASCADE` (migration `0020:183`). RESTRICT would deadlock the run-prune CASCADE (you could never delete a pipeline_run that produced a detection-referenced chart row -- contradicting the `pipeline_run_id SET NULL` prunability rationale). Worse, the `theme2_annotated` surface is NOT exclusively ours: the exemplar cache-miss path at `swing/web/view_models/patterns/exemplars.py:223-321` ALREADY renders + `refresh_chart_render`s `theme2_annotated` rows keyed by `(ticker, latest_completed_pipeline_run, pattern_class)` against the SAME partial unique index (`0020:219`). So both writers share the surface as a last-writer-wins cache. SET NULL makes this coexistence safe: the detection records whatever `chart_render_id` was current at detection; if the exemplar path (or a re-run) later refreshes that cache key, the pointer degrades to NULL -- the detection FACTS are untouched (§2.3). The captured chart is a best-effort SNAPSHOT; permanence is a V2 candidate (§13 #6).
- `detector_version` added beyond the brief's Sec 2.5 sketch: provenance for which detector emitted the row (the brief's `composite_score` is "LOCKED at detection"; `detector_version` records WHICH detector produced it -- important when detectors evolve). Mirrors `pattern_evaluations.detector_version`.
- **`detection_date` vs `data_asof_date` (Codex R2 M#1):** the runner computes BOTH `action_session_date` (the forward-looking NEXT session, `swing/evaluation/dates.py:43`) and `data_asof_date` (the last completed bar, `dates.py:21`). The detect step's `asof_run` anchor is `action_session_date` (runner.py:1499), so `detection_date = action_session_date` (the operator-facing label the verdict is FOR; consistent with `pattern_evaluations`). BUT the detector's information cutoff is `data_asof_date` (the last bar it saw). The forward-walk boundary therefore uses `data_asof_date`, NOT `detection_date` -- otherwise (with `detection_date` = a not-yet-traded action session) the strict `> detection_date` boundary would skip the first tradable session's bar. `data_asof_date` is stored on the detection so the observe step's boundary (`detection.data_asof_date < observation_date`) is self-contained (§7.1). Available at detect time via `lease_data_asof(cfg, lease)` (runner.py:977).

### §4.2 `pattern_forward_observations` DDL

```sql
CREATE TABLE pattern_forward_observations (
    observation_id INTEGER PRIMARY KEY AUTOINCREMENT,
    detection_id INTEGER NOT NULL
        REFERENCES pattern_detection_events(detection_id) ON DELETE RESTRICT,  -- append-only invariant
    observation_date TEXT NOT NULL,          -- the trading session this bar belongs to (ISO)
    ohlc_today_json TEXT NOT NULL,           -- LOCKED at observation; never re-fetched ({open,high,low,close,volume})
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
    sessions_since_detection INTEGER NOT NULL,  -- bounded-window bookkeeping (derived; persisted for cheap queries)
    created_at TEXT NOT NULL,                 -- INSERT timestamp (ISO)

    UNIQUE (detection_id, observation_date)
);

-- Observe-step "open detections" scan: most-recent observation per detection
-- whose status is in the open set. The composite index supports the
-- per-detection latest-status read.
CREATE INDEX idx_pfo_detection_date
    ON pattern_forward_observations(detection_id, observation_date);

-- Date-range queries for future backtest replay.
CREATE INDEX idx_pfo_observation_date
    ON pattern_forward_observations(observation_date);

-- Status-strata scan (e.g., "all currently-open detections").
CREATE INDEX idx_pfo_status
    ON pattern_forward_observations(status);
```

**Design notes:**
- `detection_id ON DELETE RESTRICT`: you cannot delete a detection that has observations (append-only invariant; the forward-walk record is permanent). HOLD against any cascade-delete pushback.
- The `status` CHECK allows ALL 6 values for forward-compatibility, BUT V1+ only EMITS the ruleset-agnostic subset `{pending, triggered_open, invalidated, expired}` (§7.3 + OQ-18). The `triggered_closed_at_target`/`triggered_closed_at_stop` values are reserved for the Phase 15+ replay engine (which is OUT-OF-SCOPE). Documented prominently in the migration comment + the dataclass docstring so a future maintainer does not mistake the dead V1+ values for a wiring gap.
- `status_change_event` is nullable (NULL when `status == 'pending'` and no transition fired); the V1+ emitted subset uses `{entry_fired, shape_break, time_exit, observation_horizon_reached}` (the `stop_fired`/`target_fired` events pair with the reserved closed_at_* statuses).
- `sessions_since_detection` is persisted (not just derived) so the observe-step's open-set scan + the expiry/horizon predicates are cheap (no per-row date arithmetic in SQL). It is the count of trading sessions from the detection's **`data_asof_date`** (the detector data cutoff -- the forward-walk origin) UP TO AND INCLUDING `observation_date` (Codex R3 M#2 -- measured from `data_asof_date`, NOT the forward-looking `detection_date` action-session label; the two differ and the boundary/window predicates at §7.3 all use `data_asof_date` for consistency). It is a deterministic function of `(observation_date, detection.data_asof_date)` -- not an independent fact -- but persisting it is a standard denormalization for query cheapness; the discriminating test asserts it equals the computed trading-session delta from `data_asof_date`.

### §4.3 Migration file structure (gotcha #9)

`0022_phase14_temporal_log.sql` follows the `0020`/`0021` precedent exactly:

```sql
-- 0022_phase14_temporal_log.sql
-- Phase 14 Sub-bundle 2 -- v22 migration: temporal pattern detection +
-- observation log infrastructure (2 NEW append-only tables).
-- Atomic via explicit BEGIN; ... COMMIT; per CLAUDE.md gotcha #9
-- (executescript implicit COMMIT) + migration 0021 precedent.
-- Bumps schema_version 21 -> 22.

BEGIN;

CREATE TABLE pattern_detection_events ( ... );
CREATE UNIQUE INDEX idx_pde_source_ticker_date_class ON ...;
CREATE INDEX idx_pde_ticker_date ON ...;
CREATE INDEX idx_pde_class_date ON ...;
CREATE INDEX idx_pde_pipeline_run_id ON ...;

CREATE TABLE pattern_forward_observations ( ... );
CREATE INDEX idx_pfo_detection_date ON ...;
CREATE INDEX idx_pfo_observation_date ON ...;
CREATE INDEX idx_pfo_status ON ...;

UPDATE schema_version SET version = 22;   -- MUST be FINAL statement before COMMIT

COMMIT;
```

The runner (`swing/data/db.py:_apply_migration`) wraps `executescript` in `PRAGMA foreign_keys=OFF` + try/except `rollback()`+re-raise; the migration's own explicit `BEGIN;`/`COMMIT;` makes `conn.rollback()` able to undo partial DDL on failure (gotcha #9). No table rebuilds in this migration (pure additive CREATE TABLE), so the FK-cascade-wipe risk that motivated `foreign_keys=OFF` does not apply here -- but the discipline is inherited uniformly.

### §4.4 Backup gate (gotcha #11 strict-equality form)

```python
# swing/data/db.py
PHASE14_PRE_MIGRATION_EXPECTED_TABLES: set[str] = (
    PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES  # v21 added NO new tables (only trades columns + indexes)
)

def _phase14_backup_gate(conn, *, current_version, target_version, backup_dir):
    # STRICT equality per CLAUDE.md migration backup-gate gotcha.
    if target_version < 22 or current_version != 21:
        return
    ...  # mirror _phase13_sb6c_backup_gate verbatim; filename swing-pre-phase14-migration-<ISO>.db
```

Wire `_phase14_backup_gate(...)` into `run_migrations` after `_phase13_sb6c_backup_gate`. The expected-tables set is `PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES` UNCHANGED because migration `0021` (v20 -> v21) added only `trades` columns + indexes, no new tables -- so the table set present at v21 equals the set present at v20 (the 5 Phase-13 tables + all prior). The discriminating test asserts (a) the gate fires only at `current_version == 21`; (b) a v20->v22 multi-step walk bypasses the v22-specific gate by design (matches Phase 9/12/13 precedent); (c) `db-migrate` run twice is a no-op.

### §4.5 Indexes rationale (dispatch brief §2.1 (a)-(d))

- (a) status-IN-open-states scan at observe-step time -> `idx_pfo_detection_date` (per-detection latest) + `idx_pfo_status`; the observe step reads detections whose latest observation status is open (§7.1 query).
- (b) per-ticker historical lookup -> `idx_pde_ticker_date`.
- (c) per-pattern-class strata -> `idx_pde_class_date`.
- (d) date-range queries for backtest replay -> `idx_pfo_observation_date`.

---

## §5 Repo layer design (append-only)

### §5.1 `swing/data/repos/pattern_detection_events.py`

Mirrors `swing/data/repos/pattern_evaluations.py` + `swing/data/repos/watchlist_close_track.py` (the canonical append-only + caller-tx exemplars). Caller-tx contract: **NO `conn.commit()`**.

```python
def insert_detection_event(conn, event: PatternDetectionEvent) -> int:
    """INSERT one row; return detection_id. Caller-tx (NO commit).
    UNIQUE(source, ticker, detection_date, pattern_class) raises
    sqlite3.IntegrityError on duplicate; caller decides SELECT-then-skip
    idempotency (mirrors _step_pattern_detect's existing-key pattern)."""

def get_detection_event_by_id(conn, detection_id: int) -> PatternDetectionEvent | None: ...

def list_detection_events(conn, *, ticker=None, pattern_class=None,
                          source=None, pipeline_run_id=None,
                          limit=None, offset=0) -> list[PatternDetectionEvent]: ...

def list_observable_detections(conn, *, source: str = "pipeline",
                               observation_date: str) -> list[PatternDetectionEvent]:
    """Return detections OBSERVABLE for `observation_date`:
      - detection.data_asof_date < observation_date  (STRICT; Codex R1 C#2 +
        R2 M#1 -- the forward-walk starts the FIRST COMPLETED SESSION AFTER the
        detector's DATA CUTOFF, NOT after the action-session label. This
        correctly INCLUDES the first tradable session (whose bar date exceeds
        the detection's data_asof_date) and EXCLUDES same-run detections whose
        data cutoff equals the current observation_date), AND
      - the MOST-RECENT forward observation has a status in the OPEN set
        ('pending','triggered_open') OR there is NO observation yet.
    Excludes detections whose latest status is terminal
    ('invalidated','expired','triggered_closed_*'). Uses a window function
    (ROW_NUMBER() OVER PARTITION BY detection_id ORDER BY observation_date DESC)
    to find the latest status per detection."""
```

**NO `update_detection_event` / `delete_detection_event`** -- append-only enforced at the repo layer (L1). The discriminating test source-greps the module for `def update_`/`def delete_` and asserts none exist (§11).

### §5.2 `swing/data/repos/pattern_forward_observations.py`

```python
def insert_observation(conn, observation: PatternForwardObservation) -> int:
    """INSERT one row; return observation_id. Caller-tx (NO commit).
    UNIQUE(detection_id, observation_date) raises sqlite3.IntegrityError on
    duplicate-same-day; caller (observe step) is idempotent via a pre-check."""

def get_observations_for_detection(conn, detection_id: int) -> list[PatternForwardObservation]:
    """The full chain, ORDER BY observation_date ASC."""

def get_latest_observation_for_detection(conn, detection_id: int) -> PatternForwardObservation | None: ...

def get_latest_observations_for_detections(
    conn, detection_ids: Sequence[int],
) -> dict[int, PatternForwardObservation]:
    """Batch latest-status read for the observe step. Empty input short-circuits
    to {} BEFORE executing SQL. Uses dynamic '?' expansion for the IN clause
    (sqlite3 cannot bind a list to a single :name placeholder -- CLAUDE.md
    gotcha). Window function (ROW_NUMBER() OVER PARTITION BY detection_id
    ORDER BY observation_date DESC) selects rn=1 per detection."""
```

**NO `update_*`/`delete_*`** (L1).

### §5.3 Dataclasses (gotcha #11 paired discipline)

`swing/data/models.py` gains two frozen dataclasses mirroring `PatternEvaluation` (lines 1874-1904) with `__post_init__` validators that mirror the schema CHECK constraints + module constants:

```python
_PATTERN_DETECTION_SOURCE_VALUES = (
    "pipeline", "v2_cohort", "d2_baseline", "backfill", "synthetic",
)
_FORWARD_OBSERVATION_STATUS_VALUES = (
    "pending", "triggered_open",
    "triggered_closed_at_target", "triggered_closed_at_stop",
    "invalidated", "expired",
)
_FORWARD_OBSERVATION_STATUS_CHANGE_EVENTS = (
    "entry_fired", "stop_fired", "target_fired",
    "time_exit", "shape_break", "observation_horizon_reached",
)

@dataclass(frozen=True)
class PatternDetectionEvent:
    detection_id: int | None
    ticker: str
    detection_date: str          # action_session_date (operator-facing label)
    data_asof_date: str          # detector data cutoff (forward-walk boundary anchor; R2 M#1)
    pattern_class: str           # validated against DETECTOR_PATTERN_CLASSES
    structural_anchors_json: str
    composite_score: float
    detector_version: str
    source: str                  # validated against _PATTERN_DETECTION_SOURCE_VALUES
    per_pattern_metadata_json: str
    created_at: str
    finviz_screen_state: str | None = None
    pipeline_run_id: int | None = None
    chart_render_id: int | None = None

    def __post_init__(self):
        # mirror schema CHECK: pattern_class enum + source enum.
        # (composite_score has no CHECK; structural_anchors_json/per_pattern_metadata_json NOT NULL.)

@dataclass(frozen=True)
class PatternForwardObservation:
    observation_id: int | None
    detection_id: int
    observation_date: str
    ohlc_today_json: str
    status: str                  # validated against _FORWARD_OBSERVATION_STATUS_VALUES
    sessions_since_detection: int
    created_at: str
    status_change_event: str | None = None  # validated against _..._STATUS_CHANGE_EVENTS when non-None
```

Per gotcha #11: the schema CHECK enums (migration `0022`), the Python module constants, and the `__post_init__` validators land in the SAME task. A discriminating test plants a row that satisfies the dataclass but a value-shape the CHECK rejects (and vice versa) to verify the mirror holds (§11).

---

## §6 `_step_pattern_detect` extension design (L7)

### §6.1 Where the extension hooks

The existing step (runner.py:1396-2104) builds `resolved_emit_list` (Pass 2, runner.py:1901-1969) -- each entry is `(ticker, pattern_class, version_str, window, evidence, geometric_score, template_match_score, nearest_exemplar_ids, composite_score)`. The existing emit loop (1981-2096) constructs a `PatternEvaluation` + calls `insert_evaluation(conn, row)` inside `lease.fenced_write() as conn`.

**The extension appends, in the SAME loop iteration, AFTER the successful `insert_evaluation`:**
1. Compute per-pattern metadata (§9) from the already-fetched `bars` + the candidate object.
2. Capture chart bytes -> `chart_render_id` (§8) (reuses `bars`).
3. Build a `PatternDetectionEvent` (source='pipeline'; detection_date = `asof_run` (= action_session_date); data_asof_date = `lease_data_asof(cfg, lease)` (the detector data cutoff; R2 M#1); pipeline_run_id = `pipeline_run_id`; structural_anchors_json = serialized evidence asdict + window anchors; composite_score = the same composite; finviz_screen_state = canonicalized candidate state; per_pattern_metadata_json = the metadata).
4. SELECT-then-skip idempotency (a re-run with an existing `(source='pipeline', ticker, detection_date, pattern_class)` row is skipped, mirroring the existing `existing_keys` pattern) then `insert_detection_event(conn, event)`.

All writes happen inside the SAME `lease.fenced_write()` transaction as the `insert_evaluation` (one atomic commit per detect step; the detection event + the evaluation row are written together).

### §6.2 Candidate-object sourcing (zero new query)

The step already fetches `candidates = fetch_candidates_for_run(read_conn, eval_run_id)` (runner.py:1459). The extension builds `candidate_by_ticker: dict[str, Candidate] = {c.ticker: c for c in candidates}` and looks up the `Candidate` per emit to source sector / industry / adr_pct / rs_rank / criteria / bucket / close -- ZERO new query (the candidates are already in memory). The `Candidate` dataclass fields (models.py:111-134): `ticker, bucket, close, pivot, initial_stop, adr_pct, tight_streak, pullback_pct, prior_trend_pct, rs_rank, rs_return_12w_vs_spy, rs_method, pattern_tag, notes, criteria, sector, industry`.

### §6.3 structural_anchors_json shape (OQ-7)

V1+ stores `structural_anchors_json = json.dumps({"window": {...}, "evidence": dataclasses.asdict(evidence)})` -- the SAME `dataclasses.asdict(evidence)` already computed for `pattern_evaluations.structural_evidence_json` (runner.py:2013), plus the window anchors `{start_date, end_date, anchor_date, anchor_reason}`. The evidence dict losslessly contains every per-class structural anchor (verified field inventory at §9.3 appendix). This is zero extra serialization cost (evidence is already serialized). The per-class anchor SUBSET (normalized columns) is a V2 candidate.

### §6.4 Empty-pool warnings audit (gotcha #27; L7)

The detect step's empty-pool early-return (runner.py:1485-1490: `if not aplus_tickers: log.info(...); return`) currently logs at INFO + returns silently -- exactly the gotcha #27 pattern (the silent-skip that hid the H7 finding for 7 post-T2.SB3 runs). Sub-bundle 2 hardens it: emit a structured warning into the run-level warnings accumulator (§7.4) capturing `{step: "pattern_detect", expected_pool: <len(candidates)>, actual_aplus_pool: 0, reason: "zero aplus candidates"}`. The step still returns (no work to do is legitimate), but the no-op becomes operator-visible in `pipeline_runs.warnings_json`.

---

## §7 NEW `_step_pattern_observe` pipeline step design

### §7.1 Algorithm

```
def _step_pattern_observe(*, cfg, lease, ohlcv_cache, run_warnings, max_pending_window, max_post_trigger_window):
    observation_date = lease_data_asof(cfg, lease)   # the run's DATA cutoff = the last completed bar's session (R2 M#1); the bar being recorded
    # 1. Read observable detections: detection.data_asof_date < observation_date
    #    (STRICT on the data cutoff; includes the first tradable session, excludes
    #    same-run/no-forward-bar-yet detections per R1 C#2 + R2 M#1) AND latest status open.
    open_detections = list_observable_detections(read_conn, source='pipeline', observation_date=observation_date)
    if not open_detections:
        run_warnings.append({step: "pattern_observe", actual_open_pool: 0, reason: "no observable detections"})
        return
    # 2. Batch-read latest observation per detection.
    latest = get_latest_observations_for_detections(read_conn, [d.detection_id for d in open_detections])
    # 3. For each open detection: fetch the bar FOR observation_date, compute status, append.
    with lease.fenced_write() as conn:
        for det in open_detections:
            # _bar_for_date selects the row whose date == observation_date (NOT
            # blindly the last row); asserts presence; strips in-progress partial
            # bar; archive-anchored read (R1 M#3 -- see 7.2).
            bar = _bar_for_date(ohlcv_cache, det.ticker, observation_date)
            if bar is None:
                run_warnings.append({step:"pattern_observe", ticker: det.ticker, reason:"no bar for observation_date"})
                continue
            prev = latest.get(det.detection_id)
            # idempotency: an observation already exists for (detection_id, observation_date) -> skip
            if prev is not None and prev.observation_date == observation_date:
                continue
            new_status, change_event = _advance_status(det, prev, bar, observation_date,
                                                        max_pending_window, max_post_trigger_window)
            insert_observation(conn, PatternForwardObservation(...ohlc_today_json=json(bar)..., status=new_status, ...))
```

### §7.2 OHLCV source + fetch-scope analysis (L4 + gotcha #5 + OQ-17)

The observe step reuses the SAME `OhlcvCache` instance the orchestrator passes to `_step_pattern_detect` + `_step_charts` (runner.py:768-773). Per-observed-ticker bars come via `ohlcv_cache.get_or_fetch(ticker=det.ticker, window_days=...)` -- the SAME call the detect step already makes (runner.py:1603). This is archive-first (the ladder reads the parquet archive before any yfinance call) and adds ZERO Schwab calls (L2 preserved; the OhlcvCache ladder is gated to non-Schwab unless production+configured -- the pre-existing gate).

**Nuance (OQ-17; surfaced for operator triage):** the observe step's open-detection set may include tickers that have rotated OUT of today's `bucket=='aplus'` pool and are not open trades -- so observing them is a DEFENSIBLE expansion of the "OHLCV fetch scope = open-trade tickers ONLY" gotcha (#5). The expansion is bounded (the open-detection set is the project's own actionable substrate -- small in absolute terms; observations expire/invalidate, so the set does not grow unboundedly per the §7.3 horizon), archive-first (cheap), and zero-Schwab (L2). The `get_or_fetch` per-ticker pattern is identical to the detect step's existing per-aplus-ticker fetch. **RECOMMENDED disposition:** accept the bounded expansion; document it explicitly; gotcha #5's intent (don't bulk-fetch the watchlist on every dashboard render) is not violated (this is a once-per-day pipeline step over a bounded set). Operator confirms at executing-plans.

**Bar selection MUST be anchored to `observation_date`, not "the last row" (Codex R1 M#3).** `OhlcvCache.get_or_fetch` is TTL-keyed by `(ticker, window_days)` and anchors to `last_completed_session(now())` (`swing/web/ohlcv_cache.py`), and the archive ladder can refresh from yfinance while serving a read (`swing/data/ohlcv_archive.py`) -- so blindly taking `bars.iloc[-1]` risks (a) a stale TTL hit from a different session, or (b) recording a bar that is not the intended `observation_date`. The `_bar_for_date(ohlcv_cache, ticker, observation_date)` helper therefore:
1. obtains the frame (via `get_or_fetch` OR, preferred, an archive-anchored read keyed to `observation_date`; writing-plans selects the exact read path -- e.g. `read_or_fetch_archive(ticker=..., end_date=observation_date, ...)` so the right-edge is the observation session, archive-first);
2. strips the in-progress partial bar per the CLAUDE.md yfinance gotcha if present (`observation_date` = `data_asof_date` is a COMPLETED session, so a partial bar with date > observation_date is dropped before selection; the OhlcvCache ladder already strips, and an archive-anchored read keyed to `end_date=observation_date` makes the partial-bar concern moot);
3. SELECTS the row whose date == `observation_date` (NOT `iloc[-1]`); if no such row exists, returns None (the step records a gap warning + skips -- no observation row for the gap day; the next run re-attempts);
4. returns the OHLC for exactly that session.

This anchoring is what keeps the #26-elimination claim honest at capture time: the observe step records the bar FOR `observation_date` as the archive knows it at capture, freezes it into `ohlc_today_json`, and never re-reads it -- there is no time-travel read of a past date from a later archive. (The frozen bar's value is "what was known that session"; that IS the forward-walk semantic.) The exact read path (archive-only vs cache-with-assertion) is OQ-17/writing-plans; the binding requirement here is: select-by-`observation_date` + assert-or-skip, never blind-last-row.

### §7.3 Status state machine (ruleset-agnostic V1+; OQ-4 + OQ-18)

V1+ emits ONLY the ruleset-agnostic subset `{pending, triggered_open, invalidated, expired}`, derived from objective price action vs the detection's OWN anchors. The ruleset-dependent `triggered_closed_at_target`/`triggered_closed_at_stop` are RESERVED for the Phase 15+ replay engine (OUT-OF-SCOPE) -- the replay engine applies ruleset-specific stop/target levels by REPLAYING the recorded `ohlc_today_json` path (that is the entire point of capturing the raw forward bars).

**Transitions** (recomputed each observation from the recorded path + the detection's anchors):

| From | To | Trigger (objective, anchor-derived) | status_change_event |
|---|---|---|---|
| (none) / pending | pending | first observation, no trigger, within window | NULL |
| pending | triggered_open | today's high >= `pivot_price` (breakout above the detection pivot) | `entry_fired` |
| pending | invalidated | today's close < `structural_invalidation_level` (the pattern's structural low; §7.3.1) | `shape_break` |
| pending | expired | `sessions_since_detection >= max_pending_window` without trigger | `time_exit` |
| triggered_open | triggered_open | post-trigger, within post-trigger horizon | NULL |
| triggered_open | expired | `sessions_since_detection >= max_pending_window + max_post_trigger_window` | `observation_horizon_reached` |

Terminal states (`invalidated`, `expired`, and the reserved `triggered_closed_*`) end the observation chain (the detection drops out of `list_observable_detections`).

**§7.3.1 Anchor sourcing for the predicates:** `pivot_price` is present in every detector evidence dataclass (VCP `pivot_price`; flat_base `pivot_price`; cup_with_handle `pivot_price`; high_tight_flag `pivot_price`; double_bottom_w `pivot_price`) and is stored inside `structural_anchors_json`. The `structural_invalidation_level` is the pattern's structural low -- per-class: VCP/flat_base `base_start..base_end` low (use `range_bottom_price` for flat_base; the lowest contraction trough for VCP); cup_with_handle `cup_bottom_price`; high_tight_flag `pole_start_price` (or consolidation low); double_bottom_w `min(trough_1_price, trough_2_price)`. The observe step reads these from `structural_anchors_json`. **The exact per-class invalidation-level definition + the `max_pending_window` / `max_post_trigger_window` values are OQ-18 (operator triage at executing-plans).** RECOMMENDED defaults: `max_pending_window = 30` sessions; `max_post_trigger_window = 60` sessions (so a detection is tracked at most ~90 sessions). These are config-surfaced (a small cfg block) so they are tunable without code change.

**V1-- simplification option (surfaced for operator):** an even-simpler V1 could emit ONLY a time-based `{pending -> expired}` lifecycle and defer ALL trigger/invalidation classification to the replay engine. RECOMMENDED AGAINST: the `triggered_open`/`invalidated` signals are objective + ruleset-agnostic + give the substrate an immediate "is this detection live?" read with no replay dependency. But the operator may choose the leaner variant at executing-plans.

### §7.4 Empty-pool + per-ticker warnings audit (gotcha #27; OQ-14)

`warnings_json` is currently UNUSED in `runner.py` (no accumulator is threaded to `lease.release`). Sub-bundle 2 introduces a run-level `run_warnings: list[dict]` accumulator created at run start, passed by reference to the detect + observe steps, and serialized to `lease.release(state="complete", warnings_json=json.dumps(run_warnings) if run_warnings else None)` (lease.py:74-87 already accepts `warnings_json`). Both the detect-step empty-pool path (§6.4) and the observe-step empty-pool/no-bar paths append structured entries. **Empty-state representation:** `None` when no warnings (not `"[]"`) per the audit-envelope-empty-state gotcha. This makes "0 detections observed (expected N)" operator-visible without code-reading -- the H7-finding-class regression cannot recur silently.

### §7.5 DAG position (OQ-2)

Insert `lease.step("pattern_observe")` + the best-effort try/except block immediately AFTER the `pattern_detect` block (runner.py ~854) and BEFORE `schwab_snapshot`. This is "after detect, before charts" (the recommended position). The observe step depends on detections written by the detect step in the SAME run (so a detection's first observation can fire the same day it is detected) AND on detections from prior runs (the forward-walk).

---

## §8 chart_render bytes capture at detection (V1+ LOCK; L5)

### §8.1 Surface decision (OQ-1): REUSE `theme2_annotated`

The `chart_renders.surface` CHECK already includes `theme2_annotated` (migration `0020` line 179-182), which is pattern-bound: its cross-column CHECK requires `pattern_class` + `pipeline_run_id` non-NULL, and its partial unique index keys on `(ticker, surface, pipeline_run_id, pattern_class)` (migration `0020` line 219-221). This is EXACTLY one chart per `(ticker, run, class)` -- matching one `pattern_detection_events` row per `(ticker, pipeline_run_id, pattern_class)` for source='pipeline'.

**RECOMMENDED: REUSE `theme2_annotated`.** This means:
- NO `chart_renders` schema CHECK widening (v22 stays scoped to the 2 new tables; no chart_renders table rebuild).
- The `chart_render_id` FK on `pattern_detection_events` points to the `theme2_annotated` row.

**Alternative REJECTED:** a NEW `pattern_detection_chart` surface would require a `chart_renders` table rebuild (CREATE-COPY-DROP-RENAME like the schwab_api_calls widening) + new partial-index + cross-column CHECK logic = materially more invasive v22 work for no benefit (theme2_annotated is literally "Theme 2 = pattern recognition, annotated chart").

### §8.2 Rendering (OQ-19; Codex R1 M#1 + M#2): use the DEDICATED `render_theme2_annotated_svg`

Production ALREADY has a dedicated, pattern-consuming renderer: `render_theme2_annotated_svg(*, ticker, bars, pattern_evaluation: PatternEvaluation, exemplar_thumbnails=None) -> bytes` (`swing/web/charts.py:481`). It parses `pattern_evaluation.structural_evidence_json` + draws per-class structural overlays. **`chart_jit._RENDERERS` does NOT register it** (chart_jit.py:56-61 maps only `hyprec_detail`, `market_weather`, `position_detail`, `watchlist_row`). The initial draft's recommendation to render via `render_hyprec_detail_svg` was WRONG (Codex R1 M#1) -- that would silently downgrade the locked `theme2_annotated` semantics.

**RECOMMENDED (REVISED):** wire `theme2_annotated` to `render_theme2_annotated_svg`. The detect step has the exact `PatternEvaluation` row it just built (the `row` object built at runner.py:2062 before `insert_evaluation`) and passes it as `pattern_evaluation`. The capture helper (§8.3) renders via `render_theme2_annotated_svg(ticker=..., bars=..., pattern_evaluation=row)` and caches under `surface='theme2_annotated'` with `pattern_class` + `pipeline_run_id` set. Renderer-kwargs uniformity LOCK (Expansion #10c): the detect-step callsite (and any future caller of theme2_annotated) MUST pass identical kwargs; a cache-collision discriminating test mocks the renderer + asserts `call_count == 1` on a second same-key request.

**Evidence-key repair IN SCOPE (Codex R1 M#2):** the annotation path in `swing/web/charts.py` reads STALE evidence keys -- `top_of_range`/`bottom_of_range` (charts.py:411-412), `depth_ratio` (charts.py:429), `pole_advance_pct` (charts.py:447) -- but the ACTUAL detector evidence fields are `range_top_price`/`range_bottom_price` (`swing/patterns/flat_base.py:97-98`), `cup_depth_pct` (`swing/patterns/cup_with_handle.py:135`), and `pole_pct` (`swing/patterns/high_tight_flag.py:126`). Unrepaired, `render_theme2_annotated_svg` produces base candlesticks + MAs but with MISSING/incorrect structural overlays. Writing-plans phase MUST (a) verify which renderer function actually reads which stale key (lines 411-449 fall in the hyprec region; the theme2 renderer at 481+ parses `structural_evidence_json` -- the exact stale-key surface is verified at writing-plans), and (b) include an evidence-key repair sub-task in T-2.4 so captured charts are correctly annotated. **If the repair is deferred** (operator option), the captured chart still renders (base price + MAs) with degraded overlays -- a V1 simplification (§13 #11), NOT a capture failure. The chart bytes are still frozen + non-empty (F6 barrier satisfied).

### §8.3 Invocation + failure handling (OQ-8 + OQ-13)

- **Trigger (OQ-13):** chart capture fires on EVERY emitted `pattern_detection_events` row. Since `_step_pattern_detect` runs ONLY on `bucket=='aplus'` candidates, ALL detections are A+ tier -> chart capture on every A+ detection (the natural V1+ scope; resolves OQ-13). Substrate growth is bounded: ~(#aplus tickers x #detected classes) SVGs per run; the aplus pool is typically small (0-20 in production).
- **Capture helper returns the id (Codex R1 m#2; FINALIZED at R2):** `get_or_render_surface` returns only bytes (chart_jit.py); `refresh_chart_render` returns the inserted id. To populate `chart_render_id`, the detect step uses a NEW thin helper `render_and_capture_detection_chart(conn, *, ticker, bars, pattern_evaluation, pipeline_run_id, data_asof_date) -> int | None` that: (1) renders via `render_theme2_annotated_svg`; (2) builds the `ChartRender` (construction-barrier F6 empty-bytes rejection applies); (3) calls the standard **`refresh_chart_render`** (DELETE-then-INSERT on the `theme2_annotated` key; caller-tx, returns the new id) -- this is the SAME write helper the exemplar path uses (`swing/web/view_models/patterns/exemplars.py`), so the two writers coexist as last-writer-wins cache (R2 C#1); (4) honors the CALLER-TX contract (uses the passed `conn`; does NOT open its own `with conn:` -- `refresh_chart_render` is already caller-tx per its docstring at `chart_renders.py:200-249`; it runs inside the detect step's existing `lease.fenced_write()` so the chart row + evaluation row + detection row commit atomically). The returned id is stored as the detection's `chart_render_id` (a nullable audit linkage; SET NULL if the cache row is later refreshed away -- §4.1).
- **Idempotency (Codex R1 C#1, re-framed at R2):** the detection-event INSERT is idempotency-gated (SELECT-then-skip on the unique key, §6.1 step 4); on a skip, the chart capture is also skipped (no wasted render). Because `chart_render_id` is now SET NULL (not RESTRICT), a re-run's `refresh_chart_render` that legitimately replaces the cache row is HARMLESS (the prior detection's pointer degrades to NULL; FACTS untouched) -- there is no RESTRICT deadlock and no collision failure.
- **Failure handling (OQ-8):** if the render fails (matplotlib hiccup; bar shortage; F6 empty-bytes rejection at `ChartRender.__post_init__`), the helper returns None; the `pattern_detection_events` row STILL inserts with `chart_render_id = NULL`; a gotcha #27 warnings-audit entry is appended (`{step:"pattern_detect", ticker, pattern_class, reason:"chart render failed"}`). The detection is never lost because a chart could not render. Closes CR.1 cleanly.

### §8.4 Cost note

Chart capture adds matplotlib-render cost at detect time (one SVG per A+ detection), reusing already-fetched `bars` (no new OHLCV fetch; gotcha #5 + L2 preserved). This is a NEW cost relative to pre-Sub-bundle-2 (the detect step did not render), but it is LOCKED by Sec 9.1 Q3 V1+ and bounded by the small A+ pool. The observe step does NOT render charts (L4 zero-cost).

---

## §9 Per-pattern metadata sourcing (L6) -- REDESIGN per code-read

### §9.1 Brief-vs-reality finding (forward-binding lesson #1 / Expansion #4 column verification)

Dispatch brief §2.6 prescribed: "market_cap: from `candidates.market_cap_dollars` (verify column exists)" and "ATR_pct: from `candidates.atr_pct` (verify column exists)". **Code-read verdict: NEITHER column exists.** The `candidates` table (migration `0001` CREATE + `0012` ALTER) has `sector`, `industry`, and `adr_pct` (Average **Daily** Range percent -- NOT ATR), but has NO `market_cap`/`market_cap_dollars` and NO `atr_pct`/`average_true_range`. The Finviz CSV does carry "Market Cap" + "Average True Range" columns (the 13-column validator), but those are NOT persisted onto `candidates` -- only `sector`/`industry` (migration 0012) + the computed `adr_pct`. The brief's own "(verify column exists)" caveat anticipated this verification step.

### §9.2 Per-field source-of-truth (V1+; L2 LOCK -- no new fetch)

| Field | V1+ source | Notes |
|---|---|---|
| `sector` | `Candidate.sector` (already-fetched candidate object; §6.2) | empty string for legacy/missing per migration 0012 |
| `industry` | `Candidate.industry` | same |
| `adr_pct` | `Candidate.adr_pct` | the project's canonical volatility measure (Average Daily Range %) |
| `atr_pct` | COMPUTE from `bars` at detect time: `ATR(14) / last_close * 100` | pure-bars (already fetched); no new fetch. True ATR distinct from ADR. |
| `ret_90d` | COMPUTE from `bars`: `(close_today - close_90_sessions_ago) / close_90_sessions_ago * 100` | pure-bars; helper `compute_return_pct(bars, asof, 90)` |
| `prox_52w_high_pct` | COMPUTE from `bars`: `(high_52w - close_today) / high_52w * 100` where `high_52w = closes.iloc[-252:].max()` | reuses the trend_template.py:TT7 formula (verified existing) |
| `rs_rank` | `Candidate.rs_rank` (bonus; available) | |
| `close_at_detection` | `Candidate.close` (or bars last close) | |
| `market_cap` | **NULL in V1+** (V2 candidate) | NOT persisted to candidates; capturing it requires a SEPARATE data-wiring change (persist Finviz Market Cap onto candidates) which is OUT-OF-SCOPE for Sub-bundle 2 (would be its own migration). Surfaced as OQ-16 + V1 simplification. |

`per_pattern_metadata_json = json.dumps({sector, industry, adr_pct, atr_pct, ret_90d, prox_52w_high_pct, rs_rank, close_at_detection, market_cap: null})`. The JSON-blob choice (vs separate columns) is OQ-5 (RECOMMENDED JSON for V1+; column normalization is V2).

### §9.3 Computation helpers + in-progress-bar discipline

The 3 pure-bars helpers (`compute_atr_pct`, `compute_return_pct`, `compute_52w_high_proximity_pct`) operate on the `bars` DataFrame ALREADY fetched in the detect loop, sliced to `<= data_asof_date` (the detector DATA cutoff -- the last completed bar; NOT the forward-looking `detection_date` action-session label, which has no bar yet -- Codex R3 M#3) with the in-progress partial bar stripped per the CLAUDE.md yfinance gotcha if present (the OhlcvCache ladder already strips, but the helpers assert `bars.index[-1].date() <= data_asof_date` defensively). Each helper guards short-history (e.g., `< 90` bars for ret_90d -> field = None inside the JSON, not an exception) so a short-history ticker never poisons the metadata emit. Writing-plans phase chooses module location (`swing/pipeline/temporal_metadata.py` vs inline).

### §9.4 finviz_screen_state (OQ-6)

At detect time, the `Candidate` object carries `criteria: tuple[CriterionResult, ...]` + `bucket` + `rs_rank` + `rs_method`. The `CriterionResult` dataclass fields are `criterion_name` + `result` (+ `layer`, `value`, `rule`) (`swing/data/models.py:103-105`; repo deserialization constructs `CriterionResult(name, layer, res, val, rule)` at `swing/data/repos/candidates.py:114`). `finviz_screen_state = json.dumps({"bucket": c.bucket, "rs_rank": c.rs_rank, "rs_method": c.rs_method, "criteria": {cr.criterion_name: cr.result for cr in c.criteria}})` -- a canonicalized (NOT verbatim) per-ticker evaluation/screen state, where the per-criterion value is the `CriterionResult.result` (the pass/fail/na verdict string, NOT a coerced bool -- writing-plans confirms the exact `result` value domain). (The literal Finviz screen-query params are not per-ticker; the per-ticker signal is which evaluation criteria the candidate passed.) Nullable for non-pipeline sources (V2).

---

## §10 Sub-bundle decomposition

### §10.1 Single writing-plans + executing-plans dispatch with internal task slices (RECOMMENDED)

Sub-bundle 2 is larger than Sub-bundle 1 (commissioning estimate ~15-25 commits + ~50-100 tests; v22 migration). RECOMMENDED: a SINGLE writing-plans + executing-plans dispatch with clear internal task slices:

- **T-2.1 Schema:** migration `0022` + `db.py` v22 wiring (EXPECTED_SCHEMA_VERSION + backup gate + expected-tables) + migration tests. (gotcha #9 + #11 + strict-equality backup gate.)
- **T-2.2 Models + repos:** 2 dataclasses + constants + 2 append-only repos + repo tests. (gotcha #11 paired discipline; append-only source-grep tests.)
- **T-2.3 detect-step extension:** per-pattern metadata helpers + candidate-object sourcing + `pattern_detection_events` append + empty-pool warnings audit + tests.
- **T-2.4 chart capture:** register `theme2_annotated` -> `render_theme2_annotated_svg`; caller-tx `render_and_capture_detection_chart` helper (uses `refresh_chart_render`; returns chart_render_id) + chart_render_id wiring (SET NULL FK; coexists with the exemplar theme2_annotated writer last-writer-wins) + charts.py evidence-key repair + cache-collision test. (Codex R1 C#1+M#1+M#2+m#2; R2 C#1+C#2.)
- **T-2.5 observe step:** `_step_pattern_observe` + `detection.data_asof_date < observation_date` forward-walk boundary (observation_date = run data_asof_date; Codex R1 C#2 + R2 M#1) + select-bar-for-observation_date anchoring (Codex R1 M#3) + status state machine (windows measured from data_asof_date) + DAG wiring + run-warnings accumulator + tests.
- **T-2.6 closer:** L2 source-grep verify + ASCII discipline verify + cross-step integration test.

**Alternative (operator option):** split into TWO executing-plans dispatches -- (A) substrate (T-2.1 + T-2.2 + T-2.3) then (B) behavior (T-2.4 + T-2.5 + T-2.6). RECOMMENDED single dispatch (the slices cohere + share the v22 substrate); surface the split as an operator option at executing-plans dispatch.

### §10.2 Operator-witnessed gate surfaces (dispatch brief §2.7)

| # | Surface | Pass criterion |
|---|---|---|
| **S1** | `python -m pytest -m "not slow" -q` + `ruff check swing/` | all pass; 0 ruff errors |
| **S2** | schema v22 applied | `swing db-migrate` brings the DB to v22; `_current_version` returns 22; both new tables empty + readable; `swing-pre-phase14-migration-<ISO>.db` backup written |
| **S3** | run pipeline; detect step | `pattern_detection_events` accumulates rows for A+ detections; per-pattern metadata populated (sector/industry/adr_pct/atr_pct/ret_90d/prox_52w; market_cap NULL); `chart_render_id` non-NULL for successful renders |
| **S4** | re-run pipeline; observe step | `pattern_forward_observations` accumulates today's bar for previously-open detections; status state machine transitions correctly (pending -> triggered_open on pivot breakout; -> invalidated on structural-low break; -> expired on window) |
| **S5** | append-only verification | attempt UPDATE on `pattern_detection_events` via repo -> no such repo function exists (source-grep test); attempt raw SQL DELETE on a detection with observations -> RESTRICT FK blocks it; INSERT-only path works |
| **S6** | chart_render_id chain | `pattern_detection_events.chart_render_id` -> `chart_renders.id` -> `chart_svg_bytes` resolvable; theme2_annotated row present with the detection's `pattern_class` + `pipeline_run_id` |
| **S7** | gotcha #27 audit | force an empty A+ pool (or empty open-detection set); assert `pipeline_runs.warnings_json` carries the structured empty-pool entry (NOT silent) |

(S5 + S6 may be mechanical-test-covered + spot-checked at the browser/CLI per Codex assessment.)

---

## §11 Test fixture strategy

### §11.1 Production-shape fixtures

- detect-step extension tests plant candidates via `swing.data.repos.candidates.insert_candidates(...)` + run the detector path (or a stubbed `resolved_emit_list`) so the `PatternDetectionEvent` INSERT shape matches the production emitter exactly (no synthetic-fixture-vs-production-emitter drift, the recurring Phase-12 family gotcha). Evidence fixtures use the real detector evidence dataclasses (so `dataclasses.asdict(evidence)` produces the production structural_anchors_json shape).
- observe-step tests plant `pattern_detection_events` rows via the new repo + drive `_step_pattern_observe` with a mocked `OhlcvCache.get_or_fetch` returning canned production-shape DataFrames (capitalized Open/High/Low/Close/Volume + DatetimeIndex).

### §11.2 Append-only enforcement tests (L1)

- Source-grep test: assert `swing/data/repos/pattern_detection_events.py` + `..._forward_observations.py` define NO `def update_`/`def delete_` functions.
- FK RESTRICT test: insert a detection + an observation; attempt raw `DELETE FROM pattern_detection_events WHERE detection_id=?` -> assert `sqlite3.IntegrityError` (RESTRICT).
- UNIQUE test: insert two detections with the same `(source, ticker, detection_date, pattern_class)` -> second raises `IntegrityError`; two observations same `(detection_id, observation_date)` -> second raises.

### §11.3 Migration tests (gotcha #9 + #11 + strict-equality)

- Apply `0022` on a v21 fixture -> reaches v22; both tables present; CHECK constraints reject out-of-enum values.
- Rollback-through-runner: a deliberately-malformed `0022` variant fails mid-script -> assert `conn.rollback()` left the DB at v21 + `conn.in_transaction == False` (test through the real `_apply_migration` path, NOT bare `executescript`).
- Backup-gate: assert `_phase14_backup_gate` fires only at `current_version == 21`; a v20->v22 walk bypasses it; `db-migrate` twice is a no-op.
- Paired-discipline: a row that satisfies the dataclass but violates the schema CHECK (and vice versa) -> both layers reject (gotcha #11).

### §11.4 L2 LOCK preservation

Existing `tests/integration/test_l2_lock_source_grep.py` (multiset Counter; baseline `bf7e071`; pattern `schwabdev.Client.`) MUST continue passing -- Sub-bundle 2 adds ZERO `schwabdev.Client.*` call sites. The chart capture + observe-step OHLCV reads route through the existing matplotlib renderer + OhlcvCache ladder (no Schwab). Spec cites this discriminating test.

### §11.5 Empty-input + runtime-binding-shape (Expansion #4 sub-refinement)

- `get_latest_observations_for_detections(conn, [])` -> returns `{}` WITHOUT executing SQL (empty-input short-circuit; avoids invalid `IN ()`).
- Multi-element input -> dynamic `?` expansion binds correctly (sqlite3 cannot bind a list to `:name`).
- `list_observable_detections` with zero detections -> returns `[]` (observe step then emits the gotcha #27 empty-pool warning).

### §11.6 Status state machine tests

Plant a detection with a known `pivot_price` + `structural_invalidation_level`; drive `_step_pattern_observe` across a synthetic bar sequence; assert each transition: pending (below pivot, above invalidation, within window) -> triggered_open (high crosses pivot) ; pending -> invalidated (close below structural low) ; pending -> expired (window elapsed without trigger) ; triggered_open -> expired (post-trigger horizon). Assert `sessions_since_detection` equals the computed trading-session delta FROM `data_asof_date` (not detection_date). Assert the first observation lands on the first session with date > `data_asof_date` (R2 M#1). Assert `ohlc_today_json` is frozen verbatim (never re-fetched/mutated on a later run).

---

## §12 Schema impact analysis

**Verdict: Schema v22 (single migration `0022`).** Per Sec 9.1 Q3 V1+ LOCK.

| Item | Schema touch? | Migration? | Justification |
|---|---|---|---|
| `pattern_detection_events` + `pattern_forward_observations` | 2 NEW tables + 7 indexes + CHECK + FK | YES (v22) | the substrate (Sec 9.1 Q3 V1+) |
| chart capture | REUSE existing `theme2_annotated` surface | NO | no `chart_renders` CHECK widening (§8.1) |
| per-pattern metadata | JSON blob in the new table | NO | no `candidates` schema change (market_cap NOT added; V2) |
| `db.py` v22 wiring | EXPECTED_SCHEMA_VERSION + backup gate + expected-tables | code, not DDL | gotcha #9 + #11 + strict-equality `pre_version == 21` |

**No migration beyond v22** (dispatch brief §7 LOCK). `PHASE14_PRE_MIGRATION_EXPECTED_TABLES = PHASE13_SB6C_PRE_MIGRATION_EXPECTED_TABLES` (v21 added no tables). Backup-gate STRICT equality `current_version == 21` (gotcha; mirrors `_phase13_sb6c_backup_gate`). Migration-runner discipline (gotcha #9): explicit `BEGIN`/`COMMIT` in the SQL; `UPDATE schema_version SET version = 22` as the FINAL statement; runner wraps with `foreign_keys=OFF` + try/except rollback.

---

## §13 V1+ simplifications + V2 candidates banked

| # | V1+ simplification | V2 dependency |
|---|---|---|
| 1 | `market_cap` = NULL in per-pattern metadata (NOT persisted to candidates) | V2: persist Finviz "Market Cap" onto `candidates` (its own migration + `_step_evaluate` wiring), then source market_cap at detection |
| 2 | `atr_pct` computed from bars (true ATR14); `adr_pct` also captured from candidates | V2: reconcile ADR vs ATR semantics if both prove useful, or normalize into columns |
| 3 | `structural_anchors_json` = full evidence asdict (+ window) | V2: normalized per-class anchor columns/table for indexed structural queries |
| 4 | `per_pattern_metadata_json` = JSON blob (OQ-5) | V2: normalize into typed columns if stratified queries need indexing |
| 5 | Status state machine emits only `{pending, triggered_open, invalidated, expired}` (ruleset-agnostic) | Phase 15+: replay engine emits `triggered_closed_at_target`/`triggered_closed_at_stop` by replaying `ohlc_today_json` against ruleset stops/targets (schema already forward-compat) |
| 6 | chart capture REUSES `theme2_annotated` (no new surface) + the DEDICATED `render_theme2_annotated_svg` renderer | V2: dedicated `pattern_detection_chart` surface if theme2_annotated proves too coupled with a future web journal surface |
| 11 | theme2 renderer evidence-key repair (charts.py stale keys -> actual detector fields) is IN SCOPE (T-2.4); IF deferred at operator option, captured charts render base price+MAs with degraded structural overlays | V2: full annotation-overlay parity if the repair is deferred in V1+ |
| 7 | Append-only enforced at repo layer (no update/delete fns) + UNIQUE + RESTRICT FK (OQ-10) | V2: SQLite BEFORE UPDATE/DELETE triggers (RAISE) for defense-in-depth (no existing table uses triggers; new mechanism) |
| 8 | Observe-step records gap days as skips (no observation row when no bar for the day) | V2: backfill gap observations from archive at next run (carefully; would touch #26 boundary -- likely NOT done) |
| 9 | `finviz_screen_state` = canonicalized eval criteria (not verbatim Finviz params) | V2: capture verbatim Finviz screen-query params at run level + link |
| 10 | source always `'pipeline'` (other enum values reserved, unused) | V2: backfill (source `'backfill'`) from existing `pattern_evaluations`; V2-cohort ingestion (source `'v2_cohort'`) |

---

## §14 Operator decision items pending (Open Questions)

Brief §3 OQs (1-15) + 5 NEW OQs surfaced by code-read (16-20). RECOMMENDED dispositions resolve most at brainstorm; the flagged ones go to operator triage at the executing-plans dispatch.

| # | Open Question | Brainstorm resolution / disposition |
|---|---|---|
| 1 | chart_render integration -- new surface vs reuse | **REUSE `theme2_annotated`** (§8.1); no chart_renders CHECK widening. RESOLVED. |
| 2 | pipeline step DAG position | **AFTER detect, BEFORE charts** (right after the pattern_detect block, before schwab_snapshot). RESOLVED. |
| 3 | observe-step OHLCV source | **reuse OhlcvCache** (archive-first; zero Schwab). RESOLVED (with OQ-17 nuance). |
| 4 | status state machine completeness | enumerated (§7.3); V1+ emits the ruleset-agnostic subset. RESOLVED (thresholds -> OQ-18). |
| 5 | per_pattern_metadata schema -- JSON vs columns | **JSON blob for V1+**; columns are V2. RESOLVED. |
| 6 | finviz_screen_state JSON shape | **canonicalized eval-criteria + bucket + rs** (§9.4). RESOLVED. |
| 7 | structural_anchors_json shape per class | **full evidence asdict (+ window)**; per-class subset is V2 (§6.3). RESOLVED. |
| 8 | chart_render failure handling | **nullable chart_render_id + warnings audit**. RESOLVED. |
| 9 | migration runner safety -- backup-gate equality | **STRICT `pre_version == 21`** (§4.4). RESOLVED + LOCKED. |
| 10 | append-only enforcement layer | **repo-layer (no update/delete fns) + UNIQUE + RESTRICT FK**; triggers are V2 (§5; the brief leaned schema-level -- this diverges to match precedent). **OPERATOR TRIAGE** (confirm repo-layer vs triggers). |
| 11 | which detector classes write | **ALL 5 V1 detectors** (same set detect runs). RESOLVED. |
| 12 | backwards-compat with pattern_evaluations | **coexist; both written same pass; asymmetric FK (CASCADE vs SET NULL)** (§1.3). RESOLVED. |
| 13 | chart capture trigger -- every / A+ / watch+aplus | **every detection = every A+** (detect runs only on aplus). RESOLVED. |
| 14 | observe-step empty-pool warnings audit | **run-level warnings accumulator -> lease.release(warnings_json)** (§7.4). RESOLVED. |
| 15 | V1+ simplifications + V2 candidates | enumerated at §13. RESOLVED. |
| 16 | **NEW:** market_cap + true ATR NOT in `candidates` | V1+ captures sector/industry/adr_pct (candidates) + atr_pct/ret_90d/prox_52w (computed from bars); market_cap = NULL (V2: persist Finviz Market Cap to candidates -- out of Sub-bundle 2 scope). **OPERATOR TRIAGE** (confirm NULL-market_cap-for-V1 is acceptable). |
| 17 | **NEW:** observe-step fetch scope vs gotcha #5 | bounded, archive-first, zero-Schwab expansion of the open-trade-only fetch scope to the open-detection set. RECOMMENDED accept. **OPERATOR TRIAGE.** |
| 18 | **NEW:** status state machine thresholds | RECOMMENDED `max_pending_window=30`, `max_post_trigger_window=60` sessions; per-class `structural_invalidation_level` definition (§7.3.1); config-surfaced. **OPERATOR TRIAGE** (confirm windows + invalidation levels; or choose the leaner pure-time V1-- variant). |
| 19 | **NEW:** theme2_annotated renderer + chart FK | **REVISED (Codex R1 M#1+M#2+C#1+m#2; R2 C#1+C#2):** use the DEDICATED `render_theme2_annotated_svg` (charts.py:481) -- NOT render_hyprec_detail_svg; caller-tx helper returns chart_render_id via the standard `refresh_chart_render` (coexists last-writer-wins with the exemplar theme2_annotated writer at `view_models/patterns/exemplars.py`); `chart_render_id` FK = `ON DELETE SET NULL` (nullable audit linkage to the ephemeral run-scoped cache -- the R1 RESTRICT attempt was reverted because it deadlocked the run-prune CASCADE + collided with the exemplar path); evidence-key repair IN SCOPE for T-2.4 (deferral is a V1 simplification §13 #11). RESOLVED. |
| 20 | **NEW:** Codex two-chain at writing-plans (gotcha #36) | §15.5 evaluation. **OPERATOR TRIAGE at writing-plans dispatch.** |

---

## §15 Cumulative discipline compliance summary

### §15.1 Gotcha application matrix (selected; 37 BINDING)

| Gotcha | Sub-bundle 2 applicability |
|---|---|
| #9 (executescript implicit COMMIT) | **APPLIED** -- `0022` explicit BEGIN/COMMIT + final schema_version bump; rollback-through-runner test (§4.3 + §11.3) |
| #11 (Schema-CHECK + Python-constant + dataclass-validator paired; read-path mappers same task) | **APPLIED** -- CHECK enums + module constants + `__post_init__` validators land in T-2.1/T-2.2; `_row_to_*` mappers in the same task (§5.3) |
| migration backup-gate STRICT equality | **APPLIED** -- `_phase14_backup_gate` `current_version == 21` (§4.4) |
| sqlite3 list-bind / dynamic `?` expansion + empty-input | **APPLIED** -- `get_latest_observations_for_detections` (§5.2 + §11.5) |
| `date.fromisoformat` TEXT->date boundary | **APPLIED** -- detection_date / observation_date are TEXT; the observe-step session-delta computation + status predicates convert at the callsite with malformed-input guards (§7) |
| #26 (OHLCV archive bar-content TEMPORAL mutation) | **ELIMINATED BY CONSTRUCTION** -- forward-walk; ohlc_today_json frozen at observation; no archive re-read (§1.1 + §2.3). Hardened per Codex R1 M#3: the observe step selects the bar FOR `observation_date` (not blind last-row) + freezes it; no time-travel read of a past date from a later archive (§7.2). |
| chart-pointer FK posture | **RESOLVED per Codex R1 C#1 + R2 C#1+C#2** -- `chart_render_id` is a nullable AUDIT LINKAGE to the ephemeral run-scoped cache: `ON DELETE SET NULL` + standard `refresh_chart_render` (coexists last-writer-wins with the exemplar theme2_annotated writer); the chart is a best-effort capture, NOT a frozen fact; a guaranteed-permanent chart is a V2 candidate (§2.3, §4.1, §8.3, §13 #6) |
| #27 (silent-skip-without-audit) | **APPLIED** -- detect-step empty-pool (§6.4) + observe-step empty-pool/no-bar (§7.4) + chart-render-failure (§8.3) emit warnings_json |
| #5 (OHLCV fetch scope = open-trade tickers) | **AUDITED** -- observe-step scope expansion analyzed + bounded + accepted (§7.2 + OQ-17) |
| #28/#29 (exemplar OHLCV cache discipline) | **N/A** -- chart capture uses the candidate's OWN already-fetched bars (not an exemplar corpus); the detect step's existing exemplar-template-match path is unchanged |
| #37 (substrate-freshness sensitivity) | **ELIMINATED BY CONSTRUCTION** -- append-only; no regeneration (§1.1 + §2.3) |
| #32 (ASCII discipline) | **APPLIED** -- scope declared §15.2 |
| #36 (two-Codex-chain) | brainstorming = SINGLE chain (Q7 LOCK); writing-plans evaluation §15.5 |
| #24/#25 (parity disciplines) | **N/A** -- temporal log is its own forward-walk substrate; no V1/V2 parity comparison |
| append-only precedent (`reconciliation_corrections`, `watchlist_close_track_flag_events`, `pattern_evaluations`) | **MIRRORED** -- repo-layer append-only + caller-tx + UNIQUE; RESTRICT FK on observations (§5) |
| `ChartRender.__post_init__` F6 empty-bytes + semantic contract | **REUSED** -- chart capture goes through the existing construction barrier; failure -> chart_render_id NULL (§8.3) |

### §15.2 ASCII discipline scope (gotcha #32)

ASCII-only across NEW/MODIFIED PRODUCTION + TEST surfaces: `0022_phase14_temporal_log.sql`; `swing/data/db.py` (diff); `swing/data/models.py` (new dataclasses); `swing/data/repos/pattern_detection_events.py`; `swing/data/repos/pattern_forward_observations.py`; `swing/pipeline/runner.py` (diff); `swing/web/chart_jit.py` (diff); the metadata helper module; all new/modified test modules; the return report. **This spec doc + the dispatch brief are EXCLUDED** from strict ASCII (the `§` section sign is used per project convention for spec/brief cross-references). Verification: programmatic `text.encode("ascii")` over each declared file at writing-plans + executing-plans.

### §15.3 ZERO Co-Authored-By trailer drift

Sub-bundle 2 preserves the ~611+ cumulative ZERO `Co-Authored-By` footer streak. Verification: `git log --pretty="%(trailers)" main..HEAD` emits ZERO `Co-Authored-By:` lines on the branch. Return report §14 confirms. No `--no-verify`.

### §15.4 L2 LOCK preservation

ZERO new `schwabdev.Client.*` call sites; ZERO new `schwab_api_calls` emit sites. The chart capture (matplotlib) + observe-step OHLCV reads (OhlcvCache ladder, archive-first) add no Schwab surface. Discriminating test §11.4 (existing multiset source-grep; baseline `bf7e071`).

### §15.5 Codex chain evaluation (gotcha #36; OQ-20)

- **Brainstorming (THIS phase):** SINGLE chain at end (Sec 9.1 Q7 LOCK). Target 2-5 rounds NO_NEW_CRITICAL_MAJOR.
- **Writing-plans phase:** Sub-bundle 2 produces NO analytical artifact (no smoke / findings / study) -- it is pure infrastructure (schema + pipeline). Per gotcha #36's explicit caveat, pure-infrastructure dispatches without a substantive emitted artifact MAY use single-chain at orchestrator discretion. HOWEVER, two dimensions are substantive enough to MERIT considering the two-chain default: (a) the v22 schema is substrate-changing + permanent (append-only -- a schema mistake is hard to walk back); (b) the status state machine semantics (§7.3) are a methodology design that a second methodology-review chain could harden. **RECOMMENDED:** flag for operator at the writing-plans dispatch; lean toward two-chain (implementation review + schema/semantics review) given the permanence of the append-only substrate, but single-chain is defensible. OQ-20.
- **Cumulative C.C lesson #6 validation slot:** Sub-bundle 2 consumes the next cumulative slot (47th was Sub-bundle 1 executing-plans; this brainstorming is a fresh validation). Return report enumerates round shape + finding taper + CLEAN/NOTABLE.

---

*End of Phase 14 Sub-bundle 2 design spec. Temporal pattern detection + observation log infrastructure (V1+): 2 NEW append-only tables (`pattern_detection_events` + `pattern_forward_observations`) via v22 migration + NEW `_step_pattern_observe` + per-pattern metadata enrichment at detection + chart_render bytes capture at detection (reusing `theme2_annotated`). Eliminates gotchas #26 + #37 by architectural construction (forward-walk; no archive re-read; no regeneration). Sec 9.1 Q1-Q7 + L1-L8 LOCKs honored; Schema v22; L2 LOCK preserved; ASCII scope declared; 20 OQs enumerated (15 resolved at brainstorm + 5 new code-read findings; 5 flagged for operator triage). Brainstorm ready for Codex MCP adversarial chain review.*
