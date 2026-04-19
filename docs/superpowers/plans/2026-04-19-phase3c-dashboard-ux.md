# Phase 3c Dashboard UX + Cleanup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the six Phase 3c items on top of the Phase 3b dashboard: force-clear button + CSV upload on `/pipeline`, 400-HTML for malformed query params, atomic stop-adjust guard (one scoped Phase 2 change), HX-Target-based path-aware handlers, `_templates` → `app.state.templates` promotion, and the retroactive HTMX 4xx-swap config fix.

**Architecture:** Routes (`swing/web/routes/*.py`) stay thin. `app.state.templates` becomes the single Jinja2Templates instance built at startup. Exception handlers (`_handle_http_exc`, `_handle_validation_error` in `app.py`) inspect `HX-Target` header for fragment-shape decisions and add a new non-HTMX GET branch that renders a full-page 400 via `PageErrorVM`. CSV upload gets a new `MaxBodySizeMiddleware` for pre-body-read size enforcement. One Phase 2 repo function (`update_stop_with_event`) gains an atomic `status = 'open'` guard. A new shared helper `swing/pipeline/staleness.py::is_stale_eligible` is extracted from the CLI for reuse by the web force-clear route.

**Tech Stack:** FastAPI + HTMX 2.x (3a/3b foundation), Jinja2, Starlette 1.0 `TemplateResponse(request, "name", {...})` signature, sqlite3, existing Phase 2 services. Python 3.14, Windows 11, gitbash. All commits go to `main` branch. Conventional commits (`feat(web):`, `fix(web):`, `refactor(...)`, etc.), NO Claude co-author footer, NO `--no-verify`.

**Baseline:** Phase 3b at commit `a988eb6`. Spec committed at `43b2cab`. 397 fast tests green. Target: **413+** fast tests after Phase 3c.

---

## File Structure

### Production code

```
swing/web/
├── app.py                            # MODIFIED: app.state.templates; MaxBodySizeMiddleware wiring;
│                                     #           HX-Target path-aware handlers; non-HTMX GET HTML branch
├── middleware/
│   └── body_size.py                  # NEW: MaxBodySizeMiddleware
├── view_models/
│   └── error.py                      # NEW: PageErrorVM dataclass
├── routes/
│   ├── dashboard.py                  # MODIFIED: remove _templates helper; use app.state.templates
│   ├── journal.py                    # MODIFIED: period Literal[...]; use app.state.templates
│   ├── pipeline.py                   # MODIFIED: csv-upload + force-clear trio; stale-run card
│   │                                 #           in GET /pipeline; use app.state.templates
│   ├── trades.py                     # MODIFIED: use app.state.templates at all sites
│   └── watchlist.py                  # MODIFIED: use app.state.templates at all sites
├── templates/
│   ├── base.html.j2                  # MODIFIED: htmx.config.responseHandling override
│   ├── page_error.html.j2            # NEW: full-page 400 for non-HTMX GET validation errors
│   ├── pipeline.html.j2              # MODIFIED: add #csv-upload-section and stale-run-card block
│   └── partials/
│       ├── csv_upload_form.html.j2          # NEW
│       ├── csv_upload_error.html.j2         # NEW: reasons banner + form preserved
│       ├── stale_run_card.html.j2           # NEW
│       ├── force_clear_confirm.html.j2      # NEW: 2-step confirm fragment
│       ├── force_clear_success.html.j2      # NEW: post-force-clear banner + Run-pipeline button
│       └── watchlist_row.html.j2            # MODIFIED: add id="watchlist-row-{{ w.ticker }}"

swing/pipeline/staleness.py           # NEW: is_stale_eligible(run, cfg) helper
swing/cli.py                          # MODIFIED: pipeline_force_clear_cmd uses is_stale_eligible
swing/data/repos/trades.py            # MODIFIED (Phase 2 carve-out): atomic status guard in update_stop_with_event
swing/config.py                       # MODIFIED: Web.csv_upload_max_bytes field
```

### Test files

```
tests/web/
├── test_app_smoke.py                         # MODIFIED: +1 test — app.state.templates present
├── test_base_template_htmx_config.py         # NEW: +2 tests — 4xx-swap override present + ordered after htmx.min.js
├── test_error_handling.py                    # MODIFIED: +3 tests — HX-Target row/non-row routing;
│                                             #                     non-HTMX GET → full page
├── test_origin_guard.py                      # (unchanged)
├── test_body_size_middleware.py              # NEW: +3 tests — Content-Length accept/reject/chunked passthrough
├── test_routes/
│   ├── test_journal_route.py                 # MODIFIED: +3 tests — Literal period validation paths
│   └── test_pipeline_route.py                # MODIFIED: +10 tests — CSV upload + force-clear trio + visibility
└── test_view_models/
    └── test_error_vm.py                      # NEW: +1 test — PageErrorVM shape

tests/pipeline/
└── test_staleness.py                         # NEW: +3 tests — is_stale_eligible: both-stale / one-stale / neither

tests/data/
└── test_repos_trades.py                      # MODIFIED: +2 tests — update_stop_with_event status guard
```

**Target test count:** 397 (end of 3b) + 28 = **~425 fast tests** (spec said ~413; the extra comes from granular coverage of the middleware + HTMX config + staleness helper).

---

## Task Ordering Rationale

1. **Foundation** (T1-T4): migrate `_templates` → `app.state.templates`, add HTMX 4xx-swap config override, switch handlers to HX-Target heuristic, add watchlist-row id. Each is low-risk and enables downstream work. Land T1 first so later tasks can simply write `request.app.state.templates` without remembering the old helper.
2. **Error page** (T5-T7): `PageErrorVM`, `page_error.html.j2`, `_handle_validation_error` non-HTMX GET branch, `/journal` `Literal[...]` — this unblocks the full-page 400 flow end-to-end.
3. **Phase 2 carve-out** (T8): `update_stop_with_event` atomic guard. Isolated, testable at the Phase 2 layer; doesn't depend on web changes.
4. **Staleness helper** (T9): extract `is_stale_eligible` to `swing/pipeline/staleness.py`; refactor CLI. Prerequisite for force-clear route.
5. **Force-clear chain** (T10-T13): stale-run card partial + GET route; confirm fragment + GET route; POST route with TOCTOU safety; wire into GET /pipeline.
6. **CSV upload** (T14-T17): config field + templates, MaxBodySizeMiddleware, POST route, pipeline-page wiring.
7. **Acceptance sweep** (T18): full fast suite, regression check.

Each task ends with a clean commit. No task leaves the codebase in a broken state.

---

## Task 1: Migrate `_templates` helper → `app.state.templates`

**Files:**
- Modify: `swing/web/app.py:83`
- Modify: `swing/web/routes/dashboard.py` (remove helper)
- Modify: `swing/web/routes/journal.py`
- Modify: `swing/web/routes/pipeline.py`
- Modify: `swing/web/routes/trades.py`
- Modify: `swing/web/routes/watchlist.py`
- Test: `tests/web/test_app_smoke.py`

Spec §3.3, decision #6. Build the Jinja2Templates instance once at startup; remove the cross-module private `_templates(request)` helper.

- [ ] **Step 1: Write failing test**

Append to `tests/web/test_app_smoke.py`:

```python
def test_app_state_templates_is_jinja2templates(test_cfg):
    """Spec §3.3 / decision #6: Jinja2Templates instance lives on app.state.templates,
    built once at startup. Routes must read it via request.app.state.templates."""
    from fastapi.templating import Jinja2Templates
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    assert isinstance(app.state.templates, Jinja2Templates)
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/web/test_app_smoke.py::test_app_state_templates_is_jinja2templates -v`
Expected: FAIL — `app.state.templates` does not exist yet.

- [ ] **Step 3: Add `app.state.templates` in `create_app`**

In `swing/web/app.py`, find the existing line `app.state.templates_dir = _templates_dir()` (around line 83). Add the following immediately after:

```python
    app.state.templates_dir = _templates_dir()
    app.state.templates = Jinja2Templates(directory=str(app.state.templates_dir))
```

`Jinja2Templates` is already imported.

- [ ] **Step 4: Run the new test**

Run: `python -m pytest tests/web/test_app_smoke.py::test_app_state_templates_is_jinja2templates -v`
Expected: PASS.

- [ ] **Step 5: Remove the `_templates` helper from dashboard.py**

In `swing/web/routes/dashboard.py`, delete the helper function (lines 13-20) and the `Jinja2Templates` import (line 6). Update the `index` handler to use `request.app.state.templates`:

```python
"""GET / — the main dashboard route."""
from __future__ import annotations

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from swing.web.view_models.dashboard import build_dashboard

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def index(request: Request):
    cfg = request.app.state.cfg
    cache = request.app.state.price_cache
    executor = request.app.state.price_fetch_executor
    vm = build_dashboard(cfg=cfg, cache=cache, executor=executor)
    return request.app.state.templates.TemplateResponse(
        request, "dashboard.html.j2", {"vm": vm},
    )
```

- [ ] **Step 6: Update journal.py**

In `swing/web/routes/journal.py`, replace the `_templates` import and usage:

```python
"""Journal route."""
from __future__ import annotations

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from swing.web.view_models.journal import build_journal

router = APIRouter()


@router.get("/journal", response_class=HTMLResponse)
def journal_page(request: Request, period: str = Query("month")):
    cfg = request.app.state.cfg
    vm = build_journal(cfg=cfg, period=period)
    return request.app.state.templates.TemplateResponse(
        request, "journal.html.j2", {"vm": vm},
    )
```

(The `Literal[...]` annotation lands in Task 7 — leave `period: str` for now.)

- [ ] **Step 7: Update pipeline.py**

In `swing/web/routes/pipeline.py`, remove the `from swing.web.routes.dashboard import _templates` import. Every call site `templates = _templates(request)` becomes `templates = request.app.state.templates`. There are 4 call sites (in `pipeline_page`, `pipeline_run`, `pipeline_status`, `prices_refresh`). Use your editor's find-replace in this file only: `_templates(request)` → `request.app.state.templates`.

- [ ] **Step 8: Update trades.py**

In `swing/web/routes/trades.py`, remove the `from swing.web.routes.dashboard import _templates` import. All 8 call sites `templates = _templates(request)` → `templates = request.app.state.templates`.

- [ ] **Step 9: Update watchlist.py**

In `swing/web/routes/watchlist.py`, remove the `_templates` import; replace both call sites with `request.app.state.templates`.

- [ ] **Step 10: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 398 passed (397 + 1 new). No regressions.

- [ ] **Step 11: Commit**

```bash
git add swing/web/app.py swing/web/routes/ tests/web/test_app_smoke.py
git commit -m "refactor(web): _templates helper → app.state.templates"
```

---

## Task 2: HTMX 4xx-swap config override in `base.html.j2`

**Files:**
- Modify: `swing/web/templates/base.html.j2:8`
- Test: `tests/web/test_base_template_htmx_config.py` (NEW)

Spec §3.2a. HTMX 2.x defaults to not swapping 4xx responses; Phase 3b+ fragments need an explicit override. Retroactive fix — adds coverage that Phase 3b silently missed.

- [ ] **Step 1: Write failing tests**

Create `tests/web/test_base_template_htmx_config.py`:

