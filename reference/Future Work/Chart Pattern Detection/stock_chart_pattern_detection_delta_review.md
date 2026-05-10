---
title: "Critical Review and Revision: Stock Chart Pattern Detection Analysis"
purpose: "Section-by-section delta to original document, scoped to swing-trading use case"
related_document: "stock_chart_pattern_detection_ai_ingestion.md"
review_type: "Critical review with prescriptive deltas"
version: "1.0"
created: "2026-05-08"
intended_use:
  - "AI ingestion"
  - "Development planning"
  - "Requirements baseline correction"
scope:
  context:
    - "Tool target: swing trading (Minervini/CANSLIM family)"
    - "Operation: end-of-day batch, daily and weekly bars"
    - "Production constraint: rule-based or small local ML model on 8GB GPU"
    - "User: single user, AI-assisted development"
    - "System role: pattern detection module within broader trading decision support system"
  included:
    - "Section-by-section deltas to original document"
    - "Three new sections: Development Data Strategy, Drift Detection, ML Model Decision Analysis"
    - "Reference list corrections and additions"
  excluded:
    - "Implementation details"
    - "Trade execution mechanics"
    - "Position sizing"
    - "Broker integration"
section_status_legend:
  CHANGED: "Substantive revision required from original"
  REDUCED: "Some critiques drop out under new scope"
  HEAVILY_CHANGED: "Major rework required"
  NEW: "Section did not exist in original"
  UNCHANGED: "Original critique still applies"
---

# Critical Review and Revision: Stock Chart Pattern Detection Analysis

## Reading Guide

This document is a section-by-section delta to the original analysis (`stock_chart_pattern_detection_ai_ingestion.md`). Each section is tagged with a status from the legend in the YAML front matter. The original section numbering is preserved. Three sections are new: §X Development Data Strategy, §Y Drift Detection, and §Z Small ML Model Decision Analysis.

Context shift driving these deltas: the document is now scoped as the pattern-detection module of a broader swing-trading decision-support system, targeting Minervini/CANSLIM-style setups, single user, EOD daily/weekly batch operation, AI-assisted development with rule-based or small local-ML production inference.

## Δ Front Matter — CHANGED

The original front matter is generic. It should now name swing trading explicitly, list the pattern set, and acknowledge the broader system context.

Suggested replacement scope block:

```text
included:
  - Pattern detection for swing-trading setups (Minervini/CANSLIM family)
  - EOD daily and weekly bar analysis
  - Universe pre-filtering criteria
  - Mathematical strategies for pattern detection
  - Development-time data strategy (AI-assisted labeling, synthetic, perturbation)
  - Integration points with broader trading system
  - ML model decision analysis
excluded:
  - Intraday/tick data
  - Real-time detection during bar formation
  - Trade execution and broker integration
  - Position sizing and risk management algorithms
  - Multi-user/team workflows
```

## Δ §1 Objective — CHANGED

The detector is one module of a larger system. The six-item responsibility list should be modified:

- Item 5 ("Allows a human reviewer to confirm, deny, relabel, or mark uncertain") — fine, but should specify single-user.
- Item 6 ("Stores reviewer feedback for future calibration") — should be expanded to: "Stores reviewer decisions, trade actions taken, and trade outcomes, all linked to the originating candidate, for closed-loop calibration."

The introspection requirement (the system must show *why* something was flagged) now becomes a hard constraint, not just a preference. With no second reviewer and the tool driving real capital allocation decisions, you must be able to see the evidence behind a flag. This rules out black-box production methods regardless of whether they fit in 8GB.

## Δ §2 Core Framing — CHANGED

The Question A vs Question B split (recognition vs predictiveness) stays. Add Question C (multiple-comparisons / data-snooping), but pitch it lower than the original critique implied — at this scope it is a concern, not a five-alarm fire.

Add a fourth question that is specifically relevant to the closed-loop setup:

