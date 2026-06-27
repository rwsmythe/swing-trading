# V2 OHLCV Criterion-Evaluator Harness — Brainstorming Return Report

**Status:** SHIPPED 2026-05-23 PM — first Applied Research arc post-Phase-13-FULLY-CLOSED per Path B operator decision 2026-05-23 PM.

**Branch:** `applied-research-v2-ohlcv-criterion-evaluator-brainstorm` (branched from main HEAD `acaf305`).

**Final HEAD:** `1efec56` (R5 minor sweep + chain CONVERGED).

**Deliverable:** [`docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md`](superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md) — 1086 lines; 14 sections §A-§N including self-review.

---

## §1 Commit chain shape

7 commits total: 1 initial spec + 5 Codex MCP fix bundles + 1 return report.

| # | Commit | Phase | Summary |
|---|--------|-------|---------|
| 1 | `dd6beac` | Initial spec | docs(applied-research): V2 OHLCV criterion-evaluator harness brainstorming spec (915 lines initial; 14 sections §A-§N; 13 OQs) |
| 2 | `c7f2a3c` | Codex R1 | docs(applied-research): V2 OHLCV spec Codex R1 amendments — 2C + 6M + 1m resolved |
| 3 | `5bb2640` | Codex R2 | docs(applied-research): V2 OHLCV spec Codex R2 amendments — 1C + 6M + 2m resolved |
| 4 | `5be32d2` | Codex R3 | docs(applied-research): V2 OHLCV spec Codex R3 amendments — 0C + 2M + 3m resolved |
| 5 | `c9e540e` | Codex R4 | docs(applied-research): V2 OHLCV spec Codex R4 amendments — 0C + 3M + 3m resolved |
| 6 | `1efec56` | Codex R5 (convergence) | docs(applied-research): V2 OHLCV spec Codex R5 minor sweep — chain CONVERGED (NO_NEW_CRITICAL_MAJOR) |
| 7 | THIS COMMIT | Return report | docs(applied-research): brainstorming return report |

ALL commits authored without `Co-Authored-By` trailer per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15). Cumulative ~437+ ZERO Co-Authored-By footer streak preserved.

---

## §2 Codex MCP adversarial-critic chain summary

Chain ran 5 rounds to convergence; verdict at R5: **NO_NEW_CRITICAL_MAJOR**.

| Round | Critical | Major | Minor | Verdict | Disposition |
|-------|----------|-------|-------|---------|-------------|
| R1 | 2 | 6 | 3 | ISSUES_FOUND | All 8 critical+major + 1 minor RESOLVED inline (`c7f2a3c`) |
| R2 | 1 | 6 | 2 | ISSUES_FOUND | All 7 critical+major + 2 minor RESOLVED inline (`5bb2640`) |
| R3 | 0 | 2 | 3 | ISSUES_FOUND | All 2 major + 3 minor RESOLVED inline (`5be32d2`) |
| R4 | 0 | 3 | 3 | ISSUES_FOUND | All 3 major + 3 minor RESOLVED inline (`c9e540e`) |
| R5 | 0 | 0 | 2 | **NO_NEW_CRITICAL_MAJOR** | 2 minor doc-drift items RESOLVED for cleanliness (`1efec56`) |
| **Cumulative** | **3** | **17** | **13** | **CONVERGED** | **ALL 33 findings RESOLVED in-place; ZERO accepted-as-rationale** |

### §2.1 Notable Codex-caught defects against actual code/schema

Codex MCP adversarial-critic verified spec claims against actual code at each round; surfaced REAL defects (not just stylistic concerns):

