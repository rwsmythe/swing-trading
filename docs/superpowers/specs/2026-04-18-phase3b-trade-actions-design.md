# Phase 3b — Trade Actions Design

**Status:** Draft (brainstorm output — awaiting user review, then adversarial critic, then implementation plan).

**Scope:** Interactive trade-action forms on the Phase 3a dashboard: enter, exit, stop-adjust. Plus a tightening of `OriginGuardMiddleware` to require `HX-Request: true` on unsafe methods (blocks cross-origin form POSTs — see §1.1 for the explicit threat model, which is narrower than the phrase "CSRF hardening" sometimes implies). Phase 2's `swing/trades/{entry,exit,stop_adjust}.py` services are consumed read-only and unchanged.

## 1. Context and decision

Phase 2 shipped the CLI trade lifecycle (`swing trade entry|exit|stop-adjust`). Phase 3a shipped a read-only dashboard + manual pipeline run. 3b closes the last major daily-friction gap: the user should log entries, exits, and stop moves without leaving the dashboard. 3b does **not** add settings editing, force-clear, CSV upload, or SMA-aware advisories — those are deferred to later phases (see §7).

### What 3b adds

- Three inline row-swap forms (entry on watchlist rows, exit + stop-adjust on open-position rows).
- Live sizing hint on the entry form via Phase 2's `compute_shares`.
- Two-step soft-warn confirmation surface (UX prompt, not an enforcement boundary — see §1.1 threat model).
- HX-Request-required mode on OriginGuardMiddleware (unsafe methods must carry the HTMX header; Origin/Referer fallbacks are removed for POST/PUT/DELETE/PATCH). This narrows the accepted-header matrix — it does NOT add a cryptographic CSRF token layer.

### 1.1 Threat model and explicit non-goals

The dashboard binds loopback-only (`127.0.0.1`/`localhost`/`::1`) and is intended for a single operator on their own machine. What `HX-Request`-required on unsafe methods actually defends against:

| Attacker capability | 3b defends? | Why |
|---|---|---|
| Cross-origin `<form action="http://127.0.0.1:8080/trades/…">` submission from a malicious website in the operator's other browser tab | **Yes** | Plain form POSTs cannot set the `HX-Request` custom header without a CORS preflight, which the server refuses. |
| `fetch()` from a cross-origin page with custom headers | **Yes** | Preflight required; server rejects. |
| An in-browser extension or userscript running in page context that can issue requests with arbitrary headers | **No** | The extension has same-origin power; it can pass the `HX-Request` check. Mitigation is "don't install malicious extensions." |
| Local-process attacker running `curl` or a script against 127.0.0.1 | **No** | Loopback binding does not distinguish local processes; anything on the machine can hit the port. Mitigation is OS-level user account security. |
| Compromised localhost page (e.g., another local web app with XSS) | **No** | Same-origin from attacker's perspective if it can persuade the browser the origin matches. Mitigation is "don't run other web apps on 127.0.0.1:8080 or don't trust them." |

**3b is not a security boundary for a shared machine.** It raises the bar for drive-by cross-origin form attacks. A cryptographic CSRF token layer (double-submit cookie, synchronizer pattern) was considered and dismissed during brainstorm because the remaining attacker capabilities that HX-Request-only does not cover (extensions, local-process, same-origin compromise) also bypass a token layer — the token lives in the same DOM the attacker already controls. If the threat model changes (e.g., multi-user deployment, non-loopback binding), token-based CSRF must be re-evaluated before that deployment.

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
│   ├── trades.py                         (NEW) — Entry/Exit/Stop form VMs + sizing hint VM
│   └── open_positions_row.py             (NEW) — build_open_positions_row(trade, cfg, cache, executor, conn)
│                                                  → OpenPositionsRowVM. Used by /trades POST success
│                                                  handlers and by dashboard.py to render each row.
├── templates/partials/
│   ├── trade_entry_form.html.j2          (NEW)
│   ├── trade_exit_form.html.j2           (NEW)
│   ├── trade_stop_form.html.j2           (NEW)
│   ├── trade_form_error.html.j2          (NEW) — 400 error banner + preserved form fields
│   ├── soft_warn_confirm.html.j2         (NEW) — 2-step entry confirmation
│   ├── open_positions_row.html.j2        (NEW) — extracted from open_positions.html.j2; now includes
│   │                                               Exit + Adjust stop buttons per row
│   ├── watchlist_row.html.j2             (MODIFIED) — adds "Enter" button per row
│   ├── sizing_hint.html.j2               (NEW) — tiny fragment for hx-swap on price/stop edits;
│   │                                               supports "dim" guidance mode for incomplete input
│   └── http_error_fragment.html.j2       (NEW) — HTMX 4xx response body (e.g., 404 from form GETs)
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


