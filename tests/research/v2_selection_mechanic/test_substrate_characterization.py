"""Substrate characterization metric tests on synthetic OHLCV fixtures."""
from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from research.harness.v2_selection_mechanic.substrate_characterization import (
    UNKNOWN_SECTOR,
    AsofDateMissingError,
    CacheMissError,
    aggregate_cohort_metrics,
    compute_90d_return_pct,
    compute_52w_high_proximity_pct,
    compute_atr_pct_20d,
    compute_cohort_characterization,
    compute_per_ticker_metrics,
    load_sector_map_from_finviz_csv,
    read_legacy_archive,
    resolve_sector,
    PerTickerMetrics,
)


def _synthetic_df(start: date, n_days: int, base_price: float = 100.0) -> pd.DataFrame:
    """Build a deterministic OHLCV fixture: linear ramp + constant 1% range."""
    dates = pd.bdate_range(start=pd.Timestamp(start), periods=n_days)
    closes = base_price + np.arange(n_days, dtype=float)
    highs = closes + 0.5
    lows = closes - 0.5
    opens = closes - 0.25
    volumes = np.full(n_days, 1000000, dtype=int)
    df = pd.DataFrame(
        {
            "Open": opens,
            "High": highs,
            "Low": lows,
            "Close": closes,
            "Volume": volumes,
        },
        index=dates,
    )
    df.index.name = "Date"
    return df


# ----- read_legacy_archive (gotcha #28 + brief Sec 6(d) discipline) -----


def test_read_legacy_archive_raises_cache_miss_error(tmp_path: Path) -> None:
    """Missing archive -> CacheMissError (FileNotFoundError subclass)."""
    with pytest.raises(CacheMissError) as exc_info:
        read_legacy_archive("NOTEXIST", cache_dir=tmp_path)
    assert "Operator pre-flight refresh required" in str(exc_info.value)
    # FileNotFoundError compatibility (gotcha #28 structural defense)
    assert isinstance(exc_info.value, FileNotFoundError)


def test_read_legacy_archive_loads_canonical_shape(tmp_path: Path) -> None:
    """Roundtrip: write parquet, read back, schema matches."""
    df = _synthetic_df(date(2025, 1, 1), 100)
    (tmp_path / "ABC.parquet").write_bytes(b"")  # placeholder; overwrite below
    df.to_parquet(tmp_path / "ABC.parquet")
    loaded = read_legacy_archive("abc", cache_dir=tmp_path)  # lowercase test
    assert list(loaded.columns) == ["Open", "High", "Low", "Close", "Volume"]
    assert len(loaded) == 100


def test_read_legacy_archive_squeezes_multiindex_columns(tmp_path: Path) -> None:
    """yfinance group_by='column' MultiIndex columns get squeezed defensively."""
    df = _synthetic_df(date(2025, 1, 1), 100)
    df.columns = pd.MultiIndex.from_tuples(
        [("Open", "ABC"), ("High", "ABC"), ("Low", "ABC"), ("Close", "ABC"), ("Volume", "ABC")]
    )
    df.to_parquet(tmp_path / "ABC.parquet")
    loaded = read_legacy_archive("ABC", cache_dir=tmp_path)
    # Should be single-level columns post-squeeze
    assert not isinstance(loaded.columns, pd.MultiIndex)
    assert "Close" in loaded.columns


# ----- 90-day return -----


def test_90d_return_known_values() -> None:
    """Linear ramp 100 -> 200 over 100 BD; asof at index 99; 90 BD back = index 9 = 109; return = (200-109)/109."""
    df = _synthetic_df(date(2025, 1, 1), 100, base_price=100.0)
    asof = df.index[-1].date()
    asof_close = float(df["Close"].iloc[-1])
    prior_close = float(df["Close"].iloc[-91])
    expected = (asof_close - prior_close) / prior_close * 100.0
    actual = compute_90d_return_pct(df, asof)
    assert actual is not None
    assert abs(actual - expected) < 1e-9


def test_90d_return_insufficient_history_returns_none() -> None:
    """Fewer than 91 bars -> None."""
    df = _synthetic_df(date(2025, 1, 1), 50)
    asof = df.index[-1].date()
    assert compute_90d_return_pct(df, asof) is None


