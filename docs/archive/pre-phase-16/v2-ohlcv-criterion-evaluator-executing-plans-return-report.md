# V2 OHLCV Criterion-Evaluator Harness — Executing-Plans Return Report

**Branch:** `applied-research-v2-ohlcv-criterion-evaluator-executing-plans`
**Baseline SHA:** `d999c5a` (pre-T-V2.1; post-executing-plans-dispatch-brief commit)
**Final HEAD SHA:** `0d0cce0` (post-Codex-R4-fix; CONVERGED at NO_NEW_CRITICAL_MAJOR)
**Total commits:** 43
**Test delta:** 5778 baseline → 5778 + 94 NEW V2 fast tests + 21 additional from Codex fix-rounds = ~5893 (per `pytest tests/research/ tests/cli/test_diagnose_subcommands.py` shows 315 passed in V2 scope alone)
**Adversarial Codex chain:** 5 rounds; CONVERGED at NO_NEW_CRITICAL_MAJOR
**33rd cumulative C.C lesson #6 validation:** NOTABLE (Codex surfaced 1 CRITICAL + 8 MAJOR + 4 MINOR across 5 rounds; ALL CRITICAL + MAJOR RESOLVED in-place; 1 MINOR banked as V2 candidate)

---

## §1 Commit chain shape (per-sub-bundle)

### T-V2.1 — exceptions + ohlcv_reader + cfg_substitution + context_builder (3 commits)

- `a2315df` — T-V2.1.1: `__init__.py` + `exceptions.py` (7 typed exceptions) + `ohlcv_reader.py` + L2 LOCK 5 BINDING tests (14 tests)
- `d009dac` — T-V2.1.2: `cfg_substitution.py` (6 tests)
- `be53821` — T-V2.1.3: `context_builder.py` (21 tests)

Test delta: +41 fast tests.

### T-V2.2 — sweep.py orchestrator (6 commits: 1 main + 5 fix)

- `baeba2b` — T-V2.2 main: `sweep.py` (703 lines) + `SweepEntryV2` + `run_v2_sweep` + 18 tests (single-commit mega-consolidation — discipline deviation banked at §3 below)
- `cce53de` / `c580630` / `f78adf7` / `86e51cd` / `bcaf050` — 5 code-quality fix commits addressing Important findings: discriminating tier-2 surrogate assertion + cfg-propagation assertion + vcp watch_max_fails isolation rename + V1 stub `old_criterion_failure` banking comment + widened-except clause for `_precompute_ohlcv_coverage_skips`

Test delta: +19 fast tests.

### T-V2.3 — output.py (13 commits including spec-fix pair)

- `7e8098b` — Step 0 TDD red phase: 12 failing tests for output.py
- `42faae9` / `f29bc84` / `c262545` / `dc849b8` / `0c6e806` / `a9ae2f9` / `d371076` / `0ad2f21` / `a7e6353` / `e13a607` — Steps 1-12 + L2 LOCK Test 2 extension + wrap (proper TDD red-then-green progression)
- `e1d7144` / `dea81ab` — 2 spec-compliance fix commits (manifest `tier_1_count`/`tier_2_count` + CRITERION DRIFT heading level)

Test delta: +14 fast tests.

### T-V2.4 — run.py + CLI subcommand registration (3 commits)

- `40d3ee9` — Step 0 TDD red phase: 13 failing tests for run.py
- `a14d2d6` — T-V2.4 wrap: run.py + swing/cli.py OQ-17 carve-out (71 lines) + 15 tests GREEN
- `db6b45f` — Code-quality fix: tracemalloc stopped on sweep exception path (nested try/finally; 1 NEW discriminating test)

Test delta: +14 fast tests (13 + 1 tracemalloc-on-exception).

### T-V2.5 — Method-record + study + integration tests + smoke artifact + closer (8 commits)

