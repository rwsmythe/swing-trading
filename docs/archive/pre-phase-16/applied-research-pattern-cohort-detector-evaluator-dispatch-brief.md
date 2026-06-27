# Pattern Cohort Detector Evaluator Research Harness — Dispatch Brief (Option D)

**Audience:** Fresh Claude Code instance dispatched as the pattern cohort detector evaluator research harness implementer. No prior conversation context.

**Mission:** Build a **V2-style research harness** that invokes Phase 13 chart-shape detectors (`vcp`, `flat_base`, `cup_with_handle`, `high_tight_flag`, `double_bottom_w`) against an **operator-specified cohort of candidates** — independent of the production pool predicate (`bucket == 'aplus'`). This is the architecturally correct answer to the operator's standing research question: *do Phase 13 pattern detectors filter loosened-A+ candidates productively?*

Per the predecessor `_step_pattern_detect` investigation (merge `54bd9c6`): the production detector by design only runs on aplus candidates → cannot test loosened-cohort detector performance via production pipeline. New harness mirrors the V2 OHLCV evaluator pattern at `research/harness/aplus_v2_ohlcv_evaluator/`.

**Workflow:** `superpowers:brainstorming` → `superpowers:writing-plans` → `superpowers:test-driven-development` (substantial scope; mirrors V2 OHLCV criterion-evaluator three-phase arc; brainstorming + plan + executing-plans). Operator may choose to use `copowers:*` wrappers for adversarial review per the V2 OHLCV precedent.

**Branch:** Per V2 OHLCV arc precedent: 3 branches (`-brainstorm` → `-writing-plans` → `-executing-plans`).
- Phase 1: `applied-research-pattern-cohort-detector-evaluator-brainstorm`
- Phase 2: `applied-research-pattern-cohort-detector-evaluator-writing-plans`
- Phase 3: `applied-research-pattern-cohort-detector-evaluator-executing-plans`

All branches from main HEAD `e374974` (or later).

**Worktrees:** Standard worktree pattern per phase (`.worktrees/<branch>/`). Invoke `python -m swing.cli` (NOT bare `swing`).

**Expected duration:** Substantial. Mirror V2 OHLCV evaluator timing: brainstorming ~3-5h + writing-plans ~5-8h + executing-plans ~10-15h. Total ~18-28h operator-paced across the 3 phases.

---

## §0 Read first (per phase; brainstorming consumes ALL)

1. **`docs/phase13-pattern-detect-step-silent-noop-investigation-2026-05-24.md`** — predecessor investigation §6 Option D banked candidate; architectural insight that motivates this harness.
2. **`research/harness/aplus_v2_ohlcv_evaluator/`** — full V2 OHLCV evaluator harness (7 modules: `exceptions.py`, `ohlcv_reader.py`, `cfg_substitution.py`, `context_builder.py`, `sweep.py`, `output.py`, `run.py`). THIS IS THE STRUCTURAL TEMPLATE.
3. **`research/method-records/aplus-criteria-calibration.md`** v0.3.0 SHADOW — method-record structure precedent for the pattern-cohort harness method-record.
4. **`research/studies/2026-05-23-v2-ohlcv-criterion-evaluator.md`** — study writeup template.
5. **`swing/patterns/`** — individual Phase 13 detector modules. Walk each detector's input/output contract.
6. **`swing/pipeline/runner.py:1396-1490`** — `_step_pattern_detect` implementation (especially `_pattern_detect_registry` + the pool-predicate gate). Production reference for the cohort-evaluator's detector invocation path.
7. **`swing/data/migrations/0020_phase13_charts_patterns_autofill_usability.sql`** — `pattern_evaluations` schema (do NOT use this table for harness output; reserve for production).
8. **`docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md`** — V2 OHLCV evaluator spec. STRUCTURAL TEMPLATE for the brainstorming-phase spec authoring.
9. **CLAUDE.md gotchas** — especially #19 (cascade-call-graph verification), #20 (runtime-binding-shape + empty-result-set), #21-23 (Phase 13 cumulative regression cascade family), #24-26 (V1↔V2 parity discipline family), #27 (silent-skip-without-audit; this harness's existence is gotcha #27's architectural answer).

