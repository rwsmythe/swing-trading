# V2 OHLCV Criterion-Evaluator Harness — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the V2 OHLCV writing-plans implementer. No prior conversation context.

**Mission:** Produce an implementation plan that decomposes the V2 OHLCV criterion-evaluator harness 5-sub-bundle scope (T-V2.1..T-V2.5) per the operator-confirmed brainstorming spec + 18 OQ dispositions (ALL LOCKED per operator triage 2026-05-23 PM with ZERO amendments — every OQ accepted RECOMMEND verbatim).

**Brainstorming spec (BINDING substrate):** [`docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md`](superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md) at main HEAD `362fe18` (1086 lines; 14 sections §A-§N; Codex R5 NO_NEW_CRITICAL_MAJOR; 3 CRITICAL + 17 MAJOR + 13 MINOR ALL RESOLVED in-place; ZERO accepted-as-rationale). **READ END-TO-END.**

**Brief:** `docs/v2-ohlcv-criterion-evaluator-writing-plans-dispatch-brief.md` (this file).

**Sequencing:** V2 OHLCV brainstorming SHIPPED 2026-05-23 at `362fe18` + housekeeping at `bd08644` + Turn D handoff at `08ea67e` + this brief commit. Output feeds the executing-plans dispatch (5 sub-bundles T-V2.1..T-V2.5 per spec §M.1).

**Branch:** `applied-research-v2-ohlcv-criterion-evaluator-writing-plans` — branches from main HEAD after this brief lands.

**Worktree:** `git worktree add .worktrees/applied-research-v2-ohlcv-criterion-evaluator-writing-plans applied-research-v2-ohlcv-criterion-evaluator-writing-plans`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Workflow:** `copowers:writing-plans` skill (wraps `superpowers:writing-plans` with adversarial Codex MCP review). Expected 2-5 Codex rounds.

**Expected duration:** ~3-6 hours operator-paced. Plan target: ~1000-1500 lines (T4.SB writing-plans plan was 1820 lines; V2 scope is comparable per sub-bundle complexity but with sharper architectural locks already in the spec, so ~1200 lines likely).

---

## §0 Read first (in this order)

