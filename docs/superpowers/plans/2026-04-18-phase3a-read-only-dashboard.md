# Phase 3a Read-Only Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a localhost FastAPI + HTMX dashboard over the Phase 2 foundation: four read-only routes (`/`, `/watchlist`, `/journal`, `/pipeline`) plus a "Run now" button that launches the pipeline as a subprocess and polls progress via HTMX.

**Architecture:** New `swing/web/` package consumed via `swing web` CLI subcommand. Routes are thin handlers that call page-specific view-model builders; view-models read Phase 2 repos + a lazy TTL price cache with circuit breaker. Templates are Jinja2 partials that HTMX swaps. All cross-request state is either SQLite (pipeline_runs, candidates, etc.) or the `PriceCache` instance on `app.state`. No authentication; Origin/HX-Request guard is the defense-in-depth layer for CSRF.

**Tech Stack:** FastAPI, Uvicorn, Jinja2, HTMX 2.x (vendored). yfinance and exchange_calendars are reused from Phase 1 base install. Tests via `fastapi.testclient.TestClient` + existing pytest harness.

---

## File Structure

### Production code (all new unless noted)

```
swing/web/
├── __init__.py                   # empty marker
├── app.py                        # create_app(cfg, cfg_path) -> FastAPI; lifespan; middleware
├── cli_cmd.py                    # run_server(cfg, host, port, reload) — called by `swing web`
├── price_cache.py                # PriceSnapshot, PriceCache (get, get_many, circuit breaker)
├── middleware/
│   ├── __init__.py
│   └── origin_guard.py           # HX-Request / Origin / Referer accepted-header matrix
├── routes/
│   ├── __init__.py
│   ├── dashboard.py              # GET /
│   ├── watchlist.py              # GET /watchlist, GET /watchlist/{ticker}/expand
│   ├── journal.py                # GET /journal (?period=…)
│   └── pipeline.py               # GET /pipeline, POST /pipeline/run, GET /pipeline/status/{id}, POST /prices/refresh
├── view_models/
│   ├── __init__.py
│   ├── dashboard.py              # DashboardVM + build(cfg, cache) -> DashboardVM
│   ├── watchlist.py              # WatchlistVM + expand helper
│   ├── journal.py                # JournalVM + period filter
│   └── pipeline.py               # PipelineVM + progress helper
├── templates/
│   ├── base.html.j2
│   ├── dashboard.html.j2
│   ├── watchlist.html.j2
│   ├── journal.html.j2
│   ├── pipeline.html.j2
│   ├── error.html.j2
│   └── partials/
│       ├── status_strip.html.j2
│       ├── stale_banner.html.j2
│       ├── price_degraded_banner.html.j2
│       ├── today_decisions.html.j2
│       ├── open_positions.html.j2
│       ├── watchlist_row.html.j2
│       ├── watchlist_expanded.html.j2
│       ├── pipeline_progress.html.j2
│       ├── prices_refresh_container.html.j2
│       └── error_fragment.html.j2
└── static/
    ├── htmx.min.js               # vendored HTMX 2.x
    └── app.css
```

### Modified existing files

- `swing/config.py` — add `@dataclass Web` + `web: Web` field on `Config`; parse `[web]` section with defaults.
- `swing/cli.py` — add `@main.command("web")` that forwards to `swing.web.cli_cmd.run_server`.
- `pyproject.toml` — add `[project.optional-dependencies].web = ["fastapi>=0.115,<1.0", "uvicorn[standard]>=0.30,<1.0", "jinja2>=3.1,<4.0"]`.

### New tests

```
tests/web/
├── __init__.py
├── conftest.py                   # test_cfg, seeded_db, client, cfg_path, http_headers_same_origin
├── test_config_web.py            # [web] section parsing + defaults
├── test_app_smoke.py             # create_app boots, app.state wired, static mounts resolve
├── test_origin_guard.py          # 5 tests: HX allow, Origin allow, Referer fallback, cross-origin block, non-loopback refuse
├── test_price_cache.py           # ~9 tests: TTL, market-hours, timeout, refresh_all, circuit-breaker + cooldown, instance-scoped breaker
├── test_cli_cmd.py               # loopback enforcement, port-busy error, CLI flag overrides
├── test_view_models/
│   ├── __init__.py
│   ├── test_dashboard.py
│   ├── test_watchlist.py
│   ├── test_journal.py
│   └── test_pipeline.py
├── test_routes/
│   ├── __init__.py
│   ├── test_dashboard_route.py
│   ├── test_watchlist_route.py
│   ├── test_journal_route.py
│   └── test_pipeline_route.py    # GET /pipeline + POST /pipeline/run + GET /pipeline/status/{id} + POST /prices/refresh
├── test_htmx_interactions.py     # oob swap markup, polling partial advance, refresh-prices three-region swap
├── test_error_handling.py        # 500 page, request_id middleware, error_fragment
├── test_phase2_regression.py     # web extra optional in both directions
└── test_dashboard_integration.py # full flow: seeded DB + mocked price fetch, stale-banner scenarios
```

**Target test count:** ~55 new. Breakdown by task: T1=2, T3=2, T4=6, T5=4, T6=5 (including refresh_all), T7=3, T8=4, T9=1, T11=1, T13=1, T14=3, T15=5, T16=1, T17=4, T18=3, T19=1, T20=4 (including 403-with-request-id), T21=4 (added CLI-without-web-stack coverage), T22=3. The spec target of ~38 was a rough early estimate; adversarial-review fixes added ~15 tests. Combined with Phase 2's 287 fast tests, expected total is **~342 fast tests** (R1 Minor 4 — recounted from the plan).

---

## Task Ordering Rationale

1. **Config + deps first** (T1, T2) — unlocks everything else.
2. **Package skeleton + smoke** (T3) — create_app returns a valid FastAPI instance; no routes yet.
3. **Origin guard** (T4) — small, testable in isolation; needed by every POST route.
4. **PriceCache** (T5, T6, T7) — leaf dependency for view-models. Start with `get()`, then `get_many()` + breaker, then app-state wiring.
5. **CLI + run_server** (T8) — only now does `swing web` start serving.
6. **Dashboard page** (T9, T10, T11) — proves the view-model → template → route pattern end to end.
7. **Static assets** (T12) — so `/static/htmx.min.js` resolves.
8. **Watchlist page** (T13, T14) — adds HTMX `expand` interaction.
9. **Journal page** (T15) — simpler: plain GET with period param.
10. **Pipeline page + Run now + status polling** (T16, T17, T18) — highest complexity, lands after all supporting infra is in place.
11. **Prices refresh + degraded banner** (T19) — three-region oob swap.
12. **Error handling + logging** (T20) — cross-cutting; lands once every surface is in place.
13. **Regression tests** (T21) — base install + web extra both work.
14. **Integration smoke** (T22) — end-to-end GET / against seeded DB.

---

## Task 1: Add `[web]` config section and `Web` dataclass

**Files:**
- Modify: `swing/config.py`
- Test: `tests/web/test_config_web.py`

Extends the existing Phase 2 pattern of optional sections (`[near_trigger]`, `[stop_advisory]`, `[sizing]`, `[pipeline]`, `[export]`) with dataclass defaults. `[web]` section is fully optional — omitting it yields all defaults.

- [ ] **Step 1: Write the failing test**

Create `tests/web/__init__.py` (empty file) and then:

```python
# tests/web/test_config_web.py
"""Web config section parses with defaults + partial overrides."""
from __future__ import annotations

from pathlib import Path

from swing.config import Web, load


def _write_cfg(project_dir: Path, home_dir: Path, *, extra: str = "") -> Path:
    cfg = project_dir / "swing.config.toml"
    cfg.write_text(
        f"""[paths]
db_path = "{(home_dir / 'swing.db').as_posix()}"
data_dir = "{home_dir.as_posix()}"
logs_dir = "{(home_dir / 'logs').as_posix()}"
charts_dir = "{(home_dir / 'charts').as_posix()}"
backups_dir = "{(home_dir / 'backups').as_posix()}"
prices_cache_dir = "{(home_dir / 'prices').as_posix()}"
finviz_inbox_dir = "data/finviz-inbox"
exports_dir = "exports"
rs_universe_path = "reference/rs-universe.csv"

[account]
starting_equity = 1000.0
starting_date = "2026-01-01"
risk_equity_floor = 5000.0

[position_limits]
soft_warn_open = 4
hard_cap_open = 6

[risk]
max_risk_pct = 0.005

[vcp]
prior_trend_min_pct = 25.0
adr_min_pct = 4.0
pullback_max_pct = 25.0
proximity_max_pct = 5.0
tightness_days_required = 2
tightness_range_factor = 0.67
orderliness_max_bar_ratio = 3.0
orderliness_max_range_cv = 0.60

[trend_template]
min_passes = 7
allowed_miss_names = ["TT8_rs_rank"]
rising_ma_period_days = 21
high_52w_margin_pct = 25.0
low_52w_min_pct = 30.0

[rs]
horizon_weeks = 12
benchmark_ticker = "SPY"
rs_rank_min_pass = 70
fallback_extreme_pct = 20.0

[etf_exclusion]
exclude_etfs = true
manual_block = []
manual_allow = []

[focus_ranking]
closeness_to_pivot = 0.50
adr = 0.25
prior_trend = 0.25
{extra}
""",
        encoding="utf-8",
    )
    (project_dir / "reference").mkdir(exist_ok=True)
    (project_dir / "reference" / "rs-universe.csv").write_text(
        "# version: test-v1\n# source: test\n# columns: ticker\nticker\nAAPL\n",
        encoding="utf-8",
    )
    return cfg


def test_web_defaults_when_section_absent(tmp_path: Path):
    cfg_path = _write_cfg(tmp_path / "project", tmp_path / "home")
    (tmp_path / "project").mkdir(exist_ok=True)
    cfg_path = _write_cfg(tmp_path / "project", tmp_path / "home")
    cfg = load(cfg_path)
    assert isinstance(cfg.web, Web)
    assert cfg.web.host == "127.0.0.1"
    assert cfg.web.port == 8080
    assert cfg.web.reload is False
    assert cfg.web.price_cache_ttl_seconds == 120
    assert cfg.web.price_fetch_timeout_seconds == 3
    assert cfg.web.price_fetch_deadline_seconds == 6
    assert cfg.web.max_concurrent_price_fetches == 8
    assert cfg.web.circuit_breaker_cooldown_seconds == 60
    assert cfg.web.polling_interval_seconds == 2


def test_web_partial_override(tmp_path: Path):
    (tmp_path / "project").mkdir(exist_ok=True)
    cfg_path = _write_cfg(
        tmp_path / "project", tmp_path / "home",
        extra='[web]\nport = 9090\nreload = true\n',
    )
    cfg = load(cfg_path)
    assert cfg.web.port == 9090
    assert cfg.web.reload is True
    # Unspecified fields still at default
    assert cfg.web.host == "127.0.0.1"
    assert cfg.web.price_cache_ttl_seconds == 120
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/web/test_config_web.py -v`
Expected: `ImportError: cannot import name 'Web' from 'swing.config'`

- [ ] **Step 3: Add the `Web` dataclass to `swing/config.py`**

Insert AFTER the existing `@dataclass class ExportConfig` block (around line 125):

```python
@dataclass(frozen=True)
class Web:
    host: str = "127.0.0.1"
    port: int = 8080
    reload: bool = False
    price_cache_ttl_seconds: int = 120
    price_fetch_timeout_seconds: int = 3
    price_fetch_deadline_seconds: int = 6
    max_concurrent_price_fetches: int = 8
    circuit_breaker_cooldown_seconds: int = 60
    polling_interval_seconds: int = 2
```

Add `web: Web` to the `Config` dataclass (after `export: ExportConfig`). Use `field(default_factory=Web)` so `Config(...)` constructors that omit `web` (existing Phase 2 test utilities or `dataclasses.replace(cfg, ...)` calls) continue to work — the field default is a fresh `Web()` (R1 Minor 2):

```python
from dataclasses import field   # already imported in Phase 2 config.py

    pipeline: PipelineConfig
    export: ExportConfig
    web: Web = field(default_factory=Web)
```

In the `load()` function, after the `export=ExportConfig(**raw.get("export", {}))` line, add:

```python
        web=Web(**raw.get("web", {})),
```

- [ ] **Step 4: Run test**

Run: `python -m pytest tests/web/test_config_web.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/config.py tests/web/__init__.py tests/web/test_config_web.py
git commit -m "feat(config): add [web] section with dataclass defaults"
```

---

## Task 2: Add `web` optional dependency extra to `pyproject.toml`

**Files:**
- Modify: `pyproject.toml`
- Test: manual install + import check

Base install stays CLI-only. `pip install -e ".[web]"` pulls in FastAPI/uvicorn/jinja2. `yfinance` and `exchange_calendars` are already base dependencies from Phase 1.

- [ ] **Step 1: Inspect current `pyproject.toml`**

```bash
grep -n "optional-dependencies" pyproject.toml || echo "NOT PRESENT"
```

- [ ] **Step 2: Add the `web` extra**

Append to `pyproject.toml` (before any trailing sections like `[build-system]`):

```toml
[project.optional-dependencies]
web = [
    "fastapi>=0.115,<1.0",
    "uvicorn[standard]>=0.30,<1.0",
    "jinja2>=3.1,<4.0",
]
```

If `[project.optional-dependencies]` already exists (e.g., a `charts` extra from Phase 2 Appendix B), add the `web = [...]` entry under that table instead of creating a new one.

- [ ] **Step 3: Install the extra**

Run: `pip install -e ".[web]"`
Expected: installs fastapi, uvicorn, jinja2, plus Starlette/h11/etc. transitively; no errors.

- [ ] **Step 4: Verify the imports succeed**

Run:
```bash
python -c "import fastapi, uvicorn, jinja2; print(fastapi.__version__, uvicorn.__version__, jinja2.__version__)"
```
Expected: three version strings, no traceback.

- [ ] **Step 5: Commit**

```bash
git add pyproject.toml
git commit -m "build: add [web] optional-dependencies extra (fastapi, uvicorn, jinja2)"
```

---

## Task 3: Package skeleton + `create_app` factory stub + smoke test

**Files:**
- Create: `swing/web/__init__.py` (empty)
- Create: `swing/web/app.py`
- Create: `swing/web/cli_cmd.py` (stub)
- Create: `swing/web/middleware/__init__.py` (empty)
- Create: `swing/web/routes/__init__.py` (empty)
- Create: `swing/web/view_models/__init__.py` (empty)
- Create: `swing/web/static/app.css` (empty placeholder)
- Create: `tests/web/conftest.py`
- Test: `tests/web/test_app_smoke.py`

Builds the empty scaffold so imports resolve. No routes yet. `create_app(cfg, cfg_path=None)` returns a FastAPI instance with `app.state.cfg` and `app.state.cfg_path` set.

- [ ] **Step 1: Create empty package markers**

```bash
mkdir -p swing/web/middleware swing/web/routes swing/web/view_models swing/web/templates/partials swing/web/static tests/web/test_view_models tests/web/test_routes
: > swing/web/__init__.py
: > swing/web/middleware/__init__.py
: > swing/web/routes/__init__.py
: > swing/web/view_models/__init__.py
: > tests/web/test_view_models/__init__.py
: > tests/web/test_routes/__init__.py
: > swing/web/static/app.css
```

- [ ] **Step 2: Create `swing/web/app.py` with minimal `create_app`**

```python
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
```

- [ ] **Step 3: Create `swing/web/cli_cmd.py` stub**

```python
"""`swing web` backing entry point. Populated in Task 8."""
from __future__ import annotations

from pathlib import Path

from swing.config import Config


def run_server(
    *, cfg: Config, cfg_path: Path | None = None,
    host: str | None = None, port: int | None = None,
    reload: bool | None = None,
) -> None:
    raise NotImplementedError("filled in by Task 8")
```

- [ ] **Step 4: Create `tests/web/conftest.py`**

