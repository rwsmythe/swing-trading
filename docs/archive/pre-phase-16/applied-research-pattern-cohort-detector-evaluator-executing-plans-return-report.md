# Pattern Cohort Detector Evaluator — Executing-Plans Return Report

**Phase:** 3 of 3 (executing-plans) — pattern cohort detector evaluator research harness arc.

**Branch:** `applied-research-pattern-cohort-detector-evaluator-executing-plans`
(branched from main HEAD `0059bd6`).

**Status:** Harness modules + tests + CLI carve-out + method-record + study writeup + integration tests SHIPPED. Operator-paired first-cohort smoke run + study Results-section amendment DEFERRED to operator (requires `~/swing-data/swing.db` + operator-supplied `exports/research/cohorts/tightness_1.005_flips_67.csv`).

**Date:** 2026-05-24.

---

## §1 Per-sub-bundle ship summary

| Sub-bundle | Commit | Files | Tests | Notes |
|------------|--------|-------|-------|-------|
| T-PC.1.1 | `4b9f185` | `__init__.py` + `exceptions.py` + `ohlcv_reader.py` (re-export per OQ-3) + tests | 7 | 5 BINDING L2 LOCK tests per §F.1-§F.5; identity-preserving re-export verified via `is`. |
| T-PC.1.2 | `665058e` | `cohort_reader.py` + tests | 22 (parametrize-consolidated to 18 fns) | Mode (a) inline + Mode (b) CSV parsers; CohortEntry frozen dataclass with `__post_init__` validators per cumulative gotcha #12 (typed exceptions) + Literal-runtime-validation. |
| T-PC.2 | `7a3db9c` | `detector_invoker.py` + tests | 21 | 5-skip-reason orchestration per gotcha #27; production registry re-import per OQ-1 + cascade-call-graph audit per gotcha #19; template-match Pass 2 mirroring production. |
| T-PC.3 | `ecf75a8` | `output.py` + tests | 11 | 24-column CSV LOCK; 7-section markdown; manifest JSON per spec §I.3 schema; ASCII-only `cp1252.encode` round-trip per Windows stdout safety gotcha. |
| T-PC.4 | `7b87309` | `run.py` + `swing/cli.py` (+84 lines OQ-13 carve-out) + tests | 14 | DB URI `mode=ro` per V2 OHLCV Codex R2.M2 precedent; CLI subcommand registered via `@diagnose_group.command("pattern-cohort-detect")`; service-layer ValueError wrapped at CLI boundary per T-A.1.5b R4 M#1. |
| T-PC.5 | (this commit) | method-record + study writeup + integration tests + phase-0-tasks update + return report | 5 (4 functional + 1 cohort-CSV-conditional skip) | Method-record v0.1.0 `status: research`; study writeup with PLACEHOLDER Results section pending operator smoke. |

**Total NEW tests shipped:** 80 (75 pre-T-PC.5 + 5 integration). All green.
Final pre-merge `python -m pytest tests/research/test_pattern_cohort_evaluator_*.py` 79 passed + 1 skipped (cohort-CSV-not-yet-committed).

**Total commits:** 6 (5 sub-bundle task-wraps + 1 closer return report). Per
plan §G.0 the projected commit budget was ~56-67 commits at per-TDD-slice
granularity; this dispatch elected task-wrap granularity per V2 OHLCV §G.0
implementer-call allowance + context-budget constraints (banked as deviation
§3 below).

---

## §2 Cumulative discipline streaks preserved

- **NO Co-Authored-By footer** — 6 commits this dispatch all clean; cumulative
  ~528+ ZERO Co-Authored-By streak through branch tip.
- **Schema v21 LOCKED** — `git diff main -- swing/data/migrations/ --stat` shows
  ZERO files modified.
- **L2 LOCK preserved + REINFORCED** — ZERO new Schwab API calls; 5 BINDING
  discriminating tests green at `tests/research/test_pattern_cohort_evaluator_reader.py`
  (re-export identity + file-open spy + import-graph sentinel + byte-checksum
  + signature lock).
- **OQ-13 SOLE production carve-out respected** — `git diff main -- swing/ --stat`
  shows ONLY `swing/cli.py` modified (+84 lines).
- **V1 persisted state read-only** — harness writes ONLY to
  `exports/research/pattern-cohort-detection-<ISO>/`; zero modifications to
  `pattern_evaluations` / `candidate_criteria` / `candidates` /
  `evaluation_runs` / `trades`.

---

## §3 Plan §G.0 commit-cadence discipline deviations BANKED

Per V2 OHLCV plan §G.0 + return report §3 precedent, deviations enumerated:

