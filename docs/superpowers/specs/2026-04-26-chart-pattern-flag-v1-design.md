# Phase 3e §3e.6 — Chart-pattern shape estimator: flag_pattern V1 (design)

**Baseline:** `main` at commit `c027d19`; 1002 fast tests green; schema_version = 8.

**Goal:** Encode the qualitative chart-pattern dimension of operator workflow as structured, queryable, per-trade evidence by shipping a deterministic geometric `flag_pattern` classifier. The classifier runs at pipeline time on chart-scope tickers, persists its result + a frozen feature snapshot, surfaces a `flag (0.78)` tag on the watchlist, displays its result on the trade-entry form (with operator override), and paints a verification overlay on the chart image. **Production scoring/bucketing is UNTOUCHED.**

**Framing (binding, from `docs/orchestrator-context.md` 2026-04-25):** *"Chart-pattern algorithm is for ENCODING qualitative input into structured feedback-loop data, not for throughput acceleration."* Operator can chart-read at saturation rate; the algorithm's value is making the chart-pattern dimension analytically usable alongside `hypothesis_label`.

---

## 1. Background & scope

### 1.1 Locked constraints (operator-set, NOT re-litigated)

1. **One pattern only:** `flag_pattern`. Other patterns (pennant, base, cup-with-handle) are V2+ additions.
2. **Governance posture:** display + persist on trades + confidence metric. Production scoring/bucketing UNTOUCHED. Promoting any aspect to production decision logic requires V2.1 §VII.F protocol.
3. **Compute timing:** pipeline-time, on chart-scope tickers (the same set `_step_charts` already builds).
4. **Display surface:** watchlist rows + trade-entry form + chart-image overlay.
5. **Trade-entry consumption:** cached-only. Out-of-scope manual trades have no override surface in V1.
6. **Operator override at entry:** algorithm and operator values stored separately on trade row.

### 1.2 What V1 ships

1. New `swing/evaluation/patterns/flag_classifier.py` — pure-function `classify_flag(bars: DataFrame) -> FlagClassificationResult`.
2. Two new migrations — `0009_pipeline_pattern_classifications.sql` (cache table) and `0010_trade_chart_pattern.sql` (three trade columns).
3. `_step_charts` extension — call classifier on the in-hand OHLCV; INSERT classification row in the same `lease.fenced_write()` transaction as the chart_target update.
4. Watchlist tag rendering — `flag (0.78)` appended to the existing tags cell, sort-NEUTRAL.
5. Trade-entry "Chart pattern" form section — algo display + override dropdown + free-text "other" path canonicalized like `hypothesis_label`.
6. Chart overlay — `render_chart` gains an optional `pattern_overlay` kwarg painting pole/flag bands + algo-pivot annotation. Existing `pivot` hline (candidate-pivot) preserved.
7. Three-layer tests — unit (synthetic), integration (≥15 committed labeled fixtures), slow (deferred).

### 1.3 What V1 does NOT ship (deferred)

- Additional patterns beyond `flag_pattern`.
- Manual-trade fallback for out-of-chart-scope tickers.
- ML / LLM / hybrid classifiers.
- Multi-timeframe analysis (weekly + daily).
- Real-time / intraday classification.
- Sort-PARTICIPATING flag tag (algo influence on watchlist ordering).
- `_sort_watchlist` modification.
- Any change to `swing/evaluation/scoring.py`, `swing/recommendations/`, or `bucket_for`.

---

## 2. Architecture

### 2.1 File layout

```
swing/
├── evaluation/
│   └── patterns/
│       ├── __init__.py                          # NEW
│       └── flag_classifier.py                   # NEW: pure-function classifier
├── data/
│   ├── migrations/
│   │   ├── 0009_pipeline_pattern_classifications.sql   # NEW (Phase 2 carve-out)
│   │   └── 0010_trade_chart_pattern.sql                # NEW (Phase 2 carve-out)
│   ├── models.py                                # MODIFY: Trade + new dataclass (carve-out)
│   └── repos/
│       ├── pattern_classifications.py           # NEW (carve-out)
│       └── trades.py                            # MODIFY: thread 3 new columns (carve-out)
├── trades/
│   └── entry.py                                 # MODIFY: EntryRequest extension (carve-out)
├── pipeline/
│   └── runner.py                                # MODIFY: _step_charts extension
├── rendering/
│   └── charts.py                                # MODIFY: pattern_overlay kwarg + PatternOverlay
├── web/
│   ├── view_models/
│   │   ├── dashboard.py                         # MODIFY: extend _flag_tags with flag tag
│   │   ├── watchlist.py                         # MODIFY: load classifications by pipeline_run_id
│   │   ├── trades.py                            # MODIFY: TradeEntryFormVM gains pattern fields
│   │   └── open_positions_row.py                # MODIFY: thread pattern data from trade row
│   ├── templates/partials/
│   │   ├── trade_entry_form.html.j2             # MODIFY: new "Chart pattern" section
│   │   └── watchlist_row.html.j2                # MODIFY: flag tag in tags cell
│   └── routes/
│       └── trades.py                            # MODIFY: POST handler reads chart_pattern_operator
├── cli.py                                       # MODIFY: --chart-pattern-operator on `swing trade entry`
└── config.py                                    # MODIFY: cfg.web.flag_pattern_display_threshold (default 0.0)
```

