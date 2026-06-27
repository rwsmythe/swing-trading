# Phase 13 T2.SB2 + T-PT9 — combined dispatch return report

**Status:** SHIPPED on branch `phase13-t2-sb2-foundation-primitives` (10 commits on top of main HEAD `4da4ad2`); ready for operator-paired S2 gate + merge.

**Date:** 2026-05-20.

**Dispatch brief:** `docs/phase13-t2-sb2-with-phase9-tz-drift-fix-dispatch-brief.md` (combined T2.SB2 plan §G.3 6 tasks + T-PT9 Phase-9 calendar-drift fix).

---

## 1. Commit chain (10 commits; ZERO Co-Authored-By trailer throughout)

```
6392e0c chore(phase13): T2.SB2 Codex R2 minor cleanup - ASCII discipline + Low-NaN test + error message precision
cb3119d fix(phase13): T2.SB2 Codex R1 resolution - current_stage ordering + anchor_date docstring + adaptive_threshold NaN
2f79207 test(phase13): T2.SB2 closer - foundation primitives integration + ruff (T-A.2.6)
ce091a6 fix(phase13): T-PT9 - Phase-9 test fixture calendar-drift dynamic anchor
c46170c fix(phase13): foundation primitives code-quality follow-up (T-A.2.1-T-A.2.5)
9eeedf2 feat(phase13): foundation current_stage trend-template wrapper (T-A.2.5)
384bbf2 feat(phase13): foundation volume profile primitives (T-A.2.4)
66f8db9 feat(phase13): foundation variable-window candidate generator (T-A.2.3)
20ad818 feat(phase13): foundation zigzag extrema with adaptive threshold (T-A.2.2)
83f6d13 feat(phase13): foundation smoothing primitives (T-A.2.1)
```

Branch base: `4da4ad2` (main HEAD at dispatch time). LOCK L6 verified.

---

## 2. Test counts (S1 gate verified)

| Stage | Fast suite | tests/patterns/ | Notes |
|-|-|-|-|
| Baseline (pre-T2.SB2) | 5149 | 53 | Per CLAUDE.md status line |
| Post T-A.2.5 (initial 5 tasks) | 5168 (est) | 72 | 19 new foundation tests |
| Post c46170c code-quality fix-iteration | 5176 (est) | 80 | +8 NaN-policy + threshold-floor + sorted-index tests |
| Post ce091a6 T-PT9 | 5177 (est) | 80 | +1 calendar-drift regression test (in `tests/integration/`) |
| Post 2f79207 T-A.2.6 closer | 5180 + 6 skipped | 82 | +1 integration test + 1 new cross-bundle pin skip |
| Post cb3119d Codex R1 resolution | 5182 (est) + 6 skipped | 84 | +2 ordering-discrimination + adaptive NaN tests |
| **Post 6392e0c R2 cleanup (FINAL)** | **5183 + 6 skipped** | **86** | +2 parametrize-Low-NaN cases |

Final: **5183 fast tests passing + 6 skipped + 0 failures**. Schema v20 unchanged. Ruff clean on `swing/patterns/foundation.py` + all touched test files.

T-PT9 also closes the 2 previously-failing Phase-9 integration tests (`test_phase9_full_happy_path_across_all_sub_bundles` + `test_phase9_bundle_c_e2e_account_snapshot_and_hypothesis_audit`); both now PASS.

---

## 3. Codex review history

| Round | Critical | Major | Minor | Verdict |
|-|-|-|-|-|
| R1 | 0 | 5 | 5 | ISSUES_FOUND |
| R2 | 0 | 0 | 4 | NO_NEW_CRITICAL_MAJOR |

