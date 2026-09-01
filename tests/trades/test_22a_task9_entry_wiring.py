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

import contextlib
import json
import sqlite3
from datetime import date
from pathlib import Path

import pytest

from swing.data.db import ensure_schema, open_connection, run_migrations
from swing.data.models import FREEZE_TIER_LIVE_AT_ACCEPTANCE
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
def build_world(tmp_path: Path, name: str, *, closes=None, pre_barrier=False,
                initial_stop=None):
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
    # `initial_stop` is a per-case dimension for exactly one case (the case-6
    # display-precision variant, whose whole subject is the frozen stop's
    # third decimal); every other caller leaves it at the fire's own.
    _fire_over = {} if initial_stop is None else {"initial_stop": initial_stop}
    if pre_barrier:
        conn = open_connection(root / "swing.db")
        run_migrations(conn, target_version=36)
        candidate_id = seed_fire(conn, **_fire_over)
        conn.commit()
        run_migrations(conn, target_version=37, backup_dir=root / "bak")
    else:
        conn = ensure_schema(root / "swing.db")
        candidate_id = seed_fire(conn, **_fire_over)
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

    **S3.1'S RESOLUTION HALF IS ASSERTED HERE TOO, AND IT WAS ASSERTED BY NO
    TEST BOUND TO CASE 1** (semantic re-audit 2026-08-31).  S3.1 names the two
    intent ids, the broker order id, `clear_reason`, `bars_through`,
    `horizon_session` and the freeze tier as part of the required outcome; the
    persisted-row half was pinned well and that half was not.  `bars_through`
    was asserted exactly ONCE in the whole arc, in a task-6 test carrying no
    case id.

    THE VALUES ARE THE PROBE WORLD'S, not OII's -- the module docstring
    declares that substitution with its reasoning -- so what is bound here is
    the SHAPE S3.1 specifies over this fixture's own rows: every id is read
    back from the ledger rather than typed, so a fixture that quietly stopped
    matching the emitter fails instead of agreeing with itself.
    """
    from swing.trades.latched_origin import resolve_latched_provenance

    conn, cfg, candidate_id = build_world(tmp_path, "c1")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()

    verdict = resolve_latched_provenance(conn, cfg, req())
    assert verdict.admitted is True, verdict.decline_reason
    place_id, validity_id, order_id = conn.execute(
        "SELECT place_intent_id, validity_intent_id, broker_order_id "
        "  FROM latch_order_mandate_links").fetchone()
    assert verdict.order.place_intent_id == place_id
    assert verdict.order.validity_intent_id == validity_id
    assert verdict.order.broker_order_id == order_id
    assert verdict.clear_reason is None, (
        "an admitted mandate carries NO terminal; a non-None value here is a "
        "same-session tie admission wearing an armed admission's clothes")
    assert verdict.clear_session is None
    assert verdict.freeze_tier == FREEZE_TIER_LIVE_AT_ACCEPTANCE
    # The judging window is [anchor, fill_session - 1] and the horizon is the
    # fill session itself: two DIFFERENT sessions, and collapsing them into one
    # field with two definitions is the defect S2 records by name.
    assert verdict.horizon_session == FILL_SESSION
    assert verdict.bars_through == max(
        s for s in BASE_CLOSES if s < FILL_SESSION), (
        "bars_through must be the last session the derivation actually judged")
    assert verdict.bars_through < verdict.horizon_session
    assert verdict.window_empty is False
    assert verdict.archive_status == "ok"
    # THE SNAPSHOT EQUALITY: the link's frozen pair IS the fire's own.
    assert (verdict.order.frozen_pivot, verdict.order.frozen_invalidation) == \
        conn.execute(
            "SELECT pivot, initial_stop FROM candidates WHERE id = ?",
            (candidate_id,)).fetchone()

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

    **THIS IS TRADE 25'S LIVE OUTCOME, NOT A SYNTHETIC TWIN'S HYGIENE.**  Under
    Option C every fire that exists today is PRE-BARRIER, so this row is what
    the live entry path does on trade 25 the day `0037` lands, and **S9's
    operator gate is written around exactly it** (RD, ruled 2026-09-01).

    **THE PERSISTED ROW IS IDENTICAL UNDER EVERY REFUSAL REASON.**
    `pre_barrier_unproven`, `no_accepted_latch_order`, `mandate_not_alive`,
    `aliveness_unverifiable` and the R3-13 inconsistent-pair refusal all land
    on `("manual_off_pipeline", None, None)` BY RD'S OWN RULING -- so a row
    asserting only the persisted triple passes an implementation refusing for
    entirely the wrong reason.  Three things are required and all three are
    here:

    * **(a)** the reason `pre_barrier_unproven` SPECIFICALLY, not merely
      non-admission;
    * **(b)** that the refusal came from **RUNG 9**, copying `5b-pre`'s
      pattern -- `clear_reason` `None` and NO aliveness evidence recorded.
      Without it an implementation that PROBES FIRST and refuses later passes
      on the reason string alone, which is the exact hole `5b-pre` was written
      to close;
    * **(c)** this docstring, saying which of the two it is.

    RD's diagnosis of the cause is worth keeping at the site: **case 2, forty
    lines below in this same file, states this exact defect in its own
    docstring and pairs itself with a byte-identity control.**  The knowledge
    was present in the file and was not applied one function earlier -- the
    per-clause discriminator rule needs applying per CASE, not per FILE.
    """
    from swing.trades.latched_origin import resolve_latched_provenance

    conn, cfg, candidate_id = build_world(tmp_path, "c1pre", pre_barrier=True)
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()

    verdict = resolve_latched_provenance(conn, cfg, req())
    assert verdict.decline_reason == "pre_barrier_unproven", (
        "the row lands honest-unset under EVERY refusal reason, so the reason "
        "is what this case is about")
    assert verdict.clear_reason is None, (
        "a terminal was reported, so the probe RAN -- rung 9 must refuse "
        "before it")
    assert verdict.probe_evidence is None, (
        "aliveness evidence was recorded, so the implementation probed first "
        "and refused later; it would pass on the reason string alone")

    # The SUBMITTED label is non-NULL, which is the discriminator for the
    # persisted half: an implementation that kept it would write a row Demand
    # C's `_gate_on_unset_state` can never correct.
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

    **THE INVALIDATION-SPECIFIC HALF WAS MISSING** (semantic re-audit
    2026-08-31).  S3.5 states the required result IN FULL --
    `mandate_not_alive` with `clear_reason='invalidation'` and its
    `clear_session` -- and it states it in full precisely to prevent what this
    row did: assert only the persisted triple, which is identical under ANY
    refusal reason, so a fixture that refused for a coverage hole or an
    unreadable ledger passed.  The breach SESSION is named too, because the
    difference between 5a and 5b is which session carries it.
    """
    from swing.trades.latched_origin import resolve_latched_provenance

    breach_session = date(2026, 7, 23)
    conn, cfg, candidate_id = build_world(
        tmp_path, "c5a", closes=_breach_closes(breach_session))
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()

    verdict = resolve_latched_provenance(conn, cfg, req())
    assert verdict.decline_reason == "mandate_not_alive"
    assert verdict.clear_reason == "invalidation", (
        "the row lands honest-unset under every refusal reason; the "
        "invalidation is what this case is about")
    assert verdict.clear_session == breach_session

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


def test_the_display_precision_variant_varies_BOTH_operands_case_6(
        tmp_path) -> None:
    """CASE 6's DISPLAY-PRECISION VARIANT -- lens clauses 7 and 30, and S3.6's
    own last bullet (added by review 22A-R15-13).

    **THIS WAS ABSENT FROM THE ARC** (semantic re-audit 2026-08-31): the
    strict-inequality half was asserted and the BOTH-OPERANDS rounding half was
    not, measured by grep over all twenty `test_22a_*` modules.

    **WHY BOTH OPERANDS.**  A variant that rounds only the CLOSE is passed by
    a close-only implementation, which is how the earlier geometry failed to
    discriminate.  The fixture needs a frozen stop and a close that are
    UNEQUAL raw and EQUAL at display precision, with the close BELOW the stop,
    so that every partial implementation refuses and only the both-operands
    one admits:

        raw           14.8799 <  14.884   -> refuse
        close-only    14.88   <  14.884   -> refuse
        stop-only     14.8799 <  14.88    -> refuse
        BOTH          14.88   <  14.88    -> ADMIT

    The plan states the geometry on OII's scale (`41.424` / `41.4199`); this
    module's fire is FTRE, so the same DIGIT PATTERN is applied to its own
    stop rather than re-pointing the whole fixture at another ticker.  Both
    arithmetics are ASSERTED below rather than asserted about, so the case
    cannot silently stop discriminating.
    """
    frozen_stop = 14.884
    equal_at_dp = 14.8799
    assert round(frozen_stop, 2) == round(equal_at_dp, 2) == 14.88, (
        "the operands must be EQUAL at display precision or the variant is "
        "the strict-inequality case again")
    assert equal_at_dp < frozen_stop, (
        "the close must be BELOW the stop raw, or a no-rounding "
        "implementation admits and the case discriminates nothing")

    closes = dict(BASE_CLOSES)
    closes[date(2026, 7, 23)] = equal_at_dp
    conn, cfg, candidate_id = build_world(
        tmp_path, "c6dp", closes=closes, initial_stop=frozen_stop)
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    assert conn.execute(
        "SELECT frozen_invalidation FROM latch_order_mandate_links"
    ).fetchone()[0] == frozen_stop, (
        "the mint did not freeze the third-decimal stop, so the case is about "
        "a different value than the one it names")

    result = enter(conn, cfg, req())
    origin, cand, _ = written(conn, result.trade_id)
    assert (origin, cand) == ("pipeline_aplus", candidate_id), (
        "a close-only, stop-only or no-rounding invalidation comparison "
        "refuses here")


def test_the_pre_barrier_twin_of_the_boundary_refuses_case_6_pre(
        tmp_path) -> None:
    """ONE dimension varies from case 6: the epoch boundary.

    **THE FIXTURE WAS ALREADY THE BASE CASE'S -- WHAT WAS MISSING IS THE
    REASON** (semantic re-audit 2026-08-31).  `pre_barrier_unproven` is the
    thing the twin convention exists to PIN, and the persisted row is
    identical under every refusal reason, so an implementation that refused
    case 6 for a coverage or drift reason passed this twin.  `5b-pre`, in this
    same module, shows the shape and it is copied here.
    """
    from swing.trades.latched_origin import resolve_latched_provenance

    closes = dict(BASE_CLOSES)
    closes[date(2026, 7, 23)] = STOP
    conn, cfg, candidate_id = build_world(
        tmp_path, "c6pre", closes=closes, pre_barrier=True)
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    verdict = resolve_latched_provenance(conn, cfg, req())
    assert verdict.decline_reason == "pre_barrier_unproven"
    assert verdict.clear_reason is None
    assert verdict.probe_evidence is None, (
        "rung 9 must refuse BEFORE the probe, or the twin passes on the "
        "reason string alone")
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

    **AND THE LINK NOW ACTUALLY ARRIVES** (semantic re-audit 2026-08-31).  The
    reservation half was asserted and the ARRIVAL -- the event lens clause 38b
    names the case for -- was NOT BUILT: the spy carried the comment *"and NOW
    the link arrives"* followed only by a delegation to the real lookup, so
    the world contained no link at any point and the row that landed was the
    ordinary one.  The link is planted INSIDE the spy, on the reserved
    connection, exactly as T10's case 37b plants one at the route -- and the
    written row is asserted to reflect it, which is the half the case exists
    for.  Planting it on a SECOND connection is impossible BY CONSTRUCTION
    here, and that is the same reservation this row's first half proves.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "c21b")
    conn.commit()
    db = tmp_path / "c21b" / "swing.db"
    observed: list[bool] = []
    arrived: list[int] = []

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
        # been "no link".  On the RESERVED connection, because no other one
        # can write -- which is precisely what the assertion above measured.
        if not arrived:
            order = accept_and_link(conn_, candidate_id,
                                    session=ACCEPT_SESSION)
            arrived.append(int(order.link_id))
        return real(conn_, broker_order_id=broker_order_id)

    lo.find_accepted_latch_order = _observe
    try:
        result = enter(conn, cfg, req())
    finally:
        lo.find_accepted_latch_order = real
    assert observed and all(observed), (
        "the authoritative read ran WITHOUT a write reservation; a competing "
        "writer could commit between it and the INSERT")
    assert arrived, "the link never arrived, so the case's own event is absent"
    # THE ARRIVED LINK IS WHAT THE ROW REFLECTS.  An implementation that
    # reserved only on the recognised-latched path would have taken the
    # ordinary chain on the stale negative and written
    # ('manual_off_pipeline', None) -- the fire has rolled out of the latest
    # complete run, so the two outcomes are distinguishable here.
    assert written(conn, result.trade_id)[:2] == (
        "pipeline_aplus", candidate_id), (
        "the row does not reflect the link that arrived inside the window")


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


def test_the_lock_d_a_fill_with_NO_ENVELOPE_costs_zero_queries(
        tmp_path) -> None:
    """LOCK clause (d), asserted by COUNTING STATEMENTS on the connection.

    RENAMED TO WHAT IT MEASURES (self-sweep SS-13).  It was called
    `..._an_envelope_without_an_order_id_...` while its body passes
    `schwab_source_value_json=None` -- no envelope at all.  The two were the
    same thing until PERSIST-CANONICAL, which taught the sole fills writer to
    persist a reading for any fill that CARRIES an envelope; the case the old
    NAME described now costs three statements, and the case the body actually
    runs still costs none.  The name went on reading true.  The next case
    covers the other half.

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


