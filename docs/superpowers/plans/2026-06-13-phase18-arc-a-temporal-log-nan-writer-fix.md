# Phase 18 Arc 18-A — Temporal-log NaN Writer Fix + Shared Finiteness Predicate — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Stop non-finite OHLC (the 2026-06-10 yfinance `Close=NaN` artifact) from ever entering the immutable, append-only temporal log (`pattern_forward_observations.ohlc_today_json`), by mirroring the Arc-8 trailing-ragged barrier at this second write path through **one** shared finiteness predicate that both write paths consume.

**Architecture:** Extract a single pure predicate `is_finite_ohlc(*values)` into a new stdlib-only module in `swing/data/` (the C1 fix: the two write paths each had their *own* finiteness logic — one as `isna().any()`, one missing entirely — so the Arc-8 barrier never reached the second path; a single predicate cannot re-diverge). Refactor `_trim_trailing_ragged` (DataFrame shape) to consume it; add a finiteness **skip-with-warning** at the temporal-log caller (`_step_pattern_observe`, mirroring its existing `bar is None` branch and Arc-8's "leave the hole; the engine tolerates a hole, not a NaN"); add a belt-and-suspenders finiteness **raise** in the serializer `build_ohlc_today_json` so a *future* write path that forgets the pre-check fails loud rather than silently locking a NaN into the immutable log. Import direction is strictly pipeline → data (the verified-healthy layer rule); `swing/data` never imports `swing/pipeline`.

**Tech Stack:** Python 3.14, pandas, pytest (`-m "not slow"`), ruff. No new dependencies. **NO schema change, NO migration, NO data mutation** (the 103 existing NaN rows are operator-LOCKED to age out; backfill is WITHDRAWN, out of scope).

---

## Environment / shell note (read first)

All commands in this plan run in the **executing implementer's Windows shell** inside the worktree at `<repo>/.worktrees/phase18-arc-a`, where the worktree's `.git` resolves natively — `git add`/`git commit`/`git diff` work normally. The **bash-shaped snippets** (the Task 5 self-audit `grep`/pipe/`||` block and any `\`-continued multi-line command) assume **Git Bash** — this project's POSIX shell, per CLAUDE.md "Windows + gitbash"; the single-line `pytest`/`ruff`/`git` commands run equally in Git Bash or PowerShell. **WSL is NOT the execution environment.** WSL is used ONLY for the writing-plans/executing-plans **Codex adversarial review** (the worktree `.git` is a file WSL cannot resolve, so the Codex invocation passes `--skip-git-repo-check` and Codex never runs `git`). Do not run this plan's git/commit steps inside WSL. (Resolves Codex round-1 Major 2 + round-2 Minor 1.)

---

## Context the implementer needs (read before starting)

**Why this arc exists (the defect, confirmed on disk):**
- `build_ohlc_today_json` ([swing/pipeline/temporal_metadata.py:149](../../../swing/pipeline/temporal_metadata.py#L149)) is the temporal-log construction barrier. It guards completed-session (`date <= cutoff`), key-presence, and provider-domain — but **NOT value finiteness**. A completed past session whose yfinance adjusted `Close` returns `NaN` (O/H/L/V present) passes all three gates and `json.dumps` writes `"close": NaN` into the append-only log.
- The Arc-8 barrier `_trim_trailing_ragged` ([swing/data/ohlcv_archive.py:202](../../../swing/data/ohlcv_archive.py#L202)) exists ONLY on the `ohlcv_archive` write path (call sites at lines 256 and 689); it was never mirrored onto the temporal-log writer. This is the recurring "parallel-archive / two-path divergence" gotcha family.
- The engine gate `validate_bars` ([research/harness/shadow_expectancy/validate.py:32](../../../research/harness/shadow_expectancy/validate.py#L32)) honestly rejects any chain containing a non-finite OHLC bar (`_finite_nonneg` = `math.isfinite(v) and v >= 0`, over OHLC only) to `invalid_ohlc` **before** the sim ([run.py:147](../../../research/harness/shadow_expectancy/run.py#L147)). So no R is ever poisoned — the cost is **sample attrition** (≈30% of attributed signals excluded) in a starved measurement instrument.

**The measurement chain (verified end-to-end — informs the LOCKS):**
`ohlc_today_json` → `io.parse_bar` → `Bar` → `validate_signal` → `validate_bars`. `validate_bars` consults **OHLC only** (volume is never validated); the entry recompute uses `b.high >= pivot` ([run.py:154](../../../research/harness/shadow_expectancy/run.py#L154)). A **missing** observation just yields a shorter chain (a hole the engine prices around); a **NaN** observation excludes the whole signal. Hence "the engine tolerates a hole, not a NaN" — skipping is correct.

**The exact production caller flow** ([swing/pipeline/runner.py:2976-2998](../../../swing/pipeline/runner.py#L2976-L2998)):
```python
bar = _bar_for_date(cfg, ohlcv_cache, det.ticker, observation_date)
if bar is None:
    run_warnings.append({
        "step": "pattern_observe", "ticker": det.ticker,
        "observation_date": observation_date,
        "reason": "no bar for observation_date",
    })
    continue
sessions = _sessions_since(det.data_asof_date, observation_date)
status, change = _advance_status(det, prev=prev, bar=bar, ...)
to_insert.append(PatternForwardObservation(
    ...,
    ohlc_today_json=build_ohlc_today_json(bar, observation_date=observation_date, cutoff=observe_cutoff),
    status=status, ...))
```
`_bar_for_date` ([runner.py:2857-2862](../../../swing/pipeline/runner.py#L2857-L2862)) returns a **bar dict** with lowercase keys `{open, high, low, close, volume, provider}`, values `float(...)`-coerced (`float(NaN)` is `NaN`, no error). The new finiteness skip goes **right after the `bar is None` block, before `_advance_status`** — so a NaN close can never drive a phantom status transition either (see Task 4 pre-fix arithmetic).

**Binding conditions / LOCKS (do not violate — these are QA'd at merge by orchestrator + CHARC + RD):**
- **C1** — ONE shared finiteness predicate in `swing/data/`, consumed by both write paths; no third copy. Import direction pipeline → data only.
- **C2a** — writer fix only: no migration, no data mutation, normal cycle.
- **C3** — do NOT build excluded-reason observability here (that is arc 18-D).
- **LOCK 1** — do NOT weaken `validate_bars` (it is the engine's honest-rejection belt; untouched).
- **LOCK 2** — PRESERVE the existing session/key/provider guards in `build_ohlc_today_json` (ADD finiteness; remove nothing).
- **LOCK 3** — append-only / immutable-log discipline holds (no in-place mutation; no backfill).
- **LOCK 4** — interior-valid bars preserved (the Phase-15 bad-bar-accept posture for HISTORICAL interior bars is unchanged; this guards non-finite OHLC at the write barrier only). The predicate is **finiteness-only** (no `>= 0`) so it adds zero over-rejection of legitimate values.
- **LOCK 5** — NO schema.

---

## Resolved plan-level design decisions (rationale)

1. **Predicate API: `is_finite_ohlc(*values: float) -> bool` (variadic over bare values), NOT a container-typed `is_finite_ohlc_bar(bar)`.** The two write paths carry different shapes — a DataFrame row (capitalized `Open/High/Low/Close`) vs a bar dict (lowercase `open/high/low/close`). A predicate over bare *values* is shape-agnostic, so ONE function serves both without a third copy (the literal C1 requirement). The brief's `is_finite_ohlc_bar` was illustrative ("e.g."); a value-level predicate is the precise extraction. `*values` also preserves `_trim_trailing_ragged`'s existing "check only the OHLC columns that are present" tolerance (`is_finite_ohlc(*row[ohlc])`).

2. **Predicate placement: a NEW stdlib-only module `swing/data/ohlcv_finiteness.py`, NOT inside `ohlcv_archive.py`.** Placing it in `ohlcv_archive` would force `temporal_metadata` (a deliberately pure, no-I/O module) to import `ohlcv_archive`, which imports `yfinance` — a heavy, undesirable new dependency on the pure metadata module. A new module imports only `math`, gives the shared core an unambiguous home, and keeps the import graph clean. `swing/data` → `swing/data` (intra-layer) and `swing/pipeline` → `swing/data` (allowed) only.

3. **Finiteness semantics: `math.isfinite` (rejects NaN AND ±inf), uniformly on both paths.** This matches the engine gate (`validate.py` uses `math.isfinite`), so the writer's "suspenders" reject exactly the set the engine's "belt" rejects. Using `math.isfinite` on the archive path is a **strict, beneficial superset** of the old `isna()` (which caught NaN only) — a trailing ±inf bar is non-finite garbage that should be trimmed too. Using a *different* (NaN-only) definition on one path would re-introduce the divergence C1 forbids. All existing Arc-8 NaN tests stay green (NaN is caught by both); a new trailing-inf discriminator locks the superset.

4. **Two complementary layers: the serializer `build_ohlc_today_json` ADDS a finiteness guard (raise) per the brief's explicit directive; the caller `_step_pattern_observe` does the SKIP-with-warning (the shipped pipeline behavior).** These are not in tension — they sit at different layers and the brief mandates both.
   - **The in-serializer finiteness guard is DIRECTED by the brief, not an optional planner add-on.** Dispatch-brief **Mandate**: "Add a finiteness guard to `build_ohlc_today_json` (`swing/pipeline/temporal_metadata.py`)." Dispatch-brief **LOCK 2**: "PRESERVE the existing completed-session / key-presence / provider guards in `build_ohlc_today_json` (**ADD finiteness**; remove nothing)." A serializer cannot "skip" — its only way to *add a finiteness guard* is to **raise** (exactly as it already raises on session/key/provider violations). So a finiteness raise inside `build_ohlc_today_json` is the literal LOCK-2-compliant implementation; *omitting* it would risk violating LOCK 2. The guard is inserted AFTER the existing key/provider guards (keys guaranteed present), preserving every existing guard (LOCK 2: nothing removed).
   - **The "skip-with-warning NOT reject-and-raise" lock governs the PIPELINE/CALLER behavior, which is satisfied.** The sole production caller (`_step_pattern_observe`) does an explicit `is_finite_ohlc` pre-check and, on a non-finite bar, appends a `warnings_json` entry (`reason="non_finite_ohlc"`) and `continue`s — exactly mirroring the adjacent `bar is None` branch and Arc-8's "never persist bad data; leave the hole." Because the caller pre-checks and skips *before* reaching the serializer, the serializer's finiteness raise is **unreachable in normal operation** — the observable pipeline behavior is skip-with-warning, never a crash. The raise is the belt-and-suspenders that fails loud if a *future* write path forgets the pre-check, rather than silently locking a NaN into the immutable, append-only log (the project's #26 anti-drift guarantee). CHARC's architecture pass concurred with skip-over-reject (C2a) — that concurrence is about the *pipeline* behavior, which this design honors.
   - **Why the caller does NOT just `try/except` the serializer raise:** wrapping `build_ohlc_today_json` in `try/except ValueError` would also swallow the session/key/provider raises (genuine programming errors that should be loud), converting them to silent skips. The caller therefore does a *narrow* explicit finiteness pre-check; the serializer keeps raising for all violations.
   - **Three-eyes-QA ratification hook (surfaced explicitly, per Codex round-1 Major 1):** this reconciliation — finiteness raise *inside* the serializer (LOCK 2) + skip at the caller (skip-not-reject) — is flagged for the CHARC (architecture) and RD (measurement-integrity) reviewers to ratify at the merge gate. If either prefers the strictly lock-*literal* reading (serializer must not raise on a data-quality NaN; rely solely on the caller skip + the engine's `validate_bars` belt), the removal is mechanical and isolated: delete Task 3 entirely (the serializer edit + its four tests) and keep Tasks 1/2/4 unchanged. The plan does not depend on the raise for its primary regression coverage — the caller-level `test_non_finite_ohlc_skips_with_warning` (Task 4) is the binding red→green regression for the verification mandate.

5. **Volume-only-NaN reconciliation: EXEMPT on both paths, by construction.** The predicate never receives volume (callers pass only OHLC), so a bar with finite OHLC but NaN volume is neither trimmed (archive) nor skipped (temporal log). This is identical to Arc-8 (`_trim_trailing_ragged` checks OHLC columns only — "legitimately volume-less bars exist") and consistent with the engine (`validate_bars` never validates volume; the entry recompute uses `high`). A NaN volume that reaches `json.dumps` serializes as the `NaN` token and round-trips via `json.loads` (Python's default `allow_nan=True`), inert downstream. This arc does not change volume handling on either path.

---

## File Structure

| File | Action | Responsibility |
|------|--------|----------------|
| `swing/data/ohlcv_finiteness.py` | **Create** | The ONE shared `is_finite_ohlc(*values)` predicate (stdlib `math` only). C1 home. |
| `swing/data/ohlcv_archive.py` | Modify | `_trim_trailing_ragged` consumes the shared predicate (replaces `isna().any()`); add the import. |
| `swing/pipeline/temporal_metadata.py` | Modify | `build_ohlc_today_json` adds the belt-and-suspenders finiteness raise via the shared predicate; add the import. |
| `swing/pipeline/runner.py` | Modify | `_step_pattern_observe` adds the caller finiteness skip-with-warning; add the local import. |
| `tests/data/test_ohlcv_finiteness.py` | **Create** | Unit tests for the predicate. |
| `tests/data/test_ohlcv_archive_trailing_nan.py` | Modify | Add the trailing-±inf discriminator (locks the `isfinite` superset). All existing tests must stay green. |
| `tests/pipeline/test_lock_guard_completed_day.py` | Modify | Serializer belt-raise tests (non-finite close, inf high, all-NaN) + the volume-only-NaN exemption discriminator. Existing tests stay green. |
| `tests/pipeline/test_step_pattern_observe.py` | Modify | Caller skip-with-warning regression (the REAL 06-10 shape) + volume-only-NaN-still-observed discriminator. |

**Discriminator → test map (verification mandate coverage):**
- *Fully-valid completed bar still records (no over-eager rejection)* → existing `test_observation_appended_with_provider_tag` (caller), existing `test_build_ohlc_today_json_allows_completed_day` (serializer), existing `test_trim_clean_frame_unchanged` (archive) — all stay green.
- *Interior-valid bar preserved* → existing `test_trim_interior_nan_preserved_discriminator` (archive). (Interior is an archive-path concept; the temporal log is append-only one-bar-per-call.)
- *All-NaN F6 case* → new `test_build_ohlc_today_json_rejects_all_nan_ohlc` (serializer) + existing `test_trim_all_rows_ragged_to_empty` (archive) + new `test_nan_anywhere_returns_false` (predicate).
- *Single-field-NaN trailing case* → new `test_non_finite_ohlc_skips_with_warning` (caller), new `test_build_ohlc_today_json_rejects_non_finite_close` (serializer), existing `test_trim_single_trailing_ragged_close_only` (archive).
- *Volume-only-NaN exemption reconciled, identical on both paths* → new `test_volume_only_nan_still_observed` (caller), new `test_build_ohlc_today_json_allows_volume_only_nan` (serializer), existing `test_trim_volume_only_nan_not_trimmed` (archive); the predicate excludes volume by construction.

---

## Task 1: Shared finiteness predicate (`is_finite_ohlc`)

**Files:**
- Create: `swing/data/ohlcv_finiteness.py`
- Test: `tests/data/test_ohlcv_finiteness.py`

- [ ] **Step 1: Write the failing test**

Create `tests/data/test_ohlcv_finiteness.py`:

```python
"""Phase 18 Arc 18-A — the shared OHLC finiteness predicate (C1).

ONE predicate consumed by BOTH write barriers (ohlcv_archive._trim_trailing_ragged
and temporal_metadata.build_ohlc_today_json + its caller). Uses math.isfinite
(NaN AND inf), matching the engine gate validate_bars; volume-exempt by
construction (callers omit it)."""
from __future__ import annotations

import numpy as np

from swing.data.ohlcv_finiteness import is_finite_ohlc

NAN = float("nan")
INF = float("inf")


def test_all_finite_returns_true():
    assert is_finite_ohlc(10.0, 11.0, 9.0, 10.5) is True


def test_nan_anywhere_returns_false():
    # the 2026-06-10 Close=NaN shape, plus NaN in the leading position.
    assert is_finite_ohlc(10.0, 11.0, 9.0, NAN) is False
    assert is_finite_ohlc(NAN, 11.0, 9.0, 10.5) is False


def test_inf_returns_false():
    # matches the engine gate's math.isfinite: +/-inf is non-finite too.
    assert is_finite_ohlc(10.0, INF, 9.0, 10.5) is False
    assert is_finite_ohlc(10.0, 11.0, -INF, 10.5) is False


def test_numpy_float_nan_returns_false():
    # the archive path passes numpy float64 values out of a DataFrame row.
    assert is_finite_ohlc(np.float64(10.0), np.float64("nan")) is False
    assert is_finite_ohlc(np.float64(10.0), np.float64(11.0)) is True


def test_empty_call_returns_true():
    # no values to reject -> True (matches "no OHLC columns -> no-op").
    assert is_finite_ohlc() is True


def test_finiteness_only_does_not_reject_negative():
    # LOCK 4 / no over-rejection: a negative value is FINITE -> True here.
    # Non-negativity stays the engine gate's job (validate_bars `>= 0`), NOT
    # this write barrier. Distinguishes a finiteness-only predicate from a
    # validate_bars copy.
    assert is_finite_ohlc(-5.0, 11.0, 9.0, 10.5) is True
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/data/test_ohlcv_finiteness.py -q`
Expected: FAIL — `ModuleNotFoundError: No module named 'swing.data.ohlcv_finiteness'`.

- [ ] **Step 3: Write minimal implementation**

Create `swing/data/ohlcv_finiteness.py`:

```python
"""Shared OHLC finiteness predicate (Phase 18 Arc 18-A).

ONE source of truth for "are these OHLC values finite?" — consumed by BOTH
write barriers that must reject non-finite OHLC before it reaches durable
storage:

- ``swing.data.ohlcv_archive._trim_trailing_ragged`` (DataFrame-row shape) —
  the Arc-8 trailing-ragged trim on the per-ticker OHLCV archive.
- ``swing.pipeline.temporal_metadata.build_ohlc_today_json`` (bar-dict shape)
  + its caller ``swing.pipeline.runner._step_pattern_observe`` — the
  temporal-log (``pattern_forward_observations``) write path.

Extracting the predicate here (the ``swing/data`` layer) is the C1 fix for the
root cause: the two paths each had their OWN finiteness logic (one present as
``isna().any()``, one missing entirely), so the Arc-8 barrier never reached the
second path. A single predicate cannot re-diverge.

Layer rule (verified-healthy): ``swing/data`` NEVER imports ``swing/pipeline``;
pipeline modules import FROM here. Stdlib-only (``math``) so it adds no
dependency weight to the pure ``temporal_metadata`` module.
"""
from __future__ import annotations

import math


def is_finite_ohlc(*values: float) -> bool:
    """True iff EVERY supplied value is finite (not NaN, not +/-inf).

    Operates on bare VALUES, not a container, so ONE predicate serves both the
    DataFrame-row shape (capitalized Open/High/Low/Close columns) and the
    bar-dict shape (lowercase open/high/low/close keys) without a third copy.

    Volume is EXEMPT by construction: callers pass only the OHLC values they
    wish to gate and never pass Volume (Arc-8: legitimately volume-less bars
    exist and must not be trimmed/skipped). An empty call returns True (no
    values to reject), matching ``_trim_trailing_ragged``'s "no OHLC columns ->
    no-op" arm.

    Uses ``math.isfinite`` — the SAME finiteness definition the engine gate
    ``research/harness/shadow_expectancy/validate.py:_finite_nonneg`` uses, so
    the writer's "suspenders" reject exactly the set the engine's "belt"
    rejects (NaN AND inf). The engine additionally enforces ``>= 0``; that stays
    the engine's job — this predicate is finiteness ONLY (hence the name) and
    adds no over-rejection of legitimate values at the write barrier (LOCK 4).

    Inputs MUST be real numbers (float-coercible: Python/NumPy floats). A
    non-numeric input is a programming error, not a data state. Both call sites
    supply numeric OHLC (the archive's float64 columns; the bar dict's
    ``float(...)``-coerced values).
    """
    return all(math.isfinite(v) for v in values)
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/data/test_ohlcv_finiteness.py -q`
Expected: PASS (6 tests).

- [ ] **Step 5: Commit**

```bash
git add swing/data/ohlcv_finiteness.py tests/data/test_ohlcv_finiteness.py
git commit -m "feat(data): shared is_finite_ohlc predicate for the two OHLC write barriers"
```

---

## Task 2: Refactor `_trim_trailing_ragged` to consume the shared predicate

**Files:**
- Modify: `swing/data/ohlcv_archive.py` (import near top; `_trim_trailing_ragged` body at lines 202-228)
- Test: `tests/data/test_ohlcv_archive_trailing_nan.py` (add one discriminator)

- [ ] **Step 1: Write the failing test**

Append to `tests/data/test_ohlcv_archive_trailing_nan.py` (after `test_trim_clean_frame_unchanged`):

```python
def test_trim_trailing_inf_close_phase18():
    """Phase 18 18-A: a trailing +inf Close is NON-FINITE -> trimmed. The shared
    is_finite_ohlc uses math.isfinite (matching the engine gate), a strict
    superset of the old isna()-only check, which would have KEPT the inf row.
    Locks the beneficial broadening; the NaN cases above still pass identically."""
    d1, d2 = date(2026, 6, 9), date(2026, 6, 10)
    df = _flat_frame({
        d1: (10.0, 11.0, 9.0, 10.5, 1000),
        d2: (10.5, 11.5, 10.0, float("inf"), 1200),  # trailing non-finite (inf)
    })
    trimmed, n = mod._trim_trailing_ragged(df)
    assert n == 1
    assert [d.date() for d in trimmed.index] == [d1]
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/data/test_ohlcv_archive_trailing_nan.py::test_trim_trailing_inf_close_phase18 -q`
Expected: FAIL — under the current `isna().any()` impl, `pd.isna(inf)` is `False`, so the inf row is NOT trimmed → `n == 0` (assert `n == 1` fails; both dates retained).

- [ ] **Step 3: Write the implementation**

In `swing/data/ohlcv_archive.py`, add the import. The module's imports are alphabetized stdlib-then-third-party-then-local; add the local import after the existing `from swing.data...` imports (or, if none, immediately after the third-party imports). Verify the exact insertion point by reading the import block, then add:

```python
from swing.data.ohlcv_finiteness import is_finite_ohlc
```

Then replace the loop condition in `_trim_trailing_ragged`. Change:

```python
    while cut > 0 and bool(df.iloc[cut - 1][ohlc].isna().any()):
        cut -= 1
```

to:

```python
    while cut > 0 and not is_finite_ohlc(*df.iloc[cut - 1][ohlc]):
        cut -= 1
```

And update the docstring's first line + scope note to reflect the shared predicate. Change the opening docstring line:

```python
    """Arc 8 — drop trailing rows where ANY of Open/High/Low/Close is NaN.
```

to:

```python
    """Arc 8 — drop trailing rows where ANY of Open/High/Low/Close is non-finite.

    Phase 18 18-A: the finiteness test is the shared ``is_finite_ohlc`` (the ONE
    predicate also used by the temporal-log writer; C1) — ``math.isfinite``, so
    a trailing +/-inf row is trimmed too (a strict superset of the prior
    ``isna()`` NaN-only check, aligning with the engine gate's finiteness
    definition). Volume is excluded from ``ohlc`` so Volume-only-NaN never trims.
```

Leave the remaining scope-note bullets (interior preserved, Volume-NaN exempt) intact.

Finally, update the two `log.warning` messages so the observability text matches the broadened (non-finite, not NaN-only) trim. At the **serial** trim site (~line 259-262), change:

```python
        log.warning(
            "serial trailing-ragged trim (%s): dropped %d trailing NaN-OHLC "
            "bar(s) %s (retry next fetch)", ticker, n_trimmed, dropped,
        )
```

to:

```python
        log.warning(
            "serial trailing-ragged trim (%s): dropped %d trailing non-finite "
            "OHLC bar(s) %s (retry next fetch)", ticker, n_trimmed, dropped,
        )
```

At the **warm** trim site (~line 693-696), change:

```python
                log.warning(
                    "warm trailing-ragged trim (%s): dropped %d trailing "
                    "NaN-OHLC bar(s) %s (retry next fetch)", ticker, trimmed, dropped,
                )
```

to:

```python
                log.warning(
                    "warm trailing-ragged trim (%s): dropped %d trailing "
                    "non-finite OHLC bar(s) %s (retry next fetch)", ticker, trimmed, dropped,
                )
```

(Verify the exact current strings by reading the two sites before editing — line numbers drift. These warnings go to `pipeline.log`; the text must say "non-finite" now that trailing ±inf is also trimmed, per Codex round-1 Minor 1. No test asserts this string, so no test change is needed; if a future grep test pins it, update accordingly.)

- [ ] **Step 4: Run the tests to verify pass**

Run: `python -m pytest tests/data/test_ohlcv_archive_trailing_nan.py -q`
Expected: PASS — the full file (all existing NaN/volume/interior/empty/warm/serial tests stay green; the new inf discriminator passes). NaN is caught identically by `math.isfinite`, so no existing test regresses.

- [ ] **Step 5: Commit**

```bash
git add swing/data/ohlcv_archive.py tests/data/test_ohlcv_archive_trailing_nan.py
git commit -m "refactor(data): _trim_trailing_ragged consumes shared is_finite_ohlc (C1; +inf superset)"
```

---

## Task 3: Belt-and-suspenders finiteness raise in `build_ohlc_today_json`

**Files:**
- Modify: `swing/pipeline/temporal_metadata.py` (import near top; `build_ohlc_today_json` body at lines 149-170)
- Test: `tests/pipeline/test_lock_guard_completed_day.py` (add serializer-level tests)

- [ ] **Step 1: Write the failing tests**

Append to `tests/pipeline/test_lock_guard_completed_day.py` (the file already imports `build_ohlc_today_json`, `pytest`, and `date as _date`):

```python
def test_build_ohlc_today_json_rejects_non_finite_close():
    """Phase 18 18-A: the REAL 06-10 shape (completed session, keys present,
    provider yfinance, Close=NaN, O/H/L/V finite) is REJECTED by the serializer
    belt. PRE-FIX this returned a JSON string containing the `NaN` token (no
    raise); POST-FIX it raises ValueError."""
    bar = {"open": 10.0, "high": 11.0, "low": 9.0, "close": float("nan"),
           "volume": 1_000_000.0, "provider": "yfinance"}
    with pytest.raises(ValueError, match="non-finite"):
        build_ohlc_today_json(bar, observation_date="2026-06-04",
                              cutoff=_date(2026, 6, 4))


def test_build_ohlc_today_json_rejects_inf_high():
    bar = {"open": 10.0, "high": float("inf"), "low": 9.0, "close": 10.5,
           "volume": 1_000_000.0, "provider": "yfinance"}
    with pytest.raises(ValueError, match="non-finite"):
        build_ohlc_today_json(bar, observation_date="2026-06-04",
                              cutoff=_date(2026, 6, 4))


def test_build_ohlc_today_json_rejects_all_nan_ohlc():
    """The all-NaN F6 case at the serializer belt -> raises (same barrier)."""
    nan = float("nan")
    bar = {"open": nan, "high": nan, "low": nan, "close": nan,
           "volume": 1_000_000.0, "provider": "yfinance"}
    with pytest.raises(ValueError, match="non-finite"):
        build_ohlc_today_json(bar, observation_date="2026-06-04",
                              cutoff=_date(2026, 6, 4))


def test_build_ohlc_today_json_allows_volume_only_nan():
    """Volume-only-NaN is EXEMPT (Arc-8 reconciliation): finite OHLC -> serialized
    even though volume is NaN. A discriminator: an impl that gated volume would
    FAIL this. validate_bars ignores volume too, so the NaN volume is inert."""
    bar = {"open": 10.0, "high": 11.0, "low": 9.0, "close": 10.5,
           "volume": float("nan"), "provider": "yfinance"}
    out = build_ohlc_today_json(bar, observation_date="2026-06-04",
                                cutoff=_date(2026, 6, 4))
    assert '"close": 10.5' in out
```

- [ ] **Step 2: Run tests to verify they fail (the right way)**

Run: `python -m pytest tests/pipeline/test_lock_guard_completed_day.py -q`
Expected:
- `test_build_ohlc_today_json_rejects_non_finite_close` / `_rejects_inf_high` / `_rejects_all_nan_ohlc` → FAIL: `DID NOT RAISE ValueError` (the pre-fix serializer passes all guards and `json.dumps` emits the `NaN`/`Infinity` token).
- `test_build_ohlc_today_json_allows_volume_only_nan` → PASS already (pre-fix has no finiteness check; volume-NaN serializes). This is a guard against over-rejection — it must STAY green after the fix.

- [ ] **Step 3: Write the implementation**

In `swing/pipeline/temporal_metadata.py`, add the import after the existing imports (after `import pandas as pd` on line 14):

```python
from swing.data.ohlcv_finiteness import is_finite_ohlc
```

Then, in `build_ohlc_today_json`, insert the finiteness guard AFTER the provider check and BEFORE the `return json.dumps(...)`. The keys are guaranteed present by the preceding `missing` guard, so reading `bar["open"]` etc. is safe. Change:

```python
    if bar["provider"] not in _OHLC_TODAY_PROVIDERS:
        raise ValueError(
            f"ohlc_today_json provider must be one of {_OHLC_TODAY_PROVIDERS}, "
            f"got {bar['provider']!r}"
        )
    return json.dumps({k: bar[k] for k in _OHLC_TODAY_KEYS})
```

to:

```python
    if bar["provider"] not in _OHLC_TODAY_PROVIDERS:
        raise ValueError(
            f"ohlc_today_json provider must be one of {_OHLC_TODAY_PROVIDERS}, "
            f"got {bar['provider']!r}"
        )
    # Phase 18 Arc 18-A — finiteness construction-barrier (belt-and-suspenders).
    # Mirrors the Arc-8 trailing-ragged barrier at this SECOND write path via the
    # ONE shared predicate (C1). Volume is EXEMPT (not passed) — Arc-8: legit
    # volume-less bars exist; validate_bars likewise ignores volume. SHIPPED
    # behavior is skip-with-warning at the caller (_step_pattern_observe), which
    # pre-checks and skips BEFORE reaching this serializer; this raise is the
    # suspenders that fail LOUD if a FUTURE write path forgets the pre-check,
    # rather than silently locking a NaN into the immutable, append-only log
    # (the #26 anti-drift guarantee). LOCK 1/2: validate_bars untouched; the
    # session/key/provider guards preserved (finiteness ADDED, nothing removed).
    if not is_finite_ohlc(bar["open"], bar["high"], bar["low"], bar["close"]):
        raise ValueError(
            f"ohlc_today_json: refusing to lock a non-finite OHLC bar "
            f"(open={bar['open']!r}, high={bar['high']!r}, "
            f"low={bar['low']!r}, close={bar['close']!r})"
        )
    return json.dumps({k: bar[k] for k in _OHLC_TODAY_KEYS})
```

Also update the function docstring to note the added guard (append one sentence to the existing docstring, after the "...provider provenance is guaranteed, not convention" line):

```python
    Phase 18 18-A: also refuses a non-finite OHLC bar (shared is_finite_ohlc;
    Volume exempt) — a belt-and-suspenders construction barrier; the shipped
    skip-with-warning happens at the caller, which pre-checks before serializing.
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/pipeline/test_lock_guard_completed_day.py -q`
Expected: PASS — the three reject tests now raise `ValueError` matching `non-finite`; the volume-only-NaN test stays green; the existing completed-day/ext-hours tests stay green (those bars are fully finite).

- [ ] **Step 5: Commit**

```bash
git add swing/pipeline/temporal_metadata.py tests/pipeline/test_lock_guard_completed_day.py
git commit -m "feat(pipeline): build_ohlc_today_json belt-and-suspenders finiteness raise (shared predicate)"
```

---

## Task 4: Caller skip-with-warning in `_step_pattern_observe` (the shipped behavior)

**Files:**
- Modify: `swing/pipeline/runner.py` (local import in `_step_pattern_observe` at ~line 2886-2897; new guard after the `bar is None` block at ~line 2983)
- Test: `tests/pipeline/test_step_pattern_observe.py` (add the primary regression + a discriminator)

- [ ] **Step 1: Write the failing tests**

Append to `tests/pipeline/test_step_pattern_observe.py` (the file already imports `json`, `patch`, `get_observations_for_detection`, `_step_pattern_observe`, and the conftest fixtures):

```python
def test_non_finite_ohlc_skips_with_warning(tmp_db_v22, tmp_path):
    """Phase 18 18-A PRIMARY regression (the REAL 06-10 shape): a completed-session
    bar with Close=NaN, O/H/L/V finite, provider=yfinance must be SKIPPED with a
    `non_finite_ohlc` warning -- NO observation row enters the append-only log.

    PRE-FIX arithmetic: _bar_for_date returns the bar with close=NaN (O/H/L
    finite). With NO finiteness check, _advance_status sees high=11.0 >= pivot=10.0
    (the `close < invalidation` arm is `NaN < 8.0` -> False), returning
    ('triggered_open','entry_fired') -- a NaN-close bar driving a PHANTOM trigger.
    build_ohlc_today_json then serializes `"close": NaN` -> 1 row inserted, NO
    warning. POST-FIX: the caller's is_finite_ohlc pre-check skips BEFORE
    _advance_status -> 0 rows, 1 `non_finite_ohlc` warning. The row-count
    assertion distinguishes the two paths (and the skip also prevents the phantom
    trigger)."""
    conn, db_path = tmp_db_v22
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-28")  # pivot 10.0
    cfg = _cfg(tmp_path, db_path)
    lease = _FakeLease(db_path, run_id=1, data_asof="2026-05-29")
    warnings: list[dict] = []
    import pandas as pd
    # O/H/L/V finite, Close=NaN, provider yfinance (the exact 06-10 artifact).
    nan_close = (
        pd.DataFrame([{"asof_date": "2026-05-29", "open": 10.0, "high": 11.0,
                       "low": 9.0, "close": float("nan"), "volume": 1_000_000.0}]),
        {"2026-05-29": "yfinance"})
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window", return_value=nan_close):
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
            _step_pattern_observe(cfg=cfg, lease=lease,
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}),
                                  run_warnings=warnings)
    assert get_observations_for_detection(conn, det_id) == []   # no NaN row locked
    assert any(w.get("reason") == "non_finite_ohlc" and w.get("ticker") == "AAA"
               for w in warnings)


