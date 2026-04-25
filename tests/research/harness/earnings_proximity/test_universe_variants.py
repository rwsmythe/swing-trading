"""Unit tests for the diagnostic universe-variant loader.

Covers:
    - SPX+NDX returns the same tickers as ``swing.evaluation.rs.load_universe``.
    - Russell-3000 sanity check (≥2500 tickers) using an injected fetcher.
    - Cache hit (no fetcher invocation on second call when fresh).
    - Stale-cache refetch (file older than ``max_age_days`` triggers fetch).
    - iShares IWV CSV parser (skips preamble, extracts equity tickers, drops
      cash/derivative rows).

The fetcher is injected so tests do not require network. The production
default fetcher (a thin urllib wrapper) is used only at D4 run time.
"""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import pytest

from research.harness.earnings_proximity import universe_variants
from swing.evaluation.rs import load_universe

_RS_UNIVERSE_CSV = Path(__file__).resolve().parents[4] / "reference" / "rs-universe.csv"


_HEADER_COLS = (
    "Ticker,Name,Sector,Asset Class,Market Value,Weight (%),Notional Value,"
    "Quantity,Price,Location,Exchange,Currency,FX Rate,Market Currency,Accrual Date"
)


def _equity_row(ticker: str, sector: str = "Information Technology") -> str:
    return (
        f'"{ticker}","{ticker} CORP","{sector}","Equity",'
        f'"1.0","0.001","1.0","1.0","1.0","United States","NASDAQ","USD",'
        f'"1.00","USD","-"'
    )


_CASH_ROW = (
    '"USD","US DOLLAR","Cash and/or Derivatives","Cash","1000.00","0.001",'
    '"1000.00","1000.00","1.00","-","-","USD","1.00","USD","-"'
)
_FUTURES_ROW = (
    '"-","RUSSELL 3000 INDEX MINI FUT JUN 26","-","Futures","100.00","0.001",'
    '"100.00","1.00","100.00","-","-","USD","1.00","USD","-"'
)


def _ishares_csv_payload(
    tickers: list[str],
    *,
    header_date: str = "Apr 23, 2026",
    sectors: dict[str, str] | None = None,
) -> bytes:
    """Build a minimal iShares-shaped holdings CSV payload.

    ``sectors`` maps ticker → sector for per-row sector overrides; tickers
    not in the mapping default to "Information Technology".
    """
    sectors = sectors or {}
    lines = [
        "﻿iShares Russell 3000 ETF",
        f'Fund Holdings as of,"{header_date}"',
        'Inception Date,"May 22, 2000"',
        'Shares Outstanding,"46,300,000.00"',
        'Stock,"-"',
        'Bond,"-"',
        'Cash,"-"',
        'Other,"-"',
        "\xa0",  # iShares' separator row
        _HEADER_COLS,
    ]
    for t in tickers:
        lines.append(_equity_row(t, sectors.get(t, "Information Technology")))
    # Typical non-equity rows iShares includes (cash + derivative / futures).
    lines.append(_CASH_ROW)
    lines.append(_FUTURES_ROW)
    return "\r\n".join(lines).encode("utf-8")


# ----------------------------------------------------------------------------
# SPX+NDX
# ----------------------------------------------------------------------------


def test_spx_ndx_matches_rs_universe(tmp_path: Path):
    variant = universe_variants.load_universe_variant(
        "spx_ndx",
        cache_dir=tmp_path,
    )
    expected = load_universe(_RS_UNIVERSE_CSV)
    assert variant.name == "spx_ndx"
    assert variant.tickers == expected.tickers
    # SPX+NDX is sourced from the static rs-universe.csv — no network fetch,
    # version reflects the file's pragma.
    assert variant.version == expected.version
    assert variant.source_url is None
    assert variant.fetched_date is None


# ----------------------------------------------------------------------------
# Russell 3000 — sanity + cache hit + stale refetch
# ----------------------------------------------------------------------------


def test_russell_3000_returns_at_least_2500_tickers(tmp_path: Path):
    """≥2500 tickers — Russell 3000 typically has 3000-3050 active holdings."""
    fake_tickers = [f"T{i:04d}" for i in range(2600)]
    calls: list[str] = []

    def fetcher(url: str) -> bytes:
        calls.append(url)
        return _ishares_csv_payload(fake_tickers)

    variant = universe_variants.load_universe_variant(
        "russell_3000",
        cache_dir=tmp_path,
        fetcher=fetcher,
        today=lambda: date(2026, 4, 24),
    )
    assert variant.name == "russell_3000"
    assert len(variant.tickers) >= 2500
    # Cash + derivatives rows must be filtered out — only equity rows kept.
    assert "USD" not in variant.tickers
    # First fetch: exactly one network call.
    assert len(calls) == 1


