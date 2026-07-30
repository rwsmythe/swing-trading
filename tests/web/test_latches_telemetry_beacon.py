"""POST /latches/view -- the A4 write seam.

The panel GET writes NOTHING; this dedicated POST is the ONLY write path. The
payload is an ANCHOR of what the GET rendered (the session it was rendered FOR
plus the latch ids it showed as live), never a source of truth: both fields are
VALIDATED, the handler then RE-DERIVES as of the ANCHOR session and records the
INTERSECTION, and every wall-clock timestamp is SERVER-STAMPED.
"""
from __future__ import annotations

from datetime import date, datetime

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app

NOW = datetime(2026, 7, 25, 12, 0)     # Saturday -> action session 2026-07-27
ANCHOR = "2026-07-27"
_HX = {"HX-Request": "true"}


def _seed_ftre(cfg):
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(121, '2026-07-17T17:30:05', '2026-07-17', '2026-07-20', 1, 1, 0, 0, 0, 0)")
        cur = conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(121, 'FTRE', 'aplus', 17.76, 18.34, 14.88, 'universe')")
        cid = int(cur.lastrowid)
    conn.close()
    return cid


@pytest.fixture
def frozen_clocks(monkeypatch):
    """Freeze BOTH the panel clock and the beacon handler clock at NOW."""
    import swing.web.routes.latches as route_mod
    import swing.web.view_models.latches as vm_mod
    monkeypatch.setattr(vm_mod, "_now", lambda: NOW)
    monkeypatch.setattr(route_mod, "_now", lambda: NOW)


def _rows(cfg):
    conn = connect(cfg.paths.db_path)
    try:
        return conn.execute(
            "SELECT candidate_id, evaluation_run_id, ticker, detection_date, "
            "pipeline_run_id, view_session_date, first_viewed_ts, "
            "last_viewed_ts, view_count, latch_state_at_first_view, "
            "latch_state_at_last_view FROM latch_view_events "
            "ORDER BY view_event_id").fetchall()
    finally:
        conn.close()


def test_beacon_records_one_row_per_live_latch(seeded_db, frozen_clocks):
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/view", headers=_HX,
                        data={"view_session_date": ANCHOR,
                              "actionable_candidate_ids": str(cid),
                              "withheld_candidate_ids": ""})
    assert r.status_code == 204
    (row,) = _rows(cfg)
    assert row[0] == cid
    assert row[1] == 121 and row[2] == "FTRE"
    assert row[3] == "2026-07-20"          # the DETECTION identity, not the view
    assert row[5] == ANCHOR
    assert row[8] == 1
    assert row[9] == row[10] == "armed"


def test_a_second_beacon_the_same_session_updates_in_place(seeded_db, frozen_clocks):
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        for _ in range(2):
            client.post("/latches/view", headers=_HX,
                        data={"view_session_date": ANCHOR,
                              "actionable_candidate_ids": str(cid),
                              "withheld_candidate_ids": ""})
    (row,) = _rows(cfg)
    assert row[8] == 2                       # ONE row, advancing count
    assert row[6] == row[7]                  # same frozen clock both times


