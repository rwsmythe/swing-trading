# Phase 13 `_step_pattern_detect` Silent No-Op Investigation - Findings

**Date:** 2026-05-24
**Investigator:** Implementer (dispatched per `docs/phase13-pattern-detect-step-silent-noop-triage-dispatch-brief.md`)
**Branch:** `applied-research-pattern-detect-step-silent-noop-triage`
**Worktree HEAD:** `eb48729` (main) at investigation start
**Skill:** `superpowers:systematic-debugging` (Phases 1-3 only; Phase 4 conditional on operator approval)

---

## TL;DR

**Root cause CONFIRMED.** `_step_pattern_detect` correctly hits the **empty-pool early-return** at [`swing/pipeline/runner.py:1485-1490`](../swing/pipeline/runner.py#L1485-L1490) on every post-ship pipeline run because **`bucket = 'aplus'` is empty in 100% (7/7) of pipeline runs since the step shipped 2026-05-20**.

- Brief's framing of "78 completed pipeline runs since Phase 13 T2.SB3 detector landed" is **inaccurate**: T2.SB3 pipeline integration shipped at commit `2300dd4` on **2026-05-20 08:01:24** (-1000). Only runs `72-78` (**7 runs**) are post-ship.
- All 7 post-ship runs have `evaluation_runs.aplus_count = 0`. The historical aplus-bearing runs (37 + 39, eval_run 31 + 32, both ticker `YOU` 2026-05-01 / 2026-05-04) predate the step by ~19 days.
- The step is **NOT broken**. Detector code is functional end-to-end (decisive counter-test below shows `BULZ` scoring `geometric_score=0.667` on `high_tight_flag` for eval_run 64).
- The "silent" framing is half-correct: the no-op IS visible via `log.info` (stderr) but is **invisible to DB inspection** (no `pipeline_runs.warnings_json` entry, no audit row, no `pattern_detect_status` column). **Zero of 78 runs have any `warnings_json` entry.** Confirmed contributing cause: **operational diagnostic gap (H5).**

**Disposition recommendation:** OPERATOR-PAIRED choice between (A) minimal warnings_json visibility patch (~10 lines; small operator-approved fix), (B) findings-only ship (defer fix), or (C) widen pool predicate to `bucket IN ('aplus', 'watch')` (architectural; non-trivial; separate dispatch). **Default recommendation: Option A.**

---

## 1. Hypothesis-by-hypothesis evidence summary

### 1.1 H1 - per-ticker exception swallowed: **FALSIFIED**

`_step_pattern_detect` has per-ticker try/except (bars fetch `runner.py:1604`, generate_candidate_windows `runner.py:1623`, per-detector invocation `runner.py:1676`) - but **the iteration loop is NEVER ENTERED** because `aplus_tickers` is empty (line 1485 early-return fires before line 1600). H1 cannot apply where there are no tickers to iterate.

### 1.2 H2 - config gate / feature flag disabled: **FALSIFIED**

No `cfg.X.enabled` guard exists in `_step_pattern_detect`. Source grep over `_step_pattern_detect` body confirms only one early-return condition: line 1485 `if not aplus_tickers`. No `cfg.pipeline.pattern_detect_enabled` or similar gate. Brief's H2 hypothesis fully falsified.

### 1.3 H3 - min-exemplars-per-class threshold not met: **FALSIFIED**

The template-matching gate at `runner.py:1922-1925` is `if bundles_for_class and tup_candidate_close.size > 0 and tup_geometric_score >= GEOMETRIC_SCORE_PREGATE_THRESHOLD` - this is a **soft gate** (skip template matching for that pattern; fall through to `compute_composite_score(geometric, None)` per L5 LOCK). Empty exemplar cohort does NOT prevent INSERT; it only nulls `template_match_score`. Current corpus sizes (filtered to `final_decision IN ('confirmed','watch')`): vcp=5, cup_with_handle=3, flat_base=1, high_tight_flag=3, double_bottom_w=3. All five classes have >= 1 usable exemplar, but even zero would not block detection. H3 falsified.

### 1.4 H4 - pattern_class CHECK enum mismatch: **FALSIFIED**

`_pattern_detect_registry()` at `runner.py:1297-1303` returns hardcoded literal pattern_class strings `('vcp', 'flat_base', 'cup_with_handle', 'high_tight_flag', 'double_bottom_w')` matching the schema CHECK at migration `0020_phase13_charts_patterns_autofill_usability.sql:230` (`pattern_class TEXT NOT NULL CHECK (pattern_class IN (...))`). No drift surface. The INSERT path is never reached anyway. H4 falsified.

### 1.5 H5 - outer-step exception swallowed with no audit: **CONFIRMED as CONTRIBUTING (not root cause)**

DB inspection across all 78 `pipeline_runs` shows `warnings_json` IS NULL in 78/78 rows; current_step = 'complete' in 78/78; no Phase 13 step writes to `warnings_json`. The outer-step `except Exception as exc: log.warning(...)` at `runner.py:850-853` produces stderr output ONLY - operator has zero DB-inspectable evidence of any step failure or silent skip. **This is the operational-gap that made the empty-pool no-op behavior invisible** until orchestrator-side Stage 2 reconnaissance queried `pattern_evaluations` directly and found it empty. **Contributing cause; remediation Option A addresses.**

### 1.6 H6 - detector OHLCV / min-bar-count: **FALSIFIED**

Direct invocation against 3 watch tickers (SATL, BKSY, BULZ) from eval_run=64 confirms bar-fetch + window-generation + 5 detector invocations succeed for all 3 tickers (276 bars each, 39-46 candidate windows). BULZ produced `high_tight_flag.geometric_score = 0.667`. Detector code is operational. H6 falsified.

### 1.7 H7 (NEW; not in brief enumeration) - pool predicate over-restricts: **CONFIRMED ROOT CAUSE**

The pool predicate at `runner.py:1481-1483` is `aplus_tickers = [c.ticker for c in candidates if c.bucket == 'aplus']`. Spec/recon LOCK at runner.py:1407 (docstring) binds this filter explicitly: "Pool predicate: candidates.bucket == 'aplus' (Stage-2 + RS-rank-filtered)."

Evidence across `evaluation_runs` cross-referenced with pipeline-runs that are eligible to invoke the step:

| Pipeline run ID | Eval run | Date | aplus | watch | skip | step ran? |
|----:|---:|:---|----:|----:|----:|:---|
| 72 | 58 | 2026-05-20 01:10 | **0** | 11 | 63 | early-return |
| 73 | 59 | 2026-05-20 15:58 | **0** | 10 | 51 | early-return |
| 74 | 60 | 2026-05-20 18:13 | **0** | 10 | 54 | early-return |
| 75 | 61 | 2026-05-21 07:39 | **0** | 11 | 51 | early-return |
| 76 | 62 | 2026-05-21 20:27 | **0** | 10 | 52 | early-return |
| 77 | 63 | 2026-05-22 05:52 | **0** | 12 | 62 | early-return |
| 78 | 64 | 2026-05-22 21:27 | **0** | 13 | 61 | early-return |

7/7 post-ship runs hit the early-return. Pattern_evaluations table is empty BY DESIGN given the current candidate distribution.

Historical context (pre-ship; for reference only):

| Pipeline run | Eval run | Date | aplus tickers | Pattern_detect available? |
|----:|---:|:---|:---|:---|
| 37 | 31 | 2026-05-01 16:06 | `[YOU]` | NO (step shipped 2026-05-20) |
| 39 | 32 | 2026-05-04 01:42 | `[YOU]` | NO (step shipped 2026-05-20) |

These are the **ONLY 2 of 78 historical runs that would have had any aplus tickers** to run detectors on, and both occurred ~19 days before T2.SB3 pipeline integration shipped. Pattern_evaluations was therefore correctly empty at all 78 runs.

---

## 2. Decisive counter-test results (per brief 1.7)

### 2.1 Reproducer 1 - direct invocation against eval_run_id=64

```
INVOKING _step_pattern_detect with DEBUG logging:

INFO swing.pipeline.runner: pattern_detect: no candidate windows -- zero aplus tickers; skipping (no writes)
COMPLETED WITHOUT EXCEPTION
```

Single INFO log; clean return; zero rows written. Matches the predicted code path exactly. No exception in any layer.

### 2.2 Reproducer 2 - bisect detector code path (read-only)

To distinguish "pool-predicate bug" from "detector code bug" per brief 1.7 ("If reproducer writes >= 1 row -> wiring bug; if 0 rows -> detector bug"), I invoked the 5 detectors directly against 3 randomly-selected watch tickers from eval_run=64 (read-only against current archive):

| Ticker | Bars | Windows | vcp | flat_base | cup_with_handle | high_tight_flag | double_bottom_w |
|:--|---:|---:|---:|---:|---:|---:|---:|
| SATL | 276 | 46 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| BKSY | 276 | 41 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| BULZ | 276 | 39 | 0.0 | 0.0 | 0.0 | **0.667** | 0.0 |

Detectors execute without exception across 15 (ticker, pattern_class) invocations. **BULZ scored 0.667 on high_tight_flag**, a positive evidence emit that would have been written to `pattern_evaluations` had BULZ been in `bucket = 'aplus'`. The detector code path is **fully functional**.

**Bisection conclusion:** root cause is upstream of detector code. It is the pool-predicate selectivity, not a detector defect, not a wiring defect, not a write-path defect.

---

## 3. Drift class characterization

| Dimension | Characterization |
|:--|:--|
| Failure shape | Empty-pool early-return (NOT exception swallow; NOT per-row failure) |
| Locus | `swing/pipeline/runner.py:1481-1490` (aplus filter + guard) |
| Trigger condition | `candidates.bucket = 'aplus'` row count = 0 for the bound eval_run |
| Failure scope | SYSTEMIC across all post-ship runs (7/7) |
| Detector code health | OPERATIONAL (confirmed via decisive counter-test 2.2) |
| Schema health | OPERATIONAL (no CHECK violation; INSERT path never reached) |
| Spec alignment | INTENTIONAL per recon lock at `runner.py:1407` docstring |
| Operational visibility | INVISIBLE to DB inspection (no warnings_json; no audit row; no status column) |
| Stderr visibility | VISIBLE via `log.info` (operator-facing if logs piped) |

The behavior is **operating per spec**. The "bug" is **not in code**; it is the **misalignment between pool predicate (V1 design) and current candidate distribution (aplus is rare to extinct under current finviz + criteria thresholds)**.

---

## 4. Operational-gap diagnostic findings

### 4.1 Silent-skip-without-audit pattern

The outer-step except clause at `runner.py:850-853` and the empty-pool early-return at `runner.py:1485-1490` both produce **only stderr log output**. No row is written to `pipeline_runs.warnings_json`; no `pattern_detect_status` column exists on `pipeline_runs` (would require schema change; v21 LOCKED); no `pipeline_step_audits` table exists.

Comparison with sibling Phase 13 steps:

| Step | Failure surface | Audit row written? |
|:--|:--|:--|
| `_step_pattern_detect` (Phase 13 T2.SB3) | log.info OR log.warning | NO |
| `_step_schwab_snapshot` (Phase 11) | log.warning + schwab_api_calls audit row | YES (audit) |
| `_step_schwab_orders` (Phase 11) | log.warning + schwab_api_calls audit row | YES (audit) |
| `_step_charts` (Phase 13 T1.SB0) | log.warning | NO |

`_step_pattern_detect` matches the `_step_charts` shape (silent skip on no-eligible-targets). Other Phase 13 steps follow the same pattern - they write to their own domain tables (pipeline_pattern_classifications, pipeline_chart_targets) but produce no `pipeline_runs`-level audit on skip.

The skip-without-audit pattern is **systemic** to several Phase 13 steps but the consequence is most visible at `_step_pattern_detect` because the operator's downstream research question depends on `pattern_evaluations` being populated. The discipline gap is a **new gotcha-class candidate** (banked at section 6 below).

### 4.2 Brief framing inaccuracy (orchestrator-side)

The brief's stated "78 completed pipeline runs since Phase 13 T2.SB3 detector landed" conflates "78 pipeline_runs total" with "runs since the step shipped". Only 7 runs post-date T2.SB3 (commit `2300dd4` 2026-05-20). Operator's Stage 2 reconnaissance was correct that `pattern_evaluations` is empty; the "78 runs that should have populated it" framing requires correction.

---

## 5. Remediation options

### 5.1 Option A (RECOMMENDED) - structured warnings_json entry on empty-pool skip

**Scope:** ~10-15 lines added to `_step_pattern_detect`. Append a structured JSON entry to `pipeline_runs.warnings_json` when the empty-aplus early-return fires. Mirrors the existing JSON-array shape convention.

**Sketch (subject to operator approval; NOT committed this dispatch):**

```python
# Inside _step_pattern_detect, replacing lines 1485-1490
if not aplus_tickers:
    log.info(
        "pattern_detect: no candidate windows -- zero aplus tickers; "
        "skipping (no writes)"
    )
    # Operational visibility: append structured marker to warnings_json
    # so operator can SELECT-detect the skip without grepping stderr.
    _append_step_warning(
        lease=lease, cfg=cfg,
        step_name="pattern_detect",
        warning={
            "kind": "empty_pool",
            "predicate": "bucket=='aplus'",
            "eval_run_id": eval_run_id,
            "aplus_count": 0,
            "watch_count": <count>,
            "skip_count": <count>,
        },
    )
    return
```

Plus a small helper `_append_step_warning(lease, cfg, step_name, warning)` that reads + appends + writes `pipeline_runs.warnings_json` under `lease.fenced_write()`. ~10-15 lines for the helper.

**Benefits:** operator can `SELECT id, warnings_json FROM pipeline_runs WHERE warnings_json LIKE '%pattern_detect%'` to see every skip; future investigations of "did detector run?" become a 1-query inspection; sets canonical pattern for other silent-skip steps to adopt.

**Risks:** ZERO behavioral change to detector logic; only adds a write to `pipeline_runs`. Schema unchanged (warnings_json column exists since Phase 1 baseline). TDD-compatible.

**Cumulative-discipline impact:** introduces a NEW write surface to `pipeline_runs.warnings_json`. Lease + transaction discipline must be respected - read/append/write must be inside `lease.fenced_write()` to preserve concurrency safety (Phase 7 transactional discipline family). Need 1 discriminating test.

**Operator-approval gate per brief 4.6:** YES, before merge.

### 5.2 Option B - findings-only ship (defer fix)

Ship this findings doc + return report; defer any code change to an operator-paired decision dispatch. The empty-pool behavior is correct per spec; operational visibility is a nice-to-have not a defect.

**Benefits:** zero production-code touch; lowest possible blast radius.
**Risks:** operator cannot SELECT-detect future skips; same hidden-skip class of finding may recur for other Phase 13 steps; the gotcha-class learning is captured but not enforced.

### 5.3 Option C - widen pool predicate to `bucket IN ('aplus', 'watch')`

**Scope:** 1-line change at `runner.py:1481-1483`. Architectural; touches the spec lock at runner.py:1407 docstring.

**Benefits:** detector would actually emit rows on current finviz+criteria distribution; operator's research question (detector confirmation rate on watch-bucket cohort) becomes directly answerable from `pattern_evaluations`.

**Risks:** changes V1 production behavior. Perf cost - watch is ~10-13 tickers per run vs 0 aplus; ~10x detector invocations per run. Spec-recon LOCK at runner.py:1407 + `docs/phase13-t2-sb3-recon.md` would need amendment. Pre-shipped feature flag would be the safer migration. **NOT RECOMMENDED** as part of this investigation dispatch; route to a Phase 13 closer dispatch with operator-paired scoping if pursued.

### 5.4 Option D - separate detector-confirmation harness for the cohort

The operator's actual research question ("do Phase 13 detectors over-filter the +75 cohort?") can be answered WITHOUT changing V1 production code via a parallel harness similar to `research/harness/aplus_v2_ohlcv_evaluator/` - read the cohort's (ticker, eval_run_id) tuples, fetch OHLCV at the eval_run's asof_date, invoke detectors directly, emit a study artifact. **NOT IN SCOPE** for this investigation dispatch; banked V2 candidate.

---

## 6. NEW gotcha-class candidate (BANKED for housekeeping)

**Silent-skip-without-audit pattern in pipeline steps.** When a pipeline step has a "no eligible work" early-return path (empty-pool guard; predicate-mismatch; sandbox short-circuit; or external-dep unreachable), the step MUST write a structured entry to `pipeline_runs.warnings_json` (or analog) so that operator-side `SELECT` inspection can detect the skip retroactively without grepping stderr logs. Pattern complement to the existing Phase 11 "Schwab API source-artifact reference shape locked" gotcha (which establishes that EVERY step write needs a queryable audit shape) and the Phase 8 "For any V1 single-operator form with hidden audit fields, default to SERVER-STAMPING" family (which establishes that operator visibility into POST-time behavior is non-negotiable). Same family extended from form-driven routes + write-bearing steps to **skip-bearing steps**: an INFO-level log to stderr is INVISIBLE to operator DB inspection; the operational diagnostic surface MUST include the skip as a first-class event.

Forward-binding: when authoring any future pipeline step that has a "no eligible work" predicate, the writing-plans phase MUST enumerate the skip-audit shape explicitly + add a discriminating test that asserts an empty-pool invocation writes a non-empty `warnings_json` entry. Sibling steps that already silent-skip (`_step_charts`, `_step_schwab_snapshot/orders` under client=None) may be retrofit-candidate V2.

Banked at this findings doc section 6 for the orchestrator-side housekeeping pass to promote into CLAUDE.md gotcha-cumulative #27 if operator concurs.

---

## 7. Forward-looking notes for operator + orchestrator

1. **Operator decision points:**
   - **Option A vs B vs C vs deferred** for the silent-no-op visibility fix
   - Whether to commission a separate detector-confirmation cohort harness (Option D) for the +75 cohort research question

2. **Research-question pathway** (if Option A chosen but Option D still desired):
   - V1 production stays empty on `pattern_evaluations` until aplus reappears OR the pool predicate is widened
   - The cohort question ("would detectors confirm watch-bucket candidates at composite >= 0.5?") needs a separate harness; the `tmp/stage2_detector_confirmation_query.py` orchestrator script attempts this but finds 0 rows because pattern_evaluations is empty
   - Closing the operator research question fully requires Option D harness work

3. **Cumulative discipline (if Option A chosen and Codex MCP review invoked):**
   - 26 CLAUDE.md cumulative gotchas (1-26) BINDING for the 37th cumulative C.C lesson #6 validation
   - Pre-Codex review must enumerate the lease + transaction discipline (Phase 7 family); the warnings_json read/append/write must be transactional inside `lease.fenced_write()`; discriminating test for concurrent-append safety
   - No new schema (v21 preserved); no Schwab API surface (L2 LOCK preserved); no V1 persisted-state mutation beyond `pipeline_runs.warnings_json`

---

## 8. Investigation evidence trail

All evidence-gathering scripts are inline in this document. Direct reproducer scripts are not committed (transient diagnostic queries); key results:

- DB query: 7/7 post-ship runs have `aplus = 0` (section 1.7 table)
- DB query: 0/78 runs have non-empty `warnings_json` (section 4.1)
- Decisive counter-test 1: direct `_step_pattern_detect(eval_run_id=64)` invocation produces exactly the predicted INFO log + clean return + 0 rows (section 2.1)
- Decisive counter-test 2: detectors invoked against 3 watch tickers produce 1 positive emit (BULZ high_tight_flag=0.667) + 14 zero-evidence emits across 15 invocations; zero exceptions (section 2.2)
- Git log: T2.SB3 pipeline integration shipped 2026-05-20 08:01:24 (commit `2300dd4`); 7 pipeline runs post-date this (section 1.7 table)
- Schema check: v21; pattern_evaluations 15 cols + 5-value pattern_class CHECK enum match detector registry literals (section 1.4)

---

## 9. Process compliance

- `superpowers:systematic-debugging` Phase 1 (root cause) + Phase 2 (pattern) + Phase 3 (hypothesis) COMPLETE
- Phase 4 (implementation) DEFERRED pending operator approval per brief 4.6
- 6 brief hypotheses (H1-H6) per brief 1.1-1.6 + 1 NEW hypothesis (H7) added per superpowers Phase 1.4 ("evidence-driven hypothesis expansion"); ALL 7 evaluated
- Decisive counter-test per brief 1.7 EXECUTED + RESULT REPORTED
- ASCII-only narrative per CLAUDE.md gotcha "Windows PowerShell stdout cp1252"
- V1 persisted state READ-ONLY (no writes to `candidates`, `evaluation_runs`, `pattern_evaluations`, `trades`, etc.)
- L2 LOCK preserved (no Schwab API surface touched)
- Schema v21 preserved (no migrations)
- ZERO Co-Authored-By footer commits made during this investigation (no commits made; awaiting operator approval before any production code change)

---

*End of investigation findings. Return report at `docs/phase13-pattern-detect-step-silent-noop-investigation-return-report.md`. Operator decision required on remediation options 5.1 (A), 5.2 (B), 5.3 (C), 5.4 (D) before any code change ships.*