def test_volume_only_nan_still_observed(tmp_db_v22, tmp_path):
    """Phase 18 18-A discriminator: a completed bar with finite OHLC but NaN
    volume is NOT skipped (Volume-NaN exemption reconciled -- the caller's
    is_finite_ohlc gates OHLC only). One row is appended; the engine ignores
    volume so the NaN volume is inert. An impl that gated volume would FAIL this."""
    conn, db_path = tmp_db_v22
    det_id = _plant_detection(conn, ticker="AAA", data_asof_date="2026-05-28")
    cfg = _cfg(tmp_path, db_path)
    lease = _FakeLease(db_path, run_id=1, data_asof="2026-05-29")
    warnings: list[dict] = []
    import pandas as pd
    vol_nan = (
        pd.DataFrame([{"asof_date": "2026-05-29", "open": 9.0, "high": 9.0,
                       "low": 9.0, "close": 9.0, "volume": float("nan")}]),
        {"2026-05-29": "yfinance"})
    with patch("swing.data.ohlcv_archive.resolve_ohlcv_window", return_value=vol_nan):
        with patch("swing.pipeline.runner.lease_data_asof", return_value="2026-05-29"):
            _step_pattern_observe(cfg=cfg, lease=lease,
                                  ohlcv_cache=_StubOhlcvCache({"AAA": _build_bars()}),
                                  run_warnings=warnings)
    assert len(get_observations_for_detection(conn, det_id)) == 1
    assert not any(w.get("reason") == "non_finite_ohlc" for w in warnings)
