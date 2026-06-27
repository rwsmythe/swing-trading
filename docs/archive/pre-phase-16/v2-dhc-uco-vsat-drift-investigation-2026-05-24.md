# V2 OHLCV DHC / UCO / VSAT x eval_runs 60-64 CRITERION DRIFT Investigation Findings

**Investigation date:** 2026-05-24
**Branch:** `applied-research-v2-dhc-uco-vsat-drift-triage`
**Triggered by:** Post-D.1-refresh + post-Codex-fix smoke at `exports/diagnostics/aplus-sensitivity-v2-20260524T162641Z.{csv,md}` flagged 15 tier-1 baseline-parity FAILs on DHC/UCO/VSAT x eval_runs 60-64 (V1 persisted=`excluded`, V2 recomputed=`skip` or `watch`).
**Dispatch brief:** `docs/v2-dhc-uco-vsat-drift-triage-dispatch-brief.md` (main HEAD `970ce80`).
**Workflow:** `superpowers:systematic-debugging` (forensic; diagnostic-only -- no production code changes shipped; no V2 code changes shipped).

---

## Section 0 -- TL;DR

- **Root cause:** V2 harness false-positive. V1 production pipeline at `swing/pipeline/runner.py:1105-1141` SHORT-CIRCUITS criterion evaluation for two excluded-ticker classes -- open positions (`held_set`) + ETF/fund blocklist (`cfg.etf_exclusion.manual_block`) -- and appends `Candidate(bucket='excluded', criteria=(), notes='open position'|'ETF/fund blocklist', ...)` rows directly. V2's `_compute_baseline_parity` at `research/harness/aplus_v2_ohlcv_evaluator/sweep.py:540-605` does NOT replicate the short-circuit and naively invokes `evaluate_one(ctx)` on these candidates. `swing/evaluation/scoring.py:bucket_for` cannot return `'excluded'` (returns only `'aplus'`, `'watch'`, `'skip'`), so V2's recomputed bucket NEVER matches V1's persisted `'excluded'` for these candidates.
- **Why surfaced only now:** Codex R1.C1 fix (commit `624e3e1`, 2026-05-23) changed `classify_candidate_tier(persisted_risk_result=None)` from tier-2 to tier-1. Pre-fix, these 15 entries were counted in `tier2_mismatch_count` (informational; no BLOCKING flag). Post-fix, they land in `tier1_mismatch_keys` and trigger the BLOCKING `CRITERION DRIFT DETECTED` banner.
- **Which side is correct:** Both sides are internally consistent. V1's `bucket='excluded'` is correct -- these tickers are intentionally pre-empted from criterion evaluation (open positions don't need a watch/aplus signal; UCO is on the ETF blocklist). V2's recomputed `skip`/`watch` is also "correct" in the narrow sense that it answers the question "if this ticker were eligible, what bucket would the evaluator assign?" -- but the question itself is non-sensical for excluded candidates.
- **Drift-class scope:** SYSTEMIC across the OPEN-POSITION + ETF-BLOCKLIST classes, NOT just DHC/UCO/VSAT x 60-64. Any eval_run that produces excluded rows (open positions + blocklist) will surface as tier-1 baseline-parity FAILs in the same per-Codex-fix sweep. The 5-eval_run window happens to enumerate 15 entries (3 tickers x 5 runs) for the current open-position + blocklist set; broader 63-eval-run reproduction will scale linearly with `len(held_set ∪ etf_exclusion.manual_block)`.
- **All four pre-narrowed hypotheses (H1, H2, H3, H4) FALSIFIED.** A fifth hypothesis (H5: V2 harness-vs-V1-pre-evaluation-exclusion-pathway gap) is identified as the canonical root cause.
- **Remediation recommendation (Option A LOCKED):** filter out persisted `bucket='excluded'` candidates from the V2 baseline-parity comparison in `_compute_baseline_parity` -- single-line change in research-branch only. ZERO production swing/ writes; ZERO V1 code changes; ZERO schema migrations; preserves the L2 LOCK + ZERO Schwab API calls. Discriminating test plants synthetic open-position + ETF-blocklist excluded candidates + asserts they are NOT counted in tier-1 mismatch list.
- **Unblocks:** full 63-eval-run operator reproduction (drift-class understood + non-blocking once Option A lands); research->shadow promotion gate per OQ-8 ladder (after V2 filter ships).
- **NEW cumulative gotcha #25 banked:** V2 baseline-parity comparison must filter persisted `'excluded'` candidates because production pipeline pre-empts criterion evaluation for open positions + ETF blocklist; baseline-parity can compare apples-to-apples only on candidates V1 actually evaluated.

