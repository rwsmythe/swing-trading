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

# Required-presence subset per detectors' foundation-primitive consumer
# list (recon Section 7.1 / 7.2 / 7.3). The detectors invoke smoothing /
# extrema / volume primitives that read High, Low, Close, Volume; Open
# is optional (no consumer reads it in V1).
_REQUIRED_COLUMNS: tuple[str, ...] = ("High", "Low", "Close", "Volume")


def sanitize_bars(bars: pd.DataFrame) -> pd.DataFrame:
    """Validate OHLCV bars for presence + NaN and return the frame.

    The detectors share one entry-point contract:
      (a) ``High``, ``Low``, ``Close``, ``Volume`` MUST all be present.
      (b) Every present OHLCV column MUST NOT contain NaN or other
          non-finite values.

    Raises ``ValueError`` with a precise error string when either
    contract is violated; otherwise returns ``bars`` unchanged.

    Codex R1 Minor #1: the original docstring said the columns "MUST be
    present" but the implementation silently skipped missing columns,
    pushing the failure downstream as a less-intentional ``KeyError``
    inside the detector. Validate at entry instead.
    """
    if bars is None:
        raise ValueError("sanitize_bars: bars must not be None")
    missing = [col for col in _REQUIRED_COLUMNS if col not in bars.columns]
    if missing:
        # Codex R2 Minor #1: error message must enumerate the actual
        # ``_REQUIRED_COLUMNS`` set. The prior message advertised Open
        # as required, but ``_REQUIRED_COLUMNS`` excludes Open (no V1
        # detector consumes ``bars['Open']``).
        required_list = ", ".join(_REQUIRED_COLUMNS)
        raise ValueError(
            f"sanitize_bars requires columns: {required_list}; "
            f"missing: {missing}"
        )
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