- `f467ff5` — Method-record v0.1.0 → v0.2.0 (NEW §K.2-§K.5)
- `940553c` — First V2 study writeup at `research/studies/2026-05-23-v2-ohlcv-criterion-evaluator.md`
- `28c32ea` — phase-0-tasks "Next" refresh: V2 SHIPPED
- `2cb5f2a` — 6 integration/E2E tests at `tests/research/test_aplus_v2_ohlcv_integration.py`
- `737c589` — Closer + smoke artifact at `exports/diagnostics/aplus-sensitivity-v2-20260523T230131Z.{csv,md}` (partial implementer-side smoke: 5 eval_runs / 120s cap / 516-ticker universe / 351 candidates; CRITERION DRIFT for DK:eval_run_62 + BOTH-EXIST for AESI + PL + DK)
- `19f4f23` — Post-review fix: populate gate-variable rows in study findings from smoke data
- `8bc577f` — Post-review fix: deduplicate affected_tickers in both-exist banner emit
- `b468dc2` — Post-review fix: study amendments — L2 LOCK 5-test count correction + issue log

Test delta: +6 integration tests + 1 dedup test = +7 fast tests.

### Codex MCP Round 1-4 fix commits (10 commits)

- `624e3e1` — Codex R1.C1: `classify_candidate_tier` skip-by-TT-gate semantic (None → tier-1)
- `6c98801` — Codex R1.M1: `_VARIABLE_RANGES` + `OutOfRangeSubstitutionError` raise in `substitute_cfg`
- `0542534` — Codex R1.M2: `_compute_baseline_parity` extracted; called once before variable loop
- `c4abb2a` — Codex R1.M3: dependency-injected `ohlcv_getter` through to `build_eval_run_cohort`
- `6bdf69d` — Codex R1.M4 + R1.m1: study doc reconciliation (CRITERION DRIFT alert semantics + RS dup-detection V1 simplification entry)
- `a22f160` — Codex R2.M1: runtime cap Option B semantic doc + discriminating test
- `9dc6515` — Codex R2.M2: `FlippedCandidate.variable_name` + dedicated `## V1<->V2 Baseline Parity Drift` section
- `81c03bd` — Codex R2.m1: study typo correction
- `d196d12` — Codex R3.M1: per-variable drill-down records candidate flips via `baseline_bucket_map`
- `0d0cce0` — Codex R4.M1: per-variable flip `old_bucket` uses V2 recomputed baseline (not V1 persisted)

Test delta: +21 discriminating tests from Codex fix rounds.

**Cumulative test delta**: 41 + 19 + 14 + 14 + 7 + 21 = **+116 NEW V2 fast tests** distributed across 8 test files (including the CLI extension at tests/cli/test_diagnose_subcommands.py). 1 skipped via env-var gate.

---

## §2 Codex MCP adversarial chain summary

| Round | Critical | Major | Minor | Verdict |
|-------|----------|-------|-------|---------|
| R1    | 1        | 4     | 1     | ISSUES_FOUND |
| R2    | 0        | 2     | 1     | ISSUES_FOUND |
| R3    | 0        | 1     | 1     | ISSUES_FOUND |
| R4    | 0        | 1     | 0     | ISSUES_FOUND |
| R5    | 0        | 0     | 1     | **NO_NEW_CRITICAL_MAJOR** |

**Total: 1 CRITICAL + 8 MAJOR + 4 MINOR cumulative.** ALL CRITICAL + MAJOR RESOLVED in-place via 10 fix commits. R5 MINOR (unbounded flip recording) BANKED as V2 candidate.

### Codex defects caught against actual production code