```text
Question A: Is a recognizable pattern present?
Question B: Is the pattern predictive in this regime?
Question C: How many false positives does pattern density imply by chance?
Question D: Is *my* implementation of trading this pattern profitable, given my discipline?
```

Question D is the one that matters most for this tool because it incorporates user behavior, not just market behavior. The trade history → shape library mechanism implicitly answers Question D.

## Δ §3 Detection Unit — REDUCED

Most of the original critiques drop out:

- Detection-latency / causality concerns: irrelevant for async EOD batch.
- Real-time / streaming concerns: out of scope.
- Tick data: out of scope.

What remains and gets stronger:

- **Adjustment policy** — split-adjusted is non-negotiable, but back-adjusted continuous data for indices (if used as context) needs a stated convention.
- **Bar type** — confirm OHLCV daily as primary. Heikin-Ashi may be worth keeping as an optional view since some swing-trading literature uses smoothed bars to suppress whipsaws.
- **Window construction** — fixed-window is too rigid for VCP-style patterns whose duration varies from a few weeks to several months. Variable-window with anchor-point search is the right primitive.

The table should be reduced to: input data, bar type, adjustment, window construction, output type. Drop timeframe (single answer: daily + weekly). Drop pattern type (handled in §4).

## Δ §4 Candidate Pattern Categories — HEAVILY_CHANGED

This is the section that needs the most rework. **VCP being absent from the original document is a finding worth flagging in the rewritten document itself.**

New primary table:

| Pattern | Source/Methodology | Mathematical Tractability |
|---|---|---|
| Volatility Contraction Pattern (VCP) | Minervini | High — sequence of contractions with monotonically decreasing depth %, declining volume, defined duration |
| Cup-with-handle | O'Neil/CANSLIM | High — rounded base + shallow pullback handle with defined depth/duration ratios |
| Flat base | O'Neil/CANSLIM | High — bounded range with low slope and tight ATR for ≥5–7 weeks |
| High-tight flag | Minervini/O'Neil | High — defined prior advance % and tight consolidation % |
| Double-bottom W (with shakeout/undercut) | Both | Medium-High — two troughs with center peak, optional undercut of first low |
| Pole-and-flag and tight-channel variants | Both | Medium — variations on flag structure |
| Power play / IPO base | Minervini | Medium — large advance from IPO + shallow base |

Upstream context (these are *not* patterns but pre-conditions):

| Context | Source | Role |
|---|---|---|
| Stage 2 uptrend | Weinstein/Minervini | Required pre-condition; filter out Stage 1, 3, 4 |
| Trend template | Minervini | Universe pre-filter (price > MA50 > MA150 > MA200, MA200 trending up, 52w high/low position, RS rank) |
| Relative strength rank | O'Neil/CANSLIM | Universe pre-filter |
| Liquidity / market cap floor | Both | Universe pre-filter |

Sell-side patterns (separate detector module):

| Pattern | Role |
|---|---|
| Head and shoulders top | Minervini sell signal |
| Climax run / parabolic exhaustion | Minervini sell signal |
| Stage 4 breakdown | Weinstein sell signal |
| MA50/MA200 violations | Both, exit triggers |

Demoted to "noted but not in roadmap" appendix: harmonic patterns, candlestick patterns generally, classical reversal patterns not in the swing-trading vocabulary, intraday patterns. They are not wrong; they are not what this tool is for.

## Δ §5 Mathematical and Analytical Approaches — CHANGED

The enumeration is fine; the ranking and recommendations change substantially.

### §5.1 Rule-Based Geometric Detection

Promoted to clearly primary. The original document treats it as one of several options; the swing-trading pattern set is mathematically tractable enough that rules should be the production backbone. The H&S example in the original should be replaced with a worked VCP example, since that is the headline pattern.

Illustrative VCP candidate criteria (not final):

