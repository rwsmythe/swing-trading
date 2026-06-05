# Pattern-Observation Pool Widening (aplus -> aplus+watch) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Widen the nightly `_step_pattern_detect`/`_step_pattern_observe` pool from `bucket=='aplus'` to `bucket IN ('aplus','watch')` so the Phase-14 temporal observation log accumulates the ~83x watch population as forward-walk data, while keeping the widen INVISIBLE to every operator-facing surface, at zero capital risk, zero Finviz-screen change, and zero schema change (v24 holds).

**Architecture:** The predicate is one line; the substance is (1) consumer isolation of the sibling `pattern_evaluations` aggregate/queue consumers to aplus-origin via a PROVABLE-aplus SQL ladder (NO schema column -- the bucket is reached by join / JSON / historical gate); (2) the predicate widen + the gotcha-#27 audit reshape + a pool-neutral rename + provenance-by-construction confirmation; (3) two DORMANT relief levers + observe-load instrumentation. Isolation lands FIRST (the widen stays dark until the surfaces are protected). NO migration; the bucket rides in the existing `finviz_screen_state` JSON.

**Tech Stack:** Python 3.14, SQLite (stdlib `sqlite3`, JSON1 `json_extract` proven-available), pytest (`-m "not slow"`), the existing `swing/pipeline/runner.py` detect/observe steps, `swing/evaluation/`, `swing/metrics/`, `swing/web/view_models/patterns/`, `swing/patterns/`.

---

## 0. Pre-locked decisions (BINDING -- propagate, do NOT re-litigate)

From the commissioning brief Sec 10 (D1-D6) + the design spec (`docs/superpowers/specs/2026-06-04-pattern-observation-pool-widening-design.md`) Sec 2 (L1-L6) + the writing-plans operator-pairing (2026-06-04, this arc):

| Lock | Decision |
|---|---|
| **L1 (scope)** | Widen the detect predicate to `aplus+watch` + the consequent observe scaling + the consumer isolation that keeps it invisible. NO ruleset/sizing/bucket-assignment/recommendation/Finviz change. NO beyond-Finviz net. NO new operator-facing surface reading the widened log. NO historical backfill (forward-walk from ship date). |
| **L2/L3 (pool + NO schema)** | Pool = `aplus + watch` (NOT skip). Bucket provenance rides in the EXISTING `finviz_screen_state` JSON (already emits `"bucket"`). NO migration; `EXPECTED_SCHEMA_VERSION` STAYS 24; NO `source_bucket` column. |
| **L4 (observe-load)** | ACCEPT-AND-MEASURE. V1 ships UNCAPPED; both relief levers ship DORMANT (cfg knobs default `None`). A silent cap is FORBIDDEN -- any drop/shed emits a #27 `warnings_json` audit. |
| **L5 (invariants)** | Schwab L2 LOCK untouched (zero new Schwab calls). Append-only + `ohlc_today_json` LOCK-at-observation preserved. yfinance OHLCV-fetch-scope discipline holds. |
| **L6 (Codex)** | SINGLE Codex chain at the end of writing-plans, run to convergence (`NO_NEW_CRITICAL_MAJOR`; ~5-round cap suspended). |
| **OQ-1 (operator-paired 2026-06-04)** | CONFIRM spec shape: V1 uncapped; both levers dormant; accept-uncapped iff (a) measured runtime delta < operator budget AND (b) steady-state net-new fetch < `OhlcvCache` breaker thresholds. Numbers + accept/cap decided at the exec measurement gate. |
| **OQ-4 (operator-paired 2026-06-04)** | CONFIRM the 4-part gate: (1) orchestrator QA vs disk; (2) observe-load measurement presented + judged vs the OQ-1 criterion; (3) isolated step-smoke on a SEEDED test DB (NOT the live DB); (4) operator-witnessed first live `swing pipeline run` POST-merge. |
| **OQ-7 (operator-paired 2026-06-04)** | CONFIRM KEEP the by-ticker/by-id trade backlinks (isolate ONLY the 3 silent aggregate/queue consumers). Blanket-isolating the backlinks would break legitimate watch-ticker trade linkage. |

**Schema verdict: NONE.** v24 holds. Gotcha #9 (executescript) + #11 (schema-CHECK triad) are N/A. If any task here seems to need a `source_bucket` column, STOP -- D4/L3 ruled it out.

---

## 1. Re-grepped anchors (STEP-0 done at writing-plans against worktree HEAD `db2cc378`)

