"""FastAPI app factory for the Phase 3a dashboard."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

import jinja2
from fastapi import FastAPI, HTTPException, Request
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from fastapi.exceptions import RequestValidationError
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


_ROW_TARGET_PREFIXES = (
    "open-position-",     # open-positions row
    "entry-form-",        # entry form (replaces watchlist row)
    "exit-form-",         # exit form (replaces open-position row)
    "stop-form-",         # stop-adjust form (replaces open-position row)
    "watchlist-row-",     # watchlist row (Enter-button target; id added in Phase 3c)
)


def _is_row_swap_target(request: Request) -> bool:
    return request.headers.get("HX-Target", "").startswith(_ROW_TARGET_PREFIXES)


def _static_dir() -> Path:
    return Path(__file__).parent / "static"


def _templates_dir() -> Path:
    return Path(__file__).parent / "templates"


def _build_templates(directory: Path) -> Jinja2Templates:
    """Construct Jinja2Templates with unconditional autoescape.

    Starlette's default environment uses `jinja2.select_autoescape()` which
    only autoescapes `.html`, `.htm`, `.xml`, `.xhtml` — NOT our `.html.j2`
    suffix. That left a latent reflected-XSS vector (e.g. a future Pydantic
    field validator raising `ValueError("bad: <script>…")` would reach the
    full-page 400 handler as raw markup). Forcing `autoescape=True` on all
    templates closes the gap; the codebase has no `{{ foo | safe }}` usage.
    """
    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(directory)),
        autoescape=True,
    )
    return Jinja2Templates(env=env)


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def _handle_any(request: Request, exc: Exception) -> HTMLResponse:
        # Preserve FastAPI/Starlette HTTPException semantics (Task 18's 404
        # relies on these flowing through the default handler).
        if isinstance(exc, (HTTPException, StarletteHTTPException)):
            return await http_exception_handler(request, exc)
        rid = getattr(request.state, "request_id", "-")
        log.exception("unhandled error (request_id=%s)", rid)
        tpls = _build_templates(app.state.templates_dir)
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
    app.state.templates = _build_templates(app.state.templates_dir)

    # Origin guard for all state-changing requests.
    app.add_middleware(
        OriginGuardMiddleware,
        bound_host=cfg.web.host,
        bound_port=cfg.web.port,
        strict=True,
    )
    # RequestId added AFTER OriginGuard → Starlette LIFO makes it OUTERMOST,
    # so 403 responses from OriginGuard still get X-Request-ID stamped.
    app.add_middleware(RequestIdMiddleware)

    configure_web_logging(cfg.paths.logs_dir)
    _register_exception_handlers(app)

    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exc(request: Request, exc: StarletteHTTPException):
        if request.headers.get("HX-Request", "").lower() == "true":
            tpls = request.app.state.templates
            # HX-Target-aware: row-prefix targets get <tr>, all other HTMX
            # targets get <div>. Spec §3.3.
            if _is_row_swap_target(request):
                return tpls.TemplateResponse(
                    request, "partials/trade_form_error.html.j2",
                    {"error_message": exc.detail},
                    status_code=exc.status_code,
                )
            return tpls.TemplateResponse(
                request, "partials/http_error_fragment.html.j2",
                {"status_code": exc.status_code, "detail": exc.detail},
                status_code=exc.status_code,
            )
        return await http_exception_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(request: Request, exc: RequestValidationError):
        """HTMX validation errors render fragments sized to the HX-Target.
        Non-HTMX GETs that accept HTML get a full-page 400 (Task 5 adds that
        branch). Non-HTMX POSTs or JSON-only GETs fall through to FastAPI
        default 422 JSON. Spec §3.3."""
        errors = exc.errors()
        first = errors[0] if errors else {}
        field = ".".join(str(p) for p in first.get("loc", ()) if p != "body") or "field"
        msg = first.get("msg", "invalid input")
        tpls = request.app.state.templates

        if request.headers.get("HX-Request", "").lower() == "true":
            if _is_row_swap_target(request) and request.method == "POST":
                return tpls.TemplateResponse(
                    request, "partials/trade_form_error.html.j2",
                    {"error_message": f"Invalid input in {field}: {msg}"},
                    status_code=400,
                )
            return tpls.TemplateResponse(
                request, "partials/http_error_fragment.html.j2",
                {"status_code": 400, "detail": f"Invalid input in {field}: {msg}"},
                status_code=400,
            )

        # Non-HTMX GET with Accept: text/html → full-page HTML error.
        # Spec §3.3 precedence rule #2. API clients (Accept without text/html)
        # continue to the FastAPI default 422 JSON via fallthrough.
        if request.method == "GET" and "text/html" in request.headers.get("accept", ""):
            from swing.web.view_models.error import PageErrorVM
            from swing.evaluation.dates import action_session_for_run
            from datetime import datetime
            try:
                session_date = action_session_for_run(datetime.now()).isoformat()
            except Exception:
                session_date = "n/a"
            vm = PageErrorVM(
                session_date=session_date,
                status_code=400,
                detail=f"Invalid input in {field}: {msg}",
            )
            return tpls.TemplateResponse(
                request, "page_error.html.j2",
                {"vm": vm},
                status_code=400,
            )

        return await request_validation_exception_handler(request, exc)

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
        trades as trades_route,
        watchlist as watchlist_route,
    )
    app.include_router(dashboard_route.router)
    app.include_router(watchlist_route.router)
    app.include_router(journal_route.router)
    app.include_router(pipeline_route.router)
    app.include_router(trades_route.router)

    return app
