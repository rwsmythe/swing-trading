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


def test_a_frozen_column_absent_from_the_live_row_is_SCHEMA_drift(conn) -> None:
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    row = get_correction_for_trade(conn, ids["trade_id"])
    snap = json.loads(row.cited_recommendation_snapshot_json)
    snap["a_column_that_no_longer_exists"] = 1
    conn.execute(
        "UPDATE provenance_corrections SET "
        "cited_recommendation_snapshot_json = ? "
        "WHERE provenance_correction_id = ?",
        (json.dumps(snap, sort_keys=True), row.provenance_correction_id))
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    assert any(CITATION_SCHEMA_DRIFT in line for line in report.drift_lines)


def test_pipeline_snapshot_drift_is_reported_too(conn) -> None:
    """The R3 upper-bound citation is a green-suite decoration without this."""
    ids = build_cadl_case(conn)
    _apply(conn, ids)
    conn.execute(
        "UPDATE pipeline_runs SET finished_ts = '2026-08-10T18:00:00' "
        "WHERE id = ?", (ids["pipeline_run_id"],))
    [report] = read_provenance_corrections(conn, trade_id=ids["trade_id"])
    assert any(
        line.startswith(f"{CITATION_DRIFT}: pipeline_runs.finished_ts ")
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
