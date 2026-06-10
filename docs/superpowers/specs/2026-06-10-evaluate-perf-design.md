# Design Spec — Phase 16 / Arc 6: Evaluate-Step Performance (batched gap pre-warm)

**Status:** LOCKED (Codex-converged — see `.copowers-findings.md`)
**Date:** 2026-06-10
**Cycle stage:** `copowers:brainstorming` → this spec → (separate commission) `copowers:writing-plans`
**Branch:** `arc6-evaluate-perf` (worktree from main HEAD `ac27a652`)
**Schema:** NONE — v26 holds. Latency-only; data content unchanged.
**Dispatch brief:** `docs/arc6-evaluate-perf-brainstorming-dispatch-brief.md`

---

## 1. Problem & mandate

The nightly `evaluate` pipeline step (`swing/pipeline/runner.py:_step_evaluate`, def @~1299) is
**~91% of the pipeline wall** on a cold nightly: run #98 (2026-06-09) measured **`evaluate` = 522s**
(detect 12s / observe 21s / charts 6s / schwab_orders 10s). Warm run #97 measured evaluate = 37s.

**Root cause (verified at HEAD `ac27a652`):** `_step_evaluate` makes **~580 strictly-serial
per-ticker yfinance round-trips**:

- `swing/pipeline/runner.py:1360` — `fetcher.get(SPY, lookback_days=365)` ×1.
- `swing/pipeline/runner.py:1371-1379` — candidate loop `fetcher.get(t, lookback_days=400)` (run #98:
  **63** tickers, finviz screen ∪ open-trade held tickers).
- `swing/pipeline/runner.py:1380-1389` — RS-universe loop `fetcher.get(t, lookback_days=120)` (**516**
  tickers via `load_universe`; skips any already scored in the candidate loop).

Every call routes `PriceFetcher.get` (`swing/prices.py:46`) → `read_or_fetch_archive`
(`swing/data/ohlcv_archive.py:204`). On a new-session night **every** archive is exactly one bar stale,
so the **incremental gap branch** (`ohlcv_archive.py:273`) fires per ticker: one
`_yf_download_window(ticker, start=latest+1, end=today)` = one `yf.download(..., threads=False)` HTTP
round-trip. **522s ÷ 580 ≈ 0.9s/call — serial round-trip latency, not data volume.**

A secondary, orthogonal cost is the **weekly full-refresh storm**: `needs_full_refresh`
(`ohlcv_archive.py:247-252`) fires per ticker when `(today − last_full_refresh).days >= 7`, triggering a
full `archive_history_days`-deep (~1857 calendar-day) re-download. Un-staggered, large batches of the
516-ticker universe can land their 7-day clocks on the same night.

