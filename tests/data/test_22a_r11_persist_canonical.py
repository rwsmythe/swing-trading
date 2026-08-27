"""22-A round 11 -- PERSIST-CANONICAL, at the schema grain.

THE RULING THIS FILE ENCODES (CHARC, adopting RD's sentence verbatim):

    SQL VERIFIES A FACT; IT MUST NEVER RE-DERIVE A JUDGMENT ACROSS AN ENGINE
    BOUNDARY -- the twin mirrors the AUTHORITY by consuming its OUTPUT, not by
    reimplementing its reasoning.

Ten review rounds produced THREE distinct engine-semantic divergences, each
found only after the previous was fixed, because the citation trigger was
re-deriving a Python predicate in SQL.  The structural answer is to remove the
thing that diverges: the service canonicalises the envelope ONCE and PERSISTS
its reading, and the trigger compares STORED EQUALITY.

FROZEN CLOCK: nothing here reads a wall clock for an assertion.
"""
from __future__ import annotations

import sqlite3

import pytest

from swing.data.db import run_migrations


@pytest.fixture()
def conn(tmp_path):
    c = sqlite3.connect(tmp_path / "r11.db")
    c.execute("PRAGMA foreign_keys=ON")
    run_migrations(c)
    try:
        yield c
    finally:
        c.close()


def _seed_fill(conn, *, trade_id=1, envelope=None, action="entry"):
    conn.execute(
        "INSERT OR IGNORE INTO trades (id, ticker, entry_date, entry_price, "
        " initial_shares, initial_stop, current_stop, state, trade_origin, "
        " pre_trade_locked_at) "
        "VALUES (?, 'FTRE', '2026-08-17', 18.50, 2, 17.00, 17.00, 'entered', "
        " 'manual_off_pipeline', '2026-08-17T13:00:00')",
        (trade_id,),
    )
    cur = conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        " fill_origin, schwab_source_value_json) "
        "VALUES (?, '2026-08-17T14:30:00', ?, 2, 18.50, 'schwab_auto', ?)",
        (trade_id, action, envelope),
    )
    return int(cur.lastrowid)


def test_the_stored_identity_table_exists_with_its_declared_shape(conn) -> None:
    cols = {
        r[1]: (r[2], r[3])
        for r in conn.execute("PRAGMA table_info(fill_envelope_identity)")
    }
    assert cols, "fill_envelope_identity does not exist"
    assert set(cols) == {
        "identity_id", "fill_id", "envelope_raw", "envelope_state",
        "broker_order_id", "instrument_symbol", "canonicalizer_version",
        "recorded_ts",
    }
    # The two identity columns are TEXT on BOTH sides of every comparison the
    # trigger makes, which is what makes plain equality unambiguous.
    assert cols["broker_order_id"][0] == "TEXT"
    assert cols["instrument_symbol"][0] == "TEXT"
    assert cols["envelope_raw"][1] == 1, "envelope_raw must be NOT NULL"


def test_the_state_enum_is_two_valued_and_enforced(conn) -> None:
    fid = _seed_fill(conn, envelope='{"schwab_order_id": "1"}')
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO fill_envelope_identity (fill_id, envelope_raw, "
            " envelope_state, canonicalizer_version, recorded_ts) "
            "VALUES (?, '{}', 'maybe', 'v', '2026-08-26T00:00:00Z')",
            (fid,),
        )


def test_a_refused_reading_may_carry_no_identity(conn) -> None:
    fid = _seed_fill(conn, envelope='{"schwab_order_id": 1}')
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO fill_envelope_identity (fill_id, envelope_raw, "
            " envelope_state, broker_order_id, canonicalizer_version, "
            " recorded_ts) VALUES (?, '{}', 'refused', 'X', 'v', 'T')",
            (fid,),
        )


def test_the_identity_row_is_append_only_update_delete_and_replace(
        conn) -> None:
    assert conn.execute("PRAGMA recursive_triggers").fetchone()[0] == 0
    fid = _seed_fill(conn, envelope='{"schwab_order_id": "1002937461"}')
    conn.execute(
        "INSERT INTO fill_envelope_identity (fill_id, envelope_raw, "
        " envelope_state, broker_order_id, canonicalizer_version, recorded_ts) "
        "VALUES (?, '{\"schwab_order_id\": \"1002937461\"}', 'canonical', "
        " '1002937461', 'v1', '2026-08-26T00:00:00Z')",
        (fid,),
    )
    for stmt, args in (
        ("UPDATE fill_envelope_identity SET broker_order_id = 'X'", ()),
        ("DELETE FROM fill_envelope_identity", ()),
    ):
        with pytest.raises(sqlite3.IntegrityError) as exc:
            conn.execute(stmt, args)
        assert "22-A barrier" in str(exc.value)
    # REPLACE bypasses DELETE triggers at the default pragma -- the measured
    # hole this migration closes everywhere else.
    with pytest.raises(sqlite3.IntegrityError) as exc:
        conn.execute(
            "INSERT OR REPLACE INTO fill_envelope_identity "
            "(fill_id, envelope_raw, envelope_state, broker_order_id, "
            " canonicalizer_version, recorded_ts) "
            "VALUES (?, '{\"schwab_order_id\": \"1002937461\"}', 'canonical', "
            " '999', 'v1', '2026-08-26T00:00:00Z')",
            (fid,),
        )
    assert "trg_fei_no_replace" in str(exc.value)
    assert conn.execute(
        "SELECT broker_order_id FROM fill_envelope_identity"
    ).fetchone()[0] == "1002937461"


def test_one_reading_per_fill_and_document(conn) -> None:
    """UNIQUE(fill_id, envelope_raw): two disagreeing readings of the SAME
    document cannot coexist, so the trigger's lookup is single-valued."""
    fid = _seed_fill(conn, envelope='{"schwab_order_id": "A"}')
    conn.execute(
        "INSERT INTO fill_envelope_identity (fill_id, envelope_raw, "
        " envelope_state, broker_order_id, canonicalizer_version, recorded_ts) "
        "VALUES (?, 'DOC', 'canonical', 'A', 'v1', 'T')", (fid,))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO fill_envelope_identity (fill_id, envelope_raw, "
            " envelope_state, broker_order_id, canonicalizer_version, "
            " recorded_ts) VALUES (?, 'DOC', 'canonical', 'B', 'v1', 'T')",
            (fid,))
