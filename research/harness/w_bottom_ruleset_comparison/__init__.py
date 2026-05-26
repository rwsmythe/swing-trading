"""D2 W-bottom ruleset comparison backtest harness.

Extends D1's double_bottom_w_backtest with 3 NEW literature-canonical exit
rulesets (Minervini Stage-2 / O'Neil cup-with-handle + Bulkowski measured-move
/ Qullamaggie momentum-burst) tested against an S&P-500-wide W-bottom cohort
(N=50-200 patterns) for the 39th cumulative C.C lesson #6 validation slot.

Reuses D1's cohort.py extraction + dedup + recency-filter logic verbatim via
import; defines a NEW walk-forward engine with a generalized Ruleset protocol
that supports scale-out semantics (required by Ruleset F).

ZERO production swing/ writes; ZERO new Schwab API calls; ZERO yfinance
fetches at backtest time (L2 LOCK preserved via V2 Shape A reader).
"""
