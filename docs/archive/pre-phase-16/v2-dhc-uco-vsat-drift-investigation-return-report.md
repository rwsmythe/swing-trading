# V2 OHLCV DHC/UCO/VSAT x eval_runs 60-64 CRITERION DRIFT Investigation -- Return Report

**Investigation date:** 2026-05-24
**Branch:** `applied-research-v2-dhc-uco-vsat-drift-triage`
**Dispatch brief:** `docs/v2-dhc-uco-vsat-drift-triage-dispatch-brief.md` (main HEAD `970ce80`)
**Findings doc:** `docs/v2-dhc-uco-vsat-drift-investigation-2026-05-24.md`
**Outcome:** Root cause identified + scope characterized + remediation locked + V2 candidate banked. Diagnostic-only investigation; ZERO code changes shipped.

---

## Section 1 -- Outcome summary

- **Root cause class:** V2 HARNESS FALSE-POSITIVE (NOT V1 bug; NOT V2 evaluator bug; NOT V2 reader bug; NOT architectural data desync).
- **Mechanism:** V1 production `swing/pipeline/runner.py:1105-1141` short-circuits criterion evaluation for two excluded-ticker classes (open positions + ETF blocklist); appends `Candidate(bucket='excluded', criteria=(), ...)` directly. V2's `_compute_baseline_parity` at `research/harness/aplus_v2_ohlcv_evaluator/sweep.py:540-605` does NOT mirror the short-circuit + naively invokes `evaluate_one(ctx)`. `swing/evaluation/scoring.py:bucket_for` cannot return `'excluded'` (returns only `{'aplus', 'watch', 'skip'}`), so V2-recomputed bucket NEVER matches V1-persisted `'excluded'` for these candidates.
- **Surface trigger:** Codex R1.C1 fix (commit `624e3e1`, 2026-05-23) changed `classify_candidate_tier(persisted_risk_result=None) -> tier-1`. Pre-fix, excluded candidates (which have `risk_result=None` because their `candidate_criteria` row count is 0) were counted in tier-2 (informational); post-fix they land in tier-1 (BLOCKING).
- **Per-hypothesis verdict:** H1 (reader byte drift) RULED OUT; H2 (RS universe drift) RULED OUT (V1 has no RS rank for these candidates); H3 (slicing edge case) RULED OUT (V1 never sliced); H4 (BatchContext drift) RULED OUT (V1 never built one); **H5 (V2 harness-vs-V1-pre-evaluation-exclusion-pathway gap) CONFIRMED** as canonical root cause.
- **Decisive counter-test:** PASSED for DHC:60 + UCO:62 + VSAT:64. V2 reproducer produced `skip` / `watch` / `skip` respectively -- exactly matching the smoke artifact's drift signature for each ticker (smoke listed excluded->skip / excluded->watch / excluded->skip).
- **Drift-class scope:** SYSTEMIC across the open-position + ETF-blocklist populations, NOT ticker-specific. Full 63-eval-run reproduction would surface ~100-200 entries (linear in `|held_set ∪ etf_exclusion.manual_block|`).
- **Remediation:** Option A LOCKED -- 1-line filter in `_compute_baseline_parity` to skip `persisted_bucket='excluded'` candidates. Discriminating test + method-record Limitation L5 amendment outlined in findings Section 5.

---

## Section 2 -- Deliverables produced

| Artifact | Path | Lines | Purpose |
| --- | --- | --- | --- |
| Investigation findings doc | `docs/v2-dhc-uco-vsat-drift-investigation-2026-05-24.md` | 281 | Per-hypothesis evidence + root cause + scope + remediation + 5 forward-binding lessons |
| Return report (THIS FILE) | `docs/v2-dhc-uco-vsat-drift-investigation-return-report.md` | -- | Cumulative-precedent shape; investigation summary + verification |
| Reproducer | `tmp/dhc-uco-vsat-investigation/reproducer.py` | 161 | Discriminating reproducer for V2 evaluate_one on excluded candidates; output preserved in findings doc Section 1.5 evidence #5 |

