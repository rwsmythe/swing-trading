"""Provenance manifest tests.

Covers schema shape, git-state capture, write/read round-trip, and the
graceful-fallback behavior when ``git`` is unavailable.
"""
from __future__ import annotations

import json
from datetime import date
from pathlib import Path


def _cache_stats():
    from research.harness.earnings_proximity.provenance import CacheStats

    return CacheStats(ohlcv_hits=4, ohlcv_misses=2, earnings_hits=3, earnings_misses=1)


def test_manifest_includes_required_minimum_fields(tmp_path):
    """V2.1 §IV.C minimum provenance — all listed fields must be populated."""
    from research.harness.earnings_proximity.provenance import (
        RunManifest,
        build_manifest,
    )

    repo_root = Path(__file__).resolve().parents[4]  # project root
    manifest = build_manifest(
        repo_root=repo_root,
        universe_version_hash="deadbeef" * 8,
        window_start=date(2024, 1, 2),
        window_end=date(2026, 1, 2),
        trading_days=504,
        tickers=500,
        variants=(0, 3, 5, 7, 10),
        cache_stats=_cache_stats(),
        absent_data_count=12,
        dropped_signal_count=37,
    )
    assert isinstance(manifest, RunManifest)

    for field in (
        "git_sha",
        "git_dirty",
        "run_ts",
        "yfinance_version",
        "universe_version_hash",
        "window_start",
        "window_end",
        "trading_days",
        "tickers",
        "variants",
        "cache_stats",
        "absent_data_count",
        "dropped_signal_count",
        "study_design_commit",
    ):
        assert hasattr(manifest, field)

    # Values plumbed through correctly.
    assert manifest.trading_days == 504
    assert manifest.tickers == 500
    assert manifest.variants == (0, 3, 5, 7, 10)
    assert manifest.absent_data_count == 12
    assert manifest.dropped_signal_count == 37
    # git_sha is 40 hex chars or empty-string fallback.
    assert manifest.git_sha == "" or len(manifest.git_sha) == 40


def test_manifest_write_read_roundtrip(tmp_path):
    from research.harness.earnings_proximity.provenance import (
        build_manifest,
        write_manifest,
    )

    repo_root = Path(__file__).resolve().parents[4]
    manifest = build_manifest(
        repo_root=repo_root,
        universe_version_hash="abcd",
        window_start=date(2024, 1, 2),
        window_end=date(2024, 1, 5),
        trading_days=3,
        tickers=2,
        variants=(0, 5),
        cache_stats=_cache_stats(),
        absent_data_count=0,
        dropped_signal_count=0,
    )
    out_path = tmp_path / "run_manifest.json"
    write_manifest(manifest, out_path)

    payload = json.loads(out_path.read_text())
    assert payload["trading_days"] == 3
    assert payload["tickers"] == 2
    assert payload["variants"] == [0, 5]  # JSON has no tuple
    assert payload["cache_stats"]["ohlcv_hits"] == 4
    assert payload["universe_version_hash"] == "abcd"


def test_manifest_handles_missing_git_gracefully(tmp_path, monkeypatch):
    """If git is absent (OSError on subprocess.run), manifest fields fall back
    to empty strings rather than crashing."""
    from research.harness.earnings_proximity import provenance as mod

    def fake_run(*a, **kw):
        raise OSError("git not found")

    monkeypatch.setattr(mod.subprocess, "run", fake_run)

    manifest = mod.build_manifest(
        repo_root=tmp_path,
        universe_version_hash="x",
        window_start=date(2024, 1, 2),
        window_end=date(2024, 1, 5),
        trading_days=3,
        tickers=2,
        variants=(0,),
        cache_stats=mod.CacheStats(),
        absent_data_count=0,
        dropped_signal_count=0,
    )
    assert manifest.git_sha == ""
    assert manifest.git_dirty is False
    assert manifest.study_design_commit == ""
