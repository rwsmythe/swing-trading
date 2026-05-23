"""V2 OHLCV criterion-evaluator harness -- lifts the V1 LIMITATION at
research/harness/aplus_sensitivity/sweep.py:248-250 by substituting cfg
values one-at-a-time + invoking production evaluate_one(ctx) end-to-end.
"""
from __future__ import annotations

__version__ = "0.2.0"
