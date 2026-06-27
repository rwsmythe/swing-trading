# Phase 3e — Chart-Pattern Flag-V1: Phase 6 Execution Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Execute **Phase 6 ONLY** (Tasks 6.1 + 6.2) of the chart-pattern flag-v1 implementation plan via `copowers:executing-plans`. Light up the actual chart-overlay painting that Phase 3 stubbed: `fill_betweenx` pole/flag colored bands + algo-pivot horizontal segment spanning flag region + title annotation showing classification label. Replace Phase 3's load-bearing byte-identity tests with overlay-rendered equivalence tests. Stop at the Phase 6 checkpoint — do NOT proceed to Phase 7 or beyond.
**Expected duration:** ~1 session (~2 tasks).
**Output:** Phase 6 commits landed on `main`; fast suite green; chart-image-overlay rendering active for tickers with detected flag patterns; existing candidate-pivot hline preserved as a separate visual element; adversarial Codex review on the combined Phase 6 diff reaches `NO_NEW_CRITICAL_MAJOR`.

**This is the LAST "build" phase.** After Phase 6 ships, only Phase 7 (operator-labeled fixtures + integration tests + tuning) remains. Phase 7's main work is operator-only (labeling); the implementer side is the fixture-loader + parametrized test runner.

---

## §0 Read first

In this order:

1. **`docs/superpowers/plans/2026-04-26-chart-pattern-flag-v1-plan.md`** — THE plan. Phase 6 is at lines 3938-4176 (Tasks 6.1 + 6.2). Read Phase 6 in full; skim Phases 3 + 5 (lines 1901-2363, 3118-3937) for the `pattern_overlay` kwarg context that Phase 6 lights up; do NOT execute Phase 7.
2. **`docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`** — the source-of-truth design. Phase 6 implements spec §3.4 (chart overlay) verbatim. **Spec language fidelity matters:** spec specifies `fill_betweenx` for the band painting; use that API name verbatim, not `axvspan` (per 2026-04-26 lesson on spec-fidelity).
3. **`docs/orchestrator-context.md`** — project framing, recent decisions (especially the 2026-04-26 Phase 5 triage decisions: 2-phase ZERO-rogue track record; subject-only grep refinement; 3-tier commit-message convention), most-recent lessons captured (especially internal-code-review-BEFORE-Codex pattern; Codex's contextual advantage at cross-feature interactions; spec-language-fidelity matters).
4. **`CLAUDE.md`** at repo root — gotchas, conventions. Phase 6 touches `swing/rendering/charts.py` (light up the overlay) AND `tests/rendering/` (byte-identity tests need updating/replacing). Especially relevant: matplotlib + mplfinance API patterns; `mpf.plot(..., returnfig=True)` for axes manipulation post-render; pandas `pd.Timestamp` conversion for date axis values.
5. **`docs/phase3e-todo.md`** — particularly the "2026-04-26 chart-pattern flag-v1 Phase 5 → Phase 6 handoff items" section at the bottom. Calls out the byte-identity test replacement explicitly.
6. **`docs/phase3e-chart-pattern-phase5-execution-brief.md`** (briefly) — context for the Phase 5 dispatch discipline that Phase 6 inherits.

---

## §0 Skill posture

**INVOKE:**

- `copowers:executing-plans` — wraps `superpowers:subagent-driven-development` with adversarial Codex review on the combined Phase 6 diff after task commits land. Iterates rounds to `NO_NEW_CRITICAL_MAJOR`.

**DO NOT INVOKE:**

- `copowers:writing-plans` / `superpowers:writing-plans` — plan is settled.
- `copowers:brainstorming` / `superpowers:brainstorming` — design is settled.
- `superpowers:executing-plans` directly — use the copowers wrapper for adversarial review per project standing convention.
- `superpowers:using-git-worktrees` — explicitly NOT required for Phase 6 (operator decisions through 2026-04-26 post-Phase-5: 2-phase ZERO-rogue track record vindicates single-subagent + observable-verification approach; worktree isolation reserved as fallback for novel failure modes).

The execution wrapper drives task-by-task implementation per the plan's TDD discipline, then runs Codex review on the cumulative Phase 6 diff. Fix findings as new commits (no amending).

**RECOMMENDED INTERNAL FLOW (per 2026-04-26 lesson):** After tasks 6.1 + 6.2 land but BEFORE invoking copowers wrapper's Codex round, do a self-driven internal code-review pass against the spec + plan. Catches plan-anticipated misses (Phase 5's I1 ValueError catch was caught this way); saves Codex round budget; tightens the cumulative arc.

