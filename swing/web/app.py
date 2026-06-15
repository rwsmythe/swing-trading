"""FastAPI app factory for the Phase 3a dashboard."""
from __future__ import annotations

import logging
import threading
import time as _time
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
from swing.config_overrides import apply_overrides
from swing.integrations.schwab.auth import (
    construct_authenticated_client,
    resolve_credentials_env_or_prompt,
)
from swing.integrations.schwab.client import SchwabConfigMissingError
from swing.logging_setup import install_logging
from swing.monitoring.stoplights import health_stoplights
from swing.web.middleware.body_size import MaxBodySizeMiddleware
from swing.web.middleware.origin_guard import OriginGuardMiddleware
from swing.web.middleware.request_id import RequestIdMiddleware
from swing.web.ohlcv_cache import OhlcvCache
from swing.web.price_cache import PriceCache

log = logging.getLogger(__name__)


_ROW_TARGET_PREFIXES = (
    "open-position-",     # open-positions row
    "entry-form-",        # entry form (replaces watchlist row)
    "exit-form-",         # exit form (replaces open-position row)
    "stop-form-",         # stop-adjust form (replaces open-position row)
    "watchlist-row-",     # watchlist row (Enter-button target; id added in Phase 3c)
    "hyp-rec-row-",       # hyp-recs row (chevron expand target; spec §3.5.4 R1-Major-2)
)


def _is_row_swap_target(request: Request) -> bool:
    return request.headers.get("HX-Target", "").startswith(_ROW_TARGET_PREFIXES)


def _row_error_colspan(request: Request) -> int:
    """Return the colspan to render on `trade_form_error.html.j2`.

    Per-target column-count mapping for HTMX row-swap error fragments:

    - `hyp-rec-row-*`     → 10 (hyp-recs table; +Chart col, P14.N1)
    - `open-position-*`   → 11 (open-positions table; +Chart col, P14.N1)
    - everything else     → 8  (default)

    The default-8 bucket currently covers `watchlist-row-*` (8-col
    watchlist table) and the form-target prefixes
    (`entry-form-*`, `exit-form-*`, `stop-form-*`). The form-target
    prefixes are PRE-EXISTING AMBIGUOUS: a form id alone does not
    reveal the originating table (entry forms replace watchlist rows,
    exit/stop forms replace open-position rows), so the correct
    colspan can't be derived without additional context. Tracked as
    follow-up; until then, those targets fall through to 8 and may
    render a 2-cell-short error row on a server error during exit/stop
    form submission. Surfaced by Codex R3.
    """
    hx_target = request.headers.get("HX-Target", "")
    if hx_target.startswith("hyp-rec-row-"):
        return 10   # hyp-recs table: 8 data columns + chevron + Chart (P14.N1)
    if hx_target.startswith("open-position-"):
        return 11   # open-positions table: 10 data columns + Chart (P14.N1)
    return 8


def _static_dir() -> Path:
    return Path(__file__).parent / "static"


def _templates_dir() -> Path:
    return Path(__file__).parent / "templates"


