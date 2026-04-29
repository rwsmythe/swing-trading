# QuantEcon External References

**Date:** 2026-04-24 (initial creation)
**Companion to:** [`./2026-04-24-quant-econ-future-research-program.md`](2026-04-24-quant-econ-future-research-program.md) and [`./2026-04-24-quant-econ-companion-trigger-purpose-three-branch.md`](2026-04-24-quant-econ-companion-trigger-purpose-three-branch.md)
**Status:** Living reference list. Entries added as encountered.

---

## Purpose

External references relevant to the QuantEcon program — projects, blogs, papers, or other resources that mirror, contrast with, or inform the project's quant-rigor direction.

This is a **pointer file**, not a literature review. Entries are short. Deeper engagement with any individual reference (summary, comparative analysis, content extraction) happens when a specific QuantEcon program activity needs it.

---

## Entries

### HMA Quant Strategies (Substack)

- **URL:** https://hmaquant.substack.com/s/hma-quant-strategies
- **Added:** 2026-04-24
- **Operator framing (verbatim):** "A quant-focused project that somewhat mirrors the goals of this tool although there are significant deltas."
- **Orientation note (from landing-page fetch 2026-04-24):** Author has formal training in physics and AI plus quant-analyst experience at an institutional broker. Stated specialization is "algorithmic trading, portfolio optimization, and stochastic valuation" — i.e., systematic, model-driven approaches rather than chart-pattern recognition. The landing page does not surface specific asset classes, time horizons, backtests, or code samples; deeper engagement requires fetching individual posts. Apparent contrast with this project: HMA reads as full quant-rigor (factor models, optimization, stochastic methods) operating in an institutional-scale frame; this project is practitioner-heuristic (Minervini Trend Template, VCP, discretionary momentum) operating at retail scale. The deltas the operator referenced are likely along these axes.
- **Recommended action when consulted in depth:** Fetch individual posts (the landing page alone is thin). Enumerate the specific deltas — what HMA does that this project does; what HMA does that this project doesn't; what this project does that HMA doesn't. If the analysis is useful for QuantEcon program decisions, file the comparative summary as a separate document in this folder rather than expanding this entry.

### Kenneth R. French Data Library (Tuck/Dartmouth)

- **URL:** https://mba.tuck.dartmouth.edu/pages/faculty/ken.french/data_library.html
- **Added:** 2026-04-28
- **Operator framing (paraphrased):** "A historical repository which may help with performing analyses." Surfaced as a Research Branch tool candidate.
- **What it is:** Free academic source for U.S. equity factor and portfolio returns. Maintained by Kenneth French (Dartmouth/Tuck). Updated monthly. CSV/TXT downloads. Coverage: 1925 → present; daily/weekly/monthly frequencies (daily increasingly available). Datasets: Fama-French 3-factor and 5-factor, momentum, size/B-M sorted portfolios, 5-49 industry portfolios, breakpoint data, international + emerging market returns.
- **Critical limitation:** PORTFOLIO and FACTOR returns only — NOT individual-stock returns. Cannot power per-ticker backtesting of A+ entries. Useful for factor-regime conditioning, sector-rotation studies, pre-1962 historical extension of harness studies.
- **Methodology change (2025):** Monthly returns now compounded from daily-with-dividend-on-ex-date (previously month-end-with-dividend-reinvested). Pre-2025 vs post-2025 monthly series should be treated as different data products.
- **Strategic placement:** Research Branch tool, not Operational. Reference-only data; promoting any factor-conditioning rule to production methodology requires V2.1 §VII.F. Useful for hypothesis 4 (regime) if reactivated; useful for any "does the framework's edge persist across factor regimes?" study.
- **Recommended action when consulted in depth:** Identify the specific dataset(s) needed (factor model; industry; size/B-M sort; daily vs monthly), download via direct CSV link, store under `~/swing-data/research-cache/french-library/<dataset>-<date>.csv`. Document column semantics + missing-data convention (`-99.99` or `-999`) in the consuming study's method record per V2.1 §IV.B.

