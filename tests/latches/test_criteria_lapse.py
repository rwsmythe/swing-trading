"""T4 -- the `criteria_lapsed` streak, conjuncts and counterfactual (item 3b).

**EVERY NEGATIVE RULE TEST ASSERTS THE COUNTERFACTUAL, NOT MERELY "IT DID NOT
CLEAR" (RD's standing arm-flag requirement, attached at his own ruling).** This
is the single most dangerous interaction the report-only framing introduced: a
test whose only assertion is *the latch did not clear by `criteria_lapsed`*
passes under the shipped default NO MATTER WHAT THE CONJUNCTS DO, because the
flag suppresses the terminal regardless. It would have silently voided T4.1 --
the FTRE founding case -- under the naive gate-only rule the whole amendment
exists to reject.

So each negative test asserts `lapse_qualifying_session is None` AND
`lapse_would_clear_session is None` -- the hypothetical a wrong implementation
would have produced -- and the founding case runs BOTH ARMED AND UNARMED.

THE FIXTURE BASELINE, stated once because every value here decides an outcome:
`adr_pct = 3.0`, `min_widening_adr = 1.0`, `min_widening_pct = 2.0`, `N = 5`,
pivot 100 -> the floor is `max(1.0 x 3% x 100, 2% x 100) = $3.00`. Unless a test
says otherwise `high == close` on every bar, so the stated closes fully
determine 2a; the archive is COMPLETE over every interval exercised;
`initial_stop = 1.00` (BELOW every close in every fixture, or a fixture would
pass "did not clear by criteria_lapsed" because it INVALIDATED); no entry
records; and the horizon is far beyond the window.
"""
from __future__ import annotations

from datetime import date

import pytest

from swing.evaluation.dates import session_offset
from swing.latches.models import (
    LATCH_LAPSE_DIAGNOSTIC_FIELDS,
    DailyBar,
    EntryRecord,
    FireRow,
    Latch,
    SessionStructuralVerdict,
)
from swing.latches.service import derive_latches, materiality_floor

ANCHOR = date(2026, 7, 27)


def _sessions(n: int, *, start: date = ANCHOR) -> list[date]:
    out = [start]
    while len(out) < n:
        out.append(session_offset(out[-1], 1))
    return out


def _fire(pivot=100.0, stop=1.00, adr_pct=3.0, cid=8851, ticker="TST",
          anchor: date = ANCHOR):
    return FireRow(
        candidate_id=cid, evaluation_run_id=126, ticker=ticker, pivot=pivot,
        initial_stop=stop, action_session_date=anchor.isoformat(),
        run_ts="2026-07-24T17:30:11", pipeline_run_id=140, adr_pct=adr_pct)


def _bars(closes, *, highs=None, start: date = ANCHOR):
    days = _sessions(len(closes), start=start)
    highs = list(closes) if highs is None else list(highs)
    return [
        DailyBar(session=d, open=c, high=h, low=min(c, h), close=c)
        for d, c, h in zip(days, closes, highs, strict=True)
    ]


def _verdicts(classifications, *, start: date = ANCHOR):
    """`F` failed, `P` passed, `U` unverifiable(absent)."""
    days = _sessions(len(classifications), start=start)
    out = []
    for d, code in zip(days, classifications, strict=True):
        if code == "F":
            out.append(SessionStructuralVerdict(
                action_session=d, classification="FAILED"))
        elif code == "P":
            out.append(SessionStructuralVerdict(
                action_session=d, classification="PASSED"))
        else:
            out.append(SessionStructuralVerdict(
                action_session=d, classification="UNVERIFIABLE",
                cause="absent"))
    return tuple(out)


def _derive(*, fire=None, closes=(), highs=None, verdicts=(), armed=False,
            sessions=5, adr=1.0, pct=2.0, entries=(), bar_status="ok",
            derivation_session=None, extra_bars=(), extra_fires=(),
            start: date = ANCHOR):
    fire = fire or _fire(anchor=start)
    bars = list(_bars(closes, highs=highs, start=start)) + list(extra_bars)
    last = bars[-1].session if bars else ANCHOR
    ds = derivation_session or last
    return derive_latches(
        fires=[fire, *extra_fires],
        bars_by_ticker={fire.ticker: bars},
        entries_by_ticker={fire.ticker: list(entries)},
        horizon_session=session_offset(ds, 1),
        derivation_session=ds,
        horizon_sessions=200,
        bar_status_by_ticker={fire.ticker: bar_status},
        structural_verdicts_by_ticker={fire.ticker: verdicts},
        criteria_lapse_armed=armed,
        criteria_lapse_sessions=sessions,
        criteria_lapse_min_widening_adr=adr,
        criteria_lapse_min_widening_pct=pct,
    )


# The canonical QUALIFYING path (pivot 100: nothing reaches it, ends at its low,
# widens $12 >> the $3.00 floor) and the canonical NON-qualifying one (ends
# above its low). Tests about the STREAK rather than the conjuncts use the
# qualifying path, so their asserted outcome is reached for the reason under
# test.
QUALIFYING = [98.0, 95.0, 92.0, 89.0, 86.0]
NON_QUALIFYING = [98.0, 95.0, 92.0, 89.0, 97.0]


def _assert_no_hypothetical(latch: Latch):
    """The COUNTERFACTUAL assertion every negative test makes.

    Asserting only `clear_reason != "criteria_lapsed"` would pass under the
    shipped default regardless of the conjuncts -- the vacuous-negative class
    arriving through a feature flag.
    """
    assert latch.lapse_qualifying_session is None
    assert latch.lapse_would_clear_session is None


# ===========================================================================
# T4.20a -- the roster is EXACT
# ===========================================================================
def test_the_diagnostic_roster_is_the_exact_eleven_and_all_are_real_fields():
    """T4.20a. Without it, the armed/unarmed iteration below walks a roster that
    can itself omit the newest field -- which is how a diagnostic goes missing
    from the dataclass, the roster and the comparison at the same time."""
    from dataclasses import fields

    assert set(LATCH_LAPSE_DIAGNOSTIC_FIELDS) == {
        "lapse_failed_sessions", "lapse_unverifiable_sessions",
        "lapse_unverifiable_causes", "lapse_conflicted_sessions",
        "lapse_failed_count", "lapse_unchecked_count",
        "lapse_unverifiable_tail", "directional_evaluable",
        "directional_block_reason", "lapse_qualifying_session",
        "lapse_would_clear_session"}
    assert len(LATCH_LAPSE_DIAGNOSTIC_FIELDS) == 11
    real = {f.name for f in fields(Latch)}
    assert set(LATCH_LAPSE_DIAGNOSTIC_FIELDS) <= real


