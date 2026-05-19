# Phase 13 T1.SB0 — OhlcvCache → `_step_charts` wiring recon

**Task:** T-T1.SB0.1 — read-only inventory + recon document for the OhlcvCache → `_step_charts` wiring (Phase 13 plan §G.0).

**Goal of T1.SB0 (per plan §G.0):** Close Phase 11 Sub-bundle C R1 M#5 ACCEPT-WITH-RATIONALE V1 deferral. Wire `OhlcvCache` into `swing/pipeline/runner.py:_step_charts`. Substrate for Theme 2 detectors (T2.SB2+T2.SB3) + T3.SB3 review auto-fill.

**Scope of this recon:** read-only inventory. No code changes; no test changes. Produces the design constraints + discriminating-test plan for T-T1.SB0.2..4.

---

## §1 Current `_step_charts` data flow

**Callsite shape (`swing/pipeline/runner.py`):**

- `_step_charts(*, cfg, lease: Lease, eval_run_id: int, data_asof: str, fetcher: PriceFetcher) -> dict[str, Path]` at [swing/pipeline/runner.py:1204](swing/pipeline/runner.py#L1204).
- Outer-runner callsite at [swing/pipeline/runner.py:874-877](swing/pipeline/runner.py#L874-L877):
  ```python
  chart_paths = _step_charts(
      cfg=cfg, lease=lease, eval_run_id=eval_run_id,
      data_asof=lease_data_asof(cfg, lease), fetcher=fetcher,
  )
  ```
  where `fetcher = PriceFetcher(cache_dir=cfg.paths.prices_cache_dir, archive_history_days=cfg.archive.archive_history_days)` (from [swing/pipeline/runner.py:504-507](swing/pipeline/runner.py#L504-L507)).

**Single legacy OHLCV callsite inside `_step_charts`:** [swing/pipeline/runner.py:1323](swing/pipeline/runner.py#L1323):

```python
for ticker, pivot, stop, _source in targets:
    try:
        ohlcv = fetcher.get(ticker, lookback_days=200, as_of_date=None)
    except Exception:
        with lease.fenced_write() as conn:
            update_chart_target_status(
                conn, pipeline_run_id=lease.run_id, ticker=ticker,
                chart_status="fetcher_failed",
            )
        continue
    bars_60 = ohlcv.tail(60)
    try:
        classification = classify_flag(bars_60)
        ...
```

**Critical contracts to preserve:**

1. **Per-ticker exception → `fetcher_failed`** — any exception raised by the fetch call is caught, the ticker is marked `chart_status='fetcher_failed'`, and the loop continues. The new `OhlcvCache.get_or_fetch` MUST raise `ValueError` (or similar) on empty results — matching `PriceFetcher.get`'s existing raise-on-empty contract (see §2.A) — so that the existing `except Exception` clause still produces `fetcher_failed` and the operator-visible behavior is unchanged.
2. **`lookback_days=200`** — calendar-day window. The plan template hardcodes `window_days=180`; the wiring substitution must use `200` to preserve the existing chart window (Phase 13 plan §G.0 is a substrate dispatch, not a window-resize).
3. **`ohlcv.tail(60)` for classifier** — the returned DataFrame must support `.tail(60)`. Standard `pd.DataFrame` API; trivially preserved.
4. **`render_chart(ticker=..., ohlcv=ohlcv, pivot=..., stop=..., output_path=..., pattern_overlay=...)`** — the returned DataFrame must be acceptable to `render_chart`. Today's DataFrame has capitalized OHLCV columns + DatetimeIndex; T-T1.SB0.4 chart-bytes parity test asserts this.

**Exactly one `fetcher.get(...)` callsite inside `_step_charts`.** Grep confirms: `grep -n "fetcher.get" swing/pipeline/runner.py` yields the single line 1323 inside the function body. `_step_export` (line 887) also receives `fetcher=fetcher` but routes through `briefing.md` rendering — out of scope for T1.SB0 per plan §1.1 + §3 OUT OF SCOPE (chart rendering wiring only).

---

## §2 Existing OhlcvCache public surface

`swing/web/ohlcv_cache.py` (357 lines as of bd9d2a1). Phase 11 Sub-bundle C T-C.4 extended it with ladder support; R1 M#5 ACCEPT-WITH-RATIONALE V1-deferred the `_step_charts` wiring that T1.SB0 now lands.

### §2.A `PriceFetcher.get` (legacy callsite delegate)

`swing/prices.py:46-68`:

```python
def get(self, ticker: str, lookback_days: int, *, as_of_date: date | None = None) -> pd.DataFrame:
    effective = _resolve_asof(as_of_date)  # last_completed_session(now()) when None
    df = read_or_fetch_archive(
        ticker, end_date=effective,
        cache_dir=self.cache_dir, archive_history_days=self.archive_history_days,
    )
    if df is None or df.empty:
        raise ValueError(f"No data for {ticker}")
    cutoff = effective - timedelta(days=lookback_days)
    sliced = df.loc[(df.index.date >= cutoff) & (df.index.date <= effective)]
    if sliced.empty:
        raise ValueError(f"No data for {ticker}")
    return sliced
```

**Shape returned:** `pd.DataFrame` indexed by date (DatetimeIndex) with capitalized columns Open/High/Low/Close/Volume (inherited from `read_or_fetch_archive`'s output).

**Window semantics:** calendar-day lookback (NOT trading-day; the slice uses `df.index.date >= cutoff` against the calendar-day cutoff).

### §2.B `OhlcvCache` public methods (current state, before T-T1.SB0.2)

`swing/web/ohlcv_cache.py`:

- `__init__(cfg: Config)` ([swing/web/ohlcv_cache.py:78](swing/web/ohlcv_cache.py#L78)) — TTL, semaphore, breaker, `_store: dict[str, tuple[OhlcvBundle, float]]`, `_lock: threading.Lock`.
- `set_ladder_bars_fetcher(fetcher)` ([swing/web/ohlcv_cache.py:98](swing/web/ohlcv_cache.py#L98)) — install ladder hook returning `(bars_df, provider_tag)`. Used by `_install_pipeline_marketdata_caches` ([swing/pipeline/runner.py:410](swing/pipeline/runner.py#L410)).
- `get_many_bundles(tickers, *, deadline_seconds, executor) -> dict[str, OhlcvBundle]` ([swing/web/ohlcv_cache.py:119](swing/web/ohlcv_cache.py#L119)) — async fan-out via executor; returns `OhlcvBundle` (SMA10/20/50 + previous_close + ADR% + fetched_at + provider; NOT a DataFrame).
- `is_degraded()` / `reset_circuit_breaker()` — breaker state.

**Internal:**

- `_fetch_bundle_worker(ticker) -> tuple[OhlcvBundle, bool]` ([swing/web/ohlcv_cache.py:274](swing/web/ohlcv_cache.py#L274)) — acquires semaphore; on miss calls `_ladder_bars_fetcher(ticker)` (if set) OR `ohlcv_mod.fetch_daily_bars(ticker, n_bars=60, cache_dir=..., archive_history_days=...)`. Returns bundle + source-healthy flag.
- `_record_outcome`/`_record_neutral`/`_maybe_trip_breaker` — sliding-window breaker plumbing.

**Gap identified:** `OhlcvCache` does NOT expose a `get_or_fetch(ticker, window_days) -> DataFrame` method. Plan §G.0 T-T1.SB0.2 must add it.

### §2.C `fetch_daily_bars` (`swing/pipeline/ohlcv.py:20-57`)

```python
def fetch_daily_bars(
    ticker: str, *, n_bars: int = 60, as_of_date: date | None = None,
    cache_dir: Path, archive_history_days: int,
) -> pd.DataFrame | None:
    session = as_of_date or action_session_for_run(datetime.now())
    df = read_or_fetch_archive(ticker, end_date=session, cache_dir=cache_dir, archive_history_days=archive_history_days)
    if df is None or df.empty:
        return None
    last_date = df.index[-1].date()
    if last_date >= session:
        df = df.iloc[:-1]  # strip in-progress bar (CLAUDE.md gotcha)
    if df.empty:
        return None
    return df.tail(n_bars)
```

**Note** — `fetch_daily_bars` takes `n_bars` (trailing rows), NOT `lookback_days` (calendar window). Different semantics from `PriceFetcher.get`. Both delegate to `read_or_fetch_archive`, so the underlying full-history DataFrame is identical; the slice shape differs.

`fetch_daily_bars` also anchors at `action_session_for_run(datetime.now())` (forward-looking) whereas `PriceFetcher.get` anchors at `last_completed_session(datetime.now())` (backward-looking) via `_resolve_asof`. Subtle session-anchor divergence (existing CLAUDE.md gotcha family: "Session-anchor read/write mismatch"). For T1.SB0's chart-fetch role, the existing legacy callsite uses `PriceFetcher.get` semantics (backward-looking). The new `OhlcvCache.get_or_fetch` must mirror `PriceFetcher.get` to be a drop-in replacement at line 1323.

### §2.D Plan defect identified — shape-parity test parameter mismatch

Plan §G.0 T-T1.SB0.2 Step 1 test template calls:

```python
legacy_df = fetch_daily_bars(ticker='AAPL', lookback_days=180, as_of_date=None)
```

**This fails at parse time** — `fetch_daily_bars` does NOT accept `lookback_days` (it accepts `n_bars`). Per brief §8 ("If plan §G.0 per-step instructions conflict with reality, STOP + escalate") + dispatch brief §0.5 + per the SUBSTRATE plan §G.0 instructions (acceptance criteria says "DataFrames identical between cache + legacy paths"), the test INTENT is shape parity against the `_step_charts` legacy callsite's actual delegate.

**Adaptation (banked + cited in return report; pre-emption candidate for plan §K addendum):** the shape-parity test in T-T1.SB0.2 compares against `PriceFetcher.get(ticker='AAPL', lookback_days=180, as_of_date=None)` — the same helper used by the existing line-1323 callsite. This is the BEST shape-parity discriminator because it matches the LEGACY callsite the new method is replacing.

Will document in §6 of this recon + reflect in T-T1.SB0.2 test + cite in return report.

---

## §3 Shape semantics: cache surface vs legacy

| Aspect | `PriceFetcher.get` | `OhlcvCache._fetch_bundle_worker` (bundle path) | Proposed `OhlcvCache.get_or_fetch` (new) |
|---|---|---|---|
| Return type | `pd.DataFrame` (raises on empty) | `OhlcvBundle` (None-fields on empty) | `pd.DataFrame` (raises on empty) |
| Window semantics | `lookback_days` calendar-day window | `n_bars=60` trailing rows | `window_days` calendar-day window |
| Session anchor | `last_completed_session(now())` (backward) | `n_bars` tail (no anchor needed) | `last_completed_session(now())` (backward) |
| Columns | Capitalized OHLCV | Bundle floats (no DF) | Capitalized OHLCV |
| Index | DatetimeIndex | n/a | DatetimeIndex |
| In-progress bar strip | inherited from `read_or_fetch_archive` | `fetch_daily_bars` strips | inherited from `read_or_fetch_archive` + belt-and-suspenders strip |
| Ladder support | NO | YES via `_ladder_bars_fetcher` | YES via `_ladder_bars_fetcher` (reuses same hook) |

**Shape parity assertion** (T-T1.SB0.2 acceptance): `OhlcvCache.get_or_fetch(ticker='X', window_days=K).equals(PriceFetcher(...).get(ticker='X', lookback_days=K, as_of_date=None))` for a fixture ticker.

---

## §4 Per-cache locking + concurrent-fetch discipline

### §4.A Existing OhlcvCache locking

- `self._lock = threading.Lock()` ([swing/web/ohlcv_cache.py:82](swing/web/ohlcv_cache.py#L82)) — guards `_store`, `_failure_window`, `_degraded_until` mutations.
- `self._sema = threading.Semaphore(cfg.web.max_concurrent_ohlcv_fetches)` — bounds executor parallelism in the bundle path.
- **Cache+executor race discipline (CLAUDE.md gotcha)** — worker returns pure value; request thread writes `_store` ONLY for completed-in-deadline futures. `fut.cancel()` is a no-op on a running worker, so a late-completing worker MUST NOT write to `_store` (it would overwrite the empty-bundle the request thread already returned).

### §4.B New bars-store locking discipline (for `get_or_fetch`)

`get_or_fetch` is **synchronous** (no executor). Concurrency arrives via the test scenario: 5 threads × 5 tickers, each calling `get_or_fetch` directly. Discipline:

1. Add `self._bars_lock = threading.Lock()` (separate from bundle `self._lock` to avoid contention with concurrent bundle traffic on dashboard renders).
2. Add `self._bars_store: dict[tuple[str, int], tuple[pd.DataFrame, float]]` keyed by `(ticker_upper, window_days)` so different windows for the same ticker cache independently.
3. **Pattern**: acquire bars-lock → check cache → release lock → fetch (no lock) → acquire lock → write cache → release lock. Fetch performed without lock held (prevents lock-during-I/O serialization).
4. **Race window**: two threads racing on the same `(ticker, window_days)` will each fetch independently and each write; last-writer-wins. Both fetches see the same archive-source, so values are identical; no data corruption possible. The waste (duplicate fetch) is acceptable for V1 — adding per-key in-flight tracking is V2 candidate.

**No breaker participation** for the bars path in V1 — keeps the wiring surgical. The bundle-path breaker still fires for the dashboard surface; the chart path retains its existing per-ticker `fetcher_failed` semantics. Documented as a V2 candidate banked here.

### §4.C Cache+executor race gotcha (CLAUDE.md) — does it apply?

**No, not directly.** The gotcha applies to async executor-dispatched workers. `get_or_fetch` is synchronous — there is no future to cancel. The discipline that DOES apply: bars-lock must NOT be held during the actual fetch call (otherwise concurrent calls serialize through the lock + I/O). Pattern above satisfies this.

---

## §5 Ladder routing semantics

The existing OhlcvCache ladder hook `_ladder_bars_fetcher: Callable[[str], tuple[Any, str]] | None` returns `(bars_df_or_none, provider_tag)`. Installed in pipeline runs via `_install_pipeline_marketdata_caches` ([swing/pipeline/runner.py:410](swing/pipeline/runner.py#L410)) when a Schwab client is constructed:

```python
def _bars_hook(ticker: str):
    conn = connect(cfg.paths.db_path)
    try:
        window, provider_tag = fetch_window_via_ladder(
            ticker, start=None, end=None, cfg=cfg, schwab_client=schwab_client,
            yfinance_fallback_fn=_yf_window_fallback, conn=conn,
            surface="pipeline", pipeline_run_id=pipeline_run_id,
        )
    finally:
        conn.close()
    if provider_tag == "schwab_api" and hasattr(window, "to_dataframe"):
        bars = window.to_dataframe()
    else:
        bars = window
    return (bars, provider_tag)
```

**Sandbox short-circuit** lives inside `fetch_window_via_ladder` per T-C.3 §H.6.1 LOCK — when `cfg.integrations.schwab.environment != 'production'`, the ladder falls through to the yfinance fallback. `get_or_fetch` participates transparently — the ladder layer is env-aware; `get_or_fetch` is env-agnostic.

**Ladder window shape** — `SchwabPriceHistoryWindow.to_dataframe()` returns the same capitalized-OHLCV + DatetimeIndex shape as `read_or_fetch_archive` per Phase 11 Sub-bundle C T-C.1 contract. Verified in `tests/integration/test_pipeline_marketdata_ladder_integration.py`.

**Ladder window range** — when called with `start=None, end=None`, the ladder defaults to the full archive_history_days window. `get_or_fetch` MUST slice the ladder-returned DataFrame to `window_days` (calendar-day cutoff) before returning, mirroring `PriceFetcher.get`'s slice. Otherwise the chart receives a >>200-day window and the legacy `bars_60 = ohlcv.tail(60)` still works but `render_chart` may receive an unexpectedly wide window.

---

## §6 Discriminating-test plant proposal

### §6.A T-T1.SB0.2: shape-parity (`tests/pipeline/test_ohlcv_cache_shape_parity.py`)

**Adaptation note:** plan template uses `fetch_daily_bars(ticker, lookback_days=180, as_of_date=None)` — which raises TypeError (parameter doesn't exist). Adapt to use `PriceFetcher.get` (the actual legacy callsite delegate):

```python
def test_ohlcv_cache_get_or_fetch_shape_matches_legacy_price_fetcher(tmp_path, monkeypatch):
    # Monkeypatch read_or_fetch_archive to return a deterministic fixture.
    # Construct OhlcvCache + PriceFetcher pointed at same fixture.
    # Assert both return DataFrames with identical columns/index/values.
```

Monkeypatch `swing.data.ohlcv_archive.read_or_fetch_archive` (or `swing.pipeline.ohlcv.read_or_fetch_archive` — same module, imported), so the test is deterministic + does not hit yfinance.

**Discriminator:** without `get_or_fetch` implementation → AttributeError. With shape drift → `assert_frame_equal` failure with diagnostic. With shape parity → PASS.

### §6.B T-T1.SB0.3: wiring (`tests/pipeline/test_step_charts_ohlcv_cache_wiring.py`)

```python
def test_step_charts_uses_ohlcv_cache_not_legacy_fetcher(...):
    # Build OhlcvCache with monkeypatched fetcher (no network).
    # Invoke _step_charts(... ohlcv_cache=cache); assert it calls
    # cache.get_or_fetch (spy); assert legacy fetcher.get is NOT invoked.
    # (Alternative: pass mock with get_or_fetch attribute; assert called.)
```

**Discriminator:** before T-T1.SB0.3 wiring → `_step_charts` calls legacy `fetcher.get` → mock-spy on `cache.get_or_fetch` shows zero invocations → assertion fails. After wiring → spy shows N invocations (one per target ticker) → assertion passes.

### §6.C T-T1.SB0.4: concurrent-fetch no-race (`tests/pipeline/test_ohlcv_cache_concurrent_fetch_no_race.py`)

```python
def test_ohlcv_cache_concurrent_multi_ticker_no_data_corruption(...):
    # 5 threads × 5 distinct tickers, each calling cache.get_or_fetch.
    # Assert: no exceptions raised; each thread receives its OWN ticker's frame;
    # cache._bars_store contains exactly 5 entries.
```

**Discriminator:** pre-implementation race (no lock around `_bars_store` writes) → may pass on Windows GIL (dict insertions are atomic for single keys), but a defense-in-depth lock + the assertion provides forward-binding evidence that locking is intentional. Test asserts both "no exception" and "no cross-ticker leakage" (each `results[ticker]` has rows matching ticker's fixture).

### §6.D T-T1.SB0.4: chart-bytes parity (`tests/pipeline/test_chart_bytes_parity_through_ohlcv_cache.py`)

```python
def test_chart_bytes_match_between_cache_and_legacy_paths(tmp_path, monkeypatch):
    # Monkeypatch read_or_fetch_archive to return a fixed fixture DataFrame.
    # df_cache = OhlcvCache(...).get_or_fetch(ticker='AAPL', window_days=200)
    # df_legacy = PriceFetcher(...).get('AAPL', lookback_days=200, as_of_date=None)
    # render_chart(... ohlcv=df_cache, output_path=p1) → bytes1
    # render_chart(... ohlcv=df_legacy, output_path=p2) → bytes2
    # Assert bytes1 == bytes2 (or PNG-bytes are byte-identical for the same input).
```

**Discriminator:** chart bytes must be identical when the input DataFrames are identical. If `get_or_fetch` sliced differently from `PriceFetcher.get` (e.g., different window cutoff), the rendered chart's x-axis range would differ → bytes diverge → test fails. Strong shape-AND-content parity assertion.

### §6.E Cross-bundle pin (T-T1.SB0.4 closer)

`test_ohlcv_cache_get_or_fetch_invariant` — pin asserting the public method signature + return-shape invariants:

```python
@pytest.mark.skip(reason="un-skips at T2.SB2 + T2.SB3 + T3.SB3 per plan §H.3")
def test_ohlcv_cache_get_or_fetch_invariant():
    """Cross-bundle pin (per plan §H.3): T2.SB2 + T2.SB3 + T3.SB3 consumers will
    un-skip this test. Asserts the get_or_fetch surface is stable."""
    cache = OhlcvCache(cfg=load_cfg())
    assert hasattr(cache, 'get_or_fetch')
    assert callable(cache.get_or_fetch)
    # Signature check via inspect.signature
    sig = inspect.signature(cache.get_or_fetch)
    assert 'ticker' in sig.parameters
    assert 'window_days' in sig.parameters
```

The pin sits skip-marked; consumers un-skip when they begin to depend on the surface.

---

## §7 Acceptance criteria for the remaining tasks (per plan §G.0)

| Task | Acceptance |
|---|---|
| T-T1.SB0.2 | `OhlcvCache.get_or_fetch` exists; shape-parity test PASS. |
| T-T1.SB0.3 | `_step_charts` no longer invokes `PriceFetcher.get` directly for chart-OHLCV; all existing pipeline tests pass. |
| T-T1.SB0.4 | Concurrent multi-ticker fetch no-race PASS; chart-bytes parity PASS; ruff 0 E501. |

---

## §8 LOCKS preserved + V2 candidates banked

**Preserved (inherited LOCKS per dispatch brief §1.3 + plan §A):**

- L1 no run-time AI inferencing — T1.SB0 ships zero AI code.
- L5 no drift-logging code — T1.SB0 ships zero drift code.
- L6 schema v19 UNCHANGED — T1.SB0 is consumer-side wiring only.
- OHLCV fetch scope = open-trade tickers ONLY (existing CLAUDE.md gotcha) — preserved by NOT changing `targets` composition in `_step_charts`.
- Cache+executor race (CLAUDE.md gotcha) — preserved (synchronous get_or_fetch; no executor change).
- yfinance regression family (CLAUDE.md gotchas) — preserved (no yfinance direct call changes; routes through existing `read_or_fetch_archive` + ladder hooks).
- Phase 11 sliding-window breaker (bundle path) — preserved (separate `_bars_lock`; no mutation of breaker state from `get_or_fetch`).

**V2 candidates banked (out of scope for T1.SB0):**

- **V2-A**: breaker participation for bars path — would unify cache health across bundle + bars surfaces. Surgical T1.SB0 omits; defer.
- **V2-B**: per-key in-flight dedup — eliminates duplicate fetches when N threads race on same `(ticker, window_days)`. T1.SB0 accepts the duplicate-fetch waste; defer.
- **V2-C**: `get_or_fetch` async variant via executor — for batch chart rendering at scale. T1.SB0 keeps synchronous; defer.

---

## §9 Pre-emptions for adversarial review

| Watch item | Pre-emption |
|---|---|
| Plan §G.0 test template hardcodes `fetch_daily_bars(ticker, lookback_days=180)` which is a parameter-name mismatch | §2.D — adapted test compares against `PriceFetcher.get` (actual legacy callsite delegate); reflected in T-T1.SB0.2 test code + return report |
| `_step_charts` calls `fetcher.get(..., lookback_days=200)` but plan template hardcodes `window_days=180` | T-T1.SB0.3 wiring substitution uses `window_days=200` (preserves existing chart window) |
| `_step_charts` signature changes `fetcher: PriceFetcher` → `ohlcv_cache: OhlcvCache`; outer-runner callsite (line 874-877) must also change | Update outer-runner callsite in same T-T1.SB0.3 commit |
| In sandbox/no-Schwab env, `_install_pipeline_marketdata_caches` returns `(None, None)` — no OhlcvCache exists | T-T1.SB0.3 must handle the `ohlcv_cache is None` path — either construct a fallback `OhlcvCache(cfg)` for chart-fetch use, or keep `_step_charts` signature accepting `OhlcvCache` and construct one unconditionally at the runner level (`OhlcvCache(cfg)` works without a Schwab client; ladder hook is just None) |
| Render_chart shape expectations | T-T1.SB0.4 chart-bytes parity test PROVES no shape drift |
| Session-anchor mismatch (action_session_for_run vs last_completed_session) | `get_or_fetch` MUST anchor at `last_completed_session(now())` to match `PriceFetcher.get` semantics (preserved at line 1323 callsite). DO NOT use `action_session_for_run`. |
| Empty result handling | `get_or_fetch` MUST raise `ValueError` on empty (matching `PriceFetcher.get`) so existing line 1322-1330 `except Exception` produces `fetcher_failed`. |
| ASCII-only on runtime CLI paths (Windows cp1252) | No new CLI text in T1.SB0; no risk. Existing pipeline-run CLI output is unchanged. |
| Co-Authored-By footer drift | ZERO across all T1.SB0 commits — convention BINDING per dispatch brief §4. |

---

## §10 Outer-runner callsite for `_step_charts` (T-T1.SB0.3 modification)

`swing/pipeline/runner.py:738` constructs `(price_cache, _ohlcv_cache) = _install_pipeline_marketdata_caches(...)` where `_ohlcv_cache` is the leading-underscore intentionally-not-consumed reference (Phase 11 R1 M#5 deferral artifact).

**T-T1.SB0.3 must:**

1. Rename `_ohlcv_cache` → `ohlcv_cache` at line 738 (the variable is now consumed).
2. Construct a fallback `OhlcvCache(cfg)` when `_install_pipeline_marketdata_caches` returns `(None, None)` (no Schwab client). The cache works without a ladder hook — `_fetch_bundle_worker` falls through to `ohlcv_mod.fetch_daily_bars`. The new `get_or_fetch` similarly falls through to `read_or_fetch_archive` directly.
3. Update the `_step_charts` callsite ([swing/pipeline/runner.py:874-877](swing/pipeline/runner.py#L874-L877)) to pass `ohlcv_cache=ohlcv_cache` (rename param from `fetcher` to `ohlcv_cache` per plan §G.0 T-T1.SB0.3 Step 3).

The Phase 11 R1 M#5 comment block ([swing/pipeline/runner.py:716-736](swing/pipeline/runner.py#L716-L736)) should be removed or updated to record that T1.SB0 closes the deferral.

---

## §11 References

- **Plan**: `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` §G.0 (lines 803-1043).
- **Spec**: `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md` §4.1 + §4.4.
- **Dispatch brief**: `docs/phase13-t1-sb0-executing-plans-dispatch-brief.md`.
- **Phase 11 R1 M#5 ACCEPT-WITH-RATIONALE V1 deferral**: comment block at [swing/pipeline/runner.py:716-736](swing/pipeline/runner.py#L716-L736).
- **CLAUDE.md gotchas**: cache+executor race; yfinance regressions; session-anchor mismatch; matplotlib mathtext; cp1252 stdout; USERPROFILE+HOME monkeypatch.

---

*End of recon. T-T1.SB0.1 produces this document; subsequent tasks act on §6 test plant + §10 outer-runner callsite + §9 pre-emptions. Plan defects §2.D + §9 are adapted on-the-fly + cited in return report per dispatch brief §1.5 forward-binding lesson #7 (implementer self-report accuracy gate).*
