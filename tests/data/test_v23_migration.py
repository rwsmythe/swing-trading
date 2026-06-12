"""Phase 14 Sub-bundle 3 (T-3.1) v23 chart_renders.surface rename migration.

0023 atomically renames the surface enum value 'hyprec_detail' ->
'ticker_detail' via an id-preserving single-table rebuild. These tests cover:
schema-parity (only the one token changes), row rename + same-id preservation,
FK survival from pattern_detection_events.chart_render_id (ON DELETE SET NULL),
the STRICT-equality backup gate, twice-run no-op, mid-script rollback through
the real runner path (gotcha #9), foreign_keys restore on success + rollback
(finally-block discipline), and the dataclass validator rejecting the old token.
"""
import pathlib
import re
import sqlite3

import pytest

from swing.data import db
from swing.data.db import (
    EXPECTED_SCHEMA_VERSION,
    PHASE14_SB3_PRE_MIGRATION_EXPECTED_TABLES,
    _apply_migration,
    _current_version,
    _phase14_sb3_backup_gate,
    run_migrations,
)
from swing.data.models import ChartRender


# ---------------------------------------------------------------------------
# Fixture builders (gotcha #11: build a v22 fixture by RUNNING migrations to
# v22, then insert a real-shape row — never hand-write a v23-shape INSERT).
# ---------------------------------------------------------------------------

_CHART_RENDER_COLS = (
    "ticker, surface, pipeline_run_id, pattern_class, chart_svg_bytes, "
    "source_data_hash, rendered_at, data_asof_date"
)


def _make_file_v22_db(tmp_path):
    """A file-backed DB migrated to v22 with one 'hyprec_detail' row (id known)."""
    p = tmp_path / "swing.db"
    conn = sqlite3.connect(p)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=22, backup_dir=tmp_path)
    assert _current_version(conn) == 22
    conn.execute(
        f"INSERT INTO chart_renders ({_CHART_RENDER_COLS}) "
        "VALUES ('AAPL', 'hyprec_detail', NULL, NULL, ?, ?, ?, ?)",
        (b"<svg/>", "hash1", "2026-05-29T00:00:00Z", "2026-05-29"),
    )
    conn.commit()
    return conn, p


def _make_file_v21_db(tmp_path):
    """A file-backed DB migrated only to v21 (one below the SB3 gate boundary)."""
    p = tmp_path / "swing.db"
    conn = sqlite3.connect(p)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=21, backup_dir=tmp_path)
    assert _current_version(conn) == 21
    return conn, p


# A 0023 variant that raises mid-script BEFORE the final UPDATE/COMMIT so the
# runner's except -> rollback path fires (gotcha #9).
_BROKEN_0023_BEFORE_COMMIT = """BEGIN;
CREATE TABLE chart_renders_new (id INTEGER PRIMARY KEY);
THIS IS NOT VALID SQL BEFORE COMMIT;
UPDATE schema_version SET version = 23;
COMMIT;
"""


def _patch_0023_sql(monkeypatch, broken_sql):
    """Patch Path.read_text so the 0023 migration file returns broken_sql."""
    real_read = pathlib.Path.read_text

    def fake_read(self, *a, **k):
        if self.name.startswith("0023_"):
            return broken_sql
        return real_read(self, *a, **k)

    monkeypatch.setattr(pathlib.Path, "read_text", fake_read)


def _normalize(sql: str) -> str:
    """Strip quoting (\"/[]/`), collapse whitespace, lowercase."""
    s = sql.translate(str.maketrans("", "", '"[]`'))
    s = re.sub(r"\s+", " ", s)
    return s.strip().lower()


def _chart_renders_ddl(conn) -> str:
    parts = [
        conn.execute(
            "SELECT sql FROM sqlite_schema WHERE name='chart_renders'"
        ).fetchone()[0]
    ]
    for r in conn.execute(
        "SELECT sql FROM sqlite_schema WHERE type='index' "
        "AND tbl_name='chart_renders' AND sql IS NOT NULL ORDER BY name"
    ):
        parts.append(r[0])
    return "\n".join(parts)


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_expected_schema_version_is_23():
    assert EXPECTED_SCHEMA_VERSION == 29


def test_v23_migration_renames_existing_chart_renders_rows(tmp_path):
    conn, _ = _make_file_v22_db(tmp_path)
    row_id = conn.execute(
        "SELECT id FROM chart_renders WHERE ticker='AAPL'"
    ).fetchone()[0]
    run_migrations(conn, target_version=23, backup_dir=tmp_path)
    assert _current_version(conn) == 23
    surface = conn.execute(
        "SELECT surface FROM chart_renders WHERE id=?", (row_id,)
    ).fetchone()[0]
    assert surface == "ticker_detail"


