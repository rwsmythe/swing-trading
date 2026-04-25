"""Candidate-sparsity diagnostic — universe × capital matrix driver.

Runs the harness with:
    - a configurable ``--universe`` variant (``spx_ndx`` baseline, or
      ``russell_3000`` / ``sp_1500`` for the broader-universe diagnostic).
    - a ``--capital-multiplier`` against an operator-derived
      ``--base-capital`` baseline, so the diagnostic can probe the
      operator hypothesis (low capital binding ``risk_feasibility``).

Outputs (per run):
    - ``evaluations.csv`` — one row per (ticker, date) the evaluator
      saw, with bucket + binding-constraint + per-criterion pass/fail.
    - ``aplus_signals.csv`` — A+ signals (subset of evaluations).
    - ``binding_constraints.csv`` — aggregated counts per criterion
      across all (ticker, date) pairs.
    - ``run_manifest.json`` — provenance: universe, capital, multiplier,
      cache stats, window, harness git SHA.

Phase isolation
---------------
``swing/*`` is read-only. The diagnostic does not write to the operator
DB and does not mutate any production module. New files live under
``research/harness/earnings_proximity/`` per V2.1 §IV.B-research-branch.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import sys
import tomllib
from collections import Counter
from collections.abc import Iterable
from datetime import date, datetime, timedelta
from pathlib import Path

import exchange_calendars as xcals
import pandas as pd

from research.harness.earnings_proximity import fetchers
from research.harness.earnings_proximity.instrumented_replay import (
    APLUS_KEY,
    EvaluationRecord,
    aggregate_binding_constraints,
    aplus_signals_from,
    instrumented_replay,
    write_records_csv,
)
from research.harness.earnings_proximity.replay import build_harness_config
from research.harness.earnings_proximity.universe_variants import (
    UniverseVariant,
    load_universe_variant,
)

_BENCHMARK_TICKER = "SPY"
_HISTORY_PRIOR_BARS = 220
_FORWARD_BUFFER_BARS = 30
_DEFAULT_CACHE_SUBPATH = Path("swing-data") / "research-cache"
_DEFAULT_CONFIG_PATH = Path(__file__).resolve().parents[4] / "swing.config.toml"


def operator_sizing_equity(config_path: Path = _DEFAULT_CONFIG_PATH) -> float:
    """Derive the operator's production sizing equity from ``swing.config.toml``.

    Mirrors :func:`swing.trades.equity.sizing_equity`'s rule:
    ``max(starting_equity, risk_equity_floor)``. Read directly from the
    TOML so the harness does not depend on the production DB (phase
    isolation: real-equity-from-DB requires repos.exits + cash_movements
    queries which are out-of-scope here).
    """
    with open(config_path, "rb") as fh:
        raw = tomllib.load(fh)
    account = raw["account"]
    return max(float(account["starting_equity"]), float(account["risk_equity_floor"]))


def load_universe_variant_at(name: str, cache_dir: Path) -> UniverseVariant:
    """Trivial wrapper exposing universe loading as a monkey-patch seam for tests."""
    return load_universe_variant(name, cache_dir=cache_dir)


def _trading_days(window_start: date, window_end: date) -> list[date]:
    cal = xcals.get_calendar("XNYS")
    sessions = cal.sessions_in_range(pd.Timestamp(window_start), pd.Timestamp(window_end))
    return [s.date() for s in sessions]


def _fetch_window(window_start: date, window_end: date) -> tuple[date, date]:
    cal = xcals.get_calendar("XNYS")
    backward = cal.sessions_in_range(
        pd.Timestamp(window_start) - pd.Timedelta(days=_HISTORY_PRIOR_BARS * 2 + 30),
        pd.Timestamp(window_start),
    )
    start = backward[0].date()
    forward = cal.sessions_in_range(
        pd.Timestamp(window_end),
        pd.Timestamp(window_end) + pd.Timedelta(days=_FORWARD_BUFFER_BARS * 2 + 30),
    )
    if len(forward) > _FORWARD_BUFFER_BARS:
        end = forward[_FORWARD_BUFFER_BARS].date()
    else:
        end = forward[-1].date()
    end = end + timedelta(days=1)  # yf.download end-exclusive
    return start, end


def _write_aplus_signals_csv(records: Iterable[EvaluationRecord], path: Path) -> None:
    signals = aplus_signals_from(records)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "ticker",
                "date",
                "entry_target",
                "initial_stop",
                "next_earnings_date",
                "absent_earnings_data",
            ]
        )
        for s in signals:
            writer.writerow(
                [
                    s.ticker,
                    s.date.isoformat(),
                    s.entry_target,
                    s.initial_stop,
                    s.next_earnings_date.isoformat() if s.next_earnings_date else "",
                    int(s.absent_earnings_data),
                ]
            )


def _write_binding_constraints_csv(counts: Counter[str], total: int, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["criterion", "count", "fraction_of_evaluations"])
        # Stable order: A+ first, then by count desc.
        items = sorted(
            counts.items(),
            key=lambda kv: (kv[0] != APLUS_KEY, -kv[1]),
        )
        for criterion, count in items:
            frac = (count / total) if total else 0.0
            writer.writerow([criterion, count, f"{frac:.6f}"])


def _git_sha(repo_root: Path) -> str:
    head = repo_root / ".git" / "HEAD"
    if not head.exists():
        return "unknown"
    head_text = head.read_text(encoding="utf-8").strip()
    if head_text.startswith("ref: "):
        ref_path = repo_root / ".git" / head_text[5:].strip()
        if ref_path.exists():
            return ref_path.read_text(encoding="utf-8").strip()
    return head_text


def _git_dirty(repo_root: Path) -> bool | None:
    """Return True iff the working tree has uncommitted changes; None on git error.

    Mirrors `git status --porcelain` exit semantics — any non-empty output
    means the working tree is dirty. The parity-check D5 R1 lesson
    requires this surface be captured at run time so manifest provenance
    is not invalidated by an in-flight uncommitted edit. Captured at
    run-start in :func:`run_diagnostic`'s manifest emission.
    """
    import subprocess

    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=False,
            timeout=15,
        )
    except (OSError, subprocess.SubprocessError):
        return None
    if out.returncode != 0:
        return None
    return bool(out.stdout.strip())


def run_diagnostic(
    *,
    universe_variant: UniverseVariant,
    base_capital: float,
    capital_multiplier: float,
    window_start: date,
    window_end: date,
    output_dir: Path,
    cache_dir: Path,
) -> dict:
    """Execute one diagnostic run; return a summary dict (also written as manifest)."""
    output_dir = Path(output_dir)
    cache_dir = Path(cache_dir)
    output_dir.mkdir(parents=True, exist_ok=True)
    cache_dir.mkdir(parents=True, exist_ok=True)

    effective_equity = base_capital * capital_multiplier

    trading_days = _trading_days(window_start, window_end)
    if not trading_days:
        raise RuntimeError(f"No NYSE sessions in window {window_start}..{window_end}")
    fetch_start, fetch_end = _fetch_window(window_start, window_end)

    universe_tickers = universe_variant.tickers
    fetch_tickers = sorted({*universe_tickers, _BENCHMARK_TICKER})

    ohlcv, ohlcv_stats = fetchers.load_ohlcv_with_stats(
        fetch_tickers, start=fetch_start, end=fetch_end, cache_dir=cache_dir
    )
    earnings_tickers = [t for t in fetch_tickers if t != _BENCHMARK_TICKER]
    earnings, earnings_stats = fetchers.load_earnings_with_stats(
        earnings_tickers, cache_dir=cache_dir
    )

    cfg = build_harness_config()

    # Universe hash — stable identifier for cross-run provenance.
    canonical = "\n".join(universe_tickers).encode("utf-8")
    universe_hash = hashlib.sha256(canonical).hexdigest()

    records = list(
        instrumented_replay(
            universe_tickers=universe_tickers,
            trading_days=trading_days,
            ohlcv=ohlcv,
            earnings=earnings,
            cfg=cfg,
            universe_version=universe_variant.version,
            universe_hash=universe_hash,
            benchmark_ticker=_BENCHMARK_TICKER,
            current_equity=effective_equity,
        )
    )

    # ---- Outputs ----
    write_records_csv(records, output_dir / "evaluations.csv")
    _write_aplus_signals_csv(records, output_dir / "aplus_signals.csv")

    counts = aggregate_binding_constraints(records)
    total_evals = sum(counts.values())
    _write_binding_constraints_csv(counts, total_evals, output_dir / "binding_constraints.csv")

    aplus_count = counts.get(APLUS_KEY, 0)
    repo_root = Path(__file__).resolve().parents[4]
    git_dirty = _git_dirty(repo_root)
    manifest = {
        "run_ts": datetime.now().isoformat(),
        "git_sha": _git_sha(repo_root),
        "git_dirty": git_dirty,
        "universe_name": universe_variant.name,
        "universe_version": universe_variant.version,
        "universe_hash": universe_hash,
        "universe_source_url": universe_variant.source_url,
        "universe_fetched_date": (
            universe_variant.fetched_date.isoformat() if universe_variant.fetched_date else None
        ),
        "universe_size": len(universe_tickers),
        "window_start": window_start.isoformat(),
        "window_end": window_end.isoformat(),
        "trading_days": len(trading_days),
        "fetch_start": fetch_start.isoformat(),
        "fetch_end": fetch_end.isoformat(),
        "base_capital": base_capital,
        "capital_multiplier": capital_multiplier,
        "effective_equity": effective_equity,
        "ohlcv_hits": ohlcv_stats.hit_count,
        "ohlcv_misses": ohlcv_stats.miss_count,
        "earnings_hits": earnings_stats.hit_count,
        "earnings_misses": earnings_stats.miss_count,
        "evaluations_total": total_evals,
        "aplus_signals_total": aplus_count,
        "ticker_days_total": len(universe_tickers) * len(trading_days),
        "aplus_rate_per_ticker_day": (
            aplus_count / (len(universe_tickers) * len(trading_days))
            if universe_tickers and trading_days
            else 0.0
        ),
    }
    (output_dir / "run_manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


def _parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog="diagnostic_run",
        description="Candidate-sparsity diagnostic run (universe × capital).",
    )
    parser.add_argument(
        "--universe",
        required=True,
        choices=("spx_ndx", "russell_3000", "sp_1500"),
        help="Universe variant.",
    )
    parser.add_argument(
        "--capital-multiplier",
        type=float,
        default=1.0,
        help="Multiplier on --base-capital (default 1.0).",
    )
    parser.add_argument(
        "--base-capital",
        type=float,
        default=None,
        help=(
            "Base capital (USD). Default: max(starting_equity, risk_equity_floor) "
            "from swing.config.toml."
        ),
    )
    parser.add_argument(
        "--window-start",
        type=date.fromisoformat,
        default=date(2024, 4, 19),
        help="Inclusive start of replay window (default: Session 2c window-start).",
    )
    parser.add_argument(
        "--window-end",
        type=date.fromisoformat,
        default=date(2026, 4, 23),
        help="Inclusive end of replay window (default: Session 2c window-end).",
    )
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=Path.home() / _DEFAULT_CACHE_SUBPATH,
    )
    parser.add_argument(
        "--config-path",
        type=Path,
        default=_DEFAULT_CONFIG_PATH,
        help="swing.config.toml path (used to derive default --base-capital).",
    )
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = _parse_args(argv)

    base_capital = (
        args.base_capital
        if args.base_capital is not None
        else operator_sizing_equity(args.config_path)
    )

    universe_variant = load_universe_variant_at(args.universe, args.cache_dir)
    run_diagnostic(
        universe_variant=universe_variant,
        base_capital=base_capital,
        capital_multiplier=args.capital_multiplier,
        window_start=args.window_start,
        window_end=args.window_end,
        output_dir=args.output_dir,
        cache_dir=args.cache_dir,
    )
    print(f"Wrote diagnostic outputs to {args.output_dir}")
    return 0


if __name__ == "__main__":  # pragma: no cover — CLI shim
    sys.exit(main())
