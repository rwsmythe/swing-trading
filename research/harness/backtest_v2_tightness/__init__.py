"""Walk-forward backtest harness for V2 vcp.tightness_range_factor=1.005 cohort.

Study scope: per dispatch brief at
  docs/v2-tightness-range-factor-backtest-dispatch-brief.md

L2 LOCK preserved: reads only from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader.
ZERO new Schwab API calls. ZERO V1 persisted-state mutation. ZERO production swing/ writes.
"""
