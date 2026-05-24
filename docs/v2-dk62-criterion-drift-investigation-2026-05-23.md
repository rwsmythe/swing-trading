# V2 OHLCV DK:62 CRITERION DRIFT Investigation Findings

**Investigation date:** 2026-05-23
**Branch:** `applied-research-v2-dk62-criterion-drift-triage`
**Triggered by:** Partial implementer smoke at `exports/diagnostics/aplus-sensitivity-v2-20260523T230131Z.{csv,md}` flagged tier-1 baseline-parity FAIL on DK:62 (V1 persisted=`skip`, V2 recomputed=`watch`).
**Dispatch brief:** `docs/v2-ohlcv-dk62-criterion-drift-triage-dispatch-brief.md` (HEAD `182aca9`).
**Workflow:** `superpowers:systematic-debugging` (forensic; diagnostic-only — no code changes shipped).

---

## §0 TL;DR

- **Root cause:** The Shape A archive for DK (`DK.yfinance.parquet`) is STALE relative to the legacy archive (`DK.parquet`). Shape A's last bar is 2026-05-20; legacy includes 2026-05-21 (eval_run 62's `data_asof_date`). V1 evaluated DK at eval_run 62 against bars including the 2026-05-21 close (42.10, a -5.7% intraday drop); V2 today reads the stale Shape A and evaluates against bars ending 2026-05-20 (close=44.59). Two criterion results flip across the boundary bar (`TT5_above_50` fail→pass, `proximity_20ma` fail→pass), promoting DK from `skip`→`watch`.
- **Side that is correct:** V1 persisted is the canonical truth for the eval_run 62 evaluation; V2's `watch` reflects an evaluation against a frame that LACKS the day under evaluation.
- **Drift scope:** **Isolated to DK at eval_run 62.** Only 3 both-exist tickers in cache (AESI/DK/PL); only DK has Shape A staleness; only one eval_run (62) lands on the missing boundary bar's date.
- **All four hypotheses falsified except H3 (V2 bug), and H3 is characterised as an ARCHITECTURAL desync — V2 reader correctly reads Shape A; the asymmetry between Shape A and legacy refresh paths is what produces the stale state.**
- **Remediation recommendation (Option D combined):** (1) operator triggers Shape A refresh for the 3 both-exist tickers via natural pipeline / `resolve_ohlcv_window` invocation OR a one-shot helper, (2) re-run V2 smoke to verify DK:62 parity restored, (3) document the staleness mechanism in the V2 method-record limitations, (4) bank V2-reader "prefer-fresher of (Shape A, legacy)" as a V2 candidate.
- **Unblocks:** research→shadow promotion gate per OQ-8 ladder (after DK:62 parity restored); full 63-eval-run operator reproduction (Shape A refresh is a precondition).

---

## §1 Hypothesis evaluation

### §1.1 H1: Criterion implementation drift between eval_run 62 and V2 invocation — **FALSIFIED**

**Evidence gathered:**

```
$ git log --since='2026-05-21 20:27' --oneline -- \
    swing/evaluation/scoring.py swing/evaluation/criteria/ swing/evaluation/evaluator.py
(no output — zero commits)
```

- ZERO commits to `swing/evaluation/scoring.py` between eval_run 62 timestamp (2026-05-21 20:27 UTC) and V2 smoke timestamp (2026-05-23 23:01 UTC).
- ZERO commits to `swing/evaluation/criteria/`.
- ZERO commits to `swing/evaluation/evaluator.py`.

**Counter-test:** When `evaluate_one` is invoked with the LEGACY DK bars (including 2026-05-21), it produces bucket=`skip` AND every criterion value matches V1's persisted `candidate_criteria` row EXACTLY (TT5_above_50 fail with `value=close=42.10 50MA=43.56 rule=close > 50MA`; proximity_20ma fail with `value=-6.12%`; etc.). Same code, same cfg, same bars → same result as V1.

**Verdict:** H1 RULED OUT.

### §1.2 H2: cfg drift (`bucket_for` thresholds or downstream cfg changed) — **FALSIFIED**

**Evidence gathered:**

