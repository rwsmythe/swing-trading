# Minervini Exemplar Recall - summary

Exemplars evaluated (curated=yes): 27

NOTE: the negative-control cohort is a SAME-TICKER temporal-specificity contrast,
NOT a population false-fire base rate (spec section 8/12.10).

## single_session
- screening recall (full set): 0.185
- screening recall (screenable): 0.250
- Wilson 95pct (screenable, PRIMARY): [0.112, 0.469] n=20
- ticker-clustered bootstrap 95pct (EXPLORATORY): [0.050, 0.450]
- bucket distribution: {'skip_gate_rejection': 15, 'skip_insufficient_history': 7, 'surfaced_watch': 5}
- first-rejecting-gate histogram: {'vcp': 14, 'trend_template': 1}
- per-gate pass rate (screenable): {'risk_feasibility': 1.0, 'trend_template': 0.95, 'vcp': 0.25}
- per-detector recall faithful: {'cup_with_handle': (0, 3), 'double_bottom_w': (0, 2), 'flat_base': (0, 2), 'vcp': (0, 12)}
- per-detector recall isolated: {'cup_with_handle': (1, 3), 'double_bottom_w': (0, 2), 'flat_base': (0, 2), 'vcp': (1, 12)}
- Stage-2 delta (isolated - faithful): {'cup_with_handle': 0.3333333333333333, 'double_bottom_w': 0.0, 'flat_base': 0.0, 'vcp': 0.08333333333333333}
- specificity contrast (control): {'control_surfaced_rate': 0.05185185185185185, 'control_fired_faithful_rate': 0.021052631578947368, 'control_fired_isolated_rate': 0.14736842105263157, 'control_n': 135.0, 'control_n_mapped': 95.0}

## window_sweep
- screening recall (full set): 0.667
- screening recall (screenable): 0.900
- Wilson 95pct (screenable, PRIMARY): [0.699, 0.972] n=20
- ticker-clustered bootstrap 95pct (EXPLORATORY): [0.750, 1.000]
- bucket distribution: {'surfaced_watch': 16, 'surfaced_aplus': 2, 'skip_insufficient_history': 7, 'skip_gate_rejection': 2}
- first-rejecting-gate histogram: {'vcp': 1, 'trend_template': 1}
- per-gate pass rate (screenable): {'risk_feasibility': 1.0, 'trend_template': 0.95, 'vcp': 0.9}
- per-detector recall faithful: {'cup_with_handle': (0, 3), 'double_bottom_w': (0, 2), 'flat_base': (0, 2), 'vcp': (4, 12)}
- per-detector recall isolated: {'cup_with_handle': (1, 3), 'double_bottom_w': (0, 2), 'flat_base': (0, 2), 'vcp': (9, 12)}
- Stage-2 delta (isolated - faithful): {'cup_with_handle': 0.3333333333333333, 'double_bottom_w': 0.0, 'flat_base': 0.0, 'vcp': 0.4166666666666667}
- specificity contrast (control): {'control_surfaced_rate': 0.35555555555555557, 'control_fired_faithful_rate': 0.12631578947368421, 'control_fired_isolated_rate': 0.7894736842105263, 'control_n': 135.0, 'control_n_mapped': 95.0}