```text
1. In Stage 2 uptrend (per trend template).
2. Prior uptrend leg of >=30% over >=8 weeks.
3. Sequence of N>=2 contractions where:
   - Each contraction depth (peak-to-trough) % decreases monotonically.
   - Typical depths: T1 ~15-30%, T2 ~10-15%, T3 ~5-10%.
4. Volume declines through the contraction sequence.
5. Duration: 3-12 weeks total base (varies).
6. Pivot formed near top of base.
7. Optional: breakout above pivot on volume >=40% above 50d avg.
```

### §5.2 Smoothing and Extrema Extraction

Original critique unchanged: still missing zigzag, Perceptually Important Points (PIPs). For VCP detection specifically, zigzag with adaptive percentage threshold is essentially the right primitive.

### §5.3 Template Matching and Similarity Scoring

Promoted to strong secondary. Fits perfectly with the trade-history-as-shape-library mechanism: each confirmed entry from your own trades becomes a template. DTW caveat from original review still applies (constrained warping required to prevent over-warping).

### §5.4 Feature-Based Supervised Classification

Recontextualized. This is now the natural home for the optional small ML model (see §Z). The class-imbalance and calibration issues from the original critique still apply.

### §5.5 Candlestick-Specific Pattern Detection

Demoted. Keep brief mention; explicitly note Marshall et al. 2006 finding on weak predictive power; not a primary module.

### §5.6 Image-Based Computer Vision

Further demoted. The information-loss critique from the original review still applies (rasterizing already-structured OHLCV data destroys precision). With the small-model production constraint, this approach is doubly unappealing.

### §5.7 Sequence Models

Out of scope for production. Note in passing only.

### §5.8 Unsupervised Motif Discovery and Clustering

Repositioned. **Matrix Profile remains the most important addition.** It is specifically useful for "find historical bases across my universe that look like this confirmed VCP" — exactly the operation the shape library wants to perform. Promoted from "exploratory research" to "near-term production-viable."

### §5.9 Shapelet-Based Detection

Stays roughly where it is. Defer until labeled corpus exists.

## Δ §6 Data Requirements — CHANGED

### §6.1 Minimum Market Data

Add universe pre-filter as the first step in the data pipeline:

```text
Universe pipeline:
  All listed equities
  -> Liquidity filter (avg dollar volume threshold)
  -> Market cap floor
  -> Stage 2 / trend template filter
  -> RS rank filter
  -> Pattern-detection candidate pool (typically 200-500 names)
```

This stage is upstream of pattern detection, runs once per day, and dramatically reduces the multiple-comparisons surface area.

Add fields: dollar volume, RS rank, distance from MA50/150/200, MA slopes (these are needed for trend-template evaluation, not just for features).

### §6.2 Historical Coverage

The survivorship bias call-out from the original review still applies and is more important here, because the trend template specifically selects for currently-uptrending names. Without delisted-stock data, the "stocks that *were* in stage 2 and then broke down" cohort is unobservable.

### §6.3 Label Schema

Simplified for single user:

```text
candidate_id, ticker, timeframe, start_time, end_time
pattern_class (VCP, CWH, FB, HTF, DBW, ...)
detector_version (rule version that triggered)
geometric_score (rule-based score components)
template_match_score (top-N nearest historical bases)
self_decision (confirm, deny, watch, traded)
self_decision_timestamp
trade_id (if action taken — links to trade history)
trade_outcome (if applicable — R-multiple, days held, exit reason)
quality_grade (1-5 scale, post-hoc; "would I take this trade today?")
discipline_flag (taken-as-planned, missed, deviated)
notes
```

The `quality_grade` field deserves special mention: it is the mechanism for addressing self-drift. Periodically re-rate old confirmed patterns. If your grading drifts, that is the signal.

### §6.4 Negative and Ambiguous Examples

Reframed for single user with trade history:

```text
confirmed_traded         (positive labels with outcome data)
confirmed_not_traded     (positive labels, opportunity-cost data)
watch_list_no_action     (ambiguous, watched but never triggered entry)
detector_flagged_rejected (negative labels)
near_miss_rejected        (failed one specific rule)
```

