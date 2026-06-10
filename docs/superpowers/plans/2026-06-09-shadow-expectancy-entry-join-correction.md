# Shadow-Expectancy Entry / Canonical-Detection Join Correction — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Re-key the shadow-expectancy engine's entry/canonical-detection logic off the screening `candidate.pivot` (recomputed over the canonical forward bars) instead of the geometric `detection.pivot`, so live signals route honestly through the funnel instead of 100% `no_canonical_detection`.

**Architecture:** A *surgical correction* of already-shipped harness code under `research/harness/shadow_expectancy/`. The canonical detection becomes a pure **bar-source** choice (longest frozen observation chain, tie low `detection_id`, guarded by a strict date-prefix invariant); entry is recomputed as the first canonical bar whose `high >= candidate.pivot`. The geometric `detection.pivot` is no longer consulted for entry. Two funnel reasons retire (`no_canonical_detection`, `inconsistent_trigger_state`); one is added (`no_candidate_pivot`). The simulator/bracket/censoring/scorecard math and the funnel two-level structure are **untouched**. One `swing/` change: an idempotent `sys.path` helper in `swing/cli.py` so `swing diagnose …` resolves `research.harness.*`.

**Tech Stack:** Python 3.14, pytest (`-m "not slow"`), SQLite (read-only `mode=ro`), the existing shadow-expectancy harness modules. No new dependencies, no schema change (v25 holds), no forbidden imports (`yfinance`/`schwabdev`/`swing.integrations.schwab`/`swing.data.ohlcv_archive`).

**Authoritative spec:** [`docs/superpowers/specs/2026-06-09-shadow-expectancy-entry-join-correction-design.md`](../specs/2026-06-09-shadow-expectancy-entry-join-correction-design.md) (Codex-converged `6fd664f7`). §5/§5.1 = edit map; §7 = test strategy; §9 = supersede/preserve ledger; §8 = re-runnable live-DB verification.

**Commit discipline (CLAUDE.md):** conventional commits (`fix(research):`, `test(research):`, `refactor(research):`); **NO Claude co-author footer; NO `--no-verify`; no amend.** After the final commit verify `git log -1 --format='%(trailers)'` prints `[]`. ASCII-only in any user-facing string (Windows cp1252 crash gotcha). Run the fast suite with `python -m pytest -m "not slow"`.

---

## File map

**Production (edited):**
- `research/harness/shadow_expectancy/validate.py` — split `no_candidate_pivot` (pivot fault) from `invalid_ohlc` (bar fault). *(Task 1)*
- `research/harness/shadow_expectancy/constants.py` — reason vocabularies: drop `no_canonical_detection` + `inconsistent_trigger_state`; add `no_candidate_pivot`. *(Task 2)*
- `research/harness/shadow_expectancy/collapse.py` — drop `candidate_pivot` param; canonical = longest chain (tie low id); strict date-prefix `inconsistent_detection_series` gate; delete the two retired branches; `no_candidate_join` no longer decided here. *(Task 3)*
- `research/harness/shadow_expectancy/run.py` — entry recompute (`first high >= candidate.pivot`); `never_triggered` / `insufficient_forward_depth` guards; `no_candidate_join` decided here (`candidate is None`); validate-before-recompute order; `entry_bar_weak_close` wiring; new `_DetView`/collapse call. *(Tasks 3, 4)*
- `research/harness/shadow_expectancy/scorecard.py` — additive `entry_bar_weak_close` field on `ShadowTrade` + per-hypothesis count. *(Task 4)*
- `research/harness/shadow_expectancy/output.py` — additive `entry_bar_weak_close` column on `RESULTS_HEADER`. *(Task 4)*
- `swing/cli.py` — idempotent `_ensure_research_importable()` helper + a call before EVERY deferred `from research.harness …` import under the `diagnose` group. *(Task 6)*

**Production (UNCHANGED — do not touch):** `simulator.py`, `bracket.py`, `attribution.py`, `exceptions.py`, `io.py`, `funnel.py` (structure; it merely consumes the updated vocabularies).

**Tests (edited / added):**
- `tests/research/shadow_expectancy/test_validate.py` — pivot fault now `no_candidate_pivot`. *(Task 1)*
- `tests/research/shadow_expectancy/test_constants.py` — new vocabularies. *(Task 2)*
- `tests/research/shadow_expectancy/test_funnel.py` — reason-vocab swap *(Task 2)* + collapse-driven reconciliation test rewritten to new collapse contract *(Task 3)*.
- `tests/research/shadow_expectancy/test_collapse.py` — **full rewrite** to the new contract; obsolete tests deleted. *(Task 3)*
- `tests/research/shadow_expectancy/test_run.py` — summary-label assertion *(Task 2)*; entry-recompute / `no_candidate_join` / `insufficient_forward_depth` *(Task 3)*; `entry_bar_weak_close` *(Task 4)*.
- `tests/research/shadow_expectancy/test_scorecard.py` — `entry_bar_weak_close` count + `ShadowTrade` default. *(Task 4)*
- `tests/research/shadow_expectancy/test_output.py` — new header column. *(Task 4)*
- `tests/research/shadow_expectancy/test_real_shapes.py` — **new file**: BULZ run-89 golden (`never_triggered`), breakout end-to-end (hand-verified R), mixed-first-trigger (not excluded), no-look-ahead invariant. *(Task 5)*
- `tests/research/shadow_expectancy/test_cli.py` — importability helper + grep guard. *(Task 6)*

---

## Verified shipped signatures (recon, 2026-06-09)

- `collapse.collapse_detections(detections, candidate_pivot) -> CollapseResult(canonical, collapsed_ids, exclusion_reason)`. Current branches: `no_candidate_join` (candidate None), `no_canonical_detection` (no pivot match), `inconsistent_detection_series`, `inconsistent_trigger_state`. Uses `normalize_tick`/`PRICE_TICK_DECIMALS`.
- `run._DetView(detection_id, pivot, forward_series_key, first_trigger_session)`; `run._entry_and_forward(chain)` finds first `status=="triggered_open" and status_change_event=="entry_fired"`; `_series_key(chain)` → `tuple((observation_date, open, high, low, close), ...)`; `_ohlc_tuple(j)`.
- `validate.validate_candidate_levels(*, pivot)` returns `"invalid_ohlc"` for pivot `None`/non-finite/`<=0`; `validate_bars` / `validate_signal(*, pivot, bars)`; `_REASON="invalid_ohlc"`.
- `constants`: `FUNNEL_REASONS`, `UNATTRIBUTED_REASONS` (6), `ATTRIBUTED_EXCLUDED_REASONS` (5), `PRICE_TICK_DECIMALS`.
- `funnel.build_funnel(detection, *, signal_outcomes)`; `SignalOutcome(hypothesis, terminal, reason)`; per-terminal reason validation against the two vocab tuples.
- `scorecard.ShadowTrade(hypothesis, triggered, open_at_horizon, realized_r, entry_bar_ambiguous, holding_sessions, censoring_scenarios=None)`; `build_hypothesis_scorecard(trades, *, …)`.
- `output.RESULTS_HEADER` (10 cols ending `entry_bar_ambiguous`); `_write_csv(..., extrasaction="ignore")`.
- `simulator.simulate(*, pivot, entry_bar, forward_bars, params)` — UNCHANGED; never to be called with empty `forward_bars`.
- `swing/cli.py` deferred `from research.harness` sites under `diagnose`: lines 4822, 4883, 4931, 4964, 5028, 5032, 5084, 5160, 5238. `_validate_diagnose_db_path` at 4781.
- `attribution.attribute_hypotheses(candidate, *, registry)` → list of hypothesis names. Watch + `proximity_20ma fail` → `"Near-A+ defensible: extension test"` (H2); watch + `tightness fail` → `"Sub-A+ VCP-not-formed"` (H3); empty criteria → `[]`.
- `testkit`: `make_db(tmp_path)` (migrates to v24), `insert_candidate(*, ticker, bucket, pivot, initial_stop, close=None, criteria=())`, `insert_pipeline_run(conn, eval_run_id, *, state="complete")`, `insert_detection(*, ticker, pipeline_run_id, pivot, data_asof_date, detection_date, pattern_class="vcp", structural_low=None)`, `insert_observation(conn, detection_id, observation_date, *, o,h,l,c, status, event=None, …)`.

---

## Task 1: validate.py — split `no_candidate_pivot` from `invalid_ohlc`

A null/zero/non-finite screening pivot is a **common, expected** data state (~3.5% of `candidates`), not a corrupt bar. Return the specific reason so honesty reporting isn't muddied (spec §3.2). This is self-contained: it changes only the returned string; `run.py` still emits it only for invalid pivots (no test fixture has one yet), and `funnel`'s membership check isn't exercised by this reason until `no_candidate_pivot` is added to `ATTRIBUTED_EXCLUDED_REASONS` in Task 2.

**Files:**
- Modify: `research/harness/shadow_expectancy/validate.py`
- Test: `tests/research/shadow_expectancy/test_validate.py`

- [ ] **Step 1: Rewrite the validate tests to the split contract**

Replace the `test_candidate_levels_reject` and `test_validate_signal_chains_levels_then_bars` bodies in `tests/research/shadow_expectancy/test_validate.py`:

```python
@pytest.mark.parametrize("pivot", [0.0, -5.0, float("nan"), None])
def test_candidate_levels_reject_with_no_candidate_pivot(pivot):
    # spec 3.2: a null / non-finite / <=0 screening pivot is a COMMON expected state, not a
    # corrupt bar -> its OWN reason `no_candidate_pivot`, split from invalid_ohlc.
    assert validate_candidate_levels(pivot=pivot) == "no_candidate_pivot"


def test_validate_signal_chains_levels_then_bars():
    good = [Bar("2026-05-29", 10.0, 11.0, 9.5, 10.5)]
    bad_bar = [Bar("2026-05-29", 10.0, 9.0, 11.0, 9.5)]  # high < low
    assert validate_signal(pivot=10.0, bars=good) is None
    # bad pivot -> levels reject with the pivot-specific reason
    assert validate_signal(pivot=0.0, bars=good) == "no_candidate_pivot"
    # bad bar -> bars reject with invalid_ohlc
    assert validate_signal(pivot=10.0, bars=bad_bar) == "invalid_ohlc"
```

