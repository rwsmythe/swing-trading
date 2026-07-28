"""Terminal-state semantics: RD constraints 1, 2, 4, 5, 6."""
from __future__ import annotations

from datetime import date

from swing.latches.models import DailyBar, EntryRecord, FireRow
from swing.latches.service import derive_latches


def _bar(d, o, h, low, c):
    return DailyBar(session=date.fromisoformat(d), open=o, high=h, low=low, close=c)


FTRE_FIRE = FireRow(
    candidate_id=9500, evaluation_run_id=121, ticker="FTRE", pivot=18.34,
    initial_stop=14.88, action_session_date="2026-07-20",
    run_ts="2026-07-17T17:30:05", pipeline_run_id=135)

# The REAL drifted later rows (runs 122-125, all bucket='watch'). They are NOT
# fires, so they are not in `fires` at all -- but the reader's SQL is what keeps
# them out, and this fixture documents the values a latest-row read would show.
FTRE_DRIFTED_STOPS = (15.195, 15.25, 16.515, 16.515)


def test_ftre_freezes_the_fire_time_stop_not_the_drifted_one():
    """RD constraint 1. A latest-row derivation renders 16.51 -- the value RD
    himself quoted, ~11% early. Only the fire's own row gives 14.88."""
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    latch = d.latches[0]
    assert latch.latched_initial_stop == 14.88
    assert latch.latched_pivot == 18.34
    assert latch.latched_initial_stop not in FTRE_DRIFTED_STOPS


def test_intraday_touch_below_the_stop_that_closes_above_does_not_invalidate():
    """RD constraint 6 -- CLOSES, not intraday touches."""
    bars = [_bar("2026-07-21", 15.0, 15.2, 14.10, 15.05)]   # low 14.10 < 14.88
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 22), derivation_session=date(2026, 7, 21))
    assert d.latches[0].state == "armed"
    assert d.latches[0].clear_reason is None


def test_a_close_below_the_frozen_stop_invalidates_and_stamps_the_session():
    bars = [_bar("2026-07-21", 15.0, 15.2, 14.10, 14.87)]
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 22), derivation_session=date(2026, 7, 21))
    latch = d.latches[0]
    assert latch.state == "invalidated"
    assert latch.clear_reason == "invalidation"
    assert latch.clear_session == date(2026, 7, 21)


def test_a_close_exactly_at_the_stop_does_not_invalidate():
    bars = [_bar("2026-07-21", 15.0, 15.2, 14.10, 14.88)]
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 22), derivation_session=date(2026, 7, 21))
    assert d.latches[0].state == "armed"


def test_a_close_below_the_drifted_stop_but_above_the_frozen_one_does_not_invalidate():
    """The combined constraint-1 x constraint-6 discriminator: 16.00 is below
    the drifted 16.515 and above the frozen 14.88. Only a frozen-stop
    implementation stays armed."""
    bars = [_bar("2026-07-23", 16.5, 16.8, 15.9, 16.00)]
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 24), derivation_session=date(2026, 7, 23))
    assert d.latches[0].state == "armed"


# --- Horizon: sessions, NOT calendar days (the AMN discriminator) -----------
AMN_FIRE = FireRow(
    candidate_id=9276, evaluation_run_id=103, ticker="AMN", pivot=33.48,
    initial_stop=28.81, action_session_date="2026-07-01",
    run_ts="2026-07-01T06:30:23", pipeline_run_id=116)


def test_amn_is_still_armed_where_a_calendar_horizon_would_expire():
    """AMN's real fire geometry (2026-07-01) with the fill withheld. On
    2026-07-31:
      sessions elapsed = 21  -> ARMED under the ruled 30-SESSION horizon
      calendar days    = 30  -> EXPIRED under a 30-CALENDAR-DAY horizon
    A calendar-day implementation FAILS this test."""
    d = derive_latches(
        fires=[AMN_FIRE], bars_by_ticker={"AMN": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 31), derivation_session=date(2026, 7, 31))
    latch = d.latches[0]
    assert latch.state == "armed"
    assert latch.sessions_elapsed == 21
    assert latch.sessions_to_horizon == 9
    assert latch.horizon_expiry == date(2026, 8, 13)


def test_horizon_expires_inclusively_on_the_30th_session():
    d = derive_latches(
        fires=[AMN_FIRE], bars_by_ticker={"AMN": []}, entries_by_ticker={},
        horizon_session=date(2026, 8, 13), derivation_session=date(2026, 8, 13))
    latch = d.latches[0]
    assert latch.state == "horizon_expired"
    assert latch.clear_reason == "horizon"
    assert latch.clear_session == date(2026, 8, 13)
    assert latch.sessions_to_horizon == 0