No code changes shipped to swing/. No code changes shipped to research/. No schema migration. No V1 production code changes.

---

## Section 3 -- Verification self-checks

### Section 3.1 -- ruff check

```
$ ruff check swing/ research/ tests/research/
All checks passed!
```

No code changes shipped, so ruff is no-op for the worktree; verified clean state matches main.

### Section 3.2 -- schema unchanged

```
$ git diff main -- swing/data/migrations/
(empty)
```

Schema v21 LOCKED; ZERO migration files touched.

### Section 3.3 -- production swing/ read-only invariant

```
$ git diff main -- swing/
(empty)
```

ZERO modifications to production swing/ code. The investigation read `swing/evaluation/scoring.py`, `swing/pipeline/runner.py`, `swing/evaluation/evaluator.py`, `swing/data/repos/candidates.py` (implied by Section 2 query path) but did not modify them.

### Section 3.4 -- V1 persisted state unchanged

```
$ python -c "
import sqlite3, os
db = os.path.join(os.environ['USERPROFILE'], 'swing-data', 'swing.db')
conn = sqlite3.connect(db)
# Confirm row counts match pre-investigation state
print('candidates row count:', conn.execute('SELECT COUNT(*) FROM candidates').fetchone()[0])
print('candidate_criteria row count:', conn.execute('SELECT COUNT(*) FROM candidate_criteria').fetchone()[0])
print('evaluation_runs row count:', conn.execute('SELECT COUNT(*) FROM evaluation_runs').fetchone()[0])
print('trades row count:', conn.execute('SELECT COUNT(*) FROM trades').fetchone()[0])
"
```

All read-only SELECT queries; no UPDATE / INSERT / DELETE on `candidates`, `candidate_criteria`, `evaluation_runs`, `trades`, `pipeline_runs`, `risk_policy`, or any other V1-persisted-state table.

### Section 3.5 -- ZERO Schwab API calls (L2 LOCK preserved)

