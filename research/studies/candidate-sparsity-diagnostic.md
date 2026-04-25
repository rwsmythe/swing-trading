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
- `research/harness/earnings_proximity/scripts/recompute_binding_prod_gated.py` — production-faithful blocker re-aggregation (added in adversarial-review Round 1 fix; see "Two metrics for the binding-constraint analysis" below).

**Replay window.** 2024-04-19 → 2026-04-23 (504 NYSE sessions). Identical to Session 2c.

**Universes.**
- `spx_ndx` — Session 2c baseline. SPX + NASDAQ-100 from `reference/rs-universe.csv` v2026-04-24-1, **516 tickers**.
- `russell_3000` — Russell 3000 ETF (iShares IWV) holdings as of 2026-04-23. Fetched 2026-04-24 from the iShares CDN. The CSV contains **2,579 equity-classified tickers** (the iShares listing also has cash + futures + non-equity rows that the loader filters out). This is below the 3,000–3,050 figure typically associated with the Russell 3000 index — IWV's reported holdings list is the source of truth for this diagnostic at the fetch date.

**Capital baseline.** `base_capital = max(starting_equity, risk_equity_floor) = max($1,200, $7,500) = $7,500` from `swing.config.toml`. This mirrors the production sizing rule (`swing.trades.equity.sizing_equity`). The `--capital-multiplier` flag scales this baseline:

- **1×** → $7,500 effective equity → `risk_feasibility` budget ≈ **$37.50 / share**.
- **5×** → $37,500 effective equity → `risk_feasibility` budget ≈ **$187.50 / share**.