## Δ §7 Normalization and Transformation — REDUCED

The causality concerns from the original critique drop out (EOD batch). Z-score and volatility-scaled normalization remain relevant. The "core invariance questions" block is still good and should be promoted as the original review suggested. Pattern-specific normalization (e.g., normalize VCP candidates by the height of the prior advance, not by absolute price) is worth adding.

## Δ §8 Human-Review Workflow — CHANGED

Substantially simplified for single user, but with new closed-loop elements added.

```text
1. Universe filter runs (EOD).
2. Pattern detectors run on filtered universe.
3. Candidates ranked by composite score (geometric + template similarity).
4. Top-K candidates presented in next-morning review.
5. User reviews each: confirm/watch/reject + reasoning.
6. For confirmed candidates: alert/order management (out of scope here).
7. Trades execute or don't execute (out of scope here).
8. Trade outcomes logged and back-linked to originating candidate.
9. Periodic (weekly) review: drift dashboards, false-positive trends, missed-opportunity audit.
10. Periodic (quarterly) re-grading of historical decisions to detect self-drift.
```

The review interface should show, per candidate: pattern class, geometric score breakdown by rule component, top-3 nearest historical bases (template matches), trend-template status, RS rank, recent volume profile, and — critically — outcome distribution from prior similar candidates ("of the last 20 VCPs flagged with similar scores, X% triggered, Y% reached 1R, Z% hit stop").

That last item is what makes the closed loop actually closed.

## ★ NEW §X: Development Data Strategy

This section did not exist in the original document. It addresses how to bootstrap a working detector and labeled corpus given the single-user bandwidth constraint.

```text
Development data sources (in rough priority order):

1. Historical exemplar harvest
   - Curated "textbook" examples from books and IBD/Minervini archives.
   - Hand-marked anchor points (left side, base start, contractions, pivot, breakout).
   - Small set, high quality. ~30-100 per pattern class.

2. AI-assisted labeling at scale
   - Claude Code processes candidate windows from rule-based detector.
   - Returns pattern class + confidence + structural notes.
   - User spot-checks a sample (10-20%) for calibration.
   - Use AI labels as silver-standard training data with explicit silver/gold tags.

3. Parametric synthetic generation (especially clean for VCP)
   - Random sampling over parameter space: contraction count {2,3,4},
     depth sequences with monotonicity constraints, durations,
     volume profiles, base widths, prior-trend strengths.
   - Embed synthetic patterns into real noise backgrounds
     (sample real Stage-2 segments, splice in synthetic bases).
   - Generate negative examples by intentionally violating constraints.

4. Perturbation of confirmed examples
   - Time stretching / compression within tolerance bands.
   - Amplitude scaling.
   - Volume profile perturbation.
   - Adding small noise.
   - Yields useful training data without inventing structure.

5. Organic accumulation from trade history
   - Slow but high-quality.
   - Real labels with real outcomes.
   - The eventual ground truth.
```

Critical design point: keep these sources tagged. Models trained on synthetic data alone fail on real data; models trained on real data alone are sample-starved. The right approach is mixed training with stratified evaluation (eval on held-out real-only subset, never on synthetic).

## Δ §9 Recommended Initial Strategy — CHANGED

Replace the three-phase plan with this sequence:

**Phase 0:** Universe pipeline and trend-template filter. Standalone module, valuable on day one even before any pattern detection.

**Phase 1:** Rule-based detection of VCP, flat base, cup-with-handle. AI-assisted parameter tuning against curated exemplars. Single composite score per pattern. Manual review of every flagged candidate.

**Phase 2:** Template matching against curated exemplar set. Two retrieval modes: "show me historical bases that look like this candidate" and "show me candidates that look like this confirmed historical base." DTW with constrained warping or shape-based distance.

