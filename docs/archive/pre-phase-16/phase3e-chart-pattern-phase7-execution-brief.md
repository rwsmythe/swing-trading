# Phase 3e — Chart-Pattern Flag-V1: Phase 7 Execution Dispatch Brief (Implementer-Side)

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Execute the IMPLEMENTER-SIDE of Phase 7 — Tasks 7.1 (fixture directory + labeling protocol README) + 7.2 (fixture-loader + parametrized integration test). Stop after Task 7.2 ships. Task 7.3 (≥15 operator-labeled fixtures) is OPERATOR-ONLY work that runs in parallel; Task 7.4 (Phase 7 checkpoint with FP-biased tuning gate) is gated on Task 7.3 completion + tuning decisions.
**Expected duration:** ~1 short session (~2 implementer tasks; small scope).
**Output:** Phase 7 implementer-side commits landed on `main`; fast suite green; fixture-loading helper + parametrized integration test runner in place; labeling-protocol README documents the per-fixture format + operator's labeling responsibilities; adversarial Codex review on the combined Phase 7 implementer-side diff reaches `NO_NEW_CRITICAL_MAJOR`.

**This is the FINAL phase.** After Task 7.2 ships and Task 7.3 fixture labeling completes (operator pace) and Task 7.4 closes (FP-biased tuning), chart-pattern flag-v1 V1 is fully shipped.

---

## §0 Read first

In this order:

1. **`docs/superpowers/plans/2026-04-26-chart-pattern-flag-v1-plan.md`** — THE plan. Phase 7 is at lines 4177-4344 (Tasks 7.1 through 7.4). Read Phase 7 in full. Do NOT execute Task 7.3 (operator-only); do NOT execute Task 7.4 (gated on operator labeling).
2. **`docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`** — the source-of-truth design. Phase 7 implements spec §4 (testing strategy: Layer 2 integration tests). Especially binding: spec §4.2 (operator is SOLE labeler; CSV is literal yfinance pull, no hand-edit; fixtures immutable — retire+replace, never edit-in-place).
3. **`docs/orchestrator-context.md`** — project framing, recent decisions (especially Phase 6 triage decisions: `(internal)` qualifier convention; mathtext fix landed; 4-tier commit-message convention now formalized), most-recent lessons captured (especially internal-Codex-round-BEFORE-orchestrator-Codex-round; subagent role-partitioning within a task; documentation of contract pins).
4. **`CLAUDE.md`** at repo root — gotchas, conventions. Phase 7 implementer-side touches `tests/evaluation/patterns/` (fixture-loader + parametrized test runner) and creates the fixture directory. Doesn't touch production code.
5. **`docs/phase3e-todo.md`** — particularly the "2026-04-26 chart-pattern flag-v1 Phase 6 → Phase 7 handoff items" section at the bottom.
6. **`docs/phase3e-chart-pattern-phase6-execution-brief.md`** (briefly) — context for the Phase 6 dispatch discipline.

---

## §0 Skill posture

**INVOKE:**

- `copowers:executing-plans` — wraps `superpowers:subagent-driven-development` with adversarial Codex review on the combined Phase 7 implementer-side diff.

**DO NOT INVOKE:**

- `copowers:writing-plans` / `superpowers:writing-plans` — plan is settled.
- `copowers:brainstorming` / `superpowers:brainstorming` — design is settled.
- `superpowers:executing-plans` directly — use the copowers wrapper.
- `superpowers:using-git-worktrees` — explicitly NOT required (3-phase ZERO-rogue track record vindicates single-subagent + observable-verification approach).

**RECOMMENDED INTERNAL FLOW (per Phase 5 + Phase 6 lessons):**
1. TDD per task.
2. Internal manual code-review pass after Task 7.2 lands but BEFORE invoking copowers wrapper's Codex round.
3. Optionally: internal-Codex round (subagent-dispatched) BEFORE orchestrator-Codex round if implementer wants extra coverage.
4. Orchestrator-Codex round via copowers wrapper.
5. Fix loop until `NO_NEW_CRITICAL_MAJOR`.

---

## §1 Scope (Phase 7 implementer-side ONLY)

**EXECUTE these tasks (in plan order):**