@dataclass(frozen=True)
class OpenPositionsRowVM:
    """Inputs needed to render a single open_positions_row. Defined here (not in
    dashboard.py) because stop/exit POST success handlers need to render one row
    without rebuilding the entire DashboardVM. See §3.4 for the builder."""
    trade: Trade
    price_snapshot: PriceSnapshot | None          # from PriceCache.get_many(..., executor=...)
    advisories: tuple[AdvisorySuggestionVM, ...]  # 3a subset (no SMA rules — those defer to 3c)
    remaining_shares: int                          # initial_shares - sum(prior exits)
```

### 3.4 `build_open_positions_row` — pure row render + batched dashboard use

Two entry points: a pure render helper that accepts precomputed inputs, and a convenience wrapper for the single-row POST-success path. The dashboard continues to batch its price fetches and weather lookup (the 3a pattern); it does NOT do N+1 per-row calls.

```python
def _open_positions_row_vm(
    *, trade: Trade,
    price_snapshot: PriceSnapshot | None,
    remaining_shares: int,
    advisories: tuple[AdvisorySuggestionVM, ...],
) -> OpenPositionsRowVM:
    """Pure render-input assembler. No I/O. Used by build_dashboard in the batched path
    and by build_open_positions_row in the single-row path. This is the single source of
    truth for what data an open-positions row renders from."""


def build_open_positions_row(
    *, trade: Trade, cfg: Config, cache: PriceCache, executor,
    conn: sqlite3.Connection | None = None,
) -> OpenPositionsRowVM:
    """Convenience wrapper for the POST-success path, which needs ONE row.
    Internally: cache.get_many([trade.ticker], deadline=..., executor=...);
               list_exits_for_trade(conn, trade.id) for remaining-shares;
               compute_all_suggestions(trade, AdvisoryContext(sma10=None, sma20=None, ...))
               — same 3a limitation: MA-dependent advisory rules return None until Phase 3c.
    The function opens its own read-snapshot `with conn:` if conn is None.
    Callers that have batch context (dashboard.py) should NOT call this — they should
    use `_open_positions_row_vm` directly with their precomputed snapshots + advisories."""
