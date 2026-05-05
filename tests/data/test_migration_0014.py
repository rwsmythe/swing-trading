"""Phase 7 migration 0014 smoke test.

Smoke-only at T2; full preservation invariant tests land in T9; in-flight
VIR/DHC/CC/YOU migration tests land in T10.
"""
from __future__ import annotations

import math
import sqlite3
from pathlib import Path

from swing.trades.derived_metrics import (
    initial_risk_per_share,
    r_multiple,
    realized_pnl,
)


def _seed_v13_db(path: Path) -> sqlite3.Connection:
    """Build a schema-version-13 DB. Uses the public run_migrations API."""
    from swing.data.db import run_migrations
    conn = sqlite3.connect(path)
    run_migrations(conn, target_version=13)
    return conn


def test_migration_0014_smoke(tmp_path):
    """0014 applies cleanly to an empty (no trades) v13 DB; schema_version → 14."""
    from swing.data.db import run_migrations

    db = tmp_path / "test.db"
    conn = _seed_v13_db(db)
    run_migrations(conn, target_version=14, backup_dir=tmp_path)

    # schema_version bumped.
    cur = conn.execute("SELECT version FROM schema_version")
    assert cur.fetchone()[0] == 14

    # New table fills exists.
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='fills'"
    ).fetchall()
    assert len(rows) == 1, "fills table should exist post-0014"

    # Old table exits is dropped.
    rows = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='exits'"
    ).fetchall()
    assert len(rows) == 0, "exits table should be dropped post-0014"

    # status column dropped from trades; state + new cols added.
    cols = {row[1] for row in conn.execute("PRAGMA table_info(trades)")}
    assert "status" not in cols, "status column should be dropped"
    assert "state" in cols
    assert "trade_origin" in cols
    assert "pre_trade_locked_at" in cols
    assert "current_size" in cols
    assert "current_avg_cost" in cols
    assert "last_fill_at" in cols
    # Sample of pre-trade decision fields:
    for f in ("thesis", "why_now", "invalidation_condition",
              "expected_scenario", "premortem_technical",
              "emotional_state_pre_trade", "catalyst"):
        assert f in cols, f"missing pre-trade field: {f}"

    # state CHECK enum enforced.
    with sqlite3.connect(db) as bad_conn:
        # Insert a trade with an invalid state — expect CHECK violation.
        try:
            bad_conn.execute(
                "INSERT INTO trades (ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, state, "
                "trade_origin, pre_trade_locked_at) "
                "VALUES ('AAA','2026-01-01',10.0,1,9.0,9.0,'bogus',"
                "'manual_off_pipeline','2026-01-01T16:00:00')"
            )
            bad_conn.commit()
            raise AssertionError("expected CHECK violation on state='bogus'")
        except sqlite3.IntegrityError:
            pass

    # trade_origin CHECK enum enforced.
    with sqlite3.connect(db) as bad_conn:
        try:
            bad_conn.execute(
                "INSERT INTO trades (ticker, entry_date, entry_price, "
                "initial_shares, initial_stop, current_stop, state, "
                "trade_origin, pre_trade_locked_at) "
                "VALUES ('BBB','2026-01-01',10.0,1,9.0,9.0,'entered',"
                "'bogus_origin','2026-01-01T16:00:00')"
            )
            bad_conn.commit()
            raise AssertionError("expected CHECK violation on trade_origin='bogus_origin'")
        except sqlite3.IntegrityError:
            pass

    # New event_type 'pre_trade_edit' is allowed in trade_events CHECK.
    with sqlite3.connect(db) as ev_conn:
        # Need a trade row first to satisfy FK.
        ev_conn.execute(
            "INSERT INTO trades (id, ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, "
            "trade_origin, pre_trade_locked_at) "
            "VALUES (1,'CCC','2026-01-01',10.0,1,9.0,9.0,'entered',"
            "'manual_off_pipeline','2026-01-01T16:00:00')"
        )
        ev_conn.execute(
            "INSERT INTO trade_events (trade_id, ts, event_type, payload_json) "
            "VALUES (1, '2026-01-01T17:00:00', 'pre_trade_edit', '{}')"
        )
        ev_conn.commit()
        # Verify it landed.
        row = ev_conn.execute(
            "SELECT event_type FROM trade_events WHERE trade_id = 1"
        ).fetchone()
        assert row[0] == "pre_trade_edit"


