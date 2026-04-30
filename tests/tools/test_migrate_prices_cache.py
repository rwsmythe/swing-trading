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
    _write_legacy_parquet(
        cache, "AAPL", 120, date(2026, 4, 20),
        [(date(2026, 4, d), 100.0, 100.0, 100.0, 100.0, 1000) for d in range(15, 21)],
    )
    _write_legacy_parquet(
        cache, "AAPL", 120, date(2026, 4, 25),
        [(date(2026, 4, d), 200.0, 200.0, 200.0, 200.0, 2000) for d in range(18, 26)],
    )

    mig.run(cache_dir=cache)

    consolidated = pd.read_parquet(cache / "AAPL.parquet")
    assert len(consolidated) == 11
    overlap_close = consolidated.loc[pd.Timestamp("2026-04-19"), "Close"]
    assert overlap_close == 200.0, (
        f"overlap row should have come from newer as_of file (Close=200.0), "
        f"got {overlap_close} — duplicate-date resolution is broken"
    )
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
    assert list(cache.glob("*.tmp")) == []


def test_atomic_replace_preserves_prior_archive_on_simulated_crash(tmp_path, monkeypatch):
    """If os.replace raises mid-migration for a given ticker, the prior {TICKER}.parquet
    (if any) is unchanged AND legacy files are NOT deleted (rolled back for that ticker)."""
    from swing.tools import migrate_prices_cache as mig

    cache = tmp_path
    pre_existing = pd.DataFrame(
        [(pd.Timestamp("2026-04-01"), 99.0, 99.0, 99.0, 99.0, 999)],
        columns=["date", "Open", "High", "Low", "Close", "Volume"],
    ).set_index("date")
    pre_existing.to_parquet(cache / "TSLA.parquet")
    legacy_path = _write_legacy_parquet(
        cache, "TSLA", 120, date(2026, 4, 25),
        [(date(2026, 4, 15), 1.0, 1.0, 1.0, 1.0, 1)],
    )

    real_replace = mig.os.replace

    def crashing_replace(src, dst):
        if str(dst).endswith("TSLA.parquet"):
            raise OSError("simulated crash mid-rename")
        return real_replace(src, dst)

    monkeypatch.setattr(mig.os, "replace", crashing_replace)

    with pytest.raises(OSError, match="simulated crash"):
        mig.run(cache_dir=cache)

    survived = pd.read_parquet(cache / "TSLA.parquet")
    assert survived.loc[pd.Timestamp("2026-04-01"), "Close"] == 99.0, (
        "prior archive was clobbered despite the rename crashing"
    )
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

    assert (cache / "AMZN.parquet").stat().st_mtime == mtime_before_parquet
    assert (cache / "AMZN.meta.json").stat().st_mtime == mtime_before_meta


def test_idempotency_resumes_from_interrupted_run(tmp_path):
    """If a prior run was interrupted (per-ticker archive exists AND legacy files
    still exist for that ticker), re-running converges: legacy + existing
    re-unioned, rewritten, legacy deleted."""
    from swing.tools import migrate_prices_cache as mig

    cache = tmp_path
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
    assert pd.Timestamp("2026-04-15") in consolidated.index
    assert pd.Timestamp("2026-04-18") in consolidated.index
    assert not legacy.exists()
    meta = json.loads((cache / "NVDA.meta.json").read_text())
    assert meta["last_full_refresh_date"] == "2026-04-20"


def test_unrelated_files_are_not_touched(tmp_path):
    """Files that don't match the legacy pattern (`*_*d_asof-*.parquet`) are
    left untouched. Prevents accidental clobber of operator notes or other
    artifacts that happen to live in the cache dir."""
    from swing.tools import migrate_prices_cache as mig

    cache = tmp_path
    (cache / "README.txt").write_text("operator notes")
    (cache / "research-notes.parquet").write_text("not a legacy file")

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

    assert legacy_path.exists(), (
        "legacy file deleted before meta-write succeeded — partial-write violation"
    )
    assert list(cache.glob("*.parquet.tmp")) == []
    assert list(cache.glob("*.meta.json.tmp")) == []