1. **R1.C1**: `classify_candidate_tier` only returned tier-1 for `risk_result == "pass"`, misclassifying TT-gate skips (where risk never ran; `risk_result is None`) as tier-2. Docstring documented correct semantic but implementation was wrong. Real bug; affected baseline parity attribution for the LARGEST candidate subset in any real universe.
2. **R1.M1**: `substitute_cfg` had no range validation; `OutOfRangeSubstitutionError` defined but never raised. Real gap; spec-required validation missing.
3. **R1.M2**: Inflated baseline parity counts — `tier_1_count` + `tier_2_count` accumulated N_variables × N_true (factor of 17 over actual baseline). Real arithmetic bug.
4. **R1.M3**: Per-ticker OHLCV cache scope gap — cache used inside sweep loop but `build_eval_run_cohort` read parquet directly via `read_yfinance_shape_a_sliced` for every (eval_run, universe ticker) pair. Real performance bug; would multiply I/O cost ~63× on full operator run.
5. **R1.M4 + R2.M1**: Documentation gaps on CRITERION DRIFT exit-code semantics + max_runtime_seconds applying after baseline parity. Both reconciled to clarify the "REPORTED ALERT" + "mandatory setup work" semantics.
6. **R2.M2**: Drill-down provenance misattribution — `FlippedCandidate` had no `variable_name`; output mapped flips by sweep_point matching only; baseline flips appeared under any variable with matching sweep_point. Real misattribution bug.
7. **R3.M1**: Regression from R2 — per-variable drill-down was empty because `_record_flip` only fired from `_compute_baseline_parity` (variable loop never recorded per-variable flips). Real bug introduced by moving baseline parity outside the loop without restoring per-variable recording.
8. **R4.M1**: Per-variable flip `old_bucket` always emitted `cand_row.persisted_bucket` (V1 persisted) but detection compared against `baseline_bucket_map` (V2 recomputed). If baseline drift existed, flip records showed wrong direction. Real edge-case bug.

The R1 CRITICAL + 8 MAJOR findings represent significant real defects that pre-Codex orchestrator-side + implementer-side reviews + spec-compliance + code-quality reviewers all missed. This validates the BINDING value of the adversarial Codex MCP loop.

---

## §3 Discipline streaks + deviations

### Streaks PRESERVED

- **ZERO `Co-Authored-By` footer trailers**: ~447+ cumulative streak through `d999c5a` extended to ~490+ through `0d0cce0` (43 NEW commits all clean)
- **ZERO production `swing/` writes beyond OQ-17 carve-out**: `git diff main -- swing/ --stat` shows ONLY `swing/cli.py` (+71 lines for `diagnose aplus-sensitivity-v2` subcommand registration)
- **ZERO migration writes**: `git diff main -- swing/data/migrations/` empty
- **Schema v21 UNCHANGED**
- **L2 LOCK preserved** via 5 BINDING discriminating tests at `tests/research/test_aplus_v2_ohlcv_reader.py` (file-open mock + import-graph sentinel + byte-checksum + signature lock + source grep)
- **ASCII-only on all emit paths** (CSV + markdown narrative; smoke artifact verified cp1252-roundtrip clean)
- **18 OQ dispositions LOCKED verbatim** through brainstorming → writing-plans → executing-plans phases (ZERO amendments)

### Deviations BANKED

- **T-V2.2 single-commit mega-consolidation**: Plan §G.0 expected ~15 commits via parametrize-consolidation; T-V2.2 main landed as ONE commit (`baeba2b`) bundling sweep.py orchestrator (~700 LOC) + 18 tests. TDD artifact trail lost (no separate red/green commits). Substance verified by spec + code quality reviewers; 5 fix commits subsequently restored proper artifact trail for review issues.
- **OQ-17 line count over budget**: 71 lines added to swing/cli.py vs 35-60 line target. All extras are V1-mirror patterns (`_validate_diagnose_db_path` helper invocation; `sqlite3.OperationalError` catch; `show_default=True`). No new scope.
- **T-V2.4 minimal commit count**: 2 commits (red + green) vs ~10 expected. TDD red phase IS committed separately so artifact trail preserved albeit at coarser granularity than T-V2.3's 11 commits.
- **Partial operator smoke**: smoke artifact captures 5 eval_runs / 120s cap / 516 universe / 351 candidates (vs full operator 63 eval_runs / 5681 candidates). Implementer-side partial smoke landed; full operator reproduction enumerated in `research/phase-0-tasks.md` "Next" action.
- **Closer commit message undercounted L2 LOCK tests**: `737c589` body cited "3 BINDING discriminating tests" but canonical count is 5 (3 BINDING + 2 defensive per plan §K). Code/docs were correct; closer message was wrong. Reconciled in study Amendments section at `b468dc2`.

---

## §4 Forward-binding lessons banked

### 5 NEW patterns from executing-plans-phase Codex chain