```python
"""Spec §3.2a: base.html.j2 must override htmx.config.responseHandling so that
4xx responses swap into the DOM. Phase 3b's trade_form_error.html.j2 fragments
and Phase 3c's new fragments all depend on this."""
from __future__ import annotations

from fastapi.testclient import TestClient

from swing.web.app import create_app


def test_dashboard_page_contains_htmx_config_override(test_cfg, seeded_db):
    """Ordered-source check: htmx.min.js comes first, then the config override
    containing both '[45]..' and 'swap: true' tokens."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    assert r.status_code == 200
    body = r.text
    htmx_pos = body.find("/static/htmx.min.js")
    cfg_pos = body.find("htmx.config.responseHandling")
    assert htmx_pos > 0, "htmx.min.js script tag missing"
    assert cfg_pos > htmx_pos, (
        "htmx.config.responseHandling override must appear AFTER htmx.min.js "
        "in source order so the config can be applied"
    )
    assert '"[45].."' in body, "override must include 4xx code selector"
    assert "swap: true" in body, "override must enable swapping"


def test_override_changes_4xx_entry_from_default(test_cfg, seeded_db):
    """The override must include the 4xx entry with swap:true (default is swap:false)."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/")
    # Default HTMX config has `{code: "[45]..", swap: false, error: true}`.
    # Ours must set swap: true on the 4xx entry.
    body = r.text
    # Allow whitespace variations
    import re
    m = re.search(
        r'\{[^{}]*"?\[45\]\.\."?[^{}]*swap:\s*true[^{}]*\}',
        body, re.DOTALL,
    )
    assert m is not None, (
        "4xx entry with swap: true not found in override — fragment rendering "
        "will not work in browser"
    )
```

- [ ] **Step 2: Verify they fail**

Run: `python -m pytest tests/web/test_base_template_htmx_config.py -v`
Expected: both FAIL — `htmx.config.responseHandling` is absent.

- [ ] **Step 3: Add the override in base.html.j2**

Open `swing/web/templates/base.html.j2` and replace the `<script src="/static/htmx.min.js"></script>` line with:

```html
  <script src="/static/htmx.min.js"></script>
  <script>
    // Spec 3c §3.2a: HTMX 2.x defaults 4xx responses to swap:false+error:true.
    // Phase 3b+ fragments (trade_form_error, http_error_fragment, csv_upload_error,
    // force_clear_*, stale_run_card) return 400/404/409/413 and MUST swap into
    // the target or the UI silently drops them. Override enables 4xx swapping
    // while keeping the error event for client-side logging.
    htmx.config.responseHandling = [
      {code: "204", swap: false},
      {code: "[12]..", swap: true},
      {code: "[45]..", swap: true, error: true},
    ];
  </script>
```

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/web/test_base_template_htmx_config.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 400 passed (398 + 2 new).

- [ ] **Step 6: Commit**

```bash
git add swing/web/templates/base.html.j2 tests/web/test_base_template_htmx_config.py
git commit -m "fix(web): htmx.config.responseHandling override — enable 4xx-swap (retroactive 3b fix)"
```

---

## Task 3: `watchlist_row.html.j2` id addition

**Files:**
- Modify: `swing/web/templates/partials/watchlist_row.html.j2`
- Test: `tests/web/test_routes/test_watchlist_route.py` (amended)

Spec §3.1 / decision #5. Row needs `id="watchlist-row-{{ w.ticker }}"` so HTMX sends `HX-Target` when the Enter button fires.

- [ ] **Step 1: Read the current template and find the `<tr>` opener**

Run: `cat "swing/web/templates/partials/watchlist_row.html.j2"`

Note the first line — it will be `<tr>` (no id) or similar. The variable name is `w` (single watchlist entry per row).

- [ ] **Step 2: Write failing test**

Append to `tests/web/test_routes/test_watchlist_route.py`:

```python
def test_watchlist_row_has_ticker_id_for_hx_target(seeded_db, seed_watchlist):
    """Spec §3.1: watchlist row `<tr>` gains id='watchlist-row-<ticker>' so HTMX
    populates HX-Target when the Enter button fires, letting the row-prefix
    whitelist engage for error responses."""
    seed_watchlist("AAPL", entry_target=181.0)
    cfg, cfg_path = seeded_db
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/watchlist")
    assert r.status_code == 200
    assert 'id="watchlist-row-AAPL"' in r.text
```

(`seed_watchlist` is the existing conftest fixture; use the existing AAPL-seeding pattern from adjacent tests. If a simpler seeding path exists, use that.)

- [ ] **Step 3: Verify it fails**

Run: `python -m pytest tests/web/test_routes/test_watchlist_route.py::test_watchlist_row_has_ticker_id_for_hx_target -v`
Expected: FAIL — no `id="watchlist-row-..."` in rendered output.

- [ ] **Step 4: Modify the row template**

In `swing/web/templates/partials/watchlist_row.html.j2`, change the opening `<tr>` (or `<tr ...>`) to:

```jinja
<tr id="watchlist-row-{{ w.ticker }}">
```

Preserve any existing attributes on the `<tr>` if there were any (e.g., class attributes).

- [ ] **Step 5: Run the new test**

Run: `python -m pytest tests/web/test_routes/test_watchlist_route.py::test_watchlist_row_has_ticker_id_for_hx_target -v`
Expected: PASS.

- [ ] **Step 6: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 401 passed. No regressions.

- [ ] **Step 7: Commit**

```bash
git add swing/web/templates/partials/watchlist_row.html.j2 tests/web/test_routes/test_watchlist_route.py
git commit -m "feat(web): watchlist row gains id='watchlist-row-<ticker>' for HX-Target matching"
```

---

## Task 4: HX-Target row-prefix heuristic in exception handlers

**Files:**
- Modify: `swing/web/app.py` (both handlers)
- Test: `tests/web/test_error_handling.py`

Spec §3.3 / decision #5. Replace URL-prefix heuristic with `HX-Target` header inspection. Also migrates handlers from per-call `Jinja2Templates(...)` to `app.state.templates` (picks up Task 1's work).

- [ ] **Step 1: Write failing tests**

Append to `tests/web/test_error_handling.py`:

```python
def test_htmx_handler_uses_hx_target_for_row_prefix(test_cfg, seeded_db):
    """Spec §3.3: HX-Target header determines fragment shape, not URL path.
    A /trades/* endpoint with a non-row HX-Target (e.g. sizing-hint) MUST get
    the neutral <div> fragment, not a <tr>."""
    from fastapi import HTTPException
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    @app.get("/trades/_non_row_probe")
    def _probe():
        raise HTTPException(status_code=404, detail="probe missing")

    with TestClient(app) as client:
        r = client.get(
            "/trades/_non_row_probe",
            headers={"HX-Request": "true", "HX-Target": "sizing-hint"},
        )
    assert r.status_code == 404
    # <div> shape from http_error_fragment.html.j2, NOT <tr>.
    assert "<div" in r.text.lower()
    assert "<tr" not in r.text.lower()
    assert "probe missing" in r.text


def test_htmx_handler_renders_tr_for_row_target(test_cfg, seeded_db):
    """Spec §3.3: row-prefix HX-Target → <tr> fragment from trade_form_error.html.j2."""
    from fastapi import HTTPException
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    @app.post("/trades/_row_probe")
    def _probe():
        raise HTTPException(status_code=404, detail="trade #99 not found")

    with TestClient(app) as client:
        r = client.post(
            "/trades/_row_probe",
            headers={"HX-Request": "true", "HX-Target": "open-position-42"},
        )
    assert r.status_code == 404
    assert "<tr" in r.text.lower()
    assert "trade #99 not found" in r.text


def test_htmx_handler_uses_app_state_templates(test_cfg, seeded_db):
    """Spec §3.3: handlers use request.app.state.templates (not a per-call
    Jinja2Templates instance). We can't assert this directly from outside,
    but the smoke test here confirms the handler still renders correctly
    after the migration."""
    from fastapi import HTTPException
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    @app.get("/_smoke_404")
    def _probe():
        raise HTTPException(status_code=404, detail="smoke")

    with TestClient(app) as client:
        r = client.get("/_smoke_404", headers={"HX-Request": "true"})
    assert r.status_code == 404
    assert "smoke" in r.text
```

- [ ] **Step 2: Verify they fail**

Run: `python -m pytest tests/web/test_error_handling.py -k "hx_target or app_state_templates" -v`
Expected: the first two tests fail (URL-prefix heuristic matches `/trades/*` and renders `<tr>` in both cases). The third may pass since it doesn't depend on HX-Target.

- [ ] **Step 3: Add the helper + migrate handlers in `app.py`**

At module level in `swing/web/app.py` (after imports), add:

```python
_ROW_TARGET_PREFIXES = (
    "open-position-",     # open-positions row
    "entry-form-",        # entry form (replaces watchlist row)
    "exit-form-",         # exit form (replaces open-position row)
    "stop-form-",         # stop-adjust form (replaces open-position row)
    "watchlist-row-",     # watchlist row (Enter-button target; id added in Phase 3c)
)


def _is_row_swap_target(request: Request) -> bool:
    return request.headers.get("HX-Target", "").startswith(_ROW_TARGET_PREFIXES)
```

Replace the existing `_handle_http_exc` (~lines 99-116) with:

```python
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
```

Replace the existing `_handle_validation_error` (~lines 118-144) with:

```python
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
        # Task 5 inserts the non-HTMX GET HTML branch before this fallthrough.
        return await request_validation_exception_handler(request, exc)
```

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/web/test_error_handling.py -k "hx_target or app_state_templates" -v`
Expected: 3 PASS.

- [ ] **Step 5: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 404 passed (401 + 3 new). No regressions — the existing HTMX tests still pass because both the old URL-prefix rule AND the new HX-Target rule agree on the Phase 3b trade form paths.

- [ ] **Step 6: Commit**

```bash
git add swing/web/app.py tests/web/test_error_handling.py
git commit -m "refactor(web): HTMX handlers use HX-Target row-prefix heuristic; migrate to app.state.templates"
```

---

## Task 5: `PageErrorVM` + `page_error.html.j2` template

**Files:**
- Create: `swing/web/view_models/error.py`
- Create: `swing/web/templates/page_error.html.j2`
- Test: `tests/web/test_view_models/test_error_vm.py` (NEW)

Spec §3.2. Base-layout-compatible VM so the error page renders without `UndefinedError` on `vm.session_date` / `vm.stale_banner` / `vm.price_source_degraded`.

- [ ] **Step 1: Write failing VM test**

Create `tests/web/test_view_models/test_error_vm.py`:

```python
"""PageErrorVM — base-layout-compatible context for page_error.html.j2."""
from __future__ import annotations


def test_page_error_vm_has_base_layout_fields():
    """Spec §3.2: base.html.j2 dereferences vm.session_date, vm.stale_banner,
    vm.price_source_degraded. PageErrorVM must provide all three plus
    status_code + detail."""
    from swing.web.view_models.error import PageErrorVM

    vm = PageErrorVM(
        session_date="2026-04-19",
        status_code=400,
        detail="Invalid input in query.period: value is not a valid member of enum",
    )
    assert vm.session_date == "2026-04-19"
    assert vm.stale_banner is None
    assert vm.price_source_degraded is False
    assert vm.status_code == 400
    assert "Invalid input" in vm.detail


def test_page_error_vm_defaults():
    """Defaults let a last-resort handler build the VM without every field."""
    from swing.web.view_models.error import PageErrorVM
    vm = PageErrorVM(session_date="n/a")
    assert vm.status_code == 400
    assert vm.detail == "Invalid request"
    assert vm.stale_banner is None
    assert vm.price_source_degraded is False
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/web/test_view_models/test_error_vm.py -v`
Expected: ImportError — module `swing.web.view_models.error` does not exist.

- [ ] **Step 3: Create `swing/web/view_models/error.py`**

```python
"""View-model for page_error.html.j2 — full-page HTML error responses."""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class PageErrorVM:
    """Context for page_error.html.j2. The base layout (base.html.j2)
    dereferences vm.session_date, vm.stale_banner, and vm.price_source_degraded
    on every render; this VM supplies base-layout-compatible defaults so an
    error page doesn't turn into a 500 via UndefinedError. Spec §3.2."""
    session_date: str                     # today's action_session_for_run() value, or "n/a"
    stale_banner: None = None             # never stale on an error page
    price_source_degraded: bool = False   # degraded-cache banner not shown
    status_code: int = 400
    detail: str = "Invalid request"