**Mandate:** make the ~580 round-trips fast — without weakening any archive-integrity defense (F6
transient-empty, full-archive-return, `_write_archive_atomic`, #24 freshness) or tripping yfinance rate
limits — and prove the win on a live nightly via the Arc-1 `pipeline_step_timings` instrument.

**Acceptance target:** cold-nightly `evaluate` **≤ 90s** (stretch **≤ 60s**) vs the 522s baseline,
verified via `pipeline_step_timings` on the operator-gate run.

---

## 2. Empirical grounding (probe, 2026-06-10, this machine)

The brief's core premise — that a multi-ticker `yf.download([...], threads=False)` is a *genuine batch*
rather than a serial-internal loop — was **not assumed; it was probed** (the implementer's initial
hypothesis was that `threads=False` would serialize internally and yield zero speedup). yfinance **1.2.2**,
Python 3.14:

| variant (4 tickers, period=5d)            | wall  | effective/ticker |
|-------------------------------------------|-------|------------------|
| serial 4× single-ticker `threads=False`   | 7.63s | ~1.9s            |
| batch `[4]` `threads=False`               | 1.93s | ~0.48s (**~4×**) |
| batch `[4]` `threads=True`                | 0.93s | ~0.23s           |

**Findings that bind this design:**

1. **Multi-ticker `yf.download(list, threads=False)` IS a real batch** (≈4× faster than the serial loop
   even with `threads=False`). The brief's premise holds → **`threads=False` stays the law** for the warm
   path; the speedup needs no rate-limit-poking concurrency. `threads=True` (~2× further) is a documented
   *stretch lever* used only if the §6 benchmark cannot reach ≤90s on `threads=False` alone.
2. **Response shape:** default `group_by` is column-major `MultiIndex` (level0 = OHLCV field, level1 =
   ticker). `group_by="ticker"` yields level0 = ticker, so `frame[ticker]` is a clean per-ticker OHLCV
   subframe (`Open/High/Low/Close/Adj Close/Volume`). The warm uses `group_by="ticker"`.
3. **Missing/invalid ticker is NOT dropped from the response — it is present-but-all-NaN.** A probe mixing
   a bad symbol (`ZZZZINVALIDXYZ`) into the list returned that symbol in `columns.level0` with an all-NaN
   subframe (yfinance logs a "possibly delisted" line but does not raise). **This is the F6 surface:** the
   per-ticker guard MUST be `subframe.dropna(how="all").empty`, NOT column-absence. (See §4.3.)

Probe numbers are illustrative latency evidence, not the acceptance benchmark; the §6 benchmark measures
the real ~580-ticker universe in-cycle.

---

## 3. Architecture

A new helper in `swing/data/ohlcv_archive.py`:

```python
def warm_archives_batch(
    tickers: list[str],
    *,
    cache_dir: Path,
    archive_history_days: int,
    end_date: date,
    chunk_size: int = 75,            # default; §8 benchmark may tune within 50–100
    inter_chunk_pause_s: float = 0.0,  # default; benchmark-tuned (likely 0 on threads=False)
) -> WarmReport:
    ...
```

`_step_evaluate` calls it **once**, before its three fetch loops, over the full set
`[cfg.rs.benchmark_ticker] + candidate_tickers + universe.tickers` (deduped, uppercased). The warm
pre-populates each ticker's legacy `{TICKER}.parquet` archive up to `end_date`'s session, so the existing
serial loops then all hit the **cache-hit branch** of `read_or_fetch_archive` (zero yfinance calls).

**Key isolation property:** `read_or_fetch_archive` and `PriceFetcher.get` are **NOT modified** in their
read/return contract. Every other consumer (charts, daily-management, detect/observe, web `OhlcvCache`)
is unaffected; they simply benefit when evaluate has pre-warmed the shared archive dir. The ONLY change
inside `read_or_fetch_archive` is the staggered full-refresh predicate (§5), which is behavior-preserving
for the steady state and must match the warm classifier so the serial fallback agrees.

`warm_archives_batch` reuses, verbatim, the existing write machinery — `_write_archive_atomic`,
`_write_meta_atomic`, the concat/dedup/`tail` merge shape, `_squeeze_multiindex`, and the OHLCV column
selection from `_yf_download_window`. It introduces **no** new write mechanism.

---

## 4. Two cohorts + the chunked-batch machine

### 4.1 Cohort classification (local I/O only — no fetches)

For each ticker, read its archive + meta from disk (the same `_read_archive` / `_read_meta` the serial
path uses) and bucket it using the **exact** `read_or_fetch_archive` predicates so the warm and the
fallback never disagree:

- **cache-hit** — archive present, not full-refresh-due (§5), and `latest_stored == today_session`:
  **skip** (no fetch, no write).
- **gap cohort** — archive present, not full-refresh-due, `latest_stored < today_session`.
- **full-refresh cohort** — archive missing/empty, OR meta missing/unparseable, OR full-refresh-due
  under the staggered predicate (§5).

`today_session = _last_completed_session_today()` (the same anchor the serial path uses). `end_date`
controls only the return slice for downstream callers; the archive is always written up to
`today_session` — identical to `read_or_fetch_archive`.

### 4.2 Per-cohort uniform windows

A multi-ticker `yf.download` takes ONE `start`/`end`. Each cohort fetches one uniform window; per-ticker
slicing/merging then yields the same per-ticker archive the serial path would have produced:

- **gap cohort window** = `[min(latest_stored over the cohort) + 1 day, today_session]`. Tickers with a
  smaller gap simply receive extra leading rows that the merge dedups away — same final archive.
- **full-refresh cohort window** = `[today_session − _calendar_window_for_trading_days(archive_history_days),
  today_session]` (identical to the serial full-refresh start computation). Each ticker `.tail(archive_history_days)`.

The full-refresh cohort is batched too (not left serial): post-stagger it is still ~1/7 × 516 ≈ 70
tickers; 70 serial full-downloads would alone threaten the 90s budget.

### 4.3 The chunked-batch machine (run once per cohort)

For a cohort with uniform window `[start, end]`:

1. **Chunk** tickers into groups of `chunk_size` (benchmark-pinned, 50–100).
2. Per chunk, one call:
   ```python
   yf.download(chunk, start=start, end=end + 1 day, group_by="ticker",
               threads=False, progress=False, auto_adjust=False, actions=False)
   ```
   — mirrors `_yf_download_window`'s kwargs exactly (incl. `threads=False` and the inclusive-`end`
   `+1 day` convention), plus `group_by="ticker"`.
