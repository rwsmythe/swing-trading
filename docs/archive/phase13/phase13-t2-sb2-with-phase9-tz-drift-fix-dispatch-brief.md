# Phase 13 T2.SB2 (foundation primitives) + Phase-9 TZ-drift fix — combined dispatch brief

**Status:** READY FOR DISPATCH. Drafted 2026-05-20 post-T2.SB1+T3.SB1 SHIPPED + housekeeping at main HEAD `2746bbb`. Combines plan §G.3 T2.SB2 scope (foundation primitives; 6 tasks) with a parallel one-shot fix for the 2 pre-existing Phase-9 calendar-drift test failures banked at the same housekeeping (phase3e-todo.md "2026-05-20 Phase-9 TZ-drift followup TODO" section).

**Branch:** `phase13-t2-sb2-foundation-primitives` — branches from main HEAD `2746bbb`.

**Worktree:** create via `git worktree add .worktrees/phase13-t2-sb2-foundation-primitives phase13-t2-sb2-foundation-primitives`.

**Time estimate:** orchestrator wall-clock 6-10 hours operator-paced (per `feedback_time_estimates_overstated.md` ÷3-5x for accuracy).

---

## §1 Scope summary

**Two parallel deliverables**, both atomic-on-merge:

1. **T2.SB2 — Foundation primitives** (plan §G.3; tasks T-A.2.1 through T-A.2.6): create `swing/patterns/foundation.py` housing pure-logic primitives (smoothing + extrema + candidate windows + volume profile + trend-state wrapper) consumed by T2.SB3 + T2.SB4 detectors. ZERO DB writes; ZERO side-effects. Authoritative spec lock: spec §5.1 sub-sections 5.1.1 through 5.1.5. Plan §G.3 acceptance criteria + cross-bundle pin BINDING.

