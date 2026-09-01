"""22-A Task 6a -- RUNG 8, and the competitor population is THREE-VALUED.

WHY A TASK OF ITS OWN.  Rung 8 must evaluate each competitor THROUGH
``mandate_alive_at``, which task 6 delivers, so it could not have run at task
4's point in the ladder (review 22A-R7-09).  Task 4 ships the seam as a
PARAMETER and this module supplies the callable, so the rung is claimed by
exactly ONE task -- the axis 22A-R8-08 found claimed twice.

THE RULE, and only one of the three states is dropped:
    PROVEN DEAD  -> not a competitor
    PROVEN LIVE  -> competitor -> ``ambiguous_ticker_orders``
    UNPROVABLE   -> ``competitor_liveness_unverifiable``
An exclude-the-unresolved implementation reads an unprovable competitor as an
ABSENT one and admits the selected order while two live mandates may have
existed.  Cases 23b-23d plant each unprovable shape and it ADMITS all three.

THE FIXTURES ARE BUILT ON THE FOLD'S REAL TOPOLOGY, MEASURED (2026-08-25).
Two same-ticker fires do NOT produce two independent latches: a LATER fire at
the SAME pivot folds in as a RE-CONFIRMATION of the running latch, and a later
fire at a DIFFERENT pivot SUPERSEDES the earlier one.  Executed against the
shipped ``derive_latches``, fires at (07-17, 17.50) and (07-20, 18.34) yield
``latch[07-17] superseded 2026-07-20`` and ``latch[07-20] reason None``.  My
first draft gave each rival its own pivot AND expected two independent live
mandates; every fixture refused ``frozen_value_drift`` instead, because a
re-confirmation latch keeps the OPENING fire's pivot and stop while the link
freezes its OWN fire's.  So:
    * a PROVEN-DEAD rival is an EARLIER fire the subject's fire superseded;
    * a PROVEN-LIVE rival is a LATER RE-CONFIRMATION at the SAME pivot AND
      the same stop (the stop matters -- a re-confirmation carrying a
      different stop drifts against the latch's opening value).

COMPETITOR SESSION RELATIONSHIP IS PINNED, NOT FREE (plan S3.8): each fixture
below states its rival's anchor, pivot and stop, and what makes it dead, live
or unprovable.

FROZEN CLOCK throughout.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

from swing.data.db import ensure_schema, open_connection, run_migrations
from swing.data.models import FREEZE_TIER_PRE_BARRIER
from swing.trades.latched_origin import (
    AcceptedLatchOrder,
    authorize_accepted_order,
    competitor_liveness_rung,
    find_accepted_latch_order,
    mandate_alive_at,
)
from tests._latch_probe_world_22a import (
    ANCHOR,
    BASE_CLOSES,
    BROKER_ORDER_ID,
    FILL_SESSION,
    PIVOT,
    STOP,
    TICKER,
    probe_cfg,
    seed_fire,
    seed_trade,
    write_closes,
)

NO_EXCLUSIONS: frozenset[int] = frozenset()

# The place/validity pair is recorded the session BEFORE the fill: a `place` is
# a DECISION row and the probe's as-of rule refuses one recorded on or after
# the fill session.
ACCEPT_SESSION = date(2026, 7, 24)
GOOD_PRICE = 18.50          # inside [PIVOT, mandate cap] for the 18.34 pivot
GOOD_SHARES = 2
GOOD_ORIGIN = "schwab_auto"

# The EARLIER, DIFFERENT-pivot fire the subject's own fire supersedes.  Its
# pivot/stop are stated because they are what make it a SEPARATE latch rather
# than a re-confirmation, and its own stop is never breached over BASE_CLOSES
# -- so the terminal it carries is `superseded`, which is the state the case
# names, and not an invalidation arriving by accident.
DEAD_SESSION = date(2026, 7, 17)
DEAD_PIVOT = 17.50
DEAD_STOP = 13.00


def build_world(tmp_path: Path, name: str, *, closes=None, pre_barrier=False):
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    cfg = probe_cfg(root)
    if pre_barrier:
        conn = open_connection(root / "swing.db")
        run_migrations(conn, target_version=36)
        subject = seed_fire(conn)
        conn.commit()
        run_migrations(conn, target_version=37, backup_dir=root / "bak")
    else:
        conn = ensure_schema(root / "swing.db")
        subject = seed_fire(conn)
        conn.commit()
    write_closes(cfg, BASE_CLOSES if closes is None else closes)
    return conn, cfg, subject


def dead_rival_fire(conn, *, run_id: int) -> int:
    """An EARLIER, different-pivot fire -- SUPERSEDED by the subject's own."""
    return seed_fire(conn, run_id=run_id, action_session=DEAD_SESSION,
                     ticker=TICKER, pivot=DEAD_PIVOT, initial_stop=DEAD_STOP)


