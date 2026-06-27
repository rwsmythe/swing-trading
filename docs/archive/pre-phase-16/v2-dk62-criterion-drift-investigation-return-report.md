# V2 OHLCV DK:62 CRITERION DRIFT Investigation — Implementer Return Report

**Branch:** `applied-research-v2-dk62-criterion-drift-triage`
**Investigation date:** 2026-05-23
**Dispatch brief:** `docs/v2-ohlcv-dk62-criterion-drift-triage-dispatch-brief.md` (HEAD `182aca9`)
**Findings document:** `docs/v2-dk62-criterion-drift-investigation-2026-05-23.md` (this dispatch)
**Workflow:** `superpowers:systematic-debugging` (forensic; diagnostic-only)
**Codex MCP adversarial review:** NOT invoked — no code changes shipped (dispatch brief §7 permits skipping when investigation is diagnostic-only).

---

## §1 Executive summary

DK:62 baseline-parity tier-1 FAIL is caused by **stale Shape A archive**: `DK.yfinance.parquet` is missing the 2026-05-21 boundary bar that the legacy `DK.parquet` contains. V1 evaluated DK at eval_run 62 using the boundary bar (close=42.10, the day DK dropped -5.7% intraday); V2 today reads the stale Shape A and evaluates using the prior-day frame (close=44.59). Two criterion results flip (`TT5_above_50` fail→pass; `proximity_20ma` fail→pass), promoting DK from `skip`→`watch`.

**Drift is ISOLATED to DK:62.** Only 3 both-exist tickers in cache (AESI/DK/PL); only DK has Shape A staleness; only one eval_run (62) lands on the missing-bar date. Other smoke drifts (DHC/UCO/VSAT excluded→skip/watch + tier-2 mismatches) have different mechanisms (V2 not replicating V1 pre-evaluation exclusion + OQ-15 current_equity surrogate respectively).

**Remediation Option D** (combined): refresh Shape A for both-exist tickers → re-run V2 smoke → verify parity → amend method-record limitations → bank V2 reader "prefer-fresher" enhancement.

---

## §2 Per-hypothesis verdict

| Hypothesis | Verdict | Decisive evidence |
| --- | --- | --- |
| H1: Criterion implementation drift | **FALSIFIED** | ZERO commits to `swing/evaluation/scoring.py` / `criteria/` / `evaluator.py` since eval_run 62 timestamp (2026-05-21 20:27). Counter-test: `evaluate_one` against legacy bars reproduces V1's persisted bucket + every criterion value EXACTLY. |
| H2: cfg drift | **FALSIFIED** | ZERO commits to `swing.config.toml`. The 2 commits to `swing/config.py` (dc86a4c + aafc3c7) are additive (new classmethod) / cosmetic (annotation forward-ref). Cfg values unchanged. |
| H3: Bug in V2 (reader / context_builder / cfg_substitution) | **PARTIALLY TRUE; characterized as architectural data-freshness desync, NOT V2 code bug** | V2 reader correctly reads Shape A per OQ-18 LOCK. The "bug" is the asymmetric refresh paths: legacy is refreshed by `read_or_fetch_archive` on every pipeline run; Shape A is refreshed only by `_backward_compat_rename` invoked at `resolve_ohlcv_window`. Result: legacy includes 2026-05-21 bar (mtime 20:28); Shape A is stuck at 2026-05-20 (mtime 07:39). |
| H4: V1 persisted state bug | **FALSIFIED** | `evaluation_runs` id=62 has `error_count=0`; DK candidate row + 18 `candidate_criteria` rows are complete + self-consistent; counter-test reproduces every persisted value exactly. |
| H5+: residual candidates | **NONE SURFACED** | Shape A archive corruption ruled out (zero cell-level diff across 59 common dates trailing 60 days). Criterion edge case ruled out (counter-test reproduces). Schema drift ruled out (v21 unchanged; zero migrations). |

---

## §3 Decisive evidence (root cause)

```
DK.parquet (legacy):        mtime 2026-05-21 20:28:04   last bar 2026-05-21
                            Open=45.24 High=45.41 Low=41.83 Close=42.10 Volume=1,096,600

DK.yfinance.parquet (A):    mtime 2026-05-21 07:39:42   last bar 2026-05-20
                            Open=45.28 High=46.02 Low=43.88 Close=44.59 Volume=727,473

eval_run 62 timeline:       run_ts 2026-05-21 20:27:02  data_asof 2026-05-21
                            V1 persisted bucket=skip; reads legacy (includes 2026-05-21 bar)
                            V2 today reads Shape A (missing 2026-05-21 bar); produces 'watch'

Counter-test (evaluate_one with LEGACY bars):  bucket='skip' (EXACTLY matches V1 persisted)
Forward-test (evaluate_one with SHAPE A bars): bucket='watch' (EXACTLY matches V2 smoke)
```

