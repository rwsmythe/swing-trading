"""Task 7 -- the write path, the audit row, idempotency and DRIFT reporting.

A frozen snapshot nobody compares is DECORATION, so every freeze here is
paired with a test that mutates the cited row through the PRODUCTION path and
asserts the drift line.
"""
from __future__ import annotations

import json
import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.data.repos.provenance_corrections import (
    get_correction_for_trade,
    list_provenance_corrections,
)
from swing.metrics.funnel import APLUS_TRADE_ORIGIN
from swing.trades.cohort_provenance_correction import (
    CITATION_ANCHOR_DRIFT,
    CITATION_ANCHOR_UNVERIFIABLE,
    CITATION_DRIFT,
    CITATION_INVALIDATED,
    CITATION_SCHEMA_DRIFT,
    DERIVATION_RULE_VERSION,
    CallerHeldTransactionError,
    CohortProvenanceCorrectionError,
    correct_cohort_provenance,
    preview_cohort_provenance_correction,
    read_provenance_corrections,
)
from tests.trades._cohort_provenance_fixtures import (
    CADL_ACTION_SESSION,
    CADL_F,
    CADL_FILL_DATETIME,
    CADL_LABEL,
    CADL_PIPELINE_FINISHED_LOCAL,
    CADL_RUN_TS_LOCAL,
    build_cadl_case,
    seed_fill,
)

REASON = "the framework's own contemporaneous record"
RUN_TS_UTC = "2026-08-11T03:30:26"
UPPER_UTC = "2026-08-11T03:44:45"


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = ensure_schema(tmp_path / "swing.db")
    try:
        yield c
    finally:
        c.close()


def _apply(conn, ids, *, reason=REASON, candidate_id=None,
           recommendation_id=None):
    # Fixture seeding leaves an open implicit transaction; that is the
    # FIXTURE's, not a caller-held one, and the service (correctly) refuses to
    # run inside any open transaction. The dedicated contract test below calls
    # `correct_cohort_provenance` DIRECTLY under an explicit BEGIN IMMEDIATE.
    if conn.in_transaction:
        conn.commit()
    return correct_cohort_provenance(
        conn,
        trade_id=ids["trade_id"],
        cited_candidate_id=candidate_id or ids["candidate_id"],
        cited_recommendation_id=(
            recommendation_id or ids["daily_recommendation_id"]),
        reason=reason,
    )


def _cohort_row(conn, trade_id):
    return conn.execute(
        "SELECT hypothesis_label, candidate_id, trade_origin FROM trades "
        "WHERE id = ?", (trade_id,)).fetchone()


# ----------------------------------------------------------- the happy path


def test_apply_writes_the_three_keys_and_one_audit_row(conn) -> None:
    ids = build_cadl_case(conn)
    result = _apply(conn, ids)
    assert result.already_applied is False
    assert _cohort_row(conn, ids["trade_id"]) == (
        CADL_LABEL, ids["candidate_id"], APLUS_TRADE_ORIGIN)
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 1


def test_the_audit_row_carries_every_citation_and_frozen_anchor(conn) -> None:
    ids = build_cadl_case(conn)
    result = _apply(conn, ids)
    row = get_correction_for_trade(conn, ids["trade_id"])
    assert row.provenance_correction_id == result.correction_id
    assert row.cited_candidate_id == ids["candidate_id"]
    assert row.cited_daily_recommendation_id == ids["daily_recommendation_id"]
    assert row.cited_evaluation_run_id == ids["evaluation_run_id"]
    assert row.cited_pipeline_run_id == ids["pipeline_run_id"]
    assert row.cited_hypothesis_id == 1
    assert row.cited_hypothesis_status_at_record == "active"
    assert row.cited_hypothesis_name_at_correction == "A+ baseline"
    assert row.cited_candidate_action_session_date == CADL_ACTION_SESSION
    assert row.cited_recommendation_action_session_date == CADL_ACTION_SESSION
    assert row.entry_fill_session_date == CADL_F
    assert row.entry_fill_id == ids["fill_id"]
    assert row.entry_fill_id_at_correction == ids["fill_id"]
    assert row.derivation_rule_version == DERIVATION_RULE_VERSION
    assert row.applied_by == "operator"
    # The FOUR clock columns, each with one job -- and the _utc pair is NOT
    # equal to its _raw sibling, which is proof the conversion happened.
    assert row.cited_run_ts_raw == CADL_RUN_TS_LOCAL
    assert row.cited_run_ts_utc == RUN_TS_UTC
    assert row.cited_pipeline_finished_ts_raw == CADL_PIPELINE_FINISHED_LOCAL
    assert row.cited_status_window_upper_utc == UPPER_UTC
    assert row.cited_run_ts_utc != row.cited_run_ts_raw
    assert row.cited_status_window_upper_utc != row.cited_pipeline_finished_ts_raw
    # Pre/post envelopes.
    assert json.loads(row.pre_value_json) == {
        "trades.hypothesis_label": None,
        "trades.candidate_id": None,
        "trades.trade_origin": "manual_off_pipeline",
    }
    assert json.loads(row.applied_value_json) == {
        "trades.hypothesis_label": CADL_LABEL,
        "trades.candidate_id": ids["candidate_id"],
        "trades.trade_origin": APLUS_TRADE_ORIGIN,
    }
    # The snapshots are BOUND to the rows they claim.
    fill_snap = json.loads(row.entry_fill_snapshot_json)
    assert fill_snap["fill_id"] == ids["fill_id"]
    assert fill_snap["fill_datetime"] == CADL_FILL_DATETIME
    dr_snap = json.loads(row.cited_recommendation_snapshot_json)
    assert dr_snap["id"] == ids["daily_recommendation_id"]
    assert dr_snap["action_text"] is not None  # PRAGMA-derived, not hand-listed
    pipe_snap = json.loads(row.cited_pipeline_run_snapshot_json)
    assert pipe_snap["state"] == "complete"
    assert pipe_snap["finished_ts"] == CADL_PIPELINE_FINISHED_LOCAL


def test_the_composed_reason_explains_its_own_string(conn) -> None:
    ids = build_cadl_case(conn)
    result = _apply(conn, ids)
    reason = result.correction_reason
    assert REASON in reason
    assert f"candidates row {ids['candidate_id']}" in reason
    assert f"daily_recommendations row {ids['daily_recommendation_id']}" in reason
    assert CADL_F in reason
    assert repr(CADL_LABEL) in reason
    assert DERIVATION_RULE_VERSION in reason
    # The `na`-rendered-as-`failed:` wart is NAMED, not hidden.
    assert "TT8_rs_rank" in reason and "`na`" in reason


def test_no_trade_events_row_is_emitted(conn) -> None:
    """Deliberate: no member of the seven-value trade_events CHECK enum
    truthfully names an operator cohort-provenance correction, and writing a
    MISLABELLED audit record beside a purpose-built correct one is the precise
    failure this arc exists to stop."""
    ids = build_cadl_case(conn)
    before = conn.execute("SELECT COUNT(*) FROM trade_events").fetchone()[0]
    _apply(conn, ids)
    assert conn.execute(
        "SELECT COUNT(*) FROM trade_events").fetchone()[0] == before


def test_output_is_ascii_only(conn) -> None:
    """Windows cp1252 crashes on a non-ASCII glyph in any click.echo path, and
    capsys hides it."""
    ids = build_cadl_case(conn)
    result = _apply(conn, ids)
    for text in (result.correction_reason, result.follow_up_command):
        text.encode("ascii")
    for report in read_provenance_corrections(conn):
        for line in report.drift_lines:
            line.encode("ascii")


# ------------------------------------------------------------- idempotency


def test_an_identical_re_run_returns_the_same_id_and_writes_nothing(
    conn,
) -> None:
    ids = build_cadl_case(conn)
    first = _apply(conn, ids)
    trade_before = conn.execute(
        "SELECT * FROM trades WHERE id = ?", (ids["trade_id"],)).fetchone()
    second = _apply(conn, ids)
    assert second.already_applied is True
    assert second.correction_id == first.correction_id
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 1
    assert conn.execute(
        "SELECT * FROM trades WHERE id = ?",
        (ids["trade_id"],)).fetchone() == trade_before


