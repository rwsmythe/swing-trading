# Phase 13 T1.SB0 gate-fix — T-GF1 diagnostic recon

**Task:** T-GF1 — investigation-first recon for the S3 visual chart regression observed on operator's CVGI chart after T1.SB0 merge (HEAD `418bcc8` + housekeeping `dc0cfea` + briefs `4a52f3a`/`0fe361d`).

**Brief reference:** [`docs/phase13-t1-sb0-gate-fix-dispatch-brief.md`](phase13-t1-sb0-gate-fix-dispatch-brief.md) §1.2 failure hypothesis + §1.3 fix-shape options + §1.6 forward-binding lessons.

**Verdict:** Brief's hypothesis (weekly-refresh / `archive_history_days` semantic divergence) **EMPIRICALLY FALSIFIED** by side-by-side inspection of operator's actual CVGI archive files. Real root cause identified at the **Schwab `price_history` ladder layer**, not at `read_or_fetch_archive`. New fix shape proposed — see §4.

---

## §1 Hypothesis verification against operator's real CVGI archive

Both `read_or_fetch_archive` (consumed by `PriceFetcher.get` and the no-ladder branch of `OhlcvCache._fetch_bars_window`) anchor at `last_completed_session(now())` (backward-looking) and slice on a calendar-day cutoff. End-to-end the two code paths produce IDENTICAL output against the same legacy parquet — the chart-bytes parity test verifies this byte-for-byte ([`tests/pipeline/test_chart_bytes_parity_through_ohlcv_cache.py`](../tests/pipeline/test_chart_bytes_parity_through_ohlcv_cache.py)).

**Empirical proof: operator's CVGI archive files at `~/swing-data/prices-cache/`:**

| File | Shape | Rows | Unique dates | Date range | Price range | Volume range |
|---|---|---|---|---|---|---|
| `CVGI.parquet` (legacy) | DatetimeIndex + capitalized OHLCV | **1260** | **1260** | 2021-05-12 → 2026-05-18 | $0.83 → $12.60 | 16,700 → 46,303,400 |
| `CVGI.schwab_api.parquet` (Shape A) | `asof_date` column + lowercase OHLCV | **2780** | **10** | 2026-05-05 → 2026-05-18 | $4.04 → $5.78 | **8 → 96,881** |

**Diagnosis: the Shape A Schwab archive is contaminated with 1-MINUTE INTRADAY BARS, not daily bars.** 2780 rows ÷ 10 unique dates = ~278 bars per date. That is consistent with regular-hours minute bars at 1-minute frequency for 10 trading days (6.5 hr × 60 min = 390 bars, less ~100 missing-trade minutes per date).

The legacy `CVGI.parquet` is fresh + correct (1260 unique daily bars, ending 2026-05-18). It is NOT stale; `read_or_fetch_archive` is functioning correctly. The brief's hypothesis (gap-fill / weekly-refresh semantics) is therefore **falsified** — `read_or_fetch_archive` writes 1260 fresh daily rows; the regression is downstream of it.

**Operator's S3 evidence aligns exactly:**

- "~30-40 narrow-window bars" → mplfinance renders 2780 candles compressed into 10 distinct dates; visual appearance is a dense cluster of ~30-40 distinguishable groups.
- "x-axis '00:00' time-of-day labels" → all Shape A bars' `asof_date` is an ISO date string (`YYYY-MM-DD`); `pd.to_datetime("2026-05-15")` returns `Timestamp('2026-05-15 00:00:00')`; mplfinance labels render midnight times.
- "price range $5.0-$5.3 (narrow consolidation only)" → 10 trading days ending 2026-05-18 is exactly the post-breakout consolidation window for CVGI ($4.04-$5.78 full range; intra-window dominated by $5.0-$5.3 visible cluster).
- "volume 5K-10K (raw shares; no millions annotation)" → 1-minute volumes per bar are 8 to 96,881; the chart's volume axis auto-scales to the per-bar range, dropping the `1e6` annotation that the daily-bar chart used.
- CTRA "no price data found (1d 2026-05-08 → 2026-05-19)" → SEPARATE issue (legacy archive incremental gap-fill for a delisted ticker; `1d` frequency confirms YFINANCE fallback path; unrelated to the chart-regression root cause).

---

## §2 Root cause — file:line evidence

### §2.A Where the bad data enters the system

