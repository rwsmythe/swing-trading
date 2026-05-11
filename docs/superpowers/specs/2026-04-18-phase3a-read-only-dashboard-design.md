# Phase 3a — Read-Only Dashboard Design

**Date:** 2026-04-18
**Status:** Draft for review
**Scope (explicitly bounded — this is NOT the full Phase 3):** Build a localhost FastAPI + HTMX dashboard over the Phase 2 foundation. Read-only views (`/`, `/watchlist`, `/journal`, `/pipeline`) plus a single interactive action: a "Run now" button that triggers `run_pipeline` in a separate subprocess and polls progress. `/trades`, `/settings`, the dashboard force-clear button, CSV-upload form, and trade-action forms are explicitly DEFERRED to Phase 3b — they are named in the original Phase 3 request and their absence here is intentional, agreed during brainstorming. If you are reviewing this spec against the original Phase 3 request and see those items missing, that is by design: Phase 3 was split into 3a (ship the dashboard) and 3b (layer actions on top).

---

## 1. Why this split

Phase 2 shipped the full pipeline + CLI. The user now needs to **see** decisions, open positions, watchlist state, and journal stats without opening a terminal, parsing the static `briefing.html`, or running CLI commands. Phase 3a focuses on the highest-leverage read-only UX and the single most-used interaction (manual pipeline run). Trade-action forms and settings editing are intentionally deferred because they are additive on top of the same dashboard and don't block 3a's value.

**What 3a adds that 3b does not:**
- Live current prices on the dashboard (not just last-close snapshots from the pipeline).
- Per-trade advisory text ("Move stop to breakeven," "Trail 10MA") computed at render time from current price + `compute_all_suggestions`.
- Watchlist `last_close` / proximity-to-pivot awareness updated between pipeline runs.
- One-click "Run pipeline now" without opening a terminal.

**Explicitly deferred:**
- **To 3b:** trade entry/exit/stop-adjust forms, dashboard force-clear button, CSV-upload form for the pipeline page, settings editor, CSRF protection.
- **To 3c (potential):** per-run detail route (`/pipeline/runs/{id}`). The archived `briefing.html` already provides the per-run detail view statically (spec §6.4), so the dynamic version is not urgent.

---

## 2. Architecture

### 2.1 Package layout

All new code under `swing/web/`. The Phase 2 foundation — `swing.data.*`, `swing.pipeline.*`, `swing.trades.*`, `swing.rendering.*`, `swing.evaluation.*`, `swing.config` — is consumed **read-only** and is not modified.

```
swing/web/
├── app.py                  # FastAPI factory, static mount, router includes, lifespan hooks
├── cli_cmd.py              # invoked by `swing web` CLI subcommand
├── price_cache.py          # TTL cache + market-hours gate + shared executor + circuit breaker
├── middleware/
│   └── origin_guard.py     # HX-Request / Origin / Referer accepted-header matrix
├── routes/
│   ├── __init__.py
│   ├── dashboard.py        # GET /
│   ├── watchlist.py        # GET /watchlist, GET /watchlist/{ticker}/expand
│   ├── journal.py          # GET /journal (?period=week|month|quarter|ytd|all)
│   └── pipeline.py         # GET /pipeline, POST /pipeline/run, GET /pipeline/status/{id}, POST /prices/refresh
├── view_models/
│   ├── __init__.py
│   ├── dashboard.py        # build(cfg, cache) -> DashboardVM
│   ├── watchlist.py
│   ├── journal.py
│   └── pipeline.py
├── templates/
│   ├── base.html.j2
│   ├── dashboard.html.j2
│   ├── watchlist.html.j2
│   ├── journal.html.j2
│   ├── pipeline.html.j2
│   ├── error.html.j2
│   └── partials/
│       ├── status_strip.html.j2
│       ├── today_decisions.html.j2
│       ├── open_positions.html.j2
│       ├── watchlist_row.html.j2
│       ├── watchlist_expanded.html.j2
│       ├── pipeline_progress.html.j2
│       ├── prices_refresh_container.html.j2
│       ├── price_degraded_banner.html.j2   # circuit-breaker visibility
│       └── error_fragment.html.j2
└── static/
    ├── htmx.min.js         # vendored; HTMX 2.x
    └── app.css
```

### 2.2 Layering invariants (extend spec §2.4)

- `swing.web` is the only package that imports `fastapi`, `jinja2`, `uvicorn`, or HTMX-specific concerns.
- `swing.data.repos` remains the only package importing `sqlite3`. View models go through repos; they do not open DB connections directly.
- Route handlers are thin: parse request → call view-model builder → `TemplateResponse`. No business logic in routes.
- Templates format only. No computation.
- The `price_cache.PriceCache` is the single cross-request mutable state. All other state lives in SQLite.

### 2.3 Startup sequence (`swing web` CLI command)

`swing/cli.py` gains:

```python
@main.command("web")
@click.option("--host", default=None, help="Override [web].host from config")
@click.option("--port", type=int, default=None)
@click.option("--reload", is_flag=True, default=None, help="Enable auto-reload")
@click.pass_context
def web_cmd(ctx, host, port, reload):
    """Run the swing dashboard on localhost."""
    from swing.web.cli_cmd import run_server
    run_server(cfg=ctx.obj["config"], host=host, port=port, reload=reload)
```