@pytest.mark.parametrize("bad_reason", ["", "   ", None])
def test_the_replay_ignores_the_reason_entirely(conn, bad_reason) -> None:
    """SELECT-first idempotency must precede PAYLOAD validation -- CLAUDE.md
    verbatim. The happy-path test above uses a valid reason and therefore
    CANNOT catch this ordering; this one can."""
    ids = build_cadl_case(conn)
    first = _apply(conn, ids)
    replay = _apply(conn, ids, reason=bad_reason)
    assert replay.already_applied is True
    assert replay.correction_id == first.correction_id


def test_a_FRESH_request_with_no_reason_is_refused(conn) -> None:
    ids = build_cadl_case(conn)
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _apply(conn, ids, reason=None)
    assert "--reason must be a non-empty string" in str(exc.value)
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 0


def test_a_DIFFERENT_citation_on_a_corrected_trade_is_refused(conn) -> None:
    ids = build_cadl_case(conn)
    first = _apply(conn, ids)
    # Any OTHER valid pair; the refusal fires at the idempotency rung, above
    # every anchor check, so the second pair's own eligibility is irrelevant.
    other = build_cadl_case(conn, ticker="OTHR")
    trade_before = conn.execute(
        "SELECT * FROM trades WHERE id = ?", (ids["trade_id"],)).fetchone()
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _apply(conn, ids, candidate_id=other["candidate_id"],
               recommendation_id=other["daily_recommendation_id"])
    msg = str(exc.value)
    assert str(first.correction_id) in msg
    assert "records provenance ONCE" in msg
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 1
    assert conn.execute(
        "SELECT * FROM trades WHERE id = ?",
        (ids["trade_id"],)).fetchone() == trade_before


def test_preview_on_an_applied_trade_reports_the_RECORDED_values(conn) -> None:
    ids = build_cadl_case(conn)
    applied = _apply(conn, ids)
    p = preview_cohort_provenance_correction(
        conn, trade_id=ids["trade_id"],
        cited_candidate_id=ids["candidate_id"],
        cited_recommendation_id=ids["daily_recommendation_id"], reason=None)
    assert p.already_applied_correction_id == applied.correction_id
    assert p.post_values["trades.hypothesis_label"] == CADL_LABEL


# -------------------------------------------------------- transaction contract


def test_a_caller_held_transaction_is_REJECTED_not_auto_detected(conn) -> None:
    ids = build_cadl_case(conn)
    conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    with pytest.raises(CallerHeldTransactionError):
        correct_cohort_provenance(
            conn, trade_id=ids["trade_id"],
            cited_candidate_id=ids["candidate_id"],
            cited_recommendation_id=ids["daily_recommendation_id"],
            reason=REASON)
    conn.rollback()


def test_a_failure_mid_sequence_leaves_no_partial_write(conn, monkeypatch):
    """Forced by patching the audit INSERT to raise, then asserting the trade
    row is unchanged after rollback -- so the UPDATE cannot commit alone."""
    ids = build_cadl_case(conn)
    conn.commit()
    before = _cohort_row(conn, ids["trade_id"])

    import swing.data.repos.provenance_corrections as repo

    def boom(*_a, **_k):
        raise RuntimeError("audit insert exploded")

    monkeypatch.setattr(repo, "insert_provenance_correction", boom)
    with pytest.raises(RuntimeError):
        _apply(conn, ids)
    assert _cohort_row(conn, ids["trade_id"]) == before
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 0


# ------------------------------------------------------------------- drift


def test_a_clean_correction_reports_NO_drift(conn) -> None:
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    assert report.drift_lines == ()
    assert report.has_drift is False


@pytest.mark.parametrize("column,new_value", [
    ("evaluation_run_id", None),          # filled below from a real run
    ("data_asof_date", "2026-08-09"),
    ("action_text", "Buy-stop $99.99"),
    ("entry_target", 12.34),
    ("stop_target", 8.00),
    ("shares", 7),
    ("risk_dollars", 99.9),
    ("risk_pct", 1.5),
    ("rationale", "rewritten"),
])
def test_drift_is_reported_per_mutable_column(conn, column, new_value) -> None:
    """PARAMETERIZED over the whole `DO UPDATE SET` list from
    `repos/recommendations.py` -- i.e. exactly what a same-session pipeline
    re-run can rewrite underneath the citation. `action_text`,
    `risk_dollars` and `risk_pct` are ORDINARY members here, which is the
    point: the snapshot column set is PRAGMA-derived, so an omission is not
    expressible."""
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    if column == "evaluation_run_id":
        other = build_cadl_case(conn, ticker="OTH")
        new_value = other["evaluation_run_id"]
    conn.execute(
        f"UPDATE daily_recommendations SET {column} = ? WHERE id = ?",
        (new_value, ids["daily_recommendation_id"]))
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    assert any(
        line.startswith(f"{CITATION_DRIFT}: daily_recommendations.{column} ")
        for line in report.drift_lines
    ), report.drift_lines


def test_a_frozen_column_absent_from_the_live_row_is_SCHEMA_drift() -> None:
    """Exercised on the comparison FUNCTION rather than by mutating an audit
    row: the table is APPEND-ONLY now, and routing around that to set up a
    test would be defeating the guard rather than testing the behaviour."""
    from swing.trades.cohort_provenance_correction import _snapshot_drift

    lines = _snapshot_drift(
        "daily_recommendations",
        {"id": 1, "gone_column": 7},
        {"id": 1, "new_column": 9},
    )
    joined = "\n".join(lines)
    assert f"{CITATION_SCHEMA_DRIFT}: daily_recommendations.gone_column" in joined
    assert f"{CITATION_SCHEMA_DRIFT}: daily_recommendations.new_column" in joined


def test_pipeline_snapshot_drift_is_reported_too(conn) -> None:
    """The R3 upper-bound citation is a green-suite decoration without this."""
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    conn.execute(
        "UPDATE pipeline_runs SET finished_ts = '2026-08-10T18:00:00' "
        "WHERE id = ?", (ids["pipeline_run_id"],))
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    # The label now says what it CHECKS -- persistence-bound evidence, not the
    # whole 23-column row (Codex R5 Minor 6).
    assert any(
        line.startswith(
            f"{CITATION_DRIFT}: pipeline_runs[persistence-bound evidence]"
            ".finished_ts ")
        for line in report.drift_lines
    ), report.drift_lines


def test_a_second_pipeline_row_makes_the_bound_unresolvable(conn) -> None:
    from tests.trades._cohort_provenance_fixtures import seed_pipeline_run

    ids = build_cadl_case(conn)
    _apply(conn, ids)
    seed_pipeline_run(
        conn, evaluation_run_id=ids["evaluation_run_id"],
        data_asof_date="2026-08-10", action_session_date=CADL_ACTION_SESSION)
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    assert any("no longer exists" in line for line in report.drift_lines)


# -------------------------------------------------------- the fill anchor


def test_the_anchor_is_RECOMPUTED_through_the_production_writer(conn) -> None:
    """Moved through the REAL `swing.data.repos.fills.update_fill_datetime`; a
    hand-written UPDATE would not prove the production path reaches this."""
    from swing.data.repos.fills import update_fill_datetime

    ids = build_cadl_case(conn)
    _apply(conn, ids)
    update_fill_datetime(
        conn, fill_id=ids["fill_id"], fill_datetime="2026-08-13T16:00:00")
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    assert any(
        line.startswith(f"{CITATION_ANCHOR_DRIFT}: entry_fill.fill_datetime")
        for line in report.drift_lines
    ), report.drift_lines


def test_a_move_that_hands_authority_to_ANOTHER_fill_names_it(conn) -> None:
    from swing.data.repos.fills import update_fill_datetime

    ids = build_cadl_case(conn)
    other = seed_fill(
        conn, trade_id=ids["trade_id"], fill_datetime="2026-08-12T17:00:00",
        quantity=1.0)
    _apply(conn, ids)
    update_fill_datetime(
        conn, fill_id=ids["fill_id"], fill_datetime="2026-08-14T16:00:00")
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    joined = "\n".join(report.drift_lines)
    assert CITATION_ANCHOR_DRIFT in joined
    assert f"fill {other}" in joined