```

- [ ] **Step 2: Run tests to verify they fail (the right way)**

Run: `python -m pytest tests/pipeline/test_step_pattern_observe.py::test_non_finite_ohlc_skips_with_warning tests/pipeline/test_step_pattern_observe.py::test_volume_only_nan_still_observed -q`
Expected:
- `test_non_finite_ohlc_skips_with_warning` → FAIL: pre-fix inserts 1 row (assert `== []` fails) and emits no `non_finite_ohlc` warning. (Note: pre-fix the row is `build_ohlc_today_json`-serialized — Task 3's serializer raise is NOT yet reached because that raise has shipped, but the *caller* has no pre-check yet, so the row reaches the serializer. **Sequencing caveat:** after Task 3, the serializer now RAISES on the NaN bar, so pre-Task-4 this test would fail with an *unhandled ValueError propagating out of `_step_pattern_observe`* rather than "1 row inserted". Either failure mode is an acceptable RED — see Step 2 note below.)
- `test_volume_only_nan_still_observed` → PASS already (volume exempt end-to-end). Must STAY green after the fix.

**Step 2 note (Task 3 → Task 4 interaction):** Because Task 3 shipped first, the serializer already raises on a non-finite bar. So with Task 4 not yet implemented, `test_non_finite_ohlc_skips_with_warning` fails because the un-pre-checked NaN bar reaches `build_ohlc_today_json`, which raises `ValueError`, which propagates out of `_step_pattern_observe` (the compute pass is not wrapped) — pytest reports an error/failure. This is still a valid RED that the Task-4 caller pre-check turns GREEN (the bar is skipped before the serializer is ever called). The post-fix assertions (`== []` + warning present) are the discriminating green.

- [ ] **Step 3: Write the implementation**

In `swing/pipeline/runner.py`, add the local import inside `_step_pattern_observe` alongside the existing local imports (the block ending with `from swing.pipeline.temporal_metadata import build_ohlc_today_json` at line 2897):

```python
    from swing.data.ohlcv_finiteness import is_finite_ohlc
