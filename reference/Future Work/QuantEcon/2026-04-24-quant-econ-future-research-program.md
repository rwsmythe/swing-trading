# Quantitative Economics Integration — Future Research Program

**Date:** 2026-04-24
**Audience:** Future Claude Code / Codex implementation sessions and the developer
**Status:** Forward-looking strategic document; not near-term guidance
**Companion / authority:** `2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` (V2.1) governs near-term work; this document informs research-program evolution after V2.1 tranches 1–3 complete

---

## How to use this document

This document captures a structured positioning exercise conducted 2026-04-24 to explore how quantitative-economics theories, principles, and methods might inform swing-trading methodology *after* the near-term bifurcated-architecture work is in stable operation.

**This document is not actionable in the near term.** Do not attempt to initiate the work described here until V2.1 tranches 1–3 have produced at least one completed decision-grade study and the operational branch has continued its Phase 3e progression.

**Relationship to V2.1:**

- V2.1 governs. Nothing in this document overrides V2.1's governing design principles, minimum-viable posture, or tranche sequencing.
- This document is intended to guide the *evolution* of the research program once V2.1's initial posture has matured — roughly the 18-month-and-beyond horizon.
- The four themes described here become candidate research directions when the research branch has enough infrastructure and enough evidence from the first few studies to justify broader quant-econ integration.

**Read in this order for context:**

1. `2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md` (V2.1 governing strategy)
2. `CLAUDE.md` (current repo state)
3. This document
4. `reference/Future Work/` predecessor documents (SRC, CRIT, REBUTTAL, prior proposals) only if historical context is specifically needed

---

## Purpose and scope

The question motivating this exercise: *Can quantitative economics theories, principles, and methods be used as another means to help inform these swing trading methodologies?*

The answer: **yes, but selectively, with specific traps to avoid, and with a dependency structure that matters more than the individual tools.**

This document captures:

- four positioning questions whose answers frame the quant-econ integration
- the composite profile those answers produce
- four strategic themes that emerge from the profile
- the dependency structure among the themes
- a proposed sequencing and rough timeline
- failure modes and open uncertainties

This document does **not** contain:

- specific implementation instructions for any theme
- method-record entries for the quant-econ methods discussed
- code or pseudocode
- near-term research priorities (those are V2.1 §V.D)

---

## Positioning assumptions (baseline)

The positioning exercise assumed the following baseline project state, which is correct as of 2026-04-24 and consistent with V2.1:

- Operational branch shipped through Phase 3d, 504 fast tests green on `main`
- Research branch does not yet exist as a distinct entity
- Time budget ≈4–8 hours/week sustained, 70/30 production/research currently
- Bifurcated architecture per V2.1
- Minimum-viable posture per V2.1 §III.3 and §IX

If any of these assumptions has changed by the time this document is consulted, the analysis below may need revisiting.

---

## The four positioning questions

### Q1 — What does "performance" mean in this future-state question?

Ranked priorities:

1. Expectancy (better edge per trade)
2. Capital efficiency (more capital deployed productively)
3. Consistency (less regime dependence)
4. Drawdown control (same edge, less pain)

**Characterization.** Return-maximizer posture, not risk-minimizer. Expectancy + capital efficiency at the top is internally consistent — each pairs naturally with the other. Drawdown at #4 is explicitly a risk being accepted, not ignored.

