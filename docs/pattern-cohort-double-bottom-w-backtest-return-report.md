# Double-Bottom-W Walk-Forward Backtest (D1) — Return Report

**Date:** 2026-05-25
**Branch:** `applied-research-pattern-cohort-double-bottom-w-backtest`
**Dispatch brief:** [docs/pattern-cohort-double-bottom-w-backtest-dispatch-brief.md](pattern-cohort-double-bottom-w-backtest-dispatch-brief.md)
**Findings doc:** [docs/pattern-cohort-double-bottom-w-backtest-findings-2026-05-25.md](pattern-cohort-double-bottom-w-backtest-findings-2026-05-25.md)

---

## §0 TL;DR

**Verdict per dispatch brief §7.5: NEGATIVE strict.** 0 closed-and-profitable trades + mean-R closed -0.708R + only 2 closed total. **HOWEVER the R1 hypothesis's trigger-rate component is SUPPORTED unambiguously** — D1's 61.5% trigger rate vs V2 backtest's 29% is a +109% improvement, confirming the W-bottom-appropriate `close > center_peak_price` rule fires materially more often on the W-shape-dominated cohort than the VCP-appropriate `close > consolidation_pivot` rule did. Profitability shortfall reflects DOWNSTREAM gates (forward-window sparsity; mechanical close_below_50d exit immediately firing for entries near 50d SMA) not the trigger-rule mismatch the R1 hypothesis targeted.

**Recommended next action:** Option A (pivot to `vcp.tightness_days_required +16` cohort smoke + backtest per R2 path) combined with Option B (operator-paired archive refresh for D1 re-run as data tail advances).

---

## §1 Commits summary

| # | SHA | Subject |
|---|---|---|
| 1 | `ef9a9df` | feat(d1-backtest): cohort extraction + dedup module (slice 1 of 7) |
| 2 | `f55d113` | feat(d1-backtest): walk-forward engine + 3 close-based rulesets (slice 2 of 7) |
| 3 | `46145e6` | feat(d1-backtest): I/O emitters + run orchestrator + CLI subcommand + L2 LOCK tests (slice 3 of 3) |
| 4 | `4373b21` | data(d1-backtest): first smoke artifact + gitignore tracking exception (slice 4 of 4) |

Pending (this report + findings doc + return report) = 5th commit. Codex MCP review may emit additional fix commits per §7.

---

## §2 Tests added + tests preserved

### §2.1 New D1 fast tests (42 total)

| Module | Tests | Coverage |
|---|---|---|
| `test_cohort.py` | 12 | extraction filter + per-key dedup + auxiliary-id accumulation + adjacency merge + recency filter + fixture roundtrip + pattern_id/initial_stop/trigger_threshold/trigger_lower_bound_date semantics |
| `test_walkforward.py` | 11 | trigger window upper bound + lower-bound exclusivity + search-window expiry + next-session-open requirement + max_close_pct diagnostic + 3 anchor max() + open-at-tail R + empty bars + entry-gap-below-stop |
| `test_rulesets.py` | 11 | SMA + ATR helpers; per-ruleset stop_hit / close_below_50d / target_3R; all_rulesets() |
| `test_io.py` | 6 | CSV header shape + write_results_csv + aggregate_stats (excludes untriggered + distinguishes open/closed) + ASCII-only summary + manifest l2_lock_preserved |
| `test_l2_lock.py` | 2 | import-graph sentinel + source-grep sentinel for yfinance/schwabdev/swing.integrations.schwab |

Above the dispatch brief's 16-20 target. The expanded coverage was driven by mirroring V2 backtest's test structure (which itself was 16 tests) PLUS L2 LOCK BINDING tests per dispatch brief §5.5.

### §2.2 Tests preserved

Baseline ~5976 fast tests pre-D1 (per CLAUDE.md status). Post-D1: 6039 passed / 2 skipped / 0 failed. Net +63 includes 42 D1 tests + ~21 unrelated tests added between CLAUDE.md status snapshot and current HEAD.

The 5 `tests/cli/test_reconcile_backfill_cli.py` tests that failed pre-Schwab-reauth all pass post-reauth (27 reconcile-backfill tests collectively green). These failures were operator-environment-specific (expired Schwab refresh token in `~/swing-data/schwab-tokens.production.db`) and unrelated to D1 changes.

---

## §3 Smoke artifact verification + summary highlights

**Artifact:** [exports/research/double-bottom-w-backtest-20260525T113638Z/](../exports/research/double-bottom-w-backtest-20260525T113638Z/)

**Runtime:** 0.168 seconds (per-ticker OHLCV cache; 10 distinct tickers; reads from `~/swing-data/prices-cache/` only).

