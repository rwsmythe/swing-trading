# Pattern-Observation Pool Widening (aplus -> aplus+watch) -- Design Spec

**Date:** 2026-06-04
**Phase:** Phase-15 strategic-backlog (B-family) standalone sub-bundle
**Status:** Brainstorming design spec (no production code). Derived from
`docs/pattern-observation-pool-widening-brainstorming-dispatch-brief.md` +
`docs/pattern-observation-pool-widening-commissioning-brief.md` (Sec 10 = the
operator-LOCKED triage D1-D6). Where the two briefs disagree, Sec 10 wins.
**Base HEAD:** `32132654` (the commit that adds the dispatch brief).
**Schema:** v24 -- UNCHANGED by this arc (D4).

---

## 1. Architecture overview

### 1.1 The funnel + why widening the OBSERVED pool adds learning data

`research/studies/finviz-pool-binding-constraints.md` quantifies the candidate
funnel on the operator's production snapshot (1,209 evaluations across 6 distinct
Finviz CSVs):

| Bucket | Count | % | 
|---|---:|---:|
| `aplus` | 3 | 0.25% |
| `watch` | 249 | 20.6% |
| `skip` | 898 | 74.3% |
| `error` | 45 | 3.7% |
| `excluded` | 14 | 1.2% |

**Watch:A+ ratio = 83.0** (249 / 3). The dominant blockers are trend/VCP-quality
(`proximity_20ma` 44%, `ma_stack` 13%, `TT2` 12%), NOT capital criteria
(`risk_feasibility` 2.3%). This is the empirical justification the originating
session established: widening the Finviz price band dilutes the curated A+
substrate, and raising the risk budget grows position SIZE not trade COUNT --
neither adds learning data. The lever that DOES add data is widening the OBSERVED
pool from aplus to aplus+watch, growing the forward-walk population ~83x **at zero
capital risk and zero Finviz-screen change.** This realizes the applied-research
arc closure (2026-05-27) forward direction: learn from the OBSERVATION log, not
from forced trades.

