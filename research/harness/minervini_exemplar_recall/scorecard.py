# research/harness/minervini_exemplar_recall/scorecard.py
from __future__ import annotations

import math
import random
from dataclasses import dataclass
from typing import Callable, Sequence

_SURFACED = {"surfaced_aplus", "surfaced_watch"}
_ATTRITION = {"skip_insufficient_history", "no_data"}


@dataclass(frozen=True)
class WilsonInterval:
    lower: float
    upper: float
    p_hat: float
    n: int


@dataclass(frozen=True)
class BootstrapInterval:
    lower: float
    upper: float
    b: int


def wilson_interval(successes: int, n: int, z: float = 1.96) -> WilsonInterval:
    if n == 0:
        return WilsonInterval(0.0, 1.0, 0.0, 0)
    p = successes / n
    z2 = z * z
    denom = 1.0 + z2 / n
    center = (p + z2 / (2 * n)) / denom
    half = (z * math.sqrt(p * (1 - p) / n + z2 / (4 * n * n))) / denom
    return WilsonInterval(lower=center - half, upper=center + half, p_hat=p, n=n)


def _clustered_resample(rng: random.Random, by_ticker: dict[str, list]) -> list:
    tickers = sorted(by_ticker)
    drawn = [rng.choice(tickers) for _ in tickers]
    rows: list = []
    for t in drawn:
        rows.extend(by_ticker[t])  # whole ticker's rows move together
    return rows


def _percentile(values: list[float], q: float) -> float:
    if not values:
        return 0.0
    s = sorted(values)
    idx = q / 100.0 * (len(s) - 1)
    lo = int(math.floor(idx))
    hi = int(math.ceil(idx))
    if lo == hi:
        return s[lo]
    return s[lo] + (s[hi] - s[lo]) * (idx - lo)


def ticker_clustered_bootstrap(
    rows: Sequence[tuple], value_fn: Callable[[Sequence[tuple]], float], *, b: int, base_seed: int
) -> BootstrapInterval:
    by_ticker: dict[str, list] = {}
    for row in rows:
        by_ticker.setdefault(row[0], []).append(row)
    rng = random.Random(base_seed)
    stats = [value_fn(_clustered_resample(rng, by_ticker)) for _ in range(b)]
    return BootstrapInterval(lower=_percentile(stats, 2.5), upper=_percentile(stats, 97.5), b=b)


def screening_recall(outcomes: Sequence[str]) -> tuple[float, float]:
    """Returns (full_set_recall, screenable_subset_recall)."""
    n_total = len(outcomes)
    surfaced = sum(1 for o in outcomes if o in _SURFACED)
    screenable = sum(1 for o in outcomes if o not in _ATTRITION)
    full = surfaced / n_total if n_total else 0.0
    sub = surfaced / screenable if screenable else 0.0
    return full, sub


# --- aggregate (appended to research/harness/minervini_exemplar_recall/scorecard.py) ---
from collections import Counter


@dataclass(frozen=True)
class ExemplarSummary:
    exemplar_id: str
    ticker: str
    detector_class: str
    h1_outcome: str
    first_rejecting_gate: str | None
    h2_faithful_fired_expected: bool | None  # None for unmapped
    h2_isolated_fired_expected: bool | None
    gate_passes: dict[str, bool] | None = None  # per-gate pass at the representative screenable session


@dataclass(frozen=True)
class ControlSummary:
    ticker: str
    detector_class: str
    surfaced: bool
    fired_faithful: bool
    fired_isolated: bool


@dataclass(frozen=True)
class DetectorRecall:
    per_class_faithful: dict[str, tuple[int, int]]
    per_class_isolated: dict[str, tuple[int, int]]
    overall_faithful: tuple[int, int]
    overall_isolated: tuple[int, int]
    stage2_delta: dict[str, float]


@dataclass(frozen=True)
class Scorecard:
    mode: str
    bucket_distribution: dict[str, int]
    screening_recall_full: float
    screening_recall_screenable: float
    screening_wilson_screenable: WilsonInterval
    screening_bootstrap_screenable: BootstrapInterval
    gate_attribution_hist: dict[str, int]
    per_gate_pass_rate_screenable: dict[str, float]
    detector_recall: DetectorRecall
    specificity_contrast: dict[str, float]


def _rate(num: int, den: int) -> float:
    return num / den if den else 0.0