def _identity_related(sql: str) -> bool:
    return ("fill_envelope_identity" in sql) or ("sqlite_master" in sql)


def test_the_lock_d_an_envelope_naming_no_order_costs_ONLY_the_reading(
        tmp_path) -> None:
    """THE CASE THE OTHER TEST'S NAME CLAIMED, measured honestly (SS-13).

    LOCK clause (d)'s subject is **the RESOLVER**: *"when the envelope carries
    no usable broker order id, the resolver issues ZERO additional database
    queries"*.  That is still exactly true -- such a request is not recognised,
    takes no reservation and never reaches the resolver at all.

    What DID change is outside the clause and must not hide behind it: the
    fills writer now persists the authority's reading for any fill that
    CARRIES an envelope.  So this asserts the clause where it lives -- every
    statement in the delta is an identity-table statement, i.e. the resolver
    and the ordinary chain added nothing -- rather than asserting a total that
    would quietly absorb a future resolver query.
    """
    conn, cfg, _ = build_world(tmp_path, "lockD3")
    conn.commit()
    baseline: list[str] = []
    conn.set_trace_callback(baseline.append)
    try:
        enter(conn, cfg, req(ticker="ZZAB", schwab_source_value_json=None,
                             fill_origin="operator_typed"))
    finally:
        conn.set_trace_callback(None)

    conn2, cfg2, _ = build_world(tmp_path, "lockD4")
    conn2.commit()
    seen: list[str] = []
    conn2.set_trace_callback(seen.append)
    try:
        enter(conn2, cfg2,
              req(ticker="ZZAB",
                  schwab_source_value_json='{"schwab_instrument_symbol": "Z"}',
                  fill_origin="operator_typed"))
    finally:
        conn2.set_trace_callback(None)

    assert [s for s in seen if _identity_related(s)], (
        "this case is about the reading's cost; if nothing identity-related "
        "ran, it is measuring a world where the reshape did not apply")
    assert (len([s for s in seen if not _identity_related(s)])
            == len([s for s in baseline if not _identity_related(s)])), (
        "a NON-identity statement was added for a fill whose envelope names "
        "no order id, which is LOCK clause (d)'s own subject")


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
        r"envelope_recognises_an_order.*?resolved_schwab_source_value_json,\s*"
        r"\):",
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


def test_an_inverted_window_gives_the_ENTRY_honest_unset_keys(tmp_path) -> None:
    """22A-R3-07 at the grain where it actually costs something.

    The inverted-window check lived in the correction path's fill-specific
    `gate`, and the LATCH path passes `gate=None`.  On the CORRECTION path the
    model's own validator caught the incoherence at the last moment (with a
    bare ValueError rather than this surface's refusal); on the ENTRY path
    there is no such net -- the row was WRITTEN, carrying the fire's three
    cohort keys derived through a window that bounds nothing.

    PRE-FIX: ``('pipeline_aplus', <candidate>, 'A+ baseline ...')``.
    POST-FIX: ``('manual_off_pipeline', None, None)`` -- the honest-unset row,
    because a refusal inside the shared derivation is `keys_not_derivable` and
    cohort bookkeeping never blocks the entry itself.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "r307e")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    run_ts = conn.execute(
        "SELECT run_ts FROM evaluation_runs WHERE id = 121").fetchone()[0]
    inverted = run_ts[:11] + "17:00:00"
    conn.execute(
        "UPDATE pipeline_runs SET finished_ts = ? WHERE evaluation_run_id = 121",
        (inverted,))
    conn.commit()
    assert run_ts > inverted, (
        "the fixture must INVERT the window or the case pins nothing")
    # THE INVERSION IS SMALL ON PURPOSE (thirty minutes, MEASURED).  A large
    # one -- an epoch-old finished_ts -- makes the AS-OF registry find no
    # covering interval and the derivation refuses for THAT reason instead, so
    # the case would pass pre-fix and prove nothing.  My first version used
    # '2000-01-01' and did exactly that; it was caught by running it against
    # the un-fixed derivation rather than by reading it.

    result = enter(conn, cfg, req())
    assert written(conn, result.trade_id) == ("manual_off_pipeline", None, None)


def test_every_production_record_entry_call_site_passes_cfg() -> None:
    """22A-R6-04's entry half, pinned as a CALLER-SIDE OBLIGATION (#31).

    `cfg=None` is the pre-arc path byte-for-byte -- the LOCK requires that, and
    it is what makes the whole pre-22-A suite a non-regression control.  The
    cost is that a caller who OMITS the config gets the ordinary chain even for
    an order-bearing fill, so the authority is caller-selectable in principle.

    THE CORRECTION PATH IS NOW SCHEMA-PREVENTED (22A-R6-01: the `last_word`
    branch requires the fill's order to resolve to no link), so the residual is
    the ENTRY path alone, and it is SERVICE-prevented rather than
    schema-prevented -- weaker, so it is pinned rather than declared.

    THE SEARCH THAT ESTABLISHES THE MANIFEST is a STATIC AST walk of every
    `.py` under `swing/`, not a token grep: a grep bounds a family from below,
    and the whole point is that a NEW call site added without `cfg` must FAIL
    here rather than be invisible.  Measured today: TWO production call sites,
    `swing/cli.py` and `swing/web/routes/trades.py`, both passing `cfg`.
    """
    import ast

    from pathlib import Path

    root = Path(__file__).resolve().parents[2] / "swing"
    sites: list[str] = []
    for path in sorted(root.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if not isinstance(node, ast.Call):
                continue
            fn = node.func
            name = getattr(fn, "id", None) or getattr(fn, "attr", None)
            if name != "record_entry":
                continue
            where = f"{path.relative_to(root.parent).as_posix()}:{node.lineno}"
            sites.append(where)
            assert any(k.arg == "cfg" for k in node.keywords), (
                f"{where} calls record_entry WITHOUT cfg; the latch mechanism "
                f"is then unreachable from that surface -- silently, because "
                f"every persisted value stays valid")
    assert len(sites) == 2, (
        f"the production record_entry manifest moved: {sites}. Two is the "
        f"measured count (the CLI and the web route); a third surface is a "
        f"decision, not a drive-by")


def test_a_probe_INVARIANT_FAILURE_still_writes_the_entry(tmp_path) -> None:
    """22A-R7-02: a probe malfunction must not block a broker fill.

    `LatchProbeInvariantError` is raised DELIBERATELY at two points inside the
    probe, and both sit AFTER the broad fail-soft handler around
    `build_latch_derivation`.  Nothing between there and `record_entry` caught
    a `RuntimeError`, so PRE-FIX the transaction rolled back and NO TRADE AND
    NO FILL LANDED -- the `0036:26-38` inversion in its purest form, on the
    two states whose own message says the COHORT PROBE malfunctioned.

    POST-FIX the resolver contains it and the honest-unset row is written.
    Both values are stated so the assertion distinguishes; the raise itself is
    unchanged and its probe-grain tests still pin it, because that is how a
    probe defect stays LOUD.

    The invariant is forced by SUBSTITUTING the probe rather than by building
    a world that reaches it: the two raise sites are guarded by conditions the
    fold makes unreachable in a healthy fixture, which is exactly why they are
    invariants.  What this case is about is the COMPOSITION -- who pays when
    one fires -- and a substitute is the honest way to ask that.
    """
    import swing.trades.latched_origin as lo

    conn, cfg, candidate_id = build_world(tmp_path, "r702")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()

    real = lo.authorize_accepted_order

    def boom(*a, **kw):
        raise lo.LatchProbeInvariantError(
            "the probe believes its own inputs are incoherent")

    lo.authorize_accepted_order = boom
    try:
        result = enter(conn, cfg, req())
    finally:
        lo.authorize_accepted_order = real

    assert written(conn, result.trade_id) == ("manual_off_pipeline", None, None)
    assert conn.execute(
        "SELECT COUNT(*) FROM fills WHERE trade_id = ?",
        (result.trade_id,)).fetchone()[0] == 1, (
        "the fill must land too: a blocked ENTRY and a blocked FILL are the "
        "same money-bearing failure")


def test_a_linked_fill_with_NO_CONFIG_records_honest_unset(tmp_path) -> None:
    """22A-R7-01 at the PERSISTED-ROW grain.

    `cfg=None` gated the ORDER-ID PARSE, so an order-bearing request from a
    caller who omitted the config took no reservation, never consulted the
    link table, and ran the ordinary current-candidate chain.  Where the
    ticker is `aplus` in the latest run that writes TODAY's candidate for a
    fill that demonstrably came from an accepted order -- silent-wrong, which
    is the direction the governing asymmetry forbids.

    PRE-FIX: `('pipeline_aplus', <today's candidate>, <a label>)`.
    POST-FIX: `('manual_off_pipeline', None, None)`.

    Its control is one function up: with NO link, `cfg=None` still runs the
    ordinary chain byte-for-byte, which is the LOCK's own subject.
    """
    from tests._latch_probe_world_22a import seed_run
    from tests.trades._cohort_provenance_fixtures import seed_pipeline_run

    conn, cfg, candidate_id = build_world(tmp_path, "r701")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    # TODAY's run carries the ticker as `aplus`, so the ordinary chain has a
    # DIFFERENT answer to write. Without it both paths land
    # `manual_off_pipeline` and the case cannot discriminate.
    seed_run(conn, 902, FILL_SESSION)
    today = conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
        "pivot, initial_stop, rs_method) VALUES (902, ?, 'aplus', 19.0, "
        "19.5, 15.0, 'universe')", (TICKER,)).lastrowid
    seed_pipeline_run(
        conn, evaluation_run_id=902,
        data_asof_date=date(2026, 7, 24).isoformat(),
        action_session_date=FILL_SESSION.isoformat(),
        started_ts="2026-07-24T17:30:00", finished_ts="2026-07-24T17:44:00")
    conn.commit()

    result = record_entry(conn, req(entry_path=EntryPath.HYP_RECS_BUTTON),
                          soft_warn=SOFT, hard_cap=HARD, force=False)
    origin, cand, label = written(conn, result.trade_id)
    assert (origin, cand, label) == ("manual_off_pipeline", None, None), (
        f"the ordinary chain wrote candidate {today} for a fill whose own "
        f"envelope names an accepted order")


# ===========================================================================
# 22A-R8-01 -- AN ORDER IDENTITY THE TWO DOMAINS READ DIFFERENTLY IS REFUSED
# ===========================================================================
def test_python_and_sqlite_really_do_read_the_envelope_differently() -> None:
    """THE PREMISE, MEASURED, before anything is built on it.

    A finding is a lead until the code is the evidence, and this one is a
    claim about two ENGINES rather than about this repo.  Both halves are
    executed here so the guard below cannot rest on an inherited assertion --
    and so it fails loudly on the day either engine changes, rather than
    quietly guarding nothing.
    """
    import json as _json
    import sqlite3 as _sqlite3

    padded = '{"schwab_order_id": "  1002937461  "}'
    assert _json.loads(padded)["schwab_order_id"] == "  1002937461  "
    conn = _sqlite3.connect(":memory:")
    assert conn.execute(
        "SELECT json_extract(?, '$.schwab_order_id')", (padded,)
    ).fetchone()[0] == "  1002937461  "
    # ...and the SERVICE strips, which is where the two part company.
    from swing.trades.latched_origin import broker_order_id_from_envelope
    assert broker_order_id_from_envelope(padded) == "1002937461"

    duplicated = '{"schwab_order_id": "A", "schwab_order_id": "B"}'
    assert _json.loads(duplicated)["schwab_order_id"] == "B", "Python keeps LAST"
    assert conn.execute(
        "SELECT json_extract(?, '$.schwab_order_id')", (duplicated,)
    ).fetchone()[0] == "A", "SQLite keeps FIRST"


def test_a_padded_order_id_on_a_LINKED_fill_is_refused(tmp_path) -> None:
    """PRE-FIX the service stripped it, matched the link, and admitted -- while
    every SQL scan over the SAME envelope read the PADDED string and could
    therefore miss a real prior consumption.  POST-FIX the ladder refuses
    `envelope_not_canonical`, RECOGNISED, so the row lands honest-unset rather
    than falling through to TODAY's candidate.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "r801")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    padded = json.dumps({"schwab_order_id": "  " + BROKER_ORDER_ID + "  ",
                         "schwab_instrument_symbol": TICKER})
    result = enter(conn, cfg, req(schwab_source_value_json=padded))
    assert written(conn, result.trade_id) == ("manual_off_pipeline", None, None)

    from swing.trades.latched_origin import resolve_latched_provenance
    verdict = resolve_latched_provenance(
        conn, cfg, req(schwab_source_value_json=padded))
    assert verdict.decline_reason == "envelope_not_canonical"
    assert verdict.recognised_but_underivable is True


