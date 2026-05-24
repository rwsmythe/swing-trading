"""V2 OHLCV harness CLI entry point.

Invoke via ``python -m research.harness.aplus_v2_ohlcv_evaluator.run --db PATH
--eval-runs N --output-dir DIR`` OR via ``swing diagnose aplus-sensitivity-v2``
which delegates here.

L2 LOCK preserved: NO imports of the four forbidden modules
(yfinance, schwabdev, swing.integrations.schwab, swing.data.ohlcv_archive).
DB opened via URI mode=ro per Codex R2.M2 RESOLVED (defense-in-depth; any
accidental INSERT/UPDATE/CREATE from V2 module set raises OperationalError).
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from research.harness.aplus_sensitivity.variables import enumerate_variables
from research.harness.aplus_v2_ohlcv_evaluator.output import (
    write_sensitivity_csv_v2,
    write_sensitivity_markdown_v2,
)
from research.harness.aplus_v2_ohlcv_evaluator.sweep import run_v2_sweep
from swing.config import Config


def _get_cfg() -> Config:
    """Load production cfg via Config.from_defaults().

    Isolated to a module-level helper so tests can monkeypatch it without
    importing run.py's internals directly.
    """
    return Config.from_defaults()


def run_harness(
    *,
    db_path: Path,
    eval_runs: int,
    output_dir: Path,
    variables_filter: tuple[str, ...] | None = None,
    min_universe_size: int = 100,
    max_runtime_seconds: float | None = None,
) -> tuple[Path, Path]:
    """Run the V2 sweep + emit CSV + markdown into output_dir.

    Returns: (md_path, csv_path).

    Validates:
      eval_runs in [1, 100] -> ValueError (wrapped to ClickException by CLI).
      min_universe_size >= 1 -> ValueError.
      max_runtime_seconds None or > 0 -> ValueError.
      variables_filter: subset of enumerate_variables(cfg) names -> ValueError
        on unknown names with the unknown names enumerated in the message.

    DB connection (Codex R2.M2 RESOLVED + R3.m2 path-escape-safe RESOLVED):
    opens via URI mode=ro so any accidental INSERT/UPDATE/CREATE from the V2
    module set raises sqlite3.OperationalError: attempt to write a readonly
    database. Defense-in-depth atop V2-side read-only invariant per spec §A.1.
    Path-escape safety: db_path.resolve().as_uri() properly URI-encodes paths
    containing spaces, #, ? etc.
    """
    if not 1 <= eval_runs <= 100:
        raise ValueError(
            f"eval_runs must be between 1 and 100 inclusive; got {eval_runs}"
        )
    if min_universe_size < 1:
        raise ValueError(
            f"min_universe_size must be >= 1; got {min_universe_size}"
        )
    if max_runtime_seconds is not None and max_runtime_seconds <= 0:
        raise ValueError(
            f"max_runtime_seconds must be > 0 when set; got {max_runtime_seconds}"
        )

    cfg = _get_cfg()
    all_variables = enumerate_variables(cfg)

    # Validate variables_filter against known names.
    if variables_filter is not None:
        known_names = frozenset(v.name for v in all_variables)
        unknown = [n for n in variables_filter if n not in known_names]
        if unknown:
            raise ValueError(
                f"variables_filter contains unknown variable names: {unknown}; "
                f"known names: {sorted(known_names)}"
            )
        variables = tuple(v for v in all_variables if v.name in set(variables_filter))
    else:
        variables = tuple(all_variables)

    # Open DB via URI mode=ro (Codex R2.M2 + R3.m2).
    db_uri = db_path.resolve().as_uri() + "?mode=ro"
    conn = sqlite3.connect(db_uri, uri=True)
    try:
        import tracemalloc
        peak = 0  # default: sweep raised before get_traced_memory
        tracemalloc.start()
        try:
            result = run_v2_sweep(
                conn,
                variables=variables,
                cfg=cfg,
                cache_dir=cfg.paths.prices_cache_dir,
                eval_runs_window=eval_runs,
                min_universe_size=min_universe_size,
                max_runtime_seconds=max_runtime_seconds,
            )
            _, peak = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
    finally:
        conn.close()

    output_dir.mkdir(parents=True, exist_ok=True)
    iso = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    csv_path = output_dir / f"aplus-sensitivity-v2-{iso}.csv"
    md_path = output_dir / f"aplus-sensitivity-v2-{iso}.md"
    write_sensitivity_csv_v2(result, csv_path)
    write_sensitivity_markdown_v2(result, md_path, memory_peak_bytes=peak)
    return md_path, csv_path


def main(argv: list[str] | None = None) -> int:
    """argparse main for direct ``python -m`` invocation."""
    parser = argparse.ArgumentParser(
        description="V2 OHLCV criterion-evaluator sensitivity sweep."
    )
    parser.add_argument("--db", required=True, type=Path, dest="db_path")
    parser.add_argument("--eval-runs", type=int, default=20)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("exports/diagnostics"),
    )
    parser.add_argument(
        "--variables-filter", type=str, default=None,
        help="Comma-separated variable-name filter.",
    )
    parser.add_argument(
        "--min-universe-size", type=int, default=100,
    )
    parser.add_argument(
        "--max-runtime-seconds", type=float, default=None,
    )
    args = parser.parse_args(argv)

    filter_tuple: tuple[str, ...] | None = None
    if args.variables_filter:
        filter_tuple = tuple(
            s.strip() for s in args.variables_filter.split(",") if s.strip()
        )

    try:
        md_path, csv_path = run_harness(
            db_path=args.db_path,
            eval_runs=args.eval_runs,
            output_dir=args.output_dir,
            variables_filter=filter_tuple,
            min_universe_size=args.min_universe_size,
            max_runtime_seconds=args.max_runtime_seconds,
        )
    except ValueError as exc:
        parser.error(str(exc))
        return 1  # unreachable; parser.error raises SystemExit

    print(f"Markdown: {md_path}")
    print(f"CSV:      {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
