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
                              "candidate_ids": str(cid)})
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
                              "candidate_ids": str(cid)})
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
                              "candidate_ids": "999999"})
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
                              "candidate_ids": str(cid)})
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
                              "candidate_ids": str(cid)})
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
                              "candidate_ids": str(cid)})
    assert r.status_code == 204
    assert len(_rows(cfg)) == 1


def test_a_future_session_anchor_is_rejected(seeded_db, frozen_clocks):
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/view", headers=_HX,
                        data={"view_session_date": "2026-09-01",
                              "candidate_ids": str(cid)})
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
                              "candidate_ids": str(cid)})
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
                              "candidate_ids": str(cid)})
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
            "view_session_date": ANCHOR, "candidate_ids": str(cid),
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
                        data={"view_session_date": ANCHOR, "candidate_ids": ""})
    assert r.status_code == 204
    assert _rows(cfg) == []


@pytest.mark.parametrize("form,field", [
    ({"candidate_ids": "1"}, "view_session_date"),
    ({"view_session_date": ANCHOR}, "candidate_ids"),
    ({"view_session_date": "2026-7-27", "candidate_ids": ""}, "view_session_date"),
    ({"view_session_date": "garbage", "candidate_ids": ""}, "view_session_date"),
    ({"view_session_date": ANCHOR, "candidate_ids": "true"}, "candidate_ids"),
    ({"view_session_date": ANCHOR, "candidate_ids": "0"}, "candidate_ids"),
    ({"view_session_date": ANCHOR, "candidate_ids": "-3"}, "candidate_ids"),
    ({"view_session_date": ANCHOR, "candidate_ids": "1.5"}, "candidate_ids"),
    ({"view_session_date": ANCHOR, "candidate_ids": "9500,abc"}, "candidate_ids"),
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
                              "candidate_ids": payload})
    assert r.status_code == 400
    assert "candidate_ids" in r.text


def test_beacon_without_the_hx_request_header_is_403(seeded_db, frozen_clocks):
    """OriginGuard strict mode."""
    cfg, cfg_path = seeded_db
    cid = _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post("/latches/view",
                        data={"view_session_date": ANCHOR,
                              "candidate_ids": str(cid)})
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
                      "candidate_ids": str(cid)}).status_code == 204
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
                    data={"view_session_date": ANCHOR, "candidate_ids": str(cid)})
        after = client.get("/latches").text
    assert "first viewed" in after
    assert "NOT YET RECORDED" not in after