def test_migration_0014_idempotent(tmp_path):
    """Running run_migrations against an already-v14 DB is a no-op (returns
    without re-applying)."""
    from swing.data.db import run_migrations

    db = tmp_path / "test.db"
    conn = _seed_v13_db(db)
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    # Second invocation should not re-apply (no error; schema_version still 14).
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    cur = conn.execute("SELECT version FROM schema_version")
    assert cur.fetchone()[0] == 14


def _seed_v13_with_trades_and_exits(tmp_path, trade_specs, exit_specs):
    """Build a v13 DB seeded with the given trades + exits (legacy schema).

    trade_specs format (8-tuple):
      (id, ticker, entry_date, entry_price, initial_shares,
       initial_stop, current_stop, status)
    exit_specs format (9-tuple):
      (id, trade_id, exit_date, exit_price, shares, reason,
       realized_pnl, r_multiple, notes)
    """
    from swing.data.db import run_migrations
    db = tmp_path / "test.db"
    conn = sqlite3.connect(db)
    run_migrations(conn, target_version=13)
    for spec in trade_specs:
        conn.execute(
            "INSERT INTO trades (id, ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, status) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            spec,
        )
    for spec in exit_specs:
        conn.execute(
            "INSERT INTO exits (id, trade_id, exit_date, exit_price, "
            "shares, reason, realized_pnl, r_multiple, notes) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            spec,
        )
    conn.commit()
    return conn, db


def test_preservation_invariant_singleton_exit(tmp_path):
    """One trade with one full exit (mirrors VIR shape).

    Per spec §4.4.1 binding: assert post-migration fills row contents +
    realized_pnl/r_multiple via T8 formulas match pre-migration stored values.
    """
    from swing.data.db import run_migrations
    trades = [
        (1, "AAA", "2026-04-20", 11.30, 2, 8.26, 8.26, "closed"),
    ]
    exits_data = [
        (1, 1, "2026-04-24", 10.30, 2, "stop-hit", -2.0,
         -0.32894736842105254, None),
    ]
    conn, _ = _seed_v13_with_trades_and_exits(tmp_path, trades, exits_data)
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    fills = conn.execute(
        "SELECT action, quantity, price, reason, fill_datetime "
        "FROM fills ORDER BY fill_datetime ASC, fill_id ASC"
    ).fetchall()
    assert len(fills) == 2  # 1 entry + 1 exit
    assert fills[0] == ("entry", 2.0, 11.30, None, "2026-04-20T16:00:00")
    assert fills[1] == ("exit", 2.0, 10.30, "stop-hit", "2026-04-24T16:00:00")

    # Re-compute realized_pnl + r_multiple via T8 derived_metrics; assert
    # preservation.
    pnl = realized_pnl(entry_price=11.30, exit_price=10.30, quantity=2.0)
    risk = initial_risk_per_share(entry_price=11.30, initial_stop=8.26)
    r = r_multiple(realized_pnl=pnl, initial_risk_per_share=risk, quantity=2.0)
    assert math.isclose(pnl, -2.0, abs_tol=1e-9)
    assert math.isclose(r, -0.32894736842105254, abs_tol=1e-12)