---

## Section 1 -- Hypothesis evaluation

### Section 1.1 -- H1: V2 legacy-fallback reader differs from V1's `read_or_fetch_archive` -- **FALSIFIED**

**Evidence gathered:**

1. Cache file inventory for the 3 affected tickers:

| Ticker | `{T}.parquet` (legacy) | `{T}.yfinance.parquet` (Shape A) | `{T}.schwab_api.parquet` |
| --- | --- | --- | --- |
| DHC | EXISTS (38188 bytes) | ABSENT | EXISTS (36797 bytes; V2 must NOT open per L2 LOCK) |
| UCO | EXISTS (52749 bytes) | ABSENT | ABSENT |
| VSAT | EXISTS (54175 bytes) | ABSENT | EXISTS (47389 bytes; V2 must NOT open per L2 LOCK) |

2. V2's reader at `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py:91-93` falls through to legacy when Shape A is absent. Same file V1's `read_or_fetch_archive` reads. Byte-identical.

3. The reproducer at `tmp/dhc-uco-vsat-investigation/reproducer.py` Section 4 reads `>= 1258` bars per ticker through V2's reader -- well above the 200-bar coverage threshold -- and runs `evaluate_one` end-to-end producing a `Candidate`. No OHLCV coverage issue.

**Counter-test:** Reproducer Section 4 ran V2's `read_yfinance_shape_a` + `evaluate_one(ctx)` for DHC:60, UCO:62, VSAT:64. ALL THREE produced non-`excluded` buckets (`skip`/`watch`/`skip` respectively) using the same legacy `.parquet` bytes V1 wrote. If H1 (reader-byte-drift) were true, we would expect either an OHLCV coverage error OR a criterion-evaluation crash; neither occurred.

**Verdict:** H1 RULED OUT. V2 reads the SAME byte-identical legacy parquet bars V1 reads.

### Section 1.2 -- H2: V2 RS universe drift between historical asof_date and V2 invocation (OQ-14 surrogate) -- **FALSIFIED**

**Evidence gathered:**

1. V1 persisted state for all 15 affected candidate rows shows `rs_method='unavailable'` and `rs_rank=None`. Per `swing/pipeline/runner.py:1135-1141`, these are HARD-CODED for excluded candidates -- never computed.

2. The 15 candidate rows ALSO have ZERO `candidate_criteria` rows persisted (confirmed via SQL `SELECT COUNT(*) FROM candidate_criteria WHERE candidate_id = ?` for each; all 15 return 0). V1 NEVER ran criterion evaluation for these tickers -- there's no RS rank to drift TO.

3. OQ-14 LOCK (V2 uses current-universe snapshot for ALL historical eval_runs) is irrelevant because V1 has no historical RS rank persisted for these candidates.

**Verdict:** H2 RULED OUT. The proposed drift mechanism (V1 historical RS rank vs V2 current-universe RS rank) does not apply -- V1 has no RS rank for these candidates.

### Section 1.3 -- H3: V2 OHLCV slicing edge case at asof_date boundary -- **FALSIFIED**

**Evidence gathered:**

1. Same legacy `.parquet` bars are read by both V1 and V2 (H1 evidence).
2. V2's slicing predicate at `sweep.py:786` (`sliced = full_df.loc[full_df.index.date <= asof_date]`) is INCLUSIVE backward-looking, matching the cumulative gotcha discipline ("backward-looking anchor; use `<=` inclusive"). This matches V1's `read_or_fetch_archive` end-date semantic. No off-by-one possible at the boundary.
3. V1 NEVER consumed the OHLCV bars for these candidates -- the short-circuit at `swing/pipeline/runner.py:1112-1115` skips the `CandidateContext` construction entirely. There is no V1 slicing semantic to compare against.

**Verdict:** H3 RULED OUT. V2's slicing is per-spec; V1 never sliced.

### Section 1.4 -- H4: V2 BatchContext reconstruction differs at historical asof_date -- **FALSIFIED**

**Evidence gathered:**

1. The reproducer at Section 4 invoked `build_eval_run_cohort` for run_ids 60/62/64. It successfully built `EvalRunCohort` objects with `current_equity`, `current_equity_via_surrogate`, and `batch.returns_12w_by_ticker` for the candidate set. No raise.
2. The BatchContext fields are inputs to `evaluate_one`. The reproducer DID invoke `evaluate_one` with the cohort's BatchContext + got non-`excluded` buckets. If BatchContext were the issue, we'd expect an evaluation error; none occurred.
3. V1 NEVER consumed the BatchContext for these candidates (short-circuit at line 1112-1115). There is no V1 BatchContext to compare against.