```

**dashboard.py's `build_dashboard` is minimally touched.** It keeps its batched `cache.get_many(all_active_tickers, ...)` call, keeps its single AdvisoryContext construction, and keeps its one weather lookup. It calls `_open_positions_row_vm(trade, snapshot, remaining, advisories)` for each open trade in a tight Python loop (no I/O per row) and attaches the results to `DashboardVM.open_trade_last_prices` / `open_trade_advisories` — external shape unchanged.

POST-success handlers use `build_open_positions_row(trade, cfg, cache, executor)` — which DOES do one `get_many([ticker])` + one `list_exits_for_trade` + one advisory compute. That's correct for a single-row render after a mutation.

This keeps the "single source of truth" property (both paths go through `_open_positions_row_vm`) without introducing the N+1 regression the naive refactor would cause.

### 3.2 Templates

All three form partials share a common skeleton: `<form hx-post="..." hx-target="closest tr" hx-swap="outerHTML">`, required fields marked with `required`, `type="number" step="0.01" min="0"` where numeric, a Submit button, and a Cancel button (`hx-get` that returns the row in its normal non-form state).

- `trade_entry_form.html.j2` shows 8 fields (ticker readonly, entry_date, entry_price, shares with inline sizing hint, initial_stop, watchlist_entry_target readonly, rationale textarea required, notes textarea). Sizing hint is its own element with `hx-get="/trades/entry/sizing-hint"` `hx-trigger="change from:input[name=entry_price],input[name=initial_stop] delay:200ms"` `hx-include="closest form"` `hx-target="#sizing-hint"`.

- `trade_exit_form.html.j2` shows 6 fields (trade summary readonly, exit_date, exit_price, shares with max=remaining_shares, reason select, rationale textarea required, notes textarea).

- `trade_stop_form.html.j2` shows 3 fields (trade summary readonly, new_stop, rationale textarea required).

- `trade_form_error.html.j2` renders a `banner-degraded` div with the error text + the original form body (values preserved via Jinja context).

- `soft_warn_confirm.html.j2` renders a yellow-banner "Soft cap reached (N/N)" explanation + Submit anyway / Cancel buttons. Submit carries the hidden `force=true` field.

### 3.3 OriginGuardMiddleware — strict mode

`OriginGuardMiddleware` gains a `strict: bool = False` kwarg. When `strict=True`:
- Safe methods (GET/HEAD/OPTIONS) unchanged.
- Unsafe methods MUST carry `HX-Request: true`. The Origin-matches and Referer-startswith branches from 3a are removed for unsafe methods (they were never needed for GET navigation, and on POST they widened the attack surface to "can forge Origin or Referer").
- `create_app` wires `app.add_middleware(OriginGuardMiddleware, bound_host=..., bound_port=..., strict=True)`.

This change narrows the set of requests the middleware accepts; it does not add any token, session state, or cryptographic check. See §1.1 for exactly what this defends against.

## 4. Data flow

### 4.1 Endpoints

```
GET  /trades/entry/form?ticker=<T>             → trade_entry_form fragment
POST /trades/entry                             → open_positions_row + OOB (status_strip, watchlist_top5)
                                                 OR soft_warn_confirm fragment (1st submit at cap)
                                                 OR trade_form_error fragment (hard cap / duplicate / bad input)