[`swing/integrations/schwab/marketdata_ladder.py:417-426`](../swing/integrations/schwab/marketdata_ladder.py#L417-L426) — `fetch_window_via_ladder` invokes `get_price_history` with `start_dt=start, end_dt=end` (both `None` when called from `_bars_hook` per [`swing/pipeline/runner.py:390-399`](../swing/pipeline/runner.py#L390-L399)) AND with **NO** `period_type` / `period` / `frequency_type` / `frequency` kwargs:

```python
schwab_window = get_price_history(
    schwab_client,
    conn,
    ticker,
    start_dt=start,   # None
    end_dt=end,       # None
    surface=surface,
    environment="production",
    pipeline_run_id=pipeline_run_id,
)
```

[`swing/integrations/schwab/marketdata.py:329-405`](../swing/integrations/schwab/marketdata.py#L329-L405) — `get_price_history` then defaults all `period_type` / `period` / `frequency_type` / `frequency` kwargs to `None` and forwards `None` straight through to schwabdev:

```python
return client.price_history(
    symbol,
    periodType=period_type,       # None
    period=period,                 # None
    frequencyType=frequency_type,  # None
    frequency=frequency,            # None
    startDate=start_dt,             # None
    endDate=end_dt,                 # None
)
```

### §2.B What Schwab returns when ALL kwargs are None

Per [`reference/schwabdev/api-calls.md:425-435`](../reference/schwabdev/api-calls.md#L425-L435), the Schwab `price_history` API defaults when params are unspecified:

- `periodType` → `"day"` (no explicit default; server-side default for the day-period regime)
- `period` → **`10`** (server-default for `day`-periodType)
- `frequencyType` → **`"minute"`** (the ONLY allowed value for `day`-periodType; server default)
- `frequency` → **`1`** (server-default for `minute`-frequencyType)

So `client.price_history(symbol)` returns **10 days of 1-MINUTE intraday bars** (~2730-3900 candles per ticker depending on session length / holidays / no-trade minutes).

### §2.C How the bad data poisons the chart-step + Shape A archive

1. The mapper at [`swing/integrations/schwab/mappers.py:817-828`](../swing/integrations/schwab/mappers.py#L817-L828) converts each per-minute candle's `datetime` (epoch ms) into `OhlcvBar(asof_date=datetime.fromtimestamp(ms/1000, tz=UTC).date().isoformat(), ...)`. So ~3000 minute candles become ~3000 `OhlcvBar` instances with only ~10 distinct `asof_date` values.

2. The ladder persists this to the Shape A archive via [`swing/integrations/schwab/marketdata_ladder.py:100-120`](../swing/integrations/schwab/marketdata_ladder.py#L100-L120) `_schwab_window_to_shape_a_df` → [`swing/data/ohlcv_archive.py:281-369`](../swing/data/ohlcv_archive.py#L281-L369) `write_window`. The "merge-by-asof_date" deduplication at lines 358-361 uses `drop_duplicates(subset=["asof_date"], keep="last")` — but since the INCOMING window has many rows per `asof_date`, "keep last" picks the LAST minute-bar per date, **silently overwriting any prior daily-bar Shape A content with the last-minute-of-day intraday bar**.

3. [`swing/integrations/schwab/models.py:602-642`](../swing/integrations/schwab/models.py#L602-L642) `SchwabPriceHistoryWindow.to_dataframe()` constructs an in-memory DataFrame indexed by `pd.to_datetime([bar.asof_date for bar in self.bars])`. Each `asof_date` is a date-only ISO string, so `pd.to_datetime` returns midnight timestamps. With 2780 rows sharing ~10 unique midnight timestamps, the DataFrame has 2780 rows with duplicate index entries.

4. [`swing/web/ohlcv_cache.py:198-256`](../swing/web/ohlcv_cache.py#L198-L256) `_fetch_bars_window` consumes the to_dataframe output, applies the strict-greater partial-bar strip (CLAUDE.md inequality-discipline gotcha; correct here), and slices by `bars.index.date >= cutoff & <= end`. The slice retains ALL 2780 rows because every row's `.date` falls within the 200-calendar-day window.

5. [`swing/pipeline/runner.py:1322-1358`](../swing/pipeline/runner.py#L1322-L1358) `_step_charts` passes the 2780-row DataFrame to `render_chart`. mplfinance renders 2780 candles compressed into 10 unique x-positions; the chart looks like "30-40 narrow-window bars with 00:00 time-of-day labels and per-minute volume scale" — exactly the operator's S3 evidence.

### §2.D Why the no-ladder path is unaffected

When `_install_pipeline_marketdata_caches` returns `(None, None)` (no Schwab client constructed; sandbox or missing creds), the runner constructs a fallback `OhlcvCache(cfg)` per Phase 11 Sub-bundle C contract. That cache has NO `_ladder_bars_fetcher` installed, so `_fetch_bars_window` takes the bare `read_or_fetch_archive` branch at [`swing/web/ohlcv_cache.py:228-236`](../swing/web/ohlcv_cache.py#L228-L236). That branch returns the legacy daily-bar archive correctly. The regression is **production-Schwab-environment-only** — sandbox / no-Schwab operators would not see it.

### §2.E Why the byte-parity test missed the regression

[`tests/pipeline/test_chart_bytes_parity_through_ohlcv_cache.py:64-139`](../tests/pipeline/test_chart_bytes_parity_through_ohlcv_cache.py#L64-L139) constructs an `OhlcvCache(cfg=cfg)` WITHOUT calling `set_ladder_bars_fetcher` → the test exercises the bare `read_or_fetch_archive` branch in `_fetch_bars_window`. The ladder path is never invoked. Both test paths (cache + PriceFetcher) consume IDENTICAL stub fixtures via `monkeypatch.setattr("swing.web.ohlcv_cache.read_or_fetch_archive", _stub_read)` so they trivially produce byte-identical PNGs. **The test passes pre-merge AND post-fix; it cannot detect ladder-path regressions by construction.**

This validates the brief §1.6 forward-binding lesson #1: "Byte-parity test as algorithmic substitute for operator-visual gate is INSUFFICIENT when test fixtures bypass production data-derivation paths." The test is correct AS WRITTEN for its scope (cache-vs-PriceFetcher shape parity), but the wiring's production blast radius extends beyond that scope.

---

## §3 Why T1.SB0 (and the Phase 11 Sub-bundle C R1 M#5 V1 deferral comment) missed this

The Phase 11 Sub-bundle C R1 M#5 deferral comment flagged "(a) a sweeping refactor of fetcher.get's weekly-refresh + archive_history_days semantics to align with the ladder's window semantics" — but this was framed as a yfinance/archive-side concern. The Schwab `price_history` minute-default footgun was NOT mentioned in any plan / recon / spec under Phase 11 Sub-bundle C or Phase 13 T1.SB0.

The CLI verify path at [`swing/cli_schwab.py:1100-1111`](../swing/cli_schwab.py#L1100-L1111) **explicitly** passes `period_type="month", period=1, frequency_type="daily", frequency=1` — proving the architectural intent IS for the ladder to fetch daily bars. The `_bars_hook` callsite simply forgot to mirror those kwargs. This is a copy-paste-or-forgetting-defaults defect, NOT a design flaw.

---

## §4 Selected fix shape (REVISES brief §1.3 A/B/C; alternative shape per §1.2 "implementer VERIFIES + may revise")

### §4.A Fix shape D — explicit daily-bar Schwab kwargs through `fetch_window_via_ladder`

**Files modified:**

1. **`swing/integrations/schwab/marketdata_ladder.py:358-449`** — extend `fetch_window_via_ladder` signature to accept `period_type` / `period` / `frequency_type` / `frequency` kwargs (default `None`); forward them verbatim to `get_price_history`. Backward-compatible: when all four are `None`, behavior is unchanged from today (preserved for any other caller; currently only one caller — `_bars_hook` — so blast radius is `_bars_hook` ONLY).

2. **`swing/pipeline/runner.py:383-410`** — `_bars_hook` passes `period_type="year", period=5, frequency_type="daily", frequency=1` to `fetch_window_via_ladder`. The `(year, 5, daily, 1)` tuple = "5 years of daily bars" per Schwab API table; matches `cfg.archive.archive_history_days = 1260` ≈ 5 trading years.

3. **`swing/web/ohlcv_cache.py`** — UNCHANGED. The ladder hook contract is preserved (still `(bars_df_or_none, provider_tag)`); the cache layer is agnostic to which Schwab kwargs the hook uses.

4. **`swing/data/ohlcv_archive.py`** — UNCHANGED.

5. **`swing/integrations/schwab/marketdata.py:get_price_history`** — UNCHANGED. The wrapper's defaults stay `None` for backward compatibility with the CLI verify path (which passes its own explicit `month/1/daily/1` kwargs).

### §4.B Why NOT the alternative "change `get_price_history` defaults to daily"

Option B (modify `get_price_history` defaults from `None` to daily) was considered + rejected:

- The wrapper's `None`-default contract is documented at [`swing/integrations/schwab/marketdata.py:329-353`](../swing/integrations/schwab/marketdata.py#L329-L353) as "pass-through to Schwab" — changing this default would be a silent contract break for any future caller assuming explicit Schwab defaults.
- The defect is at the CALLSITE (`_bars_hook` forgetting to pass kwargs), not at the wrapper. Fix where the bug is.
- The CLI verify callsite at [`swing/cli_schwab.py:1100-1111`](../swing/cli_schwab.py#L1100-L1111) explicitly passes `month/1/daily/1` — proving the pattern. `_bars_hook` simply needs to mirror it.

### §4.C Operator's corrupted CVGI.schwab_api.parquet — recovery posture

The operator's `~/swing-data/prices-cache/CVGI.schwab_api.parquet` (2780 rows × 10 unique dates) is contaminated with minute-frequency data from prior runs. Post-fix, on the next pipeline run's FIRST SUCCESSFUL Schwab daily fetch for each affected ticker:

1. Invoke `_bars_hook` → `fetch_window_via_ladder` with daily kwargs → `get_price_history` requests ~5y of daily bars.
2. Mapper produces `OhlcvBar` instances with unique daily `asof_date`s.
3. `write_window` merges the new daily bars with the existing minute-bar Shape A archive via `drop_duplicates(subset=["asof_date"], keep="last")`. The **NEW daily bars win** on conflict for the 10 overlapping dates; daily bars for the other ~1250 dates are appended. **Post-fix Shape A archive will be ~1260 unique daily rows** (no operator intervention required).

**Recovery conditioning** (per Codex R1 Minor #1): the auto-cleanup REQUIRES a successful Schwab daily fetch. If Schwab is degraded for an extended period and the ladder falls back to yfinance for several runs, the contaminated `CVGI.schwab_api.parquet` remains on disk in its minute-frequency shape until Schwab recovers. **`_bars_hook`'s return-to-cache path is UNAFFECTED** in this scenario — the hook returns the yfinance-fallback DataFrame directly to the OhlcvCache, so the chart-step renders correctly off the fallback bars without consulting Shape A. The contamination only matters for the FUTURE `resolve_ohlcv_window` reader (which honors `_SOURCE_PRECEDENCE_MARKET_DATA = {schwab_api: 0, yfinance: 1}` — Schwab wins on conflict). Until the contaminated rows are overwritten, any Shape A consumer that consults `resolve_ohlcv_window` for the 10 contaminated dates would see Schwab's stale minute-frequency last-of-day bars rather than yfinance's daily bars.

Operators may proactively clean up by deleting `~/swing-data/prices-cache/CVGI.schwab_api.parquet` (and any other `*.schwab_api.parquet` file with similar contamination); next pipeline run reconstitutes from scratch via either the Schwab daily-kwargs path or the yfinance-fallback persistence path. The legacy `*.parquet` files are unaffected (always daily-bar from yfinance).

No discriminating cleanup is required for the fix to close the OPERATOR-WITNESSED S3 chart-render regression — `_bars_hook` returns fresh daily data to the cache regardless of the on-disk Shape A state. Post-S3-PASS housekeeping may choose to surface a V2-F (per §4.D) cleanup helper if operators report Shape A contamination from sustained Schwab outages.

### §4.D Banked V2 candidates (NOT in V1 gate-fix scope)

- **V2-D: Defensive kwarg validation at `get_price_history`** — raise on `(start_dt=None, end_dt=None, period_type=None, period=None)` combination since this triggers Schwab's minute-default footgun. Skipped in V1 to keep the gate-fix surgical; would require touching the wrapper + retesting all callers.
- **V2-E: Mapper-side duplicate-`asof_date` rejection** — `map_price_history_to_window` could raise `SchwabSchemaParityError` when it observes >1 candle for the same `asof_date` (signaling "caller forgot daily kwarg"). Defense-in-depth; skipped in V1 to keep blast radius small.
- **V2-F: Shape A archive backfill cleanup** — sweep the operator's `~/swing-data/prices-cache/*.schwab_api.parquet` files for any that contain duplicate `asof_date` rows + dedupe to keep the latest-mtime row per date. Not necessary for V1 fix (next run's `write_window` merge resolves naturally) but operator-friendly UX.

---

## §5 T-GF2 task plan (per brief §1.3 + §2.2)

- **T-GF2.1 — failing test** at `tests/integrations/test_schwab_window_ladder_daily_kwargs.py`. Inspect `_bars_hook` execution: assert that the schwabdev `client.price_history` call receives `periodType="year"`, `period=5`, `frequencyType="daily"`, `frequency=1` (not all `None`). Test FAILS pre-fix (current `_bars_hook` passes no period/frequency kwargs).

- **T-GF2.2 — minimal fix**:
  - Extend `fetch_window_via_ladder` to accept `period_type` / `period` / `frequency_type` / `frequency` kwargs; forward to `get_price_history`.
  - Update `_bars_hook` in `swing/pipeline/runner.py` to pass `period_type="year", period=5, frequency_type="daily", frequency=1`.
  - Verify T-GF2.1 test passes.

- **T-GF3 — production-path regression test** at `tests/pipeline/test_ohlcv_cache_production_path_no_intraday.py`. Planted scenario: `OhlcvCache` with ladder hook installed; the ladder hook returns a `SchwabPriceHistoryWindow` with INTRADAY-shaped bars (multiple bars per `asof_date`, simulating the minute-default footgun); assert that:
  - (a) Under the FIXED `_bars_hook`, the ladder is invoked with daily kwargs (verified via spy on `fetch_window_via_ladder`'s incoming kwargs).
  - (b) The cache contract returns ~1 row per date (or the test asserts no duplicate index entries) for a known-good daily-bars response.

  Test PASSES post-fix; FAILS pre-fix (verified by reverting `_bars_hook` temporarily OR by Codex review verifying discriminating power).

---

## §6 Inherited LOCKS preserved + ACCEPTs not regressed

- **R1 M#1 OHLCV scope-clarification ACCEPT** (CLAUDE.md gotcha scoped to dashboard): UNCHANGED. The fix touches `_bars_hook` only; chart-target composition (A+ + open-trade + watchlist top-N) is unchanged at `swing/pipeline/runner.py:_step_charts`.

- **R1 M#2 V2-A breaker non-participation ACCEPT**: UNCHANGED. The fix does NOT add breaker participation to the bars path; the `_bars_lock`-protected `_bars_store` continues as-is.

- **CLAUDE.md "Hook fallback window-completeness" gotcha** (NEW per T1.SB0 housekeeping `dc0cfea`): RESPECTED. The hook returns the FULL Schwab/yfinance archive; consumer (cache) slices to `window_days=200`. The fix preserves this contract.

- **CLAUDE.md "Session-anchor inequality discipline" gotcha** (NEW per T1.SB0 housekeeping `dc0cfea`): RESPECTED. `_fetch_bars_window` uses strict-greater `>` for the backward-looking `last_completed_session(now())` anchor; the fix does NOT touch this predicate.

- **Schema v19 UNCHANGED**: gate-fix is consumer-side / wiring-side only.

- **Defensive copy on store + read preserved** (Codex R3 m#1 fix from T1.SB0): UNCHANGED.

- **Per-cache locking preserved**: UNCHANGED.

- **`_step_charts` interface UNCHANGED**: continues calling `ohlcv_cache.get_or_fetch(ticker, window_days=200)`.

---

## §7 Adversarial-review pre-emptions

| Watch item (brief §5 anchor) | Pre-emption |
|---|---|
| 1. T-GF1 recon doc rigor — root cause cited with file:line evidence | §2 cites 6 file:line anchors with line-range pins |
| 2. Hypothesis verification against operator's REAL CVGI archive | §1 + §2.A-E empirically inspects operator's `~/swing-data/prices-cache/CVGI*.parquet` |
| 3. Fix preserves T1.SB0's 2 banked ACCEPT-WITH-RATIONALE designs | §6 enumerates both ACCEPTs as unchanged |
| 4. CLAUDE.md "Hook fallback window-completeness" gotcha honored | §6 confirms: hook returns full archive; consumer slices |
| 5. CLAUDE.md "Session-anchor inequality discipline" gotcha honored | §6 confirms: backward-looking `>` strict preserved |
| 6. All existing T1.SB0 tests still PASS post-fix | §4.A confirms fix touches only `_bars_hook` + `fetch_window_via_ladder` signature (additive kwargs; backward-compatible) |
| 7. NEW T-GF3 regression test exercises production data-derivation path | §5 T-GF3 — planted intraday Schwab response; asserts daily-kwargs requested |
| 8. NEW T-GF3 regression test FAILS pre-fix | §5 T-GF3 explicit discriminating-test design with spy on `fetch_window_via_ladder` kwargs |
| 9. Schema v19 UNCHANGED | §6 confirms |
| 10. `_step_charts` interface unchanged | §6 confirms |
| 11. Per-cache locking preserved | §6 confirms |
| 12. Defensive copy on store + read preserved | §6 confirms |
| 13. Phase 11 Sub-bundle C R1 M#5 V1 deferral comment items ALL addressed | §3 reframes the deferral item — "weekly-refresh + archive_history_days semantics" is NOT the actual defect; the actual defect (Schwab `price_history` minute-default) is closed by §4.A |
| 14. Implementer self-report accuracy gate | return report will cite file:line + commit SHAs + test counts per brief §7 |
| 15. NO new CLAUDE.md gotcha additions in gate-fix housekeeping | gate-fix introduces no CLAUDE.md edits per operator decision 2026-05-18 PM; new "Schwab minute-default footgun" gotcha is a CAPTURE-NEED for post-S3-PASS orchestrator housekeeping |

**Banked CLAUDE.md gotcha CAPTURE-NEED for post-gate-fix housekeeping (orchestrator-decision per brief §5 watch item #15):**

> **Schwab `client.price_history(symbol)` with no `periodType` / `frequencyType` kwargs defaults to 10 days of 1-MINUTE intraday bars (NOT daily bars).** Any caller consuming the result as daily bars (chart rendering, archive persistence, SMA computation) MUST explicitly pass `period_type="year", period=5, frequency_type="daily", frequency=1` (or equivalent month/daily combo). The mapper at `swing/integrations/schwab/mappers.py:map_price_history_to_window` bucketizes per-minute candles into `OhlcvBar.asof_date` via `.date().isoformat()` — so minute-frequency responses produce ~278 bars per date (regular-hours session) with duplicate `asof_date` values. The Shape A `write_window` merge picks "last per date" via `drop_duplicates(keep='last')` — silently overwriting any prior daily-bar Shape A content with the last-minute-of-day intraday bar. Pre-empt in any new `get_price_history` callsite: writing-plans §5 watch item must enumerate the 4 explicit kwargs OR cite the `fetch_window_via_ladder` daily-defaulting helper.

---

## §8 References

- **Brief**: [`docs/phase13-t1-sb0-gate-fix-dispatch-brief.md`](phase13-t1-sb0-gate-fix-dispatch-brief.md)
- **T1.SB0 recon**: [`docs/phase13-t1-sb0-recon.md`](phase13-t1-sb0-recon.md)
- **T1.SB0 return report**: [`docs/phase13-t1-sb0-return-report.md`](phase13-t1-sb0-return-report.md)
- **Phase 11 Sub-bundle C T-C.3 ladder**: [`swing/integrations/schwab/marketdata_ladder.py`](../swing/integrations/schwab/marketdata_ladder.py)
- **Schwab `price_history` API contract**: [`reference/schwabdev/api-calls.md:417-440`](../reference/schwabdev/api-calls.md#L417-L440)
- **CLI verify reference**: [`swing/cli_schwab.py:1094-1111`](../swing/cli_schwab.py#L1094-L1111)

---

*End of recon. T-GF1 commits this document; T-GF2 acts on §4.A fix shape D; T-GF3 acts on §5 production-path regression test. Brief's §1.2 hypothesis (gap-fill / weekly-refresh divergence) empirically falsified — root cause is Schwab `price_history` minute-default in `_bars_hook` callsite, NOT `read_or_fetch_archive` semantics. Capture-needs banked at §7 for post-S3-PASS CLAUDE.md addition.*
