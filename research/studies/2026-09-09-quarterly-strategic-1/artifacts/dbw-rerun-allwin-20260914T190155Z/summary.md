# Minervini Exemplar Recall - summary

Exemplars evaluated (curated=yes): 2

NOTE: the negative-control cohort is a SAME-TICKER temporal-specificity contrast,
NOT a population false-fire base rate (spec section 8/12.10).

## single_session
- screening recall (full set): 0.000
- screening recall (screenable): 0.000
- Wilson 95pct (screenable, PRIMARY): [0.000, 0.793] n=1
- ticker-clustered bootstrap 95pct (EXPLORATORY): [0.000, 0.000]
- bucket distribution: {'skip_gate_rejection': 1, 'skip_insufficient_history': 1}
- first-rejecting-gate histogram: {'vcp': 1}
- per-gate pass rate (screenable): {'risk_feasibility': 1.0, 'trend_template': 1.0, 'vcp': 0.0}
- per-detector recall faithful: {'double_bottom_w': (0, 2)}
- per-detector recall isolated: {'double_bottom_w': (0, 2)}
- Stage-2 delta (isolated - faithful): {'double_bottom_w': 0.0}
- specificity contrast (control): {'control_surfaced_rate': 0.1, 'control_fired_faithful_rate': 0.0, 'control_fired_isolated_rate': 0.7, 'control_n': 10.0, 'control_n_mapped': 10.0}

## window_sweep
- screening recall (full set): 0.500
- screening recall (screenable): 1.000
- Wilson 95pct (screenable, PRIMARY): [0.207, 1.000] n=1
- ticker-clustered bootstrap 95pct (EXPLORATORY): [1.000, 1.000]
- bucket distribution: {'surfaced_aplus': 1, 'skip_insufficient_history': 1}
- first-rejecting-gate histogram: {}
- per-gate pass rate (screenable): {'risk_feasibility': 1.0, 'trend_template': 1.0, 'vcp': 1.0}
- per-detector recall faithful: {'double_bottom_w': (0, 2)}
- per-detector recall isolated: {'double_bottom_w': (2, 2)}
- Stage-2 delta (isolated - faithful): {'double_bottom_w': 1.0}
- specificity contrast (control): {'control_surfaced_rate': 0.3, 'control_fired_faithful_rate': 0.2, 'control_fired_isolated_rate': 1.0, 'control_n': 10.0, 'control_n_mapped': 10.0}

