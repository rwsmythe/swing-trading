# Phase 14 Sub-bundle 5.5 (Schwab-focused) -- Design Spec

**A-3 web market-data ladder wiring (sanctioned L2 extension, full parity, rate-limit-aware) + P14.N7 schwabdev checker-thread resilience**

- **Date:** 2026-05-31
- **Phase:** 14, Sub-bundle 5.5 -- the FIRST item of the operator-LOCKed close-out tail (SB5.5 -> close-out polish batch -> B-7 -> Sec 9.1 Q6 close-out review).
- **Brief:** `docs/phase14-sub-bundle-5-5-schwab-brainstorming-dispatch-brief.md` (note section 1.0 operator rulings + L9, added at base `ea0d69c`).
- **Worktree base HEAD:** `ea0d69c` (records the 2026-05-31 operator rulings; supersedes the brief's section 9 base `f274dd8` -> `f2b102c` -> `ea0d69c`).
- **Schema:** v23 LOCKED. `EXPECTED_SCHEMA_VERSION = 23` (`swing/data/db.py:51`). This spec confirms **NO migration** (NO v24).
- **Posture:** infrastructure + resilience on the Schwab integration surface. A-3 is an **operator-SANCTIONED L2 extension** (deliberate move to Schwab's better data provenance over yfinance on the web path) -- designed as intended, NOT held. The hard L2 requirement is the only one that remains: **zero NEW `schwabdev.Client.*` call SITES** (reuse the existing ladder; `tests/integration/test_l2_lock_source_grep.py` baseline `bf7e071` stays green). The new runtime Schwab-call surface is the approved part. The rate-limit-aware constraint (L9) is now the governing runtime design driver for A-3.

---

## Section 1 -- Architecture overview

Sub-bundle 5.5 is two coherent infrastructure items on a single shared surface: the **Schwab market-data integration as it behaves inside the long-lived `swing web` process**. Both are "wire / wrap the EXISTING machinery," not "build new machinery."

### 1.1 The two items

- **A-3 -- install the EXISTING market-data ladder onto the web caches (FULL PARITY).** Today the pipeline routes its quote + daily-bar fetches through the Schwab->yfinance ladder (`swing/integrations/schwab/marketdata_ladder.py`), but the **web** caches (`PriceCache`/`OhlcvCache`, constructed plain at `swing/web/app.py:188-189`) have **no ladder hooks installed** -- the web SMA / daily-bar / last-close path is **yfinance-only by wiring**. A-3 mirrors the pipeline's `_install_pipeline_marketdata_caches` (`swing/pipeline/runner.py:305-468`): construct a web Schwab client via the EXISTING factory, install the EXISTING `set_ladder_fetcher` (quote) + `set_ladder_bars_fetcher` (daily bars) hooks on BOTH web caches (operator ruling OQ-2: full parity -- daily bars + SMA path + last-close quote), gated by the EXISTING ladder predicate (`env == 'production' AND marketdata_ladder_enabled`), and **bounded by the L9 rate-limit-aware constraints** (section 4.5).

- **P14.N7 -- make the schwabdev background `checker` thread survive transient network failure.** schwabdev's `Client.__init__` spawns a `daemon=True` `checker` thread (`schwabdev/client.py:50-56`) whose body is `while True: self.tokens.update_tokens(); time.sleep(30)`. An uncaught `ConnectionError` / `NameResolutionError` raised by `update_tokens()` during a sleep/wake/DNS-loss cycle **kills the thread** -> **silent token-refresh degradation until `swing web` restart**. P14.N7 wraps the refresh call with exception-isolation + bounded backoff so the loop survives, records a liveness signal, and surfaces it via `swing schwab status`.

### 1.2 Why they belong in ONE sub-bundle (the coupling)

The checker-death problem **only manifests for a long-lived client**. The CLI subcommands construct a client, do one operation, and exit (their daemon checker dies harmlessly with the process). The pipeline holds a client only for the minutes of a run. **There is no long-lived Schwab client in the project today** -- so P14.N7 has no host process to protect... **until A-3 installs one for the life of `swing web`.** A-3 *creates the exact condition* P14.N7 *fixes*. They share one web Schwab client (sections 2.3 / 7.4): that one client feeds both the ladder hooks (A-3) and the resilient checker (P14.N7). Shipping them together is correct. (Both also draw on the same ~120-calls/min app-wide budget -- section 4.5 / 6.3.)

### 1.3 The shared Schwab-client lifecycle under `swing web`

```
swing web (process start)
  create_app(cfg)                                  swing/web/app.py
    PriceCache(cfg) / OhlcvCache(cfg)              app.py:188-189   (existing, plain)
    [A-3] _install_web_marketdata_caches(cfg, ...) (NEW; mirrors runner.py:305-468)
       if _is_ladder_active(cfg) and creds present:
         client = construct_authenticated_client(...) auth.py:694  (EXISTING factory)
         [P14.N7] install resilient checker wrap on client.tokens.update_tokens
         price_cache.set_ladder_fetcher(_quote_hook)    price_cache.py:75
         ohlcv_cache.set_ladder_bars_fetcher(_bars_hook) ohlcv_cache.py:112
         # both hooks consult the L9 open-trade-scope gate + Schwab-cooldown gate
         app.state.schwab_client = client            (one client; daemon checker runs)
       else:
         plain yfinance caches (no client, no ladder, no checker)  <- DEFAULT / sandbox / tests
  ... server serves requests; ladder fires for OPEN-TRADE tickers only (L9), TTL-cached ...
  ... schwabdev checker thread ticks every 30s for process life; wrap records liveness ...
  ... liveness -> ephemeral sidecar (section 5.4) ...

swing schwab status (SEPARATE process)              cli_schwab.py:1426 / render_status:790
  reads the ephemeral liveness sidecar + renders a checker-liveness line
```

The critical architectural fact embedded above: **`swing schwab status` runs in a different OS process from `swing web`.** Pure in-process memory liveness is invisible to it. That cross-process gap is a design tension (section 5.4 / OQ-9) the brief's "in-memory/ephemeral" phrasing did not anticipate.

---

## Section 2 -- Pre-locked decisions (do not re-litigate)

### 2.1 Operator rulings (brief section 1.0; 2026-05-31; BINDING)
- **OQ-1 RESOLVED -- A-3 is a SANCTIONED L2 EXTENSION.** The web-side ladder wiring is a deliberate expansion of Schwab usage for better data provenance over yfinance -- NOT an accidental L2 violation, NOT held. Design A-3 as intended. The L2 source-grep test still MUST stay green (zero NEW `schwabdev.Client.*` call SITES); the runtime-surface expansion is the approved part.
- **OQ-2 RESOLVED -- FULL PARITY.** A-3 wires ALL pipeline market-data consumers on the web path -- daily bars (`chart_jit` -> `OhlcvCache.get_or_fetch`) + the SMA path + the last-close quote (`PriceCache`). Match the pipeline's install surface.
- **Schwab rate limit (web-verified): ~120 API calls/minute, APP-WIDE** (shared across Market Data + Accounts/Trading endpoints), HTTP 429 on breach (~2 req/sec). Shared by web + pipeline + account/reconciliation ops + the schwabdev checker -- NOT a dedicated web budget. Treat as the working number; re-confirm at writing-plans if Schwab revises.

### 2.2 Sec 9.1 commissioning LOCKs
- **Q2 SERIAL** -- SB5.5 is its own copowers cycle, after SB5 (`6206fb6`), before the close-out polish batch.
- **Q6 operator-witnessed verification at merge** -- but SB5.5 is infrastructure/resilience, NOT a visual surface. The gate is test/CLI evidence (section 10), with operator confirmation of the `swing schwab status` checker-liveness output and (if a production session is available) an optional smoke of the web daily-bar ladder path.
- **Q7 Codex chain count = orchestrator discretion -> SINGLE chain** for this brainstorming, run to convergence (the ~5-round cap is suspended for this project).

### 2.3 SB5.5 phase-specific LOCKs (brief section 1.2)
- **L1 Scope = A-3 + P14.N7 ONLY.** No new Schwab features, market-data sources, metrics, or UX. No widening to the close-out polish batch / B-7 / Phase 15+.
- **L2 (the one hard requirement) Zero NEW `schwabdev.Client.*` call SITES** vs baseline `bf7e071` (`tests/integration/test_l2_lock_source_grep.py` stays green). A-3 INSTALLS the existing ladder (its Schwab calls are pre-existing) via the EXISTING factory; P14.N7 WRAPS the existing checker (adds no API calls). The runtime-surface expansion is operator-sanctioned (section 2.1).
- **L3 NO schema change** (v23 held). A-3 is pure wiring; P14.N7 liveness is ephemeral/non-DB (section 5.4). The audit `surface` value reuses an EXISTING enum member (`'pipeline'`) -- NO new CHECK value, NO v24 (section 7.2).
- **L4 Sandbox-gating + the inside-the-ladder short-circuit PRESERVED.** Under `env != production` OR `marketdata_ladder_enabled == False`, the web path falls through to yfinance EXACTLY as the pipeline does (audit rows only on the schwab path; ZERO domain Schwab calls under sandbox). The web ladder install inherits the ladder's own gate -- it does NOT re-implement a looser one.
- **L5 REUSE, do not re-implement.** A-3 mirrors `_install_pipeline_marketdata_caches` + the existing `set_ladder_*_fetcher` hooks + the existing ladder functions + the existing TTL caches + circuit breakers. P14.N7 wraps schwabdev's existing checker. NO new ladder, NO new client-construction path, NO new market-data fetcher. (The L9 scope-gate + Schwab-cooldown gate live INSIDE A-3's new hook closures -- the part A-3 writes anyway -- not as a new fetcher; section 4.5.)
- **L6 Audit + redaction discipline.** A-3's web ladder calls record `schwab_api_calls` audit rows (`surface='pipeline'`, `pipeline_run_id=NULL`; section 7.2); the schwabdev log-redaction `setLogRecordFactory` (capital-S `"Schwabdev"`) stays intact; P14.N7's checker wrap leaks no tokens in retry/health logging (uses `_redacted_excerpt`).
- **L7 Production-path test discipline (gotcha #15).** The A-3 wiring test exercises the REAL `app.py` cache construction (assert ladder hooks installed on `app.state.ohlcv_cache`/`price_cache` under production; yfinance fall-through under sandbox), NOT a stubbed cache. The P14.N7 test simulates a DNS failure during refresh and asserts the checker survives + liveness reflects degraded->recovered.
- **L8 No new web-render / HTMX surface.** P14.N7 liveness is CLI-surfaced via `swing schwab status`. A web health badge is a deferred OQ (OQ-6) -- CLI-only for V1.
- **L9 (rate-limit-aware; BINDING for full-parity A-3).** The ~120-calls/min APP-WIDE shared budget is the runtime constraint. The web ladder install MUST: (a) ride the EXISTING TTL cache + an open-trade fetch scope so Schwab calls are bounded (one fetch per `(ticker, window_days)` per TTL; open-trade-scoped -- NOT per-render, NOT universe-wide); (b) treat HTTP 429 + any transient miss as a fall-through to yfinance (F6) + a breaker/cooldown trip, NEVER a hammering retry; (c) SHOULD make the existing `rate_limit_remaining` audit field observable from Schwab response headers. The failure mode to design against is a render-storm that bypasses the cache (section 4.5).

---

## Section 3 -- Module touch list

> All anchors ORCHESTRATOR-VERIFIED on the worktree at `ea0d69c`. Re-grep at writing-plans per orchestrator-context discipline #2 (signatures shift). **Brief-vs-production corrections flagged inline.**

### 3.1 A-3 -- web ladder install
- **`swing/web/app.py`** -- MODIFY. Caches constructed plain at `app.py:188-189` inside `create_app(cfg, cfg_path)` (NOT in the `lifespan` at `app.py:138-149`; lifespan owns only `price_fetch_executor`). A-3 adds a NEW module-private helper `_install_web_marketdata_caches(cfg, price_cache, ohlcv_cache) -> client_or_None` invoked immediately after the cache construction, mirroring the pipeline. Holds the client at `app.state.schwab_client` (None when no ladder).
- **`swing/pipeline/runner.py:305-468`** -- READ-ONLY reference (the pattern to mirror). **CORRECTION:** the brief calls this `_build_caches_with_ladder` at "lines 308-327"; the actual function is **`_install_pipeline_marketdata_caches`** spanning **305-468** (308-327 is its docstring). The brief's quote/bars-hook anchors (`set_ladder_fetcher` / `set_ladder_bars_fetcher`) are correct. The construction call site is `runner.py:781-787`; the graceful-degradation client factory wrapper is `_construct_pipeline_schwab_client` (`runner.py:203-302`).
- **`swing/integrations/schwab/auth.py:694`** -- READ-ONLY reuse. `construct_authenticated_client(cfg, environment, client_id, client_secret)` is the SINGLE schwabdev.Client(...) construction path (+ `setup_paste_flow` + `force_refresh` in the same module). A-3 calls this; it adds NO new `schwabdev.Client.` call site.
- **`swing/integrations/schwab/marketdata_ladder.py`** -- READ-ONLY reuse: `fetch_quote_via_ladder:264`, `fetch_window_via_ladder:358`, `_is_ladder_active:221` (the `env=='production' AND marketdata_ladder_enabled` gate). The ladder already catches `SchwabRateLimitError` (429) -> yfinance fallback (`:317`).
- **`swing/web/price_cache.py:75`** + **`swing/web/ohlcv_cache.py:112`** -- READ-ONLY reuse (the hook setters already exist; A-3 calls them). Both caches already own a TTL + a sliding-window circuit breaker (`price_cache.py:271 _maybe_trip_breaker`; `ohlcv_cache.py` breaker; `cfg.web.price_cache_ttl_seconds` defaults to **120s**, `cfg.web.ohlcv_cache_ttl_seconds` to **3600s** -- `swing/config.py:353`/`:360`).
- **`swing/web/chart_jit.py:71` (`get_or_render_surface`) -> `:117` (`ohlcv_cache.get_or_fetch(ticker, window_days=200)`)** -- READ-ONLY: the per-request daily-bar consumer (arbitrary ticker -- the render-storm surface the L9 scope-gate defends).
- **`swing/data/repos/trades.py:375` (`list_open_trades`)** -- READ-ONLY: the open-trade ticker source for the L9 scope-gate (section 4.5).
- **`swing/integrations/schwab/marketdata.py:101-144` (`_extract_response_payload`)** -- READ-ONLY (L9c): already extracts `rate_limit_remaining` from response headers and the success path already passes it to the audit row (`:643`). The L9c work is verifying/correcting the header NAME (section 4.5.3), not building plumbing.

### 3.2 P14.N7 -- checker resilience + liveness
- **NEW module `swing/integrations/schwab/checker_resilience.py`** (recommended boundary; section 5) -- the resilient-wrap installer + the in-memory liveness record + the ephemeral-sidecar writer. Single clear purpose, instance-level, testable without a live network.
- **`swing/cli_schwab.py:790` (`render_status`)** -- MODIFY: add a "Checker liveness" line/section reading the ephemeral sidecar. **CORRECTION confirmed:** the command is `schwab_status` at **`cli_schwab.py:1426`** (READ-ONLY surface, no Client construction); it calls `render_status` (`:790`). The sidecar path mirrors the tokens path it already builds: `_user_home() / "swing-data" / f"schwab-checker-liveness.{env}.json"` (cf. `schwab-tokens.{env}.db` at `cli_schwab.py:1447`).
- A-3 + P14.N7 share the web client (section 2.3): the resilient wrap is installed on the SAME client A-3 constructs.

### 3.3 Tests
- **`tests/web/test_app_marketdata_ladder_wiring.py`** -- NEW (A-3; L7 production-path + L9 scope-gate + daily-bar-kwargs).
- **`tests/integration/schwab/test_checker_resilience.py`** -- NEW (P14.N7 DNS-survival + liveness state machine).
- **`tests/cli/test_schwab_status_checker_liveness.py`** -- NEW (P14.N7 render).
- **`tests/integration/test_l2_lock_source_grep.py`** -- UNCHANGED; MUST stay green (the gate).

---

## Section 4 -- A-3 web-ladder-install design (full parity, rate-limit-aware)

### 4.1 The mirror

`_install_pipeline_marketdata_caches` (`runner.py:305-468`) is the template. Its shape:
1. If `schwab_client is None` -> return plain caches (no hooks).
2. Else construct `PriceCache`/`OhlcvCache`, define `_quote_hook` (closes over `cfg`, `schwab_client`, `surface`, `pipeline_run_id`; opens a fresh `conn` per call; calls `fetch_quote_via_ladder`) and `_bars_hook` (calls `fetch_window_via_ladder` with **explicit daily-bar kwargs** `period_type='year', period=5, frequency_type='daily', frequency=1` -- the minute-default footgun guard), install both hooks.
3. The sandbox short-circuit lives INSIDE the ladder (`_is_ladder_active`), so the helper installs hooks unconditionally **once a client exists**; under sandbox the hooks fall through to yfinance with ZERO audit rows.

The web equivalent (`_install_web_marketdata_caches`) is the same code with four differences: (1) client source = the graceful-degradation factory (section 4.3); (2) `pipeline_run_id=None`; (3) `surface='pipeline'` (section 7.2 -- reuse, no schema); (4) the L9 gates inside the hook closures (section 4.5).

### 4.2 Daily-bar footgun guard (gotcha, BINDING)

The bars-hook MUST pass explicit `(year, 5, daily, 1)` kwargs to `fetch_window_via_ladder`, exactly as `runner.py:448-452` does. Without them schwabdev defaults to `(day, 10, minute, 1)` = ~3000 1-minute intraday candles, which contaminate the chart render with duplicate-timestamp / per-minute-volume / 00:00-label corruption (the operator-witnessed S3 regression at Phase 13 T1.SB0). Reusing the pipeline's `_bars_hook` verbatim inherits the guard; the L7 production-path test asserts the kwargs reach the ladder.

### 4.3 Web client construction (graceful degradation; mirror `_construct_pipeline_schwab_client`)

The web app must tolerate every Schwab construction failure without crashing (a dashboard with a stale tokens DB must still serve pages on the yfinance path). **Credential resolution MUST use the SAME resolver as the pipeline (Codex R1 Major #5): `resolve_credentials_env_or_prompt(cfg, environment, allow_prompt=False)` (`runner.py:249`), which honors the full env > cfg-tier (`user-config.toml`) cascade -- NOT env vars only.** The original draft said "env-var credentials," which would silently give yfinance-only behavior to operators who store CLIENT_ID/SECRET in `user-config.toml` despite production + ladder enabled. The branches:
- Resolver returns no credentials (neither env nor cfg) -> `None` SILENTLY (default posture; preserves the yfinance-only web app for operators not using Schwab).
- Resolver raises `SchwabConfigMissingError` (partial / one tier incomplete) -> WARN (naming present/absent, no secret bytes) + `None`.
- Construction failure (`SchwabAuthError` / `OSError` / `sqlite3.DatabaseError` / network / etc.) -> single redacted WARN (`_redacted_excerpt`) + `None`. The widened `except Exception` boundary mirrors `runner.py:275`.
- A `None` client -> plain caches (no hooks) -> the web app is exactly today's yfinance-only behavior.

**Test-safety consequence (important):** `create_app` is called once per `TestClient`. Gating client construction behind `_is_ladder_active(cfg)` (production env + ladder enabled) AND credential presence means the **default sandbox test config constructs NO client, spawns NO checker thread, and hits NO network** -- the ~6900 fast tests are unaffected by A-3. This is the same gate the pipeline already relies on.

### 4.4 Consumer breadth -- FULL PARITY (operator-LOCKed OQ-2)

Install BOTH hooks, matching the pipeline:
- **Quote-hook -> `PriceCache.set_ladder_fetcher`** feeds last-close / live price (dashboard open-position prices; `PriceCache.get` / `get_many`).
- **Bars-hook -> `OhlcvCache.set_ladder_bars_fetcher`** feeds daily bars -> SMA computation + `chart_jit.get_or_fetch` daily-bar charts.

Both are governed by the L9 gates (section 4.5) so full parity does NOT mean uncontrolled call volume.

### 4.5 L9 rate-limit-aware design (the governing runtime driver)

The ~120-calls/min budget is **app-wide and shared** (web + pipeline + account ops + checker). Full-parity web wiring on a demand-driven request surface is the new variable. The defenses below all reuse existing machinery. **Design honesty note (Codex R1):** the per-`(ticker, window_days)` de-duplication is owned by the EXISTING caches, NOT by the hook (the hook contract is `Callable[[str], ...]` -- ticker only; `ohlcv_cache.py:112`); the hook's job is the open-trade scope + a fallback-cooldown. The L9(a) brief language ("one fetch per `(ticker, window_days)` per TTL") describes the CACHE's keying, which the install rides -- it is not a claim about the hook signature.

**4.5.1 Open-trade fetch scope (the render-storm defense -- primary).** The web call surface is diffuse: `chart_jit.get_or_render_surface(ticker=...)` fires `OhlcvCache.get_or_fetch` for ANY ticker a chart page renders (`ticker_detail`, `position_detail`, watchlist thumbnails, `market_weather`), and `PriceCache` can be asked for arbitrary tickers. A render-storm (many distinct chart pages loaded quickly, e.g. a crawler or a power-user click-through) would each be a cache miss -> a Schwab call -> budget exhaustion / 429. The pipeline avoids this because its callers (`build_dashboard` / `_step_charts`) pre-scope OHLCV to `sorted({t.ticker for t in open_trades})` (the OHLCV fetch-scope gotcha). The web has no single choke-point caller, so the scope gate moves INTO the hook closures:

> Each web hook consults `_should_use_schwab(ticker)`: True iff `ticker.upper()` is in the current open-trade ticker set (from `list_open_trades(conn)`, memoized with a short TTL -- e.g. 60s -- to avoid a DB hit per call). When True -> attempt the Schwab ladder. When False -> bypass Schwab and return the yfinance fallback directly (NO Schwab call, NO audit row).

Effect: Schwab calls are bounded to a small multiple of the open-trade count per TTL window, regardless of render volume. A storm of non-open-trade chart loads never touches Schwab; a storm of open-trade loads is bounded by the small open-trade count + the TTL cache. This is the literal "open-trade fetch scope -- NOT per-render, NOT universe-wide" the operator specified, and it is the primary design-against-render-storm requirement.

**Thread-safety (Codex R2 Major #1; BINDING).** The hooks run concurrently from BOTH executor worker threads (`price_cache.py:367`, `ohlcv_cache.py:334`/`:437`) AND request paths (`ohlcv_cache.py:217`). The open-trade-set memo, the consecutive-fallback counter, and the cooldown timestamp (4.5.2) are shared mutable hook state -> they MUST be guarded by a `threading.Lock` held by the hook closures (or stored in a small thread-safe state object), or concurrent cache misses can race past the cooldown gate and over-issue Schwab calls. The writing-plans test matrix adds a concurrent-miss test (multiple threads invoking the hook simultaneously while the cooldown is set -> assert no Schwab attempt slips through).

**4.5.2 429 / Schwab failure -> yfinance + cooldown, never a hammering retry (CORRECTED per Codex R1 Critical #1).** The ladder catches `SchwabRateLimitError` (429), `SchwabAuthError`, `SchwabApiError` INTERNALLY and returns the yfinance fallback with `provider_tag='yfinance'` (`marketdata_ladder.py:317-347`, `:447`). **No 429 exception escapes to the hook** -- so the web cooldown CANNOT key on catching a `SchwabRateLimitError` (the original draft's mistake). The concrete observable signal the hook DOES receive is the `provider_tag` the ladder returns. The corrected design:
- **TTL cache as the primary natural backoff:** a yfinance fallback result is cached by the cache for its TTL, so the same cache key is NOT re-attempted against Schwab until the TTL expires. No tight retry can occur on a single cache key.
- **Consecutive-fallback cooldown (closure-local; provider_tag-driven):** the hook counts consecutive `provider_tag == 'yfinance'` returns observed *while the ladder is active and a client is present* (i.e. Schwab was attempted and fell through, for ANY reason -- 429, auth, partial, network). After N consecutive such fallbacks it sets a closure-local `_schwab_cooldown_until = monotonic() + cfg.web.circuit_breaker_cooldown_seconds`; while in cooldown, `_should_use_schwab` returns False for ALL tickers, pinning the web path to yfinance for the window. This implements the L9(b) "back off, don't hammer" intent using a signal the hook actually has; it does NOT distinguish 429 from other Schwab failures, which is acceptable -- any sustained Schwab failure warrants backing off. A few lines in the hook closure (the part A-3 writes), NOT a new fetcher and NOT a ladder change (L5 preserved).
- **NO retry/backoff on the market-data path.** Bounded backoff exists ONLY in P14.N7's checker wrap (a once-per-30s daemon loop), NEVER on a request-serving market-data fetch.

**4.5.3 No app-wide governor in V1 -- explicit residual risk (Codex R1 Major #3).** The closure-local cooldown is per-`swing web`-process; it cannot see pipeline / CLI / account-op / checker traffic against the shared 120/min budget, and it reacts only AFTER the web path itself observes fallbacks. **V1 explicitly accepts no app-wide governor.** The residual risk: a nightly pipeline run concurrent with heavy web open-trade traffic could jointly approach the budget; each surface only backs off after it individually sees failures. This is tolerable for V1 because (a) the open-trade scope keeps the web's steady-state contribution tiny (4.5.5), (b) the pipeline is open-trade-scoped too and runs off-hours, and (c) a 429 anywhere degrades gracefully to yfinance (never an error to the operator). A true shared cross-process token-bucket governor is the stronger design and is deferred to V2 (section 12). **Gate addition:** a concurrent-load failure-mode note in the writing-plans test matrix (simulate web + pipeline both fetching the same open ticker under an active ladder; assert both degrade to yfinance without raising and without unbounded retry).

**4.5.4 `rate_limit_remaining` observability (L9c -- SHOULD).** **Brief-vs-production correction:** the brief says the `rate_limit_remaining` audit field (`audit_service.py:127`) is "currently always None." In fact `marketdata.py:_extract_response_payload` (`:101-144`) ALREADY reads the header and the success + HTTP-failure audit-close paths ALREADY pass the value (`:564`, `:643`); `audit_service.py:127` is just the pass-through parameter. The reason it resolves to `None` in production is almost certainly a **header-name mismatch** -- the extractor tries `X-RateLimit-Remaining` / `X-Rate-Limit-Remaining` / `Schwab-Client-RateLimit-Remaining`, which may not be the header Schwab actually emits. L9c therefore reduces to a small, SHOULD-tier fix: confirm Schwab's actual rate-limit header name (live header inspection / Schwab docs at writing-plans) and add it to the extractor's candidate list so the EXISTING plumbing captures real headroom. No new audit write-path, no schema. If the header name cannot be confirmed without a live production session, defer the exact name to the writing-plans/executing-plans gate and land the extractor change behind the confirmed name (do NOT guess a name that silently stays None).

**4.5.5 Budget headroom sketch (corrected per Codex R1 Major #1 + Minor #1).** With the open-trade scope gate, web Schwab traffic per open ticker per TTL window is bounded by the cache structure, NOT one-call-per-ticker. `OhlcvCache` has TWO independent stores that both invoke the bars hook: `_bars_store` keyed by `(ticker, window_days)` via `get_or_fetch` (`ohlcv_cache.py:172`) and `_store` keyed by ticker via `get_many_bundles` (`:436`). So one open ticker can incur up to ~2 bars fetches (one per store, per its respective TTL) plus 1 quote fetch via `PriceCache`. The TTLs differ: `ohlcv_cache_ttl_seconds` defaults to 3600s; `price_cache_ttl_seconds` defaults to **120s** (`swing/config.py:353`/`:360`) -- so quote traffic refreshes more often than bars. Worst-case steady-state per hour from the web path is roughly `open_trades x (2 bars per their TTLs + ~30 quotes at the 120s price TTL)`. For a realistic handful of open trades (<10) this is still on the order of low-hundreds of calls per HOUR -- well under the 120/MINUTE budget -- and the render-storm spike (the real risk) is closed by 4.5.1. Writing-plans should re-state this with the live TTL values and the open-trade count assumption.

### 4.6 Failure / degrade behavior

Inherited from the ladder unchanged on the Schwab path: Schwab miss (auth / rate-limit / partial-response / unexpected) -> redacted WARN -> yfinance fallback. The F6 transient-empty discipline (never overwrite cached content with an empty external response) lives in the cache / archive layer and is unchanged by A-3.

---

## Section 5 -- P14.N7 checker-resilience design

### 5.1 The exact failure (root cause, verified in schwabdev 2.5.1 source)

`schwabdev/client.py:50-56`:
```python
def checker():
    while True:
        if self.tokens.update_tokens() and use_session:
            self._session = requests.Session()
        time.sleep(30)
threading.Thread(target=checker, daemon=True).start()
```
The thread reference is **NOT stored on the client** (no `self._checker_thread`) -- schwabdev exposes no handle to supervise it. `update_tokens()` (`tokens.py:160-198`) only touches the network when the access token is within 61s of expiry (`at_delta < 61`) -- i.e. roughly **once every ~30 minutes** (access tokens last 1800s); the other ~30s cycles are pure datetime arithmetic with no I/O. When it DOES refresh, `update_access_token()` -> `_post_oauth_token()` issues `requests.post(...)`; on DNS failure after a laptop sleep/wake this raises `requests.exceptions.ConnectionError` (wrapping `NameResolutionError`), which is **not caught** inside schwabdev and propagates into the `while True` body -> the thread dies -> no further refresh -> the access token silently expires -> every subsequent Schwab call 401s until `swing web` is restarted (and A-3's whole web ladder silently degrades to yfinance-only).

### 5.2 Approach selection (OQ-4: wrap vs replace)

- **(Recommended) Approach A -- instance-level wrap of `client.tokens.update_tokens`.** After A-3 constructs the web client, replace the bound method on THAT instance with a resilient wrapper. Rationale:
  - Robust to schwabdev internals: it depends only on the documented fact that the checker calls `self.tokens.update_tokens()` -- not on the checker's private closure, thread handle, or loop body. If schwabdev reorganizes the thread, the wrap still protects.
  - Surgical scope: only the web app's long-lived client is wrapped. The CLI's and pipeline's short-lived clients are untouched (they construct their own instances).
  - Preserves the CLI `force_refresh` contract: the wrapper inspects the `force_access_token` / `force_refresh_token` flags and **passes forced calls straight through, re-raising** (so `swing schwab refresh`, which constructs its OWN client and relies on exceptions, is unaffected even in principle). Only the background no-force path is made exception-proof.
- **Approach B -- external supervisor thread.** Spawn our own watcher that polls token freshness and reconstructs the client when the checker appears dead. Rejected for V1: reconstruction re-runs `Client.__init__` -> spawns ANOTHER checker (thread leak), is heavier, and still needs the wrap to detect death. More moving parts for no robustness gain.
- **Approach C -- global monkeypatch of `schwabdev.Client.__init__` / the checker closure.** Rejected: process-global, contaminates CLI + pipeline clients, brittle against schwabdev versions.

### 5.3 The resilient wrapper contract

`install_resilient_checker(client, *, liveness, retries=2, backoff_base_s=1.0) -> None` replaces `client.tokens.update_tokens` with:
```
def resilient_update_tokens(force_access_token=False, force_refresh_token=False):
    if force_access_token or force_refresh_token:
        return _original(force_access_token, force_refresh_token)   # CLI/forced contract: pass through, may raise
    # Codex R3 M#1 / R4 M#1: origin-aware heartbeat. A call from the checker
    # DAEMON thread is a real heartbeat; the startup-thread seed call (5.6) is not.
    origin = "daemon" if _is_checker_daemon_thread() else "seed"   # current_thread vs recorded startup thread
    liveness.record_tick(origin)                                    # sets last_daemon_tick_ts only when origin == daemon
    attempt = 0
    while True:
        try:
            refreshed = _original()                                 # background no-force path
        except Exception as exc:                                    # ConnectionError / NameResolutionError / etc.
            liveness.record_failure(exc)                            # redacted; increments consecutive_failures
            if attempt < retries:
                attempt += 1
                time.sleep(backoff_base_s * (2 ** (attempt - 1)))   # bounded backoff WITHIN this cycle
                continue
            return False                                            # give up THIS cycle; loop survives -> retries in 30s
        liveness.record_success(refreshed=refreshed,
                                access_present=_access_token_present(client))
        return refreshed
```
(`record_tick(origin)` writes `last_daemon_tick_ts` only for `origin == "daemon"` and `last_seed_ts` for the seed call -- the section 5.4 distinction that prevents the seed from showing a false ALIVE.)
Notes:
- **Returns `False` on give-up** so schwabdev's `if self.tokens.update_tokens() and use_session:` treats it as "no update" -- the loop continues normally and tries again in 30s. The thread NEVER dies.
- **Bounded backoff inside the cycle** (default 2 retries: 1s, 2s) recovers from a brief blip faster than waiting the full 30s, while a hard outage just cycles every 30s. Backoff sleeps block only the daemon checker, never a request thread. (This is the ONLY retry/backoff in SB5.5; the market-data path has none -- section 4.5.2.)
- **Post-call state verification** (`update_tokens` does not raise on auth failure -- the schwabdev gotcha): on the success branch, read `client.tokens.access_token`; if a refresh was attempted but the token did not rotate / is empty, record a degraded liveness (auth-failed) rather than a false "alive."
- **Redaction (L6):** `record_failure` logs via `_redacted_excerpt(exc)` (the existing redactor) -- never the raw exception text (may carry token-shaped substrings). The `setLogRecordFactory` capital-S `"Schwabdev"` redactor stays installed (A-3's client construction already calls `ensure_schwab_log_redaction_factory_installed`).
- **Budget note (L9):** the wrapper does NOT add network calls -- it wraps the existing ~once-per-30-min refresh. Its bounded backoff fires only on failure and is capped at 2 short sleeps, so it cannot itself become a 429 source.

### 5.4 Liveness signal + the cross-process surfacing gap (OQ-5 / OQ-9)

The liveness record (in `swing web` process memory):
```
CheckerLiveness:
  last_daemon_tick_ts     # updated ONLY by ticks from the checker DAEMON thread -> proves the loop is alive
  last_seed_ts            # set by the startup-thread seeding call (5.6); NOT a daemon heartbeat
  last_success_ts         # last time update_tokens completed without raising
  last_refresh_ts         # last time a token was actually rotated (refreshed == True)
  consecutive_failures    # reset to 0 on success
  last_error_class        # redacted exception class name (no message bytes)
  installed_ts
```
**Daemon-vs-seed distinction (Codex R3 Major #1; BINDING).** The wrap records `last_daemon_tick_ts` ONLY when the call originates from the checker daemon thread (the wrapper compares `threading.current_thread()` against the recorded startup thread, or checks a daemon-thread marker); the startup-thread seeding call (section 5.6) sets `last_seed_ts` instead. Otherwise the seeding call would advance the heartbeat from the main thread and `swing schwab status` would report ALIVE even if the daemon died at tick 1 (the bug the seeding mitigation would otherwise introduce). `render_status` reports **STARTING/UNKNOWN** until the first daemon-originated tick after install, then ALIVE/DEGRADED based on `last_daemon_tick_ts`.

**The gap the brief's wording did not anticipate:** liveness lives in the `swing web` process; **`swing schwab status` is a SEPARATE CLI process** (`cli_schwab.py:1426`, READ-ONLY, no Client construction). Pure in-memory state cannot cross that boundary. To surface checker-liveness via the CLI **without a schema change**, the wrapper writes the record to an **ephemeral on-disk sidecar JSON**:
- Path: `~/swing-data/schwab-checker-liveness.{env}.json` (mirrors the tokens-DB path convention at `cli_schwab.py:1447`).
- Write: atomic (`NamedTemporaryFile(dir=<same dir>)` + `os.replace` -- same-volume, Windows-safe per the `os.replace` gotcha). Throttled but **the write cadence and the CLI stale threshold MUST be reconciled (Codex R2 Major #2):** write on every state transition (alive<->degraded) AND a periodic heartbeat write at `HEARTBEAT_WRITE_INTERVAL` (e.g. every 4th tick, ~120s); the CLI stale threshold (below) MUST exceed the max write interval with margin (e.g. `STALE_THRESHOLD = 2 x HEARTBEAT_WRITE_INTERVAL + 60s` ~ 300s). A healthy checker must NEVER be reported stale between two normal heartbeat writes -- the original "every 10th tick (~5 min) vs ~90s stale" pairing was contradictory and is corrected here.
- This is **NOT a schema object** (no migration, no DB table/column) -> L3 honored. It is ephemeral (recreated on each `swing web` start; safe to delete; gitignored). It is the minimal way to bridge the process boundary.
- `render_status` reads the sidecar: present + `last_daemon_tick_ts` within `STALE_THRESHOLD` -> "Checker: ALIVE (last refresh <t>; <n> consecutive failures)"; present but no daemon tick yet (only `last_seed_ts`) -> "Checker: STARTING"; `last_daemon_tick_ts` older than `STALE_THRESHOLD` or sidecar present-but-degraded -> "Checker: DEGRADED -- <redacted reason>"; sidecar absent -> "Checker: unknown (web server not running, or pre-N7 build)". ASCII-only output (gotcha #16/#32). The exact `HEARTBEAT_WRITE_INTERVAL` / `STALE_THRESHOLD` constants are finalized at writing-plans with the invariant `STALE_THRESHOLD > HEARTBEAT_WRITE_INTERVAL` held.

**OQ-9 (flagged for operator):** the brief said "in-memory/ephemeral liveness surfaced by `swing schwab status`." Strictly in-memory state is invisible across the process boundary. The recommended resolution is the ephemeral sidecar file (still NO schema, still ephemeral). Alternatives: (a) surface liveness only inside the web app (violates L8 CLI-only); (b) infer liveness from `schwab_api_calls` audit rows (rejected -- the background checker's network refresh does not route through our audited wrappers, and no-op cycles write nothing, so audit rows cannot prove loop-liveness). Recommend the sidecar; confirm at writing-plans that a sidecar file satisfies the "ephemeral, no schema" intent.

### 5.5 Liveness persistence (OQ-5)
- **(Recommended)** ephemeral sidecar file (section 5.4) -- no schema, no v24.
- **Rejected** persisted health DB row -> schema v24 -> violates L3.

### 5.6 Two implementation hazards (Codex R1 Major #4 + #6)

**Startup race -- the checker starts at construction, the wrap installs after (Major #4 + Codex R2 Major #3; EXPLICIT NARROW RESIDUAL + a seeding mitigation).** `schwabdev.Client(...)` (`auth.py:756`) spawns the checker thread DURING construction and the checker's first loop iteration calls `update_tokens()` immediately; A-3 installs the resilient wrap a few statements LATER in `_install_web_marketdata_caches`. There is a sub-second window (construction -> wrap) in which an unwrapped first tick could run. **Codex R2 correctly flagged that the original "practically nil" rationale over-assumed freshness:** `construct_authenticated_client` only verifies the access token EXISTS (`auth.py:767`), NOT that it has ~1800s remaining. So IF the loaded token is already within 61s of expiry, that first unwrapped tick WOULD POST and could die on a DNS failure. The corrected disposition:
- **Scope the residual precisely:** the race can only bite on the FIRST tick AND only when the just-loaded access token is already <61s from expiry -- a narrow condition (a freshly set-up or recently-refreshed token has ~1800s).
- **Seeding mitigation (V1, cheap, closes most of the gap):** immediately AFTER installing the wrap, `_install_web_marketdata_caches` invokes ONE wrapped `client.tokens.update_tokens()` itself from the startup thread. This call is exception-isolated and refreshes the token if near expiry, and sets `last_seed_ts` (NOT `last_daemon_tick_ts` -- per the section 5.4 daemon-vs-seed distinction, so it does NOT mask a dead daemon as ALIVE). Because the daemon thread is the one that dies, the seeding call cannot resurrect it -- so the residual that remains is "the daemon thread may be dead from tick 1 under the narrow near-expiry condition." That condition surfaces correctly: `swing schwab status` shows STARTING until a daemon-originated tick lands and then DEGRADED if none ever does (never a false ALIVE), and the operator resolves it with a `swing web` restart.
- **Honest residual (not "nil"):** under the narrow near-expiry-at-startup condition the checker thread can die on tick 1 before wrapping; V1 accepts this as a small, surfaced residual. **V2 full closure:** construction-time class-level patch of `Tokens.update_tokens` scoped to the construction window (so the very first tick is already wrapped), then narrow to the instance -- banked, not V1 (it touches the class globally during the window).
- Test: assert the wrap is installed + the seeding refresh is invoked before `_install_web_marketdata_caches` returns; assert a near-expiry seeding call is exception-isolated and records liveness.

**schwabdev version brittleness (Major #6 + Codex R2 Major #4; CORRECTED -- the pin claim was false).** The instance-level wrap depends on schwabdev's checker dynamically resolving `self.tokens.update_tokens()` each cycle (orchestrator-verified in the INSTALLED schwabdev **2.5.1** on Windows: `client.py:50-56` + `tokens.py:160-198`; version string `"Schwabdev 2.5.1"` at `client.py:42`). **Correction:** the original claim that `pyproject.toml` "already pins the validated 2.5.1 behavior" is FALSE -- the actual constraint is `schwabdev>=2.4.0,<3.0.0` (`pyproject.toml:20`), which permits versions with changed checker internals. Mitigations in the plan:
- (a) **Tighten the pin** to a known-good ceiling at the validated version (e.g. `>=2.5.1,<2.6.0`) OR record an explicit "validated against 2.5.1" constraint the plan re-confirms.
- (b) **Version guard test WITHOUT constructing a client (Codex R3 Major #3):** assert the installed schwabdev version via `importlib.metadata.version("schwabdev")` (package metadata) -- NOT `schwabdev.Client(...).version`, because constructing a `Client` has side effects (it spawns a checker daemon thread and needs credentials/token-file/network, violating the "no live network / no checker in default tests" posture). Fail LOUDLY on drift from the validated version so a human re-validates the checker contract before the bump ships. A mere "attribute exists + was replaced" check does NOT prove the daemon dynamically calls the replaced method, so the version (or a source-text contract) assertion is the real guard. If deeper assurance is wanted, inspect the schwabdev `client.py` source text for the `self.tokens.update_tokens()` call within the checker, again without constructing a `Client`.
- (c) On a guard-test failure, CI surfaces the schwabdev bump rather than the checker silently going unprotected.
- (Codex could not import schwabdev under WSL `python3` -- it is installed under the Windows interpreter; the source claims here were orchestrator-verified against the installed 2.5.1 on Windows.)

---

## Section 6 -- L2 framing + the runtime-surface / budget rationale (OQ-1 RESOLVED)

> OQ-1 is RESOLVED by operator ruling (section 2.1): A-3 is a sanctioned L2 extension. This section is no longer a HOLD; it is the rationale + the proof the source-grep stays green + the shared-budget framing the operator asked the spec to retain.

### 6.1 What the L2 LOCK test actually enforces

`tests/integration/test_l2_lock_source_grep.py` greps `swing/` for the pattern `schwabdev.Client.` at HEAD vs baseline `bf7e071` and fails if HEAD introduces a NEW or count-inflated `(path, line_text)` (multiset/Counter subset comparison). In git-grep BRE the `.` is a wildcard, so the pattern also matches the construction form `schwabdev.Client(` -- the baseline already counts the three construction sites in `auth.py` (`construct_authenticated_client`, `setup_paste_flow`, `force_refresh`).

### 6.2 Why A-3 + P14.N7 keep it green (the proof)

- A-3 calls the EXISTING factory `construct_authenticated_client` (`auth.py:694`) -- it adds **no new `schwabdev.Client.` line** anywhere in `swing/`.
- A-3 reuses the EXISTING ladder functions, whose Schwab SDK calls (`get_quotes_batch` / window fetch wrappers) are pre-existing and counted at baseline.
- P14.N7 wraps an EXISTING method (`update_tokens`) on an instance and adds ZERO API calls.
- **Therefore the source-grep test stays green by construction.** The L7/L2 gate step (S3) is the binding proof.

### 6.3 The runtime-surface + shared-budget framing (retained per operator request)

Before A-3, the web **market-data path** issued ZERO Schwab calls (yfinance-only). (Per Codex R1 Minor #3: the web is not Schwab-free in general -- `swing/web/routes/schwab.py` already serves OAuth setup/status, and `trade_entry`/`trade_exit` audit surfaces exist; A-3's expansion is specifically the web MARKET-DATA path.) After A-3, the web market-data path becomes a new RUNTIME Schwab-call surface drawing on the **shared ~120-calls/min app-wide budget** alongside the pipeline, account/reconciliation ops, and the checker. The operator has sanctioned this expansion for Schwab's better data provenance; the spec's obligation is to make it **safe within the shared budget** -- which is exactly what L9 (section 4.5) delivers: open-trade scope + the existing TTL caches bound steady-state volume to roughly low-hundreds of calls/hour from the web (section 4.5.5), and the provider_tag-driven cooldown gate + yfinance fallthrough absorb sustained Schwab failure (including 429) without hammering. The source-grep measures SITES (unchanged); L9 governs the runtime SURFACE/VOLUME (the part that actually expanded).

---

## Section 7 -- Sandbox-gating + audit-surface contract

### 7.1 Sandbox gating (L4) -- inherited, not re-implemented

A-3 installs the hooks; the gate lives where it already lives: `_is_ladder_active(cfg)` (`marketdata_ladder.py:221`) returns True only for `env == 'production' AND marketdata_ladder_enabled`. Under sandbox / disabled / missing-attrs, the ladder short-circuits to the yfinance fallback with ZERO `schwab_api_calls` rows. A-3 adds ONE extra gate at the web layer -- *whether to construct the client at all* -- so that sandbox/test app construction spawns no client and no checker (section 4.3). It must be the SAME predicate, not a looser one. The L7 test asserts: production+creds -> hooks installed; sandbox -> hooks absent (plain caches).

### 7.2 Audit surface value (OQ-3) -- reuse `'pipeline'`; a CHECK collision blocks `'web'` (CRITICAL FINDING)

**Brief-vs-production correction.** The brief frames OQ-3 as "confirm the existing enum allows a web value or use an existing one." Verified at v23: the `schwab_api_calls.surface` CHECK is

```
CHECK (surface IN ('pipeline', 'cli', 'trade_entry', 'trade_exit'))
```
(migration `0020_phase13_charts_patterns_autofill_usability.sql:338`; widened from the original `('pipeline','cli')` at `0018:32`; NOT further widened by 0021/0022/0023). The same 4-tuple is mirrored in Python at `audit_service._SCHWAB_API_SURFACE_VALUES` and re-validated in the wrapper at `marketdata.py:461`. **There is no `'web'` value.** Recording web ladder calls with `surface='web'` would violate BOTH the SQL CHECK and the Python guard -> the audit INSERT inside the ladder wrapper would fail -> the ladder's `except` would swallow it -> **every web Schwab call would silently fail to yfinance.** And widening the enum to add `'web'` is a **v24 migration -> violates L3.**

**Resolution (LOCKED by L3 + the brief's "avoid a schema trigger"): reuse `surface='pipeline'` with `pipeline_run_id=NULL`.** No schema change, L3 honored. Trade-off: the audit trail + the `ix_schwab_api_calls_surface_ts` index + the surface-filtered counts in `swing schwab status` conflate web calls with pipeline calls. This is acceptable for V1 (both are internal automated market-data fetches; neither is operator-CLI-initiated), and the `pipeline_run_id IS NULL` discriminator distinguishes web calls within the `pipeline` surface for any later forensic split. A dedicated `'web'` surface value (clean audit semantics) is a V2 candidate gated on a future schema phase (section 12).

---

## Section 8 -- Schema impact (NO change)

- **A-3 wiring:** no schema. Pure cache-hook installation + client construction + the L9 closure gates. The audit `surface` value reuses `'pipeline'` (section 7.2) -- NO new CHECK member.
- **P14.N7 wrap:** no schema. Instance-level method replacement.
- **P14.N7 liveness:** no schema. Ephemeral on-disk sidecar JSON (section 5.4), not a DB table/column.
- **L9c `rate_limit_remaining`:** no schema. The column + extraction + audit-write all already exist (section 4.5.3); the only change is a header-name addition to the extractor.
- **Verdict: NO migration. `EXPECTED_SCHEMA_VERSION` stays 23.** A gate step asserts no `0024_*.sql` exists and the schema version is unchanged (S2; see also section 11).

The brief listed Schema impact at BOTH section 8 and section 11 of its deliverable shape; this spec consolidates the verdict here and keeps section 11 as the gate-assertion restatement to honor the brief's outline.

---

## Section 9 -- Sub-bundle decomposition recommendation (slices)

Operator LOCKed A-3 + P14.N7 into ONE SB5.5 executing-plans cycle (OQ-7). Recommended slice order:

- **Slice 1 -- A-3 web ladder install + L9 scope/cooldown gates.** `_install_web_marketdata_caches` in `app.py`; mirror `_install_pipeline_marketdata_caches`; graceful-degradation client construction via `resolve_credentials_env_or_prompt` (env > cfg cascade; Major #5); BOTH hooks (full parity); `surface='pipeline'`; the open-trade-scope gate + the provider_tag-driven consecutive-fallback cooldown gate in the hook closures (4.5.2). Tests: L7 production-path wiring (hooks installed under production, absent under sandbox; daily-bar kwargs reach the ladder) + the scope gate (non-open-trade ticker bypasses Schwab) + the cooldown gate (N consecutive `provider_tag='yfinance'` pins to yfinance for the cooldown window) + the cfg-tier credential resolution.
- **Slice 1b (SHOULD, small) -- L9c header-name fix.** Add Schwab's confirmed rate-limit header name to `_extract_response_payload`'s candidate list (or defer the exact name behind the writing-plans live-header confirmation). A unit test stubs a response with the header and asserts the audit row's `rate_limit_remaining` is populated.
- **Slice 2 -- P14.N7 checker-resilience wrap** (`swing/integrations/schwab/checker_resilience.py`): the wrapper + the in-memory liveness record. Install it on the web client in `app.py` (right after A-3's construction). Tests: DNS-failure-during-refresh survival (the loop does not die; liveness goes degraded then recovers; forced calls still raise) + the schwabdev-version guard (Major #6 + R3 M#2/#3: `importlib.metadata.version("schwabdev")` assertion, no client construction) + the wrap-effectiveness unit test (wrap replaced `update_tokens` + exception-isolated) + the seed-vs-daemon-tick liveness distinction (R3 M#1; seed call sets `last_seed_ts`, not the heartbeat) + the post-wrap-seeded-refresh / wrap-before-network assertion (Major #4 race).
- **Slice 3 -- liveness surfacing** (ephemeral sidecar writer + `render_status` checker line). Test: `swing schwab status` renders ALIVE / STARTING / DEGRADED / stale / unknown(absent) from a seeded sidecar (the STARTING case -- `last_seed_ts` only, no daemon tick -- proves the false-ALIVE prevention; Codex R4 Minor #1); ASCII assertion scoped to the new line.

Each slice ends with the L2-lock grep + the fast suite green. The whole cycle ends with the operator-witnessed gate (section 10).

---

## Section 10 -- Test fixture strategy + gate enumeration (production-path; DNS-failure sim)

### 10.1 Test fixture strategy (L7 / gotcha #15 -- BINDING)
- **A-3 wiring test** exercises the REAL `create_app(cfg)` construction -- NOT a stubbed cache:
  - Production cfg (`environment='production'`, `marketdata_ladder_enabled=True`) + monkeypatched `construct_authenticated_client` returning a MagicMock client (mirror the pipeline integration tests; never a live network) -> assert `app.state.ohlcv_cache._ladder_bars_fetcher is not None` AND `app.state.price_cache._ladder_fetcher is not None` AND `app.state.schwab_client is not None`.
  - Sandbox cfg (default) -> assert both `_ladder_*_fetcher is None` AND `app.state.schwab_client is None` (yfinance-only fall-through). This is the test-safety guarantee for the ~6900 fast tests.
  - Daily-bar footgun: invoke the installed bars-hook with a stubbed `fetch_window_via_ladder` and assert it is called with `period_type='year', period=5, frequency_type='daily', frequency=1` (a discriminating test, per the minute-default gotcha; do NOT byte-compare a render).
  - **L9 scope gate:** with an open-trade set `{AAA}` seeded, assert the hook attempts Schwab for `AAA` but bypasses Schwab (yfinance direct, no audit row) for `ZZZ` (a non-open-trade ticker) -- the render-storm defense.
  - **L9 cooldown gate (provider_tag-driven, per the 4.5.2 correction):** stub the ladder to return `provider_tag='yfinance'` N consecutive times (simulating sustained Schwab failure -- the hook never sees the 429 exception itself); assert that after the Nth fallback the hook enters cooldown and bypasses Schwab even for an open-trade ticker, and that it resumes attempting Schwab after `circuit_breaker_cooldown_seconds`. Do NOT write a test that expects the hook to catch `SchwabRateLimitError` (the ladder swallows it).
  - **L9 concurrent-load note (4.5.3):** a failure-mode test simulating web + pipeline both fetching the same open ticker under an active ladder -- assert both degrade to yfinance without raising and without unbounded retry (documents the V1 no-app-wide-governor acceptance).
  - **Credential resolver (Major #5):** assert `_install_web_marketdata_caches` resolves via `resolve_credentials_env_or_prompt` (cfg-tier creds with no env vars still construct the client under production+ladder).
  - **schwabdev version guard (Major #6 + Codex R3 Major #2/#3):** the BINDING guard is a version assertion via `importlib.metadata.version("schwabdev")` against the validated version (fail loudly on drift) -- NOT a client construction. Separately, a wrap-effectiveness unit test asserts the installed wrap replaced `update_tokens` on a mock-token Tokens object and is exception-isolated; the attribute-exists check alone is insufficient (it does not prove the daemon calls the replaced method).
  - Must monkeypatch BOTH `USERPROFILE` and `HOME` if any path touches `_user_home()` (gotcha).
- **P14.N7 resilience test** simulates a real DNS failure during refresh -- NOT a stubbed checker:
  - Build a fake `tokens` whose `update_tokens()` raises a `ConnectionError` (with a NameResolution-shaped message) on the first call(s) then succeeds; install the resilient wrap; invoke it and assert: (1) it does NOT raise; (2) it returns `False` on failure / the refreshed bool on success; (3) liveness transitions `installed -> degraded(consecutive_failures>0) -> alive(consecutive_failures==0)`; (4) a forced call (`force_access_token=True`) passes through and DOES propagate the exception (CLI contract preserved). **Daemon-heartbeat origin (Codex R4 Minor #2):** because a direct call from the test/main thread is NOT a daemon tick, exercise the daemon-heartbeat path either from a worker thread OR via an injected thread-origin predicate (`_is_checker_daemon_thread`), and assert a main-thread/seed call sets `last_seed_ts` (NOT `last_daemon_tick_ts`).
  - Backoff timing: monkeypatch `time.sleep` to a recorder; assert bounded backoff sequence (no unbounded loop, no real sleeping in tests).
- **Liveness render test** seeds a sidecar JSON for each state -- **ALIVE / STARTING (only `last_seed_ts`, no `last_daemon_tick_ts` -- the false-ALIVE-prevention case, Codex R4 Minor #1) / DEGRADED / stale / absent** -- and asserts the new checker-liveness line(s) render correctly. **ASCII assertion scoped to the NEW line only (Codex R1 Minor #2):** `render_status` ALREADY emits an em dash in its PROVISIONAL/DEGRADED lines (`cli_schwab.py:829`/`:831`), so a whole-output `out.isascii()` would fail on pre-existing content. Assert `.isascii()` on the checker-liveness substring the test adds (mirrors the SB5 D2 lesson: scope the ASCII assertion to the new content, not the shared surface).

### 10.2 Operator-witnessed gate (test/CLI-driven, NOT browser)
- **S1** fast suite (`-m "not slow"`) + `ruff check swing/` clean, re-run on the MERGED head and READ (per `feedback_no_false_green_claim`).
- **S2** schema: assert NO `0024_*.sql`; `EXPECTED_SCHEMA_VERSION == 23`; no migration applied.
- **S3 (CENTRAL)** `tests/integration/test_l2_lock_source_grep.py` GREEN -- zero new `schwabdev.Client.` call sites at HEAD vs `bf7e071`.
- **S4** the A-3 production-path wiring + L9 scope/cooldown tests (section 10.1) green -- hooks installed under production, absent under sandbox, Schwab scoped to open-trade tickers, sustained `provider_tag='yfinance'` fallback -> cooldown (NOT a direct-429 catch -- the ladder swallows the 429; section 4.5.2).
- **S5** the P14.N7 DNS-survival test green + operator runs `swing schwab status` and confirms the checker-liveness line renders (ALIVE in a healthy session; the test proves DEGRADED->recovered).
- **S6** `git log -1 --format='%(trailers)'` is `[]` on every commit (Co-Authored-By + trailer-parse-hazard discipline).
- **S7 (optional, if a production Schwab session is available)** operator smoke of the web daily-bar path: load an OPEN-TRADE chart surface under `env=production` + ladder enabled and confirm a `surface='pipeline'`-tagged (`pipeline_run_id IS NULL`) `schwab_api_calls` row was written (web ladder fired), the chart renders daily (not minute) bars, and a NON-open-trade chart wrote NO Schwab row (scope gate held).

---

## Section 11 -- Schema impact (gate restatement)

Per the brief's deliverable outline (which lists schema impact at both section 8 and section 11): the binding verdict is **NO migration, v23 held** (section 8). The gate enforces it at **S2** (no `0024_*.sql`; `EXPECTED_SCHEMA_VERSION == 23`). The only place a schema change could intrude is the audit `surface` value (section 7.2) -- avoided by reusing `'pipeline'`.

---

## Section 12 -- V1 simplifications + V2 candidates

### V1 simplifications
- Reuse `surface='pipeline'` (with `pipeline_run_id=NULL`) for web ladder calls -- avoids a v24 (section 7.2).
- Ephemeral sidecar for liveness -- avoids a v24 (section 5.4).
- Instance-level `update_tokens` wrap -- avoids supervising schwabdev's private thread (section 5.2).
- Open-trade-scope gate + TTL cache as the primary rate-limit defense; closure-local Schwab cooldown reusing `circuit_breaker_cooldown_seconds` -- no new breaker subsystem (section 4.5).
- L9c reduced to a header-name addition on existing plumbing (section 4.5.3).
- CLI-only liveness (L8) -- no web health badge.

### V2 candidates
- A dedicated `surface='web'` audit value + a forensic split of web vs pipeline calls (needs a v24 -> a future schema phase).
- A web health badge for checker-liveness (OQ-6; a render surface).
- A persisted checker-health history table for trend analysis (v24).
- A shared cross-process Schwab-budget governor (a token-bucket the web + pipeline + checker all consult) -- if the shared 120/min budget proves tight under concurrent load; bigger than SB5.5.
- Prefer-fresher-by-mtime gate between the web and pipeline market-data archives (gotcha #24 parallel-archive freshness).
- Generalizing the resilient-wrap to the pipeline + CLI clients (short-lived today, but a future long-running CLI daemon would benefit).

---

## Section 13 -- Operator decision items (OQs)

| OQ | Question | Disposition |
|----|----------|-------------|
| **OQ-1** | A-3 within L2 vs needs carve-out? | **RESOLVED (operator 2026-05-31): sanctioned L2 extension.** Designed as intended; source-grep stays green; L9 governs the runtime surface (section 6). |
| **OQ-2** | A-3 consumer breadth? | **RESOLVED (operator 2026-05-31): FULL PARITY** -- both hooks (quote + bars), governed by L9 (section 4.4). |
| **OQ-3** | Audit `surface` value? | **RESOLVED: reuse `'pipeline'` (pipeline_run_id NULL).** `'web'` is NOT in the v23 CHECK enum or the Python guard -> would need v24 (violates L3 + the brief's "avoid a schema trigger"). Section 7.2. |
| OQ-4 | P14.N7 wrap vs replace? | Recommend instance-level `update_tokens` wrap (Approach A); confirm at writing-plans. |
| OQ-5 | Liveness persistence? | Recommend ephemeral sidecar file (no schema), NOT a persisted DB row (v24). |
| OQ-6 | P14.N7 surface: CLI-only vs web badge? | Recommend CLI-only (`swing schwab status`) for V1; web badge deferred (L8). |
| OQ-7 | Decomposition: one cycle vs two? | Operator-LOCKed to ONE SB5.5 cycle; 3 slices + a small 1b (section 9). |
| OQ-8 | Codex chain count at writing-plans / executing-plans? | Recommend single chain. |
| **OQ-9 (NEW)** | Cross-process liveness gap: pure in-memory state is invisible to the separate `swing schwab status` process. | Recommend the ephemeral sidecar (still no schema, still ephemeral). Flag for operator -- the brief's "in-memory/ephemeral" wording did not anticipate the process boundary (section 5.4). |
| OQ-10 (NEW, minor) | L9c exact Schwab rate-limit header name. | Confirm via live header / Schwab docs at writing-plans; land the extractor change behind the confirmed name; do NOT guess a name that silently stays None (section 4.5.3). |

---

## Section 14 -- Cumulative discipline compliance (L2 / L4 / L6 / L9 central)

- **L2:** A-3 + P14.N7 add ZERO `schwabdev.Client.` lines (section 6.2); the source-grep test stays green by construction; the runtime-surface expansion is operator-sanctioned.
- **L4:** sandbox gate inherited from `_is_ladder_active`; web client not even constructed under sandbox (section 7.1).
- **L6:** web ladder calls audit via the existing wrappers (`surface='pipeline'`); the checker wrap logs only `_redacted_excerpt`; the `setLogRecordFactory` capital-S `"Schwabdev"` redactor stays installed.
- **L9:** open-trade fetch scope + the existing TTL caches bound steady-state web calls (corrected math in 4.5.5: two OhlcvCache stores + a 120s price TTL); a sustained Schwab failure is observed via the returned `provider_tag` (the ladder swallows the 429, so the hook cannot catch it -- 4.5.2 correction) and trips a closure-local cooldown -> yfinance, NEVER a hammering retry; V1 explicitly accepts no app-wide governor (4.5.3 residual risk + concurrent-load test; governor deferred to V2); `rate_limit_remaining` made observable via a header-name fix on existing plumbing; render-storm defused by the scope gate (section 4.5).
- **Schwab daily-bar minute-default footgun:** the bars-hook passes explicit `(year,5,daily,1)` (section 4.2); discriminating test asserts kwargs (gotcha).
- **`update_tokens()` does not raise on auth failure:** the wrapper verifies post-call `access_token` state (section 5.3).
- **`os.replace` same-filesystem:** the sidecar uses `NamedTemporaryFile(dir=<dest dir>)` + `os.replace` (section 5.4).
- **gotcha #15 / L7:** the A-3 test exercises real `create_app`; the P14.N7 test simulates a real DNS failure -- no byte-parity stubs substituting for production-path wiring.
- **ASCII (#16/#32):** the new `swing schwab status` checker line is ASCII-only; tests assert `.isascii()`.
- **Co-Authored-By + trailer-parse hazard:** zero co-author trailers; the final `-m` paragraph of every commit is plain prose; `%(trailers)` verified `[]`.
- **TestClient lifespan:** any A-3 test touching `app.state.price_fetch_executor` (or asserting checker behavior under lifespan) uses `with TestClient(app) as client:`.

---

## Section 15 -- Phase 14 close-out position note

SB5.5 is the FIRST item of the operator-LOCKed Phase 14 close-out tail. Sequence: **SB5.5 (this) -> close-out polish batch (P14.N1-dashboard + A-1 market_weather 200MA + A-2 vcp crowding + A-4 `_bulz_*` rename + A-6 process-grade dark-mode chart + group-(a) minor advisories) -> B-7 operator failure-mode classification (final touch) -> Phase 14 close-out review (Sec 9.1 Q6).** SB5.5 holds Schema v23 LOCKED, preserves the L2 LOCK (source-grep green), and preserves the ~700+ commit ZERO Co-Authored-By streak. With OQ-1 + OQ-2 resolved by operator ruling, SB5.5 is fully unblocked for writing-plans once this spec converges: A-3 is designed as a sanctioned, rate-limit-aware, full-parity L2 extension, and P14.N7 hardens the long-lived client A-3 introduces.

---

*End of Phase 14 Sub-bundle 5.5 design spec. Two infrastructure items on the Schwab surface: A-3 (install the EXISTING production-gated market-data ladder on the web caches at FULL PARITY, mirroring `_install_pipeline_marketdata_caches`, bounded by the L9 rate-limit-aware open-trade-scope + TTL-cache + 429-cooldown design) + P14.N7 (exception-isolate + bounded-backoff the schwabdev checker token-refresh thread; surface checker-liveness via `swing schwab status` through an ephemeral sidecar). OQ-1 (sanctioned L2 extension) + OQ-2 (full parity) + OQ-3 (reuse `surface='pipeline'`) RESOLVED. Two material brief-vs-production findings retained: the `surface='web'` CHECK collision (resolved by reuse, no schema) and the cross-process liveness gap (OQ-9). NO schema change (v23 held); reuse not re-implement; sandbox-gating preserved; L9 the governing runtime driver.*