def test_preservation_invariant_multi_exit_different_dates(tmp_path):
    """Trade with 3 exits across 3 dates totaling initial_shares.

    Asserts full backfilled fills row contents (action, quantity, price,
    reason, fill_datetime) per spec §4.4.1: each row's structured contents
    are proven, not just the action sequence."""
    from swing.data.db import run_migrations
    trades = [
        (1, "BBB", "2026-04-01", 100.0, 30, 95.0, 95.0, "closed"),
    ]
    exits_data = [
        (1, 1, "2026-04-05", 105.0, 10, "trim-1",      50.0, 1.0, None),
        (2, 1, "2026-04-10", 110.0, 10, "trim-2",     100.0, 2.0, None),
        (3, 1, "2026-04-15", 115.0, 10, "exit-final", 150.0, 3.0, None),
    ]
    conn, _ = _seed_v13_with_trades_and_exits(tmp_path, trades, exits_data)
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    fills = conn.execute(
        "SELECT action, quantity, price, reason, fill_datetime "
        "FROM fills WHERE trade_id = 1 AND action != 'entry' "
        "ORDER BY fill_datetime ASC, fill_id ASC"
    ).fetchall()
    assert fills == [
        ("trim", 10.0, 105.0, "trim-1",     "2026-04-05T16:00:00"),
        ("trim", 10.0, 110.0, "trim-2",     "2026-04-10T16:00:00"),
        ("exit", 10.0, 115.0, "exit-final", "2026-04-15T16:00:00"),
    ]
    # Per-row realized_pnl preservation (computed via derived_metrics).
    for stored, fill in zip(exits_data, fills, strict=True):
        stored_pnl = stored[6]
        computed_pnl = realized_pnl(
            entry_price=100.0, exit_price=fill[2], quantity=fill[1]
        )
        assert math.isclose(stored_pnl, computed_pnl, abs_tol=1e-9)


def test_preservation_invariant_same_date_multi_exit(tmp_path):
    """Trade with 3 exits on same date totaling initial_shares —
    deterministic ordering by (exit_date ASC, id ASC) drives action
    assignment.

    Asserts full row contents in id-ASC order: backfill SQL's tie-break on
    `id ASC` for same-date rows is the discriminator."""
    from swing.data.db import run_migrations
    trades = [
        (1, "CCC", "2026-04-01", 50.0, 30, 47.0, 47.0, "closed"),
    ]
    exits_data = [
        (1, 1, "2026-04-05", 52.0, 10, "trim-A", 20.0, 0.67, None),
        (2, 1, "2026-04-05", 53.0, 10, "trim-B", 30.0, 1.0,  None),
        (3, 1, "2026-04-05", 54.0, 10, "exit-C", 40.0, 1.33, None),
    ]
    conn, _ = _seed_v13_with_trades_and_exits(tmp_path, trades, exits_data)
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    fills = conn.execute(
        "SELECT action, quantity, price, reason, fill_datetime "
        "FROM fills WHERE trade_id = 1 AND action != 'entry' "
        "ORDER BY fill_id ASC"
    ).fetchall()
    assert fills == [
        ("trim", 10.0, 52.0, "trim-A", "2026-04-05T16:00:00"),
        ("trim", 10.0, 53.0, "trim-B", "2026-04-05T16:00:00"),
        ("exit", 10.0, 54.0, "exit-C", "2026-04-05T16:00:00"),
    ]


def test_preservation_invariant_notes_merged(tmp_path):
    """Exit row with non-empty notes; post-migration, fill.reason =
    reason + ' | ' + notes.

    Asserts ALL row fields (action, quantity, price, reason, fill_datetime)
    — not just the merged reason — to prove the migration backfill writes a
    complete row."""
    from swing.data.db import run_migrations
    trades = [
        (1, "DDD", "2026-04-01", 20.0, 100, 19.0, 19.0, "closed"),
    ]
    exits_data = [
        (1, 1, "2026-04-05", 22.0, 100, "target hit", 200.0, 2.0,
         "early bias good"),
    ]
    conn, _ = _seed_v13_with_trades_and_exits(tmp_path, trades, exits_data)
    run_migrations(conn, target_version=14, backup_dir=tmp_path)
    row = conn.execute(
        "SELECT action, quantity, price, reason, fill_datetime "
        "FROM fills WHERE trade_id = 1 AND action = 'exit'"
    ).fetchone()
    assert row == (
        "exit", 100.0, 22.0,
        "target hit | early bias good",
        "2026-04-05T16:00:00",
    )


