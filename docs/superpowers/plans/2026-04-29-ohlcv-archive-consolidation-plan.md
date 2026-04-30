# OHLCV Archive Consolidation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Consolidate the three production OHLCV fetch paths (`PriceFetcher`, `swing.pipeline.ohlcv.fetch_daily_bars`, `OhlcvCache` worker) onto a single per-ticker incremental on-disk archive at `~/swing-data/prices-cache/`, replacing the existing per-as-of-date keying. Cuts per-run yfinance call volume by ~99% for established tickers; provides cold-start hydration for the dashboard SMA cache after `swing web` restart; keeps weekly full-refresh semantics so retroactive split/dividend adjustments still propagate.

**Architecture:** A new shared helper `swing.data.ohlcv_archive.read_or_fetch_archive(ticker, *, end_date, cache_dir, archive_history_days)` is the single source for archive-aware reads; it (1) reads `{TICKER}.parquet` + `{TICKER}.meta.json` sidecar from `cache_dir`; (2) checks freshness against `end_date` and `(today - last_full_refresh_date) >= 7 days` weekly trigger; (3) fetches yfinance only for the gap (incremental) or full history (weekly refresh / new ticker); (4) writes archive + meta with per-file atomic-replace (temp file in destination dir → `os.replace`, per CLAUDE.md cross-device-link gotcha); (5) returns the archive DataFrame so each consumer slices what it needs. `PriceFetcher.get` and `fetch_daily_bars` become thin adapters around the helper. `OhlcvCache` inherits archive backing automatically (its worker already calls `fetch_daily_bars`). A standalone migration script `swing.tools.migrate_prices_cache` consolidates the existing 5,521 per-as-of-date files into ~200-300 per-ticker files; operator runs it once before pulling the consumer-refactor commits.

**Cross-file atomicity contract (Codex R1 Major 1 resolution):** `os.replace` is atomic per path, NOT across the parquet/meta pair. A crash between the two replaces leaves a benign skew window: parquet replaced + meta still pointing at prior `last_full_refresh_date`, OR parquet replaced + meta missing entirely. Readers handle both gracefully — missing/corrupted/stale meta triggers a full-refresh on the next call (recoverable; cost is one extra yfinance call). The migration script's resume path (Task 1 idempotency contract) likewise re-unions whatever it finds. This is documented as the V1 contract; readers MUST treat the parquet-meta pair as a coherence-best-effort pair, not a strict invariant. Task 1 + Task 3 each include a discriminating test for the parquet-fresh-meta-missing skew scenario.

**Trading-day vs calendar-day window semantics (Codex R1 Critical 1 + R2 Critical 1 resolution):** `archive_history_days` is the locked spec field name AND its semantics are TRADING days (per spec §2.5: "5 years (1260 trading days)"). yfinance's `start`/`end` kwargs are CALENDAR days. The helper converts trading-day retention to a calendar window using the actual market-calendar ratio: `_calendar_window_for_trading_days(n) = ceil(n * 365.25 / 252) + 30` calendar days. The 365.25/252 ratio reflects ~252 US market trading days per ~365.25 calendar days; the +30 day buffer absorbs multi-year holiday clustering (a naive `n * 7 / 5` heuristic with a 14-day buffer is too tight — 5y of US market history is ~1826 calendar days, not 1778). For default 1260 trading days the formula yields `ceil(1260 * 365.25 / 252) + 30 = 1857` calendar days (~5.08y), which dominates worst-case holiday loss across the full 5y span. Post-fetch, the helper truncates with `.tail(archive_history_days)` so over-fetch from the buffer doesn't bloat the archive. Tests assert the calendar `start` kwarg equals `end_date - timedelta(days=_calendar_window_for_trading_days(archive_history_days))`, NOT `end_date - timedelta(days=archive_history_days)` — this prevents the silent under-retention failure mode where 1260 calendar days = ~3.45 years instead of 5y.

**Tech Stack:** Python 3.14, pandas, pyarrow (parquet), yfinance ≥1.2 (with `threads=False`, MultiIndex squeeze, and `Ticker.history()` no-`threads=` gotchas honored), pytest.

---

## Pre-flight context

- **Test baseline pinned:** **1314 fast tests passed, 1 skipped, 8 deselected** (`python -m pytest -m "not slow" -q`) at HEAD `a4811f4`. Trust pytest output, not pinned counts (CLAUDE.md "Test-count drift in plan docs").
- **Branch:** `main` (project convention; no feature branches).
- **Commits:** conventional, NO Claude co-author footer, NO `--no-verify`, NO `--amend`, flat `Task <N>` numbering.
- **Per-task observable-verification step** (per binding conventions, ERE form): after each task implementation commit, run

  ```bash
  git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task <N>'
  ```

  and confirm ≥1 hit for the task you just committed. The `-E` flag is REQUIRED — git's default BRE treats `+` as literal and the regex silently returns empty without it. Cross-plan aliasing against prior plans' `Task <N>` commits is expected; the operator visually disambiguates by topic.
- **Locked decisions (per dispatch brief §2; do not re-litigate):**
  1. Corporate-action policy = weekly full-refresh on first archive-read of the calendar week per active (demand-driven) ticker.
  2. Cache-coherence policy = read archive → check `(latest_stored_bar_date, last_full_refresh_date)` → incremental gap fetch and/or weekly refresh as required.
  3. Schema = per-ticker parquet (`{TICKER}.parquet`); metadata via sidecar JSON (`{TICKER}.meta.json`). NO SQLite OHLCV table.
  4. Migration strategy = one-time consolidation script, manual operator invocation, backup-first / atomic-replace / delete-old-only-after-write-succeeds.
  5. Retained history depth = configurable, default 5 years (1260 trading days). Field name `archive_history_days` (locked literally per spec §2.5 — accessor is `cfg.archive.archive_history_days`, dataclass `ArchiveConfig`). Toml-shadowing audit required pre-commit.
  6. `OhlcvCache` backing = IN SCOPE for V1 (cold-start hydrates from archive via the wrapped `fetch_daily_bars`).
  7. Atomicity = `tempfile.NamedTemporaryFile(dir=archive_dir, delete=False, ...)` → `os.replace(tmp, final)`; never `shutil.move`.
- **Open-design resolutions (per dispatch brief §3):**
  - **§3.A Metadata encoding:** sidecar JSON `{TICKER}.meta.json` with `{"last_full_refresh_date": "YYYY-MM-DD"}`. Future fields (e.g., last-incremental-fetch timestamp) stay additive on the same JSON shape.
  - **§3.B Archive directory location:** `cfg.paths.prices_cache_dir` (consolidate in place; defaults to `~/swing-data/prices-cache/`). No path-config migration; existing toml field already names this directory. Code comments document that the directory is now an "archive" not a "cache" (TTL-flush semantics removed for stored data). V2 may rename if operator wants.
  - **§3.C Wrapper signature:** `read_or_fetch_archive(ticker: str, *, end_date: date, cache_dir: Path, archive_history_days: int) -> pd.DataFrame | None`. Returns the full retained archive (≤ `end_date`) for the ticker, or `None` for delisted/invalid (yfinance returns empty). Each consumer slices what it needs (`tail(n_bars)` for the pipeline path; calendar-day slice for `PriceFetcher`). The helper internally uses `yf.download(threads=False, progress=False, auto_adjust=False, actions=False)` for both full-history and incremental fetches; it squeezes MultiIndex columns defensively (yfinance ≥1.2 gotcha). `archive_history_days` is interpreted as trading-day retention; the helper converts to a calendar window (with holiday buffer) for the yfinance call (see Cross-file/trading-day notes in Architecture).
  - **§3.D Test surface:** discriminating tests cover (a) helper unit semantics (cache-empty / cache-fresh / cache-stale-incremental / weekly-refresh / atomic-replace / empty-result / MultiIndex squeeze / `threads=False` propagation); (b) `PriceFetcher` consumer adapter; (c) `fetch_daily_bars` consumer adapter (existing tests in `tests/pipeline/test_ohlcv.py` are repointed to monkeypatch the helper instead of `yf.Ticker`); (d) `OhlcvCache` cold-start hydration + warm-cache precedence; (e) migration script consolidation, idempotency, interruption recovery. Mocked yfinance for unit tests; live yfinance reserved for slow-marked V2 follow-up.
  - **§3.E Test count baseline:** 1314 fast tests at HEAD `a4811f4`.
- **Source-file shape (verified at HEAD `a4811f4`):**
  - `swing/prices.py:23-85` — `PriceFetcher` dataclass; `_cache_path` (per-as-of-date), `_fetch_from_yf` (uses `yf.download` already), `get`, `clear_cache`. Public API: `get(ticker, lookback_days, *, as_of_date=None) -> pd.DataFrame`.
  - `swing/pipeline/ohlcv.py:18-62` — `fetch_daily_bars(ticker, *, n_bars=60, as_of_date=None) -> pd.DataFrame | None`. Currently calls `yf.Ticker(ticker).history(period='6mo', interval='1d', auto_adjust=False)` directly, then strips in-progress bar against session.
  - `swing/web/ohlcv_cache.py:217-246` — `OhlcvCache._fetch_bundle_worker`; calls `ohlcv_mod.fetch_daily_bars(ticker, n_bars=60)`. Constructor takes `cfg: Config` (line 50) — already has access to `cfg.paths.prices_cache_dir` and (after Task 2) `cfg.archive.archive_history_days`.
  - `swing/cli.py:148, 315` and `swing/pipeline/runner.py:146` — `PriceFetcher(cache_dir=cfg.paths.prices_cache_dir)` instantiations. After Task 4 they must also pass `archive_history_days=cfg.archive.archive_history_days` (kwarg-with-default, so the call sites stay valid even if missed; the discriminating compat test catches this).
  - `swing/weather/runner.py:10-15` — `PriceFetcher` consumer. Public API stable; no change required.
  - `swing.config.toml:12` — `prices_cache_dir = "swing-data/prices-cache"`. At HEAD `a4811f4` (pre-Task-2), `archive_history_days` does not appear in any tracked file (verified by `git ls-files | xargs grep -ln 'archive_history_days' 2>/dev/null` → empty output). Post-plan, hits will appear in the touched source/test/plan files (this is correct); the audit's failure mode is a tracked CONFIG-shaped file (`*.toml`/`*.yaml`/`*.json`/`*.cfg`/`*.ini`) hitting the field name — see Step 7d for the post-plan expectation.
- **Locked-decision rationale carry-overs:**
  - Atomicity: temp file MUST be created in the same directory as the destination. On Windows with Drive-synced paths plus `$TMP` on a different volume, `os.replace(tmp, final)` raises `OSError: [Errno 18] Invalid cross-device link` (CLAUDE.md). `tempfile.NamedTemporaryFile(dir=cache_dir, delete=False, suffix=".parquet.tmp")` keeps both paths on the same filesystem.
  - yfinance gotchas (CLAUDE.md): the helper uses `yf.download(..., threads=False)` exclusively (NOT `yf.Ticker.history()`). The pipeline path's old `Ticker.history()` call site is REMOVED, so the prior `test_fetch_daily_bars_does_not_pass_threads_kwarg` test is repointed in Task 5 (the equivalent assertion moves to the helper-level test in Task 3). MultiIndex columns are squeezed via `if isinstance(df.columns, pd.MultiIndex): df.columns = df.columns.get_level_values(0)`.
  - Strip rule: `fetch_daily_bars`'s session-anchored partial-bar strip stays as a belt-and-suspenders guard (helper may also strip; redundancy is cheap; CLAUDE.md gotcha).

---

## File map

**Create:**

