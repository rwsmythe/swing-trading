"""22-A Task 9 -- ``record_entry`` wiring, at the PERSISTED-ROW grain.

EVERY ASSERTION READS THE ROW THAT LANDED, never the resolver's return value.
Task 8 already pins the resolver's verdicts; what this module exists to prove
is that the verdict REACHES the ``trades`` row -- the three keys move together
on admission, the honest-unset row SUPPRESSES the ordinary chain rather than
falling back to it, and the ordinary path is byte-identical to ``main``'s.

THE FIXTURES ARE THE PROBE WORLD, NOT THE LIVE DB.  The plan's cases 1/5/6 are
specified against OII's real geometry; the shapes that matter to THIS task are
the fire, its archive, the minted link and the envelope, and those are built by
``tests/_latch_probe_world_22a.py`` from real emitter output.  Where a case's
discriminating value is a PRICE RELATIONSHIP (5a's breach at
``invalidation - 0.05``, 6's close exactly EQUAL to the invalidation) the
relationship is reproduced exactly; the absolute numbers are the probe world's.
Stated here rather than left implicit, because a fixture that quietly changes a
dimension the case is named for is not a discriminator (plan S3.8).

FROZEN CLOCK.  Every session is an explicit date; nothing reads the wall clock.
"""
from __future__ import annotations

import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from swing.data.db import ensure_schema, open_connection, run_migrations
from swing.trades.entry import (
    EntryRequest,
    PatternEvaluationAnchorError,
    record_entry,
)
from swing.trades.origin import EntryPath
from tests._latch_probe_world_22a import (
    ANCHOR,
    BASE_CLOSES,
    BROKER_ORDER_ID,
    FILL_SESSION,
    PIVOT,
    STOP,
    TICKER,
    accept_and_link,
    probe_cfg,
    seed_fire,
    write_closes,
)

ACCEPT_SESSION = date(2026, 7, 21)
SOFT, HARD = 8, 12


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------
def build_world(tmp_path: Path, name: str, *, closes=None, pre_barrier=False):
    """A fire, its archive, the pipeline row the SHARED derivation needs.

    ``pre_barrier=True`` builds the world THE PRODUCTION WAY -- the fire is
    created on a v36 schema and the migration runs afterwards -- so the epoch
    boundary lands ABOVE it and the link mints ``pre_barrier_reconstructed``.
    The epoch is immutable by its own three triggers, so a twin fixture that
    tried to MOVE the boundary would be asking the barrier to be less than it
    is.  Exactly ONE dimension differs between a case and its ``-pre`` twin.
    """
    from tests.trades._cohort_provenance_fixtures import (
        rebase_status_history_recorded_at,
        seed_pipeline_run,
    )

    root = tmp_path / name
    root.mkdir(parents=True, exist_ok=True)
    cfg = probe_cfg(root)
    if pre_barrier:
        conn = open_connection(root / "swing.db")
        run_migrations(conn, target_version=36)
        candidate_id = seed_fire(conn)
        conn.commit()
        run_migrations(conn, target_version=37, backup_dir=root / "bak")
    else:
        conn = ensure_schema(root / "swing.db")
        candidate_id = seed_fire(conn)
    run = conn.execute(
        "SELECT data_asof_date, action_session_date FROM evaluation_runs "
        "WHERE id = 121").fetchone()
    seed_pipeline_run(
        conn, evaluation_run_id=121, data_asof_date=run[0],
        action_session_date=run[1],
        started_ts=f"{run[0]}T17:30:26",
        finished_ts=f"{run[0]}T17:44:45")
    rebase_status_history_recorded_at(conn)
    conn.commit()
    write_closes(cfg, BASE_CLOSES if closes is None else closes)
    return conn, cfg, candidate_id


def envelope(order_id: str = BROKER_ORDER_ID, symbol: str = TICKER) -> str:
    return json.dumps(
        {"schwab_order_id": order_id, "schwab_instrument_symbol": symbol,
         "entry_date": FILL_SESSION.isoformat(), "entry_price": 18.50,
         "shares": 2})


def req(**over) -> EntryRequest:
    """A REAL ``EntryRequest``, not a namespace.

    Task 8 tests the resolver against a field-set stand-in deliberately; this
    task is the WIRING, so the request must be the one production builds or the
    test would not see a field the service reads and the request does not
    carry.
    """
    fields = dict(
        ticker=TICKER, entry_date=FILL_SESSION.isoformat(), entry_price=18.50,
        shares=2, initial_stop=14.00, watchlist_entry_target=None,
        watchlist_initial_stop=None, notes=None,
        rationale="vcp_breakout",
        event_ts=f"{FILL_SESSION.isoformat()}T09:30:00",
        entry_path=EntryPath.MANUAL_WEB_FORM,
        thesis="the mandate fired", why_now="through the pivot",
        invalidation_condition="break of the stop",
        expected_scenario="20% in 4 weeks",
        premortem_technical="pivot fails",
        premortem_market_sector="sector breaks",
        premortem_execution="size too small",
        event_risk_present=0, event_handling="not_applicable",
        gap_risk_present=0, gap_risk_handling="not_applicable",
        emotional_state_pre_trade='["calm"]', market_regime="Bullish",
        catalyst="technical_only", manual_entry_confidence="normal",
        fill_origin="schwab_auto", schwab_source_value_json=envelope(),
    )
    fields.update(over)
    return EntryRequest(**fields)


def written(conn: sqlite3.Connection, trade_id: int) -> tuple:
    return conn.execute(
        "SELECT trade_origin, candidate_id, hypothesis_label FROM trades "
        "WHERE id = ?", (trade_id,)).fetchone()


def enter(conn, cfg, request, **over):
    kw = dict(soft_warn=SOFT, hard_cap=HARD, force=False, cfg=cfg)
    kw.update(over)
    return record_entry(conn, request, **kw)