```

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/web/test_view_models/test_error_vm.py -v`
Expected: 2 PASS.

- [ ] **Step 5: Create the template**

Create `swing/web/templates/page_error.html.j2`:

```jinja
{#- swing/web/templates/page_error.html.j2
    Full-page 400/404 HTML error rendered for non-HTMX GET validation errors
    (e.g. address-bar typo `/journal?period=fortnight`). Expects PageErrorVM.
    Spec §3.2. -#}
{% extends "base.html.j2" %}
{% block content %}
  <section class="page-error">
    <h1>{{ vm.status_code }} — Invalid Request</h1>
    <div class="banner banner-degraded" role="alert">
      {{ vm.detail }}
    </div>
    <p>
      <a href="/">Return to dashboard</a>
    </p>
  </section>
{% endblock %}
```

- [ ] **Step 6: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 406 passed (404 + 2 new).

- [ ] **Step 7: Commit**

```bash
git add swing/web/view_models/error.py swing/web/templates/page_error.html.j2 tests/web/test_view_models/test_error_vm.py
git commit -m "feat(web): PageErrorVM + page_error.html.j2 template"
```

---

## Task 6: Non-HTMX GET branch in `_handle_validation_error`

**Files:**
- Modify: `swing/web/app.py::_handle_validation_error`
- Test: `tests/web/test_error_handling.py`

Spec §3.3 / §4.3. Adds the full-page HTML branch with `Accept: text/html` content negotiation.

- [ ] **Step 1: Write failing tests**

Append to `tests/web/test_error_handling.py`:

```python
def test_non_htmx_get_with_bad_query_renders_full_page(test_cfg, seeded_db):
    """Spec §3.3 / §4.3: address-bar typo on /journal?period=<bad> with
    Accept: text/html → full-page page_error.html.j2, not 422 JSON."""
    from typing import Literal
    from fastapi import Query as _Query
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    # Register a synthetic GET endpoint that uses a Literal param (similar to
    # /journal's eventual shape) so RequestValidationError fires on invalid values.
    @app.get("/_typed_query_probe")
    def _probe(mode: Literal["a", "b"] = _Query("a")):
        return {"mode": mode}

    with TestClient(app) as client:
        r = client.get(
            "/_typed_query_probe?mode=nope",
            headers={"Accept": "text/html,application/xhtml+xml,*/*"},
        )
    assert r.status_code == 400
    assert "text/html" in r.headers.get("content-type", "")
    # Full-page error — contains base layout chrome (nav) + the detail.
    assert "<html" in r.text.lower()
    assert "Return to dashboard" in r.text
    assert "mode" in r.text  # field name appears in detail


def test_non_htmx_get_json_accept_falls_through_to_422(test_cfg, seeded_db):
    """Spec §3.3 precedence rule #3: GET with Accept: application/json (no
    text/html) → FastAPI default 422 JSON, not the HTML page."""
    from typing import Literal
    from fastapi import Query as _Query
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)

    @app.get("/_typed_query_probe2")
    def _probe(mode: Literal["a", "b"] = _Query("a")):
        return {"mode": mode}

    with TestClient(app) as client:
        r = client.get(
            "/_typed_query_probe2?mode=nope",
            headers={"Accept": "application/json"},
        )
    assert r.status_code == 422
    assert "application/json" in r.headers.get("content-type", "")
    body = r.json()
    assert "detail" in body
```

- [ ] **Step 2: Verify they fail**

Run: `python -m pytest tests/web/test_error_handling.py -k "non_htmx_get" -v`
Expected: first test fails with 422 JSON (current fallthrough), second test already passes (no HTML rendering attempted).

- [ ] **Step 3: Modify `_handle_validation_error` to add the HTML branch**

In `swing/web/app.py::_handle_validation_error`, insert the new branch **before** the final `return await request_validation_exception_handler(...)` line:

```python
    @app.exception_handler(RequestValidationError)
    async def _handle_validation_error(request: Request, exc: RequestValidationError):
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
```

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/web/test_error_handling.py -k "non_htmx_get" -v`
Expected: 2 PASS.

- [ ] **Step 5: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 408 passed (406 + 2). No regressions.

- [ ] **Step 6: Commit**

```bash
git add swing/web/app.py tests/web/test_error_handling.py
git commit -m "feat(web): _handle_validation_error renders full-page 400 for non-HTMX GET + text/html"
```

---

## Task 7: `/journal?period=<bad>` → 400 via `Literal[...]`

**Files:**
- Modify: `swing/web/routes/journal.py`
- Test: `tests/web/test_routes/test_journal_route.py`

Spec §3.4 / decision #3. Replace `period: str` with `period: Literal[...]` so FastAPI auto-generates `RequestValidationError` on invalid values.

- [ ] **Step 1: Write failing tests**

Append to `tests/web/test_routes/test_journal_route.py`:

```python
def test_journal_bad_period_htmx_returns_div_fragment(test_cfg, seeded_db):
    """HTMX GET /journal?period=<bad> → 400 <div> fragment (HX-Target absent)."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            "/journal?period=fortnight",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 400
    assert "<div" in r.text.lower()
    assert "period" in r.text.lower()
    assert "<tr" not in r.text.lower()


def test_journal_bad_period_nonhtmx_html_renders_page(test_cfg, seeded_db):
    """Non-HTMX GET with Accept: text/html → full-page 400, not 500."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            "/journal?period=fortnight",
            headers={"Accept": "text/html,application/xhtml+xml,*/*"},
        )
    assert r.status_code == 400
    assert "<html" in r.text.lower()
    assert "period" in r.text.lower()


def test_journal_happy_path_unchanged(test_cfg, seeded_db):
    """Valid period still renders the journal page."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/journal?period=month")
    assert r.status_code == 200
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/web/test_routes/test_journal_route.py -k "bad_period" -v`
Expected: both bad-period tests FAIL — current route returns 500 (ValueError propagates to `_handle_any`).

- [ ] **Step 3: Add `Literal` type annotation**

The existing `_ALLOWED_PERIODS` set in `swing/web/view_models/journal.py:18` is `frozenset({"week", "month", "quarter", "ytd", "all"})` — the `Literal[...]` values MUST match exactly. The existing `tests/web/test_routes/test_journal_route.py:17` already exercises `?period=week`, so missing `week` or adding a bogus `year` would regress a passing test.

Replace the route in `swing/web/routes/journal.py`:

```python
"""Journal route."""
from __future__ import annotations

from typing import Literal

from fastapi import APIRouter, Query, Request
from fastapi.responses import HTMLResponse

from swing.web.view_models.journal import build_journal

router = APIRouter()


@router.get("/journal", response_class=HTMLResponse)
def journal_page(
    request: Request,
    period: Literal["week", "month", "quarter", "ytd", "all"] = Query("month"),
):
    cfg = request.app.state.cfg
    vm = build_journal(cfg=cfg, period=period)
    return request.app.state.templates.TemplateResponse(
        request, "journal.html.j2", {"vm": vm},
    )
```

(Verify `_ALLOWED_PERIODS` is unchanged before editing: `grep -n "_ALLOWED_PERIODS" swing/web/view_models/journal.py`.)

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/web/test_routes/test_journal_route.py -k "bad_period or happy_path" -v`
Expected: 3 PASS.

- [ ] **Step 5: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 411 passed (408 + 3). No regressions.

- [ ] **Step 6: Commit**

```bash
git add swing/web/routes/journal.py tests/web/test_routes/test_journal_route.py
git commit -m "feat(web): /journal period param uses Literal[...] — 400 instead of 500 on bad values"
```

---

## Task 8: Atomic `update_stop_with_event` status guard (Phase 2 carve-out)

**Files:**
- Modify: `swing/data/repos/trades.py::update_stop_with_event`
- Test: `tests/data/test_repos_trades.py`

Spec §4.4 / decision #4. The one scoped Phase 2 change. Closes the close-then-stop-adjust race at the repo layer.

- [ ] **Step 1: Write failing tests**

First, read the existing test helpers in `tests/data/test_repos_trades.py` — there is a `_trade()` factory (~line 33) and an `ensure_schema`+`connect` pattern that all existing tests in this file use. `insert_trade_with_event(conn, trade: Trade, *, event_ts, ...)` takes a `Trade` dataclass, NOT kwargs. Follow that exact pattern for the new tests below.

Append to `tests/data/test_repos_trades.py`:

```python
def test_update_stop_with_event_rejects_closed_trade():
    """Spec §4.4: closed trade → ValueError, no row mutation, no event insert."""
    from swing.data.db import connect, ensure_schema
    from swing.data.repos.trades import (
        insert_trade_with_event, update_stop_with_event,
    )
    import pytest as _pt
    import tempfile
    import pathlib

    with tempfile.TemporaryDirectory() as tmp:
        db_path = pathlib.Path(tmp) / "test.db"
        ensure_schema(db_path).close()
        conn = connect(db_path)
        try:
            with conn:
                tid = insert_trade_with_event(
                    conn, _trade(), event_ts="2026-04-15T09:30:00",
                )
                # Mark the trade closed (simulates post-exit state transition).
                conn.execute(
                    "UPDATE trades SET status='closed' WHERE id = ?", (tid,),
                )

            # Attempt stop-adjust on the closed trade.
            with _pt.raises(ValueError) as excinfo:
                with conn:
                    update_stop_with_event(
                        conn, trade_id=tid, new_stop=175.0,
                        event_ts="2026-04-16T10:00:00",
                        rationale="attempt after close",
                    )
            # Accept either wording — the closed-trade path raises with one;
            # missing-trade path raises with another.
            msg = str(excinfo.value).lower()
            assert "not open" in msg or "does not exist" in msg

            # Confirm no stop_adjust event was inserted.
            rows = conn.execute(
                "SELECT COUNT(*) FROM trade_events "
                "WHERE event_type='stop_adjust' AND trade_id = ?",
                (tid,),
            ).fetchone()
            assert rows[0] == 0

            # current_stop must not have mutated.
            row = conn.execute(
                "SELECT current_stop FROM trades WHERE id = ?", (tid,),
            ).fetchone()
            assert row[0] == _trade().initial_stop  # whatever initial_stop _trade() sets
        finally:
            conn.close()


def test_update_stop_with_event_rejects_missing_trade():
    """Spec §4.4: nonexistent trade_id → ValueError, no event insert."""
    from swing.data.db import connect, ensure_schema
    from swing.data.repos.trades import update_stop_with_event
    import pytest as _pt
    import tempfile
    import pathlib

    with tempfile.TemporaryDirectory() as tmp:
        db_path = pathlib.Path(tmp) / "test.db"
        ensure_schema(db_path).close()
        conn = connect(db_path)
        try:
            with _pt.raises(ValueError) as excinfo:
                with conn:
                    update_stop_with_event(
                        conn, trade_id=99999, new_stop=175.0,
                        event_ts="2026-04-16T10:00:00",
                        rationale="missing",
                    )
            msg = str(excinfo.value).lower()
            assert "not found" in msg or "does not exist" in msg

            rows = conn.execute(
                "SELECT COUNT(*) FROM trade_events WHERE trade_id=99999"
            ).fetchone()
            assert rows[0] == 0
        finally:
            conn.close()
```

**Critical:** the `_trade()` factory is defined at the top of the existing `tests/data/test_repos_trades.py` — it returns a valid `Trade` dataclass with a sensible initial_stop (likely 170.0 or similar). Read that factory before copying this test in, and adjust the final `assert row[0] == _trade().initial_stop` comparison to reference whatever the factory actually sets (or use a literal value that matches).

- [ ] **Step 2: Verify the closed-trade test fails**

Run: `python -m pytest tests/data/test_repos_trades.py::test_update_stop_with_event_rejects_closed_trade -v`
Expected: FAIL — current code silently updates the closed trade.

- [ ] **Step 3: Modify `update_stop_with_event`**

In `swing/data/repos/trades.py`, find `def update_stop_with_event` (around line 108) and replace its body with:

```python
def update_stop_with_event(
    conn: sqlite3.Connection, *, trade_id: int, new_stop: float,
    event_ts: str, rationale: str | None = None,
) -> None:
    """Update trades.current_stop + write 'stop_adjust' event in same txn.
    Phase 3c §4.4: atomic status='open' guard closes the close-then-stop race.
    Missing or closed trade → ValueError with no event insert."""
    trade = get_trade(conn, trade_id)
    if trade is None:
        raise ValueError(f"trade {trade_id} not found")
    if trade.current_stop == new_stop:
        return  # no-op
    payload = {"old_stop": trade.current_stop, "new_stop": new_stop}
    cur = conn.execute(
        "UPDATE trades SET current_stop = ? WHERE id = ? AND status = 'open'",
        (new_stop, trade_id),
    )
    if cur.rowcount == 0:
        raise ValueError(f"trade {trade_id} is not open or does not exist")
    conn.execute(
        """
        INSERT INTO trade_events (trade_id, ts, event_type, payload_json, rationale)
        VALUES (?, ?, 'stop_adjust', ?, ?)
        """,
        (trade_id, event_ts, json.dumps(payload, sort_keys=True), rationale),
    )
```

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/data/test_repos_trades.py -k "update_stop_with_event" -v`
Expected: both new tests PASS. Pre-existing `update_stop_with_event` tests also pass because the happy path (status='open') still matches the guard.

- [ ] **Step 5: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 413 passed (411 + 2). No regressions.

- [ ] **Step 6: Commit**

```bash
git add swing/data/repos/trades.py tests/data/test_repos_trades.py
git commit -m "fix(data): update_stop_with_event atomic status='open' guard (Phase 3c carve-out)"
```

---

## Task 9: Extract `is_stale_eligible` helper + CLI refactor

**Files:**
- Create: `swing/pipeline/staleness.py`
- Modify: `swing/cli.py::pipeline_force_clear_cmd`
- Test: `tests/pipeline/test_staleness.py` (NEW)

Spec §2.3. Centralize the two-signal staleness check; both the CLI and the new web force-clear route consume it.

- [ ] **Step 1: Write failing tests**

Create `tests/pipeline/test_staleness.py`:

```python
"""is_stale_eligible — two-signal (heartbeat + step-progress) staleness check.
Spec §5.6, §3c/§2.3."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta


def _mk_run(
    *, hb_age_seconds: float | None = None,
    step_age_seconds: float | None = None,
    state: str = "running",
):
    from swing.data.models import PipelineRun
    now = datetime.now()
    hb = (now - timedelta(seconds=hb_age_seconds)).isoformat(timespec="seconds") if hb_age_seconds is not None else None
    step = (now - timedelta(seconds=step_age_seconds)).isoformat(timespec="seconds") if step_age_seconds is not None else None
    return PipelineRun(
        id=1, started_ts=now.isoformat(timespec="seconds"), finished_ts=None,
        trigger="manual", data_asof_date="2026-04-19",
        action_session_date="2026-04-19", state=state,
        lease_token="t-x", lease_heartbeat_ts=hb, last_step_progress_ts=step,
        current_step="evaluate", weather_status=None, evaluation_status=None,
        watchlist_status=None, recommendations_status=None, charts_status=None,
        export_status=None, rs_universe_version=None, rs_universe_hash=None,
        finviz_csv_path=None, error_message=None, warnings_json=None,
    )


def _mk_cfg(lease_threshold=300, step_threshold=900):
    """Minimal cfg stub — only the two pipeline thresholds are read."""
    from types import SimpleNamespace
    return SimpleNamespace(
        pipeline=SimpleNamespace(
            stale_lease_threshold_seconds=lease_threshold,
            stale_step_threshold_seconds=step_threshold,
        ),
    )


def test_is_stale_eligible_both_signals_stale():
    """Spec §5.6: only stale when BOTH heartbeat AND step-progress exceed thresholds."""
    from swing.pipeline.staleness import is_stale_eligible
    run = _mk_run(hb_age_seconds=600, step_age_seconds=1200)
    cfg = _mk_cfg(lease_threshold=300, step_threshold=900)
    assert is_stale_eligible(run, cfg) is True


def test_is_stale_eligible_only_heartbeat_stale_returns_false():
    """Heartbeat stale but step-progress fresh → NOT stale (long-running step)."""
    from swing.pipeline.staleness import is_stale_eligible
    run = _mk_run(hb_age_seconds=600, step_age_seconds=30)
    cfg = _mk_cfg()
    assert is_stale_eligible(run, cfg) is False


def test_is_stale_eligible_only_step_stale_returns_false():
    """Step-progress stale but heartbeat fresh → NOT stale (wedged UI-side only)."""
    from swing.pipeline.staleness import is_stale_eligible
    run = _mk_run(hb_age_seconds=30, step_age_seconds=1200)
    cfg = _mk_cfg()
    assert is_stale_eligible(run, cfg) is False


def test_is_stale_eligible_non_running_state_returns_false():
    """Only state='running' is eligible — 'force_cleared', 'complete', etc. are not."""
    from swing.pipeline.staleness import is_stale_eligible
    run = _mk_run(hb_age_seconds=600, step_age_seconds=1200, state="force_cleared")
    cfg = _mk_cfg()
    assert is_stale_eligible(run, cfg) is False


def test_is_stale_eligible_missing_timestamps_treats_as_stale():
    """Either timestamp missing → treated as infinitely stale."""
    from swing.pipeline.staleness import is_stale_eligible
    run = _mk_run(hb_age_seconds=None, step_age_seconds=None)
    cfg = _mk_cfg()
    assert is_stale_eligible(run, cfg) is True
```

- [ ] **Step 2: Verify they fail**

Run: `python -m pytest tests/pipeline/test_staleness.py -v`
Expected: ImportError — module `swing.pipeline.staleness` does not exist.

- [ ] **Step 3: Create `swing/pipeline/staleness.py`**

```python
"""Pipeline-run staleness detection — both-signal check per spec §5.6.

A run is force-clear-eligible only when BOTH:
  - heartbeat age > stale_lease_threshold_seconds
  - step-progress age > stale_step_threshold_seconds
AND state == 'running'.

Shared by CLI (`swing pipeline force-clear`) and the web dashboard's
force-clear route (Phase 3c). Spec §3c/§2.3 notes this module is NEW and
replaces the inline check that lived in cli.py::pipeline_force_clear_cmd.
"""
from __future__ import annotations

from datetime import datetime

from swing.config import Config
from swing.data.models import PipelineRun


def is_stale_eligible(run: PipelineRun, cfg: Config) -> bool:
    """Return True iff the run is force-clear-eligible under spec §5.6.

    - Requires state == 'running'.
    - Requires BOTH heartbeat age AND step-progress age > their thresholds.
    - Missing timestamps are treated as infinitely stale (threshold exceeded).
    """
    if run.state != "running":
        return False
    now = datetime.now()
    hb_age = float("inf")
    step_age = float("inf")
    if run.lease_heartbeat_ts:
        hb_age = (now - datetime.fromisoformat(run.lease_heartbeat_ts)).total_seconds()
    if run.last_step_progress_ts:
        step_age = (now - datetime.fromisoformat(run.last_step_progress_ts)).total_seconds()
    hb_stale = hb_age > cfg.pipeline.stale_lease_threshold_seconds
    step_stale = step_age > cfg.pipeline.stale_step_threshold_seconds
    return hb_stale and step_stale
```

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/pipeline/test_staleness.py -v`
Expected: 5 PASS.

- [ ] **Step 5: Refactor the CLI to use the new helper**

In `swing/cli.py`, find `pipeline_force_clear_cmd` (around line 629). The existing code computes `heartbeat_age` and `step_age` at the top of the function — `click.confirm(...)` below uses them in its message. Keep that top-of-function age computation; replace only the `hb_stale`/`step_stale`/`is_stale` derivation with a call to the new helper. This preserves the age values for the confirm message and avoids a `NameError` on the success path.

```python
        from swing.pipeline.staleness import is_stale_eligible

        now = _dt.now()
        heartbeat_age = float("inf")
        step_age = float("inf")
        if run.lease_heartbeat_ts:
            heartbeat_age = (now - _dt.fromisoformat(run.lease_heartbeat_ts)).total_seconds()
        if run.last_step_progress_ts:
            step_age = (now - _dt.fromisoformat(run.last_step_progress_ts)).total_seconds()
        is_stale = is_stale_eligible(run, cfg)

        if not is_stale and not bypass_staleness_check:
            raise click.ClickException(
                f"Run {run_id} does not meet staleness threshold "
                f"(heartbeat age {heartbeat_age:.0f}s vs "
                f"{cfg.pipeline.stale_lease_threshold_seconds}s; "
                f"step-progress age {step_age:.0f}s vs "
                f"{cfg.pipeline.stale_step_threshold_seconds}s). "
                "Spec §5.6 requires BOTH signals to be stale. "
                "Use --bypass-staleness-check to override."
            )
```

The existing `click.confirm(...)` below this block still reads `heartbeat_age` and `step_age` for its message; keep it as-is. `force_clear(...)` call below also unchanged.

- [ ] **Step 6: Run the CLI tests + full suite**

Run: `python -m pytest tests/cli/test_cli_pipeline.py -v` — this is the existing suite covering `swing pipeline force-clear`. It must stay green after the refactor (the `click.confirm` message string is asserted in some tests; age-computation behavior must be byte-identical).

Run: `python -m pytest -m "not slow" -q`
Expected: 418 passed (413 + 5). No regressions.

- [ ] **Step 7: Commit**

```bash
git add swing/pipeline/staleness.py swing/cli.py tests/pipeline/test_staleness.py
git commit -m "refactor(pipeline): extract is_stale_eligible helper; CLI reuses it"
```

---

## Task 10: `stale_run_card.html.j2` partial + `GET /pipeline/stale-run-card/{run_id}` route

**Files:**
- Create: `swing/web/templates/partials/stale_run_card.html.j2`
- Modify: `swing/web/routes/pipeline.py`
- Test: `tests/web/test_routes/test_pipeline_route.py`

Spec §3.1, §3.2. The stale-run card is the starting point of the force-clear 2-step. This task creates the partial + its "fetch me fresh" GET route (used by the Cancel button in the confirm fragment).

- [ ] **Step 1: Write failing tests**

Append to `tests/web/test_routes/test_pipeline_route.py`:

```python
def test_get_stale_run_card_renders_for_eligible_run(test_cfg, seeded_db, seed_stale_run):
    """Spec §3.1: GET /pipeline/stale-run-card/{run_id} renders the card for
    an eligible stale run. Used as the Cancel-button target in the confirm UI."""
    run_id = seed_stale_run(hb_age=600, step_age=1200)
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            f"/pipeline/stale-run-card/{run_id}",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 200
    # The card is a <section id="stale-run-{id}"> with a Force-clear button.
    assert f'id="stale-run-{run_id}"' in r.text
    assert "Force clear" in r.text or "Force-clear" in r.text


def test_get_stale_run_card_404_for_non_eligible(test_cfg, seeded_db, seed_stale_run):
    """Run that doesn't meet both-signal staleness → 404 fragment."""
    # Only heartbeat stale, step fresh → NOT eligible.
    run_id = seed_stale_run(hb_age=600, step_age=30)
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            f"/pipeline/stale-run-card/{run_id}",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 404
```

`seed_stale_run` is a new conftest fixture you need to add. Create or append in `tests/web/conftest.py`:

```python
@pytest.fixture
def seed_stale_run(seeded_db):
    """Seed a PipelineRun with state='running' and configurable heartbeat +
    step-progress ages (in seconds). Returns the new run_id."""
    from datetime import datetime, timedelta
    from swing.data.db import connect

    cfg, _ = seeded_db

    def _seed(*, hb_age: int | None, step_age: int | None, state: str = "running") -> int:
        now = datetime.now()
        hb_ts = (now - timedelta(seconds=hb_age)).isoformat(timespec="seconds") if hb_age is not None else None
        step_ts = (now - timedelta(seconds=step_age)).isoformat(timespec="seconds") if step_age is not None else None
        conn = connect(cfg.paths.db_path)
        try:
            with conn:
                cur = conn.execute(
                    """
                    INSERT INTO pipeline_runs
                      (started_ts, trigger, data_asof_date, action_session_date,
                       state, lease_token, lease_heartbeat_ts, last_step_progress_ts,
                       current_step)
                    VALUES (?, 'manual', ?, ?, ?, 't-x', ?, ?, 'evaluate')
                    """,
                    (
                        now.isoformat(timespec="seconds"),
                        now.date().isoformat(),
                        now.date().isoformat(),
                        state,
                        hb_ts,
                        step_ts,
                    ),
                )
                return int(cur.lastrowid)
        finally:
            conn.close()

    return _seed
```

- [ ] **Step 2: Verify they fail**

Run: `python -m pytest tests/web/test_routes/test_pipeline_route.py -k "stale_run_card" -v`
Expected: both FAIL — route not implemented.

- [ ] **Step 3: Create the partial template**

Create `swing/web/templates/partials/stale_run_card.html.j2`:

```jinja
{#- swing/web/templates/partials/stale_run_card.html.j2
    Expects: run (PipelineRun). Renders the wedged-run summary + Force-clear
    button. Only rendered on /pipeline when `is_stale_eligible(run, cfg)` is
    True. Spec §3.1. -#}
<section id="stale-run-{{ run.id }}" class="stale-run-card">
  <div class="banner banner-degraded" role="alert">
    <strong>⚠ Run #{{ run.id }} is wedged.</strong>
    <p>
      state=<code>{{ run.state }}</code>,
      step=<code>{{ run.current_step or '(none)' }}</code>,
      heartbeat=<code>{{ run.lease_heartbeat_ts or '(none)' }}</code>,
      step-progress=<code>{{ run.last_step_progress_ts or '(none)' }}</code>
    </p>
  </div>
  <button hx-get="/pipeline/force-clear/{{ run.id }}/confirm"
          hx-target="closest section[id^='stale-run-']"
          hx-swap="outerHTML"
          hx-headers='{"HX-Request": "true"}'>Force clear</button>
</section>
```

- [ ] **Step 4: Add the GET route**

Append to `swing/web/routes/pipeline.py`:

```python
from swing.pipeline.staleness import is_stale_eligible


@router.get("/pipeline/stale-run-card/{run_id}", response_class=HTMLResponse)
def stale_run_card(request: Request, run_id: int):
    """Render the fresh stale-run card for an eligible run. Used by the Cancel
    button on the force-clear confirm fragment (reverts the swap)."""
    cfg = request.app.state.cfg
    templates = request.app.state.templates
    conn = connect(cfg.paths.db_path)
    try:
        run = find_run(conn, run_id)
    finally:
        conn.close()
    if run is None or not is_stale_eligible(run, cfg):
        raise HTTPException(
            status_code=404,
            detail=f"Run #{run_id} is no longer stale-eligible — refresh the page",
        )
    return templates.TemplateResponse(
        request, "partials/stale_run_card.html.j2", {"run": run},
    )
```

- [ ] **Step 5: Run the new tests**

Run: `python -m pytest tests/web/test_routes/test_pipeline_route.py -k "stale_run_card" -v`
Expected: 2 PASS.

- [ ] **Step 6: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 420 passed (418 + 2). No regressions.

- [ ] **Step 7: Commit**

```bash
git add swing/web/templates/partials/stale_run_card.html.j2 swing/web/routes/pipeline.py tests/web/test_routes/test_pipeline_route.py tests/web/conftest.py
git commit -m "feat(web): GET /pipeline/stale-run-card/{run_id} + partial"
```

---

## Task 11: `force_clear_confirm.html.j2` + `GET /pipeline/force-clear/{run_id}/confirm`

**Files:**
- Create: `swing/web/templates/partials/force_clear_confirm.html.j2`
- Modify: `swing/web/routes/pipeline.py`
- Test: `tests/web/test_routes/test_pipeline_route.py`

Spec §3.1. First click of the 2-step: replaces the stale-run card with a confirmation fragment.

- [ ] **Step 1: Write failing tests**

Append to `tests/web/test_routes/test_pipeline_route.py`:

```python
def test_get_force_clear_confirm_renders_for_eligible_run(test_cfg, seeded_db, seed_stale_run):
    """GET /pipeline/force-clear/{id}/confirm → confirm fragment."""
    run_id = seed_stale_run(hb_age=600, step_age=1200)
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            f"/pipeline/force-clear/{run_id}/confirm",
            headers={"HX-Request": "true", "HX-Target": f"stale-run-{run_id}"},
        )
    assert r.status_code == 200
    assert f'id="stale-run-{run_id}"' in r.text
    assert "Confirm force-clear" in r.text
    assert "Cancel" in r.text
    # Submit button POSTs to the execute endpoint.
    assert f'hx-post="/pipeline/force-clear/{run_id}"' in r.text
    # Cancel button reverts via the GET endpoint from Task 10.
    assert f'hx-get="/pipeline/stale-run-card/{run_id}"' in r.text


def test_get_force_clear_confirm_404_for_non_eligible(test_cfg, seeded_db, seed_stale_run):
    """GET confirm on a non-stale run → 404 (HX-Target-aware fragment or page)."""
    run_id = seed_stale_run(hb_age=30, step_age=30)  # both fresh → not eligible
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            f"/pipeline/force-clear/{run_id}/confirm",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 404
```

- [ ] **Step 2: Verify they fail**

Run: `python -m pytest tests/web/test_routes/test_pipeline_route.py -k "force_clear_confirm" -v`
Expected: both FAIL — route not implemented.

- [ ] **Step 3: Create the confirm template**

Create `swing/web/templates/partials/force_clear_confirm.html.j2`:

```jinja
{#- swing/web/templates/partials/force_clear_confirm.html.j2
    Expects: run (PipelineRun). 2-step confirm fragment (spec §3.1). Replaces
    the stale-run card; submit POSTs to /pipeline/force-clear/{id}; cancel
    GETs /pipeline/stale-run-card/{id} to revert. -#}
<section id="stale-run-{{ run.id }}" class="force-clear-confirm">
  <div class="banner banner-degraded" role="alert">
    <strong>⚠ Confirm force-clear of run #{{ run.id }}.</strong>
    <p>
      Marks the run as <code>force_cleared</code>. Any still-live worker loses
      its lease and cannot commit further writes. This is irreversible.
    </p>
  </div>
  <form hx-post="/pipeline/force-clear/{{ run.id }}"
        hx-target="closest section[id^='stale-run-']"
        hx-swap="outerHTML"
        hx-headers='{"HX-Request": "true"}'>
    <button type="submit">Confirm force-clear</button>
    <button type="button"
            hx-get="/pipeline/stale-run-card/{{ run.id }}"
            hx-target="closest section[id^='stale-run-']"
            hx-swap="outerHTML"
            hx-headers='{"HX-Request": "true"}'>Cancel</button>
  </form>
</section>
```

- [ ] **Step 4: Add the GET confirm route**

Append to `swing/web/routes/pipeline.py`:

```python
@router.get("/pipeline/force-clear/{run_id}/confirm", response_class=HTMLResponse)
def force_clear_confirm(request: Request, run_id: int):
    """Render the 2-step confirm fragment for an eligible stale run (spec §3.1)."""
    cfg = request.app.state.cfg
    templates = request.app.state.templates
    conn = connect(cfg.paths.db_path)
    try:
        run = find_run(conn, run_id)
    finally:
        conn.close()
    if run is None or not is_stale_eligible(run, cfg):
        raise HTTPException(
            status_code=404,
            detail=f"Run #{run_id} is no longer stale-eligible — refresh the page",
        )
    return templates.TemplateResponse(
        request, "partials/force_clear_confirm.html.j2", {"run": run},
    )
```

- [ ] **Step 5: Run the new tests**

Run: `python -m pytest tests/web/test_routes/test_pipeline_route.py -k "force_clear_confirm" -v`
Expected: 2 PASS.

- [ ] **Step 6: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 422 passed (420 + 2). No regressions.

- [ ] **Step 7: Commit**

```bash
git add swing/web/templates/partials/force_clear_confirm.html.j2 swing/web/routes/pipeline.py tests/web/test_routes/test_pipeline_route.py
git commit -m "feat(web): GET /pipeline/force-clear/{run_id}/confirm + 2-step fragment"
```

---

## Task 12: `POST /pipeline/force-clear/{run_id}` + `force_clear_success.html.j2`

**Files:**
- Create: `swing/web/templates/partials/force_clear_success.html.j2`
- Modify: `swing/web/routes/pipeline.py`
- Test: `tests/web/test_routes/test_pipeline_route.py`

Spec §3.1 / §4.2. Second click of the 2-step: calls Phase 2 `force_clear`, verifies the state transition, returns a success fragment.

- [ ] **Step 1: Write failing tests**

Append to `tests/web/test_routes/test_pipeline_route.py`:

```python
def test_post_force_clear_happy_path(test_cfg, seeded_db, seed_stale_run):
    """POST /pipeline/force-clear/{id} on an eligible run → success fragment;
    DB row transitions to state='force_cleared'."""
    from swing.data.db import connect
    from swing.data.repos.pipeline import find_run
    run_id = seed_stale_run(hb_age=600, step_age=1200)
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/pipeline/force-clear/{run_id}",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 200
    assert f'id="stale-run-{run_id}"' in r.text
    assert "Run pipeline" in r.text or "Run now" in r.text  # Run-pipeline button
    assert "cleared" in r.text.lower()
    # DB state verified.
    conn = connect(cfg.paths.db_path)
    try:
        run = find_run(conn, run_id)
    finally:
        conn.close()
    assert run is not None and run.state == "force_cleared"
    assert "dashboard force clear" in (run.error_message or "")


def test_post_force_clear_404_for_non_eligible(test_cfg, seeded_db, seed_stale_run):
    """POST on a non-stale run → 404 (TOCTOU pre-check)."""
    run_id = seed_stale_run(hb_age=30, step_age=30)  # fresh both
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/pipeline/force-clear/{run_id}",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 404


def test_post_force_clear_post_write_state_conflict(test_cfg, seeded_db, seed_stale_run, monkeypatch):
    """If force_clear() is called but the run somehow didn't transition to
    force_cleared (concurrent writer changed state to 'failed' etc.), the
    route must return a 409 rather than silently claim success."""
    from swing.data.db import connect
    from swing.data.repos import pipeline as pr_repo
    run_id = seed_stale_run(hb_age=600, step_age=1200)
    cfg, cfg_path = test_cfg

    # Monkeypatch force_clear to be a silent no-op (simulating a concurrent
    # writer that changed state to 'failed' between our pre-check and write).
    monkeypatch.setattr(
        "swing.web.routes.pipeline.force_clear",
        lambda conn, *, run_id, error_message: None,
    )

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            f"/pipeline/force-clear/{run_id}",
            headers={"HX-Request": "true"},
        )
    assert r.status_code == 409
    assert "conflict" in r.text.lower() or "refresh" in r.text.lower()
```

- [ ] **Step 2: Verify they fail**

Run: `python -m pytest tests/web/test_routes/test_pipeline_route.py -k "post_force_clear" -v`
Expected: all 3 FAIL — route missing.

- [ ] **Step 3: Create the success fragment**

Create `swing/web/templates/partials/force_clear_success.html.j2`:

```jinja
{#- swing/web/templates/partials/force_clear_success.html.j2
    Expects: run_id (int). Renders post-force-clear banner + Run-pipeline
    button to replace the stale-run card. Spec §3.1. -#}
<section id="stale-run-{{ run_id }}" class="force-clear-success">
  <div class="banner banner-info" role="status">
    ✓ Run #{{ run_id }} force-cleared. Ready to start a new pipeline run.
  </div>
  <button hx-post="/pipeline/run" hx-target="#run-panel" hx-swap="innerHTML"
          hx-headers='{"HX-Request": "true"}'>Run now</button>
</section>
```

- [ ] **Step 4: Add the POST route**

Append to `swing/web/routes/pipeline.py` (add `force_clear` + `datetime` imports as needed):

```python
from swing.data.repos.pipeline import force_clear


@router.post("/pipeline/force-clear/{run_id}", response_class=HTMLResponse)
def force_clear_post(request: Request, run_id: int):
    """Execute force-clear after the 2-step confirm (spec §3.1, §4.2).

    Pre-check: is_stale_eligible (TOCTOU guard against cancel/clear between
    GET confirm and POST). Post-check: re-read the run and verify state
    transitioned to 'force_cleared' (guards against a concurrent writer that
    raced our UPDATE with a different state value — 409 fragment in that case).
    """
    cfg = request.app.state.cfg
    templates = request.app.state.templates
    iso_ts = datetime.now().isoformat(timespec="seconds")

    conn = connect(cfg.paths.db_path)
    try:
        run = find_run(conn, run_id)
        if run is None or not is_stale_eligible(run, cfg):
            raise HTTPException(
                status_code=404,
                detail=f"Run #{run_id} is no longer stale-eligible — refresh the page",
            )
        with conn:
            force_clear(
                conn,
                run_id=run_id,
                error_message=f"dashboard force clear at {iso_ts}",
            )
        # Re-read to confirm the state transition landed.
        updated = find_run(conn, run_id)
    finally:
        conn.close()

    if updated is None or updated.state != "force_cleared":
        # Concurrent writer raced us — state changed before our UPDATE but
        # didn't become 'force_cleared'. Return 409 to signal the conflict.
        return templates.TemplateResponse(
            request, "partials/http_error_fragment.html.j2",
            {
                "status_code": 409,
                "detail": (
                    f"Run #{run_id} state conflict (currently "
                    f"{updated.state if updated else 'missing'}). Refresh the page."
                ),
            },
            status_code=409,
        )

    return templates.TemplateResponse(
        request, "partials/force_clear_success.html.j2",
        {"run_id": run_id},
    )
```

- [ ] **Step 5: Run the new tests**

Run: `python -m pytest tests/web/test_routes/test_pipeline_route.py -k "post_force_clear" -v`
Expected: 3 PASS.

- [ ] **Step 6: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 425 passed (422 + 3). No regressions.

- [ ] **Step 7: Commit**

```bash
git add swing/web/templates/partials/force_clear_success.html.j2 swing/web/routes/pipeline.py tests/web/test_routes/test_pipeline_route.py
git commit -m "feat(web): POST /pipeline/force-clear/{run_id} (happy + 404 + 409 state-conflict)"
```

---

## Task 13: Wire stale-run card into `GET /pipeline`

**Files:**
- Modify: `swing/web/routes/pipeline.py::pipeline_page`
- Modify: `swing/web/view_models/pipeline.py` (add `stale_run` field)
- Modify: `swing/web/templates/pipeline.html.j2`
- Test: `tests/web/test_routes/test_pipeline_route.py`

Spec §4.2 step 1. The /pipeline page renders the stale-run card inline when an eligible run exists.

- [ ] **Step 1: Write failing tests**

Append to `tests/web/test_routes/test_pipeline_route.py`:

```python
def test_get_pipeline_renders_stale_run_card_when_eligible(test_cfg, seeded_db, seed_stale_run):
    """Spec §4.2: /pipeline renders stale_run_card.html.j2 inline when an
    eligible stale run exists."""
    run_id = seed_stale_run(hb_age=600, step_age=1200)
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/pipeline")
    assert r.status_code == 200
    assert f'id="stale-run-{run_id}"' in r.text
    assert "Force clear" in r.text or "Force-clear" in r.text


def test_get_pipeline_no_stale_run_card_when_no_active_run(test_cfg, seeded_db):
    """No active run at all → no stale-run card on the page."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/pipeline")
    assert r.status_code == 200
    assert 'id="stale-run-' not in r.text


def test_get_pipeline_no_stale_run_card_when_run_is_fresh(test_cfg, seeded_db, seed_stale_run):
    """Active run but fresh heartbeat + step-progress → no stale-run card."""
    seed_stale_run(hb_age=30, step_age=30)
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/pipeline")
    assert r.status_code == 200
    assert 'id="stale-run-' not in r.text
```

- [ ] **Step 2: Verify they fail**

Run: `python -m pytest tests/web/test_routes/test_pipeline_route.py -k "renders_stale_run_card or no_stale_run_card" -v`
Expected: first test fails (no stale-run card rendered). The other two happen to pass (nothing to hide), but they encode the invariants going forward.

- [ ] **Step 3: Extend `PipelineVM` with a stale_run field**

In `swing/web/view_models/pipeline.py`, modify `PipelineVM` to include an optional stale run:

```python
@dataclass(frozen=True)
class PipelineVM:
    session_date: str
    recent_runs: list[PipelineRun]
    stale_run: PipelineRun | None = None     # NEW: Phase 3c — the stale-eligible run, or None
    # Base-template banner fields
    stale_banner: str | None = None
    price_source_degraded: bool = False
    price_source_degraded_until: str | None = None
```

Modify `build_pipeline` to populate `stale_run`:

```python
def build_pipeline(*, cfg: Config, limit: int = 10) -> PipelineVM:
    from swing.data.repos.pipeline import find_active_run
    from swing.pipeline.staleness import is_stale_eligible
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            runs = list_recent_runs(conn, limit=limit)
            active = find_active_run(conn)
            stale = active if (active is not None and is_stale_eligible(active, cfg)) else None
    finally:
        conn.close()
    return PipelineVM(
        session_date=datetime.now().date().isoformat(),
        recent_runs=list(runs),
        stale_run=stale,
    )
```

- [ ] **Step 4: Render the card in pipeline.html.j2**

Modify `swing/web/templates/pipeline.html.j2`:

```jinja
{#- swing/web/templates/pipeline.html.j2 -#}
{% extends "base.html.j2" %}
{% block content %}
  <h1>Pipeline</h1>
  {% if vm.stale_run %}
    {% with run = vm.stale_run %}
      {% include "partials/stale_run_card.html.j2" %}
    {% endwith %}
  {% endif %}
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

- [ ] **Step 5: Run the new tests**

Run: `python -m pytest tests/web/test_routes/test_pipeline_route.py -k "stale_run_card or no_stale_run_card" -v`
Expected: 3 PASS.

- [ ] **Step 6: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 428 passed (425 + 3). No regressions.

- [ ] **Step 7: Commit**

```bash
git add swing/web/routes/pipeline.py swing/web/view_models/pipeline.py swing/web/templates/pipeline.html.j2 tests/web/test_routes/test_pipeline_route.py
git commit -m "feat(web): /pipeline renders stale-run card when active run is force-clear-eligible"
```

---

## Task 14: CSV upload templates + `cfg.web.csv_upload_max_bytes`

**Files:**
- Modify: `swing/config.py::Web`
- Create: `swing/web/templates/partials/csv_upload_form.html.j2`
- Create: `swing/web/templates/partials/csv_upload_error.html.j2`
- Test: `tests/web/test_config_web.py` (if exists; else skip the config test)

Spec §3.1, §3.2. Foundation templates + config field for the upload feature.

- [ ] **Step 1: Write failing config tests**

Read `tests/web/test_config_web.py` first to see its existing helpers (there's a `_write_cfg` helper pattern and a `load()`-based parser pattern). Append two tests — one checking the dataclass default, one checking TOML parsing:

```python
def test_web_config_has_csv_upload_max_bytes_default():
    """Phase 3c §3.1: Web.csv_upload_max_bytes defaults to 10 MB."""
    from swing.config import Web
    w = Web()
    assert w.csv_upload_max_bytes == 10 * 1024 * 1024


def test_web_config_csv_upload_max_bytes_parsed_from_toml(tmp_path: Path):
    """Phase 3c §3.1: [web] csv_upload_max_bytes = N in TOML → cfg.web.csv_upload_max_bytes == N.
    Follows the same two-dir pattern as existing partial-override tests in this file."""
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg_path = _write_cfg(
        project, home,
        extra='[web]\ncsv_upload_max_bytes = 5242880\n',
    )
    cfg = load(cfg_path)
    assert cfg.web.csv_upload_max_bytes == 5242880
```

The `_write_cfg` helper at `tests/web/test_config_web.py:9` is `_write_cfg(project_dir, home_dir, *, extra="")` — it needs both a project dir (where the TOML + reference/ live) and a home dir (where finviz-inbox + DB resolve to). Existing parser tests in this file use the `project / "project"` and `project / "home"` subdir pattern (e.g. `tests/web/test_config_web.py:80-81`); match that exact pattern.

Run: `python -m pytest tests/web/test_config_web.py -k "csv_upload_max_bytes" -v`
Expected: both FAIL — attribute doesn't exist yet.

- [ ] **Step 2: Add the config field**

In `swing/config.py`, add `csv_upload_max_bytes` to the `Web` dataclass (around line 131):

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
    csv_upload_max_bytes: int = 10 * 1024 * 1024     # NEW: 10 MB (spec §3.1)
```

- [ ] **Step 3: Create the upload form template**

Create `swing/web/templates/partials/csv_upload_form.html.j2`:

```jinja
{#- swing/web/templates/partials/csv_upload_form.html.j2
    Optional context: uploaded_banner = {name, rows} on success; absent otherwise.
    Submits multipart/form-data to /pipeline/csv-upload. Spec §3.1. -#}
<section id="csv-upload-section">
  <h2>Upload finviz CSV</h2>
  {% if uploaded_banner %}
    <div class="banner banner-info" role="status">
      ✓ Uploaded: <code>{{ uploaded_banner.name }}</code>
      ({{ uploaded_banner.rows }} rows). Run the pipeline when ready.
    </div>
  {% endif %}
  <form hx-post="/pipeline/csv-upload"
        hx-target="#csv-upload-section"
        hx-swap="outerHTML"
        hx-encoding="multipart/form-data"
        hx-headers='{"HX-Request": "true"}'>
    <input type="file" name="csv" accept=".csv" required>
    <button type="submit">Upload</button>
  </form>
</section>
```

- [ ] **Step 4: Create the error fragment template**

Create `swing/web/templates/partials/csv_upload_error.html.j2`:

```jinja
{#- swing/web/templates/partials/csv_upload_error.html.j2
    Expects: reasons (list[str]). Re-renders the upload form above a banner
    listing validation failures. Spec §3.1. -#}
<section id="csv-upload-section">
  <h2>Upload finviz CSV</h2>
  <div class="banner banner-degraded" role="alert">
    <strong>Upload rejected.</strong>
    <ul>
      {% for reason in reasons %}
        <li>{{ reason }}</li>
      {% endfor %}
    </ul>
  </div>
  <form hx-post="/pipeline/csv-upload"
        hx-target="#csv-upload-section"
        hx-swap="outerHTML"
        hx-encoding="multipart/form-data"
        hx-headers='{"HX-Request": "true"}'>
    <input type="file" name="csv" accept=".csv" required>
    <button type="submit">Upload</button>
  </form>
</section>
```

- [ ] **Step 5: Run config tests**

Run: `python -m pytest tests/web/test_config_web.py -k "csv_upload_max_bytes" -v`
Expected: 2 PASS.

- [ ] **Step 6: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 430 passed (428 + 2 new config tests).

- [ ] **Step 7: Commit**