- [ ] **Step 2: Run the tests, see them FAIL against shipped code**

Run: `python -m pytest tests/research/shadow_expectancy/test_validate.py -q`
Expected: FAIL — shipped `validate_candidate_levels` returns `"invalid_ohlc"`, so the new asserts on `"no_candidate_pivot"` fail.

- [ ] **Step 3: Edit validate.py to return the split reason**

In `research/harness/shadow_expectancy/validate.py`, replace the module constant and `validate_candidate_levels` body:

```python
_PIVOT_REASON = "no_candidate_pivot"   # spec 3.2: split from invalid_ohlc
_BAR_REASON = "invalid_ohlc"


def validate_candidate_levels(*, pivot) -> str | None:
    """spec 3.2 (correction): the screening pivot is the SOLE candidate field the mechanical
    trade consumes (entry_fill = max(pivot, entry_bar.open)). candidate.initial_stop is
    deliberately NOT validated (the mechanical stop is entry_bar.low; R2-M1). A null / non-finite
    / <=0 pivot is an EXPECTED, common data state (no screening breakout level) -> the specific
    reason 'no_candidate_pivot', NOT 'invalid_ohlc' (which is reserved for malformed frozen
    bars). pivot finite and > 0 -> None."""
    if pivot is None:
        return _PIVOT_REASON
    if not math.isfinite(pivot):
        return _PIVOT_REASON
    if pivot <= 0:
        return _PIVOT_REASON
    return None
```

Then change every `return _REASON` inside `validate_bars` to `return _BAR_REASON` (5 occurrences), and delete the old `_REASON = "invalid_ohlc"` line. `validate_signal` is unchanged (it already threads whatever reason the helpers return).

- [ ] **Step 4: Run the tests, see them PASS**

Run: `python -m pytest tests/research/shadow_expectancy/test_validate.py -q`
Expected: PASS (all validate tests).

- [ ] **Step 5: Commit**

```bash
git add research/harness/shadow_expectancy/validate.py tests/research/shadow_expectancy/test_validate.py
git commit -m "fix(research): split no_candidate_pivot from invalid_ohlc in shadow-expectancy validate"
```

---

## Task 2: constants.py — reason vocabulary correction

Remove the two retired reasons and add `no_candidate_pivot` (per-hypothesis excluded). At this point `collapse.py` still uses the old signature and *can* still return `no_canonical_detection`/`inconsistent_trigger_state` literals, but no test fixture drives those branches (all seeds match pivots), so the suite stays green. We also update the two consuming assertions that name the old vocabulary (`test_funnel`'s reason test and `test_run`'s summary-label test) in this task so the suite is green at commit.

**Files:**
- Modify: `research/harness/shadow_expectancy/constants.py`
- Test: `tests/research/shadow_expectancy/test_constants.py`, `tests/research/shadow_expectancy/test_funnel.py`, `tests/research/shadow_expectancy/test_run.py`

- [ ] **Step 1: Rewrite the constants vocabulary test**

In `tests/research/shadow_expectancy/test_constants.py`, replace the `test_reason_vocabularies_are_frozen_tuples` membership block:

```python
def test_reason_vocabularies_are_frozen_tuples():
    assert "no_candidate_join" in c.FUNNEL_REASONS
    assert "invalid_ohlc" in c.FUNNEL_REASONS
    assert "degenerate_risk" in c.FUNNEL_REASONS
    assert "inconsistent_detection_series" in c.FUNNEL_REASONS
    assert "never_triggered" in c.FUNNEL_REASONS
    assert "matched_no_hypothesis" in c.FUNNEL_REASONS
    assert "multi_match" in c.FUNNEL_REASONS
    assert "no_candidate_pivot" in c.FUNNEL_REASONS          # correction: split from invalid_ohlc
    # retired by the entry/join correction (spec 3.1): no geometric pivot match remains.
    assert "no_canonical_detection" not in c.FUNNEL_REASONS
    assert "inconsistent_trigger_state" not in c.FUNNEL_REASONS
    # unattributed = pre-/non-attribution states only (spec 3.4): four reasons.
    assert set(c.UNATTRIBUTED_REASONS) == {
        "no_candidate_join", "matched_no_hypothesis", "multi_match",
        "inconsistent_detection_series",
    }
    # post-attribution per-hypothesis excluded reasons (spec 3.5): no_candidate_pivot added.
    assert set(c.ATTRIBUTED_EXCLUDED_REASONS) == {
        "no_candidate_pivot", "invalid_ohlc", "degenerate_risk",
        "insufficient_forward_depth", "missing_observations", "lifecycle",
    }
    assert set(c.ATTRIBUTED_EXCLUDED_REASONS).isdisjoint(set(c.UNATTRIBUTED_REASONS))
    assert set(c.EXIT_REASONS) == {
        "initial_stop", "breakeven_stop", "ma_close_below",
        "horizon_mtm", "never_triggered", "degenerate_risk",
    }
    assert set(c.BRACKET_ARMS) == {"realistic", "favorable_reprice"}
    assert set(c.CENSORING_SCENARIOS) == {
        "closed_only", "mtm_at_horizon", "forced_exit_at_horizon_open",
        "stop_level_adverse",
    }
```

- [ ] **Step 2: Run the constants test, see it FAIL**

Run: `python -m pytest tests/research/shadow_expectancy/test_constants.py::test_reason_vocabularies_are_frozen_tuples -q`
Expected: FAIL — shipped `UNATTRIBUTED_REASONS` still has 6 entries incl. the two retired reasons; `no_candidate_pivot` not yet in any tuple.

- [ ] **Step 3: Edit constants.py vocabularies**

In `research/harness/shadow_expectancy/constants.py` replace the three tuples (leave the long explanatory comment block, but trim the references to the two retired reasons):

```python
# --- Funnel reason vocabulary (7.1; entry/join correction 3.1-3.5) ---
FUNNEL_REASONS = (
    "no_candidate_join", "matched_no_hypothesis", "multi_match",
    "no_candidate_pivot", "invalid_ohlc", "inconsistent_detection_series",
    "degenerate_risk", "insufficient_forward_depth",
    "missing_observations", "lifecycle", "never_triggered",
)
# Reasons reported WITHIN the unattributed bucket (PRE-/NON-attribution states only; spec 3.4).
# The retired no_canonical_detection / inconsistent_trigger_state are GONE (the geometric
# detection.pivot is no longer consulted for entry or collapse). matched_no_hypothesis and
# multi_match are reasons WITHIN this single bucket, not separate top-level buckets. A
# post-attribution data-quality fault (no_candidate_pivot / invalid_ohlc / degenerate_risk) is
# reported PER-HYPOTHESIS in ATTRIBUTED_EXCLUDED_REASONS, never here.
UNATTRIBUTED_REASONS = (
    "no_candidate_join", "matched_no_hypothesis", "multi_match",
    "inconsistent_detection_series",
)
# The ONLY reasons a POST-attribution (per-hypothesis) `excluded` terminal may carry. DISJOINT
# from UNATTRIBUTED_REASONS by construction. no_candidate_pivot (spec 3.2) joins + attributes,
# then is excluded at validate -> per-hypothesis, exactly like invalid_ohlc / degenerate_risk.
ATTRIBUTED_EXCLUDED_REASONS = (
    "no_candidate_pivot", "invalid_ohlc", "degenerate_risk",
    "insufficient_forward_depth", "missing_observations", "lifecycle",
)
```

Leave `PRICE_TICK_DECIMALS` in place (harmless; spec §5 permits keeping it). Leave `EXIT_REASONS`, `BRACKET_ARMS`, `CENSORING_SCENARIOS`, floors, and version unchanged.

- [ ] **Step 4: Update test_funnel's reason-vocab test (drop the retired reason)**

In `tests/research/shadow_expectancy/test_funnel.py`, `test_unattributed_reasons_vs_per_hypothesis`: remove the `no_canonical_detection` outcome from the `outs` list and its assertion. Specifically delete these two lines from `outs`:

```python
        SignalOutcome(hypothesis=None, terminal="unattributed",
                      reason="no_canonical_detection"),
```

and delete this assertion:

```python
    assert f["unattributed"]["no_canonical_detection"] == 1          # M4
```

(The `inconsistent_detection_series`, `matched_no_hypothesis`, `multi_match`, and per-hypothesis assertions stay; they are all still valid reasons.)

- [ ] **Step 5: Update test_run's summary-label assertion to the new vocabulary**

In `tests/research/shadow_expectancy/test_run.py`, `test_run_harness_emits_four_artifacts`, replace the reason-label loop:

```python
    assert "## Unattributed signals" in summary_text
    for reason in ("no_candidate_join", "matched_no_hypothesis", "multi_match",
                   "inconsistent_detection_series"):
        assert f"{reason}=" in summary_text
    # the retired reasons must NOT render anywhere in the summary.
    assert "no_canonical_detection" not in summary_text
    assert "inconsistent_trigger_state" not in summary_text
```

- [ ] **Step 6: Run the affected tests, see them PASS**

Run: `python -m pytest tests/research/shadow_expectancy/test_constants.py tests/research/shadow_expectancy/test_funnel.py tests/research/shadow_expectancy/test_run.py -q`
Expected: PASS. (`run.py`/`collapse.py` behavior is unchanged this task; `_summary_lines` now iterates the 4-reason `UNATTRIBUTED_REASONS`, and no fixture drives a retired-reason branch.)

