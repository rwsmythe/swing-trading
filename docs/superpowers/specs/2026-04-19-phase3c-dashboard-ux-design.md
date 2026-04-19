# Phase 3c — Dashboard UX + Cleanup Design

**Status:** Draft (brainstorm output — awaiting user review, then adversarial critic, then implementation plan).

**Scope:** Six changes on top of the Phase 3b dashboard (commit `a988eb6`, 397 fast tests):
1. Force-clear button on `/pipeline` for stale runs (inline 2-step confirm).
2. CSV upload form on `/pipeline` (upload-only workflow).
3. Malformed query param → 400-with-HTML (replaces current 500 on `/journal?period=<bad>`).
4. Atomic closed-trade guard on `update_stop_with_event` (**one scoped Phase 2 change**).
5. Path-aware exception handlers switch from URL-prefix heuristic to `HX-Target` header inspection.
6. `_templates` helper promoted to `app.state.templates` (startup-built, cross-module private import removed).

## 1. Context and decision

Phase 3a shipped a read-only dashboard. Phase 3b shipped inline HTMX row-swap trade-action forms. Phase 3c wraps up the previously-deferred dashboard UX items plus the two cleanup findings that surfaced during Phase 3b's adversarial Codex review (R3 Major atomicity race, R3 Minor path-aware breadth). Phase 3d will handle the only larger standalone subsystem deferred by 3b: SMA-aware advisories (`trail_ma`, `exit_close_below_ma`) that need on-demand OHLCV→SMA computation.

### 1.3 Scope notes against the original request

The original Phase 3c brainstorm request enumerated seven items, including "CSV upload … validate + trigger pipeline" and "SMA-aware advisories." Two deliberate decompositions happened during the brainstorm Q&A:

- **CSV upload is upload-only** (decision #1, locked below). The user was explicitly presented with A (upload-only), B (upload + auto-run), and C (upload + dropdown); option A was chosen because it preserves the Phase 2 `select_csv` inbox convention and avoids conflating an upload HTTP endpoint with a pipeline-subprocess lifecycle. The "trigger pipeline" half of the original request is already satisfied by the existing `POST /pipeline/run` button (Phase 3a); the user continues to click that button separately after upload.
- **SMA-aware advisories are deferred to Phase 3d** as a standalone spec cycle. The user explicitly approved the 3c={force-clear, CSV upload, query-param, stop-adjust guard, path-heuristic, _templates} / 3d={SMA advisories} decomposition at the start of this brainstorm. SMA requires its own design pass for OHLCV source, caching strategy, fetch timing, and per-render cost budget — questions that should not share a spec with a force-clear button.

### 1.1 Threat model inheritance

Phase 3b's §1.1 threat model carries forward unchanged: loopback-only binding, single-operator assumption, HX-Request-required on unsafe methods as defense-in-depth (not cryptographic CSRF). The new POST endpoints in 3c (`/pipeline/csv-upload`, `/pipeline/force-clear/{run_id}`) inherit strict OriginGuard enforcement. No new security boundary is introduced.

### 1.2 Phase 2 boundary re-opening

Phase 3b's spec §9.6 locked "Business logic stays in Phase 2; 3b is purely a form-layer addition." Phase 3c explicitly re-opens that invariant for **one** change: adding `AND status = 'open'` + rowcount check to `swing/data/repos/trades.py::update_stop_with_event`. This is a correctness fix flagged by Codex during Phase 3b R3 adversarial review; the proper fix lives at the repo layer. The carve-out is documented in §4.4 and covered by adversarial review of Phase 3c.

### Explicitly deferred

- **To 3d:** SMA-aware advisories (`trail_ma`, `exit_close_below_ma`) + on-demand OHLCV fetch + caching. Settings editor (`/settings` GET + POST). Per-run detail route (`/pipeline/runs/{run_id}` HTML equivalent of the archived briefing).
- **Phase 4+:** live streaming quotes, broker integration, mobile-optimized layout, keyboard shortcuts, client-side validation frameworks, CSV drag-and-drop UI (3c uses plain `<input type="file">`).
- **Always out of scope:** multi-user auth, cryptographic CSRF, real-time push.

## 2. Architecture

### 2.1 Layering (unchanged from 3a/3b)

- **Routes** (`swing/web/routes/*.py`) are thin handlers.
- **View-models** (`swing/web/view_models/*.py`) carry pre-computed data for templates. Frozen dataclasses.
- **Templates** (`swing/web/templates/`) are pure Jinja with HTMX attributes.
- **Business logic** stays in Phase 2 (one documented exception: §4.4).

### 2.2 File layout

```
swing/web/
├── app.py                         # MODIFIED: app.state.templates; HX-Target path-aware handlers; full-page 400 branch; MaxBodySizeMiddleware wiring
├── middleware/
│   └── body_size.py               # NEW: MaxBodySizeMiddleware — Content-Length pre-read guard for /pipeline/csv-upload
├── view_models/
│   └── error.py                   # NEW: PageErrorVM dataclass (base-layout-compatible context for page_error.html.j2)
├── routes/
│   ├── dashboard.py               # MODIFIED: remove _templates helper; use app.state.templates
│   ├── journal.py                 # MODIFIED: period: Literal[...]; use app.state.templates
│   ├── pipeline.py                # MODIFIED: POST /pipeline/csv-upload; force-clear trio; GET /pipeline renders stale-run card when eligible; use app.state.templates
│   ├── trades.py                  # MODIFIED: use app.state.templates at all call sites
│   └── watchlist.py               # MODIFIED: use app.state.templates at all call sites
├── templates/
│   ├── base.html.j2               # MODIFIED: add htmx.config override for 4xx response swapping
│   ├── pipeline.html.j2           # MODIFIED: adds #csv-upload-section and #stale-run-{run_id} regions
│   ├── page_error.html.j2         # NEW: full-page 400 for non-HTMX GET query-param errors
│   └── partials/
│       ├── csv_upload_form.html.j2       # NEW
│       ├── csv_upload_error.html.j2      # NEW: banner-degraded + validation reasons + form preserved
│       ├── stale_run_card.html.j2        # NEW: wraps stale-run info + Force-clear button
│       ├── force_clear_confirm.html.j2   # NEW: 2-step confirm fragment
│       └── watchlist_row.html.j2         # MODIFIED: add id="watchlist-row-{{ w.ticker }}" for HX-Target matching

swing/pipeline/staleness.py        # NEW: is_stale_eligible(run, cfg) helper extracted from cli.py (shared by CLI + web)

swing/cli.py                       # MODIFIED: inline staleness check replaced by is_stale_eligible import

swing/data/repos/trades.py         # MODIFIED (Phase 2 carve-out): update_stop_with_event status guard

swing/config.py                    # MODIFIED: cfg.web.csv_upload_max_bytes (default 10MB)
```

### 2.3 Dependencies (read-only, except where marked)

- `swing/pipeline/finviz_schema.py::validate_csv` — CSV schema validation (existing)
- `swing/data/repos/pipeline.py::find_active_run, force_clear` — pipeline repo (existing)
- `swing/data/repos/trades.py::update_stop_with_event` — **MODIFIED** in Phase 3c
- `swing/web/view_models/dashboard.py::build_dashboard` — for status-strip rebuild (unchanged)
- `swing/web/routes/pipeline.py::_heartbeat_age_seconds` (existing 3a helper)
- `swing/pipeline/staleness.py::is_stale_eligible` — **NEW in 3c**: extracts the `heartbeat_stale AND step_progress_stale` check currently inlined in `swing/cli.py::pipeline_force_clear_cmd` (~lines 650–660). Used by both the CLI command (refactored to import the helper) and the new web routes. Reads `cfg.pipeline.stale_lease_threshold_seconds` and `cfg.pipeline.stale_step_threshold_seconds` per spec §5.6.

## 3. Components

### 3.1 Routes (new)

**`POST /pipeline/csv-upload`** (multipart/form-data, field `csv`)
- Safety: strict OriginGuard (HX-Request required).
- **Size enforcement:** middleware-based pre-read + route-level safety net.
  - **Middleware:** new `MaxBodySizeMiddleware` in `swing/web/middleware/body_size.py`, wired in `create_app` alongside `OriginGuardMiddleware`. Applies only to `/pipeline/csv-upload` POSTs (path check). Inspects `Content-Length` header via Starlette's ASGI scope **before** FastAPI's multipart parameter binding runs. If declared size exceeds `cfg.web.csv_upload_max_bytes` (default 10MB), responds 413 with `csv_upload_error.html.j2` and short-circuits. For chunked-transfer requests (no Content-Length), middleware lets them through to the route — a second guard fires there.
  - **Route-level safety net:** after FastAPI multipart binding populates the `UploadFile`, the route checks `file.size` (Starlette attribute set post-parse). If > limit, responds 413. This catches chunked-transfer uploads that slipped past the header check, at the cost of having already buffered the body to disk (SpooledTemporaryFile spills past ~1MB).
  - **Rationale for two-layer design:** the threat model (Phase 3b §1.1, inherited) is loopback single-operator — DoS/resource-exhaustion isn't in scope. The middleware is the correct layer for "reject before body-read"; the route-level check is defense-in-depth for edge cases. Trying to bypass FastAPI's multipart parser by reading `request.stream()` in the route would require reimplementing multipart parsing and is rejected as over-engineering.
- Save upload chunks to a `tempfile.NamedTemporaryFile` → `validate_csv(path)` → on valid, atomically replace `cfg.paths.finviz_inbox_dir / <sanitized-name>`; on invalid, render `csv_upload_error.html.j2` with reasons.
- Response (200 success): re-rendered `csv_upload_form.html.j2` with inline success banner `"Uploaded: <name> (<N> rows). Run the pipeline when ready."`
- Response (400 invalid schema, bad filename): `csv_upload_error.html.j2`.
- Response (413 oversized): `csv_upload_error.html.j2` with a "file too large" reason.
- Target swap: `#csv-upload-section` `outerHTML`.

**`GET /pipeline/force-clear/{run_id}/confirm`**
- Fetches the run; if not stale-eligible → `HTTPException(404)` (handler renders as fragment or page per HX-Target).
- Else → `force_clear_confirm.html.j2`.
- Target swap: `closest section[id^='stale-run-']` `outerHTML`.

**`POST /pipeline/force-clear/{run_id}`**
- Re-verifies stale-eligibility (guards against TOCTOU between GET confirm and POST). If no longer stale-eligible → 404 HX-Target-aware fragment.
- Actual Phase 2 signature: `force_clear(conn, *, run_id: int, error_message: str) -> None`. The repo function is a silent UPDATE with `WHERE id = ? AND state = 'running'` — no `reason` kwarg, no `bypass_staleness_check` kwarg, no exception raised if the row is already non-running. **The route owns staleness enforcement**; the repo just performs the state transition.
- Route behavior: construct `error_message=f"dashboard force clear at {iso_ts}"`, call `force_clear(conn, run_id=run_id, error_message=error_message)`, then re-read the run via `find_run(conn, run_id)` to confirm `state == 'force_cleared'`. If the post-write state is still `'running'` (extreme race — another process wrote between our pre-check and UPDATE with a different state value) → render a 409-style fragment explaining the conflict and advising refresh.
- On post-write state `'force_cleared'`: response replaces the stale-run card with a transient success banner + Run-pipeline button fragment.

**`GET /pipeline/stale-run-card/{run_id}`**
- Returns the original `stale_run_card.html.j2` for the run (used by the Cancel button in the confirm fragment). 404 if no longer stale-eligible.

**`watchlist_row.html.j2` id addition:** the existing template `<tr>` has no `id` attribute, so HTMX omits `HX-Target` when the Enter button fires. Phase 3c adds `id="watchlist-row-{{ w.ticker }}"` to the row so `HX-Target` is populated and the row-prefix whitelist engages for any error responses from `GET /trades/entry/form`. No existing test asserts on the row id, so the change is additive.

### 3.2 Templates (new)

**`csv_upload_form.html.j2`** — single-file input form, submits to `/pipeline/csv-upload` with `hx-target="#csv-upload-section" hx-swap="outerHTML" hx-encoding="multipart/form-data" hx-headers='{"HX-Request":"true"}'`. Includes optional success banner slot.

**`csv_upload_error.html.j2`** — re-renders the upload form above a `banner-degraded` div listing validation reasons.

**`stale_run_card.html.j2`** — Expects `run: PipelineRun`. Renders the run summary (id, stale step-progress age, last step) + Force-clear button targeting `GET /pipeline/force-clear/{run.id}/confirm`.

**`force_clear_confirm.html.j2`** — banner-degraded `<section id="stale-run-{run.id}">` with "Confirm force-clear" warning copy (spec §5.6) + submit form to `POST /pipeline/force-clear/{run.id}` + Cancel button to `GET /pipeline/stale-run-card/{run.id}`.

**`page_error.html.j2`** — full-page HTML error (extends 3a base layout). Renders navigation + error banner + `{{ detail }}` message.

**Context compatibility:** the 3a base layout (`base.html.j2`) dereferences `vm.session_date`, `vm.stale_banner`, and `vm.price_source_degraded` on every render. `page_error.html.j2` must be called with a compatible `vm` object or template rendering will raise `UndefinedError` — turning one validation error into a 500. Phase 3c introduces `PageErrorVM` (new frozen dataclass in `swing/web/view_models/error.py`):

```python
@dataclass(frozen=True)
class PageErrorVM:
    session_date: str              # today's action_session_for_run() value, or "n/a"
    stale_banner: None = None      # never stale in an error page
    price_source_degraded: bool = False
    status_code: int = 400
    detail: str = "Invalid request"
```

`_handle_validation_error`'s non-HTMX GET branch builds this VM (best-effort — if `action_session_for_run` itself raises, fall back to `session_date="n/a"`) and renders `page_error.html.j2` with `{"vm": vm}` context. This keeps the error page inside the normal chrome (nav bar, styling) without blowing up on missing fields.

### 3.2a HTMX 4xx-swap client-side config (prerequisite for ALL 4xx fragments)

HTMX 2.x defaults to **not swapping** 4xx responses into the DOM — it fires an error event instead. Phase 3b's `trade_form_error.html.j2` fragments (400/404) and Phase 3c's new fragments (400/404/409/413) are all unreachable in the browser under default config, even though the tests (TestClient-based) don't catch this because they assert response body directly rather than DOM state.

**3c adds** a config override to `swing/web/templates/base.html.j2` immediately after the htmx script tag:

```html
<script src="/static/htmx.min.js"></script>
<script>
  // Enable inline rendering of 4xx error fragments. Phase 3b+ relies on this;
  // without the override, 400/404/409/413 responses fire an htmx error event
  // and do NOT swap into the target.
  htmx.config.responseHandling = [
    {code: "204", swap: false},
    {code: "[12]..", swap: true},
    {code: "[45]..", swap: true, error: true},
  ];
</script>
```

**Retroactive coverage:** this is effectively a Phase 3b bug fix (the 4xx fragment machinery was untested end-to-end in-browser). Phase 3c's test suite adds a stronger-than-substring test:
- Renders the full `/` (dashboard) page and asserts that (a) `/static/htmx.min.js` appears first, (b) the `htmx.config.responseHandling` override script appears AFTER the htmx.min.js script tag in source order, (c) the override string contains both `"[45].."` and `swap: true` tokens. This catches the ordering mistake Codex flagged as a weakness of a pure substring check: a malformed or mis-ordered override fails the test.
- True end-to-end browser verification (launching headless Chrome and asserting the effective `htmx.config.responseHandling` value) is deliberately out of scope — the ordered-source-check is a practical middle ground.

### 3.3 `app.state.templates` + handler changes

In `create_app`:
```python
app.state.templates_dir = <path>  # 3a
app.state.templates = Jinja2Templates(directory=str(app.state.templates_dir))  # 3c
```

`_templates(request)` helper is removed. Every route uses `request.app.state.templates`.

Both `_handle_http_exc` and `_handle_validation_error` replace `request.url.path.startswith("/trades/")` with:
```python
_ROW_TARGET_PREFIXES = (
    "open-position-",     # open-positions row
    "entry-form-",        # entry form (replaces watchlist row)
    "exit-form-",         # exit form (replaces open-position row)
    "stop-form-",         # stop-adjust form (replaces open-position row)
    "watchlist-row-",     # 3c-added id — row target for Enter-button errors
)

def _is_row_swap_target(request) -> bool:
    return request.headers.get("HX-Target", "").startswith(_ROW_TARGET_PREFIXES)
```

`_handle_validation_error` gains a third branch for non-HTMX GETs that accept HTML. **Precedence order (exact):**

1. `HX-Request: true` → HTMX handler path (row-target or div, per §3.3 whitelist). Accept header is ignored once HX-Request is truthy.
2. Else, method is `GET` AND `request.headers.get("accept", "")` contains `"text/html"` (substring match, handles `text/html,application/xhtml+xml,*/*` browser headers) → full-page `page_error.html.j2`.
3. Else (non-HTMX POST, or GET with JSON-only Accept like `application/json` or `*/*` without `text/html`) → FastAPI default 422 JSON.

This gating is heuristic — a non-browser client sending `*/*` gets JSON (intended); a non-browser client sending `text/html` gets the error page (acceptable). The spec treats "HTMX vs browser vs API" as the three-way decision; no attempt is made to further distinguish "browser" from "non-browser HTML-accepting client" since both want a readable HTML response.

Implementation:

```python
if request.headers.get("HX-Request","").lower() == "true":
    # ...existing HTMX path-aware logic using _is_row_swap_target...
elif request.method == "GET" and "text/html" in request.headers.get("accept", ""):
    return templates.TemplateResponse(
        request, "page_error.html.j2",
        {"status_code": 400, "detail": f"Invalid input in {field}: {msg}"},
        status_code=400,
    )
else:
    return await request_validation_exception_handler(request, exc)  # 422 JSON
```

**Also applied to `_handle_http_exc`:** the existing handlers currently instantiate fresh `Jinja2Templates(directory=str(app.state.templates_dir))` per call inside the handler body. Phase 3c migrates these to `request.app.state.templates` alongside the route-level refactor — one startup-built instance, zero per-request directory scans. This is part of the "single source of truth" goal, not separate.

### 3.4 `/journal?period=...` — `Literal` type annotation

```python
from typing import Literal

@router.get("/journal", response_class=HTMLResponse)
def journal_page(
    request: Request,
    period: Literal["month","quarter","year","all"] = Query("month"),
):
    ...
```

FastAPI auto-generates `RequestValidationError` for out-of-set values. No route-level try/except.

## 4. Data flow

### 4.1 CSV upload

1. User clicks `<input type="file">` on `/pipeline`; picks `finviz19Apr2026.csv`.
2. HTMX submits `POST /pipeline/csv-upload` (multipart, `HX-Request: true`, OriginGuard passes).
3. Route writes upload to a `tempfile.NamedTemporaryFile(dir=cfg.paths.finviz_inbox_dir, suffix=".csv", delete=False)`. **Same-filesystem requirement:** temp file MUST live in the same directory as the final destination so the subsequent `os.replace` is an atomic rename (not a cross-device copy). On Windows with user drives and cloud-sync paths, temp files in `$TMP` can end up on a different volume from the inbox; creating the temp file in the inbox directory itself avoids `OSError: [Errno 18] Invalid cross-device link`.
4. Route calls `validate_csv(tmp_path)` → `ValidationResult(ok, rows, reasons)`.
5. On ok: `os.replace(tmp_path, cfg.paths.finviz_inbox_dir / sanitize(filename))`. `os.replace` is atomic and cross-platform — unlike `shutil.move`, it reliably overwrites an existing destination file on Windows. Response: 200 `csv_upload_form.html.j2` with `uploaded_banner={name, rows}` context.
6. On invalid: tmp file unlinked. Response: 400 `csv_upload_error.html.j2` with `reasons=validation.reasons`.

**Filename sanitization:** strip path separators, strip `..`, enforce `.csv` extension, normalize to lowercase. Reject if the sanitized name is empty or not matching `[A-Za-z0-9][A-Za-z0-9_.-]*\.csv`. Reject filename renders as 400 fragment.

### 4.2 Force-clear 2-step

1. `/pipeline` renders `stale_run_card.html.j2` inline when `find_active_run(conn)` returns a run and `is_stale_eligible(run, cfg)` returns True (both heartbeat AND step-progress stale per spec §5.6).
2. User clicks Force-clear button → `GET /pipeline/force-clear/{run.id}/confirm` with `hx-target="closest section[id^='stale-run-']"` `outerHTML`.
3. Route re-checks stale-eligibility (guards against TOCTOU). If still eligible: renders `force_clear_confirm.html.j2`. Else: `HTTPException(404, detail="Run #N is no longer stale-eligible — refresh the page")`.
4. User clicks Confirm → `POST /pipeline/force-clear/{run.id}` with `hx-target=` same + `hx-headers HX-Request`.
5. Route re-checks stale-eligibility. If still eligible: `force_clear(conn, run_id=run.id, reason="dashboard force clear", bypass_staleness_check=False)`. Returns success fragment (a `<section id="stale-run-{id}">` containing a transient banner + Run-pipeline button).
6. User clicks Cancel instead → `GET /pipeline/stale-run-card/{run.id}` → returns original `stale_run_card.html.j2` (reverts the swap).

**Note on re-check:** both the GET confirm and the POST re-verify eligibility because the user or CLI could have cleared the run between page render and button click. Existing `force_clear()` itself validates state (raises `ValueError` if run is not running); the route's pre-check just ensures the user gets a clean UX message rather than a generic 400.

### 4.3 Malformed query param recovery

Three cases, already enumerated in §3.3's dispatch table:

- **HTMX GET on non-trade route with bad `period`:** `_handle_validation_error` → `http_error_fragment.html.j2` (`<div>`), 400. HX-Target is absent or non-row → the `<div>` path is taken.
- **Non-HTMX GET (address-bar typo):** new third branch → `page_error.html.j2` (full page), 400, readable HTML.
- **API client POST with missing form field:** unchanged, FastAPI default 422 JSON.

### 4.4 Atomic stop-adjust (Phase 2 carve-out)

**Before (current):**
```python
# swing/data/repos/trades.py::update_stop_with_event
conn.execute(
    "UPDATE trades SET current_stop = ? WHERE id = ?",
    (new_stop, trade_id),
)
# always appends event; no guard on status
conn.execute("INSERT INTO trade_events ...")
```

**After (Phase 3c):**
```python
cur = conn.execute(
    "UPDATE trades SET current_stop = ? WHERE id = ? AND status = 'open'",
    (new_stop, trade_id),
)
if cur.rowcount == 0:
    raise ValueError(f"Trade #{trade_id} is not open or does not exist")
conn.execute("INSERT INTO trade_events ...")
```

The web route's existing `except ValueError → HTTPException(404)` branch catches this uniformly — both "missing trade" and "already closed" surface as a 404 fragment (HTMX) or 404 page (non-HTMX).

**No change** to `swing/trades/stop_adjust.py::adjust_stop`. The service's own `ValueError` raise path for missing trades continues to work; this change simply adds the closed-trade case to the repo-layer guarantee.

**Scope limit of this fix:** the `AND status = 'open'` guard closes the specific close-then-stop-adjust race. **Concurrent stop-adjust-vs-stop-adjust** remains out of scope: two parallel requests that both read `current_stop = X` then both call `update_stop_with_event` will commit sequentially with SQLite's write lock, but the second write's event row will claim it adjusted from X → Y' while actually adjusting from Y → Y' (lost-update on the intermediate value). A proper fix requires either an optimistic-concurrency version column or serialized transactional read-modify-write, both outside 3c's scope. For a single-operator desktop app with UI-mediated two-step clicks, this race is vanishingly rare; a future phase can address it if the usage pattern changes.

### 4.5 HX-Target handler heuristic

All endpoints that participate in the `<tr>` vs `<div>` decision:

| Endpoint | Expected `HX-Target` value | Fragment shape |
|---|---|---|
| `POST /trades/entry` | `entry-form-<ticker>` | `<tr>` |
| `POST /trades/{id}/exit` | `open-position-<id>` | `<tr>` |
| `POST /trades/{id}/stop` | `open-position-<id>` | `<tr>` |
| `GET /trades/{id}/exit/form` | `open-position-<id>` | `<tr>` |
| `GET /trades/{id}/stop/form` | `open-position-<id>` | `<tr>` |
| `GET /trades/entry/form` | `watchlist-row-<ticker>` (via 3c id addition) | `<tr>` |
| `GET /trades/entry/sizing-hint` | `sizing-hint` | `<div>` |
| `POST /pipeline/csv-upload` | `csv-upload-section` | `<div>` |
| `GET/POST /pipeline/force-clear/*` | `stale-run-<id>` | `<div>` |
| Browser address-bar GET | (none — no HX-Request) | full page |

Row-prefix whitelist: `("open-position-", "entry-form-", "exit-form-", "stop-form-", "watchlist-row-")`. Anything else with HX-Request gets `<div>`. Anything without HX-Request on GET that accepts HTML gets the full page; GETs that don't accept HTML (API clients) fall through to FastAPI's default 422 JSON.

## 5. Error handling

| Error class | Source | Status | Rendered as |
|---|---|---|---|
| CSV validation failure (schema, size) | `validate_csv` + route | 400 | `csv_upload_error.html.j2` |
| Invalid filename (path traversal, bad extension) | route | 400 | `csv_upload_error.html.j2` |
| Force-clear on non-stale run | route re-check | 404 | HX-Target-aware fragment or page |
| Force-clear post-write state still `running` | route post-check | 409 | HX-Target-aware fragment ("state conflict — refresh") |
| CSV upload oversized (Content-Length > limit) | MaxBodySizeMiddleware | 413 | `csv_upload_error.html.j2` |
| CSV upload oversized (chunked-transfer, detected post-parse) | route safety-net | 413 | `csv_upload_error.html.j2` |
| `period` not in `Literal[...]` | FastAPI validation | 400 | Path per §3.3 dispatch table |
| `update_stop_with_event` rowcount=0 | Phase 2 repo | ValueError → 404 | Existing stop-adjust route `except ValueError` → HTTPException(404) (HX-Target-aware) |
| Unhandled | Anywhere | 500 | 3a's `error_fragment.html.j2` / `error.html.j2` (no change) |

## 6. Testing

### 6.1 New tests

| File | Tests | Focus |
|---|---|---|
| `tests/web/test_routes/test_pipeline_route.py` | +8 | CSV upload happy + invalid schema + size-limit + filename-rejection + replacement-on-collision; force-clear visibility gating + GET confirm fragment + POST success + Cancel reverts |
| `tests/web/test_routes/test_journal_route.py` | +3 | HTMX bad period → `<div>` fragment; non-HTMX bad period → `page_error.html.j2` full page; happy path unchanged |
| `tests/web/test_error_handling.py` | +2 | HX-Target row-prefix routing (synthetic `/trades/*` with non-row target → `<div>`; row target → `<tr>`); non-HTMX GET query error → full page |
| `tests/data/test_repos_trades.py` | +2 | `update_stop_with_event` on closed trade → `ValueError`, no event inserted; on missing id → `ValueError`, no event |
| `tests/web/test_app_smoke.py` | +1 | `app.state.templates` is `Jinja2Templates` instance after startup |

**Target test count:** 397 (end of 3b) + 16 = **~413 fast tests**.

### 6.2 Updated tests

Any existing test that references `_templates(request)` or the path-prefix heuristic gets updated to reference `request.app.state.templates` / `HX-Target`. Expected impact: 0–2 test tweaks (the helper is private; most tests go through the actual routes).

### 6.3 No change needed

- Phase 2's 287 fast tests (except the two new `update_stop_with_event` tests added for §4.4).
- Phase 3a's 64 web tests.
- Phase 3b's 46 web tests.

## 7. Out of scope (deferred)

- **Phase 3d:** SMA-aware advisories (`trail_ma`, `exit_close_below_ma`) + on-demand OHLCV fetch + price-cache extension. Settings editor (`/settings`). Per-run detail route (`/pipeline/runs/{run_id}`).
- **Phase 4+:** live streaming, broker integration, mobile layout, keyboard shortcuts, client-side framework, CSV drag-and-drop.
- **Always out of scope:** multi-user auth, cryptographic CSRF (per 3b §1.1).

## 8. Success criteria

- [ ] User can upload a finviz CSV from `/pipeline` without opening a terminal; the next pipeline run picks it up.
- [ ] User can force-clear a wedged run from `/pipeline`; the inline 2-step confirm requires explicit click-through.
- [ ] Address-bar typo on `/journal?period=<bad>` returns a readable HTML 400 page, not a 500.
- [ ] Concurrent close-then-stop-adjust is rejected atomically at the repo layer.
- [ ] Sizing-hint endpoint (under `/trades/*`) with a non-row `HX-Target` gets a `<div>` fragment; row-targeting endpoints continue to get `<tr>`.
- [ ] `request.app.state.templates` is the single source of truth; no route imports `_templates` from another route module.
- [ ] 413+ fast tests pass; Phase 2/3a/3b baseline coverage remains green.
- [ ] `pip install -e ".[web]" && swing db-migrate && swing web` then exercising the full CSV-upload → run → force-clear → journal-navigation flow from a browser works end-to-end.

## 9. Decisions locked

1. **Upload-only CSV flow** — save to inbox on validate, separate "Run pipeline" click. No auto-run. Preserves existing inbox-one-file convention via overwrite-on-name-collision.
2. **Inline 2-step force-clear** — matches Phase 3b soft-warn UX (same mental model, same HTMX partial-swap pattern). No modal, no browser-native confirm(). Button only rendered when run is stale-eligible (per spec §5.6 — stale `last_step_progress_ts`, not just stale heartbeat).
3. **`Literal[...]` + extended validation handler** — FastAPI-generated `RequestValidationError` feeds a 3-way dispatch: HTMX row-target → `<tr>`, HTMX else → `<div>`, non-HTMX GET → full page.
4. **One scoped Phase 2 change** — `update_stop_with_event` gains `AND status = 'open'` + rowcount guard. Documented carve-out from Phase 3b's isolation invariant; adversarial review covers both repo and web sides.
5. **`HX-Target` header inspection** replaces URL-prefix heuristic. Row-prefix whitelist is explicit: `("open-position-", "entry-form-", "exit-form-", "stop-form-", "watchlist-row-")`. Watchlist rows gain `id="watchlist-row-{{ w.ticker }}"` in 3c so HX-Target is populated when the Enter button fires.
6. **`app.state.templates`** — Jinja2Templates built once at startup; `_templates(request)` helper removed; cross-module private import eliminated; per-request directory scan eliminated.
7. **Sanitized filename handling** for CSV uploads — reject path separators, `..`, non-csv extensions, or empty names. Match regex `[A-Za-z0-9][A-Za-z0-9_.-]*\.csv`.
8. **TOCTOU-safe force-clear** — both GET confirm and POST re-check stale-eligibility; the Phase 2 `force_clear` function's own state validation remains authoritative.
9. **Non-HTMX GET query-param error** uses a new `page_error.html.j2` (full-page 400). API client POSTs unchanged (FastAPI default 422 JSON).