def test_v23_migration_preserves_chart_render_fk_from_detection_events(tmp_path):
    conn, _ = _make_file_v22_db(tmp_path)
    render_id = conn.execute(
        "SELECT id FROM chart_renders WHERE ticker='AAPL'"
    ).fetchone()[0]
    conn.execute(
        "INSERT INTO pattern_detection_events "
        "(ticker, detection_date, data_asof_date, pattern_class, "
        " structural_anchors_json, composite_score, detector_version, source, "
        " per_pattern_metadata_json, chart_render_id, created_at) "
        "VALUES ('AAPL','2026-05-29','2026-05-28','vcp','{}',0.5,'v1',"
        "'pipeline','{}',?,'2026-05-29T00:00:00Z')",
        (render_id,),
    )
    conn.commit()
    run_migrations(conn, target_version=23, backup_dir=tmp_path)
    assert _current_version(conn) == 23
    assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
    # Same id preserved + referencing row still resolves to the renamed row.
    resolved = conn.execute(
        "SELECT cr.id, cr.surface FROM pattern_detection_events pde "
        "JOIN chart_renders cr ON cr.id = pde.chart_render_id "
        "WHERE pde.ticker='AAPL'"
    ).fetchone()
    assert resolved[0] == render_id
    assert resolved[1] == "ticker_detail"


def test_v23_schema_parity_normalized_sql(tmp_path):
    conn, _ = _make_file_v22_db(tmp_path)
    before = _normalize(_chart_renders_ddl(conn))
    run_migrations(conn, target_version=23, backup_dir=tmp_path)
    after = _normalize(_chart_renders_ddl(conn))
    # The post-rebuild table is RENAMEd back to chart_renders, so normalized
    # DDL differs ONLY by the single enum token.
    assert before != after
    assert before.replace("'hyprec_detail'", "'ticker_detail'") == after


def test_v23_backup_gate_fires_strict_pre_version_22(tmp_path):
    conn, _ = _make_file_v22_db(tmp_path)
    run_migrations(conn, target_version=23, backup_dir=tmp_path)
    backups = list(tmp_path.glob("swing-pre-phase14-sb3-migration-*.db"))
    assert len(backups) == 1


def test_v23_backup_gate_skips_from_pre_v22(tmp_path):
    conn, _ = _make_file_v21_db(tmp_path)
    # A v21 DB walked to v23 must NOT write the SB3 backup (current != 22).
    run_migrations(conn, target_version=23, backup_dir=tmp_path)
    assert _current_version(conn) == 23
    assert list(tmp_path.glob("swing-pre-phase14-sb3-migration-*.db")) == []


def test_v23_backup_gate_direct_skips_non_v22(tmp_path):
    conn, _ = _make_file_v22_db(tmp_path)
    _phase14_sb3_backup_gate(
        conn, current_version=21, target_version=23, backup_dir=tmp_path,
    )
    _phase14_sb3_backup_gate(
        conn, current_version=23, target_version=23, backup_dir=tmp_path,
    )
    _phase14_sb3_backup_gate(
        conn, current_version=22, target_version=22, backup_dir=tmp_path,
    )  # target < 23
    assert list(tmp_path.glob("swing-pre-phase14-sb3-migration-*.db")) == []


def test_phase14_sb3_expected_tables_present():
    assert "chart_renders" in PHASE14_SB3_PRE_MIGRATION_EXPECTED_TABLES
    assert "pattern_detection_events" in PHASE14_SB3_PRE_MIGRATION_EXPECTED_TABLES
    assert (
        "pattern_forward_observations"
        in PHASE14_SB3_PRE_MIGRATION_EXPECTED_TABLES
    )


def test_run_migrations_twice_v23_no_op(tmp_path):
    conn, _ = _make_file_v22_db(tmp_path)
    run_migrations(conn, target_version=23, backup_dir=tmp_path)
    assert _current_version(conn) == 23
    run_migrations(conn, target_version=23, backup_dir=tmp_path)  # no-op
    assert _current_version(conn) == 23


def test_v23_migration_rollback_through_runner_leaves_v22(tmp_path, monkeypatch):
    conn, _ = _make_file_v22_db(tmp_path)
    _patch_0023_sql(monkeypatch, _BROKEN_0023_BEFORE_COMMIT)
    with pytest.raises(sqlite3.OperationalError):
        run_migrations(conn, target_version=23, backup_dir=tmp_path)
    assert conn.in_transaction is False
    assert _current_version(conn) == 22
    # The original 'hyprec_detail' row still present + unrenamed.
    surface = conn.execute(
        "SELECT surface FROM chart_renders WHERE ticker='AAPL'"
    ).fetchone()[0]
    assert surface == "hyprec_detail"


def test_apply_migration_restores_foreign_keys_after_v23(tmp_path):
    conn, _ = _make_file_v22_db(tmp_path)
    conn.execute("PRAGMA foreign_keys=ON")
    run_migrations(conn, target_version=23, backup_dir=tmp_path)
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_apply_migration_restores_foreign_keys_after_rollback(tmp_path, monkeypatch):
    conn, _ = _make_file_v22_db(tmp_path)
    conn.execute("PRAGMA foreign_keys=ON")
    _patch_0023_sql(monkeypatch, _BROKEN_0023_BEFORE_COMMIT)
    with pytest.raises(sqlite3.OperationalError):
        run_migrations(conn, target_version=23, backup_dir=tmp_path)
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1


def test_chart_render_dataclass_rejects_hyprec_detail():
    with pytest.raises(ValueError):
        ChartRender(
            id=None,
            ticker="AAPL",
            surface="hyprec_detail",
            chart_svg_bytes=b"<svg/>",
            source_data_hash="h",
            rendered_at="2026-05-29T00:00:00Z",
            data_asof_date="2026-05-29",
        )
