"""Phase 13 T2.SB3 Codex R1 Minor #1 - tests for shared sanitize_bars helper.

Per Codex R1 Minor #1: ``sanitize_bars`` documented that High/Low/Close/
Volume MUST be present, but the implementation silently skipped missing
columns. The detectors would then fail later with less intentional
``KeyError``s. The fix raises a precise ValueError at sanitize_bars entry
when any required column is missing.

LOCKs honored:
- L1: pure function; no I/O.
- L2: ZERO DB writes.
- L5: ASCII-only.
"""
from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from swing.patterns._sanitize import sanitize_bars


def _bars_full(n: int = 20) -> pd.DataFrame:
    idx = pd.DatetimeIndex(
        [pd.Timestamp("2025-01-01") + pd.Timedelta(days=i) for i in range(n)]
    )
    return pd.DataFrame(
        {
            "Open": np.full(n, 10.0),
            "High": np.full(n, 10.5),
            "Low": np.full(n, 9.5),
            "Close": np.full(n, 10.0),
            "Volume": np.full(n, 1_000_000.0),
        },
        index=idx,
    )


def test_sanitize_bars_raises_on_missing_required_column() -> None:
    """sanitize_bars MUST raise ValueError naming the missing column(s)
    when High / Low / Close / Volume is absent.
    """
    bars = _bars_full().drop(columns=["High"])
    with pytest.raises(ValueError) as exc_info:
        sanitize_bars(bars)
    msg = str(exc_info.value)
    assert "High" in msg
    assert "missing" in msg.lower()


def test_sanitize_bars_raises_on_missing_volume_column() -> None:
    """Volume is also REQUIRED (consumed by volume primitive)."""
    bars = _bars_full().drop(columns=["Volume"])
    with pytest.raises(ValueError) as exc_info:
        sanitize_bars(bars)
    assert "Volume" in str(exc_info.value)


def test_sanitize_bars_accepts_frame_without_open_column() -> None:
    """Open is NOT in the required set (no consumer reads it in V1);
    sanitize_bars should accept a frame missing Open as long as
    High/Low/Close/Volume are present + finite.
    """
    bars = _bars_full().drop(columns=["Open"])
    # Must not raise.
    sanitize_bars(bars)


def test_sanitize_bars_accepts_complete_finite_frame() -> None:
    """Happy path: all required columns present + finite -> no raise,
    returns the frame unchanged.
    """
    bars = _bars_full()
    out = sanitize_bars(bars)
    assert out is bars