def test_still_armed_on_the_29th_session():
    d = derive_latches(
        fires=[AMN_FIRE], bars_by_ticker={"AMN": []}, entries_by_ticker={},
        horizon_session=date(2026, 8, 12), derivation_session=date(2026, 8, 12))
    assert d.latches[0].state == "armed"
    assert d.latches[0].sessions_elapsed == 29


def test_ftre_horizon_expiry_is_the_ruled_2026_08_31():
    """NOT the 2026-08-17 RD had recorded from the untraced ~20 (plan A.4).
    A 20-session implementation FAILS here."""
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    assert d.latches[0].horizon_expiry == date(2026, 8, 31)
    assert d.latches[0].sessions_elapsed == 5


def test_the_horizon_tracks_an_injected_window_rather_than_a_literal():
    """Parity binding: passing a different horizon_sessions must move the
    expiry. An implementation that hard-codes 30 (or 20) FAILS."""
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24),
        horizon_sessions=20)
    assert d.latches[0].horizon_expiry == date(2026, 8, 17)


def test_the_20_session_horizon_would_have_expired_ftre_where_30_keeps_it_armed():
    """The gate correction made discriminating (plan G.2). On 2026-08-18 the
    superseded ~20-session horizon has FTRE dead; the RULED 30-session horizon
    still has it armed with 9 sessions left. A 20-session implementation
    reports `horizon_expired` here."""
    kwargs = dict(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": []}, entries_by_ticker={},
        horizon_session=date(2026, 8, 18), derivation_session=date(2026, 8, 17))
    assert derive_latches(**kwargs, horizon_sessions=20).latches[0].state == (
        "horizon_expired")
    ruled = derive_latches(**kwargs).latches[0]
    assert ruled.state == "armed"
    assert ruled.sessions_to_horizon == 9


# --- Fill detection: LATCH-SPECIFIC (RD constraint 4) -----------------------
VSTS_126 = FireRow(
    candidate_id=9999, evaluation_run_id=126, ticker="VSTS", pivot=16.90,
    initial_stop=13.40, action_session_date="2026-07-27",
    run_ts="2026-07-24T17:30:06", pipeline_run_id=140)
TRADE_17 = EntryRecord(trade_id=17, ticker="VSTS", entry_date=date(2026, 6, 25),
                       candidate_id=8851, entry_price=13.61, shares=15)