def _health_stoplights_context_processor(request: Request) -> dict:
    """Phase 18 Arc 18-F: inject the two health stoplights into EVERY template
    render via a Starlette context processor (so `base.html.j2` reads them from
    the render context, NOT a per-VM field — sidestepping the every-base-VM-or-500
    gotcha for all ~15 base VMs).

    DEFENSIVE (LOCK #2 outer guard): runs on EVERY render INCLUDING the error
    page, so it MUST NEVER raise — any failure degrades to an empty tuple (zero
    stoplights rendered, never a 500). Opens+closes a read-only DB connection per
    render (cheap — the cash-badge precedent; the providers SELECT only).
    """
    try:
        cfg = getattr(request.app.state, "cfg", None)
        if cfg is None:
            return {"health_stoplights": ()}
        # Apply the live user-config overrides (the journal.py:157 drill-down
        # precedent) so the topbar stoplight cannot diverge from the drill-down
        # page after a live user-config.toml edit (Codex R1 MAJOR). Still
        # DEFENSIVE: any apply_overrides raise is caught by the outer except ->
        # empty tuple (no stoplights), never a 500.
        cfg = apply_overrides(cfg)
        from swing.data.db import connect
        conn = connect(cfg.paths.db_path)
        try:
            stoplights = health_stoplights(conn, cfg)
        finally:
            conn.close()
        return {"health_stoplights": stoplights}
    except Exception as exc:  # noqa: BLE001 (defensive — must never 500 a page)
        log.warning(
            "health stoplights context processor degraded to empty: %s", exc,
        )
        return {"health_stoplights": ()}


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
    # Register the 18-F health-stoplights context processor INSIDE
    # _build_templates so EVERY Jinja2Templates instance carries it — both the
    # long-lived `app.state.templates` AND the FRESH instance the error handler
    # builds for the 500 page (so the stoplights render on the error page too).
    # Starlette 1.0.0 accepts `context_processors=` alongside `env=` (verified;
    # only `directory ^ env` is mutually exclusive).
    return Jinja2Templates(
        env=env, context_processors=[_health_stoplights_context_processor],
    )


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
        # Bug 2 follow-up (defense-in-depth): row-target HTMX requests get
        # a <tr> fragment so the HTML parser does not hoist a bare <div>
        # out of <tbody>, leaving an empty row position. Mirrors
        # `_handle_http_exc`'s row-target awareness for the unhandled-
        # exception path.
        if is_htmx and _is_row_swap_target(request):
            return tpls.TemplateResponse(
                request, "partials/trade_form_error.html.j2",
                {
                    "error_message": str(exc),
                    "colspan": _row_error_colspan(request),
                },
                status_code=500,
            )
        template = "partials/error_fragment.html.j2" if is_htmx else "error.html.j2"
        return tpls.TemplateResponse(
            request, template,
            {"request_id": rid, "error_message": str(exc)},
            status_code=500,
        )


# ---- A-3 web market-data ladder install (mirrors pipeline runner) ----
# SB5.5 / Phase 14: install the EXISTING production-gated market-data ladder on
# the long-lived `swing web` caches at full parity, bounded by the L9 gates.
# ZERO new schwabdev client-construction call sites (reuses the shared
# construct_authenticated_client factory; L2 LOCK).

_WEB_OPEN_TRADE_MEMO_TTL_S = 60.0
_WEB_LADDER_FALLBACK_COOLDOWN_THRESHOLD = 3


def _construct_web_schwab_client(cfg) -> object | None:
    """Construct the long-lived web Schwab client (graceful degradation).

    Gated on _is_ladder_active(cfg) FIRST so the default sandbox/test app
    constructs NO client, spawns NO checker thread, and hits NO network.
    Mirrors swing/pipeline/runner.py:_construct_pipeline_schwab_client but
    adds the web-layer ladder-active gate (so TestClient stays offline).
    """
    from swing.integrations.schwab.marketdata_ladder import _is_ladder_active
    if not _is_ladder_active(cfg):
        return None
    environment = cfg.integrations.schwab.environment
    try:
        client_id, client_secret = resolve_credentials_env_or_prompt(
            cfg, environment, allow_prompt=False,
        )
    except SchwabConfigMissingError:
        log.warning(
            "Web schwab_client construction skipped: credentials incomplete; "
            "web market-data falls back to yfinance.",
        )
        return None
    if client_id is None or client_secret is None:
        log.info(
            "Web schwab_client construction skipped: Schwab credentials "
            "absent at the env and cfg tiers (allow_prompt=False); web "
            "market-data falls back to yfinance. If you use Schwab, set "
            "integrations.schwab.client_id/client_secret in "
            "~/swing-data/user-config.toml (the web app now applies "
            "user-config overrides).",
        )
        return None
    try:
        return construct_authenticated_client(
            cfg, environment, client_id=client_id, client_secret=client_secret,
        )
    except Exception as exc:  # noqa: BLE001 -- graceful-degradation safety boundary
        from swing.integrations.schwab.auth import _redacted_excerpt
        log.warning(
            "Web schwab_client construction failed (%s: %s); web market-data "
            "falls back to yfinance.",
            type(exc).__name__, _redacted_excerpt(exc),
        )
        return None