def test_beacon_ignores_a_candidate_id_that_was_not_live_at_the_anchor(
        seeded_db, frozen_clocks):
    """Server RE-DERIVES against the ANCHOR session: a forged id writes
    nothing."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/view", headers=_HX,
                        data={"view_session_date": ANCHOR,
                              "actionable_candidate_ids": "999999",
                              "withheld_candidate_ids": ""})
    assert r.status_code == 204
    assert _rows(cfg) == []


def test_beacon_ignores_a_cleared_latchs_id(seeded_db, frozen_clocks, tmp_path):
    """RD's requirement is 'viewed WHILE A LATCH WAS ARMED'. A cleared latch
    is not evidence of a missed decision, so it must not be recorded."""
    import pandas as pd
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    cfg.paths.prices_cache_dir.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"asof_date": "2026-07-21", "open": 15.0, "high": 15.2, "low": 14.0,
         "close": 14.00, "volume": 100.0},        # closes below the 14.88 stop
    ]).to_parquet(cfg.paths.prices_cache_dir / "FTRE.yfinance.parquet")
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/view", headers=_HX,
                        data={"view_session_date": ANCHOR,
                              "actionable_candidate_ids": str(cid),
                              "withheld_candidate_ids": ""})
    assert r.status_code == 204
    assert _rows(cfg) == []


def test_view_session_date_is_the_rendered_anchor_not_a_post_time_recompute(
        seeded_db, monkeypatch):
    """Codex R2-1 + the project's hazard-2 gotcha. Render for session S; the
    POST-handler clock has ROLLED to S+1. The row MUST land on S, and the latch
    MUST NOT be dropped. A post-time-recompute implementation writes S+1 (or
    nothing) and FAILS this test."""
    import swing.web.routes.latches as route_mod
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    # 2026-07-27 17:00 HST is past the close, so action_session_for_run is
    # 2026-07-28 -- one session AHEAD of the posted anchor.
    rolled = datetime(2026, 7, 27, 17, 0)
    monkeypatch.setattr(route_mod, "_now", lambda: rolled)
    from swing.evaluation.dates import action_session_for_run
    assert action_session_for_run(rolled) == date(2026, 7, 28)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/view", headers=_HX,
                        data={"view_session_date": ANCHOR,
                              "actionable_candidate_ids": str(cid),
                              "withheld_candidate_ids": ""})
    assert r.status_code == 204
    (row,) = _rows(cfg)
    assert row[5] == ANCHOR                  # S, not S+1
    assert row[9] == "armed"


def test_a_one_session_stale_anchor_is_accepted(seeded_db, monkeypatch):
    """The bounded tolerance: a rollover between render and beacon is a real
    (if narrow) window and must not silently drop the view."""
    import swing.web.routes.latches as route_mod
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    monkeypatch.setattr(route_mod, "_now", lambda: datetime(2026, 7, 27, 17, 0))
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/view", headers=_HX,
                        data={"view_session_date": ANCHOR,
                              "actionable_candidate_ids": str(cid),
                              "withheld_candidate_ids": ""})
    assert r.status_code == 204
    assert len(_rows(cfg)) == 1


def test_a_future_session_anchor_is_rejected(seeded_db, frozen_clocks):
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/view", headers=_HX,
                        data={"view_session_date": "2026-09-01",
                              "actionable_candidate_ids": str(cid),
                              "withheld_candidate_ids": ""})
    assert r.status_code == 400
    assert "view_session_date" in r.text
    assert _rows(cfg) == []


def test_a_two_session_stale_anchor_returns_409_with_a_reload_prompt(
        seeded_db, monkeypatch):
    """Codex R5-2. NOT a silent 400: a stale anchor means a RESTORED page, and
    ACCEPTING it would manufacture a view for a session the operator did not
    view (the flattering bias RD's do-not-flatter rule forbids most strongly).
    Rejecting it SILENTLY would bias the record toward false `away` -- the same
    sin in the other direction. So: 409 + a rendered reload prompt."""
    import swing.web.routes.latches as route_mod
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    monkeypatch.setattr(route_mod, "_now", lambda: datetime(2026, 7, 30, 12, 0))
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/view", headers=_HX,
                        data={"view_session_date": ANCHOR,
                              "actionable_candidate_ids": str(cid),
                              "withheld_candidate_ids": ""})
    assert r.status_code == 409
    assert "reload" in r.text.lower()
    assert _rows(cfg) == []


def test_the_stale_response_body_names_both_sessions(seeded_db, monkeypatch):
    """The notice must be actionable, and ASCII (Windows cp1252)."""
    import swing.web.routes.latches as route_mod
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    monkeypatch.setattr(route_mod, "_now", lambda: datetime(2026, 7, 30, 12, 0))
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/view", headers=_HX,
                        data={"view_session_date": ANCHOR,
                              "actionable_candidate_ids": str(cid),
                              "withheld_candidate_ids": ""})
    # 12:00 Pacific/Honolulu == 18:00 ET on Thu 2026-07-30, i.e. POST-close, so
    # the CURRENT action session is Fri 2026-07-31 -- four sessions ahead of the
    # posted anchor. The notice must name BOTH.
    assert ANCHOR in r.text and "2026-07-31" in r.text
    r.text.encode("ascii")          # raises if a non-ASCII glyph slipped in


def test_beacon_timestamps_are_server_stamped_not_client_supplied(
        seeded_db, frozen_clocks):
    """A payload carrying viewed_ts / view_count / latch_state is ignored
    entirely (the V1 server-stamp gotcha). Only the SESSION anchor and the id
    set are read from the client, and both are validated."""
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/view", headers=_HX, data={
            "view_session_date": ANCHOR, "actionable_candidate_ids": str(cid),
                              "withheld_candidate_ids": "",
            "viewed_ts": "1999-01-01T00:00:00", "view_count": "42",
            "latch_state": "filled",
        })
    assert r.status_code == 204
    (row,) = _rows(cfg)
    assert row[6].startswith("2026-07-25")       # the SERVER clock
    assert row[8] == 1                            # not 42
    assert row[9] == "armed"                      # not 'filled'


def test_empty_candidate_ids_is_valid_and_writes_nothing(seeded_db, frozen_clocks):
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/view", headers=_HX,
                        data={"view_session_date": ANCHOR,
                              "actionable_candidate_ids": "",
                              "withheld_candidate_ids": ""})
    assert r.status_code == 204
    assert _rows(cfg) == []


_A = "actionable_candidate_ids"
_W = "withheld_candidate_ids"


@pytest.mark.parametrize("form,field", [
    ({_A: "1", _W: ""}, "view_session_date"),
    # BOTH lists are REQUIRED -- an omitted list is not an empty one. A handler
    # defaulting the missing field to "" would let a beacon that has silently
    # regressed to the 21-A contract keep writing rows, with every render
    # recorded on whichever leg the default picked.
    ({"view_session_date": ANCHOR, _W: ""}, _A),
    ({"view_session_date": ANCHOR, _A: ""}, _W),
    # The superseded single field is NOT accepted, and the rejection names the
    # list it is missing rather than silently ingesting a 21-A payload.
    ({"view_session_date": ANCHOR, "candidate_ids": "1"}, _A),
    ({"view_session_date": "2026-7-27", _A: "", _W: ""}, "view_session_date"),
    ({"view_session_date": "garbage", _A: "", _W: ""}, "view_session_date"),
    ({"view_session_date": ANCHOR, _A: "true", _W: ""}, _A),
    ({"view_session_date": ANCHOR, _A: "0", _W: ""}, _A),
    ({"view_session_date": ANCHOR, _A: "-3", _W: ""}, _A),
    ({"view_session_date": ANCHOR, _A: "1.5", _W: ""}, _A),
    ({"view_session_date": ANCHOR, _A: "9500,abc", _W: ""}, _A),
    # ...and the SAME ladder on the withheld leg, which is the leg every card
    # on today's substrate actually posts on.
    ({"view_session_date": ANCHOR, _A: "", _W: "true"}, _W),
    ({"view_session_date": ANCHOR, _A: "", _W: "0"}, _W),
    ({"view_session_date": ANCHOR, _A: "", _W: "-3"}, _W),
    # An id in BOTH lists is a render asserting two incompatible facts about one
    # moment. Rejected, not silently resolved: picking a winner would decide,
    # invisibly, which way the away/lapse split is biased.
    ({"view_session_date": ANCHOR, _A: "7", _W: "7"}, _W),
])
def test_beacon_rejection_ladder_and_the_400_names_the_offending_field(
        seeded_db, frozen_clocks, form, field):
    """A silently-broken beacon must be diagnosable, so every 400 names the
    field it rejected."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/view", headers=_HX, data=form)
    assert r.status_code == 400, form
    assert field in r.text
    assert _rows(cfg) == []


