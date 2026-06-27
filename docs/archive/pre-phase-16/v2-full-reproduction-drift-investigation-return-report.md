# V2 OHLCV Full-63-Eval-Run Reproduction CRITERION DRIFT Investigation -- Return Report

**Investigation date:** 2026-05-24
**Branch:** `applied-research-v2-full-reproduction-drift-triage`
**Workflow:** `superpowers:systematic-debugging` (diagnostic only)
**Findings doc:** [`docs/v2-full-reproduction-drift-investigation-2026-05-24.md`](v2-full-reproduction-drift-investigation-2026-05-24.md)

---

## Section 1 Investigation summary

Root-caused the 14-entry V1<->V2 baseline-parity divergence at the full-63-eval-run V2 smoke (artifact `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.{csv,md}`). The drift spans 6 tickers (CNTA, ECVT, APLS, FTI, STNG, PL) across 9 unique (ticker, asof_date) pairs in eval_runs 6-43.

**Result: H6 (NEW) CONFIRMED -- OHLCV archive bar-content mutation between V1's eval_run persistence time and V2's current-archive-read time.** All 5 narrowed hypotheses (H1-H5) FALSIFIED with concrete evidence.

The V2 evaluator is **CORRECT** given its current archive inputs (decisive counter-test reproduces V2's smoke bucket exactly for all 14 candidates). The drift is **DATA-INPUT divergence**: subsequent pipeline runs (between V1's original eval and today's V2 read) refreshed the OHLCV archive via `swing/data/ohlcv_archive.py:write_window:358-360`, which uses `drop_duplicates(subset=["asof_date"], keep="last")` semantics. yfinance returns slightly different historical bar values on re-fetch (late-reported volume; retroactive adjustments) and `write_window` overwrites the bars V1 originally saw. V2 reads the current (mutated) archive.

Per-criterion divergence pinpoint: each drift candidate has EXACTLY ONE criterion result diff between V1 and V2.
- **11 of 14 candidates** (CNTA/ECVT/APLS/FTI/STNG): `vcp_volume_contraction` flip (V2 cons_avg +0.62% to +2.77% higher than V1 persisted).
- **3 of 14 candidates** (PL x 3): `tightness` flip (V2 0-day streak vs V1 2-day streak; supported by V2 adr = 10.60% vs V1 adr = 10.55%).

---

## Section 2 Hypothesis verdicts

| Hypothesis | Verdict | Key evidence |
|---|---|---|
| H1: Shape A vs legacy historical desync (PL focus; gotcha #24 extension) | **FALSIFIED** | PL Shape A and legacy AGREE bar-by-bar on 1236/1236 common bars; 5 of 6 tickers have ONLY legacy (V2 reads legacy directly). |
| H2: OQ-14 RS universe drift | **FALSIFIED** | All 6 drift tickers ABSENT from V2's current universe (516-ticker S&P 500 snapshot); V1 and V2 BOTH compute `rs_method='fallback_spy'`; TT8 result identical with same excess value. |
| H3: V2 source-ladder asymmetry (schwab_api parquet) | **FALSIFIED** | V2 reader code path NEVER opens `*.schwab_api.parquet` (L2 LOCK preserved). For 5 tickers only legacy exists; for PL Shape A matches legacy. |
| H4: V1 sentinel-bucket extension (gotcha #25 extension) | **FALSIFIED** | All 14 candidates have `bucket='watch'` with 18 candidate_criteria rows; `notes=NULL`; not sentinel. Option A filter at `sweep.py:545-561` would have skipped them if they were. |
| H5: OHLCV history depth threshold | **FALSIFIED** | All 14 V2 reads return 1240-1256 bars; >> 200 minimum. |
| **H6 (NEW): OHLCV archive bar-content mutation** | **CONFIRMED ROOT CAUSE** | Decisive reproducer matches V2 smoke exactly; per-criterion bar-value diffs (cons_avg, adr) confirm bar-level mutation; `write_window` `keep="last"` semantics confirm overwrite mechanism. |

---

## Section 3 Per-binding-variable study impact assessment (BINDING per dispatch brief Section 5)

**Drift class identification:** L4-style (data-input divergence; V2 evaluator correct).

**Per-binding-variable verdict:**

| Variable | Headline max_delta_aplus | Drift impact on delta_aplus | Verdict |
|---|---|---|---|
| `vcp.tightness_range_factor` | +75 at sweep=1.005 | 0 (14 candidates flip skip->watch, NOT skip->aplus) | **STRONGLY ROBUST** |
| `vcp.tightness_days_required` | +16 at sweep=1 | 0 (same logic) | **STRONGLY ROBUST** |
| `vcp.adr_min_pct` | +11 at sweep=2.0 | 0 (drift candidates contribute to delta_watch, NOT delta_aplus) | **MARGINALLY ROBUST** (+11 holds) |
| `vcp.proximity_max_pct` | +5 at sweep=7.5 | 0 (drift candidates' proximity is pass for most; not aplus-flipping) | **MARGINALLY ROBUST** (+5 holds) |
| `vcp.orderliness_max_bar_ratio` | +1 at sweep=3.75 | 0 (orderliness loosening doesn't flip multi-fail candidates to aplus) | **MARGINALLY ROBUST** (+1 holds) |

**Headline finding for study writeup:** The conservative worst-case +/-14 shift assumed in dispatch brief Section 5 does NOT materialize for `delta_aplus`. The 14 drift candidates are NOT aplus-eligible at any sweep_point (they have multiple vcp_fails; aplus requires 0 fails). All 5 binding-variable identifications REMAIN VALID. **Operator can proceed with confidence that the binding-variable list is correct under V2 sensitivity analysis.**

**Study publication recommendation:** PUBLISH with caveat language (see findings Section 5.4).

---

## Section 4 Remediation recommendation

**OPTION A (RECOMMENDED): characterize as L6 limitation; do nothing in V1.**

Rationale: drift is non-blocking for the sensitivity-analysis goal; V2 evaluator is correct; binding variables are robust. The drift is a structural property of the archive design (yfinance retroactive bar mutation + `write_window` keep-last semantics) -- not a V2 bug.

Operator-paired follow-up steps (separate housekeeping bundle, NOT this investigation branch):

1. Append L6 entry to `research/method-records/aplus-criteria-calibration.md` (v0.2.1 -> v0.2.2 patch bump). Draft text in findings Section 6.1.
2. Append cumulative gotcha #26 to CLAUDE.md (paired with L6). Draft text in findings Section 7.4.
3. Append caveat to study writeup at `research/studies/2026-05-23-v2-ohlcv-criterion-evaluator.md`. Draft text in findings Section 5.4.
4. Re-interpret OQ-8 promotion gate condition 1 to "baseline parity green WITH characterized non-V2-bug root cause for residual drift." This condition is satisfied; promotion can proceed.

**OPTION B (FUTURE V2 candidate):** immutable archive snapshot architecture. Not recommended for V1; banked for V2 dispatch.

**OPTION C (NOT RECOMMENDED):** pre-V2 invocation OHLCV refresh. Doesn't close V1-vs-V2 drift; not useful.

---

## Section 5 V1 evaluator correctness audit

**V1 production code path:** ZERO changes. The 14 drift candidates were correctly evaluated by V1's `evaluate_one` at original eval_run time. V1's persisted candidate_criteria reflect the canonical truth for that snapshot.

**V2 evaluator code path:** ZERO bugs identified. The decisive counter-test (reproducer at `tmp/full-reproduction-investigation/reproducer.py`) reproduces V2's smoke bucket EXACTLY for all 14 candidates against the current archive. V2 is correct given its inputs.

**Production archive `write_window` semantics:** correct for production (latest-known yfinance value should win for live-trading purposes). Do NOT modify.

---

## Section 6 Cumulative discipline streaks preserved

- **ZERO Co-Authored-By footer** -- the 2 commits this investigation will produce (findings doc + return report) preserve the ~503+ cumulative streak through dispatch-brief commit `83409f0`.
- **L2 LOCK BINDING** -- ZERO Schwab API calls; ZERO V2-code reads of `*.schwab_api.parquet`. PL has `*.schwab_api.parquet` on disk but the V2 reader code path at `ohlcv_reader.py:88-93` never opens it (verified). Investigation's filesystem `stat` is OK per dispatch brief Section 4.4.
- **Schema v21 LOCKED** -- no migrations touched.
- **V1 persisted state READ-ONLY** -- ZERO modifications to `candidates`, `candidate_criteria`, `evaluation_runs`, `trades`, `reconciliation_*` rows.
- **Production swing/ READ-ONLY** -- `git diff main -- swing/` will remain EMPTY post-merge. Investigation read `swing/evaluation/`, `swing/pipeline/`, `swing/data/ohlcv_archive.py` but made ZERO changes.
- **ASCII-only on narrative text** -- this report + findings doc are ASCII-clean per Windows cp1252 stdout discipline.

---

## Section 7 Files produced

| Path | Purpose | Tracked? |
|---|---|---|
| `docs/v2-full-reproduction-drift-investigation-2026-05-24.md` | Investigation findings (11 sections; per-hypothesis evidence; root cause; remediation; study impact) | YES |
| `docs/v2-full-reproduction-drift-investigation-return-report.md` (THIS FILE) | Cumulative-precedent return report | YES |
| `tmp/full-reproduction-investigation/reproducer.py` | V2 evaluate_one reproducer for 14 drift candidates | NO (tmp/) |
| `tmp/full-reproduction-investigation/reproducer-output.txt` | Captured per-candidate eval results + per-criterion diffs | NO (tmp/) |

---

## Section 8 Operator-paired next-step decision tree

1. **Merge this branch to main (no-ff)?** RECOMMENDED. The findings + return report are operator-facing diagnostic artifacts that need to be in main for traceability + future-reference.

2. **Author Option A housekeeping bundle?** RECOMMENDED. Adds L6 to method-record + gotcha #26 to CLAUDE.md + caveat to study writeup. Small bundle (3 files); separate dispatch OR fold into existing housekeeping sequence (operator preference).

3. **Re-interpret OQ-8 gate condition 1?** OPERATOR DECISION. Strict interpretation forces option B (immutable snapshot architecture) which is heavy V2 work. Relaxed interpretation accepts characterized residual drift. Recommendation: relaxed (Option A path) for V1.

4. **Decide on next research-branch arc:**
   - **Path B-1:** cfg-policy method-record (if binding-variable thresholds identified per study writeup)
   - **Path B-2:** pivot to market-conditions / other-gates-not-enumerated per spec SectionB.3
   - **Path B-3:** Phase 14 commissioning per V2.1 SectionVII.B
   - **Path B-4:** V2 dispatch for immutable archive snapshot architecture (defers Path B-1/2/3)

   The binding-variable analysis (per Section 3 here) supports Path B-1 (binding thresholds identified; cfg-policy work is unblocked). Path B-2/3 are alternatives if operator wants to defer cfg-policy.

5. **OQ-8 promotion gate firing?** Once L6 is appended + caveat published + operator-paired relaxed interpretation locked, condition 1 is satisfied. Condition 3 (binding variables) is already satisfied per Section 3. Condition 2 (per OQ-8 ladder) operator-paired.

---

## Section 9 Pre-investigation context (preserved for orchestrator-side audit)

- 14 drift entries: CNTA:42-43, ECVT:40, APLS:34/38/39, FTI:31-32, STNG:19-21, PL:6-8.
- 6 unique tickers; 9 unique (ticker, asof_date) pairs; eval_runs 6-43.
- Tier-2 clean (120 match / 0 mismatch).
- Truncation: NONE (full 63 eval_runs processed; runtime 5172s under 90-min cap).
- Universe + hash: 516 universe size; v2_universe_hash matches prior smokes.
- L5 / Option A filter active at `sweep.py:545-561` (verified).
- 5 binding variables identified (all VCP-family; max_delta_aplus 1 to 75).

---

## Section 10 Cumulative gotcha banking

**NEW gotcha #26 candidate** (banked for future CLAUDE.md amendment in Option A housekeeping bundle):

> **OHLCV archive bar-content mutation invalidates V1-vs-V2 baseline-parity at the criterion level.** When V1's evaluator persists per-criterion results to the DB AND the underlying OHLCV archive is mutable (e.g., `swing/data/ohlcv_archive.py:write_window:358-360` uses `drop_duplicates(subset=["asof_date"], keep="last")` semantics so new yfinance fetches OVERWRITE existing bars), V1's persisted state diverges from V2's re-evaluation over time. Boundary candidates (criterion at pass/fail margin within ~2-3% of bar-value drift magnitude) flip bucket between V1 and V2. The drift is NOT a V2 evaluator bug; it is a structural property of the production archive design. Direct evidence: full-63-eval-run V2 smoke 2026-05-24 produced 14 baseline-parity FAILs (CNTA/ECVT/APLS/FTI/STNG/PL x eval_runs 6-43; investigation at `docs/v2-full-reproduction-drift-investigation-2026-05-24.md`). Pre-empt in any future harness comparing persisted state to live re-evaluation: writing-plans/brainstorming Section 5 watch item -- enumerate (a) data-input mutability surface; (b) production write-path overwrite semantics; (c) boundary-candidate criteria; (d) remediation tier (characterize as limitation, immutable snapshot, or per-eval replay). Pattern complement to existing #24 (parallel-archive freshness desync) + #25 (sentinel-bucket parity-comparison) -- same family extended from CROSS-archive desync to WITHIN-archive temporal mutation.

**NEW Limitation L6 candidate** (banked for future method-record amendment in Option A housekeeping):

> **Limitation L6: OHLCV archive bar-content mutation between V1 eval_run time and V2 read time.** Same content as gotcha #26 with method-record framing; full text drafted in findings Section 6.1.

---

## Section 11 C.C lesson #6 validation (this investigation)

**Pre-Codex applied (NONE -- investigation is diagnostic-only; no code changes shipped):**
- Investigation produced ZERO production code changes.
- Investigation produced ZERO research/harness/ code changes.
- Investigation produced ZERO V2 evaluator changes.
- Investigation produced ZERO test changes.
- Investigation produced 2 markdown docs (findings + return report) + 1 tmp/ reproducer script (NOT tracked).

**Adversarial Codex review:** NOT INVOKED. Per dispatch brief Section 0 + workflow note ("Adversarial Codex MCP review OPTIONAL -- invoke only if proposed code changes land beyond investigation surface"), the diagnostic-only scope does not warrant Codex invocation.

**Cumulative C.C lesson #6 validation status:** 35th cumulative validation banked as **DIAGNOSTIC-ONLY / CODEX NOT INVOKED**. The investigation surfaces a NEW gotcha #26 candidate; the actual gotcha amendment happens in a separate housekeeping bundle (Option A) which would constitute the actual validation event.

---

## Section 12 Open verification artifacts for orchestrator QA

1. **Reproducer reproducibility:** the reproducer at `tmp/full-reproduction-investigation/reproducer.py` is runnable from worktree root via `python tmp/full-reproduction-investigation/reproducer.py`. Output is preserved at `reproducer-output.txt`. Operator can re-run to verify.

2. **Bar-by-bar diffs:** the PL Shape A vs legacy diff (`0/1236 differ` on common dates) was computed inline via the reproducer's secondary diff script. The conclusion is robust.

3. **SQL evidence:** all 14 drift candidates' `bucket`, `rs_method`, `rs_rank`, `notes`, `candidate_criteria` rows are verifiable via direct SQL on `%USERPROFILE%/swing-data/swing.db`. Read-only queries; no DB mutation.

4. **Cache file inventory:** the 6 tickers' archive presence/mtimes are verifiable via `ls -la %USERPROFILE%/swing-data/prices-cache/{T}.{parquet,yfinance.parquet,schwab_api.parquet}` for each T in {CNTA, ECVT, APLS, FTI, STNG, PL}.

5. **L2 LOCK preservation verifiable** via: (a) grepping V2 reader code for `schwab_api` (zero matches); (b) reproducer source review (the reproducer's `read_yfinance_shape_a_sliced` invocation only opens Shape A / legacy paths, never schwab_api).

---

*End of V2 OHLCV full-63-eval-run reproduction CRITERION DRIFT investigation return report.*

*Root cause identified with code:line citation + decisive counter-test reproducer for all 14 candidates; all 5 narrowed hypotheses (H1-H5) FALSIFIED; H6 (NEW: OHLCV archive bar-content mutation) CONFIRMED as canonical root cause; remediation Option A (L6 limitation characterization) RECOMMENDED; per-binding-variable study-impact analysis confirms all 5 binding variables ROBUST under the L4-style drift class; operator-paired Option A housekeeping bundle banked for follow-up; ZERO production code changes; ZERO Co-Authored-By footer; L2 LOCK preserved; schema v21 LOCKED.*
