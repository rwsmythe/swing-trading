# Phase 3b Trade Actions Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add inline HTMX row-swap trade-action forms (entry/exit/stop-adjust) + strict OriginGuard + HTMX-aware 404 handler + state-drift recovery on top of the Phase 3a dashboard. Phase 2 services (`record_entry`, `record_exit`, `adjust_stop`) are consumed unchanged.

**Architecture:** Routes (`swing/web/routes/trades.py`) are thin handlers that call Phase 2 services and render template fragments. A new row-VM module (`swing/web/view_models/open_positions_row.py`) is the single source of truth for rendering one open-positions row; `build_dashboard` is refactored to use it (keeping its batched fetch) while POST-success handlers use a convenience wrapper. After-submit uses a two-call pattern: `build_open_positions_row` for the primary row, `build_dashboard` for OOB fragments (cache hits dominate in the common case). `OriginGuardMiddleware` gains a `strict=True` mode that requires `HX-Request: true` on unsafe methods (narrower accepted-header matrix, not cryptographic CSRF — see spec §1.1 threat model). HTMX-aware `HTTPException` handler renders 404/4xx as small fragments instead of JSON.

**Tech Stack:** FastAPI + HTMX 2.x (3a foundation), Jinja2, Starlette 1.0 TemplateResponse signature (`TemplateResponse(request, "name", {...})`), sqlite3, existing Phase 2 trade services.

---

## File Structure

### Production code

```
swing/web/
├── middleware/
│   └── origin_guard.py           # MODIFIED: adds `strict: bool = False` kwarg
├── view_models/
│   ├── open_positions_row.py     # NEW: OpenPositionsRowVM + _open_positions_row_vm + build_open_positions_row
│   ├── trades.py                 # NEW: TradeEntryFormVM + TradeExitFormVM + TradeStopFormVM + build_* helpers
│   └── dashboard.py              # MODIFIED: build_dashboard now uses _open_positions_row_vm (internal only)
├── routes/
│   └── trades.py                 # NEW: 7 endpoints
├── templates/
│   └── partials/
│       ├── open_positions.html.j2        # MODIFIED: delegates to open_positions_row.html.j2
│       ├── open_positions_row.html.j2    # NEW: single <tr>; adds Exit + Adjust stop buttons
│       ├── watchlist_row.html.j2         # MODIFIED: adds Enter button
│       ├── trade_entry_form.html.j2      # NEW
│       ├── trade_exit_form.html.j2       # NEW
│       ├── trade_stop_form.html.j2       # NEW
│       ├── trade_form_error.html.j2      # NEW: 400 error banner + preserved form
│       ├── soft_warn_confirm.html.j2     # NEW: 2-step confirmation
│       ├── sizing_hint.html.j2           # NEW: dim-guidance OR numbers modes
│       └── http_error_fragment.html.j2   # NEW: HTMX 4xx body
└── app.py                        # MODIFIED: add_middleware strict=True; HTMX-aware HTTPException handler; include trades router
```

### Test files

```
tests/web/
├── test_origin_guard.py                       # MODIFIED: parameterize fixture; add 2 strict tests
├── test_view_models/
│   ├── test_open_positions_row.py             # NEW
│   └── test_trades.py                         # NEW
├── test_routes/
│   └── test_trades_route.py                   # NEW: ~24 tests
├── test_error_handling.py                     # MODIFIED: 1 new test for HTMX-aware 4xx handler
└── test_trades_integration.py                 # NEW: 4 end-to-end tests
```

**Target test count:** ~36 new; full fast suite goes from 351 (end of 3a) to ~387.

---

## Task Ordering Rationale

1. **OriginGuard strict flag first** (T1–T2) — smallest leaf change; must land before other POST routes (which rely on strict behavior) so Phase 3a tests prove the flip is safe.
2. **HTMX-aware HTTPException handler** (T3) — needed by the Form-GET 404 path; land it now so all subsequent form-GET tests can assert HTMX fragment responses.
3. **Row VM infrastructure** (T4–T6) — shared by dashboard (refactor) and POST-success handlers. Refactor dashboard internally first; external `DashboardVM` shape unchanged so 3a tests stay green.
4. **Watchlist Enter button** (T7) — small template tweak; prepares dashboard for the entry-form trigger.
5. **Sizing hint endpoint** (T8) — isolated leaf endpoint with a tolerant contract; land it before the entry form so T9's form template can point at it.
6. **Entry flow** (T9–T11) — VM, form-GET, POST happy path, soft-warn, error paths.
7. **Exit flow** (T12–T13) — VM + form-GET + POST (full/partial/drift).
8. **Stop-adjust flow** (T14–T15) — VM + form-GET + POST happy + regression-drift.
9. **Integration tests** (T16) — 4 end-to-end scenarios.
10. **Acceptance sweep** (T17) — full fast suite, regression verification, hand-off to adversarial review.

Each task ends with a commit. No task leaves the codebase in a broken state.

---

## Task 1: OriginGuardMiddleware strict mode

**Files:**
- Modify: `swing/web/middleware/origin_guard.py`
- Test: `tests/web/test_origin_guard.py`

Add `strict: bool = False` kwarg to `OriginGuardMiddleware.__init__`. When `strict=True`, unsafe methods (everything except GET/HEAD/OPTIONS) MUST carry `HX-Request: true`. The Origin-matches and Referer-startswith fallbacks are still honored only under `strict=False` (the 3a default). Safe methods are unchanged in both modes.

Spec §3.3.

- [ ] **Step 1: Write failing tests**

Append to `tests/web/test_origin_guard.py`:

```python
def test_post_strict_requires_hx_request():
    """Under strict=True, POST with only same-Origin (no HX-Request) → 403."""
    app = FastAPI()
    app.add_middleware(
        OriginGuardMiddleware,
        bound_host="127.0.0.1", bound_port=8080, strict=True,
    )
    router = APIRouter()

    @router.post("/action")
    def action():
        return {"ok": True}

    app.include_router(router)
    client = TestClient(app)
    r = client.post("/action", headers={"Origin": "http://127.0.0.1:8080"})
    assert r.status_code == 403


def test_post_strict_rejects_referer_only():
    """Under strict=True, POST with only same-Referer (no HX-Request) → 403."""
    app = FastAPI()
    app.add_middleware(
        OriginGuardMiddleware,
        bound_host="127.0.0.1", bound_port=8080, strict=True,
    )
    router = APIRouter()

    @router.post("/action")
    def action():
        return {"ok": True}

    app.include_router(router)
    client = TestClient(app)
    r = client.post("/action", headers={"Referer": "http://127.0.0.1:8080/some/path"})
    assert r.status_code == 403


def test_post_strict_accepts_hx_request():
    """Under strict=True, POST with HX-Request: true → 200 (unchanged)."""
    app = FastAPI()
    app.add_middleware(
        OriginGuardMiddleware,
        bound_host="127.0.0.1", bound_port=8080, strict=True,
    )
    router = APIRouter()

    @router.post("/action")
    def action():
        return {"ok": True}

    app.include_router(router)
    client = TestClient(app)
    r = client.post("/action", headers={"HX-Request": "true"})
    assert r.status_code == 200
```

- [ ] **Step 2: Verify the new tests fail**

Run: `python -m pytest tests/web/test_origin_guard.py -v`
Expected: existing 6 pass, 3 new fail — `strict` kwarg doesn't exist yet.

- [ ] **Step 3: Implement the strict flag**

Replace `OriginGuardMiddleware` in `swing/web/middleware/origin_guard.py`:

```python
"""Origin/HX-Request/Referer guard for state-changing requests.

Two modes:
- Non-strict (default): accepts HX-Request OR same-Origin OR same-Referer on unsafe methods.
- Strict (spec §3.3): requires HX-Request on unsafe methods; Origin/Referer fallbacks
  are removed. Narrows the accepted-header matrix for defense-in-depth; does NOT add
  cryptographic CSRF (see spec §1.1 threat model).

GET/HEAD/OPTIONS are always passed through in both modes.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response


class OriginGuardMiddleware(BaseHTTPMiddleware):
    _SAFE_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})

    def __init__(self, app, *, bound_host: str, bound_port: int, strict: bool = False):
        super().__init__(app)
        self._expected_origin = f"http://{bound_host}:{bound_port}"
        self._strict = strict

    async def dispatch(self, request: Request, call_next):
        if request.method in self._SAFE_METHODS:
            return await call_next(request)

        headers = request.headers
        if headers.get("HX-Request", "").lower() == "true":
            return await call_next(request)

        if self._strict:
            return Response(
                status_code=403,
                content="Missing HX-Request header (strict mode)",
                media_type="text/plain",
            )

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

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/web/test_origin_guard.py -v`
Expected: 9 PASS (existing 6 + 3 new).

- [ ] **Step 5: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 354 passed (351 + 3 new). No regressions.

- [ ] **Step 6: Commit**

```bash
git add swing/web/middleware/origin_guard.py tests/web/test_origin_guard.py
git commit -m "feat(web): OriginGuardMiddleware gains strict HX-Request-required mode"
```

---

## Task 2: Wire strict=True into create_app

**Files:**
- Modify: `swing/web/app.py`
- Test: `tests/web/test_app_smoke.py`

Flip `create_app` to use `strict=True` on `OriginGuardMiddleware`. This is a breaking change for any test that POSTs without `HX-Request: true` — Phase 3a's test suite was already disciplined about sending the header, but verify.

- [ ] **Step 1: Write failing test**

Append to `tests/web/test_app_smoke.py`:

```python
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
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/web/test_app_smoke.py -v`
Expected: prior tests pass; new test fails (receives 200 because 3a's non-strict allows Referer fallback).

- [ ] **Step 3: Add strict=True to create_app**

In `swing/web/app.py`, find the `app.add_middleware(OriginGuardMiddleware, ...)` call and add `strict=True`:

```python
    app.add_middleware(
        OriginGuardMiddleware,
        bound_host=cfg.web.host,
        bound_port=cfg.web.port,
        strict=True,
    )
```

Do NOT touch any other part of app.py.

- [ ] **Step 4: Run full suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 355 passed (354 + 1 new). All prior 3a tests still pass because every 3a POST-route test sends `HX-Request: true`.

If any 3a test fails, it's a real gap — inspect and fix by adding `HX-Request: true` to the test's POST (do not revert strict).

- [ ] **Step 5: Commit**

```bash
git add swing/web/app.py tests/web/test_app_smoke.py
git commit -m "feat(web): create_app opts into OriginGuard strict mode"
```

---

## Task 3: HTMX-aware HTTPException handler

**Files:**
- Modify: `swing/web/app.py`
- Create: `swing/web/templates/partials/http_error_fragment.html.j2`
- Test: `tests/web/test_error_handling.py`

Register an `@app.exception_handler(StarletteHTTPException)` that renders a small HTMX fragment when the request carries `HX-Request: true`, else delegates to FastAPI's default handler. Spec §5.2.

- [ ] **Step 1: Write failing test**

Append to `tests/web/test_error_handling.py`:

```python
def test_htmx_404_renders_fragment_not_json(test_cfg):
    """HTMX-aware HTTPException handler: HX-Request 404 → HTML fragment body,
    not FastAPI's default JSON body."""
    from fastapi import HTTPException
    from fastapi.testclient import TestClient
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    @app.get("/_missing")
    def _missing():
        raise HTTPException(status_code=404, detail="nothing here")

    with TestClient(app) as client:
        # HTMX client: expect fragment
        r_hx = client.get("/_missing", headers={"HX-Request": "true"})
        assert r_hx.status_code == 404
        assert "<!doctype" not in r_hx.text.lower()  # no full page
        assert "nothing here" in r_hx.text
        # Non-HTMX client: expect FastAPI default JSON
        r_json = client.get("/_missing")
        assert r_json.status_code == 404
        assert r_json.headers["content-type"].startswith("application/json")
        assert r_json.json() == {"detail": "nothing here"}
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/web/test_error_handling.py::test_htmx_404_renders_fragment_not_json -v`
Expected: FAIL — both branches return JSON today.

- [ ] **Step 3: Create the fragment template**

Create `swing/web/templates/partials/http_error_fragment.html.j2`:

```html
{#- swing/web/templates/partials/http_error_fragment.html.j2
    Expects: status_code (int), detail (str). Rendered for HX-Request 4xx/5xx. -#}
<div class="banner banner-degraded" data-status="{{ status_code }}" role="alert">
  {{ detail }}
</div>
```

- [ ] **Step 4: Write a second failing test — RequestValidationError handler (R1 Major 1)**

Spec §5 requires Phase 2 validation errors + Starlette form-parse errors to render a 400 HTMX fragment, not FastAPI's default 422 JSON. Add to `tests/web/test_error_handling.py`:

```python
def test_htmx_validation_error_renders_fragment_not_json(test_cfg):
    """RequestValidationError (missing/malformed form field) under HX-Request →
    trade_form_error fragment at 400, not FastAPI's default 422 JSON."""
    from fastapi import Form
    from fastapi.testclient import TestClient
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    @app.post("/_typed_probe")
    def _probe(x: float = Form(...)):
        return {"ok": True}

    with TestClient(app) as client:
        # HX-Request: missing field → fragment with 400.
        r_hx = client.post(
            "/_typed_probe", headers={"HX-Request": "true"}, data={},
        )
        assert r_hx.status_code == 400
        assert "banner" in r_hx.text.lower()
        assert "<!doctype" not in r_hx.text.lower()
        # Non-HTMX: default 422 JSON still works.
        r_json = client.post("/_typed_probe", data={})
        assert r_json.status_code == 422
        assert r_json.headers["content-type"].startswith("application/json")
```

- [ ] **Step 5: Register BOTH handlers in create_app**

In `swing/web/app.py`:

Add these imports near the top (merge with existing):

```python
from fastapi.exceptions import RequestValidationError
from fastapi.exception_handlers import http_exception_handler, request_validation_exception_handler
from starlette.exceptions import HTTPException as StarletteHTTPException
```

Inside `create_app`, AFTER the existing `_register_exception_handlers(app)` call, add:

```python
    @app.exception_handler(StarletteHTTPException)
    async def _handle_http_exc(request: Request, exc: StarletteHTTPException):
        if request.headers.get("HX-Request", "").lower() == "true":
            tpls = Jinja2Templates(directory=str(app.state.templates_dir))
            return tpls.TemplateResponse(
                request, "partials/http_error_fragment.html.j2",
                {"status_code": exc.status_code, "detail": exc.detail},
                status_code=exc.status_code,
            )
        return await http_exception_handler(request, exc)

    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(request: Request, exc: RequestValidationError):
        """HTMX form-validation errors render as the trade_form_error fragment at 400
        (spec §5). Non-HTMX requests fall through to FastAPI's default 422 JSON
        (API consumers, curl probes, etc.)."""
        if request.headers.get("HX-Request", "").lower() == "true":
            # Summarize the first validation error for the banner.
            errors = exc.errors()
            first = errors[0] if errors else {}
            field = ".".join(str(p) for p in first.get("loc", ()) if p != "body") or "field"
            msg = first.get("msg", "invalid input")
            tpls = Jinja2Templates(directory=str(app.state.templates_dir))
            return tpls.TemplateResponse(
                request, "partials/trade_form_error.html.j2",
                {"error_message": f"Invalid input in {field}: {msg}", "form_body": None},
                status_code=400,
            )
        return await request_validation_exception_handler(request, exc)
```

Note: `trade_form_error.html.j2` is created in Task 10. For Task 3's RequestValidationError test to have a template to render, create a stub template NOW — Task 10 will replace its body with the full form-preservation markup:

Create `swing/web/templates/partials/trade_form_error.html.j2` with minimal body (gets enhanced in Task 10):

```html
{#- Trade form error fragment. Full form-preservation markup lands in Task 10.
    Expects: error_message (str), form_body (None or pre-rendered trusted HTML). -#}
<tr class="trade-form-error">
  <td colspan="8">
    <div class="banner banner-degraded" role="alert">{{ error_message }}</div>
    {% if form_body %}{{ form_body | safe }}{% endif %}
  </td>
</tr>
```

- [ ] **Step 6: Verify the new tests pass**

Run: `python -m pytest tests/web/test_error_handling.py -v`
Expected: all error-handling tests pass, including the new 404 fragment and validation-error fragment tests.

- [ ] **Step 7: Verify the 3a `test_pipeline_status_missing_returns_error` still passes**

Run: `python -m pytest tests/web/test_routes/test_pipeline_route.py::test_pipeline_status_missing_returns_error -v`
Expected: PASS. That test uses TestClient without HX-Request, so it hits the JSON-default branch, unchanged.

- [ ] **Step 8: Full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 357 passed (355 + 2 new error-handling tests).

- [ ] **Step 9: Commit**

```bash
git add swing/web/app.py swing/web/templates/partials/http_error_fragment.html.j2 swing/web/templates/partials/trade_form_error.html.j2 tests/web/test_error_handling.py
git commit -m "feat(web): HTMX-aware HTTPException + RequestValidationError handlers render fragments"
```

---

## Task 4: OpenPositionsRowVM + pure row-VM helper

**Files:**
- Create: `swing/web/view_models/open_positions_row.py`
- Test: `tests/web/test_view_models/test_open_positions_row.py`

The pure render-input assembler `_open_positions_row_vm(trade, price_snapshot, remaining_shares, advisories)` — NO I/O. Used by `build_dashboard` (batched path) and by `build_open_positions_row` (single-row path, T5). Spec §3.4.

- [ ] **Step 1: Write failing tests**

Create `tests/web/test_view_models/test_open_positions_row.py`:

```python
"""OpenPositionsRowVM assembly — pure helper, no I/O."""
from __future__ import annotations

from datetime import datetime

from swing.data.models import Trade
from swing.web.price_cache import PriceSnapshot
from swing.web.view_models.dashboard import AdvisorySuggestionVM


def _mk_trade(id_=42, ticker="AAPL", stop=170.0) -> Trade:
    return Trade(
        id=id_, ticker=ticker, entry_date="2026-04-15",
        entry_price=180.0, initial_shares=5, initial_stop=170.0,
        current_stop=stop, status="open",
        watchlist_entry_target=None, watchlist_initial_stop=None,
        notes=None,
    )


def test_vm_pure_assembly_with_snapshot_and_advisories():
    from swing.web.view_models.open_positions_row import (
        _open_positions_row_vm, OpenPositionsRowVM,
    )
    trade = _mk_trade()
    snap = PriceSnapshot(
        ticker="AAPL", price=182.0, asof=datetime.now(),
        is_stale=False, source="live",
    )
    advs = (AdvisorySuggestionVM(rule="breakeven", message="move stop to entry"),)
    vm = _open_positions_row_vm(
        trade=trade, price_snapshot=snap, remaining_shares=5, advisories=advs,
    )
    assert isinstance(vm, OpenPositionsRowVM)
    assert vm.trade is trade
    assert vm.price_snapshot is snap
    assert vm.remaining_shares == 5
    assert vm.advisories == advs


def test_vm_pure_assembly_with_no_snapshot_and_no_advisories():
    from swing.web.view_models.open_positions_row import _open_positions_row_vm
    trade = _mk_trade()
    vm = _open_positions_row_vm(
        trade=trade, price_snapshot=None, remaining_shares=3, advisories=(),
    )
    assert vm.price_snapshot is None
    assert vm.advisories == ()
    assert vm.remaining_shares == 3
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/web/test_view_models/test_open_positions_row.py -v`
Expected: ImportError — `swing.web.view_models.open_positions_row` does not exist.

- [ ] **Step 3: Implement the pure helper**

Create `swing/web/view_models/open_positions_row.py`:

```python
"""OpenPositionsRowVM + pure assembler + single-row convenience wrapper.

The pure assembler `_open_positions_row_vm` has NO I/O and is called by
`build_dashboard` in its batched path. The convenience wrapper
`build_open_positions_row` does the per-row I/O and is used by POST-success
handlers that need exactly one row (spec §3.4).
"""
from __future__ import annotations

from dataclasses import dataclass

from swing.data.models import Trade
from swing.web.price_cache import PriceSnapshot
from swing.web.view_models.dashboard import AdvisorySuggestionVM


@dataclass(frozen=True)
class OpenPositionsRowVM:
    trade: Trade
    price_snapshot: PriceSnapshot | None
    remaining_shares: int
    advisories: tuple[AdvisorySuggestionVM, ...]


def _open_positions_row_vm(
    *, trade: Trade,
    price_snapshot: PriceSnapshot | None,
    remaining_shares: int,
    advisories: tuple[AdvisorySuggestionVM, ...],
) -> OpenPositionsRowVM:
    """Pure render-input assembler. NO I/O. Single source of truth for the
    fields an open-positions row consumes from Jinja."""
    return OpenPositionsRowVM(
        trade=trade,
        price_snapshot=price_snapshot,
        remaining_shares=remaining_shares,
        advisories=advisories,
    )
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/web/test_view_models/test_open_positions_row.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Full suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 358 passed (356 + 2).

- [ ] **Step 6: Commit**

```bash
git add swing/web/view_models/open_positions_row.py tests/web/test_view_models/test_open_positions_row.py
git commit -m "feat(web): OpenPositionsRowVM + pure row-VM assembler"
```

---

## Task 5: build_open_positions_row convenience wrapper

**Files:**
- Modify: `swing/web/view_models/open_positions_row.py`
- Test: `tests/web/test_view_models/test_open_positions_row.py`

**Pre-check correction (R1):** `list_exits_for_trade(conn, trade_id)` already exists in `swing/data/repos/trades.py:200` and returns `list[Exit]`. The `Exit` model (`swing/data/models.py:68`) has fields `(id, trade_id, exit_date, exit_price, shares, reason, realized_pnl, r_multiple, notes)`. The SQL table is `exits` (not `trade_exits`). The plan's initial Task 5 assumed these did not exist — that was wrong. Task 5 is now scoped to ONLY the `build_open_positions_row` convenience wrapper.

The wrapper does the I/O for a single row: cache.get_many for one ticker; `list_exits_for_trade` for remaining shares; compute advisories.

- [ ] **Step 1: Verify the existing Phase 2 surface**

Run: `grep -n "def list_exits_for_trade\|class Exit" swing/data/repos/trades.py swing/data/models.py`

Expected: `list_exits_for_trade` at `swing/data/repos/trades.py:200` and `class Exit` at `swing/data/models.py:68`. No Phase 2 change required.

- [ ] **Step 2: Write failing test for build_open_positions_row**

Append to `tests/web/test_view_models/test_open_positions_row.py`:

```python
def test_build_open_positions_row_single_row(seeded_db, monkeypatch):
    """build_open_positions_row does one get_many + one list_exits_for_trade
    + one advisories compute; returns OpenPositionsRowVM."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.web.view_models.open_positions_row import build_open_positions_row

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="AAPL", entry_date="2026-04-15",
                entry_price=180.0, initial_shares=10, initial_stop=170.0,
                current_stop=170.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=182.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })
    vm = build_open_positions_row(
        trade=trade, cfg=cfg, cache=cache, executor=None,
    )
    assert vm.trade.ticker == "AAPL"
    assert vm.price_snapshot is not None
    assert vm.price_snapshot.price == 182.0
    assert vm.remaining_shares == 10  # no exits seeded
    assert isinstance(vm.advisories, tuple)


def test_build_open_positions_row_reduces_remaining_shares_for_prior_exits(seeded_db, monkeypatch):
    """After a prior partial exit, remaining_shares = initial - sum(exits.shares)."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Exit, Trade
    from swing.data.repos.trades import (
        insert_trade_with_event, insert_exit_with_event, list_open_trades,
    )
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.web.view_models.open_positions_row import build_open_positions_row

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="AAPL", entry_date="2026-04-15",
                entry_price=180.0, initial_shares=10, initial_stop=170.0,
                current_stop=170.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
            trade = list_open_trades(conn)[0]
            insert_exit_with_event(
                conn,
                Exit(id=None, trade_id=trade.id, exit_date="2026-04-17",
                     exit_price=185.0, shares=3, reason="partial",
                     realized_pnl=15.0, r_multiple=1.5, notes=None),
                event_ts="2026-04-17T10:00:00", rationale="locking in 1.5R partial",
            )
            trade = list_open_trades(conn)[0]  # refresh
    finally:
        conn.close()

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=188.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })
    vm = build_open_positions_row(
        trade=trade, cfg=cfg, cache=cache, executor=None,
    )
    assert vm.remaining_shares == 7   # 10 - 3
```

- [ ] **Step 3: Verify it fails**

Run: `python -m pytest tests/web/test_view_models/test_open_positions_row.py -v`
Expected: the 2 tests from Task 4 pass, both new tests fail — `build_open_positions_row` not yet implemented.

- [ ] **Step 4: Implement build_open_positions_row**

Append to `swing/web/view_models/open_positions_row.py`:

```python
import sqlite3
from datetime import datetime

from swing.config import Config
from swing.data.db import connect
from swing.data.models import Trade
from swing.data.repos.trades import list_exits_for_trade
from swing.trades.advisory import AdvisoryContext, compute_all_suggestions
from swing.web.price_cache import PriceCache
from swing.web.view_models.dashboard import AdvisorySuggestionVM


def build_open_positions_row(
    *, trade: Trade, cfg: Config, cache: PriceCache, executor,
    conn: sqlite3.Connection | None = None,
) -> OpenPositionsRowVM:
    """Single-row convenience wrapper for POST-success handlers.

    Does: cache.get_many([trade.ticker], deadline=..., executor=...);
          list_exits_for_trade(conn, trade.id) for remaining-shares;
          compute_all_suggestions(trade, AdvisoryContext(sma10=None, sma20=None, ...))
          — 3a reduced advisory subset; SMA-dependent rules return None until Phase 3c.

    Opens its own read-snapshot `with conn:` if `conn` is None.
    Callers that have batch context (dashboard.py) should use `_open_positions_row_vm`
    directly with precomputed snapshots + exits + advisories.
    """
    assert trade.id is not None, f"trade.id=None for {trade.ticker} — data integrity bug"

    prices = cache.get_many(
        [trade.ticker],
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )
    snapshot = prices.get(trade.ticker)

    own_conn = conn is None
    if own_conn:
        conn = connect(cfg.paths.db_path)
    try:
        with conn:
            exits = list_exits_for_trade(conn, trade.id)
    finally:
        if own_conn:
            conn.close()
    remaining = trade.initial_shares - sum(e.shares for e in exits)

    advisories: tuple[AdvisorySuggestionVM, ...] = ()
    if snapshot is not None:
        ctx = AdvisoryContext(
            as_of_date=datetime.now().date().isoformat(),
            current_price=snapshot.price,
            sma10=None, sma20=None,
            weather_status="Bullish",  # conservative default when weather unknown
            config=cfg.stop_advisory,
        )
        raw = compute_all_suggestions(trade, ctx)
        advisories = tuple(
            AdvisorySuggestionVM(rule=s.rule, message=s.message) for s in raw
        )

    return _open_positions_row_vm(
        trade=trade,
        price_snapshot=snapshot,
        remaining_shares=remaining,
        advisories=advisories,
    )
