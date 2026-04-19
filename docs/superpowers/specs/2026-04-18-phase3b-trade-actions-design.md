# Phase 3b — Trade Actions Design

**Status:** Draft (brainstorm output — awaiting user review, then adversarial critic, then implementation plan).

**Scope:** Interactive trade-action forms on the Phase 3a dashboard: enter, exit, stop-adjust. Plus a tightening of `OriginGuardMiddleware` to require `HX-Request: true` on unsafe methods (CSRF hardening). Phase 2's `swing/trades/{entry,exit,stop_adjust}.py` services are consumed read-only and unchanged.

## 1. Context and decision

Phase 2 shipped the CLI trade lifecycle (`swing trade entry|exit|stop-adjust`). Phase 3a shipped a read-only dashboard + manual pipeline run. 3b closes the last major daily-friction gap: the user should log entries, exits, and stop moves without leaving the dashboard. 3b does **not** add settings editing, force-clear, CSV upload, or SMA-aware advisories — those are deferred to later phases (see §7).

### What 3b adds

- Three inline row-swap forms (entry on watchlist rows, exit + stop-adjust on open-position rows).
- Live sizing hint on the entry form via Phase 2's `compute_shares`.
- Two-step soft-warn confirmation replacing the CLI `--force` flag.
- HX-Request-required mode on OriginGuardMiddleware (unsafe methods must carry the HTMX header; Origin/Referer fallbacks are removed for POST/PUT/DELETE/PATCH).

### Explicitly deferred

- **To 3c:** dashboard force-clear button, CSV upload on the pipeline page, SMA-aware advisories (trail_ma / exit_close_below_ma), 400-with-HTML for malformed query parameters.
- **To 3d:** settings editor (/settings GET + POST).
- **Always out of scope:** mobile-optimized layout, keyboard shortcuts, client-side validation frameworks, live streaming quotes, broker integration.

## 2. Architecture

### 2.1 Layering

- **Routes** (`swing/web/routes/trades.py`) are thin handlers: read `request.app.state.{cfg, cfg_path, price_cache, price_fetch_executor}`, load the relevant Phase 2 service, build a VM, render a template fragment. No business logic.
- **View-models** (`swing/web/view_models/trades.py`) carry pre-computed sizing hints, live-price snapshots, existing-trade context. Frozen dataclasses.
- **Templates** (`swing/web/templates/partials/`) are pure Jinja with HTMX attributes. No business logic.
- **Business logic stays in Phase 2**: `record_entry`, `record_exit`, `adjust_stop` are called as-is. No new exceptions or argument shapes.

### 2.2 File layout

```
swing/web/
├── routes/
│   └── trades.py                         (NEW) — 6 endpoints: GET/POST per action
├── view_models/
│   └── trades.py                         (NEW) — Entry/Exit/Stop form VMs + sizing hint VM
├── templates/partials/
│   ├── trade_entry_form.html.j2          (NEW)
│   ├── trade_exit_form.html.j2           (NEW)
│   ├── trade_stop_form.html.j2           (NEW)
│   ├── trade_form_error.html.j2          (NEW) — 400 error banner + preserved form fields
│   ├── soft_warn_confirm.html.j2         (NEW) — 2-step entry confirmation
│   ├── open_positions_row.html.j2        (NEW) — extracted from open_positions.html.j2; now includes
│   │                                               Exit + Adjust stop buttons per row
│   ├── watchlist_row.html.j2             (MODIFIED) — adds "Enter" button per row
│   └── sizing_hint.html.j2               (NEW) — tiny fragment for hx-swap on price/stop edits
└── middleware/
    └── origin_guard.py                   (MODIFIED) — adds strict=True kwarg
```

- `open_positions.html.j2` (Phase 3a) is refactored to iterate and `{% include "partials/open_positions_row.html.j2" %}`. The new row partial adds the two action buttons. POST /trades/.../exit and POST /trades/.../stop responses render a fresh row via the same partial, ensuring one source of truth.

### 2.3 Dependencies (read-only)

- `swing/trades/entry.py::record_entry, EntryRequest, SoftWarnException, HardCapException, DuplicateOpenPositionException`
- `swing/trades/exit.py::record_exit, ExitRequest, ExitReason`
- `swing/trades/stop_adjust.py::adjust_stop, StopAdjustRequest, StopRegressionError`
- `swing/recommendations/sizing.py::compute_shares`
- `swing/trades/equity.py::current_equity`
- `swing/data/repos/trades.py::list_open_trades, list_all_exits, get_trade`
- `swing/data/repos/watchlist.py::list_active_watchlist`
- `swing/data/repos/cash.py::list_cash`
- `swing/web/price_cache.py::PriceCache.get_many`
- `swing/web/view_models/dashboard.py::build_dashboard` (for rebuilding OOB fragments on submit)