def test_russell_3000_cache_hit_skips_fetcher(tmp_path: Path):
    fake_tickers = [f"T{i:04d}" for i in range(2600)]
    calls: list[str] = []

    def fetcher(url: str) -> bytes:
        calls.append(url)
        return _ishares_csv_payload(fake_tickers)

    today = date(2026, 4, 24)
    variant_first = universe_variants.load_universe_variant(
        "russell_3000",
        cache_dir=tmp_path,
        fetcher=fetcher,
        today=lambda: today,
    )
    variant_second = universe_variants.load_universe_variant(
        "russell_3000",
        cache_dir=tmp_path,
        fetcher=fetcher,
        today=lambda: today,
    )

    assert variant_first.tickers == variant_second.tickers
    # Second call must hit cache; total fetcher calls remains 1.
    assert len(calls) == 1


def test_russell_3000_stale_cache_refetches(tmp_path: Path):
    fake_tickers_old = [f"OLD{i:04d}" for i in range(2600)]
    fake_tickers_new = [f"NEW{i:04d}" for i in range(2600)]
    cursor = {"value": 0}

    def fetcher(url: str) -> bytes:
        cursor["value"] += 1
        if cursor["value"] == 1:
            return _ishares_csv_payload(fake_tickers_old)
        return _ishares_csv_payload(fake_tickers_new)

    # Initial fetch on day T0.
    today_t0 = date(2026, 4, 24)
    variant_first = universe_variants.load_universe_variant(
        "russell_3000",
        cache_dir=tmp_path,
        fetcher=fetcher,
        today=lambda: today_t0,
        max_age_days=30,
    )
    assert variant_first.tickers[0].startswith("OLD")
    assert cursor["value"] == 1

    # Same-day call: cache hit.
    universe_variants.load_universe_variant(
        "russell_3000",
        cache_dir=tmp_path,
        fetcher=fetcher,
        today=lambda: today_t0,
        max_age_days=30,
    )
    assert cursor["value"] == 1

    # 35 days later: stale, refetch.
    today_t1 = today_t0 + timedelta(days=35)
    variant_third = universe_variants.load_universe_variant(
        "russell_3000",
        cache_dir=tmp_path,
        fetcher=fetcher,
        today=lambda: today_t1,
        max_age_days=30,
    )
    assert variant_third.tickers[0].startswith("NEW")
    assert cursor["value"] == 2


def test_russell_3000_drops_cash_and_derivative_rows(tmp_path: Path):
    """The iShares CSV has Cash and Futures rows; loader keeps only Equity."""
    payload = _ishares_csv_payload(["AAPL", "MSFT", "NVDA"])
    variant = universe_variants.load_universe_variant(
        "russell_3000",
        cache_dir=tmp_path,
        fetcher=lambda url: payload,
        today=lambda: date(2026, 4, 24),
    )
    # AAPL/MSFT/NVDA only — USD cash row + futures row excluded.
    assert set(variant.tickers) == {"AAPL", "MSFT", "NVDA"}


# ----------------------------------------------------------------------------
# S&P 1500 fallback (uses iShares IVV+IJH+IJR; same parser; same cache contract)
# ----------------------------------------------------------------------------


def test_sp_1500_unions_three_etfs(tmp_path: Path):
    """S&P 1500 fallback unions IVV (S&P 500) + IJH (S&P 400) + IJR (S&P 600)."""
    # Build distinct payloads per URL.
    ivv = _ishares_csv_payload(["AAPL", "MSFT", "NVDA"])  # 3 tickers
    ijh = _ishares_csv_payload([f"M{i:03d}" for i in range(400)])  # 400 mid-caps
    ijr = _ishares_csv_payload([f"S{i:03d}" for i in range(600)])  # 600 small-caps

    def fetcher(url: str) -> bytes:
        if "IVV" in url:
            return ivv
        if "IJH" in url:
            return ijh
        if "IJR" in url:
            return ijr
        raise AssertionError(f"Unexpected URL: {url}")

    variant = universe_variants.load_universe_variant(
        "sp_1500",
        cache_dir=tmp_path,
        fetcher=fetcher,
        today=lambda: date(2026, 4, 24),
    )
    assert variant.name == "sp_1500"
    assert len(variant.tickers) == 1003  # 3 + 400 + 600
    assert "AAPL" in variant.tickers
    assert "M000" in variant.tickers
    assert "S000" in variant.tickers


