"""The OPEN-LATCH rule (plan A.2): a fire while a latch is LIVE is a
RE-CONFIRMATION, not a new latch -- so it never re-freezes the pivot."""
from __future__ import annotations

from datetime import date

from swing.latches.models import DailyBar, FireRow
from swing.latches.service import derive_latches


def _fire(cid, run, ticker, pivot, stop, session, run_ts, prid=None):
    return FireRow(candidate_id=cid, evaluation_run_id=run, ticker=ticker,
                   pivot=pivot, initial_stop=stop, action_session_date=session,
                   run_ts=run_ts, pipeline_run_id=prid)


# --- The live SLDB geometry: runs 9 + 10 share action session 2026-04-22
#     (TWO evaluation runs, ONE session); run 12 is 2026-04-24, a later
#     session, fired while the 04-22 latch was still live. -------------------
SLDB_FIRES = [
    _fire(101, 9, "SLDB", 8.866, 6.40, "2026-04-22", "2026-04-21T21:18:30"),
    _fire(102, 10, "SLDB", 8.866, 6.40, "2026-04-22", "2026-04-22T07:15:19"),
    _fire(103, 12, "SLDB", 8.866, 6.40, "2026-04-24", "2026-04-23T21:58:18"),
]


def test_sldb_three_aplus_rows_produce_exactly_one_latch():
    """FAILS a naive per-(evaluation_run_id, ticker) implementation, which
    would emit THREE latches for one mandate."""
    d = derive_latches(
        fires=SLDB_FIRES, bars_by_ticker={"SLDB": []}, entries_by_ticker={},
        horizon_session=date(2026, 4, 27), derivation_session=date(2026, 4, 24))
    assert len(d.latches) == 1
    latch = d.latches[0]
    assert latch.identity.candidate_id == 101          # the EARLIEST row wins
    assert latch.identity.evaluation_run_id == 9
    assert latch.anchor == date(2026, 4, 22)
    assert latch.reconfirmation_candidate_ids == (102, 103)


def test_a_different_pivot_refire_supersedes_rather_than_refreezing():
    """RD gate ruling, section A.2 branch (b). A drifted re-fire must NOT
    silently move the frozen pivot under the operator's resting order (the
    constraint-1 hazard) and must NOT leave him holding a mandate the setup has
    left behind (RD's 07-23 point). It TERMINATES the old latch with a RECORDED
    reason and arms a new one.

    Three implementations FAIL here: a per-row identity (2 latches but the old
    one never cleared), a blanket re-confirmation (1 latch), and a silent
    re-freeze (1 latch at 9.90)."""
    fires = [
        _fire(201, 9, "DRFT", 10.00, 8.00, "2026-04-22", "2026-04-21T21:00:00"),
        _fire(202, 12, "DRFT", 9.90, 7.10, "2026-04-24", "2026-04-23T21:00:00"),
    ]
    d = derive_latches(
        fires=fires, bars_by_ticker={"DRFT": []}, entries_by_ticker={},
        horizon_session=date(2026, 4, 27), derivation_session=date(2026, 4, 24))
    assert len(d.latches) == 2
    old_latch, new_latch = d.latches
    # the OLD latch keeps its own frozen values and terminates visibly
    assert old_latch.latched_pivot == 10.00
    assert old_latch.latched_initial_stop == 8.00
    assert old_latch.state == "superseded"
    assert old_latch.clear_reason == "superseded"
    assert old_latch.clear_session == date(2026, 4, 24)   # the re-fire's session
    assert old_latch.reconfirmation_candidate_ids == ()
    # the NEW latch arms at its OWN fire's values
    assert new_latch.latched_pivot == 9.90
    assert new_latch.latched_initial_stop == 7.10
    assert new_latch.anchor == date(2026, 4, 24)
    assert new_latch.state == "armed"


