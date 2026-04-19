"""Phase 3d §5.5: base-layout VM compatibility.

Every VM that extends base.html.j2 now carries ohlcv_source_degraded: bool.
Unrelated routes must still render — if any VM defaults to True or omits the
field, Jinja would 500 with UndefinedError. These tests close that class of
regression.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.web.app import create_app


def test_journal_renders_with_ohlcv_source_degraded_default_false(test_cfg, seeded_db):
    """GET /journal must render 200 HTML. JournalVM's ohlcv_source_degraded
    defaults to False; the banner must NOT appear."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/journal?period=month")
    assert r.status_code == 200
    assert "<html" in r.text.lower()
    assert "SMA advisories unavailable" not in r.text


def test_watchlist_renders_with_ohlcv_source_degraded_default_false(
    test_cfg, seeded_db, monkeypatch,
):
    """GET /watchlist must render 200 HTML. WatchlistVM's ohlcv_source_degraded
    defaults to False; the banner must NOT appear."""
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/watchlist")
    assert r.status_code == 200
    assert "<html" in r.text.lower()
    assert "SMA advisories unavailable" not in r.text


def test_page_error_renders_with_ohlcv_source_degraded_default_false(test_cfg, seeded_db):
    """Force a validation error on /journal to trigger the full-page 400 path.
    PageErrorVM.ohlcv_source_degraded defaults to False; banner absent."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            "/journal?period=fortnight",
            headers={"Accept": "text/html,application/xhtml+xml,*/*"},
        )
    assert r.status_code == 400
    assert "<html" in r.text.lower()
    assert "SMA advisories unavailable" not in r.text


def test_pipeline_banner_shown_when_ohlcv_cache_is_degraded(
    test_cfg, seeded_db, monkeypatch,
):
    """Spec §3.4 R4 pass-through: when OhlcvCache.is_degraded() is True, the
    /pipeline page renders the SMA-advisories-unavailable banner."""
    from swing.web.ohlcv_cache import OhlcvCache
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: True)

    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/pipeline")
    assert r.status_code == 200
    assert "SMA advisories unavailable" in r.text


def test_pipeline_banner_absent_when_ohlcv_cache_is_not_degraded(
    test_cfg, seeded_db, monkeypatch,
):
    """Spec §3.4 R4 pass-through: when OhlcvCache.is_degraded() is False, the
    /pipeline page renders WITHOUT the banner."""
    from swing.web.ohlcv_cache import OhlcvCache
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: False)

    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/pipeline")
    assert r.status_code == 200
    assert "SMA advisories unavailable" not in r.text


def test_dashboard_banner_shown_when_ohlcv_cache_is_degraded(
    test_cfg, seeded_db, monkeypatch,
):
    """Spec §6 end-to-end: when OhlcvCache.is_degraded() is True, the
    MAIN dashboard page (GET /) renders the SMA-advisories-unavailable
    banner. Closes the coverage gap Codex R2 Major 2 flagged — banner flows
    through T12 VM plumbing → T14 route wiring → T9 base-template render."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: True)
    monkeypatch.setattr(
        OhlcvCache, "get_many_bundles",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert "SMA advisories unavailable" in r.text


def test_dashboard_banner_absent_when_ohlcv_cache_is_not_degraded(
    test_cfg, seeded_db, monkeypatch,
):
    """Spec §6 symmetric case: healthy cache → banner absent on GET /."""
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(OhlcvCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(
        OhlcvCache, "get_many_bundles",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(
        PriceCache, "get_many",
        lambda self, tickers, *, deadline_seconds, executor: {},
    )
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: None)

    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    assert "SMA advisories unavailable" not in r.text