def test_a_canonical_order_id_still_admits(tmp_path) -> None:
    """THE CONTROL, one dimension changed: no padding, and the ladder admits.

    Without it a guard that refused every envelope would pass the case above.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "r801ctl")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    result = enter(conn, cfg, req())
    origin, cand, _label = written(conn, result.trade_id)
    assert (origin, cand) == ("pipeline_aplus", candidate_id)


def test_a_DUPLICATE_order_id_key_on_a_LINKED_fill_is_refused(tmp_path) -> None:
    """The other half of the split, and it needs no whitespace.

    Python keeps the LAST duplicate key and SQLite keeps the FIRST, so an
    envelope naming two orders is read as two different mandates by the two
    domains.  The raw JSON is built by hand because `json.dumps` cannot emit a
    duplicate key -- which is exactly why the shape survives unnoticed: no
    emitter in this repo produces it, and the guard is about what a BLOB may
    contain rather than about what we write.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "r801dup")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    duplicated = (
        '{"schwab_instrument_symbol": "' + TICKER + '", '
        '"schwab_order_id": "not-a-real-order", '
        '"schwab_order_id": "' + BROKER_ORDER_ID + '"}')
    from swing.trades.latched_origin import resolve_latched_provenance
    verdict = resolve_latched_provenance(
        conn, cfg, req(schwab_source_value_json=duplicated))
    assert verdict.decline_reason == "envelope_not_canonical"
    assert verdict.recognised_but_underivable is True


# ===========================================================================
# 22A-R8-03 -- A NON-FINITE FROZEN PRICE CANNOT BLOCK A MONEY-BEARING ENTRY
# ===========================================================================
def test_an_infinite_frozen_pivot_writes_the_entry(tmp_path) -> None:
    """`inf > 0` is TRUE, so the link CHECK and the model validator BOTH admit
    a `+inf` frozen pivot -- and `zone_cap_for_pivot` then raises `ValueError`
    on a non-finite input BY DESIGN.

    PRE-FIX that `ValueError` escaped the ladder and rolled the trade AND the
    fill back: cohort bookkeeping charging a money-bearing entry, on a value
    the positivity guard was never going to catch.  POST-FIX the guard refuses
    `frozen_value_unavailable` before any arithmetic, and the resolver's
    containment is broad enough that a future arithmetic failure cannot do it
    either.

    The fire is moved through the barrier helper, because a `candidates` row
    is structurally immutable and the mint COPIES its values into the link.
    """
    from tests._candidates_barrier_helper import candidates_barrier_lifted

    conn, cfg, candidate_id = build_world(tmp_path, "r803")
    with candidates_barrier_lifted(conn):
        conn.execute("UPDATE candidates SET pivot = 9e999 WHERE id = ?",
                     (candidate_id,))
    conn.commit()
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    frozen = conn.execute(
        "SELECT frozen_pivot FROM latch_order_mandate_links").fetchone()[0]
    assert frozen == float("inf"), (
        "the mint must FREEZE the infinite pivot, or the case is about a "
        "different value than the one it names")

    result = enter(conn, cfg, req())
    assert written(conn, result.trade_id) == ("manual_off_pipeline", None, None)
    assert conn.execute(
        "SELECT COUNT(*) FROM fills WHERE trade_id = ?",
        (result.trade_id,)).fetchone()[0] == 1


def test_an_unexpected_authorization_exception_writes_the_entry(
        tmp_path) -> None:
    """AND THE CONTAINMENT IS BROAD, which is the durable half of R8-03.

    R7-02 contained `LatchProbeInvariantError` and the very next round found a
    DIFFERENT escape.  Enumerating the raisable types is the
    hand-maintained-roster failure; this case substitutes an exception type the
    arc has never seen, so it fails against any narrowed containment.
    """
    import swing.trades.latched_origin as lo

    conn, cfg, candidate_id = build_world(tmp_path, "r803b")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    real = lo.authorize_accepted_order

    def boom(*a, **kw):
        raise ZeroDivisionError("a type this arc has never raised")

    lo.authorize_accepted_order = boom
    try:
        result = enter(conn, cfg, req())
    finally:
        lo.authorize_accepted_order = real
    assert written(conn, result.trade_id) == ("manual_off_pipeline", None, None)
    assert conn.execute(
        "SELECT COUNT(*) FROM fills WHERE trade_id = ?",
        (result.trade_id,)).fetchone()[0] == 1


# ===========================================================================
# 22A-R11-02 -- THE IDENTITY WRITE MAY NEVER COST A MONEY-BEARING FILL
#
# THE CLASS, NAMED: **THE GUARD MOVED AND ITS TEST DID NOT.**  The containment
# case directly above substitutes `authorize_accepted_order`, which is the
# boundary the RESOLVER owns.  The persist-canonical reshape opened a SECOND
# failure boundary, in `insert_fill_with_event`, that runs AFTER authorization
# and AFTER the fill INSERT -- so no amount of patching authorization can reach
# it, and the existing case passed while the new hole was live.  A boundary
# asserted at ONE call site is not a boundary (22A-R9-04's own sentence, and
# this is its third instance).
# ===========================================================================
def test_an_identity_write_failure_does_not_roll_back_the_entry(
        tmp_path, monkeypatch) -> None:
    """MEASURED PRE-FIX: `fills` = 0 and `trades` = 0.

    `record_identity` raising a `sqlite3.OperationalError` escaped
    `insert_fill_with_event`, escaped `record_entry`, and the transaction
    rolled the trade AND the fill back -- cohort bookkeeping blocking a
    money-bearing fill, which `0036:26-38` and this arc's own headline rule
    forbid outright.

    POST-FIX the fill lands AND the ladder's verdict is UNCHANGED, which is
    the discriminating half.  The ladder itself did nothing wrong here -- rung
    6's population pass had no other envelope-bearing entry fill to read in
    this world, so it never touched the patched writer -- and an implementation
    that degraded the cohort keys because an AUDIT row failed would be the
    same inversion in the opposite direction.  What is missing is exactly one
    thing: the audit row.  The next case proves that its absence fails CLOSED.
    """
    import swing.data.repos.fill_envelope_identity as fei

    conn, cfg, candidate_id = build_world(tmp_path, "r1102")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()

    def boom(*a, **kw):
        raise sqlite3.OperationalError("simulated identity write failure")

    monkeypatch.setattr(fei, "record_identity", boom)
    result = enter(conn, cfg, req())
    origin, cand, label = written(conn, result.trade_id)
    assert (origin, cand) == ("pipeline_aplus", candidate_id)
    assert label is not None
    assert conn.execute(
        "SELECT COUNT(*) FROM fills WHERE trade_id = ?",
        (result.trade_id,)).fetchone()[0] == 1
    assert conn.execute(
        "SELECT COUNT(*) FROM fill_envelope_identity").fetchone()[0] == 0, (
        "the write FAILED in this case; a row here would mean the test is "
        "measuring a path where nothing was broken")