def _detector_recall(exemplars: list[ExemplarSummary]) -> DetectorRecall:
    classes = sorted({e.detector_class for e in exemplars if e.detector_class != "unmapped"})
    per_f: dict[str, tuple[int, int]] = {}
    per_i: dict[str, tuple[int, int]] = {}
    delta: dict[str, float] = {}
    of_f = oi_f = of_i = oi_i = 0
    for cls in classes:
        mapped = [e for e in exemplars if e.detector_class == cls and e.h2_faithful_fired_expected is not None]
        denom = len(mapped)
        fired_f = sum(1 for e in mapped if e.h2_faithful_fired_expected)
        fired_i = sum(1 for e in mapped if e.h2_isolated_fired_expected)
        per_f[cls] = (fired_f, denom)
        per_i[cls] = (fired_i, denom)
        delta[cls] = _rate(fired_i, denom) - _rate(fired_f, denom)
        of_f += fired_f; oi_f += denom; of_i += fired_i; oi_i += denom
    return DetectorRecall(per_f, per_i, (of_f, oi_f), (of_i, oi_i), delta)


def build_scorecard(
    mode: str,
    exemplars: list[ExemplarSummary],
    controls: list[ControlSummary],
    *,
    bootstrap_b: int,
    base_seed: int,
) -> Scorecard:
    outcomes = [e.h1_outcome for e in exemplars]
    full, screenable = screening_recall(outcomes)
    screenable_rows = [
        (e.ticker, e.h1_outcome in _SURFACED) for e in exemplars if e.h1_outcome not in _ATTRITION
    ]
    successes = sum(1 for _, ok in screenable_rows if ok)
    wilson = wilson_interval(successes, len(screenable_rows))
    boot = ticker_clustered_bootstrap(
        screenable_rows,
        lambda rs: _rate(sum(1 for _, ok in rs if ok), len(rs)),
        b=bootstrap_b,
        base_seed=base_seed,
    )
    gate_hist = dict(
        Counter(
            e.first_rejecting_gate
            for e in exemplars
            if e.h1_outcome == "skip_gate_rejection" and e.first_rejecting_gate
        )
    )
    # Per-gate pass rate over the FULL screenable subset (spec section 9 -> histogram AND pass rate).
    # Denominator = every screenable exemplar; a screenable row missing gate_passes is a threading
    # bug (evaluate_h1 ALWAYS sets gate_passes for surfaced/gate_rejection outcomes) -> raise loudly
    # rather than silently shrink the denominator and overstate pass rates (Codex R2).
    screenable_ex = [e for e in exemplars if e.h1_outcome not in _ATTRITION]
    missing_gp = [e.exemplar_id for e in screenable_ex if e.gate_passes is None]
    if missing_gp:
        raise ValueError(
            f"per-gate pass rate: {len(missing_gp)} screenable exemplar(s) missing gate_passes "
            f"(threading bug): {missing_gp}"
        )
    per_gate_pass = {
        g: _rate(sum(1 for e in screenable_ex if e.gate_passes.get(g)), len(screenable_ex))
        for g in ("risk_feasibility", "trend_template", "vcp")
    }
    # Spec section 8: unmapped exemplars contribute SCREENING (H1) controls only -> the H2
    # fired-rate denominators exclude unmapped controls (they have no expected class to fire).
    mapped_controls = [c for c in controls if c.detector_class != "unmapped"]
    spec = {
        "control_surfaced_rate": _rate(sum(1 for c in controls if c.surfaced), len(controls)),
        "control_fired_faithful_rate": _rate(sum(1 for c in mapped_controls if c.fired_faithful), len(mapped_controls)),
        "control_fired_isolated_rate": _rate(sum(1 for c in mapped_controls if c.fired_isolated), len(mapped_controls)),
        "control_n": float(len(controls)),
        "control_n_mapped": float(len(mapped_controls)),
    }
    return Scorecard(
        mode=mode,
        bucket_distribution=dict(Counter(outcomes)),
        screening_recall_full=full,
        screening_recall_screenable=screenable,
        screening_wilson_screenable=wilson,
        screening_bootstrap_screenable=boot,
        gate_attribution_hist=gate_hist,
        per_gate_pass_rate_screenable=per_gate_pass,
        detector_recall=_detector_recall(exemplars),
        specificity_contrast=spec,
    )
