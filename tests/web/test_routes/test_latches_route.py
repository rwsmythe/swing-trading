"""GET /latches -- the read-only panel."""
from __future__ import annotations

from datetime import datetime

import pytest
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app

NOW = datetime(2026, 7, 25, 12, 0)     # Saturday -> action session 2026-07-27


def _seed_ftre(cfg, *, with_drift=True):
    """Seed the REAL FTRE geometry: run 121 aplus 18.34/14.88 plus the
    drifted watch rows 122-125 (stop -> 16.515, pivot -> 20.19)."""
    conn = connect(cfg.paths.db_path)
    rows = [(121, "2026-07-17", "2026-07-20", "aplus", 18.34, 14.88)]
    if with_drift:
        rows += [
            (122, "2026-07-20", "2026-07-21", "watch", 18.34, 15.195),
            (123, "2026-07-21", "2026-07-22", "watch", 18.34, 15.25),
            (124, "2026-07-22", "2026-07-23", "watch", 18.59, 16.515),
            (125, "2026-07-23", "2026-07-24", "watch", 20.19, 16.515),
        ]
    with conn:
        for rid, asof, action, bucket, pivot, stop in rows:
            conn.execute(
                "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
                "action_session_date, tickers_evaluated, aplus_count, "
                "watch_count, skip_count, excluded_count, error_count) "
                "VALUES (?, ?, ?, ?, 1, 0, 0, 0, 0, 0)",
                (rid, f"{asof}T17:30:05", asof, action))
            conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                "close, pivot, initial_stop, rs_method) "
                "VALUES (?, 'FTRE', ?, 17.76, ?, ?, 'universe')",
                (rid, bucket, pivot, stop))
    conn.close()


def _seed_vsts(cfg):
    conn = connect(cfg.paths.db_path)
    with conn:
        for rid, asof, action, pivot, stop in (
            (99, "2026-06-24", "2026-06-25", 13.56, 11.62),
            (126, "2026-07-24", "2026-07-27", 16.90, 13.40),
        ):
            conn.execute(
                "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
                "action_session_date, tickers_evaluated, aplus_count, "
                "watch_count, skip_count, excluded_count, error_count) "
                "VALUES (?, ?, ?, ?, 1, 1, 0, 0, 0, 0)",
                (rid, f"{asof}T17:30:05", asof, action))
            conn.execute(
                "INSERT INTO candidates (evaluation_run_id, ticker, bucket, "
                "close, pivot, initial_stop, rs_method) "
                "VALUES (?, 'VSTS', 'aplus', 13.49, ?, ?, 'universe')",
                (rid, pivot, stop))
    conn.close()


@pytest.fixture
def frozen_panel_clock(monkeypatch):
    """Freeze the panel's single clock read (the derivation is a pure function
    of it -- plan G.3)."""
    import swing.web.view_models.latches as vm_mod
    monkeypatch.setattr(vm_mod, "_now", lambda: NOW)


