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
        "VALUES (?, ?, '2026-08-17', 18.50, 2, 17.00, 17.00, 'entered', "
        " 'manual_off_pipeline', '2026-08-17T13:00:00')",
        (trade_id, f"TK{trade_id:02d}"),
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


# ---------------------------------------------------------------------------
# THE WRITER: every envelope-bearing fill carries its reading from birth.
# ---------------------------------------------------------------------------
def _insert_via_repo(conn, envelope, *, trade_id=1, action="entry"):
    from swing.data.models import Fill
    from swing.data.repos.fills import insert_fill_with_event
    conn.execute(
        "INSERT OR IGNORE INTO trades (id, ticker, entry_date, entry_price, "
        " initial_shares, initial_stop, current_stop, state, trade_origin, "
        " pre_trade_locked_at) "
        "VALUES (?, ?, '2026-08-17', 18.50, 2, 17.00, 17.00, 'entered', "
        " 'manual_off_pipeline', '2026-08-17T13:00:00')",
        (trade_id, f"TK{trade_id:02d}"),
    )
    return insert_fill_with_event(
        conn,
        Fill(fill_id=None, trade_id=trade_id,
             fill_datetime="2026-08-17T14:30:00",
             action=action, quantity=2, price=18.50,
             fill_origin="schwab_auto" if envelope else "operator_typed",
             schwab_source_value_json=envelope),
        event_ts="2026-08-17T14:30:00", emit_event=False,
    )


def test_the_fills_writer_persists_the_reading_for_an_envelope_bearing_fill(
        conn) -> None:
    fid = _insert_via_repo(
        conn,
        '{"schwab_order_id": "1007523377009", '
        '"schwab_instrument_symbol": "FTRE"}')
    row = conn.execute(
        "SELECT envelope_state, broker_order_id, instrument_symbol "
        "  FROM fill_envelope_identity WHERE fill_id = ?", (fid,)).fetchone()
    assert row == ("canonical", "1007523377009", "FTRE")


def test_a_fill_with_no_envelope_writes_no_reading_at_all(conn) -> None:
    """LOCK clause (a)/(d)'s subject: the ordinary path is untouched, and
    'untouched' includes writing nothing extra."""
    _insert_via_repo(conn, None)
    assert conn.execute(
        "SELECT COUNT(*) FROM fill_envelope_identity").fetchone()[0] == 0


def test_a_refused_document_is_recorded_as_refused_not_omitted(conn) -> None:
    """The difference between 'the authority refused this' and 'nobody has
    looked yet' is the whole reason the state column exists."""
    fid = _insert_via_repo(conn, '{"schwab_order_id": 1002937461}')
    assert conn.execute(
        "SELECT envelope_state, broker_order_id FROM fill_envelope_identity "
        " WHERE fill_id = ?", (fid,)).fetchone() == ("refused", None)


def test_recording_the_same_document_twice_is_idempotent(conn) -> None:
    from swing.data.repos.fill_envelope_identity import record_identity
    raw = '{"schwab_order_id": "A"}'
    fid = _insert_via_repo(conn, raw)
    record_identity(conn, fill_id=fid, envelope_raw=raw)
    assert conn.execute(
        "SELECT COUNT(*) FROM fill_envelope_identity").fetchone()[0] == 1


def test_a_stored_reading_that_disagrees_with_the_authority_RAISES(
        conn) -> None:
    """Append-only plus document-bound means the two can only diverge through
    a canonicaliser change or a forged row -- and either is loud."""
    from swing.data.repos.fill_envelope_identity import (
        EnvelopeIdentityDriftError, record_identity,
    )
    raw = '{"schwab_order_id": "A"}'
    fid = _seed_fill(conn, envelope=raw)
    conn.execute(
        "INSERT INTO fill_envelope_identity (fill_id, envelope_raw, "
        " envelope_state, broker_order_id, canonicalizer_version, recorded_ts) "
        "VALUES (?, ?, 'canonical', 'FORGED', 'v0', 'T')", (fid, raw))
    with pytest.raises(EnvelopeIdentityDriftError):
        record_identity(conn, fill_id=fid, envelope_raw=raw)


def test_the_authority_canonicalises_the_whole_entry_fill_population(
        conn) -> None:
    """Migration 0037 ships the table EMPTY; the SERVICE fills it.  A scan that
    consumes stored readings would otherwise treat an unread population as
    empty, which is the silent-absence failure this arc keeps meeting."""
    from swing.data.repos.fill_envelope_identity import (
        ensure_entry_fill_identities,
    )
    a = _seed_fill(conn, trade_id=1, envelope='{"schwab_order_id": "A"}')
    b = _seed_fill(conn, trade_id=2, envelope='{"schwab_order_id": 7}')
    _seed_fill(conn, trade_id=3, envelope=None)
    _seed_fill(conn, trade_id=4, envelope='{"schwab_order_id": "Z"}',
               action="exit")
    assert ensure_entry_fill_identities(conn) == 2
    assert ensure_entry_fill_identities(conn) == 0        # idempotent
    assert dict(conn.execute(
        "SELECT fill_id, envelope_state FROM fill_envelope_identity"
    ).fetchall()) == {a: "canonical", b: "refused"}
