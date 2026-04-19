"""FastAPI app factory for the Phase 3a dashboard."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.exceptions import HTTPException as StarletteHTTPException

from swing.config import Config
from swing.web.middleware.origin_guard import OriginGuardMiddleware
from swing.web.middleware.request_id import (
    RequestIdMiddleware,
    configure_web_logging,
)
from swing.web.price_cache import PriceCache

log = logging.getLogger(__name__)


def _static_dir() -> Path:
    return Path(__file__).parent / "static"


def _templates_dir() -> Path:
    return Path(__file__).parent / "templates"


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def _handle_any(request: Request, exc: Exception) -> HTMLResponse:
        # Preserve FastAPI/Starlette HTTPException semantics (Task 18's 404
        # relies on these flowing through the default handler).
        if isinstance(exc, (HTTPException, StarletteHTTPException)):
            return await http_exception_handler(request, exc)
        rid = getattr(request.state, "request_id", "-")
        log.exception("unhandled error (request_id=%s)", rid)
        tpls = Jinja2Templates(directory=str(app.state.templates_dir))
        is_htmx = request.headers.get("HX-Request", "").lower() == "true"
        template = "partials/error_fragment.html.j2" if is_htmx else "error.html.j2"
        return tpls.TemplateResponse(
            request, template,
            {"request_id": rid, "error_message": str(exc)},
            status_code=500,
        )


def create_app(cfg: Config, cfg_path: Path | None = None) -> FastAPI:
    """Build the dashboard app.

    `cfg_path` is optional for tests; `POST /pipeline/run` returns 503 when
    it is None. The CLI entry point passes `ctx.obj["config_path"]`.
    """

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.price_fetch_executor = ThreadPoolExecutor(
            max_workers=cfg.web.max_concurrent_price_fetches,
            thread_name_prefix="price-fetch",
        )
        try:
            yield
        finally:
            app.state.price_fetch_executor.shutdown(
                wait=False, cancel_futures=True,
            )

    app = FastAPI(
        title="Swing Trading Dashboard",
        docs_url=None, redoc_url=None,
        lifespan=lifespan,
    )
    app.state.cfg = cfg
    app.state.cfg_path = cfg_path
    app.state.price_cache = PriceCache(cfg)
    app.state.templates_dir = _templates_dir()

    # Origin guard for all state-changing requests.
    app.add_middleware(
        OriginGuardMiddleware,
        bound_host=cfg.web.host,
        bound_port=cfg.web.port,
    )
    # RequestId added AFTER OriginGuard → Starlette LIFO makes it OUTERMOST,
    # so 403 responses from OriginGuard still get X-Request-ID stamped.
    app.add_middleware(RequestIdMiddleware)

    configure_web_logging(cfg.paths.logs_dir)
    _register_exception_handlers(app)

    # Static mounts. charts_dir is written by the pipeline; if no run has
    # happened yet, the dir may not exist. `check_dir=False` defers the check
    # to request time — missing chart URL returns 404, and the dashboard's
    # <img onerror> handler renders a "Chart unavailable" placeholder (spec
    # §5.7 dashboard authority rule). No startup writes of any kind (R1
    # Major 6).
    app.mount(
        "/charts",
        StaticFiles(directory=cfg.paths.charts_dir, check_dir=False),
        name="charts",
    )
    app.mount("/static", StaticFiles(directory=_static_dir()), name="static")

    from swing.web.routes import (
        dashboard as dashboard_route,
        journal as journal_route,
        pipeline as pipeline_route,
        watchlist as watchlist_route,
    )
    app.include_router(dashboard_route.router)
    app.include_router(watchlist_route.router)
    app.include_router(journal_route.router)
    app.include_router(pipeline_route.router)

    return app
