# Pattern Cohort Detector Evaluator — Phase 3 Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the pattern cohort detector evaluator harness **executing-plans phase** implementer. No prior conversation context.

**Mission:** Ship the V2-style research harness per the 2948-line writing-plans plan (15 sections §A-§O; 5 sub-bundles; ~56-67 commits projected; ~61 fast tests). All 13 brainstorming-phase OQ dispositions are LOCKED + carried forward verbatim through Phase 2 writing-plans. Plan-phase additions: 1 NEW disposition at §I.3 (`--max-runtime-seconds` deferred V2.5+). Phase 3 of 3-phase arc; Phase 1 brainstorming SHIPPED at merge `18cb49e`; Phase 2 writing-plans SHIPPED at merge `4d8b35e`; this dispatch is Phase 3.

**Workflow:** `superpowers:test-driven-development` skill (TDD; test-first → minimal impl → commit per TDD slice). **Adversarial Codex MCP review STRONGLY RECOMMENDED** via `copowers:executing-plans` wrapper — 38th cumulative C.C lesson #6 validation slot RESERVED through prior phases; Phase 3 is the natural slot (mirrors V2 OHLCV executing-plans precedent where Codex caught 1 CRITICAL + 8 MAJOR real defects against actual production code).

**Branch:** `applied-research-pattern-cohort-detector-evaluator-executing-plans` — branches from main HEAD `0963ac8` (or later).

**Worktree:** `git worktree add .worktrees/applied-research-pattern-cohort-detector-evaluator-executing-plans applied-research-pattern-cohort-detector-evaluator-executing-plans`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Expected duration:** ~10-15 hours operator-paced (mirrors V2 OHLCV executing-plans phase timing; ~44 commits across 5 sub-bundles + Codex fix rounds).

---

## §0 Read first (BINDING substrate)

1. **`docs/superpowers/plans/2026-05-24-pattern-cohort-detector-evaluator-plan.md`** — the 2948-line plan. BINDING IMPLEMENTATION BLUEPRINT. Consume per-task TDD slices verbatim.

2. **`docs/applied-research-pattern-cohort-detector-evaluator-writing-plans-return-report.md`** — Phase 2 return report; surfaces plan-phase observations + 8-function signature/cascade verification details + banked V1 simplifications.

3. **`docs/superpowers/specs/2026-05-24-pattern-cohort-detector-evaluator-design.md`** — original 996-line spec; arc-wide reference (NOT primary substrate; plan supersedes for implementation specifics but spec remains authoritative for architectural locks).

4. **`docs/applied-research-pattern-cohort-detector-evaluator-brainstorming-return-report.md`** — Phase 1 return report (arc context).

5. **`docs/applied-research-pattern-cohort-detector-evaluator-dispatch-brief.md`** — Phase 1 dispatch brief (parent of this arc; full §1.1-§1.6 arc-wide context).

6. **`research/harness/aplus_v2_ohlcv_evaluator/`** — V2 OHLCV evaluator implementation. STRUCTURAL TEMPLATE for the harness modules; in particular OQ-3 LOCKS verbatim re-export of `ohlcv_reader.py`.

7. **`docs/v2-ohlcv-criterion-evaluator-executing-plans-return-report.md`** — V2 OHLCV executing-plans return report. STRUCTURAL TEMPLATE for this dispatch's deliverable + Codex chain shape (R5 NO_NEW_CRITICAL_MAJOR after 5 rounds; 1 CRITICAL + 8 MAJOR resolved in-place via 10 fix commits).

