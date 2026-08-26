"""22-A Task 10 -- EXT-2 at the entry route: tier (e) + the order-id shape rung.

WHAT THIS MODULE PROVES, and it is a ROUTE claim rather than a service one.
Task 10's whole touch is ``swing/web/routes/trades.py`` (plan S7), so every
assertion here is about what the ROUTE does with a request carrying a usable
broker order id: it performs NO origin-based rejection, opens NO connection of
its own for that decision, and reaches ``record_entry``.  What the SERVICE then
answers is task 9's, already pinned at the persisted-row grain.

WHY "REACHED ``record_entry``" IS THE ASSERTION AND NOT A STATUS CODE.  Both a
tier-(e) route rejection and a service refusal render a 400 carrying the same
operator-facing message -- deliberately, because the guard was RELOCATED rather
than reworded (review 22A-R9-03).  A status-code assertion therefore cannot
tell the two apart, and telling them apart is the entire content of EXT-2(a).
The spy is the discriminator.

FROZEN CLOCK.  Every session is an explicit date; nothing reads the wall clock.
"""
from __future__ import annotations

import json
from datetime import date

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app
from tests._latch_probe_world_22a import (
    BASE_CLOSES,
    BROKER_ORDER_ID,
    FILL_SESSION,
    STOP,
    TICKER,
    accept_and_link,
    seed_fire,
    seed_run,
    write_closes,
)
from tests.web.test_routes.test_phase13_t2_sb6c_t_a_6c_4 import (
    _pretrade_form_kwargs,
)

ACCEPT_SESSION = date(2026, 7, 21)
DRIFT_RUN = 900

# The shape rung's own words.  Asserted rather than the key name, because the
# key name appears in the round-tripped hidden input on EVERY rejection.
_SHAPE_RUNG_MESSAGE = "schwab_order_id that is not a non-empty string"


def _build_route_world(cfg, *, closes=None, with_link: bool) -> tuple[int, int]:
    """The probe world, inside the REAL app config.

    Returns ``(candidate_id, pipeline_run_id_of_the_drift_run)``.

    THE FIRE ROLLS OUT DELIBERATELY: a LATER complete run carries no candidate
    for the ticker, so ``derive_trade_origin`` answers ``manual_off_pipeline``
    and tier (e) is armed.  Without that the route would pass the request
    through for a reason unrelated to EXT-2.
    """
    from tests.trades._cohort_provenance_fixtures import (
        rebase_status_history_recorded_at,
        seed_pipeline_run,
    )

    cfg.paths.prices_cache_dir.mkdir(parents=True, exist_ok=True)
    conn = connect(cfg.paths.db_path)
    try:
        candidate_id = seed_fire(conn)
        run = conn.execute(
            "SELECT data_asof_date, action_session_date FROM evaluation_runs "
            "WHERE id = 121").fetchone()
        seed_pipeline_run(
            conn, evaluation_run_id=121, data_asof_date=run[0],
            action_session_date=run[1],
            started_ts=f"{run[0]}T17:30:26", finished_ts=f"{run[0]}T17:44:45")
        # THE DRIFT: a later complete run with NO candidate for the ticker.
        seed_run(conn, DRIFT_RUN, FILL_SESSION)
        seed_pipeline_run(
            conn, evaluation_run_id=DRIFT_RUN, data_asof_date="2026-07-24",
            action_session_date=FILL_SESSION.isoformat(),
            started_ts="2026-07-24T17:30:00",
            finished_ts="2026-07-24T17:44:59")
        pipeline_run_id = conn.execute(
            "SELECT id FROM pipeline_runs WHERE evaluation_run_id = ?",
            (DRIFT_RUN,)).fetchone()[0]
        conn.execute(
            "INSERT INTO pattern_evaluations (id, pipeline_run_id, ticker, "
            "pattern_class, detector_version, geometric_score, "
            "geometric_score_json, composite_score, structural_evidence_json, "
            "feature_distribution_log_json, window_start_date, "
            "window_end_date, created_at) "
            "VALUES (77, ?, ?, 'vcp', 'v1', 0.8, '{}', 0.8, '{}', '{}', "
            "'2026-07-01', '2026-07-24', '2026-07-24T17:44:45')",
            (pipeline_run_id, TICKER))
        rebase_status_history_recorded_at(conn)
        if with_link:
            accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
        conn.commit()

        from swing.trades.origin import EntryPath, derive_trade_origin
        derived = derive_trade_origin(conn, TICKER, EntryPath.MANUAL_WEB_FORM)
        assert derived == "manual_off_pipeline", (
            f"the fixture must arm tier (e) (got {derived}), or the route "
            f"passes the request through for a reason unrelated to EXT-2")
    finally:
        conn.close()
    write_closes(cfg, BASE_CLOSES if closes is None else closes)
    return candidate_id, int(pipeline_run_id)


