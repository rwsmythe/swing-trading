# V2-Selection-Mechanic Investigation -- Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the V2-selection-mechanic investigation implementer. No prior conversation context.

**Mission:** ANALYTICAL / EXPLORATORY investigation (NOT a backtest) of the cumulative cross-cohort finding that V2-binding-variable cohort selection produces W-pattern-thin substrates (R2-A ~13% density; R2-D ~3% density vs D2 EXPANDED ~12% bias-free baseline). For each of the 5 V2 OHLCV binding variables identified by V2 sensitivity (per `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md`), measure (a) substrate W-pattern density vs bias-free S&P 500 baseline; (b) per-variable substrate regime fingerprint (trend / volatility / proximity-from-high / sector); (c) cross-variable compatibility verdict with Ruleset E. The investigation produces a first-class research study writeup, NOT per-ruleset PARTIAL POSITIVE / NEGATIVE verdicts.

**Workflow:** `copowers:executing-plans` skill (wraps `superpowers:test-driven-development` + Codex MCP adversarial review). Codex MCP invocation per pre-dispatch operator-paired decision (see Sec 11; recommendation YES; **42nd cumulative C.C lesson #6 validation slot RESERVED**).

**Branch:** `applied-research-v2-selection-mechanic-investigation` -- branches from main HEAD `77d2162` (Turn H orchestrator handoff brief commit; reflects R2-D SHIPPED at `7330628` + housekeeping at `aa5e693` + handoff commit `77d2162`).

**Worktree:** `git worktree add .worktrees/applied-research-v2-selection-mechanic-investigation applied-research-v2-selection-mechanic-investigation`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Expected duration:** ~6-10h operator-paced implementer + ~2-5h Codex chain (full scope per operator decision: all 4 substantive research questions + all 5 V2 binding variables + bias-free baseline + NEW study writeup). Scope is larger than R2-A / R2-D because the investigation covers 5 variable cohorts simultaneously plus regime characterization + density delta analysis + study-writeup synthesis. The R2-A / R2-D extractor templates carry forward (2 of 5 cohorts are REUSE-VERBATIM via the existing sibling modules; 3 of 5 cohorts are NEW extractions).

---

## Sec 0 Read first (in this order)

1. **THIS BRIEF end-to-end.** Substantive methodology + scope decisions live here.

2. **`docs/orchestrator-handoff-2026-05-26-r2d-shipped-v2-mechanic-investigation-pending.md`** -- Turn H handoff brief. Sec 3.1 enumerates the 5 candidate research questions (operator scoped to #1+#2+#3+#5 V1; #4 sp=2.0 artifact DEFERRED V2). Sec 3.2 brief authoring discipline including NEW gotcha #34 (brief-prescription cross-table verification). Sec 3.3 the operator-paired scope LOCK that locked this brief's design.

3. **`docs/r2a-tightness-days-required-cohort-backtest-findings-20260526.md`** -- R2-A findings doc. Cross-cohort comparison table + per-ticker concentration + cohort-validity discipline. **R2-A's NEGATIVE verdict on N=65 V2-binding-variable cohort is the load-bearing prior for the compatibility question (#3).**

4. **`docs/r2d-adr-min-pct-cohort-backtest-findings-20260526.md`** -- R2-D findings doc. Substrate-depth comparison (Sec 2.1) + cross-cohort interpretation (Sec 2.2) showing ~3% R2-D density vs ~13% R2-A vs ~12% D2 EXPANDED. **R2-D's INSUFFICIENT SAMPLE / substrate-thinness finding is the load-bearing surprise that motivates the investigation.**

5. **`docs/pattern-cohort-w-bottom-ruleset-comparison-findings-2026-05-25.md`** -- D2 findings doc. Especially Amendment 5 (EXPANDED N=71 PARTIAL POSITIVE methodology + bootstrap CI) + Amendment 6 (R2-A cross-cohort consistency check bounding D2 E PARTIAL POSITIVE generalization scope). **D2 EXPANDED N=71 is the bias-free baseline this investigation re-uses.**

6. **`research/harness/r2a_tightness_days_required/`** -- R2-A cohort-extraction module set (3 modules: `cohort_csv.py` + `regenerate_cohort.py` + `__init__.py`). **REUSE VERBATIM** for the tightness_days_required substrate in this investigation. Asserted via byte-stability tests.

7. **`research/harness/r2d_adr_min_pct/`** -- R2-D cohort-extraction module set (3 modules; same shape as R2-A). **REUSE VERBATIM** for the adr_min_pct substrate. Asserted via byte-stability tests.

8. **`research/harness/pattern_cohort_evaluator/`** -- Phase 13 pattern detection harness (used by R2-A + R2-D for W primary verdict generation). **REUSE VERBATIM** for raw W primary verdict enumeration per V2 substrate. Asserted via byte-stability tests.

9. **`tests/fixtures/research/r2a_tightness_days_required/cohort.json`** + **`tests/fixtures/research/r2d_adr_min_pct/cohort.json`** -- canonical PrimaryVerdict fixtures (REUSE VERBATIM for R2-A and R2-D substrate W primaries within the investigation; byte-stability assertions inherited).

10. **`exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.{csv,md}`** -- V2 OHLCV sensitivity smoke artifact (full-63-eval-run reproduction; SAME source artifact for all 5 V2 variable cohort extractions). Canonical SHA-256 already locked at R2-A + R2-D `CANONICAL_SOURCE_SHA256` constants; this investigation re-uses the same SHA.

11. **`exports/research/cohorts/r2a_tightness_days_required_sp1.csv`** (7 unique ticker-asof rows) + **`exports/research/cohorts/r2d_adr_min_pct_sp2_0.csv`** (4 unique ticker-asof rows) -- existing V2-variable cohort CSVs. REUSE VERBATIM (no regeneration; investigation references these by SHA).

12. **`reference/methodology/`** -- methodology reference materials (informational; no V2-mechanic-specific carve-out).

13. **CLAUDE.md** gotchas #1-#34 -- cumulative discipline. **ESPECIALLY relevant for this investigation:**
    - **#34** brief-prescription cross-table verification (NEW; this investigation is the FIRST canonical application post-banking; orchestrator-side brief verified ALL 5 (variable, binding sweep_point, max_delta_aplus) tuples against the V2 sensitivity SUMMARY TABLE at lines 13-22 of the source artifact; see Sec 1.2 for the LOCK table)
    - **#33** cohort-validity-vs-verdict-criteria discipline (investigation is ANALYTICAL not verdict-producing; no PARTIAL POSITIVE / NEGATIVE thresholds; substrate-density + regime findings are descriptive; #33's "no cohort substitution" rule applies to the W-density measurement methodology where the canonical filter MUST be held fixed per gotcha #33 third canonical application precedent)
    - **#28 + #29** OHLCV cache discipline (exemplar OHLCV pre-fetch; verify pre-flight)
    - **#30** recency/filter/dedup semantic-ordering (inherit D2 + R2-A discipline)
    - **#31** narrative artifact path/fact lag (post-fix sweep mandatory)
    - **#32** ASCII discipline scope clarity

---

## Sec 1 Investigation methodology

### Sec 1.1 Research questions in scope (operator-locked V1 per Turn H scope decision 2026-05-26)

The 5 candidate questions per handoff brief Sec 3.1 were operator-triaged. The following 4 are IN SCOPE for V1:

1. **(#1) Substrate-thinness mechanism.** For each V2 binding variable, measure W-pattern density on the V2-selected substrate vs the bias-free S&P 500 baseline. Hypothesis test: V2-selection produces substrates SIGNIFICANTLY THINNER in W-pattern density than the unbiased reference.

2. **(#2) Per-variable regime characterization.** For each V2 binding variable, characterize the chart-regime of the selected substrate via objective metrics (trend; volatility; proximity-from-high; sector mix). Hypothesis test: tightness criteria select tickers in flat/declining trends (low W incidence by structural deficit of V-bottoms); adr_min_pct loosening selects tickers with intrinsically low volatility (W amplitude small + harder to detect); proximity_max_pct widening selects tickers far from highs (recovery candidates); orderliness widening selects steady trends (uneventful price action).

3. **(#3) Fundamental compatibility verdict.** Synthesize across (#1) + (#2) + R2-A's NEGATIVE on V2 tightness_days_required substrate + R2-D's INSUFFICIENT SAMPLE on V2 adr_min_pct substrate. Produce a methodological verdict: is V2 cohort selection FUNDAMENTALLY incompatible with E ruleset deployment? Categorical verdict labels (COMPATIBLE / PARTIALLY-COMPATIBLE / INCOMPATIBLE) keyed to evidence; NO per-ruleset criterion thresholds applied (per gotcha #33 analytical-not-verdict-producing discipline).

4. **(#5) Baseline cross-comparison.** For each V2 binding variable, compute density-delta vs D2 EXPANDED bias-free baseline. Surface a 5-row delta table as the methodological scaffold for question (#1).

**OUT OF SCOPE for V1 (operator-deferred to V2):** question (#4) sp=2.0 artifact (was R2-D's substrate-thinness an artifact of sp=2.0? could be re-run at sp=1; per R2-D Codex R1.M#1 disclosure sp=1 emits 15 flips identical to R2-A's tightness_days_required cohort so probably non-informative; banked V2 candidate).

### Sec 1.2 V2-binding-variable (variable, binding sweep_point, max_delta_aplus) LOCK per gotcha #34 BINDING

**Source artifact:** `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md` (SAME source as R2-A + R2-D; canonical SHA inherited from `r2a_tightness_days_required.cohort_csv.CANONICAL_SOURCE_SHA256`).

**Per gotcha #34 BINDING (this investigation is the FIRST canonical application post-banking):** the SUMMARY TABLE at lines 13-22 of the source artifact is the authoritative source for `(variable, max_delta_aplus)` tuples. The per-variable drill-down section header (Sensitivity Matrix lines 70+) is the authoritative source for the binding `sweep_point` (= the sweep_point where the drill-down section's `delta_aplus` matches the SUMMARY TABLE's max_delta_aplus). The orchestrator-side brief verified ALL 5 tuples below against BOTH SUMMARY TABLE and per-variable drill-down section header.

| # | variable_name | max_delta_aplus (SUMMARY TABLE) | binding sweep_point (drill-down) | Cohort source for investigation |
|---|---|---|---|---|
| 1 | vcp.tightness_range_factor | 75 | 1.005 | NEW extraction (D1's `tightness_1.005_flips_67.csv` is hand-curated +67 subset; investigation MUST extract the FULL watch->aplus flip set programmatically NOT reuse D1's hand-curated CSV; see Sec 2.1) |
| 2 | vcp.tightness_days_required | 16 | 1 | REUSE-VERBATIM `research/harness/r2a_tightness_days_required/cohort_csv.py` + `exports/research/cohorts/r2a_tightness_days_required_sp1.csv` (15 raw flips; 7 unique tickers) |
| 3 | vcp.adr_min_pct | 11 | 2.0 | REUSE-VERBATIM `research/harness/r2d_adr_min_pct/cohort_csv.py` + `exports/research/cohorts/r2d_adr_min_pct_sp2_0.csv` (11 raw flips; 4 unique tickers) |
| 4 | vcp.proximity_max_pct | 5 | 7.5 | NEW extraction (no existing module / CSV; see Sec 2.2) |
| 5 | vcp.orderliness_max_bar_ratio | 1 | 3.75 | NEW extraction (no existing module / CSV; sp=3.75 is the FIRST crossing of +1 delta_aplus per drill-down rows 144-145; sp=4.5 also yields +1 but is the second crossing -- LOCK at sp=3.75 per "first binding signal" convention; see Sec 2.3) |

**LOCK semantics:** The implementer MUST add a module-level constant `BINDING_SIGNALS_TABLE` to the investigation module set with these 5 tuples + a discriminating test that re-derives the tuples from the V2 sensitivity SUMMARY TABLE at runtime (NOT just from a hardcoded list). The discriminating test exercises gotcha #34 first canonical application + locks the brief-vs-artifact cross-table verification.

### Sec 1.3 Canonical evaluation filter (held constant across all 5 variable substrates + the baseline)

Per gotcha #33 BINDING + D2 + R2-A + R2-D precedent: the canonical evaluation filter is `composite>=0.5 + recency<=365d`. The filter is applied to W primary verdicts emitted by `pattern_cohort_evaluator` against each substrate. ALTERNATIVE filters (composite>=0.7 + recency<=120d; composite>=0.5 + no recency; etc.) MAY be documented in the findings doc as sub-cohort exploration BUT must NOT be used to substitute the canonical density measurement or the compatibility verdict. The investigation's analytical surfaces are KEYED on the canonical filter.

### Sec 1.4 Bias-free baseline cohort (REUSE D2 EXPANDED N=71)

Per operator decision (Turn H Q3 = YES baseline): the bias-free reference is D2 EXPANDED Amendment 5 cohort (N=71 W primary verdicts; 88 unique S&P 500 tickers; composite>=0.5 + recency<=365d filter). The N=71 fixture already exists in the codebase via D2's harness output at `exports/research/cohorts/w_bottom_ruleset_comparison_sp500_apr_may_2026.csv` (per the existing exports/research/cohorts/ listing; implementer verifies path + SHA at slice 1).

For the W-density numerator computation: the investigation needs to know how many UNIQUE S&P 500 tickers were SCANNED to produce the N=71 cohort (i.e., the universe size; ~500 tickers). This is the bias-free denominator. The W primary-verdict raw count BEFORE canonical filter (per D2's pattern_cohort_evaluator smoke artifact) is the bias-free RAW density. The implementer must verify both numbers from existing D2 smoke artifacts at slice 1 + LOCK them via discriminating tests.

### Sec 1.5 Substrate characterization metrics (per V2-variable cohort)

Per-ticker metrics (computed at each cohort's representative asof_date; defined per substrate):
- **90-day price return.** Pct change between `asof_date - 90 BD` and `asof_date` close prices.
- **ATR%** (Average True Range as percentage of close). Mean ATR over the trailing 20 BD divided by close at asof_date.
- **52-week-high proximity (pct below).** `(52w_high - close) / 52w_high * 100`.
- **Sector.** From operator's Finviz sector field on the most-recent finviz fetch row covering the ticker; OR from the candidates table's sector column. If neither has data, mark UNKNOWN. Required: implementer documents the sector resolution path in the study writeup.

Per-cohort aggregate metrics:
- **Median + IQR** (interquartile range) of each per-ticker metric across the cohort.
- **Sector mix** (count of tickers per sector).
- **Cohort size** (unique ticker count + unique (ticker, asof) count).

These are STANDARD metrics; no bespoke / hand-tuned criteria. The investigation does NOT compute regime classifications (e.g., "Stage 2") at runtime; instead, it surfaces the OBJECTIVE metrics that an operator could later cross-reference to known frameworks. Per gotcha #32 ASCII discipline: all metric labels are ASCII-only.

### Sec 1.6 W-density measurement (per V2-variable substrate)

For each of the 5 V2-variable cohorts + the bias-free baseline:

| Metric | Definition |
|---|---|
| Substrate ticker count (T) | Unique tickers in cohort |
| Raw W primary verdict count (R) | Total double_bottom_w `verdict.is_primary==True` rows emitted by `pattern_cohort_evaluator` against the substrate (no composite/recency filter) |
| Canonical-filtered W count (F) | Subset of R passing composite>=0.5 + recency<=365d + 5-BD adjacency merge |
| Raw density (D_raw) | R / T (avg raw W primaries per ticker) |
| Filtered density (D_filt) | F / T (avg canonical-filtered W primaries per ticker) |
| Density delta vs baseline (delta_filt) | D_filt(V2-cohort) - D_filt(bias-free baseline) |

Density-delta interpretation:
- delta_filt < 0 means V2 cohort produces FEWER canonical-filtered W primaries per ticker than baseline (= thin substrate)
- delta_filt ~= 0 means cohort matches baseline density (= V2 selection does not bias W incidence)
- delta_filt > 0 means cohort produces MORE W primaries per ticker than baseline (= V2 selection enriches for W-pattern-emitting tickers)

The investigation surfaces these numbers + interprets, but does NOT apply a "thin / thick" categorical threshold via hard-coded delta cutoff. The compatibility verdict in Sec 3.4 is descriptive (cite the deltas + interpretation).

### Sec 1.7 Compatibility verdict synthesis (analytical, NOT verdict-producing per gotcha #33)

Given W-density deltas + regime fingerprints + R2-A NEGATIVE on V2 tightness_days_required cohort + R2-D INSUFFICIENT SAMPLE on V2 adr_min_pct cohort, the investigation produces a NARRATIVE compatibility synthesis (NOT a categorical PARTIAL POSITIVE / NEGATIVE verdict per gotcha #33 analytical-not-verdict-producing discipline).

Synthesis structure (operator-paired LOCK):
- **Per-variable signal table** (5 rows; one per V2 variable): cohort size + density delta + regime fingerprint + R2-A/R2-D backtest carryover (where applicable) + interpretation.
- **Cross-variable consistency claim:** if ALL 5 V2 substrates show negative density delta with consistent regime fingerprint, the cross-cohort consistency supports a STRONG-FORM INCOMPATIBILITY claim. If 2-4 of 5 show negative deltas, MIXED. If 0-1 show negative deltas, WEAK / NO-EVIDENCE.
- **Methodological caveats:** (a) the investigation is ANALYTICAL not backtest; per-ruleset P&L outcomes are NOT computed (R2-A + R2-D already provide partial backtest evidence; further per-cohort backtests are V2 candidates); (b) bias-free baseline is D2 EXPANDED's S&P 500 subset (not the full S&P 500 universe scan); (c) operator's pre-flight archive refresh state may bias forward-walk-OHLCV-derived regime metrics by ~0.5-3% per gotcha #26; (d) the canonical filter (composite>=0.5 + recency<=365d) is held fixed; alternative filters are documented but not used for the headline.

### Sec 1.8 What the investigation EXPLICITLY does NOT do

- **No per-ruleset P&L computation.** The 6-ruleset comparison harness (D2's `w_bottom_ruleset_comparison/`) is OUT OF SCOPE for this investigation. R2-A + R2-D already covered Rulesets A-F for their respective V2 cohorts; further per-cohort backtests are V2 candidates (R2-E proximity_max_pct +5 + R2-F orderliness_max_bar_ratio +1 banked at handoff Sec 4).

- **No alternative-cohort substitution.** Per gotcha #33: even if the bias-free baseline's W-density seems high, the investigation does NOT substitute "composite>=0.5 + recency<=120d" or similar to make the V2 substrates "look better". The canonical filter is held FIXED across all 5 V2 cohorts + the baseline.

- **No tightness_range_factor +75 D1-CSV reuse.** The D1 hand-curated +67 subset CSV is NOT a valid substrate for the investigation's purposes (it represents a hand-curated filtered subset, not the raw V2 sensitivity output). The implementer MUST extract the FULL watch->aplus flip set at sp=1.005 programmatically.

- **No regime-detector inference at runtime.** No "Stage 2 / Stage 4 classifier" or similar derivation. The metric set is OBJECTIVE per Sec 1.5; operator can map metrics to known frameworks post-hoc.

- **No new pattern_cohort_evaluator behavior changes.** Reuse Phase 13 detector implementation verbatim. L2 LOCK + byte-stability tests inherited.

- **No new Schwab API calls.** L2 LOCK preserved + REINFORCED via 3 NEW source-grep tests parametrized over the v2_selection_mechanic module set (mirrors R2-A + R2-D precedent).

---

## Sec 2 Cohort enumeration

### Sec 2.1 NEW extraction: vcp.tightness_range_factor @ sp=1.005

Source: drill-down rows 136-140 of the source artifact (`exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md`). The drill-down section `### vcp.tightness_range_factor` enumerates the per-flip records at sp=1.005 (lines TBD; implementer locates via grep). Expected: ~75-80 watch->aplus flip records (max_delta_aplus = 75 per SUMMARY TABLE; the actual flip count may differ slightly per drill-down structure -- some flips may be excluded->aplus or skip->aplus rather than watch->aplus). Implementer enumerates at slice 1 + verifies count contract via fixture identity tests.

**NEW module set at `research/harness/v2_tightness_range_factor/`** (sibling-module strategy continues per R2-A + R2-D LOCK; DO NOT refactor into shared base; common-parser refactor remains banked V2 candidate). 3 modules:
- `__init__.py`
- `cohort_csv.py` (port R2-D's template; swap variable_name + sweep_point + expected flip count + expected tickers + canonical source SHA; FLOAT-valued sweep_point at 1.005 mirrors R2-D's FLOAT handling)
- `regenerate_cohort.py` (port R2-D's entrypoint; preserve --allow-non-canonical-paths flag)

**Output:** `exports/research/cohorts/v2_tightness_range_factor_sp1_005.csv` (1 row per unique (ticker, asof_date); cohort_label `v2_vcp_tightness_range_factor_sp1_005`).

### Sec 2.2 NEW extraction: vcp.proximity_max_pct @ sp=7.5

Source: drill-down rows 126-130 of source artifact + drill-down section `### vcp.proximity_max_pct`. Filter: sweep_point=7.5 AND old_bucket=watch AND new_bucket=aplus. Expected: ~5 raw watch->aplus flip records (max_delta_aplus = 5 per SUMMARY TABLE).

**NEW module set at `research/harness/v2_proximity_max_pct/`** (sibling-module strategy; 3 modules same shape).

**Output:** `exports/research/cohorts/v2_proximity_max_pct_sp7_5.csv`.

### Sec 2.3 NEW extraction: vcp.orderliness_max_bar_ratio @ sp=3.75

Source: drill-down rows 141-145 of source artifact + drill-down section `### vcp.orderliness_max_bar_ratio`. Filter: sweep_point=3.75 AND old_bucket=watch AND new_bucket=aplus. Expected: ~1 raw watch->aplus flip record (max_delta_aplus = 1 per SUMMARY TABLE).

**LOCK:** sp=3.75 is the binding sweep_point per "first crossing of +1 delta_aplus" convention (rows 144-145 show both sp=3.75 AND sp=4.5 yield +1; sp=3.75 is the lower threshold + first crossing; the implementer locks sp=3.75 + adds a discriminating test verifying the SUMMARY TABLE -> drill-down mapping yields sp=3.75 not sp=4.5). If the implementer discovers sp=3.75 and sp=4.5 yield IDENTICAL flip sets (same watch->aplus tickers), record this in the findings doc but maintain the sp=3.75 LOCK.

**NEW module set at `research/harness/v2_orderliness_max_bar_ratio/`** (3 modules same shape).

**Output:** `exports/research/cohorts/v2_orderliness_max_bar_ratio_sp3_75.csv`.

### Sec 2.4 REUSE-VERBATIM: R2-A + R2-D cohorts

Per Sec 1.2: `r2a_tightness_days_required_sp1.csv` (7 unique rows) + `r2d_adr_min_pct_sp2_0.csv` (4 unique rows) REUSED VERBATIM. The investigation references these by canonical SHA + size; NO regeneration; NO modification.

**Byte-stability tests:** Investigation includes 6 byte-stability tests (3 R2-A modules + 3 R2-D modules unchanged from main HEAD `77d2162`). Pattern mirrors R2-D's 3 R2-A byte-stability tests + 6 D2 harness byte-stability tests.

### Sec 2.5 Bias-free baseline cohort (REUSE D2 EXPANDED N=71)

Per Sec 1.4: D2 EXPANDED bias-free baseline cohort fixture path: implementer verifies at slice 1 by inspecting D2 smoke artifact directory (`exports/research/w-bottom-ruleset-comparison-20260512T*` or similar from D2's EXPANDED smoke at Amendment 5). The N=71 fixture's raw W primary count + universe size (S&P 500 unique tickers scanned) is captured in D2's pattern_cohort_evaluator manifest. Implementer LOCKs both numbers via discriminating tests against the existing D2 fixtures.

### Sec 2.6 Investigation module set: `research/harness/v2_selection_mechanic/`

The 5 sibling extractor modules above each handle ONE V2 variable cohort. The investigation's analytical orchestration module set lives at `research/harness/v2_selection_mechanic/` and consumes the 5 cohort CSVs + the bias-free baseline:

- `__init__.py` (module docstring + L2 LOCK preservation note + brief reference)
- `substrate_characterization.py` -- per-ticker regime metrics computation (90-day return, ATR%, 52w prox, sector). Reads OHLCV from existing legacy archives via `swing.data.ohlcv_archive.read_or_fetch_archive` (or equivalent R2-A precedent). Reads sector via candidates table or finviz table read-only.
- `w_density_analysis.py` -- W-density measurement orchestration. Reads each V2 cohort CSV; invokes `pattern_cohort_evaluator` against the substrate (or reads existing detection-run artifacts if present); aggregates raw + filtered W counts; computes density + delta.
- `synthesis.py` -- compatibility verdict synthesis (Sec 1.7). Reads density delta table + regime fingerprint table; emits the narrative synthesis string + per-variable signal table.
- `run.py` -- top-level orchestration entrypoint runnable as `python -m research.harness.v2_selection_mechanic.run`. Emits artifacts to `exports/research/v2-selection-mechanic-analysis-<TS>/` + writes the study writeup at `research/studies/2026-05-26-v2-selection-mechanic-analysis.md` (overwrites OK on re-run; idempotent).

### Sec 2.7 Pre-flight archive refresh requirements

Operator-paired session-start step (mirrors R2-A + R2-D precedent): refresh stale legacy parquet archives for any V2 substrate tickers NOT already covered by R2-A's 7 tickers + R2-D's 4 tickers + D1's 67 tickers + D2's 88 tickers. The 2 NEW V2 substrates (proximity_max_pct + orderliness_max_bar_ratio) introduce potentially-new tickers; implementer enumerates + checks archive freshness at slice 1.

Procedure per ticker requiring refresh:
```
python -c "import yfinance as yf; df = yf.download('<TICKER>', period='max'); df.to_parquet('~/swing-data/prices-cache/<TICKER>.parquet')"
```
(NOT in scope for implementer; operator handles pre-flight; implementer notes which tickers were refreshed in findings doc Sec 10 mirroring R2-A precedent.)

---

## Sec 3 Output / analytical surface

### Sec 3.1 Study writeup (NEW first-class artifact)

**Path:** `research/studies/2026-05-26-v2-selection-mechanic-analysis.md`

Structure (matches D2 study + V2 OHLCV criterion-evaluator study precedent):
- Sec 1 Headline finding (analytical compatibility verdict synthesis)
- Sec 2 Methodology (cohort enumeration; canonical filter; metric definitions; bias-free baseline)
- Sec 3 Cohort detail (per-variable substrate table; tickers; asof_dates; pre-flight refresh notes)
- Sec 4 Substrate characterization (per-variable regime fingerprint table; metric medians + IQRs)
- Sec 5 W-density analysis (per-variable density delta table + interpretation)
- Sec 6 Cross-variable consistency synthesis
- Sec 7 R2-A + R2-D backtest carryover (linking the prior NEGATIVE + INSUFFICIENT SAMPLE findings to the current density / regime evidence)
- Sec 8 Compatibility verdict (narrative; per Sec 1.7)
- Sec 9 Methodological caveats + L6-style limitations
- Sec 10 V2 candidates + future work

### Sec 3.2 Smoke artifact directory (NEW)

**Path:** `exports/research/v2-selection-mechanic-analysis-<TS>/`

Contents:
- `manifest.json` -- run timestamp; source artifact SHAs; canonical filter parameters; environment versions; ZERO Schwab API calls assertion; ZERO production swing/ writes assertion
- `summary.md` -- human-readable run summary
- `per_variable_signals.csv` -- 5-row table: variable / cohort_size / raw_density / filtered_density / density_delta / regime_fingerprint_summary
- `substrate_characterization.csv` -- per-ticker metric values (1 row per (variable, ticker))
- `w_density_detail.csv` -- per-(variable, ticker) raw + filtered W counts
- `compatibility_synthesis.md` -- structured narrative output from `synthesis.py`

### Sec 3.3 Findings doc (NEW)

**Path:** `docs/v2-selection-mechanic-analysis-findings-2026-05-26.md`

Structure (mirrors R2-A + R2-D findings docs):
- Sec 1 Headline finding (mirrors study writeup Sec 1 + Sec 8)
- Sec 2 Cross-variable density delta table
- Sec 3 Per-variable regime fingerprint table
- Sec 4 R2-A + R2-D carryover synthesis
- Sec 5 Compatibility verdict (narrative)
- Sec 6 V2 candidates banked
- Sec 7 Codex MCP review summary
- Sec 8 Discipline preservation summary
- Sec 9 L6 + L5 + L4 caveats (per gotcha #26 + cumulative discipline)

### Sec 3.4 Return report (NEW)

**Path:** `docs/v2-selection-mechanic-analysis-return-report.md` (mirrors R2-D return report shape; will be authored by implementer).

---

## Sec 4 Discriminating tests

Estimated test count: ~100-140 fast tests (5 variable cohort modules x ~22 tests each = ~110; analytical orchestration ~20-30; cross-arc byte-stability ~12; L2 LOCK source-grep ~5).

Test scope by module:

### Sec 4.1 Per-variable cohort extraction tests (5 sibling modules)

For each of {v2_tightness_range_factor, v2_tightness_days_required (REUSE R2-A), v2_adr_min_pct (REUSE R2-D), v2_proximity_max_pct, v2_orderliness_max_bar_ratio}:

For NEW extractions (3 modules):
- Parser robustness tests (mirror R2-A R1-R5 + R2-D R1-R2 patterns)
- Section-boundary tests (drill-down section header regex)
- Sweep_point coercion tests (INT vs FLOAT per variable)
- Layered verifier tests (raw flip identity + aggregate counts)
- Canonical source SHA + size validation tests
- Audit JSON shape tests (cohort_selection_method + v2_binding_variable fields)
- --allow-non-canonical-paths CLI flag tests
- Committed-artifact canonical lock tests
- Module constants + binding signal LOCK tests

For REUSE modules (2):
- Byte-stability tests against main HEAD (3 R2-A modules + 3 R2-D modules)

### Sec 4.2 Investigation orchestration tests (`research/harness/v2_selection_mechanic/`)

- BINDING_SIGNALS_TABLE re-derivation from V2 sensitivity SUMMARY TABLE (gotcha #34 first canonical application discriminating test) -- runtime: read source artifact, parse SUMMARY TABLE, assert matches the hardcoded LOCK. Per-variable drill-down section header verification: parse drill-down, find row matching max_delta_aplus, assert sweep_point matches LOCK.
- Substrate characterization metric tests:
  - 90-day return on synthetic OHLCV fixtures (known input -> known output)
  - ATR% on synthetic OHLCV fixtures
  - 52w prox on synthetic OHLCV fixtures
  - Sector resolution: ticker-with-finviz-sector returns sector; ticker-without-finviz-sector + with-candidates-sector returns candidates-sector; ticker-without-either returns UNKNOWN
- W-density aggregation tests:
  - Mock pattern_cohort_evaluator output with N planted W primaries + M canonical-filtered survivors; assert density math correct
  - Edge case: zero W primaries -> density 0.0; zero unique tickers -> raise (NOT divide by zero)
- Bias-free baseline locking tests:
  - D2 EXPANDED N=71 fixture path verification + SHA lock
  - D2 universe size (S&P 500 unique tickers scanned) extraction lock
- Compatibility synthesis tests:
  - Synthetic per-variable signal table -> narrative synthesis (per Sec 1.7 categorical labels)
  - Asserts NO "PARTIAL POSITIVE" / "NEGATIVE" terminology emitted (per gotcha #33 analytical-not-verdict-producing LOCK)

### Sec 4.3 L2 LOCK + cumulative discipline tests

- L2 LOCK source-grep: parametrize over 5+ NEW module sets (v2_tightness_range_factor, v2_proximity_max_pct, v2_orderliness_max_bar_ratio, v2_selection_mechanic, + analytical sub-modules); assert ZERO `schwabdev` / `yfinance` / `swing.integrations.schwab` imports.
- ASCII discipline test: all NEW files (Python + Markdown + JSON + CSV) `.encode('ascii')` without UnicodeEncodeError. Scope enumeration per gotcha #32 BINDING.
- Cohort-validity discipline test: `synthesis.py` MUST NOT emit "PARTIAL POSITIVE" / "NEGATIVE" / "POSITIVE" verdict terminology (per gotcha #33 analytical-not-verdict-producing).
- Byte-stability test for `research/harness/r2a_tightness_days_required/` + `research/harness/r2d_adr_min_pct/` (6 tests).
- Byte-stability test for `research/harness/pattern_cohort_evaluator/` (preserve Phase 13 detector verbatim; ~3-5 tests covering core detector modules).
- Schema v21 LOCK (no migrations test).

### Sec 4.4 Brief-prescription cross-table verification test (gotcha #34 first canonical application)

NEW discriminating test at `tests/research/v2_selection_mechanic/test_binding_signals_table_cross_check.py`:
- Reads `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md`
- Parses SUMMARY TABLE at lines 13-22 -> extracts 5 (variable, max_delta_aplus) tuples
- Parses Sensitivity Matrix drill-down -> for each (variable, max_delta_aplus) finds row where delta_aplus matches max_delta_aplus -> extracts sweep_point
- Asserts the derived 5-tuple table matches the LOCKED BINDING_SIGNALS_TABLE constant verbatim
- Asserts: for each variable, exactly ONE sweep_point in drill-down yields max_delta_aplus (or if multiple, the LOWEST is locked per "first crossing" convention) -- this is the rule for orderliness sp=3.75 vs sp=4.5

### Sec 4.5 Verify-regression-test-arithmetic discipline (per cumulative `feedback_verify_regression_test_arithmetic`)

For each W-density math test: compute the expected output under BOTH the pre-fix arithmetic AND the post-fix arithmetic + assert the test distinguishes. Example: if computing `density = filtered_count / unique_ticker_count`, a test that asserts `density == 0.5` MUST be paired with a test that asserts `density != 1.0` (where 1.0 is the buggy result if denominator collapses to filtered_count). This is operator-binding for all numerical aggregation tests in the orchestration module.

---

## Sec 5 Acceptance criteria

### Sec 5.1 Functional

- [x] 3 NEW cohort extraction module sets at `research/harness/v2_{tightness_range_factor,proximity_max_pct,orderliness_max_bar_ratio}/` (3 modules each = 9 total NEW files in `research/harness/`)
- [x] 1 NEW analytical orchestration module set at `research/harness/v2_selection_mechanic/` (5 modules)
- [x] 3 NEW cohort CSVs at `exports/research/cohorts/v2_{tightness_range_factor,proximity_max_pct,orderliness_max_bar_ratio}_sp<N>.csv`
- [x] 3 NEW sibling audit JSONs at `exports/research/cohorts/v2_{variable}_sp<N>.flips_audit.json` (mirror R2-A + R2-D)
- [x] 1 NEW analytical smoke artifact directory at `exports/research/v2-selection-mechanic-analysis-<TS>/` (manifest + summary + 3 CSVs + 1 synthesis MD)
- [x] 1 NEW study writeup at `research/studies/2026-05-26-v2-selection-mechanic-analysis.md`
- [x] 1 NEW findings doc at `docs/v2-selection-mechanic-analysis-findings-2026-05-26.md`
- [x] 1 NEW return report at `docs/v2-selection-mechanic-analysis-return-report.md`
- [x] BINDING_SIGNALS_TABLE module constant locked + cross-table verified per gotcha #34

### Sec 5.2 Test scope

- [x] ~100-140 NEW fast tests; `python -m pytest tests/research/v2_selection_mechanic/ tests/research/v2_tightness_range_factor/ tests/research/v2_proximity_max_pct/ tests/research/v2_orderliness_max_bar_ratio/ -q` exits 0
- [x] All existing R2-A + R2-D tests still green (39 + 59 = 98 fast tests)
- [x] All existing D2 6-ruleset harness tests still green
- [x] All existing pattern_cohort_evaluator tests still green
- [x] Broader project fast suite: deferred for orchestrator-side verification

### Sec 5.3 Discipline preservation

- [x] ZERO Co-Authored-By footer drift across implementer commits
- [x] ZERO production `swing/` writes
- [x] Schema v21 unchanged (no migrations)
- [x] L2 LOCK preserved + REINFORCED via 3-5 NEW source-grep tests parametrized over NEW v2_selection_mechanic module set
- [x] ZERO new Schwab API calls
- [x] ASCII discipline complete (per gotcha #32 declared-scope-enumeration)
- [x] Sibling-module strategy LOCK preserved (R2-A + R2-D modules byte-stable; no common-parser refactor)

### Sec 5.4 Analytical deliverables

- [x] 5-row per-variable signal table (filled with measured numbers)
- [x] Per-variable regime fingerprint table (sector mix + median + IQR per metric)
- [x] Bias-free baseline W-density measurement + delta computation
- [x] Compatibility verdict synthesis (NARRATIVE; descriptive labels NOT PARTIAL POSITIVE / NEGATIVE)
- [x] 4-way cross-arc carryover (D2 EXPANDED + R2-A + R2-D + this investigation)
- [x] V2 candidates banked

### Sec 5.5 Cumulative discipline

- [x] CLAUDE.md gotcha #34 first canonical application (BINDING_SIGNALS_TABLE cross-table verification + discriminating test)
- [x] CLAUDE.md gotcha #33 third canonical application reinforced (analytical-not-verdict-producing; no cohort substitution)
- [x] CLAUDE.md gotchas #1-#34 fully BINDING; no NEW gotchas anticipated but possible (banked per Codex MCP chain output)
- [x] 42nd cumulative C.C lesson #6 validation slot consumed (per Codex MCP chain)

---

## Sec 6 Watch items + cumulative discipline

(a) **Cohort generation time cost:** 3 NEW extractions should each run <5 min (operator-side via grep + cohort_csv module). Total ~15 min wall-clock for extraction step.

(b) **D2 + R2-A + R2-D harness REUSE VERBATIM:** byte-stability tests assert. The investigation does NOT modify any prior module set.

(c) **NEW tickers in V2 substrates:** the 3 NEW extractions (tightness_range_factor + proximity_max_pct + orderliness_max_bar_ratio) introduce tickers not previously covered. Implementer enumerates NEW tickers at slice 1; operator runs pre-flight archive refresh BEFORE downstream substrate characterization + W-density computation.

(d) **Substrate characterization OHLCV reads:** ALL OHLCV reads route through `swing.data.ohlcv_archive.read_or_fetch_archive` (or read-only equivalent). DO NOT trigger yfinance fetches at substrate characterization time; if an archive is missing, surface a CLEAR ERROR + halt rather than fetch.

(e) **Codex MCP invocation:** YES (42nd C.C lesson #6 validation slot per handoff Sec 3.4). Default behavior: invoke after slice 5 + 6 (analytical computation + synthesis); converge at NO_NEW_CRITICAL_MAJOR. Pattern mirrors R2-A 5-round + R2-D 2-round chains. Banked V2 candidates from Codex chain land in return report Sec 6.

(f) **NEW gotcha #34 first canonical application:** the brief-prescription cross-table verification test at Sec 4.4 is BINDING. Implementer MAY NOT bypass via "the SUMMARY TABLE matches the drill-down section header" assertion; the test MUST PROGRAMMATICALLY parse both tables + cross-verify.

(g) **Cohort-validity discipline LOCK:** the synthesis layer MUST NOT emit "PARTIAL POSITIVE" / "NEGATIVE" / "POSITIVE" verdict terminology. Per gotcha #33 third canonical application: the investigation is ANALYTICAL not verdict-producing.

(h) **Method-record amendment guidance:** the investigation does NOT amend the V2 OHLCV criterion-evaluator method record (`research/method-records/aplus-criteria-calibration.md`) because the V2-mechanic finding is about COHORT SELECTION not evaluator correctness. The study writeup is the primary artifact + stands as a methodological complement.

(i) **D2 study writeup carryover:** if the investigation's compatibility synthesis materially extends D2's "E PARTIAL POSITIVE cohort-specific" interpretation, the D2 study writeup (`research/studies/2026-05-25-pattern-cohort-w-bottom-ruleset-comparison.md` or equivalent) MAY be amended with a cross-reference to this investigation's study writeup. If amended, the amendment language goes to a NEW "Amendment X" section preserving prior text.

(j) **Cumulative gotcha checks (#1-#34) per pre-Codex review scope expansions #1-#18:** implementer pre-Codex review applies all 18 expansion candidates. The brief-vs-actual-production-function-signature checks (expansion #2 + #17 + #19) are especially relevant for `pattern_cohort_evaluator` invocations; the SQL skeleton column verification (expansion #4 + #18 + #20) for any candidates-table reads; the per-counter-accumulation audit (expansion #8 + #22) for the W-density math; the architecture-location audit (expansion #10) for the investigation module's data dependencies.

---

## Sec 7 Codex MCP decision

**INVOKE.** 42nd cumulative C.C lesson #6 validation slot RESERVED per handoff Sec 1.

Recommended invocation sequence:
- After slice 4-5 ship (analytical computation + synthesis complete + study writeup drafted)
- Round 1: full scope (cohort extractions + substrate characterization + W-density + synthesis + study writeup)
- Subsequent rounds: address MAJOR + CRITICAL findings in-place; bank MINOR per cumulative pattern
- Convergence: NO_NEW_CRITICAL_MAJOR
- Document chain summary in return report Sec 4 mirroring R2-A + R2-D structure

Pre-Codex review scope expansion checklist (apply ALL 18 cumulative candidates at orchestrator-side AND implementer-side review):
- #1 hardcoded duplicate surface guard widening
- #2 + #17 + #19 brief-vs-actual-production-function-signature + call-graph + postponed-annotation
- #3 schema-CHECK + Python-constant + dataclass-validator paired + semantic-contract
- #4 + #18 + #20 SQL skeleton column verification + JOIN-cardinality + runtime-binding-shape
- #5 cross-section spec inventory grep
- #6 V1-completeness audit
- #7 cross-row semantic SCOPE audit
- #8 + #22 per-counter-accumulation
- #9 form-render anchor lifecycle (N/A for this investigation; no form-rendering)
- #10 architecture-location audit + 4 sub-disciplines
- #11 + #23 dataclass attribution metadata + taxonomy propagation
- #12 sibling-route audit (N/A; no new route handlers)
- #13 / #21 cumulative regression cascade in fix loops
- #14 recency/filter/dedup semantic-ordering
- #15 narrative artifact path/fact lag (POST-FIX SWEEP MANDATORY per gotcha #31)
- #16 ASCII discipline scope clarity
- #17 brief-prescription cross-table verification (NEW gotcha #34; FIRST canonical application)

---

## Sec 8 Commit cadence + return report

Estimated 14-22 commits. Suggested slice structure:

- **Slice 1:** v2_tightness_range_factor cohort extraction (NEW module set + 22 fast tests + cohort CSV + audit JSON). Verify count contract empirically + LOCK fixture identity per gotcha #33 third canonical reinforcement.

- **Slice 2:** v2_proximity_max_pct cohort extraction (NEW module set + tests + CSV + audit JSON). Same shape as slice 1.

- **Slice 3:** v2_orderliness_max_bar_ratio cohort extraction (NEW module set + tests + CSV + audit JSON). Locks sp=3.75 binding per "first crossing" convention; LOCKS the sp=3.75 vs sp=4.5 disambiguation in a discriminating test.

- **Slice 4:** v2_selection_mechanic orchestration module + BINDING_SIGNALS_TABLE constant + gotcha #34 first canonical application discriminating test + substrate characterization metric tests + W-density aggregation tests + bias-free baseline locking + compatibility synthesis tests.

- **Slice 5:** Smoke artifact + per-variable signal table + substrate characterization CSV + W-density detail CSV + compatibility synthesis MD. Verifies all 5 V2 cohort extractions integrate correctly via the orchestration module.

- **Slice 6:** Study writeup at `research/studies/2026-05-26-v2-selection-mechanic-analysis.md`.

- **Slice 7:** Codex MCP fix bundle(s) (1-3 commits per round; expected 2-5 rounds).

- **Slice 8:** Findings doc + return report. Post-fix narrative sweep per gotcha #31 (verify all cited paths + fact-values against shipped artifacts).

Return report template (mirror R2-D return report shape; will be authored by implementer at slice 8):
- Sec 1 Mission summary
- Sec 2 Implementation summary (NEW modules + artifacts + ZERO production swing/ writes)
- Sec 3 Commit-cadence ledger
- Sec 4 Codex MCP adversarial review chain (42nd cumulative C.C lesson #6 validation slot)
- Sec 5 Test status
- Sec 6 V1 simplifications + V2 candidates banked
- Sec 7 Cumulative discipline preservation
- Sec 8 Acceptance criteria checklist
- Sec 9 Handoff to orchestrator (merge commit message + suggested CLAUDE.md status-line amendment)

---

## Sec 9 Branch + worktree setup

```powershell
# From main worktree at c:\Users\rwsmy\swing-trading
git fetch origin main
git checkout -b applied-research-v2-selection-mechanic-investigation main
git worktree add .worktrees/applied-research-v2-selection-mechanic-investigation applied-research-v2-selection-mechanic-investigation
cd .worktrees/applied-research-v2-selection-mechanic-investigation
python -m swing.cli --help   # sanity: bare `swing` is NOT canonical; use `python -m swing.cli`
```

Branch base: `77d2162` (main HEAD at handoff brief commit time).

---

## Sec 10 Do NOT

- Re-litigate the LOCKED gotcha #33 + #34 disciplines (cohort-validity + brief-prescription cross-table)
- Modify production `swing/` (the investigation is analytical-only; no new CLI surface anticipated; if the operator decides a CLI surface IS needed for `swing diagnose v2-selection-mechanic` or similar, that's an OQ-13-mirror; banked V2 candidate)
- Modify V1 persisted state (no DB writes; no schema migrations; no candidates table changes)
- Trigger Schwab API calls (L2 LOCK; reinforced via NEW source-grep tests)
- Trigger yfinance fetches at runtime (operator handles pre-flight archive refresh ONLY; investigation reads cached archives via `read_or_fetch_archive` or equivalent; archive-miss raises ERROR rather than fetches)
- Reuse D1's hand-curated `tightness_1.005_flips_67.csv` for the V2 tightness_range_factor substrate (D1's +67 is hand-curated subset; investigation MUST extract the FULL raw flip set programmatically per Sec 2.1)
- Refactor R2-A or R2-D modules (sibling-module strategy LOCK; common-parser refactor banked V2 candidate)
- Modify D2 6-ruleset harness or `pattern_cohort_evaluator` (byte-stability tests assert)
- Emit "PARTIAL POSITIVE" / "NEGATIVE" / "POSITIVE" verdict terminology in `synthesis.py` output (per gotcha #33 analytical-not-verdict-producing LOCK; descriptive labels only -- COMPATIBLE / PARTIALLY-COMPATIBLE / INCOMPATIBLE or equivalent narrative)
- Substitute alternative cohort filter (per gotcha #33: canonical filter `composite>=0.5 + recency<=365d` held FIXED across all 5 V2 cohorts + the baseline; alternative scopes documented but not used for headline)
- Add Co-Authored-By footer to ANY commit (~559+ cumulative ZERO trailer drift; preserve)
- Skip cumulative gotcha discipline (34 gotchas BINDING)
- Skip the gotcha #34 first canonical application discriminating test (Sec 4.4 is BINDING)
- Author another orchestrator-handoff brief (Turn H ownership through investigation ship)

---

## Sec 11 Pre-dispatch operator-paired decisions (LOCKED via Turn H operator pairing 2026-05-26)

Per Turn H AskUserQuestion 2026-05-26 (orchestrator-side; pre-brief-authoring):

**Q1 -- Research questions in scope (V1):** ALL 4 SUBSTANTIVE QUESTIONS:
- #1 substrate-thinness mechanism
- #2 per-variable regime characterization
- #3 fundamental compatibility verdict
- #5 baseline cross-comparison
(#4 sp=2.0 artifact DEFERRED to V2.)

**Q2 -- Variables covered:** ALL 5 V2 BINDING VARIABLES:
- vcp.tightness_range_factor +75 @ sp=1.005
- vcp.tightness_days_required +16 @ sp=1 (REUSE R2-A module)
- vcp.adr_min_pct +11 @ sp=2.0 (REUSE R2-D module)
- vcp.proximity_max_pct +5 @ sp=7.5
- vcp.orderliness_max_bar_ratio +1 @ sp=3.75

**Q3 -- Bias-free S&P 500 baseline cross-comparison:** YES (REUSE D2 EXPANDED N=71 fixture).

**Q4 -- Output artifact structure:** NEW first-class study writeup at `research/studies/2026-05-26-v2-selection-mechanic-analysis.md`.

Operator-side Codex MCP decision: YES (42nd cumulative C.C lesson #6 validation slot RESERVED).

**Implementer:** these 4 decisions are LOCKED for the dispatch. No re-litigation; deviations require return-trip to operator via the orchestrator.

---

*End of V2-selection-mechanic investigation dispatch brief. The investigation is ANALYTICAL / EXPLORATORY (not a backtest); examines WHY V2-binding-variable cohort selection produces W-pattern-thin substrates (R2-D ~3% density vs peer ~12-13%) AND whether V2 selection is fundamentally compatible with E ruleset deployment. ZERO production `swing/` writes; ZERO new Schwab API calls; sibling-module strategy continues for cohort extractions; bias-free D2 EXPANDED baseline reused; first-class research study writeup as the primary artifact. 34 cumulative CLAUDE.md gotchas BINDING for 42nd cumulative C.C lesson #6 validation slot. NEW gotcha #34 (brief-prescription cross-table verification) FIRST CANONICAL APPLICATION post-banking; ~559+ cumulative ZERO Co-Authored-By trailer drift to preserve.*
