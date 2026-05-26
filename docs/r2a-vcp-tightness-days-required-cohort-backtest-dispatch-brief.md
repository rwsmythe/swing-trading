# R2-A Backtest: V2 OHLCV `vcp.tightness_days_required +16` Cohort 6-Ruleset Comparison — Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the R2-A backtest implementer. No prior conversation context.

**Mission:** Test whether Ruleset E's PARTIAL POSITIVE verdict from D2 (5 closed-and-profitable; +1.220R mean R; +0.753R 95% CI lower bound on bias-free recency-365d cohort) GENERALIZES to a DIFFERENT W-cohort definition — specifically the V2 OHLCV `vcp.tightness_days_required +16` binding variable cohort (15 watch->aplus flips at sweep_point=1 across 7 unique tickers; selection-biased per V2 sensitivity framework rather than bias-free per D2). Generate cohort substrate from V2 sensitivity smoke artifact; run D2's 6-ruleset comparison harness against it; classify verdict per dispatch brief §6.5 with gotcha #33 cohort-validity discipline.

**Workflow:** `copowers:executing-plans` skill (wraps `superpowers:test-driven-development` + Codex MCP adversarial review). Codex MCP invocation per pre-dispatch operator-paired decision (see §11; recommendation YES per D2 precedent).

**Branch:** `applied-research-r2a-tightness-days-required-cohort-backtest` — branches from main HEAD `2fa2b5a` (or later; reflects D2 Amendment 5 EXPANDED cohort + bootstrap re-run).

**Worktree:** `git worktree add .worktrees/applied-research-r2a-tightness-days-required-cohort-backtest applied-research-r2a-tightness-days-required-cohort-backtest`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Expected duration:** ~4-6h operator-paced + ~1-2h Codex chain. SHORTER than D2 because most infrastructure is reused; the NEW work is cohort generation from V2 sensitivity drill-down + cross-cohort comparison analysis.

---

## §0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/pattern-cohort-w-bottom-ruleset-comparison-findings-2026-05-25.md`** — D2 findings doc. Especially §11 Amendment 3 (canonical verdict reclassification) + §12 Amendment 4 (bootstrap CI) + §13 Amendment 5 (EXPANDED cohort + bootstrap re-run; N=5 closed E at +1.220R mean / +0.753R lower bound).