def live_rival_fire(conn, *, run_id: int, session: date) -> int:
    """A LATER RE-CONFIRMATION at the SAME pivot AND stop -- one latch, alive.

    The stop must match too: a re-confirmation latch keeps the OPENING fire's
    values, so a rival whose own stop differs would refuse ``frozen_value_drift``
    at its snapshot cross-check and read as UNPROVABLE rather than LIVE.
    """
    return seed_fire(conn, run_id=run_id, action_session=session,
                     ticker=TICKER, pivot=PIVOT, initial_stop=STOP)


def accept(conn, candidate_id, *, key: str, broker_order_id: str,
           session: date = ACCEPT_SESSION, **validity_over
           ) -> AcceptedLatchOrder:
    """Place + accept on one fire, and read the MINTED link back through the
    PRODUCTION lookup."""
    from tests._latch_link_fixtures_22a import (
        insert_intent, place_row, validity_row,
    )

    run_id, ticker, detection = conn.execute(
        "SELECT c.evaluation_run_id, c.ticker, e.action_session_date "
        "FROM candidates c JOIN evaluation_runs e ON e.id = c.evaluation_run_id "
        "WHERE c.id = ?", (candidate_id,)).fetchone()
    common = {
        "evaluation_run_id": int(run_id), "ticker": str(ticker),
        "detection_date": str(detection),
        "action_session_date": session.isoformat(),
        "recorded_ts": f"{session.isoformat()}T10:00:00",
    }
    place_id = insert_intent(conn, place_row(
        candidate_id, idempotency_key=f"{key}-place", **common))
    insert_intent(conn, validity_row(
        candidate_id, place_id, key=f"{key}-validity",
        actual_broker_order_id=broker_order_id, **common, **validity_over))
    conn.commit()
    found = [
        o for o in find_accepted_latch_order(conn, broker_order_id=broker_order_id)
        if o.candidate_id == candidate_id
    ]
    assert len(found) == 1, found
    return found[0]


def authorize(conn, cfg, order, *, fill_session=FILL_SESSION,
              exclude=NO_EXCLUSIONS):
    """THE LADDER WITH RUNG 8 WIRED IN -- the composition under test."""
    return authorize_accepted_order(
        conn, cfg, order=order, ticker=TICKER, fill_session=fill_session,
        price=GOOD_PRICE, shares=GOOD_SHARES, fill_origin=GOOD_ORIGIN,
        envelope_symbol=TICKER, exclude_trade_ids=exclude,
        competitor_rung=competitor_liveness_rung)


def _entry_fill(conn, *, fill_id, trade_id, order_id, session):
    conn.execute(
        "INSERT INTO fills (fill_id, trade_id, fill_datetime, action, "
        "quantity, price, rule_based, reconciliation_status, fill_origin, "
        "schwab_source_value_json) VALUES (?, ?, ?, 'entry', 2, 18.10, 0, "
        "'unreconciled', 'schwab_auto', ?)",
        (fill_id, trade_id, f"{session.isoformat()}T14:30:00",
         json.dumps({"schwab_order_id": order_id,
                     "schwab_instrument_symbol": TICKER})))
    conn.commit()


# ===========================================================================
# 4c -- BROKER-ORDER-ID IDENTITY, BOTH LEGS
# ===========================================================================
def test_a_dead_rival_is_dropped_and_its_own_leg_refuses_case_4c_i(
        tmp_path) -> None:
    """CASE 4c-i -- lens clause 1, the PROVEN-DEAD leg.

    Two accepted orders on ONE ticker.  The rival's mandate was SUPERSEDED on
    2026-07-20 -- strictly before the fill -- so it is PROVEN DEAD and dropped:
    the subject ADMITS.  Authorizing the RIVAL's own order refuses
    ``mandate_not_alive`` naming ``superseded``, which is the second leg and is
    what makes this an IDENTITY case rather than a cardinality one.

    Dimensions PINNED: the rival's anchor (2026-07-17), its pivot/stop
    (17.50/13.00 -- a different pivot, which is what makes it a separate latch)
    and its terminal session (2026-07-20, strictly before the fill).  A rival
    whose window also contained the fill was the free dimension that once made
    an identity test pass an identity-IGNORING implementation.

    **THE SECOND LEG IS AT THE LADDER GRAIN S3.4c SPECIFIES, AND THE GRAIN DID
    NOT MOVE** (semantic re-audit 2026-08-31; ruled 2026-09-01).  This
    docstring previously recorded that the ladder answers
    ``ambiguous_ticker_orders`` from the rival's seat and that asserting it
    here would pin the wrong half -- honest at the time, and a resolution
    NOBODY HAD RULED, which is why the audit graded the row UNVERIFIABLE.
    Both refusals were TRUE of that world, because a ladder evaluated from a
    SEAT makes the reason a property of ``(world, seat)``: from the dead
    order's seat the subject is a genuinely proven-LIVE competitor.  Rung 8
    now prefers the MORE SPECIFIC of two true refusals, so S3.4c is satisfied
    as written, at the ladder grain, with no grain change -- and the probe leg
    is kept beside it, so the ladder cannot pass by returning a string that
    merely matches.
    """
    conn, cfg, subject = build_world(tmp_path, "4ci")
    try:
        rival = dead_rival_fire(conn, run_id=140)
        conn.commit()
        subject_order = accept(conn, subject, key="4ci-s",
                               broker_order_id=BROKER_ORDER_ID)
        rival_order = accept(conn, rival, key="4ci-r",
                             broker_order_id="4ci-rival")

        verdict = authorize(conn, cfg, subject_order)
        assert verdict.admitted is True, verdict.decline_reason
        assert verdict.probe_evidence["authorization"][
            "rung8_competitor_link_ids"]["input"] == [rival_order.link_id]

        # THE SECOND LEG, AT THE LADDER GRAIN S3.4c SPECIFIES.
        ladder = authorize(conn, cfg, rival_order)
        assert ladder.admitted is False, (
            "the more-specific-reason rule must never convert a refusal into "
            "an admission")
        assert ladder.decline_reason == "mandate_not_alive"
        assert ladder.clear_reason == "superseded"
        assert ladder.clear_session == ANCHOR

        # AND THE PROBE AGREES.  Kept beside the ladder leg so the ladder
        # cannot pass by producing a reason string that merely matches: the
        # terminal it reports comes from the authority that derived it.
        other = mandate_alive_at(
            conn, cfg, order=rival_order, fill_session=FILL_SESSION,
            exclude_trade_ids=NO_EXCLUSIONS)
        assert other.decline_reason == "mandate_not_alive"
        assert other.clear_reason == "superseded"
        assert other.clear_session == ANCHOR
    finally:
        conn.close()


