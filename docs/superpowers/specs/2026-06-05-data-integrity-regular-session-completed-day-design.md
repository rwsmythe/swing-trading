# Regular-Session + Completed-Day Data Integrity -- Design Spec

**Date:** 2026-06-05
**Phase:** 15 (the big near-term data-integrity arc)
**Status:** Brainstorm design spec (no production code). Input to `copowers:writing-plans`.
**Branch:** `data-integrity-arc-brainstorming` (from main HEAD `f251106e`).
**Brief:** [`docs/data-integrity-arc-brainstorming-dispatch-brief.md`](../../data-integrity-arc-brainstorming-dispatch-brief.md).
**Integration-review source:** [`docs/phase14-integration-review-checklist.md`](../../phase14-integration-review-checklist.md) (Issue #5 folded in; Issue #3 audited).

---

## 1. Architecture + the motivating lock-principle

### 1.1 The principle (operator, 2026-06-05)

The tool only ever **PULLS + LOCKS regular-session, completed-trading-day data.**

The Phase-14 temporal observation log (`pattern_forward_observations`) is **append-only with lock-at-observation**: `ohlc_today_json` is `NOT NULL`, locked the moment an observation is written, and **never re-fetched** (migration 0022 NORMATIVE invariant). A locked bar is *permanent* -- there is no post-facto correction path. The `#23` pool-widening (2026-06-04) put the nightly pipeline into the business of locking forward-walk data **every night** for the ~83x watch population.

Therefore: **the data pulled + locked MUST be completed-regular-session, enforced at the PULL stage -- before the lock -- or it is permanently wrong.** This arc does not loosen the lock; it makes the lock *unable* to capture a partial or extended-hours bar.

### 1.2 Two contamination axes

A bar can be wrong along two independent axes; the arc closes both:

1. **Extended-hours contamination (L1).** A Schwab daily candle that folds pre/post-market prints. The `high`/`low` shift to reflect ext-hours trading. **Critically, most ext-hours prints do NOT violate the OHLC invariant** -- a post-market trade above the regular high simply raises `high` while `low <= min(open, close)` still holds. So such a bar passes `OhlcvBar.__post_init__` ([`models.py:539-551`](../../../swing/integrations/schwab/models.py)) and gets **silently locked** with contaminated extremes. The ~16% of `marketdata.pricehistory` calls that error with `OhlcvBar invariant violated` are only the *pathological subset* where ext-hours pushes an extreme outside the open/close envelope. The fix MUST be at the pull (`needExtendedHoursData=False`), not the invariant.

2. **Current/partial-day contamination (L2).** A bar for the *in-progress* session (or an after-hours snapshot of "today") when the pipeline/web runs during or after trading hours. The daily bar is incomplete; its OHLC will change before the close. yfinance `history(interval="1d")` includes this in-progress bar by default.

### 1.3 Harden, don't rebuild (L4)

The completed-day machinery already exists and is mostly correct:
- [`swing/evaluation/dates.py`](../../../swing/evaluation/dates.py): `last_completed_session(now)` (backward; "never serve a partial in-progress daily bar") + `action_session_for_run(now)` (forward).
- [`runner.py:541`](../../../swing/pipeline/runner.py): `data_asof_str = last_completed_session(run_now).isoformat()` -- written into the run's `data_asof_date` at lease acquisition. **The pipeline's lock anchor is already a completed session.**
- [`temporal_metadata.py:30`](../../../swing/pipeline/temporal_metadata.py): `_slice_to_asof(bars, asof)` strips bars dated after `asof`.

The arc HARDENS + uniformly ENFORCES these helpers. It does NOT rewrite the date system.

### 1.4 Component map (what changes)

| Component | Role | Change |
|---|---|---|
| `swing/integrations/schwab/marketdata.py` | Schwab `price_history` wrapper | Add `needExtendedHoursData=False` + `needPreviousClose` |
| `swing/integrations/schwab/mappers.py` | quote mapper | Read `regularMarket*` fields |
| `swing/integrations/schwab/marketdata_ladder.py` | window ladder + archive persist | Strip in-progress bar at write barrier; classify `SchwabBarConsistencyError` |
| `swing/integrations/schwab/models.py` | `OhlcvBar` invariant | Float epsilon on low/high checks |
| `swing/integrations/schwab/client.py` (or errors module) | error taxonomy | New typed `SchwabBarConsistencyError` |
| `swing/data/ohlcv_archive.py` / `swing/web/ohlcv_cache.py` | archive write-through | In-progress-bar strip at write barrier |
| `swing/pipeline/runner.py` (`_bar_for_date`) | observe-lock bar select | Completed-day assert |
| `swing/pipeline/temporal_metadata.py` (`build_ohlc_today_json`) | lock serializer | Completed-day assert |
| `swing/evaluation/dates.py` (new helper) | topbar anchor | `topbar_session_date(page_kind)` classifier |
| ~20 base-layout VMs | topbar `session_date` | Route through the classifier |

**No schema change** (Q7). v24 holds.

---

## 2. The data-pull-and-lock + session-anchor AUDIT (the spine)

Every surface where market data is **PULLED**, where it is **LOCKED**, and where a session date is **ANCHORED**. Columns: current source; ext-hours exposure; current/partial-day exposure; proposed enforcement.

### 2.1 PULL surfaces (market data)

| # | Pull site | Source today | Ext-hours? | Partial-day? | Enforcement |
|---|---|---|---|---|---|
| P1 | Schwab `price_history` ([`marketdata.py:428`](../../../swing/integrations/schwab/marketdata.py)) -- the single wrapper feeding pipeline detect/observe/charts (via `fetch_window_via_ladder`), web `OhlcvCache` ladder ([`app.py:334`](../../../swing/web/app.py)), and CLI `--verify-marketdata` | Server default `needExtendedHoursData=true` | **YES** (root cause) | Schwab daily candles are completed-session bars *by date*, but `endDate` defaulting can include the current day | Add `needExtendedHoursData=False` + explicit `needPreviousClose=False`. §4.1 |
| P2 | Schwab `quotes` ([`marketdata.py:280`](../../../swing/integrations/schwab/marketdata.py) -> `mappers.py:630`](../../../swing/integrations/schwab/mappers.py)) | `lastPrice` (= ext-hours last during pre/post-market) | **YES** | N/A (point-in-time quote) | Map `regularMarketLastPrice`/`regularMarketTradeTime`; fall back to `lastPrice` only when regular fields absent. §4.2 |
| P3 | yfinance window fallback (`_yf_window_fallback` [`app.py:336`](../../../swing/web/app.py); pipeline `yfinance_fallback_fn` [`runner.py:441`](../../../swing/pipeline/runner.py)) | yfinance `download`/`history(interval="1d")` | No (yfinance daily is regular-session) | **YES** -- includes the in-progress partial bar | Strip the in-progress bar at the archive **write barrier** before persist (§5.2); consumers also slice `<= data_asof_date`. |
| P4 | yfinance quote fallback (`_yf_quote_fallback` [`app.py:308`](../../../swing/web/app.py)) | yfinance fast quote | Possibly (delayed/last) | N/A | Display-only; documented. Lower stakes (no locked surface). §4.2 |
| P5 | Legacy `PriceFetcher` / `PriceCache` (`_step_evaluate` last-close) | yfinance | No | Partial-bar strip already applied per CLAUDE.md gotcha (`df.iloc[:-1]` keyed to session) | Confirm the strip uses `last_completed_session`, not `date.today()`; add a regression test. §5.3 |