# ===========================================================================
# CASE 1 -- validated latch, bucket drifted, invalidation never approached
# ===========================================================================
def test_a_latched_fill_labels_from_the_fire_case_1(tmp_path) -> None:
    """PRE-FIX the row lands ``manual_off_pipeline`` + NULL + NULL, because the
    fire has rolled out of the latest complete run.  POST-FIX it carries the
    fire's three keys.  Both values are stated so the assertion distinguishes.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "c1")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    result = enter(conn, cfg, req())
    origin, cand, label = written(conn, result.trade_id)
    assert origin == "pipeline_aplus"
    assert cand == candidate_id
    assert label is not None and label.startswith("A+ baseline")


def _label_derived_from(conn, candidate_id: int, evaluation_run_id: int) -> str:
    """The hypothesis label Demand C's OWN derivation produces for one fire.

    Used to build the EXPECTED value from the candidate row the case names,
    rather than from the row the entry path happened to write -- which is the
    circularity 22A-R4-08(a) found.  It is the same derivation the arc calls,
    fed a DIFFERENT input, so the comparison discriminates the defect it is
    written for (the label sourced from the drifted bucket row) without
    re-spelling the label rule (#11).
    """
    from swing.data.repos.candidates import fetch_candidate_by_id
    from swing.trades.cohort_provenance_correction import (
        _require_naive_datetime,
        derive_cohort_keys_for_fire,
    )

    cited = fetch_candidate_by_id(conn, candidate_id)
    assert cited is not None, f"candidate {candidate_id} is absent"
    run_ts = conn.execute(
        "SELECT run_ts FROM evaluation_runs WHERE id = ?",
        (evaluation_run_id,)).fetchone()[0]
    return derive_cohort_keys_for_fire(
        conn, candidate=cited.candidate, candidate_id=candidate_id,
        evaluation_run_id=evaluation_run_id,
        run_ts_parsed=_require_naive_datetime(run_ts, what="run_ts"),
        gate=None,
    ).hypothesis_label


def test_bucket_drift_is_not_death_case_1(tmp_path) -> None:
    """A LATER `watch` row for the same ticker must not change the answer.

    If it does, something is reading the framework's BUCKET SERIES rather than
    the mandate -- which is the whole defect the arc exists to stop.

    THE OLD ASSERTION WAS CIRCULAR (Codex 22A-R4-08(a)): it compared the stored
    label to the same stored label, so a WATCH-derived wrong label passed.  The
    expected value is now derived from the FIRE's candidate row through the
    SHARED derivation -- the same code, a different input -- so the comparison
    discriminates the defect without re-spelling the label rule (#11).

    The drifted row's OWN label is not computed as a foil: measured, that
    derivation RAISES (the watch candidate matches zero registry hypotheses as
    of its cited record), so there is no second string to compare against.
    What carries the discrimination instead is the pair the ordinary chain
    WOULD have written -- asserted directly above as `pipeline_watch_manual`,
    and asserted below to be absent from the row.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "c1drift")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    from tests._latch_probe_world_22a import seed_run
    seed_run(conn, 999, date(2026, 7, 24))
    drifted_id = conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
        "pivot, initial_stop, rs_method) VALUES (999, ?, 'watch', 17.9, "
        "18.34, 14.88, 'universe')", (TICKER,)).lastrowid
    # THE DRIFTED RUN COMPLETES, which is what makes the case bite: with it,
    # `derive_trade_origin` answers `pipeline_watch_manual` and the ORDINARY
    # chain would write the drifted candidate and its watch label.  Without it
    # the drifted row is inert and the case could pass while reading the bucket
    # series.
    from tests.trades._cohort_provenance_fixtures import (
        rebase_status_history_recorded_at,
        seed_pipeline_run,
    )
    seed_pipeline_run(
        conn, evaluation_run_id=999, data_asof_date="2026-07-23",
        action_session_date="2026-07-24",
        started_ts="2026-07-23T17:30:00", finished_ts="2026-07-23T17:44:00")
    rebase_status_history_recorded_at(conn)
    conn.commit()
    from swing.trades.origin import derive_trade_origin
    assert derive_trade_origin(
        conn, TICKER, EntryPath.MANUAL_WEB_FORM) == "pipeline_watch_manual", (
        "the fixture must make the ORDINARY chain answer differently from the "
        "fire, or bucket drift is not being exercised at all")

    from_fire = _label_derived_from(conn, candidate_id, 121)
    assert from_fire == "A+ baseline (aplus)"

    result = enter(conn, cfg, req())
    assert written(conn, result.trade_id) == (
        "pipeline_aplus", candidate_id, from_fire)
    assert candidate_id != drifted_id


