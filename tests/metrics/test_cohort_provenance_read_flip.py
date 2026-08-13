"""Task 10 -- the cohort read flips, computed under BOTH paths.

The commissioning brief asked for "the monthly-read denominator moving
2/20 -> 2/21". Measured on a copy of the live DB, that figure cannot be right
for TWO independent reasons, and this file asserts the arithmetic that IS:

  - 20 is `hypothesis_registry.target_sample_size`, a static REGISTRY column.
    Nothing a correction does moves it.
  - the NUMERATOR cannot move either, because trade 23 is OPEN.
    `compute_hypothesis_progress_breakdown` computes `current_sample` from
    `list_closed_trades` ONLY; open trades go to the separate display-only
    `in_flight_sample`, whose own comment says it "does NOT count toward
    `current_sample` ... or any tripwire arithmetic".

So the real movement is `in_flight_sample` 0 -> 1, and `current_sample` moves
only when the trade CLOSES. The closed variant below is what makes the
open-trade assertion non-vacuous: without it, "current_sample unchanged" is
indistinguishable from "the correction did nothing".
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.journal.stats import compute_hypothesis_progress_breakdown
from swing.metrics.cohort import list_trades_for_cohort
from swing.trades.cohort_provenance_correction import (
    correct_cohort_provenance,
)
from tests.trades._cohort_provenance_fixtures import (
    CADL_LABEL,
    H1_ID,
    H1_NAME,
    build_cadl_case,
    seed_fill,
)

REASON = "the framework's own contemporaneous record"
STARTING_EQUITY = 7500.0


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = ensure_schema(tmp_path / "swing.db")
    try:
        yield c
    finally:
        c.close()


def _h1(conn):
    rows = compute_hypothesis_progress_breakdown(
        conn, starting_equity=STARTING_EQUITY)
    return next(r for r in rows if r.hypothesis_id == H1_ID)


def _apply(conn, ids):
    if conn.in_transaction:
        conn.commit()
    return correct_cohort_provenance(
        conn,
        trade_id=ids["trade_id"],
        cited_candidate_id=ids["candidate_id"],
        cited_recommendation_id=ids["daily_recommendation_id"],
        reason=REASON,
    )


def test_the_open_trade_flip_is_in_flight_0_to_1_and_nothing_else(
    conn,
) -> None:
    ids = build_cadl_case(conn)
    conn.commit()

    pre = _h1(conn)
    pre_cohort = [t.id for t in list_trades_for_cohort(
        conn, hypothesis_label=H1_NAME)]
    pre_standard = [t.id for t in list_trades_for_cohort(
        conn, hypothesis_label=H1_NAME, entry_intent="standard")]
    assert ids["trade_id"] not in pre_cohort
    assert ids["trade_id"] not in pre_standard
    assert pre.in_flight_sample == 0
    assert pre.target_sample == 20

    _apply(conn, ids)

    post = _h1(conn)
    post_cohort = [t.id for t in list_trades_for_cohort(
        conn, hypothesis_label=H1_NAME)]
    post_standard = [t.id for t in list_trades_for_cohort(
        conn, hypothesis_label=H1_NAME, entry_intent="standard")]
    assert ids["trade_id"] in post_cohort
    assert ids["trade_id"] in post_standard
    # THE MOVEMENT.
    assert post.in_flight_sample == pre.in_flight_sample + 1 == 1
    # AND WHAT DOES NOT MOVE.
    assert post.current_sample == pre.current_sample
    assert post.target_sample == pre.target_sample == 20


def test_a_CLOSED_trade_moves_current_sample_and_leaves_in_flight_at_zero(
    conn,
) -> None:
    """The variant that makes the assertion above non-vacuous."""
    ids = build_cadl_case(conn, trade_state="entered")
    seed_fill(
        conn, trade_id=ids["trade_id"], fill_datetime="2026-08-20T16:00:00",
        action="exit", quantity=19.0, price=12.0, reason="target")
    conn.execute(
        "UPDATE trades SET state = 'closed', current_size = 0 WHERE id = ?",
        (ids["trade_id"],))
    conn.commit()

    pre = _h1(conn)
    _apply(conn, ids)
    post = _h1(conn)

    assert post.current_sample == pre.current_sample + 1
    assert post.in_flight_sample == pre.in_flight_sample == 0
    assert post.target_sample == pre.target_sample == 20


def test_target_sample_is_a_static_registry_column_not_a_denominator(
    conn,
) -> None:
    """20 does not grow. Read straight off the registry, so the claim rests on
    the column rather than on the breakdown's own arithmetic."""
    ids = build_cadl_case(conn)
    conn.commit()
    registry_target = conn.execute(
        "SELECT target_sample_size FROM hypothesis_registry WHERE id = ?",
        (H1_ID,)).fetchone()[0]
    assert registry_target == 20
    _apply(conn, ids)
    assert conn.execute(
        "SELECT target_sample_size FROM hypothesis_registry WHERE id = ?",
        (H1_ID,)).fetchone()[0] == registry_target


def test_the_flip_holds_under_the_SUFFIXED_label_string(conn) -> None:
    """The written label is `A+ baseline (aplus); failed: TT8_rs_rank`, and
    the cohort predicate's semicolon rule is what carries it into the cohort.
    Asserting the membership AND the exact stored string separately is
    deliberate: a future `_descriptive_label` change should break the string
    assertion loudly rather than break cohort membership silently."""
    ids = build_cadl_case(conn)
    conn.commit()
    _apply(conn, ids)
    stored = conn.execute(
        "SELECT hypothesis_label FROM trades WHERE id = ?",
        (ids["trade_id"],)).fetchone()[0]
    assert stored == CADL_LABEL
    assert "; failed:" in stored
    assert ids["trade_id"] in [
        t.id for t in list_trades_for_cohort(conn, hypothesis_label=H1_NAME)]


def test_the_flip_holds_identically_under_the_CLEAN_label(conn) -> None:
    """Both candidate label strings are cohort-EQUIVALENT: exact-equality for
    the clean one, the semicolon prefix rule for the suffixed one. So the
    cohort read cannot be what decides between them -- the evidence rule
    does."""
    ids = build_cadl_case(conn, non_pass={}, ticker="VSTS")
    conn.commit()
    _apply(conn, ids)
    stored = conn.execute(
        "SELECT hypothesis_label FROM trades WHERE id = ?",
        (ids["trade_id"],)).fetchone()[0]
    assert stored == "A+ baseline (aplus)"
    assert ids["trade_id"] in [
        t.id for t in list_trades_for_cohort(conn, hypothesis_label=H1_NAME)]


def test_a_non_standard_intent_trade_joins_the_label_cohort_only(
    conn,
) -> None:
    """The D29 intent filter is orthogonal to this correction and stays so: a
    `hypothesis_test_by_design` trade gains the label but not the STANDARD
    cohort -- trade 4's live shape."""
    ids = build_cadl_case(
        conn, ticker="YOU", entry_intent="hypothesis_test_by_design")
    conn.commit()
    _apply(conn, ids)
    assert ids["trade_id"] in [
        t.id for t in list_trades_for_cohort(conn, hypothesis_label=H1_NAME)]
    assert ids["trade_id"] not in [
        t.id for t in list_trades_for_cohort(
            conn, hypothesis_label=H1_NAME, entry_intent="standard")]