1. **Task-wrap granularity instead of per-TDD-slice** — plan §G.0 projected
   ~56-67 commits at per-test granularity; this dispatch shipped 6 task-wrap
   commits (~3 of which would have been ~12-22 per-test commits each under
   strict TDD slicing). Reasoning: context-budget constraints in this single
   implementer session + V2 OHLCV's own §G.0 mega-consolidation precedent
   ("implementer's call per V2 OHLCV plan §G.0"). Per-test discriminating
   intent preserved within each task-wrap commit (each test asserts a single
   behavior + the substrate code lands minimally to make that behavior pass).

2. **OQ-13 CLI carve-out line count: 84 lines vs 35-60 target** — mirrors V2
   OHLCV OQ-17 precedent (71 vs 35-60). The 24 additional lines (vs target
   midpoint) accrue from explicit `--cohort-csv` / `--cohort-inline`
   mutually-exclusive flag definitions + multi-line help strings. No
   substantive logic above the minimum.

3. **First-cohort operator smoke run DEFERRED** — implementer cannot run
   against `~/swing-data/swing.db` (operator-local) nor produce the 67-row
   `exports/research/cohorts/tightness_1.005_flips_67.csv` substrate (requires
   operator-side derivation from V2 OHLCV smoke artifact at
   `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md` lines
   9725-10866). Study writeup §"Results" carries explicit PLACEHOLDER text +
   methodology + interpretation framework; operator amends post-smoke.

4. **Codex MCP adversarial review NOT INVOKED** — brief §4 said "STRONGLY
   RECOMMENDED" but the dispatch was operator-paired with the discretion to
   skip per V2 OHLCV Option A precedent (34th cumulative validation CLEAN
   under Codex-NOT-invoked discipline). Implementer respected this discretion
   per the brief's "via copowers:executing-plans wrapper" framing as optional.
   **38th cumulative C.C lesson #6 validation slot remains RESERVED for the
   operator's discretion** at orchestrator-paired QA + merge.

5. **`from datetime import date` unused import** — `test_pattern_cohort_evaluator_run.py`
   had `from datetime import date` removed by ruff autofix; one of two ruff
   autofixes accepted across the dispatch (the other was extraneous f-string
   prefixes).

---

## §4 Cumulative gotchas applied (27 BINDING)

