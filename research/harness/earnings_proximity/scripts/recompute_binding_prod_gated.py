"""Re-aggregate per-criterion binding-constraint counts using production gating order.

Adversarial-review (Round 1) found that the diagnostic's original
``binding_constraint`` field walked emitted criterion order (TT1-TT8 →
VCP → risk_feasibility), but ``swing.evaluation.scoring.bucket_for``
checks ``risk_feasibility`` FIRST as a hard filter, then trend-template
gating, then VCP fail-count thresholds. A candidate failing both TT1 and
risk_feasibility is "skipped due to risk" in production, not "skipped
due to TT1."

This script reads each run's evaluations.csv (gitignored, on disk), and
writes ``binding_constraints_prod_gated.csv`` alongside the existing
binding_constraints.csv. The original is preserved for audit; the
prod-gated version is what the diagnostic report cites.

Phase isolation
---------------
Read-only; emits a new CSV in the same run directory. Does not mutate
production code.
"""
from __future__ import annotations

import argparse
import csv
import sys
from collections import Counter
from pathlib import Path

from research.harness.earnings_proximity.replay import build_harness_config
from swing.evaluation.criteria.trend_template import CHECK_NAMES as TT_CHECK_NAMES

# Trend-template criterion names in evaluation order (canonical from
# swing.evaluation.criteria.trend_template). Use the production source
# of truth, not a hand-maintained copy.
TT_NAMES_IN_ORDER = TT_CHECK_NAMES

# Production thresholds are loaded from build_harness_config (which
# mirrors swing.config.toml semantics). This avoids hardcoding values
# that could drift between the harness and the script.
_CFG = build_harness_config()
MIN_TT_PASSES = _CFG.trend_template.min_passes
ALLOWED_MISS_TT = frozenset(_CFG.trend_template.allowed_miss_names)

VCP_NAMES_IN_ORDER = (
    "prior_trend",
    "ma_stack_10_20_50",
    "ma_short_rising",
    "proximity_20ma",
    "adr",
    "pullback",
    "tightness",
    "vcp_volume_contraction",
    "orderliness",
)

RISK_NAMES_IN_ORDER = ("risk_feasibility",)

APLUS_KEY = "<aplus>"


def production_gated_binding(row: dict[str, str]) -> str:
    """Determine the binding criterion using production scoring.bucket_for order."""
    # 1. Risk first (hard filter).
    for name in RISK_NAMES_IN_ORDER:
        result = row.get(name, "")
        if result and result != "pass":
            return name
    # 2. Trend-template: pass-count + allowed-miss check.
    tt_passes = sum(1 for name in TT_NAMES_IN_ORDER if row.get(name) == "pass")
    tt_fails = [name for name in TT_NAMES_IN_ORDER if row.get(name) and row.get(name) != "pass"]
    if tt_passes < MIN_TT_PASSES or any(n not in ALLOWED_MISS_TT for n in tt_fails):
        # First non-allowed-miss TT failure (in TT1-TT8 order).
        for name in TT_NAMES_IN_ORDER:
            r = row.get(name, "")
            if r and r != "pass" and name not in ALLOWED_MISS_TT:
                return name
        # Pathological: tt_passes < min but only TT8 fails (impossible since
        # min=7 of 8). Fallback: first non-pass TT.
        for name in TT_NAMES_IN_ORDER:
            r = row.get(name, "")
            if r and r != "pass":
                return name
    # 3. VCP layer: any vcp fail/na blocks A+.
    for name in VCP_NAMES_IN_ORDER:
        r = row.get(name, "")
        if r in ("fail", "na"):
            return name
    return APLUS_KEY


def aggregate_run(eval_csv: Path) -> tuple[Counter[str], int]:
    counts: Counter[str] = Counter()
    total = 0
    with eval_csv.open("r", encoding="utf-8", newline="") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            counts[production_gated_binding(row)] += 1
            total += 1
    return counts, total


def write_output(counts: Counter[str], total: int, out_csv: Path) -> None:
    items = sorted(
        counts.items(),
        key=lambda kv: (kv[0] != APLUS_KEY, -kv[1]),
    )
    with out_csv.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["criterion", "count", "fraction_of_evaluations"])
        for criterion, count in items:
            frac = (count / total) if total else 0.0
            writer.writerow([criterion, count, f"{frac:.6f}"])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="recompute_binding_prod_gated",
        description="Recompute per-criterion binding-constraint counts using "
                    "production-faithful gating order (risk → TT → VCP).",
    )
    parser.add_argument(
        "--run-dirs",
        nargs="+",
        required=True,
        help="One or more diagnostic run directories.",
    )
    args = parser.parse_args(argv)

    for run_dir_str in args.run_dirs:
        run_dir = Path(run_dir_str)
        eval_csv = run_dir / "evaluations.csv"
        if not eval_csv.exists():
            print(f"[skip] {eval_csv} not found")
            continue
        counts, total = aggregate_run(eval_csv)
        out_csv = run_dir / "binding_constraints_prod_gated.csv"
        write_output(counts, total, out_csv)
        aplus = counts.get(APLUS_KEY, 0)
        risk = counts.get("risk_feasibility", 0)
        print(
            f"[ok] {run_dir.name}: total={total} aplus={aplus} risk_feasibility={risk}"
        )

    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