**Verdict:** H4 RULED OUT. V2 builds + consumes BatchContext correctly; V1 never built one for these candidates.

### Section 1.5 -- H5 (NEW): V2 baseline-parity does not filter V1's pre-evaluation excluded candidates -- **CONFIRMED ROOT CAUSE**

**Evidence gathered:**

1. **V1 production code (`swing/pipeline/runner.py:1105-1141`) short-circuits criterion evaluation for two excluded-ticker classes:**

   ```python
   held_set = set(held_tickers)
   excluded = set(cfg.etf_exclusion.manual_block) | held_set
   excluded_tickers: list[str] = []
   contexts: list[CandidateContext] = []
   for t in tickers:
       if t in excluded:
           excluded_tickers.append(t)
           continue                # <-- SHORT-CIRCUIT: no CandidateContext built
       ...

   candidates = evaluate_batch(contexts)  # excluded tickers NOT in contexts
   for t in excluded_tickers:
       ...
       notes = "open position" if t in held_set else "ETF/fund blocklist"
       candidates.append(Candidate(
           ticker=t, bucket="excluded",
           ...
           rs_method="unavailable",  # hard-coded; no RS computed
           ...
           criteria=(),               # empty tuple; no criterion evaluation
       ))
   ```

2. **V1 production code (`swing/evaluation/scoring.py:bucket_for:13-39`) cannot return `'excluded'`:**

   ```python
   def bucket_for(trend_template_results, vcp_results, risk_results, config) -> str:
       if any(r.result != "pass" for r in risk_results):
           return "skip"
       tt_passes = sum(...)
       if tt_passes < config.trend_template.min_passes:
           return "skip"
       if not all(n in allowed for n in tt_fails):
           return "skip"
       vcp_fails = sum(...)
       if vcp_fails == 0:
           return "aplus"
       if vcp_fails <= 2:
           return "watch"
       return "skip"
   ```

   `'excluded'` is NOT in the return-value enumeration. Direct enumeration: `{aplus, watch, skip}`.

3. **V2's `_compute_baseline_parity` invokes `evaluate_one(ctx)` on every persisted candidate row WITHOUT filtering on `persisted_bucket='excluded'`:**

   ```python
   # research/harness/aplus_v2_ohlcv_evaluator/sweep.py:541-605
   for run_id, _asof_date in eval_runs:
       cohort = cohort_getter(run_id, baseline_horizon)
       run_cands = by_run.get(run_id, [])

       for cand_row, _rid in run_cands:
           ...
           sliced = full_df.loc[full_df.index.date <= asof_date]
           ...
           try:
               candidate = evaluate_one(ctx)
           ...
           bucket = candidate.bucket
           tier = classify_candidate_tier(cand_row.persisted_risk_result)
           ...
           if cand_row.persisted_bucket != bucket:    # <-- excluded != skip/watch ALWAYS
               _record_flip(...)
               if tier == 1:
                   tier1_mismatch_keys.append(f"{ticker}:{run_id}")
               else:
                   tier2_mismatch_count += 1
   ```