Files touched (full list):

- **NEW (5):** `swing/evaluation/patterns/__init__.py`, `swing/evaluation/patterns/flag_classifier.py`, `swing/data/migrations/0009_pipeline_pattern_classifications.sql`, `swing/data/migrations/0010_trade_chart_pattern.sql`, `swing/data/repos/pattern_classifications.py`.
- **Phase 2 carve-out (3 modify):** `swing/data/models.py`, `swing/data/repos/trades.py`, `swing/trades/entry.py`.
- **Phase 3 modify (10):** `swing/pipeline/runner.py`, `swing/rendering/charts.py`, `swing/web/view_models/dashboard.py`, `swing/web/view_models/watchlist.py`, `swing/web/view_models/trades.py`, `swing/web/view_models/open_positions_row.py`, `swing/web/templates/partials/trade_entry_form.html.j2`, `swing/web/templates/partials/watchlist_row.html.j2`, `swing/web/routes/trades.py`, `swing/cli.py`, `swing/config.py` (one new field).

Total: **17 files** (5 new + 12 modify).

### 2.2 Design invariants

- **Purity at the boundary.** `classify_flag(bars)` is a pure function: DataFrame in, primitives + dataclass out. No DB, no IO, no logging side-effects. Tests inject canned DataFrames; no yfinance round-trip in fast suite.
- **OHLCV scope unchanged.** Classifier consumes the bars `_step_charts` already fetched for chart rendering. NO new fetch sites, NO expansion of OHLCV scope beyond chart-scope. Honors the CLAUDE.md gotcha: *"OHLCV fetch scope = open-trade tickers ONLY"* — actually for `_step_charts`-scope (A+ + near-by-proximity), which is a strict superset of where charts already render. No new ticker classes touched.
- **Anchor consistency (Bug 7 family).** All reads of pattern classifications bind to `pipeline_runs.evaluation_run_id`'s pipeline_run_id, never to "latest classification regardless of run." If today's pipeline run has no classification row for a ticker, the watchlist row shows NO pattern tag — no fallback to prior runs.
- **Per-ticker fenced writes.** Classification INSERT happens inside the SAME `lease.fenced_write()` block as the chart_target status update for that ticker. Mirrors the existing `_step_charts` pattern; no new lease semantics.
- **Production scoring untouched.** `swing/evaluation/scoring.py`, `bucket_for`, `_sort_watchlist`, `_TAG_PRECEDENCE` are all read-only in this phase. Any reviewer concern that this design influences A+/watch/skip bucketing is a finding requiring scope rescoping.
- **Falsifiability of algorithm output.** `pipeline_pattern_classifications.components_json` carries the frozen feature snapshot at compute time so a reviewer can say "this output is wrong because feature X computed Y." Per Brief §5 watch-item.

### 2.3 Data flow (pipeline → watchlist → trade)

```
[pipeline _step_charts loop, per ticker in chart-scope set]
    fetcher.get(ticker, lookback_days=200)
        ↓ bars in hand
    classify_flag(bars)
        ↓ FlagClassificationResult
    lease.fenced_write():
        update_chart_target_status(...)
        insert_classification(pipeline_run_id, ticker, result)
        ↓
    [pipeline_pattern_classifications row committed]

[web request: GET /watchlist or GET /]
    build_watchlist (or build_dashboard) ↓
    pipeline_eval_id = (latest pipeline_runs.evaluation_run_id)
    pipeline_run_id = (parent of that eval row)
    list_classifications_for_run(pipeline_run_id) → {ticker: classification}
    flag_tags computation gains 'flag (0.78)' entry per detected ticker
    sort uses TT/VCP/A+ precedence ONLY (flag excluded)
    ↓ rendered in tags cell

[web request: GET /trades/entry?ticker=XYZ]
    build_entry_form_vm:
      get_classification(pipeline_run_id, ticker) → maybe None
      VM.chart_pattern_algo / chart_pattern_algo_confidence / chart_pattern_algo_evaluated
    template renders "Chart pattern" section + override dropdown

[web request: POST /trades/entry]
    form payload includes chart_pattern_operator (NULL when "Accept algo" selected)
    EntryRequest.chart_pattern_operator threaded through
    record_entry stores: (algo, confidence, operator_canonicalized) on trade row
```

---

## 3. Components

### 3.1 Algorithm: `flag_classifier.py`

#### 3.1.1 Result dataclass