---

## §1 Scope (Phase 6 ONLY)

**EXECUTE these tasks (in plan order):**

- **Task 6.1** — Paint pole + flag bands via `fill_betweenx` + algo-pivot horizontal segment spanning flag region only + title annotation `| flag (0.78)`. Light up the `pattern_overlay: PatternOverlay | None = None` kwarg added by Phase 3 (currently a no-op stub via `del pattern_overlay`).
- **Task 6.2** — Phase 6 checkpoint (validation; fast suite green; ruff clean; manual verification of overlay rendering on a real classification + chart).

**DO NOT EXECUTE (out of scope; STOP here):**

- Phase 7 (operator-labeled fixtures + integration tests + parametrized test runner + FP-biased tuning)
- ANY modification to `swing/data/`, `swing/web/`, `swing/trades/`, `swing/cli.py`, `swing/pipeline/`, `swing/evaluation/`
- ANY new pattern beyond `flag_pattern` (V1 = single pattern only; V2+ extensions via separate dispatch)
- ANY modification to `_step_charts` pipeline integration (Phase 3 territory; Phase 6 only changes the rendering layer)

If Phase 6 reveals a problem that requires touching out-of-scope code, STOP and surface to orchestrator under "OPEN QUESTIONS" in the return report.

**In-scope-by-extension (per scope-deviation acceptance pattern, 2026-04-26):** **The Phase 3 byte-identity tests in `tests/rendering/` ARE expected to fail when Phase 6 lands and need to be updated or replaced.** Specifically: `test_render_chart_pattern_overlay_none_is_byte_identical_to_default` and `test_render_chart_real_pattern_overlay_is_byte_identical_to_default` were load-bearing for Phase 3's no-op contract; Phase 6 lights up the actual painting. Replace with overlay-rendered equivalence tests (e.g., assert LineCollection count delta from baseline; assert pole/flag band fill_betweenx presence; assert title annotation contains classification label). Brief explicitly authorizes this work as in-scope.

---

## §2 Locked constraints + Phase 1-5 handoff items

The spec's six locked constraints (spec §1.1) and the plan's settled design decisions are binding. Phase 6 in particular must respect:

### Chart overlay rendering (binding spec §3.4)

