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
4. The pattern-outcomes-tile isolation confirmation (Sec 6).
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
    "expected_pool": len(candidates),       # total candidate rows this run
    "actual_pool": 0,                        # aplus+watch tickers entering detect
    "actual_pool_by_bucket": {"aplus": 0, "watch": 0},  # per-bucket breakdown
    "reason": "zero aplus|watch candidates",
})
```

- `expected_pool` = total candidate rows (unchanged unit).
- `actual_pool` = count of tickers entering the detect loop (= aplus + watch).
- `actual_pool_by_bucket` = the per-bucket split, computed from `candidates`
  pre-predicate (so the empty-pool path still reports e.g. `{"aplus":0,"watch":0}`
  even when both are zero).
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

- **WHERE it sits.** A cap on the DETECT pool (cap the number of watch tickers
  admitted per night) is the cleanest insertion point -- it bounds both detect and
  the downstream observe population at the source. A shorter watch-origin observation
  window (a watch-specific `observe_max_*`) is the alternative lever; it caps observe
  cost without capping detect coverage. The spec recommends the detect-pool cap as
  the primary knob and notes the shorter-window as a secondary option.
- **The knob.** A `cfg.pipeline.*` setting, default OFF/unbounded in V1, e.g.
  `detect_watch_pool_cap: int | None = None` (None = uncapped) +, if the
  shorter-window lever is wanted, `observe_max_pending_window_sessions_watch` /
  `_post_trigger_window_sessions_watch` (None = inherit the aplus defaults).
- **The selection rule** (when a cap is active). Deterministic + documented (e.g.
  rank watch tickers by `rs_rank` ascending, take the top N) -- NOT random
  (reproducibility; vary nothing across re-runs of the same session).
- **The #27 audit (MANDATORY whenever the cap drops anything).** Emit a
  `warnings_json` entry accounting for every dropped/sampled detection:

```python
run_warnings.append({
    "step": "pattern_detect",
    "expected_pool": <aplus+watch count before cap>,
    "actual_pool": <count after cap>,
    "actual_pool_by_bucket": {"aplus": A, "watch": W_capped},
    "dropped_count": <expected - actual>,
    "dropped_bucket": "watch",
    "reason": "watch pool capped at <N> (cfg.pipeline.detect_watch_pool_cap)",
})
```

A silent cap is FORBIDDEN (L4 / #27): a wider-but-partially-dropped pool MUST NOT
read as "covered everything."

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
(append-only invariant, migration 0022:8-13), run 2 finds the existing row and SKIPS
(SELECT-then-skip) -- it does NOT rewrite the locked provenance.

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

## 6. Q5 -- pattern-outcomes tile isolation

### 6.1 Confirmed uncontaminated by construction (grep result)

- A grep of `swing/web/` for `pattern_detection_events`,
  `pattern_forward_observations`, and `list_observable_detections` returns **ZERO
  hits.** No web surface reads the widened log.
- The 9th metric tile
  [`swing/metrics/pattern_outcomes.py`](../../../swing/metrics/pattern_outcomes.py)
  is **exemplar-driven**: it reads `pattern_exemplars` by `label_source`
  (`closed_loop_review`, `organic_trade_history`, `curated_gold`) + `final_decision`
  (`confirmed`) -- NOT `pattern_detection_events` / `pattern_forward_observations`.

**Implication:** widening the pool cannot contaminate any existing surface -- there
is none. Q5 isolation holds by construction; no V1 code is needed to enforce it.

### 6.2 Forward hygiene for future consumers (OQ-5: document -- recommend)

There is no V1 consumer either way, so no V1 code. The spec DOCUMENTS a forward-hygiene
recommendation: any FUTURE consumer of the widened log should DEFAULT to aplus-only
with watch as an explicit opt-in filter (read the bucket from `finviz_screen_state`).
This keeps the eventual consumer surface honest about the looser-VCP provenance of
watch-origin detections. (Statement only; not enforced in V1.)

---

## 7. Test + gate strategy

### 7.1 Test rework (per `feedback_verify_regression_test_arithmetic`)

Every new/changed test must DISTINGUISH the aplus-only path from the aplus+watch path
-- compute the asserted count under BOTH paths and confirm they differ (so the test
actually exercises the widen). Test surfaces (enumerate via grep at brainstorm; pin
exact files at writing-plans):

1. **Detect-pool widen test.** A fixture with aplus + watch + skip candidates;
   assert the detect loop processes aplus+watch (not skip). Arithmetic: under
   aplus-only, N detections = (aplus count); under aplus+watch, N = (aplus + watch);
   assert the latter (and that it strictly exceeds the aplus-only count).
2. **Provenance-by-construction test (D4).** Plant a watch candidate that produces a
   detection; assert its `finviz_screen_state` JSON carries `"bucket": "watch"`. This
   is the discriminating test that confirms D4 by construction.
3. **Bucket-flip idempotency test (Q4 / Sec 5.2).** Two same-day runs, ticker flips
   watch->aplus; assert exactly one detection row + first bucket (`watch`) locked in
   `finviz_screen_state`.
4. **#27 audit-accuracy test.** (a) Widened-empty pool: assert the warning carries
   `actual_pool: 0` + `actual_pool_by_bucket: {"aplus":0,"watch":0}` and NO
   `actual_aplus_pool` key. (b) Dormant-cap path (even though V1 ships uncapped):
   with the cap knob set, assert the `dropped_count` / `dropped_bucket` /
   `reason` accounting is emitted and accurate. Update the existing
   `tests/pipeline/test_step_pattern_detect_temporal_extension.py:195` assertion
   (the only reader of the old field name).
5. **Observe-scaling test.** Seed multiple open watch-origin detections; assert the
   observe step appends one observation per open detection per session and the
   idempotent already-observed-today guard holds at scale; assert the net-new-fetch
   counter/probe (Sec 4.2) is emitted.
6. **Existing-fixture migration.** The detect/observe + temporal e2e fixtures that
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

This is a small, contained change best executed as a single tight slice (the
substance is verification + measurement + tests, not feature breadth):

- **Slice 1 (the widen + audit + rename + provenance confirmation).** The predicate
  widen, the `aplus_tickers` -> `detect_pool_tickers` rename, the #27 audit reshape
  (`actual_pool` + per-bucket breakdown), the `stage_2_pass_rate` comment update, the
  FDL `universe_size` rename. Tests: detect-pool widen, provenance-by-construction,
  bucket-flip idempotency, #27 audit-accuracy (widened-empty). This is the shippable
  core.
- **Slice 2 (the dormant cap mechanism + observe-load instrumentation).** The cfg
  knob (default OFF), the selection rule, the cap-path #27 audit, and the observe-load
  measurement probe. Tests: dormant-cap audit-accuracy, observe-scaling + net-new-fetch
  counter. V1 ships the mechanism dormant; the measurement feeds the operator's
  accept-uncapped decision.

Writing-plans may merge these into one slice if the diff stays small; the natural
seam is "behavior change" (Slice 1) vs "dormant safety valve + measurement" (Slice 2).

---

## 10. V1 simplifications + V2 candidates

**V1 simplifications (deliberate YAGNI):**
- No `source_bucket` column -- JSON provenance only (D4).
- No cap active -- dormant mechanism only (OQ-1).
- No FeatureDistributionLog aplus/watch split -- single detector-universe snapshot
  (OQ-2).
- No new consumer surface -- the log accumulates; nothing reads the widened slice yet
  (L1).
- No historical backfill -- forward-walk from ship date (L1).

**V2 candidates (explicitly out of V1 scope; documented for the backlog):**
- A first-class indexed `source_bucket` column (-> migration 0025 / v25) IF a future
  consumer needs indexed bucket filtering (the gotcha-#11 paired triad applies then).
- A future operator-facing surface that reads the widened log (defaulting aplus-only,
  watch opt-in per Sec 6.2).
- An aplus/watch FeatureDistributionLog sub-population split.
- A beyond-Finviz universe net (a separate, larger commissioning -- needs its own
  universe source + bar-fetch budget).
- Activating the cap (flip the dormant knob) if the live measurement crosses the
  operator threshold.

---

## 11. Operator decision items (OQ-1..OQ-6) -- resolution log

| OQ | Decision | Resolved by |
|---|---|---|
| OQ-1 observe-load cap policy | **No cap in V1 + dormant mechanism designed** | Operator 2026-06-04 |
| OQ-2 universe-context semantics | **Single detector-universe FDL snapshot** (split = V2) | Recommend (propagated) |
| OQ-3 #27 audit field naming | **`actual_pool` + `actual_pool_by_bucket` breakdown** | Operator 2026-06-04 |
| OQ-4 pre-merge gate shape | **QA + measurement + isolated step-smoke + operator-witnessed live run** | Operator 2026-06-04 |
| OQ-5 future-consumer default | **Document aplus-only default, watch opt-in** (no V1 code) | Recommend (propagated) |
| OQ-6 variable rename | **Rename `aplus_tickers` -> `detect_pool_tickers`** | Operator 2026-06-04 |

OQ-1 (cap policy, gated on the measured numbers) and OQ-4 (gate shape) remain
operator-binding at writing-plans -- the acceptance criterion (Sec 4.3) is judged
against the real measurement; the live-run gate (Sec 7.2) is the operator's confirm.

---

## 12. Cumulative discipline compliance

- **#27 (silent-skip-without-audit).** The widened-pool empty-pool audit + the
  dormant cap path both emit accurate `warnings_json`; NO silent cap (Sec 3.2 / 4.4).
  Each audit field's UNIT is stated (Expansion #8).
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
- **`feedback_verify_regression_test_arithmetic`.** Every test count computed under
  BOTH paths (Sec 7.1).
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
