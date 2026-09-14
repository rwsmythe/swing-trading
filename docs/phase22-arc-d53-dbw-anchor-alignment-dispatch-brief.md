# Phase 22 — D53: the double-bottom-W detector cannot fire in production (anchor-alignment composition fix)

**Author:** CHARC (tool-development director), 2026-09-14. **Commissioned:** operator, 2026-09-14 ("execute the items backlog IAW your recommendation").
**Executor:** the orchestrator dispatches an implementer cell; the orchestrator runs Reviewer B at its gate; RD QAs the measurement-adjacent half at return.
**Audience of §1–§6:** the implementer cell, via the orchestrator's dispatch. Line numbers drift; ground on SYMBOLS.
**Expected size:** one small production change in ONE file (`swing/patterns/double_bottom_w.py`), a version-string bump, four tests, docstring supersessions. Risk is not size; it is the two REFUSALS in §4.

**Tripwire self-check (harness-architecture §5):** no schema · no new module · no dependency · no standing process · no `swing/trades`/`swing/data` carve-out → **no tripwire crossed.** CHARC-lane defect regardless (`swing/patterns/`).

**Stage recommendation (CHARC, the orchestrator may push back in-lane):** dispatch EXECUTING directly off this brief — no `writing-plans` loop. The design was settled BY EXECUTION (§1), the change is bounded to one function's predicate, and the plan-stage protocol (harness §5.1) exists to stop exactly the 3.8M-token plan loop a change this size would otherwise buy. Reviewer A runs to convergence per charter §2.9; B runs at the orchestrator's gate on the finished tree.

---

## §0 READ FIRST (pointers, not paraphrases)

1. `docs/tool-director-context.md` §4 row **D53** — the finding, its evidence, and RD's condition.
2. `swing/patterns/double_bottom_w.py` — `_backward_slice_dbw_structure` (the alignment predicate, the `enforce_anchor_alignment` branch), `DETECTOR_VERSION`, the module docstring's "Anchor_date contract" paragraph.
3. `swing/patterns/foundation.py` — `generate_candidate_windows`, the `zigzag_pivot` branch (one window per DOWN swing; `anchor_date = start_date = sw.end_date`, `end_date = last bar`).
4. `swing/pipeline/runner.py` — the `window = windows[-1]` selection in the pattern-detect step and its comment ("one verdict per (ticker, pattern_class)"). **You do not change this file.**
5. `tests/patterns/test_double_bottom_w.py` — `_bars_uvwx_dbw`, `_stage_2_conn`, `_candidate_window_at_trough_1_zigzag`, and the four `test_dbw_zigzag_pivot_anchor_*` / `test_dbw_non_zigzag_mode_*` tests.
6. `docs/implementer-dispatch-recipe.md` (read from the MAIN repo by absolute path — the worktree copy is stale by design) and `docs/harness-architecture.md` §5.1 SUPERSESSION-BY-REPLACEMENT and the DISCHARGED-DEFERRAL rules.

## §0.1 SKILL POSTURE