## 3. Components

### 3.1 View-models

```python
@dataclass(frozen=True)
class TradeEntryFormVM:
    ticker: str
    entry_date: str               # today, ISO
    entry_price: float            # live-price prefill
    initial_stop: float           # from watchlist_initial_stop if present, else 0.0
    watchlist_entry_target: float | None
    watchlist_initial_stop: float | None
    suggested_shares: int         # compute_shares output
    risk_dollars: float           # suggested_shares × (entry_price - initial_stop)
    risk_pct: float               # risk_dollars / equity
    soft_warn_threshold: int
    hard_cap: int
    open_count: int
    force: bool = False           # carried in hidden field on 2-step submit


@dataclass(frozen=True)
class TradeExitFormVM:
    trade: Trade
    exit_date: str                # today, ISO
    exit_price: float             # live-price prefill
    remaining_shares: int         # initial_shares - sum(exits)
    reasons: tuple[str, ...]      # ExitReason values


@dataclass(frozen=True)
class TradeStopFormVM:
    trade: Trade
    current_stop: float
    suggested_stops: tuple[tuple[str, float], ...]  # e.g., ((‘10MA’, 912.0), (‘breakeven’, 900.0))
                                                     # populated only when advisory data is available
                                                     # for 3b, suggested_stops is always () — placeholder
                                                     # for the Phase 3c SMA-aware advisory hook
```

### 3.2 Templates

All three form partials share a common skeleton: `<form hx-post="..." hx-target="closest tr" hx-swap="outerHTML">`, required fields marked with `required`, `type="number" step="0.01" min="0"` where numeric, a Submit button, and a Cancel button (`hx-get` that returns the row in its normal non-form state).

- `trade_entry_form.html.j2` shows 8 fields (ticker readonly, entry_date, entry_price, shares with inline sizing hint, initial_stop, watchlist_entry_target readonly, rationale textarea required, notes textarea). Sizing hint is its own element with `hx-post="/trades/entry/sizing-hint"` `hx-trigger="change from:input[name=entry_price],input[name=initial_stop] delay:200ms"` `hx-target="#sizing-hint"`.

- `trade_exit_form.html.j2` shows 6 fields (trade summary readonly, exit_date, exit_price, shares with max=remaining_shares, reason select, rationale textarea required, notes textarea).

- `trade_stop_form.html.j2` shows 3 fields (trade summary readonly, new_stop, rationale textarea required).

- `trade_form_error.html.j2` renders a `banner-degraded` div with the error text + the original form body (values preserved via Jinja context).

- `soft_warn_confirm.html.j2` renders a yellow-banner "Soft cap reached (N/N)" explanation + Submit anyway / Cancel buttons. Submit carries the hidden `force=true` field.

### 3.3 OriginGuardMiddleware — strict mode

`OriginGuardMiddleware` gains a `strict: bool = False` kwarg. When `strict=True`:
- Safe methods (GET/HEAD/OPTIONS) unchanged.
- Unsafe methods MUST carry `HX-Request: true`. The Origin-matches and Referer-startswith branches from 3a are removed for unsafe methods (they remain the only auth for GET navigation, which is fine because GET has no side effects).
- `create_app` wires `app.add_middleware(OriginGuardMiddleware, bound_host=..., bound_port=..., strict=True)`.

## 4. Data flow

### 4.1 Endpoints

```
GET  /trades/entry/form?ticker=<T>             → trade_entry_form fragment
POST /trades/entry                             → open_positions_row + OOB (status_strip, watchlist_top5)
                                                 OR soft_warn_confirm fragment (1st submit at cap)
                                                 OR trade_form_error fragment (hard cap / duplicate / bad input)
POST /trades/entry/sizing-hint                 → sizing_hint fragment (tiny, no OOB)

GET  /trades/<trade_id>/exit/form              → trade_exit_form fragment
POST /trades/<trade_id>/exit                   → open_positions_row (or empty if fully closed) + OOB (status_strip)
                                                 OR trade_form_error fragment

GET  /trades/<trade_id>/stop/form              → trade_stop_form fragment
POST /trades/<trade_id>/stop                   → open_positions_row (new current_stop; advisories regenerate inline)
                                                 OR trade_form_error fragment
```

### 4.2 Form GET (entry example)

1. HTMX fires `GET /trades/entry/form?ticker=AAPL` from a watchlist row's "Enter" button.
2. Route reads `request.app.state.{cfg, price_cache, price_fetch_executor}`.
3. Route opens a read-snapshot DB connection (`with conn:`) and calls:
   - `list_active_watchlist(conn)` → find row with ticker=AAPL → `entry_target`, `initial_stop_target`.
   - `list_open_trades(conn)` → `open_count`.
   - `list_all_exits(conn)` + `list_cash(conn)` → `current_equity(...)`.
