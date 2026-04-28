# Chart-Pattern Flag-V1 Mathtext Title Fix — Implementer Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Apply Tier-1 fix #1 from the 2026-04-27 manual verification round 1 — the mathtext title regression. The chart title format string `{ticker} | pivot ${pivot:.2f} stop ${stop:.2f} | last {len(df)} bars` triggers matplotlib mathtext interpretation despite the `\$` escape introduced in commit `2fd0ecc`. Rendered title shows "stop" italicized, `$` glyphs consumed, and spaces collapsed (e.g., `pivot 72.97stop40.69` instead of `pivot $72.97 stop $40.69`). Apply fix option (a): **drop `$` entirely from the title format**, update test assertions, update operator-facing manual-verification doc title examples, and **manually visually verify the rendered PNG before claiming completion**. The Phase 6 lesson "Manual visual verification is not optional for rendering work" applies — string-equality tests verify structure, not visual correctness; that's exactly how the original `2fd0ecc` regression slipped through.

**Expected duration:** 30-60 minutes.

---

## §0 Read first

1. `docs/chart-pattern-flag-v1-manual-verification-results.md` §"#1 — Mathtext title fix regression" (lines 42-61). The full technical detail of the failure mode + recommended fix.
2. `docs/orchestrator-context.md` §"Lessons captured" — find the entries on "Manual visual verification is not optional for rendering work" (Phase 6 lesson) and "Manual visual verification IS load-bearing — string-equality tests are not enough for rendered output" (2026-04-27 reinforcement). These are the lessons this brief enforces.
3. `docs/orchestrator-context.md` §"Binding conventions (project-wide)" — commit-message convention (4-tier), subject-only ERE grep observable verification, no-amend / no-`--no-verify` rules.
4. `swing/rendering/charts.py:75-100` — the production code surface being fixed.
5. `tests/rendering/test_chart_overlay.py:260-300` — the test surface being updated.

Do NOT read the chart-pattern flag-v1 design spec or implementation plan — both reference the *historical* title format (with `$`) and are out-of-scope to update (point-in-time records).

---

## §0.1 Skill posture

- Standard `superpowers:using-superpowers` skill at session start.
- `superpowers:test-driven-development` — single red-green-commit cycle for the code change. Tests already exist (lines 270, 287); they need to be UPDATED to match the new title format. After the update, run them RED against the unfixed `charts.py`, then GREEN after applying the production fix.
- `superpowers:verification-before-completion` — MANDATORY before final return report.
- `copowers:adversarial-critic` — invoke once on the combined diff after the fix commit lands. Iterate to `NO_NEW_CRITICAL_MAJOR`. Use the `(internal)` qualifier on any review-fix commits per the 4-tier convention.
- DO NOT invoke `superpowers:writing-plans` or `superpowers:executing-plans` — single-task scope; the brief IS the plan.
- DO NOT dispatch sub-subagents. Single-implementer dispatch.

---

## §1 Strategic context

The chart-pattern flag-v1 V1 build (Phases 1-7 implementer-side) is complete. Operator + orchestrator walked the manual verification procedure on 2026-04-27 and confirmed the title rendering bug: the `\$` escape introduced in commit `2fd0ecc` does NOT prevent matplotlib's mathtext interpreter from firing.

Why `\$` doesn't work: matplotlib renders `\$` as a literal `$` glyph BEFORE math-mode parsing. The string `pivot \$110.00 stop \$95.00` first becomes `pivot $110.00 stop $95.00`; THEN the parser sees paired `$..$` and enters math mode for the substring between them — italicizing "stop", consuming both `$` glyphs, and collapsing the surrounding whitespace.

The fix surfaced two options:
- **(a) Remove `$` entirely from the title format string** (simplest, one-line change).
- **(b) Use `fig.suptitle(..., parse_math=False)`** after `mpf.plot(returnfig=True)`.

Operator selected **option (a)** for simplicity. Trading context already implies dollar values; the labels "pivot" and "stop" carry the semantic meaning.

This fix is being dispatched ahead of Task 7.3 (operator-labeled fixture work) so that chart titles render legibly during the labeling workflow.

---

## §2 Scope

### In scope

| Surface | Change |
|---|---|
| `swing/rendering/charts.py:86-90` | Drop `$` from title format string; update inline comment-rationale block to reflect the new approach. |
| `tests/rendering/test_chart_overlay.py:270` | Update `expected` to new title format. |
| `tests/rendering/test_chart_overlay.py:287` | Update `baseline_title` to new title format. |
| `docs/chart-pattern-flag-v1-manual-verification.md:120, 135` | Update two example title strings to reflect new format. |
| Manual visual verification | Render real PNGs (non-overlay + overlay paths), confirm titles render correctly. |