def test_a_prior_consumer_whose_reading_was_never_written_still_blocks(
        tmp_path) -> None:
    """THE CONTAINMENT ABOVE IS ONLY SAFE BECAUSE OF THIS.

    Swallowing the identity write would be a fail-OPEN if the scans could not
    see a fill whose reading is absent -- an unread population reads as EMPTY,
    which is the widest wrong acceptance available at rung 6.  What closes it
    is that rung 6 runs `ensure_entry_fill_identities` FIRST, inside the same
    reservation, so a fill the writer never got to is re-read before either
    scan looks at it.

    The prior consumer is on ANOTHER TICKER because rung 6 is the only
    ORDER-scoped rung: probed on the subject's own ticker, `_match_fill`'s
    clearing and the one-open-position rule refuse first and rung 6 never
    decides (22A-R9-02's own measurement).
    """
    from tests._latch_probe_world_22a import seed_trade

    conn, cfg, candidate_id = build_world(tmp_path, "r1102b")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    seed_trade(conn, trade_id=777, entry_date=date(2026, 7, 22), price=17.0)
    conn.execute("UPDATE trades SET state = 'closed' WHERE id = 777")
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status, fill_origin, schwab_source_value_json) VALUES "
        "(777, '2026-07-22T14:30:00', 'entry', 2, 17.0, 'unreconciled', "
        "'schwab_auto', ?)", (envelope(),))
    conn.commit()
    assert conn.execute(
        "SELECT COUNT(*) FROM fill_envelope_identity").fetchone()[0] == 0, (
        "the prior consumer must start with NO stored reading, or this case "
        "is not about the repair")

    result = enter(conn, cfg, req())
    assert written(conn, result.trade_id) == ("manual_off_pipeline", None, None)


# ===========================================================================
# 22A-R11-01 -- AN UNREADABLE PRIOR CONSUMER IS IGNORANCE, NOT ABSENCE
#
# THIS CASE PREVIOUSLY ASSERTED THE OPPOSITE AND PASSED.  It was written for
# 22A-R8-04 (the service's own JSON scans taking the `CASE` form); the reshape
# then DELETED every service-side JSON scan, so the clause it guarded ceased to
# exist while the admission it asserted became live.  The suite ENSHRINED a
# wrong acceptance -- a test that survives the mechanism it was written for is
# no longer evidence about anything.
# ===========================================================================
def test_a_malformed_envelope_on_another_trade_REFUSES_the_subject(
        tmp_path) -> None:
    """PRE-FIX: `('pipeline_aplus', <the fire's candidate>)` -- MEASURED.

    The other trade's entry fill carries a document the authority cannot
    decode.  It may name this very broker order; nobody can say.  Stored as
    `canonical` with a NULL order id it was invisible to BOTH consumption
    scans -- `consuming_entry_fills` matches on an id it does not have, and
    `unreadable_entry_fills` matches on `refused`, which it was not -- so an
    unreadable prior consumer read as evidence of ABSENCE at the one rung that
    exists to stop a second consumer of one mandate.

    POST-FIX the stored reading is `refused`, the second scan sees it, and rung
    6 refuses `consumption_evidence_unavailable`.  The entry still LANDS --
    cohort bookkeeping never blocks a money-bearing fill -- with honest-unset
    keys, and that is asserted too.
    """
    from tests._latch_probe_world_22a import seed_trade

    conn, cfg, candidate_id = build_world(tmp_path, "r804")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    # The other trade must be CLOSED: one open position per ticker is a
    # pre-existing gate, and an open sibling would refuse the entry before the
    # scans ever ran -- a test blocked for a reason unrelated to its clause.
    seed_trade(conn, trade_id=777, entry_date=date(2026, 7, 22), price=17.0)
    conn.execute("UPDATE trades SET state = 'closed' WHERE id = 777")
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status, fill_origin, schwab_source_value_json) VALUES "
        "(777, '2026-07-22T14:30:00', 'entry', 2, 17.0, 'unreconciled', "
        "'schwab_auto', '{not json')")
    conn.commit()
    result = enter(conn, cfg, req())
    assert written(conn, result.trade_id) == ("manual_off_pipeline", None, None)
    assert conn.execute(
        "SELECT envelope_state FROM fill_envelope_identity fei "
        " JOIN fills f ON f.fill_id = fei.fill_id WHERE f.trade_id = 777"
    ).fetchone() == ("refused",)
    assert conn.execute(
        "SELECT COUNT(*) FROM fills WHERE trade_id = ?",
        (result.trade_id,)).fetchone()[0] == 1


def test_the_REVERSED_duplicate_key_order_is_also_refused(tmp_path) -> None:
    """22A-R9-01: the canonicality question is about the IDENTITY, not the hit.

    Gated on `orders` being non-empty, the guard asked "did the PYTHON-selected
    id find a link?"  So an envelope whose FIRST duplicate key is the LINKED
    one and whose LAST is not gave Python an unlinked id, an empty result, and
    a FALL-THROUGH to the ordinary chain -- while SQL would have read the
    linked mandate.  The wrong acceptance the guard exists to close, reachable
    by REVERSING the key order the first test happened to use.

    PRE-FIX: the ordinary chain ran (`pipeline_aplus` + today's candidate on a
    ticker that is `aplus` in the latest run).  POST-FIX: refused, recognised,
    honest-unset.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "r901")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    reversed_order = (
        '{"schwab_instrument_symbol": "' + TICKER + '", '
        '"schwab_order_id": "' + BROKER_ORDER_ID + '", '
        '"schwab_order_id": "not-a-real-order"}')
    from swing.trades.latched_origin import resolve_latched_provenance
    verdict = resolve_latched_provenance(
        conn, cfg, req(schwab_source_value_json=reversed_order))
    assert verdict.decline_reason == "envelope_not_canonical"
    assert verdict.recognised_but_underivable is True

    result = enter(conn, cfg, req(schwab_source_value_json=reversed_order))
    assert written(conn, result.trade_id) == ("manual_off_pipeline", None, None)


def test_a_NESTED_key_of_the_same_name_is_not_a_duplicate(tmp_path) -> None:
    """22A-R9-06: the count is the ROOT object's, not the document's.

    ``object_pairs_hook`` fires for every nested object, so a first version
    counted a legitimate top-level id plus an unrelated NESTED field of the
    same name as a duplicate -- a wrong REFUSAL manufactured by the guard.
    Both readers address ``$.schwab_order_id`` at the ROOT, so the root is the
    only place they can disagree.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "r906")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    nested = json.dumps({
        "schwab_order_id": BROKER_ORDER_ID,
        "schwab_instrument_symbol": TICKER,
        "raw": {"schwab_order_id": "an unrelated nested field"}})
    result = enter(conn, cfg, req(schwab_source_value_json=nested))
    origin, cand, _label = written(conn, result.trade_id)
    assert (origin, cand) == ("pipeline_aplus", candidate_id)


def test_a_RAISING_link_lookup_still_writes_the_entry(tmp_path) -> None:
    """22A-R9-04: a boundary asserted at ONE call site is not a boundary.

    The broad containment began at `authorize_accepted_order`, and
    `find_accepted_latch_order` ran BEFORE it -- so a read error or a
    hydration failure escaped the resolver and `record_entry` rolled the trade
    and the fill back.  The round-8 containment test substituted
    `authorize_accepted_order` and therefore could not see the hole.

    PRE-FIX: the exception propagated and nothing landed.
    POST-FIX: honest-unset, with the trade AND the fill written.
    """
    import swing.trades.latched_origin as lo

    conn, cfg, candidate_id = build_world(tmp_path, "r904")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    real = lo.find_accepted_latch_order

    def boom(*a, **kw):
        raise sqlite3.OperationalError("the link table is unreadable")

    lo.find_accepted_latch_order = boom
    try:
        result = enter(conn, cfg, req())
    finally:
        lo.find_accepted_latch_order = real
    assert written(conn, result.trade_id) == ("manual_off_pipeline", None, None)
    assert conn.execute(
        "SELECT COUNT(*) FROM fills WHERE trade_id = ?",
        (result.trade_id,)).fetchone()[0] == 1


# ===========================================================================
# SS-1 / SS-4 -- THE SELF-SWEEP'S RESIDUALS OF R8-01 AND R9-01
#
# NOT A COUNTED ROUND.  These come from the dedicated self-sweep the
# gate-holder ruled after round 9's composition (four of seven findings were
# residuals of round 8's own fixes).  Every one below was VERIFIED BY
# EXECUTION before it was written.
# ===========================================================================
def _seed_todays_aplus_run(conn) -> int:
    """A LATER complete run carrying the ticker as ``aplus``.

    Without it the ordinary chain and the honest-unset path both land
    ``manual_off_pipeline`` and no assertion below can discriminate.
    """
    from tests._latch_probe_world_22a import seed_run
    from tests.trades._cohort_provenance_fixtures import seed_pipeline_run

    seed_run(conn, 902, FILL_SESSION)
    today = conn.execute(
        "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
        "pivot, initial_stop, rs_method) VALUES (902, ?, 'aplus', 19.0, "
        "19.5, 15.0, 'universe')", (TICKER,)).lastrowid
    seed_pipeline_run(
        conn, evaluation_run_id=902,
        data_asof_date=date(2026, 7, 24).isoformat(),
        action_session_date=FILL_SESSION.isoformat(),
        started_ts="2026-07-24T17:30:00", finished_ts="2026-07-24T17:44:00")
    conn.commit()
    return int(today)


def _slug(label: str) -> str:
    return "".join(c for c in label.lower() if c.isalnum())[:12]


_SS1_SHAPES = {
    "the LAST duplicate is JSON null": '"schwab_order_id": null',
    "the LAST duplicate is a NUMBER": '"schwab_order_id": 42',
    "the LAST duplicate is the EMPTY string": '"schwab_order_id": ""',
}