def test_in_flight_migration_vir_dhc_cc_you(tmp_path):
    """Spec §12.3: production-shape fixture migrates VIR + DHC + CC + YOU
    correctly.

    NOTE: this fixture mirrors the production DB shape verified at
    empirical audit time (HEAD aa2dd60 → eba1625, 2026-05-04). YOU was
    added 2026-05-04 between writing-plans dispatch (251cc35) and Sub-A
    dispatch — operator-confirmed FIRM trade_origin = pipeline_aplus per
    spec §10.4.
    """
    from swing.data.db import run_migrations

    trades = [
        # VIR: closed + reviewed (Phase 6 review surface populated
        # reviewed_at).
        (1, "VIR", "2026-04-20", 11.30, 2, 8.26, 8.26, "closed"),
        # DHC: open since 2026-04-27, $7.58 × 39, initial_stop 6.56.
        (2, "DHC", "2026-04-27", 7.58, 39, 6.56, 7.28, "open"),
        # CC: open since 2026-04-30, $26.97 × 5.
        (3, "CC", "2026-04-30", 26.97, 5, 20.51, 20.51, "open"),
        # YOU: open since 2026-05-04, $56.29 × 2 (4th trade entered between
        # writing-plans dispatch and Sub-A dispatch; A+ entry; bucket=aplus).
        (4, "YOU", "2026-05-04", 56.29, 2, 45.38, 45.38, "open"),
    ]
    exits_data = [
        # VIR's single full exit at -0.33R (per production DB).
        (1, 1, "2026-04-24", 10.30, 2, "stop-hit", -2.0,
         -0.32894736842105254, None),
    ]
    conn, _ = _seed_v13_with_trades_and_exits(tmp_path, trades, exits_data)
    # Phase 6: VIR was reviewed; mark reviewed_at to drive state='reviewed'.
    conn.execute(
        "UPDATE trades SET reviewed_at = '2026-05-04T10:00:00' WHERE id = 1"
    )
    conn.commit()

    run_migrations(conn, target_version=14, backup_dir=tmp_path)

    # Verify per-trade state assignment.
    rows = conn.execute(
        "SELECT ticker, state, current_size, current_avg_cost, "
        "last_fill_at, trade_origin, pre_trade_locked_at "
        "FROM trades ORDER BY id"
    ).fetchall()
    vir, dhc, cc, you = rows
    assert vir == ("VIR", "reviewed", 0.0,  11.30, "2026-04-24T16:00:00",
                   "manual_off_pipeline",     "2026-04-20T16:00:00")
    assert dhc == ("DHC", "managing", 39.0, 7.58,  "2026-04-27T16:00:00",
                   "pipeline_watch_hyp_recs", "2026-04-27T16:00:00")
    assert cc  == ("CC",  "managing", 5.0,  26.97, "2026-04-30T16:00:00",
                   "pipeline_watch_hyp_recs", "2026-04-30T16:00:00")
    assert you == ("YOU", "managing", 2.0,  56.29, "2026-05-04T16:00:00",
                   "pipeline_aplus",          "2026-05-04T16:00:00")

    # Verify fills row count = #trades + #exits = 4 + 1 = 5.
    fill_count = conn.execute("SELECT COUNT(*) FROM fills").fetchone()[0]
    assert fill_count == 5

    # Verify VIR's pre-trade fields persist NULL (legacy migration backfill).
    row = conn.execute(
        "SELECT thesis, premortem_technical, emotional_state_pre_trade "
        "FROM trades WHERE ticker='VIR'"
    ).fetchone()
    assert row == (None, None, None)