### Out of scope

- Spec / plan historical records: `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md:439`, `docs/superpowers/plans/2026-04-26-chart-pattern-flag-v1-plan.md:4158`, `docs/superpowers/plans/2026-04-17-phase2-pipeline-trades.md:4403`. These are point-in-time records of design-state / plan-state and are NOT retroactively edited.
- Other Tier-4 verification-doc fixes (#7-#14 in the manual-verification-results doc) — separate dispatch / direct orchestrator edit.
- Tier-2 chart-view UX (#2 standalone chart route, #3 open-positions expand, #4 chart-scope alignment) — separate dispatches.
- Tier-3 design discussions (#5 lightning icon, #6 advisory state-machine) — operator-led, no dispatch.
- Any other production code touching chart titles. (Verified at brief-drafting time: only `swing/rendering/charts.py` constructs the chart title; no parallel surfaces.)

---

## §3 Binding conventions

- **Branch:** `main`. Commit conventionally; no Claude co-author footer; no `--no-verify`; no amending.
- **Commit-message convention** (per orchestrator-context Binding conventions, 4-tier):
  - **Production fix commit:** `fix(rendering): mathtext title regression — drop $ from chart title format` (no Task X.Y prefix; this is a fix, not a phase task — precedent: `2fd0ecc` itself).
  - **Test-assertion update commit:** can be bundled with the production fix or split. Suggested bundled: single commit covering production + tests + doc.
  - **Adversarial review-fix commits:** `fix(rendering): Codex R1 Major N — <description>` (no `(internal)` qualifier — this brief explicitly does NOT use within-task internal-Codex rounds; the Codex round is orchestrator-wrapper-equivalent invoked once at end).
  - **Subject-only ERE grep observable verification** is not load-bearing here (single-task; no cross-task duplication risk), but if you do choose to verify, use `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): mathtext'`.
- **TDD discipline:** Update test assertions FIRST (will go RED against unfixed production code). Then apply production fix. Then run tests GREEN. Commit. The "red phase" is the load-bearing demonstration that the test discriminates pre-fix vs post-fix; SHOW the red output in your return report.
- **Fast suite must stay green:** `python -m pytest -m "not slow" -q`. Baseline as of HEAD `05528a0`: **1145 fast tests passing**. Post-fix: 1145 (no test count change).
- **Ruff baseline 81 errors;** do not introduce new violations.
- **DB location invariant:** `%USERPROFILE%/swing-data/swing.db` — outside Drive-synced folders. Not relevant to this brief but project-wide.

---

## §4 Per-task specifications

### §4.1 — Update test assertions FIRST (red phase)

**Files:** `tests/rendering/test_chart_overlay.py:270, 287`.

Change line 270:
```python
# Before:
expected = r"AAPL | pivot \$110.00 stop \$95.00 | last 120 bars | flag (0.78)"
# After:
expected = "AAPL | pivot 110.00 stop 95.00 | last 120 bars | flag (0.78)"
```

Change line 287:
```python
# Before:
baseline_title = r"AAPL | pivot \$110.00 stop \$95.00 | last 120 bars"
# After:
baseline_title = "AAPL | pivot 110.00 stop 95.00 | last 120 bars"
```

(Drop the `r` prefix since the strings no longer contain backslash escapes.)

**Verify red:** Run `python -m pytest tests/rendering/test_chart_overlay.py -v`. The two tests asserting on these strings MUST fail with `AssertionError`. Capture the failure output for your return report — this is the discriminating-test evidence that the assertions actually changed behavior.

### §4.2 — Apply production fix

**File:** `swing/rendering/charts.py:86-90`.

Replace the existing block:

```python
    # Escape `$` with `\$` to prevent matplotlib mathtext interpretation
    # (paired `$..$` would render the intervening text in italic math mode,
    # e.g. "stop" between the two prices). matplotlib renders `\$` as a
    # literal `$` glyph without entering math mode.
    title = rf"{ticker} | pivot \${pivot:.2f} stop \${stop:.2f} | last {len(df)} bars"
```

With:

```python
    # Omit `$` from the title because matplotlib's mathtext interpreter
    # treats paired `$..$` as math mode, italicizing intervening text and
    # consuming the `$` glyphs. The `\$` escape (commit `2fd0ecc`) does
    # NOT prevent math-mode entry — matplotlib resolves `\$` to a literal
    # `$` BEFORE the math-mode parse pass. Trading context implies the
    # values are dollars; the labels "pivot" / "stop" carry the meaning.
    title = f"{ticker} | pivot {pivot:.2f} stop {stop:.2f} | last {len(df)} bars"
```

The overlay-path append at line 92 (`title += f" | flag ({pattern_overlay.confidence:.2f})"`) is unchanged — it has no `$` glyphs.

**Verify green:** Re-run `python -m pytest tests/rendering/test_chart_overlay.py -v`. All tests pass.

**Verify whole fast suite green:** `python -m pytest -m "not slow" -q`. Expect 1145 passed.

### §4.3 — Update operator-facing manual-verification doc

**File:** `docs/chart-pattern-flag-v1-manual-verification.md`.

Line 120: `AAPL | pivot $110.00 stop $95.00 | last 120 bars | flag (0.78)` → `AAPL | pivot 110.00 stop 95.00 | last 120 bars | flag (0.78)`.

Line 135: `AAPL | pivot $110.00 stop $95.00 | last 120 bars` → `AAPL | pivot 110.00 stop 95.00 | last 120 bars`.

(Search for the literal strings; do not edit by line number alone — the file may have shifted.)

### §4.4 — Manual visual verification (BLOCKING)

**This is the load-bearing step. Do NOT skip. Do NOT short-circuit.**

The Phase 6 lesson + the 2026-04-27 mathtext regression demonstrate: string-equality assertions verify structural correctness (the test passes when the *string* matches), but matplotlib renders the string through the mathtext interpreter — the visual output can still be wrong even when the string is exactly the post-fix value. The `2fd0ecc` regression slipped through because string-equality tests passed against `r"... pivot \$110.00 ..."` while the rendered PNG still had italicized "stop" + consumed `$` + collapsed spaces.

**Procedure:**

1. Render two PNGs to `.tmp-mathtext-fix-verify/` (the dir is gitignored — safe to write to):
   - **Non-overlay path** (most common case; matches the AMKR / DHC bug report).
   - **Overlay path** (with a `PatternOverlay` object passed in; covers the `| flag ({confidence:.2f})` suffix).

2. Open each PNG (use `Read` with the .png path — Claude Code displays images visually).

3. Confirm visually for BOTH PNGs:
   - Title shows `{ticker} | pivot {value} stop {value} | last {N} bars` with normal spacing between every word and number.
   - **"stop" is NOT italicized.** (Italic = mathtext is still firing — fix failed.)
   - **No `$` glyphs in the title.** (If present, the fix wasn't applied to all paths.)
   - For the overlay PNG additionally: title appends `| flag (0.XX)` suffix; no italics on "flag" or any other word.

4. **Reproduction script** (adapt as needed; the `PatternOverlay` dataclass signature lives in `swing/rendering/charts.py` — grep for `class PatternOverlay`):

```python
import pandas as pd
import numpy as np
from pathlib import Path
from swing.rendering.charts import render_chart, PatternOverlay

np.random.seed(42)
dates = pd.bdate_range("2025-01-01", periods=120)
close = 100 + np.cumsum(np.random.randn(120) * 0.5)
df = pd.DataFrame({
    "Open": close * 0.99, "High": close * 1.01,
    "Low": close * 0.98, "Close": close,
    "Volume": np.random.randint(1_000_000, 5_000_000, 120),
}, index=dates)

out_dir = Path(".tmp-mathtext-fix-verify")
out_dir.mkdir(exist_ok=True)

# Non-overlay
render_chart("AAPL", df, pivot=110.0, stop=95.0,
             output_path=out_dir / "noverlay_after_fix.png")

# Overlay (adjust constructor args to match the actual PatternOverlay signature)
overlay = PatternOverlay(...)
render_chart("AAPL", df, pivot=110.0, stop=95.0,
             output_path=out_dir / "overlay_after_fix.png",
             pattern_overlay=overlay)
```

5. **Include both PNG paths in your return report**, plus a sentence-each visual confirmation per the four checks above.

**Acceptance:** both PNGs render without error; visual checks pass for both; PNG paths in return report; operator can open them post-dispatch to independently confirm.

### §4.5 — Adversarial Codex round

After §4.1-4.3 have committed (single bundled commit acceptable; or split as you prefer per TDD discipline), invoke `copowers:adversarial-critic` on the diff between HEAD and `05528a0` (HEAD at brief-drafting time).

**Watch items to specifically pass to the critic:**

- Does the production fix prevent math-mode entry on ALL paths (overlay + non-overlay)? Are there any path that still constructs a title with `$` glyphs?
- Are there other tests asserting on title format that this brief missed? Implementer should grep for `\$110.00` and `\$95.00` and `pivot \$` and `stop \$` to confirm complete scope.
- Did the implementer perform §4.4 visual verification? PNG paths in return report; not just string-equality.
- Is the inline-comment rationale at `swing/rendering/charts.py:86-89` updated to reflect the new approach? Or does it still claim the (now-removed) `\$` escape works?
- Any other production code that emits chart titles (briefing-side, journal-side, etc.) that should also be checked?
- Could a future ticker name or numeric value (e.g., scientific notation with `e`, hyphenated symbol like `BRK-B`) re-trigger mathtext interpretation? matplotlib's mathtext also fires on `^` and `_`. Out-of-scope for this fix but worth noting if found.

Iterate to `NO_NEW_CRITICAL_MAJOR`. Fix-commits use `fix(rendering): Codex R<N> Major <M> — <description>` format.

---

## §5 Done criteria

1. ✅ `swing/rendering/charts.py:86-90` updated: title format string + inline comment-rationale block.
2. ✅ `tests/rendering/test_chart_overlay.py:270, 287` updated.
3. ✅ `docs/chart-pattern-flag-v1-manual-verification.md` updated (2 example titles).
4. ✅ Fast suite green: `python -m pytest -m "not slow" -q` — 1145 passed.
5. ✅ Manual visual verification done — 2 PNG paths in return report; visual confirmation per the 4 points in §4.4.
6. ✅ Adversarial Codex round → `NO_NEW_CRITICAL_MAJOR`; any review-fix commits landed.
7. ✅ Working tree clean (only `.tmp-mathtext-fix-verify/` and pre-existing `.tmp-*/` dirs untracked).

---

## §6 Return report format

Produce as your final message:

```markdown
## Mathtext Fix Return Report

**Commits landed (HEAD = <SHA>):**
- <SHA1> <subject1>
- <SHA2> <subject2>
- ...

**Fast suite:** <baseline> → <post-fix> (<delta>)
**Adversarial Codex verdict:** <NO_NEW_CRITICAL_MAJOR after R<N>>

### Red-phase evidence (TDD discipline)

Test assertion update commit landed FIRST; tests went RED against unfixed `charts.py`:
<paste pytest output snippet showing AssertionError on the 2 tests>

Production fix landed SECOND; tests went GREEN.

### Visual verification

PNG paths:
- Non-overlay: `.tmp-mathtext-fix-verify/noverlay_after_fix.png`
- Overlay: `.tmp-mathtext-fix-verify/overlay_after_fix.png`

**Confirmation (per §4.4 4-point check):**
1. Title spacing: PASS / FAIL — <one sentence>
2. "stop" not italicized: PASS / FAIL — <one sentence>
3. No `$` glyphs: PASS / FAIL — <one sentence>
4. Overlay flag suffix legible: PASS / FAIL — <one sentence>

**Operator-facing visual confirmation:** please open the two PNGs above and independently confirm.

### Adversarial findings + dispositions

| Round | Finding | Severity | Disposition |
|---|---|---|---|
| R1 | <one line> | Critical/Major/Minor | FIXED in <SHA> / ACCEPTED <reason> |
| ... | ... | ... | ... |

### Open follow-ups

<any items deferred per scope or surfaced for future work — e.g., "matplotlib mathtext can also fire on `^` / `_`; not relevant for current title format but worth noting for future title additions">

### Out-of-scope items NOT touched (confirmation)

- Spec/plan historical records (3 doc references): NOT updated, per §2 scope.
- Other Tier-4 doc fixes: NOT touched.
- Tier-2 / Tier-3 items: NOT touched.
```

---

## §7 If you get stuck

- **`PatternOverlay` constructor signature unclear** → grep `class PatternOverlay` in `swing/rendering/charts.py`; the dataclass definition is in the same file.
- **Visual verification PNG opens but title still shows mathtext artifacts** → the fix is incomplete. Search for any remaining `$` in the production title-construction code path. The overlay-suffix append at line 92 has no `$` so it's not the suspect; check whether anywhere ELSE in the matplotlib rendering pipeline injects `$` (style configuration, mpf defaults, etc.). Report finding to operator.
- **Adversarial round surfaces issues outside this brief's scope** (e.g., other production surfaces with `$` in matplotlib titles) → flag in return report under "Open follow-ups." Do NOT expand scope mid-session per the orchestrator-context anti-pattern "Mid-session scope expansion."
- **Fast suite shows test count drift** (not 1145) → trust pytest output over this brief; report the actual delta in your return report and check whether the change is attributable to your edits.
- **Anything else** → produce the return report with what you have, mark the blocked item explicitly, and stop. Operator + orchestrator will triage.