# ===========================================================================
# T4.1 -- THE FTRE COUNTEREXAMPLE. NOT DROPPABLE (L3).
# ===========================================================================
def test_FTRE_the_founding_case_never_lapses_ARMED_OR_UNARMED():
    """T4.1 -- the case RD's own amendment says the obvious repair would have
    DESTROYED, reproduced from the live rows.

    Quoted verbatim from his amendment, section "THE TRAP THAT KILLS THE
    OBVIOUS FIX":

        The obvious repair -- "clear after N sessions of failing the A+ gate"
        -- **would have destroyed the founding case.** Measured on the live
        rows:

        | | FTRE (pivot 18.34) | VSTS (pivot 16.90) |
        |---|---|---|
        | fire | aplus, -3.2% | aplus, -7.8% |
        | +1 | watch, -3.3% | watch, -9.2% |
        | +2 | watch, -2.3% | watch, -9.1% |
        | +3 | watch, **+0.8% ABOVE** | watch, -11.7% |
        | +4 | watch, +6.3% above | off-screen |

        **FTRE fell out of A+ on 07-20 and stayed `watch` for EIGHT
        consecutive sessions -- while advancing through its pivot and running
        to 20.70.** A 5-session criteria rule clears it around 07-27, four days
        before the operator's actual fill. It destroys the exact trade the
        latch posture exists to protect.

        The reason is structural and I should have seen it before proposing the
        rule: **a name that breaks out and runs MECHANICALLY fails the A+
        criteria** -- no longer tight, no longer near the 20MA, no longer in a
        base. **Success and decay are indistinguishable in the criteria.** Only
        the price trajectory separates them.

    WHAT THIS FIXTURE ACTUALLY DISCRIMINATES, stated exactly because an earlier
    draft over-claimed it: the streak DOES reach 5, so a NAIVE GATE-ONLY rule
    (no directional conjunct at all) clears three sessions before the fill.
    That is RD's counterexample and this pins it. It does NOT discriminate
    lifetime-vs-window 2a or endpoint-vs-ends-at-low 2b -- T4.6 and T4.7 do,
    which is why they are separately non-droppable.

    IT RUNS BOTH ARMED AND UNARMED. Unarmed alone would pass under the naive
    rule the amendment exists to reject, because the flag suppresses the
    terminal either way -- RD's own words: it would have been his SECOND
    vacuous FTRE acceptance test.
    """
    fire = _fire(pivot=18.34, stop=14.88, adr_pct=5.122, ticker="FTRE")
    # Real archive bars, by their OWN date. 07-22 closes 18.49 -- ABOVE the
    # 18.34 pivot -- which is what makes lifetime 2a permanently refuse.
    closes = [17.73, 17.91, 18.49, 19.50, 19.52, 19.20, 20.70, 20.40, 19.08,
              19.17]
    # ABSENT on 07-27 and 07-30 (runs 126 and 129 evaluated 56 and 61 tickers
    # and neither included FTRE), so the founding case exercises the
    # absent-session rule too, not only the directional conjunct.
    verdicts = _verdicts("FFFFUFFUFF")
    for armed in (False, True):
        d = _derive(fire=fire, closes=closes, verdicts=verdicts, armed=armed)
        latch = d.latches[0]
        assert latch.clear_reason != "criteria_lapsed", armed
        # The streak DOES reach 5 -- so this is not passing because the gate
        # rule never fired; it is the DIRECTIONAL conjunct refusing.
        assert latch.lapse_failed_count >= 5, armed
        _assert_no_hypothetical(latch)


def test_FTRE_clears_by_FILL_on_the_corrected_entry_date():
    """The other half of the founding case: it terminated by the operator's own
    buy, not by anything the framework did.

    The entry date is the ITEM-5-CORRECTED 2026-07-31 (the D31 auto-fill defect
    wrote the order's ENTERED date, 07-23, instead of its EXECUTION date). That
    is also what makes RD's 'four days before the operator's actual fill'
    arithmetic come out.
    """
    fire = _fire(pivot=18.34, stop=14.88, adr_pct=5.122, ticker="FTRE")
    closes = [17.73, 17.91, 18.49, 19.50, 19.52, 19.20, 20.70, 20.40, 19.08,
              19.17]
    entry = EntryRecord(trade_id=19, ticker="FTRE",
                        entry_date=date(2026, 7, 31), candidate_id=8851,
                        entry_price=18.80, shares=5)
    d = _derive(fire=fire, closes=closes, verdicts=_verdicts("FFFFUFFUFF"),
                armed=True, entries=[entry])
    latch = d.latches[0]
    assert latch.clear_reason == "fill"
    assert latch.clear_session == date(2026, 7, 31)


# ===========================================================================
# T4.2 -- THE VSTS CASE (the motivating geometry)
# ===========================================================================
def test_VSTS_clears_at_N3_and_does_NOT_at_the_shipped_N5():
    """T4.2. Both assertions, pinning the CONFIG binding as well as the rule.

    The post-anchor HIGHS are stated as literals rather than left to runtime
    discovery, because a binding acceptance oracle may not be: 15.85 / 15.74 /
    15.61 / 15.32 / 14.74, every one BELOW the 16.90 pivot -- so the OQ-14 HIGH
    ruling does not change VSTS's expected result.

    At N=3 the bar-dated window 15.36 -> 14.59 widens $0.77 against a floor of
    max(1.0 x 4.021% x 16.90, 2% x 16.90) = max(0.6796, 0.338) = $0.68. It
    passes materiality by 13% -- RD's own note that the multiple is a LIVE lever
    on the very case that produced the amendment.
    """
    fire = _fire(pivot=16.90, stop=1.00, adr_pct=4.021, ticker="VSTS")
    closes = [15.35, 15.36, 14.92, 14.59, 14.46]
    highs = [15.85, 15.74, 15.61, 15.32, 14.74]
    verdicts = _verdicts("PFFFU")     # fire session passes, then 3 failures
    at3 = _derive(fire=fire, closes=closes, highs=highs, verdicts=verdicts,
                  sessions=3).latches[0]
    assert at3.lapse_would_clear_session == _sessions(4)[3]
    at5 = _derive(fire=fire, closes=closes, highs=highs, verdicts=verdicts,
                  sessions=5).latches[0]
    assert at5.clear_reason != "criteria_lapsed"
    assert at5.lapse_failed_count == 3        # frozen at 3 of 5
    _assert_no_hypothetical(at5)


