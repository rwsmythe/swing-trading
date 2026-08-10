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
        # The leg quantities SUM to the fill's 10 shares, because that is what
        # the emitter's own candidate filter guarantees (same ticker, same
        # execution-grain quantity within tolerance) and the surface now
        # re-checks it. A fixture whose legs summed to 20 or 30 would be a
        # shape the emitter cannot produce.
        per_leg = 10.0 / len(leg_times)
        payload["execution_legs"] = [
            {"leg_id": i + 1, "price": 18.8, "quantity": per_leg, "time": t}
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
    fill_origin: str = "schwab_auto",
    source_order_id: str | None = "1007308870656",
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
            reconciliation_status, fill_origin, schwab_source_value_json
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            trade_id, fill_datetime or f"{entry_date}T16:00:00", fill_action,
            10.0, 18.8, "unreconciled", fill_origin,
            # The REAL production envelope `entry_auto_fill` writes and
            # `record_entry` persists -- live fill 39's shape. Its
            # `schwab_order_id` is what binds the discrepancy's evidence to
            # THIS fill; a fixture that omitted it masked the hole entirely.
            # NO `entry_date_source` key -- this is the LIVE pre-T1 shape
            # (fill 39's actual envelope), and its ABSENCE is what identifies a
            # D31 victim. A fixture that stamped the key would have described a
            # fill the pre-T1 code could not have written.
            None if source_order_id is None else json.dumps({
                "entry_date": entry_date,
                "entry_price": 18.8,
                "schwab_instrument_symbol": "FTRE",
                "schwab_order_id": source_order_id,
                "shares": 10,
            }, sort_keys=True),
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
    # VALUES, not presence (Codex R9 minor). A regression that repeated the
    # POST date in both envelopes, swapped pre for post, or recorded the wrong
    # fill datetime would pass a keys-exist check while every live-row
    # assertion above still succeeded.
    assert pre["trades.entry_date"] == PRE_DATE
    assert pre["fills.fill_datetime"] == f"{PRE_DATE}T16:00:00"
    assert pre["watchlist_archive.removed_date"] == PRE_DATE
    assert applied["trades.entry_date"] == TARGET_DATE
    assert applied["fills.fill_datetime"] == f"{TARGET_DATE}T16:00:00"
    assert applied["watchlist_archive.removed_date"] == TARGET_DATE
    # ...and the two bound row identities, in BOTH envelopes.
    from swing.trades.entry_date_correction import BOUND_ARCHIVE_KEY
    from swing.trades.reconciliation_auto_correct import (
        MULTI_ROW_BOUND_FILL_KEY,
    )
    archive_id = conn.execute(
        "SELECT id FROM watchlist_archive WHERE ticker='FTRE'",
    ).fetchone()[0]
    for envelope in (pre, applied):
        assert envelope[MULTI_ROW_BOUND_FILL_KEY] == ids["fill_id"]
        assert envelope[BOUND_ARCHIVE_KEY] == archive_id
    # The pre/post pair must actually DIFFER on every corrected field.
    for fname in CORRECTED_FIELDS:
        assert pre[fname] != applied[fname], fname


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
    """A payload with no `execution_legs` is a price disagreement, not DATE
    evidence. The refusal now comes from the price-authentication clause, which
    runs first and needs the legs to authenticate against -- either way the
    absence of legs is what disqualifies it, and nothing is written."""
    ids = _seed(conn, actual_value_json=_live_actual_value_json(
        include_legs=False,
    ))
    with pytest.raises(EntryDateCorrectionError, match="execution legs"):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


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


def test_an_archive_binding_refusal_happens_BEFORE_any_write(conn):
    """RENAMED, because the original name claimed coverage this test does not
    have (Codex R3 Minor 2). `_resolve_archive_row` runs inside `_authorize`,
    BEFORE any writer, so this exercises the PRE-WRITE refusal path and would
    pass even with rollback handling removed entirely. The actual rollback
    coverage is the pair of post-writer injection tests further down
    (`insert_correction` raising, and the trade_events emit raising)."""
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


# ===========================================================================
# Codex R2 fixes
# ===========================================================================


def _add_second_entry_fill(conn, ids, *, when: str = "2026-08-03T16:00:00"):
    """A scale-in: a SECOND `action='entry'` fill, later than the first."""
    cur = conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status) VALUES (?, ?, 'entry', 5.0, 19.1, "
        "'unreconciled')", (ids["trade_id"], when),
    )
    conn.commit()
    return int(cur.lastrowid)


def test_r2_M1_a_later_SCALE_IN_fill_cannot_redate_the_whole_trade(conn):
    """`action='entry'` is NOT the same as "the fill that dated this trade".

    A scale-in adds a SECOND entry fill; an `entry_price_mismatch` raised on
    that add-on would otherwise move trades.entry_date, the archive row and
    every entry-date-derived metric onto the ADD-ON's execution date.
    """
    ids = _seed(conn)
    addon_id = _add_second_entry_fill(conn, ids)
    conn.execute(
        "UPDATE reconciliation_discrepancies SET fill_id = ? "
        "WHERE discrepancy_id = ?", (addon_id, ids["discrepancy_id"]),
    )
    conn.commit()
    with pytest.raises(EntryDateCorrectionError, match="AUTHORITATIVE"):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == PRE_DATE
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


def test_r2_M1_the_authoritative_fill_still_works_with_a_scale_in_present(conn):
    """Counterfactual: the SAME trade, the SAME add-on, but the discrepancy
    binds the FIRST entry fill -- accepted."""
    ids = _seed(conn)
    _add_second_entry_fill(conn, ids)
    _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == TARGET_DATE


def test_r2_M1_a_fill_already_diverged_from_the_trade_date_is_refused(conn):
    """The surface RESTORES a coupling; it must not be used where the fill and
    the trade already disagree for some other reason."""
    ids = _seed(conn, fill_datetime="2026-07-20T16:00:00")
    with pytest.raises(EntryDateCorrectionError, match="already\n?\\s*disagrees|already disagrees"):
        _apply(conn, ids)


def test_r2_M2_a_same_ticker_same_date_sibling_trade_refuses(conn):
    """`watchlist_archive` has NO trade identity. `entry.py` writes a row only
    when the ticker is CURRENTLY watchlisted, so a same-day SECOND entry on the
    same ticker creates no row of its own -- and a naive lookup would bind, and
    rewrite, the FIRST trade's row. Exactly-one-match proves CARDINALITY, not
    OWNERSHIP."""
    ids = _seed(conn)
    conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares, "
        "initial_stop, current_stop, state, trade_origin, pre_trade_locked_at) "
        "VALUES ('FTRE', ?, 18.9, 5, 16.0, 16.0, 'closed', "
        "'manual_off_pipeline', ?)", (PRE_DATE, f"{PRE_DATE}T16:00:00"),
    )
    conn.commit()
    with pytest.raises(EntryDateCorrectionError, match="UNPROVABLE"):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT removed_date FROM watchlist_archive WHERE ticker='FTRE'",
    ).fetchone()[0] == PRE_DATE
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


def test_r2_M2_a_same_ticker_DIFFERENT_date_trade_does_not_block(conn):
    """Counterfactual: the ownership hazard is specific to a shared
    (ticker, entry_date); an earlier entry on another date is irrelevant."""
    ids = _seed(conn)
    conn.execute(
        "INSERT INTO trades (ticker, entry_date, entry_price, initial_shares, "
        "initial_stop, current_stop, state, trade_origin, pre_trade_locked_at) "
        "VALUES ('FTRE', '2026-05-20', 18.9, 5, 16.0, 16.0, 'closed', "
        "'manual_off_pipeline', '2026-05-20T16:00:00')",
    )
    conn.commit()
    _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == TARGET_DATE