def test_a_move_that_breaks_contemporaneity_reports_INVALIDATED(conn) -> None:
    from swing.data.repos.fills import update_fill_datetime

    ids = build_cadl_case(conn)
    _apply(conn, ids)
    # 2026-08-10 precedes the cited 2026-08-11 anchors.
    update_fill_datetime(
        conn, fill_id=ids["fill_id"], fill_datetime="2026-08-10T16:00:00")
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    joined = "\n".join(report.drift_lines)
    assert CITATION_INVALIDATED in joined
    assert "no longer satisfies contemporaneity" in joined


def test_a_malformed_fill_makes_the_anchor_UNVERIFIABLE_not_clean(conn) -> None:
    """A reader must not manufacture a clean answer out of data its own
    validator rejected. Planted by RAW INSERT, because `update_fill_datetime`
    is barriered against exactly this shape."""
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price) "
        "VALUES (?, '20260811T160000', 'entry', 1, 1.0)", (ids["trade_id"],))
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    joined = "\n".join(report.drift_lines)
    assert CITATION_ANCHOR_UNVERIFIABLE in joined
    assert CITATION_ANCHOR_DRIFT not in joined


def test_the_reader_uses_the_LOCAL_resolver_not_the_lexical_repo_helper(
    conn,
) -> None:
    """The residual the round-9 fix left: a reader calling
    `get_authoritative_entry_fill` would compute its verdict through the very
    lexical ordering this module forbids, HIDE the malformed earlier fill, and
    report NO drift -- on a path no authorization test exercises."""
    from swing.data.repos.fills import get_authoritative_entry_fill

    ids = build_cadl_case(conn)
    _apply(conn, ids)
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price) "
        "VALUES (?, '20260811T160000', 'entry', 1, 1.0)", (ids["trade_id"],))
    lexical = get_authoritative_entry_fill(conn, ids["trade_id"])
    assert lexical.fill_id == ids["fill_id"]  # the lexical helper says CLEAN
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    assert report.has_drift  # the local resolver says UNVERIFIABLE


# --------------------------------- the rowid-reuse discriminator + composition


def test_a_date_preserving_split_of_the_MAX_fill_still_reports_drift(
    conn,
) -> None:
    """THE ROWID-REUSE DISCRIMINATOR. `fills.fill_id` is INTEGER PRIMARY KEY
    WITHOUT AUTOINCREMENT -- a bare rowid -- so SQLite REUSES the number when
    the deleted row held the maximum, and the production split handler deletes
    the consolidated fill and reinserts partials with no explicit id.

    Verified inside this test: the reinserted partial comes back wearing the
    SAME fill_id with the SAME fill_datetime. An implementation comparing only
    `(fill_id, date)` sees a perfect match and reports NO DRIFT on a row that
    was DELETED AND REPLACED -- a false clean in the audit command. The
    `entry_fill_id IS NULL` check is what survives it, because an INSERT
    reusing the number does NOT restore an FK."""
    ids = build_cadl_case(conn)
    assert conn.execute("SELECT MAX(fill_id) FROM fills").fetchone()[0] == (
        ids["fill_id"])
    _apply(conn, ids)

    # The production shape: DELETE the consolidated fill, reinsert partials on
    # the SAME datetime with no explicit id.
    conn.execute("DELETE FROM fills WHERE fill_id = ?", (ids["fill_id"],))
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price) "
        "VALUES (?, ?, 'entry', 10, 10.81)",
        (ids["trade_id"], CADL_FILL_DATETIME))
    reused = conn.execute("SELECT MAX(fill_id) FROM fills").fetchone()[0]
    assert reused == ids["fill_id"], "SQLite did not reuse the rowid"

    row = get_correction_for_trade(conn, ids["trade_id"])
    # THE NUMBER is durable; the ROW is not. An INSERT does not restore the FK.
    assert row.entry_fill_id is None
    assert row.entry_fill_id_at_correction == ids["fill_id"]
    assert json.loads(row.entry_fill_snapshot_json)["fill_id"] == ids["fill_id"]

    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    joined = "\n".join(report.drift_lines)
    assert CITATION_ANCHOR_DRIFT in joined
    assert "DELETED" in joined


def test_the_control_a_non_max_fill_split_reports_drift_ordinarily(conn) -> None:
    """The paired control: when the cited fill is NOT the max, no reuse occurs
    and drift is reported for the ordinary reason."""
    ids = build_cadl_case(conn)
    seed_fill(
        conn, trade_id=ids["trade_id"], fill_datetime="2026-08-20T16:00:00",
        action="exit", quantity=19.0, reason="stop")
    assert conn.execute("SELECT MAX(fill_id) FROM fills").fetchone()[0] != (
        ids["fill_id"])
    _apply(conn, ids)
    conn.execute("DELETE FROM fills WHERE fill_id = ?", (ids["fill_id"],))
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price) "
        "VALUES (?, ?, 'entry', 10, 10.81)",
        (ids["trade_id"], CADL_FILL_DATETIME))
    new_id = conn.execute("SELECT MAX(fill_id) FROM fills").fetchone()[0]
    assert new_id != ids["fill_id"]
    row = get_correction_for_trade(conn, ids["trade_id"])
    assert row.entry_fill_id is None
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    assert CITATION_ANCHOR_DRIFT in "\n".join(report.drift_lines)


def test_COMPOSITION_the_real_split_handler_still_SUCCEEDS(conn) -> None:
    """The test that fails an ON DELETE RESTRICT design, run through the REAL
    `split_into_partials` handler. Cohort bookkeeping must never VETO a
    money-bearing reconciliation -- that is the priority inversion the FK
    choice exists to avoid -- and this is a COMPOSITION test, the class the
    review ladder structurally does not cover."""
    from swing.trades.reconciliation_auto_correct import apply_tier2_resolution

    ids = build_cadl_case(conn)
    _apply(conn, ids)

    run_id = conn.execute(
        "INSERT INTO reconciliation_runs (source, started_ts, state, "
        "period_start, period_end) VALUES ('schwab_api', "
        "'2026-08-13T12:00:00', 'running', '2026-08-12', '2026-08-12')",
    ).lastrowid
    disc_id = conn.execute(
        """
        INSERT INTO reconciliation_discrepancies (
            run_id, discrepancy_type, trade_id, fill_id, ticker, field_name,
            expected_value_json, actual_value_json, delta_text,
            material_to_review, resolution, ambiguity_kind, resolution_reason,
            created_at
        ) VALUES (?, 'entry_price_mismatch', ?, ?, 'CADL', 'price', ?, ?,
                  '+$0.00', 1, 'pending_ambiguity_resolution',
                  'multi_partial_vs_consolidated',
                  'Schwab returned 2 partial orders summing to journal qty',
                  '2026-08-13T12:00:00')
        """,
        (run_id, ids["trade_id"], ids["fill_id"],
         json.dumps({"price": 10.81}),
         json.dumps({"_multi_match": True, "count": 2})),
    ).lastrowid
    conn.commit()

    # DATE-PRESERVING: both partials land on the SAME session the trade's
    # entry_date already names, so the operation is coherent and the
    # entry-date coupling guard permits it.
    payload = [
        {"qty": 10, "price": 10.81, "fill_datetime": CADL_FILL_DATETIME},
        {"qty": 9, "price": 10.81, "fill_datetime": CADL_FILL_DATETIME},
    ]
    # NO FK IntegrityError: the correction's pointer is ON DELETE SET NULL.
    apply_tier2_resolution(
        conn,
        discrepancy_id=int(disc_id),
        choice_code="split_into_partials",
        operator_custom_payload=payload,
        operator_reason="Schwab shows two partial executions",
    )

    row = get_correction_for_trade(conn, ids["trade_id"])
    assert row.entry_fill_id is None
    assert row.entry_fill_id_at_correction == ids["fill_id"]
    assert json.loads(row.entry_fill_snapshot_json)["fill_id"] == ids["fill_id"]
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    joined = "\n".join(report.drift_lines)
    assert CITATION_ANCHOR_DRIFT in joined
    assert str(ids["fill_id"]) in joined


