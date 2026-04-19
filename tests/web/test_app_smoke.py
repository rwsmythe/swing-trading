"""create_app instantiates a FastAPI instance with the expected state."""
from __future__ import annotations

from fastapi import FastAPI

from swing.web.app import create_app


def test_create_app_returns_fastapi(test_cfg):
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    assert isinstance(app, FastAPI)
    assert app.state.cfg is cfg
    assert app.state.cfg_path == cfg_path


def test_create_app_cfg_path_optional(test_cfg):
    cfg, _ = test_cfg
    app = create_app(cfg)
    assert app.state.cfg_path is None


def test_create_app_mounts_static(test_cfg, tmp_path):
    """Static mounts exist and /static/<file> resolves."""
    from fastapi.testclient import TestClient
    cfg, cfg_path = test_cfg
    cfg.paths.charts_dir.mkdir(parents=True, exist_ok=True)

    app = create_app(cfg, cfg_path)
    # Static app.css written in Task 3; resolves through the /static mount.
    client = TestClient(app)
    r = client.get("/static/app.css")
    # File exists (empty placeholder created in Task 3) → 200.
    assert r.status_code == 200


def test_create_app_attaches_price_cache(test_cfg):
    from swing.web.price_cache import PriceCache
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    assert isinstance(app.state.price_cache, PriceCache)


def test_create_app_origin_guard_blocks_cross_origin_post(test_cfg):
    """POSTs without an accepted same-origin signal get 403 before hitting a route."""
    from fastapi.testclient import TestClient
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    # No routes exist yet in Task 7; register a dummy POST directly for the test.
    @app.post("/_test_probe")
    def _probe():
        return {"ok": True}

    client = TestClient(app)
    r = client.post("/_test_probe", headers={"Origin": "http://evil.example"})
    assert r.status_code == 403


def test_create_app_origin_guard_strict_rejects_referer_only_post(test_cfg):
    """Under strict mode, POST with only Referer (no HX-Request) → 403.
    Proves create_app wires strict=True."""
    from fastapi.testclient import TestClient
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    @app.post("/_strict_probe")
    def _probe():
        return {"ok": True}

    client = TestClient(app)
    r = client.post(
        "/_strict_probe",
        headers={"Referer": f"http://{cfg.web.host}:{cfg.web.port}/dashboard"},
    )
    assert r.status_code == 403
    assert "strict" in r.text.lower()


def test_app_state_templates_is_jinja2templates(test_cfg):
    """Spec §3.3 / decision #6: Jinja2Templates instance lives on app.state.templates,
    built once at startup. Routes must read it via request.app.state.templates."""
    from fastapi.templating import Jinja2Templates
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    assert isinstance(app.state.templates, Jinja2Templates)