@pytest.mark.parametrize("label", sorted(_SS1_SHAPES))
def test_an_envelope_python_reads_as_ABSENT_but_sql_reads_as_LINKED(
        tmp_path, label) -> None:
    """SS-1: the canonicality guard was UNREACHABLE for the shapes that matter.

    R8-01 refused an identity the two domains read differently and R9-01 moved
    that question ABOVE the link lookup.  Both left it BELOW the order-id
    READ -- so an envelope whose LAST duplicate key makes Python read ABSENCE
    never reached the guard at all: `record_entry`'s reservation trigger and
    the resolver both asked "did PYTHON find an id?", got None, and ran the
    ordinary chain, while SQL reads the FIRST key and would have bound a real
    mandate.

    MEASURED, all three shapes: python=None, sqlite='<the linked order>'.

    PRE-FIX the persisted row is `('pipeline_aplus', <today's candidate>)` --
    the silent misattribution this arc exists to prevent, reachable through
    the production form with a tampered hidden envelope.
    POST-FIX it is `('manual_off_pipeline', None, None)`.
    """
    from swing.trades.latched_origin import (
        broker_order_id_from_envelope,
        resolve_latched_provenance,
    )

    conn, cfg, candidate_id = build_world(tmp_path, "ss1" + _slug(label))
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    today = _seed_todays_aplus_run(conn)

    raw = ('{"schwab_instrument_symbol": "' + TICKER + '", '
           '"schwab_order_id": "' + BROKER_ORDER_ID + '", '
           + _SS1_SHAPES[label] + '}')
    # THE PREMISE, MEASURED HERE, not inherited: the two domains really do
    # disagree, and they disagree in the direction that matters.
    assert broker_order_id_from_envelope(raw) is None
    assert conn.execute(
        "SELECT json_extract(?, '$.schwab_order_id')", (raw,)
    ).fetchone()[0] == BROKER_ORDER_ID

    verdict = resolve_latched_provenance(
        conn, cfg, req(schwab_source_value_json=raw))
    assert verdict.decline_reason == "envelope_not_canonical"
    assert verdict.recognised_but_underivable is True

    result = enter(conn, cfg, req(schwab_source_value_json=raw,
                                  entry_path=EntryPath.HYP_RECS_BUTTON))
    assert written(conn, result.trade_id) == (
        "manual_off_pipeline", None, None), (
        f"the ordinary chain wrote candidate {today} for a fill SQL reads as "
        f"naming accepted order {BROKER_ORDER_ID}")



def test_a_PADDED_instrument_symbol_is_refused_at_the_ladder(tmp_path) -> None:
    """SS-4: R8-01's class, second instance -- the SYMBOL.

    R8-01 stated the class once ("refuse an identity the two domains would
    read differently") and fixed the ORDER-ID instance.  The citation trigger
    binds `$.authorization.guard_envelope_symbol.input` to
    `json_extract(f.schwab_source_value_json, '$.schwab_instrument_symbol')`
    -- SQL, unstripped -- while the service reads the SAME key through
    `instrument_symbol_from_envelope`, which STRIPS.  MEASURED: the service
    admits `latch_ladder` and the trigger then ABORTS the whole correction
    with the generic citation-graph message.

    PRE-FIX: the entry ADMITS (`pipeline_aplus` + the fire's candidate) and a
    later correction dies with an illegible structural refusal.
    POST-FIX: refused HERE, recognised, with a reason that names the cause.
    """
    from swing.trades.latched_origin import resolve_latched_provenance

    conn, cfg, candidate_id = build_world(tmp_path, "ss4")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    padded_symbol = json.dumps({
        "schwab_order_id": BROKER_ORDER_ID,
        "schwab_instrument_symbol": "  " + TICKER + "  "})
    verdict = resolve_latched_provenance(
        conn, cfg, req(schwab_source_value_json=padded_symbol))
    assert verdict.decline_reason == "envelope_not_canonical"
    assert verdict.recognised_but_underivable is True
    result = enter(conn, cfg, req(schwab_source_value_json=padded_symbol))
    assert written(conn, result.trade_id) == ("manual_off_pipeline", None, None)


def test_a_DUPLICATE_instrument_symbol_key_is_refused(tmp_path) -> None:
    """SS-4's other half, and it needs no whitespace."""
    from swing.trades.latched_origin import resolve_latched_provenance

    conn, cfg, candidate_id = build_world(tmp_path, "ss4b")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    duplicated = ('{"schwab_order_id": "' + BROKER_ORDER_ID + '", '
                  '"schwab_instrument_symbol": "ZZZZ", '
                  '"schwab_instrument_symbol": "' + TICKER + '"}')
    verdict = resolve_latched_provenance(
        conn, cfg, req(schwab_source_value_json=duplicated))
    assert verdict.decline_reason == "envelope_not_canonical"
    assert verdict.recognised_but_underivable is True


def test_a_clean_envelope_on_BOTH_keys_still_admits(tmp_path) -> None:
    """THE CONTROL for SS-1 and SS-4 together, one dimension changed.

    Without it a guard that refused every envelope would pass every case
    above.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "ssctl")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    result = enter(conn, cfg, req())
    origin, cand, _label = written(conn, result.trade_id)
    assert (origin, cand) == ("pipeline_aplus", candidate_id)


def test_a_deeply_nested_envelope_still_writes_the_ENTRY(tmp_path) -> None:
    """SS-2 at the grain where it costs money.

    The three envelope readers ran OUTSIDE the resolver's containment -- one
    of them before `record_entry` opens a transaction at all -- and each
    caught an ENUMERATED pair of exception types.  `json.loads` raises
    `RecursionError`, a `RuntimeError`, on a deeply nested document, so the
    escape reached `record_entry` and NEITHER THE TRADE NOR THE FILL LANDED.

    That is 22A-R8-03's own ruling ("enumerating the raisable types is the
    hand-maintained-roster failure") left unapplied at the sites its own fix
    did not reach.

    PRE-FIX: `RecursionError` propagates out of `record_entry`.
    POST-FIX: honest-unset, with the trade AND the fill written.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "ss2")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    deep = ('{"schwab_order_id":' + '{"a":' * 20000 + '1' + '}' * 20000 + '}')
    with pytest.raises(RecursionError):
        json.loads(deep)                        # the PREMISE, measured here
    result = enter(conn, cfg, req(schwab_source_value_json=deep))
    assert written(conn, result.trade_id) == ("manual_off_pipeline", None, None)
    assert conn.execute(
        "SELECT COUNT(*) FROM fills WHERE trade_id = ?",
        (result.trade_id,)).fetchone()[0] == 1, (
        "a blocked ENTRY and a blocked FILL are the same money-bearing "
        "failure, and an unreadable audit blob must cost neither")


# ===========================================================================
# 22A-R9-02 -- PROVEN BY EXECUTION, NOT INHERITED AS AN INFERENCE
#
# The reviewer stated plainly that its reachability was an INFERENCE from
# composed branches.  It is not: the pair below differs in exactly ONE
# dimension and is built entirely through `record_entry`, with no raw UPDATE.
# ===========================================================================
def _consumer_on_another_ticker(conn, cfg, raw_envelope: str) -> int:
    """An entry on a DIFFERENT ticker whose envelope names OUR broker order.

    The other ticker is what makes rung 6 load-bearing: `_match_fill`'s
    clearing and the one-open-position-per-ticker rule are both PER-TICKER,
    so on the subject's own ticker they refuse first and rung 6 never
    decides.  Rung 6 is the only ORDER-scoped rung, which is its whole reason
    for existing.
    """
    result = enter(conn, cfg, req(ticker="ZZZZ",
                                  schwab_source_value_json=raw_envelope))
    conn.execute("UPDATE trades SET state = 'closed', current_size = 0 "
                 "WHERE id = ?", (result.trade_id,))
    conn.commit()
    return int(result.trade_id)


# --- THE THREE MEASURED DIVERGENCES, END TO END THROUGH `record_entry` ------
#
# PERSIST-CANONICAL (CHARC + RD, 2026-08-26).  Each of the three shapes that
# ended a ten-round review loop is now either CANONICALISED at the service or
# REFUSED at it, and each is exercised here through the production entry path
# with no raw UPDATE anywhere.  Two of the three reach the ladder through a
# prior consumer on ANOTHER ticker, which is what makes rung 6 -- the only
# ORDER-scoped rung -- the deciding one.
@pytest.mark.parametrize("label,order_value", [
    # DIVERGENCE 2: python str.strip removes these; sqlite trim() removes
    # ASCII space ONLY.  The predecessor built the whole whitespace class out
    # of the one character the engines agree about, so every test it wrote
    # passed.  All four are refused by the ONE authority now.
    ("ASCII space", "  " + BROKER_ORDER_ID + "  "),
    ("TAB", "\t" + BROKER_ORDER_ID + "\t"),
    ("NEWLINE", "\n" + BROKER_ORDER_ID + "\n"),
    ("NBSP", "\u00a0" + BROKER_ORDER_ID + "\u00a0"),
])
def test_rung6_refuses_when_a_prior_consumers_document_is_unreadable(
        tmp_path, label, order_value) -> None:
    """A prior consumer the AUTHORITY could not read is IGNORANCE, not absence.

    PRE-ARC the ladder ADMITTED this world: the padded envelope is persisted by
    the production entry path itself (which writes the fill even when the
    ladder refuses its cohort keys), and a raw-equality scan could not match
    it.  Round 9 fixed that with a two-domain UNION, and round 10 showed the
    union's "SQL arm" was SQL's value judged by PYTHON's rules.

    POST-RESHAPE there is one reading and it is a REFUSAL, so the honest answer
    is not "consumed by trade N" -- the authority declines to say which order
    that document names -- but "I cannot prove this order is unconsumed".  The
    mandate is refused either way; what changed is that the refusal no longer
    asserts an identity nothing derived.

    THE TAB / NEWLINE / NBSP ROWS ARE THE ONES THAT WOULD HAVE PASSED WRONGLY:
    `trim()` leaves them untouched, so the SQL twin saw an unpadded, canonical
    document and admitted a `last_word` downgrade for a latch-governed fill.
    """
    from swing.trades.latched_origin import (
        canonical_envelope_identity,
        resolve_latched_provenance,
    )

    conn, cfg, candidate_id = build_world(tmp_path, "r1102" + label[:3])
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    padded = json.dumps({"schwab_order_id": order_value,
                         "schwab_instrument_symbol": "ZZZZ"})
    # THE PREMISE, MEASURED IN THE ENGINE THAT DECIDES IT.  The predecessor's
    # version of this assertion fetched SQLite's json_extract INTO PYTHON and
    # compared it there -- SQL's value judged by Python's rules, on the very
    # arm meant to preserve SQL's semantics.  There is now exactly one engine
    # with an opinion, so the premise is asked of it.
    assert canonical_envelope_identity(padded).state == "refused"
    prior = _consumer_on_another_ticker(conn, cfg, padded)
    assert conn.execute(
        "SELECT envelope_state FROM fill_envelope_identity fei "
        " JOIN fills f ON f.fill_id = fei.fill_id WHERE f.trade_id = ?",
        (prior,)).fetchone()[0] == "refused", (
        "the production writer must have persisted the REFUSAL, or the scan "
        "below would be reading an unread population")

    verdict = resolve_latched_provenance(conn, cfg, req())
    assert verdict.admitted is False
    assert verdict.decline_reason == "consumption_evidence_unavailable"


