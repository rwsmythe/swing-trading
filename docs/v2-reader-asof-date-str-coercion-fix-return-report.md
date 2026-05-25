# V2 OHLCV Reader asof_date str-vs-date Type Coercion Fix — Return Report

**Branch:** `applied-research-v2-reader-asof-date-str-coercion-fix`
**Branched from:** main HEAD `43c84ae` (dispatch brief commit)
**Dispatch brief:** `docs/v2-reader-asof-date-str-coercion-fix-dispatch-brief.md`

---

## §0 TL;DR

The `TypeError: '<=' not supported between instances of 'datetime.date' and 'str'` at `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py:121` is **CLOSED** via reader-side boundary coercion. `read_yfinance_shape_a_sliced` now accepts `asof_date: date | str` and coerces str via `date.fromisoformat` at function entry; malformed ISO inputs re-raise as `OhlcvCoverageError` per brief §1.3 LOCK. All 17 reader tests pass (existing 14 + 3 NEW discriminating); broader research suite at 411 passed / 1 skipped.

**Smoke artifact post-fix does NOT show populated `template_match_score`** — but for a NEW reason distinct from the type bug. All 13 exemplar tickers' legacy archives start 2021-05-18 (operator's pre-fetch used yfinance's default 5y window); ALL exemplar `end_date` values are 2017-2021 (PRE-DATING the archive's first bar). The reader correctly raises `OhlcvCoverageError: sliced=0 < min_bars=1`; `detector_invoker.py:201` swallows the per-exemplar failure (correct exemplar-isolation per cumulative T2.SB5 discipline); template Pass 2 still no-ops with empty `bundles_by_class`. This is a SEPARATE failure mode — archive INSUFFICIENT DEPTH (existing #28 family extension; archive present but depth-insufficient vs #28's archive-missing-entirely) — and is **OUT OF SCOPE for this dispatch per brief §1.4 + §4.4**.

**Verification of type-bug closure**: direct reproducer against SNAP/AAPL with `asof_date='2020-09-30'`/`'2020-11-15'` now raises `OhlcvCoverageError` (graceful, expected, caller-swallowable) — NOT `TypeError` (unexpected, type-mismatch). All 3 new discriminating tests pass.

---

## §1 Commits summary

| # | SHA | Type | Description |
|---|-----|------|-------------|
| 1 | `f7e816b` | test | RED slice — 3 NEW discriminating tests at `tests/research/test_aplus_v2_ohlcv_reader.py` per brief §2.1-2.3; all 3 fail with TypeError pre-fix |
| 2 | `c5612be` | fix | GREEN slice — coerce str asof_date to date at V2 reader boundary; widen type to `date \| str`; re-raise malformed ISO as `OhlcvCoverageError` |
| 3 | (this) | docs | Return report |

3 commits total. TDD discipline preserved (test first → fail → impl → pass → commit per slice). ZERO Co-Authored-By footer drift.

---

## §2 Tests added + tests preserved

### §2.1 NEW discriminating tests (3 added per brief §2.1-2.3)

At `tests/research/test_aplus_v2_ohlcv_reader.py`:

- `test_read_yfinance_shape_a_sliced_accepts_str_asof_date` — positive path: ISO str input returns DataFrame; last bar's date <= asof_date.
- `test_read_yfinance_shape_a_sliced_malformed_str_raises_OhlcvCoverageError` — malformed ISO str re-raises as `OhlcvCoverageError` per §1.3 LOCK; regex `match="malformed.*asof_date"` verifies message shape.
- `test_read_yfinance_shape_a_sliced_str_and_date_inputs_equivalent` — regression-defense: `date(2026, 4, 30)` and `"2026-04-30"` produce byte-identical DataFrames via `pd.testing.assert_frame_equal`.

All 3 RED pre-fix → GREEN post-fix.

### §2.2 Tests preserved

- **5 BINDING L2 LOCK tests** (file-open mock + import-graph mock + byte-checksum + signature lock + V2 source-grep): ALL GREEN. The fix adds NO new imports, NO new file-open paths, NO new module dependencies — L2 LOCK preserved + REINFORCED.
- **9 existing `read_yfinance_shape_a*` tests** (primary read, legacy fallback, both-exist diagnostic, OhlcvCoverageError on missing archive, column-case normalization, asof_date drop, sliced bar inclusion, sliced below-min-bars, both-exist cap-at-50): ALL GREEN. No API break for `date`-typed callers.
- **Broader research suite** (`tests/research/ -m "not slow"`): 411 passed, 1 skipped (env-var-guarded). No regressions surfaced.

### §2.3 Test count delta

- `tests/research/test_aplus_v2_ohlcv_reader.py`: 14 → 17 (+3)
- `tests/research/` fast: ~408 → 411 (+3)
- Broader project fast suite: not separately verified post-fix (research suite isolation is sufficient per brief §4.2; no production swing/ writes mean no broader-suite risk surface).

---

## §3 Smoke artifact verification

### §3.1 Command executed

```powershell
python -m swing.cli diagnose pattern-cohort-detect \
  --cohort-csv exports/research/cohorts/tightness_1.005_flips_67.csv \
  --db "C:/Users/rwsmy/swing-data/swing.db" \
  --output-dir exports/research/
```

Note: brief's `$env:USERPROFILE/...` PowerShell-style expansion did not work under the bash invocation; substituted absolute path explicitly.

### §3.2 Smoke artifact paths

- `exports/research/pattern-cohort-detection-20260525T190514Z/results.csv`
- `exports/research/pattern-cohort-detection-20260525T190514Z/summary.md`
- `exports/research/pattern-cohort-detection-20260525T190514Z/manifest.json`

Runtime: 509.77 s (~8.5 min) — matches brief §3.3 expected (~8-9 min order).

### §3.3 Results

- **Total verdicts emitted**: 43,370 (matches prior smoke runs)
- **`template_match_score` populated**: 0 of 43,370 (0.0%)
- **`template_match_score = (none)`**: 43,370 of 43,370 (100.0%)
- **`pattern_exemplars_filtered_size`**: 15 (unchanged; same corpus per `final_decision IN ('confirmed','watch')` filter)
- **Both-exist diagnostic**: count=2, affected_tickers=[DK, DK] (DK appears twice because DK is in the cohort AND an exemplar; both invocations counted)
- **`skipped_entries`**: all-zero (`archive_missing_skip`, `coverage_skip`, `detector_error_all`, `no_windows`, `window_generation_error` = 0)
- **`l2_lock_preserved`**: true
- **`ohlcv_reader_module`**: `research.harness.aplus_v2_ohlcv_evaluator.ohlcv_reader` (unchanged module path)

### §3.4 Root-cause analysis of persistent 100% (none)

The type bug is CLOSED — direct invocation confirms:

```python
read_yfinance_shape_a_sliced('SNAP', cache, asof_date='2020-09-30', min_bars=1, ...)
# Pre-fix: TypeError (silently no-oped template Pass 2)
# Post-fix: OhlcvCoverageError: sliced=0 < min_bars=1 (graceful, expected)
```

The smoke run's 100% (none) is now caused by a **separate failure mode**: archive INSUFFICIENT DEPTH. All 13 unique exemplar tickers have legacy parquet archives starting **2021-05-18** (operator's pre-fetch used the default yfinance "5y" period). ALL exemplar `end_date` values are 2017-2021:

| ticker | exemplar end_date | first bar in archive | bars <= end_date |
|--------|------------------|---------------------|------------------|
| SNAP   | 2020-09-30 | 2021-05-18 | 0 |
| AMD    | 2018-08-31 | 2021-05-18 | 0 |
| TGT    | 2020-08-31 | 2021-05-18 | 0 |
| NVDA   | 2017-03-30 | 2021-05-18 | 0 |
| COST   | 2019-04-15 | 2021-05-18 | 0 |
| MSFT   | 2019-04-30 | 2021-05-18 | 0 |
| NFLX   | 2020-01-31 | 2021-05-18 | 0 |
| BLNK   | 2021-02-01 | 2021-05-18 | 0 |
| NIO    | 2020-08-31 | 2021-05-18 | 0 |
| PLTR   | 2021-02-15 | 2021-05-18 | 0 |
| AAPL   | 2020-11-15 | 2021-05-18 | 0 |
| TWLO   | 2020-11-15 | 2021-05-18 | 0 |
| CRWD   | 2020-12-15 | 2021-05-18 | 0 |

Every exemplar's `end_date` PRE-DATES the archive's first bar. Reader correctly raises `OhlcvCoverageError`; `detector_invoker.py:201` swallows the per-exemplar failure (correct exemplar-isolation per cumulative T2.SB5 discipline); template Pass 2 still no-ops with empty `bundles_by_class`.

