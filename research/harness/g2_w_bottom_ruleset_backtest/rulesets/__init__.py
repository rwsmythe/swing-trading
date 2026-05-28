"""W-bottom-derived rulesets G/H/I for G2 backtest.

Sibling layout to existing w_bottom_ruleset_comparison/rulesets.py (single
file with A-F classes). G2 adopts a per-file layout per dispatch brief Sec
2 intent: each ruleset module encapsulates its own entry/stop/target/failure
logic plus a `trigger_predicate(bars, idx, verdict)` for volume gating.

The volume gating is the structural differentiator from A-F (which apply no
volume confirmation at the trigger-search step). Per brief Sec 1.2:
  - G_bulkowski_double_bottom: breakout volume > 1.3 x 20-bar mean
  - H_oneil_double_bottom_base: breakout volume > 1.4 x 50-bar mean
  - I_edwards_magee_classical_double_bottom: breakout volume > 1.5 x
    rally_volume(trough_2_date .. trigger_bar - 1)
"""