1. **`docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md`** at HEAD `362fe18` — PRIMARY SUBSTRATE. 14 sections §A-§N. Especially:
   - §A status + scope (V1 LIMITATION lift; production read-only invariant with OQ-17 CLI carve-out)
   - §B problem statement + V1 vs V2 substitution semantic differences
   - §C architecture-location audit (NEW module `research/harness/aplus_v2_ohlcv_evaluator/`)
   - §D dataclass shape projections (`SweepEntryV2` inheriting V1 enum + 3 NEW skip-count fields)
   - §E per-criterion cfg-variable mapping + tier-1/tier-2 baseline parity invariant + `vcp.watch_max_fails` special-case + OHLCV coverage failure semantics
   - §F **F.1 OHLCV reader strategy (direct Shape A read via NEW `ohlcv_reader.py`)** + F.2 BatchContext reconstruction + F.3 SQL skeletons + F.4 cfg substitution helper + F.5 per-eval_run BatchContext cache (LOAD-BEARING) + F.6 universe validation
   - §G output format (CSV + markdown; 12-col matrix; headline; drill-down; V1↔V2 parity section; both-exist diagnostic banner; manifest)
   - §H test scope projection (~68 tests across 7 modules)
   - §I 18 OQs (now ALL operator-LOCKED per §1 below)
   - §J forward-binding lessons inherited (16 cumulative gotchas + 7 expansions + 5 NEW candidate refinements)
   - §K method-record extension (version bump 0.1.0 → 0.2.0; NEW sections per OQ-8 promotion ladder)
   - §L V2.1 governance citations + repository cross-references
   - §M dispatch sequence (5 sub-bundle decomposition recommendation; **BINDING for this plan's task structure**)
   - §N self-review

2. **`docs/v2-ohlcv-criterion-evaluator-brainstorm-return-report.md`** at `8532949` — Codex chain shape (R1-R5 with 5 fix bundles); 10 V2/V3-dependency-cited V1 simplifications; 6 forward-binding lessons; NEW Expansion #2 + #4 refinement candidates banked (now CLAUDE.md gotchas #17 + #18).

3. **`docs/v2-ohlcv-criterion-evaluator-brainstorming-dispatch-brief.md`** at `acaf305` — predecessor brief that drove the brainstorming dispatch (reference-only; supplanted by spec).

4. **`research/method-records/aplus-criteria-calibration.md`** — PRIMARY substrate for §K method-record extension. V2 writing-plans phase MUST decompose the extension into per-sub-bundle deliverables.

5. **`research/harness/aplus_sensitivity/`** (variables.py + sweep.py + output.py + run.py + README.md) — V1 precedent. V2 architecture mirrors this structure with NEW additions (ohlcv_reader.py + context_builder.py + cfg_substitution.py).

6. **`research/harness/earnings_proximity/`** + **`research/studies/earnings-proximity-exclusion.md`** + **`research/method-records/_template.md`** — research-branch precedent for first-applied-research-arc shape (study writeup format; method-record template structure).

7. **`research/phase-0-tasks.md`** "Next" section — first method-record selection has been COMPLETED (V2 OHLCV harness IS that selection per OQ-CL.3 LOCK landed at T4.SB). T-V2.5 closer should reflect the SHIPPED status in this file.

8. **`CLAUDE.md`** at repo root — project conventions + **18 cumulative gotchas**. ESPECIALLY relevant for V2 writing-plans phase:
   - **#17 — Expansion #2 refinement: brief-vs-actual-production-function-signature verification** (NEW BINDING for 32nd cumulative validation; banked at V2 brainstorming Codex R1.M1+M2)
   - **#18 — Expansion #4 refinement: SQL skeleton JOIN-cardinality + downstream-sufficiency audit** (NEW BINDING for 32nd cumulative validation; banked at V2 brainstorming Codex R1.C1+R4.M2)
   - **#12 — `date.fromisoformat()` discipline** (DIRECTLY APPLIES; V2 reads `evaluation_runs.data_asof_date` TEXT → date conversion per §F.2 + §H.2)
   - **#14 — Architecture-location audit + 5 sub-disciplines (Expansion #10)** (DIRECTLY APPLIES per §C.1; V2 introduces NEW module + must justify module placement + dependency-surface verification)
   - **#15 — Taxonomy propagation audit (Expansion #11)** (DIRECTLY APPLIES per §D.3; V2 `SweepEntryV2.kind` inherits V1 enum + 3 NEW skip-count fields must propagate dataclass + CSV header + markdown matrix + fixtures)
   - **Synthetic-fixture-vs-production-emitter shape drift** (4 cumulative instances; DIRECTLY APPLIES — V2 fixtures MUST shape-match NEW `ohlcv_reader.py` reads AND `swing.data.repos.candidates.insert_candidates` persistence)
   - **Service-layer ValueErrors must be wrapped at CLI boundary** (DIRECTLY APPLIES at V2 CLI per §C.2)
   - **`Literal[...]` type hints are NOT runtime-enforced** (DIRECTLY APPLIES to V2's `SweepEntryV2.kind`; same `__post_init__` pattern as V1)
   - **Windows PowerShell stdout cp1252 ASCII-only** (DIRECTLY APPLIES to V2 CLI output paths per §G.5)

9. **`docs/orchestrator-context.md`** "Currently in-flight work" — current state reflects V2 OHLCV brainstorming SHIPPED + 18-OQ triage complete + writing-plans dispatch in-flight.

---

## §1 OQ dispositions (BINDING for writing-plans phase)

Per operator-paired triage 2026-05-23 PM (Turn D): **ALL 18 OQs LOCKED per RECOMMEND with ZERO amendments**. Operator accepted every brainstorming-spec RECOMMEND verbatim. This is a strong signal that the brainstorming-phase Codex chain (R1-R5; 3 CRITICAL + 17 MAJOR + 13 MINOR ALL RESOLVED in-place) converged the design crisply.

### §1.1 Core architecture (OQ-1 through OQ-8)

| OQ | Disposition LOCKED |
|---|---|
| OQ-1 OHLCV reconstruction scope | Direct Shape A yfinance read via NEW `ohlcv_reader.py` wrapper (bypasses `read_or_fetch_archive`; NEVER opens schwab_api parquet; legacy `{ticker}.parquet` fallback). Amended per Codex R1.M1+M2+R2.M2 RESOLVED. |
| OQ-2 Per-criterion evaluator interface | cfg-substitution via `dataclasses.replace` + production `evaluate_one(ctx)` end-to-end per §D.1. Single-variable downstream propagation preserved. `vcp.watch_max_fails` special-case mirrors V1 per §E.3 / OQ-11. |
| OQ-3 Sweep range strategy | Inherit V1 5-point grid per V2.1 §IV.B parsimony. Adaptive bisection + full-range deferred V3+. |
| OQ-4 Output format | Hybrid: V1 12-col matrix (9 V1 cols + 3 NEW skip cols) + headline section + per-variable drill-down + V1↔V2 parity section + both-exist diagnostic banner per §G. |
| OQ-5 Scope discipline | ALL 15 inert threshold variables in one dispatch (NOT phased). Shared infrastructure identical across the 15. |
| OQ-6 Validation universe | Reuse S3's 5681 candidates / 63 eval_runs for V1↔V2 reproducibility (NOT fresh fetch). |
| OQ-7 Cross-coupling | 1D per V2.1 §IV.B parsimony. Single-variable downstream propagation preserved WITHIN 1D; 2D+ interaction effects deferred V3+. |
| OQ-8 Method-record promotion criteria | 3-tier research→shadow→production ladder per §K.3. research→shadow: V2 shipped + baseline parity green + ≥1 study writeup + ≥1 binding threshold OR all 15 declared non-binding with sign-off. shadow→production: ≥1 cfg-policy proposal evaluated against ≥2 disjoint universes + delta statistically distinguishable (default ≥5 A+ delta on 5681-candidate universe — doubling A+ count) + operator-paired ratification. Anti-promotion guards per §K.3. |

### §1.2 Substrate-surfaced (OQ-9 through OQ-13)

| OQ | Disposition LOCKED |
|---|---|
| OQ-9 Performance budget cap | Default UNSET + `--max-runtime-seconds N` CLI flag for partial-run capability. Acceptance target: <60 min on operator hardware for full 5681/63/17/5 universe. If exceeded, V2.5 work targets §F.5 per-eval_run BatchContext reuse optimization. **Writing-plans-phase work-item**: implementer chooses default for `--max-runtime-seconds` (likely operator-paired or ship with no default cap; absence of `--max-runtime-seconds` means no cap). |
| OQ-10 V2 CLI surface name | `swing diagnose aplus-sensitivity-v2`. Back-compat preserved (V1 stays at `aplus-sensitivity`). "v2" suffix explicit about lineage. |
| OQ-11 `vcp.watch_max_fails` hardcode handling | Mirror V1's special-case substitution per §E.3 for V2 ship. BANK V2.5 candidate: "Promote `vcp.watch_max_fails` to cfg-derived in `bucket_for` (1-line production change at `swing/evaluation/scoring.py:37`)" — operator-paired ratification post V2 ship. |
| OQ-12 Schwab API L2 LOCK preservation | yfinance-only via direct Shape A `{ticker}.yfinance.parquet` read. Discriminating test: plant both schwab_api Shape A AND yfinance Shape A parquet files for synthetic ticker; assert V2 reads ONLY yfinance bytes (byte-checksum compare) + assert V2 process NEVER opens schwab_api parquet (file-open mock). Reinforces L2 LOCK. |
| OQ-13 OHLCV coverage failure attribution mode | Skip + report. Single `ohlcv_coverage_skip_count` scalar per V2 invocation per Codex R1.M3 (same value across all per-variable rows because `evaluate_one` runs all criteria together — coverage skip is per-candidate-per-V2-run not per-(variable, sweep_point)). Per-study scope-reduction notes per §G.4. **Writing-plans-phase work-item**: implementer chooses exact typed exception name + module location for `OhlcvCoverageError` (likely `research/harness/aplus_v2_ohlcv_evaluator/exceptions.py` or co-located with `ohlcv_reader.py`). |

### §1.3 Codex-surfaced architectural (OQ-14 through OQ-18)

| OQ | Disposition LOCKED |
|---|---|
| OQ-14 RS universe reconstruction at historical asof_date | Current-universe snapshot for V2 ship (V2 reads `cfg.paths.rs_universe_path` at V2 invocation + uses that universe for ALL historical eval_runs). Surface drift caveat in study writeup `Limitations` section. V3+ candidate: persist per-eval_run universe snapshots at write-time (schema change). |
| OQ-15 `current_equity` surrogate for risk gate recompute | Per-eval_run-historical from `account_equity_snapshots` rows with snapshot_date ≤ eval_run's `data_asof_date` IF available; fall back to latest snapshot row OTHERWISE; mark tier-2 candidates (per §E.4 risk-gate-dependent buckets) with `bucket_via_surrogate=True` for operator transparency. Per-V2-study writeup `Limitations` section enumerates surrogate usage count. |
| OQ-16 OHLCV archive read strategy | Direct Shape A parquet read via NEW V2 wrapper `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py`. Bypasses production `read_or_fetch_archive` (no `prefer_source` kwarg AND actively fetches yfinance on miss). NO fetch path; reproducible per-V2-invocation; L2 LOCK preserved. |
| OQ-17 CLI subcommand registration as read-only carve-out | Explicit minimal carve-out per §A.1 amended language: `@click.command`-decorated handler + diagnose group attachment + Click option definitions + ClickException wrapping + delegation to research-harness `run_harness`. Realistic line count: 35-60 lines per V1 precedent at `swing/cli.py:4748-4787`. This is the SOLE production-`swing/` modification V2 dispatch makes. Discriminating gate: `git diff swing/ --stat` after V2 ship shows ONLY `swing/cli.py` modified. NO other writes; NO schema change; NO migration. |
| OQ-18 Both-exist legacy/Shape A archive read policy | Shape A wins unconditionally + per-ticker diagnostic surface. V2 reads `{ticker}.yfinance.parquet`; ignores legacy in both-exist case. Per Codex R4.M1: `both_exist_shape_a_wins_count` scalar + per-ticker affected list + warning banner. Documented caveat in V2 study writeup `Limitations` section. Operator remediation: invoke any production OHLCV-read path (e.g., normal pipeline run) before V2 to force merge OR accept the drift caveat. V2.5 candidate: port production merge logic to V2 reader. |

---

## §1.5 Amendments (BINDING; executed alongside spec-encoded scope)

**NONE.** Operator accepted all 18 OQ RECOMMENDs verbatim during Turn D triage (2026-05-23 PM). The brainstorming-phase Codex chain (R1-R5 converged at NO_NEW_CRITICAL_MAJOR with 3 CRITICAL + 17 MAJOR + 13 MINOR ALL RESOLVED in-place) produced a design crisp enough that the operator triage did not surface new amendments. This is a strong validation signal for the brainstorming-phase pre-Codex 7-expansion + 5 NEW candidate refinement discipline.

This stands in contrast to T2.SB6c writing-plans brief §1.5.1+ which carried 4 amendments (parameter-sweep sensitivity diagnostic + research-branch placement + Option A re-run collision + OQ-CL.2 deferred) and T4.SB writing-plans brief §1.5.1+ which carried 4 amendments. V2 OHLCV's zero-amendment triage outcome reflects the architectural sharpness achieved at brainstorming.

**Forward-binding lesson** (banked for future arc-orchestrator pattern): when brainstorming-phase Codex chain converges crisply (NO_NEW_CRITICAL_MAJOR with ZERO accepted-as-rationale + thorough resolution of ALL findings in-place), the writing-plans-phase OQ triage often surfaces zero amendments. Future orchestrator should still drive the formal triage (per durable BINDING discipline) but should not over-engineer amendments where the operator concurs with RECOMMEND.

---

## §2 Scope inheritance from brainstorming spec (BINDING)

Per spec §M.1 5-sub-bundle decomposition: writing-plans plan MUST encode per-sub-bundle acceptance criteria + commit message templates + per-task test budget. Do NOT re-derive the sub-bundle structure; reference spec §M.1 as authoritative.

### §2.1 Per-sub-bundle scope summary (spec §M.1 is BINDING)

| Sub-bundle | Spec §M.1 ref | Brief description | Est. commits |
|---|---|---|---|
| T-V2.1 | §M.1 row 1 | `ohlcv_reader.py` (NEW per Codex amendments) + `context_builder.py` + `cfg_substitution.py` + tests | ~10-15 (expanded from §M.1 ~8-12 to absorb NEW `ohlcv_reader.py` per Codex R1-R5 amendments) |
| T-V2.2 | §M.1 row 2 | `sweep.py` + tests (largest sub-bundle; baseline parity invariants + failure isolation + per-eval_run BatchContext cache + per-TICKER OHLCV cache) | ~12-18 |
| T-V2.3 | §M.1 row 3 | `output.py` + tests (CSV + markdown sensitivity matrix + headline + drill-down + V1↔V2 parity + manifest + both-exist warning banner) | ~8-12 |
| T-V2.4 | §M.1 row 4 | `run.py` + CLI subcommand registration in `swing/cli.py` + tests (CLI entry + argparse + ClickException wrapping + smoke E2E + cp1252 stdout safety) | ~6-10 |
| T-V2.5 | §M.1 row 5 | Method-record extension per §K + first study writeup at `research/studies/<date>-v2-ohlcv-criterion-evaluator.md` + operator smoke run + closer (Phase 13 closure marker NOT relevant; V2 closer is a research-arc closer not a phase closer) | ~6-10 |

**Total estimated commits**: ~42-65 across executing-plans phase. Comparable to T4.SB executing-plans scope (~28+ commits per closer ship).

### §2.2 NEW module + sub-bundle naming

V2 OHLCV harness lives under `research/harness/aplus_v2_ohlcv_evaluator/` per spec §C.1 (NEW module decision; architecture-location audit per Expansion #10). Sub-bundle naming `T-V2.N` (NOT `T-T-V2.N`) reflects V2-as-first-applied-research-arc; subsequent applied-research arcs may use different prefixes per operator-paired naming convention.

### §2.3 Concurrent dispatch potential

Per spec §M.2 RECOMMEND: **NO concurrent dispatch**. Sequential single-implementer dispatch via `copowers:subagent-driven-development` per project workflow precedent. Sub-bundles T-V2.1 → T-V2.2 → T-V2.3 → T-V2.4 → T-V2.5 strictly sequential per dependency graph (T-V2.2 depends on T-V2.1; T-V2.3 depends on T-V2.2; T-V2.4 depends on T-V2.3 for output formatter integration; T-V2.5 depends on all prior + operator gate).

Plan should explicitly enumerate the sequential dispatch graph + note that cross-sub-bundle state isolation is NOT a feature this arc needs.

---

## §3 Watch items + cumulative discipline (BINDING for writing-plans phase)

### §3.1 Pre-Codex 7-expansion + 5 NEW candidate refinements (32nd cumulative C.C lesson #6 validation expected)

Writing-plans phase pre-Codex review applies ALL 7 expansions + 5 NEW candidate refinements:

1. **Expansion #1** — hardcoded-duplicate audit (T3.SB2 hotfix `cf3c489`). V2 application: `vcp.watch_max_fails = 2` hardcoded at `swing/evaluation/scoring.py:37`; V2 mirrors V1 special-case per OQ-11. NO other hardcoded duplicates of the 15 threshold variables (verified at brainstorming).
2. **Expansion #2** — brief-vs-spec + brief-vs-actual schema verification.
3. **Expansion #3** — schema-CHECK-vs-semantic-contract gap. N/A V2 (no schema change).
4. **Expansion #4** — specific-scenario gotcha trace + SQL skeleton column verification.
5. **Expansion #5** — cross-section spec inventory grep.
6. **Expansion #6** — content-completeness audit.
7. **Expansion #7** — cross-row semantic SCOPE audit + scope-vs-unit boundary. N/A V2 (pure CLI; no operator-input POST handler).
8. **Expansion #8 candidate** — per-aggregation-function UNIT audit on SQL skeletons. N/A V2 (no GROUP BY / COUNT / SUM in spec §F.3).
9. **Expansion #9 candidate** — form-render anchor lifecycle 4-dimension audit. N/A V2 (no forms / web routes).
10. **Expansion #10 candidate (BINDING)** — Architecture-location audit + 5 sub-disciplines. DIRECTLY APPLIES at spec §C.1 (NEW module placement decision documented; per-criterion evaluator location + cfg-substitution location + sweep orchestration location justified).
11. **Expansion #11 candidate (BINDING)** — Taxonomy propagation audit. DIRECTLY APPLIES at spec §D.3 (`SweepEntryV2` inherits V1 enum; 3 NEW skip-count fields propagated through dataclass + CSV header + markdown matrix + test fixtures).
12. **Expansion #12 candidate** — Sibling-route audit. N/A V2 (no route handlers).
13. **NEW Expansion #2 refinement (BINDING for 32nd cumulative validation)** — brief-vs-actual-production-function-signature verification. Banked at V2 brainstorming Codex R1.M1+M2 (caught `read_or_fetch_archive(prefer_source=...)` kwarg-doesn't-exist + active-fetch-vs-read-only mismatch). **Writing-plans-phase pre-Codex review MUST**: grep every production-function reference in the plan (e.g., `evaluate_one`, `bucket_for`, `_bucket_for_substituted`, `load_universe`, `read_or_fetch_archive`, `current_stage`, candidate insertion helpers) + verify (a) signature; (b) side-effect contract (read-only vs write vs fetch-on-miss); (c) error semantics; (d) any documented invariants (e.g., L2 LOCK preservation). Use `inspect.signature()` introspection in discriminating tests where feasible. Now CLAUDE.md gotcha #17.
14. **NEW Expansion #4 refinement (BINDING for 32nd cumulative validation)** — SQL skeleton JOIN-cardinality + downstream-sufficiency audit. Banked at V2 brainstorming Codex R1.C1+R4.M2 (caught candidate-only-universe-vs-RS-full-universe + post-cleanup re-check missing). **Writing-plans-phase pre-Codex review MUST**: for every SQL skeleton in the plan (especially `context_builder.py` + RS universe load + risk_feasibility persisted_risk_result lookup), enumerate (a) consumer's required row-set scope (per-candidate? per-cohort? per-universe?); (b) JOIN-cardinality assumption per JOIN clause (1:1 vs 1:N inflation risk); (c) downstream-sufficiency (walk consumer's logic; verify SQL output row-set contains everything downstream needs); (d) post-mutation re-check semantics (if harness mutates state — cleanup, fetch, fill — universe needs re-verification). Now CLAUDE.md gotcha #18.

### §3.2 Cumulative gotcha set (18 cumulative; 2 NEW from V2 brainstorming)

Per CLAUDE.md updates through `bd08644`:
- (1-8) Original cumulative discipline through Phase 11
- (9) SQL aggregation UNIT audit (Expansion #8) — T2.SB6c writing-plans
- (10) Existing-field reuse audit before claiming new dataclass fields — T2.SB6c writing-plans
- (11) Template-rendering surface audit before claiming "no template edit needed" — T2.SB6c writing-plans
- (12) `date.fromisoformat()` discipline for cross-type-boundary calls — T2.SB6c writing-plans
- (13) Form-render anchor lifecycle audit (Expansion #9) — T2.SB6c executing-plans
- (14) Architecture-location audit + 5 sub-disciplines (Expansion #10) — T4.SB brainstorming
- (15) Taxonomy propagation audit (Expansion #11) — T4.SB writing-plans
- (16) Sibling-route audit (Expansion #12) — T4.SB executing-plans
- **(17) NEW — Expansion #2 refinement: brief-vs-actual-production-function-signature verification** (V2 OHLCV brainstorming)
- **(18) NEW — Expansion #4 refinement: SQL skeleton JOIN-cardinality + downstream-sufficiency audit** (V2 OHLCV brainstorming)

ALL 18 gotchas BINDING for writing-plans-phase pre-Codex discipline. The 2 NEW gotchas #17 + #18 specifically apply to V2 dispatch's own function-invocation + SQL-skeleton work — writing-plans phase should self-apply them at every callsite in the plan.

### §3.3 Cumulative process discipline

- **NO Co-Authored-By footer** — ~438+ cumulative streak through V2 OHLCV brainstorming-merge housekeeping at `bd08644` + Turn D handoff at `08ea67e`. Cite per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15) in every commit message.
- **`python -m swing.cli` from worktree cwd**, NOT bare `swing` (per `feedback_worktree_cli_invocation`)
- **ASCII-only on runtime CLI paths** + markdown narrative text (Windows cp1252 stdout safety; cumulative gotcha lineage from Phase 12 C.D operator-witnessed gate)
- **TDD per task** via `superpowers:test-driven-development`
- **Edit tool for per-file edits**
- **Cite the discipline in commit messages** per cumulative precedent

### §3.4 Schema discipline (V2 is schema-UNCHANGED)

V2 SHOULD NOT touch schema per spec §A scope. v21 is the locked schema for this dispatch. If investigation surfaces an absolute necessity (e.g., persist per-eval_run universe snapshots for OQ-14 V3 candidate), §A.14 paired discipline applies + backup-gate strict-equality + migration runner discipline all apply per cumulative precedent. **Writing-plans phase should explicitly verify**: NO schema migration files added to `swing/data/migrations/`; NO `pragma user_version` bump; NO new tables / columns / CHECK constraints.

### §3.5 L2 LOCK reinforcement (cumulative; V2 SPECIFICALLY)

V2 dispatch is the FIRST research-branch arc post-Phase-13-FULLY-CLOSED that touches OHLCV reading machinery. The L2 LOCK invariant (ZERO new Schwab API calls; ZERO reads of `{ticker}.schwab_api.parquet`) MUST be preserved + REINFORCED via:
- **File-open mock discriminating test** (per OQ-12 LOCK): mock `pathlib.Path.open` (or equivalent file-open boundary); assert V2 process NEVER opens `{ticker}.schwab_api.parquet` for any synthetic test ticker. Test lives in `tests/research/harness/aplus_v2_ohlcv_evaluator/test_ohlcv_reader.py` or equivalent.
- **Import-graph mock discriminating test** (per spec §H.1): mock `swing.integrations.schwab.*` imports; assert V2 modules NEVER import any `schwab` symbol. Test lives same file as above.
- **Discriminating fixture test**: plant both `{synthetic_ticker}.yfinance.parquet` AND `{synthetic_ticker}.schwab_api.parquet`; run V2; byte-checksum compare V2's consumed bytes against yfinance file ONLY (NOT schwab_api).

These three tests collectively form the L2 LOCK regression-safety net. **Writing-plans phase MUST enumerate each in `ohlcv_reader.py` test suite.**

---

## §4 Per-sub-bundle acceptance criteria (writing-plans phase target)

Each sub-bundle's per-task acceptance criteria should be encoded in the plan's §B (per-task design) + §G (per-task acceptance criteria) sections. Below is the orchestrator-side guidance for what the writing-plans plan should articulate per sub-bundle.

### §4.1 T-V2.1: ohlcv_reader.py + context_builder.py + cfg_substitution.py

**Plan-phase decomposition** (target ~10-15 commits in executing-plans):

- T-V2.1.1: NEW `ohlcv_reader.py` module (direct Shape A read; legacy fallback; both-exist policy; column-case normalization; required-column check; NEVER opens schwab_api parquet; raises `OhlcvCoverageError`; both-exist diagnostic surface). **Tests: ~12** per spec §H.1.
- T-V2.1.2: NEW `context_builder.py` module (OHLCV slicing at asof_date; BatchContext reconstruction; RS universe loading via `load_universe`; full-universe `returns_12w_by_ticker` per Codex C1; per-ticker skip on <60 bars; rs.horizon_weeks parameter threading; v2_universe_hash SHA-256 prefix; tier-1/tier-2 risk-gate classification via persisted_risk_result per Codex R2.M3; typed exceptions `MissingRsUniversePathError` + `EmptyRsUniverseError` + `InvalidRsUniverseError` + `PostCleanupUniverseTooSmallError` per Codex R2.M4 + R3.M2 + R4.M2; rejected-symbol enumeration per Codex R4.m1). **Tests: ~12** per spec §H.1.
- T-V2.1.3: NEW `cfg_substitution.py` module (substitute_cfg per-subsection helpers — 4 subsections; unknown-subsection ValueError; type-preservation invariant). **Tests: ~6** per spec §H.1.

**Acceptance criteria the plan must encode**:
- All 3 modules pass ruff + mypy (if applicable) + 0 E501
- ZERO schwabdev / schwab imports verified via grep
- L2 LOCK reinforcement tests (3 per §3.5) all pass
- `OhlcvCoverageError` typed exception (NEW; writing-plans chooses exact name + module location per OQ-13 work-item)
- Test count: ~30 across 3 modules
- Discriminating test per Expansion #2 refinement: `inspect.signature(read_or_fetch_archive)` assertion verifies V2 NOT depending on the rejected `prefer_source` kwarg (defensive test against future drift)

### §4.2 T-V2.2: sweep.py

**Plan-phase decomposition** (target ~12-18 commits in executing-plans):

- T-V2.2.1: Per-(variable, sweep_point) orchestration core
- T-V2.2.2: Tier-1 baseline parity invariant (CRITICAL; blocking) — V2 with no substitution MUST match V1 persisted bucket distribution exactly per §E.4
- T-V2.2.3: Tier-2 parity reporting (non-blocking; surrogate-flagged) — risk-gate-dependent buckets using `current_equity` surrogate per OQ-15
- T-V2.2.4: Single-variable downstream propagation (e.g., substituted `rs.rs_rank_min_pass` propagates through TT8 → tt_passes → bucket_for)
- T-V2.2.5: `vcp.watch_max_fails` special-case mirroring V1 `_bucket_for_substituted` per OQ-11
- T-V2.2.6: Per-candidate failure isolation (3 modes: ohlcv-coverage skip, out-of-range substitution skip, evaluation-error skip)
- T-V2.2.7: Multi-eval_run universe scan (across 63 eval_runs per OQ-6)
- T-V2.2.8: `current_equity` surrogate threading per OQ-15
- T-V2.2.9: Per-eval_run BatchContext cache (≤315 reconstructions per Codex M4 LOAD-BEARING)
- T-V2.2.10: Per-TICKER OHLCV cache (≤ N_universe + delta opens per Codex R2.M5)

**Acceptance criteria the plan must encode**:
- Tier-1 baseline parity test passes (EXACT match; ZERO tolerance per spec §E.4)
- Tier-2 parity reporting test passes (surrogate-flagged; non-blocking)
- 3 failure-isolation modes each have a discriminating test
- BatchContext + OHLCV cache acceptance bounds asserted
- Test count: ~14 per spec §H.1

### §4.3 T-V2.3: output.py

**Plan-phase decomposition** (target ~8-12 commits in executing-plans):

- T-V2.3.1: CSV emission (12 cols: 9 V1 + 3 NEW skip cols)
- T-V2.3.2: Markdown matrix rendering (12 cols)
- T-V2.3.3: Headline section emit (operator-facing binding-variable summary)
- T-V2.3.4: Per-variable drill-down section (per-flipped-candidate provenance + `bucket_via_surrogate` flag per OQ-15)
- T-V2.3.5: V1↔V2 parity section emit (CRITERION DRIFT alert on mismatch)
- T-V2.3.6: Per-variable scope-reduction notes
- T-V2.3.7: Empty-state representation uniform (per cumulative gotcha lineage)
- T-V2.3.8: Both-exist warning banner surface (per OQ-18 + Codex R4.M1)
- T-V2.3.9: Manifest emission (`both_exist_shape_a_wins_count` + accepted ticker counts + tier-1/tier-2 split + memory peak from tracemalloc per Codex R3.m3)
- T-V2.3.10: ASCII-only output (cp1252 round-trip per cumulative gotcha)

**Acceptance criteria the plan must encode**:
- All output formats render correctly for synthetic inputs
- ASCII-only enforced (Windows cp1252 stdout safety; per cumulative gotcha)
- Manifest emission shape stable
- Test count: ~10 per spec §H.1

### §4.4 T-V2.4: run.py + CLI subcommand registration

**Plan-phase decomposition** (target ~6-10 commits in executing-plans):

- T-V2.4.1: NEW `run.py` orchestrator (`run_harness(...)` entry point)
- T-V2.4.2: CLI argparse boundaries (`--eval-runs` range; `--variables-filter` parsing; `--min-universe-size`; `--max-runtime-seconds` cap)
- T-V2.4.3: ClickException wrapping ValueError per cumulative T-A.1.5b lesson
- T-V2.4.4: Output file path conventions (`exports/diagnostics/v2-ohlcv-<timestamp>.{csv,md}`)
- T-V2.4.5: Baseline smoke test (operator's actual DB shape via fixture)
- T-V2.4.6: CLI subcommand registration in `swing/cli.py` (35-60 lines per OQ-17 LOCK; mirroring V1 at `swing/cli.py:4748-4787`; SOLE production-`swing/` write)
- T-V2.4.7: Subprocess stdout smoke via PowerShell (cp1252 encoding gotcha test per cumulative gotcha)
- T-V2.4.8: `git diff swing/ --stat` discriminating gate (asserts ONLY `swing/cli.py` modified)

**Acceptance criteria the plan must encode**:
- `swing diagnose aplus-sensitivity-v2 --help` shows V2 invocation
- V1 `swing diagnose aplus-sensitivity --help` UNCHANGED (back-compat per OQ-10)
- ClickException wrapping verified per cumulative lesson
- `git diff swing/` gate passes (ONLY `swing/cli.py` modified)
- Test count: ~8 per spec §H.1

### §4.5 T-V2.5: method-record + first study writeup + closer

**Plan-phase decomposition** (target ~6-10 commits in executing-plans):

- T-V2.5.1: Method-record extension at `research/method-records/aplus-criteria-calibration.md` (version bump 0.1.0 → 0.2.0; NEW sections per spec §K.2 + §K.3 + §K.4 + §K.5)
- T-V2.5.2: First study writeup at `research/studies/<V2-ship-date>-v2-ohlcv-criterion-evaluator.md` (per `research/studies/earnings-proximity-exclusion.md` precedent format)
- T-V2.5.3: Operator smoke run against operator's actual DB (5681/63 universe); capture output (CSV + markdown) at `exports/diagnostics/v2-ohlcv-<ship-timestamp>.{csv,md}`
- T-V2.5.4: Update `research/phase-0-tasks.md` "Next" section reflecting V2 OHLCV harness SHIPPED status (first method-record COMPLETED)
- T-V2.5.5: V2 closer commit (commit message cites: V2 OHLCV harness SHIPPED; method-record bumped to 0.2.0; first study writeup; baseline parity invariant green; ZERO Co-Authored-By footer; ALL 18 cumulative gotchas honored)
- T-V2.5.6: Integration / E2E test suite (~6 per spec §H.1)

**Acceptance criteria the plan must encode**:
- Method-record passes V2.1 §IV.B minimum viable field validation
- Study writeup contains: methodology + baseline parity verification + per-variable findings table + Limitations section enumerating OQ-14 + OQ-15 + OQ-18 caveats
- Operator smoke run output captured + committed to `exports/diagnostics/`
- `research/phase-0-tasks.md` "Next" reflects shipped status
- Test count: ~6 (integration + E2E)

### §4.6 Test count summary

Per spec §H.1: ~68 total tests across all 5 sub-bundles.

| Sub-bundle | Test count |
|---|---|
| T-V2.1 | ~30 (ohlcv_reader ~12 + context_builder ~12 + cfg_substitution ~6) |
| T-V2.2 | ~14 |
| T-V2.3 | ~10 |
| T-V2.4 | ~8 |
| T-V2.5 | ~6 (integration / E2E) |
| **Total** | **~68 fast tests** |

Baseline post-V2-ship: 5778 → ~5846 fast tests. NO slow-marked tests in V2 dispatch scope.

---

## §5 Done criteria for writing-plans output

The plan at `docs/superpowers/plans/2026-05-23-v2-ohlcv-criterion-evaluator-plan.md` (or operator-paired-named equivalent) MUST cover:

- [ ] **§A Status + scope** — V1 LIMITATION lift; production read-only invariant with OQ-17 CLI carve-out; 18 OQ dispositions verbatim (per §1 above)
- [ ] **§B Per-sub-bundle design** — for each of T-V2.1..T-V2.5: (i) bite-sized step structure (e.g., T-V2.1.1, T-V2.1.2, ...); (ii) per-step acceptance criteria; (iii) discriminating test list; (iv) commit message template
- [ ] **§C Cross-sub-bundle dependencies** — explicit graph; sequential dispatch sequencing per spec §M.2
- [ ] **§D Module function signatures + class shapes** — refine spec §C.1 + §D.3 proposed shapes to BINDING signatures (writing-plans-phase deliverable per spec §M.3 OQ #1)
- [ ] **§E SQL skeleton verification** — verify every SQL skeleton against actual migration files at `swing/data/migrations/*.sql`; per Expansion #4 refinement, enumerate per-query (a) consumer's row-set scope; (b) JOIN-cardinality assumption; (c) downstream-sufficiency walk; (d) post-mutation re-check semantics
- [ ] **§F Production-function-signature verification** — per Expansion #2 refinement, grep every production-function reference in the plan + verify signature + side-effect contract + error semantics + L2 LOCK preservation; use `inspect.signature()` introspection in discriminating tests where feasible
- [ ] **§G Per-task acceptance criteria** — same as §B but lifted to dispatchable-task granularity; per spec §H.1 test budget projection refined per-task
- [ ] **§H Test scope per-task budget** — baseline 5778 → ~5846 fast expected; ZERO slow tests; ~68 new tests distributed per §4.6 above
- [ ] **§I OQ #9 + OQ #13 work-items resolved** — implementer chooses `--max-runtime-seconds` default (likely UNSET per OQ-9 LOCK) + `OhlcvCoverageError` exact typed exception name + module location (likely `research/harness/aplus_v2_ohlcv_evaluator/exceptions.py`)
- [ ] **§J Forward-binding lessons inherited** — from brainstorming spec §J + cumulative gotcha set (18 cumulative) + 7 expansions + 5 NEW candidate refinements + 2 NEW gotchas #17 + #18
- [ ] **§K L2 LOCK reinforcement** — 3 discriminating tests per §3.5 above enumerated explicitly with test names + file locations
- [ ] **§L Research-branch coordination** — note V2 OHLCV harness SHIPPED status update in `research/phase-0-tasks.md` "Next" section as part of T-V2.5; first method-record extension at `research/method-records/aplus-criteria-calibration.md` (version bump 0.1.0 → 0.2.0; NEW sections per spec §K)
- [ ] **§M Closure procedure** — T-V2.5 acceptance criteria include CLAUDE.md line 3 refresh + orchestrator-context updates + first-study-writeup + operator-smoke-run output capture
- [ ] **§N Per-sub-bundle Codex MCP round-budget expectation** — informed by complexity; writing-plans estimates (T-V2.2 expected highest given largest scope; T-V2.5 expected lowest)

Plan-phase Codex chain expected 2-5 rounds. Pre-Codex 7-expansion + 5 NEW candidate refinements + 18 cumulative gotchas (especially NEW #17 + #18) discipline BINDING; verdict per expansion captured in plan-phase return report.

---

## §6 References

- **Brainstorming spec (BINDING)**: [`docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md`](superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md) at HEAD `362fe18`
- **Brainstorming return report**: [`docs/v2-ohlcv-criterion-evaluator-brainstorm-return-report.md`](v2-ohlcv-criterion-evaluator-brainstorm-return-report.md) at `8532949`
- **Brainstorming dispatch brief**: [`docs/v2-ohlcv-criterion-evaluator-brainstorming-dispatch-brief.md`](v2-ohlcv-criterion-evaluator-brainstorming-dispatch-brief.md) at `acaf305`
- **Turn D handoff brief**: [`docs/orchestrator-handoff-2026-05-23-post-v2-ohlcv-brainstorm-merge-pre-oq-triage.md`](orchestrator-handoff-2026-05-23-post-v2-ohlcv-brainstorm-merge-pre-oq-triage.md) at `08ea67e`
- **Method-record (PRIMARY substrate for T-V2.5)**: [`research/method-records/aplus-criteria-calibration.md`](../research/method-records/aplus-criteria-calibration.md)
- **V1 harness (architecture precedent)**: [`research/harness/aplus_sensitivity/`](../research/harness/aplus_sensitivity/) (variables.py + sweep.py + output.py + run.py + README.md)
- **V1 study writeup**: [`research/studies/aplus-criterion-sensitivity-2026-05-22.md`](../research/studies/aplus-criterion-sensitivity-2026-05-22.md)
- **Research-branch precedent (first applied-research arc shape)**: [`research/harness/earnings_proximity/`](../research/harness/earnings_proximity/) + [`research/studies/earnings-proximity-exclusion.md`](../research/studies/earnings-proximity-exclusion.md) + [`research/method-records/earnings-proximity-exclusion.md`](../research/method-records/earnings-proximity-exclusion.md) + [`research/method-records/_template.md`](../research/method-records/_template.md)
- **Triage agenda (Path B LOCKED 2026-05-23)**: [`docs/phase13-closer-next-phase-triage.md`](phase13-closer-next-phase-triage.md) at `b4d7719`
- **Production `bucket_for`**: `swing/evaluation/scoring.py`
- **Production `evaluate_one`**: `swing/evaluation/evaluator.py`
- **Production criteria**: `swing/evaluation/criteria/*.py` (8 trend_template criteria + 9 vcp criteria + 1 risk criterion)
- **Production OHLCV archive**: `swing/data/ohlcv_archive.py`
- **Production candidate_criteria repo**: `swing/data/repos/candidates.py:78` (write path)
- **Schema migrations**: `swing/data/migrations/0001_phase1_initial.sql` (candidates + candidate_criteria + evaluation_runs) + `swing/data/migrations/*.sql` (subsequent)
- **CLAUDE.md** at repo root (18 cumulative gotchas; NEW #17 + #18 BINDING for 32nd cumulative validation)
- **V2.1 governance**: [`reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md`](../reference/Future%20Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md) + [`reference/Future Work/2026-04-23-rebuttal-response-for-implementors.md`](../reference/Future%20Work/2026-04-23-rebuttal-response-for-implementors.md)
- **Operator's S3 sensitivity-harness output (V1 baseline)**: `exports/diagnostics/aplus-sensitivity-20260523T065514Z.md` + `.csv` (operator's actual S3 run; reference for V1↔V2 parity validation)

---

## §7 NON-scope (V2.5 / V3 / future arc; explicitly out of V2 OHLCV harness dispatch)

- **Schema changes** — V2 is schema-UNCHANGED per spec §A scope (v21 LOCKED)
- **ZERO new Schwab API calls** (L2 LOCK preserved + REINFORCED via §3.5 discriminating tests)
- **Pair-wise / N-D cross-coupling** — V2 stays 1D per OQ-7; 2D+ V3+
- **Adaptive bisection sweep** — V2 inherits V1 5-point grid per OQ-3; adaptive V3+
- **Per-eval_run-historical RS universe snapshots** — V2 uses current-universe snapshot per OQ-14; per-eval_run-historical V3+ (schema change required)
- **`vcp.watch_max_fails` promote-to-cfg** — V2 mirrors V1 special-case per OQ-11; V2.5 candidate (1-line production change at `swing/evaluation/scoring.py:37`)
- **Port production `_backward_compat_rename` merge logic to V2 reader** — V2 ships Shape A wins unconditionally per OQ-18; V2.5 candidate
- **`cfg.trend_template.allowed_miss_names` tuple-set sweep** — V3+ per V1 method-record §"Notes" line 70
- **`cfg.rs.benchmark_ticker` string-identifier sweep** — V3+ per V1 method-record §"Notes" line 70
- **cfg-policy method-record automation post promotion-to-production** — V3+ per OQ-8 ladder
- **Phase 14 commissioning** — DEFERRED until V2 OHLCV harness output informs operational scope per Path B sequencing
- **V2.G1-G4 operator gate bug investigations** — STILL DEFERRED per operator decision 2026-05-23 PM (work AFTER Applied Research tasking completes per `docs/phase3e-todo.md`)

---

## §8 Post-writing-plans handback

When writing-plans Codex chain converges to NO_NEW_CRITICAL_MAJOR:

1. Write return report at `docs/v2-ohlcv-criterion-evaluator-writing-plans-return-report.md` per cumulative precedent (commit chain + per-expansion verdict + Codex chain shape + forward-binding lessons + V2/V3 candidates banked + cumulative streaks).
2. Inline self-verification: ruff check; schema unchanged at v21 (writing-plans touches docs only); baseline 5778 fast tests UNCHANGED.
3. Hand back to operator with summary.

Orchestrator-side next steps post-writing-plans (Turn E):
- QA implementer product per `feedback_orchestrator_qa_implementer_product` (verify file:line + shipped-behavior + locks-preserved against reality on disk)
- Merge writing-plans branch `--no-ff` to main; push
- Post-merge housekeeping bundle (CLAUDE.md line 3 refresh + any NEW gotchas if surfaced + phase3e-todo.md NEW top entry + orchestrator-context.md current state refresh + Prior demote + archive-split per size-check trigger)
- Draft V2 OHLCV executing-plans dispatch brief consuming the operator-affirmed writing-plans plan
- Provide inline implementer dispatch prompt for executing-plans phase
- Note: Turn E may or may not finish executing-plans in same orchestrator turn depending on context budget; another shift (Turn F) may be needed before T-V2.5 ships + operator gates the V2 harness output

---

*End of V2 OHLCV criterion-evaluator harness writing-plans dispatch brief. 18 OQs operator-locked per RECOMMEND with ZERO amendments (strong validation signal for brainstorming-phase Codex chain crispness). ~438+ ZERO Co-Authored-By footer streak preserved through this brief commit. V2 OHLCV applied-research arc IN-FLIGHT (brainstorming SHIPPED `362fe18`; writing-plans next; executing-plans + T-V2.5 closer remain). FIRST Applied Research arc post-Phase-13-FULLY-CLOSED. 32nd cumulative C.C lesson #6 validation expected at writing-plans handback with NEW gotchas #17 + #18 BINDING.*