@pytest.mark.parametrize("bad_count", [True, 1.0, 2, 0, "1", None])
def test_r2_M3_candidate_count_must_be_a_STRICT_integer_one(conn, bad_count):
    """Python evaluates `True == 1`, so a bare `!= 1` admits a JSON boolean
    `true` -- and `1.0` besides. A malformed persisted payload must not
    authorize three ledger writes on a truthy value that never asserted a
    singleton."""
    payload = json.loads(_live_actual_value_json())
    payload["candidate_count"] = bad_count
    ids = _seed(conn, actual_value_json=json.dumps(payload, sort_keys=True))
    with pytest.raises(EntryDateCorrectionError, match="candidate_count"):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


def test_r2_M4_mixed_offset_legs_are_REFUSED_not_silently_resolved(conn):
    """Ranking is by ABSOLUTE INSTANT while the emitted value is the leg's own
    offset-local prefix; those agree only while every leg shares one offset.
    Codex's case: a later-in-absolute-time -10:00 leg carries an EARLIER local
    date than an earlier +14:00 leg, so "the latest leg's date" stops having
    one answer."""
    ids = _seed(conn, actual_value_json=_live_actual_value_json(
        leg_times=(
            "2026-08-01T00:30:00+14:00",
            "2026-07-31T23:00:00-10:00",
        ),
    ))
    with pytest.raises(EntryDateCorrectionError, match="unparseable"):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


# ===========================================================================
# Codex R3 fixes
# ===========================================================================


def test_r3_M1_a_move_that_would_UNSEAT_the_authoritative_fill_is_refused(conn):
    """R2's gate proved the bound fill is authoritative TODAY. Moving its
    datetime FORWARD can hand that role to an INTERVENING entry fill.

    Sibling on 07-25, move 07-23 -> 07-31. Pre-fix the correction commits an
    internally inconsistent ledger: trades.entry_date says 07-31 while
    `_recompute_aggregates` takes the 07-25 fill's price as current_avg_cost,
    and the audit row asserts the correction was coherent. R2's own test hid
    this by placing the sibling at 08-03, AFTER the target.
    """
    ids = _seed(conn)
    _add_second_entry_fill(conn, ids, when="2026-07-25T16:00:00")
    with pytest.raises(EntryDateCorrectionError, match="would make"):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date, current_avg_cost FROM trades WHERE id = ?",
        (ids["trade_id"],),
    ).fetchone() == (PRE_DATE, 18.8)
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


def test_r3_M1_a_sibling_AFTER_the_target_date_still_permits_the_move(conn):
    """Counterfactual: the guard is about ORDERING, not about the mere
    existence of a second entry fill."""
    ids = _seed(conn)
    _add_second_entry_fill(conn, ids, when="2026-08-03T16:00:00")
    _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == TARGET_DATE


def test_r3_M2_stale_evidence_whose_qty_no_longer_matches_is_refused(conn):
    """The emitter selected its candidate by same ticker AND execution-grain
    QUANTITY. A later correction can change `fills.quantity` while an older
    discrepancy sits unresolved; the stale row must not then authorize three
    ledger writes from an order that no longer matches the fill it cites."""
    ids = _seed(conn)
    conn.execute(
        "UPDATE fills SET quantity = 25.0 WHERE fill_id = ?",
        (ids["fill_id"],),
    )
    conn.commit()
    with pytest.raises(
        EntryDateCorrectionError, match="no longer describes the row",
    ):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


def test_r3_M2_a_ticker_that_no_longer_matches_is_refused(conn):
    ids = _seed(conn)
    conn.execute(
        "UPDATE reconciliation_discrepancies SET ticker = 'OTHER' "
        "WHERE discrepancy_id = ?", (ids["discrepancy_id"],),
    )
    conn.commit()
    with pytest.raises(EntryDateCorrectionError, match="no longer matches"):
        _apply(conn, ids)


def test_r3_M3_operator_truth_value_json_is_NULL(conn):
    """`models.py` defines this column as OPERATOR-SUPPLIED TRUTH for tier-3
    rows, and every existing tier-2 resolution stores NULL. Populating it with
    the applied dict would attribute current_size, current_avg_cost,
    last_fill_at and the fill's reconciliation status to the OPERATOR, who
    confirmed only a SERVER-DERIVED date."""
    ids = _seed(conn)
    result = _apply(conn, ids)
    row = conn.execute(
        "SELECT operator_truth_value_json, source_canonical_value_json, "
        "correction_choice FROM reconciliation_corrections "
        "WHERE correction_id = ?", (result.correction_id,),
    ).fetchone()
    assert row[0] is None
    # The date he DID confirm is still recorded, so nothing was lost.
    assert json.loads(row[1])["execution_leg_date"] == TARGET_DATE
    assert row[2] == CORRECTION_CHOICE


@pytest.mark.parametrize(
    "bad", ["2026-07-23garbage", "20260723T160000", "not-a-datetime"],
)
def test_r3_M4_a_malformed_existing_fill_datetime_is_refused(conn, bad):
    """`fills.fill_datetime` is a bare TEXT NOT NULL, so `2026-07-23garbage`
    is schema-legal. The agreement gate compared only `[:10]` and
    `_corrected_fill_datetime` appends everything after character ten, so it
    would have become `2026-07-31garbage` -- committed, with LEXICALLY ordered
    aggregates recomputed off it and an audit row asserting success."""
    ids = _seed(conn, fill_datetime=bad)
    with pytest.raises(EntryDateCorrectionError, match="fill_datetime"):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT fill_datetime FROM fills WHERE fill_id = ?", (ids["fill_id"],),
    ).fetchone()[0] == bad
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


def test_r3_M4_the_fills_write_boundary_refuses_independently():
    """A write boundary that trusts its caller is not a boundary."""
    import tempfile
    from pathlib import Path as _P

    from swing.data.db import ensure_schema
    from swing.data.repos.fills import update_fill_datetime

    c = ensure_schema(_P(tempfile.mkdtemp()) / "fw.db")
    try:
        c.execute(
            "INSERT INTO trades (ticker, entry_date, entry_price, "
            "initial_shares, initial_stop, current_stop, state, trade_origin, "
            "pre_trade_locked_at) VALUES ('X', '2026-07-23', 1.0, 1, 0.5, "
            "0.5, 'closed', 'manual_off_pipeline', '2026-07-23T16:00:00')",
        )
        fid = int(c.execute(
            "INSERT INTO fills (trade_id, fill_datetime, action, quantity, "
            "price) VALUES (1, '2026-07-23T16:00:00', 'entry', 1.0, 1.0)",
        ).lastrowid)
        for bad in ("2026-07-31garbage", "20260731T160000", "nope"):
            with pytest.raises(ValueError):
                update_fill_datetime(c, fill_id=fid, fill_datetime=bad)
        assert c.execute(
            "SELECT fill_datetime FROM fills WHERE fill_id = ?", (fid,),
        ).fetchone()[0] == "2026-07-23T16:00:00"
        update_fill_datetime(
            c, fill_id=fid, fill_datetime="2026-07-31T16:00:00",
        )
        assert c.execute(
            "SELECT fill_datetime FROM fills WHERE fill_id = ?", (fid,),
        ).fetchone()[0] == "2026-07-31T16:00:00"
    finally:
        c.close()


# ===========================================================================
# Codex R4 fixes
# ===========================================================================