def test_the_old_closed_vsts_position_does_not_fill_the_new_latch():
    """RD's named live subject. Trade 17 carries candidate_id 8851 (the run-99
    fire); the run-126 latch's candidate set is {9999}."""
    d = derive_latches(
        fires=[VSTS_126], bars_by_ticker={"VSTS": []},
        entries_by_ticker={"VSTS": [TRADE_17]},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    latch = d.latches[0]
    assert latch.state == "armed"
    assert latch.clear_reason is None and latch.clear_trade_id is None


def test_a_null_candidate_id_entry_before_the_anchor_also_does_not_match():
    """The windowed fallback must not reach backwards past the anchor."""
    legacy = EntryRecord(trade_id=4, ticker="VSTS", entry_date=date(2026, 6, 25),
                         candidate_id=None, entry_price=13.61, shares=15)
    d = derive_latches(
        fires=[VSTS_126], bars_by_ticker={"VSTS": []},
        entries_by_ticker={"VSTS": [legacy]},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    assert d.latches[0].state == "armed"


def test_exact_candidate_id_link_fills_its_own_latch():
    fire99 = FireRow(candidate_id=8851, evaluation_run_id=99, ticker="VSTS",
                     pivot=13.56, initial_stop=11.62,
                     action_session_date="2026-06-25",
                     run_ts="2026-06-24T20:06:25", pipeline_run_id=112)
    d = derive_latches(
        fires=[fire99], bars_by_ticker={"VSTS": []},
        entries_by_ticker={"VSTS": [TRADE_17]},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    latch = d.latches[0]
    assert latch.state == "filled"
    assert latch.clear_reason == "fill"
    assert latch.clear_trade_id == 17
    assert latch.clear_session == date(2026, 6, 25)
    assert latch.fill_link_basis == "candidate_id"


def test_windowed_fallback_fills_when_candidate_id_is_null():
    legacy = EntryRecord(trade_id=4, ticker="FTRE", entry_date=date(2026, 7, 22),
                         candidate_id=None, entry_price=18.40, shares=3)
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": []},
        entries_by_ticker={"FTRE": [legacy]},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    assert d.latches[0].state == "filled"
    assert d.latches[0].fill_link_basis == "windowed"


def test_candidate_id_match_dated_before_the_anchor_flags_an_anomaly_not_a_fill():
    weird = EntryRecord(trade_id=77, ticker="FTRE", entry_date=date(2026, 7, 10),
                        candidate_id=9500, entry_price=18.0, shares=1)
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": []},
        entries_by_ticker={"FTRE": [weird]},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    latch = d.latches[0]
    assert latch.state == "armed"
    assert latch.clear_reason is None
    assert latch.fill_link_anomaly is True


def test_fill_beats_invalidation_on_the_same_session():
    """Precedence (plan A.7): a consummated mandate is terminal in the
    strongest sense; the bar's close below the stop becomes the TRADE's
    problem, not the latch's."""
    entry = EntryRecord(trade_id=88, ticker="FTRE", entry_date=date(2026, 7, 21),
                        candidate_id=9500, entry_price=18.40, shares=3)
    bars = [_bar("2026-07-21", 18.4, 18.6, 14.0, 14.10)]
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars},
        entries_by_ticker={"FTRE": [entry]},
        horizon_session=date(2026, 7, 22), derivation_session=date(2026, 7, 21))
    assert d.latches[0].clear_reason == "fill"


def test_invalidation_beats_horizon_on_the_same_session():
    bars = [_bar("2026-07-30", 29.0, 29.5, 28.0, 28.00)]
    d = derive_latches(
        fires=[AMN_FIRE], bars_by_ticker={"AMN": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 30), derivation_session=date(2026, 7, 30))
    assert d.latches[0].clear_reason == "invalidation"


def test_absent_bars_leave_invalidation_unevaluated_and_say_so():
    """A6: never a silent 'not invalidated'."""
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    latch = d.latches[0]
    assert latch.state == "armed"
    assert latch.bars_available is False
    assert latch.bars_through is None


def test_bars_through_reports_archive_staleness():
    bars = [_bar("2026-07-21", 17.9, 18.3, 17.6, 17.91)]
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    assert d.latches[0].bars_available is True
    assert d.latches[0].bars_through == date(2026, 7, 21)


# --- Codex R1-3: overlapping windows ---------------------------------------
def _ovl_fires():
    """Latch 1 fires 2026-06-25 and INVALIDATES 2026-06-30, but its NOMINAL
    horizon_expiry is far later -- so its nominal window overlaps latch 2's."""
    return [
        FireRow(candidate_id=7001, evaluation_run_id=99, ticker="OVL",
                pivot=13.56, initial_stop=11.62,
                action_session_date="2026-06-25",
                run_ts="2026-06-24T20:06:25", pipeline_run_id=112),
        FireRow(candidate_id=7002, evaluation_run_id=103, ticker="OVL",
                pivot=16.90, initial_stop=13.40,
                action_session_date="2026-07-01",
                run_ts="2026-07-01T06:30:23", pipeline_run_id=116),
    ]


_OVL_BARS = [_bar("2026-06-30", 12.0, 12.2, 11.0, 11.50)]   # closes below 11.62


def test_a_legacy_entry_after_latch1_invalidated_belongs_to_latch2_only():
    """The windowed window is bounded by the ACTUAL non-fill terminal
    (2026-06-30), not the nominal horizon (2026-08-06). A nominal-horizon
    implementation credits the 2026-07-05 entry to latch 1 as well."""
    legacy = EntryRecord(trade_id=90, ticker="OVL", entry_date=date(2026, 7, 5),
                         candidate_id=None, entry_price=17.0, shares=4)
    d = derive_latches(
        fires=_ovl_fires(), bars_by_ticker={"OVL": _OVL_BARS},
        entries_by_ticker={"OVL": [legacy]},
        horizon_session=date(2026, 7, 10), derivation_session=date(2026, 7, 10))
    first, second = d.latches
    assert first.state == "invalidated" and first.clear_trade_id is None
    assert second.state == "filled" and second.clear_trade_id == 90
    assert second.fill_link_basis == "windowed"


def test_one_trade_can_fill_at_most_one_latch():
    """Rule (b): the consumed-trade_ids set. A trade appears as `clear_trade_id`
    on AT MOST one latch, however many latches' nominal windows contain it.

    It goes to the latch that actually held the mandate ON the entry date. Here
    latch 1 (pivot 13.56) is superseded on 2026-07-01 by latch 2 (pivot 16.90),
    and the entry lands 2026-07-02 -- i.e. AFTER latch 1 stopped being the live
    mandate. Crediting latch 1 would attribute a fill to a mandate the setup had
    already re-based away from."""
    legacy = EntryRecord(trade_id=91, ticker="OVL", entry_date=date(2026, 7, 2),
                         candidate_id=None, entry_price=17.0, shares=4)
    fires = _ovl_fires()
    d = derive_latches(
        fires=fires, bars_by_ticker={"OVL": []},   # NO bars -> no invalidation
        entries_by_ticker={"OVL": [legacy]},
        horizon_session=date(2026, 7, 10), derivation_session=date(2026, 7, 10))
    filled = [x for x in d.latches if x.clear_trade_id == 91]
    assert len(filled) == 1
    assert filled[0].identity.candidate_id == 7002
    first, second = d.latches
    assert first.state == "superseded" and first.clear_trade_id is None


def test_the_liveness_probe_cannot_see_a_fill_dated_after_the_refire():
    """Codex executing R1. The probe asks "had this latch terminated by session
    S?", so a fill dated AFTER S has not happened yet as of S. An unbounded
    exact-rung match let the probe see a FUTURE fill, conclude the latch was
    already dead at S, and open a SECOND latch where the correct answer is a
    re-confirmation -- the probe and the final resolution disagreeing about the
    same latch.

    Geometry: fire 05-04, SAME-pivot re-fire 05-05, exact trade for the FIRST
    candidate on 05-06. Correct: ONE latch (re-confirmed) that then fills."""
    fires = [
        FireRow(candidate_id=4001, evaluation_run_id=40, ticker="PROBE",
                pivot=10.0, initial_stop=8.0, action_session_date="2026-05-04",
                run_ts="2026-05-01T21:00:00", pipeline_run_id=None),
        FireRow(candidate_id=4002, evaluation_run_id=41, ticker="PROBE",
                pivot=10.0, initial_stop=8.0, action_session_date="2026-05-05",
                run_ts="2026-05-04T17:30:00", pipeline_run_id=None),
    ]
    entries = {"PROBE": [EntryRecord(
        trade_id=93, ticker="PROBE", entry_date=date(2026, 5, 6),
        candidate_id=4001, entry_price=10.05, shares=5)]}
    d = derive_latches(
        fires=fires, bars_by_ticker={"PROBE": []}, entries_by_ticker=entries,
        horizon_session=date(2026, 5, 7), derivation_session=date(2026, 5, 6))
    assert len(d.latches) == 1
    latch = d.latches[0]
    assert latch.identity.candidate_id == 4001
    assert latch.reconfirmation_candidate_ids == (4002,)
    assert latch.state == "filled" and latch.clear_trade_id == 93


def test_an_explicit_candidate_id_beats_a_windowed_claim_on_the_same_trade():
    """Rule (b) precedence: the EXACT rung consumes first."""
    exact = EntryRecord(trade_id=92, ticker="OVL", entry_date=date(2026, 7, 2),
                        candidate_id=7002, entry_price=17.0, shares=4)
    d = derive_latches(
        fires=_ovl_fires(), bars_by_ticker={"OVL": []},
        entries_by_ticker={"OVL": [exact]},
        horizon_session=date(2026, 7, 10), derivation_session=date(2026, 7, 10))
    first, second = d.latches
    assert first.clear_trade_id is None
    assert second.clear_trade_id == 92
    assert second.fill_link_basis == "candidate_id"


# --- Codex R3-3: BAR-WALK BOUNDARIES ---------------------------------------
# The walk's eligible set is EXACTLY {bar : anchor <= bar.session <=
# derivation_session}. Each boundary gets its own discriminating test, because
# an off-by-one at either end passes every interior-case test above.

def test_the_anchor_session_bar_is_included():
    """FTRE's anchor is 2026-07-20. A close below 14.88 ON 07-20 itself must
    invalidate. A walk that starts at anchor+1 leaves the latch `armed` and
    FAILS here."""
    bars = [_bar("2026-07-20", 15.0, 15.2, 14.0, 14.50)]
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 21), derivation_session=date(2026, 7, 20))
    assert d.latches[0].state == "invalidated"
    assert d.latches[0].clear_session == date(2026, 7, 20)