def test_two_live_orders_on_one_ticker_are_ambiguous_case_4c_ii(
        tmp_path) -> None:
    """CASE 4c-ii -- the PROVEN-LIVE leg.  ``ambiguous_ticker_orders``.

    The rival is a RE-CONFIRMATION at the same pivot AND stop, so both orders
    address the SAME running mandate and both are alive at the fill session --
    the envelope cannot say which one this fill came from.
    """
    conn, cfg, subject = build_world(tmp_path, "4cii")
    try:
        rival = live_rival_fire(conn, run_id=141, session=date(2026, 7, 22))
        conn.commit()
        subject_order = accept(conn, subject, key="4cii-s",
                               broker_order_id=BROKER_ORDER_ID)
        accept(conn, rival, key="4cii-r", broker_order_id="4cii-rival")
        assert authorize(conn, cfg, subject_order).decline_reason == (
            "ambiguous_ticker_orders")
    finally:
        conn.close()


def test_a_later_refire_order_also_competes_case_15f(tmp_path) -> None:
    """CASE 15f -- lens clause 17b, PER-TICKER CARDINALITY.

    The distinction from 4c-ii, which reaches the same reason by the same
    route: here the rival's order is ACCEPTED on a different session from the
    subject's.  An implementation scoping the competitor scan to one
    acceptance session -- or to one evaluation run -- passes 4c-ii and fails
    this one.
    """
    conn, cfg, subject = build_world(tmp_path, "15f")
    try:
        rival = live_rival_fire(conn, run_id=142, session=date(2026, 7, 22))
        conn.commit()
        subject_order = accept(conn, subject, key="15f-s",
                               broker_order_id=BROKER_ORDER_ID)
        accept(conn, rival, key="15f-r", broker_order_id="15f-rival",
               session=date(2026, 7, 23))
        assert authorize(conn, cfg, subject_order).decline_reason == (
            "ambiguous_ticker_orders")
    finally:
        conn.close()