- [ ] **Step 7: Commit**

```bash
git add research/harness/shadow_expectancy/constants.py tests/research/shadow_expectancy/test_constants.py tests/research/shadow_expectancy/test_funnel.py tests/research/shadow_expectancy/test_run.py
git commit -m "fix(research): retire no_canonical_detection/inconsistent_trigger_state, add no_candidate_pivot to shadow-expectancy vocabularies"
```

---

## Task 3: collapse.py + run.py — canonical longest-chain bar source + entry recompute

The atomic core of the correction. `collapse_detections` drops `candidate_pivot` and selects the **longest** frozen chain (tie low `detection_id`) as a pure bar source, enforcing a **strict date-prefix** `inconsistent_detection_series` gate. `run.py` recomputes entry as the first canonical bar with `high >= candidate.pivot`, routing `never_triggered` (no bar reaches it) and `insufficient_forward_depth` (trigger on the last bar → empty `forward_bars`, simulator NOT called) per-hypothesis. `no_candidate_join` moves to `run.py` (`candidate is None`). These two files are changed together because the collapse signature change ripples directly into the `run.py` call site.

**Files:**
- Modify: `research/harness/shadow_expectancy/collapse.py`
- Modify: `research/harness/shadow_expectancy/run.py`
- Test: `tests/research/shadow_expectancy/test_collapse.py` (full rewrite), `tests/research/shadow_expectancy/test_funnel.py` (collapse-driven test), `tests/research/shadow_expectancy/test_run.py`

- [ ] **Step 1: Full-rewrite test_collapse.py to the new contract (delete the obsolete tests)**

Replace the ENTIRE contents of `tests/research/shadow_expectancy/test_collapse.py`. The deleted tests are: `test_canonical_is_pivot_match_and_collapses_all_non_canonical`, `test_pivot_mismatch_yields_no_canonical_detection`, `test_missing_candidate_yields_no_candidate_join`, `test_tick_normalized_pivot_match`, `test_divergent_trigger_session_excludes` (the trigger-state gate is gone). The new view carries only `detection_id` + `bars`:

```python
from __future__ import annotations

from dataclasses import dataclass

from research.harness.shadow_expectancy.collapse import collapse_detections


@dataclass
class _Det:  # minimal detection view the collapser needs: id + date-ascending bars
    detection_id: int
    bars: tuple   # ((observation_date, open, high, low, close), ...)


_B1 = ("2026-06-01", 9.6, 10.2, 9.5, 10.1)
_B2 = ("2026-06-02", 10.1, 10.5, 10.0, 10.4)
_B3 = ("2026-06-03", 10.4, 10.9, 10.3, 10.8)


def test_canonical_is_longest_chain_tie_low_id():
    # spec 2.3: canonical = the LONGEST frozen chain (most bars); collapsed_ids = every other
    # detection in the group (group_size - 1). The geometric pivot is NOT consulted.
    short = _Det(2, (_B1,))
    longest = _Det(5, (_B1, _B2, _B3))
    medium = _Det(9, (_B1, _B2))
    res = collapse_detections([short, longest, medium])
    assert res.canonical.detection_id == 5             # longest (3 bars)
    assert sorted(res.collapsed_ids) == [2, 9]
    assert res.exclusion_reason is None


def test_tie_break_is_lowest_detection_id():
    a = _Det(7, (_B1, _B2))
    b = _Det(3, (_B1, _B2))   # same length -> lowest id wins
    res = collapse_detections([a, b])
    assert res.canonical.detection_id == 3
    assert res.exclusion_reason is None


def test_single_detection_group_has_no_collapsed():
    res = collapse_detections([_Det(4, (_B1, _B2))])
    assert res.canonical.detection_id == 4
    assert res.collapsed_ids == []
    assert res.exclusion_reason is None


def test_strict_prefix_chain_is_accepted():
    # spec 2.3: a terminated chain that is a STRICT date-prefix of the longest is fine.
    longest = _Det(1, (_B1, _B2, _B3))
    prefix = _Det(2, (_B1, _B2))
    res = collapse_detections([longest, prefix])
    assert res.canonical.detection_id == 1
    assert res.exclusion_reason is None


def test_differing_first_trigger_session_is_accepted():
    # spec 1.3 regression: detections that (under the old observe-step) had DIFFERENT first
    # trigger sessions are NO LONGER excluded -- entry is recomputed, the trigger-state gate is
    # gone. Identical bars across distinct pattern classes collapse cleanly.
    a = _Det(1, (_B1, _B2))
    b = _Det(2, (_B1, _B2))
    res = collapse_detections([a, b])
    assert res.exclusion_reason is None
    assert res.canonical.detection_id == 1


def test_divergent_ohlc_on_shared_date_excludes():
    longest = _Det(1, (_B1, _B2))
    bad_high = ("2026-06-01", 9.6, 10.9, 9.5, 10.1)   # diverges from _B1 on the SAME date
    other = _Det(2, (bad_high,))
    res = collapse_detections([longest, other])
    assert res.exclusion_reason == "inconsistent_detection_series"


def test_gappy_interior_missing_chain_excludes():
    # spec 2.3 / Codex R1-#1: a gappy chain A=[d1,d3] vs B=[d1,d2,d3] (interior date missing)
    # is NOT a strict prefix -> excluded under inconsistent_detection_series, NOT silently
    # accepted with a truncated bar source (the overlap-only check would have missed this).
    full = _Det(1, (_B1, _B2, _B3))
    gappy = _Det(2, (_B1, _B3))   # _B2 (interior) missing
    res = collapse_detections([full, gappy])
    assert res.exclusion_reason == "inconsistent_detection_series"
```

- [ ] **Step 2: Run test_collapse, see it FAIL**

Run: `python -m pytest tests/research/shadow_expectancy/test_collapse.py -q`
Expected: FAIL — shipped `collapse_detections` requires the `candidate_pivot` arg and `_Det` no longer carries `pivot`/`forward_series_key`/`first_trigger_session`; the new tests can't construct/call it.

- [ ] **Step 3: Rewrite collapse.py to the longest-chain + strict-prefix contract**

Replace the ENTIRE contents of `research/harness/shadow_expectancy/collapse.py`:

```python
from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class CollapseResult:
    canonical: Any | None        # the canonical detection view (longest chain), or None on exclusion
    collapsed_ids: list[int]
    # 'inconsistent_detection_series' (strict-prefix invariant violated) | None.
    # no_candidate_join is decided in run.py (candidate is None), NOT here.
    exclusion_reason: str | None


def _sorted_bars(detection) -> tuple:
    """The detection's frozen bars sorted date-ascending. Each bar is
    (observation_date, open, high, low, close)."""
    return tuple(sorted(detection.bars, key=lambda b: b[0]))


def collapse_detections(detections) -> CollapseResult:
    """spec 2.3 (entry/join correction): one shadow signal per (run, ticker) group. The
    canonical detection is a PURE BAR SOURCE -- the geometric detection.pivot is no longer
    consulted. Canonical = the LONGEST frozen observation chain (most bars), tie-broken by
    lowest detection_id.

    The `inconsistent_detection_series` gate enforces the STRICT date-prefix invariant the
    longest-chain rule relies on (Codex R1-#1): after sorting each chain by observation_date,
    every non-canonical chain's date list MUST equal canonical_dates[:len(chain)] (a true
    prefix -- no missing interior sessions, no divergent dates) AND its OHLC on every shared
    date MUST match the canonical's. ANY violation -> exclude. This is NOT an overlap-only
    check (which would silently accept a gappy A=[d1,d3] vs B=[d1,d2,d3]).

    collapsed_ids = every non-canonical detection in the group (group_size - 1), preserving the
    detection-level reconciliation invariant on both the success and exclusion paths.
    """
    group = sorted(detections, key=lambda d: d.detection_id)
    # longest chain, tie low id: max over (len(bars), -detection_id).
    canonical = max(group, key=lambda d: (len(_sorted_bars(d)), -d.detection_id))
    canonical_bars = _sorted_bars(canonical)
    canonical_dates = [b[0] for b in canonical_bars]
    canonical_by_date = {b[0]: b for b in canonical_bars}

    for d in group:
        if d.detection_id == canonical.detection_id:
            continue
        dbars = _sorted_bars(d)
        ddates = [b[0] for b in dbars]
        # strict date-prefix: dates must be exactly the canonical's leading dates.
        if ddates != canonical_dates[: len(ddates)]:
            return CollapseResult(None, [], "inconsistent_detection_series")
        # OHLC on every shared date must match the canonical (full tuple equality).
        for b in dbars:
            if b != canonical_by_date[b[0]]:
                return CollapseResult(None, [], "inconsistent_detection_series")

    collapsed = [d.detection_id for d in group if d.detection_id != canonical.detection_id]
    return CollapseResult(canonical, collapsed, None)
```

(`normalize_tick` and the `PRICE_TICK_DECIMALS` import are deleted here — no equality match remains.)

- [ ] **Step 4: Run test_collapse, see it PASS**

Run: `python -m pytest tests/research/shadow_expectancy/test_collapse.py -q`
Expected: PASS (all 8 new tests).

- [ ] **Step 5: Rewrite the collapse-driven funnel reconciliation test**

In `tests/research/shadow_expectancy/test_funnel.py`, replace `test_detection_reconciliation_from_real_collapse_output` to use the new collapse contract (no `candidate_pivot`, id + bars view, longest-chain):