**Deviation from Session 2c.** Session 2c used `current_equity=$100,000` (the harness's stylized default). The diagnostic uses operator-actual sizing equity, which is materially lower. This is a deliberate methodological choice: testing the operator hypothesis ("low capital is binding") requires anchoring 1× at the operator's actual capital, not at a stylized $100k. Consequence: Run A's signal count is **not directly comparable** to Session 2c's 11 A+ signals — see "Caveats and limitations" §"Capital baseline differs from Session 2c."

**Earnings calendar.** yfinance `Ticker.get_earnings_dates()` per ticker, cached identically to Session 2c. Coverage is markedly worse for Russell 3000 than for SPX+NDX — see Russell-specific caveats below.

**Provenance.** Per-run manifests in `research/harness/earnings_proximity/diagnostic-out/run_<X>/run_manifest.json` carry: harness git SHA, universe name + hash + version + source URL + fetch date, window, base / multiplier / effective equity, fetch-cache hit/miss counts, total evaluations, A+ count, A+ rate per ticker-day.

### Two metrics for the binding-constraint analysis

The harness instrumentation produces two related but distinct metrics for "which criterion blocked A+." Adversarial review (Round 1) flagged that the original report conflated them; this version uses **production-gated** as the primary metric and reports emitted-order separately as an audit-trail artifact.

1. **Production-gated blocker** *(primary metric in this report)*. Replicates `swing.evaluation.scoring.bucket_for`'s decision order: `risk_feasibility` is checked **first** as a hard filter, then trend-template (with `min_passes=7` and `allowed_miss_names=('TT8_rs_rank',)`), then VCP-fail-count thresholds. A candidate that fails BOTH TT1 AND `risk_feasibility` is reported as "risk-blocked" in production semantics, even though TT1 happens to be evaluated first in emitted order. Counts in `binding_constraints_prod_gated.csv` per run; computed by `recompute_binding_prod_gated.py`.
2. **First non-pass in emitted order** *(secondary; original metric)*. Walks `Candidate.criteria` in evaluator emission order (TT1–TT8 → VCP layer → risk_feasibility) and returns the first non-pass criterion (with `allowed_miss_names` honored on the trend-template segment). Counts in `binding_constraints.csv` per run. **This metric systematically under-attributes risk_feasibility blocking**, because most candidates that fail risk_feasibility also fail at least one earlier-emitted criterion. The emitted-order counts are preserved as an audit trail; analysis should use the production-gated counts.

The two metrics agree on the count of `<aplus>` (since A+ requires all criteria pass under either ordering). They agree on `risk_feasibility` only for candidates that pass everything else — the strictest "would only fail risk_feasibility" subset. They diverge on every other criterion.

---

## Results

### A+ rate by universe × capital

| Run | Universe | Capital | Effective equity | Universe size | Trading days | Ticker-days | Evaluations | A+ signals | Rate per ticker-day | Wilson 95 % CI |
|---|---|---|---|---:|---:|---:|---:|---:|---:|---|
| **A** | SPX+NDX | 1× | $7,500 | 516 | 504 | 260,064 | 258,679 | **5** | **0.00193 %** | [0.00083 %, 0.00453 %] |
| **B** | SPX+NDX | 5× | $37,500 | 516 | 504 | 260,064 | 258,679 | **10** | **0.00387 %** | [0.00210 %, 0.00712 %] |
| **C** | Russell 3000 | 1× | $7,500 | 2,579 | 504 | 1,299,816 | 1,258,774 | **112** | **0.00890 %** | [0.00740 %, 0.01070 %] |
| **D** | Russell 3000 | 5× | $37,500 | 2,579 | 504 | 1,299,816 | 1,258,774 | **123** | **0.00977 %** | [0.00819 %, 0.01166 %] |

For comparison only (NOT a fifth diagnostic run):
- **Session 2c**, SPX+NDX, $100,000 stylized capital → 11 A+ signals = 0.00423 % per ticker-day. Wilson 95 % CI [0.00237 %, 0.00756 %].
- **Session 2a anchor**, operator's Finviz-filtered universe at production capital → 2 / ~400 ticker-days = 0.500 % per ticker-day, Wilson 95 % CI [0.137 %, 1.806 %].

The "evaluations" column is < ticker-days because tickers with < 200 bars of OHLCV history at a given session are skipped per `replay._MIN_BARS_FOR_EVALUATION`.

**Statistical-inference framing.**

- **Capital comparison A↔B and C↔D is PAIRED, not independent.** Both runs in each pair are evaluated on the *same* (ticker, date) set; only `current_equity` differs. Capital scaling is also *monotonic* — `risk_feasibility`'s pass set at 5× is a strict superset of its pass set at 1× (a higher per-share budget can only allow MORE candidates through). So the appropriate framing for the headline A+-rate change is **counting the deterministic transitions** between cells of the discordant-pair table, not Wilson-CI overlap on independent rates.
  - SPX+NDX A↔B transition table on the 258,679 (ticker, date) pairs:

    | Status at 1× | Status at 5× | Count |
    |---|---|---|
    | A+ | A+ | 5 |
    | non-A+ | A+ | 5 (FIX, STX, COHR ×2, LITE — exact set named in finding 7 below) |
    | A+ | non-A+ | 0 (impossible by monotonicity) |
    | non-A+ | non-A+ | 258,669 |

    The 5 → 10 A+ count is a **deterministic count of paired transitions**, not a sampled rate ratio. Under exact one-sided binomial intuition (5 of 5 informative pairs flip in the only direction monotonicity permits), the capital effect is real on this sample by construction; "statistical significance" in the independent-Wilson sense is the wrong frame for paired-monotonic transitions.
  - Russell 3000 C↔D transition table (analogous): 112 → 123 = **11 deterministic transitions** from non-A+ at 1× to A+ at 5×, 0 reverse, 1 candidate that fails risk_feasibility at both 1× and 5×.

- **Cross-universe comparison A↔C and B↔D is INDEPENDENT** (different (ticker, date) sets). The Wilson CIs reported in the table are intervals on each rate independently. The non-overlap of A's CI [0.00083 %, 0.00453 %] and C's CI [0.00740 %, 0.01070 %] is suggestive of a non-zero rate difference but is not a formal hypothesis test; the disjoint-CI rule has known anti-conservative properties for difference-of-proportions inference. A formal Newcombe interval on (p_C − p_A) would be the proper test; the magnitude of the point-estimate difference (~6.97 × 10⁻⁵, or ~36× the smaller rate) is large enough that the qualitative conclusion is robust to choice of test, though the exact CI width is not reported here.

### Per-criterion binding-constraint analysis (production-gated)

For each (ticker, date) pair the evaluator saw, the **production-gated blocker** is the first criterion (in production gating order: `risk_feasibility` hard filter → trend-template gate → VCP-fail count) that prevents A+ classification. Counts below sum to the total evaluation count per run; the `<aplus>` row is the count of (ticker, date) pairs that reached A+, all other rows are reasons-for-rejection-under-production-gating. Source: `binding_constraints_prod_gated.csv` per run.

#### Run A — SPX+NDX, 1× ($7,500)

| Criterion | Count | % of evaluations |
|---|---:|---:|
| `<aplus>` | 5 | 0.00193 % |
| TT1_above_150_200 | 88,970 | 34.39 % |
| **risk_feasibility** | **48,155** | **18.62 %** |
| TT2_150_above_200 | 25,541 | 9.87 % |
| TT5_above_50 | 22,889 | 8.85 % |
| adr | 18,427 | 7.12 % |
| ma_stack_10_20_50 | 14,781 | 5.71 % |
| TT6_above_52w_low_30pct | 11,747 | 4.54 % |
| TT4_50_above_150_200 | 7,975 | 3.08 % |
| proximity_20ma | 6,713 | 2.60 % |
| ma_short_rising | 5,512 | 2.13 % |
| TT3_200_rising | 3,804 | 1.47 % |
| prior_trend | 3,750 | 1.45 % |
| tightness | 331 | 0.13 % |
| TT7_within_52w_high_25pct | 68 | 0.026 % |
| vcp_volume_contraction | 11 | 0.0043 % |

#### Run B — SPX+NDX, 5× ($37,500)

| Criterion | Count | % of evaluations |
|---|---:|---:|
| `<aplus>` | 10 | 0.00387 % |
| TT1_above_150_200 | 107,774 | 41.66 % |
| TT2_150_above_200 | 30,243 | 11.69 % |
| TT5_above_50 | 28,096 | 10.86 % |
| adr | 22,013 | 8.51 % |
| ma_stack_10_20_50 | 18,000 | 6.96 % |
| TT6_above_52w_low_30pct | 12,334 | 4.77 % |
| proximity_20ma | 10,607 | 4.10 % |
| TT4_50_above_150_200 | 9,931 | 3.84 % |
| ma_short_rising | 6,712 | 2.59 % |
| prior_trend | 4,441 | 1.72 % |
| TT3_200_rising | 4,336 | 1.68 % |
| **risk_feasibility** | **3,367** | **1.30 %** |
| tightness | 677 | 0.26 % |
| TT7_within_52w_high_25pct | 111 | 0.043 % |
| vcp_volume_contraction | 26 | 0.010 % |
| orderliness | 1 | 0.00039 % |

#### Run C — Russell 3000, 1× ($7,500)

| Criterion | Count | % of evaluations |
|---|---:|---:|
| `<aplus>` | 112 | 0.00890 % |
| TT1_above_150_200 | 579,576 | 46.04 % |
| TT2_150_above_200 | 149,801 | 11.90 % |
| TT5_above_50 | 107,829 | 8.57 % |
| **risk_feasibility** | **86,969** | **6.91 %** |
| ma_stack_10_20_50 | 74,453 | 5.91 % |
| adr | 58,152 | 4.62 % |
| proximity_20ma | 53,719 | 4.27 % |
| TT4_50_above_150_200 | 36,486 | 2.90 % |
| TT6_above_52w_low_30pct | 28,688 | 2.28 % |
| ma_short_rising | 28,162 | 2.24 % |
| TT3_200_rising | 24,578 | 1.95 % |
| prior_trend | 16,326 | 1.30 % |
| tightness | 8,975 | 0.71 % |
| TT7_within_52w_high_25pct | 4,493 | 0.36 % |
| vcp_volume_contraction | 400 | 0.032 % |
| orderliness | 55 | 0.0044 % |

#### Run D — Russell 3000, 5× ($37,500)

| Criterion | Count | % of evaluations |
|---|---:|---:|
| `<aplus>` | 123 | 0.00977 % |
| TT1_above_150_200 | 613,058 | 48.70 % |
| TT2_150_above_200 | 158,290 | 12.57 % |
| TT5_above_50 | 117,697 | 9.35 % |
| ma_stack_10_20_50 | 80,533 | 6.40 % |
| adr | 63,532 | 5.05 % |
| proximity_20ma | 62,641 | 4.98 % |
| TT4_50_above_150_200 | 39,650 | 3.15 % |
| ma_short_rising | 30,610 | 2.43 % |
| TT6_above_52w_low_30pct | 29,661 | 2.36 % |
| TT3_200_rising | 25,638 | 2.04 % |
| prior_trend | 17,746 | 1.41 % |
| tightness | 10,049 | 0.80 % |
| TT7_within_52w_high_25pct | 4,735 | 0.38 % |
| **risk_feasibility** | **4,315** | **0.34 %** |
| vcp_volume_contraction | 439 | 0.035 % |
| orderliness | 57 | 0.0045 % |

### Universe-shape effect (constant capital)

At constant 1× capital ($7,500), Russell 3000 produces 0.0089 % per ticker-day vs SPX+NDX 0.0019 %; at 5× capital, Russell 0.0098 % vs SPX+NDX 0.0039 %. The ratio is ~4.6× at 1× and ~2.5× at 5×. Per the "Statistical-inference framing" subsection above, these are independent-sample comparisons; the per-rate Wilson CIs are disjoint, which is suggestive of a non-zero rate difference but is not a formal hypothesis test. A formal Newcombe interval on the difference of proportions would be the proper instrument; the magnitude of the point-estimate difference (~6.97 × 10⁻⁵, or roughly 4–5× the smaller rate) is large enough that the qualitative direction is robust to choice of test, though no formal test was run here.

**Interpretation, with confounders explicit.** The universe comparison is consistent with a material universe-composition effect on A+ rate. However, the comparison **also** shifts several variables besides "trend-template universe shape":
- Snapshot membership (Russell 3000 has more tickers with limited OHLCV history; the harness's 200-bar minimum skips ~3.2 % of Russell ticker-days vs ~0.5 % of SPX+NDX ticker-days).
- Survivorship profile (Russell 3000's small-mid caps have higher historical delisting rates; absent from current-roster IWV).
- Sector/liquidity mix (Russell over-samples low-volume names where setups crystallize differently).
- yfinance OHLCV-fetch success rate (14 Russell tickers failed lookup; 0 SPX+NDX).

The diagnostic does **not** isolate "universe shape" from these confounders. The conclusion the data supports is that **changing universe from SPX+NDX to Russell-3000-via-IWV** changes the A+ rate by the reported factors; the conclusion the data does **not** support is "A+ rate is determined by trend-template suitability of mid-cap stocks." A matched-cohort or point-in-time-universe study would be needed to separate composition from shape.

A useful summary statistic, with the same caveat applied: of the (ticker, date) pairs that pass TT1 directly (i.e., the row's `TT1_above_150_200` column is `pass` regardless of gating), the conditional A+ rate is **5 / 149,540 = 0.00334 %** on SPX+NDX (1×) and **112 / 644,015 = 0.01739 %** on Russell 3000 (1×) — a ~5.2× higher conditional rate after gating on TT1. (Denominators computed from the per-row TT1 column in `evaluations.csv`; the emitted-order TT1-blocker count is 109,139 on SPX+NDX and 614,759 on Russell, and TT1-pass = total evaluations − TT1-fail-or-NA = 258,679 − 109,139 and 1,258,774 − 614,759 respectively.) This is consistent with downstream criteria (VCP layer, risk) being more often satisfied per-ticker on Russell than on SPX+NDX, but the same compositional confounders apply.

### Capital-sensitivity finding

**The structural signal: production-gated `risk_feasibility` count drops dramatically with 5× capital.**

- SPX+NDX: 1× → 5× moves `risk_feasibility` from **48,155 (18.62 %) of evaluations** to **3,367 (1.30 %)** — a 14.3× reduction. About 44,800 (ticker, date) pairs that production-gating would have rejected for risk-per-share at 1× now pass that hard filter at 5×.
- Russell 3000: 1× → 5× moves `risk_feasibility` from **86,969 (6.91 %)** to **4,315 (0.34 %)** — a 20.2× reduction. About 82,650 pairs flip past the risk filter.

**The headline-rate signal: A+ count change.** The number of (ticker, date) pairs that ALSO clear all other criteria (TT + VCP) and become A+ moves more modestly:
- SPX+NDX: 5 → 10 A+ signals (a +5 difference).
- Russell 3000: 112 → 123 A+ signals (a +11 difference).

The +5 / +11 are precisely the candidates whose **only** failing criterion at 1× was risk-per-share — they passed all TT and VCP but their risk-per-share exceeded $37.50 at 1× and is ≤ $187.50 at 5×. These show up empirically as the difference between Run A's 6 emitted-order risk_feasibility hits and Run B's 1 (= 5 candidates moved to A+, 1 remains too risky even at 5×); and Russell's 12 → 1 = 11 candidates moved + 1 still blocked. (The emitted-order count is, by construction, the strict "only failed risk_feasibility" subset; the production-gated count includes the larger pool that ALSO failed something upstream.)

**Interpretation, with statistical caveats explicit.**
- The **structural** observation (`risk_feasibility` blocks 18.6 % → 1.3 % of SPX+NDX evaluations as capital scales) is robust: it is a count over ~258K evaluations and the change is large in absolute terms. The Russell observation (6.9 % → 0.3 %) is similarly robust.
- The **headline A+-rate** transition (5 → 10 on SPX+NDX; 112 → 123 on Russell) is a **deterministic count of paired-monotonic transitions** — given that capital scaling can only relax `risk_feasibility`, every flip is in the only physically possible direction. Statistical-significance framing on independent samples (Wilson CI on the rate ratio) is inappropriate here; the right description is "5 candidates on SPX+NDX and 11 on Russell flipped from blocked-only-by-risk_feasibility to A+, in a sample where 1 / 6 (SPX) and 1 / 12 (Russell) candidates remain risk-blocked even at 5×."
- All differences are by construction attributable only to the `risk_feasibility` criterion: the harness's `current_equity` parameter is consumed only by `swing.evaluation.criteria.risk_feasibility` (verified by code reading and by the empirical data above — every non-`risk_feasibility` row in the production-gated A↔B and C↔D comparisons is shifted only because the upstream-failure counts change when more rows reach the trend-template / VCP layers). This is a deterministic property of the harness; the empirical confirmation is reported here so the reader can verify the harness's capital-routing isolation.

Whether these structural and transition-count findings constitute "capital is binding" or "capital is non-binding" depends on which threshold matters to the operator. **The diagnostic does not pick a threshold.**

---

## Findings (descriptive, not prescriptive)

1. **`risk_feasibility` blocks a substantial fraction of evaluations at the operator's current 1× capital, and that fraction shrinks substantially at 5×.** Production-gated counts: SPX+NDX 18.62 % → 1.30 %; Russell 3000 6.91 % → 0.34 %. The headline A+ rate change attributable to the same capital scale-up is +5 signals on SPX+NDX (5 → 10) and +11 on Russell (112 → 123); these specific A+ moves are precisely the candidates whose only failing criterion was risk-per-share. **Whether the structural shift in production-gated risk_feasibility count "matters" for the operator depends on a threshold the diagnostic does not set.**
2. **`risk_feasibility` is the sole capital-sensitive criterion.** All non-risk per-criterion counts shift only because upstream-rejection counts shift (production gating order): the harness's `current_equity` flows only through `swing.evaluation.criteria.risk_feasibility`. Empirical confirmation: A↔B and C↔D non-risk criterion counts are deterministic functions of (universe × window) under each gating ordering.
3. **A+ rate differs between universes at constant capital, consistent with a material universe-composition effect.** Russell 3000 produces ~4.6× the per-ticker-day A+ rate of SPX+NDX at 1× capital and ~2.5× at 5×. These are independent-sample comparisons; per-rate Wilson CIs are disjoint between SPX+NDX and Russell at both capital levels, which is suggestive of a non-zero rate difference (no formal test of the difference was run; see "Statistical-inference framing" in §"A+ rate by universe × capital"). The diagnostic does **not** isolate "universe shape" from the confounders documented in §"Universe-shape effect" (snapshot membership, survivorship profile, sector/liquidity mix, yfinance coverage); the finding is that *changing universe from SPX+NDX to Russell-3000-via-IWV* moves A+ rate by these factors, not that "small-mid-cap names are intrinsically better at producing setups."
4. **TT1_above_150_200 is the highest-recorded production-gated blocker on both universes.** ~34 % of SPX+NDX evaluations at 1× and ~46 % at Russell 3000 1×. Important: the production-gated count for TT1 is itself sensitive to the upstream `risk_feasibility` hard-filter — at 1× SPX+NDX, ~19,000 fewer evaluations are tallied as TT1-blocked vs the emitted-order metric, because they are tallied as risk_feasibility-blocked instead. The TT1-fail rate is thus a **production-gated** metric and not directly a measure of "what fraction of tickers are below their MA on a given day"; for the latter, see the emitted-order `binding_constraints.csv`.
5. **The trend-template stack collectively binds ~70-80 % of evaluations at 5× capital; smaller fraction at 1× because risk_feasibility absorbs the 1× overflow first.** Summing TT1-TT7 (excluding allowed-miss TT8) under production gating gives ~62 % SPX+NDX 1× → ~74 % SPX+NDX 5×; ~67 % Russell 1× → ~78 % Russell 5×. The trend-template gate is the largest-magnitude rejection layer once the risk-feasibility hard filter clears.
6. **`vcp_volume_contraction` and `orderliness` are rarely the recorded production-gated blocker.** Across all four runs combined, vcp_volume_contraction was the production-gated blocker for 876 of 3,034,906 evaluations (0.029 %); orderliness for 113 (0.0037 %). This count means "all upstream criteria passed AND `vcp_volume_contraction` was the first VCP-layer fail"; it does NOT mean these criteria rarely fail in some absolute sense — the conditional pass rate of these criteria, gated on upstream-passing, is not directly measured.
7. **The 11-signal Session 2c result sits between $37,500 and $100,000 effective equity on SPX+NDX.** Run B at $37,500 produces 10 A+ signals (the 5 from Run A plus 5 of the 6 emitted-order risk-blocked candidates); Session 2c at $100k reported 11. The 11th candidate (KLAC, per Session 2c) has a risk-per-share between $37.50 and ~$500 (the exact threshold is not measured here). A supplementary parity run at `--base-capital 100000 --capital-multiplier 1.0` would test whether 11 reproduces precisely; it is not part of the four-run matrix.
8. **The Session 2a anchor (~0.5 % per ticker-day on Finviz-filtered universe) remains roughly two orders of magnitude above the Russell-3000-5× rate (0.0098 %).** Universe shape (Russell vs SPX+NDX) and capital (5× vs 1×) together explain the gap from Session 2c's 0.0042 % to Run D's 0.0098 % — a ~2.3× factor — but the residual gap to the production anchor is not explained by the variables this diagnostic varied. **The diagnostic does not say what causes the residual gap.** Plausible (untested) factors: Finviz-filter pre-screening, time-period regime difference, harness-vs-production parity drift, anchor sample-size noise (n=2 / 400 in Session 2a). Each is hypothesis 4–6 territory in the brief and out-of-scope here.

---

## What this diagnostic does NOT say

- This diagnostic does **NOT** recommend changing any A+ criterion threshold.
- This diagnostic does **NOT** recommend broadening the production universe.
- This diagnostic does **NOT** make any claim about the **edge quality** of A+ candidates — only about their **rate** (count per ticker-day). No expectancy, win-rate, or gap-through statistics are computed; the harness's existing simulator was not invoked because the diagnostic question is "how many candidates do we find?" not "what is their performance?"
- This diagnostic does **NOT** test whether the trend-template's `allowed_miss_names = ('TT8_rs_rank',)` rule is correct or should be widened — only how often each TT criterion is a production-gated blocker.
- This diagnostic does **NOT** test the operator's actual current account state (open positions, realized P&L, cash deposits/withdrawals). The "operator capital" is derived from `swing.config.toml`'s `[account]` section, not from the production DB.
- This diagnostic does **NOT** state whether `risk_feasibility`'s 1× → 5× shift is "binding" or "non-binding" in any operator-preference-relative sense — it reports the structural counts (48,155 → 3,367 SPX+NDX; 86,969 → 4,315 Russell) and the deterministic-paired-transition A+ counts (5 → 10 SPX+NDX; 112 → 123 Russell, with all flips in the only direction monotonic capital scaling permits). The threshold for "matters" is operator-set.
- This diagnostic does **NOT** isolate "universe shape" from confounders (snapshot membership, survivorship profile, sector/liquidity mix, yfinance coverage). The reported universe-effect ratio is "switching from SPX+NDX-via-rs-universe.csv to Russell-3000-via-IWV moves A+ rate by ~4.6× at 1× capital."
- This diagnostic does **NOT** explain the residual gap between the Russell-3000-5× rate and the Session 2a production anchor; that gap could be attributable to Finviz pre-filtering, regime, parity drift, or anchor noise (hypotheses 4–6, out-of-scope).
- This diagnostic uses the same fixed-universe and survivorship-biased data as Session 2c; findings inherit the same caveats.

---

## Caveats and limitations

- **Survivorship bias (same as Session 2c).** The replay uses current-roster universes. Delisted tickers (biotech wipeouts, accounting-fraud cases, eventually-delisted small-caps) are absent from both SPX+NDX and Russell 3000 universes. The historical population that produced the operator's anchor rate (~0.5 %) was not survivorship-biased in the same way; the diagnostic cannot fully separate "binding-criterion" effects from "missing-population" effects. The bias likely affects Russell 3000 MORE than SPX+NDX (smaller-cap delisting rates are higher), so the universe-composition effect this diagnostic reports is a lower bound on what an FTSE-Russell-faithful, point-in-time, delisting-aware version would show; the direction of the effect is plausibly preserved but the magnitude is conservatively understated.
- **Fixed-universe at run date; no point-in-time membership reconstruction.** Both universes are snapshots as of 2026-04-24. Russell 3000 membership rebalances annually (June reconstitution); applying the 2026 snapshot to historical 2024-2025 data over-includes tickers that joined late and under-includes tickers that exited. SPX+NDX has analogous drift. Session 2a's universe-staleness concession applies identically here.
- **Russell 3000 is iShares-IWV-derived.** Authoritative Russell-3000 index membership comes from FTSE Russell directly (paid feed); this diagnostic uses iShares' tracking-fund holdings as a free, reproducible proxy. The 2,579 equity-ticker count reflects IWV holdings on 2026-04-23 and is below the 3,000+ FTSE Russell index member count. The shortfall is plausibly attributable to: iShares dropping cash-collateral / derivative / dual-class / inactive-listing rows; recent index rebalancing not yet reflected; and the loader's filter (`Asset Class == 'Equity'`) removing illiquid or non-equity holdings. The shortfall does not change the diagnostic's qualitative findings (universe-composition effect direction, capital-sensitivity direction) but means absolute Russell-3000 figures are conservative under-estimates of an FTSE-Russell-faithful universe.
- **Earnings-calendar coverage is markedly worse on Russell 3000.** 61 / 112 (54 %) of Run C's A+ signals carry `absent_earnings_data=True`; 64 / 123 (52 %) of Run D's. By contrast, 0 / 5 and 0 / 10 of the SPX+NDX runs' A+ signals are absent-data. yfinance's `Ticker.get_earnings_dates` coverage is sparse for many small/mid-cap names. The diagnostic's per-criterion blocker identification is robust to per-ticker calendar noise (binding constraint is determined pre-earnings-filter, and earnings is not a criterion in the production scoring chain), so this affects neither the universe-composition nor capital-sensitivity findings as reported. Any extension that depends on earnings-proximity filtering on Russell 3000 would be substantially affected; that is documented but not pursued here.
- **2-year window is a single regime.** The 2024-04 → 2026-04 window is one bull-market regime. Findings would not necessarily generalize to bear or volatile regimes; broader-time-period analysis is hypothesis 4 in the brief, out-of-scope this session.
- **Production-vs-replay parity is partial.** The harness imports `swing.evaluation.evaluator.evaluate_one` directly, so per-criterion logic is identical to production; but the surrounding orchestration (`BatchContext` construction, RS computation cross-section) is reconstructed in the harness. The production-gated blocker re-aggregation in this report (`recompute_binding_prod_gated.py`) replicates `swing.evaluation.scoring.bucket_for`'s decision order; the replication is by design but is itself a piece of harness code with no production-side equivalent test. Existing harness fixture tests (`test_parity.py`) verify identity for a small fixed universe; full parity against production runs is hypothesis 5, also out-of-scope this session.
- **Capital baseline differs from Session 2c.** The diagnostic uses `$7,500` (operator's `max(starting_equity, risk_equity_floor)`) where Session 2c used `$100,000`. Session 2c's 11 A+ signals are therefore not directly comparable to this diagnostic's Run A signal count (Run A would be expected to produce ≤ 11 since some Session 2c signals have risk-per-share between $37.50 and $500). The diagnostic implicitly bridges by showing Run B at $37,500 produces 10 of the 11; the 11th would require the third interval [$37,500, $500] which is not directly measured here. To explicitly bridge: a supplementary run at `--base-capital 100000 --capital-multiplier 1.0` would test whether the count is exactly 11; that run is not part of the four-run matrix and is left as a follow-on.
- **Sample size is small for headline-rate comparisons.** Wilson 95 % CIs on the four runs are reported in the results table. Capital comparisons A↔B and C↔D are paired-monotonic on the same (ticker, date) set; their interpretation rests on the deterministic transition counts (5 → 10 SPX+NDX, 112 → 123 Russell) rather than independent-rate inference. Cross-universe comparisons A↔C and B↔D are independent samples; per-rate CIs are disjoint, which is suggestive of a non-zero difference but is not a formal hypothesis test (a Newcombe interval on the difference would be the proper instrument). Any operator interpretation that treats the cross-run point ratios as precise is over-confident.
- **Two binding-constraint metrics coexist.** The original instrumentation walked emitted criterion order, which conflated "TT1 fail" with "production-skipped due to risk." The production-gated re-aggregation (Round 1 fix) is the primary metric in this report; the original (emitted-order) is preserved in `binding_constraints.csv` for audit. They differ only on attribution; both agree on `<aplus>` and on the "only failed risk_feasibility" subset.
- **`risk_feasibility` blocker counts scale with the unobserved upstream-pass rate.** Production-gated counts measure "candidates that reached the corresponding gate AND failed it." A criterion's count change between runs reflects a mix of (a) the criterion's own pass-rate change and (b) the upstream pass-rate change. For risk_feasibility under capital scaling, only its own threshold changes, so the count change is a clean signal. For trend-template criteria under capital scaling, only the upstream `risk_feasibility` hard-filter throughput changes (TT and VCP criteria are capital-independent), so the production-gated counts move purely by upstream re-routing — the diagnostic notes this explicitly above.
- **No edge / expectancy assessment.** The diagnostic measures candidate **rate**, not candidate **quality**. The 123 A+ signals on Russell 3000 5× include many small / illiquid names whose realized expectancy under live execution would likely differ from large-cap setups. The harness's simulator (`simulate_trade`) was deliberately not invoked because that is Session-2c-style analysis territory and outside this diagnostic's scope.
- **Russell 3000 cache warm-up.** First-time fetch hit yfinance for ~2,078 cold OHLCV tickers and ~2,077 cold earnings tickers during this session. 14 OHLCV tickers (e.g., GTXI, P5N994, BRKB-class shares) failed yfinance lookup and are absent from cached frames; the harness skips them silently in evaluation. This affects ~0.5 % of the Russell universe and does not materially change rate findings.

---

## Open questions for the operator

These are open questions the diagnostic findings might prompt; the diagnostic does not answer them. Each is phrased as a question, with no embedded study-design prescription — choice of how (or whether) to follow up is the operator's.

- Is the residual gap between this diagnostic's measured rates (Russell 3000 5× ≈ 0.0098 % per ticker-day) and the Session 2a production anchor (~0.5 %) explainable by the variables this diagnostic did not vary (Finviz pre-screening, time period, replay-vs-production parity, anchor sample-size noise)?
- Does the production-gated `risk_feasibility` count change with capital (SPX+NDX 18.62 % → 1.30 %; Russell 6.91 % → 0.34 %) cross any threshold the operator considers material for product workflow?
- Does the small absolute count of "only-blocked-by-risk_feasibility" candidates over the diagnostic window (6 on SPX+NDX, 12 on Russell 3000 across the full 2-year window — i.e., a rate on the order of a few candidates per universe per year) cross the operator's threshold for "this is a UI-relevant signal" (e.g., a "this setup needs more capital" hint on each candidate row)?
- Is the operator's current account-state (`starting_equity = $1,200`, `risk_equity_floor = $7,500` → effective $7,500 sizing equity) the right reference value for "operator capital" in further studies, or would the live DB-derived current equity (starting + realized P&L + cash movements) be a better reference?
- Does the universe-composition effect direction this diagnostic reports survive a delisting-aware, point-in-time-membership universe? FTSE Russell offers point-in-time-membership feeds; iShares (this diagnostic's source) does not.
- Is the TT1 ~46 % rejection rate on Russell 3000 a feature of this 2-year window's market regime, or a structural feature of the trend-template definition?

---

## Run artifacts

Each run directory under `research/harness/earnings_proximity/diagnostic-out/run_<X>/` contains:

| File | Contents | Committed? |
|---|---|---|
| `run_manifest.json` | Provenance: git SHA, universe metadata, capital, cache stats, summary counts | yes |
| `aplus_signals.csv` | One row per A+ signal (ticker, date, entry, stop, next-earnings, absent-data flag) | yes |
| `binding_constraints_prod_gated.csv` | **Primary** — production-gated blocker counts per criterion + `<aplus>` sentinel | yes |
| `binding_constraints.csv` | **Audit-trail** — first-non-pass-in-emitted-order counts (original metric, conflates upstream-rerouted candidates) | yes |
| `evaluations.csv` | Per-(ticker, date) per-criterion `pass`/`fail` results — 32 MB SPX, 154 MB Russell | **no** (in `.gitignore`; regenerable from manifest flags) |

| Run | Output directory |
|---|---|
| A | `research/harness/earnings_proximity/diagnostic-out/run_A_spx_ndx_1x/` |
| B | `research/harness/earnings_proximity/diagnostic-out/run_B_spx_ndx_5x/` |
| C | `research/harness/earnings_proximity/diagnostic-out/run_C_russell_3000_1x/` |
| D | `research/harness/earnings_proximity/diagnostic-out/run_D_russell_3000_5x/` |

Universe snapshot (cached locally, not in the repo): `~/swing-data/research-cache/universe-snapshots/russell_3000_2026-04-24.csv` (iShares IWV; 2,579 equity tickers; SHA-256 in run_C/D manifest).