Specific criterion flips driven by the boundary bar:

| Criterion | V1 (with 2026-05-21 bar) | V2 (Shape A, last bar 2026-05-20) |
| --- | --- | --- |
| TT5_above_50 | **FAIL** (close=42.10 < 50MA=43.56) | **PASS** (close=44.59 > 50MA=43.55) |
| proximity_20ma | **FAIL** (-6.12%) | **PASS** (-0.31%) |
| All other criteria | (per `candidate_criteria` rows) | (Shape A: unchanged or NA where TT8 differs by batch context) |

VCP fail count drops from 3→2 AND TT non-allowed-miss check passes → bucket promoted skip→watch.

---

## §4 Drift scope

- **Same-eval_run scope (eval_run 62 across other tickers):** ONLY DK:62 flagged as tier-1 baseline-parity FAIL in smoke. DHC/UCO/VSAT drifts (excluded→skip/watch) are tier-1 by `classify_candidate_tier(None) -> 1` but reflect V1's PRE-EVALUATION exclusion (not OHLCV-staleness). They are a SEPARATE category and not blocking.
- **Same-ticker scope (DK across all eval_runs):** DK appears at eval_runs 25-30, 53-55, 59-62. Only eval_run 62 has `data_asof_date=2026-05-21` landing on the missing-bar date. Earlier asof_dates are within covered range; later eval_runs (63, 64) don't include DK.
- **Systemic scope (cache archetype inventory):** 3 both-exist tickers (AESI/DK/PL); 0 Shape-A-only; 822 legacy-only. Only DK has Shape A < legacy boundary. Legacy-only tickers fall through V2 reader to legacy frame (`ohlcv_reader.py:91-93`); no OHLCV-staleness drift possible for them.
- **Full 63-eval-run reproduction expectation:** DK:62 will remain the SOLE tier-1 baseline-parity FAIL UNTIL Shape A is refreshed for DK.

---

## §5 Commit chain

1. `docs(applied-research): V2 OHLCV DK:62 CRITERION DRIFT investigation findings + return report` (this commit; 2 doc files; ZERO production code changes; ZERO test changes)

No Codex review chain (investigation is diagnostic-only; no code changes shipped).

---

## §6 Verification at handback

| Check | Status | Evidence |
| --- | --- | --- |
| `git diff swing/` is EMPTY | ✓ PASS | No production code changes |
| Schema v21 LOCKED (no `swing/data/migrations/` touches) | ✓ PASS | No migration touches |
| ZERO new Schwab API calls | ✓ PASS | Investigation used existing parquet bytes only |
| ZERO reads of `{T}.schwab_api.parquet` | ✓ PASS | Only `DK.parquet` + `DK.yfinance.parquet` read |
| L2 LOCK preserved | ✓ PASS | No yfinance fetch; no Schwab API call; `read_yfinance_shape_a` invoked directly without `read_or_fetch_archive` |
| V1 persisted state UNCHANGED | ✓ PASS | All DB queries were SELECT-only |
| ZERO `Co-Authored-By` footer | ✓ PASS | This commit follows the ~494+ cumulative streak |
| ASCII-only on markdown narrative text | ✓ PASS | Both docs cp1252-encodable |
| `ruff check` clean | n/a | No Python file changes |
| Fast suite green | n/a | No code changes; no test changes |

---

## §7 Forward-binding lessons banked

Five lessons enumerated in findings doc §5; summary:

1. **Archive-freshness desync is architectural, not a code bug** — parallel-archive writer asymmetry creates freshness drift at boundary bars even when both files exist. Bank as cumulative CLAUDE.md gotcha #24 candidate.

2. **Counter-test by feeding the suspect reader the canonical-truth inputs** — the decisive evidence step is `evaluate_one(LEGACY_BARS)` reproducing V1's persisted result EXACTLY. Pre-empt: in any future V2-style baseline-parity investigation, the second step after git-log-checks is reproduction via canonical input.

3. **Smoke-artifact section interpretation needs spec taxonomy** — the 3x DK:62 count in CRITERION DRIFT is cosmetic; the per-variable drill-down anomalies (DK:62 at sweep_point=7) are likely from a pre-R3.M1/R4.M1 smoke artifact (the smoke was generated before the final Codex fixes landed). Verify on post-remediation re-run.