```python
@dataclass(frozen=True)
class FlagClassificationResult:
    detected: bool
    confidence: float                      # 0.0–1.0; 0.0 when not detected (dataclass-only; persists as NULL when pattern='none' — see §3.2)
    pattern: str                           # 'flag' if detected, 'none' otherwise
    pole_start_date: date | None           # bars[pole_start_idx].date(); None if not detected
    pole_end_date: date | None             # bars[pole_end_idx-1].date() (inclusive last pole bar)
    flag_start_date: date | None
    flag_end_date: date | None
    pole_high: float | None
    flag_low: float | None
    pivot: float | None                    # max(High) over flag bars
    components: dict[str, float]           # per-gate raw values + clearances (frozen snapshot)
    # components example keys:
    #   pole_gain, pullback_depth, tightness_ratio, volume_ratio,
    #   pole_gain_clearance, pullback_clearance, tightness_clearance, volume_clearance,
    #   pole_M, flag_N, sma10_at_flag_start, sma20_at_flag_start, sma50_at_flag_start
```

#### 3.1.2 Detection algorithm

`classify_flag(bars: DataFrame) -> FlagClassificationResult`:

1. **Precondition:** `bars` is the last 60 completed daily bars (`Open, High, Low, Close, Volume` columns). If `len(bars) < 36` (need ≥ 5-bar pole + 5-bar flag + 26 bars for SMA50 + buffer), return `detected=False, pattern='none'`.

2. **Search over (M, N):** for `N` in `[5, 21]` (flag length, flag = the LAST N bars of the frame), for `M` in `[5, 30]` (pole length, pole = the M bars immediately preceding the flag):
   - Verify all 10 gates (§3.1.3) for the (M, N) candidate.
   - Compute `confidence = min(four continuous-gate clearances)` (§3.1.4).
3. **Best fit:** Return the (M*, N*) candidate with highest confidence among those with ALL gates passing. Ties broken by lower N (shorter flag, "tighter" tagging), then lower M.
4. **No candidate passes:** Return `detected=False, pattern='none', confidence=0.0`. Components dict still populated with the BEST-attempted candidate's measurements for debugging.

#### 3.1.3 Gate definitions

Each gate is a pure function over the (pole_bars, flag_bars) split:

| # | Gate | Definition |
|---|------|------------|
| 1 | data_window | `len(bars) ≥ 36` |
| 2 | flag_length | `5 ≤ N ≤ 21` |
| 3 | pole_length | `5 ≤ M ≤ 30` |
| 4 | pole_gain | `(max(pole.High) − min(pole.Low)) / min(pole.Low) ≥ 0.30` |
| 5 | ma_structure | At `flag_bars[0]`: `SMA10 > SMA20 > SMA50`, AND each rising over the last 5 bars (i.e., `sma_today > sma_5_bars_ago` for each window) |
| 6 | pullback_depth | `(max(pole.High) − min(flag.Low)) / max(pole.High) ≤ 0.15` |
| 7 | tightness | `median((H − L) / C) over flag ≤ 0.6 × median((H − L) / C) over pole` |
| 8 | volume_contraction | `mean(flag.Volume) ≤ 0.7 × mean(pole.Volume)` |
| 9 | pivot | `pivot = max(flag.High)` (definitional, not a gate per se) |
| 10 | breakout | INFORMATIONAL — `today.Close > pivot`. Recorded in components but does NOT gate detection (a flag is a flag pre-breakout so operator can stage it) |

Detection requires gates 1–8 all pass (gate 9 is definitional; gate 10 is informational).

#### 3.1.4 Confidence formula

```python
clearance_pole_gain    = clamp((pole_gain     - 0.30) / 0.70, 0.0, 1.0)   # saturates at 100% gain
clearance_pullback     = clamp((0.15 - pullback_depth)  / 0.15, 0.0, 1.0) # 1.0 at depth=0
clearance_tightness    = clamp((0.6  - tightness_ratio) / 0.6,  0.0, 1.0)
clearance_volume       = clamp((0.7  - volume_ratio)    / 0.7,  0.0, 1.0)

confidence = min(clearance_pole_gain, clearance_pullback,
                 clearance_tightness, clearance_volume)
```