**Phase 3:** Add high-tight flag and double-bottom-W detectors. Same rule-based + template approach.

**Phase 4:** Closed-loop integration. Trade actions and outcomes back-linked to candidates. Outcome distributions surfaced in review interface.

**Phase 5:** Drift detection. Feature drift, pattern frequency drift, outcome drift dashboards.

**Phase 6 (gated):** Optional small ML re-ranker. See §Z for whether and when.

**Phase 7 (gated):** Matrix Profile-based exemplar retrieval at scale. Once curated exemplar set is large enough.

## Δ §10 Approach Comparison — CHANGED

The table needs to be re-ranked for swing-trading scope and the production constraints. Image and large sequence models drop down or out. Matrix Profile moves up. Rule-based and template matching are tied for top.

| Approach | Label Requirement | Interpretability | Fit to Swing-Trading | Production Viability (8GB) | Best Stage |
|---|---|---|---|---|---|
| Rule-based geometry | Low | High | High | Yes | Phase 1 (primary) |
| Smoothing + extrema | Low | High | High | Yes | Phase 1 (foundation) |
| Template matching (DTW/SBD) | Medium | Medium-High | High | Yes | Phase 2 (primary secondary) |
| Matrix Profile | Low-Medium | Medium | High | Yes | Phase 7 (when corpus ready) |
| Feature-based GBM/RF | Medium-High | Medium (with SHAP) | Medium | Yes | Phase 6 (gated) |
| Candlestick rules | Low | High | Low | Yes | Out of roadmap |
| Image CNN | High | Low | Low | Marginal | Not recommended |
| Sequence transformers | High | Low | Low | No | Out of scope |
| Shapelets | Medium-High | Medium-High | Medium | Yes | Later/gated |

## Δ §11 Suggested System Architecture — CHANGED

Per the broader-system scope, the architecture diagram now shows pattern detection as one component:

```text
Universe Layer
  -> universe definition
  -> liquidity, market cap, RS filters
  -> trend template evaluation

Pattern Detection Layer
  -> rule-based detectors per pattern class
  -> template matching against exemplar library
  -> composite scoring and ranking

Decision Support Layer
  -> candidate review interface
  -> outcome distributions for similar prior candidates
  -> action recommendation (with confidence)

Action / Trade Layer (out of scope here, but integration point)
  -> orders, fills, position management

Performance / Discipline Layer
  -> trade outcome capture and back-linkage to candidates
  -> discipline tracking (taken-as-planned vs deviated vs missed)
  -> portfolio analytics

Drift / Calibration Layer
  -> feature distribution monitoring
  -> pattern frequency monitoring
  -> outcome distribution monitoring
  -> self-drift monitoring (re-grading)
  -> re-tuning triggers and gates

Development Substrate (offline, not in production path)
  -> AI-assisted labeling
  -> synthetic generation
  -> perturbation pipelines
  -> rule tuning harness
  -> ML training (gated; see §Z)
```

## Δ §12 Evaluation Metrics — CHANGED

For single user with closed-loop outcome data, the right metric set is different. Drop inter-rater metrics. Promote calibration and outcome-conditioned metrics:

```text
Detection metrics:
  Precision (of flagged, how many you confirm)
  Recall (against curated exemplar set; cannot be measured against universe)
  Calibration (Brier score, reliability diagram for composite scores)
  Top-K precision (of top 5/10/20 ranked, how many you confirm)
  Candidate density per day (workflow load)

Closed-loop outcome metrics:
  Score-conditioned hit rate (does score predict trade success?)
  Score-conditioned R-multiple distribution
  Time-to-resolution (how long until pattern triggers or fails)
  Failed-pattern characterization (what do failures have in common?)

Discipline metrics:
  Recommendation adherence rate
  Outcome divergence between adhered and deviated trades
  Time-of-day or fatigue effects on adherence

Drift metrics:
  Feature distribution KL or PSI vs trailing baseline
  Pattern frequency per universe size, vs trailing baseline
  Hit-rate decay vs trailing baseline (regime change indicator)
```