# ===========================================================================
# T4.3 / T4.5 -- the streak's domain
# ===========================================================================
def test_absent_sessions_neither_advance_nor_reset_the_streak():
    """T4.3 -- OQ-17's PAUSE, and the reason is structural rather than a
    preference: BREAK would make an off-screen name's real accumulated decay
    evidence vanish on the day it left the screen.

    Discriminator, both directions: counting CALENDAR sessions clears earlier;
    RESETTING on absence never clears at all.
    """
    d = _derive(closes=[98.0, 96.0, 94.0, 92.0, 90.0],
                verdicts=_verdicts("FUFUF"), sessions=3)
    latch = d.latches[0]
    # the THIRD FAILED session, not the third calendar one
    assert latch.lapse_would_clear_session == _sessions(5)[4]
    assert latch.lapse_failed_count == 3
    assert latch.lapse_unchecked_count == 2


def test_a_PASSED_session_resets_the_streak_to_zero():
    """T4.5. A later re-confirmation is BY CONSTRUCTION a PASSED session, so no
    special case is needed and none should be written."""
    d = _derive(closes=[98.0, 95.0, 92.0, 89.0, 86.0],
                verdicts=_verdicts("FFPFF"), sessions=3)
    latch = d.latches[0]
    assert latch.clear_reason != "criteria_lapsed"
    assert latch.lapse_failed_count == 2        # only the two AFTER the pass
    _assert_no_hypothetical(latch)


# ===========================================================================
# T4.6 / T4.7 / T4.14 -- the conjuncts. NOT DROPPABLE (L3).
# ===========================================================================
def test_conjunct_2a_IS_A_LIFETIME_PROPERTY_not_a_window_one():
    """T4.6 -- NOT DROPPABLE. Amendment A (OQ-12 RATIFIED).

    Closes 95, 97, 101, 99, 98, 97, 96, 95 against a pivot of 100, every session
    structurally failing, N=5.

    Discriminator: under a WINDOW-scoped 2a the 101 ages OUT and the trailing
    five (99, 98, 97, 96, 95) satisfy clauses 2-3 with a widening of $4.00 --
    above the $3.00 floor -- so the wrong implementation genuinely CLEARS. The
    widening is stated because a fixture falling under the floor would refuse
    under BOTH implementations and discriminate nothing.

    The failure it prevents is the founding class displaced a week: a stock that
    broke out successfully and is now pulling back would clear a few sessions
    later, withdrawing an entry that is still working.
    """
    d = _derive(closes=[95.0, 97.0, 101.0, 99.0, 98.0, 97.0, 96.0, 95.0],
                verdicts=_verdicts("FFFFFFFF"), armed=True)
    latch = d.latches[0]
    assert latch.clear_reason != "criteria_lapsed"
    assert latch.lapse_failed_count == 8        # the streak DID reach N
    _assert_no_hypothetical(latch)


def test_conjunct_2b_REQUIRES_THE_WINDOW_TO_END_AT_ITS_OWN_LOW():
    """T4.7 -- NOT DROPPABLE. Amendment B (OQ-13 RATIFIED).

    Closes 95.00, 80.00, 85.00, 88.00, 90.00 against a pivot of 100.

    Discriminator: an ENDPOINT-ONLY rule sees 90.00 < 95.00 with a widening of
    $5.00 -- above the $3.00 floor -- and clears a stock that has rallied 12.5%
    off its low. The correct rule refuses because 90.00 is not the window
    minimum (80.00 is). A rally off the low is a setup RE-ASSERTING, which is
    exactly what the conjunct exists to protect.

    (The earlier 95.00 ... 94.99 fixture stopped discriminating the moment
    clause 4 was added: a one-cent endpoint difference is refused by materiality
    anyway, so correct and incorrect implementations both refused.)
    """
    d = _derive(closes=[95.0, 80.0, 85.0, 88.0, 90.0],
                verdicts=_verdicts("FFFFF"), armed=True)
    latch = d.latches[0]
    assert latch.clear_reason != "criteria_lapsed"
    _assert_no_hypothetical(latch)


def test_the_scan_is_ROLLING_not_one_shot():
    """T4.8. Pivot 100, N=3, all failing, closes 90, 84, 92, 88, 80.

    At the third failure the window (90, 84, 92) does not end at its low -> no
    clear. Two sessions later (92, 88, 80) ends at its low and widens $12 -> it
    clears THERE.

    Discriminator: a one-shot implementation, tested only when the counter first
    reaches N, never clears at all.
    """
    d = _derive(closes=[90.0, 84.0, 92.0, 88.0, 80.0],
                verdicts=_verdicts("FFFFF"), sessions=3)
    latch = d.latches[0]
    assert latch.lapse_would_clear_session == _sessions(5)[4]


def test_the_clear_date_is_STABLE_when_several_windows_qualify():
    """T4.11. Closes 98, 95, 92, 89, 86, 83: the D1-D5 window qualifies AND so
    does D2-D6.

    Discriminator: a literal 'last N failures' implementation returns D6 and the
    clear date walks FORWARD every session -- so re-deriving tomorrow moves a
    terminal that already happened.
    """
    closes = [98.0, 95.0, 92.0, 89.0, 86.0, 83.0]
    days = _sessions(6)
    at5 = _derive(closes=closes[:5], verdicts=_verdicts("FFFFF")).latches[0]
    at6 = _derive(closes=closes, verdicts=_verdicts("FFFFFF")).latches[0]
    assert at5.lapse_would_clear_session == days[4]
    assert at6.lapse_would_clear_session == days[4]   # UNMOVED a session later


