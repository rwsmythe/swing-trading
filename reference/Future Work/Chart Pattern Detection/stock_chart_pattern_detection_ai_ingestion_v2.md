---
title: "Swing-Trading Chart Pattern Detection: Approaches and Requirements"
purpose: "AI-ingestible analysis brief"
topic: "Mathematical and data-strategy options for swing-trading chart pattern detection with single-user review"
version: "2.0"
supersedes: "stock_chart_pattern_detection_ai_ingestion.md v1.0"
created: "2026-05-08"
intended_use:
  - "AI ingestion"
  - "Requirements analysis"
  - "Approach comparison"
  - "System design planning"
scope:
  context:
    - "Tool target: swing trading (Minervini/CANSLIM family)"
    - "Operation: end-of-day batch on daily and weekly bars"
    - "Production constraint: rule-based or small local ML model on 8GB GPU"
    - "User: single user, AI-assisted development"
    - "System role: pattern detection module within broader trading decision support system"
  included:
    - "Mathematical strategies for pattern detection"
    - "Universe pre-filtering and data requirements"
    - "Development-time data strategy (AI-assisted labeling, synthetic, perturbation)"
    - "Human-review workflow with closed-loop outcome feedback"
    - "Drift detection strategy"
    - "ML model decision analysis with implementation gates"
    - "Recommended phased roadmap"
    - "Integration points with broader trading system"
  excluded:
    - "Data acquisition implementation"
    - "Trade execution and broker integration"
    - "Position sizing and risk management"
    - "Intraday/tick data and real-time detection"
    - "Multi-user/team workflows"
    - "Production code"
---

# Swing-Trading Chart Pattern Detection: Approaches and Requirements

## 1. Objective

Develop a tool that analyzes EOD stock chart data, identifies likely swing-trading setups, and flags those setups for single-user review as part of a broader trading decision-support system.

The tool is a **pattern-candidate detector** that:

1. Processes daily and weekly bar data on a filtered universe.
2. Identifies segments that may contain recognizable swing-trading setups.
3. Assigns one or more likely pattern labels.
4. Provides explicit, introspectable evidence for each label.
5. Allows a single human reviewer to confirm, watch, reject, or relabel.
6. Stores reviewer decisions, trade actions taken, and trade outcomes — all back-linked to the originating candidate — for closed-loop calibration.

The introspection requirement (item 4) is a hard constraint, not a preference. With no second reviewer and the tool driving real capital allocation decisions, the user must be able to see the evidence behind a flag. This rules out black-box production methods regardless of computational fit.

## 2. Core Framing

The system distinguishes four separate questions:

```text
Question A: Is a recognizable pattern present?
Question B: Is the pattern predictive in this regime?
Question C: How many false positives does pattern density imply by chance?
Question D: Is *my* implementation of trading this pattern profitable, given my discipline?
```

For the initial tool build, focus on **Question A**. Question B is addressed indirectly through outcome tracking. Question C is addressed through universe pre-filtering and pattern frequency monitoring. Question D is addressed through closed-loop integration of trade actions and outcomes back to candidates.

Question D is what makes this system specifically a swing-trading tool rather than a generic pattern detector: it incorporates user behavior (discipline, missed opportunities, deviations) alongside market behavior. The trade history → shape library mechanism implicitly answers Question D over time.

## 3. Detection Unit

| Design Area | Selected |
|---|---|
| Input data | Adjusted OHLCV |
| Bar type | Daily primary; weekly as confirmation context; Heikin-Ashi optional view |
| Adjustment | Split- and dividend-adjusted |
| Window construction | Variable-window with anchor-point search |
| Output type | Pattern label + confidence + structural evidence + uncertainty |

Streaming/intraday detection, real-time bar formation, and tick data are out of scope for this version. The system operates as an asynchronous EOD batch.

VCP-style patterns have variable durations from a few weeks to several months, so fixed windows are inadequate. The right primitive is a variable-window candidate generator that searches for plausible base-start anchors and scales window size accordingly.

## 4. Candidate Pattern Categories

The pattern set is scoped to swing-trading setups in the Minervini/CANSLIM tradition. The Volatility Contraction Pattern (VCP) — Minervini's signature setup — is the highest-priority pattern.