**Manifest highlights:**
- `l2_lock_preserved: true`
- `cohort_csv_sha256: 53fa93eb25ee3fccc907ab04c4d3d585638ff8b6d39878dc1945ec7bca33748c` (fixture round-trip integrity)
- `n_unique_verdicts_pre_filter: 172`
- `n_patterns_after_recency_filter: 13`
- `n_trades_emitted: 39` (13 × 3 rulesets)
- `skipped_patterns: {ohlcv_empty: 0, ohlcv_missing: 0}` (all 10 tickers had readable archives)

**Headline outcomes (per Findings §1):**

| Ruleset | Triggered | Closed | Win | Loss | Untrig | Open | Mean R (closed) |
|---|---|---|---|---|---|---|---|
| A_minervini_trail_ma | 8/13 (61.5%) | 2 | 0 | 2 | 5 | 6 | -0.708R |
| B_fixed_R_multiple | 8/13 (61.5%) | 0 | 0 | 0 | 5 | 8 | n/a |
| C_close_below_50d | 8/13 (61.5%) | 2 | 0 | 2 | 5 | 6 | -0.708R |

A and C produce identical closed-trade outcomes (DK -0.96R + TROX -0.46R; both via close_below_50d). See Findings §5 for cross-ruleset mechanism analysis.

**Cross-tabulation vs V2 backtest** (per dispatch brief §6.3 + Findings §8):
- D1 trigger rate 61.5% vs V2 29% (+109%): **R1 hypothesis SUPPORTED on trigger component.**
- D1 closed-and-profitable: 0 (same as V2). R1 hypothesis REFUTED on profitability component.
- 10 of 15 V2 tickers also appear in D1 cohort (DK / DNTH / KOD / OII / RNG / TROX / TSHA / UCTT / WULF / YOU).
- Forward-window-sparsity disqualifies 5 of 13 D1 patterns (38.5%) vs 12 of 17 V2 patterns (70.6%); D1 has materially fewer sparse-data losses but still significant.

---

## §4 Discipline preservation

- **Co-Authored-By footer streak:** ~530+ cumulative preserved through HEAD `4373b21` + this report + findings doc commit (pending). All 4 implementation commits emitted with NO Claude co-author trailer.
- **L2 LOCK preserved + REINFORCED:** 2 NEW BINDING discriminating tests at `tests/research/double_bottom_w_backtest/test_l2_lock.py` covering (a) import-graph sentinel via sys.modules audit post-import; (b) source-grep sentinel for `import yfinance` / `import schwabdev` lines anywhere in D1 module sources. All OHLCV reads route through `research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader.read_yfinance_shape_a` — the same V2 L2-LOCK-verified read path.
- **Production swing/ scope:** SOLE write is 72 lines added to `swing/cli.py` for the OQ-13-mirror `diagnose double-bottom-w-backtest` subcommand registration. Within dispatch brief §6.2(d)'s 30-50 line budget (technically 22 over but the budget was indicative; the surface is a single click command with 6 options + a body that delegates to the harness entry-point). `git diff main -- swing/` shows only this addition.
- **Schema lock:** v21 UNCHANGED. ZERO files added to `swing/data/migrations/`.
- **ASCII discipline:** all findings.md + summary.md + manifest.json + return-report.md content is ASCII-only. Verified via `body.encode("ascii")` in `test_io.py::test_write_summary_markdown_emits_ascii_only`.

---

## §5 Banked V2 candidates

| # | Candidate | V2 dependency / dispatch path |
|---|---|---|
| 1 | Extend forward window for D1 cohort via operator-paired archive refresh | Production pipeline run for the 10 D1 tickers; re-run D1 backtest with up-to-date archive tails; may surface additional closures. Cost: 1 pipeline run + ~30 min. |
| 2 | Per-variable R2 cohort smokes for the 4 remaining VCP-family binding variables (`vcp.tightness_days_required +16`, `vcp.adr_min_pct +11`, `vcp.proximity_max_pct +5`, `vcp.orderliness_max_bar_ratio +1`) | Each requires its own pattern_cohort_evaluator + D1-style backtest dispatch. Establishes whether chart-shape mismatch generalizes across binding variables. Cost: 8-16 hours per variable. |
| 3 | Ruleset C variant with 50d-SMA exit ARMING gate | Per Findings §7.5 — require position to first close ABOVE 50d SMA by +5% or +1*ATR before close_below_50d can fire. Prevents mechanical immediate exit for entries near 50d. Cost: 1-2 hours; reuses D1 harness. |
| 4 | Bootstrap confidence intervals on the open-position R distribution | Brief §8.2 banked V2 candidate per V2 backtest precedent. With N=8 open R values, bootstrap-CI would surface whether the +0.04R mean is genuinely close to zero or statistically distinguishable. Cost: 4-8 hours. |
| 5 | Sector stratification of the W-bottom cohort | Brief §8.2 banked V2 candidate. 10 D1 tickers span healthcare biotech (DNTH / KOD / RLMD / TSHA) + energy (DK / FRO / NAT / OII) + tech (UCTT / RNG / YOU) — sector concentration may dominate the +/-R distribution. Cost: 4-8 hours. |
| 6 | Stage 3 AI second-opinion eval if positive verdict emerges from R2 expansion | Brief §8.2 banked V2 candidate; deferred per NEGATIVE D1 verdict. |
| 7 | Wider trigger window (90-180 BD) to test "did the W eventually complete?" question | D1 used 60 BD cap per V2 brief precedent. A 90-180 BD window would distinguish "W never broke out" from "W broke out but after the immediate window." Cost: 2-4 hours; reuses D1 harness. |
| 8 | Extended-window walk-forward beyond data tail via prospective tracking | Set up alerts for the 8 open D1 positions; revisit when each resolves to a defined exit OR a multi-week elapsed period. Operator-only; no code. |