def test_materiality_both_terms_of_the_floor():
    """T4.14 -- NOT DROPPABLE (OQ-10's two-term floor).

    (a) THE ADR TERM BINDS: pivot 100, adr_pct 4.0 -> floor max(4.00, 2.00) =
        $4.00; closes 99.00, 99.04, 99.03, 99.02, 98.99 widen ONE CENT.
        Discriminator: without clause 4 this satisfies 2a and clauses 2-3, and a
        one-cent "decay" withdraws the mandate from a tight consolidation
        immediately beneath the pivot -- the most constructive pre-breakout
        shape there is.

    (b) THE PIVOT-RELATIVE TERM BINDS, and an ADR-ONLY floor FAILS IT: pivot
        100, adr_pct 0.40 -> ADR term $0.40, pivot term $2.00, floor $2.00;
        closes 99.80, 99.90, 99.75, 99.60, 99.30 widen $0.50.
        Discriminator: an ADR-only floor of $0.40 is EXCEEDED by $0.50 and
        CLEARS a sub-1% consolidation sitting under its pivot the session before
        it could break to 103.
    """
    a = _derive(fire=_fire(adr_pct=4.0),
                closes=[99.00, 99.04, 99.03, 99.02, 98.99],
                verdicts=_verdicts("FFFFF"), armed=True).latches[0]
    assert a.clear_reason != "criteria_lapsed"
    _assert_no_hypothetical(a)

    b = _derive(fire=_fire(adr_pct=0.40),
                closes=[99.80, 99.90, 99.75, 99.60, 99.30],
                verdicts=_verdicts("FFFFF"), armed=True).latches[0]
    assert b.clear_reason != "criteria_lapsed"
    _assert_no_hypothetical(b)


def test_the_materiality_boundary_rounds_AFTER_the_subtraction():
    """T4.17. The float artifact is the point, and a generic 98.00 -> 95.00 pair
    would evaluate identically under both implementations and prove nothing.

    Series 64.02, 63.50, 63.00, 62.00, 61.02 -- all below the pivot, strictly
    descending so clause 3 holds. Verified on this box: `64.02 - 61.02` is
    `2.999999999999993`, while both closes round to exactly 64.02 and 61.02 and
    the panel displays a $3.00 widening.

    BOTH floor terms are set to exactly $3.00 (pivot 150.00, adr_pct 2.0 -> ADR
    term $3.00; min_widening_pct 2.0 -> pivot term $3.00). The T4 baseline's
    adr_pct of 3.0 would make the ADR term $4.50 and the test could not clear at
    all -- a second reason it would have passed for the wrong reason.

    Discriminator: an implementation that differences the RAW floats -- OR that
    rounds the OPERANDS and then subtracts, which is the same thing -- gets
    2.999999999999993 < 3.00 and REFUSES, withdrawing nothing while the card
    states equality.
    """
    assert 64.02 - 61.02 == pytest.approx(2.999999999999993, abs=0)
    assert round(64.02, 2) - round(61.02, 2) != 3.0     # rounding first FAILS
    assert round(64.02 - 61.02, 2) == 3.0               # rounding after WORKS

    fire = _fire(pivot=150.00, stop=1.00, adr_pct=2.0)
    clears = _derive(fire=fire,
                     closes=[64.02, 63.50, 63.00, 62.00, 61.02],
                     verdicts=_verdicts("FFFFF")).latches[0]
    assert clears.lapse_would_clear_session == _sessions(5)[4]
    # And the other side of the boundary: a genuine $2.99 does NOT clear.
    refuses = _derive(fire=fire,
                      closes=[64.02, 63.50, 63.00, 62.00, 61.03],
                      verdicts=_verdicts("FFFFF")).latches[0]
    _assert_no_hypothetical(refuses)


def test_2a_reads_the_HIGH_not_the_close():
    """T4.26 -- the OQ-14 ruling's ONLY discriminator across the whole suite.

    Closes 99, 98, 97, 96, 95 -- an otherwise fully qualifying decay (all below
    the pivot, ends at its low, widens $4 > the $3 floor) -- with highs
    99, **101**, 97, 96, 95.

    Discriminator: this is the only listed test the rejected CLOSE-based 2a
    fails. FTRE crosses on the CLOSE so it disqualifies either way; VSTS stays
    below on both; T4.12 varies only closes; and T4.19's duplicate highs make
    the date UNVERIFIABLE *before* 2a runs, so an implementation that
    canonicalizes highs correctly and then wrongly tests the close still passes
    it. WITHOUT THIS TEST the ruled design and the rejected one are
    observationally identical.

    RD's reason: the mandate is a GTC stop-limit that TRIGGERS ON A TOUCH, so
    2a's question is *was the entry trigger reached* -- and a close-based 2a
    would withdraw a mandate whose order may already have filled intraday.
    """
    d = _derive(closes=[99.0, 98.0, 97.0, 96.0, 95.0],
                highs=[99.0, 101.0, 97.0, 96.0, 95.0],
                verdicts=_verdicts("FFFFF"))
    _assert_no_hypothetical(d.latches[0])


def test_display_precision_on_the_2a_comparison():
    """T4.12. Against a pivot of 18.34 at 2dp: a high of 18.3400001 rounds to
    18.34, is at-or-above the pivot and DISQUALIFIES 2a; a high of 18.3349
    rounds to 18.33, is below, and does NOT.

    (An earlier draft used 18.3399 for the second case, which rounds to 18.34
    and also disqualifies -- the test asserted an outcome no correct
    implementation could produce.)
    """
    fire = _fire(pivot=18.34, stop=1.00, adr_pct=5.0)
    closes = [17.0, 16.5, 16.0, 15.5, 15.0]
    at = _derive(fire=fire, closes=closes,
                 highs=[18.3400001, 16.5, 16.0, 15.5, 15.0],
                 verdicts=_verdicts("FFFFF")).latches[0]
    _assert_no_hypothetical(at)
    below = _derive(fire=fire, closes=closes,
                    highs=[18.3349, 16.5, 16.0, 15.5, 15.0],
                    verdicts=_verdicts("FFFFF")).latches[0]
    assert below.lapse_would_clear_session == _sessions(5)[4]