- **R1.C1**: V2 BatchContext.universe_tickers used candidate-only set; production uses full RS universe per `swing/cli.py:449` + earnings_proximity `run.py:197-201` precedent. RS percentiles + TT8 + baseline parity would break.
- **R1.C2**: `current_equity` not persisted in `candidates`/`evaluation_runs` schema per `swing/data/migrations/0001_phase1_initial.sql:9-56`; baseline parity invariant not achievable as initially specified for risk-gate-dependent buckets.
- **R1.M1**: `read_or_fetch_archive` has NO `prefer_source` parameter per `swing/data/ohlcv_archive.py:172-178`; OQ-12 original proposal not implementable.
- **R1.M2**: `read_or_fetch_archive` actively fetches from yfinance on cache-miss/stale per `swing/data/ohlcv_archive.py:223-237+242-251`; mutates archive between V2 invocations + breaks reproducibility.
- **R1.M3**: `evaluate_one(ctx)` ALWAYS runs all criteria per `swing/evaluation/evaluator.py:37-53`; OHLCV-coverage skip CANNOT be per-(variable, sweep_point) as initially specified.
- **R1.M4**: Performance plan underestimated full-universe parquet I/O cost; per-eval_run BatchContext reuse + per-ticker OHLCV cache are LOAD-BEARING not optional.
- **R1.M5**: "Cross-coupling preserved for free" wording overstated V2 design; 1D sweep does NOT detect multi-variable interaction effects.
- **R1.M6**: Production `swing/` read-only invariant contradicted by CLI subcommand registration in `swing/cli.py`; needs explicit carve-out.
- **R2.C1**: Shape A persists lowercase OHLCV columns per `swing/data/ohlcv_archive.py:449+521-522`; production criteria expect capitalized per `swing/evaluation/criteria/trend_template.py:23` etc. V2 reader would hit `KeyError` without normalization.
- **R2.M1**: 5 stale `read_or_fetch_archive`/`prefer_source` references not scrubbed in R1 amendments; spec inconsistent.
- **R2.M2**: V2 direct read bypasses production `_backward_compat_rename` at `swing/data/ohlcv_archive.py:584-657`; legacy-only-archive tickers falsely report `OhlcvCoverageError`.
- **R2.M3**: Tier-1/tier-2 risk-gate classification needs persisted `risk_feasibility` result; original §F.3 SQL only fetched candidate rows.
- **R2.M4**: `swing.evaluation.rs.load_universe` at `swing/evaluation/rs.py:22-42` returns empty universe for empty/malformed files; silently degrades TT8 to fallback semantics for ALL candidates.
- **R2.M5**: Cache acceptance test bound math inconsistent with per-(ticker, asof_date) cache key; needed per-TICKER cache lock.
- **R2.M6**: CLI carve-out line count 5-10 unrealistic; V1 precedent at `swing/cli.py:4748-4787` is ~40 lines.
- **R3.M1**: Both-exist legacy/Shape A archive case has production merge/freshness logic at `swing/data/ohlcv_archive.py:584+648-649+663+714` that V2 cannot inherit without porting; needed explicit policy.
- **R3.M2**: Universe ticker shape validation gap beyond min-size; malformed CSV with 100 garbage rows would pass min_universe_size=100 silently.
- **R4.M1**: Both-exist Shape A wins policy too silent operationally; needed per-ticker diagnostic surface (count + affected list + warning banner).
- **R4.M2**: Post-cleanup universe size re-check missing; 105-row universe with 9 invalid + 1 duplicate (accepted = 95) silently falls below default min 100.
- **R4.M3**: §H test scope drifted; ~46 stale estimate; new `ohlcv_reader.py` row + 22 additional tests not enumerated.

The R1-R5 chain validates the cumulative C.C lesson #6 discipline: adversarial Codex review catches what brainstorming-phase pre-Codex 7-expansion + 5 NEW candidate refinements miss, especially for cross-substrate verification claims (the spec applied ALL 7+5 expansions at spec-write time AND Codex still surfaced 3 CRITICAL + 17 MAJOR findings).

---

## §3 31st cumulative C.C lesson #6 validation per-expansion

