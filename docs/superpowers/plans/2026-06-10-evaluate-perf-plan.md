# Evaluate-Step Performance (batched gap pre-warm) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Cut the nightly `_step_evaluate` wall from ~522s to ≤90s by pre-warming every per-ticker OHLCV archive with ONE batched `yf.download(threads=False, group_by="ticker")` per cohort/band before the existing serial loops run — without weakening any archive-integrity defense.

**Architecture:** A new `warm_archives_batch` helper in `swing/data/ohlcv_archive.py` classifies the full ticker set into cohorts (cache-hit / gap-by-band / full-refresh) using the **exact** `read_or_fetch_archive` predicates, fetches each cohort in chunked multi-ticker batches, applies a per-ticker validation ladder (F6 all-NaN guard), and merges through the existing `_write_archive_atomic` write path. A shared pure `_full_refresh_due` predicate + a single cached `_full_refresh_stagger_enabled()` config resolver replace the inline `>= 7` test so the warm and the serial fallback can never disagree. `_step_evaluate` calls the warm once and records a `WarmReport` into `warnings_json` on any degradation (#27). The warm is a **pure accelerator** — correctness never depends on it; any miss falls through to the existing serial path.

**Tech Stack:** Python 3.14, pandas, yfinance 1.2.2 (`threads=False` law), pytest + monkeypatch, `zlib.crc32` for the stateless stagger bucket, `functools.lru_cache` for the module-level config resolver.

**Source spec (LOCKED, Codex-converged):** [`docs/superpowers/specs/2026-06-10-evaluate-perf-design.md`](../specs/2026-06-10-evaluate-perf-design.md). This plan implements that spec; it does not re-litigate it. Section references below (`§4.3`, `§5`, etc.) point into the spec.

---

## Resolutions of the spec §10 / brief §3 open items (locked by this plan)

These four decisions are made here and are binding on the tasks below:

1. **Config-read mechanics (spec §10 bullet 2; brief §3.1).** A new field `stagger_full_refresh: bool = True` is added to the existing frozen `ArchiveConfig` dataclass (`swing/config.py:209`) and is therefore TOML-backed via the existing `ArchiveConfig(**raw.get("archive", {}))` line (`config.py:620`) with no loader change. The single resolver `_full_refresh_stagger_enabled()` lives in `swing/data/ohlcv_archive.py`, decorated with `functools.lru_cache(maxsize=1)`, and resolves the value via a **lazy** `from swing.config import Config` import inside the function body (mirroring the existing lazy `from swing.evaluation.dates import last_completed_session` at `ohlcv_archive.py:200` — `swing/config.py` imports only stdlib, so there is **no import cycle**). It reads `Config.from_defaults().archive.stagger_full_refresh` (cwd-independent — `from_defaults` resolves the project root from `__file__`) and returns `True` on **any** exception. The `lru_cache` gives the cache-reset hook (`_full_refresh_stagger_enabled.cache_clear()`) that tests use and that documents the "restart `swing web` to pick up a flip" cadence (spec §5 R3 Minor #2). **`GAP_DEEP_BAND_TRADING_DAYS` and `DEFAULT_CHUNK_SIZE` are module-level constants** in `ohlcv_archive.py` (not config) — the spec §10 permits either and these are tunables the benchmark pins, not operator-facing levers; constants keep them out of the config surface.

2. **Dry-run report delivery (spec §10 bullet 4; brief §3.2).** **No CLI subcommand.** The dry-run cohort report is a `dry_run=True` keyword on `warm_archives_batch` that performs cohort classification with **zero** `yf.download` calls and returns a `WarmReport` carrying the cohort counts. The operator previews first-night load by running a one-line `python -c` snippet (documented in Task 9's runbook block) that calls it with `dry_run=True` and prints the report. This is the lean V1 surface the brief calls for; the always-on cohort telemetry (spec §6 Codex R1 Minor #1) lands in `pipeline.log` on every real run, so an in-cycle CLI is unnecessary.

3. **Benchmark harness shape (spec §8; brief §3.3).** A **non-test, gitignored, operator-run script** at `scripts/benchmark_evaluate_warm.py` (NOT a pytest test — it must hit the live ~580-ticker universe + network, which the fast suite forbids and the slow suite would make CI-fragile). It sweeps `chunk_size ∈ {50, 75, 100}`, `threads=False` first, measures the dominant gap band and the deep-gap band separately (spec §8 R3 Minor #3), and prints a table. It is the executing-phase's evidence source for pinning `DEFAULT_CHUNK_SIZE`; the **acceptance** number (≤90s) is read from `pipeline_step_timings` on the operator-gate nightly, not from this script. `threads=True` is evaluated by the script only as the documented stretch lever and only if `threads=False` cannot reach ≤90s.

4. **Warm-on/warm-off parity-proof mechanics (spec §8 headline guard; brief §3.4).** A focused harness test runs the warm classifier + merge path against a fixed mocked-yf fixture set, producing archives, then asserts **data-content parity** — value-level frame equality via `pd.testing.assert_frame_equal` (`check_dtype=False`: batch-vs-single yfinance returns can differ in int/float Volume dtype, so parity is about VALUES, not fragile parquet bytes) PLUS exact meta equality — against the archives produced by running the serial `read_or_fetch_archive` path over the same fixtures. **The fake `yf.download` MUST branch on call shape** (Codex R1 Major #1): a `str` arg returns the flat single-ticker frame the serial `_yf_download_window` consumes; a `list` arg returns the ticker-major `group_by="ticker"` batch frame — both delivering the same bar values. The discriminating foil is the **rejected R2-Major-1 promotion behavior**: the test includes a deep-gap-band ticker (stale > `GAP_DEEP_BAND_TRADING_DAYS`) and asserts it gets **NO** `last_full_refresh_date` meta write and an incrementally-concatenated archive (the 200-day-old bar retained). A naive warm that *promoted* deep gaps to full-refresh (the rejected R1 draft) would `tail(N)` the single fetched bar (dropping the old bar) + write meta → the parity assertion FAILS. See Task 8 for the exact arithmetic under both paths.

---

## File Structure

| File | Responsibility | Change |
|---|---|---|
| `swing/config.py` | Config dataclasses + TOML loader | **Modify** `ArchiveConfig` (add `stagger_full_refresh: bool = True`). |
| `swing/data/ohlcv_archive.py` | Per-ticker OHLCV archive + (new) batch warm | **Modify**: add `WarmReport`, `_full_refresh_due`, `_full_refresh_stagger_enabled`, `warm_archives_batch`, the cohort classifier + band helpers + the chunk machine; swap the inline `>= 7` in `read_or_fetch_archive` for the shared predicate. Public read/return signature of `read_or_fetch_archive` UNCHANGED. |
| `swing/pipeline/runner.py` | Nightly orchestrator | **Modify** `_step_evaluate` signature (+`run_warnings`) + add the pre-warm call before the fetch loops + the `WarmReport` → `warnings_json` plumbing + the always-on INFO cohort log; thread `run_warnings` at the call site (`runner.py:822`). |
| `scripts/benchmark_evaluate_warm.py` | Operator benchmark harness (gitignored) | **Create** (non-test). |
| `tests/data/test_ohlcv_archive_warm.py` | Unit + parity tests for the warm path | **Create**. |
| `tests/pipeline/test_step_evaluate_warm.py` | `_step_evaluate` wiring + #27 plumbing | **Create** (or extend an existing pipeline test module if the executing engineer finds a closer fit — but a new focused module is preferred). |
| `tests/config/test_archive_config.py` | `stagger_full_refresh` config round-trip | **Create** (or extend the nearest existing config test module). |
| `.gitignore` | ignore the benchmark output | **Modify** (add `scripts/benchmark_evaluate_warm_results*.csv` if the script writes one; the script itself is committed-but-operator-run — see Task 9). |

**Locks propagated verbatim from spec §7 (every task preserves these):**
- The §7 carve-out is the boundary: only `ohlcv_archive.py`, `runner.py` (`_step_evaluate`), `config.py` (`ArchiveConfig`), the new script, and tests. **NO** repo/model/**DB-schema** changes (v26 frozen). **NO** `swing/trades/`. **NO** Shape-A sidecar touches (`write_window` / `resolve_ohlcv_window` / `_backward_compat_rename` / `normalize_legacy_dataframe` — Arc-3/XMAX territory, UNTOUCHED).
- `_write_archive_atomic` is the **sole** archive write path (inherits the completed-day strip at `ohlcv_archive.py:131`).
- F6 is per-ticker: the missing ticker is **present-but-all-NaN**, guarded by `subframe.dropna(how="all").empty`, NEVER column-absence.
- The warm is a **pure accelerator**: per-ticker miss → fallback; whole-chunk raise → whole chunk to fallback; wholesale failure → serial loops re-fetch. Correctness never depends on the warm.
- `threads=False` is the **law** for the warm path. `threads=True` is a documented stretch lever only.
- The deep-gap band stays **INCREMENTAL** (no full-refresh promotion — the R2-Major-1 parity lock).
- **Single session anchor invariant (spec §4.1):** the warm and the serial fallback MUST resolve the **same** completed-session anchor via `_last_completed_session_today()`. The warm derives `today_session` from that same source (Task 4 locks it).
- Zero `Co-Authored-By` on every commit; conventional messages; no `--no-verify`. **Commits/`git diff` run on the WINDOWS host** (where the worktree `.git` file resolves normally) — the "no git in WSL" constraint applied only to Codex's read-only review session, not to plan execution.

---

## Task 1: `stagger_full_refresh` config field

**Files:**
- Modify: `swing/config.py:209-221` (the `ArchiveConfig` dataclass)
- Test: `tests/config/test_archive_config.py` (create)

- [ ] **Step 1: Write the failing test**

```python
# tests/config/test_archive_config.py
"""ArchiveConfig.stagger_full_refresh round-trips from TOML (Arc 6 §5 kill-switch)."""
from __future__ import annotations

from swing.config import ArchiveConfig


def test_stagger_full_refresh_defaults_true():
    """Absent from TOML -> dataclass default True (legacy stagger ON)."""
    cfg = ArchiveConfig()
    assert cfg.stagger_full_refresh is True


def test_stagger_full_refresh_round_trips_from_raw_archive_section():
    """The loader builds ArchiveConfig(**raw['archive']); a false override sticks."""
    cfg = ArchiveConfig(**{"archive_history_days": 1260, "stagger_full_refresh": False})
    assert cfg.stagger_full_refresh is False
    assert cfg.archive_history_days == 1260
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/config/test_archive_config.py -v`
Expected: FAIL — `TypeError: __init__() got an unexpected keyword argument 'stagger_full_refresh'`

- [ ] **Step 3: Write minimal implementation**

In `swing/config.py`, add the field to `ArchiveConfig` (keep the frozen dataclass; add after `archive_history_days`):

```python
@dataclass(frozen=True)
class ArchiveConfig:
    """Disk-archive retained-history depth for the OHLCV archive
    (`swing/data/ohlcv_archive.py`). 1260 = 5y trading days; bounds the
    full-history fetch window invoked by weekly refresh + new-ticker paths.

    `stagger_full_refresh` (Arc 6 §5): when True (default), the weekly
    full-refresh trigger is spread across the week via a stateless
    crc32 hash-bucket (≤13-day hard ceiling) instead of a bare `>= 7`
    cliff, preventing the weekly-storm where large batches of the
    universe re-download deep history on the same night. Setting it
    False restores the exact legacy `>= 7` cadence with no code change.

    Toml-shadowing audit (per locked decision §2.5 of the OHLCV archive
    consolidation plan): no override should appear in `swing.config.toml`
    unless the operator explicitly wants a different value.
    """
    archive_history_days: int = 1260
    stagger_full_refresh: bool = True
```

Do **not** add a `[archive]` block to `swing.config.toml` (the default is True and the toml-shadowing rule says no tracked override unless the operator wants a different value).

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/config/test_archive_config.py -v`
Expected: PASS (both tests)

- [ ] **Step 5: Commit**

```bash
git add swing/config.py tests/config/test_archive_config.py
git commit -m "feat(config): add ArchiveConfig.stagger_full_refresh kill-switch (Arc 6 §5)"
```

---

## Task 2: The pure `_full_refresh_due` predicate + stagger math

**Files:**
- Modify: `swing/data/ohlcv_archive.py` (add the predicate near the top, after `_last_completed_session_today` ~line 202; add `import zlib` to the import block at the top)
- Test: `tests/data/test_ohlcv_archive_warm.py` (create)

This is the **pure** stagger function. No I/O, no config read — `stagger_enabled` is passed in. The resolver (Task 3) supplies that value.

- [ ] **Step 1: Write the failing test**

```python
# tests/data/test_ohlcv_archive_warm.py
"""warm_archives_batch + the shared full-refresh predicate (Arc 6)."""
from __future__ import annotations

from datetime import date

from swing.data import ohlcv_archive as mod


def test_full_refresh_due_legacy_when_stagger_disabled():
    """stagger_enabled=False -> exact legacy `>= 7` behavior, no bucket gate."""
    today = date(2026, 6, 10)
    # 6 days since -> not due; 7 days -> due.
    assert mod._full_refresh_due("AAPL", date(2026, 6, 4), today, stagger_enabled=False) is False
    assert mod._full_refresh_due("AAPL", date(2026, 6, 3), today, stagger_enabled=False) is True


def test_full_refresh_due_stagger_bucket_gate():
    """stagger_enabled=True: a ticker `>= 7` due fires ONLY on its bucket day,
    where bucket = crc32(ticker) % 7 and day_idx = today.toordinal() % 7."""
    import zlib
    today = date(2026, 6, 10)
    day_idx = today.toordinal() % 7
    # Find a ticker whose bucket == day_idx (fires) and one whose bucket != day_idx (waits).
    on_day = next(t for t in ("AAA", "AAB", "AAC", "AAD", "AAE", "AAF", "AAG", "AAH")
                  if zlib.crc32(t.encode()) % 7 == day_idx)
    off_day = next(t for t in ("AAA", "AAB", "AAC", "AAD", "AAE", "AAF", "AAG", "AAH")
                   if zlib.crc32(t.encode()) % 7 != day_idx)
    last_full = date(2026, 6, 1)  # 9 days -> `>= 7` but `< 13`
    assert mod._full_refresh_due(on_day, last_full, today, stagger_enabled=True) is True
    assert mod._full_refresh_due(off_day, last_full, today, stagger_enabled=True) is False


def test_full_refresh_due_hard_ceiling_13_days_overrides_bucket():
    """>= 13 days stale -> due regardless of bucket (worst-case staleness bound)."""
    today = date(2026, 6, 10)
    day_idx = today.toordinal() % 7
    import zlib
    off_day = next(t for t in ("AAA", "AAB", "AAC", "AAD", "AAE", "AAF", "AAG", "AAH")
                   if zlib.crc32(t.encode()) % 7 != day_idx)
    # 13 days stale -> ceiling fires even though bucket != day_idx.
    assert mod._full_refresh_due(off_day, date(2026, 5, 28), today, stagger_enabled=True) is True


def test_full_refresh_due_not_due_under_7_days_either_mode():
    today = date(2026, 6, 10)
    assert mod._full_refresh_due("AAPL", date(2026, 6, 5), today, stagger_enabled=True) is False
    assert mod._full_refresh_due("AAPL", date(2026, 6, 5), today, stagger_enabled=False) is False
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/data/test_ohlcv_archive_warm.py -v`
Expected: FAIL — `AttributeError: module 'swing.data.ohlcv_archive' has no attribute '_full_refresh_due'`

- [ ] **Step 3: Write minimal implementation**

Add `import zlib` to the import block at the top of `swing/data/ohlcv_archive.py` (alphabetical: after `import tempfile`). Then add the predicate after `_last_completed_session_today` (~line 202):

```python
def _full_refresh_due(
    ticker: str,
    last_full_refresh: date,
    today_session: date,
    *,
    stagger_enabled: bool,
) -> bool:
    """PURE predicate — the single source of full-refresh-due truth, called by
    BOTH read_or_fetch_archive AND warm_archives_batch with the SAME
    stagger_enabled value (resolved once by _full_refresh_stagger_enabled).

    `last_full_refresh` is a real date; callers with no parseable meta MUST
    NOT call this (they are full-refresh-due unconditionally via the
    archive-missing / meta-missing arms of the classifier).

    stagger_enabled=False  -> exact legacy `days_since >= 7` cliff.
    stagger_enabled=True   -> fire on the ticker's own crc32 bucket day once
    `>= 7` due, with a `>= 13` hard ceiling bounding worst-case staleness.
    crc32 (NOT Python hash()) for cross-process determinism — hash(str) is
    randomized by PYTHONHASHSEED.
    """
    days_since_full = (today_session - last_full_refresh).days
    if not stagger_enabled:
        return days_since_full >= 7
    bucket = zlib.crc32(ticker.encode()) % 7
    day_idx = today_session.toordinal() % 7
    return (days_since_full >= 7 and bucket == day_idx) or (days_since_full >= 13)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/data/test_ohlcv_archive_warm.py -v`
Expected: PASS (4 tests)

- [ ] **Step 5: Commit**

```bash
git add swing/data/ohlcv_archive.py tests/data/test_ohlcv_archive_warm.py
git commit -m "feat(data): add pure _full_refresh_due stagger predicate (Arc 6 §5)"
```

---

## Task 3: The single cached config resolver + swap `read_or_fetch_archive` to the shared predicate

**Files:**
- Modify: `swing/data/ohlcv_archive.py` (add `_full_refresh_stagger_enabled`; rewrite the `needs_full_refresh` block at lines 247-252 to consult the resolver + predicate)
- Test: `tests/data/test_ohlcv_archive_warm.py` (extend) + a no-behavior-change regression

The **critical** locks here: (a) `read_or_fetch_archive`'s public signature is UNCHANGED; (b) when `stagger_enabled=False` the behavior is byte-identical to today's `>= 7`; (c) the archive-missing / empty / meta-missing arms still force full-refresh WITHOUT calling the bucket gate.

- [ ] **Step 1: Write the failing tests**

Append to `tests/data/test_ohlcv_archive_warm.py`:

```python
def test_stagger_resolver_returns_true_when_config_unreadable(monkeypatch):
    """_full_refresh_stagger_enabled returns True on any config exception."""
    mod._full_refresh_stagger_enabled.cache_clear()

    def boom():
        raise RuntimeError("no config")

    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", boom)
    assert mod._full_refresh_stagger_enabled() is True
    mod._full_refresh_stagger_enabled.cache_clear()


def test_stagger_resolver_reads_config_value(monkeypatch):
    mod._full_refresh_stagger_enabled.cache_clear()
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    assert mod._full_refresh_stagger_enabled() is False
    mod._full_refresh_stagger_enabled.cache_clear()


def test_read_or_fetch_archive_full_refresh_uses_shared_predicate(tmp_path, monkeypatch):
    """With stagger DISABLED, an 8-day-old meta still triggers full refresh
    (legacy `>= 7` preserved through the shared predicate)."""
    import json
    from datetime import timedelta
    import pandas as pd

    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    mod._full_refresh_stagger_enabled.cache_clear()
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)

    archive = pd.DataFrame(
        {"Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [1.0], "Volume": [10]},
        index=pd.to_datetime([FIXED - timedelta(days=1)]),
    )
    archive.to_parquet(tmp_path / "AAPL.parquet")
    (tmp_path / "AAPL.meta.json").write_text(
        json.dumps({"last_full_refresh_date": (FIXED - timedelta(days=8)).isoformat()})
    )

    called = {"full_start": None}

    def fake_download(ticker, **kwargs):
        called["full_start"] = kwargs.get("start")
        return pd.DataFrame(
            {"Open": [2.0], "High": [2.0], "Low": [2.0], "Close": [2.0], "Volume": [20]},
            index=pd.to_datetime([FIXED]),
        )

    monkeypatch.setattr(mod.yf, "download", fake_download)
    mod.read_or_fetch_archive("AAPL", end_date=FIXED, cache_dir=tmp_path, archive_history_days=1260)
    # full-refresh window start == today - calendar(1260); a gap fetch would use latest+1.
    expected = FIXED - timedelta(days=mod._calendar_window_for_trading_days(1260))
    assert called["full_start"] == expected
    mod._full_refresh_stagger_enabled.cache_clear()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/data/test_ohlcv_archive_warm.py -v -k stagger_resolver or full_refresh_uses_shared`
Expected: FAIL — `AttributeError: ... has no attribute '_full_refresh_stagger_enabled'`

- [ ] **Step 3: Write minimal implementation**

Add `import functools` to the imports. Add the resolver after `_full_refresh_due`:

```python
def _load_archive_config_for_stagger() -> bool:
    """Read [archive].stagger_full_refresh from the tracked project config.

    Isolated so tests can monkeypatch the config read without touching disk.
    Lazy import avoids any import cycle (swing.config imports only stdlib).
    """
    from swing.config import Config
    return Config.from_defaults().archive.stagger_full_refresh


@functools.lru_cache(maxsize=1)
def _full_refresh_stagger_enabled() -> bool:
    """Single source of the stagger kill-switch, cached at module level.

    Returns True (stagger ON) if the config is unreadable for any reason —
    the safe default that prevents the weekly storm. Cached for the process
    lifetime: the nightly pipeline (a fresh process) always reads current
    config; a long-lived `swing web` server holds the value until restart
    (call `_full_refresh_stagger_enabled.cache_clear()` to force a re-read,
    or restart the server — Arc 6 §5 R3 Minor #2).
    """
    try:
        return bool(_load_archive_config_for_stagger())
    except Exception:  # noqa: BLE001 — any failure -> safe default
        log.warning("could not resolve [archive].stagger_full_refresh; defaulting to True")
        return True
```

Now rewrite the `needs_full_refresh` block in `read_or_fetch_archive` (currently lines 247-252). Replace:

```python
    needs_full_refresh = (
        archive is None
        or archive.empty
        or last_full_refresh is None
        or (today - last_full_refresh).days >= 7
    )
```

with:

```python
    if archive is None or archive.empty or last_full_refresh is None:
        needs_full_refresh = True
    else:
        needs_full_refresh = _full_refresh_due(
            ticker, last_full_refresh, today,
            stagger_enabled=_full_refresh_stagger_enabled(),
        )
```

This preserves the structure exactly: the archive-missing / empty / meta-missing arms force full-refresh **without** calling the bucket gate (the predicate is only consulted when there's a real `last_full_refresh`).

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/data/test_ohlcv_archive_warm.py tests/data/test_ohlcv_archive.py -v`
Expected: PASS — the new tests pass AND the **entire existing** `test_ohlcv_archive.py` suite still passes. **Caution:** in the test environment the default config makes `stagger_full_refresh=True`, so an existing test asserting weekly refresh fires at exactly 8 days (e.g. `test_weekly_full_refresh_triggers_when_meta_is_8_days_old`) now fires ONLY when that ticker's crc32 bucket aligns with the pinned `today` — it may go red. The fix (applied in this task) is to monkeypatch `_full_refresh_stagger_enabled` to return `False` (+ `cache_clear()`) in each such legacy-cadence test, preserving its original intent. See the NOTE below.

> **NOTE for the executing engineer (regression risk).** The existing `test_weekly_full_refresh_triggers_when_meta_is_8_days_old` (and any other existing test asserting weekly refresh fires at exactly 8 days) calls real `read_or_fetch_archive`, which now consults `_full_refresh_stagger_enabled()`. In the test environment `Config.from_defaults()` reads the tracked `swing.config.toml` where `stagger_full_refresh` defaults True, so an 8-day-stale ticker fires ONLY if its crc32 bucket aligns with the test's pinned `today`. If that existing test goes red, the minimal fix is to add `monkeypatch.setattr(ohlcv_archive_mod, "_full_refresh_stagger_enabled", lambda: False)` + `cache_clear()` to it (preserving its legacy-cadence intent). Do this in THIS task's commit so the suite is green. Run the full `tests/data/` first to enumerate every affected test.

Run: `python -m pytest tests/data/ -q` and fix any weekly-refresh test the same way before committing.

- [ ] **Step 5: Commit**

```bash
git add swing/data/ohlcv_archive.py tests/data/test_ohlcv_archive_warm.py tests/data/test_ohlcv_archive.py
git commit -m "feat(data): route read_or_fetch_archive through the shared stagger predicate + cached resolver (Arc 6 §5)"
```

---

## Task 4: `WarmReport` dataclass + cohort classifier (local I/O only, zero fetches)

**Files:**
- Modify: `swing/data/ohlcv_archive.py` (add `WarmReport`, `DEFAULT_CHUNK_SIZE`, `GAP_DEEP_BAND_TRADING_DAYS`, `_classify_warm_cohorts`)
- Test: `tests/data/test_ohlcv_archive_warm.py` (extend)

The classifier reads each ticker's archive + meta from disk using the **same** `_read_archive`/`_read_meta` helpers the serial path uses, and buckets via the **exact** `read_or_fetch_archive` predicates (spec §4.1). The session anchor is resolved ONCE here via `_last_completed_session_today()` and threaded to everything (the spec §4.1 single-anchor invariant).

- [ ] **Step 1: Write the failing test**

Append to `tests/data/test_ohlcv_archive_warm.py`:

```python
def _write_archive(tmp_path, ticker, last_date, last_full_refresh_date=None):
    import json
    import pandas as pd
    df = pd.DataFrame(
        {"Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [1.0], "Volume": [10]},
        index=pd.to_datetime([last_date]),
    )
    df.to_parquet(tmp_path / f"{ticker}.parquet")
    if last_full_refresh_date is not None:
        (tmp_path / f"{ticker}.meta.json").write_text(
            json.dumps({"last_full_refresh_date": last_full_refresh_date.isoformat()})
        )


def test_classify_cohorts_cache_hit_gap_full(tmp_path, monkeypatch):
    from datetime import timedelta
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    mod._full_refresh_stagger_enabled.cache_clear()
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)

    # FRESH: latest == today, recent full refresh -> cache-hit.
    _write_archive(tmp_path, "FRESH", FIXED, FIXED - timedelta(days=2))
    # GAP1: latest == today-1, recent full refresh -> gap, band latest=today-1.
    _write_archive(tmp_path, "GAP1", FIXED - timedelta(days=1), FIXED - timedelta(days=2))
    # NEWBIE: no archive on disk -> full-refresh cohort.
    # (no file written for NEWBIE)
    # STALEFULL: latest==today but meta 8 days old -> full-refresh (>= 7 legacy).
    _write_archive(tmp_path, "STALEFULL", FIXED, FIXED - timedelta(days=8))

    report = mod._classify_warm_cohorts(
        ["FRESH", "GAP1", "NEWBIE", "STALEFULL"],
        cache_dir=tmp_path, today_session=FIXED, archive_history_days=1260,
        stagger_enabled=False,
    )
    assert report["cache_hit"] == ["FRESH"]
    assert "GAP1" in report["gap_bands"][FIXED - timedelta(days=1)]
    assert set(report["full_refresh"]) == {"NEWBIE", "STALEFULL"}
    mod._full_refresh_stagger_enabled.cache_clear()


def test_classify_gap_banding_deep_band_collapse(tmp_path, monkeypatch):
    """Tickers staler than GAP_DEEP_BAND_TRADING_DAYS collapse into ONE deep band."""
    from datetime import timedelta
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    mod._full_refresh_stagger_enabled.cache_clear()

    # Two near-current gaps (distinct bands) + two very-stale (collapse to deep band).
    _write_archive(tmp_path, "NEAR1", FIXED - timedelta(days=1), FIXED - timedelta(days=2))
    _write_archive(tmp_path, "NEAR2", FIXED - timedelta(days=2), FIXED - timedelta(days=2))
    _write_archive(tmp_path, "DEEP1", FIXED - timedelta(days=200), FIXED - timedelta(days=2))
    _write_archive(tmp_path, "DEEP2", FIXED - timedelta(days=300), FIXED - timedelta(days=2))

    report = mod._classify_warm_cohorts(
        ["NEAR1", "NEAR2", "DEEP1", "DEEP2"],
        cache_dir=tmp_path, today_session=FIXED, archive_history_days=1260,
        stagger_enabled=False,
    )
    # NEAR1 + NEAR2 in their own per-latest bands; DEEP1+DEEP2 in the single deep band.
    assert "DEEP1" in report["deep_gap"] and "DEEP2" in report["deep_gap"]
    assert "NEAR1" not in report["deep_gap"] and "NEAR2" not in report["deep_gap"]
    mod._full_refresh_stagger_enabled.cache_clear()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/data/test_ohlcv_archive_warm.py -v -k classify`
Expected: FAIL — `AttributeError: ... has no attribute '_classify_warm_cohorts'`

- [ ] **Step 3: Write minimal implementation**

Add the constants near the top of `ohlcv_archive.py` (after `_SOURCE_PRECEDENCE_MARKET_DATA`):

```python
# Arc 6 warm-batch tunables (module constants, NOT config — benchmark-pinned).
DEFAULT_CHUNK_SIZE = 75          # benchmark sweeps 50-100; §8 reliability-constrained
GAP_DEEP_BAND_TRADING_DAYS = 30  # gaps staler than this collapse into ONE deep band
```

Add the `WarmReport` dataclass (needs `from dataclasses import dataclass, field` — add to imports) near the other module-level definitions:

```python
@dataclass
class WarmReport:
    """Lightweight result of warm_archives_batch — counts + the fallback list.
    Carries NO DB rows and NO schema (Arc 6 §6). `degraded` is True whenever
    any ticker fell through to the serial path (per-ticker miss or whole-chunk
    failure), so _step_evaluate can decide whether to emit a #27 warning."""
    cache_hit: int = 0
    gap: int = 0
    deep_gap: int = 0
    full_refresh: int = 0
    chunks_attempted: int = 0
    chunk_failures: int = 0
    fallback: list[str] = field(default_factory=list)
    wall_seconds: float = 0.0
    dry_run: bool = False

    @property
    def degraded(self) -> bool:
        return bool(self.fallback) or self.chunk_failures > 0
```

Add the classifier. It returns a plain dict (the chunk machine consumes it); the public `warm_archives_batch` (Task 7) converts counts into a `WarmReport`:

```python
def _classify_warm_cohorts(
    tickers: list[str],
    *,
    cache_dir: Path,
    today_session: date,
    archive_history_days: int,
    stagger_enabled: bool,
) -> dict:
    """Bucket each ticker into cache-hit / gap-bands / deep-gap / full-refresh
    using the EXACT read_or_fetch_archive predicates (Arc 6 §4.1). Local I/O
    only — reads archive + meta from disk, performs ZERO yf.download calls.

    Returns a dict:
      {"cache_hit": [t...],
       "gap_bands": {latest_date: [t...], ...},   # near-current bands
       "deep_gap": [t...],                          # collapsed deep band
       "full_refresh": [t...]}
    """
    cache_dir = Path(cache_dir)
    cache_hit: list[str] = []
    gap_bands: dict[date, list[str]] = {}
    deep_gap: list[str] = []
    full_refresh: list[str] = []

    for raw in tickers:
        ticker = raw.upper()
        parquet_path, meta_path = _archive_paths(cache_dir, ticker)
        archive = _read_archive(parquet_path)
        meta = _read_meta(meta_path)

        last_full_refresh: date | None = None
        last_full_str = meta.get("last_full_refresh_date")
        if last_full_str:
            try:
                last_full_refresh = date.fromisoformat(last_full_str)
            except ValueError:
                last_full_refresh = None

        # Archive-missing / empty / meta-missing -> full-refresh (NO bucket gate),
        # mirroring read_or_fetch_archive's needs_full_refresh arms.
        if archive is None or archive.empty or last_full_refresh is None:
            full_refresh.append(ticker)
            continue
        if _full_refresh_due(ticker, last_full_refresh, today_session,
                             stagger_enabled=stagger_enabled):
            full_refresh.append(ticker)
            continue

        latest_stored = archive.index.max().date()
        if latest_stored >= today_session:
            cache_hit.append(ticker)
            continue

        # Gap cohort — band by latest_stored; collapse very-stale into deep band.
        staleness_days = (today_session - latest_stored).days
        if staleness_days > _calendar_window_for_trading_days(GAP_DEEP_BAND_TRADING_DAYS):
            deep_gap.append(ticker)
        else:
            gap_bands.setdefault(latest_stored, []).append(ticker)

    return {
        "cache_hit": cache_hit,
        "gap_bands": gap_bands,
        "deep_gap": deep_gap,
        "full_refresh": full_refresh,
    }
```

> **Deep-band threshold note (executing engineer):** the spec §4.2 says "staler than `GAP_DEEP_BAND_TRADING_DAYS` (default 30 trading days)". Staleness is measured in **calendar** days from `latest_stored`, so the comparison converts the trading-day constant to calendar days via the existing `_calendar_window_for_trading_days` helper (≈30 trading days → ≈74 calendar days). The test above uses 200/300-day-stale tickers (unambiguously deep) and 1/2-day-stale (unambiguously near) so it is robust to the exact conversion.

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/data/test_ohlcv_archive_warm.py -v -k classify`
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add swing/data/ohlcv_archive.py tests/data/test_ohlcv_archive_warm.py
git commit -m "feat(data): WarmReport + zero-fetch cohort classifier with gap banding (Arc 6 §4.1)"
```

---

## Task 5: The chunked-batch fetch + per-ticker validation ladder (the F6 guard)

**Files:**
- Modify: `swing/data/ohlcv_archive.py` (add `_chunk_tickers`, `_extract_ticker_subframe`, `_fetch_chunk`)
- Test: `tests/data/test_ohlcv_archive_warm.py` (extend) — **probe-shaped fixtures**

This is the heart of the F6 discipline. **Fixtures derive from the probe-confirmed shape (spec §2):** `group_by="ticker"` MultiIndex (level0=ticker, level1=OHLCV), the missing ticker **present-but-all-NaN** (NOT absent), `Adj Close` column **present-and-dropped**.

- [ ] **Step 1: Write the failing test**

Append to `tests/data/test_ohlcv_archive_warm.py` (`import pandas as pd` is added once here; it is reused by Tasks 6-8 in the same file):

```python
import pandas as pd


def _mk_batch_frame(tickers_dates: dict, *, missing: tuple = (), include_adj=True,
                    dates: list | None = None):
    """Build a probe-shaped group_by='ticker' MultiIndex batch frame.

    tickers_dates: {ticker: [date, ...]} for present (valid) tickers.
    missing: tickers that are PRESENT-BUT-ALL-NAN (the probe-confirmed F6 shape).
    include_adj: include an 'Adj Close' column (present-and-dropped on the real path).
    dates: explicit index dates — REQUIRED when tickers_dates is empty (a
        missing-only frame) so the frame has ROWS (Codex R2 Major #1: a 0-row
        frame is `.empty`, which `_fetch_chunk` treats as a whole-chunk failure
        BEFORE per-ticker all-NaN extraction can run; passing `dates` gives the
        all-NaN frame a real dated index so it exercises the F6 path, not the
        empty-response path).
    """
    all_tickers = list(tickers_dates.keys()) + list(missing)
    # Union of all dates (yfinance aligns the batch on a shared index), plus any
    # explicit `dates` so a missing-only frame still has rows.
    all_dates = sorted(
        {d for ds in tickers_dates.values() for d in ds} | set(dates or [])
    )
    index = pd.to_datetime(all_dates)
    fields = ["Open", "High", "Low", "Close", "Volume"]
    if include_adj:
        fields = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    cols = pd.MultiIndex.from_product([all_tickers, fields])
    df = pd.DataFrame(index=index, columns=cols, dtype=float)
    for t, ds in tickers_dates.items():
        present = pd.to_datetime(ds)
        for f in fields:
            df.loc[present, (t, f)] = 100.0 if f != "Volume" else 1000.0
    # `missing` tickers stay all-NaN (present-but-all-NaN — F6 shape).
    return df


def test_extract_valid_subframe_drops_adj_close_and_tz(monkeypatch):
    from datetime import date as _date
    frame = _mk_batch_frame({"AAPL": [_date(2026, 6, 10)]}, include_adj=True)
    sub = mod._extract_ticker_subframe(frame, "AAPL")
    assert sub is not None
    assert list(sub.columns) == ["Open", "High", "Low", "Close", "Volume"]  # Adj Close dropped
    assert "Adj Close" not in sub.columns


def test_extract_missing_ticker_is_all_nan_returns_none(monkeypatch):
    """F6: present-but-all-NaN subframe -> fallback (None), NOT a write."""
    from datetime import date as _date
    frame = _mk_batch_frame({"AAPL": [_date(2026, 6, 10)]}, missing=("ZZZZINVALID",))
    assert mod._extract_ticker_subframe(frame, "ZZZZINVALID") is None


def test_extract_missing_ohlcv_column_returns_none():
    """A subframe lacking a required OHLCV column -> fallback."""
    from datetime import date as _date
    idx = pd.to_datetime([_date(2026, 6, 10)])
    # AAPL present but with NO 'Close' column (only Open/High/Low/Volume).
    cols = pd.MultiIndex.from_product([["AAPL"], ["Open", "High", "Low", "Volume"]])
    frame = pd.DataFrame(100.0, index=idx, columns=cols)
    assert mod._extract_ticker_subframe(frame, "AAPL") is None


def test_extract_single_ticker_flat_frame_remnant():
    """A size-1 chunk may return a FLAT (non-MultiIndex) frame -> treat as that
    ticker's subframe (Codex R1 Minor #3)."""
    from datetime import date as _date
    idx = pd.to_datetime([_date(2026, 6, 10)])
    flat = pd.DataFrame(
        {"Open": [1.0], "High": [1.0], "Low": [1.0], "Close": [1.0],
         "Adj Close": [1.0], "Volume": [10]}, index=idx,
    )
    sub = mod._extract_ticker_subframe(flat, "AAPL")
    assert sub is not None
    assert list(sub.columns) == ["Open", "High", "Low", "Close", "Volume"]


def test_chunk_tickers_folds_lone_remnant():
    """Chunking avoids a trailing size-1 chunk by folding it into the previous."""
    chunks = mod._chunk_tickers([f"T{i}" for i in range(7)], chunk_size=3)
    # 7 / 3 would naively give [3,3,1]; fold the lone remnant -> [3,4] (no size-1 tail).
    assert all(len(c) > 1 for c in chunks) or len(chunks) == 1
    assert sum(len(c) for c in chunks) == 7


def test_fetch_chunk_whole_failure_routes_all_to_fallback(monkeypatch):
    """A yf.download raise -> every ticker in the chunk failed + chunk_failed=True,
    zero writes."""
    def boom(*a, **k):
        raise RuntimeError("rate limited")
    monkeypatch.setattr(mod.yf, "download", boom)
    from datetime import date as _date
    extracted, failed, chunk_failed = mod._fetch_chunk(
        ["AAA", "BBB"], start=_date(2026, 6, 9), end=_date(2026, 6, 10),
    )
    assert extracted == {}
    assert set(failed) == {"AAA", "BBB"}
    assert chunk_failed is True


def test_fetch_chunk_all_nan_response_is_not_a_chunk_failure(monkeypatch):
    """Codex R1 Major #6: a VALID response where every ticker is present-but-all-NaN
    -> tickers in `failed` but chunk_failed=False (NOT a download failure). This
    keeps the #27 chunk_failures counter honest."""
    from datetime import date as _date
    def all_nan(arg, **k):
        # dates=[...] so the frame has a real dated row of all-NaN (NOT a 0-row
        # .empty frame, which would hit the whole-chunk-failure guard) — Codex R2 M1.
        return _mk_batch_frame({}, missing=("AAA", "BBB"), dates=[_date(2026, 6, 10)])
    monkeypatch.setattr(mod.yf, "download", all_nan)
    extracted, failed, chunk_failed = mod._fetch_chunk(
        ["AAA", "BBB"], start=_date(2026, 6, 9), end=_date(2026, 6, 10),
    )
    assert extracted == {}
    assert set(failed) == {"AAA", "BBB"}
    assert chunk_failed is False
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/data/test_ohlcv_archive_warm.py -v -k "extract or chunk or fetch_chunk"`
Expected: FAIL — `AttributeError: ... has no attribute '_extract_ticker_subframe'`

- [ ] **Step 3: Write minimal implementation**

Add to `ohlcv_archive.py`:

```python
def _chunk_tickers(tickers: list[str], *, chunk_size: int) -> list[list[str]]:
    """Split into chunks of chunk_size, folding a trailing lone remnant into the
    previous chunk so no size-1 chunk is sent (the single-ticker-remnant shape
    is still handled by _extract_ticker_subframe — this just avoids it where we
    can). Returns [] for empty input."""
    if not tickers:
        return []
    chunks = [tickers[i:i + chunk_size] for i in range(0, len(tickers), chunk_size)]
    if len(chunks) > 1 and len(chunks[-1]) == 1:
        lone = chunks.pop()
        chunks[-1] = chunks[-1] + lone
    return chunks


def _extract_ticker_subframe(frame: pd.DataFrame, ticker: str) -> pd.DataFrame | None:
    """Extract + validate one ticker's OHLCV subframe from a group_by='ticker'
    batch response (Arc 6 §4.3 validation ladder). Returns the normalized
    subframe ([Open,High,Low,Close,Volume], tz-stripped) on success, or None on
    ANY gate failure (-> caller routes the ticker to fallback). Wrapped so a
    malformed shape degrades to None rather than crashing the chunk."""
    try:
        ticker = ticker.upper()
        # (a) subframe present. Flat (non-MultiIndex) frame == single-ticker remnant.
        if isinstance(frame.columns, pd.MultiIndex):
            level0 = {str(c).upper(): c for c in frame.columns.get_level_values(0)}
            if ticker not in level0:
                return None
            sub = frame[level0[ticker]]
            if isinstance(sub, pd.Series):  # degenerate single-column
                return None
        else:
            sub = frame  # flat remnant -> already this ticker's OHLCV
        sub = sub.copy()
        # case-insensitive column resolution
        col_map = {str(c).lower(): c for c in sub.columns}
        # (b) required OHLCV columns present
        required = ["open", "high", "low", "close", "volume"]
        if not all(r in col_map for r in required):
            return None
        keep = sub[[col_map[r] for r in required]]
        keep.columns = ["Open", "High", "Low", "Close", "Volume"]  # canonical (Adj Close dropped)
        # (c) non-empty after dropna(how="all") — F6: present-but-all-NaN -> fallback
        keep = keep.dropna(how="all")
        if keep.empty:
            return None
        # (d) index parseable to DatetimeIndex
        if not isinstance(keep.index, pd.DatetimeIndex):
            keep.index = pd.to_datetime(keep.index)
        if getattr(keep.index, "tz", None) is not None:
            keep.index = keep.index.tz_localize(None)
        return keep
    except Exception:  # noqa: BLE001 — any unforeseen shape error -> fallback
        return None


def _fetch_chunk(
    chunk: list[str], *, start: date, end: date,
) -> tuple[dict[str, pd.DataFrame], list[str], bool]:
    """Fetch ONE chunk with a single multi-ticker yf.download (threads=False,
    group_by='ticker'), mirroring _yf_download_window's kwargs + the inclusive-end
    `+1 day` convention. Returns (extracted, failed, chunk_failed):
      - extracted: {ticker: valid_subframe}
      - failed: tickers that did not extract (per-ticker miss OR whole-chunk)
      - chunk_failed: True ONLY when the whole call failed (yf.download raised, or
        an empty/None response) — a WHOLE-CHUNK download failure (Arc 6 §6). A
        VALID response in which every ticker is present-but-all-NaN sets
        chunk_failed=False (those are per-ticker misses), so the #27
        chunk_failures counter is not corrupted (Codex R1 Major #6)."""
    try:
        raw = yf.download(
            chunk, start=start, end=end + timedelta(days=1),
            group_by="ticker", threads=False, progress=False,
            auto_adjust=False, actions=False,
        )
    except Exception as exc:  # noqa: BLE001 — whole chunk -> serial fallback
        log.warning("warm chunk yf.download failed (%d tickers -> fallback): %s",
                    len(chunk), exc)
        return {}, list(chunk), True
    if raw is None or raw.empty:
        return {}, list(chunk), True
    extracted: dict[str, pd.DataFrame] = {}
    failed: list[str] = []
    for t in chunk:
        sub = _extract_ticker_subframe(raw, t)
        if sub is None:
            failed.append(t.upper())
        else:
            extracted[t.upper()] = sub
    return extracted, failed, False
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/data/test_ohlcv_archive_warm.py -v -k "extract or chunk or fetch_chunk"`
Expected: PASS (7 tests)

- [ ] **Step 5: Commit**

```bash
git add swing/data/ohlcv_archive.py tests/data/test_ohlcv_archive_warm.py
git commit -m "feat(data): chunked-batch fetch + per-ticker validation ladder with F6 all-NaN guard (Arc 6 §4.3)"
```

---

## Task 6: Per-cohort merge + write (gap = no meta; full-refresh = meta)

**Files:**
- Modify: `swing/data/ohlcv_archive.py` (add `_merge_gap_subframe`, `_write_full_refresh_subframe`)
- Test: `tests/data/test_ohlcv_archive_warm.py` (extend)

The merge mechanics must produce **data-content-identical** archives to the serial `read_or_fetch_archive` branches (same ops, same resulting bars): gap = slice-to-`> latest_stored` + `concat([archive, fresh])` + dedup `keep="last"` + `sort_index` + `.tail(N)` + `_write_archive_atomic`, **NO meta**; full-refresh = `sub.tail(N)` + `_write_archive_atomic` + `_write_meta_atomic`.

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_merge_gap_writes_no_meta_and_concats(tmp_path, monkeypatch):
    from datetime import timedelta
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    _write_archive(tmp_path, "AAPL", FIXED - timedelta(days=1), FIXED - timedelta(days=2))
    sub = pd.DataFrame(
        {"Open": [2.0], "High": [2.0], "Low": [2.0], "Close": [2.0], "Volume": [20]},
        index=pd.to_datetime([FIXED]),
    )
    mod._merge_gap_subframe(tmp_path, "AAPL", sub, archive_history_days=1260)
    written = pd.read_parquet(tmp_path / "AAPL.parquet")
    assert FIXED in [d.date() for d in written.index]  # gap bar merged
    assert (FIXED - timedelta(days=1)) in [d.date() for d in written.index]  # old bar kept
    # Gap cohort writes NO meta (Arc 6 §4.4) — the file may exist from setup but
    # _merge_gap_subframe must NOT rewrite/refresh it. Assert content unchanged:
    import json
    meta = json.loads((tmp_path / "AAPL.meta.json").read_text())
    assert meta["last_full_refresh_date"] == (FIXED - timedelta(days=2)).isoformat()


def test_merge_gap_overlap_does_not_overwrite_existing_bars(tmp_path, monkeypatch):
    """Codex R1 Critical #1: a deep-band-style sub that overlaps existing
    archived rows (because the band window is wider than this ticker's own gap)
    must NOT overwrite those existing bars — only `> latest_stored` rows merge.
    Discriminating: the overlapping row carries a DIFFERENT Close than the
    archive; the archived value must survive (byte-parity with the serial
    `[latest+1, today]` gap fetch which never re-fetches the old bar).
    """
    from datetime import timedelta
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    # Archive has two real bars; latest_stored = FIXED - 2.
    archive = pd.DataFrame(
        {"Open": [1.0, 1.0], "High": [1.0, 1.0], "Low": [1.0, 1.0],
         "Close": [50.0, 51.0], "Volume": [10, 11]},
        index=pd.to_datetime([FIXED - timedelta(days=3), FIXED - timedelta(days=2)]),
    )
    archive.to_parquet(tmp_path / "DEEP.parquet")
    # Wide-band sub: re-states the FIXED-2 bar (Close 999 — must be IGNORED) AND
    # adds the genuinely-new FIXED bar (Close 52 — must merge).
    sub = pd.DataFrame(
        {"Open": [9.0, 9.0], "High": [9.0, 9.0], "Low": [9.0, 9.0],
         "Close": [999.0, 52.0], "Volume": [99, 12]},
        index=pd.to_datetime([FIXED - timedelta(days=2), FIXED]),
    )
    mod._merge_gap_subframe(tmp_path, "DEEP", sub, archive_history_days=1260)
    written = pd.read_parquet(tmp_path / "DEEP.parquet").sort_index()
    by_date = {d.date(): c for d, c in written["Close"].items()}
    assert by_date[FIXED - timedelta(days=2)] == 51.0  # existing bar UNCHANGED (not 999)
    assert by_date[FIXED] == 52.0                       # new bar merged
    assert (FIXED - timedelta(days=3)) in by_date       # old bar retained


def test_write_full_refresh_writes_meta(tmp_path, monkeypatch):
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    sub = pd.DataFrame(
        {"Open": [2.0], "High": [2.0], "Low": [2.0], "Close": [2.0], "Volume": [20]},
        index=pd.to_datetime([FIXED]),
    )
    mod._write_full_refresh_subframe(tmp_path, "NEWBIE", sub, today_session=FIXED,
                                     archive_history_days=1260)
    import json
    meta = json.loads((tmp_path / "NEWBIE.meta.json").read_text())
    assert meta["last_full_refresh_date"] == FIXED.isoformat()
    assert (tmp_path / "NEWBIE.parquet").exists()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/data/test_ohlcv_archive_warm.py -v -k "merge_gap or full_refresh_writes_meta"`
Expected: FAIL — `AttributeError: ... has no attribute '_merge_gap_subframe'`

- [ ] **Step 3: Write minimal implementation**

```python
def _merge_gap_subframe(
    cache_dir: Path, ticker: str, sub: pd.DataFrame, *, archive_history_days: int,
) -> None:
    """Merge a gap subframe into the existing archive — data-content-identical to
    the serial read_or_fetch_archive incremental-gap branch (lines ~277-281):
    concat, dedup keep='last', sort, tail(N), atomic write. NO meta write (gap).

    Codex R1 Critical #1 (deep-band overlap): the deep-gap band collapses tickers
    with DIFFERENT latest_stored into ONE wide window, so a ticker's subframe can
    carry rows AT-OR-BEFORE its own latest_stored (rows another, staler band member
    needed). The serial gap branch fetches ONLY `[latest+1, today]`, so it NEVER
    rewrites a pre-existing archived bar. To match that outcome we slice the
    incoming sub to `index.date > latest_stored` before concat — dropping the
    overlap so existing bars are untouched (a re-fetch of an old bar yfinance may
    have re-stated must NOT overwrite the archived value; that is the serial
    behavior and the #26-temporal-mutation parity requirement). Harmless for
    ordinary bands (all members share latest_stored → zero overlap)."""
    parquet_path, _ = _archive_paths(Path(cache_dir), ticker.upper())
    archive = _read_archive(parquet_path)
    if archive is None or archive.empty:
        # Defensive: a gap-classified ticker should have an archive; if it
        # vanished, write the sub alone (still no meta) and let the serial path
        # re-derive on next read. Tail to retention.
        combined = sub.tail(archive_history_days)
        _write_archive_atomic(parquet_path, combined)
        return
    latest_stored = archive.index.max().date()
    # Drop any incoming row dated <= latest_stored so existing bars are never
    # overwritten (byte-parity with the serial `[latest+1, today]` gap fetch).
    fresh = sub.loc[sub.index.date > latest_stored]
    combined = pd.concat([archive, fresh])
    combined = combined[~combined.index.duplicated(keep="last")].sort_index()
    combined = combined.tail(archive_history_days)
    _write_archive_atomic(parquet_path, combined)


def _write_full_refresh_subframe(
    cache_dir: Path, ticker: str, sub: pd.DataFrame, *,
    today_session: date, archive_history_days: int,
) -> None:
    """Write a full-refresh subframe — data-content-identical to the serial
    full-refresh branch (lines ~266-268): tail(N), atomic write, THEN write meta."""
    parquet_path, meta_path = _archive_paths(Path(cache_dir), ticker.upper())
    fetched = sub.tail(archive_history_days)
    _write_archive_atomic(parquet_path, fetched)
    _write_meta_atomic(meta_path, {"last_full_refresh_date": today_session.isoformat()})
```

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/data/test_ohlcv_archive_warm.py -v -k "merge_gap or full_refresh_writes_meta"`
Expected: PASS (3 tests — including the deep-band overlap parity test)

- [ ] **Step 5: Commit**

```bash
git add swing/data/ohlcv_archive.py tests/data/test_ohlcv_archive_warm.py
git commit -m "feat(data): per-cohort merge/write helpers (gap=no-meta, full-refresh=meta) (Arc 6 §4.4)"
```

---

## Task 7: `warm_archives_batch` assembly + serial-fallback wiring + dry-run

**Files:**
- Modify: `swing/data/ohlcv_archive.py` (add the public `warm_archives_batch`)
- Test: `tests/data/test_ohlcv_archive_warm.py` (extend)

This assembles Tasks 4-6 into the public entry point. It resolves `today_session` ONCE (the single-anchor invariant), classifies, then per cohort/band runs the chunk machine and merges. `dry_run=True` classifies + returns counts with **zero** fetches. Whole-cohort failures degrade to fallback (the serial loops re-fetch).

- [ ] **Step 1: Write the failing test**

Append:

```python
def test_warm_dry_run_does_no_fetch(tmp_path, monkeypatch):
    from datetime import timedelta
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    mod._full_refresh_stagger_enabled.cache_clear()
    _write_archive(tmp_path, "GAP1", FIXED - timedelta(days=1), FIXED - timedelta(days=2))

    def boom(*a, **k):
        raise AssertionError("dry_run must NOT call yf.download")
    monkeypatch.setattr(mod.yf, "download", boom)

    report = mod.warm_archives_batch(
        ["GAP1", "NEWBIE"], cache_dir=tmp_path, archive_history_days=1260,
        end_date=FIXED, dry_run=True,
    )
    assert report.dry_run is True
    assert report.gap == 1
    assert report.full_refresh == 1
    mod._full_refresh_stagger_enabled.cache_clear()


def test_warm_populates_gap_so_serial_is_cache_hit(tmp_path, monkeypatch):
    """End-to-end: warm fills the gap, then read_or_fetch_archive does NO fetch."""
    from datetime import timedelta
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    mod._full_refresh_stagger_enabled.cache_clear()
    _write_archive(tmp_path, "GAP1", FIXED - timedelta(days=1), FIXED - timedelta(days=2))

    def fake_download(chunk, **kwargs):
        return _mk_batch_frame({"GAP1": [FIXED]})

    monkeypatch.setattr(mod.yf, "download", fake_download)
    report = mod.warm_archives_batch(
        ["GAP1"], cache_dir=tmp_path, archive_history_days=1260, end_date=FIXED,
    )
    assert report.gap == 1
    assert report.fallback == []
    # Now the serial read must NOT fetch.
    def boom(*a, **k):
        raise AssertionError("serial read should be a cache-hit after warm")
    monkeypatch.setattr(mod.yf, "download", boom)
    df = mod.read_or_fetch_archive("GAP1", end_date=FIXED, cache_dir=tmp_path,
                                   archive_history_days=1260)
    assert df is not None and FIXED in [d.date() for d in df.index]
    mod._full_refresh_stagger_enabled.cache_clear()


def test_warm_all_nan_ticker_lands_in_fallback_archive_unchanged(tmp_path, monkeypatch):
    """F6 end-to-end: an all-NaN ticker -> WarmReport.fallback, archive+meta
    byte-unchanged."""
    from datetime import timedelta
    import json
    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    mod._full_refresh_stagger_enabled.cache_clear()
    _write_archive(tmp_path, "GAP1", FIXED - timedelta(days=1), FIXED - timedelta(days=2))
    before = (tmp_path / "GAP1.parquet").read_bytes()
    before_meta = (tmp_path / "GAP1.meta.json").read_bytes()

    def fake_download(chunk, **kwargs):
        # GAP1 present-but-all-NaN (F6 shape) — dates=[FIXED] so it has a real
        # all-NaN row, exercising the F6 per-ticker path (not the empty-frame
        # whole-chunk-failure path) — Codex R2 M1.
        return _mk_batch_frame({}, missing=("GAP1",), dates=[FIXED])

    monkeypatch.setattr(mod.yf, "download", fake_download)
    report = mod.warm_archives_batch(
        ["GAP1"], cache_dir=tmp_path, archive_history_days=1260, end_date=FIXED,
    )
    assert "GAP1" in report.fallback
    assert (tmp_path / "GAP1.parquet").read_bytes() == before
    assert (tmp_path / "GAP1.meta.json").read_bytes() == before_meta
    mod._full_refresh_stagger_enabled.cache_clear()
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/data/test_ohlcv_archive_warm.py -v -k "warm_dry_run or warm_populates or warm_all_nan"`
Expected: FAIL — `AttributeError: ... has no attribute 'warm_archives_batch'`

- [ ] **Step 3: Write minimal implementation**

```python
def warm_archives_batch(
    tickers: list[str],
    *,
    cache_dir: Path,
    archive_history_days: int,
    end_date: date,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    inter_chunk_pause_s: float = 0.0,
    dry_run: bool = False,
) -> WarmReport:
    """Pre-warm per-ticker archives with batched multi-ticker yf.download calls
    so the serial read_or_fetch_archive loops all hit the cache-hit branch
    (Arc 6 §3). PURE ACCELERATOR: any per-ticker or per-chunk failure routes to
    `WarmReport.fallback`; the serial path re-fetches those. Never raises for a
    data problem.

    SESSION ANCHOR (Codex R1 Critical #2 — clarified). The warm has NO return
    slice (it returns a WarmReport, not bars), so `end_date` is accepted for
    signature parity with the spec §3 contract but is intentionally UNUSED for
    the write anchor: archives are always warmed to
    `today_session = _last_completed_session_today()`, the SAME source function
    the serial write path (`read_or_fetch_archive` + `_write_archive_atomic`'s
    completed-day strip) uses. The §4.1 invariant is "same SOURCE FUNCTION", not
    a single value threaded through `_write_archive_atomic` (a Shape-A shared
    writer outside this arc's carve-out). Resolving `today_session` once here and
    passing it to the classifier + writers means the warm introduces NO new
    divergence surface beyond what already exists — the three serial fetch loops
    in `_step_evaluate` each call `_last_completed_session_today()` independently
    today. A session-boundary race remains theoretically possible (warm vs serial
    crossing ~16:00 ET mid-run) but is identical in kind to that pre-existing
    inter-loop race and acceptable for a single-operator nightly that runs well
    after the close. Callers MUST pass `end_date` (signature contract); pass
    `last_completed_session(run_now)` from the runner for documentation symmetry.

    dry_run=True: classify + return cohort counts with ZERO yf.download calls.
    """
    import time
    started = time.monotonic()
    cache_dir = Path(cache_dir)
    cache_dir.mkdir(parents=True, exist_ok=True)
    today_session = _last_completed_session_today()
    stagger_enabled = _full_refresh_stagger_enabled()

    deduped = sorted({t.upper() for t in tickers})
    cohorts = _classify_warm_cohorts(
        deduped, cache_dir=cache_dir, today_session=today_session,
        archive_history_days=archive_history_days, stagger_enabled=stagger_enabled,
    )
    gap_count = sum(len(v) for v in cohorts["gap_bands"].values())
    report = WarmReport(
        cache_hit=len(cohorts["cache_hit"]),
        gap=gap_count,
        deep_gap=len(cohorts["deep_gap"]),
        full_refresh=len(cohorts["full_refresh"]),
        dry_run=dry_run,
    )
    if dry_run:
        report.wall_seconds = time.monotonic() - started
        return report

    # --- gap bands: each distinct latest_stored band gets its own window ---
    for band_latest, band_tickers in cohorts["gap_bands"].items():
        _warm_one_window(
            band_tickers, start=band_latest + timedelta(days=1), end=today_session,
            cohort="gap", cache_dir=cache_dir, today_session=today_session,
            archive_history_days=archive_history_days, chunk_size=chunk_size,
            inter_chunk_pause_s=inter_chunk_pause_s, report=report,
        )

    # --- deep-gap band: ONE widest window (still INCREMENTAL — no meta) ---
    if cohorts["deep_gap"]:
        deep_latest = min(
            _read_archive(_archive_paths(cache_dir, t)[0]).index.max().date()
            for t in cohorts["deep_gap"]
        )
        _warm_one_window(
            cohorts["deep_gap"], start=deep_latest + timedelta(days=1), end=today_session,
            cohort="gap", cache_dir=cache_dir, today_session=today_session,
            archive_history_days=archive_history_days, chunk_size=chunk_size,
            inter_chunk_pause_s=inter_chunk_pause_s, report=report,
        )

    # --- full-refresh cohort: one deep window, writes meta ---
    if cohorts["full_refresh"]:
        full_start = today_session - timedelta(
            days=_calendar_window_for_trading_days(archive_history_days)
        )
        _warm_one_window(
            cohorts["full_refresh"], start=full_start, end=today_session,
            cohort="full_refresh", cache_dir=cache_dir, today_session=today_session,
            archive_history_days=archive_history_days, chunk_size=chunk_size,
            inter_chunk_pause_s=inter_chunk_pause_s, report=report,
        )

    report.wall_seconds = time.monotonic() - started
    return report


def _warm_one_window(
    tickers: list[str], *, start: date, end: date, cohort: str,
    cache_dir: Path, today_session: date, archive_history_days: int,
    chunk_size: int, inter_chunk_pause_s: float, report: WarmReport,
) -> None:
    """Fetch one uniform [start, end] window for a set of tickers in chunks;
    merge each extracted subframe per the cohort's write rule. Mutates `report`
    counters + fallback list. cohort in {'gap', 'full_refresh'}."""
    import time
    chunks = _chunk_tickers(tickers, chunk_size=chunk_size)
    for i, chunk in enumerate(chunks):
        report.chunks_attempted += 1
        extracted, failed, chunk_failed = _fetch_chunk(chunk, start=start, end=end)
        if chunk_failed:
            report.chunk_failures += 1   # whole-chunk download failure ONLY (Codex R1 Major #6)
        report.fallback.extend(failed)
        for ticker, sub in extracted.items():
            try:
                if cohort == "gap":
                    _merge_gap_subframe(cache_dir, ticker, sub,
                                        archive_history_days=archive_history_days)
                else:
                    _write_full_refresh_subframe(
                        cache_dir, ticker, sub, today_session=today_session,
                        archive_history_days=archive_history_days)
            except Exception as exc:  # noqa: BLE001 — per-ticker merge fault -> fallback
                log.warning("warm merge failed for %s -> fallback: %s", ticker, exc)
                report.fallback.append(ticker)
        if inter_chunk_pause_s and i < len(chunks) - 1:
            time.sleep(inter_chunk_pause_s)
```

> **Deep-band start note:** the spec §4.2 says the deep-gap band fetches with "that group's single widest window" = `[min(latest_stored)+1, today_session]`. The implementation reads each deep ticker's `latest_stored` to find the band minimum. This is still INCREMENTAL: each deep ticker is merged via `_merge_gap_subframe` (concat + dedup), gets NO meta, exactly as the serial gap branch would — the wider window just fetches extra rows the dedup discards (the R2-Major-1 parity lock).

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/data/test_ohlcv_archive_warm.py -v -k "warm_dry_run or warm_populates or warm_all_nan"`
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add swing/data/ohlcv_archive.py tests/data/test_ohlcv_archive_warm.py
git commit -m "feat(data): warm_archives_batch assembly with banded windows + serial fallback + dry-run (Arc 6 §3-4)"
```

---

## Task 8: Warm-on/warm-off DATA-CONTENT parity proof (the headline guard)

**Files:**
- Test: `tests/data/test_ohlcv_archive_warm.py` (extend) — no implementation; this LOCKS the spec §8 invariant.

The binding invariant (spec §8): warm-ON vs warm-OFF produce **data-content-identical archives** (value-level frame equality, not parquet-byte equality) over the same fixture set. The discriminating foil is the **rejected R2-Major-1 promotion** — a deep-gap ticker must stay INCREMENTAL (no meta, old bar retained). The arithmetic below confirms the test distinguishes the correct path from the rejected naive path (per [[feedback_regression_test_arithmetic]]).

**Arithmetic (computed under both paths):**
- Setup: ticker `DEEP` with an archive whose `latest_stored = today − 200 days`, `last_full_refresh = today − 2 days` (so NOT full-refresh-due — it is a deep GAP). The mocked batch returns bars `[today]` for `DEEP`.
- **Correct (incremental) path:** `_merge_gap_subframe` → `concat([archive(200d ago), sub(today)])` → archive now holds the old bar + today's bar; **meta unchanged** at `today − 2`. The serial `read_or_fetch_archive` over the same fixture takes the gap branch (`latest_stored < today`, not full-refresh-due) → fetches `[latest+1, today]` → same concat → **same archive, same meta**. Parity holds → assertion PASSES.
- **Rejected (promotion) path:** if the warm had promoted `DEEP` to full-refresh (the R1 draft), it would `sub.tail(N)` (dropping the old bar — only `[today]` survives) AND write `meta.last_full_refresh_date = today`. The serial path still does the incremental gap (old bar retained, meta `today − 2`). Archives DIFFER (row count) AND meta differs → assertion **FAILS**. ✓ The test distinguishes.

- [ ] **Step 1: Write the parity test**

```python
def test_warm_on_off_archive_parity_including_deep_gap(tmp_path, monkeypatch):
    """Warm-ON archives are data-content-identical (value-level assert_frame_equal)
    to serial-path archives over the same fixtures. Discriminating: a deep-gap
    ticker stays INCREMENTAL (no meta, old bar retained) — a promotion bug
    (rejected R2-Major-1) would diverge meta + drop the old bar."""
    from datetime import timedelta
    import json
    import shutil

    FIXED = date(2026, 6, 10)
    monkeypatch.setattr(mod, "_last_completed_session_today", lambda: FIXED)
    monkeypatch.setattr(mod, "_load_archive_config_for_stagger", lambda: False)
    mod._full_refresh_stagger_enabled.cache_clear()

    warm_dir = tmp_path / "warm"
    serial_dir = tmp_path / "serial"
    warm_dir.mkdir(); serial_dir.mkdir()

    def seed(d):
        # DEEP: deep gap (latest 200d ago, full refresh only 2d ago -> NOT full-refresh-due).
        deep = pd.DataFrame(
            {"Open": [9.0], "High": [9.0], "Low": [9.0], "Close": [9.0], "Volume": [99]},
            index=pd.to_datetime([FIXED - timedelta(days=200)]),
        )
        deep.to_parquet(d / "DEEP.parquet")
        (d / "DEEP.meta.json").write_text(
            json.dumps({"last_full_refresh_date": (FIXED - timedelta(days=2)).isoformat()})
        )
    seed(warm_dir); seed(serial_dir)

    def fake_download(arg, **kwargs):
        # Codex R1 Major #1: the two paths call yf.download with DIFFERENT shapes.
        #   - WARM: list input  -> ticker-major group_by='ticker' MultiIndex batch.
        #   - SERIAL: str input -> flat single-ticker frame (the _yf_download_window
        #     shape that _squeeze_multiindex + the OHLCV select consume).
        # Both deliver the SAME DEEP bar at FIXED (Close 100, Volume 1000) so the
        # merged archives are value-identical.
        if isinstance(arg, str):
            return pd.DataFrame(
                {"Open": [100.0], "High": [100.0], "Low": [100.0], "Close": [100.0],
                 "Adj Close": [100.0], "Volume": [1000.0]},
                index=pd.to_datetime([FIXED]),
            )
        return _mk_batch_frame({"DEEP": [FIXED]})  # include_adj=True by default

    monkeypatch.setattr(mod.yf, "download", fake_download)

    # WARM path:
    mod.warm_archives_batch(["DEEP"], cache_dir=warm_dir,
                            archive_history_days=1260, end_date=FIXED)
    # SERIAL path (no warm):
    mod.read_or_fetch_archive("DEEP", end_date=FIXED, cache_dir=serial_dir,
                              archive_history_days=1260)

    warm_arch = pd.read_parquet(warm_dir / "DEEP.parquet").sort_index()
    serial_arch = pd.read_parquet(serial_dir / "DEEP.parquet").sort_index()
    # DATA-CONTENT parity: value-level frame equality (canonical column order +
    # sorted index). check_dtype=False because batch-vs-single yfinance returns can
    # differ in int/float Volume dtype — data-content parity is about VALUES, not
    # the parquet bytes (which are fragile across pandas write ordering).
    cols = ["Open", "High", "Low", "Close", "Volume"]
    pd.testing.assert_frame_equal(
        warm_arch[cols], serial_arch[cols], check_dtype=False, check_freq=False,
    )
    # The deep 200d bar is retained (NOT overwritten) and today's bar merged —
    # the C1 lock + the rejected-promotion foil (a full-refresh promotion would
    # tail(N) the single fetched bar, dropping the 200d bar, AND write meta).
    assert (FIXED - timedelta(days=200)) in [d.date() for d in warm_arch.index]
    assert FIXED in [d.date() for d in warm_arch.index]
    # Meta UNCHANGED under both (incremental gap writes no meta).
    warm_meta = json.loads((warm_dir / "DEEP.meta.json").read_text())
    serial_meta = json.loads((serial_dir / "DEEP.meta.json").read_text())
    assert warm_meta == serial_meta
    assert warm_meta["last_full_refresh_date"] == (FIXED - timedelta(days=2)).isoformat()
    mod._full_refresh_stagger_enabled.cache_clear()
```

- [ ] **Step 2: Run to verify it passes**

Run: `python -m pytest tests/data/test_ohlcv_archive_warm.py::test_warm_on_off_archive_parity_including_deep_gap -v`
Expected: PASS

- [ ] **Step 3: Verify it FAILS under the rejected promotion path (red-team the test)**

Temporarily edit `warm_archives_batch`'s deep-gap branch to call `_write_full_refresh_subframe` instead of the gap merge (simulating the rejected R2-Major-1 promotion). Re-run the parity test.
Expected: **FAIL** (archive row mismatch + meta mismatch) — this proves the test is discriminating. **Revert the temporary edit** and confirm the test passes again.

- [ ] **Step 4: Commit**

```bash
git add tests/data/test_ohlcv_archive_warm.py
git commit -m "test(data): warm-on/warm-off archive parity proof with deep-gap promotion foil (Arc 6 §8)"
```

---

## Task 9: `_step_evaluate` pre-warm call + `WarmReport` → `warnings_json` (#27) + always-on telemetry

**Files:**
- Modify: `swing/pipeline/runner.py` — add a small `_prewarm_evaluate_archives` helper (warm call + INFO cohort log + #27 append), call it from `_step_evaluate` before the fetch loops, add `run_warnings` to `_step_evaluate`'s signature, thread `run_warnings=run_warnings` at the call site (`runner.py:822-828`).
- Test: `tests/pipeline/test_step_evaluate_warm.py` (create)

**Design (resolves Codex R1 Major #3 — the placeholder test).** The warm invocation + telemetry + #27 logic is extracted into a small helper `_prewarm_evaluate_archives` so it is unit-testable WITHOUT building `_step_evaluate`'s full fixture surface (cfg/fetcher/csv/universe/lease/price_cache). Four tests target the helper directly with a monkeypatched `warm_archives_batch`. A **fifth source-text wiring test** (Codex R2 Major #2) pins that `_step_evaluate` actually CALLS the helper, and calls it BEFORE the serial `fetcher.get` loops — mirroring the project's existing `test_step_finviz_fetch_invoked_before_step_evaluate` idiom (`tests/pipeline/test_step_finviz_fetch_ordering.py`), which pins a wiring contract via `inspect.getsource` without needing the heavy pipeline fixture. Without it, an implementation could add a correct helper and never wire it in, and the four helper tests would still pass.

- [ ] **Step 1: Write the failing tests** (concrete + runnable)

```python
# tests/pipeline/test_step_evaluate_warm.py
"""_prewarm_evaluate_archives: warm call + #27 telemetry (Arc 6 §6)."""
from __future__ import annotations

from swing.pipeline import runner as rmod
from swing.data.ohlcv_archive import WarmReport


class _Cfg:
    """Minimal duck-typed cfg for the helper (only the fields it reads)."""
    class _Paths:
        prices_cache_dir = "/tmp/arc6-warm-test"
    class _Archive:
        archive_history_days = 1260
    class _RS:
        benchmark_ticker = "SPY"
    paths = _Paths()
    archive = _Archive()
    rs = _RS()


def test_prewarm_calls_warm_once_with_full_deduped_set(monkeypatch):
    captured = {}

    def spy(tickers, **kwargs):
        captured["tickers"] = tickers
        captured["kwargs"] = kwargs
        return WarmReport(cache_hit=3)

    monkeypatch.setattr(rmod, "warm_archives_batch", spy)
    run_warnings: list[dict] = []
    rmod._prewarm_evaluate_archives(
        cfg=_Cfg(), candidate_tickers=["AAPL", "MSFT"],
        universe_tickers=["AAPL", "NVDA"], run_now=None, run_warnings=run_warnings,
    )
    # Called once with benchmark + candidates + universe, deduped + uppercased
    # order-independent (warm_archives_batch dedupes internally; the helper passes
    # the full union).
    assert set(captured["tickers"]) >= {"SPY", "AAPL", "MSFT", "NVDA"}
    assert captured["kwargs"]["archive_history_days"] == 1260


def test_prewarm_degraded_report_appends_27_warning(monkeypatch):
    monkeypatch.setattr(
        rmod, "warm_archives_batch",
        lambda tickers, **k: WarmReport(cache_hit=1, gap=1, fallback=["AAPL"]),
    )
    run_warnings: list[dict] = []
    rmod._prewarm_evaluate_archives(
        cfg=_Cfg(), candidate_tickers=["AAPL"], universe_tickers=[],
        run_now=None, run_warnings=run_warnings,
    )
    assert len(run_warnings) == 1
    assert run_warnings[0]["step"] == "evaluate_warm"
    assert run_warnings[0]["fallback_count"] == 1


def test_prewarm_clean_report_appends_no_warning(monkeypatch):
    monkeypatch.setattr(
        rmod, "warm_archives_batch",
        lambda tickers, **k: WarmReport(cache_hit=5, gap=2),  # empty fallback, 0 chunk_failures
    )
    run_warnings: list[dict] = []
    rmod._prewarm_evaluate_archives(
        cfg=_Cfg(), candidate_tickers=["AAPL"], universe_tickers=["MSFT"],
        run_now=None, run_warnings=run_warnings,
    )
    assert run_warnings == []  # honest funnel — clean warm emits no warning (#27)


def test_prewarm_wholesale_failure_warns_not_raises(monkeypatch):
    def boom(tickers, **k):
        raise RuntimeError("rate limited everywhere")
    monkeypatch.setattr(rmod, "warm_archives_batch", boom)
    run_warnings: list[dict] = []
    # Must NOT raise — warm is best-effort.
    rmod._prewarm_evaluate_archives(
        cfg=_Cfg(), candidate_tickers=["AAPL"], universe_tickers=[],
        run_now=None, run_warnings=run_warnings,
    )
    assert len(run_warnings) == 1
    assert run_warnings[0]["step"] == "evaluate_warm"
    assert "wholesale" in run_warnings[0]["reason"]


def test_step_evaluate_wires_prewarm_before_fetch_loops():
    """Codex R2 Major #2: source-text wiring contract — `_step_evaluate` CALLS
    `_prewarm_evaluate_archives`, and the call site precedes the first serial
    `fetcher.get(` so the pre-warm runs before the loops it accelerates. Mirrors
    the existing `test_step_finviz_fetch_invoked_before_step_evaluate` idiom; pins
    the wiring durably without the heavy `_step_evaluate` runtime fixture (an
    impl could add a correct helper and never call it — the 4 helper tests would
    still pass; this one would not)."""
    import inspect
    import re
    src = inspect.getsource(rmod._step_evaluate)
    # Regex for an actual CALL at line start (Codex R3 Minor #1 — a comment or
    # docstring mention of the name must not satisfy the contract).
    call_match = re.search(r"^\s*_prewarm_evaluate_archives\(", src, re.MULTILINE)
    fetch_idx = src.find("fetcher.get(")
    assert call_match, "_step_evaluate does not CALL _prewarm_evaluate_archives(...)"
    assert fetch_idx > -1, "_step_evaluate has no fetcher.get( call (harness drift?)"
    assert call_match.start() < fetch_idx, (
        f"pre-warm call (offset {call_match.start()}) must precede the first "
        f"fetcher.get (offset {fetch_idx}); the warm must run BEFORE the serial loops."
    )
```

- [ ] **Step 2: Run to verify it fails**

Run: `python -m pytest tests/pipeline/test_step_evaluate_warm.py -v`
Expected: FAIL — `AttributeError: module 'swing.pipeline.runner' has no attribute '_prewarm_evaluate_archives'`

- [ ] **Step 3: Write minimal implementation**

In `swing/pipeline/runner.py`:

1. Add the import near the other `swing.data` imports: `from swing.data.ohlcv_archive import warm_archives_batch`.

2. Add the helper (place it near `_step_evaluate`, above it):

```python
def _prewarm_evaluate_archives(
    *, cfg, candidate_tickers: list[str], universe_tickers: list[str],
    run_now, run_warnings: list[dict] | None,
) -> None:
    """Arc 6: ONE batched gap pre-warm before the serial evaluate loops, so each
    of the three serial fetch loops hits the cache-hit branch (zero per-ticker
    round-trips). PURE ACCELERATOR — any miss falls through to the serial path;
    a wholesale failure is caught + #27-audited, never sinks evaluate.

    `run_now` is accepted for the documented end_date symmetry (the warm anchors
    writes on _last_completed_session_today() internally — see warm_archives_batch
    docstring; end_date is a signature-contract value the warm does not use for
    writes); pass None in unit tests."""
    from datetime import datetime
    from swing.evaluation.dates import last_completed_session
    warm_set = [cfg.rs.benchmark_ticker, *candidate_tickers, *universe_tickers]
    try:
        end_date = last_completed_session(run_now if run_now is not None else datetime.now())
        report = warm_archives_batch(
            warm_set,
            cache_dir=cfg.paths.prices_cache_dir,
            archive_history_days=cfg.archive.archive_history_days,
            end_date=end_date,
        )
    except Exception as exc:  # noqa: BLE001 — warm is best-effort; never sink evaluate
        log.warning("evaluate warm failed wholesale (serial loops will refetch): %s", exc)
        if run_warnings is not None:
            run_warnings.append({
                "step": "evaluate_warm",
                "reason": "warm raised wholesale: " + " ".join(str(exc).split())[:200],
            })
        return
    # Always-on cohort telemetry (Arc 6 §6 R1 Minor #1) — a misbucketing bug that
    # looks "clean" (zero fallbacks) is still visible as an anomalous distribution.
    log.info(
        "evaluate warm: cache_hit=%d gap=%d deep_gap=%d full_refresh=%d "
        "chunks=%d chunk_failures=%d fallback=%d wall=%.1fs",
        report.cache_hit, report.gap, report.deep_gap, report.full_refresh,
        report.chunks_attempted, report.chunk_failures, len(report.fallback),
        report.wall_seconds,
    )
    if report.degraded and run_warnings is not None:
        run_warnings.append({
            "step": "evaluate_warm",
            "reason": "warm degraded; affected tickers re-fetched serially",
            "fallback_count": len(report.fallback),
            "chunk_failures": report.chunk_failures,
            "cache_hit": report.cache_hit,
            "gap": report.gap,
            "deep_gap": report.deep_gap,
            "full_refresh": report.full_refresh,
        })
```

> **`end_date` note:** `runner.py` already imports `last_completed_session` (used at `runner.py:1400` for `data_asof`). The helper re-imports it locally for clarity. The warm IGNORES `end_date` for the write anchor (it anchors on `_last_completed_session_today()` internally — see Task 7's docstring), so `end_date` is purely the signature-contract value; production passes the real `run_now`, the unit-test None branch falls back to `datetime.now()`.

3. Change the `_step_evaluate` signature to accept `run_warnings` and call the helper. Signature:

```python
def _step_evaluate(
    *, cfg, fetcher, csv_path: Path, universe, universe_hash: str,
    run_now: _dt, action_session: _date, lease: Lease,
    price_cache=None, run_warnings: list[dict] | None = None,
) -> int:
```

Insert the call AFTER `held_tickers` is built and merged into `tickers` (after `runner.py:~1344`, the `for t in held_tickers:` merge loop) and BEFORE the SPY fetch (`~1360`):

```python
    # Arc 6: batched gap pre-warm before the three serial fetch loops.
    _prewarm_evaluate_archives(
        cfg=cfg, candidate_tickers=tickers, universe_tickers=universe.tickers,
        run_now=run_now, run_warnings=run_warnings,
    )
```

4. Thread `run_warnings` at the call site (`runner.py:822-828`):

```python
                eval_run_id = _step_evaluate(
                    cfg=cfg, fetcher=fetcher, csv_path=csv_path,
                    universe=universe, universe_hash=universe_hash,
                    run_now=run_now, action_session=action_session,
                    lease=lease,
                    price_cache=price_cache,
                    run_warnings=run_warnings,
                )
```

(`run_warnings` is already initialized at `runner.py:818` before this call — confirmed.)

- [ ] **Step 4: Run to verify it passes**

Run: `python -m pytest tests/pipeline/test_step_evaluate_warm.py -v`
Expected: PASS (5 tests: called-once / degraded-warns / clean-no-warning / wholesale-failure-warns / wiring-before-fetch-loops)

- [ ] **Step 5: Commit**

```bash
git add swing/pipeline/runner.py tests/pipeline/test_step_evaluate_warm.py
git commit -m "feat(pipeline): pre-warm OHLCV archives before evaluate loops + #27 warm telemetry (Arc 6 §6)"
```

---

## Task 10: Benchmark harness script (operator-run, gitignored output)

**Files:**
- Create: `scripts/benchmark_evaluate_warm.py`
- Modify: `.gitignore` (ignore any results CSV the script writes)

This is **not** a pytest test (it needs the live ~580-ticker universe + network). It is the executing-phase's evidence source for pinning `DEFAULT_CHUNK_SIZE`; the acceptance number (≤90s) comes from `pipeline_step_timings` on the operator-gate nightly, not from this script.

- [ ] **Step 1: Write the script** (no test — it is an operator tool)

```python
# scripts/benchmark_evaluate_warm.py
"""Arc 6 benchmark: measure warm_archives_batch wall over the REAL universe.

NOT a pytest test — hits live yfinance. Run manually before the operator gate:

    python scripts/benchmark_evaluate_warm.py

Sweeps chunk_size in {50, 75, 100}, threads=False first. Measures the dominant
near-current gap band and the deep-gap band separately (spec §8 R3 Minor #3).
Prints a table; pins DEFAULT_CHUNK_SIZE for the executing phase. The ACCEPTANCE
number (<=90s) is read from pipeline_step_timings on the gate nightly, NOT here.

To avoid mutating the operator's live archive, point it at a COPY of the cache
dir via --cache-dir, or accept that it warms the real archive (idempotent — it
only fills today's gap, same as the nightly would).
"""
from __future__ import annotations

import argparse
import time
from pathlib import Path

from swing.config import Config
from swing.data.ohlcv_archive import warm_archives_batch, _classify_warm_cohorts, \
    _last_completed_session_today, _full_refresh_stagger_enabled
# Matches swing/pipeline/runner.py:61 + :560 exactly (verified):
from swing.evaluation.rs import load_universe


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cache-dir", default=None,
                    help="archive dir (default: cfg.paths.prices_cache_dir)")
    ap.add_argument("--chunk-sizes", default="50,75,100")
    ap.add_argument("--dry-run-only", action="store_true",
                    help="just print cohort sizes (zero fetches)")
    args = ap.parse_args()

    cfg = Config.from_defaults()
    cache_dir = Path(args.cache_dir) if args.cache_dir else cfg.paths.prices_cache_dir
    universe = load_universe(cfg.paths.rs_universe_path)  # mirrors runner.py:560
    today = _last_completed_session_today()
    tickers = [cfg.rs.benchmark_ticker, *universe.tickers]

    cohorts = _classify_warm_cohorts(
        sorted({t.upper() for t in tickers}), cache_dir=cache_dir,
        today_session=today, archive_history_days=cfg.archive.archive_history_days,
        stagger_enabled=_full_refresh_stagger_enabled(),
    )
    gap_count = sum(len(v) for v in cohorts["gap_bands"].values())
    print(f"universe={len(tickers)} cache_hit={len(cohorts['cache_hit'])} "
          f"gap={gap_count} deep_gap={len(cohorts['deep_gap'])} "
          f"full_refresh={len(cohorts['full_refresh'])} "
          f"gap_bands={len(cohorts['gap_bands'])}")
    if args.dry_run_only:
        return

    for cs in (int(x) for x in args.chunk_sizes.split(",")):
        t0 = time.monotonic()
        report = warm_archives_batch(
            tickers, cache_dir=cache_dir,
            archive_history_days=cfg.archive.archive_history_days,
            end_date=today, chunk_size=cs,
        )
        wall = time.monotonic() - t0
        print(f"chunk_size={cs:3d} wall={wall:6.1f}s chunks={report.chunks_attempted} "
              f"chunk_failures={report.chunk_failures} fallback={len(report.fallback)}")


if __name__ == "__main__":
    main()
```

> **Executing-engineer note:** the universe loader import is `from swing.evaluation.rs import load_universe`, called `load_universe(cfg.paths.rs_universe_path)` — VERIFIED against `swing/pipeline/runner.py:61` + `:560` (the exact call the nightly uses), so the benchmark measures the SAME ticker set as the pipeline. The live network sweep only RUNS in the executing phase (with the operator).

- [ ] **Step 2: Add the gitignore entry** (the script is committed; if it writes a results CSV, ignore that)

Append to `.gitignore`:

```
# Arc 6 benchmark output (operator-run; not an artifact)
scripts/benchmark_evaluate_warm_results*.csv
```

- [ ] **Step 3: Verify the script's imports actually resolve** (no network, no `main()`)

`py_compile` only checks syntax — it does NOT execute the `import` statements (Codex R2 Minor #1). Load the module by file path so its top-level imports run (`swing.config.Config`, `swing.evaluation.rs.load_universe`, the `swing.data.ohlcv_archive` warm symbols) while `main()` stays guarded (`__name__` is not `"__main__"` under this loader):

Run:
```bash
python -c "import importlib.util as u; s=u.spec_from_file_location('bench','scripts/benchmark_evaluate_warm.py'); m=u.module_from_spec(s); s.loader.exec_module(m); print('import ok')"
```
Expected: `import ok` (all imports resolved; `main()` did not run). The live `--dry-run-only` / network sweep is deferred to the executing phase; the script is not exercised by the fast suite.

- [ ] **Step 4: Commit**

```bash
git add scripts/benchmark_evaluate_warm.py .gitignore
git commit -m "feat(scripts): Arc 6 warm benchmark harness (operator-run, live universe) (Arc 6 §8)"
```

---

## Task 11: Full suite + ruff + final verification

**Files:** none (verification only)

- [ ] **Step 1: Run the full fast suite on the branch HEAD**

Run: `python -m pytest -m "not slow" -q`
Expected: green (the pre-Arc-6 baseline + the new tests). Read the actual count; do NOT carry a prior number forward ([[feedback_no_false_green_claim]]). If any pre-existing weekly-refresh test went red from Task 3, it should already be fixed in Task 3's commit — if a straggler appears, fix it (monkeypatch `_full_refresh_stagger_enabled` to False in that test) before proceeding.

- [ ] **Step 2: Ruff**

Run: `ruff check swing/`
Expected: clean. Fix any `noqa` placement / unused-import issues introduced.

- [ ] **Step 3: Confirm the locks held (grep audit)**

Run these and eyeball:
- `git diff main --stat` — only `swing/config.py`, `swing/data/ohlcv_archive.py`, `swing/pipeline/runner.py`, `scripts/benchmark_evaluate_warm.py`, `.gitignore`, and the three test files changed. **No** `swing/trades/`, **no** `swing/data/repos/`, **no** `swing/data/migrations/`, **no** Shape-A function bodies (`write_window` / `resolve_ohlcv_window` / `_backward_compat_rename` / `normalize_legacy_dataframe`) touched.
- Confirm `read_or_fetch_archive`'s **public signature** (`ticker, *, end_date, cache_dir, archive_history_days`) is unchanged.
- Confirm `_write_archive_atomic` is still the only `.to_parquet`-to-final-path writer (the warm merges all funnel through it).
- Confirm schema is untouched: `git diff main -- swing/data/migrations/` is empty; v26 holds.

- [ ] **Step 4: No commit** — verification only. The plan is complete when the suite is green, ruff is clean, and the lock audit passes.

---

## Self-Review (spec coverage)

| Spec section | Task(s) |
|---|---|
| §3 architecture (`warm_archives_batch` signature, single-call, reuse write machinery) | 7 (assembly), 5-6 (machinery) |
| §4.1 cohort classification (exact predicates, single-anchor invariant) | 4 |
| §4.2 gap banding by `latest_stored` + deep-gap collapse + full-refresh window | 4 (classify), 7 (windows) |
| §4.3 chunk machine + validation ladder (a-d) + single-ticker remnant | 5 |
| §4.4 merge+write (gap no-meta / full-refresh meta) + `_write_archive_atomic` sole path | 6 |
| §5 stagger predicate (crc32 bucket, ≥13 ceiling, new/empty bypass) + kill-switch + single resolver + cache/restart note | 1 (config), 2 (predicate), 3 (resolver + swap) |
| §6 failure posture (per-ticker / whole-chunk / wholesale) + #27 + always-on telemetry | 5 (fetch fallback), 7 (assembly fallback), 9 (#27 + INFO log) |
| §7 phase-isolation carve-out | 11 (lock audit) + every task's file list |
| §8 data-content parity (headline guard) | 8 |
| §8 unit tests (cohort/banding/F6/whole-chunk/stagger/meta/remnant/strip) | 2,3,4,5,6,7 |
| §8 dry-run classifier (zero-fetch) | 7 (`dry_run=True`) |
| §8 benchmark (chunk sweep, deep-band separate, threads=False-first) | 10 |
| §10 open items (config mechanics / dry-run delivery / benchmark shape / parity mechanics) | Resolutions section + Tasks 1,3,7,8,10 |

**Placeholder scan:** the only deliberately-deferred specifics are (a) the `_step_evaluate` test fixture harness (Task 9 — must be copied from the existing pipeline test, which the engineer locates by grep) and (b) the benchmark's `load_universe` import (Task 10 — confirmed live at executing time). Both are flagged with executing-engineer notes and neither blocks a TDD task's red/green. No `TBD`/`TODO`/"add error handling" placeholders in implementation steps.

**Type consistency:** `WarmReport` fields (`cache_hit, gap, deep_gap, full_refresh, chunks_attempted, chunk_failures, fallback, wall_seconds, dry_run, degraded`) are used identically in Tasks 7 and 9. `_classify_warm_cohorts` returns the dict shape (`cache_hit/gap_bands/deep_gap/full_refresh`) consumed verbatim in Task 7. `_full_refresh_due(ticker, last_full_refresh, today_session, *, stagger_enabled)` signature is identical in Tasks 2, 3, 4. `_extract_ticker_subframe` / `_fetch_chunk` / `_merge_gap_subframe` / `_write_full_refresh_subframe` signatures match between definition (5,6) and use (7).

**Flagged for the executing phase / operator gate:**
- The §5 full-refresh cadence change (7-day → ≤13-day deep-history-correction staleness; recent bars unaffected) is an accepted, kill-switch-reversible tradeoff flagged for research-director awareness (spec §9).
- First-staggered-night catch-up wave: run the dry-run (`warm_archives_batch(..., dry_run=True)` via Task 10's `--dry-run-only`) BEFORE the gate night to preview full-refresh-cohort size; if alarming, flip `stagger_full_refresh=False` for that night (spec §5 rollout).
- `DEFAULT_CHUNK_SIZE` is pinned by Task 10's benchmark in the executing phase (spec §10 bullet 1).
- The ≤90s acceptance is verified on the operator-gate nightly via `pipeline_step_timings`, not in this cycle.
