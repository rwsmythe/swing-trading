"""Slice 3: zero references to the deleted P14.N7/F-1 surfaces remain; every base-layout
route still renders (no Jinja UndefinedError from a removed VM field)."""
import pathlib

import pytest
from fastapi.testclient import TestClient

from swing.web.app import create_app

SWING = pathlib.Path(__file__).resolve().parents[2] / "swing"


@pytest.mark.parametrize("needle", [
    "checker_resilience", "schwab_checker_badge", "build_schwab_checker_badge",
    "evaluate_liveness_state", "install_resilient_checker", "CheckerLiveness",
])
def test_no_deleted_symbol_references_remain(needle: str) -> None:
    hits = [str(p) for p in SWING.rglob("*.py")
            if needle in p.read_text(encoding="utf-8")]
    tpl = [str(p) for p in SWING.rglob("*.j2")
           if needle in p.read_text(encoding="utf-8")]
    # Pre-fix: many hits across view_models/app.py/cli_schwab/base.html.j2. Post-fix: zero.
    assert not (hits + tpl), f"{needle} still referenced in: {hits + tpl}"


@pytest.mark.parametrize("path", [
    "/", "/pipeline", "/journal", "/watchlist", "/config", "/metrics", "/schwab/status",
])
def test_base_layout_routes_render_without_badge(seeded_db, monkeypatch, tmp_path, path):
    cfg, cfg_path = seeded_db
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get(path)
    assert resp.status_code in (200, 302)  # no 500 UndefinedError from a removed field