def test_a_pre_barrier_fire_records_honest_unset_case_1_pre(tmp_path) -> None:
    """RD's refuse-by-default, at the PERSISTED-ROW grain.

    This is what the live entry path does on every fire that exists today, and
    the plan does not let the acceptance suite's green imply otherwise.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "c1pre", pre_barrier=True)
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    result = enter(conn, cfg, req(hypothesis_label="Broad-watch baseline (watch)"))
    assert written(conn, result.trade_id) == ("manual_off_pipeline", None, None)


# ===========================================================================
# CASE 2 -- no latch rows at all: the fall-through control
# ===========================================================================
def test_a_fill_with_no_latch_rows_falls_through_case_2(tmp_path) -> None:
    """The ordinary chain runs UNCHANGED.

    The discriminating assertion is that the ordinary path was taken at all --
    asserting only the origin would pass under almost any broken
    implementation, because this ticker's answer is ``manual_off_pipeline``
    either way.  So the case is paired with the LOCK matrix below, which
    asserts the persisted row is byte-identical with ``cfg`` passed and with
    ``cfg=None``.
    """
    from swing.trades.latched_origin import resolve_latched_provenance

    conn, cfg, _ = build_world(tmp_path, "c2")
    conn.commit()
    verdict = resolve_latched_provenance(conn, cfg, req())
    assert verdict.decline_reason == "no_accepted_latch_order"
    assert not verdict.recognised_but_underivable, (
        "no-link is the ONE refusal that must leave the ordinary path intact")
    result = enter(conn, cfg, req())

    control, cfg_c, _ = build_world(tmp_path, "c2ctl")
    control.commit()
    ctl = record_entry(control, req(), soft_warn=SOFT, hard_cap=HARD,
                       force=False)
    assert written(conn, result.trade_id) == written(control, ctl.trade_id)


# ===========================================================================
# CASE 3 -- never filled: the arc has NO effect where there is no fill
# ===========================================================================
_C3_TABLES = ("trades", "fills", "latch_order_mandate_links",
              "latch_order_intents", "candidates", "provenance_corrections")


def test_an_unfilled_mandate_is_untouched_by_the_arc_case_3(tmp_path) -> None:
    """No trade, no fill -> nothing is written anywhere, AND the derivation
    the operator sees is unchanged.

    THIS TEST WAS VACUOUS AND THE VACUITY WAS PROVED BY EXECUTION, NOT BY
    READING (Codex 22A-R4-07).  It snapshotted two table counts with NO
    operation between them; with ``find_accepted_latch_order`` edited to
    ``return []`` unconditionally -- an arc that does nothing at all -- it
    still passed.  A test that cannot fail against a gutted implementation
    asserts nothing about the implementation.

    THE REBUILD DRIVES THE ARC'S READ SURFACES over the unfilled mandate and
    asserts they ENGAGE: the link is found, the mandate is ALIVE at a
    hypothetical fill session, and the epoch reader reports a standing barrier.
    That half fails against a do-nothing arc.  The other half is the case's own
    claim -- that after all of it, every table count is unchanged, there is no
    trade and no fill, and the derived latches are byte-identical to the
    snapshot taken before the reads.

    Stating both halves is the point: the "nothing happened" assertion is only
    worth making once "something COULD have happened" is established, or the
    case passes for the reason the mandate was unauthorizable.
    """
    from dataclasses import asdict
    from datetime import datetime

    from swing.data.repos.candidates_immutability_epoch import (
        freeze_tier_for_candidate,
    )
    from swing.latches.reader import build_latch_derivation
    from swing.trades.latched_origin import (
        find_accepted_latch_order,
        mandate_alive_at,
    )

    conn, cfg, candidate_id = build_world(tmp_path, "c3")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()

    def counts() -> dict[str, int]:
        return {
            t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
            for t in _C3_TABLES
        }

    # FROZEN CLOCK: the derivation's whole context comes from this one datetime.
    frozen = datetime(2026, 7, 27, 9, 0, 0)
    before = counts()
    baseline = [asdict(latch)
                for latch in build_latch_derivation(conn, cfg, now=frozen).latches]

    # --- the arc's read surfaces, DRIVEN over the unfilled mandate ----------
    found = find_accepted_latch_order(conn, broker_order_id=BROKER_ORDER_ID)
    assert len(found) == 1, (
        f"the arc did not recognise the accepted order ({len(found)} links); "
        f"every 'nothing was written' assertion below would then be vacuous")
    probe = mandate_alive_at(
        conn, cfg, order=found[0], fill_session=FILL_SESSION,
        exclude_trade_ids=frozenset())
    assert probe.admitted, (
        f"the mandate was not alive at {FILL_SESSION} "
        f"({probe.decline_reason}); the case would then pass because nothing "
        f"could have been admitted, not because nothing was filled")
    tier, installed = freeze_tier_for_candidate(conn, candidate_id)
    assert (tier, installed) == ("live_at_acceptance", True)

    # --- and NOTHING moved -------------------------------------------------
    assert counts() == before
    assert before["trades"] == 0 and before["fills"] == 0
    assert [asdict(latch)
            for latch in build_latch_derivation(conn, cfg, now=frozen).latches
            ] == baseline, (
        "the arc's reads changed the derivation the operator sees")


# ===========================================================================
# CASE 5a / 5b / 5b-pre -- the invalidation branch (SYNTHETIC)
# ===========================================================================
def _breach_closes(session: date) -> dict[date, float]:
    """BASE_CLOSES with ONE session's close moved to ``invalidation - 0.05``.

    Five cents is the REAL AMN breach magnitude (30.80 against a 30.85 stop).
    A deep breach passes sloppy encodings; five cents pins them.
    """
    closes = dict(BASE_CLOSES)
    closes[session] = round(STOP - 0.05, 2)
    return closes


def test_a_breach_on_a_prior_session_refuses_case_5a(tmp_path) -> None:
    """SYNTHETIC -- no live fill has ever met a breached mandate through a
    validated order, so this case exists to make the branch falsifiable.

    An implementation OMITTING the invalidation comparison ADMITS this case and
    writes the fire's keys.  That is the point of the case.
    """
    conn, cfg, candidate_id = build_world(
        tmp_path, "c5a", closes=_breach_closes(date(2026, 7, 23)))
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    result = enter(
        conn, cfg, req(hypothesis_label="Broad-watch baseline (watch)"))
    assert written(conn, result.trade_id) == ("manual_off_pipeline", None, None)


def test_the_discarded_label_is_logged_not_persisted_case_5a(
        tmp_path, caplog) -> None:
    """The two obligations are asserted SEPARATELY so neither masks the other.

    The fixture SEEDS a non-NULL submitted label: against a fixture whose
    submitted label is already NULL, "assert the persisted label is NULL"
    passes an implementation that faithfully persists ``req.hypothesis_label``
    -- there was nothing else for it to write (harvest H4).
    """
    conn, cfg, candidate_id = build_world(
        tmp_path, "c5alog", closes=_breach_closes(date(2026, 7, 23)))
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    with caplog.at_level("WARNING"):
        result = enter(
            conn, cfg, req(hypothesis_label="Broad-watch baseline (watch)"))
    assert written(conn, result.trade_id)[2] is None
    assert any("Broad-watch baseline (watch)" in r.getMessage()
               for r in caplog.records), caplog.text


def test_a_breach_on_the_fill_session_admits_case_5b(tmp_path) -> None:
    """SYNTHETIC GEOMETRY, and the docstring says which dimension is synthetic:
    the breach session is MOVED ONTO the fill session.  The real AMN geometry
    is 5a, where the breach is strictly prior.

    THE GROUND FOR ADMITTING IS SURVIVORSHIP, not leniency.  The fastest loser
    is the fill that collapses the day it triggers; a label rule that ejects
    exactly those trades censors H1's left tail and biases the cohort mean UP.
    An implementation that refuses 5b is not being conservative -- it is
    silently improving H1's apparent results.

    5a's breach is strictly earlier and EVERY implementation refuses it, so
    only 5b separates fill-wins from any session-inclusive reading.
    """
    conn, cfg, candidate_id = build_world(
        tmp_path, "c5b", closes=_breach_closes(FILL_SESSION))
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    result = enter(conn, cfg, req())
    origin, cand, _ = written(conn, result.trade_id)
    assert (origin, cand) == ("pipeline_aplus", candidate_id)


def test_the_pre_barrier_twin_of_the_tie_refuses_case_5b_pre(tmp_path) -> None:
    """BYTE-IDENTICAL to 5b with exactly ONE dimension changed -- the epoch
    boundary is at its real value, so the link mints
    ``pre_barrier_reconstructed``.

    IT IS A REAL DISCRIMINATOR AND THE ORDER IS WHAT MAKES IT ONE.  Rung 9
    fires BEFORE the probe runs, so this must refuse on the TIER without ever
    evaluating the same-session tie.  An implementation that probed first would
    still reach ``pre_barrier_unproven`` and pass on the reason string alone --
    so the assertion also pins that NO aliveness evidence was recorded.
    """
    from swing.trades.latched_origin import resolve_latched_provenance

    conn, cfg, candidate_id = build_world(
        tmp_path, "c5bpre", closes=_breach_closes(FILL_SESSION),
        pre_barrier=True)
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    verdict = resolve_latched_provenance(conn, cfg, req())
    assert verdict.decline_reason == "pre_barrier_unproven"
    assert verdict.clear_reason is None
    assert verdict.probe_evidence is None
    result = enter(conn, cfg, req())
    assert written(conn, result.trade_id) == ("manual_off_pipeline", None, None)


# ===========================================================================
# CASE 6 -- the boundary: a close EXACTLY EQUAL to the invalidation
# ===========================================================================
def test_a_close_exactly_at_the_invalidation_admits_case_6(tmp_path) -> None:
    """A ``<=`` encoding fails this case while passing 5a, which is precisely
    why RD ruled the inequality and why the case is first-class.

    It agrees with the shipped
    ``tests/latches/test_service_terminal.py::
    test_a_close_exactly_at_the_stop_does_not_invalidate``.  If the two ever
    disagree, one is wrong and both tests say so.
    """
    closes = dict(BASE_CLOSES)
    closes[date(2026, 7, 23)] = STOP
    conn, cfg, candidate_id = build_world(tmp_path, "c6", closes=closes)
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    result = enter(conn, cfg, req())
    origin, cand, _ = written(conn, result.trade_id)
    assert (origin, cand) == ("pipeline_aplus", candidate_id)


def test_the_pre_barrier_twin_of_the_boundary_refuses_case_6_pre(
        tmp_path) -> None:
    """ONE dimension varies from case 6: the epoch boundary."""
    closes = dict(BASE_CLOSES)
    closes[date(2026, 7, 23)] = STOP
    conn, cfg, candidate_id = build_world(
        tmp_path, "c6pre", closes=closes, pre_barrier=True)
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    result = enter(conn, cfg, req())
    assert written(conn, result.trade_id) == ("manual_off_pipeline", None, None)


# ===========================================================================
# CASE 12 -- suppression, NOT fallback
# ===========================================================================
def test_a_refused_link_suppresses_the_ordinary_chain_case_12(
        tmp_path) -> None:
    """THE FIXTURE SEEDS A CURRENT `aplus` RUN FOR THE TICKER, or the test
    cannot distinguish suppression from plain fallback.

    Without that row the ordinary chain would write ``manual_off_pipeline``
    anyway and a fallback implementation would pass.  With it, a fallback
    writes ``pipeline_aplus`` plus TODAY's candidate -- a DIFFERENT mandate
    from the one this fill came from.  Silent-wrong, not honest-NULL.
    """
    from tests._latch_probe_world_22a import seed_run

    conn, cfg, candidate_id = build_world(
        tmp_path, "c12", closes=_breach_closes(date(2026, 7, 23)))
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    seed_run(conn, 900, FILL_SESSION)
    today_cand = conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
        "pivot, initial_stop, rs_method) VALUES (900, ?, 'aplus', 19.0, "
        "19.5, 15.0, 'universe')", (TICKER,)).lastrowid
    from tests.trades._cohort_provenance_fixtures import seed_pipeline_run
    seed_pipeline_run(
        conn, evaluation_run_id=900,
        data_asof_date=date(2026, 7, 24).isoformat(),
        action_session_date=FILL_SESSION.isoformat(),
        started_ts="2026-07-24T17:30:00", finished_ts="2026-07-24T17:44:00")
    conn.commit()
    result = enter(conn, cfg, req(entry_path=EntryPath.HYP_RECS_BUTTON))
    origin, cand, label = written(conn, result.trade_id)
    assert (origin, cand, label) == ("manual_off_pipeline", None, None), (
        f"the ordinary chain fell back to candidate {today_cand} instead of "
        f"suppressing")


# ===========================================================================
# CASES 21 / 21b -- BEGIN IMMEDIATE, in BOTH directions
# ===========================================================================
def test_the_written_row_reflects_the_inside_verdict_case_21(
        tmp_path) -> None:
    """link -> superseded BETWEEN recognition and INSERT.

    Under a DEFERRED transaction the authoritative read acquires no write
    reservation, so a competing writer can commit between that read and the
    INSERT and the row lands on a world that no longer holds.  ``with conn:``
    is exactly that deferred transaction -- it takes no reservation until its
    first WRITE, and the resolution is all reads.

    THE ASSERTION IS MADE FROM A SECOND CONNECTION, because a mutation issued
    on the same connection would be inside the very transaction under test and
    would prove nothing.  A competing writer that cannot even BEGIN IMMEDIATE
    cannot commit between the read and the INSERT, which is the property.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "c21")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    db = tmp_path / "c21" / "swing.db"
    observed: list[bool] = []

    import swing.trades.latched_origin as lo
    real = lo.authorize_accepted_order

    def _observe(*a, **kw):
        other = open_connection(db)
        try:
            try:
                other.execute("BEGIN IMMEDIATE")
                other.rollback()
                observed.append(False)
            except sqlite3.OperationalError:
                observed.append(True)
        finally:
            other.close()
        return real(*a, **kw)

    lo.authorize_accepted_order = _observe
    try:
        result = enter(conn, cfg, req())
    finally:
        lo.authorize_accepted_order = real
    assert observed == [True], (
        "the AUTHORITATIVE authorization ran without a write reservation; a "
        "competing writer could supersede the validity row between it and the "
        "INSERT")
    assert written(conn, result.trade_id)[0] == "pipeline_aplus"


