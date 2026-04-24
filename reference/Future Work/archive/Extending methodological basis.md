# Comprehensive reference library for an algorithmic momentum swing trading tool

A focused reference pack built for a developer's workflow: every entry below is weighted toward **quantifiable rules, specific formulas, and codeable logic** rather than narrative trading wisdom. Two sources you already have — Minervini's *Trade Like a Stock Market Wizard* and the Qullamaggie guide — supply the discretionary framework; the additions below bridge that framework to deterministic algorithms, back-testable signals, and fundamental risk quantification. The strongest single addition for your stack is pairing **Gray & Vogel's *Quantitative Momentum*** (stock-selection math) with **Clenow's *Stocks on the Move*** (position sizing and regime filters) and **Morales & Kacher's *Trade Like an O'Neil Disciple*** (the pocket-pivot rule, which is arguably the cleanest volume signal in the entire momentum canon). Everything else in this report amplifies those three pillars.

A practical implementation note up front: **survivorship-bias-free data (Norgate or equivalent) is the single biggest technical dependency** of honest backtests in this space. Free sources like yfinance will systematically overstate the performance of every strategy in this document.

---

## A. Books — classic texts, modern practitioners, psychology

### Classic foundations (essential)

**William O'Neil — *How to Make Money in Stocks* (4th ed. 2009).** The CANSLIM system and the origin of the Cup with Handle, Flat Base, Double Bottom, and RS Rating (1–99 percentile). **Codeable content:** cup depth 12–33% with ≤15% handle in upper third; 52-week-high proximity; volume ≥1.5× 50-day average on breakout; 7–8% hard stop rule. **Priority: Essential.**

**Stan Weinstein — *Secrets for Profiting in Bull and Bear Markets* (1988).** The four-stage cycle (basing, advancing, topping, declining) on weekly charts using the 30-week MA. **Codeable content:** Stage 2 = close > 30-WMA AND slope(30-WMA) > 0 AND Mansfield RS > 0; volume ≥2× average on Stage-2 breakout; MRS formula = (price/index)/SMA((price/index),52) − 1. This is the most mechanically implementable stage classifier in the canon. **Priority: Essential.**

**Nicolas Darvas — *How I Made $2,000,000 in the Stock Market* (1960).** The Darvas Box: a new high that holds for 3 days sets the top; the low of the next 3 days sets the bottom. **Codeable content:** N-bar high + 3-bar non-confirmation rule; entry on stop-buy above box top; exit on stop-sell below box bottom. One of the cleanest deterministic trigger mechanisms in trading. **Priority: Highly Recommended.**

**Edwin Lefèvre — *Reminiscences of a Stock Operator* (1923).** Narrative biography of Jesse Livermore; no formulas but the origin of pyramiding, line-of-least-resistance, and pivot-point thinking that underlies most modern momentum methods. **Priority: Adjacent (cultural context, not code).**

**Jesse Livermore — *How to Trade in Stocks* (1940, reissued).** Livermore's own pivot-point rules and position-management framework. **Codeable content:** "pivotal point" = the level where a stock breaks out of a range; scale in only on confirmation; never average down. **Priority: Recommended.**

**Richard Wyckoff — *The Richard D. Wyckoff Method of Trading and Investing in Stocks* (1934).** Source of accumulation/distribution analysis, point-and-figure, and the composite-operator concept. **Codeable content:** spring/upthrust detection at support/resistance, volume-at-price divergence. Practically useful for volume-dry-up and pocket-pivot precursors. **Priority: Recommended.**

### Modern practitioners

**Mark Minervini — *Think & Trade Like a Champion* (2017) and *Mindset Secrets for Winning* (2019).** *Think & Trade* is the direct sequel to *Stock Market Wizard* and contains the most explicit articulation of VCP pivot entries, pyramid rules, and 2:1 minimum reward/risk. *Mindset Secrets* is psychology-focused. **Codeable content from T&TLAC:** 50% rule (sell half on 3× risk, trail the rest), progressive exposure rules based on market health, 4-week closed low as trailing stop. **Priority: Essential** (both); *Master Trader* course material is a paid extension rather than a separate book.

**Gil Morales & Chris Kacher trilogy — *Trade Like an O'Neil Disciple* (2010), *In the Trading Cockpit with the O'Neil Disciples* (2012), *Short-Selling with the O'Neil Disciples* (2015).** The definitive source for the **Pocket Pivot** (volume > max down-volume of prior 10 days, near 10/50-DMA), the **Buyable Gap-Up** (gap > 0.75× ATR(40) on ≥1.5× avg volume, hold above gap-day low), and the **Short-Sale "late-stage failed base"** pattern. **Codeable content:** pocket-pivot volume signature is literally one pandas line; late-stage base count; 7-week flat-base rule. The short-selling book is uniquely valuable because systematic short rules are rare in the momentum literature. **Priority: Essential** (the trilogy as a set; Pocket Pivot alone justifies the first book).

**Oliver Kell — *Victory in Stock Trading* (2021).** 2020 US Investing Champion (+941%). Introduces the **Cycle of Price Action**: seven repeatable chart states (Reversal Extension, Wedge Pop, EMA Crossback, Base 'n' Break, Reconfirming Price Strength, Exhaustion Extension, Wedge Drop). **Codeable content:** each state has specific relationships to the 10- and 21-day EMAs that can be encoded as boolean conditions. It is the single best short modern book for translating multi-timeframe price cycles into discrete states — which is exactly how you'd model it in a state-machine. **Priority: Highly Recommended** (2020–2025 release with genuine traction).

