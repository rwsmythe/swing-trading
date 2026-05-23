# V2 OHLCV Criterion-Evaluator Harness — Brainstorming Design Spec

**Status:** brainstorming spec (pre-writing-plans). First Applied Research arc post-Phase-13-FULLY-CLOSED. Path B LOCKED per operator decision 2026-05-23 PM at [`docs/phase13-closer-next-phase-triage.md`](../../phase13-closer-next-phase-triage.md) commit `b4d7719`.

**Branch:** `applied-research-v2-ohlcv-criterion-evaluator-brainstorm` (branched from main HEAD `acaf305`).

**Predecessor dispatch brief:** [`docs/v2-ohlcv-criterion-evaluator-brainstorming-dispatch-brief.md`](../../v2-ohlcv-criterion-evaluator-brainstorming-dispatch-brief.md) at `acaf305`.

**Lineage:** first deliverable under method-record [`research/method-records/aplus-criteria-calibration.md`](../../../research/method-records/aplus-criteria-calibration.md) per OQ-CL.3 LOCK. V2 OHLCV criterion-evaluator harness extends the V1 sensitivity-harness at [`research/harness/aplus_sensitivity/`](../../../research/harness/aplus_sensitivity/) — does NOT replace it.

**Cumulative streaks preserved through this spec write:** ~434+ ZERO `Co-Authored-By` footer trailer; baseline 5778 fast tests UNCHANGED (brainstorming docs-only); schema v21 UNCHANGED (V2 harness does NOT touch schema per §A.2); ZERO new Schwab API calls (L2 LOCK preserved through V2 design per OQ-12 disposition below).

**Codex Round 1 amendments applied** (8 issues — 2 CRITICAL + 6 MAJOR — resolved inline; per-issue cross-references in §C.1 + §E.4 + §E.5 + §F.1 + §F.4 + §F.5 + §D.1 + §A.1 + new OQ-14 / OQ-15 / OQ-16 / OQ-17 sections at §I + minor citation fix at §B.2):
- C1 RESOLVED: §F.4 — V2 BatchContext `universe_tickers` MUST load the full RS universe (per production `swing/cli.py:449` + earnings_proximity `run.py:197-201` precedent), NOT the per-eval_run candidate set. Otherwise RS percentiles + TT8 break baseline parity. NEW OQ-14 surfaces the universe reconstruction strategy choice.
- C2 RESOLVED: §E.4 — baseline parity invariant SCOPED to NON-risk bucket transitions because `risk_feasibility` consumes `current_equity` which is NOT persisted in `candidates`/`evaluation_runs` schema. NEW OQ-15 surfaces the `current_equity` reconstruction strategy.
- M1 + M2 RESOLVED: §F.1 + OQ-12 — `read_or_fetch_archive` has no `prefer_source` parameter AND it actively fetches from yfinance on cache-miss/stale. V2 reads Shape A parquet files directly via a NEW read-only `ohlcv_reader.py` wrapper that bypasses the fetch path. NEW OQ-16 surfaces the read-only-vs-fetch decision.
- M3 RESOLVED: §E.5 — `evaluate_one` ALWAYS runs all criteria; OHLCV-coverage skip is per-CANDIDATE (one decision shared across all variables for that candidate), NOT per-variable. Single `ohlcv_coverage_skip_count` value per matrix.
- M4 RESOLVED: §F.5 — per-eval_run BatchContext reuse is LOAD-BEARING (not optional). Full-universe OHLCV reads dominate runtime, not `evaluate_one` invocations.
- M5 RESOLVED: §D.1 + OQ-7 — terminology corrected: "single-variable downstream propagation preserved" (NOT "cross-coupling preserved"); a 1D sweep does NOT detect interaction effects between thresholds.
- M6 RESOLVED: §A.1 — CLI subcommand registration in `swing/cli.py` is the EXPLICIT MINIMAL carve-out from the read-only invariant. NEW OQ-17 surfaces the carve-out scope.
- Minor m1 RESOLVED: line 35 → line 37 citation corrected at §B.2.

