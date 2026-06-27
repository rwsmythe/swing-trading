# V2 OHLCV Baseline-Parity Excluded-Filter Fix -- Return Report

**Dispatch date:** 2026-05-24
**Branch:** `applied-research-v2-baseline-parity-excluded-filter`
**Dispatch brief:** `docs/v2-baseline-parity-excluded-filter-dispatch-brief.md` (commit `ffd10d8`)
**Investigation substrate:** `docs/v2-dhc-uco-vsat-drift-investigation-2026-05-24.md` (merge `d7cdd51`)
**Outcome:** Fix #1 + Fix #2 shipped end-to-end; Tier-1 baseline parity now PASS on operator smoke; CLAUDE.md gotcha #25 implemented as its first canonical application; 34th cumulative C.C lesson #6 validation CLEAN.

---

## Section 1 -- Outcome summary

- **Fix #1 (CORE; LOCKED)**: 1-line filter `if cand_row.persisted_bucket == "excluded": continue` at the top of `_compute_baseline_parity`'s per-candidate loop (`research/harness/aplus_v2_ohlcv_evaluator/sweep.py:545-557`). Closes the 15 DHC/UCO/VSAT x eval_runs 60-64 false-positive tier-1 drift entries.
- **Fix #2 (DEFENSIVE; LOCKED)**: filter widened from `{"excluded"}` to `{"excluded", "error"}` in the same condition. Defense-in-depth for OHLCV-fetch-failure sentinels (V1 production at `swing/pipeline/runner.py:1142-1149`). No current `bucket='error'` rows in operator's eval_runs 60-64; closes the failure mode prospectively.
- **Fix #3 (OPTIONAL; DEFERRED)**: per-variable drill-down filter for excluded candidates is **NOT NEEDED for flip-prevention** post Fix #1+#2 -- the variable-loop's flip guard at `sweep.py:419-420` (`if baseline_bucket is not None and bucket != baseline_bucket:`) naturally short-circuits when `baseline_bucket_map.get(cand_key)` returns None (the excluded candidates were `continue`d in `_compute_baseline_parity`, so they have no `baseline_bucket_map` entry). The remaining open question -- per-sweep-point COUNT inflation (excluded candidates counted as skip/watch/aplus in matrix entries because V2's `evaluate_one` returns those buckets) -- is operator-paired per investigation Section 9.3; banked as V2 candidate; matrix-count behavior unchanged in this fix.
- **V2 smoke verification**: post-fix smoke at `exports/diagnostics/aplus-sensitivity-v2-20260524T181554Z.{csv,md}` (5 eval_runs / 121s runtime / 516 universe / 351 candidates / 5 OHLCV coverage skips). **Tier-1 match: PASS** (banner explicitly: "V1 and V2 agree on all tier-1 candidates"). `CRITERION DRIFT DETECTED` section OMITTED entirely. Tier-2 match unchanged at 10/0. Both-exist banner (AESI/DK/PL) unchanged (orthogonal).
- **Adversarial Codex review**: NOT invoked. Per brief: "OPTIONAL -- invoke if bucket='error' extension OR drill-down filter scope expands beyond the literal 1-line locked fix." Fix #2 (`bucket='error'`) was explicitly LOCKED in investigation Section 4.5 V2 candidate #3 as part of the same fix; Fix #3 was deferred per investigation Section 9.3. So neither trigger condition fired. Operator-paired choice retained per the brief.

---

## Section 2 -- Commit chain (4 commits)

| Commit | Type | Files | Purpose |
| --- | --- | --- | --- |
| `b351439` | fix(research/v2) | 2 (sweep.py + tests) | Fix #1: filter `bucket='excluded'` |
| `bab99dd` | fix(research/v2) | 2 (sweep.py + tests) | Fix #2: extend filter to `bucket='error'` |
| `be2ef9a` | test(research/v2) | 1 (tests only) | Negative control: legitimate skip-tier-1 still flagged |
| `da2e52f` | chore(diagnostics) | 2 (CSV + md) | Post-fix V2 smoke artifact (Tier-1 PASS) |