def test_rung6_refuses_when_a_prior_consumers_order_id_is_NUMERIC(
        tmp_path) -> None:
    """DIVERGENCE 3, end to end: `1002937461` vs `'1002937461'`.

    MEASURED: Python says the two are unequal and SQL, against a TEXT-affinity
    column, says they are equal.  The round-9 union missed this consumer in
    BOTH arms -- its "SQL arm" had already been fetched into Python -- so the
    mandate was ADMITTED A SECOND TIME, which is a wrong ACCEPTANCE and the
    worst direction available at this rung.

    POST-RESHAPE the authority refuses a non-string identity, the refusal is
    persisted, and the scan reports that it cannot prove non-consumption.
    """
    from swing.trades.latched_origin import (
        canonical_envelope_identity,
        resolve_latched_provenance,
    )

    conn, cfg, candidate_id = build_world(tmp_path, "r1103num")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    numeric = ('{"schwab_order_id": %s, "schwab_instrument_symbol": "ZZZZ"}'
               % BROKER_ORDER_ID)
    assert canonical_envelope_identity(numeric).state == "refused"
    _consumer_on_another_ticker(conn, cfg, numeric)
    verdict = resolve_latched_provenance(conn, cfg, req())
    assert verdict.admitted is False
    assert verdict.decline_reason == "consumption_evidence_unavailable"


def test_rung6_sees_a_prior_consumer_carrying_a_NaN_document(tmp_path) -> None:
    """DIVERGENCE 1, end to end, AND IT IS THE CANONICALISED ONE.

    MEASURED: `json.loads` ACCEPTS a document containing `NaN`; SQLite's
    `json_valid` REJECTS it outright.  Under the old shape the trigger read
    NULL, saw no order, and would have admitted a `last_word` downgrade for a
    fill the service binds to a real mandate.

    POST-RESHAPE the authority READS it -- SQL never opens the document again,
    so nothing can disagree -- and the stored order id makes this prior fill a
    VISIBLE consumer.  The refusal is therefore the specific one,
    `mandate_already_consumed`, not the ignorance one: this is the branch of
    the ruling that says a divergence may be canonicalised rather than refused.
    """
    from swing.trades.latched_origin import (
        canonical_envelope_identity,
        resolve_latched_provenance,
    )

    conn, cfg, candidate_id = build_world(tmp_path, "r1101nan")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    nan_doc = ('{"schwab_order_id": "%s", "schwab_instrument_symbol": "ZZZZ",'
               ' "x": NaN}' % BROKER_ORDER_ID)
    assert json.loads(nan_doc)["x"] != json.loads(nan_doc)["x"], (
        "the premise: python accepts NaN and this document really carries one")
    identity = canonical_envelope_identity(nan_doc)
    assert (identity.state, identity.broker_order_id) == (
        "canonical", BROKER_ORDER_ID)
    prior = _consumer_on_another_ticker(conn, cfg, nan_doc)
    assert prior

    verdict = resolve_latched_provenance(conn, cfg, req())
    assert verdict.admitted is False
    assert verdict.decline_reason == "mandate_already_consumed"


def test_rung6_still_sees_a_prior_consumer_whose_envelope_is_clean(
        tmp_path) -> None:
    """THE CONTROL, one dimension changed: the SAME world with a CANONICAL
    prior envelope.  It refused before the fix and must refuse after, or the
    pair above would be satisfied by a guard that simply refuses everything.
    """
    from swing.trades.latched_origin import resolve_latched_provenance

    conn, cfg, candidate_id = build_world(tmp_path, "r902ctl")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    clean = json.dumps({"schwab_order_id": BROKER_ORDER_ID,
                        "schwab_instrument_symbol": "ZZZZ"})
    _consumer_on_another_ticker(conn, cfg, clean)
    verdict = resolve_latched_provenance(conn, cfg, req())
    assert verdict.decline_reason == "mandate_already_consumed"


def test_rung6_admits_when_no_other_fill_names_the_order(tmp_path) -> None:
    """THE OTHER CONTROL: no prior consumer at all, and the ladder ADMITS.

    Without it a scan that matched every envelope would pass both cases above.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "r902ctl2")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    unrelated = json.dumps({"schwab_order_id": "9999999999",
                            "schwab_instrument_symbol": "ZZZZ"})
    _consumer_on_another_ticker(conn, cfg, unrelated)
    result = enter(conn, cfg, req())
    origin, cand, _label = written(conn, result.trade_id)
    assert (origin, cand) == ("pipeline_aplus", candidate_id)


# ===========================================================================
# 22A-R3-13 -- RD RULED IT: THE DISCRIMINATOR IS THE INCONSISTENT EVIDENCE
# PAIR, NEVER THE ORIGIN.
#
# A `schwab_auto` fill carries an envelope BY CONSTRUCTION -- verified by READ
# at both writers: `entry_auto_fill`'s `kind='populated'` invariant requires
# `fill_origin='schwab_auto'` and its only such return builds the envelope in
# the same expression; the entry route stamps a trusted origin only inside the
# block that also assigns `resolved_schwab_source_value_json`.  So trusted
# origin + ABSENT envelope is a state NO PRODUCTION WRITER PRODUCES -- it is
# stripped, tampered or corrupted.
#
# RULED: the ENTRY PROCEEDS; the keys land HONEST-UNSET; a WARNING names the
# inconsistency, so the operator adjudicates a legible anomaly instead of
# inheriting a silent wrong label.  Writing TODAY's candidate for such a fill
# would be attribution from a timing coincidence -- gotcha #30's family, and
# the exact misattribution this arc exists to prevent.
# ===========================================================================
@pytest.mark.parametrize(
    "label,envelope_value",
    [("absent", None), ("empty", ""), ("blank", "   ")])
def test_a_trusted_origin_with_a_STRIPPED_envelope_lands_honest_unset(
        tmp_path, caplog, label, envelope_value) -> None:
    """CASE 1: the ticker IS in today's decision table, and it must NOT win it.

    An implementation keying the ordinary chain on DATE ALONE fails this: the
    fill session is a day this ticker is `aplus` in the latest complete run, so
    the ordinary chain has a real, current, wrong answer to write.

    PRE-FIX: `('pipeline_aplus', <today's candidate>, <a label>)`.
    POST-FIX: `('manual_off_pipeline', None, None)` plus a warning that names
    the inconsistency rather than a generic refusal.
    """
    import logging

    conn, cfg, candidate_id = build_world(tmp_path, "r313" + label)
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    today = _seed_todays_aplus_run(conn)

    with caplog.at_level(logging.WARNING):
        result = enter(conn, cfg, req(
            fill_origin="schwab_auto",
            schwab_source_value_json=envelope_value,
            entry_path=EntryPath.HYP_RECS_BUTTON))
    assert written(conn, result.trade_id) == (
        "manual_off_pipeline", None, None), (
        f"the ordinary chain wrote candidate {today} for a Schwab fill whose "
        f"envelope is gone -- attribution from a timing coincidence")
    assert conn.execute(
        "SELECT COUNT(*) FROM fills WHERE trade_id = ?",
        (result.trade_id,)).fetchone()[0] == 1, "the ENTRY must still proceed"
    named = [r.getMessage() for r in caplog.records
             if "schwab_auto" in r.getMessage()
             and "envelope" in r.getMessage()]
    assert named, (
        "the warning must NAME the inconsistency -- a generic refusal leaves "
        "the operator inheriting an anomaly he cannot see. Got: "
        + repr([r.getMessage() for r in caplog.records]))


def test_an_envelope_BEARING_schwab_fill_with_no_latch_runs_the_ordinary_chain(
        tmp_path) -> None:
    """CASE 2 -- THE OVER-SUPPRESSION TWIN, and it is why the rule is the PAIR.

    An implementation suppressing on ORIGIN ALONE fails this: every Schwab
    fill that never had a latch would land honest-unset, which would erase
    correct pipeline provenance across the whole journal.

    The envelope is present and well-formed and simply names an order NO LINK
    knows, which is the ordinary post-Schwab-integration state.

    PRE-FIX and POST-FIX are the SAME here on purpose -- the case exists to
    fail an over-broad fix, and its value is that it distinguishes two
    implementations that agree on case 1.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "r313twin")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    today = _seed_todays_aplus_run(conn)
    unlinked = json.dumps({"schwab_order_id": "9999999999",
                           "schwab_instrument_symbol": TICKER})
    result = enter(conn, cfg, req(
        fill_origin="schwab_auto", schwab_source_value_json=unlinked,
        entry_path=EntryPath.HYP_RECS_BUTTON))
    origin, cand, _label = written(conn, result.trade_id)
    assert (origin, cand) == ("pipeline_aplus", today), (
        "an envelope-bearing Schwab fill with no latch must run the ordinary "
        "chain exactly as it does on main")


def test_an_operator_typed_fill_with_no_envelope_is_untouched(
        tmp_path) -> None:
    """THE THIRD CONTROL: the ordinary, overwhelming case.

    Every pre-22-A fill and every hand-typed entry is origin
    `operator_typed` with no envelope, and the pair is CONSISTENT there.  A
    rule keyed on envelope-absence alone would honest-unset the entire
    journal.
    """
    conn, cfg, candidate_id = build_world(tmp_path, "r313ctl")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    today = _seed_todays_aplus_run(conn)
    result = enter(conn, cfg, req(
        fill_origin="operator_typed", schwab_source_value_json=None,
        entry_path=EntryPath.HYP_RECS_BUTTON))
    origin, cand, _label = written(conn, result.trade_id)
    assert (origin, cand) == ("pipeline_aplus", today)


