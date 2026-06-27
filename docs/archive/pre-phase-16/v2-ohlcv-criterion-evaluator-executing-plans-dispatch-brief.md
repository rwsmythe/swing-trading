# V2 OHLCV Criterion-Evaluator Harness — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the V2 OHLCV executing-plans implementer. No prior conversation context.

**Mission:** Execute the 5-sub-bundle scope (T-V2.1..T-V2.5) per the operator-confirmed writing-plans plan + 18 OQ dispositions (ALL LOCKED per operator triage 2026-05-23 PM with ZERO amendments through brainstorming + writing-plans phases).

**Writing-plans plan (BINDING substrate):** [`docs/superpowers/plans/2026-05-23-v2-ohlcv-criterion-evaluator-plan.md`](superpowers/plans/2026-05-23-v2-ohlcv-criterion-evaluator-plan.md) at main HEAD `34f177c` (2602 lines; 15 sections §A-§O including self-review; Codex R6 NO_NEW_CRITICAL_MAJOR; 0 CRITICAL + 16 MAJOR + 13 MINOR ALL RESOLVED in-place; ZERO accepted-as-rationale). **READ END-TO-END.** Plan §G is BINDING per-task specification with bite-sized TDD step structure.

**Brainstorming spec (PRECEDENT substrate):** [`docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md`](superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md) at main HEAD `362fe18` (1086 lines; 14 sections §A-§N).

**Brief:** `docs/v2-ohlcv-criterion-evaluator-executing-plans-dispatch-brief.md` (this file).

**Sequencing:** V2 OHLCV brainstorming SHIPPED 2026-05-23 at `362fe18` + housekeeping at `bd08644` + Turn D handoff at `08ea67e` + writing-plans dispatch brief at `f8cafd9` + writing-plans merge at `34f177c` + post-merge housekeeping at `946f476` + this brief commit. Output completes the FIRST Applied Research Tranche 1 arc post-Phase-13-FULLY-CLOSED.

**Branch:** `applied-research-v2-ohlcv-criterion-evaluator-executing-plans` — branches from main HEAD after this brief lands.

**Worktree:** `git worktree add .worktrees/applied-research-v2-ohlcv-criterion-evaluator-executing-plans applied-research-v2-ohlcv-criterion-evaluator-executing-plans`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Workflow:** `copowers:executing-plans` skill (wraps `superpowers:subagent-driven-development` with adversarial Codex MCP review). Expected 2-5 Codex rounds.

**Expected duration:** ~8-16 hours operator-paced. T-V2.2 is the largest sub-bundle (sweep orchestration + baseline parity + failure isolation + caches; ~12-18 commits). Plan §G total: ~50-69 commits via parametrize-consolidation OR ~84-91 commits at raw 1-commit-per-test ceiling.

---

## §0 Read first (in this order)