```bash
git add swing/config.py swing/web/templates/partials/csv_upload_form.html.j2 swing/web/templates/partials/csv_upload_error.html.j2 tests/web/test_config_web.py
git commit -m "feat(web): CSV upload form + error templates + csv_upload_max_bytes config"
```

---

## Task 15: `MaxBodySizeMiddleware`

**Files:**
- Create: `swing/web/middleware/body_size.py`
- Modify: `swing/web/app.py` (wire into create_app)
- Test: `tests/web/test_body_size_middleware.py` (NEW)

Spec §3.1 (size enforcement layer 1). Pre-body-read Content-Length check before FastAPI's multipart parameter binding runs.

- [ ] **Step 1: Write failing tests**

Create `tests/web/test_body_size_middleware.py`:

```python
"""MaxBodySizeMiddleware — Content-Length pre-read guard for /pipeline/csv-upload.
Spec §3.1 layer 1."""
from __future__ import annotations

from fastapi.testclient import TestClient


def test_middleware_rejects_oversized_content_length(test_cfg, seeded_db):
    """Content-Length header exceeds limit → 413 rendering csv_upload_error.html.j2.
    The middleware uses the same template the route uses for other rejections,
    so HTMX can swap it into #csv-upload-section without visual regression."""
    from swing.web.app import create_app
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # Fake a massive Content-Length value. Body is small but header declares huge.
        oversize = cfg.web.csv_upload_max_bytes + 1
        r = client.post(
            "/pipeline/csv-upload",
            headers={
                "HX-Request": "true",
                "Content-Length": str(oversize),
                "Content-Type": "multipart/form-data; boundary=---x",
            },
            content=b"irrelevant",  # body content unused; middleware acts on header
        )
    assert r.status_code == 413
    # Swap-compatible fragment, not plain text.
    assert 'id="csv-upload-section"' in r.text
    assert "too large" in r.text.lower()


def test_middleware_passes_through_within_limit(test_cfg, seeded_db):
    """Content-Length within limit → middleware lets the request through to the route
    (route is Task 16; before then, the request 404s or 405s, not 413)."""
    from swing.web.app import create_app
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/pipeline/csv-upload",
            headers={
                "HX-Request": "true",
                "Content-Length": "100",
                "Content-Type": "multipart/form-data; boundary=---x",
            },
            content=b"x" * 100,
        )
    # Before Task 16 this route doesn't exist, so expect 404 or 405. The key
    # assertion is: NOT 413 (middleware didn't reject).
    assert r.status_code != 413


def test_middleware_ignores_non_csv_upload_paths(test_cfg, seeded_db):
    """Middleware only applies to /pipeline/csv-upload POSTs. Other routes
    with a large Content-Length aren't rejected by this middleware."""
    from swing.web.app import create_app
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get(
            "/",
            headers={"Content-Length": str(cfg.web.csv_upload_max_bytes + 1)},
        )
    # GET / is unaffected — the dashboard renders fine.
    assert r.status_code == 200
```

- [ ] **Step 2: Verify they fail**

Run: `python -m pytest tests/web/test_body_size_middleware.py -v`
Expected: the oversized test fails (no middleware → request either hits 404 or succeeds). The pass-through tests may pass (route doesn't exist yet, so 404 is returned — which isn't 413).

- [ ] **Step 3: Create the middleware**

Create `swing/web/middleware/body_size.py`:

```python
"""MaxBodySizeMiddleware — Content-Length pre-read guard.

Rejects requests to a configured path whose declared Content-Length exceeds a
byte limit, BEFORE FastAPI's multipart parameter binding reads the body.
Spec §3.1 (Phase 3c CSV-upload layer 1 defense).

For chunked-transfer requests (no Content-Length header), the middleware lets
the request through — a route-level `file.size` safety net catches those.

Renders the same `csv_upload_error.html.j2` fragment the route uses for
schema-invalid rejections, so the HTMX swap target (#csv-upload-section) sees
a consistent UI whether rejection came from the middleware or the route.
"""
from __future__ import annotations

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request


class MaxBodySizeMiddleware(BaseHTTPMiddleware):
    """Reject POSTs to `path_prefix` whose Content-Length > `max_bytes`.

    Arguments (keyword-only):
        path_prefix: exact path match, e.g. "/pipeline/csv-upload". Only POSTs
            to paths EQUAL to this value are inspected. Other requests (including
            sub-paths like `/pipeline/csv-upload/foo` if such routes are added
            later) pass through unchanged.
        max_bytes: inclusive upper bound. Content-Length > max_bytes → 413
            rendering `csv_upload_error.html.j2`.
    """

    def __init__(self, app, *, path_prefix: str, max_bytes: int):
        super().__init__(app)
        # Name kept as `path_prefix` for backward-compat of the kwarg; actual
        # comparison is exact equality. Rename if the comparison ever needs
        # to be prefix-based.
        self._path_prefix = path_prefix
        self._max_bytes = max_bytes

    async def dispatch(self, request: Request, call_next):
        # Exact-path match (not startswith) — a future `/pipeline/csv-upload/foo`
        # route would be unrelated and shouldn't silently inherit this guard.
        if (
            request.method == "POST"
            and request.url.path == self._path_prefix
        ):
            cl_header = request.headers.get("content-length")
            if cl_header is not None:
                try:
                    declared = int(cl_header)
                except ValueError:
                    declared = -1
                if declared > self._max_bytes:
                    # Same template the route renders — swaps cleanly into
                    # #csv-upload-section, not raw text into the DOM.
                    tpls = request.app.state.templates
                    return tpls.TemplateResponse(
                        request, "partials/csv_upload_error.html.j2",
                        {"reasons": [
                            f"file too large "
                            f"(Content-Length: {declared} > {self._max_bytes} bytes)"
                        ]},
                        status_code=413,
                    )
        return await call_next(request)
```

- [ ] **Step 4: Wire into `create_app`**

In `swing/web/app.py`, add the import at the top:

```python
from swing.web.middleware.body_size import MaxBodySizeMiddleware
```