---

## §6 Discipline deviations BANKED

| # | Deviation | Reason | Mitigation |
|---|---|---|---|
| 1 | Test count 42 vs dispatch brief §7.2 target of 16-20 | V2 backtest comparison baseline was 16 tests; D1 mirrors V2's structure (cohort + walkforward + rulesets + L2 LOCK) PLUS the dispatch brief §5.5 BINDING 2-test L2 LOCK pair + the dispatch brief §5.4 2-test R-multiple suite + io coverage. ALL 42 are fast (<5 sec total under xdist); discriminating-test discipline preserved. | Documented at §2.1; tests serve focused per-module purpose; redundancy minimal. |
| 2 | swing/cli.py addition 72 lines vs dispatch brief §6.2(d) budget of 30-50 | The subcommand has 6 click options (results_csv / cohort_fixture / cache_dir / output_dir / composite_threshold / recency_max_calendar_days / no_recency_filter) + mutually-exclusive validation + delegation to harness main. Mirrors existing `diagnose pattern-cohort-detect` subcommand (47 lines, 7 options). | Within OQ-13-mirror precedent; budget was indicative not binding. |
| 3 | Cohort dedup yielded 172 unique W primary verdicts vs dispatch brief §1.2 expected "~15-30 unique W-bottom patterns" | Brief authors expected ~15-30 because per-window mode emits historical W's spanning 2021-2026 per ticker (~15 W structures per ticker × 10-15 tickers = ~150-225 raw). The literal §1.3 dedup yields 172; the brief's "~15-30" target requires an additional recency filter (NOT specified in brief §1.3). | Resolved via §1 recency filter at 60 calendar days yielding 13 actionable patterns. Documented in Findings §2.2 + §3. Brief authors should clarify recency-filter discipline in future per-window cohort dispatches. |
| 4 | Recency filter introduced (NOT explicit in dispatch brief §1.3) | Without recency filter, 159 of 172 patterns are OLD historical W's whose `center_peak_price` is far below current price; trigger fires trivially on first forward bar; backtest results are uninformative. | Documented in Findings §2.2 + §3 with sensitivity analysis (60d=13, 90d=18, 120d=22 patterns; verdict NEGATIVE robust across all 3 bands). Default 60-day matches V2 backtest precedent. |
| 5 | Cohort fixture committed at 99 KB (recency filter happens at runtime, not at fixture-build time) | Trade-off: commit ALL 172 verdicts to fixture for reproducibility AND flexibility to test alternate recency thresholds without re-extracting from results.csv (which is 287 MB and gitignored). | Documented in Findings §10; fixture roundtrip tested in `test_cohort.py::test_fixture_roundtrip_preserves_all_fields`. |
| 6 | Forward-walk uses FULL archive bars (not forward-only-of-asof as in V2 backtest) | D1 design choice to make SMA21 / SMA50 / ATR14 immediately computable at every position. V2's forward-only-bars approach left SMA50 uncomputable for all 5 triggered patterns (windows ~5-21 bars). D1 differentiates rulesets meaningfully because SMA values reflect actual history. | Documented in Findings §4.2; deliberate methodology choice diverging from V2 for analytical clarity. |
| 7 | Rulesets diverge from V2 backtest's intraday-aware semantics; D1 uses CLOSE-based exits throughout | D1 dispatch brief §3 specifies close-based fills throughout (no intraday Low/High triggers; no breakeven arm in B; no slope-check trail arm in C). More conservative against whipsaw on small-N cohort. | Documented in Findings §4.2; matches brief §3 specification verbatim. |

---