## ★ NEW §Y: Drift Detection

Drift detection deserves its own section. Three drift surfaces:

```text
1. Feature drift
   Monitor distribution shifts in input features (volatility, breadth,
   trend-template pass rate across universe, RS distributions).
   Tool: Population Stability Index or KL divergence vs trailing 1y baseline.
   Trigger: PSI > 0.25 on any monitored feature.

2. Pattern frequency drift
   Monitor candidate density per pattern class.
   Bear regimes produce few VCPs; sideways markets produce many flat bases.
   Trigger: pattern density falls below or rises above trailing-90d baseline by >2 sigma.
   Action: not retraining — *interpretation* (regime shift, not detector failure).

3. Outcome drift
   Monitor hit rate and R-multiple distribution per pattern class.
   Falling hit rate while feature/frequency stable = pattern degradation.
   Falling hit rate while features also drifting = regime change.
   Trigger: 20-trade rolling hit rate falls >X% below trailing baseline.
   Action: investigate, possibly tighten rules or pause pattern class.

4. Self-drift
   Periodic re-grading of historical decisions.
   Compare current grades to original grades on same charts.
   Trigger: grade-disagreement rate > 15% on rolling 6-month sample.
   Action: examine systematic shift; recalibrate or document rationale.
```

## Δ §13 Key Risks — CHANGED

Risks change shape under new scope:

- **Multiple comparisons** — present but tractable (~1500–3500 tests/day, not 10⁸).
- **Survivorship bias** — *more* important under trend-template universe selection.
- **Self-drift** — central risk for single-user system.
- **Outcome attribution confusion** — was the trade good because the pattern was good, or because the market was strong? Hard to disentangle. Mitigation: track market regime alongside outcomes.
- **Overfitting rules to recent regime** — tuning rules against any narrow time window will fail in different regimes.
- **Synthetic-to-real gap** — synthetic-trained models often fail on real data in subtle ways. Always evaluate on real-only held-out set.
- **Trade-history leakage in evaluation** — if a model is trained on trades you took, then evaluated on prior trades you took, outcome information has leaked. Strict temporal splits required.
- **Labeling-with-AI bias** — Claude Code's labels reflect Claude Code's biases. If an ML model is trained on Claude-labeled data, it learns to mimic Claude. Spot-checking and outcome calibration are the mitigations.

## ★ NEW §Z: Small ML Model Decision Analysis

This section addresses whether a small ML model is beneficial, the conditions under which it would become beneficial, and the gates that should be met before implementation.

### Z.1 What Roles Could a Small ML Model Plausibly Play?

Three distinct roles, with very different value propositions:

```text
Role 1: Pattern classifier
  Input: candidate window
  Output: {VCP, CWH, FB, HTF, DBW, none}
  Replaces: rule-based detection
  Verdict: Low marginal value. For these patterns, well-tuned rules
           are competitive and far more interpretable.

Role 2: Setup quality re-ranker
  Input: rule-confirmed candidate + features + template-match scores
  Output: probability that user will confirm this as a tradeable setup
  Replaces: nothing; it adds a calibrated layer above rules
  Verdict: Highest-value role. Captures personal preferences and
           subtle feature combinations that rules miss.

Role 3: Outcome predictor
  Input: confirmed candidate at decision time
  Output: probability of positive R-multiple within H bars
  Replaces: nothing; predicts outcome rather than recognizing pattern
  Verdict: Highest-risk role. Conflates Question A (recognition) with
           Question B (prediction). Most prone to data-snooping and
           regime-overfitting. Defer indefinitely or treat as research.
```

The sweet spot is Role 2. Role 1 is mostly redundant with rules. Role 3 is a different problem and arguably should be solved with explicit regime conditioning rather than another ML layer.

### Z.2 The Case For a Small ML Re-Ranker

