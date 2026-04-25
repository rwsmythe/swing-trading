"""Production-DB read for the Finviz-pool binding-constraint analysis.

Reads ``evaluation_runs`` + ``candidates`` + ``candidate_criteria`` from
the production SQLite DB. Resolves each run's ``finviz_csv_path`` against
``data/finviz-inbox/`` (top level + ``rejected/`` subdirectory) by literal
basename match. Runs whose CSV cannot be resolved are placed in the
``skipped`` list, NOT silently dropped.

Phase isolation: read-only over the production DB. Reuses
``swing.data.repos.candidates.fetch_candidates_for_run``.
"""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from pathlib import Path, PureWindowsPath
from typing import Literal

from swing.data.models import Candidate
from swing.data.repos.candidates import fetch_candidates_for_run

ResolvedLocation = Literal["inbox", "rejected"]


@dataclass(frozen=True)
class QualifyingRun:
    """One qualifying evaluation_run — its CSV is present on disk."""
    run_id: int
    run_ts: str
    action_session_date: str
    data_asof_date: str
    finviz_csv_path: str
    finviz_csv_basename: str
    resolved_location: ResolvedLocation


@dataclass(frozen=True)
class SkippedRun:
    """One skipped evaluation_run — its CSV cannot be located on disk."""
    run_id: int
    action_session_date: str
    finviz_csv_path: str | None
    finviz_csv_basename: str | None
    reason: str  # 'csv_path_null' | 'csv_missing'


def _basename_of(stored_path: str) -> str:
    """Extract a literal basename from a stored ``finviz_csv_path``.

    The DB contains a mix of Windows-style absolute paths
    (``C:\\Users\\...\\finviz19Apr2026.csv``) and relative POSIX-ish
    paths (``data/finviz-inbox/finviz19Apr2026.csv``). ``Path(...).name``
    on POSIX does NOT split on backslash, so we use ``PureWindowsPath``
    when a backslash is present and the OS-native ``Path`` otherwise.

    This is purely a basename extraction; it does NOT resolve or touch
    the filesystem.
    """
    if "\\" in stored_path:
        return PureWindowsPath(stored_path).name
    return Path(stored_path).name


def _resolve_csv(
    basename: str, finviz_inbox_dir: Path
) -> tuple[ResolvedLocation, Path] | None:
    """Resolve a basename against inbox top-level + ``rejected/``.

    Returns ``(location, resolved_path)`` if found, else ``None``. The
    ``rejected/`` subdirectory in production renames files with a
    timestamp suffix (e.g. ``finviz16Apr2026.rejected-20260419T064456.csv``);
    a literal basename from a stored ``finviz_csv_path`` will typically
    NOT resolve there. Documented at D1 §"Provenance commitments" as a
    methodological choice.
    """
    candidate = finviz_inbox_dir / basename
    if candidate.is_file():
        return "inbox", candidate
    rejected_candidate = finviz_inbox_dir / "rejected" / basename
    if rejected_candidate.is_file():
        return "rejected", rejected_candidate
    return None


def list_qualifying_evaluation_runs(
    conn: sqlite3.Connection,
    finviz_inbox_dir: Path,
) -> tuple[list[QualifyingRun], list[SkippedRun]]:
    """Partition all production ``evaluation_runs`` rows into qualifying + skipped.

    A run qualifies iff its ``finviz_csv_path`` (basename) resolves to a
    present file under ``finviz_inbox_dir`` or ``finviz_inbox_dir/rejected``.
    Path-NULL rows skip with reason ``"csv_path_null"``; path-non-NULL but
    not-on-disk rows skip with reason ``"csv_missing"``.

    Returns:
        (qualifying, skipped) lists, both ordered by ``run_id`` ASC for
        deterministic downstream iteration.
    """
    rows = conn.execute(
        """
        SELECT id, run_ts, data_asof_date, action_session_date, finviz_csv_path
        FROM evaluation_runs
        ORDER BY id
        """
    ).fetchall()

    qualifying: list[QualifyingRun] = []
    skipped: list[SkippedRun] = []
    for row in rows:
        run_id, run_ts, asof, action, csv_path = row
        if csv_path is None:
            skipped.append(
                SkippedRun(
                    run_id=run_id,
                    action_session_date=action,
                    finviz_csv_path=None,
                    finviz_csv_basename=None,
                    reason="csv_path_null",
                )
            )
            continue
        basename = _basename_of(csv_path)
        resolved = _resolve_csv(basename, finviz_inbox_dir)
        if resolved is None:
            skipped.append(
                SkippedRun(
                    run_id=run_id,
                    action_session_date=action,
                    finviz_csv_path=csv_path,
                    finviz_csv_basename=basename,
                    reason="csv_missing",
                )
            )
            continue
        location, _ = resolved
        qualifying.append(
            QualifyingRun(
                run_id=run_id,
                run_ts=run_ts,
                action_session_date=action,
                data_asof_date=asof,
                finviz_csv_path=csv_path,
                finviz_csv_basename=basename,
                resolved_location=location,
            )
        )
    return qualifying, skipped


def fetch_run_candidates_with_criteria(
    conn: sqlite3.Connection, evaluation_run_id: int
) -> list[Candidate]:
    """Read all candidates + criteria for one evaluation_run.

    Direct delegate to ``swing.data.repos.candidates.fetch_candidates_for_run``;
    kept as a named function in this module so the aggregator's import
    surface is the analysis package, not ``swing/`` directly. The
    consumed function is read-only.
    """
    return fetch_candidates_for_run(conn, evaluation_run_id)