def test_r4_M1_generic_tier3_override_REFUSES_this_correction_head(conn):
    """The generic tier-3 path writes ONE journal column on ONE affected_table
    and recomputes aggregates only for `fills`. This correction wrote THREE
    coupled rows and records them as a single `affected_table='trades'` head,
    so `override-correction <id> --truth-value '{"entry_date": ...}'` would
    move trades.entry_date ALONE -- leaving the bound fill and the archive on
    the old date, emitting no coupled event, and stamping the discrepancy
    `operator_overridden` over an internally inconsistent ledger. The trade
    validator checks only `current_stop` and `state`, so it would not even
    reject a malformed date."""
    from swing.trades.reconciliation_auto_correct import (
        MultiRowCorrectionOverrideError,
        apply_tier3_override,
    )

    ids = _seed(conn)
    result = _apply(conn, ids)
    with pytest.raises(MultiRowCorrectionOverrideError, match="MULTI-ROW"):
        apply_tier3_override(
            conn,
            correction_id=result.correction_id,
            operator_truth_value={"entry_date": "2026-08-03"},
            operator_reason="attempted generic override",
        )
    # Nothing moved, and the discrepancy was NOT dispositioned.
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == TARGET_DATE
    assert conn.execute(
        "SELECT fill_datetime FROM fills WHERE fill_id = ?", (ids["fill_id"],),
    ).fetchone()[0] == f"{TARGET_DATE}T16:00:00"
    assert conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?", (ids["discrepancy_id"],),
    ).fetchone()[0] == "pending_ambiguity_resolution"
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT superseded_by_correction_id FROM reconciliation_corrections "
        "WHERE correction_id = ?", (result.correction_id,),
    ).fetchone()[0] is None


def test_r4_M1_the_refusal_is_keyed_on_the_DURABLE_correction_choice():
    """Keyed on `correction_choice`, not `affected_table` -- the latter is the
    very thing that under-describes a multi-row mutation."""
    from swing.trades.reconciliation_auto_correct import (
        _MULTI_ROW_CORRECTION_CHOICES,
    )

    assert CORRECTION_CHOICE in _MULTI_ROW_CORRECTION_CHOICES


def test_r4_MINOR2_an_active_trade_with_a_BAD_discrepancy_names_the_evidence(
    conn,
):
    """The `--allow-active` refusal is an INSTRUCTION: it asks the operator to
    fetch an acknowledgement, which implies the rest of the request is sound.
    Raising it before the discrepancy has been proved to authorize anything
    sends him after an acknowledgement for a correction that was never going to
    run."""
    ids = _seed(conn, trade_state="managing")
    with pytest.raises(EntryDateCorrectionError) as exc:
        correct_entry_date(
            conn, trade_id=ids["trade_id"], to_date=TARGET_DATE,
            discrepancy_id=999999, reason="x",
        )
    msg = str(exc.value)
    assert "discrepancy 999999 not found" in msg
    assert "--allow-active" not in msg


def test_r4_MINOR2_the_state_gate_still_fires_on_a_GOOD_discrepancy(conn):
    """Counterfactual: the gate moved, it did not disappear."""
    ids = _seed(conn, trade_state="managing")
    with pytest.raises(EntryDateCorrectionError, match="--allow-active"):
        _apply(conn, ids)


# ===========================================================================
# Codex R5 fixes
# ===========================================================================


def test_r5_M1_an_UNRELATED_same_size_order_cannot_date_this_fill(conn):
    """Every clause up to R4 described a SHAPE -- ticker, quantity, side,
    singleton count -- and the emitter binds its sole candidate on exactly that
    shape when the candidate failed price OR side OR session. So order B could
    supply the date for a fill created from order A, moving all three rows
    while the follow-up reason asserts D31 as the cause. `--to` is no
    protection: it confirms the WRONG order's server-derived date.

    The fill already carried the answer and it was being ignored.
    """
    ids = _seed(conn, source_order_id="9999999999999")
    with pytest.raises(EntryDateCorrectionError, match="did not produce"):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == PRE_DATE
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


def test_r5_M1_the_MATCHING_order_id_is_what_makes_the_live_case_pass(conn):
    """Counterfactual, and it is the live shape: fill 39's envelope and
    discrepancy 95's payload both name order 1007308870656."""
    ids = _seed(conn)
    envelope = json.loads(conn.execute(
        "SELECT schwab_source_value_json FROM fills WHERE fill_id = ?",
        (ids["fill_id"],),
    ).fetchone()[0])
    payload = json.loads(conn.execute(
        "SELECT actual_value_json FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?", (ids["discrepancy_id"],),
    ).fetchone()[0])
    assert envelope["schwab_order_id"] == payload["schwab_order_id"]
    _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == TARGET_DATE


@pytest.mark.parametrize(
    "origin", ["operator_typed", "tos_import", "imported_legacy"],
)
def test_r5_M1_a_non_schwab_fill_cannot_be_dated_by_this_surface(conn, origin):
    """It has no Schwab order provenance to bind the evidence to, AND it cannot
    be a D31 victim -- D31 is a defect in the Schwab auto-fill path -- so the
    follow-up reason's causal claim would be false for it."""
    ids = _seed(conn, fill_origin=origin, source_order_id=None)
    with pytest.raises(EntryDateCorrectionError, match="not Schwab-derived"):
        _apply(conn, ids)


def test_r5_M1_a_schwab_fill_with_NO_envelope_is_refused(conn):
    ids = _seed(conn, source_order_id=None)
    with pytest.raises(
        EntryDateCorrectionError, match="missing or unparseable",
    ):
        _apply(conn, ids)


def test_r5_M2_TIER_2_cannot_half_mutate_an_applied_multi_row_correction(conn):
    """`correct_entry_date` deliberately leaves the discrepancy in
    `pending_ambiguity_resolution`, and tier 2 checks only that pending state.
    `_resolve_affected_target` picks `fills` whenever `fill_id` is present and
    the multi-field handler updates that fill ALONE, so the supported CLI could
    move `fills.fill_datetime` without moving trades.entry_date or the archive
    row, then resolve the finding and append a SECOND unsuperseded correction.
    The R4 tier-3 refusal alone was two-thirds of a guard."""
    from swing.trades.reconciliation_auto_correct import (
        MultiRowCorrectionOverrideError,
        apply_tier2_resolution,
    )

    ids = _seed(conn)
    _apply(conn, ids)
    with pytest.raises(MultiRowCorrectionOverrideError, match="MULTI-ROW"):
        apply_tier2_resolution(
            conn,
            discrepancy_id=ids["discrepancy_id"],
            choice_code="pick_schwab_record_1",
            operator_custom_payload={"fill_datetime": "2026-08-05T16:00:00"},
            operator_reason="attempted tier-2 half-mutation",
        )
    assert conn.execute(
        "SELECT fill_datetime FROM fills WHERE fill_id = ?", (ids["fill_id"],),
    ).fetchone()[0] == f"{TARGET_DATE}T16:00:00"
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 1
    assert conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?", (ids["discrepancy_id"],),
    ).fetchone()[0] == "pending_ambiguity_resolution"


def test_r5_M2_TIER_1_is_guarded_too(conn):
    from swing.trades.reconciliation_auto_correct import (
        MultiRowCorrectionOverrideError,
        apply_tier1_correction,
    )

    ids = _seed(conn)
    _apply(conn, ids)
    with pytest.raises(MultiRowCorrectionOverrideError):
        apply_tier1_correction(
            conn, discrepancy_id=ids["discrepancy_id"], classification=None,
        )