3. **Per-ticker extract + F6 gate** (single-threaded loop over the chunk):
   - `sub = frame[ticker]` (handle the single-ticker-remnant case where yfinance may return a
     non-MultiIndex frame — fall back to treating the whole frame as that ticker's subframe).
   - `sub = sub.dropna(how="all")`. **If empty → transient-missing:** leave that ticker's archive AND
     meta **untouched**, append the ticker to the `fallback` list. *Never write.* (F6 — the missing
     ticker is present-but-NaN, not absent.)
   - Else keep `[Open, High, Low, Close, Volume]` (drop `Adj Close`, byte-matching the serial
     `_yf_download_window`), `_squeeze_multiindex`, tz-strip the index — identical normalization to the
     serial path.
4. **Merge + write** through the existing mechanisms verbatim:
   - **gap cohort:** `combined = pd.concat([archive, sub])`, dedup `keep="last"`, `sort_index`,
     `.tail(archive_history_days)`, `_write_archive_atomic`. **No meta write** (matches the serial gap
     branch, `ohlcv_archive.py:277-281`).
   - **full-refresh cohort:** `sub.tail(archive_history_days)`, `_write_archive_atomic`, then
     `_write_meta_atomic({"last_full_refresh_date": today_session.isoformat()})`.
   - `_write_archive_atomic` remains the **sole** archive write path (the completed-day strip at
     `ohlcv_archive.py:131` is inherited). The merge/write loop is single-threaded → no concurrent
     same-ticker writes, no `_write_archive_atomic` re-entrancy concern.
5. Optional `inter_chunk_pause_s` between chunks (rate-limit courtesy; benchmark-tuned, likely 0.0 on
   `threads=False`).

---

## 5. Weekly-storm stagger (hash-bucket)

Replace the bare `(today − last_full_refresh).days >= 7` trigger with a deterministic, **stateless**
spread, applied **in both** the warm classifier (§4.1) AND `read_or_fetch_archive` (so the serial
fallback path agrees):

```python
import zlib
bucket          = zlib.crc32(ticker.encode()) % 7     # stable across processes; NOT Python hash()
day_idx         = today_session.toordinal() % 7
days_since_full = (today_session - last_full_refresh).days   # +inf if no meta
due             = days_since_full >= 7
fire_full_refresh = (due and bucket == day_idx) or (days_since_full >= 13)
```

- New/empty/meta-missing archives are full-refresh regardless (the `archive is None / empty /
  last_full_refresh is None` arms of the current predicate are preserved — they are NOT subject to the
  bucket gate).
- Steady state: each ticker full-refreshes ~weekly on its own bucket day → ~1/7 of the universe per
  night. **Worst-case staleness is bounded at ≤13 days** by the hard ceiling.
- `crc32` (not Python `hash()`) for cross-process determinism (PYTHONHASHSEED randomizes `hash(str)`).

**Methodology-impact note (flagged for research-director):** this is a *latency-motivated* cadence
change, not a deliberate methodology change. It only affects how promptly **deep-history corrections**
(yfinance split/dividend re-statements of old bars, the #26 0.5–3% temporal mutation) propagate — bounded
to ≤13 days. **Recent bars stay daily-fresh** via the gap path, so RS 12-week-return inputs (which read
recent closes) are essentially unaffected. Called out here so the research-director is aware; not an
operator gate.

---

## 6. Failure posture (OQ-5) & #27 audit

The warm is a **pure accelerator** — correctness never depends on it:

- **Per-ticker miss** (F6/all-NaN, or a merge raises for one ticker): that ticker falls through to the
  serial `read_or_fetch_archive` in the existing `_step_evaluate` loops (which re-guards F6
  independently). Correct result, just not pre-warmed.
- **Whole-chunk failure** (rate-limit / network exception on the `yf.download` call): caught, logged, the
  **entire chunk** routed to the serial fallback set. One bad chunk never sinks the rest.
- **Wholesale warm failure**: `_step_evaluate` proceeds exactly as today — the serial loops re-fetch.
  No correctness risk.
- **#27 audit:** `_step_evaluate` records a `warnings_json` entry from the returned `WarmReport`
  whenever the warm degraded — fields: cohort sizes (cache-hit / gap / full-refresh), chunks attempted,
  per-ticker fallback count, chunk-failure count, wall time. A clean warm with zero fallbacks emits no
  warning (honest funnel); any degradation is **surfaced, not masked** — so "warm silently did nothing"
  cannot read as success (the #27 silent-skip discipline).

`WarmReport` is a lightweight dataclass returned by `warm_archives_batch` (counts + the fallback ticker
list); it carries no DB rows and no schema.

---

## 7. Phase-isolation carve-out (EXPLICIT)

`swing/data/` is read-only by default; this arc scopes the carve-out explicitly (per the 3c/3d/5/6/7
precedent):

- **`swing/data/ohlcv_archive.py`** — add `warm_archives_batch` + `WarmReport` + the staggered
  full-refresh predicate helper (shared by the warm classifier and `read_or_fetch_archive`). No change to
  `read_or_fetch_archive`'s read/return contract beyond swapping the inline `>= 7` test for the shared
  staggered predicate.
- **`swing/pipeline/runner.py`** — the `warm_archives_batch` call in `_step_evaluate` (before the loops)
  + the `WarmReport` → `warnings_json` plumbing.
- **`swing/prices.py`** — touched ONLY if the warm call needs a thin `PriceFetcher` entry point;
  preference is to call `warm_archives_batch` directly from the runner with `cfg.paths.prices_cache_dir`
  + `cfg.archive.archive_history_days`, leaving `prices.py` untouched.

**NO** repo / model / schema changes. **NO** `swing/trades/` changes. **NO** Shape-A sidecar changes
(`write_window` / `resolve_ohlcv_window` / `_backward_compat_rename` are Arc-3/XMAX territory —
untouched). Schema **v26** frozen. Zero `Co-Authored-By`.

---

## 8. Testing & benchmark

**Data-content parity (in scope, the headline guard):** run `_step_evaluate` (or a focused harness) with
the warm **ON** vs **OFF** over a fixed mocked-yf fixture set → assert **identical** `returns_12w`,
`Candidate` rows, and bucket assignments. Identical by construction (same bars → same archives → same
evaluation); the test locks it against regression.

**Unit tests (illustrative — the plan enumerates):**

- cohort classification matches `read_or_fetch_archive` branch-for-branch (cache-hit / gap / full-refresh)
  including the staggered predicate.
- gap-cohort window = widest gap; a ticker with a smaller gap ends with the correct per-ticker archive
  (merge dedups the extra rows).
- **F6: an all-NaN subframe for ticker T leaves T's `.parquet` + `.meta.json` byte-unchanged AND lists T
  in `WarmReport.fallback`** (derive the fixture from the real probe shape — present-but-NaN, not absent).
- whole-chunk `yf.download` raise → every ticker in the chunk lands in the fallback set, archives
  untouched.
- stagger bucket math: `crc32 % 7` bucket gate + the `>= 13` hard ceiling; new/empty/meta-missing bypass
  the gate; run-migrate-twice-style no-op safety (predicate is deterministic per day).
- gap cohort writes **no** meta; full-refresh cohort writes meta; `Adj Close` dropped; tz-stripped index.
- `_write_archive_atomic` completed-day strip still fires (no row dated after `today_session` persists).

**Benchmark (executing-phase, NOT this cycle):** a bounded live or recorded-harness probe over the real
~580-ticker universe measuring cold-nightly `evaluate` wall, sweeping `chunk_size`, `threads=False` first.
**Acceptance: ≤ 90s (stretch ≤ 60s)** verified via `pipeline_step_timings` on the operator-gate nightly
vs the 522s baseline. If `threads=False` cannot reach ≤90s, the benchmark evaluates the `threads=True`
stretch lever (chunk-bounded) before any decision to relax the lock — that relaxation, if needed, is a
flagged operator decision, not an implementer default.

---

## 9. Out of scope / flagged

- **Universe scope / staleness reduction** — that is a methodology change to RS-rank inputs, NOT a perf
  fix. OUT. (If a future finding shows it's the only real lever, STOP and flag for the
  operator/research-director — not in this arc.)
- **Shape-A / XMAX archive work** — Arc 3.
- **A `marketdata_calls` audit table (1c)** — if call-level metrics are wanted, log-only; no schema here.
- **Schwab-bars ladder extension** — bars stay yfinance; quotes-only ladder unchanged.
- **detect / observe / charts optimization** — 12–21s each, immaterial next to evaluate.
- The §5 full-refresh cadence change is **flagged** for research-director awareness (latency-motivated,
  ≤13-day deep-history-correction staleness, recent bars unaffected).

---

## 10. Open items handed to writing-plans

- Pin `chunk_size` and `inter_chunk_pause_s` defaults as the benchmark's first-task output (spec carries
  the 50–100 range; the plan's benchmark task locks the number).
- Decide the exact home of the shared staggered-predicate helper (private function in `ohlcv_archive.py`
  consumed by both `warm_archives_batch` and `read_or_fetch_archive`).
- Confirm whether `_step_evaluate` passes `end_date=last_completed_session(run_now)` or `None`-resolves
  inside the warm (must match the serial path's `as_of_date=None` → `last_completed_session` anchor).
- The benchmark harness shape (bounded live probe vs recorded) is a writing-plans task decision.