```

Then insert the finiteness skip immediately after the `bar is None` block (which ends with `continue` at ~line 2983) and before `sessions = _sessions_since(...)`. Change:

```python
        if bar is None:
            run_warnings.append({
                "step": "pattern_observe", "ticker": det.ticker,
                "observation_date": observation_date,
                "reason": "no bar for observation_date",
            })
            continue
        sessions = _sessions_since(det.data_asof_date, observation_date)
```

to:

```python
        if bar is None:
            run_warnings.append({
                "step": "pattern_observe", "ticker": det.ticker,
                "observation_date": observation_date,
                "reason": "no bar for observation_date",
            })
            continue
        # Phase 18 Arc 18-A — non-finite OHLC skip-with-warning (mirrors the
        # bar-is-None branch + Arc-8 "leave the hole; the engine tolerates a
        # hole, not a NaN"). A completed-session bar whose OHLC is non-finite
        # (the 2026-06-10 yfinance Close=NaN artifact, O/H/L/V-finite) must NEVER
        # enter the append-only temporal log. Volume is EXEMPT (not passed) --
        # validate_bars ignores volume too. Skipping HERE, before _advance_status,
        # also means a NaN close never drives a phantom status transition. The
        # one-session interior hole is permanent (not backfilled on later runs);
        # the engine prices around it. is_finite_ohlc (C1) is the SAME predicate
        # the Arc-8 archive trim and the serializer belt consume.
        if not is_finite_ohlc(bar["open"], bar["high"], bar["low"], bar["close"]):
            run_warnings.append({
                "step": "pattern_observe", "ticker": det.ticker,
                "observation_date": observation_date,
                "reason": "non_finite_ohlc",
            })
            continue
        sessions = _sessions_since(det.data_asof_date, observation_date)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/pipeline/test_step_pattern_observe.py -q`
Expected: PASS — the full file. `test_non_finite_ohlc_skips_with_warning`: 0 rows + a `non_finite_ohlc` warning. `test_volume_only_nan_still_observed`: 1 row, no spurious warning. All existing observe tests stay green (their bars are finite).

- [ ] **Step 5: Commit**

```bash
git add swing/pipeline/runner.py tests/pipeline/test_step_pattern_observe.py
git commit -m "feat(pipeline): _step_pattern_observe skips non-finite OHLC with a warning (shared predicate)"
```

---

## Task 5: Full-suite + ruff verification (no new code)

**Files:** none (verification only).

- [ ] **Step 1: Run the focused module set**

Run:
```bash
python -m pytest tests/data/test_ohlcv_finiteness.py \
  tests/data/test_ohlcv_archive_trailing_nan.py \
  tests/pipeline/test_lock_guard_completed_day.py \
  tests/pipeline/test_step_pattern_observe.py -q