def test_r5_M2_the_INTENDED_follow_up_resolution_is_NOT_blocked(conn):
    """The guard must not break the very next step the surface prints. The
    non-mutating manual resolver writes no journal column."""
    from swing.trades.reconciliation import resolve_discrepancy

    ids = _seed(conn)
    _apply(conn, ids)
    resolve_discrepancy(
        conn,
        discrepancy_id=ids["discrepancy_id"],
        resolution="journal_corrected",
        resolution_reason="Journal corrected, not overridden. (follow-up)",
        require_current_resolution="pending_ambiguity_resolution",
    )
    assert conn.execute(
        "SELECT resolution FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?", (ids["discrepancy_id"],),
    ).fetchone()[0] == "journal_corrected"


def test_r5_MINOR_the_state_gate_fires_AFTER_every_other_check(conn):
    """R4's partial move was not enough: an intervening entry fill would still
    reject AFTER the operator had been sent to fetch `--allow-active`."""
    ids = _seed(conn, trade_state="managing")
    _add_second_entry_fill(conn, ids, when="2026-07-25T16:00:00")
    with pytest.raises(EntryDateCorrectionError) as exc:
        _apply(conn, ids)
    assert "would make" in str(exc.value)
    assert "--allow-active" not in str(exc.value)


def test_r5_MINOR_an_unresolvable_archive_row_also_precedes_the_state_gate(
    conn,
):
    ids = _seed(conn, trade_state="managing", archive_rows=0)
    with pytest.raises(EntryDateCorrectionError) as exc:
        _apply(conn, ids)
    assert "found 0" in str(exc.value)
    assert "--allow-active" not in str(exc.value)


# ===========================================================================
# Codex R6 fixes
# ===========================================================================


def _resolve_follow_up(conn, ids):
    from swing.trades.reconciliation import resolve_discrepancy

    resolve_discrepancy(
        conn,
        discrepancy_id=ids["discrepancy_id"],
        resolution="journal_corrected",
        resolution_reason="Journal corrected, not overridden. (follow-up)",
        require_current_resolution="pending_ambiguity_resolution",
    )


def test_r6_M1_tier1_IDEMPOTENCY_survives_the_multi_row_guard(conn):
    """R5's guard sat ABOVE the documented SELECT-first terminal-idempotency
    return, so replaying tier 1 against an already-resolved entry-date
    discrepancy RAISED instead of returning the existing correction. A guard on
    MUTATION must not fire on a path that mutates nothing."""
    from swing.trades.reconciliation_auto_correct import apply_tier1_correction

    ids = _seed(conn)
    _apply(conn, ids)
    _resolve_follow_up(conn, ids)
    result = apply_tier1_correction(
        conn, discrepancy_id=ids["discrepancy_id"], classification=None,
    )
    assert result.correction_id is not None


def test_r6_M1_tier2_AUDIT_ONLY_dispositions_are_not_blocked(conn):
    """`mark_unmatched`, `acknowledge`, `keep_journal_as_is` and `custom`
    change no journal value and are exactly what an operator needs in order to
    CLOSE a finding. R5's guard rejected all four."""
    from swing.trades.reconciliation_auto_correct import apply_tier2_resolution

    ids = _seed(conn)
    _apply(conn, ids)
    result = apply_tier2_resolution(
        conn,
        discrepancy_id=ids["discrepancy_id"],
        choice_code="custom",
        operator_custom_payload={"operator_intent": "audit only"},
        operator_reason="audit-only disposition after the correction",
    )
    assert result is not None
    # The coupled rows are untouched by an audit-only disposition.
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == TARGET_DATE
    assert conn.execute(
        "SELECT fill_datetime FROM fills WHERE fill_id = ?", (ids["fill_id"],),
    ).fetchone()[0] == f"{TARGET_DATE}T16:00:00"


def test_r6_M1_tier2_MUTATING_dispositions_are_still_blocked(conn):
    """Counterfactual for the test above: the guard moved, it did not go."""
    from swing.trades.reconciliation_auto_correct import (
        MultiRowCorrectionOverrideError,
        apply_tier2_resolution,
    )

    ids = _seed(conn)
    _apply(conn, ids)
    with pytest.raises(MultiRowCorrectionOverrideError):
        apply_tier2_resolution(
            conn,
            discrepancy_id=ids["discrepancy_id"],
            choice_code="pick_schwab_record_1",
            operator_custom_payload={"fill_datetime": "2026-08-05T16:00:00"},
            operator_reason="attempted tier-2 half-mutation",
        )


def test_r6_M1_the_audit_only_registry_matches_the_handlers():
    """The classification is enumerated, not inferred, so it is pinned: every
    member delegates STRAIGHT to `_handle_no_mutation_audit`, and no
    NON-member does."""
    import inspect

    from swing.trades import reconciliation_auto_correct as rac

    for fn in rac._AUDIT_ONLY_TIER2_HANDLERS:
        src = inspect.getsource(fn)
        assert "_handle_no_mutation_audit(" in src, fn.__name__
        assert "_update_journal_field(" not in src, fn.__name__
    others = set(rac._TIER2_HANDLERS.values()) - rac._AUDIT_ONLY_TIER2_HANDLERS
    assert others
    for fn in others:
        src = inspect.getsource(fn)
        assert "return _handle_no_mutation_audit(" not in src, fn.__name__


def test_r6_M2_an_operator_EDITED_date_cannot_be_blamed_on_D31(conn):
    """`schwab_auto_then_operator_corrected` means the operator edited one of
    entry_date / entry_price / shares. If he edited the DATE, the recorded
    value is HIS -- and this surface's follow-up reason asserts flatly that
    `entry_auto_fill.py` read `enter_time`. Correcting it would write a FALSE
    CAUSAL STATEMENT into the audit ledger."""
    ids = _seed(conn, fill_origin="schwab_auto_then_operator_corrected")
    # The auto-fill offered 2026-07-30; the operator typed 2026-07-23.
    envelope = json.loads(conn.execute(
        "SELECT schwab_source_value_json FROM fills WHERE fill_id = ?",
        (ids["fill_id"],),
    ).fetchone()[0])
    envelope["entry_date"] = "2026-07-30"
    conn.execute(
        "UPDATE fills SET schwab_source_value_json = ?, "
        "operator_corrected_value_json = ? WHERE fill_id = ?",
        (json.dumps(envelope, sort_keys=True),
         json.dumps({"entry_date": PRE_DATE}, sort_keys=True),
         ids["fill_id"]),
    )
    conn.commit()
    with pytest.raises(EntryDateCorrectionError, match="edited it at the form"):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


def test_r6_M2_a_PRICE_only_operator_correction_still_qualifies(conn):
    """Counterfactual: the origin alone is not disqualifying. Only an edited
    DATE is, because only that makes the D31 causal claim false."""
    ids = _seed(conn, fill_origin="schwab_auto_then_operator_corrected")
    conn.execute(
        "UPDATE fills SET operator_corrected_value_json = ? WHERE fill_id = ?",
        (json.dumps({"entry_price": 18.81}, sort_keys=True), ids["fill_id"]),
    )
    conn.commit()
    _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == TARGET_DATE