def test_reading_across_trades_returns_one_report_each(conn) -> None:
    a = build_cadl_case(conn)
    b = build_cadl_case(conn, ticker="VSTS", non_pass={})
    _apply(conn, a)
    _apply(conn, b)
    assert len(read_provenance_corrections(conn)) == 2
    assert len(list_provenance_corrections(conn)) == 2
    assert len(read_provenance_corrections(conn, trade_id=b["trade_id"])) == 1


# =========================================================================
# Codex R1 Major 4 -- the cited STATUS-HISTORY row is re-read.
# =========================================================================


def test_R1M4_an_in_place_status_closure_is_reported_as_drift(conn) -> None:
    """`update_close_open_interval` rewrites `effective_to` IN PLACE on EVERY
    supported status transition, and the FK pins only WHICH row was cited. So
    the row the whole correction's authority rests on is mutable through a
    SHIPPED service -- and with nothing frozen to compare, the reader printed
    'no citation drift' after a real, supported mutation.

    Driven through the REAL repo writer, not a hand-written UPDATE."""
    from swing.data.repos.hypothesis_status_history import (
        update_close_open_interval,
    )

    ids = build_cadl_case(conn)
    _apply(conn, ids)
    [clean] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    assert clean.drift_lines == ()

    # A LATER closure: legitimate evolution, coverage claim still true.
    update_close_open_interval(
        conn, hypothesis_id=1, effective_to="2026-12-01T00:00:00.000")
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    joined = "\n".join(report.drift_lines)
    assert "CITATION DRIFT: hypothesis_status_history.effective_to" in joined
    assert CITATION_INVALIDATED not in joined


def test_R1M4_a_closure_INSIDE_the_window_escalates_to_INVALIDATED(
    conn,
) -> None:
    """The two questions are different: has the row MOVED (drift, always
    reported) and does it still COVER the frozen window (invalidation)."""
    from swing.data.repos.hypothesis_status_history import (
        update_close_open_interval,
    )

    ids = build_cadl_case(conn)
    _apply(conn, ids)
    # Inside [2026-08-11T03:30:26, 2026-08-11T03:44:45] UTC.
    update_close_open_interval(
        conn, hypothesis_id=1, effective_to="2026-08-11T03:35:00.000")
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    joined = "\n".join(report.drift_lines)
    assert "CITATION DRIFT: hypothesis_status_history.effective_to" in joined
    assert CITATION_INVALIDATED in joined
    assert "no longer covers it" in joined


def test_R1M4_the_cited_status_row_CANNOT_be_deleted(conn) -> None:
    """Deletion is SCHEMA-PREVENTED, so the reader's missing-row branch is a
    general degrade path rather than a reachable case. The constraint is
    CITED rather than assumed: `cited_hypothesis_status_history_id INTEGER NOT
    NULL REFERENCES hypothesis_status_history(history_id) ON DELETE RESTRICT`
    in `0036_provenance_corrections.sql`, read back here off the LIVE PRAGMA."""
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    fks = {
        r[3]: (r[2], r[6]) for r in conn.execute(
            "PRAGMA foreign_key_list(provenance_corrections)").fetchall()
    }
    assert fks["cited_hypothesis_status_history_id"] == (
        "hypothesis_status_history", "RESTRICT")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "DELETE FROM hypothesis_status_history WHERE history_id = ?", (1,))


def test_R1M4_the_interval_bounds_are_FROZEN_on_the_audit_row(conn) -> None:
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    row = get_correction_for_trade(conn, ids["trade_id"])
    assert row.cited_hypothesis_status_effective_from == (
        "2026-04-25T00:00:00.000")
    assert row.cited_hypothesis_status_effective_to is None  # still open
    live_from, live_to = conn.execute(
        "SELECT effective_from, effective_to FROM hypothesis_status_history "
        "WHERE history_id = ?",
        (row.cited_hypothesis_status_history_id,)).fetchone()
    assert row.cited_hypothesis_status_effective_from == live_from
    assert row.cited_hypothesis_status_effective_to == live_to


def test_R1M3_the_written_envelopes_carry_all_three_keys(conn) -> None:
    """The audit row must DESCRIBE its own correction: exactly the three
    corrected fields, an applied envelope naming the CITED candidate, and a
    pre envelope recording the UNSET state that was this write's
    precondition."""
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    row = get_correction_for_trade(conn, ids["trade_id"])
    assert json.loads(row.corrected_fields_json) == [
        "trades.hypothesis_label", "trades.candidate_id",
        "trades.trade_origin",
    ]
    applied = json.loads(row.applied_value_json)
    assert set(applied) == {
        "trades.hypothesis_label", "trades.candidate_id",
        "trades.trade_origin"}
    assert applied["trades.candidate_id"] == row.cited_candidate_id
    pre = json.loads(row.pre_value_json)
    assert pre == {
        "trades.hypothesis_label": None,
        "trades.candidate_id": None,
        "trades.trade_origin": "manual_off_pipeline",
    }


# =========================================================================
# Codex R2 -- the audit clocks, the margin, the preview, the wider drift.
# =========================================================================


def _kwargs_from(row):
    kw = {f: getattr(row, f) for f in row.__dataclass_fields__}
    kw["provenance_correction_id"] = None
    return kw


def _repointed_at(row, other):
    """The same well-formed row, re-pointed at an UNCORRECTED trade.

    The audit table is APPEND-ONLY (triggers), so a rejection test cannot
    simply DELETE the row it just wrote and re-insert a mutated one -- which
    is the append-only guard working, not an obstacle to route around.
    """
    kw = _kwargs_from(row)
    kw["trade_id"] = other["trade_id"]
    kw["entry_fill_id"] = other["fill_id"]
    kw["entry_fill_id_at_correction"] = other["fill_id"]
    kw["entry_fill_snapshot_json"] = json.dumps({
        "fill_id": other["fill_id"], "trade_id": other["trade_id"],
        "action": "entry", "fill_datetime": CADL_FILL_DATETIME,
    }, sort_keys=True)
    return kw


def _raw_insert_or_raise(conn, row, kw):
    names = [f for f in row.__dataclass_fields__
             if f != "provenance_correction_id"]
    conn.execute(
        f"INSERT INTO provenance_corrections ({', '.join(names)}) "
        f"VALUES ({', '.join('?' * len(names))})",
        [kw[n] for n in names])


@pytest.mark.parametrize("column", [
    "cited_run_ts_raw", "cited_pipeline_finished_ts_raw", "cited_run_ts_utc",
    "cited_status_window_upper_utc", "cited_hypothesis_status_recorded_at",
    "cited_hypothesis_status_effective_from", "applied_at",
])
def test_R2M2_every_audit_clock_has_a_GRAMMAR_not_just_an_ordering(
    conn, column,
) -> None:
    """Every 0036 ordering CHECK is LEXICAL and the model mirrored it with
    string comparisons -- so a row carrying aaa / bbb / ccc / zzz as its four
    clock columns satisfied EVERY ordering rule and inserted cleanly. An audit
    row whose window is not a window."""
    from swing.data.models import ProvenanceCorrection

    ids = build_cadl_case(conn)
    other = build_cadl_case(conn, ticker="OTHR")
    _apply(conn, ids)
    row = get_correction_for_trade(conn, ids["trade_id"])
    kw = _repointed_at(row, other)
    kw[column] = "aaa"
    with pytest.raises(ValueError):
        ProvenanceCorrection(**kw)
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert_or_raise(conn, row, kw)


def test_R2M2_an_ordered_but_MEANINGLESS_clock_quartet_is_refused(
    conn,
) -> None:
    """aaa <= bbb and ccc <= zzz both hold lexically, which is exactly how the
    pre-fix row passed."""
    assert "aaa" <= "bbb" and "ccc" <= "zzz"
    from swing.data.models import ProvenanceCorrection

    ids = build_cadl_case(conn)
    _apply(conn, ids)
    row = get_correction_for_trade(conn, ids["trade_id"])
    kw = _kwargs_from(row)
    kw.update(
        cited_run_ts_raw="aaa", cited_pipeline_finished_ts_raw="bbb",
        cited_run_ts_utc="ccc", cited_status_window_upper_utc="zzz")
    with pytest.raises(ValueError):
        ProvenanceCorrection(**kw)


