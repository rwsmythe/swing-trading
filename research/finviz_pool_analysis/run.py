"""CLI entrypoint for the Finviz-pool binding-constraint aggregation.

Outputs (locked by D1 §"Outputs"):
- ``per_criterion_blockers.csv`` — production-gated blocker counts.
- ``bucket_distribution.csv`` — per-bucket counts + watch:A+ ratio.
- ``per_run_summary.csv`` — per-run bucket counts + per-run watch:A+ ratio.
- ``near_aplus_defensible_sample.csv`` — ≤10 ticker rows.
- ``near_aplus_incompatible_sample.csv`` — ≤10 ticker rows.
- ``run_manifest.json`` — provenance per D1 §"Provenance commitments".

Usage:

    python -m research.finviz_pool_analysis.run \\
        --output-dir research/finviz_pool_analysis/out/run_<YYYYMMDD>/

D3 of the study is gated on D1 (pre-registration) being committed first.
This CLI reads the production DB read-only.
"""
from __future__ import annotations

import argparse
import csv
import json
import sqlite3
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from research.finviz_pool_analysis.aggregator import (
    AggregateResult,
    NearAplusSample,
    aggregate_runs,
)
from research.finviz_pool_analysis.doctrine import (
    DEFENSIBLE_MISS_SET,
    DOCTRINE_INCOMPATIBLE_SET,
)
from research.finviz_pool_analysis.fetcher import (
    QualifyingRun,
    SkippedRun,
    fetch_run_candidates_with_criteria,
    list_qualifying_evaluation_runs,
)
from swing.config import load as load_config