- **Personal calibration.** User preferences for "tradeable VCP" almost certainly differ from textbook in ways that are awkward to encode as rules but easy to learn from decisions (e.g., contraction-depth preferences, base-duration preferences, RS-rank preferences).
- **Calibrated probabilities.** Rule-based geometric scores are not probabilities. A re-ranker can produce calibrated outputs that support principled gating ("only show me candidates where P(I'd confirm) > 0.7").
- **Feature interactions.** Rules treat features additively or as conjunctions. A small GBM can capture meaningful interactions (e.g., "depth tolerance varies with base width and RS rank").
- **Closed-loop adaptation.** As the label corpus grows, the re-ranker can be retrained periodically, incorporating regime shifts that rules cannot easily express.

### Z.3 The Case For Not Implementing One Yet

- **Label scarcity.** Organic accumulation will yield maybe 100–300 reviewed candidates per year. Even a small GBM wants several hundred labels per class to be useful, and meaningful evaluation needs more.
- **Synthetic data has bounded utility.** Synthetic VCPs help with rule-based detection thresholds but will not capture the full distribution of "looks like VCP but isn't" that the re-ranker needs to learn against.
- **Maintenance overhead.** An ML component adds drift monitoring, retraining cadence, version management, evaluation harness, and a feature-pipeline contract. All of this competes with rule-based improvement and tool usage time.
- **Risk of fitting your mistakes.** A re-ranker trained on user decisions will reproduce those decisions, including the bad ones. Without external ground truth, this is hard to detect.
- **Diminishing returns.** For tractable patterns like VCP, well-tuned rules + template matching may capture 85–90% of the achievable performance. The ML re-ranker is squeezing marginal gains, not reshaping the system.
- **Opportunity cost.** Time spent building ML is time not spent (a) using the rule-based tool and accumulating labels, (b) refining rules, or (c) extending the broader system (drift detection, performance tracking).

### Z.4 Cost/Benefit at This Specific Scale

| Dimension | Rule-based + templates only | + Small ML re-ranker |
|---|---|---|
| Build time | Lower | +20–40% additional |
| Maintenance burden | Low | Medium (drift, retraining) |
| Interpretability | High | Medium (with SHAP, manageable) |
| Labels needed | 30–100 exemplars per pattern | 300+ per pattern with outcomes |
| Time to first useful output | Weeks | 12–18 months minimum |
| Marginal performance gain | Baseline | +5–15% on well-defined metric |

The marginal-gain estimate is informed: in domains with clean rule-encodable structure and limited training data, ML re-rankers typically add modest single-digit to low-double-digit percentage points on top of strong rule baselines. They rarely transform performance.

### Z.5 Gates That Should Be Met Before Implementation

Recommend not implementing a model until *all* of these are true:

```text
G1. Rule saturation
    Three or more iterations of rule tuning have produced
    <5% improvement on a held-out validation metric.
    Without this, ML is masking rule-tuning laziness.

G2. Label volume
    At least 200 confirmed positive examples per pattern class,
    of which at least 100 have associated trade outcomes.
    Below this, an ML model will overfit.

G3. Regime coverage
    Labels span at least two distinct market regimes (e.g., a
    bull and a sideways/correction period). Single-regime training
    sets create models that fail catastrophically on regime change.

G4. Self-drift bounded
    Quarterly re-grading shows <15% disagreement with original
    decisions on rolling 6-month samples. If labels are
    drifting, the training data is poisoned.

G5. Articulable failure mode
    User can name a specific class of false positives or false
    negatives the rules make and explain why ML would address it.
    "Just feels like the rules miss things" is not enough.

G6. Feature stability
    Rule-based feature definitions have been stable for three
    months. Otherwise, training data has incompatible features
    across time.

G7. Operational bandwidth
    User has weekly time available for drift monitoring and
    quarterly time for retraining. If not, the model will rot
    silently.
```

