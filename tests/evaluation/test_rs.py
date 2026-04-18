"""Tests for swing.evaluation.rs."""
from __future__ import annotations

from pathlib import Path

import pytest

from swing.evaluation.rs import compute_rs, load_universe, universe_version_hash


def _write_universe(path: Path, tickers: list[str], version: str = "2026-04-17-1") -> None:
    path.write_text(
        f"# version: {version}\n# source: test\n# columns: ticker\nticker\n"
        + "\n".join(tickers)
        + "\n",
        encoding="utf-8",
    )


def test_load_universe_skips_comments(tmp_path: Path):
    u = tmp_path / "u.csv"
    _write_universe(u, ["AAPL", "MSFT", "GOOG"])
    result = load_universe(u)
    assert result.tickers == ("AAPL", "GOOG", "MSFT")  # sorted
    assert result.version == "2026-04-17-1"


def test_universe_version_hash_stable(tmp_path: Path):
    u = tmp_path / "u.csv"
    _write_universe(u, ["AAPL", "MSFT"])
    h1 = universe_version_hash(u)
    h2 = universe_version_hash(u)
    assert h1 == h2
    assert len(h1) == 64  # sha256 hex


def test_compute_rs_universe_method():
    """For a ticker in the universe, rank is percentile vs all universe returns."""
    returns_12w = {
        "AAPL": 0.10,  # our target
        "MSFT": 0.05,
        "GOOG": 0.15,
        "META": 0.20,
        "NVDA": 0.25,
    }
    universe = ("AAPL", "GOOG", "META", "MSFT", "NVDA")
    spy_return = 0.08

    result = compute_rs("AAPL", returns_12w, universe, spy_return=spy_return)
    assert result.method == "universe"
    # AAPL at 0.10 is 2nd lowest of 5 = 25th percentile
    assert 0 <= result.rank < 50
    assert result.return_vs_spy == pytest.approx(0.10 - 0.08)


def test_compute_rs_fallback_for_outside_universe():
    returns_12w = {"NEWCO": 0.30}
    universe = ("AAPL", "MSFT")
    result = compute_rs("NEWCO", returns_12w, universe, spy_return=0.08)
    assert result.method == "fallback_spy"
    assert result.rank is None
    assert result.return_vs_spy == pytest.approx(0.22)


def test_compute_rs_unavailable_when_no_return_data():
    result = compute_rs("XYZ", {}, ("AAPL",), spy_return=0.08)
    assert result.method == "unavailable"
    assert result.rank is None
    assert result.return_vs_spy is None