def test_a_bar_before_the_anchor_is_excluded():
    """FTRE's pivot/stop were computed FROM pre-anchor bars; a pre-anchor close
    below the stop is history, not an invalidation of a mandate that did not
    exist yet. A walk that forgets the lower bound FAILS here."""
    bars = [_bar("2026-07-17", 15.0, 15.2, 14.0, 14.00),      # BEFORE the anchor
            _bar("2026-07-20", 17.6, 17.9, 17.4, 17.76)]
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 21), derivation_session=date(2026, 7, 20))
    assert d.latches[0].state == "armed"


def test_a_bar_after_derivation_session_is_excluded_even_when_present():
    """The archive can legitimately hold a bar newer than derivation_session
    (the warm runs at 17:30 for the NEXT session). Judging a latch on a bar the
    operator's session boundary has not reached is a look-ahead. An
    implementation that walks the whole archive FAILS here."""
    bars = [_bar("2026-07-21", 17.9, 18.3, 17.6, 17.91),
            _bar("2026-07-22", 17.7, 18.6, 14.0, 14.00)]     # AFTER the bound
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 22), derivation_session=date(2026, 7, 21))
    assert d.latches[0].state == "armed"
    assert d.latches[0].bars_through == date(2026, 7, 21)


def test_the_same_bar_set_one_session_later_does_invalidate():
    """The paired discriminator for the test above -- proves the 07-22 bar is
    excluded by the BOUND, not silently dropped by the reader."""
    bars = [_bar("2026-07-21", 17.9, 18.3, 17.6, 17.91),
            _bar("2026-07-22", 17.7, 18.6, 14.0, 14.00)]
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 23), derivation_session=date(2026, 7, 22))
    assert d.latches[0].state == "invalidated"
    assert d.latches[0].clear_session == date(2026, 7, 22)