> The 83x is the snapshot ratio, NOT a binding constant. The brainstorm uses it to
> MODEL the load; the writing-plans/execution phases MEASURE the live numbers (gotcha
> #1: trust measurement, not the snapshot). 11 of 14 snapshot runs produced ZERO aplus
> (the funnel can be aplus-empty); watch is the population that reliably accumulates.

### 1.2 The one-predicate trigger -- and why the substance is elsewhere

The code trigger is a single predicate at
[`swing/pipeline/runner.py:1531-1533`](../../../swing/pipeline/runner.py):

```python
aplus_tickers: list[str] = [c.ticker for c in candidates if c.bucket == "aplus"]
```

becomes `c.bucket in ("aplus", "watch")`. Everything else in `_step_pattern_detect`
(window generation, the 5-detector registry, SELECT-then-INSERT idempotency,
the composite-score histogram seed) is pool-agnostic. `_step_pattern_observe` has
NO bucket predicate at all -- it observes every OPEN pipeline detection -- so
widening DETECT automatically scales OBSERVE as a consequence (no observe-predicate
change).

**The predicate is trivial. The substance is:**
1. The observe-load model + an operator-judgeable acceptance criterion + a dormant
   cap mechanism (Sec 4).
2. The provenance-by-construction confirmation (Sec 3.4 / Sec 8 -- D4).
3. Idempotency + first-detection-wins provenance under ~83x population + same-day
   bucket flips (Sec 5).
4. Consumer isolation -- the detect step also writes the sibling `pattern_evaluations`,
   which HAS operator-facing consumers; the aggregate/queue ones must be isolated to
   aplus-origin so the widen stays invisible (Sec 6 -- the substantive surface a Codex
   round corrected).
5. The test rework (Sec 7).

### 1.3 The bucket semantics (why widening is correct, not a gate relaxation)

[`swing/evaluation/scoring.py:13-39`](../../../swing/evaluation/scoring.py)
(`bucket_for`):
- `aplus` = risk-pass AND TT-gate-pass AND zero VCP fails.
- `watch` = risk-pass AND TT-gate-pass AND 1-2 VCP fails.
- `skip` = risk-fail OR TT-gate-fail OR 3+ VCP fails.

**Consequence: both aplus AND watch PASS the Trend-Template / Stage-2 gate.** They
differ only in VCP-tightness. Widening to aplus+watch does NOT relax any gate; it
admits Stage-2 passers with looser VCP geometry into the OBSERVATION substrate.
This is why `skip` is excluded (D3): skip is mostly trend-template failures --
low-signal, much higher cost.

---

## 2. Pre-locked decisions (L1-L6, from commissioning brief Sec 10 / D1-D6)

These are LOCKED by the operator at commissioning (2026-06-03). The spec propagates
them; deviation requires a return-trip to the operator.

- **L1 (scope) -- D1.** Widen the `_step_pattern_detect` pool predicate from
  `bucket=='aplus'` to `bucket IN ('aplus','watch')` (+ the consequent observe-load
  scaling) ONLY. NO trade-management / sizing / bucket-assignment / recommendation
  change. NO Finviz-screen change. NO beyond-Finviz universe net (separate future
  commissioning). NO new operator-facing surface that reads the widened log. NO
  historical backfill (forward-walk only, from ship date). The risk-budget / `#3`
  hypothesis discussion is PARKED.
- **L2 / L3 (pool) -- D3.** Pool = `aplus + watch`. NOT `+ skip`.
- **L3 (provenance + NO schema) -- D4.** Bucket provenance rides in the EXISTING
  `finviz_screen_state` JSON (already emits `"bucket"`). NO schema change; NO
  migration; v24 holds; `EXPECTED_SCHEMA_VERSION` stays 24. No first-class
  `source_bucket` column for V1.
- **L4 (observe-load) -- D5: ACCEPT-AND-MEASURE.** The arc MEASURES the widened
  observe runtime + bar-fetch volume (+ the detect-step delta). A cap / sampling /
  shorter watch-origin window is introduced ONLY if the measurement crosses an
  operator-set threshold, and ONLY with a gotcha-#27 `warnings_json` audit. A silent
  cap is FORBIDDEN. **V1 default: no cap** (operator-confirmed OQ-1).
- **L5 (invariants).** Schwab L2 LOCK untouched (zero new Schwab API calls).
  Append-only invariant + `ohlc_today_json` LOCK-at-observation preserved (no
  re-fetch/regeneration of locked facts). The yfinance OHLCV-fetch-scope discipline
  holds.
- **L6 (Codex) -- D6.** SINGLE Codex chain per phase, run to convergence
  (`NO_NEW_CRITICAL_MAJOR`; the ~5-round cap is suspended).

---

## 3. The pool predicate + #27 audit + universe-context

### 3.1 The predicate + the variable rename (OQ-6: RENAME -- operator-confirmed)

Rename `aplus_tickers` -> `detect_pool_tickers` (a pool-neutral, honest name) at
every reference. Orchestrator-verified anchors (TRUST the tree + re-grep at
writing-plans per gotcha #2):

| Line (at base HEAD) | Current | Change |
|---|---|---|
| `runner.py:1531-1533` | `aplus_tickers = [c.ticker for c in candidates if c.bucket == "aplus"]` | predicate -> `c.bucket in ("aplus","watch")`; rename var |
| `runner.py:1535` | `if not aplus_tickers:` | rename var |
| `runner.py:1537-1538` | log "zero aplus tickers" | -> "zero detect-pool (aplus|watch) tickers" |
| `runner.py:1616` | `universe_size = len(aplus_tickers)` | rename var |
| `runner.py:1665` | `for ticker in aplus_tickers:` | rename var |
| `runner.py:1830-1832` | log "across %d aplus tickers" | rename var + "detect-pool" string |
| `runner.py:2332-2334` | log "across %d aplus tickers" | rename var + "detect-pool" string |

The writing-plans phase pins exact line numbers via re-grep (the tree is the
source of truth).

### 3.2 The #27 empty-pool audit (OQ-3: actual_pool + per-bucket breakdown -- operator-confirmed)

`runner.py:1535-1550` -- the empty-pool early-return MUST emit an accurate
`warnings_json` entry (gotcha #27: no silent zero-work completion). Redesign the
shape so the audit is honest about the WIDENED pool (Expansion #8 -- state what each
counter counts):

```python
run_warnings.append({
    "step": "pattern_detect",
    "expected_pool": len(candidates),        # total candidate rows this run
    "expected_detect_pool": 0,               # aplus+watch tickers (pre-cap)
    "expected_pool_by_bucket": {"aplus": 0, "watch": 0},  # the aplus+watch split
    "actual_pool": 0,                        # tickers ENTERING the detect loop (post-cap)
    "actual_pool_by_bucket": {"aplus": 0, "watch": 0},    # post-cap per-bucket split
    "reason": "zero aplus|watch candidates",
})
```

**Standardized audit vocabulary (MANDATORY -- the SAME keys + units in BOTH the
empty-pool audit and the dormant-cap audit, Sec 4.4 -- this closes a Codex MAJOR
that flagged a per-key unit conflict; Expansion #8):**
- `expected_pool` = total candidate rows this run (`len(candidates)`). SAME unit
  everywhere -- never repurposed.
- `expected_detect_pool` = the aplus+watch count BEFORE any cap (the pool the
  predicate selects).
- `expected_pool_by_bucket` = the aplus+watch split before any cap, computed from
  `candidates` pre-predicate (so the empty-pool path still reports
  `{"aplus":0,"watch":0}` even when both are zero).
- `actual_pool` = count of tickers ENTERING the detect loop (= aplus+watch AFTER any
  cap; equals `expected_detect_pool` when uncapped).
- `actual_pool_by_bucket` = the post-cap per-bucket split.
- `dropped_count` (cap path only) = `expected_detect_pool - actual_pool`.
- The field `actual_aplus_pool` is REMOVED. **Back-compat: confirmed safe.** A grep
  of the repo shows the ONLY reader of `actual_aplus_pool` is one test
  (`tests/pipeline/test_step_pattern_detect_temporal_extension.py:195`); NO
  production code reads the warnings_json key. The test is updated in the same task
  (Sec 7). The `pattern_observe` audit field `actual_open_pool` (`runner.py:2534`)
  is UNCHANGED (the observe step has no bucket predicate).

### 3.3 The FeatureDistributionLog universe context (OQ-2: single snapshot -- recommend)

`runner.py:1615-1623` builds `universe_context` for the drift log:
- `universe_size = len(detect_pool_tickers)` -- now the widened count (rename only).
- **`stage_2_pass_rate: 1.0` STAYS CORRECT.** Both aplus AND watch pass the Stage-2
  / Trend-Template gate (Sec 1.3 / `scoring.py:13-39`). Update the INLINE COMMENT
  from `# aplus bucket implies Stage 2 pass` to `# aplus|watch buckets imply Stage 2
  pass` (update the comment, not just the variable -- gotcha-family: stale comment is
  a latent correctness lie). This is an Expansion #8 unit-audit point.
- **OQ-2 resolution: keep the SINGLE detector-universe snapshot for V1.** Do NOT
  split aplus vs watch sub-populations in the FeatureDistributionLog -- it is one
  detector-universe snapshot, and the per-detection `finviz_screen_state` already
  carries the bucket for any future per-bucket analysis. An aplus/watch FDL split is
  a V2 candidate (Sec 10).

### 3.4 Provenance-by-construction (D4 -- confirmed, not built)

`build_finviz_screen_state(candidate)` at
[`swing/pipeline/temporal_metadata.py:119-127`](../../../swing/pipeline/temporal_metadata.py)
ALREADY serializes `{"bucket": candidate.bucket, "rs_rank":..., "rs_method":...,
"criteria": {...}}`. The Pass-2 `candidate_by_ticker` map (`runner.py:2071`) is built
from ALL candidates (`{c.ticker: c for c in candidates}`), not just the detect pool.
Therefore a widened pool's watch detections AUTO-TAG `"bucket": "watch"` with **ZERO
new provenance code**. D4 is satisfied by construction. The brainstorm CONFIRMS this
with a discriminating test (Sec 7); it does NOT build provenance.

---

## 4. The observe-load measurement + bound + the (dormant) cap mechanism (D5 / L4 -- THE SUBSTANCE)

### 4.1 The two load surfaces

**Detect-step delta (CPU, not network).** ~83x more detector invocations/night
(watch ~249 vs aplus ~3 on the snapshot). Each invocation = zigzag window generation
+ 5 detectors + template-match Pass 2, on bars fetched in Pass-1. Watch tickers are
evaluated upstream (`_step_evaluate` requires bars), so their OHLCV is largely cached
in the shared `ohlcv_cache`/archive at the detect-step `window_days=400` fetch
(`runner.py:1668`). The net-new DETECT fetch is small; the cost is CPU. **MODELED:
detect runtime grows roughly linearly in pool size; the per-ticker work is
unchanged.** Measure the wall-clock delta; do not assume.

**Observe-step delta (the binding surface -- network).** `_step_pattern_observe`
(`runner.py:2503-2564`) iterates EVERY open detection and calls
`_bar_for_date(cfg, ohlcv_cache, det.ticker, observation_date)` per open detection
per night. `_bar_for_date` (`runner.py:2427`) calls
`ohlcv_cache.get_or_fetch(ticker=ticker, window_days=400)` then reads the
date-anchored bar via `resolve_ohlcv_window`. Each open detection is observed daily
across its lifecycle window = `observe_max_pending_window_sessions` (default 30) +
`observe_max_post_trigger_window_sessions` (default 60) = up to ~90 sessions
(`config.py:170-171`).

**The binding cost is net-new yfinance fetches for watch tickers that ROTATE OUT of
the candidate pool mid-window.** While a watch ticker remains in the nightly Finviz
candidate set, `_step_ohlcv` keeps its bars fresh and `get_or_fetch` hits cache. But
a detection stays OPEN for up to ~90 sessions; if its ticker drops out of the screen
the next night, `_step_ohlcv` no longer fetches it (the OHLCV-fetch-scope gotcha:
fetch scope = open-trade + candidate tickers ONLY) -- yet the observe step still needs
that ticker's bar, so `_bar_for_date`'s `get_or_fetch` becomes a NET-NEW ~400-day
yfinance fetch. At aplus-only (~3 open detections) this rotation cost is negligible;
at ~83x it is the dominant new cost and the real rate-limit / `PriceCache` /
`OhlcvCache` sliding-window-breaker pressure point.

### 4.2 The measurement methodology (designed here; executed at writing-plans/exec)

The spec DESIGNS how to measure; the actual numbers are produced at
writing-plans/execution and presented to the operator (Sec 7 gate). NO connecting
`swing pipeline` run against the operator's live DB during brainstorm.

Measure on a representative candidate set (a seeded test/isolated DB mirroring the
study snapshot: ~3 aplus + ~249 watch):
1. **Detect-step wall-clock**, aplus-only vs aplus+watch (instrument the existing
   step timing; the runner already records per-step timing in `pipeline_runs`).
2. **Observe-step wall-clock + per-night `get_or_fetch` call count + net-new-fetch
   count.** Net-new = `get_or_fetch` calls that miss the cache/archive and hit
   yfinance. Distinguish (a) in-pool watch tickers (cache hit) from (b) rotated-out
   watch tickers (net-new fetch). Instrument via a counter around `_bar_for_date`
   (writing-plans decides the exact probe -- log-line vs a `warnings_json`/metrics
   counter; whatever it is, it must be #27-compliant).
3. **Sustained-window projection.** Model steady-state: at ~83x detections each
   observed for up to ~90 sessions, project the daily observe `get_or_fetch` volume
   and the net-new-fetch fraction over a full observation window (not just night 1).
4. **OHLCV cache-hit assumption QUANTIFIED.** State the assumption explicitly
   (watch tickers in-pool -> cached at `window_days=400`; the "return full archive /
   consumers slice" gotcha means a single fetch serves both detect's 400-day window
   and observe's date-anchored read). Validate it in the measurement, do not assume.

### 4.3 The acceptance criterion (operator-judged at writing-plans)

Propose a two-part criterion the operator judges against the measured numbers:
> ACCEPT UNCAPPED iff (a) the nightly pipeline runtime delta (detect+observe) is
> under an operator-set budget (proposed default: < ~5 min added on the
> representative set), AND (b) the steady-state net-new yfinance fetch volume stays
> under the `OhlcvCache` sliding-window breaker thresholds (no breaker trips on a
> representative night).

The exact thresholds are the operator's call at writing-plans (informed by the
measured numbers); the spec fixes the SHAPE of the decision, not the numbers.

### 4.4 The dormant cap mechanism (designed even though V1 ships uncapped -- OQ-1)

Per OQ-1 (operator-confirmed: no cap + dormant mechanism), V1 ships uncapped, but
the spec DESIGNS the cap so the operator can flip it on later without re-architecture:

**TWO distinct levers (they bound DIFFERENT costs at DIFFERENT times -- a Codex
MAJOR flagged that the spec previously conflated them):**

- **Lever 1 -- the DETECT-pool cap (FUTURE-only relief).** Cap the number of watch
  tickers admitted to the detect loop per night (`cfg.pipeline.detect_watch_pool_cap:
  int | None = None`; None = uncapped). It bounds the detect-step CPU AND the
  GROWTH of the open-detection population, so it caps FUTURE observe load. **It does
  NOT reduce the EXISTING open-detection backlog:** detections already open keep
  generating `_bar_for_date` calls for the remainder of their ~90-session lifecycle.
  So the detect cap is a steady-state-growth limiter, NOT an immediate breaker-relief
  mechanism. If the operator flips it on because a live night tripped the
  `OhlcvCache` breaker, it will NOT relieve that night -- the backlog runs off over
  ~90 sessions.
- **Lever 2 -- the OBSERVE-side PRE-FETCH SHED (IMMEDIATE relief; shed-without-expiry).**
  For immediate relief of an existing backlog, the lever is a shorter watch-origin
  observation horizon (`observe_max_pending_window_sessions_watch` /
  `_post_trigger_window_sessions_watch`; None = inherit the aplus defaults). **V1 does
  NOT include a per-night count cap** (a count cap over the `detection_id`-ordered
  observable scan would deterministically STARVE later detections forever and needs a
  fairness/selection rule -- Codex R4 MAJOR; deferred to V2, Sec 10). The window shed
  is age-based + applied UNIFORMLY to every watch-origin detection past the horizon,
  so it needs no selection rule and cannot starve. **The mechanism is a PRE-FETCH
  SKIP, NOT an expiry transition (Codex
  R2 MAJOR -- the earlier "transition to expired" claim was WRONG):** the expensive
  operation is `_bar_for_date` (the `get_or_fetch`), and `_advance_status` only runs
  AFTER that fetch; an `expired` row also requires a non-null `ohlc_today_json`
  (migration 0022 NOT NULL), so a no-fetch expiry is impossible without a schema
  change (out of scope, D4). Instead, the shed guard sits in the observe loop BEFORE
  `_bar_for_date` (or as an age filter inside `list_observable_detections`): for a
  watch-origin detection (bucket read from the detection's locked
  `finviz_screen_state`) whose `sessions_since_detection` exceeds the shortened
  horizon, **SKIP it -- no fetch, no observation row, no terminal state.** The
  detection remains nominally "open" (its last real observation is its final record),
  but it is no longer FETCHED -- which is exactly the cost being relieved, on the very
  next run. The trade-off (stated honestly): shed detections never receive a clean
  terminal `expired` row under V1's no-schema-change constraint. (The alternative
  semantic -- spend one more fetch per shed detection to write a real terminal
  `expired` row, relief starting the run AFTER -- is documented but NOT recommended:
  it pays the fetch it is trying to avoid.) Repeated runs cheaply re-skip the same
  shed detections (no fetch); a regression test asserts repeated runs do not re-fetch
  them.

**The selection rule** (Lever 1, when active). Deterministic + documented (e.g. rank
watch tickers by `rs_rank` ascending, take the top N) -- NOT random (reproducibility;
vary nothing across re-runs of the same session). Lever 2 needs no selection rule
(it is window-based, applied uniformly to watch-origin detections).

**The #27 audit (MANDATORY whenever EITHER lever drops/sheds anything).** Lever 1
(detect-pool) reuses the SAME standardized vocabulary as Sec 3.2; Lever 2 (observe
pre-fetch shed) emits a distinct `pattern_observe` entry keyed on `shed_count` +
`reason` (it sheds open detections pre-fetch, a different unit than the detect-pool
counts -- so it does NOT reuse `expected_pool`/`actual_pool`):

```python
# Lever 1 (detect-pool cap):
run_warnings.append({
    "step": "pattern_detect",
    "expected_pool": len(candidates),                 # total candidate rows
    "expected_detect_pool": <aplus+watch before cap>, # the predicate's selection
    "expected_pool_by_bucket": {"aplus": A, "watch": W_full},
    "actual_pool": <count after cap>,
    "actual_pool_by_bucket": {"aplus": A, "watch": W_capped},
    "dropped_count": <expected_detect_pool - actual_pool>,
    "dropped_bucket": "watch",
    "reason": "watch detect pool capped at <N> (cfg.pipeline.detect_watch_pool_cap)",
})
# Lever 2 (observe-side shorter watch window -- pre-fetch shed):
run_warnings.append({
    "step": "pattern_observe",
    "shed_count": <open watch detections shed (not fetched/observed) this run>,
    "reason": "watch observe window shortened to <N> sessions "
              "(cfg.pipeline.observe_max_*_watch)",
})
```

A silent cap is FORBIDDEN (L4 / #27): a wider-but-partially-dropped pool MUST NOT
read as "covered everything." Both levers ship DORMANT in V1 (knobs default None);
the operator flips the one that matches the cost they need to bound (growth vs
existing backlog).

---

## 5. Q4 -- idempotency / partial-retry under the wider pool

### 5.1 The existing idempotency is bucket-agnostic -> correct at ~83x

- The detection unique index `idx_pde_source_ticker_date_class` is
  `(source, ticker, detection_date, pattern_class)` (migration 0022:50-51) --
  **bucket-agnostic.** A same-day re-run is idempotent regardless of bucket.
- Pass-1 idempotency (`runner.py:1724`) skips a detector invocation when the tuple
  already exists; Pass-2 reconcile (`runner.py:1859-1903`) re-reads canonical rows
  inside the fenced write and drops any queued tuple already persisted, then builds
  the histogram universe from the FINAL persisted set (never a phantom). This logic
  is population-size-independent; ~83x more rows only lengthens the loop. The
  detection-event SELECT-then-skip (`runner.py:2239-2245`) is the same pattern at the
  detection-event layer.
- The composite-score histogram seed (`runner.py:1574-1610`, re-read at
  `:1859-1877`) is seeded from existing rows for the `pipeline_run_id` -> correct
  under partial retry at any population size.

**No idempotency change is required.** The brainstorm CONFIRMS correctness at scale;
it does not modify the idempotency machinery.

### 5.2 Same-day bucket flips -> first-detection-wins (the correct V1 semantic)

The finviz study documents per-day pipeline re-runs (14 runs / 6 CSVs; SLDB was
watch on prior days, aplus on others). Under the wider pool a ticker can be `watch`
in run 1 and `aplus` in run 2 of the same `detection_date`. Because the unique index
is bucket-agnostic AND the detection facts (`finviz_screen_state`,
`structural_anchors_json`, `composite_score`, ...) are LOCKED at the FIRST detection
(append-only invariant, migration 0022:8-13), run 2 finds the existing detection event
and SKIPS the DETECTION-EVENT append (the SELECT-then-skip at `runner.py:2239-2245`) --
it does NOT rewrite the locked provenance. (Precision for writing-plans: run 2 may
still write a per-run `pattern_evaluations` row -- that table's idempotency is keyed
per `pipeline_run_id` and a same-day re-run is a distinct run id; that is acceptable
because first-detection-wins applies to the LOCKED DETECTION facts/provenance in
`pattern_detection_events`, not to the per-run PE verdict rows.)

**Decision: first-detection-wins IS the correct V1 semantic.** It matches the
append-only forward-walk invariant: the forward walk begins from the FIRST detection's
data cutoff, and the provenance reflects the state at that cutoff. Re-running the same
session must not mutate frozen facts. (Note: a watch->aplus flip across DIFFERENT
`detection_date`s correctly produces two distinct detections -- the bucket-agnostic
key differs on date; each locks its own provenance. That is the desired forward-walk
behavior, not a flip.)

Discriminating test (Sec 7): plant a bucket flip across two same-day runs (run 1:
ticker=watch; run 2: same ticker same `detection_date`=aplus); assert exactly ONE
detection row, with `finviz_screen_state` carrying the FIRST run's bucket (`watch`).

---

## 6. Q5 -- consumer isolation (the temporal log AND the sibling `pattern_evaluations`)

### 6.1 The temporal log has ZERO consumers (confirmed by grep)

A grep of `swing/web/` for `pattern_detection_events`, `pattern_forward_observations`,
and `list_observable_detections` returns **ZERO hits.** Nothing reads the temporal
observation log; widening it cannot contaminate any existing surface. The
`pattern_outcomes` 9th tile's TRIGGERING numerator (`_count_triggering_n_k`) is
exemplar-driven (`pattern_exemplars` by `label_source`/`final_decision`), not
detection-driven.

### 6.2 BUT the detect step ALSO writes `pattern_evaluations` -- which HAS consumers (Codex MAJOR -- corrected premise)

`_step_pattern_detect` writes a `pattern_evaluations` row (`insert_evaluation`,
`runner.py:2195`) for EVERY emitted detect-pool verdict, BEFORE appending the
detection event. The commissioning brief's Q5 premise (the tile is "exemplar-driven,
uncontaminated") was INCOMPLETE: the tile's reached-1R/hit-stop denominator
(`_count_reached_1r_hit_stop`, `pattern_outcomes.py:100`, wired at `:200`) reads
`pattern_evaluations`. Today detect is aplus-only, so every `pattern_evaluations` row
is aplus-origin and all consumers implicitly see aplus-only. **The widen adds
watch-origin rows -> existing consumers can change.** A full grep of `swing/` for
`pattern_evaluations` reads yields these consumers, categorized by contamination
TYPE:

| Consumer | File:line | Type | V1 treatment |
|---|---|---|---|
| pattern-outcomes tile reached-1R/hit-stop denominator | `metrics/pattern_outcomes.py:100` | **silent aggregate** (a displayed statistic shifts with NO operator action) | **ISOLATE** to aplus-origin |
| review-form B.4 "last N similar-score" cohort | `web/view_models/patterns/review_form.py:343` | **silent aggregate** (cohort composition shifts) | **ISOLATE** to aplus-origin |
| active_learning pattern-review QUEUE (all PEs for latest run) | `patterns/active_learning.py:243` | **queue flood** (~83x more review-queue items, no operator action) | **ISOLATE** to aplus-origin |
| detect-step histogram seed | `runner.py:1587,1596,1861` | **intra-step universe** (the detector universe SHOULD include watch) | KEEP (intended; not contamination) |
| entry-form PE-anchor resolve (dashboard) | `web/view_models/dashboard.py:787,798` | **by-ticker backlink** (operator selected the ticker) | KEEP (see 6.4) |
| entry-form PE-anchor resolve (trades VM) | `web/view_models/trades.py:698` | by-ticker backlink | KEEP |
| entry POST anchor validation | `web/routes/trades.py:1162` | by-id backlink | KEEP |
| entry candidate resolution from pe_id | `trades/entry.py:332` | by-id backlink | KEEP |
| journal pattern_class by pe_id | `web/view_models/journal.py:288` | by-id backlink (already-linked trades) | KEEP |
| repo single-row fetch by id | `data/repos/pattern_evaluations.py:105,147` | by-id repo primitive | KEEP |

### 6.3 The isolation mechanism (D4-safe -- NO schema change)

`pattern_evaluations` has NO bucket column (and D4 forbids adding one). The bucket is
reached by joining `pattern_evaluations -> pipeline_runs -> candidates` on
(`ticker`, `evaluation_run_id`) and filtering `candidates.bucket = 'aplus'`. The
pattern-outcomes + review-form cohort queries ALREADY join `candidates` (for the
trades backlink), so adding the aplus filter is a localized SQL change; the
active_learning queue query (`WHERE pipeline_run_id = ?`) gains a `candidates` join.

**The discriminator MUST be provable, NOT a NULL fallback (Codex R2 MAJOR), AND it
MUST preserve historical aplus rows (Codex R3 MAJOR).** A naive
`WHERE c.bucket = 'aplus' OR c.id IS NULL` is UNSOUND post-ship: a future watch-origin
PE row whose `candidates` row is later removed would match `c.id IS NULL` and LEAK
into the aplus-only aggregate -- the Round-1 leak reappears on a delay. The predicate
is a PROVABLE-aplus ladder, evaluated in order:

1. **Fast path -- the candidate exists:** `candidates.bucket = 'aplus'` (the cheap
   join, reached `pattern_evaluations -> pipeline_runs -> candidates` on
   (`ticker`, `evaluation_run_id`); equivalent result while the candidate is present).
2. **Robust path -- the locked bucket in `pattern_detection_events.finviz_screen_state`.**
   The detection event's `finviz_screen_state` JSON carries the bucket LOCKED at
   detection (Sec 3.4). Join `pattern_evaluations -> pattern_detection_events` on the
   shared (`pipeline_run_id`, `ticker`, `pattern_class`) (both tables carry these --
   PE in migration 0020, PDE in 0022; the detect loop builds both with the same
   `pipeline_run_id`/ticker/class). Require JSON bucket == `aplus`. Use this when the
   candidate is gone but the PDE survives.
3. **MANDATORY historical gate -- pre-widen rows with neither a candidate NOR a PDE.**
   `pattern_evaluations` (migration 0020) PREDATES `pattern_detection_events`
   (migration 0022), so an OLD aplus PE row may have no PDE to read AND a pruned
   candidate. Such a row is aplus-origin BY CONSTRUCTION (every pre-widen pipeline PE
   was aplus-only). INCLUDE it iff its run is **strictly before the FIRST widened
   session**. **BOUNDARY = `MIN(detection_date)` among watch-origin PDEs, compared to
   the PE run's `action_session_date` (DURABLE-COLUMN ordering -- writing-plans Codex
   R3 supersession).** Both `detection_date` (PDE) and `action_session_date`
   (pipeline_runs) are NOT NULL and SURVIVE run pruning. **NOTE (supersedes the
   brainstorm-phase proposal above):** the earlier "first widened `pipeline_run_id` /
   `finished_ts`" boundary was proven UNSOUND at writing-plans -- `PDE.pipeline_run_id`
   is `ON DELETE SET NULL` (0022:41-42), so pruning the first widened run NULLs its
   surviving watch PDE's run id and ADVANCES a `MIN(pipeline_run_id)` boundary, leaking
   gap-run watch rows; and a `MIN(finished_ts)` boundary collapses to NULL when the
   first widened run's `finished_ts` is still NULL. The durable `detection_date`
   boundary moves with neither pruning nor unfinished runs. When NO watch-origin PDE
   exists (no widen shipped yet), INCLUDE. No first-widened-session edge: a watch PE on
   the first widened session has `action_session_date == boundary`, so `< boundary` is
   false -> EXCLUDE. Residual (accepted): a same-merge-calendar-date double-run could
   under-count (DIP) a pre-merge aplus PE that lost both its candidate and PDE -- never
   a watch leak. This clause is NOT optional -- it satisfies the historical-preservation
   requirement (Sec 7.1 test #5) without leaking any post-widen row. The plan pins the
   exact SQL + a `test_ladder_survives_run_pruning_null_pde_run_id` regression.
4. **Otherwise (post-widen, unprovable): EXCLUDE.** A post-rollout PE row that cannot
   be PROVEN aplus is omitted -- it can never leak a watch row.

**Filter BEFORE `LIMIT` for the review-form cohort (Codex R4 MAJOR).** The review-form
B.4 cohort selects inside a CTE with `ORDER BY pe.id DESC LIMIT ?`
(`review_form.py:340-369`) BEFORE joining candidates/trades. The provable-aplus ladder
MUST be applied INSIDE that cohort CTE, BEFORE `ORDER BY ... LIMIT ?` -- so the query
picks the last N similar-score APLUS-ORIGIN evaluations. If the filter is applied
AFTER the CTE, watch rows consume cohort slots and are then discarded, yielding
fewer/older results than the aplus-only baseline (the widen becomes visible as a
SHRUNKEN cohort even though no watch row is displayed). The pattern-outcomes tile
(COUNT-based, no LIMIT) and active_learning queue (also benefit from filtering at the
source) follow the same "filter at selection, not after" discipline.

**Run-pruning precision (Codex R3 MINOR).** `pattern_evaluations.pipeline_run_id` is
`ON DELETE CASCADE` (migration 0020), so deleting a pipeline run removes its PE rows
ENTIRELY (no orphan PE consumer survives a run deletion). The leak vector is therefore
NOT a surviving-PE-after-run-pruning; it is **candidate loss** (a `candidates` row
removed while its PE + run survive) -- which ladder steps 2-4 handle. Writing-plans
pins the exact SQL + the widen-rollout-date source, and adds two regression tests: (a)
post-rollout watch PE with a deleted candidate -> EXCLUDED from every isolated
aggregate; (b) pre-rollout historical aplus PE with neither candidate nor PDE ->
INCLUDED.

### 6.4 Why the by-ticker/by-id backlinks are KEPT (deliberate exception to "isolate all")

The operator's "isolate all (invisible widen)" decision (OQ-7) targets surfaces that
change WITHOUT operator action -- the genuine "the widen became visible" leak (6.2
silent-aggregate + queue). The by-ticker/by-id backlinks are a DIFFERENT category:
they surface a watch PE ONLY when the operator explicitly enters/reviews a trade on
that specific ticker. Today, entering a trade on a watch ticker finds NO PE
(`resolved_pattern_evaluation_id` stays None -> unanchored trade); after the widen
the trade auto-links to its watch detection -- an IMPROVEMENT, not contamination, and
it changes NO displayed statistic. **Blanket-isolating these backlinks to aplus-only
would BREAK legitimate watch-ticker trade linkage** (a watch ticker the operator
trades could no longer anchor to its detection). So they are KEPT, with this rationale
recorded. This is the one place the implementation honors the INTENT of "invisible
widen" (no surface changes without operator action) over a literal reading; it is
**flagged for operator confirmation at writing-plans (OQ-7)** in case the operator
wants the stricter literal isolation (which would then also need a decision on
watch-ticker trade-anchor behavior).

### 6.5 Forward hygiene for future temporal-log consumers (OQ-5: document -- recommend)

No V1 consumer of the temporal log exists, so no V1 code. The spec DOCUMENTS: any
FUTURE consumer of the widened temporal log should DEFAULT to aplus-only with watch
as an explicit opt-in filter (read the bucket from `finviz_screen_state`). This keeps
the eventual consumer surface honest about the looser-VCP provenance of watch-origin
detections. (Statement only; not enforced in V1.)

---

## 7. Test + gate strategy

### 7.1 Test rework (per `feedback_verify_regression_test_arithmetic`)

Per `feedback_verify_regression_test_arithmetic`, each test must DISTINGUISH the
specific CHANGE it guards -- the asserted value computed under BOTH states of that
change, which MUST differ (no tautology). NOTE the discriminating AXIS differs by test
(Codex R2 MAJOR -- the earlier blanket "every test distinguishes aplus-only vs
widened" claim overreached): tests 1/2/3/7 discriminate the **aplus-only vs
aplus+watch** behavior axis; test 4 (empty-pool, skip-only candidates) discriminates
the **audit field-name/shape** axis (both pool paths do zero detect work, so the
discriminator is the renamed/restructured warning, NOT widen behavior); test 5
discriminates the **pre-isolation vs post-isolation** axis; test 6 discriminates the
**intended-backlink-exception vs blanket-isolation** axis (it passes both before AND
after the intended isolation -- it only fails an OVER-eager blanket isolation). Each
bullet names its axis + both expectations. Test surfaces (enumerate via grep at
brainstorm; pin exact files at writing-plans):

1. **Detect-pool widen test.** Fixture: A aplus + W watch + S skip candidates, each
   producing a detectable window. **aplus-only:** detect loop processes A tickers ->
   A detections. **aplus+watch:** A+W tickers -> A+W detections (and skip never
   enters either path). Assert the count == A+W AND strictly > A.
2. **Provenance-by-construction test (D4).** Plant ONE watch candidate that produces
   a detection. **aplus-only:** 0 detection rows for it. **aplus+watch:** 1 row whose
   `finviz_screen_state` JSON carries `"bucket": "watch"`. Assert the widened path's
   row + bucket value.
3. **Bucket-flip idempotency test (Q4 / Sec 5.2).** Two same-day runs, same
   `detection_date`, ticker flips watch (run 1) -> aplus (run 2). **aplus-only:** run
   1 skips the ticker (not aplus) -> run 2 inserts 1 row locked `aplus`.
   **aplus+watch:** run 1 inserts 1 row locked `watch` -> run 2 finds it + skips ->
   still 1 row, bucket STILL `watch` (first-detection-wins). Assert exactly 1 row +
   bucket==`watch` on the widened path (this is the discriminating difference: the two
   paths lock DIFFERENT buckets).
4. **#27 audit-accuracy test.** (a) Widened-empty pool (candidates all `skip`): both
   paths have zero detect pool, but assert the WIDENED audit carries `actual_pool: 0`
   + `actual_pool_by_bucket: {"aplus":0,"watch":0}` + `expected_detect_pool: 0` and NO
   `actual_aplus_pool` key (the field-name/shape is the discriminator; update the
   existing `tests/pipeline/test_step_pattern_detect_temporal_extension.py:195`
   assertion -- the only reader of the old name). (b) Dormant Lever-1 cap path: with
   `detect_watch_pool_cap=N` set and W>N watch tickers, assert
   `dropped_count == (A+W) - actual_pool`, `dropped_bucket=="watch"`, accurate
   `reason`. (c) Dormant Lever-2 observe path: with a shortened watch window, assert
   the `pattern_observe` `shed_count` + `reason` accounting.
5. **PE-isolation tests (Sec 6.2/6.3 -- the Codex MAJOR fix).** For EACH of the 3
   isolated consumers (pattern-outcomes tile denominator, review-form B.4 cohort,
   active_learning queue): plant a watch-origin `pattern_evaluations` row that WOULD
   match/enter the aggregate, plus an aplus-origin row. **Pre-isolation (no filter):**
   the watch row enters -> denominator/cohort/queue count = aplus + watch.
   **Post-isolation (aplus filter):** = aplus only. Assert the widen does NOT change
   the displayed count vs the aplus-only baseline. Plus the two ladder-edge regressions
   (Sec 6.3): (a) a POST-rollout watch PE with a DELETED candidate -> EXCLUDED; (b) a
   PRE-rollout historical aplus PE with NEITHER candidate NOR PDE -> INCLUDED (the
   mandatory historical gate). PLUS a cohort filter-before-LIMIT regression (Codex R4):
   seed MORE aplus rows than the review-form cohort `LIMIT` with watch rows interleaved
   at higher `pe.id`; assert the post-isolation cohort == the aplus-only baseline (the
   last N aplus-origin rows), NOT "top N widened then filtered" (which would drop
   trailing aplus rows the watch rows displaced).
6. **Backlink-KEEP test (Sec 6.4) -- axis: intended-exception vs blanket-isolation.**
   Enter a trade on a watch ticker. **Intended implementation (backlink KEPT):** the
   entry-form PE-anchor resolves to the watch detection's `pattern_evaluations` row
   (NOT None). **Over-eager blanket-isolated implementation:** it returns None (broken
   watch-ticker linkage). Assert the KEPT behavior (resolves NOT None) -- this test
   fails ONLY a regression that wrongly isolates the backlinks; it passes both before
   and after the intended aggregate/queue isolation.
7. **Observe-scaling test.** Seed multiple open watch-origin detections; assert the
   observe step appends one observation per open detection per session and the
   idempotent already-observed-today guard holds at scale; assert the net-new-fetch
   counter/probe (Sec 4.2) is emitted.
8. **Existing-fixture migration.** The detect/observe + temporal e2e fixtures that
   assume aplus-only must be re-baselined for aplus+watch (writing-plans pins the
   exact files; gotcha #1: trust the final pytest count, not an estimate).

### 7.2 Pre-merge gate (OQ-4: QA + measurement + isolated step-smoke + operator-witnessed live run -- operator-confirmed)

This arc has NO UI surface (no browser gate) and NO schema (no live-DB migration
gate). The gate is:
1. **Orchestrator QA** against reality on disk (the L1-L6 verbatim verification +
   file:line anchors + locks-preserved).
2. **The observe-load measurement** (Sec 4.2) presented to the operator at
   writing-plans, judged against the Sec 4.3 acceptance criterion.
3. **A controlled pipeline-step smoke** on a test/isolated DB (NOT the operator's
   live nightly DB) -- exercise `_step_pattern_detect` -> `_step_pattern_observe`
   end-to-end on the seeded ~83x set.
4. **An operator-witnessed first live `swing pipeline run` post-merge** to confirm
   acceptable REAL nightly runtime + fetch volume (operator-chosen at OQ-4). Lighter
   than the schwabdev/B-7 live gates (append-only, low blast radius, no schema
   change), but it confirms the real-world load that the isolated smoke can only
   model. Re-run the fast suite ON THE MERGED HEAD before any green claim
   (`feedback_no_false_green_claim`).

---

## 8. Schema impact -- NONE (v24 holds; D4)

- **NO migration.** `EXPECTED_SCHEMA_VERSION` stays 24.
- The bucket rides in the EXISTING nullable `finviz_screen_state` JSON
  (`pattern_detection_events`, migration 0022:36) -- already emitted by
  `build_finviz_screen_state` (Sec 3.4). NO bucket column; NO `source_bucket` column
  for V1 (D4).
- Gotcha #9 (executescript implicit COMMIT) is N/A (no migration). Gotcha #11
  (schema-CHECK + Python-constant + dataclass-validator triad) is N/A (no schema
  CHECK change).
- The `source` enum (`{pipeline, v2_cohort, d2_baseline, backfill, synthetic}`,
  0022:37-39) is unchanged: watch detections remain `source='pipeline'`.

---

## 9. Slice recommendation

The substance is verification + isolation + measurement + tests, not feature breadth.
Three slices (the Codex MAJOR added the isolation slice -- it is NOT optional, it is
what keeps the widen invisible to existing surfaces per L1):

- **Slice 1 (the widen + audit + rename + provenance confirmation).** The predicate
  widen, the `aplus_tickers` -> `detect_pool_tickers` rename, the #27 audit reshape
  (standardized vocabulary, Sec 3.2), the `stage_2_pass_rate` comment update, the FDL
  `universe_size` rename. Tests: detect-pool widen, provenance-by-construction,
  bucket-flip idempotency, #27 audit-accuracy (widened-empty).
- **Slice 2 (consumer isolation -- the invisible-widen requirement, Sec 6).** Add the
  aplus-origin filter to the 3 change-without-operator-action `pattern_evaluations`
  consumers (pattern-outcomes tile denominator, review-form B.4 cohort,
  active_learning queue); KEEP the by-ticker/by-id backlinks. Tests: the 3
  PE-isolation tests + the backlink-KEEP test (Sec 7.1 #5/#6). **This slice must land
  WITH or BEFORE Slice 1's behavior change reaches the live pipeline** -- otherwise
  the first widened run silently shifts the tile/cohort/queue. (Writing-plans may
  order isolation FIRST so the widen is dark until the surfaces are protected.)
- **Slice 3 (the dormant relief levers + observe-load instrumentation).** The two cfg
  knob families (Lever 1 detect-pool cap with its deterministic selection rule; Lever
  2 observe-side shorter watch window pre-fetch shed; both default None), both #27
  audit shapes, and the observe-load measurement probe. Tests: dormant-lever
  audit-accuracy (both), observe-scaling + net-new-fetch counter, repeated-runs-no-
  refetch for the shed. Ships dormant; feeds the operator's accept-uncapped decision.

Writing-plans sets the final slice ordering; the binding constraint is Slice 2
(isolation) not lagging Slice 1 (the widen) into the operator-visible surfaces.

---

## 10. V1 simplifications + V2 candidates

**V1 simplifications (deliberate YAGNI):**
- No `source_bucket` column -- JSON provenance only (D4).
- No cap active -- dormant mechanism only (OQ-1).
- No FeatureDistributionLog aplus/watch split -- single detector-universe snapshot
  (OQ-2).
- No new consumer surface -- the temporal log accumulates; nothing reads the widened
  slice (L1). Existing `pattern_evaluations` aggregate/queue consumers are ISOLATED to
  aplus-origin (Sec 6) so the widen stays invisible to them.
- No historical backfill -- forward-walk from ship date (L1).

**V2 candidates (explicitly out of V1 scope; documented for the backlog):**
- A first-class indexed `source_bucket` column (-> migration 0025 / v25) IF a future
  consumer needs indexed bucket filtering (the gotcha-#11 paired triad applies then).
- A future operator-facing surface that reads the widened log (defaulting aplus-only,
  watch opt-in per Sec 6.2).
- An aplus/watch FeatureDistributionLog sub-population split.
- A beyond-Finviz universe net (a separate, larger commissioning -- needs its own
  universe source + bar-fetch budget).
- Activating a relief lever (flip the dormant knob) if the live measurement crosses
  the operator threshold.
- A per-night observe COUNT cap (`observe_watch_cap`) -- deferred from V1 (Codex R4):
  a count cap over the `detection_id`-ordered observable scan needs a fairness/
  selection rule to avoid starving later detections; if a future need arises it ships
  with that rule + a no-starvation test. V1's window-based shed needs no selection rule.

---

## 11. Operator decision items (OQ-1..OQ-7) -- resolution log

| OQ | Decision | Resolved by |
|---|---|---|
| OQ-1 observe-load cap policy | **No cap in V1 + dormant mechanism designed** | Operator 2026-06-04 |
| OQ-2 universe-context semantics | **Single detector-universe FDL snapshot** (split = V2) | Recommend (propagated) |
| OQ-3 #27 audit field naming | **`actual_pool` + `actual_pool_by_bucket` (standardized vocabulary, Sec 3.2)** | Operator 2026-06-04 |
| OQ-4 pre-merge gate shape | **QA + measurement + isolated step-smoke + operator-witnessed live run** | Operator 2026-06-04 |
| OQ-5 future-consumer default | **Document aplus-only default, watch opt-in** (no V1 code) | Recommend (propagated) |
| OQ-6 variable rename | **Rename `aplus_tickers` -> `detect_pool_tickers`** | Operator 2026-06-04 |
| OQ-7 `pattern_evaluations` consumer isolation (Codex MAJOR) | **Isolate all (invisible widen)**: aplus-filter the 3 aggregate/queue consumers; KEEP the by-ticker/by-id backlinks (Sec 6.4) | Operator 2026-06-04 |

OQ-1 (cap policy, gated on the measured numbers) and OQ-4 (gate shape) remain
operator-binding at writing-plans -- the acceptance criterion (Sec 4.3) is judged
against the real measurement; the live-run gate (Sec 7.2) is the operator's confirm.
**OQ-7 carries a flagged sub-decision (Sec 6.4):** the by-ticker/by-id backlinks are
KEPT (not isolated) because blanket isolation would break legitimate watch-ticker
trade linkage; the operator confirms this exception at writing-plans (the alternative
-- literal isolation of the backlinks -- additionally requires deciding watch-ticker
trade-anchor behavior).

---

## 12. Cumulative discipline compliance

- **#27 (silent-skip-without-audit).** The widened-pool empty-pool audit + BOTH
  dormant cap levers emit accurate `warnings_json` with a SINGLE standardized field
  vocabulary (Sec 3.2 -- no per-key unit drift, the Codex MAJOR fix); NO silent cap
  (Sec 4.4). Each audit field's UNIT is stated (Expansion #8).
- **Consumer isolation (Sec 6 -- the Codex MAJOR fix to the commissioning brief's Q5
  premise).** The detect step writes the sibling `pattern_evaluations`, which HAS
  operator-facing consumers. The 3 change-without-operator-action consumers
  (pattern-outcomes tile denominator, review-form B.4 cohort, active_learning queue)
  are isolated to aplus-origin so the widen is invisible to them (L1); the
  by-ticker/by-id backlinks are KEPT with rationale (Sec 6.4). PE-isolation +
  backlink-KEEP tests (Sec 7.1 #5/#6).
- **#28 / #29 (exemplar OHLCV cache + historical depth).** Less acute here -- watch
  tickers are IN-universe (unlike out-of-universe exemplars), so their bars are
  fetched upstream. The multi-session observe window re-raises cache-miss handling
  for rotated-out tickers (Sec 4.1); the per-element bad-window isolation in the
  observe loop (skip + #27 no-bar warning, `runner.py:2545-2551`) holds at scale.
- **#24 / #26 (archive freshness / bar-content temporal mutation).** Neutralized by
  construction: the `ohlc_today_json` LOCK-at-observation (0022:11-13) freezes the bar
  at observation and NEVER re-fetches; `_bar_for_date` selects the row whose
  `asof_date == observation_date` (not `iloc[-1]`) and freezes it. Confirm the
  invariant holds for watch tickers that rotate out mid-window (it does -- the lock is
  per-observation, independent of pool membership).
- **yfinance OHLCV-fetch-scope + write-through-archive.** Quantified in Sec 4.1: the
  net-new fetch is the rotated-out-watch-ticker case; the "return full archive /
  consumers slice" gotcha means one fetch serves both detect's 400-day window and
  observe's date-anchored read. External-API empty result treated as transient (F6) is
  preserved (no change to the archive write path).
- **#9 / #11.** N/A (no migration, no schema CHECK change -- Sec 8).
- **L2 LOCK (Schwab).** Untouched -- zero new Schwab API calls (the bars ladder is
  unchanged; sandbox falls through to yfinance as today).
- **Append-only + LOCK-at-observation invariants.** Preserved (Sec 5.2 / Sec 12
  #24/#26).
- **ASCII discipline (#16 / #32).** All new text in this spec + the planned code is
  ASCII (no non-ASCII glyphs in user-facing `print`/`click.echo`/log paths).
- **`feedback_verify_regression_test_arithmetic`.** Each test computes its asserted
  value under BOTH states of the CHANGE it guards (the discriminating axis is named
  per test -- widen-behavior, audit-shape, pre/post-isolation, or
  intended-backlink-exception-vs-blanket-isolation; Sec 7.1).
- **ZERO `Co-Authored-By`; no `--no-verify`; final `-m` paragraph plain prose;** verify
  `git log -1 --format='%(trailers)'` is `[]` before any push
  (`feedback_commit_message_trailer_parse_hazard`).

---

## 13. Position note

This is a standalone Phase-15 strategic-backlog (B-family) sub-bundle -- the cleanest
expression of the applied-research arc closure (2026-05-27) forward direction:
**decouple data-generation from capital deployment.** It grows the forward-walk
learning substrate ~83x by widening an INTERNAL observation accumulator from aplus to
aplus+watch, at zero capital risk, zero Finviz-screen change, and zero schema change.
It is NOT a ruleset / sizing / bucket-assignment / recommendation / Finviz change; NOT
a beyond-Finviz net; NOT a new operator-facing surface. The one-line predicate is the
trigger; the substance is the observe-load bound (accept-and-measure, no silent cap),
the provenance-by-construction confirmation, the idempotency-under-the-wider-pool
reasoning, and the test rework.

---

*End of design spec. The writing-plans phase derives a plan from Sec 9 (slices) +
Sec 7 (tests/gate) + Sec 4 (measurement methodology), re-grepping all file:line
anchors against the live tree (gotcha #2).*