- `swing/data/ohlcv_archive.py` — Task 3 (the shared helper).
- `swing/tools/__init__.py` — Task 1 (empty package marker; only created if `swing/tools/` doesn't already exist).
- `swing/tools/migrate_prices_cache.py` — Task 1 (one-time consolidation script).
- `tests/data/test_ohlcv_archive.py` — Task 3 (helper unit tests).
- `tests/tools/__init__.py` — Task 1 (empty package marker if absent).
- `tests/tools/test_migrate_prices_cache.py` — Task 1 (script tests).

**Modify:**

- `swing/config.py` — Task 2 (add `ArchiveConfig` dataclass, wire `Config.archive` field, default-from-toml).
- `swing/prices.py` — Task 4 (`PriceFetcher` consumes helper; preserve public `get()` signature; extend `clear_cache` to also delete `*.meta.json` and `*.parquet.tmp` orphans; add `archive_history_days` constructor kwarg with default 1260).
- `swing/cli.py:148, 315` — Task 4 (pass `archive_history_days=cfg.archive.archive_history_days` to `PriceFetcher`).
- `swing/pipeline/runner.py:146` — Task 4 (same).
- `swing/pipeline/ohlcv.py` — Task 5 (`fetch_daily_bars` becomes thin adapter; new required kwargs `cache_dir: Path, archive_history_days: int`; preserve `n_bars` + `as_of_date` semantics; preserve strip rule).
- `swing/web/ohlcv_cache.py:217-246` — Task 6 (worker passes `cache_dir`/`archive_history_days` to `fetch_daily_bars`).
- `tests/pipeline/test_ohlcv.py` — Task 5 (existing five `test_fetch_daily_bars_*` tests repointed; the `Ticker.history()` no-`threads=` test is replaced by a helper-level equivalent in Task 3).
- `tests/web/test_ohlcv_cache.py` — Task 6 (add cold-start hydration test + warm-cache precedence test; existing `monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", …)` tests continue to work because they replace the function entirely).
- `tests/config/test_config.py` — Task 2 (assert `cfg.archive.archive_history_days == 1260` default + toml-override honor).
- `tests/prices/test_prices.py` (verified at HEAD `a4811f4` via `git ls-files tests/ | grep test_prices.py`) — Task 4 (replace per-as-of-date cache-key tests with archive-helper-mocked equivalents; preserve API-level behavior tests).

**Verification before writing each test:** Use `git ls-files tests/ | grep -i <topic>` (or `Glob "tests/**/test_*<topic>*.py"`) to confirm the canonical test-file path before creating a new test module. The repo's test layout mirrors `swing/`, so `tests/data/test_ohlcv_archive.py` (new file) lives alongside the new `swing/data/ohlcv_archive.py`.

**Operator action between Task 1 and Task 4:** After Task 1 lands and BEFORE pulling Task 4-6 commits, the operator runs `python -m swing.tools.migrate_prices_cache` once on their machine. This consolidates the legacy 5,521 per-as-of-date files into ~200-300 per-ticker files. Without this step, Task 4-6 still work (the helper falls back to a full-history fetch for any ticker whose archive is empty), but the operator pays the yfinance cost of re-fetching ~200-300 tickers' worth of full history. The script is idempotent and safe to re-run.

---

## Task ordering rationale

Per dispatch brief §6 acceptance criterion 7, Task 1 (migration script) lands FIRST so the operator can run it independently before the consumer-refactor commits land. Tasks 2 → 3 → 4 → 5 → 6 form the consumer-refactor chain: Task 2 ships the config field that Task 3's helper consumes; Task 3 ships the helper that Tasks 4–6 wrap; Tasks 4 and 5 refactor the two distinct consumer adapters; Task 6 adds the discriminating multi-path coverage tests for `OhlcvCache` (whose backing comes for free via Task 5 but requires explicit cold-start / warm-cache assertions per multi-path-ingestion lesson). Task 7 is the final verification gate (full fast suite + ruff + observable verification of all six commits).

Sequential single-subagent execution; no parallel-collision risk (per dispatch brief §6 acceptance criterion 4).

---

## Task 1: Migration script (`swing/tools/migrate_prices_cache.py`)

**Goal:** One-time consolidation script. Reads all per-as-of-date parquet files in `cfg.paths.prices_cache_dir` matching pattern `*_*d_asof-*.parquet`, groups by ticker, unions rows by date (keeping the row from the newest as_of_date when duplicates exist on the same date — newer as_of_date = newer yfinance fetch = newer corporate-action-adjusted snapshot), writes `{TICKER}.parquet` + `{TICKER}.meta.json` atomically, deletes legacy files only after atomic-replace succeeds. Operator runs manually via `python -m swing.tools.migrate_prices_cache` BEFORE pulling Task 4-6 commits.

**Files:**
- Create: `swing/tools/__init__.py` (empty if doesn't exist; verify with `git ls-files swing/tools/ | head` first).
- Create: `swing/tools/migrate_prices_cache.py` (the script + module-level entry point).
- Create: `tests/tools/__init__.py` (empty if doesn't exist).
- Create: `tests/tools/test_migrate_prices_cache.py`.

**Discriminating-test sanity check:** Each test setup uses a fixture `tmp_path` cache directory pre-populated with synthetic per-as-of-date parquet files of KNOWN content (varying date ranges, varying as_of_date values, with deliberate row-overlap on specific dates). Assertions verify the consolidated `{TICKER}.parquet` contains the union of unique dates AND the higher-as_of_date row wins for overlapping dates AND legacy files are deleted AND `*.meta.json` files exist with `last_full_refresh_date` equal to the max as_of_date observed across legacy files for that ticker. A vacuous test like "consolidated file exists" would pass under a no-op implementation; the discriminating tests fail unless consolidation actually unions rows correctly.

**Idempotency contract** (test-asserted in Step 1d below): re-running the script after any prior run (whether previously interrupted or completed) MUST converge to the same consolidated state without corrupting existing per-ticker archives. Specifically:
- If `{TICKER}.parquet` exists AND no legacy `*_*d_asof-*.parquet` files for that ticker → SKIP that ticker (no work; no rewrite).
- If `{TICKER}.parquet` exists AND legacy files for that ticker still exist (interrupted previous run) → re-union legacy + existing per-ticker, rewrite atomically, delete legacy. Convergence.
- If `{TICKER}.parquet` doesn't exist AND legacy files exist → standard consolidation path.

- [ ] **Step 1: Verify package directories don't already exist as something else**

```bash
git ls-files swing/tools/ tests/tools/ 2>/dev/null
```

Expected: empty output (or just `__init__.py` if previously created). If non-empty, surface in return report and STOP — there's a name collision worth investigating before proceeding.

- [ ] **Step 1a: Create empty package markers**

If `swing/tools/__init__.py` doesn't exist, create it as an empty file. Likewise for `tests/tools/__init__.py`.

```python
# swing/tools/__init__.py
"""Operator-runnable maintenance scripts (manual invocation only)."""
```

```python
# tests/tools/__init__.py
```

- [ ] **Step 1b: Write the failing tests (consolidation correctness + duplicate-date resolution)**

Create `tests/tools/test_migrate_prices_cache.py`:

```python
"""Tests for swing.tools.migrate_prices_cache.

Covers consolidation correctness, duplicate-date resolution (newer as_of wins),
atomic-replace behavior, idempotency, and interrupted-run recovery.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd
import pytest


def _write_legacy_parquet(
    cache_dir: Path,
    ticker: str,
    lookback_days: int,
    as_of: date,
    rows: list[tuple[date, float, float, float, float, int]],
) -> Path:
    """Helper: write a legacy per-as-of-date parquet file with synthetic OHLCV rows."""
    df = pd.DataFrame(
        rows,
        columns=["date", "Open", "High", "Low", "Close", "Volume"],
    ).set_index("date")
    df.index = pd.to_datetime(df.index)
    path = cache_dir / f"{ticker}_{lookback_days}d_asof-{as_of.isoformat()}.parquet"
    df.to_parquet(path)
    return path


def test_consolidation_unions_unique_dates_and_picks_newer_asof_on_overlap(tmp_path):
    """Two legacy files for same ticker with overlapping dates → union of unique dates;
    rows on the overlap date come from the file with the newer as_of_date."""
    from swing.tools import migrate_prices_cache as mig

    cache = tmp_path
    # File A: as_of=2026-04-20, dates 2026-04-15..2026-04-20, Close=100.0 on overlap day
    _write_legacy_parquet(
        cache, "AAPL", 120, date(2026, 4, 20),
        [(date(2026, 4, d), 100.0, 100.0, 100.0, 100.0, 1000) for d in range(15, 21)],
    )
    # File B: as_of=2026-04-25, dates 2026-04-18..2026-04-25, Close=200.0 on overlap day
    # (newer as_of so its rows should win on 2026-04-18..2026-04-20 overlap)
    _write_legacy_parquet(
        cache, "AAPL", 120, date(2026, 4, 25),
        [(date(2026, 4, d), 200.0, 200.0, 200.0, 200.0, 2000) for d in range(18, 26)],
    )

    mig.run(cache_dir=cache)

    consolidated = pd.read_parquet(cache / "AAPL.parquet")
    # Union of unique dates: 2026-04-15..2026-04-25 (11 days).
    assert len(consolidated) == 11
    # Overlap days (2026-04-18..2026-04-20) MUST come from File B (Close=200.0).
    overlap_close = consolidated.loc[pd.Timestamp("2026-04-19"), "Close"]
    assert overlap_close == 200.0, (
        f"overlap row should have come from newer as_of file (Close=200.0), "
        f"got {overlap_close} — duplicate-date resolution is broken"
    )
    # Non-overlap day from File A only (2026-04-15) survives at Close=100.0.
    assert consolidated.loc[pd.Timestamp("2026-04-15"), "Close"] == 100.0


def test_consolidation_writes_meta_with_max_asof_observed(tmp_path):
    """Meta sidecar JSON records last_full_refresh_date = max as_of among legacy files."""
    from swing.tools import migrate_prices_cache as mig

    cache = tmp_path
    _write_legacy_parquet(
        cache, "MSFT", 120, date(2026, 4, 20),
        [(date(2026, 4, 15), 1.0, 1.0, 1.0, 1.0, 1)],
    )
    _write_legacy_parquet(
        cache, "MSFT", 120, date(2026, 4, 28),
        [(date(2026, 4, 28), 2.0, 2.0, 2.0, 2.0, 2)],
    )

    mig.run(cache_dir=cache)

    meta = json.loads((cache / "MSFT.meta.json").read_text())
    assert meta["last_full_refresh_date"] == "2026-04-28"


def test_consolidation_deletes_legacy_files_after_atomic_replace(tmp_path):
    """Legacy *_NNNd_asof-*.parquet files are removed only after the
    consolidated {TICKER}.parquet is on disk (atomic-replace succeeded)."""
    from swing.tools import migrate_prices_cache as mig

    cache = tmp_path
    legacy_a = _write_legacy_parquet(
        cache, "GOOG", 120, date(2026, 4, 20),
        [(date(2026, 4, 15), 1.0, 1.0, 1.0, 1.0, 1)],
    )
    legacy_b = _write_legacy_parquet(
        cache, "GOOG", 120, date(2026, 4, 25),
        [(date(2026, 4, 18), 2.0, 2.0, 2.0, 2.0, 2)],
    )

    mig.run(cache_dir=cache)

    assert (cache / "GOOG.parquet").exists()
    assert not legacy_a.exists()
    assert not legacy_b.exists()
    # No leftover *.parquet.tmp files (atomic-replace cleanup).
    assert list(cache.glob("*.tmp")) == []


def test_atomic_replace_preserves_prior_archive_on_simulated_crash(tmp_path, monkeypatch):
    """If os.replace raises mid-migration for a given ticker, the prior {TICKER}.parquet
    (if any) is unchanged AND legacy files are NOT deleted (rolled back for that ticker)."""
    from swing.tools import migrate_prices_cache as mig

    cache = tmp_path
    # Pre-existing per-ticker archive with KNOWN content.
    pre_existing = pd.DataFrame(
        [(pd.Timestamp("2026-04-01"), 99.0, 99.0, 99.0, 99.0, 999)],
        columns=["date", "Open", "High", "Low", "Close", "Volume"],
    ).set_index("date")
    pre_existing.to_parquet(cache / "TSLA.parquet")
    legacy_path = _write_legacy_parquet(
        cache, "TSLA", 120, date(2026, 4, 25),
        [(date(2026, 4, 15), 1.0, 1.0, 1.0, 1.0, 1)],
    )

    # Force os.replace to raise for this ticker's archive write.
    real_replace = mig.os.replace

    def crashing_replace(src, dst):
        if str(dst).endswith("TSLA.parquet"):
            raise OSError("simulated crash mid-rename")
        return real_replace(src, dst)

    monkeypatch.setattr(mig.os, "replace", crashing_replace)

    with pytest.raises(OSError, match="simulated crash"):
        mig.run(cache_dir=cache)

    # Prior archive is unchanged.
    survived = pd.read_parquet(cache / "TSLA.parquet")
    assert survived.loc[pd.Timestamp("2026-04-01"), "Close"] == 99.0, (
        "prior archive was clobbered despite the rename crashing"
    )
    # Legacy file NOT deleted (rollback discipline).
    assert legacy_path.exists(), (
        "legacy file deleted before atomic-replace succeeded — partial-write violation"
    )


def test_idempotency_clean_state_is_a_noop(tmp_path):
    """Re-running on a clean state (per-ticker archives present, no legacy files)
    is a no-op: archives unchanged, no errors."""
    from swing.tools import migrate_prices_cache as mig

    cache = tmp_path
    df = pd.DataFrame(
        [(pd.Timestamp("2026-04-15"), 1.0, 1.0, 1.0, 1.0, 1)],
        columns=["date", "Open", "High", "Low", "Close", "Volume"],
    ).set_index("date")
    df.to_parquet(cache / "AMZN.parquet")
    (cache / "AMZN.meta.json").write_text(json.dumps({"last_full_refresh_date": "2026-04-15"}))

    mtime_before_parquet = (cache / "AMZN.parquet").stat().st_mtime
    mtime_before_meta = (cache / "AMZN.meta.json").stat().st_mtime

    mig.run(cache_dir=cache)

    # File mtimes unchanged — script DID NOT rewrite (no-op convergence).
    assert (cache / "AMZN.parquet").stat().st_mtime == mtime_before_parquet
    assert (cache / "AMZN.meta.json").stat().st_mtime == mtime_before_meta


def test_idempotency_resumes_from_interrupted_run(tmp_path):
    """If a prior run was interrupted (per-ticker archive exists AND legacy files
    still exist for that ticker), re-running converges: legacy + existing
    re-unioned, rewritten, legacy deleted."""
    from swing.tools import migrate_prices_cache as mig

    cache = tmp_path
    # Simulated mid-interruption state: per-ticker archive exists with PARTIAL data,
    # AND legacy files still exist with additional data.
    partial = pd.DataFrame(
        [(pd.Timestamp("2026-04-15"), 100.0, 100.0, 100.0, 100.0, 1000)],
        columns=["date", "Open", "High", "Low", "Close", "Volume"],
    ).set_index("date")
    partial.to_parquet(cache / "NVDA.parquet")
    (cache / "NVDA.meta.json").write_text(json.dumps({"last_full_refresh_date": "2026-04-15"}))
    legacy = _write_legacy_parquet(
        cache, "NVDA", 120, date(2026, 4, 20),
        [(date(2026, 4, 18), 200.0, 200.0, 200.0, 200.0, 2000)],
    )

    mig.run(cache_dir=cache)

    consolidated = pd.read_parquet(cache / "NVDA.parquet")
    # Both rows present after convergence.
    assert pd.Timestamp("2026-04-15") in consolidated.index
    assert pd.Timestamp("2026-04-18") in consolidated.index
    # Legacy file gone.
    assert not legacy.exists()
    # Meta updated to max as_of observed (legacy's 2026-04-20 wins over the
    # pre-existing meta's 2026-04-15).
    meta = json.loads((cache / "NVDA.meta.json").read_text())
    assert meta["last_full_refresh_date"] == "2026-04-20"


def test_unrelated_files_are_not_touched(tmp_path):
    """Files that don't match the legacy pattern (`*_*d_asof-*.parquet`) are
    left untouched. Prevents accidental clobber of operator notes or other
    artifacts that happen to live in the cache dir."""
    from swing.tools import migrate_prices_cache as mig

    cache = tmp_path
    (cache / "README.txt").write_text("operator notes")
    (cache / "research-notes.parquet").write_text("not a legacy file")  # bogus content; just a name match avoidance test

    mig.run(cache_dir=cache)

    assert (cache / "README.txt").exists()
    assert (cache / "research-notes.parquet").exists()


def test_meta_write_failure_rolls_back_archive_and_legacy(tmp_path, monkeypatch):
    """Codex R1 Major 1 resolution — cross-file atomicity skew bound.

    Scenario: `_consolidate_ticker` succeeds in atomically replacing
    `{TICKER}.parquet` but the meta `os.replace` then raises (filesystem
    glitch / disk-full / permissions). The script's exception handler must
    NOT delete the legacy files (rollback discipline preserves the
    re-run-converges contract). On re-run, the partial state must converge
    cleanly.
    """
    from swing.tools import migrate_prices_cache as mig

    cache = tmp_path
    legacy_path = _write_legacy_parquet(
        cache, "META", 120, date(2026, 4, 25),
        [(date(2026, 4, 18), 1.0, 1.0, 1.0, 1.0, 1)],
    )

    real_replace = mig.os.replace

    def crash_on_meta(src, dst):
        if str(dst).endswith("META.meta.json"):
            raise OSError("simulated meta-write crash")
        return real_replace(src, dst)

    monkeypatch.setattr(mig.os, "replace", crash_on_meta)

    with pytest.raises(OSError, match="simulated meta-write crash"):
        mig.run(cache_dir=cache)

    # Legacy file MUST survive — meta-write failure rolls back.
    assert legacy_path.exists(), (
        "legacy file deleted before meta-write succeeded — partial-write violation"
    )
    # No leftover *.tmp files for either parquet or meta.
    assert list(cache.glob("*.parquet.tmp")) == []
    assert list(cache.glob("*.meta.json.tmp")) == []
```

- [ ] **Step 1c: Run the tests to confirm failure**

```bash
python -m pytest tests/tools/test_migrate_prices_cache.py -v 2>&1 | tail -20
```

Expected: all tests fail with `ModuleNotFoundError: No module named 'swing.tools.migrate_prices_cache'` or similar import error.

- [ ] **Step 1d: Implement `swing/tools/migrate_prices_cache.py`**

```python
"""One-time consolidation of `~/swing-data/prices-cache/` from per-as-of-date
parquet keying to per-ticker parquet keying.

Operator runs once via `python -m swing.tools.migrate_prices_cache` BEFORE
pulling the consumer-refactor commits (Task 4-6 of the OHLCV archive
consolidation plan). After this script completes, `cfg.paths.prices_cache_dir`
holds `{TICKER}.parquet` + `{TICKER}.meta.json` per ticker; legacy
`*_*d_asof-*.parquet` files have been deleted.

Idempotent: safe to re-run after interruption or on an already-migrated
cache. Atomic per-ticker: each ticker's consolidated archive is written to
a temp file in the same directory, then `os.replace`-d into place; legacy
files are deleted only after atomic-replace succeeds. If the rename crashes
mid-ticker, that ticker rolls back (legacy files survive; prior archive
unchanged) and a re-run will converge.
"""
from __future__ import annotations

import argparse
import json
import logging
import os
import re
import sys
import tempfile
from collections import defaultdict
from datetime import date
from pathlib import Path

import pandas as pd

log = logging.getLogger(__name__)

# Legacy filename pattern: {TICKER}_{LOOKBACK_DAYS}d_asof-{YYYY-MM-DD}.parquet
# Tickers may contain letters, digits, dots, and dashes (e.g., BRK.B, BF-A).
_LEGACY_RE = re.compile(
    r"^(?P<ticker>[A-Za-z0-9.\-]+)_(?P<lookback>\d+)d_asof-(?P<asof>\d{4}-\d{2}-\d{2})\.parquet$"
)


def _scan_legacy_files(cache_dir: Path) -> dict[str, list[tuple[Path, date]]]:
    """Group legacy files by ticker. Each value: list of (path, as_of_date) tuples."""
    by_ticker: dict[str, list[tuple[Path, date]]] = defaultdict(list)
    for entry in cache_dir.iterdir():
        if not entry.is_file():
            continue
        m = _LEGACY_RE.match(entry.name)
        if m is None:
            continue
        ticker = m.group("ticker").upper()
        as_of = date.fromisoformat(m.group("asof"))
        by_ticker[ticker].append((entry, as_of))
    return by_ticker


def _consolidate_ticker(
    ticker: str,
    legacy_files: list[tuple[Path, date]],
    cache_dir: Path,
) -> None:
    """Consolidate one ticker's legacy files (and any pre-existing per-ticker
    archive) into a single `{TICKER}.parquet` + `{TICKER}.meta.json`.

    Atomicity: writes go to temp files in `cache_dir`; both renames complete
    before any legacy file is deleted. If a rename raises, no legacy files
    are deleted and the prior archive (if any) is unchanged.
    """
    archive_path = cache_dir / f"{ticker}.parquet"
    meta_path = cache_dir / f"{ticker}.meta.json"

    # Sort legacy files by as_of ascending so newer rows OVERWRITE older
    # via DataFrame.combine_first / index dedup with keep='last'.
    legacy_files = sorted(legacy_files, key=lambda t: t[1])
    max_asof = legacy_files[-1][1] if legacy_files else None

    # Read all legacy frames + any pre-existing per-ticker archive.
    frames: list[pd.DataFrame] = []
    for path, _as_of in legacy_files:
        df = pd.read_parquet(path)
        frames.append(df)
    if archive_path.exists():
        frames.append(pd.read_parquet(archive_path))

    if not frames:
        return  # Nothing to do for this ticker.

    # Concatenate, drop duplicates on the date index keeping the LAST occurrence
    # (last = newest as_of in our sort order; pre-existing archive comes after,
    # which means a later-run incremental-fetched archive wins over an older
    # legacy file — correct since the archive is post-migration data).
    combined = pd.concat(frames)
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()

    # Atomic write: temp file in destination dir → os.replace.
    tmp_fd, tmp_name = tempfile.mkstemp(
        dir=str(cache_dir), prefix=f"{ticker}.", suffix=".parquet.tmp"
    )
    os.close(tmp_fd)
    tmp_path = Path(tmp_name)
    try:
        combined.to_parquet(tmp_path)
        os.replace(tmp_path, archive_path)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise

    # Meta: last_full_refresh_date = max as_of observed (preserves the most
    # recent yfinance fetch date as the corporate-action-adjustment baseline).
    if max_asof is not None:
        # If pre-existing meta has a NEWER last_full_refresh_date, keep it.
        existing_meta_date: date | None = None
        if meta_path.exists():
            try:
                existing_meta = json.loads(meta_path.read_text())
                existing_meta_date = date.fromisoformat(existing_meta["last_full_refresh_date"])
            except (json.JSONDecodeError, KeyError, ValueError):
                existing_meta_date = None
        effective_meta_date = max(max_asof, existing_meta_date) if existing_meta_date else max_asof
        meta_tmp_fd, meta_tmp_name = tempfile.mkstemp(
            dir=str(cache_dir), prefix=f"{ticker}.", suffix=".meta.json.tmp"
        )
        os.close(meta_tmp_fd)
        meta_tmp_path = Path(meta_tmp_name)
        try:
            meta_tmp_path.write_text(
                json.dumps({"last_full_refresh_date": effective_meta_date.isoformat()})
            )
            os.replace(meta_tmp_path, meta_path)
        except Exception:
            if meta_tmp_path.exists():
                try:
                    meta_tmp_path.unlink()
                except OSError:
                    pass
            raise

    # Both renames succeeded — safe to delete legacy files now.
    for path, _as_of in legacy_files:
        try:
            path.unlink()
        except OSError as exc:
            log.warning("failed to unlink legacy file %s: %s", path, exc)


def run(*, cache_dir: Path) -> None:
    """Consolidate every ticker found in `cache_dir`. Idempotent."""
    cache_dir = Path(cache_dir)
    if not cache_dir.exists():
        log.info("cache dir %s does not exist; nothing to migrate", cache_dir)
        return
    legacy_by_ticker = _scan_legacy_files(cache_dir)
    if not legacy_by_ticker:
        log.info("no legacy files found in %s; migration is a no-op", cache_dir)
        return
    log.info(
        "consolidating %d ticker(s) from %d legacy file(s) in %s",
        len(legacy_by_ticker),
        sum(len(v) for v in legacy_by_ticker.values()),
        cache_dir,
    )
    for ticker, files in legacy_by_ticker.items():
        _consolidate_ticker(ticker, files, cache_dir)
    log.info("migration complete")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Consolidate per-as-of-date prices-cache files into per-ticker archives."
    )
    parser.add_argument(
        "--cache-dir",
        type=Path,
        default=None,
        help="Override cache directory (defaults to swing.config.toml's prices_cache_dir).",
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("swing.config.toml"),
        help="Path to swing.config.toml (used when --cache-dir is omitted).",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

    if args.cache_dir is not None:
        cache_dir = args.cache_dir
    else:
        from swing.config import load
        cfg = load(args.config)
        cache_dir = cfg.paths.prices_cache_dir

    run(cache_dir=cache_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 1e: Run the tests to confirm pass**

```bash
python -m pytest tests/tools/test_migrate_prices_cache.py -v 2>&1 | tail -20
```

Expected: all tests pass.

- [ ] **Step 1f: Run the full fast suite to confirm no regression**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -3
```

Expected: 1314 + 7 = 1321 passed (or 1320 / 1322 depending on collection precision — trust pytest output, not pinned counts).

- [ ] **Step 1g: Commit**

```bash
git add swing/tools/__init__.py swing/tools/migrate_prices_cache.py \
        tests/tools/__init__.py tests/tools/test_migrate_prices_cache.py
git commit -m "feat(tools): Task 1 — OHLCV archive migration script"
```

- [ ] **Step 1h: Observable verification**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 1'
```

Expected: ≥1 hit including the just-created Task 1 commit. Cross-plan aliasing (other plans' Task 1 commits) is expected; visually disambiguate by the commit subject.

---

## Task 2: Config field — `archive_history_days`

**Goal:** Add `ArchiveConfig` dataclass with `archive_history_days: int = 1260` (5y trading days; semantics are trading-day retention — see Architecture for the calendar-day conversion the helper applies). Wire `Config.archive` field; defaultable from `raw.get("archive", {})` so the toml file does NOT need a new section. Toml-shadowing audit pre-commit (per locked decision §2.5 + `aeb2084` lesson + Codex R1 Major 3 resolution).

**Files:**
- Modify: `swing/config.py` (add dataclass + field + load wiring).
- Modify: `tests/config/test_config.py` (verified at HEAD `a4811f4` via `git ls-files tests/ | grep test_config.py`; canonical config-defaults home).

**Discriminating-test sanity check:** A test asserting `cfg.archive.archive_history_days == 1260` would fail under the pre-fix tree (no `archive` attribute → `AttributeError`) AND would fail under a buggy implementation that hard-codes a different default. The 1260 value is load-bearing: `swing.data.ohlcv_archive` (Task 3) consumes it for the `_fetch_full_history` window. If the default were silently 252 (1y) or 504 (2y), Task 3's full-refresh would silently truncate retained history.

- [ ] **Step 2a: Toml-shadowing audit (locked-form, repo-wide tracked files)**

```bash
git ls-files | xargs grep -ln "archive_history_days" 2>/dev/null
```

Expected: empty output. The `archive_history_days` field name is brand-new; ANY tracked-file hit pre-Task-2 indicates a stale shadow that would replicate the `aeb2084` 2026-04-28 failure mode (operator's production runtime overrode the Python default via a tracked toml/yaml/json). If non-empty, surface in return report and STOP — do NOT proceed without operator triage. Per Codex R1 Major 3: the audit applies to ALL tracked files (every committed config surface), not just `swing.config.toml`.

- [ ] **Step 2b: Locate the existing config test file**

```bash
git ls-files tests/ | grep test_config.py
```

Expected: `tests/config/test_config.py` (verified at plan-authoring time). Open it; locate the existing `_MINIMAL_VALID_TOML` (or equivalent fixture) for adapting in Step 2c.

- [ ] **Step 2c: Write the failing test**

Add to `tests/config/test_config.py`:

```python
def test_archive_config_defaults_to_5y_trading_days(tmp_path):
    """`Config.archive.archive_history_days` defaults to 1260 (5y trading days)
    when no [archive] section is present in swing.config.toml.

    Discriminating: under the pre-fix tree, `cfg.archive` raises
    AttributeError. Under a regressed default (e.g., silently 252 or 504),
    Task 3's helper would truncate the retained history window.
    """
    from swing.config import load

    # Construct a minimal toml without [archive] to exercise the default.
    toml_path = tmp_path / "swing.config.toml"
    toml_path.write_text(_MINIMAL_VALID_TOML)  # use whatever fixture pattern other config tests use

    cfg = load(toml_path)
    assert cfg.archive.archive_history_days == 1260


def test_archive_config_honors_toml_override(tmp_path):
    """If [archive] archive_history_days is set in the toml, it overrides the
    Python default — matches the dataclass-default-shadowing behavior of all
    other Config sections (lesson `aeb2084` 2026-04-28)."""
    from swing.config import load

    toml_path = tmp_path / "swing.config.toml"
    toml_path.write_text(
        _MINIMAL_VALID_TOML
        + "\n[archive]\narchive_history_days = 504\n"
    )

    cfg = load(toml_path)
    assert cfg.archive.archive_history_days == 504
```

If the existing config tests use a shared `_MINIMAL_VALID_TOML` fixture, reuse it; otherwise locate the closest-existing fixture for "valid toml content" and adapt.

- [ ] **Step 2d: Run the tests to confirm failure**

```bash
python -m pytest tests/config/test_config.py::test_archive_config_defaults_to_5y_trading_days tests/config/test_config.py::test_archive_config_honors_toml_override -v 2>&1 | tail -20
```

Expected: both tests fail with `AttributeError: 'Config' object has no attribute 'archive'`.

- [ ] **Step 2e: Add `ArchiveConfig` to `swing/config.py`**

Insert just BEFORE the `class Web:` declaration (alphabetical-by-section is not observed in this file; place near the most-related sections):

```python
@dataclass(frozen=True)
class ArchiveConfig:
    """Disk-archive retained-history depth for the OHLCV archive
    (`swing/data/ohlcv_archive.py`). 1260 = 5y trading days; bounds the
    full-history fetch window invoked by weekly refresh + new-ticker paths.

    Toml-shadowing audit (per locked decision §2.5 of the OHLCV archive
    consolidation plan): no override should appear in `swing.config.toml`
    unless the operator explicitly wants a different retention. The
    `aeb2084` 2026-04-28 lesson is in scope — Python defaults shadow at
    runtime if a tracked toml override exists.
    """
    archive_history_days: int = 1260
```

Then add to `Config`:

```python
@dataclass(frozen=True)
class Config:
    paths: Paths
    account: Account
    position_limits: PositionLimits
    risk: Risk
    vcp: VCP
    trend_template: TrendTemplate
    rs: RS
    etf_exclusion: ETFExclusion
    focus_ranking: FocusRanking
    near_trigger: NearTriggerConfig
    stop_advisory: StopAdvisoryConfig
    sizing: SizingConfig
    pipeline: PipelineConfig
    export: ExportConfig
    web: Web = field(default_factory=Web)
    classifier: ClassifierConfig = field(default_factory=ClassifierConfig)
    archive: ArchiveConfig = field(default_factory=ArchiveConfig)
```

And in `load()` near the end:

```python
        archive=ArchiveConfig(**raw.get("archive", {})),
```

- [ ] **Step 2f: Run the tests to confirm pass**

```bash
python -m pytest tests/config/test_config.py -v 2>&1 | tail -20
```

Expected: both new tests pass; no other config tests regress.

- [ ] **Step 2g: Run the full fast suite**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -3
```

Expected: prior count + 2 = 1323 passed (or close — trust pytest).

- [ ] **Step 2h: Commit**

```bash
git add swing/config.py tests/config/test_config.py
git commit -m "feat(config): Task 2 — archive_history_days config field"
```

- [ ] **Step 2i: Observable verification**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 2'
```

Expected: ≥1 hit including the just-created Task 2 commit.

---

## Task 3: Shared archive helper (`swing/data/ohlcv_archive.py`)

**Goal:** `read_or_fetch_archive(ticker, *, end_date, cache_dir, archive_history_days) -> pd.DataFrame | None`. Reads `{TICKER}.parquet` + `{TICKER}.meta.json` sidecar; checks freshness; fetches yfinance only for the gap (incremental) OR full history (weekly refresh / new ticker / corrupted meta); writes archive + meta atomically; returns the archive DataFrame (≤ end_date) or `None` for delisted/invalid tickers.

**Files:**
- Create: `swing/data/ohlcv_archive.py`.
- Create: `tests/data/test_ohlcv_archive.py`.

**Discriminating-test sanity check:** Each freshness-branch test must demonstrably exercise the freshness check, not just round-trip a cached value. For example, the cache-stale-incremental test seeds `last_full_refresh_date = today - 3 days` AND `latest_stored_bar_date = today - 3 days`; the assertion must verify yfinance was called with `start = (today - 2 days)` (gap-only, NOT a full-history window). A vacuous assertion like "result has bars" would pass even if the helper always fetches full history. Per dispatch brief §7 watch item #5.

The atomic-replace correctness test must construct a partial-write scenario AND verify recovery: pre-existing archive on disk; mid-write `os.replace` raises; post-state assertion: prior archive is byte-identical to its pre-write content; no leftover `*.parquet.tmp` files remain. A vacuous "happy path completes" test would miss the canonical orphaned-temp-file failure mode (per dispatch brief §7 watch item #2).

The `threads=False` propagation test must assert the call's actual kwargs (via mock recording), not assert that yfinance "is called" — the latter passes even if `threads=` defaults to True (the gotcha case). Equivalent to the existing `test_fetch_daily_bars_does_not_pass_threads_kwarg` precedent in `tests/pipeline/test_ohlcv.py:72`.

The MultiIndex-squeeze test must pass yfinance a fixture with `pd.MultiIndex` columns AND assert the helper returns a DataFrame with FLAT columns (per CLAUDE.md yfinance ≥1.2 gotcha; `df['Close']` must be a Series, not a DataFrame, after the squeeze).

- [ ] **Step 3a: Verify module path doesn't already exist**

```bash
git ls-files swing/data/ tests/data/ 2>/dev/null | head -10
```

Confirm `swing/data/ohlcv_archive.py` and `tests/data/test_ohlcv_archive.py` don't already exist.

- [ ] **Step 3b: Write the failing tests**

Create `tests/data/test_ohlcv_archive.py`:

```python
"""Tests for swing.data.ohlcv_archive.read_or_fetch_archive.

Covers cache-empty / cache-fresh / cache-stale-incremental / weekly-refresh
branches; atomic-replace correctness under simulated crash; empty-result
ticker handling; MultiIndex column squeeze; threads=False yfinance kwarg.

Time-stability: every test monkeypatches `_last_completed_session_today` to
a fixed date (FIXED_TODAY = 2026-04-29). The helper's weekly-refresh check
compares (today - last_full_refresh_date).days >= 7; without the
monkeypatch, tests pinning last_full_refresh_date relative to end_date
would silently flip into the weekly-refresh branch in future test runs as
real wallclock advances. The fixture below applies the monkeypatch
automatically to every test in this module.
"""
from __future__ import annotations

import json
from datetime import date, timedelta
from pathlib import Path

import pandas as pd
import pytest


FIXED_TODAY = date(2026, 4, 29)


@pytest.fixture(autouse=True)
def _pin_today(monkeypatch):
    """Pin `_last_completed_session_today` to FIXED_TODAY for every test in
    this module. Tests that need a different `today` can re-monkeypatch
    inside the test body — autouse fixtures apply BEFORE per-test setup
    runs, and the per-test monkeypatch.setattr overrides cleanly.
    """
    from swing.data import ohlcv_archive as mod
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED_TODAY)


def _mk_yf_frame(
    dates: list[date],
    close: float = 100.0,
    multiindex: bool = False,
) -> pd.DataFrame:
    """Build a synthetic yfinance-shape DataFrame keyed by date."""
    df = pd.DataFrame(
        {
            "Open": [close] * len(dates),
            "High": [close] * len(dates),
            "Low": [close] * len(dates),
            "Close": [close] * len(dates),
            "Volume": [1000] * len(dates),
        },
        index=pd.to_datetime(dates),
    )
    if multiindex:
        df.columns = pd.MultiIndex.from_product([df.columns, ["AAPL"]])
    return df


def test_new_ticker_triggers_full_history_fetch(tmp_path, monkeypatch):
    """Archive doesn't exist → full-history yfinance call → archive written +
    meta written → returns DataFrame with the fetched rows."""
    from swing.data import ohlcv_archive as mod

    recorded_kwargs: dict = {}

    def fake_download(ticker, **kwargs):
        recorded_kwargs.update(kwargs)
        return _mk_yf_frame([date(2026, 4, 25), date(2026, 4, 28)])

    monkeypatch.setattr(mod.yf, "download", fake_download)
    end_date = date(2026, 4, 28)

    result = mod.read_or_fetch_archive(
        "AAPL", end_date=end_date, cache_dir=tmp_path, archive_history_days=1260,
    )

    assert result is not None
    assert len(result) == 2
    assert (tmp_path / "AAPL.parquet").exists()
    assert (tmp_path / "AAPL.meta.json").exists()
    meta = json.loads((tmp_path / "AAPL.meta.json").read_text())
    # Meta records the actual refresh day (today), NOT the caller's end_date.
    assert meta["last_full_refresh_date"] == FIXED_TODAY.isoformat()
    # yfinance MUST be called with threads=False (CLAUDE.md gotcha).
    assert recorded_kwargs.get("threads") is False, (
        f"helper did not pass threads=False to yf.download; got {recorded_kwargs}"
    )
    # Codex R1 Critical 1: full-history start uses calendar-day conversion
    # (1260 trading days → ~1778 calendar days), NOT raw timedelta(days=1260).
    from swing.data.ohlcv_archive import _calendar_window_for_trading_days
    expected_full_start = end_date - timedelta(
        days=_calendar_window_for_trading_days(1260)
    )
    assert recorded_kwargs.get("start") == expected_full_start, (
        f"full-history start kwarg should be {expected_full_start} "
        f"(end_date - calendar window for 1260 trading days); "
        f"got {recorded_kwargs.get('start')} — calendar/trading-day "
        f"semantic regression"
    )


def test_cache_fresh_skips_yfinance(tmp_path, monkeypatch):
    """Archive has bars through end_date AND last_full_refresh < 7 days ago →
    NO yfinance call → returns the archive DataFrame ≤ end_date."""
    from swing.data import ohlcv_archive as mod

    end_date = date(2026, 4, 28)
    archive = _mk_yf_frame([end_date - timedelta(days=2), end_date - timedelta(days=1), end_date])
    archive.to_parquet(tmp_path / "AAPL.parquet")
    (tmp_path / "AAPL.meta.json").write_text(
        json.dumps({"last_full_refresh_date": (end_date - timedelta(days=3)).isoformat()})
    )

    def boom(*args, **kwargs):
        raise AssertionError("yf.download must NOT be called when archive is fresh")

    monkeypatch.setattr(mod.yf, "download", boom)

    result = mod.read_or_fetch_archive(
        "AAPL", end_date=end_date, cache_dir=tmp_path, archive_history_days=1260,
    )
    assert result is not None
    assert len(result) == 3


def test_cache_stale_incremental_fetches_only_the_gap(tmp_path, monkeypatch):
    """Archive's latest_stored_bar = end_date - 3; last_full_refresh < 7 days
    ago → incremental fetch with start = latest+1, end = end_date+1 → archive
    appended → returns combined DataFrame.

    Discriminating: assertion checks yfinance.download's `start` kwarg is
    equal to (latest_stored + 1 day), NOT (end_date - archive_history_days). A bug
    that fetched full history on every call would also produce a 'has bars'
    result; only the kwarg assertion catches the gap-fetch contract.
    """
    from swing.data import ohlcv_archive as mod

    end_date = date(2026, 4, 28)
    latest_stored = end_date - timedelta(days=3)
    archive_dates = [latest_stored - timedelta(days=2), latest_stored - timedelta(days=1), latest_stored]
    archive = _mk_yf_frame(archive_dates)
    archive.to_parquet(tmp_path / "AAPL.parquet")
    (tmp_path / "AAPL.meta.json").write_text(
        json.dumps({"last_full_refresh_date": (end_date - timedelta(days=3)).isoformat()})
    )

    recorded_kwargs: dict = {}

    def fake_download(ticker, **kwargs):
        recorded_kwargs.update(kwargs)
        gap_dates = [end_date - timedelta(days=2), end_date - timedelta(days=1), end_date]
        return _mk_yf_frame(gap_dates)

    monkeypatch.setattr(mod.yf, "download", fake_download)

    result = mod.read_or_fetch_archive(
        "AAPL", end_date=end_date, cache_dir=tmp_path, archive_history_days=1260,
    )

    # Discriminating assertion: gap-fetch (start kwarg = latest+1), NOT full-history.
    expected_start = latest_stored + timedelta(days=1)
    assert recorded_kwargs.get("start") == expected_start, (
        f"expected incremental gap fetch start={expected_start}, got start={recorded_kwargs.get('start')}"
    )
    # Combined archive has all 6 unique dates.
    saved = pd.read_parquet(tmp_path / "AAPL.parquet")
    assert len(saved) == 6


def test_weekly_full_refresh_triggers_when_meta_is_8_days_old(tmp_path, monkeypatch):
    """`last_full_refresh_date == today - 8 days` → full-history fetch (NOT
    incremental); archive overwritten; meta updated to today.

    Discriminating: assertion checks yfinance.download's `start` kwarg is
    `end_date - archive_history_days days` (full-window), NOT `latest_stored + 1 day`
    (incremental). Distinguishes weekly-refresh path from incremental path.
    """
    from swing.data import ohlcv_archive as mod

    end_date = date(2026, 4, 28)
    archive = _mk_yf_frame([end_date - timedelta(days=1), end_date])
    archive.to_parquet(tmp_path / "AAPL.parquet")
    stale_meta_date = end_date - timedelta(days=8)
    (tmp_path / "AAPL.meta.json").write_text(
        json.dumps({"last_full_refresh_date": stale_meta_date.isoformat()})
    )

    recorded_kwargs: dict = {}

    def fake_download(ticker, **kwargs):
        recorded_kwargs.update(kwargs)
        return _mk_yf_frame([end_date - timedelta(days=2), end_date - timedelta(days=1), end_date])

    monkeypatch.setattr(mod.yf, "download", fake_download)

    mod.read_or_fetch_archive(
        "AAPL", end_date=end_date, cache_dir=tmp_path, archive_history_days=1260,
    )

    # Discriminating assertion: full-window start uses the trading-day →
    # calendar-day conversion, NOT raw `archive_history_days` as a calendar
    # delta. Codex R1 Critical 1: passing `timedelta(days=1260)` would yield
    # only ~3.45 years instead of the locked 5y retention.
    from swing.data.ohlcv_archive import _calendar_window_for_trading_days
    expected_start = end_date - timedelta(days=_calendar_window_for_trading_days(1260))
    assert recorded_kwargs.get("start") == expected_start, (
        f"expected weekly-refresh full-window start={expected_start}, "
        f"got start={recorded_kwargs.get('start')} — incremental path or "
        f"raw-calendar-days fallback fired instead"
    )
    # Meta updated to today (when the weekly refresh ran), NOT end_date.
    meta = json.loads((tmp_path / "AAPL.meta.json").read_text())
    assert meta["last_full_refresh_date"] == FIXED_TODAY.isoformat()


def test_atomic_replace_preserves_prior_archive_under_simulated_crash(tmp_path, monkeypatch):
    """Pre-existing archive; mid-write os.replace raises → prior archive
    unchanged; no leftover *.parquet.tmp files."""
    from swing.data import ohlcv_archive as mod

    end_date = date(2026, 4, 28)
    pre_existing = _mk_yf_frame([date(2026, 1, 1)], close=99.0)
    pre_existing.to_parquet(tmp_path / "AAPL.parquet")
    (tmp_path / "AAPL.meta.json").write_text(
        json.dumps({"last_full_refresh_date": (end_date - timedelta(days=8)).isoformat()})
    )

    def fake_download(ticker, **kwargs):
        return _mk_yf_frame([end_date], close=200.0)

    monkeypatch.setattr(mod.yf, "download", fake_download)

    real_replace = mod.os.replace

    def crashing_replace(src, dst):
        if str(dst).endswith("AAPL.parquet"):
            raise OSError("simulated crash mid-rename")
        return real_replace(src, dst)

    monkeypatch.setattr(mod.os, "replace", crashing_replace)

    with pytest.raises(OSError, match="simulated crash"):
        mod.read_or_fetch_archive(
            "AAPL", end_date=end_date, cache_dir=tmp_path, archive_history_days=1260,
        )

    # Prior archive byte-stable: still has Close=99.0 from pre_existing.
    survived = pd.read_parquet(tmp_path / "AAPL.parquet")
    assert survived.loc[pd.Timestamp("2026-01-01"), "Close"] == 99.0
    # No leftover *.parquet.tmp files.
    assert list(tmp_path.glob("*.parquet.tmp")) == []


def test_empty_yfinance_result_returns_none(tmp_path, monkeypatch):
    """yfinance returns empty DataFrame (delisted / bad ticker / no history)
    → helper returns None; archive NOT written."""
    from swing.data import ohlcv_archive as mod

    def empty_download(ticker, **kwargs):
        return pd.DataFrame()

    monkeypatch.setattr(mod.yf, "download", empty_download)

    result = mod.read_or_fetch_archive(
        "DELISTED", end_date=date(2026, 4, 28), cache_dir=tmp_path, archive_history_days=1260,
    )
    assert result is None
    assert not (tmp_path / "DELISTED.parquet").exists()


def test_multiindex_columns_are_squeezed(tmp_path, monkeypatch):
    """yfinance ≥1.2 single-ticker `yf.download` returns MultiIndex columns
    (`Price × Ticker`); helper must squeeze to flat columns so `df['Close']`
    is a Series.
    """
    from swing.data import ohlcv_archive as mod

    def multiindex_download(ticker, **kwargs):
        return _mk_yf_frame([date(2026, 4, 28)], multiindex=True)

    monkeypatch.setattr(mod.yf, "download", multiindex_download)

    result = mod.read_or_fetch_archive(
        "AAPL", end_date=date(2026, 4, 28), cache_dir=tmp_path, archive_history_days=1260,
    )
    assert result is not None
    # df['Close'] must be a Series (1-D), not a DataFrame (2-D).
    assert result["Close"].ndim == 1, (
        "MultiIndex columns not squeezed — df['Close'] is still a DataFrame"
    )


def test_end_date_in_past_returns_archive_slice_up_to_end_date(tmp_path, monkeypatch):
    """Archive extends beyond end_date (e.g., as_of_date in the past for
    research-branch parity). Helper returns rows ≤ end_date; never returns
    rows past end_date."""
    from swing.data import ohlcv_archive as mod

    archive_end = date(2026, 4, 28)
    archive = _mk_yf_frame([archive_end - timedelta(days=i) for i in range(10)])
    archive.to_parquet(tmp_path / "AAPL.parquet")
    (tmp_path / "AAPL.meta.json").write_text(
        json.dumps({"last_full_refresh_date": (archive_end - timedelta(days=2)).isoformat()})
    )

    def boom(*args, **kwargs):
        raise AssertionError("yf.download must NOT be called when archive covers end_date")

    monkeypatch.setattr(mod.yf, "download", boom)

    end_date = archive_end - timedelta(days=4)
    result = mod.read_or_fetch_archive(
        "AAPL", end_date=end_date, cache_dir=tmp_path, archive_history_days=1260,
    )
    assert result is not None
    assert result.index.max().date() <= end_date, (
        f"helper returned bars past end_date={end_date}; max bar={result.index.max().date()}"
    )


def test_corrupted_meta_falls_back_to_full_refresh(tmp_path, monkeypatch):
    """Meta JSON is corrupted (not parseable) → helper treats it as 'no meta'
    and triggers full-history refresh. Defensive: never crash on a bad meta."""
    from swing.data import ohlcv_archive as mod

    end_date = date(2026, 4, 28)
    archive = _mk_yf_frame([end_date - timedelta(days=1), end_date])
    archive.to_parquet(tmp_path / "AAPL.parquet")
    (tmp_path / "AAPL.meta.json").write_text("{not valid json")

    fetched = []

    def tracking_download(ticker, **kwargs):
        fetched.append(kwargs)
        return _mk_yf_frame([end_date - timedelta(days=2), end_date - timedelta(days=1), end_date])

    monkeypatch.setattr(mod.yf, "download", tracking_download)

    result = mod.read_or_fetch_archive(
        "AAPL", end_date=end_date, cache_dir=tmp_path, archive_history_days=1260,
    )
    assert result is not None
    assert len(fetched) == 1, "corrupted meta should trigger exactly one refresh"
    # Full-window start uses the trading-day → calendar-day conversion.
    from swing.data.ohlcv_archive import _calendar_window_for_trading_days
    assert fetched[0].get("start") == end_date - timedelta(
        days=_calendar_window_for_trading_days(1260)
    )


def test_parquet_fresh_meta_missing_recovers_via_full_refresh(tmp_path, monkeypatch):
    """Codex R1 Major 1 resolution — cross-file atomicity skew is benign.

    Scenario: a previous run wrote `{TICKER}.parquet` atomically, then
    crashed BEFORE writing `{TICKER}.meta.json`. The next read sees a
    fresh-looking parquet with no meta. Helper's freshness logic must
    treat 'meta missing' as 'last_full_refresh_date unknown' →
    needs_full_refresh = True → recovery via a full-history refresh.
    Cost: one extra yfinance call. Correctness: preserved. Discriminating:
    asserts the refresh actually fires (NOT a vacuous 'returns data' check).
    """
    from swing.data import ohlcv_archive as mod

    end_date = date(2026, 4, 28)
    archive = _mk_yf_frame([end_date - timedelta(days=1), end_date])
    archive.to_parquet(tmp_path / "AAPL.parquet")
    # Deliberately NO meta file — simulates skew after a crash between the
    # two atomic-replace operations.
    assert not (tmp_path / "AAPL.meta.json").exists()

    refresh_calls = []

    def tracking_download(ticker, **kwargs):
        refresh_calls.append(kwargs)
        return _mk_yf_frame([end_date - timedelta(days=2),
                             end_date - timedelta(days=1), end_date])

    monkeypatch.setattr(mod.yf, "download", tracking_download)

    result = mod.read_or_fetch_archive(
        "AAPL", end_date=end_date, cache_dir=tmp_path, archive_history_days=1260,
    )

    assert result is not None
    # Discriminating: must have fired a full-history refresh, not silently
    # treated the parquet as cache-fresh.
    assert len(refresh_calls) == 1, (
        "fresh-parquet/missing-meta skew should trigger exactly one refresh; "
        f"got {len(refresh_calls)} yfinance calls"
    )
    from swing.data.ohlcv_archive import _calendar_window_for_trading_days
    assert refresh_calls[0].get("start") == end_date - timedelta(
        days=_calendar_window_for_trading_days(1260)
    ), "full-history start kwarg missing — incremental path fired instead"
    # Meta now written.
    assert (tmp_path / "AAPL.meta.json").exists()
```

- [ ] **Step 3c: Run tests to confirm failure**

```bash
python -m pytest tests/data/test_ohlcv_archive.py -v 2>&1 | tail -20
```

Expected: all tests fail with `ModuleNotFoundError: No module named 'swing.data.ohlcv_archive'`.

- [ ] **Step 3d: Implement `swing/data/ohlcv_archive.py`**

```python
"""Per-ticker incremental OHLCV archive.

Source-of-truth for archive-aware reads consumed by `swing.prices.PriceFetcher`,
`swing.pipeline.ohlcv.fetch_daily_bars`, and (via the latter) `swing.web.ohlcv_cache.OhlcvCache`.

Schema:
- `{cache_dir}/{TICKER}.parquet` — full retained history, indexed by date,
  with OHLCV columns. Sliced by callers as needed.
- `{cache_dir}/{TICKER}.meta.json` — sidecar metadata, currently
  `{"last_full_refresh_date": "YYYY-MM-DD"}`. Additive shape; future fields
  may join (e.g., last-incremental-fetch timestamp).

Coherence policy (per OHLCV archive consolidation plan locked decision §2.2):
1. New ticker (no archive on disk) → full-history fetch (start = end_date - archive_history_days).
2. Weekly full-refresh: if (today - last_full_refresh_date).days >= 7 → full-history fetch.
3. Otherwise incremental: if latest_stored_bar < end_date → fetch (latest+1, end_date+1).
4. Else cache hit → return archive slice ≤ end_date with NO yfinance call.

Atomicity: all writes go to a `tempfile.NamedTemporaryFile`-style temp file
in the destination directory, then `os.replace` to the final path. Avoids
the cross-device-link gotcha (CLAUDE.md) and ensures readers never observe
partial writes.

yfinance gotchas (CLAUDE.md): all calls go through `yf.download` with
`threads=False` (NOT `yf.Ticker.history()`); MultiIndex columns are squeezed
defensively.
"""
from __future__ import annotations

import json
import logging
import os
import tempfile
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd
import yfinance as yf

log = logging.getLogger(__name__)


def _archive_paths(cache_dir: Path, ticker: str) -> tuple[Path, Path]:
    return (cache_dir / f"{ticker}.parquet"), (cache_dir / f"{ticker}.meta.json")


def _read_meta(meta_path: Path) -> dict:
    if not meta_path.exists():
        return {}
    try:
        return json.loads(meta_path.read_text())
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("corrupted meta %s: %s — treating as missing", meta_path, exc)
        return {}


def _write_meta_atomic(meta_path: Path, meta: dict) -> None:
    cache_dir = meta_path.parent
    fd, tmp_name = tempfile.mkstemp(
        dir=str(cache_dir), prefix=f"{meta_path.stem}.", suffix=".meta.json.tmp"
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        tmp_path.write_text(json.dumps(meta))
        os.replace(tmp_path, meta_path)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def _read_archive(parquet_path: Path) -> pd.DataFrame | None:
    if not parquet_path.exists():
        return None
    return pd.read_parquet(parquet_path)


def _write_archive_atomic(parquet_path: Path, df: pd.DataFrame) -> None:
    cache_dir = parquet_path.parent
    fd, tmp_name = tempfile.mkstemp(
        dir=str(cache_dir), prefix=f"{parquet_path.stem}.", suffix=".parquet.tmp"
    )
    os.close(fd)
    tmp_path = Path(tmp_name)
    try:
        df.to_parquet(tmp_path)
        os.replace(tmp_path, parquet_path)
    except Exception:
        if tmp_path.exists():
            try:
                tmp_path.unlink()
            except OSError:
                pass
        raise


def _squeeze_multiindex(df: pd.DataFrame) -> pd.DataFrame:
    if isinstance(df.columns, pd.MultiIndex):
        df = df.copy()
        df.columns = df.columns.get_level_values(0)
    return df


def _calendar_window_for_trading_days(trading_days: int) -> int:
    """Convert trading-day retention to a calendar-day yfinance window.

    Codex R1 Critical 1 + R2 Critical 1 resolution: 1260 trading days is
    NOT 1260 calendar days (~3.45y) AND a `n * 7 / 5 + 14` heuristic is
    too tight (1778 calendar days < 5y = ~1826 calendar days; multi-year
    holiday clustering eats more than a 14-day buffer). The locked
    retention is "5 years" (spec §2.5), so the conversion uses the actual
    market-calendar ratio: ~252 trading days per ~365.25 calendar days,
    plus a 30-day buffer for holiday clustering. For default 1260 trading
    days: ceil(1260 * 365.25 / 252) + 30 = 1857 calendar days (~5.08y).
    Caller truncates the returned DataFrame to last `trading_days` rows
    post-fetch so the archive doesn't bloat with the buffer days.
    """
    import math
    return int(math.ceil(trading_days * 365.25 / 252)) + 30


def _yf_download_window(ticker: str, *, start: date, end: date) -> pd.DataFrame:
    """Wrap yf.download with the project's gotcha-resistant kwargs.
    `start` is inclusive, `end` is exclusive in yfinance — we always pass
    `end + 1 day` to make the call site's `end_date` semantics inclusive.
    """
    df = yf.download(
        ticker,
        start=start,
        end=end + timedelta(days=1),
        progress=False,
        auto_adjust=False,
        actions=False,
        threads=False,
    )
    if df is None or df.empty:
        return pd.DataFrame()
    df = _squeeze_multiindex(df)
    keep_cols = [c for c in ("Open", "High", "Low", "Close", "Volume") if c in df.columns]
    df = df[keep_cols]
    # yfinance returns timezone-aware Timestamps; normalize to date-only index.
    if hasattr(df.index, "tz") and df.index.tz is not None:
        df.index = df.index.tz_localize(None)
    return df


def _last_completed_session_today() -> date:
    """Return the most recent completed NYSE session as of now. Used as the
    'today' anchor for weekly-refresh and partial-bar-strip semantics.
    Imports lazily to avoid circular references at module load time."""
    from swing.evaluation.dates import last_completed_session
    return last_completed_session(datetime.now())


def read_or_fetch_archive(
    ticker: str,
    *,
    end_date: date,
    cache_dir: Path,
    archive_history_days: int,
) -> pd.DataFrame | None:
    """Read the per-ticker archive, refreshing from yfinance as needed,
    return rows ≤ end_date.

    Args:
        ticker: ticker symbol; used as the archive filename stem.
        end_date: caller's window end (inclusive); typically the most-recent
            completed NYSE session. Caller must NOT pass dates past
            today's last completed session — the helper does not validate.
        cache_dir: archive directory (typically `cfg.paths.prices_cache_dir`).
            Must already exist.
        archive_history_days: full-history fetch window (typically `cfg.archive.archive_history_days`).

    Returns:
        DataFrame indexed by date with OHLCV columns; rows ≤ end_date.
        None if yfinance returns empty (delisted / invalid ticker / no history).
    """
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    parquet_path, meta_path = _archive_paths(cache_dir, ticker)

    today = _last_completed_session_today()

    archive = _read_archive(parquet_path)
    meta = _read_meta(meta_path)

    last_full_refresh: date | None = None
    last_full_str = meta.get("last_full_refresh_date")
    if last_full_str:
        try:
            last_full_refresh = date.fromisoformat(last_full_str)
        except ValueError:
            last_full_refresh = None

    needs_full_refresh = (
        archive is None
        or archive.empty
        or last_full_refresh is None
        or (today - last_full_refresh).days >= 7
    )

    if needs_full_refresh:
        # Trading-day retention → calendar-day fetch window with holiday buffer
        # (Codex R1 Critical 1 resolution): 1260 trading days ≈ 1778 calendar
        # days; passing 1260 calendar would yield only ~3.45 years.
        full_calendar_days = _calendar_window_for_trading_days(archive_history_days)
        full_start = end_date - timedelta(days=full_calendar_days)
        fetched = _yf_download_window(ticker, start=full_start, end=end_date)
        if fetched.empty:
            return None
        # Truncate to most-recent archive_history_days rows in case yfinance
        # returned more than expected (over-fetch from the calendar buffer).
        fetched = fetched.tail(archive_history_days)
        _write_archive_atomic(parquet_path, fetched)
        _write_meta_atomic(meta_path, {"last_full_refresh_date": today.isoformat()})
        return fetched.loc[fetched.index.date <= end_date]

    # Incremental gap branch.
    assert archive is not None  # for type-checkers; covered by needs_full_refresh
    latest_stored: date = archive.index.max().date()
    if latest_stored < end_date:
        gap_start = latest_stored + timedelta(days=1)
        gap = _yf_download_window(ticker, start=gap_start, end=end_date)
        if not gap.empty:
            combined = pd.concat([archive, gap])
            combined = combined[~combined.index.duplicated(keep="last")].sort_index()
            _write_archive_atomic(parquet_path, combined)
            archive = combined

    return archive.loc[archive.index.date <= end_date]
```

- [ ] **Step 3e: Run tests to confirm pass**

```bash
python -m pytest tests/data/test_ohlcv_archive.py -v 2>&1 | tail -30
```

Expected: all tests pass.

- [ ] **Step 3f: Run the full fast suite**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -3
```

Expected: prior count + 9 = ~1332 passed (trust pytest output).

- [ ] **Step 3g: Commit**

```bash
git add swing/data/ohlcv_archive.py tests/data/test_ohlcv_archive.py
git commit -m "feat(data): Task 3 — OHLCV archive helper module"
```

- [ ] **Step 3h: Observable verification**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 3'
```

Expected: ≥1 hit.

---

## Task 4: Refactor `swing/prices.py PriceFetcher` to consume the helper

**Goal:** `PriceFetcher.get(ticker, lookback_days, *, as_of_date=None)` continues to return a DataFrame indexed by date with OHLCV columns; existing call sites unchanged. Internally consumes `read_or_fetch_archive` for archive-aware behavior. `clear_cache` extended to also delete `*.meta.json` files and `*.parquet.tmp` orphan files.

**Files:**
- Modify: `swing/prices.py`.
- Modify: `swing/cli.py:148, 315` (pass `archive_history_days=cfg.archive.archive_history_days`).
- Modify: `swing/pipeline/runner.py:146` (same).
- Modify: `tests/prices/test_prices.py` (verified at HEAD `a4811f4` via `git ls-files tests/ | grep test_prices.py`).

**Discriminating-test sanity check:** A backward-compat test must verify `PriceFetcher.get(ticker, lookback_days)` returns ≤ `lookback_days` calendar-days-back of bars and that bars > `as_of_date` are excluded. A bug that silently dropped the `lookback_days` slice (e.g., always returning the full archive) would pass any "result is non-empty" test; the discriminating assertion checks the date range upper-bound AND the day-count is reasonable for the requested window. Per dispatch brief §7 watch item #6.

The cache-miss-propagation test must verify the empty-fetch behavior: under the prior implementation, `_fetch_from_yf` raised `ValueError("No data for {ticker}")` on empty yfinance result. Under the refactor, `read_or_fetch_archive` returns None; `PriceFetcher.get` must convert None → `ValueError` to preserve the API contract for callers that catch this exception.

- [ ] **Step 4a: Locate the existing PriceFetcher test file**

```bash
git ls-files tests/ | xargs grep -l "PriceFetcher\|swing.prices" 2>/dev/null | head
```

Expected: `tests/prices/test_prices.py` (verified at plan-authoring time). The new tests go alongside the existing ones.

- [ ] **Step 4b: Read the existing test file and mark which tests are PER-AS-OF-DATE-CACHE-INTERNAL (need replacement) vs API-LEVEL (preserve)**

Existing tests that assert the per-as-of-date-keyed file format (e.g., `assert (cache_dir / f"AAPL_120d_asof-2026-04-28.parquet").exists()`) are INTERNAL to the prior implementation and become invalid under the refactor; they're REPLACED by archive-helper-mocked equivalents. Existing tests that assert the public API contract (e.g., `get(ticker, 120, as_of_date=date(...))` returns a DataFrame with the right column shape) must continue to pass.

- [ ] **Step 4c: Write the failing tests (or replace prior internal-cache tests)**

Add to the located test file:

```python
def test_pricefetcher_get_consumes_archive_helper(tmp_path, monkeypatch):
    """`PriceFetcher.get` calls `read_or_fetch_archive` with the resolved
    end_date and the constructor's archive_history_days; returns a DataFrame.

    Discriminating: under a regression that bypassed the helper (e.g.,
    fell back to direct yf.download for missing-archive case), the assertion
    on the helper-call-recording fails. Under a regression that passed the
    wrong end_date (e.g., today-as-naive-date instead of last_completed_session),
    the assertion on the recorded end_date fails.
    """
    from datetime import date, timedelta
    import pandas as pd
    from swing.prices import PriceFetcher

    recorded: dict = {}

    def fake_helper(ticker, *, end_date, cache_dir, archive_history_days):
        recorded["ticker"] = ticker
        recorded["end_date"] = end_date
        recorded["cache_dir"] = cache_dir
        recorded["archive_history_days"] = archive_history_days
        return pd.DataFrame(
            {
                "Open": [100.0, 101.0],
                "High": [101.0, 102.0],
                "Low": [99.0, 100.0],
                "Close": [100.5, 101.5],
                "Volume": [1000, 1100],
            },
            index=pd.to_datetime([end_date - timedelta(days=1), end_date]),
        )

    monkeypatch.setattr("swing.prices.read_or_fetch_archive", fake_helper)

    fetcher = PriceFetcher(cache_dir=tmp_path, archive_history_days=1260)
    df = fetcher.get("AAPL", lookback_days=120, as_of_date=date(2026, 4, 28))

    assert recorded["ticker"] == "AAPL"
    assert recorded["end_date"] == date(2026, 4, 28)
    assert recorded["cache_dir"] == tmp_path
    assert recorded["archive_history_days"] == 1260
    assert list(df.columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_pricefetcher_get_slices_to_lookback_days(tmp_path, monkeypatch):
    """`get(ticker, lookback_days, as_of_date)` returns only bars within
    `[as_of_date - lookback_days, as_of_date]`. The helper may return a
    deeper archive; PriceFetcher slices on the calendar window.
    """
    from datetime import date, timedelta
    import pandas as pd
    from swing.prices import PriceFetcher

    end_date = date(2026, 4, 28)
    # Helper returns 200 days of bars; lookback_days=30 should slice to ~30 calendar days.
    deep_archive = pd.DataFrame(
        {
            "Open": [1.0] * 200,
            "High": [1.0] * 200,
            "Low": [1.0] * 200,
            "Close": [1.0] * 200,
            "Volume": [1] * 200,
        },
        index=pd.to_datetime([end_date - timedelta(days=199 - i) for i in range(200)]),
    )

    def fake_helper(ticker, *, end_date, cache_dir, archive_history_days):
        return deep_archive

    monkeypatch.setattr("swing.prices.read_or_fetch_archive", fake_helper)

    fetcher = PriceFetcher(cache_dir=tmp_path, archive_history_days=1260)
    df = fetcher.get("AAPL", lookback_days=30, as_of_date=end_date)

    # All returned rows within lookback window.
    earliest = df.index.min().date()
    assert earliest >= end_date - timedelta(days=30), (
        f"sliced too widely; earliest bar {earliest} is outside the 30-day lookback"
    )
    assert df.index.max().date() <= end_date


def test_pricefetcher_get_raises_on_empty_helper_result(tmp_path, monkeypatch):
    """When `read_or_fetch_archive` returns None (delisted / bad ticker),
    `PriceFetcher.get` raises `ValueError` to preserve the prior API
    contract (callers may catch this exception)."""
    from datetime import date
    from swing.prices import PriceFetcher

    monkeypatch.setattr("swing.prices.read_or_fetch_archive", lambda *a, **kw: None)

    fetcher = PriceFetcher(cache_dir=tmp_path, archive_history_days=1260)
    with pytest.raises(ValueError, match="No data for"):
        fetcher.get("DELISTED", lookback_days=120, as_of_date=date(2026, 4, 28))


def test_pricefetcher_default_archive_history_days_is_5y(tmp_path):
    """Constructor `archive_history_days` defaults to 1260 when omitted (kwarg-with-default
    preserves backward-compat with existing call sites that don't pass the kwarg)."""
    from swing.prices import PriceFetcher
    fetcher = PriceFetcher(cache_dir=tmp_path)
    assert fetcher.archive_history_days == 1260


def test_pricefetcher_clear_cache_removes_meta_and_tmp_files(tmp_path):
    """`clear_cache` removes `*.parquet`, `*.meta.json`, and `*.parquet.tmp`
    orphan files. Returns count of files deleted."""
    from swing.prices import PriceFetcher

    (tmp_path / "AAPL.parquet").write_text("fake")
    (tmp_path / "AAPL.meta.json").write_text("{}")
    (tmp_path / "AAPL.parquet.tmp").write_text("orphan tmp")
    (tmp_path / "MSFT.parquet").write_text("fake")
    (tmp_path / "README.txt").write_text("not a cache file; preserved")

    fetcher = PriceFetcher(cache_dir=tmp_path)
    count = fetcher.clear_cache()

    assert count == 4  # AAPL.parquet, AAPL.meta.json, AAPL.parquet.tmp, MSFT.parquet
    assert not (tmp_path / "AAPL.parquet").exists()
    assert not (tmp_path / "AAPL.meta.json").exists()
    assert not (tmp_path / "AAPL.parquet.tmp").exists()
    assert not (tmp_path / "MSFT.parquet").exists()
    assert (tmp_path / "README.txt").exists()  # untouched
```

If existing internal-cache tests reference the per-as-of-date filename pattern (`*_*d_asof-*.parquet`), DELETE them — they assert implementation detail that is no longer valid. Replace with the archive-helper-mocked tests above. API-level tests (e.g., `test_pricefetcher_get_returns_dataframe_with_expected_columns`) stay; they continue to exercise the public contract.

- [ ] **Step 4d: Run tests to confirm failure**

```bash
python -m pytest tests/prices/test_prices.py -v 2>&1 | tail -20
```

(Adjust path.)

Expected: new tests fail with `AttributeError: 'PriceFetcher' object has no attribute 'archive_history_days'` or `ImportError: cannot import name 'read_or_fetch_archive' from 'swing.prices'`.

- [ ] **Step 4e: Refactor `swing/prices.py`**

Replace the contents:

```python
"""yfinance wrapper consuming the per-ticker archive helper."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from swing.data.ohlcv_archive import read_or_fetch_archive


def _resolve_asof(as_of_date: date | None) -> date:
    """Translate `None` to the most recent completed NYSE session.

    Prevents caching or evaluating partial intraday bars in live mode.
    """
    if as_of_date is not None:
        return as_of_date
    from swing.evaluation.dates import last_completed_session

    return last_completed_session(datetime.now())


@dataclass
class PriceFetcher:
    """Fetches daily OHLCV via the per-ticker archive (`swing.data.ohlcv_archive`).

    Public API stable: `get(ticker, lookback_days, *, as_of_date=None)` returns
    a DataFrame indexed by date with OHLCV columns, sliced to the
    `lookback_days` calendar-day window ending at the resolved `as_of_date`
    (or last completed NYSE session if as_of_date is None).

    `cache_dir` is the archive directory (per-ticker `{TICKER}.parquet` +
    `{TICKER}.meta.json` sidecar); `archive_history_days` is the full-history fetch
    depth used by the helper's weekly-refresh / new-ticker paths.
    """

    cache_dir: Path
    archive_history_days: int = 1260

    def __post_init__(self) -> None:
        self.cache_dir = Path(self.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def get(
        self, ticker: str, lookback_days: int, *, as_of_date: date | None = None
    ) -> pd.DataFrame:
        """Fetch OHLCV pinned to a completed session, sliced to lookback window.

        `as_of_date=None` → resolves to the last completed NYSE session.
        Raises ValueError when the archive helper has no data for the ticker
        (delisted / invalid / no history) — preserves prior API contract.
        """
        effective = _resolve_asof(as_of_date)
        df = read_or_fetch_archive(
            ticker,
            end_date=effective,
            cache_dir=self.cache_dir,
            archive_history_days=self.archive_history_days,
        )
        if df is None or df.empty:
            raise ValueError(f"No data for {ticker}")
        cutoff = effective - timedelta(days=lookback_days)
        sliced = df.loc[(df.index.date >= cutoff) & (df.index.date <= effective)]
        if sliced.empty:
            raise ValueError(f"No data for {ticker}")
        return sliced

    def clear_cache(self) -> int:
        """Delete archive parquet + meta sidecar + tmp orphan files.
        Returns count deleted."""
        count = 0
        for pattern in ("*.parquet", "*.meta.json", "*.parquet.tmp", "*.meta.json.tmp"):
            for f in self.cache_dir.glob(pattern):
                f.unlink()
                count += 1
        return count
```

- [ ] **Step 4f: Update call sites to pass `archive_history_days`**

In `swing/cli.py:148`:

```python
    fetcher = PriceFetcher(
        cache_dir=cfg.paths.prices_cache_dir,
        archive_history_days=cfg.archive.archive_history_days,
    )
```

Same change at `swing/cli.py:315`.

In `swing/pipeline/runner.py:146`:

```python
    fetcher = PriceFetcher(
        cache_dir=cfg.paths.prices_cache_dir,
        archive_history_days=cfg.archive.archive_history_days,
    )
```

(`swing/weather/runner.py:15` consumes a `PriceFetcher` instance via parameter; constructor change happens at the caller. Verify with `Grep "PriceFetcher\(" swing/` that no other instantiation site exists.)

- [ ] **Step 4g: Run prices tests to confirm pass**

```bash
python -m pytest tests/prices/test_prices.py -v 2>&1 | tail -20
```

Expected: all pass.

- [ ] **Step 4h: Run the full fast suite**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -3
```

Expected: prior count + new prices tests = ~1337 passed.

- [ ] **Step 4i: Commit**

```bash
git add swing/prices.py swing/cli.py swing/pipeline/runner.py tests/prices/test_prices.py
git commit -m "refactor(prices): Task 4 — PriceFetcher consumes archive helper"
```

- [ ] **Step 4j: Observable verification**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 4'
```

Expected: ≥1 hit.

---

## Task 5: Wrap `swing/pipeline/ohlcv.py fetch_daily_bars`

**Goal:** `fetch_daily_bars` becomes a thin adapter over `read_or_fetch_archive`. Adds required kwargs `cache_dir: Path, archive_history_days: int` (no defaults; callers must pass). Preserves `n_bars`, `as_of_date`, partial-bar strip semantics. The prior `yf.Ticker(ticker).history(...)` call is REMOVED. The existing `test_fetch_daily_bars_does_not_pass_threads_kwarg` test is REPLACED with a helper-level equivalent (already in Task 3).

**Files:**
- Modify: `swing/pipeline/ohlcv.py`.
- Modify: `tests/pipeline/test_ohlcv.py` (repoint existing tests; remove the obsolete `Ticker.history()` no-`threads=` kwarg test since the new path doesn't go through Ticker.history).

**Discriminating-test sanity check:** The strip-rule test must continue to assert that `fetch_daily_bars` returns bars whose last date is strictly before `session` when the helper returns a frame with `last_bar.date() == session` (the partial-bar-during-trading-hours scenario). A regression that dropped the strip rule would still return SOME data; only the date-strict-less-than assertion catches the partial-bar leak. Per CLAUDE.md yfinance gotcha (in-progress bar during market hours).

The archive-miss → None propagation test must verify `fetch_daily_bars` returns None when `read_or_fetch_archive` returns None — preserves the existing `OhlcvCache._fetch_bundle_worker` contract that None means "delisted / bad ticker → empty bundle, NOT breaker-relevant" (per `OhlcvCache._fetch_bundle_worker:235-237`).

- [ ] **Step 5a: Read the existing tests/pipeline/test_ohlcv.py to plan the repoint**

```bash
python -m pytest tests/pipeline/test_ohlcv.py --collect-only -q 2>&1 | tail -25
```

Catalog the 5 existing `fetch_daily_bars` tests. Plan:
- `test_fetch_daily_bars_does_not_pass_threads_kwarg` (line 72) — DELETE. The new path never calls `Ticker.history()`. Equivalent assertion lives in Task 3's test_new_ticker_triggers_full_history_fetch (verifies `yf.download` is called with `threads=False`).
- `test_fetch_daily_bars_strips_in_progress_bar_via_as_of_date` — REPOINT. Monkeypatch `swing.pipeline.ohlcv.read_or_fetch_archive` instead of `yf.Ticker`.
- `test_fetch_daily_bars_retains_last_bar_when_complete` — REPOINT. Same pattern.
- `test_fetch_daily_bars_propagates_exception` — REPOINT. Helper raises → fetch_daily_bars propagates.
- `test_fetch_daily_bars_returns_none_on_empty_result` — REPOINT. Helper returns None → fetch_daily_bars returns None.

- [ ] **Step 5b: Write the failing tests (repoint existing + add new ones)**

Modify `tests/pipeline/test_ohlcv.py`. DELETE the existing `test_fetch_daily_bars_does_not_pass_threads_kwarg`. Replace the four other `fetch_daily_bars` tests with helper-mocking versions, AND add the new archive-pass-through assertions:

```python
def test_fetch_daily_bars_strips_in_progress_bar_via_as_of_date(tmp_path, monkeypatch):
    """When the helper returns a frame whose last bar is the in-progress
    session, fetch_daily_bars strips it (CLAUDE.md yfinance gotcha)."""
    from datetime import date, timedelta
    import pandas as pd
    from swing.pipeline import ohlcv as mod

    as_of = date(2026, 4, 28)
    helper_dates = [as_of - timedelta(days=4), as_of - timedelta(days=3),
                    as_of - timedelta(days=2), as_of - timedelta(days=1), as_of]
    helper_frame = pd.DataFrame(
        {"Open": [1.0]*5, "High": [1.0]*5, "Low": [1.0]*5,
         "Close": [1.0]*5, "Volume": [1]*5},
        index=pd.to_datetime(helper_dates),
    )

    def fake_helper(ticker, *, end_date, cache_dir, archive_history_days):
        assert end_date == as_of
        assert cache_dir == tmp_path
        return helper_frame

    monkeypatch.setattr(mod, "read_or_fetch_archive", fake_helper)

    result = mod.fetch_daily_bars(
        "AAPL", n_bars=5, as_of_date=as_of, cache_dir=tmp_path, archive_history_days=1260,
    )
    assert result is not None
    # Last retained bar's date is STRICTLY before as_of (partial-bar strip).
    assert result.index[-1].date() < as_of, (
        f"strip rule failed; last bar {result.index[-1].date()} >= session {as_of}"
    )


def test_fetch_daily_bars_retains_last_bar_when_complete(tmp_path, monkeypatch):
    """Last bar date strictly before session → no strip."""
    from datetime import date, timedelta
    import pandas as pd
    from swing.pipeline import ohlcv as mod

    as_of = date(2026, 4, 28)
    helper_dates = [as_of - timedelta(days=i) for i in range(1, 6)]
    helper_dates.reverse()
    helper_frame = pd.DataFrame(
        {"Open": [1.0]*5, "High": [1.0]*5, "Low": [1.0]*5,
         "Close": [1.0]*5, "Volume": [1]*5},
        index=pd.to_datetime(helper_dates),
    )

    monkeypatch.setattr(mod, "read_or_fetch_archive",
                        lambda *a, **kw: helper_frame)

    result = mod.fetch_daily_bars(
        "AAPL", n_bars=5, as_of_date=as_of, cache_dir=tmp_path, archive_history_days=1260,
    )
    assert result is not None
    assert len(result) == 5
    # No strip — last bar at as_of - 1 day stays.
    assert result.index[-1].date() == as_of - timedelta(days=1)


def test_fetch_daily_bars_propagates_exception(tmp_path, monkeypatch):
    """Helper raises → fetch_daily_bars propagates (caller's circuit breaker
    distinguishes source-level failure from per-ticker absence)."""
    from datetime import date
    from swing.pipeline import ohlcv as mod

    def boom(*args, **kwargs):
        raise RuntimeError("yfinance down")

    monkeypatch.setattr(mod, "read_or_fetch_archive", boom)

    with pytest.raises(RuntimeError, match="yfinance down"):
        mod.fetch_daily_bars(
            "AAPL", as_of_date=date(2026, 4, 28),
            cache_dir=tmp_path, archive_history_days=1260,
        )


def test_fetch_daily_bars_returns_none_on_empty_helper_result(tmp_path, monkeypatch):
    """Helper returns None → fetch_daily_bars returns None (per-ticker
    absence; not breaker-relevant)."""
    from datetime import date
    from swing.pipeline import ohlcv as mod

    monkeypatch.setattr(mod, "read_or_fetch_archive", lambda *a, **kw: None)

    result = mod.fetch_daily_bars(
        "AAPL", as_of_date=date(2026, 4, 28),
        cache_dir=tmp_path, archive_history_days=1260,
    )
    assert result is None


def test_fetch_daily_bars_passes_resolved_session_as_end_date(tmp_path, monkeypatch):
    """When `as_of_date=None`, fetch_daily_bars resolves to action_session_for_run
    (NOT date.today()) per CLAUDE.md exchange-session gotcha (HST lags ET 5h)."""
    from swing.pipeline import ohlcv as mod
    from swing.evaluation.dates import action_session_for_run
    from datetime import datetime
    import pandas as pd

    recorded: dict = {}

    def fake_helper(ticker, *, end_date, cache_dir, archive_history_days):
        recorded["end_date"] = end_date
        return pd.DataFrame()  # Empty → fetch_daily_bars returns None

    monkeypatch.setattr(mod, "read_or_fetch_archive", fake_helper)

    mod.fetch_daily_bars("AAPL", cache_dir=tmp_path, archive_history_days=1260)

    expected_session = action_session_for_run(datetime.now())
    assert recorded["end_date"] == expected_session, (
        f"as_of_date=None should resolve to action_session_for_run; "
        f"got {recorded['end_date']}, expected {expected_session}"
    )
```

- [ ] **Step 5c: Run the tests to confirm failure**

```bash
python -m pytest tests/pipeline/test_ohlcv.py -v 2>&1 | tail -25
```

Expected: new tests fail because `fetch_daily_bars` doesn't yet accept `cache_dir`/`archive_history_days` kwargs and doesn't yet consume `read_or_fetch_archive`.

- [ ] **Step 5d: Refactor `swing/pipeline/ohlcv.py`**

Replace the existing `fetch_daily_bars` with:

```python
"""Daily-bar fetch + pure SMA math for Phase 3d advisories.

`fetch_daily_bars` is now a thin adapter over `swing.data.ohlcv_archive.read_or_fetch_archive`
(per OHLCV archive consolidation plan Task 5). The session-anchored
partial-bar strip (CLAUDE.md yfinance gotcha) is preserved as belt-and-suspenders.
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from swing.data.ohlcv_archive import read_or_fetch_archive
from swing.evaluation.dates import action_session_for_run


def fetch_daily_bars(
    ticker: str,
    *,
    n_bars: int = 60,
    as_of_date: date | None = None,
    cache_dir: Path,
    archive_history_days: int,
) -> pd.DataFrame | None:
    """Fetch up to `n_bars` completed daily bars ≤ as_of_date / session.

    Now archive-aware: consults `swing.data.ohlcv_archive.read_or_fetch_archive`
    instead of calling yfinance directly. Cache_dir + archive_history_days come from
    config (typically `cfg.paths.prices_cache_dir` + `cfg.archive.archive_history_days`).

    Strip rule (CLAUDE.md gotcha + spec §3.1): drops the last row iff
    `last_bar.date() >= session`. Defends against in-progress intraday bar
    leak even if the helper's archive happens to contain it.

    Returns None on empty result (delisted / bad ticker / no data) — the
    cache layer distinguishes this from raised exceptions (source-level
    failures, breaker-relevant).
    """
    session = as_of_date or action_session_for_run(datetime.now())
    df = read_or_fetch_archive(
        ticker, end_date=session, cache_dir=cache_dir, archive_history_days=archive_history_days,
    )
    if df is None or df.empty:
        return None
    last_date = df.index[-1].date()
    if last_date >= session:
        df = df.iloc[:-1]
    if df.empty:
        return None
    return df.tail(n_bars)


def compute_smas(
    bars: pd.DataFrame, periods: Sequence[int],
) -> dict[int, float | None]:
    """Return {period: float|None} from the last row of a rolling-mean over
    the 'Close' column. None if fewer bars than `period` (or 'Close' missing)."""
    if bars is None or bars.empty or "Close" not in bars.columns:
        return {p: None for p in periods}
    closes = bars["Close"].dropna()
    out: dict[int, float | None] = {}
    for p in periods:
        if len(closes) < p:
            out[p] = None
        else:
            sma = closes.rolling(p, min_periods=p).mean()
            last = sma.iloc[-1]
            out[p] = float(last) if pd.notna(last) else None
    return out


def previous_close(bars: pd.DataFrame) -> float | None:
    """Last daily bar's Close, or None if unavailable."""
    if bars is None or bars.empty or "Close" not in bars.columns:
        return None
    closes = bars["Close"].dropna()
    if closes.empty:
        return None
    return float(closes.iloc[-1])
```

- [ ] **Step 5e: Run the tests to confirm pass**

```bash
python -m pytest tests/pipeline/test_ohlcv.py -v 2>&1 | tail -25
```

Expected: all pass. Test count for this file: 4 deleted (the threads-kwarg test) → 5 + 1 = +1 net (4 repointed + 1 new session-resolution test - 1 deleted threads test). Actually 5 retained + 1 new = 6 vs prior 5 → +1 net. Adjust expectation accordingly.

- [ ] **Step 5f: Run the full fast suite**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -3
```

Expected: prior count - 1 (the deleted threads test) + 1 (new session test) = ~1337 passed.

- [ ] **Step 5g: Commit**

```bash
git add swing/pipeline/ohlcv.py tests/pipeline/test_ohlcv.py
git commit -m "refactor(pipeline): Task 5 — fetch_daily_bars consumes archive helper"
```

- [ ] **Step 5h: Observable verification**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 5'
```

Expected: ≥1 hit.

---

## Task 6: `OhlcvCache` backing — wire kwargs + discriminating multi-path tests

**Goal:** `OhlcvCache._fetch_bundle_worker` passes `cache_dir` and `archive_history_days` to `fetch_daily_bars`. Discriminating tests verify (a) cold-start from disk archive (in-memory cache empty + warm disk archive → bundle hydrates from disk), (b) warm-cache precedence (in-memory hit → no disk read).

**Files:**
- Modify: `swing/web/ohlcv_cache.py:217-246` (worker passes cache_dir/archive_history_days; cfg accessor on dataclass).
- Modify: `tests/web/test_ohlcv_cache.py` (add 2 discriminating tests; existing tests continue to pass since they monkeypatch `fetch_daily_bars` directly and don't care about its signature change as long as the new kwargs default sensibly OR the existing tests' `fake_fetch` accepts them via **kwargs).

**Discriminating-test sanity check:** Per dispatch brief §7 watch item #10. The cold-start test seeds the disk archive (via `read_or_fetch_archive`-callable shape OR via direct file write) with KNOWN bars; the warm-cache test pre-populates `OhlcvCache._store` with a known bundle and asserts `read_or_fetch_archive` is NEVER called. A vacuous "bundle returned" test would pass under either branch even if cold-start always re-fetched yfinance; only the explicit "helper called once for cold start, zero times for warm" assertion distinguishes.

Existing tests at `tests/web/test_ohlcv_cache.py` use `monkeypatch.setattr(ohlcv_mod, "fetch_daily_bars", fake_fetch)` where `fake_fetch` typically has signature `(ticker, *, n_bars=...)`. After Task 5 the real `fetch_daily_bars` requires `cache_dir, archive_history_days` kwargs; the monkeypatched `fake_fetch` must accept them too (via `**kwargs` or explicit kwargs). Either update existing fakes to accept `**kwargs` OR keep them strict and let the worker's call satisfy them — verify in Step 6a.

- [ ] **Step 6a: Audit existing tests/web/test_ohlcv_cache.py for fake_fetch signature compatibility**

```bash
grep -n "def fake_fetch\|def slow_fetch\|def always_fail\|def good_fetch\|def tracking_fetch\|def no_data_fetch\|def mixed_fetch" tests/web/test_ohlcv_cache.py
```

For each, examine its signature. If any uses strict kwargs (e.g., `def fake_fetch(ticker, *, n_bars=60)`), it will reject the new `cache_dir=` and `archive_history_days=` from the worker. Quick fix: change every fake's signature to `def fake_fetch(ticker, *, n_bars=60, **_)` to absorb the extra kwargs. This is a mechanical edit; preserve semantics.

- [ ] **Step 6b: Apply the mechanical signature update to existing fakes**

In each `fake_fetch`/`slow_fetch`/`always_fail`/etc. helper inside `tests/web/test_ohlcv_cache.py`, append `**_` to the kwargs list. Example transform:

```python
# Before:
def fake_fetch(ticker, *, n_bars=60):
    ...

# After:
def fake_fetch(ticker, *, n_bars=60, **_):
    ...
```

- [ ] **Step 6c: Write the new failing tests**

Add to `tests/web/test_ohlcv_cache.py`:

```python
def test_ohlcv_cache_cold_start_hydrates_from_disk_archive(tmp_path, monkeypatch):
    """Empty in-memory cache + warm disk archive → bundle hydrates via the
    archive-aware fetch_daily_bars (Task 5 wrapping). Discriminating: counts
    helper invocations; verifies bundle SMA values reflect archive content,
    not yfinance live values."""
    from concurrent.futures import ThreadPoolExecutor
    from datetime import date, timedelta
    import pandas as pd
    from swing.config import Config, Paths, Account, PositionLimits, Risk, VCP, \
        TrendTemplate, RS, ETFExclusion, FocusRanking, NearTriggerConfig, \
        StopAdvisoryConfig, SizingConfig, PipelineConfig, ExportConfig, Web, \
        ClassifierConfig, ArchiveConfig
    from swing.web.ohlcv_cache import OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    # Synthetic 60-day archive with KNOWN closes.
    end_date = date(2026, 4, 28)
    archive_dates = [end_date - timedelta(days=i) for i in range(60, 0, -1)]
    archive = pd.DataFrame(
        {
            "Open": [100.0]*60, "High": [100.0]*60, "Low": [100.0]*60,
            "Close": [100.0 + i for i in range(60)],  # known close pattern
            "Volume": [1000]*60,
        },
        index=pd.to_datetime(archive_dates),
    )
    archive.to_parquet(tmp_path / "AAPL.parquet")
    import json
    (tmp_path / "AAPL.meta.json").write_text(
        json.dumps({"last_full_refresh_date": end_date.isoformat()})
    )

    # Codex R1 Major 4 resolution: freeze the helper's "today" so the
    # weekly-refresh check is stable across wallclock advance. Without this,
    # once real today drifts > 7 days past end_date the helper would enter
    # the weekly-refresh branch and try to call yfinance live.
    from swing.data import ohlcv_archive as archive_mod
    monkeypatch.setattr(
        archive_mod, "_last_completed_session_today",
        lambda: end_date + timedelta(days=1),
    )

    helper_calls: list[str] = []
    real_helper = ohlcv_mod.read_or_fetch_archive

    def counting_helper(ticker, *, end_date, cache_dir, archive_history_days):
        helper_calls.append(ticker)
        return real_helper(
            ticker, end_date=end_date, cache_dir=cache_dir, archive_history_days=archive_history_days,
        )

    monkeypatch.setattr(ohlcv_mod, "read_or_fetch_archive", counting_helper)

    cfg = _minimal_config_for_ohlcv_cache(
        prices_cache_dir=tmp_path,
        archive_history_days=1260,
    )  # see helper at bottom of test file; minimal Config fixture

    cache = OhlcvCache(cfg)
    with ThreadPoolExecutor(max_workers=2) as ex:
        bundles = cache.get_many_bundles(["AAPL"], deadline_seconds=2.0, executor=ex)

    assert "AAPL" in bundles
    bundle = bundles["AAPL"]
    # Discriminating: bundle reflects archive's Close pattern (last close = 100 + 59 = 159).
    assert bundle.previous_close == 159.0, (
        f"cold-start did not hydrate from disk archive; got previous_close={bundle.previous_close}"
    )
    # Helper called exactly once for the requested ticker.
    assert helper_calls == ["AAPL"]


def test_ohlcv_cache_warm_hit_does_not_call_helper(tmp_path, monkeypatch):
    """In-memory cache hit → no disk archive read. Discriminating:
    helper-side fail-loud monkeypatch confirms zero invocations during the
    second call after a successful warm-up."""
    import time
    from concurrent.futures import ThreadPoolExecutor
    from swing.web.ohlcv_cache import OhlcvBundle, OhlcvCache
    from swing.pipeline import ohlcv as ohlcv_mod

    cfg = _minimal_config_for_ohlcv_cache(
        prices_cache_dir=tmp_path,
        archive_history_days=1260,
    )

    cache = OhlcvCache(cfg)
    # Pre-populate in-memory cache with a known bundle.
    warm_bundle = OhlcvBundle(sma10=10.0, sma20=20.0, sma50=50.0,
                              previous_close=99.0, fetched_at=time.monotonic())
    cache._store["AAPL"] = (warm_bundle, time.monotonic())

    def boom(*args, **kwargs):
        raise AssertionError("read_or_fetch_archive must NOT be called on a warm hit")

    monkeypatch.setattr(ohlcv_mod, "read_or_fetch_archive", boom)

    with ThreadPoolExecutor(max_workers=2) as ex:
        bundles = cache.get_many_bundles(["AAPL"], deadline_seconds=2.0, executor=ex)

    assert bundles["AAPL"].previous_close == 99.0
```

The `_minimal_config_for_ohlcv_cache` helper builds a Config with the smallest viable shape; if this helper already exists in the test file (it likely does for the existing tests that construct a Config), reuse it and extend it with `archive=ArchiveConfig(archive_history_days=archive_history_days)`. Otherwise add a small fixture function near the top of the test file.

- [ ] **Step 6d: Run the tests to confirm failure**

```bash
python -m pytest tests/web/test_ohlcv_cache.py::test_ohlcv_cache_cold_start_hydrates_from_disk_archive tests/web/test_ohlcv_cache.py::test_ohlcv_cache_warm_hit_does_not_call_helper -v 2>&1 | tail -20
```

Expected: failures because `OhlcvCache._fetch_bundle_worker` doesn't yet pass `cache_dir`/`archive_history_days` to `fetch_daily_bars`.

- [ ] **Step 6e: Wire `cache_dir` and `archive_history_days` through `OhlcvCache._fetch_bundle_worker`**

Modify `swing/web/ohlcv_cache.py:217-246`:

```python
    def _fetch_bundle_worker(self, ticker: str) -> tuple[OhlcvBundle, bool]:
        """Worker: acquire semaphore, fetch bars, build bundle. Returns
        (bundle, is_source_healthy).

        ... (existing docstring preserved) ...
        """
        with self._sema:
            try:
                bars = ohlcv_mod.fetch_daily_bars(
                    ticker,
                    n_bars=60,
                    cache_dir=self._cfg.paths.prices_cache_dir,
                    archive_history_days=self._cfg.archive.archive_history_days,
                )
            except Exception as exc:
                log.warning("ohlcv fetch raised for %s: %s", ticker, exc)
                return OhlcvBundle.empty(fetched_at=time.monotonic()), False
            # ... (rest of method unchanged) ...
```

- [ ] **Step 6f: Run the tests to confirm pass**

```bash
python -m pytest tests/web/test_ohlcv_cache.py -v 2>&1 | tail -20
```

Expected: all pass — the 2 new tests + every existing test (because the existing fakes accept `**_`).

- [ ] **Step 6g: Run the full fast suite**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -3
```

Expected: prior count + 2 = ~1339 passed.

- [ ] **Step 6h: Commit**

```bash
git add swing/web/ohlcv_cache.py tests/web/test_ohlcv_cache.py
git commit -m "feat(web): Task 6 — OhlcvCache backed by disk archive"
```

- [ ] **Step 6i: Observable verification**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 6'
```

Expected: ≥1 hit.

---

## Task 7: Final verification gate

**Goal:** Verify the full plan landed cleanly. No new code; this is a pure verification task. No commit; this step's output is reported in the executing-plans return report.

- [ ] **Step 7a: Full fast suite**

```bash
python -m pytest -m "not slow" -q 2>&1 | tail -3
```

Expected: ~1339 passed (1314 baseline + ~7 Task 1 + 2 Task 2 + 9 Task 3 + 5 Task 4 + 1 net Task 5 + 2 Task 6 = ~1340 — trust pytest output, not pinned counts).

- [ ] **Step 7b: Ruff baseline**

```bash
ruff check swing/ 2>&1 | tail -5
```

Expected: 91 errors (pre-existing baseline per orchestrator-context.md). Plan introduces zero new violations. If the count rose, identify which task introduced violations and fix in a follow-up commit before reporting.

- [ ] **Step 7c: Full per-task observable verification**

```bash
for n in 1 2 3 4 5 6; do
  echo "=== Task $n ==="
  git log -E --pretty='%s' --grep="^[a-z]+\([a-z]+\): Task $n"
done
```

Expected: each of Tasks 1-6 has ≥1 commit subject matching its task ID. Cross-plan aliasing (other plans' Task N commits) is expected.

- [ ] **Step 7d: Toml-shadowing audit (final, locked-form)**

```bash
git ls-files | xargs grep -ln "archive_history_days" 2>/dev/null
```

Expected output: ONLY the files this plan touched (Python source under `swing/`, test files under `tests/`, this plan document). NO toml/yaml/json/cfg/ini hit anywhere — that's the toml-shadowing failure mode we're guarding against (`aeb2084` 2026-04-28 lesson + Codex R1 Major 3). If a tracked config-shaped file references `archive_history_days`, surface in return report.

- [ ] **Step 7e: yfinance gotcha compliance check**

```bash
grep -rn "yf\.Ticker\|yf\.download" swing/data/ swing/prices.py swing/pipeline/ohlcv.py swing/web/ohlcv_cache.py
```

Expected: only `swing/data/ohlcv_archive.py` calls `yf.download` (with `threads=False`); no other production file calls yfinance directly. `swing/pipeline/ohlcv.py` no longer references `yf.Ticker`. `swing/prices.py` no longer references `yf.download` directly (it consumes the helper instead).

- [ ] **Step 7f: Operator runbook (recorded in return report, not in plan body)**

Operator runs in this order on their machine:

1. Pull Task 1 commit → `git pull && python -m swing.tools.migrate_prices_cache` → consolidate the existing 5,521 per-as-of-date files into per-ticker archives.
2. Verify the migration completed: `ls -1 ~/swing-data/prices-cache/*.parquet | wc -l` should drop from ~5,521 to ~200-300.
3. Pull Tasks 2-6 commits → `git pull` → run `python -m pytest -m "not slow" -q` to confirm tests pass on the operator's machine.
4. `swing web` → first dashboard load may trigger weekly-refresh on a few tickers (last_full_refresh_date inherited from migration is ~recent, so most tickers are "fresh"). Subsequent loads consume the archive.

---

## Self-review

**1. Spec coverage** (against dispatch brief §6 acceptance criteria):
- AC1 (Per-task TDD): every task has Write test → run fail → implement → run pass → commit. ✓
- AC2 (Discriminating-test discipline): each Task body includes a "Discriminating-test sanity check" sentence above the steps. ✓
- AC3 (Multi-path-ingestion): Tasks 4, 5, 6 explicitly cover PriceFetcher, fetch_daily_bars, OhlcvCache. Task 6 specifically asserts cold-start + warm-cache via the OhlcvCache surface. ✓
- AC4 (Sequential single-subagent): Tasks 1-7 are sequential; flat numbering. ✓
- AC5 (Observable-verification ERE form): each task's Step Nh runs `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task N'`. ✓
- AC6 (4-tier commit message): Task 1 = `feat(tools)`, Task 2 = `feat(config)`, Task 3 = `feat(data)`, Task 4 = `refactor(prices)`, Task 5 = `refactor(pipeline)`, Task 6 = `feat(web)`. Codex review-fix commits during executing-plans will follow `fix(area): Codex R<round> Major <id>` per binding conventions. ✓
- AC7 (Migration script first): Task 1 is the migration script. Body specifies operator-action: "Operator runs `python -m swing.tools.migrate_prices_cache` once before pulling Task 4-6 commits" (Step 7f, also Pre-flight context). ✓
- AC8 (Toml-shadowing audit): Task 2 Step 2a runs the audit; Task 7 Step 7d re-verifies. ✓
- AC9 (Atomic-replace correctness tested): Task 1 includes `test_atomic_replace_preserves_prior_archive_on_simulated_crash`; Task 3 includes `test_atomic_replace_preserves_prior_archive_under_simulated_crash`. ✓
- AC10 (Test count baseline pinned): "1314 fast tests passed at HEAD a4811f4" pinned in Pre-flight context. ✓
- AC11 (Plan passes Codex review cycle): handed off to copowers:writing-plans wrapper.

**2. Placeholder scan:** No "TBD", "TODO", "implement later", "fill in details", "appropriate error handling", "Similar to Task N" present. Every step has actual content.

**3. Type consistency:** `read_or_fetch_archive(ticker: str, *, end_date: date, cache_dir: Path, archive_history_days: int) -> pd.DataFrame | None` is the contract used uniformly across Tasks 3, 4, 5, 6. `PriceFetcher.archive_history_days: int = 1260` matches the kwarg name and default in Tasks 2, 4. `ArchiveConfig.archive_history_days` (NOT `archive_history_days`) is the dataclass field name; the field accessor is `cfg.archive.archive_history_days`. Toml audit grep uses `archive_history_days` AND `ohlcv_archive` because the toml override could appear under either name (the audit catches both). Migration script's filename regex matches `[A-Za-z0-9.\-]+` for tickers (covers BRK.B, BF-A).

**4. Adversarial-review watch items pre-emptive coverage** (per dispatch brief §7):
- WI1 (Multi-path coverage): Task 4 (PriceFetcher), Task 5 (pipeline.ohlcv), Task 6 (OhlcvCache cold-start + warm-cache) all have explicit tests.
- WI2 (Atomic-replace correctness): Task 1 + Task 3 each have a partial-write/crash test asserting prior archive byte-stable AND no leftover tmp files.
- WI3 (Migration script idempotency): Task 1 has `test_idempotency_clean_state_is_a_noop` AND `test_idempotency_resumes_from_interrupted_run`. Body specifies the contract above the steps.
- WI4 (yfinance gotchas): Task 3 helper uses `yf.download(threads=False)` exclusively; MultiIndex squeeze test is `test_multiindex_columns_are_squeezed`; `threads=False` propagation test is `test_new_ticker_triggers_full_history_fetch`'s discriminating assertion.
- WI5 (Cache-coherence semantic correctness): Task 3 has discriminating tests for new-ticker, cache-fresh, cache-stale-incremental, weekly-refresh, end-date-in-past, corrupted-meta — every branch.
- WI6 (Backward-compat of PriceFetcher API): Task 4 preserves `get(ticker, lookback_days, *, as_of_date=None)` signature; constructor adds `archive_history_days` kwarg-with-default 1260 so existing call sites without the kwarg still work; Task 4 explicitly updates the three call sites (`cli.py:148, 315`; `pipeline/runner.py:146`).
- WI7 (Toml-shadowing audit): Task 2 Step 2a + Task 7 Step 7d both run the grep.
- WI8 (Discriminating-test for migration): Task 1 fixtures use known-content per-as-of-date files with deliberate overlapping dates; assertions verify newer-as_of-wins semantics + legacy deletion.
- WI9 (Migration interruption recovery): Task 1 `test_atomic_replace_preserves_prior_archive_on_simulated_crash` (mid-rename crash) + `test_idempotency_resumes_from_interrupted_run` (resume from partial state).
- WI10 (OhlcvCache hydration discriminating-test): Task 6 cold-start test counts helper invocations + asserts bundle reflects archive content (not yfinance live); warm-cache test asserts helper not called.

**5. Dispatch-brief §10 escape-hatch surface check:**
- All locked decisions §2.1-2.7 implemented as written. None impossible.
- All precedent file paths verified (CLAUDE.md, orchestrator-context.md, phase3e-todo.md, swing/prices.py, swing/pipeline/ohlcv.py, swing/web/ohlcv_cache.py, swing/config.py).
- One judgment-call resolution worth noting: the migration script's "duplicate-date resolution" picks the row from the higher-as_of file (newer yfinance fetch = newer adjustment factor). This is the operator-coherent choice per the corporate-action policy locked in §2.1; documented in Task 1 body.
- One known limitation surfaced: queries with `as_of_date` deeper than `today - archive_history_days` may return fewer bars than requested (archive doesn't extend backward beyond the configured retention window). V1 callers don't hit this in practice (PriceFetcher typically called with `as_of_date=None` → resolves to today; research-branch parity reproducibility uses its own cache per V1 out-of-scope §5).

---

## Open questions for orchestrator triage

None. All §3 design questions resolved in Pre-flight context. All §2 locked decisions implementable as written. Operator runbook captured in Step 7f. No items requiring orchestrator decision before executing-plans dispatch.