def test_migration_0014_preserves_fills_and_trade_events_under_foreign_keys_on(tmp_path):
    """Hotfix regression: with PRAGMA foreign_keys=ON (production setting),
    migration 0014's table-rebuild step (DROP TABLE trades) must NOT cascade-
    delete the just-populated fills + pre-existing trade_events.

    Pre-hotfix root cause: step 10's DROP TABLE trades (during the CREATE-COPY-
    DROP-RENAME rebuild) triggers ON DELETE CASCADE on fills.trade_id and
    trade_events.trade_id when foreign_keys=ON. Production wiped 5 fills (4
    entry-fills synthesized in step 2 + 1 exit-fill from step 3) AND all 11
    trade_events audit-log rows during the rebuild.

    Sub-A T10 test passed because its fixture connection had foreign_keys=OFF
    (sqlite3 default for fresh connections); the test couldn't discriminate
    "fills/trade_events preserved under FK enforcement" from "fills/trade_events
    preserved because CASCADE didn't fire." Production's ensure_schema sets
    foreign_keys=ON explicitly, so the cascade fired in production.

    Hotfix lands in `swing/data/db.py:_apply_migration` — toggles
    foreign_keys=OFF before executescript + restores prior value after. Per
    SQLite docs §11.2, table-rebuild migrations should disable FK enforcement
    for the duration. Applies to all current + future migrations through the
    runner.

    Discriminating shape: this test sets foreign_keys=ON BEFORE the migration.
    Pre-hotfix: post-migration fills count == 0, trade_events count == 0
    (cascade wiped both). Post-hotfix: fills count == 2 (1 entry + 1 exit),
    trade_events count == 2 (preserved through table-rebuild).
    """
    from swing.data.db import run_migrations

    trades = [(1, "VIR", "2026-04-20", 11.30, 2, 10.30, 10.30, "closed")]
    exits_data = [(1, 1, "2026-04-24", 10.30, 2, "stop-hit", -2.0, -1.0, None)]
    conn, db = _seed_v13_with_trades_and_exits(tmp_path, trades, exits_data)

    # Seed audit-log entries — Sub-A T10 fixture didn't have these, which is
    # why production loss of 11 trade_events rows wasn't caught at test time.
    conn.executemany(
        "INSERT INTO trade_events (trade_id, ts, event_type, payload_json, "
        "rationale, notes) VALUES (?, ?, ?, ?, ?, ?)",
        [
            (1, "2026-04-20T06:58:55", "entry", "{}", "Other", None),
            (1, "2026-04-24T04:52:23", "exit", "{}", "Stop hit, auto-sell", None),
        ],
    )
    # Mark VIR reviewed so step 5's state-backfill assigns 'reviewed' (matches
    # the production-equivalent state for the in-flight trade).
    conn.execute(
        "UPDATE trades SET reviewed_at = '2026-05-04T10:00:00' WHERE id = 1"
    )
    conn.commit()

    # Production-equivalent FK enforcement (db.ensure_schema sets this ON).
    conn.execute("PRAGMA foreign_keys=ON")
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1

    run_migrations(conn, target_version=14, backup_dir=tmp_path)

    # Discriminating asserts: data preserved across step-10 trades-rebuild.
    fill_count = conn.execute("SELECT COUNT(*) FROM fills").fetchone()[0]
    assert fill_count == 2, (
        f"Expected 2 fills (1 entry + 1 exit) preserved across trades-rebuild; "
        f"got {fill_count}. Pre-hotfix value would be 0 due to CASCADE on DROP TABLE."
    )

    event_count = conn.execute("SELECT COUNT(*) FROM trade_events").fetchone()[0]
    assert event_count == 2, (
        f"Expected 2 trade_events preserved across trades-rebuild; got "
        f"{event_count}. Pre-hotfix value would be 0 due to CASCADE on DROP TABLE."
    )

    # Verify the runner restored foreign_keys=ON after migration (the hotfix
    # toggles OFF for the duration; restore is part of the contract).
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1, (
        "Hotfix runner must restore prior foreign_keys value (ON in this test) "
        "after migration completes."
    )


def test_migration_runner_preserves_foreign_keys_off_state(tmp_path):
    """Companion to the FK-on regression: when caller sets foreign_keys=OFF
    before migration, runner must NOT silently re-enable it. Hotfix's restore
    semantics: save prior value + restore exactly that value (don't assume ON).
    """
    from swing.data.db import run_migrations

    db = tmp_path / "test_fk_off.db"
    conn = sqlite3.connect(db)
    conn.execute("PRAGMA foreign_keys=OFF")
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 0

    run_migrations(conn, target_version=14, backup_dir=tmp_path)

    # Runner must have restored the prior OFF value, not silently set ON.
    assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 0, (
        "Hotfix runner must restore prior foreign_keys value (OFF in this test) "
        "after migration completes; must NOT silently force ON."
    )
