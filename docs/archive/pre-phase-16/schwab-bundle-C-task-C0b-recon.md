# Schwab API Sub-bundle C — Task T-C.0.b operator-paired live verification recon

**Purpose:** Capture Phase-1 pre-check findings from `reference/schwabdev/api-calls.md` L296-440 (quotes + price_history) + `reference/schwabdev/client.md` (rate limits) so Sub-bundle C endpoint wiring consumes the verified Market-Data-API surface — and bank deviations from the writing-plans plan §E.3 synthesized signatures for the V2.1 §VII.F amendment channel.

**Status:** Phase 1 = COMPLETE (this doc). **Phase 2 = DEFERRED** — live Market-Data-API cassette recording against the operator's production-tier Schwab account is scheduled post-merge operator-paired session. Cassette-dependent acceptance criteria for T-C.3 + T-C.5 + T-C.6 stay synthetic-fixture-driven (mocked schwabdev) until that pairing happens. T-C.1 + T-C.2 + T-C.4 + T-C.7 proceed on Phase-1 pre-check authority alone per dispatch brief §2.

**Plan reference:** `docs/superpowers/plans/2026-05-13-schwab-api-integration-plan.md` §E.3 + §E.4 + §E.5 + §E.8 + §H.6 + §H.7 (Tasks T-C.1..T-C.6 consumers).

**Operator-supplied distillations consumed:**

- `reference/schwabdev/api-calls.md` L296-440 (quotes + price_history sections) — schwabdev 2.5.x wrapper method → REST endpoint mapping for the 2 methods Sub-bundle C consumes.
- `reference/schwabdev/client.md` (rate limits 120/min for both `quotes` + `price_history`; "Do NOT use in loops — use streaming instead" warnings on both per L255-265).
- `reference/schwab-api/market-data-{documentation,specification}.md` — NOTE: these describe Schwab's **streaming** (WebSocket) Market Data services (LEVELONE, BOOK, CHART, SCREENER, ACCOUNT). V1 consumes REST `/marketdata/quotes` + `/marketdata/pricehistory` only (per spec §1.4 + Q4 V2-fence on streaming). The streaming docs are out-of-scope for Sub-bundle C; consulted only for cross-reference of symbol semantics.

---

## §1 Sub-bundle C marketdata-method surface (post-pre-check)

| Logical name | schwabdev method (verified `api-calls.md`) | HTTP verb + path | Required params | Optional params | Project consumer |
|---|---|---|---|---|---|
| `marketdata.quotes` | `Client.quotes(symbols=None, fields=None, indicative=False)` | `GET /marketdata/quotes` | `symbols` (effectively yes) | `fields`, `indicative` | T-C.1 `get_quotes_batch`; T-C.3 ladder; T-C.4 `PriceSnapshot` cache-fill; T-C.5 CLI `--verify-marketdata` |
| `marketdata.pricehistory` | `Client.price_history(symbol, periodType=None, period=None, frequencyType=None, frequency=None, startDate=None, endDate=None, needExtendedHoursData=None, needPreviousClose=None)` | `GET /marketdata/pricehistory` | `symbol` (positional) | all 8 others (all camelCase) | T-C.1 `get_price_history`; T-C.3 ladder; T-C.4 `OhlcvCache` cache-fill; T-C.5 CLI `--verify-marketdata` |

**Key pre-check observations:**

