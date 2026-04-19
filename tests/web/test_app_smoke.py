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