**Total:** 4 commits; 0 production swing/ writes; 0 schema migrations; 0 new Schwab API calls; 0 `Co-Authored-By` footer trailers.

**TDD slice discipline:** each of the 3 fix/test commits followed the RED-GREEN-COMMIT cycle:
- **Slice 1**: wrote `test_baseline_parity_filters_persisted_excluded_open_position_and_blocklist` first; ran -> RED (`{'ZZEXCL1:1', 'ZZEXCL2:1'}` leaked into `tier1_mismatch_candidates`); implemented Fix #1; ran -> GREEN (all 28 tests pass); committed.
- **Slice 2**: wrote `test_baseline_parity_filters_persisted_error_bucket` first; ran -> RED (`{'ZZERR1:1'}` leaked); extended filter set to `{"excluded", "error"}`; ran -> GREEN (29 tests pass); committed.
- **Slice 3**: wrote `test_baseline_parity_filter_does_not_swallow_legitimate_skip_tier1_drift` (negative-control); ran -> GREEN (filter correctly narrow). To verify discriminating power, mutated filter to over-broad `{"excluded", "error", "skip"}`; test FAILED with empty `tier1_mismatch_candidates`; restored correct fix; test PASSED; committed test only (no production change in slice 3).

---

## Section 3 -- Deliverables

| Artifact | Path | Lines / Size | Purpose |
| --- | --- | --- | --- |
| Fix #1 implementation | `research/harness/aplus_v2_ohlcv_evaluator/sweep.py:545-557` | +13 lines | Sentinel-bucket filter at `_compute_baseline_parity` per-candidate loop entry |
| Fix #1+#2 discriminating tests | `tests/research/test_aplus_v2_ohlcv_sweep.py` | +269 lines (3 tests) | Excluded-filter + error-filter + negative-control |
| Test helper extension | `tests/research/test_aplus_v2_ohlcv_sweep.py:_seed_candidate` | +2 lines | Added optional `notes` kwarg (backward-compatible; defaults None) |
| Post-fix V2 smoke artifact | `exports/diagnostics/aplus-sensitivity-v2-20260524T181554Z.{csv,md}` | 627 lines | Tier-1 PASS verification |
| Return report (THIS FILE) | `docs/v2-baseline-parity-excluded-filter-return-report.md` | -- | Outcome summary + verification + handback |

---

## Section 4 -- Verification self-checks (inline)

### Section 4.1 -- ruff check

```
$ ruff check research/harness/aplus_v2_ohlcv_evaluator/
All checks passed!
```

### Section 4.2 -- schema unchanged (v21 LOCKED)

```
$ git diff main -- swing/data/migrations/
(empty)
```

### Section 4.3 -- production swing/ read-only invariant

```
$ git diff main -- swing/
(empty)
```

All edits confined to `research/harness/aplus_v2_ohlcv_evaluator/sweep.py` + `tests/research/test_aplus_v2_ohlcv_sweep.py` + `docs/` + `exports/diagnostics/`.

### Section 4.4 -- L2 LOCK preservation

```
$ python -m pytest tests/research/test_aplus_v2_ohlcv_reader.py -q
14 passed
```

All 14 V2 reader L2 LOCK reinforcement tests remain GREEN (4 file-open boundaries + 4-module import sentinel graph + byte-checksum + signature lock + V2 source-grep). Zero new Schwab API calls; zero V2 reads of `{T}.schwab_api.parquet`.

### Section 4.5 -- ZERO Schwab API calls

The fix is contained in `_compute_baseline_parity` (research-branch only). The 5 BINDING L2 LOCK discriminating tests stay green. No schwabdev imports, no `client.X(...)` calls, no reads of `{T}.schwab_api.parquet` introduced.

### Section 4.6 -- ZERO Co-Authored-By footer

```
$ git log main.. --format='%B' | grep -i 'co-authored-by'
(empty)
```