# ===========================================================================
# T4.13 / T4.15 / T4.19 -- the UNVERIFIABLE directional half
# ===========================================================================
def test_lifetime_2a_completeness_is_checked_where_2b_cannot_see_it():
    """T4.13 -- NOT DROPPABLE, and THE GAP MUST SIT BEFORE THE STREAK WINDOW or
    the test proves nothing.

    The N-failure window itself is COMPLETE and fully qualifying (99, 96, 95,
    94, 92), while the MISSING bar -- the one whose true close was 101 -- lies
    after the anchor but BEFORE first(W): inside lifetime 2a's [anchor, s] and
    OUTSIDE 2b's [first(W), last(W)].

    Discriminator: an implementation that omits LIFETIME-2a completeness but
    implements 2b's correctly STILL CLEARS -- the streak window is complete and
    qualifying, so 2b is satisfied, and 2a sees no pivot touch because the
    crossing bar is simply ABSENT. That is the argument-from-silence hole: 2a's
    whole claim is "price never traded through the pivot", and a gap cannot
    support it.

    (An earlier draft put the missing bar INSIDE the streak window, where 2b's
    own completeness already refuses it, so the test passed under an
    implementation with no lifetime-2a completeness at all.)
    """
    days = _sessions(7)
    # Sessions 0 and 1 exist; session 2's bar (the 101) is MISSING; the
    # five-failure window is sessions 3..6 plus session 1.
    bars = [
        DailyBar(session=days[0], open=99.0, high=99.0, low=99.0, close=99.0),
        DailyBar(session=days[2], open=96.0, high=96.0, low=96.0, close=96.0),
        DailyBar(session=days[3], open=95.0, high=95.0, low=95.0, close=95.0),
        DailyBar(session=days[4], open=94.0, high=94.0, low=94.0, close=94.0),
        DailyBar(session=days[5], open=92.0, high=92.0, low=92.0, close=92.0),
    ]
    verdicts = tuple(
        SessionStructuralVerdict(action_session=d, classification="FAILED")
        for d in (days[0], days[2], days[3], days[4], days[5]))
    d = derive_latches(
        fires=[_fire()], bars_by_ticker={"TST": bars}, entries_by_ticker={},
        horizon_session=session_offset(days[5], 1),
        derivation_session=days[5], horizon_sessions=200,
        bar_status_by_ticker={"TST": "ok"},
        structural_verdicts_by_ticker={"TST": verdicts},
        criteria_lapse_armed=True, criteria_lapse_sessions=5)
    latch = d.latches[0]
    assert latch.clear_reason != "criteria_lapsed"
    assert latch.directional_evaluable is False
    assert "archive gap" in (latch.directional_block_reason or "")
    _assert_no_hypothetical(latch)


def test_an_unavailable_archive_suppresses_the_lapse():
    """T4.13's sibling. `archive_status == 'unavailable'` means the read RAISED
    -- OUR IGNORANCE -- so nothing downstream may reason from the absence. 21-G's
    own asymmetry."""
    d = _derive(closes=QUALIFYING, verdicts=_verdicts("FFFFF"), armed=True,
                bar_status="unavailable")
    latch = d.latches[0]
    assert latch.clear_reason != "criteria_lapsed"
    assert latch.directional_evaluable is False
    assert latch.directional_block_reason == "archive unavailable"
    _assert_no_hypothetical(latch)


def test_a_NULL_adr_suppresses_and_the_guarantee_lives_in_ONE_pure_function():
    """T4.15 -- and the discriminating assertion is at the PURE HELPER, because
    the guarantee is observationally INVISIBLE from outside.

    Two earlier drafts of this test were unfalsifiable: 'exceeds any plausible
    fallback' fails because a 25%-of-pivot substitute refuses the series too,
    and the 'order of operations' form fails because such an implementation can
    ALSO emit directional_evaluable = False with a missing-ADR reason -- every
    black-box output identical.

    So: `materiality_floor(adr_pct=None, ...) is None`, WHICH NO FALLBACK
    IMPLEMENTATION CAN SATISFY, BECAUSE RETURNING ANY NUMBER IS THE FALLBACK.
    """
    assert materiality_floor(adr_pct=None, pivot=100.0, adr_multiple=1.0,
                             min_widening_pct=2.0) is None
    assert materiality_floor(adr_pct=float("nan"), pivot=100.0,
                             adr_multiple=1.0, min_widening_pct=2.0) is None
    assert materiality_floor(adr_pct=float("inf"), pivot=100.0,
                             adr_multiple=1.0, min_widening_pct=2.0) is None
    assert materiality_floor(adr_pct="4.0", pivot=100.0, adr_multiple=1.0,
                             min_widening_pct=2.0) is None
    # The positive control -- without it a helper that returned None for
    # EVERYTHING would satisfy all four assertions above.
    assert materiality_floor(adr_pct=4.0, pivot=100.0, adr_multiple=1.0,
                             min_widening_pct=2.0) == pytest.approx(4.0)

    # Integration cover: the pair differs ONLY in the ADR's presence.
    closes = [95.0, 90.0, 85.0, 80.0, 75.0]        # a $20 widening
    without = _derive(fire=_fire(adr_pct=None), closes=closes,
                      verdicts=_verdicts("FFFFF"), armed=True).latches[0]
    assert without.clear_reason != "criteria_lapsed"
    assert without.directional_evaluable is False
    _assert_no_hypothetical(without)
    with_adr = _derive(fire=_fire(adr_pct=3.0), closes=closes,
                       verdicts=_verdicts("FFFFF")).latches[0]
    assert with_adr.lapse_would_clear_session == _sessions(5)[4]


