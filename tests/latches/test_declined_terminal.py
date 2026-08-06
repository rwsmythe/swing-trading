"""The `declined` terminal -- item 3a (RD OQ-4, R5, R6; 2026-08-06).

An operator `decline` intent recorded against a live latch's candidate family
ENDS the mandate. V1-B, UNIFORM: a decline is a decline, on-screen or off.

Two things every test here is written against, because a plausible alternative
implementation gets each wrong in a way no other test catches:

* **earliest-date-wins, rank only on a same-session tie.** A terminal is an
  event with a DATE, and nothing later can un-happen it (L10).
* **the CROSS-KIND resolution.** The governing answer is the latest of the
  `place`/`decline` FAMILY, never the latest DECLINE -- otherwise a decline the
  operator CORRECTED by re-placing still withdraws his mandate.
"""
from __future__ import annotations

from datetime import date

from swing.data.models import LatchOrderIntent
from swing.latches.classification import (
    classify_latch,
    decision_bounds_for,
    r_bucket_for,
)
from swing.latches.constants import LATCH_CLEAR_REASONS
from swing.latches.models import DailyBar, EntryRecord, FireRow
from swing.latches.service import _CLEAR_REASON_RANK, derive_latches

ANCHOR = "2026-07-27"
D1, D2, D3 = "2026-07-28", "2026-07-29", "2026-07-30"
D4, D5, D6 = "2026-07-31", "2026-08-03", "2026-08-04"
D10 = "2026-08-10"
HORIZON_SESSION = date(2026, 8, 6)
DERIVATION_SESSION = date(2026, 8, 5)

VSTS_FIRE = FireRow(
    candidate_id=8851, evaluation_run_id=126, ticker="VSTS", pivot=16.90,
    initial_stop=13.40, action_session_date=ANCHOR,
    run_ts="2026-07-24T17:30:11", pipeline_run_id=140)


def _bar(d: str, close: float) -> DailyBar:
    return DailyBar(session=date.fromisoformat(d), open=close, high=close,
                    low=close, close=close)


def _decision(kind: str, *, session: str, intent_id: int,
              candidate_id: int = 8851, recorded_ts: str | None = None,
              ticker: str = "VSTS") -> LatchOrderIntent:
    return LatchOrderIntent(
        intent_id=intent_id, candidate_id=candidate_id, evaluation_run_id=126,
        ticker=ticker, detection_date=ANCHOR, pipeline_run_id=140,
        idempotency_key=f"k{intent_id}", action_session_date=session,
        recorded_ts=recorded_ts or f"{session}T10:00:00",
        surface="latch_panel", intent_kind=kind,
        decline_reason="off the screen; the pivot is stale" if kind == "decline"
        else None,
        framework_order_type="STOP_LIMIT", framework_duration="GOOD_TILL_CANCEL",
        framework_stop_price=16.90, framework_limit_price=17.40,
        framework_quantity=9, derivation_zone_cap_pct=3.0,
        derivation_sizing_equity=7500.0, derivation_max_risk_pct=0.005,
        derivation_position_pct_cap=0.15, derivation_sizing_basis="limit_price",
        derivation_regime_close=15.58, derivation_regime_close_session=ANCHOR,
        derivation_real_equity=1300.0, derivation_equity_floor=7500.0)


def _derive(*, fires=None, bars=(), entries=(), decisions=(),
            horizon_session=HORIZON_SESSION,
            derivation_session=DERIVATION_SESSION):
    return derive_latches(
        fires=list(fires if fires is not None else [VSTS_FIRE]),
        bars_by_ticker={"VSTS": list(bars)},
        entries_by_ticker={"VSTS": list(entries)},
        decision_intents_by_candidate_id=_by_candidate(decisions),
        horizon_session=horizon_session,
        derivation_session=derivation_session)


def _by_candidate(decisions):
    out: dict[int, list] = {}
    for d in decisions:
        out.setdefault(d.candidate_id, []).append(d)
    return out


