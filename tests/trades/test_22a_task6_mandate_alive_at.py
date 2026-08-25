"""22-A Task 6 -- ``mandate_alive_at``: the probe, and the guards on its inputs.

THE ARC AUTHORS NO SECOND INVALIDATION COMPARISON (plan S0(1)).  This function
DELEGATES the judgment to ``derive_latches`` -- RD's full precedence ladder,
including the invalidation rung -- and adds only the guards that make the
delegated answer trustworthy: the fill session must BE a session, the fire must
be derivable and uniquely so, the drift rung must be forced off and PROVEN off,
the decision ledger must have been READ and its rows must be orderable against
the fill, the judging window must be COVERED, and the frozen values must still
match what the link recorded.

**THE TIE RULE IS THE LADDER'S OWN, IMPORTED RATHER THAN RE-SPELLED.**  A
mandate is alive when the probe returns ``clear_reason is None``, OR when it
returns a NON-``fill`` terminal whose ``clear_session`` EQUALS the fill session.
That second clause is a re-derivation of ``fill.order_key <= nonfill.order_key``
with the subject's own ``(fill_session, rank 0)`` supplied, so it is computed
with the imported ``_CLEAR_REASON_RANK`` / ``_Terminal.order_key`` and never by
a local inequality (#11).  **The ground is a measurement argument, not
leniency:** refusing same-session collapses is SURVIVORSHIP BIAS -- the fastest
loser is the fill that collapses the day it triggers, and ejecting exactly those
trades censors H1's left tail and biases its mean UP.

FROZEN CLOCK.  Every probe is anchored by an explicit ``fill_session``; nothing
here reads the wall clock.
"""
from __future__ import annotations

import dataclasses
from datetime import date
from pathlib import Path

import pytest

from swing.data.db import ensure_schema
from swing.evaluation.dates import session_offset
from swing.latches.constants import PRICE_DP
from swing.latches.reader import build_latch_derivation
from swing.trades.latched_origin import (
    LATCH_PROBE_EVIDENCE_VERSION,
    LatchProbeInvariantError,
    mandate_alive_at,
)
from tests._candidates_barrier_helper import candidates_barrier_lifted
from tests._latch_probe_world_22a import (
    ANCHOR,
    BASE_CLOSES,
    FILL_SESSION,
    PIVOT,
    STOP,
    TICKER,
    accept_and_link,
    order_for_candidate,
    probe_cfg,
    record_decision,
    seed_fire,
    seed_run,
    seed_trade,
    write_closes,
)

NO_EXCLUSIONS: frozenset[int] = frozenset()


def build_world(
    tmp_path: Path,
    name: str,
    *,
    horizon_sessions: int = 30,
    closes: dict[date, float] | None = None,
    initial_stop: float | None = STOP,
    pivot: float | None = PIVOT,
):
    """A fire, an archive, and a config.  Returns ``(conn, cfg, candidate_id)``.

    Dimensions PINNED for every case built on this: the fire's anchor
    (2026-07-20), its pivot/stop, and the archive covering
    ``[anchor, FILL_SESSION - 1]`` with closes ABOVE the stop and BELOW the
    pivot -- so neither an invalidation nor the fold's lifetime rule is what
    ends the mandate in any case that does not name one.
    Dimensions deliberately FREE: the link's own provenance (the probe reads
    only ``candidate_id`` / ``ticker`` / the frozen pair), quantities and the
    broker limit.
    """
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    cfg = probe_cfg(root, horizon_sessions=horizon_sessions)
    conn = ensure_schema(root / "swing.db")
    candidate_id = seed_fire(conn, pivot=pivot, initial_stop=initial_stop)
    conn.commit()
    write_closes(cfg, BASE_CLOSES if closes is None else closes)
    return conn, cfg, candidate_id


def _probe(conn, cfg, order, *, fill_session=FILL_SESSION, exclude=NO_EXCLUSIONS):
    return mandate_alive_at(
        conn, cfg, order=order, fill_session=fill_session,
        exclude_trade_ids=exclude)


# ---------------------------------------------------------------------------
# The fixture's own binding to the emitter
# ---------------------------------------------------------------------------
def test_the_hand_built_order_matches_a_trigger_minted_one(tmp_path) -> None:
    """The synthetic-fixture-vs-production-emitter class, closed at the fixture.

    ``order_for_candidate`` builds the dataclass directly, which is what keeps
    a ``place`` intent out of fixtures that are not about decisions -- so its
    shape must be BOUND to what the minting trigger actually produces, not
    assumed to match it.  Every field but the ids the mint assigns.
    """
    conn, _cfg, candidate_id = build_world(tmp_path, "bind")
    try:
        minted = accept_and_link(
            conn, candidate_id, session=date(2026, 7, 21))
        hand = order_for_candidate(conn, candidate_id)
        assigned = {"link_id", "validity_intent_id", "place_intent_id",
                    "actual_quantity", "actual_limit_price"}
        for field in dataclasses.fields(minted):
            if field.name in assigned:
                continue
            assert getattr(hand, field.name) == getattr(minted, field.name), (
                field.name
            )
        # ...and the two fields the mint copies from the LEDGER are the ledger's.
        assert minted.actual_quantity == 10
        assert minted.freeze_tier == "live_at_acceptance"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# The input guards
