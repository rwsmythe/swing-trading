# R2-D Backtest Return Report

**Branch:** `applied-research-r2d-adr-min-pct-cohort-backtest`
**Dispatch brief:** [`docs/r2d-adr-min-pct-cohort-backtest-dispatch-brief.md`](r2d-adr-min-pct-cohort-backtest-dispatch-brief.md) (with Amendment 1)
**Findings doc:** [`docs/r2d-adr-min-pct-cohort-backtest-findings-20260526.md`](r2d-adr-min-pct-cohort-backtest-findings-20260526.md)
**Baseline SHA:** `6c34e2d070ce9951d74b4de522e12a3d43733af7` (R2-D dispatch brief commit)
**Final HEAD:** `ae039cc` (after smoke + Codex R2 NO_NEW_CRITICAL_MAJOR convergence + sidecar lock)
**Status:** READY FOR MERGE

---

## 1 Mission summary

Test whether R2-A's cohort-specific-NEGATIVE finding (`vcp.tightness_days_required +16` cohort; merge `634cc9f`; E mean R -1.086R / 95% CI [-1.377R, -0.782R] / NEGATIVE) is UNIQUE to tightness_days_required OR SYSTEMIC across V2 OHLCV binding variables. Run D2's 6-ruleset comparison harness against a DIFFERENT V2 binding variable cohort: `vcp.adr_min_pct +11`.

**Headline verdict: INSUFFICIENT SAMPLE (DIRECTIONAL POSITIVE color).** The R2-D canonical evaluation cohort (composite>=0.5 + recency<=365d) yields N=4 W primary verdicts ALL from STNG. Per dispatch brief Amendment 1 (post Codex R1 fix bundle) + gotcha #33 BINDING third canonical application, this substrate is statistically indistinguishable from a single-ticker case study and CANNOT defensibly support the cross-cohort generalization claim.

**Cross-cohort signal:** DEFERRED. R2-A NEGATIVE (N=65) vs R2-D INSUFFICIENT SAMPLE (N=4) does not discriminate between "tightness_days_required-SPECIFIC NEGATIVE" and "SYSTEMIC across V2 binding variables." A future R2-* dispatch against a thicker V2 binding-variable substrate (e.g., `proximity_max_pct +5` or `orderliness_max_bar_ratio +1`) is required.

---

## 2 Implementation summary

### 2.1 NEW research/harness/r2d_adr_min_pct/ modules

Ported R2-A's `research/harness/r2a_tightness_days_required/` template per dispatch brief section 1.2 sibling-module strategy LOCK:

- `__init__.py` -- module docstring + L2 LOCK preservation note + brief discrepancy disclosure (sp=1 vs actual sp=2.0).
- `cohort_csv.py` -- V2 sensitivity drill-down parser tuned for `vcp.adr_min_pct` + sweep_point=2.0 (FLOAT-valued; R2-A used int=1):
  - `extract_flips_from_sensitivity_md()` -- column-name-resolved markdown table parser
  - `verify_expected_r2d_cohort()` -- layered verifier (raw 11-tuple identity + ticker-asof 4-tuple set + aggregate counts)
  - `write_cohort_csv()` -- emit dedup-by-(ticker,asof) cohort CSV
  - `write_flips_audit_json()` -- audit JSON with source SHA + size + cohort_selection_method + v2_binding_variable fields
  - `verify_canonical_source_identity()` (NEW in R1 fix; Codex R1.M#5) -- source SHA-256 + size lock
  - `generate_r2d_cohort_artifacts()` -- canonical one-call wrapper with `allow_non_canonical_source` kwarg
  - 8 module constants: `EXPECTED_FLIP_COUNT=11`, `EXPECTED_UNIQUE_TICKER_ASOF=4`, `EXPECTED_TICKERS` (4-set), `EXPECTED_TICKER_ASOF` (4-tuple set), `EXPECTED_FLIPS` (11-tuple set), `R2D_COHORT_LABEL`, `R2D_VARIABLE_NAME`, `R2D_SWEEP_POINT`, `CANONICAL_SOURCE_SHA256`, `CANONICAL_SOURCE_SIZE_BYTES`.
- `regenerate_cohort.py` -- argparse-driven entrypoint runnable as `python -m research.harness.r2d_adr_min_pct.regenerate_cohort`; supports `--allow-non-canonical-paths` flag (Codex R1.M#6 fix).

### 2.2 NEW exports/research/ artifacts

- `exports/research/cohorts/r2d_adr_min_pct_sp2_0.csv` -- 4 unique (ticker, asof_date) rows with cohort_label `r2d_vcp_adr_min_pct_sp2_0`.
- `exports/research/cohorts/r2d_adr_min_pct_sp2_0.flips_audit.json` -- 11 raw flip records (with eval_run_id) + source artifact SHA-256 + size + `cohort_selection_method` + `v2_binding_variable` attribution.
- `exports/research/pattern-cohort-detection-20260526T160518Z/manifest.json + summary.md` (results.csv excluded per project convention; regeneratable via cohort CSV).
- `exports/research/w-bottom-ruleset-comparison-20260526T062529Z/manifest.json + summary.md + r2d_cohort_metadata.json` -- D2 6-ruleset smoke against R2-D cohort. The `r2d_cohort_metadata.json` sidecar (NEW Codex R1.M#4 closure) bridges the D2 harness's generic manifest to R2-D-specific attribution.

### 2.3 NEW tests/fixtures/research/r2d_adr_min_pct/

- `cohort.json` -- 4 canonical PrimaryVerdict entries (all STNG; composite>=0.5 + recency<=365d) for downstream test fixtures + D2 6-ruleset harness consumption.

### 2.4 NEW tests/research/r2d_adr_min_pct/

- `test_cohort_generation.py` -- 22 fast tests for parser robustness + flip identity + section-boundary + canonical wrapper + audit JSON shape + sweep_point=2.0 FLOAT-coercion.
- `test_harness_reuse_and_l2_lock.py` -- 12 tests for D2 + R2-A byte-stability + L2 LOCK source-grep + cohort-validity-vs-verdict-criteria documentation lock.
- `test_committed_artifacts_canonical.py` -- 5 tests locking the committed CSV + audit JSON against canonical SHA / size / metadata / row-identity.
- `test_codex_r1_fixes.py` -- 20 tests for Codex R1 + R2 fix bundle closures (brief Amendment 1 locks + fixture identity 4-tuple + audit JSON attribution + canonical source SHA + CLI flags + smoke sidecar).
- `__init__.py` (empty).

### 2.5 ZERO production swing/ modifications

The dispatch brief mandated REUSE of D2's CLI subcommand `python -m research.harness.w_bottom_ruleset_comparison.run` against the R2-D cohort.json fixture; no production swing/ writes were needed. All 6 byte-stability tests for D2 harness pass + all 3 byte-stability tests for R2-A modules pass -- both module sets unchanged from `main` HEAD.

---

## 3 Commit-cadence ledger

| Commit | Description |
|---|---|
| `a1fbd60` | Slice 1: cohort CSV generator + 22 fast tests (11 flips -> 4 unique tuples; sp=2.0 FLOAT) |
| `d0892fc` | Slice 2: cohort.json fixture + 17 harness-reuse / L2-LOCK / committed-artifact tests |
| `2be5df2` | Codex R1 fix bundle: 6 MAJOR + 1 MINOR closures (Amendment 1; fixture identity lock; audit JSON attribution; canonical source SHA validation; --allow-non-canonical-paths flag) |
| `19a8179` | Codex R2 minor fix bundle: 3 of 4 MINOR closures (flag-bypass proof; identity quadruple; CLI output-path rejection test) |
| `ae039cc` | D2 6-ruleset backtest smoke artifact + r2d_cohort_metadata.json sidecar + lock test |
| _this commit_ | Slice 6: findings doc + return report |

**Total: 6 commits; ZERO Co-Authored-By trailer drift (preserves ~558+ cumulative streak through R2-A merge `634cc9f`).**

---

## 4 Codex MCP adversarial review chain (41st cumulative C.C lesson #6 validation slot)

| Round | C | M | m | Resolution summary |
|---|---|---|---|---|
| R1 | 0 | 6 | 2 | 6 MAJOR + 1 MINOR resolved in-code; 1 MINOR banked (R1.m#2 byte-stability vs main per R2-A precedent) |
| R2 | 0 | 0 | 4 | 3 MINOR resolved in-code; 1 MINOR non-actionable (R2.m#4 Codex sandbox cannot run pytest) |

**Cumulative: 0 CRITICAL + 6 MAJOR + 6 MINOR; ALL MAJOR RESOLVED in-place; 4 of 6 MINOR RESOLVED in-code; 2 MINOR BANKED.** R2 verdict: `NO_NEW_CRITICAL_MAJOR` -- chain converged after 2 rounds.

**41st cumulative C.C lesson #6 validation NOTABLE.** Codex caught 6 REAL MAJOR defects despite pre-Codex application of all 17 cumulative expansion candidates:
- R1.M#1: brief sweep_point reconciliation (sp=1 prescription vs actual sp=2.0 binding signal)
- R1.M#2: INSUFFICIENT SAMPLE pre-commit per gotcha #33 (N=4 STNG-only substrate too thin for systemic claim)
- R1.M#3: fixture identity lock (empty fixture silently passed issubset check)
- R1.M#4: audit JSON cohort_selection_method + v2_binding_variable attribution fields missing
- R1.M#5: canonical source SHA + size validation missing in wrapper
- R1.M#6: --allow-non-canonical-paths CLI flag claimed in brief but not implemented

### 4.1 NEW writing-plans / brief-authoring patterns banked

1. **Brief authoring discipline: cross-check canonical sweep_point against V2 sensitivity SUMMARY table**, not just the drill-down section header. The R1.M#1 surface (brief prescribed sp=1; actual binding signal sp=2.0) escaped pre-Codex review because the brief's count contract (11 flips) was empirically met at sp=2.0 but the brief's prescription (sp=1) yielded a different 15-flip cohort. Future R2-* briefs MUST cite the V2 sensitivity summary table's `max_delta_aplus` cell explicitly when prescribing the binding sweep_point.

2. **Fixture identity lock discipline: assert exact N + exact ticker set + exact (trough_1_date, center_peak_date, trough_2_date, composite_score) 4-tuple set**, not just subset / non-empty / range checks. The R1.M#3 surface (empty fixture silently passing issubset check) is a cumulative gap in fixture-identity discipline -- the existing R2-A fixture test uses set-equality on tickers but did not exhaustively lock structural identity per entry.

3. **Audit envelope attribution discipline: explicit cohort_selection_method + variable_name attribution fields in the persisted audit JSON**, not implicit from variable_name only. The R1.M#4 surface (downstream consumers cannot attribute selection method from variable_name alone) is a forward-binding lesson for any cohort-extraction module.

4. **Canonical source identity discipline: source SHA + size lock in the canonical wrapper**, with explicit override flag for non-canonical regeneration. The R1.M#5 surface (a source artifact with the same 11 triples but altered surrounding text could regenerate 'canonical' outputs) is a defense-in-depth lesson for any V2 sensitivity-style source-based pipeline.

5. **CLI flag-vs-brief contract discipline: claimed CLI flags MUST be implemented**, with discriminating tests that exercise the rejection path. The R1.M#6 surface (brief mentioned `--allow-non-canonical-paths` but the entrypoint had no such flag) is a writing-plans-phase lesson: brief contracts MUST be reified in the implementation, not just referenced.

### 4.2 ALL 18 OQ-style dispositions LOCKED verbatim through dispatch -> Codex chain -> ship

ZERO amendments to the dispatch brief's substantive content during execution (only Amendment 1 was appended post-Codex R1; the original sections preserved verbatim as authoring record per A1.5).

---

## 5 Test status

- 59 R2-D fast tests pass (`tests/research/r2d_adr_min_pct/`).
  - 22 test_cohort_generation.py
  - 12 test_harness_reuse_and_l2_lock.py
  - 5 test_committed_artifacts_canonical.py
  - 20 test_codex_r1_fixes.py (R1 fix tests + R2 minor fix tests + smoke sidecar test)
- 39 R2-A fast tests still pass (byte-stability defenses inherited; R2-A modules FROZEN).
- 98 total R2-A + R2-D fast tests green.
- Broader project fast suite: deferred for orchestrator-side verification (no production swing/ changes; D2 harness + R2-A modules byte-unchanged tests pass).
- L2 LOCK preserved + reinforced via 3 NEW R2-D source-grep tests parametrized over r2d_adr_min_pct module set.

---

## 6 V1 simplifications + V2 candidates banked

Per cumulative discipline (CLAUDE.md V1-simplification-banking discipline):

### Banked from Codex chain

1. **R1.m#2 / R2.m#2 byte-stability vs merge-base**: byte-stability tests compare to `main` HEAD (R2-A precedent). For long-lived branch review stability, prefer merge-base comparison. V2 hardening candidate.

2. **R2.m#4 Codex sandbox cannot run pytest**: non-actionable for the implementer; informational. Future Codex MCP runs may benefit from a sandbox policy that allows `pytest` invocation (V2 consideration for copowers plugin).

### Banked from R2-A precedent + R2-D-specific

3. **Common-parser refactor (dispatch brief section 1.2 banking)**: R2-A + R2-D + future R2-* common cohort_csv.py parser logic pulled into a `research/harness/cohort_extractors/v2_sensitivity_drilldown.py` shared module. R2-D adds the FLOAT-valued sweep_point coercion + tolerance check as a parametrization axis. Banked V2 candidate.

4. **Pattern Pass-2 template matching empty (gotcha #28 / #29 family)**: pattern_cohort_evaluator smoke shows `template_match_score=None` across ALL 1559 emitted double_bottom_w verdicts (cache-empty per exemplar OHLCV pre-fetch limitation; same condition as R2-A). Composite_score collapses to geometric_score only. R2-D verdict is NOT materially affected because the canonical evaluation cohort is N=4 STNG-only; template matching would not have rescued additional AMX/GLNG/XENE tickers (those have ZERO W primaries within the recency window regardless of template scoring). Banked V2 dependency: extend `_step_exemplar_ohlcv` pipeline step OR pre-fetch exemplar tickers operationally before R2-* dispatches.

5. **Bootstrap CI on R2-D's R distribution (brief section 6.4 ask)**: with N=1 closed for Ruleset E and N=3 closed for Ruleset F, bootstrap CI is undefined / unreliable. The brief's bootstrap-CI request is implicitly contingent on N >= 10 closed per D2 Amendment 5.3 methodology. Banked: a future R2-* dispatch with N >= 20 closed-and-profitable per ruleset can run the bootstrap re-evaluation.

6. **Thicker-substrate cross-cohort discrimination (Amendment 1 A1.3 deferred test)**: future R2-E (`proximity_max_pct +5`) or R2-F (`orderliness_max_bar_ratio +1`) dispatch with the same harness architecture (sibling module pattern; same canonical filter; same 6-ruleset comparison) should reveal whether the cohort-specific NEGATIVE pattern persists. The implementer recommends R2-E next (next-largest-remaining binding variable per brief section 11.2 ordering).

### Banked from substrate-density analysis

7. **V2 binding-variable selection mechanic produces thin W substrates**: R2-D's substrate density (~3%) is ~4x thinner than R2-A's (~13%) or D2 EXPANDED's (~12%). This may be a systemic property of V2 binding-variable selection: the cohort filter selects tickers based on classification flips, NOT historical W-pattern incidence. If R2-E also reproduces this thin-substrate pattern, the **next-arc investigation** is: WHY does V2 selection produce W-pattern-thin substrates? Is the recency<=365d filter over-restrictive for selection-biased cohorts (gotcha #33 boundary)? Banked as: methodologically informative even if it falls outside R2-D's primary research question.

---

## 7 Cumulative discipline preservation

- **ZERO Co-Authored-By footer trailer drift** (~558+ cumulative streak preserved through baseline `6c34e2d`; R2-D adds 6 commits all clean).
- **ZERO production swing/ writes** (R2-D reuses D2's existing CLI subcommand; no new CLI surface).
- **L2 LOCK preserved + reinforced** (3 NEW R2-D source-grep tests parametrized over r2d_adr_min_pct module set; ZERO new schwabdev / yfinance / swing.integrations.schwab imports).
- **Schema v21 unchanged** (no migrations).
- **ZERO new Schwab API calls** at backtest time (uses V2 Shape A reader's legacy parquet fallback; all 4 tickers use legacy `.parquet` files at `~/swing-data/prices-cache/`).
- **ASCII discipline preserved** across all NEW R2-D files (cohort_csv.py / regenerate_cohort.py / __init__.py / 4 test files / cohort.json / cohort CSV / audit JSON / smoke artifact files / findings doc / return report / brief amendment).
- **D2 harness REUSED verbatim** (6 byte-stability tests pass; `research/harness/w_bottom_ruleset_comparison/` unchanged from main).
- **R2-A modules FROZEN** (3 byte-stability tests pass; `research/harness/r2a_tightness_days_required/` unchanged from main; sibling-module strategy LOCK preserved).

---

## 8 Acceptance criteria checklist (dispatch brief section 6 + Amendment 1)

### Section 6.1 Functional

- [x] Cohort CSV generated at `exports/research/cohorts/r2d_adr_min_pct_sp2_0.csv` (4 unique rows).
- [x] Sibling audit JSON at `exports/research/cohorts/r2d_adr_min_pct_sp2_0.flips_audit.json` (11 raw flips + source SHA-256 + cohort_selection_method + v2_binding_variable).
- [x] pattern_cohort_evaluator smoke produces W primary verdicts for the 4-entry cohort (1559 raw double_bottom_w verdicts).
- [x] Cohort.json fixture at `tests/fixtures/research/r2d_adr_min_pct/cohort.json` (N=4 canonical primaries; all STNG).
- [x] D2 6-ruleset harness invoked against new fixture; smoke artifact at `exports/research/w-bottom-ruleset-comparison-20260526T062529Z/`.
- [x] Manifest `l2_lock_preserved: true`; `cohort_selection_method: v2_binding_variable_flips` + `v2_binding_variable: vcp.adr_min_pct` (in r2d_cohort_metadata.json sidecar per Codex R1.M#4).

### Section 6.2 Test scope

- [x] 59 NEW R2-D fast tests (exceeds 10-15 target; Codex-driven expansion).
- [x] `python -m pytest tests/research/r2d_adr_min_pct/ -q` exits 0.
- [x] All R2-A tests (39) still green.
- [ ] Broader project fast suite: deferred for orchestrator-side verification.

### Section 6.3 Discipline preservation

- [x] ZERO Co-Authored-By footer drift.
- [x] ZERO production swing/ writes.
- [x] Schema v21 unchanged.
- [x] ZERO new Schwab API calls (L2 LOCK; reinforced via 3 NEW R2-D source-grep tests).
- [x] ASCII discipline complete (all NEW R2-D files are ASCII-only; declared scope per gotcha #32).

### Section 6.4 Analytical deliverables

- [x] Artifact directory at `exports/research/w-bottom-ruleset-comparison-20260526T062529Z/`.
- [x] Findings doc at `docs/r2d-adr-min-pct-cohort-backtest-findings-20260526.md`.
- [x] Return report at `docs/r2d-adr-min-pct-cohort-backtest-return-report.md`.
- [x] 4-way cross-cohort comparison vs R2-A + D2 EXPANDED + D2 Companion 2 + D1 in findings section 2.
- [x] Verdict classification per Amendment 1 (post brief section 6.5 update): **INSUFFICIENT SAMPLE** (DIRECTIONAL POSITIVE color); gotcha #33 BINDING third canonical application.
- [ ] Bootstrap CI on E R distribution: SKIPPED per V2 candidate 5 (N=1 closed E + N=3 closed F insufficient for defensible bootstrap; banked for future R2-* with N >= 20).

### Section 6.5 Verdict classification (per Amendment 1 A1.2 + A1.3)

- [x] Applied to canonical evaluation cohort verbatim per gotcha #33 (no cohort substitution).
- [x] **INSUFFICIENT SAMPLE** verdict (N=4 STNG-only is well below brief's expected N=50-200 range; PARTIAL POSITIVE thresholds met by F technically but headline forbidden per gotcha #33 cohort-validity discipline).
- [x] Cross-cohort consistency assertion: DEFERRED (R2-A NEGATIVE vs R2-D INSUFFICIENT SAMPLE cannot discriminate systemic-vs-cohort-specific; banked to future R2-E / R2-F dispatch).

### Section 7 Watch items

- [x] (a) Cohort generation time cost: <5 min orchestrator-side via grep + cohort_csv module.
- [x] (b) D2 + R2-A harness REUSE VERBATIM: 9 byte-stability tests pass (6 D2 + 3 R2-A).
- [x] (c) R2-D ticker overlap with R2-A (0), D2 (0), D1 (0): documented.
- [x] (d) NEW tickers AMX/GLNG/STNG/XENE: pre-flight archive refresh applied (all 4 refreshed via yfinance period='max' through 2026-05-26; operator-authorized at session start).
- [x] (e) Cross-comparison cardinality: 4 R2-D vs 65 R2-A vs 71 D2 EXPANDED vs 12 D1; ZERO ticker-overlap with R2-A.
- [x] (f) Codex MCP invocation: invoked; 2 rounds; converged at R2 NO_NEW_CRITICAL_MAJOR.

### Section 10 Do NOT (compliance)

- [x] No modifications to `research/harness/w_bottom_ruleset_comparison/` (6 byte-stability tests confirm).
- [x] No modifications to `research/harness/r2a_tightness_days_required/` (3 byte-stability tests confirm).
- [x] No refactor of R2-A's `cohort_csv.py` into shared generic (V2 candidate; OUT OF SCOPE for R2-D).
- [x] No modifications to production `swing/` (D2 CLI subcommand reused verbatim).
- [x] No new rulesets (A-F unchanged from D2).
- [x] No Co-Authored-By footer.
- [x] No override of D2 / R2-A smoke artifacts (R2-D in NEW dated subdirectory).
- [x] No substitution of alternative cohort filter (gotcha #33 third canonical application; Amendment 1 LOCKS canonical filter at composite>=0.5 + recency<=365d).

---

## 9 Handoff to orchestrator

R2-D backtest implementation + Codex review + smoke + findings + return report COMPLETE end-to-end.

**Ready for orchestrator merge per `feedback_orchestrator_performs_merge` BINDING.**

Recommended merge commit message (no Claude co-author footer):

```
Merge applied-research-r2d-adr-min-pct-cohort-backtest into main: R2-D V2 OHLCV vcp.adr_min_pct +11 cohort 6-ruleset backtest SHIPPED -- INSUFFICIENT SAMPLE verdict on canonical evaluation cohort (composite>=0.5 + recency<=365d; N=4 STNG-only); DIRECTIONAL POSITIVE color on F (3 of 3 closed @ +0.122R) + E (1 of 1 closed @ +0.800R); cross-cohort systemic-vs-cohort-specific test DEFERRED to future R2-* against thicker substrate (R2-A NEGATIVE on N=65 vs R2-D INSUFFICIENT SAMPLE on N=4 cannot discriminate); 41st cumulative C.C lesson #6 validation NOTABLE; Codex MCP 2 rounds R2 NO_NEW_CRITICAL_MAJOR; 0 new gotchas; gotcha #33 cohort-validity discipline applied as canonical third application; brief Amendment 1 reconciles sp=1 prescription vs actual sp=2.0 binding signal + pre-commits INSUFFICIENT SAMPLE verdict
```

Suggested CLAUDE.md status-line amendment (orchestrator-side):
- Append R2-D SHIPPED at HEAD `<merge-sha>`; INSUFFICIENT SAMPLE verdict; cross-cohort systemic-vs-cohort-specific test DEFERRED.
- C.C lesson #6 validation count: 41 NOTABLE (was 40 R2-A NOTABLE).
- Brief Amendment 1 sweep_point reconciliation: precedent for future R2-* dispatches (lesson banked for brief-authoring discipline).
- ~558+ cumulative ZERO Co-Authored-By streak preserved.

Next-arc operator decisions banked (section 6 above); orchestrator chooses next dispatch:

1. **R2-E: vcp.proximity_max_pct +5** (recommended; next-largest remaining binding variable; substrate density unknown).
2. **R2-F: vcp.orderliness_max_bar_ratio +1** (last remaining V2 binding variable; substrate likely thinnest).
3. **Market-conditions investigation** (pivot away from V2 binding-variable cross-cohort dimension).
4. **V2 binding-variable selection mechanic investigation** (banked V2 candidate 7; WHY are V2-selected substrates W-pattern-thin?).
5. **Phase 14 commissioning** (per Path B sequencing).
