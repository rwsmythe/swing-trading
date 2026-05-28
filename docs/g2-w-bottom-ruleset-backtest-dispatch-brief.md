# G2 -- W-Bottom-Derived Ruleset Backtest Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the G2 W-bottom-ruleset backtest implementer. No prior conversation context.

**Mission:** Test the operator's joint hypothesis: expand the candidate population (via V2-binding-variable threshold relaxations identified at V2-mechanic Turn H) AND apply a ruleset SPECIFICALLY derived for the W-bottom shape from the available reference library, in pursuit of expanded actionable tickers WHILE maintaining or improving portfolio performance ($ earned per unit time). The existing 6-ruleset comparison (A_minervini_trail_ma through F_qullamaggie_momentum_burst) included E_oneil_cup_with_handle_measured_move as the closest structural near-miss to a W-bottom ruleset, but NO ruleset derived FROM W-bottom literature has been tested. R2-A's NEGATIVE on E was driven by asymmetric P&L (winners +0.512R, losers -1.55R) -- a stop-placement failure mode. W-bottom-literature rulesets handle stop placement + volume confirmation differently and could change the verdict.

**Critical methodological contribution:** Introduce a **9-metric scorecard** (expectancy in R, win rate, avg_win_R, avg_loss_R, profit factor, trigger conversion rate, median time-in-trade, open-at-data-tail count, estimated $ per period at $7500-floor sizing) as the headline backtest output. Replace any single-metric verdict-gating (win-rate>=25%, mean-R>0, etc.) with the scorecard. Headline interpretation is narrative across the 9 metrics; gotcha #33 banned-verdict-terms LOCK preserved.