# ---------------------------------------------------------------------------
def test_a_weekend_fill_date_is_refused_before_any_probe_runs_case_41b(
        tmp_path) -> None:
    """2026-07-25 is a Saturday.  An implementation skipping the guard walks
    ``session_offset`` from a weekend and shifts the WHOLE probe window, so the
    coverage it then computes is over sessions the mandate never lived in."""
    conn, cfg, candidate_id = build_world(tmp_path, "weekend")
    try:
        order = order_for_candidate(conn, candidate_id)
        verdict = _probe(conn, cfg, order, fill_session=date(2026, 7, 25))
        assert verdict.admitted is False
        assert verdict.decline_reason == "fill_session_not_a_session"
    finally:
        conn.close()


def test_a_probe_before_the_fires_own_session_is_not_derivable_case_41c(
        tmp_path) -> None:
    """The S1.9 shape, and the reason the reason has a case at all: case 27
    only asserted that a WRONG implementation produces ``fire_not_derivable``;
    nothing asserted the CORRECT one does.

    Fires are scoped ``action_session_date <= horizon_session``, so a probe
    as-of 2026-07-17 excludes a fire dated 2026-07-20 entirely.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "prefire")
    try:
        order = order_for_candidate(conn, candidate_id)
        verdict = _probe(conn, cfg, order, fill_session=date(2026, 7, 17))
        assert verdict.admitted is False
        assert verdict.decline_reason == "fire_not_derivable"
    finally:
        conn.close()


def test_two_latches_containing_one_fire_are_ambiguous_case_41d(
        tmp_path, monkeypatch) -> None:
    """The reason created by the R3-06 membership fix, given the case it never had.

    **THE SHAPE IS INJECTED, AND THAT IS STATED RATHER THAN HIDDEN.**  The
    production fold assigns each fire to exactly ONE latch, so no seedable
    database produces two latches whose ``candidate_set``s share a member.  This
    case pins the GUARD -- what the selector does if the fold ever changes --
    not a reachable production state, and it is written this way for the same
    reason case 28d' pins an absence loudly.
    """
    import swing.trades.latched_origin as module

    conn, cfg, candidate_id = build_world(tmp_path, "ambiguous")
    try:
        real = build_latch_derivation(
            conn, cfg, horizon_session_override=FILL_SESSION,
            criteria_lapse_armed_override=False,
            exclude_trade_ids=NO_EXCLUSIONS, strict_decisions=True)
        (latch,) = real.latches
        twin = dataclasses.replace(
            latch,
            identity=dataclasses.replace(
                latch.identity, candidate_id=candidate_id + 5000),
            reconfirmation_candidate_ids=(candidate_id,),
            reconfirmation_sessions=(ANCHOR.isoformat(),),
        )
        doubled = dataclasses.replace(real, latches=(latch, twin))
        monkeypatch.setattr(module, "build_latch_derivation",
                            lambda *a, **k: doubled)

        order = order_for_candidate(conn, candidate_id)
        verdict = _probe(conn, cfg, order)
        assert verdict.admitted is False
        assert verdict.decline_reason == "ambiguous_fire_membership"
    finally:
        conn.close()


def test_an_order_on_a_reconfirmation_fire_is_found_by_membership_case_27(
        tmp_path) -> None:
    """Selection is by ``candidate_set`` MEMBERSHIP, never by identity.

    ``Latch.candidate_set`` is *the opening fire PLUS every re-confirmation*,
    and the fold keeps the OPENING candidate as the identity -- so an accepted
    order placed against a same-pivot RE-CONFIRMATION returns
    ``fire_not_derivable`` under an identity match: a refusal manufactured by
    the lookup rather than by the mandate.

    Dimension PINNED and worth naming: the re-confirmation carries the SAME
    ``initial_stop`` as the opening fire.  Re-confirmation keys on the PIVOT
    alone, so a drifted stop would (correctly) refuse ``frozen_value_drift`` at
    the snapshot cross-check, which compares the link's frozen value against the
    LATCH's -- and the latch's is the OPENING fire's.
    """
    conn, cfg, first = build_world(tmp_path, "reconf")
    try:
        seed_run(conn, 122, date(2026, 7, 22))
        cur = conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) "
            "VALUES (122, ?, 'aplus', 17.02, ?, ?, 'universe')",
            (TICKER, PIVOT, STOP))
        second = int(cur.lastrowid)
        conn.commit()

        derivation = build_latch_derivation(
            conn, cfg, horizon_session_override=FILL_SESSION,
            criteria_lapse_armed_override=False,
            exclude_trade_ids=NO_EXCLUSIONS, strict_decisions=True)
        (latch,) = derivation.latches
        assert latch.identity.candidate_id == first        # NOT the second
        assert second in latch.candidate_set               # ...but it is inside

        order = order_for_candidate(conn, second)
        verdict = _probe(conn, cfg, order)
        assert verdict.admitted is True, verdict.decline_reason
        assert verdict.clear_reason is None
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# The drift rung is FORCED off, and proven off
# ---------------------------------------------------------------------------
def test_the_lapse_rung_is_forced_off_and_a_lapse_arriving_anyway_raises_case_10(
        tmp_path, monkeypatch) -> None:
    """RD's bound: a latch NEVER dies of drift.

    Half one: a config-ARMED lapse-qualifying latch is still ADMITTED, because
    the probe forces the rung off.  Half two: with the force bypassed, the
    ``criteria_lapsed`` reason arriving back RAISES rather than taking a branch
    -- a silent branch would hide that the force did not take.

    The lapse geometry is the shipped T5.6 one, reused rather than re-invented.
    """
    import swing.trades.latched_origin as module
    from tests.latches.test_structural_verdicts import (
        _bars_frame,
        _seed_lapse_geometry,
    )

    from swing.config import load

    root = tmp_path / "lapse"
    root.mkdir(parents=True, exist_ok=True)
    conn = ensure_schema(root / "swing.db")
    try:
        days, _ = _seed_lapse_geometry(conn)
        conn.commit()
        frame = _bars_frame(days, [16.50, 16.20, 15.90, 15.60, 15.30, 15.00])
        import swing.data.ohlcv_archive as archive
        monkeypatch.setattr(
            archive, "resolve_ohlcv_window",
            lambda ticker, **kw: (frame, {"provider": "test"}))

        base = load(Path(__file__).resolve().parents[2] / "swing.config.toml")
        armed = dataclasses.replace(
            base,
            paths=dataclasses.replace(base.paths, prices_cache_dir=root),
            latches=dataclasses.replace(base.latches, criteria_lapse_armed=True))
        # The session AFTER the last failing one: the derivation session is then
        # ``days[5]`` itself, so all five failing sessions are inside the walk
        # AND the archive covers ``[anchor, fill_session - 1]`` exactly.  One
        # session later and the fixture would refuse `aliveness_unverifiable`
        # for a missing bar, passing this test for the wrong reason.
        fill_session = session_offset(days[5], 1)

        # The config REALLY arms the rung: without the force, it lapses.
        unforced = build_latch_derivation(
            conn, armed, horizon_session_override=fill_session).latches[0]
        assert unforced.clear_reason == "criteria_lapsed"

        candidate_id = unforced.identity.candidate_id
        order = order_for_candidate(conn, candidate_id)
        verdict = _probe(conn, armed, order, fill_session=fill_session)
        assert verdict.admitted is True, verdict.decline_reason

        # ...and with the force bypassed, the reason RAISES.
        monkeypatch.setattr(
            module, "build_latch_derivation",
            lambda conn_, cfg_, **kw: build_latch_derivation(
                conn_, cfg_,
                horizon_session_override=kw.get("horizon_session_override"),
                exclude_trade_ids=kw.get("exclude_trade_ids"),
                strict_decisions=kw.get("strict_decisions", False)))
        with pytest.raises(LatchProbeInvariantError):
            _probe(conn, armed, order, fill_session=fill_session)
    finally:
        conn.close()


def test_declined_and_criteria_lapsed_are_distinguished_by_reason_case_11(
        tmp_path, monkeypatch) -> None:
    """``clear_reason``, never ``state``.

    ``swing/latches/service.py`` maps ``declined``, ``horizon`` AND
    ``criteria_lapsed`` all to ``state='horizon_expired'``, so a resolver
    written as ``if latch.state == 'armed'`` would treat a DRIFT-cleared latch
    -- the rung RD's bound says must never kill a mandate -- as dead, and no
    live case would show it because the flag ships disarmed.
    """
    import swing.trades.latched_origin as module

    conn, cfg, candidate_id = build_world(tmp_path, "reason-not-state")
    try:
        record_decision(
            conn, candidate_id=candidate_id, run_id=121, ticker=TICKER,
            detection=ANCHOR, session=date(2026, 7, 22),
            recorded_ts="2026-07-21T18:00:00")
        order = order_for_candidate(conn, candidate_id)

        derivation = build_latch_derivation(
            conn, cfg, horizon_session_override=FILL_SESSION,
            criteria_lapse_armed_override=False,
            exclude_trade_ids=NO_EXCLUSIONS, strict_decisions=True)
        (declined,) = derivation.latches
        assert declined.state == "horizon_expired"      # the collapsed state
        assert declined.clear_reason == "declined"      # the distinguishing fact

        verdict = _probe(conn, cfg, order)
        assert verdict.decline_reason == "mandate_not_alive"
        assert verdict.clear_reason == "declined"

        # The SAME rendered state, a different reason, a different outcome.
        lapsed = dataclasses.replace(
            declined, clear_reason="criteria_lapsed",
            clear_session=date(2026, 7, 22))
        assert lapsed.state == "horizon_expired"
        monkeypatch.setattr(
            module, "build_latch_derivation",
            lambda *a, **k: dataclasses.replace(derivation, latches=(lapsed,)))
        with pytest.raises(LatchProbeInvariantError):
            _probe(conn, cfg, order)
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# The terminals that refuse
# ---------------------------------------------------------------------------
def test_a_decline_before_the_fill_refuses_case_11b(tmp_path) -> None:
    """Resolver-level, asserting non-admission AND the exact reason and session
    -- a bare "it declined" assertion passes an implementation refusing for any
    reason at all."""
    conn, cfg, candidate_id = build_world(tmp_path, "declined-before")
    try:
        record_decision(
            conn, candidate_id=candidate_id, run_id=121, ticker=TICKER,
            detection=ANCHOR, session=date(2026, 7, 22),
            recorded_ts="2026-07-21T18:00:00")
        verdict = _probe(conn, cfg, order_for_candidate(conn, candidate_id))
        assert verdict.admitted is False
        assert verdict.decline_reason == "mandate_not_alive"
        assert verdict.clear_reason == "declined"
        assert verdict.clear_session == date(2026, 7, 22)
    finally:
        conn.close()


def test_a_supersession_before_the_fill_refuses_case_11c(tmp_path) -> None:
    """A DIFFERENT-pivot later fire re-bases the mandate; the earlier one is
    ``superseded`` at the re-fire's own session."""
    conn, cfg, candidate_id = build_world(tmp_path, "superseded-before")
    try:
        seed_run(conn, 123, date(2026, 7, 23))
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) "
            "VALUES (123, ?, 'aplus', 17.44, 19.90, 16.10, 'universe')",
            (TICKER,))
        conn.commit()
        verdict = _probe(conn, cfg, order_for_candidate(conn, candidate_id))
        assert verdict.admitted is False
        assert verdict.decline_reason == "mandate_not_alive"
        assert verdict.clear_reason == "superseded"
        assert verdict.clear_session == date(2026, 7, 23)
    finally:
        conn.close()


