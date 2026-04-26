# Chart-Pattern Flag-V1 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Encode the qualitative chart-pattern dimension of operator workflow as structured per-trade evidence by shipping a deterministic geometric `flag_pattern` classifier that runs at pipeline time, surfaces a `flag (0.78)` watchlist tag, displays its result on the trade-entry form (with operator override), paints a chart overlay, and persists algo+operator values + audit anchor on the trade row. Production scoring/bucketing untouched.

**Architecture:** Pure-function classifier in `swing/evaluation/patterns/flag_classifier.py` consumes the OHLCV bars `_step_charts` already fetches, returns a `FlagClassificationResult`, persists to a new `pipeline_pattern_classifications` cache table inside the same `lease.fenced_write()` block as the chart_target update, and is read at watchlist + trade-entry-form render time (bound to `pipeline_runs.evaluation_run_id`'s `pipeline_run_id` — Bug-7-family anchor discipline). Operator override on the trade-entry form/CLI captures a free-text label canonicalized like `hypothesis_label`. Chart overlay paints pole/flag bands + algo-pivot via `mpf.plot(..., returnfig=True)` + `fill_betweenx`. Sort-neutrality is structurally guaranteed: `_pattern_tags` is a sibling helper to `_flag_tags`, never enters the `tags` tuple consumed by `_sort_watchlist`.

**Tech Stack:** Python 3.11+ (3.14 on dev box), pandas/numpy, SQLite (migrations 0009 + 0010), FastAPI + HTMX + Jinja2, mplfinance, click CLI.

**Spec:** `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md` (passed 5 adversarial Codex rounds). Spec is settled — this plan executes it, not redesigns it.

**Brief:** `docs/phase3e-chart-pattern-writing-plans-brief.md`.

**Baseline:** `main` at the head commit when this plan executes; `python -m pytest -m "not slow" -q` green; schema_version = 8.

**Phase 2 carve-out scope (per CLAUDE.md):** This plan touches `swing/data/` and `swing/trades/` in Phase 2 below. The carve-out enumeration is in §"Phase 2 carve-outs" at the bottom of this plan. No carve-out is implicit; every modified file in those trees is justified there.

**Operator-labeled fixtures:** Spec §4.2 makes the operator the SOLE labeler. Phase 7 fixture-LABELING tasks are operator-only; the implementer cannot fabricate labels. The implementer's Phase 7 work is the test runner + fixture-loading helper; the labeled fixtures themselves are committed by the operator (potentially across multiple sessions).

**No execution in this plan-drafting dispatch.** This file is the deliverable; per-task implementation is a future, separate dispatch.

---

## Conventions for every task

- **TDD discipline (rigid):** failing test → run to see RED → minimal implementation → run to see GREEN → commit. One red-green cycle per logical change.
- **Commits:** Conventional Commits. NO Claude co-author footer. NO `--no-verify`. NO amending — every fix is a new commit.
- **Phase-end checkpoint:** `python -m pytest -m "not slow" -q` MUST be green before declaring the phase complete. Plan must NOT introduce new ruff violations beyond the CLAUDE.md-recorded baseline; run `ruff check swing/` after each phase and fix any phase-introduced issues before commit.
- **Spec cross-references:** every task header notes the spec section(s) it implements (e.g., "implements spec §3.1.4").
- **Discriminating-test discipline:** every test must produce a different outcome under post-fix code than under pre-fix code (per `feedback_regression_test_arithmetic` memory). Tests at thresholds use ±epsilon pairs.
- **Compounding-confound discipline (per 2026-04-26 lesson):** for any test asserting a primary-key behavior, the plan also includes a "delete the keyed-on element and confirm the test now fails differently" check.

---

# Phase 1 — Algorithm core (pure-function classifier)

**Pre-conditions:** baseline fast suite green; no DB or web surface touched yet.
**Scope:** Pure-function `classify_flag(bars: DataFrame) -> FlagClassificationResult`. Zero DB / web / IO. Synthetic-DataFrame unit tests at every gate threshold.
**Phase-end checkpoint:** all unit tests in `tests/evaluation/patterns/test_flag_classifier.py` green; `python -m pytest -m "not slow" -q` green; `ruff check swing/evaluation/patterns/` clean.
**Spec sections:** §1.2 deliverable 1; §3.1 (algorithm); §4.1 (Layer 1 unit tests).

### Task 1.1 — Package skeleton

**Files:**
- Create: `swing/evaluation/patterns/__init__.py`
- Create: `swing/evaluation/patterns/flag_classifier.py` (skeleton)
- Create: `tests/evaluation/patterns/__init__.py`
- Create: `tests/evaluation/patterns/test_flag_classifier.py` (skeleton)

- [ ] **Step 1: Write failing import test**

```python
# tests/evaluation/patterns/test_flag_classifier.py
def test_module_imports():
    from swing.evaluation.patterns.flag_classifier import (
        FlagClassificationResult, classify_flag,
    )
    assert callable(classify_flag)
    assert FlagClassificationResult is not None
```

- [ ] **Step 2: Run test to see fail**

Run: `python -m pytest tests/evaluation/patterns/test_flag_classifier.py::test_module_imports -v`
Expected: FAIL with `ModuleNotFoundError: No module named 'swing.evaluation.patterns'`.

- [ ] **Step 3: Create minimal module + dataclass**

```python
# swing/evaluation/patterns/__init__.py
"""Pattern classifiers (chart-pattern flag-v1)."""
```

```python
# swing/evaluation/patterns/flag_classifier.py
"""Deterministic geometric flag-pattern classifier (V1).

Pure-function: DataFrame in, FlagClassificationResult out. No DB, no IO,
no logging side-effects. Spec: docs/superpowers/specs/2026-04-26-chart-
pattern-flag-v1-design.md §3.1.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

import pandas as pd


@dataclass(frozen=True)
class FlagClassificationResult:
    detected: bool
    confidence: float
    pattern: str | None
    pole_start_date: date | None
    pole_end_date: date | None
    flag_start_date: date | None
    flag_end_date: date | None
    pole_high: float | None
    flag_low: float | None
    pivot: float | None
    components: dict[str, float] = field(default_factory=dict)


def classify_flag(bars: pd.DataFrame) -> FlagClassificationResult:
    """Stub — implementation in subsequent tasks."""
    raise NotImplementedError
```

- [ ] **Step 4: Run test to see pass**

Run: `python -m pytest tests/evaluation/patterns/test_flag_classifier.py::test_module_imports -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/evaluation/patterns/__init__.py swing/evaluation/patterns/flag_classifier.py tests/evaluation/patterns/__init__.py tests/evaluation/patterns/test_flag_classifier.py
git commit -m "feat(patterns): scaffold flag_classifier module + dataclass"
```

### Task 1.2 — `data_window` gate (gate 1)

Implements spec §3.1.3 gate 1.

**Files:**
- Modify: `swing/evaluation/patterns/flag_classifier.py`
- Modify: `tests/evaluation/patterns/test_flag_classifier.py`

- [ ] **Step 1: Write failing test pair (35 vs 36 bars)**

```python
import pandas as pd
import numpy as np
from swing.evaluation.patterns.flag_classifier import classify_flag


def _flat_bars(n: int, start_close: float = 100.0) -> pd.DataFrame:
    """Build n bars with constant OHLCV — used as a no-detect baseline."""
    idx = pd.date_range("2026-01-01", periods=n, freq="B")
    return pd.DataFrame(
        {"Open": start_close, "High": start_close, "Low": start_close,
         "Close": start_close, "Volume": 1_000_000.0}, index=idx,
    )


def test_data_window_gate_below_threshold_returns_none():
    res = classify_flag(_flat_bars(35))
    assert res.detected is False
    assert res.pattern == "none"


def test_data_window_gate_at_threshold_enters_search():
    # 36 bars — minimum. Flat bars still fail later gates, but classify_flag
    # MUST run the search instead of short-circuiting.
    res = classify_flag(_flat_bars(36))
    assert res.detected is False
    # components_json must populate (best-attempted baseline) — proof the
    # search ran and was not short-circuited by data_window.
    assert "pole_M" in res.components
```

- [ ] **Step 2: Run to see RED**

Run: `python -m pytest tests/evaluation/patterns/test_flag_classifier.py -v`
Expected: FAIL with `NotImplementedError`.

- [ ] **Step 3: Implement data_window gate + skeleton search loop**

Replace the stub with:

```python
def classify_flag(bars: pd.DataFrame) -> FlagClassificationResult:
    if len(bars) < 36:
        return FlagClassificationResult(
            detected=False, confidence=0.0, pattern="none",
            pole_start_date=None, pole_end_date=None,
            flag_start_date=None, flag_end_date=None,
            pole_high=None, flag_low=None, pivot=None,
            components={},
        )
    # Search loop — populates baseline components even when no candidate
    # passes (best-attempted at (M=5, N=5)).
    M_baseline, N_baseline = 5, 5
    components = {"pole_M": float(M_baseline), "flag_N": float(N_baseline)}
    return FlagClassificationResult(
        detected=False, confidence=0.0, pattern="none",
        pole_start_date=None, pole_end_date=None,
        flag_start_date=None, flag_end_date=None,
        pole_high=None, flag_low=None, pivot=None,
        components=components,
    )
```

- [ ] **Step 4: Run to see GREEN**

Run: `python -m pytest tests/evaluation/patterns/test_flag_classifier.py -v`
Expected: PASS for both `test_data_window_gate_*` tests.

- [ ] **Step 5: Commit**

```bash
git add swing/evaluation/patterns/flag_classifier.py tests/evaluation/patterns/test_flag_classifier.py
git commit -m "feat(patterns): flag_classifier data_window gate (35 vs 36 bars)"
```

### Task 1.3 — Synthetic flag fixture builder + first detection

Implements the substrate for gates 2–9 tests. A reusable helper that builds an OHLCV DataFrame with a configurable pole + flag, against which subsequent threshold tests vary one feature.

**Files:**
- Create: `tests/evaluation/patterns/_synthetic.py`
- Modify: `tests/evaluation/patterns/test_flag_classifier.py`

- [ ] **Step 1: Write helper + first end-to-end detection test**

```python
# tests/evaluation/patterns/_synthetic.py
"""Synthetic OHLCV builders for pure-function classifier tests.

Discriminating-test discipline: each test varies ONE feature at the
gate threshold. Use these helpers as the baseline for those variations.
"""
from __future__ import annotations
import numpy as np
import pandas as pd


def make_flag_bars(
    *,
    pre_run_bars: int = 30,           # bars BEFORE the pole (uptrend setup
                                      # so SMA10/20/50 stack-and-rise at
                                      # flag start)
    pole_bars: int = 10,
    flag_bars: int = 8,
    pole_gain_pct: float = 0.40,      # pole_gain >= 0.30 default — passes gate 4
    pullback_pct: float = 0.10,       # pullback_depth — gate 6 default 0.15
    pole_atr_pct: float = 0.05,       # avg pole bar range / close
    flag_tightness_factor: float = 0.4,  # flag range / pole range — gate 7 ≤ 0.6
    flag_volume_factor: float = 0.5,  # flag avg vol / pole avg vol — gate 8 ≤ 0.7
    floor_holds: bool = True,         # gate 9
    pole_volume: float = 2_000_000.0,
    start_close: float = 100.0,
) -> pd.DataFrame:
    """Construct a synthetic 60-bar window: pre_run | pole | flag.

    Default parameters yield a detection-passing flag against the spec's
    default thresholds. Override one parameter per test to drive a single
    gate across its threshold.
    """
    n = pre_run_bars + pole_bars + flag_bars
    idx = pd.date_range("2026-01-01", periods=n, freq="B")
    closes = np.empty(n, dtype=float)

    # Pre-run: gentle uptrend to seat the SMAs in stacked-and-rising order.
    pre_close_start = start_close * 0.85
    closes[:pre_run_bars] = np.linspace(pre_close_start, start_close, pre_run_bars)

    # Pole: linear advance to start_close * (1 + pole_gain_pct).
    pole_top = start_close * (1.0 + pole_gain_pct)
    closes[pre_run_bars:pre_run_bars + pole_bars] = np.linspace(
        start_close, pole_top, pole_bars,
    )

    # Flag: drift between pole_top and pole_top * (1 - pullback_pct), with
    # tightness driven by flag_tightness_factor. Floor holds → second-half
    # min ≥ first-half min.
    flag_low_target = pole_top * (1.0 - pullback_pct)
    flag_idx_start = pre_run_bars + pole_bars
    half = flag_bars // 2
    flag_close = np.empty(flag_bars)
    if floor_holds:
        flag_close[:half] = np.linspace(pole_top * 0.99, flag_low_target, half)
        flag_close[half:] = np.linspace(flag_low_target * 1.005, pole_top * 0.985, flag_bars - half)
    else:
        # Drifting-down floor — second-half min < first-half min by 5%.
        flag_close[:half] = np.linspace(pole_top * 0.99, flag_low_target, half)
        flag_close[half:] = np.linspace(flag_low_target * 0.99, flag_low_target * 0.94, flag_bars - half)
    closes[flag_idx_start:] = flag_close

    pole_range = pole_top * pole_atr_pct
    flag_range = pole_range * flag_tightness_factor

    high = closes.copy()
    low = closes.copy()
    high[:pre_run_bars] = closes[:pre_run_bars] * 1.005
    low[:pre_run_bars] = closes[:pre_run_bars] * 0.995
    high[pre_run_bars:pre_run_bars + pole_bars] = closes[pre_run_bars:pre_run_bars + pole_bars] + pole_range / 2
    low[pre_run_bars:pre_run_bars + pole_bars] = closes[pre_run_bars:pre_run_bars + pole_bars] - pole_range / 2
    high[flag_idx_start:] = flag_close + flag_range / 2
    low[flag_idx_start:] = flag_close - flag_range / 2

    volume = np.empty(n)
    volume[:pre_run_bars] = pole_volume * 0.7
    volume[pre_run_bars:pre_run_bars + pole_bars] = pole_volume
    volume[flag_idx_start:] = pole_volume * flag_volume_factor

    return pd.DataFrame(
        {"Open": closes, "High": high, "Low": low, "Close": closes,
         "Volume": volume}, index=idx,
    )
```

```python
# tests/evaluation/patterns/test_flag_classifier.py — append
from tests.evaluation.patterns._synthetic import make_flag_bars


def test_default_synthetic_flag_is_detected():
    bars = make_flag_bars()
    res = classify_flag(bars)
    assert res.detected is True
    assert res.pattern == "flag"
    assert 0.0 < res.confidence <= 1.0
```

- [ ] **Step 2: Run to see RED**

Run: `python -m pytest tests/evaluation/patterns/test_flag_classifier.py::test_default_synthetic_flag_is_detected -v`
Expected: FAIL — current implementation returns `detected=False`.

- [ ] **Step 3: Implement gates 2–10 + search**

Build the full search in `flag_classifier.py`. Inputs and outputs per spec §3.1.

```python
# swing/evaluation/patterns/flag_classifier.py — full implementation
from __future__ import annotations
from dataclasses import dataclass, field
from datetime import date
import pandas as pd
import numpy as np

POLE_GAIN_MIN = 0.30
PULLBACK_DEPTH_MAX = 0.15
TIGHTNESS_RATIO_MAX = 0.6
VOLUME_RATIO_MAX = 0.7
M_RANGE = range(5, 31)   # pole length [5, 30]
N_RANGE = range(5, 22)   # flag length [5, 21]
MIN_BARS = 36


@dataclass(frozen=True)
class FlagClassificationResult:
    detected: bool
    confidence: float
    pattern: str | None
    pole_start_date: date | None
    pole_end_date: date | None
    flag_start_date: date | None
    flag_end_date: date | None
    pole_high: float | None
    flag_low: float | None
    pivot: float | None
    components: dict[str, float] = field(default_factory=dict)


def _clamp(x: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, x))


def _ma_structure_passes(closes: np.ndarray, flag_start_idx: int) -> bool:
    """Gate 5: at flag_start, SMA10 > SMA20 > SMA50 AND each rising over
    the last 5 bars (today vs 5 bars ago, exclusive)."""
    if flag_start_idx < 50 + 5:
        return False
    def sma(window: int, at: int) -> float:
        return float(np.mean(closes[at - window + 1:at + 1]))
    today = flag_start_idx
    earlier = flag_start_idx - 5
    s10 = sma(10, today); s20 = sma(20, today); s50 = sma(50, today)
    if not (s10 > s20 > s50):
        return False
    for w in (10, 20, 50):
        if sma(w, today) <= sma(w, earlier):
            return False
    return True


def _evaluate_candidate(
    bars: pd.DataFrame, pole_start: int, flag_start: int, flag_end: int,
) -> dict:
    """Return per-gate measurements for a single (pole_start, flag_start, flag_end)
    triple. Caller decides pass/fail + ranking."""
    closes = bars["Close"].to_numpy(dtype=float)
    highs = bars["High"].to_numpy(dtype=float)
    lows = bars["Low"].to_numpy(dtype=float)
    vols = bars["Volume"].to_numpy(dtype=float)

    pole_high = float(highs[pole_start:flag_start].max())
    pole_low = float(lows[pole_start:flag_start].min())
    flag_high = float(highs[flag_start:flag_end].max())
    flag_low = float(lows[flag_start:flag_end].min())

    pole_gain = (pole_high - pole_low) / max(pole_low, 1e-9)
    pullback_depth = (pole_high - flag_low) / max(pole_high, 1e-9)

    pole_ranges = (highs[pole_start:flag_start] - lows[pole_start:flag_start]) \
        / np.maximum(closes[pole_start:flag_start], 1e-9)
    flag_ranges = (highs[flag_start:flag_end] - lows[flag_start:flag_end]) \
        / np.maximum(closes[flag_start:flag_end], 1e-9)
    pole_med = float(np.median(pole_ranges)) if len(pole_ranges) else 0.0
    flag_med = float(np.median(flag_ranges)) if len(flag_ranges) else 0.0
    tightness_ratio = flag_med / max(pole_med, 1e-9)

    pole_vol_mean = float(np.mean(vols[pole_start:flag_start])) if (flag_start - pole_start) else 0.0
    flag_vol_mean = float(np.mean(vols[flag_start:flag_end])) if (flag_end - flag_start) else 0.0
    volume_ratio = flag_vol_mean / max(pole_vol_mean, 1e-9)

    N = flag_end - flag_start
    half = N // 2
    flag_low_first_half = float(np.min(lows[flag_start:flag_start + half])) if half else flag_low
    flag_low_second_half = float(np.min(lows[flag_start + half:flag_end])) if (N - half) else flag_low
    flag_floor_holds = flag_low_second_half >= flag_low_first_half

    ma_ok = _ma_structure_passes(closes, flag_start)

    return {
        "pole_M": float(flag_start - pole_start),
        "flag_N": float(N),
        "pole_gain": pole_gain,
        "pullback_depth": pullback_depth,
        "tightness_ratio": tightness_ratio,
        "volume_ratio": volume_ratio,
        "ma_structure": float(ma_ok),
        "flag_floor_holds": float(flag_floor_holds),
        "pole_high": pole_high,
        "flag_low": flag_low,
        "pivot": flag_high,
    }


def _continuous_clearances(c: dict) -> tuple[float, float, float, float]:
    return (
        _clamp((c["pole_gain"] - POLE_GAIN_MIN) / 0.70, 0.0, 1.0),
        _clamp((PULLBACK_DEPTH_MAX - c["pullback_depth"]) / PULLBACK_DEPTH_MAX, 0.0, 1.0),
        _clamp((TIGHTNESS_RATIO_MAX - c["tightness_ratio"]) / TIGHTNESS_RATIO_MAX, 0.0, 1.0),
        _clamp((VOLUME_RATIO_MAX - c["volume_ratio"]) / VOLUME_RATIO_MAX, 0.0, 1.0),
    )


def _soft_clearances(c: dict) -> tuple[float, float, float, float]:
    """Allow negative values for failed continuous gates (best-attempted ranking)."""
    return (
        (c["pole_gain"] - POLE_GAIN_MIN) / 0.70,
        (PULLBACK_DEPTH_MAX - c["pullback_depth"]) / PULLBACK_DEPTH_MAX,
        (TIGHTNESS_RATIO_MAX - c["tightness_ratio"]) / TIGHTNESS_RATIO_MAX,
        (VOLUME_RATIO_MAX - c["volume_ratio"]) / VOLUME_RATIO_MAX,
    )


def _detection_passes(c: dict) -> bool:
    return (
        c["pole_gain"] >= POLE_GAIN_MIN
        and c["pullback_depth"] <= PULLBACK_DEPTH_MAX
        and c["tightness_ratio"] <= TIGHTNESS_RATIO_MAX
        and c["volume_ratio"] <= VOLUME_RATIO_MAX
        and c["ma_structure"] >= 1.0
        and c["flag_floor_holds"] >= 1.0
    )


def classify_flag(bars: pd.DataFrame) -> FlagClassificationResult:
    if len(bars) < MIN_BARS:
        return FlagClassificationResult(
            detected=False, confidence=0.0, pattern="none",
            pole_start_date=None, pole_end_date=None,
            flag_start_date=None, flag_end_date=None,
            pole_high=None, flag_low=None, pivot=None,
            components={},
        )

    n = len(bars)
    best_pass = None  # (confidence, -N (lower better), -M (lower better), c, anchors)
    best_attempt = None  # (max_min_soft_clearance, c, anchors)

    for N in N_RANGE:
        flag_end = n
        flag_start = n - N
        if flag_start <= 0:
            continue
        for M in M_RANGE:
            pole_start = flag_start - M
            if pole_start < 0:
                continue
            c = _evaluate_candidate(bars, pole_start, flag_start, flag_end)
            anchors = (pole_start, flag_start, flag_end)
            if _detection_passes(c):
                conf = min(_continuous_clearances(c))
                # Tie-break: higher confidence first; on tie, lower N then lower M.
                key = (conf, -N, -M)
                if best_pass is None or key > best_pass[0]:
                    best_pass = (key, c, anchors)
            soft_min = min(_soft_clearances(c))
            if best_attempt is None or soft_min > best_attempt[0]:
                best_attempt = (soft_min, c, anchors)

    if best_pass is not None:
        _, c, (ps, fs, fe) = best_pass
        idx = bars.index
        return FlagClassificationResult(
            detected=True,
            confidence=min(_continuous_clearances(c)),
            pattern="flag",
            pole_start_date=idx[ps].date() if hasattr(idx[ps], "date") else None,
            pole_end_date=idx[fs - 1].date() if hasattr(idx[fs - 1], "date") else None,
            flag_start_date=idx[fs].date() if hasattr(idx[fs], "date") else None,
            flag_end_date=idx[fe - 1].date() if hasattr(idx[fe - 1], "date") else None,
            pole_high=c["pole_high"],
            flag_low=c["flag_low"],
            pivot=c["pivot"],
            components=c,
        )

    # No candidate passes. Use deterministic baseline (5, 5) IF best_attempt's
    # soft_min < 0 and (5, 5) was evaluable; else use best_attempt for debugging.
    if best_attempt is not None:
        _, c, _ = best_attempt
        components = dict(c)
    else:
        components = {"pole_M": 5.0, "flag_N": 5.0}
    return FlagClassificationResult(
        detected=False, confidence=0.0, pattern="none",
        pole_start_date=None, pole_end_date=None,
        flag_start_date=None, flag_end_date=None,
        pole_high=None, flag_low=None, pivot=None,
        components=components,
    )
```

- [ ] **Step 4: Run to see GREEN**

Run: `python -m pytest tests/evaluation/patterns/test_flag_classifier.py -v`
Expected: PASS for `test_default_synthetic_flag_is_detected` AND the prior `data_window` tests.

- [ ] **Step 5: Commit**

```bash
git add swing/evaluation/patterns/flag_classifier.py tests/evaluation/patterns/_synthetic.py tests/evaluation/patterns/test_flag_classifier.py
git commit -m "feat(patterns): flag_classifier search loop + all gates"
```

### Task 1.4 — pole_gain gate threshold pair

Implements spec §3.1.3 gate 4 + §4.1.

- [ ] **Step 1: Write failing pair**

```python
def test_pole_gain_gate_at_threshold_below_rejects():
    bars = make_flag_bars(pole_gain_pct=0.299)
    res = classify_flag(bars)
    assert res.detected is False
    assert res.pattern == "none"


def test_pole_gain_gate_at_threshold_above_passes():
    bars = make_flag_bars(pole_gain_pct=0.301)
    res = classify_flag(bars)
    assert res.detected is True
    assert res.pattern == "flag"
```

- [ ] **Step 2: Run to see GREEN (gate already implemented in 1.3)**

Run: `python -m pytest tests/evaluation/patterns/test_flag_classifier.py::test_pole_gain_gate_at_threshold_below_rejects tests/evaluation/patterns/test_flag_classifier.py::test_pole_gain_gate_at_threshold_above_passes -v`
Expected: PASS both. If FAIL, the threshold logic is wrong — fix in `_detection_passes` / `_continuous_clearances` before commit.

- [ ] **Step 3: Confirm discriminating-test discipline**

Manually toggle `POLE_GAIN_MIN` to `0.25` in the source, re-run the pair: the `_below_rejects` test MUST flip to detected=True. Restore `0.30`. This proves the test pair is sensitive to the threshold value. If both tests pass under both threshold settings, the synthetic fixture is not actually crossing the gate — fix the fixture.

- [ ] **Step 4: Commit**

```bash
git add tests/evaluation/patterns/test_flag_classifier.py
git commit -m "test(patterns): pole_gain gate threshold pair (0.299 vs 0.301)"
```

### Task 1.5 — pullback_depth gate threshold pair

Implements spec §3.1.3 gate 6 + §4.1.

- [ ] **Step 1: Write failing pair**

```python
def test_pullback_depth_gate_above_threshold_rejects():
    bars = make_flag_bars(pullback_pct=0.151)
    res = classify_flag(bars)
    assert res.detected is False


def test_pullback_depth_gate_below_threshold_passes():
    bars = make_flag_bars(pullback_pct=0.149)
    res = classify_flag(bars)
    assert res.detected is True
```

- [ ] **Step 2: Run + commit**

Run: `python -m pytest tests/evaluation/patterns/test_flag_classifier.py::test_pullback_depth_gate_above_threshold_rejects tests/evaluation/patterns/test_flag_classifier.py::test_pullback_depth_gate_below_threshold_passes -v`
Expected: PASS both.

```bash
git add tests/evaluation/patterns/test_flag_classifier.py
git commit -m "test(patterns): pullback_depth gate threshold pair (0.149 vs 0.151)"
```

### Task 1.6 — tightness_ratio gate threshold pair

Implements spec §3.1.3 gate 7 + §4.1.

- [ ] **Step 1: Write failing pair**

```python
def test_tightness_ratio_gate_above_threshold_rejects():
    bars = make_flag_bars(flag_tightness_factor=0.601)
    res = classify_flag(bars)
    assert res.detected is False


def test_tightness_ratio_gate_below_threshold_passes():
    bars = make_flag_bars(flag_tightness_factor=0.599)
    res = classify_flag(bars)
    assert res.detected is True
```

- [ ] **Step 2: Run + commit**

```bash
git add tests/evaluation/patterns/test_flag_classifier.py
git commit -m "test(patterns): tightness_ratio gate threshold pair"
```

### Task 1.7 — volume_contraction gate threshold pair

Implements spec §3.1.3 gate 8 + §4.1.

- [ ] **Step 1: Write failing pair**

```python
def test_volume_contraction_gate_above_threshold_rejects():
    bars = make_flag_bars(flag_volume_factor=0.701)
    res = classify_flag(bars)
    assert res.detected is False


def test_volume_contraction_gate_below_threshold_passes():
    bars = make_flag_bars(flag_volume_factor=0.699)
    res = classify_flag(bars)
    assert res.detected is True
```

- [ ] **Step 2: Run + commit**

```bash
git add tests/evaluation/patterns/test_flag_classifier.py
git commit -m "test(patterns): volume_contraction gate threshold pair"
```

### Task 1.8 — ma_structure gate (binary; stacked + rising)

Implements spec §3.1.3 gate 5 + §4.1. The default synthetic builder produces stacked-and-rising SMAs. Three cases: not-stacked, stacked-but-flat, stacked-and-rising.

- [ ] **Step 1: Write failing tests**

```python
def test_ma_structure_not_stacked_rejects():
    # Setup: build a fixture where SMA10 < SMA50 at flag_start.
    # Achieved by setting pre_run_bars to a DOWNTREND (negative slope).
    bars = make_flag_bars()
    # Force a 50-bar lookback that ends UP/UP/DOWN ordering. We construct
    # by overwriting Close in the pre-run region with a downtrend so SMA50
    # lags above SMA10/20.
    closes = bars["Close"].to_numpy().copy()
    n_pre = 30
    closes[:n_pre] = np.linspace(120.0, 100.0, n_pre)  # downtrend into pole
    bars = bars.assign(Close=closes, Open=closes)
    res = classify_flag(bars)
    assert res.detected is False


def test_ma_structure_stacked_and_rising_passes():
    bars = make_flag_bars()
    res = classify_flag(bars)
    assert res.detected is True
```

- [ ] **Step 2: Run + commit**

Run the pair. The stacked-and-rising case must PASS; the non-stacked case must FAIL.

```bash
git add tests/evaluation/patterns/test_flag_classifier.py
git commit -m "test(patterns): ma_structure gate (stacked + rising)"
```

### Task 1.9 — flag_floor_holds gate

Implements spec §3.1.3 gate 9 (R1 C2 fix).

- [ ] **Step 1: Write failing pair**

```python
def test_flag_floor_holds_gate_drifting_floor_rejects():
    bars = make_flag_bars(floor_holds=False)
    res = classify_flag(bars)
    assert res.detected is False
    # Discriminating verification: flag_floor_holds component must be 0.0.
    assert res.components.get("flag_floor_holds", 1.0) == 0.0


def test_flag_floor_holds_gate_holding_floor_passes():
    bars = make_flag_bars(floor_holds=True)
    res = classify_flag(bars)
    assert res.detected is True
```

- [ ] **Step 2: Run + commit**

```bash
git add tests/evaluation/patterns/test_flag_classifier.py
git commit -m "test(patterns): flag_floor_holds gate (drifting vs holding)"
```

### Task 1.10 — confidence min-aggregation

Implements spec §3.1.4. Use a fixture where one clearance is 0.2 and the others are ≥ 0.9.

- [ ] **Step 1: Write failing test**

```python
def test_confidence_is_min_of_continuous_clearances():
    # pole_gain just above 0.30 → clearance ≈ 0.014 (smallest)
    # pullback_pct = 0.05 → pullback clearance ≈ 0.667
    # tightness 0.3 → clearance ≈ 0.5
    # volume 0.3 → clearance ≈ 0.571
    bars = make_flag_bars(
        pole_gain_pct=0.31,           # tight on pole_gain
        pullback_pct=0.05,
        flag_tightness_factor=0.3,
        flag_volume_factor=0.3,
    )
    res = classify_flag(bars)
    assert res.detected is True
    # The minimum clearance (pole_gain) should drive confidence.
    expected_min = (0.31 - 0.30) / 0.70
    assert abs(res.confidence - expected_min) < 0.05
```

- [ ] **Step 2: Run + commit**

```bash
git add tests/evaluation/patterns/test_flag_classifier.py
git commit -m "test(patterns): confidence min-aggregation"
```

### Task 1.11 — search picks best fit; tie-break

Implements spec §3.1.2 step 3.

- [ ] **Step 1: Write failing test**

```python
def test_search_prefers_higher_confidence_then_lower_N_then_lower_M():
    # Build a fixture admitting multiple valid (M, N) candidates. Default
    # builder yields one passing window; we widen the flag region so that
    # several N values pass.
    bars = make_flag_bars(flag_bars=15)  # multiple N in [5, 15] could pass
    res = classify_flag(bars)
    assert res.detected is True
    # The search must report SOME (M, N) — and must be deterministic across
    # calls (tie-break by lower N then lower M).
    res2 = classify_flag(bars)
    assert res.components["flag_N"] == res2.components["flag_N"]
    assert res.components["pole_M"] == res2.components["pole_M"]
```

- [ ] **Step 2: Run + commit**

```bash
git add tests/evaluation/patterns/test_flag_classifier.py
git commit -m "test(patterns): search determinism + tie-break"
```

### Task 1.12 — best-attempted candidate (max-min soft clearance)

Implements spec §3.1.2 step 4 + R1 M3 / R2 M1 ranking.

- [ ] **Step 1: Write failing test**

```python
def test_best_attempted_uses_max_min_soft_clearance():
    # Build a fixture where NO candidate passes. The algorithm should still
    # populate components_json with the (M, N) candidate whose min-soft-
    # clearance is highest (i.e., closest to passing).
    bars = make_flag_bars(pole_gain_pct=0.20)  # all candidates fail pole_gain
    res = classify_flag(bars)
    assert res.detected is False
    assert "pole_gain" in res.components
    # Soft clearance for pole_gain at 0.20: (0.20 - 0.30) / 0.70 ≈ -0.143.
    # Across all (M, N), the best-attempted must report a pole_gain in the
    # neighborhood of the synthetic value (≈ 0.20).
    assert 0.15 < res.components["pole_gain"] < 0.25
```

- [ ] **Step 2: Run + commit**

```bash
git add tests/evaluation/patterns/test_flag_classifier.py
git commit -m "test(patterns): best-attempted ranking via max-min soft clearance"
```

### Task 1.13 — `pattern=NULL` adapter for classifier-error path

Implements spec §3.2.1 NULL semantics + §3.3 exception handling at the pipeline boundary. The classifier itself does NOT catch — exceptions propagate. The pipeline-side adapter (`_step_charts`, Phase 3) is what catches and synthesizes a `FlagClassificationResult` with `pattern=None`. This task tests the dataclass field discipline so future maintainers don't accidentally collapse `None` and `'none'` (R1 M1 + R2 Minor 1).

- [ ] **Step 1: Write test asserting the type contract**

```python
def test_pattern_None_distinct_from_string_none_in_dataclass():
    """Future-proofing: pattern is `str | None`, NOT `str`. Pipeline-level
    classifier-error path constructs a result with pattern=None (NoneType)
    that persists as SQL NULL, distinguishing it from pattern='none'
    (evaluated negative). This test guards against accidental
    `pattern: str = 'none'` field re-typing."""
    from swing.evaluation.patterns.flag_classifier import FlagClassificationResult
    err_result = FlagClassificationResult(
        detected=False, confidence=0.0, pattern=None,
        pole_start_date=None, pole_end_date=None,
        flag_start_date=None, flag_end_date=None,
        pole_high=None, flag_low=None, pivot=None,
        components={"error": "boom"},
    )
    assert err_result.pattern is None
    assert err_result.pattern != "none"
```

- [ ] **Step 2: Run + commit**

```bash
git add tests/evaluation/patterns/test_flag_classifier.py
git commit -m "test(patterns): pattern=None distinct from 'none' (NULL vs string)"
```

### Task 1.14 — Phase 1 checkpoint

- [ ] **Step 1: Run full fast suite + ruff**

```bash
python -m pytest -m "not slow" -q
ruff check swing/evaluation/patterns/
```

Expected: fast suite green; no new ruff violations introduced by Phase 1.

- [ ] **Step 2: Confirm spec coverage for Phase 1**

Manually walk spec §3.1.1 (dataclass), §3.1.2 (algorithm), §3.1.3 (gates 1–10), §3.1.4 (confidence). Each must point at a Phase 1 task. Gate 11 (breakout) is informational and need not gate detection — verify components dict carries today's close vs pivot for diagnostics if your implementation reaches that point; otherwise leave for Phase 6 chart overlay (the operator reads breakout off the chart).

---

# Phase 2 — Persistence (Phase 2 carve-out)

**Pre-conditions:** Phase 1 green; baseline schema_version = 8.
**Scope:** Migrations 0009 + 0010; `pipeline_pattern_classifications` repo; `Trade` dataclass +4 fields; `insert_trade_with_event` + every read path threading 4 new columns; repo-layer cross-column ValueError invariant.
**Phase-end checkpoint:** fast suite green; migrations apply forward and idempotently on a v8 DB; CHECK constraints reject inconsistent state; repo-layer ValueError fires on invalid Trade combinations.
**Spec sections:** §1.2 deliverable 2; §3.2 (persistence); §4.5 (persistence tests); §5 (carve-outs).

### Task 2.1 — Bump `EXPECTED_SCHEMA_VERSION` constant

Implements spec §3.2 migration sequence preflight.

**Files:**
- Modify: `swing/data/db.py`

The constant lives near the top of `swing/data/db.py`. Bump from `8` to `10` so `ensure_schema` is willing to apply 0009 + 0010. Do this as a SINGLE bump in the same PR/commit chain as the migration files — otherwise a half-landed state has the constant pointing at a version that doesn't have a migration.

- [ ] **Step 1: Locate the constant**

```bash
grep -n "EXPECTED_SCHEMA_VERSION" swing/data/db.py
```

Expected: one or two lines naming the constant.

- [ ] **Step 2: Bump from 8 → 10**

Edit `swing/data/db.py` and change `EXPECTED_SCHEMA_VERSION = 8` to `EXPECTED_SCHEMA_VERSION = 10`. Do NOT commit alone — the next two tasks land the migration files; the bump must be in a commit that ALSO contains the SQL files so a checkout at any commit boundary has a consistent state.

- [ ] **Step 3: Defer commit until 2.2 + 2.3 are ready**

No commit at this task; Task 2.3 commits all three files (constant + 0009 + 0010) together.

### Task 2.2 — Migration 0009: `pipeline_pattern_classifications` table

Implements spec §3.2.1.

**Files:**
- Create: `swing/data/migrations/0009_pipeline_pattern_classifications.sql`
- Create: `tests/data/test_migration_0009_pattern_classifications.py`

- [ ] **Step 1: Write failing migration test**

```python
# tests/data/test_migration_0009_pattern_classifications.py
import sqlite3
from pathlib import Path
import pytest
from swing.data.db import ensure_schema


def test_migration_0009_creates_pattern_classifications_table(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' "
            "AND name='pipeline_pattern_classifications'"
        )
        assert cur.fetchone() is not None
        # Index present.
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND name='idx_pattern_classifications_run'"
        )
        assert cur.fetchone() is not None
        # schema_version reaches 10 (or higher if more migrations land).
        cur = conn.execute("SELECT version FROM schema_version")
        assert cur.fetchone()[0] >= 9
    finally:
        conn.close()


def test_migration_0009_pattern_state_consistency_check_rejects_mixed_state(tmp_path: Path):
    """Row-level CHECK rejects pattern='flag' with NULL confidence/pivot."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        # Seed a pipeline_runs row to satisfy FK.
        conn.execute(
            "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
            "action_session_date, state, lease_token) "
            "VALUES ('2026-04-26T00:00:00', 'manual', '2026-04-25', "
            "'2026-04-26', 'complete', 'tok')"
        )
        run_id = conn.execute("SELECT id FROM pipeline_runs").fetchone()[0]
        with pytest.raises(sqlite3.IntegrityError) as exc_info:
            conn.execute(
                "INSERT INTO pipeline_pattern_classifications "
                "(pipeline_run_id, ticker, pattern, confidence, components_json, computed_at) "
                "VALUES (?, ?, 'flag', NULL, '{}', '2026-04-26T00:00:00')",
                (run_id, "TEST"),
            )
        assert "pattern_state_consistency" in str(exc_info.value) or "CHECK" in str(exc_info.value)
    finally:
        conn.close()


def test_migration_0009_idempotent_on_v9_or_later(tmp_path: Path):
    """A second ensure_schema on an already-migrated DB is a no-op."""
    db = tmp_path / "swing.db"
    conn1 = ensure_schema(db)
    conn1.close()
    conn2 = ensure_schema(db)  # MUST NOT raise.
    try:
        cur = conn2.execute("SELECT version FROM schema_version")
        assert cur.fetchone()[0] >= 9
    finally:
        conn2.close()
```

- [ ] **Step 2: Run to see RED**

Run: `python -m pytest tests/data/test_migration_0009_pattern_classifications.py -v`
Expected: FAIL — migration file doesn't exist; ensure_schema raises or table missing.

- [ ] **Step 3: Create migration 0009**

Use the SQL from spec §3.2.1 verbatim. Save as `swing/data/migrations/0009_pipeline_pattern_classifications.sql`. Confirm:
- `CREATE TABLE pipeline_pattern_classifications (...)` (NOT `IF NOT EXISTS` — fail-loud on rerun matches 0008's discipline).
- `pattern TEXT CHECK (pattern IS NULL OR pattern IN ('none', 'flag'))`.
- `confidence REAL CHECK (confidence IS NULL OR (confidence >= 0.0 AND confidence <= 1.0))`.
- All four boundary-date columns (`pole_start_date`, `pole_end_date`, `flag_start_date`, `flag_end_date`).
- `UNIQUE (pipeline_run_id, ticker)`.
- `CONSTRAINT pattern_state_consistency CHECK (...)` covering both branches per spec §3.2.1.
- `CREATE INDEX idx_pattern_classifications_run ON pipeline_pattern_classifications(pipeline_run_id);`
- `UPDATE schema_version SET version = 9;`

Do NOT commit yet — Task 2.3 lands 0010 alongside.

### Task 2.3 — Migration 0010: trade chart_pattern columns + commit the migration trio

Implements spec §3.2.2.

**Files:**
- Create: `swing/data/migrations/0010_trade_chart_pattern.sql`
- Create: `tests/data/test_migration_0010_trade_chart_pattern.py`

- [ ] **Step 1: Write failing migration test**

```python
# tests/data/test_migration_0010_trade_chart_pattern.py
import sqlite3
from pathlib import Path
import pytest
from swing.data.db import ensure_schema


def test_migration_0010_adds_four_trade_columns(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        cur = conn.execute("PRAGMA table_info(trades)")
        cols = {row[1] for row in cur.fetchall()}
        assert "chart_pattern_algo" in cols
        assert "chart_pattern_algo_confidence" in cols
        assert "chart_pattern_operator" in cols
        assert "chart_pattern_classification_pipeline_run_id" in cols
        cur = conn.execute("SELECT version FROM schema_version")
        assert cur.fetchone()[0] == 10
    finally:
        conn.close()


def test_migration_0010_chart_pattern_algo_check_rejects_invalid_value(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO trades (ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, status, "
                "chart_pattern_algo) VALUES "
                "('T', '2026-04-26', 10.0, 1, 9.0, 9.0, 'open', 'pennant')"
            )
    finally:
        conn.close()
```

- [ ] **Step 2: Run to see RED**

Run: `python -m pytest tests/data/test_migration_0010_trade_chart_pattern.py -v`
Expected: FAIL.

- [ ] **Step 3: Create migration 0010**

Use the SQL from spec §3.2.2 verbatim — preserving the FK comment qualifier ("whether the FK is ENFORCED depends on PRAGMA foreign_keys = ON ..."). Save as `swing/data/migrations/0010_trade_chart_pattern.sql`. Confirm:
- Four `ALTER TABLE trades ADD COLUMN` statements (algo, algo_confidence, operator, classification_pipeline_run_id).
- `CHECK` on `chart_pattern_algo IN ('none', 'flag')` (NULL allowed).
- `CHECK` on `chart_pattern_algo_confidence` 0.0–1.0 (NULL allowed).
- `chart_pattern_operator TEXT` (no CHECK — free-text per §3.6).
- `chart_pattern_classification_pipeline_run_id INTEGER REFERENCES pipeline_runs(id)`.
- `UPDATE schema_version SET version = 10;`

- [ ] **Step 4: Run to see GREEN**

Run: `python -m pytest tests/data/test_migration_0009_pattern_classifications.py tests/data/test_migration_0010_trade_chart_pattern.py -v`
Expected: PASS.

- [ ] **Step 5: Commit migration trio**

```bash
git add swing/data/db.py swing/data/migrations/0009_pipeline_pattern_classifications.sql swing/data/migrations/0010_trade_chart_pattern.sql tests/data/test_migration_0009_pattern_classifications.py tests/data/test_migration_0010_trade_chart_pattern.py
git commit -m "feat(data): migrations 0009 + 0010 for chart-pattern persistence"
```

### Task 2.4 — `PipelinePatternClassification` dataclass

Implements spec §3.2.3.

**Files:**
- Modify: `swing/data/models.py`
- Create: `tests/data/test_pattern_classification_model.py`

- [ ] **Step 1: Write failing test**

```python
# tests/data/test_pattern_classification_model.py
def test_pattern_classification_dataclass_shape():
    from swing.data.models import PipelinePatternClassification
    row = PipelinePatternClassification(
        id=1, pipeline_run_id=2, ticker="AAPL",
        pattern="flag", confidence=0.78,
        components_json='{"a":1}',
        pivot=10.0, pole_high=11.0, flag_low=9.0,
        pole_start_date="2026-04-01", pole_end_date="2026-04-10",
        flag_start_date="2026-04-11", flag_end_date="2026-04-18",
        computed_at="2026-04-26T00:00:00",
    )
    assert row.pattern == "flag"
    assert row.confidence == 0.78
```

- [ ] **Step 2: Run to see RED, add dataclass, run to see GREEN**

Append to `swing/data/models.py`:

```python
@dataclass(frozen=True)
class PipelinePatternClassification:
    """One row of `pipeline_pattern_classifications` (migration 0009).

    NULL semantics — spec §3.2.1:
      - pattern='flag', confidence=0.0–1.0 → detection.
      - pattern='none', confidence=NULL    → evaluated negative.
      - pattern=NULL,   confidence=NULL    → classifier error
        (components_json carries an "error" key).
    """
    id: int | None
    pipeline_run_id: int
    ticker: str
    pattern: str | None        # 'none' | 'flag' | None
    confidence: float | None
    components_json: str
    pivot: float | None
    pole_high: float | None
    flag_low: float | None
    pole_start_date: str | None
    pole_end_date: str | None
    flag_start_date: str | None
    flag_end_date: str | None
    computed_at: str
```

- [ ] **Step 3: Commit**

```bash
git add swing/data/models.py tests/data/test_pattern_classification_model.py
git commit -m "feat(data): PipelinePatternClassification dataclass"
```

### Task 2.5 — `pattern_classifications` repo + tests

Implements spec §3.2.3 repo signatures.

**Files:**
- Create: `swing/data/repos/pattern_classifications.py`
- Create: `tests/data/test_pattern_classifications_repo.py`

- [ ] **Step 1: Write failing test for insert + get + list**

```python
# tests/data/test_pattern_classifications_repo.py
import json
from pathlib import Path
import pytest
import sqlite3
from swing.data.db import ensure_schema
from swing.data.repos.pattern_classifications import (
    insert_classification, get_classification, list_classifications_for_run,
)
from swing.evaluation.patterns.flag_classifier import FlagClassificationResult
from datetime import date


def _seed_pipeline_run(conn) -> int:
    conn.execute(
        "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
        "action_session_date, state, lease_token) "
        "VALUES ('2026-04-26T00:00:00','manual','2026-04-25','2026-04-26','complete','t')"
    )
    return conn.execute("SELECT id FROM pipeline_runs").fetchone()[0]


def _flag_result() -> FlagClassificationResult:
    return FlagClassificationResult(
        detected=True, confidence=0.78, pattern="flag",
        pole_start_date=date(2026, 4, 1), pole_end_date=date(2026, 4, 10),
        flag_start_date=date(2026, 4, 11), flag_end_date=date(2026, 4, 18),
        pole_high=120.0, flag_low=110.0, pivot=119.5,
        components={"pole_gain": 0.45},
    )


def test_insert_and_get(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        with conn:
            row_id = insert_classification(
                conn, pipeline_run_id=run_id, ticker="AAPL",
                result=_flag_result(),
                computed_at="2026-04-26T00:00:00",
            )
        assert row_id > 0
        row = get_classification(conn, pipeline_run_id=run_id, ticker="AAPL")
        assert row is not None
        assert row.pattern == "flag"
        assert row.confidence == 0.78
        assert json.loads(row.components_json)["pole_gain"] == 0.45
    finally:
        conn.close()


def test_list_for_run_returns_mapping(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        with conn:
            insert_classification(conn, pipeline_run_id=run_id, ticker="AAPL",
                                  result=_flag_result(), computed_at="ts")
            insert_classification(conn, pipeline_run_id=run_id, ticker="MSFT",
                                  result=_flag_result(), computed_at="ts")
        m = list_classifications_for_run(conn, pipeline_run_id=run_id)
        assert set(m.keys()) == {"AAPL", "MSFT"}
    finally:
        conn.close()


def test_pattern_none_persists_with_NULL_confidence_and_anchors(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        none_result = FlagClassificationResult(
            detected=False, confidence=0.0, pattern="none",
            pole_start_date=None, pole_end_date=None,
            flag_start_date=None, flag_end_date=None,
            pole_high=None, flag_low=None, pivot=None,
            components={"pole_gain": 0.10},
        )
        with conn:
            insert_classification(conn, pipeline_run_id=run_id, ticker="X",
                                  result=none_result, computed_at="ts")
        row = get_classification(conn, pipeline_run_id=run_id, ticker="X")
        assert row.pattern == "none"
        assert row.confidence is None
        assert row.pivot is None


def test_pattern_None_classifier_error_persists_NULL(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        err_result = FlagClassificationResult(
            detected=False, confidence=0.0, pattern=None,
            pole_start_date=None, pole_end_date=None,
            flag_start_date=None, flag_end_date=None,
            pole_high=None, flag_low=None, pivot=None,
            components={"error": "boom"},
        )
        with conn:
            insert_classification(conn, pipeline_run_id=run_id, ticker="X",
                                  result=err_result, computed_at="ts")
        row = get_classification(conn, pipeline_run_id=run_id, ticker="X")
        assert row.pattern is None
        assert row.confidence is None
        assert "error" in json.loads(row.components_json)


def test_unique_constraint_rejects_duplicate_run_ticker(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        run_id = _seed_pipeline_run(conn)
        with conn:
            insert_classification(conn, pipeline_run_id=run_id, ticker="AAPL",
                                  result=_flag_result(), computed_at="ts")
        with pytest.raises(sqlite3.IntegrityError):
            with conn:
                insert_classification(conn, pipeline_run_id=run_id, ticker="AAPL",
                                      result=_flag_result(), computed_at="ts")
    finally:
        conn.close()
```

- [ ] **Step 2: Run to see RED**

Expected: FAIL — module doesn't exist.

- [ ] **Step 3: Implement `swing/data/repos/pattern_classifications.py`**

```python
"""Repo for `pipeline_pattern_classifications` cache table (migration 0009)."""
from __future__ import annotations
import json
import sqlite3
from typing import Mapping

from swing.data.models import PipelinePatternClassification
from swing.evaluation.patterns.flag_classifier import FlagClassificationResult


def _confidence_for_persistence(result: FlagClassificationResult) -> float | None:
    """Translate dataclass `confidence: float` → DB `confidence REAL` per
    spec §3.2.3: NULL when pattern != 'flag', otherwise the float value."""
    return result.confidence if result.pattern == "flag" else None


def _date_iso(d) -> str | None:
    return d.isoformat() if d is not None else None


def insert_classification(
    conn: sqlite3.Connection, *, pipeline_run_id: int, ticker: str,
    result: FlagClassificationResult, computed_at: str,
) -> int:
    """Insert one row. Caller wraps in `with conn:`. Returns row id.

    Persistence rules (spec §3.2.3):
      - pattern='flag': all anchor/confidence columns NOT NULL.
      - pattern='none': anchor/confidence columns NULL; components_json
        carries best-attempted measurements.
      - pattern is None (classifier error): same NULLs; components_json
        carries an "error" key.
    """
    if result.pattern == "flag":
        confidence = result.confidence
        pivot = result.pivot
        pole_high = result.pole_high
        flag_low = result.flag_low
        pole_start = _date_iso(result.pole_start_date)
        pole_end = _date_iso(result.pole_end_date)
        flag_start = _date_iso(result.flag_start_date)
        flag_end = _date_iso(result.flag_end_date)
        pattern = "flag"
    else:
        confidence = None
        pivot = pole_high = flag_low = None
        pole_start = pole_end = flag_start = flag_end = None
        pattern = result.pattern  # 'none' or None
    cur = conn.execute(
        """
        INSERT INTO pipeline_pattern_classifications
          (pipeline_run_id, ticker, pattern, confidence, components_json,
           pivot, pole_high, flag_low,
           pole_start_date, pole_end_date, flag_start_date, flag_end_date,
           computed_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (pipeline_run_id, ticker, pattern, confidence,
         json.dumps(result.components, sort_keys=True),
         pivot, pole_high, flag_low,
         pole_start, pole_end, flag_start, flag_end,
         computed_at),
    )
    return int(cur.lastrowid)


def _row_to_classification(row) -> PipelinePatternClassification:
    return PipelinePatternClassification(
        id=row[0], pipeline_run_id=row[1], ticker=row[2],
        pattern=row[3], confidence=row[4], components_json=row[5],
        pivot=row[6], pole_high=row[7], flag_low=row[8],
        pole_start_date=row[9], pole_end_date=row[10],
        flag_start_date=row[11], flag_end_date=row[12],
        computed_at=row[13],
    )


def get_classification(
    conn: sqlite3.Connection, *, pipeline_run_id: int, ticker: str,
) -> PipelinePatternClassification | None:
    row = conn.execute(
        """SELECT id, pipeline_run_id, ticker, pattern, confidence,
                  components_json, pivot, pole_high, flag_low,
                  pole_start_date, pole_end_date, flag_start_date, flag_end_date,
                  computed_at
           FROM pipeline_pattern_classifications
           WHERE pipeline_run_id = ? AND ticker = ?""",
        (pipeline_run_id, ticker),
    ).fetchone()
    return _row_to_classification(row) if row else None


def list_classifications_for_run(
    conn: sqlite3.Connection, *, pipeline_run_id: int,
) -> Mapping[str, PipelinePatternClassification]:
    rows = conn.execute(
        """SELECT id, pipeline_run_id, ticker, pattern, confidence,
                  components_json, pivot, pole_high, flag_low,
                  pole_start_date, pole_end_date, flag_start_date, flag_end_date,
                  computed_at
           FROM pipeline_pattern_classifications
           WHERE pipeline_run_id = ?""",
        (pipeline_run_id,),
    ).fetchall()
    return {r[2]: _row_to_classification(r) for r in rows}
```

- [ ] **Step 4: Run to see GREEN**

Run: `python -m pytest tests/data/test_pattern_classifications_repo.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/data/repos/pattern_classifications.py tests/data/test_pattern_classifications_repo.py
git commit -m "feat(data): pattern_classifications repo (insert/get/list)"
```

### Task 2.6 — `Trade` dataclass: 4 new fields

Implements spec §3.2.2 + §3.2.3.

**Files:**
- Modify: `swing/data/models.py`

- [ ] **Step 1: Write failing test asserting field shape**

Append to `tests/data/test_pattern_classification_model.py`:

```python
def test_trade_has_four_chart_pattern_fields():
    from swing.data.models import Trade
    t = Trade(
        id=None, ticker="AAPL", entry_date="2026-04-26",
        entry_price=10.0, initial_shares=1, initial_stop=9.0,
        current_stop=9.0, status="open",
        watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None,
    )
    assert t.hypothesis_label is None
    assert t.chart_pattern_algo is None
    assert t.chart_pattern_algo_confidence is None
    assert t.chart_pattern_operator is None
    assert t.chart_pattern_classification_pipeline_run_id is None
```

- [ ] **Step 2: Run to see RED, add fields, run to see GREEN**

In `swing/data/models.py`, extend the `Trade` dataclass with four trailing-default fields:

```python
@dataclass(frozen=True)
class Trade:
    id: int | None
    ticker: str
    entry_date: str
    entry_price: float
    initial_shares: int
    initial_stop: float
    current_stop: float
    status: str
    watchlist_entry_target: float | None
    watchlist_initial_stop: float | None
    notes: str | None
    hypothesis_label: str | None = None
    # Migration 0010 — chart-pattern algo + operator override + audit anchor.
    # All trailing-default to preserve every existing Trade(...) call site.
    # Joint-NULL invariants enforced at repo layer (insert_trade_with_event)
    # per spec §3.2.2.
    chart_pattern_algo: str | None = None
    chart_pattern_algo_confidence: float | None = None
    chart_pattern_operator: str | None = None
    chart_pattern_classification_pipeline_run_id: int | None = None
```

- [ ] **Step 3: Commit**

```bash
git add swing/data/models.py tests/data/test_pattern_classification_model.py
git commit -m "feat(data): Trade gains four chart_pattern_* fields"
```

### Task 2.7 — `insert_trade_with_event` writes 4 new columns + repo-layer cross-column ValueError

Implements spec §3.2.2 cross-column constraint (R2 M2 repo-layer enforcement).

**Files:**
- Modify: `swing/data/repos/trades.py`
- Create: `tests/data/test_trade_chart_pattern_columns.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/data/test_trade_chart_pattern_columns.py
from pathlib import Path
import pytest
from swing.data.db import ensure_schema
from swing.data.models import Trade
from swing.data.repos.trades import insert_trade_with_event, get_trade


def _make_trade(**over) -> Trade:
    base = dict(
        id=None, ticker="AAPL", entry_date="2026-04-26",
        entry_price=10.0, initial_shares=1, initial_stop=9.0,
        current_stop=9.0, status="open",
        watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None,
    )
    base.update(over)
    return Trade(**base)


def test_insert_trade_with_chart_pattern_flag_persists_all_four(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            tid = insert_trade_with_event(
                conn,
                _make_trade(
                    chart_pattern_algo="flag",
                    chart_pattern_algo_confidence=0.78,
                    chart_pattern_operator="flag",
                    chart_pattern_classification_pipeline_run_id=42,
                ),
                event_ts="2026-04-26T00:00:00", rationale="aplus-setup",
            )
        t = get_trade(conn, tid)
        assert t.chart_pattern_algo == "flag"
        assert t.chart_pattern_algo_confidence == 0.78
        assert t.chart_pattern_operator == "flag"
        assert t.chart_pattern_classification_pipeline_run_id == 42
    finally:
        conn.close()


def test_insert_trade_with_no_chart_pattern_columns_works(tmp_path: Path):
    """Backward-compat: existing call sites pass no chart_pattern_* fields."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            tid = insert_trade_with_event(
                conn, _make_trade(),
                event_ts="2026-04-26T00:00:00", rationale="aplus-setup",
            )
        t = get_trade(conn, tid)
        assert t.chart_pattern_algo is None
        assert t.chart_pattern_algo_confidence is None
        assert t.chart_pattern_operator is None
        assert t.chart_pattern_classification_pipeline_run_id is None
    finally:
        conn.close()


def test_insert_trade_flag_without_confidence_raises_valueerror(tmp_path: Path):
    """Repo-layer cross-column invariant per spec §3.2.2 (R2 M2)."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with pytest.raises(ValueError, match="chart_pattern"):
            with conn:
                insert_trade_with_event(
                    conn,
                    _make_trade(
                        chart_pattern_algo="flag",
                        chart_pattern_algo_confidence=None,
                        chart_pattern_classification_pipeline_run_id=1,
                    ),
                    event_ts="ts", rationale="aplus-setup",
                )
    finally:
        conn.close()


def test_insert_trade_none_with_confidence_raises_valueerror(tmp_path: Path):
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with pytest.raises(ValueError, match="chart_pattern"):
            with conn:
                insert_trade_with_event(
                    conn,
                    _make_trade(
                        chart_pattern_algo="none",
                        chart_pattern_algo_confidence=0.5,
                        chart_pattern_classification_pipeline_run_id=1,
                    ),
                    event_ts="ts", rationale="aplus-setup",
                )
    finally:
        conn.close()


def test_insert_trade_algo_set_anchor_unset_raises_valueerror(tmp_path: Path):
    """Joint-NULL invariant: algo NOT NULL ⟺ anchor NOT NULL."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with pytest.raises(ValueError, match="chart_pattern"):
            with conn:
                insert_trade_with_event(
                    conn,
                    _make_trade(
                        chart_pattern_algo="flag",
                        chart_pattern_algo_confidence=0.78,
                        chart_pattern_classification_pipeline_run_id=None,
                    ),
                    event_ts="ts", rationale="aplus-setup",
                )
    finally:
        conn.close()
```

- [ ] **Step 2: Run to see RED**

Expected: FAIL — INSERT statement doesn't have new columns; ValueError checks not implemented.

- [ ] **Step 3: Modify `insert_trade_with_event`**

Update `swing/data/repos/trades.py`:

```python
def _validate_chart_pattern_invariant(trade: Trade) -> None:
    """Repo-layer cross-column invariant per spec §3.2.2 (R2 M2).

    SQLite ALTER TABLE cannot add a multi-column row CHECK without a
    heavyweight rebuild. V1 enforces the invariant here. V2 hardens at
    schema level when the next trade-table rebuild bundles other changes.
    """
    algo = trade.chart_pattern_algo
    conf = trade.chart_pattern_algo_confidence
    anchor = trade.chart_pattern_classification_pipeline_run_id
    if (algo is None) != (anchor is None):
        raise ValueError(
            "chart_pattern invariant: algo and "
            "chart_pattern_classification_pipeline_run_id must both be "
            "NULL or both be non-NULL"
        )
    if algo == "flag" and conf is None:
        raise ValueError(
            "chart_pattern invariant: chart_pattern_algo='flag' requires "
            "chart_pattern_algo_confidence NOT NULL"
        )
    if algo == "none" and conf is not None:
        raise ValueError(
            "chart_pattern invariant: chart_pattern_algo='none' requires "
            "chart_pattern_algo_confidence NULL"
        )


def insert_trade_with_event(
    conn: sqlite3.Connection, trade: Trade, *,
    event_ts: str, rationale: str | None = None,
) -> int:
    _validate_chart_pattern_invariant(trade)
    cur = conn.execute(
        """
        INSERT INTO trades
            (ticker, entry_date, entry_price, initial_shares, initial_stop,
             current_stop, status, watchlist_entry_target,
             watchlist_initial_stop, notes, hypothesis_label,
             chart_pattern_algo, chart_pattern_algo_confidence,
             chart_pattern_operator,
             chart_pattern_classification_pipeline_run_id)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (trade.ticker, trade.entry_date, trade.entry_price, trade.initial_shares,
         trade.initial_stop, trade.current_stop, trade.status,
         trade.watchlist_entry_target, trade.watchlist_initial_stop, trade.notes,
         trade.hypothesis_label,
         trade.chart_pattern_algo, trade.chart_pattern_algo_confidence,
         trade.chart_pattern_operator,
         trade.chart_pattern_classification_pipeline_run_id),
    )
    trade_id = int(cur.lastrowid)
    payload = {
        "ticker": trade.ticker,
        "entry_date": trade.entry_date,
        "entry_price": trade.entry_price,
        "initial_shares": trade.initial_shares,
        "initial_stop": trade.initial_stop,
    }
    conn.execute(
        """INSERT INTO trade_events (trade_id, ts, event_type, payload_json, rationale)
           VALUES (?, ?, 'entry', ?, ?)""",
        (trade_id, event_ts, json.dumps(payload, sort_keys=True), rationale),
    )
    return trade_id
```

Do NOT yet modify any read paths — that is Task 2.8.

- [ ] **Step 4: Run targeted tests to see GREEN, fast suite to confirm no read-path regression yet**

Run targeted tests: `python -m pytest tests/data/test_trade_chart_pattern_columns.py -v`
Expected: PASS for all five tests.

Run fast suite: `python -m pytest -m "not slow" -q`
Expected: PASS — even though `_row_to_trade` doesn't yet thread the four new columns, `Trade` has trailing defaults so existing reads still construct a valid `Trade`. The new columns will read as NULL → fields default to None.

- [ ] **Step 5: Commit**

```bash
git add swing/data/repos/trades.py tests/data/test_trade_chart_pattern_columns.py
git commit -m "feat(data): insert_trade_with_event writes 4 chart_pattern columns + invariant"
```

### Task 2.8 — Thread 4 new columns through every `trades` read path + `_row_to_trade`

Implements spec §3.2.3 ("existing read queries SELECT them"). Six SELECT statements in `swing/data/repos/trades.py` use the explicit column list; each must gain the four columns. `_row_to_trade` must consume them.

**Files:**
- Modify: `swing/data/repos/trades.py`

**Read-path inventory (count enforces completeness — verify with grep before commit):**

```bash
grep -n "SELECT id, ticker, entry_date, entry_price" swing/data/repos/trades.py
```

Each match is a SELECT that needs the column extension. Currently six occurrences; the count MUST remain six after this task (no reads added or removed).

- [ ] **Step 1: Write failing test asserting end-to-end round-trip via `list_open_trades`**

Append to `tests/data/test_trade_chart_pattern_columns.py`:

```python
def test_list_open_trades_returns_chart_pattern_columns(tmp_path: Path):
    from swing.data.repos.trades import list_open_trades, list_closed_trades, find_any_open_trade, find_open_trade_by_match
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        with conn:
            insert_trade_with_event(
                conn,
                _make_trade(
                    chart_pattern_algo="flag",
                    chart_pattern_algo_confidence=0.78,
                    chart_pattern_operator=None,
                    chart_pattern_classification_pipeline_run_id=42,
                ),
                event_ts="ts", rationale="aplus-setup",
            )
        # Every read path must surface the new columns.
        for trades in [list_open_trades(conn), [find_any_open_trade(conn, ticker="AAPL")],
                       [find_open_trade_by_match(conn, ticker="AAPL", entry_date="2026-04-26")]]:
            assert trades[0].chart_pattern_algo == "flag"
            assert trades[0].chart_pattern_algo_confidence == 0.78
            assert trades[0].chart_pattern_classification_pipeline_run_id == 42
    finally:
        conn.close()
```

- [ ] **Step 2: Run to see RED**

Expected: FAIL — `_row_to_trade` reads only 12 columns; new columns aren't in the SELECT.

- [ ] **Step 3: Update every SELECT + `_row_to_trade`**

Modify `swing/data/repos/trades.py`. For EACH of the six `SELECT id, ticker, entry_date, entry_price, ...` queries, append the four columns (preserve column ORDER consistency across queries):

```sql
SELECT id, ticker, entry_date, entry_price, initial_shares, initial_stop,
       current_stop, status, watchlist_entry_target,
       watchlist_initial_stop, notes, hypothesis_label,
       chart_pattern_algo, chart_pattern_algo_confidence,
       chart_pattern_operator,
       chart_pattern_classification_pipeline_run_id
FROM trades ...
```

(For `list_closed_trades` joined query, prefix with `t.` for the four new columns to match the existing prefix style.)

Update `_row_to_trade`:

```python
def _row_to_trade(row: tuple) -> Trade:
    return Trade(
        id=row[0], ticker=row[1], entry_date=row[2], entry_price=row[3],
        initial_shares=row[4], initial_stop=row[5], current_stop=row[6],
        status=row[7], watchlist_entry_target=row[8],
        watchlist_initial_stop=row[9], notes=row[10],
        hypothesis_label=row[11],
        chart_pattern_algo=row[12],
        chart_pattern_algo_confidence=row[13],
        chart_pattern_operator=row[14],
        chart_pattern_classification_pipeline_run_id=row[15],
    )
```

- [ ] **Step 4: Run to see GREEN + fast suite**

Run targeted: `python -m pytest tests/data/test_trade_chart_pattern_columns.py -v`
Expected: PASS.

Run fast suite: `python -m pytest -m "not slow" -q`
Expected: PASS — no regressions.

Verify no SELECT was missed:
```bash
grep -c "chart_pattern_algo," swing/data/repos/trades.py
```
Expected: at least 7 occurrences (6 SELECTs + 1 INSERT column list + uses in `_row_to_trade`).

- [ ] **Step 5: Commit**

```bash
git add swing/data/repos/trades.py tests/data/test_trade_chart_pattern_columns.py
git commit -m "feat(data): all trades read paths thread 4 chart_pattern columns"
```

### Task 2.9 — Phase 2 checkpoint

- [ ] **Step 1: Run full fast suite + ruff**

```bash
python -m pytest -m "not slow" -q
ruff check swing/data/
```
Expected: green; no new ruff violations.

- [ ] **Step 2: Confirm Phase 2 carve-out file enumeration**

The plan's Phase 2 carve-out section at the end of this document MUST list every file in `swing/data/` and `swing/trades/` modified during Phase 2. Cross-check by listing changed files since the start of Phase 2:

```bash
git log --name-only --pretty=format: <baseline-sha>..HEAD | sort -u
```

Expected files (and only these in carve-out trees): `swing/data/db.py`, `swing/data/models.py`, `swing/data/migrations/0009_*.sql`, `swing/data/migrations/0010_*.sql`, `swing/data/repos/pattern_classifications.py`, `swing/data/repos/trades.py`. (`swing/trades/entry.py` is touched in Phase 5, not Phase 2.)

---

# Phase 3 — Pipeline integration (`_step_charts` extension)

**Pre-conditions:** Phase 2 green; classifier callable; cache table writable.
**Scope:** Extend `_step_charts` per-ticker loop to call `classify_flag` on `ohlcv.tail(60)`, persist a row in the SAME `lease.fenced_write()` block as `update_chart_target_status`, log the classifier-error path, build pattern overlay for chart rendering. Render-chart kwarg gating chart-overlay land in Phase 6 (smoke tests); the kwarg signature lands here so Phase 3's call site doesn't break.
**Phase-end checkpoint:** integration test for `_step_charts` writes one classification row per chart-scope ticker; classifier-exception path persists `pattern=NULL` + `components_json` with `"error"` key + `logger.warning` emitted; existing `_step_charts` happy/sad paths unchanged.
**Spec sections:** §1.2 deliverable 3; §3.3 (pipeline integration); §3.4 (chart overlay declaration only).

### Task 3.1 — `render_chart` gains `pattern_overlay` kwarg + `PatternOverlay` dataclass

Implements spec §3.4 declaration. The kwarg defaults to `None`; behavior on `None` MUST be byte-equivalent to the current `render_chart`. Painting bands/annotation when overlay is non-None lands in Phase 6.

**Files:**
- Modify: `swing/rendering/charts.py`
- Create: `tests/rendering/test_chart_overlay.py`

- [ ] **Step 1: Write failing equivalence test**

```python
# tests/rendering/test_chart_overlay.py
from pathlib import Path
import pandas as pd
import pytest
from swing.rendering.charts import render_chart


@pytest.fixture
def fake_ohlcv() -> pd.DataFrame:
    idx = pd.date_range("2026-01-01", periods=120, freq="B")
    return pd.DataFrame({
        "Open": 100.0, "High": 101.0, "Low": 99.0, "Close": 100.0,
        "Volume": 1_000_000.0,
    }, index=idx)


def test_render_chart_pattern_overlay_default_is_none_and_writes_png(
    tmp_path: Path, fake_ohlcv,
):
    """Backward-compat: render_chart(...) without pattern_overlay must
    behave as before — accept the call, produce the PNG."""
    out = tmp_path / "AAPL.png"
    res = render_chart(
        ticker="AAPL", ohlcv=fake_ohlcv, pivot=110.0, stop=95.0,
        output_path=out,
    )
    assert res == out
    assert out.exists()


def test_render_chart_accepts_pattern_overlay_none_kwarg(
    tmp_path: Path, fake_ohlcv,
):
    """The kwarg is OPTIONAL and defaults to None; passing None explicitly
    must produce the same PNG."""
    out = tmp_path / "AAPL.png"
    res = render_chart(
        ticker="AAPL", ohlcv=fake_ohlcv, pivot=110.0, stop=95.0,
        output_path=out, pattern_overlay=None,
    )
    assert res == out
```

- [ ] **Step 2: Run to see RED**

Expected: FAIL — `pattern_overlay` is not a recognized keyword argument.

- [ ] **Step 3: Add `PatternOverlay` + accept the kwarg (no behavior change yet)**

```python
# swing/rendering/charts.py — append
from dataclasses import dataclass
from datetime import date


@dataclass(frozen=True)
class PatternOverlay:
    """Algo-derived pole/flag region + algo-pivot for chart annotation.

    Distinct from the candidate-pivot hline already drawn by render_chart
    (operator-relevant for trade execution). Spec §3.4 (Q11 option B).
    """
    pattern: str
    confidence: float
    pole_start_date: date
    pole_end_date: date
    flag_start_date: date
    flag_end_date: date
    pivot: float

    @classmethod
    def from_classification(cls, r) -> "PatternOverlay | None":
        """Build from a FlagClassificationResult; returns None if not detected."""
        if not r.detected or r.pattern != "flag":
            return None
        return cls(
            pattern="flag", confidence=r.confidence,
            pole_start_date=r.pole_start_date, pole_end_date=r.pole_end_date,
            flag_start_date=r.flag_start_date, flag_end_date=r.flag_end_date,
            pivot=r.pivot,
        )
```

Modify `render_chart` signature to accept the kwarg without painting yet:

```python
def render_chart(
    *, ticker: str, ohlcv: pd.DataFrame, pivot: float, stop: float,
    output_path: Path,
    pattern_overlay: "PatternOverlay | None" = None,
) -> Path | None:
    # ... existing body unchanged ...
    # Phase 6 lands the band-painting when pattern_overlay is non-None.
```

- [ ] **Step 4: Run to see GREEN**

Run: `python -m pytest tests/rendering/test_chart_overlay.py -v`
Expected: PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/rendering/charts.py tests/rendering/test_chart_overlay.py
git commit -m "feat(rendering): PatternOverlay dataclass + render_chart kwarg (no-op when None)"
```

### Task 3.2 — `_step_charts` calls `classify_flag` + persists row in same fenced_write

Implements spec §3.3 happy path.

**Files:**
- Modify: `swing/pipeline/runner.py`
- Create: `tests/pipeline/test_step_charts_classification.py`

- [ ] **Step 1: Write failing integration test**

```python
# tests/pipeline/test_step_charts_classification.py
from pathlib import Path
import pandas as pd
from unittest.mock import MagicMock, patch

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.pattern_classifications import (
    list_classifications_for_run,
)
# Fixture-builder reuse:
from tests.evaluation.patterns._synthetic import make_flag_bars


@pytest.fixture
def stub_pipeline_state(tmp_path: Path):
    """Seed schema + a pipeline_runs row + chart_targets so _step_charts has
    enough state to iterate."""
    db_path = tmp_path / "swing.db"
    conn = ensure_schema(db_path)
    conn.execute(
        "INSERT INTO pipeline_runs (started_ts, trigger, data_asof_date, "
        "action_session_date, state, lease_token, current_step) "
        "VALUES ('2026-04-26T00:00:00','manual','2026-04-25','2026-04-26',"
        "'running','tok','charts')"
    )
    run_id = conn.execute("SELECT id FROM pipeline_runs").fetchone()[0]
    conn.commit()
    conn.close()
    return {"db_path": db_path, "run_id": run_id}


def test_step_charts_writes_classification_row_for_each_target(stub_pipeline_state, tmp_path):
    """End-to-end: _step_charts iterates targets, calls classify_flag,
    persists via insert_classification under the SAME lease.fenced_write
    as update_chart_target_status."""
    # NOTE: this test uses the harness-pattern of building a minimal cfg/lease
    # and passing a stub PriceFetcher. Refer to existing
    # tests/pipeline/test_step_charts_*.py for the harness shape and adapt.
    pytest.skip(
        "Harness-construction TODO during execution: lift the existing "
        "_step_charts test harness from tests/pipeline/test_step_charts_*.py "
        "and patch fetcher.get to return make_flag_bars() for ticker AAPL "
        "and a non-flag fixture for ticker NOPE. After patching, run "
        "_step_charts and assert list_classifications_for_run returns "
        "{'AAPL': pattern='flag', 'NOPE': pattern='none'}."
    )
```

The test is intentionally `pytest.skip`-based at this drafting stage because the existing `_step_charts` test harness is non-trivial (lease, staging dir, fetcher stub). Implementer's first step: locate `tests/pipeline/test_step_charts_*.py`, lift the smallest harness, adapt — replace the skip with the real assertions.

- [ ] **Step 2: Modify `_step_charts` to integrate the classifier**

Edit `swing/pipeline/runner.py:594-623` (the per-ticker loop). Insert classifier call between fetcher.get and render_chart, AND insert the cache write inside the existing `fenced_write` blocks. Reference implementation (preserving the spec §3.3 control flow):

```python
# Top-of-file imports — add:
import logging
from swing.data.repos.pattern_classifications import insert_classification
from swing.evaluation.patterns.flag_classifier import (
    FlagClassificationResult, classify_flag,
)
from swing.rendering.charts import PatternOverlay

logger = logging.getLogger(__name__)


# Inside _step_charts per-ticker loop, replace the existing block with:

errors_count = 0  # track for summary log line
for ticker, pivot, stop, _source in targets:
    try:
        ohlcv = fetcher.get(ticker, lookback_days=200, as_of_date=None)
    except Exception:
        with lease.fenced_write() as conn:
            update_chart_target_status(
                conn, pipeline_run_id=lease.run_id, ticker=ticker,
                chart_status="fetcher_failed",
            )
        continue

    # Classify on the in-hand OHLCV (last 60 completed bars).
    bars_60 = ohlcv.tail(60)
    try:
        classification = classify_flag(bars_60)
    except Exception as exc:
        logger.warning(
            f"flag_classifier failed for {ticker}: {exc!r}"
        )
        errors_count += 1
        # Synthesize a pattern=NULL result so downstream analysis can
        # distinguish system error from evaluated-negative (spec §3.2.2).
        classification = FlagClassificationResult(
            detected=False, confidence=0.0, pattern=None,
            pole_start_date=None, pole_end_date=None,
            flag_start_date=None, flag_end_date=None,
            pole_high=None, flag_low=None, pivot=None,
            components={"error": repr(exc)},
        )

    pattern_overlay = PatternOverlay.from_classification(classification)

    path = render_chart(
        ticker=ticker, ohlcv=ohlcv, pivot=pivot, stop=stop,
        output_path=staging.path / f"{ticker}.png",
        pattern_overlay=pattern_overlay,
    )
    chart_status = "ok" if path is not None else "too_few_bars"
    if path is not None:
        out_paths[ticker] = path

    # Single fenced write — chart_status update + classification row commit
    # together so a partial-failure leaves a structurally consistent state.
    with lease.fenced_write() as conn:
        update_chart_target_status(
            conn, pipeline_run_id=lease.run_id, ticker=ticker,
            chart_status=chart_status,
        )
        insert_classification(
            conn, pipeline_run_id=lease.run_id, ticker=ticker,
            result=classification,
            computed_at=datetime.now().isoformat(timespec="seconds"),
        )

# After the loop:
total = len(targets)
ok = total - errors_count - sum(1 for t, *_ in targets if t not in out_paths)
logger.info(f"flag_classifier: {ok}/{total} ok, {errors_count} errors")
```

(Verify `datetime` is already imported at the top of `runner.py`; if not, add `from datetime import datetime`.)

- [ ] **Step 3: Replace the test skip with the real harness**

Lift the harness from `tests/pipeline/test_step_charts_*.py` (the existing tests for chart-target persistence). Substitute a stub `fetcher.get` that returns `make_flag_bars()` for `'AAPL'` and a flat-bars OHLCV (no detection) for `'NOPE'`. Run `_step_charts`. Assert `list_classifications_for_run(conn, pipeline_run_id=run_id)['AAPL'].pattern == 'flag'` and `... ['NOPE'].pattern == 'none'`.

- [ ] **Step 4: Run to see GREEN + fast suite**

Run: `python -m pytest tests/pipeline/test_step_charts_classification.py -v`
Run: `python -m pytest -m "not slow" -q`
Expected: green.

- [ ] **Step 5: Commit**

```bash
git add swing/pipeline/runner.py tests/pipeline/test_step_charts_classification.py
git commit -m "feat(pipeline): _step_charts classifies + persists per-ticker classification"
```

### Task 3.3 — Classifier exception → log + persist `pattern=NULL`; chart proceeds without overlay

Implements spec §3.3 failure path (R2 M4 logging + R1 M1 NULL distinction).

**Files:**
- Modify: `tests/pipeline/test_step_charts_classification.py`

- [ ] **Step 1: Write failing test**

```python
def test_step_charts_classifier_exception_persists_NULL_and_logs(stub_pipeline_state, caplog):
    """Classifier exception → cache row with pattern=NULL + components_json
    error key; logger.warning fires; chart still renders (pattern_overlay=None)."""
    # Patch classify_flag at the runner's import site to raise on AAPL only.
    pytest.skip(
        "Implementer: monkeypatch swing.pipeline.runner.classify_flag to raise "
        "ValueError('boom') for one specific ticker. Run _step_charts. "
        "Assert list_classifications_for_run[ticker].pattern is None, "
        "json.loads(components_json)['error'] contains 'boom', "
        "and 'flag_classifier failed for' appears in caplog.records."
    )
```

Implementer flesh-out: monkeypatch the classifier import inside `swing.pipeline.runner` (NOT the source `swing.evaluation.patterns.flag_classifier.classify_flag` directly — patching at the runner's import site is the established pattern in this codebase per its other pipeline tests).

- [ ] **Step 2: Implementation already in 3.2 — confirm RED → GREEN with fleshed test**

Run: `python -m pytest tests/pipeline/test_step_charts_classification.py::test_step_charts_classifier_exception_persists_NULL_and_logs -v`
Expected: PASS once the test is fully fleshed (the exception-handling code in 3.2 already implements this behavior; this task only ADDS coverage for the negative path).

- [ ] **Step 3: Commit**

```bash
git add tests/pipeline/test_step_charts_classification.py
git commit -m "test(pipeline): classifier exception path persists NULL + logs warning"
```

### Task 3.4 — Phase 3 checkpoint

- [ ] **Step 1: Run full fast suite + ruff**

```bash
python -m pytest -m "not slow" -q
ruff check swing/pipeline/runner.py swing/rendering/charts.py
```
Expected: green; no new ruff violations.

- [ ] **Step 2: Manual smoke trigger** (optional, gates Phase 4 readiness)

If feasible, run a `swing pipeline run` against a small finviz CSV and confirm `pipeline_pattern_classifications` rows appear post-run (one per chart-scope ticker). Operator can defer this to end-of-Phase-7 instead.

---

# Phase 4 — Watchlist + dashboard read paths

**Pre-conditions:** Phase 3 green; classifications written by `_step_charts`. Config field `cfg.web.flag_pattern_display_threshold` exists (Task 4.0 lands it BEFORE other Phase 4 tasks reference it).
**Scope:** New `_pattern_tags` helper SIBLING to `_flag_tags`; `WatchlistVM` + `DashboardVM` gain `pattern_tags` field; `build_watchlist` / `build_watchlist_row` / `build_dashboard` resolve classifications by `pipeline_runs.evaluation_run_id` → `pipeline_run_id`; templates render the flag tag in a separate `<span>`. **`_sort_watchlist`, `_TAG_PRECEDENCE`, and `_flag_tags` are byte-for-byte UNCHANGED.**
**Phase-end checkpoint:** watchlist renders flag tag for detected rows; sort byte-equivalent to pre-Phase-4 baseline; mixed-anchor regression closed (post-pipeline standalone eval does not leak classifications).
**Spec sections:** §1.2 deliverable 4; §3.5 (watchlist tag rendering); §4.4 (sort-neutrality regression); §4.5 anchor test.

### Task 4.0 — Config: `cfg.web.flag_pattern_display_threshold`

Implements spec §3.8. Lands FIRST in Phase 4 because subsequent Phase 4 + Phase 5 tasks read this field.

**Files:**
- Modify: `swing/config.py`
- Create: `tests/test_config_flag_pattern.py`

- [ ] **Step 1: Write failing test**

```python
# tests/test_config_flag_pattern.py
def test_web_config_has_flag_pattern_display_threshold():
    from swing.config import Web
    assert Web().flag_pattern_display_threshold == 0.0
```

- [ ] **Step 2: Add the field**

Append to `Web` dataclass in `swing/config.py`:

```python
# Spec §3.8: filters watchlist flag-tag rendering. Default 0.0 = show every
# detected flag. Operator dials up after labeled-example calibration.
flag_pattern_display_threshold: float = 0.0
```

- [ ] **Step 3: Commit**

```bash
git add swing/config.py tests/test_config_flag_pattern.py
git commit -m "feat(config): cfg.web.flag_pattern_display_threshold default 0.0"
```

### Task 4.1 — `_pattern_tags` helper (sibling to `_flag_tags`)

Implements spec §3.5 helper signature.

**Files:**
- Modify: `swing/web/view_models/dashboard.py`
- Create: `tests/web/view_models/test_pattern_tags.py`

- [ ] **Step 1: Write failing helper test**

```python
# tests/web/view_models/test_pattern_tags.py
from swing.data.models import PipelinePatternClassification
from swing.web.view_models.dashboard import _pattern_tags


def _make_cls(ticker: str, pattern: str | None, conf: float | None):
    return PipelinePatternClassification(
        id=1, pipeline_run_id=1, ticker=ticker,
        pattern=pattern, confidence=conf, components_json="{}",
        pivot=None, pole_high=None, flag_low=None,
        pole_start_date=None, pole_end_date=None,
        flag_start_date=None, flag_end_date=None,
        computed_at="ts",
    )


def test_pattern_tags_emits_flag_format_above_threshold():
    classifications = {
        "AAPL": _make_cls("AAPL", "flag", 0.78),
        "MSFT": _make_cls("MSFT", "none", None),
    }
    tags = _pattern_tags(classifications, display_threshold=0.0)
    assert tags == {"AAPL": "flag (0.78)"}


def test_pattern_tags_filters_below_threshold():
    classifications = {"X": _make_cls("X", "flag", 0.10)}
    tags = _pattern_tags(classifications, display_threshold=0.50)
    assert tags == {}


def test_pattern_tags_filters_classifier_error_rows():
    classifications = {"X": _make_cls("X", None, None)}
    tags = _pattern_tags(classifications, display_threshold=0.0)
    assert tags == {}


def test_pattern_tags_handles_None_classifications_arg():
    assert _pattern_tags(None, display_threshold=0.0) == {}
```

- [ ] **Step 2: Run to see RED, implement helper, run to see GREEN**

Append to `swing/web/view_models/dashboard.py` (at module level, NOT inside any class):

```python
def _pattern_tags(
    classifications_by_ticker, display_threshold: float,
):
    """Return {ticker: 'flag (0.78)'} for tickers whose classification's
    pattern == 'flag' and confidence >= threshold. Spec §3.5 (R1 M2).

    SIBLING to `_flag_tags` — by construction the pattern tag NEVER enters
    the `tags` tuple consumed by `_sort_watchlist`. Sort-neutrality is
    structurally guaranteed."""
    if not classifications_by_ticker:
        return {}
    out: dict[str, str] = {}
    for ticker, cls in classifications_by_ticker.items():
        if (cls.pattern == "flag"
                and cls.confidence is not None
                and cls.confidence >= display_threshold):
            out[ticker] = f"flag ({cls.confidence:.2f})"
    return out
```

- [ ] **Step 3: Commit**

```bash
git add swing/web/view_models/dashboard.py tests/web/view_models/test_pattern_tags.py
git commit -m "feat(web): _pattern_tags helper (sibling to _flag_tags)"
```

### Task 4.2 — `WatchlistVM` + `DashboardVM` gain `pattern_tags` field; verify base-layout VMs

Implements spec §3.5 VM extension + CLAUDE.md base-layout shared VM gotcha.

**Files:**
- Modify: `swing/web/view_models/watchlist.py`
- Modify: `swing/web/view_models/dashboard.py`
- Modify: `swing/web/templates/base.html.j2` (audit only)

- [ ] **Step 1: Audit `base.html.j2` for `pattern_tags` reference**

```bash
grep -n "pattern_tags" swing/web/templates/base.html.j2
```
Expected: zero matches (the spec asserts `pattern_tags` is consumed only by watchlist + dashboard partials, not the base layout).

If matches DO appear, the plan branches: every base-layout VM (`DashboardVM`, `PipelineVM`, `JournalVM`, `WatchlistVM`, `PageErrorVM`) gains `pattern_tags: Mapping[str, str] = field(default_factory=dict)`. If zero matches, only `WatchlistVM` and `DashboardVM` need it.

- [ ] **Step 2: Write failing dataclass-shape tests**

```python
# tests/web/view_models/test_pattern_tags.py — append
def test_watchlist_vm_has_pattern_tags_field():
    from swing.web.view_models.watchlist import WatchlistVM
    import dataclasses
    fields = {f.name for f in dataclasses.fields(WatchlistVM)}
    assert "pattern_tags" in fields


def test_dashboard_vm_has_pattern_tags_field():
    from swing.web.view_models.dashboard import DashboardVM
    import dataclasses
    fields = {f.name for f in dataclasses.fields(DashboardVM)}
    assert "pattern_tags" in fields
```

- [ ] **Step 3: Run to see RED, add fields, run to see GREEN**

`swing/web/view_models/watchlist.py` — add to `WatchlistVM`:

```python
pattern_tags: Mapping[str, str] = field(default_factory=dict)
```

`swing/web/view_models/dashboard.py` — add to `DashboardVM`:

```python
pattern_tags: Mapping[str, str] = field(default_factory=dict)
```

(Both files already import `Mapping`; add `from dataclasses import field` if missing.)

- [ ] **Step 4: Commit**

```bash
git add swing/web/view_models/watchlist.py swing/web/view_models/dashboard.py tests/web/view_models/test_pattern_tags.py
git commit -m "feat(web): WatchlistVM + DashboardVM gain pattern_tags field"
```

### Task 4.3 — `build_watchlist` + `build_dashboard` load classifications by `pipeline_run_id`

Implements spec §3.5 + Bug-7-family anchor discipline.

**Files:**
- Modify: `swing/web/view_models/watchlist.py`
- Modify: `swing/web/view_models/dashboard.py`

- [ ] **Step 1: Write failing anchor-correctness test**

```python
# tests/web/view_models/test_watchlist_classifications_anchor.py
from pathlib import Path
import pytest
from swing.data.db import ensure_schema
from swing.data.repos.pattern_classifications import insert_classification
from swing.evaluation.patterns.flag_classifier import FlagClassificationResult
from datetime import date


def test_build_watchlist_uses_pipeline_run_id_not_latest_eval(tmp_path: Path):
    """Mixed-anchor closed: a post-pipeline standalone eval does NOT leak
    classifications from a prior pipeline run."""
    # Seed: pipeline_run #1 (complete) → has classification for AAPL.
    # Seed: standalone eval AFTER pipeline_run #1 finishes — no
    # classification rows. build_watchlist must surface AAPL's flag tag
    # from pipeline_run #1's row, NOT consult eval-latest at all.
    pytest.skip(
        "Implementer: seed pipeline_runs (state='complete', "
        "evaluation_run_id=N) with insert_classification for AAPL; seed "
        "an evaluation_runs row newer than the pipeline's finished_ts; "
        "call build_watchlist; assert vm.pattern_tags['AAPL'] == "
        "'flag (0.78)'. Then DELETE the classification row, re-call "
        "build_watchlist, assert pattern_tags is empty (proving the read "
        "binds to pipeline_run_id, not 'latest classification anywhere')."
    )
```

- [ ] **Step 2: Implementation**

In `swing/web/view_models/watchlist.py:build_watchlist`, AFTER the existing `pipeline_eval_id` resolution block, add:

```python
# Resolve pipeline_run_id (the parent of pipeline_eval_id).
pipeline_run_id: int | None = None
if pipeline_eval_id is not None:
    row = conn.execute(
        "SELECT id FROM pipeline_runs WHERE evaluation_run_id = ?",
        (pipeline_eval_id,),
    ).fetchone()
    pipeline_run_id = row[0] if row else None

# Load classifications.
from swing.data.repos.pattern_classifications import list_classifications_for_run
from swing.web.view_models.dashboard import _pattern_tags
if pipeline_run_id is not None:
    classifications = list_classifications_for_run(conn, pipeline_run_id=pipeline_run_id)
else:
    classifications = {}
```

Below `_flag_tags` resolution:

```python
pattern_tags = _pattern_tags(
    classifications,
    display_threshold=cfg.web.flag_pattern_display_threshold,
)
```

Pass `pattern_tags=pattern_tags` to the `WatchlistVM(...)` constructor.

Repeat the equivalent change in `swing/web/view_models/dashboard.py:build_dashboard`. (Locate the `pipeline_eval_id` block in build_dashboard at ~line 310 — confirm via grep — and apply the same pattern_run_id resolution + classifications load + pattern_tags compute.)

- [ ] **Step 3: Commit**

```bash
git add swing/web/view_models/watchlist.py swing/web/view_models/dashboard.py tests/web/view_models/test_watchlist_classifications_anchor.py
git commit -m "feat(web): build_watchlist + build_dashboard surface pattern_tags"
```

### Task 4.4 — `WatchlistRowVM` gains `pattern_tag`; `build_watchlist_row` populates it

Implements spec §3.5 for the compact-row collapse path.

**Files:**
- Modify: `swing/web/view_models/watchlist.py`

- [ ] **Step 1: Write failing test**

```python
def test_build_watchlist_row_returns_pattern_tag_when_classification_exists(tmp_path):
    pytest.skip(
        "Implementer: same harness as test_build_watchlist_uses_pipeline_run_id_*. "
        "Seed an active watchlist row for AAPL + a pipeline_pattern_classifications "
        "row with pattern='flag'. Call build_watchlist_row(ticker='AAPL'); assert "
        "row.pattern_tag == 'flag (0.78)'."
    )
```

- [ ] **Step 2: Modify `WatchlistRowVM`**

```python
@dataclass(frozen=True)
class WatchlistRowVM:
    w: WatchlistEntry
    price: PriceSnapshot | None
    tags: tuple[str, ...]
    pattern_tag: str | None = None
```

In `build_watchlist_row`, after `tags = _flag_tags(...).get(ticker, ())`, add:

```python
# Resolve pipeline_run_id same way build_watchlist does.
pipeline_run_id: int | None = None
if pipeline_eval_id is not None:
    pr = conn.execute(
        "SELECT id FROM pipeline_runs WHERE evaluation_run_id = ?",
        (pipeline_eval_id,),
    ).fetchone()
    pipeline_run_id = pr[0] if pr else None
pattern_tag: str | None = None
if pipeline_run_id is not None:
    cls = get_classification(conn, pipeline_run_id=pipeline_run_id, ticker=ticker)
    if (cls is not None and cls.pattern == "flag"
            and cls.confidence is not None
            and cls.confidence >= cfg.web.flag_pattern_display_threshold):
        pattern_tag = f"flag ({cls.confidence:.2f})"
```

Pass `pattern_tag=pattern_tag` to `WatchlistRowVM(...)`. (Note: this `pipeline_run_id` resolution sits OUTSIDE the existing `with conn:` block in current `build_watchlist_row` — refactor the block scope so the queries are inside the same transaction.)

- [ ] **Step 3: Commit**

```bash
git add swing/web/view_models/watchlist.py tests/web/view_models/test_pattern_tags.py
git commit -m "feat(web): WatchlistRowVM gains pattern_tag (compact-row collapse)"
```

### Task 4.5 — Sort-neutrality regression: behavioral parity-vector test

Implements spec §4.4 (R2 m2 fix — replaces brittle `inspect.getsource` source-stability check).

**Files:**
- Create: `tests/web/view_models/test_dashboard_sort_parity.py`

- [ ] **Step 1: Capture pre-Phase-4 baseline parity vector**

Build a frozen committed list of (rows, flag_tags, expected_order) tuples covering the existing pre-V1 sort cases. Lift fixture data from existing dashboard sort tests (`tests/web/view_models/test_dashboard_*.py`) — pick 5–8 representative cases.

```python
# tests/web/view_models/test_dashboard_sort_parity.py
"""Sort-neutrality regression: behavioral parity vector for _sort_watchlist.

Architectural guarantee (R1 M2 fix): _pattern_tags is a SIBLING to _flag_tags;
the flag tag never enters the `tags` tuple consumed by _sort_watchlist. This
test asserts the contract by replaying a fixed input/output vector through
_sort_watchlist after Phase 4 changes."""
import pytest
from swing.data.models import WatchlistEntry
from swing.web.view_models.dashboard import _sort_watchlist

# Each tuple: (label, list-of-(ticker, last_close, entry_target),
#             {ticker: tag-tuple}, expected order of tickers)
PARITY_VECTOR = [
    (
        "all-untagged-sort-by-proximity",
        [("AAA", 100.0, 110.0), ("BBB", 105.0, 110.0), ("CCC", 90.0, 110.0)],
        {},
        ["BBB", "CCC", "AAA"],  # closest first
    ),
    (
        "tag-count-beats-precedence",
        [("AAA", 100.0, 110.0), ("BBB", 100.0, 110.0)],
        {"AAA": ("TT✓",), "BBB": ("TT✓", "VCP✓")},
        ["BBB", "AAA"],  # 2 tags > 1 tag
    ),
    (
        "precedence-beats-proximity-on-equal-tag-count",
        [("AAA", 100.0, 110.0), ("BBB", 105.0, 110.0)],
        {"AAA": ("A+",), "BBB": ("TT✓",)},
        ["AAA", "BBB"],  # A+ (4) > TT (1)
    ),
    # Implementer: lift 3-5 more representative cases from existing
    # dashboard sort tests so the parity vector covers the existing
    # surface comprehensively.
]


def _entry(ticker: str, last_close: float, entry_target: float) -> WatchlistEntry:
    return WatchlistEntry(
        ticker=ticker, added_date="2026-04-01",
        last_qualified_date="2026-04-26", status="watch",
        qualification_count=1, not_qualified_streak=0,
        last_data_asof_date="2026-04-25",
        entry_target=entry_target, initial_stop_target=None,
        last_close=last_close, last_pivot=None, last_stop=None,
        last_adr_pct=None, missing_criteria=None, notes=None,
    )


@pytest.mark.parametrize("label,rows_data,flag_tags,expected_order", PARITY_VECTOR)
def test_sort_watchlist_byte_for_byte_parity(label, rows_data, flag_tags, expected_order):
    rows = [_entry(*r) for r in rows_data]
    sorted_rows = _sort_watchlist(rows, flag_tags)
    assert [r.ticker for r in sorted_rows] == expected_order, (
        f"Sort regression on case '{label}'."
    )
```

- [ ] **Step 2: Run, expect GREEN**

Phase 4 has not modified `_sort_watchlist`; the parity vector should already pass. Failing here means Phase 4 has accidentally touched the sort.

- [ ] **Step 3: Commit**

```bash
git add tests/web/view_models/test_dashboard_sort_parity.py
git commit -m "test(web): _sort_watchlist behavioral parity vector"
```

### Task 4.6 — Compounding-confound test (per 2026-04-26 lesson)

Implements spec §3.5 + §4.4 compounding-confound discipline.

**Files:**
- Modify: `tests/web/view_models/test_dashboard_sort_parity.py` (extend) OR new file.

- [ ] **Step 1: Write the test**

```python
def test_disabling_pattern_tags_does_not_change_sort_order(monkeypatch):
    """Compounding-confound: deleting the _pattern_tags call from a
    build_watchlist run must NOT change row order — only the rendered tag
    presence. If removing the call DOES change order, the architectural
    separation has regressed."""
    from swing.web.view_models import dashboard as dash_mod
    rows = [_entry("AAA", 100.0, 110.0), _entry("BBB", 105.0, 110.0)]
    flag_tags = {"AAA": ("TT✓",)}
    baseline = [r.ticker for r in _sort_watchlist(rows, flag_tags)]

    # Force _pattern_tags to return an empty mapping no matter what — i.e.,
    # the architectural disable. Sort must be unchanged.
    monkeypatch.setattr(dash_mod, "_pattern_tags", lambda *a, **k: {})
    after_disable = [r.ticker for r in _sort_watchlist(rows, flag_tags)]
    assert baseline == after_disable
```

- [ ] **Step 2: Run + commit**

```bash
git add tests/web/view_models/test_dashboard_sort_parity.py
git commit -m "test(web): compounding-confound — disabling _pattern_tags preserves sort"
```

### Task 4.7 — Template change: render flag tag in tags cell

Implements spec §3.5 template fragment.

**Files:**
- Modify: `swing/web/templates/partials/watchlist_row.html.j2`
- Modify: `swing/web/templates/watchlist.html.j2` (if needed to pass `pattern_tag` into row context)
- Modify: `swing/web/templates/partials/watchlist_top5_section.html.j2` (likewise)

- [ ] **Step 1: Locate `{% include "partials/watchlist_row.html.j2" %}` call sites and verify `pattern_tag` (or `pattern_tags`) is in scope**

```bash
grep -rn "watchlist_row\.html" swing/web/templates/
```

Both call sites loop over `vm.rows` and currently set up `tags = vm.flag_tags.get(w.ticker, ())` for each row. Both must also expose `pattern_tag = vm.pattern_tags.get(w.ticker)` (or `None`) into the include scope. Use Jinja's `with` block to avoid name collisions.

- [ ] **Step 2: Update `watchlist_top5_section.html.j2` and `watchlist.html.j2` to pass `pattern_tag` into the row include scope**

For each include, change from (current):

```jinja
{% include "partials/watchlist_row.html.j2" %}
```

to (with explicit binding):

```jinja
{% with tags=vm.flag_tags.get(w.ticker, ()), pattern_tag=vm.pattern_tags.get(w.ticker) %}
  {% include "partials/watchlist_row.html.j2" %}
{% endwith %}
```

(Confirm by reading the existing template what variable names are already in scope. If `tags` is already passed, the `with` block becomes additive.)

- [ ] **Step 3: Update `partials/watchlist_row.html.j2`**

Modify the tags cell:

```jinja
<td>
  {{ tags | join(' · ') }}
  {% if pattern_tag %}
    {% if tags %} · {% endif %}
    <span class="tag tag-pattern">{{ pattern_tag }}</span>
  {% endif %}
</td>
```

(Use the actual `·` middle-dot character — `·` is shown for documentation clarity.)

- [ ] **Step 4: Write a route-level rendering test**

```python
# tests/web/routes/test_watchlist_pattern_tag_render.py
def test_watchlist_top5_renders_flag_tag_for_classified_ticker(client):
    pytest.skip(
        "Implementer: seed DB with active watchlist + pipeline_run + "
        "classification(pattern='flag', confidence=0.78). GET /. Assert "
        "'flag (0.78)' appears in response body within the watchlist-top5 "
        "section."
    )
```

- [ ] **Step 5: Commit**

```bash
git add swing/web/templates/ tests/web/routes/test_watchlist_pattern_tag_render.py
git commit -m "feat(web): watchlist_row renders pattern_tag in separate <span>"
```

### Task 4.8 — Phase 4 checkpoint

- [ ] **Step 1: Run full fast suite + ruff**

```bash
python -m pytest -m "not slow" -q
ruff check swing/web/
```
Expected: green; no new ruff violations.

- [ ] **Step 2: Confirm `_sort_watchlist` byte-equal**

```bash
git diff <phase-4-baseline-sha>..HEAD -- swing/web/view_models/dashboard.py | grep -A2 -B2 "_sort_watchlist\|_TAG_PRECEDENCE\|_flag_tags"
```
Expected: zero diff lines inside any of those three constructs (only the new `_pattern_tags` helper appears as added).

---

# Phase 5 — Trade-entry form + CLI

**Pre-conditions:** Phase 4 green; classifications readable by ticker via `get_classification`.
**Scope:** `TradeEntryFormVM` gains four chart_pattern fields; `build_entry_form_vm` resolves cache row by `pipeline_run_id`; template renders algo display + override dropdown OR "Not classified" stub; POST handler reads form fields, builds `EntryRequest` with the resolved snapshot AS-IS (ToCToU-aware); `record_entry` persists snapshot, no re-resolve; CLI `--chart-pattern-operator` mirrors form with refusal gate when no cached classification.
**Phase-end checkpoint:** form posts route through to a persisted trade row carrying the snapshot; CLI refuses for out-of-scope tickers; mid-run pipeline completion between render and submit does NOT change persisted values vs operator's view.
**Spec sections:** §1.2 deliverables 5; §3.6 (form); §3.7 (CLI).

### Task 5.1 — `EntryRequest` gains 4 new fields + `record_entry` persists snapshot AS-IS

Implements spec §3.6 ToCToU fix (R2 M3 + R3 M1).

**Files:**
- Modify: `swing/trades/entry.py`
- Create: `tests/trades/test_entry_chart_pattern_snapshot.py`

- [ ] **Step 1: Write failing test for snapshot AS-IS persistence**

```python
# tests/trades/test_entry_chart_pattern_snapshot.py
from pathlib import Path
from swing.data.db import ensure_schema
from swing.data.repos.trades import get_trade
from swing.trades.entry import EntryRequest, record_entry


def test_record_entry_persists_chart_pattern_snapshot_as_is(tmp_path: Path):
    """ToCToU fix: record_entry persists what's passed in, NOT a fresh
    cache lookup. A pipeline run completing between render and submit
    cannot change the persisted values."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        req = EntryRequest(
            ticker="AAPL", entry_date="2026-04-26",
            entry_price=10.0, shares=1, initial_stop=9.0,
            watchlist_entry_target=None, watchlist_initial_stop=None,
            notes=None, rationale="aplus-setup",
            event_ts="2026-04-26T00:00:00",
            hypothesis_label=None,
            chart_pattern_operator=None,
            chart_pattern_algo="flag",
            chart_pattern_algo_confidence=0.78,
            chart_pattern_classification_pipeline_run_id=42,
        )
        result = record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
        t = get_trade(conn, result.trade_id)
        assert t.chart_pattern_algo == "flag"
        assert t.chart_pattern_algo_confidence == 0.78
        assert t.chart_pattern_classification_pipeline_run_id == 42
        assert t.chart_pattern_operator is None
    finally:
        conn.close()


def test_record_entry_canonicalizes_operator_label(tmp_path: Path):
    """Operator override goes through canonicalize_hypothesis_label
    (NFC + control-byte stripping). Spec §3.6."""
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        # Embed a zero-width-space + tab to verify they're stripped.
        req = EntryRequest(
            ticker="AAPL", entry_date="2026-04-26", entry_price=10.0,
            shares=1, initial_stop=9.0,
            watchlist_entry_target=None, watchlist_initial_stop=None,
            notes=None, rationale="aplus-setup",
            event_ts="ts", hypothesis_label=None,
            chart_pattern_operator="  flag​\t",
            chart_pattern_algo="flag", chart_pattern_algo_confidence=0.78,
            chart_pattern_classification_pipeline_run_id=42,
        )
        result = record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
        t = get_trade(conn, result.trade_id)
        assert t.chart_pattern_operator == "flag"  # canonicalized
    finally:
        conn.close()


def test_record_entry_refuses_invariant_violation_at_record_entry_layer(tmp_path: Path):
    """Form-tampering defense: if EntryRequest arrives with algo='flag'
    but confidence=None, the repo-layer ValueError fires from
    insert_trade_with_event (V1 enforcement)."""
    import pytest
    conn = ensure_schema(tmp_path / "swing.db")
    try:
        req = EntryRequest(
            ticker="AAPL", entry_date="2026-04-26", entry_price=10.0,
            shares=1, initial_stop=9.0,
            watchlist_entry_target=None, watchlist_initial_stop=None,
            notes=None, rationale="aplus-setup",
            event_ts="ts", hypothesis_label=None,
            chart_pattern_operator=None, chart_pattern_algo="flag",
            chart_pattern_algo_confidence=None,
            chart_pattern_classification_pipeline_run_id=42,
        )
        with pytest.raises(ValueError, match="chart_pattern"):
            record_entry(conn, req, soft_warn=10, hard_cap=20, force=False)
    finally:
        conn.close()
```

- [ ] **Step 2: Modify `EntryRequest` + `record_entry`**

```python
# swing/trades/entry.py
@dataclass(frozen=True)
class EntryRequest:
    ticker: str
    entry_date: str
    entry_price: float
    shares: int
    initial_stop: float
    watchlist_entry_target: float | None
    watchlist_initial_stop: float | None
    notes: str | None
    rationale: str
    event_ts: str
    hypothesis_label: str | None = None
    # Operator-override (canonicalized at record_entry boundary).
    chart_pattern_operator: str | None = None
    # Resolved-at-entry-surface classification snapshot — persisted AS-IS
    # by record_entry (no re-lookup). ToCToU fix per spec §3.6 (R2 M3 + R3 M1).
    chart_pattern_algo: str | None = None
    chart_pattern_algo_confidence: float | None = None
    chart_pattern_classification_pipeline_run_id: int | None = None
```

In `record_entry`, extend the `Trade(...)` construction:

```python
trade = Trade(
    id=None, ticker=req.ticker, entry_date=req.entry_date,
    entry_price=req.entry_price, initial_shares=req.shares,
    initial_stop=req.initial_stop, current_stop=req.initial_stop,
    status="open",
    watchlist_entry_target=req.watchlist_entry_target,
    watchlist_initial_stop=req.watchlist_initial_stop,
    notes=req.notes,
    hypothesis_label=canonicalize_hypothesis_label(req.hypothesis_label),
    chart_pattern_algo=req.chart_pattern_algo,
    chart_pattern_algo_confidence=req.chart_pattern_algo_confidence,
    chart_pattern_operator=canonicalize_hypothesis_label(req.chart_pattern_operator),
    chart_pattern_classification_pipeline_run_id=req.chart_pattern_classification_pipeline_run_id,
)
```

(Re-use `canonicalize_hypothesis_label` directly — its rules are identical to what spec §3.6 calls for. Future V2 may extract a `canonicalize_freetext_label` helper if other free-text fields show up.)

- [ ] **Step 3: Run + commit**

```bash
git add swing/trades/entry.py tests/trades/test_entry_chart_pattern_snapshot.py
git commit -m "feat(trades): EntryRequest carries chart_pattern snapshot; record_entry persists AS-IS"
```

### Task 5.2 — `TradeEntryFormVM` gains 4 chart_pattern fields; `build_entry_form_vm` resolves cache row

Implements spec §3.6.

**Files:**
- Modify: `swing/web/view_models/trades.py`
- Create: `tests/web/view_models/test_trade_entry_form_classification.py`

- [ ] **Step 1: Write failing test**

```python
# tests/web/view_models/test_trade_entry_form_classification.py
import pytest


def test_entry_form_vm_populates_chart_pattern_when_classification_exists(tmp_path):
    pytest.skip(
        "Implementer: seed pipeline_runs + classification('AAPL', 'flag', 0.78). "
        "Build the cfg/cache/executor harness used by other entry-form-VM tests. "
        "Call build_entry_form_vm(ticker='AAPL', ...). Assert vm.chart_pattern_algo "
        "== 'flag', vm.chart_pattern_algo_confidence == 0.78, "
        "vm.chart_pattern_algo_evaluated is True, "
        "vm.chart_pattern_classification_pipeline_run_id == <seeded run id>."
    )


def test_entry_form_vm_chart_pattern_evaluated_False_for_classifier_error(tmp_path):
    pytest.skip(
        "Implementer: seed classification('AAPL', pattern=None, confidence=NULL, "
        "components_json='{\"error\": \"...\"}'). Build VM. Assert "
        "vm.chart_pattern_algo_evaluated is False (classifier-error rows render "
        "the 'Not classified' stub, not the override dropdown)."
    )


def test_entry_form_vm_chart_pattern_evaluated_False_for_no_cache_row(tmp_path):
    pytest.skip(
        "Implementer: seed pipeline_run with NO classification row for AAPL. "
        "Build VM. Assert vm.chart_pattern_algo_evaluated is False."
    )
```

- [ ] **Step 2: Modify `TradeEntryFormVM`**

```python
@dataclass(frozen=True)
class TradeEntryFormVM:
    ticker: str
    entry_date: str
    entry_price: float
    initial_stop: float
    watchlist_entry_target: float | None
    watchlist_initial_stop: float | None
    suggested_shares: int
    risk_dollars: float
    risk_pct: float
    soft_warn_threshold: int
    hard_cap: int
    open_count: int
    force: bool = False
    rationale: str = ""
    notes: str = ""
    input_shares: int = 0
    rationale_options: tuple[tuple[str, str], ...] = ()
    # Chart-pattern algo display + override snapshot — spec §3.6.
    chart_pattern_algo: str | None = None
    chart_pattern_algo_confidence: float | None = None
    chart_pattern_algo_evaluated: bool = False
    chart_pattern_algo_computed_at: str | None = None
    chart_pattern_classification_pipeline_run_id: int | None = None
```

In `build_entry_form_vm`, after the existing watchlist/open-trade load, before `return TradeEntryFormVM(...)`, add:

```python
# Resolve pipeline_run_id same way build_watchlist does.
conn = connect(cfg.paths.db_path)
try:
    pipeline_eval_row = conn.execute(
        """SELECT evaluation_run_id FROM pipeline_runs
           WHERE state='complete' ORDER BY finished_ts DESC LIMIT 1"""
    ).fetchone()
    pipeline_eval_id = pipeline_eval_row[0] if pipeline_eval_row else None
    pipeline_run_id: int | None = None
    if pipeline_eval_id is not None:
        pr = conn.execute(
            "SELECT id FROM pipeline_runs WHERE evaluation_run_id = ?",
            (pipeline_eval_id,),
        ).fetchone()
        pipeline_run_id = pr[0] if pr else None
    cls = None
    if pipeline_run_id is not None:
        from swing.data.repos.pattern_classifications import get_classification
        cls = get_classification(conn, pipeline_run_id=pipeline_run_id, ticker=ticker)
finally:
    conn.close()

cp_algo: str | None = None
cp_conf: float | None = None
cp_evaluated = False
cp_computed_at: str | None = None
cp_anchor: int | None = None
if cls is not None and cls.pattern in ("flag", "none"):
    cp_algo = cls.pattern
    cp_conf = cls.confidence
    cp_evaluated = True
    cp_computed_at = cls.computed_at
    cp_anchor = cls.pipeline_run_id
# pattern is None (classifier error) or no row → cp_evaluated stays False.
```

Pass these into the VM constructor. (Combine with the existing `connect` block to avoid two connections; the example above shows it separately for clarity.)

- [ ] **Step 3: Commit**

```bash
git add swing/web/view_models/trades.py tests/web/view_models/test_trade_entry_form_classification.py
git commit -m "feat(web): TradeEntryFormVM + build_entry_form_vm load classification"
```

### Task 5.3 — Trade-entry form template: "Chart pattern" section

Implements spec §3.6 form fragment.

**Files:**
- Modify: `swing/web/templates/partials/trade_entry_form.html.j2`

- [ ] **Step 1: Write failing test for hidden inputs + dropdown**

```python
# tests/web/routes/test_trade_entry_chart_pattern.py
import pytest


def test_entry_form_renders_chart_pattern_section_when_evaluated(client):
    pytest.skip(
        "Implementer: seed classification('AAPL', 'flag', 0.78). "
        "GET /trades/entry/form?ticker=AAPL. Assert response body contains:\n"
        "  - input[type=hidden][name=chart_pattern_algo][value=flag]\n"
        "  - input[type=hidden][name=chart_pattern_algo_confidence][value=0.78]\n"
        "  - input[type=hidden][name=chart_pattern_classification_pipeline_run_id]\n"
        "  - select[name=chart_pattern_operator] with options "
        "    'Accept algo' / 'flag' / 'none' / 'other'\n"
        "  - text input for chart_pattern_operator_other (hidden until 'other' selected)"
    )


def test_entry_form_renders_not_classified_stub_when_unevaluated(client):
    pytest.skip(
        "Implementer: GET /trades/entry/form?ticker=NOPE (no classification). "
        "Assert response contains 'Not classified' stub text and DOES NOT "
        "contain a chart_pattern_operator <select>."
    )
```

- [ ] **Step 2: Edit the template**

Insert the "Chart pattern" section between the sizing-hint block and the rationale field:

```jinja
{% if vm.chart_pattern_algo_evaluated %}
<div class="chart-pattern-section">
  <label>Chart pattern (algo)</label>
  <div>
    {% if vm.chart_pattern_algo == 'flag' %}
      <strong>flag</strong> ({{ '%.2f' | format(vm.chart_pattern_algo_confidence) }})
    {% else %}
      <em>none</em>
    {% endif %}
    {% if vm.chart_pattern_algo_computed_at %}
      <span class="subtitle">from pipeline run {{ vm.chart_pattern_algo_computed_at }}</span>
    {% endif %}
  </div>
  <input type="hidden" name="chart_pattern_algo" value="{{ vm.chart_pattern_algo or '' }}">
  <input type="hidden" name="chart_pattern_algo_confidence"
         value="{{ vm.chart_pattern_algo_confidence if vm.chart_pattern_algo_confidence is not none else '' }}">
  <input type="hidden" name="chart_pattern_classification_pipeline_run_id"
         value="{{ vm.chart_pattern_classification_pipeline_run_id if vm.chart_pattern_classification_pipeline_run_id is not none else '' }}">
  <label>Operator override</label>
  <select name="chart_pattern_operator"
          onchange="var h=this.form.querySelector('.cp-other-input');
                    if(h){h.style.display=(this.value==='other')?'inline':'none';}">
    <option value="">Accept algo</option>
    <option value="flag">flag</option>
    <option value="none">none</option>
    <option value="other">other (specify)</option>
  </select>
  <input type="text" name="chart_pattern_operator_other"
         class="cp-other-input" style="display:none" placeholder="other label">
</div>
{% else %}
<div class="chart-pattern-section">
  <label>Chart pattern (algo)</label>
  <div class="subtitle">Not classified (out-of-scope or no recent pipeline run).</div>
</div>
{% endif %}
```

- [ ] **Step 3: Commit**

```bash
git add swing/web/templates/partials/trade_entry_form.html.j2 tests/web/routes/test_trade_entry_chart_pattern.py
git commit -m "feat(web): trade_entry_form Chart pattern section + hidden snapshot inputs"
```

### Task 5.4 — POST `/trades/entry` reads new form fields + builds `EntryRequest` with snapshot

Implements spec §3.6.

**Files:**
- Modify: `swing/web/routes/trades.py`

- [ ] **Step 1: Write failing test (E2E POST → trade row)**

```python
def test_post_entry_with_chart_pattern_override_persists(client):
    pytest.skip(
        "Implementer: seed classification('AAPL', 'flag', 0.78, run_id=42). "
        "POST /trades/entry with form fields including:\n"
        "  chart_pattern_algo=flag, chart_pattern_algo_confidence=0.78,\n"
        "  chart_pattern_classification_pipeline_run_id=42,\n"
        "  chart_pattern_operator=flag\n"
        "Assert response 200; query DB for the new trade; assert "
        "chart_pattern_algo='flag', chart_pattern_algo_confidence=0.78, "
        "chart_pattern_operator='flag', "
        "chart_pattern_classification_pipeline_run_id=42."
    )


def test_post_entry_with_accept_algo_persists_NULL_operator(client):
    pytest.skip(
        "Implementer: same as above but submit chart_pattern_operator='' "
        "(Accept algo). Assert trade row's chart_pattern_operator IS NULL."
    )


def test_post_entry_other_with_text_canonicalizes(client):
    pytest.skip(
        "Implementer: submit chart_pattern_operator=other, "
        "chart_pattern_operator_other='  pennant​\\t  '. "
        "Assert trade row's chart_pattern_operator == 'pennant' (canonicalized)."
    )
```

- [ ] **Step 2: Modify `entry_post` in `swing/web/routes/trades.py:213`**

Add the new `Form` parameters and thread them into `EntryRequest`:

```python
@router.post("/trades/entry", response_class=HTMLResponse)
def entry_post(
    request: Request,
    ticker: str = Form(...),
    entry_date: str = Form(...),
    entry_price: float = Form(...),
    shares: int = Form(...),
    initial_stop: float = Form(...),
    rationale: str = Form(...),
    notes: str | None = Form(None),
    watchlist_target: float | None = Form(None),
    watchlist_stop: float | None = Form(None),
    force: str | None = Form(None),
    chart_pattern_algo: str | None = Form(None),
    chart_pattern_algo_confidence: float | None = Form(None),
    chart_pattern_classification_pipeline_run_id: int | None = Form(None),
    chart_pattern_operator: str | None = Form(None),
    chart_pattern_operator_other: str | None = Form(None),
):
    # ... existing validation unchanged ...

    # Resolve operator override: 'other' → use the free-text input;
    # empty string ('Accept algo') → None.
    if chart_pattern_operator == "other":
        cp_operator_value = chart_pattern_operator_other or None
    else:
        cp_operator_value = chart_pattern_operator or None

    # Empty-string Form values from hidden fields when classification absent
    # arrive as '' (not None). Coerce to None for the dataclass.
    cp_algo_value = chart_pattern_algo or None
    cp_conf_value = chart_pattern_algo_confidence  # already typed float|None
    cp_anchor_value = chart_pattern_classification_pipeline_run_id

    req = EntryRequest(
        ticker=ticker.upper(),
        entry_date=entry_date,
        entry_price=entry_price,
        shares=shares,
        initial_stop=initial_stop,
        watchlist_entry_target=watchlist_target,
        watchlist_initial_stop=watchlist_stop,
        notes=notes,
        rationale=rationale,
        event_ts=datetime.now().isoformat(timespec="seconds"),
        chart_pattern_operator=cp_operator_value,
        chart_pattern_algo=cp_algo_value,
        chart_pattern_algo_confidence=cp_conf_value,
        chart_pattern_classification_pipeline_run_id=cp_anchor_value,
    )
    # ... rest of body unchanged ...
```

`record_entry` already raises `ValueError` from `_validate_chart_pattern_invariant` if the form-tampering case fires; current 400-handler may need to be extended to catch this. Add a `try/except ValueError` around `record_entry(...)` only for the chart_pattern messages (re-raise others) and re-render the form with an error banner. Match the existing duplicate/soft-warn re-render pattern.

- [ ] **Step 3: Commit**

```bash
git add swing/web/routes/trades.py tests/web/routes/test_trade_entry_chart_pattern.py
git commit -m "feat(web): POST /trades/entry reads chart_pattern snapshot + override"
```

### Task 5.5 — CLI `--chart-pattern-operator` + refusal gate

Implements spec §3.7 (R1 C1 CLI parity gate).

**Files:**
- Modify: `swing/cli.py`
- Create: `tests/test_cli_trade_entry_chart_pattern.py`

- [ ] **Step 1: Write failing CLI tests**

```python
# tests/test_cli_trade_entry_chart_pattern.py
import pytest
from click.testing import CliRunner

from swing.cli import cli


def test_cli_trade_entry_chart_pattern_operator_refused_without_cache(tmp_path):
    pytest.skip(
        "Implementer: build the cfg fixture pattern used by other CLI tests "
        "(initialized DB at tmp_path). DO NOT seed any classification row. "
        "Run `swing trade entry --ticker AAPL ... --chart-pattern-operator flag`. "
        "Assert exit_code != 0; result.output contains "
        "'requires a cached classification' or similar refusal message."
    )


def test_cli_trade_entry_chart_pattern_operator_persists_when_cached(tmp_path):
    pytest.skip(
        "Implementer: seed classification('AAPL', 'flag', 0.78, run_id=42). "
        "Run `swing trade entry --ticker AAPL ... --chart-pattern-operator flag`. "
        "Assert exit_code == 0; query DB for the trade; assert "
        "chart_pattern_operator='flag', chart_pattern_algo='flag', "
        "chart_pattern_algo_confidence=0.78, "
        "chart_pattern_classification_pipeline_run_id=42."
    )


def test_cli_trade_entry_no_chart_pattern_flag_omitted_works(tmp_path):
    pytest.skip(
        "Backward-compat: existing CLI invocations without "
        "--chart-pattern-operator must still succeed. Assert trade row's "
        "chart_pattern_operator IS NULL; algo+confidence+anchor surface "
        "from the cached classification (or NULL if no cache)."
    )
```

- [ ] **Step 2: Modify `swing/cli.py:trade_entry_cmd`**

```python
@click.option("--chart-pattern-operator", default=None,
              help="Operator override for chart pattern. Free text per "
                   "locked-constraint #6 (canonicalized at persistence). "
                   "Refused if ticker has no cached classification "
                   "(V1 cached-only; manual fallback deferred to V2).")
@click.pass_context
def trade_entry_cmd(ctx, ticker, entry_date, entry_price, shares, initial_stop,
                    watchlist_target, watchlist_stop, rationale, notes,
                    hypothesis, chart_pattern_operator, force):
    # ... existing body up to the existing connect(cfg.paths.db_path) ...

    # Chart-pattern resolution at command start (entry-surface ONCE, then
    # snapshot persisted AS-IS by record_entry — spec §3.6 ToCToU fix).
    cp_algo: str | None = None
    cp_conf: float | None = None
    cp_anchor: int | None = None
    cp_evaluated = False
    pipeline_eval_row = conn.execute(
        """SELECT evaluation_run_id FROM pipeline_runs
           WHERE state='complete' ORDER BY finished_ts DESC LIMIT 1"""
    ).fetchone()
    if pipeline_eval_row is not None and pipeline_eval_row[0] is not None:
        pr = conn.execute(
            "SELECT id FROM pipeline_runs WHERE evaluation_run_id = ?",
            (pipeline_eval_row[0],),
        ).fetchone()
        if pr is not None:
            from swing.data.repos.pattern_classifications import get_classification
            cls = get_classification(
                conn, pipeline_run_id=pr[0], ticker=ticker.upper(),
            )
            if cls is not None and cls.pattern in ("flag", "none"):
                cp_algo = cls.pattern
                cp_conf = cls.confidence
                cp_anchor = cls.pipeline_run_id
                cp_evaluated = True

    # CLI parity gate: refuse --chart-pattern-operator when no cache row
    # (or only a classifier-error row) exists for this ticker.
    if chart_pattern_operator is not None and not cp_evaluated:
        raise click.ClickException(
            f"--chart-pattern-operator requires a cached classification for "
            f"{ticker.upper()}; ticker is out-of-scope for the latest "
            f"pipeline run. (V1 cached-only; manual fallback deferred to V2.)"
        )

    # ... existing hypothesis pre-fill block unchanged ...

    req = EntryRequest(
        ticker=ticker.upper(), entry_date=entry_date, entry_price=entry_price,
        shares=shares, initial_stop=initial_stop,
        watchlist_entry_target=watchlist_target,
        watchlist_initial_stop=watchlist_stop,
        notes=notes, rationale=rationale,
        event_ts=_dt.now().isoformat(timespec="seconds"),
        hypothesis_label=hypothesis,
        chart_pattern_operator=chart_pattern_operator,
        chart_pattern_algo=cp_algo,
        chart_pattern_algo_confidence=cp_conf,
        chart_pattern_classification_pipeline_run_id=cp_anchor,
    )
    # ... rest of existing body unchanged ...
```

- [ ] **Step 3: Commit**

```bash
git add swing/cli.py tests/test_cli_trade_entry_chart_pattern.py
git commit -m "feat(cli): trade entry --chart-pattern-operator with cached-only refusal gate"
```

### Task 5.6 — Phase 5 checkpoint

- [ ] **Step 1: Run full fast suite + ruff**

```bash
python -m pytest -m "not slow" -q
ruff check swing/cli.py swing/web/ swing/trades/ swing/config.py
```
Expected: green; no new ruff violations.

- [ ] **Step 2: Confirm CLI + form parity**

Both surfaces must refuse `chart_pattern_operator` when no cached classification (or only a classifier-error row) exists. Manual smoke check via:
- `swing trade entry --ticker XYZ --chart-pattern-operator flag --rationale aplus-setup ...` (no classification → refuses).
- POST `/trades/entry` with hidden-input chart_pattern_algo='' → record_entry's invariant fires if `chart_pattern_operator` is provided AND repo-layer ValueError triggers (the form-side check must reject before reaching record_entry; if it doesn't, file as a Phase 5 follow-up — but the repo-layer ValueError is the safety net).

---

# Phase 6 — Chart overlay painting

**Pre-conditions:** Phase 3 green; `render_chart` accepts `pattern_overlay` kwarg as no-op.
**Scope:** When `pattern_overlay` is non-None, paint pole/flag colored bands + algo-pivot horizontal segment (spanning flag region only) + title annotation. Existing candidate-pivot hline preserved (separate hline from algo-pivot).
**Phase-end checkpoint:** smoke test producing a PNG with overlay; existing `render_chart` regression test green; `pattern_overlay=None` produces byte-equivalent (or smoke-equivalent) PNG to pre-Phase-6 code.
**Spec sections:** §1.2 deliverable 6; §3.4.

### Task 6.1 — Paint pole + flag bands via `fill_betweenx` + algo-pivot segment + title annotation

Implements spec §3.4 painting.

**Files:**
- Modify: `swing/rendering/charts.py`
- Modify: `tests/rendering/test_chart_overlay.py`

- [ ] **Step 1: Write failing painting test**

Add to `tests/rendering/test_chart_overlay.py`:

```python
from datetime import date


def test_render_chart_with_pattern_overlay_writes_png_and_preserves_existing_hlines(
    tmp_path: Path, fake_ohlcv,
):
    """Smoke test: with overlay, the function still returns the path and
    writes a non-empty PNG. Detailed visual checks are deferred to slow
    tests; this guards against accidental crash paths."""
    from swing.rendering.charts import render_chart, PatternOverlay
    overlay = PatternOverlay(
        pattern="flag", confidence=0.78,
        pole_start_date=fake_ohlcv.index[80].date(),
        pole_end_date=fake_ohlcv.index[100].date(),
        flag_start_date=fake_ohlcv.index[101].date(),
        flag_end_date=fake_ohlcv.index[119].date(),
        pivot=120.0,
    )
    out = tmp_path / "AAPL.png"
    res = render_chart(
        ticker="AAPL", ohlcv=fake_ohlcv, pivot=110.0, stop=95.0,
        output_path=out, pattern_overlay=overlay,
    )
    assert res == out
    assert out.exists()
    assert out.stat().st_size > 0
```

- [ ] **Step 2: Implement painting**

Modify `render_chart` to call `mpf.plot(..., returnfig=True)` only when `pattern_overlay` is non-None, then paint via the returned `(fig, axes)` tuple, then save manually. When `pattern_overlay is None`, preserve the existing `mpf.plot(..., savefig=...)` flow (no axes-level painting → exact same output).

```python
def render_chart(
    *, ticker: str, ohlcv: pd.DataFrame, pivot: float, stop: float,
    output_path: Path,
    pattern_overlay: "PatternOverlay | None" = None,
) -> Path | None:
    try:
        import mplfinance as mpf
    except ImportError as exc:
        raise ChartingUnavailable("mplfinance not installed") from exc

    df = ohlcv.tail(CHART_LOOKBACK_DAYS).copy()
    if len(df) < MIN_BARS:
        return None

    addplots = []
    closes = df["Close"]
    for window, color in ((10, "blue"), (20, "orange"), (50, "red")):
        sma = closes.rolling(window).mean()
        if not sma.isna().all():
            addplots.append(mpf.make_addplot(sma, color=color, width=1.0))

    output_path.parent.mkdir(parents=True, exist_ok=True)

    title = f"{ticker} | pivot ${pivot:.2f} stop ${stop:.2f} | last {len(df)} bars"
    if pattern_overlay is not None:
        title += f" | flag ({pattern_overlay.confidence:.2f})"

    plot_kwargs = dict(
        type="candle", volume=True, style="yahoo",
        figsize=(11, 6),
        title=title,
        ylabel_lower="Volume",
        addplot=addplots,
        hlines=dict(hlines=[pivot, stop], colors=["green", "red"], linestyle="--"),
        vlines=dict(vlines=[df.index[-CONSOLIDATION_DAYS]],
                    colors=["purple"], linestyle=":", alpha=0.5),
    )

    if pattern_overlay is None:
        mpf.plot(df, savefig=dict(fname=str(output_path), dpi=100, bbox_inches="tight"),
                 **plot_kwargs)
        return output_path

    fig, axes = mpf.plot(df, returnfig=True, **plot_kwargs)
    price_ax = axes[0]
    # Convert overlay dates to matplotlib x-coords using df.index.
    def _idx_for(d):
        # Find the first index >= d; falls back to last bar if d > last.
        match = df.index[df.index.date >= d]
        return match[0] if len(match) else df.index[-1]
    pole_start_x = _idx_for(pattern_overlay.pole_start_date)
    pole_end_x = _idx_for(pattern_overlay.pole_end_date)
    flag_start_x = _idx_for(pattern_overlay.flag_start_date)
    flag_end_x = _idx_for(pattern_overlay.flag_end_date)
    # Pole band — faint green.
    price_ax.axvspan(pole_start_x, pole_end_x, alpha=0.15, color="green")
    # Flag band — faint yellow.
    price_ax.axvspan(flag_start_x, flag_end_x, alpha=0.15, color="yellow")
    # Algo-pivot horizontal segment — only spans flag region.
    price_ax.hlines(
        y=pattern_overlay.pivot, xmin=flag_start_x, xmax=flag_end_x,
        colors="darkblue", linestyles="-", linewidth=1.5,
    )
    fig.savefig(str(output_path), dpi=100, bbox_inches="tight")
    import matplotlib.pyplot as plt
    plt.close(fig)
    return output_path
```

(If matplotlib's `axvspan` complains about the index being a `Timestamp`, fall back to numeric x indices via `df.index.get_indexer([...])`.)

- [ ] **Step 3: Run + commit**

```bash
git add swing/rendering/charts.py tests/rendering/test_chart_overlay.py
git commit -m "feat(rendering): paint pole/flag bands + algo-pivot segment + title annotation"
```

### Task 6.2 — Phase 6 checkpoint

- [ ] **Step 1: Run full fast suite + ruff**

```bash
python -m pytest -m "not slow" -q
ruff check swing/rendering/
```
Expected: green; no new ruff violations.

- [ ] **Step 2: Manual visual sanity** (optional)

Hand-render a known flag fixture (operator-labeled, from Phase 7) and visually verify the pole/flag bands + algo-pivot segment paint sensibly. If the overlay looks wrong, the algorithm OR the painting is wrong — adjust before declaring Phase 6 complete.

---

# Phase 7 — Integration test suite (≥15 operator-labeled fixtures)

**Pre-conditions:** Phases 1–6 green.
**Scope:** Test runner + fixture-loading helper. ≥15 operator-labeled OHLCV fixtures (8 flags + 7 non-flags spanning the rejection cases enumerated in spec §1.2 Q2). FP-biased tuning gate at end.
**Operator-only sub-task:** the labeled FIXTURES themselves. Implementer cannot fabricate labels per spec §4.2.
**Phase-end checkpoint:** runner + helper landed; ≥15 fixtures committed (operator-driven); all integration tests pass.

### Task 7.1 — Fixture directory + labeling protocol README

Implements spec §4.2 procedure.

**Files:**
- Create: `tests/evaluation/patterns/fixtures/README.md`
- Create: `tests/evaluation/patterns/fixtures/.gitkeep`

- [ ] **Step 1: Author the README**

The README documents the labeling protocol (operator is sole labeler, rubric, procedure, immutability rule, retire-and-replace policy). Reproduce spec §4.2 verbatim into the README so future operators can re-read it standalone. Commit the README + `.gitkeep` so the directory exists in the repo.

- [ ] **Step 2: Commit**

```bash
git add tests/evaluation/patterns/fixtures/
git commit -m "docs(tests): chart-pattern fixture labeling protocol README"
```

### Task 7.2 — Fixture-loading helper + parametrized integration test

Implements spec §4.2 test.

**Files:**
- Create: `tests/evaluation/patterns/_fixtures.py`
- Create: `tests/evaluation/patterns/test_flag_classifier_integration.py`

- [ ] **Step 1: Write the loader + test**

```python
# tests/evaluation/patterns/_fixtures.py
from __future__ import annotations
from dataclasses import dataclass
from pathlib import Path
import json
import pandas as pd

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class LabeledFixture:
    ticker: str
    end_date: str
    label: str               # 'flag' | 'none'
    csv_path: Path
    json_path: Path
    metadata: dict


def list_labeled_fixtures() -> list[LabeledFixture]:
    """Discover (TICKER_YYYY-MM-DD_label).csv + .json pairs in fixtures/."""
    out: list[LabeledFixture] = []
    for csv_path in sorted(FIXTURES_DIR.glob("*.csv")):
        json_path = csv_path.with_suffix(".json")
        if not json_path.exists():
            continue
        # Expect filename: <TICKER>_<YYYY-MM-DD>_<label>.csv
        parts = csv_path.stem.split("_")
        if len(parts) < 3:
            continue
        ticker = parts[0]
        end_date = parts[1]
        label = parts[2]
        meta = json.loads(json_path.read_text())
        out.append(LabeledFixture(
            ticker=ticker, end_date=end_date, label=label,
            csv_path=csv_path, json_path=json_path, metadata=meta,
        ))
    return out


def load_fixture_bars(fixture: LabeledFixture) -> pd.DataFrame:
    """Load 60-bar yfinance-shaped DataFrame (Open/High/Low/Close/Volume)."""
    df = pd.read_csv(fixture.csv_path, parse_dates=["Date"], index_col="Date")
    return df
```

```python
# tests/evaluation/patterns/test_flag_classifier_integration.py
"""Operator-labeled integration tests. Spec §4.2.

Fixtures live in fixtures/. The OPERATOR is the sole labeler — implementer
cannot fabricate labels. Each test is parametrized over discovered fixtures."""
import pytest

from swing.evaluation.patterns.flag_classifier import classify_flag
from tests.evaluation.patterns._fixtures import (
    list_labeled_fixtures, load_fixture_bars,
)


_FIXTURES = list_labeled_fixtures()


@pytest.mark.skipif(len(_FIXTURES) < 15,
                    reason="Spec §4.2 requires ≥15 operator-labeled fixtures.")
@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda f: f.csv_path.stem)
def test_classifier_against_labeled_fixture(fixture):
    bars = load_fixture_bars(fixture)
    res = classify_flag(bars)
    if fixture.label == "flag":
        assert res.detected, f"{fixture.ticker} {fixture.end_date}: expected flag, got pattern={res.pattern}"
        if "expected_confidence_min" in fixture.metadata:
            assert res.confidence >= fixture.metadata["expected_confidence_min"]
    else:
        assert not res.detected, f"{fixture.ticker} {fixture.end_date}: expected non-flag, got detected={res.detected} confidence={res.confidence}"
```

- [ ] **Step 2: Commit**

```bash
git add tests/evaluation/patterns/_fixtures.py tests/evaluation/patterns/test_flag_classifier_integration.py
git commit -m "feat(tests): chart-pattern integration test runner + fixture loader"
```

### Task 7.3 — OPERATOR-ONLY: label and commit ≥15 fixtures

Implements spec §4.2 fixtures. Per §4.2:
- **Labeler:** operator (Reid Smythe). Implementer CANNOT fabricate.
- **Procedure:** operator picks (ticker, end-date) pairs; literal yfinance pull → 60-bar window; saves CSV + JSON to `tests/evaluation/patterns/fixtures/`.
- **Floor:** ≥15 = 8 flags + 7 non-flags spanning rejection cases (wide-and-loose, deep base/cup, sideways drift with no pole, late-stage failed breakout, stage-4 with bounce, multi-month flat base, ambiguous edge case).
- **Immutability:** never edit-in-place; retire-and-replace if a label changes.

The plan does NOT prescribe which tickers; that's an operator choice. The plan DOES require the count and rejection-case coverage. This task is gated behind operator session availability.

- [ ] **Step 1: Operator labels and commits 8 flag fixtures**

For each: yfinance pull, save as `<TICKER>_<YYYY-MM-DD>_flag.csv` (literal data — no hand-edit) and `<TICKER>_<YYYY-MM-DD>_flag.json` with `{"label": "flag", "notes": "<why>", "expected_confidence_min": <optional float>}`.

```bash
git add tests/evaluation/patterns/fixtures/<file>.csv tests/evaluation/patterns/fixtures/<file>.json
git commit -m "test(patterns): add labeled flag fixture <TICKER>_<DATE>"
```

(One commit per fixture or one batch — operator's choice.)

- [ ] **Step 2: Operator labels and commits 7 non-flag fixtures**

Cover the seven rejection cases enumerated in spec §1.2 Q2. Same filename convention; `"label": "none"` and `"notes"` describing which gate the operator expects to fail.

- [ ] **Step 3: Run integration suite**

```bash
python -m pytest tests/evaluation/patterns/test_flag_classifier_integration.py -v
```

If FAIL: classify each failure as FP (algo says flag, operator labeled none) or FN (algo says none, operator labeled flag). Tally. Per spec §3.1.4 FP-bias: if FP > FN at default thresholds, tighten — operator-decision call.

- [ ] **Step 4: Decision: tune defaults OR retire mislabeled fixtures**

If a failure traces to the operator's eye changing on re-review (genuine relabel), retire-and-replace per §4.2 immutability rule. If failures cluster (e.g., all FPs share `pole_gain` clearance < 0.1), tighten `cfg.classifier.flag_pole_gain_min` from 0.30 → e.g., 0.35. Document the chosen defaults in `docs/orchestrator-context.md` recent-decisions per spec §7 step 5.

### Task 7.4 — Phase 7 checkpoint

- [ ] **Step 1: Run full fast suite + ruff**

```bash
python -m pytest -m "not slow" -q
ruff check swing/
```
Expected: green; ≥15 fixtures present; integration tests all pass; no new ruff violations.

- [ ] **Step 2: Confirm spec §9 done criteria**

Walk spec §9 Done criteria. Each must point at a passing test or a verifiable behavior in the codebase.

---

# Phase 2 carve-outs (CLAUDE.md isolation enforcement)

Files in `swing/data/` and `swing/trades/` modified by this plan, with justification per CLAUDE.md "during Phase 3 work, `swing/trades/` and `swing/data/` are read-only unless an explicit carve-out is granted in the brief":

| # | File | Phase | Action | Justification |
|---|---|---|---|---|
| 1 | `swing/data/db.py` | 2 | MODIFY (constant bump) | `EXPECTED_SCHEMA_VERSION` 8→10 so `ensure_schema` applies migrations 0009 + 0010. Single-line constant change. |
| 2 | `swing/data/migrations/0009_pipeline_pattern_classifications.sql` | 2 | NEW | Spec §3.2.1 — pipeline-time pattern cache table. Fresh CREATE; row-level CHECK constraint enforced at schema layer (free with new table). |
| 3 | `swing/data/migrations/0010_trade_chart_pattern.sql` | 2 | NEW | Spec §3.2.2 — four columns on `trades` for per-trade encoding + audit anchor. ALTER-only; cross-column invariant deferred to repo layer (V2 hardening bundles trade-table rebuild). |
| 4 | `swing/data/models.py` | 2 | MODIFY | `Trade` gains 4 trailing-default fields (mirrors `hypothesis_label` precedent at `models.py:69`). New `PipelinePatternClassification` dataclass. |
| 5 | `swing/data/repos/pattern_classifications.py` | 2 | NEW | Spec §3.2.3 — data-access for the new cache table. Isolated module; does not touch trades repo. |
| 6 | `swing/data/repos/trades.py` | 2 | MODIFY | `insert_trade_with_event` writes 4 new columns + `_validate_chart_pattern_invariant`. Six SELECT statements thread 4 new columns; `_row_to_trade` consumes them. Repo-layer cross-column invariant (R2 M2). |
| 7 | `swing/trades/entry.py` | 5 | MODIFY | `EntryRequest` gains 4 fields (operator + resolved-at-surface snapshot). `record_entry` persists snapshot AS-IS; canonicalizes operator label via `canonicalize_hypothesis_label`. ToCToU fix per spec §3.6. |

All other modifications are within Phase 3 territory or new modules; no further carve-outs needed.

---

# Out-of-V1 scope (per spec §1.3 — plan must NOT include)

- Patterns beyond `flag` (pennant, base, cup-with-handle).
- Manual-trade fallback for out-of-chart-scope tickers.
- ML / LLM / hybrid classifiers.
- Multi-timeframe analysis.
- Real-time / intraday classification.
- Sort-PARTICIPATING flag tag.
- `_sort_watchlist` / `_TAG_PRECEDENCE` modification.
- Any change to `swing/evaluation/scoring.py`, `swing/recommendations/`, or `bucket_for`.
- Layer-3 slow tests (live yfinance refresh) — deferred to backlog per spec §4.3.
- Schema-layer cross-column CHECK on `trades` (V2 — bundle with next trade-table rebuild).
- Operator-facing classifier-error count surface (V2 dashboard banner).

---

# References

- Spec: `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`
- Brief: `docs/phase3e-chart-pattern-writing-plans-brief.md`
- CLAUDE.md gotchas (root)
- Hypothesis-label precedent: `swing/data/migrations/0007_trade_hypothesis_label.sql`, `swing/data/models.py:69`
- Existing `_step_charts`: `swing/pipeline/runner.py:535-628`
- Existing sort architecture: `swing/web/view_models/dashboard.py:610-673` (TOUCHED ZERO BYTES IN THIS PLAN)
- Existing chart renderer: `swing/rendering/charts.py`