```python
"""Shared fixtures for Phase 3a web tests."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.config import Config, load
from swing.data.db import ensure_schema


@pytest.fixture
def test_cfg(tmp_path: Path) -> tuple[Config, Path]:
    """Return (cfg, cfg_path) for a fresh test project."""
    from tests.cli.test_cli_eval import _minimal_config
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _minimal_config(project, home)
    cfg = load(cfg_path)
    return cfg, cfg_path


@pytest.fixture
def seeded_db(test_cfg) -> tuple[Config, Path]:
    """Ensure schema is applied; return (cfg, cfg_path). Subtests may seed rows."""
    cfg, cfg_path = test_cfg
    ensure_schema(cfg.paths.db_path).close()
    return cfg, cfg_path
```

- [ ] **Step 5: Write the failing smoke test**

```python
# tests/web/test_app_smoke.py
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
```

- [ ] **Step 6: Run the smoke test**

Run: `python -m pytest tests/web/test_app_smoke.py -v`
Expected: 2 PASS.

- [ ] **Step 7: Commit**

```bash
git add swing/web tests/web
git commit -m "feat(web): package skeleton + create_app factory"
```

---

## Task 4: Origin/HX-Request guard middleware

**Files:**
- Create: `swing/web/middleware/origin_guard.py`
- Test: `tests/web/test_origin_guard.py`

Enforces the accepted-header matrix from spec §2.4: state-changing requests require `HX-Request: true` OR `Origin == http://<bound>:<port>` OR `Referer` startswith that URL. GETs are always allowed. Non-matching → 403.

- [ ] **Step 1: Write the failing test**

```python
# tests/web/test_origin_guard.py
"""Origin / HX-Request / Referer accepted-header matrix."""
from __future__ import annotations

from fastapi import FastAPI, APIRouter
from fastapi.testclient import TestClient

from swing.web.middleware.origin_guard import OriginGuardMiddleware


def _app_with_test_route(bound_host: str = "127.0.0.1", bound_port: int = 8080) -> FastAPI:
    app = FastAPI()
    app.add_middleware(OriginGuardMiddleware, bound_host=bound_host, bound_port=bound_port)

    router = APIRouter()

    @router.get("/ping")
    def ping():
        return {"ok": True}

    @router.post("/action")
    def action():
        return {"ok": True}

    app.include_router(router)
    return app


def test_get_always_allowed_no_headers():
    client = TestClient(_app_with_test_route())
    r = client.get("/ping")
    assert r.status_code == 200


def test_post_with_hx_request_header_allowed():
    client = TestClient(_app_with_test_route())
    r = client.post("/action", headers={"HX-Request": "true"})
    assert r.status_code == 200


def test_post_with_same_origin_allowed():
    client = TestClient(_app_with_test_route())
    r = client.post("/action", headers={"Origin": "http://127.0.0.1:8080"})
    assert r.status_code == 200


def test_post_with_same_origin_referer_allowed():
    client = TestClient(_app_with_test_route())
    r = client.post("/action", headers={"Referer": "http://127.0.0.1:8080/pipeline"})
    assert r.status_code == 200


def test_post_cross_origin_blocked():
    client = TestClient(_app_with_test_route())
    r = client.post("/action", headers={"Origin": "http://evil.example"})
    assert r.status_code == 403


def test_post_no_headers_blocked():
    client = TestClient(_app_with_test_route())
    r = client.post("/action")
    assert r.status_code == 403
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/web/test_origin_guard.py -v`
Expected: `ImportError: cannot import name 'OriginGuardMiddleware'`

- [ ] **Step 3: Implement `swing/web/middleware/origin_guard.py`**

```python
"""Origin/HX-Request/Referer guard for state-changing requests.

Accepts a request when ANY of:
  - HX-Request: true header is present
  - Origin header equals http://<bound_host>:<bound_port>
  - Referer header starts with http://<bound_host>:<bound_port>/

GET/HEAD/OPTIONS are always passed through.
Everything else failing the matrix returns 403.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class OriginGuardMiddleware(BaseHTTPMiddleware):
    _SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    def __init__(self, app, *, bound_host: str, bound_port: int):
        super().__init__(app)
        self._expected_origin = f"http://{bound_host}:{bound_port}"

    async def dispatch(self, request: Request, call_next):
        if request.method in self._SAFE_METHODS:
            return await call_next(request)

        headers = request.headers
        if headers.get("HX-Request", "").lower() == "true":
            return await call_next(request)

        origin = headers.get("Origin")
        if origin is not None:
            if origin == self._expected_origin:
                return await call_next(request)
            return Response(
                status_code=403,
                content=f"Cross-origin request blocked (origin={origin})",
                media_type="text/plain",
            )

        referer = headers.get("Referer", "")
        if referer.startswith(self._expected_origin + "/"):
            return await call_next(request)

        return Response(
            status_code=403,
            content="Missing HX-Request / Origin / Referer same-origin signal",
            media_type="text/plain",
        )
```

- [ ] **Step 4: Run test**

Run: `python -m pytest tests/web/test_origin_guard.py -v`
Expected: 6 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/middleware/origin_guard.py tests/web/test_origin_guard.py
git commit -m "feat(web): OriginGuardMiddleware — HX/Origin/Referer matrix"
```

---

## Task 5: `PriceCache` — `PriceSnapshot` + `get()` + market-hours gate

**Files:**
- Create: `swing/web/price_cache.py`
- Test: `tests/web/test_price_cache.py`

Per-ticker cache miss does a single yfinance fetch with timeout; market-closed or fetch-failure paths fall back to latest `candidates.close` from the most recent `evaluation_runs`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/web/test_price_cache.py
"""PriceCache — TTL, market-hours, timeout fallback, circuit breaker."""
from __future__ import annotations

import time
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from swing.data.db import connect, ensure_schema


def _seed_candidate(cfg, ticker: str, close: float) -> None:
    """Seed one evaluation_runs + one candidate so last-close fallback has data."""
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 0, 0, 1, 0, 0, ?, ?)""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20",
                 "test-v1", "deadbeef"),
            )
            run_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates
                   (evaluation_run_id, ticker, bucket, close, rs_method)
                   VALUES (?, ?, 'skip', ?, 'universe')""",
                (run_id, ticker, close),
            )
    finally:
        conn.close()


def test_cache_hit_within_ttl(seeded_db, monkeypatch):
    from swing.web.price_cache import PriceCache
    cfg, _ = seeded_db
    _seed_candidate(cfg, "AAPL", 180.0)

    cache = PriceCache(cfg)

    # Force market hours True and a deterministic live fetch.
    monkeypatch.setattr(cache, "market_hours_now", lambda: True)
    call_count = [0]

    def fake_fetch(ticker: str) -> float:
        call_count[0] += 1
        return 181.50

    monkeypatch.setattr(cache, "_fetch_live_price", fake_fetch)

    s1 = cache.get("AAPL")
    s2 = cache.get("AAPL")
    assert s1.price == 181.50
    assert not s1.is_stale
    assert call_count[0] == 1  # second call was cache hit


def test_market_closed_returns_last_close(seeded_db, monkeypatch):
    from swing.web.price_cache import PriceCache
    cfg, _ = seeded_db
    _seed_candidate(cfg, "AAPL", 178.25)

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "market_hours_now", lambda: False)

    s = cache.get("AAPL")
    assert s.price == 178.25
    assert s.is_stale
    assert s.source == "last_close_market_closed"


def test_fetch_timeout_falls_back(seeded_db, monkeypatch):
    from swing.web.price_cache import PriceCache
    cfg, _ = seeded_db
    _seed_candidate(cfg, "AAPL", 175.50)

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "market_hours_now", lambda: True)

    def boom(ticker):
        raise TimeoutError("yfinance hung")

    monkeypatch.setattr(cache, "_fetch_live_price", boom)

    s = cache.get("AAPL")
    assert s.price == 175.50
    assert s.is_stale
    assert s.source == "last_close"


def test_unknown_ticker_returns_none_price_fallback(seeded_db, monkeypatch):
    from swing.web.price_cache import PriceCache
    cfg, _ = seeded_db
    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "market_hours_now", lambda: False)
    s = cache.get("NOPE")
    assert s is None
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/web/test_price_cache.py -v`
Expected: `ImportError: cannot import name 'PriceCache'`

- [ ] **Step 3: Implement `swing/web/price_cache.py` core**

```python
"""In-memory lazy TTL price cache with market-hours gate and circuit breaker.

See spec §3.2. The cache serves both `get(ticker)` and `get_many(tickers, deadline)`
(added in Task 6). Live fetches go through yfinance's fast_info; failures and
market-closed windows fall back to the latest `candidates.close` for the ticker.
"""
from __future__ import annotations

import logging
import threading
import time
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from typing import Sequence

from swing.config import Config
from swing.data.db import connect

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class PriceSnapshot:
    ticker: str
    price: float
    asof: datetime
    is_stale: bool
    source: str   # "live" | "last_close" | "last_close_market_closed"


class PriceCache:
    """Thread-safe lazy TTL price cache.

    Thread safety: a single `self._lock` guards `_cache`, `_failure_window`,
    and `_degraded_until`. Executor worker threads record outcomes and request
    threads read the degraded flag under the same lock.
    """

    def __init__(self, cfg: Config):
        self._cfg = cfg
        self._lock = threading.Lock()
        self._cache: dict[str, tuple[PriceSnapshot, float]] = {}
        self._failure_window: deque[bool] = deque(maxlen=20)
        self._degraded_until: float | None = None

    # ---------- single-ticker API ----------

    def get(self, ticker: str) -> PriceSnapshot | None:
        """Return a snapshot, or None if no last-close is known either.

        Cache hit returns instantly. Cache miss routes through
        `_fetch_with_fallback`, which may hit the network or fall back to
        the most recent `candidates.close` row.
        """
        now = time.monotonic()
        ttl = self._cfg.web.price_cache_ttl_seconds
        with self._lock:
            hit = self._cache.get(ticker)
            if hit is not None:
                snap, fetched_at = hit
                if now - fetched_at <= ttl:
                    return snap
        snap = self._fetch_with_fallback(ticker)
        if snap is None:
            return None
        with self._lock:
            self._cache[ticker] = (snap, now)
        return snap

    def clear(self) -> None:
        with self._lock:
            self._cache.clear()

    def refresh_all(self, tickers) -> None:
        """Invalidate cache entries so the next `get` re-fetches."""
        with self._lock:
            for t in tickers:
                self._cache.pop(t, None)

    # ---------- internals (single-ticker) ----------

    def _fetch_with_fallback(self, ticker: str) -> PriceSnapshot | None:
        if not self.market_hours_now():
            last = self._last_close(ticker)
            if last is None:
                return None
            return PriceSnapshot(
                ticker=ticker, price=last, asof=datetime.now(),
                is_stale=True, source="last_close_market_closed",
            )
        try:
            price = self._fetch_live_price(ticker)
            self._record_outcome(success=True)
            return PriceSnapshot(
                ticker=ticker, price=price, asof=datetime.now(),
                is_stale=False, source="live",
            )
        except Exception as exc:
            log.warning("live fetch failed for %s: %s", ticker, exc)
            self._record_outcome(success=False)
            last = self._last_close(ticker)
            if last is None:
                return None
            return PriceSnapshot(
                ticker=ticker, price=last, asof=datetime.now(),
                is_stale=True, source="last_close",
            )

    def _fetch_live_price(self, ticker: str) -> float:
        """Live yfinance call with an enforced per-ticker timeout.

        `yfinance.Ticker(t).fast_info` does NOT accept a `timeout` kwarg and
        can hang indefinitely behind a requests-level socket timeout default.
        `yfinance.download(ticker, period='1d', interval='1m', timeout=N,
        progress=False)` DOES propagate the timeout through to the underlying
        requests session and is the supported path for a bounded fetch.

        Timeout is `self._cfg.web.price_fetch_timeout_seconds` (default 3s).
        A fetch that overruns the timeout raises `requests.ReadTimeout` (or
        yfinance's wrapped equivalent); callers should catch and fall back.
        Returns the most recent close in the returned minute-bar DataFrame.
        """
        import yfinance as yf
        df = yf.download(
            ticker,
            period="1d",
            interval="1m",
            progress=False,
            timeout=self._cfg.web.price_fetch_timeout_seconds,
            auto_adjust=False,
        )
        if df is None or df.empty:
            raise RuntimeError(f"yfinance returned no bars for {ticker}")
        return float(df["Close"].iloc[-1])

    def _last_close(self, ticker: str) -> float | None:
        conn = connect(self._cfg.paths.db_path)
        try:
            row = conn.execute(
                """SELECT close FROM candidates c
                   JOIN evaluation_runs e ON e.id = c.evaluation_run_id
                   WHERE c.ticker = ? AND c.close IS NOT NULL
                   ORDER BY e.run_ts DESC
                   LIMIT 1""",
                (ticker,),
            ).fetchone()
        finally:
            conn.close()
        return float(row[0]) if row else None

    # ---------- circuit breaker (wired in Task 6) ----------

    def _record_outcome(self, *, success: bool) -> None:
        """Update the failure window + degraded flag atomically. Called
        after every real fetch attempt. Live-only: last-close fallbacks
        don't count as either success or failure."""
        with self._lock:
            self._failure_window.append(not success)  # True = failure

    # ---------- market hours ----------

    def market_hours_now(self) -> bool:
        """True during NYSE regular session (incl. holidays-aware).

        Uses `exchange_calendars` (already a Phase 1 base dep via
        `swing.evaluation.dates`).
        """
        import exchange_calendars as xcals
        nyse = xcals.get_calendar("XNYS")
        now = datetime.now()
        # XNYS.is_open_at_time takes UTC; convert from local naive.
        from datetime import timezone
        utc_now = datetime.now(timezone.utc)
        try:
            return bool(nyse.is_open_at_time(utc_now, ignore_breaks=True))
        except Exception:
            return False
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/web/test_price_cache.py -v`
Expected: 4 PASS (the batch/circuit-breaker tests arrive in Task 6).

- [ ] **Step 5: Commit**

```bash
git add swing/web/price_cache.py tests/web/test_price_cache.py
git commit -m "feat(web): PriceCache core — TTL, market-hours gate, last-close fallback"
```

---

## Task 6: `PriceCache.get_many` + circuit breaker

**Files:**
- Modify: `swing/web/price_cache.py`
- Test: `tests/web/test_price_cache.py` (add cases)

Adds `get_many(tickers, deadline_seconds)` that dispatches cache misses in parallel via a caller-supplied executor and respects a global deadline. Implements the circuit-breaker degraded-mode gate at the top of `get` / `get_many`.

- [ ] **Step 1: Append failing tests**

Append to `tests/web/test_price_cache.py`:

```python
def test_get_many_parallel_dispatch(seeded_db, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    for t, px in (("AAPL", 180.0), ("MSFT", 420.0), ("NVDA", 900.0)):
        _seed_candidate(cfg, t, px)

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "market_hours_now", lambda: True)

    def fake_fetch(ticker):
        time.sleep(0.05)
        return {"AAPL": 181.0, "MSFT": 421.0, "NVDA": 901.0}[ticker]

    monkeypatch.setattr(cache, "_fetch_live_price", fake_fetch)

    executor = ThreadPoolExecutor(max_workers=3)
    try:
        snaps = cache.get_many(["AAPL", "MSFT", "NVDA"], deadline_seconds=2.0, executor=executor)
    finally:
        executor.shutdown(wait=True)
    assert set(snaps.keys()) == {"AAPL", "MSFT", "NVDA"}
    assert snaps["AAPL"].price == 181.0
    assert snaps["MSFT"].price == 421.0
    assert snaps["NVDA"].price == 901.0
    assert not any(s.is_stale for s in snaps.values())


def test_get_many_deadline_falls_back(seeded_db, monkeypatch):
    from concurrent.futures import ThreadPoolExecutor
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    _seed_candidate(cfg, "AAPL", 180.0)
    _seed_candidate(cfg, "MSFT", 420.0)

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "market_hours_now", lambda: True)

    def slow(ticker):
        time.sleep(5.0)
        return 1.0

    monkeypatch.setattr(cache, "_fetch_live_price", slow)

    executor = ThreadPoolExecutor(max_workers=2)
    t0 = time.monotonic()
    try:
        snaps = cache.get_many(["AAPL", "MSFT"], deadline_seconds=0.3, executor=executor)
    finally:
        executor.shutdown(wait=False, cancel_futures=True)
    elapsed = time.monotonic() - t0
    # Deadline is honored; both fall back to last_close.
    assert elapsed < 2.0
    assert snaps["AAPL"].is_stale and snaps["AAPL"].source == "last_close"
    assert snaps["MSFT"].is_stale and snaps["MSFT"].source == "last_close"


def test_circuit_breaker_trips_and_recovers(seeded_db, monkeypatch):
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    _seed_candidate(cfg, "AAPL", 180.0)
    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "market_hours_now", lambda: True)

    # Record 15 failures to drive failure fraction > 0.5 over a 20-wide window.
    for _ in range(15):
        cache._record_outcome(success=False)
    for _ in range(5):
        cache._record_outcome(success=True)

    # Force the breaker evaluation by calling _maybe_trip_breaker directly.
    cache._maybe_trip_breaker()
    assert cache.is_degraded()

    # During degraded mode, get() returns last-close without touching the network.
    def should_not_be_called(ticker):
        raise AssertionError("live fetch must be skipped in degraded mode")

    monkeypatch.setattr(cache, "_fetch_live_price", should_not_be_called)
    s = cache.get("AAPL")
    assert s.is_stale
    assert s.source == "last_close"


def test_circuit_breaker_is_instance_scoped(seeded_db):
    from swing.web.price_cache import PriceCache
    cfg, _ = seeded_db
    a = PriceCache(cfg)
    b = PriceCache(cfg)
    for _ in range(20):
        a._record_outcome(success=False)
    a._maybe_trip_breaker()
    assert a.is_degraded()
    # The second instance must not inherit degraded state.
    assert not b.is_degraded()


def test_refresh_all_invalidates_and_next_get_refetches(seeded_db, monkeypatch):
    """refresh_all is invalidate-only: it pops entries from the cache so the
    next get/get_many re-fetches. It does NOT itself hit the network (that
    would duplicate work — POST /prices/refresh rebuilds the VM after calling
    refresh_all, and the VM build triggers the actual re-fetch via get_many).
    """
    from swing.web.price_cache import PriceCache

    cfg, _ = seeded_db
    _seed_candidate(cfg, "AAPL", 180.0)
    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "market_hours_now", lambda: True)

    fetch_calls = [0]
    def counting_fetch(ticker):
        fetch_calls[0] += 1
        return 181.0

    monkeypatch.setattr(cache, "_fetch_live_price", counting_fetch)

    # Populate cache.
    s1 = cache.get("AAPL")
    assert s1.price == 181.0
    assert fetch_calls[0] == 1

    # Second get hits cache — no new fetch.
    cache.get("AAPL")
    assert fetch_calls[0] == 1

    # refresh_all invalidates.
    cache.refresh_all(["AAPL"])
    cache.get("AAPL")
    assert fetch_calls[0] == 2, "refresh_all must invalidate; next get re-fetches"
```

- [ ] **Step 2: Verify the new tests fail**

Run: `python -m pytest tests/web/test_price_cache.py -v`
Expected: 4 PASS, 4 FAIL (get_many/breaker not yet implemented).

- [ ] **Step 3: Extend `swing/web/price_cache.py`**

Replace the circuit-breaker placeholder section (`_record_outcome`) with:

```python
    # ---------- circuit breaker ----------

    def _record_outcome(self, *, success: bool) -> None:
        with self._lock:
            self._failure_window.append(not success)

    def is_degraded(self) -> bool:
        with self._lock:
            return self._degraded_until is not None and time.monotonic() < self._degraded_until

    def degraded_until(self) -> datetime | None:
        with self._lock:
            if self._degraded_until is None:
                return None
            if time.monotonic() >= self._degraded_until:
                return None
            remaining = self._degraded_until - time.monotonic()
            return datetime.fromtimestamp(time.time() + remaining)

    def _maybe_trip_breaker(self) -> None:
        """Enter degraded mode if failure fraction in window > 0.5."""
        with self._lock:
            if not self._failure_window:
                return
            failures = sum(1 for x in self._failure_window if x)
            if failures / len(self._failure_window) > 0.5:
                cooldown = self._cfg.web.circuit_breaker_cooldown_seconds
                self._degraded_until = time.monotonic() + cooldown
                log.warning(
                    "price cache entered degraded mode for %ss (failures=%d/%d)",
                    cooldown, failures, len(self._failure_window),
                )

    # ---------- batch API ----------

    def get_many(
        self, tickers: Sequence[str], deadline_seconds: float,
        *, executor=None,
    ) -> dict[str, PriceSnapshot]:
        """Batch version of get(). Cache hits are served synchronously; misses
        are dispatched to `executor` (required; app.state.price_fetch_executor
        in production) with a total deadline.

        Leaked threads on timeout are tolerated (spec §3.2): each is waiting
        on an HTTP socket with yfinance's own timeout and terminates at most
        one per-ticker-timeout window later.
        """
        # Degraded mode: skip all live fetches.
        if self.is_degraded():
            out: dict[str, PriceSnapshot] = {}
            for t in tickers:
                last = self._last_close(t)
                if last is not None:
                    out[t] = PriceSnapshot(
                        ticker=t, price=last, asof=datetime.now(),
                        is_stale=True, source="last_close",
                    )
            return out

        if executor is None:
            raise ValueError("executor is required — pass app.state.price_fetch_executor")

        results: dict[str, PriceSnapshot] = {}
        misses: list[str] = []
        now = time.monotonic()
        ttl = self._cfg.web.price_cache_ttl_seconds
        with self._lock:
            for t in tickers:
                hit = self._cache.get(t)
                if hit is not None and now - hit[1] <= ttl:
                    results[t] = hit[0]
                else:
                    misses.append(t)

        if not misses:
            return results

        from concurrent.futures import as_completed, TimeoutError as FuturesTimeout
        futures = {executor.submit(self._fetch_with_fallback, t): t for t in misses}
        try:
            for future in as_completed(futures, timeout=deadline_seconds):
                ticker = futures[future]
                try:
                    snap = future.result(timeout=0)
                except Exception:
                    snap = self._fallback_snapshot(ticker)
                if snap is not None:
                    results[ticker] = snap
                    with self._lock:
                        self._cache[ticker] = (snap, time.monotonic())
        except FuturesTimeout:
            pass

        for ticker in misses:
            if ticker not in results:
                snap = self._fallback_snapshot(ticker)
                if snap is not None:
                    results[ticker] = snap

        self._maybe_trip_breaker()
        return results

    def _fallback_snapshot(self, ticker: str) -> PriceSnapshot | None:
        last = self._last_close(ticker)
        if last is None:
            return None
        return PriceSnapshot(
            ticker=ticker, price=last, asof=datetime.now(),
            is_stale=True, source="last_close",
        )
```

Also adjust `_fetch_with_fallback` to enter the breaker path when degraded:

```python
    def _fetch_with_fallback(self, ticker: str) -> PriceSnapshot | None:
        if self.is_degraded():
            return self._fallback_snapshot(ticker)
        # ...existing body unchanged...
```

Wire the breaker trip into `get()`: append `self._maybe_trip_breaker()` after the `self._cache[ticker] = (snap, now)` assignment.

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/web/test_price_cache.py -v`
Expected: 8 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/price_cache.py tests/web/test_price_cache.py
git commit -m "feat(web): PriceCache.get_many + circuit breaker (instance-scoped)"
```

---

## Task 7: App wiring — shared executor lifespan + price cache on `app.state`

**Files:**
- Modify: `swing/web/app.py`
- Test: extend `tests/web/test_app_smoke.py`

Adds the shared `ThreadPoolExecutor` with FastAPI lifespan cleanup, attaches the `PriceCache` to `app.state`, mounts `/charts` + `/static`, registers the origin-guard middleware. No routes yet.

- [ ] **Step 1: Extend the smoke test**

Append to `tests/web/test_app_smoke.py`:

```python
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
```

- [ ] **Step 2: Verify the new assertions fail**

Run: `python -m pytest tests/web/test_app_smoke.py -v`
Expected: first two pass from Task 3, the three new ones fail.

- [ ] **Step 3: Replace `swing/web/app.py`**

```python
"""FastAPI app factory for the Phase 3a dashboard."""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from swing.config import Config
from swing.web.middleware.origin_guard import OriginGuardMiddleware
from swing.web.price_cache import PriceCache

log = logging.getLogger(__name__)


def _static_dir() -> Path:
    return Path(__file__).parent / "static"


def _templates_dir() -> Path:
    return Path(__file__).parent / "templates"


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

    return app
```

- [ ] **Step 4: Run test**

Run: `python -m pytest tests/web/test_app_smoke.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/app.py tests/web/test_app_smoke.py
git commit -m "feat(web): app wiring — lifespan executor, price cache, static mounts, origin guard"
```

---

## Task 8: `swing web` CLI command + `run_server` with loopback enforcement

**Files:**
- Modify: `swing/cli.py`
- Modify: `swing/web/cli_cmd.py`
- Test: `tests/web/test_cli_cmd.py`

Adds `swing web` as a Click subcommand that resolves effective host/port/reload and invokes uvicorn. `run_server` refuses any non-loopback host and surfaces a clear "port busy" error.

- [ ] **Step 1: Write the failing test**

```python
# tests/web/test_cli_cmd.py
"""`swing web` CLI + run_server guards."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

import pytest

from swing.web.cli_cmd import run_server


def test_refuses_non_loopback_host(test_cfg, capsys):
    cfg, cfg_path = test_cfg
    with pytest.raises(SystemExit) as exc:
        run_server(cfg=cfg, cfg_path=cfg_path, host="0.0.0.0", port=None, reload=None)
    assert exc.value.code == 1
    out = capsys.readouterr().err
    assert "loopback" in out.lower() or "127.0.0.1" in out


def test_refuses_non_loopback_from_config(test_cfg, capsys, tmp_path):
    """The [web].host config value is also enforced — user cannot bypass via config."""
    from swing.config import Config, Web
    cfg, cfg_path = test_cfg
    # Replace the web config with a non-loopback host.
    import dataclasses
    bad_web = dataclasses.replace(cfg.web, host="0.0.0.0")
    bad_cfg = dataclasses.replace(cfg, web=bad_web)
    with pytest.raises(SystemExit) as exc:
        run_server(cfg=bad_cfg, cfg_path=cfg_path, host=None, port=None, reload=None)
    assert exc.value.code == 1


def test_cli_overrides_config(test_cfg, monkeypatch):
    cfg, cfg_path = test_cfg
    captured = {}

    def fake_run(app, *, host, port, reload, **_):
        captured["host"] = host
        captured["port"] = port
        captured["reload"] = reload

    monkeypatch.setattr("uvicorn.run", fake_run)
    run_server(cfg=cfg, cfg_path=cfg_path, host=None, port=9191, reload=True)
    assert captured["port"] == 9191
    assert captured["reload"] is True
    assert captured["host"] == "127.0.0.1"


def test_swing_web_cli_registered():
    """The `web` subcommand is visible via `swing web --help`."""
    from click.testing import CliRunner
    from swing.cli import main
    r = CliRunner().invoke(main, ["web", "--help"])
    assert r.exit_code == 0
    assert "web" in r.output.lower()
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/web/test_cli_cmd.py -v`
Expected: `NotImplementedError` or assertion failures.

- [ ] **Step 3: Implement `swing/web/cli_cmd.py`**

```python
"""`swing web` backing entry point."""
from __future__ import annotations

import logging
import sys
from pathlib import Path

import click

from swing.config import Config
from swing.web.app import create_app

log = logging.getLogger(__name__)

_ALLOWED_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})


def run_server(
    *, cfg: Config, cfg_path: Path | None = None,
    host: str | None = None, port: int | None = None,
    reload: bool | None = None,
) -> None:
    """Resolve effective host/port/reload and start uvicorn.

    Precedence: CLI flag > [web] config > dataclass default. The
    resolved host MUST be a loopback name; non-loopback values are
    refused even when set via config.
    """
    effective_host = host or cfg.web.host
    effective_port = port if port is not None else cfg.web.port
    effective_reload = reload if reload is not None else cfg.web.reload

    if effective_host not in _ALLOWED_HOSTS:
        click.echo(
            f"ERROR: dashboard must bind a loopback host (got {effective_host!r}). "
            f"Allowed: {sorted(_ALLOWED_HOSTS)}.",
            err=True,
        )
        sys.exit(1)

    app = create_app(cfg, cfg_path)

    import uvicorn
    try:
        uvicorn.run(
            app, host=effective_host, port=effective_port,
            reload=effective_reload, log_level="info",
        )
    except OSError as exc:
        click.echo(
            f"ERROR: could not bind {effective_host}:{effective_port} ({exc}). "
            f"Set [web].port in swing.config.toml or pass --port.",
            err=True,
        )
        sys.exit(1)
```

- [ ] **Step 4: Add `swing web` to `swing/cli.py`**

Find the existing Click group / main function. Add the command (after existing commands, before the `if __name__ == "__main__":` block or module-level `main` invocation).

**CRITICAL: the `swing.web.cli_cmd` import MUST live INSIDE the command function body**, not at the module top. That keeps the base install (no `[web]` extra) starting the CLI without requiring fastapi/uvicorn/jinja2 — without it, running any `swing <non-web>` subcommand on a base install fails at `swing/cli.py` import time (R1 Major 3).

```python
@main.command("web")
@click.option("--host", default=None, help="Override [web].host from config")
@click.option("--port", type=int, default=None)
@click.option("--reload", is_flag=True, default=None, help="Enable auto-reload")
@click.pass_context
def web_cmd(ctx, host, port, reload):
    """Run the dashboard on localhost."""
    # Lazy import: do NOT hoist to module top — keeps base install working
    # without [web] extra (invariant 12).
    from swing.web.cli_cmd import run_server
    run_server(
        cfg=ctx.obj["config"],
        cfg_path=ctx.obj.get("config_path"),
        host=host, port=port, reload=reload,
    )
```

If `ctx.obj` does not yet carry `"config_path"`, open `swing/cli.py`'s top-level group and ensure the `@main.callback` / `@click.group` entry stores it. Typical existing pattern:

```python
@click.group()
@click.option("--config", "config_path", required=True, type=click.Path(exists=True))
@click.pass_context
def main(ctx, config_path):
    ctx.ensure_object(dict)
    ctx.obj["config"] = load(Path(config_path))
    ctx.obj["config_path"] = Path(config_path)   # <-- ADD THIS LINE if missing
```

- [ ] **Step 5: Run the tests**

Run: `python -m pytest tests/web/test_cli_cmd.py -v`
Expected: 4 PASS.

- [ ] **Step 6: Commit**

```bash
git add swing/web/cli_cmd.py swing/cli.py tests/web/test_cli_cmd.py
git commit -m "feat(cli): add `swing web` command + loopback enforcement in run_server"
```

---

## Task 9: `DashboardVM` + `build_dashboard` view-model builder

**Files:**
- Create: `swing/web/view_models/dashboard.py`
- Test: `tests/web/test_view_models/test_dashboard.py`

Produces the frozen VM consumed by the dashboard template. Reads Phase 2 repos + the price cache; computes `open_trade_advisories` via `compute_all_suggestions`.

- [ ] **Step 1: Write the failing test**