```

- [ ] **Step 5: Run tests**

Run: `python -m pytest tests/web/test_view_models/test_open_positions_row.py -v`
Expected: 4 PASS (2 pure helpers + 2 build).

- [ ] **Step 6: Full suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 360 passed (358 + 2).

- [ ] **Step 7: Commit**

```bash
git add swing/web/view_models/open_positions_row.py tests/web/test_view_models/test_open_positions_row.py
git commit -m "feat(web): build_open_positions_row convenience wrapper"
```

---

## Task 6: Refactor build_dashboard to use _open_positions_row_vm

**Files:**
- Modify: `swing/web/view_models/dashboard.py`
- Test: run existing 3a dashboard tests (no new tests — external contract unchanged)

Internally restructure: `build_dashboard` keeps its batched `cache.get_many(all_tickers, ...)` + one weather lookup + one `AdvisoryContext` construction, then loops and calls `_open_positions_row_vm` for each open trade. Attach the results to `DashboardVM.open_trade_last_prices` / `open_trade_advisories` — external shape UNCHANGED.

- [ ] **Step 1: Read existing build_dashboard**

Read `swing/web/view_models/dashboard.py` carefully — understand where `open_trade_last_prices` and `open_trade_advisories` are assembled. Note the existing pattern (probably a single loop already).

- [ ] **Step 2: Refactor internally**

Modify the open-trade loop in `build_dashboard` to:

```python
    # Build per-row VMs via the pure assembler (no I/O here — all I/O happened above).
    from swing.web.view_models.open_positions_row import _open_positions_row_vm
    from swing.data.repos.trades import list_exits_for_trade

    open_trade_last_prices: dict[str, PriceSnapshot] = {}
    open_trade_advisories: dict[int, list[AdvisorySuggestionVM]] = {}
    for t in open_trades:
        assert t.id is not None, f"open trade {t.ticker} has id=None — data-integrity bug"
        snap = prices.get(t.ticker)
        exits = list_exits_for_trade(conn, t.id)
        remaining = t.initial_shares - sum(e.shares for e in exits)
        # compute_all_suggestions call — keep the existing weather/SMA setup that
        # already happens once above this loop (reuse weather_status_str and pass
        # sma10=None, sma20=None as today).
        ctx_adv = AdvisoryContext(
            as_of_date=action_session,
            current_price=snap.price if snap else 0.0,
            sma10=None, sma20=None,
            weather_status=weather_status_str,
            config=cfg.stop_advisory,
        )
        raw = compute_all_suggestions(t, ctx_adv) if snap else []
        advisories_tuple = tuple(
            AdvisorySuggestionVM(rule=s.rule, message=s.message) for s in raw
        )
        # Pure assembly (no I/O).
        _open_positions_row_vm(
            trade=t, price_snapshot=snap,
            remaining_shares=remaining, advisories=advisories_tuple,
        )
        # Attach to the existing DashboardVM fields (external shape unchanged).
        if snap is not None:
            open_trade_last_prices[t.ticker] = snap
        open_trade_advisories[t.id] = list(advisories_tuple)
```

Important: the existing `DashboardVM.open_trade_last_prices` and `open_trade_advisories` fields stay exactly as they are — the per-row VMs are computed as a side benefit but not attached to `DashboardVM`. This preserves the external contract.

Note: `list_exits_for_trade(conn, t.id)` is called once per trade. The dashboard typically has ≤6 open trades (hard cap). N+1 is bounded in practice; the cost is a few indexed SELECT queries.

- [ ] **Step 3: Run the existing dashboard test**

Run: `python -m pytest tests/web/test_view_models/test_dashboard.py -v`
Expected: PASS. External shape unchanged.

- [ ] **Step 4: Run all 3a route tests that depend on the dashboard**

Run: `python -m pytest tests/web/test_routes/test_dashboard_route.py tests/web/test_dashboard_integration.py -v`
Expected: all pass.

- [ ] **Step 5: Full suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 360 passed (unchanged — refactor adds no new tests).

- [ ] **Step 6: Commit**

```bash
git add swing/web/view_models/dashboard.py
git commit -m "refactor(web): build_dashboard uses _open_positions_row_vm + list_exits_for_trade"
```

---

## Task 7: Extract open_positions_row.html.j2 partial (row-only VM contract, no buttons yet)

**Files:**
- Modify: `swing/web/templates/partials/open_positions.html.j2`
- Create: `swing/web/templates/partials/open_positions_row.html.j2`
- Test: run existing dashboard/watchlist route tests

**R1 resolution notes:**
- **R1 Major 2 fix:** The Enter/Exit/Adjust-stop action buttons are NOT added in this task. They land in the tasks that create the routes those buttons point at: Enter button in Task 9 (entry form GET), Exit button in Task 13 (exit form GET), Adjust stop button in Task 15 (stop form GET). This keeps every intermediate commit a working product — no button ever exists without its backing endpoint.
- **R1 Major 3 fix:** The row partial has a SINGLE contract — it takes only `row: OpenPositionsRowVM`. No dual `{% if row is defined %}` branch. The dashboard loop constructs a row VM per trade via `_open_positions_row_vm(...)` and passes it as `row`.
- **R1 Major 5 golden-output note:** This task is a RENDERING CHANGE even though `DashboardVM`'s external dataclass shape is unchanged. The Phase 3a integration tests (`test_dashboard_no_stale_banner_when_run_is_current`, `test_dashboard_shows_stale_banner_when_run_is_old`, `test_dashboard_renders_degraded_banner_when_cache_degraded`) are the de-facto golden-output tests — if they stay green, the HTML is semantically equivalent. If any assert a specific HTML substring that changes (e.g., a tag ordering), the test assertion is updated to match the new output AND the change is called out in the commit message.

3a tests likely to need assertion updates: `tests/web/test_routes/test_dashboard_route.py`, `tests/web/test_routes/test_watchlist_route.py`, `tests/web/test_dashboard_integration.py`, `tests/web/test_routes/test_pipeline_route.py::test_post_prices_refresh_*` (the oob-swap test reads open_positions markup).

- [ ] **Step 1: Read the current open_positions.html.j2**

Understand its structure. Today it iterates `vm.open_trades` and renders a `<tr>` for each using `vm.open_trade_last_prices[t.ticker]` and `vm.open_trade_advisories[t.id]`.

- [ ] **Step 2: Create the new per-row partial (row-only contract, no buttons)**

Create `swing/web/templates/partials/open_positions_row.html.j2`:

```html
{#- Single open-positions row.
    SINGLE contract: expects `row: OpenPositionsRowVM` with fields
      trade (Trade), price_snapshot (PriceSnapshot|None),
      remaining_shares (int), advisories (tuple[AdvisorySuggestionVM, ...]).
    No dual-contract / legacy locals branch. All call sites MUST pass `row`.
    Action buttons (Exit, Adjust stop) are appended in Tasks 13 and 15 as
    their routes come online — this intermediate partial deliberately has no
    action-button cell (R1 Major 2). -#}
<tr id="open-position-{{ row.trade.id }}">
  <td>{{ row.trade.ticker }}</td>
  <td>{{ row.trade.entry_date }}</td>
  <td>${{ '%.2f' | format(row.trade.entry_price) }}</td>
  <td>{{ row.remaining_shares }} / {{ row.trade.initial_shares }}</td>
  <td>${{ '%.2f' | format(row.trade.current_stop) }}</td>
  <td>
    {% if row.price_snapshot %}
      ${{ '%.2f' | format(row.price_snapshot.price) }}
      {% if row.price_snapshot.is_stale %}<span class="stale">(stale)</span>{% endif %}
    {% else %}—{% endif %}
  </td>
  <td>
    {% for s in row.advisories %}
      <div>{{ s.message }}</div>
    {% endfor %}
  </td>
</tr>
```

- [ ] **Step 3: Refactor the outer open_positions.html.j2**

The dashboard loop needs to construct an `OpenPositionsRowVM` on the fly from the existing `DashboardVM` mappings, then pass it to the partial. Read the current `swing/web/templates/partials/open_positions.html.j2`, then replace the per-row content:

```html
{% for t in vm.open_trades %}
  {% set snap = vm.open_trade_last_prices.get(t.ticker) %}
  {% set advisories = vm.open_trade_advisories.get(t.id, []) %}
  {% set remaining = vm.open_trade_remaining_shares.get(t.id, t.initial_shares) %}
  {% set row = _row_vm_factory(t, snap, remaining, advisories) %}
  {% include "partials/open_positions_row.html.j2" %}
{% endfor %}
```

Where `_row_vm_factory` is a Jinja global callable registered on the `Jinja2Templates` environment in `create_app`. Alternative — simpler — approach: have `build_dashboard` compute a `DashboardVM.open_trade_rows: Mapping[int, OpenPositionsRowVM]` as an ADDITIVE field (external shape extended, not broken; existing consumers ignore it), and the template iterates that mapping. Implement THIS alternative (cleaner, no Jinja globals).

Modify `swing/web/view_models/dashboard.py` (Task 6's refactor landed already; now add the new field):

```python
# In DashboardVM, add an additive field:
open_trade_rows: Mapping[int, "OpenPositionsRowVM"]  # keyed by trade.id; additive to legacy fields
```

And populate it in `build_dashboard` using the same per-row computation Task 6 already does — just collect the `_open_positions_row_vm(...)` results into a dict.

Then the outer template becomes:

```html
{% for t in vm.open_trades %}
  {% set row = vm.open_trade_rows[t.id] %}
  {% include "partials/open_positions_row.html.j2" %}
{% endfor %}
```

Single contract, no factory needed, no Jinja globals.

The `DashboardVM.open_trade_last_prices` and `open_trade_advisories` mappings remain for backward compatibility (any consumer that reads them directly keeps working); the dashboard template now prefers the new `open_trade_rows` field.

Keep the surrounding `<section>`, `<table>`, `<thead>` unchanged — only the inside of the `<tbody>` loop changes.

- [ ] **Step 4: Update DashboardVM + build_dashboard to populate open_trade_rows**

In `swing/web/view_models/dashboard.py`:

Add the import:
```python
from swing.web.view_models.open_positions_row import OpenPositionsRowVM
```

Add to `DashboardVM`:
```python
open_trade_rows: Mapping[int, OpenPositionsRowVM] = field(default_factory=dict)
```

(Use `field(default_factory=dict)` for backward compat with any caller that constructs DashboardVM without this field.)

In `build_dashboard`, populate:
```python
    open_trade_rows: dict[int, OpenPositionsRowVM] = {}
    for t in open_trades:
        assert t.id is not None
        snap = prices.get(t.ticker)
        exits = list_exits_for_trade(conn, t.id)
        remaining = t.initial_shares - sum(e.shares for e in exits)
        # ... (advisory construction per Task 6) ...
        open_trade_rows[t.id] = _open_positions_row_vm(
            trade=t, price_snapshot=snap,
            remaining_shares=remaining, advisories=advisories_tuple,
        )
        # Legacy mappings (kept for backward compat):
        if snap is not None:
            open_trade_last_prices[t.ticker] = snap
        open_trade_advisories[t.id] = list(advisories_tuple)
    # When building DashboardVM, pass both old and new fields.
```

- [ ] **Step 5: Run dashboard + watchlist tests**

Run: `python -m pytest tests/web/test_routes/test_dashboard_route.py tests/web/test_routes/test_watchlist_route.py tests/web/test_dashboard_integration.py tests/web/test_routes/test_pipeline_route.py -v`
Expected: all pass. If a test asserts a specific HTML string that's now moved/added, update the assertion to match the new output. Any such change must be minimal (e.g., adjusting whitespace or attribute order) and documented in the commit message.

- [ ] **Step 6: Full suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 360 passed (unchanged).

- [ ] **Step 7: Commit**

```bash
git add swing/web/templates/partials/open_positions.html.j2 swing/web/templates/partials/open_positions_row.html.j2 swing/web/view_models/dashboard.py
git commit -m "refactor(web): open_positions_row single-contract partial + DashboardVM.open_trade_rows"
```

---

## Task 8: GET /trades/entry/sizing-hint + tolerant contract

**Files:**
- Create: `swing/web/routes/trades.py` (NEW — this is the first endpoint added; all future trade endpoints will extend this file)
- Create: `swing/web/templates/partials/sizing_hint.html.j2`
- Modify: `swing/web/app.py` (include the trades router)
- Test: `tests/web/test_routes/test_trades_route.py`

Spec §4.6. Always returns 200. Missing/blank/non-numeric/non-positive/stop≥entry → "dim" guidance fragment. Valid → numbers fragment.

- [ ] **Step 1: Create sizing_hint.html.j2 template**

Create `swing/web/templates/partials/sizing_hint.html.j2`:

```html
{#- Sizing hint fragment, two modes:
    Mode 1 (numbers): pass `sizing` (SizingResult feasible=True) — shows shares + risk.
    Mode 2 (dim guidance): pass `guidance` (str) — shows hint text in muted style. -#}
<span id="sizing-hint" class="sizing-hint">
  {% if guidance is defined and guidance %}
    <span class="subtitle">{{ guidance }}</span>
  {% elif sizing is defined and sizing.feasible %}
    Suggested max: <strong>{{ sizing.shares }} sh</strong>
    (~${{ '%.2f' | format(sizing.risk_dollars) }} risk =
    {{ '%.2f' | format(sizing.risk_pct) }}%)
  {% else %}
    <span class="subtitle">Enter a valid entry price and stop (stop &lt; entry) to see sizing</span>
  {% endif %}
</span>
```

- [ ] **Step 2: Write failing tests**

Create `tests/web/test_routes/test_trades_route.py`:

```python
"""Trade routes: GET /trades/entry/sizing-hint (tolerant contract) for now."""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.web.app import create_app


def test_sizing_hint_happy_path(test_cfg, monkeypatch):
    """Valid entry/stop with feasible sizing → numbers fragment, always 200."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/sizing-hint?entry_price=180.0&initial_stop=170.0")
    assert r.status_code == 200
    assert "sizing-hint" in r.text
    # With starting_equity high enough and 10% stop distance, compute_shares
    # should produce a feasible result — text should include "sh".
    assert "sh" in r.text.lower()


def test_sizing_hint_missing_params(test_cfg):
    """Missing query params → 200 with dim guidance."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/sizing-hint")
    assert r.status_code == 200
    assert "valid entry price" in r.text.lower()


def test_sizing_hint_blank_params(test_cfg):
    """Blank query params → 200 with dim guidance."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/sizing-hint?entry_price=&initial_stop=")
    assert r.status_code == 200
    assert "valid entry price" in r.text.lower()


def test_sizing_hint_non_numeric(test_cfg):
    """Non-numeric values → 200 with dim guidance (no 422)."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/sizing-hint?entry_price=abc&initial_stop=xyz")
    assert r.status_code == 200
    assert "valid entry price" in r.text.lower()


