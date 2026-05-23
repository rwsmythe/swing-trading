# V2 OHLCV Criterion-Evaluator Harness — Writing-Plans Return Report

**Status:** SHIPPED 2026-05-23 PM — writing-plans phase for first Applied Research arc post-Phase-13-FULLY-CLOSED per Path B operator LOCK 2026-05-23 PM (`b4d7719`).

**Branch:** `applied-research-v2-ohlcv-criterion-evaluator-writing-plans` (branched from main HEAD `f8cafd9`).

**Final HEAD:** `41831a7` (R6 minor sweep + chain CONVERGED NO_NEW_CRITICAL_MAJOR).

**Deliverable:** [`docs/superpowers/plans/2026-05-23-v2-ohlcv-criterion-evaluator-plan.md`](superpowers/plans/2026-05-23-v2-ohlcv-criterion-evaluator-plan.md) — **2602 lines; 15 sections §A-§O** including self-review.

---

## §1 Commit chain shape

8 commits total: 1 initial plan + 6 Codex MCP fix bundles + 1 return report.

| # | Commit | Phase | Summary |
|---|--------|-------|---------|
| 1 | `ef66feb` | Initial plan | V2 OHLCV criterion-evaluator harness implementation plan (~2400 lines; 15 sections §A-§O) per writing-plans dispatch brief §5 done criteria. |
| 2 | `21cc950` | Codex R1 | 7 MAJOR + 2 MINOR resolved in-place (SQL IN-clause dynamic placeholder; cfg.paths vs cfg.archive; L2 LOCK 4-module sentinel + 4-boundary file-open mock; evaluate_one signature lock via typing.get_type_hints; commit-cadence §G.0 preface; test budget recalibrated +12). |
| 3 | `947552d` | Codex R2 | 3 MAJOR + 3 MINOR resolved (candidate-not-in-universe BatchContext returns; sqlite3 URI mode=ro; Config.from_defaults purity corrected; stale `:eval_run_ids` text; ~68 vs ~80 inconsistency; footer "3 file-open boundaries" → 4). |
| 4 | `7b20fd4` | Codex R3 | 3 MAJOR + 2 MINOR resolved (horizon_weeks-scaled bars_needed; Config.from_defaults user-config cascade corrected; empty-eval-runs short-circuit; tomli → tomllib; URI path-escape via `Path.resolve().as_uri()`). |
| 5 | `08322ac` | Codex R4 | 2 MAJOR + 1 MINOR resolved (empty-eval-runs test moved to T-V2.2 from T-V2.1.3; empty-DB return shape consistency; Schwab citation extended). |
| 6 | `f39b62f` | Codex R5 | 1 MAJOR + 3 MINOR resolved (`v2_universe_hash="empty_no_eval_runs"` sentinel in empty-DB return; Schwab refresh_token citation corrected; §H total ~80 → ~84; §G.0 commit-cadence table refresh). |
| 7 | `41831a7` | Codex R6 (CONVERGED) | 0 MAJOR + 2 MINOR doc-drift sweep (peripheral test-count + baseline refreshes; §N T-V2.2 commit-estimate description refresh). **NO_NEW_CRITICAL_MAJOR.** |
| 8 | THIS COMMIT | Return report | docs(applied-research): writing-plans return report. |

ALL commits authored without `Co-Authored-By` trailer per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15). Cumulative **~445+ ZERO Co-Authored-By footer streak** preserved.

---

## §2 Codex MCP adversarial-critic chain summary

Chain ran **6 rounds to convergence**; verdict at R6: **NO_NEW_CRITICAL_MAJOR**.

| Round | Critical | Major | Minor | Verdict | Disposition |
|-------|----------|-------|-------|---------|-------------|
| R1 | 0 | 7 | 2 | ISSUES_FOUND | All 7 major + 1 minor RESOLVED inline (`21cc950`) |
| R2 | 0 | 3 | 3 | ISSUES_FOUND | All 3 major + 3 minor RESOLVED inline (`947552d`) |
| R3 | 0 | 3 | 2 | ISSUES_FOUND | All 3 major + 2 minor RESOLVED inline (`7b20fd4`) |
| R4 | 0 | 2 | 1 | ISSUES_FOUND | All 2 major + 1 minor RESOLVED inline (`08322ac`) |
| R5 | 0 | 1 | 3 | ISSUES_FOUND | All 1 major + 3 minor RESOLVED inline (`f39b62f`) |
| R6 | 0 | 0 | 2 | **NO_NEW_CRITICAL_MAJOR** | 2 minor doc-drift items RESOLVED for cleanliness (`41831a7`) |
| **Cumulative** | **0** | **16** | **13** | **CONVERGED** | **ALL 29 findings RESOLVED in-place; ZERO accepted-as-rationale** |