- **`fill_betweenx` for pole + flag bands.** Spec specifies this API name verbatim. Use `mpf.plot(..., returnfig=True)` to obtain `fig, axes`; then on the price axes, call `axes[0].fill_betweenx(...)` for the pole band (typically pole_start_date to pole_end_date, low to high) and another `fill_betweenx(...)` for the flag band (flag_start_date to flag_end_date, low to high). Faint colors (alpha < 0.3 typical for non-distracting overlay).
- **Algo-pivot horizontal segment.** A horizontal line segment at `pivot` price level spanning ONLY the flag region (flag_start_date to flag_end_date) — NOT the entire chart width. Use `axes[0].hlines(...)` or `axes[0].plot(...)` with x-bounds. Distinct from the existing candidate-pivot hline (see below).
- **Title annotation.** Append `| flag (0.78)` (or whatever format the spec specifies; verify against §3.4) to the existing chart title. Format: `<existing title> | flag (<confidence:.2f>)`.
- **Existing candidate-pivot hline preserved.** The existing `pivot` hline (full-chart-width horizontal line at the candidate's pivot price, used by all chart-scope candidates regardless of pattern detection) MUST NOT be removed. The algo-pivot is a SEPARATE visual element (flag-region-spanning, not full-width); two semantically-different "pivots" that happen to coincide visually only when they share a price level.
- **`PatternOverlay.from_classification(r)` filtering rule already in place** (Phase 3): returns None when `not r.detected or r.pattern != 'flag'`. Phase 6 doesn't change this. Overlay painting only fires when `pattern_overlay is not None`.
- **Phase 5 Task 5.0a aligned dataclass annotations.** Phase 6 painting can `isinstance(cls.pole_start_date, date)` and `pd.Timestamp(cls.pole_start_date)` directly. Date-axis conversion is straightforward.

### Phase 3 byte-identity tests — REPLACEMENT required

- `test_render_chart_pattern_overlay_none_is_byte_identical_to_default` — kept (still asserts that `pattern_overlay=None` produces byte-identical output to default; Phase 6's painting only fires when overlay IS present, so the None case stays byte-identical).
- `test_render_chart_real_pattern_overlay_is_byte_identical_to_default` — REPLACED with an inverted version: `test_render_chart_real_pattern_overlay_is_NOT_byte_identical_to_default` (or equivalent) asserting the byte hashes DIFFER when an overlay is provided. Discriminating-test discipline (per `feedback_regression_test_arithmetic` memory): the test must produce different outcomes pre-Phase-6 (no painting; bytes identical) vs post-Phase-6 (painting; bytes different).
- ADD: Phase 6 introduces overlay-rendered equivalence tests. Suggested:
  - Assert `LineCollection` count delta from baseline (overlay adds ≥2 fill_betweenx polygons + 1 algo-pivot segment).
  - Assert title annotation contains classification label (exact-substring or exact-equality; per 2026-04-26 lesson, prefer exact-equality).
  - Assert pole band x-bounds (start_date to end_date) match `cls.pole_start_date` to `cls.pole_end_date`.
  - Assert flag band x-bounds match `cls.flag_start_date` to `cls.flag_end_date`.
  - Assert algo-pivot y-coord matches `cls.pivot`.

### Bug-7-family anchor discipline

- Phase 6 doesn't read classifications from the cache directly; it consumes `PatternOverlay` instances passed via the `pattern_overlay` kwarg from `_step_charts` (which already binds correctly via Phase 3's `PatternOverlay.from_classification(r)`). No new reads to police.

### Phase 1-5 handoff items

- **Pure-function discipline verified for Phase 1.** `classify_flag(bars)` does NOT mutate input.
- **Repo-layer cross-column invariant** on `trades` (4 cases) enforced from Phase 2.
- **`PipelinePatternClassification` dataclass annotations aligned** (Phase 5 Task 5.0a): `pole_start_date: date | None` etc. Phase 6 can rely on `date` methods.
- **Per spec §3.3, classifier-error rows have `pattern=NULL`.** `PatternOverlay.from_classification(r)` returns None for these (per Phase 3 implementation); Phase 6 doesn't paint overlays for classifier-error rows. No painting fires for non-detected or error cases.

If anything in Phase 6 conflicts with the spec or the locked constraints, STOP and surface to orchestrator. Do NOT redesign.

---

## §3 Subagent task partitioning + observable verification (BINDING — operator decisions through 2026-04-26)

**Background.** Phase 4 + Phase 5 both produced ZERO rogue duplicate task commits with single-subagent dispatch + subject-only-grep observable verification. Worktree isolation NOT escalated.

### Required partitioning rules

1. **Each task assigned to exactly one subagent.** Phase 6 has only 2 tasks (6.1 + 6.2); single-subagent sequential is the natural partitioning.
2. **Pre-task verification.** Before starting any task's implementation, the assigned subagent MUST verify the task's deliverable does NOT already exist (grep for the function/method/import; read the relevant file). Abort + report if it does.
3. **Sequential dependencies.** Task 6.1 (overlay painting) must land before Task 6.2 (checkpoint). Single subagent.
4. **Commit-message conventions** (formalized 2026-04-26):
   - **Task implementation commits** MUST include task ID: `feat(rendering): Task 6.1 — fill_betweenx pole/flag bands + algo-pivot + title annotation`.
   - **Adversarial review-fix commits** SHOULD include round + finding ID: `fix(rendering): Codex R1 Major 1 — <description>`.
   - **Internal code-review fix commits** use `fix(rendering): code-review <ID> — <description>` per Phase 5 precedent.
   - **Format-only cleanup commits** no task ID needed.
5. **Subject-only grep observable verification** (refined 2026-04-26): subagent MUST include `git log --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'` output in commit body BEFORE each task implementation commit. If grep returns ANY existing commits, abort.

### Watch items for adversarial review

- **Duplicate task implementations.**
- **Missing pre-task verification evidence in commit body.**
- **Mixed-task commits.**
- **Scratch directory pollution.** Use `pytest --basetemp=.tmp-phase6/` (add to `.gitignore`). Document any Windows-ACL-blocked dirs.
- **Phase 3 byte-identity test handling.** Tests must be UPDATED or REPLACED, not just deleted. The replacement tests must be discriminating (assert overlay produces different bytes vs no-overlay; assert specific overlay elements present).
- **Existing candidate-pivot hline NOT REMOVED.** Spec is explicit: algo-pivot is a SEPARATE visual element; existing pivot hline stays.

---

## §4 Conventions

- **Branch:** `main`. No feature branches.
- **TDD discipline (rigid):** failing test → run to see RED → minimal implementation → run to see GREEN → commit. One red-green cycle per logical change. Phase 6's painting work is amenable to per-element TDD (test for fill_betweenx pole band; test for fill_betweenx flag band; test for algo-pivot segment; test for title annotation; each as separate red-green cycle).
- **Internal code-review pass BEFORE Codex** (per Phase 5 lesson 2026-04-26). After tasks 6.1 + 6.2 land, do a self-driven internal review pass against spec §3.4 and the plan. Look for plan-anticipated edge cases (e.g., what happens when `pattern_overlay.pivot is None`? what if dates are NaT? what if mpf.plot returns axes in unexpected order?). Catches misses pre-Codex; saves a round.
- **Commit-message conventions** (per §3 rule 4 above).
- **Discriminating-test discipline:** every test must produce a different outcome under post-fix code than under pre-fix code (per `feedback_regression_test_arithmetic` memory and the 2026-04-26 lesson extensions). Especially relevant for the byte-identity test replacement: pre-Phase-6 produces identical bytes; post-Phase-6 produces different bytes. The replacement test must distinguish.
- **Exact-equality for format assertions.** Per 2026-04-26 lesson: title-annotation assertions use exact-equality, NOT substring matching, when the intent is format verification.
- **Tests:** `python -m pytest -m "not slow" -q` MUST be green at the Phase 6 checkpoint. Baseline at start of Phase 6: 1124 fast tests.
- **Ruff:** baseline 81 errors per CLAUDE.md. Phase 6 must NOT introduce new violations in `swing/rendering/`. Run `ruff check swing/rendering/` after Task 6.1 and before Task 6.2 commit.
- **Phase 6 scope boundary:** every modified file MUST be in `swing/rendering/` OR `tests/rendering/`. If you find yourself touching `swing/data/`, `swing/web/`, `swing/trades/`, `swing/cli.py`, `swing/pipeline/`, OR `swing/evaluation/`, STOP — it's out of scope.
- **Scratch directory hygiene.** Use `pytest --basetemp=.tmp-phase6/` (add to `.gitignore` first; brief §5 hygiene corollary). Clean up after the task's test cycle.
- **Manual visual verification.** Phase 6 is the only phase where the rendered output IS the artifact. Manual verification: render a chart with a real classification + real OHLCV, inspect the PNG for visual correctness (band placement, pivot level, title annotation). Save the verification screenshot/output to the return report.

---

## §5 Adversarial review (handled by copowers wrapper)

The `copowers:executing-plans` wrapper invokes Codex MCP review on the combined Phase 6 diff after Task 6.2 lands. Pass these specific watch items:

- **Spec fidelity.** Phase 6 implements spec §3.4 verbatim — `fill_betweenx` for bands (NOT `axvspan` or alternatives); algo-pivot segment spans flag region only (NOT full chart width); title annotation appends classification label.
- **Plan fidelity.** Tasks executed in plan order; no skipped tasks; no tasks added beyond the plan; commit messages follow §3 rule 4 conventions.
- **Existing candidate-pivot hline preservation.** Test verifies the existing `pivot` hline is still present in the rendered output; Phase 6's algo-pivot is a SEPARATE element, not a replacement.
- **Phase 3 byte-identity test replacement correctness.** The replaced tests must be discriminating: pre-Phase-6 produces identical bytes (overlay was no-op); post-Phase-6 produces different bytes (overlay paints). New equivalence tests assert specific overlay elements (LineCollection count delta; title annotation; band x-bounds; algo-pivot y-coord).
- **Edge cases.** What happens when:
  - `pattern_overlay is None`? → no painting, byte-identical to default.
  - `pattern_overlay.pivot is None` (shouldn't happen since `from_classification` only fires when `pattern == 'flag'` AND pivot is set, but defensive)?
  - `pole_start_date == flag_start_date` (impossible per gate definitions but worth testing)?
  - The DataFrame's date axis doesn't include `pole_start_date` (out-of-window classification)?
  - Confidence is exactly 0.0 or 1.0 (boundary formatting)?
- **Discriminating tests.** Per `feedback_regression_test_arithmetic`: every test produces different outcomes pre-fix vs post-fix. Vacuous tests are findings.
- **Compounding-confound.** For the band-presence assertion: if you delete the `fill_betweenx` call, the test must fail (per 2026-04-26 lesson).
- **Observable verification (per §3 rule 5).** Each task implementation commit body contains the subject-only grep output. Absence is a finding.
- **Spec-language fidelity** (per 2026-04-26 lesson): use `fill_betweenx` not `axvspan` even if alternatives are equivalent.
- **Out-of-scope creep.** No modification to `swing/data/`, `swing/web/`, `swing/trades/`, `swing/cli.py`, `swing/pipeline/`, OR `swing/evaluation/`.

---

## §6 Done criteria

Phase 6 execution is done when ALL of the following hold:

- [ ] Tasks 6.1 + 6.2 have landed commits on `main`.
- [ ] Each task implementation commit message follows §3 rule 4 conventions; commit body contains §3 rule 5 observable verification evidence.
- [ ] No duplicate task implementations; no mixed-task commits.
- [ ] `python -m pytest -m "not slow" -q` green (full fast suite); baseline + new/replacement tests on overlay rendering.
- [ ] `ruff check swing/rendering/` clean (no new violations).
- [ ] Phase 3 byte-identity test for `pattern_overlay=None` PRESERVED (still passes; no-painting case still byte-identical).
- [ ] Phase 3 byte-identity test for non-None overlay REPLACED with inverted/equivalence tests.
- [ ] Existing candidate-pivot hline rendering UNCHANGED (verified by test).
- [ ] Manual visual verification: render a chart with a real classification + real OHLCV; inspect rendered PNG for visual correctness; include in return report (description or attachment).
- [ ] No scratch pytest directories left in repo root (only pre-existing ACL-blocked dirs; document in return report).
- [ ] Adversarial Codex review on combined Phase 6 diff reaches `NO_NEW_CRITICAL_MAJOR`.
- [ ] Phase 6 implementation does NOT touch `swing/data/`, `swing/web/`, `swing/trades/`, `swing/cli.py`, `swing/pipeline/`, OR `swing/evaluation/`.

---

## §7 Return report format

Final message to orchestrator (via operator) MUST include:

```
PHASE: 6 (Chart overlay painting) of chart-pattern flag-v1 plan
COMMIT CHAIN: <first SHA>..<last SHA> (N commits)
FAST SUITE: 1124 → <new count> tests (Δ +<count>)
ADVERSARIAL ROUNDS: <N>; FINAL VERDICT: NO_NEW_CRITICAL_MAJOR

TASKS COMPLETED:
- Task 6.1 — Paint pole + flag bands + algo-pivot + title annotation, commit SHA
- Task 6.2 — Phase 6 checkpoint, commit SHA

INTERNAL CODE-REVIEW PASS:
- Did internal review fire? <yes/no>
- Findings caught pre-Codex: <list>
- Round budget saved: <count>

PARTITIONING DISCIPLINE OUTCOME:
- Subagent count: <N>
- Task assignments: <list>
- Collisions detected: <none / list>
- Pre-task deliverable-existence checks: <fired count; aborts>
- Observable verification (subject-only grep): <count of task commits with grep block; sample>
- Scratch directories: <cleaned / list any remaining + ACL state>

OVERLAY RENDERING SUMMARY:
- fill_betweenx pole band: <colors, alpha, x-bounds source>
- fill_betweenx flag band: <colors, alpha, x-bounds source>
- algo-pivot horizontal segment: <x-bounds, y-coord source>
- Title annotation: <format string used>
- Existing candidate-pivot hline: <preserved; verified by test>
- Manual visual verification: <description; attach screenshot or describe rendered output>

PHASE 3 BYTE-IDENTITY TESTS HANDLING:
- test_render_chart_pattern_overlay_none_is_byte_identical_to_default: <preserved/updated>
- test_render_chart_real_pattern_overlay_is_byte_identical_to_default: <inverted/replaced>
- New overlay-rendered equivalence tests: <list>

ADVERSARIAL FINDINGS (each with disposition):
- <finding>: FIXED in commit <SHA> / ACCEPTED with rationale: <text>

OPEN QUESTIONS FOR ORCHESTRATOR:
- <any plan/spec contradiction surfaced; otherwise "None">

LESSONS WORTH CAPTURING (process insights from execution):
- <bullet list>

PHASE 6 → PHASE 7 HANDOFF NOTES:
- Phase 6 is the LAST build phase. Phase 7 is operator-labeled fixtures + integration tests + tuning.
- <anything Phase 7 implementer needs to know that isn't in the plan>
- <anything operator needs to know about labeling work that emerged from Phase 6>
```

---

## §8 If you get stuck

- **Plan/spec contradictions.** Surface in return report under "OPEN QUESTIONS." Do NOT amend the plan or spec; do NOT re-design.
- **TDD ordering uncertainty.** Failing-test-first. Phase 6's painting work is amenable to per-element TDD (one element per red-green cycle).
- **Codex finding contradicts plan.** Apply receiving-code-review discipline. If finding correct AND plan wrong, surface to orchestrator. If finding wrong, document why with rationale.
- **Out-of-scope pull.** If a Phase 6 task seems to require touching out-of-scope code (Phase 7 territory or non-rendering code), STOP. Surface as "OPEN QUESTIONS." Do NOT silently expand scope. Test file replacements in `tests/rendering/` ARE in-scope by extension.
- **Subagent collision detected mid-execution.** STOP, surface to orchestrator immediately. Document the collision details. Per §3: if Phase 6 collides despite the partitioning + observable verification, the orchestrator will escalate to worktree isolation in Phase 7+.
- **mpf.plot axes structure.** `mpf.plot(..., returnfig=True)` returns `(fig, axes)` where `axes` is typically a list with the price axis at index 0 and (sometimes) a volume axis at index 1. Verify the structure with the actual mpf version in use; consult `swing/rendering/charts.py` for the existing pattern.
- **Date-axis x-coordinates.** mpf typically uses pandas DatetimeIndex on the x-axis. To plot at specific dates, use `pd.Timestamp(date_obj)` to convert; `fill_betweenx` accepts the date values directly (matplotlib auto-converts via the date locator).
- **Visual verification is required.** Phase 6 is the only phase where rendered output IS the artifact. Don't ship without manually verifying the overlay renders correctly on a real classification. Attach a screenshot or detailed visual description to the return report.

---

## §9 Anti-patterns specific to this execution

- **Removing the existing candidate-pivot hline.** Spec is explicit: algo-pivot is a SEPARATE visual element. Two semantically-different "pivots." Existing candidate-pivot hline stays.
- **Using `axvspan` instead of `fill_betweenx`.** Spec specifies `fill_betweenx` verbatim. Per 2026-04-26 spec-language-fidelity lesson: use the spec's API name even if alternatives are equivalent. Adversarial review will flag the deviation.
- **Algo-pivot spanning full chart width.** Spec explicitly says algo-pivot spans the flag region ONLY (flag_start_date to flag_end_date). Don't make it full-width.
- **Painting overlays for non-flag classifications.** `PatternOverlay.from_classification(r)` returns None when `r.pattern != 'flag'`. Phase 6 painting only fires when overlay IS NOT None. Don't add fallback painting for `pattern == 'none'` or classifier-error rows.
- **Skipping the manual visual verification.** This is the only phase where rendered output IS the artifact. Tests verify structural correctness (LineCollection count, x-bounds, y-coord) but NOT visual correctness (do the bands look reasonable? is the title legible? do alpha values create distraction?). Manual verification is required.
- **Skipping internal code-review pass BEFORE Codex.** Per Phase 5 lesson: internal review pre-empts plan-anticipated misses; saves Codex round budget.
- **Mixed-task commits** (Tasks 6.1 + 6.2 in one commit). Phase 6 has only 2 tasks; they must commit separately per partitioning discipline.
- **Vacuous test replacements.** The replacement byte-identity tests must DISCRIMINATE: pre-Phase-6 (no painting; bytes identical) vs post-Phase-6 (painting; bytes different). Tests asserting overlay element presence must FAIL if the corresponding paint call is removed (compounding-confound check).
- **Not updating `.gitignore` for `.tmp-phase6/`.** Per brief §5 hygiene corollary; must be explicitly added.
- **Substring-match assertions for the title annotation.** Per 2026-04-26 lesson: format assertions use exact-equality. Use `assert title == "<exact expected>"` not `assert "flag" in title`.