Preserves the ~500+ cumulative streak through housekeeping `8330e50` (per orchestrator-context lesson #7 + Phase 12 Sub-sub-bundle C.B 2026-05-15 forward-binding).

### Section 4.7 -- ASCII-only on runtime CLI paths + markdown narrative

All edits (sweep.py comment block, tests, this report, smoke artifact) are ASCII-clean per Windows cp1252 stdout discipline. The two embedded "<->" arrow tokens in the report narrative are ASCII; the sweep.py docstring uses no non-ASCII glyphs.

### Section 4.8 -- All test suites green

```
$ python -m pytest tests/research/test_aplus_v2_ohlcv_sweep.py -q
30 passed

$ python -m pytest tests/research/ -q
310 passed, 1 skipped (env-var-guarded, baseline)
```

+1 net test vs pre-fix baseline (was 309 passed + 1 skipped per the pre-fix smoke baseline; now 310 passed + 1 skipped after the 3 new discriminating tests minus 2 organizational deltas).

### Section 4.9 -- V1 persisted state unchanged

The fix is a research-branch READ-ONLY filter on `cand_row.persisted_bucket` (column read from operator's `candidates` table via existing `_fetch_candidates_with_run_id`). No `INSERT`/`UPDATE`/`DELETE` issued against `candidates`, `candidate_criteria`, `evaluation_runs`, or any other V1-persisted-state table.

---

## Section 5 -- Smoke artifact delta (pre-fix vs post-fix)

| Field | Pre-fix `20260524T162641Z` | Post-fix `20260524T181554Z` | Delta |
| --- | --- | --- | --- |
| Tier-1 match | FAIL | PASS | **CLOSED** |
| CRITERION DRIFT DETECTED entries | 15 | 0 (section OMITTED) | **CLOSED** |
| Tier-2 match count | 10 | 10 | unchanged |
| Tier-2 mismatch count | 0 | 0 | unchanged |
| Tier-2 via surrogate count | 0 | 0 | unchanged |
| Eval-runs window | 5 (60..64) | 5 (60..64) | unchanged |
| Total candidates evaluated | 351 | 351 | unchanged |
| V2 universe size | 516 | 516 | unchanged |
| OHLCV coverage skips (global) | 5 | 5 | unchanged |
| Universe skipped tickers | 0 | 0 | unchanged |
| Truncated by runtime cap | YES (120.56s) | YES (121.73s) | runtime drift only (in-cap) |
| Both-exist banner | AESI / DK / PL | AESI / DK / PL | unchanged (orthogonal) |
| Headline binding variables | none | none | unchanged |
| Sensitivity matrix | 17 vars / ~85 rows | 17 vars / ~85 rows | unchanged (matrix counts unaffected by baseline-parity filter; see Section 6 Fix #3 note) |

**Confidence**: V1 evaluator (production) + V2 evaluator (research-branch) agree on ALL tier-1 candidates V1 actually evaluated. V2 is materially better than the pre-fix smoke suggested per investigation `d7cdd51` "GREAT NEWS for V2 quality" framing.

---

## Section 6 -- V2 candidates banked + open questions

### Section 6.1 -- Closed by this fix

1. **V2 candidate #1 (investigation Section 4.5)**: filter `bucket='excluded'` from baseline parity -- CLOSED by Fix #1.
2. **V2 candidate #3 (investigation Section 4.5)**: extend filter to `bucket='error'` -- CLOSED by Fix #2.

### Section 6.2 -- Banked / DEFERRED (operator-paired or V2 dispatch)

1. **V2 candidate #2 (investigation Section 4.5 + Section 9.3)**: per-variable drill-down filter for excluded candidates. Per analysis in Section 1 above, flip-recording is ALREADY transitively prevented by Fix #1+#2 via the `baseline_bucket_map.get(cand_key) is None` guard at `sweep.py:419-420`. The only remaining effect is per-(variable, sweep_point) COUNT inflation -- excluded candidates' V2-recomputed buckets (skip/watch/aplus) count into the sensitivity matrix. This is operator-visible matrix behavior; per investigation Section 9.3 the default recommendation is FILTER but it's a separate operator-paired decision. **DEFERRED** to a follow-up V2 dispatch if operator confirms.
2. **Method-record amendment (investigation Section 5.3 + Section 9.4)**: append Limitation L5 to `research/method-records/aplus-criteria-calibration.md` bumping v0.2.0 -> v0.2.1 (complementing the L4 Shape A desync entry). Per brief Section 5 NON-scope (D.3 from Option D; "SEPARATE follow-up -- small inline doc edit OR mini dispatch post-Option-A-fix"). **DEFERRED** to operator decision per brief.
3. **V2 reader prefer-fresher mtime tiebreaker (investigation D.4 + OQ-18)**: V2.5/V3 candidate per brief Section 5 NON-scope. **DEFERRED** to V2 dispatch.
4. **Full 63-eval-run operator reproduction**: UNBLOCKED by this fix (Tier-1 PASS no longer blocks promotion gate). Per brief Section 6: "operator-paired execution of full 63-eval-run reproduction (Tier-1 PASS unblocks this)". **DEFERRED** to operator execution step.

### Section 6.3 -- NEW V2 candidates this dispatch surfaced

None. The fix is a clean implementation of CLAUDE.md gotcha #25's discriminating-test pattern verbatim. No new failure modes identified.

---

## Section 7 -- Cumulative C.C lesson #6 validation (34th)

**Pre-Codex review applied (Codex MCP NOT invoked per brief operator-paired choice):**

| Gotcha | Application |
| --- | --- |
| #25 (sentinel-bucket parity-comparison discipline) | DIRECT APPLICATION -- this fix is gotcha #25's first canonical implementation; the discriminating-test pattern in slice 1+2 mirrors the gotcha's prescribed test shape verbatim. |
| #21 (Expansion #13 cumulative regression cascade audit) | APPLIED -- `_compute_baseline_parity` was restructured 4 times by the executing-plans Codex R1.M2 + R3.M1 + R4.M1 cascade. Fix #1+#2 are surgical additions (one `continue` guard at the top of the inner loop) that do NOT touch any of the restructured logic (counter accumulation, baseline_bucket_map population, flip recording with old_bucket attribution). Per "imagined Codex next-round" audit: no second-order regressions surfaced (verified via 310 tests green + smoke artifact matrix unchanged from pre-fix). |
| #22 (per-counter-accumulation audit applies to ANY counter) | APPLIED -- the filter skips candidates via `continue` BEFORE the `baseline_tier_1_count` / `baseline_tier_2_count` increments + BEFORE the `tier2_match_count` / `tier2_mismatch_count` increments. Counter unit-correctness preserved: each non-sentinel candidate is counted exactly once per `_compute_baseline_parity` invocation. Smoke artifact's tier-2 counts (10/0) are unchanged from pre-fix, confirming counter behavior intact. |
| #23 (dataclass attribution metadata audit) | APPLIED -- FlippedCandidate field consumption: the filter prevents excluded/error candidates from reaching `_record_flip` in `_compute_baseline_parity` (no orphan attribution from those candidates). Variable-loop path is naturally short-circuited (Section 1 analysis). |
| #11 (template-rendering surface audit) | APPLIED -- the smoke artifact's CSV + markdown emitters surface the `tier1_mismatch_candidates` tuple from `BaselineParityReport`; the fix reduces this from 15 entries to 0 (visible in artifact delta Section 5 above). No new dataclass fields; no template changes needed; downstream rendering naturally reflects the filtered set. |
| #20 (Expansion #4 sub-refinement: runtime-binding-shape + empty-input audit) | N/A -- no new SQL skeletons; no new parameterized queries. |
| #19 (Expansion #2 sub-refinement: cascade-call-graph) | APPLIED -- verified that `_compute_baseline_parity`'s `cand_row.persisted_bucket` field exists on `CandidateRow` (per `context_builder.py:64` -- field signature is `persisted_bucket: str  # 'aplus' \| 'watch' \| 'skip' \| 'error' \| 'excluded'`). The cascade from `_fetch_candidates_with_run_id` (which SELECTs `c.bucket AS persisted_bucket`) into `_compute_baseline_parity` is verified intact. |

**Verdict**: 34th cumulative validation CLEAN. No NEW gotchas surfaced. Pre-Codex orchestrator-side review caught everything that needed to be considered for a clean filter implementation of an already-locked architectural lesson.

---

## Section 8 -- Streaks preserved

- **ZERO Co-Authored-By footer**: 4 new commits, all clean (~500+ cumulative streak preserved through this dispatch's da2e52f tip).
- **L2 LOCK BINDING**: preserved; 14 BINDING discriminating tests stay green (`test_aplus_v2_ohlcv_reader.py`).
- **Schema v21 LOCKED**: no migrations.
- **V1 persisted state READ-ONLY**: only SELECT queries through existing `_fetch_candidates_with_run_id` consumer; zero mutations.
- **Production swing/ READ-ONLY**: `git diff main -- swing/` empty; existing OQ-17 CLI carve-out at `swing/cli.py` unchanged.
- **ASCII-only on narrative + runtime**: all edits ASCII-clean per Windows cp1252 stdout discipline.
- **34th C.C lesson #6 cumulative validation**: CLEAN (no new gotchas; first canonical application of #25).

---

## Section 9 -- Handback to operator

### Section 9.1 -- What shipped

1. Fix #1 (CORE; locked Option A): bucket='excluded' filter in `_compute_baseline_parity`.
2. Fix #2 (DEFENSIVE; locked Option A extension): same filter widened to `{'excluded', 'error'}`.
3. 3 discriminating tests in `tests/research/test_aplus_v2_ohlcv_sweep.py` (open-position-and-blocklist + error-bucket + negative-control).
4. Post-fix V2 smoke artifact at `exports/diagnostics/aplus-sensitivity-v2-20260524T181554Z.{csv,md}` -- **Tier-1 FULL PASS**.
5. This return report.

### Section 9.2 -- What did NOT ship (per brief Section 5 NON-scope + investigation Section 9 OQs)

- Fix #3 per-variable drill-down COUNT filter (operator-paired; flip-prevention already covered transitively).
- Method-record amendment (D.3; small follow-up).
- Method-record V2 candidate banking (D.4; same follow-up).
- Full 63-eval-run operator reproduction (separate operator-paired execution step; UNBLOCKED by this fix).
- V2 reader prefer-fresher mtime tiebreaker (V2.5/V3 candidate).
- V1 production code changes (production READ-ONLY).
- Schwab API integration changes (L2 LOCK preserved).

### Section 9.3 -- Suggested orchestrator-side next steps

Per brief Section 6:
1. QA implementer product (this return report + the 4-commit chain + the smoke artifact + the 3 new discriminating tests). All invariants self-verified in Section 4 above.
2. Merge `--no-ff` to main; push.
3. Post-merge housekeeping (sub-event scale; in-place amendments to `CLAUDE.md` "Current state" line if desired; no new gotchas to bank since gotcha #25 was already added at housekeeping `8330e50`).
4. Operator-paired decision on:
   - D.3 (method-record v0.2.1 amendment with Limitation L5) -- small inline edit OR mini dispatch.
   - D.4 (V2 candidate banking in method-record) -- same follow-up vehicle.
   - Fix #3 per-variable drill-down COUNT filter (operator-paired per investigation Section 9.3 default recommendation FILTER).
5. Operator-paired execution of full 63-eval-run reproduction (Tier-1 PASS unblocks this).
6. Research -> shadow promotion gate per OQ-8 ladder fires post-full-reproduction + binding-threshold identification.

### Section 9.4 -- Expected duration vs actual

Brief estimated ~1-3 hours operator-paced; actual implementer time was sub-hour for the 3 TDD slices + smoke re-run + return report. The fix's surgical 1-line-then-set-extension scope landed cleanly without Codex involvement.

---

*End of V2 OHLCV baseline-parity excluded-filter fix return report.*

*Fix shipped end-to-end; Tier-1 baseline parity now PASS on operator smoke; CLAUDE.md cumulative gotcha #25 implemented as its first canonical application; 34th cumulative C.C lesson #6 validation CLEAN; ZERO Co-Authored-By footer (4-commit chain); L2 LOCK preserved; schema v21 LOCKED; production swing/ READ-ONLY; full 63-eval-run operator reproduction + research->shadow promotion gate now UNBLOCKED.*
