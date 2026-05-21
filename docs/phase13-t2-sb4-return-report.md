# Phase 13 T2.SB4 — Detectors batch 2 (HTF + DBW) — RETURN REPORT

**Status:** SHIPPED on branch `phase13-t2-sb4-detectors-batch2` at HEAD `16f21d2`. Awaiting operator-paired S2 + S3 gates + merge.

**Branch base:** main HEAD `af2ed5b` (the T2.SB4 dispatch brief commit).

**Date:** 2026-05-21.

---

## §1 Full commit chain (12 commits)

```
16f21d2 docs(phase13): T2.SB4 Codex R4 fixes - spec line 290 + dispatch brief errata
499c5ab fix(phase13): T2.SB4 Codex R3 fixes - pattern_evaluations.geometric_score column persists evidence
4768ee3 fix(phase13): T2.SB4 Codex R2 fixes - DBW composite-cap + HTF bounded pole
6f735db fix(phase13): T2.SB4 Codex R1 fixes - DBW evidence cap + DBW anchor + HTF pole peak
52ee630 fix(phase13): T2.SB4 closer ASCII-only LOCK 1-char em-dash swap
82050fd test(phase13): T2.SB4 closer (T-A.4.7)
d744a9e test(phase13): T2.SB4 integration E2E (T-A.4.6)
f413a6b feat(phase13): T2.SB4 Codex high-stakes clause activated for HTF + DBW (T-A.4.5)
d73b50b feat(phase13): drift_logging extension for HTF + DBW (T-A.4.4)
7685090 feat(phase13): _step_pattern_detect extended to 5 detectors (T-A.4.3)
f3c2107 feat(phase13): double-bottom-W detector + undercut bonus (T-A.4.2)
b9decf5 feat(phase13): high-tight-flag detector (T-A.4.1)
```

7 task commits (T-A.4.1 through T-A.4.7) + 1 ASCII-only LOCK closer fix + 4 Codex fix-bundle commits (R1 through R4).

ZERO `Co-Authored-By` trailer across all 12 commits (verified via `git log --pretty='%(trailers:key=Co-Authored-By)' phase13-t2-sb4-detectors-batch2 --not main | grep -c .` → 0). Cumulative ~294+ commit ZERO-trailer streak preserved (T2.SB3 = ~282 + T2.SB4 added 12).

---

## §2 Codex MCP adversarial-critic chain — 5 rounds; converged to NO_NEW_CRITICAL_MAJOR at R5

| Round | Critical | Major | Minor | Verdict | Fix commit |
|---|---|---|---|---|---|
| R1 | 0 | 3 | 2 | ISSUES_FOUND | `6f735db` |
| R2 | 1 | 1 | 1 | ISSUES_FOUND | `4768ee3` |
| R3 | 0 | 1 | 2 | ISSUES_FOUND | `499c5ab` |
| R4 | 0 | 1 | 1 | ISSUES_FOUND | `16f21d2` |
| R5 | 0 | 0 | 2 | NO_NEW_CRITICAL_MAJOR | (Minors banked as advisory) |

### Per-round findings + resolutions

**Round 1 (3 Major + 2 Minor):**
1. (Major) DBW evidence `geometric_score` capped at 1.0 contradicts spec §5.8 line 718 + §10.5 line 1325 (1.10 for evidence). RESOLVED: renamed `_SCORE_CAP` → `_EVIDENCE_SCORE_CAP = 1.10`; `__post_init__` validates [0.0, 1.10]; renamed discriminating test + asserts 1.10.
2. (Major) DBW `_backward_slice_dbw_structure` ignores `candidate_window.anchor_date` (zigzag_pivot semantic per `swing/patterns/foundation.py:379-387`). RESOLVED: helper signature takes full `CandidateWindow`; enforces `abs(trough_1_date - anchor_date) <= 1 day` for zigzag_pivot mode (detected via `anchor_reason.startswith("zigzag_pivot")`); preserves end-bar backward-slice for ma_crossover / high_low_breakout modes. 4 new discriminating tests.
3. (Major) HTF `_backward_slice_pole_peak` returns first-reversed up-swing endpoint — can pick consolidation swing-high (not pole peak). RESOLVED initially via highest-end_price selection + 21-day gap (subsequently refined at R2 with bounded search window).
4. (Minor) `±` glyph drift at `swing/patterns/double_bottom_w.py:343, :392` + `tests/patterns/test_double_bottom_w.py:300`. RESOLVED: ASCII swap to `+/-`.
5. (Minor) `consolidation_width_pct` unit ambiguity (percent vs fraction). RESOLVED: inline comment in `HighTightFlagEvidence` field section clarifies percent units; cites §5.5 LOCK shape `<= 0.15` equivalence to `<= 15.0 percent`.

