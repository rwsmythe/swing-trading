"""Task 4.7 — Template change: watchlist + dashboard render flag tag.

Spec §3.5 template fragment. The pattern tag renders in the row's tags
cell as `<span class="tag tag-pattern">flag (0.78)</span>`. The dashboard
top-5 section uses the SAME `partials/watchlist_row.html.j2` partial as
the standalone /watchlist page (HTMX OOB-swap drift gotcha — both call
sites must include the partial, never hand-duplicate markup), so the
flag tag surfaces in BOTH places.

Route tests verify end-to-end: seed a classified ticker → GET /watchlist
(or /) → assert the rendered HTML contains the formatted tag.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.web.app import create_app
from swing.web.price_cache import PriceCache

from ..test_view_models._pattern_classification_seed import (
    delete_all_classifications,
    seed_pipeline_with_classification,
)


def _patch_price_cache(monkeypatch):
    """Stub PriceCache so the route doesn't try to fetch prices."""
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)


def test_watchlist_renders_flag_tag_for_classified_ticker(seeded_db, monkeypatch):
    """GET /watchlist with a classified ticker renders 'flag (0.78)' in the
    response body. Discriminator: pre-Task-4.7, the template doesn't
    reference `pattern_tag` so the string is absent."""
    cfg, cfg_path = seeded_db
    seed_pipeline_with_classification(
        cfg.paths.db_path, ticker="AAPL",
        pattern="flag", confidence=0.78,
    )
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/watchlist")
    assert resp.status_code == 200
    assert "flag (0.78)" in resp.text


def test_watchlist_omits_flag_tag_when_no_classification(seeded_db, monkeypatch):
    """Inverse: with classifications wiped, no flag tag in response.
    Catches a regression where the template hardcodes 'flag (0.78)'
    without an `if pattern_tag` guard."""
    cfg, cfg_path = seeded_db
    seed_pipeline_with_classification(
        cfg.paths.db_path, ticker="AAPL",
        pattern="flag", confidence=0.78,
    )
    delete_all_classifications(cfg.paths.db_path)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/watchlist")
    assert resp.status_code == 200
    assert "flag (" not in resp.text


def test_dashboard_top5_renders_flag_tag_for_classified_ticker(
    seeded_db, monkeypatch,
):
    """Spec §1.1(4) display surface includes the dashboard, not just
    /watchlist. The dashboard's top-5 section includes the same
    watchlist_row partial, so 'flag (0.78)' must appear when the ticker
    is in the top-5 set. Catches the failure mode where the watchlist
    page works but build_dashboard's pattern_tags is unwired into the
    template context."""
    cfg, cfg_path = seeded_db
    seed_pipeline_with_classification(
        cfg.paths.db_path, ticker="AAPL",
        pattern="flag", confidence=0.78,
    )
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "flag (0.78)" in resp.text


def test_dashboard_top5_omits_flag_tag_when_no_classification(
    seeded_db, monkeypatch,
):
    """Inverse for the dashboard: with classifications wiped, no flag
    tag — proves build_dashboard's pattern_tags is computed and not
    stuck on stale state."""
    cfg, cfg_path = seeded_db
    seed_pipeline_with_classification(
        cfg.paths.db_path, ticker="AAPL",
        pattern="flag", confidence=0.78,
    )
    delete_all_classifications(cfg.paths.db_path)
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "flag (" not in resp.text


def test_watchlist_row_collapse_renders_flag_tag(seeded_db, monkeypatch):
    """The /watchlist/<ticker>/row collapse path returns the same
    `partials/watchlist_row.html.j2` partial; it must also surface the
    flag tag so collapse-back-from-expanded does not silently drop it."""
    cfg, cfg_path = seeded_db
    seed_pipeline_with_classification(
        cfg.paths.db_path, ticker="AAPL",
        pattern="flag", confidence=0.78,
    )
    _patch_price_cache(monkeypatch)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(
            "/watchlist/AAPL/row",
            headers={"HX-Request": "true"},
        )
    assert resp.status_code == 200
    assert "flag (0.78)" in resp.text