def test_a_same_pivot_refire_reconfirms_and_does_not_supersede():
    """Branch (a). SLDB run 12 is the live instance: identical 8.866 / 6.40
    two sessions after the 04-22 fire. Forking here would fabricate a second
    mandate for a setup that merely held."""
    d = derive_latches(
        fires=SLDB_FIRES, bars_by_ticker={"SLDB": []}, entries_by_ticker={},
        horizon_session=date(2026, 4, 27), derivation_session=date(2026, 4, 24))
    assert len(d.latches) == 1
    assert d.latches[0].clear_reason is None
    assert d.latches[0].state == "armed"


def test_the_pivot_branch_test_uses_display_precision():
    """A sub-cent float artifact must NOT fork a latch (price-precision
    parity). 10.001 rounds to 10.00 -> branch (a)."""
    fires = [
        _fire(211, 9, "EPS", 10.00, 8.00, "2026-04-22", "2026-04-21T21:00:00"),
        _fire(212, 12, "EPS", 10.001, 8.00, "2026-04-24", "2026-04-23T21:00:00"),
    ]
    d = derive_latches(
        fires=fires, bars_by_ticker={"EPS": []}, entries_by_ticker={},
        horizon_session=date(2026, 4, 27), derivation_session=date(2026, 4, 24))
    assert len(d.latches) == 1
    assert d.latches[0].latched_pivot == 10.00


def test_a_same_pivot_different_stop_refire_reconfirms_and_keeps_the_first_stop():
    """The pivot is what the resting order is keyed to, so only the pivot
    drives the branch. Constraint 1 then keeps the ORIGINAL frozen stop."""
    fires = [
        _fire(221, 9, "STOP", 10.00, 8.00, "2026-04-22", "2026-04-21T21:00:00"),
        _fire(222, 12, "STOP", 10.00, 8.50, "2026-04-24", "2026-04-23T21:00:00"),
    ]
    d = derive_latches(
        fires=fires, bars_by_ticker={"STOP": []}, entries_by_ticker={},
        horizon_session=date(2026, 4, 27), derivation_session=date(2026, 4, 24))
    assert len(d.latches) == 1
    assert d.latches[0].latched_initial_stop == 8.00


def test_reconfirmations_are_recorded_as_signal_not_discarded():
    """RD gate: a setup that re-confirms across sessions is plausibly stronger
    evidence. The count AND the session dates must survive."""
    d = derive_latches(
        fires=SLDB_FIRES, bars_by_ticker={"SLDB": []}, entries_by_ticker={},
        horizon_session=date(2026, 4, 27), derivation_session=date(2026, 4, 24))
    latch = d.latches[0]
    assert latch.reconfirmation_candidate_ids == (102, 103)
    assert latch.reconfirmation_sessions == ("2026-04-22", "2026-04-24")


def test_a_same_session_refire_with_a_different_pivot_still_collapses():
    """Clause (i) outranks the two-branch rule: a session has ONE verdict, so
    a same-session re-run cannot supersede. (Live evidence: no A+ ticker has
    ever had mixed buckets within a session, and within-session pivot
    divergence is confined to genesis week.)"""
    fires = [
        _fire(231, 9, "SS", 10.00, 8.00, "2026-04-22", "2026-04-21T21:00:00"),
        _fire(232, 10, "SS", 9.90, 7.10, "2026-04-22", "2026-04-22T07:15:00"),
    ]
    d = derive_latches(
        fires=fires, bars_by_ticker={"SS": []}, entries_by_ticker={},
        horizon_session=date(2026, 4, 23), derivation_session=date(2026, 4, 22))
    assert len(d.latches) == 1
    assert d.latches[0].latched_pivot == 10.00
    assert d.latches[0].clear_reason is None