@pytest.mark.parametrize(
    "source", ["execution_leg", "enter_time", "something_new"],
)
def test_r6_M2_ANY_post_fix_source_marker_is_refused(conn, source):
    """The key's ABSENCE is the qualifier, not a particular value (sharpened
    by Codex R7 Major 2).

    `execution_leg` says the post-T1 auto-fill took the execution grain.
    `enter_time` says it fell back DELIBERATELY on a malformed leg. Either way
    the fill was written by the FIXED code, so D31 is not its cause -- and this
    surface's reason names D31 flatly. An earlier draft refused only
    `execution_leg`, which would have blamed the old bug for the new code's
    intentional fallback.
    """
    ids = _seed(conn)
    envelope = json.loads(conn.execute(
        "SELECT schwab_source_value_json FROM fills WHERE fill_id = ?",
        (ids["fill_id"],),
    ).fetchone()[0])
    # The LIVE pre-T1 shape has no such key at all.
    assert "entry_date_source" not in envelope
    envelope["entry_date_source"] = source
    conn.execute(
        "UPDATE fills SET schwab_source_value_json = ? WHERE fill_id = ?",
        (json.dumps(envelope, sort_keys=True), ids["fill_id"]),
    )
    conn.commit()
    with pytest.raises(EntryDateCorrectionError, match="POST-D31"):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


def test_r6_M2_a_HISTORICAL_envelope_with_no_source_key_qualifies(conn):
    """Counterfactual, and the founding case: every fill recorded before T1
    shipped has NO `entry_date_source` key -- live fill 39 included -- and
    those are precisely the D31 victims this surface exists for."""
    ids = _seed(conn)
    assert "entry_date_source" not in json.loads(conn.execute(
        "SELECT schwab_source_value_json FROM fills WHERE fill_id = ?",
        (ids["fill_id"],),
    ).fetchone()[0])
    _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == TARGET_DATE


# ===========================================================================
# Codex R7 fixes
# ===========================================================================


def test_r7_M1_the_audit_only_then_tier3_BYPASS_is_closed(conn):
    """The three-command bypass R6's fix opened.

    `correct-entry-date` -> an AUDIT-ONLY tier-2 disposition (permitted, and it
    appends its OWN unsuperseded correction with a harmless choice, without
    superseding the multi-row head) -> `override-correction <that new head>
    --truth-value '{"fill_datetime": ...}'`. Tier 3 checked only the SELECTED
    row's choice, so the newer head sailed past -- moving the fill alone,
    leaving trades.entry_date and the archive row behind, and terminally
    resolving the discrepancy. The barrier belongs to the FINDING, not to one
    row of its chain.
    """
    from swing.trades.reconciliation_auto_correct import (
        MultiRowCorrectionOverrideError,
        apply_tier2_resolution,
        apply_tier3_override,
    )

    ids = _seed(conn)
    _apply(conn, ids)
    audit_head = apply_tier2_resolution(
        conn,
        discrepancy_id=ids["discrepancy_id"],
        choice_code="custom",
        operator_custom_payload={"operator_intent": "audit only"},
        operator_reason="audit-only disposition",
    )
    assert audit_head.correction_id is not None

    with pytest.raises(MultiRowCorrectionOverrideError):
        apply_tier3_override(
            conn,
            correction_id=audit_head.correction_id,
            operator_truth_value={"fill_datetime": "2026-08-05T16:00:00"},
            operator_reason="attempted bypass via the audit-only head",
        )
    assert conn.execute(
        "SELECT fill_datetime FROM fills WHERE fill_id = ?", (ids["fill_id"],),
    ).fetchone()[0] == f"{TARGET_DATE}T16:00:00"
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == TARGET_DATE
    assert conn.execute(
        "SELECT removed_date FROM watchlist_archive WHERE ticker='FTRE'",
    ).fetchone()[0] == TARGET_DATE


def test_r7_M2_a_ZERO_quantity_pseudo_leg_cannot_supply_the_date(conn):
    """The sum check alone was not enough. A real 10-share leg on the RECORDED
    date plus a zero-quantity pseudo-leg on a LATER date sums to 10 and passed
    -- and `latest_execution_leg_date` then picked the pseudo-leg's date to
    rewrite three ledger rows. `SchwabExecutionLeg` rejects a non-positive
    quantity at construction, so this payload could never have come from the
    production model; `insert_discrepancy` stores JSON, not that model."""
    payload = json.loads(_live_actual_value_json())
    payload["execution_legs"] = [
        {"leg_id": 1, "price": 18.8, "quantity": 10.0,
         "time": f"{PRE_DATE}T13:30:05+0000"},
        {"leg_id": 2, "price": 18.8, "quantity": 0.0,
         "time": f"{TARGET_DATE}T13:30:05+0000"},
    ]
    ids = _seed(conn, actual_value_json=json.dumps(payload, sort_keys=True))
    with pytest.raises(
        EntryDateCorrectionError, match="finite and strictly positive",
    ):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == PRE_DATE
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


@pytest.mark.parametrize("bad_qty", [0.0, -5.0])
def test_r7_M2_every_leg_quantity_must_be_finite_and_positive(conn, bad_qty):
    """`inf` / `nan` are deliberately NOT parametrized here: they are
    UNREACHABLE through the read path. `ReconciliationDiscrepancy.__post_init__`
    parses `actual_value_json` with `parse_constant=
    _reject_non_standard_constant` (models.py), so a payload containing
    `Infinity` or `NaN` raises before `get_discrepancy` can return it -- the
    schema-prevented class, cited rather than assumed. The `math.isfinite`
    clause in the service stays as a belt for a future caller that does not
    come through that reader.
    """
    payload = json.loads(_live_actual_value_json())
    payload["execution_legs"] = [
        {"leg_id": 1, "price": 18.8, "quantity": bad_qty, "time": LIVE_LEG_TIME},
    ]
    ids = _seed(conn, actual_value_json=json.dumps(payload, sort_keys=True))
    with pytest.raises(EntryDateCorrectionError):
        _apply(conn, ids)


# ===========================================================================
# Codex R8 fixes
# ===========================================================================


def test_r8_M1_a_MIXED_date_and_price_discrepancy_is_refused(conn):
    """Shape-D fires when the sole candidate fails price OR side OR session, so
    one row can carry BOTH a wrong date and a genuine execution-price
    divergence. This surface corrects only the DATE, then stamps the fill
    `reconciled_discrepancy_resolved` and prints a `journal_corrected`
    follow-up that CLOSES the finding -- so a real, material price error would
    be silently discharged by a correction that never touched it.

    The shared fixture masked this by forcing payload, legs and fill all to
    $18.80 -- which is exactly why trade 19 IS a legitimate case ($+0.0000).
    """
    payload = json.loads(_live_actual_value_json())
    payload["price"] = 19.25
    payload["execution_legs"][0]["price"] = 19.25
    ids = _seed(conn, actual_value_json=json.dumps(payload, sort_keys=True))
    with pytest.raises(EntryDateCorrectionError, match="ALSO a price mismatch"):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == PRE_DATE
    assert conn.execute(
        "SELECT reconciliation_status FROM fills WHERE fill_id = ?",
        (ids["fill_id"],),
    ).fetchone()[0] == "unreconciled"
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


def test_r8_M1_the_live_zero_delta_case_is_what_qualifies(conn):
    """Counterfactual: discrepancy 95's real `$+0.0000` is what makes it a pure
    DATE finding."""
    ids = _seed(conn)
    payload = json.loads(conn.execute(
        "SELECT actual_value_json FROM reconciliation_discrepancies "
        "WHERE discrepancy_id = ?", (ids["discrepancy_id"],),
    ).fetchone()[0])
    assert payload["price"] == 18.8
    _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == TARGET_DATE


