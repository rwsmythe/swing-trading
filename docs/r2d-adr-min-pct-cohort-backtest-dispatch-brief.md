# R2-D Backtest: V2 OHLCV `vcp.adr_min_pct +11` Cohort 6-Ruleset Comparison -- Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the R2-D backtest implementer. No prior conversation context.

**Mission:** Test whether R2-A's cohort-specific-NEGATIVE finding (`vcp.tightness_days_required +16` cohort; merge `634cc9f`; E mean R -1.086R / 95% CI [-1.377, -0.782]R / NEGATIVE) is UNIQUE to tightness_days_required OR SYSTEMIC across V2 OHLCV binding variables. Run D2's 6-ruleset comparison harness against a DIFFERENT V2 binding variable cohort (`vcp.adr_min_pct +11`; 11 watch->aplus flips at sweep_point=1) + cross-compare verdict with R2-A NEGATIVE + D2 EXPANDED PARTIAL POSITIVE + D1 NEGATIVE-strict.

**Workflow:** `copowers:executing-plans` skill (wraps `superpowers:test-driven-development` + Codex MCP adversarial review). Codex MCP invocation per pre-dispatch operator-paired decision (see §11; recommendation YES per R2-A + D2 precedent; 41st cumulative C.C lesson #6 validation slot).

**Branch:** `applied-research-r2d-adr-min-pct-cohort-backtest` -- branches from main HEAD `6f64f91` (or later; reflects R2-A merge `634cc9f` + Amendment 6 housekeeping).

**Worktree:** `git worktree add .worktrees/applied-research-r2d-adr-min-pct-cohort-backtest applied-research-r2d-adr-min-pct-cohort-backtest`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Expected duration:** ~4-6h operator-paced + ~1-2h Codex chain. Same scope as R2-A; the R2-A architecture template + parser robustness fixes (Codex R1-R5 cumulative) carry forward via a sibling module.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/r2a-vcp-tightness-days-required-cohort-backtest-dispatch-brief.md`** -- R2-A dispatch brief. **R2-D is functionally a re-execution of R2-A's pattern against a DIFFERENT V2 binding variable.** Reuse §2-§8 verbatim with variable swap; this brief only documents the DELTAS.

3. **`docs/r2a-tightness-days-required-cohort-backtest-findings-20260526.md`** -- R2-A findings doc. Especially §2 cross-cohort comparison table + §3 per-ticker concentration + §4 cohort-validity discipline.

4. **`docs/r2a-tightness-days-required-cohort-backtest-return-report.md`** -- R2-A return report. Especially §2.1 R2-A `cohort_csv.py` architecture (CONSTANTS + parser robustness + layered verifier + canonical wrapper) + §4 Codex chain (5 rounds; 26M+21m converged; 5 NEW parser-robustness defenses).

5. **`docs/pattern-cohort-w-bottom-ruleset-comparison-findings-2026-05-25.md`** -- D2 findings doc. Especially Amendment 6 (post-merge housekeeping at `6f64f91`; cross-cohort consistency check; R2-A finding bounds D2 E PARTIAL POSITIVE generalization scope).

6. **`research/harness/w_bottom_ruleset_comparison/`** -- D2 harness (5 modules). **REUSE VERBATIM** for R2-D (same as R2-A). Asserted via byte-stability tests inherited from R2-A.

7. **`research/harness/r2a_tightness_days_required/`** -- R2-A cohort-extraction module set (3 modules: `cohort_csv.py` + `regenerate_cohort.py` + `__init__.py`). **THIS IS THE ARCHITECTURAL TEMPLATE** for R2-D's NEW sibling module set. The implementer creates a sibling at `research/harness/r2d_adr_min_pct/` with R2-D-specific constants (variable_name + expected flip count + expected tickers + expected flip-tuples).

8. **`exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.{csv,md}`** -- V2 OHLCV sensitivity smoke artifact (full-63-eval-run reproduction; SAME source as R2-A; SAME SHA-256). Contains the `vcp.adr_min_pct` per-sweep-point drill-down with **11 watch->aplus flip records at sweep_point=1** across N unique tickers (precise list to be enumerated by implementer at slice 1).

9. **`reference/methodology/`** -- Minervini Stage-2 framework (primary literature source per operator decision).

10. **`mcp__qullamaggie__*` MCP tools** -- Qullamaggie reference for Ruleset F semantics (unchanged from D2 + R2-A).

11. **CLAUDE.md** gotchas #1-#33 -- cumulative discipline. **ESPECIALLY relevant:**
    - **#33** cohort-validity-vs-verdict-criteria distinction (now 3rd canonical application post-R2-A SHIPPED Amendment 6; discipline LOCKED)
    - **#28 + #29** OHLCV cache discipline (exemplar OHLCV provisioning; same as D2 + R2-A; verify pre-flight)
    - **#30** recency/filter/dedup semantic-ordering (inherit D2 discipline)
    - **#31** narrative artifact path/fact lag (post-fix sweep mandatory)
    - **#32** ASCII discipline scope clarity

---

## §1 R2-D cohort generation procedure

### §1.1 Source: V2 OHLCV sensitivity drill-down (UNCHANGED from R2-A)

Source artifact: `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md` (SAME file as R2-A; canonical SHA-256 `b25bcde9...`). Drill-down section `### vcp.adr_min_pct` (precise grep at execution time).

Filter from drill-down: `sweep_point=1` AND `old_bucket=watch` AND `new_bucket=aplus`. Expected: **11 flip records** across N unique tickers (precise count TBD; implementer enumerates from the drill-down table at slice 1).

### §1.2 R2-D module set (NEW sibling of R2-A; DO NOT modify R2-A)

Create NEW module set at `research/harness/r2d_adr_min_pct/`:
- `cohort_csv.py` -- PORT R2-A's parser module verbatim; swap module constants:
  - `EXPECTED_FLIP_COUNT = 11` (was 15)
  - `EXPECTED_UNIQUE_TICKER_ASOF = <TBD>` (implementer determines after slice 1 enumeration)
  - `EXPECTED_TICKERS = frozenset({...})` (implementer enumerates the N unique tickers)
  - `EXPECTED_TICKER_ASOF = frozenset({...})` (implementer enumerates N tuples)
  - `EXPECTED_FLIPS = frozenset({...})` (implementer enumerates 11 tuples)
  - `R2D_COHORT_LABEL = "r2d_vcp_adr_min_pct_sp1"`
  - `R2D_VARIABLE_NAME = "vcp.adr_min_pct"`
  - `CANONICAL_SOURCE_SHA256 = "b25bcde9..."` (same as R2-A; the source artifact is unchanged)
- `regenerate_cohort.py` -- PORT R2-A's entrypoint verbatim; swap canonical paths to R2-D names; preserve `--allow-non-canonical-paths` semantics (banked R5.minor#2 V2 candidate per R2-A return report §6).
- `__init__.py` -- module docstring referencing THIS brief + L2 LOCK preservation.

**Architecture decision LOCK (per orchestrator pre-dispatch):** sibling module strategy is CANONICAL. DO NOT refactor R2-A's `cohort_csv.py` into a shared base / generic. Each R2-* cohort gets its own module set. V2 candidate banked at THIS brief: post-R2-D ship, the operator MAY pivot to a refactor that pulls common parser logic into a `research/harness/cohort_extractors/v2_sensitivity_drilldown.py` shared module + R2-A + R2-D + future R2-* become thin parametrized wrappers. NOT in scope for R2-D.

### §1.3 Cohort fixture generation

Build cohort.json fixture at `tests/fixtures/research/r2d_adr_min_pct/cohort.json`. Fixture shape MUST mirror R2-A's cohort.json (and D2's; same PrimaryVerdict serialization). Process:

