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
    assert EXPECTED_SCHEMA_VERSION == 35


def test_no_new_migration_file_added() -> None:
    # The schwabdev-v3 arc added NO migration of its own (it landed at v23).
    # This is a HEAD-tracking ceiling guard: the highest migration on disk must
    # not exceed the current EXPECTED_SCHEMA_VERSION (v28 today: B-7 0024,
    # phase16 0025, broad-watch 0026, entry_intent 0027, watchlist_pin 0028). A higher
    # number means an unaccounted migration file slipped in. Phase 18 Arc 18-C
    # adds 0030 (yfinance_calls audit); Phase 18 Arc 18-H.6 adds 0031
    # (untracked_broker_position enum widen); Phase 21 Arc 21-A adds 0032
    # (latch_view_events view telemetry) and Arc 21-B adds 0033
    # (latch_order_intents + the telemetry surface column); the H1
    # decision-criteria amendment adds 0034 (the V2.1 §VII.F governance
    # amendment); item-5 A-4 adds 0035 (the discrepancy_type enum widen
    # 11 -> 12 by table rebuild), so the ceiling is now 35.
    #
    # Raising this ceiling is the guard WORKING AS DESIGNED for an AUTHORIZED
    # migration (CHARC's section-3 pass). An UNAUTHORIZED one must still trip
    # it, which is why the bump belongs in the same commit as the migration and
    # nowhere else.
    versions = sorted(int(p.name[:4]) for p in MIG.glob("[0-9][0-9][0-9][0-9]_*.sql"))
    assert versions[-1] <= 35, f"a new migration file was added: {versions[-1]} (L3 violation)"
