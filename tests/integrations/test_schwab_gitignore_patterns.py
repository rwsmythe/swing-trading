"""T-A.0 — verify .gitignore patterns for Schwab tokens DBs + audit backups.

Per plan §F.2: `git check-ignore -v` must return non-empty for 5 sample token-DB
paths AND for the migration-backup pattern. Tests assert DISCRIMINATING match
reasons — the SPECIFIC Schwab patterns (not the broader `swing-data/` umbrella)
must be the matchers.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]

TOKEN_DB_SAMPLE_PATHS = [
    "swing-data/schwab-tokens.sandbox.db",
    "swing-data/schwab-tokens.production.db",
    "swing-data/schwab-tokens.production.db-journal",
    "swing-data/schwab-tokens.production.db-wal",
    "swing-data/schwab-tokens.production.db-shm",
]

TOKEN_DB_PATTERN_STEMS = [
    "swing-data/schwab-tokens.*.db",
    "swing-data/schwab-tokens.*.db-journal",
    "swing-data/schwab-tokens.*.db-shm",
    "swing-data/schwab-tokens.*.db-wal",
]

MIGRATION_BACKUP_SAMPLE = "swing-pre-phase11-schwab-migration-20260513T120000Z.db"
MIGRATION_BACKUP_PATTERN = "swing-pre-phase11-schwab-migration-*.db"


def _check_ignore(path: str) -> subprocess.CompletedProcess[str]:
    """Run `git check-ignore -v <path>` from the repo root."""
    return subprocess.run(
        ["git", "check-ignore", "-v", path],
        capture_output=True,
        text=True,
        cwd=REPO_ROOT,
        check=False,
    )


def _parse_check_ignore_pattern(stdout: str) -> str:
    """Parse the matching PATTERN column from `git check-ignore -v` output.

    Format: `<source-file>:<line>:<pattern>\\t<path>` — extract the third
    colon-separated field (the pattern) up to the tab. This isolates the
    matching rule from the file path being checked, so substring assertions
    on the pattern are not polluted by the path being checked.
    """
    line = stdout.strip().splitlines()[0]
    before_tab = line.split("\t", 1)[0]
    # `<source-file>:<line>:<pattern>` — pattern starts after the second colon.
    parts = before_tab.split(":", 2)
    assert len(parts) == 3, f"unexpected check-ignore format: {stdout!r}"
    return parts[2]


@pytest.mark.parametrize("sample_path", TOKEN_DB_SAMPLE_PATHS)
def test_schwab_token_db_sample_paths_are_gitignored(sample_path: str) -> None:
    """All 5 §F.2 sample paths are ignored per `git check-ignore -v`.

    Note on discrimination: the existing `swing-data/` umbrella rule (line 11)
    matches the directory, and gitignore short-circuits at the directory match
    — so the more-specific §F.2 patterns appended later cannot win the
    last-match-wins race for files INSIDE `swing-data/`. The §F.2 explicit
    patterns are intentional defense-in-depth + readability (per dispatch brief
    §Context lock: "do NOT remove the broader pattern, append the specific
    patterns AFTER it"); the binding acceptance is non-empty match per plan
    §F.2 ("`git check-ignore -v` returns non-empty for ALL 5 sample paths").
    Discrimination of §F.2's presence is carried by the migration-backup test
    below — that pattern lives at repo root and CAN only match via §F.2.
    """
    result = _check_ignore(sample_path)
    assert result.returncode == 0, (
        f"git check-ignore returned {result.returncode} for {sample_path!r}; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert result.stdout.strip(), (
        f"git check-ignore returned empty stdout for {sample_path!r} (expected match-reason)"
    )
    # The match-reason must reference SOMETHING in .gitignore — sanity check
    # that a non-Schwab rule (e.g., `*.pyc`) is not coincidentally winning.
    pattern = _parse_check_ignore_pattern(result.stdout)
    assert pattern in TOKEN_DB_PATTERN_STEMS or pattern == "swing-data/", (
        f"Match-reason PATTERN for {sample_path!r} is {pattern!r}; "
        f"expected the umbrella `swing-data/` rule OR one of the §F.2 "
        f"per-pattern lines {TOKEN_DB_PATTERN_STEMS}."
    )


def test_schwab_migration_backup_pattern_matches_dated_filename() -> None:
    """Migration-backup pattern matches `swing-pre-phase11-schwab-migration-*.db` filenames.

    Discriminating: assert the matching pattern is the SPECIFIC migration-backup
    pattern (not coincidentally caught by some other rule). This filename lives
    at the repo root, so the broader `swing-data/` umbrella does NOT cover it
    — the §F.2 explicit pattern is the only thing that can match.
    """
    result = _check_ignore(MIGRATION_BACKUP_SAMPLE)
    assert result.returncode == 0, (
        f"git check-ignore returned {result.returncode} for {MIGRATION_BACKUP_SAMPLE!r}; "
        f"stdout={result.stdout!r} stderr={result.stderr!r}"
    )
    assert result.stdout.strip(), (
        f"git check-ignore returned empty stdout for {MIGRATION_BACKUP_SAMPLE!r}"
    )
    pattern = _parse_check_ignore_pattern(result.stdout)
    assert pattern == MIGRATION_BACKUP_PATTERN, (
        f"Match-reason PATTERN for {MIGRATION_BACKUP_SAMPLE!r} is {pattern!r}; "
        f"expected §F.2 migration-backup pattern {MIGRATION_BACKUP_PATTERN!r}."
    )