def test_a_no_link_preliminary_still_reserves_case_21b(tmp_path) -> None:
    """A request whose RECOGNITION found no link acquires one before the
    INSERT.

    The trigger for the reservation is "the request carries a usable broker
    order id", NEVER "the recognition found a link" -- a negative result is as
    perishable as a positive one.  An implementation reserving only on the
    recognised-latched path takes the ordinary path on a stale negative.

    Asserted by observing that the WRITE TRANSACTION IS ALREADY IMMEDIATE while
    the row is being written: a second connection cannot acquire the write lock
    at any point during ``record_entry`` for an order-id-bearing request whose
    preliminary answer was NO LINK.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "c21b")
    conn.commit()
    db = tmp_path / "c21b" / "swing.db"
    observed: list[bool] = []

    import swing.trades.latched_origin as lo
    real = lo.find_accepted_latch_order

    def _observe(conn_, *, broker_order_id):
        other = open_connection(db)
        try:
            try:
                other.execute("BEGIN IMMEDIATE")
                other.rollback()
                observed.append(False)      # the lock was NOT held
            except sqlite3.OperationalError:
                observed.append(True)       # reserved, as required
        finally:
            other.close()
        # and NOW the link arrives, after the preliminary answer would have
        # been "no link"
        return real(conn_, broker_order_id=broker_order_id)

    lo.find_accepted_latch_order = _observe
    try:
        result = enter(conn, cfg, req())
    finally:
        lo.find_accepted_latch_order = real
    assert observed and all(observed), (
        "the authoritative read ran WITHOUT a write reservation; a competing "
        "writer could commit between it and the INSERT")
    # The row itself is the ORDINARY one -- there was no link.  What the case
    # pins is that the reservation was taken ANYWAY, on the strength of the
    # order id alone.
    assert conn.execute(
        "SELECT COUNT(*) FROM trades WHERE id = ?",
        (result.trade_id,)).fetchone()[0] == 1


# ===========================================================================
# CASE 37c -- the RELOCATED PE-anchor guard, on the STABLE no-link outcome
# ===========================================================================
def test_an_unmatched_order_id_with_a_pe_anchor_is_refused_case_37c(
        tmp_path) -> None:
    """THE DISCRIMINATING CASE for review 22A-R9-03, and it is task 9's.

    A request carrying (a) a usable but UNMATCHED broker order id, (b) a
    ``pattern_evaluation_id`` anchor, and (c) a manual latest-run origin is
    REJECTED TODAY, at the route.  EXT-2 defers that decision to the service
    for order-id-bearing requests, so an implementation that DEFERS the guard
    without RELOCATING it writes the row -- and passes case 37, case 37b and
    every other case in this plan, because 37b plants a link that ARRIVES and
    therefore exercises the race rather than the stable no-link outcome.
    """
    other = "ZZQQ"                       # no candidate row in ANY run
    conn, cfg, _ = build_world(tmp_path, "c37c")
    run_id = conn.execute(
        "SELECT id FROM pipeline_runs ORDER BY id LIMIT 1").fetchone()[0]
    conn.execute(
        "INSERT INTO pattern_evaluations (id, pipeline_run_id, ticker, "
        "pattern_class, detector_version, geometric_score, "
        "geometric_score_json, composite_score, structural_evidence_json, "
        "feature_distribution_log_json, window_start_date, window_end_date, "
        "created_at) "
        "VALUES (5, ?, ?, 'vcp', 'v1', 0.8, '{}', 0.8, '{}', '{}', "
        "'2026-07-01', '2026-07-24', '2026-07-24T17:44:45')",
        (run_id, other))
    conn.commit()
    request = req(ticker=other, pattern_evaluation_id=5,
                  schwab_source_value_json=envelope(symbol=other))
    from swing.trades.origin import derive_trade_origin
    assert derive_trade_origin(
        conn, other, EntryPath.MANUAL_WEB_FORM) == "manual_off_pipeline", (
        "the fixture must produce the MANUAL server origin the guard keys on, "
        "or the case passes for a reason unrelated to its clause")
    with pytest.raises(PatternEvaluationAnchorError) as exc:
        enter(conn, cfg, request)
    assert "manual_off_pipeline" in str(exc.value)
    assert conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0

    # AND THE CONTROL: with NO order id the route still owns the guard, so the
    # service must NOT refuse -- otherwise the relocation would have become a
    # DUPLICATION and every non-latched PE-anchored entry would break.
    control, cfg_c, _ = build_world(tmp_path, "c37cctl")
    control.commit()
    enter(control, cfg_c, req(
        ticker=other, schwab_source_value_json=None,
        fill_origin="operator_typed"))
    assert control.execute(
        "SELECT COUNT(*) FROM trades").fetchone()[0] == 1


# ===========================================================================
# THE LOCK -- S2.2 (a)-(d), tested with ``cfg`` PASSED
# ===========================================================================
def _persisted_row(conn, trade_id) -> dict:
    cols = [r[1] for r in conn.execute("PRAGMA table_info(trades)")]
    vals = conn.execute(
        "SELECT * FROM trades WHERE id = ?", (trade_id,)).fetchone()
    return dict(zip(cols, vals, strict=True))


# ---------------------------------------------------------------------------
# THE PRE-ARC REFERENCE ROW -- captured by RUNNING the base commit, not by
# running this branch twice (Codex 22A-R4-08(b)).
#
# PROVENANCE.  Produced by executing `record_entry` in a detached checkout of
# the arc's base commit `a18a3771` (schema v36, before migration 0037), against
# a world built exactly as `build_world` builds it minus every 22-A-only
# artefact -- the same evaluation run 121, the same FTRE `aplus` candidate with
# the same close / pivot / stop, the same `seed_pipeline_run` +
# `rebase_status_history_recorded_at`, and the same `EntryRequest` field values
# `req(schwab_source_value_json=None, fill_origin="operator_typed")` produces.
# Regenerate the same way: check out `a18a3771` detached, replay that fixture,
# and dump `SELECT * FROM trades`.
#
# WHY A PINNED GOLDEN AND NOT A SECOND RUN.  The old test compared a
# `cfg`-passed run against a `cfg=None` run of THIS branch's code.  Both are
# post-change, so a regression shared by the two paths passes -- it proved
# DETERMINISM, and clause (a) claims BYTE-IDENTITY WITH THE PRE-ARC ROW.  A
# lock that cannot fail its own lock is not a lock.
#
# Every value here is deterministic: `id` and `candidate_id` come from a fresh
# database's rowid sequence, and both timestamps derive from `entry_date`, not
# from the wall clock.
# ---------------------------------------------------------------------------
LOCK_A_PRE_ARC_ROW: dict = {
    "candidate_id": 1,
    "catalyst": "technical_only",
    "catalyst_other_description": None,
    "chart_pattern_algo": None,
    "chart_pattern_algo_confidence": None,
    "chart_pattern_classification_pipeline_run_id": None,
    "chart_pattern_operator": None,
    "current_avg_cost": 18.5,
    "current_size": 2.0,
    "current_stop": 14.0,
    "disqualifying_process_violation": None,
    "emotional_state_pre_trade": '["calm"]',
    "entry_date": "2026-07-27",
    "entry_grade": None,
    "entry_intent": None,
    "entry_price": 18.5,
    "event_date": None,
    "event_handling": "not_applicable",
    "event_risk_present": 0,
    "event_type": None,
    "exit_grade": None,
    "expected_scenario": "20% in 4 weeks",
    "failure_mode": None,
    "gap_risk_handling": "not_applicable",
    "gap_risk_present": 0,
    "hypothesis_label": None,
    "id": 1,
    "industry": "",
    "initial_shares": 2,
    "initial_stop": 14.0,
    "invalidation_condition": "break of the stop",
    "last_fill_at": "2026-07-27T16:00:00",
    "lesson_learned": None,
    "management_grade": None,
    "market_regime": "Bullish",
    "mistake_cost_confidence": None,
    "mistake_tags": None,
    "notes": None,
    "pattern_evaluation_id": None,
    "planned_target_R": None,
    "pre_trade_locked_at": "2026-07-27T16:00:00",
    "premortem_additional": None,
    "premortem_execution": "size too small",
    "premortem_market_sector": "sector breaks",
    "premortem_technical": "pivot fails",
    "process_grade": None,
    "realized_R_if_plan_followed": None,
    "reviewed_at": None,
    "risk_policy_id_at_lock": 1,
    "sector": "",
    "state": "entered",
    "thesis": "the mandate fired",
    "ticker": "FTRE",
    "trade_origin": "pipeline_aplus",
    "watchlist_entry_target": None,
    "watchlist_initial_stop": None,
    "why_now": "through the pivot",
}


def test_the_lock_a_an_unlatched_fill_is_byte_identical_with_cfg_passed(
        tmp_path) -> None:
    """LOCK clause (a), against the PRE-ARC row captured off `a18a3771`.

    Both arms are asserted against the SAME external reference: `cfg` PASSED
    (the production path -- testing only `cfg=None` would prove the arc is
    inert when switched off, which is not the claim) and `cfg=None` (the
    pre-existing caller). A regression shared by the two post-change paths
    fails here and could not fail a two-run comparison.

    The COLUMN SET is asserted too. If a later change adds a `trades` column,
    a dict comparison would fail on the diff -- but a comparison written to
    tolerate that (subset, or key intersection) would silently stop covering
    the new column, so the failure is left loud and this line says why.
    """
    conn_a, cfg_a, _ = build_world(tmp_path, "lockA")
    conn_a.commit()
    a = _persisted_row(conn_a, enter(conn_a, cfg_a, req(
        schwab_source_value_json=None, fill_origin="operator_typed")).trade_id)

    conn_b, _cfg_b, _ = build_world(tmp_path, "lockB")
    conn_b.commit()
    b = _persisted_row(conn_b, record_entry(
        conn_b, req(schwab_source_value_json=None,
                    fill_origin="operator_typed"),
        soft_warn=SOFT, hard_cap=HARD, force=False).trade_id)

    assert set(a) == set(LOCK_A_PRE_ARC_ROW), (
        "the `trades` column set moved relative to the pre-arc capture: "
        f"{sorted(set(a) ^ set(LOCK_A_PRE_ARC_ROW))}")
    assert a == LOCK_A_PRE_ARC_ROW, "cfg PASSED diverged from the pre-arc row"
    assert b == LOCK_A_PRE_ARC_ROW, "cfg=None diverged from the pre-arc row"


def test_the_lock_c_every_pre_existing_failure_branch_is_unchanged(
        tmp_path) -> None:
    """LOCK clause (c), with ``cfg`` PASSED.

    The stop-vs-entry branch is exercised because it sits BEFORE the seam and
    is the cheapest proof that the seam did not move ahead of the gauntlet.
    """
    conn, cfg, _ = build_world(tmp_path, "lockC")
    conn.commit()
    with pytest.raises(ValueError, match="stop must be < entry"):
        enter(conn, cfg, req(initial_stop=99.0))
    assert conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0


def test_the_lock_d_an_envelope_without_an_order_id_costs_zero_queries(
        tmp_path) -> None:
    """LOCK clause (d), asserted by COUNTING STATEMENTS on the connection.

    The recognition read parses the operator-submitted envelope and nothing
    else, so a fill with no usable broker order id must issue no additional
    query at all -- which is what keeps the ordinary path free.
    """
    conn, cfg, _ = build_world(tmp_path, "lockD")
    conn.commit()
    baseline: list[str] = []
    conn.set_trace_callback(baseline.append)
    try:
        record_entry(conn, req(ticker="ZZAA", schwab_source_value_json=None,
                               fill_origin="operator_typed"),
                     soft_warn=SOFT, hard_cap=HARD, force=False)
    finally:
        conn.set_trace_callback(None)

    conn2, cfg2, _ = build_world(tmp_path, "lockD2")
    conn2.commit()
    seen: list[str] = []
    conn2.set_trace_callback(seen.append)
    try:
        enter(conn2, cfg2, req(ticker="ZZAA", schwab_source_value_json=None,
                               fill_origin="operator_typed"))
    finally:
        conn2.set_trace_callback(None)
    assert len(seen) == len(baseline), (
        f"the seam issued {len(seen) - len(baseline)} extra statements on a "
        f"fill with no usable order id")


def test_a_caller_held_transaction_is_rejected_on_the_latched_path(
        tmp_path) -> None:
    """The single-transaction contract: REJECT, never auto-detect.

    An ``in_transaction`` auto-detect guard re-introduces the very race the
    explicit lock closed.
    """
    from swing.trades.entry import CallerHeldEntryTransactionError

    conn, cfg, candidate_id = build_world(tmp_path, "callerheld")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    conn.execute("BEGIN IMMEDIATE")
    try:
        with pytest.raises(CallerHeldEntryTransactionError):
            enter(conn, cfg, req())
    finally:
        conn.rollback()
    assert conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0


def test_the_validator_never_keys_a_rule_on_the_trade_origin_VALUE() -> None:
    """The property that makes the seam's placement provably safe.

    ``record_entry`` validates BEFORE the override, so the validator sees the
    pre-override ``trade_origin``.  That is only safe because
    ``swing/trades/state.py`` requires the field for PRESENCE and nowhere keys
    a conditional rule on its VALUE -- asserted directly rather than trusted to
    a reading.
    """
    import re

    src = Path(__import__("swing.trades.state", fromlist=["x"]).__file__
               ).read_text(encoding="utf-8")
    hits = [ln for ln in src.splitlines() if "trade_origin" in ln]
    assert hits, "trade_origin vanished from the validator"
    for line in hits:
        assert not re.search(r"trade_origin\s*(==|!=|in\s|not\s+in\s)", line), (
            f"a conditional rule is keyed on the trade_origin VALUE: {line!r}")


# ===========================================================================
# CODEX 22A-R4-01 -- the ORIGIN the reservation was taken for
#
# `derive_trade_origin` runs at :278, BEFORE `BEGIN IMMEDIATE` at :437, and its
# value feeds BOTH the persisted ordinary origin AND the relocated PE-anchor
# guard.  The guard's own comment claims it reads "the world the write lands
# in".  It did not.  A comment asserting an invariant the code does not hold is
# worse than no comment, because it reads true -- gotcha #31, arriving INSIDE a
# fix written to avoid it.
#
# THE WINDOW IS REAL AND THESE TESTS OPEN IT AT ITS TRUE POSITION: the
# concurrent commit fires from a SECOND connection during the PRELIMINARY
# derivation, which is before the reservation exists.  Once `BEGIN IMMEDIATE`
# is held no competing writer can commit at all -- which is the point of taking
# it, and the reason the stale read is the only remaining hole.
# ===========================================================================
def _commit_a_newer_empty_run(db: Path) -> None:
    """A LATER complete pipeline run in which the ticker does not appear.

    `derive_trade_origin` reads the most-recent COMPLETE run and then that
    run's candidate for the ticker.  With no candidate row the answer flips
    `pipeline_aplus` -> `manual_off_pipeline`, which is the cheapest honest
    flip available: it needs no `candidates` write at all, so the immutability
    barrier is never asked to be less than it is.
    """
    other = open_connection(db)
    try:
        other.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, "
            "watch_count, skip_count, excluded_count, error_count) "
            "VALUES (7001, '2026-07-24T17:30:05', '2026-07-24', "
            "'2026-07-27', 1, 0, 0, 1, 0, 0)")
        from tests.trades._cohort_provenance_fixtures import seed_pipeline_run
        seed_pipeline_run(
            other, evaluation_run_id=7001, data_asof_date="2026-07-24",
            action_session_date="2026-07-27",
            started_ts="2026-07-24T17:30:00",
            finished_ts="2026-07-24T17:44:59")
        other.commit()
    finally:
        other.close()


def _race_derive_trade_origin(monkeypatch, db: Path) -> list[str]:
    """Commit the newer run AFTER the first derivation and BEFORE the next.

    Returns the list of values each call returned, so a test can state how many
    derivations happened rather than infer it.
    """
    import swing.trades.entry as entry_mod

    real = entry_mod.derive_trade_origin
    returned: list[str] = []

    def _racing(conn, ticker, entry_path):
        value = real(conn, ticker, entry_path)
        if not returned:                       # the PRELIMINARY call only
            _commit_a_newer_empty_run(db)
        returned.append(value)
        return value

    monkeypatch.setattr(entry_mod, "derive_trade_origin", _racing)
    return returned


def test_the_persisted_origin_is_derived_inside_the_reservation(
        tmp_path, monkeypatch) -> None:
    """PRE-FIX the row lands `pipeline_aplus` with a NULL candidate -- an
    origin claiming a pipeline mandate that the world the write landed in no
    longer carries.  POST-FIX it lands `manual_off_pipeline`.

    Both values are stated because a test that passes under both paths is
    worthless.  The request carries a usable order id (so the reservation is
    taken) and NO accepted link exists (so the ORDINARY chain writes the row) --
    which is exactly the combination that persists the stale value.
    """
    conn, cfg, _ = build_world(tmp_path, "r401origin")
    conn.commit()
    db = tmp_path / "r401origin" / "swing.db"
    returned = _race_derive_trade_origin(monkeypatch, db)

    result = enter(conn, cfg, req())
    origin, cand, label = written(conn, result.trade_id)
    assert returned[0] == "pipeline_aplus", (
        "the fixture must make the PRELIMINARY answer differ from the "
        "committed one, or the case passes without opening the window")
    assert (origin, cand, label) == ("manual_off_pipeline", None, None), (
        "the persisted origin came from the pre-reservation world")
    assert len(returned) == 2, (
        f"the origin was derived {len(returned)} time(s); the reserved path "
        f"must re-derive it inside the transaction")


def test_the_relocated_pe_anchor_guard_judges_the_committed_world(
        tmp_path, monkeypatch) -> None:
    """The guard's comment, made TRUE.

    PRE-FIX the guard sees `pipeline_aplus` (the pre-reservation world), does
    not fire, and the row is WRITTEN carrying a `pattern_evaluation_id` anchor
    the committed world no longer supports.  POST-FIX it sees
    `manual_off_pipeline` and refuses, which is the live production rejection
    22A-R9-03 relocated here rather than deleted.
    """
    conn, cfg, _ = build_world(tmp_path, "r401pe")
    run_id = conn.execute(
        "SELECT id FROM pipeline_runs ORDER BY id LIMIT 1").fetchone()[0]
    conn.execute(
        "INSERT INTO pattern_evaluations (id, pipeline_run_id, ticker, "
        "pattern_class, detector_version, geometric_score, "
        "geometric_score_json, composite_score, structural_evidence_json, "
        "feature_distribution_log_json, window_start_date, window_end_date, "
        "created_at) "
        "VALUES (5, ?, ?, 'vcp', 'v1', 0.8, '{}', 0.8, '{}', '{}', "
        "'2026-07-01', '2026-07-24', '2026-07-24T17:44:45')",
        (run_id, TICKER))
    conn.commit()
    db = tmp_path / "r401pe" / "swing.db"
    returned = _race_derive_trade_origin(monkeypatch, db)

    with pytest.raises(PatternEvaluationAnchorError):
        enter(conn, cfg, req(pattern_evaluation_id=5))
    assert returned[0] == "pipeline_aplus", (
        "the fixture must make the PRELIMINARY answer non-manual, or the "
        "guard fires for a reason unrelated to the race")
    assert conn.execute("SELECT COUNT(*) FROM trades").fetchone()[0] == 0


# ===========================================================================
# CODEX 22A-R4-03 -- a commit that RAISES must still roll back
#
# `conn.commit()` sat in the `else:` clause, OUTSIDE the `except BaseException:`
# handler, so a busy / disk-full / I-O failure at commit left the transaction
# AND its write reservation open on a connection the caller goes on reusing.
# ===========================================================================
class _CommitRaises:
    """A connection whose COMMIT fails and whose ROLLBACK is observable.

    Only the four members `_entry_transaction` touches are proxied; anything
    else raises `AttributeError` loudly rather than silently degrading, so the
    stand-in cannot quietly diverge from the real connection's surface.
    """

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.rolled_back = False

    def execute(self, *args, **kwargs):
        return self._conn.execute(*args, **kwargs)

    def commit(self) -> None:
        raise sqlite3.OperationalError("disk I/O error")

    def rollback(self) -> None:
        self.rolled_back = True
        self._conn.rollback()

    @property
    def in_transaction(self) -> bool:
        return self._conn.in_transaction


def test_a_commit_that_raises_rolls_the_reservation_back(tmp_path) -> None:
    """PRE-FIX: `rolled_back` is False and the connection is STILL in a
    transaction after the raise -- the reservation leaks.  POST-FIX: the
    rollback ran and the connection is clean.

    The exception itself propagates either way, so asserting only the raise
    would pass under both paths.
    """
    from swing.trades.entry import _entry_transaction

    conn, _, _ = build_world(tmp_path, "r403")
    conn.commit()
    proxy = _CommitRaises(conn)

    with pytest.raises(sqlite3.OperationalError, match="disk I/O error"):
        with _entry_transaction(proxy, immediate=True):
            proxy.execute(
                "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
                "action_session_date, tickers_evaluated, aplus_count, "
                "watch_count, skip_count, excluded_count, error_count) "
                "VALUES (8001, '2026-07-24T17:30:05', '2026-07-24', "
                "'2026-07-27', 1, 0, 0, 1, 0, 0)")

    assert proxy.rolled_back, (
        "the commit raised OUTSIDE the rollback handler; the write "
        "reservation is still held on a connection the caller reuses")
    assert not conn.in_transaction
    assert conn.execute(
        "SELECT COUNT(*) FROM evaluation_runs WHERE id = 8001"
    ).fetchone()[0] == 0


# ===========================================================================
# 22A-R9-03 x 22A-R4-06 -- THE RELOCATED GUARD FIRES ON THE ORDINARY PATH ONLY
# (RD, ruled 2026-08-25)
# ===========================================================================
def _pe_anchored_world(tmp_path, name, *, closes):
    """A recognised link, a `pattern_evaluation_id` anchor, a MANUAL origin.

    All THREE conditions the relocated PE-anchor guard keys on, assembled
    together so a test can vary one.  Each is established here rather than
    assumed:

      * the PE row is planted on the fixture's own pipeline run, so tier (b)'s
        server re-derivation would resolve it;
      * a LATER complete run is seeded WITHOUT the ticker, so
        `derive_trade_origin` returns `manual_off_pipeline` -- the fire has
        rolled out of the latest run, which is the real-world shape the guard
        exists for.  Without this the FTRE fire is still `aplus` in the latest
        run, the origin is `pipeline_aplus`, and every test below passes
        because the guard's third condition was never met.
    """
    from tests._latch_probe_world_22a import seed_run
    from tests.trades._cohort_provenance_fixtures import seed_pipeline_run

    conn, cfg, candidate_id = build_world(tmp_path, name, closes=closes)
    run_id = conn.execute(
        "SELECT id FROM pipeline_runs ORDER BY id LIMIT 1").fetchone()[0]
    conn.execute(
        "INSERT INTO pattern_evaluations (id, pipeline_run_id, ticker, "
        "pattern_class, detector_version, geometric_score, "
        "geometric_score_json, composite_score, structural_evidence_json, "
        "feature_distribution_log_json, window_start_date, window_end_date, "
        "created_at) "
        "VALUES (7, ?, ?, 'vcp', 'v1', 0.8, '{}', 0.8, '{}', '{}', "
        "'2026-07-01', '2026-07-24', '2026-07-24T17:44:45')",
        (run_id, TICKER))
    seed_run(conn, 901, FILL_SESSION)
    conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
        "pivot, initial_stop, rs_method) VALUES (901, 'OTHR', 'aplus', 20.0, "
        "20.5, 16.0, 'universe')")
    seed_pipeline_run(
        conn, evaluation_run_id=901,
        data_asof_date=date(2026, 7, 24).isoformat(),
        action_session_date=FILL_SESSION.isoformat(),
        started_ts="2026-07-24T17:30:00", finished_ts="2026-07-24T17:44:00")
    conn.commit()

    from swing.trades.origin import derive_trade_origin
    assert derive_trade_origin(
        conn, TICKER, EntryPath.MANUAL_WEB_FORM) == "manual_off_pipeline", (
        "the fixture must produce the MANUAL server origin the guard keys on, "
        "or every case built on it passes for a reason unrelated to its clause")
    return conn, cfg, candidate_id


def test_a_recognised_and_refused_entry_is_written_not_refused(
        tmp_path) -> None:
    """RD's one-line ruling, encoded: the guard is for the ORDINARY path.

    PRE-RULING the guard fired on ``not latched.admitted``, and
    ``recognised_but_underivable`` IS a not-admitted state -- so an entry
    whose mandate the ladder recognised and REFUSED raised
    ``PatternEvaluationAnchorError`` and NO row was written.  POST-RULING the
    honest-unset row is WRITTEN.  Both values are stated so the assertion
    distinguishes.

    RD's grounds: **cohort bookkeeping never blocks a money-bearing entry.**
    The refusal is about the LABEL, never about the ENTRY -- so a guard whose
    condition is "did not admit" is one clause too wide.  The plan says the
    same thing at two sites (S5.2 outcome (c), S3.7 lens row 43).
    """
    conn, cfg, candidate_id = _pe_anchored_world(
        tmp_path, "r9x", closes=_breach_closes(date(2026, 7, 23)))
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()

    from swing.trades.latched_origin import resolve_latched_provenance
    verdict = resolve_latched_provenance(conn, cfg, req(pattern_evaluation_id=7))
    assert verdict.recognised_but_underivable, (
        "the fixture must produce a RECOGNISED-AND-REFUSED verdict or the "
        "case proves nothing about the clause it names")

    result = enter(conn, cfg, req(pattern_evaluation_id=7))
    assert written(conn, result.trade_id) == ("manual_off_pipeline", None, None)


def test_the_pe_backlink_survives_on_the_honest_unset_row_22a_r4_06(
        tmp_path) -> None:
    """RD's `22A-R4-06` ruling, with the criterion VERIFIED not inherited.

    RULED: the honest-unset row KEEPS ``pattern_evaluation_id`` **iff** the PE
    anchor was derived by its own independent ladder, and DROPS anything
    derived FROM the refused latch recognition.  Grounds: the all-three-or-none
    rule covers the COHORT TRIPLE -- three statements of ONE provenance claim
    -- while the PE backlink is a DIFFERENT evidence chain, and categories
    differing in evidence kind are never merged.

    THE VERIFICATION, stated with the read that established it.  The 5-tier
    ladder is ``swing/web/routes/trades.py`` from ``pe_anchor_raw = ...``
    through ``resolved_pe_id = parsed_pe_id``.  Tier (a) parses the submitted
    string; tier (b) reads ``pattern_evaluations`` BY ID; tier (c) compares
    that row's ticker to the submitted ticker; tier (d) compares the
    form-render ``pipeline_run_id`` anchor to that row's own
    ``pipeline_run_id``; then ``resolved_pe_id = parsed_pe_id`` -- the value
    comes from (a)/(b) and from nothing else.  Tier (e) is a REFUSAL gate that
    contributes no value, and its 22-A skip condition reads the ENVELOPE
    (``broker_order_id_from_envelope``), never the link table.  **No tier
    touches latch_order_mandate_links, latch_order_intents or
    resolve_latched_provenance.**  The ladder is INDEPENDENT, so the backlink
    SURVIVES the refusal.

    The three COHORT keys are asserted NULL in the same breath, because the
    ruling's force is in the contrast: what dies is what the refused claim
    produced; what lives is an independently-derived true fact.
    """
    conn, cfg, candidate_id = _pe_anchored_world(
        tmp_path, "r406", closes=_breach_closes(date(2026, 7, 23)))
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    result = enter(conn, cfg, req(pattern_evaluation_id=7))
    row = conn.execute(
        "SELECT trade_origin, candidate_id, hypothesis_label, "
        "pattern_evaluation_id FROM trades WHERE id = ?",
        (result.trade_id,)).fetchone()
    assert row == ("manual_off_pipeline", None, None, 7)


def test_the_pe_ladder_reads_nothing_from_the_latch_recognition_path() -> None:
    """AND THE CRITERION IS PINNED MECHANICALLY, not left to the docstring.

    RD's ruling is conditional -- the backlink survives IFF the PE ladder is
    independent -- so the test that matters is the one that FAILS on the day a
    tier starts consulting the latch.  A prose claim about independence cannot
    fail; this reads the ladder's source and asserts the absence.

    SCOPE, STATED: the walk covers the 5-tier block only (from the
    ``pe_anchor_raw`` assignment through the ``resolved_pe_id`` assignment),
    because that is the span RD's criterion is about.  The route's OTHER latch
    read -- EXT-2's envelope rung, which decides whether tier (e) runs -- is
    outside it by design and is excised BY NAME below, so the boundary is a
    decision rather than an oversight.
    """
    import re
    from pathlib import Path

    source = (Path(__file__).resolve().parents[2]
              / "swing" / "web" / "routes" / "trades.py").read_text(
                  encoding="utf-8")
    start = source.index("pe_anchor_raw = pattern_evaluation_id.strip()")
    end = source.index("resolved_pe_id = parsed_pe_id", start)
    block = source[start:end]
    excised, count = re.subn(
        r"from swing\.trades\.latched_origin import\s+"
        r"broker_order_id_from_envelope.*?_deferred_order_id is None:",
        "", block, flags=re.S)
    assert count == 1, (
        "EXT-2's envelope rung was not found in the ladder block; the "
        "excision below would then be silently vacuous, which is the "
        "existence-is-not-completeness class arriving in a scope carve-out")
    forbidden = ("latch_order_mandate_links", "latch_order_intents",
                 "resolve_latched_provenance", "latched_origin",
                 "freeze_tier")
    hits = [token for token in forbidden if token in excised]
    assert not hits, (
        f"the 5-tier PE ladder now reads the latch recognition path ({hits}); "
        "RD's 22A-R4-06 ruling makes the honest-unset row's backlink "
        "conditional on that ladder being INDEPENDENT, so this changes the "
        "ruling's premise and must be re-routed, not patched")