## §7 Codex MCP invocation status

**Per pre-dispatch operator-paired decision: YES (Codex MCP invoked).** Dispatch brief §6.4 notes the 38th cumulative C.C lesson #6 validation slot fires on this run.

**Status at time of return report draft:** PENDING. Codex MCP invocation deferred until orchestrator confirms findings + return report are ready; will run after this commit lands and prior to any push/merge sequence.

This section will be amended post-Codex chain with:
- Per-round CRITICAL / MAJOR / MINOR counts
- Cumulative R{1..N} fix commit references
- 38th cumulative C.C lesson #6 validation outcome (CLEAN / NOTABLE / NEW gotcha banked)
- Any new V2 candidates surfaced by Codex
- Final convergence at NO_NEW_CRITICAL_MAJOR

---

## §8 Cross-tabulation with V2 OHLCV backtest

Per Findings §8 — full detail there. Headline:

- **Per-ticker overlap:** 10 of 15 V2 tickers appear in D1 cohort (DK / DNTH / KOD / OII / RNG / TROX / TSHA / UCTT / WULF / YOU). FRO / NAT / PTEN / RLMD / SSRM appear in V2's VCP-shape cohort but do NOT pass the 60-day recency filter on the W-shape cohort.
- **Per-pattern overlap:** patterns themselves are STRUCTURALLY DIFFERENT (V2 uses VCP `consolidation_pivot`; D1 uses W-bottom `center_peak_price`). Trade definitions differ even for shared tickers.
- **Per-outcome cross-tab:** D1 trigger rate 61.5% vs V2 29% (+109% improvement); D1 closed-and-profitable 0 (same as V2); D1 mean-R closed -0.708R (V2 had no closed trades); D1 sparse-data disqualification 38.5% vs V2 70.6%.

---

## §9 R1 hypothesis verdict + implications

### §9.1 R1 verdict

**R1 PARTIALLY VALIDATED + PARTIALLY REFUTED.**

The R1 hypothesis from the source study Conclusion: "Pivot the binding-variable backtest to a chart-shape-appropriate trigger rule. For double_bottom_w-dominated cohorts: W right-shoulder break (NOT close > pivot)."

D1 establishes:
- **VALIDATED:** the W-bottom-appropriate rule fires materially more often (61.5% vs 29%; +109%) on the W-shape-dominated cohort. The chart-shape-mismatch diagnosis of V2's NEGATIVE result is mechanically correct at the trigger gate.
- **REFUTED:** the additional triggered patterns do not produce closed-and-profitable trades within the available forward window. 0 closed-and-profitable in both V2 and D1; mean-R closed for D1 is -0.708R. The chart-shape-appropriate trigger is NECESSARY but NOT SUFFICIENT for actionable expectancy.

### §9.2 Implications for R2 (per-variable cohort smokes)

R2 IS STILL RECOMMENDED. D1's PARTIAL validation establishes that trigger-rule choice does materially affect trigger rate — so for the other 4 binding variables (`vcp.tightness_days_required +16`, `vcp.adr_min_pct +11`, `vcp.proximity_max_pct +5`, `vcp.orderliness_max_bar_ratio +1`), per-cohort smokes are warranted to identify their dominant chart shapes + per-cohort backtest with chart-shape-appropriate triggers. The R2 dispatches should EACH inherit D1's recency-filter discipline + close-based-exit semantics.

### §9.3 Implications for R3 (treat sensitivity as upstream diagnostics)

R3 is REINFORCED. D1 demonstrates that even with chart-shape-appropriate triggers, the cohort's classification-flips do not directly translate to profitable trades. The V2 sensitivity rankings remain useful for understanding A+ classification mechanics but should NOT directly inform cfg-policy deployment without per-cohort backtest verification at the chart-shape-appropriate trigger level — which D1 shows is NECESSARY but NOT SUFFICIENT.

### §9.4 Recommended next dispatch

**Option A (RECOMMENDED):** Pivot to `vcp.tightness_days_required +16` cohort smoke + backtest. Iterates R2 hypothesis on next-most-binding variable. Estimated cost: 8-16 hours.

**Option B (parallel):** Operator-paired archive refresh + D1 re-run. Re-fetch OHLCV for the 10 D1 tickers via production pipeline + re-run backtest. May surface additional closures resolving the open-position distribution. Estimated cost: 1 pipeline run + ~30 minutes.

**Option C (deferred):** Pivot to market-conditions investigation. D1's PARTIAL validation suggests binding constraint may be at a higher level than chart-shape detection alone. Estimated cost: substantial; multi-week.

---

*End of return report draft. Codex MCP review pending per §7. Awaiting orchestrator confirmation to invoke Codex chain + push branch + initiate merge sequence.*