# ----------------------------------------------------------------------------
# Sector-map extraction (used by D4 reporting on S&P 1500)
# ----------------------------------------------------------------------------


def test_parse_ishares_csv_with_sector_extracts_per_ticker_sector(tmp_path: Path):
    """parse_ishares_csv_with_sector returns (ticker, sector) pairs and skips non-equity rows."""
    payload = _ishares_csv_payload(
        ["AAPL", "MSFT", "JPM"],
        sectors={"AAPL": "Information Technology", "MSFT": "Information Technology", "JPM": "Financials"},
    )
    rows = universe_variants.parse_ishares_csv_with_sector(payload)
    mapping = dict(rows)
    assert mapping == {
        "AAPL": "Information Technology",
        "MSFT": "Information Technology",
        "JPM": "Financials",
    }
    # Cash + futures rows excluded as in the equity-only parser.
    assert "USD" not in mapping
    assert "-" not in mapping


def test_load_sp_1500_sector_map_unions_three_etfs_and_caches(tmp_path: Path):
    """load_sp_1500_sector_map fetches IVV/IJH/IJR, unions per-ticker sectors, and caches."""
    ivv = _ishares_csv_payload(["AAPL"], sectors={"AAPL": "Information Technology"})
    ijh = _ishares_csv_payload(["MID1"], sectors={"MID1": "Industrials"})
    ijr = _ishares_csv_payload(["SML1"], sectors={"SML1": "Health Care"})

    calls: list[str] = []

    def fetcher(url: str) -> bytes:
        calls.append(url)
        if "IVV" in url:
            return ivv
        if "IJH" in url:
            return ijh
        if "IJR" in url:
            return ijr
        raise AssertionError(f"Unexpected URL: {url}")

    sectors = universe_variants.load_sp_1500_sector_map(
        cache_dir=tmp_path,
        fetcher=fetcher,
        today=lambda: date(2026, 4, 25),
    )
    assert sectors == {
        "AAPL": "Information Technology",
        "MID1": "Industrials",
        "SML1": "Health Care",
    }
    assert len(calls) == 3  # one per sub-ETF

    # Second call: cache hit; fetcher must not be invoked again.
    sectors2 = universe_variants.load_sp_1500_sector_map(
        cache_dir=tmp_path,
        fetcher=fetcher,
        today=lambda: date(2026, 4, 25),
    )
    assert sectors2 == sectors
    assert len(calls) == 3


def test_load_sp_1500_sector_map_dedupe_keeps_first(tmp_path: Path):
    """When a ticker appears in more than one sub-ETF, the first sector wins (IVV → IJH → IJR)."""
    # AAPL appears in both IVV and IJH (artificial overlap for the test);
    # IVV's "Information Technology" should win.
    ivv = _ishares_csv_payload(["AAPL"], sectors={"AAPL": "Information Technology"})
    ijh = _ishares_csv_payload(["AAPL", "MID1"], sectors={"AAPL": "WRONG", "MID1": "Industrials"})
    ijr = _ishares_csv_payload(["SML1"], sectors={"SML1": "Health Care"})

    def fetcher(url: str) -> bytes:
        if "IVV" in url:
            return ivv
        if "IJH" in url:
            return ijh
        if "IJR" in url:
            return ijr
        raise AssertionError(f"Unexpected URL: {url}")

    sectors = universe_variants.load_sp_1500_sector_map(
        cache_dir=tmp_path,
        fetcher=fetcher,
        today=lambda: date(2026, 4, 25),
    )
    assert sectors["AAPL"] == "Information Technology"
    assert sectors["MID1"] == "Industrials"
    assert sectors["SML1"] == "Health Care"


# ----------------------------------------------------------------------------
# Unknown universe
# ----------------------------------------------------------------------------


def test_unknown_universe_raises(tmp_path: Path):
    with pytest.raises(ValueError, match="unknown"):
        universe_variants.load_universe_variant("not_a_universe", cache_dir=tmp_path)