The spec cites base HEAD `32132654`; the live tree was re-grepped (discipline #2). Live line numbers:

| Anchor | Live location | Confirmed |
|---|---|---|
| Pool predicate | `swing/pipeline/runner.py:1531-1533` `aplus_tickers = [c.ticker for c in candidates if c.bucket == "aplus"]` | YES |
| Empty-pool guard | `runner.py:1535` `if not aplus_tickers:` | YES |
| Empty-pool log | `runner.py:1536-1539` "zero aplus tickers" | YES |
| #27 empty-pool audit | `runner.py:1543-1549` (`expected_pool`, `actual_aplus_pool`, `reason`) | YES |
| FDL universe-context | `runner.py:1615-1623` (`universe_size:1616`, `stage_2_pass_rate:1.0` + comment `:1617`) | YES |
| Detect loop | `runner.py:1665` `for ticker in aplus_tickers:` | YES |
| Detect-step fetch | `runner.py:1668` `ohlcv_cache.get_or_fetch(ticker=ticker, window_days=400)` | YES |
| Empty-emit log | `runner.py:1828-1834` "across %d aplus tickers" | YES |
| Pass-2 `candidate_by_ticker` | `runner.py:2071` `{c.ticker: c for c in candidates}` (ALL candidates, not just pool) | YES |
| `insert_evaluation` | `runner.py:2195` | YES |
| Detection SELECT-then-skip | `runner.py:2239-2245` (`source='pipeline' AND ticker=? AND detection_date=? AND pattern_class=?`) | YES |
| Detection build + `build_finviz_screen_state(cand)` | `runner.py:2293-2308` (`:2301`) | YES |
| Final-log "aplus tickers" | `runner.py:2332-2337` | YES |
| `_advance_status` | `runner.py:2373-2424` | YES |
| `_bar_for_date` | `runner.py:2427-2482` | YES |
| `_sessions_since` | `runner.py:2485-2500` (needs only `data_asof_date` + `observation_date`) | YES |
| `_step_pattern_observe` | `runner.py:2503-2564` | YES |
| Observe open-pool + `actual_open_pool` audit | `runner.py:2525-2536` (`actual_open_pool:2534`) | YES |
| Observe per-detection loop / pre-fetch point | `runner.py:2540-2564` (`_bar_for_date` call `:2544`) | YES |
| `build_finviz_screen_state` | `swing/pipeline/temporal_metadata.py:119-127` (emits `"bucket": candidate.bucket` `:123`) | YES |
| `bucket_for` | `swing/evaluation/scoring.py:13-39` (aplus = 0 VCP fails; watch = 1-2; both pass the TT/Stage-2 gate) | YES |
| Pattern-outcomes denominator | `swing/metrics/pattern_outcomes.py:66-133` (`_count_reached_1r_hit_stop`; SQL `:85-127`; LEFT JOIN candidates `:107-111`) | YES |
| Review-form B.4 cohort CTE | `swing/web/view_models/patterns/review_form.py:338-376` (CTE `:340-349`, `ORDER BY pe.id DESC LIMIT ?` `:347-348`) | YES |
| active_learning queue | `swing/patterns/active_learning.py:241-246` (`SELECT ... FROM pattern_evaluations WHERE pipeline_run_id = ?`) | YES |
| Backlink (dashboard) | `swing/web/view_models/dashboard.py:787-804` (by `(pipeline_run_id, ticker, pattern_class)` then by `(run, ticker)`) | YES (KEEP) |
| Backlinks (others, KEEP) | `web/view_models/trades.py:698`, `web/routes/trades.py:1162`, `trades/entry.py:332`, `web/view_models/journal.py:288`, `data/repos/pattern_evaluations.py` by-id | YES (KEEP) |
| PE table DDL | `swing/data/migrations/0020_*.sql:230-254` (`pipeline_run_id NOT NULL REFERENCES pipeline_runs(id) ON DELETE CASCADE` `:232-233`; unique `(pipeline_run_id, ticker, pattern_class)` `:253-254`) | YES |
| PDE table DDL | `swing/data/migrations/0022_*.sql:24-62` (`finviz_screen_state` nullable `:36`; `pipeline_run_id ... ON DELETE SET NULL` `:41-42`; unique `(source, ticker, detection_date, pattern_class)` `:50-51`) | YES |
| candidates DDL | `0001_*.sql:26,28,44` (`evaluation_run_id NOT NULL`, `bucket NOT NULL CHECK(...)`, index `(evaluation_run_id, bucket)`) | YES |
| pipeline_runs cols | `pipeline_runs.evaluation_run_id` added `0006_*.sql:18`; `finished_ts TEXT` (nullable) + `action_session_date TEXT NOT NULL` `0003_*.sql:123,126` | YES |
| `EXPECTED_SCHEMA_VERSION` | `swing/data/db.py:51` `= 24` (STAYS) | YES |
| `actual_aplus_pool` readers | EXACTLY ONE: `tests/pipeline/test_step_pattern_detect_temporal_extension.py:195`. NO production reader. | YES |
| `list_observable_detections` | `swing/data/repos/pattern_detection_events.py:113-155` returns full `PatternDetectionEvent` incl. `finviz_screen_state` (row[8]) | YES |
| PipelineConfig | `swing/config.py:157-171` (`@dataclass(frozen=True)`; observe windows `:170-171`) | YES |
| `json_extract` | Production-proven (`journal/tos_import.py:1318`, `trades/reconciliation_classifier.py:108`); works in bundled sqlite3 | YES |
| Shared test fixtures | `tests/pipeline/conftest_temporal.py` (`tmp_db_v22`, `_build_bars`, `_StubOhlcvCache`, `_FakeLease`, `_Cfg`/`_cfg`, `_seed_aplus_candidate_and_run`, `_seed_run_with_zero_aplus`, `_drive_detect`) | YES |

**Re-grep at execution.** Line numbers drift between writing-plans and executing-plans; each task says WHAT to find, not only the line. Re-grep the symbol before editing.

---

## 2. File map

**Create:**
- `swing/evaluation/pe_origin.py` -- the single source of truth for the PROVABLE-aplus PE SQL predicate constant (`PROVABLE_APLUS_PE_PREDICATE`). One responsibility: hold + document the ladder SQL so the 3 consumers stay in lock-step (Expansion #4 SQL-skeleton discipline).
- `tests/evaluation/test_pe_origin_ladder.py` -- the 6-case ladder regression (the ladder's own discriminating tests).
- `tests/metrics/test_pattern_outcomes_aplus_isolation.py` -- pattern-outcomes denominator pre/post-isolation.
- `tests/web/view_models/patterns/test_review_form_aplus_isolation.py` -- review-form B.4 cohort isolation + filter-before-LIMIT regression.
- `tests/patterns/test_active_learning_aplus_isolation.py` -- active_learning queue isolation.
- `tests/web/view_models/test_pe_backlink_keep.py` -- the backlink-KEEP guard test (no production change).
- `tests/pipeline/test_pattern_pool_widen.py` -- the detect-pool widen + provenance-by-construction + bucket-flip idempotency + #27 audit-shape tests.
- `tests/pipeline/test_pattern_pool_dormant_levers.py` -- Lever 1 + Lever 2 dormant/active audit-accuracy + repeated-runs-no-refetch.
- `tests/pipeline/test_observe_load_instrumentation.py` -- the observe-load net-new-fetch counter + observe-scaling.

**Modify:**
- `swing/metrics/pattern_outcomes.py:85-127` -- add the aplus ladder to `_count_reached_1r_hit_stop`.
- `swing/web/view_models/patterns/review_form.py:340-349` -- add the aplus ladder INSIDE the cohort CTE (filter-before-LIMIT).
- `swing/patterns/active_learning.py:241-246` -- add the aplus ladder to the queue query.
- `swing/pipeline/runner.py` -- the predicate widen + rename + #27 audit reshape (Slice 1); the Lever 1 cap + audit (Slice 3); the Lever 2 shed + audit + the observe-load counter (Slice 3).
- `swing/config.py:157-171` -- add 3 dormant cfg knobs to `PipelineConfig`.
- `tests/pipeline/conftest_temporal.py` -- add `_seed_aplus_watch_skip_candidates_and_run` + extend the `_Cfg._Pipeline` stub with the 3 new knobs (default `None`).
- `tests/pipeline/test_step_pattern_detect_temporal_extension.py:195` -- update the lone `actual_aplus_pool` reader to the new audit shape.
- Any existing detect/observe fixtures that assume aplus-only (Task D1 enumerates + re-baselines via the actual pytest run).

**Untouched (verified):** `swing/data/` migrations (NO schema change); `swing/data/db.py:51` (`EXPECTED_SCHEMA_VERSION` stays 24); `swing/integrations/schwab/` (L2 LOCK); the KEPT backlink callsites.

---

## 3. Slice ordering + the binding sequencing constraint

The spec (Sec 9) binds: **Slice 2 (consumer isolation) MUST land WITH or BEFORE Slice 1's widen behavior reaches the live pipeline** -- else the first widened run silently shifts the tile/cohort/queue.

**Chosen ordering: ISOLATION FIRST.** Execute spec-Slice-2 (isolation) as **Part A**, spec-Slice-1 (widen) as **Part B**, spec-Slice-3 (levers + measurement) as **Part C**, then re-baseline + gate as **Part D**. Task numbers are linear across the whole plan in execution order; the spec-slice mapping is in each part header.

**Why this satisfies the constraint:**
1. **Branch-atomic merge.** The orchestrator merges the entire branch to `main` in one move (memory `feedback_orchestrator_performs_merge`); the live pipeline only ever runs off `main`. So isolation + widen reach the live pipeline together at merge regardless of intra-branch order -- the constraint cannot be violated by this single-branch arc.
2. **Test-baseline cleanliness (the real reason to order isolation first).** With isolation landed first, Part B's widen tests can assert the invisible-widen property immediately (the displayed counts do not move) against already-protected consumers, and no intermediate commit on the branch has a widened-but-unprotected detect step.
3. **Isolation is independently testable + shippable BEFORE the widen exists.** The isolation tests plant synthetic watch-origin `pattern_evaluations` rows directly (not via the widened pipeline), so Part A is green on its own. On real pre-widen data every PE is aplus-origin, so the ladder filter is a no-op on production rows (no displayed count changes) -- Part A is a safe, dark, standalone landing.
4. **The historical gate degrades correctly pre-widen.** The ladder's step-3 boundary (the first run emitting a watch-origin PDE) is NULL before the widen ships, so all pre-widen "neither candidate nor PDE" rows are INCLUDED (correct -- they are all aplus by construction). After Part B ships and the first widened run produces watch PDEs, the boundary self-defines.

---

## 4. The PROVABLE-aplus ladder (THE substance -- pinned exact SQL)

`pattern_evaluations` has NO bucket column (D4 forbids one). A PE row's origin bucket is reached by a PROVABLE ladder, evaluated in order. **A naive `OR c.id IS NULL` is UNSOUND (Codex R2 leak -- a future watch PE whose candidate is later deleted would match `c.id IS NULL` and leak into the aplus-only aggregate).** The ladder closes that leak.

**Ladder semantics (per spec Sec 6.3):**
1. **Fast path** -- the candidate row still exists with `bucket='aplus'` (join PE -> pipeline_runs -> candidates on `(ticker, evaluation_run_id)`).
2. **Robust path** -- the bucket LOCKED in the detection event's `finviz_screen_state` JSON is `aplus` (join PE -> PDE on `(pipeline_run_id, ticker, pattern_class)`; used when the candidate is pruned but the PDE survives -- PDE `pipeline_run_id` is `ON DELETE SET NULL`, so the PDE row itself is never deleted by app code).
3. **MANDATORY historical gate** -- a PE with NEITHER a candidate NOR a PDE is aplus BY CONSTRUCTION iff its run is **strictly before the FIRST widened run**. Boundary = the earliest run that emitted a watch-origin PDE (`finished_ts` primary; `action_session_date` fallback ONLY when the self-run lacks `finished_ts`). A NULL boundary => no widen has shipped => INCLUDE.
4. **Otherwise (post-widen, unprovable): EXCLUDE** -- it can never leak a watch row.

**Leak-vector note (verified):** `pattern_evaluations.pipeline_run_id` is `ON DELETE CASCADE` (migration 0020:232-233), so deleting a run removes its PE rows ENTIRELY -- there is NO surviving-PE-after-run-pruning vector. The ONLY leak vector is **candidate loss** (a `candidates` row removed while its PE + run survive), which steps 2-4 handle.

**The constant (pinned -- `swing/evaluation/pe_origin.py`). The consuming SELECT MUST alias `pattern_evaluations` as `pe`. The predicate adds NO bind parameters (all literals), so every consumer's existing `?` parameter tuple is unchanged.**

```python
# swing/evaluation/pe_origin.py
"""Provenance-by-origin filtering for pattern_evaluations rows.

The pool-widening arc (2026-06-04) admits watch-origin pattern_evaluations rows
into the nightly detect step. The 3 silent aggregate/queue consumers must stay
aplus-origin-only so the widen is invisible to operator-facing surfaces. There
is NO bucket column on pattern_evaluations (D4 -- no schema change); the origin
is reached by the PROVABLE-aplus ladder below.

CONTRACT: the consuming SELECT MUST alias pattern_evaluations as ``pe``. The
predicate references pe.pipeline_run_id, pe.ticker, pe.pattern_class and adds
NO bind parameters (all literals) -- interpolate it into a WHERE clause without
disturbing the consumer's ``?`` positions. Internal subquery aliases are
suffixed ``_pa``/``_w`` to avoid shadowing the consumer's own aliases.
"""
from __future__ import annotations

# TRUE iff the pe row is PROVABLY aplus-origin (see plan section 4).
PROVABLE_APLUS_PE_PREDICATE = """(
    EXISTS (
        SELECT 1 FROM pipeline_runs pr_pa
        JOIN candidates c_pa
          ON c_pa.evaluation_run_id = pr_pa.evaluation_run_id
         AND c_pa.ticker = pe.ticker
        WHERE pr_pa.id = pe.pipeline_run_id
          AND c_pa.bucket = 'aplus'
    )
    OR EXISTS (
        SELECT 1 FROM pattern_detection_events pde_pa
        WHERE pde_pa.pipeline_run_id = pe.pipeline_run_id
          AND pde_pa.ticker = pe.ticker
          AND pde_pa.pattern_class = pe.pattern_class
          AND json_extract(pde_pa.finviz_screen_state, '$.bucket') = 'aplus'
    )
    OR (
        NOT EXISTS (
            SELECT 1 FROM pipeline_runs pr_h
            JOIN candidates c_h
              ON c_h.evaluation_run_id = pr_h.evaluation_run_id
             AND c_h.ticker = pe.ticker
            WHERE pr_h.id = pe.pipeline_run_id
        )
        AND NOT EXISTS (
            SELECT 1 FROM pattern_detection_events pde_h
            WHERE pde_h.pipeline_run_id = pe.pipeline_run_id
              AND pde_h.ticker = pe.ticker
              AND pde_h.pattern_class = pe.pattern_class
        )
        AND CASE
            WHEN (
                SELECT MIN(pr_w.finished_ts) FROM pipeline_runs pr_w
                JOIN pattern_detection_events pde_w
                  ON pde_w.pipeline_run_id = pr_w.id
                WHERE json_extract(pde_w.finviz_screen_state, '$.bucket') = 'watch'
            ) IS NULL
                THEN 1
            WHEN (
                SELECT pr_s.finished_ts FROM pipeline_runs pr_s
                WHERE pr_s.id = pe.pipeline_run_id
            ) IS NOT NULL
                THEN CASE WHEN (
                        SELECT pr_s.finished_ts FROM pipeline_runs pr_s
                        WHERE pr_s.id = pe.pipeline_run_id
                    ) < (
                        SELECT MIN(pr_w.finished_ts) FROM pipeline_runs pr_w
                        JOIN pattern_detection_events pde_w
                          ON pde_w.pipeline_run_id = pr_w.id
                        WHERE json_extract(pde_w.finviz_screen_state, '$.bucket') = 'watch'
                    ) THEN 1 ELSE 0 END
            ELSE CASE WHEN (
                        SELECT pr_s.action_session_date FROM pipeline_runs pr_s
                        WHERE pr_s.id = pe.pipeline_run_id
                    ) < (
                        SELECT MIN(pr_w.action_session_date) FROM pipeline_runs pr_w
                        JOIN pattern_detection_events pde_w
                          ON pde_w.pipeline_run_id = pr_w.id
                        WHERE json_extract(pde_w.finviz_screen_state, '$.bucket') = 'watch'
                    ) THEN 1 ELSE 0 END
        END = 1
    )
)"""
```

The 3 consumers interpolate `PROVABLE_APLUS_PE_PREDICATE` into their existing query strings (see Tasks 2-4). The ladder regression (Task 1) exercises all six branches against a minimal `SELECT COUNT(*) FROM pattern_evaluations pe WHERE <predicate>` on a seeded DB.

---

## PART A -- Consumer isolation (spec Slice 2) -- LANDS FIRST

> Axis (per `feedback_verify_regression_test_arithmetic`): Tasks 2/3/4 discriminate the **pre-isolation vs post-isolation** axis (with the filter, a planted watch row does NOT enter the aggregate; without it, it does). Task 1 discriminates the **ladder-branch** axis. Task 5 discriminates the **intended-backlink-exception vs blanket-isolation** axis.

### Task 1: The provable-aplus ladder constant + the 6-case ladder regression

**Files:**
- Create: `swing/evaluation/pe_origin.py`
- Test: `tests/evaluation/test_pe_origin_ladder.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/evaluation/test_pe_origin_ladder.py
"""The PROVABLE-aplus ladder (plan section 4): all six branches.

Discriminating axis: each case asserts INCLUDE vs EXCLUDE for a pe row whose
ONLY difference is which ladder branch it lands in. A no-op predicate (TRUE for
all) would fail the EXCLUDE cases; a naive `OR c.id IS NULL` would fail the
deleted-candidate watch case (it would leak).
"""
from __future__ import annotations
import sqlite3
import pytest
from swing.data.db import EXPECTED_SCHEMA_VERSION, run_migrations
from swing.evaluation.pe_origin import PROVABLE_APLUS_PE_PREDICATE


def _db(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=EXPECTED_SCHEMA_VERSION, backup_dir=tmp_path)
    return conn


def _run(conn, run_id, *, eval_run_id, asof, session, finished_ts):
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
        "action_session_date, tickers_evaluated, aplus_count, watch_count, "
        "skip_count, excluded_count, error_count) VALUES (?,?,?,?,1,1,0,0,0,0)",
        (eval_run_id, session + "T18:00:00", asof, session))
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, finished_ts, trigger, "
        "data_asof_date, action_session_date, lease_token, state, "
        "evaluation_run_id) VALUES (?,?,?,'manual',?,?,?,?,?)",
        (run_id, session + "T18:00:00", finished_ts, asof, session,
         f"tok{run_id}", "complete", eval_run_id))


def _cand(conn, eval_run_id, ticker, bucket):
    conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
        "adr_pct, tight_streak, pullback_pct, prior_trend_pct, rs_rank, "
        "rs_return_12w_vs_spy, rs_method) VALUES (?,?,?,15.0,2.5,3,5.0,40.0,"
        "85,12.0,'universe')",
        (eval_run_id, ticker, bucket))


def _pe(conn, run_id, ticker, pattern_class="vcp", score=0.7):
    # pattern_evaluations NOT-NULL cols (migration 0020:230-251, VERIFIED at
    # writing-plans): pipeline_run_id, ticker, pattern_class (CHECK detector
    # classes), detector_version, geometric_score, geometric_score_json,
    # composite_score, structural_evidence_json, feature_distribution_log_json,
    # window_start_date, window_end_date, created_at. There is NO `surface`
    # column on this table (that is chart_renders).
    cur = conn.execute(
        "INSERT INTO pattern_evaluations (pipeline_run_id, ticker, "
        "pattern_class, detector_version, geometric_score, "
        "geometric_score_json, composite_score, structural_evidence_json, "
        "feature_distribution_log_json, window_start_date, window_end_date, "
        "created_at) VALUES (?,?,?, 'v1', 0.7, '{}', ?, '{}', '{}', "
        "'2026-05-01','2026-05-20','2026-05-20T18:00:00')",
        (run_id, ticker, pattern_class, score))
    return cur.lastrowid


def _pde(conn, run_id, ticker, bucket, pattern_class="vcp"):
    import json
    conn.execute(
        "INSERT INTO pattern_detection_events (ticker, detection_date, "
        "data_asof_date, pattern_class, structural_anchors_json, "
        "composite_score, detector_version, finviz_screen_state, source, "
        "per_pattern_metadata_json, pipeline_run_id, created_at) VALUES "
        "(?,?,?,?,'{}',0.7,'v1',?, 'pipeline','{}',?, '2026-05-20T00:00:00Z')",
        (ticker, "2026-05-20", "2026-05-19", pattern_class,
         json.dumps({"bucket": bucket}), run_id))


def _included_ids(conn) -> set[int]:
    rows = conn.execute(
        f"SELECT pe.id FROM pattern_evaluations pe "
        f"WHERE {PROVABLE_APLUS_PE_PREDICATE}").fetchall()
    return {r[0] for r in rows}


def test_ladder_all_six_branches(tmp_path):
    conn = _db(tmp_path)
    # A widen has shipped: run 2 (a later session) emitted a watch PDE, so the
    # historical boundary is run 2's finished_ts.
    _run(conn, 1, eval_run_id=1, asof="2026-05-19", session="2026-05-20",
         finished_ts="2026-05-20T18:30:00")   # pre-widen run
    _run(conn, 2, eval_run_id=2, asof="2026-06-02", session="2026-06-03",
         finished_ts="2026-06-03T18:30:00")   # first widened run (has watch PDE)
    # Case A (step 1 INCLUDE): candidate present, bucket aplus.
    _cand(conn, 1, "AAA", "aplus"); a = _pe(conn, 1, "AAA")
    # Case B (step 1 path -> EXCLUDE): candidate present, bucket watch.
    _cand(conn, 2, "BBB", "watch"); b = _pe(conn, 2, "BBB"); _pde(conn, 2, "BBB", "watch")
    # Case C (step 2 INCLUDE): candidate GONE, PDE bucket aplus.
    _cand(conn, 2, "CCC", "aplus"); c = _pe(conn, 2, "CCC"); _pde(conn, 2, "CCC", "aplus")
    conn.execute("DELETE FROM candidates WHERE ticker='CCC'")
    # Case D (step 2 path -> EXCLUDE): candidate GONE, PDE bucket watch (the
    # Codex-R2 leak vector: must NOT leak).
    _cand(conn, 2, "DDD", "watch"); d = _pe(conn, 2, "DDD"); _pde(conn, 2, "DDD", "watch")
    conn.execute("DELETE FROM candidates WHERE ticker='DDD'")
    # Case E (step 3 INCLUDE): pre-widen historical PE, NO candidate, NO PDE,
    # run strictly before the boundary.
    e = _pe(conn, 1, "EEE")
    # Case F (step 4 EXCLUDE): post-widen PE on the widened run, NO candidate,
    # NO PDE (pathological), run NOT before the boundary.
    f = _pe(conn, 2, "FFF")
    conn.commit()
    got = _included_ids(conn)
    assert a in got   # step 1 aplus
    assert b not in got   # step 1 watch
    assert c in got   # step 2 aplus
    assert d not in got   # step 2 watch (no leak)
    assert e in got   # step 3 historical
    assert f not in got   # step 4 unprovable


def test_ladder_no_widen_yet_includes_historical(tmp_path):
    # Boundary NULL (no watch PDE anywhere) => historical neither-cand-nor-PDE
    # row INCLUDED.
    conn = _db(tmp_path)
    _run(conn, 1, eval_run_id=1, asof="2026-05-19", session="2026-05-20",
         finished_ts="2026-05-20T18:30:00")
    e = _pe(conn, 1, "EEE")  # no candidate, no PDE, no watch run exists
    conn.commit()
    assert e in _included_ids(conn)
```

- [ ] **Step 2: Run -- verify it fails**

Run: `python -m pytest tests/evaluation/test_pe_origin_ladder.py -q`
Expected: FAIL at import (`ModuleNotFoundError: swing.evaluation.pe_origin`).

> Before implementing, confirm the seed column lists match the live schema: `python -c "import sqlite3,tempfile,os; from swing.data.db import run_migrations,EXPECTED_SCHEMA_VERSION; d=tempfile.mkdtemp(); c=sqlite3.connect(os.path.join(d,'t.db')); run_migrations(c,target_version=EXPECTED_SCHEMA_VERSION,backup_dir=d); [print(t, [r[1] for r in c.execute(f'PRAGMA table_info({t})')]) for t in ('pattern_evaluations','candidates','pipeline_runs','evaluation_runs')]"` -- if a NOT NULL column is missing from a seed INSERT, add it (Expansion #4 SQL-skeleton-column-verify). The seed column lists in this plan were VERIFIED at writing-plans against a migrated v24 tmp DB (the 6-case ladder query passed). NOTE: `pattern_evaluations` has NO `surface` column (the `surface`/`theme2_annotated` cross-column CHECK is on `chart_renders`, migration 0020:185-204 -- a different table); `pattern_evaluations` requires `detector_version`, `geometric_score_json`, `structural_evidence_json`, `feature_distribution_log_json` (all NOT NULL).

- [ ] **Step 3: Write `swing/evaluation/pe_origin.py`** -- the module + `PROVABLE_APLUS_PE_PREDICATE` constant verbatim from plan section 4.

- [ ] **Step 4: Run -- verify it passes**

Run: `python -m pytest tests/evaluation/test_pe_origin_ladder.py -q`
Expected: PASS (2 tests).

- [ ] **Step 5: Commit**

```bash
cd <worktree> && git add swing/evaluation/pe_origin.py tests/evaluation/test_pe_origin_ladder.py
git commit -m "feat(pool-widening): provable-aplus PE ladder + 6-case regression"
```

### Task 2: Isolate the pattern-outcomes tile denominator

**Files:**
- Modify: `swing/metrics/pattern_outcomes.py:85-127` (`_count_reached_1r_hit_stop`)
- Test: `tests/metrics/test_pattern_outcomes_aplus_isolation.py`

- [ ] **Step 1: Write the failing test.** Seed a confirmed `pattern_exemplars` row for `vcp`; seed an aplus-origin PE (candidate aplus) + a watch-origin PE (candidate watch) that BOTH overlap the exemplar window. Assert the denominator counts ONLY the aplus PE.

```python
# tests/metrics/test_pattern_outcomes_aplus_isolation.py
from __future__ import annotations
import sqlite3
import pytest
from swing.data.db import EXPECTED_SCHEMA_VERSION, run_migrations
from swing.metrics.pattern_outcomes import _count_reached_1r_hit_stop
# Reuse the ladder test's seed helpers via a tiny local copy or import.
from tests.evaluation.test_pe_origin_ladder import _run, _cand, _pe, _pde  # noqa


def _exemplar(conn, ticker, pattern_class="vcp"):
    conn.execute(
        "INSERT INTO pattern_exemplars (ticker, start_date, end_date, "
        "proposed_pattern_class, label_source, final_decision, created_at) "
        "VALUES (?, '2026-05-01','2026-05-20', ?, 'curated_gold','confirmed',"
        "'2026-05-20T00:00:00Z')",
        (ticker, pattern_class))


def test_denominator_excludes_watch_origin(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=EXPECTED_SCHEMA_VERSION, backup_dir=tmp_path)
    _run(conn, 1, eval_run_id=1, asof="2026-05-19", session="2026-05-20",
         finished_ts="2026-05-20T18:30:00")
    _exemplar(conn, "AAA"); _exemplar(conn, "BBB")
    _cand(conn, 1, "AAA", "aplus"); _pe(conn, 1, "AAA")        # aplus-origin
    _cand(conn, 1, "BBB", "watch"); _pe(conn, 1, "BBB"); _pde(conn, 1, "BBB", "watch")
    conn.commit()
    denom, _r, _h = _count_reached_1r_hit_stop(conn, pattern_class="vcp")
    # Post-isolation: ONLY the aplus PE counts (denom == 1). Pre-isolation
    # (no filter) would count both (denom == 2). Discriminating axis: the
    # watch PE's presence in the denominator.
    assert denom == 1
```

- [ ] **Step 2: Run -- verify it fails** (`denom == 2`). Run: `python -m pytest tests/metrics/test_pattern_outcomes_aplus_isolation.py -q`. Expected: FAIL (`assert 2 == 1`).

- [ ] **Step 3: Implement.** In `_count_reached_1r_hit_stop`, import the predicate and append it to the WHERE:

```python
from swing.evaluation.pe_origin import PROVABLE_APLUS_PE_PREDICATE
# ... inside the SQL string, the trailing clause becomes:
        f"""
        ...
        WHERE pe.pattern_class = ?
          AND {PROVABLE_APLUS_PE_PREDICATE}
        """,
```

The existing outer `LEFT JOIN candidates c` (aliased `c`) is untouched; the predicate's internal aliases are `_pa`/`_h`/`_w` (no collision). The param tuple `(pattern_class,)` is unchanged (the predicate adds no `?`).

- [ ] **Step 4: Run -- verify it passes** (`denom == 1`).

- [ ] **Step 5: Commit**

```bash
cd <worktree> && git add swing/metrics/pattern_outcomes.py tests/metrics/test_pattern_outcomes_aplus_isolation.py
git commit -m "feat(pool-widening): isolate pattern-outcomes denominator to aplus-origin"
```

### Task 3: Isolate the review-form B.4 cohort (filter-BEFORE-LIMIT)

**Files:**
- Modify: `swing/web/view_models/patterns/review_form.py:340-349` (the cohort CTE)
- Test: `tests/web/view_models/patterns/test_review_form_aplus_isolation.py`

**The filter goes INSIDE the cohort CTE, BEFORE `ORDER BY pe.id DESC LIMIT ?` (Codex R4 MAJOR).** If applied after the CTE, watch rows consume cohort slots then get discarded, yielding a SHRUNKEN cohort vs the aplus-only baseline -- the widen becomes visible as fewer/older results even though no watch row is displayed.

- [ ] **Step 1: Write the failing test** -- the filter-before-LIMIT regression. Seed `cohort_limit + N` aplus PEs at the target composite score, plus watch PEs INTERLEAVED at HIGHER `pe.id` (so a post-CTE filter would let them displace trailing aplus rows). Assert the cohort == the last `cohort_limit` aplus-origin rows (not "top-LIMIT widened then filtered").

```python
# tests/web/view_models/patterns/test_review_form_aplus_isolation.py
from __future__ import annotations
import sqlite3
import pytest
from swing.data.db import EXPECTED_SCHEMA_VERSION, run_migrations
# The cohort lives in the private _build_outcome_distribution(conn, *,
# pattern_class, current_evaluation_id, composite_score, cohort_limit=20)
# (review_form.py:275-280). This test asserts the cohort CTE directly (below);
# an end-to-end assertion via _build_outcome_distribution is added at exec once
# the n<5 suppression interaction is accounted for.
from swing.web.view_models.patterns.review_form import _build_outcome_distribution  # noqa
from tests.evaluation.test_pe_origin_ladder import _run, _cand, _pe, _pde  # noqa


def test_cohort_filter_before_limit(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=EXPECTED_SCHEMA_VERSION, backup_dir=tmp_path)
    _run(conn, 1, eval_run_id=1, asof="2026-05-19", session="2026-05-20",
         finished_ts="2026-05-20T18:30:00")
    score = 0.70
    aplus_ids = []
    # Interleave: aplus, watch, aplus, watch ... watch rows at higher pe.id.
    for i in range(40):
        _cand(conn, 1, f"A{i}", "aplus"); aplus_ids.append(_pe(conn, 1, f"A{i}", score=score))
        _cand(conn, 1, f"W{i}", "watch"); wid = _pe(conn, 1, f"W{i}", score=score)
        _pde(conn, 1, f"W{i}", "watch")
    # current evaluation = a separate aplus row.
    _cand(conn, 1, "CUR", "aplus"); cur = _pe(conn, 1, "CUR", score=score)
    conn.commit()
    # The exact assertion is pinned at exec against the real fn signature; the
    # property: every cohort evaluation_id is an aplus-origin id, and the
    # cohort size equals min(cohort_limit, len(aplus_ids)). A post-CTE filter
    # would yield fewer aplus rows (watch rows displaced trailing aplus).
    # Assert via the cohort SQL directly (the production CTE string), e.g.:
    from swing.evaluation.pe_origin import PROVABLE_APLUS_PE_PREDICATE
    rows = conn.execute(
        f"""WITH cohort AS (
              SELECT pe.id FROM pattern_evaluations pe
              WHERE pe.pattern_class='vcp'
                AND pe.composite_score BETWEEN ? AND ?
                AND pe.id != ?
                AND {PROVABLE_APLUS_PE_PREDICATE}
              ORDER BY pe.id DESC LIMIT 20)
            SELECT id FROM cohort""",
        (score - 0.1, score + 0.1, cur)).fetchall()
    got = {r[0] for r in rows}
    assert got <= set(aplus_ids)          # NO watch row in the cohort
    assert len(got) == 20                  # full cohort (filter-before-LIMIT)
```

- [ ] **Step 2: Run -- verify it fails** (the public fn does not yet apply the filter). Run: `python -m pytest tests/web/view_models/patterns/test_review_form_aplus_isolation.py -q`.

- [ ] **Step 3: Implement.** In the cohort CTE (`review_form.py:340-349`), add the predicate as the final WHERE clause inside the CTE, BEFORE `ORDER BY pe.id DESC LIMIT ?`:

```python
from swing.evaluation.pe_origin import PROVABLE_APLUS_PE_PREDICATE
# cohort CTE becomes:
        f"""
        WITH cohort AS (
            SELECT pe.id AS evaluation_id, pe.composite_score, pe.ticker,
                   pe.pipeline_run_id
            FROM pattern_evaluations pe
            WHERE pe.pattern_class = ?
              AND pe.composite_score BETWEEN ? AND ?
              AND pe.id != ?
              AND {PROVABLE_APLUS_PE_PREDICATE}
            ORDER BY pe.id DESC
            LIMIT ?
        )
        SELECT cohort.evaluation_id, ...
        """,
```

The param tuple `(pattern_class, score_low, score_high, current_evaluation_id, cohort_limit)` is unchanged (predicate adds no `?`).

- [ ] **Step 4: Run -- verify it passes.**

- [ ] **Step 5: Commit**

```bash
cd <worktree> && git add swing/web/view_models/patterns/review_form.py tests/web/view_models/patterns/test_review_form_aplus_isolation.py
git commit -m "feat(pool-widening): isolate review-form B.4 cohort (filter-before-LIMIT)"
```

### Task 4: Isolate the active_learning queue

**Files:**
- Modify: `swing/patterns/active_learning.py:241-246` (`prioritize_candidates` query)
- Test: `tests/patterns/test_active_learning_aplus_isolation.py`

- [ ] **Step 1: Write the failing test.** Seed the latest complete run with 1 aplus PE + many watch PEs (a flood). Assert the queue contains only the aplus-origin row.

```python
# tests/patterns/test_active_learning_aplus_isolation.py
from __future__ import annotations
import sqlite3
import pytest
from swing.data.db import EXPECTED_SCHEMA_VERSION, run_migrations
from swing.patterns.active_learning import prioritize_candidates
from tests.evaluation.test_pe_origin_ladder import _run, _cand, _pe, _pde  # noqa


def test_queue_excludes_watch_origin(tmp_path):
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=EXPECTED_SCHEMA_VERSION, backup_dir=tmp_path)
    _run(conn, 1, eval_run_id=1, asof="2026-05-19", session="2026-05-20",
         finished_ts="2026-05-20T18:30:00")
    _cand(conn, 1, "AAA", "aplus"); _pe(conn, 1, "AAA")
    for i in range(30):
        _cand(conn, 1, f"W{i}", "watch"); _pe(conn, 1, f"W{i}"); _pde(conn, 1, f"W{i}", "watch")
    conn.commit()
    out = prioritize_candidates(conn, top_k=50)
    tickers = {c.ticker for c in out}
    # Post-isolation: queue holds at most the aplus-origin row (priority rules
    # may further filter). Pre-isolation: up to 31 rows including watch flood.
    assert all(t == "AAA" for t in tickers)
    assert "W0" not in tickers
```

- [ ] **Step 2: Run -- verify it fails** (watch tickers present).

- [ ] **Step 3: Implement.** Alias the table `pe` and add the predicate:

```python
from swing.evaluation.pe_origin import PROVABLE_APLUS_PE_PREDICATE
    rows = conn.execute(
        f"SELECT pe.id, pe.ticker, pe.pattern_class, pe.geometric_score, "
        f"pe.composite_score, pe.template_match_score FROM pattern_evaluations pe "
        f"WHERE pe.pipeline_run_id = ? AND {PROVABLE_APLUS_PE_PREDICATE}",
        (latest_run_id,),
    ).fetchall()
```

The param tuple `(latest_run_id,)` is unchanged.

- [ ] **Step 4: Run -- verify it passes.**

- [ ] **Step 5: Commit**

```bash
cd <worktree> && git add swing/patterns/active_learning.py tests/patterns/test_active_learning_aplus_isolation.py
git commit -m "feat(pool-widening): isolate active_learning queue to aplus-origin"
```

### Task 5: The backlink-KEEP guard test (axis: intended-exception vs blanket-isolation)

**Files:**
- Test ONLY: `tests/web/view_models/test_pe_backlink_keep.py` (NO production change -- this guards that a future over-eager isolation does NOT break the backlinks)

- [ ] **Step 1: Write the test.** Seed a run with a WATCH candidate + its watch PE. Resolve the entry-form PE anchor for that ticker; assert it resolves to the watch PE (NOT None).

```python
# tests/web/view_models/test_pe_backlink_keep.py
from __future__ import annotations
import sqlite3
import pytest
from swing.data.db import EXPECTED_SCHEMA_VERSION, run_migrations
from tests.evaluation.test_pe_origin_ladder import _run, _cand, _pe  # noqa


def test_watch_ticker_backlink_resolves(tmp_path):
    """A trade entered on a WATCH ticker must auto-link to its detection's PE
    row (an IMPROVEMENT; changes no displayed statistic). Blanket-isolating
    the backlinks would return None (broken linkage) -- this test fails ONLY
    such a regression; it passes both before AND after the aggregate/queue
    isolation (Tasks 2-4)."""
    conn = sqlite3.connect(tmp_path / "t.db")
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=EXPECTED_SCHEMA_VERSION, backup_dir=tmp_path)
    _run(conn, 1, eval_run_id=1, asof="2026-05-19", session="2026-05-20",
         finished_ts="2026-05-20T18:30:00")
    _cand(conn, 1, "WCH", "watch"); pe_id = _pe(conn, 1, "WCH", pattern_class="vcp")
    conn.commit()
    # The by-(run, ticker, pattern_class) backlink query (dashboard.py:787-792)
    # is NOT filtered by origin. Mirror it directly to assert the KEEP:
    row = conn.execute(
        "SELECT id FROM pattern_evaluations WHERE pipeline_run_id = ? "
        "AND ticker = ? AND pattern_class = ? LIMIT 1",
        (1, "WCH", "vcp")).fetchone()
    assert row is not None and row[0] == pe_id
```

- [ ] **Step 2: Run -- verify it passes** (the backlink is NOT isolated). Run: `python -m pytest tests/web/view_models/test_pe_backlink_keep.py -q`. Expected: PASS.

> This is a guard, not a TDD red->green. It documents OQ-7 (KEEP) and will fail loudly if a later change wrongly isolates the by-ticker/by-id backlinks.

- [ ] **Step 3: Commit**

```bash
cd <worktree> && git add tests/web/view_models/test_pe_backlink_keep.py
git commit -m "test(pool-widening): backlink-KEEP guard for watch-ticker trade linkage"
```

---

## PART B -- The widen + #27 audit + rename + provenance (spec Slice 1)

> Axis: Tasks 6/8/9 discriminate **aplus-only vs aplus+watch** behavior; Task 7 discriminates the **audit field-name/shape** axis (both pool paths do zero detect work on a skip-only fixture -- the discriminator is the renamed/restructured warning, NOT widen behavior).

### Task 6: Widen the predicate + the pool-neutral rename

**Files:**
- Modify: `swing/pipeline/runner.py` (predicate `:1531-1533`; rename `aplus_tickers`->`detect_pool_tickers` at `:1531,1535,1616,1665,1832,2336`; log strings `:1537,1830,2334`; the FDL comment `:1617`)
- Modify: `tests/pipeline/conftest_temporal.py` (add `_seed_aplus_watch_skip_candidates_and_run`)
- Test: `tests/pipeline/test_pattern_pool_widen.py`

- [ ] **Step 1: Add the fixture helper to `conftest_temporal.py`.** Seeds A aplus + W watch + S skip candidates (each with bars in the stub cache so they produce windows):

```python
def _seed_aplus_watch_skip_candidates_and_run(
    db, *, aplus=("AAA",), watch=("WAT1", "WAT2"), skip=("SKP",),
    data_asof_date="2026-05-19", action_session_date="2026-05-20"):
    """Seed a run + EvaluationRun + candidates across buckets; return
    (conn, cfg, lease, eval_run_id, all_tickers)."""
    conn, db_path = db
    from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
    from swing.data.models import Candidate, EvaluationRun
    conn.execute(
        "INSERT INTO pipeline_runs (id, started_ts, trigger, data_asof_date, "
        "action_session_date, lease_token, state) VALUES "
        "(1, ?, 'manual', ?, ?, 'tok-test-1', 'running')",
        ("2026-05-20T18:00:00", data_asof_date, action_session_date))
    eval_run_id = insert_evaluation_run(conn, EvaluationRun(
        id=None, run_ts="2026-05-20T18:00:00", data_asof_date=data_asof_date,
        action_session_date=action_session_date, finviz_csv_path=None,
        tickers_evaluated=len(aplus) + len(watch) + len(skip),
        aplus_count=len(aplus), watch_count=len(watch), skip_count=len(skip),
        excluded_count=0, error_count=0))
    def _mk(ticker, bucket):
        return Candidate(
            ticker=ticker, bucket=bucket, close=15.0, pivot=15.1,
            initial_stop=13.5, adr_pct=2.5, tight_streak=3, pullback_pct=5.0,
            prior_trend_pct=40.0, rs_rank=85, rs_return_12w_vs_spy=12.0,
            rs_method="universe", pattern_tag=None, notes=None,
            criteria=tuple(), sector="", industry="")
    rows = ([_mk(t, "aplus") for t in aplus] + [_mk(t, "watch") for t in watch]
            + [_mk(t, "skip") for t in skip])
    insert_candidates(conn, eval_run_id, rows)
    conn.commit()
    cfg = _cfg(db_path.parent, db_path)
    lease = _FakeLease(db_path, run_id=1, data_asof=data_asof_date)
    return conn, cfg, lease, eval_run_id, tuple(aplus) + tuple(watch) + tuple(skip)
```

- [ ] **Step 2: Write the failing widen test.**

```python
# tests/pipeline/test_pattern_pool_widen.py
from __future__ import annotations
import pytest
from tests.pipeline.conftest_temporal import (  # noqa
    tmp_db_v22, _build_bars, _StubOhlcvCache, _drive_detect,
    _seed_aplus_watch_skip_candidates_and_run)


def test_detect_pool_includes_watch_not_skip(tmp_db_v22, tmp_path):
    conn, cfg, lease, eval_run_id, tickers = \
        _seed_aplus_watch_skip_candidates_and_run((conn_, _path) := tmp_db_v22) \
        if False else _seed_aplus_watch_skip_candidates_and_run(tmp_db_v22)
    bars = {t: _build_bars() for t in tickers}
    cache = _StubOhlcvCache(bars)
    warnings: list[dict] = []
    _drive_detect(conn, cfg, lease, eval_run_id, cache, warnings)
    rows = conn.execute(
        "SELECT DISTINCT ticker FROM pattern_evaluations "
        "WHERE pipeline_run_id = 1").fetchall()
    got = {r[0] for r in rows}
    # aplus+watch enter the detect loop (1 aplus + 2 watch = 3); skip never
    # enters either path. Pre-widen (aplus-only) would yield {AAA} only.
    assert "AAA" in got and "WAT1" in got and "WAT2" in got
    assert "SKP" not in got
    assert len(got) == 3 and len(got) > 1   # > the aplus-only count of 1
```

(Clean up the stray walrus line at exec -- the canonical call is `_seed_aplus_watch_skip_candidates_and_run(tmp_db_v22)`.)

- [ ] **Step 3: Run -- verify it fails** (`got == {"AAA"}`). Run: `python -m pytest tests/pipeline/test_pattern_pool_widen.py::test_detect_pool_includes_watch_not_skip -q`.

- [ ] **Step 4: Implement the widen + rename.** In `runner.py`:
  - `:1531-1533`: `detect_pool_tickers: list[str] = [c.ticker for c in candidates if c.bucket in ("aplus", "watch")]`
  - `:1529-1530` comment: update "= aplus bucket" -> "= aplus|watch buckets (Stage-2 passers; watch differs only in VCP-tightness)".
  - `:1535` `if not detect_pool_tickers:`
  - `:1536-1539` log: "zero detect-pool (aplus|watch) tickers".
  - `:1616` `"universe_size": len(detect_pool_tickers),`
  - `:1617` comment: `# aplus|watch buckets imply Stage 2 pass.`
  - `:1665` `for ticker in detect_pool_tickers:`
  - `:1828-1834` + `:2332-2337` log strings: rename var + "detect-pool" wording.
  - (The #27 audit dict at `:1543-1549` is reshaped in Task 7 -- leave it for now; `actual_aplus_pool` stays a key here and the existing `:195` test still passes until Task 7.)

- [ ] **Step 5: Run -- verify it passes** + ruff. Run: `python -m pytest tests/pipeline/test_pattern_pool_widen.py::test_detect_pool_includes_watch_not_skip -q && ruff check swing/pipeline/runner.py`.

- [ ] **Step 6: Commit**

```bash
cd <worktree> && git add swing/pipeline/runner.py tests/pipeline/conftest_temporal.py tests/pipeline/test_pattern_pool_widen.py
git commit -m "feat(pool-widening): widen detect predicate to aplus+watch + pool-neutral rename"
```

### Task 7: Reshape the #27 empty-pool audit to the standardized vocabulary

**Files:**
- Modify: `swing/pipeline/runner.py:1543-1549` (the empty-pool `run_warnings.append`)
- Modify: `tests/pipeline/test_step_pattern_detect_temporal_extension.py:195` (the lone `actual_aplus_pool` reader)
- Test: `tests/pipeline/test_pattern_pool_widen.py` (add the audit-shape test)

**Standardized vocabulary (spec Sec 3.2 -- SAME keys/units in BOTH the empty-pool audit AND the Lever-1 cap audit, Task 10):** `expected_pool` (total candidate rows), `expected_detect_pool` (aplus+watch pre-cap), `expected_pool_by_bucket` ({aplus, watch}), `actual_pool` (entering the loop, post-cap), `actual_pool_by_bucket`. REMOVE `actual_aplus_pool`.

- [ ] **Step 1: Write the failing audit-shape test.**

```python
def test_empty_pool_audit_uses_standardized_vocabulary(tmp_db_v22, tmp_path):
    from tests.pipeline.conftest_temporal import (
        _StubOhlcvCache, _drive_detect, _seed_aplus_watch_skip_candidates_and_run)
    # Skip-only pool: zero detect work on BOTH paths; the discriminator is the
    # audit SHAPE, not widen behavior.
    conn, cfg, lease, eval_run_id, tickers = \
        _seed_aplus_watch_skip_candidates_and_run(
            tmp_db_v22, aplus=(), watch=(), skip=("SKP1", "SKP2"))
    warnings: list[dict] = []
    _drive_detect(conn, cfg, lease, eval_run_id, _StubOhlcvCache({}), warnings)
    entry = next(w for w in warnings if w["step"] == "pattern_detect")
    assert entry["expected_pool"] == 2          # total candidate rows
    assert entry["expected_detect_pool"] == 0   # aplus+watch pre-cap
    assert entry["expected_pool_by_bucket"] == {"aplus": 0, "watch": 0}
    assert entry["actual_pool"] == 0
    assert entry["actual_pool_by_bucket"] == {"aplus": 0, "watch": 0}
    assert "actual_aplus_pool" not in entry     # the removed key
```

- [ ] **Step 2: Run -- verify it fails** (KeyError / `actual_aplus_pool` present).

- [ ] **Step 3: Implement the reshape** at `runner.py:1543-1549`:

```python
        if run_warnings is not None:
            _aplus_n = sum(1 for c in candidates if c.bucket == "aplus")
            _watch_n = sum(1 for c in candidates if c.bucket == "watch")
            run_warnings.append({
                "step": "pattern_detect",
                "expected_pool": len(candidates),
                "expected_detect_pool": _aplus_n + _watch_n,
                "expected_pool_by_bucket": {"aplus": _aplus_n, "watch": _watch_n},
                "actual_pool": len(detect_pool_tickers),
                "actual_pool_by_bucket": {"aplus": _aplus_n, "watch": _watch_n},
                "reason": "zero aplus|watch candidates",
            })
```

(In the empty-pool branch `detect_pool_tickers` is empty so `actual_pool == 0`; `_aplus_n/_watch_n` are both 0 here, but the keys are still emitted -- the by-bucket split is honest even at zero. Units: counts of candidate rows, NOT tickers entering the loop except `actual_pool`. Expansion #8.)

- [ ] **Step 4: Update the lone existing reader** `test_step_pattern_detect_temporal_extension.py:195` from `assert entry["actual_aplus_pool"] == 0` to `assert entry["actual_pool"] == 0` (and add `assert "actual_aplus_pool" not in entry`).

- [ ] **Step 5: Run -- verify both pass.** Run: `python -m pytest tests/pipeline/test_pattern_pool_widen.py tests/pipeline/test_step_pattern_detect_temporal_extension.py -q`.

- [ ] **Step 6: Commit**

```bash
cd <worktree> && git add swing/pipeline/runner.py tests/pipeline/test_pattern_pool_widen.py tests/pipeline/test_step_pattern_detect_temporal_extension.py
git commit -m "feat(pool-widening): reshape #27 empty-pool audit to standardized vocabulary"
```

### Task 8: Provenance-by-construction confirmation test (D4)

**Files:**
- Test ONLY: `tests/pipeline/test_pattern_pool_widen.py` (no production change -- `build_finviz_screen_state` already emits `"bucket"`; `candidate_by_ticker` is built from ALL candidates `:2071`).

- [ ] **Step 1: Write the test.** Plant ONE watch candidate that produces a detection; assert exactly one detection row whose `finviz_screen_state` JSON carries `"bucket": "watch"`.

```python
def test_watch_detection_tags_bucket_watch(tmp_db_v22, tmp_path):
    import json
    from tests.pipeline.conftest_temporal import (
        _build_bars, _StubOhlcvCache, _drive_detect,
        _seed_aplus_watch_skip_candidates_and_run)
    conn, cfg, lease, eval_run_id, tickers = \
        _seed_aplus_watch_skip_candidates_and_run(
            tmp_db_v22, aplus=(), watch=("WAT1",), skip=())
    cache = _StubOhlcvCache({t: _build_bars() for t in tickers})
    _drive_detect(conn, cfg, lease, eval_run_id, cache, [])
    rows = conn.execute(
        "SELECT finviz_screen_state FROM pattern_detection_events "
        "WHERE ticker='WAT1'").fetchall()
    assert rows, "widened path must emit a detection for the watch ticker"
    assert any(json.loads(r[0]).get("bucket") == "watch" for r in rows)
    # Pre-isolation discriminator: aplus-only path emits ZERO rows for WAT1.
```

- [ ] **Step 2: Run -- verify it passes** (provenance is by construction).

- [ ] **Step 3: Commit**

```bash
cd <worktree> && git add tests/pipeline/test_pattern_pool_widen.py
git commit -m "test(pool-widening): confirm watch detections tag bucket=watch (D4 by construction)"
```

### Task 9: Bucket-flip idempotency / first-detection-wins (Q4)

**Files:**
- Test ONLY: `tests/pipeline/test_pattern_pool_widen.py` (no production change -- the unique index is bucket-agnostic; the SELECT-then-skip at `:2239-2245` is the mechanism).

- [ ] **Step 1: Write the test.** Two same-day runs, same `detection_date`, same ticker: run 1 bucket=watch, run 2 bucket=aplus. Assert exactly ONE `pattern_detection_events` row whose `finviz_screen_state` carries the FIRST run's bucket (`watch`).

```python
def test_bucket_flip_first_detection_wins(tmp_db_v22, tmp_path):
    import json
    from tests.pipeline.conftest_temporal import _build_bars, _StubOhlcvCache
    from swing.pipeline.runner import _step_pattern_detect
    from swing.data.repos.candidates import insert_candidates, insert_evaluation_run
    from swing.data.models import Candidate, EvaluationRun
    conn, db_path = tmp_db_v22
    cache = _StubOhlcvCache({"FLP": _build_bars()})
    # ... seed run 1 (eval_run id=1, pipeline_runs id=1) with FLP bucket=watch,
    #     same data_asof_date + action_session_date; drive detect.
    # ... seed run 2 (eval_run id=2, pipeline_runs id=2) SAME dates, FLP=aplus;
    #     drive detect. (Both runs share detection_date -> the bucket-agnostic
    #     unique index (source,ticker,detection_date,pattern_class) matches.)
    rows = conn.execute(
        "SELECT finviz_screen_state FROM pattern_detection_events "
        "WHERE ticker='FLP'").fetchall()
    assert len(rows) == 1                                   # ONE locked detection
    assert json.loads(rows[0][0])["bucket"] == "watch"     # FIRST run's bucket
    # Discriminating difference: aplus-only path would lock 'aplus' (run 1
    # skips FLP as non-aplus; run 2 inserts aplus). Widened path locks 'watch'.
```

> Exec note: the two runs MUST share `detection_date` (= `action_session_date`) for the bucket-agnostic unique index to match across runs; use distinct `pipeline_runs.id`/`evaluation_run_id` but identical dates. Re-use the seed shape from `_seed_aplus_watch_skip_candidates_and_run` with explicit `id` values.

- [ ] **Step 2: Run -- verify it passes** (1 row, bucket=watch).

- [ ] **Step 3: Commit**

```bash
cd <worktree> && git add tests/pipeline/test_pattern_pool_widen.py
git commit -m "test(pool-widening): bucket-flip first-detection-wins locks watch provenance"
```

---

## PART C -- Dormant relief levers + observe-load instrumentation (spec Slice 3)

> Axis: Tasks 10/11 discriminate **dormant (None) vs active** lever behavior + audit accuracy; Task 12 discriminates the **counter-present vs absent** instrumentation axis. All levers ship DORMANT (knobs default `None`); a silent cap is FORBIDDEN.

### Task 10: Lever 1 -- the dormant DETECT-pool cap + #27 cap audit

**Files:**
- Modify: `swing/config.py:157-171` (`PipelineConfig`: add `detect_watch_pool_cap: int | None = None`)
- Modify: `swing/pipeline/runner.py` (after the predicate at `:1533`: apply the deterministic cap when set; emit the standardized #27 cap audit)
- Modify: `tests/pipeline/conftest_temporal.py` (`_Cfg._Pipeline`: add `detect_watch_pool_cap = None`)
- Test: `tests/pipeline/test_pattern_pool_dormant_levers.py`

**Lever 1 = a FUTURE-growth limiter (bounds detect CPU + the GROWTH of the open-detection population; does NOT relieve an existing backlog).** Deterministic selection: rank watch tickers by `rs_rank` ASCENDING, keep the lowest-N (NOT random -- reproducibility). aplus tickers are NEVER capped.

- [ ] **Step 1: Write the failing tests** (dormant-default + active-cap accuracy).

```python
# tests/pipeline/test_pattern_pool_dormant_levers.py
from __future__ import annotations
import pytest
from tests.pipeline.conftest_temporal import (  # noqa
    tmp_db_v22, _build_bars, _StubOhlcvCache, _drive_detect,
    _seed_aplus_watch_skip_candidates_and_run)


def test_lever1_dormant_default_no_cap_no_audit(tmp_db_v22):
    conn, cfg, lease, eval_run_id, tickers = \
        _seed_aplus_watch_skip_candidates_and_run(
            tmp_db_v22, aplus=("AAA",), watch=("W1", "W2", "W3"), skip=())
    assert cfg.pipeline.detect_watch_pool_cap is None     # dormant default
    cache = _StubOhlcvCache({t: _build_bars() for t in tickers})
    warnings: list[dict] = []
    _drive_detect(conn, cfg, lease, eval_run_id, cache, warnings)
    got = {r[0] for r in conn.execute(
        "SELECT DISTINCT ticker FROM pattern_evaluations").fetchall()}
    assert got == {"AAA", "W1", "W2", "W3"}               # uncapped
    assert not [w for w in warnings if w.get("dropped_count")]  # no cap audit


def test_lever1_active_cap_audit_accuracy(tmp_db_v22):
    conn, cfg, lease, eval_run_id, tickers = \
        _seed_aplus_watch_skip_candidates_and_run(
            tmp_db_v22, aplus=("AAA",), watch=("W1", "W2", "W3"), skip=())
    cfg.pipeline.detect_watch_pool_cap = 1                 # cap watch to 1
    cache = _StubOhlcvCache({t: _build_bars() for t in tickers})
    warnings: list[dict] = []
    _drive_detect(conn, cfg, lease, eval_run_id, cache, warnings)
    audit = next(w for w in warnings
                 if w["step"] == "pattern_detect" and "dropped_count" in w)
    assert audit["expected_detect_pool"] == 4             # 1 aplus + 3 watch
    assert audit["actual_pool"] == 2                      # 1 aplus + 1 watch
    assert audit["dropped_count"] == 2                    # 4 - 2
    assert audit["dropped_bucket"] == "watch"
    assert audit["expected_pool_by_bucket"] == {"aplus": 1, "watch": 3}
    assert audit["actual_pool_by_bucket"] == {"aplus": 1, "watch": 1}
```

(`_Cfg._Pipeline` is a plain class; `cfg.pipeline.detect_watch_pool_cap = N` mutates it for the test. Production `PipelineConfig` is frozen; the cap is read-only there.)

- [ ] **Step 2: Run -- verify they fail** (no cap logic / no knob).

- [ ] **Step 3: Implement.**
  - `config.py`: add `detect_watch_pool_cap: int | None = None` to `PipelineConfig`.
  - `conftest_temporal.py` `_Cfg._Pipeline`: add `detect_watch_pool_cap = None`.
  - `runner.py` after `:1533`: split aplus vs watch, apply the deterministic cap, emit the audit:

```python
    detect_pool_tickers: list[str] = [
        c.ticker for c in candidates if c.bucket in ("aplus", "watch")
    ]
    _cap = getattr(cfg.pipeline, "detect_watch_pool_cap", None) if cfg else None
    if _cap is not None:
        _aplus = [c for c in candidates if c.bucket == "aplus"]
        _watch = sorted((c for c in candidates if c.bucket == "watch"),
                        key=lambda c: c.rs_rank)  # deterministic: lowest rs_rank first
        _kept_watch = _watch[:_cap]
        _capped = [c.ticker for c in _aplus] + [c.ticker for c in _kept_watch]
        if len(_capped) < len(detect_pool_tickers) and run_warnings is not None:
            run_warnings.append({
                "step": "pattern_detect",
                "expected_pool": len(candidates),
                "expected_detect_pool": len(detect_pool_tickers),
                "expected_pool_by_bucket": {
                    "aplus": len(_aplus), "watch": len(_watch)},
                "actual_pool": len(_capped),
                "actual_pool_by_bucket": {
                    "aplus": len(_aplus), "watch": len(_kept_watch)},
                "dropped_count": len(detect_pool_tickers) - len(_capped),
                "dropped_bucket": "watch",
                "reason": (f"watch detect pool capped at {_cap} "
                           "(cfg.pipeline.detect_watch_pool_cap)"),
            })
        detect_pool_tickers = _capped
```

(ASCII-only strings; #16/#32. The cap fires AFTER the empty-pool guard at `:1535` -- if `detect_pool_tickers` is empty the early-return already happened.)

- [ ] **Step 4: Run -- verify they pass** + ruff.

- [ ] **Step 5: Commit**

```bash
cd <worktree> && git add swing/config.py swing/pipeline/runner.py tests/pipeline/conftest_temporal.py tests/pipeline/test_pattern_pool_dormant_levers.py
git commit -m "feat(pool-widening): dormant Lever 1 detect-pool cap + #27 cap audit"
```

### Task 11: Lever 2 -- the dormant OBSERVE-side pre-fetch shed + #27 shed audit

**Files:**
- Modify: `swing/config.py:157-171` (add `observe_max_pending_window_sessions_watch: int | None = None` + `observe_max_post_trigger_window_sessions_watch: int | None = None`)
- Modify: `swing/pipeline/runner.py:2540-2564` (the observe loop: a pre-fetch shed guard BEFORE `_bar_for_date` at `:2544`; emit a `pattern_observe` shed audit)
- Modify: `tests/pipeline/conftest_temporal.py` (`_Cfg._Pipeline`: add the 2 watch-window knobs = None)
- Test: `tests/pipeline/test_pattern_pool_dormant_levers.py`

**Lever 2 = IMMEDIATE relief (a shorter watch-origin observation horizon). The mechanism is a PRE-FETCH SKIP, NOT an `expired` transition** (a no-fetch expiry is impossible without a schema change -- `ohlc_today_json` is NOT NULL). For a watch-origin detection (bucket read from `det.finviz_screen_state`) whose `sessions_since_detection` exceeds the shortened horizon: SKIP -- no fetch, no observation row, no terminal state. `_sessions_since(det.data_asof_date, observation_date)` is computable BEFORE the fetch (it needs only those two dates). Repeated runs cheaply re-skip (no fetch). **NO per-night COUNT cap in V1** (would starve later detections -- deferred to V2).

- [ ] **Step 1: Write the failing tests** (dormant-default + active-shed + repeated-runs-no-refetch).

```python
def test_lever2_dormant_default_no_shed(tmp_db_v22, tmp_path):
    # With both watch-window knobs None, a watch-origin detection past the
    # default aplus horizon is still observed (inherits aplus windows).
    # (Drive _step_pattern_observe with a planted watch-origin detection +
    #  a stub cache; assert an observation row IS written, no shed audit.)
    ...

def test_lever2_active_shed_audit_and_no_fetch(tmp_db_v22, tmp_path, monkeypatch):
    # Set observe_max_pending_window_sessions_watch = 5; plant a watch-origin
    # detection at sessions_since_detection > 5; spy on _bar_for_date.
    calls = []
    import swing.pipeline.runner as R
    real = R._bar_for_date
    monkeypatch.setattr(R, "_bar_for_date",
                        lambda *a, **k: calls.append(a) or real(*a, **k))
    # ... drive observe; assert:
    #   - NO observation row appended for the shed detection
    #   - _bar_for_date NOT called for it (calls excludes its ticker)
    #   - a {"step":"pattern_observe","shed_count":1,"reason":...} audit entry
    ...

def test_lever2_repeated_runs_do_not_refetch_shed(tmp_db_v22, tmp_path, monkeypatch):
    # Drive observe twice with the shed active; assert _bar_for_date is never
    # called for the shed detection on either run (cheap re-skip).
    ...
```

(The `...` bodies are filled at exec using the observe harness in `tests/pipeline/test_step_pattern_observe.py` -- which already plants detections + drives `_step_pattern_observe` with a stub cache + a `resolve_ohlcv_window` stub. Mirror its setup; add a watch `finviz_screen_state` to the planted detection via `_plant_detection` extended with a `bucket="watch"` arg.)

- [ ] **Step 2: Run -- verify they fail.**

- [ ] **Step 3: Implement.**
  - `config.py` + `conftest_temporal.py` `_Cfg._Pipeline`: add the 2 knobs (= None).
  - `runner.py` observe loop, inside `for det in open_dets:` BEFORE `_bar_for_date` (`:2544`):

```python
            # Lever 2 (dormant): watch-origin pre-fetch shed. Read the LOCKED
            # bucket from the detection's finviz_screen_state (never recomputed).
            _pend_w = getattr(cfg.pipeline, "observe_max_pending_window_sessions_watch", None)
            _post_w = getattr(cfg.pipeline, "observe_max_post_trigger_window_sessions_watch", None)
            if _pend_w is not None or _post_w is not None:
                _bucket = None
                if det.finviz_screen_state:
                    try:
                        _bucket = json.loads(det.finviz_screen_state).get("bucket")
                    except (ValueError, TypeError):
                        _bucket = None
                if _bucket == "watch":
                    _sess = _sessions_since(det.data_asof_date, observation_date)
                    _horizon = ((_pend_w if _pend_w is not None else max_pending)
                                + (_post_w if _post_w is not None else max_post))
                    if _sess > _horizon:
                        _shed_count += 1
                        continue   # no fetch, no observation row, no terminal state
```

After the loop (or accumulate then emit once), append the audit when `_shed_count > 0`:

```python
        if _shed_count > 0:
            run_warnings.append({
                "step": "pattern_observe",
                "shed_count": _shed_count,
                "reason": ("watch observe window shortened "
                           "(cfg.pipeline.observe_max_*_watch)"),
            })
```

(`_shed_count = 0` initialized before the loop. `json` is already imported in the observe step's module scope -- confirm at exec; the file imports `json` at top. ASCII strings.)

- [ ] **Step 4: Run -- verify they pass** + ruff.

- [ ] **Step 5: Commit**

```bash
cd <worktree> && git add swing/config.py swing/pipeline/runner.py tests/pipeline/conftest_temporal.py tests/pipeline/test_pattern_pool_dormant_levers.py
git commit -m "feat(pool-widening): dormant Lever 2 observe pre-fetch shed + #27 shed audit"
```

### Task 12: The observe-load net-new-fetch instrumentation + observe-scaling

**Files:**
- Modify: `swing/pipeline/runner.py:2503-2564` (`_step_pattern_observe`: a #27-compliant counter distinguishing in-pool cache-hit vs rotated-out net-new fetch)
- Test: `tests/pipeline/test_observe_load_instrumentation.py`

The measurement probe must distinguish (a) in-pool watch tickers (cache hit -- their bars are kept fresh by `_step_ohlcv`) from (b) rotated-out watch tickers (net-new ~400-day yfinance fetch). Implement as a counter accumulated in the observe loop and emitted as a `pattern_observe` metrics entry (NOT a per-detection warning -- it is informational, but #27-shaped: it states expected vs actual). The net-new signal: `_bar_for_date` cache-hit vs fetch is observable by whether the ticker is in the current run's `candidates` set (in-pool) -- query `candidates` for the run's `evaluation_run_id`.

- [ ] **Step 1: Write the failing test.**

```python
# tests/pipeline/test_observe_load_instrumentation.py
def test_observe_emits_net_new_fetch_counter(tmp_db_v22, tmp_path):
    # Plant 2 open detections: one whose ticker IS in the current candidate set
    # (in-pool), one whose ticker is NOT (rotated out). Drive observe; assert a
    # {"step":"pattern_observe", "observed": N, "net_new_fetch": M,
    #  "in_pool_cache_hit": K} metrics entry with the rotated-out one counted
    #  as net_new.
    ...

def test_observe_scaling_one_obs_per_open_detection(tmp_db_v22, tmp_path):
    # Plant 5 open watch-origin detections; drive observe; assert 5 observation
    # rows (one per open detection) and the idempotent already-observed-today
    # guard holds on a second drive (still 5).
    ...
```

- [ ] **Step 2: Run -- verify they fail.**

- [ ] **Step 3: Implement the counter** in `_step_pattern_observe`: accumulate `observed`, `net_new_fetch`, `in_pool_cache_hit` (in-pool = the detection's ticker is in the current run's candidate set), and emit one metrics entry to `run_warnings` after the loop. Keep it #27-shaped (expected vs actual; no silent zero-work). ASCII strings.

- [ ] **Step 4: Run -- verify they pass** + ruff.

- [ ] **Step 5: Commit**

```bash
cd <worktree> && git add swing/pipeline/runner.py tests/pipeline/test_observe_load_instrumentation.py
git commit -m "feat(pool-widening): observe-load net-new-fetch instrumentation + scaling test"
```

### Task 13: The observe-load MEASUREMENT RUN (executing-plans runbook -- NOT a code task)

**This task produces NO commit; it produces the NUMBERS the operator judges at the OQ-4 gate.** It runs at executing-plans on a SEEDED / isolated DB (NEVER the operator's live DB).

- [ ] **Step 1:** Build a seeded measurement DB mirroring the study snapshot: ~3 aplus + ~249 watch candidates (use `_seed_aplus_watch_skip_candidates_and_run` scaled up, or a dedicated seed script under `scripts/` that is NOT committed to production paths). Each ticker gets a `_build_bars()` frame in the stub cache; for the rotated-out projection, plant N watch detections whose tickers are NOT in the next run's candidate set.
- [ ] **Step 2:** Measure (a) detect-step wall-clock aplus-only vs aplus+watch; (b) observe-step wall-clock + per-night `get_or_fetch` count + the net-new-fetch count from Task 12's counter; (c) the steady-state projection over a ~90-session window (model the daily observe `get_or_fetch` volume + net-new fraction, not just night 1); (d) state + validate the OHLCV cache-hit assumption (in-pool watch -> cached at `window_days=400`; one fetch serves both detect's 400-day window and observe's date-anchored read -- the "return full archive / consumers slice" gotcha).
- [ ] **Step 3:** Present the numbers to the operator and judge against the **acceptance criterion (OQ-1, operator-confirmed):** ACCEPT UNCAPPED iff (a) the nightly pipeline runtime delta (detect+observe) is under the operator budget (proposed default: < ~5 min added on the representative set) AND (b) the steady-state net-new yfinance fetch volume stays under the `OhlcvCache` sliding-window breaker thresholds (no breaker trip on a representative night). If EITHER fails, the operator flips the matching dormant lever (Lever 1 for growth, Lever 2 for an existing backlog) WITH its #27 audit -- never a silent cap.

---

## PART D -- Re-baseline + the pre-merge gate

### Task 14: Re-baseline existing detect/observe fixtures that assume aplus-only

**Files:**
- Modify (as the pytest run reveals): the existing detect/observe/temporal test modules:
  `tests/pipeline/test_step_pattern_detect.py`, `test_step_pattern_detect_template_matching.py`, `test_step_pattern_detect_temporal_extension.py`, `test_step_pattern_observe.py`, `test_temporal_metadata.py`, and the chart-step tests that seed candidates (`test_runner_chart_step_walltime.py`, `test_runner_chart_targets.py`, `test_step_charts_ohlcv_cache_wiring.py`).

> Gotcha #1: trust the final pytest count, not an estimate. Most existing detect tests seed ONLY aplus candidates, so the widen does not change their outcome (no watch rows present). The re-baseline targets are tests that (a) assert a specific detect-pool COUNT that the widen would change, or (b) assert the old `actual_aplus_pool` audit key (already handled in Task 7), or (c) seed watch/skip candidates expecting them excluded.

- [ ] **Step 1: Run the full detect/observe/temporal + metrics + web-VM test subset on the branch HEAD:**

Run: `python -m pytest tests/pipeline/ tests/metrics/ tests/web/view_models/ tests/patterns/ tests/evaluation/ -q`

- [ ] **Step 2:** For each FAIL, classify: is it a CORRECT new behavior (re-baseline the assertion to aplus+watch) or a REGRESSION (fix the code)? Re-baseline only the assertions whose discriminating axis is the widen itself; never silence a regression. For each re-baselined assertion, re-confirm the value under BOTH pre-widen and post-widen paths (`feedback_verify_regression_test_arithmetic`).

- [ ] **Step 3: Run the FULL fast suite:**

Run: `python -m pytest -m "not slow" -q`
Expected: GREEN. Record the exact count (gotcha #1 -- this is the binding number, not the estimate).

- [ ] **Step 4: Commit** (only if re-baseline edits were needed):

```bash
cd <worktree> && git add tests/
git commit -m "test(pool-widening): re-baseline detect/observe fixtures for aplus+watch pool"
```

### Task 15: The pre-merge gate (OQ-4 -- operator-confirmed 4-part)

**No production change. This is the orchestrator/operator gate runbook executed at the executing-plans return.**

1. **Orchestrator QA against reality on disk:** the L1-L6 + the 3 OQ confirmations verbatim; the re-grepped file:line anchors (section 1); the locks preserved (Schwab L2 untouched -- `git diff --stat` shows ZERO `swing/integrations/schwab/` change; `EXPECTED_SCHEMA_VERSION` still 24; NO new migration file; the provable-aplus ladder is the 4-step ladder, NOT `OR c.id IS NULL`; the by-ticker/by-id backlinks are NOT filtered).
2. **The observe-load measurement (Task 13)** presented to the operator + judged against the OQ-1 acceptance criterion.
3. **A controlled pipeline-step smoke on a SEEDED test/isolated DB** (NOT the live nightly DB): drive `_step_pattern_detect` -> `_step_pattern_observe` end-to-end on the seeded ~83x set; confirm the widened detect pool, the watch provenance tags, the isolated consumers' counts unchanged vs the aplus-only baseline, and the #27 audits.
4. **An operator-witnessed first live `swing pipeline run` POST-merge** to confirm acceptable REAL nightly runtime + fetch volume (lighter than the schwabdev/B-7 live gates -- append-only, low blast radius, no schema -- but it confirms the real-world load the isolated smoke can only model). **Re-run the fast suite ON THE MERGED HEAD before any green claim** (`feedback_no_false_green_claim`; isolate the known date-sensitive xdist co-residency flakes -- do NOT carry a branch count forward as the post-merge result).

> Trailer hygiene: before any push, verify `git log -1 --format='%(trailers)'` is `[]`; final `-m` paragraph plain prose (`feedback_commit_message_trailer_parse_hazard`). ZERO `Co-Authored-By`. NO `--no-verify`.

---

## 5. Self-review -- spec coverage matrix

| Spec section / requirement | Plan task(s) |
|---|---|
| Sec 3.1 predicate widen + `aplus_tickers`->`detect_pool_tickers` rename (all sites) | Task 6 |
| Sec 3.2 #27 audit standardized vocabulary; remove `actual_aplus_pool`; update the lone reader | Task 7 |
| Sec 3.3 FDL `universe_size` rename + `stage_2_pass_rate` comment update | Task 6 |
| Sec 3.4 provenance-by-construction (D4 -- confirmed not built) | Task 8 |
| Sec 4.2 observe-load measurement methodology | Task 12 (probe) + Task 13 (run) |
| Sec 4.3 acceptance criterion (OQ-1) | Task 13 Step 3 |
| Sec 4.4 Lever 1 (detect cap, deterministic rs_rank selection) | Task 10 |
| Sec 4.4 Lever 2 (observe pre-fetch shed, no per-night count cap) | Task 11 |
| Sec 5.1 idempotency bucket-agnostic at scale | Task 9 (+ existing machinery, confirmed) |
| Sec 5.2 same-day bucket-flip first-detection-wins | Task 9 |
| Sec 6.2/6.3 the 3 isolated consumers via the provable-aplus ladder | Tasks 1-4 |
| Sec 6.3 the 2 ladder-edge regressions (deleted-candidate watch EXCLUDE; historical neither INCLUDE) | Task 1 (cases D, E) |
| Sec 6.3 filter-before-LIMIT (review-form cohort) | Task 3 |
| Sec 6.4 KEPT by-ticker/by-id backlinks | Task 5 |
| Sec 7.1 tests 1-8 (per-axis discriminating) | Tasks 1-12, 14 |
| Sec 7.2 pre-merge gate (OQ-4 4-part) | Task 15 |
| Sec 8 schema impact NONE (v24) | Verified -- no migration task exists |
| Sec 9 slice ordering + the binding sequencing constraint | Section 3 (isolation FIRST) |

**Placeholder scan:** the `...`-bodied steps in Tasks 11/12/13 are RUNBOOK steps whose exact harness wiring is pinned at exec against the existing `tests/pipeline/test_step_pattern_observe.py` setup (named explicitly); every PRODUCTION code step shows the full code. No "TBD"/"add error handling"/"similar to" placeholders in implementation steps.

**Type/name consistency:** `PROVABLE_APLUS_PE_PREDICATE` (Task 1) is the single name reused in Tasks 2/3/4; `detect_pool_tickers` (Task 6) is the single rename target; the audit vocabulary keys (`expected_pool`/`expected_detect_pool`/`expected_pool_by_bucket`/`actual_pool`/`actual_pool_by_bucket`/`dropped_count`/`dropped_bucket`) are identical across Task 7 (empty-pool) and Task 10 (cap); `shed_count` is Lever-2-only (Task 11).

---

## 6. Task count + line estimate (gotcha #1 -- trust the final pytest count, not this estimate)

- **15 tasks** across 4 parts: Part A (isolation, Tasks 1-5), Part B (widen, Tasks 6-9), Part C (levers + measurement, Tasks 10-13), Part D (re-baseline + gate, Tasks 14-15).
- **~12 commits** (Tasks 13 + 15 produce no commit; Task 14 may be a no-op).
- **~22-30 new tests** (ladder 2, per-consumer 3, backlink-KEEP 1, widen/provenance/flip/audit 4, dormant levers ~5-6, instrumentation/scaling ~3) plus 1 updated existing test. The BINDING count is the final `pytest -m "not slow"` total at Task 14 Step 3.
- **NEW production code:** 1 new module (`pe_origin.py`, ~70 lines), 3 cfg knobs, ~3 consumer one-clause edits, the runner widen+rename+audit+Lever1+Lever2+counter (~80 lines net). NO migration. NO schema change.

---

## 7. Execution handoff

**Plan complete and saved to `docs/superpowers/plans/2026-06-04-pattern-observation-pool-widening-plan.md`.**

**Execution order is BINDING: Part A (isolation) before Part B (widen)** -- isolation lands first so the widen never reaches the live pipeline before the 3 consumers are protected (section 3). Two execution options:

1. **Subagent-Driven (recommended)** -- a fresh subagent per task, two-stage review between tasks.
2. **Inline Execution** -- batch execution with checkpoints via `superpowers:executing-plans`.

The arc closes at the OQ-4 4-part gate (Task 15): orchestrator QA + the observe-load measurement + the seeded step-smoke + the operator-witnessed first live run, with the fast suite re-run on the merged HEAD.