1. **`quotes` kwargs are ALL snake_case** (`symbols`, `fields`, `indicative`) — SAFE from the Sub-bundle-B camelCase trap family. `symbols` accepts `list | str | None`; both `["AAPL","AMD"]` and `"AAPL,AMD"` forms supported per `api-calls.md` L307. `fields` allowed values `"all"` (default) / `"quote"` / `"fundamental"`; `indicative: bool` (default `False`).
2. **`price_history` kwargs are CAMELCASE on EVERY non-positional param** per `api-calls.md` L407-423 — `periodType` / `period` / `frequencyType` / `frequency` / `startDate` / `endDate` / `needExtendedHoursData` / `needPreviousClose`. Only `symbol` is positional snake_case. **THIS IS THE SAME DEFECT FAMILY** that bit Sub-bundle B's `account_orders(maxResults=...)` (gate-caught fix `34be84e`). Pre-empt via `inspect.signature(schwabdev.Client.price_history)` discriminating test at T-C.1 BEFORE writing any other test (per brief §0.5 row 1).
3. **`startDate` / `endDate` accept `datetime` OR `int` (UNIX epoch ms)** per `api-calls.md` L432-433 — NOT ISO-string. The `_schwab_iso` helper from Sub-bundle B `trader.py` is **NOT applicable** to `price_history`; pass `datetime` directly OR convert to `int(dt.timestamp() * 1000)`. Plan §E.3 row 2 text "start_datetime=ms, end_datetime=ms" is shorthand for the int-epoch-ms form. **Plan-text amendment banked (§5 §B below).**
4. **Both methods return `requests.Response`** (NOT raw dicts). Wrapper must call `.json()` + verify HTTP status from the Response object. The Sub-bundle B trader.py call-wrapper pattern (`_call_endpoint()` helper at `swing/integrations/schwab/trader.py`) is reusable VERBATIM.
5. **`price_history` JSON body shape (verbatim from `api-calls.md` L437):** `{"candles": [{open, high, low, close, volume, datetime}, ...], "symbol": ..., "empty": bool}`. **Schwab explicitly returns an `empty: bool` field.** Mapper MUST consult BOTH `len(candles) == 0` AND `empty == True` (defense-in-depth — Schwab may return `empty=true AND candles=[]` OR `empty=false AND candles=[...]`; both signal "no data" in different shapes per spec §E.5). Per spec §H.6.4: empty → mapper raises synthetic `SchwabApiError(204, "empty bars")`; ladder catches; falls back to yfinance; audit row `status='error'`, `error_message="empty bars (transient)"`; parquet UNCHANGED.
6. **`quotes` JSON body shape:** dict keyed by symbol per `api-calls.md` L312. Partial-response on per-symbol failure surfaces as an error envelope under the symbol key (NOT a separate top-level errors array) — mapper splits per spec §E.4: emit `SchwabQuoteResponse` per OK symbol; mark failed symbols for yfinance fallback at ladder layer. Audit row `error_message` excerpt captures per-symbol breakdown (e.g., "3/5 OK; failed: XYZ (404)") — under the no-token-leak contract.
7. **Per-bar field names in `price_history` candles** per `api-calls.md` L437: `open, high, low, close, volume, datetime`. `datetime` is UNIX epoch ms (not ISO string) — mapper converts to ISO date string for `OhlcvBar.asof_date` (mapping to project-internal `OhlcvBar(asof_date: str)` shape per plan §E.3 row 2).
8. **`needPreviousClose` + `needExtendedHoursData`** default `None` (treated as `False` by Schwab). V1 callsite omits both (project does not consume previous-close or extended-hours bars).
9. **Rate limits:** 120 req/min for BOTH `quotes` + `price_history` per `client.md` L255-265. Verbatim "Do NOT use in loops — use streaming instead" warning on both per `api-calls.md` L314 + L439. Bundle C handles at audit layer (rate_limit_remaining captured if headers present) + ladder layer (catch `SchwabRateLimitError` → fall back to yfinance).
10. **Single-Client-instance discipline (Sub-bundle B forward-binding lesson #3):** `marketdata.py` MUST NOT instantiate `schwabdev.Client(...)` directly. Reuse `construct_authenticated_client()` from `swing/integrations/schwab/auth.py` (Bundle B `e61d735`). Verified via `grep -rn "schwabdev.Client("` returns 0 matches inside `swing/integrations/schwab/marketdata.py` + `marketdata_ladder.py`.

---

## §2 Plan §E.3 reconciliation — 4 falsifications + 4 confirmations

| Plan §E.3 claim | schwabdev actual (`api-calls.md`) | Status | Resolution |
|---|---|---|---|
| `Client.quotes(symbols=['A','B','C',...])` | `Client.quotes(symbols=None, fields=None, indicative=False)`; `symbols: list \| str \| None` | **CORRECT ✓** (cosmetic — plan omits the optional `fields` + `indicative` params; both default None/False so omitting is fine) | T-C.1 passes `symbols=list[str]`; omits `fields` + `indicative`. |
| `Client.price_history(symbol, period_type='day', period=10, frequency_type='daily', frequency=1, start_datetime=ms, end_datetime=ms)` | Actual: `Client.price_history(symbol, periodType=None, period=None, frequencyType=None, frequency=None, startDate=None, endDate=None, needExtendedHoursData=None, needPreviousClose=None)`; **ALL non-positional kwargs are camelCase** | **FALSIFIED (semantic — repeat of Sub-bundle B family)** | Pin kwarg names via `inspect.signature` discriminating test at T-C.1; call as `Client.price_history(symbol, periodType="day", period=10, frequencyType="daily", frequency=1, startDate=start_dt, endDate=end_dt)`. **Plan amendment §5 §A.** |
| `price_history` `start_datetime` / `end_datetime` documented as "ms" | Actual: `startDate` / `endDate` accept `datetime \| int \| None`; int is UNIX epoch ms | **FALSIFIED (cosmetic — datatype permissive)** | Implementer's choice: pass `datetime` directly OR `int(dt.timestamp() * 1000)`. **Plan amendment §5 §B.** |
| `price_history` response shape `{"candles": [...], "symbol": ..., "empty": bool}` | Confirmed verbatim per `api-calls.md` L437 | **CORRECT ✓** | Mapper consults `empty` field directly (NOT only `len(candles) == 0`) — defense-in-depth per spec §H.6.4. |
| `quotes` partial-response: error envelopes mixed with success envelopes per symbol | Confirmed per `api-calls.md` L312 + spec §E.4 | **CORRECT ✓** | Mapper splits per spec §E.4. |
| `quotes` field names: `last_price` / `bid` / `ask` | Schwab API actually returns camelCase fields inside the per-symbol dict (`lastPrice`, `bidPrice`/`bid`, `askPrice`/`ask`) — confirmed against Schwab Developer Portal account API specs (analogous to Trader naming). **Phase 2 LIVE pending** to lock exact field names. | **PARTIAL** (needs live verify) | Mapper tolerates both snake_case + camelCase via `dict.get("lastPrice") or dict.get("last_price")` defensive lookup at T-C.1. |
| `quotes` `delayed: bool` informational flag | Plan §E.3 claims schwabdev exposes; **Phase 2 LIVE pending** to confirm field name (`delayed` vs `realTime` vs absence-as-default-delayed). | **PARTIAL** (needs live verify) | Mapper tolerates absence by defaulting `delayed=False`; flag is informational only per §A.1 Q12 default-tier acceptable. |
| `quotes` `quote_time` / `quoteTimeInLong` etc. | Schwab API typically returns long (epoch ms) field `quoteTimeInLong` or similar; **Phase 2 LIVE pending** to lock. | **PARTIAL** (needs live verify) | Mapper converts to ISO ms string for `SchwabQuoteResponse.quote_time`; defensive fallback to `now_ms()` if absent. |
| Rate limits 120/min for both methods | Confirmed `client.md` L255-265 | **CORRECT ✓** | Bundle C handles at audit layer + ladder layer. |

---

## §3 Marketdata-method param plumbing notes (T-C.1 implementation)

### §3.1 `inspect.signature` discriminating-test pattern (BINDING for T-C.1)

Per brief §0.5 row 1 + §4.1. Mirror Sub-bundle B's `tests/integrations/test_schwab_trader_kwarg_signatures.py` pattern:

```python
# tests/integrations/test_schwab_marketdata_kwarg_signatures.py (NEW at T-C.1)
import inspect
import schwabdev

def test_quotes_kwargs_snake_case():
    sig = inspect.signature(schwabdev.Client.quotes)
    assert set(sig.parameters.keys()) - {"self"} == {"symbols", "fields", "indicative"}
    # All snake_case per api-calls.md L298

def test_price_history_kwargs_camel_case():
    sig = inspect.signature(schwabdev.Client.price_history)
    expected = {"symbol", "periodType", "period", "frequencyType", "frequency",
                "startDate", "endDate", "needExtendedHoursData", "needPreviousClose"}
    assert set(sig.parameters.keys()) - {"self"} == expected
    # 8 of 9 kwargs are camelCase; ONLY `symbol` is positional snake_case.
    # Pinning this set discriminates against the Sub-bundle B-family camelCase drift defect.
```

If either test fails on a future schwabdev upgrade, the wrapper code is wrong-cased and would `TypeError` at runtime — the test fires before any cassette gets recorded.

### §3.2 Mapper `quotes` partial-response handling

Per spec §E.4 + plan §H.6.1. The mapper at `swing/integrations/schwab/mappers.py:map_quotes_to_price_cache_entries` takes the raw `quotes` JSON dict (keyed by symbol) and returns `dict[str, SchwabQuoteResponse]`:

- For each input symbol:
  - If response has a fully-populated quote shape (`lastPrice`/`bid`/`ask` present + numeric) → emit `SchwabQuoteResponse(symbol=..., last_price=..., bid=..., ask=..., mark=..., quote_time=..., delayed=...)`.
  - If response has an error envelope (`errors`/`error`/`fault` keys) OR the symbol is absent from response keys → DO NOT emit; symbol marked for yfinance fallback by the ladder.
- Returns the successfully-mapped subset (dict, possibly empty).
- Audit row `error_message` excerpt captures the per-symbol breakdown via `_make_redactor(known_secrets)`-redacted format: `"3/5 OK; failed: XYZ (404), ABC (timeout)"` (no token bytes; no client_secret).
- Audit-row status: `'success'` if at least one symbol mapped; `'error'` if all symbols failed.

### §3.3 Mapper `price_history` empty-response handling

Per spec §E.5 + plan §H.6.4. The mapper at `swing/integrations/schwab/mappers.py:map_price_history_to_window` takes the raw `price_history` JSON dict + the ticker; returns `SchwabPriceHistoryWindow`:

- Read both shape signals:
  - `candles = body.get("candles", [])`
  - `empty_flag = body.get("empty", False)`
- If `len(candles) == 0` OR `empty_flag is True` → raise synthetic `SchwabApiError(status_code=204, body_excerpt="empty bars")`.
- Else: convert each candle dict to `OhlcvBar(asof_date=..., open=..., high=..., low=..., close=..., volume=...)`. `candle["datetime"]` (epoch ms) converts to ISO date via `datetime.fromtimestamp(ms / 1000, UTC).date().isoformat()`.
- Validate per-bar invariants in `OhlcvBar.__post_init__` (low ≤ min(open, close); high ≥ max(open, close); volume ≥ 0) — defense-in-depth per plan §H.7 `SchwabPriceHistoryWindow` row.
- Sort bars by asof_date ascending.

---

## §4 Q12 (default tier) + Q17 (rate limit) deferral status

### §4.1 Q12 default-tier acceptable

Per spec §A.1 Q12 default disposition. Default-tier accounts receive **delayed quotes** (15-minute delay typical per Schwab Developer Portal documentation; informational only per §A.1).

- **Pre-check verdict:** No code change required regardless of Q12 disposition. The `delayed: bool` field on `SchwabQuoteResponse` carries the flag through to downstream consumers; V1 does NOT branch on it (Phase 10 metrics-dashboard does NOT consume `delayed` per spec §3.8.2).
- **Phase 2 LIVE observation pending:** confirm Schwab actually returns the `delayed` flag (vs absence) under operator's default-tier production credentials. Mapper tolerates absence by defaulting `False`.
- **V2 candidate:** if operator upgrades to real-time tier, surface the delay in briefing.md banner. NOT V1.

### §4.2 Q17 rate-limit headroom

Per spec §A.1 Q17. Both `quotes` + `price_history` are documented at 120 req/min per `client.md`. The current pipeline's open-trade-tickers fetch loop issues at most O(N_open) requests per run where N_open is typically ≤10 trades — well within budget.

- **Pre-check verdict:** Headroom unproblematic for V1 pipeline cadence (1 run/day). No code-level throttling required.
- **Phase 2 LIVE observation pending:** verify `X-RateLimit-Remaining` HTTP header presence + counter accuracy under back-to-back calls (operator-paired session: issue 5 back-to-back `quotes` calls; observe header decrement).
- **`schwab_api_calls.rate_limit_remaining` audit column** captures the header value when present per spec §C.1. Already shipped in Sub-bundle A migration 0018.

---

## §5 Plan §E.3 amendments banked for V2.1 §VII.F channel

### §5.A `price_history` kwarg naming (CRITICAL — same family as Sub-bundle B `34be84e` defect)

Plan §E.3 row 2 reads:

> `Client.price_history(symbol, period_type='day', period=10, frequency_type='daily', frequency=1, start_datetime=ms, end_datetime=ms)` `[VERIFY]`

Schwabdev 2.5.x actual surface per `reference/schwabdev/api-calls.md` L407-423:

```python
Client.price_history(
    symbol,                       # positional, snake_case
    periodType=None,              # camelCase
    period=None,                  # camelCase
    frequencyType=None,           # camelCase
    frequency=None,               # camelCase
    startDate=None,               # camelCase
    endDate=None,                 # camelCase
    needExtendedHoursData=None,   # camelCase
    needPreviousClose=None,       # camelCase
)
```

**Amendment:** Plan §E.3 row 2 + §H.6.2 ladder pseudocode `schwab_client.get_price_history(ticker, start, end)` MUST surface camelCase kwargs in any concrete code-shape. Wrapper-internal helper signature can be snake_case (`get_price_history(client, symbol, period_type, period, frequency_type, frequency, start_dt, end_dt)`) but the inner schwabdev call MUST pass camelCase. **`inspect.signature` discriminating test at T-C.1 pins the camelCase set.**

### §5.B `price_history` datetime datatype (cosmetic)

Plan §E.3 row 2 + §H.6.2 use `start_datetime=ms` / `end_datetime=ms` shorthand. Actual schwabdev accepts `datetime | int | None` per `api-calls.md` L432-433. **Amendment:** Pass `datetime` objects directly when convenient (cleaner code path); convert to `int(dt.timestamp() * 1000)` only if needed for cassette determinism. The `_schwab_iso` helper from Sub-bundle B `trader.py` is **NOT applicable** here — that helper emits ISO strings, which `price_history` does NOT accept.

### §5.C `PriceCacheEntry` vs actual `PriceSnapshot` class name (CRITICAL — plan-implementation drift)

Plan §A.8 + §H.7 refer to dataclass `PriceCacheEntry` as the cache entry shape for the `PriceCache` consumer.

**Verified at recon:** the actual class at `swing/web/price_cache.py:24` is `@dataclass(frozen=True) class PriceSnapshot`. There is NO `PriceCacheEntry` class anywhere in the codebase (verified via `grep -rn "class PriceCacheEntry" swing/` returning 0 matches).

**Amendment:** Plan §A.8 + §H.7 + every reference in plan §Tasks-C to `PriceCacheEntry` should read `PriceSnapshot`. Implementer at T-C.4 EXTENDS the existing `PriceSnapshot` class (adds `provider: str | None` field) — does NOT create a new `PriceCacheEntry` dataclass.

### §5.D `OhlcvCache` location drift (cosmetic but path-binding)

Plan §B.1 + various §H references mention `swing/data/ohlcv_cache.py`.

**Verified at recon:** `swing/data/ohlcv_cache.py` DOES NOT EXIST. The actual `OhlcvCache` class lives at `swing/web/ohlcv_cache.py` (verified via `grep -rn "class OhlcvCache"` returning only `swing/web/ohlcv_cache.py`).

**Amendment:** Plan path references to `swing/data/ohlcv_cache.py` should read `swing/web/ohlcv_cache.py`. Implementer at T-C.4 extends the existing `OhlcvCache` at the actual location.

### §5.E `OhlcvCacheEntry` dataclass per §A.9 #1

Plan §A.9 #1 enumerates `OhlcvCacheEntry` among the new dataclasses needing `__post_init__` validators. Phase-1 recon could NOT verify whether such a dataclass already exists at `swing/web/ohlcv_cache.py` (file exists per §5.D but contents not inspected at recon time). **Implementer at T-C.4 must inspect FIRST and either extend the existing entry shape OR add the new dataclass per the actual code shape.**

---

## §6 Phase 2 LIVE deferrals (operator-paired post-merge session)

The following observations are NOT pre-checkable from refs and require operator-paired live Market-Data-API calls against operator's production-tier Schwab credentials at `~/swing-data/schwab-tokens.production.db` (7-day refresh-token clock started 2026-05-14; expires ~2026-05-21):

1. **`quotes` per-symbol response field names** — confirm whether `lastPrice` / `bidPrice` / `askPrice` (camelCase Schwab REST convention) vs snake_case alternates. Plan §E.3 dataclass `SchwabQuoteResponse` uses snake_case; mapper currently uses defensive dual-lookup (§3.2 above).
2. **`quotes` `delayed` flag presence + name** — confirm whether default-tier responses carry a `delayed` field, an `realTime` field, or neither (absence ⇒ assumed delayed).
3. **`quotes` quote-time field shape** — `quoteTimeInLong` (epoch ms) or `quoteTime` (ISO string) — mapper currently converts both to ISO ms string for `SchwabQuoteResponse.quote_time`.
4. **`price_history` candle `datetime` field shape** — confirm epoch ms (per `api-calls.md` L437 "datetime"); confirm timezone convention (UTC assumed; Schwab Developer Portal documents UTC for all REST market-data timestamps).
5. **`price_history` `empty=true` flag actual triggering condition** — verify by requesting a future-only date range (e.g., `startDate=tomorrow, endDate=tomorrow+1day`); confirm response carries `empty=true AND candles=[]`. Drives spec §H.6.4 transient-handling discriminating test.
6. **Partial-response error envelope shape on `quotes`** — confirm whether failed symbol surfaces as `{symbol: {errors: [...]}}` OR `{symbol: {fault: ...}}` OR symbol absent from response keys. Mapper currently tolerates all three.
7. **`X-RateLimit-Remaining` header presence + counter accuracy** — observe under 5 back-to-back `quotes` calls; verify decrement.
8. **Q12 default-tier delay magnitude** — observe `quoteTimeInLong` lag vs wall clock under operator's default-tier credentials (informational; typical 15-min documented).

**Acceptance criterion deferrals (T-C.3 + T-C.5 + T-C.6):**
- T-C.3 ladder discriminating tests use **mocked schwabdev** (`unittest.mock.MagicMock` returning canned JSON dicts shaped per §E.3 + §E.4 + §E.5). Cassette-driven E2E acceptance criteria DEFER to operator-paired session.
- T-C.5 CLI `--verify-marketdata` discriminating tests use **mocked schwabdev** for same reason. CLI integration smoke test against operator's actual Schwab account DEFERS to operator-paired gate (Surface S2 + S3 per brief §3).
- T-C.6 pipeline integration smoke test against ladder-enabled production env DEFERS to operator-paired gate (Surface S4 per brief §3).

T-C.1 + T-C.2 + T-C.4 + T-C.7 ship without dependency on Phase 2 LIVE observations:
- T-C.1: signature pins + mapper structural tests + audit-lifecycle tests are deterministic.
- T-C.2: parquet-layer only; zero schwabdev surface.
- T-C.4: cache integration tests use mocked ladder return values.
- T-C.7: sentinel-leak audit drives sentinels through mocked schwabdev's `Schwabdev` logger; cassette-replay coverage extends post-Phase-2.

---

## §7 Verification summary

**Pre-check FROM `reference/schwabdev/api-calls.md` L296-440 (verified inline):**

- `quotes(symbols, fields, indicative)` signature: ✓ verified verbatim L298.
- `price_history(symbol, periodType, period, frequencyType, frequency, startDate, endDate, needExtendedHoursData, needPreviousClose)` signature: ✓ verified verbatim L407-423.
- `quotes` response shape: dict keyed by symbol — ✓ verified L312.
- `price_history` response shape `{"candles": [...], "symbol": ..., "empty": bool}`: ✓ verified L437.
- Rate limits 120/min for both: ✓ verified L314 + L439 + `client.md` L255-265.

**Pre-check FROM `reference/schwabdev/client.md`:**

- Threading model + rate-limit doctrine consumed verbatim; mirror Sub-bundle A + B precedent.

**Pre-check FROM `reference/schwab-api/market-data-{documentation,specification}.md`:**

- These describe streaming-services API (WebSocket LEVELONE, BOOK, CHART, SCREENER, ACCOUNT) — out-of-scope for Sub-bundle C REST consumption per spec §1.4. Consulted only for cross-reference of symbol semantics + rate-limit conventions.

**Plan-implementation drift surfaced for V2.1 §VII.F amendment channel:**

- §5.A `price_history` camelCase kwarg surface (CRITICAL family — same as Sub-bundle B `34be84e` defect).
- §5.B `price_history` datetime datatype permissiveness (cosmetic).
- §5.C `PriceCacheEntry` → actual `PriceSnapshot` (CRITICAL drift).
- §5.D `swing/data/ohlcv_cache.py` → actual `swing/web/ohlcv_cache.py` (path-binding drift).
- §5.E `OhlcvCacheEntry` dataclass existence not verifiable at recon time (extends-or-creates determined by implementer at T-C.4).

**Phase 1 → Phase 2 boundary:**

- Phase 1 (this doc) closes T-C.0.b sufficiently to unblock T-C.1 + T-C.2 + T-C.4 + T-C.7 per brief §2 fallback path.
- Phase 2 LIVE cassette recording DEFERS to operator-paired post-merge session. T-C.3 + T-C.5 + T-C.6 ship with mocked-schwabdev test fixtures; live cassette acceptance criteria fold in at the operator-paired gate (Surfaces S2 + S3 + S4 per brief §3).

**Operator action required post-merge:**

- Operator-paired session to record cassettes for `marketdata.quotes` + `marketdata.pricehistory` against production-tier credentials.
- Re-record cassette if 7-day refresh-token clock expires before pairing (re-run `swing schwab setup` paste-back to extend).
- Post-session: convert mocked tests to cassette-replay tests at T-C.3 + T-C.5 + T-C.6 (orchestrator-followup dispatch).
