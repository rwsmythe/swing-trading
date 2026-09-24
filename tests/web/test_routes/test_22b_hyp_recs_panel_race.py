"""Arc 22-B RULING R1-3-SURFACES item 1 (i) -- ``GET /``, ``POST
/prices/refresh``, ``GET /hyp-recs/refresh`` isolate the hyp-recs panel AT
ITS BUILDER (``dashboard.py:578``, the ``build_recommendation_progress``
call) the way ``/metrics`` isolates cards: a raced cohort read degrades ONLY
the hyp-recs panel -- "hypothesis progress unavailable: cohort read raced an
intent write; re-run" -- and every other panel renders.

The race is planted by monkeypatching ``build_recommendation_progress``
(the SAME name imported by both ``build_hyp_recs_section`` at line 578 and
``build_dashboard``'s own hyp-recs construction) -- both call sites are the
subject of this arc's isolation, tested directly rather than via seeded
candidate-matching internals.
"""
from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot
from tests.web.test_routes.test_hyp_recs_expand_route import (
    _seed_hyp_recs_fixture,
)

UNAVAILABLE_TEXT = "hypothesis progress unavailable: cohort read raced an intent write; re-run"


def _patch_price_cache(monkeypatch) -> None:
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {
            t: PriceSnapshot(
                ticker=t, price=110.0, asof=datetime.now(),
                is_stale=False, source="live",
            )
            for t in tickers
        },
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def _plant_cohort_race(monkeypatch) -> None:
    import swing.web.view_models.dashboard as dashboard_mod

    def raced(conn, registry, *, starting_equity, budget_seconds=None):
        from swing.metrics.cohort import CohortReadRacedError
        raise CohortReadRacedError((3,))

    monkeypatch.setattr(dashboard_mod, "build_recommendation_progress", raced)


# ---------------------------------------------------------------------------
# VM-level: both call sites (build_hyp_recs_section, build_dashboard)
# ---------------------------------------------------------------------------
def test_build_hyp_recs_section_degrades_the_panel_b22_238(
        seeded_db, monkeypatch) -> None:
    from swing.web.view_models.dashboard import build_hyp_recs_section

    cfg, _cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    _plant_cohort_race(monkeypatch)

    vm = build_hyp_recs_section(cfg=cfg, cache=PriceCache(cfg), executor=None)
    assert vm.active_recommendations == ()
    assert vm.hyp_recs_unavailable_text == UNAVAILABLE_TEXT


def test_build_dashboard_degrades_only_the_panel_b22_238(
        seeded_db, monkeypatch) -> None:
    from swing.web.view_models.dashboard import build_dashboard

    cfg, _cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    _plant_cohort_race(monkeypatch)

    class _StubExecutor:
        pass

    vm = build_dashboard(
        cfg=cfg, cache=PriceCache(cfg), executor=_StubExecutor(),
        ohlcv_cache=None,
    )
    assert vm.active_recommendations == ()
    assert vm.hyp_recs_unavailable_text == UNAVAILABLE_TEXT
    # Every OTHER panel still rendered -- the isolation is scoped, not a
    # page-wide degrade.
    assert vm.status_strip is not None
    assert vm.watchlist_top5 is not None


# ---------------------------------------------------------------------------
# Route-level: the 3 named surfaces
# ---------------------------------------------------------------------------
def test_hyp_recs_refresh_route_degrades_the_panel_b22_238(
        seeded_db, monkeypatch) -> None:
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    _plant_cohort_race(monkeypatch)
    with TestClient(create_app(cfg, cfg_path)) as client:
        resp = client.get("/hyp-recs/refresh")
    assert resp.status_code == 200, resp.text
    assert UNAVAILABLE_TEXT in resp.text, resp.text


def test_dashboard_index_degrades_only_the_panel_b22_238(
        seeded_db, monkeypatch) -> None:
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    _plant_cohort_race(monkeypatch)
    with TestClient(create_app(cfg, cfg_path)) as client:
        resp = client.get("/")
    assert resp.status_code == 200, resp.text
    assert UNAVAILABLE_TEXT in resp.text, resp.text
    # Every other panel rendered -- the status strip's Account tile is
    # present regardless of the hyp-recs panel's degraded state.
    assert 'id="account-tile"' in resp.text, resp.text


def test_prices_refresh_degrades_only_the_panel_b22_238(
        seeded_db, monkeypatch) -> None:
    """`/prices/refresh`'s OOB response does NOT include the hyp-recs
    section at all (`partials/prices_refresh_container.html.j2` renders
    only status-strip / open-positions / watchlist-top5) -- but it calls
    `build_dashboard()` to build the FULL vm (including the hyp-recs
    computation) before selecting which fragments to render, so a raced
    cohort read there must not 500 the whole refresh over an
    unrelated-looking response. The discriminator is therefore the status
    code, not panel text that was never rendered by this route to begin
    with -- measured, not assumed."""
    cfg, cfg_path = seeded_db
    _seed_hyp_recs_fixture(cfg)
    _patch_price_cache(monkeypatch)
    _plant_cohort_race(monkeypatch)
    with TestClient(create_app(cfg, cfg_path)) as client:
        resp = client.post("/prices/refresh", headers={"HX-Request": "true"})
    assert resp.status_code == 200, resp.text
    # Every OTHER OOB fragment this route DOES emit still renders.
    assert 'id="status-strip"' in resp.text, resp.text
    assert 'id="open-positions"' in resp.text, resp.text
    assert 'id="watchlist-top5"' in resp.text, resp.text