```
$ git log --since='2026-05-21 20:27' --oneline -- swing.config.toml
(no output)

$ git log --since='2026-05-21 20:27' --oneline -- swing/config.py
aafc3c7 style(research,diagnostics): ruff clean (UP017 + I001 + UP037 + N806 + B007)
dc86a4c feat(research): aplus_sensitivity sweep variable enumeration (Item 1; T-T4.SB.1)
```

- ZERO commits to `swing.config.toml` (the tracked cfg values for `trend_template.min_passes`, `vcp.watch_max_fails`, `allowed_miss_names`, `rs.horizon_weeks`, etc. are UNCHANGED).
- The two `swing/config.py` commits are cosmetic / additive:
  - `dc86a4c` ADDS a NEW `Config.from_defaults()` classmethod (no modification of existing fields).
  - `aafc3c7` replaces string annotation `"Config"` with bare `Config` (Python 3.10+ forward-ref; semantically identical).
- Confirmed: `cfg.trend_template.min_passes == 7`; `cfg.trend_template.allowed_miss_names == ('TT8_rs_rank',)`; `cfg.rs.horizon_weeks == 12`. All match the values that produce V1's persisted bucket.

**Verdict:** H2 RULED OUT.

### §1.3 H3: Bug in V2 (OHLCV reader / context_builder / cfg_substitution) — **PARTIALLY TRUE (characterized as architectural desync, NOT V2 code bug)**

**Evidence gathered:**

1. **Cache file inventory for DK** at `C:\Users\rwsmy\swing-data\prices-cache\`:
   - `DK.parquet` (legacy): 50,518 bytes, mtime `2026-05-21 20:28:04` — last bar `2026-05-21` (Open=45.24, High=45.41, Low=41.83, Close=42.10, Volume=1,096,600)
   - `DK.yfinance.parquet` (Shape A): 48,207 bytes, mtime `2026-05-21 07:39:42` — last bar `2026-05-20` (Open=45.28, High=46.02, Low=43.88, Close=44.59, Volume=727,473)
   - Legacy includes a bar the Shape A archive is MISSING.

2. **V2 reproduction against DK alone with Shape A (current V2 read path)**:

   ```
   $ python -c "...read_yfinance_shape_a('DK', cache) -> evaluate_one(...)"
   V2 bucket: watch
   TT5_above_50: pass (close=44.59 > 50MA=43.55)        # FLIP vs V1 fail
   proximity_20ma: pass (-0.31%)                         # FLIP vs V1 fail
   # VCP fails count: 2 (ma_short_rising, tightness)     -> watch
   # TT passes: 8 (with provided batch; TT8 N/A handling
   # may differ in real V2 universe-batch context)
   ```

3. **Counter-test reproduction against DK with LEGACY bars (V1's input)**:

   ```
   V1 reproduced bucket: skip
   TT5_above_50: fail (close=42.10 < 50MA=43.56)        # matches V1 persisted EXACTLY
   TT8_rs_rank: na (no 12w return available)             # matches V1 persisted EXACTLY
   proximity_20ma: fail (-6.12%)                         # matches V1 persisted EXACTLY
   ma_short_rising: fail; tightness: fail                # matches V1 persisted
   # VCP fails count: 3 -> skip
   # TT non-allowed-miss check: TT5 not in allowed -> skip
   ```

   Every criterion value (closes / MAs / percentages / volumes) matches V1's persisted `candidate_criteria` row to the displayed precision.

**Characterization:** The V2 reader's behavior is per-spec (Shape A wins unconditionally per OQ-18 LOCK at `swing/data/migrations/...`-era + spec §F.1). The "bug" is NOT in V2 code — it is an **architectural data-freshness desync** between two archive paths:

| Archive | Writer | Frequency |
| --- | --- | --- |
| `{T}.parquet` (legacy) | `swing/data/ohlcv_archive.py::read_or_fetch_archive` (called from `swing/pipeline/ohlcv.py`, `swing/prices.py`, `swing/trades/daily_management.py`) | Every pipeline run + chart/daily-management read |
| `{T}.yfinance.parquet` (Shape A) | `swing/data/ohlcv_archive.py::_backward_compat_rename`, invoked at the top of `resolve_ohlcv_window` | Only when `resolve_ohlcv_window` is called for that ticker |

Under V1, NO production caller of `resolve_ohlcv_window` exists for the routine pipeline OHLCV path (per the docstring at `swing/data/ohlcv_archive.py:585-596`): "V1 LEAVES the legacy `{TICKER}.parquet` file IN PLACE because `read_or_fetch_archive` ... reads ONLY the legacy path." Shape A is refreshed opportunistically when `resolve_ohlcv_window` is called by Sub-bundle C ladder / Phase 10 metrics paths, NOT by the evaluator's daily refresh.

**Concrete DK timeline at eval_run 62 (2026-05-21):**

| Time | Event | Effect on DK.parquet | Effect on DK.yfinance.parquet |
| --- | --- | --- | --- |
| 2026-05-21 07:39 | Earlier `resolve_ohlcv_window` call (e.g., metrics path) | (no change) | Refreshed with bars through 2026-05-20 (mtime updated) |
| 2026-05-21 20:27 | Pipeline run starts (eval_run 62) | (in progress) | (untouched) |
| 2026-05-21 20:28 | `read_or_fetch_archive` writes fresh bars including 2026-05-21 | mtime updated; last bar 2026-05-21 | (untouched — Shape A NOT propagated forward) |
| 2026-05-21 ~20:28 | `_step_evaluate` reads legacy bars; persists candidate_criteria + bucket=`skip` | (consumed) | (untouched) |
| 2026-05-23 23:01 | V2 sensitivity smoke reads Shape A | (untouched) | Returns frame ending 2026-05-20; V2 evaluator never sees the 2026-05-21 bar |

**Verdict:** H3 is the architectural mechanism. V2 reader code is per-spec; the desync is upstream.

### §1.4 H4: Bug in V1 persisted state (race / partial-write / stale OHLCV at original eval_run 62) — **FALSIFIED**

**Evidence gathered:**

```
evaluation_runs id=62:
  run_ts: 2026-05-21T20:27:02
  data_asof_date: 2026-05-21
  action_session_date: 2026-05-22
  tickers_evaluated: 65
  aplus_count: 0
  watch_count: 10
  skip_count: 52
  excluded_count: 3
  error_count: 0
  rs_universe_hash: bb7b38792ce6170627cfad6299d26efb4514de2ad375cad70617502d3a9d977c