`swing/web/cli_cmd.py::run_server`:
1. Verify DB via `connect(cfg.paths.db_path)` — fail fast with "Run: swing db-migrate" if schema mismatch.
2. Build app via `create_app(cfg)`:
   - `app.mount("/charts", StaticFiles(directory=cfg.paths.charts_dir))`
   - `app.mount("/static", StaticFiles(directory=_static_dir()))`
   - Instantiate `PriceCache(cfg)` on `app.state.price_cache`.
   - Include all four routers.
3. Resolve effective host/port/reload: CLI flags > `[web]` config > defaults.
4. `uvicorn.run(app, host=host, port=port, reload=reload, log_config=_uvicorn_log_config(cfg))`.

### 2.4 Binding + authentication

- Bind **127.0.0.1 only**. Binding to `0.0.0.0` or any non-loopback address is refused with a clear error at startup — the user can set `[web].host` in config, but any non-loopback value is rejected.
- **No authentication.** No CSRF tokens.
- **Origin check as CSRF defense-in-depth.** A cross-site `<form action="http://127.0.0.1:8080/pipeline/run" method="POST">` on a malicious page the user happens to be visiting CAN be submitted even without JS — the browser will POST to localhost from any origin. Middleware `swing/web/middleware/origin_guard.py` blocks state-changing requests that lack an acceptable same-origin indicator.

- **Accepted-header matrix (3a).** Every state-changing POST in 3a is dispatched by HTMX from the dashboard itself — no plain-HTML-form POSTs. The middleware accepts a request when ANY of the following is true:
  | Request signal | Accepted when | Why |
  |---|---|---|
  | `HX-Request: true` | always | HTMX sets this automatically; cross-origin form POSTs without JS do NOT (it is a custom header → triggers CORS preflight → preflight is refused by the server). |
  | `Origin: http://<bound host>:<port>` | header is present | Modern browsers always send `Origin` on cross-origin POSTs; absence-or-match is the valid same-origin case. |
  | `Referer` starts with `http://<bound host>:<port>/` | Origin is absent AND no HX-Request | Fallback for older user-agents — rare on localhost but cheap to check. |
  State-changing routes receiving a request that satisfies NONE of the above return `403 Forbidden`. This matrix is enforced for `POST /pipeline/run`, `POST /prices/refresh`, and `GET /pipeline/status/{id}` when called from HTMX (GET polling carries `HX-Request`; same-origin direct GETs from the address bar are allowed unconditionally for `GET` requests).
- **Plain HTML form POSTs are NOT supported in 3a.** 3b will extend `origin_guard` with CSRF token validation for the trade-action forms it introduces; 3a deliberately has no submit-form surface.
- Spec §2.4 invariant — DB outside Drive folder, code inside — is honored by reading `cfg.paths.db_path` and `cfg.paths.charts_dir`, which Phase 1 already resolved to `%USERPROFILE%/swing-data/`.

### 2.5 New config section

```toml
[web]
host = "127.0.0.1"
port = 8080
reload = false
price_cache_ttl_seconds = 120
price_fetch_timeout_seconds = 3
price_fetch_deadline_seconds = 6      # get_many overall deadline (defensive second cap)
max_concurrent_price_fetches = 8      # bound on shared price-fetch executor workers
circuit_breaker_cooldown_seconds = 60 # how long to stay in degraded mode after failure threshold
polling_interval_seconds = 2          # HTMX progress-polling interval
```