### 2.2 LOCK surfaces (append-only / persisted facts)

| # | Lock site | What is locked | Date anchor today | Risk | Enforcement |
|---|---|---|---|---|---|
| L-A | Temporal observe-lock: `_step_pattern_observe` -> `_bar_for_date(cfg, cache, ticker, observation_date)` -> `build_ohlc_today_json(bar)` ([`runner.py:2466,2558`](../../../swing/pipeline/runner.py); [`temporal_metadata.py:149`](../../../swing/pipeline/temporal_metadata.py)) | `pattern_forward_observations.ohlc_today_json` (`{open,high,low,close,volume,provider}`) -- **NEVER re-fetched** | `observation_date = lease_data_asof(cfg, lease)` = `data_asof_date` = `last_completed_session(run_now)` | Date anchor is correct (completed session). **Bar CONTENT** can still be ext-hours-contaminated (via P1) or wrong if a future regression supplies a current-day `observation_date`. | (1) P1/P3 guarantee clean content; (2) completed-day assert at `_bar_for_date` AND `build_ohlc_today_json` (§6). |
| L-B | Detection-event lock: `_step_pattern_detect` writes `pattern_detection_events` (`structural_anchors_json`, `composite_score`, `per_pattern_metadata_json`) ([`runner.py:2312-2343`](../../../swing/pipeline/runner.py)) | Detection facts | `data_asof_date` (= `last_completed_session`); metadata computed off bars sliced via `_slice_to_asof(bars, asof=data_asof_date)` | Bars are detect-step fetch (via P1/P3) -> same ext-hours exposure as L-A; slice handles partial-day | P1/P3 clean the content; the `_slice_to_asof` slice already strips post-`asof` bars. No new guard needed beyond P1/P3. |
| L-C | OHLCV archive write-through (`_persist_window_to_archive` [`marketdata_ladder.py:468`](../../../swing/integrations/schwab/marketdata_ladder.py); `ohlcv_archive.py`) | Per-ticker `{TICKER}.{provider}.parquet` (read later by `_bar_for_date` + detect) | Bar `asof_date` | A persisted current-day/partial bar could be read by a later lock; ext-hours bars persisted verbatim | **Write-barrier strip** of any bar dated >= the current in-progress session (§5.2). This is the single chokepoint. |
| L-D | `account_equity_snapshots` (Schwab account fetch; `record_snapshot`) | NLV/cash/positions snapshot | `snapshot_date = last_completed_session` ([`runner.py:3665`](../../../swing/pipeline/runner.py)) | Point-in-time equity, not OHLC; production-only (sandbox short-circuit) | Out of OHLC scope. Issue #3 audit (§8) confirms the capital-friction 0-count is a *metrics reconstruction* bug, not a snapshot defect. |