def test_a_fill_past_the_horizon_refuses_case_16(tmp_path) -> None:
    """A resting buy-stop that fills after its window closed filled OUTSIDE the
    window the framework declared for it, so "labels from the fire" would
    attribute a trade to a mandate whose own horizon had shut.  Fail-CLOSED,
    declared, and routed to RD as a reading rather than presented as his."""
    conn, cfg, candidate_id = build_world(
        tmp_path, "horizon-past", horizon_sessions=3)
    try:
        expiry = session_offset(ANCHOR, 3)
        assert expiry < FILL_SESSION
        verdict = _probe(conn, cfg, order_for_candidate(conn, candidate_id))
        assert verdict.admitted is False
        assert verdict.decline_reason == "mandate_not_alive"
        assert verdict.clear_reason == "horizon"
        assert verdict.clear_session == expiry
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# The same-session tie -- harvest H1, and RD's uniform fill-wins bound
# ---------------------------------------------------------------------------
def test_a_horizon_expiry_on_the_fill_session_admits_case_28a(tmp_path) -> None:
    """A resting buy-stop filling on the 30th session of a 30-session window is
    not exotic; it is the ordinary way a horizon case resolves.  The shipped
    ladder ranks a fill at 0 so it TAKES the tie -- *"you cannot decline a
    filled mandate, and the same for an invalidation or an expiry landing that
    day"* -- and this arc imports that rule rather than writing a stricter one.
    """
    conn, cfg, candidate_id = build_world(
        tmp_path, "tie-horizon", horizon_sessions=5)
    try:
        assert session_offset(ANCHOR, 5) == FILL_SESSION
        verdict = _probe(conn, cfg, order_for_candidate(conn, candidate_id))
        assert verdict.admitted is True, verdict.decline_reason
        assert verdict.clear_reason == "horizon"
        assert verdict.clear_session == FILL_SESSION
        assert (verdict.probe_evidence["admission_basis"]
                == "subject_fill_wins_same_session_tie")
    finally:
        conn.close()