---

## §1 Architectural scope (brainstorming spec target)

### §1.1 Mirror V2 OHLCV evaluator structural template

NEW research module at `research/harness/pattern_cohort_evaluator/`:

```
research/harness/pattern_cohort_evaluator/
    __init__.py
    exceptions.py             # PatternCohortEvaluatorError + sub-classes
    cohort_reader.py          # Read operator-specified cohort (CSV / JSON / SQL query)
    ohlcv_reader.py           # Read OHLCV bars per candidate; mirror V2 evaluator's L2 LOCK
    detector_invoker.py       # Wrap swing/patterns/* detectors with cohort-iteration shell
    output.py                 # Emit results CSV + markdown summary
    run.py                    # CLI entry point + orchestration
```

### §1.2 Cohort input format (OQ for brainstorming)

Operator specifies a cohort via one of:
- **(a) Inline tuple list** in cfg / CLI args (small cohorts; <100 entries)
- **(b) CSV input** at operator-supplied path (large cohorts; analytical workflow)
- **(c) SQL query** against `candidates` / `candidate_criteria` (programmatic; e.g., "all candidates that flip to aplus at vcp.tightness_range_factor=1.005")

V1 recommendation per V2 OHLCV precedent: support (b) as primary + (a) as smoke-test fallback. (c) deferred to V2.5/V3.

### §1.3 Detector invocation independent of pool predicate

For each (ticker, asof_date) in cohort:
1. Read OHLCV bars (V2 evaluator L2 LOCK preserved: reads from `~/swing-data/prices_cache/` legacy parquet only; ZERO Schwab API).
2. Invoke ALL 5 Phase 13 detectors at asof_date (per `_pattern_detect_registry` shape).
3. Capture per-detector verdict: composite_score, geometric_score, template_match_score, structural_evidence, window_start/end.
4. Write per-(ticker, asof_date, detector) row to results CSV.

Output is operator-facing (exports/research/), NOT pattern_evaluations table (which is production-only).

### §1.4 L2 LOCK preservation (binding)

Mirror V2 OHLCV evaluator's 5 BINDING L2 LOCK discriminating tests at `tests/research/test_aplus_v2_ohlcv_reader.py`. Equivalent tests at `tests/research/test_pattern_cohort_evaluator_reader.py`:
- 4 file-open boundaries (`pd.read_parquet`, `pathlib.Path.open`, `builtins.open`, `pyarrow.parquet.read_table`)
- 4-module import sentinel graph (`yfinance`, `schwabdev`, `swing.integrations.schwab`, `swing.data.ohlcv_archive`)
- Byte-checksum + signature lock + source-grep tests

### §1.5 First-cohort target

V1 ship target = invoke harness against the +67 watch→aplus flips at `vcp.tightness_range_factor=1.005` cohort (per backtest study). Produces detector verdicts on the loosened-A+ cohort. Operator can then cross-tabulate detector-pass vs backtest-trigger vs (eventually) winners.

### §1.6 Banked V2 candidates (NON-scope for this dispatch)