The reproducer at `tmp/dhc-uco-vsat-investigation/reproducer.py` invokes only:
- `pd.read_parquet({T}.parquet)` (legacy fallback path; V2 reader honors L2 LOCK).
- `sqlite3.connect(db, mode='ro')` (read-only against operator's local DB).
- `Config.from_defaults()` + `cfg.paths.prices_cache_dir` (in-memory cfg load).

The diagnostic-only `{T}.schwab_api.parquet` file-existence check uses `Path.exists()` (filesystem-level read, NOT API call). V2 reader code (`research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py`) still preserves the L2 LOCK per the 5 BINDING discriminating tests at `tests/research/test_aplus_v2_ohlcv_reader.py` (4 file-open boundaries + module-import sentinel graph).

### Section 3.6 -- ZERO Co-Authored-By footer

```
$ git log applied-research-v2-dhc-uco-vsat-drift-triage --not main --format='%B' | grep -i 'co-authored-by' || echo "ZERO co-authored-by footer detected"
ZERO co-authored-by footer detected
```

Preserves the ~496+ cumulative streak through the dispatch-brief commit `970ce80`.

### Section 3.7 -- ASCII-only on narrative text

The findings doc + this return report are ASCII-clean per the Windows cp1252 stdout discipline (existing CLAUDE.md gotcha). All section headers use ASCII delimiters; no non-ASCII glyphs.

### Section 3.8 -- decisive counter-test reproduces smoke artifact signature

| ticker:eval_run | smoke artifact: V1 -> V2 | reproducer Section 4: V2 evaluate_one | match |
| --- | --- | --- | --- |
| DHC:60 | excluded -> skip | skip | YES |
| UCO:62 | excluded -> watch | watch | YES |
| VSAT:64 | excluded -> skip | skip | YES |

Reproducer also reads V1 `candidate_criteria` row count = 0 for all 15 affected candidates -- direct evidence V1 never ran criterion evaluation for these.

---

## Section 4 -- Handback to operator: root cause + per-criterion divergence + drift-class scope + remediation + V2 candidates banked

### Section 4.1 -- Root cause (1 sentence + code:line citation)

V2's `_compute_baseline_parity` at `research/harness/aplus_v2_ohlcv_evaluator/sweep.py:540-605` does NOT filter persisted `bucket='excluded'` candidates (open positions + ETF blocklist short-circuited at `swing/pipeline/runner.py:1105-1141`), so V2's `evaluate_one(ctx)` returns a `bucket_for(...)` output of `'skip'`/`'watch'`/`'aplus'` that NEVER matches V1's persisted `'excluded'`, producing systemic tier-1 baseline-parity false-positives.

### Section 4.2 -- Per-criterion divergence

NONE. V1 never evaluated criteria for these candidates (`candidate_criteria` row count = 0 for all 15 entries). The drift signature is BUCKET-LEVEL only:
- DHC:* and VSAT:* (open positions): V2 -> `skip` (TT passes 8/8 + VCP fails 3/9 -> skip via `bucket_for` "vcp_fails > 2 -> skip" branch).
- UCO:* (ETF blocklist): V2 -> `watch` (TT passes 8/8 + VCP fails 1/9 -> watch via "1 <= vcp_fails <= 2 -> watch" branch).

### Section 4.3 -- Drift-class scope

| Scope dimension | Finding |
| --- | --- |
| Same-eval_run | 3 tickers x 5 eval_runs = 15 entries in the 5-eval_run window |
| Same-ticker | DHC + VSAT systemic until trade closure; UCO systemic until ETF blocklist edit |
| Systemic | All `held_set ∪ etf_exclusion.manual_block` tickers in every eval_run |
| Full 63-eval-run extrapolation | ~100-200 entries (linear in held_set size + 63 eval_runs) |
| Ticker-specific? | NO -- CLASS-LEVEL defect |

### Section 4.4 -- Remediation recommendation (Option A LOCKED)

1. **Filter `persisted_bucket='excluded'` in `_compute_baseline_parity` inner loop** (1-line addition).
2. **Add discriminating test** at `tests/research/test_aplus_v2_ohlcv_sweep_excluded_filter.py` that plants 2 synthetic excluded candidates (open-position + blocklist) + 1 legitimate skip candidate; asserts tier-1 mismatch list is EMPTY for the excluded candidates + COUNT for the legitimate one.
3. **Method-record amendment** -- append Limitation L5 to `research/method-records/aplus-criteria-calibration.md` (v0.2.0 -> v0.2.1).
4. **Re-run V2 smoke after fix lands** -- expect `Tier-1 match: PASS` + `CRITERION DRIFT DETECTED` banner omitted.
5. **Optional Section 5.5 (banked V2 candidate):** also filter excluded candidates from per-variable drill-down + per-variable sweep iteration. Operator decision; default recommendation FILTER per architectural argument.

Estimated dispatch scope: 1 sub-bundle; ~5-10 commits; <1 day operator-paced. NO schema migration; NO production swing/ touches; NO V1 code changes.

### Section 4.5 -- V2 candidates banked from this investigation

1. **V2 baseline-parity filter for sentinel buckets** (Option A -- the immediate fix; primary V2 candidate).
2. **V2 per-variable drill-down filter for excluded candidates** (banked; operator decision; affects readability of the per-variable matrix but not correctness).
3. **V2 baseline-parity filter for `bucket='error'` candidates** (banked; same architectural argument as `'excluded'`; no current `error` candidates in eval_runs 60-64 but the failure mode is identical; include in the same fix as Option A).
4. **NEW cumulative CLAUDE.md gotcha #25 candidate** -- V2 baseline-parity comparison must filter persisted sentinel buckets that V1's pre-evaluation pathway produces (open-position + ETF-blocklist + error). Bank if Option A ships.

---

## Section 5 -- Cumulative gotcha banking (for orchestrator-side housekeeping post-merge)

### NEW gotcha #25 candidate

**Title:** V2 baseline-parity comparison must filter V1 pre-evaluation-excluded candidates (`bucket='excluded'` or `'error'`).

**Pattern:**
- V1 production has SHORT-CIRCUIT paths that write SENTINEL bucket values (`'excluded'`, `'error'`) the V2 evaluator architecturally cannot reproduce (`bucket_for` returns only `{aplus, watch, skip}`).
- V2 baseline-parity comparison naively invoking `evaluate_one` on every persisted candidate produces 100% false-positive drift on the SHORT-CIRCUITED populations.
- Codex R1.C1 `classify_candidate_tier(None) -> tier-1` inadvertently promotes these false-positives from tier-2 (informational) to tier-1 (BLOCKING).

**Pre-empt:** in any V1-vs-V2 baseline-parity harness, enumerate all persisted bucket values + identify which originate from `bucket_for(...)` (subject to parity comparison) vs which originate from pre-evaluation paths (must be filtered).

**Discriminating test:** plant 1 candidate per sentinel-bucket class (open-position, blocklist, error) + assert NONE are counted in tier-1 mismatch list.

**Forward-binding for:** V2 reader enhancements; any future V1-vs-V2 parity harness for criterion/scoring/bucket comparison; T4.SB sensitivity work that may inherit the same pattern.

**Direct evidence:** DHC/UCO/VSAT x eval_runs 60-64 investigation 2026-05-24 (this finding).

**Suggested CLAUDE.md location:** append to existing gotcha list following #24 (parallel-archive freshness desync from DK:62 investigation precedent).

---

## Section 6 -- Open questions for orchestrator-side QA

1. Merge investigation branch `--no-ff` to main per existing investigation-branch merge pattern (DK:62 precedent at `4afab36`).
2. Decision on whether to ship the Option A fix in a follow-on dispatch OR fold it into the next research-branch arc.
3. Decision on Section 5.5 banked V2 candidate (per-variable drill-down filter for excluded candidates).
4. Decision on whether the L4 + L5 method-record limitation entries ship together in a single v0.2.1 patch bump OR L4 alone first.

---

## Section 7 -- Forward-binding lessons enumerated

5 forward-binding lessons banked in findings doc Section 6:
1. V2 baseline-parity comparison must filter pre-evaluation-excluded candidates (lesson 1).
2. Tier-classification semantic gap on LEFT JOIN miss (lesson 2 -- complements Codex R1.C1).
3. Pre-evaluation exclusion is a V1 architectural feature, not an evaluator bug (lesson 3).
4. Cumulative gotcha #25 candidate (lesson 4 -- the codified pattern).
5. Predecessor-investigation prediction realized -- regenerating smoke after Codex fixes SURFACES new drift classes (lesson 5).

---

## Section 8 -- Streaks preserved

- ZERO Co-Authored-By footer streak: maintained through this investigation's commits (findings doc + return report + reproducer script). Approximately ~497+ cumulative commits depending on whether the findings + report + reproducer ship as 1 commit or 2 separate commits.
- L2 LOCK BINDING streak: preserved (no Schwab API calls; no V2 reads of `{T}.schwab_api.parquet`).
- Schema v21 LOCKED streak: preserved.
- V1 persisted state READ-ONLY streak: preserved.
- Production swing/ READ-ONLY streak: preserved (V2's existing OQ-17 carve-out in `swing/cli.py:+71` lines is unchanged).
- ASCII-only on narrative text: preserved.

---

*End of V2 OHLCV DHC/UCO/VSAT x eval_runs 60-64 CRITERION DRIFT investigation return report.*

*Investigation complete: root cause identified with code:line citations + decisive reproducer; all 4 narrowed hypotheses falsified; H5 (V2 harness-vs-V1-pre-evaluation-exclusion-pathway gap) confirmed; drift-class scope SYSTEMIC across open-position + ETF-blocklist populations; remediation Option A LOCKED for follow-on dispatch; 5 forward-binding lessons banked including NEW gotcha #25 candidate; ZERO production code changes; ZERO Co-Authored-By footer; L2 LOCK preserved; schema v21 LOCKED.*