# --------------------------------------------------------------------------
# The ladder table -- RD's projection pin
# --------------------------------------------------------------------------
def test_the_rank_tables_domain_IS_the_live_clear_reason_vocabulary():
    """RD's projection pin (lean of 2026-08-06). The AUTHORITY for the ladder is
    his R6 ruling, not this table; what the table holds is that ladder RESTRICTED
    to the reasons this code can actually produce.

    Asserting the domain rather than a subset is what makes it survive the next
    arc: the moment a reason joins `LATCH_CLEAR_REASONS` without a rank, this
    fails -- the vocabulary and its precedence can never drift apart.
    """
    assert set(_CLEAR_REASON_RANK) == set(LATCH_CLEAR_REASONS)


def test_the_rank_order_IS_the_ruled_ladder_projected():
    """`fill > declined > superseded > invalidation > horizon` -- R6's six-rung
    ladder with the one reason that has no producer yet left out. 3b re-asserts
    this same property over six members when it gains one.

    Ranks must also be DISTINCT: a duplicate makes the same-session tiebreak
    depend on the order the candidate list happened to be built in, which is a
    silent, input-order-dependent bug rather than a visible one.
    """
    ordered = sorted(_CLEAR_REASON_RANK, key=lambda r: _CLEAR_REASON_RANK[r])
    assert ordered == [
        "fill", "declined", "superseded", "invalidation", "horizon"]
    assert len(set(_CLEAR_REASON_RANK.values())) == len(_CLEAR_REASON_RANK)


# --------------------------------------------------------------------------
# T4.21 (a)-(o)
# --------------------------------------------------------------------------
def test_a_decline_terminates_the_mandate_at_its_own_session():
    """(a). The V1-A gap closed: the decision now CORRECTS the stale pivot
    rather than only noting it beside a mandate that stays live."""
    d = _derive(decisions=[_decision("decline", session=D5, intent_id=1)])
    latch = d.latches[0]
    assert latch.clear_reason == "declined"
    assert latch.clear_session == date.fromisoformat(D5)
    assert latch.state == "horizon_expired"      # OQ-2 Option B / residual R1
    assert latch.is_live is False


def test_the_decline_is_UNIFORM_and_consults_no_screen_state():
    """(b). RD OQ-4: special-casing off-screen would make the same operator act
    mean two different things. The resolver reads INTENTS only, so a latch with
    a full bar history and one with none terminate identically."""
    decisions = [_decision("decline", session=D5, intent_id=1)]
    on_screen = _derive(
        bars=[_bar(D1, 15.35), _bar(D2, 15.36), _bar(D3, 14.92)],
        decisions=decisions).latches[0]
    off_screen = _derive(decisions=decisions).latches[0]
    assert on_screen.clear_reason == off_screen.clear_reason == "declined"
    assert on_screen.clear_session == off_screen.clear_session


def test_a_fill_AT_the_decline_session_wins():
    """(c). "You cannot decline a filled mandate." The tie goes to the fill
    because operator FACTS outrank operator DECISIONS."""
    entry = EntryRecord(trade_id=41, ticker="VSTS",
                        entry_date=date.fromisoformat(D5), candidate_id=8851,
                        entry_price=16.95, shares=9)
    d = _derive(entries=[entry],
                decisions=[_decision("decline", session=D5, intent_id=1)])
    assert d.latches[0].clear_reason == "fill"
    assert d.latches[0].clear_trade_id == 41


def test_a_fill_AFTER_the_decline_session_does_not_win():
    """(d). The mandate was already over; a later buy is not this latch's."""
    entry = EntryRecord(trade_id=41, ticker="VSTS",
                        entry_date=date.fromisoformat(D6), candidate_id=8851,
                        entry_price=16.95, shares=9)
    d = _derive(entries=[entry],
                decisions=[_decision("decline", session=D5, intent_id=1)])
    latch = d.latches[0]
    assert latch.clear_reason == "declined"
    assert latch.clear_trade_id is None


def test_a_decline_and_an_invalidation_on_ONE_session_resolve_declined():
    """(e). The same-session tie is where the RANK is load-bearing, and it is
    the only place it is: on different dates the earlier event wins whatever the
    ranks say."""
    d = _derive(bars=[_bar(D5, 13.00)],
                decisions=[_decision("decline", session=D5, intent_id=1)],
                derivation_session=date.fromisoformat(D5))
    assert d.latches[0].clear_reason == "declined"