def test_empty_state_renders_200_with_no_latches(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert r.status_code == 200
    assert "No live latches" in r.text


def test_panel_renders_the_fire_time_stop_not_the_drifted_one(
        seeded_db, frozen_panel_clock):
    """THE discriminating render test: a latest-row implementation prints
    16.51 (the value RD quoted, ~11% early)."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert r.status_code == 200
    assert "14.88" in r.text
    assert "16.51" not in r.text
    assert "18.34" in r.text
    assert "18.89" in r.text            # zone cap 18.34 * 1.03 == 18.8902
    assert "2026-08-31" in r.text       # the ruled 30-session horizon
    assert "2026-08-17" not in r.text   # the superseded ~20-session horizon


def test_two_vsts_fires_render_as_two_rows_that_do_not_merge(
        seeded_db, frozen_panel_clock):
    """RD constraint 3: concurrent/sequential latches on one ticker must never
    merge or overwrite."""
    cfg, cfg_path = seeded_db
    _seed_vsts(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert r.status_code == 200
    assert "13.56" in r.text and "16.90" in r.text


def test_null_pivot_aplus_row_renders_a_degraded_row_not_a_500(seeded_db):
    """A6 -- planted via RAW conn.execute (write-barrier-bypass technique)."""
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(50, '2026-04-30T17:30:05', '2026-04-30', '2026-05-01', 1, 1, 0, 0, 0, 0)")
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(50, 'BAD', 'aplus', 5.0, NULL, 4.0, 'universe')")
    conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert r.status_code == 200
    assert "Degraded fires" in r.text
    assert "pivot missing" in r.text


def test_panel_writes_nothing_on_get(seeded_db, frozen_panel_clock):
    """A4: the panel GET must not touch latch_view_events -- NOR
    schwab_api_calls (the broker join is the lazy POST fragment)."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        client.get("/latches")
    conn = connect(cfg.paths.db_path)
    try:
        assert conn.execute(
            "SELECT COUNT(*) FROM latch_view_events").fetchone()[0] == 0
        assert conn.execute(
            "SELECT COUNT(*) FROM schwab_api_calls").fetchone()[0] == 0
    finally:
        conn.close()


def test_panel_degrades_to_a_visible_message_when_the_builder_raises(
        seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db

    def _boom(*_a, **_k):
        raise RuntimeError("boom")

    import swing.web.view_models.latches as vm_mod
    monkeypatch.setattr(vm_mod, "build_latch_derivation", _boom)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert r.status_code == 200
    assert "latch derivation unavailable" in r.text.lower()


def test_panel_survives_a_base_banner_failure(seeded_db, monkeypatch):
    """Codex R5-1: `_base_banner_fields` runs THREE DB reads before the
    derivation guard. If any raises, an unguarded builder 500s the page --
    an A6 violation. A guarded builder renders 200 with the safe banner."""
    cfg, cfg_path = seeded_db

    def _boom(*_a, **_k):
        raise RuntimeError("banner boom")

    import swing.web.view_models.latches as vm_mod
    monkeypatch.setattr(vm_mod, "_base_banner_fields", _boom)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert r.status_code == 200


def test_safe_banner_covers_every_base_layout_field(seeded_db):
    """Drift pin: a MISSING key in the fallback is a Jinja UndefinedError 500
    on an unrelated banner -- exactly the failure the fallback exists to
    prevent."""
    from swing.web.view_models.latches import _SAFE_BANNER, declared_banner_fields
    declared = declared_banner_fields()
    assert set(_SAFE_BANNER) == declared
    assert set(_SAFE_BANNER) == {
        "session_date", "stale_banner", "price_source_degraded",
        "price_source_degraded_until", "ohlcv_source_degraded",
        "unresolved_material_discrepancies_count",
        "recent_multi_leg_auto_correction_count", "banner_resolve_link",
    }


def test_order_fragment_is_lazily_loaded_with_an_explicit_hx_target(
        seeded_db, frozen_panel_clock):
    """The hx-target INHERITANCE gotcha: a revealed/loaded child inside any
    ancestor that sets hx-target must set hx-target='this'."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert 'hx-post="/latches/orders"' in r.text
    assert 'hx-target="this"' in r.text


def test_nav_link_target_route_exists(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    assert any(getattr(rt, "path", None) == "/latches" for rt in app.routes)
    with TestClient(app) as client:
        assert client.get("/latches").status_code == 200


def test_the_invalidation_level_is_labelled_stop_level_only(
        seeded_db, frozen_panel_clock):
    """RD gate condition on plan G.5: the panel must not present itself as
    implementing FULL invalidation. A bare 'invalidation' label with no
    qualifier FAILS."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert "stop level only" in r.text.lower()


def test_the_panel_carries_the_base_break_footnote(seeded_db, frozen_panel_clock):
    """The same condition at page level."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert "Structural base-break is not implemented in V1." in r.text