def test_r8_M3_a_move_PAST_an_existing_exit_is_refused(conn):
    """The authority check looks only at other ENTRY fills. A closed trade with
    a stop on 07-25 would otherwise accept an entry move 07-23 -> 07-31: the
    stop would sit BEFORE the entry, `_recompute_aggregates` would move
    `last_fill_at` onto the later entry on a CLOSED trade, and the audit row
    would record that impossible chronology as successfully applied."""
    ids = _seed(conn)
    conn.execute(
        "UPDATE fills SET fill_datetime = '2026-07-25T16:00:00' "
        "WHERE trade_id = ? AND action = 'stop'", (ids["trade_id"],),
    )
    conn.commit()
    with pytest.raises(EntryDateCorrectionError, match="cannot exit before"):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == PRE_DATE
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


def test_r8_M3_an_exit_AFTER_the_target_date_still_permits_the_move(conn):
    """Counterfactual, and the live shape: trade 19's stop is 08-04, after the
    07-31 target."""
    ids = _seed(conn)
    _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == TARGET_DATE


def test_r8_M2_a_NEW_discrepancy_on_the_same_fill_cannot_mutate_it(conn):
    """The barrier was scoped to ONE discrepancy id. A LATER reconciliation run
    emits a NEW discrepancy for the SAME fill; that id carries no multi-row
    correction, so its mutating tier-2 path sailed through --
    `split_into_partials` DELETES the corrected fill and replaces it with
    differently-dated partials, while `trades.entry_date` and the archive row
    stay on the corrected date and the surviving correction keeps asserting a
    value for a fill that no longer exists. The coupling lives on the FILL, so
    the barrier has to as well.
    """
    from swing.trades.reconciliation_auto_correct import (
        MultiRowCorrectionOverrideError,
        apply_tier2_resolution,
    )

    ids = _seed(conn)
    _apply(conn, ids)

    # A LATER run raises a fresh finding against the very same fill.
    run2 = int(conn.execute(
        "INSERT INTO reconciliation_runs (source, started_ts, state) VALUES "
        "('schwab_api', '2026-08-10T03:00:00', 'completed')",
    ).lastrowid)
    disc2 = int(conn.execute(
        "INSERT INTO reconciliation_discrepancies (run_id, discrepancy_type, "
        "trade_id, fill_id, ticker, field_name, expected_value_json, "
        "actual_value_json, material_to_review, resolution, ambiguity_kind, "
        "created_at) VALUES (?, 'entry_price_mismatch', ?, ?, 'FTRE', "
        "'price', '{}', '{}', 1, 'pending_ambiguity_resolution', "
        "'multi_partial_vs_consolidated', '2026-08-10T03:00:00')",
        (run2, ids["trade_id"], ids["fill_id"]),
    ).lastrowid)
    conn.commit()

    with pytest.raises(MultiRowCorrectionOverrideError, match="bound by"):
        apply_tier2_resolution(
            conn,
            discrepancy_id=disc2,
            choice_code="split_into_partials",
            operator_custom_payload={"partials": []},
            operator_reason="attempted cross-discrepancy mutation",
        )
    assert conn.execute(
        "SELECT fill_datetime FROM fills WHERE fill_id = ?", (ids["fill_id"],),
    ).fetchone()[0] == f"{TARGET_DATE}T16:00:00"


def test_r8_M2_a_DIFFERENT_fill_is_NOT_blocked(conn):
    """Scoped to the bound fill and no wider: another fill on the same trade is
    untouched by the barrier (an over-broad block would permanently freeze
    every future correction on a trade that ever had its entry date fixed)."""
    from swing.trades.reconciliation_auto_correct import (
        _multi_row_bound_fill_ids,
    )

    ids = _seed(conn)
    other_fill = _add_second_entry_fill(conn, ids, when="2026-08-03T16:00:00")
    _apply(conn, ids)
    bound = _multi_row_bound_fill_ids(conn)
    assert ids["fill_id"] in bound
    assert other_fill not in bound


def test_r8_M2_the_bound_fill_id_is_recorded_in_the_audit_row(conn):
    """The binding is DURABLE -- read out of the correction's own
    `applied_value_json`, which this surface owns."""
    from swing.trades.reconciliation_auto_correct import (
        MULTI_ROW_BOUND_FILL_KEY,
    )

    ids = _seed(conn)
    result = _apply(conn, ids)
    applied = json.loads(conn.execute(
        "SELECT applied_value_json FROM reconciliation_corrections "
        "WHERE correction_id = ?", (result.correction_id,),
    ).fetchone()[0])
    pre = json.loads(conn.execute(
        "SELECT pre_correction_value_json FROM reconciliation_corrections "
        "WHERE correction_id = ?", (result.correction_id,),
    ).fetchone()[0])
    assert applied[MULTI_ROW_BOUND_FILL_KEY] == ids["fill_id"]
    assert pre[MULTI_ROW_BOUND_FILL_KEY] == ids["fill_id"]


# ===========================================================================
# Codex R9 fixes
# ===========================================================================


def test_r9_M1_trades_entry_date_is_RESERVED_from_the_generic_path(conn):
    """The fill-scoped barrier checked only mutations resolving to `fills`. A
    later `position_qty_mismatch` for the same trade has a `trade_id` and NO
    `fill_id`, so `_resolve_affected_target` resolves it to `trades` and sails
    past -- and the tier-2 `operator_truth` handler accepts an arbitrary key
    because `validate_trade_correction` checks only `current_stop` and `state`.
    `trades.entry_date` would move ALONE while the fill and the archive row
    stayed on the corrected date, and the surviving correction row would keep
    asserting that all three agree.

    Refusing the COLUMN closes every generic path at once, and holds even when
    no multi-row correction exists to compare against.
    """
    from swing.trades.reconciliation_auto_correct import (
        ReservedJournalFieldError,
        _update_journal_field,
    )

    ids = _seed(conn)
    _apply(conn, ids)
    with pytest.raises(ReservedJournalFieldError, match="correct-entry-date"):
        _update_journal_field(
            conn, "trades", ids["trade_id"], "entry_date", "2026-08-05",
        )
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == TARGET_DATE


def test_r9_M1_a_LATER_trade_scoped_discrepancy_cannot_uncouple_the_date(conn):
    """The concrete route, driven through the supported tier-2 entry point."""
    from swing.trades.reconciliation_auto_correct import (
        ReservedJournalFieldError,
        apply_tier2_resolution,
    )

    ids = _seed(conn)
    _apply(conn, ids)
    run2 = int(conn.execute(
        "INSERT INTO reconciliation_runs (source, started_ts, state) VALUES "
        "('schwab_api', '2026-08-10T03:00:00', 'completed')",
    ).lastrowid)
    disc2 = int(conn.execute(
        "INSERT INTO reconciliation_discrepancies (run_id, discrepancy_type, "
        "trade_id, ticker, field_name, expected_value_json, "
        "actual_value_json, material_to_review, resolution, ambiguity_kind, "
        "created_at) VALUES (?, 'position_qty_mismatch', ?, 'FTRE', "
        "'quantity', '{}', '{}', 1, 'pending_ambiguity_resolution', "
        "'unknown_schwab_subtype', '2026-08-10T03:00:00')",
        (run2, ids["trade_id"]),
    ).lastrowid)
    conn.commit()

    with pytest.raises(ReservedJournalFieldError):
        apply_tier2_resolution(
            conn,
            discrepancy_id=disc2,
            choice_code="operator_truth",
            operator_custom_payload={"entry_date": "2026-08-05"},
            operator_reason="attempted trade-scoped uncoupling",
        )
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == TARGET_DATE
    assert conn.execute(
        "SELECT fill_datetime FROM fills WHERE fill_id = ?", (ids["fill_id"],),
    ).fetchone()[0] == f"{TARGET_DATE}T16:00:00"