**Jack Schwager — *Market Wizards* (1989), *The New Market Wizards* (1992), *Stock Market Wizards* (2001), *Unknown Market Wizards* (2020).** Interviews. Look specifically at: O'Neil, Minervini, Ryan, Zanger (original series); Dan Zanger in *Stock Market Wizards*; Richard Bargh and Amrit Sall in *Unknown Market Wizards* (2020) both discuss systematic execution rules. **Priority: Recommended** (pattern library, not code).

**Dan Zanger — no canonical book**, but the *Zanger Report* newsletter and his Chartpattern.com material document: breakout ≥1.5× avg volume, avoid extended stocks (>10% from 10-DMA), pyramid only in leading groups, use "crawling-along-the-20-DMA" as an add-up signal. **Priority: Adjacent** (Twitter/newsletter material is inconsistent; use as supplement).

**David Ryan** — no book. Interviews in Schwager and *Investor's Business Daily* archives articulate his checklist-driven, fundamentals-first CANSLIM interpretation. **Priority: Adjacent.**

### Trading psychology (for rule-following discipline)

**Mark Douglas — *Trading in the Zone* (2000).** The canonical text on probabilistic thinking and executing a rule-based system without overriding it. Directly relevant because an algorithmic tool only has value if the human operating it respects the signals. **Priority: Essential.**

**Brett Steenbarger — *The Daily Trading Coach* (2009) and *Trading Psychology 2.0* (2015).** Steenbarger is the most quantitatively-minded trading psychologist; *Trading Psychology 2.0* covers performance metrics, journaling structure, and A/B-testing your own decisions. **Codeable content:** trade-by-trade metrics dashboards, pattern-of-mistakes classification. **Priority: Highly Recommended.**

**Van Tharp — *Trade Your Way to Financial Freedom* (1998, 3rd ed. 2022).** Source of **R-multiples** and **expectancy** as a system-evaluation framework: E = (W × avg_win_R) − (L × avg_loss_R). The R-multiple framework is how your tool should evaluate every trade. **Priority: Essential.**

**James Clear — *Atomic Habits* (2018).** Not trading-specific but directly applicable to building the daily routine (pre-market scan, journaling, post-close review) that disciplined momentum trading requires. **Priority: Adjacent.**

**Denise Shull — *Market Mind Games* (2012).** Neuroscience of emotional decision-making; less systematically codeable. **Priority: Adjacent.**

### Quantitative / systematic (the bridge layer)

**Andreas Clenow — *Stocks on the Move: Beating the Market with Hedge Fund Momentum Strategies* (2015).** The most implementation-ready momentum book for individual developers. **Codeable content (canonical Clenow rules):** rank S&P 500 constituents by `(exp(slope)^252 − 1) × R²` of log-price over 90 days; disqualify if any day moved >15%; disqualify if price < 100-DMA; position size = `(0.001 × account) / ATR(20)` targeting 10 bps daily portfolio vol contribution; only enter new longs when S&P > 200-DMA; rebalance weekly, reposition biweekly. This is a complete, testable specification. **Priority: Essential.**

**Andreas Clenow — *Following the Trend* (2012) and *Trading Evolved* (2019).** *Following the Trend* is the CTA-style trend-following companion (commodities/futures; less relevant to equity swing). *Trading Evolved* is Clenow's Python/Zipline cookbook and is directly useful as an implementation reference. **Priority: Recommended** (both).

**Gary Antonacci — *Dual Momentum Investing* (2014).** The **Global Equities Momentum (GEM)** model: monthly, if SPY 12-month return > T-bill 12-month return, hold whichever of SPY/EFA has higher 12-month return; else hold BND. Two-to-three trades per year, 1974–present has materially outperformed SPY with smaller drawdowns. **Codeable content:** a 20-line implementation. **Caveat:** recent research (Newfound Research "Fragility Case Study: Dual Momentum GEM") shows the strategy is highly sensitive to the exact lookback window — year-to-year spreads of hundreds to thousands of basis points between 6- and 12-month specifications. **Recommendation:** diversify across lookbacks (e.g., average of 3/6/9/12-month signals, "Accelerating Dual Momentum" variant). **Priority: Essential** for the portfolio-overlay layer of your tool.

**Wesley Gray & Jack Vogel — *Quantitative Momentum* (2016).** The academic-to-retail translation of Jegadeesh-Titman. **Codeable content (canonical QMOM rules):** monthly, from the liquid US universe, (1) rank by 12-month return skipping the most recent month — `C[t-21]/C[t-252] − 1`; (2) keep top 20%; (3) within that group, rank by FIP — `sign(TotalRet_12m) × (%negative_days − %positive_days)` — ascending (lowest FIP = smoothest trend); (4) buy top ~50 stocks equal-weighted; (5) seasonal rebalance quarterly at end of Feb/May/Aug/Nov (tax-loss and window-dressing exploitation). This is **the most directly implementable cross-sectional stock-selection system in print**. **Priority: Essential.**

**Meb Faber — *The Ivy Portfolio* (2009) and the research series.** The 10-month SMA timing rule (hold asset if above 10-month SMA, else T-bills) generalizes elegantly to any market-regime filter. **Codeable content:** 10-month SMA regime filter (or 200-day daily equivalent). **Priority: Recommended** (as a regime overlay, not a primary stock selector).

**Perry Kaufman — *Trading Systems and Methods* (6th ed. 2019).** Encyclopedia of indicators and systems; the reference you reach for when you need the exact formulation of Kaufman's Adaptive Moving Average, efficiency ratio, channel systems, etc. **Priority: Recommended** (reference shelf, not linear read).