def test_beacon_over_the_cap_is_rejected(seeded_db, frozen_clocks):
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    payload = ",".join(str(i) for i in range(1, 202))     # 201 ids
    with TestClient(app) as client:
        r = client.post("/latches/view", headers=_HX,
                        data={"view_session_date": ANCHOR,
                              "actionable_candidate_ids": payload,
                              "withheld_candidate_ids": ""})
    assert r.status_code == 400
    assert "candidate_ids" in r.text


def test_the_cap_applies_to_the_UNION_of_the_two_lists(seeded_db, frozen_clocks):
    """The discriminator for a per-list cap: splitting the field must not have
    doubled the flood ceiling as a side effect. 101 + 100 is over the 200 cap
    while NEITHER list is."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/view", headers=_HX, data={
            "view_session_date": ANCHOR,
            "actionable_candidate_ids": ",".join(str(i) for i in range(1, 102)),
            "withheld_candidate_ids": ",".join(str(i) for i in range(200, 300)),
        })
    assert r.status_code == 400
    assert "both lists" in r.text
    assert _rows(cfg) == []


def test_beacon_without_the_hx_request_header_is_403(seeded_db, frozen_clocks):
    """OriginGuard strict mode."""
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/view",
                        data={"view_session_date": ANCHOR,
                              "actionable_candidate_ids": str(cid),
                              "withheld_candidate_ids": ""})
    assert r.status_code == 403
    assert _rows(cfg) == []


def test_the_beacon_derivation_ignores_now_entirely(seeded_db, monkeypatch):
    """Codex R3-1. Freeze the handler clock at two DIFFERENT instants, POST the
    SAME anchor both times, and assert the recorded state is identical. A
    handler that still derives its bar bound from `now` records a different
    state for the second POST."""
    import swing.web.routes.latches as route_mod
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    seen = []
    for clock in (NOW, datetime(2026, 7, 27, 17, 0)):
        monkeypatch.setattr(route_mod, "_now", lambda c=clock: c)
        with TestClient(app) as client:
            assert client.post(
                "/latches/view", headers=_HX,
                data={"view_session_date": ANCHOR,
                      "actionable_candidate_ids": str(cid),
                              "withheld_candidate_ids": ""}).status_code == 204
        seen.append(_rows(cfg)[0][10])
    assert seen[0] == seen[1] == "armed"
    assert len(_rows(cfg)) == 1          # still ONE row for the anchor session


def test_panel_renders_the_beacon_element_with_hx_headers_and_the_session_anchor(
        seeded_db, frozen_clocks):
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert 'hx-post="/latches/view"' in r.text
    assert 'hx-trigger="load"' in r.text
    assert 'HX-Request' in r.text
    # hx-swap="innerHTML" on ITSELF, NOT "none" -- hx-swap="none" would
    # silently discard the 409 stale notice.
    assert 'id="latch-view-beacon"' in r.text
    assert "view_session_date" in r.text and ANCHOR in r.text
    assert str(cid) in r.text


def test_the_beacon_element_is_absent_when_nothing_is_live(seeded_db, frozen_clocks):
    """No live latch -> no beacon -> no write. The empty state stays honest."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert 'id="latch-view-beacon"' not in r.text


