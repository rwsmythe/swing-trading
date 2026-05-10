---
title: "Initial Approaches for Stock Chart Pattern Identification"
purpose: "AI-ingestible analysis brief"
topic: "Mathematical and data-strategy options for detecting stock chart patterns with human review"
version: "1.0"
created: "2026-05-08"
intended_use:
  - "AI ingestion"
  - "Requirements analysis"
  - "Approach comparison"
  - "System design planning"
scope:
  included:
    - "Mathematical strategies for pattern detection"
    - "Data requirements"
    - "Human-review workflow"
    - "Recommended staged approach"
  excluded:
    - "Data acquisition implementation"
    - "Trading execution"
    - "Broker integration"
    - "Production code"
---

# Initial Approaches for Stock Chart Pattern Identification

## 1. Objective

Develop a tool that analyzes stock chart data, identifies likely visual or mathematical chart patterns, and flags those patterns for human review.

The initial objective is not to build an autonomous trading system. The objective is to build a **pattern-candidate detector** that:

1. Processes historical or streaming chart data.
2. Identifies segments that may contain recognizable chart patterns.
3. Assigns one or more likely pattern labels.
4. Provides evidence for the label.
5. Allows a human reviewer to confirm, deny, relabel, or mark the result as uncertain.
6. Stores reviewer feedback for future calibration or model training.

## 2. Core Framing

The system should distinguish between two separate questions:

```text
Question A: Is a recognizable pattern visually or mathematically present?
Question B: Is the pattern predictive or profitable?
```

For the initial tool, focus on **Question A**.

Question B can be analyzed later by tracking post-pattern outcomes.

## 3. Detection Unit

Before selecting a mathematical approach, define the unit of analysis.

| Design Area | Options |
|---|---|
| Input data | Close-only, OHLC, OHLCV, returns, log returns |
| Timeframe | Intraday, daily, weekly, multi-timeframe |
| Window type | Fixed window, variable window, rolling window, event-based segment |
| Pattern type | Candlestick, geometric chart pattern, trend/regime pattern |
| Output type | Single label, multiple labels, confidence score, uncertainty score, no-pattern label |

## 4. Candidate Pattern Categories

Initial target patterns may include:

| Pattern Category | Examples |
|---|---|
| Reversal patterns | Double top, double bottom, head and shoulders, inverse head and shoulders |
| Continuation patterns | Flags, pennants, channels |
| Consolidation patterns | Rectangles, trading ranges, triangles |
| Breakout patterns | Range breakout, neckline break, resistance break, support break |
| Candlestick patterns | Doji, hammer, engulfing, morning star, evening star |
| Structural patterns | Cup and handle, rounded bottom, wedge |

## 5. Mathematical and Analytical Approaches

### 5.1 Rule-Based Geometric Detection

Rule-based detection defines each pattern using explicit mathematical criteria.

Typical inputs:

- Local maxima
- Local minima
- Relative peak heights
- Relative trough depths
- Trendline slopes
- Duration constraints
- Symmetry constraints
- Breakout confirmation
- Volume behavior

Example: head-and-shoulders candidate criteria may include:

```text
1. Five alternating extrema exist in the sequence.
2. The center peak is higher than the left and right shoulder peaks.
3. The shoulder peaks are within a tolerance band of each other.
4. The troughs define a neckline.
5. The neckline slope is within an allowed range.
6. Optional: price breaks below the neckline after the right shoulder.
```

Strengths:

- Highly interpretable.
- Easy to show evidence to a human reviewer.
- Good starting point for a prototype.
- Does not require large labeled datasets.

Weaknesses:

- Can be brittle.
- Requires hand-tuned thresholds.
- May reject visually valid but imperfect patterns.
- May generate many false positives if rules are loose.

Best initial use:

```text
Use as the first baseline for named geometric patterns.
```

---

### 5.2 Smoothing and Extrema Extraction

Raw prices are noisy. Many chart patterns are easier to identify after reducing small fluctuations.

Possible smoothing methods:

- Simple moving average
- Exponential moving average
- Kernel regression
- Local polynomial regression
- Spline smoothing
- Wavelet denoising
- Piecewise linear approximation

After smoothing, extract meaningful extrema:

```text
smoothed_price_series -> local maxima/minima -> extrema sequence -> pattern rules
```

Key parameter:

```text
smoothing strength
```

Tradeoff:

| Too little smoothing | Too much smoothing |
|---|---|
| Captures noise as false extrema | Removes meaningful pattern structure |

Strengths:

- Useful for all geometric chart patterns.
- Helps reduce false positives caused by noise.
- Provides a compact representation of chart shape.

Weaknesses:

- Results depend heavily on smoothing settings.
- Different timeframes may need different smoothing parameters.
- Smoothing can introduce lag.

Best initial use:

```text
Use before geometric rule detection and template matching.
```

---

### 5.3 Template Matching and Similarity Scoring

Template matching compares a candidate chart segment against one or more known reference patterns.

Basic process:

```text
candidate_window -> normalize -> compare to pattern templates -> score similarity
```

Possible distance or similarity methods:

| Method | Use Case |
|---|---|
| Euclidean distance | Same-length normalized windows |
| Correlation distance | Shape similarity independent of scale |
| Dynamic Time Warping | Shape similarity with time stretching/compression |
| Feature-vector distance | Compare slopes, extrema, ratios, and durations |
| Fréchet/Hausdorff-style distances | Curve-shape similarity |

Strengths:

- More flexible than rigid rules.
- Can rank candidates by similarity.
- Easy to add confirmed human-reviewed examples as templates.
- Useful for visual “looks like this” comparisons.

Weaknesses:

- Requires representative templates.
- Normalization choices strongly affect results.
- Poor templates can bias detection.

Best initial use:

```text
Use after geometric rules to rank and soften candidate detection.
```

---

### 5.4 Feature-Based Supervised Classification

This approach converts chart windows into structured feature vectors and trains a classifier.

Possible feature groups:

| Feature Group | Examples |
|---|---|
| Price shape | Slopes, curvature, returns, range expansion |
| Extrema structure | Number of peaks/troughs, peak ratios, trough ratios, spacing |
| Volatility | ATR, rolling standard deviation, realized volatility |
| Volume | Volume trend, breakout volume, price-volume divergence |
| Trend context | Moving-average slope, prior trend strength, distance from moving average |
| Breakout context | Resistance distance, support distance, neckline break, retest behavior |

Possible models:

- Logistic regression
- Decision tree
- Random forest
- Gradient boosting
- Support vector machine
- Calibrated probabilistic classifier

Strengths:

- Can learn reviewer preferences.
- Can combine many weak signals.
- Often more interpretable than deep learning.
- Works with moderate labeled datasets.

Weaknesses:

- Requires labeled examples.
- Feature engineering is important.
- Labels may be subjective or inconsistent.

Best initial use:

```text
Use after accumulating human-reviewed labels.
```

---

### 5.5 Candlestick-Specific Pattern Detection

Candlestick patterns are short-window OHLC formations.

Typical input:

```text
1 to 10 bars of OHLC data
```

Possible features:

- Candle body size
- Upper wick length
- Lower wick length
- Close position within candle range
- Gap direction
- Relative size compared to recent candles
- Prior trend context
- Confirmation candle behavior

Strengths:

- Well-suited to short windows.
- Can be rule-based or classifier-based.
- Easy to isolate from broader geometric patterns.

Weaknesses:

- Many candlestick patterns are context-dependent.
- May produce many false positives without trend filters.
- Short patterns may be less robust than larger structures.

Best initial use:

```text
Treat as a separate detection module from larger geometric patterns.
```

---

### 5.6 Image-Based Computer Vision

This approach renders chart windows as images and applies computer vision models.

Possible model types:

- Convolutional neural networks
- Vision transformers
- Image embedding models
- Similarity search over chart images

Strengths:

- Similar to how humans visually inspect charts.
- Can learn complex visual structures.
- Can detect visual patterns not easily encoded by rules.

Weaknesses:

- Requires many labeled images.
- Less interpretable.
- Sensitive to rendering choices such as scaling, colors, axes, and indicators.
- May learn chart-format artifacts instead of market structure.

Best initial use:

```text
Consider later if a large labeled dataset is available.
```

---

### 5.7 Sequence Models

Sequence models use raw or transformed time-series data directly.

Possible model types:

- 1D convolutional neural networks
- LSTM networks
- GRU networks
- Temporal convolutional networks
- Transformer-based time-series models

Possible inputs:

- Returns
- Log returns
- Normalized OHLC
- OHLCV feature sequences
- Multi-timeframe sequences

Strengths:

- Avoids chart rendering artifacts.
- Can model temporal structure directly.
- Can learn complex pattern definitions from data.

Weaknesses:

- Requires substantial labeled data.
- Less interpretable than rule-based systems.
- Needs careful validation to avoid overfitting.

Best initial use:

```text
Use later, after collecting enough reviewer-confirmed examples.
```

---

### 5.8 Unsupervised Motif Discovery and Clustering

This approach searches for recurring shapes without predefined labels.

Basic process:

```text
chart_windows -> normalize -> reduce dimensionality -> cluster -> human labels clusters
```

Possible representations:

- Piecewise aggregate approximation
- Symbolic aggregate approximation
- Fourier coefficients
- Wavelet coefficients
- Autoencoder embeddings
- Shape descriptors

Strengths:

- Useful for discovering patterns not predefined.
- Can help build an initial pattern taxonomy.
- Can identify repeated market structures.

Weaknesses:

- Clusters may not correspond to meaningful chart patterns.
- Requires human interpretation.
- Results depend heavily on representation and distance metric.

Best initial use:

```text
Use as an exploratory research tool, not the first production detector.
```

---

### 5.9 Shapelet-Based Detection

Shapelets are short subsequences that are highly discriminative of a class.

Example concept:

```text
A small price movement shape may strongly indicate a larger pattern category.
```

Strengths:

- More interpretable than many black-box models.
- Can highlight the specific subsequence that triggered detection.
- Useful for pattern fragments.

Weaknesses:

- More complex to design and tune.
- May still require labeled data.
- Can be computationally expensive depending on search strategy.

Best initial use:

```text
Consider after collecting labeled examples and wanting more interpretable ML.
```

## 6. Data Requirements

### 6.1 Minimum Market Data

Recommended minimum input:

```text
Adjusted OHLCV bars
```

Fields:

| Field | Purpose |
|---|---|
| Open | Candlestick structure and gaps |
| High | Extrema, resistance, wick structure |
| Low | Extrema, support, wick structure |
| Close | Returns, trend, breakout validation |
| Volume | Breakout and confirmation signal |
| Adjusted prices | Split/dividend consistency |

### 6.2 Historical Coverage

The dataset should include:

- Multiple tickers or assets.
- Multiple market regimes.
- Bull markets.
- Bear markets.
- Sideways markets.
- High-volatility periods.
- Low-volatility periods.
- Different liquidity profiles.
- Sufficient examples of both patterns and non-patterns.

### 6.3 Label Data

For a human-review workflow, labels should include more than just final pattern names.

Recommended label schema:

| Label Field | Description |
|---|---|
| candidate_id | Unique ID for candidate segment |
| ticker | Asset identifier |
| timeframe | Bar interval |
| start_time | Segment start |
| end_time | Segment end |
| proposed_pattern | Pattern suggested by system |
| reviewer_decision | Confirm, deny, uncertain, relabel |
| reviewer_label | Final human label if different |
| confidence_override | Optional reviewer confidence |
| notes | Reviewer comments |
| post_pattern_outcome | Optional future outcome tracking |

### 6.4 Negative and Ambiguous Examples

Important training categories:

```text
confirmed_pattern
rejected_candidate
ambiguous_candidate
similar_but_not_pattern
unknown
```