def test_an_invalidating_close_on_the_horizon_expiry_session_beats_horizon():
    """AMN's expiry is 2026-08-13. A close below 28.81 on 08-13 must record
    `invalidation` (the more informative terminal), not `horizon`. An
    implementation that checks the horizon before walking the bars FAILS."""
    bars = [_bar("2026-08-13", 29.0, 29.5, 27.5, 28.00)]
    d = derive_latches(
        fires=[AMN_FIRE], bars_by_ticker={"AMN": bars}, entries_by_ticker={},
        horizon_session=date(2026, 8, 13), derivation_session=date(2026, 8, 13))
    assert d.latches[0].clear_reason == "invalidation"
    assert d.latches[0].clear_session == date(2026, 8, 13)


def test_the_horizon_anchors_on_action_session_not_data_asof():
    """FTRE's horizon is 2026-08-31 == action_session (2026-07-20) + 30
    sessions. Anchoring on data_asof_date (2026-07-17) gives 2026-08-28 and
    FAILS -- and would expire the mandate three sessions early."""
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": []}, entries_by_ticker={},
        horizon_session=date(2026, 8, 28), derivation_session=date(2026, 8, 27))
    assert d.latches[0].state == "armed"          # NOT expired on 08-28
    assert d.latches[0].horizon_expiry == date(2026, 8, 31)