class _WebLadderState:
    """L9 gate state shared by both hooks; thread-safe (executor + request)."""

    def __init__(self, cfg) -> None:
        self._cfg = cfg
        self._lock = threading.Lock()
        self._open_trades: frozenset[str] = frozenset()
        self._open_trades_asof = -1e18           # monotonic; forces first refresh
        self._consecutive_fallbacks = 0
        self._cooldown_until = 0.0               # monotonic

    def _refresh_open_trades(self) -> None:
        # DB read OUTSIDE the lock to avoid holding it during I/O. A transient
        # DB error (e.g. a lock during a pipeline write) must NOT propagate out
        # of the cache worker: retain the prior memo and back off for the TTL so
        # the hook degrades to yfinance rather than raising (Codex R1 Major #1).
        from swing.data.db import connect
        from swing.data.repos.trades import list_open_trades
        try:
            conn = connect(self._cfg.paths.db_path)
            try:
                tickers = frozenset(
                    t.ticker.upper() for t in list_open_trades(conn)
                )
            finally:
                conn.close()
        except Exception:  # noqa: BLE001 -- never let a DB error kill the hook
            log.warning(
                "web ladder open-trade memo refresh failed; retaining prior "
                "scope and backing off for the memo TTL.",
            )
            with self._lock:
                self._open_trades_asof = _time.monotonic()
            return
        with self._lock:
            self._open_trades = tickers
            self._open_trades_asof = _time.monotonic()

    def should_use_schwab(self, ticker: str) -> bool:
        now = _time.monotonic()
        with self._lock:
            if now < self._cooldown_until:
                return False
            stale = (now - self._open_trades_asof) > _WEB_OPEN_TRADE_MEMO_TTL_S
            current = self._open_trades
        if stale:
            self._refresh_open_trades()
            with self._lock:
                current = self._open_trades
        return ticker.upper() in current

    def note_provider(self, provider_tag: str) -> None:
        with self._lock:
            if provider_tag == "yfinance":
                self._consecutive_fallbacks += 1
                if self._consecutive_fallbacks >= _WEB_LADDER_FALLBACK_COOLDOWN_THRESHOLD:
                    self._cooldown_until = (
                        _time.monotonic()
                        + self._cfg.web.circuit_breaker_cooldown_seconds
                    )
                    self._consecutive_fallbacks = 0
            else:  # 'schwab_api' success
                self._consecutive_fallbacks = 0