def test_duplicate_bar_canonicalization_covers_the_HIGH_too():
    """T4.19. Two rows for one date AGREEING on close but DISAGREEING on high
    (close 95 / high 101 and close 95 / high 99) make that date UNVERIFIABLE.

    Discriminator: a CLOSE-ONLY canonicalization collapses them, and under the
    ruled HIGH-based 2a a surviving `high 99` row HIDES a pivot touch at 101 --
    clearing a latch whose stop-limit had already triggered.
    """
    days = _sessions(5)
    closes = [99.0, 95.0, 94.0, 93.0, 92.0]
    bars = [DailyBar(session=d, open=c, high=c, low=c, close=c)
            for d, c in zip(days, closes, strict=True)]
    # The duplicate pair on day 1, agreeing on close and NOT on high.
    bars[1] = DailyBar(session=days[1], open=95.0, high=101.0, low=95.0,
                       close=95.0)
    bars.append(DailyBar(session=days[1], open=95.0, high=99.0, low=95.0,
                         close=95.0))
    d = derive_latches(
        fires=[_fire()], bars_by_ticker={"TST": bars}, entries_by_ticker={},
        horizon_session=session_offset(days[4], 1), derivation_session=days[4],
        horizon_sessions=200, bar_status_by_ticker={"TST": "ok"},
        structural_verdicts_by_ticker={"TST": _verdicts("FFFFF")},
        criteria_lapse_armed=True, criteria_lapse_sessions=5)
    latch = d.latches[0]
    assert latch.clear_reason != "criteria_lapsed"
    _assert_no_hypothetical(latch)


# ===========================================================================
# T4.9 / T4.16 -- precedence and L10
# ===========================================================================
def test_a_LATER_invalidation_does_not_rewrite_an_earlier_lapse():
    """T4.9(a)(b) -- NOT DROPPABLE, and the case an earlier draft of the PLAN
    got wrong.

    A latch lapses on D5; on D8 the close finally breaks the frozen stop.

    Discriminator (a): a resolver that scans the WHOLE eligible range for
    invalidation BEFORE considering the lapse finds D8 and stamps
    invalidation/D8 -- retroactively changing a terminal that resolved three
    sessions earlier.

    Discriminator (b): under that wrong structure the fill rung then compares
    against D8 instead of D5, so a fill on D6 satisfies `entry_date <=
    nonfill.session` and IS attributed -- a real position credited to a mandate
    the framework had already withdrawn.
    """
    days = _sessions(8)
    closes = [98.0, 95.0, 92.0, 89.0, 86.0, 85.0, 84.0, 0.50]   # D8 < stop 1.00
    entry = EntryRecord(trade_id=42, ticker="TST", entry_date=days[5],
                        candidate_id=8851, entry_price=100.5, shares=5)
    latch = _derive(closes=closes, verdicts=_verdicts("FFFFFFFF"),
                    entries=[entry]).latches[0]
    # The counterfactual runs the FULL ladder with the lapse forced in: it beats
    # the D8 invalidation on DATE and the D6 fill on date, so the armed answer is
    # the D5 lapse and the D6 fill is not attributed to it.
    assert latch.lapse_would_clear_session == days[4]


def test_same_session_collisions_resolve_by_rank():
    """T4.9(c)(d)(e). Different-session terminals pass under EITHER structure
    and prove nothing, so these are all same-session ties.

    (c) invalidation and lapse on one session -> invalidation (rank 3 < 4).
    (d) lapse and horizon on one session      -> criteria_lapsed (4 < 5).
    (e) a fill at-or-before the lapse         -> fill (rank 0).
    """
    days = _sessions(5)
    # (c) the D5 close is BOTH the qualifying window's terminal and below stop.
    inval = _derive(fire=_fire(stop=90.0),
                    closes=[98.0, 95.0, 92.0, 91.0, 86.0],
                    verdicts=_verdicts("FFFFF")).latches[0]
    assert inval.clear_reason == "invalidation"
    assert inval.clear_session == days[4]
    assert inval.lapse_qualifying_session == days[4]     # the lapse DID qualify
    assert inval.lapse_would_clear_session is None       # and STILL loses

    # (d) the horizon expires exactly on the lapse session.
    horizon = derive_latches(
        fires=[_fire()], bars_by_ticker={"TST": _bars(QUALIFYING)},
        entries_by_ticker={}, horizon_session=session_offset(days[4], 1),
        derivation_session=days[4], horizon_sessions=4,
        bar_status_by_ticker={"TST": "ok"},
        structural_verdicts_by_ticker={"TST": _verdicts("FFFFF")},
        criteria_lapse_sessions=5).latches[0]
    assert horizon.horizon_expiry == days[4]
    assert horizon.clear_reason == "horizon"             # unarmed
    assert horizon.lapse_would_clear_session == days[4]  # armed it would WIN

    # (e) a fill dated ON the lapse session.
    entry = EntryRecord(trade_id=43, ticker="TST", entry_date=days[4],
                        candidate_id=8851, entry_price=100.5, shares=5)
    fill = _derive(closes=QUALIFYING, verdicts=_verdicts("FFFFF"),
                   entries=[entry]).latches[0]
    assert fill.clear_reason == "fill"
    assert fill.lapse_would_clear_session is None


def test_a_later_pivot_crossing_cannot_RESURRECT_a_cleared_latch():
    """T4.16. Closes 95, 94, 93, 92, 90 clear at D5; then a D6 bar closing 105
    is added and the derivation is re-run.

    Discriminator: an implementation bounding 2a at `derivation_session` instead
    of at the CANDIDATE WINDOW'S OWN terminal `s` finds the 105 crossing,
    disqualifies 2a, and RESURRECTS a latch that had already cleared -- breaking
    L10 through the conjunct rather than through the precedence. And a fill
    dated D6 would then be attributed to a withdrawn mandate.
    """
    days = _sessions(6)
    before = _derive(closes=[95.0, 94.0, 93.0, 92.0, 90.0],
                     verdicts=_verdicts("FFFFF")).latches[0]
    assert before.lapse_would_clear_session == days[4]

    entry = EntryRecord(trade_id=44, ticker="TST", entry_date=days[5],
                        candidate_id=8851, entry_price=100.5, shares=5)
    after = _derive(closes=[95.0, 94.0, 93.0, 92.0, 90.0, 105.0],
                    verdicts=_verdicts("FFFFFF"), entries=[entry]).latches[0]
    assert after.lapse_would_clear_session == days[4]    # UNMOVED