**Workflow:** `copowers:executing-plans` skill (wraps `superpowers:test-driven-development` + Codex MCP adversarial review). Codex MCP YES per Sec 7 (44th cumulative C.C lesson #6 validation slot RESERVED).

**Branch:** `applied-research-g2-w-bottom-ruleset-backtest` -- branches from main HEAD `b371261` (V2-mechanic housekeeping commit; reflects 35 cumulative CLAUDE.md gotchas BINDING).

**Worktree:** `git worktree add .worktrees/applied-research-g2-w-bottom-ruleset-backtest applied-research-g2-w-bottom-ruleset-backtest`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Expected duration:** ~5-8h implementer + ~2-4h Codex chain. Scope is smaller than V2-mechanic because (a) substrates are REUSED VERBATIM (no cohort extraction); (b) ruleset construction follows existing A-F template; (c) NEW methodological surface is the 9-metric scorecard + derived $-per-period synthesis.

---

## Sec 0 Read first (in this order)

1. **THIS BRIEF end-to-end.**

2. **`docs/v2-selection-mechanic-analysis-findings-2026-05-26.md`** + **`research/studies/2026-05-26-v2-selection-mechanic-analysis.md`** -- Turn H V2-mechanic findings. Key carryover: V2 substrates are ENRICHED for W-pattern productivity per ticker (D_filt 7.2x-70x baseline 0.138) but SMALL in absolute substrate size (T<=15). If a W-specific ruleset improves win/loss vs E, the expanded V2 population is HIGH-QUALITY per ticker AND directly responsive to the original "raise the count" goal.

3. **`docs/r2a-tightness-days-required-cohort-backtest-findings-20260526.md`** Sec 2-4 -- R2-A NEGATIVE on E + asymmetric P&L analysis. **Critical context: R2-A's failure mechanism was avg_loss_R = -1.55R (~50% larger magnitude than winners +0.512R). A W-specific ruleset with TIGHTER stop placement could materially improve expectancy even if win-rate stays flat.**

4. **`docs/pattern-cohort-w-bottom-ruleset-comparison-findings-2026-05-25.md`** Amendment 5 -- D2 EXPANDED N=71 ruleset E result on bias-free baseline (PARTIAL POSITIVE). E's bias-free success vs R2-A NEGATIVE is the cohort-specificity finding bounded by Amendment 6.

5. **`research/harness/w_bottom_ruleset_comparison/`** -- existing 6-ruleset comparison harness. **REUSE VERBATIM**; G2 adds NEW rulesets G/H/I as siblings to A-F. Asserted via byte-stability tests inherited from R2-D.

6. **`tests/fixtures/research/r2a_tightness_days_required/cohort.json`** (N=65) + **D2 EXPANDED N=71 cohort fixture** (path verified at slice 0; mirror D2 Amendment 5 source). **REUSE VERBATIM** as the substrate inputs.

7. **`reference/methodology/`** -- methodology source-of-truth library. Operator-paired triage at Sec 11 selects WHICH 3 W-bottom rulesets to derive from this library.

8. **`reference/Future Work/QuantEcon/external-references.md`** -- Lo-Mamaysky-Wang (2000) citation if implementer-selected as one of the 3 derived rulesets.

9. **CLAUDE.md gotchas #1-#35** -- cumulative discipline. **ESPECIALLY relevant for G2:**
   - **#35** substrate density metric disambiguation (NEW; this dispatch is the FIRST canonical application post-banking; any narrative quoting prior-arc anchors MUST cite metric definitions)
   - **#33** cohort-validity-vs-verdict-criteria (BANNED terms PARTIAL POSITIVE / NEGATIVE / POSITIVE in scorecard output; descriptive metrics only)
   - **#31** narrative artifact path/fact lag (post-fix sweep MANDATORY)
   - **#32** ASCII discipline scope clarity (declared scope per gotcha #32; all NEW Python + Markdown + JSON + CSV ASCII-only)
   - **#26** OHLCV archive bar-content TEMPORAL mutation (L6-style caveat for forward-walk metrics)
   - **#28+#29** OHLCV cache discipline (pre-flight verify; archive-miss raises ERROR not fetches)

---

## Sec 1 Investigation methodology

### Sec 1.1 Joint hypothesis under test

**H_joint:** A W-bottom-derived ruleset applied to a V2-binding-variable-expanded population produces NET-POSITIVE portfolio performance (positive expectancy in R AND positive estimated $ per period at canonical sizing), in a way that the existing A-F rulesets do not on the same population.

Two preconditions:
- **Population expansion is real:** confirmed via V2 sensitivity SUMMARY TABLE (+75 / +16 / +11 / +5 / +1 candidates per universe scan; verified per gotcha #34 in R2-A + R2-D + V2-mechanic dispatches).
- **Per-ticker substrate is W-pattern-productive:** confirmed via V2-mechanic Turn H D_filt 7.2x-70x baseline.

The remaining open question is whether **the right ruleset choice** can convert that population expansion into expectancy-positive trade outcomes. This dispatch tests that directly.

### Sec 1.2 Ruleset family construction (3 NEW W-bottom rulesets G/H/I)

The implementer constructs THREE new rulesets in `research/harness/w_bottom_ruleset_comparison/rulesets/` (or analogous existing location alongside A-F), each derived from a NAMED canonical reference work. Operator-paired triage at Sec 11 selects which 3.

**Default proposal (operator may override at Sec 11):**

- **G_bulkowski_double_bottom** -- Bulkowski's *Encyclopedia of Chart Patterns* (2nd ed.). Entry: close above center_peak with breakout volume > 30% above 20-bar volume mean. Stop: below trough_2's low (e.g., `trough_2_price - 0.01 * trough_2_price`, i.e., 1% buffer; TIGHTER than E's max(trough_2 * 0.99, entry * 0.92)). Target: measured-move = (center_peak - min(trough_1, trough_2)) projected up from center_peak. Failure: close below trough_2 (no time-stop in V1).

- **H_oneil_double_bottom_base** -- O'Neil *How to Make Money in Stocks*, "Double Bottom" as a Stage 2 base variant. Entry: close above pivot (= center_peak) with volume > 40% above 50-bar volume mean. Stop: 7-8% below pivot (= same as E's entry * 0.92 arm). Target: same measured-move as G. Failure: close below 50d MA OR -8% below pivot (whichever fires first).

- **I_edwards_magee_classical_double_bottom** -- Edwards & Magee *Technical Analysis of Stock Trends*. Entry: close above center_peak with volume confirmation (breakout-bar volume > 1.5x rally-bar-from-trough_2 volume). Stop: below the LOWER of the two troughs (= min(trough_1_price, trough_2_price) - 1% buffer). Target: measured-move (same as G). Failure: close below stop. THROWBACK-AWARE variant: if first close > center_peak occurs but next 2 sessions retrace into [trough_2, center_peak] then re-break, treat the FIRST break as entry; do NOT re-enter on the second break.

**Operator triage at Sec 11 may substitute:** Disciplined Swing Trader PDF W-specific guidance; Qullamaggie MCP-server-queried W-pattern guidance; or other reference-library rulesets.

**Each ruleset MUST be encoded as a standalone module file** (e.g., `g_bulkowski_double_bottom.py`) mirroring the structure of existing E/F. Each emits the same Trade dataclass shape (entry_date, entry_price, exit_date, exit_price, exit_reason, r_multiple, etc.) for downstream scorecard consumption.

### Sec 1.3 Substrate enumeration (REUSE VERBATIM)

Two primary substrates (no new cohort extraction):

- **R2-A canonical cohort:** `tests/fixtures/research/r2a_tightness_days_required/cohort.json` (N=65 W primary verdicts; 7 unique tickers FRO/KOD/NAT/OII/RLMD/SEI/TROX). Existing R2-A backtest established 22.5% win-rate / -1.086R mean R closed on E. G2's primary substrate; tests whether W-specific rulesets convert R2-A's NEGATIVE to net-positive expectancy.

- **D2 EXPANDED N=71:** D2's bias-free S&P 500 cohort (path verified at slice 0; mirror D2 Amendment 5 source-of-truth). Existing D2 backtest established +1.220R mean R closed on E across 5 closed-and-profitable. G2's cross-cohort consistency substrate; tests whether W-specific rulesets maintain D2's E success.

**Optionally (operator triage at Sec 11):** D1 hand-curated +67 substrate (V2 tightness_range_factor expansion; D1 backtest established 17 patterns / 5 triggered / 0 closed at backtest time). Decision deferred to Sec 11.

**R2-D N=4 EXCLUDED:** per gotcha #33 cohort-validity discipline + V2-mechanic Turn H profile tag INSUFFICIENT(T=4); too thin for the G2 9-metric scorecard to yield defensible numbers.

### Sec 1.4 9-metric scorecard definition (NEW methodological contribution)

For EACH (ruleset, substrate) cell, the scorecard reports nine metrics:

| # | Metric | Definition | Why it matters |
|---|---|---|---|
| 1 | **expectancy_R** | sum(R per closed trade) / N_closed = mean R closed | The headline per-trade expectation in R units |
| 2 | **win_rate** | N(R > 0 closed trades) / N_closed | Already standard; one of operator's two named metrics |
| 3 | **avg_win_R** | mean(R) over closed-and-profitable trades | Already standard; second of operator's two named metrics |
| 4 | **avg_loss_R** | abs(mean(R)) over closed-and-unprofitable trades | The missing lever; R2-A's failure mechanism (winners +0.512R vs losers -1.55R) is the canonical example |
| 5 | **profit_factor** | sum(R from winners) / abs(sum(R from losers)) | Robust to asymmetric distributions; >1.0 indicates net-positive aggregate even with low win-rate |
| 6 | **trigger_conversion_rate** | N_triggered / N_patterns | How many candidates actually convert to entered positions; D1's 5/17 vs R2-A's 62/65 demonstrate substrate-recency sensitivity |
| 7 | **median_time_in_trade_sessions** | median(exit_date - entry_date in trading sessions) over closed trades | Capital cycling rate; faster cycling means more trades per period at fixed capital |
| 8 | **open_at_tail_count** | N(trades still open at data tail) / N_triggered | Unresolved fraction; bounds the closed-trade-based metrics' completeness |
| 9 | **estimated_dollar_per_period** | N_triggered_per_year x expectancy_R x R_dollar_size_at_$7500_floor | The synthesis: how much $ per year if deployed at operator's $7500 floor + 1% risk-per-trade ($75 per R; configurable in run.py) |

**Estimated_dollar_per_period derivation:**

```python
# Per substrate; computed in scorecard.py
R_DOLLAR_SIZE_AT_7500_FLOOR = 75.0  # = 0.01 * 7500
# N_triggered_per_year extrapolates the substrate's trigger count to an annualized rate
# based on the substrate's effective evaluation window (asof_date span; documented in fixture)
N_triggered_per_year = (N_triggered / substrate_window_days) * 365
estimated_dollar_per_period = N_triggered_per_year * expectancy_R * R_DOLLAR_SIZE_AT_7500_FLOOR
```

**Substrate_window_days** is computed from the cohort fixture's earliest to latest asof_date; this is a deliberate normalization that lets cross-substrate dollar-per-period comparisons be apples-to-apples. **Document the normalization assumption explicitly in findings doc Sec 5 as L-style caveat:** the estimate assumes constant trigger rate over the year; real-world conditions vary by market regime.

**Cohort-validity discipline at scorecard layer (gotcha #33 BINDING):** the scorecard is METRIC-ONLY. NO categorical verdict labels (PARTIAL POSITIVE / NEGATIVE / POSITIVE) emitted by the scorecard. Headline interpretation is narrative across the 9 metrics. The findings doc may emit DESCRIPTIVE narrative (e.g., "ruleset G achieves positive expectancy on R2-A substrate with avg_loss tighter than E by 47% but reduced win-rate by 4 pp") but NEVER the banned terms.

### Sec 1.5 Cross-ruleset consistency check (cohort-validity discipline applied)

Per gotcha #33 third canonical application LOCK from R2-D: the scorecard must not be substituted across cohort definitions. Each ruleset's per-substrate scorecard is its own data point; the cross-cohort comparison (R2-A vs D2 EXPANDED) is INFORMATIONAL not verdict-determining.

If a W-specific ruleset achieves POSITIVE expectancy on R2-A AND maintains POSITIVE expectancy on D2 EXPANDED, that's a DESCRIPTIVE finding that the ruleset is robust across cohort definitions. If it achieves POSITIVE on one but NEGATIVE on the other, that's a cohort-specificity finding (mirrors D2 Amendment 6 + R2-A Sec 4 + R2-D Amendment 1 precedent).

### Sec 1.6 What's explicitly NOT in scope

- **No new cohort extraction.** R2-A + D2 EXPANDED + (optional) D1 substrates REUSED VERBATIM via byte-stability tests.
- **No modification of A-F rulesets.** A-F LOCKED via byte-stability tests inherited from R2-A + R2-D + V2-mechanic precedent.
- **No new V2-binding-variable analysis.** V2-mechanic Turn H completed that analysis; G2 consumes its findings.
- **No production swing/ writes.** L2 LOCK preserved + REINFORCED via NEW source-grep tests parametrized over the NEW G2 module set.
- **No new Schwab API calls.**
- **No verdict terminology** (PARTIAL POSITIVE / NEGATIVE / POSITIVE) in scorecard output (gotcha #33 BINDING).
- **No substrate substitution** to make a ruleset "look better" (gotcha #33 third canonical application).
- **No headline verdict synthesis** that overrides the 9-metric scorecard (the scorecard IS the headline).

---

## Sec 2 Ruleset construction details

### Sec 2.1 G_bulkowski_double_bottom

Module: `research/harness/w_bottom_ruleset_comparison/rulesets/g_bulkowski_double_bottom.py` (sibling to existing E + F module locations; implementer verifies exact path at slice 0).

Entry logic (canonical Bulkowski):
- First close > center_peak_price (post `effective_asof_date + 1 BD` per existing harness convention)
- AND breakout_bar_volume > 1.3 * trailing_20_bar_mean_volume
- Entry price = close of breakout bar
- Entry date = breakout bar date

Stop logic (TIGHT; the key differentiator from E):
- `stop_price = trough_2_price - 0.01 * trough_2_price` (1% buffer below trough_2 low)
- NO entry-relative arm (unlike E's max(trough_2 * 0.99, entry * 0.92))
- The tightness is intentional; Bulkowski emphasizes "the pattern fails if price closes below the second trough"

Target logic (canonical measured-move):
- `pattern_height = center_peak_price - min(trough_1_price, trough_2_price)`
- `target_price = center_peak_price + pattern_height`
- Exit at first close >= target_price

Failure logic:
- Close < stop_price -> exit at next-bar open (with realistic slippage assumption per existing harness)
- Time-stop: NONE in V1 (Bulkowski does not specify a time-stop; could be V2 extension)

Discriminating tests at slice 1 (mirror R2-A + R2-D test patterns):
- Synthetic W fixture with known anchors -> assert entry/stop/target prices
- Edge case: trough_2 break BEFORE breakout above center_peak -> assert no entry, pattern recorded as "invalidated_pre_breakout"
- Edge case: gap-through-target -> assert exit at target_price (NOT gap close; document as conservative assumption)
- Edge case: gap-through-stop (gap-down opens below stop) -> assert exit at gap-open price
- Volume requirement test: breakout-bar volume = 1.2x mean -> assert NO entry; = 1.3x mean -> assert entry; = 1.4x mean -> assert entry

### Sec 2.2 H_oneil_double_bottom_base

Module: `h_oneil_double_bottom_base.py`.

Entry logic:
- First close > pivot_price (= center_peak_price) with volume > 1.4 * 50-bar_mean_volume
- Entry price = close of breakout bar

Stop logic (PIVOT-RELATIVE; same as E's entry * 0.92 arm):
- `stop_price = entry_price * 0.92` (8% below entry)

Target logic:
- Same as G: measured-move from center_peak + pattern_height

Failure logic:
- Close < stop_price (= -8% from entry) -> exit at next-bar open
- Close < 50-bar SMA -> exit at next-bar open (O'Neil's stage-2-break invalidation)
- First to fire wins

Discriminating tests:
- Same patterns as G
- 50d MA break test: synthetic post-entry sequence with close crossing below 50d SMA -> assert exit on that bar's close (or next open per harness convention)

### Sec 2.3 I_edwards_magee_classical_double_bottom

Module: `i_edwards_magee_classical_double_bottom.py`.

Entry logic (Edwards & Magee classical with throwback awareness):
- First close > center_peak_price AND breakout-bar volume > 1.5 * (rally_volume_from_trough_2)
- WHERE `rally_volume_from_trough_2` = mean volume between trough_2_date and breakout_bar_date - 1
- Entry price = close of breakout bar
- THROWBACK-AWARE: if next 2 bars after entry retrace into the [trough_2, center_peak] zone then close back above center_peak, the FIRST break is the canonical entry (no re-entry on second break)

Stop logic (LOWER-TROUGH-RELATIVE):
- `stop_price = min(trough_1_price, trough_2_price) - 0.01 * min(trough_1, trough_2)`
- Wider than G (which uses trough_2 only) when trough_1 < trough_2

Target logic:
- Same measured-move as G + H

Failure logic:
- Close < stop_price -> exit at next-bar open

Discriminating tests:
- Patterns as above
- Volume comparison test: rally_volume_from_trough_2 = 1.0M, breakout_volume = 1.4M -> NO entry; breakout_volume = 1.6M -> entry
- Throwback test: synthetic post-entry sequence with bar2 close in [trough_2, center_peak], bar3 close > center_peak -> assert no re-entry; original entry preserved
- Lower-trough test: trough_1 = 50, trough_2 = 52 -> stop based on trough_1 (49.50); confirm correct

### Sec 2.4 Universal harness extension surface

Existing `research/harness/w_bottom_ruleset_comparison/` includes A-F as parallel modules + a `run.py` orchestrator. G2 ADD pattern:
- 3 NEW ruleset modules at `rulesets/g_*.py` + `rulesets/h_*.py` + `rulesets/i_*.py` (or whatever the existing A-F file convention is; implementer verifies at slice 0)
- NEW `scorecard.py` module computing the 9-metric scorecard per (ruleset, substrate) cell
- EXTEND `run.py` to invoke A-F + G + H + I against the substrates AND emit the 9-metric scorecard as `scorecard.csv` per substrate
- EXTEND `manifest.json` schema to include scorecard rows AND extracted methodology version (`g2_version: "1.0"`)

The A-F modules MUST remain byte-stable. The implementer verifies via 6 byte-stability tests inherited from R2-D's precedent.

---

## Sec 3 Output / analytical surface

### Sec 3.1 Smoke artifact directory (NEW)

**Path:** `exports/research/g2-w-bottom-ruleset-backtest-<TS>/`

Contents:
- `manifest.json` -- run timestamp; ruleset versions; substrate SHA-256s; canonical filter parameters; ZERO Schwab API call assertion; ZERO production swing/ writes assertion
- `summary.md` -- human-readable run summary
- `scorecard.csv` -- the 9-metric scorecard per (ruleset, substrate) cell; (3 new + 6 existing) x (2-3 substrates) = 18-27 rows
- `per_trade_detail.csv` -- per-(ruleset, substrate, trade) detail rows for forensic analysis
- `narrative_synthesis.md` -- per-ruleset narrative interpretation across the 9 metrics; per-substrate cross-ruleset comparison; CROSS-COHORT consistency check; descriptive labels only (NO verdict terms)

### Sec 3.2 Findings doc (NEW)

**Path:** `docs/g2-w-bottom-ruleset-backtest-findings-<DATE>.md`

Structure (mirrors R2-A + R2-D + V2-mechanic findings):
- Sec 1 Headline finding (narrative; descriptive)
- Sec 2 Per-ruleset 9-metric scorecard (3 new rulesets across 2-3 substrates)
- Sec 3 Cross-ruleset comparison on the headline substrate (R2-A)
- Sec 4 Cross-substrate consistency check (R2-A vs D2 EXPANDED per Sec 1.5)
- Sec 5 Methodological caveats + L-style limitations (incl. gotcha #26 archive bar-content TEMPORAL mutation; gotcha #35 prior-arc-anchor citations)
- Sec 6 Joint hypothesis assessment (H_joint test result + interpretation)
- Sec 7 V2 candidates + future-arc enumeration
- Sec 8 Codex MCP chain summary

### Sec 3.3 Return report (NEW)

**Path:** `docs/g2-w-bottom-ruleset-backtest-return-report.md`. Mirror R2-D return report shape per existing precedent.

---

## Sec 4 Discriminating tests

Estimated test count: ~60-100 fast tests.

### Sec 4.1 Per-ruleset tests (G + H + I; ~12-20 tests each = ~40-60 tests)

For each new ruleset:
- Entry-logic unit tests (canonical case + edge cases per Sec 2.1-2.3)
- Stop-logic unit tests
- Target-logic unit tests
- Failure-logic unit tests
- Trade dataclass shape tests (round-trip serialization compat with existing E/F)
- Volume-confirmation tests (per ruleset's volume rules)

### Sec 4.2 Scorecard tests (~15-25 tests)

- 9 metric arithmetic correctness tests (synthetic trade lists with known per-metric values)
- estimated_dollar_per_period derivation tests (verify $-amount = N_triggered_per_year * expectancy_R * R_DOLLAR_SIZE)
- Edge case: 0 closed trades -> expectancy_R = None (NOT 0; NOT divide-by-zero); win_rate = None; etc.
- Edge case: 0 triggered -> trigger_conversion_rate = 0.0; estimated_dollar_per_period = 0.0
- Edge case: 0 losses -> profit_factor = None or sentinel (per implementer choice; document in scorecard.py)
- Cross-ruleset comparison test: synthetic 2-ruleset, 1-substrate input -> assert correct scorecard rows + correct ordering

### Sec 4.3 Cohort-validity + cumulative discipline tests (~10-15 tests)

- L2 LOCK source-grep: parametrize over NEW G2 module set (rulesets + scorecard); assert ZERO `schwabdev` / `yfinance` / `swing.integrations.schwab` imports
- ASCII discipline test: all NEW files encode("ascii") cleanly (per gotcha #32 declared-scope)
- Gotcha #33 banned-terms test: parse narrative_synthesis.md output for synthetic backtest input; assert ZERO occurrences of "PARTIAL POSITIVE" / "NEGATIVE" / "POSITIVE" (case-insensitive substring + word-boundary)
- Gotcha #35 prior-arc-anchor citation test: any narrative referencing R2-A / R2-D / D2 / V2-mechanic anchors MUST cite the metric definition; verify via regex in findings doc draft
- Byte-stability tests for existing A-F rulesets (6 tests; mirror R2-D precedent)
- Schema v21 LOCK test (no migrations test)
- R2-A + D2 EXPANDED cohort fixture identity tests (re-verify against canonical SHA + N counts)

### Sec 4.4 Cumulative regression test arithmetic (per `feedback_verify_regression_test_arithmetic`)

For each scorecard arithmetic test: compute the expected output under BOTH the canonical formula AND a deliberately-buggy alternative; assert the test distinguishes them. Example: expectancy_R test with input [+1, +1, -1, -1, -1] (5 trades; 2 wins; 3 losses; mean=-0.2). Canonical formula yields -0.2; a buggy "win-rate divided by total" formula would yield 0.4; the test must assert -0.2 specifically (not "exists" or "is_finite").

---

## Sec 5 Acceptance criteria

### Sec 5.1 Functional

- [x] 3 NEW ruleset modules at the harness location (G + H + I)
- [x] 1 NEW scorecard module computing the 9 metrics
- [x] 1 NEW smoke artifact directory at `exports/research/g2-w-bottom-ruleset-backtest-<TS>/`
- [x] scorecard.csv with 18-27 rows (3 new + 6 existing rulesets x 2-3 substrates)
- [x] per_trade_detail.csv for forensic analysis
- [x] narrative_synthesis.md per-ruleset interpretation
- [x] findings doc + return report

### Sec 5.2 Test scope

- [x] ~60-100 NEW fast tests; `pytest tests/research/g2_w_bottom_ruleset/ -q` exits 0
- [x] All existing A-F ruleset tests still green (byte-stability)
- [x] All R2-A + R2-D + D2 + V2-mechanic tests still green (cross-arc byte-stability)
- [ ] Broader project fast suite: deferred for orchestrator-side verification

### Sec 5.3 Discipline preservation

- [x] ZERO Co-Authored-By footer drift
- [x] ZERO production `swing/` writes
- [x] Schema v21 unchanged (no migrations)
- [x] L2 LOCK preserved + REINFORCED via parametric source-grep tests over NEW G2 module set
- [x] ZERO new Schwab API calls
- [x] ASCII discipline complete (declared scope per gotcha #32)
- [x] Sibling-module strategy LOCK preserved (G/H/I are NEW siblings to A-F; A-F not modified)
- [x] Gotcha #33 banned-verdict-terms LOCK enforced in scorecard + narrative output

### Sec 5.4 Analytical deliverables

- [x] 9-metric scorecard per (ruleset, substrate) cell
- [x] Per-substrate cross-ruleset comparison (R2-A: A-F vs G-I; D2 EXPANDED: same)
- [x] Cross-substrate consistency check (per-ruleset R2-A vs D2 EXPANDED)
- [x] Joint hypothesis H_joint assessment (does G2 enable expanded-population + W-specific-ruleset combination to achieve positive expectancy?)
- [x] Operator decision support: which ruleset (if any) is worth shipping to production via cfg-amendment

### Sec 5.5 Cumulative discipline

- [x] CLAUDE.md gotchas #1-#35 fully BINDING
- [x] Gotcha #35 FIRST canonical application post-banking (prior-arc-anchor citation discipline; substrate density metric disambiguation in narrative output)
- [x] 44th cumulative C.C lesson #6 validation slot consumed
- [x] Pre-Codex review applies all 19 cumulative expansion candidates

---

## Sec 6 Watch items + cumulative discipline

(a) **Substrate REUSE VERBATIM:** R2-A + D2 + V2-mechanic byte-stability tests inherited.

(b) **No new OHLCV fetches at runtime:** substrate characterization is NOT in G2 scope; forward-walk uses CURRENT archive via existing harness `read_or_fetch_archive` (or equivalent legacy reader path). Archive freshness is operator-paired pre-flight if needed.

(c) **Gotcha #33 third canonical application reinforced:** no PARTIAL POSITIVE / NEGATIVE / POSITIVE in scorecard or narrative output. The 9-metric scorecard's headline interpretation is narrative across metrics; categorical labels are DESCRIPTIVE substrate characterization (e.g., "G achieves positive expectancy on R2-A" is descriptive; "G is POSITIVE on R2-A" uses banned term).

(d) **Gotcha #35 FIRST canonical application post-banking:** any narrative citing R2-A's "22.5% win-rate" or D2's "+1.220R mean R" or V2-mechanic's "D_filt 7.2x-70x baseline" MUST cite the metric definition (composite_filter spec; recency filter; per-ticker vs per-cohort denominator). The discriminating test at Sec 4.3 enforces this.

(e) **Codex MCP invocation:** YES per Sec 7. 44th C.C lesson #6 validation slot RESERVED. Pattern mirrors R2-A 5-round + R2-D 2-round + V2-mechanic 5+2-round chains.

(f) **9-metric scorecard methodological honesty:** the scorecard's `estimated_dollar_per_period` is a DERIVED estimate under explicit assumptions (constant trigger rate; $7500 floor; 1% R-sizing). The findings doc Sec 5 caveats this. The scorecard's true value is the 8 RAW metrics; the derived $ amount is a synthesis for portfolio-impact intuition.

(g) **R2-A asymmetric P&L is the canonical failure mode under test:** G's tight-stop placement is the most direct intervention. If G achieves higher avg_loss_R (less negative) than E without crushing win-rate, the joint hypothesis gains evidence.

(h) **Pre-Codex review expansions #1-#19 applied:** including the NEW gotcha #35 first canonical application (prior-arc-anchor metric-definition cross-reference). For any narrative quotation from R2-A / R2-D / D2 / V2-mechanic, verify the metric definition matches the implementer's computed metric definition.

---

## Sec 7 Codex MCP decision

**INVOKE.** 44th cumulative C.C lesson #6 validation slot RESERVED.

Recommended invocation sequence:
- After Slice 5 ship (rulesets + scorecard + smoke + findings draft)
- Round 1: full scope (3 NEW rulesets + scorecard + smoke + narrative synthesis + findings)
- Subsequent rounds: address MAJOR + CRITICAL findings in-place; bank MINOR per cumulative pattern
- Convergence: NO_NEW_CRITICAL_MAJOR
- Document chain summary in return report Sec 8

Pre-Codex review checklist (apply ALL 19 cumulative candidates):
1. hardcoded duplicate surface guard widening
2 + 17 + 19. brief-vs-actual-production-function-signature + call-graph + postponed-annotation
3. schema-CHECK + Python-constant + dataclass-validator paired + semantic-contract
4 + 18 + 20. SQL skeleton column verification (N/A for G2; no new SQL)
5. cross-section spec inventory grep
6. V1-completeness audit (per scorecard metric)
7. cross-row semantic SCOPE audit (per ruleset, per substrate)
8 + 22. per-counter-accumulation (scorecard arithmetic)
9. form-render anchor lifecycle (N/A)
10. architecture-location audit (rulesets in correct sibling location)
11 + 23. dataclass attribution metadata + taxonomy propagation (per-ruleset enum if added)
12. sibling-route audit (N/A)
13 / 21. cumulative regression cascade in fix loops
14. recency/filter/dedup semantic-ordering (scorecard arithmetic robust to substrate-window edge cases)
15. narrative artifact path/fact lag (POST-FIX SWEEP MANDATORY per gotcha #31)
16. ASCII discipline scope clarity (declared scope explicit)
17. brief-prescription cross-table verification (gotcha #34; N/A here)
18 / 19. (covered above)
**NEW: gotcha #35 first canonical application** (prior-arc-anchor metric-definition citation)

---

## Sec 8 Commit cadence + return report

Estimated 8-14 commits. Suggested slice structure:

- **Slice 1:** G_bulkowski_double_bottom module + tests (~22 tests; entry/stop/target/failure logic + edge cases)
- **Slice 2:** H_oneil_double_bottom_base module + tests (~22 tests)
- **Slice 3:** I_edwards_magee_classical_double_bottom module + tests (~22 tests including throwback edge case)
- **Slice 4:** Scorecard module + tests (~20 tests; 9-metric arithmetic + edge cases + estimated_dollar_per_period derivation)
- **Slice 5:** Harness extension (run.py invokes A-F + G + H + I; emits scorecard.csv + per_trade_detail.csv + narrative_synthesis.md) + smoke artifact + cohort-validity + L2 LOCK tests (~15 tests)
- **Slice 6:** Findings doc + Codex MCP chain
- **Slice 7:** Codex MCP fix bundle(s)
- **Slice 8:** Return report + post-fix narrative sweep

Return report template at `docs/g2-w-bottom-ruleset-backtest-return-report.md` (mirror R2-D return report shape).

---

## Sec 9 Branch + worktree setup

```powershell
git fetch origin main
git checkout -b applied-research-g2-w-bottom-ruleset-backtest main
git worktree add .worktrees/applied-research-g2-w-bottom-ruleset-backtest applied-research-g2-w-bottom-ruleset-backtest
cd .worktrees/applied-research-g2-w-bottom-ruleset-backtest
python -m swing.cli --help   # sanity check
```

Branch base: `b371261` (main HEAD at V2-mechanic housekeeping ship).

---

## Sec 10 Do NOT

- Re-litigate the LOCKED gotcha #33 / #34 / #35 disciplines
- Modify production `swing/`
- Modify V1 persisted state
- Trigger Schwab API calls
- Modify existing A-F rulesets OR the R2-A / D2 / R2-D / V2-mechanic substrate fixtures (byte-stability assertions BINDING)
- Emit verdict terminology (PARTIAL POSITIVE / NEGATIVE / POSITIVE / SUFFICIENT-as-a-verdict-not-a-tag) in scorecard or narrative output
- Substitute alternative cohort filter (canonical filter held FIXED on all substrates)
- Add Co-Authored-By footer to ANY commit
- Author the 9-metric scorecard as a SINGLE CATEGORICAL HEADLINE (the scorecard IS the headline; narrative interpretation is across-metrics; gotcha #33 third canonical application LOCK)
- Use `--no-verify` on commits
- Skip pre-Codex Expansion #1-#19 application (19 cumulative candidates BINDING; #35 is the FIRST canonical application post-banking)
- Author another orchestrator-handoff brief (Turn H ownership continues until G2 ship or context exhaustion)

---

## Sec 11 Pre-dispatch operator-paired decisions

**Q1 -- Ruleset selection (3 rulesets to derive from the reference library):**

Default proposal at Sec 1.2: G_bulkowski / H_oneil_double_bottom_base / I_edwards_magee_classical.

Operator may substitute or extend:
- Disciplined Swing Trader PDF W-bottom guidance (operator's first framework reference)
- Qullamaggie MCP-server-queried W-pattern variant (run `mcp__qullamaggie__query_trading_rules` at slice 0 for W-related rules; if Qullamaggie's framework includes a W-specific rule, derive ruleset)
- Lo-Mamaysky-Wang (2000) academic geometric variant (5-day forward measurement; not a tradeable ruleset per se but useful as academic baseline)
- Other reference library selections

**Q2 -- Substrate inclusion:**

Default proposal at Sec 1.3:
- R2-A canonical N=65 (primary substrate; R2-A NEGATIVE on E is the failure mode under test)
- D2 EXPANDED N=71 (cross-cohort consistency substrate; D2 PARTIAL POSITIVE on E is the success baseline)

Operator may include:
- D1 hand-curated +67 (V2 tightness_range_factor expansion substrate; D1 backtest established 17 patterns / 5 triggered / 0 closed; broader population coverage)

**Q3 -- Codex MCP:** YES per Sec 7 default. Operator may override.

**Q4 -- Scorecard $-amount basis:** $7500 floor + 1% risk-per-trade = $75 per R. Operator may override (e.g., actual balance $1300; different risk-per-trade fraction).

Operator-side decisions are LOCKED at dispatch time; deviations require return-trip to orchestrator.

---

*Note: the 'End of G2 W-bottom-ruleset backtest dispatch brief' end-marker (originally located here) is now PRECEDED by the 'Brief Amendments' section below (banked during Codex MCP pre-smoke chain R1-R4). The 'End of' marker has been moved to AFTER the amendments so the amendments are read as part of the locked brief, not as a stale appendix. See R5 MINOR #1 closure.*

---

## Brief Amendments (banked during implementation per gotcha #34 + Codex MCP adversarial-critic feedback)

### Brief Amendment 1 -- D2 EXPANDED substrate actual N=42 (NOT N=71)

**Source:** Codex MCP pre-smoke chain Round 1 MAJOR #2 finding.

**Issue:** Brief Sec 1.3 + Sec 1.5 state 'D2 EXPANDED N=71' citing D2 Amendment 5 source-of-truth (`docs/pattern-cohort-w-bottom-ruleset-comparison-findings-2026-05-25.md` Amendment 5.2). At dispatch baseline (D2 cohort fixture SHA `9075ac66d70401a19f11c06b681d859d3a5fbcd16e373e282c4db991bd6cc40c`), applying the brief-locked filter (composite>=0.5 + recency<=365d + 5-BD adjacency merge) actually yields N=42, NOT N=71. The cohort fixture has drifted since D2 Amendment 5 was originally run (likely a regenerate-cohort pass updated `max_observed_asof_date` timestamps for some verdicts, shifting them out of the 365d recency window).

**Resolution:** Per gotcha #34 (brief-prescription cross-table verification): the SHA-locked fixture + brief-locked filter yields the AUTHORITATIVE count. Brief's stated N=71 was a stale snapshot. The G2 dispatch proceeds against the actual N=42 substrate.

**Implementation evidence:**
- `tests/research/g2_w_bottom_ruleset/test_locks.py::test_d2_expanded_filter_yields_actual_n_against_real_cohort_fixture` LOCKS `D2_EXPANDED_ACTUAL_N=42` as regression-test constant.
- `research/harness/g2_w_bottom_ruleset_backtest/run.py` substrate label is `'d2_expanded'` (no embedded stale count); runtime `substrate_summary.n_filtered` surfaces the actual count.
- `filter_spec` text emitted in `manifest.json` substrates_summary cites both brief's stated N=71 + actual count for forensic clarity.

### Brief Amendment 2 -- entry/exit price semantic CONFIRMED brief-literal (Codex R1 CRITICAL #2 closure)

**Source:** Codex MCP pre-smoke chain Round 1 CRITICAL #2 finding.

**Issue:** Initial implementation used the existing harness's entry-at-next-bar-open + stop-exit-at-same-bar-close convention (mirroring RulesetE). Codex R1 flagged this as a brief LOCK violation: brief Sec 2.1 line 146-147 / Sec 2.2 line 176-177 / Sec 2.3 line 200-201 specify entry at the TRIGGER BAR'S CLOSE with entry date = trigger bar's date; brief Sec 2.1 line 160 / Sec 2.2 line 185-186 / Sec 2.3 line 211 specify stop / SMA-break exit at NEXT-BAR OPEN.

**Resolution:** Implementation switched to brief-literal semantic:
- `walkforward_ghi.walk_forward_with_trigger_predicate`: entry at trigger bar's close; entry_date = trigger bar's date.
- NEW `DeferredExit(reason)` action type in walkforward_ghi.py; rulesets G/H/I return DeferredExit for stop / close_below_50d exits; engine resolves exit_idx_canonical = i+1 (next-bar open) OR i (data-tail fallback) and assigns ALL of exit_price + exit_date + days_held from exit_idx_canonical for coherent forensic detail.
- Data-tail fallback (no bar i+1) emits status='open' + reason suffix '_pending_at_tail' (Codex R3 MAJOR #1 closure; unresolved trade per brief Sec 1.4 metric #8 'Unresolved fraction').

**Methodological consequence:** G/H/I now have GENUINELY DIFFERENT execution semantics from A-F (entry-at-trigger-close vs entry-at-next-bar-open; deferred next-bar-open exits vs same-bar-close exits). The 9-metric scorecard surfaces this divergence as a methodology-comparison feature, NOT a bug. The findings doc will note the execution-semantic divergence as a methodological caveat for cross-ruleset interpretation.

### Brief Amendment 3 -- target measured-move formula = center_peak + height (PATTERN-ANCHORED; NOT entry-relative)

**Source:** Codex MCP pre-smoke chain Round 1 CRITICAL #1 finding.

**Issue:** Initial implementation used `target_price = entry_price + pattern_height` (entry-anchored; mirrored existing RulesetE's convention). Brief Sec 2.1 line 156 / Sec 2.2 / Sec 2.3 explicitly LOCK `target_price = center_peak_price + pattern_height` (PATTERN-ANCHORED -- the measured-move is a property of the W pattern at the neckline, not of the operator's entry price).

**Resolution:** All 3 rulesets (G/H/I) `init_state()` updated to use `verdict.center_peak_price + pattern_height`. Diverges from existing RulesetE convention for literature fidelity (Bulkowski / O'Neil / Edwards-Magee canonical measured-move). Discriminator test asserts target = 70.0 (pattern-anchored, center_peak=60 + height=10) explicitly rejecting 72.0 (entry-anchored, entry=62 + height=10).

### Brief Amendment 4 -- brief Sec 2.1 internal inconsistency on 1.3x volume boundary

**Source:** Codex MCP pre-smoke chain Round 1 MAJOR #1 finding.

**Issue:** Brief Sec 2.1 line 145 specifies `breakout_bar_volume > 1.3 * trailing_20_bar_mean_volume` (STRICT `>`; 1.3x exactly should be REJECTED). Brief Sec 2.1 line 168 specifies in the discriminating-test sketch: `breakout-bar volume = 1.3x mean -> assert entry` (treats 1.3x exactly as ADMITTED; `>=`).

**Resolution:** ACCEPTED-with-rationale: implementation honors the SPEC LINE (145) with strict `>`; line 168 was a discriminating-test sketch with boundary error. Test `test_g_trigger_predicate_rejects_at_or_below_1_3x_volume` asserts strict `>` semantic. Documented as a brief internal inconsistency.

---

*End of G2 W-bottom-ruleset backtest dispatch brief (including Brief Amendments 1-4 above). Mission: test the joint hypothesis (V2-expanded population + W-bottom-derived ruleset = positive portfolio expectancy at acceptable trade frequency). Introduces 9-metric scorecard (expectancy_R + win_rate + avg_win_R + avg_loss_R + profit_factor + trigger_conversion_rate + median_time_in_trade + open_at_tail_count + estimated_dollar_per_period) as the headline output. Replaces single-metric verdict-gating with narrative across the scorecard. Sibling-module strategy continues; A-F + substrates LOCKED via byte-stability; gotcha #33 banned-verdict-terms LOCK preserved. 35 cumulative CLAUDE.md gotchas BINDING for 44th cumulative C.C lesson #6 validation slot. NEW gotcha #35 FIRST CANONICAL APPLICATION post-banking. ~576+ cumulative ZERO Co-Authored-By trailer drift to preserve.*
