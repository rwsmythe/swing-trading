"""V2 proximity_max_pct cohort-extraction module set for V2-selection-mechanic investigation.

Mirrors `research/harness/r2a_tightness_days_required/` +
`research/harness/r2d_adr_min_pct/` +
`research/harness/v2_tightness_range_factor/` sibling-module architecture
(per V2-selection-mechanic dispatch brief Sec 2.2). Each V2-binding-variable
cohort gets its own module set; common-parser refactor remains a banked V2
candidate.

Extracts the canonical 5 watch->aplus flips at the binding sweep_point=7.5
for vcp.proximity_max_pct from the V2 sensitivity smoke artifact at
`exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md`, emits the
cohort CSV + audit JSON for downstream `pattern_cohort_evaluator`
consumption + V2-selection-mechanic analytical orchestration.

Per V2 sensitivity SUMMARY TABLE the binding signal for vcp.proximity_max_pct
is max_delta_aplus = +5 at sweep_point = 7.5. The drill-down strict
watch->aplus filter yields exactly 5 transition rows -- SUMMARY TABLE +
drill-down agree (0% non-watch-transition fraction for this variable;
contrast with vcp.tightness_range_factor's ~11% gap documented in that
sibling module's docstring).

L2 LOCK preserved: ZERO new Schwab API calls; ZERO production swing/
writes; reads only the local V2 sensitivity markdown artifact.
"""