```python
# tests/web/test_view_models/test_dashboard.py
"""build_dashboard produces a correctly-shaped VM from seeded state."""
from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock

from swing.data.db import connect
from swing.data.repos.trades import insert_trade_with_event
from swing.data.models import Trade


def _seed_for_dashboard(cfg) -> None:
    """Seed one pipeline run, one evaluation run, one open trade, one weather, one watchlist row."""
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Weather
            conn.execute(
                """INSERT INTO weather_runs (run_ts, asof_date, ticker, status, close, rationale)
                   VALUES (?, ?, 'SPY', 'Bullish', 450.0, 'ok')""",
                ("2026-04-17T21:49:00", "2026-04-17"),
            )
            # Evaluation + candidate
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 2, 1, 1, 0, 0, 0, 'v1', 'deadbeef')""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20"),
            )
            eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket, close, pivot, initial_stop, rs_method)
                   VALUES (?, 'AAPL', 'aplus', 180.0, 181.0, 170.0, 'universe')""",
                (eval_id,),
            )
            # Daily recommendation for today's action session
            conn.execute(
                """INSERT INTO daily_recommendations
                   (evaluation_run_id, data_asof_date, action_session_date,
                    ticker, recommendation, action_text)
                   VALUES (?, '2026-04-17', '2026-04-20', 'AAPL', 'today_decision',
                           'Buy-stop limit $181.00 · 5 sh · $55 risk')""",
                (eval_id,),
            )
            # Open trade
            insert_trade_with_event(
                conn,
                Trade(
                    id=None, ticker="AAPL", entry_date="2026-04-15",
                    entry_price=180.0, initial_shares=5, initial_stop=170.0,
                    current_stop=170.0, status="open",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ),
                event_ts="2026-04-15T09:30:00",
            )
            # Pipeline run
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date, action_session_date,
                    state, lease_token)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00', 'scheduled',
                           '2026-04-17', '2026-04-20', 'complete', 'done-token')""",
            )
    finally:
        conn.close()


def test_build_dashboard_shape(seeded_db, monkeypatch):
    from swing.web.view_models.dashboard import DashboardVM, build_dashboard
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from datetime import datetime

    cfg, _ = seeded_db
    _seed_for_dashboard(cfg)

    cache = PriceCache(cfg)
    fake_snap = PriceSnapshot(
        ticker="AAPL", price=182.0, asof=datetime.now(),
        is_stale=False, source="live",
    )
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {t: fake_snap for t in tickers})
    monkeypatch.setattr(cache, "is_degraded", lambda: False)

    vm = build_dashboard(cfg=cfg, cache=cache, executor=None)
    assert isinstance(vm, DashboardVM)
    assert vm.session_date != ""
    assert len(vm.open_trades) == 1
    assert vm.open_trades[0].ticker == "AAPL"
    assert "AAPL" in vm.open_trade_last_prices
    assert vm.open_trade_last_prices["AAPL"].price == 182.0
    assert 1 in vm.open_trade_advisories   # keyed by trade_id
    assert vm.price_source_degraded is False
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/web/test_view_models/test_dashboard.py -v`
Expected: `ImportError: cannot import name 'DashboardVM'`.

- [ ] **Step 3: Implement `swing/web/view_models/dashboard.py`**

```python
"""DashboardVM + builder."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Mapping

from swing.config import Config
from swing.data.db import connect
from swing.data.models import Candidate, Trade, WatchlistEntry, WeatherRun
from swing.data.repos.cash import list_cash
from swing.data.repos.candidates import fetch_candidates_for_run
from swing.data.repos.recommendations import list_for_session
from swing.data.repos.trades import list_all_exits, list_open_trades
from swing.data.repos.watchlist import list_active_watchlist
from swing.data.repos.weather import get_latest_for_date
from swing.evaluation.dates import action_session_for_run
from swing.trades.advisory import compute_all_suggestions
from swing.trades.equity import current_equity
from swing.web.price_cache import PriceCache, PriceSnapshot


@dataclass(frozen=True)
class StatusStripVM:
    weather_status: str       # "Bullish" | "Caution" | "Bearish" | "STALE"
    weather_rationale: str
    equity: float
    open_count: int
    soft_warn: int
    hard_cap: int
    last_pipeline_ts: str | None
    last_pipeline_state: str | None


@dataclass(frozen=True)
class DecisionVM:
    ticker: str
    action_text: str
    narrative: str | None


@dataclass(frozen=True)
class AdvisorySuggestionVM:
    rule: str
    message: str   # matches Phase 2 AdvisorySuggestion.message — do not rename


@dataclass(frozen=True)
class DashboardVM:
    generated_at: str
    session_date: str
    stale_banner: str | None
    status_strip: StatusStripVM
    today_decisions: list[DecisionVM]
    open_trades: list[Trade]
    open_trade_advisories: Mapping[int, list[AdvisorySuggestionVM]]
    open_trade_last_prices: Mapping[str, PriceSnapshot]
    watchlist_top5: list[WatchlistEntry]
    watchlist_remaining_count: int
    watchlist_last_prices: Mapping[str, PriceSnapshot]
    flag_tags: Mapping[str, tuple[str, ...]]
    candidates_by_ticker: Mapping[str, Candidate]
    prices_generated_at: str
    price_source_degraded: bool
    price_source_degraded_until: str | None


def build_dashboard(*, cfg: Config, cache: PriceCache, executor) -> DashboardVM:
    """Read state + prices, return a frozen VM. `executor` may be None in
    tests (the cache will fall back to serial `get()` behavior via the
    monkeypatched `get_many`).
    """
    now = datetime.now()
    action_session = action_session_for_run(now).isoformat()

    conn = connect(cfg.paths.db_path)
    try:
        open_trades = list_open_trades(conn)
        recs = list_for_session(conn, action_session)
        watchlist = list_active_watchlist(conn)
        weather = get_latest_for_date(conn, action_session, ticker=cfg.rs.benchmark_ticker)
        # Equity for status strip.
        equity = current_equity(
            starting_equity=cfg.account.starting_equity,
            exits=list_all_exits(conn),
            cash_movements=list_cash(conn),
        )
        # Latest pipeline run.
        row = conn.execute(
            """SELECT finished_ts, state FROM pipeline_runs
               ORDER BY started_ts DESC LIMIT 1"""
        ).fetchone()
        last_pipeline_ts, last_pipeline_state = (row[0], row[1]) if row else (None, None)
        # Stale banner: most recent complete run's action_session < today's action_session.
        row = conn.execute(
            """SELECT action_session_date FROM pipeline_runs
               WHERE state='complete'
               ORDER BY finished_ts DESC LIMIT 1"""
        ).fetchone()
        stale_banner = None
        if row is not None and row[0] < action_session:
            stale_banner = (
                f"Last pipeline session: {row[0]} — decisions below are for session "
                f"{action_session}. Run pipeline for the current session."
            )
        # Latest candidates for flag_tags + narrative.
        row = conn.execute("SELECT id FROM evaluation_runs ORDER BY run_ts DESC LIMIT 1").fetchone()
        candidates: list[Candidate] = []
        if row is not None:
            candidates = fetch_candidates_for_run(conn, row[0])
    finally:
        conn.close()

    candidates_by_ticker = {c.ticker: c for c in candidates}

    # Prices — batch fetch all tickers we need.
    active_tickers = {t.ticker for t in open_trades}
    watch_sorted = _sort_by_proximity(watchlist)
    top5 = watch_sorted[:5]
    active_tickers.update(w.ticker for w in top5)
    prices = cache.get_many(
        sorted(active_tickers),
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )

    open_trade_last_prices = {t.ticker: prices[t.ticker] for t in open_trades if t.ticker in prices}
    watchlist_last_prices = {w.ticker: prices[w.ticker] for w in top5 if w.ticker in prices}

    # Advisories. Phase 2's compute_all_suggestions expects an
    # AdvisoryContext with (as_of_date, current_price, sma10, sma20,
    # weather_status, config=StopAdvisoryConfig). SMA values come from the
    # ticker's candidates.criteria rows when present; the advisory rules
    # handle None gracefully (no-op if MA data missing).
    from swing.trades.advisory import AdvisoryContext
    advisories: dict[int, list[AdvisorySuggestionVM]] = {}
    weather_status_str = weather.status if weather else "STALE"
    for t in open_trades:
        snap = open_trade_last_prices.get(t.ticker)
        if snap is None:
            continue
        sma10, sma20 = _extract_smas(candidates_by_ticker.get(t.ticker))
        ctx_adv = AdvisoryContext(
            as_of_date=now.date().isoformat(),
            current_price=snap.price,
            sma10=sma10,
            sma20=sma20,
            weather_status=weather_status_str,
            config=cfg.stop_advisory,
        )
        raw = compute_all_suggestions(t, ctx_adv)
        advisories[t.id or 0] = [
            AdvisorySuggestionVM(rule=s.rule, message=s.message)
            for s in raw
        ]

    flag_tags = _flag_tags(candidates_by_ticker)

    # Status strip.
    status_strip = StatusStripVM(
        weather_status=(weather.status if weather else "STALE"),
        weather_rationale=(weather.rationale if weather and weather.rationale else ""),
        equity=equity,
        open_count=len(open_trades),
        soft_warn=cfg.position_limits.soft_warn_open,
        hard_cap=cfg.position_limits.hard_cap_open,
        last_pipeline_ts=last_pipeline_ts,
        last_pipeline_state=last_pipeline_state,
    )

    today_decisions = [
        DecisionVM(
            ticker=r.ticker, action_text=r.action_text or "",
            narrative=r.rationale,
        ) for r in recs if r.recommendation == "today_decision"
    ]

    degraded_until = cache.degraded_until()
    return DashboardVM(
        generated_at=now.isoformat(timespec="seconds"),
        session_date=action_session,
        stale_banner=stale_banner,
        status_strip=status_strip,
        today_decisions=today_decisions,
        open_trades=list(open_trades),
        open_trade_advisories=advisories,
        open_trade_last_prices=open_trade_last_prices,
        watchlist_top5=list(top5),
        watchlist_remaining_count=max(0, len(watchlist) - 5),
        watchlist_last_prices=watchlist_last_prices,
        flag_tags=flag_tags,
        candidates_by_ticker=candidates_by_ticker,
        prices_generated_at=now.isoformat(timespec="seconds"),
        price_source_degraded=cache.is_degraded(),
        price_source_degraded_until=(
            degraded_until.isoformat(timespec="seconds") if degraded_until else None
        ),
    )


def _sort_by_proximity(watchlist: list[WatchlistEntry]) -> list[WatchlistEntry]:
    def key(w: WatchlistEntry) -> float:
        if w.entry_target is None or w.last_close is None:
            return float("inf")
        return abs(w.last_close - w.entry_target) / max(w.entry_target, 1e-6)
    return sorted(watchlist, key=key)


def _extract_smas(candidate: Candidate | None) -> tuple[float | None, float | None]:
    """Read sma10/sma20 out of a candidate's criteria list for advisory
    context. Phase 2 stores MA stack results with the raw values in
    `CandidateCriterion.value` as comma-joined strings — we pull them from
    there when present. Missing MAs → (None, None); the advisory rules
    tolerate None inputs (no-op)."""
    if candidate is None:
        return (None, None)
    sma10 = sma20 = None
    for cr in candidate.criteria:
        if cr.criterion_name == "ma_short_rising" and cr.value:
            # value format example: "10MA=152.34, 20MA=150.12, 50MA=148.90"
            for piece in cr.value.split(","):
                piece = piece.strip()
                if piece.startswith("10MA="):
                    try: sma10 = float(piece.split("=", 1)[1])
                    except ValueError: pass
                elif piece.startswith("20MA="):
                    try: sma20 = float(piece.split("=", 1)[1])
                    except ValueError: pass
    return (sma10, sma20)


def _flag_tags(candidates_by_ticker: Mapping[str, Candidate]) -> Mapping[str, tuple[str, ...]]:
    tags: dict[str, tuple[str, ...]] = {}
    for ticker, c in candidates_by_ticker.items():
        row_tags: list[str] = []
        tt_pass = sum(1 for cr in c.criteria if cr.layer == "trend_template" and cr.result == "pass")
        if tt_pass >= 7:
            row_tags.append("TT✓")
        vcp_pass = sum(1 for cr in c.criteria if cr.layer == "vcp" and cr.result == "pass")
        vcp_total = sum(1 for cr in c.criteria if cr.layer == "vcp")
        if vcp_total and vcp_pass == vcp_total:
            row_tags.append("VCP✓")
        if c.bucket == "aplus":
            row_tags.append("A+")
        if row_tags:
            tags[ticker] = tuple(row_tags)
    return tags
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/web/test_view_models/test_dashboard.py -v`
Expected: 1 PASS.

Signature is locked per Phase 2 `swing/trades/advisory.py`:
- `AdvisoryContext(as_of_date: str, current_price: float, sma10: float | None, sma20: float | None, weather_status: str, config: StopAdvisoryConfig)` — frozen dataclass.
- `AdvisorySuggestion(rule: str, message: str)` — exactly these two fields; no `proposed_stop` or `narrative`. The VM mirrors this as `AdvisorySuggestionVM(rule, message)`.
- `compute_all_suggestions(trade: Trade, ctx: AdvisoryContext) -> list[AdvisorySuggestion]`.

- [ ] **Step 5: Commit**

```bash
git add swing/web/view_models/dashboard.py tests/web/test_view_models/test_dashboard.py
git commit -m "feat(web): DashboardVM + build_dashboard view-model builder"
```

---

## Task 10: Base template + dashboard template + partials

**Files:**
- Create: `swing/web/templates/base.html.j2`
- Create: `swing/web/templates/dashboard.html.j2`
- Create: `swing/web/templates/partials/status_strip.html.j2`
- Create: `swing/web/templates/partials/stale_banner.html.j2`
- Create: `swing/web/templates/partials/price_degraded_banner.html.j2`
- Create: `swing/web/templates/partials/today_decisions.html.j2`
- Create: `swing/web/templates/partials/open_positions.html.j2`
- Create: `swing/web/templates/partials/watchlist_row.html.j2`

Templates are pure formatting; no business logic. Each partial wraps its HTMX swap target ID.

- [ ] **Step 1: Create `base.html.j2`**

```html
{#- swing/web/templates/base.html.j2 -#}
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Swing Trading Dashboard</title>
  <link rel="stylesheet" href="/static/app.css">
  <script src="/static/htmx.min.js"></script>
</head>
<body>
  <nav class="topbar">
    <span class="date">{{ vm.session_date }}</span>
    <a href="/">Dashboard</a>
    <a href="/watchlist">Watchlist</a>
    <a href="/journal">Journal</a>
    <a href="/pipeline">Pipeline</a>
  </nav>
  {% if vm.stale_banner %}
    {% include "partials/stale_banner.html.j2" %}
  {% endif %}
  {% if vm.price_source_degraded %}
    {% include "partials/price_degraded_banner.html.j2" %}
  {% endif %}
  <main>
    {% block content %}{% endblock %}
  </main>
</body>
</html>
```

- [ ] **Step 2: Create `dashboard.html.j2`**

```html
{#- swing/web/templates/dashboard.html.j2 -#}
{% extends "base.html.j2" %}
{% block content %}
  <div id="status-strip">
    {% include "partials/status_strip.html.j2" %}
  </div>
  <div id="today-decisions">
    {% include "partials/today_decisions.html.j2" %}
  </div>
  <div id="open-positions">
    {% include "partials/open_positions.html.j2" %}
  </div>
  <section id="watchlist-top5">
    <h2>Watchlist — near trigger</h2>
    <table class="watchlist">
      <thead><tr>
        <th></th><th>Ticker</th><th>Last</th><th>Pivot</th><th>% to pivot</th><th>ADR</th><th>Tags</th>
      </tr></thead>
      <tbody>
        {% for w in vm.watchlist_top5 %}
          {% set price = vm.watchlist_last_prices.get(w.ticker) %}
          {% set tags = vm.flag_tags.get(w.ticker, ()) %}
          {% include "partials/watchlist_row.html.j2" %}
        {% endfor %}
      </tbody>
    </table>
    {% if vm.watchlist_remaining_count > 0 %}
      <a href="/watchlist">Show all ({{ vm.watchlist_remaining_count + 5 }})</a>
    {% endif %}
  </section>
  <footer class="price-refresh">
    Prices {{ vm.prices_generated_at }}
    <button hx-post="/prices/refresh" hx-swap="none" hx-headers='{"HX-Request": "true"}'>Refresh now</button>
  </footer>
{% endblock %}
```

- [ ] **Step 3: Create `partials/status_strip.html.j2`**

```html
{#- status_strip — three tiles + run-now button -#}
<div class="tile" id="weather-tile">
  <div class="label">Weather</div>
  <div class="value">{{ vm.status_strip.weather_status }}</div>
  <div class="rationale">{{ vm.status_strip.weather_rationale }}</div>
</div>
<div class="tile" id="account-tile">
  <div class="label">Account</div>
  <div class="value">${{ '%.0f' | format(vm.status_strip.equity) }}</div>
  <div class="rationale">
    {{ vm.status_strip.open_count }} / {{ vm.status_strip.soft_warn }}
    (hard cap {{ vm.status_strip.hard_cap }})
  </div>
</div>
<div class="tile" id="pipeline-tile">
  <div class="label">Last pipeline</div>
  <div class="value">{{ vm.status_strip.last_pipeline_ts or "never" }}</div>
  <div class="rationale">
    state: {{ vm.status_strip.last_pipeline_state or "—" }}
    <button hx-post="/pipeline/run" hx-target="#run-panel"
            hx-swap="innerHTML" hx-headers='{"HX-Request": "true"}'>
      Run now
    </button>
  </div>
</div>
<div id="run-panel"></div>
```

