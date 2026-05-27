"""V2 tightness_range_factor cohort-extraction module set for V2-selection-mechanic investigation.

Mirrors `research/harness/r2a_tightness_days_required/` and
`research/harness/r2d_adr_min_pct/` architecture (per V2-selection-mechanic
investigation dispatch brief
`docs/v2-selection-mechanic-investigation-dispatch-brief.md` Sec 2.1
sibling-module strategy LOCK). Each V2-binding-variable cohort gets its
own module set; common-parser refactor remains a banked V2 candidate.

Extracts the canonical 67 watch->aplus flips at the binding sweep_point=1.005
for vcp.tightness_range_factor from the V2 sensitivity smoke artifact at
`exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md`,
emits the cohort CSV + audit JSON for downstream
`pattern_cohort_evaluator` consumption + V2-selection-mechanic
analytical orchestration.

SUMMARY-TABLE-vs-DRILL-DOWN ACCOUNTING NOTE (per gotcha #34 second canonical
application; operator-paired LOCK at investigation dispatch greenlight
2026-05-26): the V2 sensitivity SUMMARY TABLE reports
`vcp.tightness_range_factor | 75` (max_delta_aplus). The drill-down section
at sweep_point=1.005 filtered to `old_bucket=watch AND new_bucket=aplus`
yields exactly 67 flip records -- an 8-row gap (about 11% of the +75 net
aplus change). The drill-down at sp=1.005 ALSO emits 574 `skip->watch`
transitions and ZERO `skip->aplus` or `excluded->aplus` transitions. The
+75 vs 67 gap is therefore attributable to the V2 sensitivity emitter's
delta_aplus accounting capturing additional aplus-bucket churn that the
strict `watch->aplus` filter does not surface (e.g., baseline aplus rows
that the sweep does NOT flip away from aplus -- counted in delta but
absent from the drill-down's transition-only rows).

The investigation locks EXPECTED_FLIP_COUNT = 67 as the binding drill-down
contract. The +75 vs 67 reconciliation is documented in the findings doc
+ study writeup as a methodological side-finding (per-variable
non-watch-transition-fraction characterizes each V2 binding variable's
transition signature distinct from substrate-thinness). See gotcha #34
first canonical application discriminating test at
`tests/research/v2_selection_mechanic/test_binding_signals_table_cross_check.py`
for the cross-table verification (gotcha #34 second canonical application
across all 5 V2 binding variables).

L2 LOCK preserved: ZERO new Schwab API calls; ZERO production swing/
writes; reads only the local V2 sensitivity markdown artifact.
"""