**Ernest Chan — *Quantitative Trading* (2009), *Algorithmic Trading* (2013), *Machine Trading* (2017).** Practical algorithmic trading methodology including statistical arbitrage and mean-reversion (counter-balance to pure momentum). **Priority: Recommended.**

**Michael Covel — *Trend Following* (2017 expanded ed.).** Performance history and philosophy of systematic trend-followers (Dunn, Seykota, Henry). Light on formulas. **Priority: Adjacent.**

**Curtis Faith — *Way of the Turtle* (2007).** The Turtle rules: Donchian 20-day breakout entry, 10-day opposite-break exit, 2×N (where N ≈ 20-day ATR) stop, position-size units = `(1% × equity) / (N × $-per-point)`. A full trend-following specification that transfers readably to equity swing. **Priority: Highly Recommended.**

**Robert Carver — *Systematic Trading* (2015) and *Leveraged Trading* (2019).** The most sophisticated treatment of position sizing, volatility targeting, and capital allocation across multiple signals. `pysystemtrade` on GitHub is the reference implementation. **Codeable content:** volatility-scaled forecast combination, where each indicator produces a −20 to +20 "forecast" and portfolio weight = `forecast × (target_vol / instrument_vol)`. **Priority: Essential** if your tool will combine multiple momentum signals — which yours likely will.

---

## B. Academic / quantitative research papers

Ordered roughly by implementation priority for a swing trading tool.

**Jegadeesh & Titman (1993), *"Returns to Buying Winners and Selling Losers"*, Journal of Finance 48(1).** The foundational paper. **Rule:** rank by 3-/6-/9-/12-month return, long top decile / short bottom, skip one month, hold 3–12 months. The 6/1/6 and 12/1/12 formations are canonical. **Priority: High.** (SSRN / JSTOR availability.)

**Jegadeesh & Titman (2001), *"Profitability of Momentum Strategies: An Evaluation of Alternative Explanations"*, Journal of Finance 56(2).** Out-of-sample confirmation on 1990s data; confirms momentum is not data-mining. **Priority: High.**

**Asness, Moskowitz & Pedersen (2013), *"Value and Momentum Everywhere"*, Journal of Finance 68(3).** Momentum works across eight asset classes and interacts with value. **Codeable content:** combined 50/50 value+momentum portfolios have materially better Sharpe than either alone. **Priority: High.**

**Carhart (1997), *"On Persistence in Mutual Fund Performance"*, Journal of Finance 52(1).** Introduces the UMD (up-minus-down) momentum factor as the fourth factor. Use for factor-attribution of your tool's returns. **Priority: Medium.**

**Moskowitz, Ooi & Pedersen (2012), *"Time Series Momentum"*, Journal of Financial Economics 104(2).** **Rule:** each asset's own 12-month excess return sign predicts next month's return; scale positions by inverse volatility; diversify across instruments. Different from cross-sectional momentum — both can be combined. **Priority: High.**

**Faber (2007/2013), *"A Quantitative Approach to Tactical Asset Allocation"*, SSRN.** The 10-month SMA rule across five asset classes. The most cited tactical paper for retail; highly implementable. **Priority: High.**

**Faber (2010), *"Relative Strength Strategies for Investing"*, SSRN.** Combines relative strength ranking with the 10-month SMA filter across sectors/asset classes. **Priority: High.**

**Hurst, Ooi & Pedersen (2017), *"A Century of Evidence on Trend-Following Investing"*, AQR.** 137-year backtest, 67 markets — trend-following earns a positive risk premium across regimes. The canonical robustness paper. **Priority: Medium.**

**Daniel & Moskowitz (2016), *"Momentum Crashes"*, Journal of Financial Economics 122(2).** Momentum strategies crash violently in rebound phases after bear markets (March 2009, April 2020, etc.). **Codeable content:** scale momentum exposure by recent realized volatility of the momentum factor itself; reduce exposure when bear-market dummy AND lagged market return are negative. **Priority: High** for a risk layer.

**Barroso & Santa-Clara (2015), *"Momentum Has Its Moments"*, Journal of Financial Economics 116(1).** Scaling momentum exposure by `σ_target / σ_realized_126d` of the momentum factor roughly doubles its Sharpe ratio and eliminates the 2009-style crashes identified by Daniel & Moskowitz. **Priority: High.**

**George & Hwang (2004), *"The 52-Week High and Momentum Investing"*, Journal of Finance 59(5).** Proximity-to-52-week-high is a cleaner momentum signal than 12-month return. **Codeable content:** rank stocks by `close / high_252d`; long top decile. **Priority: High** — this is academic validation for a core Minervini criterion.

**Da, Gurun & Warachka (2014), *"Frog in the Pan: Continuous Information and Momentum"*, Review of Financial Studies 27(7).** Smooth (low-information-shock) momentum outperforms jumpy momentum. **Formula:** FIP = `sign(ret_12m) × (pct_negative_days − pct_positive_days)`. Lowest (most negative) FIP among top-momentum stocks is preferred. Operationalized by Alpha Architect's QMOM ETF. **Priority: High.**

**Asness, Frazzini, Israel & Moskowitz (2014), *"Fact, Fiction, and Momentum Investing"*, AQR.** Rebuts ten common objections to momentum with data — useful for calibrating confidence. **Priority: Medium.**