### §2.1 Notable Codex-caught defects against actual code

Codex MCP adversarial-critic verified plan claims against actual production code; surfaced REAL defects:

- **R1.M1**: SQL `WHERE evaluation_run_id IN (:eval_run_ids)` not bindable per Python sqlite3 (cannot bind list into single placeholder). V1 precedent at `research/harness/aplus_sensitivity/sweep.py:89-95` uses dynamic `?` expansion. V2 plan now mirrors.
- **R1.M2**: `cfg.archive.prices_cache_dir` does not exist; actual config path is `cfg.paths.prices_cache_dir` per `swing/config.py:17` + `swing/config.py:456`. `cfg.archive` only holds `archive_history_days` per `swing/config.py:188-199`.
- **R1.M3**: L2 LOCK import-graph mock missed indirect yfinance via `swing.data.ohlcv_archive` (which imports yfinance at `swing/data/ohlcv_archive.py:47`). V2 plan now sentinel-blocks 4 modules + asserts `sys.modules` absence post-V2-import.
- **R1.M4**: L2 LOCK file-open mock too narrow — only spied `pd.read_parquet`. Brief §3.5 required `Path.open` or equivalent boundary. V2 plan now spies 4 boundaries (`pd.read_parquet` + `pathlib.Path.open` + `builtins.open` + `pyarrow.parquet.read_table`).
- **R1.M5**: `evaluate_one` return-annotation assertion via `inspect.signature(...).return_annotation` overreaches under `from __future__ import annotations` at `swing/evaluation/evaluator.py:2`. Raw annotation is STRING form; must use `typing.get_type_hints` to resolve to class object.
- **R1.M6**: Sub-bundle commit-budget not honored — initial plan had 1 commit per task (7 total) vs brief §2.1 prescribed ~42-65. NEW §G.0 commit-cadence preface enumerates per-test commit discipline; parametrize-consolidated commits land at ~50-60 (within brief range).
- **R1.M7**: Test budget undercount — initial ~68 enumerated <14 tests per row; recalibrated to ~84.
- **R2.M1**: BatchContext reconstruction omitted candidate-not-in-universe tickers; production `compute_rs` at `swing/evaluation/rs.py:65-85` returns `'fallback_spy'` (not `'unavailable'`) for ticker absent from universe but with returns data; TT8 at `swing/evaluation/criteria/trend_template.py:125-145` consumes that fallback. V2 plan now requires `candidate_tickers` param to `build_eval_run_cohort`.
- **R2.M2**: sqlite3 connection not enforced read-only — V1 precedent uses plain `sqlite3.connect(str(db_path))` (read/write). V2 plan now requires URI `mode=ro` for defense-in-depth (any accidental INSERT raises `sqlite3.OperationalError`).
- **R2.M3**: `Config.from_defaults` purity claim wrong — reads tracked `swing.config.toml` per `swing/config.py:399-407+437-438`; was claimed PURE.
- **R3.M1**: `_RS_FALLBACK_MIN_BARS = 60` hardcoded — wrong for `rs.horizon_weeks=14` substitution (should be 70 trading days). Production uses `bars_needed = horizon_weeks * 5` per `swing/pipeline/runner.py:1060-1077`. V2 plan now scales dynamically.
- **R3.M2**: `Config.from_defaults` cascade claim wrong — R2.M3 fix incorrectly added user-config.toml cascade claim; actual code only reads tracked `swing.config.toml`.
- **R3.M3**: Empty eval-runs short-circuit not bound after dynamic-`IN` fix — would generate `IN ()` (invalid SQL). V1 precedent at `sweep.py:81` has explicit empty guard; V2 plan now mirrors.
- **R4.M1**: Empty-eval-runs test assigned to T-V2.1.3 (context_builder) but invokes `run_v2_sweep` which is introduced at T-V2.2. Moved.
- **R4.M2**: Empty-DB return shape internally inconsistent — said `universe_size=<resolved>` + `universe_skipped_ticker_count=<resolved>` but ALSO said no EvalRunCohort built. Amended: ALL counts zero-sentinel.
- **R5.M1**: `SweepResultV2` dataclass requires `v2_universe_hash` between `universe_size` and `entries`; empty-DB return constructor omitted it → would not build literally. Added `v2_universe_hash="empty_no_eval_runs"` sentinel.