| # | Expansion | Brainstorming-phase pre-Codex disposition | Codex R1-R5 outcome |
|---|-----------|------------------------------------------|---------------------|
| 1 | Hardcoded-duplicate audit | APPLIED at §B.2 + §E.3 (vcp.watch_max_fails = 2 hardcoded; V2 mirrors V1 special-case per OQ-11) | CLEAN at R1-R5; no NEW hardcoded duplicates surfaced |
| 2 | Brief-vs-spec + brief-vs-actual schema verification | APPLIED at §A.2 (schema verification against migration files) | CLEAN at R1-R5 for schema; Codex R1.M1+R1.M2 caught BRIEF-VS-ACTUAL-CODE schema (read_or_fetch_archive signature) — Expansion #2 did NOT catch this because brief did not specify the exact function signature; lesson: Expansion #2 needs to extend from "schema" to "production-function-signature" verification |
| 3 | Schema-CHECK vs semantic-contract gap | N/A V2 (no schema change) | N/A |
| 4 | Specific-scenario gotcha trace + SQL skeleton column verification | APPLIED at §F.3 (SQL skeletons column-verified vs `0001_phase1_initial.sql`) | CLEAN for column-existence; Codex R2.M3 surfaced JOIN-shape gap (needed candidate_criteria for persisted_risk_result); Expansion #4 caught the columns exist but did NOT catch the JOIN was incomplete for tier-1/2 classification — lesson: Expansion #4 needs to extend from "columns exist" to "JOIN-cardinality + sufficiency for downstream requirements" |
| 5 | Cross-section spec inventory grep | APPLIED at §E.2 (per-criterion cfg-variable mapping table) | CLEAN at R1-R5 |
| 6 | Content-completeness audit | APPLIED at §N (self-review) — every dispatch brief §4 checklist item mapped to spec section | CLEAN at R1-R5 |
| 7 | Cross-row semantic SCOPE audit | N/A V2 (no operator-input POST handler) | N/A |
| 8 (cand) | Per-aggregation-function UNIT audit on SQL skeletons | N/A V2 (no GROUP BY / COUNT / SUM in §F.3) | N/A |
| 9 (cand) | Form-render anchor lifecycle 4-dimension audit | N/A V2 (no forms / web routes) | N/A |
| **10 (cand)** | **Architecture-location audit + 5 sub-disciplines** | **APPLIED at §C.1 (NEW module placement + dependency surface verification + sub-discipline (e) orphan-label preservation mapped)** | **NOTABLE: Codex R1.M6 caught CLI carve-out as Expansion #10 sub-discipline (a) architecture-location dependency-surface issue (CLI registration crossed read-only invariant)** — banked CLEAN at R2-R5 post fix |
| **11 (cand)** | **Taxonomy propagation audit** | **APPLIED at §D.3 (V2 SweepEntryV2 inherits V1 `{gate, threshold_additive, threshold_multiplicative}` kind enum verbatim; 3 NEW skip-count fields propagated through dataclass + CSV header + markdown matrix + test fixtures)** | **CLEAN at R1-R5 — V2 did NOT introduce a NEW enum, so propagation was minimal; R5.m1 caught documentation-drift in cumulative-gotcha statement about fixture-shape source (now references new V2 reader)** |
| **12 (cand)** | **Sibling-route audit when introducing single-anchor-binding discipline** | N/A V2 (no route handlers; no single-anchor invariant) | N/A |

**Validation result: 31st cumulative C.C lesson #6 = NOTABLE** (Expansions #2 + #4 surfaced inadequacy in their existing formulation; lessons banked for V2.G OR cumulative gotcha catalog extension):

- **NEW Expansion #2 refinement candidate (BANKED for 32nd cumulative validation)**: brief-vs-actual-production-function-signature verification (extend Expansion #2 from schema to function signatures + parameter shapes for any production function the spec proposes to invoke or extend).
- **NEW Expansion #4 refinement candidate (BANKED for 32nd cumulative validation)**: SQL skeleton JOIN-cardinality + sufficiency audit (extend Expansion #4 from column-existence to "does the JOIN actually fetch all downstream-needed data; would a LEFT JOIN be required to handle missing rows; is the JOIN-cardinality 1:1 or 1:N").

---

## §4 V1 simplifications + V2/V3 candidates banked

10 V2/V3-dependency-cited candidates banked per cumulative discipline (every V1 simplification cites its V2/V3 dependency):