- [ ] **Step 4: Create `partials/stale_banner.html.j2`**

```html
<div class="banner banner-stale">
  {{ vm.stale_banner }}
</div>
```

- [ ] **Step 5: Create `partials/price_degraded_banner.html.j2`**

```html
<div class="banner banner-degraded">
  Live price fetch disabled — upstream outage; showing last close
  {% if vm.price_source_degraded_until %}
    until {{ vm.price_source_degraded_until }}
  {% endif %}
</div>
```

- [ ] **Step 6: Create `partials/today_decisions.html.j2`**

```html
<section class="decisions">
  <h2>Today's decisions</h2>
  {% if not vm.today_decisions %}
    <p class="empty">No decisions today — watchlist below.</p>
  {% else %}
    <ul>
      {% for d in vm.today_decisions %}
        <li>
          <strong>{{ d.ticker }}</strong> — {{ d.action_text }}
          {% if d.narrative %}<div class="narrative">{{ d.narrative }}</div>{% endif %}
        </li>
      {% endfor %}
    </ul>
  {% endif %}
</section>
```

- [ ] **Step 7: Create `partials/open_positions.html.j2`**

```html
<section class="open-positions">
  <h2>Open positions</h2>
  {% if not vm.open_trades %}
    <p class="empty">No open positions.</p>
  {% else %}
    <table>
      <thead><tr>
        <th>Ticker</th><th>Entry</th><th>Current stop</th><th>Last</th><th>Advisory</th>
      </tr></thead>
      <tbody>
        {% for t in vm.open_trades %}
          {% set snap = vm.open_trade_last_prices.get(t.ticker) %}
          <tr>
            <td>{{ t.ticker }}</td>
            <td>${{ '%.2f' | format(t.entry_price) }}</td>
            <td>${{ '%.2f' | format(t.current_stop) }}</td>
            <td>
              {% if snap %}
                ${{ '%.2f' | format(snap.price) }}
                {% if snap.is_stale %}<span class="stale">(stale)</span>{% endif %}
              {% else %}—{% endif %}
            </td>
            <td>
              {% for s in vm.open_trade_advisories.get(t.id, []) %}
                <div>{{ s.message }}</div>
              {% endfor %}
            </td>
          </tr>
        {% endfor %}
      </tbody>
    </table>
  {% endif %}
</section>
```

- [ ] **Step 8: Create `partials/watchlist_row.html.j2`**

```html
{#- Expects: w (WatchlistEntry), price (PriceSnapshot|None), tags (tuple[str]) -#}
<tr hx-get="/watchlist/{{ w.ticker }}/expand" hx-swap="outerHTML"
    hx-headers='{"HX-Request": "true"}'>
  <td>
    {% if price and w.entry_target and price.price >= w.entry_target * 0.99 %}⚡{% endif %}
  </td>
  <td>{{ w.ticker }}</td>
  <td>
    {% if price %}
      ${{ '%.2f' | format(price.price) }}
      {% if price.is_stale %}<span class="stale">(stale)</span>{% endif %}
    {% else %}—{% endif %}
  </td>
  <td>${{ '%.2f' | format(w.entry_target or 0) }}</td>
  <td>
    {% if price and w.entry_target %}
      {{ '%.1f' | format(((price.price - w.entry_target) / w.entry_target) * 100) }}%
    {% else %}—{% endif %}
  </td>
  <td>{{ '%.2f' | format(w.last_adr_pct or 0) }}</td>
  <td>{{ tags | join(' · ') }}</td>
</tr>
```

- [ ] **Step 9: No test yet — templates render in Task 11**

- [ ] **Step 10: Commit**

```bash
git add swing/web/templates
git commit -m "feat(web): dashboard templates + 6 partials"
```

---

## Task 11: `GET /` dashboard route + integration test

**Files:**
- Create: `swing/web/routes/dashboard.py`
- Modify: `swing/web/app.py` — include the router
- Test: `tests/web/test_routes/test_dashboard_route.py`

Thin handler — parses `request`, calls `build_dashboard`, returns a `TemplateResponse`.

- [ ] **Step 1: Write the failing test**

```python
# tests/web/test_routes/test_dashboard_route.py
"""GET / returns 200 with expected snippets."""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.web.app import create_app


def _seed_minimal_dashboard_state(cfg):
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count, rs_universe_version, rs_universe_hash)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17', '2026-04-20',
                           NULL, 0, 0, 0, 0, 0, 0, 'v1', 'deadbeef')""",
            )
            eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date, action_session_date,
                    state, lease_token)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00', 'scheduled',
                           '2026-04-17', '2026-04-20', 'complete', 't')""",
            )
    finally:
        conn.close()


def test_get_root_renders(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _seed_minimal_dashboard_state(cfg)

    # Avoid hitting real yfinance.
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    client = TestClient(app)
    r = client.get("/")
    assert r.status_code == 200
    assert "Today's decisions" in r.text
    assert "Watchlist" in r.text
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/web/test_routes/test_dashboard_route.py -v`
Expected: 404 Not Found (no route yet) → assertion fails.

- [ ] **Step 3: Implement `swing/web/routes/dashboard.py`**

```python
"""GET / — the main dashboard route."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates

from swing.web.view_models.dashboard import build_dashboard

router = APIRouter()


def _templates(request: Request) -> Jinja2Templates:
    """Lazy-built, per-app templates object (avoids re-scanning the dir)."""
    app = request.app
    tpls = getattr(app.state, "_jinja_templates", None)
    if tpls is None:
        tpls = Jinja2Templates(directory=str(app.state.templates_dir))
        app.state._jinja_templates = tpls
    return tpls


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    vm = build_dashboard(cfg=cfg, cache=cache, executor=executor)
    return _templates(request).TemplateResponse(
        "dashboard.html.j2", {"request": request, "vm": vm},
    )
```

- [ ] **Step 4: Wire the router into `create_app`**

Modify `swing/web/app.py` — after the mounts, before `return app`:

```python
    from swing.web.routes import dashboard as dashboard_route
    app.include_router(dashboard_route.router)
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/web/test_routes/test_dashboard_route.py -v`
Expected: 1 PASS.

- [ ] **Step 6: Commit**

```bash
git add swing/web/routes/dashboard.py swing/web/app.py tests/web/test_routes/test_dashboard_route.py
git commit -m "feat(web): GET / dashboard route"
```

---

## Task 12: Vendor HTMX 2.x + minimal `app.css`

**Files:**
- Create: `swing/web/static/htmx.min.js` (vendored)
- Modify: `swing/web/static/app.css` (minimal styling)

Vendoring HTMX avoids a CDN dependency on a localhost tool.

- [ ] **Step 1: Download HTMX 2.x with integrity verification**

HTMX 2.0.3 from unpkg. Verify the SHA-256 after download — the asset is vendored into the repo and must be reproducible across installs (R1 Minor 1).

```bash
curl -fsSL https://unpkg.com/htmx.org@2.0.3/dist/htmx.min.js \
  -o swing/web/static/htmx.min.js
# Record the checksum in the commit message and in a sidecar file.
sha256sum swing/web/static/htmx.min.js > swing/web/static/htmx.min.js.sha256
wc -c swing/web/static/htmx.min.js
```
Expected: ~50KB. Commit both `htmx.min.js` AND `htmx.min.js.sha256` so a future verifier can reproduce. If unpkg ever serves a different payload for the same version, the commit diff will catch it.

The SHA-256 sidecar is a checked-in manifest; upgrading HTMX means overwriting the JS file AND regenerating the sidecar in the same commit.

- [ ] **Step 2: Write minimal CSS**

```css
/* swing/web/static/app.css */
* { box-sizing: border-box; }
body { font-family: system-ui, sans-serif; margin: 1rem; }
.topbar { display: flex; gap: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid #ccc; }
.topbar a { text-decoration: none; color: #333; }
.banner { padding: 0.5rem 1rem; margin: 0.5rem 0; border-radius: 4px; }
.banner-stale { background: #fff3cd; border: 1px solid #ffeaa7; }
.banner-degraded { background: #f8d7da; border: 1px solid #f5c6cb; }
#status-strip { display: flex; gap: 1rem; margin: 1rem 0; }
.tile { flex: 1; padding: 0.75rem; border: 1px solid #ddd; border-radius: 4px; }
.tile .label { font-size: 0.75rem; text-transform: uppercase; color: #666; }
.tile .value { font-size: 1.25rem; font-weight: bold; }
.tile .rationale { font-size: 0.85rem; color: #555; }
.decisions { background: #fff8e1; padding: 1rem; border-radius: 4px; margin: 1rem 0; }
.stale { color: #b00; font-size: 0.75rem; }
table { border-collapse: collapse; width: 100%; }
th, td { text-align: left; padding: 0.25rem 0.5rem; border-bottom: 1px solid #eee; }
```

- [ ] **Step 3: Verify via `TestClient`**

Run `tests/web/test_app_smoke.py::test_create_app_mounts_static` again:
```bash
python -m pytest tests/web/test_app_smoke.py::test_create_app_mounts_static -v
```
Expected: PASS (was already passing, but now serves a real non-empty file).

- [ ] **Step 4: Commit**

```bash
git add swing/web/static
git commit -m "chore(web): vendor HTMX 2.0.3 + minimal app.css"
```

---

## Task 13: Watchlist view-model + watchlist templates

**Files:**
- Create: `swing/web/view_models/watchlist.py`
- Create: `swing/web/templates/watchlist.html.j2`
- Create: `swing/web/templates/partials/watchlist_expanded.html.j2`
- Test: `tests/web/test_view_models/test_watchlist.py`

Full `/watchlist` page shows archive + live rows. The expanded partial is served via HTMX swap.

- [ ] **Step 1: Write the failing VM test**

```python
# tests/web/test_view_models/test_watchlist.py
"""WatchlistVM shape + expand helper."""
from __future__ import annotations

from unittest.mock import MagicMock

from swing.data.db import connect
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import upsert_watchlist_entry


def test_build_watchlist_shape(seeded_db, monkeypatch):
    from swing.web.view_models.watchlist import WatchlistVM, build_watchlist
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from datetime import datetime

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(ticker="AAPL", price=180.5, asof=datetime.now(),
                                   is_stale=False, source="live")
        })
    monkeypatch.setattr(cache, "is_degraded", lambda: False)

    vm = build_watchlist(cfg=cfg, cache=cache, executor=None)
    assert isinstance(vm, WatchlistVM)
    assert len(vm.rows) == 1
    assert vm.rows[0].ticker == "AAPL"
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/web/test_view_models/test_watchlist.py -v`
Expected: ImportError.

- [ ] **Step 3: Implement `swing/web/view_models/watchlist.py`**

```python
"""WatchlistVM + builder."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Mapping

from swing.config import Config
from swing.data.db import connect
from swing.data.models import Candidate, WatchlistEntry
from swing.data.repos.candidates import fetch_candidates_for_run
from swing.data.repos.watchlist import list_active_watchlist
from swing.evaluation.dates import action_session_for_run
from swing.web.price_cache import PriceCache, PriceSnapshot
from swing.web.view_models.dashboard import _flag_tags, _sort_by_proximity


@dataclass(frozen=True)
class WatchlistVM:
    session_date: str
    rows: list[WatchlistEntry]
    watchlist_last_prices: Mapping[str, PriceSnapshot]
    flag_tags: Mapping[str, tuple[str, ...]]
    candidates_by_ticker: Mapping[str, Candidate]
    prices_generated_at: str
    price_source_degraded: bool
    price_source_degraded_until: str | None
    stale_banner: str | None = None   # placeholder — populated only on the main dashboard


@dataclass(frozen=True)
class WatchlistExpandedVM:
    ticker: str
    entry: WatchlistEntry
    candidate: Candidate | None
    last_price: PriceSnapshot | None
    data_asof_date: str | None   # for /charts/<date>/<ticker>.png


def build_watchlist(*, cfg: Config, cache: PriceCache, executor) -> WatchlistVM:
    now = datetime.now()
    conn = connect(cfg.paths.db_path)
    try:
        rows = _sort_by_proximity(list_active_watchlist(conn))
        row = conn.execute("SELECT id FROM evaluation_runs ORDER BY run_ts DESC LIMIT 1").fetchone()
        candidates: list[Candidate] = []
        if row is not None:
            candidates = fetch_candidates_for_run(conn, row[0])
    finally:
        conn.close()
    by_ticker = {c.ticker: c for c in candidates}
    prices = cache.get_many(
        [r.ticker for r in rows],
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )
    degraded_until = cache.degraded_until()
    return WatchlistVM(
        session_date=action_session_for_run(now).isoformat(),
        rows=list(rows),
        watchlist_last_prices={r.ticker: prices[r.ticker] for r in rows if r.ticker in prices},
        flag_tags=_flag_tags(by_ticker),
        candidates_by_ticker=by_ticker,
        prices_generated_at=now.isoformat(timespec="seconds"),
        price_source_degraded=cache.is_degraded(),
        price_source_degraded_until=(
            degraded_until.isoformat(timespec="seconds") if degraded_until else None
        ),
    )


def build_watchlist_expanded(
    *, cfg: Config, cache: PriceCache, ticker: str,
) -> WatchlistExpandedVM | None:
    conn = connect(cfg.paths.db_path)
    try:
        rows = list_active_watchlist(conn)
        row = next((r for r in rows if r.ticker == ticker), None)
        if row is None:
            return None
        eval_row = conn.execute(
            "SELECT id, data_asof_date FROM evaluation_runs ORDER BY run_ts DESC LIMIT 1"
        ).fetchone()
        candidate = None
        data_asof = None
        if eval_row is not None:
            data_asof = eval_row[1]
            for c in fetch_candidates_for_run(conn, eval_row[0]):
                if c.ticker == ticker:
                    candidate = c
                    break
    finally:
        conn.close()
    snap = cache.get(ticker)
    return WatchlistExpandedVM(
        ticker=ticker, entry=row, candidate=candidate,
        last_price=snap, data_asof_date=data_asof,
    )
```

- [ ] **Step 4: Create `watchlist.html.j2`**

```html
{% extends "base.html.j2" %}
{% block content %}
  <h1>Watchlist</h1>
  <table class="watchlist">
    <thead><tr>
      <th></th><th>Ticker</th><th>Last</th><th>Pivot</th><th>% to pivot</th><th>ADR</th><th>Tags</th>
    </tr></thead>
    <tbody>
      {% for w in vm.rows %}
        {% set price = vm.watchlist_last_prices.get(w.ticker) %}
        {% set tags = vm.flag_tags.get(w.ticker, ()) %}
        {% include "partials/watchlist_row.html.j2" %}
      {% endfor %}
    </tbody>
  </table>
{% endblock %}
```

- [ ] **Step 5: Create `partials/watchlist_expanded.html.j2`**

```html
{#- Expects: expanded (WatchlistExpandedVM) -#}
<tr id="watchlist-row-{{ expanded.ticker }}" class="expanded">
  <td colspan="7">
    <h3>{{ expanded.ticker }}</h3>
    {% if expanded.last_price %}
      <p>Last: ${{ '%.2f' | format(expanded.last_price.price) }}
         {% if expanded.last_price.is_stale %}<span class="stale">(stale)</span>{% endif %}
      </p>
    {% endif %}
    {% if expanded.candidate %}
      <h4>Trend Template</h4>
      <ul class="tt-grid">
        {% for cr in expanded.candidate.criteria if cr.layer == 'trend_template' %}
          <li class="{{ cr.result }}">{{ cr.criterion_name }}: {{ cr.result }}</li>
        {% endfor %}
      </ul>
      <h4>VCP</h4>
      <ul class="vcp-grid">
        {% for cr in expanded.candidate.criteria if cr.layer == 'vcp' %}
          <li class="{{ cr.result }}">{{ cr.criterion_name }}: {{ cr.result }}</li>
        {% endfor %}
      </ul>
    {% endif %}
    {% if expanded.data_asof_date %}
      <img src="/charts/{{ expanded.data_asof_date }}/{{ expanded.ticker }}.png"
           alt="Chart {{ expanded.ticker }}"
           onerror="this.style.display='none'; this.nextElementSibling.style.display='block';">
      <div class="chart-unavailable" style="display:none">Chart unavailable.</div>
    {% endif %}
    <div class="actions">
      <span title="Log entry: `swing trade entry --ticker {{ expanded.ticker }}`">Log entry (CLI — 3b adds button)</span>
    </div>
  </td>
</tr>
```