- **Task 7.1** — Fixture directory at `tests/evaluation/patterns/fixtures/` + labeling protocol README at `tests/evaluation/patterns/fixtures/README.md`. README documents:
  - Per-fixture file pair: `<TICKER>_<YYYY-MM-DD>_<label>.csv` (literal yfinance pull) + `<TICKER>_<YYYY-MM-DD>_<label>.json` (label + notes + optional expected_confidence_min).
  - Label values: `flag` | `none`.
  - JSON schema: `{"label": "flag|none", "notes": "<why>", "expected_confidence_min": <optional float>}`.
  - Operator-only labeling rule (per spec §4.2): operator picks tickers + dates; literal yfinance pull (no hand-edit); fixtures immutable (retire-and-replace if a label changes).
  - Floor: ≥15 fixtures = 8 flags + 7 non-flags spanning rejection cases (wide-and-loose, deep base/cup, sideways drift with no pole, late-stage failed breakout, stage-4 with bounce, multi-month flat base, ambiguous edge case).
- **Task 7.2** — Fixture-loading helper + parametrized integration test at `tests/evaluation/patterns/test_flag_classifier_integration.py`:
  - Helper function `load_labeled_fixtures(fixture_dir: Path) -> list[LabeledFixture]` that scans the fixtures directory, pairs CSV + JSON files, returns parametrized test cases.
  - Parametrized integration test that runs `classify_flag(bars)` against each fixture's CSV-loaded DataFrame and asserts the label matches expected (`pattern == fixture.label` when `label == 'flag'`; `pattern in ('none', None)` when `label == 'none'`).
  - When `expected_confidence_min` is set, also assert `confidence >= expected_confidence_min`.
  - Test SKIPS gracefully when fixtures directory is empty (Task 7.3 hasn't shipped yet); doesn't fail the suite.
  - When fixtures DO exist, computes FP/FN tally per spec §3.1.4 + §4.2; reports tally for FP-biased tuning gate (Task 7.4).

**DO NOT EXECUTE (out of scope; STOP here):**

- **Task 7.3** — OPERATOR-ONLY work. Operator labels and commits ≥15 fixtures at their own pace. Implementer MUST NOT label fixtures (per spec §4.2 — operator is SOLE labeler; implementer cannot fabricate). If you find yourself wanting to "demonstrate" with even one example fixture, STOP — the operator's first labeling commit IS the demonstration.
- **Task 7.4** — Phase 7 checkpoint. Gated on Task 7.3 completion + FP-biased tuning decisions. Operator runs the integration tests, classifies failures as FP (algo says flag, operator labeled none) or FN (algo says none, operator labeled flag), and tunes `cfg.classifier.*` thresholds per spec §3.1.4 if FP > FN. Implementer's role at Task 7.4 (when it eventually fires): support tuning recommendations + final test-suite verification.
- ANY modification to `swing/` production code (no tasks in this dispatch touch it).
- ANY new pattern beyond `flag_pattern` (V1 = single pattern only; V2+ extensions via separate dispatch).

If Phase 7 implementer-side reveals a problem that requires touching out-of-scope code, STOP and surface to orchestrator under "OPEN QUESTIONS" in the return report.

**In-scope-by-extension** (per scope-deviation acceptance pattern, 2026-04-26): updating `.gitignore` if needed for new test scratch directories (`pytest --basetemp=.tmp-phase7/` per brief §4 hygiene corollary).

---

## §2 Task 7.1 specification (fixture directory + labeling protocol README)

**Files:**
- Create: `tests/evaluation/patterns/fixtures/.gitkeep` (empty file to track empty directory)
- Create: `tests/evaluation/patterns/fixtures/README.md` (labeling protocol)

**README content:**

The README MUST document:

1. **Purpose.** Operator-labeled OHLCV fixtures for chart-pattern flag-v1 integration tests. Per spec §4.2, operator is SOLE labeler.
2. **File format per fixture (paired CSV + JSON):**
   - CSV: `<TICKER>_<YYYY-MM-DD>_<label>.csv`. Format: literal yfinance OHLCV pull (Open, High, Low, Close, Volume columns; Date index). DO NOT hand-edit values; pull and save as-is.
   - JSON: `<TICKER>_<YYYY-MM-DD>_<label>.json`. Schema: `{"label": "flag" | "none", "notes": "<operator rationale>", "expected_confidence_min": <optional float in [0.0, 1.0]>}`.
3. **Labeling rules** (per spec §4.2):
   - Operator picks (ticker, end-date) pairs based on visual flag-pattern criteria (reference: `reference/images/flag_pattern.png`).
   - Operator labels each fixture as `flag` (clearly fits the §3.1.3 gate definitions) OR `none` (clearly does not).
   - Operator notes WHY in the JSON `notes` field (which gate(s) the operator believes the fixture exercises).
   - Optional `expected_confidence_min` for `flag` fixtures pins a confidence floor (test asserts `result.confidence >= expected_confidence_min`).
4. **Coverage requirement** (per spec §4.2):
   - ≥15 total fixtures = 8 flags + 7 non-flags.
   - Non-flag fixtures should span rejection cases: wide-and-loose (fails tightness or pullback_depth), deep base/cup (fails flag_length range), sideways drift with no pole (fails pole_gain), late-stage failed breakout (fails flag_floor_holds), stage-4 with bounce (fails ma_structure), multi-month flat base (fails flag_length range), ambiguous edge case (operator's call on which gate).
5. **Immutability** (per spec §4.2):
   - Fixtures are immutable. NEVER edit a fixture's CSV or JSON in place.
   - If a label changes (operator's eye changes on re-review), retire the fixture (delete) and replace with a new one (different filename).
6. **Generation procedure (operator-facing):**
   - Pick (ticker, end-date) pair.
   - `python -c "import yfinance as yf; df = yf.Ticker('AAPL').history(end='2026-04-26', period='90d'); df.to_csv('tests/evaluation/patterns/fixtures/AAPL_2026-04-26_flag.csv')"` (or equivalent).
   - Create paired JSON with label + notes.
   - Commit: `test(patterns): add labeled flag fixture <TICKER>_<DATE>` (or equivalent).
7. **Running the integration tests:**
   - `python -m pytest tests/evaluation/patterns/test_flag_classifier_integration.py -v` runs the parametrized suite over all committed fixtures.
   - Empty directory → suite SKIPS gracefully.
   - With fixtures → runs `classify_flag(bars)` against each, asserts label match + optional confidence floor.

**Tests:** Task 7.1 doesn't directly add tests beyond confirming the README is well-formed (e.g., a smoke test that the README path exists; that the fixtures directory exists with `.gitkeep`).

**Commit message:** `feat(patterns): Task 7.1 — fixture directory + labeling protocol README`

---

## §3 Task 7.2 specification (fixture-loader + parametrized integration test)

**Files:**
- Create: `tests/evaluation/patterns/_fixtures.py` (helper module, leading-underscore opts out of pytest collection)
- Create: `tests/evaluation/patterns/test_flag_classifier_integration.py` (parametrized integration test)

**`_fixtures.py` content:**

```python
"""Fixture-loader for chart-pattern flag-v1 integration tests (Task 7.2).

Scans `tests/evaluation/patterns/fixtures/` for paired CSV + JSON files;
returns parametrized test cases. Per spec §4.2, fixtures are immutable
operator-labeled OHLCV pulls; this module just loads them.
"""

from dataclasses import dataclass
from pathlib import Path
import json
import pandas as pd

FIXTURE_DIR = Path(__file__).parent / "fixtures"


@dataclass(frozen=True)
class LabeledFixture:
    name: str
    bars: pd.DataFrame
    label: str  # 'flag' or 'none'
    notes: str
    expected_confidence_min: float | None


def load_labeled_fixtures(fixture_dir: Path = FIXTURE_DIR) -> list[LabeledFixture]:
    """Scan fixture_dir for paired CSV + JSON files; return list of LabeledFixture."""
    if not fixture_dir.exists():
        return []
    fixtures = []
    for csv_path in sorted(fixture_dir.glob("*.csv")):
        json_path = csv_path.with_suffix(".json")
        if not json_path.exists():
            continue  # unpaired CSV; skip
        meta = json.loads(json_path.read_text())
        bars = pd.read_csv(csv_path, parse_dates=[0], index_col=0)
        fixtures.append(LabeledFixture(
            name=csv_path.stem,
            bars=bars,
            label=meta["label"],
            notes=meta.get("notes", ""),
            expected_confidence_min=meta.get("expected_confidence_min"),
        ))
    return fixtures
```

**`test_flag_classifier_integration.py` content (skeleton):**

```python
"""Parametrized integration test for chart-pattern flag-v1 (Task 7.2).

Per spec §4.2, runs classify_flag against operator-labeled fixtures and
asserts label match + optional confidence floor. Empty fixture directory
SKIPS gracefully (Task 7.3 hasn't shipped); doesn't fail the suite.
"""

import pytest

from swing.config import ClassifierConfig
from swing.evaluation.patterns.flag_classifier import classify_flag
from tests.evaluation.patterns._fixtures import LabeledFixture, load_labeled_fixtures


_FIXTURES = load_labeled_fixtures()


@pytest.mark.skipif(not _FIXTURES, reason="No labeled fixtures committed yet (Task 7.3 operator-only)")
@pytest.mark.parametrize("fixture", _FIXTURES, ids=lambda f: f.name)
def test_classify_flag_matches_labeled_fixture(fixture: LabeledFixture):
    """Operator-labeled fixture: classify_flag(bars) should match label."""
    cfg = ClassifierConfig()
    result = classify_flag(fixture.bars, cfg=cfg)

    if fixture.label == "flag":
        assert result.pattern == "flag", (
            f"Fixture {fixture.name} labeled 'flag' but classifier returned "
            f"pattern={result.pattern!r}. Notes: {fixture.notes}"
        )
        if fixture.expected_confidence_min is not None:
            assert result.confidence >= fixture.expected_confidence_min, (
                f"Fixture {fixture.name} labeled 'flag' but classifier "
                f"confidence {result.confidence:.3f} < expected_min "
                f"{fixture.expected_confidence_min:.3f}."
            )
    elif fixture.label == "none":
        assert result.pattern in ("none", None), (
            f"Fixture {fixture.name} labeled 'none' but classifier returned "
            f"pattern={result.pattern!r}. Notes: {fixture.notes}"
        )
    else:
        pytest.fail(f"Unknown label {fixture.label!r} on fixture {fixture.name}")
```

**Tests for the helper module:**

- `test_load_labeled_fixtures_empty_dir_returns_empty_list`: passes an empty directory; asserts `[]`.
- `test_load_labeled_fixtures_pairs_csv_and_json`: creates a synthetic paired CSV + JSON in a tmp dir; asserts `LabeledFixture` constructed correctly.
- `test_load_labeled_fixtures_skips_unpaired_csv`: creates an unpaired CSV; asserts skipped (not in result).
- `test_load_labeled_fixtures_returns_sorted_by_name`: creates 2+ fixtures; asserts result is sorted by `csv_path.stem` (deterministic ordering for parametrize).

**Discriminating-test discipline:** the helper tests use exact-equality on field values (`fixture.label == "flag"`), not substring matching. Per the 2026-04-26 lesson on log-line / format assertions.

**Commit message:** `feat(patterns): Task 7.2 — fixture-loader + parametrized integration test runner`

---

## §4 Conventions

- **Branch:** `main`. No feature branches.
- **TDD discipline (rigid):** failing test first; one red-green cycle per logical change. Phase 7 implementer-side has 2 tasks; sequential single-subagent dispatch is recommended (3-phase ZERO-rogue track record).
- **Commit-message conventions** (4-tier formalized 2026-04-26 post-Phase-6):
  - **Task implementations:** `feat(patterns): Task X.Y — <description>`.
  - **Adversarial review-fix commits (orchestrator Codex):** `fix(patterns): Codex R1 Major 2 — <description>`.
  - **Adversarial review-fix commits (internal Codex within-task):** `fix(patterns): Codex R1 Major 1 (internal) — <description>` — the `(internal)` qualifier distinguishes from orchestrator-Codex; subject-only grep regex `^[a-z]+\([a-z]+\): Codex R\d` still matches both.
  - **Internal code-review fix commits:** `fix(patterns): code-review T7.1 — <description>`.
  - **Format-only cleanup:** no task ID needed.
- **Subject-only grep observable verification** (refined 2026-04-26): `git log --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'` in commit body BEFORE each task implementation commit.
- **Discriminating-test discipline:** every test must produce different outcomes pre-fix vs post-fix (per `feedback_regression_test_arithmetic` memory). Fixture-loader tests use exact-equality on field values; integration test asserts pattern-label match.
- **Tests:** `python -m pytest -m "not slow" -q` MUST be green at the Phase 7 implementer-side checkpoint. Baseline at start: 1127 fast tests.
- **Ruff:** baseline 81 errors per CLAUDE.md. Phase 7 implementer-side must NOT introduce new violations in `tests/evaluation/patterns/`. Run `ruff check tests/evaluation/patterns/` before final commit.
- **Phase 7 implementer-side scope boundary:** every modified file MUST be in `tests/evaluation/patterns/` OR `.gitignore` (for `.tmp-phase7/`). If you find yourself touching `swing/`, STOP — implementer-side is test-only; production code is not modified.
- **Scratch directory hygiene.** Use `pytest --basetemp=.tmp-phase7/` (add to `.gitignore`).
- **Operator labeling is OUT OF SCOPE.** DO NOT add even one example fixture. The first labeling commit MUST be the operator's. Per spec §4.2 + locked-constraint: operator is SOLE labeler.

---

## §5 Adversarial review (handled by copowers wrapper)

The `copowers:executing-plans` wrapper invokes Codex MCP review on the combined Phase 7 implementer-side diff. Pass these specific watch items:

- **Spec fidelity.** Phase 7 implementer-side implements spec §4 verbatim — fixture format (paired CSV + JSON); labeling protocol; ≥15 floor; immutability; operator-only labeling.
- **Plan fidelity.** Tasks executed in plan order; no skipped tasks; no tasks added beyond Tasks 7.1 + 7.2; commit messages follow §4 conventions.
- **Operator-labeling boundary.** Implementer MUST NOT add any labeled fixtures. The fixtures directory should be EMPTY at end of Phase 7 implementer-side dispatch (only `.gitkeep` + `README.md`). Verify by `ls tests/evaluation/patterns/fixtures/`.
- **Helper module robustness.** `load_labeled_fixtures(fixture_dir)`:
  - Returns `[]` on missing directory.
  - Returns `[]` on empty directory.
  - Skips unpaired CSV (no JSON match).
  - Skips unpaired JSON (no CSV match).
  - Returns sorted list (deterministic for parametrize).
  - Handles malformed JSON gracefully (raise with clear error OR skip + warn — pick one and document).
  - Handles malformed CSV gracefully (raise with clear error OR skip + warn).
- **Integration test SKIPs gracefully** when fixtures empty (Task 7.3 hasn't shipped). Verified by running the suite at Phase 7 implementer-side ship time — should NOT fail; should report "skipped" for the parametrized case.
- **Discriminating tests.** Per `feedback_regression_test_arithmetic`: exact-equality on label match; substring-match insufficient.
- **Commit-message convention compliance.** Codex flags any task implementation commit missing `Task X.Y —` prefix; any review-fix commit missing round + finding ID; any internal-Codex commit missing `(internal)` qualifier.
- **Observable verification (per §4 subject-only grep).** Each task implementation commit body contains the grep output.
- **Out-of-scope creep.** No modification to `swing/` production code; no labeled fixture additions.

---

## §6 Done criteria

Phase 7 implementer-side is done when ALL of the following hold:

- [ ] Tasks 7.1 + 7.2 have landed commits on `main`.
- [ ] Each task implementation commit message follows §4 conventions; commit body contains observable verification evidence.
- [ ] No duplicate task implementations; no mixed-task commits.
- [ ] `python -m pytest -m "not slow" -q` green (full fast suite); helper-module tests pass; integration test SKIPs gracefully (no fixtures).
- [ ] `ruff check tests/evaluation/patterns/` clean (no new violations).
- [ ] Fixture directory exists with `.gitkeep` + `README.md`; ZERO labeled fixture files committed (operator-only territory).
- [ ] `_fixtures.py` helper module loads parametrized test cases correctly (verified by helper-module tests).
- [ ] `test_flag_classifier_integration.py` runs parametrized over loaded fixtures; SKIPs gracefully when empty.
- [ ] Adversarial Codex review on combined Phase 7 implementer-side diff reaches `NO_NEW_CRITICAL_MAJOR`.
- [ ] Phase 7 implementer-side does NOT touch `swing/` production code.

---

## §7 Return report format

Final message to orchestrator (via operator) MUST include:

```
PHASE: 7 implementer-side (Tasks 7.1 + 7.2; Tasks 7.3 + 7.4 OPERATOR/GATED) of chart-pattern flag-v1 plan
COMMIT CHAIN: <first SHA>..<last SHA> (N commits)
FAST SUITE: 1127 → <new count> tests (Δ +<count>)
ADVERSARIAL ROUNDS: <N>; FINAL VERDICT: NO_NEW_CRITICAL_MAJOR

TASKS COMPLETED:
- Task 7.1 — Fixture directory + labeling protocol README, commit SHA
- Task 7.2 — Fixture-loader + parametrized integration test runner, commit SHA

PARTITIONING DISCIPLINE OUTCOME:
- Subagent count: <N>
- Task assignments: <list>
- Collisions detected: <none / list>
- Pre-task deliverable-existence checks: <fired count; aborts>
- Observable verification (subject-only grep): <count; sample>
- Scratch directories: <cleaned / list any remaining + ACL state>

INTEGRATION TEST INFRASTRUCTURE SUMMARY:
- Fixture directory: tests/evaluation/patterns/fixtures/ with .gitkeep + README.md
- Labeling protocol README: <one-line summary of content>
- Helper module _fixtures.py: <function signature + behavior>
- Parametrized test: <skeleton verified; SKIPs when empty>
- Empty-directory SKIP behavior: <verified>

ADVERSARIAL FINDINGS (each with disposition):
- <finding>: FIXED in commit <SHA> / ACCEPTED with rationale: <text>

OPEN QUESTIONS FOR ORCHESTRATOR:
- <any plan/spec contradiction surfaced; otherwise "None">

LESSONS WORTH CAPTURING (process insights from execution):
- <bullet list>

PHASE 7 IMPLEMENTER → OPERATOR (Task 7.3) HANDOFF NOTES:
- Fixtures directory ready; labeling protocol README documents the format + procedure.
- Operator picks tickers + dates; saves yfinance pulls + label JSONs; commits.
- ≥15 fixtures floor (8 flags + 7 non-flags spanning rejection cases per spec §4.2).
- Integration test SKIPs gracefully until first fixture ships; runs automatically once fixtures present.
- <any other operator-facing notes>

PHASE 7 IMPLEMENTER → ORCHESTRATOR (Task 7.4) HANDOFF NOTES:
- Task 7.4 (Phase 7 checkpoint with FP-biased tuning gate) gated on Task 7.3 (operator labeling).
- When fixtures ship, run `python -m pytest tests/evaluation/patterns/test_flag_classifier_integration.py -v`; classify failures as FP/FN; tune cfg.classifier.* if FP > FN per spec §3.1.4.
- Phase 7 implementer-side ships the test infrastructure; tuning + checkpoint are operator+orchestrator decisions.
```

---

## §8 If you get stuck

- **Plan/spec contradictions.** Surface in return report under "OPEN QUESTIONS." Do NOT amend the plan or spec; do NOT re-design.
- **TDD ordering uncertainty.** Failing-test-first. Phase 7 implementer-side tasks are small and amenable to per-element TDD.
- **Codex finding contradicts plan.** Apply receiving-code-review discipline.
- **Out-of-scope pull.** If a task seems to require touching `swing/`, STOP. Implementer-side is test-only.
- **Subagent collision detected mid-execution.** STOP, surface to orchestrator immediately. Per Phase 4 + 5 + 6 vindication: this should NOT happen with single-subagent dispatch + observable verification, but if it does, surface and let orchestrator decide.
- **Operator-labeling boundary uncertainty.** If you find yourself wanting to add even one example fixture to "demonstrate" the loader works, STOP. The helper-module tests use SYNTHETIC fixtures (constructed in tmp dir) for verification; the real fixtures directory stays empty until operator labels.
- **mpf import in helper module.** The helper module uses pandas + json only; doesn't need mpf. classify_flag is invoked at integration test time, not at fixture load time.

---

## §9 Anti-patterns specific to this execution

- **Adding even one labeled fixture.** Operator-labeling territory. Helper-module tests use synthetic fixtures in tmp dirs, NEVER in the real fixtures directory.
- **Hand-editing fixture CSV values.** Per spec §4.2, CSVs are literal yfinance pulls. Tests verify the loader works on real-format data; synthetic-data smoke tests are fine for the loader itself.
- **Skipping the empty-directory SKIP behavior.** The integration test MUST skip gracefully when fixtures are empty (Task 7.3 hasn't shipped). If the test fails or errors instead of skipping, the suite breaks at Phase 7 ship time.
- **Coupling helper module to specific fixture filenames.** The loader scans the directory; doesn't hardcode names. Test by creating various filenames in tmp dirs.
- **Misnamed parametrize IDs.** Use `csv_path.stem` for clean test IDs (e.g., `AAPL_2026-04-26_flag` rather than the full path). Makes test failures readable.
- **Substring-match assertions.** Per 2026-04-26 lesson: format assertions use exact-equality. Use `assert fixture.label == "flag"` not `assert "flag" in fixture.label`.
- **Missing `(internal)` qualifier on internal-Codex fix commits.** Per Phase 6 lesson + 2026-04-26 convention. If you dispatch an internal-Codex round before the orchestrator round, qualify the fix commits.