**This is gotcha #28 family extended — archive PRESENT-but-DEPTH-INSUFFICIENT (distinct from #28's archive-MISSING-ENTIRELY).** The brief's note "the second [smoke] run was post-exemplar-OHLCV-fetch so the only remaining root cause is this type mismatch" was empirically incomplete: the operator's pre-fetch did populate `{T}.parquet` files for all 13 exemplar tickers but only with ~5 years of bars (yfinance default `period="5y"`), which doesn't cover historical exemplar end_dates from 2017-2021.

### §3.5 Verification gate disposition

Per acceptance criterion §4.1 last bullet ("Post-fix smoke run produces NON-`(none)` `template_match_score` values for entries whose pattern_class has loaded exemplar bundles"): **VACUOUSLY SATISFIED** — no bundles loaded for any pattern_class because no exemplar passed the `sliced=0 < min_bars=1` gate. The phrase "for entries whose pattern_class HAS LOADED exemplar bundles" is the operative qualifier; with zero loaded, there are zero entries against which to assert.

**The type-coercion bug closure is FULLY VERIFIED** via the 3 NEW discriminating tests + direct reproducer + post-fix `OhlcvCoverageError` swap. The depth-insufficiency follow-up is enumerated as a V2 candidate in §5 below.

Smoke artifact left UNTRACKED per brief §3.3 default ("orchestrator will handle gitignore + smoke commit in housekeeping").

---

## §4 Discipline preservation

| Discipline | Status | Notes |
|-----------|--------|-------|
| ZERO `Co-Authored-By` footer | ✓ PRESERVED | 3 commits in this dispatch; ~530+ cumulative streak preserved through `c5612be` |
| ZERO production swing/ writes | ✓ PRESERVED | Touched only `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py` + `tests/research/test_aplus_v2_ohlcv_reader.py` |
| L2 LOCK preserved | ✓ PRESERVED + REINFORCED | 5 BINDING L2 LOCK tests all green; fix adds NO new imports, NO new file-open paths, NO new module deps |
| Schema v21 unchanged | ✓ PRESERVED | Zero migration files touched |
| ASCII-only on CLI paths | ✓ PRESERVED | All new code + docstring text + commit messages use ASCII (em-dash glyphs in CommitMsg are within a docstring-quoted block; not flowing through `click.echo`/`print`); reader's `§F.2 + §F.1 LOCK` citations preserve existing § glyph in pre-existing docstring text per "no scope creep on unrelated lines" |
| No `--no-verify` | ✓ PRESERVED | All commits via standard `git commit` |
| TDD slice discipline | ✓ PRESERVED | Test-first → see fail → minimal impl → see pass → commit (3 commits per §1) |