Do not discard rejected candidates. They are useful negative examples.

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
| Smoothing | Reduces small fluctuations |
| Multi-scale windowing | Finds patterns across different durations |

Core invariance questions:

```text
Should the detector ignore absolute price level?
Should the detector ignore volatility level?
Should the detector tolerate time stretching?
Should the detector tolerate imperfect symmetry?
Should the detector require volume confirmation?
Should the detector require a breakout?
```

## 8. Human-Review Workflow

Recommended candidate lifecycle:

```text
1. Generate chart windows.
2. Normalize and smooth data.
3. Extract extrema and features.
4. Apply rule-based detectors.
5. Apply template similarity scoring.
6. Rank candidate patterns.
7. Show candidate to human reviewer.
8. Reviewer confirms, denies, relabels, or marks uncertain.
9. Store reviewer feedback.
10. Periodically recalibrate thresholds or train models.
```

### 8.1 Evidence to Show Reviewer

For each candidate, show:

- Proposed pattern.
- Confidence score.
- Similarity score.
- Pattern-specific geometric evidence.
- Key extrema.
- Trendlines.
- Support/resistance lines.
- Breakout level, if applicable.
- Volume behavior, if applicable.
- Nearest confirmed examples.
- Reason for uncertainty.

### 8.2 Human Feedback Types

Possible review decisions:

| Decision | Meaning |
|---|---|
| Confirm | Pattern label is correct |
| Deny | No valid pattern |
| Relabel | Pattern exists but label is wrong |
| Uncertain | Reviewer cannot confidently classify |
| Needs more context | Segment alone is insufficient |

## 9. Recommended Initial Strategy

The recommended first approach is a hybrid interpretable detector.

### Phase 1: Rule-Based Geometry with Smoothing

Use:

```text
OHLCV -> adjusted data -> smoothing -> extrema detection -> geometric rules
```

Initial target patterns:

| Pattern | Mathematical Basis |
|---|---|
| Double top | Two peaks at similar levels with intervening trough |
| Double bottom | Two troughs at similar levels with intervening peak |
| Head and shoulders | Five extrema with center peak dominant |
| Inverse head and shoulders | Five extrema with center trough dominant |
| Triangle | Converging support and resistance lines |
| Rectangle | Bounded range with low directional slope |
| Channel | Approximately parallel trendlines |
| Breakout | Exit from prior range with optional volume expansion |
| Flag | Impulse move followed by compact counter-trend consolidation |
| Pennant | Impulse move followed by converging consolidation |
| Cup and handle | Rounded base followed by smaller pullback |

Primary benefits:

- Good explainability.
- Low data-label requirement.
- Easy for human reviewers to validate.
- Generates useful labeled training data.

---

### Phase 2: Template Similarity

Add confirmed examples as templates.

Process:

```text
confirmed_patterns -> normalized templates -> similarity comparison -> candidate ranking
```

Benefits:

- Reduces brittleness.
- Helps detect imperfect but visually valid patterns.
- Supports “nearest example” explanations.

---

### Phase 3: Learn from Reviewer Feedback

Use reviewed candidates to train a model.

Possible progression:

```text
reviewed labels -> engineered features -> supervised classifier -> calibrated confidence scores
```

Primary model goals:

- Improve ranking.
- Reduce false positives.
- Learn reviewer-specific tolerance.
- Identify ambiguous cases.
- Suggest alternate labels.

## 10. Approach Comparison

| Approach | Label Requirement | Interpretability | Flexibility | Best Stage |
|---|---:|---:|---:|---|
| Rule-based geometry | Low | High | Low-Medium | Prototype |
| Smoothing + extrema | Low | High | Medium | Prototype |
| Template matching | Medium | Medium-High | Medium-High | Early validation |
| Feature classifier | Medium | Medium | High | After reviewer labels |
| Candlestick rules | Low | High | Medium | Separate short-pattern module |
| Image model | High | Low | High | Later |
| Sequence model | High | Low-Medium | High | Later |
| Clustering/motifs | Low-Medium | Medium | Exploratory | Research |
| Shapelets | Medium-High | Medium-High | Medium | Later/interpretable ML |

