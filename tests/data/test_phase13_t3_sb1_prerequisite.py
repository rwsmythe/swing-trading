"""Phase 13 T3.SB1 task T-B.1.1 — schema-version-20 prerequisite test.

Per plan §G.2 T-B.1.1 step 2 + dispatch brief §5 watch item 2: verifies the
T3.SB1 worktree branched off T2.SB1's T-A.1.1 commit SHA so the v20 schema
substrate is in place BEFORE T-B.1.2 starts building on top of it.

If this test fails, T3.SB1 worktree was branched off the wrong SHA — STOP and
escalate per dispatch brief §8.

Discriminates against:
  - Worktree branched off main HEAD (would lack v20 schema entirely).
  - Worktree branched off a stale T2.SB1 SHA before T-A.1.1 landed
    (would lack all 5 new tables + 4 fills columns + widened CHECK).
"""
from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from swing.data.db import EXPECTED_SCHEMA_VERSION, ensure_schema
from swing.integrations.schwab.audit_service import _SCHWAB_API_SURFACE_VALUES


def _extract_check_values_from_sql(sql: str, column: str) -> set[str]:
    """Pull the literal string values from a CHECK (<column> IN (...)) clause.

    Tolerant of whitespace + line breaks. Returns the set of single-quoted
    string literals inside the first matching IN-list following the column
    reference. Mirrors the helper in tests/data/test_v20_migration.py —
    kept inlined so this prerequisite test is self-contained.
    """
    pattern = re.compile(
        rf"{re.escape(column)}\s+IN\s*\(([^)]*?)\)",
        flags=re.IGNORECASE | re.DOTALL,
    )
    match = pattern.search(sql)
    assert match is not None, (
        f"CHECK IN clause for {column!r} not found in SQL:\n{sql}"
    )
    return set(re.findall(r"'([^']+)'", match.group(1)))


def test_schema_version_is_20(tmp_path: Path) -> None:
    """T-B.1.1 prerequisite: EXPECTED_SCHEMA_VERSION pinned (now v22 post-Phase-14-SB2).

    Fails fast if worktree branched off pre-T-A.6c.1 SHA. The pin originally
    landed at T3.SB1 expecting v20; T2.SB6c (migration 0021) bumped the head
    to v21; Phase 14 Sub-bundle 2 (migration 0022) bumps it to v22. Test name
    preserved to keep grep-history continuity per cumulative discipline (the
    corresponding tests in test_migration_0017.py etc. follow the same
    stale-name-but-current-assertion pattern).
    """
    assert EXPECTED_SCHEMA_VERSION == 30, (
        f"Worktree branched off wrong SHA - expected v23 schema, "
        f"got v{EXPECTED_SCHEMA_VERSION}. Re-create worktree off the "
        f"current head SHA."
    )


def test_fills_has_phase13_audit_columns(tmp_path: Path) -> None:
    """T-B.1.1 prerequisite: 4 new fills columns landed at v20.

    Per migration 0020 §7. T-B.1.4 persists into these columns.
    """
    db_path = tmp_path / "prereq_fills_cols.db"
    conn = ensure_schema(db_path)
    cols = {
        r[1] for r in conn.execute("PRAGMA table_info(fills)").fetchall()
    }
    conn.close()
    expected_new = {
        "fill_origin",
        "schwab_source_value_json",
        "operator_corrected_value_json",
        "auto_fill_audit_at",
    }
    missing = expected_new - cols
    assert not missing, (
        f"fills missing Phase 13 audit columns: {sorted(missing)}. "
        f"Re-verify worktree branched off T-A.1.1 SHA."
    )


def test_fills_fill_origin_check_enum(tmp_path: Path) -> None:
    """T-B.1.1 prerequisite: fill_origin CHECK enum lists all 5 V1 values.

    Per migration 0020 §7 + spec §6.4 + plan §E.1 LOCK.
    """
    db_path = tmp_path / "prereq_fill_origin_check.db"
    conn = ensure_schema(db_path)
    row = conn.execute(
        "SELECT sql FROM sqlite_master WHERE type='table' AND name='fills'"
    ).fetchone()
    conn.close()
    assert row is not None
    fills_sql: str = row[0]
    values = _extract_check_values_from_sql(fills_sql, "fill_origin")
    expected = {
        "operator_typed",
        "schwab_auto",
        "schwab_auto_then_operator_corrected",
        "tos_import",
        "imported_legacy",
    }
    assert values == expected, (
        f"fill_origin CHECK enum drift: extra={sorted(values - expected)} "
        f"missing={sorted(expected - values)}"
    )