- [ ] **Step 6: Run the VM test**

Run: `python -m pytest tests/web/test_view_models/test_watchlist.py -v`
Expected: 1 PASS.

- [ ] **Step 7: Commit**

```bash
git add swing/web/view_models/watchlist.py swing/web/templates/watchlist.html.j2 swing/web/templates/partials/watchlist_expanded.html.j2 tests/web/test_view_models/test_watchlist.py
git commit -m "feat(web): watchlist VM + templates (page + expanded row)"
```

---

## Task 14: `GET /watchlist` + `GET /watchlist/{ticker}/expand` routes

**Files:**
- Create: `swing/web/routes/watchlist.py`
- Modify: `swing/web/app.py` — include the router
- Test: `tests/web/test_routes/test_watchlist_route.py`

- [ ] **Step 1: Write failing tests**

```python
# tests/web/test_routes/test_watchlist_route.py
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import upsert_watchlist_entry
from swing.web.app import create_app


def _seed_one_watchlist(cfg):
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker="AAPL", added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()


def test_get_watchlist_renders(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _seed_one_watchlist(cfg)
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    r = TestClient(app).get("/watchlist")
    assert r.status_code == 200
    assert "AAPL" in r.text


def test_watchlist_expand_htmx(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _seed_one_watchlist(cfg)
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(PriceCache, "get", lambda self, t: None)

    app = create_app(cfg, cfg_path)
    client = TestClient(app)
    r = client.get("/watchlist/AAPL/expand", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "Trend Template" in r.text or "AAPL" in r.text


def test_watchlist_expand_unknown_ticker_404(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    r = TestClient(app).get("/watchlist/NOPE/expand", headers={"HX-Request": "true"})
    assert r.status_code == 404
```

- [ ] **Step 2: Implement `swing/web/routes/watchlist.py`**

```python
"""Watchlist routes."""
from __future__ import annotations

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import HTMLResponse

from swing.web.routes.dashboard import _templates
from swing.web.view_models.watchlist import build_watchlist, build_watchlist_expanded

router = APIRouter()


@router.get("/watchlist", response_class=HTMLResponse)
def watchlist_page(request: Request):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    vm = build_watchlist(cfg=cfg, cache=cache, executor=executor)
    return _templates(request).TemplateResponse(
        "watchlist.html.j2", {"request": request, "vm": vm},
    )


@router.get("/watchlist/{ticker}/expand", response_class=HTMLResponse)
def watchlist_expand(request: Request, ticker: str):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    expanded = build_watchlist_expanded(cfg=cfg, cache=cache, ticker=ticker.upper())
    if expanded is None:
        raise HTTPException(status_code=404, detail=f"ticker {ticker} not on watchlist")
    return _templates(request).TemplateResponse(
        "partials/watchlist_expanded.html.j2",
        {"request": request, "expanded": expanded},
    )
```

- [ ] **Step 3: Wire the router into `create_app`**

Modify `swing/web/app.py` to include the watchlist router:

```python
    from swing.web.routes import dashboard as dashboard_route, watchlist as watchlist_route
    app.include_router(dashboard_route.router)
    app.include_router(watchlist_route.router)
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/web/test_routes/test_watchlist_route.py -v`
Expected: 3 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/routes/watchlist.py swing/web/app.py tests/web/test_routes/test_watchlist_route.py
git commit -m "feat(web): GET /watchlist + /watchlist/{ticker}/expand routes"
```

---

## Task 15: Journal page — VM, template, route

**Files:**
- Create: `swing/web/view_models/journal.py`
- Create: `swing/web/templates/journal.html.j2`
- Create: `swing/web/routes/journal.py`
- Modify: `swing/web/app.py` — include router
- Test: `tests/web/test_view_models/test_journal.py`, `tests/web/test_routes/test_journal_route.py`

Reuses Phase 2's `swing.journal.stats.compute_period_stats` and `swing.journal.flags.detect_behavioral_flags`.

- [ ] **Step 1: Write failing VM test**

```python
# tests/web/test_view_models/test_journal.py
from __future__ import annotations


def test_build_journal_default_period_month(seeded_db):
    from swing.web.view_models.journal import JournalVM, build_journal
    cfg, _ = seeded_db
    vm = build_journal(cfg=cfg, period="month")
    assert isinstance(vm, JournalVM)
    assert vm.period == "month"
    # Empty DB → stats show zeros.
    assert vm.stats.trades_count == 0


def test_build_journal_rejects_unknown_period(seeded_db):
    from swing.web.view_models.journal import build_journal
    import pytest
    cfg, _ = seeded_db
    with pytest.raises(ValueError, match="period"):
        build_journal(cfg=cfg, period="fortnight")
```

- [ ] **Step 2: Implement `swing/web/view_models/journal.py`**

```python
"""JournalVM + builder."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Literal

from swing.config import Config
from swing.data.db import connect
from swing.data.repos.trades import list_all_exits, list_all_trades
from swing.journal.flags import detect_behavioral_flags
from swing.journal.stats import compute_period_stats, PeriodStats

Period = Literal["week", "month", "quarter", "ytd", "all"]

_ALLOWED_PERIODS: frozenset[str] = frozenset({"week", "month", "quarter", "ytd", "all"})


@dataclass(frozen=True)
class JournalVM:
    period: str
    stats: PeriodStats
    flags: list          # list[BehavioralFlag] from Phase 2
    trades: list         # list[Trade]


def build_journal(*, cfg: Config, period: str = "month") -> JournalVM:
    if period not in _ALLOWED_PERIODS:
        raise ValueError(
            f"unknown period {period!r}; allowed: {sorted(_ALLOWED_PERIODS)}"
        )
    today = date.today()
    start = _period_start(today, period)
    conn = connect(cfg.paths.db_path)
    try:
        trades = list_all_trades(conn)
        exits = list_all_exits(conn)
        stats = compute_period_stats(
            trades=trades, exits=exits,
            period_start=start, period_end=today,
        )
        flags = detect_behavioral_flags(trades=trades, exits=exits, cfg=cfg)
    finally:
        conn.close()
    # Filter trades shown in table to the selected period.
    def _closed_in_period(trade) -> bool:
        if start is None:
            return True
        last_exit = max((e.exit_date for e in exits if e.trade_id == trade.id), default=None)
        return last_exit is not None and last_exit >= start.isoformat()
    return JournalVM(period=period, stats=stats, flags=list(flags),
                     trades=[t for t in trades if _closed_in_period(t)])


def _period_start(today: date, period: str) -> date | None:
    if period == "week":
        return today - timedelta(days=7)
    if period == "month":
        return today - timedelta(days=30)
    if period == "quarter":
        return today - timedelta(days=90)
    if period == "ytd":
        return date(today.year, 1, 1)
    return None   # "all"
```

- [ ] **Step 3: Create `journal.html.j2`**

```html
{% extends "base.html.j2" %}
{% block content %}
  <h1>Journal</h1>
  <nav class="period-selector">
    {# Period keys are rolling day-count approximations, not calendar months/quarters.
       Labels are renamed to avoid the semantic mismatch (R1 Minor 3). #}
    {% set _labels = {'week': 'Last 7d', 'month': 'Last 30d', 'quarter': 'Last 90d', 'ytd': 'YTD', 'all': 'All'} %}
    {% for p in ('week','month','quarter','ytd','all') %}
      <a href="/journal?period={{ p }}" class="{{ 'active' if p == vm.period else '' }}">{{ _labels[p] }}</a>
    {% endfor %}
  </nav>
  <section class="stats">
    <div>Trades: {{ vm.stats.trades_count }}</div>
    <div>Win rate: {{ '%.1f' | format(vm.stats.win_rate_pct) }}%</div>
    <div>Expectancy: {{ '%.2f' | format(vm.stats.expectancy_r) }}R</div>
    <div>Total R: {{ '%.2f' | format(vm.stats.total_r) }}</div>
    <div>Streak: {{ vm.stats.streak }}</div>
  </section>
  <section class="flags">
    <h2>Behavioral flags</h2>
    {% for f in vm.flags %}
      <div>{{ f.rule }}: {{ f.narrative }}</div>
    {% else %}
      <p>No flags.</p>
    {% endfor %}
  </section>
  <section class="trades">
    <h2>Trades ({{ vm.trades | length }})</h2>
    <table>
      <thead><tr><th>Ticker</th><th>Entry</th><th>Status</th></tr></thead>
      <tbody>
        {% for t in vm.trades %}
          <tr><td>{{ t.ticker }}</td><td>{{ t.entry_date }}</td><td>{{ t.status }}</td></tr>
        {% endfor %}
      </tbody>
    </table>
  </section>
{% endblock %}
```

Note: the base template references `vm.session_date`, `vm.stale_banner`, and `vm.price_source_degraded` — which `JournalVM` does not have. Either:
- (a) Add those fields to `JournalVM` with sensible defaults, OR
- (b) Make the base template guards tolerate missing attributes.

Choose (a) for safety — add to `JournalVM`:

```python
# Append to JournalVM fields:
    session_date: str = ""
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
```

And populate `session_date` in `build_journal`:

```python
    return JournalVM(
        period=period, stats=stats, flags=list(flags),
        trades=[...],
        session_date=today.isoformat(),
    )
```

Apply the same treatment to WatchlistVM and PipelineVM so the base template's banner guards work uniformly (WatchlistVM already has `stale_banner`; add the rest).

- [ ] **Step 4: Implement `swing/web/routes/journal.py`**

```python
"""Journal route."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from swing.web.routes.dashboard import _templates
from swing.web.view_models.journal import build_journal

router = APIRouter()


@router.get("/journal", response_class=HTMLResponse)
def journal_page(request: Request, period: str = Query("month")):
    cfg = request.app.state.cfg
    try:
        vm = build_journal(cfg=cfg, period=period)
    except ValueError:
        raise
    return _templates(request).TemplateResponse(
        "journal.html.j2", {"request": request, "vm": vm},
    )
```

Include in `swing/web/app.py` alongside the dashboard + watchlist routers.

- [ ] **Step 5: Write the route test**

```python
# tests/web/test_routes/test_journal_route.py
from fastapi.testclient import TestClient

from swing.web.app import create_app