### 2.3 ANCHOR surfaces (topbar `session_date` across base-layout VMs -- Issue #5)

Three anchor families are in play today (verified by grep over `swing/web/`). The naive-calendar family is a latent bug (it equals `action_session` only on a weekday before close; it diverges after-hours and on weekends/holidays).

| VM / route | Current anchor | Family | Page kind | Target (§7) |
|---|---|---|---|---|
| `DashboardVM` ([`dashboard.py:1534`](../../../swing/web/view_models/dashboard.py), `action_session`) | `action_session_for_run` | forward | forward-planning | **forward** (keep) |
| `WatchlistVM` ([`watchlist.py:217`](../../../swing/web/view_models/watchlist.py)) | `action_session_for_run` | forward | forward-planning | **forward** (keep) |
| `JournalVM` ([`journal.py:252`](../../../swing/web/view_models/journal.py), `banner["session_date"]`) | `date.today()` | **naive** | history/analysis | **backward** (fix) |
| Journal drill-down VMs (share `_base_banner_fields`) | `date.today()` | **naive** | history/analysis | **backward** (fix) |
| Reviews VMs ([`trades.py:1351,1523`](../../../swing/web/view_models/trades.py)) | `last_completed_session` | backward | history/analysis | **backward** (keep) |
| Patterns queue/exemplars/review-form (`_session_date_str` [`patterns.py:78`](../../../swing/web/routes/patterns.py)) | `last_completed_session` | backward | history/analysis | **backward** (keep) |
| Metrics overview + all 9 tiles ([`metrics/index.py:437`](../../../swing/web/view_models/metrics/index.py) + each `metrics/*.py`) | `action_session_for_run` | forward | history/analysis | **backward** (fix) |
| `CapitalFrictionVM` ([`capital_friction.py:106`](../../../swing/web/view_models/metrics/capital_friction.py)) | `action_session_for_run` (topbar) while DATA uses `last_completed_session` (line 100, §A.15 LOCK) | forward | history/analysis | **backward** (fix -- align topbar to the data the page already shows) |
| `PipelineVM` ([`pipeline.py:71`](../../../swing/web/view_models/pipeline.py)) | `datetime.now().date()` | **naive** | history (last run) | **backward** (fix) |
| `ConfigVM` ([`config.py:170`](../../../swing/web/view_models/config.py)) | `date.today()` | **naive** | settings (not session-anchored) | **backward** (fix; settings show last-completed framing) |
| Reconcile route/VM ([`reconcile.py`](../../../swing/web/routes/reconcile.py)) | `action_session_for_run` | forward | history (last fills) | **backward** (fix) |
| Schwab status/setup routes ([`schwab.py`](../../../swing/web/routes/schwab.py)) | `action_session_for_run` | forward | operational status | **backward** (fix) |
| Account route ([`account.py:65`](../../../swing/web/routes/account.py)) | `action_session_for_run` | forward | operational status | **backward** (fix) |
| `PageErrorVM` | (default `""`) | n/a | error | backward default (graceful) |

**Classification principle ("page is about"):** the topbar shows the session the page is **about**. Forward-planning pages (what should I do at the next session) -> `action_session_for_run`. History/analysis/operational pages (what happened through the last completed session) -> `last_completed_session`. The naive-calendar family is eliminated entirely.

---

## 3. LOCKed scope (L1-L6, BINDING -- propagated, not re-opened)

- **L1** -- no extended-hours on ANY Schwab market-data call. `price_history` (`needExtendedHoursData=False`) AND `quotes` (`regularMarket*` fields). Every call site.
- **L2** -- completed-trading-day only. During/after hours, discount the in-progress day; use only the last completed session. No partial bar, no after-hours print enters a computation or a lock.
- **L3** -- the lock is sacred. Append-only + `ohlc_today_json` lock-at-observation PRESERVED. The arc adds a guard so the lock can never capture a partial/extended/current-day bar; it does NOT loosen the lock (no re-fetch/regeneration).
- **L4** -- harden, don't rebuild. Enforce the existing `last_completed_session`/`action_session_for_run`/`data_asof_date`/`_slice_to_asof` machinery. No date-system rewrite.
- **L5** -- Schwab L2 LOCK preserved. `needExtendedHoursData=False` is a parameter on the EXISTING `price_history` endpoint. ZERO new Schwab REST endpoints. Re-validate the kwarg on the schwabdev 3.0.5 signature.
- **L6** -- Issue #5 folded in. Uniform topbar policy applied consistently across all base-layout VMs (forward for planning, backward for history/analysis).

---

## 4. The extended-hours fix (L1)

### 4.1 `price_history` -- `needExtendedHoursData=False`

**Change:** [`marketdata.py:428-436`](../../../swing/integrations/schwab/marketdata.py), the `client.price_history(...)` call inside `_client_method`. Add two kwargs (both documented as valid in the wrapper docstring `:397-399` + the schwabdev signature):

```python
return client.price_history(
    symbol,
    periodType=period_type,
    period=period,
    frequencyType=frequency_type,
    frequency=frequency,
    startDate=start_dt,
    endDate=end_dt,
    needExtendedHoursData=False,   # L1: regular-session candles only
    needPreviousClose=False,       # explicit; we never consume previousClose
)
```