def test_a_decline_on_the_fill_session_admits_case_28b(tmp_path) -> None:
    """The decline is FOR the fill session's mandate and was RECORDED the
    evening before -- the production shape, and the one the as-of rule permits.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "tie-declined")
    try:
        record_decision(
            conn, candidate_id=candidate_id, run_id=121, ticker=TICKER,
            detection=ANCHOR, session=FILL_SESSION,
            recorded_ts="2026-07-24T18:00:00")
        verdict = _probe(conn, cfg, order_for_candidate(conn, candidate_id))
        assert verdict.admitted is True, verdict.decline_reason
        assert verdict.clear_reason == "declined"
        assert verdict.clear_session == FILL_SESSION
        assert (verdict.probe_evidence["admission_basis"]
                == "subject_fill_wins_same_session_tie")
    finally:
        conn.close()


def test_a_supersession_on_the_fill_session_admits_case_28c(tmp_path) -> None:
    """A re-fire dated on the fill session re-bases the mandate that same day;
    the fill still happened against the mandate that was live when it triggered.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "tie-superseded")
    try:
        seed_run(conn, 124, FILL_SESSION)
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) "
            "VALUES (124, ?, 'aplus', 17.31, 19.90, 16.10, 'universe')",
            (TICKER,))
        conn.commit()
        verdict = _probe(conn, cfg, order_for_candidate(conn, candidate_id))
        assert verdict.admitted is True, verdict.decline_reason
        assert verdict.clear_reason == "superseded"
        assert verdict.clear_session == FILL_SESSION
    finally:
        conn.close()