4. Route fetches live price: `cache.get_many(["AAPL"], deadline_seconds=cfg.web.price_fetch_deadline_seconds, executor=executor)`.
5. Route calls `compute_shares(risk_dollars=equity × cfg.risk.max_risk_pct, entry_price=..., initial_stop=..., cfg.sizing)` → `suggested_shares`.
6. Builds `TradeEntryFormVM`, renders `trade_entry_form.html.j2`.

### 4.3 Form POST (entry with soft-warn flow)

1. HTMX submits the form → `POST /trades/entry` with form fields.
2. Route builds `EntryRequest` from form data. Required fields that pass HTML5 validation are trusted to be present (route still guards against empty strings); missing field → 400 error fragment.
3. Route opens a DB connection and calls:
   ```python
   record_entry(conn, req,
                soft_warn=cfg.position_limits.soft_warn_open,
                hard_cap=cfg.position_limits.hard_cap_open,
                force=(form.get("force") == "true"))
   ```
4. On `SoftWarnException`: if `force` was missing/false, render `soft_warn_confirm.html.j2` with the submitted form values re-serialized in a hidden block plus `<input type="hidden" name="force" value="true">`. The user clicks "Submit anyway" → a fresh POST with `force=true` → route retries and on `SoftWarnException` now bypasses (Phase 2 behavior).
5. On `HardCapException` / `DuplicateOpenPositionException`: render `trade_form_error.html.j2` with the Phase 2 error message prepended above the re-rendered form.
6. On success: rebuild `DashboardVM` via `build_dashboard(cfg=cfg, cache=cache, executor=executor)`. Render `open_positions_row.html.j2` for the new trade as the primary target; emit OOB fragments for `#status-strip` and `#watchlist-top5` using the rebuilt VM.

### 4.4 Form POST (exit)

1. Route builds `ExitRequest` from form.
2. `record_exit(conn, req)` runs; no `--force` path exists for exits.
3. On validation error (shares > remaining, reason not in ExitReason enum, bad date): render 400 error fragment.
4. On success:
   - If `result.fully_closed`: render an empty string (or a stub `<tr style="display:none"></tr>`) as primary target so the row disappears; OOB `#status-strip` to update open_count.
   - Else: render refreshed `open_positions_row` (with updated `initial_shares` computed from `remaining_shares`).

### 4.5 Form POST (stop-adjust)

1. Route builds `StopAdjustRequest` with `force=False` (no UI bypass).
2. `adjust_stop(conn, req)` runs.
3. On `StopRegressionError`: render 400 error fragment with the CLI-`--force` hint verbatim.
4. On success: render refreshed `open_positions_row` (new `current_stop`; advisories in the row's advisory column regenerate from the updated stop). No OOB (status_strip and watchlist unchanged).

### 4.6 Sizing-hint live recompute

`POST /trades/entry/sizing-hint` is a small endpoint that:
1. Reads `entry_price`, `initial_stop` from form data.
2. Reads equity the same way as the form GET (via `current_equity` + repos).
3. Calls `compute_shares(...)`.
4. Returns just the `sizing_hint.html.j2` fragment (inline `<span>` with the new numbers).

This keeps UI math server-side and matches the Phase 3a "no client-side JS beyond HTMX" principle.

## 5. Error handling

| Error class | Source | HTTP status | Rendered as |
|---|---|---|---|
| Field validation (required missing, non-numeric, negative) | Starlette form parsing + route guards | 400 | `trade_form_error.html.j2` — banner above re-rendered form |
| `SoftWarnException` (1st submit) | `record_entry` | 200 | `soft_warn_confirm.html.j2` — replaces form body; hidden `force=true` primed |
| `HardCapException` | `record_entry` | 400 | Error fragment: "Hard cap ({cap}) reached. Close a position first." No UI bypass. |
| `DuplicateOpenPositionException` | `record_entry` | 400 | Error fragment: "Ticker already has an open trade (#{id})." |
| `StopRegressionError` | `adjust_stop` | 400 | Error fragment: "New stop {new} is below current {old}. Use CLI `swing trade stop-adjust ... --force` if intentional." |
| Exit shares > remaining | `record_exit` | 400 | Error fragment: "Cannot exit {shares} sh — only {remaining} remaining." |
| Trade id not found / not open (for exit/stop form GET) | DB lookup | 404 | 3a's 404 handler (the row's HTMX target swaps in the 404 fragment) |
| Unhandled | Anywhere | 500 | 3a's `error_fragment.html.j2` or `error.html.j2` (no change) |

**OriginGuard violation** (unsafe method without HX-Request under strict mode) → 403 `"Missing HX-Request header (strict mode)"`. `X-Request-ID` still present (3a invariant).

## 6. Testing

### 6.1 New test files