def test_an_EARLIER_invalidation_beats_a_later_decline():
    """(f). L10: a terminal is an event with a date and nothing later can
    un-happen it. Discriminator: an implementation that ranked `declined` above
    `invalidation` unconditionally returns `declined` at D5 and rewrites a
    terminal that had already resolved on D3."""
    d = _derive(bars=[_bar(D1, 15.35), _bar(D3, 13.00)],
                decisions=[_decision("decline", session=D5, intent_id=1)])
    latch = d.latches[0]
    assert latch.clear_reason == "invalidation"
    assert latch.clear_session == date.fromisoformat(D3)


def test_the_governing_decline_is_the_LATEST_by_recorded_ts_then_intent_id():
    """(g). The same total order every other latest-by-what ruling in this arc
    uses; the id tiebreak is load-bearing because `recorded_ts` is whole
    seconds. Asserted under BOTH list orders -- reading "the first found" passes
    under one and fails under the other, which IS the bug."""
    early = _decision("decline", session=D3, intent_id=1,
                      recorded_ts="2026-08-03T09:00:00")
    late = _decision("decline", session=D5, intent_id=2,
                     recorded_ts="2026-08-03T09:00:00")
    for order in ([early, late], [late, early]):
        d = _derive(decisions=order)
        assert d.latches[0].clear_session == date.fromisoformat(D5)


def test_a_later_PLACE_erases_the_decline_the_operator_corrected():
    """(i) -- the headline protection.

    `governing_decision` resolves the place/decline FAMILY together: they are
    the two mutually exclusive answers to ONE question. A lifecycle keyed on the
    latest DECLINE terminates at D5 while the classifier scores the same latch
    `accepted` -- the framework withdrawing a mandate AFTER the operator
    corrected himself and re-placed it.
    """
    d = _derive(decisions=[
        _decision("decline", session=D5, intent_id=1),
        _decision("place", session=D6, intent_id=2)])
    latch = d.latches[0]
    assert latch.clear_reason != "declined"
    assert latch.is_live is True


def test_a_decline_recorded_AFTER_the_horizon_leaves_the_expiry_standing():
    """(k). The same cap the invalidation walk already carries: once the mandate
    is dead, a later act is not a withdrawal OF it."""
    late_session = "2026-09-21"          # well past a 30-session horizon
    d = _derive(
        decisions=[_decision("decline", session=late_session, intent_id=1)],
        horizon_session=date(2026, 9, 22),
        derivation_session=date(2026, 9, 21))
    latch = d.latches[0]
    assert latch.clear_reason == "horizon"
    assert latch.clear_session == latch.horizon_expiry


def test_a_decline_ON_the_horizon_expiry_session_still_wins():
    """(o), the neighbouring-rung tie a new insertion gets wrong. An off-by-one
    that excluded a decision dated exactly at `horizon_expiry` would file the
    operator's own act as a deadline running out."""
    d = _derive(decisions=[_decision("decline", session=D5, intent_id=1)],
                horizon_session=HORIZON_SESSION)
    expiry = d.latches[0].horizon_expiry
    on_expiry = _derive(
        decisions=[_decision("decline", session=expiry.isoformat(),
                             intent_id=1)],
        horizon_session=date(2026, 9, 22),
        derivation_session=date(2026, 9, 21))
    assert on_expiry.latches[0].clear_reason == "declined"
    assert on_expiry.latches[0].clear_session == expiry


def test_an_older_latchs_decline_never_touches_a_newer_latch_on_the_ticker():
    """(m). Discriminator: a TICKER-keyed intent mapping terminates the newer
    mandate the operator never declined."""
    second = FireRow(
        candidate_id=9100, evaluation_run_id=131, ticker="VSTS", pivot=18.50,
        initial_stop=15.00, action_session_date=D5,
        run_ts="2026-07-31T17:30:04", pipeline_run_id=145)
    d = _derive(fires=[VSTS_FIRE, second],
                decisions=[_decision("decline", session=D1, intent_id=1,
                                     candidate_id=8851)])
    by_id = {x.identity.candidate_id: x for x in d.latches}
    assert by_id[8851].clear_reason == "declined"
    assert by_id[9100].is_live is True


