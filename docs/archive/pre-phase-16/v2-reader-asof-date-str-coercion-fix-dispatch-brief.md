# V2 OHLCV Reader asof_date str-vs-date Type Coercion Fix — Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the V2 reader asof_date type-coercion fix implementer. No prior conversation context.

**Mission:** Fix the `TypeError: '<=' not supported between instances of 'datetime.date' and 'str'` raised by `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py:read_yfinance_shape_a_sliced` when called from `research/harness/pattern_cohort_evaluator/detector_invoker.py:182-188`. The bug silently no-ops the pattern_cohort_evaluator's template-match Pass 2 corpus load loop (per-exemplar try/except swallows the TypeError + logs at INFO level + continues with empty `bundles_by_class`), so ALL template_match_score values render `(none)` and composite_score collapses to geometric_score only. Two smoke runs (`exports/research/pattern-cohort-detection-20260525T164425Z` + `20260525T175553Z`) both exhibit 100% `template_match_score=(none)` across 43,370 verdicts; the second run was post-exemplar-OHLCV-fetch so the only remaining root cause is this type mismatch.

**Workflow:** `superpowers:test-driven-development` skill (TDD; test-first → impl → commit per TDD slice). Codex MCP NOT recommended for this dispatch (small targeted fix; per-dispatch operator-paired decision — 38th cumulative C.C lesson #6 validation slot remains RESERVED).

**Branch:** `applied-research-v2-reader-asof-date-str-coercion-fix` — branches from main HEAD `a168f19` (or later).

**Worktree:** `git worktree add .worktrees/applied-research-v2-reader-asof-date-str-coercion-fix applied-research-v2-reader-asof-date-str-coercion-fix`. Work from that cwd; invoke `python -m swing.cli` (NOT bare `swing`).

**Expected duration:** ~1-3 hours operator-paced (small fix; reader-side coercion + 3 discriminating tests + verification re-run).

---

## §0 Read first

1. **THIS BRIEF end-to-end.**
2. **`research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py:101-127`** — `read_yfinance_shape_a_sliced` definition. The slice at line 121 (`df.index.date <= asof_date`) is where the TypeError fires when `asof_date` is `str`.
3. **`research/harness/pattern_cohort_evaluator/detector_invoker.py:177-209`** — calling code. Line 185 passes `ex_row.end_date` (a `str` per `swing/data/models.py:1686 PatternExemplar.end_date: str`). The try/except at line 201 swallows the TypeError into INFO log + `continue` per cumulative T2.SB5 "Bad-exemplar isolation in retrieval functions" discipline — which is correct exemplar-isolation behavior but masks the systemic type-mismatch.
4. **`swing/data/models.py:1674-1702`** — `PatternExemplar` dataclass; `start_date` + `end_date` are typed `str  # ISO date` and have no coercion in `__post_init__`. SQLite TEXT columns hydrate as Python `str`.
5. **`research/harness/aplus_v2_ohlcv_evaluator/sweep.py:759`** + **`research/harness/aplus_v2_ohlcv_evaluator/context_builder.py:285-290 + 357`** — V2 OHLCV evaluator callers; they call `parse_asof_date(...)` (returning a `date`) BEFORE passing to the reader, which is why the V2 OHLCV path works fine. THIS is the precedent: callers normalize at the boundary.
6. **`tests/research/test_aplus_v2_ohlcv_reader.py:133-148`** — existing fixture tests for `read_yfinance_shape_a_sliced` (use `date(...)` inputs; never exercised `str` input).
7. **`docs/orchestrator-handoff-2026-05-25-post-cohort-smoke-typebug-banked.md` §3.2** — handoff brief's reproducer command + fix-site enumeration.
8. **CLAUDE.md** gotchas #1-#28 — cumulative discipline. Especially relevant: gotcha #28 (pattern exemplar OHLCV cache discipline) for context on why this bug surfaced post-OHLCV-fetch.

---

## §1 Root cause + scope

### §1.1 Root cause

`read_yfinance_shape_a_sliced` annotates parameter `asof_date: date` (where `date` is `datetime.date`), but the function body does NOT validate or coerce the input at the boundary. The slice expression `df.index.date <= asof_date` requires both sides to be `date` (numpy element-wise compares `array[date]` against the scalar). Python's `datetime.date.__le__` raises `TypeError` when given a `str` operand. The annotation is documentation-only; runtime accepts any object.

V2 OHLCV callers (sweep.py + context_builder.py) call `parse_asof_date(asof_raw)` (from `swing/evaluation/dates.py` or equivalent) to coerce SQLite-TEXT `data_asof_date` into `date` BEFORE passing to the reader. `pattern_cohort_evaluator/detector_invoker.py:185` does NOT — it passes `ex_row.end_date` (`str` from `PatternExemplar.end_date`) directly.

### §1.2 Two viable fix sites

**Reader-side (RECOMMENDED — defense-in-depth at the boundary):**
- Widen the parameter type to `asof_date: date | str` in `read_yfinance_shape_a_sliced`
- Coerce at function entry: `if isinstance(asof_date, str): asof_date = date.fromisoformat(asof_date)`
- Add typed exception for malformed ISO inputs (re-raise as `OhlcvCoverageError` or new `MalformedAsofDateError`; whichever is more consistent — see §1.3 LOCK)
- Preserves all current `date`-typed callers without API break

**Caller-side (FALLBACK if reader-side scope blocked — discouraged):**
- 1-line at `detector_invoker.py:185`: `asof_date=date.fromisoformat(ex_row.end_date)`
- Risks: future callers from another harness module (or test fixture, or new sub-feature) hit the same bug class; doesn't preempt; defers the lesson

**Decision LOCK: reader-side fix.** Matches existing cumulative gotcha pattern (T-A.1.5b "Literal[...] type hints are NOT runtime-enforced" + T-A.1.5b "Service-layer ValueErrors must be wrapped at CLI boundary"); the type annotation should be backed by `__post_init__`-style runtime validation at the function entry, not relied on as enforcement.

### §1.3 Malformed-input error semantics LOCK

If `asof_date` is `str` and `date.fromisoformat` raises `ValueError` (malformed ISO date), re-raise as `OhlcvCoverageError` with a descriptive message citing the malformed input. Rationale: the calling code's broad try/except at `detector_invoker.py:201` already catches `Exception` and logs+continues; raising `OhlcvCoverageError` keeps the semantic shape consistent with other reader failure modes (`OhlcvCoverageError` is what the reader raises for missing-archive + below-min-bars cases per line 95+123). Do NOT add a new typed exception class for this fix — minimize scope.

### §1.4 Scope LOCK (research-only)

- **Touch ONLY** `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py` (reader-side fix)
- **Touch ONLY** `tests/research/test_aplus_v2_ohlcv_reader.py` (3 NEW discriminating tests; existing 5 BINDING L2 LOCK tests + the 9 `read_yfinance_shape_a_sliced` tests MUST remain green)
- **NO** changes to `research/harness/pattern_cohort_evaluator/` (caller is correct AS-IS once reader accepts str)
- **NO** changes to `swing/` production code (PatternExemplar.end_date stays `str`; that's the schema-mapper contract per pattern_exemplars.py + spec §3.1 ISO-string LOCK)
- **NO** schema migration (v21 LOCKED)
- **NO** new Schwab API calls (L2 LOCK preserved + REINFORCED via existing 5 BINDING reader tests)
- **NO** changes to `swing/data/models.py` (PatternExemplar dataclass)

---

## §2 Discriminating tests (3 NEW required at `tests/research/test_aplus_v2_ohlcv_reader.py`)

### §2.1 Test 1: str input coerces to date and returns DataFrame (positive path)

```python
def test_read_yfinance_shape_a_sliced_accepts_str_asof_date(tmp_path):
    """Reader accepts ISO-date str (e.g., from PatternExemplar.end_date) and
    coerces internally, matching the date-typed call site behavior."""
    # Plant a Shape A parquet with N>=1 bars
    _plant_shape_a(tmp_path / "ZZSL.yfinance.parquet", ...)  # mirror existing fixture pattern
    # Call with ISO date STRING (not datetime.date) — the SQLite-hydrated repo shape
    result = read_yfinance_shape_a_sliced("ZZSL", tmp_path, asof_date="2026-04-30")
    assert isinstance(result, pd.DataFrame)
    assert len(result) >= 1
    # Last index date should be <= the asof
    assert result.index[-1].date() <= date(2026, 4, 30)
```

### §2.2 Test 2: malformed str raises OhlcvCoverageError (not TypeError; not unhandled ValueError)

```python
def test_read_yfinance_shape_a_sliced_malformed_str_raises_OhlcvCoverageError(tmp_path):  # noqa: N802
    """Malformed ISO str input re-raises as OhlcvCoverageError per §1.3 LOCK,
    keeping callers' try/except shape consistent."""
    _plant_shape_a(tmp_path / "ZZSL.yfinance.parquet", ...)
    with pytest.raises(OhlcvCoverageError, match="malformed.*asof_date"):
        read_yfinance_shape_a_sliced("ZZSL", tmp_path, asof_date="not-a-date")
```

### §2.3 Test 3: date input still works (regression-defense; existing 9 tests already cover but this asserts post-fix)

```python
def test_read_yfinance_shape_a_sliced_accepts_date_asof_date_unchanged(tmp_path):
    """date input continues to work identically (no API break)."""
    _plant_shape_a(tmp_path / "ZZSL.yfinance.parquet", ...)
    result_date = read_yfinance_shape_a_sliced("ZZSL", tmp_path, asof_date=date(2026, 4, 30))
    result_str = read_yfinance_shape_a_sliced("ZZSL", tmp_path, asof_date="2026-04-30")
    # Both call shapes return identical results post-fix
    pd.testing.assert_frame_equal(result_date, result_str)
```

### §2.4 L2 LOCK BINDING preservation (existing tests must remain green)

The existing 5 BINDING L2 LOCK tests in `tests/research/test_aplus_v2_ohlcv_reader.py` (covering 4 file-open boundaries + 4-module import sentinel graph + byte-checksum + signature lock + V2 source-grep) MUST remain green. The reader-side fix only adds a coercion at function entry; does NOT introduce new imports, new file-open paths, or new module dependencies. Run the existing tests after the fix to verify.

---

## §3 Watch items + cumulative discipline (BINDING)

### §3.1 Cumulative discipline (28 gotchas; pre-Codex 12-expansion BINDING)

If Codex MCP review invoked (operator-paired choice per pre-dispatch breakpoint), ALL 28 gotchas BINDING for 38th cumulative C.C lesson #6 validation. **ESPECIALLY relevant to this fix**:

- **#28** — pattern exemplar OHLCV cache discipline (just banked; THIS fix is the second part of unblocking template Pass 2 after exemplar OHLCV pre-fetch). Bug #1 was the cache miss; bug #2 is this type mismatch.
- **#27** — silent-skip-without-audit pattern (the per-exemplar try/except at detector_invoker.py:201 IS canonical per-row failure isolation; the silent-skip discipline applies at the manifest counter level — `pattern_exemplars_filtered_size` reports post-final_decision-filter count, NOT post-bar-load survivor count. This fix DOES NOT close that gap; banked as V2 candidate via this brief §4.4).
- **T-A.1.5b "Literal[...] type hints are NOT runtime-enforced"** — same family at the asof_date parameter: annotation `date` is documentation-only without runtime coercion. THIS fix introduces the runtime coercion.
- **T-A.1.5b "Service-layer ValueErrors must be wrapped at CLI boundary"** — analog at the reader boundary: `date.fromisoformat` raises `ValueError`; this fix wraps it as `OhlcvCoverageError` for caller-try/except shape consistency (§1.3 LOCK).

### §3.2 Per-dispatch watch items

- (a) **Existing 5 BINDING L2 LOCK tests + 9 existing reader tests** must all remain green (no API break).
- (b) **No new imports** in `ohlcv_reader.py` (existing `from datetime import date` already covers `date.fromisoformat`).
- (c) **Type annotation widening** from `asof_date: date` to `asof_date: date | str` — confirm Python 3.11+ union-type syntax (project supports per `pyproject.toml >=3.11`).
- (d) **`_get_ohlcv` consumer at context_builder.py:348** (`df.loc[full_df.index.date <= data_asof_date]`) — this is a DIFFERENT slice expression in a DIFFERENT function (not in scope of `read_yfinance_shape_a_sliced`); does NOT need this fix because the caller `build_eval_run_cohort` already receives `data_asof_date: date` (parsed by callers per OQ-15 contract). Verify by tracing the call graph but do NOT modify.
- (e) **Hardcoded date strings in tests** — Python 3.14's stricter ISO parsing should accept "2026-04-30" + reject "not-a-date"; verify the malformed-input test's regex captures the actual error message text.

### §3.3 Post-fix verification re-run (REQUIRED before return-report ship)

```
python -m swing.cli diagnose pattern-cohort-detect \
  --cohort-csv exports/research/cohorts/tightness_1.005_flips_67.csv \
  --db "$env:USERPROFILE/swing-data/swing.db" \
  --output-dir exports/research/
```

Expected outcomes:
- **Smoke artifact written** to `exports/research/pattern-cohort-detection-<NEW-iso-timestamp>/{summary.md, results.csv, manifest.json}`
- **Template Pass 2 verdicts populated** for at least SOME (ideally most) of the 43,370 emits — `template_match_score` column shows NON-`(none)` values for entries whose pattern_class has loaded exemplar bundles
- **`pattern_exemplars_filtered_size: 15`** (unchanged; same corpus)
- **NEW manifest field (banked V2 candidate; see §4.4)**: post-bar-load survivor count — could be implemented in this dispatch as defensive scope expansion OR deferred. **Recommendation: DEFER** to avoid scope expansion — close just the type bug here.
- **Runtime ~8-9 minutes** (same order as prior 8.4 and 8.6 min runs)
- **Both-exist diagnostic should report tickers that have both Shape A + legacy archive shapes** (orthogonal to this fix; some exemplar tickers DO have both — e.g., DK)

Save the smoke artifact dir; commit it alongside the test commits per Turn F's pending §3.3 (gitignore amendment for `exports/research/pattern-cohort-detection-*/{summary.md,results.csv,manifest.json}` — see handoff brief §3.3). The orchestrator will land that gitignore amendment in a separate commit before merge; for THIS dispatch's commit cadence, the smoke artifact can be left untracked OR committed with the test commits (operator-paired choice; default — leave untracked, orchestrator will handle gitignore + smoke commit in housekeeping).

---

## §4 Acceptance criteria

### §4.1 Functional

- [ ] `read_yfinance_shape_a_sliced(asof_date=str)` returns DataFrame (no TypeError)
- [ ] `read_yfinance_shape_a_sliced(asof_date=date)` still returns DataFrame (no regression)
- [ ] Malformed ISO str raises `OhlcvCoverageError` (not TypeError; not unhandled ValueError)
- [ ] Post-fix smoke run produces NON-`(none)` `template_match_score` values for entries whose pattern_class has loaded exemplar bundles (at least 1 verdict per loaded pattern_class)

### §4.2 Test scope

- [ ] 3 NEW discriminating tests added at `tests/research/test_aplus_v2_ohlcv_reader.py` per §2.1-2.3
- [ ] All existing 14 tests at `tests/research/test_aplus_v2_ohlcv_reader.py` still pass (9 reader tests + 5 BINDING L2 LOCK tests)
- [ ] All existing 80 pattern_cohort_evaluator tests at `tests/research/test_pattern_cohort_evaluator_*.py` still pass (the integration test at `test_pattern_cohort_evaluator_integration.py` un-skips when cohort CSV present; should now pass post-fix; verify)
- [ ] `python -m pytest tests/research/ -m "not slow" -q` exits 0 with the new tests included
- [ ] Broader fast suite `python -m pytest -m "not slow" -q` exits 0 (baseline ~5973 tests; this fix adds 3 → ~5976)

### §4.3 Discipline preservation

- [ ] ZERO Co-Authored-By footer drift (preserve ~530+ cumulative streak through `a168f19`)
- [ ] ZERO production swing/ writes
- [ ] L2 LOCK preserved (5 BINDING tests still green)
- [ ] Schema v21 unchanged
- [ ] ASCII-only on CLI paths + reader docstring text

### §4.4 Banked V2 candidates (DO NOT land in this dispatch; enumerate in return report)

- (a) **Manifest post-bar-load survivor counter** (per gotcha #28 + #27 family): add `pattern_exemplars_loaded_bars_count` field to manifest emit that reflects the post-bar-load survivor count (NOT just post-final_decision filter); makes silent-skip operator-visible. Out of scope here.
- (b) **WARNING-level log on exemplar-load-failure-rate** (per gotcha #28 follow-up): elevate the INFO log at detector_invoker.py:202 to WARNING when the cumulative failure count crosses some threshold (e.g., >50% of filtered exemplars). Out of scope here.
- (c) **PatternExemplar dataclass `__post_init__` coercion**: alternative future fix — coerce `start_date` + `end_date` to `date` in `__post_init__`; would require schema-mapper round-trip discipline + may break existing tests that construct with `str`. Production swing/ scope; deferred.

---

## §5 Commit cadence + return report

### §5.1 Commit cadence

Minimum 3 commits (TDD slice discipline):
1. **Test slice (red)**: add 3 NEW failing tests at `tests/research/test_aplus_v2_ohlcv_reader.py`; `pytest` shows them red; commit.
2. **Implementation slice**: add the str→date coercion at `read_yfinance_shape_a_sliced` function entry; widen type annotation; `pytest` shows green; commit.
3. **Verification / smoke re-run (optional commit if smoke artifact is included)**: run `python -m swing.cli diagnose pattern-cohort-detect ...`; verify smoke artifact has populated `template_match_score` values; commit the artifact (or document the path in the return report and leave for orchestrator housekeeping).

If consolidation is more pragmatic (e.g., red+impl as one commit per the operator's recent precedent at T-V2.2 mega-consolidation), document the deviation in the return report.

### §5.2 Return report

Author at `docs/v2-reader-asof-date-str-coercion-fix-return-report.md` per V2 OHLCV / Option A / Option D arc precedents. Sections:
- §0 TL;DR
- §1 Commits summary
- §2 Tests added + tests preserved
- §3 Smoke artifact verification (path + headline)
- §4 Discipline preservation (Co-Authored-By streak + L2 LOCK + production scope + schema lock + ASCII)
- §5 Banked V2 candidates (mirror §4.4 above)
- §6 Discipline deviations BANKED (if any commit consolidation per §5.1 above)
- §7 Codex MCP invocation status (NOT invoked per operator-paired pre-dispatch decision; OR document invocation + Codex chain + 38th cumulative validation outcome if invoked)

---

## §6 Branch + worktree setup

```powershell
# From the repo root:
git checkout main
git pull origin main
git worktree add .worktrees/applied-research-v2-reader-asof-date-str-coercion-fix -b applied-research-v2-reader-asof-date-str-coercion-fix
cd .worktrees/applied-research-v2-reader-asof-date-str-coercion-fix
# Verify branch + working tree are clean
git status
git log --oneline -5
# Work begins from here. Use `python -m swing.cli` (NOT bare `swing`).
```

When done:
- Push branch: `git push -u origin applied-research-v2-reader-asof-date-str-coercion-fix`
- Author return report at `docs/v2-reader-asof-date-str-coercion-fix-return-report.md`
- Open a PR (or notify orchestrator for merge) — orchestrator performs the merge per `feedback_orchestrator_performs_merge` BINDING

---

## §7 Reproducer command

```python
# From the repo root, with the operator's prices_cache populated (e.g., AAPL via Phase 13 exemplar pre-fetch):
import os
from datetime import date
from pathlib import Path
from research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader import (
    read_yfinance_shape_a_sliced,
    BothExistDiagnostic,
)

cache = Path(os.environ['USERPROFILE']) / 'swing-data' / 'prices_cache'

# PRE-FIX: this raises TypeError
try:
    read_yfinance_shape_a_sliced('AAPL', cache, asof_date='2026-05-22', min_bars=1, diagnostic=BothExistDiagnostic())
    print('PRE-FIX: would have returned (post-fix expected)')
except TypeError as exc:
    print(f'PRE-FIX TypeError (expected): {exc}')

# CONTROL: date input works pre-fix
df = read_yfinance_shape_a_sliced('AAPL', cache, asof_date=date(2026, 5, 22), min_bars=1, diagnostic=BothExistDiagnostic())
print(f'CONTROL date input: {len(df)} bars')

# POST-FIX: str input also works
df_str = read_yfinance_shape_a_sliced('AAPL', cache, asof_date='2026-05-22', min_bars=1, diagnostic=BothExistDiagnostic())
print(f'POST-FIX str input: {len(df_str)} bars (expected: same as control)')
```

---

## §8 Do NOT

- Modify `swing/` production code (`PatternExemplar.end_date` stays `str` per spec §3.1 LOCK)
- Modify `research/harness/pattern_cohort_evaluator/` (caller stays unchanged; reader fix is sufficient)
- Add new typed exception classes (re-raise as `OhlcvCoverageError` per §1.3 LOCK)
- Land the banked V2 candidates from §4.4 (manifest survivor counter; WARNING log; PatternExemplar coercion — all DEFERRED)
- Skip the post-fix smoke re-run — without it the fix is not verified end-to-end
- Add Co-Authored-By footer to ANY commit
- Trigger Schwab API calls (L2 LOCK BINDING + REINFORCED via existing 5 tests)

---

*End of dispatch brief. Small targeted research-only fix; reader-side coercion at the boundary; 3 NEW discriminating tests + verification smoke re-run; preserves all cumulative discipline streaks; banked V2 candidates enumerated for future dispatches.*