def test_sizing_hint_stop_ge_entry(test_cfg):
    """stop >= entry → 200 with dim guidance (no compute_shares call, so no ValueError)."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/sizing-hint?entry_price=100.0&initial_stop=100.0")
    assert r.status_code == 200
    assert "stop &lt; entry" in r.text or "valid entry price" in r.text.lower()


def test_sizing_hint_zero_equity(test_cfg, monkeypatch):
    """Zero equity → 200 with feasible=False guidance, not 500."""
    cfg, cfg_path = test_cfg
    # Force equity=0 by patching current_equity where the route reads it.
    monkeypatch.setattr("swing.web.routes.trades.current_equity", lambda **_kw: 0.0)
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/sizing-hint?entry_price=180.0&initial_stop=170.0")
    assert r.status_code == 200
    assert "no equity" in r.text.lower() or "unavailable" in r.text.lower()
```

- [ ] **Step 3: Verify tests fail**

Run: `python -m pytest tests/web/test_routes/test_trades_route.py -v`
Expected: ALL FAIL — no route exists yet.

- [ ] **Step 4: Create the trades router**

Create `swing/web/routes/trades.py`:

```python
"""Phase 3b trade-action routes. Starts with sizing-hint; entry/exit/stop
endpoints are added in later tasks. All write endpoints require HX-Request
under strict OriginGuard (spec §3.3)."""
from __future__ import annotations

import logging

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from swing.data.db import connect
from swing.data.repos.cash import list_cash
from swing.data.repos.trades import list_all_exits
from swing.recommendations.sizing import compute_shares, SizingResult
from swing.trades.equity import current_equity
from swing.web.routes.dashboard import _templates

log = logging.getLogger(__name__)
router = APIRouter()


def _parse_optional_float(raw: str | None) -> float | None:
    if raw is None or raw.strip() == "":
        return None
    try:
        return float(raw)
    except ValueError:
        return None


@router.get("/trades/entry/sizing-hint", response_class=HTMLResponse)
def sizing_hint(
    request: Request,
    entry_price: str | None = None,
    initial_stop: str | None = None,
) -> HTMLResponse:
    """Tolerant sizing-hint endpoint (spec §4.6). Always 200.

    Mode contract:
      - Missing / blank / non-numeric / non-positive / stop >= entry
        → 'dim' guidance fragment ("Enter a valid entry price and stop...").
      - Valid inputs + SizingResult(feasible=True) → numbers fragment.
      - SizingResult(feasible=False) → dim fragment with the specific reason.
      - Any unexpected exception → caught, logged WARNING, dim fallback fragment.
    """
    templates = _templates(request)
    cfg = request.app.state.cfg
    entry = _parse_optional_float(entry_price)
    stop = _parse_optional_float(initial_stop)

    if entry is None or stop is None or entry <= 0 or stop <= 0 or stop >= entry:
        return templates.TemplateResponse(
            request, "partials/sizing_hint.html.j2",
            {"guidance": "Enter a valid entry price and stop (stop < entry) to see sizing"},
        )

    try:
        conn = connect(cfg.paths.db_path)
        try:
            with conn:
                exits = list_all_exits(conn)
                cash_movements = list_cash(conn)
        finally:
            conn.close()
        equity = current_equity(
            starting_equity=cfg.account.starting_equity,
            exits=exits, cash_movements=cash_movements,
        )
        sizing: SizingResult = compute_shares(
            entry=entry, stop=stop, equity=equity,
            max_risk_pct=cfg.risk.max_risk_pct,
            position_pct_cap=cfg.sizing.position_pct_cap,
        )
    except Exception as exc:
        log.warning("sizing-hint unexpected exception: %s", exc)
        return templates.TemplateResponse(
            request, "partials/sizing_hint.html.j2",
            {"guidance": "Sizing unavailable — check values"},
        )

    if not sizing.feasible:
        if sizing.constraint == "no_equity":
            reason = "No equity recorded — add a cash_movement or set account.starting_equity"
        else:
            reason = "Risk cap too tight for 1 share at this stop"
        return templates.TemplateResponse(
            request, "partials/sizing_hint.html.j2",
            {"guidance": reason},
        )

    return templates.TemplateResponse(
        request, "partials/sizing_hint.html.j2",
        {"sizing": sizing},
    )
```

- [ ] **Step 5: Include the router in create_app**

In `swing/web/app.py`, find the existing router includes (dashboard, watchlist, journal, pipeline). Add trades:

```python
    from swing.web.routes import (
        dashboard as dashboard_route,
        watchlist as watchlist_route,
        journal as journal_route,
        pipeline as pipeline_route,
        trades as trades_route,
    )
    app.include_router(dashboard_route.router)
    app.include_router(watchlist_route.router)
    app.include_router(journal_route.router)
    app.include_router(pipeline_route.router)
    app.include_router(trades_route.router)
```

- [ ] **Step 6: Run tests**

Run: `python -m pytest tests/web/test_routes/test_trades_route.py -v`
Expected: 6 PASS.

- [ ] **Step 7: Full suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 366 passed (360 + 6).

- [ ] **Step 8: Commit**

```bash
git add swing/web/routes/trades.py swing/web/templates/partials/sizing_hint.html.j2 swing/web/app.py tests/web/test_routes/test_trades_route.py
git commit -m "feat(web): GET /trades/entry/sizing-hint (tolerant contract, always 200)"
```

---

## Task 9: TradeEntryFormVM + GET /trades/entry/form + template

**Files:**
- Create: `swing/web/view_models/trades.py`
- Create: `swing/web/templates/partials/trade_entry_form.html.j2`
- Modify: `swing/web/routes/trades.py`
- Test: `tests/web/test_view_models/test_trades.py`, `tests/web/test_routes/test_trades_route.py`

Spec §3.1, §4.2.

- [ ] **Step 1: Failing VM test**

Create `tests/web/test_view_models/test_trades.py`:

```python
"""Trade form VMs — entry/exit/stop."""
from __future__ import annotations

from datetime import datetime

from swing.data.db import connect
from swing.data.models import WatchlistEntry
from swing.data.repos.watchlist import upsert_watchlist_entry


def test_build_entry_form_vm_shape(seeded_db, monkeypatch):
    """Entry form VM populated with ticker, prefilled price/stop, suggested shares."""
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.web.view_models.trades import build_entry_form_vm, TradeEntryFormVM

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
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=180.95, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })

    vm = build_entry_form_vm(
        ticker="AAPL", cfg=cfg, cache=cache, executor=None,
    )
    assert isinstance(vm, TradeEntryFormVM)
    assert vm.ticker == "AAPL"
    assert vm.entry_price == 180.95
    assert vm.initial_stop == 170.0  # from watchlist
    assert vm.watchlist_entry_target == 181.0
    assert vm.soft_warn_threshold == cfg.position_limits.soft_warn_open
    assert vm.hard_cap == cfg.position_limits.hard_cap_open
    # suggested_shares: depends on equity/risk/stop distance — just assert ≥ 0.
    assert vm.suggested_shares >= 0
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/web/test_view_models/test_trades.py -v`
Expected: ImportError.

- [ ] **Step 3: Create view_models/trades.py with TradeEntryFormVM + builder**

Create `swing/web/view_models/trades.py`:

```python
"""Trade form view-models + builders for Phase 3b."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from swing.config import Config
from swing.data.db import connect
from swing.data.repos.cash import list_cash
from swing.data.repos.trades import list_all_exits, list_open_trades
from swing.data.repos.watchlist import list_active_watchlist
from swing.recommendations.sizing import compute_shares
from swing.trades.equity import current_equity
from swing.web.price_cache import PriceCache


@dataclass(frozen=True)
class TradeEntryFormVM:
    ticker: str
    entry_date: str                  # today, ISO
    entry_price: float               # from live price cache
    initial_stop: float              # from watchlist_initial_stop_target if present, else 0.0
    watchlist_entry_target: float | None
    watchlist_initial_stop: float | None
    suggested_shares: int
    risk_dollars: float
    risk_pct: float
    soft_warn_threshold: int
    hard_cap: int
    open_count: int
    force: bool = False


def build_entry_form_vm(
    *, ticker: str, cfg: Config, cache: PriceCache, executor,
) -> TradeEntryFormVM:
    """Build entry-form VM from: watchlist row, live price, open positions, equity.
    Spec §4.2."""
    ticker = ticker.upper()
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            wl = list_active_watchlist(conn)
            wl_entry = next((w for w in wl if w.ticker == ticker), None)
            open_trades = list_open_trades(conn)
            exits = list_all_exits(conn)
            cash_movements = list_cash(conn)
    finally:
        conn.close()

    # Live price.
    prices = cache.get_many(
        [ticker],
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )
    snap = prices.get(ticker)
    entry_price = snap.price if snap else (wl_entry.last_close if wl_entry else 0.0)

    initial_stop = wl_entry.initial_stop_target if wl_entry and wl_entry.initial_stop_target else 0.0
    watchlist_entry_target = wl_entry.entry_target if wl_entry else None
    watchlist_initial_stop = wl_entry.initial_stop_target if wl_entry else None

    # Sizing hint at current (entry, stop).
    equity = current_equity(
        starting_equity=cfg.account.starting_equity,
        exits=exits, cash_movements=cash_movements,
    )
    if entry_price > 0 and 0 < initial_stop < entry_price:
        sizing = compute_shares(
            entry=entry_price, stop=initial_stop, equity=equity,
            max_risk_pct=cfg.risk.max_risk_pct,
            position_pct_cap=cfg.sizing.position_pct_cap,
        )
        suggested_shares = sizing.shares
        risk_dollars = sizing.risk_dollars
        risk_pct = sizing.risk_pct
    else:
        suggested_shares = 0
        risk_dollars = 0.0
        risk_pct = 0.0

    return TradeEntryFormVM(
        ticker=ticker,
        entry_date=date.today().isoformat(),
        entry_price=entry_price,
        initial_stop=initial_stop,
        watchlist_entry_target=watchlist_entry_target,
        watchlist_initial_stop=watchlist_initial_stop,
        suggested_shares=suggested_shares,
        risk_dollars=risk_dollars,
        risk_pct=risk_pct,
        soft_warn_threshold=cfg.position_limits.soft_warn_open,
        hard_cap=cfg.position_limits.hard_cap_open,
        open_count=len(open_trades),
    )