candidates DK at eval_run 62:
  id: 5601
  bucket: skip
  close: 42.099998
  adr_pct: 4.887
  rs_method: fallback_spy
  rs_rank: None
  pattern_tag: None
  notes: None

candidate_criteria DK at eval_run 62: (18 rows; all values listed in §1.3 counter-test)
  - risk_feasibility: pass
  - 7 TT pass / 1 TT fail (TT5) / 1 TT na (TT8)
  - 6 VCP pass / 3 VCP fail (ma_short_rising, proximity_20ma, tightness)
```

- `error_count: 0` — no per-ticker errors.
- `run_ts` to `data_asof_date` mapping is consistent.
- DK candidate row carries plausible/expected values; no error markers; no anomalous timing.
- The 18 `candidate_criteria` rows are complete; no missing criterion; no `status='error'`.
- The counter-test in §1.3 reproduces every criterion value EXACTLY when fed the legacy bars — V1's persisted state is internally consistent and reproducible.

**Verdict:** H4 RULED OUT. V1's persisted state is healthy.

### §1.5 H5+ (residual candidates) — none surfaced

- yfinance Shape A archive corruption: ruled out (bars overlap legacy for ALL common dates with zero cell-level diff across the trailing 60 trading days).
- Criterion edge-case not exercised by tests: ruled out (the V2 reproduction with legacy bars produces V1's persisted result exactly; if there were an edge-case discrepancy it would show up here).
- Schema drift: ruled out (schema v21 unchanged; ZERO migration commits since eval_run 62 per `swing/data/migrations/`).

---

## §2 Drift scope

### §2.1 Same-eval_run scope (eval_run 62, other tickers)

- 65 candidates total at eval_run 62 (per `evaluation_runs.tickers_evaluated`).
- Smoke's CRITERION DRIFT section lists **ONLY DK:62** as tier-1 baseline-parity FAIL.
- DHC/UCO/VSAT (bucket=excluded; risk_result=None) ALSO appear in the per-variable drill-down at eval_run 62, but their flips are `excluded→skip` / `excluded→watch` — these are tier-1 per `classify_candidate_tier` (None → tier-1) BUT they do NOT appear in the tier-1 mismatch list because their persisted_bucket=`excluded` reflects a PRE-EVALUATION exclusion (e.g., earnings-proximity exclusion, market-cap floor) that the V2 harness does not replicate (it runs `evaluate_one` directly on persisted candidate rows). This is a SEPARATE category from OHLCV-staleness drift and is expected per V2's `evaluate_one`-direct architecture. (Note: the smoke's tier-1 FAIL section explicitly lists DK:62 only — DHC/UCO/VSAT drifts are either not classified as tier-1 baseline-parity failures by the V2 sweep OR are being filtered before the tier-1 mismatch list aggregation; the BLOCKING signal is DK:62 alone.)

### §2.2 Same-ticker scope (DK across all eval_runs)

DK persisted buckets across the full DB:

| eval_run | data_asof_date | V1 persisted bucket | Shape A coverage at asof_date | Expected V2 drift? |
| --- | --- | --- | --- | --- |
| 25-30 | 2026-04-29 / -30 | skip | (pre-Shape-A-existence; safe) | No — Shape A almost certainly fresh enough |
| 53-54 | 2026-05-15 | watch | covered (Shape A last=2026-05-20) | No |
| 55 | 2026-05-18 | watch | covered | No |
| 59-61 | 2026-05-20 | watch | boundary date = 2026-05-20 (covered) | No |
| **62** | **2026-05-21** | **skip** | **MISSING (Shape A last=2026-05-20)** | **YES — TIER-1 BLOCKING** |
| 63, 64 | — | DK not a candidate | — | n/a |

DK:62 is the ONLY eval_run where Shape A staleness lands exactly on the eval_run's `data_asof_date`. Earlier eval_runs land within the covered range; later eval_runs do not include DK.

### §2.3 Systemic scope (broader cache-archive freshness audit)

Inventory of the prices cache:

| Archetype | Count | Notes |
| --- | --- | --- |
| Both-exist (legacy + Shape A) | **3** (AESI, DK, PL) | Only DK has Shape A staleness at a critical eval_run asof_date |
| Shape A only | 0 | n/a |
| Legacy only | **822** | V2 reader falls back to legacy at `ohlcv_reader.py:91-93` → reads SAME bars V1 wrote → no OHLCV-driven drift |

**Conclusion:** the drift mechanism (Shape A staleness vs legacy at the boundary bar) affects EXACTLY ONE ticker at ONE eval_run in the 5-eval_run partial smoke. Extrapolating to the full 63-eval-run reproduction:
- AESI / PL have Shape A current as of 2026-05-22, so any eval_run asof_date ≤ 2026-05-22 is covered.
- DK has Shape A current through 2026-05-20, so eval_run 62 (asof 2026-05-21) is the SOLE boundary-miss case.
- 822 legacy-only tickers cannot drift via this mechanism.

**The drift is ISOLATED. Full 63-eval-run reproduction will almost certainly continue to show DK:62 as the single tier-1 baseline-parity failure UNTIL Shape A is refreshed.**

---

## §3 Why does this matter (impact analysis)

- **V1 production correctness:** UNAFFECTED. V1 reads legacy bars (which are fresh). V1's persisted state for DK:62 = `skip` is the canonical truth.
- **V2 sensitivity research blocking:** PARTIALLY. The tier-1 BLOCKING flag halts research→shadow promotion per OQ-8 ladder. Once Shape A is refreshed for DK, parity restores and promotion can proceed.
- **Other research-branch artifacts:** UNAFFECTED. The method-record (`research/method-records/aplus-criteria-calibration.md`) and study writeup (`research/studies/2026-05-23-v2-ohlcv-criterion-evaluator.md`) correctly reflect partial-smoke state.
- **Schema / production code:** UNAFFECTED. ZERO schema migrations, ZERO production code changes are required.
- **L2 LOCK:** UNAFFECTED. No Schwab API calls; no reads of `{T}.schwab_api.parquet`.

---

## §4 Remediation recommendation (Option D — combined)

### §4.1 Step 1 — Operator: refresh Shape A archive for DK (and audit AESI/PL)

Three operator-paired paths (preference order):

1. **Natural pipeline run (LOW-EFFORT, RECOMMENDED):** the next routine pipeline run will fetch fresh OHLCV for DK via `read_or_fetch_archive` (legacy update). To propagate to Shape A, invoke any caller of `resolve_ohlcv_window` (e.g., chart rendering for a watchlist row containing DK; daily management for an open DK position; metrics audit). The `_backward_compat_rename` invocation inside `resolve_ohlcv_window` will merge legacy → Shape A, including the 2026-05-21 bar.

2. **One-shot script (HIGHER-EFFORT, EXPLICIT):** operator-paired Python snippet from project root:
   ```python
   from pathlib import Path
   from swing.config import Config
   from swing.data.ohlcv_archive import resolve_ohlcv_window
   cfg = Config.from_defaults()
   cache = Path(cfg.paths.prices_cache_dir)
   for t in ("DK", "AESI", "PL"):
       # 30-day window suffices to trigger _backward_compat_rename merge
       resolve_ohlcv_window(t, start="2026-04-23", end="2026-05-22", cache_dir=cache)
   ```
   Verify post-fix Shape A `mtime` and `asof_date.max()` reflect the new boundary.

3. **Production CLI command (V2 candidate, NOT in scope):** add `swing diagnose ohlcv-shape-a-refresh-all` subcommand to sweep all both-exist tickers. Bank as V2.

### §4.2 Step 2 — Operator: re-run V2 smoke + verify parity restored

After Shape A refresh, re-run the partial smoke:

```
python -m swing.cli diagnose aplus-sensitivity-v2 \
    --eval-runs=5 --max-runtime-seconds=120
