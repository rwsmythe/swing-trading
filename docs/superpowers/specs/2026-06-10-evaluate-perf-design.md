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

**INVARIANT — single session anchor (Codex R1 Minor #4, promoted to a design invariant).** The warm and
the serial fallback MUST resolve the **exact same** completed-session anchor for a given run. If they
disagree across a market-close / holiday / timezone boundary (e.g. warm computes `today_session` a moment
after the serial loop crosses into a new session), one path writes/strips to a different day than the
other and parity silently breaks. The warm therefore derives `today_session` from the SAME
`_last_completed_session_today()` / `last_completed_session(run_now)` source the serial path uses, and the
chosen anchor is the binding contract — not a writing-plans placement detail. (See §10 for the precise
call-site wiring decision, but the equality requirement itself is locked here.)

### 4.2 Per-cohort uniform windows

A multi-ticker `yf.download` takes ONE `start`/`end`. Each cohort fetches one uniform window; per-ticker
slicing/merging then yields the same per-ticker archive the serial path would have produced.

**Gap-cohort banding (Codex R1 Major #1 — widest-window amplification; corrected R2 Major #1).** A naive
single gap window `[min(latest_stored) + 1, today_session]` lets ONE archive that is weeks/months stale
expand the window for the entire cohort, forcing every otherwise-1-bar-stale ticker to download months of
redundant history (latency + rate-limit + memory regression). The fix is **banding by `latest_stored`,
NOT reclassification**:

- **Band the gap cohort by `latest_stored`.** Group gap tickers by their `latest_stored` date; each
  distinct band runs as its own uniform-window batch (`[band_latest + 1, today_session]`). On a normal
  new-session night the overwhelming majority share `latest_stored == today_session − 1` → a single
  dominant band (one batch set); a handful of multi-day stragglers form tiny side-bands. Redundant
  transfer is bounded to within a band, never universe-wide.
- **Bound band proliferation:** tickers staler than `GAP_DEEP_BAND_TRADING_DAYS` (default **30 trading
  days**; a tunable constant, NOT schema) are collapsed into ONE "deep-gap" band fetched with that
  group's single widest window. This caps the number of bands when staleness is scattered; the residual
  amplification is bounded to that small deep-gap group, never the whole cohort.
- **CRITICAL — no semantic change, parity-preserving (R2 Major #1).** Banding changes only *how the gap
  fetch is batched*, NEVER the per-ticker outcome. Every gap ticker — including a very-stale one in the
  deep-gap band — remains an **incremental gap**: its archive is `concat([archive, slice])`-merged, it
  gets **NO** `last_full_refresh_date` meta write, and no deep-history re-download beyond what the natural
  gap concat requires. This is byte-identical to what the serial `read_or_fetch_archive` incremental-gap
  branch would produce for that ticker, so warm-on/warm-off parity holds. (The earlier R1 draft proposed
  *promoting* very-stale gaps to full-refresh — that would overwrite deep history and reset the cadence
  clock, breaking parity AND the latency-only mandate; it is rejected.)

- **full-refresh cohort window** = `[today_session − _calendar_window_for_trading_days(archive_history_days),
  today_session]` (identical to the serial full-refresh start computation). Each ticker `.tail(archive_history_days)`.

The full-refresh cohort is batched too (not left serial): post-stagger it is ~1/7 × 516 ≈ 70 tickers;
70+ serial full-downloads would alone threaten the 90s budget. (First-night rollout may exceed
steady-state — see §5 rollout note.)

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
3. **Per-ticker extract + validation gate** (single-threaded loop over the chunk). Each gate failure ⇒
   **no write + append to `fallback`** (the serial path re-fetches that ticker). A malformed subframe
   NEVER poisons the chunk and NEVER writes partial/bad data (Codex R1 Major #2). The whole extract is
   wrapped per-ticker in try/except so any unforeseen shape error degrades to fallback, not a crash:
   - **(a) subframe present** — `frame[ticker]`. The chunk request list and the response label set can
     differ (case/suffix normalization, omission): resolve the column case-insensitively against the
     requested symbol; absent ⇒ fallback. **Single-ticker-remnant:** when the chunk has one ticker
     yfinance may return a flat (non-MultiIndex) frame — detect via `isinstance(frame.columns,
     MultiIndex)` and treat the flat frame as that ticker's subframe. (Chunking SHOULD also avoid a
     trailing size-1 chunk by folding a lone remnant into the previous chunk; §8 locks the size-1 path
     with a test regardless.)
   - **(b) required OHLCV columns present** — `{Open,High,Low,Close,Volume}` all exist after case
     normalization; missing any ⇒ fallback.
   - **(c) non-empty after `dropna(how="all")`** — all-NaN ⇒ transient-missing ⇒ fallback. (F6 — the
     missing ticker is present-but-NaN, not absent. This is the probe-confirmed shape, §2 finding 3.)
   - **(d) index parseable** to a `DatetimeIndex`; unparseable ⇒ fallback.
   - On pass: keep `[Open, High, Low, Close, Volume]` (drop `Adj Close`, byte-matching the serial
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

def _full_refresh_due(ticker, last_full_refresh, today_session, *, stagger_enabled):
    """PURE predicate — the single source of full-refresh-due truth, called by BOTH
    read_or_fetch_archive AND warm_archives_batch with the SAME stagger_enabled value."""
    days_since_full = (today_session - last_full_refresh).days   # caller passes +inf if no meta
    if not stagger_enabled:
        return days_since_full >= 7                  # exact legacy behavior
    bucket  = zlib.crc32(ticker.encode()) % 7        # stable across processes; NOT Python hash()
    day_idx = today_session.toordinal() % 7
    return (days_since_full >= 7 and bucket == day_idx) or (days_since_full >= 13)
```

- New/empty/meta-missing archives are full-refresh regardless (the `archive is None / empty /
  last_full_refresh is None` arms of the current predicate are preserved — they are NOT subject to the
  bucket gate).
- Steady state: each ticker full-refreshes ~weekly on its own bucket day → ~1/7 of the universe per
  night. **Worst-case staleness is bounded at ≤13 days** by the hard ceiling.
- `crc32` (not Python `hash()`) for cross-process determinism (PYTHONHASHSEED randomizes `hash(str)`).

**Config kill-switch + single source-of-truth (Codex R1 Major #4, R2 Major #2).** The stagger is gated on
a new config key `[archive] stagger_full_refresh` (default `True`) in `swing.config.toml` — a CONFIG
addition, **not** a DB schema change (v26 holds). Setting it `False` restores the exact legacy `>= 7`
cadence with no code change.

The kill-switch's value is resolved by **exactly ONE module-level function** in `ohlcv_archive.py` —
`_full_refresh_stagger_enabled()` — which reads the project config once (cached at module level) and
returns `True` if the config is unreadable. **Both** `read_or_fetch_archive` and `warm_archives_batch`
obtain the `stagger_enabled` value from this single resolver and pass it into the pure `_full_refresh_due`
predicate above. This is the *defined, sanctioned* config-resolution mechanism (NOT a hidden per-call
global read, NOT a default-only path): `read_or_fetch_archive`'s public **signature is unchanged** (the
resolution is internal), and because the stagger is an **archive-level refresh policy** — a property of
the shared `{T}.parquet` files, not of any one caller — EVERY caller (evaluate AND non-evaluate: charts,
daily-management, web) sees the identical policy. There is no call site at which the warm and the serial
fallback can resolve different values, so they cannot diverge. (Non-evaluate callers therefore also adopt
the staggered cadence; this is correct — it is the archive's policy, and the §5 cadence tradeoff +
kill-switch govern it uniformly.)

**Cache/restart expectation (Codex R3 Minor #2).** Because the resolver caches at module level, flipping
`stagger_full_refresh` takes effect for the **nightly pipeline on its next run** (a fresh process — the
common case) but a **long-lived process** (the `swing web` server, which calls `read_or_fetch_archive`)
holds the cached value until restart. This is acceptable for a single-operator tool — the kill-switch is
a deliberate, infrequent lever — but writing-plans must document "restart `swing web` to pick up a
`stagger_full_refresh` change" (or provide a trivial cache-clear), so the no-deploy lever's latency is
not surprising.

**Cadence change is an EXPLICIT, ACCEPTED tradeoff (Codex R1 Major #4).** Staggering moves the
full-refresh cadence from "≥ every 7 days" to "≤ 13 days." This is accepted, not incidental: it affects
ONLY how promptly **deep-history corrections** (yfinance split/dividend re-statements of old bars, the
#26 0.5–3% temporal mutation) propagate. **Recent bars stay daily-fresh** via the gap path, so RS
12-week-return inputs (which read recent closes) are essentially unaffected. Flagged for research-director
awareness; reversible via the kill-switch above.

**Rollout transition (Codex R1 Major #3).** On the FIRST staggered night the existing
`last_full_refresh_date` distribution is arbitrary — many tickers may already be `>= 7` due, and the
`>= 13` ceiling can bunch a concentrated catch-up wave into the full-refresh cohort (larger than the
~70 steady-state). This is **latency-bounded** (the full-refresh cohort is batched + chunked + serial-
fallback, not 70+ serial round-trips) but is a real rate-limit/volume consideration. Mitigation: the
classifier exposes a **dry-run cohort-size report** (counts only — cache-hit / gap / per-band gap /
full-refresh — with **zero** fetches) that the operator runs **before** the gate night to see the
expected first-night load. If that load is alarmingly large, the real levers are (a) flip
`stagger_full_refresh=False` for the rollout night to keep legacy cadence, or (b) accept the one-time
heavier-but-batched night (it is bounded, not 70+ serial). The spec does NOT claim a staged
"pre-warm over several nights" mechanism — none is built (R2 Minor #2); the kill-switch is the
sanctioned lever. See §8.

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
  *warning* (honest funnel); any degradation is **surfaced, not masked** — so "warm silently did nothing"
  cannot read as success (the #27 silent-skip discipline).
- **Always-on cohort telemetry (Codex R1 Minor #1).** Independent of the warning path, EVERY warm run
  logs its cohort counts (cache-hit / gap / per-band gap / full-refresh / fallback) at INFO via the
  Phase-16 `pipeline.log` seam — so a classifier bug that misbuckets everything as cache-hit (zero
  fallbacks, *looks* clean) is still visible as an anomalous cohort distribution, not silently green.

`WarmReport` is a lightweight dataclass returned by `warm_archives_batch` (counts + the fallback ticker
list); it carries no DB rows and no schema.

---

## 7. Phase-isolation carve-out (EXPLICIT)

`swing/data/` is read-only by default; this arc scopes the carve-out explicitly (per the 3c/3d/5/6/7
precedent):

- **`swing/data/ohlcv_archive.py`** — add `warm_archives_batch` + `WarmReport` + the pure
  `_full_refresh_due` predicate + the single `_full_refresh_stagger_enabled()` config resolver (both
  shared by the warm classifier and `read_or_fetch_archive`). `read_or_fetch_archive`'s public
  read/return SIGNATURE is unchanged; the only internal change is swapping the inline `>= 7` test for the
  shared predicate (which now consults the resolver).
- **`swing/pipeline/runner.py`** — the `warm_archives_batch` call in `_step_evaluate` (before the loops)
  + the `WarmReport` → `warnings_json` plumbing.
- **`swing/prices.py`** — touched ONLY if the warm call needs a thin `PriceFetcher` entry point;
  preference is to call `warm_archives_batch` directly from the runner with `cfg.paths.prices_cache_dir`
  + `cfg.archive.archive_history_days`, leaving `prices.py` untouched.

- **`swing.config.toml` + the config model** — add `[archive] stagger_full_refresh = true` (the §5
  kill-switch) and the `GAP_DEEP_BAND_TRADING_DAYS` / `chunk_size` tunables (config or module constants —
  writing-plans decides). This is a CONFIG surface, **not** DB schema.

**NO** repo / model / **DB**-schema changes. **NO** `swing/trades/` changes. **NO** Shape-A sidecar
changes (`write_window` / `resolve_ohlcv_window` / `_backward_compat_rename` are Arc-3/XMAX territory —
untouched). DB schema **v26** frozen (the config-key addition is not a migration). Zero `Co-Authored-By`.

---

## 8. Testing & benchmark

**Data-content parity (in scope, the headline guard):** run `_step_evaluate` (or a focused harness) with
the warm **ON** vs **OFF** over a fixed mocked-yf fixture set → assert **identical** `returns_12w`,
`Candidate` rows, and bucket assignments. Identical by construction (same bars → same archives → same
evaluation); the test locks it against regression.

**Unit tests (illustrative — the plan enumerates):**

- cohort classification matches `read_or_fetch_archive` branch-for-branch (cache-hit / gap / full-refresh)
  including the staggered predicate.
- gap banding: each gap band uses its own widest window; a ticker with a smaller gap (batched in a wider
  band, or in the deep-gap band) still ends with the correct per-ticker archive (merge dedups the extra
  rows) and gets NO meta write — byte-parity with the serial incremental-gap branch.
- **F6: an all-NaN subframe for ticker T leaves T's `.parquet` + `.meta.json` byte-unchanged AND lists T
  in `WarmReport.fallback`** (derive the fixture from the real probe shape — present-but-NaN, not absent).
- whole-chunk `yf.download` raise → every ticker in the chunk lands in the fallback set, archives
  untouched.
- stagger bucket math: `crc32 % 7` bucket gate + the `>= 13` hard ceiling; new/empty/meta-missing bypass
  the gate; `stagger_full_refresh=False` restores exact legacy `>= 7`; run-migrate-twice-style no-op
  safety (predicate is deterministic per day).
- gap cohort writes **no** meta; full-refresh cohort writes meta; `Adj Close` dropped; tz-stripped index.
- gap banding (NO reclassification): a ticker stale > `GAP_DEEP_BAND_TRADING_DAYS` is grouped into the
  deep-gap band but stays an INCREMENTAL gap (no meta write, no full-refresh); gap bands fetch per-band
  windows (a 1-bar-stale ticker batched in a wider band still lands the correct per-ticker archive,
  byte-identical to the serial gap path).
- **validation gates (Codex R1 Major #2):** subframe absent / missing OHLCV column / all-NaN /
  unparseable index each ⇒ archive+meta byte-unchanged AND ticker in `WarmReport.fallback`; a malformed
  ticker does NOT poison its chunk.
- **single-ticker-remnant (Codex R1 Minor #3):** a size-1 final chunk (flat non-MultiIndex frame) is
  extracted correctly — a dedicated test locks the shape.
- `_write_archive_atomic` completed-day strip still fires (no row dated after `today_session` persists).

**Dry-run classifier report (Codex R1 Major #3).** A counts-only, **zero-fetch** entry point that
classifies the full ticker set and reports cohort sizes (cache-hit / gap / per-band gap / deep-gap band /
full-refresh). The operator runs it before the gate night to preview first-night load; a unit test
asserts it performs no `yf.download`.

**Benchmark (executing-phase, NOT this cycle):** a bounded live or recorded-harness probe over the real
~580-ticker universe measuring cold-nightly `evaluate` wall, sweeping `chunk_size`, `threads=False` first.
**Chunk sizing is constrained by request RELIABILITY (yfinance URL/request-size limits, and response
memory — a full-refresh chunk is `chunk_size × ~1857` rows), not latency alone (Codex R1 Minor #2);** the
50–100 range is the starting envelope, the benchmark may narrow it for reliability. The benchmark
also inspects the **deep-gap band's count and window span separately** from ordinary gap bands (Codex R3
Minor #3) — a scattered-staleness deep-gap band can carry a wide window, and its cost should be measured
distinctly so a regression there is not hidden inside the dominant near-current band's timing.
**Acceptance: ≤ 90s (stretch ≤ 60s)** verified via `pipeline_step_timings` on the operator-gate nightly
vs the 522s baseline.
If `threads=False` cannot reach ≤90s, the benchmark evaluates the `threads=True` stretch lever
(chunk-bounded) before any decision to relax the lock — that relaxation, if needed, is a flagged operator
decision, not an implementer default.

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
  ≤13-day deep-history-correction staleness, recent bars unaffected) — an explicit accepted tradeoff,
  reversible via the `stagger_full_refresh` config kill-switch, with a pre-gate dry-run cohort report.

---

## 10. Open items handed to writing-plans

- Pin `chunk_size`, `inter_chunk_pause_s`, and `GAP_DEEP_BAND_TRADING_DAYS` (default 30) defaults as the
  benchmark's first-task output (spec carries the ranges; the plan's benchmark task locks the numbers,
  reliability-constrained per §8).
- The predicate/resolver OWNERSHIP is locked (§5/§7: `_full_refresh_due` + `_full_refresh_stagger_enabled`
  in `ohlcv_archive.py`); writing-plans decides only the implementation mechanics of the config read
  (which config loader, cache shape) — not where the functions live.
- The session-anchor EQUALITY is locked as an invariant (§4.1); the remaining decision is only the
  precise wiring — pass `end_date=last_completed_session(run_now)` from the runner vs `None`-resolve
  inside the warm — both must hit the identical anchor source for the run.
- Whether the dry-run classifier report (§8) ships as a CLI subcommand, a `--dry-run` flag on the warm,
  or a logged line on the first real run.
- The benchmark harness shape (bounded live probe vs recorded) is a writing-plans task decision.
