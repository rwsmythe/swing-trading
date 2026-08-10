"""Item-5 T2 -- the audited entry-date correction surface.

The fixture is trade 19's LIVE shape, read off the operator's DB rather than
invented: FTRE, entry_date 2026-07-23, entry_price 18.80, 10 shares, one entry
fill at 2026-07-23T16:00:00, a `watchlist_archive` row with reason='entered'
and removed_date 2026-07-23, and an `entry_price_mismatch` discrepancy in
`pending_ambiguity_resolution` whose `actual_value_json` carries the real
`execution_legs` payload (`2026-07-31T13:30:05+0000`) and the real
`execution_sessions_from_fill: 6`.

Frozen dates throughout; no test reads `datetime.now()` for an assertion.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

import pytest

from swing.data.db import ensure_schema
from swing.trades.entry_date_correction import (
    ACTIVE_TRADE_CONSEQUENCES,
    CORRECTED_FIELDS,
    CORRECTION_ACTION,
    CORRECTION_CHOICE,
    CallerHeldTransactionError,
    EntryDateCorrectionError,
    correct_entry_date,
    preview_entry_date_correction,
)

PRE_DATE = "2026-07-23"
TARGET_DATE = "2026-07-31"
LIVE_LEG_TIME = "2026-07-31T13:30:05+0000"


def _live_actual_value_json(
    *,
    leg_times: tuple[str, ...] = (LIVE_LEG_TIME,),
    sessions_from_fill: int = 6,
    include_legs: bool = True,
) -> str:
    payload: dict[str, Any] = {
        "candidate_count": 1,
        "execution_sessions_from_fill": sessions_from_fill,
        "execution_side": "BUY",
        "price": 18.8,
        "schwab_order_id": "1007308870656",
        "schwab_order_price": 18.89,
    }
    if include_legs:
        payload["execution_legs"] = [
            {"leg_id": i + 1, "price": 18.8, "quantity": 10.0, "time": t}
            for i, t in enumerate(leg_times)
        ]
    return json.dumps(payload, sort_keys=True)


def _seed(
    conn: sqlite3.Connection,
    *,
    trade_state: str = "closed",
    entry_date: str = PRE_DATE,
    fill_action: str = "entry",
    fill_datetime: str | None = None,
    archive_rows: int = 1,
    archive_removed_date: str | None = None,
    discrepancy_type: str = "entry_price_mismatch",
    resolution: str = "pending_ambiguity_resolution",
    actual_value_json: str | None = None,
    fill_id_on_discrepancy: int | None = -1,
    discrepancy_trade_id: int | None = -1,
) -> dict[str, Any]:
    """Plant trade 19's live shape. Returns the key ids."""
    cur = conn.execute(
        """
        INSERT INTO trades (
            ticker, entry_date, entry_price, initial_shares, initial_stop,
            current_stop, state, trade_origin, pre_trade_locked_at,
            current_size, current_avg_cost, last_fill_at, hypothesis_label
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            "FTRE", entry_date, 18.8, 10, 16.554, 16.554, trade_state,
            "pipeline_watch_manual", f"{entry_date}T16:00:00",
            0.0 if trade_state in ("closed", "reviewed") else 10.0,
            18.8,
            # last_fill_at is a DENORM of MAX(fills.fill_datetime): a terminal
            # trade has the 08-04 stop fill below, an active one has only its
            # entry fill. Seeding a value the fills do not support would make
            # the aggregate assertions meaningless.
            "2026-08-04T16:00:00"
            if trade_state in ("closed", "reviewed")
            else f"{entry_date}T16:00:00",
            "Broad-watch baseline (watch); failed: tightness",
        ),
    )
    trade_id = int(cur.lastrowid)

    fcur = conn.execute(
        """
        INSERT INTO fills (
            trade_id, fill_datetime, action, quantity, price,
            reconciliation_status, fill_origin
        ) VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id, fill_datetime or f"{entry_date}T16:00:00", fill_action,
            10.0, 18.8, "unreconciled", "schwab_auto",
        ),
    )
    fill_id = int(fcur.lastrowid)
    if trade_state in ("closed", "reviewed"):
        conn.execute(
            """
            INSERT INTO fills (
                trade_id, fill_datetime, action, quantity, price,
                reconciliation_status
            ) VALUES (?, ?, ?, ?, ?, ?)
            """,
            (trade_id, "2026-08-04T16:00:00", "stop", 10.0, 18.4,
             "unreconciled"),
        )

    for _ in range(archive_rows):
        conn.execute(
            """
            INSERT INTO watchlist_archive
                (ticker, added_date, removed_date, reason, qualification_count,
                 last_data_asof_date)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            ("FTRE", "2026-06-30",
             archive_removed_date or entry_date, "entered", 19, "2026-07-30"),
        )

    rcur = conn.execute(
        """
        INSERT INTO reconciliation_runs (source, started_ts, state)
        VALUES ('schwab_api', '2026-08-01T03:41:00', 'completed')
        """,
    )
    run_id = int(rcur.lastrowid)

    dcur = conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            run_id, discrepancy_type, trade_id, fill_id, ticker, field_name,
            expected_value_json, actual_value_json, delta_text,
            material_to_review, resolution, ambiguity_kind, resolution_reason,
            resolved_at, resolved_by, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            run_id, discrepancy_type,
            trade_id if discrepancy_trade_id == -1 else discrepancy_trade_id,
            fill_id if fill_id_on_discrepancy == -1 else fill_id_on_discrepancy,
            "FTRE", "price",
            json.dumps({"price": 18.8}),
            actual_value_json if actual_value_json is not None
            else _live_actual_value_json(),
            "$+0.0000 (schwab execution minus journal)",
            1, resolution,
            "multi_match_within_window"
            if resolution == "pending_ambiguity_resolution" else None,
            "entry_price_mismatch on (ticker='FTRE', fill_id=39): execution "
            "is 6 NYSE-session(s) from fill (> 1) (20-A A2-date)",
            # A terminal resolution requires resolved_at/resolved_by
            # (ReconciliationDiscrepancy.__post_init__), so a fixture that
            # omits them cannot even be READ back.
            None if resolution in ("unresolved", "pending_ambiguity_resolution")
            else "2026-08-02T00:00:00",
            None if resolution in ("unresolved", "pending_ambiguity_resolution")
            else "operator",
            "2026-08-01T03:41:06.772",
        ),
    )
    discrepancy_id = int(dcur.lastrowid)
    conn.commit()
    return {
        "trade_id": trade_id, "fill_id": fill_id, "run_id": run_id,
        "discrepancy_id": discrepancy_id,
    }


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = ensure_schema(tmp_path / "edc.db")
    yield c
    c.close()


def _apply(conn, ids, **kw):
    return correct_entry_date(
        conn,
        trade_id=ids["trade_id"],
        to_date=kw.pop("to_date", TARGET_DATE),
        discrepancy_id=ids["discrepancy_id"],
        reason=kw.pop("reason", "RD ruling 20260801T145327Z part 3."),
        **kw,
    )


# ===========================================================================
# Happy path
# ===========================================================================


def test_correction_moves_the_three_coupled_values(conn):
    ids = _seed(conn)
    result = _apply(conn, ids)

    row = conn.execute(
        "SELECT entry_date, pre_trade_locked_at FROM trades WHERE id = ?",
        (ids["trade_id"],),
    ).fetchone()
    assert row[0] == TARGET_DATE
    # RD 2026-08-09: pre_trade_locked_at is DELIBERATELY NOT MOVED. It equals
    # entry_date + 'T16:00:00' on 20 of 20 live trades -- a synthetic
    # restatement of the column under correction, not independent evidence.
    assert row[1] == f"{PRE_DATE}T16:00:00"

    assert conn.execute(
        "SELECT fill_datetime, reconciliation_status FROM fills "
        "WHERE fill_id = ?", (ids["fill_id"],),
    ).fetchone() == (f"{TARGET_DATE}T16:00:00", "reconciled_discrepancy_resolved")

    assert conn.execute(
        "SELECT removed_date FROM watchlist_archive WHERE ticker='FTRE' "
        "AND reason='entered'",
    ).fetchone()[0] == TARGET_DATE

    assert result.target_date == TARGET_DATE
    assert result.pre_entry_date == PRE_DATE


def test_the_stored_reason_names_the_pre_trade_locked_at_staleness(conn):
    """RD 2026-08-09: a labelled inconsistency beats an invented timestamp.

    The reason must NAME the staleness AND must not cite pre_trade_locked_at
    as corroboration -- it is derived from the very column being corrected, so
    citing it would assert an independence that does not exist.
    """
    ids = _seed(conn)
    result = _apply(conn, ids)
    stored = conn.execute(
        "SELECT correction_reason FROM reconciliation_corrections "
        "WHERE correction_id = ?", (result.correction_id,),
    ).fetchone()[0]
    assert "pre_trade_locked_at" in stored
    assert "STALE DERIVATIVE" in stored
    assert f"{PRE_DATE}T16:00:00" in stored
    assert "no independent evidence" in stored


def test_correction_row_carries_the_action_and_choice_PAIR(conn):
    """models.py names `operator_resolved_ambiguity` with a NULL
    correction_choice as an explicit LIFECYCLE CONTRADICTION the schema
    deliberately does not enforce. The pair -- not either alone -- is what
    makes the row valid."""
    ids = _seed(conn)
    result = _apply(conn, ids)
    row = conn.execute(
        "SELECT correction_action, correction_choice, affected_table, "
        "affected_row_id, field_name, applied_by, reconciliation_run_id "
        "FROM reconciliation_corrections WHERE correction_id = ?",
        (result.correction_id,),
    ).fetchone()
    assert row[0] == CORRECTION_ACTION == "operator_resolved_ambiguity"
    assert row[1] == CORRECTION_CHOICE == "correct_entry_date"
    assert (row[2], row[3], row[4], row[5]) == (
        "trades", ids["trade_id"], "entry_date", "operator",
    )
    assert row[6] == ids["run_id"]


def test_correction_is_never_labelled_operator_overridden(conn):
    """`operator_overridden` is tier-3 -- an override OF A PRIOR CORRECTION.
    A discrepancy reaching this surface has none to supersede, so the label
    would assert a supersession of nothing."""
    ids = _seed(conn)
    result = _apply(conn, ids)
    assert conn.execute(
        "SELECT correction_action FROM reconciliation_corrections "
        "WHERE correction_id = ?", (result.correction_id,),
    ).fetchone()[0] != "operator_overridden"


def test_applied_value_json_reflects_POST_recompute_aggregates(conn):
    """`_recompute_aggregates` runs BEFORE the audit INSERT, so the row can
    tell the truth in the cases where last_fill_at / current_avg_cost move."""
    ids = _seed(conn)
    result = _apply(conn, ids)
    applied = json.loads(conn.execute(
        "SELECT applied_value_json FROM reconciliation_corrections "
        "WHERE correction_id = ?", (result.correction_id,),
    ).fetchone()[0])
    live = conn.execute(
        "SELECT current_size, current_avg_cost, last_fill_at FROM trades "
        "WHERE id = ?", (ids["trade_id"],),
    ).fetchone()
    assert applied["trades.current_size"] == live[0]
    assert applied["trades.current_avg_cost"] == live[1]
    assert applied["trades.last_fill_at"] == live[2]
    pre = json.loads(conn.execute(
        "SELECT pre_correction_value_json FROM reconciliation_corrections "
        "WHERE correction_id = ?", (result.correction_id,),
    ).fetchone()[0])
    assert set(CORRECTED_FIELDS).issubset(pre)
    assert set(CORRECTED_FIELDS).issubset(applied)


def test_aggregates_move_on_an_open_trade_and_the_audit_records_it(conn):
    """The forward case: on an un-exited position the corrected entry fill IS
    the MAX, so last_fill_at moves -- and the pre/post pair must show it."""
    ids = _seed(conn, trade_state="managing")
    result = _apply(conn, ids, allow_active=True)
    pre = json.loads(conn.execute(
        "SELECT pre_correction_value_json FROM reconciliation_corrections "
        "WHERE correction_id = ?", (result.correction_id,),
    ).fetchone()[0])
    applied = json.loads(conn.execute(
        "SELECT applied_value_json FROM reconciliation_corrections "
        "WHERE correction_id = ?", (result.correction_id,),
    ).fetchone()[0])
    assert pre["trades.last_fill_at"] == f"{PRE_DATE}T16:00:00"
    assert applied["trades.last_fill_at"] == f"{TARGET_DATE}T16:00:00"


def test_a_trade_events_row_is_emitted_with_the_shared_payload_shape(conn):
    ids = _seed(conn)
    result = _apply(conn, ids)
    rows = conn.execute(
        "SELECT event_type, payload_json FROM trade_events "
        "WHERE trade_id = ? AND event_type = 'reconciliation_auto_correct'",
        (ids["trade_id"],),
    ).fetchall()
    assert len(rows) == 1
    payload = json.loads(rows[0][1])
    assert set(payload) == {
        "correction_id", "affected_table", "affected_row_id", "field_name",
        "pre", "applied",
    }
    assert payload["correction_id"] == result.correction_id


def test_follow_up_command_carries_the_real_id_and_no_placeholder(conn):
    """Two commands run minutes apart; nothing carries the id between them, so
    a literal `<correction_id>` would land in the ledger."""
    ids = _seed(conn)
    result = _apply(conn, ids)
    cmd = result.follow_up_command
    assert f"correction {result.correction_id}" in cmd
    assert "<" not in cmd
    assert "--resolution journal_corrected" in cmd
    assert "--force" in cmd
    assert "mark_unmatched" not in cmd
    assert "1007308870656" in cmd


def test_the_discrepancy_row_itself_is_untouched_by_the_correction(conn):
    """Ordering is binding: correct first, resolve second. This surface does
    NOT resolve the finding -- that is a separate, witnessed command."""
    ids = _seed(conn)
    _apply(conn, ids)
    assert conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?", (ids["discrepancy_id"],),
    ).fetchone()[0] == "pending_ambiguity_resolution"


# ===========================================================================
# The server-derived target date
# ===========================================================================


def test_a_to_date_that_does_not_match_the_evidence_is_REFUSED(conn):
    """The sharpest guard. Every other clause proves date evidence EXISTS and
    DIFFERS; none of them binds --to to it. 2026-08-03 is a Monday, a real
    session, later than the evidence, and satisfies every other check."""
    ids = _seed(conn)
    with pytest.raises(EntryDateCorrectionError, match="SERVER-DERIVED"):
        _apply(conn, ids, to_date="2026-08-03")
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == PRE_DATE
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


def test_the_derived_date_is_the_LATEST_leg_not_an_index(conn):
    """Three legs, maximum in the MIDDLE: legs[0] -> 07-31, legs[-1] -> 08-01,
    max() -> 08-03. One fixture excludes both wrong implementations."""
    ids = _seed(conn, actual_value_json=_live_actual_value_json(
        leg_times=(
            "2026-07-31T13:30:05+0000",
            "2026-08-03T15:00:00+0000",
            "2026-08-01T18:45:00+0000",
        ),
    ))
    _apply(conn, ids, to_date="2026-08-03")
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == "2026-08-03"


def test_a_nonzero_session_distance_is_NOT_sufficient_evidence(conn):
    """gotcha #30 in its general form. `execution_sessions_from_fill` is
    max(distance) ACROSS ALL LEGS, so a nonzero value only proves SOME leg
    differs. Here leg 1 is six sessions earlier and the LATEST leg is the
    fill's own date, so the date this surface would write is unchanged --
    and the aggregate still reads 6."""
    ids = _seed(conn, actual_value_json=_live_actual_value_json(
        leg_times=("2026-07-23T13:30:05+0000", "2026-07-23T19:59:00+0000"),
        sessions_from_fill=6,
    ))
    with pytest.raises(
        EntryDateCorrectionError, match="already equals the fill's date",
    ):
        _apply(conn, ids)


def test_a_price_only_discrepancy_carries_no_date_evidence(conn):
    ids = _seed(conn, actual_value_json=_live_actual_value_json(
        include_legs=False,
    ))
    with pytest.raises(EntryDateCorrectionError, match="no execution_legs"):
        _apply(conn, ids)


def test_an_unparseable_leg_time_refuses_rather_than_ranking_a_partial_view(
    conn,
):
    ids = _seed(conn, actual_value_json=_live_actual_value_json(
        leg_times=(LIVE_LEG_TIME, "not-a-timestamp"),
    ))
    with pytest.raises(EntryDateCorrectionError, match="unparseable"):
        _apply(conn, ids)


# ===========================================================================
# --to validation
# ===========================================================================


def test_a_datetime_to_value_is_refused(conn):
    ids = _seed(conn)
    with pytest.raises(EntryDateCorrectionError, match="not a datetime"):
        _apply(conn, ids, to_date="2026-07-31T13:30:05")


def test_a_malformed_to_value_raises_a_typed_error_not_a_deep_TypeError(conn):
    ids = _seed(conn)
    with pytest.raises(EntryDateCorrectionError, match="valid YYYY-MM-DD"):
        _apply(conn, ids, to_date="2026-99-99")


def test_a_non_session_to_value_is_refused_and_the_residue_is_NAMED(conn):
    """2026-08-01 is a Saturday. Under the UTC-prefix convention a Friday
    after-hours execution DERIVES a Saturday date -- that is not a typo, it is
    a real fill this surface cannot correct, and the refusal says so rather
    than writing a date that would de-latch a live position."""
    ids = _seed(conn)
    with pytest.raises(EntryDateCorrectionError) as exc:
        _apply(conn, ids, to_date="2026-08-01")
    assert "not an NYSE trading session" in str(exc.value)
    assert "after-hours" in str(exc.value)
    assert "not a typo" in str(exc.value)


def test_an_empty_reason_is_refused_before_any_db_work(conn):
    ids = _seed(conn)
    with pytest.raises(EntryDateCorrectionError, match="--reason"):
        _apply(conn, ids, reason="   ")
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


def test_a_no_op_correction_is_refused_and_writes_nothing(conn):
    ids = _seed(conn, entry_date=TARGET_DATE)
    with pytest.raises(EntryDateCorrectionError, match="already has entry_date"):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


def test_a_missing_trade_is_refused(conn):
    ids = _seed(conn)
    with pytest.raises(EntryDateCorrectionError, match="not found"):
        correct_entry_date(
            conn, trade_id=99999, to_date=TARGET_DATE,
            discrepancy_id=ids["discrepancy_id"], reason="x",
        )


# ===========================================================================
# The state gate -- BOTH branches
# ===========================================================================


@pytest.mark.parametrize("state", ["entered", "managing", "partial_exited"])
def test_an_active_trade_is_refused_without_the_flag(conn, state):
    ids = _seed(conn, trade_state=state)
    with pytest.raises(EntryDateCorrectionError) as exc:
        _apply(conn, ids)
    msg = str(exc.value)
    assert "--allow-active" in msg
    # An acknowledgement flag that UNDER-STATES what is being acknowledged is
    # worse than no flag: the refusal prints the whole inventory.
    for item in ACTIVE_TRADE_CONSEQUENCES:
        assert item in msg


@pytest.mark.parametrize("state", ["entered", "managing", "partial_exited"])
def test_an_active_trade_is_accepted_WITH_the_flag(conn, state):
    ids = _seed(conn, trade_state=state)
    result = _apply(conn, ids, allow_active=True)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == TARGET_DATE
    assert "--allow-active acknowledged" in result.correction_reason


@pytest.mark.parametrize("state", ["closed", "reviewed"])
def test_a_terminal_trade_needs_no_flag(conn, state):
    ids = _seed(conn, trade_state=state)
    _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == TARGET_DATE


# ===========================================================================
# Discrepancy authorization
# ===========================================================================


@pytest.mark.parametrize(
    "resolution",
    ["journal_corrected", "source_treated_canonical", "acknowledged_immaterial"],
)
def test_an_already_dispositioned_finding_cannot_authorize(conn, resolution):
    """Without this, any long-closed entry discrepancy on the trade is a
    standing warrant to rewrite its date."""
    ids = _seed(conn, resolution=resolution)
    with pytest.raises(
        EntryDateCorrectionError, match="already dispositioned",
    ):
        _apply(conn, ids)


def test_a_discrepancy_for_a_different_trade_cannot_authorize(conn):
    ids = _seed(conn, discrepancy_trade_id=None)
    with pytest.raises(EntryDateCorrectionError, match="belongs to trade"):
        _apply(conn, ids)


def test_a_discrepancy_with_no_bound_fill_cannot_authorize(conn):
    ids = _seed(conn, fill_id_on_discrepancy=None)
    with pytest.raises(EntryDateCorrectionError, match="binds no fill_id"):
        _apply(conn, ids)


def test_a_non_entry_fill_cannot_authorize(conn):
    ids = _seed(conn, fill_action="exit")
    with pytest.raises(EntryDateCorrectionError, match="not 'entry'"):
        _apply(conn, ids)


def test_a_wrong_typed_discrepancy_cannot_authorize(conn):
    ids = _seed(conn, discrepancy_type="stop_mismatch")
    with pytest.raises(EntryDateCorrectionError, match="stop_mismatch"):
        _apply(conn, ids)


def test_a_fills_vs_trades_internal_consistency_row_cannot_authorize(conn):
    """A fills-vs-trades PRICE diagnostic is internal to the journal on both
    sides. It says nothing about a date, and it is typed
    `entry_price_mismatch` today, so the type check alone would admit it."""
    payload = json.loads(_live_actual_value_json())
    payload["internal_consistency"] = "fills_vs_trades"
    ids = _seed(conn, actual_value_json=json.dumps(payload, sort_keys=True))
    with pytest.raises(
        EntryDateCorrectionError, match="internal\n?\\s*consistency|internal "
        "consistency",
    ):
        _apply(conn, ids)


# ===========================================================================
# watchlist_archive binding -- zero / one / many
# ===========================================================================


def test_zero_archive_matches_refuses_and_leaves_the_trade_UNCORRECTED(conn):
    """A manually-recorded trade that never sat on the watchlist is a real and
    common shape. Without this the trade would be HALF corrected."""
    ids = _seed(conn, archive_rows=0)
    with pytest.raises(EntryDateCorrectionError, match="found 0"):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == PRE_DATE
    assert conn.execute(
        "SELECT fill_datetime FROM fills WHERE fill_id = ?", (ids["fill_id"],),
    ).fetchone()[0] == f"{PRE_DATE}T16:00:00"
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


def test_two_archive_matches_refuse_naming_the_count(conn):
    """Same ticker entered twice on the same date. A best-effort
    `UPDATE ... WHERE ticker=? AND reason='entered'` passes the happy path and
    rewrites every row in exactly this case."""
    ids = _seed(conn, archive_rows=2)
    with pytest.raises(EntryDateCorrectionError, match="found 2"):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT COUNT(*) FROM watchlist_archive WHERE removed_date = ?",
        (TARGET_DATE,),
    ).fetchone()[0] == 0


def test_a_sibling_archive_row_on_another_date_is_not_touched(conn):
    ids = _seed(conn)
    conn.execute(
        "INSERT INTO watchlist_archive (ticker, added_date, removed_date, "
        "reason, qualification_count) VALUES ('FTRE','2026-05-01',"
        "'2026-05-20','entered',3)",
    )
    conn.commit()
    _apply(conn, ids)
    dates = sorted(
        r[0] for r in conn.execute(
            "SELECT removed_date FROM watchlist_archive WHERE ticker='FTRE'",
        ).fetchall()
    )
    assert dates == ["2026-05-20", TARGET_DATE]


# ===========================================================================
# Transaction discipline + dry run
# ===========================================================================


def test_a_caller_held_transaction_is_REJECTED_never_auto_detected(conn):
    ids = _seed(conn)
    conn.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(CallerHeldTransactionError):
            _apply(conn, ids)
    finally:
        conn.rollback()


def test_a_refusal_mid_transaction_rolls_everything_back(conn):
    """The archive guard fires AFTER the trade + fill UPDATEs in the inner, so
    a rollback is the only thing that keeps the trade whole."""
    ids = _seed(conn, archive_rows=0)
    with pytest.raises(EntryDateCorrectionError):
        _apply(conn, ids)
    assert not conn.in_transaction
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == PRE_DATE


def test_dry_run_writes_nothing_and_reports_what_it_does_not_know(conn):
    ids = _seed(conn)
    preview = preview_entry_date_correction(
        conn, trade_id=ids["trade_id"], to_date=TARGET_DATE,
        discrepancy_id=ids["discrepancy_id"], reason="dry run",
    )
    assert preview.target_date == TARGET_DATE
    assert preview.pre_values["trades.entry_date"] == PRE_DATE
    assert preview.post_values["fills.fill_datetime"] == (
        f"{TARGET_DATE}T16:00:00"
    )
    assert set(preview.aggregates_before) == {
        "current_size", "current_avg_cost", "last_fill_at",
    }
    # No aggregates_after: predicting them means re-implementing
    # _recompute_aggregates in the preview, and a second implementation of a
    # derivation is the two-path-divergence class invited into a preview.
    assert not hasattr(preview, "aggregates_after")
    assert preview.pre_trade_locked_at_left_stale == f"{PRE_DATE}T16:00:00"
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == PRE_DATE
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


def test_dry_run_raises_the_same_refusals_as_the_write_path(conn):
    ids = _seed(conn)
    with pytest.raises(EntryDateCorrectionError, match="SERVER-DERIVED"):
        preview_entry_date_correction(
            conn, trade_id=ids["trade_id"], to_date="2026-08-03",
            discrepancy_id=ids["discrepancy_id"], reason="dry run",
        )


def test_dry_run_on_an_active_trade_lists_the_consequences(conn):
    ids = _seed(conn, trade_state="managing")
    preview = preview_entry_date_correction(
        conn, trade_id=ids["trade_id"], to_date=TARGET_DATE,
        discrepancy_id=ids["discrepancy_id"], reason="dry run",
        allow_active=True,
    )
    assert preview.allow_active_used is True
    assert preview.active_trade_consequences == ACTIVE_TRADE_CONSEQUENCES


# ===========================================================================
# The closed field enum
# ===========================================================================


def test_the_corrected_field_manifest_is_pinned(conn):
    """A silent widening of what one correction touches must be visible.
    `trades.pre_trade_locked_at` is NOT a member (RD 2026-08-09)."""
    assert CORRECTED_FIELDS == (
        "trades.entry_date",
        "fills.fill_datetime",
        "watchlist_archive.removed_date",
    )
    assert "trades.pre_trade_locked_at" not in CORRECTED_FIELDS


def test_the_service_module_interpolates_no_sql_identifier():
    """`_update_journal_field`'s docstring forbids operator-sourced identifiers
    reaching an f-string SQL slot. This surface never calls it; the assertion
    pins that no f-string SQL is introduced here later."""
    import inspect

    from swing.trades import entry_date_correction as mod
    src = inspect.getsource(mod)
    # A CALL, not a mention -- the module documents WHY it avoids the helper.
    assert "_update_journal_field(" not in src
    for marker in ('f"UPDATE', "f'UPDATE", 'f"SELECT', "f'SELECT"):
        assert marker not in src


# ===========================================================================
# Codex R1 fixes
# ===========================================================================


def test_r1_M1_a_SELL_side_execution_cannot_date_an_ENTRY(conn):
    """The sole-candidate Shape-D emit fires when the candidate failed price OR
    **SIDE** OR session, and it always carries `execution_side`. So a
    same-ticker same-quantity SELL execution reaches the surface as the only
    evidence on an `entry_price_mismatch` for an ENTRY fill.

    Without the side clause the surface would derive the EXIT's date, move all
    three values onto it, and append an audit row that looks entirely valid.
    `--to` is no protection: the server derives the WRONG date and asks the
    operator to confirm it.
    """
    payload = json.loads(_live_actual_value_json())
    payload["execution_side"] = "SELL"
    ids = _seed(conn, actual_value_json=json.dumps(payload, sort_keys=True))
    with pytest.raises(EntryDateCorrectionError, match="not an ENTRY side"):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == PRE_DATE
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


def test_r1_M1_a_BUY_side_execution_is_accepted(conn):
    """Counterfactual for the clause above -- the live payload's own BUY."""
    ids = _seed(conn)
    assert json.loads(
        conn.execute(
            "SELECT actual_value_json FROM reconciliation_discrepancies "
            "WHERE discrepancy_id = ?", (ids["discrepancy_id"],),
        ).fetchone()[0]
    )["execution_side"] == "BUY"
    _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == TARGET_DATE


def test_r1_M1_a_missing_execution_side_is_refused(conn):
    payload = json.loads(_live_actual_value_json())
    del payload["execution_side"]
    ids = _seed(conn, actual_value_json=json.dumps(payload, sort_keys=True))
    with pytest.raises(EntryDateCorrectionError, match="not an ENTRY side"):
        _apply(conn, ids)


def test_r1_M1_a_multi_candidate_payload_cannot_authorize(conn):
    """`candidate_count != 1`. The A1 multi-match emit is a JSON ARRAY --
    'which candidate is the truth' is precisely the question the operator has
    not answered."""
    payload = json.loads(_live_actual_value_json())
    del payload["candidate_count"]
    ids = _seed(conn, actual_value_json=json.dumps(payload, sort_keys=True))
    with pytest.raises(EntryDateCorrectionError, match="candidate_count"):
        _apply(conn, ids)


def test_r1_M1_a_json_array_payload_cannot_authorize(conn):
    """The real A1 shape: a LIST of candidate dicts."""
    single = json.loads(_live_actual_value_json())
    ids = _seed(conn, actual_value_json=json.dumps([single, single]))
    with pytest.raises(EntryDateCorrectionError, match="OBJECT payload"):
        _apply(conn, ids)


@pytest.mark.parametrize("raw", ["20260731", "2026-W31-5T13:30:05"])
def test_r1_M2_a_basic_iso_leg_time_cannot_derive_a_date(conn, raw):
    """`datetime.fromisoformat` on 3.11+ accepts BASIC ISO forms. A naive
    `[:10]` of `20260731` is `"20260731"` -- not a date -- and writing it into
    `trades.entry_date` would break every downstream prefix comparison."""
    ids = _seed(conn, actual_value_json=_live_actual_value_json(
        leg_times=(raw,),
    ))
    with pytest.raises(EntryDateCorrectionError, match="unparseable"):
        _apply(conn, ids, to_date="2026-07-31")


def test_r1_M2_a_non_string_leg_time_cannot_derive_a_date(conn):
    ids = _seed(conn, actual_value_json=_live_actual_value_json())
    payload = json.loads(conn.execute(
        "SELECT actual_value_json FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?", (ids["discrepancy_id"],),
    ).fetchone()[0])
    payload["execution_legs"][0]["time"] = 20260731
    conn.execute(
        "UPDATE reconciliation_discrepancies SET actual_value_json = ? "
        "WHERE discrepancy_id = ?",
        (json.dumps(payload, sort_keys=True), ids["discrepancy_id"]),
    )
    conn.commit()
    with pytest.raises(EntryDateCorrectionError, match="unparseable"):
        _apply(conn, ids, to_date="2026-07-31")


@pytest.mark.parametrize("bad_to", ["20260731", "2026-W31-5"])
def test_r1_M2_a_basic_iso_to_value_is_refused(conn, bad_to):
    ids = _seed(conn)
    with pytest.raises(EntryDateCorrectionError, match="EXTENDED-format"):
        _apply(conn, ids, to_date=bad_to)


def test_r1_M2_the_repo_writer_refuses_a_basic_iso_date():
    """The write boundary refuses independently of the service, so a future
    caller cannot slip a non-canonical date past it."""
    import sqlite3 as _sq

    from swing.data.db import ensure_schema
    from swing.data.repos.trades import update_entry_date

    import tempfile
    from pathlib import Path as _P
    c = ensure_schema(_P(tempfile.mkdtemp()) / "w.db")
    try:
        cur = c.execute(
            "INSERT INTO trades (ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, trade_origin, "
            "pre_trade_locked_at) "
            "VALUES ('X', '2026-07-23', 1.0, 1, 0.5, 0.5, 'closed', "
            "'manual_off_pipeline', '2026-07-23T16:00:00')",
        )
        tid = int(cur.lastrowid)
        with pytest.raises(ValueError, match="EXTENDED-format"):
            update_entry_date(c, trade_id=tid, entry_date="20260731")
        assert c.execute(
            "SELECT entry_date FROM trades WHERE id = ?", (tid,),
        ).fetchone()[0] == "2026-07-23"
        assert isinstance(c, _sq.Connection)
    finally:
        c.close()


def test_r1_MINOR_a_MID_TRANSACTION_failure_rolls_everything_back(
    conn, monkeypatch,
):
    """The previous rollback test could not reach a mid-transaction failure:
    the archive row is resolved during `_authorize`, BEFORE any writer runs, so
    a zero-match refused before the first UPDATE. This injects a failure AFTER
    all three updates and the aggregate recompute."""
    from swing.trades import entry_date_correction as mod

    ids = _seed(conn)
    pre_locked = conn.execute(
        "SELECT pre_trade_locked_at FROM trades WHERE id = ?",
        (ids["trade_id"],),
    ).fetchone()[0]

    def _boom(*a, **k):
        raise RuntimeError("audit insert exploded")

    monkeypatch.setattr(mod, "insert_correction", _boom)
    with pytest.raises(RuntimeError, match="exploded"):
        _apply(conn, ids)

    assert not conn.in_transaction
    assert conn.execute(
        "SELECT entry_date, pre_trade_locked_at, current_avg_cost, "
        "last_fill_at FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[:2] == (PRE_DATE, pre_locked)
    assert conn.execute(
        "SELECT fill_datetime, reconciliation_status FROM fills "
        "WHERE fill_id = ?", (ids["fill_id"],),
    ).fetchone() == (f"{PRE_DATE}T16:00:00", "unreconciled")
    assert conn.execute(
        "SELECT removed_date FROM watchlist_archive WHERE ticker='FTRE'",
    ).fetchone()[0] == PRE_DATE
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0
    assert conn.execute(
        "SELECT COUNT(*) FROM trade_events WHERE event_type = "
        "'reconciliation_auto_correct'",
    ).fetchone()[0] == 0


def test_r1_MINOR_a_failure_AFTER_the_audit_insert_also_rolls_back(
    conn, monkeypatch,
):
    """The last writer in the flow is the trade_events emit; a failure there
    must not leave a correction row pointing at an unwritten mutation."""
    from swing.trades import reconciliation_auto_correct as rac

    ids = _seed(conn)

    def _boom(*a, **k):
        raise RuntimeError("event emit exploded")

    monkeypatch.setattr(rac, "_emit_trade_events_correction", _boom)
    with pytest.raises(RuntimeError, match="exploded"):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == PRE_DATE
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0