**Codex Round 2 amendments applied** (1 CRITICAL + 6 MAJOR + 2 MINOR — all RESOLVED inline):
- R2.C1 RESOLVED: §F.1 — Shape A persists OHLCV columns as lowercase (`open/high/low/close/volume` per `swing/data/ohlcv_archive.py:449+521-522`); production criteria expect capitalized. V2 `ohlcv_reader.py` MUST normalize lowercase → capitalized at read boundary.
- R2.M1 RESOLVED: scrubbed stale `read_or_fetch_archive`/`prefer_source` references across §A.5, §C.1 dependency table, §F.2, OQ-1 RECOMMEND, OQ-12 RECOMMEND (5 separate sections updated to consistently route through the NEW `ohlcv_reader.py` wrapper).
- R2.M2 RESOLVED: §F.1 — V2 reader handles legacy `{ticker}.parquet` fallback (production `_backward_compat_rename` at `swing/data/ohlcv_archive.py:584-657` is invoked inside `read_or_fetch_archive` ONLY; V2's direct-read bypass needs its own legacy fallback path).
- R2.M3 RESOLVED: §F.3 — SQL extended with LEFT JOIN to `candidate_criteria` to fetch `persisted_risk_result` for tier-1 vs tier-2 parity classification per §E.4.
- R2.M4 RESOLVED: §F.4 — RS universe load fails-fast with `EmptyRsUniverseError` if loaded universe is empty OR has < N_MIN tickers (default 100; configurable via `--min-universe-size`).
- R2.M5 RESOLVED: §F.5 — V2 OHLCV cache key choice: per-TICKER (full-history frame; in-memory slice for asof_date), NOT per-(ticker, asof_date). Parquet open count bound = `N_universe + N_candidate_tickers_not_in_universe`.
- R2.M6 RESOLVED: §A.1 + OQ-17 — CLI carve-out described by SURFACE/RESPONSIBILITY (subcommand handler + group attachment + Click options + error wrapping + delegation), NOT line count. Realistic V2 line count is 35-60 (V1 precedent spans `swing/cli.py:4748-4787`); the original 5-10 line estimate was unrealistic.
- R2.m1 RESOLVED: §F.4 — `universe_hash` renamed `v2_universe_hash_` prefix + SHA-256 (matches production `swing/evaluation/rs.py:45-49`); NOT comparable to persisted `evaluation_runs.rs_universe_hash`.
- R2.m2 RESOLVED: scrubbed stale "cross-coupling preserved for free / within a single 1D substitution" wording in OQ-2 + OQ-7 RECOMMEND (replaced with "single-variable downstream propagation preserved").

**Codex Round 3 amendments applied** (0 CRITICAL + 2 MAJOR + 3 MINOR — all resolved inline):
- R3.M1 RESOLVED: §F.1 — both-exist legacy/Shape A policy LOCKED to "Shape A wins unconditionally"; caveat documented; NEW OQ-18 surfaces operator triage choice (V2.5 candidate: port production merge logic to V2 reader).
- R3.M2 RESOLVED: §F.4 — RS universe validation extended from non-empty + min-size to also include (b) ticker-shape regex validation + (c) duplicate detection. Three discriminating tests added.
- R3.m1 RESOLVED: §F.5 cost table updated to reflect per-TICKER cache choice (was inconsistent with per-(ticker, asof_date) original framing).
- R3.m2 confirmed §F.1 column normalization is feasible (no action; just confirmation).
- R3.m3 RESOLVED: §F.5 acceptance criteria add `test_v2_smoke_records_memory_footprint` using `tracemalloc.get_traced_memory()` (non-blocking instrumentation).

**Codex Round 4 amendments applied** (0 CRITICAL + 3 MAJOR + 3 MINOR — all resolved inline):
- R4.M1 RESOLVED: §F.1 — both-exist Shape A wins policy now emits per-ticker diagnostic surface: `both_exist_shape_a_wins_count` manifest field + markdown warning banner with affected ticker list + WARNING log per-ticker. Operator sees affected tickers explicitly, not just "documented in study limitations".
- R4.M2 RESOLVED: §F.4 — post-cleanup universe size re-check added. After dropping invalid + dedup rows, if accepted-tickers < min_universe_size → fail-fast `PostCleanupUniverseTooSmallError`. Discriminating test added.
- R4.M3 RESOLVED: §H.1 test scope expanded from ~46 to ~68 tests; NEW `ohlcv_reader.py` test row added; other module rows expanded for R2/R3/R4 amendments. §H.3 baseline projection updated from +46 to +68 fast tests.
- R4.m1 RESOLVED: §F.4 — warnings include rejected symbol list (capped at 20) for operator allowlist remediation.
- R4.m2 confirmed §F.5 internally consistent (no action).
- R4.m3 RESOLVED: OQ-17 + OQ-18 reordered numerically.

OQ count UNCHANGED at 18 (R4 surfaced no NEW operator triage questions).

---

## §A Status + scope

### §A.1 Research-branch positioning (V2.1 §V)

V2 OHLCV criterion-evaluator harness lives under `research/` per V2.1 §V branch posture:

- **NEW module**: `research/harness/aplus_v2_ohlcv_evaluator/` (4-6 files; see §C.1 module breakdown). NOT a fork of `research/harness/aplus_sensitivity/`; the V1 harness STAYS as the gate-variable assessment surface per §A.4.
- **NEW study writeup**: `research/studies/<date>-v2-ohlcv-criterion-evaluator.md` (companion to existing `aplus-criterion-sensitivity-2026-05-22.md`). Follows the format precedent from `research/studies/earnings-proximity-exclusion.md`.
- **Method-record EXTENSION** (not new record): append-only sections at [`research/method-records/aplus-criteria-calibration.md`](../../../research/method-records/aplus-criteria-calibration.md) (see §K). The existing 72-line record stays; V2 sections appended below the existing "V2 dependencies" section + corresponding promotion criteria bullets added to the existing "Validation notes" + "Notes" sections.
- **Tests** under `tests/research/test_aplus_v2_ohlcv_*.py` mirroring T-T4.SB.1 precedent at `tests/research/test_aplus_sensitivity_*.py`. Test count budget per §H.
- **Production `swing/` code is READ-ONLY through this dispatch arc EXCEPT for ONE explicit minimal carve-out** (per OQ-17 RECOMMEND amended per Codex R2.M6): a CLI subcommand registration in `swing/cli.py` registers `swing diagnose aplus-sensitivity-v2`. Scope of the carve-out is described by SURFACE / RESPONSIBILITY rather than line count: the carve-out covers (a) a `@click.command` decorated function (subcommand handler) + (b) `@diagnose.command` group attachment + (c) Click `@click.option` definitions for the V2 CLI flags (per §C.2) + (d) `ClickException` wrapping per cumulative T-A.1.5b lesson + (e) delegation to `research.harness.aplus_v2_ohlcv_evaluator.run.run_harness`. Per V1 precedent at `swing/cli.py` (V1 `swing diagnose aplus-sensitivity` registration spans roughly `swing/cli.py:4748-4787` per Codex R2.M6 verification), a realistic V2 subcommand with new flags + error wrapping will be in the 35-60 line range. This is the SOLE production-`swing/` modification V2 dispatch makes. NO other writes to `swing/`, NO writes to `swing-data/swing.db` domain tables, NO schema changes.

  V2 imports (READ-ONLY usage) from `swing.evaluation.evaluator.evaluate_one` + `swing.evaluation.scoring.bucket_for` + `swing.evaluation.context.{CandidateContext, BatchContext, MarketContext}` + `swing.config.Config` + `swing.data.ohlcv_archive` Shape A parquet reader path (NOT `read_or_fetch_archive` per Codex M1 + M2 disposition; see §F.1 amendment).

### §A.2 Schema discipline (LOCK)

Schema v21 is the LOCKED schema. V2 SHOULD NOT touch migrations.

The brainstorming spec EXPLICITLY does NOT propose any v22 delta. Per the existing method-record V2 dependency #2 ("Structured threshold columns on `candidate_criteria`") — that V3+ work pushes value substitution into SQL and is NOT in V2 OHLCV harness scope.

Verified at brainstorming-phase pre-Codex Expansion #4 refinement (BINDING for 26th cumulative validation onwards — "every SQL skeleton's columns verified against actual migration files"): the V2 harness's SQL skeletons (§F.3) read ONLY existing columns:

- `evaluation_runs.id` + `evaluation_runs.data_asof_date` + `evaluation_runs.action_session_date` per `swing/data/migrations/0001_phase1_initial.sql:9-21`
- `candidates.id` + `candidates.evaluation_run_id` + `candidates.ticker` + `candidates.bucket` per `swing/data/migrations/0001_phase1_initial.sql:24-42`
- `candidate_criteria.candidate_id` + `candidate_criteria.criterion_name` + `candidate_criteria.layer` + `candidate_criteria.result` + `candidate_criteria.value` + `candidate_criteria.rule` per `swing/data/migrations/0001_phase1_initial.sql:48-56`

ZERO new columns referenced. ZERO new table references. ZERO CHECK enum widenings. Verified via `grep -n` against `swing/data/migrations/0001_phase1_initial.sql` at spec-write time.

### §A.3 V2.1 §IV.D + §VII.C lifecycle posture

The existing method-record `aplus-criteria-calibration` is at `status='research'`. V2 OHLCV harness output is the evidence summary that operator + research branch evaluate for promotion to `shadow` and eventually `production` per V2.1 §VII.C.

V2 harness ships at `status='research'` (no `shadow` claim at landing). Promotion criteria proposed at §K.3 (binding for downstream Applied Research arcs; NOT triggered by V2 ship itself).

### §A.4 V1 harness retention (no replacement)

The V1 aplus_sensitivity harness at `research/harness/aplus_sensitivity/` STAYS as the gate-variable quick assessment surface. The CLI `swing diagnose aplus-sensitivity` continues to invoke V1 unchanged.

V2 ships under a NEW CLI surface name `swing diagnose aplus-sensitivity-v2` per OQ-10 RECOMMEND (less invasive than renaming V1). V2 + V1 share the variable enumeration at `research/harness/aplus_sensitivity/variables.py` (V2 imports `enumerate_variables(cfg)` to inherit the 17-variable set verbatim); V2 + V1 share the cfg + ohlcv-archive read-only interfaces. V2 differs from V1 ONLY in the substitution semantics (live `evaluate_one` recompute vs persisted-bucket passthrough).

### §A.5 Non-scope (V3+ / future arc; explicitly out of V2)

- **Schema changes** — `candidate_criteria` structured threshold columns is V3+ work per existing method-record V2 dependency #2.
- **Multi-D sensitivity sweep** — pair-wise variable interaction is V3+ per V2.1 §IV.B parsimony (see §B.5 + OQ-7).
- **cfg-policy automation** — automatic cfg updates based on V2 output is POST-promotion-to-`production` lifecycle work; V2 ships at `status='research'` per §A.3.
- **Phase 14 commissioning** — deferred per OQ-CL.2 LOCK until V2 outputs inform operational scope.
- **V2.G1-G4 operator gate bug investigations** — deferred per operator decision 2026-05-23 PM (worked AFTER Applied Research tasking per operator direction; banked at `docs/phase3e-todo.md` §"Post-T4.SB-SHIPPED operator gate feedback").
- **Production `swing/` code changes** — V2 harness is research-branch only; production stack stable through V2 dispatch (per §A.1 final paragraph).
- **`cfg.trend_template.allowed_miss_names` (tuple-set) sweep** — non-numeric grid; V3+ candidate per V1 method-record §"Notes" line 70.
- **`cfg.rs.benchmark_ticker` (string identifier) sweep** — non-numeric; not a threshold; V3+ candidate per V1 method-record §"Notes" line 70.
- **Adaptive bisection sweep strategy** — V2 inherits the V1 5-point grid (OQ-3 RECOMMEND). Adaptive bisection deferred V3+ per V2.1 §IV.B parsimony.
- **Schwab API calls** — V2 OHLCV reconstruction uses yfinance-only by direct Shape A parquet read via the NEW `ohlcv_reader.py` wrapper that opens ONLY `{ticker}.yfinance.parquet` (legacy fallback `{ticker}.parquet`); NEVER touches `{ticker}.schwab_api.parquet`. Per OQ-12 + OQ-16 amended RECOMMEND (preserves L2 LOCK; no new Schwab API calls; no fetch path; no archive mutation).

---

## §B Research question + S3 findings inheritance

### §B.1 Operator motivating question (per Path B disposition)

> Which of the 15 inert threshold variables (V1 LIMITATION at `research/harness/aplus_sensitivity/sweep.py:248-250`) are binding at the watch→A+ promotion boundary, ranked by marginal A+ count per loosening unit?

V2 harness output MUST answer this directly. The output format (§G) is designed to surface the binding-variable ranking in the top-line summary section.

### §B.2 V1 sensitivity-harness output (S3) findings inherited

Per operator-paired triage session 2026-05-23 PM (at [`docs/phase13-closer-next-phase-triage.md`](../../phase13-closer-next-phase-triage.md) §"Findings from 2026-05-23 S3 sensitivity-harness review"):

**Baseline** (5681 candidates across 63 eval_runs):
- Gate-variable view: A+ = 5 / Watch = 1184 / Skip = 4492 / Excluded = 0
- Threshold-variable view: A+ = 5 / Watch = 1186 / Skip = 4277 / Excluded = 168 (V1 path-attribution artifact; headline holds)

**Gate findings (LIVE-recompute; 2 variables)** — both NON-BINDING at the watch→A+ boundary:
- `trend_template.min_passes=7` (current) → loosening to 5/6 produces ZERO A+ delta; tightening to 8 trims 87 Watch (-7%) without changing A+; tightening to 9 collapses A+ (only 8 TT criteria exist; implicit ceiling).
- `vcp.watch_max_fails=2` (current; HARDCODED in `swing/evaluation/scoring.py:37` as the literal `2` in `if vcp_fails <= 2:`, NOT cfg-derived) → sweep 0→4 produces 0/234/1184/2874/3968 Watch counts with A+ UNCHANGED at 5 across all sweep points. Pure Watch-fanout dial.

**Threshold findings (15 variables — INERT under V1 per V1 LIMITATION)**:

Verbatim from S3 markdown at `exports/diagnostics/aplus-sensitivity-20260523T065514Z.md`:

| # | Variable | Kind | V1 sweep range |
|---|----------|------|----------------|
| 1 | `trend_template.rising_ma_period_days` | threshold_additive | 11..31 (21 sweep points; current 21) |
| 2 | `trend_template.high_52w_margin_pct` | threshold_multiplicative | 12.5, 18.75, 25.0, 31.25, 37.5 (current 25.0) |
| 3 | `trend_template.low_52w_min_pct` | threshold_multiplicative | 15.0, 22.5, 30.0, 37.5, 45.0 (current 30.0) |
| 4 | `vcp.prior_trend_min_pct` | threshold_multiplicative | 12.5, 18.75, 25.0, 31.25, 37.5 (current 25.0) |
| 5 | `vcp.adr_min_pct` | threshold_multiplicative | 2.0, 3.0, 4.0, 5.0, 6.0 (current 4.0) |
| 6 | `vcp.pullback_max_pct` | threshold_multiplicative | 12.5, 18.75, 25.0, 31.25, 37.5 (current 25.0) |
| 7 | `vcp.proximity_max_pct` | threshold_multiplicative | 2.5, 3.75, 5.0, 6.25, 7.5 (current 5.0) |
| 8 | `vcp.tightness_days_required` | threshold_additive | 0, 1, 2, 3, 4 (current 2) |
| 9 | `vcp.tightness_range_factor` | threshold_multiplicative | 0.335, 0.5025, 0.67, 0.8375, 1.005 (current 0.67) |
| 10 | `vcp.orderliness_max_bar_ratio` | threshold_multiplicative | 1.5, 2.25, 3.0, 3.75, 4.5 (current 3.0) |
| 11 | `vcp.orderliness_max_range_cv` | threshold_multiplicative | 0.3, 0.45, 0.6, 0.75, 0.9 (current 0.6) |
| 12 | `risk.max_risk_pct` | threshold_multiplicative | 0.0025, 0.00375, 0.005, 0.00625, 0.0075 (current 0.005) |
| 13 | `rs.horizon_weeks` | threshold_additive | 10, 11, 12, 13, 14 (current 12) |
| 14 | `rs.rs_rank_min_pass` | threshold_additive | 60..80 (21 sweep points; current 70) |
| 15 | `rs.fallback_extreme_pct` | threshold_multiplicative | 10.0, 15.0, 20.0, 25.0, 30.0 (current 20.0) |

V2 covers all 15 in one dispatch per OQ-5 RECOMMEND. Per-variable hypothesis enumeration at §B.4.

### §B.3 Headline interpretation feedback to V2 design

Per S3 review:

> The 5-A+-candidates-across-63-eval_runs constraint is therefore caused by EITHER:
> 1. The 15 untested threshold criteria — V2 OHLCV harness needed to identify which one(s) are binding.
> 2. Market conditions (no qualifying setups in the universe regardless of threshold).
> 3. Other gates not enumerated as `kind=gate` in V1 (e.g., `risk_feasibility` hard pre-filter, Stage-2 trend status that isn't part of TT8-count).

V2 design directly addresses (1). V2 design surfaces (2) via the baseline-recompute parity invariant (§E.4). V2 design partially addresses (3) by making the per-candidate per-criterion re-evaluation visible in the drill-down (§G.2) — operator can inspect WHICH criterion is failing for the watch-bucket candidates that don't promote to A+, even when the substituted threshold is loose.

### §B.4 Per-variable hypothesis (which threshold variables might be binding)

Pre-V2-run hypothesis ranking (operator + research-branch shared model). Banked to test against V2 output post-ship:

- **HIGH binding-likelihood candidates** (often-cited as overly strict in operator review):
  - `vcp.orderliness_max_bar_ratio` (3.0 default; bars-with-large-range often filter out otherwise valid setups)
  - `vcp.orderliness_max_range_cv` (0.6 default; CV is sensitive to a single outlier bar)
  - `vcp.tightness_range_factor` (0.67 default; tighter than many real-world bases)
  - `vcp.proximity_max_pct` (5.0% default; "near pivot" can exclude bases consolidating 6-8% below pivot)
  - `rs.rs_rank_min_pass` (70 default; RS<70 names with strong absolute setup are excluded)
- **MEDIUM binding-likelihood**:
  - `vcp.adr_min_pct` (4.0% default; low-vol stocks filtered out)
  - `vcp.prior_trend_min_pct` (25.0% default; mid-run setups filtered out)
  - `vcp.pullback_max_pct` (25.0% default; deeper-pullback bases filtered out)
  - `trend_template.high_52w_margin_pct` (25.0% default; TT7 strict)
- **LOW binding-likelihood** (often non-tight at the watch boundary):
  - `vcp.tightness_days_required` (2 default; usually met by valid bases)
  - `trend_template.rising_ma_period_days` (21 default; 200-MA usually rising at these scales)
  - `trend_template.low_52w_min_pct` (30% default; TT6 usually met)
  - `risk.max_risk_pct` (0.5% default; affects share count not bucket)
  - `rs.horizon_weeks` (12 default; structural parameter not boundary)
  - `rs.fallback_extreme_pct` (20.0% default; affects only outside-universe tickers)

V2 output ranks all 15 by ACTUAL marginal A+ count per loosening unit and confirms / refutes this hypothesis.

### §B.5 Null hypothesis for V2 study

> No single threshold variable substitution, within the V1 5-point sweep grid, produces a material delta in `aplus_count` against the operator's retained 5681-candidate / 63-eval_run universe.

V2 rejects the null iff ≥1 variable produces a non-zero `delta_aplus` at any sweep point. The threshold of "material" is operator-paired (banked as OQ-8 promotion-criteria sub-question; default proposed: ≥5 A+ delta on a 5681-candidate universe, i.e., doubling the A+ count).

---

## §C V2 OHLCV evaluator architecture

### §C.1 Module placement decision (Expansion #10 architecture-location BINDING applied)

Pre-Codex Expansion #10 (architecture-location audit) discipline BINDING for 31st cumulative C.C lesson #6 validation:

- **NEW module `research/harness/aplus_v2_ohlcv_evaluator/`** for cross-cutting V2 logic. Justification:
  - V1 `research/harness/aplus_sensitivity/sweep.py:run_sensitivity_sweep` is shaped around PERSISTED-bucket consumption — its data flow is `candidate_criteria` rows in / sweep-counts out. V2's data flow is fundamentally different: `candidates` + OHLCV archive in / per-candidate re-evaluated buckets out. Forking sweep.py to add V2 substitution would cross dependency-context boundaries (sweep.py has no OHLCV-cache plumbing; no `evaluate_one` invocation site).
  - The V1 `_bucket_for_substituted` function in sweep.py is a STANDALONE mirror of `bucket_for` semantics for the gate-variable resimulation path. V2 invokes the REAL production `evaluate_one` end-to-end (per §D.1); this is structurally different from a substituted-bucket mirror. Sharing a module would conflate two distinct architectural patterns.
- **Shared with V1 (READ-ONLY imports)**:
  - `research.harness.aplus_sensitivity.variables.SweepVariable` + `research.harness.aplus_sensitivity.variables.enumerate_variables` — V2 inherits the 17-variable set verbatim (3 gate + 15 threshold from V1 enumeration; V2 substitutes ALL 17 via OHLCV recompute; V1's gate-variable special-case path becomes redundant in V2, but the enumeration is shared).
  - **Architectural note on V1↔V2 variable substitution divergence**: V1 has SPECIAL-CASE `_bucket_for_substituted` for 2 gate variables (cfg-derived `trend_template.min_passes` + hardcoded `vcp.watch_max_fails`) + parity-passthrough for 15 threshold variables. V2 has UNIFORM end-to-end recompute for the cfg-derived 14 of the 15 threshold variables AND `trend_template.min_passes` — but the hardcoded `vcp.watch_max_fails` in `swing/evaluation/scoring.py:37` requires SPECIAL-CASE substitution (see OQ-11 + §E.3).

**V2 module file layout** (proposed; subject to writing-plans refinement):

```
research/harness/aplus_v2_ohlcv_evaluator/
  __init__.py
  context_builder.py        # rebuilds CandidateContext at historical data_asof_date
  cfg_substitution.py       # dataclasses.replace on Config for per-variable substitution
  sweep.py                  # V2 sweep orchestrator (per-candidate per-sweep-point evaluate_one)
  output.py                 # V2 output formatter (sensitivity matrix + per-variable drill-down)
  run.py                    # CLI entry point
```

**Dependency surface verification per Expansion #10 sub-discipline (a) architecture-location audit**:

| Module | Dependencies | Justification |
|--------|--------------|---------------|
| `context_builder.py` | `research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader` (NEW V2 read-only Shape A wrapper per §F.1 amended), `swing.evaluation.context.{CandidateContext, BatchContext, MarketContext}`, `swing.config.Config`, `swing.evaluation.rs.compute_rs`, `swing.evaluation.rs.load_universe` (for RS universe load per §F.4) | All READ-ONLY production imports (plus NEW V2 reader). OHLCV slicing + 12-week-return computation + RS batch context reconstruction at historical asof_date. NOTE: does NOT import `swing.data.ohlcv_archive.read_or_fetch_archive` per Codex M1+M2 amendment — direct Shape A read via V2 reader instead. |
| `ohlcv_reader.py` (NEW per Codex M1+M2 amendment) | `pandas`, `pathlib.Path`, NO yfinance / NO Schwab imports | Read-only Shape A parquet wrapper at `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py`. Opens `{ticker}.yfinance.parquet` (or legacy `{ticker}.parquet` fallback per Codex R2.M2); normalizes lowercase OHLCV cols to capitalized per Codex R2.C1; NEVER opens `{ticker}.schwab_api.parquet`. NO fetch. NO write. |
| `cfg_substitution.py` | `swing.config.{Config, TrendTemplate, VCP, Risk, RS}`, `dataclasses.replace` | Pure cfg-substitution via `dataclasses.replace`. No I/O. |
| `sweep.py` | `swing.evaluation.evaluator.evaluate_one`, `swing.evaluation.scoring.bucket_for` (for `vcp.watch_max_fails` special-case per §E.3), `swing.config.Config`, `research.harness.aplus_sensitivity.variables.{SweepVariable, enumerate_variables}`, `cfg_substitution.substitute_cfg`, `context_builder.build_candidate_context`, `sqlite3.Connection` (READ-ONLY for `evaluation_runs` + `candidates` + `candidate_criteria` SQL) | Per-candidate per-sweep-point orchestration. Reads candidate universe from operator DB. NO writes. |
| `output.py` | `dataclasses`, `csv`, `pathlib.Path`, V2 result dataclasses from `sweep.py` | Pure I/O formatter. ASCII-only output (Windows cp1252 safety per cumulative gotcha). |
| `run.py` | `argparse`, `sqlite3`, all V2 modules + `swing.config.Config.from_defaults` | CLI entry. Click delegation from `swing diagnose aplus-sensitivity-v2` (registered in `swing/cli.py`; V2 dispatch's only `swing/` modification is the CLI subcommand registration). |

Expansion #10 sub-discipline (c) cache-key shape + renderer-kwargs uniformity LOCK: V2 produces NO chart_renders rows. N/A.

Expansion #10 sub-discipline (d) SQL LIKE wildcard-escape: V2 produces NO LIKE-pattern SQL. N/A.

Expansion #10 sub-discipline (e) orphan-label preservation: V2 GROUP BY semantics replace V1 persisted-bucket passthrough with live recompute. Orphan-handling — candidates that V2 cannot evaluate due to OHLCV-coverage gaps — are explicitly handled per §E.5 + OQ-13 disposition (skip + per-variable count + per-study scope-reduction count surfaced in output).

### §C.2 CLI surface registration

NEW CLI subcommand `swing diagnose aplus-sensitivity-v2` registered in `swing/cli.py` (the ONLY production-`swing/` file V2 dispatch modifies — a 1-function CLI subcommand-registration block per Phase 13 T4.SB precedent for `swing diagnose aplus-sensitivity`). Delegates to `research.harness.aplus_v2_ohlcv_evaluator.run.run_harness`.

Per-flag contract:

```
swing diagnose aplus-sensitivity-v2 --db PATH [--eval-runs N] [--output-dir DIR] [--variables-filter NAME[,NAME...]] [--max-runtime-seconds N]
```

- `--db PATH` — operator's `swing-data/swing.db`. REQUIRED (mirror V1).
- `--eval-runs N` — default 20; max 100; range `[1, 100]` (mirror V1).
- `--output-dir DIR` — default `exports/diagnostics/` (mirror V1).
- `--variables-filter NAME[,NAME...]` — optional comma-separated variable-name filter for incremental runs / debugging. Default: ALL 17 variables (15 threshold + 2 gate).
- `--max-runtime-seconds N` — optional runtime cap (default UNSET = no cap). When provided, the harness emits a partial-result CSV + markdown with explicit "PARTIAL RUN — cap=N seconds — N of M variables completed" header. See OQ-9 RECOMMEND.

Per cumulative Phase 13 T-A.1.5b lesson "Service-layer ValueErrors must be wrapped at CLI boundary", the CLI subcommand wraps ALL service-layer dispatches in `try: ... except ValueError as exc: raise click.ClickException(str(exc))`.

### §C.3 Output paths

- CSV: `exports/diagnostics/aplus-sensitivity-v2-<ISO>.csv`
- Markdown: `exports/diagnostics/aplus-sensitivity-v2-<ISO>.md`

`<ISO>` is UTC `%Y%m%dT%H%M%SZ` (mirror V1 at `research/harness/aplus_sensitivity/run.py:48`).

V2 + V1 outputs coexist in `exports/diagnostics/` with distinct filename prefixes (`aplus-sensitivity-` vs `aplus-sensitivity-v2-`) for operator-side V1↔V2 comparison.

---

## §D Per-criterion evaluator design

### §D.1 Interface decision: cfg-substitution + production `evaluate_one(ctx)` end-to-end (OQ-2 RECOMMEND)

V2 substitutes ONE variable at a time via `dataclasses.replace(cfg.<sub>, <field>=<sweep_value>)` + invokes the production `swing.evaluation.evaluator.evaluate_one(ctx)` per candidate per sweep point. The end-to-end recompute preserves:

- **Single-variable downstream propagation** (Codex M5 RESOLVED — terminology corrected from "cross-coupling preserved for free" which overstated the V2 design). Example: substituting `rs.rs_rank_min_pass=60` propagates through `compute_rs(...).rank >= 60` in TT8 → flips tt8 result → may flip `tt_passes` count → may move `bucket_for` from skip to watch to aplus. V2 captures THIS downstream effect faithfully — but a 1D sweep does NOT detect interaction effects between MULTIPLE thresholds (e.g., the joint effect of loosening `rs.rs_rank_min_pass` AND `vcp.adr_min_pct` simultaneously may differ from the sum of each variable's solo effect). Multi-variable interaction is V3+ per V2.1 §IV.B parsimony (OQ-7 RECOMMEND stays 1D for V2).
- **`allowed_miss_names` invariant** preserved verbatim per `swing/evaluation/scoring.py:27` (no V1 `_bucket_for_substituted` mirror needed).
- **Risk hard-filter semantics** preserved verbatim per `swing/evaluation/scoring.py:20`.
- **VCP-fails (`na` counts as fail) semantics** preserved verbatim per `swing/evaluation/scoring.py:34`.

The alternative (OQ-2 option b: explicit override-dict + per-criterion evaluator consuming `(bars, threshold, ...)`) was rejected because (a) it requires reimplementing each criterion's threshold-consumption logic in a parallel surface (HIGH drift risk vs production criteria); (b) it does NOT preserve cross-coupling without explicit modeling; (c) it scales poorly as new criteria are added (each new criterion requires V2-side adapter).

### §D.2 cfg-substitution implementation pattern

Per substitution call:

```python
# pseudo-code; actual signature TBD in writing-plans phase
def substitute_cfg(cfg: Config, variable_name: str, sweep_value: float | int) -> Config:
    """Return a NEW Config with variable_name = sweep_value; other fields unchanged.

    variable_name format: '<sub>.<field>' (e.g., 'trend_template.min_passes',
    'vcp.adr_min_pct', 'rs.rs_rank_min_pass'). The 'vcp.watch_max_fails'
    special case is NOT routed through this helper — see §E.3.
    """
    sub, field = variable_name.split(".", 1)
    if sub not in {"trend_template", "vcp", "risk", "rs"}:
        raise ValueError(f"Unknown cfg subsection: {sub!r}")
    sub_obj = getattr(cfg, sub)
    new_sub = dataclasses.replace(sub_obj, **{field: sweep_value})
    return dataclasses.replace(cfg, **{sub: new_sub})
```

**Type-preservation invariant**: `sweep_value` MUST match the field's expected type (int for additive variables; float for multiplicative; OR int for some additive thresholds like `tightness_days_required`). V1 enumerator already produces correct-typed sweep points per `_additive_sweep` (int) vs `_multiplicative_sweep` (rounded float). V2 inherits.

**Out-of-range guard**: V2 explicitly validates that the SUBSTITUTED value falls within the cfg dataclass field's documented range (e.g., `trend_template.min_passes` ∈ [0, 8] inclusive since only 8 TT criteria exist). Out-of-range sweep points are SKIPPED with a per-variable `out_of_range_skip_count` reported in the output. (See cumulative `Literal[...]` runtime-validation gotcha — discriminating test plants out-of-range substitution + asserts skip behavior.)

### §D.3 Criterion evaluation invocation flow per sweep-point

For each `(variable, sweep_point)` pair:

1. Substitute cfg → `substituted_cfg`.
2. For each `(candidate_id, ticker, data_asof_date)` in the universe:
   a. Build `CandidateContext` at `data_asof_date` per §F (OHLCV slice + reconstructed BatchContext).
   b. Invoke `evaluate_one(ctx)` with `substituted_cfg` → produces re-evaluated `Candidate` with new bucket.
   c. Accumulate counts into per-(variable, sweep_point) tallies: `aplus / watch / skip / excluded` + per-candidate drill-down `bucket_flipped: (old, new, criterion_results_summary)`.
3. Emit `SweepEntryV2` per (variable, sweep_point) with counts + delta-vs-current-value + per-variable drill-down attached at the parent level.

`SweepEntryV2` dataclass shape proposed (per Expansion #11 taxonomy propagation BINDING for 30th cumulative validation — V2 inherits the `{gate, threshold_additive, threshold_multiplicative}` kind enum from V1's `SweepVariable.kind`; NO new enum introduced; propagation surface is inherited):

```python
@dataclass(frozen=True)
class SweepEntryV2:
    variable_name: str
    kind: str  # inherits V1 enum: "gate" | "threshold_additive" | "threshold_multiplicative"
    sweep_point: float | int
    aplus_count: int
    watch_count: int
    skip_count: int
    excluded_count: int
    delta_aplus: int       # vs current_value entry's aplus_count
    delta_watch: int
    out_of_range_skip_count: int  # NEW vs V1 (per §D.2 guard)
    ohlcv_coverage_skip_count: int  # NEW vs V1 (per §F.3 coverage-failure handling)
    evaluation_error_skip_count: int  # NEW vs V1 (per-candidate try/except per cumulative lesson)
```

The 3 NEW skip-count columns vs V1 are intentional V2 additions per the increased scope of V2's recompute path. Per Expansion #11 taxonomy-propagation discipline:

- V1 `SweepEntry` has 9 fields (per `research/harness/aplus_sensitivity/sweep.py:33-49`); V2 `SweepEntryV2` adds 3 NEW fields → CSV header column list extends from 9 to 12.
- V2 `output.py:_CSV_HEADERS_V2` enumerates ALL 12 columns explicitly.
- V2 markdown matrix table extends from 9 columns (V1) to 12 columns (V2).
- Test fixtures plant non-zero values for EACH of the 3 NEW columns to verify the propagation invariant via discriminating test `test_sweep_entry_v2_serializer_round_trip_preserves_new_skip_columns`.

### §D.4 Per-candidate failure isolation

Per cumulative T2.SB5 gotcha "Bad-exemplar isolation in retrieval functions": V2's per-candidate `evaluate_one` invocation MUST be wrapped in try/except. A single candidate's exception (e.g., malformed OHLCV bar; missing 200-bar window after slice; cfg-substitution boundary case) MUST NOT poison the entire per-(variable, sweep_point) tally.

Failure isolation pattern:

```python
# pseudo-code; actual signature TBD in writing-plans
for cand in candidates_in_universe:
    try:
        ctx = build_candidate_context(cand.ticker, cand.data_asof_date, substituted_cfg, ...)
        result = evaluate_one(ctx)
        counts[result.bucket] += 1
    except OhlcvCoverageError:
        counts["ohlcv_coverage_skip"] += 1
    except OutOfRangeSubstitutionError:
        counts["out_of_range_skip"] += 1
    except Exception:
        counts["evaluation_error_skip"] += 1
        log.warning(...)
```

Discriminating test plants 3 candidates: 1 good + 1 with malformed OHLCV + 1 with cfg-out-of-range → asserts the good candidate's bucket is still tallied + the other 2 increment per-failure-mode skip counts.

---

## §E `bucket_for` recomputation end-to-end

### §E.1 Standard path (14 of 15 threshold variables + `trend_template.min_passes` gate)

For 14 of 15 threshold variables + the cfg-derived gate `trend_template.min_passes`, V2's `evaluate_one(ctx_with_substituted_cfg)` invocation re-runs ALL 8 trend_template + 9 vcp + 1 risk criterion functions against the OHLCV bars, then routes the resulting Results through `bucket_for(tt_results, vcp_results, risk_results, substituted_cfg)`. The result is the V2-recomputed bucket.

NO V2-side mirror of `bucket_for` is needed for the standard path. V2 invokes the production function verbatim.

### §E.2 Per-criterion threshold mapping (which criterion consumes which cfg-variable)

Verified via grep at spec-write time against `swing/evaluation/criteria/*.py` (Expansion #5 cross-section spec inventory grep BINDING per 25th cumulative validation):

| cfg variable | Consumed by | File:line |
|--------------|-------------|-----------|
| `trend_template.min_passes` | `bucket_for` gate (NOT a criterion) | `swing/evaluation/scoring.py:29` |
| `trend_template.rising_ma_period_days` | TT3 `200MA rising` | `swing/evaluation/criteria/trend_template.py:59-71` |
| `trend_template.high_52w_margin_pct` | TT7 `within 52w high` | `swing/evaluation/criteria/trend_template.py:111-122` |
| `trend_template.low_52w_min_pct` | TT6 `above 52w low` | `swing/evaluation/criteria/trend_template.py:96-108` |
| `vcp.prior_trend_min_pct` | `prior_trend.evaluate` | `swing/evaluation/criteria/prior_trend.py` (verified file exists; line refs in writing-plans) |
| `vcp.adr_min_pct` | `adr.evaluate` | `swing/evaluation/criteria/adr.py` |
| `vcp.pullback_max_pct` | `pullback.evaluate` | `swing/evaluation/criteria/pullback.py` |
| `vcp.proximity_max_pct` | `proximity.evaluate` | `swing/evaluation/criteria/proximity.py` |
| `vcp.tightness_days_required` | `tightness.evaluate` | `swing/evaluation/criteria/tightness.py` |
| `vcp.tightness_range_factor` | `tightness.evaluate` | `swing/evaluation/criteria/tightness.py` |
| `vcp.orderliness_max_bar_ratio` | `orderliness.evaluate` | `swing/evaluation/criteria/orderliness.py` |
| `vcp.orderliness_max_range_cv` | `orderliness.evaluate` | `swing/evaluation/criteria/orderliness.py` |
| `risk.max_risk_pct` | `risk_feasibility.evaluate` | `swing/evaluation/criteria/risk_feasibility.py` |
| `rs.horizon_weeks` | Affects `BatchContext.returns_12w_by_ticker` upstream (in §F batch reconstruction); NOT criterion-internal | `swing/evaluation/rs.py` + V2 `context_builder.py` |
| `rs.rs_rank_min_pass` | TT8 `RS rank` | `swing/evaluation/criteria/trend_template.py:124-145` |
| `rs.fallback_extreme_pct` | TT8 fallback path | `swing/evaluation/criteria/trend_template.py:146-155` |

**Special case `rs.horizon_weeks`**: this variable is CONSUMED at BatchContext construction time (12w return windowing), NOT at criterion-evaluation time. V2's `context_builder.build_batch_context(..., horizon_weeks=substituted_cfg.rs.horizon_weeks)` re-windows the returns dictionary. This is the ONE substitution that affects ALL candidates' batch context simultaneously (not just the candidate being evaluated). Documented in spec for writing-plans clarity.

### §E.3 Special case `vcp.watch_max_fails` (hardcoded in `bucket_for`)

`swing/evaluation/scoring.py:37` hardcodes `if vcp_fails <= 2:`. The value `2` is NOT cfg-derived; substituting `cfg.vcp.watch_max_fails` does NOTHING because no production code reads it.

V2 OPTIONS:
- **(a)** Promote `vcp.watch_max_fails` to cfg-derived in `swing/evaluation/scoring.py` as a 1-line production change. PROBLEM: violates §A.1 "Production `swing/` code is READ-ONLY through this dispatch arc." V2 dispatch declines this.
- **(b)** Mirror V1's `_bucket_for_substituted` pattern for this ONE variable: V2's sweep.py special-cases `variable_name == "vcp.watch_max_fails"` and threads the sweep_value into a V2-side `bucket_for_with_substituted_watch_max_fails(...)` mirror (NOT invoking production `bucket_for`). RECOMMEND (V2 ship target).
- **(c)** Drop `vcp.watch_max_fails` from V2 enumeration. PROBLEM: V1 covers it; dropping creates V2 regression. Rejected.

**V2 ship target = (b)**. V2 mirrors V1's existing `_bucket_for_substituted` watch_max_fails branch. The V2 mirror is at `research/harness/aplus_v2_ohlcv_evaluator/sweep.py` and is functionally IDENTICAL to V1's `_bucket_for_substituted` watch_max_fails branch but inputs are LIVE-recomputed Result tuples (from V2's `evaluate_one`) NOT persisted candidate_criteria rows (V1). Discriminating test asserts V2's watch_max_fails sweep produces same delta-counts as V1 against a fixture where the threshold variable substitutions are no-ops (sanity).

BANK as V2.5 (post-V2-ship, post-V2-study-output, operator-paired): "Promote `vcp.watch_max_fails` to cfg-derived in `bucket_for`" — a 1-line production-code change that closes the hardcode AND eliminates V2's special-case branch. Citation: OQ-11 disposition; dependency = operator approval + writing-plans cycle.

### §E.4 Baseline-recompute parity invariant (SCOPED per Codex C2)

V2's first sanity check: when invoked with `substituted_cfg == production_cfg` (i.e., NO substitution; sweep_point == current_value for every variable), V2's bucket distribution MUST match the persisted bucket distribution from `candidates.bucket` per the scoping below.

**Scoping clarification (Codex C2 RESOLVED)**: exact baseline parity is NOT achievable for the risk gate because `risk_feasibility.evaluate(ctx)` at `swing/evaluation/criteria/risk_feasibility.py:23` consumes `CandidateContext.current_equity` per `swing/evaluation/context.py:39`, and `current_equity` is NOT persisted on `candidates` / `evaluation_runs` per `swing/data/migrations/0001_phase1_initial.sql:9-56`. The production pipeline supplies dynamic sizing equity per `swing/pipeline/runner.py:1095`+`1121`; the historical value at the original eval_run is unrecoverable from schema.

V2 baseline parity is therefore SCOPED to bucket assignments that do NOT depend on the risk gate's outcome:

1. **Baseline parity tier 1 (EXACT)**: candidates whose persisted bucket is independent of the risk gate (e.g., `bucket='skip'` due to insufficient TT-passes; `bucket='aplus'` only when ALL gates pass including risk). For these, V2 re-evaluation MUST match exactly.
2. **Baseline parity tier 2 (CONDITIONAL)**: candidates whose persisted bucket DEPENDS on the risk gate outcome. V2 uses a documented `current_equity` surrogate per OQ-15 RECOMMEND (default: operator's CURRENT equity from latest `account_equity_snapshots` row at V2-invocation time; per-eval_run-historical-equity surrogate is V3+). V2 marks tier-2 candidates with `bucket_via_surrogate=True` in drill-down output; parity-mismatch in tier 2 is REPORTED but NOT a blocking failure.

**Acceptance criteria**:
- `test_baseline_recompute_tier1_matches_persisted_bucket_distribution_exactly` (discriminating test; blocking landing).
- `test_baseline_recompute_tier2_surfaces_surrogate_attribution_without_blocking` (discriminating test; landing).

Failure mode (anti-pattern): V2 tier-1 baseline diverges from persisted = some criterion has DRIFTED between when the persisted bucket was written (eval_run T) and when V2 re-evaluates against OHLCV at that asof_date OR the OHLCV archive itself has been mutated post-persisted-bucket-write (yfinance backfill / split-adjustment / dividend-adjustment per Codex M2). Discovered drift surfaces ANOTHER applied-research candidate (criterion-drift investigation OR archive-replay investigation) — banked as orthogonal to V2 OHLCV harness.

Per cumulative gotcha "Session-anchor read/write mismatch": V2 reads `evaluation_runs.data_asof_date` (writer-stamped backward-looking session) to slice OHLCV — same anchor the production writer used. Verified via end-to-end discriminating test plant 1 candidate at fixture asof_date + re-evaluate → bucket matches.

**OHLCV archive mutation caveat (Codex M2)**: V2's reproducibility is bounded by the OHLCV archive's stability between eval_run write-time and V2 invocation time. Splits / dividend-adjustment events that re-write historical bars (yfinance behavior; per cumulative gotcha "External-API empty-result must be treated as transient") will produce baseline-parity divergence even in tier 1. V2 study writeup MUST surface archive-mutation diagnostics: per-candidate per-asof_date archive-checksum vs current-archive-checksum if available; OR a documented assumption that V2 invocation soon after persisted-bucket-write minimizes mutation risk. See OQ-16 RECOMMEND for the read-only archive reader proposal.

### §E.5 OHLCV coverage failure handling (OQ-13 RECOMMEND; M3 RESOLVED)

When the OHLCV archive at `swing/data/ohlcv_archive.py` returns insufficient bars at the candidate's `data_asof_date` (most commonly: < 200 bars for trend_template's MA200 requirement at `swing/evaluation/criteria/trend_template.py:24-29`), V2 SKIPS the candidate for ALL variable-sweep points with `OhlcvCoverageError` and increments `ohlcv_coverage_skip_count`.

**Codex M3 RESOLVED**: the skip is per-CANDIDATE (NOT per-(variable, sweep_point)) because `evaluate_one(ctx)` at `swing/evaluation/evaluator.py:37-53` ALWAYS runs ALL criteria — there's no path through the production evaluator where some criteria run but others don't based on bar-count availability. The candidate either has 200+ bars (evaluable for all variables) or doesn't (skipped for all variables). The original spec's "some variables still evaluable" premise was wrong.

Consequence: `ohlcv_coverage_skip_count` is a SCALAR per V2 invocation (not a per-variable column with potentially different values across variables). Every per-variable row in the sensitivity matrix surfaces the SAME `ohlcv_coverage_skip_count` value, reflecting the same set of skipped candidates.

Baseline parity is maintained: N skipped candidates are skipped at all sweep points uniformly, so the delta-vs-current-value math nets out cleanly because the SAME candidates participate in both numerator and denominator at every sweep point.

Output reporting: V2's matrix surfaces `ohlcv_coverage_skip_count` (scalar; same value per row). The CSV column is retained per-row for shape simplicity. Study writeup's "Limitations" section enumerates skip percentage if material (e.g., `>5%` skip rate triggers a banner note).

**Out-of-range and evaluation-error skip counts retain per-variable shape** per §D.3 (these vary per variable because out-of-range substitution is variable-specific + evaluation errors can be cfg-substitution-specific). Only the coverage-skip column is invariant across variables.

---

## §F OHLCV archive reconstruction strategy

### §F.1 Strategy decision (OQ-1 RECOMMEND; M1 + M2 + OQ-12 + OQ-16 RESOLVED)

V2 uses **direct Shape A parquet read via a NEW read-only V2 wrapper** at `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py`. The wrapper bypasses `swing.data.ohlcv_archive.read_or_fetch_archive` entirely (per Codex M1 + M2 RESOLVED).

**Why bypass `read_or_fetch_archive`** (Codex M1 + M2 facts):
- `read_or_fetch_archive(ticker, end_date, cache_dir, archive_history_days)` per `swing/data/ohlcv_archive.py:172-178` has NO `prefer_source` parameter — the OQ-12 original proposal is not implementable as written.
- The Shape A resolver at `swing/data/ohlcv_archive.py:372-377+428-439` defaults to provider precedence with `schwab_api` winning (per `_SOURCE_PRECEDENCE_MARKET_DATA` at `swing/data/ohlcv_archive.py:52-58`).
- `read_or_fetch_archive` actively FETCHES from yfinance on cache-miss / stale-archive per `swing/data/ohlcv_archive.py:223-237+242-251`. V2's reproducibility story is incompatible with archive mutation between persisted-bucket-write and V2 invocation; a fetch could backfill bars that did not exist at the original eval_run.

**V2 read-only reader (`ohlcv_reader.py`) responsibilities**:
- Compose the per-(ticker, source) Shape A parquet path: `{cache_dir}/{ticker}.{source}.parquet` per the Shape A naming convention (verified against `swing/data/ohlcv_archive.py` Shape A path conventions at writing-plans phase).
- Read primary: the yfinance Shape A parquet (`{ticker}.yfinance.parquet`); NEVER touch the schwab_api Shape A parquet (L2 LOCK preserved per OQ-12 RECOMMEND).
- **Legacy archive fallback (Codex R2.M2 + R3.M1 RESOLVED)**: if `{ticker}.yfinance.parquet` does NOT exist, fall back to reading `{ticker}.parquet` (the legacy single-source archive). The production `_backward_compat_rename` at `swing/data/ohlcv_archive.py:584-657` (+ both-exist merge/freshness logic at `:648-649+663+714`) copies/merges legacy archives into yfinance Shape A AT FIRST PRODUCTION READ. V2 reader policy for the BOTH-EXIST case (Codex R3.M1 LOCK; surface as OQ-18 NEW): **Shape A wins unconditionally**. V2 does NOT merge legacy into Shape A; if the operator has both files for a ticker AND legacy carries fresher / longer history than Shape A, V2 reads Shape A and may produce baseline-parity drift in the affected tier-1 candidates. Caveat documented in V2 study writeup `Limitations` section. Operator remediation: invoke any production OHLCV-read path that goes through `read_or_fetch_archive` (e.g., a CLI subcommand or pipeline run) to force the `_backward_compat_rename` merge AND THEN re-run V2; or accept the drift caveat. Discriminating tests: (a) plant ONLY `{ticker}.parquet` legacy file + assert V2 reader returns correct bars (not raises `OhlcvCoverageError`); (b) plant BOTH `{ticker}.yfinance.parquet` (shorter history) AND `{ticker}.parquet` (longer history) + assert V2 reads Shape A's shorter history (NOT the legacy longer history); (c) document the both-exist policy in the reader's docstring + study writeup template. Rationale for "Shape A wins": deterministic + reproducible per-V2-invocation; simple test surface; the both-exist case is RARE in operator's archive (post-production-read, Shape A becomes the canonical source); the V3+ V2.5 candidate is "V2 reader optionally merges legacy via direct port of `_backward_compat_rename` logic" (operator-paired). See OQ-18.

**Both-exist diagnostic surface (Codex R4.M1 RESOLVED)**: V2 reader tracks `both_exist_shape_a_wins_count` (integer; incremented per ticker where both files exist + Shape A was read in preference). Reader also records `both_exist_ticker_list` (sorted list of affected tickers; capped at first 50 with `... +N more` suffix). Both surfaces emitted to:
- V2 invocation manifest (always, even if count is zero, for audit).
- V2 markdown output `Notes` section as a warning banner when count > 0: `"WARNING: <N> tickers have both Shape A and legacy archive files; V2 read Shape A unconditionally per OQ-18 policy. Affected tickers (first 50): <list>. Operator remediation: invoke any production OHLCV-read path before V2 to force the production merge logic at swing/data/ohlcv_archive.py:584-657, then re-run V2."`
- Per-ticker LOGging at WARNING level (so operator's tail can see the live count grow during V2 run).

Discriminating test: plant 5 tickers with both files (different bar counts) + plant 5 tickers with Shape A only + plant 5 tickers with legacy only + assert `both_exist_shape_a_wins_count == 5` + assert manifest contains affected ticker list + assert markdown Notes section emits the warning banner.
- **OHLCV column-case normalization (Codex R2.C1 RESOLVED)**: Shape A persists OHLCV columns as lowercase `open/high/low/close/volume` per `swing/data/ohlcv_archive.py:449+521-522`. Production criteria + evaluator expect capitalized `Open/High/Low/Close/Volume` per `swing/evaluation/criteria/trend_template.py:23` + `risk_feasibility.py:17-18` + `vcp.py:16-17` + `swing/evaluation/evaluator.py:55+59-60`. V2 reader normalizes lowercase → capitalized at the read boundary so downstream `evaluate_one(ctx)` sees the production-expected column names. Discriminating test: plant a Shape A parquet with lowercase columns + assert V2 reader returns DataFrame with capitalized columns + assert `evaluate_one(ctx)` does not raise `KeyError` against the normalized DataFrame.
- Return the full per-ticker frame indexed by date with capitalized OHLCV columns. Caller slices to `<= data_asof_date` per §F.2.
- NO fetch path. NO writes. NO archive mutation. If neither `{ticker}.yfinance.parquet` NOR legacy `{ticker}.parquet` exists OR if the slice has fewer than the required bars for `evaluate_one` (200 per §E.5), raise `OhlcvCoverageError` → caller skips per §E.5.
- Discriminating test: plant both `{ticker}.schwab_api.parquet` AND `{ticker}.yfinance.parquet` files for a synthetic ticker + assert V2 reads ONLY the yfinance bytes via byte-checksum compare; assert V2 does NOT invoke `yf.download` / yf.Ticker / any yfinance API path (mock yfinance module + assert zero calls).

Rationale for direct Shape A read:
- **Reproducibility (Codex M2)**: V2 reads the parquet bytes AS-IS at V2 invocation time. No fetch can mutate the archive between V2's universe scan + V2's per-candidate evaluation. Per-V2-invocation archive snapshot consistency.
- **L2 LOCK preservation (OQ-12)**: V2 reader is the ONLY consumer of the OHLCV archive path; it explicitly opens ONLY the `{ticker}.yfinance.parquet` file. ZERO new Schwab API calls. Defense-in-depth via test that asserts the schwab Shape A file is unread + yfinance module unloaded.
- **Coverage failure**: per §E.5 skip-and-report.
- **No double-cache**: V2 reads the operator's authoritative archive directly. No earnings_proximity-style research-cache layer.

REJECTED alternatives:
- **Fetch-on-demand via live yfinance**: 5681 candidates × per-candidate fetch is rate-limit-prohibitive AND blocks reproducibility (later runs hit different yfinance-version state).
- **Reuse `read_or_fetch_archive`**: per Codex M1 + M2 above, the function signature lacks the source-preference parameter AND the fetch path mutates the archive between invocations; both block V2.
- **Limit-to-recent only**: artificially shrinks the universe + doesn't actually need to be done; the archive covers what's needed for S3's last-63-eval_runs scope.
- **Independent research-cache (earnings_proximity-style)**: dupe-storage with no offsetting benefit since V2 is operator-paired (not arc-spanning). Acknowledged as PRECEDENT but rejected for V2-specific reasons.

### §F.2 OHLCV slicing semantics

For each candidate `(ticker, data_asof_date)`:

1. Read full per-ticker parquet via NEW V2 reader `research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader.read_yfinance_shape_a(ticker, cache_dir)` per §F.1 amended (Codex M1+M2 RESOLVED). Returns DataFrame indexed by date with capitalized OHLCV columns (per Codex R2.C1 normalization at the read boundary). The reader bypasses `swing.data.ohlcv_archive.read_or_fetch_archive` entirely; NO fetch; legacy `{ticker}.parquet` fallback per Codex R2.M2.
2. Slice to bars `<= data_asof_date` (inclusive of asof_date; OHLCV is the session that JUST closed at writer-stamp time per `data_asof_date` backward-looking semantics).
3. Verify `len(sliced) >= 200` (minimum for TT MA200 per `swing/evaluation/criteria/trend_template.py:24-29`). If insufficient, raise `OhlcvCoverageError` (caught at sweep.py per §D.4).
4. Pass sliced DataFrame to `CandidateContext(ohlcv=sliced, ...)`.

Per cumulative gotcha "Session-anchor inequality discipline depends on anchor directionality (backward-looking vs forward-looking)": `data_asof_date` is BACKWARD-looking (the session that just closed at eval_run time). Strict `>` inequality applies when stripping the in-progress bar (per the existing lesson) — but for V2 V2-time slicing the data is HISTORICAL ARCHIVE (no in-progress bar exists at the asof_date), so the strip is moot. V2 uses simple `<=` slicing per the precedent at `research/harness/earnings_proximity/replay.py:142-143`. Discriminating test plants archive at end of asof_date + verifies the asof_date bar IS included.

### §F.3 Candidate universe SQL skeleton (Expansion #4 refinement BINDING)

Per cumulative gotcha "Brief-vs-actual schema reality check + SQL skeleton column verification": every SQL skeleton's columns verified against actual migration files. Verified at spec-write time:

```sql
-- Read the last N eval_runs (mirror V1 sweep.py:60-62)
SELECT id, data_asof_date
  FROM evaluation_runs
  ORDER BY id DESC
  LIMIT :eval_runs_window;
```
Verified: `evaluation_runs.id` + `evaluation_runs.data_asof_date` exist at `swing/data/migrations/0001_phase1_initial.sql:9-12`.

```sql
-- Read all candidates in those eval_runs (V2's primary universe scan).
-- Joined with candidate_criteria to surface the persisted risk_feasibility
-- result per candidate (Codex R2.M3 RESOLVED — needed for tier-1 vs tier-2
-- parity classification per §E.4).
SELECT c.id, c.ticker, c.bucket, er.data_asof_date,
       cc_risk.result AS persisted_risk_result
  FROM candidates c
  JOIN evaluation_runs er ON er.id = c.evaluation_run_id
  LEFT JOIN candidate_criteria cc_risk
    ON cc_risk.candidate_id = c.id
   AND cc_risk.layer = 'risk'
   AND cc_risk.criterion_name = 'risk_feasibility'
  WHERE c.evaluation_run_id IN (:eval_run_ids)
  ORDER BY er.id DESC, c.ticker ASC;
```
Verified: `candidates.id` + `candidates.ticker` + `candidates.bucket` + `candidates.evaluation_run_id` exist at `swing/data/migrations/0001_phase1_initial.sql:25-28+26`. `candidate_criteria.candidate_id` + `.layer` + `.criterion_name` + `.result` exist at `0001_phase1_initial.sql:48-56`. `evaluation_runs.data_asof_date` already verified. LEFT JOIN handles candidates without a persisted risk_feasibility row (e.g., legacy fixtures from pre-Phase-1 — defaults to NULL → V2 treats as tier 2 conservatively).

Per Codex R2.M3 RESOLVED: tier-1 (NON-risk-gated) classification uses `persisted_risk_result == 'pass'` (the risk gate did NOT cause the persisted bucket disposition); tier-2 classification uses `persisted_risk_result != 'pass'` OR NULL (the risk gate's outcome was load-bearing for the persisted bucket; V2 re-evaluation needs the `current_equity` surrogate per OQ-15). Discriminating test: plant 2 candidates with bucket='skip' — one with persisted_risk_result='pass' (skip caused by TT-gate; tier 1) + one with persisted_risk_result='fail' (skip caused by risk; tier 2); assert classifier puts each in correct tier.

Per cumulative gotcha "SQL aggregation UNIT audit (Expansion #8 candidate)": V2's SQL does NOT use COUNT / GROUP BY / SUM — it's a pure row-fetcher. No JOIN-cardinality concerns. No DISTINCT needed (PRIMARY KEY on `candidates.id` guarantees per-row uniqueness). Verified.

**Universe size at V2 baseline (operator DB; per S3 output)**: 5681 candidates across 63 eval_runs = ~90 candidates per eval_run avg. V2 universe scan returns 5681 rows + per-row OHLCV reconstruction.

### §F.4 BatchContext reconstruction at historical asof_date

Per `swing/evaluation/context.py:14-19`, BatchContext requires:

- `returns_12w_by_ticker: dict[str, float]` — cross-sectional 12-week returns
- `universe_tickers: tuple[str, ...]`
- `universe_version: str`
- `universe_hash: str`
- `spy_return_12w: float`

V2 reconstructs at each `(eval_run_id, data_asof_date)` cohort:

1. **`universe_tickers` = the FULL RS universe** (Codex C1 RESOLVED — NOT the per-eval_run candidate set). The RS universe is the ranking-universe-of-record from `cfg.paths.rs_universe_path` per production `swing/cli.py:449` + earnings_proximity precedent at `research/harness/earnings_proximity/run.py:197-201`+`279`. **Why**: `compute_rs(...).rank` per `swing/evaluation/rs.py:71-85` computes per-ticker RS percentile via cross-sectional ranking against the universe — using only candidate tickers would produce WRONG percentiles + flip TT8 results + break baseline parity per §E.4 invariant.
   - NEW dependency: V2 reads the RS universe via `swing.evaluation.rs.load_universe(cfg.paths.rs_universe_path)` at invocation time. V2 fails-fast with `MissingRsUniversePathError` if the path is unset OR the file unreadable. **Codex R2.M4 + R3.M2 RESOLVED**: V2 layers THREE validations on top of `load_universe`:
     - **(a) Non-empty + minimum size** (Codex R2.M4): loaded universe must be non-empty AND have ≥ N_MIN tickers (proposed default: 100; configurable via `--min-universe-size N`). Fail-fast with `EmptyRsUniverseError` if not.
     - **(b) Ticker-shape validation** (Codex R3.M2): each ticker must match the symbol-shape regex `^[A-Z][A-Z0-9.\-]*$` (NYSE/NASDAQ canonical: starts with capital letter; followed by capital letters / digits / dots / hyphens). `load_universe` at `swing/evaluation/rs.py:22-42` accepts every post-header line as a ticker string without validating shape; a malformed CSV with `header=ticker` + 100 garbage rows would pass (a) silently. V2 counts shape-invalid rows; if > `N_INVALID_THRESHOLD` (default: 5% of total OR 10 rows whichever is greater) → fail-fast with `InvalidRsUniverseError` listing first 10 invalid rows; otherwise log warning + drop invalid rows (proceed with remainder).
     - **(c) Duplicate detection**: log warning + drop duplicates if any (Codex R3.M2; duplicates skew RS percentile computation).
   - **Post-cleanup universe-size re-check (Codex R4.M2 RESOLVED)**: AFTER dropping invalid rows + deduping, V2 RE-checks `len(valid_unique_tickers) >= min_universe_size`. Example: 105 rows, 9 invalid (under 5% allowed threshold), 1 duplicate → accepted = 95 unique tickers. If 95 < 100 (default min), V2 fails-fast with `PostCleanupUniverseTooSmallError` (or operator can pass `--min-universe-size 90` to accept the cleanup result). Otherwise the universe might silently fall below the operationally-meaningful minimum even though no individual validation step rejected it.
   - **Rejected-symbol enumeration in warning (Codex R4.m1 RESOLVED)**: when V2 logs/warns on shape-invalid rows, the warning message MUST list the EXACT rejected symbols (capped at first 20; with `... +N more` suffix). Enables operator to allowlist legitimate-but-rejected formats quickly (e.g., if a saved-screen exports `BRK/B` style with slash separator).
   - Discriminating tests: (i) plant empty universe file + assert `EmptyRsUniverseError`; (ii) plant 100-row universe with 50 garbage rows (>5%) + assert `InvalidRsUniverseError` (lists first 20 garbage symbols); (iii) plant 100-row universe with 3 garbage rows (<5%) + 2 duplicates + assert warning logged + accepted-tickers = 95 unique + accepted-count >= min_universe_size; (iv) plant 105-row universe with 9 garbage + 1 duplicate (accepted = 95 < min_universe_size=100) + assert `PostCleanupUniverseTooSmallError`.
   - NEW OQ-14 surfaces the historical-RS-universe-snapshot question (the universe membership at the historical eval_run may differ from the universe membership today; for V2 ship target, we accept current-universe-snapshot as the surrogate; per-eval_run-historical-universe-snapshot is V3+).
2. `universe_version` = `f"v2_harness_eval_run_{eval_run_id}_universe_{cfg.paths.rs_universe_path.name}"` (NOT the production universe-version; V2 is a research-branch invariant per §A.1).
3. `universe_hash` = `v2_universe_hash_` prefix + SHA-256 of the sorted `universe_tickers` tuple bytes (Codex R2.m1 RESOLVED — explicit prefix marks the V2 research-branch derivation; SHA-256 matches production's `swing.evaluation.rs.universe_version_hash` at `swing/evaluation/rs.py:45-49`; deterministic; reproducible). NOT comparable to persisted `evaluation_runs.rs_universe_hash` if such a column exists.
4. `returns_12w_by_ticker` = per-ticker 12-week return computed from the OHLCV archive slice across the FULL RS universe (NOT just candidates) — mirror earnings_proximity `_return_12w` at `research/harness/earnings_proximity/replay.py:146-158`. Per-ticker skip if <60 bars history available; per-ticker `OhlcvCoverageError` accumulates into per-universe-ticker-skip count (separate from per-candidate skip per §E.5).
5. `spy_return_12w` = SPY's 12-week return at the asof_date (separate OHLCV archive read via §F.1 V2 reader).

**The `rs.horizon_weeks` substitution** propagates here: when V2 substitutes `rs.horizon_weeks=14`, the BatchContext reconstruction MUST window returns at 70 trading days (14 × 5), NOT the default 60. V2's `context_builder.build_batch_context(..., horizon_weeks=substituted_cfg.rs.horizon_weeks)` accepts the parameter explicitly.

### §F.5 Per-eval_run batch reuse + per-eval_run universe-OHLCV caching (LOAD-BEARING per Codex M4)

**Codex M4 RESOLVED**: V2's runtime is dominated by full-universe OHLCV reads + per-eval_run returns-12w reconstruction, NOT by `evaluate_one` invocations. The original spec's "optional optimization" framing was wrong.

**Cost breakdown** (envelope-of-the-back; refined in writing-plans phase) — assumes per-TICKER cache (Codex R3.m1 RESOLVED: previous cost-table version cited per-eval_run parquet reads which conflicted with the locked per-ticker cache; corrected below):

| Cost component | Per V2 invocation | Notes |
|----------------|-------------------|-------|
| Parquet opens (per-TICKER cache; LOCKED per §F.5) | `N_universe + N_candidate_tickers_not_in_universe` (typically ≤ N_universe + 5681 worst case; usually much less due to overlap) | N_universe = full RS universe size (per production cfg.paths.rs_universe_path; typically 500-2000 tickers). At ~10ms per parquet open + full-history-load = 5-30 seconds per V2 invocation total. |
| In-memory slicing per (ticker, asof_date) | ~5681 candidate slices + ~N_universe × 63 batch-context returns_12w slices | Cheap per-slice (pandas DataFrame `loc[]` is ~10µs); total ~63 × N_universe ≈ 30k-130k operations × 10µs = sub-second. |
| `returns_12w_by_ticker` cross-sectional computation | 63 eval_runs × N_universe × 1 calc | Cached per (eval_run_id, horizon_weeks) tuple per §F.5; ~315 distinct BatchContext reconstructions. |
| `evaluate_one(ctx)` invocations | ~482k (5681 candidates × 17 vars × ~5 sweep_points) | Per-call cost: SMA50 + SMA150 + SMA200 over up-to-200 bars + 9 vcp criteria + 1 risk + RS rank lookup = ~5-20ms per envelope. Cumulative 40-160 minutes — the DOMINANT cost component (with caches in place; pre-cache parquet I/O would dominate). |
| Total runtime with both caches | ~15-60 minutes on a fast SSD | Within OQ-9's 60-minute target on a fast machine; tight on a slow machine. |

**Per-eval_run BatchContext + universe-OHLCV caching is LOAD-BEARING (NOT optional)**:

V2 caches the BatchContext per `(eval_run_id, substituted_cfg.rs.horizon_weeks)` tuple. Reduces BatchContext reconstructions from 482k to 63 eval_runs × ~5 distinct horizon_weeks values = ~315.

**V2 OHLCV cache key choice (Codex R2.M5 RESOLVED)** — V2 caches per-TICKER (full-history frame), NOT per-(ticker, asof_date) slice. Each ticker's parquet is OPENED ONCE per V2 invocation; the full-history frame is held in memory and sliced in-memory (cheap) per `(ticker, asof_date)` combo as needed. This makes the cache key `ticker` (NOT `(ticker, asof_date)`) and brings the parquet-open count down to at-most `N_universe + N_candidate_tickers_not_in_universe` (typically `N_universe` for ranking-universe-member candidates + the candidate-only tickers that aren't in the RS universe).

For S3's universe (5681 candidates + N_universe ranking universe; many candidate tickers ARE ranking-universe-members; let candidate_tickers \ universe_tickers = D; then parquet opens ≤ N_universe + D ≤ N_universe + 5681 worst-case if zero overlap).

With both caches: estimated V2 runtime ≈ 15-45 minutes on a fast SSD, within OQ-9's 60-minute target.

**Acceptance criteria**:
- `test_v2_per_eval_run_batch_context_cached_not_recomputed` (discriminating; counts BatchContext construction calls; must be ≤315).
- `test_v2_per_ticker_ohlcv_parquet_opened_once` (discriminating per Codex R2.M5; counts parquet `pd.read_parquet` calls; must be ≤ N_universe + N_candidate_tickers_not_in_universe).
- `test_v2_runtime_below_60_minutes_on_smoke_universe` (smoke; synthetic 100-candidate / 5-eval_run / 17-var universe; runtime cap 90 seconds).
- `test_v2_smoke_records_memory_footprint` (Codex R3.m3; smoke records `N_cached_tickers` + approximate memory bytes from `tracemalloc.get_traced_memory()` peak; logged to V2 invocation manifest so the operator can observe actual memory footprint on real hardware; non-blocking but instrumented).

If V2 still exceeds OQ-9 budget on operator hardware, V2.5 candidates banked: parquet bulk-read via pyarrow; per-eval_run universe-tickers OHLCV pre-load into a single memory frame indexed by (ticker, date); per-process parallelism via concurrent.futures (operator-paired since this is research code).

---

## §G Output format

### §G.1 Sensitivity matrix (top-level, parity-preserving) — OQ-4 hybrid (a) component

V2 emits a CSV mirroring V1's 9-column shape PLUS 3 NEW skip-count columns per §D.3:

```
variable_name, kind, sweep_point,
aplus_count, watch_count, skip_count, excluded_count,
delta_aplus, delta_watch,
out_of_range_skip_count, ohlcv_coverage_skip_count, evaluation_error_skip_count
```

V2 markdown matrix mirrors V1's table format (12 columns instead of 9 — see §D.3 taxonomy-propagation invariant). The markdown matrix's HEADLINE summary section (placed ABOVE the matrix) directly answers operator's motivating question per §B.1:

> ## Headline: variables binding at watch→A+ boundary (V2 OHLCV recompute)
>
> Top 5 by marginal A+ count per loosening unit (sorted descending; loosening = sweep direction that grows A+):
>
> 1. `<variable>` at sweep_point=<X> → A+ delta +<N> (<+P%>)
> 2. ...
> [zero entries if no variable produces non-zero delta_aplus in the 5-point grid]

The headline answers the operator's question in ONE table at the top. The full sensitivity matrix follows for completeness.

### §G.2 Per-variable drill-down (OQ-4 hybrid (b) component)

For EACH variable with `max(|delta_aplus|) > 0` across its sweep grid, V2 emits a drill-down section in the markdown:

```
## Drill-down: <variable_name>

| Sweep point | Direction | A+ delta | Candidates flipped (watch→A+) | Candidates flipped (A+→watch) | Candidates flipped (skip→watch) | ... |
|-------------|-----------|----------|---|---|---|---|
| <pt-2>      | loosen    | +<N>     | <ticker_1, ticker_2, ...>      | ...                            | ...                              | ... |
| <pt-1>      | loosen    | +<N>     | ...                            | ...                            | ...                              | ... |
| <current>   | -         | 0        | (anchor)                       |                                |                                  |     |
| <pt+1>      | tighten   | -<N>     | ...                            | ...                            | ...                              | ... |
| <pt+2>      | tighten   | -<N>     | ...                            | ...                            | ...                              | ... |
```

Plus a per-flipped-candidate provenance block:

```
### Candidates flipped (watch→A+) at <variable>=<sweep_point>:

- <ticker> (eval_run=<id>, data_asof_date=<date>): old criterion failure = '<criterion_name>' (value=<old_value>, rule='<old_rule>'); new evaluation = 'pass' under substituted threshold.
```

This drill-down enables the OPERATOR to inspect WHICH candidates flipped + WHY they flipped (per-criterion attribution). Critical for the downstream cfg-policy threshold-loosening proposal-drafting workflow per Path B disposition.

### §G.3 V1↔V2 comparison section (NEW; not in V1)

V2 markdown emits a "V1↔V2 parity" section reporting:

- Baseline A+ count (V1 persisted) vs Baseline A+ count (V2 recompute at current_value). MUST match exactly per §E.4 invariant; if mismatch, the markdown surfaces "CRITERION DRIFT DETECTED" alert + lists divergent candidates.
- Gate-variable resimulation: V1's `_bucket_for_substituted` gate output for `trend_template.min_passes` + `vcp.watch_max_fails` vs V2's `evaluate_one`-recomputed gate output. SHOULD match per parity invariant; surfaces deltas if any.

### §G.4 Per-variable scope-reduction reporting

When V2 skips candidates per §E.5 (OHLCV coverage) OR §D.2 (out-of-range substitution) OR §D.4 (evaluation error), the per-variable row in the matrix surfaces the skip counts as explicit columns (per §G.1). Additionally, the markdown's "Notes" section enumerates per-variable scope-reduction summary:

```
## Notes

- Total V2 universe: <N> candidates across <M> eval_runs.
- Per-variable coverage: <variable_1>: <N - skip_count> evaluable / <N> total (<P%> coverage).
- ...
```

### §G.5 ASCII-only output (cumulative gotcha BINDING)

Per cumulative gotcha "Windows PowerShell stdout defaults to cp1252; non-ASCII glyphs ... will raise `UnicodeEncodeError`": V2 output (CSV + markdown) MUST be cp1252-encodable. Test verifies via `text.encode("cp1252")` mirroring V1's pattern at `tests/research/test_aplus_sensitivity_output.py` + `tests/cli/test_diagnose_subcommands.py`.

Particular discipline:
- NO `→` arrow glyphs in the drill-down "flipped" descriptions; use ASCII `-> ` or `:` syntax.
- NO `§` section markers in CLI output strings (markdown body is allowed `§` since markdown doesn't go through stdout; only `click.echo()` paths matter).
- NO em-dash `—` in CSV cells or `print()` strings; ASCII `-` substitutes.

### §G.6 Output empty-state representation

Per cumulative T3.SB3 lesson "Audit envelope empty-state representation must be uniform across emit + persist paths": V2 output empty-state (e.g., a variable with no per-candidate flips for drill-down) uses `(none)` literal string in the drill-down section, NOT empty string OR `null`. Uniform across CSV + markdown emit paths.

---

## §H Test scope projection

### §H.1 Per-task test budget (writing-plans phase will decompose)

Estimated test count for V2 OHLCV harness brainstorming → executing-plans full landing:

| Module / area | Tests | Detail |
|---------------|-------|--------|
| `ohlcv_reader.py` (NEW per Codex R1+R2+R3+R4 amendments) | ~12 | Shape A primary read (`{ticker}.yfinance.parquet`); legacy fallback (`{ticker}.parquet`); both-exist policy (Shape A wins; per-ticker count tracked); column-case normalization (lowercase → capitalized); required-column check (Open/High/Low/Close/Volume present post-normalization); never opens `{ticker}.schwab_api.parquet` (file-open mock asserts); no yfinance / no schwabdev import (import-graph mock asserts); raises `OhlcvCoverageError` on missing/insufficient bars; both-exist diagnostic surface (`both_exist_shape_a_wins_count` manifest field; markdown warning banner; tracked per-ticker affected list) |
| `context_builder.py` | ~12 | OHLCV slicing at asof_date; BatchContext reconstruction; RS universe loading via `load_universe`; full-universe `returns_12w_by_ticker` reconstruction (Codex C1); per-ticker skip on <60 bars; rs.horizon_weeks parameter threading; v2_universe_hash SHA-256 prefix; tier-1 / tier-2 risk-gate classification via persisted_risk_result (Codex R2.M3); OHLCV-coverage error path; MissingRsUniversePathError + EmptyRsUniverseError + InvalidRsUniverseError + PostCleanupUniverseTooSmallError (Codex R2.M4 + R3.M2 + R4.M2); rejected-symbol enumeration in warnings (Codex R4.m1) |
| `cfg_substitution.py` | ~6 | substitute_cfg per-subsection (4) + unknown-subsection ValueError + type-preservation invariant |
| `sweep.py` | ~14 | per-(variable, sweep_point) orchestration; tier-1 baseline parity invariant (CRITICAL; blocking); tier-2 parity reporting (non-blocking); single-variable downstream propagation; vcp.watch_max_fails special case mirroring V1 _bucket_for_substituted; per-candidate failure isolation (3 modes: ohlcv-coverage, out-of-range, evaluation-error); ohlcv-coverage skip as scalar (Codex M3); out-of-range substitution skip; evaluation-error skip; multi-eval_run universe scan; current_equity surrogate per OQ-15; per-eval_run BatchContext cache (≤315 reconstructions; Codex M4 LOAD-BEARING); per-TICKER OHLCV cache (≤ N_universe + delta opens; Codex R2.M5) |
| `output.py` | ~10 | CSV header includes 3 new skip columns; markdown matrix renders 12 columns; headline section emits correctly; drill-down emits per-flipped-candidate provenance + bucket_via_surrogate flag (per OQ-15); ASCII-only output (cp1252 round-trip); V1↔V2 parity section emits CRITERION DRIFT alert on mismatch; per-variable scope-reduction notes; empty-state representation uniform; both-exist warning banner surface; manifest emission (`both_exist_shape_a_wins_count` + accepted ticker counts + tier-1/2 split + memory peak from tracemalloc) |
| `run.py` / CLI | ~8 | argparse boundaries (--eval-runs range; --variables-filter parsing; --min-universe-size; --max-runtime-seconds cap); ClickException wrapping ValueError per cumulative T-A.1.5b; output file path conventions; baseline smoke (operator's actual DB shape via fixture); CLI subcommand registration carve-out (git diff swing/ assertion); subprocess stdout smoke via PowerShell (cp1252 encoding gotcha test) |
| Integration / E2E | ~6 | end-to-end synthetic-universe run; V1↔V2 parity discriminating test; OHLCV coverage failure discriminating test; runtime budget smoke (synthetic 100-candidate / 5-eval_run / 17-var universe; runtime cap 90 seconds); memory footprint smoke (tracemalloc peak; Codex R3.m3); CRITERION DRIFT detection smoke (alter cfg between persistence + V2 invocation; assert alert fires) |
| **Total** | **~68** | Updated from R1's ~46 to account for new `ohlcv_reader.py` module + ~22 additional tests across other modules per Codex R1-R4 amendments. Substantially larger than T-T4.SB.1's ~30-40 because V2's substitution scope (15 threshold variables + universe reconstruction + tier-1/2 parity + both-exist diagnostic + universe validation) is larger than V1's gate-only scope. Within reasonable bounds for a 5-sub-bundle dispatch per §M.1. |

### §H.2 Discriminating-test patterns inherited from cumulative gotcha catalog

Each pattern below is a BINDING test for V2 per the cited cumulative gotcha:

- **Schema-CHECK + Python-constant + dataclass-validator paired discipline (cumulative)** — N/A V2 (no schema change); but the propagation principle applies to V2's `SweepEntryV2` kind enum (inherited from V1's V1-level taxonomy; same enum values).
- **F6 (write-through-cache transient empty) defense (cumulative)** — N/A V2 writes no cache rows; OHLCV archive write-through is owned by production code (READ-ONLY by V2).
- **`Literal[...]` type hints are NOT runtime-enforced (cumulative)** — DIRECTLY APPLIES to V2's `SweepEntryV2.kind`; same `__post_init__` validation pattern as V1 `SweepVariable.kind` per `research/harness/aplus_sensitivity/variables.py:39-44`.
- **Service-layer ValueErrors must be wrapped at CLI boundary (cumulative)** — DIRECTLY APPLIES to V2 CLI per §C.2.
- **`date.fromisoformat()` discipline (cumulative gotcha #12)** — DIRECTLY APPLIES; `evaluation_runs.data_asof_date` is TEXT (ISO format); V2's `context_builder` MUST convert via `date.fromisoformat(row[1])` at the SQL boundary. Discriminating test: plant a row with malformed ISO date + assert `MalformedAsofDateError` (typed) NOT `TypeError` deep in stack.
- **Bad-exemplar isolation in retrieval functions (cumulative T2.SB5)** — DIRECTLY APPLIES per §D.4. Discriminating test: 3-candidate fixture (1 good + 2 failure-mode) asserts only failure-mode candidates skip + good candidate tallied.
- **External-API empty-result transient defense (cumulative F6)** — N/A direct (V2 doesn't fetch from external API; uses archive). But indirectly relevant if archive read returns empty parquet: V2 treats as OhlcvCoverageError + skip (per §E.5), NOT silent ZERO-bar evaluation.
- **Synthetic-fixture-vs-production-emitter shape drift (cumulative, 4 instances)** — DIRECTLY APPLIES to V2 test fixtures: V2 fixture data (synthetic OHLCV bars + synthetic candidate rows) MUST shape-match what `swing.data.ohlcv_archive.read_or_fetch_archive` would actually return AND what `swing.data.repos.candidates.insert_candidates` would actually persist. Discriminating test: derive fixture from a real eval_run dump (write a fixture-generator that consumes operator's DB + dumps to JSON) per the cumulative defense-in-depth pattern.

### §H.3 Test count baseline + V2 bump projection

V2 brainstorming docs-only: ZERO test delta (baseline 5778 fast tests UNCHANGED through brainstorming phase).

V2 writing-plans + executing-plans projected: +68 fast tests (~5846 total post-V2-ship; updated from R1's +46 per Codex R4.M3 test-scope expansion).

NO slow-marked tests in V2 dispatch scope (V2 operates against OHLCV archive read-only; no live API calls).

### §H.4 Cross-bundle pin disposition (cumulative discipline)

V2 dispatch is NEW research-branch arc; NO existing cross-bundle pins exist. V2 shipping does not affect any existing pin's un-skip schedule.

Forward-binding: if V2 ship reveals criterion drift (per §E.4 baseline parity invariant fails), a NEW cross-bundle pin may be needed at the criterion-implementation point. Decision deferred to writing-plans phase post operator-triage.

---

## §I OQs surfaced for operator-paired triage

18 OQs surfaced — 8 from dispatch brief §1.1 + 5 NEW from initial substrate analysis + 4 NEW from Codex Round 1 review (OQ-14 C1 + OQ-15 C2 + OQ-16 M1/M2 + OQ-17 M6) + 1 NEW from Codex Round 3 review (OQ-18 R3.M1 both-exist legacy/Shape A policy). Each OQ has a RECOMMEND disposition; final disposition is operator-paired between brainstorming + writing-plans phases.

### OQ-1: OHLCV reconstruction scope

**Question**: Limit-to-recent vs fetch-on-demand vs piggyback?

**RECOMMEND** (amended per Codex M1+M2 RESOLVED): Direct Shape A parquet read via NEW read-only V2 wrapper `ohlcv_reader.py` per §F.1 amended decision. Bypasses `read_or_fetch_archive` entirely (which has no `prefer_source` parameter AND actively fetches/mutates the archive). NO fetch path; NEVER reads schwab_api Shape A; reproducible per-V2-invocation; legacy `{ticker}.parquet` fallback per Codex R2.M2. L2 LOCK preserved (OQ-12 + OQ-16).

### OQ-2: Per-criterion evaluator interface

**Question**: Mutate cfg dataclass vs explicit override-dict?

**RECOMMEND** (amended per Codex R2.m2): (a) mutate cfg via `dataclasses.replace` + invoke production `evaluate_one(ctx)` end-to-end per §D.1. High-fidelity; single-variable downstream propagation preserved (e.g., substituted `rs.rs_rank_min_pass` propagates through TT8 → tt_passes → bucket_for). Does NOT detect multi-variable interaction effects (that's V3+ per OQ-7). Special case `vcp.watch_max_fails` per §E.3 / OQ-11.

### OQ-3: Sweep range strategy per variable

**Question**: Inherit V1 5-point grid vs adaptive bisection vs full-range?

**RECOMMEND**: (a) inherit V1 5-point grid per V2.1 §IV.B parsimony. Adaptive bisection deferred V3+.

### OQ-4: Output format

**Question**: Same V1 shape vs per-candidate granular vs hybrid?

**RECOMMEND**: (c) hybrid — V1 9-col matrix at top (+3 new skip cols) + per-variable drill-down sections + headline section + V1↔V2 parity section per §G. Answers operator's binding-variable question in headline; enables downstream cfg-policy work via drill-down.

### OQ-5: Scope discipline

**Question**: All 15 inert variables in one dispatch vs phased?

**RECOMMEND**: All 15 in one dispatch. Shared infrastructure (OHLCV reconstruction + cfg substitution + evaluate_one invocation) is identical across the 15; phasing creates orphan V2 stub state + duplicate infrastructure.

### OQ-6: Validation universe

**Question**: Reuse S3's 5681 candidates / 63 eval_runs OR fresh fetch?

**RECOMMEND**: Reuse the operator's existing S3 universe (5681 / 63). Reproducibility — direct V1↔V2 comparison of "which variables matter" against the same universe. A fresh fetch conflates threshold-substitution effects with universe-drift effects.

### OQ-7: Cross-coupling

**Question**: V2 stays 1D vs introduces pair-wise variables?

**RECOMMEND** (amended per Codex R2.m2): 1D per V2.1 §IV.B parsimony. 2D + interaction terms deferred V3+. Note that single-variable downstream propagation IS preserved WITHIN a single 1D substitution per §D.1 (e.g., substituting `rs.rs_rank_min_pass` propagates through TT8 → `tt_passes` → `bucket_for`); but a 1D sweep does NOT detect interaction effects between MULTIPLE thresholds.

### OQ-8: Method-record promotion criteria

**Question**: What evidence threshold for research → shadow → production per V2.1 §IV.D?

**RECOMMEND**: 3-tier promotion ladder per §K.3:

- **research → shadow** (post V2 ship + first study output): (i) V2 OHLCV harness shipped + V2 baseline parity invariant green per §E.4; (ii) ≥1 study writeup published; (iii) AT LEAST ONE binding threshold variable identified (`max(|delta_aplus|) > 0` for ≥1 variable) OR all 15 declared NON-binding with operator-paired sign-off.
- **shadow → production** (post cfg-policy proposal evaluation): (i) ≥1 cfg-policy proposal evaluated against ≥2 disjoint validation universes (operator's 5681-candidate universe + a future operator-paired holdout); (ii) proposal's A+ delta is statistically distinguishable from baseline (default proposed: ≥5 A+ delta on a 5681-candidate universe — i.e., doubling A+ count); (iii) operator-paired ratification.
- **Anti-promotion guards**: regression on existing A+ candidates' bucket assignments; cross-coupling instability (binding threshold flips when OTHER variables are held at different values); production-cfg drift would invalidate the evidence (re-evaluation required if production cfg changed since the V2 study output).

### OQ-9 (NEW): Performance budget cap

**Question**: V2 invokes `evaluate_one` 5681 × 17 × 5 = ~482k times. At ~5ms each = ~40 min runtime (envelope; actual may be 2-3x). Cap V2 runtime at N seconds via `--max-runtime-seconds` flag?

**RECOMMEND**: Default UNSET (no cap) for operator's first run. Provide `--max-runtime-seconds N` CLI flag for partial-run capability. Acceptance target: <60 minutes on operator's hardware for the full 5681 / 63 / 17 / 5 universe. If V2 exceeds, V2.5 work targets §F.5 per-eval_run BatchContext reuse optimization.

### OQ-10 (NEW): V2 CLI surface name

**Question**: V2 CLI name — `aplus-sensitivity-v2` vs `aplus-ohlcv-evaluator` vs rename V1 to `aplus-sensitivity-gates` + V2 takes `aplus-sensitivity`?

**RECOMMEND**: `swing diagnose aplus-sensitivity-v2`. Less invasive than renaming V1; back-compat preserved; "v2" suffix is explicit about lineage. Operators familiar with V1's `swing diagnose aplus-sensitivity` find V2 via tab-complete or `swing diagnose --help` enumeration.

### OQ-11 (NEW): `vcp.watch_max_fails` hardcode handling

**Question**: Production `bucket_for` at `swing/evaluation/scoring.py:37` hardcodes `vcp_fails <= 2`. V2's `vcp.watch_max_fails` substitution — promote to cfg-derived in production (1-line change; violates §A.1 read-only invariant) OR mirror V1's special-case substitution OR drop from V2 enumeration?

**RECOMMEND**: (b) mirror V1's special-case per §E.3. V2 ship target. BANK as V2.5: "Promote `vcp.watch_max_fails` to cfg-derived in `bucket_for` (1-line production change)" — operator-paired triage post V2 ship, closes the hardcode for V3+.

### OQ-12 (NEW): Schwab API L2 LOCK preservation

**Question**: V2 OHLCV reconstruction may fall through Schwab API in the production ladder (via `swing/data/ohlcv_archive.py`'s `_SOURCE_PRECEDENCE_MARKET_DATA` shape — verified at lines 52-58: `schwab_api: 0, yfinance: 1`). V2 must explicitly enforce yfinance-only.

**RECOMMEND** (amended per Codex M1+M2+R2.M2+R2.C1 RESOLVED): V2 reads the yfinance Shape A parquet directly via the NEW `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py` wrapper per §F.1 amended. Reader opens `{ticker}.yfinance.parquet` (or legacy `{ticker}.parquet` fallback); normalizes lowercase OHLCV → capitalized; NEVER opens `{ticker}.schwab_api.parquet`. Discriminating test: plant both schwab_api Shape A and yfinance Shape A parquet files for a synthetic ticker + assert V2 reads ONLY the yfinance bytes (via byte-checksum compare) + assert V2 process never opens the schwab_api parquet file (via file-open mock). L2 LOCK preserved (ZERO new Schwab API calls through V2 dispatch).

### OQ-13 (NEW): OHLCV coverage failure attribution mode

**Question**: When archive returns <200 bars at candidate's asof_date → V2 attribution? (a) skip + report; (b) substitute persisted bucket (V1 fallback); (c) abort.

**RECOMMEND**: (a) skip + report per §E.5. Clean attribution (V2 cannot recompute → V2 has no opinion). Surfaces in `ohlcv_coverage_skip_count` (scalar per V2 invocation per Codex M3 RESOLVED; same value across all per-variable rows) + per-study scope-reduction notes per §G.4.

### OQ-14 (Codex C1 NEW): RS universe reconstruction strategy at historical asof_date

**Question**: V2's BatchContext reconstruction requires `universe_tickers` = full RS universe at the eval_run's `data_asof_date`. The RS universe membership at the historical eval_run may DIFFER from the universe membership today (RS universe is operator-curated + can drift between months). Three options:

- **(a) current-universe snapshot** — V2 reads `cfg.paths.rs_universe_path` AT V2 INVOCATION TIME + uses that universe for ALL historical eval_runs. Simpler; reproducible per-V2-invocation; may produce a slightly different RS percentile than the original eval_run if universe membership has drifted.
- **(b) per-eval_run-historical-universe snapshot** — V2 reads a per-eval_run-historical snapshot from a NEW persistence layer (e.g., `evaluation_runs.universe_hash` + a `rs_universe_snapshots` table). Requires schema change (V3+ per V1 method-record V2 dependency #2) + ongoing per-eval_run snapshot persistence. Reproducible.
- **(c) eval_run universe-hash gate** — V2 checks `evaluation_runs.rs_universe_hash` (if persisted) AND skip-with-WARNING if it differs from current universe hash. Bounded scope but requires per-eval_run universe-hash to be persisted (verify it exists; if not, this option degenerates to (a)).

**RECOMMEND**: (a) current-universe snapshot for V2 ship. Universe drift is bounded between eval_runs (operator typically curates monthly OR by exception); current-universe is a reasonable surrogate for the last-63-eval_runs scope of S3 (~3 trading months). Surface drift caveat in study writeup `Limitations` section. BANK as V3 candidate: persist per-eval_run universe snapshots at write-time (schema change V3+).

### OQ-15 (Codex C2 NEW): `current_equity` surrogate for risk gate recompute

**Question**: V2's `risk_feasibility.evaluate(ctx)` requires `CandidateContext.current_equity`. The historical value at the original eval_run is NOT persisted in `candidates` or `evaluation_runs` (schema verified per `swing/data/migrations/0001_phase1_initial.sql:9-56`). Three options:

- **(a) Operator's CURRENT equity** — V2 reads from latest `account_equity_snapshots` row at V2 invocation time. Simple. Drift-affected for eval_runs predating any equity-snapshot changes (e.g., recent deposits/withdrawals/PnL).
- **(b) Per-eval_run-historical equity** — V2 reads from `account_equity_snapshots` rows with snapshot_date ≤ eval_run's `data_asof_date`. Reproducible per the snapshot history; requires snapshot rows actually exist at the right dates.
- **(c) `cfg.account.risk_equity_floor` surrogate** — V2 uses the cfg-defined floor (max(7500, ...) per project Capital risk floor convention auto-memory). Simpler; bounded surrogate; ignores actual equity entirely.

**RECOMMEND**: (b) per-eval_run-historical equity from `account_equity_snapshots` IF snapshot rows are available at the eval_run dates; fall back to (a) current equity OTHERWISE; mark tier-2 candidates (per §E.4) with `bucket_via_surrogate=True` for operator transparency. Per-V2-study writeup `Limitations` section enumerates surrogate usage count.

### OQ-16 (Codex M1 + M2 NEW): OHLCV archive read strategy — fetch path vs read-only

**Question**: `swing.data.ohlcv_archive.read_or_fetch_archive` actively fetches from yfinance on cache-miss / stale archive (per `swing/data/ohlcv_archive.py:223-237+242-251`), which would mutate the archive between V2 invocations + break V2 reproducibility (per Codex M2). Three options:

- **(a) Direct Shape A parquet read via NEW V2 wrapper** — V2 reads `{cache_dir}/{ticker}.yfinance.parquet` directly; NO fetch; raise `OhlcvCoverageError` on missing/insufficient. Bypasses production `read_or_fetch_archive`. RECOMMEND per §F.1 amended decision.
- **(b) Reuse `read_or_fetch_archive` with archive-snapshot freeze** — V2 takes a `cp -r` snapshot of the archive directory before invocation + reads from the snapshot. Adds disk-snapshot maintenance burden; potential disk-space concern.
- **(c) Extend `read_or_fetch_archive` to accept `fetch_disabled=True` parameter** — production-code change; violates §A.1 read-only invariant beyond the OQ-17 CLI carve-out.

**RECOMMEND**: (a) direct Shape A parquet read via NEW V2 wrapper at `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py` per §F.1 amended decision. Simplest. No archive snapshot maintenance. No production-code change. Cleanly preserves L2 LOCK (NEVER reads `{ticker}.schwab_api.parquet`).

### OQ-17 (Codex M6 NEW): CLI subcommand registration as the read-only carve-out

**Question**: §A.1 originally claimed "Production `swing/` code is READ-ONLY through this dispatch arc." But V2 must register the new CLI subcommand `swing diagnose aplus-sensitivity-v2` in `swing/cli.py`. This is a contradiction or an explicit carve-out?

**RECOMMEND** (amended per Codex R2.M6): Explicit carve-out per §A.1 amended language. The CLI subcommand registration is a `@click.command` decorated function added to `swing/cli.py` mirroring the V1 `swing diagnose aplus-sensitivity` registration at the same precedent file (T-T4.SB.1 ship; V1 registration spans roughly `swing/cli.py:4748-4787`). Carve-out scope described by SURFACE: subcommand handler + diagnose group attachment + Click option definitions + ClickException wrapping + delegation to research-harness `run_harness`. Realistic V2 line count: 35-60 lines (NOT the original 5-10 unrealistic estimate). This is the SOLE production-`swing/` modification V2 dispatch makes. NO other writes; NO schema change; NO migration. Discriminating test: `git diff swing/ --stat` after V2 executing-plans ship shows ONLY `swing/cli.py` modified.

### OQ-18 (Codex R3.M1 NEW): Both-exist legacy/Shape A archive read policy

**Question**: When BOTH `{ticker}.yfinance.parquet` AND legacy `{ticker}.parquet` exist for the same ticker, which file does V2 read? Production has merge/freshness logic at `swing/data/ohlcv_archive.py:584+648-649+663+714`; V2's direct-read bypass cannot inherit that logic without porting it. Three options:

- **(a) Shape A wins unconditionally** — V2 reads `{ticker}.yfinance.parquet`; ignores legacy in both-exist case. Deterministic + reproducible per-V2-invocation. May produce baseline-parity drift if legacy carries fresher/longer history that Shape A lacks (RARE post-production-read scenario).
- **(b) Port production `_backward_compat_rename` merge/freshness logic to V2 reader** — adds ~50-100 lines to `ohlcv_reader.py`; matches production semantics; higher fidelity but more code surface.
- **(c) Pre-V2 hook**: V2 dispatches a "merge-only" production-side call before running (e.g., for each in-universe ticker, invoke `read_or_fetch_archive` with a "no-fetch" parameter ONLY for the merge side-effect). Requires production-code change beyond OQ-17 carve-out.

**RECOMMEND**: (a) Shape A wins unconditionally per §F.1 amended decision + per-ticker diagnostic surface (Codex R4.M1; `both_exist_shape_a_wins_count` + warning banner). Simplest. Documented caveat in V2 study writeup `Limitations` section. Operator remediation: invoke any production OHLCV-read path (e.g., a normal pipeline run) before V2 to force merge; OR accept the drift caveat. V2.5 candidate: port production merge logic to V2 reader (operator-paired post V2 ship).

---

## §J Forward-binding lessons inherited

### §J.1 Cumulative gotcha set (16 cumulative)

Per CLAUDE.md updates through `2a56158`+`f1044ee` (gotchas #9-#16) + Expansion #11 candidate banked at `9b2a4db` + Expansion #12 candidate banked at `acaf305`:

Per `docs/v2-ohlcv-criterion-evaluator-brainstorming-dispatch-brief.md` §3.2 (16 cumulative gotcha enumeration):

| # | Gotcha | V2 applicability |
|---|--------|------------------|
| 9 | SQL aggregation UNIT audit | N/A (V2 SQL is pure row fetch; no GROUP BY / COUNT / SUM). Verified at §F.3. |
| 10 | Existing-field reuse audit | DIRECTLY APPLIES per §D.3 (V2 `SweepEntryV2` adds 3 NEW skip-count fields; verified V1 `SweepEntry` has no equivalents at `research/harness/aplus_sensitivity/sweep.py:33-49`; no field duplication). |
| 11 | Template-rendering surface audit | N/A (V2 has no Jinja templates; CSV + markdown emission via Python `print` / `csv.writer`). |
| 12 | `date.fromisoformat()` cross-type-boundary | DIRECTLY APPLIES per §H.2 (V2 reads `evaluation_runs.data_asof_date` TEXT → date conversion). |
| 13 | Form-render anchor lifecycle | N/A (V2 has no web routes / forms). |
| 14 | Architecture-location 5-sub-discipline (Expansion #10) | DIRECTLY APPLIES per §C.1 (NEW module placement decision documented; per-criterion evaluator location + cfg-substitution location + sweep orchestration location justified). |
| 15 | Taxonomy propagation (Expansion #11) | DIRECTLY APPLIES per §D.3 (V2 `SweepEntryV2.kind` inherits V1 enum; 3 NEW field propagation across dataclass + CSV header + markdown matrix + fixtures verified). |
| 16 | Sibling-route audit (Expansion #12) | N/A (V2 has no route handlers; single-CLI-entry-point). |

### §J.2 Pre-Codex 7-expansion + 5 NEW candidate refinements verification

Per brainstorming-phase pre-Codex review discipline (BINDING per dispatch brief §3.1; 31st cumulative C.C lesson #6 validation expected):

| # | Expansion | V2 brainstorming-phase application |
|---|-----------|-----------------------------------|
| 1 | Hardcoded-duplicate audit | `vcp.watch_max_fails = 2` hardcoded at `swing/evaluation/scoring.py:37` — V2 mirrors V1 special-case per OQ-11. NO other hardcoded duplicates of the 15 threshold variables found via `grep -n` against `swing/evaluation/criteria/*.py`. |
| 2 | Brief-vs-spec + brief-vs-actual schema verification | Dispatch brief substrate verified end-to-end vs spec; schema column references verified at §A.2. NO drift. |
| 3 | Schema-CHECK vs semantic-contract gap | N/A V2 (no schema change); semantic-contract for V2's `SweepEntryV2.kind` enum mirrors V1's runtime `__post_init__` validation. |
| 4 | Specific-scenario gotcha trace + SQL skeleton column verification | Walked: `date.fromisoformat()` boundary at `evaluation_runs.data_asof_date` per §F.2 + §H.2 → discriminating test pattern enumerated. SQL skeletons at §F.3 verified column-by-column against `swing/data/migrations/0001_phase1_initial.sql`. |
| 5 | Cross-section spec inventory grep | §E.2 cfg-variable → criterion mapping table grepped against `swing/evaluation/criteria/*.py` at spec-write time. |
| 6 | Content-completeness audit | Each spec checklist item from dispatch brief §4 mapped to a section in this spec (§A=A; §B=B; §C=C; §D=D; §E=E; §F=F; §G=G; §H=H; §I=I; §J=J; §K=K; §L=L; §M=M). NO `(n/a)` / `(TBD)` placeholders. NO V1-STUB silent ship. |
| 7 | Cross-row semantic SCOPE audit + scope-vs-unit boundary | N/A (V2 has no operator-input POST handler; pure CLI invocation). |
| 8 (cand) | Per-aggregation-function UNIT audit on SQL skeletons | V2's SQL has NO aggregation functions per §F.3. N/A this dispatch. |
| 9 (cand) | Form-render anchor lifecycle 4-dimension audit | N/A (no forms). |
| 10 (cand) | Architecture-location audit + 5 sub-disciplines | DIRECTLY APPLIED at §C.1 — module placement + dependency-surface verification + cache-key uniformity LOCK (N/A this dispatch) + SQL LIKE wildcard-escape (N/A this dispatch) + orphan-label preservation (mapped to V2's OHLCV-coverage skip handling per §C.1 sub-discipline (e)). |
| 11 (cand) | Taxonomy propagation audit | DIRECTLY APPLIED at §D.3 — V2 inherits V1's `{gate, threshold_additive, threshold_multiplicative}` enum verbatim; 3 NEW skip-count fields propagated through dataclass + CSV header + markdown matrix + test fixtures per the V2 propagation invariant. |
| 12 (cand) | Sibling-route audit when introducing single-anchor-binding discipline | N/A (no route handlers; no single-anchor invariant). |

V2 brainstorming-phase pre-Codex review = ALL 7 EXPANSIONS + 5 NEW CANDIDATE REFINEMENTS verified CLEAN at spec-write time. Awaiting Codex MCP chain for 31st cumulative C.C lesson #6 validation result capture.

### §J.3 T4.SB executing-plans forward-binding lessons (5 banked at `2a56158`)

Per dispatch brief §J reference. V2 inherits the lesson family:

- T4.SB.1 lesson — V2 enumerates ALL 15 threshold variables in one dispatch per OQ-5 (not phased).
- T4.SB.2 lesson — V2 surface dependencies verified at §C.1 architecture-location audit.
- T4.SB.3 lesson — V2 has no JIT cache; N/A.
- T4.SB.4 lesson — V2 emits ASCII-only output per §G.5.
- T4.SB.5 lesson — V2 inherits the V1 `SweepVariable.kind` enum without introducing new enum taxonomy.

---

## §K Method-record extension to `aplus-criteria-calibration.md`

The existing 72-line method-record at `research/method-records/aplus-criteria-calibration.md` extends with:

### §K.1 Updated `version` + `last_updated`

```yaml
---
key: aplus-criteria-calibration
name: A+ criteria parameter sensitivity calibration
layer: ranking
status: research
baseline_or_predecessor: internal (swing.evaluation.scoring.bucket_for current cfg)
version: 0.2.0  # bumped from 0.1.0 — V2 OHLCV harness shipped
last_updated: <V2 ship date>
---
```

### §K.2 NEW section after V2 dependencies — "V2 OHLCV harness shipped (status='research')"

Documents:
- V2 OHLCV criterion-evaluator harness module location (`research/harness/aplus_v2_ohlcv_evaluator/`)
- V2 CLI surface (`swing diagnose aplus-sensitivity-v2`)
- V2 vs V1 substitution semantic differences (per §A.4)
- V2's coverage of all 15 threshold variables + 2 gate variables (per OQ-5)
- V2-shipped V1-LIMITATION lift status (V2 closes the V1 LIMITATION per §B.1)

### §K.3 NEW section — "Promotion criteria (research → shadow → production)"

Per OQ-8 RECOMMEND + V2.1 §IV.D + §VII.C lifecycle posture:

- **research → shadow**:
  1. V2 OHLCV harness shipped + baseline parity invariant green per §E.4 of design spec.
  2. ≥1 V2 study writeup published.
  3. AT LEAST ONE binding threshold variable identified OR all 15 declared non-binding with operator-paired sign-off.
- **shadow → production**:
  1. ≥1 cfg-policy proposal evaluated against ≥2 disjoint validation universes.
  2. Proposal's A+ delta statistically distinguishable from baseline (default threshold proposed: ≥5 A+ delta on a 5681-candidate universe — doubling A+ count).
  3. Operator-paired ratification.
- **Anti-promotion guards**: regression on existing A+ candidates; cross-coupling instability; production-cfg drift.

### §K.4 Updated Validation notes section

Append:

- **V2-recompute baseline parity invariant**: V2 invoked with no substitution (sweep_point == current_value for every variable) MUST produce the same bucket distribution as V1's persisted-bucket pass per §E.4. Discriminating test: `tests/research/test_aplus_v2_ohlcv_sweep.py::test_baseline_recompute_matches_persisted_bucket_distribution_exactly`.
- **V1↔V2 gate-variable parity**: V2's gate substitution for `trend_template.min_passes` MUST produce the same delta-counts as V1's `_bucket_for_substituted` mirror path. Discriminating test: `tests/research/test_aplus_v2_ohlcv_sweep.py::test_v2_gate_substitution_matches_v1_bucket_for_substituted_output`.
- **Per-candidate failure isolation**: V2 candidates failing OHLCV coverage / out-of-range substitution / arbitrary evaluation error MUST NOT poison other candidates' tallies. Discriminating test: 3-candidate fixture per §D.4.

### §K.5 Notes section append

- V2 ships with `vcp.watch_max_fails` special-cased per §E.3 to mirror V1's `_bucket_for_substituted` semantics (production `swing/evaluation/scoring.py:37` hardcoded value `2` not cfg-derived).
- V2 BANK: Promote `vcp.watch_max_fails` to cfg-derived in `bucket_for` as V2.5 production-code change candidate (operator-paired ratification post V2 ship).
- V2 BANK: `cfg.trend_template.allowed_miss_names` tuple-set sweep + `cfg.rs.benchmark_ticker` string-identifier sweep STAY V3+ (consistent with V1 method-record §"Notes" line 70 enumeration).
- V2 NOT-scoped: schema changes (`candidate_criteria` structured threshold columns) STAY V3+ per V1 method-record V2 dependencies #2.
- V2 NOT-scoped: pair-wise cross-coupling STAYS V3+ per V1 method-record V2 dependencies #3.

---

## §L Cross-references + V2.1 governance citations

### §L.1 V2.1 governance citations

- **V2.1 §V branch posture**: V2 OHLCV harness lives under `research/` (V2.1 governing strategy at [`reference/Future Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md`](../../../reference/Future%20Work/2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md)). Production `swing/` stable through V2 dispatch.
- **V2.1 §IV.B minimum viable method-record fields**: V2 method-record extension per §K honors the minimum viable field list (key + name + layer + status + version + last_updated + Definition + Inputs + Parameters + Outputs + Operator explainability + Validation notes + Changelog). NEW V2-shipped sections + Promotion criteria sections added per §K.2 + §K.3.
- **V2.1 §IV.D + §VII.C lifecycle posture**: V2 ships at `status='research'`; promotion ladder per OQ-8 + §K.3.
- **V2.1 §IV.B parsimony**: V2 stays 1D per OQ-7; V2 inherits V1 5-point sweep grid per OQ-3 (no full-range sweep); V2 has no cross-coupling explicit modeling.
- **V2.1 §VII.F source-of-truth correction protocol**: applies only if V2 outputs surface a methodology-reference drift. NOT triggered by V2 ship itself.
- **V2.1 §X tranche progression**: V2 is the first method-record under `aplus-criteria-calibration` lineage per OQ-CL.3 LOCK; subsequent applied-research arcs follow the established pattern.

### §L.2 Repository cross-references

- Dispatch brief: [`docs/v2-ohlcv-criterion-evaluator-brainstorming-dispatch-brief.md`](../../v2-ohlcv-criterion-evaluator-brainstorming-dispatch-brief.md)
- Triage agenda (Path B LOCKED): [`docs/phase13-closer-next-phase-triage.md`](../../phase13-closer-next-phase-triage.md)
- S3 sensitivity-harness output: `exports/diagnostics/aplus-sensitivity-20260523T065514Z.md` + `.csv` (operator's actual S3 run)
- Method-record (PRIMARY substrate): [`research/method-records/aplus-criteria-calibration.md`](../../../research/method-records/aplus-criteria-calibration.md)
- V1 harness: [`research/harness/aplus_sensitivity/`](../../../research/harness/aplus_sensitivity/) (variables.py + sweep.py + output.py + run.py)
- V1 study writeup: [`research/studies/aplus-criterion-sensitivity-2026-05-22.md`](../../../research/studies/aplus-criterion-sensitivity-2026-05-22.md)
- Research-branch precedent: [`research/harness/earnings_proximity/`](../../../research/harness/earnings_proximity/) + [`research/studies/earnings-proximity-exclusion.md`](../../../research/studies/earnings-proximity-exclusion.md) + [`research/method-records/earnings-proximity-exclusion.md`](../../../research/method-records/earnings-proximity-exclusion.md)
- Production `bucket_for`: `swing/evaluation/scoring.py`
- Production `evaluate_one`: `swing/evaluation/evaluator.py`
- Production criteria: `swing/evaluation/criteria/*.py` (8 trend_template criteria + 9 vcp criteria + 1 risk criterion)
- Production OHLCV archive: `swing/data/ohlcv_archive.py`
- Production candidate_criteria repo: `swing/data/repos/candidates.py:78` (write path)
- Schema migrations: `swing/data/migrations/0001_phase1_initial.sql` (candidates + candidate_criteria + evaluation_runs) + `swing/data/migrations/*.sql` (subsequent)
- CLAUDE.md at repo root (16 cumulative gotchas; #14 + #15 + #12 most relevant to V2 design)
- T4.SB return reports (cumulative discipline lineage):
  - `docs/phase13-t4-sb-brainstorm-return-report.md`
  - `docs/phase13-t4-sb-writing-plans-return-report.md`
  - `docs/phase13-t4-sb-executing-plans-return-report.md`

---

## §M Dispatch sequence

### §M.1 Sub-bundle decomposition recommendation for executing-plans phase

V2 OHLCV criterion-evaluator harness is the FIRST research-branch arc post-Phase-13-FULLY-CLOSED. Sub-bundle decomposition recommendation (RECOMMEND; binding for writing-plans phase):

| Sub-bundle | Task | Deliverable | Estimated commits |
|------------|------|-------------|-------------------|
| **T-V2.1** | `context_builder.py` + `cfg_substitution.py` + tests | OHLCV slicing + BatchContext reconstruction + cfg substitution helpers | ~8-12 commits |
| **T-V2.2** | `sweep.py` + tests | Per-(variable, sweep_point) orchestrator + baseline parity + failure isolation | ~12-18 commits (largest sub-bundle) |
| **T-V2.3** | `output.py` + tests | CSV + markdown sensitivity matrix + headline + per-variable drill-down + V1↔V2 parity section | ~8-12 commits |
| **T-V2.4** | `run.py` + CLI subcommand registration in `swing/cli.py` + tests | CLI entry + argparse + ClickException wrapping + smoke E2E | ~6-10 commits |
| **T-V2.5** | Method-record extension + first study writeup + operator smoke run + closer | Extend `aplus-criteria-calibration.md` per §K; first study writeup at `research/studies/<date>-v2-ohlcv-criterion-evaluator.md`; operator runs V2 against operator DB + captures output; closer commit | ~6-10 commits |

**Total estimated commits**: ~40-62 across executing-plans phase. Comparable to T4.SB executing-plans scope (28+ commits per T4.SB.6 closer ship).

### §M.2 Concurrent dispatch potential

Sub-bundles T-V2.1, T-V2.2, T-V2.3 have sequential dependencies (T-V2.2 depends on T-V2.1; T-V2.3 depends on T-V2.2). Sub-bundle T-V2.4 partially depends on T-V2.3 (CLI emit paths). T-V2.5 depends on all prior + operator gate.

**RECOMMEND**: Sequential single-implementer dispatch for executing-plans phase. NO concurrent dispatch (single-implementer-driven via `copowers:subagent-driven-development` per project workflow precedent). Cross-implementer state isolation NOT a feature this arc needs.

### §M.3 Open questions deferred to writing-plans phase

- Actual function signatures + class shapes (proposed in §C.1 + §D.3 but not BINDING; writing-plans refines)
- Exact OQ-9 runtime cap default (`--max-runtime-seconds N=?`); writing-plans evaluates against operator's hardware baseline
- Per-task test-budget refinement (writing-plans decomposes the §H.1 ~46-test estimate into per-task budgets)
- Exact OQ-13 OhlcvCoverageError typed exception name + module location
- Per-sub-bundle Codex MCP round-budget expectation (informed by complexity per sub-bundle; writing-plans estimates)

### §M.4 Post executing-plans handback

V2 OHLCV harness shipping completes the FIRST applied-research arc under `aplus-criteria-calibration` lineage. Forward-binding for the NEXT applied-research arc:

- IF V2 output identifies binding threshold variables: NEXT arc drafts cfg-policy method-record + threshold-loosening evaluation against retained validation universes.
- IF V2 output declares all 15 non-binding: NEXT arc pivots to investigate market-conditions (cause 2 per §B.3) OR other-gates-not-enumerated (cause 3 per §B.3).
- THEN: Phase 14 commissioning per OQ-CL.2 disposition revisit.

---

## §N Self-review (BINDING per superpowers:brainstorming spec self-review gate)

### §N.1 Placeholder scan

- ZERO `TBD` placeholders. (Verified via grep at spec-write time; ALL `<date>` placeholders are intentional for downstream writing-plans phase + V2 ship date stamping.)
- ZERO `TODO` markers.
- ZERO incomplete sections.
- ZERO vague requirements.

### §N.2 Internal consistency

Checked sections for contradiction:
- §A.1 + §C.1: NEW module `research/harness/aplus_v2_ohlcv_evaluator/` referenced consistently.
- §A.4 + §C.2: V1 CLI `swing diagnose aplus-sensitivity` stays + V2 CLI `swing diagnose aplus-sensitivity-v2` is NEW. Consistent.
- §D.1 + §E.1 + §E.3: cfg-substitution + production `evaluate_one` invocation for 16 of 17 variables; `vcp.watch_max_fails` special-case for the 1 hardcoded variable. Consistent.
- §H.1 test count (~46) matches §H.3 baseline-bump projection (+46). Consistent.
- §I OQs (8 brief + 5 substrate-NEW + 4 Codex-R1-NEW + 1 Codex-R3-NEW = 18) match dispatch brief §1.1 (8 brief + 5+ new) bound; Codex R1 added 4 (OQ-14 C1 + OQ-15 C2 + OQ-16 M1/M2 + OQ-17 M6); Codex R3 added 1 more (OQ-18 R3.M1 both-exist policy). Consistent.
- §K version bump (0.1.0 → 0.2.0) matches §K.1 + V2 ship status `research`. Consistent.

### §N.3 Scope check

V2 OHLCV criterion-evaluator harness is the FIRST applied-research arc — appropriately scoped for ONE writing-plans → executing-plans cycle. Sub-bundle decomposition at §M.1 (5 sub-bundles; ~40-62 commits) is comparable to T4.SB executing-plans precedent. No over-scoping.

### §N.4 Ambiguity check

Per requirement-ambiguity check, all interpretation-ambiguous statements made explicit:

- "binding at the watch→A+ promotion boundary" (per §B.1) defined operationally as `max(|delta_aplus|) > 0` per OQ-8 disposition + per-variable hypothesis ranking at §B.4.
- "material A+ delta" (per OQ-8 + §B.5 null hypothesis) defined as ≥5 A+ delta on a 5681-candidate universe (configurable per operator-paired evidence summary).
- "VCP-fails (`na` counts as fail)" semantic preserved verbatim per cumulative V1 LOCK at `swing/evaluation/scoring.py:34`.
- "OHLCV coverage failure" defined at §E.5 as `<200 bars at candidate's data_asof_date`.

ZERO interpretation-ambiguous requirements remaining.

---

*End of V2 OHLCV criterion-evaluator harness brainstorming design spec. First Applied Research arc post-Phase-13-FULLY-CLOSED. Path B LOCKED 2026-05-23 PM. Banked V2 dependency #1 from existing `aplus-criteria-calibration` method-record is this deliverable's lifted target.*