**Implication.** Quant-econ tools that improve edge or deploy capital more efficiently are priority. Kelly-family sizing theory becomes central rather than peripheral because it addresses the exact priority dimension (#2).

**Caveat to surface later.** Drawdown tolerance and capital efficiency interact non-linearly — a strategy with 20% expected drawdown at 1x leverage has ~40% at 2x, and the psychological threshold for continuing to trade a system degrades faster than linearly (Benartzi-Thaler on myopic loss aversion). The #4 ranking is valid but its consequences deserve attention at deployment time.

### Q2 — Why does momentum work?

Ranked explanations:

1. Behavioral (cognitive biases, slow to change)
2. Adaptive (ecosystem of competing strategies)
3. Risk-based (compensation for crash risk)
4. Frictional (slow information diffusion)

**Characterization.** Behavioral + Adaptive dominant is the closest match to the O'Neil / Minervini / Qullamaggie implicit worldview. Edge is rooted in durable cognitive structure; specific methods exploiting that edge decay as the ecology changes.

**Note on ranking interpretation.** Rankings are relative, not absolute — low rank does not imply low absolute credence. Frictional at #4 still has non-trivial explanatory weight, especially for the setup-specific methods already in operational use (pocket pivots, VCPs, buyable gap-ups); those methods are actually best-justified by the frictional frame even though it ranks lowest.

**Implications for future research:**

- Method decay is a first-class phenomenon, not a failure — expect 20–40% of production methods per decade to require demotion for ecology-change reasons unrelated to original validity. Demotion pathway (V2.1 §VII.E) is a mainline process, not an exception handler.
- Crowding metrics become relevant even though risk-based ranks low — crowding is the primary decay mechanism under behavioral+adaptive.
- Edge is vulnerable to: widespread retail adoption, algorithmic replication of pattern detectors, cognitive-regime shifts (e.g., 0DTE flows altering short-term price structure).
- Edge is robust to: macro regime changes per se, interest-rate cycles, most risk-based-model-flagged events.

### Q3 — Quant-econ as method library, theoretical anchor, or hybrid?

Answer: **Hybrid with explicit division (Posture C).**

**Characterization.** This is the structurally correct answer for the project because it maps onto the bifurcated architecture. Pure method-library (Posture A) would subordinate the working practitioner methodology; pure theoretical-anchor (Posture B) would waste directly-usable quant-econ infrastructure.

**Layer assignments:**

*Posture A layers (quant-econ as method library — directly import and adapt):*

- Sizing and capital allocation — Kelly-family theory; directly addresses Q1 #2; highest-leverage A layer
- Volatility scaling and exposure management — Barroso-Santa-Clara and crash-risk literature; methods work even if Q2 #3 ranking of risk-based is low
- Performance attribution and factor decomposition — Fama-French-Carhart and AQR extensions; diagnostic tool, not trading rule
- Statistical evaluation infrastructure — bootstrap, block-bootstrap, White's reality check, Hansen SPA, deflated Sharpe, purged k-fold CV

*Posture B layers (quant-econ as theoretical anchor — theory evaluates empirically-sourced methods):*

- Trigger and pattern detection — practitioners have the edge; theory informs decay expectations
- Universe construction and ranking — practitioner RS rules are the baseline; momentum theory (Jegadeesh-Titman, Moskowitz-Ooi-Pedersen) provides theoretical anchor
- Regime framing — theory provides vocabulary (distribution days, breadth deterioration); practitioners provide operational implementations
- Operator workflow and psychology — entirely practitioner and behavioral-finance territory; quant-econ contributes little here

**Tension to name.** The Posture A sizing work is where Q1's ranking creates the most pressure. Kelly requires accurate expectancy estimation, and biased expectancy estimates produce dangerous leverage errors. This isn't a reason to avoid Kelly; it's a reason to commit to statistical-evaluation infrastructure (also Posture A) *before* sizing work — so the inputs to Kelly are defensible.

### Q4 — Mathematical complexity tolerance, operational vs research

Answer: **L2 operational / L3 research, soft — willing to push L2→L3 and L3→L4 in research, start conservative, find aggressive failure point, move back.**

**Complexity levels:**

- L1 — Transparent rules (threshold comparisons, arithmetic)
- L2 — Transparent composites (weighted primitives, conditional logic)
- L3 — Interpretable models (parametric models with understandable outputs)
- L4 — Black-box outputs with provenance (validated but not in-the-moment reconstructable)

**Characterization.** The "start conservative, find failure point, move back" posture is structured exploration, not just cautious default. It implies research-branch design that lets L3/L4 methods run for *comparison* against L1/L2 baselines — the comparison is the research output, not just the method.

**Consequences:**

- L3/L4 research work is justified even before operational adoption is certain; running a Hamilton filter in research isn't wasted effort if production stays at L2 regime detection — it's how the L2 choice is earned.
- The failure mode guarded against is *premature sophistication* — adopting complexity before simpler baselines have been exhausted.
- Under Q2's behavioral+adaptive worldview, simpler methods with clearer decay signatures are more diagnosable than complex methods whose decay looks like parameter instability. This reinforces the conservative operational default.

**Asymmetric direction worth planning for.** "Start conservative, move up if warranted" is safe and usually correct. The opposite movement — starting complex in an area where simple methods work, running L1 simplification of an L2 production method in shadow mode to test whether the L2 complexity earns its keep — is also valuable. This is the mechanism by which long-running quant systems avoid complexity accretion over years. V2.1's demotion pathway currently handles demotion in favor of *better* methods but not demotion in favor of *simpler* methods that perform equivalently. Worth keeping as a future governance question.

---

## Composite profile

The four answers compose into a distinctive internally-consistent profile:

- **Return-focused** (expectancy + capital efficiency dominant)
- **Behavioral-adaptive worldview** (durable edge via cognitive structure, decaying methods via ecology)
- **Bifurcated quant-econ integration** (method library in sizing/evaluation layers, theoretical anchor elsewhere)
- **Methodologically sophisticated but operationally disciplined** (aggressive research, conservative production, willing to recalibrate based on real-world results)

**What the composite points toward (ordered by strength of support):**

1. **Kelly-family capital efficiency work.** Directly addresses Q1 #2; fits Q3 Posture A sizing; sits at L2-L3 matching Q4. Highest-leverage area.
2. **Method-decay detection infrastructure.** Q2 worldview predicts methods decay; quant-econ has mature tools (structural break tests, CUSUM, rolling z-scores, crowding metrics). Low operational risk, high diagnostic value.
3. **Performance attribution via factor decomposition.** Answers "is my edge real?" — existentially important before Kelly work because Kelly-sized positions on false alpha are ruinous.
4. **Setup-quality improvement via theoretical anchoring.** Q3 Posture B applied to existing practitioner methods; lower leverage because practitioner methods are already good, but improves extension rather than replacement.

**What the composite points away from:**

- Regime-switching models as operational tools (Q2 de-emphasis of risk-based + Q1 de-emphasis of consistency)
- Complex multi-asset portfolio theory (single-asset-class by design, not hedging)
- Options/derivatives strategies (methodology discontinuity)
- Most macro and top-down frameworks (methodology is bottom-up by design)

---

## The four strategic themes

### Theme 1 — Kelly-family capital efficiency

**Quant-econ content.** Kelly (1956) criterion for log-optimal capital growth. Thorp (1969, 2006) practical extensions. Fractional Kelly (Kelly × 0.25 to 0.5 typical for real traders). Drawdown-constrained Kelly. Parameter-uncertainty bounds (MacLean-Thorp-Ziemba, 2010). Bayesian Kelly with prior updating.

**What the work consists of.** Honest expectancy estimation from trade history; backtesting sizing rules with out-of-sample protocols; shadow-mode deployment with extensive monitoring; explicit leverage bounds; degradation behavior when estimates become unreliable.

**Operational complexity.** L2 achievable with fixed fractional Kelly and static expectancy estimates. L3 required for dynamic Kelly adapting to changing expectancy. L4 not recommended operationally.

**Known failure modes:**

- Biased expectancy inputs produce dangerous leverage — mitigated by Theme 3 being a hard prerequisite
- Psychological tolerance for Kelly-sized positions may bind before mathematical optimum — plan for 9–12 month paper/shadow deployment minimum before real-money
- Parameter instability over regime changes may make static Kelly dangerous — mitigated by Theme 2 decay monitoring

**Reading priority list** (in order of usefulness for this project):

- Thorp, "The Kelly Criterion in Blackjack, Sports Betting, and the Stock Market" (2006 revision)
- MacLean, Thorp, Ziemba (eds.), *The Kelly Capital Growth Investment Criterion* (2010)
- López de Prado, *Advances in Financial Machine Learning* (2018) — chapter on bet sizing
- Poundstone, *Fortune's Formula* (2005) — historical and intuitive context, not a reference

### Theme 2 — Method-decay detection

**Quant-econ content.** Structural break tests (Chow, Quandt-Andrews, Bai-Perron). Sequential testing methods (CUSUM, CUSUM-of-squares). Rolling performance z-scores and Sharpe-ratio stability tests. Crowding metrics (13F overlap, short-interest curation, ETF flow concentration, retail-sentiment proxies).

**What the work consists of.** Build rolling-metrics infrastructure; implement structural-break tests on method-level P&L; develop at least one crowding-proxy dashboard; define decay thresholds that trigger research-branch review.

**Operational complexity.** L3 for the tests themselves; L2 for the operator-visible outputs (red/yellow/green status per method).

**Known failure modes:**

- Crowding metrics depend on data sources that are expensive, proprietary, or require substantial ETL — minimum-viable version may have performance-based decay detection only, crowding deferred
- False positives (statistical artifact) vs true decay signals — hard to distinguish with short method histories; mitigation is using tests with known properties under serial correlation
- Decay detection at the method level can be misleading when the issue is portfolio-level (correlation structure change, not individual-method change) — plan for both-level monitoring

**Reading priority list:**

- Hamilton, *Time Series Analysis* (1994) — canonical structural break material
- Zeileis, Leisch, Hornik, Kleiber, "strucchange: An R Package for Testing Structural Change in Linear Regression Models" — practical reference
- López de Prado, *Advances in Financial Machine Learning* (2018) — chapter on backtest overfitting and deflated Sharpe
- Harvey, Liu, Zhu, "...and the Cross-Section of Expected Returns" (Review of Financial Studies 2016) — multiple-testing corrections for strategy evaluation

### Theme 3 — Performance attribution via factor decomposition

**Quant-econ content.** Fama-French three-factor model (1993). Carhart four-factor extension (1997). AQR-style multi-factor decomposition including quality, low-volatility, and time-series momentum (Asness et al., various). Regime-conditional factor loadings.

**What the work consists of.** Curate trade ledger with clean entry/exit dates and P&L; match factors to trade dates; run regressions decomposing realized returns into factor-beta components and residual alpha; produce monthly or quarterly attribution report; track alpha stability over time.

**Operational complexity.** L3 for the regression and interpretation; L2 for the reported output (% alpha vs % factor beta).

**Prerequisites.**

- Trade ledger must contain ≥50 closed trades for regression to be meaningful; ≥100 strongly preferred
- Factor data must be available for the entire trade history date range (Ken French data library covers US equity factors well; AQR publishes extended factors)
- Sufficient time tracking for alpha *stability* (not just point estimate) requires ≥12 months of history

**Known failure modes:**

- Too-small trade sample produces wide confidence intervals on alpha estimate; may incorrectly conclude alpha exists or doesn't exist
- Factor-model misspecification if the factors used don't match the setups being traded (e.g., using only Fama-French-Carhart when the actual edge is in a factor not included)
- Time-variation in factor loadings means a single regression over all history can hide important regime-conditional effects

**Reading priority list:**

- Fama, French, "Common Risk Factors in the Returns on Stocks and Bonds" (Journal of Financial Economics 1993)
- Carhart, "On Persistence in Mutual Fund Performance" (Journal of Finance 1997)
- Ang, *Asset Management: A Systematic Approach to Factor Investing* (2014) — comprehensive factor-investing treatment
- Asness, Moskowitz, Pedersen, "Value and Momentum Everywhere" (Journal of Finance 2013)
- Ken French data library (practical data source, not a reading)

### Theme 4 — Setup-quality improvement via theoretical anchoring

**Quant-econ content.** Behavioral underreaction models (Barberis-Shleifer-Vishny 1998; Daniel-Hirshleifer-Subrahmanyam 1998). Slow-information-diffusion models (Hong-Stein 1999). Limited-attention effects (Cohen-Frazzini 2008; Da-Gurun-Warachka 2014 "frog in the pan"). Adaptive Markets Hypothesis (Lo 2004, 2017).

**What the work consists of.** For each existing production setup (pocket pivot, VCP, buyable gap-up, etc.), identify the theoretical mechanism most closely matching the setup's empirical behavior; use theory to propose refinements or extensions; use theory to predict decay conditions; run research-branch studies comparing theoretically-informed variants against current operational versions.

**Operational complexity.** L2 achievable for most refinements; L3 not generally needed for setup work.

**Known failure modes:**

- Theoretical neatness can override empirical evidence — mitigation is treating theory as hypothesis-generating, not hypothesis-confirming
- Setup work is open-ended with no natural stopping point; can absorb arbitrary effort — mitigation is defining a specific stopping criterion (e.g., "three validated refinements" or "one new promoted setup") per session tranche
- Theoretical explanations often fit multiple observed patterns equally well — the behavioral, frictional, and adaptive frames often make similar predictions, making it hard to distinguish them empirically

**Reading priority list:**

- Lo, *Adaptive Markets* (2017) — overarching framework
- Barberis, Thaler, "A Survey of Behavioral Finance" (Handbook of the Economics of Finance 2003) — comprehensive behavioral finance survey
- Hong, Stein, "A Unified Theory of Underreaction, Momentum Trading and Overreaction in Asset Markets" (Journal of Finance 1999)
- Da, Gurun, Warachka, "Frog in the Pan: Continuous Information and Momentum" (Review of Financial Studies 2014)

---

## Dependency structure among the themes

The themes are not independent. Their dependencies constrain any sensible sequencing:

```
Theme 2 (decay detection) ──┬──> Theme 3 (attribution) ──> Theme 1 (Kelly)
                            │
                            └──> Theme 4 (setup refinement)
```

**Hard constraint: Theme 3 is logically prior to Theme 1.** Kelly sizing requires expectancy estimates, and naive expectancy from historical trades includes factor beta. If 60% of realized edge is actually momentum-factor beta, naive-Kelly leverages 2.5x more than justified. This is not a preference — it's a mathematical fact. Kelly work must be conditional on Theme 3 establishing that alpha is meaningfully positive after factor decomposition.

**Softer constraint: Theme 2 is logically prior to Theme 4.** Setup refinement optimizes existing methods. If those methods are already decaying, Theme 4 work optimizes something that's dying. Theme 2 identifies which methods have headroom vs which are candidates for replacement.

**Enabling relationship: Theme 2 enables Theme 3's diagnostic value.** Static factor decomposition at one point in time is a snapshot. Theme 2's rolling-metrics infrastructure makes Theme 3 a living diagnostic that detects alpha decay as it happens rather than after the fact.

**Parallelizable: Themes 1 and 4 once prerequisites met.** Different layers (sizing vs setup detection), different parts of quant-econ toolkit, no direct dependency between them.

**Notable counterintuitive consequence.** Theme 1 (Kelly-family) is the highest-leverage theme for the stated priorities (Q1 #2 = capital efficiency). But it is the *last* theme in sequencing because premature Kelly work is dangerous in a way that premature attribution or decay-detection work isn't. The theme serving priorities most directly is the theme requiring the longest wait.

---

## Proposed sequencing

### Relationship to V2.1 tranches

V2.1 mandates three tranches before broader research expansion:

- Tranche 1: Strategy executable; method-record mechanism; one chosen research question; small Phase 0 task list
- Tranche 2: One decision-grade study completed
- Tranche 3: Operational-branch improvements from real backlog

**All four themes in this document are strictly post-tranche-3.** Tranches 1–3 are not optional preludes to this work; they are independent V2.1 deliverables that must complete first.

However, the *choice* of tranche-2 study can bridge toward Theme work. V2.1 §V.D lists candidate first studies including "test one risk-budgeting or exposure-throttle refinement that maps cleanly to operator decisions." A tranche-2 study oriented toward simple volatility-budgeted sizing would serve both V2.1's completion requirement and seed Theme 1's infrastructure. This is a natural bridge worth considering when choosing the first study, though V2.1's other candidates (RS formulation comparison, earnings-proximity exclusion) are equally valid first-study choices.

### Theme sequencing (post-V2.1 tranche 3)

**Phase R1 — Theme 2 foundation.** Build rolling-metrics infrastructure; implement structural-break tests; build minimum-viable crowding dashboard or explicitly defer crowding.

- First-milestone criterion: every production method has rolling-performance z-score, structural-break test history, and (if attempted) one crowding proxy metric
- Reusable across all later themes
- Calendar estimate: 4–6 months at 1.5–2.5 hrs/week research time

**Phase R2 — Theme 3 (factor decomposition).** Curate trade ledger; match factors; run regressions; produce attribution reports.

- First-milestone criterion: monthly decomposition report reliably separating factor beta from residual alpha, with ≥12 months of history
- Constrained by trade-history volume — if ledger has <50 closed trades at Phase R1 completion, R2 must wait for accumulation
- Calendar estimate: 3–5 months, lighter than R1 because R1 infrastructure helps

**Phase R3 — Theme 1 (Kelly) and Theme 4 (setup refinement) in parallel.**

Theme 1 first-milestone criterion: fractional-Kelly sizing in shadow mode alongside existing sizing, with explicit leverage bounds and degradation behavior
- Calendar estimate: 6–9 months shadow mode; real-money deployment gated on ≥9–12 months shadow evidence

Theme 4 first-milestone criterion: one completed study per tranche — either a validated refinement to an existing setup or theoretical documentation of decay conditions for an existing setup
- Calendar estimate: continuous, open-ended; discrete milestones every 3–6 months

**Total to first mature state: roughly 18–24 months of calendar time post-V2.1 tranche 3.**

### Timeline sketch

```
Pre-Phase (V2.1 tranches): near-term and not covered by this document

Months 0–6 (post-tranche-3):   Theme 2 foundation
                               ├─ Parallel: trade-log accumulation if below 50-trade threshold
                               └─ Parallel: theoretical reading for Theme 1 (Kelly + Thorp)

Months 4–10:                   Theme 3 (factor decomposition)
                               ├─ Overlaps with late Theme 2 work
                               └─ First attribution report around month 8

Months 9–18:                   Theme 1 (Kelly-family) in shadow mode
                               ├─ Runs alongside existing sizing rules
                               └─ Real-money deployment gated on 9+ months shadow evidence

Months 6–ongoing:              Theme 4 (setup refinement)
                               └─ Starts after decay detection identifies setups with headroom

Month 18+:                     Full quant-econ integration operational
                               └─ All four themes in steady state
```

Slippage against this timeline is acceptable as long as the dependency order holds.

---

## Known failure modes and mitigations

**FM1 — Trade-history volume insufficient for Theme 3.**
- Symptom: factor regression produces wide confidence intervals; alpha indistinguishable from zero
- Mitigation: start Theme 2 while trade history accumulates; run Theme 3 the moment trade threshold is crossed
- Early check: at start of Phase R1, audit the trade ledger and project when ≥50 closed trades will exist

**FM2 — Theme 2 crowding metrics unusually expensive for solo developer.**
- Symptom: Phase R1 stalls on 13F aggregation or short-interest curation
- Mitigation: split Theme 2 into (a) performance-based decay detection (achievable) and (b) crowding proxies (deferred or omitted)
- Early check: first 2 weeks of Phase R1 prototype both sub-themes to estimate feasibility

**FM3 — Kelly psychologically intolerable at mathematically-correct sizes.**
- Symptom: operator systematically undershoots Kelly recommendations, making Theme 1's real-money deployment a theoretical exercise
- Mitigation: extend shadow-mode duration to 12+ months; explicitly treat psychological tolerance as a research finding about the operator, not a Theme 1 failure; consider fractional Kelly at 0.25x rather than 0.5x as operational target
- This is expected more often than not

**FM4 — Theme 4 has no natural stopping point, absorbs arbitrary effort.**
- Symptom: months of setup-refinement work with no discrete deliverables
- Mitigation: define per-tranche stopping criterion in advance ("three validated refinements" or "one new promoted setup"); treat Theme 4 as a steady trickle rather than a focused project

**FM5 — Theoretical framework becomes an overfitting aid rather than a constraint.**
- Symptom: every empirical finding gets explained post-hoc by one of the four Q2 frames; no predictions are ever falsified
- Mitigation: require *predictions* (what would falsify the frame's application to this method?) before running studies; pre-register predictions in the method record
- Applies specifically to Theme 4 but could affect any theme

**FM6 — Composite profile changes over time, invalidating the sequencing.**
- Symptom: after 12 months of real-money operation, the trader's actual preferences diverge from Q1/Q2 rankings
- Mitigation: re-run the four positioning questions annually; treat this document as a snapshot, not permanent doctrine
- Expected failure mode over multi-year horizons

---

## Open uncertainty

**The Theme 2 vs Theme 3 ordering is a real choice, not a fake one.**

Current recommendation: Theme 2 first. Reasons: more foundational, doesn't require trade-history accumulation, can start immediately post-tranche-3, aligns with Q2 behavioral+adaptive worldview, enables both downstream themes.

Counterargument: Theme 3 first. Reason: factor decomposition directly answers "is my edge real?" which is existentially important for everything else planned. If Theme 3 reveals most edge is factor beta rather than alpha, that changes whether Theme 1 is worth pursuing at all.

**Decision criterion at the time of phase R1 start:** if trade ledger already has ≥50 closed trades, the case for Theme 3 first strengthens considerably. If trade ledger has <50 closed trades, Theme 2 first is clear.

This is the single most important open decision in this document and should be revisited at the time R1 begins, not locked in now.

---

## Governance interactions with V2.1

These four themes, when initiated, will interact with V2.1 governance in specific ways:

**Method-record implications (V2.1 §IV.B).** Quant-econ methods require the same method-record treatment as practitioner methods. Theme 1 produces `sizing:kelly-fractional-v1` and similar. Theme 2 produces monitoring-layer methods — registry may need a `layer=monitoring` entry class. Theme 3 is primarily diagnostic and may not require method records per se, but attribution reports produced are research artifacts subject to the same provenance discipline as any research run (V2.1 §IV.C).

**Promotion-boundary implications (V2.1 §IV.D).** Theme 1's fractional-Kelly sizing when moved from shadow to primary is a standard promotion event. Theme 2's decay-detection status flags are operator-facing but are not methods driving primary recommendations — they sit in a governance layer closer to §IV.D's production-safety boundary than to its method-promotion boundary. Worth clarifying this distinction in the method record before Theme 2 ships.

**Demotion-pathway implications (V2.1 §VII.E).** Theme 2 directly produces the evidence that feeds V2.1's demotion pathway. This is the mechanism by which the demotion pathway becomes a mainline process rather than an exception handler, consistent with Q2's prediction that 20–40% of production methods per decade will require demotion.

**Source-of-truth correction implications (V2.1 §VII.F).** Theme 4's theoretical-anchoring work will periodically surface cases where a practitioner method in production is described differently from (or inconsistently with) a primary theoretical source. These are source-of-truth corrections and flow through the standard §VII.F protocol.

**Parity-standard implications (V2.1 §VII.B).** Theme 1's Kelly sizing uses floating-point arithmetic across research and production environments. Parity-standard applies: identical on fixtures, equivalent within tolerance on live data. Theme 3's factor regressions do not cross the research/production boundary (attribution is research-only), so parity standard does not apply.

**Time-budget implications (V2.1 §III.7).** The 18–24-month calendar estimate assumes the V2.1 budget of 4–8 hrs/week, with research share rising from ~30% currently to ~50% once production is in steady-state late-Phase-3. If that share rise does not materialize, all calendar estimates extend proportionally.

---

## Downstream handoff notes

For future Claude Code / Codex sessions consulting this document:

**Do not treat this document as implementation guidance.** It is forward positioning, not a task list. The first implementation session that should consult this document in detail is the one that begins Phase R1 (post-V2.1 tranche 3), and even then V2.1 remains the governing strategy.

**If V2.1 is still the governing strategy and tranches 1–3 are incomplete, defer this document entirely.** V2.1 §V.A mandates one decision-grade study before generalized infrastructure. This document's themes are generalized infrastructure. Attempting them before tranche 3 completes violates V2.1 §V.A.

**When Phase R1 begins, re-validate positioning before starting work.** The four questions in this document captured the developer's position on 2026-04-24. If more than 6 months have elapsed, re-run the questions briefly before committing to the sequencing derived from the 2026-04-24 answers.

**If the operational branch or research branch state has materially changed** from the "Positioning assumptions (baseline)" section, the dependency analysis and timeline may need adjustment. The *themes* are likely still valid; the *sequencing* is more sensitive to context.

**Do not expand this document.** It captures a snapshot of forward positioning. Amendments should be new documents referencing this one, not edits to this one — consistent with V2.1's minimum-viable posture on governance artifacts.

**Cross-references for future sessions:**

- Governing strategy: `2026-04-23-bifurcated-strategic-implementation-proposal-v2.1.md`
- Current repo state: `CLAUDE.md` (root)
- Near-term operational backlog: `docs/phase3e-todo.md`
- First source-of-truth artifact (per V2.1 changelog): `reference/methodology/minervini-trend-template.md`
- Diagnostic predecessor documents (read only if historical context needed): `reference/Future Work/2026-04-22-formal-critique-extending-methodological-basis.md`, `reference/Future Work/2026-04-22-rebuttal-critique-and-implementation-proposal.md`

---

## Changelog

- 2026-04-24: Initial creation. Captures positioning exercise conducted in session of same date. No prior versions.