4. **Why surfaced after the Codex R1.C1 fix (commit `624e3e1`, 2026-05-23):**

   Pre-fix: `classify_candidate_tier(None)` returned tier-2 (per the older docstring interpretation: "risk_result=None means risk was not load-bearing because risk-was-not-evaluated; treat as tier-2").

   Post-fix: `classify_candidate_tier(None)` returns tier-1 (per spec E.4: "risk_result=None means LEFT JOIN miss; risk was not load-bearing; bucket independent of risk; tier-1").

   The excluded candidates have:
   - `persisted_bucket = 'excluded'` (set by V1's pre-evaluation short-circuit)
   - `persisted_risk_result = None` (no `risk_feasibility` candidate_criteria row was ever persisted; LEFT JOIN miss in V2's SQL)

   The R1.C1 fix re-classified `None` from tier-2 to tier-1 for the legitimate case of pre-risk-feasibility-schema-era candidates. But the same fix INADVERTENTLY captures the `bucket='excluded'` cases too, because their `risk_result=None` for a DIFFERENT reason -- not "risk was not yet a criterion in the schema" but "this candidate was short-circuited from evaluation entirely". The fix moves both populations from tier-2 (informational) to tier-1 (BLOCKING).

5. **Decisive counter-test passed (reproducer Section 4):**

   For DHC:60, UCO:62, VSAT:64:
   - Each ticker has >= 1258 bars in the legacy parquet (well above 200-bar coverage threshold).
   - V2 builds `EvalRunCohort` successfully.
   - V2 invokes `evaluate_one(ctx)` end-to-end with no error.
   - V2 returns `bucket='skip'` (DHC, VSAT) or `bucket='watch'` (UCO) -- matching the smoke artifact's per-ticker drift signature EXACTLY.

| ticker | V1 persisted | V2 reproducer | Smoke artifact drift | Match |
| --- | --- | --- | --- | --- |
| DHC:60 | excluded (open position) | skip | excluded -> skip | YES |
| UCO:62 | excluded (ETF/fund blocklist) | watch | excluded -> watch | YES |
| VSAT:64 | excluded (open position) | skip | excluded -> skip | YES |

   The reproducer exactly mirrors the smoke artifact's drift signature -- direct evidence of the harness false-positive mechanism.

6. **V1 DB cross-check for ticker-class membership:**
   - **DHC**: trade id=2, state='partial_exited' (open position; appears in `held_set`).
   - **VSAT**: trade id=5, state='managing' (open position; appears in `held_set`).
   - **UCO**: NOT a trade row; is the SOLE entry in `cfg.etf_exclusion.manual_block` (from `swing.config.toml`).

   Each ticker's notes field in the candidates table precisely matches the production code's branch: `"open position" if t in held_set else "ETF/fund blocklist"` at `swing/pipeline/runner.py:1134`.

**Verdict:** H5 CONFIRMED as canonical root cause. V2 harness false-positive caused by missing excluded-bucket filter in `_compute_baseline_parity`.

---

## Section 2 -- Per-criterion divergence pinpoint

The drift signature is BUCKET-LEVEL (excluded vs skip/watch), NOT per-criterion. There is no per-criterion divergence to enumerate because V1 NEVER evaluated criteria for these candidates (`candidate_criteria` row count = 0 for all 15 entries; verified via SQL).

V2's `evaluate_one` produces a full criterion set for each ticker (per reproducer Section 4 output):
- DHC:60 -- TT passes 8/8; VCP fails 3/9 -> `skip` (vcp_fails > 2)
- UCO:62 -- TT passes 8/8; VCP fails 1/9 -> `watch` (1 <= vcp_fails <= 2)
- VSAT:64 -- TT passes 8/8; VCP fails 3/9 -> `skip` (vcp_fails > 2)

The V2-recomputed criteria are valid evaluator outputs but conceptually inapplicable because V1 production code intentionally elides this evaluation for these tickers.

---

## Section 3 -- Drift-class scope

### Section 3.1 -- Same-eval_run scope (per eval_run 60-64)

15 entries across DHC/UCO/VSAT x 60-64 are listed in the smoke artifact's `CRITERION DRIFT DETECTED` section. The per-eval_run breakdown:

| eval_run | data_asof_date | excluded count (V1) | tier-1 drift in smoke |
| --- | --- | --- | --- |
| 60 | 2026-05-20 | 3 (DHC + UCO + VSAT) | 3 (DHC + UCO + VSAT) |
| 61 | 2026-05-20 | 3 (DHC + UCO + VSAT) | 3 (DHC + UCO + VSAT) |
| 62 | 2026-05-21 | 3 (DHC + UCO + VSAT) | 3 (DHC + UCO + VSAT) |
| 63 | 2026-05-21 | 3 (DHC + UCO + VSAT) | 3 (DHC + UCO + VSAT) |
| 64 | 2026-05-22 | 3 (DHC + UCO + VSAT) | 3 (DHC + UCO + VSAT) |

Confirmed via SQL: `SELECT er.id, COUNT(*) FROM candidates c JOIN evaluation_runs er ON er.id = c.evaluation_run_id WHERE c.bucket = 'excluded' AND er.id BETWEEN 60 AND 64 GROUP BY er.id` returns 3 per run.

### Section 3.2 -- Same-ticker scope (across all eval_runs)

DHC + VSAT are stable open positions (trade id=2 state='partial_exited' since 2026-04-27; trade id=5 state='managing' since 2026-05-06). DHC + VSAT will be `bucket='excluded' notes='open position'` for EVERY eval_run between their entry date and trade closure. UCO is on the ETF blocklist permanently (until operator removes); will be `bucket='excluded' notes='ETF/fund blocklist'` for EVERY eval_run that includes UCO in the finviz pull.

### Section 3.3 -- Systemic scope (full 63-eval-run reproduction extrapolation)

The drift class is systemic across BOTH excluded-ticker classes (open-position + ETF-blocklist). The 5-eval_run window enumerates 15 entries; extrapolation to 63 eval_runs is approximately:

```
total_tier1_drift = sum over eval_runs er of |{c in candidates : c.evaluation_run_id == er.id AND c.bucket == 'excluded'}|
```

For the operator's 63-eval-run reproduction, this is bounded above by `63 * len(held_set ∪ etf_exclusion.manual_block)` -- specifically, the held_set varies over time (3+ historical position transitions) but the ETF blocklist is constant (1 entry: UCO).

**Total expected tier-1 drift in full 63-eval-run reproduction:** order of magnitude 100-200 entries (assuming average 2-3 open positions + 1 blocklist ticker per eval_run; exact count depends on operator's trade history).

### Section 3.4 -- Drift class is NOT ticker-specific

This is NOT a DHC/UCO/VSAT-specific defect. It is a CLASS-LEVEL defect (excluded-pre-evaluation candidates) that happens to manifest on the currently-open positions + blocklist. Any future ticker that lands in `held_set` or `etf_exclusion.manual_block` will surface the same drift.

---

## Section 4 -- Why this matters (impact analysis)

- **V1 production correctness:** UNAFFECTED. V1's `bucket='excluded'` is correct -- intentional pre-evaluation pre-emption.
- **V2 sensitivity research blocking:** YES, BLOCKING. The tier-1 BLOCKING flag halts research->shadow promotion per OQ-8 ladder. Full 63-eval-run reproduction will produce a much larger excluded-drift list that prevents any binding-variable identification.
- **Other research-branch artifacts:** PARTIALLY AFFECTED. The method-record (`research/method-records/aplus-criteria-calibration.md`) v0.2.0 / v0.2.1 amendment plan needs an additional Limitation entry for this drift class.
- **Schema / production code:** UNAFFECTED. ZERO schema migrations, ZERO V1 production code changes required.
- **L2 LOCK:** UNAFFECTED. No Schwab API calls; no reads of `{T}.schwab_api.parquet`.
- **DK:62 finding:** ORTHOGONAL. The DK:62 parallel-archive-freshness desync (predecessor investigation) is a distinct architectural data class. The D.1 Shape A refresh fixed DK:62 cleanly; this DHC/UCO/VSAT class is unrelated to Shape A asymmetry.

---

## Section 5 -- Remediation recommendation (Option A -- LOCKED)

### Section 5.1 -- Step 1: Filter excluded candidates in V2 baseline parity

Modify `research/harness/aplus_v2_ohlcv_evaluator/sweep.py:_compute_baseline_parity` to short-circuit candidates with `persisted_bucket='excluded'`:

```python
# At the top of the inner for-loop in _compute_baseline_parity:
for cand_row, _rid in run_cands:
    # Skip V1's pre-evaluation-excluded candidates; V2's evaluate_one
    # cannot produce 'excluded' (per bucket_for return enumeration).
    # V1 short-circuits these at swing/pipeline/runner.py:1105-1141 for
    # held_set (open positions) + cfg.etf_exclusion.manual_block.
    if cand_row.persisted_bucket == "excluded":
        continue
    ...
```

**Effect:** Excluded candidates are NEITHER included in tier-1 mismatch list NOR counted in tier_1_count / tier_2_count. The baseline-parity comparison applies only to candidates V1 actually evaluated. The matrix-sensitivity sweep still runs over all candidates (no filter there -- sweep continues to expose how excluded candidates SOMETIMES SHIFT bucket under cfg substitution, which is a useful per-variable drill-down signal).

**Out-of-scope refinement (V2 candidate):** also drop excluded candidates from per-variable sweep iteration. The per-variable drill-down currently lists excluded->skip and excluded->watch flips for excluded candidates at every sweep_point because their bucket change at a different threshold is meaningful only as "this excluded ticker would have produced a skip at threshold X" -- not actionable for the sensitivity question. Banked for V2 dispatch.

### Section 5.2 -- Step 2: Add discriminating test

Create `tests/research/test_aplus_v2_ohlcv_sweep_excluded_filter.py` with:

```python
def test_excluded_persisted_candidates_skip_baseline_parity():
    """V2 baseline parity must filter persisted bucket='excluded' candidates.

    V1 production code at swing/pipeline/runner.py:1105-1141 short-circuits
    held_set + cfg.etf_exclusion.manual_block tickers via pre-evaluation
    exclusion; their candidates carry bucket='excluded' notes='open position'
    or 'ETF/fund blocklist' with criteria=() and rs_method='unavailable'.
    bucket_for cannot return 'excluded'; comparison is meaningless.
    """
    # Plant 2 synthetic candidates: one bucket='excluded' notes='open position',
    # one bucket='excluded' notes='ETF/fund blocklist'.
    # Plant 1 legitimate candidate with bucket='skip'.
    # Invoke _compute_baseline_parity + assert:
    #   - parity.tier1_match == True
    #   - parity.tier1_mismatch_candidates == ()  (NO excluded entries)
    #   - parity.tier_1_count == 1 (only the legitimate candidate counted)
    #   - flipped == ()  (no baseline-parity flips recorded)
```

### Section 5.3 -- Step 3: Method-record amendment

Append a new Limitations entry to `research/method-records/aplus-criteria-calibration.md` (v0.2.0 -> v0.2.1 -- complements the L4 Shape A desync entry already planned):

> **Limitation L5: V2 baseline-parity must filter V1 pre-evaluation-excluded candidates.** V1's production pipeline at `swing/pipeline/runner.py:1105-1141` short-circuits criterion evaluation for two excluded-ticker classes -- open positions (`held_set` from journal) + ETF/fund blocklist (`cfg.etf_exclusion.manual_block`) -- and writes `Candidate(bucket='excluded', criteria=(), notes='open position'|'ETF/fund blocklist', rs_method='unavailable', rs_rank=None, ...)` directly without invoking `evaluate_batch`. V2's `evaluate_one(ctx)` produces a Candidate from `bucket_for(...)` which returns only `{'aplus', 'watch', 'skip'}` -- never `'excluded'`. Baseline parity comparison must filter `persisted_bucket='excluded'` candidates to avoid systemic tier-1 mismatch false-positives. Documented direct evidence: DHC/UCO/VSAT x eval_runs 60-64 investigation 2026-05-24 (this finding). Remediation: 1-line `if cand_row.persisted_bucket == "excluded": continue` guard at top of `_compute_baseline_parity` inner loop.

### Section 5.4 -- Step 4: Re-run smoke after V2 fix lands

After the V2 filter ships, re-run:

```bash
python -m swing.cli diagnose aplus-sensitivity-v2 --eval-runs=5 --max-runtime-seconds=120
```

Expected: `Tier-1 match: PASS`; `CRITERION DRIFT DETECTED` banner OMITTED entirely (per `output.py:178` early-return when `tier1_match=True`). Both-exist diagnostic still emits 3-ticker AESI/DK/PL banner (unrelated; from D.1 refresh state).

### Section 5.5 -- What this investigation does NOT recommend

- **DO NOT** modify V1 production code (read-only invariant). The pre-evaluation exclusion at `swing/pipeline/runner.py:1105-1141` is correct V1 design; preserving the `bucket='excluded'` row keeps `PriceCache._last_close` fresh for the dashboard fallback (existing CLAUDE.md gotcha "PriceCache._last_close only sees tickers in today's candidates table").
- **DO NOT** modify V1 persisted candidate rows. The 15 affected rows have correct state.
- **DO NOT** attempt to replicate V1's exclusion logic in V2 (e.g., reading the journal + ETF blocklist in V2). The filter pattern is simpler, lower-risk, and architecturally cleaner -- baseline parity only applies to candidates V1 actually evaluated.
- **DO NOT** ship the V2 filter fix in this investigation dispatch (scope is DIAGNOSTIC; remediation Option A is the minimal-blast-radius path documented for a follow-on dispatch).

---

## Section 6 -- Forward-binding lessons for future research-branch arcs

### Section 6.1 -- Lesson 1: V2 baseline-parity comparison must filter pre-evaluation-excluded candidates

When V1 production has a SHORT-CIRCUIT path that writes a persisted bucket value the V2 evaluator cannot reproduce, the V2 baseline-parity comparison MUST filter those candidates before invoking the evaluator. Otherwise the comparison produces 100% false-positive drift on the entire short-circuited population.

Pattern complement to the predecessor DK:62 investigation lesson #1: where DK:62 was an ARCHITECTURAL DATA FRESHNESS desync (asymmetric writers + symmetric readers), this is an ARCHITECTURAL EVALUATION-PATHWAY asymmetry (V1's two-path evaluate_or_short-circuit vs V2's one-path evaluate-everything).

### Section 6.2 -- Lesson 2: Tier-classification semantic gap on LEFT JOIN miss

`classify_candidate_tier(persisted_risk_result=None)` returns tier-1 per Codex R1.C1 (spec E.4 binding). But the `None` value arises from TWO distinct upstream conditions:

1. Pre-risk-feasibility schema era -- legitimate "risk not yet a criterion"; the R1.C1 intent.
2. Pre-evaluation-excluded candidates -- "criterion evaluation never ran; LEFT JOIN miss is a side effect of the short-circuit"; INCIDENTAL collateral of R1.C1.

The R1.C1 fix correctly handles case 1 but does not distinguish case 2. The remediation (Option A filter on `persisted_bucket='excluded'`) corrects the tier-1 mismatch list at the BUCKET level rather than the tier level -- complementary to R1.C1 rather than supplanting it.

Bank as forward-binding lesson #6 for the V2 research arc: tier-classification function semantics must enumerate ALL upstream conditions producing the input value, not just the spec'd primary case.

### Section 6.3 -- Lesson 3: Pre-evaluation exclusion is a V1 architectural feature, not an evaluator bug

V1's `swing/pipeline/runner.py:1105-1141` pre-evaluation exclusion serves three production purposes:
1. Open positions don't need a buy/watch signal (they're already in portfolio).
2. ETF/fund blocklist filters known-non-tradeable instruments.
3. Both classes preserve their candidate row so `PriceCache._last_close` returns fresh close (per existing CLAUDE.md gotcha).

V2 should NOT attempt to replicate these purposes; V2's only baseline-parity question is "do V1's evaluator-produced buckets match V2's evaluator-produced buckets?" -- which by definition only applies to candidates V1 actually evaluated.

Pre-empt in any future research-branch harness consuming `candidates`-table rows: enumerate ALL persisted-bucket values + identify which were produced by `bucket_for(...)` vs which are sentinel bucket values from pre-evaluation paths (`'excluded'`, `'error'`). Baseline-parity only applies to the former. Bank as forward-binding lesson #7.

### Section 6.4 -- Lesson 4: Banked CLAUDE.md cumulative gotcha candidate (#25)

**Gotcha candidate:** *V2 baseline-parity comparison must filter persisted `bucket='excluded'` candidates because V1 production pipeline pre-empts criterion evaluation for open positions (`held_set`) + ETF blocklist (`cfg.etf_exclusion.manual_block`); `bucket_for` cannot return `'excluded'` so direct V1-vs-V2 bucket comparison is meaningless on these rows.*

**Failure mode:** When a V1 production code path writes a sentinel bucket value (e.g., `'excluded'`, `'error'`) that the V2 evaluator architecturally cannot reproduce (because `bucket_for` only returns evaluator-output buckets), V2's baseline-parity comparison naively flags every such row as drift. Codex R1.C1 (`classify_candidate_tier(None) -> tier-1`) inadvertently promotes these false-positives from tier-2 (informational) to tier-1 (BLOCKING). The 15-entry DHC/UCO/VSAT x 60-64 surface is direct evidence; broader 63-eval-run reproduction would scale linearly with `|held_set ∪ etf_exclusion.manual_block|`.

**Pre-empt** in any future V2 baseline-parity harness: enumerate every persisted bucket value V1 can produce + identify which originate from `bucket_for(...)` (subject to parity comparison) vs which originate from pre-evaluation paths (must be filtered before comparison). Discriminating test pattern: plant 1 candidate per sentinel-bucket class (`'excluded'/notes='open position'`, `'excluded'/notes='ETF/fund blocklist'`, `'error'/notes='OHLCV fetch failed'`) + assert NONE are counted in tier-1 mismatch list.

Forward-binding for V2 reader enhancement (Section 5.4 banked) + any future V1-vs-V2 parity harness for criterion / scoring / bucket comparison.

### Section 6.5 -- Lesson 5: Predecessor-investigation prediction realized

The predecessor DK:62 investigation Section 5.3 lesson #3 explicitly anticipated:

> "Bank as a verification candidate: regenerate the smoke against HEAD `a43a921` (post-merge with all Codex fixes applied) and confirm the drill-down rows behave per spec."

The 2026-05-24 smoke is the regeneration. The drill-down rows DO behave per spec (per-variable drill-down records all flips correctly per R3.M1 fix; `old_bucket` is V2-recomputed-baseline per R4.M1 fix). The new finding is that the BASELINE itself is wrong for excluded candidates because `_compute_baseline_parity` does not filter them.

Pattern complement to DK:62 §5.3 lesson #3: regenerating the smoke after Codex fixes SURFACES new drift classes that the pre-fix sweep masked. The R1.C1 fix specifically promoted this drift class from tier-2 (silent) to tier-1 (visible). The predecessor's anticipation was correct + accurately identified the surfaced-by-Codex-fix mechanism. Bank as forward-binding lesson #8.

---

## Section 7 -- Verification artifacts produced

| Artifact | Path | Purpose |
| --- | --- | --- |
| Investigation findings doc (THIS FILE) | `docs/v2-dhc-uco-vsat-drift-investigation-2026-05-24.md` | Per-hypothesis evidence + root cause + scope + remediation |
| Return report | `docs/v2-dhc-uco-vsat-drift-investigation-return-report.md` | Cumulative-precedent shape; investigation summary + verification + handback |
| Reproducer script | `tmp/dhc-uco-vsat-investigation/reproducer.py` | Discriminating reproducer for V2 evaluate_one on excluded candidates; output preserved in this doc Section 1.5 evidence #5 |

No code changes shipped. No V2 reader fix. No schema migration. No V1 production code changes. ZERO new Schwab API calls. ZERO reads of `{T}.schwab_api.parquet` (the V2 reader's L2 LOCK preserved; the reproducer's diagnostic-only file-existence check is filesystem-level read, not API call). ZERO modifications to `candidate_criteria` / `candidates` / `evaluation_runs` / `trades` rows.

---

## Section 8 -- Cumulative streaks preserved

- **ZERO Co-Authored-By footer** -- investigation findings + return report committed without the footer (preserves the ~496+ cumulative streak through the dispatch-brief commit `970ce80`).
- **L2 LOCK BINDING** -- investigation used legacy `.parquet` reads only; ZERO Schwab API calls; ZERO reads of `{T}.schwab_api.parquet`; V2 reader code (still preserves L2 LOCK via the 5 BINDING tests at `tests/research/test_aplus_v2_ohlcv_reader.py`).
- **Schema v21 LOCKED** -- no migrations touched.
- **V1 persisted state READ-ONLY** -- investigation queried `candidates` / `candidate_criteria` / `evaluation_runs` / `trades` rows but did not modify them.
- **Production swing/ READ-ONLY** -- investigation read `swing/evaluation/scoring.py`, `swing/pipeline/runner.py`, `swing/evaluation/evaluator.py` but did not modify them. `git diff main -- swing/` remains EMPTY.
- **ASCII-only on narrative text** -- this document is ASCII-clean per Windows cp1252 stdout discipline.
- **C.C lesson #6 cumulative validation** -- if a follow-on V2 dispatch ships the Option A fix, it would be 34th cumulative validation. This investigation itself produces NO code, so no validation count change applies here.

---

## Section 9 -- Open questions for orchestrator-side QA / operator review

1. Should the V2 filter fix (Section 5.1) be a SEPARATE dispatch (clean scope; single sub-bundle; ~5-10 commits including test + method-record patch) OR folded into the next research-branch arc?
   - **Recommendation:** SEPARATE dispatch -- the fix is small + self-contained + unblocks the research->shadow promotion gate. A larger arc that bundles the fix risks scope creep.

2. Should `_compute_baseline_parity` ALSO filter `bucket='error'` candidates?
   - **Recommendation:** YES. Same architectural argument as `'excluded'`: V2's evaluate_one cannot produce `'error'` (errors are handled via raised exceptions, not return values). The reproducer did not test this case (no `bucket='error'` candidates currently exist in eval_runs 60-64), but the failure mode is identical. Include in the same fix.

3. Should the per-variable drill-down section ALSO filter excluded candidates?
   - **Recommendation:** OPERATOR DECISION. The drill-down currently shows excluded->skip / excluded->watch flips at various sweep_points. These are not informationally useful for sensitivity analysis (the excluded candidate is never going to enter the operator's actionable population). But filtering them removes a column of "what would happen if this excluded ticker were eligible" data that some operators may find marginally informative. Default recommendation: FILTER (drop from drill-down) because the same architectural argument applies: V2 cannot reproduce V1's `'excluded'` so any flip vs the V2 recomputed baseline is from a non-comparable starting point. Bank as separate operator-paired decision.

4. Should the method-record amendment (Section 5.3) be applied in THIS branch (alongside this investigation handback) OR in a follow-up housekeeping bundle?
   - **Recommendation:** Defer to operator preference; investigation branch ships diagnostic findings only by default. If operator prefers, the method-record patch is a 1-file edit and can be appended to this branch before merge. The L4 + L5 limitation entries naturally pair; merging them together makes for a cleaner method-record v0.2.1 patch bump.

---

*End of V2 OHLCV DHC/UCO/VSAT x eval_runs 60-64 CRITERION DRIFT investigation findings.*

*Root cause identified with code:line citations + decisive counter-test reproducer; all 4 narrowed hypotheses falsified; H5 (V2 harness-vs-V1-pre-evaluation-exclusion-pathway gap) confirmed as canonical root cause; drift-class scope SYSTEMIC across open-position + ETF-blocklist populations; remediation Option A LOCKED with 1-line research-branch filter + discriminating test + method-record Limitation L5 patch; 5 forward-binding lessons banked including NEW gotcha #25 candidate; ZERO production code changes; ZERO Co-Authored-By footer; L2 LOCK preserved; schema v21 LOCKED.*