8. **CLAUDE.md gotchas (1-27)** — full cumulative discipline. Especially relevant:
   - **#17** (signature verification) — plan applied this; preserve through implementation
   - **#19** (cascade-call-graph) — plan applied this; preserve through implementation
   - **#20** (runtime-binding-shape + empty-result-set) — implementer MUST apply at every SQL skeleton + dataclass empty-state
   - **#21** (cumulative regression cascade audit) — if Codex chain fixes introduce regressions in follow-up rounds, "imagined Codex next-round" audit BINDING
   - **#22** (per-counter-accumulation audit) — applies to ANY counter, not just SQL aggregates
   - **#23** (dataclass attribution metadata) — applies to ALL attribution-bearing dataclasses
   - **#24-26** (V1↔V2 parity discipline family) — preserved via spec §E.1 baseline parity invariant
   - **#27** (silent-skip-without-audit pattern) — this harness ARCHITECTURALLY answers gotcha #27's research question; implementer MUST NOT reintroduce silent-skip patterns in the new harness modules

---

## §1 Sub-bundle dispatch sequence (per plan §G)

Per plan §G dependency graph; sequential dispatch:

- **T-PC.1.1** — `cohort_reader.py` (CSV + inline parsing; per-entry pattern-class filter per OQ-5)
- **T-PC.1.2** — `exceptions.py` + module skeleton + `__init__.py`
- **T-PC.2** — `detector_invoker.py` (re-import `_pattern_detect_registry` per OQ-1; per-window verdict capture per OQ-7; template-match Pass 2 default on per OQ-6)
- **T-PC.3** — `output.py` (CSV + markdown + manifest; uniform empty-state per OQ-12)
- **T-PC.4** — `run.py` orchestration + CLI subcommand registration (OQ-13 sole production-swing/ carve-out; 35-60 lines at `swing/cli.py`)
- **T-PC.5** — first-cohort smoke + method-record (`research/method-records/pattern-cohort-detection.md` v0.1.0 per spec §K) + study writeup (`research/studies/2026-05-24-pattern-cohort-detection.md` per spec §L)

Per-task acceptance criteria + per-task discriminating tests enumerated at plan §D + §E.

---

## §2 Commit cadence discipline (BINDING per plan §G.0)

Per V2 OHLCV executing-plans precedent + plan §G.0:

- Each TDD slice (test + minimal implementation expansion + passing test) = ONE commit
- Parametrize-consolidation for related discriminating tests (per V2 OHLCV §G.0)
- ~56-67 commits projected across 5 sub-bundles
- Codex fix rounds add additional commits (V2 OHLCV had 10 fix commits across R1-R4 rounds)

Discipline deviations BANKED per V2 OHLCV precedent (e.g., mega-consolidation for fixture-heavy tasks acceptable if substance verified + artifact trail preserved). Banked at return report §3 if deviations occur.

---

## §3 Test budget (per plan §H)

