"""Shared NaN sanitizer for Phase 13 T2.SB3+ detectors.

Per dispatch brief Section 1.1 #3 forward-binding lesson and recon
Section 7.4: T2.SB3 detectors (VCP, flat base, cup-with-handle) and the
upcoming T2.SB4 detectors (high-tight-flag, double-bottom-W) consume
real OHLCV archives that can carry NaN holiday-adjacent rows. Foundation
primitives in ``swing/patterns/foundation.py`` reject NaN at entry; the
detectors must therefore sanitize bars before invoking foundation
primitives.

LOCKs:
- L1: pure function; no I/O, no logging.
- L2: ZERO DB writes (this module never opens a connection).
- L5: ASCII-only docstring and error-message text.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

_OHLCV_COLUMNS: tuple[str, ...] = ("Open", "High", "Low", "Close", "Volume")


def sanitize_bars(bars: pd.DataFrame) -> pd.DataFrame:
    """Validate OHLCV bars for NaN and return the (unchanged) frame.

    The detectors share one entry-point contract: bars MUST NOT contain
    NaN in any present OHLCV column. This helper raises ``ValueError``
    with a precise error string if any present OHLCV column carries
    non-finite values; otherwise it returns ``bars`` unchanged.

    Only columns actually present on the input frame are checked; absent
    columns are silently skipped (some primitives need only ``Close``,
    others need ``Volume``). Per detectors' foundation-primitive consumer
    list (recon Section 7.1 / 7.2 / 7.3), at minimum ``Close``, ``High``,
    ``Low``, and ``Volume`` MUST be present and finite for V1.
    """
    if bars is None:
        raise ValueError("sanitize_bars: bars must not be None")
    for col in _OHLCV_COLUMNS:
        if col not in bars.columns:
            continue
        arr = bars[col].astype(float).to_numpy()
        if not np.all(np.isfinite(arr)):
            raise ValueError(
                f"sanitize_bars: bars[{col!r}] contains NaN or non-finite "
                f"values; caller must drop or impute before invoking the "
                f"detector"
            )
    return bars