```

- [ ] **Step 4: Verify the VM test passes**

Run: `python -m pytest tests/web/test_view_models/test_trades.py -v`
Expected: 1 PASS.

- [ ] **Step 5: Create the entry form template**

Create `swing/web/templates/partials/trade_entry_form.html.j2`:

```html
{#- Trade entry form — swaps into a watchlist row.
    Expects: vm (TradeEntryFormVM) -#}
<tr id="entry-form-{{ vm.ticker }}">
  <td colspan="8">
    <form hx-post="/trades/entry"
          hx-target="closest tr" hx-swap="outerHTML"
          hx-headers='{"HX-Request": "true"}'>
      <input type="hidden" name="ticker" value="{{ vm.ticker }}">
      <div><label>Ticker</label>
        <span>{{ vm.ticker }}</span></div>
      <div><label>Entry date</label>
        <input type="date" name="entry_date" value="{{ vm.entry_date }}" required></div>
      <div><label>Entry price</label>
        <input type="number" step="0.01" min="0" name="entry_price"
               value="{{ '%.2f' | format(vm.entry_price) }}" required></div>
      <div><label>Shares</label>
        <input type="number" step="1" min="1" name="shares"
               value="{{ vm.suggested_shares }}" required>
        <span id="sizing-hint"
              hx-get="/trades/entry/sizing-hint"
              hx-trigger="change from:input[name=entry_price],input[name=initial_stop] delay:200ms"
              hx-include="closest form"
              hx-swap="outerHTML">
          {% if vm.suggested_shares > 0 %}
            Suggested max: <strong>{{ vm.suggested_shares }} sh</strong>
            (~${{ '%.2f' | format(vm.risk_dollars) }} risk =
            {{ '%.2f' | format(vm.risk_pct) }}%)
          {% else %}
            <span class="subtitle">Enter a valid entry price and stop to see sizing</span>
          {% endif %}
        </span></div>
      <div><label>Initial stop</label>
        <input type="number" step="0.01" min="0" name="initial_stop"
               value="{{ '%.2f' | format(vm.initial_stop) }}" required></div>
      {% if vm.watchlist_entry_target is not none %}
      <div><label>Watchlist target</label>
        <input type="hidden" name="watchlist_target" value="{{ vm.watchlist_entry_target }}">
        <span>${{ '%.2f' | format(vm.watchlist_entry_target) }}</span></div>
      {% endif %}
      {% if vm.watchlist_initial_stop is not none %}
        <input type="hidden" name="watchlist_stop" value="{{ vm.watchlist_initial_stop }}">
      {% endif %}
      <div><label>Rationale ★</label>
        <textarea name="rationale" required></textarea></div>
      <div><label>Notes</label>
        <textarea name="notes"></textarea></div>
      <div>
        <button type="submit">Submit</button>
        <button type="button"
                hx-get="/watchlist/{{ vm.ticker }}/expand"
                hx-target="closest tr" hx-swap="outerHTML"
                hx-headers='{"HX-Request": "true"}'>Cancel</button>
      </div>
    </form>
  </td>
</tr>
```

- [ ] **Step 5b: Add Enter button to watchlist_row.html.j2 (R1 Major 2 fix)**

Now that the entry form route exists (just added in this task), wire up the UI trigger. Read `swing/web/templates/partials/watchlist_row.html.j2`, then add an Enter button as the last cell of the row:

```html
  <td>
    <button hx-get="/trades/entry/form?ticker={{ w.ticker }}"
            hx-target="closest tr" hx-swap="outerHTML"
            hx-headers='{"HX-Request": "true"}'>Enter</button>
  </td>
```

Place it as the last cell so existing column-count assertions aren't disturbed. If a prior test asserts a specific cell count (likely in `tests/web/test_routes/test_watchlist_route.py` or `tests/web/test_dashboard_integration.py`), update the test's assertion OR update the outer `<thead>` accordingly. Minor change; document in the commit message.

Affected 3a tests likely needing assertion tweaks: `tests/web/test_routes/test_dashboard_route.py::test_get_root_renders`, `tests/web/test_routes/test_watchlist_route.py::test_get_watchlist_renders`, `tests/web/test_dashboard_integration.py::test_dashboard_no_stale_banner_when_run_is_current`. Run them after this step.

- [ ] **Step 6: Failing route test**

Append to `tests/web/test_routes/test_trades_route.py`:

```python
def test_get_entry_form_renders(seeded_db, monkeypatch):
    """GET /trades/entry/form?ticker=X → trade_entry_form fragment with prefills."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
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

    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=180.95, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=AAPL")
    assert r.status_code == 200
    assert "AAPL" in r.text
    # Entry price prefilled from live snapshot.
    assert "180.95" in r.text
    # Initial stop prefilled from watchlist.
    assert "170.00" in r.text
```

- [ ] **Step 7: Verify it fails**

Run: `python -m pytest tests/web/test_routes/test_trades_route.py::test_get_entry_form_renders -v`
Expected: 404 — route doesn't exist.

- [ ] **Step 8: Add the GET route**

Append to `swing/web/routes/trades.py` (import `build_entry_form_vm` at top):

```python
from swing.web.view_models.trades import build_entry_form_vm


@router.get("/trades/entry/form", response_class=HTMLResponse)
def entry_form(request: Request, ticker: str):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = _templates(request)
    vm = build_entry_form_vm(ticker=ticker, cfg=cfg, cache=cache, executor=executor)
    return templates.TemplateResponse(
        request, "partials/trade_entry_form.html.j2", {"vm": vm},
    )
```

- [ ] **Step 9: Run tests**

Run: `python -m pytest tests/web/test_view_models/test_trades.py tests/web/test_routes/test_trades_route.py -v`
Expected: 8 PASS (1 VM + 6 sizing-hint + 1 entry-form).

- [ ] **Step 10: Full suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 368 passed (366 + 2).

- [ ] **Step 11: Commit**

```bash
git add swing/web/view_models/trades.py swing/web/templates/partials/trade_entry_form.html.j2 swing/web/routes/trades.py tests/web/test_view_models/test_trades.py tests/web/test_routes/test_trades_route.py
git commit -m "feat(web): entry form VM + GET /trades/entry/form"
```

---

## Task 10: POST /trades/entry — happy path (two-call rebuild)

**Files:**
- Modify: `swing/web/routes/trades.py`
- Create: `swing/web/templates/partials/trade_form_error.html.j2`
- Test: `tests/web/test_routes/test_trades_route.py`

Spec §4.3 happy path (success branch, step 6).

- [ ] **Step 1: Write failing test**

Append to `tests/web/test_routes/test_trades_route.py`:

```python
def test_post_entry_success_emits_row_and_oobs(seeded_db, monkeypatch):
    """POST /trades/entry success → primary row + #status-strip OOB + #watchlist-top5 OOB."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
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

    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(
                ticker=t, price=180.95, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        })
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            headers={"HX-Request": "true"},
            data={
                "ticker": "AAPL",
                "entry_date": "2026-04-18",
                "entry_price": "180.95",
                "shares": "5",
                "initial_stop": "170.00",
                "rationale": "A+ entry",
            },
        )
    assert r.status_code == 200
    # Primary target: a new open-position row with id.
    assert "open-position-" in r.text
    assert "AAPL" in r.text
    # OOB fragments present.
    assert "hx-swap-oob" in r.text
    assert 'id="status-strip"' in r.text
    assert 'id="watchlist-top5"' in r.text
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/web/test_routes/test_trades_route.py::test_post_entry_success_emits_row_and_oobs -v`
Expected: 404.

- [ ] **Step 3: Create trade_form_error.html.j2 (used by later tasks too, but needed here as a fallback import)**

Create `swing/web/templates/partials/trade_form_error.html.j2`:

```html
{#- Trade form error fragment.
    Expects: error_message (str), form_body (str optional — re-rendered form HTML).
    Placed ABOVE a re-rendered form so user sees the error and can adjust. -#}
<tr class="trade-form-error">
  <td colspan="8">
    <div class="banner banner-degraded" role="alert">{{ error_message }}</div>
    {% if form_body is defined and form_body %}
      {{ form_body | safe }}
    {% endif %}
  </td>
</tr>
```

- [ ] **Step 4: Add POST /trades/entry happy path**

Append to `swing/web/routes/trades.py`:

Imports to add:
```python
from datetime import datetime
from fastapi import Form, HTTPException
from markupsafe import Markup
from swing.data.repos.trades import list_open_trades
from swing.trades.entry import (
    EntryRequest, HardCapException, DuplicateOpenPositionException,
    SoftWarnException, record_entry,
)
from swing.web.view_models.dashboard import build_dashboard
from swing.web.view_models.open_positions_row import build_open_positions_row
```

Route:
```python
@router.post("/trades/entry", response_class=HTMLResponse)
def entry_post(
    request: Request,
    ticker: str = Form(...),
    entry_date: str = Form(...),
    entry_price: float = Form(...),
    shares: int = Form(...),
    initial_stop: float = Form(...),
    rationale: str = Form(...),
    notes: str | None = Form(None),
    watchlist_target: float | None = Form(None),
    watchlist_stop: float | None = Form(None),
    force: str | None = Form(None),
):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = _templates(request)

    req = EntryRequest(
        ticker=ticker.upper(),
        entry_date=entry_date,
        entry_price=entry_price,
        shares=shares,
        initial_stop=initial_stop,
        watchlist_entry_target=watchlist_target,
        watchlist_initial_stop=watchlist_stop,
        notes=notes,
        rationale=rationale,
        event_ts=datetime.now().isoformat(timespec="seconds"),
    )

    conn = connect(cfg.paths.db_path)
    try:
        try:
            result = record_entry(
                conn, req,
                soft_warn=cfg.position_limits.soft_warn_open,
                hard_cap=cfg.position_limits.hard_cap_open,
                force=(force == "true"),
            )
        except SoftWarnException:
            # Soft-warn 2-step flow — implemented in Task 11.
            raise
        except (HardCapException, DuplicateOpenPositionException) as exc:
            # Error-path rendering — implemented in Task 12. For now re-raise so
            # the happy-path test fails loudly if it hits these.
            raise
    finally:
        conn.close()

    # Two-call rebuild (spec §4.3 step 6).
    # a) Primary row.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            open_trades = list_open_trades(conn)
    finally:
        conn.close()
    new_trade = next(t for t in open_trades if t.id == result.trade_id)
    row_vm = build_open_positions_row(
        trade=new_trade, cfg=cfg, cache=cache, executor=executor,
    )

    # b) Dashboard rebuild — source for OOB fragments.
    dashboard_vm = build_dashboard(cfg=cfg, cache=cache, executor=executor)

    # Render response: primary row + #status-strip OOB + #watchlist-top5 OOB.
    # Single-contract partial: pass only `row` (R1 Major 3 fix).
    row_html = templates.get_template("partials/open_positions_row.html.j2").render(
        request=request, row=row_vm,
    )
    status_strip_html = templates.get_template("partials/status_strip.html.j2").render(
        request=request, vm=dashboard_vm,
    )
    watchlist_html = templates.get_template(
        "partials/prices_refresh_container.html.j2"
    ).render(request=request, vm=dashboard_vm)
    # prices_refresh_container already emits status-strip + open-positions + watchlist
    # as OOB — but we only need status-strip + watchlist. Extract via string surgery
    # would be brittle; instead, emit the fragments we need explicitly.
    return HTMLResponse(Markup(
        f'{row_html}'
        f'<div id="status-strip" hx-swap-oob="true">{status_strip_html}</div>'
        f'<section id="watchlist-top5" hx-swap-oob="true">{watchlist_html}</section>'
    ))
```

Note on the response construction: the OOB wrapper divs MUST match the dashboard template's IDs exactly — `#status-strip` and `#watchlist-top5`. If the dashboard template uses a different outer element or ID, adjust to match. Re-read `swing/web/templates/dashboard.html.j2` to verify the IDs.

- [ ] **Step 5: Run the test**

Run: `python -m pytest tests/web/test_routes/test_trades_route.py::test_post_entry_success_emits_row_and_oobs -v`
Expected: PASS.

- [ ] **Step 6: Full suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 369 passed (368 + 1).

- [ ] **Step 7: Commit**

```bash
git add swing/web/routes/trades.py swing/web/templates/partials/trade_form_error.html.j2 tests/web/test_routes/test_trades_route.py
git commit -m "feat(web): POST /trades/entry happy path (two-call rebuild, row + OOB)"
```

---

## Task 11: POST /trades/entry — soft-warn 2-step flow

**Files:**
- Modify: `swing/web/routes/trades.py`
- Create: `swing/web/templates/partials/soft_warn_confirm.html.j2`
- Test: `tests/web/test_routes/test_trades_route.py`

Spec §4.3 step 4. First submit at soft cap → confirm fragment with hidden `force=true`. Second submit with `force=true` → success.

- [ ] **Step 1: Create soft_warn_confirm.html.j2**

Create `swing/web/templates/partials/soft_warn_confirm.html.j2`:

```html
{#- Soft-warn 2-step confirmation fragment.
    Expects: form_values (dict of the original form submission fields). -#}
<tr class="soft-warn-confirm">
  <td colspan="8">
    <div class="banner" style="background:#fff3cd;color:#92400e;padding:12px;">
      <strong>⚠ Soft cap reached ({{ form_values.open_count }}/{{ form_values.soft_warn }}).</strong>
      <p>Opening this trade exceeds your configured soft-warn threshold.
         Hard cap is {{ form_values.hard_cap }} (still available).</p>
      <form hx-post="/trades/entry" hx-target="closest tr" hx-swap="outerHTML"
            hx-headers='{"HX-Request": "true"}'>
        {% for key, value in form_values.items() %}
          {% if key not in ("open_count", "soft_warn", "hard_cap") %}
            <input type="hidden" name="{{ key }}" value="{{ value }}">
          {% endif %}
        {% endfor %}
        <input type="hidden" name="force" value="true">
        <button type="submit">Submit anyway</button>
        <button type="button"
                hx-get="/watchlist/{{ form_values.ticker }}/expand"
                hx-target="closest tr" hx-swap="outerHTML"
                hx-headers='{"HX-Request": "true"}'>Cancel</button>
      </form>
    </div>
  </td>
</tr>
```

- [ ] **Step 2: Write failing test**

Append to `tests/web/test_routes/test_trades_route.py`:

```python
def test_post_entry_soft_warn_2step(seeded_db, monkeypatch):
    """First submit at soft cap → confirm fragment; second with force=true → success."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade, WatchlistEntry
    from swing.data.repos.trades import insert_trade_with_event
    from swing.data.repos.watchlist import upsert_watchlist_entry
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    # Seed open trades up to soft_warn_open (default 4).
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            for i, t in enumerate(("MSFT", "NVDA", "GOOG", "META")):
                insert_trade_with_event(conn, Trade(
                    id=None, ticker=t, entry_date="2026-04-15",
                    entry_price=100.0, initial_shares=1, initial_stop=90.0,
                    current_stop=90.0, status="open",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ), event_ts=f"2026-04-15T09:{30+i}:00")
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

    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(
                ticker=t, price=180.95, asof=datetime.now(),
                is_stale=False, source="live",
            ) for t in tickers
        })
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    form_data = {
        "ticker": "AAPL", "entry_date": "2026-04-18",
        "entry_price": "180.95", "shares": "1", "initial_stop": "170.00",
        "rationale": "5th trade past soft cap",
    }
    with TestClient(app) as client:
        # First submit — no force. Should get soft_warn_confirm fragment.
        r1 = client.post("/trades/entry", headers={"HX-Request": "true"}, data=form_data)
        assert r1.status_code == 200
        assert "Soft cap reached" in r1.text
        assert 'name="force" value="true"' in r1.text
        # Second submit — with force=true. Should succeed.
        form_data2 = dict(form_data)
        form_data2["force"] = "true"
        r2 = client.post("/trades/entry", headers={"HX-Request": "true"}, data=form_data2)
        assert r2.status_code == 200
        assert "open-position-" in r2.text
```

- [ ] **Step 3: Verify it fails**

Run: `python -m pytest tests/web/test_routes/test_trades_route.py::test_post_entry_soft_warn_2step -v`
Expected: FAIL — first submit currently raises 500 (SoftWarnException re-raised).

- [ ] **Step 4: Handle SoftWarnException in the route**

Replace the `except SoftWarnException: raise` block in `swing/web/routes/trades.py::entry_post` with:

```python
        except SoftWarnException:
            # First submit at soft cap — render the 2-step confirm fragment.
            # Re-serialize the submitted form values so the next submit carries
            # them + force=true (spec §4.3 step 4).
            form_values = {
                "ticker": req.ticker,
                "entry_date": req.entry_date,
                "entry_price": req.entry_price,
                "shares": req.shares,
                "initial_stop": req.initial_stop,
                "rationale": req.rationale,
                "notes": req.notes or "",
                "watchlist_target": req.watchlist_entry_target or "",
                "watchlist_stop": req.watchlist_initial_stop or "",
                "open_count": cfg.position_limits.soft_warn_open,   # shown in banner
                "soft_warn": cfg.position_limits.soft_warn_open,
                "hard_cap": cfg.position_limits.hard_cap_open,
            }
            return templates.TemplateResponse(
                request, "partials/soft_warn_confirm.html.j2",
                {"form_values": form_values},
            )
```

- [ ] **Step 5: Run the test**

Run: `python -m pytest tests/web/test_routes/test_trades_route.py::test_post_entry_soft_warn_2step -v`
Expected: PASS.

- [ ] **Step 6: Full suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 370 passed.

- [ ] **Step 7: Commit**

```bash
git add swing/web/routes/trades.py swing/web/templates/partials/soft_warn_confirm.html.j2 tests/web/test_routes/test_trades_route.py
git commit -m "feat(web): POST /trades/entry soft-warn 2-step confirm fragment"
```

---

## Task 12: POST /trades/entry — error paths (hard-cap, duplicate)

**Files:**
- Modify: `swing/web/routes/trades.py`
- Test: `tests/web/test_routes/test_trades_route.py`

Spec §4.3 step 5 + §5.1 case 1.

- [ ] **Step 1: Write failing tests**

Append to `tests/web/test_routes/test_trades_route.py`:

```python
def test_post_entry_hard_cap_error(seeded_db, monkeypatch):
    """Hard cap reached → 400 trade_form_error fragment, no UI bypass."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    # Seed to hard_cap (default 6).
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            for i, t in enumerate(("A", "B", "C", "D", "E", "F")):
                insert_trade_with_event(conn, Trade(
                    id=None, ticker=t, entry_date="2026-04-15",
                    entry_price=100.0, initial_shares=1, initial_stop=90.0,
                    current_stop=90.0, status="open",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ), event_ts=f"2026-04-15T09:{30+i}:00")
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry", headers={"HX-Request": "true"},
            data={
                "ticker": "AAPL", "entry_date": "2026-04-18",
                "entry_price": "180.0", "shares": "1",
                "initial_stop": "170.0", "rationale": "test",
                "force": "true",   # bypass soft-warn; but hard cap still blocks
            },
        )
    assert r.status_code == 400
    assert "hard cap" in r.text.lower() or "hard_cap" in r.text.lower()


def test_post_entry_duplicate_error(seeded_db, monkeypatch):
    """Duplicate open position → 400 fragment with drift-recovery wording."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event
    from swing.web.price_cache import PriceCache

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="AAPL", entry_date="2026-04-15",
                entry_price=180.0, initial_shares=5, initial_stop=170.0,
                current_stop=170.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry", headers={"HX-Request": "true"},
            data={
                "ticker": "AAPL", "entry_date": "2026-04-18",
                "entry_price": "182.0", "shares": "3",
                "initial_stop": "175.0", "rationale": "add-on",
            },
        )
    assert r.status_code == 400
    assert "already" in r.text.lower() or "open trade" in r.text.lower()
```

- [ ] **Step 2: Verify they fail**

Run: `python -m pytest tests/web/test_routes/test_trades_route.py::test_post_entry_hard_cap_error tests/web/test_routes/test_trades_route.py::test_post_entry_duplicate_error -v`
Expected: FAIL — currently raise 500.

- [ ] **Step 3: Handle the exceptions**

Replace the `except (HardCapException, DuplicateOpenPositionException) as exc: raise` block in `swing/web/routes/trades.py::entry_post` with:

```python
        except (HardCapException, DuplicateOpenPositionException) as exc:
            return templates.TemplateResponse(
                request, "partials/trade_form_error.html.j2",
                {"error_message": str(exc), "form_body": None},
                status_code=400,
            )
```

- [ ] **Step 4: Run the tests**

Run: `python -m pytest tests/web/test_routes/test_trades_route.py::test_post_entry_hard_cap_error tests/web/test_routes/test_trades_route.py::test_post_entry_duplicate_error -v`
Expected: 2 PASS.

- [ ] **Step 5: Full suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 372 passed (370 + 2).

- [ ] **Step 6: Commit**

```bash
git add swing/web/routes/trades.py tests/web/test_routes/test_trades_route.py
git commit -m "feat(web): POST /trades/entry renders 400 fragment for hard-cap / duplicate"
```

---

## Task 13: Exit form VM + GET /trades/<id>/exit/form

**Files:**
- Modify: `swing/web/view_models/trades.py`
- Create: `swing/web/templates/partials/trade_exit_form.html.j2`
- Modify: `swing/web/routes/trades.py`
- Test: `tests/web/test_view_models/test_trades.py`, `tests/web/test_routes/test_trades_route.py`

Spec §3.1 (TradeExitFormVM), §3.2 (trade_exit_form template).

- [ ] **Step 1: Failing VM test**

Append to `tests/web/test_view_models/test_trades.py`:

```python
def test_build_exit_form_vm_shape(seeded_db, monkeypatch):
    """Exit form VM shows remaining_shares, live exit_price prefill, reason choices."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.price_cache import PriceCache, PriceSnapshot
    from swing.web.view_models.trades import build_exit_form_vm, TradeExitFormVM

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()

    cache = PriceCache(cfg)
    monkeypatch.setattr(cache, "get_many",
        lambda tickers, deadline_seconds, *, executor=None: {
            "NVDA": PriceSnapshot(
                ticker="NVDA", price=932.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })

    vm = build_exit_form_vm(
        trade_id=trade.id, cfg=cfg, cache=cache, executor=None,
    )
    assert isinstance(vm, TradeExitFormVM)
    assert vm.trade.ticker == "NVDA"
    assert vm.exit_price == 932.0
    assert vm.remaining_shares == 5  # no exits yet
    assert "stop-hit" in vm.reasons
    assert "manual" in vm.reasons
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/web/test_view_models/test_trades.py::test_build_exit_form_vm_shape -v`
Expected: ImportError.

- [ ] **Step 3: Implement TradeExitFormVM + build_exit_form_vm**

Append to `swing/web/view_models/trades.py`:

```python
from swing.data.models import Trade
from swing.data.repos.trades import get_trade, list_exits_for_trade
from swing.trades.exit import ExitReason


@dataclass(frozen=True)
class TradeExitFormVM:
    trade: Trade
    exit_date: str
    exit_price: float
    remaining_shares: int
    reasons: tuple[str, ...]


def build_exit_form_vm(
    *, trade_id: int, cfg: Config, cache: PriceCache, executor,
) -> TradeExitFormVM | None:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = get_trade(conn, trade_id)
            if trade is None or trade.status != "open":
                return None
            exits = list_exits_for_trade(conn, trade_id)
    finally:
        conn.close()
    remaining = trade.initial_shares - sum(e.shares for e in exits)

    prices = cache.get_many(
        [trade.ticker],
        deadline_seconds=cfg.web.price_fetch_deadline_seconds,
        executor=executor,
    )
    snap = prices.get(trade.ticker)
    exit_price = snap.price if snap else trade.entry_price  # conservative fallback

    return TradeExitFormVM(
        trade=trade,
        exit_date=date.today().isoformat(),
        exit_price=exit_price,
        remaining_shares=remaining,
        reasons=tuple(r.value for r in ExitReason),
    )
```

- [ ] **Step 4: Run VM test**

Run: `python -m pytest tests/web/test_view_models/test_trades.py::test_build_exit_form_vm_shape -v`
Expected: PASS.

- [ ] **Step 5: Create trade_exit_form.html.j2**

Create `swing/web/templates/partials/trade_exit_form.html.j2`:

```html
{#- Trade exit form — swaps into an open-position row.
    Expects: vm (TradeExitFormVM) -#}
<tr id="exit-form-{{ vm.trade.id }}">
  <td colspan="8">
    <form hx-post="/trades/{{ vm.trade.id }}/exit"
          hx-target="closest tr" hx-swap="outerHTML"
          hx-headers='{"HX-Request": "true"}'>
      <div><label>Trade</label>
        <span>#{{ vm.trade.id }} {{ vm.trade.ticker }} —
              {{ vm.remaining_shares }} sh remaining, stop ${{ '%.2f' | format(vm.trade.current_stop) }}</span></div>
      <div><label>Exit date</label>
        <input type="date" name="exit_date" value="{{ vm.exit_date }}" required></div>
      <div><label>Exit price</label>
        <input type="number" step="0.01" min="0" name="exit_price"
               value="{{ '%.2f' | format(vm.exit_price) }}" required></div>
      <div><label>Shares</label>
        <input type="number" step="1" min="1" max="{{ vm.remaining_shares }}"
               name="shares" value="{{ vm.remaining_shares }}" required></div>
      <div><label>Reason ★</label>
        <select name="reason" required>
          {% for reason in vm.reasons %}
            <option value="{{ reason }}">{{ reason }}</option>
          {% endfor %}
        </select></div>
      <div><label>Rationale ★</label>
        <textarea name="rationale" required></textarea></div>
      <div><label>Notes</label><textarea name="notes"></textarea></div>
      <div>
        <button type="submit">Submit</button>
        <button type="button"
                hx-get="/trades/{{ vm.trade.id }}/cancel"
                hx-target="closest tr" hx-swap="outerHTML"
                hx-headers='{"HX-Request": "true"}'>Cancel</button>
      </div>
    </form>
  </td>
</tr>
```

Note: the Cancel button's `hx-get` needs a route that returns the normal open-position row. We'll add that in Task 16.

- [ ] **Step 5b: Add Exit button to open_positions_row.html.j2 (R1 Major 2 fix)**

Now that the exit form GET route is being added in this task, wire up the UI trigger. Open `swing/web/templates/partials/open_positions_row.html.j2` and append a new `<td>` cell at the end of the row:

```html
  <td class="row-actions">
    <button hx-get="/trades/{{ row.trade.id }}/exit/form"
            hx-target="closest tr" hx-swap="outerHTML"
            hx-headers='{"HX-Request": "true"}'>Exit</button>
    {#- Adjust stop button appended in Task 15 as its route comes online -#}
  </td>
```

Update any `<thead>` column count in `open_positions.html.j2` to add the matching column header. Affected 3a tests likely needing assertion tweaks: `tests/web/test_routes/test_dashboard_route.py::test_get_root_renders`, `tests/web/test_dashboard_integration.py::test_dashboard_no_stale_banner_when_run_is_current`, `tests/web/test_routes/test_pipeline_route.py::test_post_prices_refresh_emits_three_oob_regions`. Run them after this step and fix assertions minimally.

- [ ] **Step 6: Failing route test**

Append to `tests/web/test_routes/test_trades_route.py`:

```python
def test_get_exit_form_renders(seeded_db, monkeypatch):
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "NVDA": PriceSnapshot(
                ticker="NVDA", price=932.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{trade.id}/exit/form",
                       headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "NVDA" in r.text
    assert "932.00" in r.text  # exit price prefilled
    assert "stop-hit" in r.text  # reasons select populated


def test_get_exit_form_for_closed_trade_returns_404_fragment(seeded_db):
    """Missing/closed trade → HTMX-aware 404 fragment (§5.1 case 4 + §5.2)."""
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/99999/exit/form",
                       headers={"HX-Request": "true"})
    assert r.status_code == 404
    # Not JSON — HTMX-aware fragment.
    assert "banner" in r.text
    assert "not found" in r.text.lower() or "not open" in r.text.lower()
```

- [ ] **Step 7: Verify failures**

Run: `python -m pytest tests/web/test_routes/test_trades_route.py::test_get_exit_form_renders tests/web/test_routes/test_trades_route.py::test_get_exit_form_for_closed_trade_returns_404_fragment -v`
Expected: 404 (route missing) / NotFound.

- [ ] **Step 8: Add the GET route**

Append to `swing/web/routes/trades.py` (import `build_exit_form_vm`):

```python
from swing.web.view_models.trades import build_exit_form_vm


@router.get("/trades/{trade_id}/exit/form", response_class=HTMLResponse)
def exit_form(request: Request, trade_id: int):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = _templates(request)
    vm = build_exit_form_vm(trade_id=trade_id, cfg=cfg, cache=cache, executor=executor)
    if vm is None:
        raise HTTPException(status_code=404, detail=f"Trade #{trade_id} not found or not open")
    return templates.TemplateResponse(
        request, "partials/trade_exit_form.html.j2", {"vm": vm},
    )
```

- [ ] **Step 9: Run tests**

Run: `python -m pytest tests/web/test_view_models/test_trades.py tests/web/test_routes/test_trades_route.py -v`
Expected: all pass (+2 new).

- [ ] **Step 10: Full suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 374 passed (372 + 2).

- [ ] **Step 11: Commit**

```bash
git add swing/web/view_models/trades.py swing/web/templates/partials/trade_exit_form.html.j2 swing/web/routes/trades.py tests/web/test_view_models/test_trades.py tests/web/test_routes/test_trades_route.py
git commit -m "feat(web): exit form VM + GET /trades/{id}/exit/form with HTMX 404"
```

---

## Task 14: POST /trades/<id>/exit — full close + partial + drift

**Files:**
- Modify: `swing/web/routes/trades.py`
- Test: `tests/web/test_routes/test_trades_route.py`

Spec §4.4.

- [ ] **Step 1: Failing tests**

Append to `tests/web/test_routes/test_trades_route.py`:

```python
def test_post_exit_full_close_removes_row(seeded_db, monkeypatch):
    """Full close → row disappears; #status-strip OOB only (no watchlist OOB)."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(ticker=t, price=932.0, asof=datetime.now(),
                             is_stale=False, source="live")
            for t in tickers
        })
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/exit", headers={"HX-Request": "true"},
            data={"exit_date": "2026-04-18", "exit_price": "932.00",
                  "shares": "5", "reason": "manual", "rationale": "full close"},
        )
    assert r.status_code == 200
    # Full close: no <tr> for the now-closed position; empty/hidden stub OK.
    assert f"open-position-{trade.id}" not in r.text or 'display:none' in r.text.lower()
    # Status-strip OOB present.
    assert 'id="status-strip"' in r.text
    assert "hx-swap-oob" in r.text
    # Watchlist OOB NOT emitted on exit.
    assert 'id="watchlist-top5"' not in r.text


def test_post_exit_partial_updates_row(seeded_db, monkeypatch):
    """Partial close → row re-rendered with reduced remaining_shares."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=10, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(ticker=t, price=932.0, asof=datetime.now(),
                             is_stale=False, source="live")
            for t in tickers
        })
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/exit", headers={"HX-Request": "true"},
            data={"exit_date": "2026-04-18", "exit_price": "932.00",
                  "shares": "3", "reason": "partial", "rationale": "lock in partial gain"},
        )
    assert r.status_code == 200
    assert f"open-position-{trade.id}" in r.text
    # Remaining shares: 10 - 3 = 7.
    assert "7 / 10" in r.text or ">7<" in r.text


def test_post_exit_shares_too_many_400(seeded_db, monkeypatch):
    """Shares > remaining → 400 error fragment (§5.1 case 2)."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.price_cache import PriceCache

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/exit", headers={"HX-Request": "true"},
            data={"exit_date": "2026-04-18", "exit_price": "932.00",
                  "shares": "10", "reason": "manual",  # over-exit
                  "rationale": "too many"},
        )
    assert r.status_code == 400
    assert "remaining" in r.text.lower() or "exceed" in r.text.lower()
```

- [ ] **Step 2: Verify they fail**

Run: `python -m pytest tests/web/test_routes/test_trades_route.py -k "exit" -v`
Expected: 3 fail — POST route missing.

- [ ] **Step 3: Add POST /trades/<id>/exit**

Append to `swing/web/routes/trades.py`:

Imports (merge):
```python
from swing.trades.exit import ExitReason, ExitRequest, record_exit
from swing.data.repos.trades import get_trade
```

Route:
```python
@router.post("/trades/{trade_id}/exit", response_class=HTMLResponse)
def exit_post(
    request: Request,
    trade_id: int,
    exit_date: str = Form(...),
    exit_price: float = Form(...),
    shares: int = Form(...),
    reason: str = Form(...),
    rationale: str = Form(...),
    notes: str | None = Form(None),
):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = _templates(request)

    # Validate reason.
    try:
        reason_enum = ExitReason(reason)
    except ValueError:
        return templates.TemplateResponse(
            request, "partials/trade_form_error.html.j2",
            {"error_message": f"Invalid reason: {reason}", "form_body": None},
            status_code=400,
        )

    req = ExitRequest(
        trade_id=trade_id, exit_date=exit_date, exit_price=exit_price,
        shares=shares, reason=reason_enum, notes=notes, rationale=rationale,
        event_ts=datetime.now().isoformat(timespec="seconds"),
    )

    conn = connect(cfg.paths.db_path)
    try:
        try:
            result = record_exit(conn, req)
        except Exception as exc:
            # Phase 2's record_exit raises on shares > remaining and other validations.
            return templates.TemplateResponse(
                request, "partials/trade_form_error.html.j2",
                {"error_message": str(exc), "form_body": None},
                status_code=400,
            )
    finally:
        conn.close()

    # Two-call rebuild.
    dashboard_vm = build_dashboard(cfg=cfg, cache=cache, executor=executor)
    status_strip_html = templates.get_template("partials/status_strip.html.j2").render(
        request=request, vm=dashboard_vm,
    )

    if result.fully_closed:
        # Primary target: empty/hidden stub so the row disappears.
        return HTMLResponse(Markup(
            f'<tr id="open-position-{trade_id}" style="display:none"></tr>'
            f'<div id="status-strip" hx-swap-oob="true">{status_strip_html}</div>'
        ))

    # Partial: re-render the row.
    updated = get_trade(conn := connect(cfg.paths.db_path), trade_id)
    conn.close()
    row_vm = build_open_positions_row(
        trade=updated, cfg=cfg, cache=cache, executor=executor,
    )
    row_html = templates.get_template("partials/open_positions_row.html.j2").render(
        request=request, row=row_vm,
        t=row_vm.trade, snap=row_vm.price_snapshot, advisories=row_vm.advisories,
    )
    return HTMLResponse(Markup(
        f'{row_html}'
        f'<div id="status-strip" hx-swap-oob="true">{status_strip_html}</div>'
    ))
```

- [ ] **Step 4: Run tests**

Run: `python -m pytest tests/web/test_routes/test_trades_route.py -k "exit" -v`
Expected: 3 PASS (plus 2 earlier exit tests = 5 pass).

- [ ] **Step 5: Full suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 377 passed (374 + 3).

- [ ] **Step 6: Commit**

```bash
git add swing/web/routes/trades.py tests/web/test_routes/test_trades_route.py
git commit -m "feat(web): POST /trades/{id}/exit full/partial + shares-too-many drift"
```

---

## Task 15: Stop form VM + GET /trades/<id>/stop/form + POST

**Files:**
- Modify: `swing/web/view_models/trades.py`
- Create: `swing/web/templates/partials/trade_stop_form.html.j2`
- Modify: `swing/web/routes/trades.py`
- Test: `tests/web/test_view_models/test_trades.py`, `tests/web/test_routes/test_trades_route.py`

Spec §3.1 (TradeStopFormVM), §4.5. Combines VM + GET + POST into one task since stop flow is simplest (3 fields).

- [ ] **Step 1: Failing VM test**

Append to `tests/web/test_view_models/test_trades.py`:

```python
def test_build_stop_form_vm_shape(seeded_db):
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.view_models.trades import build_stop_form_vm, TradeStopFormVM

    cfg, _ = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()

    vm = build_stop_form_vm(trade_id=trade.id, cfg=cfg)
    assert isinstance(vm, TradeStopFormVM)
    assert vm.trade.ticker == "NVDA"
    assert vm.current_stop == 860.0
    assert vm.suggested_stops == ()  # 3b leaves this empty; 3c populates
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/web/test_view_models/test_trades.py::test_build_stop_form_vm_shape -v`
Expected: ImportError.

- [ ] **Step 3: Implement TradeStopFormVM + build_stop_form_vm**

Append to `swing/web/view_models/trades.py`:

```python
@dataclass(frozen=True)
class TradeStopFormVM:
    trade: Trade
    current_stop: float
    suggested_stops: tuple[tuple[str, float], ...]  # empty in 3b; 3c populates


def build_stop_form_vm(*, trade_id: int, cfg: Config) -> TradeStopFormVM | None:
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            trade = get_trade(conn, trade_id)
            if trade is None or trade.status != "open":
                return None
    finally:
        conn.close()
    return TradeStopFormVM(
        trade=trade, current_stop=trade.current_stop, suggested_stops=(),
    )
```

- [ ] **Step 4: Run VM test**

Run: `python -m pytest tests/web/test_view_models/test_trades.py::test_build_stop_form_vm_shape -v`
Expected: PASS.

- [ ] **Step 5: Create trade_stop_form.html.j2**

Create `swing/web/templates/partials/trade_stop_form.html.j2`:

```html
{#- Trade stop-adjust form — swaps into an open-position row.
    Expects: vm (TradeStopFormVM) -#}
<tr id="stop-form-{{ vm.trade.id }}">
  <td colspan="8">
    <form hx-post="/trades/{{ vm.trade.id }}/stop"
          hx-target="closest tr" hx-swap="outerHTML"
          hx-headers='{"HX-Request": "true"}'>
      <div><label>Trade</label>
        <span>#{{ vm.trade.id }} {{ vm.trade.ticker }} —
              current stop ${{ '%.2f' | format(vm.current_stop) }}</span></div>
      <div><label>New stop</label>
        <input type="number" step="0.01" min="0" name="new_stop"
               value="{{ '%.2f' | format(vm.current_stop) }}" required></div>
      <div><label>Rationale ★</label>
        <textarea name="rationale" required></textarea></div>
      <div>
        <button type="submit">Submit</button>
        <button type="button"
                hx-get="/trades/{{ vm.trade.id }}/cancel"
                hx-target="closest tr" hx-swap="outerHTML"
                hx-headers='{"HX-Request": "true"}'>Cancel</button>
      </div>
    </form>
  </td>
</tr>
```

- [ ] **Step 5b: Append Adjust stop button to open_positions_row.html.j2 (R1 Major 2 fix)**

Now that the stop form GET route is being added in this task, wire up the UI trigger. Open `swing/web/templates/partials/open_positions_row.html.j2` and append the button to the row-actions `<td>` that Task 13 created:

```html
  <td class="row-actions">
    <button hx-get="/trades/{{ row.trade.id }}/exit/form"
            hx-target="closest tr" hx-swap="outerHTML"
            hx-headers='{"HX-Request": "true"}'>Exit</button>
    <button hx-get="/trades/{{ row.trade.id }}/stop/form"
            hx-target="closest tr" hx-swap="outerHTML"
            hx-headers='{"HX-Request": "true"}'>Adjust stop</button>
  </td>
```

No new column-count changes (reusing the cell Task 13 added). Run the 3a integration suite to confirm: `python -m pytest tests/web/test_dashboard_integration.py -v`.

- [ ] **Step 6: Failing route tests**

Append to `tests/web/test_routes/test_trades_route.py`:

```python
def test_get_stop_form_renders(seeded_db):
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{trade.id}/stop/form",
                       headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert "NVDA" in r.text
    assert "860.00" in r.text


def test_post_stop_adjust_success(seeded_db, monkeypatch):
    """Stop-adjust success → row re-render; no OOB."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "NVDA": PriceSnapshot(ticker="NVDA", price=932.0, asof=datetime.now(),
                                   is_stale=False, source="live"),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/stop", headers={"HX-Request": "true"},
            data={"new_stop": "912.00", "rationale": "trail to 10MA"},
        )
    assert r.status_code == 200
    assert f"open-position-{trade.id}" in r.text
    assert "912.00" in r.text
    # Stop-adjust emits NO OOB.
    assert 'id="status-strip"' not in r.text


def test_post_stop_regression_400_with_updated_current(seeded_db):
    """Lowering stop → 400 fragment with updated current_stop prefilled (§5.1 case 3)."""
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=900.0, status="open",  # someone already trailed to BE
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/stop", headers={"HX-Request": "true"},
            data={"new_stop": "880.00", "rationale": "attempt lower"},
        )
    assert r.status_code == 400
    # Error message names the actual current_stop.
    assert "900" in r.text
    assert "force" in r.text.lower()  # CLI hint
```

- [ ] **Step 7: Verify failures**

Run: `python -m pytest tests/web/test_routes/test_trades_route.py -k "stop" -v`
Expected: 3 fail.

- [ ] **Step 8: Add GET + POST stop routes**

Append to `swing/web/routes/trades.py`:

Imports (merge):
```python
from swing.trades.stop_adjust import StopAdjustRequest, StopRegressionError, adjust_stop
from swing.web.view_models.trades import build_stop_form_vm
```

Routes:
```python
@router.get("/trades/{trade_id}/stop/form", response_class=HTMLResponse)
def stop_form(request: Request, trade_id: int):
    cfg = request.app.state.cfg
    templates = _templates(request)
    vm = build_stop_form_vm(trade_id=trade_id, cfg=cfg)
    if vm is None:
        raise HTTPException(status_code=404, detail=f"Trade #{trade_id} not found or not open")
    return templates.TemplateResponse(
        request, "partials/trade_stop_form.html.j2", {"vm": vm},
    )


@router.post("/trades/{trade_id}/stop", response_class=HTMLResponse)
def stop_post(
    request: Request, trade_id: int,
    new_stop: float = Form(...), rationale: str = Form(...),
):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = _templates(request)

    req = StopAdjustRequest(
        trade_id=trade_id, new_stop=new_stop, rationale=rationale,
        event_ts=datetime.now().isoformat(timespec="seconds"), force=False,
    )
    conn = connect(cfg.paths.db_path)
    try:
        try:
            adjust_stop(conn, req)
        except StopRegressionError as exc:
            return templates.TemplateResponse(
                request, "partials/trade_form_error.html.j2",
                {"error_message": (
                    f"{exc}. Use CLI `swing trade stop-adjust --trade-id {trade_id} "
                    f"--new-stop {new_stop} --rationale ... --force` if intentional."
                ), "form_body": None},
                status_code=400,
            )
    finally:
        conn.close()

    # Row-only render (no OOB).
    conn = connect(cfg.paths.db_path)
    try:
        updated = get_trade(conn, trade_id)
    finally:
        conn.close()
    row_vm = build_open_positions_row(
        trade=updated, cfg=cfg, cache=cache, executor=executor,
    )
    row_html = templates.get_template("partials/open_positions_row.html.j2").render(
        request=request, row=row_vm,
        t=row_vm.trade, snap=row_vm.price_snapshot, advisories=row_vm.advisories,
    )
    return HTMLResponse(Markup(row_html))