def _envelope(order_id=BROKER_ORDER_ID) -> str:
    return json.dumps(
        {
            "entry_date": FILL_SESSION.isoformat(),
            "entry_date_source": "execution_leg",
            "entry_price": 18.50,
            "shares": 2,
            "schwab_order_id": order_id,
            "schwab_instrument_symbol": TICKER,
        },
        sort_keys=True,
    )


def _post_data(*, pipeline_run_id: int, envelope: str | None) -> dict:
    data = {
        "ticker": TICKER,
        "entry_date": FILL_SESSION.isoformat(),
        "entry_price": "18.50",
        "shares": "2",
        "initial_stop": "14.00",
        "rationale": "vcp-breakout",
        "origin": "watchlist",
        "pattern_evaluation_id": "77",
        "claimed_pattern_evaluation_anchor": "true",
        "pipeline_run_id_at_form_render": str(pipeline_run_id),
    }
    data.update(_pretrade_form_kwargs())
    if envelope is not None:
        data["schwab_source_value_json"] = envelope
        data["fill_origin_at_form_render"] = "schwab_auto"
        data["auto_fill_audit_at"] = f"{FILL_SESSION.isoformat()}T09:00:00"
    return data


def _spy_record_entry(monkeypatch, *, before=None) -> list[str]:
    """Record every ``record_entry`` the ROUTE makes, optionally racing first.

    ``before`` runs INSIDE the call, before the service does anything -- which
    is the window between the route's decision point and the service's
    ``BEGIN IMMEDIATE``.
    """
    import swing.web.routes.trades as route_mod

    real = route_mod.record_entry
    calls: list[str] = []

    def _spy(conn, req, **kw):
        if before is not None and not calls:
            before()
        calls.append(req.ticker)
        return real(conn, req, **kw)

    monkeypatch.setattr(route_mod, "record_entry", _spy)
    return calls


def _written(cfg) -> list[tuple]:
    conn = connect(cfg.paths.db_path)
    try:
        return conn.execute(
            "SELECT ticker, trade_origin, candidate_id, hypothesis_label "
            "FROM trades ORDER BY id").fetchall()
    finally:
        conn.close()


def _breach_closes() -> dict[date, float]:
    """BASE_CLOSES with ONE prior session's close five cents under the stop.

    Five cents is the real AMN breach magnitude; a deep breach passes sloppy
    encodings and this one does not.
    """
    closes = dict(BASE_CLOSES)
    closes[date(2026, 7, 23)] = round(STOP - 0.05, 2)
    return closes