def test_r9_M1_an_UNRELATED_trade_field_is_still_writable(conn):
    """Counterfactual: exactly ONE column is reserved, not the table."""
    from swing.trades.reconciliation_auto_correct import _update_journal_field

    ids = _seed(conn)
    _update_journal_field(
        conn, "trades", ids["trade_id"], "current_stop", 17.0,
    )
    assert conn.execute(
        "SELECT current_stop FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == 17.0


def test_r9_M2_the_audit_row_names_the_ARCHIVE_row_it_changed(conn):
    """The archive row is updated BY PRIMARY KEY and the correction's formal
    `affected_row_id` names only the TRADE, so without this the append-only
    trail could not reconstruct one of its own three mutations -- and a sibling
    archive row carrying the same ticker and target date would leave the change
    unattributable."""
    from swing.trades.entry_date_correction import BOUND_ARCHIVE_KEY

    ids = _seed(conn)
    archive_id = conn.execute(
        "SELECT id FROM watchlist_archive WHERE ticker='FTRE'",
    ).fetchone()[0]
    result = _apply(conn, ids)
    for column in ("pre_correction_value_json", "applied_value_json"):
        envelope = json.loads(conn.execute(
            f"SELECT {column} FROM reconciliation_corrections "  # noqa: S608
            "WHERE correction_id = ?", (result.correction_id,),
        ).fetchone()[0])
        assert envelope[BOUND_ARCHIVE_KEY] == archive_id
    # And the trade_events payload carries the same dicts, so a forensic
    # replay reads the identity too.
    payload = json.loads(conn.execute(
        "SELECT payload_json FROM trade_events WHERE trade_id = ? AND "
        "event_type = 'reconciliation_auto_correct'", (ids["trade_id"],),
    ).fetchone()[0])
    assert payload["pre"][BOUND_ARCHIVE_KEY] == archive_id
    assert payload["applied"][BOUND_ARCHIVE_KEY] == archive_id


# ===========================================================================
# THE COUPLING INVARIANT, stated and enforced (coordinator steer, mid-loop)
#
# R6-R9 were four holes in one guard whose UNIT OF COUPLING had never been
# decided -- it was being discovered by counterexample. The invariant:
#
#   trades.entry_date, the AUTHORITATIVE entry fill's fills.fill_datetime
#   date-prefix, and the reason='entered' watchlist_archive.removed_date for
#   that trade MUST always name the SAME calendar date; any write that changes
#   one MUST change all three in one transaction.
#
# Enforced STRUCTURALLY: the coupled COLUMNS are reserved to the dedicated
# surface at the single generic writer, and the bound FILL cannot be destroyed.
# Neither depends on a correction row existing.
# ===========================================================================


def test_INVARIANT_the_three_coupled_dates_agree_after_a_correction(conn):
    """The invariant itself, asserted end-to-end rather than inferred from the
    three separate field assertions."""
    ids = _seed(conn)
    _apply(conn, ids)
    trade_date = conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0]
    fill_date = conn.execute(
        "SELECT substr(fill_datetime, 1, 10) FROM fills WHERE fill_id = ?",
        (ids["fill_id"],),
    ).fetchone()[0]
    archive_date = conn.execute(
        "SELECT removed_date FROM watchlist_archive WHERE ticker = 'FTRE' "
        "AND reason = 'entered'",
    ).fetchone()[0]
    assert trade_date == fill_date == archive_date == TARGET_DATE


def test_INVARIANT_an_ENTRY_fills_datetime_is_reserved_from_the_generic_path(
    conn,
):
    """The second leg of the triple. Previously reachable through tier-2
    `pick_schwab_record_N` with a `fill_datetime` custom value, and blocked
    only by a correction-keyed barrier -- so with NO correction present the
    coupling could be broken from a standing start. The affordance is REMOVED
    rather than validated a fourth time (the item-4 precedent); writing an
    entry fill's datetime without moving the other two IS the incoherent
    operation."""
    from swing.trades.reconciliation_auto_correct import (
        ReservedJournalFieldError,
        _update_journal_field,
    )

    ids = _seed(conn)  # NO correction applied -- the guard must not need one.
    with pytest.raises(ReservedJournalFieldError, match="correct-entry-date"):
        _update_journal_field(
            conn, "fills", ids["fill_id"], "fill_datetime",
            "2026-08-05T16:00:00",
        )
    assert conn.execute(
        "SELECT fill_datetime FROM fills WHERE fill_id = ?", (ids["fill_id"],),
    ).fetchone()[0] == f"{PRE_DATE}T16:00:00"


def test_INVARIANT_a_NON_entry_fills_datetime_is_still_writable(conn):
    """Scoped to the ROW, not the column: an exit / trim / stop fill's datetime
    is not part of the coupling, and correcting one is a legitimate tier-2
    operation this must not remove. The ban is exactly as wide as the
    invariant."""
    from swing.trades.reconciliation_auto_correct import _update_journal_field

    ids = _seed(conn)
    stop_fill = conn.execute(
        "SELECT fill_id FROM fills WHERE trade_id = ? AND action = 'stop'",
        (ids["trade_id"],),
    ).fetchone()[0]
    _update_journal_field(
        conn, "fills", stop_fill, "fill_datetime", "2026-08-05T16:00:00",
    )
    assert conn.execute(
        "SELECT fill_datetime FROM fills WHERE fill_id = ?", (stop_fill,),
    ).fetchone()[0] == "2026-08-05T16:00:00"


def test_INVARIANT_a_fills_PRICE_is_still_writable(conn):
    """Counterfactual on the column axis: only the coupled column is reserved,
    and the tier-1 price correction this project's whole reconciliation
    machinery exists for is untouched."""
    from swing.trades.reconciliation_auto_correct import _update_journal_field

    ids = _seed(conn)
    _update_journal_field(conn, "fills", ids["fill_id"], "price", 18.9)
    assert conn.execute(
        "SELECT price FROM fills WHERE fill_id = ?", (ids["fill_id"],),
    ).fetchone()[0] == 18.9


def test_INVARIANT_the_reservation_needs_NO_correction_row_to_exist(conn):
    """The structural property that the correction-keyed barriers could never
    have: with zero corrections in the table, both coupled columns are already
    unwritable by the generic path."""
    from swing.trades.reconciliation_auto_correct import (
        ReservedJournalFieldError,
        _update_journal_field,
    )

    ids = _seed(conn)
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0
    for table, row_id, field, value in (
        ("trades", ids["trade_id"], "entry_date", "2026-08-05"),
        ("fills", ids["fill_id"], "fill_datetime", "2026-08-05T16:00:00"),
    ):
        with pytest.raises(ReservedJournalFieldError):
            _update_journal_field(conn, table, row_id, field, value)


def test_INVARIANT_watchlist_archive_has_no_generic_write_path_at_all():
    """The third leg needs no reservation: `watchlist_archive` is not a member
    of the `affected_table` enum, so `_update_journal_field` cannot reach it
    and neither can any tier. Pinned so a future widening of that enum has to
    confront this."""
    from swing.data.models import ReconciliationCorrection  # noqa: F401
    from swing.trades import reconciliation_auto_correct as rac

    tables = {
        rac._AFFECTED_TABLE_FILLS, rac._AFFECTED_TABLE_TRADES,
        rac._AFFECTED_TABLE_CASH, rac._AFFECTED_TABLE_SNAPSHOTS,
    }
    assert "watchlist_archive" not in tables


# ===========================================================================
# Codex R10 fixes
# ===========================================================================