def test_90d_return_distinguishes_pre_fix_vs_post_fix_arithmetic() -> None:
    """Verify the test arithmetic distinguishes correct vs off-by-one denominator.

    Per cumulative `feedback_verify_regression_test_arithmetic`: a test
    that asserts `return == 100.0` should NOT pass if the implementation
    used the asof_close as the denominator (the buggy form would yield
    a different value).
    """
    df = _synthetic_df(date(2025, 1, 1), 100, base_price=100.0)
    asof = df.index[-1].date()
    correct = compute_90d_return_pct(df, asof)
    # Correct: (199 - 109) / 109 * 100 = ~82.57%
    # Buggy (denominator = asof_close): (199 - 109) / 199 * 100 = ~45.23%
    # Discriminating: the absolute difference between the two is > 30 pct
    asof_close = float(df["Close"].iloc[-1])
    prior_close = float(df["Close"].iloc[-91])
    buggy = (asof_close - prior_close) / asof_close * 100.0
    assert abs(correct - buggy) > 30.0


# ----- ATR% -----


def test_atr_pct_known_values() -> None:
    """Constant 1.0 H-L range; ATR ~ 1.0; ATR% = 1/close_at_asof * 100."""
    df = _synthetic_df(date(2025, 1, 1), 100, base_price=100.0)
    asof = df.index[-1].date()
    asof_close = float(df["Close"].iloc[-1])
    atr_pct = compute_atr_pct_20d(df, asof)
    assert atr_pct is not None
    # With constant 1.0 H-L range + ramp +1/bar, ATR is ~ 1.0 to 1.5
    # (range_hpc + range_lpc include the +1 close-to-close move).
    # We assert a reasonable bound, not a tight equality, to keep the
    # test deterministic against the constant-ramp fixture without
    # over-specifying float arithmetic.
    expected_range_low = (1.0 / asof_close) * 100.0
    expected_range_high = (2.0 / asof_close) * 100.0
    assert expected_range_low < atr_pct < expected_range_high


def test_atr_pct_insufficient_history_returns_none() -> None:
    df = _synthetic_df(date(2025, 1, 1), 5)
    asof = df.index[-1].date()
    assert compute_atr_pct_20d(df, asof) is None


# ----- 52w high proximity -----


def test_52w_proximity_at_high_returns_small_positive() -> None:
    """At the all-time high in the fixture, proximity is small positive."""
    df = _synthetic_df(date(2025, 1, 1), 300, base_price=100.0)
    asof = df.index[-1].date()
    prox = compute_52w_high_proximity_pct(df, asof)
    assert prox is not None
    # All-time high (last bar's High = close+0.5) is the trailing 52w high;
    # close is High - 0.5, so proximity = 0.5 / High * 100 -- small positive
    assert 0 < prox < 1.0


def test_52w_proximity_after_drawdown_known_values() -> None:
    """Build a fixture with a known 52w high; close is half that; proximity ~= 50%."""
    df = _synthetic_df(date(2025, 1, 1), 300, base_price=100.0)
    # Force a known high then drawdown
    df.loc[df.index[200], "High"] = 1000.0  # 52w high inside trailing window
    df.loc[df.index[-1], "Close"] = 500.0  # close at half the high
    asof = df.index[-1].date()
    prox = compute_52w_high_proximity_pct(df, asof)
    assert prox is not None
    assert abs(prox - 50.0) < 1e-9


def test_52w_proximity_insufficient_history_returns_none() -> None:
    """Codex R1 MAJOR #1 fix discriminator: <252 BD history -> None.

    Pre-fix returned a numeric value computed from partial-archive
    trailing-window max, conflating short histories with true 52-week
    lookbacks. Post-fix requires len(sliced) >= 252.
    """
    df = _synthetic_df(date(2025, 1, 1), 10, base_price=100.0)
    asof = df.index[-1].date()
    assert compute_52w_high_proximity_pct(df, asof) is None
    # Boundary: 251 bars still insufficient
    df = _synthetic_df(date(2025, 1, 1), 251, base_price=100.0)
    asof = df.index[-1].date()
    assert compute_52w_high_proximity_pct(df, asof) is None
    # 252 bars sufficient
    df = _synthetic_df(date(2024, 1, 1), 252, base_price=100.0)
    asof = df.index[-1].date()
    assert compute_52w_high_proximity_pct(df, asof) is not None