Binary gates (#5 ma_structure, #2/#3 length bounds) do not enter the formula — by construction they are 1 post-detection.

**Threshold defaults** (config; tunable from labeled-example test feedback):
- `cfg.classifier.flag_pole_gain_min = 0.30`
- `cfg.classifier.flag_pullback_depth_max = 0.15`
- `cfg.classifier.flag_tightness_ratio_max = 0.6`
- `cfg.classifier.flag_volume_ratio_max = 0.7`

V1 bias: false-positive cost > false-negative cost (operator-arbiter framing; FP erodes tag trust). If labeled tests reveal FP > FN, tighten defaults — captured as a tuning note in the spec, not as a separate config-amendment process.

### 3.2 Persistence

#### 3.2.1 Migration 0009 — pipeline_pattern_classifications

```sql
-- 0009_pipeline_pattern_classifications.sql
--
-- Pipeline-time pattern classification cache. One row per (pipeline_run_id, ticker)
-- for tickers in chart-scope. Bound to pipeline_runs.id; reads bind via
-- pipeline_runs.evaluation_run_id → pipeline_run_id (Bug 7 family discipline).

CREATE TABLE pipeline_pattern_classifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_run_id INTEGER NOT NULL REFERENCES pipeline_runs(id),
    ticker TEXT NOT NULL,
    pattern TEXT
        CHECK (pattern IS NULL OR pattern IN ('none', 'flag')),
    confidence REAL
        CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0)),
    components_json TEXT NOT NULL,          -- frozen feature snapshot (falsifiability)
    pivot REAL,
    pole_high REAL,
    flag_low REAL,
    computed_at TEXT NOT NULL,              -- ISO timestamp
    UNIQUE (pipeline_run_id, ticker)
);

CREATE INDEX idx_pattern_classifications_run ON pipeline_pattern_classifications(pipeline_run_id);

UPDATE schema_version SET version = 9;
```

#### 3.2.2 Migration 0010 — trade chart_pattern columns

```sql
-- 0010_trade_chart_pattern.sql
--
-- Three columns on trades for the chart-pattern algo's per-trade encoding.
-- Brief locked-constraint #6: algo and operator values stored separately so future
-- agreement-rate / calibration analysis can compare them. Effective-pattern-for-
-- analysis = COALESCE(chart_pattern_operator, chart_pattern_algo).

ALTER TABLE trades ADD COLUMN chart_pattern_algo TEXT
    CHECK (chart_pattern_algo IS NULL OR chart_pattern_algo IN ('none', 'flag'));
ALTER TABLE trades ADD COLUMN chart_pattern_algo_confidence REAL
    CHECK (chart_pattern_algo_confidence IS NULL
           OR (chart_pattern_algo_confidence >= 0.0
               AND chart_pattern_algo_confidence <= 1.0));
ALTER TABLE trades ADD COLUMN chart_pattern_operator TEXT;

UPDATE schema_version SET version = 10;
```

NULL semantics:
- `chart_pattern_algo='flag', confidence=0.78`: classifier detected.
- `chart_pattern_algo='none', confidence=NULL`: classifier evaluated, no detection.
- `chart_pattern_algo=NULL, confidence=NULL`: classifier did NOT run on this ticker (out-of-scope manual trade; V1 deferred).
- `chart_pattern_operator='flag'` (or any text): operator override, takes precedence in analysis.
- `chart_pattern_operator=NULL`: operator accepted algorithm; analysis falls through to algo value.

**CHECK constraint extensibility:** the `IN ('none', 'flag')` check is V1-scoped. V2 patterns extend the IN list via a future migration; existing rows preserved.

#### 3.2.3 Repo layer

**Confidence persistence rule:** the dataclass's `confidence: float` field is always populated (0.0 when not detected) for in-memory completeness. The repo layer translates: when `result.pattern == 'none'`, `confidence` column persists as **NULL** (matches the trade-row NULL semantics in §3.2.2 and the CHECK constraint in §3.2.1). When `result.pattern == 'flag'`, the float value persists as-is.

`swing/data/repos/pattern_classifications.py`:

```python
def insert_classification(conn, *, pipeline_run_id: int, ticker: str,
                          result: FlagClassificationResult,
                          computed_at: str) -> int: ...
def get_classification(conn, *, pipeline_run_id: int,
                       ticker: str) -> PipelinePatternClassification | None: ...
def list_classifications_for_run(conn, *,
                                 pipeline_run_id: int) -> Mapping[str, PipelinePatternClassification]: ...
```

`swing/data/repos/trades.py` — `insert_trade_with_event` adds the three new columns to its INSERT; existing read queries SELECT them. Trade dataclass at `swing/data/models.py` gains three trailing-default fields (mirrors `hypothesis_label` precedent at [models.py:69](../../../swing/data/models.py#L69)) preserving every existing call site.

### 3.3 Pipeline integration

`_step_charts` ([swing/pipeline/runner.py:535-628](../../../swing/pipeline/runner.py#L535-L628)) gains one block in the per-ticker loop:

```python
for ticker, pivot, stop, _source in targets:
    try:
        ohlcv = fetcher.get(ticker, lookback_days=200, as_of_date=None)
    except Exception:
        with lease.fenced_write() as conn:
            update_chart_target_status(conn, ..., chart_status="fetcher_failed")
        continue

    # NEW: classify on the in-hand OHLCV
    bars_60 = ohlcv.tail(60)
    try:
        classification = classify_flag(bars_60)
    except Exception as exc:
        # Persist a row with components_json carrying the error so the
        # falsifiability path stays intact even on classifier bugs. Trade
        # row reads see chart_pattern_algo='none' for this ticker.
        classification = FlagClassificationResult(
            detected=False, confidence=0.0, pattern='none',
            pole_start_date=None, pole_end_date=None,
            flag_start_date=None, flag_end_date=None,
            pole_high=None, flag_low=None, pivot=None,
            components={"error": repr(exc)},
        )

    # NEW: build optional chart overlay (Q11 option B — algo-derived,
    # separate from candidate-pivot hline)
    pattern_overlay = (
        PatternOverlay.from_classification(classification)
        if classification.detected else None
    )

    path = render_chart(
        ticker=ticker, ohlcv=ohlcv, pivot=pivot, stop=stop,
        output_path=staging.path / f"{ticker}.png",
        pattern_overlay=pattern_overlay,    # NEW kwarg
    )

    with lease.fenced_write() as conn:
        update_chart_target_status(conn, ..., chart_status=...)
        # NEW: same fenced transaction as chart_status update
        insert_classification(
            conn, pipeline_run_id=lease.run_id, ticker=ticker,
            result=classification,
            computed_at=datetime.now().isoformat(timespec="seconds"),
        )
```

**Performance budget:** `classify_flag` is pure pandas/numpy on a 60-bar DataFrame searching ≤ 26 × 17 = 442 (M, N) candidates. Sub-millisecond per ticker. Negligible (<1s for 15-ticker chart-scope set).

**Failure isolation:** classifier exception for one ticker does NOT fail the chart_target update or other tickers. Same per-ticker failure boundary that already exists for chart rendering.

### 3.4 Chart overlay (Q11 option B)

`render_chart` gains `pattern_overlay: PatternOverlay | None = None`. When present, mplfinance receives:

- `vlines` extended with TWO date pairs: pole_start..pole_end (faint green band, alpha~0.15), flag_start..flag_end (faint yellow band, alpha~0.15). Implemented via `fill_betweenx` on the underlying axes after `mpf.plot` returns the figure (mplfinance 0.12+ supports `returnfig=True`).
- A horizontal segment at the algo's `pivot` value, drawn ONLY across the flag region (distinct from the existing `pivot` hline which spans the full chart and represents candidate-pivot).
- Title annotation: existing `title=f"{ticker} | pivot ${pivot:.2f} stop ${stop:.2f} | last {len(df)} bars"` extended with ` | flag ({confidence:.2f})` when overlay fires.

**Existing `pivot` hline preserved** — the candidate-pivot semantics (operator-relevant for trade execution) is NOT replaced by the algo-pivot. The two pivots may differ; operator can compare visually.

`PatternOverlay` lives in `swing/rendering/charts.py` alongside `render_chart`:

```python
@dataclass(frozen=True)
class PatternOverlay:
    pattern: str                # 'flag'
    confidence: float
    pole_start_date: date
    pole_end_date: date
    flag_start_date: date
    flag_end_date: date
    pivot: float                # algo-derived pivot

    @classmethod
    def from_classification(cls, r: FlagClassificationResult) -> "PatternOverlay":
        ...
```

### 3.5 Watchlist tag rendering

`_flag_tags` at [swing/web/view_models/dashboard.py:658-673](../../../swing/web/view_models/dashboard.py#L658-L673) gains a sibling helper or extends in-place:

```python
def _flag_tags(
    candidates_by_ticker: Mapping[str, Candidate],
    classifications_by_ticker: Mapping[str, PipelinePatternClassification] | None = None,
    display_threshold: float = 0.0,
) -> Mapping[str, tuple[str, ...]]:
    tags: dict[str, tuple[str, ...]] = {}
    for ticker, c in candidates_by_ticker.items():
        row_tags = []
        # ... existing TT/VCP/A+ logic unchanged ...
        if classifications_by_ticker:
            cls = classifications_by_ticker.get(ticker)
            if cls and cls.pattern == 'flag' and cls.confidence is not None \
               and cls.confidence >= display_threshold:
                row_tags.append(f"flag ({cls.confidence:.2f})")
        if row_tags:
            tags[ticker] = tuple(row_tags)
    return tags
```

**`_sort_watchlist` and `_TAG_PRECEDENCE` remain UNTOUCHED.** The flag tag is appended to the tuple but excluded from sort key computation — `_sort_watchlist` already counts `len(tags)` and sums `_TAG_PRECEDENCE.get(t, 0)`, so:
- `len(tags)` would naturally include the flag tag (raising tag_count) — UNDESIRED.
- `_TAG_PRECEDENCE.get(t, 0)` for `"flag (0.78)"` returns 0 (unknown key, falls through) — DESIRED.

To preserve sort-NEUTRAL: change `_sort_watchlist`'s tag-count term to **count only TT/VCP/A+ tags** (not the full tuple). One-line guard:

```python
tt_vcp_aplus_count = sum(1 for t in tags if t in _TAG_PRECEDENCE)
return (
    -tt_vcp_aplus_count,           # was -len(tags)
    -_tag_precedence_score(tags),  # already 0 for unknown flag tag
    _abs_proximity(w),
    w.ticker,
)
```

Discriminating-test discipline: tests must verify a row with `('TT✓', 'flag (0.99)')` does NOT outrank a row with `('TT✓', 'VCP✓')` — i.e., flag tag does NOT bump count or precedence.

`build_watchlist` and `build_watchlist_row` at [swing/web/view_models/watchlist.py](../../../swing/web/view_models/watchlist.py) gain a query path that resolves `pipeline_run_id` from the same `pipeline_runs.evaluation_run_id` block they already use, then `list_classifications_for_run(pipeline_run_id)` and pass the result to `_flag_tags`. No anchor mismatch.

`watchlist_row.html.j2` template renders `tags` cell unchanged — the new tag is just one more string in the existing tuple iteration. No layout change.

### 3.6 Trade-entry form

`TradeEntryFormVM` at [swing/web/view_models/trades.py:21-41](../../../swing/web/view_models/trades.py#L21-L41) gains:

```python
chart_pattern_algo: str | None = None              # 'flag' | 'none' | None
chart_pattern_algo_confidence: float | None = None
chart_pattern_algo_evaluated: bool = False         # True if a classification row exists
chart_pattern_algo_computed_at: str | None = None  # for the "from pipeline run finished ..." subline
```

`build_entry_form_vm` resolves `pipeline_run_id` (same anchor logic) → `get_classification(pipeline_run_id, ticker)` → populates the four fields.

`partials/trade_entry_form.html.j2` gains the "Chart pattern" section between the sizing-hint and the rationale field (per Q8 mockup):

- If `vm.chart_pattern_algo_evaluated`: render the algo display + override dropdown (`Accept algo` / `flag` / `none` / `other(text)`).
- Else: render the dashed "Not classified" stub (no override surface; V1 cached-only).

Form POST handler in `swing/web/routes/trades.py` reads `chart_pattern_operator` and `chart_pattern_operator_other` form fields. Resolution: if `chart_pattern_operator == "other"`, use `chart_pattern_operator_other`; else use the dropdown value (or `None` for "Accept algo").

`EntryRequest` at [swing/trades/entry.py:80-94](../../../swing/trades/entry.py#L80-L94) gains:

```python
chart_pattern_operator: str | None = None
```

`record_entry` canonicalizes via the existing `canonicalize_hypothesis_label` (or extracts a shared `canonicalize_freetext_label` helper if review prefers — the canonicalization rules are identical).

### 3.7 CLI

`swing trade entry` gains `--chart-pattern-operator` (str, default None) for parity with the form. Threads to `EntryRequest.chart_pattern_operator`. **Optional sub-scope** — if scope is tight at execution time, this is the cheapest item to defer to a follow-up; the form path is the operator's primary entry surface.

### 3.8 Config

`swing/config.py` adds one Web field:

```python
class Web:
    flag_pattern_display_threshold: float = 0.0   # NEW; below = tag hidden on watchlist
```

(Algorithm thresholds at §3.1.4 are also config-tunable; they live under `cfg.classifier.*` as a new sub-namespace.)

---

## 4. Tests

Three layers per Q9. All must run in the fast suite (no network).

### 4.1 Layer 1 — Unit tests (`tests/evaluation/patterns/test_flag_classifier.py`)

Per-component pure-function tests on synthetic DataFrames. Discriminating-test discipline ([feedback_regression_test_arithmetic](../../../README.md) memory): each pair of tests differs by ONE feature value crossing the threshold.

- `test_pole_gain_gate_at_threshold`: synthetic DataFrame with pole_gain = 0.299 → reject; 0.301 → pass.
- `test_pullback_depth_gate_at_threshold`: 0.151 → reject; 0.149 → pass.
- `test_tightness_ratio_at_threshold`: ratio 0.601 → reject; 0.599 → pass.
- `test_volume_contraction_at_threshold`: ratio 0.701 → reject; 0.699 → pass.
- `test_ma_structure_requires_stack_and_rising`: 10>20>50 not stacked → reject; stacked but flat → reject; stacked + rising → pass.
- `test_data_window_too_short`: 35 bars → `detected=False`; 36 bars (boundary) → enters search.
- `test_confidence_min_aggregation`: build a DataFrame where pole_gain clearance = 0.9 and pullback clearance = 0.2; assert `confidence == 0.2`.
- `test_search_picks_best_fit`: DataFrame admitting two valid (M, N) candidates; assert algorithm returns the higher-confidence pair, ties broken by lower N then lower M.
- `test_pattern_none_emits_components_for_debugging`: failed candidate still populates components dict.

### 4.2 Layer 2 — Integration tests (`tests/evaluation/patterns/test_flag_classifier_integration.py`)

Operator-curated labeled fixtures committed to repo (V1 floor: ≥15 examples = 8 flags + 7 non-flags spanning the rejection cases enumerated in Q2: wide-and-loose, deep base/cup, sideways drift with no pole, late-stage failed breakout, stage-4 with bounce, multi-month flat base, ambiguous edge case).

Fixture format:
```
tests/evaluation/patterns/fixtures/<TICKER>_<YYYY-MM-DD>_<label>.csv   ← 60 daily bars
tests/evaluation/patterns/fixtures/<TICKER>_<YYYY-MM-DD>_<label>.json  ← {label, notes, expected_confidence_min (for flags)}
```

Test:
```python
@pytest.mark.parametrize("fixture", _list_fixtures())
def test_classifier_against_labeled_fixture(fixture):
    bars = load_csv(fixture.csv_path)
    metadata = json.loads(fixture.json_path.read_text())
    result = classify_flag(bars)
    if metadata["label"] == "flag":
        assert result.detected and result.pattern == "flag"
        if "expected_confidence_min" in metadata:
            assert result.confidence >= metadata["expected_confidence_min"]
    else:
        assert not result.detected and result.pattern == "none"
```

**FP-biased tuning:** if integration tests show false-positives outweigh false-negatives, tighten defaults (raise pole_gain, lower pullback, lower tightness ratio). Tuning history captured in spec or per-phase notes.

### 4.3 Layer 3 — Slow tests (`tests/evaluation/patterns/test_flag_classifier_live.py`, `@pytest.mark.slow`)

Deferred to backlog. Operator can periodically run against live yfinance refresh to detect upstream-data drift on fixture tickers.

### 4.4 Sort-neutrality regression (`tests/web/view_models/test_dashboard_sort.py` extension)

Must include:
- A row with tags `('TT✓', 'flag (0.99)')` does NOT outrank a row with tags `('TT✓', 'VCP✓')` — confirms flag is excluded from `tag_count`.
- Two rows tagged `('A+',)` and `('A+', 'flag (0.99)')` sort by proximity, not by flag presence — confirms flag does NOT bump precedence.
- Compounding-confound discipline (per the 2026-04-26 memory extension): each test temporarily zeroes out the keyed-on element and re-asserts to confirm the test is not vacuous.

### 4.5 Persistence + integration tests

- `tests/data/test_pattern_classifications_repo.py` — insert + get + list_for_run; UNIQUE constraint enforcement; CHECK constraint rejection (pattern='other' rejected pre-V2).
- `tests/data/test_trade_chart_pattern_columns.py` — Trade insert/read with the three new columns; backward-compat with NULL trio.
- `tests/pipeline/test_step_charts_classification.py` — `_step_charts` writes a classification row per chart-scope ticker; classifier exception → row with components_json error; no row missing for a ticker with successful chart fetch.
- `tests/web/view_models/test_watchlist_classifications_anchor.py` — watchlist binds to `pipeline_runs.evaluation_run_id`'s pipeline_run_id; mid-pipeline standalone eval does NOT leak classifications from a prior pipeline run (Bug 7 family).
- `tests/web/routes/test_trade_entry_chart_pattern.py` — form renders the algo display when classification exists; renders "Not classified" stub when absent; POST with override stores `chart_pattern_operator` canonicalized; POST with "Accept algo" stores NULL.
- `tests/rendering/test_chart_overlay.py` — `render_chart` with `pattern_overlay=None` produces same output as before (regression). With overlay: figure includes the pole/flag bands and algo-pivot annotation; existing `pivot` hline preserved.

---

## 5. Phase 2 carve-outs

Five `swing/data/` items + one `swing/trades/` item:

| # | File | Action | Justification |
|---|---|---|---|
| 1 | `swing/data/migrations/0009_pipeline_pattern_classifications.sql` | NEW | Schema for the pipeline-time pattern cache. |
| 2 | `swing/data/migrations/0010_trade_chart_pattern.sql` | NEW | Three columns on `trades` for per-trade encoding. |
| 3 | `swing/data/models.py` | MODIFY | `Trade` gets 3 trailing-default fields (mirrors `hypothesis_label` precedent at [models.py:69](../../../swing/data/models.py#L69)). New `PipelinePatternClassification` dataclass. |
| 4 | `swing/data/repos/pattern_classifications.py` | NEW | Data-access for the new cache table. Isolated module — does not touch trades repo. |
| 5 | `swing/data/repos/trades.py` | MODIFY | `insert_trade_with_event` and read paths thread the 3 new Trade columns. |
| 6 | `swing/trades/entry.py` | MODIFY | `EntryRequest` gains `chart_pattern_operator` field; `record_entry` canonicalizes via `canonicalize_hypothesis_label` (or shared helper). |

All other modifications are within Phase 3 territory or new modules; no further carve-outs needed.

---

## 6. Adversarial-review watch items (for the wrapper)

Per Brief §5; surface to the Codex critic during `copowers:brainstorming`'s adversarial round:

- **Locked-constraint violations.** Any spec text that suggests V2 patterns ship in V1; any spec text that implies algo output influences `bucket_for`, `_sort_watchlist`, or any production decision; any expansion of OHLCV scope beyond chart-scope.
- **Falsifiability of algorithm output.** Confirm `components_json` carries enough of the per-gate measurements that a reviewer can identify why a given output was wrong.
- **Mixed-anchor risk.** Every read path that touches `pipeline_pattern_classifications` should bind to `pipeline_runs.evaluation_run_id` → `pipeline_run_id`. No "latest classification" by `computed_at` ordering.
- **Schema integrity.** Migration sequence (0009 then 0010, both `UPDATE schema_version`); CHECK constraints sound; UNIQUE(pipeline_run_id, ticker) enforced.
- **Sort neutrality.** `_sort_watchlist` change must EXCLUDE flag tag from `tag_count`; `_TAG_PRECEDENCE` not extended; tests prove neutrality on tagged-vs-tagged rows AND temporarily-disabled-element regression.
- **CLAUDE.md gotchas.** Base-layout shared VM (no new VM field needs adding to the shared base); HTMX OOB-swap partial drift (form section uses shared `{% include %}` — flag panel reusable from row reload); yfinance API regression patterns (none introduced — no new yfinance call sites).
- **OHLCV scope correctness.** Classifier consumes `_step_charts` in-hand bars only; no new fetch sites; `OhlcvCache` semantics not affected.
- **Discriminating tests.** Each test pair differs by one feature crossing a threshold; compounding-confound regression (per 2026-04-26 memory extension) on the sort-neutrality assertions.
- **Pre-registration / governance.** No sneaking in scoring influence; `bucket_for` untouched; `swing/evaluation/scoring.py` confirmed unchanged.
- **Test strategy adequacy.** ≥15 fixtures committed; FP-biased tuning rationale; layer separation clear; slow tests deferred not omitted.
- **Phase 2 carve-out enumeration.** Every `swing/data/` and `swing/trades/` file listed with action + justification (§5).

---

## 7. Migration / rollout

1. **Migrations apply on first `swing db-migrate` post-deploy.** No backfill required — all new columns nullable, all new table empty initially. Existing trades have NULL trio for chart_pattern columns; queries treat as "not evaluated."
2. **First pipeline run after deploy** populates `pipeline_pattern_classifications` for that run's chart-scope set.
3. **Watchlist tag visibility** appears on the next dashboard render after a pipeline run with classifications. Default threshold 0.0 = all detected flags visible.
4. **Trade entry form** displays algo data for in-scope tickers immediately; out-of-scope tickers display the "Not classified" stub.
5. **Operator validation gate.** Before merging V1, run the labeled-example test set; review FP/FN distribution; tighten defaults if FP > FN. Document the chosen defaults in `docs/orchestrator-context.md` recent-decisions.

---

## 8. Open follow-ups (V2 candidates, NOT in V1 scope)

- Additional patterns beyond `flag` (pennant, cup-with-handle, flat-base, tight channel). Each adds to `pattern` IN-list via a new migration.
- Manual-trade fallback for out-of-chart-scope tickers (synchronous classifier fetch on form load).
- Sort-PARTICIPATING flag tag (operator-decision; affects production UX-priority).
- Calibration study: agreement-rate analysis between `chart_pattern_algo` and `chart_pattern_operator` once 20+ overrides accumulate.
- Multi-timeframe (weekly + daily) classification.
- Slow-test live-fetch suite for upstream-data drift detection.
- Tuning-history versioning: record which `cfg.classifier.*` values were active at each pipeline run (currently the components_json captures the per-row clearances but not the threshold values themselves).
- `swing/web/watchlist_ranking.py` module extraction (per 2026-04-26 deferred item) — natural place to land flag-tag-aware sort exclusion logic if extracted.

---

## 9. Done criteria

- [ ] Migrations 0009 + 0010 apply cleanly on a v8 DB.
- [ ] `classify_flag` unit tests pass on synthetic DataFrames.
- [ ] Integration tests pass on ≥15 labeled fixtures with FP ≤ FN (or tighter defaults applied).
- [ ] `_step_charts` writes a classification row for every successfully-fetched chart-scope ticker.
- [ ] Watchlist renders `flag (0.78)` tag for detected rows; sort order unchanged from pre-V1 baseline (regression test).
- [ ] Trade-entry form shows algo display when classification exists; override stores correctly; out-of-scope shows stub.
- [ ] Chart image includes pole/flag overlay + algo-pivot annotation when classification fires; existing `pivot` hline preserved.
- [ ] Adversarial Codex review reaches `NO_NEW_CRITICAL_MAJOR`.
- [ ] Operator approves the spec via the brainstorming skill's review gate.

---

## 10. References

- Brief: `docs/phase3e-chart-pattern-brainstorm-brief.md`
- Reference image: `reference/images/flag_pattern.png`
- Qullamaggie criteria source: MCP `get_setup_criteria('flag_pattern')` (capability doc at `docs/qullamaggie-mcp-capabilities.md`)
- Methodology: `reference/methodology/minervini-trend-template.md`
- Phase 2 isolation rule + `hypothesis_label` precedent: `CLAUDE.md`, `swing/data/migrations/0007_trade_hypothesis_label.sql`, `swing/data/models.py:69`
- Bug 7 family / mixed-anchor lessons: `docs/orchestrator-context.md` recent-decisions section
- Sort architecture: [swing/web/view_models/dashboard.py:610-673](../../../swing/web/view_models/dashboard.py#L610-L673)
- OHLCV cache + breaker: [swing/web/ohlcv_cache.py](../../../swing/web/ohlcv_cache.py)
- Existing chart renderer: [swing/rendering/charts.py](../../../swing/rendering/charts.py)
- Brief framing source: `docs/orchestrator-context.md` 2026-04-25 entry "Chart-pattern algorithm is for encoding, not throughput"