def test_R2M2_an_empty_applied_label_is_refused_at_BOTH_layers(conn) -> None:
    """json_type = text accepts the empty string, which the model REJECTS --
    so a schema-valid row existed that the supported reader CRASHED on while
    hydrating. The two layers now accept the same set."""
    from swing.data.models import ProvenanceCorrection

    ids = build_cadl_case(conn)
    other = build_cadl_case(conn, ticker="OTHR")
    _apply(conn, ids)
    row = get_correction_for_trade(conn, ids["trade_id"])
    env = json.loads(row.applied_value_json)
    env["trades.hypothesis_label"] = ""
    kw = _repointed_at(row, other)
    kw["applied_value_json"] = json.dumps(env, sort_keys=True)
    with pytest.raises(ValueError):
        ProvenanceCorrection(**kw)
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert_or_raise(conn, row, kw)


def test_R3M1_applied_at_cannot_be_supplied_by_a_caller(conn) -> None:
    """A caller could previously pass applied_at='1900-01-01T00:00:00' and the
    audit row would durably record that the correction happened then --
    reachable through a direct service call, and grammar validation
    established only that the value LOOKED like a timestamp, never that this
    surface OBSERVED it. In a table whose purpose is to hold true claims, the
    one field nobody may supply is when it happened."""
    import inspect

    ids = build_cadl_case(conn)
    conn.commit()
    assert "applied_at" not in inspect.signature(
        correct_cohort_provenance).parameters
    with pytest.raises(TypeError):
        correct_cohort_provenance(
            conn, trade_id=ids["trade_id"],
            cited_candidate_id=ids["candidate_id"],
            cited_recommendation_id=ids["daily_recommendation_id"],
            reason=REASON, applied_at="1900-01-01T00:00:00")
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 0


def test_R3M1_the_clock_is_stamped_inside_and_is_patchable_for_tests(
    conn, monkeypatch,
) -> None:
    """The determinism seam is a MODULE attribute, not a parameter, precisely
    so it is not part of the public surface."""
    import swing.trades.cohort_provenance_correction as svc

    ids = build_cadl_case(conn)
    monkeypatch.setattr(
        svc, "_APPLIED_AT_CLOCK", lambda: "2026-08-13T00:00:00.000")
    _apply(conn, ids)
    row = get_correction_for_trade(conn, ids["trade_id"])
    assert row.applied_at == "2026-08-13T00:00:00.000"


def test_R3M6_the_audit_row_cannot_be_UPDATED_or_DELETED(conn) -> None:
    """`ux_provenance_corrections_trade` only stops a SECOND row existing. It
    does nothing about REWRITING the citation, or DELETING it and reopening
    the trade for a different one -- so "enforced by the schema rather than by
    prose" was true of the COUNT and false of the CONTENT."""
    ids = build_cadl_case(conn)
    result = _apply(conn, ids)
    with pytest.raises(sqlite3.IntegrityError, match="APPEND-ONLY"):
        conn.execute(
            "UPDATE provenance_corrections SET cited_candidate_id = 999 "
            "WHERE provenance_correction_id = ?", (result.correction_id,))
    with pytest.raises(sqlite3.IntegrityError, match="APPEND-ONLY"):
        conn.execute(
            "UPDATE provenance_corrections SET correction_reason = 'rewritten' "
            "WHERE provenance_correction_id = ?", (result.correction_id,))
    with pytest.raises(sqlite3.IntegrityError, match="APPEND-ONLY"):
        conn.execute(
            "DELETE FROM provenance_corrections "
            "WHERE provenance_correction_id = ?", (result.correction_id,))
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 1


def test_R3M6_the_FK_driven_nulling_is_STILL_permitted(conn) -> None:
    """The trigger cannot simply reject everything: `entry_fill_id` is
    deliberately ON DELETE SET NULL so cohort bookkeeping never vetoes the
    money-bearing split handler, and SQLite implements that as an UPDATE. The
    composition test elsewhere in this file exercises the real split path;
    this one pins the transition directly."""
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    conn.execute("DELETE FROM fills WHERE fill_id = ?", (ids["fill_id"],))
    row = get_correction_for_trade(conn, ids["trade_id"])
    assert row.entry_fill_id is None
    assert row.entry_fill_id_at_correction == ids["fill_id"]


def test_R3M4_a_malformed_live_interval_bound_is_UNVERIFIABLE(conn) -> None:
    """The coverage test is a string comparison over an unconstrained TEXT
    column, so closing the interval with a basic-form `20260811T033500`
    produced an ordinary drift line and NO invalidation -- the malformed value
    sorts AFTER the bound. A reader must not manufacture a coverage verdict
    out of data it cannot parse."""
    assert "20260811T033500" > "2026-08-11T03:44:45"
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    conn.execute(
        "UPDATE hypothesis_status_history SET effective_to = '20260811T033500' "
        "WHERE history_id = 1")
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    joined = "\n".join(report.drift_lines)
    assert CITATION_ANCHOR_UNVERIFIABLE in joined
    assert "effective_to" in joined


def test_R3M3_moving_the_cited_candidate_to_another_run_is_reported(
    conn,
) -> None:
    """The audit's candidate and evaluation-run FKs are INDEPENDENT, so moving
    the cited candidate to a different run left its label and bucket unchanged
    and the reader reported CLEAN -- while the correction's whole claim is
    that THIS candidate came from THAT run."""
    ids = build_cadl_case(conn)
    other = build_cadl_case(conn, ticker="OTHR")
    _apply(conn, ids)
    conn.execute(
        "UPDATE candidates SET evaluation_run_id = ? WHERE id = ?",
        (other["evaluation_run_id"], ids["candidate_id"]))
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    joined = "\n".join(report.drift_lines)
    assert "candidates.evaluation_run_id" in joined
    assert "no longer belongs to the cited run" in joined


def test_R3M3_a_reticketed_cited_candidate_is_reported(conn) -> None:
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    conn.execute(
        "UPDATE candidates SET ticker = 'ELSE' WHERE id = ?",
        (ids["candidate_id"],))
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    assert any("now ticker" in line for line in report.drift_lines)


def test_R3M2_an_equal_instant_at_finer_precision_does_not_cover(conn) -> None:
    """The grammar admits 0-6 fractional digits and the coverage comparison
    was LEXICAL: verified, '2026-08-11T03:44:45.0' > '2026-08-11T03:44:45' is
    True although they are the SAME INSTANT and the half-open interval does
    not cover the bound. Truncating to seconds removes the precision axis."""
    from swing.data.models import ProvenanceCorrection

    assert "2026-08-11T03:44:45.0" > "2026-08-11T03:44:45"
    ids = build_cadl_case(conn)
    other = build_cadl_case(conn, ticker="OTHR")
    _apply(conn, ids)
    row = get_correction_for_trade(conn, ids["trade_id"])
    kw = _repointed_at(row, other)
    kw["cited_hypothesis_status_effective_to"] = "2026-08-11T03:44:45.0"
    with pytest.raises(ValueError):
        ProvenanceCorrection(**kw)
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert_or_raise(conn, row, kw)


@pytest.mark.parametrize("bad", [
    "2026-02-30T00:00:00",   # SQLite NORMALISES this rather than NULLing it
    "2026-08-11T24:00:00",   # SQLite round-trips hour 24 happily
    "0000-01-01T00:00:00",   # ...and year zero
])
def test_R3M5_impossible_dates_are_refused_by_SQL_too(conn, bad) -> None:
    """`datetime(x) IS NOT NULL` was not enough: SQLite NORMALISES Feb 30
    rather than returning NULL, and ECHOES hour 24 and year zero -- all three
    of which Python's fromisoformat RAISES on. A raw row therefore INSERTed
    and then crashed the supported reader at hydration."""
    from swing.data.models import ProvenanceCorrection

    ids = build_cadl_case(conn)
    other = build_cadl_case(conn, ticker="OTHR")
    _apply(conn, ids)
    row = get_correction_for_trade(conn, ids["trade_id"])
    kw = _repointed_at(row, other)
    kw["applied_at"] = bad
    with pytest.raises(ValueError):
        ProvenanceCorrection(**kw)
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert_or_raise(conn, row, kw)


