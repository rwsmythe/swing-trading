"""Task 5 -- the LAST-WORD guard, the citation binding and DR cardinality.

Contemporaneity alone does not close citation-shopping: on the live data CADL
has 33 `candidates` rows and FOUR of them pre-date the 08-12 fill (watch
08-06, watch 08-07, watch 08-10, aplus 08-11), so all four are
contemporaneous and an operator free to choose picks the bucket he likes.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.trades.cohort_provenance_correction import (
    CohortProvenanceCorrectionError,
    preview_cohort_provenance_correction,
)
from tests.trades._cohort_provenance_fixtures import (
    build_cadl_case,
    seed_candidate,
    seed_evaluation_run,
    seed_pipeline_run,
    seed_recommendation,
)

REASON = "the framework's own contemporaneous record"


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = ensure_schema(tmp_path / "swing.db")
    try:
        yield c
    finally:
        c.close()


def _preview(conn, ids, *, candidate_id=None, recommendation_id=None):
    return preview_cohort_provenance_correction(
        conn,
        trade_id=ids["trade_id"],
        cited_candidate_id=candidate_id or ids["candidate_id"],
        cited_recommendation_id=(
            recommendation_id or ids["daily_recommendation_id"]),
        reason=REASON,
    )


def _seed_competitor(
    conn, *, ticker="CADL", data_asof, action_session, run_ts, bucket="watch",
) -> tuple[int, int]:
    run_id = seed_evaluation_run(
        conn, run_ts=run_ts, data_asof_date=data_asof,
        action_session_date=action_session)
    cand_id = seed_candidate(
        conn, evaluation_run_id=run_id, ticker=ticker, bucket=bucket,
        non_pass={"tightness": "fail"} if bucket == "watch" else {})
    return cand_id, run_id


# ----------------------------------------------------------- the live shape


def test_the_live_cadl_vicinity_still_accepts_12341s_analogue(conn) -> None:
    """The four real CADL rows around the fill: watch 08-06, watch 08-07,
    watch 08-10, aplus 08-11. All four pre-date the 08-12 fill; the aplus row
    on 08-11 IS the last word, so the live case is unaffected."""
    ids = build_cadl_case(conn)
    for asof, session, ts in (
        ("2026-08-05", "2026-08-06", "2026-08-05T17:30:00"),
        ("2026-08-06", "2026-08-07", "2026-08-06T17:30:00"),
        ("2026-08-07", "2026-08-10", "2026-08-07T17:30:00"),
    ):
        _seed_competitor(
            conn, data_asof=asof, action_session=session, run_ts=ts)
    p = _preview(conn, ids)
    assert p.cited_candidate_id == ids["candidate_id"]


def test_a_later_qualifying_row_makes_the_earlier_citation_refused(conn) -> None:
    """A `skip` on the entry session SUPERSEDES the earlier aplus row, and the
    trade becomes uncorrectable through this surface. Conservative in a
    contestable way and deliberately so: the alternative admits
    citation-shopping. Verified NOT to affect the live CADL case -- run 138
    (action session 2026-08-12) contains no CADL row."""
    ids = build_cadl_case(conn)
    later_id, later_run = _seed_competitor(
        conn, data_asof="2026-08-11", action_session="2026-08-12",
        run_ts="2026-08-11T17:44:24", bucket="skip")
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    msg = str(exc.value)
    assert f"candidate {later_id}" in msg
    assert f"evaluation run {later_run}" in msg
    assert "last word" in msg


def test_a_row_AFTER_the_fill_does_not_supersede(conn) -> None:
    """The guard ranks only rows that pre-date `F`; a post-fill row is not a
    competitor at all."""
    ids = build_cadl_case(conn)
    _seed_competitor(
        conn, data_asof="2026-08-12", action_session="2026-08-13",
        run_ts="2026-08-12T17:44:24", bucket="aplus")
    p = _preview(conn, ids)
    assert p.cited_candidate_id == ids["candidate_id"]


def test_the_guard_ranks_on_run_ts_then_id_within_one_session(conn) -> None:
    """Multiple runs per action session are ROUTINE on live data (six on
    2026-07-06), so the tiebreak matters."""
    ids = build_cadl_case(conn)
    later_id, _ = _seed_competitor(
        conn, data_asof="2026-08-10", action_session="2026-08-11",
        run_ts="2026-08-10T18:30:00", bucket="watch")
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    assert f"candidate {later_id}" in str(exc.value)


def test_a_basic_form_competitor_is_REFUSED_not_silently_dropped(conn) -> None:
    """The sharpest case. `'20260811' <= '2026-08-12'` is FALSE because `'0'`
    (0x30) sorts after `'-'` (0x2D), so a lexical SQL filter DROPS this row
    from the competitor set and the guard then blesses the operator's earlier
    citation -- the citation-shopping it exists to prevent, arriving through
    its own comparison. Validation scope is every row the DECISION reads."""
    assert not ("20260811" <= "2026-08-12")
    ids = build_cadl_case(conn)
    bad_id, bad_run = _seed_competitor(
        conn, data_asof="20260810", action_session="20260811",
        run_ts="2026-08-10T18:30:00", bucket="aplus")
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    msg = str(exc.value)
    assert f"competitor candidate {bad_id}" in msg
    assert f"evaluation run {bad_run}" in msg


def test_a_malformed_competitor_run_ts_is_refused_too(conn) -> None:
    ids = build_cadl_case(conn)
    bad_id, bad_run = _seed_competitor(
        conn, data_asof="2026-08-05", action_session="2026-08-06",
        run_ts="not-a-timestamp")
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    msg = str(exc.value)
    assert f"competitor candidate {bad_id}" in msg and "run_ts" in msg
    assert str(bad_run) in msg


def test_a_hidden_non_session_competitor_anchor_is_refused(conn) -> None:
    """2026-08-09 is a SUNDAY. A competitor carrying it would otherwise win
    the ranking on a Monday-or-later fill while being an impossible framework
    record."""
    ids = build_cadl_case(conn)
    bad_id, _ = _seed_competitor(
        conn, data_asof="2026-08-07", action_session="2026-08-09",
        run_ts="2026-08-07T18:30:00", bucket="aplus")
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    msg = str(exc.value)
    assert f"competitor candidate {bad_id}" in msg
    assert "not an NYSE trading session" in msg


def test_another_tickers_rows_are_not_competitors(conn) -> None:
    ids = build_cadl_case(conn)
    _seed_competitor(
        conn, ticker="VSTS", data_asof="2026-08-11", action_session="2026-08-12",
        run_ts="2026-08-11T17:44:24", bucket="aplus")
    p = _preview(conn, ids)
    assert p.cited_candidate_id == ids["candidate_id"]


# ------------------------------------------------------------- DR cardinality


def test_two_same_run_today_decision_rows_refuse_naming_both(conn) -> None:
    """Schema-legal: the unique index is keyed on (action_session_date,
    ticker, recommendation), and `upsert_recommendation` rewrites
    `evaluation_run_id` in place -- so two rows CAN share a run. The refusal
    fires EVEN THOUGH the operator's supplied id is one of them, because the
    cardinality rung precedes the confirmation compare and a supplied id must
    never break a tie."""
    ids = build_cadl_case(conn)
    # A DIFFERENT action session, which is what the unique index permits --
    # and `upsert_recommendation`'s DO UPDATE SET is what lets it end up
    # carrying the SAME evaluation_run_id.
    second = seed_recommendation(
        conn, evaluation_run_id=ids["evaluation_run_id"],
        data_asof_date="2026-08-10", action_session_date="2026-08-10",
        ticker="CADL", recommendation="today_decision",
    )
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids)
    msg = str(exc.value)
    assert "carries 2 " in msg
    assert str(ids["daily_recommendation_id"]) in msg and str(second) in msg


def test_zero_same_run_today_decision_rows_refuse_naming_the_count(
    conn,
) -> None:
    ids = build_cadl_case(conn)
    other_run = seed_evaluation_run(
        conn, run_ts="2026-08-10T17:30:26", data_asof_date="2026-08-10",
        action_session_date="2026-08-11")
    orphan = seed_recommendation(
        conn, evaluation_run_id=other_run, data_asof_date="2026-08-10",
        action_session_date="2026-08-10", ticker="CADL")
    conn.execute(
        "DELETE FROM daily_recommendations WHERE id = ?",
        (ids["daily_recommendation_id"],))
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids, recommendation_id=orphan)
    assert "carries 0 " in str(exc.value)


def test_a_recommendation_from_another_run_is_refused_as_unconfirmed(
    conn,
) -> None:
    """`--cited-recommendation` CONFIRMS the derived row; it never selects."""
    ids = build_cadl_case(conn)
    other_run = seed_evaluation_run(
        conn, run_ts="2026-08-10T17:31:00", data_asof_date="2026-08-10",
        action_session_date="2026-08-11")
    seed_pipeline_run(
        conn, evaluation_run_id=other_run, data_asof_date="2026-08-10",
        action_session_date="2026-08-11")
    impostor = seed_recommendation(
        conn, evaluation_run_id=other_run, data_asof_date="2026-08-10",
        action_session_date="2026-08-10", ticker="CADL")
    with pytest.raises(CohortProvenanceCorrectionError) as exc:
        _preview(conn, ids, recommendation_id=impostor)
    msg = str(exc.value)
    assert "CONFIRMATION, never the" in msg
    assert str(ids["daily_recommendation_id"]) in msg