def test_r10_M1_leg_prices_are_authenticated_against_the_summary_and_fill(conn):
    """The LEGS are the evidence of record; the summary `price` is a DERIVED
    field the emitter wrote. A payload whose summary reads 18.80 while its
    10-share leg reads 19.25 satisfied the summary-vs-fill check alone and
    would have moved all three ledger values, stamped the fill reconciled, and
    closed a finding whose own cited legs prove a material price error. The R8
    test masked it by changing BOTH values together."""
    payload = json.loads(_live_actual_value_json())
    payload["price"] = 18.8               # agrees with the fill
    payload["execution_legs"][0]["price"] = 19.25   # ...the legs do not
    ids = _seed(conn, actual_value_json=json.dumps(payload, sort_keys=True))
    with pytest.raises(EntryDateCorrectionError, match="disagrees with itself"):
        _apply(conn, ids)
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 0


@pytest.mark.parametrize("bad_price", [0.0, -1.0])
def test_r10_M1_every_leg_price_must_be_finite_and_positive(conn, bad_price):
    payload = json.loads(_live_actual_value_json())
    payload["execution_legs"][0]["price"] = bad_price
    ids = _seed(conn, actual_value_json=json.dumps(payload, sort_keys=True))
    with pytest.raises(EntryDateCorrectionError, match="leg price"):
        _apply(conn, ids)


def test_r10_M1_a_MULTI_LEG_vwap_that_matches_the_fill_still_qualifies(conn):
    """Counterfactual, with the same VWAP math `_compute_execution_price`
    uses: two 5-share legs at 18.70 and 18.90 VWAP to 18.80."""
    payload = json.loads(_live_actual_value_json(
        leg_times=(LIVE_LEG_TIME, "2026-07-31T13:31:00+0000"),
    ))
    payload["execution_legs"][0]["price"] = 18.70
    payload["execution_legs"][1]["price"] = 18.90
    ids = _seed(conn, actual_value_json=json.dumps(payload, sort_keys=True))
    _apply(conn, ids)
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == TARGET_DATE


def _second_finding(conn, ids, *, target: str, order_id: str = "1007308870656"):
    """A LATER discrepancy citing the same order with newer broker evidence."""
    run2 = int(conn.execute(
        "INSERT INTO reconciliation_runs (source, started_ts, state) VALUES "
        "('schwab_api', '2026-08-10T03:00:00', 'completed')",
    ).lastrowid)
    payload = json.loads(_live_actual_value_json(
        leg_times=(f"{target}T13:30:05+0000",),
    ))
    payload["schwab_order_id"] = order_id
    disc2 = int(conn.execute(
        "INSERT INTO reconciliation_discrepancies (run_id, discrepancy_type, "
        "trade_id, fill_id, ticker, field_name, expected_value_json, "
        "actual_value_json, material_to_review, resolution, ambiguity_kind, "
        "created_at) VALUES (?, 'entry_price_mismatch', ?, ?, 'FTRE', "
        "'price', ?, ?, 1, 'pending_ambiguity_resolution', "
        "'multi_match_within_window', '2026-08-10T03:00:00')",
        (run2, ids["trade_id"], ids["fill_id"],
         json.dumps({"price": 18.8}), json.dumps(payload, sort_keys=True)),
    ).lastrowid)
    conn.commit()
    return disc2


def test_r10_M2_a_correction_CAN_be_re_corrected_and_the_chain_records_it(conn):
    """Every refusal message in this surface tells the operator to re-run
    `correct-entry-date` against a current finding. That was FALSE: the first
    correction leaves the auto-fill envelope's `entry_date` at its ORIGINAL
    value while the fill holds the corrected one, so the provenance check read
    it as an operator edit and refused -- a wrongly-corrected money-bearing
    ledger value would have been permanent short of hand-editing SQLite.
    """
    ids = _seed(conn)
    first = _apply(conn, ids)
    later = "2026-08-03"
    disc2 = _second_finding(conn, ids, target=later)

    second = correct_entry_date(
        conn, trade_id=ids["trade_id"], to_date=later,
        discrepancy_id=disc2, reason="newer broker evidence",
    )
    # All three coupled rows moved AGAIN, together.
    assert conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?", (ids["trade_id"],),
    ).fetchone()[0] == later
    assert conn.execute(
        "SELECT substr(fill_datetime, 1, 10) FROM fills WHERE fill_id = ?",
        (ids["fill_id"],),
    ).fetchone()[0] == later
    assert conn.execute(
        "SELECT removed_date FROM watchlist_archive WHERE ticker='FTRE'",
    ).fetchone()[0] == later
    # APPEND-ONLY: the prior head is SUPERSEDED, not rewritten, and exactly one
    # live head remains -- two would be the correction-chain corruption state.
    assert conn.execute(
        "SELECT superseded_by_correction_id FROM reconciliation_corrections "
        "WHERE correction_id = ?", (first.correction_id,),
    ).fetchone()[0] == second.correction_id
    heads = conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections "
        "WHERE superseded_by_correction_id IS NULL",
    ).fetchone()[0]
    assert heads == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM reconciliation_corrections",
    ).fetchone()[0] == 2


def test_r10_M2_the_re_correction_still_needs_FRESH_evidence(conn):
    """The escape hatch is not a bypass: the second correction runs the whole
    authorization ladder against its own discrepancy."""
    ids = _seed(conn)
    _apply(conn, ids)
    disc2 = _second_finding(conn, ids, target="2026-08-03",
                            order_id="9999999999999")
    with pytest.raises(EntryDateCorrectionError, match="did not produce"):
        correct_entry_date(
            conn, trade_id=ids["trade_id"], to_date="2026-08-03",
            discrepancy_id=disc2, reason="wrong order",
        )


def test_r10_M2_an_OPERATOR_edit_after_a_correction_is_still_refused(conn):
    """Counterfactual: the relaxation admits a PRIOR CORRECTION's applied date
    and nothing else. A hand-edited fill date still fails provenance."""
    ids = _seed(conn)
    _apply(conn, ids)
    conn.execute(
        "UPDATE fills SET fill_datetime = '2026-07-29T16:00:00' "
        "WHERE fill_id = ?", (ids["fill_id"],),
    )
    conn.execute(
        "UPDATE trades SET entry_date = '2026-07-29' WHERE id = ?",
        (ids["trade_id"],),
    )
    conn.execute(
        "UPDATE watchlist_archive SET removed_date = '2026-07-29' "
        "WHERE ticker = 'FTRE'",
    )
    conn.commit()
    disc2 = _second_finding(conn, ids, target="2026-08-03")
    with pytest.raises(EntryDateCorrectionError, match="edited it at the form"):
        correct_entry_date(
            conn, trade_id=ids["trade_id"], to_date="2026-08-03",
            discrepancy_id=disc2, reason="after a hand edit",
        )


def test_r10_M2_the_barrier_LIFTS_once_the_head_is_superseded(conn):
    """The fill-scoped barrier filters on `superseded_by_correction_id IS
    NULL`, so chaining is what makes the surface's own instruction true."""
    from swing.trades.reconciliation_auto_correct import (
        _multi_row_bound_fill_ids,
    )

    ids = _seed(conn)
    first = _apply(conn, ids)
    assert _multi_row_bound_fill_ids(conn)[ids["fill_id"]] == first.correction_id
    disc2 = _second_finding(conn, ids, target="2026-08-03")
    second = correct_entry_date(
        conn, trade_id=ids["trade_id"], to_date="2026-08-03",
        discrepancy_id=disc2, reason="newer broker evidence",
    )
    assert _multi_row_bound_fill_ids(conn)[ids["fill_id"]] == (
        second.correction_id
    )
