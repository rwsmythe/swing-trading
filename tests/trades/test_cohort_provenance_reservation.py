"""Task 9 -- the three cohort keys are RESERVED from the generic corrector.

`_handle_multi_field_correction` applies operator-supplied fields
SEQUENTIALLY with no cross-field coherence check, and the generic path takes
an operator-supplied VALUE -- so `hypothesis_label` reachable through it is
precisely the free-typing surface the evidence rule forbids, with an audit
trail attached to make it look sound.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.models import PROVENANCE_CORRECTED_FIELDS
from swing.trades.reconciliation_auto_correct import (
    _RESERVED_JOURNAL_FIELDS,
    ReservedJournalFieldError,
    _update_journal_field,
)
from tests.trades._cohort_provenance_fixtures import build_cadl_case

COHORT_COLUMNS = ("hypothesis_label", "candidate_id", "trade_origin")


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = ensure_schema(tmp_path / "swing.db")
    try:
        yield c
    finally:
        c.close()


def test_the_reservation_manifest_matches_the_corrected_fields_manifest(
) -> None:
    """The reserved set and the manifest of what ONE correction may touch are
    the SAME three columns -- read off both, not assumed."""
    reserved = {
        f"{table}.{field}"
        for (table, field), surface in _RESERVED_JOURNAL_FIELDS.items()
        if surface == "swing journal correct-cohort-provenance"
    }
    assert reserved == set(PROVENANCE_CORRECTED_FIELDS)


@pytest.mark.parametrize("column,value", [
    ("hypothesis_label", "Anything The Operator Types"),
    ("candidate_id", 12341),
    ("trade_origin", "pipeline_aplus"),
])
def test_each_cohort_column_is_refused_by_the_generic_path(
    conn, column, value,
) -> None:
    ids = build_cadl_case(conn)
    before = conn.execute(
        f"SELECT {column} FROM trades WHERE id = ?",
        (ids["trade_id"],)).fetchone()[0]
    with pytest.raises(
        ReservedJournalFieldError,
        match="correct-cohort-provenance",
    ):
        _update_journal_field(conn, "trades", ids["trade_id"], column, value)
    assert conn.execute(
        f"SELECT {column} FROM trades WHERE id = ?",
        (ids["trade_id"],)).fetchone()[0] == before


def test_the_refusal_names_the_coupled_surface_and_writes_nothing(
    conn,
) -> None:
    ids = build_cadl_case(conn)
    with pytest.raises(ReservedJournalFieldError) as exc:
        _update_journal_field(
            conn, "trades", ids["trade_id"], "hypothesis_label", "free text")
    msg = str(exc.value)
    assert "swing journal correct-cohort-provenance" in msg
    assert msg.endswith("Nothing was written.")


def test_the_generic_path_still_writes_a_NON_reserved_trades_column(
    conn,
) -> None:
    """The reservation must be exactly as wide as the invariant. A widening
    that swept in unrelated `trades` columns would remove a legitimate tier-2
    capability, so the negative control is not optional."""
    ids = build_cadl_case(conn)
    _update_journal_field(conn, "trades", ids["trade_id"], "current_stop", 9.5)
    assert conn.execute(
        "SELECT current_stop FROM trades WHERE id = ?",
        (ids["trade_id"],)).fetchone()[0] == 9.5


def test_the_entry_date_reservation_is_untouched(conn) -> None:
    """The pre-existing reservations keep their own surface; this arc ADDS
    three entries and rewires none."""
    assert _RESERVED_JOURNAL_FIELDS[("trades", "entry_date")] == (
        "swing journal correct-entry-date")
    assert _RESERVED_JOURNAL_FIELDS[("fills", "fill_datetime")] == (
        "swing journal correct-entry-date")
    ids = build_cadl_case(conn)
    with pytest.raises(
        ReservedJournalFieldError, match="correct-entry-date",
    ):
        _update_journal_field(
            conn, "trades", ids["trade_id"], "entry_date", "2026-08-05")


def test_a_historical_correction_on_a_NON_reserved_field_still_replays(
    conn,
) -> None:
    """THE REAL REGRESSION RISK, seeded rather than asserted-into-existence.

    The previous version of this test counted rows in a FRESHLY MIGRATED
    temporary database, where `reconciliation_corrections` is necessarily
    empty -- it proved nothing about the live history it claimed to be about
    and would have passed whatever the reservation did. The live-DB fact (zero
    of 37 rows target these columns) belongs in the return report, where it
    can be checked against the live DB; what a TEST can establish is that a
    representative historical shape still replays.
    """
    ids = build_cadl_case(conn)
    run_id = conn.execute(
        "INSERT INTO reconciliation_runs (source, started_ts, state) "
        "VALUES ('schwab_api', '2026-08-01T00:00:00', 'running')",
    ).lastrowid
    disc_id = conn.execute(
        "INSERT INTO reconciliation_discrepancies (run_id, discrepancy_type, "
        "trade_id, field_name, material_to_review, resolution, created_at) "
        "VALUES (?, 'stop_mismatch', ?, 'current_stop', 1, 'unresolved', "
        "'2026-08-01T00:00:00')",
        (run_id, ids["trade_id"]),
    ).lastrowid
    assert disc_id
    # The historical shape: a correction targeting a NON-reserved trades
    # column. Replaying it must still work.
    _update_journal_field(conn, "trades", ids["trade_id"], "current_stop", 8.5)
    assert conn.execute(
        "SELECT current_stop FROM trades WHERE id = ?",
        (ids["trade_id"],)).fetchone()[0] == 8.5


def test_the_reserved_columns_have_no_historical_correction_shape(
    conn,
) -> None:
    """And the three RESERVED columns are refused even when a discrepancy
    exists for the trade -- the reservation is on the COLUMN, so it holds
    whatever finding is cited."""
    ids = build_cadl_case(conn)
    for column in COHORT_COLUMNS:
        with pytest.raises(ReservedJournalFieldError):
            _update_journal_field(
                conn, "trades", ids["trade_id"], column, "x")


def test_reservation_applies_unconditionally_for_the_trades_table(conn) -> None:
    """`_reservation_applies` returns True unconditionally for
    `affected_table != 'fills'`, so the three entries need no per-row scoping
    -- verified against the function rather than assumed from its name."""
    from swing.trades.reconciliation_auto_correct import _reservation_applies

    ids = build_cadl_case(conn)
    for column in COHORT_COLUMNS:
        assert _reservation_applies(
            conn, "trades", ids["trade_id"], column, "whatever") is True