def test_the_tie_does_not_widen_to_the_session_before_case_28e(
        tmp_path) -> None:
    """Each of the THREE reachable tie branches, dated ONE session EARLIER,
    must REFUSE.  Without this, *"admit on any terminal at-or-after the
    anchor"* also passes 28a-28c and the rule silently loses its boundary.
    """
    # horizon, one session early
    conn, cfg, candidate_id = build_world(
        tmp_path, "nowiden-horizon", horizon_sessions=4)
    try:
        assert session_offset(ANCHOR, 4) == date(2026, 7, 24)
        verdict = _probe(conn, cfg, order_for_candidate(conn, candidate_id))
        assert verdict.decline_reason == "mandate_not_alive"
        assert (verdict.clear_reason, verdict.clear_session) == (
            "horizon", date(2026, 7, 24))
    finally:
        conn.close()

    # declined, one session early
    conn, cfg, candidate_id = build_world(tmp_path, "nowiden-declined")
    try:
        record_decision(
            conn, candidate_id=candidate_id, run_id=121, ticker=TICKER,
            detection=ANCHOR, session=date(2026, 7, 24),
            recorded_ts="2026-07-23T18:00:00")
        verdict = _probe(conn, cfg, order_for_candidate(conn, candidate_id))
        assert verdict.decline_reason == "mandate_not_alive"
        assert (verdict.clear_reason, verdict.clear_session) == (
            "declined", date(2026, 7, 24))
    finally:
        conn.close()

    # superseded, one session early
    conn, cfg, candidate_id = build_world(tmp_path, "nowiden-superseded")
    try:
        seed_run(conn, 125, date(2026, 7, 24))
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) "
            "VALUES (125, ?, 'aplus', 17.31, 19.90, 16.10, 'universe')",
            (TICKER,))
        conn.commit()
        verdict = _probe(conn, cfg, order_for_candidate(conn, candidate_id))
        assert verdict.decline_reason == "mandate_not_alive"
        assert (verdict.clear_reason, verdict.clear_session) == (
            "superseded", date(2026, 7, 24))
    finally:
        conn.close()