If any gate fails, the answer is "not yet" rather than "no" — the gates are addressable over time.

### Z.6 Recommendation

**Defer ML implementation 12–18 months minimum.** Use the time to build, deploy, and use the rule-based + template-matching system; accumulate organic labels through trade history; develop intuition for specific failure modes the rules exhibit. When the gates are met, start with the simplest viable model — gradient-boosted trees over engineered features as a Role-2 re-ranker — *not* a CNN over chart images, *not* a sequence model. Calibrate the output (Platt scaling or isotonic regression). Evaluate against rule-only baseline on a temporally held-out set. If it does not beat the baseline by enough margin to justify the maintenance, do not ship it.

A reasonable concrete plan when the gates are reached:

```text
1. Engineered features (50-100 features over the candidate window):
   - Geometric: contractions, depths, durations, slopes, ratios.
   - Statistical: ATR, volatility regimes, volume Z-scores.
   - Trend: distance from MAs, MA slopes, RS rank.
   - Pattern-specific: VCP contraction monotonicity score, etc.
2. Model: LightGBM or XGBoost, modest depth (3-6), modest n_estimators (200-500).
3. Target: binary "user confirmed" label, or graded confirmation if available.
4. Training: temporal split, train on older 80%, validate on most recent 20%.
5. Calibration: isotonic regression on validation predictions.
6. Evaluation: top-K precision, calibration curve, lift over rule-only baseline.
7. Deployment: as a re-ranker over rule-confirmed candidates, never as a primary detector.
```

Such a model fits in <100MB on disk, runs in milliseconds on CPU, and does not even use the 4070.

The 4070 is most likely useful for the *training data generation* side (running embedding models for similarity search, or local LLMs for labeling assistance), not for production inference.

## Δ §14 Recommended Starting Point — CHANGED

Replace with the phased starting point that matches the new §9:

```text
Start with:
1. Universe pipeline + trend-template filter.
2. Curated exemplar set (30-100 examples per primary pattern).
3. Rule-based VCP detector.
4. AI-assisted parameter tuning against exemplars.
5. Single-user review interface.
6. Trade-action and outcome capture, back-linked to candidates.
7. Composite scoring (rule-based geometric + template similarity).

Add over time:
8. Additional pattern detectors (CWH, FB, HTF, DBW).
9. Sell-side detector module (H&S top, climax, MA breakdown).
10. Drift detection dashboards.
11. Matrix Profile-based exemplar retrieval.
12. (Gated) Small ML re-ranker.
```

## Δ §15 References — CHANGED

Add to the reference list:

- **Minervini, M.** *Trade Like a Stock Market Wizard.* Defines VCP, trend template, stage analysis specifics for swing trading.
- **O'Neil, W.J.** *How to Make Money in Stocks.* CANSLIM, cup-with-handle, base structures.
- **Weinstein, S.** *Secrets for Profiting in Bull and Bear Markets.* Stage analysis foundation.
- **Bulkowski, T.** *Encyclopedia of Chart Patterns.* Empirical base-rate reference. Even if most patterns are not used, his measurement methodology matters.
- **Yeh et al. — Matrix Profile** papers (ICDM 2016 onward).
- **Ye & Keogh (2009), KDD.** Time series shapelets foundational paper.
- **Berndt & Clifford (1994), KDD workshop.** Original DTW for time series.
- **Lopez de Prado, *Advances in Financial Machine Learning*.** Specifically for the data-snooping, multiple-comparisons, and labeling-with-outcomes treatment.
- **Marshall, Young, and Rose (2006), Journal of Banking & Finance.** Empirical evaluation of candlestick patterns showing weak-to-zero predictive power; necessary counterweight to §5.5.

The MDPI Sustainability DTW paper and the PLOS ONE candlestick paper from the original list are real but incidental. They can stay or be replaced with stronger versions of the same topics. The Kim et al. 2025 shapelet paper is fine as a recent example but should be paired with Ye & Keogh.