- Cohort-input mode (c) SQL query
- Stage 3 AI second-opinion eval on winners-without-detection cell (per operator's earlier methodology proposal; gated on harness producing data + backtest producing winners)
- Production-pipeline backfill via this harness (separate operational dispatch)
- Bootstrap / Monte Carlo statistical confidence intervals
- Cohort-stratified analysis (sector / market-cap / regime)

---

## §2 Three-phase dispatch sequence (mirror V2 OHLCV precedent)

### §2.1 Phase 1: brainstorming

- Author spec at `docs/superpowers/specs/2026-MM-DD-pattern-cohort-detector-evaluator-design.md` per `superpowers:brainstorming` skill.
- Spec sections per V2 OHLCV precedent (`docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md`): §A scope + §B file map + §C architecture + §D OHLCV semantics + §E baseline parity + §F discriminating tests + §G commit cadence + §H test budget + §I integration points + §J open questions + §K method-record extension + §L study writeup + §M dispatch + §N self-review.
- Spec MUST address all V2 OHLCV evaluator design decisions adapted to detector context (cfg substitution NOT needed — detectors don't have configurable thresholds in same way; replace §D cfg-substitution with §D detector-invocation-shell).
- 5 narrowed hypothesis equivalent: open questions for operator-paired triage at Turn D.
- Adversarial Codex MCP review per `copowers:brainstorming` wrapper if operator chooses.

### §2.2 Phase 2: writing-plans

- Author plan at `docs/superpowers/plans/2026-MM-DD-pattern-cohort-detector-evaluator-plan.md` per `superpowers:writing-plans` skill.
- Plan sections per V2 OHLCV precedent (`docs/superpowers/plans/2026-05-23-v2-ohlcv-criterion-evaluator-plan.md`): file map + dependency graph + commit cadence preface + test budget + per-task TDD slices.
- Plan §G.0 commit cadence per V2 OHLCV precedent: ~30-50 commits depending on parametrize consolidation.
- Adversarial Codex MCP review per `copowers:writing-plans` wrapper if operator chooses.

### §2.3 Phase 3: executing-plans

- Ship modules per plan; TDD discipline; per-task slice commits.
- Adversarial Codex MCP review per `copowers:executing-plans` wrapper if operator chooses.
- Return report at `docs/applied-research-pattern-cohort-detector-evaluator-executing-plans-return-report.md`.

---

## §3 Deliverables (across 3 phases)

### Phase 1 brainstorming
1. Spec at `docs/superpowers/specs/2026-MM-DD-pattern-cohort-detector-evaluator-design.md`
2. Return report at `docs/applied-research-pattern-cohort-detector-evaluator-brainstorming-return-report.md`
3. Open questions enumerated for operator-paired triage at Turn D

### Phase 2 writing-plans
1. Plan at `docs/superpowers/plans/2026-MM-DD-pattern-cohort-detector-evaluator-plan.md`
2. Return report at `docs/applied-research-pattern-cohort-detector-evaluator-writing-plans-return-report.md`
3. All operator-paired OQ dispositions locked

### Phase 3 executing-plans
1. NEW research module at `research/harness/pattern_cohort_evaluator/` (estimated 5-7 modules per §1.1)
2. Fast tests at `tests/research/test_pattern_cohort_evaluator_*.py` (estimated ~50-80 tests; mirror V2 OHLCV's 115 tests)
3. CLI subcommand at `swing/cli.py` per OQ-17 carve-out precedent (the SOLE production-swing/ write per phase; ~35-60 lines)
4. NEW method-record at `research/method-records/pattern-cohort-detection.md` (or equivalent)
5. First-cohort smoke artifact at `exports/research/pattern-cohort-detection-<ISO>/{results.csv, summary.md}` (cohort = 67 watch→aplus flips at vcp.tightness_range_factor=1.005)
6. First study writeup at `research/studies/2026-MM-DD-pattern-cohort-detection.md`
7. Return report at `docs/applied-research-pattern-cohort-detector-evaluator-executing-plans-return-report.md`

---

## §4 Watch items + cumulative discipline (BINDING)

### §4.1 Cumulative discipline

27 cumulative CLAUDE.md gotchas (1-27) BINDING for any 38th-40th cumulative C.C lesson #6 validations across the 3 phases (one validation per phase if Codex invoked).

### §4.2 Process discipline

- **NO Co-Authored-By footer** — ~515+ cumulative streak through `e374974`; preserve across all 3 phases
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing`
- **ASCII-only on runtime CLI paths + markdown narrative**
- **TDD per task** in executing-plans phase
- **Edit tool for per-file edits**

### §4.3 Schema discipline (LOCK)

Schema v21 LOCKED across all 3 phases. Harness MUST NOT touch migrations.

### §4.4 L2 LOCK preservation (BINDING — mirror V2 OHLCV evaluator)

ZERO new Schwab API calls. Reads OHLCV via legacy parquet path ONLY (`~/swing-data/prices_cache/<TICKER>.parquet`). 5 BINDING discriminating tests at `tests/research/test_pattern_cohort_evaluator_reader.py` per §1.4 mirror.

### §4.5 V1 persisted state read-only

ZERO modification of `candidate_criteria` / `candidates` / `evaluation_runs` / `trades` / `pattern_evaluations` / V1 persisted state. Harness output lives ONLY in `exports/research/pattern-cohort-detection-<ISO>/`.

### §4.6 Production swing/ — APPROVED for OQ-17 CLI carve-out only

CLI subcommand at `swing/cli.py` (mirror V2 OHLCV evaluator pattern; ~35-60 lines). ALL other production swing/ code stays read-only.

### §4.7 Brief-framing accuracy discipline (per gotcha #27 sub-lesson)

Implementer brainstorming spec MUST verify any "since X shipped" / "across N runs" framing against `git log` of cited commits BEFORE writing spec text. Banked discipline from `_step_pattern_detect` investigation (which framed "78 runs" → actual 7 post-ship).

---

## §5 NON-scope

- ZERO Option A scope creep (separate dispatch already authored at `swing-pipeline-pattern-detect-warnings-json-visibility-fix-dispatch-brief.md`)
- ZERO Option C scope (widening production pool predicate; substantive arch decision; operator-paired separate dispatch)
- ZERO modification of production `_step_pattern_detect` behavior
- ZERO modification of `pattern_evaluations` table writes (harness output is research-branch CSV; production table untouched)
- ZERO backfill of historical pipeline_runs
- ZERO Phase 14 commissioning consideration
- ZERO Schwab API integration changes
- ZERO new schema migrations
- ZERO Stage 3 AI second-opinion eval scope (banked V2 candidate per §1.6)
- ZERO bootstrap / Monte Carlo / sector-stratified analysis (banked V2 candidates per §1.6)

---

## §6 Three-phase handback sequence

Per V2 OHLCV evaluator precedent:

**Phase 1 brainstorming handback**: spec + open-questions list + return report. Operator-paired OQ triage at Turn D. Orchestrator commissions Phase 2.

**Phase 2 writing-plans handback**: plan + return report. Operator-paired plan review. Orchestrator commissions Phase 3.

**Phase 3 executing-plans handback**: harness + tests + CLI + smoke artifact + method-record + study writeup + return report. Operator-paired smoke review. Orchestrator merges + housekeeping + surfaces Stage 3 (AI second-opinion) decision.

Each phase has its own QA + merge + housekeeping cycle per `feedback_orchestrator_qa_implementer_product` + `feedback_orchestrator_performs_merge` BINDING.

---

## §7 First-cohort substrate (the +75 watch→aplus flips)

The first cohort target for Phase 3 smoke is the **+67 watch→aplus flips at vcp.tightness_range_factor=1.005** documented in the V2 sensitivity backtest dispatch brief §1 (`docs/v2-tightness-range-factor-backtest-dispatch-brief.md`). 15 unique tickers (RLMD 12 / DNTH 10 / RNG 9 / KOD 8 / YOU 7 / FRO 6 / TROX 4 / PTEN 2 / OII 2 / DK 2 / WULF 1 / UCTT 1 / TSHA 1 / SSRM 1 / NAT 1).

Smoke produces per-(ticker, asof_date, detector) detector verdicts → operator can cross-tabulate with backtest-trigger outcomes (already shipped at merge `e0a9edd`) to answer: *do detector-passed candidates have higher breakout-trigger rate than detector-failed candidates?*

If detector-pass cohort has DIFFERENTIATED outcomes, the operator's earlier hypothesis is validated + the next-binding-variable backtest gets a pattern-filter overlay. If not, the architectural insight remains: numeric A+ classification + chart-shape detection are independently calibrated layers that don't compose simply.

---

*End of pattern cohort detector evaluator research harness dispatch brief. V2 candidate per operator decision 2026-05-24 PM. Three-phase dispatch (brainstorming + writing-plans + executing-plans) mirroring V2 OHLCV criterion-evaluator arc precedent. Architecturally correct answer to operator's standing research question about Phase 13 detector filtering performance on loosened-A+ cohorts. ~515+ ZERO Co-Authored-By footer streak preserved through this brief commit. Substantive scope (~18-28h operator-paced across 3 phases) appropriate for V2-tier research infrastructure investment.*