# ----- Sector resolution -----


def test_resolve_sector_unknown_when_no_map() -> None:
    assert resolve_sector("ABC") == UNKNOWN_SECTOR


def test_resolve_sector_returns_mapped_value() -> None:
    m = {"ABC": "Technology"}
    assert resolve_sector("ABC", finviz_sector_map=m) == "Technology"
    assert resolve_sector("abc", finviz_sector_map=m) == "Technology"  # case-insens


def test_resolve_sector_unknown_for_unmapped() -> None:
    m = {"ABC": "Technology"}
    assert resolve_sector("DEF", finviz_sector_map=m) == UNKNOWN_SECTOR


def test_load_sector_map_from_finviz_csv(tmp_path: Path) -> None:
    csv_path = tmp_path / "finviz5May2026.csv"
    csv_path.write_text(
        "No.,Ticker,Sector,Industry,Country,Price,Change,Average Volume,"
        "Relative Volume,Average True Range,52-Week High,52-Week Low,Market Cap\n"
        "1,ABC,Technology,Software,USA,100,0.5,1000000,1.0,2.5,150,50,5000000\n"
        "2,DEF,Healthcare,Pharma,USA,50,1.0,500000,2.0,1.5,80,30,2000000\n",
        encoding="utf-8",
    )
    m = load_sector_map_from_finviz_csv(csv_path)
    assert m == {"ABC": "Technology", "DEF": "Healthcare"}


def test_load_sector_map_missing_file_returns_empty(tmp_path: Path) -> None:
    m = load_sector_map_from_finviz_csv(tmp_path / "nope.csv")
    assert m == {}


# ----- Per-ticker + cohort aggregation -----


def test_per_ticker_metrics_against_fixture(tmp_path: Path) -> None:
    df = _synthetic_df(date(2024, 1, 1), 400, base_price=100.0)
    df.to_parquet(tmp_path / "ABC.parquet")
    asof = df.index[-1].date()
    metrics = compute_per_ticker_metrics(
        "ABC", asof, cache_dir=tmp_path
    )
    assert metrics.ticker == "ABC"
    assert metrics.asof_date == asof
    assert metrics.return_90d_pct is not None
    assert metrics.atr_pct_20d is not None
    assert metrics.high_52w_proximity_pct is not None
    assert metrics.sector == UNKNOWN_SECTOR


def test_compute_cohort_characterization_aggregates(tmp_path: Path) -> None:
    """Plant 3 ticker archives + compute cohort metrics."""
    for t, base in [("AAA", 100), ("BBB", 200), ("CCC", 300)]:
        df = _synthetic_df(date(2024, 1, 1), 400, base_price=float(base))
        df.to_parquet(tmp_path / f"{t}.parquet")
    asof = pd.bdate_range(start=pd.Timestamp(date(2024, 1, 1)), periods=400)[-1].date()
    pairs = [("AAA", asof), ("BBB", asof), ("CCC", asof)]
    sector_map = {"AAA": "Tech", "BBB": "Tech", "CCC": "Energy"}
    per_ticker, aggregate = compute_cohort_characterization(
        "test_cohort",
        pairs,
        cache_dir=tmp_path,
        finviz_sector_map=sector_map,
    )
    assert len(per_ticker) == 3
    assert aggregate.cohort_label == "test_cohort"
    assert aggregate.unique_ticker_count == 3
    assert aggregate.unique_ticker_asof_count == 3
    assert aggregate.sector_counts == {"Tech": 2, "Energy": 1}
    assert aggregate.return_90d_pct_median is not None
    assert aggregate.atr_pct_20d_median is not None
    assert aggregate.high_52w_proximity_pct_median is not None


def test_aggregate_cohort_metrics_empty() -> None:
    """Empty per_ticker -> aggregate with None medians + empty sector_counts."""
    agg = aggregate_cohort_metrics("empty", [])
    assert agg.unique_ticker_count == 0
    assert agg.unique_ticker_asof_count == 0
    assert agg.sector_counts == {}
    assert agg.return_90d_pct_median is None
    assert agg.return_90d_pct_iqr is None


