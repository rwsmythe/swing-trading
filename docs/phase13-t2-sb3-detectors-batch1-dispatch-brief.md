# Phase 13 T2.SB3 — Detectors batch 1 (VCP + flat_base + cup_with_handle) dispatch brief

**Status:** READY FOR DISPATCH. Drafted 2026-05-20 PM post-T2.SB2 + T-PT9 SHIPPED + housekeeping at main HEAD `71739ed`. Largest single sub-bundle remaining in Phase 13 (9 tasks; +90-150 fast tests projected; +1 slow E2E). Per plan §G.4 lines 1573-1732.

**Branch:** `phase13-t2-sb3-detectors-batch1` — branches from main HEAD `71739ed`.

**Worktree:** create via `git worktree add .worktrees/phase13-t2-sb3-detectors-batch1 phase13-t2-sb3-detectors-batch1`.

**Time estimate:** orchestrator wall-clock 10-16 hours operator-paced (per `feedback_time_estimates_overstated.md` ÷3-5x for accuracy; T2.SB3 is the largest single sub-bundle).

---

## §1 Scope summary

**3 rule-based geometric detectors** consuming T2.SB2 foundation primitives + `OhlcvCache` substrate from T1.SB0 + v20 `pattern_evaluations` table from T-A.1.1:

| Detector | Spec lock | Worked example | Failing tests target |
|---|---|---|---|
| VCP | §5.2 (8 criteria) | §10.1 CVGI hypothetical | 12+ tests |
| flat_base | §5.3 (7 criteria) | §10.2 alternative pass scenario (22% uptrend) | 8+ tests |
| cup_with_handle | §5.4 (8 criteria) + §10.7 rounded-vs-V LOCK + §D.11 LOCK | §10.3 worked example | 12+ tests |

Plus 6 supporting tasks: pipeline recon + integration (NEW `_step_pattern_detect` step), drift_logging per OQ-9, selective Codex retroactive T2.SB3 evaluation against T-A.1.7 corpus, slow E2E, closer.

Per plan §G.4: 9 tasks T-A.3.1 through T-A.3.9. Cross-bundle pin un-skip at `tests/patterns/test_foundation_integration.py:231` per plan §H.3 line 2617 (T2.SB3 + T2.SB4 consumers).

### §1.1 Inheritance from T2.SB2 + T2.SB1 forward-binding lessons

This is the FIRST consumer of T2.SB2 foundation primitives + the FIRST detector batch consuming the T-A.1.7 corpus + the FIRST sub-bundle exercising the cross-bundle pin un-skip workflow. Several inherited lessons MUST be honored:

**From T2.SB2 return report §4 (banked at `71739ed` housekeeping)**:
1. **Vectorize EMA + ma_crossover hot-paths** (Codex R1 Important #3 + #7 deferred from T2.SB2). EMA via `pandas.Series.ewm(span=window, adjust=False).mean()`; ma_crossover via boolean mask. Both O(n) algorithmically but currently use Python loops that will dominate detector wall-clock at T2.SB3 scale. **If detector wall-clock exceeds 100ms per (ticker, window) tuple on operator hardware**, vectorize as part of this dispatch.
2. **Per-mode `anchor_date` contract**: `generate_candidate_windows` emits 3 anchor modes with DIFFERENT semantics:
   - `zigzag_pivot`: anchor_date = inferred base START (spec-faithful).
   - `ma_crossover`: anchor_date = trigger event date (NOT base start).
   - `high_low_breakout`: anchor_date = breakout confirmation bar (NOT base start).
   **Detectors consuming non-zigzag_pivot modes MUST perform backward-slicing from anchor_date** to assemble base context. T2.SB3's 3 detectors all CONSUME windows; brief §4.2 watch item enumerates the per-mode contract handling.
3. **Shared NaN sanitizer**: extend existing helper OR create `swing/patterns/_sanitize.py` that drops NaN bars before invoking foundation primitives. yfinance/Schwab archives carry NaN holiday-adjacent rows; foundation primitives reject NaN at entry; detectors MUST call the shared sanitizer rather than duplicating drop logic.
4. **Realistic OHLC fixtures**: some T2.SB2 unit tests used H==L==Close shortcuts. **T2.SB3 detector tests MUST use realistic OHLC fixtures** with H > Close > L divergence + Volume > 0. The **T-A.1.7 silver corpus at `data/phase13-t2-sb1-corpus/pattern_exemplars_dump.jsonl`** supplies real-shape fixtures across all 5 V1 pattern classes.
5. **Spec amendments banked for T2.SB3 brainstorming** (Codex R1 Major #1 + #2 ACCEPT at T2.SB2):
   - `current_stage(conn, ticker, asof_date)` signature — spec §5.1.5 line 526 API sketch omits `conn`; T2.SB3 detectors that consume trend-state context PASS `conn` explicitly.
   - `generate_candidate_windows(bars, anchor_search_method, *, ticker, timeframe, ...)` signature — spec §5.1.3 line 494 API sketch omits ticker + timeframe; T2.SB3 detector callsites PASS both.
   - **T2.SB3 dispatch SHOULD propose spec amendments at brainstorming OR fold into per-detector spec criteria fields** (operator-decision-pending; default = propose amendments at T-A.3.1 recon).
6. **Cross-bundle pin un-skip discipline**: at T-A.3.9 closer, remove `@pytest.mark.skip` decorator at `tests/patterns/test_foundation_integration.py:231`; add imports for `swing.patterns.vcp`, `swing.patterns.flat_base`, `swing.patterns.cup_with_handle`; assert each detector imports the expected primitives via `inspect.getsource` or function-attribute checks OR exercise the detector against a fixture and verify foundation primitives are called via mock-patch + call-args verification. **Pin un-skip is BINDING at T-A.3.9 closer** — leaving it skipped silently extends the pin window beyond schedule (CLAUDE.md gotcha "Cross-bundle pin fixture-shape mismatch silently extends the pin window").
7. **`VolumeSegment.swing_index` provisional** (T2.SB2 R1 Minor #5 banked): field is implementer-added not spec-defined. T2.SB3 CONFIRMS whether detector evidence-trail needs it (likely YES for VCP contraction-sequence evidence). If consumed, lock semantics in the detector test; if unused, strip at the T-A.3.9 closer.

**From T2.SB1 T-A.1.8 closer return report (banked at `2746bbb` housekeeping)**:
8. **Cup-with-handle rounded-vs-V hard gate caused 4 of 5 cup dispatches at T-A.1.7 to fail by sub-1% margins.** T2.SB3 cup_with_handle detector SHOULD either (a) **widen the §10.7 gate by 5-10% tolerance** OR (b) **downgrade to scoring penalty** (subtract 0.10 from geometric_score for marginal rounded-zone rather than hard fail). **Implementer VERIFIES at T-A.3.4 recon** which approach is appropriate; brief default = widen tolerance with §10.7 LOCK preservation (5 bars HARD PASS / 3-4 bars 0.10 PENALTY / 2 bars HARD FAIL per §10.7 marginal-zone semantics).
9. **VCP monotonic-tightening hard gate**: consider 1-violation tolerance. T2.SB3 VCP detector at T-A.3.2 SHOULD plant a discriminating test asserting **either** strict monotonic OR 1-violation tolerance behavior is locked in the criterion #3 evaluation; brief default = strict per spec §5.2 criterion #3 (no tolerance widening without operator escalation).
10. **HTF consolidation tightness** — N/A for T2.SB3 (HTF lands at T2.SB4); banked for forward reference.
11. **Precursor 3-dip "early identifier" pattern** — V2 detector candidate; NOT in T2.SB3 scope.

### §1.2 Pipeline integration recon (T-A.3.1)

Brief default per plan §G.4: NEW `_step_pattern_detect` step after `_step_evaluate` (preserves separation of concerns; detection consumes Stage 2 + RS-rank-filtered candidate pool from `_step_evaluate`).

**Implementer VERIFIES at T-A.3.1 recon** by reading `swing/pipeline/runner.py` end-to-end + writing recon doc at `docs/phase13-t2-sb3-recon.md` enumerating: (a) pipeline integration point; (b) per-detector evaluation order; (c) `pattern_evaluations` write discipline (caller-tx; NO `INSERT OR REPLACE` per CLAUDE.md gotcha). If recon reveals a better integration point (e.g., extending `_step_evaluate` directly OR a NEW step somewhere else in the chain), implementer MAY revise per "VERIFIES + may revise" precedent from T1.SB0 gate-fix + T-PT9 chain.

---

## §2 Per-task acceptance criteria (per plan §G.4 verbatim)

| Task | Title | Acceptance |
|---|---|---|
| T-A.3.1 | Pipeline integration recon | Recon doc enumerates integration point + per-detector evaluation order + write discipline; integration point VERIFIED |
| T-A.3.2 | VCP detector per spec §5.2 | 12+ tests pass; §10.6 tolerance semantics applied; `VCPEvidence` + `Contraction` frozen dataclasses with `__post_init__` Literal[...] frozenset validation |
| T-A.3.3 | flat_base detector per spec §5.3 | 8+ tests pass; §10.2 errata correction (18% relaxed threshold) honored; `FlatBaseEvidence` frozen dataclass |
| T-A.3.4 | cup_with_handle detector per spec §5.4 + §10.7 + §D.11 LOCK | 12+ tests pass; rounded-vs-V semantics per §10.7 marginal-zone disposition (5 bars HARD PASS / 3-4 bars 0.10 PENALTY / 2 bars HARD FAIL); `CupWithHandleEvidence` frozen dataclass + `_is_rounded_cup` helper |
| T-A.3.5 | drift_logging.py per OQ-9 | 4 tests pass; `FeatureDistributionLog` frozen dataclass per §D.7 + `capture_feature_distribution` helper; JSON column on pattern_evaluations |
| T-A.3.6 | Pipeline `_step_pattern_detect` integration | 4 tests pass; step invokes 3 detectors; emits 1 pattern_evaluations row per (ticker, pattern_class); feature_distribution_log_json on each row; zero-candidate-windows succeeds without writes |
| T-A.3.7 | Selective Codex T2.SB3 retroactive evaluation per spec §5.9 step 4 | failing-test-then-pass cycle; `retroactive_codex_evaluation_against_corpus` recomputes geometric_score for Claude silver rows + fires Codex on high-stakes predicate rows |
| T-A.3.8 | T2.SB3 fast E2E + 1 slow E2E | Fast E2E seeds 3 candidate windows × 3 detectors; asserts pattern_evaluations rows + composite_score = geometric_score (no template-match yet); Slow E2E asserts VCP geometric_score in [0.9, 1.0] on CVGI-like real fixture per §10.1 |
| T-A.3.9 | T2.SB3 closer | Full fast-test suite + ruff sweep PASS; cross-bundle pin un-skipped at `tests/patterns/test_foundation_integration.py:231` per §1.1 #6 |

**Recommended ordering**: T-A.3.1 (recon-first; sets integration anchor) → T-A.3.2 + T-A.3.3 + T-A.3.4 (3 detectors; order doesn't matter; recommend VCP first as it's the densest spec) → T-A.3.5 (drift_logging; needed before pipeline integration) → T-A.3.6 (pipeline integration) → T-A.3.7 (retroactive Codex; consumes the 3 detectors + drift_logging) → T-A.3.8 (E2E) → T-A.3.9 (closer with cross-bundle pin un-skip).

---

## §3 Files in scope

**Create** (4 production modules + 4 unit-test files + 1 slow E2E file + 1 recon doc):
- `swing/patterns/vcp.py`
- `swing/patterns/flat_base.py`
- `swing/patterns/cup_with_handle.py`
- `swing/patterns/drift_logging.py`
- `tests/patterns/test_vcp.py`
- `tests/patterns/test_flat_base.py`
- `tests/patterns/test_cup_with_handle.py`
- `tests/patterns/test_drift_logging.py`
- `tests/integration/test_phase13_t2_sb3_detectors_e2e.py` (1 slow E2E)
- `docs/phase13-t2-sb3-recon.md` (T-A.3.1 output)

**Modify**:
- `swing/pipeline/runner.py` (add `_step_pattern_detect` step; integration point per T-A.3.1 recon)
- `swing/patterns/labeling.py` (add `retroactive_codex_evaluation_against_corpus()` per T-A.3.7)
- `tests/patterns/test_foundation_integration.py` (un-skip the cross-bundle pin at line 231 per T-A.3.9 closer)

**Optionally create** (if recon at T-A.3.1 reveals need):
- `swing/patterns/_sanitize.py` (NEW shared NaN sanitizer per T2.SB2 forward-binding lesson #3)

**NOT in scope (V2 / future sub-bundles)**:
- HTF detector (T2.SB4 territory)
- DBW detector (T2.SB4 territory)
- Template matching DTW (T2.SB5 territory)
- Review auto-fill (T3.SB3 territory)
- Closed-loop / charts surface (T2.SB6 territory)
- Spec amendments to §5.1.3 + §5.1.5 signatures (banked for T2.SB3 brainstorming OR fold into per-detector spec — operator decision pending)

---

## §4 Watch items (cumulative discipline; banked across Phase 12 + 12.5 + 13)

### §4.1 T2.SB3-specific watch items

1. **PURE-FUNCTION DISCIPLINE** preserved for detectors: each detector consumes `(bars, candidate_window) -> <Detector>Evidence`; ZERO DB writes from inside the detector function itself; pipeline step layer (`_step_pattern_detect`) owns the DB writes. Per T2.SB2 LOCK L2 precedent.
2. **Spec §5.2 + §5.3 + §5.4 lock fidelity**: every criterion + tolerance value + boundary case MUST match spec verbatim. Implementer SHOULD grep spec for the criterion text; do NOT paraphrase.
3. **§10.6 tolerance semantics LOCK** uniform across all 3 detectors: e.g., VCP criterion #2 28% uptrend boundary = 30% - 2% tolerance per §10.6; flat_base criterion #2 18% boundary = 20% - 2% tolerance per §10.2 errata.
4. **§10.7 cup-curvature LOCK** centered on `cup_bottom_date ± 10 days`: 5 bars HARD PASS / 3-4 bars 0.10 PENALTY (marginal zone) / 2 bars HARD FAIL. Per T2.SB1 forward-binding lesson #8: widen marginal-zone if 4-of-5 cup exemplars hit sub-1% margin failure. **Implementer VERIFIES at T-A.3.4** + escalates to operator if data suggests widening beyond §10.7 LOCK.
5. **§D.11 `_is_rounded_cup` LOCK**: 5-bars-in-marginal-window predicate; returns `tuple[bool, float]` where float is the per-bar penalty contribution (0.0 for HARD PASS; 0.10 for marginal; +inf for HARD FAIL).
6. **VCP criterion #3 monotonic-tightening**: strict per spec §5.2 (no tolerance widening without operator escalation). Forward-binding lesson #9 from T2.SB1 noted "consider 1-violation tolerance" — DEFER unless data demands.
7. **Frozen dataclass + `__post_init__` Literal[...] frozenset validation** for every detector evidence dataclass (VCPEvidence + Contraction + FlatBaseEvidence + CupWithHandleEvidence + FeatureDistributionLog). Honors cumulative CLAUDE.md gotcha "`Literal[...]` not runtime-enforced".
8. **Cross-bundle pin un-skip at T-A.3.9** per §1.1 #6 BINDING. Plan §H.3 row 6.
9. **NaN-handling**: detectors REJECT NaN at entry via the shared sanitizer (or inline drop with explicit error message); zero-baseline-volume edge case returns 0.0 NOT NaN NOT raise.
10. **Real-shape OHLC fixtures**: detector unit tests MUST use realistic OHLC (H > Close > L divergence + Volume > 0); reference T-A.1.7 corpus at `data/phase13-t2-sb1-corpus/pattern_exemplars_dump.jsonl` for shape templates.

### §4.2 Pipeline integration watch items (T-A.3.6)

11. **Per-mode `anchor_date` contract handling** per §1.1 #2: detectors that consume `ma_crossover` OR `high_low_breakout` mode windows MUST perform backward-slicing from anchor_date to assemble base context. **Discriminating test**: feed a `ma_crossover` candidate window where anchor_date is the trigger event; assert detector backward-slices to find the base start.
12. **`pattern_evaluations` write discipline (caller-tx; no INSERT OR REPLACE)**: `_step_pattern_detect` opens single `BEGIN IMMEDIATE / COMMIT / ROLLBACK` outer transaction; INSERTs rows via SELECT-then-INSERT pattern per CLAUDE.md gotcha "SQLite INSERT OR REPLACE is DELETE old + INSERT new semantically".
13. **Sandbox short-circuit**: `_step_pattern_detect` SHOULD honor `cfg.integrations.schwab.environment == 'sandbox'` gating — but **VERIFY at recon T-A.3.1**: detectors don't directly call Schwab (consume cached OHLCV bars), so sandbox gating may NOT be needed at this layer. Default: NO sandbox gating; bars consumed are already routed via the ladder at OhlcvCache.
14. **Caller-tx vs own-tx discipline**: `_step_pattern_detect(*, cfg, lease, eval_run_id, conn, ohlcv_cache)` per §A.5. Step receives `conn` from caller (pipeline runner); step layer owns transaction; detectors are pure functions. Per cumulative Phase 8 + Phase 12 C.C transactional discipline (3-piece family: caller-controlled at repo layer / transaction-owning at service layer / reject-caller-held-tx at any new single-transaction service).
15. **Zero-candidate-windows graceful handling**: step exits early without writes when no candidates produced; emits INFO log; no exception.

### §4.3 Drift logging watch items (T-A.3.5)

16. **JSON column on pattern_evaluations** per OQ-9 V1 LOCK; V2 dedicated table only if Phase 13.5 demands.
17. **Consistent schema across all 5 detectors** (V1 batch 1 = 3 + V2 batch 2 = 2 at T2.SB4): `FeatureDistributionLog` dataclass shape stable across detector classes.
18. **Histogram bin count for composite_score**: matches §5.11 specification.

### §4.4 Selective Codex retroactive evaluation watch items (T-A.3.7)

19. **Random 15% CONTINUES per spec §5.9 step 4**: `retroactive_codex_evaluation_against_corpus()` re-fires Codex on random 15% of T-A.1.7 silver rows where geometric_score is NOW computable (T2.SB3 detectors land); high-stakes clause activated per spec §5.9.
20. **Idempotency**: re-invoking against the same corpus row does NOT double-fire Codex; SELECT-first idempotency check (per cumulative CLAUDE.md gotcha "SELECT-first idempotency MUST precede payload validation" from Phase 12 C.C R1 Major #2).

### §4.5 Cumulative process discipline

21. **Pre-Codex orchestrator-side review (C.C lesson #6 BINDING; 18th cumulative validation expected)**: implementer dispatches a focused reviewer subagent with this brief's §3 file-scope + §4 watch items + §5 done criteria as anchors BEFORE invoking Codex MCP.
22. **NO `Co-Authored-By` footer** — cumulative ~249+ commit streak ZERO trailer drift; do NOT regress. Per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15).
23. **`python -m swing.cli` from worktree cwd**, NOT bare `swing` (memory feedback_worktree_cli_invocation).
24. **ASCII-only on any new CLI/print path** — if detector emits diagnostic via print/click.echo, ASCII-only invariant BINDS (no `→` / `§` / em-dash glyphs).
25. **Edit tool for per-file edits** when fixing E501 / type / import-order issues — do NOT bulk-rewrite (Phase 12.5 #3 L-W4 precedent).
26. **Cite the discipline in commit messages** (matches all prior T1.SB0 + T2.SB1 + T3.SB1 + T2.SB2 commit-message precedent).

---

## §5 Done criteria

### §5.1 S1 (inline; implementer self-verifies before invoking Codex)

- [ ] All 9 T-A.3.X tasks committed per plan §G.4 acceptance criteria.
- [ ] `python -m pytest -m "not slow" -q -n auto` PASS post-merge. **Expected**: 5184 + ~90-150 new fast tests from 3 detectors + 4 from drift_logging + 4 from pipeline integration + 1 from retroactive Codex + 1 from fast E2E = ~5275-5350 total; 0 failures; ≤6 skipped (no NEW skips; the cross-bundle pin at `tests/patterns/test_foundation_integration.py:231` MUST un-skip and PASS).
- [ ] `python -m pytest -m slow tests/integration/test_phase13_t2_sb3_detectors_e2e.py -q` PASS for the 1 NEW slow E2E test.
- [ ] `ruff check swing/` clean (0 E501).
- [ ] Schema version unchanged at v20 (`python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"` returns `20`).
- [ ] Pre-Codex orchestrator-side review dispatched + verdict captured (18th cumulative C.C lesson #6 validation expected CLEAN).
- [ ] All commits on branch `phase13-t2-sb3-detectors-batch1` have empty `Co-Authored-By` trailer (verified via `git log --pretty='%(trailers:key=Co-Authored-By)' phase13-t2-sb3-detectors-batch1 --not main | grep -c .` returning 0).
- [ ] Codex MCP adversarial-critic chain converges to `NO_NEW_CRITICAL_MAJOR` (expected 3-5 rounds based on largest-sub-bundle scope + 3-detector breadth).

### §5.2 S2 (operator-paired post-merge)

- **T2.SB3 S2**: `python -m swing.cli pipeline run` against operator's production candidate pool. Verify `_step_pattern_detect` lands `pattern_evaluations` rows; operator inspects rows for plausible verdicts (geometric_score in [0, 1]; structural_evidence_json populated; feature_distribution_log_json populated).
- **T2.SB3 S3**: operator visually compares detector output for a known historical VCP setup (e.g., a prior CVGI-style base from the T-A.1.7 corpus) against subjective assessment.

---

## §6 LOCKs (do not deviate without operator escalation)

- **L1**: Spec §5.2 + §5.3 + §5.4 criteria + §10.6 tolerance + §10.7 cup curvature + §D.11 `_is_rounded_cup` BIND verbatim. Implementer reads spec; does NOT paraphrase.
- **L2**: ZERO DB writes inside detector functions (`detect_vcp`, `detect_flat_base`, `detect_cup_with_handle`). All DB writes routed through `_step_pattern_detect` step layer with caller-tx discipline.
- **L3**: NO `INSERT OR REPLACE` on `pattern_evaluations` writes. SELECT-then-INSERT pattern per CLAUDE.md gotcha + cumulative Phase 8 + Phase 12 transactional discipline.
- **L4**: Cross-bundle pin at `tests/patterns/test_foundation_integration.py:231` MUST un-skip at T-A.3.9 closer. Skipping it (leaving as-is) violates plan §H.3 schedule + extends the pin window silently.
- **L5**: §10.7 rounded-vs-V marginal-zone semantics LOCK preserved (5 bars HARD PASS / 3-4 bars 0.10 PENALTY / 2 bars HARD FAIL). If T-A.1.7 corpus exemplar miss rate justifies widening beyond marginal zone, escalate to operator with empirical evidence before deviating.
- **L6**: Branch base = main HEAD `71739ed` at dispatch time. Verify at T-A.3.1 Step 0: `git merge-base --is-ancestor 71739ed HEAD` returns 0.
- **L7**: 3 frozen dataclasses (VCPEvidence + FlatBaseEvidence + CupWithHandleEvidence) carry `__post_init__` Literal[...] frozenset validation honoring T-A.1.5b R3 M#1 cumulative gotcha. Plus `Contraction` sub-dataclass for VCP + `FeatureDistributionLog` for drift_logging.

---

## §7 Reference materials (read before dispatching)

- **Plan**: `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` §G.4 lines 1573-1732 (T2.SB3 verbatim task list).
- **Spec**: `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md`:
  - §5.2 VCP (8 criteria + §10.1 worked example)
  - §5.3 flat_base (7 criteria + §10.2 worked example + errata)
  - §5.4 cup_with_handle (8 criteria + §10.3 worked example)
  - §5.9 selective Codex retroactive (steps 1-4)
  - §5.11 composite_score histogram bin count
  - §10.6 tolerance-semantics uniformity LOCK
  - §10.7 cup-curvature centered-on-cup_bottom_date LOCK
  - §D.7 FeatureDistributionLog dataclass shape
  - §D.11 `_is_rounded_cup` LOCK
- **T2.SB2 return report** at `docs/phase13-t2-sb2-with-phase9-tz-drift-fix-return-report.md` §4 — 7 forward-binding lessons banked for T2.SB3 inheritance.
- **T-A.1.7 corpus manifest** at `data/phase13-t2-sb1-corpus/README.md` — real-shape OHLC fixtures across 5 V1 pattern classes (use for detector unit-test fixtures).
- **T-A.1.7 silver dump** at `data/phase13-t2-sb1-corpus/pattern_exemplars_dump.jsonl` — 34 rows (13 gold + 21 silver) for retroactive Codex evaluation at T-A.3.7.
- **CLAUDE.md gotchas relevant to T2.SB3**:
  - `Literal[...]` not runtime-enforced (T-A.1.5b R3 M#1 inherited)
  - ASCII-only on runtime CLI paths
  - SQLite INSERT OR REPLACE is DELETE + INSERT semantically (per L3 LOCK)
  - SELECT-first idempotency MUST precede payload validation (per T-A.3.7 watch item #20)
  - Cross-bundle pin fixture-shape mismatch silently extends pin window (per L4 LOCK)
  - HTF post-pole sub-window is `consolidation_*` not `flag_*` (N/A for T2.SB3; banked for T2.SB4)

---

## §8 Post-dispatch housekeeping checklist (orchestrator-inline)

When T2.SB3 merge ships:

1. **CLAUDE.md line 3 refresh** — update HEAD reference + mention T2.SB3 SHIPPED + 18th cumulative C.C lesson #6 validation; mention any NEW gotchas surfaced.
2. **phase3e-todo.md** — new top entry for T2.SB3 SHIPPED with: Codex chain shape + ACCEPT-WITH-RATIONALE banks + forward-binding lessons for T3.SB2 / T2.SB4 inheritance + per-detector empirical observations (rounded-vs-V miss rate; VCP monotonic-violation rate; flat_base tolerance behavior); cross-bundle pin un-skip confirmation.
3. **orchestrator-context.md** — refresh current state; demote former to Prior; archive-split per size-check trigger (Prior state count will be 10 at cap pre-housekeeping; demote pushes to 11; archive oldest).
4. **orchestrator-context-archive.md** — new "Appended 2026-05-2X" section with archived Prior verbatim.
5. **Streaks update** — bank the 18th cumulative C.C lesson #6 validation (if CLEAN); bank ~260+ cumulative ZERO Co-Authored-By streak (T2.SB3 expected ~10-15 commits).
6. **Spec amendment decision** — per §1.1 #5 + #11: T2.SB3 dispatch should propose spec amendments OR fold into per-detector spec fields. Operator decision captured at post-merge housekeeping if not resolved earlier.

---

## §9 Forward-binding to T3.SB2 + T2.SB4

T3.SB2 = Exit auto-fill (5 tasks; plan §G.5). Sequenced AFTER T2.SB3 per plan §H.1 dispatch sequence. Inherits Schwab integration discipline from T3.SB1 + uses `OhlcvCache.get_or_fetch` exit-time context.

T2.SB4 = Detectors batch 2 (HTF + DBW) (7 tasks; plan §G.6). Inherits ALL T2.SB3 detector patterns + per-mode anchor_date contract + cross-bundle pin discipline. HTF naming `consolidation_*` not `flag_*` BINDING per CLAUDE.md gotcha from T-A.1.8 Deficiency 3.

Forward-binding lessons expected from T2.SB3 to T2.SB4 (per detector empirical observations):
- Per-detector tolerance widening rationale (if any) — banked at post-merge housekeeping.
- VCP monotonic-tightening 1-violation tolerance disposition (if data demands).
- Cup-with-handle rounded-vs-V marginal-zone semantics empirical validation against T-A.1.7 corpus.
- Pipeline `_step_pattern_detect` extension pattern (T2.SB4 detectors plug into same step).

---

*End of dispatch brief. Phase 13 T2.SB3 (9 tasks; +90-150 fast tests + 1 slow E2E projected) — first detector batch consuming T2.SB2 foundation primitives + T-A.1.7 corpus + cross-bundle pin un-skip. 3-5 Codex rounds expected for largest-sub-bundle scope. 18th cumulative C.C lesson #6 validation expected. ZERO Co-Authored-By footer drift streak (~249+ commits) preserved.*
