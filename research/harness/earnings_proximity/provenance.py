"""Run-manifest emission for the earnings-proximity replay.

Per V2.1 §IV.C, every study run writes a JSON manifest alongside its
metrics output capturing enough context to reproduce or audit the run:

- ``git_sha`` / ``git_dirty`` — source version at run time.
- ``run_ts`` — ISO-8601 UTC timestamp.
- ``yfinance_version`` — data-vendor library version (relevant: multiple
  yfinance API regressions have been documented in CLAUDE.md).
- ``universe_version_hash`` — SHA-256 of the RS universe CSV (via
  ``swing.evaluation.rs.universe_version_hash``).
- ``window_start`` / ``window_end`` / ``trading_days`` / ``tickers`` /
  ``variants`` — run scope.
- ``cache_stats`` — fetch hits/misses per data type (implementer populates).
- ``absent_data_count`` / ``dropped_signal_count`` — downstream data-quality
  counters.
- ``study_design_commit`` — SHA of ``research/studies/...`` at run time so
  the evidence summary can cite a specific design version.
"""
from __future__ import annotations

import json
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, date, datetime
from pathlib import Path


@dataclass(frozen=True)
class CacheStats:
    ohlcv_hits: int = 0
    ohlcv_misses: int = 0
    earnings_hits: int = 0
    earnings_misses: int = 0


@dataclass(frozen=True)
class RunManifest:
    git_sha: str
    git_dirty: bool
    run_ts: str
    yfinance_version: str
    universe_version_hash: str
    window_start: str
    window_end: str
    trading_days: int
    tickers: int
    variants: tuple[int, ...]
    cache_stats: CacheStats
    absent_data_count: int
    dropped_signal_count: int
    study_design_commit: str
    notes: tuple[str, ...] = field(default_factory=tuple)


def _run_git(*args: str, repo_root: Path) -> str:
    """Run ``git`` with ``args`` from ``repo_root``; return stripped stdout or ''.

    Errors (non-repo, git missing) resolve to the empty string — manifest
    readers treat empty strings as "unknown at run time" rather than crashing
    the harness.
    """
    try:
        result = subprocess.run(
            ["git", *args],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
            check=False,
            timeout=10,
        )
    except (OSError, subprocess.TimeoutExpired):
        return ""
    return result.stdout.strip() if result.returncode == 0 else ""


def git_head_sha(repo_root: Path) -> str:
    return _run_git("rev-parse", "HEAD", repo_root=repo_root)


def git_is_dirty(repo_root: Path) -> bool:
    """True iff the working tree has uncommitted changes."""
    status = _run_git("status", "--porcelain", repo_root=repo_root)
    return bool(status)


def git_file_head_sha(repo_root: Path, relative_path: str) -> str:
    """SHA of the most recent commit that touched ``relative_path``."""
    return _run_git("log", "-1", "--format=%H", "--", relative_path, repo_root=repo_root)


def yfinance_version() -> str:
    try:
        import yfinance

        return str(yfinance.__version__)
    except (ImportError, AttributeError):
        return ""


def build_manifest(
    *,
    repo_root: Path,
    universe_version_hash: str,
    window_start: date,
    window_end: date,
    trading_days: int,
    tickers: int,
    variants: tuple[int, ...],
    cache_stats: CacheStats,
    absent_data_count: int,
    dropped_signal_count: int,
    study_design_path: str = "research/studies/earnings-proximity-exclusion.md",
    notes: tuple[str, ...] = (),
) -> RunManifest:
    """Populate a manifest from live git + environment state."""
    return RunManifest(
        git_sha=git_head_sha(repo_root),
        git_dirty=git_is_dirty(repo_root),
        run_ts=datetime.now(UTC).isoformat(),
        yfinance_version=yfinance_version(),
        universe_version_hash=universe_version_hash,
        window_start=window_start.isoformat(),
        window_end=window_end.isoformat(),
        trading_days=trading_days,
        tickers=tickers,
        variants=variants,
        cache_stats=cache_stats,
        absent_data_count=absent_data_count,
        dropped_signal_count=dropped_signal_count,
        study_design_commit=git_file_head_sha(repo_root, study_design_path),
        notes=notes,
    )


def write_manifest(manifest: RunManifest, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(asdict(manifest), indent=2, default=str))
