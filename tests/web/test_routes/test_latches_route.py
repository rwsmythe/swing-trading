"""GET /latches -- the read-only panel."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

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


# --- Arc 21-G Task 6 (RD OQ-3): the card states a date it can PROVE ---------
def _write_archive_bars(cfg, ticker, rows):
    """Shape-A archive bars as `(iso_session, close)`. The panel reads Shape A
    ONLY (`migrate=False` is the A4 no-write property)."""
    import pandas as pd
    cache = Path(cfg.paths.prices_cache_dir)
    cache.mkdir(parents=True, exist_ok=True)
    pd.DataFrame([
        {"asof_date": session, "open": close, "high": close, "low": close,
         "close": close, "volume": 100.0}
        for session, close in rows
    ]).to_parquet(cache / f"{ticker.upper()}.yfinance.parquet")


def _seed_last_close(cfg, rid, *, asof, action, close):
    """A NON-aplus row supplying the panel's rendered last close under the run
    stamp `asof`, without adding a fire."""
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute(
            "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, "
            "action_session_date, tickers_evaluated, aplus_count, watch_count, "
            "skip_count, excluded_count, error_count) VALUES "
            "(?, ?, ?, ?, 1, 0, 1, 0, 0, 0)",
            (rid, f"{asof}T17:30:05", asof, action))
        conn.execute(
            "INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, "
            "pivot, initial_stop, rs_method) VALUES "
            "(?, 'FTRE', 'watch', ?, 18.34, 14.88, 'universe')", (rid, close))
    conn.close()


def test_the_card_renders_the_proven_close_date_when_it_is_corroborated(
        seeded_db, frozen_panel_clock):
    """T11a -- the LOCK half of RD's OQ-3 fold-in.

    Its adversary is an implementation that degrades EVERY card to the
    upper-bound form and thereby tells the operator LESS than it knows. When
    the archive holds a bar dated the derivation session whose close IS the
    recorded close, the card may -- and must -- state that date as PROVEN."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg, with_drift=False)
    _seed_last_close(cfg, 127, asof="2026-07-24", action="2026-07-27",
                     close=17.76)
    _write_archive_bars(cfg, "FTRE", [("2026-07-24", 17.76)])
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert r.status_code == 200
    assert "close dated 2026-07-24" in r.text
    assert "on or before" not in r.text


def test_the_card_never_renders_a_run_stamp_as_the_price_own_date(
        seeded_db, frozen_panel_clock):
    """T11b -- THE DISCRIMINATOR. Survey hit 3, and RD folded it into this arc
    rather than pay a second dispatch to leave it live for a week:

        `One string, same surface, same cycle, and it renders a run-level stamp
        as a per-row date on the very panel this arc exists to correct -- a
        live instance of gotcha #30 sitting inside the fix for gotcha #30.`

    The Route-B geometry: run 127 stamps 2026-07-24 over a close that is
    actually FTRE's 2026-07-23 bar. PRE-FIX the card renders a bare
    `as of 2026-07-24` for a close that is NOT the 2026-07-24 close. POST-FIX
    it renders the UPPER BOUND the stamp actually is.

    The card already says `last_close` and `[STALE]` unconditionally, so it
    never claimed FRESHNESS -- what it claimed wrongly is the DATE.

    THE COUPLING (RD, OQ-2) is asserted here too: a card that silently dropped
    to a bare price with no date claim would satisfy `no wrong date` while
    telling the operator nothing. The reduction must be LABELLED."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg, with_drift=False)
    _seed_last_close(cfg, 127, asof="2026-07-24", action="2026-07-27",
                     close=19.52)
    _write_archive_bars(cfg, "FTRE", [
        ("2026-07-23", 19.52),      # what the recorded close ACTUALLY is
        ("2026-07-24", 17.76),      # FTRE's real 07-24 close
    ])
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert r.status_code == 200
    assert "as of 2026-07-24" not in r.text          # fails pre-fix
    assert "close dated on or before 2026-07-24" in r.text
    # ...and the reduction is LABELLED, not silently dropped.
    assert "19.52" in r.text
    assert "last_close" in r.text and "[STALE]" in r.text


def test_the_card_names_a_future_stamped_close_as_later_than_this_page(
        seeded_db, frozen_panel_clock):
    """Rung F on the card. A close stamped after the session this page
    describes cannot be dated INTO this page, so the card says exactly that
    rather than presenting a date the price does not have here."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg, with_drift=False)
    _seed_last_close(cfg, 127, asof="2026-07-28", action="2026-07-29",
                     close=17.76)
    _write_archive_bars(cfg, "FTRE", [("2026-07-24", 17.76)])
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert r.status_code == 200
    assert "as of 2026-07-28" not in r.text
    assert ("close stamped 2026-07-28, later than the session this page "
            "describes (2026-07-24)" in r.text)


def test_a_card_with_no_price_still_renders_the_shipped_dash(
        seeded_db, frozen_panel_clock):
    """Rung C is UNCHANGED: no price, no claim, the shipped `-`."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg, with_drift=False)
    conn = connect(cfg.paths.db_path)
    with conn:
        conn.execute("UPDATE candidates SET close = NULL")
    conn.close()
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert r.status_code == 200
    assert "source -, as of -" in r.text


def test_the_zone_label_is_not_re_gated_by_the_provenance_ladder(
        seeded_db, frozen_panel_clock):
    """THE SCOPE BOUNDARY, pinned so the review does not widen it. Task 6 fixes
    the DATE the card claims for the price -- it does NOT re-gate
    `_zone_position` or the IN ZONE / OUT OF ZONE label. Once the date is
    honest, `at the close dated X, this latch is in zone` is a TRUE statement:
    the zone label describes the price the card shows rather than asserting
    order coverage, so it is not a #30 instance once the date beside it stops
    overstating."""
    cfg, cfg_path = seeded_db
    _seed_ftre(cfg, with_drift=False)
    _seed_last_close(cfg, 127, asof="2026-07-24", action="2026-07-27",
                     close=19.52)                    # ABOVE the 18.89 zone cap
    _write_archive_bars(cfg, "FTRE", [("2026-07-23", 19.52)])
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/latches")
    assert r.status_code == 200
    assert "ABOVE ZONE - do not chase" in r.text
    assert "close dated on or before 2026-07-24" in r.text