def test_a_successor_latchs_PLACE_never_resurrects_its_predecessor():
    """(l2) -- residual R5, RULED by RD: decisions are PER-LATCH and never
    retroactive.

    A decline at D1 ends the first mandate; a different-pivot re-fire at D5 arms
    a NEW one; a place recorded at D6 against the NEW candidate governs that
    latch only. Discriminator: an implementation matching decisions by TICKER --
    or widening the predecessor's family to include its successor -- erases the
    D1 decline and resurrects a mandate the operator declined.
    """
    second = FireRow(
        candidate_id=9100, evaluation_run_id=131, ticker="VSTS", pivot=18.50,
        initial_stop=15.00, action_session_date=D5,
        run_ts="2026-07-31T17:30:04", pipeline_run_id=145)
    d = _derive(fires=[VSTS_FIRE, second], decisions=[
        _decision("decline", session=D1, intent_id=1, candidate_id=8851),
        _decision("place", session=D6, intent_id=2, candidate_id=9100)])
    by_id = {x.identity.candidate_id: x for x in d.latches}
    assert by_id[8851].clear_reason == "declined"
    assert by_id[8851].clear_session == date.fromisoformat(D1)
    assert by_id[9100].is_live is True


def test_declined_BEATS_superseded_on_the_same_session_and_the_successor_lives():
    """(n) -- residual R6, RULED by RD: operator facts beat framework events.

    A predecessor-family decline and a DIFFERENT-pivot re-fire landing on ONE
    action session. `superseded` is stamped by the FOLD, outside the resolver,
    and the liveness probe deliberately cannot see the re-fire session itself --
    so the fold must consult the decline before it stamps.

    TWO discriminators, and the second is the one a predecessor-only assertion
    misses entirely: an implementation that stamps `superseded` overwrites the
    operator's recorded decision with a framework inference; and one that marks
    the predecessor `declined` but DROPS the incoming fire -- or absorbs it as a
    re-confirmation -- passes the first assertion while silently losing the
    succeeding mandate.
    """
    second = FireRow(
        candidate_id=9100, evaluation_run_id=131, ticker="VSTS", pivot=18.50,
        initial_stop=15.00, action_session_date=D5,
        run_ts="2026-07-31T17:30:04", pipeline_run_id=145)
    d = _derive(fires=[VSTS_FIRE, second], decisions=[
        _decision("decline", session=D5, intent_id=1, candidate_id=8851)])
    assert len(d.latches) == 2
    by_id = {x.identity.candidate_id: x for x in d.latches}
    assert by_id[8851].clear_reason == "declined"
    assert by_id[8851].clear_session == date.fromisoformat(D5)
    successor = by_id[9100]
    assert successor.is_live is True
    assert successor.latched_pivot == 18.50
    assert successor.clear_reason is None


def test_a_supersede_with_NO_decline_is_untouched():
    """The other half of (n): the shipped supersede must still fire when there
    is no decision to outrank it. Without this the R6 branch could swallow every
    supersede and nothing here would notice."""
    second = FireRow(
        candidate_id=9100, evaluation_run_id=131, ticker="VSTS", pivot=18.50,
        initial_stop=15.00, action_session_date=D5,
        run_ts="2026-07-31T17:30:04", pipeline_run_id=145)
    d = _derive(fires=[VSTS_FIRE, second])
    by_id = {x.identity.candidate_id: x for x in d.latches}
    assert by_id[8851].clear_reason == "superseded"
    assert by_id[8851].clear_session == date.fromisoformat(D5)