**Rationale:** Schwab's server default is `needExtendedHoursData=true`. Daily candles then fold pre/post-market prints into the OHLC. Setting `False` requests regular-session-only candles -> the candle's high/low reflect the 09:30-16:00 ET session only.

**Signature-pin (L5 + camelCase discipline):** a discriminating test asserts `inspect.signature(client.price_history)` includes `needExtendedHoursData` (and `needPreviousClose`) on schwabdev 3.0.5 BEFORE the wrapper relies on it. Cassettes stub the whole call and will NOT catch a kwarg drop -- the signature-pin test is the real guard (CLAUDE.md Schwab gotcha).

**Determinism note:** `needPreviousClose=False` is set explicitly only because we never read `previousClose`; if a future consumer needs it, flip this kwarg alone. It does not affect candle OHLC.

### 4.2 `quotes` -- regular-session fields

**Change:** [`mappers.py:706-720`](../../../swing/integrations/schwab/mappers.py), `map_quotes_to_price_cache_entries`. The Schwab `/quotes` response carries BOTH `lastPrice` (the ext-hours last trade during pre/post-market) AND `regularMarketLastPrice` + `regularMarketTradeTime`. Switch the primary read to the regular-session fields:

```python
last_price = body.get("regularMarketLastPrice")
if last_price is None:
    last_price = body.get("lastPrice")      # fallback only when regular absent
if last_price is None:
    last_price = body.get("last_price")     # snake_case forward-compat
# quote_time prefers regularMarketTradeTime
quote_time_raw = (
    body.get("regularMarketTradeTime")
    or body.get("quoteTimeInLong")
    or body.get("quoteTime")
    or body.get("quote_time")
)
```

`bid`/`ask` remain as-is (bid/ask are quotes, not trades; there is no "regular-market bid" distinct field in the daily-bar sense -- but document that during extended hours the bid/ask reflect the extended book; acceptable because the quote is display-only).

**Stakes (Q3):** quotes feed ONLY ephemeral display + the CLI `--verify-marketdata` path ([`cli_schwab.py:1067`](../../../swing/cli_schwab.py)) -> `PriceSnapshot` -> the ephemeral price cache. **No locked surface consumes a quote.** The change is made anyway to honor the L1 blanket policy and to future-proof (if a quote ever feeds a locked surface, it is already clean). The spec documents the display-only scope so writing-plans does not over-engineer a locked-surface guard here.

**OQ for writing-plans:** re-validate `regularMarketLastPrice`/`regularMarketTradeTime` field availability against a live quote or a recorded cassette (Schwab quote schema varies by `fields=` selection). If the regular fields are absent under the project's quote-field selection, the plan must either add the field selection or fall back gracefully (the `or lastPrice` chain already does). See §13 OQ-3.

---

## 5. Completed-day enforcement (L2) -- locus + mechanism

**Decision (Q1):** write-barrier strip **+** consumer slice (belt-and-suspenders).

### 5.1 The anchor is already centralized (confirmed)

`data_asof_date = last_completed_session(run_now)` at lease acquisition ([`runner.py:541`](../../../swing/pipeline/runner.py)). Every pipeline lock (L-A, L-B) anchors on it. `last_completed_session` correctly returns the prior session before today's close (it checks `ny_ts_utc >= close_ts`, HST->ET aware). **No change to the anchor computation.** The arc adds a regression test asserting `data_asof_date` is a completed session for representative clocks (pre-open, mid-session, post-close, weekend, holiday) -- see §10.

### 5.2 Write-barrier strip (the single chokepoint)

**Where:** the archive write-through -- `_persist_window_to_archive` ([`marketdata_ladder.py`](../../../swing/integrations/schwab/marketdata_ladder.py)) and the `OhlcvCache` write path ([`swing/web/ohlcv_cache.py`](../../../swing/web/ohlcv_cache.py)) / `ohlcv_archive.py`.

**What:** before persisting a window, drop any bar whose `asof_date` is **>= the current in-progress session**. "Current in-progress session" = the NYSE session date for `now` when `now` is before that session's close; equivalently, any date strictly after `last_completed_session(now)`. Implementation: `cutoff = last_completed_session(now)`; keep bars with `asof_date <= cutoff`.

**Why a write barrier (not just consumer slicing):** the archive is the *shared* surface read by both the observe-lock (`_bar_for_date` selects an exact date) and the detect step. A partial current-day bar that lands in the archive is a latent hazard for any future reader. Stripping at write means **no partial bar is ever persisted**, so the append-only lock cannot read one. (This also respects the F6 write-through-archive empty-result rule: if stripping leaves the window empty, treat as transient -- do NOT overwrite existing cached content with emptiness; retain prior + leave stale metadata so the next call retries.)

**Defense-in-depth (consumer slice):** keep the existing `_slice_to_asof(bars, asof=data_asof_date)` on the detect/metadata path ([`temporal_metadata.py`](../../../swing/pipeline/temporal_metadata.py)) and the exact-date select in `_bar_for_date`. If a partial bar somehow lands (e.g., a write path the strip missed), the consumer still cannot lock it.