def test_panel_echoes_the_persisted_telemetry_for_a_live_latch(
        seeded_db, frozen_clocks):
    """After a beacon, the next GET shows 'first viewed' + the count -- the
    self-revealing check that the beacon still works (plan section D)."""
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        assert "NOT YET RECORDED" in client.get("/latches").text
        client.post("/latches/view", headers=_HX,
                    data={"view_session_date": ANCHOR, "actionable_candidate_ids": str(cid),
                              "withheld_candidate_ids": ""})
        after = client.get("/latches").text
    assert "first viewed" in after
    assert "NOT YET RECORDED" not in after


@pytest.mark.parametrize("bad_anchor", [
    "2026-07-26",   # Sunday
    "2026-07-25",   # Saturday
])
def test_a_non_session_anchor_is_rejected(seeded_db, frozen_clocks, bad_anchor):
    """Codex executing R1. The proximity check ALONE does not imply the anchor
    is a session: `sessions_behind(2026-07-27, 2026-07-26)` is 1 even though
    2026-07-26 is a SUNDAY. A weekend/holiday date would therefore be written as
    a `view_session_date`, corrupting the session keyspace 21-B's ledger joins
    on."""
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/view", headers=_HX,
                        data={"view_session_date": bad_anchor,
                              "actionable_candidate_ids": str(cid),
                              "withheld_candidate_ids": ""})
    assert r.status_code == 400
    assert "view_session_date" in r.text
    assert "session" in r.text.lower()
    assert _rows(cfg) == []


def test_every_persisted_view_session_date_is_a_real_nyse_session(
        seeded_db, frozen_clocks):
    """The invariant the rejection above protects, asserted on the DATA."""
    from swing.evaluation.dates import is_trading_session
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        for anchor in (ANCHOR, "2026-07-26", "2026-07-24"):
            client.post("/latches/view", headers=_HX,
                        data={"view_session_date": anchor,
                              "actionable_candidate_ids": str(cid),
                              "withheld_candidate_ids": ""})
    persisted = {r[5] for r in _rows(cfg)}
    assert persisted
    assert all(is_trading_session(date.fromisoformat(d)) for d in persisted)


# =====================================================================
# Arc 21-B Task 6b -- the beacon records SURFACE + RENDER-TIME ACTIONABILITY.
#
# THE R7 CRITICAL. A view row that does not say whether the mandate was
# actionably PRESENTED makes the away/lapse split uncomputable from renders
# that showed nothing -- and on today's substrate EVERY card is withheld, so
# that is the entire corpus rather than a corner case. Both silences are wrong
# and they are wrong in OPPOSITE directions (a withheld render recorded as a
# view inflates `discipline_lapse` and DEFLATES the away rate; not recording it
# at all inflates the away rate), which is the tell that the fact has to be
# RECORDED rather than inferred.
# =====================================================================
def _actionability(cfg):
    conn = connect(cfg.paths.db_path)
    try:
        return conn.execute(
            "SELECT surface, actionable_at_first_view, actionable_at_last_view, "
            "actionable_ever_viewed FROM latch_view_events "
            "ORDER BY view_event_id").fetchall()
    finally:
        conn.close()