# ===========================================================================
# 22A-R11-03 -- A STALE READING ADMITTED A SECOND CONSUMER OF ONE MANDATE
#
# PROVEN BY EXECUTION rather than carried as the reviewer's own inference: the
# reading below is written by the PRODUCTION writer, and only the CODE is
# advanced -- which is exactly what bumping `ENVELOPE_CANONICALIZER_VERSION`
# means.  Nothing about the data is forged.
# ===========================================================================
def test_a_reading_from_an_older_grammar_cannot_admit_a_second_consumer(
        tmp_path, monkeypatch) -> None:
    """MEASURED, both arms, on the SAME world one dimension apart:

    * stale reading `(canonical, None)` under version `2026-01-01.0`
      -> PRE-FIX `('pipeline_aplus', <the fire>, 'A+ baseline (aplus)')`
    * current reading `(canonical, '1002937461')`
      -> `('manual_off_pipeline', None, None)` (`mandate_already_consumed`)

    So the stale row admitted a SECOND consumer of a mandate trade 777's entry
    fill already consumes.  POST-FIX the population pass re-reads it, the
    disagreement RAISES, the resolver's broad containment refuses
    `aliveness_unverifiable`, and the entry lands honest-unset with its fill.
    """
    import swing.trades.latched_origin as lo
    from swing.data.repos.fill_envelope_identity import record_identity
    from tests._latch_probe_world_22a import seed_trade

    conn, cfg, candidate_id = build_world(tmp_path, "r1103")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    seed_trade(conn, trade_id=777, entry_date=date(2026, 7, 22), price=17.0)
    conn.execute("UPDATE trades SET state = 'closed' WHERE id = 777")
    conn.execute(
        "INSERT INTO fills (trade_id, fill_datetime, action, quantity, price, "
        "reconciliation_status, fill_origin, schwab_source_value_json) VALUES "
        "(777, '2026-07-22T14:30:00', 'entry', 2, 17.0, 'unreconciled', "
        "'schwab_auto', ?)", (envelope(),))
    fid = conn.execute(
        "SELECT fill_id FROM fills WHERE trade_id = 777").fetchone()[0]

    # THE OLD GRAMMAR, THROUGH THE PRODUCTION WRITER.
    monkeypatch.setattr(
        lo, "canonical_envelope_identity",
        lambda raw: lo.EnvelopeIdentity(lo.ENVELOPE_CANONICAL, None, None))
    monkeypatch.setattr(lo, "ENVELOPE_CANONICALIZER_VERSION", "2026-01-01.0")
    record_identity(conn, fill_id=int(fid), envelope_raw=envelope())
    conn.commit()
    monkeypatch.undo()                       # THE CODE IS NOW BUMPED
    assert conn.execute(
        "SELECT envelope_state, broker_order_id, canonicalizer_version "
        "  FROM fill_envelope_identity WHERE fill_id = ?",
        (fid,)).fetchone() == ("canonical", None, "2026-01-01.0")

    result = enter(conn, cfg, req())
    assert written(conn, result.trade_id) == ("manual_off_pipeline", None, None)
    assert conn.execute(
        "SELECT COUNT(*) FROM fills WHERE trade_id = ?",
        (result.trade_id,)).fetchone()[0] == 1


# ===========================================================================
# SELF-SWEEP SS-15 -- THE POPULATION IS ESTABLISHED BEFORE EVERY SCAN
#
# Every consumption scan reads STORED readings, so a population the authority
# has not read is a population the scan silently treats as EMPTY -- the widest
# wrong acceptance available at rung 6, and the property the identity write's
# containment (22A-R11-02) leans on to be safe.  It is pinned at RUNTIME rather
# than asserted in a comment, because a comment promising an ordering is the
# #31 class.
# ===========================================================================
def test_the_reading_population_is_established_before_any_scan(
        tmp_path, monkeypatch) -> None:
    """Rung 8's scan is covered by the same guarantee without a second world:
    it sits BELOW rung 6 in one function's linear flow, and every exit between
    them is a refusal that skips the scan as well."""
    import swing.data.repos.fill_envelope_identity as fei

    seq: list[str] = []

    def _spy(name, real):
        def wrapper(*a, **kw):
            seq.append(name)
            return real(*a, **kw)
        return wrapper

    for name in ("ensure_entry_fill_identities", "consuming_entry_fills",
                 "unreadable_entry_fills"):
        monkeypatch.setattr(fei, name, _spy(name, getattr(fei, name)))

    conn, cfg, candidate_id = build_world(tmp_path, "ss15")
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    enter(conn, cfg, req())

    assert seq, "no scan ran; this world does not reach rung 6"
    assert seq[0] == "ensure_entry_fill_identities", (
        f"a scan ran before the population was established: {seq}")
    assert "ensure_entry_fill_identities" not in seq[1:], (
        f"the population pass ran more than once inside one ladder: {seq}")


# ===========================================================================
# THE ENTRY-OR-LABEL SEAM, ENFORCED RATHER THAN DECLARED (RD, ruled twice;
# violated FOUR times in this arc -- `NotSessionError`, 37c, `R11-02`'s
# uncontained `record_identity`, and the entry route's `schwab_order_id` rung)
#
# **THAT IS NOT FOUR SLIPS; IT IS A DEFAULT THAT MUST BE INVERTED AT THE SEAM.**
# Every guard written to protect the cohort keys defaulted to blocking the
# ENTRY, and each was found individually, by a different reviewer, on a
# different round.  A standing requirement that each guard STATE which of ENTRY
# or LABEL it refuses is a prose rule, and a prose rule is exactly what the
# four instances each satisfied in spirit and broke in code.
#
# So the seam carries a PROPERTY instead: **for EVERY member of
# `DECLINE_REASONS`, in BOTH recognition states, the trade row is still
# WRITTEN.**  A fifth guard added anywhere in the resolution -- whatever it is
# called, whatever it refuses over -- fails here the moment it prevents the
# row, without anyone having to notice it was a cohort guard.
# ===========================================================================
def _every_refusal_still_writes(tmp_path, monkeypatch, *, recognised: bool,
                               pe_anchored: bool):
    """``pe_anchored`` ARMS THE RELOCATED PE-ANCHOR GUARD, and without it this
    property could not have caught the instance it is written for.

    37c's guard fires only when a `pattern_evaluation_id` anchor is present
    AND the server-derived origin is `manual_off_pipeline`; a bare request
    never meets it, so a seam property run only on bare requests would have
    gone green against the very code RD ruled against.  Both request shapes
    run -- the BOTH-MODES requirement applied to the arming condition rather
    than to a config flag.
    """
    from swing.trades import latched_origin as lo

    name = f"seam{int(recognised)}{int(pe_anchored)}"
    if pe_anchored:
        conn, cfg, candidate_id = _pe_anchored_world(
            tmp_path, name, closes=BASE_CLOSES)
    else:
        conn, cfg, candidate_id = build_world(tmp_path, name)
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()
    if pe_anchored:
        from swing.trades.origin import derive_trade_origin
        assert derive_trade_origin(
            conn, TICKER, EntryPath.MANUAL_WEB_FORM) == "manual_off_pipeline", (
            "the PE-anchor guard's third condition is unmet, so this arming "
            "proves nothing")

    written_rows: dict[str, tuple] = {}
    for reason in sorted(lo.DECLINE_REASONS):
        def _refuse(_conn, _cfg, _req, reason=reason):
            return lo.LatchedProvenance(
                admitted=False, recognised_but_underivable=recognised,
                decline_reason=reason)

        monkeypatch.setattr(lo, "resolve_latched_provenance", _refuse)
        monkeypatch.setattr(
            "swing.trades.entry.resolve_latched_provenance", _refuse,
            raising=False)
        result = enter(conn, cfg, req(
            hypothesis_label="a submitted label",
            **({"pattern_evaluation_id": 7} if pe_anchored else {})))
        assert result.trade_id is not None, reason
        written_rows[reason] = written(conn, result.trade_id)
        # ONE OPEN POSITION PER TICKER is a PRE-EXISTING production gate
        # (`ux_trades_one_open_per_ticker`, migration 0014) and has nothing to
        # do with cohort bookkeeping, so the row is removed between reasons
        # rather than the world rebuilt thirty-six times.  Raw, because the
        # row's existence is what was just measured and its disposal is not
        # part of the property.
        conn.execute("DELETE FROM fills WHERE trade_id = ?",
                     (result.trade_id,))
        conn.execute("DELETE FROM trades WHERE id = ?", (result.trade_id,))
        conn.commit()
    conn.close()
    return written_rows


@pytest.mark.parametrize("pe_anchored", [False, True],
                         ids=["bare", "pe-anchored"])
def test_EVERY_refusal_reason_still_writes_the_entry_recognised(
        tmp_path, monkeypatch, pe_anchored) -> None:
    """RECOGNISED-AND-REFUSED: the row lands HONEST-UNSET for every reason.

    Honest-unset is `('manual_off_pipeline', None, None)` -- all three keys
    move together, because a row carrying origin and candidate but a NULL
    label is incoherent AND permanently uncorrectable (Demand C's
    `_gate_on_unset_state` refuses a trade carrying any of the three).
    """
    rows = _every_refusal_still_writes(
        tmp_path, monkeypatch, recognised=True, pe_anchored=pe_anchored)
    assert rows, "no reason was exercised, so this row measures nothing"
    for reason, row in rows.items():
        assert row == ("manual_off_pipeline", None, None), (
            f"refusal {reason!r} did not land honest-unset: {row}")


def test_EVERY_refusal_reason_still_writes_the_entry_fall_through(
        tmp_path, monkeypatch) -> None:
    """NOT-RECOGNISED: the ordinary chain runs and the row is still written.

    The two recognition states are exercised separately because they take
    DIFFERENT branches -- suppression versus fall-through -- and a guard added
    to either one would be invisible to a test that only ran the other.

    **THE PE-ANCHORED SHAPE IS DELIBERATELY NOT RUN HERE, AND ITS ABSENCE IS A
    RULING RATHER THAN A GAP** -- see the declared exception below.  A
    parametrization that ran it would assert the opposite of what RD ruled.
    """
    rows = _every_refusal_still_writes(
        tmp_path, monkeypatch, recognised=False, pe_anchored=False)
    assert rows, "no reason was exercised, so this row measures nothing"
    for reason, row in rows.items():
        assert row[0] is not None, (
            f"refusal {reason!r} blocked the entry; cohort bookkeeping never "
            f"blocks a money-bearing entry")