# ===========================================================================
# 23 -- THE POPULATION IS FILTERED BEFORE IT IS JUDGED
# ===========================================================================
def test_superseded_consumed_and_dead_rivals_all_drop_case_23(
        tmp_path) -> None:
    """CASE 23 -- lens clause 26.  ADMIT, not ``ambiguous_ticker_orders``.

    THREE rivals, each dropped by a DIFFERENT filter, so an implementation
    missing any one of them refuses:
      * a SUPERSEDED-VALIDITY link -- a later validity child of the same place
        replaced the broker's answer, so the link records what was said before
        the answer changed.  It never reaches the probe;
      * a CONSUMED link -- another trade's entry fill carries its order id.  It
        never reaches the probe either;
      * a PROVEN-DEAD link -- the superseded earlier mandate, which DOES reach
        the probe and is dropped on its verdict.
    The scanned population therefore contains EXACTLY the dead one, which is
    the assertion below: it distinguishes "filtered out" from "judged and
    dropped", two outcomes a bare ADMIT cannot tell apart.
    """
    from tests._latch_link_fixtures_22a import insert_intent, validity_row

    conn, cfg, subject = build_world(tmp_path, "case23")
    try:
        dead = dead_rival_fire(conn, run_id=150)
        superseded = live_rival_fire(conn, run_id=151, session=date(2026, 7, 22))
        consumed = live_rival_fire(conn, run_id=152, session=date(2026, 7, 23))
        conn.commit()
        subject_order = accept(conn, subject, key="23-s",
                               broker_order_id=BROKER_ORDER_ID)
        dead_order = accept(conn, dead, key="23-d", broker_order_id="23-dead")

        sup = accept(conn, superseded, key="23-sup", broker_order_id="23-sup")
        insert_intent(conn, validity_row(
            superseded, sup.place_intent_id, key="23-sup-later",
            run_id=151, ticker=TICKER, detection_date="2026-07-22",
            action_session_date=ACCEPT_SESSION.isoformat(),
            recorded_ts=f"{ACCEPT_SESSION.isoformat()}T15:00:00",
            validity_outcome="rejected_by_broker",
            actual_order_type=None, actual_duration=None,
            actual_stop_price=None, actual_limit_price=None,
            actual_quantity=None, actual_broker_order_id=None))
        conn.commit()

        con = accept(conn, consumed, key="23-con", broker_order_id="23-con")
        seed_trade(conn, trade_id=61, entry_date=date(2026, 7, 28), price=18.10)
        _entry_fill(conn, fill_id=61, trade_id=61,
                    order_id=con.broker_order_id, session=date(2026, 7, 28))

        verdict = authorize(conn, cfg, subject_order)
        assert verdict.admitted is True, verdict.decline_reason
        scanned = verdict.probe_evidence["authorization"][
            "rung8_competitor_link_ids"]["input"]
        assert scanned == [dead_order.link_id]
        assert sup.link_id not in scanned
        assert con.link_id not in scanned
    finally:
        conn.close()


# ===========================================================================
# 23b-23d -- THE UNPROVABLE THIRD STATE
# ===========================================================================
def test_a_rival_over_an_incomplete_window_is_unverifiable_case_23b(
        tmp_path) -> None:
    """CASE 23b -- lens clause 37.  ARCHIVE COVERAGE.

    The archive is missing an INTERIOR session of the judging window, so the
    rival's aliveness cannot be established.

    WHAT MAKES THIS DISCRIMINATING, stated because the shared latch makes it
    non-obvious: the same hole also makes the SUBJECT's own probe unverifiable.
    Rung 8 runs FIRST, so a correct implementation refuses
    ``competitor_liveness_unverifiable`` while an exclude-the-unresolved one
    drops the rival and falls through to the subject's own probe, refusing
    ``aliveness_unverifiable``.  Both refuse; only one names rung 8, so the
    assertion is on the REASON and not on the refusal.
    """
    gapped = {s: c for s, c in BASE_CLOSES.items() if s != date(2026, 7, 22)}
    conn, cfg, subject = build_world(tmp_path, "23b", closes=gapped)
    try:
        rival = live_rival_fire(conn, run_id=160, session=date(2026, 7, 23))
        conn.commit()
        subject_order = accept(conn, subject, key="23b-s",
                               broker_order_id=BROKER_ORDER_ID)
        accept(conn, rival, key="23b-r", broker_order_id="23b-rival")
        assert authorize(conn, cfg, subject_order).decline_reason == (
            "competitor_liveness_unverifiable")
    finally:
        conn.close()


def test_a_rival_whose_decision_ledger_cannot_be_read_is_unverifiable_case_23c(
        tmp_path, monkeypatch) -> None:
    """CASE 23c -- the DECISION-READ shape.

    A lost decline ledger is indistinguishable from no decline at all, so a
    rival whose decisions could not be read is UNPROVABLE.  Same discrimination
    argument as 23b: the assertion is on the reason NAME, because an
    exclude-the-unresolved implementation refuses too -- with the subject's own
    ``decision_evidence_unavailable`` instead of rung 8's reason.
    """
    conn, cfg, subject = build_world(tmp_path, "23c")
    try:
        rival = live_rival_fire(conn, run_id=161, session=date(2026, 7, 22))
        conn.commit()
        subject_order = accept(conn, subject, key="23c-s",
                               broker_order_id=BROKER_ORDER_ID)
        accept(conn, rival, key="23c-r", broker_order_id="23c-rival")

        import swing.data.repos.latch_order_intents as repo
        real = repo.list_intents_for_latch

        def _selective(conn_, *, candidate_id):
            if candidate_id == rival:
                raise sqlite3.OperationalError("simulated ledger read failure")
            return real(conn_, candidate_id=candidate_id)

        monkeypatch.setattr(repo, "list_intents_for_latch", _selective)
        assert authorize(conn, cfg, subject_order).decline_reason == (
            "competitor_liveness_unverifiable")
    finally:
        conn.close()