def test_schwab_api_calls_surface_check_widened(tmp_path: Path) -> None:
    """T-B.1.1 prerequisite: schwab_api_calls.surface CHECK widened 2 → 4.

    Per migration 0020 §6 + spec §6.4 + plan §A.14 paired-atomic-landing LOCK.
    Mirrors the Python-side constant at
    ``swing/integrations/schwab/audit_service.py:_SCHWAB_API_SURFACE_VALUES``.
    """
    db_path = tmp_path / "prereq_surface_check.db"
    conn = ensure_schema(db_path)
    row = conn.execute(
        "SELECT sql FROM sqlite_master "
        "WHERE type='table' AND name='schwab_api_calls'"
    ).fetchone()
    conn.close()
    assert row is not None
    sac_sql: str = row[0]
    values = _extract_check_values_from_sql(sac_sql, "surface")
    expected = {"pipeline", "cli", "trade_entry", "trade_exit"}
    assert values == expected, (
        f"schwab_api_calls.surface CHECK enum drift: "
        f"extra={sorted(values - expected)} "
        f"missing={sorted(expected - values)}"
    )
    # Python-side constant parity (CLAUDE.md schema-CHECK + Python-constant
    # paired-discipline gotcha).
    assert set(_SCHWAB_API_SURFACE_VALUES) == expected


def test_t_a_1_1_sha_is_branch_base() -> None:
    """T-B.1.1 prerequisite: branch base is T2.SB1's T-A.1.1 commit SHA
    per OQ-12 Option E + dispatch brief §1.2.

    SHA cited verbatim in the dispatch brief + return report. This test
    asserts the T-A.1.1 commit is in the branch's ancestor history (i.e.,
    the worktree was created from it).
    """
    # The SHA the orchestrator dispatched us with; cited verbatim in the
    # return report header (dispatch brief §5 — return report cites
    # SHA verbatim).
    expected_sha = "4cfd5f2ca9b0103231fb558b141cd87132939d12"
    # Locate the project root by walking up from this test file.
    here = Path(__file__).resolve()
    repo_root = here.parent.parent.parent
    # Sanity: this should be the worktree root.
    assert (repo_root / "swing").is_dir(), (
        f"could not locate worktree root from {here}"
    )
    git_dir = repo_root / ".git"
    # In a worktree, .git is a FILE that points at the actual gitdir.
    # We only need to verify the SHA is reachable from HEAD via git.
    # Use git CLI via subprocess (no shell expansion needed; pure args).
    import subprocess
    result = subprocess.run(
        ["git", "merge-base", "--is-ancestor", expected_sha, "HEAD"],
        cwd=str(repo_root),
        capture_output=True,
        text=True,
    )
    # `git merge-base --is-ancestor` exits 0 if A is an ancestor of B,
    # exits 1 otherwise.
    assert result.returncode == 0, (
        f"T-A.1.1 SHA {expected_sha} is NOT an ancestor of HEAD. "
        f"T3.SB1 worktree branched off wrong SHA — re-create per "
        f"dispatch brief §1.2: "
        f"git worktree add .worktrees/phase13-t3-sb1-entry-auto-fill "
        f"{expected_sha} -b phase13-t3-sb1-entry-auto-fill. "
        f"Output: stderr={result.stderr!r} stdout={result.stdout!r}"
    )
    # Belt-and-suspenders: also assert .git is present at repo_root (a
    # worktree has .git as a FILE not a directory, but it must exist).
    assert git_dir.exists(), f".git missing at {git_dir}"


def test_sqlite_connect_smoke(tmp_path: Path) -> None:
    """T-B.1.1 prerequisite smoke: ensure_schema() + connect + migrate
    cycle completes without exception against v20.
    """
    db_path = tmp_path / "smoke.db"
    conn = ensure_schema(db_path)
    try:
        # Verify schema_version row matches expected.
        row = conn.execute(
            "SELECT version FROM schema_version"
        ).fetchone()
        assert row is not None
        version = row[0]
        assert isinstance(version, int)
        assert version == EXPECTED_SCHEMA_VERSION == 30
        # Verify fills table is queryable with the new columns.
        # (Should succeed even with zero rows.)
        conn.execute(
            "SELECT fill_id, fill_origin, schwab_source_value_json, "
            "operator_corrected_value_json, auto_fill_audit_at FROM fills"
        ).fetchall()
        # Verify schwab_api_calls table is queryable.
        conn.execute(
            "SELECT call_id, surface FROM schwab_api_calls "
            "WHERE surface IN ('pipeline', 'cli', 'trade_entry', 'trade_exit')"
        ).fetchall()
    finally:
        conn.close()
        # Reach across the sqlite3 module reference to silence ruff F401
        # if subsequent edits remove the explicit import.
        _ = sqlite3
