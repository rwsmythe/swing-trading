# Phase 14 Sub-bundle 5.5 (Schwab) — Web Market-Data Ladder + Checker Resilience Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking. **CLI in the worktree: `python -m swing.cli` (NOT bare `swing`).**

**Goal:** Two infrastructure items on the Schwab integration surface, on **schwabdev 2.5.1**: **A-3** installs the EXISTING production-gated market-data ladder onto the long-lived `swing web` caches at FULL PARITY (daily bars + SMA + last-close quote), bounded by the rate-limit-aware **L9** gates; **P14.N7** wraps the schwabdev background `checker` token-refresh thread with exception-isolation + bounded backoff and surfaces checker-liveness through an ephemeral cross-process sidecar read by BOTH `swing schwab status` (CLI) AND a new web health badge (operator-re-ruled OQ-6).

**Architecture:** REUSE, do not re-implement. A-3 mirrors `swing/pipeline/runner.py:_install_pipeline_marketdata_caches` (NOT `_build_caches_with_ladder` — that name does not exist) by constructing a web Schwab client via the EXISTING `construct_authenticated_client` factory and installing the EXISTING `set_ladder_fetcher` / `set_ladder_bars_fetcher` hooks on the web `PriceCache` / `OhlcvCache`, with the L9 open-trade-scope + provider_tag-driven cooldown gates living inside the new hook closures (the part A-3 writes anyway), all guarded by a `threading.Lock`. P14.N7 replaces the bound `client.tokens.update_tokens` on the one web client instance with a resilient wrapper; the liveness record is written to an ephemeral JSON sidecar (atomic `os.replace`), evaluated by ONE shared 6-step state machine consumed by both the CLI line and the web badge (no forked logic). **NO schema change** (v23 held); the sidecar is ephemeral; the audit `surface` reuses `'pipeline'`. **ZERO new `schwabdev.Client.*` call sites** (L2 stays green by construction; no re-anchor in SB5.5). P14.N7 is a cleanly-removable guard (the Phase-15 v3 upgrade deletes the checker).

**Tech Stack:** Python 3.14, FastAPI + Starlette 1.0, Jinja2, schwabdev 2.5.1, sqlite3, `threading`, `importlib.metadata`, pytest (`-m "not slow"`), ruff. CLI in worktree: `python -m swing.cli`.

---

## §A Goals / Non-goals

### §A.1 Goals (in scope)
1. **A-3 web ladder install (full parity).** A new `_install_web_marketdata_caches(cfg, price_cache, ohlcv_cache) -> client|None` in `swing/web/app.py`, invoked right after the plain caches are constructed (`app.py:188-189`), that constructs the web Schwab client via the graceful-degradation factory and installs BOTH ladder hooks (quote + daily-bars) on the web caches. Holds the client at `app.state.schwab_client` (None when no ladder).
2. **L9 rate-limit-aware gates (the governing runtime driver).** Inside the hook closures: an **open-trade fetch scope** (Schwab attempted only for open-trade tickers; render-storm defense) + a **provider_tag-driven consecutive-fallback cooldown** (reusing `cfg.web.circuit_breaker_cooldown_seconds`), all shared hook state guarded by a `threading.Lock`. NEVER a hammering retry; the TTL caches are the primary natural backoff.
3. **L9c `rate_limit_remaining` observability — header-name CONFIRMATION (OQ-10).** A redaction-safe header-KEY capture diagnostic so the actual Schwab rate-limit header name (if any) is empirically confirmed at the production smoke; the extractor name-addition lands BEHIND the confirmed name. NO guessed name that silently stays `None`.
4. **P14.N7 resilient checker wrap.** A new `swing/integrations/schwab/checker_resilience.py`: an instance-level wrapper around `client.tokens.update_tokens` (exception-isolation + bounded backoff; forced calls pass through and re-raise; post-call token-state verification), installed on the web client. Cleanly removable.
5. **Cross-process liveness sidecar (OQ-5/OQ-9).** An ephemeral `~/swing-data/schwab-checker-liveness.{env}.json` written atomically; ONE shared 6-step state machine; the seed call does NOT advance the daemon heartbeat.
6. **CLI surface.** A "Checker liveness" line in `swing schwab status` (`cli_schwab.py:render_status`), ASCII-only.
7. **Web health badge (OQ-6 re-ruled, V1).** A small alive/stale/degraded badge in the shared `base.html.j2` topbar, reading the SAME sidecar via the SAME state machine through a shared helper; a new `schwab_checker_badge` field with a safe default on EVERY base-layout VM.
8. **Operator-witnessed gate** with a NEW browser leg (S6) for the badge.
9. **Phase 14 close-out tail position note** — SB5.5 is the FIRST close-out-tail item.

### §A.2 Non-goals (OUT of scope — do NOT plan/implement)
- ANY new `schwabdev.Client.*` call site / new client-construction path / new market-data fetcher / new ladder (L2 / L5). A-3 REUSES `construct_authenticated_client` + the existing ladder; P14.N7 WRAPS the existing `update_tokens`.
- ANY swing schema change / migration / `EXPECTED_SCHEMA_VERSION` bump / a `'web'` `surface` enum value (L3) — reuse `surface='pipeline'` (`pipeline_run_id=NULL`); the sidecar is an ephemeral file.
- The schwabdev v2.5.1 → 3.0.5 upgrade (Phase 15). Do NOT install or assume v3.
- An app-wide cross-process rate-limit governor (V2, §4.5.3 of spec).
- A persisted checker-health history DB table (V2).
- Generalizing the resilient wrap to the pipeline / CLI clients (V2).
- The Phase 14 close-out polish batch / A-6 / B-7 / `market_weather` 200MA / vcp crowding / `_bulz_*` rename.
- Constructing a `schwabdev.Client` in ANY test (it spawns a checker daemon + needs creds/network) — the version guard uses `importlib.metadata.version`.

---

## §B File map

All paths relative to repo root. **(N)** = new, **(M)** = modify, **(R)** = reuse read-only.

### §B.1 Production
| File | Disp | Responsibility |
|------|------|----------------|
| `swing/web/app.py` | **(M)** | Add `_construct_web_schwab_client(cfg)` (graceful degradation; gated on `_is_ladder_active` + creds) + `_install_web_marketdata_caches(cfg, price_cache, ohlcv_cache)` + the `_WebLadderState` L9 gate object + the quote/bars hook factories. Invoke the installer right after `app.py:188-189`; hold the client at `app.state.schwab_client` (default `None`). Install the P14.N7 resilient wrap + seed on the constructed client. |
| `swing/integrations/schwab/checker_resilience.py` | **(N)** | P14.N7: `CheckerLiveness` record (thread-safe) + `install_resilient_checker(client, *, liveness, retries=2, backoff_base_s=1.0)` + the sidecar path/writer/reader + the shared `evaluate_liveness_state(...)` 6-step state machine + the timing constants. Single clear purpose; cleanly removable. |
| `swing/integrations/schwab/marketdata.py` | **(M)** | L9c (Slice 1b): in `_extract_response_payload`, when env is production AND no known rate-limit header matched, emit a ONCE-per-process redaction-safe DEBUG log of the response header KEY list (names only, no values) so OQ-10 is confirmable at the S7 smoke. NO guessed header name added. |
| `swing/cli_schwab.py` | **(M)** | In `render_status` (`:790`): append a "Checker liveness" line read from the sidecar via `evaluate_liveness_state`. ASCII-only (cp1252 stdout). `schwab_status` (`:1426`) stays READ-ONLY (no Client construction). |
| `swing/web/view_models/schwab_checker_badge.py` | **(N)** | `SchwabCheckerBadgeVM` (ASCII fields) + `build_schwab_checker_badge(cfg) -> SchwabCheckerBadgeVM | None` (reads the SAME sidecar via the SAME state machine; `None` when sidecar absent → badge hidden). The shared helper (no forked liveness logic). |
| `swing/web/view_models/metrics/shared.py` | **(M)** | Add `schwab_checker_badge: SchwabCheckerBadgeVM | None = None` to `BaseLayoutVM` (covers Family A — ~11 metrics/account/exemplar VMs in ONE edit). |
| `swing/web/view_models/dashboard.py` | **(M)** | Add `schwab_checker_badge` field (safe default) to `DashboardVM`; populate via the helper in `build_dashboard`. |
| `swing/web/view_models/pipeline.py` | **(M)** | Field on `PipelineVM`; populate in `build_pipeline`. |
| `swing/web/view_models/journal.py` | **(M)** | Field on `JournalVM` + `TradeDrilldownVM`; populate via `_base_banner_fields(conn, cfg)` (covers BOTH). |
| `swing/web/view_models/watchlist.py` | **(M)** | Field on `WatchlistVM`; populate in `build_watchlist`. |
| `swing/web/view_models/config.py` | **(M)** | Field on `ConfigPageVM`; populate in `build_config_vm`. |
| `swing/web/view_models/error.py` | **(M)** | Field on `PageErrorVM` (safe default; populated `None` — error pages need only the field to exist). |
| `swing/web/view_models/schwab.py` | **(M)** | Field on `SchwabSetupVM` + `SchwabStatusVM`; populate in their route builders. |
| `swing/web/templates/base.html.j2` | **(M)** | Render `vm.schwab_checker_badge` in the topbar (after the Config link / theme toggle). ASCII-only badge markup, linked to `/schwab/status`. |
| `swing/web/static/app.css` | **(M)** | `.schwab-health-badge` + `--ok` / `--warn` / `--info` modifier styling. |

### §B.2 Reuse (read-only — DO NOT modify)
| File | What is reused |
|------|----------------|
| `swing/pipeline/runner.py:203-302` (`_construct_pipeline_schwab_client`) + `:305-468` (`_install_pipeline_marketdata_caches`) | The mirror template. `:415-463` `_bars_hook` carries the daily-bar `(year,5,daily,1)` footgun guard + the `to_dataframe()` conversion; `:358-389` `_quote_hook`; `:249` `resolve_credentials_env_or_prompt(...allow_prompt=False)`; `:275` widened `except Exception` graceful-degradation boundary. |
| `swing/integrations/schwab/auth.py` | `construct_authenticated_client(cfg, environment, client_id, client_secret)` :694 (the SINGLE `schwabdev.Client(...)` site); `resolve_credentials_env_or_prompt(cfg, environment, *, allow_prompt=True, prompter=None)` :114; `_redacted_excerpt(exc, *, max_chars=80)` :661; `ensure_schwab_log_redaction_factory_installed` (imported :49, called inside `construct_authenticated_client`). |
| `swing/integrations/schwab/marketdata_ladder.py` | `fetch_quote_via_ladder(ticker, *, cfg, schwab_client, yfinance_fallback_fn, conn, surface, pipeline_run_id=None) -> tuple[PriceSnapshot, str]` :264; `fetch_window_via_ladder(ticker, *, start, end, cfg, schwab_client, yfinance_fallback_fn, conn, surface, pipeline_run_id=None, period_type=None, period=None, frequency_type=None, frequency=None) -> tuple[SchwabPriceHistoryWindow, str]` :358; `_is_ladder_active(cfg)` :221 (`env=='production' AND marketdata_ladder_enabled`); the ladder SWALLOWS `(SchwabAuthError, SchwabRateLimitError, SchwabApiError)` → returns `(entry, "yfinance")` at :317. Provider tags: `'schwab_api'` / `'yfinance'`. |
| `swing/web/price_cache.py` | `set_ladder_fetcher(fetcher: Callable[[str], tuple[float, str]] | None)` :75 → sets `self._ladder_fetcher`; worker invokes it at :151; breaker `_maybe_trip_breaker` :271 (`self._degraded_until`). |
| `swing/web/ohlcv_cache.py` | `set_ladder_bars_fetcher(fetcher: Callable[[str], tuple[Any, str]] | None)` :112 → sets `self._ladder_bars_fetcher`; invoked at :217 (request) and :437 (worker). `get_or_fetch(*, ticker, window_days=180)` :131 keyed `(ticker_upper, window_days)` in `_bars_store`; `get_many_bundles(...)` :260 uses `_store`. |
| `swing/web/chart_jit.py` | `get_or_render_surface(*, conn, ohlcv_cache, surface, ticker, ...)` :71 → `ohlcv_cache.get_or_fetch(ticker=ticker, window_days=200)` :117 (the arbitrary-ticker render-storm surface the scope gate defends). |
| `swing/data/repos/trades.py:375` | `list_open_trades(conn) -> list[Trade]` (the open-trade ticker source). |
| `swing/config.py` | `Web.price_cache_ttl_seconds=120` :353; `Web.ohlcv_cache_ttl_seconds=3600` :360; `Web.circuit_breaker_cooldown_seconds=60` :357; `SchwabIntegrationConfig.marketdata_ladder_enabled=True` :253. |
| `swing/config_user.py:18` | `_user_home()` (reads `USERPROFILE`/`HOME`/`Path.home()`) — the sidecar path base. |
| `swing/integrations/schwab/audit_service.py` | `_SCHWAB_API_SURFACE_VALUES=('pipeline','cli','trade_entry','trade_exit')` :48; `record_call_finish(..., rate_limit_remaining, ...)` :127. |
| `swing/data/db.py:51` | `EXPECTED_SCHEMA_VERSION = 23` (asserted unchanged). |
| `tests/integration/test_l2_lock_source_grep.py` | UNCHANGED gate: greps `schwabdev.Client.` at HEAD vs baseline `bf7e071` (Counter/multiset subset). |