def test_THE_DECLARED_EXCEPTION_the_pe_anchor_guard_still_bites_on_the_ordinary_path(
        tmp_path, monkeypatch) -> None:
    """THE ONE COMBINATION THE SEAM PROPERTY DOES NOT ASSERT, with its reason.

    On the ORDINARY (not-recognised) path a `pattern_evaluation_id` anchor
    whose server-derived origin is `manual_off_pipeline` STILL refuses, and
    **RD ruled that deliberately**: the guard is a PRE-EXISTING production
    rejection RELOCATED from the route (`22A-R9-03`), not a cohort-provenance
    guard, and deleting it would remove a live production rejection rather
    than invert a default.  Case 37c is the same property from the other side.

    It is pinned in the DIRECTION THAT FAILS IF THE EXCEPTION EVER STOPS
    HOLDING, so the seam property's scope cannot silently widen or narrow: if
    this ever stops refusing, the exception is no longer real and the
    parametrization above should grow the `pe-anchored` case rather than this
    row being deleted.
    """
    from swing.trades import latched_origin as lo

    conn, cfg, candidate_id = _pe_anchored_world(
        tmp_path, "seam-declared", closes=BASE_CLOSES)
    accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
    conn.commit()

    def _fall_through(_conn, _cfg, _req):
        return lo.LatchedProvenance(
            admitted=False, recognised_but_underivable=False,
            decline_reason="no_accepted_latch_order")

    monkeypatch.setattr(
        "swing.trades.entry.resolve_latched_provenance", _fall_through,
        raising=False)
    monkeypatch.setattr(lo, "resolve_latched_provenance", _fall_through)
    with pytest.raises(PatternEvaluationAnchorError):
        enter(conn, cfg, req(pattern_evaluation_id=7))
    conn.close()


def test_the_seam_property_covers_the_WHOLE_reason_roster() -> None:
    """The closure half: the property above iterates the LIVE roster, so a
    thirty-seventh reason is covered the day it is added rather than the day
    somebody remembers to add a case for it."""
    from swing.trades.latched_origin import DECLINE_REASONS

    assert len(DECLINE_REASONS) >= 33, len(DECLINE_REASONS)


# ===========================================================================
# REVIEWER B (post-fix tree) -- THE TWO TRANSACTION DEFECTS ON THE
# MONEY-BEARING ENTRY PATH.  **ARC-INTRODUCED, NOT PRE-EXISTING.**
#
# `_entry_transaction` has ZERO occurrences in `main:swing/trades/entry.py`
# and `main`'s `entry.py` contains no `BEGIN IMMEDIATE` at all: the whole
# contextmanager arrived with `ed897bc5` ("Task 9 -- record_entry consults the
# mandate, inside BEGIN IMMEDIATE"), a commit in THIS arc's exec leg.  Under
# the introduced-versus-banked boundary that means FIX IN THE ARC, never cite
# -- and the fix leg had already repaired this exact shape THREE TIMES in
# `cohort_provenance_correction.py` while leaving it here, on the path that
# writes a trade.
#
# THE PROXY FAILS BOTH VERBS.  A proxy failing one cannot reach the
# composition -- the `22A-R15-03` lesson, which this module now inherits.
# ===========================================================================
class _EntryTxProxy:
    """Delegates the four members `_entry_transaction` touches, and can fail
    the ACQUISITION (after it really takes effect) and/or the ROLLBACK.

    ``begin`` performs the REAL statement before raising: a proxy that raised
    INSTEAD of beginning would test a transaction that never opened, which is
    a different window from the one-bytecode gap between the statement taking
    the reservation and the ``try`` being entered.
    """

    def __init__(self, conn: sqlite3.Connection, *,
                 interrupt_begin: bool = False,
                 fail_rollback: bool = False) -> None:
        self._conn = conn
        self._interrupt_begin = interrupt_begin
        self._fail_rollback = fail_rollback
        self.began = False
        self.rollback_attempted = False

    def execute(self, sql, *args, **kwargs):
        if self._interrupt_begin and sql.startswith("BEGIN IMMEDIATE"):
            self._conn.execute(sql, *args, **kwargs)
            self.began = True
            raise KeyboardInterrupt("planted just after BEGIN IMMEDIATE")
        return self._conn.execute(sql, *args, **kwargs)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self.rollback_attempted = True
        if self._fail_rollback:
            raise sqlite3.OperationalError("cannot rollback (planted)")
        self._conn.rollback()

    @property
    def in_transaction(self) -> bool:
        return self._conn.in_transaction


def test_B_an_interrupt_AT_ACQUISITION_does_not_leak_the_reservation(
        tmp_path) -> None:
    """**FIX (2).**  `BEGIN IMMEDIATE` sat OUTSIDE the `try`, so an interrupt
    landing between the statement TAKING THE WRITE RESERVATION and the `try`
    being entered skipped the handler entirely.

    Reviewer B reproduced it with a connection proxy that executes the real
    `BEGIN` and then raises: `conn.in_transaction` stayed TRUE.  On the
    money-bearing entry path that is a write reservation held on a connection
    the caller goes on using.

    PRE-FIX: `in_transaction` is True and `rollback` was never attempted.
    POST-FIX: the recovery ran and the connection is clean.  Both values are
    stated so the assertion distinguishes.
    """
    from swing.trades.entry import _entry_transaction

    conn, _, _ = build_world(tmp_path, "b-acq")
    conn.commit()
    assert not conn.in_transaction, "the premise: nothing is open"
    proxy = _EntryTxProxy(conn, interrupt_begin=True)

    with pytest.raises(KeyboardInterrupt, match="planted just after BEGIN"):
        with _entry_transaction(proxy, immediate=True):
            raise AssertionError("the body must never run")

    assert proxy.began, (
        "the planted BEGIN never took effect, so this row measures nothing "
        "about the acquisition window")
    assert proxy.rollback_attempted, (
        "the interrupt landed outside the protected region and no recovery "
        "ran at all")
    assert not conn.in_transaction, (
        "the write reservation leaked onto a connection the caller reuses")


def test_B_a_failed_rollback_after_a_failed_write_is_SURFACED_and_CHAINED(
        tmp_path) -> None:
    """**FIX (3).**  The rollback failure was swallowed by
    `contextlib.suppress(sqlite3.Error)`.

    Reviewer B reproduced an inner write followed by `ValueError`, with
    `rollback()` raising `OperationalError`: the reported exception carried NO
    cleanup cause, `in_transaction` stayed true, and the partial row stayed
    visible for a later accidental commit.

    **B's reachability line is the reason the route's mitigation is not a
    reason to leave it:** the web route's `finally: conn.close()` contains the
    open transaction, but REUSABLE SERVICE CALLERS remain exposed -- and
    `record_entry` takes a connection rather than owning one.

    This is `AL-15`'s standard, which this leg applied three times in
    `cohort_provenance_correction.py` and not here: a cleanup failure is the
    MORE DANGEROUS of two simultaneous conditions and must surface loudly.
    """
    import logging

    from swing.trades.entry import _entry_transaction

    conn, _, _ = build_world(tmp_path, "b-rb")
    conn.commit()
    proxy = _EntryTxProxy(conn, fail_rollback=True)

    with caplog_at_error() as records:
        with pytest.raises(sqlite3.OperationalError,
                           match="cannot rollback") as caught:
            with _entry_transaction(proxy, immediate=True):
                proxy.execute(
                    "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
                    "action_session_date, tickers_evaluated, aplus_count, "
                    "watch_count, skip_count, excluded_count, error_count) "
                    "VALUES (8002, '2026-07-24T17:30:05', '2026-07-24', "
                    "'2026-07-27', 1, 0, 0, 1, 0, 0)")
                raise ValueError("the write failed")

    assert proxy.rollback_attempted
    assert isinstance(caught.value.__cause__, ValueError), (
        "the WRITE error must travel with the cleanup error, or the reason "
        "the recovery ran at all is lost -- which is what a bare "
        "`suppress(sqlite3.Error)` did")
    assert "the write failed" in str(caught.value.__cause__)
    assert any("discard" in r.getMessage().lower() for r in records
               if r.levelno >= logging.ERROR), (
        "nothing told the caller the connection is unusable while its "
        "transaction is still open with a partial row in it")
    conn.rollback()


@contextlib.contextmanager
def caplog_at_error():
    """A minimal ERROR-record collector, so this module's rows keep their
    existing signatures rather than growing a `caplog` parameter."""
    import logging

    records: list[logging.LogRecord] = []

    class _Sink(logging.Handler):
        def emit(self, record):
            records.append(record)

    sink = _Sink(level=logging.ERROR)
    root = logging.getLogger()
    root.addHandler(sink)
    try:
        yield records
    finally:
        root.removeHandler(sink)


class _RollbackAfterEffect:
    """Performs the REAL rollback and then raises -- the after-effect shape."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn
        self.rolled = False

    def execute(self, *a, **kw):
        return self._conn.execute(*a, **kw)

    def commit(self) -> None:
        self._conn.commit()

    def rollback(self) -> None:
        self._conn.rollback()
        self.rolled = True
        raise KeyboardInterrupt("planted just after rollback")

    @property
    def in_transaction(self) -> bool:
        return self._conn.in_transaction


def test_B_the_cleanup_warning_is_RE_DERIVED_not_assumed(tmp_path) -> None:
    """**A CLEANUP WARNING THAT IS WRONG ABOUT THE STATE TEACHES AN OPERATOR
    TO DISTRUST THE RIGHT ONES** (Codex 22A-FIX-R9-05).

    An AFTER-EFFECT exception -- SQLite performing the rollback and the
    interrupt landing as the call returns -- leaves the transaction CLOSED and
    the partial row GONE.  The first version of this handler announced
    "STILL OPEN with a partial row in it" anyway, because it inferred the
    state from the fact that `rollback()` raised rather than asking the
    connection.

    Both halves are asserted: the state is genuinely clean, and the message
    SAYS so.  The `in_transaction`-true branch keeps its own wording and is
    pinned by `test_B_a_failed_rollback_after_a_failed_write_is_SURFACED_and_CHAINED`.
    """
    import logging

    from swing.trades.entry import _entry_transaction

    conn, _, _ = build_world(tmp_path, "b-after")
    conn.commit()
    proxy = _RollbackAfterEffect(conn)

    with caplog_at_error() as records:
        with pytest.raises(KeyboardInterrupt, match="planted just after"):
            with _entry_transaction(proxy, immediate=True):
                proxy.execute(
                    "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
                    "action_session_date, tickers_evaluated, aplus_count, "
                    "watch_count, skip_count, excluded_count, error_count) "
                    "VALUES (8003, '2026-07-24T17:30:05', '2026-07-24', "
                    "'2026-07-27', 1, 0, 0, 1, 0, 0)")
                raise ValueError("the write failed")

    assert proxy.rolled, "the planted rollback never took effect"
    assert not conn.in_transaction, "the premise: the rollback DID take effect"
    assert conn.execute(
        "SELECT COUNT(*) FROM evaluation_runs WHERE id = 8003"
    ).fetchone()[0] == 0, "the premise: nothing partial survived"

    messages = [r.getMessage() for r in records
                if r.levelno >= logging.ERROR]
    assert messages, "the cleanup failure was not reported at all"
    assert any("TOOK EFFECT" in m for m in messages), messages
    assert not any("STILL OPEN" in m for m in messages), (
        "the warning claims an open transaction and a visible partial row "
        "while the connection is clean and the row is gone")
