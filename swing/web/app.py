"""FastAPI app factory for the Phase 3a dashboard."""
from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI

from swing.config import Config


def create_app(cfg: Config, cfg_path: Path | None = None) -> FastAPI:
    """Build the dashboard app.

    `cfg_path` is optional for test instantiation; `POST /pipeline/run`
    returns 503 when it is None. Set it in the CLI entry point from
    `ctx.obj["config_path"]` so subprocess launch has a source file.
    """
    app = FastAPI(title="Swing Trading Dashboard", docs_url=None, redoc_url=None)
    app.state.cfg = cfg
    app.state.cfg_path = cfg_path
    return app
