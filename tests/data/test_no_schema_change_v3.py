"""L3: the schwabdev v3 migration changes NO swing-DB schema (the tokens DB is
schwabdev-internal SQLite under ~/swing-data/, not the swing.db)."""
import pathlib

from swing.data.db import EXPECTED_SCHEMA_VERSION

MIG = pathlib.Path(__file__).resolve().parents[2] / "swing" / "data" / "migrations"


def test_expected_schema_version_unchanged() -> None:
    # The schwabdev-v3 arc itself made NO swing-DB change (it landed at v23). The
    # B-7 (Phase 15) arc subsequently bumped HEAD to v24 (migration 0024 adds the
    # nullable failure_mode column); this guard tracks the current HEAD so the
    # schwabdev-arc invariant (it added nothing of its own) stays auditable.
    assert EXPECTED_SCHEMA_VERSION == 27


def test_no_new_migration_file_added() -> None:
    # The schwabdev-v3 arc added NO migration of its own (it landed at v23).
    # This is a HEAD-tracking ceiling guard: the highest migration on disk must
    # not exceed the current EXPECTED_SCHEMA_VERSION (v27 today: B-7 0024,
    # phase16 0025, broad-watch 0026, entry_intent 0027). A higher number means
    # an unaccounted migration file slipped in.
    versions = sorted(int(p.name[:4]) for p in MIG.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    assert versions[-1] <= 27, f"a new migration file was added: {versions[-1]} (L3 violation)"