1. **`docs/superpowers/plans/2026-05-23-v2-ohlcv-criterion-evaluator-plan.md`** at HEAD `34f177c` — PRIMARY SUBSTRATE. 15 sections §A-§O. Especially:
   - §A Status + scope (18 OQ dispositions verbatim; production read-only invariant with OQ-17 CLI carve-out; schema discipline LOCK; streaks preserved)
   - §B Per-sub-bundle file map + dependency graph (5 NEW research/ modules + 1 MODIFIED swing/cli.py; sequential dispatch T-V2.1 → T-V2.2 → T-V2.3 → T-V2.4 → T-V2.5)
   - §C Module function signatures + class shapes (BINDING per Codex R1-R6; ~740 lines of dataclass + function signatures verified against actual production code)
   - §D SQL skeleton verification (Expansion #4 refinement BINDING per NEW gotcha #18; dynamic `?` IN-clause expansion per Codex R1.M1; URI mode=ro per R2.M2; horizon_weeks-scaled bars_needed per R3.M1; empty-eval-runs short-circuit per R3.M3)
   - §E Production function signature verification (Expansion #2 refinement BINDING per NEW gotcha #17; `evaluate_one` return-annotation via `typing.get_type_hints` under postponed annotations per Codex R1.M5; `Config.from_defaults` purity correction per R2.M3+R3.M2)
   - §F L2 LOCK reinforcement (3 BINDING discriminating tests per dispatch brief §3.5; 4 file-open boundaries; 4-module import sentinel graph)
   - §G Per-task acceptance criteria + bite-sized step structure (BINDING — every TDD slice is ONE commit per §G.0 commit-cadence preface; parametrize-consolidation lands at ~50-69 commits)
   - §H Test scope per-task budget (Codex R1.M7 RESOLVED — recalibrated to ~84 fast tests distributed across 7 test files)
   - §I OQ #9 + OQ #13 work-items resolved (--max-runtime-seconds default UNSET; 7 typed exceptions co-located at `research/harness/aplus_v2_ohlcv_evaluator/exceptions.py`)
   - §J Forward-binding lessons inherited (all cumulative gotchas + 7 expansions + 5 NEW candidate refinements applied)
   - §K L2 LOCK reinforcement summary (3 discriminating tests + 2 defensive tests; BINDING)
   - §L Research-branch coordination (method-record extension; first study writeup; phase-0-tasks update)
   - §M Closure procedure (T-V2.5 closer commit message template + post-V2-ship orchestrator handback procedure)
   - §N Per-sub-bundle Codex MCP round-budget expectation (T-V2.2 highest; T-V2.5 lowest)
   - §O Self-review (Codex chain validation; placeholder scan; internal consistency; scope check; ambiguity check)

2. **`docs/v2-ohlcv-criterion-evaluator-writing-plans-return-report.md`** at `75a2649` — Codex chain shape (R1-R6 with 6 fix bundles); 5 NEW writing-plans-phase patterns banked; 6 forward-binding lessons; NEW Expansion #2 + #4 sub-refinement candidates banked (now CLAUDE.md gotchas #19 + #20).

3. **`docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md`** at `362fe18` — Brainstorming spec (1086 lines; 14 sections §A-§N). Use as PRECEDENT substrate when plan references "per spec §X". DO NOT modify in-place.

4. **`docs/v2-ohlcv-criterion-evaluator-writing-plans-dispatch-brief.md`** at `f8cafd9` — Writing-plans dispatch brief (this dispatch's parent). Inherits 18 OQ dispositions verbatim.

5. **`docs/v2-ohlcv-criterion-evaluator-brainstorming-dispatch-brief.md`** at `acaf305` + **`docs/v2-ohlcv-criterion-evaluator-brainstorm-return-report.md`** at `8532949` — predecessor briefs (reference-only).

6. **`research/method-records/aplus-criteria-calibration.md`** — PRIMARY substrate for T-V2.5 method-record extension per plan §L + spec §K.

7. **`research/harness/aplus_sensitivity/`** (variables.py + sweep.py + output.py + run.py + README.md) — V1 precedent. V2 architecture mirrors with NEW additions per plan §B file map.

8. **`research/harness/earnings_proximity/`** + **`research/studies/earnings-proximity-exclusion.md`** + **`research/method-records/_template.md`** — research-branch precedent for first-applied-research-arc shape.

9. **`CLAUDE.md`** at repo root — project conventions + **20 cumulative gotchas** (was 18 at writing-plans dispatch; +2 = #19 + #20 banked at writing-plans housekeeping). ESPECIALLY relevant for V2 executing-plans phase:
   - **#19 NEW — Expansion #2 sub-refinement: cascade-call-graph verification** (BINDING for 33rd cumulative validation; banked at V2 OHLCV writing-plans Codex R1.M2+R1.M5+R2.M3+R3.M2+R5.m1)
   - **#20 NEW — Expansion #4 sub-refinement: runtime-binding-shape + empty-result-set audit** (BINDING for 33rd cumulative validation; banked at V2 OHLCV writing-plans Codex R1.M1+R3.M3+R4.M2+R5.M1)
   - **#17 — Expansion #2 refinement: brief-vs-actual-production-function-signature verification** (banked at V2 OHLCV brainstorming Codex R1.M1+M2)
   - **#18 — Expansion #4 refinement: SQL skeleton JOIN-cardinality + downstream-sufficiency audit** (banked at V2 OHLCV brainstorming Codex R1.C1+R4.M2)
   - **#14 — Architecture-location audit + 5 sub-disciplines (Expansion #10)** (DIRECTLY APPLIES per plan §B.1; V2 introduces NEW module under `research/harness/aplus_v2_ohlcv_evaluator/`)
   - **#15 — Taxonomy propagation audit (Expansion #11)** (DIRECTLY APPLIES per plan §C; `SweepEntryV2.kind` inherits V1 enum + 3 NEW skip-count fields must propagate)
   - **#12 — `date.fromisoformat()` discipline** (DIRECTLY APPLIES; plan §C reads `evaluation_runs.data_asof_date` TEXT → `date` conversion at the SQL boundary)
   - **Synthetic-fixture-vs-production-emitter shape drift** (4 cumulative instances; DIRECTLY APPLIES — V2 fixtures MUST shape-match NEW `ohlcv_reader.py` reads AND `swing.data.repos.candidates.insert_candidates` persistence)
   - **Service-layer ValueErrors must be wrapped at CLI boundary** (DIRECTLY APPLIES at V2 CLI per plan §G T-V2.4.3)
   - **`Literal[...]` type hints are NOT runtime-enforced** (DIRECTLY APPLIES to `SweepEntryV2.kind`; same `__post_init__` pattern as V1)
   - **Windows PowerShell stdout cp1252 ASCII-only** (DIRECTLY APPLIES to V2 CLI output paths per plan §G T-V2.4.7 cp1252 subprocess smoke test)

10. **`docs/orchestrator-context.md`** "Currently in-flight work" — current state reflects V2 OHLCV writing-plans SHIPPED + executing-plans dispatch in-flight.

---

## §1 OQ dispositions (BINDING; inherited verbatim from writing-plans brief §1)

Per operator-paired triage 2026-05-23 PM (Turn D): **ALL 18 OQs LOCKED per RECOMMEND with ZERO amendments**, preserved verbatim through brainstorming + writing-plans phases.

### §1.1 Core architecture (OQ-1 through OQ-8) — inherited from writing-plans brief

| OQ | Disposition LOCKED |
|---|---|
| OQ-1 OHLCV reconstruction scope | Direct Shape A yfinance read via NEW `ohlcv_reader.py` wrapper (bypasses `read_or_fetch_archive`; NEVER opens schwab_api parquet; legacy `{ticker}.parquet` fallback). |
| OQ-2 Per-criterion evaluator interface | cfg-substitution via `dataclasses.replace` + production `evaluate_one(ctx)` end-to-end. Single-variable downstream propagation preserved. `vcp.watch_max_fails` special-case mirrors V1 per spec §E.3. |
| OQ-3 Sweep range strategy | Inherit V1 5-point grid per V2.1 §IV.B parsimony. |
| OQ-4 Output format | Hybrid: V1 12-col matrix (9 V1 cols + 3 NEW skip cols) + headline + per-variable drill-down + V1↔V2 parity section + both-exist diagnostic banner per spec §G. |
| OQ-5 Scope discipline | ALL 15 inert threshold variables in one dispatch (NOT phased). |
| OQ-6 Validation universe | Reuse S3's 5681 candidates / 63 eval_runs for V1↔V2 reproducibility. |
| OQ-7 Cross-coupling | 1D per V2.1 §IV.B parsimony. 2D+ deferred V3+. |
| OQ-8 Method-record promotion criteria | 3-tier research→shadow→production ladder per spec §K.3. |

### §1.2 Substrate-surfaced (OQ-9 through OQ-13)

| OQ | Disposition LOCKED |
|---|---|
| OQ-9 Performance budget cap | Default UNSET + `--max-runtime-seconds N` CLI flag for partial-run capability. Acceptance target: <60 min on operator hardware for full 5681/63/17/5 universe. |
| OQ-10 V2 CLI surface name | `swing diagnose aplus-sensitivity-v2`. Back-compat preserved. |
| OQ-11 `vcp.watch_max_fails` hardcode handling | Mirror V1's special-case substitution per spec §E.3 for V2 ship. BANK V2.5 candidate per plan §J.2. |
| OQ-12 Schwab API L2 LOCK preservation | yfinance-only via direct Shape A `{ticker}.yfinance.parquet` read. 5 BINDING discriminating tests per plan §F + §K (3 BINDING + 2 defensive; 4 file-open boundaries + 4-module import sentinel graph). |
| OQ-13 OHLCV coverage failure attribution mode | Skip + report. Single `ohlcv_coverage_skip_count` scalar per V2 invocation. `OhlcvCoverageError` typed exception at `research/harness/aplus_v2_ohlcv_evaluator/exceptions.py` per plan §I. |

### §1.3 Codex-surfaced architectural (OQ-14 through OQ-18)

| OQ | Disposition LOCKED |
|---|---|
| OQ-14 RS universe reconstruction at historical asof_date | Current-universe snapshot for V2 ship. V3+ candidate: persist per-eval_run universe snapshots. |
| OQ-15 `current_equity` surrogate for risk gate recompute | Per-eval_run-historical from `account_equity_snapshots` IF available; fall back to latest snapshot OTHERWISE; mark tier-2 candidates with `bucket_via_surrogate=True`. |
| OQ-16 OHLCV archive read strategy | Direct Shape A parquet read via NEW V2 wrapper `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py`. |
| OQ-17 CLI subcommand registration as read-only carve-out | Explicit minimal carve-out (35-60 lines in `swing/cli.py` mirroring V1 at `swing/cli.py:4748-4787`). SOLE production-`swing/` modification. Discriminating gate: `git diff swing/ --stat` after V2 ship shows ONLY `swing/cli.py` modified. |
| OQ-18 Both-exist legacy/Shape A archive read policy | Shape A wins unconditionally + per-ticker diagnostic surface (`both_exist_shape_a_wins_count` + per-ticker affected list + warning banner). |

---

## §1.5 Amendments (BINDING; inherited verbatim from writing-plans brief §1.5)

**NONE.** Operator accepted all 18 OQ RECOMMENDs verbatim during Turn D triage. Preserved through brainstorming → writing-plans → executing-plans phases. This is a strong validation signal for the brainstorming + writing-plans Codex chain crispness.

---

## §2 Scope inheritance from writing-plans plan §G (BINDING)

Per plan §G + §M.1 BINDING decomposition: 5 sub-bundle structure T-V2.1..T-V2.5 with bite-sized TDD step structure. Do NOT re-derive task structure; plan §G is authoritative per-test step + commit cadence + acceptance criteria.

### §2.1 Per-sub-bundle scope summary (plan §G is BINDING)

| Sub-bundle | Plan §B ref | Brief description | Est. commits | Tests |
|---|---|---|---|---|
| T-V2.1 | §B.1 rows 1-5 | `exceptions.py` + `ohlcv_reader.py` + `cfg_substitution.py` + `context_builder.py` + tests | ~10-15 (parametrize-consolidation) OR ~26 (raw 1-commit-per-test ceiling) | ~30 (~12+~12+~6) |
| T-V2.2 | §B.1 row 6 | `sweep.py` + tests (largest sub-bundle; baseline parity + failure isolation + caches; `vcp.watch_max_fails` special-case) | ~12-18 OR ~15 raw | ~17 |
| T-V2.3 | §B.1 row 7 | `output.py` + tests (CSV + markdown + headline + drill-down + V1↔V2 parity + both-exist banner + manifest) | ~8-12 OR ~11 raw | ~10 |
| T-V2.4 | §B.1 rows 8-9 | `run.py` + CLI subcommand registration in `swing/cli.py` + tests (argparse + ClickException wrapping + cp1252 stdout smoke + git diff swing/ gate) | ~6-10 OR ~10 raw | ~11 |
| T-V2.5 | §B.1 rows 10-13 | Method-record extension + first study writeup + operator smoke run + closer + integration tests | ~6-10 OR ~7 raw | ~6 |
| **Total** | | | **~42-65 (parametrize-consolidation) OR ~69-84-91 (raw)** | **~84** |

### §2.2 Sequential dispatch (plan §M.2 BINDING)

**NO concurrent dispatch.** Strictly sequential per dependency graph at plan §B.2:

```
T-V2.1 (exceptions + ohlcv_reader + cfg_substitution + context_builder)
   ↓
T-V2.2 (sweep.py — consumes ohlcv_reader + context_builder + cfg_substitution)
   ↓
T-V2.3 (output.py — consumes SweepEntryV2 from sweep.py)
   ↓
T-V2.4 (run.py + CLI registration — consumes sweep.run_v2_sweep + output writers)
   ↓
T-V2.5 (method-record extension + study writeup + operator smoke + closer)
```

Single-implementer sequential via `copowers:subagent-driven-development` per project workflow precedent. Cross-sub-bundle state isolation NOT a feature this arc needs.

### §2.3 Commit-cadence preface BINDING per plan §G.0

Every logical TDD slice (test + minimal implementation expansion + passing test) is ONE commit per plan §G.0 (Codex R1.M6 RESOLVED). Where tests share fixtures + a single implementation expansion, parametrize-consolidation may bundle to ONE commit per logical cluster. Per-sub-bundle wrap commits land AFTER all per-test slices.

---

## §3 Watch items + cumulative discipline (BINDING for executing-plans phase)

### §3.1 Pre-Codex 7-expansion + 5 NEW candidate refinements + 2 NEW sub-refinements (33rd cumulative C.C lesson #6 validation expected)

Executing-plans phase pre-Codex review applies ALL 7 expansions + 5 NEW candidate refinements + 2 NEW sub-refinements:

1. **Expansion #1** — hardcoded-duplicate audit (T3.SB2 hotfix `cf3c489`)
2. **Expansion #2** — brief-vs-spec + brief-vs-actual schema verification
3. **Expansion #3** — schema-CHECK-vs-semantic-contract gap (N/A V2; no schema change)
4. **Expansion #4** — SQL skeleton column verification
5. **Expansion #5** — cross-section spec inventory grep
6. **Expansion #6** — content-completeness audit
7. **Expansion #7** — cross-row semantic SCOPE audit (N/A V2; no operator-input POST handler)
8. **Expansion #8 candidate** — SQL aggregation UNIT audit (N/A V2; no GROUP BY/COUNT/SUM in plan §D)
9. **Expansion #9 candidate** — form-render anchor lifecycle 4-dimension audit (N/A V2; no forms/web routes)
10. **Expansion #10 candidate (BINDING)** — Architecture-location audit + 5 sub-disciplines. DIRECTLY APPLIES at plan §B.1 (NEW module placement); plan §C dependency surface verification.
11. **Expansion #11 candidate (BINDING)** — Taxonomy propagation audit. DIRECTLY APPLIES at plan §C `SweepEntryV2` kind enum + 3 NEW skip-count fields.
12. **Expansion #12 candidate** — Sibling-route audit (N/A V2; no route handlers)
13. **NEW Expansion #2 refinement (BINDING since 32nd; CLAUDE.md gotcha #17)** — brief-vs-actual-production-function-signature verification. Plan §E enumerates 5 production-function signature locks; executing-plans MUST keep them honored at code-write time.
14. **NEW Expansion #4 refinement (BINDING since 32nd; CLAUDE.md gotcha #18)** — SQL skeleton JOIN-cardinality + downstream-sufficiency audit. Plan §D verified at writing-plans phase; executing-plans MUST execute the SQL exactly per plan §D shapes (dynamic `?` IN-clause expansion; URI mode=ro; horizon_weeks scaling; empty short-circuit).
15. **NEW Expansion #2 sub-refinement (BINDING for 33rd; CLAUDE.md gotcha #19)** — cascade-call-graph verification. **Pre-empt at executing-plans**: when writing production-function callsites, grep the function's source body for documented sibling-helper invocations + verify CASCADE behavior matches actual code (NOT documentation/naming). Use `inspect.signature` AND `typing.get_type_hints` for return-annotation verification under postponed annotations.
16. **NEW Expansion #4 sub-refinement (BINDING for 33rd; CLAUDE.md gotcha #20)** — runtime-binding-shape + empty-result-set audit. **Pre-empt at executing-plans**: for every parameterized SQL execution, verify (a) runtime binding shape per parameter; (b) empty-input handling; (c) empty-result dataclass shape consistency with required-field sentinel values.

### §3.2 Cumulative gotcha set (20 cumulative)

Per CLAUDE.md updates through `946f476`:
- (1-8) Original cumulative discipline through Phase 11
- (9) SQL aggregation UNIT audit (Expansion #8) — T2.SB6c writing-plans
- (10) Existing-field reuse audit before claiming new dataclass fields — T2.SB6c writing-plans
- (11) Template-rendering surface audit before claiming "no template edit needed" — T2.SB6c writing-plans
- (12) `date.fromisoformat()` discipline for cross-type-boundary calls — T2.SB6c writing-plans
- (13) Form-render anchor lifecycle audit (Expansion #9) — T2.SB6c executing-plans
- (14) Architecture-location audit + 5 sub-disciplines (Expansion #10) — T4.SB brainstorming
- (15) Taxonomy propagation audit (Expansion #11) — T4.SB writing-plans
- (16) Sibling-route audit (Expansion #12) — T4.SB executing-plans
- (17) Expansion #2 refinement: brief-vs-actual-production-function-signature verification — V2 OHLCV brainstorming
- (18) Expansion #4 refinement: SQL skeleton JOIN-cardinality + downstream-sufficiency audit — V2 OHLCV brainstorming
- **(19) NEW Expansion #2 sub-refinement: cascade-call-graph verification** — V2 OHLCV writing-plans
- **(20) NEW Expansion #4 sub-refinement: runtime-binding-shape + empty-result-set audit** — V2 OHLCV writing-plans

ALL 20 gotchas BINDING for executing-plans-phase pre-Codex discipline. The 4 NEW V2-banked gotchas #17-#20 specifically apply to V2 dispatch's own function-invocation + SQL-execution surfaces — executing-plans phase MUST self-apply them at every callsite written.

### §3.3 Cumulative process discipline

- **NO Co-Authored-By footer** — ~448+ cumulative streak through housekeeping `946f476`. Cite per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15) in every commit message.
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing`
- **ASCII-only on runtime CLI paths** + markdown narrative text (Windows cp1252 stdout safety; cumulative gotcha from Phase 12 C.D operator-witnessed gate; T-V2.4.7 ships discriminating subprocess smoke)
- **TDD per task** via `superpowers:test-driven-development` — each TDD slice is ONE commit per plan §G.0
- **Edit tool for per-file edits**
- **Cite the discipline in commit messages** per cumulative precedent

### §3.4 Schema discipline (LOCK)

Schema v21 LOCKED. V2 does NOT touch migrations. Plan §A.5 enumerates this LOCK + discriminating gate at T-V2.5 closer: `git diff swing/data/migrations/ --stat` after V2 ship shows ZERO files modified.

### §3.5 L2 LOCK reinforcement (5 BINDING discriminating tests per plan §F + §K)

The L2 LOCK invariant (ZERO new Schwab API calls; ZERO reads of `{ticker}.schwab_api.parquet`) MUST be preserved + REINFORCED via 5 BINDING discriminating tests in `tests/research/test_aplus_v2_ohlcv_reader.py`:

- **Test 1 (file-open mock)**: spy on 4 boundaries (`pd.read_parquet` + `pathlib.Path.open` + `builtins.open` + `pyarrow.parquet.read_table`); assert V2 NEVER opens `{ticker}.schwab_api.parquet` for any synthetic test ticker
- **Test 2 (import-graph sentinel)**: mock 4 modules (`yfinance` + `schwabdev` + `swing.integrations.schwab` + `swing.data.ohlcv_archive`); assert V2 modules NEVER load any sentinel module via `sys.modules` post-import absence
- **Test 3 (byte-checksum)**: plant both `{synthetic_ticker}.yfinance.parquet` AND `{synthetic_ticker}.schwab_api.parquet`; run V2; byte-checksum compare V2's consumed bytes against yfinance file ONLY
- **Test 4 (defensive — `read_or_fetch_archive` signature lock per Expansion #2 refinement)**: `inspect.signature(read_or_fetch_archive)` assertion verifies V2 NOT depending on the rejected `prefer_source` kwarg
- **Test 5 (defensive — V2 import-grep)**: grep V2 source files; assert ZERO `import schwabdev`, `import yfinance`, `from swing.integrations.schwab import`, `from swing.data.ohlcv_archive import` (only `from swing.evaluation` + `from swing.evaluation.criteria` + stdlib + dataclasses imports allowed in V2 modules)

All 5 tests live in `tests/research/test_aplus_v2_ohlcv_reader.py` per plan §F + §K. **Executing-plans MUST land all 5 tests with discriminating fixture coverage.**

---

## §4 Per-task summary (REFERENCE; plan §G is BINDING substrate)

The per-task summary below is REFERENCE; plan §G holds BINDING bite-sized TDD step specification. Implementer MUST work from plan §G end-to-end, NOT from this summary.

### §4.1 T-V2.1: exceptions + ohlcv_reader + cfg_substitution + context_builder

- **T-V2.1.1**: NEW `exceptions.py` (7 typed exceptions per plan §B.1 row 2: `OhlcvCoverageError`, `MissingRsUniversePathError`, `EmptyRsUniverseError`, `InvalidRsUniverseError`, `PostCleanupUniverseTooSmallError`, `OutOfRangeSubstitutionError`, `MalformedAsofDateError`)
- **T-V2.1.2**: NEW `ohlcv_reader.py` — ~12 tests per plan §H (Shape A primary + legacy fallback + both-exist policy + column normalization + required-column check + 5 L2 LOCK tests per §3.5)
- **T-V2.1.3**: NEW `cfg_substitution.py` — ~6 tests (`substitute_cfg` per-subsection 4 + unknown-subsection ValueError + type-preservation)
- **T-V2.1.4**: NEW `context_builder.py` — ~12 tests (OHLCV slicing + BatchContext reconstruction + RS universe loading + full-universe returns_12w + per-ticker skip + horizon_weeks-scaled bars_needed + v2_universe_hash + tier-1/tier-2 risk-gate classifier + universe validation + 5 typed exceptions)

### §4.2 T-V2.2: sweep.py

- **T-V2.2.1**: `SweepEntryV2` dataclass + `run_v2_sweep` orchestrator
- **T-V2.2.2**: Tier-1 baseline parity invariant (CRITICAL; blocking; V2 with no substitution MUST match V1 persisted bucket distribution exactly per spec §E.4)
- **T-V2.2.3**: Tier-2 parity reporting (non-blocking; surrogate-flagged per OQ-15)
- **T-V2.2.4**: Single-variable downstream propagation
- **T-V2.2.5**: `vcp.watch_max_fails` special-case mirror per OQ-11
- **T-V2.2.6**: Per-candidate failure isolation (3 modes: ohlcv-coverage skip, out-of-range substitution skip, evaluation-error skip)
- **T-V2.2.7**: Multi-eval_run universe scan (63 eval_runs per OQ-6)
- **T-V2.2.8**: `current_equity` surrogate threading per OQ-15
- **T-V2.2.9**: Per-eval_run BatchContext cache (≤315 reconstructions per Codex M4 LOAD-BEARING)
- **T-V2.2.10**: Per-TICKER OHLCV cache (≤ N_universe + delta opens per Codex R2.M5)
- **T-V2.2.11**: Empty-eval-runs short-circuit per Codex R3.M3
- Empty-DB return sentinel `v2_universe_hash="empty_no_eval_runs"` per Codex R5.M1

### §4.3 T-V2.3: output.py

- CSV emission (12 cols); markdown matrix; headline; per-variable drill-down (with `bucket_via_surrogate` flag per OQ-15); V1↔V2 parity section (CRITERION DRIFT alert); per-variable scope-reduction notes; empty-state uniform representation; both-exist warning banner per OQ-18; manifest emission (`both_exist_shape_a_wins_count` + tier-1/tier-2 split + memory peak from tracemalloc); ASCII-only enforcement (cp1252 round-trip)

### §4.4 T-V2.4: run.py + CLI subcommand registration

- `run_harness(...)` orchestrator + argparse `main()`
- CLI argparse boundaries (`--eval-runs` + `--variables-filter` + `--min-universe-size` + `--max-runtime-seconds` cap; default UNSET per OQ-9)
- ClickException wrapping ValueError per cumulative lesson
- Output file paths `exports/diagnostics/aplus-sensitivity-v2-<ISO>.{csv,md}`
- Baseline smoke test (operator's actual DB shape via fixture)
- CLI subcommand registration in `swing/cli.py` (35-60 lines per OQ-17 LOCK; mirror V1 at `swing/cli.py:4748-4787`; SOLE production-`swing/` write)
- Subprocess stdout smoke via PowerShell (cp1252 encoding gotcha test per cumulative gotcha)
- `git diff swing/ --stat` discriminating gate (asserts ONLY `swing/cli.py` modified)

### §4.5 T-V2.5: method-record + first study writeup + closer

- Method-record extension at `research/method-records/aplus-criteria-calibration.md` (version bump 0.1.0 → 0.2.0; NEW sections per spec §K.2 + §K.3 + §K.4 + §K.5)
- First study writeup at `research/studies/<V2-ship-date>-v2-ohlcv-criterion-evaluator.md` (per `research/studies/earnings-proximity-exclusion.md` precedent)
- Operator smoke run against operator's actual DB (5681/63 universe); capture output (CSV + markdown) at `exports/diagnostics/aplus-sensitivity-v2-<ship-timestamp>.{csv,md}`
- Update `research/phase-0-tasks.md` "Next" section reflecting V2 OHLCV harness SHIPPED status (first method-record COMPLETED)
- V2 closer commit (commit message cites: V2 OHLCV harness SHIPPED; method-record bumped to 0.2.0; first study writeup; baseline parity invariant green; ZERO Co-Authored-By footer; ALL 20 cumulative gotchas honored)
- Integration / E2E test suite (~6 per spec §H.1)

---

## §5 Done criteria for executing-plans output

V2 OHLCV executing-plans phase SHIPPED requires:

- [ ] **All 5 sub-bundles T-V2.1..T-V2.5 SHIPPED** with per-sub-bundle return reports OR consolidated return report at `docs/v2-ohlcv-criterion-evaluator-executing-plans-return-report.md`
- [ ] **~84 fast tests added** distributed per plan §H (~12+~12+~6+~17+~10+~8+~11 across 7 test files); baseline 5778 → ~5862 fast tests post-V2-ship; ZERO slow tests
- [ ] **~50-69 commits via parametrize-consolidation** (or ~84-91 at raw 1-commit-per-test ceiling) per plan §G.0 commit-cadence preface
- [ ] **L2 LOCK 5 BINDING discriminating tests all GREEN** per plan §F + §K
- [ ] **`git diff swing/ --stat` shows ONLY `swing/cli.py` modified** post-V2-ship (per OQ-17 LOCK discriminating gate)
- [ ] **`git diff swing/data/migrations/ --stat` shows ZERO files modified** post-V2-ship (per plan §A.5 schema LOCK discriminating gate)
- [ ] **Method-record at `research/method-records/aplus-criteria-calibration.md` extended** per plan §L + spec §K.2-§K.5 (version bump 0.1.0 → 0.2.0)
- [ ] **First study writeup at `research/studies/<V2-ship-date>-v2-ohlcv-criterion-evaluator.md`** per `research/studies/earnings-proximity-exclusion.md` precedent; includes Limitations section enumerating OQ-14 + OQ-15 + OQ-18 caveats
- [ ] **`research/phase-0-tasks.md` "Next" section updated** reflecting V2 SHIPPED status (first method-record COMPLETED)
- [ ] **Operator smoke run output captured + committed** to `exports/diagnostics/aplus-sensitivity-v2-<ship-timestamp>.{csv,md}`
- [ ] **Tier-1 baseline parity invariant GREEN** (EXACT match per spec §E.4; ZERO tolerance)
- [ ] **Tier-2 baseline parity reporting GREEN** (surrogate-flagged; non-blocking per OQ-15)
- [ ] **Codex chain converged at NO_NEW_CRITICAL_MAJOR**
- [ ] **ZERO Co-Authored-By footer trailer** across ALL executing-plans-phase commits + merge (~448+ cumulative streak preserved + extended)
- [ ] **Return report** at `docs/v2-ohlcv-criterion-evaluator-executing-plans-return-report.md` covers: commit chain shape (per-sub-bundle); Codex chain shape (per-round Major counts); 33rd cumulative C.C lesson #6 validation result; per-expansion verdict (especially NEW gotchas #19 + #20 BINDING for 33rd validation); forward-binding lessons banked; V2/V3 candidates banked + refined from writing-plans §4; cumulative streaks preserved

Plan-phase Codex chain expected 2-5 rounds. Pre-Codex 7-expansion + 5 NEW candidate refinements + 2 NEW sub-refinements + 20 cumulative gotchas (especially NEW #19 + #20) discipline BINDING; verdict per expansion captured in plan-phase return report.

---

## §6 References

- **Writing-plans plan (BINDING)**: [`docs/superpowers/plans/2026-05-23-v2-ohlcv-criterion-evaluator-plan.md`](superpowers/plans/2026-05-23-v2-ohlcv-criterion-evaluator-plan.md) at main HEAD `34f177c`
- **Writing-plans return report**: [`docs/v2-ohlcv-criterion-evaluator-writing-plans-return-report.md`](v2-ohlcv-criterion-evaluator-writing-plans-return-report.md) at `75a2649`
- **Writing-plans dispatch brief**: [`docs/v2-ohlcv-criterion-evaluator-writing-plans-dispatch-brief.md`](v2-ohlcv-criterion-evaluator-writing-plans-dispatch-brief.md) at `f8cafd9`
- **Brainstorming spec (PRECEDENT)**: [`docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md`](superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md) at `362fe18`
- **Brainstorming return report**: [`docs/v2-ohlcv-criterion-evaluator-brainstorm-return-report.md`](v2-ohlcv-criterion-evaluator-brainstorm-return-report.md) at `8532949`
- **Brainstorming dispatch brief**: [`docs/v2-ohlcv-criterion-evaluator-brainstorming-dispatch-brief.md`](v2-ohlcv-criterion-evaluator-brainstorming-dispatch-brief.md) at `acaf305`
- **Turn D handoff brief**: [`docs/orchestrator-handoff-2026-05-23-post-v2-ohlcv-brainstorm-merge-pre-oq-triage.md`](orchestrator-handoff-2026-05-23-post-v2-ohlcv-brainstorm-merge-pre-oq-triage.md) at `08ea67e`
- **Method-record (PRIMARY substrate for T-V2.5)**: [`research/method-records/aplus-criteria-calibration.md`](../research/method-records/aplus-criteria-calibration.md)
- **V1 harness (architecture precedent)**: [`research/harness/aplus_sensitivity/`](../research/harness/aplus_sensitivity/)
- **V1 study writeup**: [`research/studies/aplus-criterion-sensitivity-2026-05-22.md`](../research/studies/aplus-criterion-sensitivity-2026-05-22.md)
- **Research-branch precedent (first applied-research arc shape)**: [`research/harness/earnings_proximity/`](../research/harness/earnings_proximity/) + [`research/studies/earnings-proximity-exclusion.md`](../research/studies/earnings-proximity-exclusion.md) + [`research/method-records/_template.md`](../research/method-records/_template.md)
- **Triage agenda (Path B LOCKED 2026-05-23)**: [`docs/phase13-closer-next-phase-triage.md`](phase13-closer-next-phase-triage.md) at `b4d7719`
- **Production `bucket_for`**: `swing/evaluation/scoring.py`
- **Production `evaluate_one`**: `swing/evaluation/evaluator.py`
- **Production criteria**: `swing/evaluation/criteria/*.py` (8 trend_template criteria + 9 vcp criteria + 1 risk criterion)
- **Production OHLCV archive**: `swing/data/ohlcv_archive.py`
- **Production candidate_criteria repo**: `swing/data/repos/candidates.py:78` (write path)
- **Schema migrations**: `swing/data/migrations/0001_phase1_initial.sql` + subsequent
- **CLAUDE.md** at repo root (20 cumulative gotchas; NEW #17 + #18 + #19 + #20 BINDING for 33rd cumulative validation)
- **V2.1 governance**: [`reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md`](../reference/Future%20Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md) + [`reference/Future Work/2026-04-23-rebuttal-response-for-implementors.md`](../reference/Future%20Work/2026-04-23-rebuttal-response-for-implementors.md)
- **Operator's S3 sensitivity-harness output (V1 baseline for V1↔V2 parity)**: `exports/diagnostics/aplus-sensitivity-20260523T065514Z.md` + `.csv`

---

## §7 NON-scope (V2.5 / V3 / future arc; explicitly out of V2 OHLCV harness executing-plans dispatch)

- **Schema changes** — V2 is schema-UNCHANGED per plan §A.5 (v21 LOCKED)
- **ZERO new Schwab API calls** (L2 LOCK preserved + REINFORCED via 5 BINDING discriminating tests per plan §F + §K)
- **Pair-wise / N-D cross-coupling** — V2 stays 1D per OQ-7; 2D+ V3+
- **Adaptive bisection sweep** — V2 inherits V1 5-point grid per OQ-3; adaptive V3+
- **Per-eval_run-historical RS universe snapshots** — V2 uses current-universe snapshot per OQ-14; per-eval_run-historical V3+ (schema change required)
- **`vcp.watch_max_fails` promote-to-cfg** — V2 mirrors V1 special-case per OQ-11; V2.5 candidate
- **Port production `_backward_compat_rename` merge logic to V2 reader** — V2 ships Shape A wins unconditionally per OQ-18; V2.5 candidate
- **`cfg.trend_template.allowed_miss_names` tuple-set sweep** — V3+ per V1 method-record §"Notes" line 70
- **`cfg.rs.benchmark_ticker` string-identifier sweep** — V3+ per V1 method-record §"Notes" line 70
- **cfg-policy method-record automation post promotion-to-production** — V3+ per OQ-8 ladder
- **Phase 14 commissioning** — DEFERRED until V2 OHLCV harness output informs operational scope per Path B sequencing
- **V2.G1-G4 operator gate bug investigations** — STILL DEFERRED per operator decision 2026-05-23 PM (work AFTER Applied Research tasking completes per `docs/phase3e-todo.md`)
- **5 NEW writing-plans-phase patterns banked at writing-plans return report §4** — those are V2.5/V3+ promotion candidates; not enforced as BINDING templates at executing-plans phase (executing-plans applies them only inasmuch as plan §G prescribes)

---

## §8 Post-executing-plans handback

When executing-plans Codex chain converges to NO_NEW_CRITICAL_MAJOR:

1. Write return report at `docs/v2-ohlcv-criterion-evaluator-executing-plans-return-report.md` per cumulative precedent (commit chain shape per-sub-bundle + Codex chain shape + per-expansion verdict + forward-binding lessons + V2/V3 candidates banked + cumulative streaks).
2. Inline self-verification per dispatch brief BINDING handback discipline:
   - Ruff check
   - Schema unchanged at v21
   - Baseline 5778 → ~5862 fast tests (per §H projection; +84 NEW)
   - ZERO new Schwab API calls (L2 LOCK 5 BINDING tests all GREEN)
   - ZERO Co-Authored-By footer
   - `git diff swing/ --stat` shows ONLY `swing/cli.py` modified
   - `git diff swing/data/migrations/ --stat` shows ZERO files modified
3. Hand back to operator with summary.

Orchestrator-side next steps post-executing-plans (Turn E or fresh Turn F):
- QA implementer product per `feedback_orchestrator_qa_implementer_product` (verify file:line + shipped-behavior + L2 LOCK 5 tests GREEN + 33rd cumulative C.C lesson #6 validation against reality on disk)
- Merge executing-plans branch `--no-ff` to main; push
- Post-merge housekeeping bundle (CLAUDE.md line 3 refresh — V2 OHLCV harness SHIPPED status update; any NEW gotchas surfaced from executing-plans Codex chain; phase3e-todo NEW top entry; orchestrator-context current state refresh + Prior demote + archive-split per size-check trigger)
- Operator-paired session: review V2 OHLCV harness output (CSV + markdown at `exports/diagnostics/`); identify binding threshold variables OR declare all 15 non-binding
- Per OQ-8 promotion ladder: research → shadow promotion gate (V2 OHLCV harness shipped + baseline parity green + ≥1 study writeup + ≥1 binding threshold OR all 15 declared non-binding with sign-off)
- Optional next-arc: cfg-policy method-record drafting if binding thresholds identified
- Phase 14 commissioning consideration per Path B sequencing post-V2-output review

---

*End of V2 OHLCV criterion-evaluator harness executing-plans dispatch brief. 18 OQs operator-locked per RECOMMEND with ZERO amendments preserved through brainstorming + writing-plans + executing-plans phases. ~448+ ZERO Co-Authored-By footer streak preserved through this brief commit. V2 OHLCV applied-research arc IN-FLIGHT (brainstorming + writing-plans SHIPPED 2026-05-23; executing-plans next; ~50-69 commits + ~84 fast tests + 5 sub-bundles T-V2.1..T-V2.5 sequential). FIRST Applied Research arc post-Phase-13-FULLY-CLOSED. 33rd cumulative C.C lesson #6 validation expected at executing-plans handback with NEW gotchas #19 + #20 BINDING.*