4. **CLAUDE.md gotcha #24 candidate** — parallel-archive freshness desync invalidates baseline-parity claims for V2-style readers consuming ONE of N parallel archive shapes. Banked with full failure mode + pre-empt enumeration in findings §5.4.

5. **Two-sided staleness wording (banner inversion)** — the smoke's OQ-18 both-exist banner copy presumes Shape A is canonical-fresh; reality under V1 is the OPPOSITE (legacy is canonical-fresh because production pipeline writes there). Documentation fix candidate for `research/harness/aplus_v2_ohlcv_evaluator/output.py:225-228`.

---

## §8 Cumulative C.C lesson #6 validation (34th)

This investigation was diagnostic-only; Codex review was not invoked. The pre-Codex 7-expansion + 5-candidate + 2-sub-refinement + 3-V2-executing-plans-sub-promotion (23 expansions cumulative) discipline was NOT applied as a Codex-prep step.

However, the investigation surfaced **two NEW expansion / lesson candidates**:

- **Expansion candidate (parallel-archive freshness desync audit)** — when a V2-style harness reads ONE of N parallel archive shapes, enumerate producers vs consumers per shape; if asymmetric, document the freshness-invariant precondition. Pre-empt in writing-plans + brainstorming §5. Lesson banked as new gotcha #24 (see findings §5.4).
- **Forward-binding lesson #6 for V2 research arc (counter-test-via-canonical-input)** — the decisive falsification step for parallel-archive drift is reproducing V1's exact persisted result by feeding the V2 reader V1's input directly. Bank for future V2 method-record amendments.

If a follow-up dispatch ships V2 reader fix (Option B at §4.4 of findings), Codex review SHOULD be invoked with these 2 new expansions BINDING.

---

## §9 Streaks preserved

- **ZERO `Co-Authored-By` footer**: ~494+ cumulative streak through this commit.
- **C.C lesson #6 cumulative**: 33rd validation NOTABLE (V2 OHLCV executing-plans); this investigation is the 34th attempt — but DIAGNOSTIC-ONLY (no Codex). Streak preserved at 33 NOTABLE; this dispatch is neither CLEAN nor NOTABLE; it's a forensic outcome that surfaced 2 new expansion candidates.
- **L2 LOCK BINDING**: 5 BINDING discriminating tests at `tests/research/test_aplus_v2_ohlcv_reader.py` unchanged + preserved by the investigation's no-code-change scope.
- **Schema v21 LOCKED**: no migrations.

---

## §10 Recommendation to orchestrator

After QA of this return report + findings document, orchestrator may proceed with one of three handback paths:

### Path A — Direct merge to main + operator-paired remediation (RECOMMENDED)

1. Orchestrator-side QA: verify findings document hypothesis-walks + drift-scope conclusions + remediation Option D rationale.
2. Merge `applied-research-v2-dk62-criterion-drift-triage` → `main` via `--no-ff`.
3. Post-merge housekeeping bundle: add cumulative gotcha #24 (parallel-archive freshness desync); update CLAUDE.md status-line.
4. Hand back to operator for Shape A refresh (findings §4.1) + V2 smoke re-run (findings §4.2).
5. After operator confirms parity restored, unblock the research → shadow promotion gate per OQ-8 ladder.

### Path B — Bundle method-record amendment with investigation

Add findings §4.3 method-record patch (V0.2.0 → V0.2.1) to this branch BEFORE merge. Operator-pair the limitations entry verbatim. Then proceed per Path A steps 2-5.

### Path C — Defer to V2-OHLCV-prefer-fresher dispatch

If operator wants the V2 reader enhancement (findings §4.4) to land BEFORE operator-paired full 63-eval-run reproduction, commission a NEW dispatch:

- Brief: `docs/v2-ohlcv-prefer-fresher-shape-a-reader-dispatch-brief.md`
- Scope: V2 reader reads BOTH files when present, picks fresher by mtime / `asof_date.max()` (mirroring `_backward_compat_rename` mtime-tiebreaker logic at `swing/data/ohlcv_archive.py:670-695`). Adds discriminating tests including a planted-stale-Shape-A regression test.
- Codex review BINDING with 23 cumulative expansions + 2 NEW from this investigation.

Recommended: Path A (lowest blast radius; operator-paired natural recovery; no additional dispatch overhead).

---

*End of return report. Investigation handback complete. Root cause identified; drift scope isolated; remediation Option D recommended; 5 forward-binding lessons banked + 1 new gotcha candidate enumerated. ZERO production code changes; ZERO Co-Authored-By footer; L2 LOCK preserved; schema v21 LOCKED.*
