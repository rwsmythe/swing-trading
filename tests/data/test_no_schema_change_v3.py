"""L3: the schwabdev v3 migration changes NO swing-DB schema (the tokens DB is
schwabdev-internal SQLite under ~/swing-data/, not the swing.db)."""
import pathlib

from swing.data.db import EXPECTED_SCHEMA_VERSION

MIG = pathlib.Path(__file__).resolve().parents[2] / "swing" / "data" / "migrations"


def test_expected_schema_version_unchanged() -> None:
    assert EXPECTED_SCHEMA_VERSION == 23


def test_no_new_migration_file_added() -> None:
    # Highest existing migration is 0023 for v23; assert no 0024+ appeared.
    versions = sorted(int(p.name[:4]) for p in MIG.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    assert versions[-1] <= 23, f"a new migration file was added: {versions[-1]} (L3 violation)"
