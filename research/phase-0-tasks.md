# Phase 0 task list — Research branch

Per V2.1 §X tranche 1. Time-budget anchor: 4–8 hours/week total project time, 70/30 production/research. Realistic allocation: 1–2 hours/week on research during Phase 0.

Tasks are sized for completion in one evening each (2–4 hours). No task larger than 4 hours; split if it grows.

## Done

- [x] Adopt V2.1 as governing strategy (Tranche A, 2026-04-23).
- [x] Create research-branch scaffolding: directory, README, method-record template (Tranche B-research, 2026-04-23).
- [x] First method record: earnings-proximity exclusion (Tranche B-research, 2026-04-23).
- [x] First study design: earnings-proximity parameter sweep (Tranche B-research, 2026-04-23).
- [x] Evaluate ≥2 free earnings-calendar sources for date-precision accuracy (Tranche B-research 2a, 2026-04-24). See `notes/earnings-calendar-sources.md`. Decision: yfinance `get_earnings_dates()`; 5/5 primary-source spot-check matches.
- [x] Decide historical-candidate data source (Tranche B-research 2a, 2026-04-24). See `notes/historical-candidate-source-decision.md`. Decision: Option B (synthetic replay); repo has 2 A+ signals vs. ≥120 threshold; ~77% of replay logic reusable from `swing/evaluation`, `swing/recommendations`, `swing/trades`.

## Next

- [ ] **Operator: run pattern cohort detector evaluator harness against `tightness_1.005_flips_67` cohort** — `python -m swing.cli diagnose pattern-cohort-detect --cohort-csv exports/research/cohorts/tightness_1.005_flips_67.csv --db "$USERPROFILE/swing-data/swing.db" --output-dir exports/research/ --window-mode per-window --template-match on`. Capture output triple `{results.csv, summary.md, manifest.json}` + commit. Populate `Results` section at `research/studies/2026-05-24-pattern-cohort-detection.md` + cross-tabulate with V2 OHLCV backtest verdict at merge `e0a9edd` (17 patterns / 5 triggered / -0.18R). **Pattern cohort harness SHIPPED 2026-05-24** (SECOND applied-research method-record COMPLETED; status `research` v0.1.0 at `research/method-records/pattern-cohort-detection.md`).

- [ ] **Operator: run V2 OHLCV harness against swing-data/swing.db** — `swing diagnose aplus-sensitivity-v2 --db "$USERPROFILE/swing-data/swing.db" --eval-runs 63 --output-dir exports/diagnostics/` (acceptance target: <60 min per OQ-9). Capture output files + commit to `exports/diagnostics/`. Populate the findings table at `research/studies/2026-05-23-v2-ohlcv-criterion-evaluator.md`. **V2 OHLCV harness SHIPPED at `f467ff5`** (2026-05-23; first method-record COMPLETED per OQ-CL.3 LOCK; method-record at `research/method-records/aplus-criteria-calibration.md` bumped to 0.2.0).

- [ ] **Review V2 findings + pick binding variables** — after operator DB run, review the sensitivity matrix. If any of the 15 threshold dials produce non-zero `delta_aplus` / `delta_watch`, those are binding variables. Rank by marginal A+ per loosening unit. Propose cfg-policy candidates for shadow promotion per `research/method-records/aplus-criteria-calibration.md` promotion ladder §"shadow -> production" criteria. If all 15 are non-binding, the conclusion is no-near-threshold candidates; see V2 study §"Conclusion" for interpretation guidance.

- [ ] **Build the study harness** — minimum viable Python script (can live under `research/` as a notebook or plain `.py`; does not go under `swing/`). Reads historical candidates, applies each `blackout_trading_days` variant, emits expectancy/gap-rate/gap-loss/signal-volume metrics. (3–4 hours.) *Note: earnings-proximity exclusion study deferred while V2 OHLCV arc was prioritized; resumable per Path B sequencing.*

- [ ] **Run the study** — execute harness with variants ∈ {0, 3, 5, 7, 10}. Capture raw output. (1 hour.)

- [ ] **Write evidence summary** — `research/studies/earnings-proximity-exclusion-results.md`. Includes decision (reject/shadow/promote) and rationale. Triggers copowers adversarial review per Tranche-B-research session 2. (2–3 hours.)

- [ ] **Evaluate which A+-like indicators from source-of-truth references warrant method-records + studies** (promoted from "Later (deferred)" 2026-05-22 PM at Phase 13 T4.SB executing-plans T-T4.SB.1). Context: V1 sensitivity harness shipped under T4.SB answered the 2 gate dials; V2 OHLCV criterion-evaluator harness now answers the 15 threshold dials (SHIPPED 2026-05-23). Next-action sequence post-V2-findings-review: pick 1-3 indicators to advance → author method-record stub(s) per `method-records/_template.md` → design study per `studies/earnings-proximity-exclusion.md` precedent. **V2.5 candidates banked** (per spec §M.4 + brainstorming return report §4): promote `vcp.watch_max_fails` to cfg-derived; `old_criterion_failure` per-criterion attribution; parquet bulk-read via pyarrow; concurrent.futures parallelism; `allowed_miss_names` sweep (V3+); `benchmark_ticker` sweep (V3+); 2D cross-coupling (V3+). **Posture per V2.1 §IX**: minimum viable governance -- let V2 outputs inform the next applied-research arc + Phase 14 commissioning consideration per Path B sequencing.

## Later (deferred)

- [ ] Second method record authored (TBD — orchestrator will choose based on study outcomes and operator-branch priorities).
- [ ] Parity test harness — single pytest fixture + helper. Deferred until the first promotion package needs it; minimum viable is fixture-identity on a synthetic input.
- [ ] Cross-study shared utility code (if any pattern emerges across multiple studies). Deferred per V2.1 §V.B until a second study actually surfaces a shared pattern.

## Off the list (V2.1 §VIII deferred)

Explicitly NOT Phase 0 work:

- Full signal-registry platform features.
- Generated code from registry schema.
- Pre-commit enforcement of registry transitions.
- Generalized experiment framework.
- Broad evidence-tier bureaucracy.
- Broad vendor-equivalence frameworks.
- Generalized panel-data architecture.

Revisit these only when a concrete active study demands them and no cheaper alternative exists.