```

- [ ] **Step 9: Run tests**

Run: `python -m pytest tests/web/test_view_models/test_trades.py tests/web/test_routes/test_trades_route.py -v`
Expected: all pass (+4 new stop tests).

- [ ] **Step 10: Full suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 381 passed (377 + 4).

- [ ] **Step 11: Commit**

```bash
git add swing/web/view_models/trades.py swing/web/templates/partials/trade_stop_form.html.j2 swing/web/routes/trades.py tests/web/test_view_models/test_trades.py tests/web/test_routes/test_trades_route.py
git commit -m "feat(web): stop-adjust VM + GET /trades/{id}/stop/form + POST with regression drift"
```

---

## Task 16: Cancel endpoint for form rows

**Files:**
- Modify: `swing/web/routes/trades.py`
- Test: `tests/web/test_routes/test_trades_route.py`

The exit/stop form Cancel buttons `hx-get="/trades/<id>/cancel"` to get the normal row back. Spec implicit (row must revert on Cancel).

- [ ] **Step 1: Failing test**

Append to `tests/web/test_routes/test_trades_route.py`:

```python
def test_get_trade_cancel_returns_normal_row(seeded_db, monkeypatch):
    """GET /trades/{id}/cancel → normal open-positions row."""
    from datetime import datetime
    from swing.data.db import connect
    from swing.data.models import Trade
    from swing.data.repos.trades import insert_trade_with_event, list_open_trades
    from swing.web.price_cache import PriceCache, PriceSnapshot

    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "NVDA": PriceSnapshot(ticker="NVDA", price=932.0, asof=datetime.now(),
                                   is_stale=False, source="live"),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(f"/trades/{trade.id}/cancel",
                       headers={"HX-Request": "true"})
    assert r.status_code == 200
    assert f"open-position-{trade.id}" in r.text
    # The row has Exit + Adjust stop buttons (normal state).
    assert "Exit" in r.text
    assert "Adjust stop" in r.text
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/web/test_routes/test_trades_route.py::test_get_trade_cancel_returns_normal_row -v`
Expected: 404.

- [ ] **Step 3: Add the cancel route**

Append to `swing/web/routes/trades.py`:

```python
@router.get("/trades/{trade_id}/cancel", response_class=HTMLResponse)
def trade_cancel(request: Request, trade_id: int):
    """Return the normal open-position row (no form). Used by Cancel buttons."""
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    templates = _templates(request)

    conn = connect(cfg.paths.db_path)
    try:
        trade = get_trade(conn, trade_id)
    finally:
        conn.close()
    if trade is None or trade.status != "open":
        raise HTTPException(status_code=404, detail=f"Trade #{trade_id} not found or not open")

    row_vm = build_open_positions_row(
        trade=trade, cfg=cfg, cache=cache, executor=executor,
    )
    # Single-contract partial: pass only `row` (R1 Major 3 fix).
    return templates.TemplateResponse(
        request, "partials/open_positions_row.html.j2", {"row": row_vm},
    )