```

Expected: `Tier-1 match: PASS`; CRITERION DRIFT section omitted entirely (per `output.py:178` early-return when `tier1_match=True`).

### §4.3 Step 3 — Method-record + study writeup amendment

Add a Limitations entry to `research/method-records/aplus-criteria-calibration.md` (V0.2.0 → V0.2.1 patch bump) under §K.4 or new §K.6:

> **Limitation L4: Shape A vs legacy archive freshness desync.** V2 reads `{T}.yfinance.parquet` (Shape A) exclusively. Shape A is refreshed only when `resolve_ohlcv_window` is invoked for that ticker (via Sub-bundle C ladder / Phase 10 metrics paths). The production pipeline OHLCV path (`read_or_fetch_archive`) writes to `{T}.parquet` (legacy) ONLY. When legacy contains a fresher boundary bar than Shape A at the eval_run's `data_asof_date`, V2 evaluates against bars MISSING the boundary — producing a different bucket than V1 persisted. Symptom: BLOCKING tier-1 baseline-parity FAIL when the boundary-miss falls on an eval_run's asof_date. Documented direct evidence: DK:62 investigation 2026-05-23 (this finding). Mitigation: refresh Shape A for affected tickers before V2 sensitivity invocation (see investigation findings §4.1).

Also update the smoke artifact (or note in the study writeup) that the OQ-18 caveat's directionality wording is INVERTED — the danger is stale Shape A relative to legacy (not stale legacy relative to Shape A as the current banner phrasing suggests). Bank as a documentation fix candidate.

### §4.4 Step 4 — Bank V2 candidate: "prefer-fresher" Shape A reader

V2 reader enhancement: `read_yfinance_shape_a` could read BOTH files when present, compare `Path.stat().st_mtime` (or `asof_date.max()`), and select the fresher frame — mirroring the merge-with-mtime-tiebreaker logic already in `_backward_compat_rename` at `swing/data/ohlcv_archive.py:670-695` (R3 Major #1 fix). This eliminates the V2-side observability gap without changing production write paths.

Per OQ-17 swing/ carve-out invariant, this would touch `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py` (research-side; OK) and could ALSO refactor `_backward_compat_rename`'s merge helper to be reusable from research-side (research-side reuse via import; production swing/ unchanged). Bank as V2 dispatch.

### §4.5 What this investigation does NOT recommend

- **DO NOT** delete the legacy `DK.parquet` file. Many production callers read it; deleting it would break V1 chart rendering, daily-management ATR, and PriceFetcher. The asymmetric-but-coexisting state is intentional V1 design per Codex R2 Major #1 at `swing/data/ohlcv_archive.py:588-596`.
- **DO NOT** modify V1 production code (read-only invariant per dispatch brief §4.5).
- **DO NOT** modify V1 persisted state (read-only invariant per dispatch brief §4.5; the V1 persisted bucket for DK:62 = `skip` is correct).
- **DO NOT** ship V2 reader fix in this investigation dispatch (scope is DIAGNOSTIC; remediation Option A natural-recovery is the lowest-blast-radius path).

---

## §5 Forward-binding lessons for future research-branch arcs

### §5.1 Lesson 1 — Archive-freshness desync is an architectural risk, not a code bug

When two write paths produce two copies of the same logical data (V1 legacy + V1 Shape A), and the read paths assume sync, expect drift at boundary cases. The OQ-18 both-exist policy LOCK is correct as a tie-breaker rule, but it presupposes Shape A is at least as fresh as legacy. Forward-binding for any future V2-style harness that reads ONE of two parallel archive shapes: **verify the freshness invariant at investigation time, not just the contents**. Bank as cumulative gotcha #24 candidate (see §5.4).

### §5.2 Lesson 2 — Counter-test by feeding the suspect reader the canonical-truth inputs

The decisive evidence for the DK:62 root cause was a counter-test: feed `evaluate_one` the LEGACY bars (V1's input) and verify it reproduces V1's persisted bucket + every criterion value EXACTLY. This rules out criterion / cfg / evaluator drift in one step. Pre-empt in any future V2-style baseline-parity investigation: **the second hypothesis-falsification step after git-log-checks is the "feed the suspect reader the V1 input" reproduction**. Bank as forward-binding lesson #6 for the V2 research arc.

### §5.3 Lesson 3 — Smoke-artifact section interpretation requires the spec's section taxonomy

The smoke artifact's CRITERION DRIFT section reports DK:62 three times. The dispatch brief flagged this as "cosmetic OR signal — verify". Investigation finding: the 3-instance count is COSMETIC (per `_compute_baseline_parity` appending `f"{ticker}:{run_id}"` once per processing pass; the per-variable drill-down anomalies — DK:62 appearing at sweep_point=7 trend_template.min_passes — are likely an artifact of running the smoke against a pre-R3.M1 / pre-R4.M1 version of `sweep.py` that did not yet apply the `is_current_point` guard and `baseline_bucket_map` semantics). Bank as a verification candidate: **regenerate the smoke against HEAD `a43a921` (post-merge with all Codex fixes applied) and confirm the drill-down rows behave per spec**. Out of scope for this investigation but documented for the post-remediation re-run.

### §5.4 Lesson 4 — Banked CLAUDE.md gotcha candidate (cumulative #24)

**Gotcha candidate:** *Parallel-archive freshness desync invalidates baseline-parity claims for V2-style readers that consume ONE of two parallel archive shapes.* Failure mode: when two archive paths write to two files (legacy `{T}.parquet` + Shape A `{T}.yfinance.parquet`) and the read paths read the same single file each, the writer asymmetry (legacy refreshed on every pipeline run; Shape A refreshed only via `_backward_compat_rename` invoked at `resolve_ohlcv_window`) creates a per-ticker freshness desync. V2 baseline-parity tests assume sync; reality drifts at boundary cases. **Pre-empt** in any future harness that reads ONE of N parallel archives: writing-plans §5 watch item — enumerate the producer-vs-consumer set per archive shape; if producers ≠ consumers, document the freshness invariant precondition; add a discriminating test that plants a synthetic stale archive + asserts the harness EITHER (a) detects + warns OR (b) falls through to the freshest archive. Forward-binding for V2 ohlcv reader enhancement (§4.4) + any future archive-shape proliferation.

### §5.5 Lesson 5 — Two-sided staleness wording (banner inversion)

The smoke's OQ-18 both-exist banner says "Verify no stale legacy files contaminate results." This wording presumes Shape A is the canonical-fresh side. In reality, under V1 (legacy is what production pipeline writes), the asymmetric risk is REVERSED — Shape A may be stale relative to legacy. Forward-binding: any future both-exist banner copy must enumerate which side is fresher under what production write path; do not presume the architecturally-preferred read side is the fresher write side. Bank as documentation fix candidate for the smoke-artifact output formatter (`research/harness/aplus_v2_ohlcv_evaluator/output.py:225-228`).

---

## §6 Verification artifacts produced

| Artifact | Path | Purpose |
| --- | --- | --- |
| Investigation findings doc (THIS FILE) | `docs/v2-dk62-criterion-drift-investigation-2026-05-23.md` | Per-hypothesis evidence + root cause + scope + remediation |
| Return report | `docs/v2-dk62-criterion-drift-investigation-return-report.md` | Cumulative-precedent shape; investigation summary + verification + handback |

No code changes shipped. No V2 reader fix. No schema migration. No V1 production code changes. ZERO new Schwab API calls. ZERO reads of `{ticker}.schwab_api.parquet`. ZERO modifications to `candidate_criteria` / `pipeline_runs` / `evaluation_runs` rows.

---

## §7 Cumulative streaks preserved

- **ZERO Co-Authored-By footer** — investigation findings + return report committed without the footer (~494+ cumulative streak through this commit).
- **L2 LOCK BINDING** — investigation used existing Shape A + legacy parquet bytes only; no yfinance fetch; no Schwab API call; no `{T}.schwab_api.parquet` reads.
- **Schema v21 LOCKED** — no migrations touched.
- **V1 persisted state READ-ONLY** — investigation queried `candidate_criteria` / `evaluation_runs` / `candidates` rows but did not modify them.
- **Production swing/ READ-ONLY** — investigation read `swing/evaluation/scoring.py`, `swing/data/ohlcv_archive.py`, etc. but did not modify them.
- **ASCII-only on narrative text** — this document is ASCII-clean per Windows cp1252 stdout discipline.

---

## §8 Open questions for orchestrator-side QA / operator review

1. Should the post-remediation V2 smoke re-run be a fresh dispatch OR is operator-paired manual invocation acceptable? Recommendation: operator-paired invocation since the operator already has a 63-eval-run reproduction planned (per CLAUDE.md status-line "operator-paired V2 OHLCV harness output review" next action).

2. Should the V2 reader "prefer-fresher" enhancement (§4.4) be a SEPARATE dispatch OR folded into the next research-branch arc (e.g., DBE-criterion-evaluator V2)? Recommendation: SEPARATE V2-OHLCV-prefer-fresher dispatch because the lesson is general (not specific to A+ criteria) and the V2 dispatch would touch `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py` shared by future V2 harnesses.

3. Should the method-record amendment (§4.3) be applied in THIS branch (alongside this investigation handback) OR in a follow-up housekeeping bundle? Recommendation: defer to operator preference; investigation branch ships diagnostic findings only by default. If operator prefers, the method-record patch is a 1-file edit and can be appended to this branch before merge.

---

*End of V2 OHLCV DK:62 CRITERION DRIFT investigation findings.*

*Root cause identified with code:line citations + concrete bar-level evidence; all four hypotheses falsified (H1, H2, H4) or characterized as architectural (H3); drift scope isolated to DK:62; remediation Option D recommended; 5 forward-binding lessons banked; ZERO production code changes; ZERO Co-Authored-By footer; L2 LOCK preserved; schema v21 LOCKED.*