def _install_web_marketdata_caches(cfg, price_cache, ohlcv_cache) -> object | None:
    """Install the EXISTING ladder hooks on the web caches (full parity).

    Returns the constructed web Schwab client or None (sandbox / no creds /
    construction failure -> yfinance-only web app, today's behavior). Also
    (Phase 15: the P14.N7 resilient-checker wrap + liveness sidecar were removed
    with the schwabdev v3 upgrade -- v3 refreshes synchronously per-request, so
    there is no daemon thread to babysit, and the topbar checker badge is gone.)
    """
    from swing.integrations.schwab.marketdata_ladder import _is_ladder_active
    ladder_active = _is_ladder_active(cfg)

    client = _construct_web_schwab_client(cfg)
    if client is None:
        # The specific None-path reason (creds-absent / creds-partial-raise /
        # construction-raise) is logged by _construct_web_schwab_client above.
        log.info(
            "web schwab client not constructed (ladder_active=%s); web "
            "market-data falls back to yfinance.",
            ladder_active,
        )
        return None

    from swing.data.db import connect
    from swing.integrations.schwab.marketdata_ladder import (
        fetch_quote_via_ladder,
        fetch_window_via_ladder,
        resolve_full_archive_bars,
    )

    state = _WebLadderState(cfg)

    def _yf_quote_fallback(ticker: str):
        from datetime import datetime as _dt2

        from swing.web.price_cache import PriceSnapshot
        price = price_cache._fetch_live_price(ticker)
        return PriceSnapshot(
            ticker=ticker, price=price, asof=_dt2.now(),
            is_stale=False, source="live", provider="yfinance",
        )

    def _quote_hook(ticker: str) -> tuple[float, str]:
        if not state.should_use_schwab(ticker):
            snap = _yf_quote_fallback(ticker)          # bypass Schwab; NO audit row
            return (snap.price, "yfinance")
        conn = connect(cfg.paths.db_path)
        try:
            snap, provider_tag = fetch_quote_via_ladder(
                ticker, cfg=cfg, schwab_client=client,
                yfinance_fallback_fn=_yf_quote_fallback,
                conn=conn, surface="pipeline", pipeline_run_id=None,
            )
        finally:
            conn.close()
        state.note_provider(provider_tag)
        return (snap.price, provider_tag)

    def _yf_window_fallback(ticker: str, start, end):
        from datetime import datetime as _dt

        from swing.data.ohlcv_archive import read_or_fetch_archive
        from swing.evaluation.dates import last_completed_session
        return read_or_fetch_archive(
            ticker,
            end_date=last_completed_session(_dt.now()),
            cache_dir=cfg.paths.prices_cache_dir,
            archive_history_days=cfg.archive.archive_history_days,
        )

    def _bars_hook(ticker: str):
        if not state.should_use_schwab(ticker):
            bars = _yf_window_fallback(ticker, None, None)
            return (bars, "yfinance")              # bypass Schwab; NO audit row
        conn = connect(cfg.paths.db_path)
        try:
            window, provider_tag = fetch_window_via_ladder(
                ticker, start=None, end=None, cfg=cfg, schwab_client=client,
                yfinance_fallback_fn=_yf_window_fallback,
                conn=conn, surface="pipeline", pipeline_run_id=None,
                period_type="year", period=5, frequency_type="daily", frequency=1,
            )
        finally:
            conn.close()
        # note_provider drives the consecutive-fallback cooldown — it MUST see
        # the ladder's REAL routing outcome (whether Schwab actually answered),
        # so it is called with the original provider_tag BEFORE the helper
        # remaps provenance to the bars' source.
        state.note_provider(provider_tag)
        # Full-archive-return contract (Phase 16 Arc 3): on a schwab_api success
        # the short Schwab sub-window would truncate the ticker_detail / JIT
        # render for a short-listed ticker (XMAX). The shared helper re-reads the
        # full archive so this web hook converges with the pipeline hook + the
        # no-ladder path. Mirrors swing/pipeline/runner.py:_bars_hook.
        bars, effective_provider = resolve_full_archive_bars(
            ticker, window, provider_tag,
            yfinance_window_fn=_yf_window_fallback,
        )
        return (bars, effective_provider)

    price_cache.set_ladder_fetcher(_quote_hook)
    ohlcv_cache.set_ladder_bars_fetcher(_bars_hook)
    return client


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
    # Phase 9 T-A.5: post-schema-validation TOML divergence hook.
    # Per Codex R3 M#1 architectural fix (plan §A.5.1): swing/config.py:load()
    # REMAINS PURE — divergence reconciliation lives here, AFTER the DB has
    # been brought to v17 by run_server's connect() call (or the test's
    # ensure_schema fixture). When divergent, app.state.cfg is the corrected
    # immutable Config (frozen-dataclass replace; original cfg unchanged).
    # Pre-v17 / no-active-policy DBs silently return (cfg, None) — the helper
    # tolerates fresh / partially-migrated test fixtures without crashing.
    import sqlite3 as _sqlite3

    from swing.data.db import open_connection
    try:
        _conn = open_connection(cfg.paths.db_path, busy_timeout_ms=cfg.web.db_busy_timeout_ms)
    except _sqlite3.OperationalError:
        # DB path doesn't exist or can't be opened — defer to the connect()
        # gate at run_server / first request. Use raw cfg here so the app
        # can still construct (pre-migration test fixtures need this).
        app.state.cfg = cfg
    else:
        try:
            from swing.trades.risk_policy import (
                check_and_reconcile_toml_divergence,
            )
            new_cfg, divergence = check_and_reconcile_toml_divergence(_conn, cfg)
        finally:
            _conn.close()
        if divergence is not None:
            log.warning(
                "TOML diverges from risk_policy at web app startup: %s; "
                "app.state.cfg corrected to risk_policy value.",
                divergence,
            )
        app.state.cfg = new_cfg
    app.state.cfg_path = cfg_path
    # Phase 18 Arc 18-C: install the persistent surface='web' yfinance audit base
    # FROM the finalized app.state.cfg (post divergence reconciliation — Codex R7;
    # the audit base is long-lived provenance, so don't bake in a pre-correction
    # db_path). The web server is a single long-lived process, so a once-set base
    # tags every web-triggered yfinance call (live-price + chart archive reads)
    # without per-request scoping. NULL run id (web has no pipeline run).
    from swing.data.yfinance_audit_context import set_yfinance_audit_base_context
    set_yfinance_audit_base_context(
        db_path=app.state.cfg.paths.db_path, pipeline_run_id=None, surface="web",
    )
    app.state.price_cache = PriceCache(cfg)
    app.state.ohlcv_cache = OhlcvCache(cfg)     # NEW — Phase 3d §3.5
    app.state.schwab_client = _install_web_marketdata_caches(  # NEW -- A-3 / P14.N7
        cfg, app.state.price_cache, app.state.ohlcv_cache,
    )
    app.state.templates_dir = _templates_dir()
    app.state.templates = _build_templates(app.state.templates_dir)

    # Body-size guard FIRST (innermost on request path) — runs AFTER OriginGuard
    # on the request path because Starlette middleware is LIFO (earlier
    # add_middleware = more-inner = runs AFTER the outer middleware). This
    # preserves OriginGuard's 403-before-413 contract for strict mode.
    app.add_middleware(
        MaxBodySizeMiddleware,
        path_prefix="/pipeline/csv-upload",
        max_bytes=cfg.web.csv_upload_max_bytes,
    )
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

    install_logging(cfg, surface="web")
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
                    {
                        "error_message": exc.detail,
                        "colspan": _row_error_colspan(request),
                    },
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
            # HX-Target drives fragment shape regardless of method. A GET
            # validation error targeting a row (e.g. bad int path param on a
            # row-bound exit/stop form) must still render a <tr> fragment,
            # or HTMX would inject a <div> into a <table>. Spec §3.3.
            if _is_row_swap_target(request):
                return tpls.TemplateResponse(
                    request, "partials/trade_form_error.html.j2",
                    {
                        "error_message": f"Invalid input in {field}: {msg}",
                        "colspan": _row_error_colspan(request),
                    },
                    status_code=400,
                )
            return tpls.TemplateResponse(
                request, "partials/http_error_fragment.html.j2",
                {"status_code": 400, "detail": f"Invalid input in {field}: {msg}"},
                status_code=400,
            )

        # Non-HTMX GET with Accept: text/html → full-page HTML error.
        # Spec §3.3 precedence rule #2. API clients (Accept without text/html)
        # continue to the FastAPI default 422 JSON via fallthrough. Accept
        # media types are case-insensitive per RFC 7231.
        accept_header = request.headers.get("accept", "").lower()
        if request.method == "GET" and "text/html" in accept_header:
            from datetime import datetime

            from swing.evaluation.dates import PageKind, topbar_session_date
            from swing.web.view_models.error import PageErrorVM
            try:
                session_date = topbar_session_date(
                    PageKind.HISTORY_ANALYSIS, datetime.now()).isoformat()
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

    # Date-less chart redirect route MUST be registered BEFORE the /charts
    # StaticFiles mount: Starlette resolves routes in registration order, and
    # `app.mount("/charts", ...)` claims everything under /charts unless an
    # earlier-registered route matches first. Single-segment paths like
    # /charts/AAPL.png hit the dynamic handler; two-segment date-prefixed
    # paths (/charts/<date>/<ticker>.png) don't match the {ticker}.png param
    # template and correctly fall through to StaticFiles.
    from swing.web.routes import charts as charts_route
    app.include_router(charts_route.router)

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
        account as account_route,
    )
    from swing.web.routes import (
        config as config_route,
    )
    from swing.web.routes import (
        dashboard as dashboard_route,
    )
    from swing.web.routes import (
        health as health_route,
    )
    from swing.web.routes import (
        journal as journal_route,
    )
    from swing.web.routes import (
        metrics as metrics_route,
    )

    # Phase 13 T2.SB1 T-A.1.6 — `/patterns/*` group.
    from swing.web.routes import (
        patterns as patterns_route,
    )
    from swing.web.routes import (
        pipeline as pipeline_route,
    )
    from swing.web.routes import (
        recommendations as recommendations_route,
    )
    from swing.web.routes import (
        reconcile as reconcile_route,
    )
    from swing.web.routes import (
        schwab as schwab_route,
    )
    from swing.web.routes import (
        trades as trades_route,
    )
    from swing.web.routes import (
        watchlist as watchlist_route,
    )
    app.include_router(dashboard_route.router)
    app.include_router(watchlist_route.router)
    app.include_router(journal_route.router)
    app.include_router(pipeline_route.router)
    app.include_router(trades_route.router)
    app.include_router(recommendations_route.router)
    app.include_router(config_route.router)
    app.include_router(metrics_route.router)
    app.include_router(account_route.router)
    app.include_router(schwab_route.router)
    app.include_router(reconcile_route.router)
    app.include_router(patterns_route.router)
    app.include_router(health_route.router)

    return app