| # | V1 simplification | V2/V3 dependency citation |
|---|-------------------|---------------------------|
| 1 | V2 reads RS universe AT V2 INVOCATION time (current-snapshot surrogate) | V3+: persist per-eval_run universe snapshots at write-time per OQ-14 disposition |
| 2 | V2 uses current `account_equity_snapshots` row as `current_equity` surrogate (fallback if historical snapshots unavailable) | V3+: per-eval_run-historical equity reconstruction OR schema change to persist `current_equity` on `candidates`/`evaluation_runs` per OQ-15 |
| 3 | V2 reads Shape A `{ticker}.yfinance.parquet` ONLY (never schwab_api Shape A) | V2.5 candidate: `vcp.watch_max_fails` promoted to cfg-derived in `bucket_for` (1-line production change per OQ-11) |
| 4 | V2 reads legacy `{ticker}.parquet` as fallback (Shape A wins in both-exist case) | V2.5 candidate: port production `_backward_compat_rename` merge/freshness logic to V2 reader per OQ-18 |
| 5 | V2 ships at status='research' with 3-tier promotion ladder | V3+: cfg-policy automation post promotion-to-production per OQ-8 |
| 6 | V2 inherits V1 5-point sweep grid (no adaptive bisection) | V3+: adaptive bisection sweep strategy per OQ-3 |
| 7 | V2 stays 1D (no cross-variable interaction modeling) | V3+: 2D + multi-variable interaction sweep per OQ-7 |
| 8 | V2 does NOT touch `candidate_criteria` schema for structured threshold columns | V3+: schema change to persist measured numeric values per criterion (existing method-record V2 dependency #2) |
| 9 | V2 excludes `cfg.trend_template.allowed_miss_names` (tuple-set) + `cfg.rs.benchmark_ticker` (string) from sweep | V3+: tuple-set sweep + string-identifier sweep semantics (existing V1 method-record §"Notes" line 70 enumeration) |
| 10 | V2 emits per-V2-invocation `both_exist_shape_a_wins_count` diagnostic but does NOT auto-merge | V2.5 candidate (per #4): port production merge logic to V2 reader OR add pre-V2 hook to invoke production-side merge per OQ-18 option (b)/(c) |

---

## §5 Cumulative streaks preserved

- **ZERO `Co-Authored-By` footer trailer**: ~437+ commits cumulative through this dispatch (7 commits added; ZERO with co-author trailer).
- **Schema v21 UNCHANGED**: brainstorming docs-only; no migration files touched. Verified via `grep -h "UPDATE schema_version SET version" swing/data/migrations/*.sql` → latest is `version = 21` per migration `0021_phase13_t2_sb6c_trades_backlinks.sql`.
- **Baseline 5778 fast tests UNCHANGED**: brainstorming docs-only; no test files touched. V2 writing-plans + executing-plans phases will land +68 fast tests (~5846 total post-V2-ship per §H.3 amended).
- **ZERO new Schwab API calls (L2 LOCK preserved)**: V2 design explicitly reads ONLY `{ticker}.yfinance.parquet` (and legacy `{ticker}.parquet` fallback); NEVER `{ticker}.schwab_api.parquet`. Reinforced through R1-R4 amendments + R4.M1 discriminating test (`ohlcv_reader.py` file-open mock asserts schwab parquet never opened).
- **ZERO production code changes**: only `docs/superpowers/specs/...` touched in this dispatch arc (verified via `git diff --name-only acaf305..HEAD`). The V2 CLI subcommand registration in `swing/cli.py` is BANKED for executing-plans phase per OQ-17 explicit carve-out (NOT shipped in brainstorming).

---

## §6 V1 simplifications enumerated for return-report ledger

Per cumulative T2.SB6b lesson "V1 simplification banking discipline" — every V1 placeholder/simplification cited above is enumerated with V2/V3 dependency. ZERO silent V1 stubs.

---

## §7 OQ enumeration ready for operator-paired triage

18 OQs surfaced for operator-paired triage between brainstorming + writing-plans phases. Each OQ has a RECOMMEND disposition; operator may accept RECOMMEND OR redirect.

Summary table for operator triage session:

| OQ | Topic | RECOMMEND |
|----|-------|-----------|
| 1 | OHLCV reconstruction scope | Direct Shape A read via NEW V2 wrapper (amended per Codex R1+R2 from initial "piggyback OhlcvArchive") |
| 2 | Per-criterion evaluator interface | cfg-substitution via dataclasses.replace + production evaluate_one end-to-end |
| 3 | Sweep range strategy | Inherit V1 5-point grid per V2.1 §IV.B parsimony |
| 4 | Output format | Hybrid: V1 12-col matrix + headline + drill-down + V1↔V2 parity |
| 5 | Scope discipline | All 15 inert threshold variables in one dispatch |
| 6 | Validation universe | Reuse S3's 5681 candidates / 63 eval_runs for V1↔V2 reproducibility |
| 7 | Cross-coupling | 1D per V2.1 §IV.B (single-variable downstream propagation preserved per R2.m2 amendment) |
| 8 | Method-record promotion criteria | 3-tier research→shadow→production ladder per V2.1 §IV.D + §VII.C |
| 9 (NEW) | Performance budget cap | Default UNSET (no cap); `--max-runtime-seconds N` CLI flag for partial runs; <60min target |
| 10 (NEW) | V2 CLI surface name | `swing diagnose aplus-sensitivity-v2` (back-compat with V1) |
| 11 (NEW) | vcp.watch_max_fails hardcode | Mirror V1 `_bucket_for_substituted` special case (V2 ship); BANK V2.5 production 1-line promote-to-cfg |
| 12 (NEW) | Schwab L2 LOCK preservation | yfinance-only via direct Shape A `{ticker}.yfinance.parquet` read (amended per R1+R2 from `prefer_source` proposal) |
| 13 (NEW) | OHLCV coverage failure mode | Skip + report (single ohlcv_coverage_skip_count scalar per V2 invocation per R1.M3) |
| 14 (Codex R1.C1 NEW) | RS universe reconstruction at historical asof_date | Current-universe-snapshot surrogate; per-eval_run-historical V3+ |
| 15 (Codex R1.C2 NEW) | current_equity surrogate for risk gate recompute | Per-eval_run-historical from account_equity_snapshots (fallback to current-equity); bucket_via_surrogate flag in drill-down |
| 16 (Codex R1.M1+M2 NEW) | OHLCV archive read strategy: fetch path vs read-only | Direct Shape A parquet read via NEW V2 wrapper (bypasses read_or_fetch_archive fetch path) |
| 17 (Codex R1.M6 NEW) | CLI subcommand registration as read-only carve-out | Explicit minimal carve-out: subcommand handler + group attachment + Click options + ClickException wrapping + delegation (~35-60 lines per V1 precedent) |
| 18 (Codex R3.M1 NEW) | Both-exist legacy/Shape A archive read policy | Shape A wins unconditionally + per-ticker diagnostic surface (count + affected list + warning banner per R4.M1) |

---

## §8 Inline self-verification

Per §7 of dispatch brief BINDING handback discipline:

### §8.1 Ruff check

Pre-existing ruff items in `research/` (NOT introduced by this brainstorming dispatch). Verified via `git diff --name-only acaf305..HEAD` — only `docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md` was modified. ZERO Python files touched. ZERO new ruff items introduced.

### §8.2 Schema unchanged at v21

Verified via `grep -h "UPDATE schema_version SET version" swing/data/migrations/0021_phase13_t2_sb6c_trades_backlinks.sql` → `UPDATE schema_version SET version = 21` (latest migration is v21; ZERO new migration files added).

### §8.3 Test baseline matches pre-brainstorming

Brainstorming docs-only; ZERO test files touched. Baseline 5778 fast tests UNCHANGED through this dispatch phase. V2 writing-plans + executing-plans phases will land +68 fast tests (~5846 total) per §H.3 amended projection.

### §8.4 ZERO new Schwab API calls

V2 design preserves L2 LOCK by reading ONLY `{ticker}.yfinance.parquet` (Shape A) + legacy `{ticker}.parquet` fallback; NEVER `{ticker}.schwab_api.parquet`. Reinforced through R1-R5 amendments + discriminating test specification at `ohlcv_reader.py` (file-open mock asserts schwab parquet never opened).

### §8.5 ZERO Co-Authored-By footer

All 7 commits in this dispatch arc authored without `Co-Authored-By` trailer. Cumulative ~437+ ZERO-streak preserved. Citation in each commit per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15).

---

## §9 Forward-binding lessons banked for future research-branch arcs OR writing-plans phase

1. **Codex MCP adversarial-critic catches what pre-Codex 7-expansion + 5 NEW candidate refinements miss for cross-substrate verification claims** — V2 brainstorming applied ALL expansions at spec-write time AND Codex still surfaced 3 CRITICAL + 17 MAJOR findings. Confirms the cumulative C.C lesson #6 discipline. Future arcs should NOT skip Codex MCP review on basis of "pre-Codex review was thorough".
2. **NEW Expansion #2 refinement candidate** (banked for 32nd cumulative validation): brief-vs-actual-production-function-signature verification. Extend Expansion #2 from schema/column to function signatures + parameter shapes.
3. **NEW Expansion #4 refinement candidate** (banked for 32nd cumulative validation): SQL skeleton JOIN-cardinality + downstream-sufficiency audit. Extend Expansion #4 from column-existence to JOIN-cardinality (1:1 vs 1:N) + sufficiency-for-downstream-requirements (does the JOIN fetch all data needed downstream).
4. **Research-branch direct Shape A parquet read pattern** — pattern banked for future research-branch harnesses that need to read OHLCV without fetch-path mutation: NEW read-only V2 wrapper bypasses `read_or_fetch_archive`; reads Shape A `{ticker}.yfinance.parquet` (with legacy `{ticker}.parquet` fallback); never opens schwab_api parquet (L2 LOCK preservation pattern).
5. **Tier-1/tier-2 baseline parity discipline for replay harnesses** — when a replay harness invokes production evaluator end-to-end against persisted state, the parity invariant is SCOPED to data the schema actually persists (V2's tier-1 = non-risk-gated buckets; tier-2 = risk-gate-dependent buckets where `current_equity` surrogate is used). Future replay harnesses inheriting `evaluate_one` should enumerate per-context-field persistence status before claiming exact parity.
6. **Both-exist-file diagnostic surface pattern** — when a research-branch reader simplifies a production multi-file resolution policy (e.g., V2's Shape A wins vs production's merge), the simplification MUST surface a per-affected-item diagnostic (count + affected list + warning banner) so the operator sees the affected universe explicitly. Future research-branch readers inherit this pattern.

---

## §10 Handback to operator

V2 OHLCV criterion-evaluator harness brainstorming SHIPPED. Spec converged via Codex MCP adversarial-critic at R5 NO_NEW_CRITICAL_MAJOR; ALL 3 CRITICAL + 17 MAJOR + 13 MINOR findings RESOLVED in-place.

### §10.1 Orchestrator next-steps per dispatch brief §7.1

- QA implementer product per `feedback_orchestrator_qa_implementer_product` BINDING (verify file:line + shipped-behavior + cumulative gotcha citations against reality on disk)
- Merge `applied-research-v2-ohlcv-criterion-evaluator-brainstorm` `--no-ff` to `main`; push
- Post-merge housekeeping bundle (CLAUDE.md line 3 refresh — Applied Research arc IN-FLIGHT pivot post-Phase-13-closed + any NEW gotchas if any + phase3e-todo.md NEW top entry + orchestrator-context.md current state refresh + Prior demote + archive-split per size-check trigger)
- **Operator-paired OQ triage session** (18 OQs surfaced per §I)
- Draft writing-plans dispatch brief consuming the operator-affirmed brainstorming spec + OQ dispositions
- Provide inline implementer dispatch prompt for writing-plans phase

### §10.2 Summary

V2 OHLCV criterion-evaluator harness brainstorming spec is the FIRST applied-research arc post-Phase-13-FULLY-CLOSED. Spec covers all 13 sections §A-§M per dispatch brief done criteria + §N self-review. 18 OQs surfaced (8 dispatch brief + 5 substrate analysis + 4 Codex R1 + 1 Codex R3). Codex MCP adversarial-critic chain ran 5 rounds; ALL findings resolved in-place; chain CONVERGED at R5.

Schema v21 UNCHANGED; baseline 5778 fast tests UNCHANGED; ZERO new Schwab API calls; ZERO Co-Authored-By footer; ZERO production code changes (CLI subcommand registration BANKED for executing-plans per OQ-17). 5-sub-bundle decomposition recommendation at §M.1 (~40-62 commits projected for executing-plans phase; ~68 fast tests projected per §H.1 R4-amended). Method-record extension proposal at §K (version bump 0.1.0 → 0.2.0; NEW sections "V2 OHLCV harness shipped (status='research')" + "Promotion criteria (research→shadow→production)").

Ready for operator-paired OQ triage + writing-plans dispatch brief drafting.

---

*End of V2 OHLCV criterion-evaluator harness brainstorming return report. Spec at [`docs/superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md`](superpowers/specs/2026-05-23-v2-ohlcv-criterion-evaluator-design.md) (1086 lines; 14 sections). Codex chain CONVERGED at R5 NO_NEW_CRITICAL_MAJOR. 31st cumulative C.C lesson #6 validation NOTABLE (Expansions #10 + #11 verified; NEW refinement candidates for Expansions #2 + #4 banked for 32nd validation). Final HEAD: `1efec56`.*
