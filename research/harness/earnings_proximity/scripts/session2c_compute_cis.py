"""Session 2c — bootstrap + Wilson + Newcombe CI summary builder.

Historical reference script — see ``./README.md``. Not the canonical
interface for the harness; that is ``research.harness.earnings_proximity.run``.

Reads ``outcomes.csv`` + ``variant_membership.csv`` (written by
``session2c_run_full_study.py``) and emits ``analysis_summary.json`` with
the schema observed in commit ``e5510a8``.

Statistical framework (per the pre-registration, commit ``0e04079``)
-------------------------------------------------------------------
- **Means** (expectancy_r, gap_magnitude_mean_r): bootstrap 95% percentile
  CI with ``n_resamples=10000``, ``seed=20260424``.
- **Proportions** (gap_through_rate): Wilson 95% CI.
- **Difference of proportions** (gap_rate_delta_pp): Newcombe Method-10 CI.

Known issue (documented in the evidence summary, commit ``48320c8``)
--------------------------------------------------------------------
The expectancy-delta bootstrap in this script resamples each arm
INDEPENDENTLY rather than paired. The pre-registration calls for paired
bootstrap (same resample indices applied to X=0 and X=N's outcomes
indexed by signal ID). With Session 2c's bit-identical variant
membership, paired bootstrap would yield delta=0 in every resample
(identity → zero), but independent resampling produces artificial spread
that does not reflect any real sampling variability — the
``expectancy_delta_ci95`` of roughly ``[-0.745, +0.740]`` in
``analysis_summary.json`` is THIS spread, and the evidence summary
labels those intervals **vacuous** rather than legitimate uncertainty
bounds. The reconstructed script faithfully reproduces the flawed
behavior so the historical artifact is reproducible.

Temporal split
--------------
The 504-session window is split at the midpoint session by
``analysis_summary.json``: ``window_split_midpoint = 2025-12-24``. Signals
with ``signal_date < 2025-12-24`` belong to the first half;
``>=`` belong to the second half.
"""
from __future__ import annotations

import argparse
import csv
import json
import math
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np

WINDOW_SPLIT_MIDPOINT = date(2025, 12, 24)
BOOTSTRAP_N_RESAMPLES = 10_000
BOOTSTRAP_SEED = 20260424
VARIANT_LIST = (0, 3, 5, 7, 10)

_DEFAULT_INPUT_DIR = Path("research") / "harness" / "earnings_proximity" / "full-run-out"


@dataclass(frozen=True)
class OutcomeRow:
    outcome_id: int
    ticker: str
    signal_date: date
    triggered: bool
    r_multiple: float | None
    gap_through: bool
    gap_magnitude_r: float | None
    time_capped: bool
    absent_earnings_data: bool