def test_R3m7_an_already_populated_trade_refuses_BEFORE_asking_for_a_reason(
    conn,
) -> None:
    """The unset-state verdict is TERMINAL and true whatever payload arrives,
    while "supply a reason" is an INSTRUCTION implying the rest is sound. With
    the reason first, the operator was sent away to justify an operation that
    can never be authorized."""
    ids = build_cadl_case(conn)
    conn.execute(
        "UPDATE trades SET trade_origin = 'pipeline_aplus' WHERE id = ?",
        (ids["trade_id"],))
    conn.commit()
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        correct_cohort_provenance(
            conn, trade_id=ids["trade_id"],
            cited_candidate_id=ids["candidate_id"],
            cited_recommendation_id=ids["daily_recommendation_id"],
            reason=None)
    msg = str(exc.value)
    assert "already carries cohort provenance" in msg
    assert "--reason" not in msg


def test_R2M3_a_recorded_at_inside_the_margin_REFUSES(conn) -> None:
    """The margin exists to protect a verdict a wrong-by-hours conversion
    could flip, and the retrospective guard DECIDES AUTHORIZATION by comparing
    recorded_at against the zone-converted lower bound -- so omitting
    recorded_at left the one comparison the margin was built for unprotected.
    Window lower bound 2026-08-11T03:30:26 UTC; recorded_at two hours before
    it is inside the band."""
    ids = build_cadl_case(conn)
    conn.execute(
        "UPDATE hypothesis_status_history SET recorded_at = "
        "'2026-08-11T01:30:26.000' WHERE hypothesis_id = 1")
    conn.commit()
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        preview_cohort_provenance_correction(
            conn, trade_id=ids["trade_id"],
            cited_candidate_id=ids["candidate_id"],
            cited_recommendation_id=ids["daily_recommendation_id"],
            reason=REASON)
    msg = str(exc.value)
    assert "recorded_at" in msg
    assert "within 24 hours of the" in msg


def test_R2M4_the_preview_leaves_no_transaction_open(conn) -> None:
    """It pins ONE read snapshot for the whole ladder and rolls back
    unconditionally, so it still writes nothing and takes no write lock."""
    ids = build_cadl_case(conn)
    conn.commit()
    assert not conn.in_transaction
    preview_cohort_provenance_correction(
        conn, trade_id=ids["trade_id"],
        cited_candidate_id=ids["candidate_id"],
        cited_recommendation_id=ids["daily_recommendation_id"],
        reason=REASON)
    assert not conn.in_transaction
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 0


def test_R2M5_a_bucket_change_on_the_cited_candidate_is_reported(conn) -> None:
    """No current UPDATE site is not immutability, and a migration or an
    operator repair is where an audit reader earns its keep. The label is
    RE-DERIVED rather than snapshot-compared, so ONE comparison catches a
    bucket change, a criterion change AND a registry rename."""
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    conn.execute(
        "UPDATE candidates SET bucket = 'watch' WHERE id = ?",
        (ids["candidate_id"],))
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    joined = "\n".join(report.drift_lines)
    assert "candidates.bucket" in joined
    assert "RE-DERIVED" in joined


def test_R2M5_a_criterion_change_moves_the_re_derived_label(conn) -> None:
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    conn.execute(
        "UPDATE candidate_criteria SET result = 'fail' "
        "WHERE candidate_id = ? AND criterion_name = 'tightness'",
        (ids["candidate_id"],))
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    joined = "\n".join(report.drift_lines)
    assert "RE-DERIVED" in joined
    assert "tightness" in joined


def test_R2M5_a_registry_rename_is_reported(conn) -> None:
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    conn.execute(
        "UPDATE hypothesis_registry SET name = 'A+ baseline v2' WHERE id = 1")
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    assert any("hypothesis_registry.name" in line
               for line in report.drift_lines)


def test_R2M5_a_moved_evaluation_run_anchor_is_reported(conn) -> None:
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    conn.execute(
        "UPDATE evaluation_runs SET action_session_date = '2026-08-10' "
        "WHERE id = ?", (ids["evaluation_run_id"],))
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    assert any("evaluation_runs.action_session_date" in line
               for line in report.drift_lines)


@pytest.mark.parametrize("column,value", [
    ("hypothesis_label", "a label nobody derived"),
    ("candidate_id", None),
    ("trade_origin", "manual_off_pipeline"),
])
def test_R2M5_the_TRADE_no_longer_carrying_the_applied_triple_is_reported(
    conn, column, value,
) -> None:
    """The audit row asserts three values were WRITTEN and nothing until now
    ever checked that the trade still carries them -- the most direct honesty
    check available."""
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    conn.execute(
        f"UPDATE trades SET {column} = ? WHERE id = ?",
        (value, ids["trade_id"]))
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    assert any(f"trades.{column} was written as" in line
               for line in report.drift_lines), report.drift_lines


# =========================================================================
# Codex R4 -- the 1900 floor, the pinned origin, the candidate freeze,
#            the widened derivation digest, and the tightened trigger.
# =========================================================================


def test_R4M1_a_pre_1900_history_stamp_REFUSES_in_preview_AND_apply(
    conn,
) -> None:
    """Every 0036 timestamp CHECK requires year >= 1900 and neither Python
    validator did -- so a schema-legal
    `hypothesis_status_history.recorded_at='1899-01-01T00:00:00.000'` passed
    parsing, the retrospective test and the margin, the PREVIEW said GO, and
    the apply then UPDATED THE TRADE and died at the audit INSERT with an
    untyped IntegrityError. Both entry points now refuse identically."""
    ids = build_cadl_case(conn)
    conn.execute(
        "UPDATE hypothesis_status_history SET recorded_at = "
        "'1899-01-01T00:00:00.000', effective_from = '1899-01-01T00:00:00.000' "
        "WHERE hypothesis_id = 1")
    conn.commit()
    with pytest.raises(CohortProvenanceCorrectionError) as preview_exc:
        preview_cohort_provenance_correction(
            conn, trade_id=ids["trade_id"],
            cited_candidate_id=ids["candidate_id"],
            cited_recommendation_id=ids["daily_recommendation_id"],
            reason=REASON)
    with pytest.raises(CohortProvenanceCorrectionError) as apply_exc:
        correct_cohort_provenance(
            conn, trade_id=ids["trade_id"],
            cited_candidate_id=ids["candidate_id"],
            cited_recommendation_id=ids["daily_recommendation_id"],
            reason=REASON)
    assert "before 1900" in str(preview_exc.value)
    assert str(preview_exc.value) == str(apply_exc.value)
    assert _cohort_row(conn, ids["trade_id"])[2] == "manual_off_pipeline"
    assert conn.execute(
        "SELECT COUNT(*) FROM provenance_corrections").fetchone()[0] == 0


def test_R4M2_an_impossible_aplus_watch_origin_row_is_refused(conn) -> None:
    """Binding only `candidate_id` let an audit row cite an A+ candidate with
    the correct label and `trade_origin='pipeline_watch_manual'` -- an
    impossible cohort assignment that passed BOTH layers."""
    from swing.data.models import ProvenanceCorrection

    ids = build_cadl_case(conn)
    other = build_cadl_case(conn, ticker="OTHR")
    _apply(conn, ids)
    row = get_correction_for_trade(conn, ids["trade_id"])
    env = json.loads(row.applied_value_json)
    env["trades.trade_origin"] = "pipeline_watch_manual"
    kw = _repointed_at(row, other)
    kw["applied_value_json"] = json.dumps(env, sort_keys=True)
    with pytest.raises(ValueError):
        ProvenanceCorrection(**kw)
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert_or_raise(conn, row, kw)


def test_R4M2_the_reader_RE_DERIVES_the_origin_too(conn) -> None:
    """The reader re-derived the LABEL and checked the bucket but never the
    ORIGIN, so a trade carrying a watch origin beside an A+ citation reported
    CLEAN."""
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    conn.execute(
        "UPDATE trades SET trade_origin = 'pipeline_watch_manual' "
        "WHERE id = ?", (ids["trade_id"],))
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    joined = "\n".join(report.drift_lines)
    assert "trades.trade_origin was written as" in joined