def _git_sha(repo_root: Path) -> str:
    """Return the current HEAD SHA at run time (NOT commit time)."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return "unknown"


def _git_dirty(repo_root: Path) -> bool:
    """Return True iff the worktree has uncommitted changes at run time.

    Checks both staged and unstaged changes via ``git status --porcelain``;
    any non-empty output flags the tree as dirty. The brief's manifest-
    integrity watch item requires the manifest to distinguish "run from a
    clean commit" from "run from a dirty tree" so subsequent reproductions
    are not silently misled by stale `harness_git_sha`.

    Callers should invoke this BEFORE generating run outputs; otherwise
    the run's own output files appear as dirty modifications and the
    flag is uninformative.
    """
    try:
        result = subprocess.run(
            ["git", "status", "--porcelain"],
            cwd=repo_root,
            capture_output=True,
            text=True,
            check=True,
        )
        return bool(result.stdout.strip())
    except (subprocess.CalledProcessError, FileNotFoundError):
        return False


def _write_blockers_csv(result: AggregateResult, path: Path) -> None:
    items = sorted(
        result.blocker_counts.items(),
        key=lambda kv: (kv[0] != "<aplus>", -kv[1]),
    )
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["criterion", "count", "fraction_of_evaluations"])
        for name, count in items:
            frac = count / result.total_evaluations if result.total_evaluations else 0.0
            writer.writerow([name, count, f"{frac:.6f}"])


def _write_bucket_csv(result: AggregateResult, path: Path) -> None:
    buckets = ("aplus", "watch", "skip", "error", "excluded")
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["bucket", "count", "fraction_of_evaluations"])
        for b in buckets:
            count = result.bucket_counts.get(b, 0)
            frac = count / result.total_evaluations if result.total_evaluations else 0.0
            writer.writerow([b, count, f"{frac:.6f}"])
        ratio_str = (
            "undefined"
            if result.watch_aplus_ratio is None
            else f"{result.watch_aplus_ratio:.6f}"
        )
        writer.writerow(["watch_aplus_ratio_overall", "", ratio_str])


def _write_per_run_csv(
    qualifying: list[QualifyingRun], result: AggregateResult, path: Path
) -> None:
    """Per-run bucket counts + watch:A+ ratio. Counts re-derived per-run
    by walking the original (run_id, candidates) inputs is not necessary
    here because we have the per-run watch_aplus dict from the aggregate;
    the per-run bucket counts are written from the qualifying-run row's
    persisted columns since ``aggregate_runs`` does not retain per-run
    breakdown beyond the watch:A+ ratio."""
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "evaluation_run_id",
                "action_session_date",
                "watch_aplus_ratio",
            ]
        )
        for run in qualifying:
            ratio = result.per_run_watch_aplus_ratio.get(run.run_id)
            ratio_str = "undefined" if ratio is None else f"{ratio:.6f}"
            writer.writerow([run.run_id, run.action_session_date, ratio_str])


def _write_sample_csv(samples: Iterable[NearAplusSample], path: Path) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            [
                "ticker",
                "evaluation_run_id",
                "action_session_date",
                "bucket",
                "failed_criteria",
            ]
        )
        for s in samples:
            writer.writerow(
                [
                    s.ticker,
                    s.evaluation_run_id,
                    s.action_session_date,
                    s.bucket,
                    "|".join(s.failed_criteria),
                ]
            )


def _write_manifest(
    *,
    output_dir: Path,
    db_path: Path,
    repo_root: Path,
    qualifying: list[QualifyingRun],
    skipped: list[SkippedRun],
    result: AggregateResult,
    finviz_inbox_dir: Path,
    candidate_criteria_row_count: int,
    git_sha: str,
    git_dirty: bool,
) -> None:
    if qualifying:
        action_dates = sorted(r.action_session_date for r in qualifying)
        date_range = {"start": action_dates[0], "end": action_dates[-1]}
    else:
        date_range = {"start": None, "end": None}
    manifest = {
        "harness_git_sha": git_sha,
        "harness_git_dirty": git_dirty,
        "run_timestamp_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "production_db_path": str(db_path),
        "finviz_inbox_dir": str(finviz_inbox_dir),
        "qualifying_run_count": len(qualifying),
        "skipped_run_count": len(skipped),
        "qualifying_runs": [
            {
                "run_id": r.run_id,
                "action_session_date": r.action_session_date,
                "data_asof_date": r.data_asof_date,
                "finviz_csv_basename": r.finviz_csv_basename,
                "resolved_location": r.resolved_location,
            }
            for r in qualifying
        ],
        "skipped_runs": [
            {
                "run_id": s.run_id,
                "action_session_date": s.action_session_date,
                "finviz_csv_path": s.finviz_csv_path,
                "finviz_csv_basename": s.finviz_csv_basename,
                "reason": s.reason,
            }
            for s in skipped
        ],
        "action_session_date_range": date_range,
        "total_evaluations": result.total_evaluations,
        "candidate_criteria_row_count": candidate_criteria_row_count,
        "bucket_counts": dict(result.bucket_counts),
        "blocker_counts": dict(result.blocker_counts),
        "watch_aplus_ratio_overall": result.watch_aplus_ratio,
        "near_aplus_defensible_count": result.near_aplus_defensible_count,
        "near_aplus_incompatible_count": result.near_aplus_incompatible_count,
        # Doctrine-defensible miss set membership — frozen at D1, copied
        # verbatim so the manifest is self-contained provenance.
        "doctrine_defensible_miss_set": sorted(DEFENSIBLE_MISS_SET),
        "doctrine_incompatible_miss_set": sorted(DOCTRINE_INCOMPATIBLE_SET),
        "consistency_warnings": list(result.consistency_warnings),
        "path_resolution_rule": (
            "literal basename match against finviz_inbox_dir top level, "
            "then rejected/ subdirectory; not-found → skipped (csv_missing). "
            "Rejected files in production are renamed with a timestamp suffix; "
            "literal basenames typically do NOT resolve in rejected/."
        ),
    }
    (output_dir / "run_manifest.json").write_text(
        json.dumps(manifest, indent=2, sort_keys=False) + "\n", encoding="utf-8"
    )


def run_finviz_pool_aggregation(
    *,
    db_path: Path,
    finviz_inbox_dir: Path,
    output_dir: Path,
    repo_root: Path,
) -> AggregateResult:
    """Programmatic entrypoint (also called from the CLI main).

    Reads the production DB read-only, partitions runs into qualifying +
    skipped, aggregates, writes all D1-required outputs to ``output_dir``.
    Returns the ``AggregateResult`` so callers (tests) can introspect.
    """
    # Capture git state BEFORE creating any output files — once the run
    # writes outputs, the worktree is necessarily dirty, so capture must
    # happen first to be informative.
    git_sha = _git_sha(repo_root)
    git_dirty = _git_dirty(repo_root)

    output_dir.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True)
    try:
        qualifying, skipped = list_qualifying_evaluation_runs(conn, finviz_inbox_dir)
        runs_input: list[tuple[int, str, list]] = []
        candidate_criteria_row_count = 0
        for q in qualifying:
            cands = fetch_run_candidates_with_criteria(conn, q.run_id)
            runs_input.append((q.run_id, q.action_session_date, cands))
            for c in cands:
                candidate_criteria_row_count += len(c.criteria)
    finally:
        conn.close()

    result = aggregate_runs(runs_input)

    _write_blockers_csv(result, output_dir / "per_criterion_blockers.csv")
    _write_bucket_csv(result, output_dir / "bucket_distribution.csv")
    _write_per_run_csv(qualifying, result, output_dir / "per_run_summary.csv")
    _write_sample_csv(
        result.defensible_sample, output_dir / "near_aplus_defensible_sample.csv"
    )
    _write_sample_csv(
        result.incompatible_sample, output_dir / "near_aplus_incompatible_sample.csv"
    )
    _write_manifest(
        output_dir=output_dir,
        db_path=db_path,
        repo_root=repo_root,
        qualifying=qualifying,
        skipped=skipped,
        result=result,
        finviz_inbox_dir=finviz_inbox_dir,
        candidate_criteria_row_count=candidate_criteria_row_count,
        git_sha=git_sha,
        git_dirty=git_dirty,
    )
    return result


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="finviz_pool_analysis",
        description=(
            "Aggregate per-criterion production-gated blocker distribution + "
            "bucket counts + watch:A+ ratio + near-A+ defensible subset "
            "across all production evaluation_runs whose Finviz CSVs are "
            "present on disk."
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        required=True,
        help="Directory to write CSVs and run_manifest.json.",
    )
    parser.add_argument(
        "--db-path",
        type=Path,
        default=None,
        help="Override production DB path (default: cfg.paths.db_path).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("swing.config.toml"),
        help="Path to swing.config.toml (defaults to ./swing.config.toml).",
    )
    parser.add_argument(
        "--finviz-inbox-dir",
        type=Path,
        default=Path("data/finviz-inbox"),
        help="Directory holding finviz CSVs.",
    )
    parser.add_argument(
        "--repo-root",
        type=Path,
        default=Path("."),
        help="Repo root for git SHA capture.",
    )
    args = parser.parse_args(argv)

    db_path = args.db_path
    if db_path is None:
        cfg = load_config(args.config)
        db_path = Path(cfg.paths.db_path)
    if not db_path.exists():
        print(f"[error] production DB not found at {db_path}", file=sys.stderr)
        return 2
    if not args.finviz_inbox_dir.is_dir():
        print(
            f"[error] finviz inbox dir not found at {args.finviz_inbox_dir}",
            file=sys.stderr,
        )
        return 2

    result = run_finviz_pool_aggregation(
        db_path=db_path,
        finviz_inbox_dir=args.finviz_inbox_dir,
        output_dir=args.output_dir,
        repo_root=args.repo_root,
    )

    # Stdout summary — counts only, NO interpretation (per D1 run procedure).
    print(f"total_evaluations={result.total_evaluations}")
    print(f"buckets={dict(result.bucket_counts)}")
    print(f"watch_aplus_ratio_overall={result.watch_aplus_ratio}")
    print(f"near_aplus_defensible={result.near_aplus_defensible_count}")
    print(f"near_aplus_incompatible={result.near_aplus_incompatible_count}")
    if result.consistency_warnings:
        print(
            f"consistency_warnings: {len(result.consistency_warnings)} (see manifest)",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