**Shared-infrastructure caveat (CLAUDE.md gotcha):** the write-barrier strip must NOT pre-truncate the *historical depth* of the window -- it only drops the trailing in-progress bar. Consumers slice their own windows; the archive returns full history minus the partial tail.

### 5.3 Legacy `PriceCache` last-close strip

`_step_evaluate`'s last-close computation already strips the in-progress bar per the CLAUDE.md yfinance gotcha. The arc adds a regression test asserting the strip keys on `last_completed_session(datetime.now())` (the exchange-session helper), NOT `date.today()` (HST lags ET 5h -> `date.today()` can name tomorrow's session pre-midnight ET or mis-handle the post-close window). No behavior change expected; the test pins the contract.

---

## 6. The lock-guard (L3) -- the one-way-door backstop

**Decision (Q4):** completed-day assert at BOTH `build_ohlc_today_json` AND `_bar_for_date`.

The lock-guard cannot detect *value-based* ext-hours contamination from OHLC alone (there is no field that says "this high was a post-market print"). So pull-stage cleanliness (§4, §5) is **primary**. The guard is the hard backstop against the *current/partial-day* axis -- a defense against a future wiring regression that supplies a current-day `observation_date` or a partial bar.

### 6.1 `_bar_for_date` ([`runner.py:2466`](../../../swing/pipeline/runner.py))

Add, before the archive read:

```python
# L3 completed-day guard: never select a bar for the current in-progress
# session. observation_date MUST be <= last_completed_session(now).
cutoff = last_completed_session(datetime.now())
if date.fromisoformat(observation_date) > cutoff:
    raise ValueError(
        f"_bar_for_date: observation_date {observation_date} is not a "
        f"completed session (cutoff {cutoff.isoformat()}); refusing to "
        f"select a partial/in-progress bar for the append-only log")
```

This raises loudly rather than silently returning a partial bar (consistent with the existing `_advance_status` terminal-guard pattern at `runner.py:2432`). In normal operation `observation_date == data_asof_date == last_completed_session`, so the guard never fires; it catches only a wiring bug.

### 6.2 `build_ohlc_today_json` ([`temporal_metadata.py:149`](../../../swing/pipeline/temporal_metadata.py))

The serializer is the **narrowest one-way-door point** before the `pattern_forward_observations` INSERT. Extend its signature to receive the `observation_date` (and the cutoff) and assert the same invariant at the construction barrier:

```python
def build_ohlc_today_json(bar: dict, *, observation_date: str, cutoff: date) -> str:
    if date.fromisoformat(observation_date) > cutoff:
        raise ValueError(
            f"ohlc_today_json: refusing to lock a non-completed-session bar "
            f"({observation_date} > {cutoff.isoformat()})")
    # ... existing key + provider validation ...
```

**Rationale for both:** `_bar_for_date` is the data-source guard (no partial bar is ever *returned*); `build_ohlc_today_json` is the construction-barrier guard (no partial bar is ever *serialized into the append-only log*), mirroring the project's "enforce at the `__post_init__` construction barrier" discipline. Two cheap asserts on a permanent one-way door is proportionate.

**Caller wiring:** `_step_pattern_observe` already computes `observation_date = lease_data_asof(cfg, lease)`; it passes it (and `cutoff = last_completed_session(now)`) to both helpers. No new fetch, no schema change.

---

## 7. Uniform topbar-date policy (L6, Issue #5)

**Decision (Q2):** a shared classifier + the "page is about" principle. Metrics + operational pages -> backward.

### 7.1 The shared helper

Add to [`swing/evaluation/dates.py`](../../../swing/evaluation/dates.py):

```python
from enum import Enum

class PageKind(Enum):
    FORWARD_PLANNING = "forward"   # what to do at the next session
    HISTORY_ANALYSIS = "backward"  # what happened through the last completed session

def topbar_session_date(page_kind: PageKind, now_local: datetime) -> date:
    """The single source of truth for a base-layout topbar date.

    FORWARD_PLANNING -> action_session_for_run (the next session).
    HISTORY_ANALYSIS -> last_completed_session (the last closed session).
    Eliminates the naive date.today()/datetime.now().date() third family.
    """
    if page_kind is PageKind.FORWARD_PLANNING:
        return action_session_for_run(now_local)
    return last_completed_session(now_local)
```

Every base-layout VM sets `session_date=topbar_session_date(<kind>, datetime.now()).isoformat()`. A VM can no longer silently pick the wrong anchor or a naive-calendar date -- it must declare its `PageKind`.

### 7.2 The classification (per §2.3)

- **FORWARD_PLANNING:** `DashboardVM`, `WatchlistVM`.
- **HISTORY_ANALYSIS:** `JournalVM` (+ drill-downs), the reviews VMs, patterns queue/exemplars/review-form, the metrics overview + all 9 tile VMs, `PipelineVM`, `ConfigVM`, the reconcile VM/route, the schwab status/setup routes, the account route, `PageErrorVM` (default).