```

- [ ] **Step 4: Run the test**

Run: `python -m pytest tests/web/test_routes/test_trades_route.py::test_get_trade_cancel_returns_normal_row -v`
Expected: PASS.

- [ ] **Step 5: Full suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 382 passed.

- [ ] **Step 6: Commit**

```bash
git add swing/web/routes/trades.py tests/web/test_routes/test_trades_route.py
git commit -m "feat(web): GET /trades/{id}/cancel returns normal row"
```

---

## Task 17: Strict-mode test at route level

**Files:**
- Test: `tests/web/test_routes/test_trades_route.py`

Spec success criterion: "Non-HTMX POST to any trade endpoint returns 403 with an X-Request-ID header."

- [ ] **Step 1: Failing test**

Append to `tests/web/test_routes/test_trades_route.py`:

```python
def test_post_trades_without_hx_request_403(test_cfg):
    """Strict OriginGuard: POST /trades/entry without HX-Request → 403 with X-Request-ID."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/trades/entry",
            data={"ticker": "AAPL", "entry_date": "2026-04-18",
                  "entry_price": "180.0", "shares": "1",
                  "initial_stop": "170.0", "rationale": "test"},
            # NO HX-Request header.
        )
    assert r.status_code == 403
    assert "strict" in r.text.lower()
    assert "x-request-id" in {h.lower() for h in r.headers.keys()}
```

- [ ] **Step 2: Verify it passes** (it should — Task 2 already wired strict=True)

Run: `python -m pytest tests/web/test_routes/test_trades_route.py::test_post_trades_without_hx_request_403 -v`
Expected: PASS.

- [ ] **Step 3: Full suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 383 passed.

- [ ] **Step 4: Commit**

```bash
git add tests/web/test_routes/test_trades_route.py
git commit -m "test(web): strict OriginGuard rejects non-HTMX POST /trades/entry with X-Request-ID"
```

---

## Task 18: Integration tests

**Files:**
- Create: `tests/web/test_trades_integration.py`

Spec §6.1 integration row (4 tests).

- [ ] **Step 1: Create the integration test file**

Create `tests/web/test_trades_integration.py`:

```python
"""End-to-end integration tests for Phase 3b trade actions."""
from __future__ import annotations

from datetime import datetime

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import Trade, WatchlistEntry
from swing.data.repos.trades import (
    get_trade, insert_trade_with_event, list_open_trades,
)
from swing.data.repos.watchlist import upsert_watchlist_entry
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot


def _seed_watchlist(cfg, ticker="AAPL"):
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            upsert_watchlist_entry(conn, WatchlistEntry(
                ticker=ticker, added_date="2026-04-10",
                last_qualified_date="2026-04-17", status="watch",
                qualification_count=1, not_qualified_streak=0,
                last_data_asof_date="2026-04-17",
                entry_target=181.0, initial_stop_target=170.0,
                last_close=180.0, last_pivot=181.0, last_stop=170.0,
                last_adr_pct=2.5, missing_criteria=None, notes=None,
            ))
    finally:
        conn.close()


def test_entry_end_to_end(seeded_db, monkeypatch):
    """Seed watchlist → GET form → POST entry → verify DB + VM state."""
    cfg, cfg_path = seeded_db
    _seed_watchlist(cfg)
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(ticker=t, price=180.95, asof=datetime.now(),
                             is_stale=False, source="live")
            for t in tickers
        })
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r_get = client.get("/trades/entry/form?ticker=AAPL",
                           headers={"HX-Request": "true"})
        assert r_get.status_code == 200
        r_post = client.post(
            "/trades/entry", headers={"HX-Request": "true"},
            data={"ticker": "AAPL", "entry_date": "2026-04-18",
                  "entry_price": "180.95", "shares": "5",
                  "initial_stop": "170.00", "rationale": "A+ entry e2e"},
        )
        assert r_post.status_code == 200

    # DB assertions: trade persisted, watchlist archived.
    conn = connect(cfg.paths.db_path)
    try:
        open_trades = list_open_trades(conn)
    finally:
        conn.close()
    assert any(t.ticker == "AAPL" for t in open_trades)


def test_soft_warn_loop_end_to_end(seeded_db, monkeypatch):
    """Seed 4 open trades → first submit at cap → confirm → second submit force=true → success."""
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            for i, t in enumerate(("MSFT", "NVDA", "GOOG", "META")):
                insert_trade_with_event(conn, Trade(
                    id=None, ticker=t, entry_date="2026-04-15",
                    entry_price=100.0, initial_shares=1, initial_stop=90.0,
                    current_stop=90.0, status="open",
                    watchlist_entry_target=None, watchlist_initial_stop=None,
                    notes=None,
                ), event_ts=f"2026-04-15T09:{30+i}:00")
    finally:
        conn.close()
    _seed_watchlist(cfg)
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            t: PriceSnapshot(ticker=t, price=180.95, asof=datetime.now(),
                             is_stale=False, source="live")
            for t in tickers
        })
    monkeypatch.setattr(PriceCache, "is_degraded", lambda self: False)

    app = create_app(cfg, cfg_path)
    form = {"ticker": "AAPL", "entry_date": "2026-04-18",
            "entry_price": "180.95", "shares": "1",
            "initial_stop": "170.00", "rationale": "5th"}
    with TestClient(app) as client:
        r1 = client.post("/trades/entry", headers={"HX-Request": "true"}, data=form)
        assert r1.status_code == 200
        assert "Soft cap reached" in r1.text
        form2 = dict(form); form2["force"] = "true"
        r2 = client.post("/trades/entry", headers={"HX-Request": "true"}, data=form2)
        assert r2.status_code == 200
        assert "open-position-" in r2.text


def test_stop_adjust_end_to_end(seeded_db, monkeypatch):
    """Adjust stop → verify DB current_stop updated."""
    cfg, cfg_path = seeded_db
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            insert_trade_with_event(conn, Trade(
                id=None, ticker="NVDA", entry_date="2026-04-15",
                entry_price=900.0, initial_shares=5, initial_stop=860.0,
                current_stop=860.0, status="open",
                watchlist_entry_target=None, watchlist_initial_stop=None,
                notes=None,
            ), event_ts="2026-04-15T09:30:00")
        trade = list_open_trades(conn)[0]
    finally:
        conn.close()
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "NVDA": PriceSnapshot(ticker="NVDA", price=932.0, asof=datetime.now(),
                                   is_stale=False, source="live"),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/trades/{trade.id}/stop", headers={"HX-Request": "true"},
            data={"new_stop": "912.00", "rationale": "trail"},
        )
    assert r.status_code == 200

    conn = connect(cfg.paths.db_path)
    try:
        updated = get_trade(conn, trade.id)
    finally:
        conn.close()
    assert updated.current_stop == 912.0


def test_cold_cache_entry_renders_last_close_fallback(seeded_db, monkeypatch):
    """R1 Major 4 resolution: seed candidates.close so _last_close has data,
    then make yf.download raise TimeoutError — the real _fallback_snapshot path
    fires, the row renders with is_stale=True / source='last_close', and the
    submit completes within a bounded window.

    This test exercises the spec's 'cold-cache renders stale row' contract
    rather than the previous version which only proved 'does not hang'."""
    from datetime import datetime
    import time
    import yfinance as yf
    from swing.data.db import connect
    from swing.data.models import WatchlistEntry
    from swing.data.repos.watchlist import upsert_watchlist_entry

    cfg, cfg_path = seeded_db
    _seed_watchlist(cfg)
    # Seed a candidates row with a known last_close so _last_close returns data.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count, rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 0, 0, 1, 0, 0, 'v1', 'deadbeef')""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20"),
            )
            eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                                           close, rs_method)
                   VALUES (?, 'AAPL', 'skip', 178.25, 'universe')""",
                (eval_id,),
            )
    finally:
        conn.close()

    # Force yf.download to raise, exercising the real _fetch_with_fallback code.
    def boom(*args, **kwargs):
        raise TimeoutError("simulated cold-cache timeout")
    monkeypatch.setattr(yf, "download", boom)
    # Ensure market_hours returns True so the live-fetch branch is taken.
    from swing.web.price_cache import PriceCache
    monkeypatch.setattr(PriceCache, "market_hours_now", lambda self: True)

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        t0 = time.monotonic()
        r = client.post(
            "/trades/entry", headers={"HX-Request": "true"},
            data={"ticker": "AAPL", "entry_date": "2026-04-18",
                  "entry_price": "180.0", "shares": "5",
                  "initial_stop": "170.0", "rationale": "cold"},
        )
        elapsed = time.monotonic() - t0
    assert r.status_code == 200
    # With seeded candidates row, _fallback_snapshot returns a stale snapshot —
    # the row should render with last_close price and stale marker.
    assert "stale" in r.text.lower() or "178.25" in r.text
    # Bounded by price_fetch_deadline_seconds (6s default) + rebuild overhead.
    assert elapsed < 10.0, f"cold-cache submit took {elapsed}s; expected <10s"