```python
def test_detection_reconciliation_from_real_collapse_output():
    # Drive the detection-level reconciliation from the REAL collapser over an actual
    # multi-detection group: three detections for one (run, ticker) sharing an identical frozen
    # series -> 1 unique signal + 2 collapsed (group_size - 1).
    from dataclasses import dataclass

    @dataclass
    class _Det:
        detection_id: int
        bars: tuple

    series = (("2026-06-01", 9.6, 10.2, 9.5, 10.1),)
    dets = [_Det(5, series), _Det(2, series), _Det(9, series)]
    res = collapse_detections(dets)
    assert res.exclusion_reason is None
    total_detections = len(dets)
    collapsed_duplicate = len(res.collapsed_ids)
    unique_signals = 1
    det = DetectionLevel(total_detections, collapsed_duplicate, unique_signals)
    f = build_funnel(det, signal_outcomes=[
        SignalOutcome(hypothesis="A+ baseline", terminal="closed", reason=None)])
    dl = f["detection_level"]
    assert (dl["unique_signals"] + dl["collapsed_duplicate_detection"]
            == dl["total_detections"] == 3)
    assert collapsed_duplicate == 2   # group_size - 1
```

- [ ] **Step 6: Update test_run.py for entry-recompute + no_candidate_join move + insufficient_forward_depth**

The existing `_seed_*` helpers in `test_run.py` already produce entry bars whose `high >= pivot` (e.g. `_seed_one_aplus_winner` bar1 high 10.4 vs pivot 10.0), so the recompute yields the same entries — those tests keep passing unchanged. Add three new tests at the end of `tests/research/shadow_expectancy/test_run.py` (they exercise the recompute branches the rewrite introduces):

```python
def _seed_never_triggers_above_pivot(conn, ticker="ZZZ"):
    # candidate.pivot 10.0; the single forward bar's high (9.8) never reaches it -> never_triggered
    # via the RECOMPUTE (not via absence of an entry_fired event).
    eval_id = insert_candidate(conn, ticker=ticker, bucket="aplus", pivot=10.0,
                               initial_stop=9.0, close=10.0)
    pr_id = insert_pipeline_run(conn, eval_id)
    det_id = insert_detection(conn, ticker=ticker, pipeline_run_id=pr_id, pivot=10.0,
                              data_asof_date="2026-05-28", detection_date="2026-05-29")
    insert_observation(conn, det_id, "2026-06-01", o=9.0, h=9.8, l=8.9, c=9.5,
                       status="pending")
    conn.commit()


def test_recompute_never_triggered_when_no_high_reaches_pivot(tmp_path):
    conn = make_db(tmp_path)
    _seed_never_triggers_above_pivot(conn)
    out = tmp_path / "out"
    _, _, _, manifest = run_harness(db_path=tmp_path / "t.db", output_dir=out,
                                    source="pipeline")
    funnel = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]
    assert funnel["per_hypothesis"]["A+ baseline"]["never_triggered"] == 1


def _seed_trigger_on_last_bar(conn, ticker="LAST"):
    # candidate.pivot 10.0; the trigger fires on the LAST (only) bar -> forward_bars empty ->
    # insufficient_forward_depth (per-hypothesis excluded); simulate must NOT be called.
    eval_id = insert_candidate(conn, ticker=ticker, bucket="aplus", pivot=10.0,
                               initial_stop=9.0, close=10.0)
    pr_id = insert_pipeline_run(conn, eval_id)
    det_id = insert_detection(conn, ticker=ticker, pipeline_run_id=pr_id, pivot=10.0,
                              data_asof_date="2026-05-28", detection_date="2026-05-29")
    insert_observation(conn, det_id, "2026-06-01", o=10.0, h=10.4, l=9.6, c=10.2,
                       status="triggered_open", event="entry_fired")
    conn.commit()


def test_zero_forward_depth_routes_insufficient_and_skips_simulate(tmp_path, monkeypatch):
    # Codex R1-#3: a trigger on the last bar excludes under insufficient_forward_depth and
    # simulate() is NEVER called with empty forward_bars.
    import research.harness.shadow_expectancy.run as run_mod

    def _boom(*a, **k):
        raise AssertionError("simulate must not be called for zero-forward-depth")

    monkeypatch.setattr(run_mod, "simulate", _boom)
    conn = make_db(tmp_path)
    _seed_trigger_on_last_bar(conn)
    out = tmp_path / "out"
    _, _, _, manifest = run_mod.run_harness(db_path=tmp_path / "t.db", output_dir=out,
                                            source="pipeline")
    f = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]
    h1 = f["per_hypothesis"]["A+ baseline"]
    assert h1["excluded"].get("insufficient_forward_depth", 0) == 1
    assert h1["closed"] == 0 and h1["never_triggered"] == 0


def _seed_null_pivot_attributed(conn, ticker="NPV"):
    # spec 3.2: an attributed candidate whose screening pivot is 0.0 still JOINS and ATTRIBUTES
    # (bucket + criteria are independent of pivot), then is excluded at VALIDATE -> per-hypothesis
    # no_candidate_pivot. Watch + proximity_20ma -> H2. This is the END-TO-END proof of the
    # attribute -> validate -> per-hyp-excluded ordering (the route a unit test on
    # validate_candidate_levels alone cannot exercise).
    eval_id = insert_candidate(conn, ticker=ticker, bucket="watch", pivot=0.0,
                               initial_stop=9.0, close=10.0,
                               criteria=[("proximity_20ma", "trend_template", "fail")])
    pr_id = insert_pipeline_run(conn, eval_id)
    det_id = insert_detection(conn, ticker=ticker, pipeline_run_id=pr_id, pivot=49.89,
                              data_asof_date="2026-05-28", detection_date="2026-05-29")
    insert_observation(conn, det_id, "2026-06-01", o=10.0, h=10.4, l=9.6, c=10.2,
                       status="pending")
    insert_observation(conn, det_id, "2026-06-02", o=10.3, h=10.6, l=10.1, c=10.5,
                       status="pending")
    conn.commit()


def test_null_candidate_pivot_routes_per_hypothesis_excluded(tmp_path):
    conn = make_db(tmp_path)
    _seed_null_pivot_attributed(conn)
    out = tmp_path / "out"
    _, _, _, manifest = run_harness(db_path=tmp_path / "t.db", output_dir=out,
                                    source="pipeline")
    f = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]
    h2 = f["per_hypothesis"]["Near-A+ defensible: extension test"]
    assert h2["excluded"].get("no_candidate_pivot", 0) == 1
    # it was attributed first (per-hypothesis), NOT dropped to the unattributed bucket.
    assert "no_candidate_pivot" not in f["unattributed"]
```

- [ ] **Step 7: Run the affected tests, see them FAIL**

Run: `python -m pytest tests/research/shadow_expectancy/test_funnel.py::test_detection_reconciliation_from_real_collapse_output tests/research/shadow_expectancy/test_run.py -q`
Expected: FAIL — `run.py` still calls `collapse_detections(views, candidate_pivot=…)` (TypeError now that the param is gone) and still keys entry off `triggered_open`/`entry_fired`, with no `insufficient_forward_depth` guard.

- [ ] **Step 8: Rewrite run.py — `_DetView`, collapse call, validate-before-recompute, entry recompute, guards**

In `research/harness/shadow_expectancy/run.py`:

(a) Replace the `_DetView` dataclass and delete `_entry_and_forward` (keep `_ohlc_tuple` and `_series_key`):

```python
@dataclass
class _DetView:
    detection_id: int
    bars: tuple   # date-ascending ((observation_date, open, high, low, close), ...)
```

(b) Replace the per-group body (the block from `unique_signals += 1` through the `simulate(...)` result emission) with the corrected pipeline order. Use this exact body:

```python
    for (pipeline_run_id, ticker), dets in sorted(groups.items(),
                                                  key=lambda kv: (kv[0][0] or -1, kv[0][1])):
        unique_signals += 1
        # every group collapses len(dets) detections to ONE signal -> len(dets) - 1 duplicates,
        # REGARDLESS of the terminal path (preserves total == unique + collapsed). Counted once
        # here so excluded/unattributed multi-detection groups reconcile too (Codex R1-M3).
        collapsed_duplicate += len(dets) - 1

        # collapse = pure BAR-SOURCE choice (longest chain, tie low id); strict date-prefix gate.
        views = []
        chains = {}
        for d in dets:
            chain = io.read_observation_chain(conn, d.detection_id)
            chains[d.detection_id] = chain
            views.append(_DetView(d.detection_id, _series_key(chain)))
        res = collapse_detections(views)
        if res.exclusion_reason is not None:
            # inconsistent_detection_series (substrate-integrity) -> unattributed bucket.
            signal_outcomes.append(
                SignalOutcome(None, "unattributed", res.exclusion_reason))
            continue

        # join: candidate row absent -> no_candidate_join (decided HERE, not in collapse; 3.3).
        candidate = io.resolve_candidate(conn, pipeline_run_id=pipeline_run_id, ticker=ticker)
        if candidate is None:
            signal_outcomes.append(
                SignalOutcome(None, "unattributed", "no_candidate_join"))
            continue

        # attribute.
        hyps = attribute_hypotheses(candidate, registry=registry)
        if not hyps:
            signal_outcomes.append(
                SignalOutcome(None, "unattributed", "matched_no_hypothesis"))
            continue
        if len(hyps) > 1:
            signal_outcomes.append(
                SignalOutcome(None, "unattributed", "multi_match"))
            continue

        # canonical bar series (longest chain), date-ascending, parsed.
        canonical_chain = chains[res.canonical.detection_id]
        all_bars = [io.parse_bar(o.ohlc_today_json, session=o.observation_date)
                    for o in canonical_chain]

        # validate BEFORE the recompute (Codex M5 order): a null/<=0 pivot is caught as
        # no_candidate_pivot before the recompute dereferences it; bad frozen bars -> invalid_ohlc.
        # Both route PER-HYPOTHESIS (post-attribution), in ATTRIBUTED_EXCLUDED_REASONS.
        reason = validate_signal(pivot=candidate.pivot, bars=all_bars)
        if reason is not None:
            for h in hyps:
                signal_outcomes.append(SignalOutcome(h, "excluded", reason))
            continue

        # entry RECOMPUTE (spec 2.1): first canonical bar whose high >= candidate.pivot.
        entry_idx = next((i for i, b in enumerate(all_bars)
                          if b.high >= candidate.pivot), None)
        if entry_idx is None:
            # no forward bar reaches the screening pivot -> never_triggered (attributed terminal;
            # contributes 0R to per-signal expectancy; D11). Emit a non-triggered ShadowTrade so
            # the scorecard denominator matches the funnel's never_triggered count.
            for h in hyps:
                signal_outcomes.append(
                    SignalOutcome(h, "never_triggered", "never_triggered"))
                shadow_trades.append(ShadowTrade(
                    hypothesis=h, triggered=False, open_at_horizon=False,
                    realized_r=None, entry_bar_ambiguous=False,
                    holding_sessions=0, censoring_scenarios=None,
                    entry_bar_weak_close=False))
            continue
        if entry_idx == len(all_bars) - 1:
            # zero-forward-depth (Codex R1-#3): trigger on the last bar -> forward_bars empty.
            # Exclude per-hypothesis; do NOT call simulate (it would fabricate a 0R MTM).
            for h in hyps:
                signal_outcomes.append(
                    SignalOutcome(h, "excluded", "insufficient_forward_depth"))
            continue

        entry_bar = all_bars[entry_idx]
        forward_bars = all_bars[entry_idx + 1:]
        entry_bar_weak_close = entry_bar.close < candidate.pivot   # 2.2 annotation only

        sim = simulate(pivot=candidate.pivot, entry_bar=entry_bar,
                       forward_bars=forward_bars, params=params)
        if sim.degenerate:
            for h in hyps:
                signal_outcomes.append(SignalOutcome(h, "excluded", "degenerate_risk"))
            continue
        terminal = "open_at_horizon" if sim.open_at_horizon else "closed"
        detection_date = next(d.detection_date for d in dets
                              if d.detection_id == res.canonical.detection_id)
        for h in hyps:
            signal_outcomes.append(SignalOutcome(h, terminal, None))
            shadow_trades.append(ShadowTrade(
                hypothesis=h, triggered=True,
                open_at_horizon=sim.open_at_horizon, realized_r=sim.realized_r,
                entry_bar_ambiguous=sim.entry_bar_ambiguous,
                holding_sessions=sim.holding_sessions,
                censoring_scenarios=sim.censoring_scenarios,
                entry_bar_weak_close=entry_bar_weak_close))
            results_rows.append({
                "ticker": ticker, "detection_date": detection_date,
                "run_id": pipeline_run_id, "hypothesis": h,
                "bucket": candidate.bucket,
                "realistic_r": f"{sim.realized_r['realistic']:.4f}",
                "favorable_r": f"{sim.realized_r['favorable_reprice']:.4f}",
                "exit_reason": sim.exit_reason,
                "open_at_horizon": str(sim.open_at_horizon),
                "entry_bar_ambiguous": str(sim.entry_bar_ambiguous),
                "entry_bar_weak_close": str(entry_bar_weak_close)})
            for leg in sim.legs:
                fav = (sim.terminal_fill["favorable_reprice"]
                       if (sim.terminal_fill is not None and leg.action == "exit")
                       else leg.price)
                ledger_rows.append({"ticker": ticker, "hypothesis": h,
                                    "action": leg.action, "qty": f"{leg.qty:.4f}",
                                    "price": f"{leg.price:.4f}",
                                    "price_favorable": f"{fav:.4f}",
                                    "session": leg.session})
```

> **Note for the worker:** `ShadowTrade(..., entry_bar_weak_close=...)` and the `"entry_bar_weak_close"` results-row key reference the field/column added in Task 4. They are written here (the run-loop rewrite is atomic) and `ShadowTrade` gains the field with a default in Task 4 — so between Step 9 of this task and Task 4 the keyword arg is passed to a dataclass that does not yet accept it. To keep this task green on its own, **add the `entry_bar_weak_close: bool = False` field to `ShadowTrade` now** (the one-line dataclass change from Task 4 Step 3) as part of this step, and the `output.py` header column in Task 4 Step 5. The scorecard count and the dedicated weak-close test still land in Task 4. (Adding the field early is forward-compatible; `extrasaction="ignore"` means the extra results-row key is harmless until the header is widened.)

So in this step ALSO apply the one-line `ShadowTrade` field addition:

```python
@dataclass(frozen=True)
class ShadowTrade:
    hypothesis: str
    triggered: bool
    open_at_horizon: bool
    realized_r: dict | None
    entry_bar_ambiguous: bool
    holding_sessions: int
    censoring_scenarios: dict | None = None
    entry_bar_weak_close: bool = False   # 2.2: entry_bar.close < candidate.pivot (annotation only)
```

- [ ] **Step 9: Run the shadow suite, see it PASS**

Run: `python -m pytest tests/research/shadow_expectancy/ -q`
Expected: PASS (entire shadow-expectancy test directory). The retired `triggered_open`/`entry_fired` entry path is gone; entry is recompute-based; `no_candidate_join` is decided in `run.py`; `insufficient_forward_depth` is wired.

- [ ] **Step 10: Commit**

```bash
git add research/harness/shadow_expectancy/collapse.py research/harness/shadow_expectancy/run.py research/harness/shadow_expectancy/scorecard.py tests/research/shadow_expectancy/test_collapse.py tests/research/shadow_expectancy/test_funnel.py tests/research/shadow_expectancy/test_run.py
git commit -m "fix(research): recompute shadow-expectancy entry from candidate.pivot over longest-chain bar source"
```

---

## Task 4: entry_bar_weak_close annotation (scorecard count + ledger column)

`entry_bar_weak_close` (`entry_bar.close < candidate.pivot`) is an **annotation only** — no behavior change. The field on `ShadowTrade` and the run-loop wiring landed in Task 3; this task adds the **scorecard count** and the **results.csv column**, plus their tests, and a summary line so the operator can discount intraday-touch entries (spec §2.2).

**Files:**
- Modify: `research/harness/shadow_expectancy/scorecard.py`
- Modify: `research/harness/shadow_expectancy/output.py`
- Modify: `research/harness/shadow_expectancy/run.py` (summary line)
- Test: `tests/research/shadow_expectancy/test_scorecard.py`, `tests/research/shadow_expectancy/test_output.py`, `tests/research/shadow_expectancy/test_run.py`

- [ ] **Step 1: Write the scorecard count test**

Add to `tests/research/shadow_expectancy/test_scorecard.py`:

```python
def test_entry_bar_weak_close_count_is_additive():
    from research.harness.shadow_expectancy.scorecard import (
        ShadowTrade,
        build_hypothesis_scorecard,
    )
    rr = {"realistic": 1.0, "favorable_reprice": 1.0}
    trades = [
        ShadowTrade(hypothesis="H", triggered=True, open_at_horizon=False, realized_r=rr,
                    entry_bar_ambiguous=False, holding_sessions=2, censoring_scenarios=None,
                    entry_bar_weak_close=True),
        ShadowTrade(hypothesis="H", triggered=True, open_at_horizon=False, realized_r=rr,
                    entry_bar_ambiguous=False, holding_sessions=2, censoring_scenarios=None,
                    entry_bar_weak_close=False),
        # a never-triggered signal never contributes a weak-close (no entry bar).
        ShadowTrade(hypothesis="H", triggered=False, open_at_horizon=False, realized_r=None,
                    entry_bar_ambiguous=False, holding_sessions=0, censoring_scenarios=None,
                    entry_bar_weak_close=False),
    ]
    card = build_hypothesis_scorecard(
        trades, sample_floor_mean=5, sample_floor_rate=5, profit_factor_floor=5)["H"]
    assert card["entry_bar_weak_close_count"] == 1
    # additive: the headline expectancy is unchanged by the flag.
    assert card["headline_realistic_closed_only"] == 1.0
```

- [ ] **Step 2: Run it, see it FAIL**

Run: `python -m pytest tests/research/shadow_expectancy/test_scorecard.py::test_entry_bar_weak_close_count_is_additive -q`
Expected: FAIL with `KeyError: 'entry_bar_weak_close_count'`.

- [ ] **Step 3: Add the count to the scorecard**

In `research/harness/shadow_expectancy/scorecard.py`, inside `build_hypothesis_scorecard`'s per-hypothesis loop, after `card["median_holding_sessions"] = …` and before `out[hyp] = card`, add:

```python
        # 2.2 (annotation only): count triggered entries that broke out intraday but closed
        # below candidate.pivot. No effect on any expectancy/win-rate computation.
        card["entry_bar_weak_close_count"] = sum(
            1 for t in triggered if t.entry_bar_weak_close)
```

(`triggered` is already `[t for t in group if t.triggered and t.realized_r is not None]`.)

- [ ] **Step 4: Run it, see it PASS**

Run: `python -m pytest tests/research/shadow_expectancy/test_scorecard.py -q`
Expected: PASS.

- [ ] **Step 5: Add the results.csv column (test first)**

Add to `tests/research/shadow_expectancy/test_output.py`:

```python
def test_results_header_includes_entry_bar_weak_close():
    from research.harness.shadow_expectancy.output import RESULTS_HEADER
    assert "entry_bar_weak_close" in RESULTS_HEADER
    assert RESULTS_HEADER[-1] == "entry_bar_weak_close"   # appended (additive)
```

Run: `python -m pytest tests/research/shadow_expectancy/test_output.py::test_results_header_includes_entry_bar_weak_close -q`
Expected: FAIL.

Then in `research/harness/shadow_expectancy/output.py` append the column to `RESULTS_HEADER`:

```python
RESULTS_HEADER = (
    "ticker", "detection_date", "run_id", "hypothesis", "bucket",
    "realistic_r", "favorable_r", "exit_reason", "open_at_horizon",
    "entry_bar_ambiguous", "entry_bar_weak_close",
)
```

Run: `python -m pytest tests/research/shadow_expectancy/test_output.py -q`
Expected: PASS.

- [ ] **Step 6: Surface the count in summary.md (test first)**

Add to `tests/research/shadow_expectancy/test_run.py`:

```python
def _seed_weak_close_winner(conn, ticker="WEAK"):
    # entry bar breaks out intraday (high 10.5 >= pivot 10.0) but closes weak (9.8 < 10.0).
    # A clean forward bar keeps it open at horizon=1 -> a TRIGGERED trade carrying weak_close.
    eval_id = insert_candidate(conn, ticker=ticker, bucket="aplus", pivot=10.0,
                               initial_stop=9.0, close=10.0)
    pr_id = insert_pipeline_run(conn, eval_id)
    det_id = insert_detection(conn, ticker=ticker, pipeline_run_id=pr_id, pivot=10.0,
                              data_asof_date="2026-05-28", detection_date="2026-05-29")
    insert_observation(conn, det_id, "2026-06-01", o=10.0, h=10.5, l=9.7, c=9.8,
                       status="triggered_open", event="entry_fired")
    insert_observation(conn, det_id, "2026-06-02", o=9.8, h=10.0, l=9.75, c=9.9,
                       status="triggered_open")
    conn.commit()


def test_entry_bar_weak_close_flagged_and_counted(tmp_path):
    conn = make_db(tmp_path)
    _seed_weak_close_winner(conn)
    out = tmp_path / "out"
    _, _, summary, manifest = run_harness(db_path=tmp_path / "t.db", output_dir=out,
                                          source="pipeline", horizon_sessions=1)
    card = json.loads(Path(manifest).read_text(encoding="utf-8"))["scorecard"]["A+ baseline"]
    assert card["entry_bar_weak_close_count"] == 1
    summary_text = Path(summary).read_text(encoding="utf-8")
    assert "entry_bar_weak_close" in summary_text
```

Run: `python -m pytest tests/research/shadow_expectancy/test_run.py::test_entry_bar_weak_close_flagged_and_counted -q`
Expected: FAIL — `summary.md` does not yet render the count.

- [ ] **Step 7: Render the count in `_summary_lines`**

In `research/harness/shadow_expectancy/run.py`, inside `_summary_lines`, in the per-hypothesis loop, after the `trigger rate … per-signal expectancy` line and before the trailing `lines.append("")`, add (ASCII only):

```python
        lines.append(f"entry_bar_weak_close (intraday-touch entries) "
                     f"= {card['entry_bar_weak_close_count']}")
```

- [ ] **Step 8: Run the shadow suite, see it PASS**

Run: `python -m pytest tests/research/shadow_expectancy/ -q`
Expected: PASS.

- [ ] **Step 9: Commit**

```bash
git add research/harness/shadow_expectancy/scorecard.py research/harness/shadow_expectancy/output.py research/harness/shadow_expectancy/run.py tests/research/shadow_expectancy/test_scorecard.py tests/research/shadow_expectancy/test_output.py tests/research/shadow_expectancy/test_run.py
git commit -m "feat(research): add entry_bar_weak_close annotation to shadow-expectancy ledger and scorecard"
```

---

## Task 5: real-emitter golden fixtures (spec §7.1 — the whole point)

The bug existed because every shipped fixture forced `detection.pivot == candidate.pivot`. These fixtures mirror the **live emitter shape**: per-pattern geometric pivots (including `0.0` for cup/dbw, real levels for vcp/flat_base/htf) that are **never** equal to `candidate.pivot`. The geometric pivots are now irrelevant to the logic — present to prove they are ignored. A shared invariant asserts no-look-ahead (`data_asof_date < observation_date`) for every forward bar.

**Files:**
- Create: `tests/research/shadow_expectancy/test_real_shapes.py`

- [ ] **Step 1: Write the no-look-ahead invariant helper + BULZ golden (never_triggered)**

Create `tests/research/shadow_expectancy/test_real_shapes.py`:

```python
from __future__ import annotations

import json
from pathlib import Path

from research.harness.shadow_expectancy.run import run_harness
from tests.research.shadow_expectancy.testkit import (
    insert_candidate,
    insert_detection,
    insert_observation,
    insert_pipeline_run,
    make_db,
)

# Per-pattern geometric pivots mirroring run 89: vcp/flat_base/htf carry a real level, cup/dbw
# carry 0.0. NONE equals candidate.pivot -- the load-bearing real-shape fact (spec 1.2 / 7.1).
_BULZ_PIVOTS = {
    "vcp": 49.89, "flat_base": 49.89, "high_tight_flag": 49.89,
    "cup_with_handle": 0.0, "double_bottom_w": 0.0,
}
# Two identical frozen bars, both VALID OHLC and BELOW candidate.pivot 56.09. The second bar is
# the real run-89 BULZ observation (2026-06-08 o=43.795 h=44.57 l=42.6 c=43.5); the earlier draft
# used (47.5, 44.57, 44.0, 44.2) which has high < open -> validate_bars would route it to
# invalid_ohlc before the recompute, masking the never_triggered assertion. Both bars satisfy
# low <= min(open,close) and high >= max(open,close).
_BULZ_BARS = [
    ("2026-06-05", 47.0, 48.16, 46.5, 47.8),
    ("2026-06-08", 43.795, 44.57, 42.6, 43.5),
]


def _assert_no_look_ahead(conn):
    # spec 4: every forward observation satisfies data_asof_date < observation_date.
    rows = conn.execute(
        "SELECT e.data_asof_date, o.observation_date "
        "FROM pattern_forward_observations o "
        "JOIN pattern_detection_events e ON e.detection_id = o.detection_id"
    ).fetchall()
    assert rows, "fixture seeded no observations"
    for data_asof_date, observation_date in rows:
        assert data_asof_date < observation_date, (
            f"look-ahead: data_asof_date={data_asof_date} >= "
            f"observation_date={observation_date}")


def _seed_bulz_run89(conn):
    # candidate.pivot 56.09; bucket watch with a proximity_20ma miss -> attributes to H2.
    eval_id = insert_candidate(
        conn, ticker="BULZ", bucket="watch", pivot=56.09, initial_stop=50.0, close=48.16,
        criteria=[("proximity_20ma", "trend_template", "fail")])
    pr_id = insert_pipeline_run(conn, eval_id)
    for pattern_class, pivot in _BULZ_PIVOTS.items():
        det_id = insert_detection(
            conn, ticker="BULZ", pipeline_run_id=pr_id, pivot=pivot,
            data_asof_date="2026-06-04", detection_date="2026-06-05",
            pattern_class=pattern_class)
        for (obs_date, o, h, low, close) in _BULZ_BARS:
            insert_observation(conn, det_id, obs_date, o=o, h=h, l=low, c=close,
                               status="pending")
    conn.commit()


def test_bulz_run89_routes_never_triggered_not_no_canonical(tmp_path):
    # Regression for the live bug: the real BULZ shape (5 detections, geometric pivots never ==
    # candidate.pivot, all watch) must route HONESTLY to never_triggered -- never the retired
    # no_canonical_detection -- because no forward high reaches candidate.pivot 56.09.
    conn = make_db(tmp_path)
    _seed_bulz_run89(conn)
    _assert_no_look_ahead(conn)
    out = tmp_path / "out"
    _, _, _, manifest = run_harness(db_path=tmp_path / "t.db", output_dir=out,
                                    source="pipeline")
    f = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]
    h2 = f["per_hypothesis"]["Near-A+ defensible: extension test"]
    assert h2["never_triggered"] == 1
    # the retired reason cannot appear anywhere.
    assert "no_canonical_detection" not in f["unattributed"]
    assert "inconsistent_trigger_state" not in f["unattributed"]
    dl = f["detection_level"]
    assert dl["total_detections"] == 5 and dl["unique_signals"] == 1
    assert dl["collapsed_duplicate_detection"] == 4   # group_size - 1
```

- [ ] **Step 2: Run it, see it PASS**

Run: `python -m pytest tests/research/shadow_expectancy/test_real_shapes.py::test_bulz_run89_routes_never_triggered_not_no_canonical -q`
Expected: PASS (the engine already routes correctly after Task 3; this fixture is the regression guard).

> If it FAILS, the most likely cause is attribution: confirm a watch candidate with a `proximity_20ma` fail maps to `"Near-A+ defensible: extension test"` (verified in `test_attribution.py::test_watch_proximity_only_maps_to_h2`). Do not change production code to satisfy the fixture — fix the fixture's criteria.

- [ ] **Step 3: Add the breakout end-to-end fixture (hand-verified R bracket)**

Append to `tests/research/shadow_expectancy/test_real_shapes.py`:

```python
def _seed_breakout_prices_through(conn):
    # candidate.pivot 50.0; geometric detection pivot 49.89 (!= candidate). bar1 high 49 < 50
    # (pre-entry, skipped); bar2 high 52 >= 50 (entry); bar3 stops out. Hand-verified bracket
    # below.
    eval_id = insert_candidate(
        conn, ticker="BRKT", bucket="watch", pivot=50.0, initial_stop=47.0, close=48.5,
        criteria=[("proximity_20ma", "trend_template", "fail")])
    pr_id = insert_pipeline_run(conn, eval_id)
    det_id = insert_detection(
        conn, ticker="BRKT", pipeline_run_id=pr_id, pivot=49.89,
        data_asof_date="2026-06-04", detection_date="2026-06-05", pattern_class="vcp")
    insert_observation(conn, det_id, "2026-06-05", o=48.0, h=49.0, l=47.0, c=48.5,
                       status="pending")
    insert_observation(conn, det_id, "2026-06-06", o=50.0, h=52.0, l=49.5, c=51.0,
                       status="triggered_open", event="entry_fired")
    insert_observation(conn, det_id, "2026-06-07", o=49.0, h=49.2, l=48.0, c=48.5,
                       status="triggered_open")
    conn.commit()


def test_breakout_prices_end_to_end(tmp_path):
    # spec 6.1: a real-shaped fixture where a forward high EXCEEDS candidate.pivot prices a trade
    # all the way through the simulator. Hand-verified:
    #   entry_fill = max(50.0, open 50.0) = 50.0; initial_stop = entry_bar.low = 49.5; rps = 0.5.
    #   forward = [bar3]; bar3.low 48.0 <= stop 49.5 -> initial_stop.
    #   realistic fill = min(stop 49.5, open 49.0) = 49.0 -> R = (49.0-50.0)/0.5 = -2.0
    #   favorable fill = 49.5 -> R = (49.5-50.0)/0.5 = -1.0
    #   entry_bar.close 51.0 >= 50.0 -> NOT weak_close.
    conn = make_db(tmp_path)
    _seed_breakout_prices_through(conn)
    _assert_no_look_ahead(conn)
    out = tmp_path / "out"
    results, _, _, manifest = run_harness(db_path=tmp_path / "t.db", output_dir=out,
                                          source="pipeline")
    f = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]
    h2 = f["per_hypothesis"]["Near-A+ defensible: extension test"]
    assert h2["closed"] == 1
    rows = Path(results).read_text(encoding="utf-8").splitlines()
    # header + one data row; verify the hand-computed bracket and the weak-close flag.
    data = rows[1].split(",")
    header = rows[0].split(",")
    rec = dict(zip(header, data))
    assert rec["exit_reason"] == "initial_stop"
    assert float(rec["realistic_r"]) == -2.0
    assert float(rec["favorable_r"]) == -1.0
    assert rec["entry_bar_weak_close"] == "False"
```

- [ ] **Step 4: Run it, see it PASS**

Run: `python -m pytest tests/research/shadow_expectancy/test_real_shapes.py::test_breakout_prices_end_to_end -q`
Expected: PASS (the hand-verified bracket matches the simulator output).

- [ ] **Step 5: Add the mixed-first-trigger fixture (not excluded; longest chain is the bar source)**

Append to `tests/research/shadow_expectancy/test_real_shapes.py`:

```python
def _seed_mixed_first_trigger(conn):
    # spec 1.3 regression: a cup detection (geometric pivot 0.0, which under the OLD observe-step
    # "triggered" on bar 1) and a vcp detection (geometric pivot 49.89, never) in the same group.
    # The vcp chain is LONGER (2 bars); the cup chain is a 1-bar strict prefix. Entry is
    # recomputed off candidate.pivot 10.0 -> the differing geometric trigger sessions are
    # irrelevant and the signal is NOT excluded.
    eval_id = insert_candidate(
        conn, ticker="MIX", bucket="watch", pivot=10.0, initial_stop=9.0, close=10.0,
        criteria=[("proximity_20ma", "trend_template", "fail")])
    pr_id = insert_pipeline_run(conn, eval_id)
    # vcp: 2-bar chain (the canonical bar source).
    vcp_id = insert_detection(
        conn, ticker="MIX", pipeline_run_id=pr_id, pivot=49.89,
        data_asof_date="2026-06-04", detection_date="2026-06-05", pattern_class="vcp")
    insert_observation(conn, vcp_id, "2026-06-05", o=10.0, h=10.5, l=9.6, c=10.2,
                       status="triggered_open", event="entry_fired")
    insert_observation(conn, vcp_id, "2026-06-06", o=10.3, h=10.8, l=10.1, c=10.6,
                       status="triggered_open")
    # cup: 1-bar strict prefix (identical bar 1), geometric pivot 0.0.
    cup_id = insert_detection(
        conn, ticker="MIX", pipeline_run_id=pr_id, pivot=0.0,
        data_asof_date="2026-06-04", detection_date="2026-06-05",
        pattern_class="cup_with_handle")
    insert_observation(conn, cup_id, "2026-06-05", o=10.0, h=10.5, l=9.6, c=10.2,
                       status="triggered_open", event="entry_fired")
    conn.commit()


def test_mixed_first_trigger_not_excluded_and_longest_chain_is_bar_source(tmp_path):
    conn = make_db(tmp_path)
    _seed_mixed_first_trigger(conn)
    _assert_no_look_ahead(conn)
    out = tmp_path / "out"
    _, _, _, manifest = run_harness(db_path=tmp_path / "t.db", output_dir=out,
                                    source="pipeline", horizon_sessions=1)
    f = json.loads(Path(manifest).read_text(encoding="utf-8"))["funnel"]
    # NOT excluded: no unattributed reason fired (the retired inconsistent_trigger_state is gone).
    assert f["unattributed"] == {} or sum(f["unattributed"].values()) == 0
    h2 = f["per_hypothesis"]["Near-A+ defensible: extension test"]
    # entry on bar1 (high 10.5 >= 10.0), one forward bar -> open at horizon=1. The 2-bar (vcp)
    # chain was the bar source; a 1-bar bar source would have been insufficient_forward_depth.
    assert h2["open_at_horizon"] == 1
    assert h2["excluded"].get("insufficient_forward_depth", 0) == 0
    dl = f["detection_level"]
    assert dl["total_detections"] == 2 and dl["unique_signals"] == 1
    assert dl["collapsed_duplicate_detection"] == 1
```

- [ ] **Step 6: Run the whole new file, see it PASS**

Run: `python -m pytest tests/research/shadow_expectancy/test_real_shapes.py -q`
Expected: PASS (all three fixtures + the no-look-ahead invariant).

- [ ] **Step 7: Commit**

```bash
git add tests/research/shadow_expectancy/test_real_shapes.py
git commit -m "test(research): add real-emitter golden fixtures for shadow-expectancy entry/join correction"
```

---

## Task 6: swing/cli.py — `_ensure_research_importable()` (the only `swing/` change)

`swing diagnose shadow-expectancy` (and the other research diagnostics) fail `ModuleNotFoundError: research` from the installed entry point because the repo root is not on `sys.path`. Add an idempotent helper that prepends the source-tree root **only when it actually contains `research/harness`** (so it cannot shadow site-packages), and call it before EVERY deferred `from research.harness …` import under the `diagnose` group. The rule is **mechanical (grep-enforced)**, not a hand-list (spec §5.1).

**Files:**
- Modify: `swing/cli.py`
- Test: `tests/research/shadow_expectancy/test_cli.py`

- [ ] **Step 1: Write the importability + idempotency + grep tests**

Add to `tests/research/shadow_expectancy/test_cli.py`:

```python
def test_ensure_research_importable_is_idempotent_and_root_guarded(monkeypatch):
    import sys as _sys
    from pathlib import Path as _Path

    from swing.cli import _ensure_research_importable

    # A path entry resolves to a research-root if (its dir, or cwd for a falsey "" entry) contains
    # research/harness. Falsey entries ("" = cwd) MUST be treated as cwd: under pytest from the
    # repo root, "" resolves to a research-root and would otherwise mask a non-insert (Codex R3-#1).
    def _is_research_root(p):
        base = _Path(p) if p else _Path.cwd()
        return (base / "research" / "harness").is_dir()

    pruned = [p for p in _sys.path if not _is_research_root(p)]
    monkeypatch.setattr(_sys, "path", pruned)
    assert not any(_is_research_root(p) for p in _sys.path), \
        "precondition: pruning must remove every research-root (incl. cwd via an empty entry)"
    _ensure_research_importable()
    # DIRECT proof the helper inserted a NON-EMPTY ABSOLUTE source root at sys.path[0] containing
    # research/harness. A bare "" (cwd) does NOT count. Do NOT use importlib.import_module as the
    # proof: test_run.py imports run_harness at module load, so the module is already cached and
    # importlib would false-pass off sys.modules even if the insert failed (Codex R2-#1, R3-#1).
    head = _sys.path[0]
    assert head and _Path(head).is_absolute() and (_Path(head) / "research" / "harness").is_dir()
    before = list(_sys.path)
    _ensure_research_importable()   # idempotent: no duplicate insert.
    assert _sys.path == before


def test_no_unguarded_research_harness_import_under_diagnose():
    # spec 5.1 (Codex R1-#5): the rule is MECHANICAL -- EVERY `from research.harness` import site
    # under the diagnose group must be preceded (within its enclosing function) by a
    # _ensure_research_importable() call. This grep guard fails if any new un-guarded site lands.
    from pathlib import Path

    import swing.cli as cli_mod

    src = Path(cli_mod.__file__).read_text(encoding="utf-8").splitlines()
    import_lines = [i for i, ln in enumerate(src) if "from research.harness" in ln]
    assert import_lines, "expected at least one deferred research.harness import in cli.py"
    for i in import_lines:
        # scan upward within the same function for a _ensure_research_importable() call. A call on
        # a COMMENTED line does not count (skip lines starting with '#'); stop at the enclosing
        # top-level command function header (a `def ` not indented two levels in).
        guarded = False
        for j in range(i - 1, -1, -1):
            line = src[j]
            stripped = line.lstrip()
            if stripped.startswith("#"):
                continue
            if "_ensure_research_importable()" in line:
                guarded = True
                break
            if stripped.startswith("def ") and not line.startswith("    " * 2):
                break   # hit the enclosing top-level/command function header
        assert guarded, (
            f"un-guarded `from research.harness` at cli.py line {i + 1}: "
            f"{src[i].strip()!r} -- add _ensure_research_importable() before it")
```

- [ ] **Step 2: Run the tests, see them FAIL**