def _read_outcomes(path: Path) -> list[OutcomeRow]:
    rows: list[OutcomeRow] = []
    with path.open("r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            r_mult = row["r_multiple"]
            gap_mag = row["gap_magnitude_r"]
            rows.append(
                OutcomeRow(
                    outcome_id=int(row["outcome_id"]),
                    ticker=row["ticker"],
                    signal_date=date.fromisoformat(row["signal_date"]),
                    triggered=bool(int(row["triggered"])),
                    r_multiple=float(r_mult) if r_mult else None,
                    gap_through=bool(int(row["gap_through"])),
                    gap_magnitude_r=float(gap_mag) if gap_mag else None,
                    time_capped=bool(int(row["time_capped"])),
                    absent_earnings_data=bool(int(row["absent_earnings_data"])),
                )
            )
    return rows


def _read_membership(path: Path) -> dict[int, list[int]]:
    """Return variant_x → list of outcome_ids in that variant's filtered set."""
    by_variant: dict[int, list[int]] = {x: [] for x in VARIANT_LIST}
    with path.open("r", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            x = int(row["variant_x"])
            by_variant.setdefault(x, []).append(int(row["outcome_id"]))
    return by_variant


def _bootstrap_mean_ci(
    values: list[float],
    *,
    rng: np.random.Generator,
    n_resamples: int,
) -> tuple[float, tuple[float, float]]:
    """Return (mean, (ci_low, ci_high)) using percentile bootstrap.

    Empty input: mean=0.0, ci=(0.0, 0.0). Single value: mean=value, ci=(value, value).
    """
    n = len(values)
    if n == 0:
        return 0.0, (0.0, 0.0)
    arr = np.asarray(values, dtype=float)
    mean = float(arr.mean())
    if n == 1:
        return mean, (mean, mean)
    means = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        idx = rng.integers(0, n, size=n)
        means[i] = float(arr[idx].mean())
    lo = float(np.percentile(means, 2.5))
    hi = float(np.percentile(means, 97.5))
    return mean, (lo, hi)


def _bootstrap_diff_ci(
    values_treat: list[float],
    values_baseline: list[float],
    *,
    rng: np.random.Generator,
    n_resamples: int,
) -> tuple[float, tuple[float, float]]:
    """Independently-resampled difference-of-means bootstrap.

    Faithfully reproduces Session 2c's flawed approach (see module docstring).
    """
    n_t = len(values_treat)
    n_b = len(values_baseline)
    if n_t == 0 or n_b == 0:
        return 0.0, (0.0, 0.0)
    arr_t = np.asarray(values_treat, dtype=float)
    arr_b = np.asarray(values_baseline, dtype=float)
    diff = float(arr_t.mean() - arr_b.mean())
    diffs = np.empty(n_resamples, dtype=float)
    for i in range(n_resamples):
        idx_t = rng.integers(0, n_t, size=n_t)
        idx_b = rng.integers(0, n_b, size=n_b)
        diffs[i] = float(arr_t[idx_t].mean() - arr_b[idx_b].mean())
    lo = float(np.percentile(diffs, 2.5))
    hi = float(np.percentile(diffs, 97.5))
    return diff, (lo, hi)


def _wilson_ci(successes: int, n: int, z: float = 1.959963984540054) -> tuple[float, float]:
    """Wilson 95% CI for a single proportion. Returns (0,0) on n=0."""
    if n == 0:
        return 0.0, 0.0
    p_hat = successes / n
    denom = 1.0 + z * z / n
    center = (p_hat + z * z / (2 * n)) / denom
    half = (z * math.sqrt(p_hat * (1 - p_hat) / n + z * z / (4 * n * n))) / denom
    return max(0.0, center - half), min(1.0, center + half)


def _newcombe_diff_ci(
    s1: int, n1: int, s2: int, n2: int, z: float = 1.959963984540054
) -> tuple[float, float]:
    """Newcombe Method-10 95% CI for the difference (p1 - p2).

    Source: Newcombe RG. "Interval estimation for the difference between
    independent proportions: comparison of eleven methods." Statistics in
    Medicine 1998 (Method 10).

    Returns (0, 0) when either denominator is zero (no useful interval).
    """
    if n1 == 0 or n2 == 0:
        return 0.0, 0.0
    p1 = s1 / n1
    p2 = s2 / n2
    l1, u1 = _wilson_ci(s1, n1, z)
    l2, u2 = _wilson_ci(s2, n2, z)
    delta = (p1 - p2)
    lower = delta - math.sqrt((p1 - l1) ** 2 + (u2 - p2) ** 2)
    upper = delta + math.sqrt((u1 - p1) ** 2 + (p2 - l2) ** 2)
    return lower, upper


def _per_variant_summary(
    outcomes_in_variant: list[OutcomeRow],
    *,
    rng: np.random.Generator,
) -> dict:
    triggered = [
        o for o in outcomes_in_variant if o.triggered and o.r_multiple is not None
    ]
    r_multiples = [o.r_multiple for o in triggered if o.r_multiple is not None]
    stopped = [
        o
        for o in triggered
        if (o.r_multiple or 0.0) < 0 and not o.time_capped
    ]
    gapped = [o for o in stopped if o.gap_through]
    gap_mags = [
        o.gap_magnitude_r for o in gapped if o.gap_magnitude_r is not None
    ]

    expectancy, exp_ci = _bootstrap_mean_ci(
        r_multiples, rng=rng, n_resamples=BOOTSTRAP_N_RESAMPLES
    )

    gap_rate = (len(gapped) / len(stopped)) if stopped else 0.0
    gap_rate_ci = _wilson_ci(len(gapped), len(stopped))

    gap_mag_mean, gap_mag_ci = _bootstrap_mean_ci(
        gap_mags, rng=rng, n_resamples=BOOTSTRAP_N_RESAMPLES
    )
    gap_mag_max = max(gap_mags) if gap_mags else 0.0

    return {
        "signal_count": len(outcomes_in_variant),
        "traded_count": len(triggered),
        "dropped_count": len(outcomes_in_variant) - len(triggered),
        "absent_data_count": sum(
            1 for o in outcomes_in_variant if o.absent_earnings_data
        ),
        "stopped_count": len(stopped),
        "gapped_count": len(gapped),
        "expectancy_r": float(expectancy),
        "expectancy_ci95": list(exp_ci),
        "gap_through_rate": float(gap_rate),
        "gap_through_rate_wilson_ci95": list(gap_rate_ci),
        "gap_magnitude_mean_r": float(gap_mag_mean),
        "gap_magnitude_mean_ci95": list(gap_mag_ci),
        "gap_magnitude_max_r": float(gap_mag_max),
    }


def _delta_summary(
    outcomes_treat: list[OutcomeRow],
    outcomes_baseline: list[OutcomeRow],
    *,
    rng: np.random.Generator,
) -> dict:
    triggered_t = [
        o.r_multiple
        for o in outcomes_treat
        if o.triggered and o.r_multiple is not None
    ]
    triggered_b = [
        o.r_multiple
        for o in outcomes_baseline
        if o.triggered and o.r_multiple is not None
    ]
    expectancy_delta, exp_delta_ci = _bootstrap_diff_ci(
        triggered_t, triggered_b, rng=rng, n_resamples=BOOTSTRAP_N_RESAMPLES
    )

    stopped_t = [
        o
        for o in outcomes_treat
        if o.triggered
        and o.r_multiple is not None
        and o.r_multiple < 0
        and not o.time_capped
    ]
    stopped_b = [
        o
        for o in outcomes_baseline
        if o.triggered
        and o.r_multiple is not None
        and o.r_multiple < 0
        and not o.time_capped
    ]
    gapped_t = [o for o in stopped_t if o.gap_through]
    gapped_b = [o for o in stopped_b if o.gap_through]

    gap_rate_t = (len(gapped_t) / len(stopped_t)) if stopped_t else 0.0
    gap_rate_b = (len(gapped_b) / len(stopped_b)) if stopped_b else 0.0
    gap_rate_delta_pp = (gap_rate_t - gap_rate_b) * 100.0
    gap_rate_reduction_pp = -gap_rate_delta_pp
    gap_rate_diff_ci = _newcombe_diff_ci(
        len(gapped_t), len(stopped_t), len(gapped_b), len(stopped_b)
    )

    mags_t = [o.gap_magnitude_r for o in gapped_t if o.gap_magnitude_r is not None]
    mags_b = [o.gap_magnitude_r for o in gapped_b if o.gap_magnitude_r is not None]
    gap_mag_delta, gap_mag_delta_ci = _bootstrap_diff_ci(
        mags_t, mags_b, rng=rng, n_resamples=BOOTSTRAP_N_RESAMPLES
    )

    sig_t = len(outcomes_treat)
    sig_b = len(outcomes_baseline)
    signal_volume_loss_pct = (
        (1.0 - sig_t / sig_b) * 100.0 if sig_b > 0 else 0.0
    )

    return {
        "expectancy_delta_r": float(expectancy_delta),
        "expectancy_delta_ci95": list(exp_delta_ci),
        "gap_rate_delta_pp": float(gap_rate_delta_pp),
        "gap_rate_reduction_pp": float(gap_rate_reduction_pp),
        "gap_rate_diff_newcombe_ci95_pp": [
            float(gap_rate_diff_ci[0]) * 100.0,
            float(gap_rate_diff_ci[1]) * 100.0,
        ],
        "gap_magnitude_delta_r": float(gap_mag_delta),
        "gap_magnitude_reduction_r": float(-gap_mag_delta),
        "gap_magnitude_delta_ci95": list(gap_mag_delta_ci),
        "signal_volume_loss_pct": float(signal_volume_loss_pct),
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="session2c_compute_cis",
        description="Session 2c CI summary builder (historical reference).",
    )
    repo_root = Path(__file__).resolve().parents[4]
    parser.add_argument(
        "--input-dir",
        default=str(repo_root / _DEFAULT_INPUT_DIR),
        help=(
            "Directory containing outcomes.csv + variant_membership.csv. "
            "analysis_summary.json is written to the same directory."
        ),
    )
    args = parser.parse_args(argv)

    input_dir = Path(args.input_dir)
    outcomes = _read_outcomes(input_dir / "outcomes.csv")
    membership = _read_membership(input_dir / "variant_membership.csv")

    by_id = {o.outcome_id: o for o in outcomes}

    rng = np.random.default_rng(BOOTSTRAP_SEED)

    per_variant: dict[str, dict] = {}
    deltas_vs_x0: dict[str, dict] = {}
    baseline_outcomes = [by_id[oid] for oid in membership.get(0, []) if oid in by_id]

    for x in VARIANT_LIST:
        variant_outcomes = [by_id[oid] for oid in membership.get(x, []) if oid in by_id]
        per_variant[f"X={x}"] = _per_variant_summary(variant_outcomes, rng=rng)
        if x == 0:
            continue
        deltas_vs_x0[f"X={x}"] = _delta_summary(
            variant_outcomes, baseline_outcomes, rng=rng
        )

    # ---- Temporal subsets. ----
    first_half_outcomes = [o for o in outcomes if o.signal_date < WINDOW_SPLIT_MIDPOINT]
    second_half_outcomes = [o for o in outcomes if o.signal_date >= WINDOW_SPLIT_MIDPOINT]
    first_ids = {o.outcome_id for o in first_half_outcomes}
    second_ids = {o.outcome_id for o in second_half_outcomes}

    temporal_first: dict[str, dict] = {}
    temporal_second: dict[str, dict] = {}
    for x in VARIANT_LIST:
        v_outcomes = [by_id[oid] for oid in membership.get(x, []) if oid in by_id]
        first = [o for o in v_outcomes if o.outcome_id in first_ids]
        second = [o for o in v_outcomes if o.outcome_id in second_ids]
        temporal_first[f"X={x}"] = _per_variant_summary(first, rng=rng)
        temporal_second[f"X={x}"] = _per_variant_summary(second, rng=rng)

    summary = {
        "per_variant": per_variant,
        "deltas_vs_X0": deltas_vs_x0,
        "window_split_midpoint": WINDOW_SPLIT_MIDPOINT.isoformat(),
        "temporal_subset_first_half": temporal_first,
        "temporal_subset_second_half": temporal_second,
        "absent_data_audit": {
            "overall_signals_with_earnings_data": sum(
                1 for o in outcomes if not o.absent_earnings_data
            ),
            "overall_absent_data_signals": sum(
                1 for o in outcomes if o.absent_earnings_data
            ),
            "overall_total_signals": len(outcomes),
        },
        "bootstrap_config": {
            "n_resamples": BOOTSTRAP_N_RESAMPLES,
            "seed": BOOTSTRAP_SEED,
        },
    }

    out_path = input_dir / "analysis_summary.json"
    out_path.write_text(json.dumps(summary, indent=2))
    print(f"Wrote {out_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover — module-level CLI shim
    raise SystemExit(main())