def test_compute_cohort_characterization_raises_on_cache_miss(tmp_path: Path) -> None:
    """One ticker present + one missing -> CacheMissError on the missing one."""
    df = _synthetic_df(date(2024, 1, 1), 400, base_price=100.0)
    df.to_parquet(tmp_path / "AAA.parquet")
    asof = df.index[-1].date()
    pairs = [("AAA", asof), ("MISSING", asof)]
    with pytest.raises(CacheMissError):
        compute_cohort_characterization("test", pairs, cache_dir=tmp_path)


# ----- Codex R3 MAJOR #3 fix: strict asof_date presence check -----


def test_compute_per_ticker_metrics_raises_on_asof_not_in_index(tmp_path: Path) -> None:
    """Codex R3 MAJOR #3 fix discriminator: asof_date NOT in archive
    index -> AsofDateMissingError.

    Pre-fix: _slice_at_or_before silently substituted prior bar; metrics
    were labeled with requested asof but computed from a different bar's
    close (asof contract violation; data-integrity gap masked).
    Post-fix: strict guard requires asof in archive index.
    """
    df = _synthetic_df(date(2024, 1, 1), 400, base_price=100.0)
    df.to_parquet(tmp_path / "ABC.parquet")
    # Pick a date that's NOT in the index (e.g., a weekend or future date)
    not_in_index = date(2099, 1, 1)
    with pytest.raises(AsofDateMissingError, match="not present in OHLCV archive"):
        compute_per_ticker_metrics("ABC", not_in_index, cache_dir=tmp_path)


def test_compute_per_ticker_metrics_accepts_asof_in_index(tmp_path: Path) -> None:
    """An asof_date present in the archive index proceeds normally."""
    df = _synthetic_df(date(2024, 1, 1), 400, base_price=100.0)
    df.to_parquet(tmp_path / "ABC.parquet")
    asof = df.index[100].date()  # Pick a known index date
    metrics = compute_per_ticker_metrics("ABC", asof, cache_dir=tmp_path)
    assert metrics.asof_date == asof


# ----- Codex R4 MAJOR #1 fix: strict asof at primitive boundaries -----


def test_compute_90d_return_pct_raises_on_asof_not_in_index() -> None:
    """Codex R4 MAJOR #1: primitive enforces asof-in-index strictly."""
    df = _synthetic_df(date(2024, 1, 1), 400)
    with pytest.raises(AsofDateMissingError, match="not present"):
        compute_90d_return_pct(df, date(2099, 1, 1))


def test_compute_atr_pct_20d_raises_on_asof_not_in_index() -> None:
    df = _synthetic_df(date(2024, 1, 1), 400)
    with pytest.raises(AsofDateMissingError, match="not present"):
        compute_atr_pct_20d(df, date(2099, 1, 1))


def test_compute_52w_proximity_raises_on_asof_not_in_index() -> None:
    df = _synthetic_df(date(2024, 1, 1), 400)
    with pytest.raises(AsofDateMissingError, match="not present"):
        compute_52w_high_proximity_pct(df, date(2099, 1, 1))


def test_primitive_strict_asof_distinguishes_weekend_from_business_day() -> None:
    """Saturday adjacent to a business-day fixture -> raise.

    Pre-fix: Saturday silently substituted prior Friday's close; metric
    labeled with Sat but computed from Fri. Post-fix: raise.
    """
    df = _synthetic_df(date(2024, 1, 1), 400)
    # df.index ends on a business day; find adjacent Saturday
    last_bd = df.index[-1].date()
    # Saturday is 1-2 calendar days after last bd depending on weekday
    saturday = last_bd + timedelta(days=(5 - last_bd.weekday()) % 7 or 7)
    while saturday.weekday() != 5:  # find next Saturday
        saturday = saturday + timedelta(days=1)
    # Ensure Saturday is NOT in the bdate-range index
    assert saturday not in {d.date() for d in df.index}
    with pytest.raises(AsofDateMissingError):
        compute_90d_return_pct(df, saturday)