def test_a_rival_with_a_null_snapshot_is_unverifiable_case_23d(
        tmp_path) -> None:
    """CASE 23d -- the NULL-SNAPSHOT shape, and the CLEANEST of the three.

    The rival's fire carries a JUNK pivot, so the minting trigger lands NULL
    frozen values rather than aborting the operator's ledger write (cohort
    bookkeeping must never block a money-bearing operation).  A link with no
    frozen value can never be cross-checked, so its liveness is UNPROVABLE --
    and unlike 23b/23c the junk fire is DEGRADED by the fold and never joins
    the subject's latch, so the subject's own probe is untouched and the
    refusal can only have come from rung 8.
    """
    conn, cfg, subject = build_world(tmp_path, "23d")
    try:
        rival = seed_fire(conn, run_id=162, action_session=date(2026, 7, 22),
                          ticker=TICKER, pivot=-1.0, initial_stop=13.00)
        conn.commit()
        subject_order = accept(conn, subject, key="23d-s",
                               broker_order_id=BROKER_ORDER_ID)
        junk = accept(conn, rival, key="23d-r", broker_order_id="23d-rival")
        assert junk.frozen_pivot is None, "the trigger's CASE did not fire"
        assert authorize(conn, cfg, subject_order).decline_reason == (
            "competitor_liveness_unverifiable")
    finally:
        conn.close()


# ===========================================================================
# THE TWO ``-pre`` TWINS WHOSE BASES ARE THIS TASK'S
# ===========================================================================
def test_a_dead_rival_does_not_rescue_a_pre_barrier_link_case_4c_i_pre(
        tmp_path) -> None:
    """``4c-i-pre`` -- the base ADMITS; the twin refuses at rung 9.

    Rung 8 passes (the rival is proven dead and dropped) and rung 9 then
    refuses outright: under Option C there is no tier-2 escape, so a
    pre-barrier link cannot be admitted however clean the rest of the ladder.
    """
    conn, cfg, subject = build_world(tmp_path, "4cipre", pre_barrier=True)
    try:
        rival = dead_rival_fire(conn, run_id=170)
        conn.commit()
        subject_order = accept(conn, subject, key="4cipre-s",
                               broker_order_id=BROKER_ORDER_ID)
        accept(conn, rival, key="4cipre-r", broker_order_id="4cipre-rival")
        verdict = authorize(conn, cfg, subject_order)
        assert verdict.decline_reason == "pre_barrier_unproven"
        assert verdict.freeze_tier == FREEZE_TIER_PRE_BARRIER
    finally:
        conn.close()


def test_a_filtered_population_does_not_rescue_a_pre_barrier_link_case_23_pre(
        tmp_path) -> None:
    """``23-pre`` -- case 23's twin, same shape and same ruling."""
    conn, cfg, subject = build_world(tmp_path, "23pre", pre_barrier=True)
    try:
        dead = dead_rival_fire(conn, run_id=171)
        conn.commit()
        subject_order = accept(conn, subject, key="23pre-s",
                               broker_order_id=BROKER_ORDER_ID)
        accept(conn, dead, key="23pre-d", broker_order_id="23pre-dead")
        assert authorize(conn, cfg, subject_order).decline_reason == (
            "pre_barrier_unproven")
    finally:
        conn.close()


# ===========================================================================
# THE RUNG'S OWN CONTRACT
# ===========================================================================
def test_the_rung_returns_the_scanned_population_not_the_live_one(
        tmp_path) -> None:
    """``rung8_competitor_link_ids`` records the INPUT, not the conclusion.

    NO CASE ID.  The standing evidence rule is that a refusal-capable clause
    records the input it JUDGED; recording only the live subset would make an
    empty list mean either "nothing competed" or "nothing was scanned", which
    is the "passed vs never ran" collapse in a different costume.
    """
    conn, cfg, subject = build_world(tmp_path, "scanned")
    try:
        dead = dead_rival_fire(conn, run_id=180)
        conn.commit()
        subject_order = accept(conn, subject, key="sc-s",
                               broker_order_id=BROKER_ORDER_ID)
        dead_order = accept(conn, dead, key="sc-d", broker_order_id="sc-dead")
        reason, scanned = competitor_liveness_rung(
            conn, cfg, order=subject_order, fill_session=FILL_SESSION,
            exclude_trade_ids=NO_EXCLUSIONS)
        assert reason is None
        assert scanned == [dead_order.link_id]
    finally:
        conn.close()


def test_the_subject_never_competes_with_itself(tmp_path) -> None:
    """A lone accepted order has an EMPTY competitor population.

    NO CASE ID.  The subject's own link is on the ticker too, so a scan that
    forgot to exclude it would refuse ``ambiguous_ticker_orders`` on EVERY
    admission -- the arc's headline path -- and every case above would still
    pass, because they all assert refusals.  This is the one that would not.
    """
    conn, cfg, subject = build_world(tmp_path, "alone")
    try:
        order = accept(conn, subject, key="alone",
                       broker_order_id=BROKER_ORDER_ID)
        assert (order.frozen_pivot, order.frozen_invalidation) == (PIVOT, STOP)
        assert competitor_liveness_rung(
            conn, cfg, order=order, fill_session=FILL_SESSION,
            exclude_trade_ids=NO_EXCLUSIONS) == (None, [])
        assert authorize(conn, cfg, order).admitted is True
    finally:
        conn.close()