def test_the_lapse_walk_is_capped_at_the_horizon_expiry():
    """T4.10. A streak completing AFTER expiry leaves `horizon` at the horizon's
    own clear session -- once the mandate is dead, a later structural failure is
    not a withdrawal OF IT."""
    days = _sessions(6)
    d = derive_latches(
        fires=[_fire()], bars_by_ticker={"TST": _bars([98.0, 95.0, 92.0, 89.0,
                                                       86.0, 83.0])},
        entries_by_ticker={}, horizon_session=session_offset(days[5], 1),
        derivation_session=days[5], horizon_sessions=2,
        bar_status_by_ticker={"TST": "ok"},
        structural_verdicts_by_ticker={"TST": _verdicts("FFFFFF")},
        criteria_lapse_sessions=5).latches[0]
    assert d.horizon_expiry == days[2]
    assert d.clear_reason == "horizon"
    assert d.clear_session == days[2]


# ===========================================================================
# T4.20 / T4.23 / T4.24 / T4.25 -- the report-only instrument itself
# ===========================================================================
# ===========================================================================
# TASK 5c -- THE TERMINAL AND ITS GATE. These are the ONLY tests here that
# assert an actual `criteria_lapsed` clear; everything above asserts the
# HYPOTHETICAL, which is what ships in the default configuration.
# ===========================================================================
def test_the_hypothetical_is_computed_IDENTICALLY_armed_or_not():
    """T4.20 -- NOT DROPPABLE. The invariant that makes report-only mean
    anything.

    Scoped to the RESOLVER'S HYPOTHETICAL, not the whole latch: returning a
    terminal necessarily also changes `clear_session`, `is_live`, the state
    label and the classification, so "differ ONLY in clear_reason" could never
    hold.

    It ITERATES the named roster rather than listing a subset -- a test that
    enumerates its own subset omits exactly the newest field, which is how
    `lapse_conflicted_sessions` and `lapse_would_clear_session` would have
    escaped.

    Discriminator: an implementation that short-circuits the streak fold or the
    conjuncts when unarmed produces empty or different diagnostics, and
    report-only measures NOTHING -- the failure that would make RD's framing
    ruling worthless.
    """
    kwargs = dict(closes=QUALIFYING, verdicts=_verdicts("FFFFF"))
    unarmed = _derive(**kwargs, armed=False).latches[0]
    armed = _derive(**kwargs, armed=True).latches[0]
    for name in LATCH_LAPSE_DIAGNOSTIC_FIELDS:
        assert getattr(unarmed, name) == getattr(armed, name), name
    assert unarmed.is_live is True
    assert unarmed.clear_reason is None
    assert armed.clear_reason == "criteria_lapsed"
    assert armed.clear_session == unarmed.lapse_would_clear_session


def test_the_counterfactual_respects_the_FULL_ladder_including_the_fill():
    """T4.23. Three cases, all UNARMED -- which is the shipped configuration and
    therefore the one the calibration read actually consumes.

    (a) FILL-ONLY: a fill on D4, a qualifying lapse on D5, NO earlier non-fill
        terminal. `lapse_qualifying_session == D5` but `would_clear is None`,
        because ARMED the latch clears by `fill`.
        Discriminator: THIS IS THE ONLY FIXTURE THAT CATCHES A COUNTERFACTUAL
        BUILT AS A `min(...)` OVER THE NON-FILL CANDIDATE LIST -- the fill is a
        SEPARATE pass whose window depends on which non-fill terminal won, so
        that implementation reports a withdrawal on D5 and inflates the very
        number that decides whether the rule gets armed.
    (b) INVALIDATION on D3 beats the D5 lapse -> would_clear is None.
    (c) CLEAN: no competing terminal -> would_clear == qualifying.
    """
    days = _sessions(5)
    entry = EntryRecord(trade_id=45, ticker="TST", entry_date=days[3],
                        candidate_id=8851, entry_price=100.5, shares=5)
    a = _derive(closes=QUALIFYING, verdicts=_verdicts("FFFFF"),
                entries=[entry]).latches[0]
    assert a.lapse_qualifying_session == days[4]
    assert a.lapse_would_clear_session is None

    b = _derive(fire=_fire(stop=93.0), closes=QUALIFYING,
                verdicts=_verdicts("FFFFF")).latches[0]
    assert b.lapse_qualifying_session == days[4]
    assert b.lapse_would_clear_session is None

    c = _derive(closes=QUALIFYING, verdicts=_verdicts("FFFFF")).latches[0]
    assert c.lapse_qualifying_session == days[4]
    assert c.lapse_would_clear_session == days[4]


def test_the_diagnostic_roster_SURVIVES_a_precedence_loss():
    """T4.23(d). For the fill-only and invalidation cases, derive armed and
    unarmed and assert EVERY roster field is equal across the pair AND
    populated.

    Discriminator: T4.20 compares only the CLEAN winning-lapse case, so an
    implementation that stops populating diagnostics whenever another terminal
    wins passes it -- losing the streak, gap and conflict evidence on exactly
    the precedence-losing latches the calibration read needs to distinguish.
    """
    days = _sessions(5)
    entry = EntryRecord(trade_id=46, ticker="TST", entry_date=days[3],
                        candidate_id=8851, entry_price=100.5, shares=5)
    for kwargs in (dict(entries=[entry]), dict(fire=_fire(stop=93.0))):
        unarmed = _derive(closes=QUALIFYING, verdicts=_verdicts("FFFFF"),
                          armed=False, **kwargs).latches[0]
        armed = _derive(closes=QUALIFYING, verdicts=_verdicts("FFFFF"),
                        armed=True, **kwargs).latches[0]
        for name in LATCH_LAPSE_DIAGNOSTIC_FIELDS:
            assert getattr(unarmed, name) == getattr(armed, name), name
        assert unarmed.lapse_qualifying_session == days[4]
        assert unarmed.lapse_failed_count == 5
        assert unarmed.directional_evaluable is True


def test_the_resolver_owns_the_unverifiable_SUFFIX():
    """T4.24. Sequence FAIL / UNVERIFIABLE / PASS / UNVERIFIABLE / UNVERIFIABLE
    -> tail 2.

    Discriminator: this is the check the `Latch` constructor CANNOT make --
    `Latch` never carries the PASSED session, so a constructor cannot tell a
    genuine 2-tail from one that ignored an intervening PASS. Owning it at the
    resolver is what makes the claim true rather than merely asserted.
    """
    latch = _derive(closes=[98.0, 97.0, 96.0, 95.0, 94.0],
                    verdicts=_verdicts("FUPUU")).latches[0]
    assert latch.lapse_unverifiable_tail == 2


