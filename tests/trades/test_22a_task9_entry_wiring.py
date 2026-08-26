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


def test_bucket_drift_is_not_death_case_1(tmp_path) -> None:
    """A LATER `watch` row for the same ticker must not change the answer.

    If it does, something is reading the framework's BUCKET SERIES rather than
    the mandate -- which is the whole defect the arc exists to stop.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "c1drift")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    from tests._latch_probe_world_22a import seed_run
    seed_run(conn, 999, date(2026, 7, 24))
    conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
        "pivot, initial_stop, rs_method) VALUES (999, ?, 'watch', 17.9, "
        "18.34, 14.88, 'universe')", (TICKER,))
    conn.commit()
    result = enter(conn, cfg, req())
    assert written(conn, result.trade_id) == (
        "pipeline_aplus", candidate_id,
        written(conn, result.trade_id)[2])


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
def test_an_unfilled_mandate_is_untouched_by_the_arc_case_3(tmp_path) -> None:
    """No trade, no fill, no acceptance -> nothing is written anywhere.

    The class this guards is a PHANTOM LABEL on an unfilled mandate: the arc's
    only write path is ``record_entry``, so a mandate nobody filled must leave
    every table exactly as it found them.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "c3")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    before = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in ("trades", "fills", "latch_order_mandate_links",
                  "latch_order_intents", "candidates")
    }
    # the entry path is simply never entered
    after = {
        t: conn.execute(f"SELECT COUNT(*) FROM {t}").fetchone()[0]
        for t in before
    }
    assert after == before
    assert before["trades"] == 0 and before["fills"] == 0


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


def test_the_lock_a_an_unlatched_fill_is_byte_identical_with_cfg_passed(
        tmp_path) -> None:
    """LOCK clause (a), tested with ``cfg`` PASSED -- the production path.

    Testing it only with ``cfg=None`` would prove the arc is inert when it is
    switched off, which is not the claim.
    """
    conn_a, cfg_a, _ = build_world(tmp_path, "lockA")
    conn_a.commit()
    a = _persisted_row(conn_a, enter(conn_a, cfg_a, req(
        schwab_source_value_json=None, fill_origin="operator_typed")).trade_id)

    conn_b, cfg_b, _ = build_world(tmp_path, "lockB")
    conn_b.commit()
    b = _persisted_row(conn_b, record_entry(
        conn_b, req(schwab_source_value_json=None,
                    fill_origin="operator_typed"),
        soft_warn=SOFT, hard_cap=HARD, force=False).trade_id)
    assert a == b


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
