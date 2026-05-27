"""V2 orderliness_max_bar_ratio cohort-extraction module set for V2-selection-mechanic investigation.

Mirrors `research/harness/v2_tightness_range_factor/` +
`research/harness/v2_proximity_max_pct/` sibling-module architecture
(per V2-selection-mechanic dispatch brief Sec 2.3).

Extracts the canonical 1 watch->aplus flip at the binding sweep_point=3.75
for vcp.orderliness_max_bar_ratio. Per V2 sensitivity SUMMARY TABLE the
binding signal is max_delta_aplus = +1 at sweep_point = 3.75 (FIRST
CROSSING convention per dispatch brief Sec 2.3 LOCK). The drill-down
ALSO emits +1 flip at sp=4.5 with the IDENTICAL single flip
(LASR:52:2026-05-15); sp=3.75 is the lower threshold + first crossing
+ the canonical LOCK. SUMMARY TABLE + drill-down agree exactly here
(0% non-watch-transition fraction for this variable).

The sp=3.75-vs-sp=4.5 disambiguation is preserved as a discriminating
test in the sibling test module + documented in the forthcoming study
writeup as evidence of the "first crossing" convention's load-bearing
role for canonical sweep_point identification.

L2 LOCK preserved: ZERO new Schwab API calls; ZERO production swing/
writes; reads only the local V2 sensitivity markdown artifact.
"""