### Lo, Mamaysky, Wang (2000) — "Foundations of Technical Analysis"

- **URL:** https://www.cis.upenn.edu/~mkearns/teaching/cis700/lo.pdf (course-hosted PDF; canonical citation: Andrew W. Lo, Harry Mamaysky, Jiang Wang, "Foundations of Technical Analysis: Computational Algorithms, Statistical Inference, and Empirical Implementation," *Journal of Finance* 55(4), 2000, pp. 1705–1765)
- **Added:** 2026-04-28
- **Operator framing (paraphrased):** "A paper that looks into determining chart shapes using analytical methods." Surfaced as a methodology reference candidate for the chart-pattern flag-v1 program.
- **What it is:** The canonical academic paper on algorithmic chart-pattern detection. Method: Nadaraya-Watson kernel regression (Gaussian kernel) to smooth the price series, then geometric pattern detection on local extrema of the smoothed function. Bandwidth chosen via cross-validation, then reduced to `0.3 × h*` per polled professional analysts (authors explicitly admit this is ad hoc, p. 10). Three-step algorithm: (1) define each pattern by local-extrema sequence; (2) construct kernel estimator of price series; (3) scan smoothed series for occurrences.
- **Pattern catalog (10 patterns, 5 pairs):** Head-and-shoulders (HS) / inverse head-and-shoulders (IHS); broadening top/bottom (BTOP/BBOT); triangle top/bottom (TTOP/TBOT); rectangle top/bottom (RTOP/RBOT); double top/bottom (DTOP/DBOT). **Flag, pennant, cup-and-handle, base — NOT covered.** Closest adjacencies to our V1/V2+ list: rectangle ≈ "tight channel" (on our V2+ list); triangle ≈ "pennant" geometrically.
- **Universe + sample:** 350 NYSE/AMEX + 350 Nasdaq stocks, 1962–1996 (34 years, 7 five-year subperiods, stratified by size quintile).
- **Statistical test + findings:** Goodness-of-fit chi-squared on 10-decile conditional vs unconditional 1-day return distributions, plus Kolmogorov-Smirnov with bootstrap percentiles. Several patterns produce statistically significant departures (p<0.001 for HS, IHS on NYSE/AMEX; multiple patterns significant on Nasdaq). **Effect sizes are small — patterns carry incremental information, NOT large profit signals.** Significance varies by subperiod and universe.
- **Authors' stated limitations:** 0.3×h* bandwidth is ad hoc; boundary bias of kernel estimators; "information ≠ profit" — paper does not test trading rules; local polynomial regression suggested as future improvement.
- **Strategic placement:** Reference-only methodology anchor for any future V2+ pattern coverage that goes beyond our current V2+ deferred list. Per V2.1 §VII.F, promoting kernel-smoothing-then-geometric-detection to production methodology requires the source-of-truth correction protocol. Per the operator-drives-agent-serves discipline (QuantEcon companion §"AI's role"), treat Lo et al. as evidence base + methodology reference, NOT as a prescription — academic methodology homogenization is the named risk.
- **Recommended action when consulted in depth:** When V2+ pattern scope expands beyond pennant/cup-and-handle/flat-base/tight-channel to include HS/triangle/rectangle/double-top, use Lo et al.'s geometric definitions (Definitions 1–5 in §II.A) as a starting point for spec drafting. Compare against our V1 rule-based-without-smoothing methodology — the kernel-smoothing-first approach is an alternative the operator explicitly considers (and accepts/rejects) at that point. Replication caveats to surface in any V2+ spec: bandwidth ad-hocery; small effect sizes; sample-period limitations (1962–1996 pre-modern microstructure).

---

## Adding new entries

For each new reference:

- URL or citation
- Date added
- Operator framing (one sentence) if available — quoted verbatim if from the developer, paraphrased with attribution otherwise
- Why relevant (one sentence)
- Recommended action when consulted in depth (one sentence)

Keep entries brief. If a reference warrants extended engagement, that engagement belongs in its own document (e.g., a comparative-analysis file), not in this pointer list.