**Round 2 (1 Critical + 1 Major + 1 Minor):**
1. (**Critical**) R1 M1's 1.10 evidence cap poisons drift_logging via pipeline `composite_score = geometric_score` path: `swing/patterns/drift_logging.py:_composite_score_histogram` rejects scores outside [0.0, 1.0] with ValueError; `_step_pattern_detect` catches and skips all queued inserts — one all-pass DBW row would suppress drift_logging for every queued row in the run. RESOLVED via composite clamp at `swing/pipeline/runner.py:1661-1683`: `composite_score = min(1.0, geometric_score)` per spec §5.8 line 712 wrap (pre-T2.SB5 simplification of §5.8 formula). Evidence preserved at 1.10 in structural_evidence_json. 2 discriminating tests added: single-row composite-clamp + multi-row regression where ONE row hits 1.10 and all rows still persist.
2. (Major) R1 M3 fix overcorrected: `max(end_price)` selection picks historical max (e.g., prior bull-cycle peak), not recent valid pole. RESOLVED via bounded search `[anchor_date - 91 days, anchor_date - 21 days]` (pole_duration max 56 + consolidation_duration max 35; consolidation_duration min 21); LATEST-valid candidate selection gated by pole_pct ≥ 0.85 + pole_duration in [28, 56]. 2 discriminating tests added (historical $50 + recent $11 pole; no-recent-pole returns zero-evidence).
3. (Minor) `swing/patterns/spec_static.py:617` + `tests/integration/test_phase13_t2_sb4_detectors_e2e.py:443-485` encoded old [0.0, 1.0] DBW cap. RESOLVED: spec_static documents [0.0, 1.10] evidence with composite-clamp note; E2E asserts branch DBW vs other-4 detectors.