### 4.1 Primary Buy-Side Patterns

| Pattern | Source/Methodology | Mathematical Tractability |
|---|---|---|
| Volatility Contraction Pattern (VCP) | Minervini | High — sequence of contractions with monotonically decreasing depth %, declining volume, defined duration |
| Cup-with-handle | O'Neil/CANSLIM | High — rounded base + shallow pullback handle with defined depth/duration ratios |
| Flat base | O'Neil/CANSLIM | High — bounded range with low slope and tight ATR for ≥5–7 weeks |
| High-tight flag | Minervini/O'Neil | High — defined prior advance % and tight consolidation % |
| Double-bottom W (with shakeout/undercut) | Both | Medium-High — two troughs with center peak, optional undercut of first low |
| Pole-and-flag and tight-channel variants | Both | Medium — variations on flag structure |
| Power play / IPO base | Minervini | Medium — large advance from IPO + shallow base |

### 4.2 Upstream Context (Pre-conditions, Not Patterns)

| Context | Source | Role |
|---|---|---|
| Stage 2 uptrend | Weinstein/Minervini | Required pre-condition; filter out Stage 1, 3, 4 |
| Trend template | Minervini | Universe pre-filter (price > MA50 > MA150 > MA200, MA200 trending up, 52w high/low position, RS rank) |
| Relative strength rank | O'Neil/CANSLIM | Universe pre-filter |
| Liquidity / market cap floor | Both | Universe pre-filter |

### 4.3 Sell-Side Patterns (Separate Detector Module)

| Pattern | Role |
|---|---|
| Head and shoulders top | Minervini sell signal |
| Climax run / parabolic exhaustion | Minervini sell signal |
| Stage 4 breakdown | Weinstein sell signal |
| MA50/MA200 violations | Both, exit triggers |

### 4.4 Out-of-Scope Pattern Families

Noted but not in roadmap: harmonic patterns (Gartley, Bat, Butterfly), candlestick patterns (Marshall et al. 2006 found weak-to-zero predictive power on developed-market equity), classical reversal patterns not used in swing-trading vocabulary, intraday patterns. These can be revisited if scope expands.

## 5. Mathematical and Analytical Approaches

### 5.1 Rule-Based Geometric Detection (PRIMARY)

Rule-based detection defines each pattern using explicit mathematical criteria. For the swing-trading pattern set, the patterns are tractable enough that rules should be the production backbone.

Typical inputs:
- Local maxima and minima (extracted via zigzag with adaptive threshold or smoothed extrema)
- Relative peak heights and trough depths
- Trendline slopes
- Duration constraints
- Volume behavior at extrema and on breakouts
- Trend-template state (Stage 2)

Illustrative VCP candidate criteria:

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

Strengths:
- Highly interpretable (critical given single-user reviewer).
- Easy to show evidence to the reviewer.
- Low data-label requirement.
- Strong fit to swing-trading patterns where structure is mathematically encodable.
- Generates labeled training data for any later ML extension.

Weaknesses:
- Requires hand-tuned thresholds (mitigated by AI-assisted parameter tuning).
- May reject visually valid but imperfect patterns (mitigated by template matching layer).
- Tolerance bands are subjective; different traders use different thresholds.

### 5.2 Smoothing and Extrema Extraction (FOUNDATION)

Raw prices are noisy. Many chart patterns are easier to identify after reducing small fluctuations.