def test_a_superseded_latch_is_terminal_and_distinguishable_from_horizon():
    """RD ledger note: a superseded latch still counts in the denominators but
    its reason must NOT collapse into `horizon`, so 21-B can separate
    'unfilled because the setup re-based' from 'unfilled because it went
    stale'."""
    fires = [
        FireRow(candidate_id=6001, evaluation_run_id=121, ticker="SUP",
                pivot=18.34, initial_stop=14.88,
                action_session_date="2026-07-20",
                run_ts="2026-07-17T17:30:05", pipeline_run_id=135),
        FireRow(candidate_id=6002, evaluation_run_id=125, ticker="SUP",
                pivot=20.19, initial_stop=16.515,
                action_session_date="2026-07-24",
                run_ts="2026-07-23T17:30:05", pipeline_run_id=139),
    ]
    d = derive_latches(
        fires=fires, bars_by_ticker={"SUP": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    old_latch, new_latch = d.latches
    assert old_latch.clear_reason == "superseded"
    assert old_latch.clear_reason != "horizon"
    assert old_latch.state == "superseded"
    assert old_latch.clear_session == date(2026, 7, 24)
    assert old_latch.latched_pivot == 18.34       # its OWN frozen values kept
    assert new_latch.state == "armed"
    assert new_latch.latched_pivot == 20.19


def test_a_zone_escape_does_not_clear_the_latch():
    """Section A.7.1 / RD gate: the resting order at the cap remains VALID and
    fills on a pullback, so clearing would desynchronize the panel from a real
    broker order. Price far above the zone cap, no invalidating close: the
    latch stays ARMED."""
    bars = [_bar("2026-07-24", 19.77, 20.09, 19.25, 19.52)]   # >> cap 18.89
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": bars}, entries_by_ticker={},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    assert d.latches[0].state == "armed"
    assert d.latches[0].clear_reason is None


def test_the_probe_ignores_facts_from_the_refire_session_itself():
    """Codex executing R2. The liveness question is asked at the moment the new
    fire EXISTS -- the evening before its action session -- so that session's
    own fill/close has not happened yet and must not decide that the old latch
    was already dead.

    Geometry: fire 05-04, SAME-pivot re-fire 05-05, invalidating close ON 05-05.
    Correct: ONE re-confirmed latch that then invalidates. An implementation
    that lets the re-fire session's own bar decide the probe produces TWO
    latches -- a duplicate mandate for a setup that merely held then broke."""
    fires = [
        FireRow(candidate_id=5001, evaluation_run_id=40, ticker="SAMEDAY",
                pivot=10.0, initial_stop=8.0, action_session_date="2026-05-04",
                run_ts="2026-05-01T21:00:00", pipeline_run_id=None),
        FireRow(candidate_id=5002, evaluation_run_id=41, ticker="SAMEDAY",
                pivot=10.0, initial_stop=8.0, action_session_date="2026-05-05",
                run_ts="2026-05-04T17:30:00", pipeline_run_id=None),
    ]
    bars = [_bar("2026-05-05", 9.0, 9.2, 7.5, 7.90)]     # closes below 8.0
    d = derive_latches(
        fires=fires, bars_by_ticker={"SAMEDAY": bars}, entries_by_ticker={},
        horizon_session=date(2026, 5, 6), derivation_session=date(2026, 5, 5))
    assert len(d.latches) == 1
    latch = d.latches[0]
    assert latch.identity.candidate_id == 5001
    assert latch.reconfirmation_candidate_ids == (5002,)
    assert latch.state == "invalidated"
    assert latch.clear_session == date(2026, 5, 5)


def test_a_horizon_that_closes_on_the_refire_session_still_opens_a_new_latch():
    """The paired discriminator: the horizon stays INCLUSIVE at the re-fire
    session even though bars and fills do not. A mandate whose window closes at
    S is already dead for S, so a fire for S opens a genuinely new latch. An
    implementation that pushed the horizon back a session too would re-confirm
    here and keep a dead mandate alive."""
    fires = [
        FireRow(candidate_id=5101, evaluation_run_id=40, ticker="HZN",
                pivot=10.0, initial_stop=8.0, action_session_date="2026-07-01",
                run_ts="2026-06-30T21:00:00", pipeline_run_id=None),
        # 2026-07-01 + 30 sessions == 2026-08-13 (the AMN geometry).
        FireRow(candidate_id=5102, evaluation_run_id=41, ticker="HZN",
                pivot=10.0, initial_stop=8.0, action_session_date="2026-08-13",
                run_ts="2026-08-12T17:30:00", pipeline_run_id=None),
    ]
    d = derive_latches(
        fires=fires, bars_by_ticker={"HZN": []}, entries_by_ticker={},
        horizon_session=date(2026, 8, 13), derivation_session=date(2026, 8, 13))
    assert len(d.latches) == 2
    assert d.latches[0].state == "horizon_expired"
    assert d.latches[1].state == "armed"


# --- Codex executing R3: the windowed rung must verify the PRICE ------------
def test_a_null_candidate_trade_at_an_unrelated_price_does_not_fill_the_latch():
    """Codex executing R3 CRITICAL. `trades.candidate_id` is nullable (migration
    0021 backfilled every pre-v21 row to NULL), so an unrelated manual/legacy
    buy in the SAME ticker within the window would clear the mandate on date
    proximity alone -- marking it `filled` and silencing the order alarms for a
    fire the operator never acted on. That is exactly what RD constraint 4
    forbids: "a pre-existing position or unrelated order in the same ticker must
    not read as this latch's fill".

    FTRE's mandate is a BUY STOP at 18.34 with a cap at 18.89; a fill at 10.00
    cannot have come from it."""
    unrelated = EntryRecord(trade_id=91, ticker="FTRE", entry_date=date(2026, 7, 21),
                            candidate_id=None, entry_price=10.00, shares=3)
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": []},
        entries_by_ticker={"FTRE": [unrelated]},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    latch = d.latches[0]
    assert latch.state == "armed"
    assert latch.clear_reason is None and latch.clear_trade_id is None


def test_a_null_candidate_trade_priced_above_the_cap_does_not_fill_the_latch():
    """A gap THROUGH the cap is precisely what the cap exists to refuse, so a
    fill above it did not come from this mandate."""
    above = EntryRecord(trade_id=92, ticker="FTRE", entry_date=date(2026, 7, 21),
                        candidate_id=None, entry_price=19.50, shares=3)
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": []},
        entries_by_ticker={"FTRE": [above]},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    assert d.latches[0].state == "armed"


def test_a_null_candidate_trade_with_no_price_does_not_fill_the_latch():
    """An unverifiable price must not clear a live mandate: the windowed rung is
    a heuristic for legacy rows, and a heuristic cannot clear on evidence it
    cannot check."""
    priceless = EntryRecord(trade_id=93, ticker="FTRE", entry_date=date(2026, 7, 21),
                            candidate_id=None, entry_price=None, shares=3)
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": []},
        entries_by_ticker={"FTRE": [priceless]},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    assert d.latches[0].state == "armed"


def test_an_exact_candidate_id_link_fills_regardless_of_price():
    """The paired discriminator: an EXPLICIT link is authoritative, so the price
    band must NOT be applied to the exact rung. Over-tightening here would
    silently stop recognising real fills that slipped or gapped."""
    slipped = EntryRecord(trade_id=94, ticker="FTRE", entry_date=date(2026, 7, 21),
                          candidate_id=9500, entry_price=25.00, shares=3)
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": []},
        entries_by_ticker={"FTRE": [slipped]},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    latch = d.latches[0]
    assert latch.state == "filled"
    assert latch.clear_trade_id == 94
    assert latch.fill_link_basis == "candidate_id"


def test_a_null_candidate_trade_inside_the_zone_still_fills():
    """And the in-band case must still work, or the windowed rung is dead code
    and the legacy NULL-candidate_id rows it exists for are never matched."""
    in_band = EntryRecord(trade_id=95, ticker="FTRE", entry_date=date(2026, 7, 21),
                          candidate_id=None, entry_price=18.40, shares=3)
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": []},
        entries_by_ticker={"FTRE": [in_band]},
        horizon_session=date(2026, 7, 27), derivation_session=date(2026, 7, 24))
    assert d.latches[0].state == "filled"
    assert d.latches[0].fill_link_basis == "windowed"


def test_a_close_below_the_stop_AFTER_the_horizon_does_not_overwrite_expiry():
    """Codex executing R4. Once the mandate is DEAD, a later close below the
    stop is not an invalidation OF IT. Without a horizon cap on the bar walk the
    latch renders `invalidated` at the later session instead of
    `horizon_expired` at the expiry -- which also moves the clear date and
    ESCALATES a stale resting order from `warning` to `critical` for a mandate
    that had already lapsed.

    AMN fires 2026-07-01 and expires 2026-08-13; the break lands 2026-08-14."""
    bars = [_bar("2026-08-14", 29.0, 29.5, 27.5, 28.00)]   # below the 28.81 stop
    d = derive_latches(
        fires=[AMN_FIRE], bars_by_ticker={"AMN": bars}, entries_by_ticker={},
        horizon_session=date(2026, 8, 14), derivation_session=date(2026, 8, 14))
    latch = d.latches[0]
    assert latch.state == "horizon_expired"
    assert latch.clear_reason == "horizon"
    assert latch.clear_session == date(2026, 8, 13)


def test_a_sub_cent_close_artifact_does_not_invalidate_a_live_mandate():
    """Codex executing R8. A parquet float artifact -- a close of 14.879999999
    against a frozen 14.88 stop -- would CLEAR the mandate under a raw float
    comparison while the panel renders BOTH numbers as 14.88, and clearing
    silences the no-resting-order alarm. Every other price comparison in this
    arc rounds to display precision; this one now does too, and it errs in the
    SAFE direction (a marginal mandate stays armed rather than dying silently).
    A genuinely-below close still invalidates."""
    artifact = [_bar("2026-07-21", 15.0, 15.2, 14.10, 14.879999999)]
    d = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": artifact}, entries_by_ticker={},
        horizon_session=date(2026, 7, 22), derivation_session=date(2026, 7, 21))
    assert d.latches[0].state == "armed"

    genuine = [_bar("2026-07-21", 15.0, 15.2, 14.10, 14.8749)]   # rounds to 14.87
    d2 = derive_latches(
        fires=[FTRE_FIRE], bars_by_ticker={"FTRE": genuine}, entries_by_ticker={},
        horizon_session=date(2026, 7, 22), derivation_session=date(2026, 7, 21))
    assert d2.latches[0].state == "invalidated"