def test_the_streak_tuples_are_CURRENT_STREAK_and_the_analysis_ones_are_not():
    """T4.25 -- the §3.2.1 split, and neither scope alone satisfies both
    contracts.

    FAIL D1 / PASS D2 / FAIL D3 -> failed sessions (D3,), count 1 -- NOT
    (D1, D3) / 2. A conflict on D1 STILL appears in the conflicted tuple, which
    is ANALYSIS-window scoped: a conflict RESOLVES to PASS, so a streak-scoped
    tuple would DELETE the ambiguity RD required to be surfaced the instant it
    was conservatively resolved.

    Discriminator: one analysis-window rule for all tuples fails the first
    assertion; one streak-scoped rule fails the conflict assertion. And T4.20's
    armed/unarmed equality would notice NEITHER error, because both runs would
    be identically wrong.
    """
    days = _sessions(3)
    verdicts = (
        SessionStructuralVerdict(action_session=days[0], classification="FAILED"),
        SessionStructuralVerdict(action_session=days[1], classification="PASSED",
                                 conflicted=True),
        SessionStructuralVerdict(action_session=days[2], classification="FAILED"),
    )
    latch = _derive(closes=[98.0, 97.0, 96.0], verdicts=verdicts).latches[0]
    assert latch.lapse_failed_sessions == (days[2],)
    assert latch.lapse_failed_count == 1
    assert latch.lapse_conflicted_sessions == (days[1],)

    # The unchecked half of the same split.
    latch2 = _derive(closes=[98.0, 97.0, 96.0],
                     verdicts=_verdicts("UPF")).latches[0]
    assert latch2.lapse_unchecked_count == 0


def test_no_verdicts_at_all_makes_the_feature_inert():
    """The default path every existing caller and fixture takes: verdicts=None
    means NO lapse is ever resolved -- inert, never a fabricated clear."""
    d = derive_latches(
        fires=[_fire()], bars_by_ticker={"TST": _bars(QUALIFYING)},
        entries_by_ticker={}, horizon_session=session_offset(_sessions(5)[4], 1),
        derivation_session=_sessions(5)[4], horizon_sessions=200,
        criteria_lapse_armed=True)
    latch = d.latches[0]
    assert latch.clear_reason is None
    _assert_no_hypothetical(latch)
    assert latch.lapse_failed_count == 0


def test_arming_the_flag_emits_the_terminal_at_the_would_clear_session():
    """Task 5c's own assertion, stated as a PAIR rather than in isolation: the
    session the ARMED derivation clears on is exactly the session the UNARMED
    derivation predicted. That equality is the whole claim report-only makes to
    the calibration decision -- if it did not hold, the measured evidence would
    describe a rule other than the one that would be armed.
    """
    days = _sessions(5)
    unarmed = _derive(closes=QUALIFYING, verdicts=_verdicts("FFFFF")).latches[0]
    armed = _derive(closes=QUALIFYING, verdicts=_verdicts("FFFFF"),
                    armed=True).latches[0]
    assert unarmed.clear_reason is None
    assert unarmed.lapse_would_clear_session == days[4]
    assert armed.clear_reason == "criteria_lapsed"
    assert armed.clear_session == days[4]
    assert armed.state == "horizon_expired"        # Option B


def test_arming_CHANGES_LATCH_TOPOLOGY_and_that_is_expected():
    """T4.22 -- the legitimate downstream consequence T4.20's scoping excludes,
    tested SEPARATELY rather than hidden.

    A same-pivot RE-FIRE arriving after the hypothetical lapse session:
    UNARMED the old latch is still live, so the re-fire is a RE-CONFIRMATION;
    ARMED it had already cleared, so the re-fire opens a NEW latch.

    This is a real fact for whoever arms the flag: **arming changes the latch
    CORPUS, not merely the labels** -- which is also why report-only measures the
    first hypothetical clear per latch rather than simulating the armed world.
    """
    days = _sessions(7)
    refire = FireRow(
        candidate_id=8852, evaluation_run_id=131, ticker="TST", pivot=100.0,
        initial_stop=1.00, action_session_date=days[5].isoformat(),
        run_ts="2026-08-04T17:30:00", pipeline_run_id=141, adr_pct=3.0)
    closes = [*QUALIFYING, 85.0, 84.0]
    kwargs = dict(closes=closes, verdicts=_verdicts("FFFFFFF"),
                  extra_fires=[refire])
    unarmed = _derive(**kwargs).latches
    armed = _derive(**kwargs, armed=True).latches
    assert len(unarmed) == 1
    assert unarmed[0].reconfirmation_candidate_ids == (8852,)
    assert len(armed) == 2
    assert armed[0].clear_reason == "criteria_lapsed"
    assert armed[1].identity.candidate_id == 8852
    assert armed[1].is_live


def test_an_armed_lapse_classifies_framework_withdrawn_not_discipline_lapse():
    """The Task-6 composition, asserted at the point the terminal becomes
    emittable. Without the disposition rung -- which is why Task 6 was
    re-sequenced ahead of this commit -- this same latch classifies
    `discipline_lapse`, charging the operator for a mandate the framework
    retracted."""
    from swing.latches.classification import classify_latch, r_bucket_for
    from swing.latches.constants import LATCH_TELEMETRY_EPOCH_SESSION

    # ANCHORED AFTER THE TELEMETRY EPOCH, deliberately: before it, rung 4
    # legitimately returns `pre_telemetry` and pre-empts this rung (residual R3,
    # pinned as ruled in test_framework_withdrawn.py). A fixture that ignored
    # that would assert the wrong composition.
    start = LATCH_TELEMETRY_EPOCH_SESSION
    armed = _derive(closes=QUALIFYING,
                    verdicts=_verdicts("FFFFF", start=start),
                    start=start, armed=True).latches[0]
    got = classify_latch(latch=armed, views=[], intents=[])
    assert got.disposition == "framework_withdrawn"
    assert r_bucket_for(got.disposition, is_terminal=True) == "unattributable_r"