```
Expected: all PASS.

- [ ] **Step 2: Run the full fast suite**

Run: `python -m pytest -m "not slow" -q`
Expected: green (≈8132+ as of phase-17 close; the new tests add a handful). Investigate any failure before proceeding — a research-test `sys.modules` polluter is a known intermittent (CLAUDE.md §Windows/tooling); re-run with `-n 0` if a flake is suspected, but a real regression in the four touched modules is not acceptable.

- [ ] **Step 3: Lint**

Run the project's established lint gate (the CLAUDE.md quick-start scope):
```bash
ruff check swing/
```
Expected: clean — the new module `swing/data/ohlcv_finiteness.py` plus the edited lines in `swing/data/ohlcv_archive.py`, `swing/pipeline/temporal_metadata.py`, and `swing/pipeline/runner.py`.

**Test-file lint is OUT OF SCOPE for this arc** (per Codex round-1 Minor 2 / round-2 Major 1, accepted): the project's lint gate is `swing/` only, and the existing `tests/` tree carries pre-existing `I001`/`E501` violations (e.g. `tests/pipeline/test_step_pattern_observe.py` has an unsorted import block + several >100-char lines) that this arc neither introduced nor is chartered to fix — `ruff check tests/...` would flag those, so "Expected: clean" cannot hold over the whole file. Keep the new/edited test code in the existing files' style (≤100-char lines; the local `import pandas as pd` inside the test function, matching each file's established pattern) so the arc adds no NEW violation, but do NOT run ruff over `tests/`.

- [ ] **Step 4: Grep the locks (self-audit before handing to QA)**

Run:
```bash
# C1 / layer rule: data must NOT import pipeline
grep -rn "import swing.pipeline\|from swing.pipeline" swing/data/ || echo "OK: swing/data imports no pipeline"
# the predicate has exactly one definition
grep -rn "def is_finite_ohlc" swing/
# both write paths + the caller consume it
grep -rn "is_finite_ohlc" swing/data/ohlcv_archive.py swing/pipeline/temporal_metadata.py swing/pipeline/runner.py
# validate_bars untouched (LOCK 1)
git diff --stat -- research/harness/shadow_expectancy/validate.py   # expect: empty
# no schema/migration (LOCK 5 / C2a)
git diff --name-only | grep -E "migrations/|\.sql$" && echo "VIOLATION: schema touched" || echo "OK: no schema"
```
Expected: `swing/data` imports no pipeline; exactly one `def is_finite_ohlc`; the predicate referenced in all three production sites; `validate.py` unchanged; no `.sql`/migration in the diff.

- [ ] **Step 5: No commit** (verification task; nothing to add).

---

## Self-Review (run after the plan is written; resolved here)

**1. Spec/condition coverage:**
- C1 (one shared predicate, both paths, pipeline→data import) → Tasks 1-4 (new `swing/data/ohlcv_finiteness.py`; consumed by archive trim, serializer, caller; data imports no pipeline — Task 5 grep).
- C2a (writer fix only; no migration/mutation; normal cycle) → no `.sql`, no `migrations/` (Task 5 grep); no row writes/edits.
- C3 (no observability here) → only `warnings_json` skip entries are added (the going-forward partial-close the brief explicitly allows); no summary.md/monitor surface touched.
- LOCK 1 (validate_bars unchanged) → Task 5 `git diff --stat` of validate.py is empty.
- LOCK 2 (preserve session/key/provider; add finiteness) → Task 3 inserts AFTER those guards; removes nothing (existing completed-day/ext-hours tests stay green).
- LOCK 3 (append-only; no backfill) → no existing-row mutation anywhere; skip = no row.
- LOCK 4 (interior-valid preserved; finiteness-only, no over-rejection) → existing `test_trim_interior_nan_preserved_discriminator` stays green; `test_finiteness_only_does_not_reject_negative` + the volume-only-NaN discriminators lock no over-rejection.
- LOCK 5 (no schema) → Task 5 grep.
- Verification mandate (REAL 06-10 failing test, both-path arithmetic) → Task 4 `test_non_finite_ohlc_skips_with_warning` (caller, shipped) + Task 3 `test_build_ohlc_today_json_rejects_non_finite_close` (serializer belt), each with pre/post arithmetic shown.
- All five mandated discriminators → the discriminator→test map above.

**2. Placeholder scan:** none — every code/test step shows the full content; every command shows expected output.

**3. Type/name consistency:** the predicate is `is_finite_ohlc(*values)` in all four call sites and tests; the warning reason string is `"non_finite_ohlc"` in both the implementation and the caller test; module path `swing.data.ohlcv_finiteness` is identical in all imports and tests.

**Known sequencing caveat (documented, intentional):** Task 3 ships the serializer raise before Task 4 ships the caller pre-check. Between them, the sole production caller has no pre-check, so a NaN bar would raise out of `_step_pattern_observe`. This is fine because (a) the arc is committed as a unit on a feature branch (the intermediate commit is never on `main`), and (b) Task 4's RED/GREEN is robust to either pre-Task-4 failure mode (see Task 4 Step 2 note). If a reviewer prefers the caller-skip to land first, Tasks 3 and 4 may be swapped without changing any code — the predicate (Task 1) is the only hard prerequisite for both.