def test_R4M3_a_criteria_change_that_PRESERVES_the_label_is_still_reported(
    conn,
) -> None:
    """THE EQUIVALENCE CLASS THAT DEFEATS RE-DERIVATION.
    `_non_pass_criterion_names` observes only the SET OF NAMES whose result is
    not `pass`, so flipping the live CADL case's `TT8_rs_rank` from `na` to
    `fail` leaves that set -- and therefore the LABEL -- UNCHANGED, while the
    correction's stored reason specifically records the `na` evidence. The
    earlier test flipped `tightness` from pass to fail, which MOVES the label,
    so it could not cover this class at all."""
    from swing.recommendations.hypothesis import _descriptive_label
    from swing.data.repos.candidates import fetch_candidate_by_id

    ids = build_cadl_case(conn)
    _apply(conn, ids)
    before = _descriptive_label(
        fetch_candidate_by_id(conn, ids["candidate_id"]).candidate,
        "A+ baseline")
    conn.execute(
        "UPDATE candidate_criteria SET result = 'fail' "
        "WHERE candidate_id = ? AND criterion_name = 'TT8_rs_rank'",
        (ids["candidate_id"],))
    after = _descriptive_label(
        fetch_candidate_by_id(conn, ids["candidate_id"]).candidate,
        "A+ baseline")
    assert before == after, "the fixture must leave the label UNCHANGED"
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    joined = "\n".join(report.drift_lines)
    assert "candidates.criteria" in joined
    assert "RE-DERIVED" not in joined  # the label really did not move


def test_R4M3_a_criterion_value_change_is_reported(conn) -> None:
    """`value`, `rule` and `layer` are invisible to re-derivation too."""
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    conn.execute(
        "UPDATE candidate_criteria SET value = 'universe, rank 12' "
        "WHERE candidate_id = ? AND criterion_name = 'TT8_rs_rank'",
        (ids["candidate_id"],))
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    assert any("candidates.criteria" in line for line in report.drift_lines)


def test_R4M3_deleting_a_PASSING_criterion_is_reported(conn) -> None:
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    conn.execute(
        "DELETE FROM candidate_criteria WHERE candidate_id = ? "
        "AND criterion_name = 'ma_short_rising'", (ids["candidate_id"],))
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    assert any("candidates.criteria" in line for line in report.drift_lines)


def test_R4m5_an_empty_hypothesis_name_is_refused_by_SQL_too(conn) -> None:
    """`__post_init__` already rejected it, so without the SQL CHECK a RAW row
    inserted cleanly and then made `list_provenance_corrections` RAISE during
    hydration -- aborting the whole supported report rather than surfacing one
    bad row."""
    from swing.data.models import ProvenanceCorrection

    ids = build_cadl_case(conn)
    other = build_cadl_case(conn, ticker="OTHR")
    _apply(conn, ids)
    row = get_correction_for_trade(conn, ids["trade_id"])
    kw = _repointed_at(row, other)
    kw["cited_hypothesis_name_at_correction"] = "   "
    with pytest.raises(ValueError):
        ProvenanceCorrection(**kw)
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert_or_raise(conn, row, kw)


def test_R4m6_the_pointer_cannot_be_nulled_while_the_parent_still_EXISTS(
    conn,
) -> None:
    """The trigger recognised only the VALUE TRANSITION, so a direct
    `UPDATE ... SET entry_fill_id = NULL` succeeded while the fill still
    existed -- after which the reader falsely reported that the fill had been
    DELETED. The exception now says what it actually is."""
    ids = build_cadl_case(conn)
    result = _apply(conn, ids)
    assert conn.execute(
        "SELECT COUNT(*) FROM fills WHERE fill_id = ?",
        (ids["fill_id"],)).fetchone()[0] == 1
    with pytest.raises(sqlite3.IntegrityError, match="APPEND-ONLY"):
        conn.execute(
            "UPDATE provenance_corrections SET entry_fill_id = NULL "
            "WHERE provenance_correction_id = ?", (result.correction_id,))
    # ...and it IS permitted once the parent is genuinely gone.
    conn.execute("DELETE FROM fills WHERE fill_id = ?", (ids["fill_id"],))
    assert get_correction_for_trade(conn, ids["trade_id"]).entry_fill_id is None


# =========================================================================
# Codex R5 -- the reader snapshot, the citation graph, the clock binding,
#            and the recommendation column manifest.
# =========================================================================


def test_R5M3_the_reader_reports_from_ONE_snapshot(conn, tmp_path) -> None:
    """THE TWIN OF A DEFECT ALREADY FIXED ONE FUNCTION AWAY. The reader runs
    many independent SELECTs, so a production write committing MID-REPORT left
    it comparing half its checks against one world and half against another,
    and then printing a verdict that is a picture of no moment that ever
    existed.

    Driven with a SECOND CONNECTION that commits a real status-history
    transition part-way through the report, from inside `_snapshot_drift` --
    the first comparison the reader makes.

    THE ASSERTION UNDER BOTH PATHS: with the read snapshot the report is the
    consistent PRE-image and carries NO status drift; without it the reader
    sees the post-mutation status row and emits an `effective_to` drift line
    beside recommendation checks taken from the pre-image. The two differ, so
    this test distinguishes."""
    import swing.trades.cohort_provenance_correction as svc

    db = tmp_path / "swing.db"
    conn.close()
    from swing.data.db import ensure_schema, open_connection

    live = ensure_schema(db)
    ids = build_cadl_case(live)
    live.commit()
    correct_cohort_provenance(
        live, trade_id=ids["trade_id"],
        cited_candidate_id=ids["candidate_id"],
        cited_recommendation_id=ids["daily_recommendation_id"],
        reason=REASON)

    other = open_connection(db)
    fired = {"n": 0}
    real = svc._snapshot_drift

    def _mutating(label, frozen, live_values):
        if fired["n"] == 0:
            fired["n"] = 1
            # A REAL, supported transition committed from another connection.
            other.execute(
                "UPDATE hypothesis_status_history SET effective_to = "
                "'2026-12-01T00:00:00.000' WHERE history_id = 1")
            other.commit()
        return real(label, frozen, live_values)

    svc._snapshot_drift = _mutating
    try:
        [report] = svc.read_provenance_corrections(
            live, trade_id=ids["trade_id"])
    finally:
        svc._snapshot_drift = real
        other.close()

    assert fired["n"] == 1, "the mid-report mutation never fired"
    joined = "\n".join(report.drift_lines)
    assert "hypothesis_status_history.effective_to" not in joined, (
        "the report mixed a post-mutation status row with a pre-mutation "
        "recommendation image: " + joined)
    assert report.drift_lines == ()
    # ...and the NEXT report, on a fresh snapshot, DOES see it -- so the
    # mutation was real and the first report was stale-but-consistent rather
    # than blind.
    [after] = svc.read_provenance_corrections(live, trade_id=ids["trade_id"])
    assert any("hypothesis_status_history.effective_to" in line
               for line in after.drift_lines), after.drift_lines
    live.close()


def test_R5M3_the_reader_leaves_no_transaction_open(conn) -> None:
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    conn.commit()
    assert not conn.in_transaction
    read_provenance_corrections(conn, trade_id=ids["trade_id"])
    assert not conn.in_transaction