```powershell
# Step 1: Generate cohort CSV from V2 sensitivity drill-down
python -m research.harness.r2d_adr_min_pct.regenerate_cohort

# Step 2: Run pattern_cohort_evaluator against the +11 sweep_point=1 cohort
python -m swing.cli diagnose pattern-cohort-detect `
  --cohort-csv exports/research/cohorts/r2d_adr_min_pct_sp1.csv `
  --db "$env:USERPROFILE/swing-data/swing.db" `
  --output-dir exports/research/ `
  --pattern-class-filter double_bottom_w
```

Expected runtime: ~1-2 min (11 cohort entries; small).

### §1.4 Cohort scope analysis pre-backtest (UNCHANGED from R2-A §1.3)

Report in findings doc:
- Number of W primary verdicts emitted (raw)
- Number passing composite>=0.7 (D2 brief default)
- Number passing composite>=0.5 + recency<=365d (CANONICAL evaluation cohort per D2 Amendment 5 + R2-A Amendment 6)
- Number passing composite>=0.5 + recency<=120d (Companion 2 filter)
- Cross-comparison cardinality table -- R2-D N vs R2-A N=65 vs D2 EXPANDED N=71 vs D2 Companion 2 N=26 vs D1 N=12

### §1.5 Pre-flight checks before backtest

