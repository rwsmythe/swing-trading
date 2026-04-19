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
├── app.py                         # MODIFIED: app.state.templates; HX-Target path-aware handlers; full-page 400 branch
├── routes/
│   ├── dashboard.py               # MODIFIED: remove _templates helper; use app.state.templates
│   ├── journal.py                 # MODIFIED: period: Literal[...]; use app.state.templates
│   ├── pipeline.py                # MODIFIED: POST /pipeline/csv-upload; force-clear trio; GET /pipeline renders stale-run card when eligible; use app.state.templates
│   ├── trades.py                  # MODIFIED: use app.state.templates at all call sites
│   └── watchlist.py               # MODIFIED: use app.state.templates at all call sites
├── templates/
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
- Safety: strict OriginGuard (HX-Request required), 10MB body limit via config.
- Save upload to temp file → `validate_csv(path)` → on valid, move to `cfg.paths.finviz_inbox_dir / <sanitized-name>` (overwrite existing same-name file); on invalid, render `csv_upload_error.html.j2` with reasons.
- Response (200 success): re-rendered `csv_upload_form.html.j2` with inline success banner `"Uploaded: <name> (<N> rows). Run the pipeline when ready."`
- Response (400 invalid schema or size): `csv_upload_error.html.j2`.
- Target swap: `#csv-upload-section` `outerHTML`.

**`GET /pipeline/force-clear/{run_id}/confirm`**
- Fetches the run; if not stale-eligible → `HTTPException(404)` (handler renders as fragment or page per HX-Target).
- Else → `force_clear_confirm.html.j2`.
- Target swap: `closest section[id^='stale-run-']` `outerHTML`.

**`POST /pipeline/force-clear/{run_id}`**
- Re-verifies stale-eligibility (guards against race between GET confirm and POST).
- Calls `force_clear(conn, run_id=run_id, reason="dashboard force clear", bypass_staleness_check=False)`.
- On success: response replaces the stale-run card with a transient success banner + Run-pipeline button fragment.
- On `LeaseConflict` or not-stale: 400 fragment.

**`GET /pipeline/stale-run-card/{run_id}`**
- Returns the original `stale_run_card.html.j2` for the run (used by the Cancel button in the confirm fragment). 404 if no longer stale-eligible.

**`watchlist_row.html.j2` id addition:** the existing template `<tr>` has no `id` attribute, so HTMX omits `HX-Target` when the Enter button fires. Phase 3c adds `id="watchlist-row-{{ w.ticker }}"` to the row so `HX-Target` is populated and the row-prefix whitelist engages for any error responses from `GET /trades/entry/form`. No existing test asserts on the row id, so the change is additive.

### 3.2 Templates (new)

**`csv_upload_form.html.j2`** — single-file input form, submits to `/pipeline/csv-upload` with `hx-target="#csv-upload-section" hx-swap="outerHTML" hx-encoding="multipart/form-data" hx-headers='{"HX-Request":"true"}'`. Includes optional success banner slot.

**`csv_upload_error.html.j2`** — re-renders the upload form above a `banner-degraded` div listing validation reasons.

**`stale_run_card.html.j2`** — Expects `run: PipelineRun`. Renders the run summary (id, stale step-progress age, last step) + Force-clear button targeting `GET /pipeline/force-clear/{run.id}/confirm`.

**`force_clear_confirm.html.j2`** — banner-degraded `<section id="stale-run-{run.id}">` with "Confirm force-clear" warning copy (spec §5.6) + submit form to `POST /pipeline/force-clear/{run.id}` + Cancel button to `GET /pipeline/stale-run-card/{run.id}`.

**`page_error.html.j2`** — full-page HTML error (extends 3a base layout). Expects `status_code`, `detail`. Used for non-HTMX GET validation errors.

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

`_handle_validation_error` gains a third branch for non-HTMX GETs:
```python
if request.headers.get("HX-Request","").lower() == "true":
    # ...existing HTMX path-aware logic using _is_row_swap_target...
elif request.method == "GET":
    return templates.TemplateResponse(
        request, "page_error.html.j2",
        {"status_code": 400, "detail": f"Invalid input in {field}: {msg}"},
        status_code=400,
    )
else:
    return await request_validation_exception_handler(request, exc)  # 422 JSON
```

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
3. Route writes upload to a `tempfile.NamedTemporaryFile` under `cfg.paths.tmp_dir` (or OS default).
4. Route calls `validate_csv(tmp_path)` → `ValidationResult(ok, rows, reasons)`.
5. On ok: `shutil.move(tmp_path, cfg.paths.finviz_inbox_dir / sanitize(filename))`. If a file exists at the destination, it's overwritten. Response: 200 `csv_upload_form.html.j2` with `uploaded_banner={name, rows}` context.
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

Row-prefix whitelist: `("open-position-", "entry-form-", "exit-form-", "stop-form-")`. Anything else with HX-Request gets `<div>`. Anything without HX-Request on GET gets the full page.

## 5. Error handling

| Error class | Source | Status | Rendered as |
|---|---|---|---|
| CSV validation failure (schema, size) | `validate_csv` + route | 400 | `csv_upload_error.html.j2` |
| Invalid filename (path traversal, bad extension) | route | 400 | `csv_upload_error.html.j2` |
| Force-clear on non-stale run | route re-check | 404 | HX-Target-aware fragment or page |
| Force-clear `LeaseConflict` | Phase 2 `force_clear` | 400 | HX-Target-aware fragment |
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