### §B.3 Tests (N)
| File | Covers |
|------|--------|
| `tests/web/test_app_marketdata_ladder_wiring.py` | Slice 1: L7 production-path wiring (hooks installed under production, absent under sandbox); daily-bar kwargs; the L9 scope gate; the provider_tag cooldown gate; concurrent-miss thread-safety; cfg-tier credential resolution. |
| `tests/integration/schwab/test_marketdata_header_capture.py` | Slice 1b: the header-KEY capture diagnostic fires only when no known header matched under production; never logs header VALUES. |
| `tests/integration/schwab/test_checker_resilience.py` | Slice 2: DNS-failure survival; liveness transitions; forced-call passthrough re-raises; seed-vs-daemon origin; bounded-backoff timing; the `importlib.metadata` version guard; wrap-effectiveness. |
| `tests/integration/schwab/test_checker_liveness_state.py` | Slice 3: the shared 6-step `evaluate_liveness_state` precedence; atomic sidecar write/read; `STALE_THRESHOLD > HEARTBEAT_WRITE_INTERVAL`. |
| `tests/cli/test_schwab_status_checker_liveness.py` | Slice 3: `render_status` checker line per state; ASCII scoped to the new line. |
| `tests/web/test_schwab_checker_badge.py` | Slice 3: `build_schwab_checker_badge` per state + sidecar-absent → None; base-VM field fan-out (every base-layout VM has the field with a safe default); template render (badge present/hidden); ASCII scoped to the badge markup. |

---

## §C Surface integration

### §C.1 The shared web Schwab-client lifecycle (A-3 + P14.N7)
```
swing web (process start)
  create_app(cfg, cfg_path)                                   swing/web/app.py
    app.state.price_cache = PriceCache(cfg)                   :188 (existing, plain)
    app.state.ohlcv_cache = OhlcvCache(cfg)                   :189 (existing, plain)
    app.state.schwab_client = _install_web_marketdata_caches( :NEW
        cfg, app.state.price_cache, app.state.ohlcv_cache)
      client = _construct_web_schwab_client(cfg)
        if not _is_ladder_active(cfg):       return None   <- sandbox/disabled/tests: NO client, NO checker, NO network
        creds via resolve_credentials_env_or_prompt(allow_prompt=False)
        construct_authenticated_client(...)  (graceful-degradation except Exception -> None)
      if client is None:                     return None   <- yfinance-only web app (today's behavior)
      liveness = CheckerLiveness(env=..., sidecar_path=...)
      install_resilient_checker(client, liveness=liveness)   # P14.N7 wrap (Slice 2)
      client.tokens.update_tokens()                          # seed (Slice 2; origin='seed', NOT a heartbeat)
      state = _WebLadderState(cfg)                           # L9 gate object (threading.Lock)
      price_cache.set_ladder_fetcher(_make_web_quote_hook(cfg, client, state))
      ohlcv_cache.set_ladder_bars_fetcher(_make_web_bars_hook(cfg, client, state))
      return client
  ... server serves; ladder fires for OPEN-TRADE tickers only (L9), TTL-cached ...
  ... schwabdev daemon checker ticks every 30s; the wrap records liveness -> sidecar ...

swing schwab status (SEPARATE process)  cli_schwab.py:1426 -> render_status:790
  reads ~/swing-data/schwab-checker-liveness.{env}.json -> evaluate_liveness_state -> "Checker: ..." line

any web page render  base.html.j2 topbar
  vm.schwab_checker_badge (build_schwab_checker_badge(cfg)) -> reads the SAME sidecar via the SAME state machine
```