The R1-R6 chain validates cumulative C.C lesson #6: pre-Codex review applied ALL 7 expansions + 5 NEW candidate refinements (Expansions #2 + #4 refinements per NEW gotchas #17 + #18 BINDING) AND Codex still surfaced 16 MAJOR findings, mostly cross-substrate verification gaps + dataclass shape consistency + sqlite3 binding/URI semantics + commit-cadence discipline.

---

## §3 32nd cumulative C.C lesson #6 validation per-expansion

| # | Expansion | Writing-plans-phase pre-Codex disposition | Codex R1-R6 outcome |
|---|-----------|-------------------------------------------|---------------------|
| 1 | Hardcoded-duplicate audit | APPLIED at §J.1 (`vcp.watch_max_fails = 2` hardcoded at `swing/evaluation/scoring.py:37`; V2 mirrors V1 special-case per OQ-11) | CLEAN R1-R6 |
| 2 | Brief-vs-spec + brief-vs-actual schema verification | APPLIED at §A.5 (schema v21 LOCKED; spec §A.2 verification inherited) | CLEAN at schema; Codex R1.M2 caught cfg.archive vs cfg.paths drift (NEW Expansion #2 refinement caught it) |
| 3 | Schema-CHECK vs semantic-contract gap | N/A V2 (no schema change) | N/A |
| 4 | Specific-scenario gotcha trace + SQL skeleton column verification | APPLIED at §D (SQL skeletons column-verified vs `0001_phase1_initial.sql`) | CLEAN for column-existence + JOIN-cardinality; Codex R1.M1 caught dynamic-IN-binding gap (NEW Expansion #4 refinement extends here to runtime-binding-shape verification) |
| 5 | Cross-section spec inventory grep | APPLIED at §E (5 production functions verified) | CLEAN; Codex R1.M5 caught return-annotation under postponed-annotations + R3.M1 caught horizon_weeks-scaling — both NEW Expansion #2 refinement extensions |
| 6 | Content-completeness audit | APPLIED at §O.1 self-review (every spec section + brief done-criterion mapped to plan section) | CLEAN R1-R6 |
| 7 | Cross-row semantic SCOPE audit | N/A V2 (no operator-input POST handler) | N/A |
| 8 (cand) | Per-aggregation-function UNIT audit on SQL skeletons | N/A V2 (no GROUP BY / COUNT / SUM in §D) | N/A |
| 9 (cand) | Form-render anchor lifecycle 4-dimension audit | N/A V2 (no forms / web routes) | N/A |
| **10 (cand)** | **Architecture-location audit + 5 sub-disciplines** | APPLIED at §B.1 NEW module placement + dep-surface verification | NOTABLE: R1.M3 caught L2 LOCK import sentinel insufficient — sub-discipline (a) architecture-location-vs-dep-surface mismatch (V2 dep surface needed to block 4 modules not just schwabdev). |
| **11 (cand)** | **Taxonomy propagation audit** | APPLIED at §C.5 SweepEntryV2 inherits V1 kind enum + 3 NEW skip-count fields propagated | CLEAN at enum surface; R5.M1 caught dataclass-shape propagation gap at empty-DB constructor (`v2_universe_hash` field missing) — NEW dataclass-completeness sub-discipline candidate. |
| 12 (cand) | Sibling-route audit when introducing single-anchor-binding discipline | N/A V2 (no route handlers) | N/A |
| **13 NEW (#17)** | **Expansion #2 refinement: brief-vs-actual-production-function-signature verification** | APPLIED at §E (5 production functions verified; 1 NEGATIVE verification for `read_or_fetch_archive`); 5 defensive `inspect.signature` tests in plan | NOTABLE: R1.M2 + R1.M5 + R3.M2 + R5.m1 caught function-signature / side-effect / cascade-claim defects despite pre-Codex application. **Confirms #17 BINDING value** but also indicates the refinement needs ADDITIONAL discipline: verify cascade behavior (whether helper invokes sibling helpers), NOT just signature + side-effect at the leaf level. **NEW Expansion #2 sub-refinement BANKED for 33rd cumulative validation**: cascade-call-graph verification (when production function A has documented sibling B, verify A invokes / does NOT invoke B per actual code; do not infer from naming convention). |
| **14 NEW (#18)** | **Expansion #4 refinement: SQL skeleton JOIN-cardinality + downstream-sufficiency audit** | APPLIED at §D (every SQL skeleton enumerates row-set scope + JOIN-cardinality + downstream-sufficiency + post-mutation re-check) | NOTABLE: R1.M1 caught runtime-binding-shape gap (dynamic `?` expansion required for `IN` clause; sqlite3 cannot bind list to single placeholder); R3.M3 caught empty-result-set short-circuit gap (V1 precedent missing). **Confirms #18 BINDING value** but indicates refinement needs ADDITIONAL discipline: verify runtime-binding-shape for parameterized SQL (NOT just column existence + JOIN cardinality); verify empty-result-set handling (NOT just non-empty case). **NEW Expansion #4 sub-refinement BANKED for 33rd cumulative validation**: runtime-binding-shape + empty-result-set audit. |

**Validation result: 32nd cumulative C.C lesson #6 = NOTABLE** (Expansions #2 + #4 refinements per NEW gotchas #17 + #18 surfaced ADDITIONAL refinement candidates; 2 NEW sub-refinements banked for 33rd cumulative validation):

- **NEW Expansion #2 sub-refinement candidate** (BANKED for 33rd cumulative validation): cascade-call-graph verification (when production function A has documented sibling B, verify A invokes / does NOT invoke B per actual code; do not infer from naming or docstring; cf. `Config.from_defaults` does NOT invoke `swing/config_overrides.py` user-config cascade despite naming suggesting it might).
- **NEW Expansion #4 sub-refinement candidate** (BANKED for 33rd cumulative validation): runtime-binding-shape + empty-result-set audit (when a SQL skeleton uses parameterized binds, verify the runtime binding shape — single placeholder vs dynamic expansion vs sqlite3-specific limitations; verify empty-input handling for every iteration / IN-clause).

---

## §4 V2/V3 candidates banked (refinement of brainstorming-phase ledger)

The brainstorming return report §4 banked 10 V2/V3-dependency-cited V1 simplifications. Writing-plans phase adds the following refinements + NEW candidates:

| # | V2/V3 candidate refined or banked | Dependency citation |
|---|-----------------------------------|---------------------|
| 1-10 | Brainstorming-phase candidates inherited unchanged | Per brainstorming return report §4 |
| **11 NEW** | sqlite3 URI mode=ro hardening as cumulative discipline pattern for ALL future research-branch harnesses reading operator's swing.db | Banked Codex R2.M2; consider promoting to research-branch BINDING pattern when 2nd research harness lands |
| **12 NEW** | Dynamic `?` IN-clause expansion as cumulative pattern for ALL Python sqlite3 multi-row queries (not specific to V2) | Banked Codex R1.M1; consider adding to CLAUDE.md SQLite gotcha family alongside existing `INSERT OR REPLACE` cascade-wipe + `executescript` implicit-COMMIT lessons |
| **13 NEW** | 4-boundary file-open mock + 4-module import sentinel pattern as cumulative L2 LOCK reinforcement template | Banked Codex R1.M3 + R1.M4; consider promoting to BINDING template for any future research-branch arc that touches OHLCV archive |
| **14 NEW** | Empty-result-set short-circuit discipline as cumulative pattern for harness invocations against operator DB | Banked Codex R3.M3 + R4.M2 + R5.M1; consider adding to CLAUDE.md gotcha catalog as "Empty-input handling discriminating test" |
| **15 NEW** | typing.get_type_hints over inspect.signature for return-annotation locks under postponed annotations | Banked Codex R1.M5; consider extending Expansion #2 refinement (NEW gotcha #17) to mention this Python-3.10+ postponed-annotation interaction |

---

## §5 Cumulative streaks preserved

- **ZERO `Co-Authored-By` footer trailer**: **~445+ commits cumulative** through this dispatch (8 commits added; ZERO with co-author trailer).
- **Schema v21 UNCHANGED**: writing-plans docs-only; no migration files touched. Verified via `git diff --name-only main..HEAD -- swing/data/migrations/` → empty.
- **Baseline 5778 fast tests UNCHANGED**: writing-plans docs-only; no test files touched (test plans in `tests/research/test_aplus_v2_ohlcv_*.py` are described in §G + §H but NOT created — that's executing-plans phase). V2 executing-plans phase will land **+84 fast tests** (~5862 total post-V2-ship per §H R5 recalibration).
- **ZERO new Schwab API calls (L2 LOCK preserved)**: V2 plan explicitly enumerates 5 BINDING discriminating tests per §K (file-open mock + import-graph mock + byte-checksum + `read_or_fetch_archive` signature lock + V2 import-grep) covering 4 file-open boundaries + 4-module import sentinel graph.
- **ZERO production code changes through writing-plans phase**: only `docs/superpowers/plans/...` touched in this dispatch arc (verified via `git diff --name-only f8cafd9..HEAD`). The V2 CLI subcommand registration in `swing/cli.py` is BANKED for executing-plans phase per OQ-17 explicit carve-out.

---

## §6 Inline self-verification

Per dispatch brief §8 BINDING handback discipline:

### §6.1 Ruff check

Writing-plans docs-only; ZERO Python files touched. Verified via `git diff --name-only f8cafd9..HEAD` → only `docs/superpowers/plans/2026-05-23-v2-ohlcv-criterion-evaluator-plan.md` + (this commit) `docs/v2-ohlcv-criterion-evaluator-writing-plans-return-report.md`. ZERO new ruff items introduced.

### §6.2 Schema unchanged at v21

Verified: ZERO migration files touched in writing-plans phase. v21 LOCKED per spec §A.2.

### §6.3 Test baseline matches pre-writing-plans

Writing-plans docs-only; ZERO test files touched. Baseline 5778 fast tests UNCHANGED through this dispatch phase. Executing-plans phase will land +84 fast tests (~5862 total) per §H R5 recalibration.

### §6.4 ZERO new Schwab API calls

V2 plan preserves L2 LOCK by enumerating BINDING discriminating tests at §K covering 4 file-open boundaries + 4-module import sentinel graph + V2 source-grep. The actual L2 LOCK tests are written in executing-plans phase per the per-task plan; this writing-plans phase only specifies them.

### §6.5 ZERO Co-Authored-By footer

All 8 commits in this dispatch arc authored without `Co-Authored-By` trailer. Cumulative **~445+ ZERO-streak preserved**. Citation in each commit per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15).

---

## §7 Forward-binding lessons banked

1. **NEW Expansion #2 sub-refinement candidate** (banked for 33rd cumulative validation): cascade-call-graph verification — when production function A has documented sibling B, verify A invokes / does NOT invoke B per actual code; do not infer from naming convention or docstring (e.g., `Config.from_defaults` does NOT invoke `swing/config_overrides.py` user-config cascade despite the existence of the sibling; only `swing/cli.py` Click-handler entry points invoke the cascade).
2. **NEW Expansion #4 sub-refinement candidate** (banked for 33rd cumulative validation): runtime-binding-shape + empty-result-set audit — when a SQL skeleton uses parameterized binds, verify the runtime binding shape (Python sqlite3 cannot bind list to single `:name` placeholder; requires dynamic `?` expansion); verify empty-input handling for every iteration / IN-clause / aggregate.
3. **sqlite3 URI mode=ro discipline** as defense-in-depth for any future research-branch harness reading operator's swing.db. Pattern: `db_path.resolve().as_uri() + "?mode=ro"`; `sqlite3.connect(uri, uri=True)`; discriminating test asserts `sqlite3.OperationalError "attempt to write a readonly database"` on attempted INSERT.
4. **4-boundary file-open mock + 4-module import sentinel template** for L2 LOCK reinforcement. Pattern: spy on `pd.read_parquet` + `pathlib.Path.open` + `builtins.open` + `pyarrow.parquet.read_table`; sentinel-block `yfinance` + `schwabdev` + `swing.integrations.schwab` + `swing.data.ohlcv_archive`; post-import `sys.modules` absence assertion verifies indirect imports don't load real modules.
5. **typing.get_type_hints over inspect.signature for return-annotation locks** under `from __future__ import annotations` (Python 3.10+). Raw `inspect.signature(...).return_annotation` is STRING form for forward references; `typing.get_type_hints` resolves to class object.
6. **Empty-result-set short-circuit discipline** for harness invocations against operator DB — V1 precedent at `research/harness/aplus_sensitivity/sweep.py:81` is BINDING template. Discriminating test: invoke harness against empty DB + mock-assert downstream functions NOT called + assert all sentinel zero/empty values in result envelope.
7. **`v2_universe_hash` sentinel pattern** for empty-DB return constructor — when a dataclass has required fields that depend on a build step (universe hash from universe load), the empty-short-circuit return MUST provide a sentinel value (e.g., `"empty_no_eval_runs"`) for those fields; dataclass-shape consistency check via Codex R5.M1 caught this pattern.

---

## §8 V1 simplifications enumerated for ledger

Per cumulative T2.SB6b lesson "V1 simplification banking discipline": every V1 placeholder/simplification in the plan is enumerated with V2.5/V3 dependency at §J.2 + §K.5. Plan inherits the 10 brainstorming-phase candidates + adds 5 NEW writing-plans-phase patterns per §4 above.

---

## §9 Handback to operator

V2 OHLCV criterion-evaluator harness writing-plans phase SHIPPED. Plan converged via Codex MCP adversarial-critic at R6 NO_NEW_CRITICAL_MAJOR; ALL 16 MAJOR + 13 MINOR findings RESOLVED in-place; ZERO accepted-as-rationale.

### §9.1 Orchestrator next-steps per dispatch brief §8

- QA implementer product per `feedback_orchestrator_qa_implementer_product` BINDING (verify file:line + shipped-behavior + cumulative gotcha citations + Codex R1-R6 resolution chain against reality on disk).
- Merge `applied-research-v2-ohlcv-criterion-evaluator-writing-plans` `--no-ff` to `main`; push.
- Post-merge housekeeping bundle (CLAUDE.md line 3 refresh — V2 OHLCV writing-plans SHIPPED status update + any NEW gotchas if surfaced + phase3e-todo.md NEW top entry + orchestrator-context.md current state refresh + Prior demote + archive-split per size-check trigger).
- Draft executing-plans dispatch brief consuming the operator-affirmed writing-plans plan.
- Provide inline implementer dispatch prompt for executing-plans phase.
- Note: Turn E may or may not finish executing-plans in same orchestrator turn depending on context budget; another shift (Turn F) may be needed before T-V2.5 ships + operator gates the V2 harness output.

### §9.2 Summary

V2 OHLCV criterion-evaluator harness writing-plans plan is the BINDING implementation specification for the FIRST applied-research arc post-Phase-13-FULLY-CLOSED. Plan covers all 15 sections §A-§O per dispatch brief §5 done criteria + §O self-review. 5-sub-bundle decomposition (T-V2.1..T-V2.5) per spec §M.1 with bite-sized TDD step structure + commit message templates + ~84 NEW fast tests distributed per §H (parametrize-consolidated bound ~68-74).

Codex MCP adversarial-critic chain ran 6 rounds; ALL findings resolved in-place; chain CONVERGED at R6 NO_NEW_CRITICAL_MAJOR. The chain validated cumulative C.C lesson #6 with NEW Expansion #2 + #4 sub-refinement candidates banked for 33rd cumulative validation.

Schema v21 UNCHANGED; baseline 5778 fast tests UNCHANGED through writing-plans phase; ZERO new Schwab API calls; ZERO Co-Authored-By footer; ZERO production code changes. ~445+ ZERO Co-Authored-By footer streak preserved.

Ready for operator review + orchestrator-side merge + executing-plans dispatch brief drafting.

---

*End of V2 OHLCV criterion-evaluator harness writing-plans return report. Plan at [`docs/superpowers/plans/2026-05-23-v2-ohlcv-criterion-evaluator-plan.md`](superpowers/plans/2026-05-23-v2-ohlcv-criterion-evaluator-plan.md) (2602 lines; 15 sections §A-§O). Codex chain CONVERGED at R6 NO_NEW_CRITICAL_MAJOR. 32nd cumulative C.C lesson #6 validation NOTABLE (Expansions #2 + #4 refinements per NEW gotchas #17 + #18 BINDING applied + Codex still surfaced 16 MAJOR findings — confirms cumulative C.C lesson #6 + 2 NEW sub-refinement candidates banked for 33rd validation). Final HEAD: `41831a7`.*