def test_a_refire_on_the_expiry_session_does_not_arm_over_a_same_session_fill():
    """Codex executing R11. An interaction between two EARLIER fixes.

    The liveness probe deliberately cannot see the re-fire session's own fill
    (R6), but the horizon stays inclusive at that session -- so a latch expiring
    ON the re-fire session reads "dead", a new mandate arms, and the FINAL
    resolution (which CAN see the fill, R2) then resolves the SAME latch to
    `filled` on that very session. The operator would be holding the position
    AND be told to place an order for it: a double-buy instruction.

    Geometry: fire 2026-07-01 (expires 2026-08-13), re-fire 2026-08-13, and a
    trade linked to the OLD candidate dated 2026-08-13."""
    fires = [
        FireRow(candidate_id=8001, evaluation_run_id=40, ticker="EXP",
                pivot=33.48, initial_stop=28.81, action_session_date="2026-07-01",
                run_ts="2026-06-30T21:00:00", pipeline_run_id=None),
        FireRow(candidate_id=8002, evaluation_run_id=41, ticker="EXP",
                pivot=40.00, initial_stop=35.00, action_session_date="2026-08-13",
                run_ts="2026-08-12T17:30:00", pipeline_run_id=None),
    ]
    entries = {"EXP": [EntryRecord(
        trade_id=96, ticker="EXP", entry_date=date(2026, 8, 13),
        candidate_id=8001, entry_price=33.60, shares=5)]}
    d = derive_latches(
        fires=fires, bars_by_ticker={"EXP": []}, entries_by_ticker=entries,
        horizon_session=date(2026, 8, 13), derivation_session=date(2026, 8, 13))
    assert len(d.latches) == 1, "a second mandate must not arm over the fill"
    latch = d.latches[0]
    assert latch.state == "filled" and latch.clear_trade_id == 96
    assert latch.reconfirmation_candidate_ids == (8002,)
    assert not any(x.is_live for x in d.latches)


