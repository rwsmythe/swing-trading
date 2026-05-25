"""Read-only Shape A parquet wrapper for the pattern cohort harness.

RE-EXPORT of V2 OHLCV evaluator's existing reader per OQ-3 LOCK.

L2 LOCK preservation: this module DELEGATES to V2 OHLCV evaluator's
reader which has its own 5 BINDING discriminating tests at
tests/research/test_aplus_v2_ohlcv_reader.py. This harness adds 5
ADDITIONAL BINDING discriminating tests at
tests/research/test_pattern_cohort_evaluator_reader.py verifying the
RE-EXPORT INTEGRITY per spec §E.3 + §F.1.

NEVER opens {ticker}.schwab_api.parquet under any code path.
NO fetch path. NO writes. NO archive mutation.
"""
from __future__ import annotations

from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import (
    BothExistDiagnostic,
    read_yfinance_shape_a,
    read_yfinance_shape_a_sliced,
)

# Identity-preserving re-export: the symbols below are the SAME objects as
# the V2 OHLCV reader's exports (verified via `is` identity in §F.4 test).
__all__ = (
    "BothExistDiagnostic",
    "read_yfinance_shape_a",
    "read_yfinance_shape_a_sliced",
)