- Do NOT invoke `superpowers:brainstorming` or `writing-plans`. The design is settled (§1–§2).
- DO use `superpowers:test-driven-development`: every change is red-first; the discriminating test in §3.1 must be seen RED on the unfixed tree before the fix lands.
- Reviewer A (the implementer's adversarial loop) runs to convergence per the recipe. Reviewer B is the ORCHESTRATOR's, on the finished head. You do not pre-empt it.
- You never post to a mailbox. Your return report is your final chat message to the orchestrator.

---

## §1 THE DEFECT — determined by execution, twice, on the suite's own synthetic W

`generate_candidate_windows(bars, "zigzag_pivot")` emits one window per qualifying DOWN swing, anchored at that swing's low. For a COMPLETED W there are two such lows — trough 1 and trough 2 — and the runner takes `windows[-1]`, the LATEST anchor, which is trough 2. The DBW detector, in zigzag mode, rejects any W whose trough 1 is more than ±1 day from the anchor. So the window the runner always hands it is the one window the detector always refuses.

Measured 2026-09-14 (CHARC, this brief's author; reproduces the 2026-09-10 record exactly), with `_bars_uvwx_dbw()` pushed through the PRODUCTION generator, the detector called as the runner calls it (Stage-2 conn, ticker, `asof_date` = last bar):

| window handed to the detector | anchor | `anchor_reason` | `geometric_score` |
|---|---|---|---|
| `windows[0]` | 2026-01-24 (trough 1) | `zigzag_pivot:swing_1_down` | **1.10** |
| `windows[-1]` — what the runner picks | 2026-03-03 (trough 2) | `zigzag_pivot:swing_3_down` | **0.00** (zero envelope; both troughs stamped as the window end) |
| `windows[-1]`, alignment disabled (control: `anchor_reason` swapped to `ma_crossover:control`, nothing else changed) | 2026-03-03 | — | **1.10**, `trough_1_date` 2026-01-24, `trough_2_date` 2026-03-03 |

The control isolates the cause: on the exact window the runner chooses, the ONLY thing standing between the detector and a 1.10 is the trough-1 alignment predicate, and the anchor it refuses sits on trough 2 TO THE DAY. Bar clipping is not a factor (the generator clips on `end_date` only; the trough-2 window still contains trough 1). The live-DB consequence is D53's: 1,302 of 1,302 DBW signals at zero across 66 sessions; the two June exemplars ran the same path.

**The instrument note that travels with this brief:** a first run of that control WITHOUT the Stage-2 conn returned 0.00 on ALL three windows — the detector's Stage-2 gate fires before the slice. Call the detector the way the runner and the tests call it (`conn=`, `ticker=`, `asof_date=`), or your discriminating test will be red for the wrong reason and green for the wrong fix.

## §2 THE FIX — fork census (both branches stated; the chosen branch is a ruling, not a preference)

**F1 — where the fix lives.**
- **(a) CHOSEN — detector-local.** In zigzag mode, `_backward_slice_dbw_structure` accepts a candidate landmark tuple when the anchor aligns (within the existing ±1-day tolerance) with **trough 1 OR trough 2**. Rationale: the most-recent-low anchor of a COMPLETED W is trough 2 by construction; trough 1 is what a window anchored mid-formation lands on. Both are the same W. The Codex R1 Major #2 defense ("a window anchored at trough A must not score a later W anchored at trough B") is PRESERVED: an anchor that is neither trough of the tuple is still refused (§3.2 pins this).
- (b) REJECTED — runner iterates windows for DBW. Changes the one-verdict-per-ticker contract for all five classes and the idempotency key's meaning; wider than the defect.
- (c) REJECTED — drop alignment in zigzag mode. Reopens the exact hole Major #2 closed.

**F2 — the version string.** `DETECTOR_VERSION` becomes `double_bottom_w@v1.1.0`. RD's condition (D53 row, RD mail `dbw-detector-silence` 2026-09-10) binds: the immutable temporal log is NOT rewritten; historical rows stay as emitted under `v1.0.0`; the fixed detector emits FORWARD under the new string. `tests/research/double_bottom_w_backtest/test_cohort.py` carries `"double_bottom_w@v1.0.0"` as a literal in a HISTORICAL-ROW fixture — it is data, not a mirror of the constant; **leave it.** `runner.py` imports the constant (`DBW_VERSION`) and needs no edit.

**F3 — docstrings that now state a superseded rule.** The module docstring "Anchor_date contract" paragraph, the `_backward_slice_dbw_structure` docstring's anchor-contract paragraph, the comment block above `_ZIGZAG_ANCHOR_ALIGN_TOLERANCE_DAYS`, and the test helper `_candidate_window_at_trough_1_zigzag`'s docstring all say the anchor IS trough 1. **Supersession is performed by REPLACEMENT** (harness §5.1): rewrite each to the two-trough rule; no "amended 2026-09-14" notes in normative voice. The change record is the commit message. `foundation.py:458-461` is cited by those docstrings — read it; if it also asserts trough-1-only for DBW, replace there too; if it states the generic base-START semantic, leave it and say so in the return.

No other fork found. A fork discovered mid-work STOPS the work and returns to the orchestrator (plan-stage protocol clause 3), not a local resolution.

## §3 TESTS (the roster; each names what it discriminates)

3.1 **The composition test — RED before, GREEN after:** `_bars_uvwx_dbw()` → `generate_candidate_windows(bars, "zigzag_pivot", ticker="UVWX")` → `windows[-1]` → `detect_double_bottom_w(bars, window, conn=_stage_2_conn(), ticker="UVWX", asof_date=last bar)` → assert `geometric_score == pytest.approx(1.10)`, `trough_1_date == date(2026, 1, 24)`, `trough_2_date == date(2026, 3, 3)`, and assert the window's `anchor_reason` startswith `zigzag_pivot` and its `anchor_date == trough_2_date` (so the test cannot silently pass through a generator change that starts emitting a trough-1 window last). This is the only test in the DBW file that calls the generator; that absence is the fixture-routes-around-the-branch class and this test closes it.
3.2 **The preserved defense — negative control:** same bars, a `zigzag_pivot` window anchored at a date that is NEITHER trough (the existing misaligned test uses 2026-02-10, the center-peak vicinity — keep it as is; it must stay GREEN on the fixed tree). Add its trough-2 twin's boundary: anchor at trough 2 + 2 days → refused (zero envelope); anchor at trough 2 + 1 day → accepted at 1.10. The pair pins the inequality direction rather than guessing it.
3.3 **The existing four alignment tests stay green unchanged** (`..._aligned_with_trough_1_detects_w`, `..._misaligned_with_trough_1_rejects`, `..._within_1day_tolerance_detects_w`, `..._non_zigzag_mode_skips_anchor_alignment_check`). If any goes red the fix is wrong, not the test.
3.4 **Version pin:** a test asserting `DETECTOR_VERSION == "double_bottom_w@v1.1.0"` AND that `runner.py`'s registered `(detect_double_bottom_w, "double_bottom_w", DBW_VERSION)` tuple carries the same string (import both; compare — the drift-test shape, not a grep).
3.5 Full fast suite on the final head (`-n 4` if `-n auto` is memory-killed in your seat — D52); ruff clean.

## §4 LOCKS AND REFUSALS

- **REFUSE** any edit to `swing/pipeline/runner.py`, `swing/patterns/foundation.py` (except a docstring replacement under F3, reported), any migration, any other detector. The defect is one predicate.
- **REFUSE** any write to the live DB or any backfill/re-score of historical `pattern_detection_events` rows. Forward emission only. (RD's measurement-chain lock; D53 row.)
- The `foundation.py` generator contract (`anchor_date = start_date = swing low`, `end_date = last bar`) is unchanged.
- Evidence-vs-composite cap (1.10 evidence / 1.0 composite) is unchanged.
- Zero `Co-Authored-By`; conventional commit messages; TDD per task.

## §5 RETURN REPORT (the ORCHESTRATOR posts it AFTER QA — the cell reports in chat only)

To `charc,rd`, type `return_report`, subject ≤ 80 chars. Body carries: the head SHA; the 3.1 test's RED output on the unfixed tree (quoted) and GREEN on the fixed; the A-loop verdict line and the B transcript path + verdict (harness §5.1 B-gate: no transcript, no clearance); the F3 docstring sites replaced (list); the `foundation.py:458-461` determination; the suite line with SHA.

**RD's QA at return (measurement-adjacent, RD rules it; CHARC holds):** the two June DBW exemplars (`research/studies/2026-06-08-minervini-exemplar-recall.md`, class table) re-run through the exemplar-recall path under `v1.1.0` — hit/miss with method. This is CALIBRATION evidence for RD's T9 reading, NOT a merge gate: the synthetic proves the mechanism; whether real Ws pass the eight criteria is RD's specificity question, exactly as RD scoped it.

## §6 EVIDENCE PER ROUND (harness §5.1)

Each review round's FOUR artifacts — prompt, diff input, transcript, ledger — copied to `~/swing-data/review-transcripts/22-d53-exec/` the moment the round's assertions pass; the cumulative ledger committed beside this brief's plan-of-record in the worktree (`docs/superpowers/plans/2026-09-14-phase22-arc-d53-dbw-anchor-alignment.ledger.md`). The worktree is deletable only when both halves are preserved.

## §7 FORWARD MEASUREMENT (after merge; owners named)

- The first nightly after merge emits DBW rows under `v1.1.0`. RD reads the count of non-zero DBW signals against the 1,302-at-zero baseline — the temporal clause binds: only runs executing the fixed code evidence the fix.
- CHARC closes D53 on that run's evidence, not on the merge.