| File | Tests | Focus |
|---|---|---|
| `tests/web/test_view_models/test_trades.py` | 5 | Entry VM shape (prefills, sizing hint, soft/hard cap wiring). Exit VM shape. Stop VM shape. Sizing hint recompute on different (price, stop) combinations. Equity = starting_equity when no exits/cash. |
| `tests/web/test_routes/test_trades_route.py` | 18 | GET each form returns expected fragment with ticker/trade_id context. POST entry success → row+OOB. POST entry soft-warn → confirm fragment → POST again with `force=true` → success. POST entry hard-cap → 400. POST entry duplicate → 400. POST exit full → row disappearance fragment + OOB. POST exit partial → updated row. POST exit shares-too-many → 400. POST stop-adjust success → row. POST stop-adjust regression → 400 with CLI hint. POST /trades/entry/sizing-hint → fragment with updated numbers. POST /trades/entry without HX-Request → 403 (strict mode). |
| `tests/web/test_trades_integration.py` | 3 | End-to-end: seed watchlist → GET entry form → POST entry → verify DB `trades` row, `watchlist` archived, dashboard VM shows open_count+1. End-to-end soft-warn loop. End-to-end stop-adjust updates `current_stop` and advisories regenerate. |

### 6.2 Updated tests

**`tests/web/test_origin_guard.py`**: parameterize the fixture to take `strict: bool`. Add 2 new tests:
- `test_post_strict_requires_hx_request` — POST with Origin matching bound host but no `HX-Request` → 403 under strict mode. Same request → 200 under non-strict.
- `test_post_strict_rejects_referer_only` — POST with Referer matching bound host but no `HX-Request` → 403 under strict mode.

Existing non-strict tests stay; they document the 3a behavior of the middleware (still supported for consumers who don't want strict).

### 6.3 No change needed

- `test_phase2_regression.py`: 3b only touches `swing/web/*`; Phase 2 isolation is unchanged.
- `test_error_handling.py::test_403_cross_origin_post_still_carries_request_id`: Origin:evil with no HX-Request → blocked in both modes.
- `test_htmx_post_error_returns_error_fragment`: already sends `HX-Request: true`.
- `test_post_pipeline_run_*`, `test_post_prices_refresh_*`: already send `HX-Request: true`.

### 6.4 Target test count

351 (end of 3a) + 5 VM + 18 routes + 3 integration + 2 origin-guard strict = **~379 fast tests**. The 2 origin-guard additions and the 18 route tests include `with TestClient(app) as client:` on any POST route test (existing invariant).

## 7. Out of scope (deferred)

- **Phase 3c**: dashboard force-clear button, CSV upload on pipeline page, SMA-aware advisories (trail_ma + exit_close_below_ma rules requiring on-demand OHLCV → SMA computation), 400-with-HTML for malformed query parameters (e.g., `/journal?period=fortnight` currently 500s, should be 400).
- **Phase 3d**: `/settings` GET + POST (view/edit config).
- **Phase 4+**: live streaming quotes, broker integration, mobile layout, keyboard shortcuts, client-side framework.

## 8. Success criteria

- [ ] User can log a trade entry from the dashboard in < 30s without opening a terminal.
- [ ] Entry form displays live sizing hint that responds to price/stop edits within 200ms.
- [ ] Soft-warn cap requires two explicit submits; single-submit bypass is impossible from the UI.
- [ ] Hard-cap and duplicate-open and stop-regression return a 400 fragment inline; no reload.
- [ ] After submit, status-strip (equity, open_count) and affected rows (watchlist archive, open-position new/updated/removed) reflect new state without full page reload.
- [ ] Non-HTMX POST to any trade endpoint returns 403 with an `X-Request-ID` header.
- [ ] `pip install -e ".[web]" && swing db-migrate && swing web` then exercising the full entry/exit/stop flow from a browser works against a freshly-migrated DB.
- [ ] 379+ fast tests pass. Phase 2's 287 fast tests remain untouched.
- [ ] Phase 3a's 64 web tests remain green (the OriginGuard strict-mode flip is isolated behind a flag passed from `create_app`; existing tests that don't set strict mode still pass).

## 9. Decisions locked

1. **Inline row-swap forms** — not a separate /trades page; not modal dialogs.
2. **HX-Request-required** on unsafe methods — no token middleware, no double-submit cookie.
3. **Entry form carries a live sizing hint** using Phase 2's `compute_shares`.
4. **B+D validation**: HTML5 input attributes as cheap client-side guard + 2-step soft-warn confirmation. No live field-level HTMX validation.
5. **After submit**: row swap + OOB fragments — matches the `/prices/refresh` pattern already shipped in 3a.
6. **Business logic unchanged** in Phase 2; 3b is purely a form-layer addition.
7. **No UI bypass for hard-cap, duplicate-open, stop-regression** — those remain CLI-only (`--force`) because silent bypass would undermine the invariants.