def test_another_trades_fill_on_the_fill_session_still_refuses_case_28f(
        tmp_path) -> None:
    """``fill`` is EXCLUDED from the widening.

    With the subject excluded, a ``fill`` terminal on the fill session is
    ANOTHER trade's fill -- a genuine consumption, refused as such.  It refuses
    ``mandate_not_alive`` rather than ``mandate_already_consumed``: that other
    trade carries a DIFFERENT (here absent) broker order id, so rung 6's
    ORDER-LINKED consumption never fires, and expecting the consumption reason
    would not discriminate.

    **The refusal NAMES the matched trade and its ``fill_link_basis``**, because
    the ``fill`` terminal is weaker evidence than it looks: ``_match_fill``'s
    windowed rung matches ANY NULL-candidate, same-ticker, in-zone entry and
    never inspects a broker order id.  A heuristic-driven refusal must be
    visible as one rather than presented as proof.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "other-fill")
    try:
        seed_trade(conn, trade_id=77, entry_date=FILL_SESSION, price=18.50)
        conn.commit()
        verdict = _probe(conn, cfg, order_for_candidate(conn, candidate_id))
        assert verdict.admitted is False
        assert verdict.decline_reason == "mandate_not_alive"
        assert verdict.clear_reason == "fill"
        assert verdict.clear_session == FILL_SESSION
        assert verdict.probe_evidence["fill_terminal_trade_id"] == 77
        assert verdict.probe_evidence["fill_terminal_link_basis"] == "windowed"
    finally:
        conn.close()


def test_a_sub_stop_close_on_the_fill_session_is_never_seen_case_28d_prime(
        tmp_path) -> None:
    """**THIS CASE PINS AN ABSENCE, AND THE ABSENCE IS THE MECHANISM.**

    The probe's ``bar_bound`` is ``session_offset(fill_session, -1)`` -- the
    session BEFORE the fill -- so a breaching close dated ON the fill session is
    never loaded and never judged, and the probe returns ``clear_reason is
    None``.  Under RD's uniform fill-wins bound that is the CORRECT admit, and
    it is delivered structurally with NO comparison authored by this arc.

    **If a future change widens ``bar_bound`` to include the fill session, this
    case FAILS -- loudly, on the case that would otherwise silently start
    REFUSING case 5b and re-introducing the survivorship bias RD's ruling exists
    to prevent.**  The tie rule's scope is then revisited deliberately rather
    than gaining a fourth branch by accident.
    """
    closes = dict(BASE_CLOSES)
    closes[FILL_SESSION] = round(STOP - 0.05, 2)      # 14.83, a real breach
    conn, cfg, candidate_id = build_world(
        tmp_path, "unreachable-invalidation", closes=closes)
    try:
        derivation = build_latch_derivation(
            conn, cfg, horizon_session_override=FILL_SESSION,
            criteria_lapse_armed_override=False,
            exclude_trade_ids=NO_EXCLUSIONS, strict_decisions=True)
        (latch,) = derivation.latches
        assert latch.clear_reason is None               # the bar was never seen
        assert FILL_SESSION not in derivation.archive_closes[TICKER]

        verdict = _probe(conn, cfg, order_for_candidate(conn, candidate_id))
        assert verdict.admitted is True, verdict.decline_reason
        assert verdict.probe_evidence["admission_basis"] == "armed"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# Coverage -- absence of a breach is not proof of no breach
# ---------------------------------------------------------------------------
def test_an_unreadable_archive_is_not_a_survival_case_7(
        tmp_path, monkeypatch) -> None:
    """``archive_status='unavailable'`` means the read RAISED -- OUR IGNORANCE.
    Admitting on ``clear_reason is None`` alone would treat it as evidence."""
    conn, cfg, candidate_id = build_world(tmp_path, "archive-unavailable")

    def _boom(ticker, **kw):
        raise OSError("archive unreadable")

    import swing.data.ohlcv_archive as archive
    monkeypatch.setattr(archive, "resolve_ohlcv_window", _boom)
    try:
        verdict = _probe(conn, cfg, order_for_candidate(conn, candidate_id))
        assert verdict.admitted is False
        assert verdict.decline_reason == "aliveness_unverifiable"
        assert verdict.archive_status == "unavailable"
    finally:
        conn.close()


def test_an_ok_archive_with_an_interior_hole_is_not_covered_case_7b(
        tmp_path) -> None:
    """``ok`` does NOT imply COMPLETE.  The reader permits an empty or partial
    bar set on a successful read and ``_eligible_bars`` judges only the sessions
    it was handed, so an ``ok`` archive missing an INTERIOR session silently
    hides a breach.  **Omitting per-session completeness passes case 7 and fails
    only this one.**"""
    closes = {s: c for s, c in BASE_CLOSES.items() if s != date(2026, 7, 22)}
    conn, cfg, candidate_id = build_world(
        tmp_path, "interior-hole", closes=closes)
    try:
        verdict = _probe(conn, cfg, order_for_candidate(conn, candidate_id))
        assert verdict.admitted is False
        assert verdict.decline_reason == "aliveness_unverifiable"
        assert verdict.archive_status == "ok"
        assert verdict.probe_evidence["coverage"]["missing_sessions"] == [
            "2026-07-22"]
    finally:
        conn.close()


def test_a_fill_on_the_anchor_session_needs_no_bars_case_8(tmp_path) -> None:
    """The judging window is EMPTY: no session has elapsed since the fire, so
    the mandate is alive BY CONSTRUCTION.  This is the common good case -- fire
    tonight, fill at tomorrow's open -- and a naive "require bars" rule refuses
    exactly it."""
    conn, cfg, candidate_id = build_world(tmp_path, "empty-window", closes={})
    try:
        verdict = _probe(
            conn, cfg, order_for_candidate(conn, candidate_id),
            fill_session=ANCHOR)
        assert verdict.admitted is True, verdict.decline_reason
        assert verdict.window_empty is True
        assert verdict.probe_evidence["coverage"] == {"window_empty": True}
    finally:
        conn.close()


def test_coverage_comes_from_the_derivations_own_bars_case_24(
        tmp_path, monkeypatch) -> None:
    """ONE READ, ONE WORLD.

    The parquet is MUTABLE, so a coverage computed from a SECOND
    ``load_bars_with_status`` call can report a complete window over bars the
    fold never judged -- a split-world FALSE ADMISSION.  Here the first read
    (the derivation's) returns a GAPPED frame and any later read would return a
    complete one: a second-read implementation ADMITS, and the call counter
    proves no second read happened.
    """
    import pandas as pd

    import swing.data.ohlcv_archive as archive

    conn, cfg, candidate_id = build_world(tmp_path, "one-read", closes={})

    def _frame(sessions):
        return pd.DataFrame([
            {"asof_date": s.isoformat(), "open": c, "high": c + 0.1,
             "low": c - 0.1, "close": c, "volume": 100.0}
            for s, c in sorted(sessions.items())
        ])

    gapped = _frame({s: c for s, c in BASE_CLOSES.items()
                     if s != date(2026, 7, 22)})
    complete = _frame(BASE_CLOSES)
    calls: list[str] = []

    def _counting(ticker, **kw):
        calls.append(ticker)
        return (gapped if len(calls) == 1 else complete,
                {"provider": "test"})

    monkeypatch.setattr(archive, "resolve_ohlcv_window", _counting)
    try:
        verdict = _probe(conn, cfg, order_for_candidate(conn, candidate_id))
        assert verdict.admitted is False
        assert verdict.decline_reason == "aliveness_unverifiable"
        assert len(calls) == 1, (
            f"the probe read the archive {len(calls)} times; coverage must come "
            f"from derivation.archive_closes, never from a second read")
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# The snapshot cross-check -- RD's gate, enforced at the comparison
# ---------------------------------------------------------------------------
def test_a_moved_invalidation_refuses_case_9(tmp_path) -> None:
    """The fire's ``initial_stop`` moved after the link was minted.

    **THE MUTATION IS PLANTED THROUGH THE BARRIER-LIFT HELPER AND THE CANONICAL
    TRIGGER IS RESTORED BYTE-IDENTICALLY BEFORE THE PROBE RUNS** (inherited
    finding 22A-R9-08).  Rung 9 refuses ``barrier_not_installed`` whenever a
    barrier is absent OR ALTERED, so a fixture that dropped the trigger and left
    it down -- or restored an approximation -- would test the integrity guard
    instead of ``frozen_value_drift``.  A byte-identical restore passes the body
    check BY CONSTRUCTION, which is the point.
    """
    from swing.data.repos.candidates_immutability_epoch import barrier_installed

    conn, cfg, candidate_id = build_world(tmp_path, "drift-stop")
    try:
        order = order_for_candidate(conn, candidate_id)
        assert order.frozen_invalidation == STOP
        with candidates_barrier_lifted(conn):
            conn.execute("UPDATE candidates SET initial_stop = ? WHERE id = ?",
                         (14.90, candidate_id))
        conn.commit()
        assert barrier_installed(conn) is True

        verdict = _probe(conn, cfg, order)
        assert verdict.admitted is False
        assert verdict.decline_reason == "frozen_value_drift"
    finally:
        conn.close()


def test_a_moved_pivot_refuses_case_9b(tmp_path) -> None:
    """The same cross-check on the OTHER operand.  An implementation checking
    only the stop admits this and looks correct."""
    from swing.data.repos.candidates_immutability_epoch import barrier_installed

    conn, cfg, candidate_id = build_world(tmp_path, "drift-pivot")
    try:
        order = order_for_candidate(conn, candidate_id)
        assert order.frozen_pivot == PIVOT
        with candidates_barrier_lifted(conn):
            conn.execute("UPDATE candidates SET pivot = ? WHERE id = ?",
                         (18.40, candidate_id))
        conn.commit()
        assert barrier_installed(conn) is True

        verdict = _probe(conn, cfg, order)
        assert verdict.admitted is False
        assert verdict.decline_reason == "frozen_value_drift"
    finally:
        conn.close()


def test_a_null_frozen_value_refuses_at_the_resolver_case_41e(
        tmp_path) -> None:
    """The junk-fire link, carried through to admission.

    Task 2's migration test proved the minting trigger does NOT RAISE on a junk
    fire -- cohort bookkeeping must never block a money-bearing operation -- and
    lands NULL frozen values.  **Nothing proved the resolver then REFUSES**, and
    that is this case.

    The NULL check runs BEFORE the probe deliberately: a link with no frozen
    value can never be cross-checked whatever the probe answers, and a junk fire
    is DEGRADED by ``derive_latches`` so a later check would report
    ``fire_not_derivable`` and hide the real defect behind a symptom.
    """
    conn, cfg, candidate_id = build_world(
        tmp_path, "junk-fire", initial_stop=None)
    try:
        minted = accept_and_link(conn, candidate_id, session=date(2026, 7, 21))
        conn.commit()
        assert minted.frozen_pivot == PIVOT
        assert minted.frozen_invalidation is None      # the trigger's CASE

        verdict = _probe(conn, cfg, minted)
        assert verdict.admitted is False
        assert verdict.decline_reason == "frozen_value_unavailable"
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# The decision ledger -- read, and orderable
# ---------------------------------------------------------------------------
def test_an_unreadable_decision_ledger_refuses_case_19(
        tmp_path, monkeypatch) -> None:
    """``load_decision_intents`` returns ``{}`` on ANY read failure and ``Latch``
    exposes no decision-ledger status, so ``clear_reason is None`` cannot be
    distinguished from *"the decline ledger could not be read"* -- and a
    DECLINED mandate would be admitted.  **This test passes trivially against
    today's silent ``{}``**, which is why the control leg below is not
    decoration."""
    import swing.data.repos.latch_order_intents as intents_repo

    conn, cfg, candidate_id = build_world(tmp_path, "ledger-unreadable")
    try:
        order = order_for_candidate(conn, candidate_id)
        assert _probe(conn, cfg, order).admitted is True      # the control

        def _boom(conn_, *, candidate_id):
            raise RuntimeError("the ledger could not be read")

        monkeypatch.setattr(intents_repo, "list_intents_for_latch", _boom)
        verdict = _probe(conn, cfg, order)
        assert verdict.admitted is False
        assert verdict.decline_reason == "decision_evidence_unavailable"
    finally:
        conn.close()


def test_decisions_are_ordered_against_the_fill_by_recorded_ts_case_20(
        tmp_path) -> None:
    """``action_session_date`` says WHICH SESSION'S MANDATE; ``recorded_ts``
    says WHEN THE ANSWER HAPPENED (migration 0033 draws exactly this
    distinction), and ``admissible_decisions`` filters on the FIRST while
    ``_order_key`` lets a LATER-RECORDED row win.  **So a ``place`` recorded
    AFTER the fill can outrank an earlier ``decline`` and make a historical
    probe admit a mandate that was dead when it filled.**

    The comparison is date-to-date in ONE domain -- ``recorded_ts`` is naive
    LOCAL and the entry carries only a DATE -- deliberately coarse, and it can
    only ever REFUSE.
    """
    # (a) recorded AFTER the fill
    conn, cfg, candidate_id = build_world(tmp_path, "decision-after")
    try:
        record_decision(
            conn, candidate_id=candidate_id, run_id=121, ticker=TICKER,
            detection=ANCHOR, session=date(2026, 7, 22),
            recorded_ts="2026-07-21T18:00:00")
        record_decision(
            conn, candidate_id=candidate_id, run_id=121, ticker=TICKER,
            detection=ANCHOR, session=date(2026, 7, 24), kind="place",
            recorded_ts="2026-07-28T09:00:00")
        verdict = _probe(conn, cfg, order_for_candidate(conn, candidate_id))
        assert verdict.admitted is False
        assert verdict.decline_reason == "decision_evidence_post_dates_fill"
    finally:
        conn.close()

    # (b) recorded ON the fill session -- UNORDERABLE against a date-only fill
    conn, cfg, candidate_id = build_world(tmp_path, "decision-on")
    try:
        record_decision(
            conn, candidate_id=candidate_id, run_id=121, ticker=TICKER,
            detection=ANCHOR, session=FILL_SESSION, kind="place",
            recorded_ts=f"{FILL_SESSION.isoformat()}T10:00:00")
        verdict = _probe(conn, cfg, order_for_candidate(conn, candidate_id))
        assert verdict.admitted is False
        assert verdict.decline_reason == "decision_ordering_ambiguous"
    finally:
        conn.close()

    # (c) the control: recorded strictly BEFORE, and it admits
    conn, cfg, candidate_id = build_world(tmp_path, "decision-before")
    try:
        record_decision(
            conn, candidate_id=candidate_id, run_id=121, ticker=TICKER,
            detection=ANCHOR, session=date(2026, 7, 22), kind="place",
            recorded_ts="2026-07-21T18:00:00")
        verdict = _probe(conn, cfg, order_for_candidate(conn, candidate_id))
        assert verdict.admitted is True, verdict.decline_reason
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# The evidence blob -- "passed" and "never ran" must be distinguishable
# ---------------------------------------------------------------------------
def test_the_admission_evidence_records_every_probe_input_and_verdict(
        tmp_path) -> None:
    """The standing rule (plan S4.3): *if a clause can REFUSE an admission, the
    evidence blob records the INPUT it judged and the VERDICT it reached, or
    "passed" and "never ran" are indistinguishable at audit.*

    The key set is asserted against migration 0037's own closure list, read off
    disk, minus ``$.authorization`` -- which the AUTHORIZER fills, not the
    probe.  A hand-typed expected set is the same instrument as the count it
    replaced.
    """
    migration = (
        Path(__file__).resolve().parents[2]
        / "swing" / "data" / "migrations" / "0037_latch_order_mandate_links.sql"
    ).read_text(encoding="utf-8")
    start = migration.index("json_remove(NEW.cited_latch_probe_json,")
    closure = migration[start:migration.index("= '{}'", start)]
    expected = {
        chunk.split("'")[1].removeprefix("$.")
        for chunk in closure.split(",")
        if "'$." in chunk
    } - {"authorization"}

    conn, cfg, candidate_id = build_world(tmp_path, "evidence")
    try:
        verdict = _probe(conn, cfg, order_for_candidate(conn, candidate_id))
        assert verdict.admitted is True, verdict.decline_reason
        assert set(verdict.probe_evidence) == expected

        evidence = verdict.probe_evidence
        assert evidence["evidence_version"] == LATCH_PROBE_EVIDENCE_VERSION
        assert evidence["fire_candidate_id"] == candidate_id
        assert evidence["ticker"] == TICKER
        assert evidence["fill_session"] == FILL_SESSION.isoformat()
        assert evidence["horizon_session"] == FILL_SESSION.isoformat()
        # bars_through is the DERIVATION's prior exchange session, NOT the fill
        # session -- the two were collapsed into one `probe_session` with two
        # incompatible definitions, and a truthful correction could not have
        # been written under it.
        assert evidence["bars_through"] == "2026-07-24"
        assert evidence["clear_reason"] is None
        assert evidence["clear_session"] is None
        assert evidence["admission_basis"] == "armed"
        assert evidence["criteria_lapse_forced_off"] == 1
        assert evidence["archive_status"] == "ok"
        assert evidence["frozen_invalidation_raw"] == STOP
        assert evidence["live_invalidation_raw"] == STOP
        assert evidence["frozen_pivot_raw"] == PIVOT
        assert evidence["live_pivot_raw"] == PIVOT
        assert evidence["invalidation_equal_at_dp"] == 1
        assert evidence["pivot_equal_at_dp"] == 1
        assert evidence["compare_dp"] == PRICE_DP
        assert evidence["coverage"]["missing_sessions"] == []
        assert evidence["coverage"]["expected_sessions"] == [
            s.isoformat() for s in sorted(BASE_CLOSES)]
        assert (evidence["coverage"]["observed_sessions"]
                == evidence["coverage"]["expected_sessions"])
    finally:
        conn.close()


def test_the_tie_rule_inherits_the_ladders_ranks_rather_than_copying_them(
) -> None:
    """The two properties ``_fill_wins`` actually depends on, pinned AT the
    ladder.

    ``latched_origin`` holds NO copy of the rank table -- it imports
    ``_Terminal`` and lets ``order_key`` consult ``_CLEAR_REASON_RANK`` -- so
    the inheritance is by construction.  What a construction cannot pin is
    whether the ladder's ranks still MEAN what the tie rule assumes, and that is
    what these two assertions do: if ``fill`` ever stopped being the strict
    minimum, a fill dated ON a terminal's session would silently start LOSING
    the tie, and every same-session collapse would be refused again.
    """
    from swing.latches.models import LATCH_CLEAR_REASONS
    from swing.latches.service import _CLEAR_REASON_RANK

    assert _CLEAR_REASON_RANK["fill"] == 0
    assert all(
        rank > 0 for reason, rank in _CLEAR_REASON_RANK.items()
        if reason != "fill"
    )
    # ...and the vocabulary and its precedence cannot drift apart.
    assert set(_CLEAR_REASON_RANK) == set(LATCH_CLEAR_REASONS)


def test_the_exclusion_set_is_a_required_keyword() -> None:
    """No default.  A defaulted exclusion set is how the 22A-AR-04 defect comes
    back: the correction probe would silently see the SUBJECT's own fill and
    answer ``clear_reason='fill'`` for the mandate it is being asked about."""
    import inspect

    parameter = inspect.signature(mandate_alive_at).parameters["exclude_trade_ids"]
    assert parameter.kind is inspect.Parameter.KEYWORD_ONLY
    assert parameter.default is inspect.Parameter.empty
