# Phase 13 T2.SB5 — Template matching (DTW + composite scoring) dispatch brief

**Status:** READY FOR DISPATCH. Drafted 2026-05-21 post-T2.SB4 SHIPPED + housekeeping at main HEAD `7f49b82` (handoff brief committed). Mid-sized sub-bundle (6 tasks; +50-80 fast tests projected per plan §H projections + 1 pytest-benchmark slow gate). Per plan §G.7 lines 1973-2046.

**Branch:** `phase13-t2-sb5-template-matching` — branches from main HEAD `7f49b82` at dispatch time (per plan §G.7 line 1977 + dispatch sequence §H.1: T2.SB5 branches AFTER T2.SB4 merge).

**Worktree:** create via `git worktree add .worktrees/phase13-t2-sb5-template-matching phase13-t2-sb5-template-matching`.

**Time estimate:** orchestrator wall-clock 5-8 hours operator-paced (per `feedback_time_estimates_overstated.md` ÷3-5x for accuracy; T2.SB5 is mid-sized — symmetric to T2.SB4 detector-batch shape but only 6 tasks vs 7 + introduces benchmark gate as new discipline weight).

---

## §1 Scope summary

**Template matching (DTW with Sakoe-Chiba band) + composite scoring formula + 120s/run benchmark gate per spec §5.7 + §5.8 + OQ-4 BINDING.** T2.SB5 layers the SECONDARY signal on top of the 5-detector PRIMARY substrate completed at T2.SB4 (5-detector V1 set COMPLETE per L2 LOCK). Consumes existing `pattern_evaluations` rows + `pattern_exemplars` corpus; populates `template_match_score` + `template_match_nearest_exemplar_ids_json` columns + recomputes `composite_score` per spec §5.8 formula.

| Task | Title | Tests target |
|---|---|---|
| T-A.5.1 | DTW core + Sakoe-Chiba band per spec §5.7 + OQ-4 | 6+ tests |
| T-A.5.2 | `match_forward` + `match_reverse` retrieval per spec §5.7 + §5.7 pruning LOCK | 6+ tests |
| T-A.5.3 | Composite scoring per spec §5.8 (`compute_composite_score`) | 4+ tests |
| T-A.5.4 | Pipeline `_step_pattern_detect` integration with template matching | 2+ tests |
| T-A.5.5 | pytest-benchmark 120s gate per OQ-4 | 1 benchmark (slow-marked) |
| T-A.5.6 | T2.SB5 closer — integration E2E + ruff sweep + 2 cross-bundle pins | 1 fast E2E + 2 cross-bundle pin un-skips/plants |

Per plan §G.7 verbatim. Cross-bundle pin work at T-A.5.6 closer:

- **UN-SKIP** `test_pattern_exemplars_schema_shape_invariant` at `tests/data/test_v20_migration.py:840` (currently `@pytest.mark.skip` reason "un-skip at T2.SB3 + T2.SB5"; T2.SB3 closer did NOT un-skip it per `git grep` audit on main HEAD `7f49b82` — T2.SB5 closes this lag). Body already correct (verifies `pattern_exemplars` 20-column schema shape post-T2.SB5 consumes the table); just remove `@pytest.mark.skip` decorator + verify PASS.
- **PLANT + UN-SKIP** `test_pattern_evaluations_template_match_score_persistable` per plan §H.3 row 8. Per `git grep` audit on main HEAD `7f49b82`, this test does NOT exist anywhere in the codebase (plan §H.3 says "planted at T2.SB3 T-A.3.6" but T2.SB3 did NOT plant it). T2.SB5 PLANTS + un-skips at T-A.5.6 closer with a body that: (a) ensures `pattern_evaluations.template_match_score` accepts NULL (pre-T2.SB5 path) + (b) accepts a float value in [0.0, 1.0] post-T2.SB5 implementation (round-trip an INSERT/SELECT with a known float; assert exact equality within float epsilon). Mirror the cross-bundle pin name + plan §H.3 row 8 schedule.

### §1.1 Inheritance from T2.SB4 forward-binding lessons (per T2.SB4 return report §7)

T2.SB5 is the SECONDARY signal layer consuming the T2.SB3 + T2.SB4 detector substrate + the T-A.1.7 corpus. Inherited disciplines (BINDING for T2.SB5):

1. **Evidence-tier vs composite-tier score cap distinction LOCKED** per T2.SB4 R2 Critical #1 + R3 Major #1 + R1 Major #1 lesson family (CLAUDE.md gotcha banked at `c44aebd`):
   - `pattern_evaluations.geometric_score` carries RAW evidence (unconstrained REAL; DBW reaches 1.10 per spec §5.8 line 718 + §10.5 line 1325 undercut bonus)
   - `pattern_evaluations.composite_score` carries CLAMPED composite (always `[0.0, 1.0]` per spec §5.8 line 712 + §5.11 LOCK; downstream `_composite_score_histogram` requires this)
   - `structural_evidence_json` carries RAW evidence
   - **The current pipeline composite formula at `swing/pipeline/runner.py:1677` is `composite_score = min(1.0, geometric_score)` (template_match=None pre-T2.SB5 LOCK per spec §5.8 line 720).** T2.SB5 replaces this with the full §5.8 formula but **MUST preserve the `min(1.0, ...)` wrap** — DBW evidence at 1.10 + a template_match_score at 1.0 yields `0.60 × 1.10 + 0.40 × 1.0 = 1.06` which without clamp would re-poison drift_logging.
