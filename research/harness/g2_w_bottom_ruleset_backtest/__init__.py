"""G2 W-bottom-derived ruleset backtest harness.

Sibling package to research/harness/w_bottom_ruleset_comparison/ (the existing
A-F rulesets). Adds three W-specific rulesets (G/H/I) derived from canonical
chart-pattern reference works and a 9-metric scorecard for cross-ruleset
comparison on R2-A + D2 EXPANDED substrates.

Per the G2 dispatch brief (docs/g2-w-bottom-ruleset-backtest-dispatch-brief.md):
  - A-F rulesets in w_bottom_ruleset_comparison/ are LOCKED via byte-stability
  - R2-A + D2 cohort fixtures are REUSED VERBATIM as substrates
  - The 9-metric scorecard replaces single-metric verdict-gating; gotcha #33
    banned-verdict-terms LOCK preserved across scorecard + narrative output

ZERO production swing/ writes; ZERO new Schwab API calls; ZERO yfinance
fetches at backtest time. OHLCV reads via the V2 Shape A reader
(research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader.read_yfinance_shape_a)
inherited from the existing harness for L2 LOCK parity.
"""
