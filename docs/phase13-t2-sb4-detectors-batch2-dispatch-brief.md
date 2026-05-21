# Phase 13 T2.SB4 — Detectors batch 2 (high_tight_flag + double_bottom_w) dispatch brief

**Status:** READY FOR DISPATCH. Drafted 2026-05-20 PM #3 post-T3.SB2 SHIPPED + hotfix + housekeeping at main HEAD `be38c17`. Mid-sized sub-bundle (7 tasks; +60-100 fast tests projected per plan §H projections). Per plan §G.6 lines 1881-1971.

**Branch:** `phase13-t2-sb4-detectors-batch2` — branches from main HEAD `be38c17` at dispatch time (per plan §G.6 line 1885 + dispatch sequence §H.1: T2.SB4 branches AFTER T3.SB2 merge).

**Worktree:** create via `git worktree add .worktrees/phase13-t2-sb4-detectors-batch2 phase13-t2-sb4-detectors-batch2`.

**Time estimate:** orchestrator wall-clock 6-10 hours operator-paced (per `feedback_time_estimates_overstated.md` ÷3-5x for accuracy; T2.SB4 is mid-sized — symmetric to T2.SB3's detector-batch shape but only 2 detectors vs 3 + no pipeline-integration recon task + no separate retroactive-Codex task).

---

## §1 Scope summary

**2 remaining rule-based geometric detectors per spec §5.5 + §5.6**, completing the 5 V1 detector pattern classes locked at L2 (vcp + flat_base + cup_with_handle from T2.SB3 + high_tight_flag + double_bottom_w from T2.SB4). Same pipeline integration + drift_logging substrate as T2.SB3.

| Task | Title | Tests target |
|---|---|---|
| T-A.4.1 | High-tight-flag detector per spec §5.5 (6 criteria + §10.4 worked example + §10.6 STRICT bound NONE for consolidation width) | 10+ tests |
| T-A.4.2 | Double-bottom-W detector per spec §5.6 (8 criteria + undercut bonus + §10.5 worked example) | 12+ tests |
| T-A.4.3 | Pipeline `_step_pattern_detect` extension from 3 → 5 detectors | 1+ tests |
| T-A.4.4 | drift_logging extension for HTF + DBW per OQ-9 | 2+ tests |
| T-A.4.5 | Selective Codex T2.SB4 high-stakes clause activation per spec §5.9 step 4 (5-detector geometric_score) | 1+ tests |
| T-A.4.6 | T2.SB4 integration E2E (5-detector pattern_evaluations rows) | 1 fast E2E |
| T-A.4.7 | T2.SB4 closer — full suite + ruff sweep + 2 cross-bundle pin extensions | (closer) |

Per plan §G.6 verbatim. Cross-bundle pin work at T-A.4.7 closer:
- **EXTEND** `tests/patterns/test_foundation_integration.py:231` (`test_foundation_primitives_consumed_by_detectors_invariant`) — currently introspects 3 T2.SB3 detector modules per the un-skip body at T2.SB3 T-A.3.9; extend to introspect 5 modules (add `swing.patterns.high_tight_flag` + `swing.patterns.double_bottom_w`).
- **UN-SKIP** `test_drift_logging_5_detector_schema_consistent` per plan §H.3 row 7 (planted at T2.SB3 T-A.3.5; un-skips at T2.SB4 + Phase 13.5 — verify it exists in the codebase; if missing, plant + un-skip at T-A.4.4 OR T-A.4.7 closer).

### §1.1 Inheritance from T2.SB3 forward-binding lessons (per T2.SB3 return report §7)

T2.SB4 is the SECOND detector batch consuming the T2.SB2 foundation primitives + the T-A.1.7 corpus + the v20 `pattern_evaluations` table. Inherited disciplines:

**From T2.SB3 return report §7 (banked at `368784f` housekeeping):**
1. **PURE-function discipline LOCK L2 inherits verbatim** — detectors consume `(bars, candidate_window) -> <Detector>Evidence`; ZERO DB writes from inside the detector function itself. Pipeline `_step_pattern_detect` step layer owns DB writes (caller-tx; SELECT-then-INSERT idempotency; NO INSERT OR REPLACE per CLAUDE.md L3 gotcha).
2. **Frozen dataclass + `__post_init__` Literal[...] frozenset validation** for `HighTightFlagEvidence`, `DoubleBottomWEvidence`, and any sub-dataclasses (e.g., `PoleSegment`, `ConsolidationSegment`, `TroughEvent`, `UndercutEvent`). Honors cumulative CLAUDE.md gotcha "`Literal[...]` not runtime-enforced" (T-A.1.5b R3 M#1).
3. **Shared NaN sanitizer at `swing/patterns/_sanitize.py` REUSE** — do NOT duplicate. `_REQUIRED_COLUMNS = ('High', 'Low', 'Close', 'Volume')` lock. Reject NaN at entry via the shared sanitizer (or inline drop with explicit ValueError); zero-baseline-volume edge case returns 0.0 NOT NaN NOT raise.
4. **Per-mode anchor_date contract** — each detector implements its OWN backward-slice helper. HTF uses swing-HIGH (pole-peak anchor); DBW uses swing-LOW (trough-1 anchor). Do NOT share helpers across detectors with different swing-direction semantics.
5. **Bar-clipping at detector entry** — apply to HTF + DBW the SAME way `cup_with_handle.py:631-636` does (clip `bars` to `bars.index <= candidate_window.end_date` BEFORE anchor identification). RESOLVED at T2.SB3 R1 Major #1 (`detect_cup_with_handle()` future-bar leak). Discriminating test pattern: plant a future-bar lowest-low (or highest-high for HTF) + assert detected anchor date ≤ window.end_date. **BINDING** per T2.SB3 forward-binding lesson #2.
6. **HTF naming `consolidation_*` (NOT `flag_*`) per existing CLAUDE.md gotcha + T-A.1.8 Deficiency 3.** Spec §5.5 names the post-pole sub-window `consolidation_*` per criterion #3 + #4 lock strings + Structural evidence enumeration (e.g., `consolidation_start_date`, `consolidation_end_date`, `consolidation_pullback_pct`, `consolidation_width_pct`, `consolidation_duration_days`). Operator's colloquial "flag_start_date / flag_end_date" terminology is a misnomer. Locked at `tests/patterns/test_spec_static.py::test_high_tight_flag_consolidation_naming_matches_spec_5_5_not_flag_naming`.
7. **Cross-bundle pin extension** at `tests/patterns/test_foundation_integration.py:231` per §1 above — extend test body to include `swing.patterns.high_tight_flag` + `swing.patterns.double_bottom_w` module introspection via `inspect.getsource` verification of foundation primitive references (mirror T2.SB3 T-A.3.9 pattern).
8. **Pipeline `_step_pattern_detect` extension pattern** — T2.SB4 detectors plug into the SAME step (per spec §3.6 + T-A.3.6 architecture); extend `_pattern_detect_registry()` helper at runner.py to add the 2 new detector classes; Pass 1 / Pass 2 architecture inherits (two-pass-then-reconcile-then-serialize per T2.SB3 R4 architectural refinement; per T2.SB3 forward-binding lesson #1).
9. **`_DETECTOR_CLASS_VALUES` 5-value frozenset in drift_logging.py** already includes "high_tight_flag" + "double_bottom_w" — schema-CHECK-vs-Python-constant pre-aligned per §A.14 atomic-landing LOCK; T-A.4.4 only extends the per-detector feature shape registry (does NOT widen the constant).
10. **`EvalRunResolutionError` typed-exception precedent** (T2.SB3 R2 Major #3) — N/A for T2.SB4 detector code paths (T-A.4.1/4.2 are pure functions consuming bars+window; they don't derive session-anchor dates). VERIFY at T-A.4.6 E2E if any session-anchor derivation appears; if so, honor the pattern.

**From T2.SB1 forward-binding lesson #8 (still V2-bankable):**
11. **HTF consolidation tightness** — if T-A.4.1 empirical fixture analysis shows the §5.5 STRICT bound (NONE tolerance for consolidation_width_pct per §10.4 errata + §10.6 LOCK) rejects realistic HTF setups, FLAG for operator escalation at T-A.4.1 completion (do NOT widen unilaterally). Per spec §10.6 LOCK: HTF consolidation_width_pct has STRICT bound NONE; the §10.4 errata case (15.6% rejected) is intentional.
12. **DBW undercut bonus capped at 1.0** per spec §10.5 — `geometric_score` increments by 0.10 on undercut detection; cap at 1.0 (per `min(geometric_score + undercut_bonus, 1.0)`). Discriminating test at T-A.4.2 (`test_dbw_passes_all_criteria_with_undercut_geometric_score_capped_1_0`) enforces.

### §1.2 Inheritance from T3.SB2 hotfix + 20th C.C lesson #6 BANKED-WITH-CAVEAT scope-expansion

**NEW from the T3.SB2 post-merge hotfix at `cf3c489` (closes critical `_call_endpoint` surface-guard defect that T3.SB1 + T3.SB2's combined ~10 Codex rounds + 4 slow E2E + cross-bundle pin all MISSED)**:

13. **C.C lesson #6 pre-Codex orchestrator-side review scope expansion is BINDING for the 20th cumulative validation expected at this dispatch.** When the brief touches a constant (frozenset / tuple / enum) that's mirrored elsewhere in the codebase, the pre-Codex review MUST grep `swing/` for redundant hardcoded copies of the OLD value tuple AND verify each downstream consumer is widened consistently. Specifically for T2.SB4: the `_DETECTOR_CLASS_VALUES` frozenset in `swing/patterns/drift_logging.py` is the canonical 5-value detector enum already aligned per §A.14; verify NO other hardcoded `("vcp", "flat_base", "cup_with_handle")` 3-value tuples exist anywhere in `swing/` that would silently reject `"high_tight_flag"` or `"double_bottom_w"`. Per CLAUDE.md gotcha "Schema-CHECK widening MUST audit ALL Python-side surface guards across the repo, not just the canonical constant" (banked at `9899bda` housekeeping).
14. **T2.SB4 has NO Schwab integration scope** — detectors are pure functions consuming OhlcvCache-routed bars; no Schwab Trader API consumers; no surface-guard concerns specific to this dispatch. BUT the cumulative discipline (grep for hardcoded duplicates of any constant the brief widens or extends) still applies — particularly for `_DETECTOR_CLASS_VALUES` + `_pattern_detect_registry()` callsites.

---

## §2 Per-task acceptance criteria (per plan §G.6 verbatim)

| Task | Title | Acceptance |
|---|---|---|
| T-A.4.1 | High-tight flag detector per spec §5.5 | 10+ discriminating tests pass per plan §G.6 step 1 enumeration; §10.4 worked example covered (14.8% PASS strict bound + 15.6% REJECT per §10.6 STRICT bound NONE); `HighTightFlagEvidence` frozen dataclass with `__post_init__` Literal[...] frozenset validation; bar-clipping at entry; consolidation_* naming (NOT flag_*) |
| T-A.4.2 | Double-bottom-W detector per spec §5.6 | 12+ discriminating tests pass per plan §G.6 step 1 enumeration; §10.5 worked example covered (undercut bonus → 1.0 cap; non-undercut → 1.0 without bonus); `DoubleBottomWEvidence` frozen dataclass; stage 4→2 transition test; criterion #1-#7 boundary tests (optional #7 volume rises increments evidence) |
| T-A.4.3 | Pipeline `_step_pattern_detect` extension from 3 → 5 detectors | 1+ tests pass; step invokes all 5 detectors per candidate window; emits 1 pattern_evaluations row per (ticker, pattern_class); two-pass-then-reconcile-then-serialize architecture preserved |
| T-A.4.4 | Drift logging extension for HTF + DBW per OQ-9 | 2+ tests pass; `capture_feature_distribution` correctly emits per-detector feature distributions for HTF + DBW; per-detector feature shape registry extended in `swing/patterns/drift_logging.py`; `_DETECTOR_CLASS_VALUES` frozenset UNCHANGED (5 values already aligned at T-A.1.1) |
| T-A.4.5 | Selective Codex T2.SB4 high-stakes clause activation | 1+ tests pass; `retroactive_codex_evaluation_against_corpus()` now uses ALL 5 detectors' geometric_score (HTF + DBW corpus rows now eligible); SELECT-first idempotency PRECEDES payload validation per Phase 12 C.C R1 Major #2 |
| T-A.4.6 | T2.SB4 integration E2E | 1 fast E2E PASSES; seeds 5 candidate windows (one per pattern class); invokes `_step_pattern_detect`; asserts 5 pattern_evaluations rows per applicable window; composite_score = geometric_score (template_match still NULL pre-T2.SB5) |
| T-A.4.7 | T2.SB4 closer — full suite + ruff + 2 cross-bundle pin extensions | Full fast-test suite + ruff sweep PASS; `test_foundation_primitives_consumed_by_detectors_invariant` EXTENDED to introspect 5 detector modules; `test_drift_logging_5_detector_schema_consistent` UN-SKIPPED (verify existence; plant if T-A.3.5 didn't) |

**Recommended ordering**: T-A.4.1 (HTF; densest spec at 6 criteria; bar-clipping discipline establishes the pattern) → T-A.4.2 (DBW; undercut bonus + cap; trough-1 anchor) → T-A.4.3 (pipeline 5-detector extension; sequential prerequisite for E2E) → T-A.4.4 (drift_logging extension; feature shape registry only; NO constant widening) → T-A.4.5 (Codex high-stakes activation; consumes 5-detector geometric_score) → T-A.4.6 (E2E; needs all 5 detectors landed) → T-A.4.7 (closer + cross-bundle pin extensions).

---

## §3 Files in scope

**Create** (2 production modules + 2 unit-test files + 1 E2E file):
- `swing/patterns/high_tight_flag.py`
- `swing/patterns/double_bottom_w.py`
- `tests/patterns/test_high_tight_flag.py`
- `tests/patterns/test_double_bottom_w.py`
- `tests/integration/test_phase13_t2_sb4_detectors_e2e.py` (1 fast E2E)

**Modify**:
- `swing/pipeline/runner.py` (extend `_step_pattern_detect` + `_pattern_detect_registry()` helper to invoke 5 detectors instead of 3)
- `swing/patterns/drift_logging.py` (extend per-detector feature shape registry for HTF + DBW; NO constant widening — `_DETECTOR_CLASS_VALUES` 5-value frozenset already aligned at T-A.1.1)
- `swing/patterns/labeling.py` (extend `retroactive_codex_evaluation_against_corpus()` to consume HTF + DBW geometric_score per T-A.4.5)
- `swing/patterns/__init__.py` (re-export new detector classes per the namespace convention established at T-A.1.1)
- `tests/patterns/test_foundation_integration.py:231` (EXTEND `test_foundation_primitives_consumed_by_detectors_invariant` body to introspect 5 detector modules — was 3 at T2.SB3 T-A.3.9)
- `tests/patterns/test_drift_logging.py` (extend if `test_drift_logging_5_detector_schema_consistent` was planted at T-A.3.5; un-skip at T-A.4.7 if so; plant + un-skip if not)

**NOT in scope (V2 / future sub-bundles)**:
- Template matching DTW (T2.SB5 territory)
- Review auto-fill (T3.SB3 territory)
- Closed-loop / charts surface (T2.SB6 territory)
- Schwab integration (none for detectors; T2.SB4 has zero Schwab API consumers)
- Schema changes (v20 LOCKED per spec §B.4; if any test surfaces a schema need, STOP + escalate per dispatch §B.6 precedent)
- HTF consolidation_width tolerance widening (per §1.1 #11; flag for operator escalation if empirical data demands; do NOT widen unilaterally — §10.6 LOCK STRICT bound NONE is intentional per §10.4 errata)

---

## §4 Watch items (cumulative discipline; banked across Phase 12 + 12.5 + 13)

### §4.1 T2.SB4-specific watch items

1. **PURE-FUNCTION DISCIPLINE preserved for detectors** per LOCK L2 + T2.SB3 forward-binding lesson #1: each detector consumes `(bars, candidate_window) -> <Detector>Evidence`; ZERO DB writes from inside; pipeline step layer owns transactions.
2. **Spec §5.5 + §5.6 lock fidelity**: every criterion + tolerance value + boundary case MUST match spec verbatim. Implementer SHOULD grep spec for the criterion text; do NOT paraphrase.
3. **§10.6 STRICT bound NONE for HTF consolidation_width_pct** uniform across all 3 HTF criteria (#3 width + #5 volume drop + #6 pivot offset). The §10.4 errata case (15.6% width rejected) is intentional; do NOT widen.
4. **§10.5 DBW undercut bonus capped at 1.0** per spec §5.6 + §10.5 — `geometric_score = min(base_score + undercut_bonus, 1.0)` where undercut_bonus = 0.10 on detection.
5. **HTF naming `consolidation_*` (NOT `flag_*`)** BINDING per CLAUDE.md gotcha + T-A.1.8 Deficiency 3. Locked at `test_high_tight_flag_consolidation_naming_matches_spec_5_5_not_flag_naming`; T-A.4.1 implementation MUST use `consolidation_*` field names in `HighTightFlagEvidence` dataclass + all helpers.
6. **DBW criterion #1 stage 4→2 transition** — discriminating test asserts stage transition is detected (not raw stage 2 entry); per spec §5.6 criterion #1 lock string.
7. **Frozen dataclass + `__post_init__` Literal[...] frozenset validation** for every detector evidence dataclass (HighTightFlagEvidence + DoubleBottomWEvidence + sub-dataclasses).
8. **Bar-clipping at detector entry per T2.SB3 forward-binding lesson #2**: clip `bars` to `bars.index <= candidate_window.end_date` BEFORE anchor identification. Discriminating test: plant future-bar highest-high (HTF) / lowest-low (DBW) + assert anchor date ≤ window.end_date.
9. **NaN-handling**: detectors REJECT NaN at entry via the shared `sanitize_bars()` from `swing/patterns/_sanitize.py`; zero-baseline-volume edge case returns 0.0 NOT NaN NOT raise.
10. **Real-shape OHLC fixtures**: detector unit tests MUST use realistic OHLC (H > Close > L divergence + Volume > 0); reference T-A.1.7 corpus at `data/phase13-t2-sb1-corpus/pattern_exemplars_dump.jsonl` for HTF + DBW exemplar shape templates.
11. **DBW criterion #4 trough_2 within 5% of trough_1** — boundary cases: 3% undercut (PASS within 5% bound); 6% undercut (FAIL outside 5% bound); 5% boundary (PASS at the boundary per inclusive bound semantics).
12. **DBW optional criterion #7 volume_rises increments evidence (NOT score)** — `geometric_score` is unaffected; `structural_evidence_json` carries `volume_rises_on_trough_2_to_center_peak: bool` for downstream visibility. Per spec §5.6 criterion #7 optional lock.

### §4.2 Pipeline + drift_logging + Codex extension watch items (T-A.4.3-4.5)

13. **`_step_pattern_detect` extension preserves two-pass-then-reconcile-then-serialize architecture** per T2.SB3 R4 architectural refinement. Pass 1 (outside `lease.fenced_write()`): seed universe from existing rows + emit_queue. Pass 2 (inside `lease.fenced_write()`): re-read canonical existing ONCE → reconcile emit_queue → build FINAL universe → serialize EVERY surviving row with same universe → INSERTs.
14. **drift_logging per-detector feature shape registry MUST be data-driven** (NOT hardcoded enum match) — extend the registry dict; do NOT add new code paths per detector class. Preserves the `_DETECTOR_CLASS_VALUES` frozenset alignment at T-A.1.1.
15. **Selective Codex high-stakes clause activation** per spec §5.9 step 4 + OQ-5 BINDING: T2.SB4 activates HIGH-STAKES disagreement clause for all 5 detectors (T2.SB1 was random 15% only; T2.SB3 added high-stakes for 3 detectors; T2.SB4 closes the loop for 5).
16. **SELECT-first idempotency PRECEDES payload validation** per Phase 12 C.C R1 Major #2 + cumulative gotcha — for the retroactive Codex evaluation path, re-invoking against the same corpus row does NOT double-fire Codex.

### §4.3 Cross-bundle pin watch items (T-A.4.7)

17. **EXTEND `test_foundation_primitives_consumed_by_detectors_invariant`** at `tests/patterns/test_foundation_integration.py:231` — was un-skipped at T2.SB3 T-A.3.9 with 3-module body (`vcp` + `flat_base` + `cup_with_handle`); T-A.4.7 extends to introspect 5 modules. Use the same `inspect.getsource` introspection pattern + verify each new detector references the expected foundation primitives (`CandidateWindow`, `current_stage`, `extract_zigzag_swings`, `adaptive_initial_threshold_pct`; `volume_trend_through_swings` for HTF given the pole-volume + consolidation-volume-drop semantics).
18. **UN-SKIP `test_drift_logging_5_detector_schema_consistent`** per plan §H.3 row 7 (planted at T2.SB3 T-A.3.5; un-skips at T2.SB4 + Phase 13.5). **VERIFY existence first** — if the test was NOT planted at T-A.3.5 (orchestrator did not verify against T2.SB3 actuals; plan §H.3 may be aspirational), then PLANT + un-skip at T-A.4.7 closer with a body that introspects `_DETECTOR_CLASS_VALUES` against the FeatureDistributionLog dataclass shape across all 5 detector classes.

### §4.4 Cumulative process discipline

19. **Pre-Codex orchestrator-side review (C.C lesson #6 BINDING; 20th cumulative validation expected with SCOPE-EXPANDED discipline)** — implementer dispatches a focused reviewer subagent with this brief's §3 file-scope + §4 watch items + §5 done criteria + §6 LOCKs as anchors BEFORE invoking Codex MCP. **NEW SCOPE EXPANSION for 20th validation (per T3.SB2 hotfix forensic banked at `cf3c489`)**: pre-Codex review MUST grep `swing/` for any hardcoded duplicates of constants the brief widens or extends (e.g., the `_DETECTOR_CLASS_VALUES` 5-tuple, the `_pattern_detect_registry()` per-detector class list). Reference: 19th cumulative validation BANKED-WITH-CAVEAT after operator-witnessed S2 caught the surface-guard defect that 5 Codex rounds + slow E2E + cross-bundle pin all MISSED. Per CLAUDE.md gotcha "Schema-CHECK widening MUST audit ALL Python-side surface guards across the repo, not just the canonical constant."
20. **NO `Co-Authored-By` footer** — cumulative ~282+ commit streak ZERO trailer drift through T3.SB2 + hotfix + housekeeping + script-track; do NOT regress. Per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15): explicit citation in commit messages required.
21. **`python -m swing.cli` from worktree cwd**, NOT bare `swing` (memory `feedback_worktree_cli_invocation`).
22. **ASCII-only on any new CLI/print path** — runtime CLI paths bind (Windows cp1252 footgun); detector internal logging is fine (logged via stdlib logger which handles encoding).
23. **Edit tool for per-file edits** when fixing E501 / type / import-order issues — do NOT bulk-rewrite (Phase 12.5 #3 L-W4 precedent).
24. **Cite the discipline in commit messages** (matches all prior T1.SB0 + T2.SB1 + T3.SB1 + T2.SB2 + T2.SB3 + T3.SB2 + hotfix commit-message precedent).
25. **TDD discipline per task** via `superpowers:test-driven-development` (write failing test → see fail → minimal implementation → see pass → commit).

---

## §5 Done criteria

### §5.1 S1 (inline; implementer self-verifies before invoking Codex)

- [ ] All 7 T-A.4.X tasks committed per plan §G.6 acceptance criteria.
- [ ] `python -m pytest -m "not slow" -q -n auto` PASS post-merge. **Expected**: 5328 + ~60-100 new fast tests = ~5390-5430 total; 0 failures; ≤4 skipped (T-A.4.7 un-skip of `test_drift_logging_5_detector_schema_consistent` brings skipped from 4 → 3 if it was planted; otherwise plant + un-skip net 0 NEW skips).
- [ ] `python -m pytest -m slow tests/integration/test_phase13_t2_sb4_detectors_e2e.py -q` PASS for any new slow E2E (likely NONE for T2.SB4 — fast E2E only per plan §G.6 T-A.4.6; verify at recon).
- [ ] `ruff check swing/` clean (0 E501).
- [ ] Schema version unchanged at v20.
- [ ] Pre-Codex orchestrator-side review dispatched + verdict captured (20th cumulative C.C lesson #6 validation expected CLEAN with scope-expanded discipline — grep-verified zero hardcoded duplicates of 5-detector class list outside `_DETECTOR_CLASS_VALUES`).
- [ ] All commits on branch `phase13-t2-sb4-detectors-batch2` have empty `Co-Authored-By` trailer (verified via `git log --pretty='%(trailers:key=Co-Authored-By)' phase13-t2-sb4-detectors-batch2 --not main | grep -c .` returning 0).
- [ ] Codex MCP adversarial-critic chain converges to `NO_NEW_CRITICAL_MAJOR` (expected 2-4 rounds based on mid-sized scope + detector-batch symmetric inheritance from T2.SB3).

### §5.2 S2-S3 (operator-paired post-merge per plan §G.6 lines 1967-1969)

- **S2 (CLI)**: `python -m swing.cli pipeline run` against operator's production candidate pool. Verify `_step_pattern_detect` lands `pattern_evaluations` rows across all 5 detector classes (when candidate windows of each pattern class are present); operator inspects rows for plausible verdicts (geometric_score in [0, 1]; structural_evidence_json populated; feature_distribution_log_json populated with run-level histograms across 5 detector classes).
- **S3 (cross-check)**: operator visually compares detector output for a known historical HTF setup AND a known historical DBW setup; verifies detector verdicts match subjective assessment. Opportunity to empirically validate the §10.4 HTF STRICT bound + §10.5 DBW undercut bonus against real HTF/DBW exemplars from the T-A.1.7 corpus (if HTF/DBW exemplars present) or operator's known prior setups.

---

## §6 LOCKs (do not deviate without operator escalation)

- **L1**: Spec §5.5 + §5.6 + §10.4 + §10.5 + §10.6 STRICT bound NONE criteria + tolerances bound verbatim. Implementer reads spec; does NOT paraphrase.
- **L2**: ZERO DB writes inside detector functions (`detect_high_tight_flag`, `detect_double_bottom_w`). All DB writes routed through `_step_pattern_detect` step layer with caller-tx discipline (preserved from T2.SB3 architecture).
- **L3**: NO `INSERT OR REPLACE` on `pattern_evaluations` writes. SELECT-then-INSERT idempotency pattern (preserved from T2.SB3 Pass 2 reconcile-then-serialize at runner.py).
- **L4**: Cross-bundle pin EXTENSIONS at T-A.4.7 closer per §1 + §4.3 #17 + #18. Leaving stale (3-detector body OR skipped state) violates plan §H.3 schedule.
- **L5**: HTF §10.6 STRICT bound NONE for consolidation_width_pct preserved. If T-A.4.1 empirical fixture analysis demands widening, escalate to operator with evidence — do NOT widen unilaterally.
- **L6**: Branch base = main HEAD `be38c17` at dispatch time. Verify at T-A.4.1 Step 0: `git merge-base --is-ancestor be38c17 HEAD` returns 0.
- **L7**: Frozen dataclasses (HighTightFlagEvidence + DoubleBottomWEvidence) carry `__post_init__` Literal[...] frozenset validation honoring T-A.1.5b R3 M#1 CLAUDE.md gotcha.
- **L8**: HTF naming `consolidation_*` (NOT `flag_*`) per CLAUDE.md gotcha + T-A.1.8 Deficiency 3. `HighTightFlagEvidence` field names + all helpers use `consolidation_*`. Test `test_high_tight_flag_consolidation_naming_matches_spec_5_5_not_flag_naming` at `tests/patterns/test_spec_static.py` MUST continue to pass.
- **L9**: `_DETECTOR_CLASS_VALUES` 5-value frozenset in `swing/patterns/drift_logging.py` UNCHANGED (already aligned at T-A.1.1 per §A.14 atomic-landing LOCK). T-A.4.4 extends per-detector feature shape registry; does NOT widen the constant.
- **L10**: Bar-clipping at detector entry per T2.SB3 forward-binding lesson #2 (clip bars to `bars.index <= candidate_window.end_date` BEFORE anchor identification).

---

## §7 Reference materials (read before dispatching)

- **Plan**: `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` §G.6 lines 1881-1971 (T2.SB4 verbatim 7-task spec) + §H.3 line ~2620 (cross-bundle pin schedule rows for `test_foundation_primitives_consumed_by_detectors_invariant` un-skip + `test_drift_logging_5_detector_schema_consistent` un-skip).
- **Spec**: `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`:
  - §5.5 HTF (6 criteria + §10.4 worked example + errata)
  - §5.6 DBW (8 criteria + undercut bonus + §10.5 worked example)
  - §5.9 step 4 selective Codex high-stakes clause (now activated for 5 detectors at T2.SB4)
  - §10.4 HTF worked example + 15.6% width REJECT case
  - §10.5 DBW worked example + undercut bonus → 1.0 cap
  - §10.6 STRICT bound NONE LOCK for HTF consolidation_width_pct
- **T2.SB3 return report** at `docs/phase13-t2-sb3-return-report.md` §7 — 9 forward-binding lessons banked for T2.SB4 inheritance (verbatim sources for §1.1 above).
- **T2.SB3 dispatch brief** at `docs/phase13-t2-sb3-detectors-batch1-dispatch-brief.md` — template for this brief's shape; detector batch pattern.
- **T2.SB3 implementation references** at `swing/patterns/vcp.py` + `swing/patterns/flat_base.py` + `swing/patterns/cup_with_handle.py` + `swing/patterns/drift_logging.py` + `swing/patterns/_sanitize.py` — mirror the dataclass + function shapes; reuse `sanitize_bars()` + foundation primitives.
- **T2.SB3 pipeline integration recon** at `docs/phase13-t2-sb3-recon.md` — 314-line recon doc; T-A.4.3 extends `_step_pattern_detect` per the established architecture (NO new recon needed for T2.SB4; the integration point + per-detector ordering + write discipline are already locked).
- **T-A.1.7 corpus manifest** at `data/phase13-t2-sb1-corpus/README.md` + JSONL dump at `data/phase13-t2-sb1-corpus/pattern_exemplars_dump.jsonl` — HTF + DBW gold/silver exemplars for unit-test fixture inspiration + S3 visual cross-check.
- **CLAUDE.md gotchas relevant to T2.SB4**:
  - `Literal[...]` not runtime-enforced (T-A.1.5b R3 M#1 inherited)
  - ASCII-only on runtime CLI paths
  - SQLite INSERT OR REPLACE is DELETE + INSERT semantically (per L3 LOCK)
  - SELECT-first idempotency MUST precede payload validation (per T-A.4.5 watch item #16)
  - HTF post-pole sub-window is `consolidation_*` not `flag_*` (BINDING per L8)
  - Schema-CHECK widening MUST audit ALL Python-side surface guards across the repo (NEW from T3.SB2 hotfix; informs 20th C.C lesson #6 scope-expanded discipline)

---

## §8 Post-dispatch housekeeping checklist (orchestrator-inline)

When T2.SB4 merge ships:

1. **CLAUDE.md line 3 refresh** — update HEAD reference + mention T2.SB4 SHIPPED + 20th cumulative C.C lesson #6 validation; mention any NEW gotchas surfaced.
2. **phase3e-todo.md** — new top entry for T2.SB4 SHIPPED with: Codex chain shape + any ACCEPT-WITH-RATIONALE banks + forward-binding lessons for T2.SB5 / T3.SB3 / T2.SB6 inheritance + per-detector empirical observations (HTF STRICT bound rejection rate against T-A.1.7 corpus; DBW undercut bonus distribution); cross-bundle pin extension confirmations.
3. **orchestrator-context.md** — refresh current state; demote former current to Prior; archive-split per size-check trigger (Prior state count was 10 at cap post-housekeeping; demote pushes to 11; archive oldest Prior to `orchestrator-context-archive.md` "Appended 2026-05-2X" section per retention discipline).
4. **orchestrator-context-archive.md** — new "Appended 2026-05-2X" section with archived Prior verbatim.
5. **Streaks update** — bank the 20th cumulative C.C lesson #6 validation (if CLEAN with scope-expanded discipline applied); bank ~292+ cumulative ZERO Co-Authored-By streak (T2.SB4 expected ~10-15 commits).
6. **5-detector completion celebration**: T2.SB4 completes the L2 5-pattern set (vcp + flat_base + cup_with_handle + high_tight_flag + double_bottom_w). Pattern detection substrate is feature-complete for V1; T2.SB5 template matching + T2.SB6 closed-loop now layer on top.

---

## §9 Forward-binding to T2.SB5 + T3.SB3 + T2.SB6

T2.SB5 = Template matching DTW + composite scoring (6 tasks; plan §G.7). Inherits ALL 5 detector substrate from T2.SB4. NEW: template matching layer per spec §5.7 + OQ-4; composite scoring formula per spec §5.8; 120s/run benchmark gate.

T3.SB3 = Review auto-fill consuming OhlcvCache (per spec §6.3). Inherits T3.SB1 + T3.SB2 hidden-anchor + value-validation + recovery anchor-clear discipline verbatim. T3.SB3 consumes OhlcvCache patterns (NOT Schwab Trader API per spec §6.3); auto-fill is from prior reviews + Phase 8 daily_management_records + candle data.

T2.SB6 = Closed-loop surface + Theme 1 annotated charts (8 tasks per plan §G.9; includes T-A.6.6b Deficiency 1 fold-in from T-A.1.6). Inherits ALL Phase 13 detector substrate; consumes pattern_evaluations + structural_evidence_json for annotated chart rendering.

**Forward-binding lessons expected from T2.SB4 to T2.SB5 + downstream (per detector empirical observations):**
- HTF STRICT bound NONE rejection rate against T-A.1.7 corpus (if elevated, V2 calibration territory).
- DBW undercut bonus distribution (does undercut fire frequently enough on real data, or is it a rare edge case?).
- 5-detector pipeline integration latency (does the 2-detector extension materially slow pipeline runs?).
- Cross-bundle pin extension pattern (T-A.4.7 establishes the precedent for `test_foundation_primitives_consumed_by_detectors_invariant` body extensions in future detector-adding sub-bundles — Phase 13.5 + V2).
- 20th cumulative C.C lesson #6 validation with scope-expanded discipline (sets precedent for all future widening dispatches).
- ZERO `Co-Authored-By` trailer streak (~292+ cumulative commits expected post-T2.SB4 merge + housekeeping).

---

*End of dispatch brief. Phase 13 T2.SB4 (7 tasks; +60-100 fast tests + likely 1 fast E2E projected; no slow E2E) — SECOND detector batch completing the 5 V1 pattern class set per L2 LOCK. Inherits T2.SB3 detector patterns verbatim (PURE-function discipline + frozen dataclasses + shared NaN sanitizer + per-mode anchor_date contract + bar-clipping + HTF consolidation_* naming + cross-bundle pin extension + pipeline `_step_pattern_detect` extension + two-pass-reconcile-serialize). 2-4 Codex rounds expected for mid-sized scope. **20th cumulative C.C lesson #6 validation expected with SCOPE-EXPANDED discipline** (pre-Codex review MUST grep `swing/` for hardcoded duplicates of any widened/extended constants per T3.SB2 hotfix forensic). ZERO Co-Authored-By footer drift streak (~282+ commits at handoff) preserved.*