Run: `python -m pytest tests/research/shadow_expectancy/test_cli.py -q`
Expected: FAIL — `_ensure_research_importable` does not exist; the grep test finds un-guarded import sites.

- [ ] **Step 3: Add the helper to swing/cli.py**

In `swing/cli.py`, immediately after `_validate_diagnose_db_path` (ends ~line 4796), add:

```python
def _ensure_research_importable() -> None:
    """Prepend the source-tree root to sys.path so deferred `research.harness.*` imports resolve
    from the `swing` entry point (research/ is not an installed package). Idempotent; verifies
    the located root actually contains research/harness before inserting (R2-#2), so it is a safe
    no-op when the source tree is absent rather than silently shadowing site-packages."""
    import sys
    from pathlib import Path
    here = Path(__file__).resolve()
    for root in here.parents:
        if (root / "research" / "harness").is_dir():
            if str(root) not in sys.path:
                sys.path.insert(0, str(root))
            return
    # No source tree on disk (true non-editable install): nothing to add; the deferred import
    # will raise its normal ModuleNotFoundError, which is the honest outcome.
```

- [ ] **Step 4: Add the helper call before every diagnose-group `from research.harness` import**

Insert a `_ensure_research_importable()` line immediately before EACH of the deferred imports. There are eight sites (the two pattern-cohort imports at 5028/5032 are consecutive, so one call before the first covers both — but to satisfy the per-site grep guard, place the call right before the import statement / consecutive import block in each command body). Concretely, before each of these lines (current numbers; they will shift as you edit top-down — edit bottom-up or re-locate by content):

- `from research.harness.aplus_sensitivity.run import run_harness` (`aplus-sensitivity`)
- `from research.harness.aplus_v2_ohlcv_evaluator.run import run_harness` (`aplus-sensitivity-v2`)
- `from research.harness.minervini_exemplar_recall.run import run_harness` (`minervini-recall`)
- `from research.harness.minervini_primary_base_recall.run import run_harness` (`primary-base-recall`)
- the `from research.harness.pattern_cohort_evaluator.exceptions import (…)` + `from research.harness.pattern_cohort_evaluator.run import run_harness` pair (`pattern-cohort`) — one call before the pair
- `from research.harness.shadow_expectancy.run import run_harness` (`shadow-expectancy`)
- `from research.harness.double_bottom_w_backtest.run import main as backtest_main` (`double-bottom-w-backtest`)
- `from research.harness.w_bottom_ruleset_comparison.run import main as backtest_main` (`w-bottom-ruleset-comparison`)

Example (the shadow-expectancy site, cli.py ~5083-5084):

```python
    _validate_diagnose_db_path(db_path)
    _ensure_research_importable()
    from research.harness.shadow_expectancy.run import run_harness  # deferred import
```

Apply the same one-line insertion before each of the other sites. The grep guard in Step 1 enforces completeness — if you miss one, it fails.

- [ ] **Step 5: Run the tests, see them PASS**

Run: `python -m pytest tests/research/shadow_expectancy/test_cli.py -q`
Expected: PASS (importability, idempotency, root-guard, and the grep guard).

- [ ] **Step 6: Commit**

```bash
git add swing/cli.py tests/research/shadow_expectancy/test_cli.py
git commit -m "fix(cli): make research diagnostics importable from the swing entry point"
```

---

## Task 7: full-suite verification + L2-lock + V1 limitation note

Confirm the whole correction is green end-to-end, the L2-lock invariants hold (no forbidden imports, harness still read-only), and the no-close-confirmation V1 limitation is recorded.

**Files:**
- Modify: `research/harness/shadow_expectancy/run.py` (docstring note only)
- Test: (run-only; no new test code)

- [ ] **Step 1: Record the no-close-confirmation V1 limitation (spec §2.2 / §7.5)**

In `research/harness/shadow_expectancy/run.py`, extend `run_harness`'s docstring (or add a module-level comment above `run_harness`) with an ASCII-only note:

```python
    # V1 LIMITATION (spec 2.2 / 7.5): entry uses a plain threshold high >= candidate.pivot with
    # NO close-confirmation gate. This admits intraday-touch entries (a bar that tips the pivot
    # then closes weak still enters); such entries are flagged via entry_bar_weak_close
    # (annotation only) so the operator can discount the headline. Candidate-frame close
    # confirmation is a possible V2 hardening. The geometric structural_low is deliberately NOT
    # reintroduced (it is the per-pattern geometry this correction abandons).
```

- [ ] **Step 2: Run the L2-lock + the full shadow suite**

Run: `python -m pytest tests/research/shadow_expectancy/ -q`
Expected: PASS, including `test_l2_lock.py` (no forbidden imports; `collapse.py` no longer imports `PRICE_TICK_DECIMALS`, but that is not a forbidden token).

- [ ] **Step 3: Run the full fast suite on the working head**

Run: `python -m pytest -m "not slow" -q`
Expected: PASS. Read the ACTUAL pytest summary line; do not carry forward a prior count. (Baseline was ~7504 on `main`; the net test delta from this plan is a handful of added/removed cases — trust the live output.) Also run `ruff check swing/ research/harness/shadow_expectancy/` and confirm clean.

- [ ] **Step 4: Commit + verify trailers**

```bash
git add research/harness/shadow_expectancy/run.py
git commit -m "docs(research): record shadow-expectancy V1 no-close-confirmation entry limitation"
git log -1 --format='%(trailers)'
```

Expected: `git log -1 --format='%(trailers)'` prints `[]` (no Co-Authored-By footer). Spot-check the last several commit messages for the same.

---

## Self-review (run against the spec — performed during plan authoring)

**1. Spec coverage (§5/§5.1/§7 vs tasks):**

| Spec item | Task |
|---|---|
| `collapse.py` drop `candidate_pivot`; longest-chain tie-low-id; strict date-prefix gate; delete `no_canonical_detection`/`inconsistent_trigger_state` branches; return canonical bar series (§5, §2.3) | Task 3 |
| `run.py` entry recompute `first high >= candidate.pivot`; `forward_bars=bars[entry_idx+1:]`; `None`→`never_triggered`; `entry_idx==len-1`→`insufficient_forward_depth` (no `simulate`); `entry_bar_weak_close`; `candidate is None`→`no_candidate_join`; order collapse→join→attribute→validate→recompute→simulate (§5, §2.1, §2.2) | Tasks 3, 4 |
| `validate.py` `no_candidate_pivot` for pivot fault; `invalid_ohlc` for bars (§5, §3.2) | Task 1 |
| `constants.py` vocab: remove two, add `no_candidate_pivot` (§5, §3.4/§3.5) | Task 2 |
| `funnel.py` consumes vocab, no structural change (§5) | Tasks 2-3 (tests only) |
| `scorecard.py`/`output.py` additive `entry_bar_weak_close` (§5) | Task 4 |
| `simulator.py`/`bracket.py`/`attribution.py`/`exceptions.py` UNCHANGED; `simulate` never empty `forward_bars` (§5) | Enforced by Task 3 guard + Task 3 Step 6 test |
| `swing/cli.py` `_ensure_research_importable` + grep-enforced call sites (§5.1) | Task 6 |
| Fixtures forbid `detection.pivot==candidate.pivot`; BULZ golden → `never_triggered`; breakout end-to-end; mixed-first-trigger; `data_asof_date < observation_date` (§7.1) | Task 5 |
| Delete pivot-match / `no_canonical_detection` / `inconsistent_trigger_state` collapse tests (§7.2) | Task 3 Step 1 |
| Entry-recompute tests incl. zero-forward-depth + simulate-not-called + weak-close (§7.3) | Tasks 3, 4 |
| `no_candidate_pivot` per-hyp distinct from `invalid_ohlc`; grep test (§7.4) | Tasks 1, 2, 6 |
| Preserved sim/bracket/scorecard/censoring tests stay green; L2-lock + banned-import grep green; V1 limitation note (§7.5) | Task 7 |

**2. Placeholder scan:** every code step contains complete, runnable code; no TBD/TODO/"handle edge cases".

**3. Type consistency:** `_DetView(detection_id, bars)` matches the collapse view (`detection_id`, `bars`); `CollapseResult(canonical, collapsed_ids, exclusion_reason)` unchanged in shape; `ShadowTrade.entry_bar_weak_close: bool = False` is referenced consistently in `run.py` emission, scorecard count, and tests; `RESULTS_HEADER` column name `entry_bar_weak_close` matches the results-row key; reason strings (`no_candidate_pivot`, `insufficient_forward_depth`, `inconsistent_detection_series`, `no_candidate_join`) match the constants tuples after Task 2.

**Note on green-between-commits:** Task 2 changes vocab while `collapse.py` still holds the old signature; this is safe because no fixture drives a retired-reason branch (all seeds match pivots, so `collapse` never returns `no_canonical_detection`/`inconsistent_trigger_state` at runtime) and the consuming assertions are updated in the same task. Task 3 is the only task that changes `collapse.py` + `run.py` together (the signature coupling is atomic); its Step 8 note pulls the one-line `ShadowTrade` field forward so the run-loop rewrite stays self-consistent. Every task ends with its targeted tests green; Task 7 confirms the full fast suite.

## LOCKS honored
- Surgical: only the §5/§5.1 surface + affected tests/fixtures. `simulator.py`/`bracket.py` math, censoring/scorecard expectancy/Wilson math, and the funnel two-level structure untouched.
- L2 LOCK: the only `swing/` change is `swing/cli.py` (`_ensure_research_importable` + call sites). No new `swing/` files.
- No schema change (v25; harness stays `mode=ro`).
- No new dependency / no forbidden imports (`test_l2_lock.py` stays green).
- Conventional commits; no Claude co-author footer; no `--no-verify`; no amend; trailers `[]` verified in Task 7.
