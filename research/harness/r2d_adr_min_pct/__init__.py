"""R2-D cohort-extraction module set for V2 OHLCV vcp.adr_min_pct +11.

Mirrors `research/harness/r2a_tightness_days_required/` architecture
(per dispatch brief `docs/r2d-adr-min-pct-cohort-backtest-dispatch-brief.md`
section 1.2 sibling-module strategy LOCK). Each R2-* cohort gets its
own module set; common-parser refactor is a banked V2 candidate.

Extracts the canonical 11 watch->aplus flips at the binding sweep_point
for vcp.adr_min_pct from the V2 sensitivity smoke artifact at
`exports/diagnostics/aplus-sensitivity-v2-20260524T205849Z.md`,
emits the cohort CSV + audit JSON for downstream
`pattern_cohort_evaluator` consumption + D2 6-ruleset harness.

Brief discrepancy note (documented in findings doc): the dispatch brief
states "sweep_point=1" but the actual +11 max_delta_aplus binding
signal for vcp.adr_min_pct is at sweep_point=2.0 (per the V2 sensitivity
summary table at line 116 of the source artifact: `vcp.adr_min_pct |
threshold_multiplicative | 2.0 | ... | 11 | ...`). This module uses
sweep_point=2.0 -- the value that yields exactly the brief's stated
11 watch->aplus flip count. At sweep_point=1 the section emits 15
flips (identical to R2-A's vcp.tightness_days_required cohort because
adr_min_pct=1 is more relaxed than the +11 binding sweep_point).
The brief was internally inconsistent on this point; the 11-flip count
is the binding contract.

L2 LOCK preserved: ZERO new Schwab API calls; ZERO production swing/
writes; reads only the local V2 sensitivity markdown artifact.
"""