# ===========================================================================
# 22A-R4-05 (second half) -- A PRE-BARRIER COMPETITOR IS UNPROVABLE, NEVER
# PROVEN DEAD (CHARC, ruled 2026-08-25 -- the NARROW fix)
# ===========================================================================
def _mixed_barrier_world(tmp_path, name):
    """A PRE-barrier rival and a POST-barrier subject, on ONE ticker.

    The epoch boundary is stamped at migration time, so the ONLY way to build
    a mixed world is to create the rival's fire on a v36 schema, migrate, and
    create the subject's afterwards.  The boundary is then strictly between
    them -- asserted below, because a fixture whose two fires landed on the
    same side would make every assertion here vacuous.
    """
    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    cfg = probe_cfg(root)
    conn = open_connection(root / "swing.db")
    run_migrations(conn, target_version=36)
    rival = dead_rival_fire(conn, run_id=140)
    conn.commit()
    run_migrations(conn, target_version=37, backup_dir=root / "bak")
    subject = seed_fire(conn)
    conn.commit()
    write_closes(cfg, BASE_CLOSES)
    boundary = conn.execute(
        "SELECT max_candidate_id_at_barrier FROM candidates_immutability_epoch"
    ).fetchone()[0]
    assert rival <= boundary < subject, (
        f"the fixture put rival {rival} and subject {subject} on the same side "
        f"of the barrier {boundary}; the case cannot then discriminate")
    return conn, cfg, subject, rival


def test_a_pre_barrier_competitor_is_unprovable_not_dead(tmp_path) -> None:
    """CHARC's ruled NARROW fix, and the case that discriminates it.

    The rival's mandate REALLY IS dead -- superseded on 2026-07-20, strictly
    before the fill -- so the probe returns ``mandate_not_alive`` and rung 8
    used to DROP it, admitting the subject.  But the rival's link is
    ``pre_barrier_reconstructed``: its frozen pivot and stop were reconstructed
    from a ``candidates`` row that was NOT immutable when they were read, so
    "proven dead" rests on evidence AL-4 says does not exist.  Using a
    pre-barrier mandate as PROOF is a wrong ACCEPTANCE, and the direction is
    what makes it worth three lines.

    PRE-FIX: ``admitted is True`` (the rival dropped as proven dead).
    POST-FIX: ``competitor_liveness_unverifiable``.
    Both values are stated so the assertion distinguishes.

    THE CONTROL sits beside it: the byte-identical world with BOTH fires
    post-barrier still ADMITS, so the refusal is the TIER's doing and not the
    rival's mere presence.  Without that half a fix that refused every
    competitor would pass.
    """
    conn, cfg, subject, rival = _mixed_barrier_world(tmp_path, "r405")
    try:
        subject_order = accept(conn, subject, key="r405-s",
                               broker_order_id=BROKER_ORDER_ID)
        rival_order = accept(conn, rival, key="r405-r",
                             broker_order_id="r405-rival")
        assert rival_order.freeze_tier == FREEZE_TIER_PRE_BARRIER
        assert subject_order.freeze_tier == "live_at_acceptance"

        # The rival's mandate is GENUINELY dead: that is what makes dropping
        # it tempting, and it is why the case is about EVIDENCE rather than
        # about liveness.
        probe = mandate_alive_at(
            conn, cfg, order=rival_order, fill_session=FILL_SESSION,
            exclude_trade_ids=NO_EXCLUSIONS)
        assert probe.decline_reason == "mandate_not_alive"
        assert probe.clear_reason == "superseded"

        verdict = authorize(conn, cfg, subject_order)
        assert verdict.admitted is False
        assert verdict.decline_reason == "competitor_liveness_unverifiable"
    finally:
        conn.close()


def test_a_post_barrier_dead_competitor_is_still_dropped(tmp_path) -> None:
    """THE CONTROL for the case above, in its own test so a failure names it.

    ONE dimension differs -- both fires are created after the migration, so
    both links mint ``live_at_acceptance`` -- and the subject ADMITS.  A fix
    that treated EVERY dead competitor as unprovable would fail here while
    passing the case it was written for.
    """
    conn, cfg, subject = build_world(tmp_path, "r405ctl")
    try:
        rival = dead_rival_fire(conn, run_id=140)
        conn.commit()
        subject_order = accept(conn, subject, key="r405c-s",
                               broker_order_id=BROKER_ORDER_ID)
        rival_order = accept(conn, rival, key="r405c-r",
                             broker_order_id="r405c-rival")
        assert rival_order.freeze_tier == "live_at_acceptance"
        verdict = authorize(conn, cfg, subject_order)
        assert verdict.admitted is True, verdict.decline_reason
        assert verdict.probe_evidence["authorization"][
            "rung8_competitor_link_ids"]["input"] == [rival_order.link_id]
    finally:
        conn.close()