**Why metrics are backward:** every metrics tile analyzes *completed* trade history. `CapitalFrictionVM` already computes its DATA off `last_completed_session` (line 100, §A.15 LOCK: "Forward-looking action_session_for_run MUST NOT be used here -- would create the session-anchor read/write mismatch family"). The topbar showing `action_session` while the data is `last_completed_session` is exactly the Issue #5 seam. Aligning the topbar to backward makes the page internally consistent.

### 7.3 Session-anchor read/write discipline (CLAUDE.md gotcha family)

Issue #5 is a direct instance of the recurring forward-vs-backward bug. The classifier enforces the WRITER's anchor at the read predicate. Inequality directionality stays as the helpers already implement (`>=` for the forward `action_session_for_run` close check; `>=` for the backward `last_completed_session` close check -- both inclusive of the boundary bar as written). The arc does not touch the inequality logic inside the helpers (L4).

### 7.4 Test

A cross-VM consistency test builds every base-layout VM at a single frozen `now` and asserts:
- All FORWARD_PLANNING VMs report the same `session_date` (== `action_session_for_run(now)`).
- All HISTORY_ANALYSIS VMs report the same `session_date` (== `last_completed_session(now)`).
- No VM reports `date.today()`/`datetime.now().date()` when those differ from both anchors (freeze `now` at a post-close evening on a session day so the three families diverge).

---

## 8. Issue #3 disposition (Q5) -- audit-only -> route OUT

**Decision:** audit-only, then decide. The audit (performed during this brainstorm) shows Issue #3 is **not** a data-integrity/completed-day/ext-hours defect.

### 8.1 Root cause (pinned)

The capital-friction view has two distinct position counts:
- **Current** count: `_count_concurrent_open_positions(conn)` ([`capital.py:347`](../../../swing/metrics/capital.py)) -- `COUNT(*) FROM trades WHERE state IN open_states`. Non-zero (SKYT is `managing`). This drives the live capital/risk %.
- **Per-run trend** count: `_count_open_at_run(conn, started_ts=...)` ([`capital.py:418`](../../../swing/metrics/capital.py)) -- `pre_trade_locked_at <= started_ts AND (last_fill_at IS NULL OR last_fill_at >= started_ts)`.

For Run #89 (started 6/4) and SKYT (filled 5/28, still open): `last_fill_at (5/28) >= started_ts (6/4)` is **FALSE**, so SKYT is excluded -> the per-run trend count = 0, while the live capital/risk row is non-zero. **That is the contradiction the integration review saw.** The `account_equity_snapshots`-recorded-0 hypothesis from the review is incorrect; the count never reads the Schwab snapshot's position list.

### 8.2 Why it routes OUT

The bug is a historical-reconstruction **predicate** error in the metrics layer (a position filled *before* the run but still open at run time is wrongly excluded by `last_fill_at >= started_ts`). It is orthogonal to ext-hours and completed-day data. It involves no Schwab call, no lock, no OHLC bar, no session anchor. Folding it in would dilute the arc.

**Disposition:** OUT of the data-integrity arc. The spec records the root cause so the operator can open a **separate small metrics fix** (`_count_open_at_run` should count trades open at `started_ts`: `pre_trade_locked_at <= started_ts AND (exit/close_ts IS NULL OR close_ts >= started_ts)` -- i.e., key the "still open" clause on the *exit/terminal* timestamp, not `last_fill_at`). That fix is specified at the recommendation level only here; it gets its own brief.

---

## 9. OhlcvBar invariant + error classification (Q6)

**Decision:** typed `SchwabBarConsistencyError` + tiny float epsilon.

### 9.1 Will the invariant violations vanish?

Largely yes. Once `needExtendedHoursData=False` (§4.1), the daily candle's OHLC is internally consistent regular-session data: `low <= min(open, close) <= max(open, close) <= high` holds by construction for a single regular session. The ~16% `OhlcvBar invariant violated` error rate should collapse toward ~0% for the ext-hours-driven subset. The live re-fetch gate (§10.4) confirms this empirically before merge.

### 9.2 Typed error (honest logging + `/schwab/status`)

Today an OHLC-consistency `ValueError` from `OhlcvBar.__post_init__` propagates through `_call_endpoint` (wrapped as parity / re-raised), is caught by the ladder's catch-all `except Exception` ([`marketdata_ladder.py:456`](../../../swing/integrations/schwab/marketdata_ladder.py)), and logs the opaque "unexpected error from T-C.1 wrapper". Add a typed exception:

- New `SchwabBarConsistencyError` (in the schwab errors module; subclass of `SchwabApiError` or a sibling -- chosen so the ladder's existing `except (SchwabAuthError, SchwabRateLimitError, SchwabApiError)` clause catches it and falls back to yfinance *cleanly*, rather than via the opaque catch-all).
- `OhlcvBar.__post_init__` keeps raising `ValueError` (it is a pure dataclass with no Schwab dependency). The **mapper** (`map_price_history_to_window`) catches the per-bar `ValueError` and re-raises it as `SchwabBarConsistencyError(asof_date, detail)` so the audit row records `error_message='OHLC consistency: <detail>'` and `/schwab/status` reads honestly ("N bar-consistency errors" instead of "N unexpected errors").
- The `schwab_api_calls` audit close uses the typed classification (`_classify_schwab_error`) so the status page's success/error mix is truthful.

### 9.3 Tiny float epsilon

Add a small absolute epsilon to the low/high comparisons in `OhlcvBar.__post_init__` to absorb float-representation noise (e.g., a close that prints `12.340000000001` vs a high of `12.34`):

```python
_OHLC_EPS = 1e-6
if self.low > oc_min + _OHLC_EPS:
    raise ValueError(...)
if self.high < oc_max - _OHLC_EPS:
    raise ValueError(...)
```

Epsilon is absolute and tiny (sub-cent); it does NOT mask a genuine ext-hours violation (those are cents-to-dollars outside the envelope). A regression test asserts: (a) a `12.340000000001`-style noise bar passes; (b) a genuine `high = 12.00, close = 12.50` violation still raises.

---

## 10. Test + gate strategy

### 10.1 Signature-pin (L5)
`inspect.signature(schwabdev.Client.price_history)` includes `needExtendedHoursData` + `needPreviousClose` on 3.0.5. Fails loudly if schwabdev drops/renames the kwarg.

### 10.2 Regression-arithmetic (CLAUDE.md `feedback_verify_regression_test_arithmetic`)
For each behavioral value, compute it under BOTH the old path AND the new path and assert the test distinguishes them:
- A synthetic price-history payload with an ext-hours print that raises the high: assert the OLD call (no kwarg) would fold it; assert the NEW wrapper passes `needExtendedHoursData=False` (mock asserts kwarg present).
- A window containing a current-day partial bar: assert the OLD archive write persists it; assert the NEW write-barrier strips it (cutoff = `last_completed_session`).
- A `build_ohlc_today_json`/`_bar_for_date` call with a current-day `observation_date`: OLD locks it; NEW raises.

### 10.3 Completed-day anchor tests
`data_asof_date` and `topbar_session_date` for representative clocks: pre-open ET, mid-session, 1 min post-close, weekend, NYSE holiday, and the HST-evening edge (where `date.today()` in HST names tomorrow's ET session). Assert the completed-day helpers never name the in-progress session.

### 10.4 Live re-fetch gate (operator-witnessed)
After the price_history fix, run a real Schwab market-data fetch (operator's live env, GATE) over the open-trade + a sample of recently-erroring tickers and confirm on `/schwab/status` that the `OhlcvBar invariant violated` / bar-consistency error rate has collapsed (was ~16%). This is the empirical proof §9.1's claim holds. Per the seeded-gate discipline, also witness the UNSEEDED normal path (a routine pipeline run produces clean Schwab windows, no spurious yfinance fallbacks).

### 10.5 Topbar cross-VM consistency test
Per §7.4. Freeze `now` at a post-close evening so the three anchor families diverge; assert same-kind pages agree and no VM uses a naive-calendar date.

### 10.6 Quote regular-session test
A synthetic quote payload carrying both `lastPrice` (ext-hours) and `regularMarketLastPrice`: assert the mapper emits the regular value; a payload missing `regularMarketLastPrice` falls back to `lastPrice`.

### 10.7 Provider redaction / append-only invariants unchanged
Re-run the existing temporal-log append-only + provider-provenance tests; no regression.

### 10.8 Gate sequencing
Fast suite green on the merged HEAD (isolate known xdist date-flakes per `feedback_no_false_green_claim`) -> operator browser gate for the topbar consistency across pages (light + dark; the SVG-text gotcha is N/A here, topbar is text) -> operator live re-fetch gate (§10.4). The live Schwab fetch touches the operator's env; treat per the shared-dependency gate discipline (the brainstorm does NOT run it; it is a post-merge operator gate, like the schwabdev GATE-B cutover).

---

## 11. Schema impact (Q7)

**None.** v24 holds. Pure pull/anchor/guard logic + presentation + error taxonomy. No new column, no migration. The lock-guard makes "regular-session + completed-day verified" an **invariant** (guaranteed by construction), not recorded **data** -- so no provenance column is added (D4 prefer-no-schema). If a future arc wants auditable per-bar cleanliness provenance, that is a separate schema decision.

---

## 12. Slice recommendation (for writing-plans)

A single copowers cycle, sliced into mergeable units in dependency order:

1. **Slice A -- the ext-hours pull fix (L1, highest value).** `price_history` `needExtendedHoursData=False` + signature-pin + the typed `SchwabBarConsistencyError` + the OhlcvBar epsilon (§4.1, §9). Independently shippable; directly kills the ~16% error rate. Gated by the live re-fetch gate (§10.4).
2. **Slice B -- quotes regular-session (L1).** `regularMarket*` mapping + test (§4.2). Small; depends on the OQ-3 field-availability re-validation.
3. **Slice C -- completed-day write-barrier + lock-guard (L2/L3).** The archive write-barrier strip + the `_bar_for_date`/`build_ohlc_today_json` asserts + the anchor regression tests (§5, §6). The core lock-integrity work.
4. **Slice D -- uniform topbar policy (L6, Issue #5).** The `topbar_session_date` helper + routing every base-layout VM + the cross-VM test (§7). Presentation-only; operator browser gate.

Slices A and D are independent and could parallelize; B depends on A's error taxonomy landing first only if sharing the errors module; C is the keystone. Recommend A -> C -> (B, D) or A -> B -> C -> D linear if the implementer prefers one chain.

---

## 13. Open questions (flagged for the operator at writing-plans)

- **OQ-1 (resolved at brainstorm, restated):** enforcement locus = write-barrier strip + consumer slice. Confirm no consumer relies on a persisted current-day bar (grep `asof_date ==` / `iloc[-1]` archive reads; the audit found only `_bar_for_date`'s exact-date select, which is safe).
- **OQ-2:** the exact set of `OhlcvCache`/archive write paths that need the strip (P3 + L-C). Writing-plans must enumerate every write-through entry point (`_persist_window_to_archive`, `OhlcvCache.get_or_fetch` write, any direct `ohlcv_archive` writer) so the chokepoint is complete -- a missed write path defeats the "single chokepoint" guarantee.
- **OQ-3:** `quotes` regular-session field availability. Re-validate `regularMarketLastPrice`/`regularMarketTradeTime` exist under the project's quote `fields=` selection against a live quote or cassette. If absent, decide: widen the field selection vs rely on the `lastPrice` fallback (which re-admits ext-hours -> would violate L1 during pre/post-market). Operator call.
- **OQ-4:** `SchwabBarConsistencyError` placement in the exception hierarchy -- subclass of `SchwabApiError` (caught by the ladder's existing clause -> clean yfinance fallback) vs a sibling needing a new `except` branch. Recommend subclass for minimal ladder churn; confirm it does not change the audit `_classify_schwab_error` mapping unexpectedly.
- **OQ-5:** Issue #3 -- confirm the OUT disposition + whether to open the separate `_count_open_at_run` metrics-fix brief now or bank it.
- **OQ-6:** the epsilon magnitude (`1e-6` absolute). Confirm it is below the smallest meaningful price tick (sub-cent) for all instruments the tool trades.
- **OQ-7:** already-locked ext-hours bars. Per §4 out-of-scope, V1 is forward-only (clean from ship date). Confirm the operator accepts the already-locked historical observations as an L6-style limitation (no backfill/re-lock -- the lock is append-only).

---

## 14. Cumulative discipline (BINDING)

- **Session-anchor read/write mismatch family:** read the WRITER's anchor before locking a read predicate; the classifier enforces it. Issue #5 is the instance.
- **yfinance partial-bar strip + OHLCV-fetch-scope + F6 write-through-archive empty-result rule:** the write-barrier strip must retain prior cached content if stripping empties the window (never blank).
- **Schwab camelCase signature-pin:** re-validate `needExtendedHoursData` on 3.0.5; the price_history minute-default footgun stays handled (callers still pass `periodType=year/month, frequencyType=daily`); sandbox-vs-production domain-row gating preserved (market-data ladder falls through to yfinance under sandbox -> the ext-hours fix is production-relevant; sandbox already uses yfinance).
- **Append-only / lock-at-observation invariant (L3):** the guard adds rejection, never re-fetch/regeneration.
- **`feedback_verify_regression_test_arithmetic`:** every test value under both the old (ext-hours/current-day) and new (regular-session/completed-day) paths.
- **ZERO `Co-Authored-By`; ASCII discipline; no `--no-verify`; final `-m` paragraph plain prose; verify `git log -1 --format='%(trailers)'` is `[]`.**
- **Re-run the suite on the MERGED HEAD before any green claim** (isolate known date-sensitive xdist flakes); `feedback_no_false_green_claim`.
- **`feedback_seeded_gate_masks_default_state`:** witness the unseeded normal pipeline run at the live re-fetch gate, not only a seeded fetch.

---

## 15. Out of scope (do NOT design into V1)

- The broader Schwab Phase B/C (`cfg.data_source.primary` yfinance->schwab flip + parity study; trade automation).
- A rewrite of the date/session machinery (L4 -- harden + enforce the existing helpers only).
- Integration-review Issue #2 (non-uniform empty-state messaging) + Issue #4 (Schwab nav link) -- the separate polish batch.
- Issue #3's fix (the `_count_open_at_run` metrics predicate) -- audited here, routed to a separate small brief (§8).
- Historical backfill / re-locking of already-locked temporal-log bars (append-only; V1 forward-only -- clean from ship date; already-locked ext-hours observations are an accepted L6-style limitation).
- Intraday/sub-day precision (the tool is daily-bar; "current-day" means the in-progress daily session).
- Recording regular-session/completed-day provenance as schema data (Q7 -- it is an invariant, not data).

---

*End of design spec. Regular-session + completed-day data integrity: no extended-hours on any Schwab call (`price_history needExtendedHoursData=False` + quotes `regularMarket*`); discount the current/partial day via the write-barrier strip anchored on `last_completed_session`; a completed-day lock-guard at `_bar_for_date` + `build_ohlc_today_json` so the append-only temporal log can never lock a partial/extended bar; a uniform `topbar_session_date(page_kind)` policy across all base-layout VMs (Issue #5). Harden the existing machinery, don't rebuild it. No schema change. Issue #3 audited (metrics-predicate bug) and routed out.*