**Round 3 (1 Major + 2 Minor):**
1. (Major) Pipeline row stores `geometric_score=float(composite_score)` (clamped) at `swing/pipeline/runner.py:1844` — DB column loses 1.10 evidence value (only structural_evidence_json keeps it). RESOLVED: schema CHECK on `pattern_evaluations.geometric_score` confirmed UNCONSTRAINED REAL at migration 0020 line 240 (no CHECK rejecting > 1.0). Row construction now persists `geometric_score=float(evidence.geometric_score)` (RAW evidence, 1.10) + `composite_score=float(composite_score)` (CLAMPED via R2's min(1.0, ...) wrap). R2 Critical #1 discriminating test extended with 3-way assertion: DB geometric_score==1.10 + DB composite_score==1.0 + JSON geometric_score==1.10. **Option C chosen** (Option A migration was unnecessary; schema v20 LOCK preserved).
2. (Minor) `swing/patterns/spec_static.py:463-468` DBW `composite_scoring_note` still encoded old "capping at 1.0 via min(1.0, ...)" framing. RESOLVED: note distinguishes evidence-tier 1.10 cap from composite-tier 1.0 cap; cites §5.8 line 718 + §10.5 line 1325.
3. (Minor) E2E docstring at `tests/integration/test_phase13_t2_sb4_detectors_e2e.py:295-300` still claimed old `composite_score == geometric_score` invariant. RESOLVED: docstring rewritten reflecting DBW vs other-4 detector branch asymmetry.

**Round 4 (1 Major + 1 Minor):**
1. (Major) Spec doc internal inconsistency at `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md:290`: `pattern_evaluations.geometric_score` table entry said `0..1` but §5.8 line 718 + §10.5 line 1325 BINDING locks specify 1.10 for DBW evidence. RESOLVED as **spec ERRATA closure** (internal-inconsistency repair; binding §5.8 + §10.5 text unchanged): line 290 + adjacent `composite_score` entry rewritten to document the [0.0, 1.10] / [0.0, 1.0] split with full LOCK chain citation.
2. (Minor) Dispatch brief lines 49 + 110 still encoded old "1.0 cap" framing. RESOLVED: top-of-brief errata note appended citing R1 M1 + R2 + R3 + R4 LOCK chain + return report; lines 49 + 110 PRESERVED as historical audit artifact.

**Round 5 (2 Minor; CONVERGED):**
1. (Minor) `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md:2671` still says DBW "undercut bonus + geometric_score capped at 1.0". **BANKED ADVISORY** (V2 plan-amendment sweep candidate).
2. (Minor) Dispatch brief lines 67 + 189 also carry stale "1.0 cap" language. **BANKED ADVISORY** (brief is archival; top-of-file errata note from R4 covers the LOCK chain).

### TECHNICALLY SOUND ACCEPT-WITH-RATIONALE banks
- R5 #1 + #2: Minor doc drift in plan + dispatch brief beyond what R4 top-of-file errata note covers. ACCEPT — both are non-blocking; plan + brief are historical reference artifacts; the BINDING source-of-truth (spec §5.8 + §10.5; spec line 290 + 294 corrected at R4) reflects the correct LOCK chain.

### Banks for future sub-bundle inheritance (forward-binding lessons)
- DBW evidence-vs-composite cap distinction: spec §5.8 line 718 + §10.5 line 1325 — evidence-tier `geometric_score` can reach 1.10; composite-tier wraps with `min(1.0, ...)`. Pipeline composite_score derivation MUST apply the clamp to preserve drift_logging contract.
- Pipeline row construction: persist RAW evidence in `pattern_evaluations.geometric_score` (column unconstrained REAL); persist CLAMPED in `pattern_evaluations.composite_score`. Both values traceable to `structural_evidence_json` raw evidence.
- HTF bounded pole-peak search: `[anchor_date - 91 days, anchor_date - 21 days]`; LATEST-valid candidate selection. Forward-binding for any future swing-HIGH anchor detector with consolidation post-anchor semantic.
- DBW anchor_date contract: zigzag_pivot mode's `anchor_date` is the inferred base START — for DBW that aligns with trough_1 (±1 day tolerance). Forward-binding for any future zigzag_pivot-mode-aware detector.

---

## §3 Test count pre/post

| Phase | Fast tests | Slow tests | Skipped | Failed |
|---|---|---|---|---|
| Baseline (post-T3.SB2 + hotfix at `cf3c489`) | 5328 | (existing) | 4 | 0 |
| Post-T-A.4.1 HTF (`b9decf5`) | 5341 | — | 4 | 0 |
| Post-T-A.4.2 DBW (`f3c2107`) | 5357 | — | 4 | 0 |
| Post-T-A.4.3 pipeline 5-detector (`7685090`) | 5358 | — | 4 | 0 |
| Post-T-A.4.4 drift_logging (`d73b50b`) | 5361 | — | 4 | 0 |
| Post-T-A.4.5 Codex high-stakes (`f413a6b`) | 5365 | — | 4 | 0 |
| Post-T-A.4.6 E2E (`d744a9e`) | 5366 | — | 4 | 0 |
| Post-T-A.4.7 closer + ASCII fix (`52ee630`) | 5366 | — | 4 | 0 |
| Post-R1 fix bundle (`6f735db`) | 5372 | — | 4 | 0 |
| Post-R2 fix bundle (`4768ee3`) | 5376 | — | 4 | 0 |
| Post-R3 fix bundle (`499c5ab`) | 5376 | — | 4 | 0 |
| Post-R4 fix bundle (`16f21d2`) | **5376** | — | **4** | **0** |

**Delta:** +48 fast tests (5328 → 5376). Per-task minimum hits:
- T-A.4.1 HTF: 13 (≥10 required)
- T-A.4.2 DBW: 16 (≥12 required)
- T-A.4.3 pipeline 5-detector: 2 new + 8 existing updated (≥1 required)
- T-A.4.4 drift_logging: 3 new (≥2 required)
- T-A.4.5 Codex high-stakes: 4 new (≥1 required)
- T-A.4.6 E2E: 1 fast E2E (=1 required); no slow E2E (per plan §G.6 T-A.4.6 fast-only)
- T-A.4.7 closer: in-place extension of 2 cross-bundle pins
- R1-R4 fixes: +10 discriminating tests across 4 fix bundles

4 skipped tests are pre-existing cross-bundle pins targeting later milestones per plan §H.3 (T2.SB5 template matching DTW; T4.SB closer schema-validation sweep) — none T2.SB4-scheduled. **0 NEW skips, 0 un-skips** (the `test_all_5_detectors_emit_consistent_schema` cross-bundle pin per plan §H.3 row 7 was actually planted at T2.SB3 T-A.3.5 under a slightly different name without skip-decoration; T-A.4.7 extended it in-place from 3 to 5 detector classes).

---

## §4 Cross-bundle pin extensions — CONFIRMED at T-A.4.7

### §4.1 `test_foundation_primitives_consumed_by_detectors_invariant`

`tests/patterns/test_foundation_integration.py:218-325` — extended from 3-detector T2.SB3 body to 5-detector body. Adds `swing.patterns.high_tight_flag` + `swing.patterns.double_bottom_w` introspection via `inspect.getsource`.

**Per-detector foundation primitive inventory (recorded faithfully in test):**
- VCP: `CandidateWindow`, `current_stage`, `extract_zigzag_swings`, `adaptive_initial_threshold_pct`, `volume_trend_through_swings`
- flat_base: `CandidateWindow`, `current_stage`, `extract_zigzag_swings`, `adaptive_initial_threshold_pct`
- cup_with_handle: `CandidateWindow`, `current_stage`, `extract_zigzag_swings`, `adaptive_initial_threshold_pct`
- **high_tight_flag (NEW)**: `CandidateWindow`, `current_stage`, `extract_zigzag_swings`, `adaptive_initial_threshold_pct` (does NOT use `volume_trend_through_swings` — computes its own pole + consolidation volume aggregates inline)
- **double_bottom_w (NEW)**: `CandidateWindow`, `current_stage`, `extract_zigzag_swings`, `adaptive_initial_threshold_pct` (also does NOT use `volume_trend_through_swings` — computes its own trough_1 / trough_2 average volumes inline)

**Forward-binding lesson #1 (T2.SB4 → T2.SB5)**: HTF + DBW are the first detectors that DO NOT reuse `volume_trend_through_swings`. The foundation primitive REUSE invariant is partial in detectors batch 2. Future detector additions (T2.SB5 + V2) may continue this pattern OR may share more primitives — the test accurately records actual imports, not aspirational primitive coverage.

### §4.2 `test_all_5_detectors_emit_consistent_schema`

`tests/patterns/test_drift_logging.py:323+` — extended to call `capture_feature_distribution()` for HTF + DBW via `_build_high_tight_flag_evidence` + `_build_double_bottom_w_evidence` fixture builders (planted at T-A.4.4). Asserts:
- All 5 detectors emit `FeatureDistributionLog` with the same field set (schema consistency invariant)
- HTF populates `volume_aggregates` (consolidation_avg_volume_to_pole_ratio + raw consolidation_avg_volume)
- DBW populates `center_trough_retracement` (via new `_extract_center_trough_retracement` helper at drift_logging.py:212-228)
- VCP `contraction_depths` is None for non-VCP detectors

**Cross-bundle pin name divergence**: plan §H.3 row 7 names this pin `test_drift_logging_5_detector_schema_consistent`; the actual planted name (at T2.SB3 T-A.3.5) is `test_all_5_detectors_emit_consistent_schema`. Semantic equivalence verified — both test the 5-detector schema consistency invariant. The pin was NOT skip-decorated pre-T2.SB4; T-A.4.7 extended in-place.

---

## §5 Per-detector empirical observations + tolerance behavior

### §5.1 HTF — STRICT bound NONE preservation on consolidation_width_pct

**Locked**: STRICT per spec §5.5 criterion #4 + §10.6 LOCK STRICT bound NONE. Implementation: `consolidation_width_pct <= 15.0 percent` (equivalent to spec `<= 0.15` fraction).

**Synthetic §10.4 fixture observation**:
- 14.8% width: PASSES strict bound (alternative-pass scenario per §10.4)
- 15.6% width: REJECTS per §10.4 errata + §10.6 LOCK
- Boundary at exactly 15.0% width: PASSES (`<=` inclusive)

**No empirical widening demanded** — `_check_consolidation_width` returns False for any width > 15.0; hard-gate zeros geometric_score. The STRICT bound is preserved without operator escalation (L5 LOCK honored).

**HTF pole-peak selection algorithm (post-R2 refinement)**:
- Bounded search: `[anchor_date - 91 days, anchor_date - 21 days]` (the only zone where a pole peak can plausibly precede a valid consolidation per §5.5 criterion #2 + #3 duration bounds)
- LATEST-valid candidate selection gated by pole_pct ≥ 0.85 + pole_duration in [28, 56]
- Tie-breaker: earlier peak (more conservative pole identification)
- Real-world implication: an older historical peak in fetched history (e.g., prior bull cycle) is OUT-OF-BOUNDS and won't capture the algorithm.

### §5.2 DBW — undercut bonus + evidence vs composite cap

**Locked per §5.8 line 718 + §10.5 line 1325**:
- Evidence-tier `geometric_score` = `min(base_pass_fraction + 0.10 if undercut, 1.10)` (caps at 1.10)
- Composite-tier `composite_score` = `min(1.0, geometric_score)` at pipeline (pre-T2.SB5 simplification of §5.8 formula `min(1.0, 0.60 × geom + 0.40 × tm)`)
- DB columns: `pattern_evaluations.geometric_score` stores RAW 1.10; `pattern_evaluations.composite_score` stores CLAMPED 1.0
- structural_evidence_json carries RAW evidence (1.10)

**Synthetic §10.5 fixture observation (with implementer V2 spec amendment candidate banked)**:
- §10.5 narrative claims center_peak=$23 → 60% retracement, but standard retracement formula `(23-20)/(26.67-20) = 0.45` (45%). Implementer used center_peak=$24.00 in DBW test fixture to honor the 60% spec criterion #3 LOCK shape rather than the literal $23. **V2 spec amendment candidate** — either fix §10.5 numerics ($24.00 with 60% retained) or redefine the retracement formula. Implementation is faithful to criterion #3 LOCK shape (60% retracement); the worked-example narrative is the source of the inconsistency.

**DBW anchor_date contract (post-R1 M2 refinement)**:
- For `zigzag_pivot` mode (`anchor_reason.startswith("zigzag_pivot")`): `_backward_slice_dbw_structure` enforces `abs(trough_1_date - anchor_date) <= 1 day` (zigzag anchor IS base START per `swing/patterns/foundation.py:379-387`)
- For `ma_crossover` / `high_low_breakout` modes: preserves end-bar backward-slice (anchor_date is TRIGGER EVENT, not base START)

### §5.3 5-detector pipeline integration latency

**Observation**: The pipeline integration E2E (`test_phase13_t2_sb4_detectors_e2e_fast`) completes in ~5.5s with 5 candidate windows × 5 detectors = 25 pattern_evaluations row emits. No latency regression observed vs T2.SB3's 3-detector baseline. **Forward-binding lesson**: 5-detector iteration is comfortably within fast-test budget.

### §5.4 Pipeline path single-window-per-ticker (V1; inherited from T2.SB3 §6.4)

`_step_pattern_detect` selects `windows[-1]` (most-recent candidate window per ticker per detector). Same V1 known limitation as T2.SB3 — pipeline-path candidate windows often produce too-short base context that fails detector criteria. The fast E2E asserts SHAPE contracts (row counts; JSON parseability; composite_score relationship); unit-level slow E2E (none for T2.SB4) is unnecessary — the unit-level detector tests at `tests/patterns/test_high_tight_flag.py` + `tests/patterns/test_double_bottom_w.py` exercise the algorithms directly with synthesized §10.4 + §10.5 fixtures.

**V2 candidate banked (inherited from T2.SB3 §6.4)**: multi-anchor candidate window iteration (iterate ALL windows per ticker, pick highest-scoring per pattern_class). Spec §3.6 v21+ territory.

---

## §6 Operator-witnessed gate (post-merge, S2 + S3)

### §6.1 S2 (CLI)

Per plan §G.6 lines 1967-1969 + brief §5.2:

```bash
cd c:/Users/rwsmy/swing-trading  # NOT the worktree; merge to main first
python -m swing.cli pipeline run
```

**Expected**: `_step_pattern_detect` lands `pattern_evaluations` rows across all 5 detector classes (when candidate windows of each pattern class are present); operator inspects rows for plausible verdicts.

**Operator verification checklist**:
- `geometric_score` in `[0.0, 1.10]` for DBW rows (1.0 max for other 4 detectors)
- `composite_score` in `[0.0, 1.0]` (clamped per §5.8 line 712 wrap)
- `structural_evidence_json` populated + parseable (full evidence shape per detector)
- `feature_distribution_log_json` populated with run-level histograms across 5 detector classes
- No drift_logging exception abort under DBW undercut scenarios (R2 Critical #1 regression check)

### §6.2 S3 (cross-check)

**Operator visually compares detector output for**:
- A known historical HTF setup (e.g., recent strong-momentum stock with a 3-5 week tight consolidation after a 90%+ move; verify detector's pole_peak_date matches operator's subjective pole top; verify consolidation_* fields match operator's subjective consolidation boundaries; verify §10.6 STRICT bound NONE on consolidation_width_pct rejects on any width > 15.0%).
- A known historical DBW setup (e.g., recent W-shaped recovery from a multi-month base; verify detector's trough_1 / center_peak / trough_2 alignment; verify undercut bonus fires when expected; verify pivot at center_peak height).

**Opportunity**: empirically validate the §10.4 HTF STRICT bound rejection rate + §10.5 DBW undercut bonus distribution against real exemplars. If HTF STRICT bound rejects > 50% of operator-recognized HTF setups, that's V2 calibration territory (re-amend §10.6 LOCK with operator data). If DBW undercut bonus fires < 10% of real DBW setups, the bonus may be too conservative (also V2 calibration).

---

## §7 Forward-binding lessons banked for T2.SB5 + T3.SB3 + T2.SB6

### §7.1 For T2.SB5 (Template matching DTW + composite scoring; plan §G.7; 6 tasks)

1. **§5.8 composite formula MUST preserve `min(1.0, ...)` wrap** when template_match_score lands. The pre-T2.SB5 pipeline composite at `swing/pipeline/runner.py:1661-1683` clamps via `composite_score = min(1.0, geometric_score)`. When T2.SB5 lands the `min(1.0, 0.60 × geom + 0.40 × tm)` formula, the `min(1.0, ...)` wrap MUST be preserved — DBW evidence at 1.10 + template_match_score at 1.0 yields `0.60 × 1.10 + 0.40 × 1.0 = 1.06` which without clamp would re-poison drift_logging.
2. **DB column semantics**: `pattern_evaluations.geometric_score` stores RAW rule-tier evidence (unconstrained REAL); `pattern_evaluations.composite_score` stores CLAMPED composite. T2.SB5 should not regress this — keep evidence + composite as separate column semantics.
3. **`structural_evidence_json` carries raw evidence values** even when DB columns clamp. Downstream consumers (T2.SB6 closed-loop UI; T4.SB Q4 reviews) reading evidence must consult JSON if they want unclamped values.
4. **5-detector pipeline integration latency stable** at ~5.5s for 5 candidate windows; T2.SB5 DTW O(n²) layer may not regress this materially per spec §5.7 benchmark gate.

### §7.2 For T3.SB3 (Review auto-fill consuming OhlcvCache; spec §6.3)

1. **Foundation primitive REUSE is partial** in detectors batch 2 (HTF + DBW do NOT use `volume_trend_through_swings`). T3.SB3 review auto-fill consuming Phase 8 daily_management_records + candle data may inherit partial primitive coverage; document foundation primitive usage faithfully in cross-bundle pin extensions.
2. **Hidden anchor 4-tier rejection ladder discipline** (per existing CLAUDE.md gotcha + T3.SB1 + T3.SB2) inherits verbatim — T3.SB3 form-driven routes with operator hidden anchors must enforce the canonical 4-tier rejection.

### §7.3 For T2.SB6 (Closed-loop surface + Theme 1 annotated charts; plan §G.9; 8 tasks)

1. **`structural_evidence_json` is the source of truth for full evidence rendering** (raw values; not clamped column values). T2.SB6 annotated chart rendering consuming pattern_evaluations should consult JSON for HTF `pole_*` / `consolidation_*` / DBW `trough_1_*` / `center_peak_*` / `trough_2_*` / `undercut` fields.
2. **5-detector pattern_evaluations rows are the substrate** — when no detector fires (geometric_score=0.0 across all 5), the emit-when-zero contract still persists rows for the closed-loop UI to show "evaluated; no pattern match" instead of "missing evaluation".

### §7.4 For both T2.SB5 + T3.SB3 + T2.SB6 + future arc work

1. **Pre-Codex orchestrator-side review (C.C lesson #6 BINDING; 20th cumulative validation)** — BANKED CLEAN here with scope-expanded discipline (grep `swing/` for hardcoded duplicates of widened constants). 21st expected at T2.SB5 dispatch.
2. **ZERO `Co-Authored-By` trailer streak** — ~294+ cumulative commits (T2.SB4 added 12). Discipline preserved.
3. **Two-pass-reconcile-serialize architecture (T2.SB3 R4 refinement)** preserved verbatim through T2.SB4. T2.SB5 template-matching layer should NOT regress this.
4. **Spec-text-vs-implementation alignment**: when a spec entry is internally inconsistent (R4 Major #1 line 290 vs §5.8 + §10.5), treat as "spec errata closure" not "L1 behavioral deviation". Update derivative text to align with BINDING source-of-truth; do NOT modify BINDING text without operator escalation.

---

## §8 Deviations from brief with rationale

1. **Test count below upper projection (+48 actual vs +60-100 brief projection)**: per-task contracts honored. Codex chain added +10 discriminating tests across 4 fix bundles, bringing actual delta to +48. Below the brief's lower bound of +60 but each per-task minimum met.

2. **DBW evidence cap initially wrong per dispatch brief sketch**: brief §1.1 #12 + §4.1 #4 + §10.5 references prescribed `min(base + bonus, 1.0)` evidence cap. Codex R1 M1 correctly caught the spec divergence (§5.8 line 718 + §10.5 line 1325 establish 1.10 evidence cap; only composite caps at 1.0). Implementer's R1 fix bundle corrected. Brief errata note appended at R4 documenting supersession.

3. **§10.5 worked-example arithmetic inconsistency**: spec narrative center_peak=$23 → 60% retracement is mathematically inconsistent (actual = 45%). Implementer used center_peak=$24.00 in DBW test fixture to honor the 60% spec criterion #3 LOCK shape. **V2 spec amendment candidate banked**.

4. **HTF M3 R2-refined pole-peak algorithm**: R1 fix picked `max(end_price)` over all UP-swings with 21-day gap; Codex R2 M1 correctly caught this overcorrects (older historical peaks win over recent valid poles). R2 fix bounded search to `[anchor − 91d, anchor − 21d]` + LATEST-valid candidate selection.

5. **Cross-bundle pin name divergence**: plan §H.3 row 7 names the pin `test_drift_logging_5_detector_schema_consistent`; actual planted name (T2.SB3 T-A.3.5) is `test_all_5_detectors_emit_consistent_schema`. Semantic equivalence; T-A.4.7 extended in-place. NOT a regression.

6. **DBW `_RECENT_STAGE_VALUES` defined as duplicate of `_STAGE_VALUES`**: implementer-flagged at T-A.4.2 code-quality review. Defensible as forward-compat hook for criterion #1 `recent_stage` enumeration if/when stage-history lookback is wired (spec §5.6 criterion #1 mentions `recent_stage == 'stage_4'`). ACCEPT-WITH-RATIONALE.

7. **Foundation primitive `volume_trend_through_swings` NOT reused by HTF + DBW**: both detectors compute their own per-segment volume aggregates inline. Acceptable per the test's accurate-introspection discipline (it asserts what each detector ACTUALLY imports, not aspirational coverage).

---

## §9 LOCKs preserved (verbatim across all 12 commits)

- **L1**: Spec §5.5 + §5.6 + §5.8 + §10.4 + §10.5 + §10.6 + §D.7 criteria + tolerances + composite formula bound verbatim. R4 Major #1 spec line 290 errata closure ALIGNS derivative table entry with BINDING §5.8 + §10.5; binding text unchanged.
- **L2**: ZERO DB writes inside detector pure functions (`detect_high_tight_flag` + `detect_double_bottom_w`). Verified via grep: no `conn.execute|INSERT|UPDATE|DELETE` inside `swing/patterns/high_tight_flag.py` + `swing/patterns/double_bottom_w.py` (only allowed DB call: `current_stage()` SELECT-only).
- **L3**: NO `INSERT OR REPLACE` on `pattern_evaluations`. SELECT-then-INSERT idempotency preserved at runner.py Pass 2.
- **L4**: Cross-bundle pin EXTENSIONS landed at T-A.4.7 closer (foundation introspection 3→5 detectors; drift_logging schema test 3→5 detectors via in-place extension).
- **L5**: §10.6 STRICT bound NONE on HTF consolidation_width_pct preserved. 15.6% rejects; 14.8% passes; 15.0% boundary inclusive. NO empirical widening.
- **L6**: Branch base = main HEAD `af2ed5b` (T2.SB4 dispatch brief commit). Verified.
- **L7**: Frozen dataclasses + `__post_init__` runtime validation: HighTightFlagEvidence + DoubleBottomWEvidence + per-criterion sub-validators. Honors CLAUDE.md gotcha "`Literal[...]` not runtime-enforced". DBW geometric_score field validated to [0.0, 1.10] post-R1 M1.
- **L8**: HTF naming `consolidation_*` (NOT `flag_*`). `HighTightFlagEvidence` field names use `consolidation_start_date`, `consolidation_end_date`, `consolidation_pullback_pct`, `consolidation_width_pct`, `consolidation_duration_days`, `consolidation_avg_volume`, `consolidation_top_price`, `consolidation_bottom_price`. `tests/patterns/test_spec_static.py::test_high_tight_flag_consolidation_naming_matches_spec_5_5_not_flag_naming` continues to pass.
- **L9**: `_DETECTOR_CLASS_VALUES` 5-value frozenset in `swing/patterns/drift_logging.py:43` UNCHANGED. T-A.4.4 extended per-detector feature shape registry via isinstance branching; did NOT widen the constant.
- **L10**: Bar-clipping at detector entry — both HTF + DBW apply `bars = bars.loc[bars.index <= candidate_window.end_date]` BEFORE anchor identification (mirrors `cup_with_handle.py:631-636` precedent). Discriminating tests: HTF plants future-bar HIGHEST-HIGH + asserts pole_peak_date ≤ window.end_date; DBW plants future-bar LOWEST-LOW + asserts trough_1/2/center_peak dates ≤ window.end_date.

---

## §10 Pre-Codex orchestrator-side review (C.C lesson #6 — 20th cumulative validation)

**Verdict**: APPROVED_FOR_CODEX (BANKED CLEAN).

**Scope-expanded discipline applied** (per T3.SB2 hotfix forensic banked at `9899bda` housekeeping):
- Grep `swing/` for hardcoded 3-tuple/3-frozenset/3-list of `("vcp", "flat_base", "cup_with_handle")` that would silently reject HTF + DBW
- Audit findings:
  - Canonical `DETECTOR_PATTERN_CLASSES` at `swing/data/models.py:28` — **already 5-value tuple** (T-A.1.1 atomic landing)
  - `_DETECTOR_CLASS_VALUES` at `swing/patterns/drift_logging.py:43` — **already 5-value frozenset**
  - Schema CHECK at migration `0020_phase13_charts_patterns_autofill_usability.sql` lines 71/79/187/236 — **already 5-value enum**
  - `swing/cli.py:3772` help text — already lists all 5 detector class names
  - `_pattern_detect_registry()` at `swing/pipeline/runner.py:1246+` — extended 3→5 at T-A.4.3 (the only callsite needing widening)
- **NO hardcoded `("vcp", "flat_base", "cup_with_handle")` 3-tuple guards found anywhere in `swing/` that would silently reject HTF or DBW.**
- T-A.1.1's atomic landing of the 5-value constants paid off; the scope-expanded discipline confirms no surface-guard defect awaiting discovery (like T3.SB2's `_call_endpoint` 4-site duplication).

**20th cumulative C.C lesson #6 validation: CLEAN.** 21st expected at T2.SB5 dispatch.

**Anticipated Codex findings (per pre-Codex review)**:
- Predicted ~3 Minor + ~0-2 Major. Actual Codex: 1 Critical (R2) + 6 Major (R1×3 + R2×1 + R3×1 + R4×1) + 8 Minor (R1×2 + R2×1 + R3×2 + R4×1 + R5×2).
- The Critical at R2 was a downstream consequence of R1 M1's spec-fidelity fix (the implementer's original dispatch brief was wrong on the cap, and the brief sketch led implementer to bypass the spec divergence the pre-Codex review didn't catch). Forward-binding lesson: pre-Codex review must cross-check spec source-of-truth against dispatch brief sketches, not assume the brief is spec-faithful.

---

## §11 S1 inline gate — PASSED

- [x] All 7 T-A.4.X tasks committed per plan §G.6 acceptance criteria + 1 ASCII fix + 4 Codex fix bundles = 12 commits total.
- [x] `python -m pytest -m "not slow" -q -n auto` → **5376 passed, 4 skipped, 0 failed** in ~106s.
- [x] T2.SB4 has no slow E2E (per plan §G.6 T-A.4.6 fast-only).
- [x] `ruff check swing/` clean (0 E501).
- [x] Schema version unchanged at v20.
- [x] Pre-Codex orchestrator-side review APPROVED_FOR_CODEX (20th cumulative C.C lesson #6 BANKED CLEAN with scope-expanded discipline).
- [x] All 12 commits on branch have empty Co-Authored-By trailer (verified via `git log --pretty='%(trailers:key=Co-Authored-By)' phase13-t2-sb4-detectors-batch2 --not main | grep -c .` → 0).
- [x] Codex MCP adversarial-critic chain converged to NO_NEW_CRITICAL_MAJOR at R5 (5 rounds; 1 Critical + 6 Major + 6 fixed-Minor + 2 banked-Minor).

---

## §12 Remaining S2 + S3 operator-paired gates (post-merge)

- **S2 (CLI)**: `python -m swing.cli pipeline run` against operator's production candidate pool. Verify `_step_pattern_detect` lands `pattern_evaluations` rows across applicable pattern classes (when candidate windows of each class are present); operator inspects rows for plausible verdicts (geometric_score in [0.0, 1.10] for DBW; [0.0, 1.0] for other 4; composite_score in [0.0, 1.0]; structural_evidence_json + feature_distribution_log_json populated).
- **S3 (cross-check)**: operator visually compares detector output for a known historical HTF setup AND a known historical DBW setup; verifies detector verdicts match subjective assessment. Opportunity to empirically validate the §10.4 HTF STRICT bound + §10.5 DBW undercut bonus against real exemplars.

---

## §13 NEW CLAUDE.md gotchas surfaced

1. **Evidence-tier vs composite-tier score cap distinction** (R1 M1 + R2 Critical #1 + R3 Major #1 lesson family): when a spec defines BOTH an evidence-tier metric (rule-pass-fraction + bonus) AND a composite-tier metric (weighted blend + clamp), the implementation MUST:
   - Allow evidence-tier to reach the spec'd upper bound (e.g., 1.10 for DBW with undercut bonus)
   - Clamp composite-tier at the spec'd composite cap (e.g., 1.0)
   - Persist evidence in `structural_evidence_json` raw + DB evidence column unconstrained
   - Persist composite in DB composite column clamped
   - Validate the downstream `_composite_score_histogram` or similar histogramming functions consume the CLAMPED composite, NOT the raw evidence (otherwise ValueErrors poison the run)
2. **Bounded backward-slice search for anchor-relative detectors**: when an algorithm walks back from an anchor_date to find a structural landmark (pole peak; cup left edge; trough_1), bound the search window per the spec's max duration constraints. Picking "most recent" OR "absolute max" without bounding allows historical-data anomalies to capture the algorithm.
3. **DBW anchor_date contract via `anchor_reason.startswith("zigzag_pivot")`**: detectors consuming `CandidateWindow` MUST check the `anchor_reason` mode tag to determine `anchor_date` semantic (zigzag_pivot = base START; ma_crossover / high_low_breakout = TRIGGER EVENT). T2.SB3 detectors did not enforce this strictly; T2.SB4 DBW does (per R1 M2 fix).
4. **Pre-Codex review must cross-check spec source-of-truth against dispatch brief sketches**: the dispatch brief's prescription of "geometric_score = min(base + bonus, 1.0)" was wrong per spec §5.8 line 718 + §10.5 line 1325 (1.10 evidence cap). The pre-Codex review reading the brief alone wouldn't catch this; cross-checking against §5.8 + §10.5 BINDING text is required. Forward-binding lesson: pre-Codex review templates SHOULD include "verify dispatch brief prescriptions against spec source-of-truth" as a binding step.

---

## §14 V2 amendment candidates

1. **§10.5 worked-example arithmetic** (banked at T-A.4.2): center_peak=$23 → 60% retracement is inconsistent (`(23-20)/(26.67-20) = 0.45`). Recommend amendment: change center_peak to $24.00 to honor the 60% retracement, OR keep $23 + clarify the alternative-pass scenario at 45% retracement. Implementer fixture used $24.00.
2. **Plan §G.6 line 2671 stale DBW summary** (banked at R5): "undercut bonus + geometric_score capped at 1.0" → update to "geometric_score 1.10; composite capped at 1.0" matching the now-settled LOCK chain.
3. **DBW `_RECENT_STAGE_VALUES` consolidation** (banked at T-A.4.2 code-quality review): currently duplicate of `_STAGE_VALUES`. V2 either inline one reference or document the distinct forward-compat purpose explicitly.
4. **Multi-anchor candidate window iteration** (inherited T2.SB3 §6.4): iterate ALL windows per ticker, pick highest-scoring per pattern_class. Spec §3.6 v21+ territory.
5. **Foundation primitive `volume_trend_through_swings` consolidation**: HTF + DBW compute their own per-segment volume aggregates; if a future detector OR refactor opportunity arises, consider extending `volume_trend_through_swings` to handle pole + consolidation + trough segments.
6. **HTF empirical calibration**: if S3 operator-witnessed gate shows §10.6 STRICT bound NONE rejects > 50% of operator-recognized HTF setups, V2 calibration territory.
7. **DBW empirical undercut bonus distribution**: if S3 shows undercut bonus fires < 10% of operator-recognized DBW setups, V2 calibration may loosen the undercut threshold.

---

## §15 Files in scope (final state)

**Created** (production):
- `swing/patterns/high_tight_flag.py` (673 lines; `HighTightFlagEvidence` + `detect_high_tight_flag` + `_backward_slice_pole_peak` + `_identify_pole_start` + per-criterion check helpers; R2 bounded-search refinement of pole-peak selection)
- `swing/patterns/double_bottom_w.py` (600 lines; `DoubleBottomWEvidence` + `detect_double_bottom_w` + `_backward_slice_dbw_structure` + per-criterion check helpers; R1 M2 anchor_date contract enforcement + R1 M1 + R3 M1 evidence-vs-composite cap distinction)

**Modified** (production):
- `swing/pipeline/runner.py` (`_pattern_detect_registry` extended 3→5 detectors; composite_score derivation clamps `min(1.0, geometric_score)`; row construction persists raw `geometric_score=float(evidence.geometric_score)` + clamped `composite_score=float(composite_score)`)
- `swing/patterns/drift_logging.py` (extended per-detector feature shape registry for HTF + DBW via isinstance branching; new `_extract_center_trough_retracement` helper; `_DETECTOR_CLASS_VALUES` UNCHANGED)
- `swing/patterns/labeling.py` (narrative comment block updated from 3-detector to 5-detector scope; production function body UNCHANGED — class-agnostic since T2.SB3)
- `swing/patterns/spec_static.py` (DBW evidence range + composite_scoring_note clarified evidence vs composite cap distinction)
- `swing/patterns/__init__.py` (UNCHANGED — re-exports stay tight to `DETECTOR_PATTERN_CLASSES` per T-A.1.1 LOCK)

**Created** (tests):
- `tests/patterns/test_high_tight_flag.py` (15 tests post-R1+R2 fix bundles; 13 original + 2 R1 fix bundle + R2 bounded-search additions)
- `tests/patterns/test_double_bottom_w.py` (20 tests post-R1 fix bundle; 16 original + 4 R1 M2 anchor-aligned discriminating tests)
- `tests/integration/test_phase13_t2_sb4_detectors_e2e.py` (478 lines; 1 fast E2E; R3 Minor #2 docstring + R2 Minor #1 + R3 Major #1 asserts branch DBW vs other-4 detectors)

**Modified** (tests):
- `tests/patterns/test_drift_logging.py` (+3 new HTF/DBW tests; `test_all_5_detectors_emit_consistent_schema` extended in-place 3→5 detector schema coverage)
- `tests/patterns/test_foundation_integration.py` (`test_foundation_primitives_consumed_by_detectors_invariant` extended 3→5 detector introspection; faithful per-detector primitive inventory)
- `tests/patterns/test_retroactive_codex_evaluation.py` (+4 tests covering HTF + DBW high-stakes activation + agreement no-fire anti-regression)
- `tests/pipeline/test_step_pattern_detect.py` (+2 new tests; 8 existing updated for 5-detector contract; R2 Critical #1 multi-row regression test; R3 Major #1 3-way DB column + JSON assertion)
- `tests/integration/test_phase13_t2_sb3_detectors_e2e.py` (small updates; row counts 9→15 to reflect 5-detector emission per 3 candidate windows)

**Modified** (docs):
- `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md` (lines 290 + 294 `geometric_score` + `composite_score` table entries — R4 spec errata closure aligning derivative table with §5.8 + §10.5 BINDING locks)
- `docs/phase13-t2-sb4-detectors-batch2-dispatch-brief.md` (top-of-file errata note appended per R4 Minor #1)

**Created** (docs):
- `docs/phase13-t2-sb4-return-report.md` (THIS file)

---

*End of return report. Phase 13 T2.SB4 SHIPPED at `16f21d2` ready for operator-paired S2 + S3 gates + merge. 5 Codex rounds + 20th cumulative C.C lesson #6 BANKED CLEAN with scope-expanded discipline. ZERO trailer drift across 12 commits.*