```

- [ ] **Step 2: Run the tests**

Run: `python -m pytest tests/web/test_trades_integration.py -v`
Expected: 4 PASS.

- [ ] **Step 3: Full suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 387 passed (383 + 4).

- [ ] **Step 4: Commit**

```bash
git add tests/web/test_trades_integration.py
git commit -m "test(web): 4 integration tests — entry, soft-warn loop, stop-adjust, cold-cache"
```

---

## Task 19: Full-suite acceptance sweep

**Files:** none (verification only)

Final regression gate before handing off to adversarial review.

- [ ] **Step 1: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: **387 passed, 8 deselected** — matching the spec's target test count.

- [ ] **Step 2: Verify Phase 2 tests still pass (base-install regression)**

Run: `python -m pytest tests/web/test_phase2_regression.py -v`
Expected: 4 PASS. Phase 2 isolation invariant held.

- [ ] **Step 3: Verify Phase 3a tests still green**

Run subset of Phase 3a tests that the 3b changes most likely disturbed:

```bash
python -m pytest tests/web/test_origin_guard.py tests/web/test_error_handling.py tests/web/test_view_models/test_dashboard.py tests/web/test_routes/test_dashboard_route.py tests/web/test_routes/test_watchlist_route.py tests/web/test_dashboard_integration.py -v
```

Expected: all pass.

- [ ] **Step 4: Type-check (optional but recommended)**

If `mypy` or `ruff` is configured:
```bash
ruff check swing/web/
```
Expected: no new warnings.

- [ ] **Step 5: Final commit**

Nothing to commit if all is clean. If any lint fixes are needed, apply and commit:

```bash
git commit -m "chore(web): Phase 3b acceptance sweep — 387 fast tests green"
```

Or skip this step entirely if nothing changed.

---

## Plan summary

- **19 tasks**, each ending in a clean commit.
- **~36 new tests** distributed across VM, route, origin-guard, error-handling, and integration files.
- **Target test count:** 351 (end of 3a) → 387 (end of 3b).
- **Files touched in Phase 2:** exactly one — `swing/data/repos/trades.py` gains a new additive `list_exits_for_trade(conn, trade_id)` helper (symmetric with `list_all_exits`). No Phase 2 schema/business-logic change.
- **Spec coverage:** every spec section §1–§9 has at least one task; §5.2 HTMX-aware handler is Task 3; §4.6 tolerant sizing-hint is Task 8; §4.3 two-call rebuild is Tasks 10–12; §5.1 state-drift recovery cases are Tasks 12 (case 1), 14 (case 2), 15 (case 3), 13 + 15 (case 4 via HTMX-aware 404 handler from Task 3); §9 locked decisions are all implemented.

**Ready for adversarial review.**