def test_a_decline_dated_AFTER_a_re_fire_does_not_kill_the_old_latch_early():
    """(j) -- THE AS-OF BOUND, asserted through the fold's own topology.

    The liveness probe asks "had this latch terminated by the session BEFORE the
    re-fire?". A decline recorded at D10 has not happened as of D5, so the probe
    must not see it; if it does, the old latch reads dead at D5, the fold takes
    the wrong clause, and the reconfirm/supersede topology is corrupted.

    Discriminator: unbounded, the old latch clears `declined` at D10 -- a date
    AFTER the successor already armed -- instead of `superseded` at D5.
    """
    second = FireRow(
        candidate_id=9100, evaluation_run_id=131, ticker="VSTS", pivot=18.50,
        initial_stop=15.00, action_session_date=D5,
        run_ts="2026-07-31T17:30:04", pipeline_run_id=145)
    d = _derive(fires=[VSTS_FIRE, second], decisions=[
        _decision("decline", session=D10, intent_id=1, candidate_id=8851)],
        horizon_session=date(2026, 8, 12),
        derivation_session=date(2026, 8, 11))
    by_id = {x.identity.candidate_id: x for x in d.latches}
    assert by_id[8851].clear_reason == "superseded"
    assert by_id[8851].clear_session == date.fromisoformat(D5)


def test_no_decisions_at_all_leaves_every_shipped_outcome_unchanged():
    """The null case, asserted rather than assumed: with the new parameter
    absent the derivation is the shipped one."""
    bars = [_bar(D1, 15.35), _bar(D2, 15.36), _bar(D3, 14.92)]
    with_param = _derive(bars=bars)
    without = derive_latches(
        fires=[VSTS_FIRE], bars_by_ticker={"VSTS": bars},
        entries_by_ticker={}, horizon_session=HORIZON_SESSION,
        derivation_session=DERIVATION_SESSION)
    assert with_param.latches == without.latches


# --------------------------------------------------------------------------
# T6.12 / T6.13 -- the lifecycle and the classifier, asserted TOGETHER
# --------------------------------------------------------------------------
def _classified(latch, intents):
    return classify_latch(
        latch=latch, views=[], intents=list(intents),
        decision_bounds=decision_bounds_for(
            latch, fill_bound=HORIZON_SESSION))


def test_a_declined_latch_is_TERMINAL_and_enters_the_scored_denominator():
    """T6.12 -- the measurement transition, pinned because it moves a PUBLISHED
    denominator.

    Before OQ-4 a declined latch stayed LIVE, so `r_bucket_for` gated it to
    `pending_r`: reported, never scored. Now the decline TERMINATES it and the
    same latch lands in `decision_r`, entering `classifiable_fires` and the
    away-rate denominator. That is RD's intent -- "scored, his call" -- and the
    monthly read should expect the shift once.
    """
    decline = _decision("decline", session=D5, intent_id=1)
    latch = _derive(decisions=[decline]).latches[0]
    got = _classified(latch, [decline])
    assert got.is_terminal is True
    assert got.disposition == "declined"
    assert r_bucket_for("declined", is_terminal=True) == "decision_r"
    # the pre-ruling pair, stated so the shift is legible
    assert r_bucket_for("declined", is_terminal=False) == "pending_r"


def test_the_lifecycle_and_the_classifier_agree_on_every_collision():
    """T6.13. Each pair is asserted TOGETHER: either side alone passes while the
    two contradict each other about the SAME latch.

    Discriminator: an UNBOUNDED classifier returns `declined` for all three --
    a FILLED mandate scored in `decision_r` as a decline.
    """
    decline5 = _decision("decline", session=D5, intent_id=1)
    fill4 = EntryRecord(trade_id=41, ticker="VSTS",
                        entry_date=date.fromisoformat(D4), candidate_id=8851,
                        entry_price=16.95, shares=9)
    fill5 = EntryRecord(trade_id=42, ticker="VSTS",
                        entry_date=date.fromisoformat(D5), candidate_id=8851,
                        entry_price=16.95, shares=9)

    for entries, bars, reason in (
        ([fill4], (), "fill"),                      # fill D4 / decline D5
        ([fill5], (), "fill"),                      # BOTH on D5
        ([], [_bar(D3, 13.00)], "invalidation"),    # invalidation D3 / decline D5
    ):
        latch = _derive(entries=entries, bars=bars,
                        decisions=[decline5]).latches[0]
        assert latch.clear_reason == reason
        assert _classified(latch, [decline5]).disposition != "declined"

    # ... and a decline belonging to a DIFFERENT latch on the same ticker
    foreign = _decision("decline", session=D5, intent_id=9, candidate_id=99999)
    live = _derive().latches[0]
    assert live.is_live is True
    assert _classified(live, [foreign]).disposition != "declined"