2. **Bounded backward-slice search discipline** per T2.SB4 R2 Major #2 — if T2.SB5 template matching adds any backward-slice or windowed search (e.g., matching a candidate against a historical exemplar's bar range), bound the search window by spec's max-duration constraints + add discriminating tests at the boundary.
3. **DBW anchor_date contract via `anchor_reason.startswith("zigzag_pivot")`** per T2.SB4 R1 Major #2 — `pattern_evaluations.window_start_date` + `window_end_date` are populated from `CandidateWindow.start_date` + `end_date`; if T2.SB5 template matching consumes `anchor_date` semantic (NOT just window extent), enforce the mode tag check explicitly (zigzag_pivot = base START; ma_crossover / high_low_breakout = TRIGGER EVENT).
4. **Pre-Codex review must cross-check spec source-of-truth against dispatch brief sketches** per T2.SB4 R1 M1 lesson — **BINDING for T2.SB5 pre-Codex review**. When this brief sketches the §5.8 composite formula or §5.7 pruning constants or DTW band parameters, the pre-Codex review MUST grep spec §5.7 + §5.8 BINDING text and verify byte-fidelity. (Implementer-side note: plan §G.7 references `§D.4` + `§D.5 pruning LOCK` but the spec has NO §D section — those are plan-side reference drift. Spec source-of-truth is §5.7 (lines 667-706 incl. 4-item pruning LOCK at lines 700-704) + §5.8 (lines 708-724 composite formula + line 720 fallback LOCK + line 724 calibration LOCK).)

### §1.2 Inheritance from T2.SB3 + T2.SB4 detector substrate (5-detector V1 set COMPLETE per L2 LOCK)

5. **5-detector substrate consumed verbatim**: all 5 detectors (vcp + flat_base + cup_with_handle + high_tight_flag + double_bottom_w) emit `<Detector>Evidence` dataclasses with `geometric_score` + `structural_evidence_json` fields per L2 LOCK. T2.SB5 consumes via `pattern_evaluations` table (v20 schema; UNCHANGED). DO NOT widen `_pattern_detect_registry()` further; do NOT add new detectors in T2.SB5 scope (template matching is a SEPARATE pipeline step layered on top per plan §G.7 recon).
6. **`pattern_evaluations.template_match_score` column was planted at T-A.1.1** (v20 schema) with NULL pre-T2.SB5. T2.SB5 populates it via `_step_pattern_detect` integration (T-A.5.4); the row construction at `swing/pipeline/runner.py:1866` currently writes `template_match_score=None` — T-A.5.4 replaces this with the actual `match_forward` top-K max similarity score.
7. **`pattern_evaluations.template_match_nearest_exemplar_ids_json` column** planted at T-A.1.1 (v20 schema) with NULL pre-T2.SB5. T2.SB5 populates with JSON-encoded list of top-3 nearest exemplar IDs per spec §5.7 retrieval mode (per `_step_pattern_detect` row construction at `swing/pipeline/runner.py:1867`).
8. **Two-pass-reconcile-serialize architecture** (T2.SB3 R4 architectural refinement) preserved verbatim. Pass 1 (outside `lease.fenced_write()`): seed universe + detector invocations + emit_queue. Pass 2 (inside `lease.fenced_write()`): re-read canonical + reconcile + serialize. T2.SB5 template-matching layer plugs into Pass 2 row construction — the template_match invocation per row happens during Pass 2 reconcile, NOT during Pass 1 detector invocation (DB-substrate reads on `pattern_exemplars` corpus are part of the reconcile step).

### §1.3 Inheritance from T3.SB2 hotfix + 21st C.C lesson #6 scope-expanded validation

9. **C.C lesson #6 pre-Codex orchestrator-side review BINDING for the 21st cumulative validation expected at this dispatch with BOTH scope expansions BINDING:**
   - **Expansion #1** (T3.SB2 hotfix `cf3c489`): when widening a constant mirrored elsewhere in the codebase, grep `swing/` for redundant hardcoded copies of the OLD value tuple. For T2.SB5: the `_DETECTOR_CLASS_VALUES` 5-value frozenset at `swing/patterns/drift_logging.py:43` is UNCHANGED by T2.SB5 (no enum widening); but if T2.SB5 introduces ANY new constant (e.g., DTW band width tuple, template-match retrieval direction enum, composite formula weights tuple), apply the SAME discipline — grep `swing/` for hardcoded duplicates + verify each downstream consumer is widened consistently.
   - **Expansion #2** (T2.SB4 R1 M1 lesson): cross-check dispatch brief prescriptions against spec source-of-truth at cited sections. Pre-Codex review templates MUST include "verify dispatch brief prescriptions against spec source-of-truth at the cited section" as a binding step. For T2.SB5: §1.1 #4 above identified the plan-side `§D.4` + `§D.5` reference drift; the BINDING source is §5.7 + §5.8. Pre-Codex review MUST grep spec §5.7 (4-item pruning LOCK at lines 700-704) + §5.8 (composite formula at line 714 + bounds at lines 718-720) verbatim and verify the implementation matches byte-for-byte.

---

## §2 Per-task acceptance criteria (per plan §G.7 verbatim)