Loaded by `swing.config.load()` with dataclass defaults for backward compatibility (same pattern as Phase 2's `[near_trigger]`, `[stop_advisory]`).

### 2.6 New optional dependency extra

`pyproject.toml`:

```toml
[project.optional-dependencies]
web = [
    "fastapi>=0.115,<1.0",
    "uvicorn[standard]>=0.30,<1.0",
    "jinja2>=3.1,<4.0",
]
```

The `web` extra only adds the three web-stack packages. `yfinance` and `exchange_calendars` (required by `swing/web/price_cache.py`) are **already base dependencies** from Phase 1 — `yfinance` via `swing.prices.PriceFetcher`, `exchange_calendars` via `swing.evaluation.dates`. The web extra does not need to re-declare them. Base install (no extras) stays CLI-only.

Acceptance: `tests/web/test_phase2_regression.py::test_web_extra_is_truly_optional` verifies the base install works without `fastapi`/`uvicorn`/`jinja2`; a separate test `test_web_extra_install_starts_app` verifies the full `[web]` extra actually boots `create_app(cfg)` without additional missing imports.

---

## 3. Components

### 3.1 `swing/web/app.py`

```python
def create_app(cfg: Config) -> FastAPI:
    app = FastAPI(title="Swing Trading Dashboard", docs_url=None, redoc_url=None)
    app.state.cfg = cfg
    app.state.price_cache = PriceCache(cfg)
    app.state.templates = Jinja2Templates(directory=_templates_dir())
    app.mount("/charts", StaticFiles(directory=cfg.paths.charts_dir), name="charts")
    app.mount("/static", StaticFiles(directory=_static_dir()), name="static")
    _register_exception_handlers(app)
    app.include_router(dashboard.router)
    app.include_router(watchlist.router)
    app.include_router(journal.router)
    app.include_router(pipeline.router)
    return app
```

Factory pattern so tests can instantiate an isolated app per `TestClient(create_app(test_cfg))`.

### 3.2 `swing/web/price_cache.py`

```python
@dataclass(frozen=True)
class PriceSnapshot:
    ticker: str
    price: float
    asof: datetime          # when the price was fetched OR the last-close date
    is_stale: bool          # True if outside market hours OR fetch failed
    source: str             # "live" | "last_close" | "last_close_market_closed"


class PriceCache:
    def __init__(self, cfg: Config):
        self._cfg = cfg
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[PriceSnapshot, float]] = {}  # ticker -> (snap, monotonic_fetched_at)

    def get(self, ticker: str) -> PriceSnapshot: ...
    def get_many(self, tickers: Sequence[str], deadline_seconds: float) -> dict[str, PriceSnapshot]: ...
    def refresh_all(self, tickers: Iterable[str]) -> None: ...
    def clear(self) -> None: ...
    def market_hours_now(self) -> bool: ...     # NYSE calendar via exchange_calendars
```

`get(ticker)` logic (cache hit path is fast; miss path does network):
1. If cache hit within `ttl_seconds`, return cached snapshot.
2. If `market_hours_now()` is False, return `PriceSnapshot(source="last_close_market_closed", is_stale=True, price=<latest candidates.close>)` and cache it for the remaining-to-open window (effectively until next market open).
3. Else try `yfinance.Ticker(ticker).fast_info['last_price']` with per-ticker `timeout=cfg.web.price_fetch_timeout_seconds`. On success → cache + return `is_stale=False`.
4. On timeout / exception → fall back to latest `candidates.close` from the most recent `evaluation_runs` row for this ticker. Return `is_stale=True, source="last_close"`. Log at WARNING.

**`get_many(tickers, deadline_seconds)` — batch fetch with total-time bound** (adversarial review Round 1 Major 3). View-model builders use this, not `get()` in a loop:

```python
def get_many(self, tickers, deadline_seconds):
    # 1. Serve cache hits synchronously (no network).
    results, misses = self._split_cache_hits(tickers)
    if not misses:
        return results
    # 2. Dispatch misses in parallel, bounded by an OVERALL deadline.
    with ThreadPoolExecutor(max_workers=min(len(misses), 8)) as pool:
        futures = {pool.submit(self._fetch_one, t): t for t in misses}
        try:
            for future in as_completed(futures, timeout=deadline_seconds):
                ticker = futures[future]
                try:
                    results[ticker] = future.result(timeout=0)
                except Exception:
                    results[ticker] = self._fallback_snapshot(ticker)
        except TimeoutError:
            pass  # deadline hit
    # 3. Any ticker whose future did not complete → fallback.
    for ticker, future in futures.items():
        if ticker not in results:
            future.cancel()
            results[ticker] = self._fallback_snapshot(ticker)
    return results
```

**Why parallel rather than serial**: a serial loop of `get(ticker)` with a 3s per-ticker timeout degrades `GET /` latency to `O(N × 3s)` when yfinance is slow or timing out. With 8–12 tickers that is a 24–36 second page load. `get_many` dispatches all misses in parallel, so expected latency is `~max(per-ticker timeout) ≈ 3s`, not `N × 3s`.

**On the "deadline" — honest statement of the guarantee** (adversarial review Round 2 Major 2): Python's `ThreadPoolExecutor` cannot forcibly terminate in-progress threads. The `as_completed(..., timeout=deadline_seconds)` call only stops the *iterator*; submitted tasks whose calls are blocked inside yfinance / `requests.get()` continue to run until those libraries themselves return or raise. The pool's context-manager exit will wait for them. To prevent the request handler from blocking past the deadline, `get_many` must:
1. Use `executor = ThreadPoolExecutor(...)` WITHOUT a `with` block.
2. After `as_completed` timeout fires, mark missing tickers as `_fallback_snapshot(ticker)`.
3. Call `executor.shutdown(wait=False, cancel_futures=True)` (Python 3.9+) — cancels *queued* futures; in-flight futures are abandoned. They complete in the background and their results are garbage-collected.
4. **Leaked threads are tolerated in 3a.** Each is waiting on an HTTP socket with its own yfinance-level timeout; they terminate within at most that timeout even if abandoned. In a localhost single-user app, the worst case is a handful of zombie threads for the remainder of a 3-second window — negligible memory, no correctness impact.

The primary bound is thus the **yfinance-level per-ticker timeout**, which the implementation must pass through explicitly (via `yfinance.Ticker(t).fast_info` — internally uses `requests` with a `timeout` kwarg). The `deadline_seconds` passed to `get_many` is a second defensive cap for the case where yfinance ignores or mishandles its own timeout.

**Cross-request capacity protection** (Round 3 Major 1). A per-request `ThreadPoolExecutor` stacks threads under sustained upstream outage: 10 page loads × 8 workers during a yfinance timeout regression = 80 blocked threads. The cache therefore uses:

1. **A single shared executor** stored on `app.state.price_fetch_executor` with `max_workers=cfg.web.max_concurrent_price_fetches` (default 8). Lifecycle: created in `create_app`, shut down with `wait=False, cancel_futures=True` in the FastAPI lifespan shutdown hook — avoids leaked worker threads in tests or uvicorn reload cycles. `get_many` submits to this executor rather than creating its own. Excess submissions queue (bounded by workers); worst case is slow response, not unbounded thread growth.
2. **A circuit breaker — instance-scoped on `PriceCache`** (Round 4 Minor 2; NOT class-level, so multiple app instances in the same process — e.g. test matrix — are isolated). Instance attributes `self._failure_window: deque[bool]` (maxlen=20), `self._degraded_until: float | None` (monotonic timestamp). If failure fraction > 0.5 over the last 20 outcomes, `_degraded_until = monotonic() + cooldown`: all `get()` / `get_many()` calls skip live fetch entirely and return last-close `PriceSnapshot(is_stale=True, source="last_close")` until the cooldown expires. Success during cooldown expiry resets the window.
3. **Thread safety for breaker state** (Round 4 Minor 1): the SAME `self._lock` that guards `_cache` also guards `_failure_window` and `_degraded_until` — executor worker threads record outcomes and request threads read the degraded flag under the same lock. No separate synchronization primitive needed.
4. **Degraded-mode VM field** (Round 4 Minor 3): `DashboardVM` (and `WatchlistVM`) gain `price_source_degraded: bool` and `price_source_degraded_until: str | None` (ISO timestamp for display). Templates render a dedicated degraded-banner partial (`partials/price_degraded_banner.html.j2`) separately from the pipeline stale-banner (`stale_banner`). The two states are orthogonal and must not be conflated.

Two new `[web]` config fields: `max_concurrent_price_fetches` (default 8), `circuit_breaker_cooldown_seconds` (default 60).

### 3.3 `swing/web/view_models/<page>.py`

Each page has a `build(cfg, cache, **params) -> <Page>VM` function. It opens a DB connection, reads repos, calls the price cache for the active tickers, and returns a frozen dataclass. The template receives only the VM — no raw connection, no live objects.

**DashboardVM fields** — field names align with Phase 2's `BriefingInputs` (`swing/rendering/briefing.py`) so the dashboard and the static briefing share vocabulary. The original Phase 3 request called out `open_trade_advisories`, `watchlist_last_prices`, and `flag_tags` as the concrete fields to fill; the dashboard populates them at render time (the static briefing model stays empty per Phase 2 Appendix C — the briefing.html artifact is not regenerated by the dashboard).

**Type upgrade on the price maps** (vs BriefingInputs, Round 2 Minor 2): `BriefingInputs` types the price maps as `Mapping[str, float]` because the static briefing has no concept of staleness. The dashboard needs staleness for badge rendering, so its VM types them as `Mapping[str, PriceSnapshot]` — same field name, richer value type. Templates render `.price` for display and branch on `.is_stale` / `.source` for the "(stale)" badge.

```python
@dataclass(frozen=True)
class DashboardVM:
    generated_at: str
    session_date: str                       # action_session_for_run(now).isoformat()
    stale_banner: str | None                # non-None when last complete run is older than current session
    status_strip: StatusStripVM             # weather + account + last_pipeline tiles
    today_decisions: list[DecisionVM]
    open_trades: list[Trade]                # from Phase 2 repo dataclass, unchanged
    open_trade_advisories: Mapping[int, list[AdvisorySuggestionVM]]
                                            # keyed by trade_id; from compute_all_suggestions(trade, current_price, …)
    open_trade_last_prices: Mapping[str, PriceSnapshot]
                                            # keyed by ticker; carries is_stale + source for badge rendering
    watchlist_top5: list[WatchlistEntry]    # from Phase 2 repo dataclass
    watchlist_remaining_count: int
    watchlist_last_prices: Mapping[str, PriceSnapshot]
                                            # keyed by ticker; carries is_stale + source for badge rendering
    flag_tags: Mapping[str, tuple[str, ...]]
                                            # keyed by ticker; e.g. ("TT✓","VCP✓","A+"). Computed by joining
                                            # watchlist ticker → latest candidates.criteria results.
    candidates_by_ticker: Mapping[str, Candidate]
    prices_generated_at: str                # for "refreshed 45s ago" badge
    price_source_degraded: bool             # True during circuit-breaker cooldown
    price_source_degraded_until: str | None # ISO timestamp when degraded mode ends
```

`WatchlistVM` mirrors the same `watchlist_last_prices` + `flag_tags` naming. `JournalVM` and `PipelineVM` do not need live-price fields.

### 3.4 `swing/web/routes/*`

Each route module defines `router = APIRouter()` and 1–4 handlers. Handlers:

```python
@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    templates = request.app.state.templates
    vm = build_dashboard(cfg, cache)
    return templates.TemplateResponse("dashboard.html.j2", {"request": request, "vm": vm})
```

The `pipeline.py` router is the only one with non-trivial logic — see §4.4.

### 3.5 Templates

Jinja2 autoescape on. `base.html.j2` provides `<head>`, top-bar nav, and a `{% block content %}`. Each page template extends base and composes partials. Partials correspond 1:1 with HTMX swap targets so the wiring is straightforward.

Partial filenames:
- `status_strip.html.j2` — the three-tile top row with IDs `#weather-tile`, `#account-tile`, `#pipeline-tile`.
- `today_decisions.html.j2` — amber panel, wrapped in `<div id="today-decisions">`.
- `open_positions.html.j2` — table wrapped in `<div id="open-positions">`.
- `watchlist_row.html.j2` — one `<tr>` per row, with `hx-get="/watchlist/{ticker}/expand" hx-swap="outerHTML"`.
- `watchlist_expanded.html.j2` — expanded detail for one ticker.
- `pipeline_progress.html.j2` — swap-polled progress panel.
- `prices_refresh_container.html.j2` — contains `<div hx-swap-oob="true">` elements for each swap target.
- `error_fragment.html.j2` — inline error block for HTMX response bodies.
- `price_degraded_banner.html.j2` — surfaces circuit-breaker degraded mode; rendered separately from the pipeline-stale banner. The two states are orthogonal.

---

## 4. Data flow

### 4.1 Plain page load — `GET /`

1. Router handler reads `cfg` + `cache` from `request.app.state`.
2. Calls `build_dashboard(cfg, cache)`:
   - Opens DB connection.
   - Reads: latest `weather_runs` row for `action_session_for_run(now)`, all open `trades`, `daily_recommendations` WHERE `action_session_date = current_session`, latest `pipeline_runs` row, watchlist rows.
   - For each open position + each top-5 watchlist ticker: `cache.get(ticker)` populates lazily on first call per TTL window.
   - For each open position: `compute_all_suggestions(trade, current_price, ohlcv_summary, cfg)` using the cached price.
   - Computes `stale_banner`: if latest complete `pipeline_runs.action_session_date < current_session` → banner text per spec §5.3.
3. Returns frozen `DashboardVM`.
4. Handler returns `templates.TemplateResponse("dashboard.html.j2", {"request": request, "vm": vm})`.

### 4.2 Expanded watchlist row — `GET /watchlist/{ticker}/expand`

HTMX `hx-get` swap. Handler reads the `candidates` row for `ticker` in the latest `evaluation_runs`, the `watchlist` row, and `cache.get(ticker)`. Renders `partials/watchlist_expanded.html.j2` containing:

- 1–2-sentence narrative.
- Trend Template 8-check grid (pass/fail chips).
- VCP 10-check grid.
- `<img src="/charts/{data_asof}/{ticker}.png" onerror="...">` with an `onerror` handler that swaps in a "Chart unavailable" placeholder per spec §5.7 "Dashboard authority rule."
- Action-button placeholders — disabled in 3a, tooltip shows the equivalent CLI command ("Log entry: `swing trade entry --ticker AAPL ...`").

Response is the expanded `<tr>` replacing the collapsed one via `hx-swap="outerHTML"`.

### 4.3 Price refresh — `POST /prices/refresh`

Status-strip button has `hx-post="/prices/refresh" hx-swap="none"` and the response uses `hx-swap-oob` on multiple regions. Handler:

1. Collects active ticker set: current open positions + top-5 near-trigger watchlist tickers + SPY (for weather tile freshness reuse).
2. `cache.refresh_all(tickers)` — invalidates; the next `cache.get()` per ticker refetches.
3. Builds a fresh `DashboardVM`.
4. Renders `prices_refresh_container.html.j2`:

   ```html
   <div id="status-strip" hx-swap-oob="true">...</div>
   <div id="open-positions" hx-swap-oob="true">...</div>
   <div id="watchlist-top5" hx-swap-oob="true">...</div>
   ```

All three regions swap simultaneously in the browser.

### 4.4 "Run now" trigger flow

**`POST /pipeline/run`** — spawns a **subprocess**, not a daemon thread:

1. Handler checks `find_active_run(conn)`.
   - If an active run exists with fresh heartbeat → return `partials/pipeline_progress.html.j2` immediately with that run's id, so the UI shows the existing run's progress.
   - If active run exists with stale heartbeat → return an error fragment with the actual heartbeat age formatted at render time: `f"A previous run is stuck (run #{id}, state=running, heartbeat age {age_minutes}m). A dashboard force-clear button ships in Phase 3b; until then, run `swing pipeline force-clear {id} --bypass-staleness-check` in a terminal."` The fragment also includes a copy-to-clipboard button for the command to reduce CLI friction.
2. Otherwise spawn a detached subprocess.
   - **Signature** (Round 3 Minor 1): `create_app(cfg: Config, cfg_path: Path | None = None) -> FastAPI`. `cfg_path` is **optional in the signature** (allowing tests to instantiate the app without a config file) but **required at runtime for `POST /pipeline/run`**. At creation time `app.state.cfg_path = cfg_path`. When the CLI command `swing --config <path> web` starts the server, `cfg_path` is set from `ctx.obj["config_path"]`. When tests call `create_app(test_cfg)` without a file, `app.state.cfg_path is None`, and `POST /pipeline/run` short-circuits to a 503 response (see next bullet). Routes that do not need subprocess launch (all GETs, `POST /prices/refresh`) work regardless of `cfg_path`.
   - **When `cfg_path is None`**: `POST /pipeline/run` returns `503 Service Unavailable` with body: `"Pipeline subprocess launch requires a config-file-backed app startup. Configure via `swing --config <path> web`."`
   - **Spawn invocation**:
     ```python
     cmd = [sys.executable, "-m", "swing.cli",
            "--config", str(app.state.cfg_path),
            "pipeline", "run", "--manual"]
     log.info("spawning pipeline subprocess: %s", cmd)
     proc = subprocess.Popen(
         cmd, close_fds=True,
         stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
         start_new_session=True,
     )
     log.info("pipeline subprocess started: pid=%d", proc.pid)
     ```
   - **Detect immediate child-exit failures** (Round 3 Minor 2): while tight-looping `find_active_run(conn)` for up to 2s, also call `proc.poll()` on each iteration. If the child exits with non-None return code before the `pipeline_runs` row appears, return an error fragment with the exit code and point to `swing-data/logs/pipeline.log`. This catches early failures (missing dependency, invalid config path, import error) where Phase 2 logging never initialized.
   - **Rationale for subprocess over thread**: a daemon thread dies on uvicorn reload or process exit, orphaning the `pipeline_runs` row with `state='running'` (Round 1 Major 4). A subprocess decouples pipeline lifecycle from the web-server lifecycle.
   - **Rationale for `DEVNULL` redirects**: parent-opened file descriptors inherited to children on Windows can fail with sharing-violation errors. Phase 2's `swing.pipeline.runner` already uses `logging.getLogger(__name__)` writing to `swing-data/logs/pipeline.log`, so the child's real logging flows through that path. The cmd+pid log in the parent (above) plus `proc.poll()` detection covers the pre-init window.
   - Trade-off: ~1s subprocess-startup overhead is negligible vs pipeline runtime of several minutes.
3. Tight-loop `find_active_run(conn)` (up to 2s, 50ms sleep) to pick up the new row's id after the child acquires its lease. If still missing after 2s → return error fragment ("Pipeline subprocess did not acquire lease within 2s. Check `swing-data/logs/pipeline-run-*.log` and `swing-data/logs/web.log`.").
4. Return `partials/pipeline_progress.html.j2` with `hx-get="/pipeline/status/{run_id}" hx-trigger="every 2s" hx-swap="outerHTML"`.

**`GET /pipeline/status/{run_id}`**:

1. Reads `find_run(conn, run_id)`.
2. If run is missing → render terminal error.
3. If `state == 'running'` → render progress bar showing `current_step` (e.g., "Step 4/9: Evaluate — 32/62 tickers scored") and per-step status icons for completed steps. Response keeps the `hx-get` / `hx-trigger="every 2s"` on the outer `<div>` so polling continues.
4. If `state IN ('complete','failed','blocked','force_cleared')` → render the terminal panel WITHOUT `hx-trigger` (polling stops). Include `hx-swap-oob` for the status strip's "Last pipeline" tile so the rest of the dashboard updates.

Polling interval comes from `cfg.web.polling_interval_seconds` (default 2). Outside an active run, no polling occurs — the progress partial exists only after the button is clicked.

### 4.5 Navigation model

- Each page has a unique URL; back/forward buttons work.
- Cross-page navigation is full reload (plain `<a href="...">` links in the top bar).
- Within-page HTMX is fragment-swap only (no `pushState` manipulation).
- Journal period selector is a set of plain GET links: `<a href="/journal?period=week">Week</a>`.

---

## 5. Error handling

### 5.1 Failure-origin table

| Failure origin | Who catches | User-visible outcome |
|---|---|---|
| DB unavailable / schema mismatch | `connect()` raises `SchemaVersionMismatchError` at app startup | App doesn't start; `swing web` prints "Run: swing db-migrate" and exits 1 |
| Port already in use | `uvicorn.run()` raises `OSError` | `swing web` prints "Port {port} busy. Set `[web].port` or pass --port." exits 1 |
| Repo/DB exception mid-request | FastAPI exception handler | 500 page via `error.html.j2` showing exception summary + "Check `swing-data/logs/web.log` (request id X)" |
| Price-cache fetch timeout / yfinance error | Caught **inside** `PriceCache.get()` | Returns `PriceSnapshot(is_stale=True, source="last_close")`. Template shows "(stale)" badge. Never propagates. |
| Market closed (no live prices) | `market_hours_now()` gate | Returns `is_stale=True, source="last_close_market_closed"`. Template shows "Last close: Fri Apr 17" badge. Not an error. |
| Pipeline thread fails to spawn | `POST /pipeline/run` try/except | HTMX response is `error_fragment.html.j2` swapped into `#run-panel`; user stays on page; full traceback logged |
| Pipeline itself fails mid-run | The thread's `run_pipeline` writes `state='failed'` to `pipeline_runs` | Next HTMX poll sees `state='failed'`, renders terminal-failure panel with `error_message`. No live exception surface. |
| Chart PNG missing on disk | Browser `<img>` 404 | `onerror` swaps in `<div class="chart-unavailable">Chart unavailable — pipeline may not have completed this session.</div>`. Matches spec §5.7 "Dashboard authority rule." |
| Config missing `[web]` section | Dataclass defaults apply | Silent OK; dashboard starts on defaults |

### 5.2 Structured logging

- One log file: `%USERPROFILE%/swing-data/logs/web.log`, daily-rotated via `TimedRotatingFileHandler`, 7-day retention.
- Request middleware emits `[<ts>] <method> <path> <status> <duration_ms> <request_id>` per request.
- Exceptions log full traceback at `ERROR`. `request_id` (uuid4) attached to both the log line and the error page body.
- Uvicorn's access log is disabled (replaced by middleware logging) to avoid duplicate lines.

### 5.3 Stale-banner policy (reused from spec §5.3)

Dashboard's status strip renders a top-of-page amber banner when the most recent complete `pipeline_runs.action_session_date < action_session_for_run(now)`:

> "Last pipeline: Fri Apr 17 — decisions below are for session Mon Apr 20. Run pipeline for Tue Apr 21."

The banner's "Run now" button is the same `POST /pipeline/run` flow described in §4.4.

### 5.4 Concurrent browser tabs (explicitly supported)

Multiple tabs of the dashboard open against the same server is a normal case, not a limitation:
- **Reads** — all GET routes are read-only against SQLite (Phase 2's WAL-mode reader-writer isolation) plus the in-process `PriceCache` (guarded by `threading.Lock`). N concurrent GETs from N tabs work correctly.
- **`POST /prices/refresh`** — `cache.refresh_all(...)` + subsequent `get_many` is idempotent; concurrent calls may each refresh, but the result is the same.
- **`POST /pipeline/run`** — the check-then-spawn race is already mitigated by `acquire_lease`'s `ConcurrentRunBlockedError` (Phase 2's partial unique index `ux_pipeline_one_running` is the DB-level authoritative gate). The loser tab sees "Pipeline already running" and polls the existing run's progress.

### 5.5 NYSE-only assumption (documented)

`price_cache.market_hours_now()` uses the NYSE calendar from `exchange_calendars`. This is correct for the current universe (S&P 500 + NASDAQ-100 — all NYSE/NASDAQ listed; NASDAQ follows NYSE-equivalent regular session windows). If the tool is ever extended to international tickers, ETFs with half-day schedules, or futures, the "stale / live" badge will be wrong outside those instruments' hours. Non-US expansion is not in any phase of the current plan.

### 5.6 What 3a explicitly does NOT handle

- **Authentication failures** — no auth exists.
- **CSRF tokens** — not used; the Origin/HX-Request header check (§2.4) is the defense-in-depth layer.
- **Cross-site resource loading** — all JS/CSS/charts are same-origin.

---

## 6. Testing

### 6.1 Test tiers and counts

| Tier | Coverage | Tool | Target |
|---|---|---|---|
| View-model unit tests | Pure data → dataclass shape; no I/O | `pytest` with fixture seed | ~12 |
| Price cache unit tests | TTL, market-hours gate, timeout fallback, refresh_all | `pytest` + monkeypatched `yfinance.Ticker` + frozen clock | ~8 |
| Route smoke tests | 200 response, template renders, expected snippets in body | `fastapi.testclient.TestClient` + seeded SQLite | ~10 |
| HTMX interaction tests | `hx-swap-oob` markup on POST /prices/refresh; progress partial advances | TestClient + BeautifulSoup or string matching | ~5 |
| Pipeline trigger integration | POST /pipeline/run spawns thread, status polls, terminal state surfaces | TestClient + monkeypatched `PriceFetcher.get` | ~3 |

Total target: **~38 new tests**. Combined with Phase 2's 287 fast + 3 new slow = **~325 fast + 3 slow** after 3a.

### 6.2 Directory layout

```
tests/web/
├── conftest.py
├── test_price_cache.py
├── test_view_models/
│   ├── test_dashboard.py
│   ├── test_watchlist.py
│   ├── test_journal.py
│   └── test_pipeline.py
├── test_routes/
│   ├── test_dashboard_route.py
│   ├── test_watchlist_route.py
│   ├── test_journal_route.py
│   └── test_pipeline_route.py
├── test_htmx_interactions.py
└── test_phase2_regression.py      # import graph: confirm base install still works
```

### 6.3 Shared fixtures (`tests/web/conftest.py`)

- `test_cfg(tmp_path)` — reuses Phase 1's `_minimal_config` + adds a `[web]` section; DB and charts_dir under `tmp_path`.
- `seeded_db(test_cfg)` — applies schema, seeds one completed `pipeline_runs`, one `evaluation_runs` with ~5 candidates across buckets, one watchlist row, one open `trades` row, one `weather_runs`.
- `client(test_cfg, seeded_db)` — returns `TestClient(create_app(test_cfg))`.

### 6.4 Security-posture tests

- `test_cli_cmd.py::test_refuses_non_loopback_host` — asserts `run_server(cfg=..., host="0.0.0.0", ...)` exits with a clear error and never calls `uvicorn.run`.
- `test_origin_guard.py::test_cross_origin_post_blocked` — `TestClient` POSTs to `/pipeline/run` with an `Origin: http://evil.example` header and no `HX-Request`; asserts 403.
- `test_origin_guard.py::test_htmx_post_allowed` — same POST with `HX-Request: true`; asserts spawn succeeds (monkeypatched).
- `test_origin_guard.py::test_same_origin_form_post_allowed` — `Origin: http://127.0.0.1:8080`; asserts 200.

### 6.5 Explicitly out of scope

- Browser end-to-end tests (Playwright/Selenium) — spec §7.4 scoped out for Phase 2; same applies to 3a.
- Visual regression / pixel-perfect template checks — verify HTML structure, not appearance.
- Real yfinance network calls — every test monkeypatches.
- UI accessibility audits — manual-review scope.

### 6.6 Performance expectations (documented, not asserted)

- `GET /` with warm price cache should render in <200ms on the user's machine. If it doesn't, the view-model builder is the suspect — usually `compute_all_suggestions` doing redundant work or a cache miss cascade.
- Pipeline-progress polling adds 1 request / 2s while a run is active. Outside polling, zero background network.

---

## 7. Out of scope (deferred to later)

- **Phase 3b**: trade-action forms (entry/exit/stop-adjust), dashboard force-clear button, CSV-upload form, settings editor, CSRF.
- **Phase 3c (potential)**: per-run detail route (`/pipeline/runs/{id}` — HTML equivalent of archived briefing.html), run comparison views, search across history.
- **Phase 4**: legacy data import, folder archival, delete legacy `.py` files, create `scripts/run-pipeline.bat`.
- **Not in any phase**: multi-user support, authentication, remote hosting, mobile UX, backtesting.

---

## 8. Decisions locked during brainstorming

1. **Phase 3 is split into 3a (this spec) and 3b.** 3a ships read-only + Run now; 3b ships interactive forms.
2. **Run now is in 3a.** CSV upload stays CLI until 3b.
3. **Live-price cache is lazy with TTL** — 2 minutes during market hours, fall-back-to-last-close outside hours or on fetch failure. 3-second per-ticker fetch timeout.
4. **Market-hours detection uses `exchange_calendars` NYSE** — already in Phase 1 dependencies.
5. **Pipeline progress uses HTMX polling** against the existing `pipeline_runs` table — no SSE, no WebSockets, no in-memory pipeline state.
6. **Charts served via `StaticFiles`** mount of `cfg.paths.charts_dir` — browser caches, missing charts handled by `<img onerror>`.
7. **Startup via `swing web` CLI command** calling `uvicorn.run()` — not via a standalone `.bat` file. `scripts/run-web.bat` becomes a one-line wrapper.
8. **127.0.0.1 bind only, no authentication, no CSRF** — single-user localhost, matches spec §2.4 invariant.
9. **No per-run detail route in 3a** — archived `briefing.html` is the existing static equivalent.
10. **`web` optional extra** in `pyproject.toml` — base install stays CLI-only.

---

## 9. Success criteria

- [ ] `pip install -e ".[web]" && swing db-migrate && swing web` starts a dashboard on http://127.0.0.1:8080.
- [ ] `GET /` renders with correct stale-banner behavior across (today's session done, yesterday's session done, mid-week) date scenarios.
- [ ] Open positions display `R-so-far` using live price + advisory text from `compute_all_suggestions`.
- [ ] Watchlist top-5 rows show proximity-to-pivot with live prices during market hours, last-close with "(stale)" badge outside.
- [ ] Expanded watchlist row (HTMX swap) renders narrative, TT grid, VCP grid, and chart image.
- [ ] `GET /watchlist` lists all watchlist entries; `GET /journal?period=<p>` renders stats + trade table per selected period.
- [ ] `POST /pipeline/run` spawns a background pipeline; HTMX polls `GET /pipeline/status/{id}` every 2s; terminal state stops polling and refreshes the status-strip pipeline tile.
- [ ] Clicking "Refresh prices" invalidates cache and updates three regions via `hx-swap-oob`.
- [ ] `POST /pipeline/run` blocked by `ConcurrentRunBlockedError` surfaces a "Pipeline already running" panel instead of attempting a second run.
- [ ] Full Phase 2 fast test suite still green (287 tests). ~38 new tests for `swing.web` all pass.
- [ ] Base install (without the `web` extra) still starts the CLI without ImportError.

---

## 10. Appendix — HTMX quick reference for this spec

- `hx-get="<url>"` + `hx-swap="outerHTML"` — replaces the element with the response HTML.
- `hx-trigger="every Ns"` — repeatedly fires the request every N seconds until the element is replaced by a response without `hx-trigger`.
- `hx-swap="none"` + response uses `hx-swap-oob="true"` on any element with an id matching the DOM — "out-of-band" swap; replaces the id-matched element regardless of hx-target.
- `hx-post="<url>"` — POST request; response swapped per `hx-swap`.
- `hx-target="#selector"` — where the response HTML goes (default is the source element).