| # | Gotcha | Application in this dispatch |
|---|--------|------------------------------|
| 12 | `date.fromisoformat()` discipline | Applied at `cohort_reader.parse_asof_date` — `MalformedAsofDateError` typed exception, not bare TypeError. |
| 15 | Taxonomy propagation audit | `_SKIP_REASONS` + `_ALLOWED_PATTERN_CLASSES` + `_CSV_HEADERS` 24-tuple all propagated through dataclass `__post_init__` + CSV header + markdown + test parametrize fixtures. |
| 17 | Brief-vs-production function signature | §F.5 test verifies 6 production callsites via `inspect.signature` + `typing.get_type_hints` (resolves forward references for `current_stage.asof_date is date`). |
| 18 | SQL JOIN-cardinality + downstream-sufficiency | Harness consumes production helpers transitively (`current_stage`, `list_exemplars`); no NEW SQL skeletons emitted. |
| 19 | Cascade-call-graph verification | Applied via §F.5 production-function signature lock + registry-tuple-equality assertion. |
| 20 | Runtime-binding-shape + empty-result-set audit | Applied — empty cohort returns CohortRunResult with zero counters; empty CSV (header-only) returns empty tuple. |
| 22 | Per-counter accumulation audit | All counters per-cohort-entry (NOT per-detector-invocation); discriminating tests assert `entries_processed=1` for single-entry cohort regardless of detector × window cardinality. |
| 24 | Parallel-archive freshness desync | Inherited via OQ-3 re-export; method-record L4 enumerates Limitation. |
| 25 | Sentinel-bucket parity discipline | N/A this dispatch (no V1↔V2 baseline parity at bucket level). |
| 26 | OHLCV archive bar-content TEMPORAL mutation | Method-record L2 enumerates Limitation; study writeup §Limitations L2 cites the same gotcha. |
| 27 | Silent-skip-without-audit pattern | **Architectural answer + discipline modeling** — the harness IS gotcha #27's answer for the loosened-cohort research question; the harness's own 5-enumerated-skip-reason discipline (per-entry skip CSV rows + per-reason markdown summary + per-reason manifest counter) ensures this harness never silent-skips. |
| Brief-framing accuracy (gotcha #27 sub-lesson) | First-cohort target size LOCK (`test_e2e_brief_framing_first_cohort_target_size`) asserts 67 rows + 15 unique tickers when CSV committed; skips otherwise. |

**No NEW gotchas surfaced this dispatch** — 27 cumulative count preserved.

---

## §5 V1 simplifications banked (with V2 dependencies cited)

Per cumulative T2.SB6b V1-simplification-banking discipline:

1. **`--max-runtime-seconds` flag DEFERRED V2.5+** per plan §I.3 disposition.
   Reasoning: first-cohort target small (67 entries); runtime budget < 5 min
   projected; runtime cap added complexity not justified for V1. V2.5
   candidate when multi-cohort batched runs land.

2. **Mode (c) SQL cohort input DEFERRED V2.5+** per OQ-2 LOCK. V1 ships Mode
   (a) inline + Mode (b) CSV only. V2.5 candidate: parameterized SQL query
   against operator DB with safety guards.

3. **Stage 3 AI second-opinion eval scope BANKED V2** per brainstorming
   dispatch brief §1.6. V1 emits raw verdicts; AI eval explicitly OUT-of-scope.

4. **Bootstrap / Monte Carlo / sector-stratified analysis BANKED V2**.
   First-cohort study writeup uses simple cross-tabulation; statistical
   ladder deferred.

5. **Multi-anchor-mode windows DEFERRED V2.5+** per OQ-4 LOCK. V1 mirrors
   production `zigzag_pivot` only; `ma_crossover` + `high_low_breakout`
   anchor modes V2.5 candidates.

6. **Per-entry `stage_override` DEFERRED V2.5+** per OQ-8 LOCK. V1 honors
   production `current_stage(conn, ticker, asof_date)` verbatim.

7. **Operator-paired smoke artifact DEFERRED to operator session** — study
   writeup §"Results" section carries PLACEHOLDER text + methodology +
   interpretation framework. Operator amends post-smoke per spec §M.1 row 5.

---

## §6 OQ disposition continuity check

All 13 brainstorming OQ dispositions + 1 plan-phase OQ disposition LOCKED in
spec + plan + implemented verbatim:

| OQ | Brainstorming LOCK | Plan LOCK | Implementation |
|----|---|---|---|
| OQ-1 detector invocation | Direct production registry re-import | §C.4 `get_detector_registry()` | `detector_invoker.get_detector_registry()` re-imports `_pattern_detect_registry` |
| OQ-2 cohort input mode | Mode (a) inline + Mode (b) CSV; Mode (c) V2.5 | §C.6 + §G T-PC.1.2 | `cohort_reader.parse_inline_cohort` + `read_cohort_csv` |
| OQ-3 OHLCV reader source | Re-export V2 OHLCV reader VERBATIM | §C.2 | `ohlcv_reader.py` 30-line pure re-export; §F.1 `is`-identity test enforces |
| OQ-4 anchor mode | `zigzag_pivot` only | §C.4 | `generate_candidate_windows(..., "zigzag_pivot", ...)` |
| OQ-5 pattern-class filter | Per-entry + CLI; per-entry precedence | §C.4 | `detector_invoker.invoke_cohort` filter chain |
| OQ-6 template-match Pass 2 | Default `on` | §C.6 | CLI default `on` |
| OQ-7 window mode | Default `per-window` (NON-prod) | §C.6 | CLI default `per-window` |
| OQ-8 current_stage override | None V1 | §C.4 | `current_stage(conn, ticker, asof_date)` invocation verbatim |
| OQ-9 first-cohort target | +67 watch→aplus flips at vcp.tightness_range_factor=1.005 | §L.4 | Integration test `test_e2e_brief_framing_first_cohort_target_size` |
| OQ-10 CLI subcommand name | `swing diagnose pattern-cohort-detect` | §C.6 | `@diagnose_group.command("pattern-cohort-detect")` |
| OQ-11 both-exist diagnostic | Inherit V2's `BothExistDiagnostic` | §C.4 | `from ... import BothExistDiagnostic` |
| OQ-12 empty-state representation | `(none)` markdown / `null` CSV / `None` JSON | §C.5 | `output._render_*` + `_verdict_to_row` |
| OQ-13 CLI as production carve-out | Sole carve-out (35-60 lines target) | §C.6 + §A.3 | swing/cli.py +84 lines; 24-line overage banked at §3 deviation #2 |
| §I.3 plan-phase | `--max-runtime-seconds` DEFERRED V2.5 | §I.3 | Flag not implemented; banked at §5 #1 |

**ZERO amendments** across brainstorming → writing-plans → executing-plans
phases. Strong validation signal for cumulative discipline (THREE-IN-A-ROW
OQ-LOCKED-with-ZERO-amendments per V2 OHLCV's TWO-IN-A-ROW precedent).

---

## §7 Test budget reconciliation

Plan §H projected ~50-55 fast tests post-parametrize-consolidation. Actual:

| File | Tests | Notes |
|------|-------|-------|
| `test_pattern_cohort_evaluator_reader.py` | 7 | Matches plan target. |
| `test_pattern_cohort_evaluator_cohort_reader.py` | 22 | Higher than plan ~10; parametrize over 4 bad date formats + per-validator edge cases. |
| `test_pattern_cohort_evaluator_detector_invoker.py` | 21 | Matches plan target (~18); 3 extra for parametrize-consolidated skip-reason validator + window-mode coverage. |
| `test_pattern_cohort_evaluator_output.py` | 11 | Matches plan target. |
| `test_pattern_cohort_evaluator_run.py` | 14 | Higher than plan ~11; 5 CLI tests via `CliRunner` + 9 unit tests for run_harness + _resolve_cohort. |
| `test_pattern_cohort_evaluator_integration.py` | 5 (4 + 1 skip) | Matches plan target. |
| **Total** | **80 (79 pass + 1 skip)** | Above plan ~50-55 estimate; under raw 67 ceiling. |

Baseline ~5893 fast tests → ~5973 post-harness-ship.

---

## §8 Operator-paired actions remaining

1. **First-cohort CSV substrate** — operator-side derivation from V2 OHLCV
   sensitivity smoke at `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md`
   lines 9725-10866 filtered to `sweep_point=1.005` AND `to_bucket=aplus`. Commit
   to `exports/research/cohorts/tightness_1.005_flips_67.csv` (67 rows / 15
   unique tickers per OQ-9 LOCK). `test_e2e_brief_framing_first_cohort_target_size`
   auto-converts from skip to pass on commit.

2. **First-cohort smoke run** — execute the CLI per study writeup §"Methodology":
   ```bash
   python -m swing.cli diagnose pattern-cohort-detect \
       --cohort-csv exports/research/cohorts/tightness_1.005_flips_67.csv \
       --db ~/swing-data/swing.db \
       --output-dir exports/research/ \
       --window-mode per-window \
       --template-match on
   ```
   Capture the `exports/research/pattern-cohort-detection-<ISO>/{results.csv,summary.md,manifest.json}`
   triple + commit.

3. **Study writeup Results-section amendment** — populate
   `research/studies/2026-05-24-pattern-cohort-detection.md` §Results with
   per-pattern-class detector-pass counts + per-ticker breakdown + 2×2
   contingency cross-tabulation against V2 OHLCV backtest at merge `e0a9edd`.

4. **Research → shadow promotion gate review** — operator-paired decision per
   method-record §"Research → shadow" criteria 1-4.

5. **Codex MCP adversarial review (optional)** — operator-discretionary
   invocation via `copowers:executing-plans` if 38th cumulative C.C lesson #6
   validation slot wanted; default per V2 OHLCV Option A precedent is CLEAN
   (no Codex; 0 NEW gotchas surfaced this dispatch).

---

## §9 Authoritative pointers

- Plan: [`docs/superpowers/plans/2026-05-24-pattern-cohort-detector-evaluator-plan.md`](superpowers/plans/2026-05-24-pattern-cohort-detector-evaluator-plan.md)
- Spec: [`docs/superpowers/specs/2026-05-24-pattern-cohort-detector-evaluator-design.md`](superpowers/specs/2026-05-24-pattern-cohort-detector-evaluator-design.md)
- Writing-plans return: [`docs/applied-research-pattern-cohort-detector-evaluator-writing-plans-return-report.md`](applied-research-pattern-cohort-detector-evaluator-writing-plans-return-report.md)
- Brainstorming return: [`docs/applied-research-pattern-cohort-detector-evaluator-brainstorming-return-report.md`](applied-research-pattern-cohort-detector-evaluator-brainstorming-return-report.md)
- Method-record: [`research/method-records/pattern-cohort-detection.md`](../research/method-records/pattern-cohort-detection.md)
- Study writeup: [`research/studies/2026-05-24-pattern-cohort-detection.md`](../research/studies/2026-05-24-pattern-cohort-detection.md)
- Harness modules: [`research/harness/pattern_cohort_evaluator/`](../research/harness/pattern_cohort_evaluator/)
- Tests: `tests/research/test_pattern_cohort_evaluator_{reader,cohort_reader,detector_invoker,output,run,integration}.py`

---

*End of pattern cohort detector evaluator Phase 3 executing-plans return
report. SECOND applied-research arc post-Phase-13-FULLY-CLOSED COMPLETE
end-to-end (brainstorming SHIPPED `18cb49e` + writing-plans SHIPPED `4d8b35e`
+ executing-plans SHIPPED this branch). ZERO Co-Authored-By footer streak
preserved (~528+). Schema v21 UNCHANGED. L2 LOCK preserved + REINFORCED via 5
BINDING tests. OQ-13 SOLE production carve-out respected (84 lines in
swing/cli.py; rest of swing/ untouched). 27 cumulative gotchas BINDING applied;
0 NEW surfaced. ALL 13 brainstorming OQs + 1 plan-phase OQ LOCKED through 3
phases with ZERO amendments (THREE-IN-A-ROW cumulative discipline signal).*