2. **T-PT9 — Phase-9 calendar-drift test fixture fix** (new task; sister to T2.SB2 closer; lands as final task before closer or absorbed by closer): closes 2 PRE-EXISTING failing tests `test_phase9_full_happy_path_across_all_sub_bundles` + `test_phase9_bundle_c_e2e_account_snapshot_and_hypothesis_audit`. **Recon-first scope** (see §1.2 below) — handoff brief framed the fix as one-line edit at `swing/trades/account_equity_snapshots.py:49-63` (`> 7` → `>= 7`), BUT orchestrator-side recon at 2026-05-20 revealed the brief mischaracterized root cause; actual root cause is **test fixture calendar-drift** (hardcoded `"2026-05-12"` constants in 2 test files that silently slip past the 7-day window as today's date advances). Same lesson family as L-E2 banked at Phase 12.5 #3 T-3.5 ("time-dependent fixture calendar-buffer ≥7d"). Implementer MUST verify root cause at recon time BEFORE applying fix.

### §1.1 Why batch

Operator batched per "minimal context-switch cost; both are well-scoped and TDD-friendly; combined dispatch keeps the cumulative C.C lesson #6 17th validation in a single bundle." Phase-9 fix is mechanically independent from T2.SB2 (touches different files; foundation primitives are creation-only in `swing/patterns/foundation.py`; Phase-9 fix touches `tests/integration/test_phase9_*.py` only). No code-level interaction risk.

### §1.2 ⚠ Recon-first scope for T-PT9 (calendar-drift hypothesis VERIFY before fix)

**Brief hypothesis (from handoff brief §3.4 + phase3e-todo §"2026-05-20 Phase-9 TZ-drift followup TODO"):** `is_back_recorded` `> 7` → `>= 7` at `swing/trades/account_equity_snapshots.py:49-63`.

**Orchestrator-side recon at 2026-05-20 FALSIFIED this hypothesis.** Actual recon findings:
- Test failure output: `(back-recorded: snapshot_date 2026-05-12 is >7 days before today 2026-05-20)`. Today 2026-05-20 minus hardcoded `2026-05-12` = 8 days; `8 > 7` = True → `is_back_recorded` correctly flags as back-recorded per `> threshold_days` strict comparison.
- Test ASSERTION at `tests/integration/test_phase9_full_happy_path.py:296`: `assert "back-recorded" not in r_snap.output` — test expects the snapshot to NOT be flagged as back-recorded.
- Test SET-UP at `tests/integration/test_phase9_full_happy_path.py:287`: `snapshot_date = "2026-05-12"` — HARDCODED CONSTANT.
- Same shape at `tests/integration/test_phase9_end_to_end.py:401, 405, 413` (snapshot_date hardcoded `"2026-05-12"` at `account snapshot --date` arg + assertion at line 405 + downstream fetchone() arg at line 413).
- `is_back_recorded` semantics (`> threshold_days`) match docstring + intent ("more than 7 days after"). Function is correct as written.

**Root cause = test fixture calendar-drift.** Tests were authored when "today" was ≤7 days from 2026-05-12 (sometime around mid-May 2026); as wall-clock advanced past 2026-05-19 the gap exceeded threshold + the back-recorded flag started firing for what the tests treat as "today's session" recording.

**Prescribed fix shape (implementer VERIFIES + may revise at recon time):**
1. Replace `snapshot_date = "2026-05-12"` (and inline equivalents) with a dynamic anchor: `snapshot_date = (date.today() - timedelta(days=2)).isoformat()` (2 days before today; safely inside 7-day window; preserves "recent backdated snapshot" semantics).
2. Update both downstream surfaces in each test: (a) the `--date` CLI arg; (b) the fetchone() WHERE clause arg; (c) the row equality assertion if it includes snapshot_date literal.
3. **Do NOT touch `is_back_recorded` function semantics** — it is correct. Touching it would mask the real lesson + create a fragile dependency on the boundary inequality direction.
4. Add 1 discriminating regression test that pins the dynamic-anchor pattern. Suggested name: `tests/integration/test_phase9_calendar_drift_anchor_does_not_drift.py::test_account_snapshot_today_minus_2_days_is_not_back_recorded`. Construct synthetic CLI invocation with `--date (date.today() - timedelta(days=2)).isoformat()` + assert "back-recorded" not in output. This test MUST PASS regardless of what wall-clock day it's run on; CI calendar drift cannot make it fail.

**Implementer recon obligation:** at T-PT9 Step 1 (recon), confirm orchestrator's calendar-drift hypothesis empirically by:
- Running `python -m pytest tests/integration/test_phase9_full_happy_path.py::test_phase9_full_happy_path_across_all_sub_bundles -x --tb=short` against current HEAD; capture failure output verbatim.
- Reading `swing/trades/account_equity_snapshots.py:49-63` `is_back_recorded` impl.
- Reading the 2 failing tests' snapshot_date setup verbatim.
- Documenting confirmed root cause in a recon note (inline commit message or recon doc).
- **IF recon reveals a DIFFERENT root cause** (e.g., HST-UTC `last_completed_session` drift + brief mis-recon was correct), implementer MAY revise fix shape — same allowance precedent as T1.SB0 gate-fix brief §1.2 "implementer-VERIFIES + may revise".

**CLAUDE.md gotcha revision candidate banked for post-dispatch housekeeping:** the gotcha I added at `2746bbb` HEAD ("`is_back_recorded` UTC-vs-HST date-boundary fix") is mis-framed per orchestrator-side recon. Post-T2.SB2-merge housekeeping should REVISE the gotcha to: "Phase-9 test fixture calendar-drift; same family as L-E2; use `(date.today() - timedelta(days=N)).isoformat()` dynamic anchors with N ≤ threshold_days - margin for all `back-recorded` test fixtures."

---

## §2 T2.SB2 task decomposition (plan §G.3 verbatim; 6 tasks)

Inherit plan §G.3 tasks T-A.2.1 through T-A.2.6 verbatim. Plan reference: `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md:1508-1571`.

| Task | Title | Spec lock | Acceptance |
|---|---|---|---|
| T-A.2.1 | `smooth_ema` + `smooth_kernel_regression` | spec §5.1.1 | 4 failing tests → impl → pass; pure functions; ZERO DB writes; EMA + kernel regression match known-good fixtures |
| T-A.2.2 | `extract_zigzag_swings` with adaptive threshold | spec §5.1.2 + §D.2 Swing dataclass | 5 failing tests; monotonic_narrow=True produces decreasing thresholds (VCP-specific); adaptive threshold per `max(3.0, ATR_5d_pct × 1.5)` heuristic |
| T-A.2.3 | `generate_candidate_windows` | spec §5.1.3 + §D.2 CandidateWindow dataclass | 4 failing tests; 3 anchor modes (zigzag_pivot + ma_crossover + high_low_breakout); multi-anchor mode V2-deferred |
| T-A.2.4 | `volume_trend_through_swings` + `breakout_volume_ratio` | spec §5.1.4 | 3 failing tests; edge case zero baseline volume → 0.0 (NOT NaN; NOT raise) |
| T-A.2.5 | `current_stage` trend-template wrapper | spec §5.1.5 | 2 failing tests; thin wrapper consuming shipped Phase 4 evaluation surface; ticker without evaluation returns `'undefined'` |
| T-A.2.6 | Closer — integration test + ruff sweep | — | End-to-end chain: smoothing → extrema → candidate windows → volume profile → trend state; full fast-test suite + ruff sweep |

**NEW TASK** (sister to closer; precede or absorb):

| Task | Title | Spec lock | Acceptance |
|---|---|---|---|
| T-PT9 | Phase-9 calendar-drift test fixture fix | n/a (test-only) | Recon-first; replace hardcoded `"2026-05-12"` in 2 test files with `(date.today() - timedelta(days=2)).isoformat()` dynamic anchor; add 1 NEW regression test pinning the dynamic anchor; verify 2 previously-failing tests now PASS; **do NOT modify `is_back_recorded` semantics** |

**Recommended ordering:** T-A.2.1 → T-A.2.2 → T-A.2.3 → T-A.2.4 → T-A.2.5 → T-PT9 (small + independent; lands before closer to avoid mixing test-fixture-fix with primitive-integration commit) → T-A.2.6 (closer; includes T-PT9 verification in the full-suite re-run).

---

## §3 Files in scope

**Create (T2.SB2):**
- `swing/patterns/foundation.py` — 5 functions (smooth_ema + smooth_kernel_regression + extract_zigzag_swings + generate_candidate_windows + volume_trend_through_swings + breakout_volume_ratio + current_stage) + 2 dataclasses (Swing + CandidateWindow per spec §D.2 + VolumeSegment).
- `tests/patterns/test_foundation_smoothing.py`
- `tests/patterns/test_foundation_extrema.py`
- `tests/patterns/test_foundation_candidate_windows.py`
- `tests/patterns/test_foundation_volume.py`
- `tests/patterns/test_foundation_trend_state.py`

**Modify (T-PT9):**
- `tests/integration/test_phase9_full_happy_path.py` — change line 287 hardcoded `snapshot_date = "2026-05-12"` to dynamic anchor; update downstream references at line 296 assertion + line 303 fetchone() arg if present.
- `tests/integration/test_phase9_end_to_end.py` — change line 401 `--date "2026-05-12"` CLI arg to dynamic anchor; update line 405 assertion + line 413 fetchone() arg.

**Create (T-PT9 regression test):**
- `tests/integration/test_phase9_calendar_drift_anchor.py` (or merge into either of the 2 existing files as a sibling test) — 1 test asserting `(date.today() - timedelta(days=2)).isoformat()` does not fire back-recorded; calendar-drift-proof.

**NO modifications to:**
- `swing/trades/account_equity_snapshots.py` — `is_back_recorded` semantics LOCKED.
- Anything in `swing/patterns/` except `foundation.py` creation.
- Existing `pattern_exemplars` / `pattern_evaluations` / `chart_renders` / `watchlist_close_track_flags` repos.

---

## §4 Watch items (T2.SB2 + T-PT9 cumulative)

Recurring discipline (banked across Phase 12 + 12.5 + 13 dispatches). Implementer + Codex 2nd-reviewer + orchestrator-side pre-Codex review consume this list.

### §4.1 T2.SB2 watch items

1. **PURE-FUNCTION DISCIPLINE** — all foundation primitives are pure functions; ZERO DB writes; ZERO side-effects; ZERO global state; ZERO logging from inside the primitive functions (logging belongs in callers/detectors).
2. **Spec §5.1 lock fidelity** — every function signature + return shape MUST match spec §5.1 verbatim. Implementer SHOULD grep spec for the function name; do NOT paraphrase.
3. **Swing + CandidateWindow + VolumeSegment dataclass shape (spec §D.2)** — frozen dataclasses; ALL fields named exactly as spec §D.2 specifies. CLAUDE.md gotcha precedent (Phase 12.5 Q2 R1 #1 tuple-vs-list frozen-dataclass invariant): frozen dataclass field types must be immutable sequences when applicable.
4. **`monotonic_narrow=True` semantics for VCP** — `extract_zigzag_swings(..., monotonic_narrow=True)` must produce DECREASING swing thresholds as swing index advances (per spec §5.1.2 LOCK). Discriminating test pattern: feed alternating ±N% pattern; assert thresholds[i+1] < thresholds[i] for all i.
5. **Adaptive threshold heuristic** — `max(3.0, ATR_5d_pct × 1.5)` per spec §5.1.2. Hardcode the constants ONLY where spec says hardcode; if spec says configurable, pin to cfg field.
6. **Zero-baseline volume edge case (T-A.2.4)** — `breakout_volume_ratio` against ZERO baseline must return `0.0`, NOT NaN, NOT raise. Discriminating test BINDING.
7. **`current_stage` thin-wrapper semantics (T-A.2.5)** — wrap shipped Phase 4 evaluation surface; do NOT re-implement trend-template logic; ticker without evaluation returns string `'undefined'` (per spec §5.1.5 LOCK).
8. **Cross-bundle pin discipline** — plant `test_foundation_primitives_consumed_by_detectors_invariant` at T-A.2.6 closer per plan §G.3 acceptance + plan §H.3 cross-bundle pin table row 6 (un-skips at T2.SB3 + T2.SB4). Skip-marker shape per Phase 13 plan §H.3 precedent: pin to specific consumer SHAs at un-skip time.
9. **ASCII-only on any new CLI/print path** (per CLAUDE.md gotcha) — T2.SB2 ships pure functions + tests; no CLI emit paths expected; if implementer introduces any `print`/`click.echo`/`sys.stdout.write` path, ASCII-only invariant BINDS (use `_` or words instead of `→` / `←` / `§`).
10. **`Literal[...]` not runtime-enforced** (recurring lesson from T-A.1.5b R3 M#1) — if foundation primitives have `Literal[...]` typed fields on data-integrity-relevant inputs (e.g., anchor reason enum), add `__post_init__` runtime validation against an explicit frozenset of allowed values.

### §4.2 T-PT9 watch items

11. **Recon-first verification** — confirm orchestrator's calendar-drift hypothesis (vs handoff-brief's `> 7` → `>= 7` hypothesis) BEFORE applying fix. Document in recon commit message OR inline recon comment.
12. **`is_back_recorded` semantics LOCKED** — do NOT modify the function. Touching it would mask the actual lesson + create fragile dependency on inequality direction.
13. **Dynamic-anchor calendar-drift-proof regression test** — new test must use `(date.today() - timedelta(days=N)).isoformat()` with N ≤ 5 (safely inside 7-day window with margin); test MUST pass regardless of what wall-clock day it runs on.
14. **Spell out N choice in commit message** — why 2 days (or 3, or 5)? Document the margin: e.g., "N=2 day delta gives 5-day margin before threshold; absorbs DST / 1-day wall-clock drift / weekend session boundaries without test flakiness."
15. **Do NOT widen scope to other calendar-drift candidates** — there may be other hardcoded date constants in the test suite; THIS dispatch fixes ONLY the 2 listed failing tests. Other candidates banked for V2 audit dispatch.

### §4.3 Cumulative process discipline

16. **Pre-Codex orchestrator-side review (C.C lesson #6 BINDING; 17th cumulative validation expected)** — implementer dispatches a focused reviewer subagent with this brief §3 file-scope + §4 watch items + §5 done criteria as anchors BEFORE invoking Codex MCP. Banks the 17th C.C lesson #6 validation in the cumulative streak.
17. **NO `Co-Authored-By` footer** — cumulative ~239+ commit streak ZERO trailer drift; do NOT regress. Per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15): do NOT add `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (or any other Co-Authored-By footer attributing the AI assistant) to ANY commit message.
18. **`python -m swing.cli` from worktree cwd, NOT bare `swing`** (memory feedback_worktree_cli_invocation; durable). Use `python -m swing.cli` for any CLI invocation during testing.
19. **Use Edit tool for per-file edits when fixing E501 / type / import-order issues** — do NOT bulk-rewrite files (Phase 12.5 #3 L-W4 precedent).
20. **`Co-Authored-By` discipline citation in commit messages preferred** — match T1.SB0 gate-fix + T2.SB1 + T3.SB1 + housekeeping commit-message precedent (cite the discipline explicitly).

---

## §5 Done criteria (S1 gate, inline; S2 gate, operator-paired)

### §5.1 S1 (inline; implementer self-verifies before invoking Codex)

- [ ] All 6 T-A.2.X tasks committed per plan §G.3 acceptance criteria.
- [ ] T-PT9 recon documented + fix applied + regression test landed.
- [ ] `python -m pytest -m "not slow" -q -n auto` PASS post-merge. **Expected**: 5149 + ~60-100 new fast tests from foundation primitives + 1 new regression test from T-PT9 = ~5210-5250 total; 0 failures (2 previously-failing Phase-9 tests now PASS via T-PT9 fix); ≤5 skipped (no NEW skips beyond inherited cross-bundle pins).
- [ ] `ruff check swing/` clean (0 E501).
- [ ] Schema version unchanged at v20 (`python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"` returns `20`).
- [ ] Pre-Codex orchestrator-side review dispatched + verdict captured.
- [ ] All commits on branch `phase13-t2-sb2-foundation-primitives` have empty `Co-Authored-By` trailer (verified via `git log --pretty='%(trailers:key=Co-Authored-By)' phase13-t2-sb2-foundation-primitives --not main | grep -c .` returning 0).
- [ ] Codex MCP adversarial-critic chain converges to `NO_NEW_CRITICAL_MAJOR` (expected 2-3 rounds based on small scope + pure-function discipline).

### §5.2 S2 (operator-paired post-merge)

- **T2.SB2 S2**: operator runs ad-hoc Python REPL (or `python -m swing.cli`-driven script) invoking primitives against operator's real ticker data; verifies sanity (e.g., zigzag swings on a known VCP base produce plausible contraction sequence).
- **T-PT9 S2**: ZERO operator-paired gate needed — calendar-drift fix is test-only; S1 pytest pass is sufficient verification.

---

## §6 LOCKs (do not deviate without operator escalation)

- **L1**: Spec §5.1 sub-section locks BIND verbatim function signatures + return shapes. Implementer reads spec; does NOT paraphrase.
- **L2**: ZERO DB writes in `swing/patterns/foundation.py`. All primitives pure. Pinned via discriminating test that imports + invokes every primitive against in-memory fixtures + asserts NO open SQLite connection objects created (`tests/patterns/test_foundation_pure_no_db_writes.py` candidate).
- **L3**: T-PT9 does NOT modify `swing/trades/account_equity_snapshots.py:49-63` `is_back_recorded`. Touching it requires operator escalation + brief revision.
- **L4**: T-PT9 dynamic-anchor regression test MUST be calendar-drift-proof (run-day-agnostic). Constructed via `date.today()` arithmetic; never hardcoded.
- **L5**: Cross-bundle pin `test_foundation_primitives_consumed_by_detectors_invariant` planted at T-A.2.6 closer with skip-marker per plan §H.3. Skip-msg cites un-skip target sub-bundles.
- **L6**: Branch base = main HEAD `2746bbb` at dispatch time. Verify at T-A.2.1 Step 0 (recon-shadow): `git merge-base --is-ancestor 2746bbb HEAD` returns 0.

---

## §7 Reference materials (read before dispatching)

- **Plan**: `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` §G.3 lines 1508-1571 (T2.SB2 verbatim task list).
- **Spec**: `docs/superpowers/specs/2026-05-18-phase13-charts-patterns-autofill-usability-design.md` §5.1 (smoothing + extrema + candidate windows + volume + trend-state) + §D.2 (Swing + CandidateWindow + VolumeSegment dataclass shapes).
- **CLAUDE.md gotchas relevant to T2.SB2**: `Literal[...]` not runtime-enforced (T-A.1.5b inherited); ASCII-only on runtime CLI paths; HTF `consolidation_*` not `flag_*` naming (CLA: T-A.1.8 inherited; affects T-A.2.X if any HTF-related primitive naming bleeds in — none expected per §5.1).
- **Phase-9 TZ-drift failing tests** (verified 2026-05-20):
  - `tests/integration/test_phase9_full_happy_path.py:287, 296, 303` (hardcoded `"2026-05-12"`).
  - `tests/integration/test_phase9_end_to_end.py:401, 405, 413` (hardcoded `"2026-05-12"`).
- **Lesson L-E2 banked at Phase 12.5 #3 T-3.5** (referenced in this brief §1.2): time-dependent fixture calendar-buffer ≥7d. Same family.

---

## §8 Post-dispatch housekeeping checklist (orchestrator-inline)

When T2.SB2 + T-PT9 merge ships:

1. **CLAUDE.md line 3 refresh** — update HEAD reference + mention T2.SB2 + T-PT9 SHIPPED; mention any NEW gotchas from Codex chain.
2. **CLAUDE.md gotcha REVISION** — the gotcha I added at `2746bbb` ("`is_back_recorded` UTC-vs-HST date-boundary fix") is mis-framed per orchestrator-side recon. REVISE to: "Phase-9 test fixture calendar-drift; use `(date.today() - timedelta(days=N)).isoformat()` dynamic anchors with N ≤ threshold_days - margin for all `back-recorded` test fixtures. Same lesson family as L-E2 banked at Phase 12.5 #3 T-3.5."
3. **phase3e-todo.md** — new top entry for T2.SB2 + T-PT9 SHIPPED; remove the "2026-05-20 Phase-9 TZ-drift followup TODO" section (now CLOSED).
4. **orchestrator-context.md** — refresh current state; demote former to Prior; archive-split per size-check trigger (Prior state count was 10 pre-this-housekeeping; demote pushes to 11; archive oldest).
5. **orchestrator-context-archive.md** — new "Appended 2026-05-XX" section with archived Prior verbatim.
6. **Streaks update** — bank the 17th cumulative C.C lesson #6 validation (if CLEAN); bank ~245+ cumulative ZERO Co-Authored-By streak.

---

## §9 Forward-binding to T2.SB3

T2.SB3 = Detectors batch 1 (VCP + flat_base + cup_with_handle); 9 tasks; +90-150 fast tests; branches off main HEAD post-T2.SB2 merge. Plan §G.4 lines 1573+.

Forward-binding lessons from T2.SB1 chain to inform T2.SB3 detector design (banked at phase3e-todo.md "Phase 13 T2.SB1 SHIPPED" §"9 forward-binding lessons"):
- **Cup-with-handle rounded-vs-V hard gate** caused 4 of 5 cup dispatches at T-A.1.7 to fail by sub-1% margins. T2.SB3 cup_with_handle detector SHOULD widen the gate OR downgrade to scoring penalty.
- **VCP monotonic-tightening hard gate** — consider 1-violation tolerance.
- **HTF consolidation tightness** — widen for high-magnitude-pole cases (T2.SB4 territory, not T2.SB3).
- **Precursor 3-dip "early identifier" pattern** — banked per operator's TSM/TGT/SNAP chart references. Labeling-window-vs-setup-quality separation as detector-spec contract.

---

*End of dispatch brief. T2.SB2 (6 tasks) + T-PT9 (1 task) batched per operator direction 2026-05-20. ~7 tasks total; foundation primitives ship pure-logic substrate for T2.SB3 + T2.SB4 detectors; T-PT9 closes 2 pre-existing Phase-9 calendar-drift failures with recon-first discipline + calendar-drift-proof regression test. 17th cumulative C.C lesson #6 validation expected. ZERO Co-Authored-By footer drift streak (~239+ commits) preserved.*
