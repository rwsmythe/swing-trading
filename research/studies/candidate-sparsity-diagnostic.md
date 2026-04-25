# Candidate-Sparsity Diagnostic

**Date:** 2026-04-24
**Companion to:** Session 2c evidence summary ([`./earnings-proximity-exclusion-results.md`](earnings-proximity-exclusion-results.md))
**Status:** Diagnostic — no production-code recommendations.
**Question motivating the diagnostic:** Why is the production A+ rate (~0.5 % per ticker-day, Session 2a observation: 2 / 400 ticker-days on the operator's Finviz-filtered universe) ~120× higher than the Session 2c replay rate (0.0042 % per ticker-day on SPX+NDX, $100k stylized capital)?

---

## Hypotheses tested

This diagnostic is scoped to test the three hypotheses below. Hypotheses 4–6 from `docs/tranche-c-candidate-sparsity-diagnostic-brief.md` (time-period regime, deeper production-vs-replay parity, Finviz-universe reconstruction) are out-of-scope per brief §2.

1. **A+ criteria too restrictive in absolute terms.** The conjunction may be over-restrictive even though each criterion is individually reasonable. Tested by: per-criterion binding-constraint analysis across all four runs.
2. **A+ criteria too restrictive given the universe.** SPX+NDX is mature large-caps; Minervini-style setups should fire more often on small/mid-caps. Tested by: comparing SPX+NDX vs Russell 3000 at constant capital.
3. **Capital/sizing constraints filter pattern-valid candidates.** Operator hypothesis. If `risk_feasibility` or sizing math rejects setups, low capital makes this binding. Tested by: comparing 1× vs 5× operator capital at constant universe.

---

## Methodology

**Harness.** Same earnings-proximity replay harness as Session 2b/2c (`research/harness/earnings_proximity/`), with the post-Session-2c housekeeping fixes inherited (commits `e9c9195` pre-IPO NaN strip, `fceedc3` `_covers()` future-fetch clamp). Diagnostic-specific instrumentation:

- `research/harness/earnings_proximity/universe_variants.py` — universe-variant loader (D1).
- `research/harness/earnings_proximity/instrumented_replay.py` — per-(ticker, date) per-criterion logging (D2).
- `research/harness/earnings_proximity/scripts/diagnostic_run.py` — diagnostic driver (D3).

**Replay window.** 2024-04-19 → 2026-04-23 (504 NYSE sessions). Identical to Session 2c.

**Universes.**
- `spx_ndx` — Session 2c baseline. SPX + NASDAQ-100 from `reference/rs-universe.csv` v2026-04-24-1, **516 tickers**.
- `russell_3000` — Russell 3000 ETF (iShares IWV) holdings as of 2026-04-23. Fetched 2026-04-24 from the iShares CDN. The CSV contains **2,579 equity-classified tickers** (the iShares listing also has cash + futures + non-equity rows that the loader filters out). Note: this is below the 3,000–3,050 figure typically associated with the Russell 3000 index — IWV's reported holdings list is the source of truth for this diagnostic at the fetch date.

**Capital baseline.** `base_capital = max(starting_equity, risk_equity_floor) = max($1,200, $7,500) = $7,500` from `swing.config.toml`. This mirrors the production sizing rule (`swing.trades.equity.sizing_equity`). The `--capital-multiplier` flag scales this baseline:

- **1×** → $7,500 effective equity → `risk_feasibility` budget ≈ **$37.50 / share**.
- **5×** → $37,500 effective equity → `risk_feasibility` budget ≈ **$187.50 / share**.

**Deviation from Session 2c.** Session 2c used `current_equity=$100,000` (the harness's stylized default). The diagnostic uses operator-actual sizing equity, which is materially lower. This is a deliberate methodological choice: testing the operator hypothesis ("low capital is binding") requires anchoring 1× at the operator's actual capital, not at a stylized $100k. Consequence: Run A's signal count is **not directly comparable** to Session 2c's 11 A+ signals — see "Caveats and limitations" §"Capital baseline differs from Session 2c."

**Earnings calendar.** yfinance `Ticker.get_earnings_dates()` per ticker, cached identically to Session 2c. **Coverage is markedly worse for Russell 3000 than for SPX+NDX** — see Russell-specific caveats below.

**Provenance.** Per-run manifests in `research/harness/earnings_proximity/diagnostic-out/run_<X>/run_manifest.json` carry: harness git SHA, universe name + hash + version + source URL + fetch date, window, base / multiplier / effective equity, fetch-cache hit/miss counts, total evaluations, A+ count, A+ rate per ticker-day.

---

## Results

### A+ rate by universe × capital

| Run | Universe | Capital | Effective equity | Universe size | Trading days | Ticker-days | Evaluations | A+ signals | Per-ticker-day rate |
|---|---|---|---|---:|---:|---:|---:|---:|---:|
| **A** | SPX+NDX | 1× | $7,500 | 516 | 504 | 260,064 | 258,679 | **5** | **0.00192 %** |
| **B** | SPX+NDX | 5× | $37,500 | 516 | 504 | 260,064 | 258,679 | **10** | **0.00385 %** |
| **C** | Russell 3000 | 1× | $7,500 | 2,579 | 504 | 1,299,816 | 1,258,774 | **112** | **0.00862 %** |
| **D** | Russell 3000 | 5× | $37,500 | 2,579 | 504 | 1,299,816 | 1,258,774 | **123** | **0.00946 %** |

For comparison only (NOT a fifth diagnostic run):
- **Session 2c**, SPX+NDX, $100,000 stylized capital → 11 A+ signals = 0.00423 % per ticker-day.
- **Session 2a anchor**, operator's Finviz-filtered universe at production capital → 2 / ~400 ticker-days = ~0.5 % per ticker-day, Wilson 95 % CI [0.11 %, 1.81 %].

The "evaluations" column is < ticker-days because tickers with < 200 bars of OHLCV history at a given session are skipped per `replay._MIN_BARS_FOR_EVALUATION`.

### Per-criterion binding-constraint analysis

For each (ticker, date) pair the evaluator saw, the **binding constraint** is the first criterion (in evaluation order: trend-template TT1–TT8 → VCP layer → risk_feasibility) whose `pass`/`fail` result blocked A+ classification, after honoring the trend-template `allowed_miss_names = ('TT8_rs_rank',)` rule (so TT8 fails are skipped over and the next non-pass is reported). The instrumentation logic is in `instrumented_replay._binding_constraint`. Counts below sum to the total evaluation count per run; the `<aplus>` row is the count of (ticker, date) pairs that reached A+, all other rows are reasons-for-rejection.

**Critical observation on capital propagation:** the harness's `current_equity` parameter is consumed only by `swing.evaluation.criteria.risk_feasibility` (verified by code reading and by the empirical data below: every non-`risk_feasibility` row in the SPX+NDX A vs B comparison is bit-identical, and same for Russell C vs D). So per-criterion binding-constraint counts for non-risk criteria are deterministic functions of (universe × window), not of capital.

#### Run A — SPX+NDX, 1× ($7,500)

| Criterion | Count | % of evaluations |
|---|---:|---:|
| `<aplus>` | 5 | 0.00193 % |
| TT1_above_150_200 | 109,139 | 42.19 % |
| TT2_150_above_200 | 30,437 | 11.77 % |
| TT5_above_50 | 28,503 | 11.02 % |
| adr | 22,202 | 8.58 % |
| ma_stack_10_20_50 | 18,270 | 7.06 % |
| TT6_above_52w_low_30pct | 12,453 | 4.81 % |
| proximity_20ma | 11,072 | 4.28 % |
| TT4_50_above_150_200 | 10,035 | 3.88 % |
| ma_short_rising | 6,820 | 2.64 % |
| prior_trend | 4,533 | 1.75 % |
| TT3_200_rising | 4,343 | 1.68 % |
| tightness | 717 | 0.28 % |
| TT7_within_52w_high_25pct | 115 | 0.044 % |
| vcp_volume_contraction | 28 | 0.011 % |
| **risk_feasibility** | **6** | **0.0023 %** |
| orderliness | 1 | 0.00039 % |

#### Run B — SPX+NDX, 5× ($37,500)

| Criterion | Count | % of evaluations |
|---|---:|---:|
| `<aplus>` | 10 | 0.00387 % |
| TT1_above_150_200 | 109,139 | 42.19 % |
| TT2_150_above_200 | 30,437 | 11.77 % |
| TT5_above_50 | 28,503 | 11.02 % |
| adr | 22,202 | 8.58 % |
| ma_stack_10_20_50 | 18,270 | 7.06 % |
| TT6_above_52w_low_30pct | 12,453 | 4.81 % |
| proximity_20ma | 11,072 | 4.28 % |
| TT4_50_above_150_200 | 10,035 | 3.88 % |
| ma_short_rising | 6,820 | 2.64 % |
| prior_trend | 4,533 | 1.75 % |
| TT3_200_rising | 4,343 | 1.68 % |
| tightness | 717 | 0.28 % |
| TT7_within_52w_high_25pct | 115 | 0.044 % |
| vcp_volume_contraction | 28 | 0.011 % |
| orderliness | 1 | 0.00039 % |
| **risk_feasibility** | **1** | **0.00039 %** |

#### Run C — Russell 3000, 1× ($7,500)

| Criterion | Count | % of evaluations |
|---|---:|---:|
| `<aplus>` | 112 | 0.00890 % |
| TT1_above_150_200 | 614,759 | 48.84 % |
| TT2_150_above_200 | 158,660 | 12.60 % |
| TT5_above_50 | 118,235 | 9.39 % |
| ma_stack_10_20_50 | 80,847 | 6.42 % |
| adr | 63,743 | 5.06 % |
| proximity_20ma | 63,248 | 5.02 % |
| TT4_50_above_150_200 | 39,702 | 3.15 % |
| ma_short_rising | 30,731 | 2.44 % |
| TT6_above_52w_low_30pct | 29,848 | 2.37 % |
| TT3_200_rising | 25,660 | 2.04 % |
| prior_trend | 17,870 | 1.42 % |
| tightness | 10,098 | 0.80 % |
| TT7_within_52w_high_25pct | 4,751 | 0.38 % |
| vcp_volume_contraction | 441 | 0.035 % |
| orderliness | 57 | 0.0045 % |
| **risk_feasibility** | **12** | **0.00095 %** |

#### Run D — Russell 3000, 5× ($37,500)

| Criterion | Count | % of evaluations |
|---|---:|---:|
| `<aplus>` | 123 | 0.00977 % |
| TT1_above_150_200 | 614,759 | 48.84 % |
| TT2_150_above_200 | 158,660 | 12.60 % |
| TT5_above_50 | 118,235 | 9.39 % |
| ma_stack_10_20_50 | 80,847 | 6.42 % |
| adr | 63,743 | 5.06 % |
| proximity_20ma | 63,248 | 5.02 % |
| TT4_50_above_150_200 | 39,702 | 3.15 % |
| ma_short_rising | 30,731 | 2.44 % |
| TT6_above_52w_low_30pct | 29,848 | 2.37 % |
| TT3_200_rising | 25,660 | 2.04 % |
| prior_trend | 17,870 | 1.42 % |
| tightness | 10,098 | 0.80 % |
| TT7_within_52w_high_25pct | 4,751 | 0.38 % |
| vcp_volume_contraction | 441 | 0.035 % |
| orderliness | 57 | 0.0045 % |
| **risk_feasibility** | **1** | **0.00008 %** |

### Universe-shape effect (constant capital)

At constant 1× capital ($7,500): SPX+NDX produces 5 / 260,064 = 0.0019 % per ticker-day; Russell 3000 produces 112 / 1,299,816 = 0.0086 %. **Russell 3000 has a ~4.5× higher per-ticker-day A+ rate than SPX+NDX at the same capital level.**

At 5× capital: SPX+NDX 0.0039 % vs Russell 0.0095 %, **~2.5× higher rate on Russell**.

The universe-shape effect is the largest single driver of A+-rate variance in this diagnostic. Mechanism (descriptive): the dominant binding constraint in BOTH universes is **TT1_above_150_200** ("close above both 150-day and 200-day MA"), but Russell 3000 has a slightly higher TT1-fail rate (48.8 %) than SPX+NDX (42.2 %) — i.e., a marginally higher fraction of Russell tickers are below their 200-MA at any given session. Despite that, Russell still produces ~5× more A+ signals because the universe is ~5× larger AND the survivors that do clear TT1 are more likely to clear the rest of the stack. A useful summary statistic: of the (ticker, date) pairs that pass TT1, the conditional A+ rate is ~0.0033 % on SPX+NDX (5 / 149,540) and ~0.0174 % on Russell 3000 (112 / 644,015) — the conditional rate is **~5× higher on Russell after gating on TT1**, suggesting the downstream criteria (VCP layer + risk) are also more often satisfied per-ticker on Russell, not only the trend-template gate.

### Capital-sensitivity finding

At constant universe (SPX+NDX), increasing capital 1× → 5× **doubles A+ count** (5 → 10 signals). The 5 added signals are precisely the ones the binding-constraint logger flagged as `risk_feasibility`-blocked at 1×: **FIX, STX, COHR (×2), LITE**. The 6th risk-blocked candidate at 1× (the one not recovered at 5×) corresponds to the 1 remaining `risk_feasibility`-binding count in Run B — its risk-per-share exceeds $187.50 even after the 5× scale-up.

At constant universe (Russell 3000), increasing capital 1× → 5× **adds 11 signals** (112 → 123). The 11 added correspond to the 11 = 12 - 1 reduction in `risk_feasibility` binding-constraint count between Run C and Run D (12 → 1). On the larger universe, 11 candidates are sitting just-below the 1× risk budget and just-above the 5× budget; one remains blocked even at 5×.

In percentage terms:
- **SPX+NDX**: capital 1× → 5× changes A+ rate from 0.0019 % → 0.0039 % — a **2.0× increase**, all attributable to `risk_feasibility` relaxation.
- **Russell 3000**: 1× → 5× changes from 0.0086 % → 0.0095 % — a **1.10× increase**, also entirely attributable to `risk_feasibility`.

The capital effect is **substantially smaller on Russell 3000** because Russell has more lower-priced tickers (median price lower than SPX+NDX), so the per-share risk budget at $7,500 already accommodates many setups that SPX+NDX's higher-priced names can't fit.

---

## Findings (descriptive, not prescriptive)

1. **Capital is binding for SPX+NDX but only weakly for Russell 3000 at the operator's current sizing equity.** SPX+NDX shows a 2.0× A+ rate change between $7,500 and $37,500; Russell 3000 shows a 1.10× change. On Russell 3000, capital becomes effectively non-binding at $37,500 (1 candidate still blocked, vs 12 at $7,500).
2. **`risk_feasibility` is the sole capital-sensitive criterion.** All non-risk binding-constraint counts are bit-identical across the A↔B and C↔D comparisons. This is by construction — `current_equity` propagates only through `swing.evaluation.criteria.risk_feasibility` — but the empirical confirmation is reported here so the operator can verify the harness's capital-routing isolation.
3. **Universe shape is the largest single driver of A+ rate variance.** At constant 1× capital, Russell 3000 produces a 4.5× higher per-ticker-day A+ rate than SPX+NDX. Per ticker, Russell is ~22× more productive (112 vs 5 signals on the same window). At 5× capital, the per-ticker-day ratio compresses to 2.5×.
4. **TT1_above_150_200 is the dominant binding constraint regardless of universe or capital.** It is the first failing criterion for ~42 % of SPX+NDX evaluations and ~49 % of Russell 3000 evaluations. This means the trend-template's first check (close above both 150-day and 200-day MAs) is by itself rejecting close to half of all (ticker, date) pairs in this 2-year window — i.e., most tickers are not in a sustained uptrend at most points in the window.
5. **The trend-template stack collectively binds ~70-80 % of evaluations across both universes.** Summing TT1+TT2+TT3+TT4+TT5+TT6+TT7 gives ~74 % on SPX+NDX and ~78 % on Russell 3000. The VCP layer and `risk_feasibility` operate on a much smaller eligible pool; their binding-constraint counts are downstream of the trend-template gate.
6. **`vcp_volume_contraction` and `orderliness` are rarely binding.** Across all four runs combined, vcp_volume_contraction was the binding constraint for 938 of 3,034,906 evaluations (0.031 %); orderliness for 116 (0.0038 %). These two criteria fire late in the evaluation chain and the sample of (ticker, date) pairs that even reach them is small.
7. **The 11-signal Session 2c result reproduces between $37,500 and $100,000.** Run B at $37,500 gets 10 A+ signals (the 5 from Run A plus 5 of the 6 risk-blocked candidates); Session 2c at $100k got 11 (the 11th, the highest-priced setup, needs >$37.5k and <$100k to fit). The Session 2c result is not "lost" in the diagnostic — it is the upper end of the SPX+NDX × capital curve this diagnostic mapped.
8. **The Session 2a anchor (~0.5 % per ticker-day on Finviz-filtered universe) is still ~50× above the Russell-3000 1× rate (0.0086 %).** Universe shape (Russell vs SPX+NDX) and capital (5× vs 1×) together explain the gap from Session 2c's 0.0042 % to Run D's 0.0095 % — a ~2.3× factor — but the residual gap to the production anchor is two orders of magnitude. **What this diagnostic does NOT explain is why the production anchor is so high relative to either universe's diagnostic-measured rate**; that residual could be Finviz-filter pre-screening, time-period regime difference, harness-vs-production parity drift, or anchor sample-size noise (n=2 / 400 in Session 2a). Each is hypothesis 4–6 territory and out-of-scope here.

---

## What this diagnostic does NOT say

- This diagnostic does **NOT** recommend changing any A+ criterion threshold.
- This diagnostic does **NOT** recommend broadening the production universe.
- This diagnostic does **NOT** make any claim about the **edge quality** of A+ candidates — only about their **rate** (count per ticker-day). No expectancy, win-rate, or gap-through statistics are computed; the harness's existing simulator was not invoked because the diagnostic question is "how many candidates do we find?" not "what is their performance?"
- This diagnostic does **NOT** test whether the trend-template's `allowed_miss_names = ('TT8_rs_rank',)` rule is correct or should be widened — only how often each TT criterion is exercised.
- This diagnostic does **NOT** test the operator's actual current account state (open positions, realized P&L, cash deposits/withdrawals). The "operator capital" is derived from `swing.config.toml`'s `[account]` section, not from the production DB.
- This diagnostic does **NOT** provide Wilson- or bootstrap-CIs for any rate quoted; reported rates are point estimates with sample sizes given so the reader can derive intervals if needed. (For reference: a Wilson 95 % CI on Run D's 123 / 1,258,774 is approximately ±0.0017 %; on Run A's 5 / 258,679 it is approximately [0.0006 %, 0.0045 %].)
- This diagnostic does **NOT** explain the residual gap between the Russell-3000-5× rate and the Session 2a production anchor; that gap could be attributable to Finviz pre-filtering, regime, or anchor noise (hypotheses 4–6, out-of-scope).
- This diagnostic uses the same fixed-universe and survivorship-biased data as Session 2c; findings inherit the same caveats.

---

## Caveats and limitations

- **Survivorship bias (same as Session 2c).** The replay uses current-roster universes. Delisted tickers (biotech wipeouts, accounting-fraud cases, eventually-delisted small-caps) are absent from both SPX+NDX and Russell 3000 universes. The historical population that produced the operator's anchor rate (~0.5 %) was not survivorship-biased in the same way; the diagnostic cannot fully separate "binding criterion" effects from "missing-population" effects. The bias likely affects Russell 3000 MORE than SPX+NDX (smaller-cap delisting rates are higher), so the universe-shape effect this diagnostic reports is conservatively understated.
- **Fixed-universe at run date; no point-in-time membership reconstruction.** Both universes are snapshots as of 2026-04-24. Russell 3000 membership rebalances annually (June reconstitution); applying the 2026 snapshot to historical 2024-2025 data over-includes tickers that joined late and under-includes tickers that exited. SPX+NDX has analogous drift. Session 2a's universe-staleness concession applies identically here.
- **Russell 3000 is iShares-IWV-derived.** Authoritative Russell-3000 index membership comes from FTSE Russell directly (paid feed); this diagnostic uses iShares' tracking-fund holdings as a free, reproducible proxy. The 2,579 equity-ticker count reflects IWV holdings on 2026-04-23 and is below the 3,000+ FTSE Russell index member count. The shortfall is plausibly attributable to: iShares dropping cash-collateral / derivative / dual-class / inactive-listing rows; recent index rebalancing not yet reflected; and the loader's filter (`Asset Class == 'Equity'`) removing illiquid or non-equity holdings. The shortfall does NOT change the diagnostic's qualitative findings (universe-shape effect, capital sensitivity) but means absolute Russell-3000 figures are conservative under-estimates of an FTSE-Russell-faithful universe.
- **Earnings-calendar coverage is markedly worse on Russell 3000.** 61 / 112 (54 %) of Run C's A+ signals carry `absent_earnings_data=True`; 64 / 123 (52 %) of Run D's. By contrast, 0 / 5 and 0 / 10 of the SPX+NDX runs' A+ signals are absent-data. yfinance's `Ticker.get_earnings_dates` coverage is sparse for many small/mid-cap names. The diagnostic's binding-constraint identification is robust to per-ticker calendar noise (binding constraint is determined pre-earnings-filter), so this affects neither the universe-shape nor capital-sensitivity findings as reported. Any extension that depends on earnings-proximity filtering on Russell 3000 would be substantially affected; that is documented but not pursued here.
- **2-year window is a single regime.** The 2024-04 → 2026-04 window is one bull-market regime. Findings would not necessarily generalize to bear or volatile regimes; broader-time-period analysis is hypothesis 4 in the brief, out-of-scope this session.
- **Production-vs-replay parity is partial.** The harness imports `swing.evaluation.evaluator.evaluate_one` directly, so per-criterion logic is identical to production; but the surrounding orchestration (`BatchContext` construction, RS computation cross-section) is reconstructed in the harness. Existing harness fixture tests (`test_parity.py`) verify identity for a small fixed universe; full parity against production runs is hypothesis 5, also out-of-scope this session.
- **Capital baseline differs from Session 2c.** The diagnostic uses `$7,500` (operator's `max(starting_equity, risk_equity_floor)`) where Session 2c used `$100,000`. Session 2c's 11 A+ signals are therefore not directly comparable to this diagnostic's Run A signal count (Run A would be expected to produce ≤11). The diagnostic implicitly bridges by showing Run B at $37,500 produces 10 of the 11; the 11th would require the third interval [$37,500, $100,000] which is not directly measured here. To explicitly bridge: a supplementary parity run at `--base-capital 100000 --capital-multiplier 1.0` would reproduce Session 2c's 11; that run is not part of the four-run matrix and is left as a follow-on if the operator wants explicit Session-2c parity verification.
- **`risk_feasibility` binding-constraint identification depends on evaluation order.** Because TT1 is by far the most-frequently-failing criterion (~42-49 % of evaluations), most ticker-date pairs never even reach `risk_feasibility` — the binding constraint reported is whatever fails first in the chain, NOT a ranked list of "which criteria would fail if all upstream had passed." A candidate could fail BOTH TT1 and `risk_feasibility` and be tallied only as TT1. The capital-sensitivity finding is robust to this (only `risk_feasibility` changes between A↔B and C↔D, by construction), but the absolute size of the "candidate pool that risk_feasibility would block if everything else passed" is NOT what this diagnostic reports.
- **No edge / expectancy assessment.** The diagnostic measures candidate **rate**, not candidate **quality**. The 123 A+ signals on Russell 3000 5× include many small / illiquid names whose realized expectancy under live execution would likely differ from large-cap setups. The harness's simulator (`simulate_trade`) was deliberately not invoked because that is Session-2c-style analysis territory and outside this diagnostic's scope.
- **Russell 3000 cache warm-up.** First-time fetch hit yfinance for ~2,078 cold OHLCV tickers and ~2,077 cold earnings tickers during this session. 14 OHLCV tickers (e.g., GTXI, P5N994, BRKB-class shares) failed yfinance lookup and are absent from cached frames; the harness skips them silently in evaluation. This affects ~0.5 % of the Russell universe and does not materially change rate findings.

---

## Open questions for the operator

These are questions the diagnostic findings might prompt; the diagnostic does not answer them, and they are surfaced here so the operator can decide which (if any) to commission as follow-on work. Phrasing is intentionally open-ended — none of these are recommendations.

- Is the residual gap between the Russell-3000-5× rate (0.0095 % per ticker-day) and the Session 2a production anchor (~0.5 %) explainable by Finviz-filter pre-screening alone, or is some other factor (regime, parity drift, anchor sample-size noise) load-bearing? A reconstruction-of-historical-Finviz-CSV study would be needed to answer.
- Would a study that runs the harness on the operator's actual production DB universe at the operator's actual realized capital — rather than the current operator config + a stylized universe — produce a rate that matches the production anchor? This is the explicit production-vs-replay parity test, hypothesis 5.
- The `risk_feasibility` binding-constraint count at 1× ($7,500) is small in absolute terms (6 on SPX+NDX, 12 on Russell 3000). Is the operator's product workflow more sensitive to the COUNT of risk-blocked candidates (a few names per quarter) or to the ROUTING of those candidates (e.g., would knowing "this setup needs 5× your current capital" be useful UI signal)?
- Does TT1's ~45 % rejection rate represent a regime feature (the 2024-04 → 2026-04 window had many tickers below 200-MA) or a structural feature (Minervini's TT1 rule is meant to be selective)? A multi-regime study (different 2-year windows) would distinguish.
- Is the operator's current account-state (`starting_equity = $1,200`, `risk_equity_floor = $7,500`, → effective $7,500 sizing equity) the right mental model for "operator capital" in further studies? Or should diagnostics use the LIVE current equity from the DB (starting + realized P&L + cash movements) when one exists?
- Does the survivorship-bias gap between current-roster Russell 3000 (used here) and a delisting-aware historical universe (not used) materially change conclusions? FTSE Russell offers point-in-time-membership feeds; iShares does not. A bootstrap-bias-quantification study would compare.

---

## Run artifacts

Each run directory under `research/harness/earnings_proximity/diagnostic-out/run_<X>/` contains:

| File | Contents | Committed? |
|---|---|---|
| `run_manifest.json` | Provenance: git SHA, universe metadata, capital, cache stats, summary counts | yes |
| `aplus_signals.csv` | One row per A+ signal (ticker, date, entry, stop, next-earnings, absent-data flag) | yes |
| `binding_constraints.csv` | Aggregated counts: per-criterion + `<aplus>` sentinel | yes |
| `evaluations.csv` | Per-(ticker, date) per-criterion `pass`/`fail` results — 32 MB SPX, 154 MB Russell | **no** (in `.gitignore`; regenerable from manifest flags) |

| Run | Output directory |
|---|---|
| A | `research/harness/earnings_proximity/diagnostic-out/run_A_spx_ndx_1x/` |
| B | `research/harness/earnings_proximity/diagnostic-out/run_B_spx_ndx_5x/` |
| C | `research/harness/earnings_proximity/diagnostic-out/run_C_russell_3000_1x/` |
| D | `research/harness/earnings_proximity/diagnostic-out/run_D_russell_3000_5x/` |

Universe snapshot (cached locally, not in the repo): `~/swing-data/research-cache/universe-snapshots/russell_3000_2026-04-24.csv` (iShares IWV; 2,579 equity tickers; SHA-256 in run_C/D manifest).