## 11. Suggested System Architecture at Conceptual Level

```text
Data Layer
  -> adjusted OHLCV bars
  -> corporate-action-adjusted history
  -> timeframe consistency

Preprocessing Layer
  -> normalization
  -> smoothing
  -> volatility scaling
  -> window generation

Feature and Shape Layer
  -> extrema extraction
  -> trendline estimation
  -> support/resistance estimates
  -> volume features
  -> pattern-specific features

Candidate Detection Layer
  -> rule-based detectors
  -> template similarity
  -> optional classifier

Human Review Layer
  -> proposed label
  -> visual evidence
  -> confidence
  -> reviewer decision
  -> notes

Feedback Layer
  -> confirmed labels
  -> rejected candidates
  -> ambiguous examples
  -> threshold calibration
  -> future model training
```

## 12. Evaluation Metrics

Because the tool is for human review, evaluate it differently from a pure trading model.

### 12.1 Pattern Detection Metrics

| Metric | Meaning |
|---|---|
| Precision | Of flagged candidates, how many reviewers confirm? |
| Recall | Of true patterns, how many did the tool flag? |
| False positive rate | How often does it waste reviewer time? |
| Candidate density | How many candidates per ticker per period? |
| Reviewer agreement | How consistently humans classify patterns? |
| Label confusion | Which patterns are commonly confused? |
| Time-to-review | How quickly can a human validate a candidate? |

### 12.2 Later Outcome Metrics

Optional later metrics:

| Metric | Meaning |
|---|---|
| Forward return | Price movement after pattern |
| Max favorable excursion | Best move after signal |
| Max adverse excursion | Worst move after signal |
| Breakout follow-through | Whether breakout sustains |
| Failure rate | Pattern fails after confirmation |
| Regime sensitivity | Performance by market regime |

## 13. Key Risks

| Risk | Mitigation |
|---|---|
| Overfitting to visual examples | Use multiple assets and regimes |
| Subjective labels | Allow uncertain and relabel states |
| Too many false positives | Rank by confidence and candidate density |
| Brittle thresholds | Use tolerance bands and template matching |
| Data distortions | Use adjusted OHLCV and corporate-action handling |
| Timeframe mismatch | Build separate models or thresholds by timeframe |
| Lookahead bias | Ensure detection uses only data available at detection time |
| Confusing recognition with prediction | Track visual labels separately from future outcomes |

## 14. Recommended Starting Point

Start with:

```text
1. Adjusted OHLCV data.
2. Fixed and variable rolling windows.
3. Smoothing.
4. Extrema extraction.
5. Rule-based geometric detectors.
6. Pattern-specific confidence scores.
7. Human-review interface.
8. Storage of confirmed, rejected, relabeled, and uncertain examples.
```

Then add:

```text
9. Template similarity using confirmed examples.
10. Feature-based supervised classifier after enough labels are available.
11. Outcome analysis as a separate later layer.
```

## 15. References and Source URLs

These sources informed the original response:

1. Lo, Mamaysky, and Wang, *Foundations of Technical Analysis: Computational Algorithms, Statistical Inference, and Empirical Implementation*  
   URL: https://www.cis.upenn.edu/~mkearns/teaching/cis700/lo.pdf

2. Dynamic Time Warping for financial pattern matching, MDPI Sustainability  
   URL: https://www.mdpi.com/2071-1050/10/12/4641

3. Candlestick pattern recognition study, PMC  
   URL: https://pmc.ncbi.nlm.nih.gov/articles/PMC8345893/

4. Deep-learning stock chart pattern recognition paper  
   URL: https://arxiv.org/pdf/1808.00418

5. Time-series data mining overview  
   URL: https://mason.gmu.edu/~jgentle/papers/JSM_TimeSeries.pdf

6. Shapelet-style financial pattern research  
   URL: https://arxiv.org/html/2509.15040v1