**R1 disposition:**
- Major #5 (current_stage ORDER BY id DESC vs run_ts DESC) -> RESOLVED at `cb3119d` (foundation.py:711 ORDER BY chain extended; discriminating test plants reverse-insert-order rows + pre-fix FAIL + post-fix PASS verified).
- Major #3 (anchor_date per-mode semantic) -> RESOLVED at `cb3119d` via docstring clarification (foundation.py:369 + 445); V1 LOCK acknowledged; V2 candidate banked.
- Minor #3 (adaptive_initial_threshold_pct NaN check) -> RESOLVED at `cb3119d` (foundation.py:172-180) + parametrized 3-column at `6392e0c`.
- Major #1 (current_stage(conn, ticker, asof_date) signature widening) -> ACCEPT-WITH-RATIONALE: any DB-backed wrapper requires a connection; spec API sketch abstracted; flag for spec amendment at T2.SB3 brainstorming.
- Major #2 (generate_candidate_windows kwargs widening) -> ACCEPT-WITH-RATIONALE: CandidateWindow dataclass requires ticker + timeframe per spec lines 498-499; documented inline.
- Major #4 (current_stage 'undefined' collapses 4 conditions) -> ACCEPT-WITH-RATIONALE: V1 LOCK per spec line 523 "thin wrapper"; documented; future V2 can distinguish.

**R2 disposition:**
- Minor #1 (ASCII em-dash regression in R1 docstring updates) -> RESOLVED at `6392e0c`.
- Minor #3 (adaptive_initial_threshold_pct Low column not covered) -> RESOLVED at `6392e0c` via parametrize-3-column.
- Minor #4 (error message "contains NaN" -> "contains NaN or non-finite values") -> RESOLVED at `6392e0c`.
- Minor #2 (per-mode start_date == anchor_date test pin) -> DEFERRED to T2.SB3 dispatch brief §5.

**Total Codex review iterations:** 2 rounds (within MIN_ROUNDS..MAX_ROUNDS = 2..5 band per copowers settings).

---

## 4. Forward-binding lessons banked (for T2.SB3 inheritance)

The T2.SB3 dispatch brief should inherit these forward-binding obligations:

1. **Vectorize EMA + ma_crossover hot-paths** (Codex R1 Important #3 + #7; deferred from this fix-iteration). EMA via `pandas.Series.ewm(span=window, adjust=False).mean()`; ma_crossover via boolean mask `(ma50 > ma150) & (ma50.shift(1) <= ma150.shift(1))`. Both are O(n) algorithmically but currently use Python loops that will dominate detector wall-clock at T2.SB3 scale.

2. **Per-mode anchor_date contract** (Codex R2 Minor #2 deferred). `generate_candidate_windows` emits 3 modes with DIFFERENT anchor_date semantics:
   - `zigzag_pivot`: anchor_date = inferred base START (spec-faithful).
   - `ma_crossover`: anchor_date = trigger event date (NOT base start).
   - `high_low_breakout`: anchor_date = breakout confirmation bar (NOT base start).
   T2.SB3 detector dispatch brief §5 watch item: cup_with_handle / VCP / flat_base detectors that consume non-zigzag_pivot modes MUST perform their own backward-slicing from anchor_date to assemble base context. Add explicit per-mode test pins (`start_date == anchor_date` + stable `anchor_reason` prefix per mode).

3. **Shared NaN sanitizer** (Codex R1 Minor #2). yfinance/Schwab archives carry NaN holiday-adjacent rows; foundation primitives reject NaN at entry. T2.SB3 ships a shared `swing/patterns/_sanitize.py` (or extends an existing helper) that drops NaN bars before invoking primitives; each detector calls the shared sanitizer rather than duplicating drop logic.

4. **Realistic OHLC fixtures** (Codex R1 Minor #4). Some foundation unit tests use H==L==Close shortcuts. T2.SB3 detector tests MUST use realistic OHLC fixtures with H > Close > L divergence + Volume > 0. The T-A.1.7 silver corpus at `data/phase13-t2-sb1-corpus/pattern_exemplars_dump.jsonl` supplies real-shape fixtures.

5. **Spec amendment for current_stage + generate_candidate_windows signatures** (Codex R1 Major #1 + #2). T2.SB3 brainstorming should propose spec amendments to §5.1.3 + §5.1.5 to acknowledge the implementer-faithful widened signatures (`conn` for current_stage; `*, ticker, timeframe` for generate_candidate_windows). Detector criteria at §5.2 line 538 + §5.3 + §5.4 + §5.5 + §5.6 will then pass `conn` explicitly.

6. **Cross-bundle pin un-skip discipline** (Codex R1 Minor #1). `tests/patterns/test_foundation_integration.py:test_foundation_primitives_consumed_by_detectors_invariant` is `@pytest.mark.skip` with detailed un-skip instructions. T2.SB3 dispatch brief checklist MUST cite this pin + its un-skip step (remove decorator; add detector module imports; assert call-args).

7. **VolumeSegment.swing_index provisional** (Codex R1 Minor #5). Field is implementer-added (not spec-defined); T2.SB3 confirms whether detector evidence-trail needs it or it should be stripped. Avoid expanding the dataclass further without detector-driven requirements.

---

## 5. Cross-bundle pin disposition

`test_foundation_primitives_consumed_by_detectors_invariant` planted at `tests/patterns/test_foundation_integration.py:231-256` per plan §H.3 + brief §4.1 #8.

**Un-skip schedule:** T2.SB3 (VCP + flat_base + cup_with_handle detector dispatch) + T2.SB4 (high_tight_flag + double_bottom_w detector dispatch).

**Un-skip instructions embedded in the test's skip-marker reason:**
1. Remove `@pytest.mark.skip` decorator.
2. Add imports for `swing.patterns.vcp`, `swing.patterns.flat_base`, `swing.patterns.cup_with_handle` (T2.SB3), then later for `swing.patterns.high_tight_flag`, `swing.patterns.double_bottom_w` (T2.SB4).
3. For each detector, assert it imports the expected primitives via `inspect.getsource` or function-attribute checks, OR exercise the detector against a fixture and verify foundation primitives are called (via mock-patch + call-args verification).

Test body raises `pytest.fail` so accidental un-skipping without implementing detector wiring fails loudly.

---

## 6. Deviations from brief (with rationale)

1. **Branch base: `4da4ad2`, NOT `2746bbb`** (LOCK L6 stated `2746bbb`). Rationale: operator's actual main HEAD at dispatch time was `4da4ad2` (one docs-only commit ahead of `2746bbb` — the brief commit itself). Branching from `4da4ad2` includes the dispatch brief in the worktree; `2746bbb` is still an ancestor (`git merge-base --is-ancestor 2746bbb HEAD` returns 0). No code-level conflict since the docs commit is docs-only.

2. **VolumeSegment dataclass shape (4 fields: start_date, end_date, avg_volume, swing_index).** Spec §5.1.4 references VolumeSegment by name but does NOT define its shape. Implementer designed the 4-field shape mirroring `Contraction` dataclass at spec lines 568-577 + adds `swing_index: int` for consumer correlation. Documented inline; Codex R1 Minor #5 acknowledged as provisional pending T2.SB3 confirmation.

3. **`current_stage` signature: `current_stage(conn, ticker, asof_date)`, NOT `current_stage(ticker, asof_date)`.** Spec §5.1.5 line 526 API sketch omits `conn`. Implementer added `conn` as first positional arg because no DB-backed wrapper can work without a connection. Documented inline; Codex R1 Major #1 accepted with rationale; spec amendment flagged for T2.SB3 brainstorming.

4. **`generate_candidate_windows` signature: keyword-only `ticker` + `timeframe` args added.** Spec §5.1.3 line 494 API sketch omits both. Implementer added because CandidateWindow dataclass requires them per spec lines 498-499. Documented inline; Codex R1 Major #2 accepted with rationale; spec amendment flagged for T2.SB3 brainstorming.

5. **T-PT9 calendar-drift fix applied per brief §1.2 hypothesis (test-fixture drift, NOT `is_back_recorded` logic).** Implementer's Step 1 recon confirmed orchestrator's hypothesis empirically: today (2026-05-20) - hardcoded "2026-05-12" = 8 days > 7-day threshold; `is_back_recorded` strict-`>` is correct as written. `swing/trades/account_equity_snapshots.py:49-63` UNTOUCHED per LOCK L3. Fix scoped to 2 test files + 1 new calendar-drift-proof regression test.

---

## 7. Cumulative streaks preserved

- **ZERO Co-Authored-By footer trailer drift:** all 10 commits verified empty trailer; cumulative project streak now ~249+ commits.
- **C.C lesson #6 17th cumulative validation:** orchestrator-side pre-Codex review dispatched + verdict APPROVED_FOR_CODEX before Codex MCP invocation. C.C lesson #6 streak CLEAN.
- **`Literal[...]` runtime-enforcement discipline:** 3 frozen dataclasses (Swing + CandidateWindow + VolumeSegment) all carry `__post_init__` validation against explicit frozensets (`_SWING_DIRECTIONS`, `_CANDIDATE_TIMEFRAMES`, indirect via `_ANCHOR_SEARCH_METHODS` at function entry). Honors the cumulative CLAUDE.md gotcha "Literal[...] not runtime-enforced" forward-binding lesson from T-A.1.5b R3 M#1.
- **ASCII-only on user-facing string paths:** after R2 cleanup, no non-ASCII glyphs in `swing/patterns/foundation.py` (R2 Minor #1 closed an em-dash regression introduced by the R1 docstring fix).

---

## 8. Files modified / created

**Created (7 files; +1898 lines net):**
- `swing/patterns/foundation.py` (731 lines pre-R1-R2; grown to ~756 after fix iterations)
- `tests/patterns/test_foundation_smoothing.py`
- `tests/patterns/test_foundation_extrema.py`
- `tests/patterns/test_foundation_candidate_windows.py`
- `tests/patterns/test_foundation_volume.py`
- `tests/patterns/test_foundation_trend_state.py`
- `tests/patterns/test_foundation_integration.py`

**Modified (2 files; T-PT9 only):**
- `tests/integration/test_phase9_full_happy_path.py` (+ dynamic anchor; + dynamic-date import)
- `tests/integration/test_phase9_end_to_end.py` (+ dynamic anchor; + new calendar-drift-proof regression test)

**Production code NOT touched (LOCK L3 verified):**
- `swing/trades/account_equity_snapshots.py` — UNCHANGED; `is_back_recorded` at lines 49-63 correct as written.

---

## 9. S2 operator-paired gate (post-merge)

Per dispatch brief §5.2:

- **T2.SB2 S2:** operator runs ad-hoc Python REPL (or `python -m swing.cli`-driven script) invoking foundation primitives against operator's real ticker data; verifies sanity (e.g., zigzag swings on a known VCP base produce plausible contraction sequence). Suggested ticker for sanity check: a recent VCP-base name from the operator's journal (e.g., the operator's pre-2026-05-15 CVGI base referenced in spec §5.2 worked example).
- **T-PT9 S2:** ZERO operator-paired gate needed — calendar-drift fix is test-only; S1 pytest pass is sufficient verification (the 2 previously-failing Phase-9 tests now PASS).

---

## 10. Recommended post-merge housekeeping

Per dispatch brief §8:

1. **CLAUDE.md line 3 refresh:** update HEAD reference to post-merge SHA + mention T2.SB2 + T-PT9 SHIPPED + 17th cumulative C.C lesson #6 validation CLEAN.
2. **CLAUDE.md gotcha REVISION:** the gotcha I (orchestrator) added at `2746bbb` HEAD ("`is_back_recorded` UTC-vs-HST date-boundary fix") was mis-framed per the T-PT9 recon. REVISE to: "Phase-9 test fixture calendar-drift; use `(date.today() - timedelta(days=N)).isoformat()` dynamic anchors with N <= threshold_days - margin for all `back-recorded` test fixtures. Same lesson family as L-E2 banked at Phase 12.5 #3 T-3.5." The function `swing/trades/account_equity_snapshots.py:is_back_recorded` is correct as written.
3. **phase3e-todo.md:** new top entry for T2.SB2 + T-PT9 SHIPPED; remove the "2026-05-20 Phase-9 TZ-drift followup TODO" section (now CLOSED).
4. **orchestrator-context.md:** refresh current state; demote former to Prior; archive-split per size-check trigger.
5. **orchestrator-context-archive.md:** new "Appended 2026-05-XX" section with archived Prior verbatim.
6. **Streaks update:** bank the 17th cumulative C.C lesson #6 validation (CLEAN); bank ~249+ cumulative ZERO Co-Authored-By streak.

---

*End of return report. Phase 13 T2.SB2 (6 tasks: T-A.2.1 through T-A.2.6) + T-PT9 (1 task) combined dispatch SHIPPED on branch `phase13-t2-sb2-foundation-primitives` at HEAD `6392e0c`. 10 commits; ZERO Co-Authored-By trailer; 5183 fast tests + 6 skipped + 0 failures; schema v20 unchanged; ruff clean; 2 Codex adversarial rounds NO_NEW_CRITICAL_MAJOR at R2. Ready for operator-paired S2 gate + orchestrator-side merge to main.*