**Novy-Marx (2012), *"Is Momentum Really Momentum?"*, Journal of Financial Economics 103(3).** Most of the momentum premium comes from the 7–12 month portion of the lookback, not 1–6 months. **Codeable content:** weight older-lookback returns more heavily; specifically, rank by `ret(t−252, t−126)` rather than `ret(t−252, t−21)`. **Priority: Medium-High.**

**Ang, Hodrick, Xing & Zhang (2006), *"The Cross-Section of Volatility and Expected Returns"*, Journal of Finance 61(1).** Idiosyncratic volatility is negatively priced — low-idiovol stocks outperform. Combines well with momentum screens (remove highest-idiovol decile from momentum longs). **Priority: Medium.**

**Hong & Stein (1999), *"A Unified Theory of Underreaction, Momentum Trading, and Overreaction in Asset Markets"*, Journal of Finance 54(6).** Behavioral underpinning for why momentum persists (gradual information diffusion). **Priority: Medium** (theory, not rules).

**Daniel, Hirshleifer & Subrahmanyam (1998), *"Investor Psychology and Security Market Under- and Overreactions"*, Journal of Finance 53(6).** Overconfidence/self-attribution-bias model of momentum. **Priority: Medium.**

**Lee, Sun, Wang & Zhang (2019), *"Technical Analysis in the Chinese Stock Market"*, and ongoing SSRN momentum-factor updates (2020–2025)** — recent work shows momentum weakened post-2000 in developed markets but remains robust internationally and when combined with quality (Asness *"Quality Minus Junk"*, 2013/2019). **Priority: Medium.**

**Corey Hoffstein / Newfound Research whitepapers (ongoing)** — "Tranching, Trend, and Mean Reversion," "Fragility Case Study: Dual Momentum GEM," "Two Centuries of Momentum." Not peer-reviewed but among the highest-quality practitioner research available; `blog.thinknewfound.com`. **Priority: High** for risk-aware implementation.

**Alpha Architect research library (alphaarchitect.com)** — Gray, Vogel, and collaborators publish continuously on momentum, value, trend, and quality. The blog operationalizes academic research into screener-ready rules. **Priority: High** (effectively the bridge between SSRN and a Python notebook).

---

## C. Online methodologies with documented quantifiable rules

### Stockbee / Pradeep Bonde (stockbee.blogspot.com)

The Stockbee catalog is one of the most under-appreciated free resources in swing trading, with numeric rules documented in blog posts and X threads.

**Momentum Burst (4% breakout).** TC2000 formula `c/c1 > 1.04 AND v > v1 AND v > 100000`. Core qualifiers ("2LYNCH"): not up 2 days in a row pre-breakout, linear prior uptrend, young trend (1st–2nd breakout from base), narrow-range pre-breakout day, shallow consolidation, high-volume confirmation, close near high of day.

**Episodic Pivots (EP).** Three elements: neglect + game-changing catalyst + rapid repricing on heavy volume. Intraday scan: `c/c1 > 1.04 AND v > 3 × avgv50 AND v >= 300000`. Earnings-EP ideal: ≥100% QoQ earnings growth AND ≥5% sales growth (some versions reverse: triple-digit sales + 5% earnings). Entry at pre-market or at open; stop at EP-day low; scale out in parts; 20%+ profit target.

**Growth screens (MAGNA / CAP 10×10 / "Bucket" filters).** Specific quarterly thresholds: sales growth ≥39% (Bucket 1) or ≥99% (extreme), 2-quarter average sales ≥39%, annual sales ≥$25M, price ≥$10, 50-day average volume ≥100k–200k, market cap ≤$11B, IPO within 10 years. These are all deterministic filters directly codeable against any fundamental-data API.

### IBD / CANSLIM ratings (investors.com, MarketSurge)

