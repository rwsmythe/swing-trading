# Phase 13 T2.SB5 — Template matching (DTW + composite scoring) return report

**Status:** READY FOR INTEGRATION-MERGE. Drafted 2026-05-21 post-Codex
chain convergence (R2 NO_NEW_CRITICAL_MAJOR; R1 had 0 Critical + 0
Major + 2 Minor with 1 RESOLVED + 1 ACCEPT-WITH-RATIONALE banked).

**Branch:** `phase13-t2-sb5-template-matching` based on main HEAD
`a8be12a` (descendant of the brief's L6-locked `7f49b82`). 7 commits;
ZERO `Co-Authored-By` trailer drift verified.

**Dispatch brief:** `docs/phase13-t2-sb5-template-matching-dispatch-brief.md`
(committed at main `a8be12a`; brief shape mirrored from T2.SB4
dispatch brief precedent).

---

## §1 Commit chain (7 commits)

```
5534cc6 fix(phase13): isolate bad exemplar from cohort in match_forward (Codex R1 M#1)
a105df7 test(phase13): T2.SB5 closer - template matching E2E + ruff (T-A.5.6)
689ec36 test(phase13): T2.SB5 pytest-benchmark 120s gate (T-A.5.5)
1798c2f feat(phase13): _step_pattern_detect template matching integration (T-A.5.4)
730fa07 feat(phase13): composite scoring (T-A.5.3)
58dfaea feat(phase13): template matching retrieval (T-A.5.2)
f532ed8 feat(phase13): DTW core with Sakoe-Chiba band (T-A.5.1)
```

ZERO `Co-Authored-By` trailer drift verified via:
```
git log --pretty='%(trailers:key=Co-Authored-By)' --not main | grep -c .  # -> 0
```

---

## §2 Per-task summary

| Task | Title | New tests | Commit |
|---|---|---|---|
| T-A.5.1 | DTW core + Sakoe-Chiba band | 11 | `f532ed8` |
| T-A.5.2 | match_forward + match_reverse retrieval + pruning LOCK | 9 | `58dfaea` |
| T-A.5.3 | compute_composite_score per spec §5.8 | 9 | `730fa07` |
| T-A.5.4 | Pipeline _step_pattern_detect integration | 3 | `1798c2f` |
| T-A.5.5 | pytest-benchmark 120s gate (slow-marked) | 1 (slow) | `689ec36` |
| T-A.5.6 | Closer — fast E2E + cross-bundle pin closures | 1 + 1 plant + 1 un-skip | `a105df7` |
| Codex R1 fix | Bad-exemplar isolation in match_forward | +1 | `5534cc6` |

**Total fast-test delta: +35 net passes + 1 un-skipped pin (5376 → 5412 passing; 4 → 3 skipped).**

---

## §3 Modules + files landed

### Created

- `swing/patterns/template_matching.py` — DTW core + Sakoe-Chiba band +
  retrieval (`match_forward` + `match_reverse`) + pruning helpers
  (`cap_candidates_per_ticker` + `subsample_exemplar_corpus`) +
  TemplateMatchHit + TemplateMatchExemplar frozen dataclasses.
- `swing/patterns/composite.py` — `compute_composite_score` per spec
  §5.8 V1 LOCK formula.
- `tests/patterns/test_template_matching.py` — 21 unit tests (DTW +
  retrieval + pruning + bad-exemplar isolation).
- `tests/patterns/test_composite.py` — 9 unit tests for composite formula.
- `tests/patterns/test_template_matching_benchmark.py` — slow-marked
  pytest-benchmark 120s gate.
- `tests/pipeline/test_step_pattern_detect_template_matching.py` — 3
  pipeline integration tests.
- `tests/integration/test_phase13_t2_sb5_template_matching_e2e.py` — 1
  fast E2E.

### Modified

- `swing/patterns/__init__.py` — re-exports `TemplateMatchHit`,
  `TemplateMatchExemplar`, `compute_composite_score`.
- `swing/pipeline/runner.py` — added T2.SB5 imports + extended
  `_step_pattern_detect` Pass-1/Pass-2 architecture to plumb template
  matching + recompute composite_score per spec §5.8.
- `tests/data/test_v20_migration.py` —
  `test_pattern_exemplars_schema_shape_invariant` un-skipped (cross-
  bundle pin closure #1 per plan §H.3 row 7);
  `test_pattern_evaluations_template_match_score_persistable` PLANTED
  (cross-bundle pin closure #2 per plan §H.3 row 8).
- `pyproject.toml` — `pytest-benchmark>=4` added to dev deps.

---

## §4 LOCK fidelity (L1-L12 per dispatch brief §6)

| LOCK | Status | Evidence |
|---|---|---|
| L1 spec §5.7 + §5.8 BINDING fidelity | PASS | Coefficients 0.60/0.40, clamp `min(1.0, ...)`, Sakoe-Chiba ratio 0.1, min-max normalization, 4-item pruning LOCK constants — all byte-fidelity verified per Codex R1 + pre-Codex review. |
| L2 ZERO DB writes (pure functions) | PASS | `template_matching.py` + `composite.py` carry no SQL. DB I/O routed through `_step_pattern_detect` step layer with caller-tx discipline. |
| L3 NO INSERT OR REPLACE on pattern_evaluations | PASS | SELECT-then-INSERT idempotency preserved at `swing/pipeline/runner.py:1780-1824`. |
| L4 Cross-bundle pin un-skips + plant at T-A.5.6 | PASS | Both pins closed at `tests/data/test_v20_migration.py:833` + new test planted. |
| L5 `min(1.0, ...)` clamp PRESERVED on BOTH paths | PASS | `compute_composite_score` clamps on template-bearing path (composite.py:106) AND None-fallback path (composite.py:98). DBW arithmetic verified: `0.60 × 1.10 + 0.40 × 1.0 = 1.06 → clamp → 1.0`. |
| L6 Branch base main HEAD `7f49b82` | PASS | Verified via `git merge-base --is-ancestor 7f49b82 HEAD` (returns 0). Current main HEAD `a8be12a` is a descendant of `7f49b82`. |
| L7 Frozen dataclasses + `__post_init__` validation | PASS | `TemplateMatchHit` validates exemplar_id type (bool rejected), distance finiteness, similarity_score range [0.0, 1.0]; `TemplateMatchExemplar` validates close_prices type + ndim. |
| L8 4-item pruning LOCK in place before benchmark | PASS | #1 per-pattern_class filter (match_forward); #2 geometric_score >= 0.4 pre-gate (consumed both inside match_forward AND at pipeline integration site at runner.py:1914); #3 max-windows-per-ticker = 3 helper (production architecture picks `windows[-1]` so cap satisfied trivially); #4 corpus subsampling >100 -> top-50 quality_grade. |
| L9 Sakoe-Chiba band ratio LOCKED at 0.1 | PASS | `SAKOE_CHIBA_WINDOW_RATIO = 0.1` at template_matching.py:46. |
| L10 Min-max normalization (z-score V2) | PASS | `_min_max_normalize` at template_matching.py:141; applied in both match_forward + match_reverse. |
| L11 composite_score is evidence-strength NOT probability | PASS | docstrings at composite.py:22-26 + 60-62; L11 header. |
| L12 Bar-clipping discipline at detector entry | PASS | Pipeline uses inclusive `(bars.index >= start) & (bars.index <= end)` mask at runner.py:1699-1707 (candidate) + 1859-1861 (exemplar). |

---

## §5 Spec source-of-truth byte-fidelity (Expansion #2)

Cross-checked spec §5.7 lines 667-706 + §5.8 lines 708-724 verbatim:

- §5.7 line 672+674 Sakoe-Chiba band ratio 0.1 → ✓
- §5.7 line 695 min-max normalization → ✓
- §5.7 line 701 Pruning #1 per-pattern_class filter → ✓
- §5.7 line 702 Pruning #2 geometric_score >= 0.4 → ✓
- §5.7 line 703 Pruning #3 max 3 windows per ticker → ✓ (helper exists; production architecture satisfies cap trivially via `windows[-1]`)
- §5.7 line 704 Pruning #4 >100 rows → top-50 quality_grade → ✓
- §5.7 line 706 120s benchmark gate → ✓ (observed mean ~8.3s)
- §5.8 line 712 composite clamp `min(1.0, ...)` → ✓
- §5.8 line 714 formula `0.60 × geometric + 0.40 × template_match` → ✓
- §5.8 lines 718-720 evidence-tier bounds + fallback `composite = geometric` → ✓
- §5.8 line 724 calibration LOCK ("evidence-strength NOT probability") → ✓

Per dispatch brief §1.1 #4: plan-side `§D.4` + `§D.5` references are
reference drift (spec has NO §D section). Implementation cross-checks
against spec §5.7 + §5.8 directly per the BINDING text.

---

## §6 Codex MCP adversarial-critic chain

**Round 1**: 0 Critical + 0 Major + 2 Minor.

- **Minor #1** (RESOLVED at `5534cc6`): `TemplateMatchExemplar.__post_init__`
  only validates type + ndim; a NaN/inf close_prices slips past
  validation. When `match_forward` invokes `_min_max_normalize` on the
  bad exemplar, the ValueError propagates out of the function; the
  pipeline caller's broad try/except buries the failure + stamps
  `template_match=None` for the row even though OTHER valid same-class
  exemplars in the cohort would have produced hits.
  
  Fix: per-exemplar try/except inside `match_forward` (skip bad
  exemplar; continue with cohort); symmetric defense in `match_reverse`;
  symmetric per-call defense on the candidate-side normalize call.
  
  Discriminating test
  (`test_match_forward_isolates_bad_exemplar_from_cohort`): plants one
  NaN exemplar + one finite identical exemplar; asserts the finite
  exemplar produces a hit with similarity_score=1.0. Pre-fix: NaN
  exemplar raises through match_forward → caller stamps tm=None
  (hits=0). Post-fix: NaN exemplar skipped → finite cohort exemplar
  yields hit (hits=1).

- **Minor #2** (ACCEPT-WITH-RATIONALE banked): the benchmark's
  `assert result >= 0` sanity check at
  `tests/patterns/test_template_matching_benchmark.py:164-166` is
  non-discriminating (would pass with zero hits). The benchmark's
  primary purpose is the 120s timing gate per spec §5.7 line 706; the
  hit-count sanity is intentionally loose because the random-fixture-
  generated exemplar lengths (25-35 bars) vs candidate length (30 bars)
  admit some band-infeasibility cases. **Banked as V2 candidate**:
  tighten to `assert result > 0` if the synthetic universe shape ever
  changes such that band-infeasibility is guaranteed not to suppress
  all hits.

**Round 2**: 0 Critical + 0 Major + 0 Minor. **NO_NEW_CRITICAL_MAJOR**.

Chain converged at R2 (2 rounds total).

---

## §7 Pre-Codex orchestrator-side review (21st cumulative C.C lesson #6)

Dispatched to `general-purpose` subagent BEFORE invoking Codex MCP per
dispatch brief §4.4 #18 BINDING.

**Expansion #1 (T3.SB2 hotfix `cf3c489` discipline — grep `swing/` for
hardcoded duplicates of new T2.SB5 constants)**: CLEAN. Grep on all
new module-level constants (`SAKOE_CHIBA_WINDOW_RATIO`,
`GEOMETRIC_SCORE_PREGATE_THRESHOLD`, `MAX_WINDOWS_PER_TICKER`,
`EXEMPLAR_CORPUS_SUBSAMPLE_THRESHOLD/LIMIT`, `COMPOSITE_GEOMETRIC_WEIGHT`,
`COMPOSITE_TEMPLATE_MATCH_WEIGHT`, `COMPOSITE_SCORE_MAX`) returned ZERO
hardcoded duplicates in template-matching / composite-scoring /
pipeline domains within `swing/`. Pre-existing references (e.g.,
weather classifier `FLAT_MARGIN_PCT = 0.1` + drift_logging histogram
`0.1` bin width) are different-domain and ACCEPTABLE — leave unchanged.

5-tuple `("vcp", "flat_base", "cup_with_handle", "high_tight_flag",
"double_bottom_w")` audit on T2.SB5-new files: ZERO new hits.

**Expansion #2 (T2.SB4 R1 M1 lesson — cross-check spec source-of-truth
against dispatch brief sketches)**: CLEAN. Byte-fidelity verified
across spec §5.7 + §5.8 (see §5 above for the audit).

**Verdict**: CLEAN — proceed to Codex MCP. 21st cumulative C.C lesson
#6 validation **BANKED CLEAN** with BOTH scope expansions applied.

---

## §8 Forward-binding lessons surfaced

### NEW gotcha #1: Bad-exemplar isolation in retrieval functions

**Discovered 2026-05-21 (T2.SB5 Codex R1 Minor #1; RESOLVED at `5534cc6`).**

`TemplateMatchExemplar.__post_init__` (template_matching.py:122) only
validates type + ndim of `close_prices`; a NaN/inf array slips past
construction. When `match_forward` then invokes `_min_max_normalize`
on the bad bundle, the ValueError propagates out of the function;
the pipeline caller's broad try/except buries the failure + stamps
`template_match_score=None` for the row even though OTHER valid
same-class exemplars in the cohort would have produced hits.

**Pre-empt in any future retrieval-style function that consumes a
cohort + delegates per-element work to a normalization/transformation
helper that can raise**: per-element try/except around the helper
(skip bad element; continue with cohort) rather than letting the
exception bubble up + suppress the whole call. Aligns with the
existing "per-row failure isolation" discipline in pipeline step
runners.

### NEW gotcha #2: DTW Sakoe-Chiba band infeasibility on asymmetric series

**Surfaced 2026-05-21 during T-A.5.4 integration testing; non-defect
behavior documented at template_matching.py:202-208.**

When candidate (N bars) and exemplar (M bars) lengths are asymmetric
beyond the Sakoe-Chiba band's reach (e.g., 2-bar candidate vs 50-bar
exemplar with 10% band), the DTW DP table's final cell remains `inf`
because the path is infeasible within the band. `match_forward` +
`match_reverse` skip such exemplars (treat as "no match found")
rather than poisoning the hit list with a non-finite distance.

This is correct semantic behavior but worth documenting: a candidate
window much shorter or longer than the exemplar corpus distribution
may yield zero hits even when the candidate's pattern_class has
exemplars planted. This is V1-acceptable; V2 may consider
length-stratified exemplar selection or adaptive band widths.

### NEW gotcha #3: Universe histogram must reflect POST-template composite

**Discovered during T-A.5.4 architecture design; honored at
runner.py:1964-1968.**

When the pipeline's `_step_pattern_detect` Pass-2 layer adds a
template-matching post-processing step that modifies `composite_score`,
the downstream `universe_context["composite_scores"]` histogram MUST
be seeded from the POST-template composites (the final persisted
values), NOT the pre-template fallback (the Pass-1
`min(1.0, geometric_score)` placeholder). The dispatch brief watch
item #11 + #12 highlighted this. Implementation correctly builds
`final_universe_scores` from `resolved_emit_list[i][8]` (the post-
template composite_score).

**Pre-empt in any future pipeline step that mutates a column AFTER
the universe-snapshot point**: explicitly enumerate which column
the universe histogram should reflect + verify the universe-build
happens AFTER all mutations.

### Inherited from T2.SB4 (preserved in T2.SB5)

- **Evidence-tier vs composite-tier score cap distinction**: preserved
  via the L5 LOCK + `compute_composite_score` clamp on BOTH paths.
- **Pre-Codex review must cross-check spec source-of-truth against
  dispatch brief sketches**: applied as Expansion #2 in this dispatch;
  CLEAN verdict from pre-Codex review.

---

## §9 S1 inline gate confirmations

- [x] All 6 T-A.5.X tasks committed (plus 1 Codex R1 fix commit).
- [x] `python -m pytest -m "not slow" -q -n auto` PASS: **5412 passed, 3 skipped, 0 failed.**
- [x] `python -m pytest -m slow tests/patterns/test_template_matching_benchmark.py -q -o "addopts=-ra --strict-markers"` PASS: mean **8.33s** << 120s gate (~14x under budget).
- [x] `ruff check swing/` clean (0 E501 — canonical CI scope).
- [x] Schema version unchanged at v20 (no migrations under T2.SB5 scope).
- [x] Pre-Codex orchestrator-side review dispatched + verdict CLEAN (21st cumulative C.C lesson #6 BANKED CLEAN with BOTH scope expansions).
- [x] All commits have empty `Co-Authored-By` trailer (verified via `git log --pretty='%(trailers:key=Co-Authored-By)' --not main | grep -c .` returning 0; ~302+ cumulative ZERO trailer streak preserved).
- [x] Codex MCP adversarial-critic chain converged to `NO_NEW_CRITICAL_MAJOR` (R2; faster than the T2.SB4 R5 convergence; matches the 2-4 rounds expectation per brief §5.1).

---

## §10 Pre-Codex orchestrator-side review verdict (verbatim summary)

**Reviewer**: `general-purpose` subagent (focused review with brief §3
file-scope + §4 watch items + §5 done criteria + §6 LOCKs as anchors).

**Findings**:
- Scope Expansion #1: CLEAN (no hardcoded duplicates).
- Scope Expansion #2: CLEAN (byte-fidelity confirmed against spec
  §5.7 + §5.8).
- LOCK fidelity audit L1-L12: PASS (with `cap_candidates_per_ticker`
  helper noted as defensive-only since the runner's `windows[-1]`
  choice satisfies Pruning #3 trivially — V1-acceptable).
- 10 additional adversarial findings reviewed; all classified as
  ACCEPTABLE per documented behavior.

**Verdict**: CLEAN — proceed to Codex MCP. 21st cumulative C.C lesson
#6 validation BANKED CLEAN with BOTH scope expansions applied.

---

## §11 S2 benchmark observation

`pytest-benchmark` run on operator's hardware:
```
Name (time in s)                                                         Min     Max    Mean  StdDev  Median     IQR  Outliers     OPS  Rounds  Iterations
----------------------------------------------------------------------------------------------------------------------------------------------------------
test_dtw_full_pipeline_completes_within_120s_on_baseline_hardware     8.3315  8.3315  8.3315  0.0000  8.3315  0.0000       0;0  0.1200       1           1
```

- Mean: **8.33 seconds**
- Gate: 120 seconds
- Margin: **~14.4× under budget**
- Total DTW pair-computations: ~62,500 (250 candidates × 5 patterns ×
  50 exemplars per class per spec §5.7 line 706 budget).

Generous margin allows for production overhead:
- Per-exemplar OHLCV fetch via OhlcvCache.
- Lease-fenced read overhead.
- Per-row drift_log serialization.
- Pandas Timestamp coercion + boolean masking.

V2 candidates banked:
- Tighten benchmark hit-count assertion if synthetic universe is
  re-shaped (Codex R1 M#2 ACCEPT-WITH-RATIONALE).
- Length-stratified exemplar selection (gotcha #2 banking).
- Adaptive Sakoe-Chiba band based on series-length ratio.

---

## §12 Cross-bundle pin closure confirmations

### Closure #1: `test_pattern_exemplars_schema_shape_invariant`

- **Location**: `tests/data/test_v20_migration.py:833`
- **Plan reference**: `§H.3` row 7.
- **Pre-T2.SB5 state**: `@pytest.mark.skip(reason="...un-skip at T2.SB3 + T2.SB5...")` — T2.SB3 closer did NOT un-skip; T2.SB5 closes the lag.
- **Action**: removed `@pytest.mark.skip` decorator; body unchanged
  (already correctly verifying the v20 schema shape invariant).
- **Verified**: test PASS post un-skip.

### Closure #2: `test_pattern_evaluations_template_match_score_persistable`

- **Location**: `tests/data/test_v20_migration.py:885` (planted).
- **Plan reference**: `§H.3` row 8.
- **Pre-T2.SB5 state**: test did NOT exist anywhere on main HEAD per
  `git grep` audit (plan §H.3 row 8 said "planted at T2.SB3 T-A.3.6"
  but T2.SB3 did not plant it).
- **Action**: PLANTED + un-skipped (un-skipped from start since T2.SB5
  lands the column-population logic). Body verifies (a) `template_match_score`
  accepts NULL (pre-T2.SB5 fallback path + post-T2.SB5 empty-exemplar
  path); (b) accepts a float in [0.0, 1.0] via INSERT/SELECT round-trip
  with exact-equality-within-epsilon assertion + parseable
  `nearest_exemplar_ids_json`.
- **Verified**: test PASS.

---

## §13 Phase 13 dispatch sequence forward state

Per plan §H.1:

- ✅ **T2.SB5 SHIPPED** (this dispatch). Template matching DTW +
  composite scoring + 120s benchmark gate + 2 cross-bundle pin
  closures + 35 net fast-test passes + 1 un-skip.
- ▶ **T3.SB3 NEXT** — Review auto-fill consuming OhlcvCache (5 tasks
  per plan §G.8). Branches from main HEAD AFTER T2.SB5 merge.
  Inherits Phase 13 detector substrate + template matching layer
  (templates may inform "top-3 similar prior reviews" pre-population
  per spec §6.3).
- ▶ **T2.SB6 AFTER T3.SB3** — Closed-loop surface + Theme 1 annotated
  charts (8 tasks per plan §G.9; includes T-A.6.6b Deficiency 1
  fold-in). Consumes `template_match_nearest_exemplar_ids_json` for
  top-3 thumbnail rendering per spec §5.10 page content #3.
- ⏸ **[PAUSE FOR OPERATOR LIST ADDITIONS]** — orchestrator surfaces
  the pause at T2.SB6 SHIPPED + housekeeping boundary per
  `project_phase13_t4_sb_pause_for_list_additions` BINDING memory.
- ▶ **T4.SB closer** — Usability triage + Q4 close-tracking + T-D.6b
  metrics-audit (8 tasks + operator-added items).

---

## §14 Streaks preserved

- **ZERO `Co-Authored-By` trailer drift**: ~302+ cumulative commits
  (T2.SB5 adds 7; ZERO trailers across all). Verified pre-amend +
  post-amend on T-A.5.1 (amended to clean the initial trailer; all
  subsequent 6 commits clean from the start).
- **C.C lesson #6 cumulative validation**: 20× banked clean through
  T2.SB4; **21× banked CLEAN at T2.SB5 with BOTH SCOPE EXPANSIONS
  applied** (hardcoded-duplicate audit + spec source-of-truth
  byte-fidelity).
- **5-detector V1 set COMPLETE per L2 LOCK** preserved (no detector
  widening at T2.SB5; template matching layered on top per L2).

---

## §15 Operator-paired S2-S4 gate dispatch

Per dispatch brief §5.2:

### S2 (benchmark on operator's hardware)
```powershell
cd c:/Users/rwsmy/swing-trading/.worktrees/phase13-t2-sb5-template-matching
python -m pytest -m slow tests/patterns/test_template_matching_benchmark.py -q -o "addopts=-ra --strict-markers"
```
Expected: mean << 120s (orchestrator observed 8.33s on this hardware).

### S3 (CLI integration probe)
```powershell
python -m swing.cli pipeline run
```
Verify: `pattern_evaluations` rows for any aplus tickers with
geometric_score >= 0.4 carry non-NULL `template_match_score` in
[0.0, 1.0] AND `template_match_nearest_exemplar_ids_json` as a
parseable JSON list of 1-3 exemplar IDs AND `composite_score` in
[0.0, 1.0] (clamped via `compute_composite_score`).

DBW row spot-check: `geometric_score = 1.10` + `composite_score = min(1.0, 0.60 × 1.10 + 0.40 × template_match_score)` ≤ 1.0.

### S4 (cross-check on known historical VCP)
Operator selects a known historical VCP setup (or any pattern with
corpus coverage) + verifies `match_forward(candidate_window,
exemplar_corpus, top_k=3)` returns plausible historical bases as
top-3 hits (subjective shape similarity assessment vs operator's
mental model).

Per T-A.1.7 corpus carrying metadata-only (no embedded OHLCV bars),
S4 requires fresh OHLCV fetch via OhlcvCache for the candidate's
ticker + each exemplar's ticker. May require yfinance/Schwab quota
budget for ~10-20 fetches per S4 probe.

---

*End of T2.SB5 return report. Ready for integration-merge of
`phase13-t2-sb5-template-matching` into main via `--no-ff`. ~302+
cumulative ZERO Co-Authored-By trailer streak preserved. 21st
cumulative C.C lesson #6 validation BANKED CLEAN with BOTH SCOPE
EXPANSIONS applied. 5-detector V1 PRIMARY substrate + SECONDARY
template matching layer + composite scoring all in place per spec
§5.7 + §5.8. Next dispatch: T3.SB3 (Review auto-fill consuming
OhlcvCache) per plan §H.1.*