Same as R2-A §1.4. Verify NEW R2-D tickers have current archives in `~/swing-data/prices-cache/`. The R2-D ticker set is DIFFERENT from R2-A's {FRO/KOD/NAT/OII/RLMD/SEI/TROX}. Implementer enumerates R2-D's ticker set + checks each archive; refresh stale tickers via yfinance `period='max'` (per R2-A's pre-flight pattern).

---

## §2 Entry rule (UNCHANGED from D2 + R2-A)

Per D2 dispatch brief §2 + R2-A dispatch brief §2. REUSE verbatim:
- Trigger: first daily close > `center_peak_price` after `effective_asof_date`
- Entry: next-session OPEN
- Initial stop: ruleset-dependent (D + F use trough_2 * 0.99; E uses max(trough_2 * 0.99, entry * 0.92))
- Trigger search window: effective_asof + 1 BD lower, effective_asof + 60 BD upper

---

## §3 Six rulesets -- UNCHANGED from D2 + R2-A

Per D2 dispatch brief §3.1-3.6. REUSE D2 implementations verbatim. No new rulesets.

---

## §4 Output / analytical surface

Per D2 dispatch brief §4 + R2-A dispatch brief §4. Smoke artifact path: `exports/research/r2d-adr-min-pct-backtest-<ISO>/` (canonical naming distinguishable from R2-A's `r2a-tightness-days-required-backtest-<ISO>/`).

27-column CSV (post-R2-A R3 schema; UNCHANGED); summary.md with per-ruleset stats + cross-ruleset comparison; manifest.json with cohort SHA-256 + provenance fields + `cohort_selection_method: v2_binding_variable_flips` + NEW field `v2_binding_variable: vcp.adr_min_pct`.

**NEW analytical sections in summary.md / findings doc** (extended from R2-A's cross-cohort section):
- 4-cohort cross-comparison: R2-D + R2-A + D2 EXPANDED + D2 Companion 2 + D1 post-refresh (5 rows in table)
- Per-V2-binding-variable ranking: is R2-D's E result CONSISTENT with R2-A's NEGATIVE (suggesting SYSTEMIC V2-binding-variable cohort-specificity)? OR DISTINCT (suggesting tightness_days_required-specific phenomenon)?
- Per-ticker overlap with D1 + D2 + R2-A: enumerate which (if any) R2-D tickers appear in prior cohorts
- Statistical-defensibility tier per D2 Amendment 5.5

---

## §5 Discriminating tests (~10-15 fast tests; LIGHTER than R2-A because architecture template is established)

### §5.1 Cohort fixture generation (~3-5 tests; mirror R2-A §5.1)

- Parse V2 sensitivity drill-down + filter to sweep_point=1 + watch->aplus + variable_name="vcp.adr_min_pct"; assert 11 entries / N unique tickers.
- Generate cohort.json fixture; verify shape matches R2-A + D2 fixture; verify round-trip preservation.
- Verify NEW `R2D_VARIABLE_NAME` constant equals `"vcp.adr_min_pct"` (NOT `"vcp.tightness_days_required"`).

### §5.2 Cohort-validity cross-check (~3 tests; gotcha #33 third canonical application)

- Manifest field `cohort_selection_method: v2_binding_variable_flips` (UNCHANGED from R2-A).
- Manifest field `v2_binding_variable: vcp.adr_min_pct` (NEW; distinguishes R2-D from R2-A).
- Findings doc asserting canonical evaluation cohort definition + 4-way cross-comparison vs R2-A + D2 EXPANDED + D2 Companion 2 + D1.

### §5.3 D2 harness REUSE verbatim (~6 tests; mirror R2-A §5.3 byte-stability suite)

INHERIT R2-A's 6 byte-stability parametrize for `research/harness/w_bottom_ruleset_comparison/` modules + 1 cohort module. ADD: assert `research/harness/r2a_tightness_days_required/` modules ALSO unchanged (no cross-bundle drift between R2-A + R2-D).

### §5.4 L2 LOCK (~2 tests; mirror R2-A §5.4)

- Source-grep test parametrized over R2-D's 2 NEW modules: `r2d_adr_min_pct/cohort_csv.py` + `r2d_adr_min_pct/regenerate_cohort.py`. Assert NO schwab / yfinance / swing.integrations.schwab imports.
- Existing R2-A L2 LOCK tests + D2 + V2 5 BINDING tests all still pass.

### §5.5 Committed-artifact canonical lock (~4 tests; mirror R2-A §5.5)

- Cohort CSV byte-stable: 11 data rows + header + cohort_label column matching `r2d_vcp_adr_min_pct_sp1`.
- Audit JSON contains 11 flip records + source SHA-256 + size.
- Cohort.json fixture entries all carry composite_score >= 0.5 (canonical filter).
- Dispatch brief contains "v2_binding_variable_flips" + "selection-biased" strings (forward-binding lock against documentation drift).

---

## §6 Acceptance criteria

### §6.1 Functional

- [ ] Cohort CSV generated at `exports/research/cohorts/r2d_adr_min_pct_sp1.csv` (N unique rows where N is the unique-ticker count from 11 flips).
- [ ] Sibling audit JSON at `exports/research/cohorts/r2d_adr_min_pct_sp1.flips_audit.json` (11 raw flips + source SHA-256).
- [ ] pattern_cohort_evaluator smoke produces W primary verdicts for the 11-entry cohort.
- [ ] Cohort.json fixture at `tests/fixtures/research/r2d_adr_min_pct/cohort.json`.
- [ ] D2 6-ruleset harness invoked against new fixture; smoke artifact at `exports/research/r2d-adr-min-pct-backtest-<ISO>/`.
- [ ] Manifest `l2_lock_preserved: true` + `cohort_selection_method: v2_binding_variable_flips` + NEW `v2_binding_variable: vcp.adr_min_pct`.

### §6.2 Test scope

- [ ] 10-15 NEW R2-D fast tests at `tests/research/r2d_adr_min_pct/`.
- [ ] All D2 + R2-A + D1 + prior tests still green (cross-bundle pin verifier).
- [ ] `python -m pytest tests/research/r2d_adr_min_pct/ -q` exits 0.
- [ ] Broader `tests/research/ -m "not slow" -q` still green.

### §6.3 Discipline preservation

- [ ] ZERO Co-Authored-By footer drift (preserve ~553+ cumulative streak through `6f64f91`).
- [ ] ZERO production swing/ writes (R2-D reuses D2's existing CLI subcommand; NO new CLI needed).
- [ ] Schema v21 unchanged.
- [ ] ZERO new Schwab API calls (L2 LOCK; same as R2-A; reinforced via 2 NEW R2-D source-grep tests).
- [ ] ASCII discipline complete per gotcha #32 (declare scope explicitly; mirror R2-A `7.6 ASCII discipline preserved across all NEW R2-D files`).

### §6.4 Analytical deliverables

- [ ] `exports/research/r2d-adr-min-pct-backtest-<ISO>/` artifact directory (manifest.json + summary.md committed; results.csv excluded per project convention).
- [ ] `docs/r2d-adr-min-pct-cohort-backtest-findings-<ISO>.md` -- analytical narrative.
- [ ] `docs/r2d-adr-min-pct-cohort-backtest-return-report.md` -- return report mirroring R2-A's shape.
- [ ] 4-way cross-cohort comparison vs R2-A NEGATIVE + D2 EXPANDED PARTIAL POSITIVE + D2 Companion 2 PARTIAL POSITIVE + D1 NEGATIVE-strict MANDATED in findings.
- [ ] Verdict classification per D2 §6.5 (POSITIVE / PARTIAL POSITIVE / DIRECTIONAL / NEGATIVE / AMBIGUOUS) on the CANONICAL evaluation cohort (composite>=0.5 + recency<=365d).
- [ ] Bootstrap CI on E's R distribution per Amendment 5.3 methodology (10,000 resamples; seed=42).

### §6.5 Verdict classification (UNCHANGED from R2-A §6.5; gotcha #33 BINDING)

Apply D2 §6.5 thresholds to the canonical evaluation cohort (composite>=0.5 + recency<=365d):

- **POSITIVE**: at least 1 of {D, E, F} produces mean-R closed > 0 AND win-rate >= 35% AND >= 5 closed-and-profitable
- **PARTIAL POSITIVE**: at least 1 of {D, E, F} produces mean-R closed > 0 AND win-rate >= 25% AND >= 3 closed-and-profitable
- **DIRECTIONAL**: mean-R > 0 + N<3 closed-and-profitable
- **NEGATIVE**: ALL of {D, E, F} fail PARTIAL POSITIVE thresholds
- **AMBIGUOUS**: rankings across rulesets statistically indistinguishable

**Cross-cohort consistency assertion (UPDATED for R2-D with 3 prior cohort verdicts now BINDING):**

| R2-D E result | R2-A E result | D2 EXPANDED E result | Cross-cohort verdict | Implication |
|---|---|---|---|---|
| POSITIVE/PARTIAL POSITIVE | NEGATIVE | PARTIAL POSITIVE | R2-A NEGATIVE was tightness_days_required-SPECIFIC | E partially generalizes across V2 binding variables (mixed signal) |
| NEGATIVE | NEGATIVE | PARTIAL POSITIVE | **SYSTEMIC V2-binding-variable cohort-specific NEGATIVE** | Strong evidence that V2 selection produces fundamentally different P&L distribution than bias-free detection; E's mechanism does NOT generalize across V2 binding variables |
| AMBIGUOUS / DIRECTIONAL | NEGATIVE | PARTIAL POSITIVE | R2-D cohort too small to discriminate; weak evidence | Recommend R2-E (another V2 binding variable) OR temporal wait |
| INSUFFICIENT SAMPLE | NEGATIVE | PARTIAL POSITIVE | R2-D cohort yielded N<3 closed | Reduce composite threshold OR widen recency further (within canonical bounds per gotcha #33) |

---

## §7 Watch items + cumulative discipline (BINDING)

### §7.1 Cumulative discipline (33 gotchas BINDING for 41st cumulative validation onwards)

If Codex MCP review invoked, ALL 33 gotchas BINDING. **ESPECIALLY relevant per gotcha #33 BINDING (THIRD canonical application):**
- R2-D cohort is selection-biased (V2 OHLCV +11 watch->aplus filter; mirrors R2-A's +16 selection-biased mechanism on a different variable).
- Canonical evaluation cohort decision LOCKED at composite>=0.5 + recency<=365d (D2 Amendment 5 + R2-A Amendment 6 + R2-D MANDATORY for cross-comparability).
- If R2-D yields N<3 closed-and-profitable for any ruleset, verdict for that ruleset is INSUFFICIENT SAMPLE.

### §7.2 Per-dispatch watch items

- (a) **Cohort generation TIME COST**: V2 sensitivity drill-down parsing is small (~11 lines from 15K-line md); cohort CSV generation should be <5 min orchestrator-side. Parser robustness inherited from R2-A's R1-R5 Codex-driven hardening.
- (b) **D2 + R2-A harness REUSE VERBATIM**: assert `research/harness/w_bottom_ruleset_comparison/` files UNCHANGED AND `research/harness/r2a_tightness_days_required/` files UNCHANGED via parametrized byte-stability tests.
- (c) **Cohort overlap analysis**: enumerate R2-D ticker overlap with R2-A (7 tickers) + D2 (7 tickers) + D1 (10 tickers). The 11 R2-D flips MAY or MAY NOT share tickers with R2-A; this is methodologically informative.
- (d) **NEW tickers**: pre-flight archive verification; refresh stale via yfinance `period='max'` (R2-A pattern; ~30 min per stale ticker).
- (e) **Cross-comparison cardinality table**: 4-way comparison MANDATED in findings (R2-D + R2-A + D2 EXPANDED + D2 Companion 2 + D1).
- (f) **Codex MCP invocation per pre-dispatch operator-paired decision**: 41st cumulative C.C lesson #6 validation slot RESERVED.

### §7.3 Cross-comparison MANDATED in findings doc (4-way; load-bearing)

| Cohort | Definition | Size | E closed | E closed-and-profitable | E mean R | E lower CI | E verdict |
|---|---|---|---|---|---|---|---|
| D1 post-refresh (`131423Z`) | Hand-curated +67 watch->aplus from V2 OHLCV `vcp.tightness_range_factor=1.005`; recency<=60d | 12 | n/a (E not tested at D1) | n/a | n/a | n/a | NEGATIVE-strict via DK + TROX close_below_50d |
| D2 Companion 2 canonical | Bias-free S&P 500; composite>=0.5 + recency<=120d | 26 | 6 | 3 | +1.208R | +0.464R | PARTIAL POSITIVE (degenerate) |
| D2 EXPANDED Amendment 5 | Bias-free S&P 500; composite>=0.5 + recency<=365d | 71 | 10 | 5 | +1.220R | +0.753R | PARTIAL POSITIVE (6 of 7 statistical-defensibility tests PASS) |
| R2-A canonical | V2 binding-variable flips (`vcp.tightness_days_required +16`); composite>=0.5 + recency<=365d | 65 | 40 | 9 (22.5% wr) | -1.086R | -0.782R | NEGATIVE |
| **R2-D canonical** | **V2 binding-variable flips (`vcp.adr_min_pct +11`); composite>=0.5 + recency<=365d** | **TBD** | **TBD** | **TBD** | **TBD** | **TBD** | **TBD** |

### §7.4 Codex MCP decision (OPERATOR-PAIRED PRE-DISPATCH)

**Recommendation: invoke Codex MCP for the 41st cumulative C.C lesson #6 validation slot.** Rationale:
- R2-D is the SECOND V2-binding-variable cohort backtest; methodologically central to bounding the cohort-specific generalization claim
- Parser-robustness defenses inherited from R2-A's R1-R5 chain (5 NEW defenses; documented at R2-A return report §4) -- Codex may surface NEW defects in the R2-D variant or confirm convergence
- Codex caught REAL defects in R2-A's cohort_csv (silent under-extraction; hardcoded column positions; section-boundary bug; line-anchored heading regex; per-triple identity verification); the R2-D port could re-introduce variants
- Gotcha #33 third canonical application -- discipline LOCKED but verification expected

---

## §8 Commit cadence + return report

### §8.1 Commit cadence (~6-10 commits; mirror R2-A)

1. Cohort CSV generator + module constants (slice 1; enumerate the 11 flips + N tickers + register `R2D_VARIABLE_NAME = "vcp.adr_min_pct"`)
2. Cohort.json fixture + harness-reuse + L2-LOCK + cohort-validity tests (slice 2)
3. Codex R1+ fix bundles (if invoked; mirror R2-A's R1-R5 pattern)
4. Smoke artifact emission + commit
5. Findings doc + return report

### §8.2 Return report

Author at `docs/r2d-adr-min-pct-cohort-backtest-return-report.md` per R2-A return report shape (§1 mission summary / §2 implementation / §3 commit ledger / §4 Codex chain / §5 test status / §6 V1 simplifications + V2 candidates / §7 discipline preservation / §8 acceptance criteria checklist / §9 handoff to orchestrator).

---

## §9 Branch + worktree setup

```powershell
git checkout main
git pull origin main
git worktree add .worktrees/applied-research-r2d-adr-min-pct-cohort-backtest -b applied-research-r2d-adr-min-pct-cohort-backtest
cd .worktrees/applied-research-r2d-adr-min-pct-cohort-backtest
```

---

## §10 Do NOT

- Modify `research/harness/w_bottom_ruleset_comparison/` (REUSE verbatim; same as R2-A).
- Modify `research/harness/r2a_tightness_days_required/` (R2-A module set is FROZEN; byte-stability tests enforce).
- Refactor R2-A's `cohort_csv.py` into a shared generic (V2 candidate; OUT OF SCOPE for R2-D).
- Modify production `swing/` (the D2 CLI subcommand should work for R2-D by pointing to the new fixture).
- Add new rulesets (A-F unchanged from D2; no new variants).
- Add Co-Authored-By footer.
- Override D2 or R2-A smoke artifacts (R2-D goes in NEW dated subdirectory).
- Substitute alternative cohort filter to "find a winning ruleset" (per gotcha #33; third canonical application; discipline LOCKED).
- Apply different filter than D2 EXPANDED (composite>=0.5 + recency<=365d) to the canonical evaluation cohort -- cross-comparability with R2-A requires identical filter.

---

## §11 Pre-dispatch operator-paired decisions

### §11.1 Codex MCP invocation: YES (recommended)

Per §7.4 rationale. 41st cumulative C.C lesson #6 validation slot.

### §11.2 Variable selection: `vcp.adr_min_pct +11`

Selected per orchestrator next-largest-remaining ordering post-R2-A (V2 binding variables by max_delta_aplus: tightness_range_factor +75 -> tightness_days_required +16 -> **adr_min_pct +11** -> proximity_max_pct +5 -> orderliness_max_bar_ratio +1). Future R2-* dispatches would proceed left-to-right through remaining variables if pattern persists.

### §11.3 Architecture: sibling module strategy (NOT refactor)

Per §1.2 LOCK. R2-D creates its own `research/harness/r2d_adr_min_pct/` mirroring R2-A's structure. Common-parser refactor banked as V2 candidate.

---

*End of dispatch brief. Light dispatch ~4-6h implementer + ~1-2h Codex chain; tests whether R2-A's cohort-specific-NEGATIVE finding is UNIQUE to tightness_days_required OR SYSTEMIC across V2 binding variables. Cross-cohort 4-way consistency is the load-bearing finding; per-cohort verdict is secondary. Gotcha #33 third canonical application; discipline LOCKED.*

---

## Amendment 1 (2026-05-26; implementer ratification post Codex R1)

**Author:** R2-D implementer (Codex MCP adversarial review R1 disposition).

**Rationale:** Reconciles the brief's prescriptive sweep_point=1 against the V2 sensitivity smoke artifact's actual `+11 max_delta_aplus` binding signal, and pre-commits the canonical evaluation cohort's sample-size disposition per gotcha #33.

### A1.1 sweep_point reconciliation (was: §1.1 / §1.2 / §1.3 / §5.1 / §5.5 / §6.1 / §7.2)

The brief consistently stated "sweep_point=1" + "11 watch->aplus flips". Empirical inspection of the source artifact at `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md` shows:

- vcp.adr_min_pct summary table (line 116): `vcp.adr_min_pct | threshold_multiplicative | 2.0 | 16 | 1890 | 3672 | 0 | 11 | 569 | 0 | 88 | 0` -- **the +11 max_delta_aplus signal is at sweep_point=2.0** (NOT 1).
- vcp.adr_min_pct drill-down section at sweep_point=1: 15 watch->aplus flips (identical to R2-A's vcp.tightness_days_required cohort because adr_min_pct=1 is more relaxed than the +11 binding sweep_point).
- vcp.adr_min_pct drill-down section at sweep_point=2.0: EXACTLY 11 watch->aplus flips (matches the brief's stated 11-count contract).

The brief's count-based contract (11 flips matching the +11 binding signal) is the binding interpretation; the prescriptive sweep_point=1 is a brief-authoring error. The implementer uses **sweep_point=2.0** as the canonical R2-D sweep_point.

Artifact naming reflects this:
- Module: `research/harness/r2d_adr_min_pct/` (variable-name-derived; sweep_point-agnostic).
- Constant: `R2D_SWEEP_POINT = 2.0` (FLOAT-valued; differs from R2-A's int=1).
- Cohort CSV: `exports/research/cohorts/r2d_adr_min_pct_sp2_0.csv` (NOT `sp1.csv`).
- Cohort label: `r2d_vcp_adr_min_pct_sp2_0` (NOT `..._sp1`).
- Fixture: `tests/fixtures/research/r2d_adr_min_pct/cohort.json` (path unchanged; suffix sweep-agnostic).

All "sp1" references in §1.2 / §1.3 / §5.5 / §6.1 / §6.2 / §7.2 / §8.1 are SUPERSEDED by "sp2_0" naming.

### A1.2 Pre-commit: cohort-validity disposition (was: §6.5 + §7.1)

Per gotcha #33 cohort-validity-vs-verdict-criteria discipline (third canonical application; LOCKED):

The canonical evaluation cohort (composite>=0.5 + recency<=365d) for R2-D yields **N=4 W primary verdicts ALL from STNG** (post pattern_cohort_evaluator smoke at `exports/research/pattern-cohort-detection-20260526T160518Z/`; 1559 raw double_bottom_w verdicts -> 132 at composite>=0.5 -> 127 post 5-BD adjacency merge -> **4** post recency<=365d filter).

This is **well below the brief's expected N=50-200 range** (was: §7.3 R2-D row). Per gotcha #33:

- **PARTIAL POSITIVE thresholds** (>=3 closed-and-profitable AND mean-R closed > 0 AND win-rate >= 25%) require at least 3 closed-and-profitable per ruleset. With N=4 total + 4 STNG-only patterns, even the maximum possible PARTIAL POSITIVE outcome (4 of 4 triggered AND profitable across all 6 rulesets) is at the statistical-defensibility threshold.

- **SYSTEMIC NEGATIVE claim is FORBIDDEN** as a headline verdict against this cohort. A NEGATIVE outcome on N=4 STNG-only patterns cannot defensibly support the claim "R2-A's NEGATIVE generalizes across V2 binding variables." The valid finding is "R2-D cohort yields N=4; INSUFFICIENT SAMPLE for the cross-cohort-systemic claim."

- **POSITIVE / PARTIAL POSITIVE on N=4 STNG-only** would be a ticker-concentrated case study NOT a defensible "generalization across V2 binding variables" claim either; findings doc MUST disclose this concentration explicitly.

**Headline verdict for R2-D is bound to one of:**
- INSUFFICIENT SAMPLE (most likely outcome; the canonical disposition per gotcha #33 when N falls below the discriminating threshold)
- INSUFFICIENT SAMPLE -- DIRECTIONAL POSITIVE (if all 4 are profitable; case-study qualifier mandatory)
- INSUFFICIENT SAMPLE -- DIRECTIONAL NEGATIVE (if all 4 are unprofitable; case-study qualifier mandatory)

**INSUFFICIENT SAMPLE is the headline verdict in all three sub-cases** -- the DIRECTIONAL suffix is informational color, not a defense of the systemic claim.

### A1.3 Cross-cohort interpretation under N=4 (was: §6.5 table)

Updated cross-cohort consistency table interpretation:

| R2-A E result | R2-D E result | Cross-cohort verdict |
|---|---|---|
| NEGATIVE (canonical) | INSUFFICIENT SAMPLE (N=4) | R2-A's NEGATIVE neither confirmed nor refuted at the systemic level by R2-D. R2-D's thin substrate prevents the cross-cohort discrimination test from running. Next-arc operator decision: pivot to a different V2 binding variable with a thicker substrate (e.g., proximity_max_pct +5 or orderliness_max_bar_ratio +1) OR investigate WHY R2-D's W substrate is so thin (binding variable selection mechanism interacting with W-pattern incidence). |

The brief's §6.5 cross-cohort cells assuming N comparable to R2-A's 65 are NOT applicable to R2-D's actual N=4 substrate. The systemic-vs-cohort-specific research question is **DEFERRED** to a future R2-* dispatch against a thicker substrate.

### A1.4 Acceptance criteria modifications

- §6.4 fourth bullet: "Verdict classification per D2 §6.5..." now reads "Verdict classification per D2 §6.5 on the CANONICAL evaluation cohort (composite>=0.5 + recency<=365d); per A1.2 gotcha #33 pre-commit, headline verdict is INSUFFICIENT SAMPLE with DIRECTIONAL suffix."
- §6.5 cross-cohort consistency table: superseded by A1.3.

### A1.5 Disposition of brief sections referencing "sp1" / sweep_point=1

The following brief locations contain literal "sp1" / "sweep_point=1" / "sweep_point == 1" text that is technically inconsistent with the implementation but PRESERVED as the brief's authoring record (no edit-in-place per documentation discipline):

- §1.1 (line 53), §1.2 (lines 61, 65, 67), §1.3 (line 80), §5.1 (line 142), §5.5 (line 161), §6.1 (line 172), §7.2 (line 235).

All such references are SUPERSEDED by Amendment 1 §A1.1 above.

---

*End of Amendment 1.*