def test_an_expiry_session_refire_WITHOUT_a_fill_still_opens_a_new_latch():
    """The paired discriminator: the suppression is keyed on the FILL, not on
    the expiry. Without a fill the re-fire opens a genuinely new mandate (the
    R6 behaviour), or a real setup would be silently dropped."""
    fires = [
        FireRow(candidate_id=8101, evaluation_run_id=40, ticker="EXP2",
                pivot=33.48, initial_stop=28.81, action_session_date="2026-07-01",
                run_ts="2026-06-30T21:00:00", pipeline_run_id=None),
        FireRow(candidate_id=8102, evaluation_run_id=41, ticker="EXP2",
                pivot=40.00, initial_stop=35.00, action_session_date="2026-08-13",
                run_ts="2026-08-12T17:30:00", pipeline_run_id=None),
    ]
    d = derive_latches(
        fires=fires, bars_by_ticker={"EXP2": []}, entries_by_ticker={},
        horizon_session=date(2026, 8, 13), derivation_session=date(2026, 8, 13))
    assert len(d.latches) == 2
    assert d.latches[0].state == "horizon_expired"
    assert d.latches[1].state == "armed"


def test_a_different_pivot_refire_does_not_supersede_over_a_real_fill():
    """Codex executing R12 CRITICAL. The R11 fix guarded the horizon path but
    NOT the supersede path: branch (b) stamped `superseded` immediately and so
    never ran the final resolution that can see the re-fire session's fill.

    Old fire 2026-07-20, DIFFERENT-pivot re-fire 2026-07-21, and an exact
    candidate_id fill for the OLD candidate dated 2026-07-21. Superseding there
    leaves the old latch `superseded`, the new one `armed`, and the panel
    telling the operator to buy despite an actual filled position."""
    fires = [
        FireRow(candidate_id=8201, evaluation_run_id=121, ticker="SUPF",
                pivot=18.34, initial_stop=14.88, action_session_date="2026-07-20",
                run_ts="2026-07-17T17:30:05", pipeline_run_id=None),
        FireRow(candidate_id=8202, evaluation_run_id=122, ticker="SUPF",
                pivot=20.19, initial_stop=16.515, action_session_date="2026-07-21",
                run_ts="2026-07-20T17:30:05", pipeline_run_id=None),
    ]
    entries = {"SUPF": [EntryRecord(
        trade_id=97, ticker="SUPF", entry_date=date(2026, 7, 21),
        candidate_id=8201, entry_price=18.40, shares=3)]}
    d = derive_latches(
        fires=fires, bars_by_ticker={"SUPF": []}, entries_by_ticker=entries,
        horizon_session=date(2026, 7, 22), derivation_session=date(2026, 7, 21))
    assert len(d.latches) == 1, "a second mandate must not arm over the fill"
    latch = d.latches[0]
    assert latch.state == "filled" and latch.clear_trade_id == 97
    assert latch.reconfirmation_candidate_ids == (8202,)
    assert not any(x.is_live for x in d.latches)


def test_a_different_pivot_refire_WITHOUT_a_fill_still_supersedes():
    """The paired discriminator: the reversal is keyed on a REAL fill, so the
    ordinary supersede path is untouched."""
    fires = [
        FireRow(candidate_id=8301, evaluation_run_id=121, ticker="SUPG",
                pivot=18.34, initial_stop=14.88, action_session_date="2026-07-20",
                run_ts="2026-07-17T17:30:05", pipeline_run_id=None),
        FireRow(candidate_id=8302, evaluation_run_id=122, ticker="SUPG",
                pivot=20.19, initial_stop=16.515, action_session_date="2026-07-21",
                run_ts="2026-07-20T17:30:05", pipeline_run_id=None),
    ]
    d = derive_latches(
        fires=fires, bars_by_ticker={"SUPG": []}, entries_by_ticker={},
        horizon_session=date(2026, 7, 22), derivation_session=date(2026, 7, 21))
    assert [x.state for x in d.latches] == ["superseded", "armed"]
