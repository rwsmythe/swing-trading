"""R2-A backtest: V2 OHLCV `vcp.tightness_days_required +16` cohort.

Generates a cohort of (ticker, asof_date) flips from the V2 OHLCV sensitivity
drill-down markdown table at:

  exports/diagnostics/aplus-sensitivity-v2-<ISO>.md

The cohort is filtered to:
  - section `### vcp.tightness_days_required`
  - sweep_point == 1
  - old_bucket == 'watch'
  - new_bucket == 'aplus'

For the full-63-eval-run reproduction artifact (2026-05-24), this filter yields
15 flip records across 7 unique tickers (FRO/KOD/NAT/OII/RLMD/SEI/TROX).

The cohort drives the D2 W-bottom 6-ruleset comparison harness against a
DIFFERENT cohort definition (selection-biased per V2 sensitivity framework)
vs D2's bias-free S&P-500 W-bottom detection cohort. See
docs/r2a-vcp-tightness-days-required-cohort-backtest-dispatch-brief.md.

ZERO production swing/ writes; ZERO new Schwab API calls (L2 LOCK preserved).
"""