def test_R5M2_the_LIVE_CADL_citation_graph_is_ADMITTED(conn) -> None:
    """THE BINDING SAFETY CONDITION. The first production row this table will
    ever hold is the CADL correction, applied at an operator-witnessed gate. A
    trigger set that refuses it turns a witnessed gate into a failure in front
    of the operator.

    Every value below was read READ-ONLY off the live DB before this test was
    written (`file:...?mode=ro`), and the graph is asserted here in the same
    shape the trigger checks:
      candidate 12341 -> evaluation run 137 (run_ts 2026-08-10T17:30:26,
      action session 2026-08-11) ; daily_recommendations 172 (today_decision,
      CADL, 2026-08-11) ; pipeline run 151 (complete, finished
      2026-08-10T17:44:45) ; hypothesis 1 'A+ baseline' via status-history row
      1 ; trade 23 / entry fill 45 (2026-08-12T16:00:00).

    NOTE FOR THE RECORD: the citation graph runs through evaluation run
    **137**, not 138. Run 138 is the LATER run (action session 2026-08-12)
    that contains NO CADL row -- which is exactly what makes 12341 the
    framework's last word."""
    ids = build_cadl_case(conn)   # built on those same live shapes
    conn.commit()
    result = correct_cohort_provenance(
        conn, trade_id=ids["trade_id"],
        cited_candidate_id=ids["candidate_id"],
        cited_recommendation_id=ids["daily_recommendation_id"],
        reason=REASON)
    assert result.correction_id > 0
    row = get_correction_for_trade(conn, ids["trade_id"])
    assert row.cited_candidate_id == ids["candidate_id"]
    assert row.cited_evaluation_run_id == ids["evaluation_run_id"]
    assert row.cited_pipeline_run_id == ids["pipeline_run_id"]
    assert row.cited_hypothesis_id == 1
    assert row.cited_run_ts_raw == "2026-08-10T17:30:26"
    assert row.cited_pipeline_finished_ts_raw == "2026-08-10T17:44:45"
    assert row.cited_candidate_action_session_date == "2026-08-11"
    assert row.entry_fill_session_date == "2026-08-12"


@pytest.mark.parametrize("break_it", [
    "candidate_run", "recommendation_run", "pipeline_run", "status_hypothesis",
    "registry_name", "fill_trade", "run_anchor",
])
def test_R5M2_a_broken_citation_graph_is_REFUSED_by_the_trigger(
    conn, break_it,
) -> None:
    """The FKs prove each row EXISTS; they do not prove the rows form the
    contemporaneous PAIR the correction asserts. The arc ADVERTISES the
    citation as structural, so claim and code have to agree."""
    ids = build_cadl_case(conn)
    other = build_cadl_case(conn, ticker="OTHR")
    _apply(conn, ids)
    row = get_correction_for_trade(conn, ids["trade_id"])
    kw = _repointed_at(row, other)
    if break_it == "candidate_run":
        kw["cited_candidate_id"] = other["candidate_id"]
        env = json.loads(kw["applied_value_json"])
        env["trades.candidate_id"] = other["candidate_id"]
        kw["applied_value_json"] = json.dumps(env, sort_keys=True)
        snap = json.loads(kw["cited_candidate_snapshot_json"])
        snap["id"] = other["candidate_id"]
        kw["cited_candidate_snapshot_json"] = json.dumps(snap, sort_keys=True)
    elif break_it == "recommendation_run":
        kw["cited_daily_recommendation_id"] = other["daily_recommendation_id"]
        snap = dict(other["dr_snapshot"])
        kw["cited_recommendation_snapshot_json"] = json.dumps(
            snap, sort_keys=True)
        kw["cited_recommendation_action_session_date"] = str(
            snap["action_session_date"])
    elif break_it == "pipeline_run":
        kw["cited_pipeline_run_id"] = other["pipeline_run_id"]
        snap = json.loads(kw["cited_pipeline_run_snapshot_json"])
        snap["id"] = other["pipeline_run_id"]
        kw["cited_pipeline_run_snapshot_json"] = json.dumps(
            snap, sort_keys=True)
    elif break_it == "status_hypothesis":
        kw["cited_hypothesis_status_history_id"] = 2   # belongs to H2
    elif break_it == "registry_name":
        kw["cited_hypothesis_name_at_correction"] = "Not The Registry Name"
    elif break_it == "fill_trade":
        kw["entry_fill_id"] = None
        kw["entry_fill_id_at_correction"] = ids["fill_id"]   # another trade
        snap = json.loads(kw["entry_fill_snapshot_json"])
        snap["fill_id"] = ids["fill_id"]
        kw["entry_fill_snapshot_json"] = json.dumps(snap, sort_keys=True)
    elif break_it == "run_anchor":
        kw["cited_run_ts_raw"] = "2026-08-10T17:30:27"      # not the run's
        kw["cited_run_ts_utc"] = "2026-08-11T03:30:27"
    with pytest.raises(sqlite3.IntegrityError):
        _raw_insert_or_raise(conn, row, kw)


def test_R5M1_the_utc_pair_must_BE_the_conversion_of_the_raw_pair(
    conn,
) -> None:
    """Both layers validated ordering WITHIN each clock domain and never that
    the two domains describe the SAME INSTANTS -- so a row could shift both UTC
    values by hours, cite a different status window, satisfy every coverage and
    retrospective CHECK, and be reported CLEAN. Nine hours instead of ten,
    which is exactly the shape a wrong-zone assumption produces."""
    from swing.data.models import ProvenanceCorrection

    ids = build_cadl_case(conn)
    other = build_cadl_case(conn, ticker="OTHR")
    _apply(conn, ids)
    row = get_correction_for_trade(conn, ids["trade_id"])
    kw = _repointed_at(row, other)
    kw["cited_run_ts_utc"] = "2026-08-11T02:30:26"          # nine hours
    kw["cited_status_window_upper_utc"] = "2026-08-11T02:44:45"
    with pytest.raises(ValueError, match="SAME INSTANT"):
        ProvenanceCorrection(**kw)


def test_R5m5_a_partial_recommendation_snapshot_is_REFUSED(conn) -> None:
    """The snapshot is advertised as a WHOLE-ROW freeze and only three keys
    were enforced -- so a three-key object satisfied both layers while omitting
    exactly the columns `upsert_recommendation` can rewrite underneath the
    citation."""
    from swing.data.models import ProvenanceCorrection

    ids = build_cadl_case(conn)
    other = build_cadl_case(conn, ticker="OTHR")
    _apply(conn, ids)
    row = get_correction_for_trade(conn, ids["trade_id"])
    full = json.loads(row.cited_recommendation_snapshot_json)
    kw = _repointed_at(row, other)
    kw["cited_recommendation_snapshot_json"] = json.dumps({
        "id": full["id"], "evaluation_run_id": full["evaluation_run_id"],
        "action_session_date": full["action_session_date"],
    }, sort_keys=True)
    with pytest.raises(ValueError, match="EXACTLY the"):
        ProvenanceCorrection(**kw)


@pytest.mark.parametrize("dropped", [
    "data_asof_date", "ticker", "recommendation", "action_text",
    "entry_target", "stop_target", "shares", "risk_dollars", "risk_pct",
    "rationale",
])
def test_R5m5_dropping_ANY_live_column_is_refused(conn, dropped) -> None:
    """Parameterized over every live column the three ID checks do NOT name --
    the ones a three-key test could never have covered."""
    from swing.data.models import ProvenanceCorrection

    ids = build_cadl_case(conn)
    other = build_cadl_case(conn, ticker="OTHR")
    _apply(conn, ids)
    row = get_correction_for_trade(conn, ids["trade_id"])
    snap = json.loads(row.cited_recommendation_snapshot_json)
    snap.pop(dropped)
    kw = _repointed_at(row, other)
    kw["cited_recommendation_snapshot_json"] = json.dumps(snap, sort_keys=True)
    with pytest.raises(ValueError, match="EXACTLY the"):
        ProvenanceCorrection(**kw)


def test_R5m5_the_column_manifest_matches_the_LIVE_schema(conn) -> None:
    """#11: a checked-in manifest cannot read the live schema, so the drift
    test is what stops it rotting on the next ALTER TABLE."""
    from swing.data.models import DAILY_RECOMMENDATION_SNAPSHOT_COLUMNS

    live = {
        r[1] for r in conn.execute(
            "PRAGMA table_info(daily_recommendations)").fetchall()
    }
    assert set(DAILY_RECOMMENDATION_SNAPSHOT_COLUMNS) == live


def test_R5m6_a_churn_column_on_the_pipeline_row_is_NOT_drift(conn) -> None:
    """The CLAIM was narrowed, not the snapshot widened. `pipeline_runs` has 23
    columns and only the five persistence-bound ones are frozen -- deliberately,
    because `current_step` and the lease/progress columns churn legitimately
    and freezing them would manufacture constant false drift. The label now
    says what it checks."""
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    conn.execute(
        "UPDATE pipeline_runs SET current_step = 'export', "
        "lease_heartbeat_ts = '2026-08-10T17:44:00' WHERE id = ?",
        (ids["pipeline_run_id"],))
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    assert report.drift_lines == ()