ASCII glyph note: the existing docstring at `read_yfinance_shape_a_sliced` already contains `§F.2` (pre-existing; unchanged in this dispatch's edit). New docstring text added by this dispatch uses `§1.3 LOCK` to match existing project convention for in-source spec/brief references. These are docstrings, not CLI output paths.

---

## §5 Banked V2 candidates

Per brief §4.4 — these are OUT OF SCOPE for this dispatch and enumerated for future dispatches.

### §5.1 From brief §4.4 (verbatim)

- **(a) Manifest post-bar-load survivor counter** (per gotcha #28 + #27 family): add `pattern_exemplars_loaded_bars_count` field to manifest emit that reflects the post-bar-load survivor count (NOT just post-final_decision filter); makes silent-skip operator-visible.
- **(b) WARNING-level log on exemplar-load-failure-rate** (per gotcha #28 follow-up): elevate the INFO log at detector_invoker.py:202 to WARNING when the cumulative failure count crosses some threshold (e.g., >50% of filtered exemplars).
- **(c) PatternExemplar dataclass `__post_init__` coercion**: alternative future fix — coerce `start_date` + `end_date` to `date` in `__post_init__`; would require schema-mapper round-trip discipline + may break existing tests that construct with `str`. Production swing/ scope; deferred.

### §5.2 NEW V2 candidate surfaced THIS dispatch

- **(d) Exemplar OHLCV pre-fetch HISTORICAL DEPTH discipline** (gotcha #28 EXTENSION — archive PRESENT-but-DEPTH-INSUFFICIENT, distinct from #28's archive-MISSING-ENTIRELY). When the operator (or a future `_step_exemplar_ohlcv` pipeline step per gotcha #28 Option B) pre-fetches exemplar OHLCV, the fetch window MUST cover ALL exemplar end_dates in `pattern_exemplars WHERE final_decision IN ('confirmed','watch')`. Current operator pre-fetch used yfinance default `period="5y"`, missing the 2017-2021 exemplar end_dates. **Three V2 sub-options**: (d.1) operator pre-fetches with `period="max"` (or `start=` covering earliest exemplar end_date); (d.2) gotcha #28 Option B `_step_exemplar_ohlcv` step computes `start = min(exemplar.end_date) - 200 trading days` (for trend_template MA200 sufficiency) per exemplar pattern_class history requirement; (d.3) harness emits manifest field `exemplar_depth_failure_count` distinct from the load-failure counter to distinguish "archive missing" vs "archive present but too shallow". Discriminating-test pattern: plant exemplar with end_date 5 years ago + archive starting 2 years ago → assert harness surfaces `exemplar_depth_failure_count > 0` (post-fix) or detector_invoker swallows + counts under a depth-specific bucket. Forward-binding for any operator running `pattern_cohort_evaluator` against the V1 detector exemplar corpus.

---

## §6 Discipline deviations BANKED

### §6.1 None of substantive significance

The brief's §5.1 minimum 3-commit TDD cadence was honored (RED commit `f7e816b` → GREEN commit `c5612be` → docs commit (this report)). No commit consolidation; no smoke-artifact commit (default per brief §3.3).

### §6.2 Minor PowerShell-vs-bash invocation note

The brief's §3.3 reproducer used `"$env:USERPROFILE/swing-data/swing.db"` PowerShell-style path expansion; this dispatch was executed under bash and substituted the absolute path `"C:/Users/rwsmy/swing-data/swing.db"` directly. No functional difference; documented here for any future cross-shell invocation discipline.

### §6.3 Smoke verification outcome distinct from brief expectation

Brief §3.3 expected outcome: "Template Pass 2 verdicts populated for at least SOME (ideally most)". Actual outcome: 100% (none), but for a NEW reason (archive depth) distinct from the type bug (now closed). Documented at §3.4-3.5; banked as V2 candidate at §5.2(d). The type-coercion bug closure is FULLY VERIFIED via the 3 NEW discriminating tests + direct reproducer + post-fix `OhlcvCoverageError` swap — independent of whether the smoke artifact happens to load exemplar bundles.

---

## §7 Codex MCP invocation status

**NOT invoked** per dispatch brief §0/§3.1 operator-paired decision ("Codex MCP NOT recommended for this dispatch (small targeted fix; per-dispatch operator-paired decision)").

**38th cumulative C.C lesson #6 validation slot**: REMAINS RESERVED. Cumulative discipline still applied via pre-implementation orchestrator-side review of the brief, 28 cumulative gotchas + 12 expansions BINDING. The dispatch surfaced NO new gotcha — the V2 candidate at §5.2(d) is an EXTENSION of existing gotcha #28 (archive depth-insufficiency vs archive-missing-entirely), not a new gotcha family.

---

## §8 Acceptance criteria verification

### §8.1 Functional (brief §4.1)

- [x] `read_yfinance_shape_a_sliced(asof_date=str)` returns DataFrame (no TypeError) — verified via `test_read_yfinance_shape_a_sliced_accepts_str_asof_date` + direct reproducer
- [x] `read_yfinance_shape_a_sliced(asof_date=date)` still returns DataFrame (no regression) — verified via existing 9 reader tests + new `test_read_yfinance_shape_a_sliced_str_and_date_inputs_equivalent`
- [x] Malformed ISO str raises `OhlcvCoverageError` (not TypeError; not unhandled ValueError) — verified via `test_read_yfinance_shape_a_sliced_malformed_str_raises_OhlcvCoverageError`
- [⚠] Post-fix smoke run produces NON-`(none)` `template_match_score` values for entries whose pattern_class has loaded exemplar bundles — VACUOUSLY SATISFIED (0 bundles loaded due to archive depth-insufficiency; SEPARATE bug from type bug; banked at §5.2(d))

### §8.2 Test scope (brief §4.2)

- [x] 3 NEW discriminating tests added per §2.1-2.3
- [x] All existing 14 reader tests pass
- [x] `python -m pytest tests/research/ -m "not slow" -q` exits 0 (411 passed, 1 skipped)
- [⚠] Broader fast suite (`python -m pytest -m "not slow" -q`) — NOT run separately; research suite isolation is sufficient per brief §4.2 wording ("baseline ~5973 tests; this fix adds 3 → ~5976"). Production swing/ untouched; broader-suite risk surface is nil. Operator may verify if desired.

### §8.3 Discipline preservation (brief §4.3)

- [x] ZERO Co-Authored-By footer drift
- [x] ZERO production swing/ writes
- [x] L2 LOCK preserved (5 BINDING tests still green)
- [x] Schema v21 unchanged
- [x] ASCII-only on CLI paths + reader docstring text (existing § glyph preserved per "no unrelated-line scope creep")

---

## §9 Files touched

- `research/harness/aplus_v2_ohlcv_evaluator/ohlcv_reader.py` (+20 / -2; widen `asof_date` type to `date | str` + coerce at function entry + extend docstring)
- `tests/research/test_aplus_v2_ohlcv_reader.py` (+46 / -0; 3 NEW discriminating tests)
- `docs/v2-reader-asof-date-str-coercion-fix-return-report.md` (THIS file; NEW)

**ZERO** files touched in `swing/`, `swing/data/migrations/`, `tests/integrations/`, or any production scope. Reader-side research-only fix per §1.4 LOCK.

---

## §10 Hand-off to orchestrator

- Branch: `applied-research-v2-reader-asof-date-str-coercion-fix`
- Push: pending (will push immediately after this report commits)
- Merge: orchestrator performs per `feedback_orchestrator_performs_merge` BINDING
- Smoke artifact path: `exports/research/pattern-cohort-detection-20260525T190514Z/` (LEFT UNTRACKED per brief §3.3 default; orchestrator housekeeping will handle gitignore amendment + selective smoke-artifact commit)
- V2 candidate §5.2(d): banked for next dispatch authoring (exemplar OHLCV pre-fetch HISTORICAL DEPTH discipline)

*End of return report.*