| Task | Title | Acceptance |
|---|---|---|
| T-A.5.1 | DTW core + Sakoe-Chiba band per spec §5.7 + OQ-4 | 6+ discriminating tests pass per plan §G.7 step 1 enumeration: (a) DTW(identical, identical) = 0.0; (b) DTW(known-similar) matches known-good fixture; (c) Sakoe-Chiba band with `window=0.1 × series_length` prevents over-warping (regression vs unconstrained DTW); (d) similarity_score normalization 0..1 (1=identical); (e) edge case: empty exemplar corpus returns empty list; (f) min-max normalization applied per v2 brief §7 LOCK. Pure-Python implementation; NumPy-vectorized inner loop; NO scipy dependency. |
| T-A.5.2 | `match_forward` + `match_reverse` retrieval | 6+ discriminating tests pass: (a) `match_forward` returns 3 hits ordered by similarity; (b) per-pattern filtering (VCP candidate compares ONLY against VCP exemplars per §5.7 pruning #1); (c) geometric_score pre-gate filter (DTW only fires for `geometric_score >= 0.4` per §5.7 pruning #2); (d) max-windows-per-ticker = 3 (§5.7 pruning #3); (e) exemplar corpus subsampling at 100+ rows (50 highest-quality_grade per §5.7 pruning #4); (f) `match_reverse` returns inverse direction. `TemplateMatchHit` frozen dataclass with `__post_init__` Literal[...] frozenset validation per CLAUDE.md gotcha. |
| T-A.5.3 | Composite scoring per spec §5.8 (`compute_composite_score`) | 4+ discriminating tests pass: (a) `compute_composite_score(geometric=0.8, template_match=0.7)` = `min(1.0, 0.60 × 0.8 + 0.40 × 0.7)` = 0.76; (b) double-bottom-W undercut bonus → geometric=1.10 → composite **CLAMPED at 1.0** via `min(1.0, ...)` wrap (per §5.8 line 718 + §1.1 #1 LOCK chain); (c) template_match_score=None → composite = geometric_score (clamped via `min(1.0, geometric_score)` per §5.8 line 720 fallback LOCK; preserves DBW 1.10 → 1.0 clamp behavior); (d) calibration LOCK: composite_score is 0..1 evidence-strength, NOT probability (per §5.8 line 724 LOCK; documented in dataclass docstring + function docstring). |
| T-A.5.4 | Pipeline `_step_pattern_detect` integration | 2+ tests pass; step invokes `match_forward` for each detector verdict (gated by geometric_score >= 0.4 per §5.7 pruning #2); persists `template_match_score` + `template_match_nearest_exemplar_ids_json` + recomputes `composite_score` on `pattern_evaluations` rows per spec §5.8 formula. **CRITICAL**: the existing `composite_score = min(1.0, geometric_score)` line at `swing/pipeline/runner.py:1677` is REPLACED with `composite_score = compute_composite_score(geometric_score, template_match_score)` — the `min(1.0, ...)` wrap MUST be inside `compute_composite_score` (NOT removed). Discriminating test (per `feedback_regression_test_arithmetic`): plant DBW evidence with geometric=1.10 + template_match=1.0; compute pre-fix (no clamp) = 1.06 (would fail drift_logging histogram); post-fix (clamp inside `compute_composite_score`) = 1.0 (passes histogram). |
| T-A.5.5 | pytest-benchmark 120s gate per OQ-4 | 1 benchmark test (slow-marked or `@pytest.mark.benchmark`). Seeds universe of ~250 candidate tickers × 5 patterns × ~50 exemplars per pattern (≈62,500 DTW pair-computations per spec §5.7 perf budget). Asserts `benchmark.stats['mean'] < 120.0` seconds on operator's hardware. **All 4 §5.7 pruning LOCK items MUST be in place before benchmark fires** (per-pattern filtering + geometric_score pre-gate + max-windows-per-ticker + exemplar corpus subsampling). FAILURE escalates to OQ-4 V2 fallback (SBD or pruning tightening — operator escalation). |
| T-A.5.6 | T2.SB5 closer — integration E2E + ruff sweep + 2 cross-bundle pins | Full fast-test suite + ruff sweep PASS; 1 fast E2E seeds 5 pattern_evaluations rows + 25 exemplars; invokes full pipeline; asserts composite_score correctly composed from geometric + template_match per §5.8. Cross-bundle pin un-skips: (1) `test_pattern_exemplars_schema_shape_invariant` un-skipped at `tests/data/test_v20_migration.py:840` (lag from T2.SB3 closer; T2.SB5 closes); (2) `test_pattern_evaluations_template_match_score_persistable` PLANTED + un-skipped per §1 above (does not exist on main HEAD `7f49b82`; T2.SB5 plants the body). |

**Recommended ordering**: T-A.5.1 (DTW core; pure algorithm — no dependencies) → T-A.5.2 (retrieval + pruning LOCK; consumes DTW core) → T-A.5.3 (composite scoring; pure function — no DB; spec §5.8 LOCK fidelity) → T-A.5.4 (pipeline integration; sequential prerequisite for E2E + benchmark) → T-A.5.5 (benchmark gate; needs full pipeline integration landed) → T-A.5.6 (closer + cross-bundle pin work).

---

## §3 Files in scope

**Create** (2 production modules + 3 unit-test files + 1 benchmark test + 1 E2E file):
- `swing/patterns/template_matching.py` — `_dtw_distance` + `match_forward` + `match_reverse` + `TemplateMatchHit` frozen dataclass; pure-Python DTW with Sakoe-Chiba band; NumPy-vectorized inner loop; NO scipy dependency.
- `swing/patterns/composite.py` — `compute_composite_score(geometric, template_match) -> float` per spec §5.8 LOCK formula; preserves `min(1.0, ...)` wrap discipline.
- `tests/patterns/test_template_matching.py` — unit tests for DTW core + retrieval functions (T-A.5.1 + T-A.5.2 contracts).
- `tests/patterns/test_composite.py` — unit tests for composite scoring (T-A.5.3 contract).
- `tests/patterns/test_template_matching_benchmark.py` — pytest-benchmark 120s gate test (T-A.5.5 contract; slow-marked).
- `tests/integration/test_phase13_t2_sb5_template_matching_e2e.py` — 1 fast E2E (T-A.5.6 contract).

**Modify**:
- `swing/pipeline/runner.py:1664-1677` (the existing T2.SB4 R2 Critical #1 composite cap at line 1677 — REPLACED with `composite_score = compute_composite_score(geometric_score, template_match_score)` call; the `min(1.0, ...)` wrap MOVES INSIDE `compute_composite_score`); `swing/pipeline/runner.py:1860-1867` (row construction at line 1866-1867 — `template_match_score=None` + `template_match_nearest_exemplar_ids_json=None` REPLACED with actual values from `match_forward` invocation).
- `swing/patterns/__init__.py` (re-export `TemplateMatchHit` + `compute_composite_score` per the namespace convention established at T-A.1.1).
- `tests/data/test_v20_migration.py:833-880` (REMOVE `@pytest.mark.skip` decorator on `test_pattern_exemplars_schema_shape_invariant`; verify PASS; body already correct).
- `tests/data/test_v20_migration.py` (PLANT new `test_pattern_evaluations_template_match_score_persistable` test per §1 above; un-skipped from start since T2.SB5 lands the column population logic).

**NOT in scope (V2 / future sub-bundles)**:
- Review auto-fill (T3.SB3 territory; per plan §H.1 dispatch sequence)
- Closed-loop / charts surface (T2.SB6 territory)
- Schwab integration (none for template matching; T2.SB5 has zero Schwab API consumers)
- Schema changes (v20 LOCKED per spec §B.4; if any test surfaces a schema need, STOP + escalate per dispatch §B.6 precedent)
- New detector additions (5-detector V1 set COMPLETE per L2 LOCK at T2.SB4; do NOT widen `_pattern_detect_registry()`)
- SBD (Shape-Based Distance) — V2 fallback only if 120s benchmark FAILS; do NOT implement preemptively
- Z-score normalization for shape comparison — V2 per plan §V2-5; V1 LOCK is min-max per v2 brief §7
- Calibration of composite_score (Brier + isotonic regression) — V2 per plan §V2-6; V1 LOCK is "evidence-strength NOT probability" per spec §5.8 line 724
- Matrix Profile-based exemplar retrieval at scale — Phase 14+ per plan §V2-8

---

## §4 Watch items (cumulative discipline; banked across Phase 12 + 12.5 + 13)

### §4.1 T2.SB5-specific watch items

1. **Spec §5.7 + §5.8 LOCK fidelity**: every formula coefficient + threshold + pruning constraint MUST match spec verbatim. Implementer SHOULD grep spec §5.7 (lines 667-706) + §5.8 (lines 708-724); do NOT paraphrase. **Cross-check spec source-of-truth against this brief's prescriptions per C.C lesson #6 Expansion #2 BINDING** (§1.1 #4).
2. **§5.7 pruning LOCK 4-item discipline**: per-pattern exemplar filtering (#1) + geometric_score pre-gate `>= 0.4` (#2) + max-windows-per-ticker = 3 (#3) + exemplar corpus subsampling at 100+ rows take 50 highest-quality_grade (#4). All 4 in place BEFORE benchmark fires (T-A.5.5 dependency).
3. **§5.8 composite formula LOCK**: `composite_score = min(1.0, 0.60 × geometric_score + 0.40 × template_match_score)`. Coefficients (0.60 + 0.40) + clamp (`min(1.0, ...)`) bound verbatim. T-A.5.3 + T-A.5.4 discriminating tests assert exact arithmetic.
4. **§5.8 line 720 fallback LOCK**: when `template_match_score=None` (e.g., empty exemplar corpus, geometric_score below pre-gate, candidate skipped per pruning), `composite_score = geometric_score` — but the `min(1.0, ...)` wrap from the formula MUST still apply for DBW evidence 1.10 → composite 1.0 clamp. **Failure mode caught at T2.SB4 R2 Critical #1**: if the fallback path bypasses the clamp, drift_logging `_composite_score_histogram` ValueError aborts the entire Pass-2 emit loop for the run.
5. **§5.8 line 724 calibration LOCK**: composite_score is 0..1 evidence-strength, NOT probability. Document in dataclass docstring + function docstring + any user-facing render (V2-6 banked as candidate for Brier + isotonic regression calibration).
6. **DTW Sakoe-Chiba band `window = 0.1 × series_length`** per spec §5.7 line 672 + line 674. Discriminating test asserts band reduces warp distance vs unconstrained DTW. Band parameter LOCKED at 0.1 ratio; do NOT widen without operator escalation.
7. **Min-max normalization on candidate + exemplar windows** per spec §5.7 line 695 + v2 brief §7 LOCK. Z-score deferred to V2 per plan V2-5.
8. **Pure-Python DTW implementation**: NumPy-vectorized inner loop per plan §G.7 T-A.5.1 Step 2 LOCK; NO scipy dependency added to `pyproject.toml`. (Pytest-benchmark IS a new test-only dependency; verify it lands in `[project.optional-dependencies].dev` only.)
9. **`TemplateMatchHit` frozen dataclass + `__post_init__` Literal[...] frozenset validation** per CLAUDE.md gotcha "`Literal[...]` not runtime-enforced" (T-A.1.5b R3 M#1 cumulative). Fields: `exemplar_id: int`, `distance: float`, `similarity_score: float` per §5.7 lines 689-693.
10. **`match_forward` + `match_reverse` PURE FUNCTIONS** — ZERO DB writes from inside; pipeline `_step_pattern_detect` step layer owns DB writes per L2 LOCK inherited from T2.SB3.

### §4.2 Pipeline integration watch items (T-A.5.4)

11. **`_step_pattern_detect` two-pass-then-reconcile-then-serialize architecture preserved** per T2.SB3 R4 + T2.SB4 inheritance. Template matching invocation belongs in Pass 2 reconcile-step (alongside row construction at line 1850-1868), NOT in Pass 1 detector invocation. Rationale: Pass 2 is the only place that has the FULL canonical universe of `pattern_exemplars` available (after lease-acquired re-read of any in-flight inserts). Pass 1 may run on a stale exemplar corpus if a parallel pipeline run is mid-flight.
12. **The existing T2.SB4 R2 Critical #1 composite cap at `runner.py:1677`** (`composite_score = min(1.0, geometric_score)`) is REPLACED with the full §5.8 formula via `compute_composite_score(geometric_score, template_match_score)`. **CRITICAL**: the `min(1.0, ...)` wrap MUST move INSIDE `compute_composite_score` — do NOT just replace the formula without the clamp. Discriminating test: plant DBW evidence with geometric=1.10 + template_match=1.0 → pre-fix (no clamp) = 1.06 → drift_logging ValueError; post-fix (clamp inside) = 1.0 → drift_logging PASS.
13. **Pipeline row construction at `runner.py:1860-1868`**: replace `template_match_score=None` + `template_match_nearest_exemplar_ids_json=None` with actual values from `match_forward` invocation. **DB column semantics**: `pattern_evaluations.geometric_score` continues to carry RAW evidence (unconstrained REAL; per T2.SB4 R3 Major #1 LOCK); `pattern_evaluations.composite_score` carries CLAMPED composite (per T2.SB4 R2 Critical #1 LOCK).
14. **`structural_evidence_json` continues to carry RAW evidence** even when DB columns clamp — preserves T2.SB4 inheritance.
15. **Geometric_score pre-gate `>= 0.4`** per §5.7 pruning #2: candidates with `geometric_score < 0.4` SKIP template matching entirely (`template_match_score=None` + `template_match_nearest_exemplar_ids_json=None`). The §5.8 line 720 fallback path kicks in: `composite_score = min(1.0, geometric_score)` — identical to current pre-T2.SB5 behavior. Discriminating test: plant evidence with geometric=0.35 → assert template_match_score remains NULL + composite_score = 0.35.

### §4.3 Cross-bundle pin watch items (T-A.5.6)

16. **UN-SKIP `test_pattern_exemplars_schema_shape_invariant`** at `tests/data/test_v20_migration.py:840` — body already correct (verifies 20-column schema shape); just remove `@pytest.mark.skip` decorator. Per plan §H.3 row 7 schedule + §1 of this brief.
17. **PLANT + UN-SKIP `test_pattern_evaluations_template_match_score_persistable`** at `tests/data/test_v20_migration.py` (NEW test; does not exist on main HEAD `7f49b82` per `git grep` audit) — body verifies (a) `pattern_evaluations.template_match_score` accepts NULL (pre-T2.SB5 path); (b) accepts a float in [0.0, 1.0] via INSERT + SELECT round-trip with exact-equality-within-epsilon assertion. Per plan §H.3 row 8 schedule + §1 of this brief.

### §4.4 Cumulative process discipline

18. **Pre-Codex orchestrator-side review (C.C lesson #6 BINDING; 21st cumulative validation expected with BOTH SCOPE EXPANSIONS BINDING)** — implementer dispatches a focused reviewer subagent with this brief's §3 file-scope + §4 watch items + §5 done criteria + §6 LOCKs as anchors BEFORE invoking Codex MCP. Reference: 20th cumulative validation BANKED CLEAN at T2.SB4 with scope-expanded discipline. **Expansion #1 (T3.SB2 hotfix `cf3c489`)**: grep `swing/` for hardcoded duplicates of any new constant T2.SB5 introduces (DTW band ratio, retrieval direction enum, composite weights tuple) + verify each downstream consumer is widened consistently. **Expansion #2 (T2.SB4 R1 M1 lesson)**: cross-check this brief's prescriptions against spec §5.7 + §5.8 BINDING text byte-for-byte; the plan-side `§D.4` + `§D.5` references are reference drift (spec has NO §D section).
19. **NO `Co-Authored-By` footer** — cumulative ~295+ commit streak ZERO trailer drift through T2.SB4 + housekeeping; do NOT regress. Per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15): explicit citation in commit messages required.
20. **`python -m swing.cli` from worktree cwd**, NOT bare `swing` (memory `feedback_worktree_cli_invocation`).
21. **ASCII-only on any new CLI/print path** — runtime CLI paths bind (Windows cp1252 footgun); template matching internal logging via stdlib logger handles encoding.
22. **Edit tool for per-file edits** when fixing E501 / type / import-order issues — do NOT bulk-rewrite (Phase 12.5 #3 L-W4 precedent).
23. **Cite the discipline in commit messages** (matches all prior T1.SB0 + T2.SB1 + T3.SB1 + T2.SB2 + T2.SB3 + T3.SB2 + T2.SB4 commit-message precedent).
24. **TDD discipline per task** via `superpowers:test-driven-development` (write failing test → see fail → minimal implementation → see pass → commit).

---

## §5 Done criteria

### §5.1 S1 (inline; implementer self-verifies before invoking Codex)

- [ ] All 6 T-A.5.X tasks committed per plan §G.7 acceptance criteria.
- [ ] `python -m pytest -m "not slow" -q -n auto` PASS post-merge. **Expected**: 5376 + ~50-80 new fast tests = ~5426-5456 total + 2 un-skips/plants from T-A.5.6 closer = ~5428-5458; 0 failures; ≤2 skipped (T-A.5.6 un-skip of `test_pattern_exemplars_schema_shape_invariant` brings skipped from 4 → 3; T-A.5.6 plant + un-skip of `test_pattern_evaluations_template_match_score_persistable` adds 0 skips since it's planted un-skipped).
- [ ] `python -m pytest -m slow tests/patterns/test_template_matching_benchmark.py -q` PASS (T-A.5.5 benchmark gate; mean < 120s on operator's hardware).
- [ ] `python -m pytest -m slow tests/integration/test_phase13_t2_sb5_template_matching_e2e.py -q` PASS if T-A.5.6 includes any slow E2E (verify at recon; likely fast-only per plan §G.7 T-A.5.6 step 1).
- [ ] `ruff check swing/` clean (0 E501).
- [ ] Schema version unchanged at v20.
- [ ] Pre-Codex orchestrator-side review dispatched + verdict captured (21st cumulative C.C lesson #6 validation expected CLEAN with BOTH scope expansions applied — grep-verified zero hardcoded duplicates of any T2.SB5-introduced constants + spec §5.7 + §5.8 byte-fidelity verified vs brief sketches).
- [ ] All commits on branch `phase13-t2-sb5-template-matching` have empty `Co-Authored-By` trailer (verified via `git log --pretty='%(trailers:key=Co-Authored-By)' phase13-t2-sb5-template-matching --not main | grep -c .` returning 0).
- [ ] Codex MCP adversarial-critic chain converges to `NO_NEW_CRITICAL_MAJOR` (expected 2-4 rounds based on mid-sized scope; T2.SB4 took 5 rounds with 1 RESOLVED Critical — T2.SB5 may converge faster given inherited composite cap discipline OR slower given benchmark gate as new discipline weight).

### §5.2 S2-S4 (operator-paired post-merge per plan §G.7 lines 2039-2043)

- **S2 (benchmark)**: operator runs `python -m pytest -m slow tests/patterns/test_template_matching_benchmark.py -q` on their production hardware (~3GHz CPU baseline per spec §5.7 line 706). Verifies 120s/run gate. FAIL escalates to OQ-4 V2 fallback (SBD per spec §5.7 line 706 + plan §V2-7).
- **S3 (CLI)**: `python -m swing.cli pipeline run` against operator's production candidate pool. Verifies `_step_pattern_detect` populates `template_match_score` + `template_match_nearest_exemplar_ids_json` on `pattern_evaluations` rows when geometric_score ≥ 0.4 (per §5.7 pruning #2). Operator inspects rows for:
  - `template_match_score` in [0.0, 1.0] (NULL for geometric_score < 0.4 candidates)
  - `composite_score` in [0.0, 1.0] (clamped via `compute_composite_score` per §5.8)
  - DBW row with undercut bonus: `geometric_score = 1.10` + `template_match_score = X` + `composite_score = min(1.0, 0.60 × 1.10 + 0.40 × X)` = `min(1.0, 0.66 + 0.40 × X)` ≤ 1.0 (formula honored; clamp applied)
  - `template_match_nearest_exemplar_ids_json` parseable as JSON list of 1-3 exemplar IDs
- **S4 (cross-check)**: operator selects a known historical VCP (or any pattern with corpus coverage) and verifies `match_forward(candidate_window, exemplar_corpus, top_k=3)` returns plausible historical bases as top-3 hits (subjective shape similarity assessment vs operator's mental model).

---

## §6 LOCKs (do not deviate without operator escalation)

- **L1**: Spec §5.7 + §5.8 BINDING text verbatim. Composite formula coefficients (0.60 + 0.40) + clamp (`min(1.0, ...)`) + pruning LOCK 4-item constants + Sakoe-Chiba band ratio (0.1) + min-max normalization. Plan-side `§D.4` + `§D.5` references are drift (spec has NO §D section); brief authors use §5.7 + §5.8 verbatim. Implementer reads spec; does NOT paraphrase.
- **L2**: ZERO DB writes inside `match_forward` + `match_reverse` + `compute_composite_score` (PURE FUNCTIONS). All DB writes routed through `_step_pattern_detect` step layer with caller-tx discipline (preserved from T2.SB3 + T2.SB4 architecture).
- **L3**: NO `INSERT OR REPLACE` on `pattern_evaluations` writes. SELECT-then-INSERT idempotency pattern (preserved from T2.SB3 Pass 2 reconcile-then-serialize at runner.py).
- **L4**: Cross-bundle pin UN-SKIPS + PLANT at T-A.5.6 closer per §1 + §4.3 #16 + #17. Leaving stale (skipped state OR missing test) violates plan §H.3 schedule.
- **L5**: §5.8 composite formula `min(1.0, ...)` wrap PRESERVED inside `compute_composite_score` (do NOT bypass clamp on the `template_match_score=None` fallback path; the §5.8 line 720 fallback also goes through `min(1.0, geometric_score)` because DBW evidence may reach 1.10).
- **L6**: Branch base = main HEAD `7f49b82` at dispatch time. Verify at T-A.5.1 Step 0: `git merge-base --is-ancestor 7f49b82 HEAD` returns 0.
- **L7**: Frozen dataclasses (`TemplateMatchHit`) carry `__post_init__` Literal[...] frozenset validation honoring T-A.1.5b R3 M#1 CLAUDE.md gotcha.
- **L8**: §5.7 pruning LOCK 4-item discipline (per-pattern filtering + geometric pre-gate + max-windows-per-ticker + corpus subsampling) all in place BEFORE T-A.5.5 benchmark fires.
- **L9**: Sakoe-Chiba band ratio LOCKED at 0.1 (`window = 0.1 × series_length`); do NOT widen without operator escalation (V2 territory).
- **L10**: Min-max normalization on candidate + exemplar windows per spec §5.7 line 695 + v2 brief §7 LOCK. Z-score deferred to V2 per plan §V2-5.
- **L11**: V1 composite_score is 0..1 evidence-strength signal for operator triage, NOT a probability. NO calibration in V1 (V2-6 banked). Documented in dataclass + function docstrings.
- **L12**: Bar-clipping discipline at detector entry (inherited from T2.SB3 forward-binding lesson #2) — `match_forward` consumes `CandidateWindow.start_date` + `end_date` from the existing row; template matching does NOT re-derive window boundaries from bars. The `bars.loc[bars.index <= candidate_window.end_date]` discipline is already enforced at detector layer; template matching consumes the resulting `CandidateWindow` verbatim.

---

## §7 Reference materials (read before dispatching)

- **Plan**: `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` §G.7 lines 1973-2046 (T2.SB5 verbatim 6-task spec) + §H.3 cross-bundle pin schedule rows 7-8 (`test_pattern_exemplars_schema_shape_invariant` un-skip at T2.SB3 + T2.SB5; `test_pattern_evaluations_template_match_score_persistable` un-skip at T2.SB5).
- **Spec**: `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`:
  - §5.7 Template matching layer (lines 667-706; DTW + Sakoe-Chiba band LOCK + 4-item pruning LOCK at lines 700-704 + 120s benchmark gate at line 706)
  - §5.8 Composite scoring (lines 708-724; formula at line 714 + bounds at lines 718-720 + calibration LOCK at line 724)
  - §5.11 Drift logging baseline substrate (line 802+; `_composite_score_histogram` LOCK [0.0, 1.0] — explains WHY the §5.8 clamp is BINDING)
  - §10.5 Double-bottom-W worked example (line 1325 undercut bonus → geometric 1.10) — discriminating arithmetic for T-A.5.3 (b) + T-A.5.4 discriminating test.
- **T2.SB4 return report** at `docs/phase13-t2-sb4-return-report.md` §7 — 4 forward-binding lessons banked for T2.SB5 inheritance (verbatim sources for §1.1 above).
- **T2.SB4 dispatch brief** at `docs/phase13-t2-sb4-detectors-batch2-dispatch-brief.md` — template for this brief's shape; detector-batch + cross-bundle-pin-extension pattern.
- **T2.SB3 implementation references** at `swing/patterns/vcp.py` + `swing/patterns/flat_base.py` + `swing/patterns/cup_with_handle.py` — for the 5-detector substrate consumed by T2.SB5; `swing/patterns/_sanitize.py` reusable if T2.SB5 introduces any bar-derived normalization.
- **T2.SB4 implementation references** at `swing/patterns/high_tight_flag.py` + `swing/patterns/double_bottom_w.py` — for the HTF + DBW evidence shapes; DBW evidence reaches 1.10 (the discriminating arithmetic for §5.8 clamp tests).
- **Pipeline integration site** at `swing/pipeline/runner.py:1660-1700` (composite_score derivation) + `swing/pipeline/runner.py:1840-1880` (row construction) — exact lines T-A.5.4 modifies.
- **T-A.1.7 corpus manifest** at `data/phase13-t2-sb1-corpus/README.md` + JSONL dump at `data/phase13-t2-sb1-corpus/pattern_exemplars_dump.jsonl` — exemplar shape templates for unit-test fixture inspiration + S4 visual cross-check.
- **CLAUDE.md gotchas relevant to T2.SB5**:
  - `Literal[...]` not runtime-enforced (T-A.1.5b R3 M#1 inherited)
  - ASCII-only on runtime CLI paths
  - SQLite INSERT OR REPLACE is DELETE + INSERT semantically (per L3 LOCK)
  - Evidence-tier vs composite-tier score cap distinction (T2.SB4 R2 C1 + R3 M1; BINDING per §1.1 #1 + §4.2 #12)
  - Bounded backward-slice search for anchor-relative detectors (T2.SB4 R2 M2; informs §1.1 #2 forward-binding)
  - Pre-Codex review must cross-check spec source-of-truth against dispatch brief sketches (T2.SB4 R1 M1 lesson; BINDING per §1.1 #4 + §4.4 #18 Expansion #2)
  - Schema-CHECK widening MUST audit ALL Python-side surface guards across the repo (T3.SB2 hotfix; informs §4.4 #18 Expansion #1)

---

## §8 Post-dispatch housekeeping checklist (orchestrator-inline)

When T2.SB5 merge ships:

1. **CLAUDE.md line 3 refresh** — update HEAD reference + mention T2.SB5 SHIPPED + 21st cumulative C.C lesson #6 validation with BOTH scope expansions applied; mention any NEW gotchas surfaced; bank any new V2 candidates; flag if benchmark gate passed/failed.
2. **phase3e-todo.md** — new top entry for T2.SB5 SHIPPED with: Codex chain shape + any ACCEPT-WITH-RATIONALE banks + forward-binding lessons for T3.SB3 + T2.SB6 + T4.SB inheritance + benchmark observation (actual wall-clock vs 120s gate) + 2 cross-bundle pin closure notes; cross-bundle pin status updates.
3. **orchestrator-context.md** — refresh current state; demote former current to Prior; **archive-split per size-check trigger (Prior state count is 10 at cap per handoff brief §0; demote pushes to 11; archive-split MUST fire — same shape as 3 prior splits in 2026-05-20+21)**.
4. **orchestrator-context-archive.md** — new "Appended 2026-05-2X" section with archived Prior verbatim.
5. **Streaks update** — bank the 21st cumulative C.C lesson #6 validation (if CLEAN with BOTH scope expansions applied); bank ~305+ cumulative ZERO Co-Authored-By streak (T2.SB5 expected ~8-12 commits including Codex fix bundles).
6. **Phase 13 dispatch sequence forward state** — T2.SB5 SHIPPED; T3.SB3 NEXT per plan §H.1 (review auto-fill consuming OhlcvCache; 5 tasks); T2.SB6 after T3.SB3; T4.SB after T2.SB6 + operator-added list items per `project_phase13_t4_sb_pause_for_list_additions` BINDING memory.

---

## §9 Forward-binding to T3.SB3 + T2.SB6 + T4.SB

T3.SB3 = Review auto-fill consuming OhlcvCache (5 tasks per plan §G.8; per spec §6.3). Branches from main HEAD AFTER T2.SB5 merge (per plan §G.8 line 2053). Inherits Phase 13 detector substrate + template matching layer (templates may inform "top-3 similar prior reviews" pre-population per spec §6.3).

T2.SB6 = Closed-loop surface + Theme 1 annotated charts (8 tasks per plan §G.9; includes T-A.6.6b Deficiency 1 fold-in). Inherits ALL Phase 13 detector substrate + template matching layer; consumes `template_match_nearest_exemplar_ids_json` for top-3 thumbnail rendering per spec §5.10 page content #3.

T4.SB = Usability triage + Q4 close-tracking + T-D.6b metrics-audit (8 tasks + operator-added items). **PAUSE FOR OPERATOR LIST ADDITIONS** BINDING per `project_phase13_t4_sb_pause_for_list_additions` memory — orchestrator MUST surface the pause at T2.SB6 SHIPPED + housekeeping boundary; do NOT proceed past T2.SB6 housekeeping without operator's added items.

**Forward-binding lessons expected from T2.SB5 to T3.SB3 + T2.SB6 + future arc work:**
- 120s/run benchmark gate observation (actual wall-clock on operator's hardware; if elevated, V2 calibration territory OR SBD fallback per OQ-4).
- §5.7 pruning LOCK 4-item discipline (sets precedent for any future O(n²) algorithm at pipeline scale — Phase 14 Matrix Profile per V2-8 inherits this discipline).
- Composite formula `min(1.0, ...)` wrap discipline (inherited from T2.SB4; preserved through T2.SB5; T2.SB6 closed-loop UI rendering MUST honor the evidence-tier vs composite-tier column semantics when surfacing pattern_evaluations rows).
- Cross-bundle pin closure pattern (T-A.5.6 un-skip of one stale-from-T2.SB3 pin + plant + un-skip of one never-planted pin; sets precedent for closer-task hygiene at T2.SB6 + T4.SB).
- 21st cumulative C.C lesson #6 validation with BOTH scope expansions applied (sets precedent for all future dispatches; scope-expanded discipline durable across the Phase 13 arc).
- ZERO `Co-Authored-By` trailer streak (~305+ cumulative commits expected post-T2.SB5 merge + housekeeping).

---

*End of dispatch brief. Phase 13 T2.SB5 (6 tasks; +50-80 fast tests + 1 pytest-benchmark slow gate + 1 fast E2E + 2 cross-bundle pin closures projected) — SECONDARY signal layer (template matching DTW + composite scoring) on top of 5-detector V1 PRIMARY substrate completed at T2.SB4. Inherits 4 forward-binding lessons from T2.SB4 verbatim (evidence-tier vs composite-tier cap distinction + bounded backward-slice + DBW anchor_date contract + pre-Codex review brief-vs-spec cross-check). 2-4 Codex rounds expected for mid-sized scope. **21st cumulative C.C lesson #6 validation expected with BOTH SCOPE EXPANSIONS BINDING** (grep `swing/` for hardcoded duplicates of any new T2.SB5 constants + cross-check spec §5.7 + §5.8 BINDING text byte-for-byte vs brief sketches; plan-side `§D.4` + `§D.5` references are reference drift). ZERO Co-Authored-By footer drift streak (~295+ commits at handoff) preserved.*