1. **Tier classification semantics under spec ambiguity** (R1.C1): when a docstring documents a richer semantic than the code implements, treat the docstring as the BINDING contract and audit all callsites against the docstring. Discriminating-test pattern: plant the full Cartesian product of (bucket, risk_result) combinations + assert each row classified per the documented semantic.
2. **Counter-double-counting risk in variable-sweep loops** (R1.M2): when extracting baseline computation from a per-variable loop, audit ALL counters that accumulate inside the loop — any counter that was accumulating once per (variable, candidate) but should be once per candidate needs explicit extraction to a pre-loop pass. Pre-empt: enumerate per-counter accumulation semantic at design time.
3. **Cache architecture full-graph audit** (R1.M3): when claiming "per-X cache" architecture, audit ALL callsites that read X to verify the cache wraps them all. A cache that wraps only the headline call path while bypassed by helper functions defeats the architectural claim. Discriminating-test pattern: mock the underlying I/O + assert call count == N (cache hit) for N>1 reads of same X.
4. **Flip attribution provenance** (R2.M2 + R3.M1 + R4.M1): when a dataclass represents an outcome with attribution metadata (variable_name, source, etc.), ensure (a) the attribution field is required for downstream rendering; (b) the rendering code uses the attribution field NOT a value-matching heuristic; (c) old_value source matches new_value source (don't compare against one baseline + record against another). This is a 3-instance lesson across Codex R2 + R3 + R4.
5. **Cumulative regression cascade in adversarial-review fix loops** (R2 + R3 + R4 chain): a single Codex MAJOR fix can introduce a NEW MAJOR finding in the next round; this happened twice in this dispatch (R1.M2 fix → R3.M1; R3.M1 fix → R4.M1). Banking: pre-Codex reviews should "imagine the fix" and audit for second-order regressions BEFORE the fix lands.

### 2 NEW Expansion sub-refinements promoted

- **Expansion #2 sub-refinement (#19) reinforced** at R1.C1: docstring-vs-implementation drift verification (when a function's docstring documents semantic X but code implements semantic Y, the docstring should be the BINDING contract for spec audit).
- **Expansion #4 sub-refinement (#20) reinforced** at R1.M3: dependency-injection-vs-direct-call audit for cache/wrapper architectures (when a function claims to wrap a cache, audit ALL callsites of the wrapped function; do NOT accept "the wrapper is invoked here but the wrapped function is called directly there" — the wrapper architecture is structurally broken).

These ENRICH existing CLAUDE.md gotchas #19 + #20 (banked from V2 writing-plans phase). The executing-plans phase confirmed both via real defects.

### V2 candidates banked (V2-DEFERRED items requiring NEW dispatch)

1. **`old_criterion_failure` real computation**: V1 stub emits `"(none)"` universally; V2 candidate threads `evaluate_one` result through `_record_flip` to expose actual failing criterion (T-V2.2 banking).
2. **Per-variable flip recording cap / top-N / detail-output flag**: R5 minor — current implementation could produce unbounded `flipped` tuple on full 5681×17×4 sweep; V2 candidate adds cap or top-N filter or detail-output flag.
3. **RS universe duplicate detection**: defense-in-depth stage inert today (`load_universe()` pre-dedups); V2 candidate validates raw file rows before `load_universe()`.
4. **Per-eval_run-historical RS universe snapshots**: V2 uses current-universe snapshot per OQ-14; V3+ candidate persists per-eval_run snapshots at write-time.
5. **`vcp.watch_max_fails` promote-to-cfg**: V2 mirrors V1 special-case per OQ-11; V2.5 candidate promotes to cfg-derived in production `bucket_for` (1-line production change).
6. **`Config.from_defaults` user-config.toml cascade**: `python -m research.harness.aplus_v2_ohlcv_evaluator.run` direct-invocation path doesn't cascade user-config overrides (only Click handler does); V2 candidate wires cascade through main argparse path.
7. **`schwab_api` parquet fixture-spy escalation**: L2 LOCK 5 BINDING tests use synthetic fixtures + 4-boundary file-open mock; cassette-recording of REAL Schwab response would close the residual gap (V2 dispatch — operator-paired session required).
8. **Full operator 63-eval-run reproduction**: implementer-side partial smoke landed; full operator reproduction is the FIRST Applied Research arc operator-paired follow-up (enumerated in `research/phase-0-tasks.md` "Next").

---

## §5 Per-expansion verdict (33rd cumulative C.C lesson #6 validation: NOTABLE)

Pre-Codex orchestrator-side review applied ALL 7 expansions + 5 NEW candidate refinements + 2 NEW sub-refinements (#19 + #20) BUT Codex still surfaced 1 CRITICAL + 8 MAJOR. This is the SECOND consecutive NOTABLE validation (V2 writing-plans was the first; cumulative C.C lesson #6 banks 22 CLEAN + 11 NOTABLE through this dispatch).

- **Expansion #1 (hardcoded-duplicate audit)**: CLEAN (no hardcoded-duplicate findings)
- **Expansion #2 + #17 (brief-vs-actual-production-function-signature)**: PARTIALLY APPLIED — R1.C1 docstring-vs-code drift not caught pre-Codex; documented audit pattern reinforced.
- **Expansion #3 (schema-CHECK-vs-semantic-contract)**: N/A V2 (no schema)
- **Expansion #4 + #18 + #20 (SQL skeleton verification + runtime-binding-shape)**: APPLIED CLEAN (no SQL findings from Codex; all SQL discipline preserved)
- **Expansion #5 (cross-section spec inventory grep)**: APPLIED CLEAN
- **Expansion #6 (content-completeness)**: PARTIALLY APPLIED — drill-down provenance misattribution (R2.M2) is a content-completeness gap NOT a documentation gap
- **Expansion #7 (cross-row semantic scope)**: N/A V2 (no operator-input POST handler)
- **Expansion #8 (SQL aggregation UNIT)**: N/A V2 (no GROUP BY/COUNT/SUM); HOWEVER the R1.M2 inflated-counts finding is THE SAME family of arithmetic-unit-correctness — promote Expansion #8 to apply to ANY counter accumulation, not just SQL aggregates.
- **Expansion #9 (form-render anchor lifecycle)**: N/A V2 (no forms)
- **Expansion #10 (architecture-location audit)**: APPLIED CLEAN at design-time (NEW module placement under research/harness/)
- **Expansion #11 (taxonomy propagation)**: APPLIED CLEAN at SweepEntryV2 kind enum; HOWEVER `FlippedCandidate.variable_name` would have been caught earlier had Expansion #11 audited that dataclass too — promote Expansion #11 scope to ALL dataclasses with attribution metadata, not just enum-bearing.
- **Expansion #12 (sibling-route audit)**: N/A V2 (no route handlers)
- **Expansion #19 (cascade-call-graph)**: APPLIED CLEAN at writing-plans phase; reinforced at R1.C1.
- **Expansion #20 (runtime-binding-shape + empty-result-set)**: APPLIED CLEAN.

**Process improvement candidate (BANK as 34th-validation expansion)**: **Expansion #13 candidate — Cumulative regression cascade audit in adversarial-review fix loops**. When a MAJOR Codex finding is fixed by restructuring code, the orchestrator MUST audit the FIX for second-order regressions BEFORE the next round invokes. Discriminating pattern: post-fix code review SHOULD include "imagined Codex next-round" pass that anticipates the cascade. R2.M2, R3.M1, R4.M1 chain in this dispatch is direct evidence — promotion candidate.

---

## §6 V1 simplifications enumerated (per V1-simplification-banking discipline)

(Inherited from study writeup §"V1 simplifications enumerated"; canonical ledger at `research/studies/2026-05-23-v2-ohlcv-criterion-evaluator.md`:230-260.)

1. `old_criterion_failure="(none)"` always emitted in `_record_flip` (V2 candidate per §4)
2. `_precompute_ohlcv_coverage_skips` widened except clause `(OhlcvCoverageError, FileNotFoundError, OSError)` — defense-in-depth; test exercises OhlcvCoverageError branch only
3. tracemalloc-on-exception fix (T-V2.4): nested try/finally ensures cleanup
4. RS universe duplicate detection: defense-in-depth (inert today; `load_universe()` pre-dedups). V2 candidate per §4.
5. Partial implementer smoke (5 eval_runs / 120s cap) vs operator full 63-eval-run reproduction (operator-paired next action)
6. Per-variable flip recording potentially unbounded (R5 minor banking)

---

## §7 Verification at handback

```bash
# Test count
python -m pytest tests/research/ tests/cli/test_diagnose_subcommands.py -q --no-header
# Output: 315 passed, 1 skipped (env-var-guarded git diff gate)

# ZERO Co-Authored-By trailers
git log d999c5a..HEAD --format='%(trailers:key=Co-Authored-By)' | grep -ci "Co-Authored-By"
# Output: 0

# Production swing/ scope: ONLY swing/cli.py
git diff d999c5a..HEAD -- swing/ --stat
# Output: swing/cli.py | 71 +++++++++++++++++++++

# ZERO migration writes
git diff d999c5a..HEAD -- swing/data/migrations/
# Output: empty

# L2 LOCK preserved: zero banned imports in V2 modules
grep -rE "import yfinance|import schwabdev|from swing.integrations.schwab|from swing.data.ohlcv_archive" research/harness/aplus_v2_ohlcv_evaluator/
# Output: empty (zero matches)

# Ruff clean
python -m ruff check research/harness/aplus_v2_ohlcv_evaluator/ swing/cli.py
# Output: All checks passed!
```

---

## §8 Orchestrator post-merge handback checklist (recommended)

Per `feedback_orchestrator_performs_merge` discipline + plan §M "Post-closer orchestrator-side housekeeping":

1. **Operator handback** with this report + the smoke artifact for review (real CRITERION DRIFT for DK:eval_run_62 worth operator attention)
2. **Merge `--no-ff` to main** + push
3. **Post-merge housekeeping bundle**:
   - CLAUDE.md line 3 "Current state" refresh — V2 OHLCV harness SHIPPED status
   - `docs/orchestrator-context.md` "Currently in-flight work" — V2 SHIPPED + Applied Research Tranche 1 arc COMPLETED (3 of 3 commits — brainstorming + writing-plans + executing-plans)
   - Any NEW gotchas surfaced from Codex chain (especially Expansion #13 candidate — cumulative regression cascade)
   - phase3e-todo NEW top entry: operator full 63-eval-run reproduction
   - orchestrator-context current state refresh + Prior demote + archive-split per size-check trigger
4. **Operator-paired next action**: review V2 OHLCV harness output → identify binding threshold variables OR declare all 15 non-binding per OQ-8 promotion ladder gates

---

## §9 Streaks tally (final at handback)

- **~490+ ZERO `Co-Authored-By` footer trailer** cumulative through this dispatch (43 NEW commits)
- **5778 → ~5893 fast tests** projected (post-V2-merge; +115 NEW from V2 dispatch including Codex fix rounds)
- **ZERO new Schwab API calls** (L2 LOCK preserved + REINFORCED via 5 BINDING discriminating tests)
- **Schema v21 UNCHANGED**
- **22 + 11 = 33rd cumulative C.C lesson #6 validations** (22 CLEAN through T3.SB3 + 11 NOTABLE through Phase 13 closer arc + V2 brainstorming + V2 writing-plans + V2 executing-plans)
- **18 OQ dispositions LOCKED verbatim** through brainstorming → writing-plans → executing-plans (ZERO amendments)
- **5 NEW writing-plans-phase patterns + 5 NEW executing-plans-phase patterns banked at §4**

---

*End of V2 OHLCV criterion-evaluator harness executing-plans return report. Codex chain CONVERGED at R5 NO_NEW_CRITICAL_MAJOR (1 CRITICAL + 8 MAJOR + 4 MINOR cumulative; ALL CRITICAL + MAJOR RESOLVED in-place; 1 MINOR banked as V2 candidate). ~490+ ZERO Co-Authored-By footer streak preserved + extended. FIRST Applied Research Tranche 1 arc COMPLETED (3 of 3 commits: brainstorming + writing-plans + executing-plans).*