Possible smoothing methods:
- Simple moving average
- Exponential moving average
- Kernel regression (Lo, Mamaysky, and Wang's approach for formal pattern detection)
- Local polynomial regression
- Spline smoothing
- Wavelet denoising
- Piecewise linear approximation

Extrema extraction methods:
- Zigzag indicator with adaptive percentage threshold — de facto standard for chart pattern detection
- Perceptually Important Points (PIPs) — specifically designed for chart pattern matching
- Local maxima/minima after smoothing

For VCP detection specifically, zigzag with adaptive percentage threshold is essentially the right primitive: each zigzag swing corresponds directly to one contraction in the VCP sequence.

Strengths:
- Useful for all geometric chart patterns.
- Helps reduce false positives caused by noise.
- Provides a compact representation of chart shape.

Weaknesses:
- Results depend heavily on smoothing settings.
- Smoothing strength defines the temporal scale of detected patterns; a single setting will miss patterns at other scales (motivates multi-scale detection).
- Naive smoothers (moving averages) introduce lag; centered methods (kernel regression) do not but cannot be applied to the most recent data points.

### 5.3 Template Matching and Similarity Scoring (STRONG SECONDARY)

Template matching compares a candidate chart segment against one or more known reference patterns.

This fits naturally with the trade-history-as-shape-library mechanism: each confirmed entry from past trades becomes a template, and the library grows organically over time.

Two retrieval modes:
- "Show me historical bases that look like this candidate" (forward retrieval)
- "Show me candidates that look like this confirmed historical base" (reverse retrieval)

Possible distance/similarity methods:

| Method | Use Case |
|---|---|
| Euclidean distance | Same-length normalized windows |
| Correlation distance | Shape similarity independent of scale |
| Dynamic Time Warping (constrained) | Shape similarity with time stretching/compression |
| Shape-Based Distance (SBD) | Cross-correlation-based, used in k-Shape clustering |
| Feature-vector distance | Compare slopes, extrema, ratios, and durations |

DTW caveat: unconstrained DTW can over-warp, matching patterns that don't actually look alike to a human. Use Sakoe-Chiba band or Itakura parallelogram constraints.

Strengths:
- More flexible than rigid rules.
- Can rank candidates by similarity.
- Naturally accommodates the growing trade-history shape library.
- Useful for "looks like this" reviewer presentations.

Weaknesses:
- Requires representative templates (bootstrap problem for early-stage tool).
- Normalization choices strongly affect results.
- Template proliferation eventually causes nearest-neighbor search to slow without an index.

### 5.4 Feature-Based Supervised Classification (DEFERRED, GATED)

Converts chart windows into structured feature vectors and trains a classifier. This is the natural home for the optional small ML re-ranker (see §16).

Possible feature groups:

| Feature Group | Examples |
|---|---|
| Geometric | Contractions, depths, durations, slopes, ratios |
| Statistical | ATR, rolling standard deviation, realized volatility |
| Volume | Volume trend, breakout volume, price-volume divergence |
| Trend | Distance from MAs, MA slopes, RS rank |
| Pattern-specific | VCP contraction monotonicity score, base width, etc. |

Possible models suitable for 8GB local production:
- Logistic regression (calibrated)
- Random forest
- Gradient boosting (LightGBM / XGBoost)
- Calibrated probabilistic classifier wrappers

Class imbalance is the defining practical problem — true positives are rare, and naïve classifiers will trivially predict "no pattern." Calibration is also essential: rule-based geometric scores are not probabilities, and any "confidence score" used to gate decisions must be calibrated (Platt scaling or isotonic regression).

This category is deferred until the gates in §16 are met.

### 5.5 Candlestick-Specific Pattern Detection (DEMOTED)

Brief mention only. Marshall, Young, and Rose (2006) found weak-to-zero predictive power for most named candlestick patterns on developed-market equity. Not a primary module for this tool.

### 5.6 Image-Based Computer Vision (NOT RECOMMENDED)

Renders chart windows as images and applies computer vision models.

Compounding weaknesses:
- Information-destructive: OHLCV is already structured, low-dimensional, clean numerical data; rasterizing it and back-solving is throwing away precision.
- Sensitive to rendering choices (scaling, colors, axes, indicators).
- Less interpretable than rule-based systems.
- Requires many labeled images.

Doubly unappealing here: even if a small CNN fits in 8GB, the interpretability cost violates the introspection requirement (§1, item 4).

### 5.7 Sequence Models (OUT OF SCOPE)

LSTMs, transformers, and TCNs over OHLCV sequences. Out of scope for production:
- Large variants don't fit the 8GB constraint.
- Small variants are essentially uninterpretable for a single-user reviewer.

Noted in passing for completeness only.

### 5.8 Unsupervised Motif Discovery and Clustering (NEAR-TERM VIABLE)

Searches for recurring shapes without predefined labels. **Matrix Profile (Yeh, Zhu, Keogh et al.)** is the modern state of the art and is specifically useful for this tool's use case.

Matrix Profile use case here:
- "Find historical bases across my universe that look like this confirmed VCP."
- Fast, parameter-free, well-documented.
- Fits naturally with the shape library as it grows.

Other representations:
- Symbolic Aggregate Approximation (SAX) — fast indexed search via lower-bounding
- Piecewise Aggregate Approximation
- Wavelet coefficients
- Autoencoder embeddings

### 5.9 Shapelet-Based Detection (LATER, GATED)

Short subsequences highly discriminative of a class. Foundational reference: Ye & Keogh (2009). Recent extensions (Grabocka et al. 2014 learnable shapelets; ShapeNet by Li et al. 2021) reduce computational cost.

Defer until labeled corpus exists.

## 6. Data Requirements

### 6.1 Universe Pipeline

Universe pre-filtering is upstream of pattern detection and dramatically reduces the multiple-comparisons surface area:

```text
Universe pipeline:
  All listed equities
  -> Liquidity filter (avg dollar volume threshold)
  -> Market cap floor
  -> Stage 2 / trend template filter
  -> RS rank filter
  -> Pattern-detection candidate pool (typically 200-500 names)
```

This stage runs once per day. With ~200–500 names × ~5–7 patterns × 1 timeframe primary, the system runs ~1500–3500 pattern tests per day. The multiple-comparisons concern is real but tractable.

### 6.2 Minimum Market Data

Required fields:

| Field | Purpose |
|---|---|
| Open | Candlestick structure and gaps |
| High | Extrema, resistance, wick structure |
| Low | Extrema, support, wick structure |
| Close | Returns, trend, breakout validation |
| Volume | Breakout and confirmation signal |
| Adjusted prices | Split/dividend consistency |
| Dollar volume | Liquidity filter |
| RS rank | Universe filter, pattern feature |
| MA50, MA150, MA200 (and slopes) | Trend template, pattern features |

### 6.3 Historical Coverage

The dataset should include:
- Multiple tickers across sectors.
- Multiple market regimes (bull, bear, sideways).
- Different volatility regimes.
- Sufficient examples of both patterns and non-patterns.
- **Delisted-stock data is essential** — the trend template specifically selects for currently-uptrending names; without delisted stocks, the "stocks that *were* in stage 2 and then broke down" cohort is unobservable. Survivorship bias is more acute under trend-template universe selection than under random sampling.

### 6.4 Label Schema (Single-User)

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

The `quality_grade` field enables self-drift detection: periodically re-rate old confirmed patterns. If grading drifts, that is the signal.

### 6.5 Negative and Ambiguous Examples

```text
confirmed_traded         (positive labels with outcome data)
confirmed_not_traded     (positive labels, opportunity-cost data)
watch_list_no_action     (ambiguous, watched but never triggered entry)
detector_flagged_rejected (negative labels)
near_miss_rejected        (failed one specific rule — most informative negatives)
```

Do not discard rejected candidates. They are the most valuable training negatives.

## 7. Normalization and Transformation

Pattern detection should usually avoid raw price-level comparison.

Common transformations:

| Transformation | Purpose |
|---|---|
| Percentage returns | Removes absolute price-level dependency |
| Log returns | Creates additive return representation |
| Z-score normalization | Compares shape independent of level and volatility |
| Min-max scaling | Normalizes visual chart shape |
| Volatility scaling | Reduces dominance of high-volatility instruments |
| Detrending | Focuses on local structure |
| Pattern-specific normalization | E.g., normalize VCP candidates by height of prior advance |

Robust normalization (median/MAD) is preferred over mean/std for windows containing gaps, since gaps can dominate standard z-scoring.

Core invariance questions:

```text
Should the detector ignore absolute price level?     [Yes for shape; relative for breakouts]
Should the detector ignore volatility level?         [Yes for shape; condition on it for thresholds]
Should the detector tolerate time stretching?        [Yes within bounds]
Should the detector tolerate imperfect symmetry?     [Yes within bounds]
Should the detector require volume confirmation?     [Yes for breakout phase]
Should the detector require a breakout?              [Optional; pre-breakout flag is also useful]
```

## 8. Development Data Strategy

This section addresses how to bootstrap a working detector and labeled corpus given single-user bandwidth constraints. Five sources, in rough priority order.

### 8.1 Historical Exemplar Harvest

```text
- Curated "textbook" examples from books and IBD/Minervini archives.
- Hand-marked anchor points (left side, base start, contractions, pivot, breakout).
- Small set, high quality. ~30-100 per pattern class.
- Used as gold-standard validation set throughout development.
```

### 8.2 AI-Assisted Labeling at Scale

```text
- Claude Code processes candidate windows from rule-based detector.
- Returns pattern class + confidence + structural notes.
- User spot-checks a sample (10-20%) for calibration.
- Use AI labels as silver-standard training data with explicit silver/gold tags.
- Track AI-labeler version; results from different versions are not interchangeable.
```

### 8.3 Parametric Synthetic Generation

Especially clean for VCP, since the pattern is mathematically defined:

```text
- Random sampling over parameter space:
  - Contraction count {2, 3, 4}
  - Depth sequences with monotonicity constraints
  - Durations
  - Volume profiles
  - Base widths
  - Prior-trend strengths
- Embed synthetic patterns into real noise backgrounds:
  - Sample real Stage-2 segments
  - Splice in synthetic bases
- Generate negative examples by intentionally violating constraints
  (e.g., non-monotonic contraction sequence).
```

### 8.4 Perturbation of Confirmed Examples

```text
- Time stretching / compression within tolerance bands.
- Amplitude scaling.
- Volume profile perturbation.
- Adding small noise.
- Yields useful training data without inventing structure.
```

### 8.5 Organic Accumulation from Trade History

```text
- Slow but high-quality (~100-300 reviewed candidates per year).
- Real labels with real outcomes.
- The eventual ground truth.
- Closed-loop: trade outcomes back-link to originating candidates.
```

### 8.6 Source Tagging and Mixed Training

Keep these sources tagged in the corpus. Models trained on synthetic data alone fail on real data; models trained on real data alone are sample-starved. The right approach is **mixed training with stratified evaluation**: evaluate on held-out real-only subset, never on synthetic.

Source bias profiles:

| Source | Quality | Volume | Bias |
|---|---|---|---|
| Curated exemplars | High | Low | Curator selection bias |
| AI-assisted labels | Medium | High | Labeler-model bias |
| Synthetic | Medium | Unbounded | Misses real-world noise distribution |
| Perturbation | Medium | Bounded by source | Inherits source bias |
| Organic | Highest | Slow | User decision bias |

## 9. Human-Review Workflow

Single-user review with closed-loop outcome feedback.

### 9.1 Candidate Lifecycle

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

### 9.2 Evidence to Show Reviewer

For each candidate, the review interface should show:
- Proposed pattern class.
- Geometric score breakdown by rule component (which rules passed, which marginally, which failed).
- Top-3 nearest historical bases (template matches), including both confirmed positives and notable failures.
- Trend-template status for the ticker.
- RS rank.
- Recent volume profile.
- Reason for any uncertainty in rule evaluation.
- **Outcome distribution from prior similar candidates**: "of the last 20 VCPs flagged with similar scores, X% triggered, Y% reached 1R, Z% hit stop."

The last item closes the loop. It is what distinguishes this from a generic pattern detector.

### 9.3 Reviewer Decision Types

| Decision | Meaning |
|---|---|
| Confirm | Pattern is valid and tradeable now |
| Watch | Pattern is valid but not yet tradeable (e.g., pre-breakout) |
| Reject | No valid pattern |
| Relabel | Pattern exists but proposed class is wrong |
| Pattern-present-outside-window | Real pattern, system framed it wrong |
| Multiple-overlapping-patterns | More than one valid pattern in window |

### 9.4 Active Learning Prioritization

User review bandwidth is the bottleneck. Prioritize candidates whose review labels would most improve the rule set:
- Borderline geometric scores (uncertain rule evaluation).
- High template-match score but low geometric score, or vice versa (rule/template disagreement).
- Patterns from regimes underrepresented in current corpus.
- Failed-rule near-misses (informative negatives).

## 10. Recommended Initial Strategy

Phased approach, each phase delivering standalone value.

**Phase 0:** Universe pipeline and trend-template filter. Standalone module, valuable on day one even before any pattern detection.

**Phase 1:** Rule-based detection of VCP, flat base, cup-with-handle. AI-assisted parameter tuning against curated exemplars. Single composite score per pattern. Manual review of every flagged candidate.

**Phase 2:** Template matching against curated exemplar set. Two retrieval modes (forward and reverse). DTW with constrained warping or shape-based distance.

**Phase 3:** Add high-tight flag and double-bottom-W detectors. Same rule-based + template approach.

**Phase 4:** Closed-loop integration. Trade actions and outcomes back-linked to candidates. Outcome distributions surfaced in review interface.

**Phase 5:** Drift detection. Feature drift, pattern frequency drift, outcome drift dashboards.

**Phase 6 (gated):** Optional small ML re-ranker. See §16 for whether and when.

**Phase 7 (gated):** Matrix Profile-based exemplar retrieval at scale. Once curated exemplar set is large enough.

**Phase 8 (gated):** Sell-side detector module (H&S top, climax, MA breakdown).

## 11. Approach Comparison

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

## 12. Suggested System Architecture

Pattern detection is one module within a broader trading decision-support system. The architecture below shows integration points with adjacent modules that are formally out of scope for this document but consume from or feed into pattern detection.

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
  -> ML training (gated; see §16)
```

The Decision Support Layer is the user-facing surface; the Performance/Discipline and Drift/Calibration layers operate continuously in the background; the Development Substrate operates offline during build cycles.

## 13. Evaluation Metrics

Closed-loop, single-user metrics differ from generic pattern-detection metrics.

### 13.1 Detection Metrics

```text
Precision (of flagged, how many user confirms)
Recall (against curated exemplar set; cannot be measured against universe)
Calibration (Brier score, reliability diagram for composite scores)
Top-K precision (of top 5/10/20 ranked, how many user confirms)
Candidate density per day (workflow load)
Ranking metrics (NDCG, MAP) for ranked candidate streams
```

### 13.2 Closed-Loop Outcome Metrics

```text
Score-conditioned hit rate (does composite score predict trade success?)
Score-conditioned R-multiple distribution
Time-to-resolution (how long until pattern triggers or fails)
Failed-pattern characterization (what do failures have in common?)
Forward-return distribution at multiple horizons (5, 10, 20 days)
```

### 13.3 Discipline Metrics

```text
Recommendation adherence rate
Outcome divergence between adhered and deviated trades
Time-of-day or fatigue effects on adherence
Missed-opportunity rate (confirmed but not traded -> outcome would have been positive)
```

### 13.4 Drift Metrics (detail in §14)

```text
Feature distribution KL or PSI vs trailing baseline
Pattern frequency per universe size, vs trailing baseline
Hit-rate decay vs trailing baseline (regime change indicator)
Self-drift rate (re-grading disagreement)
```

Calibration is essential: any "confidence score" used to gate decisions must be calibrated. Brier score and reliability diagrams are the diagnostic tools.

## 14. Drift Detection

Drift detection is a first-class system component, not a footnote. Four drift surfaces:

### 14.1 Feature Drift

```text
Monitor distribution shifts in input features (volatility, breadth,
trend-template pass rate across universe, RS distributions).
Tool: Population Stability Index or KL divergence vs trailing 1y baseline.
Trigger: PSI > 0.25 on any monitored feature.
Action: investigate; may indicate regime shift or data pipeline change.
```

### 14.2 Pattern Frequency Drift

```text
Monitor candidate density per pattern class.
Bear regimes produce few VCPs; sideways markets produce many flat bases.
Trigger: pattern density falls below or rises above trailing-90d baseline by >2 sigma.
Action: not retraining — *interpretation* (regime shift, not detector failure).
        May warrant universe filter relaxation or pattern class pause.
```

### 14.3 Outcome Drift

```text
Monitor hit rate and R-multiple distribution per pattern class.
Falling hit rate while feature/frequency stable = pattern degradation.
Falling hit rate while features also drifting = regime change.
Trigger: 20-trade rolling hit rate falls >X% below trailing baseline.
Action: investigate, possibly tighten rules or pause pattern class entirely.
```

### 14.4 Self-Drift

```text
Periodic re-grading of historical decisions.
Compare current grades to original grades on same charts.
Trigger: grade-disagreement rate > 15% on rolling 6-month sample.
Action: examine systematic shift; recalibrate or document rationale.
        Drift may be improvement (learning) or degradation (fatigue, overconfidence).
```

## 15. Key Risks

| Risk | Mitigation |
|---|---|
| Multiple comparisons | Tractable at this scope (~1500–3500 tests/day); universe pre-filter reduces surface; pattern frequency monitoring catches density anomalies |
| Survivorship bias | Use delisted-stock data; especially important under trend-template universe selection |
| Self-drift | Quarterly re-grading; quality_grade field in label schema |
| Outcome attribution confusion | Track market regime alongside outcomes; condition outcome metrics on regime |
| Overfitting rules to recent regime | Tune against multi-regime data; never tune against single bull/bear period |
| Synthetic-to-real gap | Always evaluate on real-only held-out set; never on synthetic |
| Trade-history leakage in evaluation | Strict temporal splits; train on older 80%, validate on most recent 20% |
| Labeling-with-AI bias | Spot-check 10-20% of AI labels; calibrate against outcomes |
| Brittle thresholds | Tolerance bands; template matching layer; AI-assisted parameter tuning |
| Lookahead bias | EOD batch operates only on closed bars; no streaming detection |
| Confusing recognition with prediction | Track Question A separately from Question B/D outcomes |
| Stage-mismatch detection | Trend-template gate before pattern detection; Stage 1/3/4 stocks excluded |

## 16. Small ML Model Decision Analysis

Whether and when to add a small ML model on top of the rule-based + template-matching system.

### 16.1 Plausible Roles for an ML Model

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
  Replaces: nothing; adds a calibrated layer above rules
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

### 16.2 The Case For a Small ML Re-Ranker

- Personal calibration: user preferences for "tradeable VCP" almost certainly differ from textbook in ways awkward to encode as rules but easy to learn from decisions.
- Calibrated probabilities: rule-based scores are not probabilities; a re-ranker can produce calibrated outputs supporting principled gating.
- Feature interactions: rules treat features additively; a small GBM captures meaningful interactions.
- Closed-loop adaptation: as label corpus grows, the re-ranker can be retrained periodically.

### 16.3 The Case For Not Implementing One Yet

- Label scarcity: organic accumulation yields ~100–300 reviewed candidates per year; meaningful evaluation needs more.
- Synthetic data has bounded utility for the re-ranker problem (less so for rule tuning).
- Maintenance overhead: drift monitoring, retraining, version management, evaluation harness.
- Risk of fitting your own mistakes: re-ranker reproduces user decisions including bad ones; hard to detect without external ground truth.
- Diminishing returns: rules + templates may capture 85–90% of achievable performance.
- Opportunity cost: ML build time competes with rule refinement and tool usage.

### 16.4 Cost/Benefit at This Scale

| Dimension | Rule-based + templates only | + Small ML re-ranker |
|---|---|---|
| Build time | Lower | +20–40% additional |
| Maintenance burden | Low | Medium (drift, retraining) |
| Interpretability | High | Medium (with SHAP, manageable) |
| Labels needed | 30–100 exemplars per pattern | 300+ per pattern with outcomes |
| Time to first useful output | Weeks | 12–18 months minimum |
| Marginal performance gain | Baseline | +5–15% on well-defined metric |

### 16.5 Implementation Gates

Implement the re-ranker only when *all* of the following are true:

```text
G1. Rule saturation
    Three or more iterations of rule tuning have produced
    <5% improvement on a held-out validation metric.
    Without this, ML masks rule-tuning laziness.

G2. Label volume
    At least 200 confirmed positive examples per pattern class,
    of which at least 100 have associated trade outcomes.
    Below this, an ML model overfits.

G3. Regime coverage
    Labels span at least two distinct market regimes.
    Single-regime training sets fail catastrophically on regime change.

G4. Self-drift bounded
    Quarterly re-grading shows <15% disagreement with original
    decisions on rolling 6-month samples.
    If labels are drifting, training data is poisoned.

G5. Articulable failure mode
    User can name a specific class of false positives or false
    negatives the rules make and explain why ML would address it.
    "Just feels like the rules miss things" is not enough.

G6. Feature stability
    Rule-based feature definitions stable for three months.
    Otherwise training data has incompatible features across time.

G7. Operational bandwidth
    Weekly time available for drift monitoring and quarterly
    time for retraining. Without this, the model rots silently.
```

Failed gates indicate "not yet" rather than "no." Gates are addressable over time.

### 16.6 Recommendation

**Defer ML implementation 12–18 months minimum.** Use the time to build, deploy, and use the rule-based + template-matching system; accumulate organic labels through trade history; develop intuition for specific failure modes the rules exhibit.

When the gates are met, the recommended initial implementation:

```text
1. Engineered features (50-100 features over the candidate window):
   - Geometric: contractions, depths, durations, slopes, ratios
   - Statistical: ATR, volatility regimes, volume Z-scores
   - Trend: distance from MAs, MA slopes, RS rank
   - Pattern-specific: VCP contraction monotonicity score, etc.
2. Model: LightGBM or XGBoost, modest depth (3-6), modest n_estimators (200-500).
3. Target: binary "user confirmed" label, or graded confirmation if available.
4. Training: temporal split, train on older 80%, validate on most recent 20%.
5. Calibration: isotonic regression on validation predictions.
6. Evaluation: top-K precision, calibration curve, lift over rule-only baseline.
7. Deployment: as a re-ranker over rule-confirmed candidates,
   never as a primary detector.
```

Such a model fits in <100MB on disk, runs in milliseconds on CPU, and does not even use the GPU.

The 8GB GPU is more likely useful for the *training data generation* side (running embedding models for similarity search, or local LLMs for labeling assistance), not for production inference.

## 17. Recommended Starting Point

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

## 18. References

### 18.1 Foundational Literature

1. **Lo, Mamaysky, and Wang.** *Foundations of Technical Analysis: Computational Algorithms, Statistical Inference, and Empirical Implementation.* Journal of Finance, 2000.
   URL: https://www.cis.upenn.edu/~mkearns/teaching/cis700/lo.pdf

2. **Edwards, R.D., Magee, J.** *Technical Analysis of Stock Trends.*

3. **Bulkowski, T.** *Encyclopedia of Chart Patterns.* Wiley.

### 18.2 Swing-Trading Methodologies

4. **Minervini, M.** *Trade Like a Stock Market Wizard.* Defines VCP, trend template, stage analysis specifics for swing trading.

5. **O'Neil, W.J.** *How to Make Money in Stocks.* CANSLIM, cup-with-handle, base structures.

6. **Weinstein, S.** *Secrets for Profiting in Bull and Bear Markets.* Stage analysis foundation.

### 18.3 Algorithmic Foundations

7. **Berndt, D.J. and Clifford, J. (1994).** Using Dynamic Time Warping to Find Patterns in Time Series. KDD Workshop.

8. **Ye, L. and Keogh, E. (2009).** Time series shapelets: a new primitive for data mining. KDD.

9. **Yeh, Zhu, Ulanova, Begum, Ding, Dau, Silva, Mueen, Keogh.** Matrix Profile papers, ICDM 2016 onward.

10. **Chung, F.L., Fu, T.C., Luk, R., Ng, V.** Perceptually Important Points (PIPs) for time series pattern matching.

### 18.4 Empirical Studies and Surveys

11. **Marshall, B.R., Young, M.R., Rose, L.C. (2006).** Candlestick Technical Trading Strategies: Can They Create Value for Investors? Journal of Banking & Finance. (Counterweight to candlestick approaches.)

12. **Lopez de Prado, M.** *Advances in Financial Machine Learning.* Data-snooping, multiple-comparisons, and labeling-with-outcomes treatment.

### 18.5 Recent Domain Applications

13. **Velay, M. and Daniel, F. (2018).** Stock Chart Pattern Recognition with Deep Learning. arXiv:1808.00418.

14. **Kim, S.H. et al. (2018).** Pattern Matching Trading System Based on the Dynamic Time Warping Algorithm. Sustainability, MDPI, 10(12), 4641.
    URL: https://www.mdpi.com/2071-1050/10/12/4641

15. **Improving stock trading decisions based on pattern recognition using machine learning technology.** PLOS ONE, 2021.
    URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC8345893/

16. **Kim, J. et al. (2025).** From Patterns to Predictions: A Shapelet-Based Framework for Directional Forecasting in Noisy Financial Markets. CIKM 2025.
    URL: https://arxiv.org/abs/2509.15040
