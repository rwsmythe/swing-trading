"""Generate golden fixtures: synthetic OHLCV CSVs + expected.yaml files.

Each CSV is a 260-bar daily OHLCV. Paired expected.yaml declares expected bucket.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import yaml

OUT = Path(__file__).parent


def _save(name: str, df: pd.DataFrame, expected: dict) -> None:
    df.to_csv(OUT / f"{name}.csv", index=True, index_label="Date")
    (OUT / f"{name}.expected.yaml").write_text(yaml.safe_dump(expected, sort_keys=False))


def _build_trend_frame(
    start_close: float = 10.0,
    step: float = 0.15,
    n: int = 260,
    range_pct: float = 0.03,
    tight_last_n: int = 0,
    tight_range_pct: float = 0.015,
    volume_low_from: int | None = None,
    low_vol: int = 500_000,
    high_vol: int = 3_000_000,
) -> pd.DataFrame:
    """Linear uptrend with configurable range and optional tightening at end."""
    closes = [start_close + i * step for i in range(n)]
    highs = [c * (1 + range_pct) for c in closes]
    lows = [c * (1 - range_pct) for c in closes]
    for i in range(tight_last_n):
        highs[-(i + 1)] = closes[-(i + 1)] * (1 + tight_range_pct)
        lows[-(i + 1)] = closes[-(i + 1)] * (1 - tight_range_pct)
    if volume_low_from is not None:
        volumes = [high_vol] * volume_low_from + [low_vol] * (n - volume_low_from)
    else:
        volumes = [high_vol] * n
    idx = pd.bdate_range(end="2026-04-17", periods=n)
    return pd.DataFrame(
        {"Open": closes, "High": highs, "Low": lows, "Close": closes, "Volume": volumes},
        index=idx,
    )


def aplus_clean_vcp() -> None:
    """Strong 260-bar uptrend, tight 2-day consolidation at end, contracting volume.

    All 8 TT pass (assuming ticker RS ranks top). All 9 VCP pass.
    Bucket: aplus.
    """
    df = _build_trend_frame(
        start_close=10.0, step=0.15, n=260,
        range_pct=0.03, tight_last_n=2, tight_range_pct=0.015,
        volume_low_from=220, low_vol=500_000, high_vol=3_000_000,
    )
    _save("aplus_clean_vcp", df, {
        "expected_bucket": "aplus",
        "notes": "Strong linear uptrend; last 2 bars tight; volume contracts. All criteria pass (RS set high in test).",
    })


def rs_low_universe() -> None:
    """Same shape as aplus but RS forced low -> TT8 fails. Still aplus (TT8 is allowed miss)."""
    df = _build_trend_frame(
        start_close=10.0, step=0.15, n=260,
        range_pct=0.03, tight_last_n=2, tight_range_pct=0.015,
        volume_low_from=220, low_vol=500_000, high_vol=3_000_000,
    )
    _save("rs_low_universe", df, {
        "expected_bucket": "aplus",
        "notes": "Same uptrend as aplus_clean_vcp but RS forced to lowest rank. TT8 fails, other 7 pass. Bucket still aplus (TT >= 7).",
    })


def vcp_fail_no_tightness() -> None:
    """Same uptrend but NO tightening at end -> tightness fails. Bucket: watch."""
    df = _build_trend_frame(
        start_close=10.0, step=0.15, n=260,
        range_pct=0.03, tight_last_n=0,
        volume_low_from=220, low_vol=500_000, high_vol=3_000_000,
    )
    _save("vcp_fail_no_tightness", df, {
        "expected_bucket": "watch",
        "notes": "Trend template passes; VCP tightness fails (no tight bars at end). 1 VCP fail -> watch.",
    })


def tt_fail_flat_200ma() -> None:
    """Flat closes -> 200MA flat, TT3 fails (and others)."""
    closes = [50.0] * 260
    idx = pd.bdate_range(end="2026-04-17", periods=260)
    df = pd.DataFrame(
        {"Open": closes, "High": [50.5] * 260, "Low": [49.5] * 260,
         "Close": closes, "Volume": [1_000_000] * 260},
        index=idx,
    )
    _save("tt_fail_flat_200ma", df, {
        "expected_bucket": "skip",
        "notes": "Flat closes - 200MA is flat (TT3 fail), multiple other TTs fail. Not enough TT passes -> skip.",
    })


if __name__ == "__main__":
    aplus_clean_vcp()
    rs_low_universe()
    vcp_fail_no_tightness()
    tt_fail_flat_200ma()
    print("Generated 4 golden fixtures")