# ===========================================================================
# CASE 37 -- BOTH branches pass through the route
# ===========================================================================
def test_an_admitted_latched_entry_passes_through_the_route_case_37(
        seeded_db, monkeypatch) -> None:
    """Branch (b): recognised AND admitted.

    PRE-FIX the route rejects at tier (e) -- the server-derived origin has
    drifted to manual while a ``pattern_evaluation_id`` anchor is present --
    and ``record_entry`` is NEVER CALLED, so the arc's own mechanism is
    unreachable through the production form (#31, cross-site composition).
    POST-FIX the route decides nothing and the service admits.
    """
    cfg, cfg_path = seeded_db
    candidate_id, pipeline_run_id = _build_route_world(cfg, with_link=True)
    calls = _spy_record_entry(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        response = client.post(
            "/trades/entry",
            data=_post_data(pipeline_run_id=pipeline_run_id,
                            envelope=_envelope()),
            headers={"HX-Request": "true"})

    assert calls == [TICKER], (
        "the route decided the request itself; `record_entry` was never "
        "reached, so the latch mechanism is unreachable through the form")
    assert response.status_code == 200
    assert _written(cfg) == [
        (TICKER, "pipeline_aplus", candidate_id, "A+ baseline (aplus)")]


def test_a_recognised_and_refused_entry_passes_through_the_route_case_37(
        seeded_db, monkeypatch) -> None:
    """Branch (c): recognised AND REFUSED (the mandate was invalidated).

    An acceptance naming only the admitted branch passes an implementation
    that still rejects (c) at the route -- which is the branch where a
    money-bearing entry would be blocked over cohort bookkeeping.  So the
    claim is asserted where it lives: the route reached the service.

    The SERVICE's answer for this shape is task 9's and is NOT re-decided
    here.  See the module docstring: both a route rejection and a service
    refusal render the same 400, and the spy is what distinguishes them.

    MEASURED DOWNSTREAM OUTCOME, RECORDED AND DELIBERATELY NOT ASSERTED.
    End to end this request currently returns **400 carrying the PE-anchor
    message, with NO row written**: the route defers (this test's claim), and
    `record_entry`'s RELOCATED guard then refuses, because its condition is
    "latch resolution did not admit" and `recognised_but_underivable` is a
    not-admitted state.

    THE PLAN SPECIFIES THE OPPOSITE END STATE AT TWO SITES -- S5.2's outcome
    (c) ("pass through, do NOT reject ... the service's correct answer is the
    honest-unset row") and S3.7 lens row 43 ("the route must NOT reject it, or
    the service never writes the honest-unset row").  Reconciling them is a
    ONE-LINE change to task 9's guard (fire on the ORDINARY path only, which
    still refuses case 37c) and it collides with `22A-R4-06`, the open
    measurement-semantics question about whether an honest-unset row may keep
    a `pattern_evaluation_id` backlink at all.

    So the outcome is REPORTED rather than pinned: asserting it here would
    cement a contested reading in the test suite, and asserting the opposite
    would ship an unruled behaviour change.  Whichever way it is ruled, the
    ruling gets its own test.
    """
    cfg, cfg_path = seeded_db
    _, pipeline_run_id = _build_route_world(
        cfg, closes=_breach_closes(), with_link=True)
    calls = _spy_record_entry(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        client.post(
            "/trades/entry",
            data=_post_data(pipeline_run_id=pipeline_run_id,
                            envelope=_envelope()),
            headers={"HX-Request": "true"})

    assert calls == [TICKER], (
        "the route rejected a RECOGNISED-AND-REFUSED request instead of "
        "passing it through; (c) is the branch S5.2 names explicitly")


# ===========================================================================
# CASE 37b -- the ROUTE-level no-link -> link race
# ===========================================================================
def test_a_link_arriving_after_the_routes_decision_point_wins_case_37b(
        seeded_db, monkeypatch) -> None:
    """The shipped route opened its OWN connection, computed a rejection and
    closed it before ``record_entry`` opened another, so it could observe
    "no link + manual origin", reject, and never reach the authoritative
    transaction at all -- even for a link that landed immediately afterwards.

    PRE-FIX: 400, zero trades, ``record_entry`` never called.  POST-FIX: the
    route reads nothing, the link lands in the window, and the written row
    carries the fire's three keys.
    """
    cfg, cfg_path = seeded_db
    candidate_id, pipeline_run_id = _build_route_world(cfg, with_link=False)

    def _link_arrives() -> None:
        conn = connect(cfg.paths.db_path)
        try:
            accept_and_link(conn, candidate_id, session=ACCEPT_SESSION)
            conn.commit()
        finally:
            conn.close()

    calls = _spy_record_entry(monkeypatch, before=_link_arrives)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        response = client.post(
            "/trades/entry",
            data=_post_data(pipeline_run_id=pipeline_run_id,
                            envelope=_envelope()),
            headers={"HX-Request": "true"})

    assert calls == [TICKER]
    assert response.status_code == 200
    assert _written(cfg) == [
        (TICKER, "pipeline_aplus", candidate_id, "A+ baseline (aplus)")], (
        "the written row did not reflect the INSIDE verdict")


# ===========================================================================
# EXT-2(a)'s OTHER HALF -- a request with NO usable order id keeps today's
# route behaviour byte-for-byte, which is what bounds the LOCK's scope.
# ===========================================================================
def test_a_request_without_an_order_id_is_still_rejected_by_the_route(
        seeded_db, monkeypatch) -> None:
    """The tier-(e) rejection is NARROWED, never deleted.

    Without this the change would read as "the route stops deciding" for
    EVERY request, silently removing a live production rejection from the
    ordinary form path -- the 22A-R9-03 class one surface over.
    """
    cfg, cfg_path = seeded_db
    _, pipeline_run_id = _build_route_world(cfg, with_link=True)
    calls = _spy_record_entry(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        response = client.post(
            "/trades/entry",
            data=_post_data(pipeline_run_id=pipeline_run_id, envelope=None),
            headers={"HX-Request": "true"})

    assert response.status_code == 400
    assert calls == [], "the route deferred a request carrying NO order id"
    assert _written(cfg) == []


# ===========================================================================
# EXT-2(b) -- the `schwab_order_id` SHAPE RUNG
#
# The ladder validated `entry_date` / `entry_price` / `shares` and NOT
# `schwab_order_id`.  Harmless until this arc, which promotes the key to
# provenance-bearing (plan S2.4.1 / F4).
# ===========================================================================
@pytest.mark.parametrize(
    "bad", ["", "   ", 1002937461, 1.5, True, ["1002937461"], {"id": "1"}],
    ids=["empty", "whitespace", "int", "float", "bool", "list", "dict"])
def test_a_malformed_order_id_in_the_envelope_is_rejected(
        seeded_db, monkeypatch, bad) -> None:
    """Every non-string and every blank string, not just the empty one.

    A value-set sweep that checked only ``""`` would miss the numeric case,
    which is the LIKELY tamper: Schwab order ids read as numbers.
    """
    cfg, cfg_path = seeded_db
    _, pipeline_run_id = _build_route_world(cfg, with_link=True)
    calls = _spy_record_entry(monkeypatch)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        response = client.post(
            "/trades/entry",
            data=_post_data(pipeline_run_id=pipeline_run_id,
                            envelope=_envelope(order_id=bad)),
            headers={"HX-Request": "true"})

    assert response.status_code == 400
    # THE MESSAGE, NOT THE KEY NAME.  Tier (e) refuses this request anyway
    # (a malformed id is not a usable one), and the re-rendered form echoes
    # the envelope, so `"schwab_order_id" in response.text` would pass for a
    # reason unrelated to the rung -- a test blocked for an unrelated reason
    # proves nothing.
    assert _SHAPE_RUNG_MESSAGE in response.text, (
        "the request was refused, but not by the shape rung")
    assert calls == [], "a malformed order id reached the service"
    assert _written(cfg) == []


def test_an_absent_or_null_order_id_is_accepted_by_the_shape_rung(
        seeded_db, monkeypatch) -> None:
    """THE ACCEPTED BASELINE, and a refusal-only set could not establish it.

    ``entry_auto_fill`` writes the key from ``getattr(chosen, 'order_id',
    None)``, so a JSON null is a shape the SERVER ITSELF renders; a rung that
    rejected it would refuse the form's own output.  An absent key is the
    pre-22-A envelope and every legacy round-trip.
    """
    cfg, cfg_path = seeded_db
    _, pipeline_run_id = _build_route_world(cfg, with_link=True)
    calls = _spy_record_entry(monkeypatch)

    null_envelope = _envelope(order_id=None)
    absent = json.loads(null_envelope)
    del absent["schwab_order_id"]

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        for envelope in (null_envelope, json.dumps(absent, sort_keys=True)):
            response = client.post(
                "/trades/entry",
                data=_post_data(pipeline_run_id=pipeline_run_id,
                                envelope=envelope),
                headers={"HX-Request": "true"})
            assert _SHAPE_RUNG_MESSAGE not in response.text, (
                "the shape rung refused an envelope the server itself renders")
    # Neither carries a usable order id, so both take the ordinary route path
    # and tier (e) still refuses them -- which is the previous test's claim,
    # asserted here only to show the rung is not what stopped them.
    assert calls == []