- ~50-55 fast tests after parametrize-consolidation (~61 pre-consolidation)
- Baseline ~5893 → ~5944-5954 post-ship projection
- **5 BINDING L2 LOCK discriminating tests** at `tests/research/test_pattern_cohort_evaluator_reader.py` per plan §F + §K (mirrors V2 OHLCV evaluator's 5 BINDING tests; 4 file-open boundaries + 4-module import sentinel graph + byte-checksum + signature lock + V2-source-grep)

---

## §4 Codex MCP review (38th cumulative C.C lesson #6 validation slot)

**STRONGLY RECOMMENDED** at this phase per V2 OHLCV precedent:

- V2 OHLCV executing-plans Codex caught R1.C1 `classify_candidate_tier` docstring-vs-implementation drift (TT-gate skip candidates misclassified; affected LARGEST candidate subset)
- R1.M1 `substitute_cfg` range validation missing
- R1.M2 baseline parity counter inflation by factor of 17
- R1.M3 per-ticker OHLCV cache architecture broken (would multiply I/O cost ~63x on full operator run)
- R2.M2+R3.M1+R4.M1 flip-attribution provenance 3-instance cascade

Invoke via `copowers:executing-plans` wrapper. Expected chain shape per V2 OHLCV precedent: R5 NO_NEW_CRITICAL_MAJOR after 5 rounds with 0 CRITICAL + 0 MAJOR convergence.

27 cumulative CLAUDE.md gotchas (1-27) BINDING for the 38th cumulative C.C lesson #6 validation. Pre-Codex review applied at plan phase (8 functions verified via signature + cascade-call-graph audit); Codex still likely surfaces REAL defects per the cumulative-validation NOTABLE pattern.

---

## §5 Deliverables

Per plan §B file map + §K method-record + §L study writeup:

1. **6 NEW research/ modules** at `research/harness/pattern_cohort_evaluator/`:
   - `__init__.py`
   - `exceptions.py`
   - `cohort_reader.py`
   - `detector_invoker.py`
   - `output.py`
   - `run.py`
   - (OHLCV reader re-exported VERBATIM from `research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader` per OQ-3)

2. **1 MODIFIED `swing/cli.py`** — sole production-swing/ carve-out per OQ-13; `swing diagnose pattern-cohort-detect` subcommand registration (35-60 lines mirroring V2 OHLCV's `swing diagnose aplus-sensitivity-v2` precedent)

3. **~50-55 fast tests** at `tests/research/test_pattern_cohort_evaluator_*.py` (~61 pre-consolidation per plan §H; 5 BINDING L2 LOCK + ~45-50 functional)

4. **NEW method-record** at `research/method-records/pattern-cohort-detection.md` (v0.1.0 per spec §K.1 frontmatter)

5. **First-cohort smoke artifact** at `exports/research/pattern-cohort-detection-<ISO>/{results.csv, summary.md, manifest.json}` against the +67 watch→aplus flips at `vcp.tightness_range_factor=1.005` (15 unique tickers per OQ-9 LOCK)

6. **First study writeup** at `research/studies/2026-05-24-pattern-cohort-detection.md` per spec §L template (cohort-level detector-confirmation rate + per-class breakdown + per-ticker breakdown + cross-tabulation with V2 OHLCV backtest trigger outcomes if feasible)

7. **Return report** at `docs/applied-research-pattern-cohort-detector-evaluator-executing-plans-return-report.md` per V2 OHLCV executing-plans precedent: per-sub-bundle ship summary + Codex chain shape (per-round Major counts) + 38th cumulative C.C lesson #6 validation result + any NEW gotchas surfaced + banked V1 simplifications + discipline deviations

---

## §6 Watch items + cumulative discipline (BINDING)

### §6.1 Cumulative discipline

27 cumulative CLAUDE.md gotchas (1-27) BINDING for 38th cumulative C.C lesson #6 validation. ALL applicable per V2 OHLCV executing-plans precedent.

### §6.2 Process discipline

- **NO Co-Authored-By footer** — ~521+ cumulative streak through `4d8b35e`; preserve across all commits
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing`
- **ASCII-only on runtime CLI paths + markdown narrative** (Windows cp1252 stdout safety)
- **TDD per task** — each TDD slice = ONE commit per plan §G.0
- **Edit tool for per-file edits**

### §6.3 Schema discipline (LOCK)

Schema v21 LOCKED. Harness MUST NOT touch migrations. ZERO files in `swing/data/migrations/`.

### §6.4 L2 LOCK preservation (BINDING)

ZERO new Schwab API calls. ZERO reads of `{T}.schwab_api.parquet` from harness code. 5 BINDING L2 LOCK discriminating tests at `tests/research/test_pattern_cohort_evaluator_reader.py` MUST stay green per plan §F + §K.

### §6.5 V1 persisted state read-only

Harness output lives ONLY in `exports/research/pattern-cohort-detection-<ISO>/`. ZERO modification of `pattern_evaluations` / `candidate_criteria` / `candidates` / `evaluation_runs` / `trades` / V1 persisted state.

### §6.6 Production swing/ — OQ-13 carve-out ONLY

ONLY ALLOWED swing/ modification = CLI subcommand at `swing/cli.py` per OQ-13 (35-60 lines mirroring V2 OHLCV OQ-17 precedent). ALL other production swing/ stays read-only. `git diff main -- swing/` post-ship MUST show ONLY `swing/cli.py` modifications.

### §6.7 Brief-framing accuracy discipline (per gotcha #27 sub-lesson)

Implementer MUST verify all "since X shipped" / "across N runs" / file-line-range citations against `git log` + source code BEFORE inclusion in study writeup or method-record. Banked from `_step_pattern_detect` investigation framing error.

### §6.8 Silent-skip discipline (per gotcha #27)

Harness modules MUST NOT reintroduce silent-skip patterns. If a code path has an empty-pool / no-targets / nothing-to-do early-return, the path MUST emit a manifest field OR markdown warning surface (analogous to V2 OHLCV evaluator's `BothExistDiagnostic`). The whole point of this harness is to AVOID the production silent-skip; the harness itself must respect the same discipline.

---

## §7 NON-scope

- ZERO modification of LOCKED brainstorming OQ dispositions (all 13) + LOCKED plan-phase disposition (1 at plan §I.3)
- ZERO scope creep into Option A (warnings_json visibility fix; SEPARATE dispatch at brief `e374974`)
- ZERO scope creep into Option C (pool-predicate widening; SEPARATE dispatch banked)
- ZERO modification of production `_step_pattern_detect` behavior
- ZERO modification of `pattern_evaluations` table writes (harness output is research-branch CSV; production table untouched)
- ZERO backfill of historical pipeline_runs
- ZERO Phase 14 commissioning consideration
- ZERO Schwab API integration changes
- ZERO new schema migrations
- ZERO Stage 3 AI second-opinion eval scope (banked V2 candidate per Phase 1 dispatch brief §1.6)
- ZERO bootstrap / Monte Carlo / sector-stratified analysis (banked V2 candidates)
- ZERO --max-runtime-seconds CLI flag (DEFERRED V2.5+ per plan §I.3 disposition)

---

## §8 Post-executing-plans handback

When harness + tests + CLI + smoke + method-record + study writeup + return report shipped + (optional) Codex chain converged:

1. Inline self-verification: ruff check `research/harness/pattern_cohort_evaluator/`; schema unchanged; ZERO new Schwab API calls; ZERO Co-Authored-By footer; V1 persisted state otherwise unchanged; ALL fast tests green; smoke artifact written
2. Hand back to operator with: per-sub-bundle ship summary + Codex chain shape + 38th cumulative C.C lesson #6 validation result + cohort-level detector-confirmation rate from first-cohort smoke + study writeup substance.

Orchestrator-side next steps post-handback:
- QA per `feedback_orchestrator_qa_implementer_product` (multi-day-scale; expect 30-50 commits to QA)
- Merge `--no-ff` to main; push
- Post-merge housekeeping (full pivot scale per V2 OHLCV executing-plans precedent if Codex chain surfaces NEW gotchas; sub-event scale if zero new gotchas)
- Operator-paired first-cohort smoke review (does detector-pass cohort have differentiated breakout-trigger rate vs detector-fail per the V2 OHLCV backtest cross-tabulation?)
- Method-record promotion gate per V2.1 §IV.D + §VII.C: research → shadow promotion conditions enumerated at spec §K.3

---

*End of pattern cohort detector evaluator Phase 3 executing-plans dispatch brief. Consumes 2948-line writing-plans plan as BINDING IMPLEMENTATION BLUEPRINT. ALL 13 brainstorming OQs + 1 plan-phase OQ LOCKED + carried forward verbatim with ZERO amendments through both prior phases (TWO-IN-A-ROW cumulative discipline signal). Ships ~7 modules + ~50-55 tests + CLI subcommand + method-record + first-cohort smoke + study writeup. ~521+ ZERO Co-Authored-By footer streak preserved through this brief commit. Mirrors V2 OHLCV criterion-evaluator executing-plans precedent ~10-15h scope + R5 NO_NEW_CRITICAL_MAJOR Codex convergence expectation.*