def _post(client, cid, *, actionable):
    field = ("actionable_candidate_ids" if actionable
             else "withheld_candidate_ids")
    other = ("withheld_candidate_ids" if actionable
             else "actionable_candidate_ids")
    return client.post("/latches/view", headers=_HX, data={
        "view_session_date": ANCHOR, field: str(cid), other: ""})


def test_an_actionable_render_records_actionable_1_on_all_three_columns(
        seeded_db, frozen_clocks):
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        assert _post(client, cid, actionable=True).status_code == 204
    assert _actionability(cfg) == [("latch_panel", 1, 1, 1)]


def test_a_withheld_render_records_actionable_0_and_is_still_a_view(
        seeded_db, frozen_clocks):
    """It is STILL RECORDED, as `0`. Not recording it would make a latch whose
    form was withheld for its whole armed window classify `away_unseen` even
    though the operator checked the panel every day -- inflating the away rate,
    which is the number that would justify automating his entries."""
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        assert _post(client, cid, actionable=False).status_code == 204
    assert _actionability(cfg) == [("latch_panel", 0, 0, 0)]


def test_first_view_is_frozen_last_view_tracks_and_ever_is_monotonic(
        seeded_db, frozen_clocks):
    """THREE COLUMNS, THREE DIFFERENT QUESTIONS.

    A single `actionable` advanced by MAX() would let an offered later render
    retroactively upgrade an earlier withheld one -- while the row still carries
    the EARLIER `first_viewed_ts`, so it would assert "first viewed at 09:00,
    with an actionable mandate", which is false. Naming that MAX column
    `..._at_last_view` commits the mirror-image lie. So `first` is frozen at
    insert, `last` describes the LATEST view and must be able to fall 1 -> 0,
    and the monotone fact gets its own honestly-named column.
    """
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        _post(client, cid, actionable=False)      # 09:00-ish: withheld
        assert _actionability(cfg) == [("latch_panel", 0, 0, 0)]
        _post(client, cid, actionable=True)       # ...then offered
        assert _actionability(cfg) == [("latch_panel", 0, 1, 1)]


def test_an_offered_then_withheld_pair_falls_on_last_and_holds_on_ever(
        seeded_db, frozen_clocks):
    """The PAIRED discriminator, and the one that fails an implementation which
    advances `last` with MAX(): after an offered render and then a withheld one
    the LAST view genuinely was NOT actionable, while `ever` must NOT fall
    back -- the mandate WAS offered at some point this session."""
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        _post(client, cid, actionable=True)
        _post(client, cid, actionable=False)
    assert _actionability(cfg) == [("latch_panel", 1, 0, 1)]


def test_both_lists_are_intersected_with_the_live_set_INDEPENDENTLY(
        seeded_db, frozen_clocks):
    """A forged id on EITHER leg writes nothing, and a real id on the other leg
    is still recorded -- an implementation that rejects the whole payload when
    any id misses would drop a genuine view."""
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/view", headers=_HX, data={
            "view_session_date": ANCHOR,
            "actionable_candidate_ids": "999999",
            "withheld_candidate_ids": str(cid)})
    assert r.status_code == 204
    assert _actionability(cfg) == [("latch_panel", 0, 0, 0)]


def test_the_render_time_claim_survives_a_disagreeing_re_derivation(
        seeded_db, frozen_clocks, monkeypatch, caplog):
    """CODEX R11 MAJOR 3. `actionable` is a fact about WHAT THE OPERATOR WAS
    SHOWN. A card that WAS offered when he looked does not stop having been
    offered because the derivation moved a moment later, so the payload's claim
    is PERSISTED and the disagreement is LOGGED -- never silently downgraded.

    Recording "the weaker claim" sounds conservative and is a corruption: it
    manufactures a `never_actionable` for a mandate he was genuinely presented
    with. The re-derivation still gates EXISTENCE (the live-set intersection);
    it does not get a vote on what he saw.
    """
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    # No close is dated the derivation session, so a POST-time re-derivation
    # would compute a WITHHELD form for this latch -- the disagreement case.
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        assert _post(client, cid, actionable=True).status_code == 204
    assert _actionability(cfg) == [("latch_panel", 1, 1, 1)]
