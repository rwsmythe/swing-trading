"""Task 4 -- THE ANCHOR DISCRIMINATORS (plan sections 3.1, 3.2).

Why these tests exist at all: on the LIVE CADL case the two candidate anchors
DIFFER (`data_asof_date='2026-08-10'` vs `action_session_date='2026-08-11'`)
and BOTH satisfy `<= F = 2026-08-12`. An implementation reading
`data_asof_date` is green on CADL, green on the acceptance test, green on the
operator gate, and WRONG. So the discriminating fixture is built from the
LIVE trade-21 / LQDA weekend shape, where the wrong anchor ACCEPTS exactly
where the right one REFUSES.

Every fixture docstring carries BOTH anchor values and the verdict each
produces -- the numbers ARE the test.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.trades.cohort_provenance_correction import (
    CohortProvenanceCorrectionError,
    preview_cohort_provenance_correction,
    resolve_authoritative_entry_fill,
)
from tests.trades._cohort_provenance_fixtures import (
    build_cadl_case,
    seed_fill,
)

REASON = "the framework's own contemporaneous record"


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = ensure_schema(tmp_path / "swing.db")
    try:
        yield c
    finally:
        c.close()


def _preview(conn, ids, **kw):
    return preview_cohort_provenance_correction(
        conn,
        trade_id=ids["trade_id"],
        cited_candidate_id=ids["candidate_id"],
        cited_recommendation_id=ids["daily_recommendation_id"],
        reason=REASON,
        **kw,
    )


# --------------------------------------------------------------- the live case


def test_live_cadl_shape_is_accepted_and_both_anchors_differ(conn) -> None:
    """WRONG anchor `data_asof_date` = 2026-08-10 -> `<= 2026-08-12` ACCEPT.
    RIGHT anchor `action_session_date` = 2026-08-11 -> `<= 2026-08-12` ACCEPT.
    Both accept, which is precisely why CADL cannot be the discriminator."""
    ids = build_cadl_case(conn)
    p = _preview(conn, ids)
    assert p.candidate_action_session_date == "2026-08-11"
    assert p.recommendation_action_session_date == "2026-08-11"
    assert p.entry_fill_session_date == "2026-08-12"
    run_asof = conn.execute(
        "SELECT data_asof_date FROM evaluation_runs WHERE id = ?",
        (ids["evaluation_run_id"],)).fetchone()[0]
    assert run_asof == "2026-08-10" != p.candidate_action_session_date


# ------------------------------------------------- T2a-T2c: the cited anchors


def test_T2a_candidate_anchor_is_action_session_not_data_asof(conn) -> None:
    """The trade-21 / LQDA weekend shape.
    `F = 2026-08-07`.
    WRONG `data_asof_date` = 2026-08-07 -> `2026-08-07 <= 2026-08-07` ACCEPT.
    RIGHT `action_session_date` = 2026-08-10 -> `2026-08-10 <= 2026-08-07`
    FALSE -> REFUSE.
    The DR anchor is deliberately ACCEPTING (2026-08-07) so it cannot mask the
    candidate's refusal. An implementation reading `data_asof_date` writes
    three columns here and this test fails."""
    ids = build_cadl_case(
        conn,
        data_asof_date="2026-08-07",
        action_session_date="2026-08-10",
        dr_action_session_date="2026-08-07",
        dr_data_asof_date="2026-08-07",
        run_ts="2026-08-07T17:30:02",
        fill_datetime="2026-08-07T16:00:00",
        entry_date="2026-08-07",
        pipeline_finished_ts="2026-08-07T17:44:00",
    )
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    msg = str(exc.value)
    assert "evaluation_runs.action_session_date" in msg
    assert "2026-08-10" in msg and "2026-08-07" in msg


def test_T2b_recommendation_anchor_is_gated_on_its_own_column(conn) -> None:
    """Candidate run `action_session_date` = 2026-08-06 -> ACCEPT.
    DR row WRONG `data_asof_date` = 2026-08-07 -> `<= 2026-08-07` ACCEPT.
    DR row RIGHT `action_session_date` = 2026-08-10 -> REFUSE.
    An implementation that gates only the candidate, or reads the DR's
    `data_asof_date`, accepts here."""
    ids = build_cadl_case(
        conn,
        data_asof_date="2026-08-05",
        action_session_date="2026-08-06",
        dr_data_asof_date="2026-08-07",
        dr_action_session_date="2026-08-10",
        run_ts="2026-08-05T17:30:02",
        fill_datetime="2026-08-07T16:00:00",
        entry_date="2026-08-07",
        pipeline_finished_ts="2026-08-05T17:44:00",
    )
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    msg = str(exc.value)
    assert "daily_recommendations.action_session_date" in msg
    assert "2026-08-10" in msg


def test_T2c_one_anchor_is_never_applied_to_both_rows(conn) -> None:
    """The INFERENCE TRAP. Candidate run 2026-08-10, DR row 2026-08-07 --
    the two DISAGREE, which live data never shows (0 of 182) and the schema
    does not forbid. `F = 2026-08-07` -> REFUSE on the candidate.
    An implementation that reads ONE anchor and applies it to both cited rows
    accepts here."""
    ids = build_cadl_case(
        conn,
        data_asof_date="2026-08-07",
        action_session_date="2026-08-10",
        dr_data_asof_date="2026-08-06",
        dr_action_session_date="2026-08-07",
        run_ts="2026-08-07T17:30:02",
        fill_datetime="2026-08-07T16:00:00",
        entry_date="2026-08-07",
        pipeline_finished_ts="2026-08-07T17:44:00",
    )
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert "evaluation_runs.action_session_date" in str(exc.value)


# -------------------------------------------- T2d-T2e: `<=` in both directions


def test_T2d_equality_ACCEPTS_trade_17s_real_shape(conn) -> None:
    """Trade 17's live shape: candidate + DR `action_session_date` = F =
    2026-06-25. `2026-06-25 <= 2026-06-25` -> ACCEPT.
    A strict `<` implementation REFUSES here -- and would refuse 10 of the 11
    live candidate-bearing trades including the two rows the rule was derived
    from."""
    ids = build_cadl_case(
        conn,
        ticker="VSTS",
        data_asof_date="2026-06-24",
        action_session_date="2026-06-25",
        run_ts="2026-06-24T17:30:02",
        pipeline_finished_ts="2026-06-24T17:44:00",
        fill_datetime="2026-06-25T16:00:00",
        entry_date="2026-06-25",
        non_pass={},
    )
    p = _preview(conn, ids)
    assert p.candidate_action_session_date == p.entry_fill_session_date


def test_T2e_one_day_later_REFUSES(conn) -> None:
    """Candidate `action_session_date` = 2026-08-13, `F` = 2026-08-12.
    `2026-08-13 <= 2026-08-12` is FALSE -> REFUSE.
    Built with `data_asof_date` = 2026-08-12, which the WRONG anchor ACCEPTS,
    so this discriminates too -- though T2a-T2c stay the sharper instruments.
    An off-by-one that used `<` on the wrong side would pass this and fail
    T2d, which is why both directions are pinned."""
    ids = build_cadl_case(
        conn,
        data_asof_date="2026-08-12",
        action_session_date="2026-08-13",
        dr_action_session_date="2026-08-11",
        run_ts="2026-08-12T17:30:02",
        pipeline_finished_ts="2026-08-12T17:44:00",
    )
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert "POST-DATES" in str(exc.value)


# ---------------------------------------- T2f-T2h: which column supplies `F`


def test_T2f_F_comes_from_the_fill_not_from_trades_entry_date(conn) -> None:
    """`trades.entry_date` = 2026-08-11 while the authoritative entry fill is
    2026-08-12T16:00:00, so `F` = 2026-08-12; cited candidate
    `action_session_date` = 2026-08-12 -> `2026-08-12 <= 2026-08-12` ACCEPT.
    An implementation reading `trades.entry_date` computes `F` = 2026-08-11
    and REFUSES. The divergence is a SUPPORTED live state -- item 5 compares
    the two explicitly and handles disagreement."""
    ids = build_cadl_case(
        conn,
        data_asof_date="2026-08-11",
        action_session_date="2026-08-12",
        run_ts="2026-08-11T17:30:02",
        pipeline_finished_ts="2026-08-11T17:44:00",
        entry_date="2026-08-11",
        fill_datetime="2026-08-12T16:00:00",
    )
    p = _preview(conn, ids)
    assert p.entry_fill_session_date == "2026-08-12"
    stored_entry_date = conn.execute(
        "SELECT entry_date FROM trades WHERE id = ?",
        (ids["trade_id"],)).fetchone()[0]
    assert stored_entry_date == "2026-08-11" != p.entry_fill_session_date


def test_T2g_the_AUTHORITATIVE_fill_supplies_F_not_the_latest(conn) -> None:
    """Two entry fills, 2026-08-12T16:00:00 and 2026-08-14T16:00:00; cited
    candidate `action_session_date` = 2026-08-13.
    Authoritative (earliest) fill -> `F` = 2026-08-12 -> `2026-08-13 <=
    2026-08-12` FALSE -> REFUSE.
    An implementation taking the LATEST fill computes `F` = 2026-08-14 and
    ACCEPTS."""
    ids = build_cadl_case(
        conn,
        data_asof_date="2026-08-12",
        action_session_date="2026-08-13",
        run_ts="2026-08-12T17:30:02",
        pipeline_finished_ts="2026-08-12T17:44:00",
        fill_datetime="2026-08-12T16:00:00",
    )
    seed_fill(
        conn, trade_id=ids["trade_id"],
        fill_datetime="2026-08-14T16:00:00", quantity=5.0,
    )
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert "POST-DATES" in str(exc.value)
    assert "2026-08-12" in str(exc.value)


def test_T2h_offset_bearing_fill_is_REFUSED_not_prefix_anchored(conn) -> None:
    """`fill_datetime` = 2026-08-13T00:30:00Z. Its `[:10]` prefix is
    2026-08-13, which is ONE SESSION LATE (the fill is the 2026-08-12 ET
    session) -- i.e. MORE PERMISSIVE. The surface names the representation
    unsupported instead of silently mis-dating."""
    ids = build_cadl_case(conn, fill_datetime="2026-08-13T00:30:00Z")
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    msg = str(exc.value)
    assert "UNSUPPORTED" in msg
    assert "offset" in msg or "Z suffix" in msg


# --------------------------------------------- the local resolver (section 3.0)


def test_local_resolver_REFUSES_a_basic_form_sibling_fill(conn) -> None:
    """The selection-rule discriminator. Two entry fills: canonical
    `2026-08-12T16:00:00` and basic-form `20260811T160000`. Verified:
    `'2026-08-12T16:00:00' < '20260811T160000'` is True, so a SQL
    `ORDER BY fill_datetime ASC LIMIT 1` returns the 08-12 row as 'earliest'
    and NEVER SEES the other -- handing the gate a day-later, more permissive
    `F`. The local resolver loads both and refuses."""
    assert "2026-08-12T16:00:00" < "20260811T160000"
    ids = build_cadl_case(conn)
    seed_fill(
        conn, trade_id=ids["trade_id"], fill_datetime="20260811T160000",
        quantity=1.0,
    )
    from swing.data.repos.fills import get_authoritative_entry_fill
    lexical = get_authoritative_entry_fill(conn, ids["trade_id"])
    assert lexical is not None
    assert lexical.fill_datetime == "2026-08-12T16:00:00"  # the WRONG answer
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        resolve_authoritative_entry_fill(conn, ids["trade_id"])
    assert "EXTENDED" in str(exc.value) or "parseable" in str(exc.value)


def test_local_resolver_matches_the_repo_helper_on_canonical_data(conn) -> None:
    """The equivalence pin: on a well-formed corpus the two agree, so the
    divergence is scoped to the malformed case and cannot become a SECOND
    definition of 'the authoritative entry fill'."""
    from swing.data.repos.fills import get_authoritative_entry_fill

    ids = build_cadl_case(conn)
    seed_fill(
        conn, trade_id=ids["trade_id"], fill_datetime="2026-08-14T16:00:00",
        quantity=3.0)
    seed_fill(
        conn, trade_id=ids["trade_id"], fill_datetime="2026-08-11T16:00:00",
        quantity=2.0)
    seed_fill(
        conn, trade_id=ids["trade_id"], fill_datetime="2026-08-20T16:00:00",
        action="exit", quantity=1.0, reason="stop")
    mine = resolve_authoritative_entry_fill(conn, ids["trade_id"])
    theirs = get_authoritative_entry_fill(conn, ids["trade_id"])
    assert theirs is not None
    assert mine.fill_id == theirs.fill_id
    assert mine.fill_datetime == theirs.fill_datetime


def test_a_trade_with_no_entry_fill_is_refused(conn) -> None:
    ids = build_cadl_case(conn)
    conn.execute("DELETE FROM fills WHERE trade_id = ?", (ids["trade_id"],))
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert "no action='entry' fill" in str(exc.value)


# ------------------------------------------- non-session anchors (section 5.1)


def test_a_sunday_candidate_anchor_is_refused(conn) -> None:
    """2026-08-09 is a SUNDAY. It parses, round-trips, and satisfies `<=` a
    Monday `F` -- so parsing alone accepts it. `action_session_for_run` always
    derives an NYSE session, so its presence is corruption."""
    import datetime as _dt
    assert _dt.date(2026, 8, 9).weekday() == 6
    ids = build_cadl_case(
        conn,
        data_asof_date="2026-08-07",
        action_session_date="2026-08-09",
        dr_action_session_date="2026-08-07",
        run_ts="2026-08-07T17:30:02",
        pipeline_finished_ts="2026-08-07T17:44:00",
        fill_datetime="2026-08-10T16:00:00",
        entry_date="2026-08-10",
    )
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert "not an NYSE trading session" in str(exc.value)


def test_a_holiday_fill_session_is_refused(conn) -> None:
    """2026-07-03 is the observed Independence Day holiday (2026-07-04 is a
    Saturday), so `F` itself must be validated -- not only the cited rows."""
    from swing.evaluation.dates import is_trading_session
    import datetime as _dt
    assert not is_trading_session(_dt.date(2026, 7, 3))
    ids = build_cadl_case(
        conn,
        data_asof_date="2026-07-01",
        action_session_date="2026-07-02",
        run_ts="2026-07-01T17:30:02",
        pipeline_finished_ts="2026-07-01T17:44:00",
        fill_datetime="2026-07-03T16:00:00",
        entry_date="2026-07-02",
    )
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert "not an NYSE trading session" in str(exc.value)


@pytest.mark.parametrize("bad", ["2026-02-30", "garbage", "20260811"])
def test_malformed_cited_dates_are_refused_before_any_comparison(
    conn, bad,
) -> None:
    """`evaluation_runs.action_session_date` is a bare TEXT NOT NULL column,
    so `'2026-02-30'` is schema-legal AND lexically `<=` a later `F`. The
    validation lives in the authorization function, not only in the model or
    the DDL, because `--dry-run` constructs no model and inserts no row."""
    ids = build_cadl_case(conn)
    conn.execute(
        "UPDATE evaluation_runs SET action_session_date = ? WHERE id = ?",
        (bad, ids["evaluation_run_id"]))
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    msg = str(exc.value)
    assert "action_session_date" in msg


def test_a_garbage_run_ts_is_refused(conn) -> None:
    ids = build_cadl_case(conn)
    conn.execute(
        "UPDATE evaluation_runs SET run_ts = 'garbage' WHERE id = ?",
        (ids["evaluation_run_id"],))
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert "run_ts" in str(exc.value)


# ------------------------------------------------------- eligibility + clocks


def test_a_near_trigger_recommendation_is_refused_at_its_own_rung(conn) -> None:
    ids = build_cadl_case(conn, recommendation="near_trigger")
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert "near_trigger" in str(exc.value)


def test_a_watch_bucket_candidate_is_refused_with_the_reason(conn) -> None:
    ids = build_cadl_case(conn, bucket="watch")
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    msg = str(exc.value)
    assert "entry_path" in msg and "COMPOSE" in msg


def test_a_trade_that_already_carries_provenance_is_refused(conn) -> None:
    ids = build_cadl_case(conn)
    conn.execute(
        "UPDATE trades SET trade_origin = 'pipeline_aplus' WHERE id = ?",
        (ids["trade_id"],))
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert "already carries cohort provenance" in str(exc.value)


def test_ticker_disagreement_is_refused_on_each_side(conn) -> None:
    ids = build_cadl_case(conn)
    conn.execute(
        "UPDATE candidates SET ticker = 'OTHER' WHERE id = ?",
        (ids["candidate_id"],))
    with pytest.raises(CohortProvenanceCorrectionError):
        _preview(conn, ids)
    conn.execute(
        "UPDATE candidates SET ticker = 'CADL' WHERE id = ?",
        (ids["candidate_id"],))
    conn.execute(
        "UPDATE daily_recommendations SET ticker = 'OTHER' WHERE id = ?",
        (ids["daily_recommendation_id"],))
    with pytest.raises(CohortProvenanceCorrectionError):
        _preview(conn, ids)


def test_run_ts_is_normalized_to_utc_and_the_date_ROLLS(conn) -> None:
    """The positive normalization assertion. `2026-08-10T17:30:26` HST is
    `2026-08-11T03:30:26` UTC -- the DATE rolls, so a stored `_utc` equal to
    its `_raw` sibling is PROOF the conversion was skipped. Refusal-only tests
    cannot see a skipped normalization, because the margin refusal fires
    whether or not the bounds were converted."""
    ids = build_cadl_case(conn)
    p = _preview(conn, ids)
    assert p.run_ts_raw == "2026-08-10T17:30:26"
    assert p.run_ts_utc == "2026-08-11T03:30:26"
    assert p.run_ts_utc != p.run_ts_raw
    assert p.run_ts_utc[:10] != p.run_ts_raw[:10]


def test_missing_candidate_or_recommendation_is_refused(conn) -> None:
    ids = build_cadl_case(conn)
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        preview_cohort_provenance_correction(
            conn, trade_id=ids["trade_id"], cited_candidate_id=987654,
            cited_recommendation_id=ids["daily_recommendation_id"],
            reason=REASON)
    assert "candidate 987654 not found" in str(exc.value)
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        preview_cohort_provenance_correction(
            conn, trade_id=ids["trade_id"],
            cited_candidate_id=ids["candidate_id"],
            cited_recommendation_id=987654, reason=REASON)
    assert "987654 not found" in str(exc.value)


def test_a_missing_trade_is_refused_first(conn) -> None:
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        preview_cohort_provenance_correction(
            conn, trade_id=987654, cited_candidate_id=1,
            cited_recommendation_id=1, reason=REASON)
    assert "trade 987654 not found" in str(exc.value)


def test_the_pipeline_local_timezone_constant_is_the_single_source(conn) -> None:
    """The envelope extension's own pin: THREE consumers resolve to ONE
    constant object, so the literal is not re-spelled a third time."""
    import inspect

    from swing.evaluation.dates import (
        PIPELINE_LOCAL_TIMEZONE,
        action_session_for_run,
        last_completed_session,
    )
    from swing.trades import cohort_provenance_correction as svc

    assert PIPELINE_LOCAL_TIMEZONE == "Pacific/Honolulu"
    assert (inspect.signature(last_completed_session)
            .parameters["tz"].default is PIPELINE_LOCAL_TIMEZONE)
    assert (inspect.signature(action_session_for_run)
            .parameters["tz"].default is PIPELINE_LOCAL_TIMEZONE)
    assert svc.PIPELINE_LOCAL_TIMEZONE is PIPELINE_LOCAL_TIMEZONE
    # And the service does not re-spell it.
    source = inspect.getsource(svc)
    assert "Pacific/Honolulu" not in source