def test_vsts_two_fires_separated_by_a_fill_are_two_latches():
    """RD constraint 3: the run-99 latch FILLED (trade 17, 2026-06-25) and
    cleared; the run-126 fire therefore opens a genuinely NEW latch."""
    from swing.latches.models import EntryRecord
    fires = [
        _fire(8851, 99, "VSTS", 13.56, 11.62, "2026-06-25", "2026-06-24T20:06:25", 112),
        _fire(9999, 126, "VSTS", 16.90, 13.40, "2026-07-27", "2026-07-24T17:30:06", 140),
    ]
    entries = {"VSTS": [EntryRecord(
        trade_id=17, ticker="VSTS", entry_date=date(2026, 6, 25),
        candidate_id=8851, entry_price=13.61, shares=15)]}
    d = derive_latches(
        fires=fires, bars_by_ticker={"VSTS": []}, entries_by_ticker=entries,
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    assert len(d.latches) == 2
    first, second = d.latches
    assert (first.identity.evaluation_run_id, first.state) == (99, "filled")
    assert first.clear_reason == "fill" and first.clear_trade_id == 17
    assert (second.identity.evaluation_run_id, second.state) == (126, "armed")
    assert second.latched_pivot == 16.90 and second.latched_initial_stop == 13.40
    assert second.reconfirmation_candidate_ids == ()


def test_null_pivot_aplus_row_degrades_and_opens_no_latch():
    """A6: NOT write-prevented -- migration 0001 has no NOT NULL on pivot and
    SQLite stores float('nan') as NULL, so an aplus row CAN carry a NULL pivot."""
    d = derive_latches(
        fires=[_fire(301, 50, "BAD", None, 5.0, "2026-05-01", "2026-04-30T21:00:00")],
        bars_by_ticker={}, entries_by_ticker={},
        horizon_session=date(2026, 5, 1), derivation_session=date(2026, 5, 1))
    assert d.latches == ()
    assert len(d.degraded) == 1
    assert d.degraded[0].reason == "pivot_missing"
    assert d.degraded[0].candidate_id == 301


def test_a_degraded_fire_does_not_disturb_a_live_latch():
    fires = [
        _fire(401, 60, "MIX", 10.0, 8.0, "2026-05-01", "2026-04-30T21:00:00"),
        _fire(402, 61, "MIX", float("nan"), 8.0, "2026-05-04", "2026-05-01T21:00:00"),
    ]
    d = derive_latches(
        fires=fires, bars_by_ticker={"MIX": []}, entries_by_ticker={},
        horizon_session=date(2026, 5, 5), derivation_session=date(2026, 5, 4))
    assert len(d.latches) == 1 and d.latches[0].latched_pivot == 10.0
    assert d.latches[0].reconfirmation_candidate_ids == ()
    assert [x.reason for x in d.degraded] == ["pivot_missing"]


def test_stop_not_below_pivot_degrades():
    d = derive_latches(
        fires=[_fire(501, 70, "FLAT", 10.0, 10.0, "2026-05-01", "2026-04-30T21:00:00")],
        bars_by_ticker={}, entries_by_ticker={},
        horizon_session=date(2026, 5, 1), derivation_session=date(2026, 5, 1))
    assert d.latches == () and d.degraded[0].reason == "stop_not_below_pivot"


def test_bad_action_session_date_degrades_instead_of_raising():
    d = derive_latches(
        fires=[_fire(601, 80, "BADD", 10.0, 8.0, "2026-5-01", "2026-04-30T21:00:00")],
        bars_by_ticker={}, entries_by_ticker={},
        horizon_session=date(2026, 5, 1), derivation_session=date(2026, 5, 1))
    assert d.latches == () and d.degraded[0].reason == "bad_session_date"


def test_missing_stop_degrades():
    """The stop half of the same A6 analysis: `initial_stop` carries no NOT
    NULL either, and a non-finite stop lands as NULL."""
    d = derive_latches(
        fires=[_fire(511, 71, "NOSTOP", 10.0, None, "2026-05-01",
                     "2026-04-30T21:00:00")],
        bars_by_ticker={}, entries_by_ticker={},
        horizon_session=date(2026, 5, 1), derivation_session=date(2026, 5, 1))
    assert d.latches == () and d.degraded[0].reason == "stop_missing"


def test_zone_cap_is_pivot_times_one_point_oh_three():
    d = derive_latches(
        fires=[_fire(701, 121, "FTRE", 18.34, 14.88, "2026-07-20",
                     "2026-07-17T17:30:05", 135)],
        bars_by_ticker={"FTRE": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    assert d.latches[0].zone_cap == round(18.34 * 1.03, 4)


# --- Codex R1-1: the SAME-SESSION clause -----------------------------------
def test_a_same_session_refire_after_a_fill_does_not_open_a_second_latch():
    """A.2 clause (i). Without it, the fill clears the latch AS OF session S,
    the second same-session evaluation run then sees 'not live' and opens a
    DUPLICATE latch that is `armed` for a position the operator already holds
    -- firing a false LATCH_ARMED_NO_RESTING_ORDER. A still-live-only
    implementation FAILS this test with len(latches) == 2."""
    from swing.latches.models import EntryRecord
    fires = [
        _fire(801, 40, "SAME", 10.0, 8.0, "2026-05-04", "2026-05-01T21:00:00"),
        _fire(802, 41, "SAME", 10.0, 8.0, "2026-05-04", "2026-05-04T11:00:00"),
    ]
    entries = {"SAME": [EntryRecord(
        trade_id=55, ticker="SAME", entry_date=date(2026, 5, 4),
        candidate_id=801, entry_price=10.05, shares=5)]}
    d = derive_latches(
        fires=fires, bars_by_ticker={"SAME": []}, entries_by_ticker=entries,
        horizon_session=date(2026, 5, 5), derivation_session=date(2026, 5, 4))
    assert len(d.latches) == 1
    assert d.latches[0].identity.candidate_id == 801
    assert d.latches[0].reconfirmation_candidate_ids == (802,)
    assert d.latches[0].state == "filled"


def test_a_same_session_refire_after_an_invalidating_close_also_collapses():
    fires = [
        _fire(811, 40, "SAME", 10.0, 8.0, "2026-05-04", "2026-05-01T21:00:00"),
        _fire(812, 41, "SAME", 10.0, 8.0, "2026-05-04", "2026-05-04T11:00:00"),
    ]
    bars = [DailyBar(session=date(2026, 5, 4), open=9.0, high=9.2,
                     low=7.5, close=7.90)]
    d = derive_latches(
        fires=fires, bars_by_ticker={"SAME": bars}, entries_by_ticker={},
        horizon_session=date(2026, 5, 5), derivation_session=date(2026, 5, 4))
    assert len(d.latches) == 1
    assert d.latches[0].state == "invalidated"


def test_a_next_session_refire_after_a_fill_does_open_a_second_latch():
    """The discriminator in the other direction: clause (i) must not swallow a
    genuinely new session's fire. A blanket 'same ticker never re-opens' rule
    FAILS this test."""
    from swing.latches.models import EntryRecord
    fires = [
        _fire(821, 40, "NEXT", 10.0, 8.0, "2026-05-04", "2026-05-01T21:00:00"),
        _fire(822, 42, "NEXT", 11.0, 9.0, "2026-05-05", "2026-05-04T17:30:00"),
    ]
    entries = {"NEXT": [EntryRecord(
        trade_id=56, ticker="NEXT", entry_date=date(2026, 5, 4),
        candidate_id=821, entry_price=10.05, shares=5)]}
    d = derive_latches(
        fires=fires, bars_by_ticker={"NEXT": []}, entries_by_ticker=entries,
        horizon_session=date(2026, 5, 6), derivation_session=date(2026, 5, 5))
    assert len(d.latches) == 2
    assert d.latches[0].state == "filled"
    assert d.latches[1].latched_pivot == 11.0     # the NEW fire's own price


# ---------------------------------------------------------------------------
# R6 AT THE EXPIRY TIE -- banked from the item-3a gate to 3b (RD, 2026-08-07).
# ---------------------------------------------------------------------------
def test_a_different_pivot_refire_ON_the_expiry_session_supersedes_not_horizon():
    """R6 conformance at the ONE geometry the shipped fold got wrong.

    RD's ladder puts `superseded` ABOVE `horizon`: a re-fire is an affirmative
    CURRENT fact, so "re-based" must not file as "went stale" -- at the tie as
    everywhere. When a different-pivot re-fire lands EXACTLY on the
    predecessor's `horizon_expiry`, both liveness probes find the horizon
    terminal (the horizon stays inclusive AT the re-fire session), so the
    shipped fold took clause (iii) and let the resolver stamp `horizon`. The
    supersede candidate was never built and its rank never consulted.

    Discriminator, and it is exact: on the pre-fix fold this latch clears
    `horizon` at the same session, so an assertion on the SESSION alone passes
    under both implementations -- only the REASON separates them. The alarm
    severity moves with it (`superseded` is critical-stale, `horizon` is not),
    which is the operator-visible cost of getting it wrong: a resting order
    behind a re-based mandate alarms at `warning` when the duty to cancel it is
    identical to the invalidation case.
    """
    fires = [
        _fire(901, 9, "TIE", 10.00, 8.00, "2026-07-27", "2026-07-24T21:00:00"),
        # 3 sessions after 2026-07-27 is 2026-07-30 -- the expiry itself.
        _fire(902, 12, "TIE", 11.50, 9.20, "2026-07-30", "2026-07-29T21:00:00"),
    ]
    d = derive_latches(
        fires=fires, bars_by_ticker={"TIE": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 31), derivation_session=date(2026, 7, 30),
        horizon_sessions=3)
    assert len(d.latches) == 2
    old_latch, new_latch = d.latches
    assert old_latch.horizon_expiry == date(2026, 7, 30)   # the tie is REAL
    assert old_latch.clear_session == date(2026, 7, 30)
    assert old_latch.clear_reason == "superseded"          # NOT "horizon"
    assert old_latch.state == "superseded"
    # The successor still arms at its OWN frozen values -- an implementation
    # that fixed the reason by dropping the incoming fire would pass the
    # predecessor assertions while silently losing the new mandate.
    assert new_latch.latched_pivot == 11.50
    assert new_latch.anchor == date(2026, 7, 30)
    assert new_latch.state == "armed"


def test_a_same_pivot_refire_ON_the_expiry_session_still_expires():
    """The sibling that BOUNDS the fix, and the shipped behaviour it must not
    disturb. A same-pivot re-fire is not a RE-BASING -- nothing about the
    mandate moved -- so the predecessor genuinely ran out its window and clears
    `horizon`, while the fire opens its own fresh mandate (the re-confirmation
    branch applies only while the latch is LIVE, and at the expiry it is not).

    Discriminator: an over-broad fix that stamps `superseded` on ANY re-fire
    landing on the expiry passes the test above and fails this one.
    """
    fires = [
        _fire(911, 9, "SAMETIE", 10.00, 8.00, "2026-07-27", "2026-07-24T21:00:00"),
        _fire(912, 12, "SAMETIE", 10.00, 8.00, "2026-07-30", "2026-07-29T21:00:00"),
    ]
    d = derive_latches(
        fires=fires, bars_by_ticker={"SAMETIE": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 31), derivation_session=date(2026, 7, 30),
        horizon_sessions=3)
    assert len(d.latches) == 2
    assert d.latches[0].clear_reason == "horizon"
    assert d.latches[1].anchor == date(2026, 7, 30)


def test_an_earlier_invalidation_still_beats_a_later_refire_on_date():
    """The other bound: earliest-date-wins is untouched (L10). The old latch
    died on 2026-07-28; a different-pivot re-fire two sessions later does not
    re-open it to stamp `superseded` over a terminal that had already resolved.

    Discriminator: a fix that builds the supersede candidate unconditionally and
    forgets the DATE comparison returns `superseded` at 2026-07-30 here,
    rewriting a terminal three sessions after it happened.
    """
    fires = [
        _fire(921, 9, "EARLY", 10.00, 8.00, "2026-07-27", "2026-07-24T21:00:00"),
        _fire(922, 12, "EARLY", 11.50, 9.20, "2026-07-30", "2026-07-29T21:00:00"),
    ]
    bars = [DailyBar(session=date(2026, 7, 28), open=8.5, high=8.6,
                     low=7.0, close=7.50)]
    d = derive_latches(
        fires=fires, bars_by_ticker={"EARLY": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 31), derivation_session=date(2026, 7, 30),
        horizon_sessions=3)
    assert len(d.latches) == 2
    assert d.latches[0].clear_reason == "invalidation"
    assert d.latches[0].clear_session == date(2026, 7, 28)