def test_get_journal_default_period(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    r = TestClient(app).get("/journal")
    assert r.status_code == 200
    assert "Journal" in r.text


def test_get_journal_with_period(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    r = TestClient(app).get("/journal?period=week")
    assert r.status_code == 200
    assert "week" in r.text.lower()


def test_get_journal_invalid_period(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    r = TestClient(app).get("/journal?period=fortnight")
    assert r.status_code == 500 or r.status_code == 400   # error surfaces
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/web/test_view_models/test_journal.py tests/web/test_routes/test_journal_route.py -v`
Expected: 5 PASS.

- [ ] **Step 7: Commit**

```bash
git add swing/web/view_models/journal.py swing/web/view_models/watchlist.py swing/web/view_models/dashboard.py swing/web/templates/journal.html.j2 swing/web/routes/journal.py swing/web/app.py tests/web/test_view_models/test_journal.py tests/web/test_routes/test_journal_route.py
git commit -m "feat(web): journal page (VM + template + route + shared banner fields)"
```

---

## Task 16: Pipeline page — `PipelineVM` + `GET /pipeline` route

**Files:**
- Create: `swing/web/view_models/pipeline.py`
- Create: `swing/web/templates/pipeline.html.j2`
- Create: `swing/web/templates/partials/pipeline_progress.html.j2`
- Create: `swing/web/routes/pipeline.py` (GET only; POST handlers arrive in Tasks 17–19)
- Test: `tests/web/test_routes/test_pipeline_route.py`

`GET /pipeline` shows the last N runs + a Run now button + a placeholder `#run-panel` for HTMX swaps.

- [ ] **Step 1: Write failing tests**

```python
# tests/web/test_routes/test_pipeline_route.py
from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app


def _seed_pipeline_history(cfg):
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.executemany(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date, action_session_date,
                    state, lease_token)
                   VALUES (?, ?, 'scheduled', ?, ?, 'complete', ?)""",
                [
                    ("2026-04-17T21:49:00", "2026-04-17T21:55:00", "2026-04-17", "2026-04-20", "tok-1"),
                    ("2026-04-16T21:49:00", "2026-04-16T21:55:00", "2026-04-16", "2026-04-17", "tok-2"),
                ],
            )
    finally:
        conn.close()


def test_get_pipeline_page(seeded_db):
    cfg, cfg_path = seeded_db
    _seed_pipeline_history(cfg)
    app = create_app(cfg, cfg_path)
    r = TestClient(app).get("/pipeline")
    assert r.status_code == 200
    assert "tok-1" in r.text or "2026-04-17" in r.text
    assert "Run now" in r.text
```

- [ ] **Step 2: Implement the VM**

```python
# swing/web/view_models/pipeline.py
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from swing.config import Config
from swing.data.db import connect
from swing.data.models import PipelineRun


@dataclass(frozen=True)
class PipelineVM:
    session_date: str
    recent_runs: list[PipelineRun]
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None


def build_pipeline(*, cfg: Config, limit: int = 10) -> PipelineVM:
    from swing.data.repos.pipeline import list_recent_runs
    conn = connect(cfg.paths.db_path)
    try:
        runs = list_recent_runs(conn, limit=limit)
    finally:
        conn.close()
    return PipelineVM(
        session_date=datetime.now().date().isoformat(),
        recent_runs=list(runs),
    )
```

- [ ] **Step 3: Implement the template**

```html
{#- swing/web/templates/pipeline.html.j2 -#}
{% extends "base.html.j2" %}
{% block content %}
  <h1>Pipeline</h1>
  <button hx-post="/pipeline/run" hx-target="#run-panel" hx-swap="innerHTML"
          hx-headers='{"HX-Request": "true"}'>Run now</button>
  <div id="run-panel"></div>
  <h2>Recent runs</h2>
  <table>
    <thead><tr>
      <th>ID</th><th>State</th><th>Started</th><th>Finished</th><th>Session</th><th>Trigger</th>
    </tr></thead>
    <tbody>
      {% for r in vm.recent_runs %}
        <tr>
          <td>{{ r.id }}</td>
          <td>{{ r.state }}</td>
          <td>{{ r.started_ts }}</td>
          <td>{{ r.finished_ts or '—' }}</td>
          <td>{{ r.action_session_date }}</td>
          <td>{{ r.trigger }}</td>
        </tr>
      {% endfor %}
    </tbody>
  </table>
{% endblock %}
```

- [ ] **Step 4: Implement the progress partial**

```html
{#- swing/web/templates/partials/pipeline_progress.html.j2 -#}
{#- Expects: run (PipelineRun or None), error_text (str or None), poll_interval (int) -#}
{% if error_text %}
  <div class="banner banner-degraded">{{ error_text }}</div>
{% elif run and run.state == 'running' %}
  <div id="pipeline-progress"
       hx-get="/pipeline/status/{{ run.id }}"
       hx-trigger="every {{ poll_interval }}s"
       hx-swap="outerHTML"
       hx-headers='{"HX-Request": "true"}'>
    <div class="progress-strip">
      Step: {{ run.current_step or 'starting…' }}
      (weather: {{ run.weather_status or '—' }},
       evaluation: {{ run.evaluation_status or '—' }},
       watchlist: {{ run.watchlist_status or '—' }})
    </div>
  </div>
{% else %}
  <div id="pipeline-progress" class="terminal">
    Run #{{ run.id }} {{ run.state }}.
    {% if run.error_message %}Error: {{ run.error_message }}.{% endif %}
  </div>
{% endif %}
```

- [ ] **Step 5: Implement the route (GET only for now)**

```python
# swing/web/routes/pipeline.py
"""Pipeline routes. POST handlers land in Tasks 17–19."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from swing.web.routes.dashboard import _templates
from swing.web.view_models.pipeline import build_pipeline

router = APIRouter()


@router.get("/pipeline", response_class=HTMLResponse)
def pipeline_page(request: Request):
    cfg = request.app.state.cfg
    vm = build_pipeline(cfg=cfg)
    return _templates(request).TemplateResponse(
        "pipeline.html.j2", {"request": request, "vm": vm},
    )
```

Include in `swing/web/app.py`.

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/web/test_routes/test_pipeline_route.py -v`
Expected: 1 PASS.

- [ ] **Step 7: Commit**

```bash
git add swing/web/view_models/pipeline.py swing/web/templates/pipeline.html.j2 swing/web/templates/partials/pipeline_progress.html.j2 swing/web/routes/pipeline.py swing/web/app.py tests/web/test_routes/test_pipeline_route.py
git commit -m "feat(web): GET /pipeline page + progress partial (no POST yet)"
```

---

## Task 17: `POST /pipeline/run` — subprocess launch + active-run detection

**Files:**
- Modify: `swing/web/routes/pipeline.py`
- Modify: `swing/web/templates/partials/pipeline_progress.html.j2` (already supports error_text)
- Test: extend `tests/web/test_routes/test_pipeline_route.py`

Spawns `swing pipeline run --manual` as a detached subprocess. Polls `find_active_run` for up to 2s, inspecting `proc.poll()` for immediate child-exit failures.

- [ ] **Step 1: Append failing tests**

```python
def test_post_pipeline_run_spawns_subprocess(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    # Pre-insert the 'running' row that the child would create; the route's
    # find_active_run loop picks it up immediately.
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, trigger, data_asof_date, action_session_date,
                    state, lease_token, lease_heartbeat_ts)
                   VALUES ('2026-04-17T21:49:00', 'manual', '2026-04-17',
                           '2026-04-20', 'running', 'subprocess-tok',
                           '2026-04-17T21:49:00')""",
            )
    finally:
        conn.close()

    spawned = {}

    class FakeProc:
        pid = 4242
        returncode = None
        def poll(self):
            return None  # still running

    def fake_popen(cmd, **kwargs):
        spawned["cmd"] = cmd
        return FakeProc()

    monkeypatch.setattr("subprocess.Popen", fake_popen)

    app = create_app(cfg, cfg_path)
    r = TestClient(app).post("/pipeline/run", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "cmd" in spawned
    assert "--config" in spawned["cmd"]
    assert str(cfg_path) in spawned["cmd"]
    assert "pipeline" in spawned["cmd"]
    assert "run" in spawned["cmd"]
    assert "--manual" in spawned["cmd"]
    # Progress partial is returned.
    assert "pipeline-progress" in r.text or "state" in r.text.lower()


def test_post_pipeline_run_503_when_cfg_path_missing(seeded_db):
    cfg, _ = seeded_db
    app = create_app(cfg, None)
    r = TestClient(app).post("/pipeline/run", headers={"HX-Request": "true"})
    assert r.status_code == 503
    assert "config" in r.text.lower()


def test_post_pipeline_run_detects_stale_heartbeat(seeded_db):
    cfg, cfg_path = seeded_db
    from datetime import datetime, timedelta
    from swing.data.db import connect
    stale_ts = (datetime.now() - timedelta(seconds=900)).isoformat(timespec="seconds")
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, trigger, data_asof_date, action_session_date,
                    state, lease_token, lease_heartbeat_ts)
                   VALUES (?, 'scheduled', '2026-04-17', '2026-04-20',
                           'running', 'stale-tok', ?)""",
                (stale_ts, stale_ts),
            )
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    r = TestClient(app).post("/pipeline/run", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "force-clear" in r.text.lower() or "stuck" in r.text.lower()


def test_post_pipeline_run_detects_early_child_exit(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db

    class FakeProc:
        pid = 5252
        returncode = 1
        def poll(self):
            return 1  # exited immediately with code 1

    monkeypatch.setattr("subprocess.Popen", lambda cmd, **kw: FakeProc())

    app = create_app(cfg, cfg_path)
    r = TestClient(app).post("/pipeline/run", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "exited early" in r.text.lower() or "code=1" in r.text
```

- [ ] **Step 2: Implement `POST /pipeline/run`**

Add to `swing/web/routes/pipeline.py`:

```python
import logging
import subprocess
import sys
import time
from datetime import datetime

from fastapi import HTTPException
from fastapi.responses import HTMLResponse

from swing.data.db import connect
from swing.data.repos.pipeline import find_active_run

log = logging.getLogger(__name__)

_STALE_HEARTBEAT_SECONDS = 300   # mirrors spec §5.6 default


@router.post("/pipeline/run", response_class=HTMLResponse)
def pipeline_run(request: Request):
    cfg = request.app.state.cfg
    cfg_path = request.app.state.cfg_path
    templates = _templates(request)

    if cfg_path is None:
        return HTMLResponse(
            "Pipeline subprocess launch requires a config-file-backed app startup. "
            "Configure via `swing --config <path> web`.",
            status_code=503,
        )

    # Existing active run?
    conn = connect(cfg.paths.db_path)
    try:
        active = find_active_run(conn)
    finally:
        conn.close()

    poll_interval = cfg.web.polling_interval_seconds
    if active is not None:
        hb_age = _heartbeat_age_seconds(active.lease_heartbeat_ts)
        if hb_age is not None and hb_age <= _STALE_HEARTBEAT_SECONDS:
            # Fresh heartbeat — show existing progress.
            return templates.TemplateResponse(
                "partials/pipeline_progress.html.j2",
                {"request": request, "run": active, "error_text": None,
                 "poll_interval": poll_interval},
            )
        # Stale heartbeat — explicit manual force-clear required.
        age_min = int((hb_age or 0) // 60)
        return templates.TemplateResponse(
            "partials/pipeline_progress.html.j2",
            {
                "request": request, "run": None,
                "error_text": (
                    f"A previous run is stuck (run #{active.id}, state=running, "
                    f"heartbeat age {age_min}m). A dashboard force-clear button "
                    f"ships in Phase 3b; until then, run `swing pipeline "
                    f"force-clear {active.id} --bypass-staleness-check` in a terminal."
                ),
                "poll_interval": poll_interval,
            },
        )

    # Spawn subprocess.
    cmd = [
        sys.executable, "-m", "swing.cli",
        "--config", str(cfg_path),
        "pipeline", "run", "--manual",
    ]
    log.info("spawning pipeline subprocess: %s", cmd)
    proc = subprocess.Popen(
        cmd, close_fds=True,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
        start_new_session=True,
    )
    log.info("pipeline subprocess started: pid=%d", proc.pid)

    # Wait for the child to acquire its lease (up to 2s).
    deadline = time.monotonic() + 2.0
    run = None
    while time.monotonic() < deadline:
        rc = proc.poll()
        if rc is not None:
            return templates.TemplateResponse(
                "partials/pipeline_progress.html.j2",
                {
                    "request": request, "run": None,
                    "error_text": (
                        f"Pipeline subprocess exited early (code={rc}) before "
                        f"acquiring lease. Check `swing-data/logs/pipeline.log`."
                    ),
                    "poll_interval": poll_interval,
                },
            )
        conn = connect(cfg.paths.db_path)
        try:
            run = find_active_run(conn)
        finally:
            conn.close()
        if run is not None:
            break
        time.sleep(0.05)

    if run is None:
        return templates.TemplateResponse(
            "partials/pipeline_progress.html.j2",
            {
                "request": request, "run": None,
                "error_text": (
                    "Pipeline subprocess did not acquire lease within 2s. "
                    "Check `swing-data/logs/pipeline.log` and "
                    "`swing-data/logs/web.log`."
                ),
                "poll_interval": poll_interval,
            },
        )

    return templates.TemplateResponse(
        "partials/pipeline_progress.html.j2",
        {"request": request, "run": run, "error_text": None,
         "poll_interval": poll_interval},
    )


def _heartbeat_age_seconds(ts: str | None) -> float | None:
    if ts is None:
        return None
    try:
        return (datetime.now() - datetime.fromisoformat(ts)).total_seconds()
    except ValueError:
        return None
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/web/test_routes/test_pipeline_route.py -v`
Expected: 5 PASS (1 from Task 16 + 4 new).

- [ ] **Step 4: Commit**

```bash
git add swing/web/routes/pipeline.py tests/web/test_routes/test_pipeline_route.py
git commit -m "feat(web): POST /pipeline/run — subprocess launch + early-exit detection"
```

---

## Task 18: `GET /pipeline/status/{run_id}` — progress polling

**Files:**
- Modify: `swing/web/routes/pipeline.py`
- Test: extend `tests/web/test_routes/test_pipeline_route.py`

Returns the progress partial; when the run reaches a terminal state, the partial no longer carries `hx-trigger` and polling stops.

- [ ] **Step 1: Append failing tests**

```python
def test_pipeline_status_running_keeps_trigger(seeded_db):
    cfg, cfg_path = seeded_db
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO pipeline_runs
                   (id, started_ts, trigger, data_asof_date, action_session_date,
                    state, lease_token, lease_heartbeat_ts, current_step)
                   VALUES (99, '2026-04-17T21:49:00', 'manual', '2026-04-17',
                           '2026-04-20', 'running', 'tok', '2026-04-17T21:49:00',
                           'evaluate')""",
            )
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    r = TestClient(app).get("/pipeline/status/99", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "hx-trigger" in r.text.lower()
    assert "evaluate" in r.text


def test_pipeline_status_complete_drops_trigger(seeded_db):
    cfg, cfg_path = seeded_db
    from swing.data.db import connect
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO pipeline_runs
                   (id, started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token)
                   VALUES (100, '2026-04-17T21:49:00', '2026-04-17T21:55:00',
                           'manual', '2026-04-17', '2026-04-20', 'complete', 'tok')""",
            )
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    r = TestClient(app).get("/pipeline/status/100", headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "hx-trigger" not in r.text.lower()
    assert "complete" in r.text.lower()


def test_pipeline_status_missing_returns_error(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    r = TestClient(app).get("/pipeline/status/99999", headers={"HX-Request": "true"})
    assert r.status_code == 404
```

- [ ] **Step 2: Implement the handler**

Append to `swing/web/routes/pipeline.py`:

```python
from swing.data.repos.pipeline import find_run


@router.get("/pipeline/status/{run_id}", response_class=HTMLResponse)
def pipeline_status(request: Request, run_id: int):
    cfg = request.app.state.cfg
    templates = _templates(request)
    conn = connect(cfg.paths.db_path)
    try:
        run = find_run(conn, run_id)
    finally:
        conn.close()
    if run is None:
        raise HTTPException(status_code=404, detail=f"run {run_id} not found")
    poll_interval = cfg.web.polling_interval_seconds
    return templates.TemplateResponse(
        "partials/pipeline_progress.html.j2",
        {"request": request, "run": run, "error_text": None,
         "poll_interval": poll_interval},
    )
```

- [ ] **Step 3: Run tests**

Run: `python -m pytest tests/web/test_routes/test_pipeline_route.py -v`
Expected: 8 PASS.

- [ ] **Step 4: Commit**

```bash
git add swing/web/routes/pipeline.py tests/web/test_routes/test_pipeline_route.py
git commit -m "feat(web): GET /pipeline/status/{id} — HTMX progress polling"
```

---

## Task 19: `POST /prices/refresh` + three-region oob swap

**Files:**
- Modify: `swing/web/routes/pipeline.py` (the route lives here alongside the other POSTs)
- Create: `swing/web/templates/partials/prices_refresh_container.html.j2`
- Test: extend pipeline-route tests + add HTMX-interactions test

Invalidates the cache for active tickers, rebuilds the dashboard VM, and responds with an oob container that swaps `#status-strip`, `#open-positions`, and `#watchlist-top5` simultaneously.

- [ ] **Step 1: Write failing test**

```python
# Append to tests/web/test_routes/test_pipeline_route.py

def test_post_prices_refresh_emits_three_oob_regions(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    from swing.web.price_cache import PriceCache
    calls = {"refresh": 0}
    orig_refresh = PriceCache.refresh_all
    def wrapped_refresh(self, tickers):
        calls["refresh"] += 1
        return orig_refresh(self, tickers)
    monkeypatch.setattr(PriceCache, "refresh_all", wrapped_refresh)
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    r = TestClient(app).post("/prices/refresh", headers={"HX-Request": "true"})
    assert r.status_code == 200
    # Three oob containers with the expected IDs.
    for marker in ("status-strip", "open-positions", "watchlist-top5"):
        assert f'id="{marker}"' in r.text
    assert "hx-swap-oob" in r.text
    assert calls["refresh"] == 1
```

- [ ] **Step 2: Create the container partial**

```html
{#- swing/web/templates/partials/prices_refresh_container.html.j2 -#}
<div id="status-strip" hx-swap-oob="true">
  {% include "partials/status_strip.html.j2" %}
</div>
<div id="open-positions" hx-swap-oob="true">
  {% include "partials/open_positions.html.j2" %}
</div>
<div id="watchlist-top5" hx-swap-oob="true">
  <table class="watchlist">
    <thead><tr>
      <th></th><th>Ticker</th><th>Last</th><th>Pivot</th><th>% to pivot</th><th>ADR</th><th>Tags</th>
    </tr></thead>
    <tbody>
      {% for w in vm.watchlist_top5 %}
        {% set price = vm.watchlist_last_prices.get(w.ticker) %}
        {% set tags = vm.flag_tags.get(w.ticker, ()) %}
        {% include "partials/watchlist_row.html.j2" %}
      {% endfor %}
    </tbody>
  </table>
</div>
```

- [ ] **Step 3: Implement the route**

Add to `swing/web/routes/pipeline.py`:

```python
from swing.data.repos.trades import list_open_trades
from swing.data.repos.watchlist import list_active_watchlist
from swing.web.view_models.dashboard import build_dashboard, _sort_by_proximity


@router.post("/prices/refresh", response_class=HTMLResponse)
def prices_refresh(request: Request):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = _templates(request)

    # Collect active tickers.
    conn = connect(cfg.paths.db_path)
    try:
        open_trade_tickers = {t.ticker for t in list_open_trades(conn)}
        top5_tickers = {w.ticker for w in _sort_by_proximity(list_active_watchlist(conn))[:5]}
    finally:
        conn.close()
    active = sorted(open_trade_tickers | top5_tickers | {cfg.rs.benchmark_ticker})
    cache.refresh_all(active)

    vm = build_dashboard(cfg=cfg, cache=cache, executor=executor)
    return templates.TemplateResponse(
        "partials/prices_refresh_container.html.j2",
        {"request": request, "vm": vm},
    )
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/web/test_routes/test_pipeline_route.py -v`
Expected: 9 PASS.

- [ ] **Step 5: Commit**

```bash
git add swing/web/routes/pipeline.py swing/web/templates/partials/prices_refresh_container.html.j2 tests/web/test_routes/test_pipeline_route.py
git commit -m "feat(web): POST /prices/refresh — three-region oob swap"
```

---

## Task 20: Error handling — FastAPI exception handler + request-id middleware + rotating log

**Files:**
- Modify: `swing/web/app.py`
- Create: `swing/web/templates/error.html.j2`
- Create: `swing/web/templates/partials/error_fragment.html.j2`
- Create: `swing/web/middleware/request_id.py`
- Test: `tests/web/test_error_handling.py`

Attaches a `uuid4` request id to every request; 500 responses render `error.html.j2` with the id; a `TimedRotatingFileHandler` writes to `swing-data/logs/web.log`.

- [ ] **Step 1: Write failing tests**

```python
# tests/web/test_error_handling.py
from fastapi import APIRouter, HTTPException
from fastapi.testclient import TestClient

from swing.web.app import create_app


def test_500_on_repo_error_renders_error_page(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)

    @app.get("/_explode")
    def _explode():
        raise RuntimeError("synthetic boom")

    r = TestClient(app, raise_server_exceptions=False).get("/_explode")
    assert r.status_code == 500
    # Error page carries a request-id for log correlation.
    assert "request" in r.text.lower()
    # Error fragment body mentions the underlying message.
    assert "boom" in r.text.lower() or "error" in r.text.lower()


def test_request_id_header_set_on_every_response(seeded_db):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    r = TestClient(app).get("/", headers={"HX-Request": "true"})
    assert "x-request-id" in (h.lower() for h in r.headers.keys())


def test_htmx_post_error_returns_error_fragment(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)

    @app.post("/_htmx_explode")
    def _hx():
        raise RuntimeError("htmx boom")

    r = TestClient(app, raise_server_exceptions=False).post(
        "/_htmx_explode", headers={"HX-Request": "true"},
    )
    assert r.status_code == 500
    # HTMX errors swap into the target; body is a small fragment, not a full page.
    assert "<html" not in r.text.lower()


def test_403_cross_origin_post_still_carries_request_id(seeded_db):
    """R1 Major 4: middleware order must be RequestId OUTERMOST so the 403
    response from OriginGuard still gets X-Request-ID stamped on it. Without
    this, operators cannot grep the CSRF-defense rejections in web.log."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)

    @app.post("/_guarded_probe")
    def _probe():
        return {"ok": True}

    client = TestClient(app)
    r = client.post("/_guarded_probe", headers={"Origin": "http://evil.example"})
    assert r.status_code == 403
    assert "x-request-id" in (h.lower() for h in r.headers.keys())
```

- [ ] **Step 2: Create `error.html.j2`**

```html
{#- swing/web/templates/error.html.j2 -#}
<!doctype html>
<html>
<head><meta charset="utf-8"><title>Dashboard error</title>
<link rel="stylesheet" href="/static/app.css"></head>
<body>
  <h1>Something went wrong</h1>
  <p class="banner banner-degraded">
    Request <code>{{ request_id }}</code> failed: {{ error_message }}
  </p>
  <p>Check <code>swing-data/logs/web.log</code> and grep for <code>{{ request_id }}</code>.</p>
  <a href="/">Back to dashboard</a>
</body>
</html>
```

- [ ] **Step 3: Create `error_fragment.html.j2`**

```html
{#- swing/web/templates/partials/error_fragment.html.j2 -#}
<div class="banner banner-degraded" data-request-id="{{ request_id }}">
  Error (request {{ request_id }}): {{ error_message }}
</div>
```

- [ ] **Step 4: Create `swing/web/middleware/request_id.py`**

```python
"""Request-id middleware and rotating web.log setup."""
from __future__ import annotations

import logging
import uuid
from logging.handlers import TimedRotatingFileHandler
from pathlib import Path

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        rid = str(uuid.uuid4())
        request.state.request_id = rid
        response = await call_next(request)
        response.headers["X-Request-ID"] = rid
        return response


def configure_web_logging(logs_dir: Path) -> None:
    logs_dir.mkdir(parents=True, exist_ok=True)
    handler = TimedRotatingFileHandler(
        filename=str(logs_dir / "web.log"),
        when="D", interval=1, backupCount=7, encoding="utf-8",
    )
    handler.setFormatter(logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
    ))
    root = logging.getLogger()
    # Avoid duplicate handlers if create_app called multiple times (tests).
    for h in list(root.handlers):
        if isinstance(h, TimedRotatingFileHandler) and h.baseFilename == handler.baseFilename:
            return
    root.addHandler(handler)
    root.setLevel(logging.INFO)
```

- [ ] **Step 5: Wire exception handlers into `create_app`**

Add to `swing/web/app.py` (imports + inside `create_app` before `return app`):

```python
from fastapi import Request
from fastapi.responses import HTMLResponse

from swing.web.middleware.request_id import RequestIdMiddleware, configure_web_logging


def _register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(Exception)
    async def _handle_any(request: Request, exc: Exception) -> HTMLResponse:
        rid = getattr(request.state, "request_id", "—")
        log.exception("unhandled error (request_id=%s)", rid)
        from fastapi.templating import Jinja2Templates
        tpls = Jinja2Templates(directory=str(app.state.templates_dir))
        is_htmx = request.headers.get("HX-Request", "").lower() == "true"
        template = "partials/error_fragment.html.j2" if is_htmx else "error.html.j2"
        return tpls.TemplateResponse(
            template,
            {"request": request, "request_id": rid, "error_message": str(exc)},
            status_code=500,
        )
```

Inside `create_app`, BEFORE the existing `app.add_middleware(OriginGuardMiddleware, ...)` line in §2.3's wiring, add RequestId:

```python
    configure_web_logging(cfg.paths.logs_dir)
    app.add_middleware(RequestIdMiddleware)
    # NOTE: already-added OriginGuardMiddleware stays where it is.
    _register_exception_handlers(app)
```

**Middleware execution order (CRITICAL, R1 Major 4).** Starlette/FastAPI's `add_middleware` stack is LIFO: the LAST `add_middleware` call becomes the OUTERMOST layer and runs FIRST. So with the order `RequestId` added FIRST and `OriginGuard` added SECOND (both calls above happen before `_register_exception_handlers`), OriginGuard runs OUTERMOST → its 403 short-circuit returns before RequestId ever sees the request. We want the OPPOSITE: RequestId MUST wrap OriginGuard so that every response — including a 403 for cross-origin — carries `X-Request-ID` for log correlation.

**Correct sequence** (explicit instruction for the implementer):
```python
# In create_app, REPLACE the Task 7 origin-guard add_middleware line with:
app.add_middleware(
    OriginGuardMiddleware,
    bound_host=cfg.web.host, bound_port=cfg.web.port,
)
app.add_middleware(RequestIdMiddleware)  # added AFTER → becomes outermost
configure_web_logging(cfg.paths.logs_dir)
_register_exception_handlers(app)
```
After this edit, execution order for a request is: RequestId (assign id) → OriginGuard (may 403) → route → OriginGuard returns → RequestId stamps `X-Request-ID` on the response → client. A 403 still carries the header.

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/web/test_error_handling.py -v`
Expected: 3 PASS.

- [ ] **Step 7: Commit**

```bash
git add swing/web/middleware/request_id.py swing/web/app.py swing/web/templates/error.html.j2 swing/web/templates/partials/error_fragment.html.j2 tests/web/test_error_handling.py
git commit -m "feat(web): request-id middleware + rotating web.log + error templates"
```

---

## Task 21: Phase 2 regression — `web` extra is truly optional + install smoke

**Files:**
- Test: `tests/web/test_phase2_regression.py`

Two tests: (a) CLI works without the web extra imports; (b) when the web extra is installed, `create_app(cfg)` boots without additional missing imports.

- [ ] **Step 1: Write the tests**

```python
# tests/web/test_phase2_regression.py
"""Confirm the [web] extra is purely additive on top of Phase 2."""
from __future__ import annotations

import importlib

import pytest


PHASE2_PACKAGES = [
    "swing.config",
    "swing.data.db",
    "swing.pipeline",
    "swing.trades.advisory",
    "swing.trades.equity",
    "swing.evaluation.dates",
    "swing.journal.stats",
    "swing.rendering.briefing",
]


def test_phase2_packages_import_without_web_stack(monkeypatch):
    """Simulate `[web]` extra NOT installed: pretend fastapi/uvicorn/jinja2 are missing.

    If any Phase 2 module accidentally imports the web stack, this test fails.
    """
    for hidden in ("fastapi", "uvicorn", "jinja2", "starlette"):
        monkeypatch.setitem(__import__("sys").modules, hidden, None)

    for mod in PHASE2_PACKAGES:
        # Force a fresh import (drop cached copies that may have loaded the stack).
        import sys
        sys.modules.pop(mod, None)
        try:
            importlib.import_module(mod)
        except ImportError as exc:
            if any(s in str(exc) for s in ("fastapi", "uvicorn", "jinja2", "starlette")):
                pytest.fail(
                    f"Phase 2 module {mod} imports the web stack (via: {exc})"
                )
            raise


def test_web_extra_install_starts_app(test_cfg):
    """With the web extra installed (this test already running through pytest
    under the [web] extra), create_app must boot without ImportError."""
    from swing.web.app import create_app
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    assert app is not None
    assert app.state.cfg is cfg


def test_cli_import_does_not_pull_in_web_stack(monkeypatch):
    """Proves `from swing.cli import main` does not transitively import
    fastapi/uvicorn/jinja2/starlette. Regression guard for R1 Major 3: the
    base install must continue to run the CLI even without the [web] extra.

    The test works by replacing the web-stack modules with None in
    sys.modules BEFORE importing swing.cli fresh. If swing.cli (or any
    module it transitively imports at module-import time) touches one of
    those names, Python will surface an ImportError during import."""
    import sys
    for hidden in ("fastapi", "uvicorn", "jinja2", "starlette"):
        monkeypatch.setitem(sys.modules, hidden, None)
    # Drop any cached Phase 2 / CLI modules so the import goes through fresh.
    for name in list(sys.modules):
        if name == "swing" or name.startswith("swing."):
            monkeypatch.delitem(sys.modules, name, raising=False)
    # Clean import — must succeed regardless of the [web] extra.
    importlib.import_module("swing.cli")


def test_cli_help_lists_all_subcommands_without_web_stack(monkeypatch, capsys):
    """Even with the web stack hidden, `swing --help` must enumerate every
    subcommand (including `web`, because the command's backing import is
    inside its function body, not at module top). Proves the lazy-import
    contract from T8."""
    import sys
    for hidden in ("fastapi", "uvicorn", "jinja2", "starlette"):
        monkeypatch.setitem(sys.modules, hidden, None)
    for name in list(sys.modules):
        if name == "swing" or name.startswith("swing."):
            monkeypatch.delitem(sys.modules, name, raising=False)

    from click.testing import CliRunner
    from swing.cli import main
    r = CliRunner().invoke(main, ["--help"])
    assert r.exit_code == 0
    assert "web" in r.output.lower()
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/web/test_phase2_regression.py -v`
Expected: 2 PASS.

- [ ] **Step 3: Commit**

```bash
git add tests/web/test_phase2_regression.py
git commit -m "test(web): phase 2 regression — web extra is purely additive"
```

---

## Task 22: Full dashboard integration smoke test + stale-banner scenarios

**Files:**
- Test: `tests/web/test_dashboard_integration.py`

End-to-end against a seeded DB with Phase 2-style data. Verifies the three stale-banner states.

- [ ] **Step 1: Write the tests**

```python
# tests/web/test_dashboard_integration.py
from __future__ import annotations

from datetime import date

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.web.app import create_app


def _seed_evaluation(cfg, *, data_asof: str, action_session: str) -> int:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count, rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 0, 0, 0, 0, 0, 0, 'v1', 'hash')""",
                ("2026-04-17T21:49:00", data_asof, action_session),
            )
            return cur.lastrowid
    finally:
        conn.close()


def _seed_pipeline_run(cfg, *, state: str, action_session: str) -> None:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date, action_session_date,
                    state, lease_token)
                   VALUES (?, ?, 'scheduled', ?, ?, ?, ?)""",
                ("2026-04-17T21:49:00", "2026-04-17T21:55:00",
                 "2026-04-17", action_session, state, "tok"),
            )
    finally:
        conn.close()


def test_dashboard_no_stale_banner_when_run_is_current(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    from swing.evaluation.dates import action_session_for_run
    from datetime import datetime
    current_session = action_session_for_run(datetime.now()).isoformat()

    _seed_evaluation(cfg, data_asof="2026-04-17", action_session=current_session)
    _seed_pipeline_run(cfg, state="complete", action_session=current_session)

    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    r = TestClient(app).get("/")
    assert r.status_code == 200
    assert "banner-stale" not in r.text


def test_dashboard_shows_stale_banner_when_run_is_old(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db
    _seed_pipeline_run(cfg, state="complete", action_session="1999-01-01")

    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    r = TestClient(app).get("/")
    assert r.status_code == 200
    assert "banner-stale" in r.text


def test_dashboard_renders_degraded_banner_when_cache_degraded(seeded_db, monkeypatch):
    cfg, cfg_path = seeded_db

    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: True)
    from datetime import datetime, timedelta
    fake_until = datetime.now() + timedelta(seconds=30)
    monkeypatch.setattr(PriceCache, "degraded_until", lambda self: fake_until)

    app = create_app(cfg, cfg_path)
    r = TestClient(app).get("/")
    assert r.status_code == 200
    assert "banner-degraded" in r.text
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/web/test_dashboard_integration.py -v`
Expected: 3 PASS.

- [ ] **Step 3: Full sweep — regression check**

Run: `python -m pytest -m "not slow" -q`
Expected: 287 (existing Phase 2) + ~55 new = **~342 PASS** (R1 Minor 4).

- [ ] **Step 4: Commit**

```bash
git add tests/web/test_dashboard_integration.py
git commit -m "test(web): dashboard integration smoke + 3 stale-banner scenarios"
```

---

## Self-Review

### Spec coverage

| Spec section | Task(s) |
|---|---|
| §2.1 Package layout | T3 (skeleton), T20 (middleware dirs populated) |
| §2.2 Layering invariants | enforced by task structure — routes are thin, repos read-only |
| §2.3 Startup sequence | T7 (lifespan + mounts), T8 (CLI + run_server) |
| §2.4 Binding + origin guard | T4 (guard), T8 (loopback refusal), accepted-header matrix is guard's contract |
| §2.5 `[web]` config section | T1 |
| §2.6 `web` optional extra | T2, T21 |
| §3.1 `create_app` | T3 (stub) + T7 (full) |
| §3.2 `PriceCache` + circuit breaker | T5 (core) + T6 (batch + breaker) + T7 (app wiring) |
| §3.3 `DashboardVM` | T9 (dashboard) + T13 (watchlist) + T15 (journal VM share banner fields) + T16 (pipeline VM) |
| §3.4 Route handlers | T11, T14, T15, T16–T19 |
| §3.5 Templates | T10 (base + dashboard + partials), T13 (watchlist), T15 (journal), T16 (pipeline), T20 (error) |
| §4.1 GET / | T11 |
| §4.2 GET /watchlist/{ticker}/expand | T14 |
| §4.3 POST /prices/refresh | T19 |
| §4.4 POST /pipeline/run + GET /pipeline/status/{id} | T17 + T18 |
| §4.5 Navigation | T10 (topbar), T15 (journal period selector) |
| §5.1 Error-origin table | T20 (exception handler + chart onerror in T13/T10) |
| §5.2 Structured logging | T20 (TimedRotatingFileHandler) |
| §5.3 Stale-banner policy | T9 (compute banner in VM), T10 (render partial), T22 (integration tests) |
| §5.4 Concurrent browser tabs | covered by PriceCache lock (T5, T6) + `acquire_lease` (Phase 2 dep) |
| §5.5 NYSE-only assumption | T5 `market_hours_now()` uses XNYS |
| §6.1–6.5 Testing | T3 (fixtures), T4–T22 (per-tier tests), T21 (regression) |
| §6.6 Performance expectations | not asserted (documented-only) |
| §7 Out of scope | no tasks — intentional |
| §8 Decisions locked | all honored via task choices |
| §9 Success criteria | verified in aggregate by T22 full sweep |

No gaps identified.

### Placeholder scan

Searched for "TBD", "TODO", "implement later", "add appropriate error handling", "similar to Task N", "…fill in…". None present. A few tasks note implementation specifics that depend on Phase 2 signatures (e.g., T9 mentions `compute_all_suggestions` may need minor adaptation); those call out the exact Phase 2 source file to consult rather than deferring the decision.

### Type consistency

- `PriceSnapshot` used consistently (T5, T6, T9, T13, T19).
- `DashboardVM.open_trade_last_prices: Mapping[str, PriceSnapshot]` matches spec §3.3 (post-R2 revision).
- `PriceCache.get_many(tickers, deadline_seconds, *, executor)` signature consistent across T6, T9, T13.
- `create_app(cfg, cfg_path=None)` consistent across T3, T7, T8, T17.
- Route handlers all use `_templates(request)` from T11.
- `build_*` naming consistent: `build_dashboard`, `build_watchlist`, `build_watchlist_expanded`, `build_journal`, `build_pipeline`.

No inconsistencies found.