### §C.2 L9 design (the governing runtime driver) — verified corrections embedded
- **Open-trade fetch scope (primary render-storm defense).** Each hook consults `state.should_use_schwab(ticker)`: True iff `ticker.upper()` is in the memoized open-trade set (`list_open_trades(conn)`, refreshed at most every 60s) AND not in cooldown. False → bypass Schwab, return the yfinance fallback DIRECTLY (NO Schwab call, NO audit row). Bounds Schwab calls to a small multiple of the open-trade count regardless of render volume.
- **Provider_tag-driven cooldown (NOT a 429 catch).** The ladder swallows `SchwabRateLimitError` internally (`marketdata_ladder.py:317`) and returns `provider_tag='yfinance'` — the hook NEVER sees the 429 exception. So the hook keys its cooldown on the OBSERVED `provider_tag`: after `WEB_LADDER_FALLBACK_COOLDOWN_THRESHOLD` (=3) consecutive `provider_tag=='yfinance'` returns (Schwab attempted + fell through for ANY reason), it sets `_cooldown_until = monotonic() + cfg.web.circuit_breaker_cooldown_seconds`; while in cooldown `should_use_schwab` returns False for ALL tickers. A `'schwab_api'` success resets the counter. **Do NOT write a test expecting the hook to catch `SchwabRateLimitError`.**
- **Thread-safety (BINDING).** The hooks run concurrently from executor workers (`price_cache.py:151`, `ohlcv_cache.py:437`) AND request paths (`ohlcv_cache.py:217`). The open-trade memo, the consecutive-fallback counter, and the cooldown timestamp are shared mutable state guarded by a `threading.Lock` on `_WebLadderState`. The DB read for the open-trade set is performed OUTSIDE the lock (double-checked) to avoid holding the lock during I/O.
- **TTL caches are the primary natural backoff.** A yfinance fallback result is cached for its TTL, so the same cache key is not re-attempted against Schwab until expiry. NO retry/backoff on the market-data path (the only backoff in SB5.5 is P14.N7's checker wrap).
- **No app-wide governor in V1** (explicit residual; §4.5.3 of spec) — the per-process cooldown cannot see pipeline/CLI/checker traffic. Acceptable because the open-trade scope keeps web steady-state tiny and any 429 degrades gracefully. Banked V2.

### §C.3 L9c header-name confirmation (OQ-10) — RESOLUTION
**Finding (this plan, re-grepped):** `_extract_response_payload` (`marketdata.py:101-144`) already reads three candidate header names (`X-RateLimit-Remaining`, `X-Rate-Limit-Remaining`, `Schwab-Client-RateLimit-Remaining`) and plumbs `rate_limit_remaining` to the audit close (`:564` failure, `:643` success). **The actual Schwab rate-limit-remaining header name is NOT confirmable from any on-disk artifact:** no recorded response headers exist in any cassette; `reference/schwab-api/market-data-specification.md` documents the ~120/min budget but NO rate-limit-remaining response header. (Schwab's Trader API is widely reported to emit NO such header — only HTTP 429 on breach — so `rate_limit_remaining` resolving to `None` in production is likely because Schwab sends no header at all, not merely a name mismatch.)
**Disposition:** Slice 1b does NOT add a guessed name (that would silently stay `None` → false confidence, exactly what OQ-10 forbids). Instead it lands a redaction-safe, ONCE-per-process DEBUG log of the response header KEY list (names only, no values) when env is production AND no known header matched, so the operator EMPIRICALLY confirms the actual header name (or its absence) from the `swing web` console during the S7 production smoke. The candidate-name addition is then a trivial follow-up landed BEHIND the confirmed name. The primary L9 rate-limit defense (open-trade scope + TTL + cooldown) does not depend on `rate_limit_remaining`; it is observability-only (SHOULD-tier).

### §C.4 P14.N7 checker wrap — contract
`install_resilient_checker(client, *, liveness, retries=2, backoff_base_s=1.0)` records `startup_thread = threading.current_thread()` at install time, then replaces `client.tokens.update_tokens`:
```python
def resilient_update_tokens(force_access_token=False, force_refresh_token=False):
    if force_access_token or force_refresh_token:
        return original(force_access_token=force_access_token,
                        force_refresh_token=force_refresh_token)  # CLI/forced contract: pass through, may raise
    origin = "seed" if threading.current_thread() is startup_thread else "daemon"
    liveness.record_tick(origin)            # sets last_daemon_tick_ts ONLY for origin=='daemon'
    attempt = 0
    while True:
        try:
            refreshed = original()           # background no-force path
        except Exception as exc:             # noqa: BLE001 — ConnectionError/NameResolutionError/etc.
            liveness.record_failure(exc)     # redacted; increments consecutive_failures
            if attempt < retries:
                attempt += 1
                time.sleep(backoff_base_s * (2 ** (attempt - 1)))   # bounded backoff WITHIN this cycle
                continue
            return False                     # give up THIS cycle; the loop survives -> retries in 30s
        liveness.record_success(refreshed=refreshed,
                                access_present=_access_token_present(client))
        return refreshed
```
- **Returns `False` on give-up** so schwabdev's `if self.tokens.update_tokens() and use_session:` treats it as "no update" — the daemon loop continues, NEVER dies.
- **Origin via the startup-thread identity** (the daemon thread already started before the wrap installed, so we cannot capture its id; comparing `current_thread() is startup_thread` is robust — the seed runs on the startup thread, daemon ticks do not).
- **Post-call state verification** (`update_tokens` does NOT raise on auth failure): `record_success` records a degraded liveness (auth-failed) when `refreshed` is True but the access token is absent.
- **Redaction (L6):** `record_failure` logs only `_redacted_excerpt(exc)`; the `setLogRecordFactory` `"Schwabdev"` redactor stays installed (A-3's `construct_authenticated_client` already installs it).

### §C.5 Liveness record + the shared 6-step state machine (OQ-5/OQ-9)
`CheckerLiveness` (in-memory, `threading.Lock`-guarded; serialized to the sidecar):
```
installed_ts, last_daemon_tick_ts, last_seed_ts, last_success_ts,
last_refresh_ts, consecutive_failures, last_error_class
```
**Timing constants (invariants held):** `HEARTBEAT_WRITE_INTERVAL = 120.0` (write every 4th daemon tick ~120s) · `STALE_THRESHOLD = 300.0` (> HEARTBEAT) · `STARTUP_GRACE = 90.0` (>= one 30s cadence + margin). Sidecar writes: on every state transition (success↔failure, first daemon tick) AND a periodic heartbeat every `HEARTBEAT_WRITE_INTERVAL`; the seed call writes once.
`evaluate_liveness_state(data, *, now_ts) -> tuple[str, str]` — THE shared machine, consumed by BOTH `render_status` and `build_schwab_checker_badge`, evaluated in THIS precedence (explicit failure outranks STARTING):
1. `data is None` → `("UNKNOWN", "web server not running, or pre-N7 build")`.
2. `consecutive_failures > 0` OR `last_error_class` set → `("DEGRADED", "<redacted reason>")` (BEFORE STARTING).
3. `last_daemon_tick_ts` present and `now - last_daemon_tick_ts <= STALE_THRESHOLD` → `("ALIVE", "last refresh <t>; <n> consecutive failures")`.
4. `last_daemon_tick_ts` present but older than `STALE_THRESHOLD` → `("DEGRADED", "stale heartbeat")`.
5. no daemon tick, no failure, `last_seed_ts`/`installed_ts` younger than `STARTUP_GRACE` → `("STARTING", "")`.
6. no daemon tick, no failure, older than `STARTUP_GRACE` → `("DEGRADED", "no daemon heartbeat since startup")` (STARTING expires).
All reasons ASCII.

### §C.6 Web badge — population breadth (V1 decision; documented)
The badge must EXIST (safe default `None`) on EVERY base-layout VM or Jinja 500s unrelated routes (the `base.html.j2` gotcha). Two VM families:
- **Family A** — ~11 VMs inheriting `BaseLayoutVM` (`metrics/shared.py`): ONE edit adds the field to all.
- **Family B** — 9 hand-replicated VMs (`DashboardVM`, `PipelineVM`, `JournalVM`, `WatchlistVM`, `PageErrorVM`, `ConfigPageVM`, `SchwabSetupVM`, `SchwabStatusVM`, `TradeDrilldownVM`): the field is added to EACH (no shared base for this family — verified: the existing `unresolved_material_discrepancies_count` is hand-populated at ~30 sites; there is no universal chokepoint).
**Population (showing the badge):** `build_schwab_checker_badge(cfg)` returns `None` when the sidecar is absent (sandbox / no Schwab / tests), so populating broadly is SAFE (badge silently hidden). V1 populates at the primary topbar-nav-target builders (all take `cfg: Config`): `build_dashboard`, `build_pipeline`, `build_journal` + `build_trade_drilldown_vm` (via `_base_banner_fields(conn, cfg)`), `build_watchlist`, `build_config_vm`, `build_metrics_index_vm`, and the `/schwab/status` + `/schwab/setup` route builders. Other base-layout surfaces (pattern review/queue, reconcile, account, per-metric drilldowns) carry the field at default `None` (badge hidden) in V1 — a safe, gotcha-compliant simplification, banked for V2 broadening.

---

## §D Out-of-scope (re-statement — HOLD THE LINE)
Identical to §A.2. Specifically the executing engineer MUST NOT: add a `schwabdev.Client.*` call site or a new client-construction path; add a migration / bump `EXPECTED_SCHEMA_VERSION` / add a `'web'` `surface` value; add an app-wide governor; construct a `Client` in a test; add a guessed rate-limit header name; install/assume schwabdev v3; touch the close-out polish batch / B-7. If any appears necessary, STOP and escalate (§6 of the brief).

---

## §E LOCK reverification (OQ table + L1–L9)

| LOCK | Disposition in this plan | Where enforced |
|------|--------------------------|----------------|
| **OQ-1** sanctioned L2 extension | A-3 reuses the existing factory + ladder; zero new call sites | §C.1 / §G Slice 1 / S3 |
| **OQ-2** full parity | BOTH hooks (quote + bars) installed | §G Slice 1 |
| **OQ-3** reuse `surface='pipeline'` | hooks pass `surface="pipeline", pipeline_run_id=None`; no v24 | §G Slice 1 / §K |
| **OQ-4** P14.N7 = WRAP (instance-level) | `install_resilient_checker`; version guard via `importlib.metadata`, never construct a Client | §C.4 / §G Slice 2 |
| **OQ-5** ephemeral sidecar | atomic `os.replace` from same-dir temp; no schema | §C.5 / §G Slice 3 |
| **OQ-6 (re-ruled)** CLI line AND web badge | both read the SAME sidecar via the SAME state machine; field on every base-layout VM | §G Slice 3 / §C.6 |
| **OQ-7** one cycle, 3 slices (+1b) | Slice 1 · 1b · 2 · 3 | §G |
| **OQ-8** single Codex chain | one chain to convergence | §J |
| **OQ-9** cross-process via sidecar | the sidecar bridges the `swing web` ↔ CLI ↔ web-render boundary | §C.1 / §C.5 |
| **OQ-10** header-name confirmed, no silent-None guess | header-KEY capture diagnostic; name-add landed behind confirmation | §C.3 / §G Slice 1b |
| **L1** scope = A-3 + P14.N7 + badge | no new features | §A.2 / §D |
| **L2** zero new `schwabdev.Client.*` sites | reuse + wrap; source-grep stays green | §G Slice 1/2 / S3 |
| **L3** NO schema | v23 held; ephemeral sidecar; `surface='pipeline'` | §K |
| **L4** sandbox gate + inside-ladder short-circuit | client not constructed under sandbox; ladder gate preserved | §C.1 / §G Slice 1 / S4 |
| **L5** reuse not re-implement | mirror `_install_pipeline_marketdata_caches`; wrap (not replace) the checker | §B.2 / §G |
| **L6** audit + redaction | `surface='pipeline'`; `_redacted_excerpt`; `setLogRecordFactory` intact; header-capture logs no values | §G Slice 1b/2 |
| **L7** production-path tests | real `create_app`; real DNS-failure sim; no stubs | §H / §G |
| **L9** rate-limit-aware | open-trade scope + TTL + provider_tag cooldown + `threading.Lock` | §C.2 / §G Slice 1 |
| **P14.N7 cleanly removable** | self-contained module + one install call + one VM helper | §B.1 / §M |

---

## §F Discipline hooks (cumulative gotchas applied)
- **base.html.j2 shared / VM-field-default gotcha:** the new `schwab_checker_badge` field lands with a safe default `None` on `BaseLayoutVM` (Family A) AND each of the 9 Family B VMs; a cascade-grep gate (Slice 3) asserts EVERY base-layout VM carries it. base.html.j2 reads ONLY `vm.*` (verified — no context-processor channel), so the field-existence fan-out is mandatory.
- **PowerShell cp1252 (#16/#32):** the CLI `render_status` checker line is strictly ASCII (it flows through stdout). The badge template markup is ASCII (text + CSS, NOT a glyph). base.html.j2 ALREADY contains non-ASCII (`🌙` :80, `⚠` :99) so ASCII assertions are SCOPED to the new line / badge substring, never whole-body (mirrors the SB5 D2 lesson).
- **Schwab daily-bar minute-default footgun:** the web bars-hook passes explicit `period_type='year', period=5, frequency_type='daily', frequency=1` (mirrors `runner.py:448-452`); a discriminating test asserts the kwargs reach `fetch_window_via_ladder`.
- **`update_tokens()` does not raise on auth failure:** the wrap verifies post-call `access_token` presence (§C.4) and records degraded rather than false-alive.
- **`os.replace` same-filesystem:** the sidecar writer uses `NamedTemporaryFile(dir=<sidecar parent>)` + `os.replace` (Windows-safe).
- **`_user_home()` test leakage:** every test touching the sidecar path monkeypatches BOTH `USERPROFILE` AND `HOME` (and points them at `tmp_path`) before invoking.
- **TestClient lifespan:** A-3 wiring tests that enter the app touch `app.state.price_fetch_executor` → use `with TestClient(app) as client:`. Pure construction tests that only assert `app.state.*` may use `create_app(cfg)` directly (no request).
- **Synthetic-fixture-vs-production-emitter drift / L7:** the A-3 test exercises the REAL `create_app` cache construction (monkeypatch `construct_authenticated_client` to a `MagicMock`; never a live network); the P14.N7 test drives a real `ConnectionError` through the wrap (no stubbed checker).
- **threading.Lock on hook state:** `_WebLadderState` guards the open-trade memo + fallback counter + cooldown ts; the DB read happens outside the lock (double-checked); a concurrent-miss test asserts no Schwab attempt slips past an active cooldown.
- **Service-layer `with conn:`:** the hooks open a FRESH `conn` per call and close it in `finally` (mirrors the pipeline hooks); no caller-held transaction.
- **Co-Authored-By / trailer-parse:** NO co-author footer; final `-m` paragraph plain prose (no leading `Word:`); `git log -1 --format='%(trailers)'` == `[]` verified after each commit.
- **#27 silent-skip audit:** N/A (no pipeline step); the header-capture diagnostic LOGS (does not silently swallow).

---

## §G Per-slice implementation tasks

### §G.0 Commit cadence preface
- Conventional commits only; stems `feat(web):` / `feat(schwab):` / `test(...)` / `style(web):`. **NO `Co-Authored-By`. NO `--no-verify`.** Final `-m` paragraph plain prose.
- TDD per step: write failing test → run, see it fail for the RIGHT reason → minimal impl → run, see pass → commit.
- **STEP 0 (do FIRST, before any code):** re-grep every anchor in §B against the worktree (signatures shift). If any no longer matches, STOP + escalate (do NOT silently patch). The anchors were orchestrator-verified at base `c7a8df3`; confirm they hold.
- After every slice: `python -m pytest -m "not slow" -q tests/integration/test_l2_lock_source_grep.py` GREEN + the slice's new tests GREEN + `ruff check swing/` clean. Full fast suite at the closer.

---

### Slice 1 — A-3 web ladder install + L9 scope/cooldown gates

**Files:**
- Modify: `swing/web/app.py`
- Test: `tests/web/test_app_marketdata_ladder_wiring.py`

**Acceptance criteria:** under production + ladder-enabled + creds, `create_app` installs BOTH ladder hooks on `app.state.price_cache` / `app.state.ohlcv_cache` and holds `app.state.schwab_client`; under sandbox (default) NO client is constructed and both `_ladder_*_fetcher` are `None` (the ~6900-test safety guarantee); the bars-hook passes `(year,5,daily,1)`; the open-trade scope gate bypasses Schwab for non-open-trade tickers; the provider_tag cooldown gate pins to yfinance after N consecutive `'yfinance'` returns and resumes after the cooldown; the credential resolver honors the cfg-tier cascade; shared hook state is `threading.Lock`-guarded.

- [ ] **Step 1: Write the failing production-path wiring tests**

```python
# tests/web/test_app_marketdata_ladder_wiring.py
"""Slice 1 — A-3 web market-data ladder install + L9 gates (production-path)."""
from __future__ import annotations

import dataclasses
import threading
from unittest.mock import MagicMock

import pytest

from swing.web.app import create_app


def _production_cfg(base_cfg):
    """Return a cfg with production env + ladder enabled (no live network)."""
    schwab = dataclasses.replace(
        base_cfg.integrations.schwab,
        environment="production", marketdata_ladder_enabled=True,
    )
    integ = dataclasses.replace(base_cfg.integrations, schwab=schwab)
    return dataclasses.replace(base_cfg, integrations=integ)


def test_sandbox_app_constructs_no_client_no_hooks(seeded_db):
    cfg, _ = seeded_db  # default env == 'sandbox'
    app = create_app(cfg)
    assert app.state.schwab_client is None
    assert app.state.price_cache._ladder_fetcher is None
    assert app.state.ohlcv_cache._ladder_bars_fetcher is None


def test_production_app_installs_both_hooks(seeded_db, monkeypatch):
    cfg, _ = seeded_db
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "id-xxxx")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "secret-xxxx")
    fake_client = MagicMock(name="schwab_client")
    monkeypatch.setattr(
        "swing.web.app.construct_authenticated_client",
        lambda *a, **k: fake_client,
    )
    app = create_app(_production_cfg(cfg))
    assert app.state.schwab_client is fake_client
    assert app.state.price_cache._ladder_fetcher is not None
    assert app.state.ohlcv_cache._ladder_bars_fetcher is not None
```

- [ ] **Step 2: Run; verify fail** — `python -m pytest tests/web/test_app_marketdata_ladder_wiring.py -q` → FAIL (`app.state.schwab_client` AttributeError / hooks not installed).

- [ ] **Step 3: Implement `_construct_web_schwab_client` + `_install_web_marketdata_caches` + invoke** (in `swing/web/app.py`)

```python
# ---- A-3 web market-data ladder install (mirrors pipeline runner) ----
import threading
import time as _time

from swing.integrations.schwab.auth import (
    construct_authenticated_client,
    resolve_credentials_env_or_prompt,
)
from swing.integrations.schwab.errors import SchwabConfigMissingError

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
        return None  # silent — operator not using Schwab
    try:
        return construct_authenticated_client(
            cfg, environment, client_id=client_id, client_secret=client_secret,
        )
    except Exception as exc:  # noqa: BLE001 — graceful-degradation safety boundary
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
        # DB read OUTSIDE the lock to avoid holding it during I/O.
        from swing.data.db import connect
        from swing.data.repos.trades import list_open_trades
        conn = connect(self._cfg.paths.db_path)
        try:
            tickers = frozenset(t.ticker.upper() for t in list_open_trades(conn))
        finally:
            conn.close()
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

    Returns the constructed web Schwab client (with the P14.N7 resilient
    checker wrap installed) or None (sandbox / no creds / construction
    failure → yfinance-only web app, today's behavior).
    """
    client = _construct_web_schwab_client(cfg)
    if client is None:
        return None

    # P14.N7 (Slice 2): wrap the checker + seed one refresh before serving.
    from swing.integrations.schwab.checker_resilience import (
        CheckerLiveness,
        checker_liveness_sidecar_path,
        install_resilient_checker,
    )
    env = cfg.integrations.schwab.environment
    liveness = CheckerLiveness(
        installed_ts=_time.time(),
        sidecar_path=checker_liveness_sidecar_path(env),
    )
    install_resilient_checker(client, liveness=liveness)
    client.tokens.update_tokens()  # seed (origin='seed'; exception-isolated by the wrap)

    from swing.integrations.schwab.marketdata_ladder import (
        fetch_quote_via_ladder,
        fetch_window_via_ladder,
    )
    from swing.data.db import connect

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
            from datetime import datetime as _dt
            bars = _yf_window_fallback(
                ticker, None, None,
            )
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
        state.note_provider(provider_tag)
        if provider_tag == "schwab_api" and hasattr(window, "to_dataframe"):
            bars = window.to_dataframe()
        else:
            bars = window
        return (bars, provider_tag)

    price_cache.set_ladder_fetcher(_quote_hook)
    ohlcv_cache.set_ladder_bars_fetcher(_bars_hook)
    return client
```

Invoke it immediately after the cache construction (`app.py:189`):
```python
    app.state.price_cache = PriceCache(cfg)
    app.state.ohlcv_cache = OhlcvCache(cfg)     # NEW — Phase 3d §3.5
    app.state.schwab_client = _install_web_marketdata_caches(  # NEW — A-3 / P14.N7
        cfg, app.state.price_cache, app.state.ohlcv_cache,
    )
```
(Confirm the exact import names `read_or_fetch_archive`, `last_completed_session`, `connect`, `PriceSnapshot` at IMPLEMENT time — mirror the pipeline hooks at `runner.py:355-463`, which import the same symbols. If `_fetch_live_price` is private/renamed, mirror whatever the pipeline `_yf_quote_fallback` uses.)

- [ ] **Step 4: Run; verify pass** — `python -m pytest tests/web/test_app_marketdata_ladder_wiring.py::test_sandbox_app_constructs_no_client_no_hooks tests/web/test_app_marketdata_ladder_wiring.py::test_production_app_installs_both_hooks -q` → PASS. `ruff check swing/web/app.py` clean.

- [ ] **Step 5: Commit**

```bash
git add swing/web/app.py tests/web/test_app_marketdata_ladder_wiring.py
git commit -m "feat(web): install the Schwab market-data ladder on the web caches under production

Mirrors the pipeline cache-install helper: constructs the web Schwab client via
the existing factory only when the ladder is active and credentials are present,
then installs both the quote and daily-bar ladder hooks. The default sandbox
configuration constructs no client and no checker, so the fast suite stays
offline."
```

- [ ] **Step 6: Add the daily-bar footgun + L9 scope + cooldown + thread-safety tests**

```python
# tests/web/test_app_marketdata_ladder_wiring.py (append)

def _install_hooks(cfg, monkeypatch, fake_client):
    """Build a production app with a captured ladder, returning the state +
    the installed hooks for direct invocation."""
    monkeypatch.setenv("SCHWAB_CLIENT_ID", "id-xxxx")
    monkeypatch.setenv("SCHWAB_CLIENT_SECRET", "secret-xxxx")
    monkeypatch.setattr(
        "swing.web.app.construct_authenticated_client", lambda *a, **k: fake_client,
    )
    app = create_app(_production_cfg(cfg))
    return app


def test_bars_hook_passes_explicit_daily_kwargs(seeded_db, monkeypatch):
    cfg, _ = seeded_db
    captured = {}

    def _fake_window(ticker, **kwargs):
        captured.update(kwargs)
        return (object(), "yfinance")

    monkeypatch.setattr(
        "swing.integrations.schwab.marketdata_ladder.fetch_window_via_ladder",
        _fake_window,
    )
    # seed AAA as the only open trade so the scope gate ATTEMPTS Schwab
    _seed_open_trade(cfg, "AAA")
    app = _install_hooks(cfg, monkeypatch, MagicMock())
    app.state.ohlcv_cache._ladder_bars_fetcher("AAA")
    assert captured["period_type"] == "year"
    assert captured["period"] == 5
    assert captured["frequency_type"] == "daily"
    assert captured["frequency"] == 1
    assert captured["surface"] == "pipeline"
    assert captured["pipeline_run_id"] is None


def test_scope_gate_bypasses_schwab_for_non_open_trade(seeded_db, monkeypatch):
    cfg, _ = seeded_db
    calls = []
    monkeypatch.setattr(
        "swing.integrations.schwab.marketdata_ladder.fetch_quote_via_ladder",
        lambda ticker, **k: calls.append(ticker) or (MagicMock(price=1.0), "schwab_api"),
    )
    _seed_open_trade(cfg, "AAA")
    app = _install_hooks(cfg, monkeypatch, MagicMock())
    # also stub the yfinance fallback so the bypass path needs no network
    monkeypatch.setattr(app.state.price_cache, "_fetch_live_price", lambda t: 9.0)
    _price, provider = app.state.price_cache._ladder_fetcher("ZZZ")  # not open
    assert provider == "yfinance"
    assert calls == []  # Schwab NEVER attempted for the non-open-trade ticker


def test_cooldown_after_consecutive_yfinance_fallbacks(seeded_db, monkeypatch):
    cfg, _ = seeded_db
    attempts = []
    monkeypatch.setattr(
        "swing.integrations.schwab.marketdata_ladder.fetch_quote_via_ladder",
        lambda ticker, **k: attempts.append(ticker) or (MagicMock(price=1.0), "yfinance"),
    )
    _seed_open_trade(cfg, "AAA")
    app = _install_hooks(cfg, monkeypatch, MagicMock())
    monkeypatch.setattr(app.state.price_cache, "_fetch_live_price", lambda t: 9.0)
    hook = app.state.price_cache._ladder_fetcher
    for _ in range(3):       # _WEB_LADDER_FALLBACK_COOLDOWN_THRESHOLD
        hook("AAA")
    assert len(attempts) == 3
    hook("AAA")              # now in cooldown -> bypassed, NO new Schwab attempt
    assert len(attempts) == 3


def test_concurrent_misses_do_not_slip_past_cooldown(seeded_db, monkeypatch):
    cfg, _ = seeded_db
    attempts = []
    lock = threading.Lock()
    def _fetch(ticker, **k):
        with lock:
            attempts.append(ticker)
        return (MagicMock(price=1.0), "yfinance")
    monkeypatch.setattr(
        "swing.integrations.schwab.marketdata_ladder.fetch_quote_via_ladder", _fetch,
    )
    _seed_open_trade(cfg, "AAA")
    app = _install_hooks(cfg, monkeypatch, MagicMock())
    monkeypatch.setattr(app.state.price_cache, "_fetch_live_price", lambda t: 9.0)
    hook = app.state.price_cache._ladder_fetcher
    for _ in range(3):
        hook("AAA")          # trip the cooldown
    threads = [threading.Thread(target=hook, args=("AAA",)) for _ in range(8)]
    for t in threads: t.start()
    for t in threads: t.join()
    assert len(attempts) == 3  # cooldown held under concurrency; no extra Schwab calls
```
Add the `_seed_open_trade(cfg, ticker)` helper (insert one row into `trades` in an open `state` mirroring `tests/web` open-trade seeders — derive from an existing open-trade fixture, NOT hand-rolled SQL; gotcha: synthetic-fixture-vs-emitter drift).

> **Test-arithmetic note (memory `feedback_regression_test_arithmetic`):** the cooldown test counts Schwab ATTEMPTS pre- and post-threshold: 3 attempts then a 4th call adds ZERO (cooldown). Under the pre-fix path (no cooldown) the 4th would attempt → `len(attempts)==4`. The test distinguishes.

- [ ] **Step 7: Run; verify pass; commit**

```bash
git add swing/web/app.py tests/web/test_app_marketdata_ladder_wiring.py
git commit -m "feat(web): bound web ladder calls with an open-trade scope gate and a provider-tag cooldown

The hooks attempt Schwab only for open-trade tickers and back off to yfinance
after a run of consecutive fallbacks, with all shared gate state guarded by a
lock so concurrent cache misses cannot over-issue calls. The daily-bar hook
passes explicit year and daily kwargs so the chart path never receives intraday
minute candles."
```

- [ ] **Step 8: Add the cfg-tier credential-resolution test**

```python
def test_cfg_tier_credentials_construct_client_without_env(seeded_db, monkeypatch):
    cfg, _ = seeded_db
    monkeypatch.delenv("SCHWAB_CLIENT_ID", raising=False)
    monkeypatch.delenv("SCHWAB_CLIENT_SECRET", raising=False)
    monkeypatch.setattr(
        "swing.web.app.resolve_credentials_env_or_prompt",
        lambda cfg, env, *, allow_prompt=False: ("cfg-id", "cfg-secret"),
    )
    fake = MagicMock()
    monkeypatch.setattr("swing.web.app.construct_authenticated_client", lambda *a, **k: fake)
    app = create_app(_production_cfg(cfg))
    assert app.state.schwab_client is fake  # cfg-tier creds construct the client
```
Run; verify pass; commit (`feat(web): resolve web Schwab credentials via the env-then-config cascade`).

---

### Slice 1b — L9c rate-limit header-name confirmation diagnostic (OQ-10)

**Files:**
- Modify: `swing/integrations/schwab/marketdata.py` (`_extract_response_payload`)
- Test: `tests/integration/schwab/test_marketdata_header_capture.py`

**Acceptance criteria:** when a response carries NONE of the known rate-limit header names AND env is production, the extractor logs the response header KEY list (names only — NO values) ONCE per process at DEBUG; when a known header matches, no capture log fires; header VALUES never appear in any log. NO guessed header name is added to the candidate list (the actual name is confirmed at the S7 smoke; the candidate-add is a follow-up).

- [ ] **Step 1: Write the failing test**

```python
# tests/integration/schwab/test_marketdata_header_capture.py
"""Slice 1b — OQ-10 rate-limit header-name capture diagnostic (no value leak)."""
from __future__ import annotations

import logging

from swing.integrations.schwab import marketdata


class _Resp:
    def __init__(self, headers):
        self.status_code = 200
        self.headers = headers
    def json(self):
        return {"ok": True}


def test_capture_logs_header_keys_when_no_known_header(caplog, monkeypatch):
    marketdata._reset_header_capture_for_tests()  # clear the once-per-process flag
    with caplog.at_level(logging.DEBUG, logger="swing.integrations.schwab.marketdata"):
        marketdata._extract_response_payload(
            _Resp({"X-Mystery-Budget": "118", "Content-Type": "application/json"}),
            endpoint="quotes",
        )
    msgs = " ".join(r.getMessage() for r in caplog.records)
    assert "X-Mystery-Budget" in msgs        # the KEY is surfaced for OQ-10 confirmation
    assert "118" not in msgs                  # the VALUE is NEVER logged


def test_no_capture_when_known_header_present(caplog, monkeypatch):
    marketdata._reset_header_capture_for_tests()
    with caplog.at_level(logging.DEBUG, logger="swing.integrations.schwab.marketdata"):
        _payload, _status, remaining = marketdata._extract_response_payload(
            _Resp({"X-RateLimit-Remaining": "42"}), endpoint="quotes",
        )
    assert remaining == 42
    assert "header-name capture" not in " ".join(r.getMessage() for r in caplog.records)
```

- [ ] **Step 2: Run; verify fail** — `_reset_header_capture_for_tests` / the capture branch do not exist yet.

- [ ] **Step 3: Implement the capture branch** (in `marketdata.py`, inside `_extract_response_payload`, after the existing header loop)

```python
# module level (near the top of marketdata.py)
_HEADER_CAPTURE_DONE = False


def _reset_header_capture_for_tests() -> None:
    global _HEADER_CAPTURE_DONE
    _HEADER_CAPTURE_DONE = False


# inside _extract_response_payload, AFTER the existing candidate-name loop,
# replacing the bare `return payload, http_status, rate_limit_remaining`:
    global _HEADER_CAPTURE_DONE
    if (
        rate_limit_remaining is None
        and headers is not None
        and not _HEADER_CAPTURE_DONE
    ):
        # OQ-10: the actual Schwab rate-limit header name is unknown (no
        # on-disk artifact records it). Log the header KEY list ONCE (names
        # only, never values) so the operator can confirm the real name from
        # the production console; the candidate-name addition then lands
        # behind that confirmation. NO guessed name is added here.
        try:
            keys = sorted(headers.keys())
        except Exception:  # noqa: BLE001 — best-effort diagnostic only
            keys = None
        if keys is not None:
            _HEADER_CAPTURE_DONE = True
            log.debug(
                "Schwab rate-limit header-name capture (%s): no known "
                "rate-limit header matched; response header keys present: %s",
                endpoint, keys,
            )
    return payload, http_status, rate_limit_remaining
```
(Confirm `log` is the module logger `logging.getLogger("swing.integrations.schwab.marketdata")`; if the module uses a different `log` binding, reuse it.)

- [ ] **Step 4: Run; verify pass.** `ruff check` clean.

- [ ] **Step 5: Commit**

```bash
git add swing/integrations/schwab/marketdata.py tests/integration/schwab/test_marketdata_header_capture.py
git commit -m "feat(schwab): log unmatched response header names once so the rate-limit header can be confirmed

The actual Schwab rate-limit-remaining header name is not recorded in any
on-disk artifact, so guessing one would leave the audit value silently null. A
one-time debug log of the response header names (never their values) lets the
operator confirm the real name during the production smoke; the candidate-name
addition then lands behind that confirmation."
```

---

### Slice 2 — P14.N7 checker-resilience wrap + liveness record

**Files:**
- Create: `swing/integrations/schwab/checker_resilience.py`
- Test: `tests/integration/schwab/test_checker_resilience.py`
- (Slice 1 already calls `install_resilient_checker` + seed; this slice makes it real.)

**Acceptance criteria:** the wrap replaces `client.tokens.update_tokens`; a background no-force call that raises does NOT propagate (returns `False` after bounded backoff); a forced call passes through and DOES propagate; liveness transitions installed → degraded(`consecutive_failures>0`) → alive(`consecutive_failures==0`); a seed-origin call sets `last_seed_ts` (NOT `last_daemon_tick_ts`); the schwabdev version guard asserts `2.5.1` via `importlib.metadata.version` WITHOUT constructing a `Client`.

- [ ] **Step 1: Write the failing tests**

```python
# tests/integration/schwab/test_checker_resilience.py
"""Slice 2 — P14.N7 resilient checker wrap + liveness (DNS-failure sim)."""
from __future__ import annotations

import importlib.metadata
import threading
import time

import pytest

from swing.integrations.schwab.checker_resilience import (
    CheckerLiveness,
    install_resilient_checker,
)


class _FakeTokens:
    def __init__(self, raises_n=0, access_token="acc"):
        self._raises_left = raises_n
        self.access_token = access_token
        self.calls = []
    def update_tokens(self, force_access_token=False, force_refresh_token=False):
        self.calls.append((force_access_token, force_refresh_token))
        if force_access_token or force_refresh_token:
            raise ConnectionError("forced path must propagate")
        if self._raises_left > 0:
            self._raises_left -= 1
            raise ConnectionError("Failed to resolve api.schwabapi.com")
        return True


class _FakeClient:
    def __init__(self, tokens):
        self.tokens = tokens


def _liveness(tmp_path):
    return CheckerLiveness(installed_ts=time.time(), sidecar_path=tmp_path / "lv.json")


def test_wrap_replaces_update_tokens(tmp_path):
    tokens = _FakeTokens()
    client = _FakeClient(tokens)
    original = client.tokens.update_tokens
    install_resilient_checker(client, liveness=_liveness(tmp_path))
    assert client.tokens.update_tokens is not original


def test_background_failure_is_isolated_then_recovers(tmp_path, monkeypatch):
    sleeps = []
    monkeypatch.setattr("swing.integrations.schwab.checker_resilience.time.sleep", sleeps.append)
    tokens = _FakeTokens(raises_n=5)  # exceeds retries -> give up THIS cycle
    client = _FakeClient(tokens)
    lv = _liveness(tmp_path)
    install_resilient_checker(client, liveness=lv, retries=2, backoff_base_s=1.0)
    # daemon-origin call: simulate from a worker thread (not the startup thread)
    out = {}
    th = threading.Thread(target=lambda: out.setdefault("r", client.tokens.update_tokens()))
    th.start(); th.join()
    assert out["r"] is False                       # gave up, did NOT raise
    assert lv.consecutive_failures > 0             # degraded
    assert sleeps == [1.0, 2.0]                    # bounded backoff 2^0, 2^1
    # next cycle succeeds -> alive
    th2 = threading.Thread(target=lambda: client.tokens.update_tokens())
    th2.start(); th2.join()
    assert lv.consecutive_failures == 0            # recovered


def test_forced_call_propagates(tmp_path):
    tokens = _FakeTokens()
    client = _FakeClient(tokens)
    install_resilient_checker(client, liveness=_liveness(tmp_path))
    with pytest.raises(ConnectionError):
        client.tokens.update_tokens(force_access_token=True)


def test_seed_origin_does_not_advance_daemon_heartbeat(tmp_path):
    tokens = _FakeTokens()
    client = _FakeClient(tokens)
    lv = _liveness(tmp_path)
    install_resilient_checker(client, liveness=lv)  # installed on THIS (startup) thread
    client.tokens.update_tokens()                    # SEED (same thread) -> origin 'seed'
    assert lv.last_seed_ts is not None
    assert lv.last_daemon_tick_ts is None            # the seed must NOT look like a heartbeat


def test_schwabdev_version_guard_without_constructing_client():
    # OQ-4: NEVER construct a Client; assert via package metadata.
    assert importlib.metadata.version("schwabdev") == "2.5.1"
```

- [ ] **Step 2: Run; verify fail** — module does not exist.

- [ ] **Step 3: Implement `checker_resilience.py`** (wrap + liveness; the sidecar writer + state machine land in Slice 3, but the record + constants live here now)

```python
# swing/integrations/schwab/checker_resilience.py
"""P14.N7 — resilient wrap for the schwabdev background checker thread.

schwabdev's Client spawns a daemon checker that calls
``self.tokens.update_tokens()`` every 30s; an uncaught ConnectionError
(e.g. DNS loss after laptop sleep) kills that thread and silently degrades
token refresh until ``swing web`` restarts. This module wraps the bound
``update_tokens`` on a SINGLE client instance so the loop survives, records
a liveness signal, and surfaces it via an ephemeral sidecar (Slice 3).

Cleanly removable: the Phase-15 schwabdev v3 upgrade deletes the checker and
this module with it. Validated against schwabdev 2.5.1
(``client.py:50-56`` + ``tokens.py:160-198``).
"""
from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path

from swing.integrations.schwab.auth import _redacted_excerpt

log = logging.getLogger(__name__)

# Timing constants (invariant: STALE_THRESHOLD > HEARTBEAT_WRITE_INTERVAL;
# STARTUP_GRACE >= one 30s checker cadence + margin).
HEARTBEAT_WRITE_INTERVAL = 120.0   # write the sidecar every ~4th daemon tick
STALE_THRESHOLD = 300.0            # CLI/badge report DEGRADED past this
STARTUP_GRACE = 90.0               # STARTING expires to DEGRADED past this
_HEARTBEAT_TICKS = 4               # 4 * 30s ~ HEARTBEAT_WRITE_INTERVAL


@dataclass
class CheckerLiveness:
    installed_ts: float
    sidecar_path: Path
    last_daemon_tick_ts: float | None = None
    last_seed_ts: float | None = None
    last_success_ts: float | None = None
    last_refresh_ts: float | None = None
    consecutive_failures: int = 0
    last_error_class: str | None = None
    _lock: threading.Lock = field(default_factory=threading.Lock, repr=False)
    _daemon_tick_count: int = field(default=0, repr=False)

    def record_tick(self, origin: str) -> None:
        with self._lock:
            if origin == "daemon":
                first = self.last_daemon_tick_ts is None
                self.last_daemon_tick_ts = time.time()
                self._daemon_tick_count += 1
                write = first or (self._daemon_tick_count % _HEARTBEAT_TICKS == 0)
            else:  # 'seed'
                self.last_seed_ts = time.time()
                write = True
        if write:
            self._write_sidecar()

    def record_failure(self, exc: BaseException) -> None:
        with self._lock:
            self.consecutive_failures += 1
            self.last_error_class = type(exc).__name__
        log.warning(
            "Schwab checker refresh failed (%s: %s); loop continues.",
            type(exc).__name__, _redacted_excerpt(exc),
        )
        self._write_sidecar()  # transition -> persist

    def record_success(self, *, refreshed: bool, access_present: bool) -> None:
        with self._lock:
            had_failures = self.consecutive_failures > 0
            if refreshed and not access_present:
                # update_tokens does not raise on auth failure (gotcha):
                # a claimed refresh with no token = degraded, not alive.
                self.consecutive_failures += 1
                self.last_error_class = "AuthRefreshNoToken"
                transition = True
            else:
                self.consecutive_failures = 0
                self.last_error_class = None
                self.last_success_ts = time.time()
                if refreshed:
                    self.last_refresh_ts = time.time()
                transition = had_failures
        if transition:
            self._write_sidecar()

    def _write_sidecar(self) -> None:
        # Real implementation lands in Slice 3 (write_liveness_sidecar). Until
        # then this is a no-op so Slice 2 tests run without a sidecar.
        try:
            write_liveness_sidecar(self, self.sidecar_path)
        except Exception:  # noqa: BLE001 — never let sidecar IO kill the daemon
            log.debug("checker liveness sidecar write skipped", exc_info=True)


def _access_token_present(client: object) -> bool:
    return bool(getattr(getattr(client, "tokens", None), "access_token", None))


def install_resilient_checker(
    client: object, *, liveness: CheckerLiveness,
    retries: int = 2, backoff_base_s: float = 1.0,
) -> None:
    """Replace ``client.tokens.update_tokens`` with the resilient wrapper."""
    original = client.tokens.update_tokens
    startup_thread = threading.current_thread()

    def resilient_update_tokens(force_access_token=False, force_refresh_token=False):
        if force_access_token or force_refresh_token:
            return original(
                force_access_token=force_access_token,
                force_refresh_token=force_refresh_token,
            )
        origin = "seed" if threading.current_thread() is startup_thread else "daemon"
        liveness.record_tick(origin)
        attempt = 0
        while True:
            try:
                refreshed = original()
            except Exception as exc:  # noqa: BLE001
                liveness.record_failure(exc)
                if attempt < retries:
                    attempt += 1
                    time.sleep(backoff_base_s * (2 ** (attempt - 1)))
                    continue
                return False
            liveness.record_success(
                refreshed=bool(refreshed), access_present=_access_token_present(client),
            )
            return refreshed

    client.tokens.update_tokens = resilient_update_tokens
```
(Slice 3 adds `write_liveness_sidecar`, `read_liveness_sidecar`, `checker_liveness_sidecar_path`, `evaluate_liveness_state` to this same module. For Slice 2, define a minimal `write_liveness_sidecar`/`checker_liveness_sidecar_path` stub at the bottom so imports resolve — OR land them now; see Slice 3. To keep Slice 2 self-contained, add the path helper + a real writer now and let Slice 3 add the reader + state machine. The plan lands the writer here.)

- [ ] **Step 3b: Add the sidecar path + writer (so Slice 1's import + the wrap's `_write_sidecar` resolve)**

```python
import json
import os
import tempfile

from swing.config_user import _user_home


def checker_liveness_sidecar_path(env: str) -> Path:
    return _user_home() / "swing-data" / f"schwab-checker-liveness.{env}.json"


def write_liveness_sidecar(record: "CheckerLiveness", path: Path) -> None:
    payload = {
        "installed_ts": record.installed_ts,
        "last_daemon_tick_ts": record.last_daemon_tick_ts,
        "last_seed_ts": record.last_seed_ts,
        "last_success_ts": record.last_success_ts,
        "last_refresh_ts": record.last_refresh_ts,
        "consecutive_failures": record.consecutive_failures,
        "last_error_class": record.last_error_class,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="ascii") as fh:
            json.dump(payload, fh)
        os.replace(tmp, path)  # atomic; same filesystem (dest dir) -> Windows-safe
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise
```

- [ ] **Step 4: Run; verify pass** — `python -m pytest tests/integration/schwab/test_checker_resilience.py -q`. Note: the `_write_sidecar` calls need a real `sidecar_path` under `tmp_path` (the tests pass `tmp_path / "lv.json"`); monkeypatch `USERPROFILE`/`HOME` is NOT needed because the tests inject the path directly. `ruff check` clean.

- [ ] **Step 5: Commit**

```bash
git add swing/integrations/schwab/checker_resilience.py tests/integration/schwab/test_checker_resilience.py
git commit -m "feat(schwab): resilient wrap for the schwabdev checker token-refresh thread

Replaces the bound update_tokens on the long-lived web client with a wrapper
that isolates background failures behind a bounded backoff so the daemon loop
survives a transient DNS loss, passes forced calls straight through, verifies
the post-refresh token state, and records a thread-safe liveness signal. The
version is asserted from package metadata so no client is constructed in tests."
```

---

### Slice 3 — liveness surfacing: state machine + CLI line + web badge

**Files:**
- Modify: `swing/integrations/schwab/checker_resilience.py` (`read_liveness_sidecar` + `evaluate_liveness_state`)
- Modify: `swing/cli_schwab.py` (`render_status` checker line)
- Create: `swing/web/view_models/schwab_checker_badge.py`
- Modify: `swing/web/view_models/metrics/shared.py` + the 9 Family B VMs + the population builders
- Modify: `swing/web/templates/base.html.j2`, `swing/web/static/app.css`
- Tests: `tests/integration/schwab/test_checker_liveness_state.py`, `tests/cli/test_schwab_status_checker_liveness.py`, `tests/web/test_schwab_checker_badge.py`

#### §G.S3.a — the shared 6-step state machine + reader

- [ ] **Step 1: Write the failing state-machine tests**

```python
# tests/integration/schwab/test_checker_liveness_state.py
"""Slice 3 — shared liveness state machine (6-step precedence)."""
from __future__ import annotations

from swing.integrations.schwab.checker_resilience import (
    HEARTBEAT_WRITE_INTERVAL,
    STALE_THRESHOLD,
    STARTUP_GRACE,
    evaluate_liveness_state,
)


def test_invariant_stale_exceeds_heartbeat():
    assert STALE_THRESHOLD > HEARTBEAT_WRITE_INTERVAL


def test_absent_is_unknown():
    state, _ = evaluate_liveness_state(None, now_ts=1000.0)
    assert state == "UNKNOWN"


def test_explicit_failure_outranks_starting():
    data = {"installed_ts": 1000.0, "last_seed_ts": 1000.0,
            "consecutive_failures": 1, "last_error_class": "ConnectionError"}
    state, _ = evaluate_liveness_state(data, now_ts=1001.0)  # within grace, but failed
    assert state == "DEGRADED"


def test_alive_within_stale_threshold():
    data = {"installed_ts": 0.0, "last_daemon_tick_ts": 1000.0,
            "consecutive_failures": 0}
    state, _ = evaluate_liveness_state(data, now_ts=1000.0 + STALE_THRESHOLD - 1)
    assert state == "ALIVE"


def test_stale_daemon_tick_is_degraded():
    data = {"installed_ts": 0.0, "last_daemon_tick_ts": 1000.0,
            "consecutive_failures": 0}
    state, reason = evaluate_liveness_state(data, now_ts=1000.0 + STALE_THRESHOLD + 1)
    assert state == "DEGRADED" and "stale" in reason


def test_seed_only_within_grace_is_starting():
    data = {"installed_ts": 1000.0, "last_seed_ts": 1000.0, "consecutive_failures": 0}
    state, _ = evaluate_liveness_state(data, now_ts=1000.0 + STARTUP_GRACE - 1)
    assert state == "STARTING"


def test_seed_only_past_grace_expires_to_degraded():
    data = {"installed_ts": 1000.0, "last_seed_ts": 1000.0, "consecutive_failures": 0}
    state, reason = evaluate_liveness_state(data, now_ts=1000.0 + STARTUP_GRACE + 1)
    assert state == "DEGRADED" and "no daemon heartbeat" in reason


def test_all_reasons_ascii():
    for data, now in [
        (None, 0.0),
        ({"installed_ts": 0.0, "consecutive_failures": 2, "last_error_class": "X"}, 1.0),
        ({"installed_ts": 0.0, "last_daemon_tick_ts": 0.0, "consecutive_failures": 0}, 1.0),
    ]:
        _state, reason = evaluate_liveness_state(data, now_ts=now)
        assert reason.isascii()
```

- [ ] **Step 2: Run; verify fail** — `evaluate_liveness_state` / `read_liveness_sidecar` not defined.

- [ ] **Step 3: Implement the reader + state machine** (append to `checker_resilience.py`)

```python
def read_liveness_sidecar(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        with open(path, encoding="ascii") as fh:
            return json.load(fh)
    except (OSError, ValueError):
        return None


def evaluate_liveness_state(data: dict | None, *, now_ts: float) -> tuple[str, str]:
    """The ONE state machine (consumed by render_status AND the web badge).

    Precedence (explicit failure outranks STARTING):
      1 absent -> UNKNOWN | 2 failure -> DEGRADED | 3 fresh daemon tick -> ALIVE
      4 stale daemon tick -> DEGRADED | 5 seed-only within grace -> STARTING
      6 seed-only past grace -> DEGRADED.
    """
    if data is None:
        return ("UNKNOWN", "web server not running, or pre-N7 build")
    failures = data.get("consecutive_failures") or 0
    if failures > 0 or data.get("last_error_class"):
        cls = data.get("last_error_class") or "refresh failure"
        return ("DEGRADED", f"{failures} consecutive failures ({cls})")
    last_tick = data.get("last_daemon_tick_ts")
    if last_tick is not None:
        if now_ts - last_tick <= STALE_THRESHOLD:
            return ("ALIVE", "checker heartbeat fresh")
        return ("DEGRADED", "stale heartbeat")
    anchor = data.get("last_seed_ts") or data.get("installed_ts") or 0.0
    if now_ts - anchor < STARTUP_GRACE:
        return ("STARTING", "awaiting first daemon heartbeat")
    return ("DEGRADED", "no daemon heartbeat since startup")
```

- [ ] **Step 4: Run; verify pass; commit** (`feat(schwab): shared checker-liveness state machine and sidecar reader`).

#### §G.S3.b — the `render_status` checker line (CLI)

- [ ] **Step 1: Write the failing CLI test**

```python
# tests/cli/test_schwab_status_checker_liveness.py
"""Slice 3 — `swing schwab status` checker-liveness line."""
from __future__ import annotations

import json
import time

from swing.integrations.schwab import checker_resilience as cr


def _render_with_sidecar(tmp_path, monkeypatch, payload, conn, cfg):
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    sidecar = cr.checker_liveness_sidecar_path("sandbox")
    sidecar.parent.mkdir(parents=True, exist_ok=True)
    if payload is not None:
        sidecar.write_text(json.dumps(payload), encoding="ascii")
    from swing.cli_schwab import render_status
    from datetime import datetime, UTC
    return render_status(cfg=cfg, env="sandbox", tokens_path=sidecar.parent / "x.db",
                         now=datetime.now(UTC), conn=conn)


def test_status_reports_alive(tmp_path, monkeypatch, status_cfg_conn):
    cfg, conn = status_cfg_conn
    out = _render_with_sidecar(
        tmp_path, monkeypatch,
        {"installed_ts": 0.0, "last_daemon_tick_ts": time.time(),
         "consecutive_failures": 0}, conn, cfg,
    )
    assert "Checker:" in out
    assert "ALIVE" in out


def test_status_reports_unknown_when_absent(tmp_path, monkeypatch, status_cfg_conn):
    cfg, conn = status_cfg_conn
    out = _render_with_sidecar(tmp_path, monkeypatch, None, conn, cfg)
    assert "Checker:" in out and "unknown" in out.lower()


def test_checker_line_is_ascii(tmp_path, monkeypatch, status_cfg_conn):
    cfg, conn = status_cfg_conn
    out = _render_with_sidecar(
        tmp_path, monkeypatch,
        {"installed_ts": 0.0, "consecutive_failures": 2, "last_error_class": "ConnectionError"},
        conn, cfg,
    )
    line = next(ln for ln in out.splitlines() if ln.startswith("Checker:"))
    assert line.isascii()  # ASCII scoped to the NEW line (render_status uses em dash elsewhere)
```
Provide a `status_cfg_conn` fixture mirroring an existing `cli_schwab` status test (a sandbox cfg + a v23 schema conn). Reuse an existing schwab-status test's seeding rather than hand-rolling.

- [ ] **Step 2: Run; verify fail** — no "Checker:" line yet.

- [ ] **Step 3: Add the checker line to `render_status`** (after the section-1 LIVE/PROVISIONAL/DEGRADED block, before section 2). The line is ASCII-only:

```python
    # Section 1b — P14.N7 checker-thread liveness (read from the ephemeral
    # sidecar; cross-process bridge to the swing web checker). ASCII-only.
    from swing.integrations.schwab.checker_resilience import (
        checker_liveness_sidecar_path,
        evaluate_liveness_state,
        read_liveness_sidecar,
    )
    _live = read_liveness_sidecar(checker_liveness_sidecar_path(env))
    _state, _reason = evaluate_liveness_state(_live, now_ts=now.timestamp())
    if _state == "ALIVE":
        out.append(f"Checker: ALIVE ({_reason})")
    elif _state == "STARTING":
        out.append(f"Checker: STARTING ({_reason})")
    elif _state == "UNKNOWN":
        out.append(f"Checker: unknown -- {_reason}")
    else:
        out.append(f"Checker: DEGRADED -- {_reason}")
    out.append("")
```
(`now` is a tz-aware `datetime`; `now.timestamp()` is the monotonic-comparable wall-clock the sidecar uses `time.time()` for.)

- [ ] **Step 4: Run; verify pass; commit** (`feat(schwab): surface checker-thread liveness in swing schwab status`).

#### §G.S3.c — the web badge VM helper + base-VM field fan-out

- [ ] **Step 1: Write the failing badge-helper + fan-out tests**

```python
# tests/web/test_schwab_checker_badge.py
"""Slice 3 — web checker-health badge helper + base-VM field fan-out."""
from __future__ import annotations

import dataclasses
import json
import time

from swing.integrations.schwab import checker_resilience as cr
from swing.web.view_models.schwab_checker_badge import (
    SchwabCheckerBadgeVM,
    build_schwab_checker_badge,
)


def test_badge_none_when_sidecar_absent(tmp_path, monkeypatch, seeded_db):
    cfg, _ = seeded_db
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    assert build_schwab_checker_badge(cfg) is None  # hidden when no sidecar


def test_badge_alive(tmp_path, monkeypatch, seeded_db):
    cfg, _ = seeded_db
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    env = cfg.integrations.schwab.environment
    p = cr.checker_liveness_sidecar_path(env)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(
        {"installed_ts": 0.0, "last_daemon_tick_ts": time.time(), "consecutive_failures": 0}
    ), encoding="ascii")
    badge = build_schwab_checker_badge(cfg)
    assert isinstance(badge, SchwabCheckerBadgeVM)
    assert badge.state == "ALIVE"
    assert badge.label.isascii() and badge.title.isascii() and badge.css_class.isascii()


def test_every_base_layout_vm_has_badge_field_with_safe_default():
    from dataclasses import fields
    from swing.web.view_models.metrics.shared import BaseLayoutVM
    from swing.web.view_models.dashboard import DashboardVM
    from swing.web.view_models.pipeline import PipelineVM
    from swing.web.view_models.journal import JournalVM, TradeDrilldownVM
    from swing.web.view_models.watchlist import WatchlistVM
    from swing.web.view_models.error import PageErrorVM
    from swing.web.view_models.config import ConfigPageVM
    from swing.web.view_models.schwab import SchwabSetupVM, SchwabStatusVM
    for vm_cls in (BaseLayoutVM, DashboardVM, PipelineVM, JournalVM, TradeDrilldownVM,
                   WatchlistVM, PageErrorVM, ConfigPageVM, SchwabSetupVM, SchwabStatusVM):
        names = {f.name for f in fields(vm_cls)}
        assert "schwab_checker_badge" in names, vm_cls.__name__
```

- [ ] **Step 2: Run; verify fail** — module + fields absent.

- [ ] **Step 3: Create `schwab_checker_badge.py`**

```python
# swing/web/view_models/schwab_checker_badge.py
"""Web checker-health badge — reads the SAME sidecar via the SAME state
machine as `swing schwab status` (no forked liveness logic). ASCII-only."""
from __future__ import annotations

from dataclasses import dataclass

from swing.integrations.schwab.checker_resilience import (
    checker_liveness_sidecar_path,
    evaluate_liveness_state,
    read_liveness_sidecar,
)


@dataclass(frozen=True)
class SchwabCheckerBadgeVM:
    state: str       # ALIVE | STARTING | DEGRADED | UNKNOWN
    label: str       # short ASCII glyph-free label
    title: str       # hover text (ASCII)
    css_class: str   # ok | info | warn


_BADGE_MAP = {
    "ALIVE":    ("Schwab", "ok"),
    "STARTING": ("Schwab", "info"),
    "DEGRADED": ("Schwab!", "warn"),
    "UNKNOWN":  ("Schwab?", "warn"),
}


def build_schwab_checker_badge(cfg) -> SchwabCheckerBadgeVM | None:
    """Return the badge VM, or None when no sidecar exists (badge hidden:
    sandbox / no Schwab client / tests)."""
    import time
    env = cfg.integrations.schwab.environment
    data = read_liveness_sidecar(checker_liveness_sidecar_path(env))
    if data is None:
        return None
    state, reason = evaluate_liveness_state(data, now_ts=time.time())
    label, css = _BADGE_MAP[state]
    return SchwabCheckerBadgeVM(
        state=state, label=label,
        title=f"Schwab checker: {state.lower()} ({reason})", css_class=css,
    )
```

- [ ] **Step 4: Add the `schwab_checker_badge` field (safe default None) to `BaseLayoutVM` + the 9 Family B VMs**

In `swing/web/view_models/metrics/shared.py` `BaseLayoutVM` (after the existing base fields, all defaulted):
```python
    schwab_checker_badge: "object | None" = None  # SchwabCheckerBadgeVM | None (P14.N7 badge)
```
(Use `object | None` to avoid a circular import in `shared.py`; the template only reads `.label`/`.title`/`.css_class`. If `shared.py` can import the VM without a cycle, prefer the precise type.)

Add the SAME line to each Family B VM dataclass (each is `@dataclass(frozen=True)`; add as a trailing defaulted field, mind any `__post_init__` — the badge needs no validation):
- `swing/web/view_models/dashboard.py` `DashboardVM`
- `swing/web/view_models/pipeline.py` `PipelineVM`
- `swing/web/view_models/journal.py` `JournalVM` AND `TradeDrilldownVM`
- `swing/web/view_models/watchlist.py` `WatchlistVM`
- `swing/web/view_models/error.py` `PageErrorVM`
- `swing/web/view_models/config.py` `ConfigPageVM`
- `swing/web/view_models/schwab.py` `SchwabSetupVM` AND `SchwabStatusVM`

- [ ] **Step 5: Run; verify the fan-out test passes** — `python -m pytest tests/web/test_schwab_checker_badge.py -q`. `ruff check` clean.

- [ ] **Step 6: Commit**

```bash
git add swing/web/view_models/schwab_checker_badge.py swing/web/view_models/metrics/shared.py swing/web/view_models/dashboard.py swing/web/view_models/pipeline.py swing/web/view_models/journal.py swing/web/view_models/watchlist.py swing/web/view_models/error.py swing/web/view_models/config.py swing/web/view_models/schwab.py tests/web/test_schwab_checker_badge.py
git commit -m "feat(web): add the Schwab checker-health badge view-model and base-layout field

A shared helper reads the same liveness sidecar through the same state machine
the CLI uses, returning a small badge or None when no sidecar exists. The field
is added with a safe default to every base-layout view-model so the shared
template never raises on an unrelated route."
```

#### §G.S3.d — populate the badge + render it + CSS

- [ ] **Step 1: Write the failing render test** (append to `test_schwab_checker_badge.py`)

```python
def test_dashboard_renders_badge_when_sidecar_present(tmp_path, monkeypatch, seeded_db):
    cfg, cfg_path = seeded_db
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    p = cr.checker_liveness_sidecar_path(cfg.integrations.schwab.environment)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(
        {"installed_ts": 0.0, "last_daemon_tick_ts": time.time(), "consecutive_failures": 0}
    ), encoding="ascii")
    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "schwab-health-badge" in resp.text


def test_dashboard_hides_badge_when_sidecar_absent(tmp_path, monkeypatch, seeded_db):
    cfg, cfg_path = seeded_db
    monkeypatch.setenv("USERPROFILE", str(tmp_path))
    monkeypatch.setenv("HOME", str(tmp_path))
    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        resp = client.get("/")
    assert resp.status_code == 200
    assert "schwab-health-badge" not in resp.text
```
(Confirm `seeded_db` yields `(cfg, cfg_path)` and that `GET /` builds a `DashboardVM`; mirror an existing dashboard route test.)

- [ ] **Step 2: Run; verify fail** — the badge is not populated/rendered yet.

- [ ] **Step 3: Populate the badge at the primary builders** — add `schwab_checker_badge=build_schwab_checker_badge(cfg)` (import the helper) at:
  - `swing/web/view_models/dashboard.py` `build_dashboard` (the `DashboardVM(...)` construction).
  - `swing/web/view_models/pipeline.py` `build_pipeline` (`PipelineVM(...)`).
  - `swing/web/view_models/journal.py` `_base_banner_fields(conn, cfg)` — add `"schwab_checker_badge": build_schwab_checker_badge(cfg)` to the returned dict (covers JournalVM + TradeDrilldownVM, which spread `**banner`).
  - `swing/web/view_models/watchlist.py` `build_watchlist` (`WatchlistVM(...)`).
  - `swing/web/view_models/config.py` `build_config_vm` (`ConfigPageVM(...)`).
  - `swing/web/view_models/metrics/index.py` `build_metrics_index_vm` (`MetricsIndexVM(...)`).
  - `swing/web/routes/schwab.py` the `/schwab/status` (`:173`) + `/schwab/setup` (`:234`) VM constructions (cfg available from `request.app.state.cfg` via `apply_overrides`).

> **Cascade audit:** `git grep -n "schwab_checker_badge=" -- swing/web` after this step lists exactly the populated builders; the OTHER base-layout VM sites keep the default `None` (badge hidden) in V1 (documented §C.6).

- [ ] **Step 4: Render the badge in `base.html.j2`** (topbar, after the Config link / theme toggle at `:76-80`)

```jinja
    {% if vm.schwab_checker_badge %}
    <a class="schwab-health-badge schwab-health-badge--{{ vm.schwab_checker_badge.css_class }}"
       href="/schwab/status"
       title="{{ vm.schwab_checker_badge.title }}">{{ vm.schwab_checker_badge.label }}</a>
    {% endif %}
```
(ASCII-only markup; `vm.schwab_checker_badge` defaults to `None` everywhere → the `{% if %}` suppresses it. Use `|default(None)` is unnecessary since every base-layout VM now declares the field.)

- [ ] **Step 5: Add CSS** (append to `swing/web/static/app.css`)

```css
/* P14.N7 Schwab checker-health badge (topbar) */
.schwab-health-badge {
  display: inline-block; margin-left: 0.5rem; padding: 0.1rem 0.4rem;
  border-radius: 4px; font-size: 0.75rem; text-decoration: none; font-weight: 600;
}
.schwab-health-badge--ok   { background: #1f7a3d; color: #fff; }
.schwab-health-badge--info { background: #2b6cb0; color: #fff; }
.schwab-health-badge--warn { background: #b03030; color: #fff; }
```

- [ ] **Step 6: Run; verify pass.** ASCII gate on the new markup: the badge `<a>` and CSS are ASCII (`git grep -nP "[^\x00-\x7F]" -- swing/web/static/app.css` shows no NEW non-ASCII; the badge block in base.html.j2 is ASCII — base.html.j2 already contains `🌙`/`⚠`, so do NOT whole-body assert). `ruff check` clean.

- [ ] **Step 7: Commit**

```bash
git add swing/web/view_models/dashboard.py swing/web/view_models/pipeline.py swing/web/view_models/journal.py swing/web/view_models/watchlist.py swing/web/view_models/config.py swing/web/view_models/metrics/index.py swing/web/routes/schwab.py swing/web/templates/base.html.j2 swing/web/static/app.css tests/web/test_schwab_checker_badge.py
git commit -m "feat(web): render the Schwab checker-health badge in the shared topbar

The primary navigation builders populate the badge from the shared helper, and
the topbar renders it when present, linking to the Schwab status page. Pages
with no sidecar (sandbox, tests, no Schwab) carry the default empty badge and
render nothing, so unrelated routes are unaffected."
```

---

### Slice-closer — full suite + gates + return report

**Files:** none (verification + the §I runbook + the return report). No production code.

- [ ] **Step 1: Full fast suite** — `python -m pytest -m "not slow" -q`. READ the actual result; do NOT carry a branch/older count forward (`feedback_no_false_green_claim`). Expected green (prior baseline ~6933 + the new tests).
- [ ] **Step 2: ruff** — `ruff check swing/` clean.
- [ ] **Step 3: Schema gate** — `git grep -n "EXPECTED_SCHEMA_VERSION" swing/data/db.py` shows `= 23`; `git status` shows NO new `swing/data/migrations/00XX_*.sql`; no `chart_renders` / domain write added.
- [ ] **Step 4: L2 source-grep gate** — `python -m pytest tests/integration/test_l2_lock_source_grep.py -q` GREEN (zero new `schwabdev.Client.` call sites vs `bf7e071`); manually confirm A-3 added NO `schwabdev.Client.` line and P14.N7 wraps an existing method.
- [ ] **Step 5: ASCII gate** — `git grep -nP "[^\x00-\x7F]" -- swing/integrations/schwab/checker_resilience.py swing/web/view_models/schwab_checker_badge.py swing/web/static/app.css` returns nothing; the new `render_status` checker line + the badge markup assert `.isascii()` (scoped) in their tests.
- [ ] **Step 6: Trailer gate** — `git log -1 --format='%(trailers)'` == `[]` on every commit; spot-check no `Co-Authored-By` + plain-prose final paragraph.
- [ ] **Step 7: Operator gate** — run the §I runbook; operator confirms S5 (CLI) + S6 (browser badge).
- [ ] **Step 8: Return report** (run §N self-review first).

---

## §H Test surface (sum-check)

| Slice | New test file | Tests | Discriminating assertions |
|------|---------------|-------|---------------------------|
| 1 | `test_app_marketdata_ladder_wiring.py` | ~7 | sandbox → no client/hooks (the ~6900-test safety guarantee); production → both hooks + `app.state.schwab_client`; **daily-bar `(year,5,daily,1)` kwargs reach the ladder**; **scope gate bypasses Schwab for a non-open-trade ticker (zero attempts)**; **provider_tag cooldown after N consecutive `'yfinance'` (the 4th call adds zero attempts)**; **concurrent misses do not slip past cooldown**; cfg-tier creds construct the client without env. |
| 1b | `test_marketdata_header_capture.py` | 2 | unmatched header → KEY list logged once, **VALUE never logged**; known header → no capture, `rate_limit_remaining` populated. |
| 2 | `test_checker_resilience.py` | ~5 | wrap replaced `update_tokens`; **background failure isolated (returns False, no raise) with bounded backoff `[1.0, 2.0]` then recovers**; **forced call propagates**; **seed-origin sets `last_seed_ts` NOT `last_daemon_tick_ts`**; **version `2.5.1` via `importlib.metadata`, NO Client constructed**. |
| 3a | `test_checker_liveness_state.py` | ~8 | **`STALE_THRESHOLD > HEARTBEAT_WRITE_INTERVAL`**; the 6-step precedence incl. **explicit-failure outranks STARTING** + **STARTING expires to DEGRADED past grace** + stale-tick → DEGRADED; reasons ASCII. |
| 3b | `test_schwab_status_checker_liveness.py` | 3 | `render_status` ALIVE / unknown(absent); **the new checker line `.isascii()` (scoped)**. |
| 3c/d | `test_schwab_checker_badge.py` | ~5 | badge None when sidecar absent; ALIVE badge fields ASCII; **EVERY base-layout VM carries the field with a safe default**; dashboard renders `schwab-health-badge` when present, hides it when absent. |

**Total new tests: ~30.** No test constructs a `schwabdev.Client`. No test expects the hook to catch `SchwabRateLimitError`.

**Insufficiency caveat:** the badge string/markup assertions confirm the badge is EMITTED; the operator-witnessed browser render (§I S6) is the BINDING visual gate for the badge.

---

## §I Operator-witnessed gate (test/CLI-driven + a browser leg)

Re-confirm the orchestrator/operator split at executing-plans (`feedback_visual_gate_both_render_and_browser`).

**S1 — suite + lint (orchestrator/DB-side):** `python -m pytest -m "not slow" -q` green; `ruff check swing/` clean. READ the actual numbers (no false-green).
**S2 — schema unchanged:** `EXPECTED_SCHEMA_VERSION == 23`; no new `0024_*.sql`; no domain/`chart_renders` write added.
**S3 (CENTRAL) — L2 source-grep:** `tests/integration/test_l2_lock_source_grep.py` GREEN (zero new `schwabdev.Client.` sites vs `bf7e071`).
**S4 — A-3 production-path + L9:** the Slice 1 tests green — hooks installed under production, absent under sandbox; Schwab scoped to open-trade tickers; sustained `provider_tag='yfinance'` → cooldown (NOT a direct-429 catch — the ladder swallows the 429).
**S5 — P14.N7 + CLI (operator-confirmed):** the Slice 2 DNS-survival test green; operator runs `python -m swing.cli schwab status` and confirms the "Checker:" line renders (UNKNOWN when no web server is running; ALIVE in a healthy production session).
**S6 (NEW — browser leg; operator-driven, BINDING for the badge):** with a sidecar present (either a live production `swing web` session OR a hand-seeded sidecar for a sandbox demo), `python -m swing.cli web`; open `http://127.0.0.1:8080/` and confirm the topbar shows a small "Schwab" health badge (green ALIVE / red DEGRADED), the badge links to `/schwab/status`, no mojibake / no `UnicodeEncodeError` in the console; with the sidecar removed, the badge is absent and all pages still render.
**S7 (optional — if a production Schwab session is available):** operator smoke of the web daily-bar path: load an OPEN-TRADE chart surface under `env=production` + ladder enabled → confirm a `surface='pipeline'` (`pipeline_run_id IS NULL`) `schwab_api_calls` row was written, the chart renders DAILY (not minute) bars, a NON-open-trade chart wrote NO Schwab row (scope gate held), AND — for OQ-10 — read the `swing web` console for the one-time "rate-limit header-name capture" DEBUG line and record the actual Schwab header key list (confirms or refutes a rate-limit-remaining header for the follow-up extractor add).

**Teardown (`feedback_taskstop_does_not_kill_detached_server`):** after S6/S7, find the `swing web` PID via `Get-NetTCPConnection -LocalPort 8080`, `Stop-Process -Force`, and VERIFY the port is free + no straggler `python ... web` processes.

Merge is BLOCKED until the operator confirms S5 + S6.

---

## §J Codex single-chain placement (OQ-8)
- **ONE** adversarial Codex chain, AFTER the plan is written + internally chunk-reviewed, BEFORE executing-plans dispatch. **Run to CONVERGENCE** (zero new crit/major; the ~5-round cap is suspended — `feedback_codex_round_limit_suspended`).
- Transport: copowers v2.0.3 WSL Codex CLI fallback (MCP tools DEAD in the VS Code extension). VERIFY `command -v codex` → `/home/<wsluser>/.local/node22/bin/codex` (confirmed: `codex-cli 0.135.0`). R1: `codex exec -s read-only --skip-git-repo-check -C <worktree> - < <promptfile>`. R2+: `codex exec resume --last -c sandbox_mode="read-only" --skip-git-repo-check -` (`resume` REJECTS `-s` AND `-C`; pre-generate the diff on Windows; tell Codex NOT to run git). PERSIST each round's prompt AND response to `.copowers-findings.md` (v2.0.3 does this; the final `### Verdict` must be readable for QA).
- **Codex watch items:** (1) L2 stays green (zero new `schwabdev.Client.` sites; A-3 reuses the factory, P14.N7 wraps); (2) NO schema (sidecar ephemeral; `surface='pipeline'`); (3) the web-badge base-VM fan-out is COMPLETE (every base-layout VM; the shared helper; no forked liveness logic); (4) the sidecar cross-process correctness + the 6-step precedence + `STALE_THRESHOLD > HEARTBEAT`; (5) the provider_tag-driven cooldown (NOT hook-catches-`SchwabRateLimitError`); (6) OQ-10 no silent-None guess (capture diagnostic only); (7) production-path tests (L7); (8) daily-bar `(year,5,daily,1)` footgun; (9) redaction intact (`_redacted_excerpt`; `setLogRecordFactory`; header-capture logs no values); (10) `threading.Lock` on hook state + DB-read-outside-lock; (11) P14.N7 cleanly removable; (12) ASCII scoped (CLI line + badge) + trailer hygiene; (13) `importlib.metadata` version guard never constructs a Client; (14) seed does NOT advance the heartbeat.
- If a finding needs a schema change or a new call site, STOP + escalate.

---

## §K Schema impact — VERDICT: NO change (v23 held)
- **A-3:** pure cache-hook install + client construction + the L9 closure gates. The audit `surface` reuses `'pipeline'` (`pipeline_run_id=NULL`) — NO new CHECK member (a `'web'` value would collide with the v23 CHECK + the Python guard → would need v24).
- **P14.N7 wrap:** instance-level method replacement. No schema.
- **P14.N7 liveness:** ephemeral on-disk sidecar JSON. No DB table/column.
- **L9c:** the column + extraction + audit-write already exist; the only change is a one-time header-KEY capture log (no schema).
- **Verdict: NO migration. `EXPECTED_SCHEMA_VERSION` stays 23.** S2 asserts no `0024_*.sql`.

---

## §L Fixtures
- **Slice 1 (`test_app_marketdata_ladder_wiring.py`):** the existing `seeded_db` fixture (`(cfg, cfg_path)`, v23 schema-only DB) + a `_production_cfg` helper (dataclasses.replace env→production + ladder enabled) + a `_seed_open_trade(cfg, ticker)` helper inserting one open-`state` `trades` row (derive from an existing open-trade seeder — do NOT hand-roll SQL; synthetic-fixture-vs-emitter drift gotcha). `construct_authenticated_client` monkeypatched to a `MagicMock` (never a live network). The ladder functions monkeypatched per-test to assert kwargs / provider_tag sequences.
- **Slice 1b:** pure stub `_Resp` objects (headers dict + `.json()`); no DB. Reset the once-per-process flag via `_reset_header_capture_for_tests`.
- **Slice 2:** pure `_FakeTokens`/`_FakeClient` (no schwabdev import, no network); `time.sleep` monkeypatched to a recorder; the sidecar path injected under `tmp_path` (no `_user_home` monkeypatch needed — path is direct). Version guard via `importlib.metadata`.
- **Slice 3a:** pure dicts → `evaluate_liveness_state`; no DB.
- **Slice 3b/c/d:** a `status_cfg_conn` fixture (sandbox cfg + v23 conn; mirror an existing `cli_schwab` status test) + `seeded_db`; the sidecar hand-seeded under `tmp_path` with `USERPROFILE`+`HOME` BOTH monkeypatched (gotcha); `with TestClient(app) as client:` for the render tests (lifespan).

---

## §M Forward-binding lessons (for executing-plans)
1. **Re-grep anchors at IMPLEMENT time (STEP 0).** The §B anchors were verified at `c7a8df3`; confirm before writing. Notable verified facts: `get_or_fetch(*, ticker, window_days=180)` is keyword-only; the ladder fetcher runs at `price_cache.py:151` (worker) + `ohlcv_cache.py:217/437`; `circuit_breaker_cooldown_seconds=60`; the ladder swallows the 429 at `marketdata_ladder.py:317`.
2. **The hook NEVER sees `SchwabRateLimitError`** — the ladder swallows it and returns `provider_tag='yfinance'`. The cooldown keys on the observed `provider_tag`, never on catching the 429. Do NOT write a 429-catch test.
3. **Thread-safety:** `_WebLadderState` is touched by executor workers AND request threads. Guard the memo/counter/cooldown with the lock; do the open-trade DB read OUTSIDE the lock (double-checked).
4. **Seed ≠ heartbeat:** the seed call runs on the startup thread → `origin='seed'` → sets `last_seed_ts`, NOT `last_daemon_tick_ts`. Otherwise `status` would show false-ALIVE for a dead-at-tick-1 daemon.
5. **`update_tokens` does NOT raise on auth failure** — verify post-call `access_token` presence; a claimed refresh with no token records DEGRADED.
6. **Version guard via `importlib.metadata.version("schwabdev")` — NEVER construct a `Client`** (spawns a checker daemon + needs creds/network).
7. **Sidecar atomicity:** `tempfile.mkstemp(dir=<dest parent>)` + `os.replace` (same filesystem; Windows-safe). `mkdir(parents=True, exist_ok=True)` first.
8. **ASCII scope:** the CLI checker line + the badge markup are ASCII; assert `.isascii()` on the NEW substring only (base.html.j2 + render_status already carry non-ASCII elsewhere).
9. **base.html.j2 reads only `vm.*`** — the badge field must exist (safe default) on EVERY base-layout VM (Family A base + 9 Family B); the cascade-grep test guards it.
10. **OQ-10:** do NOT add a guessed header name (it would stay `None`). The capture diagnostic confirms the real name at S7; the candidate-add is a follow-up.
11. **Startup race (accepted narrow residual):** the checker's first tick can run before the wrap installs; the seed mitigation closes most of it but a dead-at-tick-1 daemon under a near-expiry token surfaces as STARTING→DEGRADED (never false-ALIVE) + an operator restart. Documented, NOT fully closed (V2: construction-window class patch).
12. **schwabdev `update_refresh_token()` path:** a non-force background call with `rt_delta < 1800` (refresh token near its 7-day expiry) tries `update_refresh_token()` which calls `input()` — in a daemon thread with no stdin this raises (e.g. `EOFError`), which the wrap catches and records as DEGRADED (surfaced via liveness; operator re-auths). The wrap does NOT attempt to drive the OAuth `input()` dance.

---

## §N Self-review (run against the spec before Codex)
**1. Spec coverage:** §1 architecture/coupling → §C.1; §2 LOCKs → §E; §4 A-3 full-parity + L9 (4.5.1-4.5.5) → §C.2 + Slice 1; §4.5.4 L9c → §C.3 + Slice 1b; §5 P14.N7 (5.1-5.6 wrap/liveness/state machine/version guard/startup race) → §C.4/§C.5 + Slice 2/3 + §M.11; §6 L2 framing → §E + S3; §7 sandbox+audit (`surface='pipeline'`) → §C.1/§K; §8/§11 no schema → §K; §9 slices → §G (1·1b·2·3); §10 fixtures/gate → §L/§I; §13 OQs → §E; §14 disciplines → §F. The OQ-6 web-badge ADD (beyond the spec's CLI-only) → §C.6 + Slice 3c/d + S6. No gap.
**2. Placeholder scan:** every code step shows complete code; no "TBD"/"similar to". The base-VM fan-out enumerates all 10 classes; the population sites are enumerated.
**3. Type/name consistency:** `install_resilient_checker` / `CheckerLiveness` / `evaluate_liveness_state` / `checker_liveness_sidecar_path` / `read_liveness_sidecar` / `write_liveness_sidecar` identical across Slices 2/3 + app.py; `build_schwab_checker_badge` / `SchwabCheckerBadgeVM` consistent VM↔template; `_WebLadderState.should_use_schwab` / `.note_provider` consistent; provider tags `'schwab_api'`/`'yfinance'` consistent; constants `HEARTBEAT_WRITE_INTERVAL`/`STALE_THRESHOLD`/`STARTUP_GRACE`/`_WEB_LADDER_FALLBACK_COOLDOWN_THRESHOLD` referenced consistently.

---

## §O Phase 14 close-out position note
SB5.5 is the FIRST item of the operator-LOCKed Phase 14 close-out tail. Sequence: **SB5.5 (this) → close-out polish batch (P14.N1-dashboard + A-1 `market_weather` 200MA + A-2 vcp crowding + A-4 `_bulz_*` rename + A-6 process-grade dark-mode chart + group-(a) minor advisories) → B-7 operator failure-mode classification → Phase 14 close-out review (Sec 9.1 Q6).**

**Schema verdict for SB5.5:** lands at **v23** (no schema). L2 LOCK preserved (source-grep green; NO re-anchor). The ~700+ commit ZERO Co-Authored-By streak preserved.

**Banked follow-ups created by SB5.5 (V1 simplifications — for the return-report ledger):**
- OQ-10 extractor candidate-name addition once the actual Schwab rate-limit header name (or its absence) is confirmed at the S7 smoke.
- Web-badge population broadening to the remaining base-layout surfaces (pattern review/queue, reconcile, account, per-metric drilldowns) — V1 carries the field at default `None` there.
- A dedicated `surface='web'` audit value (needs a future schema phase).
- An app-wide cross-process Schwab-budget governor (V2).
- The checker startup-race full closure (construction-window class patch) — V2.
- The Phase-15 schwabdev v3 upgrade obsoletes the checker + deletes P14.N7.

**Executing-plans dispatch-readiness:** ONE executing-plans bundle (Slice 1 → 1b → 2 → 3, serial), ~30 new tests, read-mostly on the trade/Schwab surface, NO schema, ONE Codex chain to convergence after the plan converges. The operator gate (S5 CLI + S6 browser badge) is merge-blocking.

---

*End of plan. A-3 installs the existing production-gated market-data ladder on the long-lived web caches at full parity (mirroring `_install_pipeline_marketdata_caches`), bounded by the L9 open-trade-scope + TTL + provider_tag-driven cooldown gates under a `threading.Lock`; P14.N7 wraps the schwabdev checker token-refresh with exception-isolation + bounded backoff and surfaces liveness via an ephemeral cross-process sidecar read by BOTH `swing schwab status` AND a new web health badge through one shared state machine. NO schema (v23 held); ZERO new `schwabdev.Client.*` call sites; the OQ-10 rate-limit header name is confirmed empirically at the production smoke, never guessed; P14.N7 is a cleanly-removable Phase-15 guard.*