# ===========================================================================
# 22A-R3-05 -- A COMPETITOR WITH NO VALIDITY SIBLINGS IS UNPROVABLE
# ===========================================================================
def test_a_competitor_link_with_no_validity_siblings_is_unprovable(
        tmp_path) -> None:
    """A link is MINTED BY a validity insert, so a link whose place has no
    validity children contradicts its own provenance.

    PRE-FIX the loop hit ``continue`` -- reading incoherence as ABSENCE and
    dropping the competitor, after which the subject ADMITTED.  POST-FIX it is
    UNPROVABLE and the subject refuses.  Both values are stated so the
    assertion distinguishes; the two-valued reading is the exact inversion
    this rung exists to refuse.

    THE SHAPE IS BUILT THE ONLY WAY THE SCHEMA ALLOWS: the mint trigger is
    SUPPRESSED around a real acceptance and RESTORED VERBATIM out of
    ``sqlite_master``, then a link is written by hand pointing at a SECOND
    place row that has no validity children.  ``validity_intent_id`` is UNIQUE
    and the link table is append-only, so neither a raw copy of a minted link
    nor an edit of one is representable.
    """
    from tests._latch_link_fixtures_22a import (
        insert_intent,
        place_row,
        validity_row,
    )

    conn, cfg, subject = build_world(tmp_path, "r305")
    try:
        rival = dead_rival_fire(conn, run_id=140)
        conn.commit()
        subject_order = accept(conn, subject, key="r305-s",
                               broker_order_id=BROKER_ORDER_ID)

        saved = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'trigger' "
            "AND name = 'trg_latch_link_mint_on_acceptance'").fetchone()[0]
        conn.execute("DROP TRIGGER trg_latch_link_mint_on_acceptance")
        try:
            common = {
                "evaluation_run_id": 140, "ticker": TICKER,
                "detection_date": DEAD_SESSION.isoformat(),
                "action_session_date": ACCEPT_SESSION.isoformat(),
                "recorded_ts": f"{ACCEPT_SESSION.isoformat()}T10:00:00",
            }
            real_place = insert_intent(conn, place_row(
                rival, idempotency_key="r305-place", **common))
            orphan_place = insert_intent(conn, place_row(
                rival, idempotency_key="r305-orphan-place", **common))
            validity_id = insert_intent(conn, validity_row(
                rival, real_place, key="r305-validity",
                actual_broker_order_id="r305-rival", **common))
            conn.commit()
        finally:
            conn.execute(saved)
            conn.commit()

        pivot, stop = conn.execute(
            "SELECT pivot, initial_stop FROM candidates WHERE id = ?",
            (rival,)).fetchone()
        conn.execute(
            "INSERT INTO latch_order_mandate_links (validity_intent_id, "
            "place_intent_id, candidate_id, evaluation_run_id, ticker, "
            "detection_date, broker_order_id, frozen_pivot, "
            "frozen_invalidation, actual_quantity, freeze_tier, linked_at) "
            "VALUES (?, ?, ?, 140, ?, ?, 'r305-rival', ?, ?, 10, "
            "'live_at_acceptance', '2026-07-24T12:00:00Z')",
            (validity_id, orphan_place, rival, TICKER,
             DEAD_SESSION.isoformat(), pivot, stop))
        conn.commit()
        assert conn.execute(
            "SELECT COUNT(*) FROM latch_order_intents WHERE intent_kind = "
            "'validity' AND validated_place_intent_id = ?",
            (orphan_place,)).fetchone()[0] == 0, (
            "the orphan place must have NO validity children, or the case is "
            "about a different branch")

        verdict = authorize(conn, cfg, subject_order)
        assert verdict.admitted is False
        assert verdict.decline_reason == "competitor_liveness_unverifiable"
    finally:
        conn.close()