In `create_app`, add the middleware **before** `OriginGuardMiddleware` (Starlette's LIFO order means middleware added last runs first — we want size check to run before origin guard, so add it AFTER origin guard per the LIFO rule):

```python
    # Origin guard for all state-changing requests.
    app.add_middleware(
        OriginGuardMiddleware,
        bound_host=cfg.web.host,
        bound_port=cfg.web.port,
        strict=True,
    )
    # Body-size guard for CSV upload. Runs BEFORE OriginGuard in LIFO order
    # (added after = outer = runs first). Rejects oversized Content-Length at
    # the edge without reading the body.
    app.add_middleware(
        MaxBodySizeMiddleware,
        path_prefix="/pipeline/csv-upload",
        max_bytes=cfg.web.csv_upload_max_bytes,
    )
    # RequestId added AFTER OriginGuard → Starlette LIFO makes it OUTERMOST,
    # so 403 responses from OriginGuard still get X-Request-ID stamped.
    app.add_middleware(RequestIdMiddleware)
```

Starlette middleware stack is LIFO: `app.add_middleware(M)` wraps the app so M runs **outermost**. Each subsequent `add_middleware` wraps what came before, becoming the new outermost. Execution order on the request path is the reverse of the `add_middleware` call order.

**Security contract:** under strict OriginGuard (Phase 3b decision), a POST without `HX-Request: true` MUST return 403 — regardless of what else is wrong with the request. If `MaxBodySizeMiddleware` runs BEFORE `OriginGuardMiddleware` on the request path, an oversized POST without HX-Request gets a 413 instead of a 403, silently weakening the strict-mode contract. OriginGuard inspects only headers (no body read), so running it first is safe and preserves the "403 first, everything else after" rule.

Desired execution order (outermost → innermost): `RequestIdMiddleware` (stamps X-Request-ID on every response) → `OriginGuardMiddleware` (403 if no HX-Request) → `MaxBodySizeMiddleware` (413 if Content-Length too big) → route (schema validation, 400 on bad filename/schema, 200 on success).

To achieve that with LIFO `add_middleware` calls, the add order must be (innermost first, outermost last):

1. `app.add_middleware(MaxBodySizeMiddleware, ...)` — added FIRST → innermost on request path
2. `app.add_middleware(OriginGuardMiddleware, ...)` — added SECOND → middle
3. `app.add_middleware(RequestIdMiddleware)` — added LAST → outermost

Since the existing `create_app` already has `add_middleware(OriginGuardMiddleware)` THEN `add_middleware(RequestIdMiddleware)`, Phase 3c inserts the `MaxBodySizeMiddleware` call **before** the OriginGuard call:

```python
    # Body-size guard FIRST (innermost) — runs AFTER OriginGuard on the
    # request path. Only fires on /pipeline/csv-upload POSTs that already
    # passed OriginGuard (i.e., they have HX-Request: true). Oversized POSTs
    # without HX-Request get 403 from OriginGuard before ever hitting this.
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
    # RequestId added LAST → outermost → runs first → all responses (403, 413,
    # 200) get X-Request-ID stamped.
    app.add_middleware(RequestIdMiddleware)
```

- [ ] **Step 5: Run the new tests**

Run: `python -m pytest tests/web/test_body_size_middleware.py -v`
Expected: 3 PASS.

- [ ] **Step 6: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 431 passed (428 + 3). No regressions.

- [ ] **Step 7: Commit**

```bash
git add swing/web/middleware/body_size.py swing/web/app.py tests/web/test_body_size_middleware.py
git commit -m "feat(web): MaxBodySizeMiddleware — Content-Length pre-read guard for /pipeline/csv-upload"
```

---

## Task 16: `POST /pipeline/csv-upload` route

**Files:**
- Modify: `swing/web/routes/pipeline.py`
- Test: `tests/web/test_routes/test_pipeline_route.py`

Spec §3.1, §4.1. Upload endpoint: validate schema, sanitize filename, atomic replace into the inbox. Middleware + route-level safety-net for size.

- [ ] **Step 1: Write failing tests**

Append to `tests/web/test_routes/test_pipeline_route.py`:

```python
def _valid_finviz_csv_bytes() -> bytes:
    """Minimal CSV matching the finviz REQUIRED_COLUMNS for validate_csv."""
    header = (
        'No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,'
        'Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap\n'
    )
    row = "1,AAPL,Tech,Consumer Elec,USA,180.95,+0.5%,50M,1.2,2.3,200.0,100.0,2.5B\n"
    return (header + row).encode("utf-8")


def test_csv_upload_happy_path(test_cfg, seeded_db):
    """POST /pipeline/csv-upload with a valid CSV → 200 + file in inbox."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/pipeline/csv-upload",
            headers={"HX-Request": "true"},
            files={"csv": ("finviz19Apr2026.csv", _valid_finviz_csv_bytes(), "text/csv")},
        )
    assert r.status_code == 200
    assert "Uploaded" in r.text
    assert "finviz19apr2026.csv" in r.text.lower()
    # File landed in the inbox.
    inbox_files = list(cfg.paths.finviz_inbox_dir.glob("*.csv"))
    assert any("finviz19apr2026.csv" in f.name for f in inbox_files)


def test_csv_upload_invalid_schema_returns_400(test_cfg, seeded_db):
    """CSV missing required columns → 400 csv_upload_error.html.j2 with reasons."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/pipeline/csv-upload",
            headers={"HX-Request": "true"},
            files={"csv": ("bad.csv", b"foo,bar\n1,2\n", "text/csv")},
        )
    assert r.status_code == 400
    assert "Upload rejected" in r.text
    assert "missing columns" in r.text.lower()


def test_csv_upload_bad_filename_rejected(test_cfg, seeded_db):
    """Path-traversal / invalid-character filenames → 400."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.post(
            "/pipeline/csv-upload",
            headers={"HX-Request": "true"},
            files={"csv": ("../evil.csv", _valid_finviz_csv_bytes(), "text/csv")},
        )
    assert r.status_code == 400
    assert "filename" in r.text.lower() or "invalid" in r.text.lower()


def test_csv_upload_replaces_existing_inbox_file(test_cfg, seeded_db):
    """Uploading the same filename twice overwrites the first copy atomically."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        first = client.post(
            "/pipeline/csv-upload",
            headers={"HX-Request": "true"},
            files={"csv": ("finviz19apr2026.csv", _valid_finviz_csv_bytes(), "text/csv")},
        )
        assert first.status_code == 200

        # Second upload with same name replaces the first.
        second_bytes = _valid_finviz_csv_bytes() + b"2,MSFT,Tech,Software,USA,400.0,+1%,20M,1.0,2.0,450.0,200.0,3T\n"
        second = client.post(
            "/pipeline/csv-upload",
            headers={"HX-Request": "true"},
            files={"csv": ("finviz19apr2026.csv", second_bytes, "text/csv")},
        )
    assert second.status_code == 200
    # Inbox has exactly one file with this name, and it contains both rows.
    inbox_files = [f for f in cfg.paths.finviz_inbox_dir.glob("*.csv") if "finviz19apr2026" in f.name.lower()]
    assert len(inbox_files) == 1
    assert b"MSFT" in inbox_files[0].read_bytes()


def test_csv_upload_size_over_limit_returns_413(test_cfg, seeded_db):
    """Oversized upload → 413 rendering csv_upload_error.html.j2.

    Note: with `TestClient`, the client always sets Content-Length, so in practice
    the middleware's Content-Length pre-check is what fires here. The route-level
    `file.size` safety-net exists for chunked-transfer requests (no Content-Length)
    that may arrive from real HTTP clients; exercising that code path end-to-end
    would require a chunked-transfer test harness beyond TestClient. The two
    layers share the same template, so the user-visible response is identical
    regardless of which layer rejected."""
    cfg, cfg_path = test_cfg
    # Lower the limit for this test so we can trigger it with a small body.
    from dataclasses import replace as _replace
    small_web = _replace(cfg.web, csv_upload_max_bytes=100)
    tiny_cfg = _replace(cfg, web=small_web)

    app = create_app(tiny_cfg, cfg_path)
    big_body = b"x" * 500
    with TestClient(app) as client:
        r = client.post(
            "/pipeline/csv-upload",
            headers={"HX-Request": "true"},
            files={"csv": ("big.csv", big_body, "text/csv")},
        )
    assert r.status_code == 413
    assert 'id="csv-upload-section"' in r.text
    assert "too large" in r.text.lower()
```

- [ ] **Step 2: Verify they fail**

Run: `python -m pytest tests/web/test_routes/test_pipeline_route.py -k "csv_upload" -v`
Expected: all 5 FAIL (route missing).

- [ ] **Step 3: Add the route**

Append to `swing/web/routes/pipeline.py`. First, add imports at the top:

```python
import os
import pathlib
import re
import tempfile

from fastapi import File, UploadFile

from swing.pipeline.finviz_schema import validate_csv
```

Then the route:

```python
_FILENAME_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.-]*\.csv$")


def _sanitize_filename(raw: str | None) -> str | None:
    """Return a safe inbox filename or None if unacceptable.

    Accepts: A-Z, a-z, 0-9, underscore, dot, hyphen. Must start with alphanumeric
    and end in .csv. Any path separators or '..' segments → rejected.
    Spec §4.1 + §9.7.
    """
    if not raw:
        return None
    name = raw.replace("\\", "/").split("/")[-1].strip().lower()
    if ".." in name:
        return None
    if not _FILENAME_RE.match(name):
        return None
    return name


@router.post("/pipeline/csv-upload", response_class=HTMLResponse)
async def csv_upload(request: Request, csv: UploadFile = File(...)):
    """Upload a finviz CSV to the inbox. Validate schema + sanitize filename +
    atomically replace any existing same-name file. Spec §3.1 / §4.1."""
    cfg = request.app.state.cfg
    templates = request.app.state.templates
    max_bytes = cfg.web.csv_upload_max_bytes

    # Route-level size safety-net (middleware also guards via Content-Length).
    # UploadFile.size is populated by Starlette after multipart parsing.
    if csv.size is not None and csv.size > max_bytes:
        return templates.TemplateResponse(
            request, "partials/csv_upload_error.html.j2",
            {"reasons": [f"file too large ({csv.size} bytes > {max_bytes} limit)"]},
            status_code=413,
        )

    sanitized = _sanitize_filename(csv.filename)
    if sanitized is None:
        return templates.TemplateResponse(
            request, "partials/csv_upload_error.html.j2",
            {"reasons": [f"invalid filename: {csv.filename!r}"]},
            status_code=400,
        )

    # Temp file MUST live in the inbox directory so os.replace is a same-volume
    # atomic rename (spec §4.1 — avoids cross-device EXDEV on Windows cloud-sync).
    inbox = cfg.paths.finviz_inbox_dir
    inbox.mkdir(parents=True, exist_ok=True)
    fd, tmp_path_str = tempfile.mkstemp(suffix=".csv", dir=str(inbox))
    tmp_path = pathlib.Path(tmp_path_str)
    try:
        # Write upload bytes to tmp file, enforcing limit along the way.
        total = 0
        os_write = os.write
        while True:
            chunk = await csv.read(64 * 1024)
            if not chunk:
                break
            total += len(chunk)
            if total > max_bytes:
                os.close(fd)
                tmp_path.unlink(missing_ok=True)
                return templates.TemplateResponse(
                    request, "partials/csv_upload_error.html.j2",
                    {"reasons": [f"file too large (streamed > {max_bytes} bytes)"]},
                    status_code=413,
                )
            os_write(fd, chunk)
        os.close(fd)

        result = validate_csv(tmp_path)
        if not result.is_valid:
            tmp_path.unlink(missing_ok=True)
            return templates.TemplateResponse(
                request, "partials/csv_upload_error.html.j2",
                {"reasons": result.reasons},
                status_code=400,
            )

        final_path = inbox / sanitized
        os.replace(tmp_path, final_path)
    except Exception:
        tmp_path.unlink(missing_ok=True)
        raise

    return templates.TemplateResponse(
        request, "partials/csv_upload_form.html.j2",
        {"uploaded_banner": {"name": sanitized, "rows": result.row_count}},
        status_code=200,
    )
```

(Pathlib is added to the import list above.)

- [ ] **Step 4: Run the new tests**

Run: `python -m pytest tests/web/test_routes/test_pipeline_route.py -k "csv_upload" -v`
Expected: 5 PASS.

- [ ] **Step 5: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 436 passed (431 + 5). No regressions.

- [ ] **Step 6: Commit**

```bash
git add swing/web/routes/pipeline.py tests/web/test_routes/test_pipeline_route.py
git commit -m "feat(web): POST /pipeline/csv-upload — validate + sanitize + atomic replace"
```

---

## Task 17: Wire CSV upload section into `pipeline.html.j2`

**Files:**
- Modify: `swing/web/templates/pipeline.html.j2`
- Test: `tests/web/test_routes/test_pipeline_route.py`

Spec §3.1. The form is rendered inline on the /pipeline page so the user sees the upload UI without navigating.

- [ ] **Step 1: Write failing test**

Append to `tests/web/test_routes/test_pipeline_route.py`:

```python
def test_get_pipeline_includes_csv_upload_section(test_cfg, seeded_db):
    """Spec §3.1: /pipeline renders the #csv-upload-section inline."""
    cfg, cfg_path = test_cfg
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/pipeline")
    assert r.status_code == 200
    assert 'id="csv-upload-section"' in r.text
    assert 'hx-post="/pipeline/csv-upload"' in r.text
    assert 'type="file"' in r.text
```

- [ ] **Step 2: Verify it fails**

Run: `python -m pytest tests/web/test_routes/test_pipeline_route.py::test_get_pipeline_includes_csv_upload_section -v`
Expected: FAIL — `#csv-upload-section` not rendered.

- [ ] **Step 3: Include the upload form in `pipeline.html.j2`**

Modify `swing/web/templates/pipeline.html.j2` to include the upload form between the stale-run card block and the Run-now button:

```jinja
{#- swing/web/templates/pipeline.html.j2 -#}
{% extends "base.html.j2" %}
{% block content %}
  <h1>Pipeline</h1>
  {% if vm.stale_run %}
    {% with run = vm.stale_run %}
      {% include "partials/stale_run_card.html.j2" %}
    {% endwith %}
  {% endif %}
  {% include "partials/csv_upload_form.html.j2" %}
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

- [ ] **Step 4: Run the new test**

Run: `python -m pytest tests/web/test_routes/test_pipeline_route.py::test_get_pipeline_includes_csv_upload_section -v`
Expected: PASS.

- [ ] **Step 5: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: 437 passed (436 + 1). No regressions.

- [ ] **Step 6: Commit**

```bash
git add swing/web/templates/pipeline.html.j2 tests/web/test_routes/test_pipeline_route.py
git commit -m "feat(web): /pipeline page includes #csv-upload-section inline"
```

---

## Task 18: Full-suite acceptance sweep

**Files:** none (verification only)

Final regression gate before adversarial review.

- [ ] **Step 1: Run full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: **~437 passed** (397 baseline + ~40 new from Phase 3c). Actual number may vary by a few as tasks add/adjust tests. Minimum: **413** (spec target).

If any Phase 2, 3a, or 3b test regresses, investigate immediately. Phase 2 should have exactly 2 new tests added (from Task 8); everything else was Phase 3-layer.

- [ ] **Step 2: Spot-check Phase 2 regression isolation**

Run: `python -m pytest tests/data/ tests/pipeline/ -q`
Expected: Phase 2 + new staleness tests pass. If a pre-existing Phase 2 test fails, revert the Phase 3c change that broke it and re-evaluate.

- [ ] **Step 3: Spot-check Phase 3a + 3b routes**

Run: `python -m pytest tests/web/test_origin_guard.py tests/web/test_error_handling.py tests/web/test_routes/ tests/web/test_dashboard_integration.py tests/web/test_trades_integration.py -v`
Expected: all green. Any failures indicate a 3c change broke 3a/3b contract.

- [ ] **Step 4: Optional lint**

Run: `ruff check swing/web/ swing/data/repos/trades.py swing/pipeline/staleness.py swing/cli.py`
Expected: no new warnings in the modified/added files.

- [ ] **Step 5: Final commit (only if lint fixes were needed)**

If lint produced fixes:
```bash
git add swing/ && git commit -m "chore(web): lint sweep after Phase 3c"
```

Otherwise skip this step.

---

## Plan summary

- **18 tasks**, each ending in a clean commit.
- **~40 new tests** distributed across view_models, routes, middleware, handlers, Phase 2 repo, and a new staleness helper module.
- **Target test count:** 397 (end of 3b) → ~437 (3c). Spec baseline: 413+.
- **Phase 2 change scope:** exactly one function — `update_stop_with_event` gains an atomic `status = 'open'` guard + rowcount check (spec §4.4 / decision #4). All other Phase 2 files are consumed read-only.
- **Spec coverage:**
  - §1.2 Phase 2 carve-out → Task 8
  - §2.3 is_stale_eligible helper → Task 9
  - §3.1 routes → Tasks 10-13, 16-17
  - §3.2 PageErrorVM + page_error.html.j2 → Task 5
  - §3.2a HTMX 4xx-swap config → Task 2
  - §3.3 app.state.templates + HX-Target handlers + non-HTMX GET branch → Tasks 1, 4, 6
  - §3.4 /journal Literal[...] → Task 7
  - §4.1 CSV upload flow → Task 16
  - §4.2 Force-clear 2-step → Tasks 10-13
  - §4.3 Malformed query recovery → Tasks 6-7
  - §4.4 Atomic stop-adjust → Task 8
  - §4.5 HX-Target handler heuristic → Task 4
  - MaxBodySizeMiddleware → Task 15
  - CSV upload form/error partials → Task 14
  - watchlist_row id addition → Task 3
