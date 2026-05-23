"""CLI entrypoint for the A+ sensitivity sweep harness.

Invoke via ``python -m research.harness.aplus_sensitivity.run --db PATH
--eval-runs N --output-dir DIR`` OR via ``swing diagnose aplus-sensitivity``
which delegates here.
"""
from __future__ import annotations

import argparse
import sqlite3
from datetime import UTC, datetime
from pathlib import Path

from research.harness.aplus_sensitivity.output import (
    write_sensitivity_csv,
    write_sensitivity_markdown,
)
from research.harness.aplus_sensitivity.sweep import run_sensitivity_sweep
from research.harness.aplus_sensitivity.variables import enumerate_variables
from swing.config import Config


def run_harness(
    *,
    db_path: Path,
    eval_runs: int,
    output_dir: Path,
) -> tuple[Path, Path]:
    """Run the sweep + emit CSV + markdown into ``output_dir``.

    Returns ``(md_path, csv_path)``. Validates ``eval_runs`` in [1, 100]; a
    ValueError raised here is wrapped into ``click.ClickException`` by the
    ``swing diagnose aplus-sensitivity`` CLI surface.
    """
    if not 1 <= eval_runs <= 100:
        raise ValueError(
            f"eval_runs must be between 1 and 100 inclusive; got {eval_runs}"
        )
    cfg = Config.from_defaults()
    variables = enumerate_variables(cfg)
    conn = sqlite3.connect(str(db_path))
    try:
        result = run_sensitivity_sweep(
            conn, variables=variables, cfg=cfg, eval_runs_window=eval_runs,
        )
    finally:
        conn.close()
    iso = datetime.now(UTC).strftime("%Y%m%dT%H%M%SZ")
    csv_path = output_dir / f"aplus-sensitivity-{iso}.csv"
    md_path = output_dir / f"aplus-sensitivity-{iso}.md"
    write_sensitivity_csv(result, csv_path)
    write_sensitivity_markdown(result, md_path)
    return md_path, csv_path


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", required=True, type=Path)
    parser.add_argument("--eval-runs", type=int, default=20)
    parser.add_argument(
        "--output-dir", type=Path, default=Path("exports/diagnostics"),
    )
    args = parser.parse_args(argv)
    if not 1 <= args.eval_runs <= 100:
        parser.error("--eval-runs must be between 1 and 100 inclusive")
    md_path, csv_path = run_harness(
        db_path=args.db, eval_runs=args.eval_runs, output_dir=args.output_dir,
    )
    print(f"Markdown: {md_path}")
    print(f"CSV:      {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