# ===========================================================================
# THE RUNG-8 LEGIBILITY ENRICHMENT -- WHERE TWO REFUSALS ARE BOTH TRUE, PREFER
# THE MORE SPECIFIC (orchestrator-proposed, CHARC-approved 2026-09-01)
#
# S3.4c's second leg says the envelope naming the DEAD order refuses
# `mandate_not_alive`.  From the dead order's SEAT the SUBJECT is a genuinely
# proven-LIVE competitor, so rung 8 fired first and the ladder answered
# `ambiguous_ticker_orders` -- and the audit graded 4c-i UNVERIFIABLE on that
# disagreement.  **A LADDER EVALUATED FROM A SEAT MAKES THE REFUSAL REASON A
# PROPERTY OF `(world, seat)`, NOT OF THE WORLD** (CHARC, now canon): S3.4c
# pinned a reason without naming whose seat, and that one missing word read as
# a contradiction, then a fixture defect, then a rung-ordering question.
#
# The fix chooses a better REASON and can never convert a refusal into an
# admission -- the safe direction under the governing asymmetry -- so S3.4c is
# satisfied AS WRITTEN, at the LADDER grain, with no grain change.
#
# **THE SELECTION IS THREE-VALUED, AND THAT IS CHARC'S BINDING ADDITION.**
#     proven DEAD -> the specific reason
#     proven LIVE -> fall through to `ambiguous_ticker_orders`
#     UNPROVABLE  -> fall through to `ambiguous_ticker_orders`
# A two-valued "dead or not-dead" check reintroduces exactly the inversion
# `R3-03` corrected in the POPULATION rule -- the same defect, in the same
# file, one rung over.  The discriminating case below is what fails it.
# ===========================================================================
def test_an_UNPROVABLE_subject_beside_a_live_rival_stays_AMBIGUOUS(
        tmp_path) -> None:
    """**THE DISCRIMINATING CASE, AND IT IS MANDATORY** (CHARC).

    The subject's own fire carries a JUNK pivot, so the minting trigger lands
    NULL frozen values and its own probe answers `frozen_value_unavailable` --
    UNPROVABLE, not dead.  Beside it stands a genuinely live accepted order.

    A THREE-VALUED selection falls through to `ambiguous_ticker_orders`.  A
    two-valued "the probe did not admit, so it is dead" selection answers
    `mandate_not_alive` and asserts a death nothing established -- which is
    `R3-03`'s inversion, in the same file, one rung over.

    The junk link's freeze tier is asserted LIVE so the case cannot pass for
    the unrelated reason that the pre-barrier gate short-circuited it before
    the probe ran.
    """
    conn, cfg, ordinary = build_world(tmp_path, "unprovable-subject")
    try:
        junk = seed_fire(conn, run_id=162, action_session=date(2026, 7, 22),
                         ticker=TICKER, pivot=-1.0, initial_stop=13.00)
        conn.commit()
        accept(conn, ordinary, key="ups-o", broker_order_id=BROKER_ORDER_ID)
        junk_order = accept(conn, junk, key="ups-j",
                            broker_order_id="ups-junk")
        assert junk_order.frozen_pivot is None, "the trigger's CASE did not fire"
        assert junk_order.freeze_tier == "live_at_acceptance", (
            "the case must reach the PROBE, not stop at the pre-barrier gate")

        # THE PREMISE, measured: the subject's own state is UNPROVABLE, and it
        # is specifically NOT `mandate_not_alive`.
        own = mandate_alive_at(
            conn, cfg, order=junk_order, fill_session=FILL_SESSION,
            exclude_trade_ids=NO_EXCLUSIONS)
        assert own.admitted is False
        assert own.decline_reason == "frozen_value_unavailable", (
            f"the fixture must be UNPROVABLE, not dead (got "
            f"{own.decline_reason})")

        verdict = authorize(conn, cfg, junk_order)
        assert verdict.decline_reason == "ambiguous_ticker_orders", (
            "an UNPROVABLE subject was reported DEAD; the selection is "
            "two-valued and has reintroduced R3-03's inversion one rung over")
        assert verdict.clear_reason is None, (
            "a terminal was reported for a mandate whose state was never "
            "established")
    finally:
        conn.close()


def test_a_PRE_BARRIER_subject_cannot_prove_its_own_death_either(
        tmp_path) -> None:
    """AL-4, applied to the SUBJECT exactly as rung 8 already applies it to a
    COMPETITOR.

    `mandate_not_alive` rests on the frozen pivot and stop the link carries,
    and a `pre_barrier_reconstructed` link's pair was copied from a
    `candidates` row that was NOT immutable when it was read -- so a
    pre-barrier subject's death is UNPROVABLE and the ladder must not name it.

    Rung 9 would refuse `pre_barrier_unproven` for this order anyway, which is
    exactly why this row asserts the RUNG-8 reason: it pins that the
    enrichment did not reach past its own gate and mint a death claim the
    arc's own limitation forbids.
    """
    conn, cfg, subject = build_world(
        tmp_path, "pre-barrier-subject", pre_barrier=True)
    try:
        live = live_rival_fire(conn, run_id=170, session=date(2026, 7, 22))
        conn.commit()
        accept(conn, live, key="pbs-live", broker_order_id="pbs-live-order")
        pre = accept(conn, subject, key="pbs-s",
                     broker_order_id=BROKER_ORDER_ID)
        assert pre.freeze_tier == FREEZE_TIER_PRE_BARRIER, (
            "the fixture must carry the pre-barrier tier or it measures "
            "nothing about AL-4")
        verdict = authorize(conn, cfg, pre)
        assert verdict.decline_reason == "ambiguous_ticker_orders", (
            "a pre-barrier subject's death was reported as PROVEN")
    finally:
        conn.close()
