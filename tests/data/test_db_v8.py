"""Migration 0008 — `hypothesis_registry` + initial v0.1 seed.

Per `docs/hypothesis-recommendation-backend-brief.md` §4.1:
- Table created with all required columns + status CHECK constraint
- Indexed on `status`
- 4 seed rows inserted at migration time (the frozen v0.1 plan)
- Re-running ensure_schema is idempotent (no duplicate seeds)
"""
from __future__ import annotations

from pathlib import Path

from swing.data.db import EXPECTED_SCHEMA_VERSION, ensure_schema


def test_migration_0008_creates_hypothesis_registry_table(tmp_db: Path):
    conn = ensure_schema(tmp_db)
    try:
        cols = conn.execute("PRAGMA table_info(hypothesis_registry)").fetchall()
        names = {c[1] for c in cols}
        # All required columns present
        assert names == {
            "id", "name", "statement", "target_sample_size",
            "decision_criteria", "status",
            "consecutive_loss_tripwire", "absolute_loss_tripwire_pct",
            "created_at", "status_changed_at", "status_change_reason", "notes",
        }
        # name UNIQUE
        idx_rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' "
            "AND tbl_name='hypothesis_registry'"
        ).fetchall()
        idx_names = [r[0] for r in idx_rows]
        # ix_hypothesis_status explicit index + the auto unique-name index
        assert any(n == "ix_hypothesis_status" for n in idx_names)
    finally:
        conn.close()


def test_migration_0008_seeds_four_active_hypotheses(tmp_db: Path):
    conn = ensure_schema(tmp_db)
    try:
        rows = conn.execute(
            "SELECT name, target_sample_size, status, "
            "consecutive_loss_tripwire, absolute_loss_tripwire_pct "
            "FROM hypothesis_registry ORDER BY id"
        ).fetchall()
        assert len(rows) == 4
        names = [r[0] for r in rows]
        assert names == [
            "A+ baseline",
            "Near-A+ defensible: extension test",
            "Sub-A+ VCP-not-formed",
            "Capital-blocked: smaller-position test",
        ]
        # All seeded as active
        assert all(r[2] == "active" for r in rows)
        # Tripwire values per brief §1
        targets = {r[0]: r[1] for r in rows}
        assert targets["A+ baseline"] == 20
        assert targets["Near-A+ defensible: extension test"] == 10
        assert targets["Sub-A+ VCP-not-formed"] == 5
        assert targets["Capital-blocked: smaller-position test"] == 10

        consec = {r[0]: r[3] for r in rows}
        assert consec["A+ baseline"] == 5
        assert consec["Near-A+ defensible: extension test"] == 4
        assert consec["Sub-A+ VCP-not-formed"] == 3
        assert consec["Capital-blocked: smaller-position test"] == 4

        # Absolute-loss tripwire is 5% per brief
        assert all(r[4] == 5.0 for r in rows)
    finally:
        conn.close()


def test_migration_0008_status_check_rejects_invalid(tmp_db: Path):
    import sqlite3

    conn = ensure_schema(tmp_db)
    try:
        try:
            conn.execute(
                "INSERT INTO hypothesis_registry "
                "(name, statement, target_sample_size, decision_criteria, "
                "status, consecutive_loss_tripwire, absolute_loss_tripwire_pct, "
                "created_at) VALUES "
                "('bad', 'bad', 1, 'bad', 'rabbit-hole', 1, 1.0, '2026-04-25')"
            )
            assert False, "expected CHECK to reject 'rabbit-hole' status"
        except sqlite3.IntegrityError:
            pass
    finally:
        conn.close()


def test_migration_0008_idempotent_on_re_apply(tmp_db: Path):
    """Running ensure_schema on a v8 DB must not re-insert seed rows."""
    ensure_schema(tmp_db).close()
    # Second invocation: schema already at expected version, must be a no-op
    conn = ensure_schema(tmp_db)
    try:
        n = conn.execute(
            "SELECT COUNT(*) FROM hypothesis_registry"
        ).fetchone()[0]
        assert n == 4, f"expected 4 seed rows, got {n}"
    finally:
        conn.close()


def test_expected_schema_version_is_19():
    assert EXPECTED_SCHEMA_VERSION == 19