3. **`docs/pattern-cohort-w-bottom-ruleset-comparison-return-report.md`** — D2 return report. Especially §5 V2 candidates (#1 next-binding-variable cohort = THIS dispatch) + §7 Codex chain (3 rounds; 6M+9m converged) + §10 Amendment 3 orchestrator amendment.

4. **`docs/pattern-cohort-w-bottom-ruleset-comparison-dispatch-brief.md`** — D2 dispatch brief. **THIS dispatch is functionally a re-execution of D2's harness against a DIFFERENT cohort.** Reuse §2 entry rule + §3 6-ruleset specs + §4 output shape + §5 test scope + §6 acceptance criteria + §7 watch items + §8 verdict classification verbatim.

5. **`research/harness/w_bottom_ruleset_comparison/`** — D2 harness (5 modules). **REUSE VERBATIM** for R2-A. The only NEW code is the cohort-generation step that builds a cohort.json fixture from V2 sensitivity drill-down data.

6. **`exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.{csv,md}`** — V2 OHLCV sensitivity smoke artifact (full-63-eval-run reproduction; 5666 candidates; 88 OHLCV coverage skips). Contains the `vcp.tightness_days_required` per-sweep-point drill-down with 15 watch->aplus flip records at sweep_point=1 across 7 unique tickers.

7. **`reference/methodology/`** — Minervini Stage-2 framework (primary literature source per operator decision).

8. **`mcp__qullamaggie__*` MCP tools** — Qullamaggie reference for Ruleset F semantics (unchanged from D2).

9. **CLAUDE.md** gotchas #1-#33 — cumulative discipline. **ESPECIALLY relevant:**
   - **#33 (NEW)** cohort-validity-vs-verdict-criteria distinction. THIS dispatch's cohort is selection-biased (V2 OHLCV +16 watch->aplus filter; mirrors D1's operator-curated style). The verdict MUST be reported on this cohort + documented as "selection-biased parallel-evidence cohort to bias-free D2 cohort." Cross-comparison MANDATED.
   - **#28 + #29** OHLCV cache discipline (exemplar OHLCV provisioning; same as D2; verify pre-flight)
   - **#30** recency/filter/dedup semantic-ordering (inherit D2 discipline)
   - **#31** narrative artifact path/fact lag (post-fix sweep)
   - **#32** ASCII discipline scope clarity

---

## §1 Cohort generation procedure

### §1.1 Source: V2 OHLCV sensitivity drill-down

Source artifact: `exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md`. Drill-down section `### vcp.tightness_days_required` (~lines 5000-6000 of the md; precise grep at execution time).

Filter from drill-down: `sweep_point=1` AND `old_bucket=watch` AND `new_bucket=aplus`. Expected: **15 flip records** across **7 unique tickers** (FRO / KOD / NAT / OII / RLMD / SEI / TROX).

### §1.2 Cohort fixture generation

Build cohort.json fixture at `tests/fixtures/research/r2a_tightness_days_required/cohort.json`. Fixture shape MUST mirror D2's cohort.json (one entry per unique W primary verdict with: ticker, anchor_asof_date, max_observed_asof_date, trough_1_date, trough_1_price, center_peak_date, center_peak_price, trough_2_date, trough_2_price, pivot_price, composite_score, geometric_score, template_match_score, window_count, observed_asof_dates).

To populate the W structural-evidence fields, run `pattern_cohort_evaluator` against the 7-ticker / 15-flip cohort CSV. Use the V2 sensitivity drill-down's `(ticker, asof_date)` pairs as input.

```powershell
# Step 1: Generate cohort CSV from V2 sensitivity drill-down
# (NEW orchestrator helper script at tmp/r2a-cohort-csv-from-v2-sensitivity.py)

# Step 2: Run pattern_cohort_evaluator against the +16 sweep_point=1 cohort
python -m swing.cli diagnose pattern-cohort-detect `
  --cohort-csv exports/research/cohorts/r2a_tightness_days_required_sp1.csv `
  --db "$env:USERPROFILE/swing-data/swing.db" `
  --output-dir exports/research/ `
  --pattern-class-filter double_bottom_w
```

Expected runtime: ~1-2 min (15 cohort entries; small).

### §1.3 Cohort scope analysis pre-backtest

After step 2, the implementer MUST report in findings doc §2.X:
- Number of W primary verdicts emitted (raw)
- Number passing composite>=0.7 (D2 brief default)
- Number passing composite>=0.5 + recency<=365d (EXPANDED filter per D2 Amendment 5)
- Number passing composite>=0.5 + recency<=120d (Companion 2 filter)
- Cross-comparison with D1's 10-ticker cohort + D2's bias-free 7-ticker cohort

This pre-backtest analysis enables the verdict-classification cohort decision per gotcha #33: bind the canonical evaluation cohort to the FILTER that yields N>=3 closed-and-profitable in D2 precedent terms.

### §1.4 Pre-flight checks before backtest

Same as D2 dispatch brief §1.3. Verify exemplar tickers have deep archives + new cohort tickers (FRO / SEI; NEW vs D1+D2) have current archives in `~/swing-data/prices-cache/`. For FRO + SEI specifically: if missing or stale, refresh via the same `tmp/d1-cohort-archive-refresh.py` pattern (or equivalent script for these 2 tickers).

---

## §2 Entry rule (UNCHANGED from D2)

Per D2 dispatch brief §2. REUSE verbatim:
- Trigger: first daily close > `center_peak_price` after effective_asof
- Entry: next-session OPEN
- Initial stop: ruleset-dependent (D + F use trough_2 × 0.99; E uses max(trough_2 × 0.99, entry × 0.92))
- Trigger search window: effective_asof + 1 BD lower, effective_asof + 60 BD upper

---

## §3 Six rulesets — UNCHANGED from D2

Per D2 dispatch brief §3.1-3.6. REUSE D2 implementations verbatim. No new rulesets.

---

## §4 Output / analytical surface

Per D2 dispatch brief §4. Smoke artifact path: `exports/research/r2a-tightness-days-required-backtest-<ISO>/`.

27-column CSV (post-Codex-R3 schema); summary.md with per-ruleset stats + cross-ruleset comparison; manifest.json with cohort SHA-256 + provenance fields.

NEW analytical sections in summary.md / findings doc:
- Cross-cohort comparison with D2 Companion 2 (N=26 / canonical) + D2 EXPANDED (N=71 / recency<=365d) + D1 post-refresh (N=12 / hand-curated)
- Per-ticker overlap: which of the 5 D1-overlap tickers (KOD / NAT / OII / RLMD / TROX) produce SAME outcome direction in R2-A as in D1 or D2?
- Statistical-defensibility tier per D2 Amendment 5.5 (mean R / win-rate / count / CI bound / P-positive / sign test / N>=10)

---

## §5 Discriminating tests (~10-15 fast tests)

LIGHTER test scope than D2 because the harness is reused verbatim. Focus on:

### §5.1 Cohort fixture generation (~3-5 tests)

- Parse V2 sensitivity drill-down + filter to sweep_point=1 + watch->aplus; assert 15 entries / 7 unique tickers.
- Generate cohort.json fixture; verify shape matches D2 fixture; verify round-trip preservation.

### §5.2 Cohort-validity cross-check (~3 tests; NEW per gotcha #33)

- Cohort selection bias is RECORDED in manifest; manifest field `cohort_selection_method` enum `{bias_free_universe, v2_binding_variable_flips, operator_curated}` set to `v2_binding_variable_flips`.
- Findings doc § asserting canonical evaluation cohort definition + cross-comparison vs D2 (bias-free) + D1 (operator-curated) is mandatory.

### §5.3 Backtest harness reuse (~2-3 tests)

- D2 harness modules invoke unchanged from R2-A driver; assert NO modification to `research/harness/w_bottom_ruleset_comparison/` files.
- Manifest correctly reflects new cohort source path + provenance vs D2.

### §5.4 L2 LOCK (~2 tests; inherited from D2)

Inherit D2's source-grep + import-graph sentinel tests by reference; one NEW test at `tests/research/r2a_tightness_days_required/` ensures NEW R2-A modules don't introduce schwab/yfinance imports.

---

## §6 Acceptance criteria

### §6.1 Functional

- [ ] Cohort CSV generated from V2 sensitivity drill-down at `exports/research/cohorts/r2a_tightness_days_required_sp1.csv` (15 entries; 7 tickers).
- [ ] pattern_cohort_evaluator smoke produces W primary verdicts for the 15-entry cohort.
- [ ] Cohort.json fixture generated at `tests/fixtures/research/r2a_tightness_days_required/cohort.json`.
- [ ] D2 6-ruleset harness invoked against new fixture; smoke artifact at `exports/research/r2a-tightness-days-required-backtest-<ISO>/`.
- [ ] Manifest `l2_lock_preserved: true` + `cohort_selection_method: v2_binding_variable_flips`.

### §6.2 Test scope

- [ ] 10-15 NEW fast tests at `tests/research/r2a_tightness_days_required/`.
- [ ] All D2 + D1 + prior tests still green.
- [ ] `python -m pytest tests/research/ -m "not slow" -q` exits 0.

### §6.3 Discipline preservation

- [ ] ZERO Co-Authored-By footer drift (preserve ~544+ cumulative streak through `2fa2b5a`).
- [ ] ZERO production swing/ writes (R2-A uses D2's existing CLI subcommand; NO new CLI needed).
- [ ] Schema v21 unchanged.
- [ ] ZERO new Schwab API calls (L2 LOCK).
- [ ] ASCII discipline complete per gotcha #32 (declare scope explicitly).

### §6.4 Analytical deliverables

- [ ] `exports/research/r2a-tightness-days-required-backtest-<ISO>/` artifact directory.
- [ ] `docs/r2a-tightness-days-required-cohort-backtest-findings-<ISO>.md` — analytical narrative.
- [ ] Cross-cohort comparison vs D2 Companion 2 + D2 EXPANDED + D1 post-refresh MANDATED in findings doc.
- [ ] Verdict classification per D2 §6.5 (POSITIVE / PARTIAL POSITIVE / NEGATIVE / AMBIGUOUS) on the CANONICAL evaluation cohort (apply same filter that D2 used; recommend composite>=0.5 + recency<=365d EXPANDED filter for consistency with D2 Amendment 5).
- [ ] Bootstrap CI on E's R distribution (mirrors Amendment 5.3); cross-bootstrap with D2 EXPANDED N=5 to test cross-cohort consistency.

### §6.5 Verdict classification (R2-A version per gotcha #33 cohort-validity discipline)

Apply D2 §6.5 thresholds to the canonical evaluation cohort (recommended: composite>=0.5 + recency<=365d EXPANDED filter):

- **POSITIVE**: at least 1 of {D, E, F} produces (a) mean-R closed > 0 across all closed trades AND (b) win-rate >= 35% AND (c) at least 5 closed-and-profitable trades.
- **PARTIAL POSITIVE**: at least 1 of {D, E, F} produces (a) mean-R closed > 0 AND (b) win-rate >= 25% AND (c) at least 3 closed-and-profitable trades.
- **DIRECTIONAL** (NEW; sub-threshold of PARTIAL POSITIVE): mean-R > 0 + N<3 closed-and-profitable. Includes acknowledgment that cohort size limits inference.
- **NEGATIVE**: ALL of {D, E, F} fail PARTIAL POSITIVE thresholds.
- **AMBIGUOUS**: rankings across rulesets statistically indistinguishable.

Cross-cohort consistency assertion (per gotcha #33):
- If R2-A E reaches POSITIVE/PARTIAL POSITIVE AND D2 E PARTIAL POSITIVE → consistency confirmed; arc verdict strengthens
- If R2-A E NEGATIVE AND D2 E PARTIAL POSITIVE → inconsistency; E may be cohort-specific not robust
- If R2-A E AMBIGUOUS → N inadequate; cohort enrichment / temporal expansion needed

---

## §7 Watch items + cumulative discipline (BINDING)

### §7.1 Cumulative discipline (33 gotchas BINDING for 40th cumulative validation onwards)

If Codex MCP review invoked, ALL 33 gotchas BINDING. **ESPECIALLY relevant per gotcha #33 BINDING**:
- The R2-A cohort is selection-biased (V2 OHLCV +16 watch->aplus filter); MUST document cohort selection method in manifest + findings doc.
- The canonical evaluation cohort decision MUST be made BEFORE backtest execution (apply same filter as D2 EXPANDED: composite>=0.5 + recency<=365d).
- If cohort yields N<3 closed-and-profitable for any ruleset, verdict for that ruleset is INSUFFICIENT SAMPLE (not "fall through to looser filter to find a winner").

### §7.2 Per-dispatch watch items

- (a) **Cohort generation TIME COST**: V2 sensitivity drill-down parsing is small (~15 lines from 15K-line md); cohort CSV generation should be <5 min orchestrator-side.
- (b) **D2 harness REUSE VERBATIM**: assert `research/harness/w_bottom_ruleset_comparison/` files UNCHANGED via test (verifies code reuse not re-implementation).
- (c) **D2 + D1 cohort overlap with R2-A**: enumerate per-ticker overlap; document.
- (d) **NEW tickers FRO + SEI**: pre-flight archive verification; refresh via yfinance period="max" if missing/stale.
- (e) **Cross-comparison cardinality**: R2-A 7 tickers vs D2 7 tickers vs D1 10 tickers; ZERO ticker-overlap with D2; 5-ticker overlap with D1 (KOD/NAT/OII/RLMD/TROX). This is methodologically informative.
- (f) **Codex MCP invocation per pre-dispatch operator-paired decision**: 40th cumulative C.C lesson #6 validation slot RESERVED.

### §7.3 Cross-comparison MANDATED in findings doc

Per gotcha #33 + the broader R2-A research question (does E's PARTIAL POSITIVE generalize to a different cohort definition?):

| Cohort | Definition | Size | E closed | E mean R | E lower CI |
|---|---|---|---|---|---|
| D1 post-refresh (`131423Z`) | Hand-curated +67 watch->aplus from V2 OHLCV `vcp.tightness_range_factor=1.005`; recency<=60d | N=12 | n/a (E not tested at D1) | n/a | n/a |
| D2 Companion 2 canonical | Bias-free S&P 500; composite>=0.5 + recency<=120d | N=26 | 3 winners | +1.208R | +0.464R |
| D2 EXPANDED | Bias-free S&P 500; composite>=0.5 + recency<=365d | N=71 | 5 winners | +1.220R | +0.753R |
| **R2-A canonical** | **V2 OHLCV +16 watch->aplus; sweep_point=1; composite>=0.5 + recency<=365d** | **TBD** | **TBD** | **TBD** | **TBD** |

Cross-validation interpretation:
- D2 EXPANDED is bias-free (good); R2-A is selection-biased (different signal)
- If R2-A E also PARTIAL POSITIVE → E generalizes across cohort selection methods
- If R2-A E NEGATIVE → E is cohort-specific to bias-free S&P 500 W's

### §7.4 Codex MCP decision

OPERATOR-PAIRED PRE-DISPATCH decision. Recommendation: invoke Codex MCP for the 40th cumulative C.C lesson #6 validation slot given:
- New cohort generation pipeline (small but novel)
- Cross-cohort analytical surface (new dimension vs D2)
- Gotcha #33 first-application (cohort-validity-vs-verdict-criteria discipline is BINDING for THIS dispatch)

---

## §8 Commit cadence + return report

### §8.1 Commit cadence

LIGHTER cadence than D2 because harness is reused (~6-10 commits):
1. Cohort CSV generator test + impl (slice 1)
2. pattern_cohort_evaluator smoke + cohort fixture extractor (slice 2)
3. R2-A driver (mirror D2 CLI subcommand if needed; OR reuse D2 subcommand with new fixture path)
4. Smoke artifact emission + commit
5. Findings doc + return report
6. Codex MCP review chain fix bundles (if invoked)

### §8.2 Return report

Author at `docs/r2a-tightness-days-required-cohort-backtest-return-report.md` per D2 return report shape.

---

## §9 Branch + worktree setup

```powershell
git checkout main
git pull origin main
git worktree add .worktrees/applied-research-r2a-tightness-days-required-cohort-backtest -b applied-research-r2a-tightness-days-required-cohort-backtest
cd .worktrees/applied-research-r2a-tightness-days-required-cohort-backtest
```

---

## §10 Do NOT

- Modify `research/harness/w_bottom_ruleset_comparison/` (REUSE verbatim).
- Modify production `swing/` (the D2 CLI subcommand should work for R2-A by pointing to the new fixture).
- Add new rulesets (A-F unchanged from D2; no new variants).
- Add Co-Authored-By footer.
- Override D2's existing smoke artifacts (R2-A goes in NEW dated subdirectory).
- Substitute alternative cohort filter to "find a winning ruleset" (per gotcha #33).
- Skip the cross-comparison vs D2 + D1 in findings.
- Apply D1's "hand-curation" or "no-recency-filter" to the canonical evaluation cohort for R2-A — use the same EXPANDED filter (composite>=0.5 + recency<=365d) that D2 Amendment 5 ratified as canonical.

---

*End of dispatch brief. Light dispatch ~4-6h implementer + ~1-2h Codex chain; tests whether D2's PARTIAL POSITIVE for Ruleset E generalizes to a DIFFERENT cohort definition (V2 OHLCV binding variable selection vs D2's bias-free S&P 500 detection). Cross-cohort consistency is the load-bearing finding; per-cohort verdict is secondary.*