GET  /trades/entry/sizing-hint?entry_price&initial_stop
                                               → sizing_hint fragment (tiny, no OOB). Always 200.
                                                 Missing/invalid params render a guidance fragment
                                                 rather than erroring (see §4.6).

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
5. Route calls `compute_shares(entry=entry_price, stop=initial_stop, equity=equity, max_risk_pct=cfg.risk.max_risk_pct, position_pct_cap=cfg.sizing.position_pct_cap)` → `SizingResult(shares, risk_dollars, risk_pct, notional, notional_pct, feasible, constraint)`. (Signature and return type verified in `swing/recommendations/sizing.py:16`.)
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
6. On success: rebuild `DashboardVM` via `build_dashboard(cfg=cfg, cache=cache, executor=executor)` — with warm cache this is in-memory work plus a single batched get_many (cache hits) plus one weather lookup, bounded by `price_fetch_deadline_seconds` on cold cache (§4.7). Render `open_positions_row.html.j2` for the new trade as the primary target (using `build_open_positions_row` or the `_open_positions_row_vm` data already inside the rebuilt `DashboardVM`). Emit OOB fragments directly from the rebuilt VM — the fragments render from exactly the same `StatusStripVM` / `watchlist_top5` / `flag_tags` / `watchlist_remaining_count` fields the dashboard template consumes, guaranteeing field-set parity. Exit and stop-adjust POSTs follow the same rebuild pattern but emit a narrower set of OOB fragments (exit: #status-strip only; stop: none).

### 4.4 Form POST (exit)

1. Route builds `ExitRequest` from form.
2. `record_exit(conn, req)` runs; no `--force` path exists for exits.
3. On validation error (shares > remaining, reason not in ExitReason enum, bad date): render 400 error fragment.
4. On success:
   - If `result.fully_closed`: render an empty string (or a stub `<tr style="display:none"></tr>`) as primary target so the row disappears; OOB `#status-strip` to update open_count and equity (realized P&L).
   - Else (partial): render refreshed `open_positions_row` via `build_open_positions_row(trade=<reloaded>, ...)`. The row's displayed share count is `remaining_shares` (a derived value computed inside `OpenPositionsRowVM`); `Trade.initial_shares` is the persisted entry lot and is NEVER mutated — exits are separate `TradeExit` rows and remaining shares is always `initial_shares - sum(exits.shares_closed)`.

### 4.5 Form POST (stop-adjust)

1. Route builds `StopAdjustRequest` with `force=False` (no UI bypass).
2. `adjust_stop(conn, req)` runs.
3. On `StopRegressionError`: render 400 error fragment with the CLI-`--force` hint verbatim.
4. On success: render refreshed `open_positions_row` via `build_open_positions_row` (new `current_stop`; advisories regenerate by calling `compute_all_suggestions` with the updated trade — still the 3a reduced subset with `sma10=None, sma20=None`; MA-dependent rules `suggest_trail_ma` and `suggest_exit_close_below_ma` continue to return None until Phase 3c wires on-demand SMA computation). No OOB (status_strip and watchlist unchanged by a stop-adjust).

### 4.6 Sizing-hint live recompute — tolerant fragment contract

`GET /trades/entry/sizing-hint?entry_price=<X>&initial_stop=<Y>` is a small read-only endpoint that fires as the user types, so it must tolerate incomplete/invalid input without raising. Always returns 200 with a fragment; it does NOT rely on the generic 3b/3c error handlers.

Contract:
1. Parse `entry_price` and `initial_stop` from query params. Both optional and both tolerant of blank strings.
2. If either is missing, non-numeric, ≤ 0, or `initial_stop >= entry_price` → render `sizing_hint.html.j2` in its "dim" mode with the guidance text `Enter a valid entry price and stop (stop < entry) to see sizing`. No compute_shares call.
3. Otherwise: read equity via `current_equity` + repos; call `compute_shares(entry=..., stop=..., equity=..., max_risk_pct=..., position_pct_cap=...)`; render `sizing_hint.html.j2` with `SizingResult.shares`, `.risk_dollars`, `.risk_pct` (plus `.feasible` / `.constraint` if feasible=False, to tell the user whether risk or position-cap was binding).
4. If `compute_shares` raises any unexpected exception (e.g., equity = 0), catch it, log at WARNING, and render the same "dim" guidance fragment with text `Sizing unavailable — check values`. Do NOT 500.

The route is intentionally a closed error-handling island — the tight feedback loop during editing must never produce a 400/422/500 the HTMX target would swap into the UI. This is narrower than the generic "400 HTML for malformed query params" deferred to Phase 3c (§7); only this specific endpoint gets bespoke tolerance.

HTMX fires the request via `hx-get="/trades/entry/sizing-hint" hx-trigger="change from:input[name=entry_price],input[name=initial_stop] delay:200ms" hx-include="closest form" hx-target="#sizing-hint"`, which serializes the form's price and stop inputs as query params.

Chosen `GET` rather than `POST` because the endpoint has no side effects and exposes no state-changing surface — semantically appropriate, and GET under strict OriginGuard does not need `HX-Request` (safe methods pass through). This keeps UI math server-side and matches the Phase 3a "no client-side JS beyond HTMX" principle.

### 4.7 Post-submit latency and degraded-cache behavior

Every successful POST emits a narrow set of fragments (the affected row + 0–2 OOB fragments), not a full `build_dashboard` rebuild. Cost profile:

- **Cached prices case (typical):** The user just loaded the dashboard, so `PriceCache` is warm. `cache.get_many` returns snapshots from the in-memory dict — no yfinance round-trips. Submit latency is dominated by DB writes (Phase 2's `record_entry` etc.) — sub-10ms on SQLite.
- **Cold cache case:** User's first action after a long idle. `get_many` issues yfinance fetches under the shared executor with `price_fetch_deadline_seconds` cap (6s default). Submit latency is bounded by that deadline; on timeout, `_fallback_snapshot` supplies `last_close` from DB, so the row renders with stale-marked prices rather than blocking indefinitely.
- **Degraded mode (breaker tripped):** `get_many` short-circuits to last-close without dispatching to the executor. Submit latency is DB-only; the row renders with `is_stale=True` and `source="last_close"`.

The POST handler does not block on price fetches beyond the configured deadline. The handler does not rebuild the entire dashboard on submit — only the affected row + targeted OOB fragments. This is a deliberate departure from the 3a `POST /prices/refresh` path (which DOES rebuild the full dashboard, because its explicit purpose is to refresh everything).

## 5. Error handling

| Error class | Source | HTTP status | Rendered as |
|---|---|---|---|
| Field validation (required missing, non-numeric, negative) | Starlette form parsing + route guards | 400 | `trade_form_error.html.j2` — banner above re-rendered form |
| `SoftWarnException` (1st submit) | `record_entry` | 200 | `soft_warn_confirm.html.j2` — replaces form body; hidden `force=true` primed |
| `HardCapException` | `record_entry` | 400 | Error fragment: "Hard cap ({cap}) reached. Close a position first." No UI bypass. |
| `DuplicateOpenPositionException` | `record_entry` | 400 | Error fragment: "Ticker already has an open trade (#{id})." |
| `StopRegressionError` | `adjust_stop` | 400 | Error fragment: "New stop {new} is below current {old}. Use CLI `swing trade stop-adjust ... --force` if intentional." |
| Exit shares > remaining | `record_exit` | 400 | Error fragment: "Cannot exit {shares} sh — only {remaining} remaining." |
| Trade id not found / not open (for exit/stop form GET) | DB lookup | 404 | HTMX-aware 404 fragment (see §5.2); the row's HTMX target swaps in a small "Trade #N not found or closed" fragment, not the default FastAPI JSON 404 body |
| Unhandled | Anywhere | 500 | 3a's `error_fragment.html.j2` or `error.html.j2` (no change) |

**OriginGuard violation** (unsafe method without HX-Request under strict mode) → 403 `"Missing HX-Request header (strict mode)"`. `X-Request-ID` still present (3a invariant).

### 5.2 HTMX-aware HTTPException handler (3b extension to 3a)

Phase 3a's generic exception handler (`swing/web/app.py::_handle_any`) already delegates `HTTPException` / `StarletteHTTPException` subclasses to FastAPI's default handler so route-raised 404s get the default JSON response. That is fine for API consumers but wrong for HTMX, which swaps response bodies into DOM targets — the user would see a JSON blob in the row. 3b adds one narrow override:

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
```

New template `swing/web/templates/partials/http_error_fragment.html.j2` — a small banner-degraded div with `status_code` and `detail`. The route for `GET /trades/<trade_id>/exit/form` and `GET /trades/<trade_id>/stop/form` raises `HTTPException(404, detail="Trade #N not found or not open")` on missing/closed trades; the handler turns that into the HTMX fragment automatically. Non-HTMX 404s (e.g., typing a bad URL in the address bar) still hit FastAPI's default.

This tightens — but does not replace — 3a's generic exception handler. The ordering contract: FastAPI dispatches to the most specific handler first, so `StarletteHTTPException` matches ahead of the `Exception` catch-all. Tests verify both code paths.

### 5.1 State-drift recovery

Inline forms are populated from DB state at form-GET time. Between GET and POST, another tab (or the CLI) can mutate that state: create a duplicate open trade, close the trade being edited, exit some of its shares, adjust its stop. Phase 2 services already catch most of this at write time (`record_entry` re-checks `open_count`, `record_exit` re-checks `remaining_shares`, `adjust_stop` re-reads `current_stop`). The 3b UX contract on state-drift:

1. On `DuplicateOpenPositionException` during entry POST: render `trade_form_error.html.j2` with banner `"Ticker already has an open trade (#<id>)."` Form fields stay populated but submit is disabled until user explicitly cancels (swaps row back to normal). The existing trade is visible in the dashboard's open-positions table; there is no separate /trades tab (rejected as a design decision — see §9.1).
2. On `record_exit` raising a "shares-exceeds-remaining" error: re-fetch the trade + its exits from DB, re-render the exit form with the **authoritative** remaining-shares bound (new `max="<remaining>"`) and a banner explaining the conflict. The user sees the fresh limit; their previous input is preserved but clamped.
3. On `adjust_stop` raising `StopRegressionError`: the route already re-reads `current_stop` inside the service, so the error message carries both the attempted `new_stop` and the actual `current_stop`. Re-render the stop form with the updated `current_stop` prefilled (not the user's attempted value) and the rationale preserved.
4. On form GET discovering the trade is closed or missing: return a 404 fragment that replaces the row. A Phase 3c polling mechanism could notice this proactively; 3b accepts that the user sees "trade not found" only after clicking an action button.

These contracts are each tested individually (see §6.1). None of them depend on optimistic-concurrency tokens or timestamp-based `If-Match` headers — the Phase 2 services already own the authoritative re-read at commit time; the 3b layer just translates the service's rejection into a useful fragment.

## 6. Testing

### 6.1 New test files

| File | Tests | Focus |
|---|---|---|
| `tests/web/test_view_models/test_trades.py` | 6 | Entry VM shape (prefills, sizing hint, soft/hard cap wiring). Exit VM shape. Stop VM shape. Sizing hint recompute on different (price, stop) combinations. Equity = starting_equity when no exits/cash. `build_open_positions_row` returns the correct snapshot + advisories (3a subset with sma=None) for a given trade. |
| `tests/web/test_routes/test_trades_route.py` | 24 | GET each form returns expected fragment with ticker/trade_id context. POST entry success → row+OOB (status_strip + watchlist_top5 only, NOT full dashboard rebuild). POST entry soft-warn → confirm fragment → POST again with `force=true` → success. POST entry hard-cap → 400. POST entry duplicate → 400 with drift-recovery fragment (§5.1 case 1). POST exit full → row disappearance fragment + OOB status_strip only. POST exit partial → updated row with derived remaining-shares. POST exit shares-too-many after CLI drift → form re-rendered with updated max (§5.1 case 2). POST stop-adjust success → row (advisories regenerate with sma=None). POST stop-adjust regression → 400 with updated `current_stop` prefilled (§5.1 case 3). Form GET for a closed trade → HTMX-aware 404 fragment from §5.2 handler (not JSON). GET /trades/entry/sizing-hint happy path → fragment with numbers. GET /trades/entry/sizing-hint with missing/blank/invalid/stop-≥-entry params → 200 with "dim" guidance fragment (never 400/422/500). GET /trades/entry/sizing-hint does NOT require HX-Request (it's a safe method). POST /trades/entry without HX-Request → 403 (strict mode). HTMX 404 response is a fragment; non-HTMX 404 still uses FastAPI default. |
| `tests/web/test_trades_integration.py` | 4 | End-to-end: seed watchlist → GET entry form → POST entry → verify DB `trades` row, `watchlist` archived, dashboard VM shows open_count+1, prices in status strip came from cache hits. End-to-end soft-warn loop (GET form → POST no force → confirm fragment → POST force=true → success). End-to-end stop-adjust updates `current_stop` and advisories regenerate (still 3a subset — no MA rules fire). Cold-cache submit path: `PriceCache` empty → POST entry → row renders with `last_close` fallback and `is_stale=True`, does not hang. |

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

351 (end of 3a) + 6 VM + 24 routes + 4 integration + 2 origin-guard strict = **~387 fast tests**. All new tests exercising POST routes use `with TestClient(app) as client:` so the lifespan-managed `price_fetch_executor` exists (established 3a invariant).

## 7. Out of scope (deferred)

- **Phase 3c**: dashboard force-clear button, CSV upload on pipeline page, SMA-aware advisories (trail_ma + exit_close_below_ma rules requiring on-demand OHLCV → SMA computation), 400-with-HTML for malformed query parameters (e.g., `/journal?period=fortnight` currently 500s, should be 400).
- **Phase 3d**: `/settings` GET + POST (view/edit config).
- **Phase 4+**: live streaming quotes, broker integration, mobile layout, keyboard shortcuts, client-side framework.

## 8. Success criteria

- [ ] User can log a trade entry from the dashboard in < 30s without opening a terminal.
- [ ] Entry form displays live sizing hint that responds to price/stop edits within 200ms.
- [ ] Soft-warn cap requires two explicit submits in the normal UI flow. (Not an enforcement boundary against a scripted attacker — see §1.1; the real risk cap is the hard cap, which is not bypassable from the UI at all.)
- [ ] Hard-cap and duplicate-open and stop-regression return a 400 fragment inline; no reload.
- [ ] After submit, status-strip (equity, open_count) and affected rows (watchlist archive, open-position new/updated/removed) reflect new state without full page reload.
- [ ] Non-HTMX POST to any trade endpoint returns 403 with an `X-Request-ID` header.
- [ ] `pip install -e ".[web]" && swing db-migrate && swing web` then exercising the full entry/exit/stop flow from a browser works against a freshly-migrated DB.
- [ ] 387+ fast tests pass. Phase 2's 287 fast tests remain untouched.
- [ ] Phase 3a's 64 web tests remain green (the OriginGuard strict-mode flip is isolated behind a flag passed from `create_app`; existing tests that don't set strict mode still pass).

## 9. Decisions locked

1. **Inline row-swap forms** — not a separate /trades page; not modal dialogs.
2. **HX-Request-required** on unsafe methods — no token middleware, no double-submit cookie. The explicit threat model is §1.1; this is not "CSRF hardening" in the cryptographic sense. It blocks cross-origin form POSTs, not malicious same-origin scripts / extensions / local-process attackers.
3. **Entry form carries a live sizing hint** using Phase 2's `compute_shares` with its actual signature `compute_shares(entry, stop, equity, max_risk_pct, position_pct_cap)`.
4. **B+D validation**: HTML5 input attributes as cheap client-side guard + 2-step soft-warn UX prompt (not an enforcement boundary — see §1.1 and §8). No live field-level HTMX validation.
5. **After submit**: rebuild `DashboardVM` via `build_dashboard` (warm-cache fast path; cold-cache bounded by `price_fetch_deadline_seconds` per §4.7), then render a narrow set of fragments from the rebuilt VM: row swap + targeted OOB fragments. Entry emits `#status-strip` + `#watchlist-top5` OOBs. Exit emits `#status-strip` only. Stop-adjust emits no OOB (only the row). Fragments always render from the full, authoritative VM — no bespoke per-fragment fetch logic that could drift from the dashboard's field set.
6. **Business logic unchanged** in Phase 2; 3b is purely a form-layer addition. `Trade.initial_shares` is never mutated by exits; remaining-shares is always a derived value.
7. **No UI bypass for hard-cap, duplicate-open, stop-regression** — those remain CLI-only (`--force`) because silent bypass would undermine the invariants. State-drift recovery (§5.1) re-renders authoritative values so the user sees the conflict before clicking again.
8. **Sizing-hint endpoint is GET**, not POST — it is semantically read-only and does not need to be covered by the strict unsafe-method policy.
9. **Row-level VM builder** pair: `_open_positions_row_vm` (pure, no I/O) is the single source of truth for render inputs; `build_open_positions_row` (single-row convenience wrapper) is for POST-success handlers; `build_dashboard` stays BATCHED (one `get_many`, one weather lookup, then loops through `_open_positions_row_vm`) to avoid an N+1 regression.
10. **HTMX-aware 404 handler** (§5.2) added in 3b so form GETs on missing/closed trades render a small fragment instead of FastAPI's default JSON 404 body. Non-HTMX 404s still use FastAPI default.
11. **Sizing-hint endpoint tolerates incomplete/invalid query params** without ever returning 4xx (always 200 with either numbers or dim guidance text). This is deliberately narrower than the generic "400 HTML for malformed query params" deferred to 3c.