**RS Rating formula** (community-verified approximation since IBD doesn't publish the exact formula): `StrengthFactor = 0.4 × ROC(C,63) + 0.2 × ROC(C,126) + 0.2 × ROC(C,189) + 0.2 × ROC(C,252)`, then percentile-rank across universe to 1–99. **Target ≥ 80.** Open-source implementation: `skyte/relative-strength` on GitHub.

**Other IBD ratings:** EPS Rating (combines 2 most recent quarters' EPS growth with 3–5y annual rate, percentile-ranked); SMR Rating A–E (sales + margins + ROE); Accumulation/Distribution Rating A–E (13-week weighted price-volume); Composite Rating 1–99 (weighted blend of the above). **Screening targets:** EPS ≥80, RS ≥80, Composite ≥90, Acc/Dis = A or B.

**85-85 list criterion**: `EPS ≥ 85 AND RS ≥ 85 AND within 15% of 52-week high`. Directly implementable as a screen.

**IBD Market School / Follow-Through Day rules** — quantitative market-regime detection: after a correction, a follow-through day = major index closes up ≥1.5% on higher volume than prior day, 4–10 days into a rally attempt. Reduces trading exposure when distribution days ≥5 in 25 sessions. **Codeable** as a market-state boolean.

### Qullamaggie (qullamaggie.com, @qullamaggie on X)

**Stair-step continuation / bull flag.** Three-step structure: 30–100%+ prior move in 1–3 months → 2-week-to-2-month orderly pullback riding the 10/20/50-day MA → range-expansion breakout. **Scan:** top 1–2% of market by 1-/3-/6-month % gain; ADR ≥ 5–6%; dollar volume filter $1.5M minimum, often $20M+. **Entry:** opening range high (1-, 5-, or 60-min). **Stop:** low of day; stop width must not exceed one ADR. **Exit:** trail 10- or 20-day MA.

**Qullamaggie Episodic Pivot.** Gap ≥10% on major catalyst (earnings, FDA, guidance), massive volume (stock trades its average daily volume in first 15–20 minutes), ideally from a neglected stock. Same entry/exit mechanics as the flag breakout.

**Parabolic short.** Stock up 50–100%+ in days for large caps (300–1000%+ for small caps); 3–5+ consecutive up days. Short on opening range low, stop at day high, target 10/20-day MAs. Lower reward/risk (5–10R) than longs.

The **ADR% formula** he uses is now canonical in the momentum community: `ADR%_20 = 100 × (mean(H/L, 20) − 1)`.

### Other documented systematic approaches

**Brian Shannon — *Technical Analysis Using Multiple Timeframes* / AlphaTrends.** The canonical multi-timeframe VWAP-anchored framework used by many current momentum swing traders. **Codeable content:** anchored VWAP from earnings date / breakout day / swing low; stock reclaiming AVWAP on volume = long signal.

**TraderLion (traderlion.com).** Community content aggregating Minervini/Ryan/Morales/Kell methodologies with specific setup definitions and chart examples. Useful as a free teaching aggregator; paid content has audited championship performers.

**Finviz screening filters** — community-documented CANSLIM-style screens using native filters (e.g., Price > $10, Avg Vol > 500k, RSI 14 50–70, 50-DMA above 200-DMA, 52-week-high proximity). `finvizfinance` Python library scrapes these.

**TC2000 / Worden forum** — the most complete open repository of momentum scan PCFs (personal criteria formulas), including reverse-engineered IBD RS approximations, Minervini Trend Template, ADR%, VCP pivot detection.

**TradingView Pine Script community** — searchable open-source scripts for Mansfield RS, IBD RS, Minervini Trend Template (multiple versions), Darvas Box, Pocket Pivot (two named scripts), Weinstein Stage indicator, anchored VWAP.

**ChartMill** — publishes its Weinstein Stage indicator and Stage Length indicator with defined rules; useful as a sanity check against your own stage classifier.

**Corey Hoffstein — *Flirting with Models* podcast + blog.** The most rigorous practitioner-accessible discussion of momentum/trend implementation choices (lookback diversification, ensemble strategies, crash mitigation).

**Alpha Architect blog (alphaarchitect.com/blog).** Continuously publishes operationalizable research on momentum, value, trend, and quality. The "Quantopian-style" Python code is often directly embedded.

**Top Traders Unplugged** podcast — CTA-heavy but relevant for trend-following and systematic risk management at portfolio level.

**Chat with Traders** (Aaron Fifield, active 2015–2021, archival) — contains interview episodes with Qullamaggie (#112, #183), PJ Sutherland (#72, systematic swing), Richard Moglen, and several USIC competitors.

**Reddit r/algotrading consensus on momentum (2023–2025)** — the practical retail view settles on: 12-1 cross-sectional momentum + trend filter + vol-targeting + ensemble of lookbacks as the robust template, echoing Newfound Research. Treat community posts skeptically but the consensus architecture is sound.

---

## D. Specific indicators and metrics — the implementation core

This section is the densest block of codeable content in the report. All formulas verified against primary sources.

### Relative strength

**IBD RS Rating (1–99):** `StrengthFactor = 0.4 × ROC(C,63) + 0.2 × ROC(C,126) + 0.2 × ROC(C,189) + 0.2 × ROC(C,252)`; percentile-rank across universe. Target ≥80 (leaders); ≥90 (elite). Reference impl: `skyte/relative-strength`.

**Mansfield Relative Strength:** `MRS = ((Price_stock/Price_index) / SMA((Price_stock/Price_index), 52)) − 1` on weekly bars. MRS > 0 confirms Stage 2. One-line in pandas.

**Multi-timeframe momentum rank:** compute `ROC(C, 21/63/126/252)`, percentile-rank each across universe, average ranks. Captures cross-sectional consensus across lookbacks — diversifies against the lookback-specification fragility documented by Newfound.

**RSNH (Relative Strength at New High):** `rs_line = close / index_close`; signal = `rs_line[t] == max(rs_line[t-N:t])` ideally **before** price makes a new high. This is Mike Webster's "blue dot" and precedes many of the biggest breakouts in MarketSurge data.

### Volatility / range

**ADR% (Qullamaggie/TheScrutiniser):** `ADR%_20 = 100 × (mean(H/L, 20) − 1)`. Threshold >4% required for momentum candidates; >5–6% preferred.

**ATR (Wilder, 14):** `TR = max(H−L, |H−C_prev|, |L−C_prev|)`; `ATR = Wilder_smooth(TR, 14)`. Use for absolute-dollar stop distance and Clenow position sizing.

**Volatility contraction (VCP) detection** — no canonical algorithm; the consensus pipeline used by open-source repos is: (1) pre-filter with Minervini Trend Template; (2) detect pivots via `scipy.signal.argrelextrema(order=5..10)` or `find_peaks`; (3) compute contraction widths `(high_i − low_i)/high_i` for each swing; (4) check that the last 2–6 contractions are monotonically tightening, each ≤ ~75% of prior; (5) confirm VDU: rolling 5-day mean volume < 50% of 50-day mean. Reference implementations: `marco-hui-95/vcp_screener`, `shiyu2011/cookstock`, `clairetsoi1129/stock-screener`, `crankycandle/volatility-contraction-pattern`. Expect to tune per-regime — VCP is inherently fuzzier than trend-template logic.

### Volume

**Volume dry-up (VDU):** `vol_today < 0.5 × SMA(vol, 50)`, often combined with a rolling 5-day version for robustness.

**Pocket Pivot (Morales & Kacher):** `vol_today > max(vol where close<close.shift(1) over prior 10 bars)`. Additional rules: close > open; price near 10-DMA or 50-DMA; stock in constructive base or uptrend; avoid if wedging or extended >5–10% from 10-DMA.

**Relative volume (RVOL):** `vol / SMA(vol, N)`. Useful at multiple scales: intraday (5-min RVOL for early-session setups), daily (for breakout confirmation ≥1.5–2×), weekly (Stage 2 ≥2×).

**Accumulation/distribution days** (market-health proxy): count days where major index closed down >0.2% on higher volume than prior day, within a 25-session window. ≥5 = warning signal.

**OBV, CMF(20), A/D Line (Chaikin)** — all one-liners in `pandas-ta` or `talib`.

### Trend / stage classification

**Minervini Trend Template (8 conditions, all must be true):**
1. `C > SMA(150) AND C > SMA(200)`
2. `SMA(150) > SMA(200)`
3. `SMA(200)[t] > SMA(200)[t−22]` (rising ≥1 month)
4. `SMA(50) > SMA(150) AND SMA(50) > SMA(200)`
5. `C > SMA(50)`
6. `C >= 1.30 × low_52w`
7. `C >= 0.75 × high_52w`
8. `RS_rating >= 70` (80+ preferred)

**Weinstein stage classification:**
| Stage | Rule |
|---|---|
| 1 Basing | `abs(slope(WMA30)) ≈ 0` AND recent Stage-4 history |
| 2 Advancing | `C > WMA30 AND slope(WMA30) > 0 AND MRS > 0` |
| 3 Topping | slope(WMA30) flattening; RS rolling over |
| 4 Declining | `C < WMA30 AND slope(WMA30) < 0` |

### Momentum scoring

**Jegadeesh 12-1:** `MOM = C[t−21]/C[t−252] − 1`.

**Clenow momentum:** `score = ((exp(slope(log_C, 90))^252) − 1) × R²`, where slope/R² from `scipy.stats.linregress`. Disqualify: stock < SMA(100), any 1-day move > 15% in lookback, S&P < SMA(200).

**FIP (Frog-in-the-Pan):** `FIP = sign(ret_252) × (pct_neg_days − pct_pos_days)`. Lower (more negative) = smoother = preferred.

**Novy-Marx "intermediate" momentum:** `ret(t−252, t−126)` — the 7-to-12-month return slice — has stronger out-of-sample predictive power than the full 12-1.

### Pattern / breakout detection

**Cup with Handle (O'Neil):** left-high ≈ right-high (within 5%); cup depth 12–33%; U-shape (fit quadratic, positive coefficient); duration 7–65 weeks; handle forms in upper third, depth ≤15%, duration 1–4 weeks; pivot = handle high + $0.10; breakout volume ≥1.5× avg.

**Flat base:** ≥5 weeks duration, depth ≤15%, follows a Stage-2 move.

**Double bottom:** two troughs within 2–3% separated by intermediate peak; breakout = close above intermediate peak.

**High-tight flag (Qullamaggie favorite):** pole ≥90–120% in 4–8 weeks; flag pullback ≤25%.

**Darvas Box:** new N-bar high not exceeded for 3 consecutive days sets top; lowest low of next 3 days sets bottom; entry = stop-buy above top, stop = below bottom.

**NR7 / inside day:** `range[t] == min(range[t-6:t+1])`; inside day = `H[t]<H[t-1] AND L[t]>L[t-1]`. Crabel-style range-expansion trigger the next day.

### Risk / position sizing

**Fixed-R sizing:** `shares = (risk_dollar) / (entry − stop)`; R typically 0.25–1.0% of equity per trade.

**Volatility-normalized (Clenow):** `shares = (0.001 × account) / ATR(20)` → each position contributes ~10 bps of expected daily portfolio P&L.

**Barroso-Santa-Clara vol-scaled momentum:** `exposure = min(1, σ_target / σ_realized_126d)` applied to a standard momentum factor. Roughly doubles Sharpe and eliminates crashes.

**Kelly fraction (use ≤25% fractional):** `f* = W − (1−W)/R`, where W = win rate and R = avg_win/avg_loss.

**Performance metrics** — Van-Tharp R-framework: expectancy, profit factor, max drawdown, MAR/Calmar, Sharpe, Sortino, tail ratio. Reference libraries: `empyrical`, `quantstats`, `pyfolio-reloaded`.

### Fundamental risk quantification

This is an area where momentum tools are commonly weak. Consider encoding:

- **Earnings quality:** QoQ EPS growth, YoY EPS growth, sales growth trend (require both accelerating, Stockbee's style).
- **Debt/liquidity:** debt-to-equity, current ratio, interest coverage — simple thresholds (D/E < 2, current > 1.5) filter out balance-sheet blow-ups.
- **Float/shares-short:** short-interest ratio, float turnover; Qullamaggie uses low-float as positive for momentum but it also amplifies gap risk.
- **IPO age:** <10 years per Stockbee CAP 10×10; newer IPOs have cleaner trends but less fundamental history.
- **Earnings date proximity:** never enter a swing position within 5 trading days of earnings unless the setup is *the* earnings catalyst itself (EP). Make this a hard rule in your tool.
- **Gap risk (ATR-normalized):** if a stock's ADR > 8% or typical overnight gap > 1× ATR, reduce position sizing accordingly.

---

## E. Open-source tools, libraries, and frameworks

### Technical indicators
**TA-Lib** (C + Python binding) remains the gold standard for reference values — 150+ indicators, 61 candlestick patterns. **pandas-ta** is the ergonomic DataFrame-native choice (`df.ta.strategy(...)`), with an optional TA-Lib backend. **finta** is pure-pandas and avoids the C dependency. For bit-exact reproducibility on a developer-controlled stack, prefer hand-rolled pandas or finta over TA-Lib (TA-Lib has warmup-period quirks like Wilder-seeded RSI that differ from `.ewm`).

### Data
**Norgate Data** ($630/yr Platinum) — **survivorship-bias-free US equities with delisted tickers and historical index constituents**, native Python package (`norgatedata`), native Zipline-Reloaded bundle. This is the single most important paid dependency for honest backtests. **Polygon.io** and **Tiingo** are reasonably priced tick+aggregate providers. **yfinance** is acceptable for live scanning but not for backtesting. **FMP / Financial Modeling Prep** or **Tiingo fundamentals** for the EPS/sales/margin fields CANSLIM requires. **finvizfinance** scrapes Finviz for screener output. **Alpaca SDK** or **ib_insync** for execution.

### Backtesting
**vectorbt / vectorbtpro** — fastest for parameter sweeps and factor research (Numba-vectorized). **zipline-reloaded** + Norgate bundle — the idiomatic choice for equity factor / long-short momentum research with dynamic universes (Pipeline API). **backtrader** — event-driven, multi-timeframe, broker-integrated (IB, Alpaca, Oanda) — best choice for going live with a swing-trading rule set. **backtesting.py** — lightweight prototyping. **bt** — portfolio-level weight rebalancing. **Nautilus Trader** — production-grade Rust core (steep learning curve). **LEAN / QuantConnect** — full research-to-live stack with cloud and a large strategy library. **FinRL** — reinforcement-learning experiments only. **StrateQueue** — one-command deploy layer that bridges vectorbt/backtrader/backtesting.py/zipline-reloaded to Alpaca/IB in production.

### Momentum-specific Github repositories (the highest-leverage list)

| Repo | What it gives you |
|---|---|
| `skyte/relative-strength` | IBD-style RS percentile ranker, outputs `rs_stocks.csv`, `rs_industries.csv` |
| `icedevil2001/mark_minervini_stock_screener` | Streamlit app, full 8-criteria Trend Template + RSI/MACD/ADX/BB/Stoch/ATR/OBV |
| `douglasg-fintec/stocksscreener` | Python Minervini Trend Template |
| `ktshen/screener` | RS ranker + Trend Template + DTW similar-trend scanner |
| `marco-hui-95/vcp_screener` | Full VCP scan via Finviz + yfinance, Excel output |
| `shiyu2011/cookstock` | VCP detection + Stage-2 filter + news sentiment |
| `clairetsoi1129/stock-screener` | VCP screener |
| `crankycandle/volatility-contraction-pattern` | VCP with chart rendering |
| `kanwalpreet18/canslimTechnical` | Cup-with-handle pattern detection |
| `HumanRupert/marketsmith_pattern_recognition` | Cup-handle backtest using MarketSmith API + zipline-reloaded + pyfolio |
| `rawsashimi1604/Stock_EXPOREG` | Clenow exponential regression momentum ranker |
| `vakilp/darvasBox` | Darvas box (MATLAB/Octave) |
| `fmzquant/strategies` | Multi-language collection including Darvas, momentum |
| `avinashbarnwal/Momentum-Strategy` | Gray & Vogel QMOM Python implementation |
| `stefan-jansen/machine-learning-for-trading` | Companion code to *ML for Algorithmic Trading*; extensive momentum/factor content |
| `robcarver17/pysystemtrade` | Full systematic trend-following platform; production-grade position sizing and risk overlays |
| GitHub topic `minervini` / `canslim` | Discovery starting points |

### Analytics
**QuantStats** for one-line tearsheets; **pyfolio-reloaded** for round-trip + factor attribution; **empyrical-reloaded** for primitive risk metrics; **alphalens-reloaded** for factor-return research; **riskfolio-lib** / **skfolio** for portfolio optimization overlays.

### Pattern toolkit
`scipy.signal.argrelextrema` and `find_peaks` for pivot detection (Darvas, VCP, cup-handle); `scipy.stats.linregress` for Clenow regression and MA slope tests; `numpy.polyfit` for quadratic-fit cup roundedness; `ruptures` for regime change-point detection; `hmmlearn` for HMM stage-classification; `tslearn` / `dtaidistance` / `fastdtw` for DTW-based pattern similarity.

---

## F. Emerging and 2023–2025 developments

**Oliver Kell's Cycle of Price Action** has arguably been the most influential *new* systematic framework to gain momentum-community traction since Qullamaggie's material. Kell's 2020 USIC win (+941%) and subsequent 2021 book translate multi-timeframe CANSLIM execution into seven discrete chart states — which is unusually friendly to state-machine implementation in code. **Substantive, not hype.**

**US Investing Championship recent winners and top finishers** (all use variants of CANSLIM/Minervini momentum, all trade real verified accounts): Oliver Kell (2020, +941%); Mark Minervini himself (2021, +334%); Roy Mattox (2022); Tanmay Khandelwal of TwoXCapital (2023, +129%, $1M+ stock division); Goverdhan Gajjala (2023 stock division, +805%, Minervini Private Access client); Aryan Khandelwal (2024 leader, +143% nine-month); J Law of Hong Kong (2025 first-half leader, +184%). Minervini's MPA client list has dominated three of the last five years. The community is mostly unified around a CANSLIM/Minervini base, meaning the *Trade Like a Stock Market Wizard* + *Think & Trade Like a Champion* foundation remains the current state of the art for discretionary swing trading — not superseded.

**Platforms that emerged or gained market share 2023–2025:**
- **MarketSurge** (replacement for MarketSmith by IBD, launched 2023) — includes Pattern Recognition, RSNH/"blue dot," and the full IBD rating suite; API access is limited but data can be imaged/scraped with care.
- **Deepvue** — momentum-swing-specific screener built around Minervini/Qullamaggie workflow, with pre-built templates for VCP, ADR filters, RS. Closed API but useful as a visual cross-check.
- **TrendSpider** — AI chart-pattern recognition including VCP and cup-handle; anchored VWAP automation. Has a public API for alerts.
- **TraderLion** — community platform aggregating USIC competitor content, systematic setup definitions.
- **FinChat, Koyfin, Stratosphere** — fundamental data layers more suited to CANSLIM's EPS/sales/margin requirements than Bloomberg terminal alternatives.
- **TradingView Pine Script v5 + Alerts Webhooks** — has become production-capable for low-frequency swing signals.

**Recent research (2020–2025) worth incorporating:**
- Newfound Research's ongoing "lookback diversification" series establishes that ensemble-of-horizons (6/9/12-month momentum averaged) materially reduces single-point-specification risk.
- Post-2022 momentum research confirms the strategy survived the 2020 crash and 2022 bear market with vol-scaled implementations (per Barroso-Santa-Clara framework) performing far better than naive momentum.
- **Factor momentum** (Ehsani & Linnainmaa 2022, "Factor Momentum and the Momentum Factor," Journal of Finance) — argues that individual-stock momentum is substantially a manifestation of factor momentum; has implications for combining momentum with quality/value factors.
- Machine-learning momentum papers have proliferated but few produce robust out-of-sample retail-implementable rules that beat the simple 12-1 + FIP + vol-scaling stack. Treat as research area, not production.

**What's mostly hype (flag skeptically):** LLM-based "AI trading tools" marketed 2023–2025 almost uniformly lack audited performance; most are marketing wrappers over ChatGPT for news summarization. Crypto-momentum-on-equities content. Any Twitter account marketing "100% win rate" swing systems. Discord signal services without real-money verified track records. The US Investing Championship and Minervini MPA are the credibility gold standards — verify any 2023–2025 influencer's performance against that bar.

---

## Putting it together — a synthesized implementation blueprint

The research above converges on a layered architecture that maps cleanly to your tool's pipeline:

**Screening layer.** Start with the Minervini Trend Template (8 hard booleans) as a universe filter — this is the single most validated, codeable, quantifiable gate in the entire literature. Add IBD-style RS percentile rank (skyte's implementation), ADR% >4%, average daily dollar volume >$1M, market cap >$300M, IPO age >6 months. This gates a ~5000-stock universe down to ~50–200 candidates on most days.

**Pattern/trigger layer.** Run parallel detectors on each candidate: VCP (pivot-based), Pocket Pivot (volume signature), Darvas Box, Cup-with-Handle, Buyable Gap-Up, Stockbee Episodic Pivot. Each emits a boolean-plus-pivot-level. Score signal strength by Clenow momentum × FIP × volume-surge — this aggregates the academic (Jegadeesh, Da/Gurun/Warachka) with the practitioner (Minervini, Morales/Kacher) consistently.

**Risk/sizing layer.** Every signal produces an explicit stop (day low, pivot low, or 2×ATR — whichever is tightest). Position size via Van Tharp R-framework with 0.25–1.0% risk per trade, capped by Clenow's volatility-normalized ceiling. Apply Barroso-Santa-Clara vol-scaling at the *portfolio* level: reduce gross exposure when realized momentum-factor vol is elevated. Hard block on entries within 5 trading days of earnings unless the setup *is* an earnings EP.

**Regime layer.** Apply a market-health filter before new entries: S&P above 200-DMA (Clenow), accumulation/distribution day count over trailing 25 sessions, follow-through-day state (IBD Market School). Suspend new longs when regime is unfavorable; existing positions managed per their individual stops.

**Execution/management layer.** Oliver Kell's Cycle of Price Action states drive trade-management decisions (first profit-take on Exhaustion Extension, add on EMA Crossback, etc.). Minervini's "sell half at 3× risk" + 4-week-closed-low trail gives a robust default exit. Morales/Kacher's "7-week flat base" rule for late-stage warning. Track every trade as R-multiples for Van-Tharp-style expectancy analysis.

**Psychology and process layer.** Douglas and Steenbarger inform the discipline to *not override the algorithm*. Steenbarger 2.0's journaling discipline + Van Tharp's systematic metrics + Clear's habit architecture give the daily/weekly review structure that makes an algorithmic tool actually usable by a human.

The single biggest leverage from the research: **the literature you already have (Minervini + Qullamaggie) is world-class on discretionary setup identification. The gap you're filling is the quantitative factor-research layer (Gray-Vogel, Clenow, Antonacci, Faber, Carver) and the risk-overlay layer (Barroso-Santa-Clara, Newfound). Adding those two bodies to your existing foundation gives a swing trading tool with institutional-grade architecture — a combination vanishingly few retail tools actually execute.**