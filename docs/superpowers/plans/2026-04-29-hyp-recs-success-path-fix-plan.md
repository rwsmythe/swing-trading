# Hyp-recs Success-Path Fix Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the two production-blocking gaps from the just-shipped hyp-recs trade-prep expansion (commits `5bd496d → a29a592`): R1 Major 1 (entry_post success-path on origin=hyp-recs leaves the open-positions row inside hyp-recs `<tbody>` and never refreshes the hyp-recs section) and R1 Major 2 (anchor divergence between `build_hyp_recs_section` and `build_dashboard` via two non-shared queries).

**Architecture:** R1 M2 is closed by extending the existing `latest_evaluation_run_id(conn)` helper in `swing/web/view_models/dashboard.py` (add `id DESC` tiebreaker) and refactoring `build_hyp_recs_section` to consume it — eliminating the second pipeline_runs query and inheriting the 2-step pipeline-bound → standalone-eval fallback. R1 M1 is closed via a new third OOB swap (`#hypothesis-recommendations`) appended to entry_post's success-path response when `origin == "hyp-recs"`. The OOB swap is rendered through the existing `partials/hypothesis_recommendations.html.j2` partial (the same `{% include %}` chain `/hyp-recs/refresh` and the full-page render use — per CLAUDE.md "HTMX OOB-swap partial drift" gotcha). Two small enabling changes ship first: (a) `build_hyp_recs_section` gains an `exclude_tickers` kwarg so the post-trade rebuild structurally excludes the just-traded ticker (the matcher operates on candidates, not trades — so without this kwarg the just-traded ticker would still appear in the rebuilt section); (b) the partial gains an `oob` kwarg so the section element with id `#hypothesis-recommendations` is always emitted under OOB (HTMX needs the target to exist even when the rebuilt section is empty, e.g. operator just traded their only remaining hyp-rec).

**Tech Stack:** Python 3.14, FastAPI, Jinja2, HTMX 2.x, SQLite, pytest.

---

## Pre-flight context

- **Test baseline pinned:** 1294 fast tests passed, 1 skipped, 8 deselected (`python -m pytest -m "not slow" -q`) at HEAD `3c43757`. Trust pytest output, not pinned counts (CLAUDE.md "Test-count drift in plan docs").
- **Branch:** `main` (project convention; no feature branches).
- **Commits:** conventional, NO Claude co-author footer, NO `--no-verify`, flat `Task <N>` numbering.
- **Per-task observable-verification step:** `git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task <N>'` after commit. Aliasing against the just-shipped hyp-recs trade-prep expansion's `Task 1..9` commits is **expected** — the verification step confirms ≥1 hit; the operator visually disambiguates by topic. (Per orchestrator-context "binding conventions" + just-shipped precedent.)
- **Locked decisions (per dispatch brief §2; do not re-litigate):**
  1. R1 M1 fix uses option (a) — symmetric OOB-refresh of `#hypothesis-recommendations` from entry_post.
  2. R1 M2 fix factors a shared helper consumed by both call sites; the helper preserves the 2-step pipeline-bound → standalone-eval fallback and adds `id DESC` tiebreaker. Resolved design call: the helper is the existing `latest_evaluation_run_id(conn) -> int | None` (it already returns the right shape for both consumers; both want `evaluation_run_id` for binding candidates). `build_hyp_recs_section`'s current inline query consumes only `evaluation_run_id` from its `(id, evaluation_run_id)` tuple, so swapping to the helper is a strict refactor on the consumer side.
- **Source-file shape (verified at HEAD `3c43757`):**
  - `swing/web/view_models/dashboard.py:70-101` — `latest_evaluation_run_id(conn)`. Pipeline-bound branch lacks `id DESC` tiebreaker. Standalone-eval fallback present.
  - `swing/web/view_models/dashboard.py:300-372` — `build_hyp_recs_section`. Inline query at lines 327-335 selects `(id, evaluation_run_id)` from `pipeline_runs WHERE state='complete' ORDER BY finished_ts DESC, id DESC LIMIT 1`. Only `evaluation_run_id` (`pipe_row[1]`) is consumed; `id` (`pipe_row[0]`) is never used. No standalone-eval fallback.
  - `swing/web/templates/partials/hypothesis_recommendations.html.j2` — wraps content with `<section id="hypothesis-recommendations">`; `{% if vm.active_recommendations %}` guard means an empty-rec section emits NOTHING (no element). Used by `/hyp-recs/refresh` (full-section render, no OOB attribute) and the full-page render via `{% include %}`.
  - `swing/web/routes/trades.py:228-608` — `entry_post`. Success-path response (lines 587-608) returns: primary row + `#status-strip` OOB + `#watchlist-top5` OOB. Origin field already coerced via `_coerce_origin` and threaded through every error-path re-render (Task 8 from prior dispatch).
  - `swing/recommendations/hypothesis.py:220-336` — `match_candidate_to_hypotheses` and `prioritize_recommendations` operate on `Candidate` rows + the registry; **neither filters by open-position trade state.** Hence Task 3's `exclude_tickers` kwarg is required to make Task 4's discriminating "just-traded ticker absent" test pass.

---

## File map

**Modify:**

- `swing/web/view_models/dashboard.py` — Tasks 1–3 (helper tiebreaker, refactor consumer, add `exclude_tickers` kwarg).
- `swing/web/templates/partials/hypothesis_recommendations.html.j2` — Task 4 (add `oob` kwarg branching).
- `swing/web/routes/trades.py` — Task 5 (wire OOB swap into entry_post success path).

**Test files modified:**

- `tests/web/view_models/test_dashboard_recommendations.py` — extend existing tests for Tasks 1–3 (verify file exists; if not, the closest match is the file that exercises `latest_evaluation_run_id` and `build_hyp_recs_section`; use `Glob` to confirm before writing).
- `tests/web/routes/test_recommendations_routes.py` or equivalent — Tasks 2–4 cover the `/hyp-recs/refresh` route's behavior under the refactored helper.
- `tests/web/templates/` (or `tests/web/view_models/test_hypothesis_recommendations_partial.py`) — Task 4 partial-render tests.
- `tests/web/routes/test_trades_entry.py` (or the file that owns existing entry_post POST tests) — Task 5 OOB-swap integration tests.

**Verification before writing each test:** Use `Glob` to confirm the canonical test-file path. The test layout mirrors `swing/`; use the existing test file for the surface under test rather than creating a new one when one already exists.

---

## Task ordering rationale

Per dispatch brief §4 acceptance criterion 6: R1 M2 helper extraction lands FIRST so subsequent R1 M1 tasks can rely on the refactored helper if needed. Within R1 M2: tiebreaker (Task 1) lands before refactor (Task 2) because Task 2's behavior-equivalence test for `build_hyp_recs_section` against `build_dashboard` under tied-`finished_ts` is only meaningful once the helper is deterministic. Tasks 3 and 4 are independent enabling changes for Task 5 (R1 M1's integration). Task 5 lands last and is the only task that actually wires the new OOB swap into the response.

Sequential single-subagent execution; no parallel-collision risk (per dispatch brief §4 acceptance criterion 3).

---

## Task 1: Add `id DESC` tiebreaker to `latest_evaluation_run_id`

**Goal:** Strict refinement of `latest_evaluation_run_id`'s pipeline-bound branch — adds `id DESC` as a deterministic secondary sort key so two `pipeline_runs` rows with identical `finished_ts` resolve to the higher-id row. Closes Codex R1 M2's "tied `finished_ts` could diverge" concern at the helper level. Existing callers that don't tie on `finished_ts` see no behavior change.

**Files:**
- Modify: `swing/web/view_models/dashboard.py:88-92` — pipeline-bound query in `latest_evaluation_run_id`.
- Test: existing test file for `latest_evaluation_run_id` (locate with `Glob "tests/web/**/test_*dashboard*.py"` or `Grep -rn "latest_evaluation_run_id"` under `tests/`); if no dedicated file exists, use the closest existing file that already imports `latest_evaluation_run_id` for fixture reuse.

**Discriminating-test sanity check:** The new test would fail if the implementation never adds `id DESC` to the query — under tied `finished_ts`, SQLite's row order is unspecified and the original query may return either row. The test pins two `pipeline_runs` rows to the SAME `finished_ts` and asserts the helper returns the row with the HIGHER `id`. Without the `id DESC` clause, this assertion is non-deterministic (passes intermittently); with the clause, it passes every run.

- [ ] **Step 1: Locate the existing test file**

```bash
# Find the canonical test file for latest_evaluation_run_id.
git ls-files tests/ | xargs grep -l "latest_evaluation_run_id" 2>/dev/null || echo "no existing test"
```

Expected: a single test file path under `tests/web/view_models/` (the `dashboard.py` view-model tests). If no file exists, create `tests/web/view_models/test_latest_evaluation_run_id.py`.

- [ ] **Step 2: Write the failing test**

Open the located test file (or create the new one). Add:

```python
import sqlite3

import pytest

from swing.data.db import connect
from swing.web.view_models.dashboard import latest_evaluation_run_id


@pytest.fixture
def conn_with_two_pipeline_runs_same_finished_ts(tmp_path):
    """Two complete pipeline_runs rows with identical finished_ts. The
    higher-id row also has the higher evaluation_run_id; the helper must
    deterministically resolve to that one (Task 1: id DESC tiebreaker).
    """
    db_path = tmp_path / "swing.db"
    conn = connect(db_path)
    # Two evaluation_runs (FK targets).
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, action_session_date) "
        "VALUES (10, '2026-04-29T09:00:00', '2026-04-28', '2026-04-29')"
    )
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, action_session_date) "
        "VALUES (11, '2026-04-29T09:01:00', '2026-04-28', '2026-04-29')"
    )
    # Two pipeline_runs rows, same finished_ts, increasing ids.
    conn.execute(
        "INSERT INTO pipeline_runs "
        "(id, started_ts, finished_ts, action_session_date, state, evaluation_run_id) "
        "VALUES (100, '2026-04-29T08:55:00', '2026-04-29T09:00:00', '2026-04-29', "
        "'complete', 10)"
    )
    conn.execute(
        "INSERT INTO pipeline_runs "
        "(id, started_ts, finished_ts, action_session_date, state, evaluation_run_id) "
        "VALUES (101, '2026-04-29T08:55:01', '2026-04-29T09:00:00', '2026-04-29', "
        "'complete', 11)"
    )
    conn.commit()
    yield conn
    conn.close()


def test_latest_evaluation_run_id_id_desc_tiebreaker(
    conn_with_two_pipeline_runs_same_finished_ts,
):
    """Tied finished_ts → deterministic resolution to higher-id row.

    Discriminating: pre-fix, the query lacks `id DESC` and SQLite is free
    to return either row. The fixture inserts the two rows in id-ascending
    order; without the tiebreaker, plain `finished_ts DESC` typically
    leaves the lower-id row last-inserted-wins-or-loses depending on
    SQLite's internal ordering for tied keys (NOT guaranteed). With the
    `id DESC` tiebreaker, the helper deterministically returns
    evaluation_run_id=11 (paired with pipeline_run id=101).
    """
    result = latest_evaluation_run_id(
        conn_with_two_pipeline_runs_same_finished_ts,
    )
    assert result == 11
```

Note: the schema columns above are the minimum needed; if the `evaluation_runs` or `pipeline_runs` tables require additional NOT NULL columns at HEAD, extend the inserts accordingly. Run the existing `tests/conftest.py` fixtures by importing the canonical seed helper if one exists (search via `git ls-files tests/ | xargs grep -l "INSERT INTO pipeline_runs"`).

- [ ] **Step 3: Run test to verify it fails**

Run: `python -m pytest tests/web/view_models/<file>.py::test_latest_evaluation_run_id_id_desc_tiebreaker -v`

Expected: PASS or FAIL non-deterministically depending on SQLite's tied-key ordering. If it passes by coincidence, swap the insert order of the two pipeline_runs rows (insert id=101 first, then id=100) to force a pre-fix failure. The test must be DETERMINISTICALLY failing pre-fix. Adjust insert order until pre-fix is FAIL.

- [ ] **Step 4: Implement `id DESC` tiebreaker**

Edit `swing/web/view_models/dashboard.py:88-92`:

Before:
```python
    pipeline_eval_row = conn.execute(
        """SELECT evaluation_run_id FROM pipeline_runs
           WHERE state = 'complete'
           ORDER BY finished_ts DESC LIMIT 1"""
    ).fetchone()
```

After:
```python
    # Codex R1 M2 follow-up (Task 1): `id DESC` tiebreaker defends against
    # second-precision `finished_ts` collisions on rapid runs. Mirrors the
    # tiebreaker already on `chart_scope.latest_completed_pipeline_run`.
    pipeline_eval_row = conn.execute(
        """SELECT evaluation_run_id FROM pipeline_runs
           WHERE state = 'complete'
           ORDER BY finished_ts DESC, id DESC LIMIT 1"""
    ).fetchone()
```

- [ ] **Step 5: Run test to verify it passes**

Run: `python -m pytest tests/web/view_models/<file>.py::test_latest_evaluation_run_id_id_desc_tiebreaker -v`

Expected: PASS.

- [ ] **Step 6: Run the full fast suite to verify no regressions**

Run: `python -m pytest -m "not slow" -q 2>&1 | tail -5`

Expected: 1295 passed (1294 baseline + 1 new test), 1 skipped, 8 deselected.

- [ ] **Step 7: Commit**

```bash
git add swing/web/view_models/dashboard.py tests/web/view_models/<file>.py
git commit -m "feat(web): Task 1 — id DESC tiebreaker on latest_evaluation_run_id"
```

- [ ] **Step 8: Observable-verification**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 1' | head -5
```

Expected: at least one line ending in `Task 1 — id DESC tiebreaker on latest_evaluation_run_id`. (Aliases against the prior dispatch's `Task 1 — CC pivot bug fix` are expected; that's the documented cross-plan grep aliasing per orchestrator-context.)

---

## Task 2: Refactor `build_hyp_recs_section` to consume `latest_evaluation_run_id`

**Goal:** Eliminate the inline `pipeline_runs` query in `build_hyp_recs_section` and route through the shared `latest_evaluation_run_id(conn)` helper. This closes Codex R1 M2's anchor-divergence drift in two ways: (1) `build_hyp_recs_section` and `build_dashboard` now resolve the SAME `evaluation_run_id` under tied `finished_ts` (Task 1's `id DESC` tiebreaker propagates); (2) `build_hyp_recs_section` inherits the 2-step pipeline-bound → standalone-eval fallback, so a standalone-eval-only state (`evaluation_runs` row but no completed `pipeline_runs`) no longer makes `/hyp-recs/refresh` return an empty section while `/` renders hyp-recs from the standalone eval.

**Files:**
- Modify: `swing/web/view_models/dashboard.py:300-372` — `build_hyp_recs_section`. Replace the inline query (lines 327-335) with a call to `latest_evaluation_run_id(conn)`.
- Test: same file as Task 1 (or `tests/web/routes/test_recommendations_routes.py` for the route-level integration test).

**Discriminating-test sanity check:** The standalone-eval-only fallback test would fail if the refactor never lands — pre-refactor, `build_hyp_recs_section` returns `HypRecsSectionVM(active_recommendations=())` under no-pipeline state because the inline `pipeline_runs` query returns None. The test seeds an `evaluation_runs` row but NO `pipeline_runs` row, plus a candidate matching one of the active hypotheses, and asserts the returned section is non-empty (contains the candidate's ticker). Pre-refactor: empty tuple → assertion fails. Post-refactor: `latest_evaluation_run_id` falls back to the standalone eval → matcher runs → ticker is present.

- [ ] **Step 1: Write the failing test**

```python
def test_build_hyp_recs_section_falls_back_to_standalone_eval(tmp_path, monkeypatch):
    """Standalone-eval-only state (no completed pipeline_runs) — section
    should now render via the latest_evaluation_run_id 2-step fallback.

    Discriminating: pre-refactor, the inline query in build_hyp_recs_section
    is pipeline-bound only and returns None under this state, so the
    section is empty. Post-refactor, the helper falls back to the
    standalone eval and the matcher runs against its candidates.
    """
    from swing.config import Config
    from swing.data.db import connect
    from swing.web.view_models.dashboard import build_hyp_recs_section
    from swing.web.price_cache import PriceCache

    db_path = tmp_path / "swing.db"
    conn = connect(db_path)
    # Standalone evaluation_run (no associated pipeline_runs row).
    conn.execute(
        "INSERT INTO evaluation_runs (id, run_ts, data_asof_date, action_session_date) "
        "VALUES (50, '2026-04-29T09:00:00', '2026-04-28', '2026-04-29')"
    )
    # Insert one A+ candidate that matches the H_APLUS_BASELINE hypothesis.
    # The exact INSERT shape depends on the candidates schema at HEAD; use
    # the closest existing fixture builder. Sentinel ticker 'TESTAPLUS'
    # avoids collision with the CC-pivot sentinel pair (FOO/BAR sized at
    # $24.13/$26.98 in the prior dispatch). See dispatch brief §3.F.
    _seed_aplus_candidate(conn, eval_run_id=50, ticker="TESTAPLUS")
    # Active hypothesis registry seeding.
    _seed_active_hypothesis(conn, name="A+ baseline")
    conn.commit()
    conn.close()

    cfg = _build_test_config(db_path=db_path, starting_equity=10_000.0)
    cache = PriceCache(...)  # use existing test fixture
    section_vm = build_hyp_recs_section(cfg=cfg, cache=cache, executor=None)
    tickers = [r.ticker for r in section_vm.active_recommendations]
    assert "TESTAPLUS" in tickers, (
        "Standalone-eval-only state should fall back to the latest "
        "evaluation_runs row and surface its candidates as recommendations."
    )
```

Note: replace `_seed_aplus_candidate`, `_seed_active_hypothesis`, and `_build_test_config` with the canonical helpers in your test conftest. The CC-pivot sentinel pair from the prior dispatch (entry_target=$24.13, candidates.pivot=$26.98) is reserved for sentinel reuse; pick a distinct ticker (`TESTAPLUS` above) so test setup cannot accidentally match a default fixture row.

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/web/view_models/<file>.py::test_build_hyp_recs_section_falls_back_to_standalone_eval -v`

Expected: FAIL — `assert "TESTAPLUS" in tickers` fails because pre-refactor `build_hyp_recs_section` returns an empty tuple under no-pipeline state.

- [ ] **Step 3: Implement the refactor**

Edit `swing/web/view_models/dashboard.py:322-356` (the `with conn:` block in `build_hyp_recs_section`). Replace the inline pipe_row query and its conditional with a call to `latest_evaluation_run_id`.

Before (lines 322-335):
```python
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Anchor on the latest completed pipeline run's evaluation
            # — same anchor build_dashboard uses for candidates_by_ticker.
            pipe_row = conn.execute(
                """SELECT id, evaluation_run_id FROM pipeline_runs
                   WHERE state='complete'
                   ORDER BY finished_ts DESC, id DESC LIMIT 1"""
            ).fetchone()
            if pipe_row is None or pipe_row[1] is None:
                # No completed pipeline yet — return empty section.
                return HypRecsSectionVM(active_recommendations=())
            eval_id = pipe_row[1]
```

After:
```python
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            # Task 2 (R1 M2): consume the shared `latest_evaluation_run_id`
            # helper so the hyp-recs section anchors on the same eval that
            # `build_dashboard` binds candidates_by_ticker to. Closes the
            # divergence between `/` and `/hyp-recs/refresh` under tied
            # `finished_ts` (helper has `id DESC` tiebreaker per Task 1)
            # and under standalone-eval-only state (helper falls back to
            # the most-recent `evaluation_runs` row when no completed
            # pipeline_runs exist).
            eval_id = latest_evaluation_run_id(conn)
            if eval_id is None:
                # No eval at all (fresh install, no pipeline + no
                # standalone eval) — empty section.
                return HypRecsSectionVM(active_recommendations=())
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/web/view_models/<file>.py::test_build_hyp_recs_section_falls_back_to_standalone_eval -v`

Expected: PASS.

- [ ] **Step 5: Run the full fast suite to verify no regressions**

Run: `python -m pytest -m "not slow" -q 2>&1 | tail -5`

Expected: 1296 passed (1294 baseline + Task 1 + Task 2), 1 skipped, 8 deselected.

If a pre-existing test for `build_hyp_recs_section` asserted empty-on-no-pipeline state (i.e. the negative behavior we just changed), it may now FAIL. Inspect the failure: if the prior assertion was the "pre-fix bug behavior" frozen as a regression test, the test needs updating to assert the new fallback behavior. Surface in the commit message.

- [ ] **Step 6: Commit**

```bash
git add swing/web/view_models/dashboard.py tests/web/view_models/<file>.py
git commit -m "refactor(web): Task 2 — build_hyp_recs_section consumes latest_evaluation_run_id"
```

- [ ] **Step 7: Observable-verification**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 2' | head -5
```

Expected: at least one line ending in `Task 2 — build_hyp_recs_section consumes latest_evaluation_run_id`.

---

## Task 3: Add `exclude_tickers` kwarg to `build_hyp_recs_section`

**Goal:** Allow the post-trade rebuild path (Task 5) to structurally exclude tickers with currently-open positions — most importantly the just-traded ticker. The matcher (`match_candidate_to_hypotheses`) and prioritizer (`prioritize_recommendations`) operate on `Candidate` rows and the registry; neither filters by trade state. Without this kwarg, an OOB-rebuilt section would still surface the just-traded ticker (its `Candidate` row from the latest pipeline run is unchanged by an entry; the bucket field reflects pre-entry state until the next pipeline run reclassifies it as `excluded` with `notes='open position'`). The kwarg defaults to `()` so `/hyp-recs/refresh` and any other existing caller see no behavior change.

**Files:**
- Modify: `swing/web/view_models/dashboard.py:300-372` — `build_hyp_recs_section`. Add `exclude_tickers: Iterable[str] = ()` to the signature; filter both `candidates` (so prices/recommendations skip the excluded set) and the final `top_recommendations` list (defense-in-depth — guarantees no excluded ticker leaks through even if a future matcher path bypasses the candidate filter).
- Test: same file as Tasks 1–2.

**Discriminating-test sanity check:** Test asserts that when `exclude_tickers=("TESTAPLUS",)` is passed and the seeded candidate set contains `TESTAPLUS`, the returned section's tickers do NOT include `TESTAPLUS`. Pre-implementation, the kwarg doesn't exist → call fails with TypeError. After signature added but before filter wiring, kwarg accepted silently but filter never applied → ticker still present → assertion fails. Both pre-states fail, post-state passes — discriminating.

- [ ] **Step 1: Write the failing test**

```python
def test_build_hyp_recs_section_excludes_specified_tickers(tmp_path):
    """exclude_tickers kwarg structurally suppresses listed tickers from
    the recommendations output, even when their candidate row is still
    in the latest evaluation run.

    Discriminating: pre-Task-3, the kwarg doesn't exist (TypeError); a
    pure signature-only addition without filter wiring would pass the
    call but still surface TESTAPLUS in the recommendations.
    """
    from swing.web.price_cache import PriceCache
    from swing.web.view_models.dashboard import build_hyp_recs_section

    db_path = tmp_path / "swing.db"
    # Seed a completed pipeline_run + evaluation_run + matching candidate
    # (use the canonical fixture-builder pattern from Task 2).
    _seed_completed_pipeline_with_aplus_candidate(
        db_path, ticker="TESTAPLUS", pipeline_run_id=200, eval_run_id=51,
    )
    cfg = _build_test_config(db_path=db_path, starting_equity=10_000.0)
    cache = PriceCache(...)  # existing fixture

    # Sanity: without exclusion, TESTAPLUS appears.
    sec_baseline = build_hyp_recs_section(cfg=cfg, cache=cache, executor=None)
    baseline_tickers = [r.ticker for r in sec_baseline.active_recommendations]
    assert "TESTAPLUS" in baseline_tickers

    # With exclusion, TESTAPLUS is suppressed.
    sec_filtered = build_hyp_recs_section(
        cfg=cfg, cache=cache, executor=None,
        exclude_tickers=("TESTAPLUS",),
    )
    filtered_tickers = [r.ticker for r in sec_filtered.active_recommendations]
    assert "TESTAPLUS" not in filtered_tickers, (
        "exclude_tickers must structurally suppress the listed tickers, "
        "even when their candidate row is still present in the eval."
    )
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/web/view_models/<file>.py::test_build_hyp_recs_section_excludes_specified_tickers -v`

Expected: FAIL with `TypeError: build_hyp_recs_section() got an unexpected keyword argument 'exclude_tickers'`.

- [ ] **Step 3: Implement the kwarg + filter**

Edit `swing/web/view_models/dashboard.py:300` (signature) and the body where `candidates` and `top_recommendations` are constructed.

Signature change:
```python
def build_hyp_recs_section(
    *, cfg: Config, cache: PriceCache, executor,
    exclude_tickers: Iterable[str] = (),
) -> HypRecsSectionVM:
```

Add an `Iterable` import at the top of the file if not already present:
```python
from typing import Iterable, Mapping  # extend the existing typing import
```

Inside the body, after `candidates = fetch_candidates_for_run(conn, eval_id)` (around line 336 post-Task-2), filter:

```python
            candidates = fetch_candidates_for_run(conn, eval_id)
            # Task 3 (R1 M1 prereq): structurally exclude tickers (open
            # positions, including the just-traded one when called from
            # entry_post). Filter the candidate set before matching so the
            # prices/matchers/prioritizer never see them; the post-filter
            # below the matcher loop is defense-in-depth.
            exclude_set = {t.upper() for t in exclude_tickers}
            if exclude_set:
                candidates = [c for c in candidates if c.ticker not in exclude_set]
            candidates_by_ticker = {c.ticker: c for c in candidates}
```

After `top_recommendations = list(prioritized[:_RECOMMENDATIONS_TOP_N])`, add the defense-in-depth post-filter:

```python
            top_recommendations = list(prioritized[:_RECOMMENDATIONS_TOP_N])
            if exclude_set:
                top_recommendations = [
                    r for r in top_recommendations
                    if r.candidate_ticker not in exclude_set
                ]
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/web/view_models/<file>.py::test_build_hyp_recs_section_excludes_specified_tickers -v`

Expected: PASS.

- [ ] **Step 5: Run the full fast suite**

Run: `python -m pytest -m "not slow" -q 2>&1 | tail -5`

Expected: 1297 passed, 1 skipped, 8 deselected.

- [ ] **Step 6: Commit**

```bash
git add swing/web/view_models/dashboard.py tests/web/view_models/<file>.py
git commit -m "feat(web): Task 3 — build_hyp_recs_section gains exclude_tickers kwarg"
```

- [ ] **Step 7: Observable-verification**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 3' | head -5
```

Expected: at least one line ending in `Task 3 — build_hyp_recs_section gains exclude_tickers kwarg`.

---

## Task 4: Add `oob` kwarg to `hypothesis_recommendations.html.j2` partial

**Goal:** Make the partial always emit a `<section id="hypothesis-recommendations">` element when called with `oob=True`, so HTMX has a valid OOB-swap target even when the rebuilt section's `vm.active_recommendations` is empty (operator just traded their only remaining hyp-rec). The `oob=True` path also adds the `hx-swap-oob="true"` attribute on the section element so HTMX recognizes the fragment as an out-of-band swap. `oob=False` (default) preserves the existing behavior — empty recs → empty render — so `/hyp-recs/refresh` and the full-page `{% include %}` are unchanged. CLAUDE.md "HTMX OOB-swap partial drift" gotcha: this single partial remains the SOLE source of truth for the section's markup; entry_post (Task 5) renders the partial directly with `oob=True` rather than hand-duplicating markup.

**Files:**
- Modify: `swing/web/templates/partials/hypothesis_recommendations.html.j2` — branch on `oob` flag (default False).
- Test: a partial-render test that uses Jinja's environment directly (or a thin pytest fixture that loads the templates dir). If the test layout doesn't have a partial-render test file, locate the closest existing example with `Glob "tests/web/templates/**"` or `Grep -rn "templates.get_template" tests/`. Otherwise, add the partial-render assertion as part of Task 5's route-level test (entry_post response body contains the OOB-section markup) — that route-level assertion alone is discriminating enough.

**Discriminating-test sanity check:** Two assertions: (a) render with `oob=True` AND empty `active_recommendations` produces output containing `<section id="hypothesis-recommendations" hx-swap-oob="true">` — pre-fix, an empty rec list emits nothing, so the assertion fails; (b) render with `oob=False` AND empty `active_recommendations` produces empty output — preserves existing full-page-render behavior. Both assertions together are discriminating: a naive "always emit section" implementation would pass (a) but break (b).

- [ ] **Step 1: Write the failing test**

If a partial-render test file exists, add to it; otherwise create `tests/web/templates/test_hypothesis_recommendations_partial.py`:

```python
from jinja2 import Environment, FileSystemLoader

import pytest

from swing.web.view_models.dashboard import HypRecsSectionVM


@pytest.fixture
def env():
    # Match the loader configuration the FastAPI app uses; if the project
    # exposes a helper for this (e.g., swing.web.app.build_templates),
    # call that instead so the partial render path is identical.
    return Environment(
        loader=FileSystemLoader("swing/web/templates"),
        autoescape=True,
    )


def test_partial_oob_true_empty_recs_emits_section(env):
    """oob=True + empty recs → emits <section id="hypothesis-recommendations"
    hx-swap-oob="true"> with empty inner content. Required so HTMX has a
    valid OOB target even when the operator just traded their only hyp-rec.
    """
    template = env.get_template("partials/hypothesis_recommendations.html.j2")
    vm = HypRecsSectionVM(active_recommendations=())
    rendered = template.render(vm=vm, oob=True)
    assert 'id="hypothesis-recommendations"' in rendered
    assert 'hx-swap-oob="true"' in rendered


def test_partial_oob_false_empty_recs_emits_nothing(env):
    """oob=False (default) + empty recs → preserves current full-page
    behavior (no section element).
    """
    template = env.get_template("partials/hypothesis_recommendations.html.j2")
    vm = HypRecsSectionVM(active_recommendations=())
    rendered = template.render(vm=vm)
    assert 'id="hypothesis-recommendations"' not in rendered


def test_partial_oob_true_populated_recs_emits_section_and_rows(env):
    """oob=True + populated recs → emits the OOB section with the row
    markup the existing partial produces. Defense against accidentally
    breaking the populated path while branching on oob.
    """
    from swing.web.view_models.dashboard import HypothesisRecommendation
    template = env.get_template("partials/hypothesis_recommendations.html.j2")
    rec = HypothesisRecommendation(
        ticker="TESTAPLUS", current_price=27.10, hypothesis_id=1,
        hypothesis_name="A+ baseline", hypothesis_progress_n=2,
        hypothesis_progress_target=10, tripwire_fired=False,
        tripwire_reason=None, suggested_label="A+ baseline — TESTAPLUS",
        pivot_price=26.98,
    )
    vm = HypRecsSectionVM(active_recommendations=(rec,))
    rendered = template.render(vm=vm, oob=True)
    assert 'id="hypothesis-recommendations"' in rendered
    assert 'hx-swap-oob="true"' in rendered
    assert "TESTAPLUS" in rendered
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/web/templates/test_hypothesis_recommendations_partial.py -v`

Expected: the `oob_true_empty_recs` and `oob_true_populated_recs` tests FAIL (template doesn't accept `oob` param meaningfully — current `{% if vm.active_recommendations %}` guard ignores `oob`); the `oob_false_empty_recs` test PASSES (current behavior).

- [ ] **Step 3: Implement the `oob` branch in the template**

Edit `swing/web/templates/partials/hypothesis_recommendations.html.j2`. The new template:

```jinja2
{#- swing/web/templates/partials/hypothesis_recommendations.html.j2 -#}
{#- Frontend brief §4.2 — top-N hypothesis-driven recommendations.

    `oob` flag (Task 4 of hyp-recs success-path fix):
    - oob=False (default, current behavior): the section element is emitted
      ONLY when `vm.active_recommendations` is non-empty. Used by the full-
      page render `{% include %}` and `/hyp-recs/refresh`.
    - oob=True: the section element is ALWAYS emitted (even when recs are
      empty) and carries `hx-swap-oob="true"`. Required by entry_post's
      success-path response so HTMX has a valid OOB-swap target on
      `#hypothesis-recommendations`, including the empty-recs edge case
      where the operator just traded their only remaining hyp-rec.

    Single source of truth for the section markup — CLAUDE.md "HTMX OOB-
    swap partial drift" gotcha forbids hand-duplicating this markup at any
    callsite. -#}
{%- set oob = oob|default(false) -%}
{% if oob or vm.active_recommendations %}
<section id="hypothesis-recommendations" class="hypothesis-recommendations"{% if oob %} hx-swap-oob="true"{% endif %}>
  {%- if vm.active_recommendations %}
  <h2>Hypothesis-driven recommendations</h2>
  <table class="hypothesis-recommendations">
    <thead>
      <tr>
        <th aria-label="Expand"></th>
        <th>Ticker</th>
        <th>Price</th>
        <th>Pivot</th>
        <th>Hypothesis</th>
        <th>Progress</th>
        <th>Tripwire</th>
        <th>Suggested label</th>
        <th aria-label="Action"></th>
      </tr>
    </thead>
    <tbody>
      {% for rec in vm.active_recommendations %}
        {% include "partials/hypothesis_recommendations_row.html.j2" %}
      {% endfor %}
    </tbody>
  </table>
  {%- endif %}
</section>
{% endif %}
```

Key invariants:
- `{%- set oob = oob|default(false) -%}` makes the variable safe when callers don't pass it (Jinja's `default` filter handles undefined gracefully).
- The outer `{% if %}` guard now allows the section to render under EITHER condition (oob OR populated), matching the expected behavior matrix.
- The inner `{%- if vm.active_recommendations %}` branch keeps the heading + table out of the OOB-empty case (so an empty rebuilt section doesn't display a stale heading with no rows beneath it).
- `hx-swap-oob="true"` is added only on the oob branch.

- [ ] **Step 4: Run tests to verify they pass**

Run: `python -m pytest tests/web/templates/test_hypothesis_recommendations_partial.py -v`

Expected: all three tests PASS.

- [ ] **Step 5: Run the full fast suite**

Run: `python -m pytest -m "not slow" -q 2>&1 | tail -5`

Expected: 1300 passed (1294 baseline + Tasks 1–3 + 3 new partial tests), 1 skipped, 8 deselected. **Special check:** the existing route test for `/hyp-recs/refresh` MUST still pass (it renders without `oob`, so the default-false branch preserves behavior). If it fails, the `oob|default(false)` resolution may need an explicit `is defined` check — investigate before proceeding.

- [ ] **Step 6: Commit**

```bash
git add swing/web/templates/partials/hypothesis_recommendations.html.j2 tests/web/templates/test_hypothesis_recommendations_partial.py
git commit -m "feat(web): Task 4 — hypothesis_recommendations partial gains oob kwarg"
```

- [ ] **Step 7: Observable-verification**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 4' | head -5
```

Expected: at least one line ending in `Task 4 — hypothesis_recommendations partial gains oob kwarg`.

---

## Task 5: Wire `#hypothesis-recommendations` OOB swap into entry_post on origin=hyp-recs success

**Goal:** Close R1 Major 1. When `entry_post` succeeds and `origin_coerced == "hyp-recs"`, the response includes a third OOB swap of `#hypothesis-recommendations` rendered through the `partials/hypothesis_recommendations.html.j2` partial with `oob=True`. The rebuild excludes all open-position tickers (which by post-trade state includes the just-traded ticker) via Task 3's `exclude_tickers` kwarg. The OOB swap fires alongside the existing primary swap (open-positions row → form `<tr>`) and the existing OOB swaps (`#status-strip`, `#watchlist-top5`); HTMX applies all swaps. Net effect: the broken open-positions row that briefly lands inside the hyp-recs `<tbody>` is replaced when HTMX OOB-replaces the entire `#hypothesis-recommendations` section, AND the just-traded ticker is no longer surfaced as a recommendation.

**Files:**
- Modify: `swing/web/routes/trades.py` — `entry_post` success-path response (lines 568-608). Build `section_html` conditional on `origin_coerced == "hyp-recs"` and append to the response body.
- Test: existing test file for entry_post POST behavior. Locate via `Grep -rn "POST /trades/entry\|test_post_entry\|entry_post" tests/`. The most likely candidate is `tests/web/routes/test_trades_entry.py` or a similarly-named file.

**Discriminating-test sanity checks** (4 separate tests; per dispatch brief §3.D):

1. **Hyp-recs origin success → OOB swap present.** Pre-fix, the response body contains the primary row + status-strip + watchlist OOB only. Post-fix, the body additionally contains `id="hypothesis-recommendations"` AND `hx-swap-oob="true"` colocated within the same element. Discriminating: a vacuous test (e.g., asserting only `"hypothesis-recommendations" in body`) would pass spuriously because `partials/trade_entry_form.html.j2` references `/hyp-recs/refresh` for hyp-recs origin's Cancel target — verify by asserting the `hx-swap-oob="true"` marker (which only appears in the OOB-rendered partial) on the SAME element as `id="hypothesis-recommendations"`.

2. **Hyp-recs origin success → just-traded ticker absent from OOB chunk.** The fixture seeds `TESTAPLUS` as a hyp-rec; the POST trades it. Post-fix, the OOB chunk's substring containing `id="hypothesis-recommendations"` does NOT contain `>TESTAPLUS<` (the `<td>` cell renders the ticker as bare text). Discriminating: pre-Task-3 (kwarg absent), the rebuild would include TESTAPLUS even though it's now an open position — assertion fails. Post-Task-3 with `exclude_tickers` plumbed by entry_post → TESTAPLUS absent.

3. **Watchlist origin success → no OOB swap of `#hypothesis-recommendations`.** The same POST against origin=watchlist returns the existing 3-fragment response. Post-fix, the body must NOT contain `id="hypothesis-recommendations"` AND `hx-swap-oob="true"` colocated. Discriminating: catches a regression where the OOB swap unconditionally fires regardless of origin (would be a silent over-refresh of an unrelated panel from a watchlist trade).

4. **Hyp-recs origin error path → no `#hypothesis-recommendations` OOB swap.** A POST that triggers an error path (rationale validation failure, duplicate position, etc.) for origin=hyp-recs returns the existing form re-render unchanged — the response body must NOT contain the OOB-swap marker. Discriminating: protects against accidentally re-rendering the hyp-recs section on an error response that the operator's HTMX target (`closest tr`) would then mis-swap.

- [ ] **Step 1: Write the four failing tests**

Open the existing entry_post test file. Add (preserving its existing fixtures and TestClient lifespan setup):

```python
def test_entry_post_hyp_recs_origin_success_emits_hypothesis_recs_oob_swap(
    client, seed_hyp_recs_with_traded_ticker_fixture,
):
    """R1 M1 fix: entry_post on origin=hyp-recs success emits the new
    third OOB swap of `#hypothesis-recommendations`. The marker pair —
    `id="hypothesis-recommendations"` colocated with `hx-swap-oob="true"`
    — distinguishes the OOB swap from incidental string mentions (e.g.
    Cancel target's `hx-target` reference).
    """
    # POST a successful entry on origin=hyp-recs.
    response = client.post(
        "/trades/entry",
        data={
            "ticker": "TESTAPLUS", "entry_date": "2026-04-29",
            "entry_price": "27.10", "shares": "10", "initial_stop": "26.50",
            "rationale": "hypothesis", "notes": "test entry",
            "sector": "Technology", "industry": "Software",
            "origin": "hyp-recs",
        },
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    body = response.text
    # Find the OOB-section block and verify the marker pair is colocated.
    # A simple substring check on `hx-swap-oob="true"` would match the
    # `#status-strip` and `#watchlist-top5` OOBs too — locate the section
    # explicitly to ensure the third OOB lives on the hyp-recs element.
    import re
    pat = re.compile(
        r'<section[^>]*id="hypothesis-recommendations"[^>]*hx-swap-oob="true"',
        re.IGNORECASE,
    )
    assert pat.search(body), (
        f"Expected OOB swap of #hypothesis-recommendations in response body. "
        f"Got: {body[:400]}"
    )


def test_entry_post_hyp_recs_origin_success_excludes_traded_ticker_from_oob(
    client, seed_hyp_recs_with_traded_ticker_fixture,
):
    """R1 M1 fix: the OOB-rebuilt hyp-recs section excludes the just-
    traded ticker. Pre-fix without Task 3's exclude_tickers kwarg, the
    matcher operates on candidates (not trades) so TESTAPLUS would still
    surface in the rebuilt recommendations.
    """
    response = client.post(
        "/trades/entry",
        data={
            "ticker": "TESTAPLUS", "entry_date": "2026-04-29",
            "entry_price": "27.10", "shares": "10", "initial_stop": "26.50",
            "rationale": "hypothesis", "notes": "test entry",
            "sector": "Technology", "industry": "Software",
            "origin": "hyp-recs",
        },
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    body = response.text
    # Extract the OOB-section block.
    import re
    section_match = re.search(
        r'<section[^>]*id="hypothesis-recommendations"[^>]*hx-swap-oob="true"[^>]*>'
        r'(?P<inner>.*?)</section>',
        body, re.DOTALL,
    )
    assert section_match, "OOB section block missing from response"
    inner = section_match.group("inner")
    # The hyp-recs row template renders the ticker inside a `<td>` cell.
    # A naive `"TESTAPLUS" in inner` check would also match a `<a>`-link's
    # href (defensive); pin to the cell-text shape `>TESTAPLUS<`.
    assert ">TESTAPLUS<" not in inner, (
        f"Just-traded ticker leaked into the OOB-rebuilt hyp-recs section. "
        f"Inner: {inner[:400]}"
    )


def test_entry_post_watchlist_origin_success_does_not_emit_hyp_recs_oob_swap(
    client, seed_watchlist_with_traded_ticker_fixture,
):
    """R1 M1 fix preserves existing watchlist-origin response shape:
    no OOB swap of #hypothesis-recommendations on origin=watchlist.

    Discriminating: catches a regression where the OOB swap fires
    unconditionally regardless of origin (silent over-refresh).
    """
    response = client.post(
        "/trades/entry",
        data={
            "ticker": "TESTWATCH", "entry_date": "2026-04-29",
            "entry_price": "30.00", "shares": "5", "initial_stop": "28.00",
            "rationale": "watchlist", "notes": "test entry",
            "sector": "Technology", "industry": "Software",
            "origin": "watchlist",
        },
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 200
    body = response.text
    import re
    pat = re.compile(
        r'<section[^>]*id="hypothesis-recommendations"[^>]*hx-swap-oob="true"',
        re.IGNORECASE,
    )
    assert not pat.search(body), (
        "Watchlist-origin entry must NOT emit the hyp-recs OOB swap. "
        "Found unexpected OOB section."
    )


def test_entry_post_hyp_recs_origin_error_path_does_not_emit_hyp_recs_oob_swap(
    client, seed_hyp_recs_with_traded_ticker_fixture,
):
    """Error-path response shape unchanged for origin=hyp-recs: form
    re-render, no OOB swap. Trigger via invalid rationale (closed
    taxonomy) so EntryRationale rejects pre-record_entry — this hits the
    `_rerender_entry_form_with_error` path which returns 400 + form
    fragment.
    """
    response = client.post(
        "/trades/entry",
        data={
            "ticker": "TESTAPLUS", "entry_date": "2026-04-29",
            "entry_price": "27.10", "shares": "10", "initial_stop": "26.50",
            "rationale": "BOGUS_NOT_IN_ENUM", "notes": "test entry",
            "sector": "Technology", "industry": "Software",
            "origin": "hyp-recs",
        },
        headers={"HX-Request": "true"},
    )
    assert response.status_code == 400
    body = response.text
    import re
    pat = re.compile(
        r'<section[^>]*id="hypothesis-recommendations"[^>]*hx-swap-oob="true"',
        re.IGNORECASE,
    )
    assert not pat.search(body), (
        "Error-path must not emit the hyp-recs OOB swap. Found unexpected "
        "OOB section."
    )
```

Fixture notes:
- `seed_hyp_recs_with_traded_ticker_fixture`: seeds a completed `pipeline_runs` row + matching `evaluation_runs` + an A+ candidate row for `TESTAPLUS` (so the matcher surfaces it as a hyp-rec) + the active hypothesis registry. Re-uses Task 2/3 fixture builders. Seeds an opening cash movement so `current_equity > 0` (sizing-hint feasibility upstream of the request).
- `seed_watchlist_with_traded_ticker_fixture`: similar but seeds `TESTWATCH` as a watchlist row, no hyp-rec match required.
- TestClient lifespan: must use `with TestClient(app) as client:` per CLAUDE.md (exercises `app.state.price_fetch_executor`).

If a canonical fixture exists for the prior dispatch's hyp-recs round-trip tests, prefer it (commit `472d650` Task 9 introduced anchor-consistency tests; the fixtures used there should be reusable here).

- [ ] **Step 2: Run tests to verify they fail**

Run: `python -m pytest tests/web/routes/test_trades_entry.py -k "hyp_recs_origin_success_emits or hyp_recs_origin_success_excludes or watchlist_origin_success_does_not or hyp_recs_origin_error_path" -v`

Expected: tests 1, 2 FAIL (no OOB swap emitted pre-fix); test 3 PASSES (current watchlist-origin behavior already excludes the swap); test 4 PASSES (error-path already returns form re-render unchanged). Tests 3 and 4 are regression guards — they should pass at every step including pre-fix.

- [ ] **Step 3: Implement the OOB-swap wiring in entry_post**

Edit `swing/web/routes/trades.py:568-608`. Modify the success-path response so that when `origin_coerced == "hyp-recs"`, a third OOB chunk is built and appended.

Two-call rebuild block (lines 568-585) is unchanged. The `dashboard_vm = build_dashboard(...)` call is preserved (it sources `#status-strip` and `#watchlist-top5`).

Append after the existing partial renders (lines 592-600):

```python
    # Task 5 (R1 M1): on origin=hyp-recs success, emit a third OOB swap
    # of #hypothesis-recommendations so the broken open-positions row
    # that briefly lands inside hyp-recs <tbody> is replaced and the
    # just-traded ticker is removed from the recommendations panel.
    # The rebuild via build_hyp_recs_section uses the same partial
    # (`partials/hypothesis_recommendations.html.j2`) the full-page render
    # and /hyp-recs/refresh use — single source of truth, per CLAUDE.md
    # "HTMX OOB-swap partial drift" gotcha.
    hyp_recs_section_html = ""
    if origin_coerced == "hyp-recs":
        # Open-position tickers post-trade — record_entry has already
        # persisted the new trade row so list_open_trades returns the
        # post-trade state including the just-traded ticker. Task 3's
        # exclude_tickers kwarg structurally suppresses these tickers
        # from the matcher's output.
        open_trade_tickers = {t.ticker for t in open_trades}
        section_vm = build_hyp_recs_section(
            cfg=cfg, cache=cache, executor=executor,
            exclude_tickers=open_trade_tickers,
        )
        hyp_recs_section_html = templates.get_template(
            "partials/hypothesis_recommendations.html.j2"
        ).render(request=request, vm=section_vm, oob=True)
```

Add the import for `build_hyp_recs_section` to the existing import block at the top of `trades.py` (around line 27 next to the `build_dashboard` import):

```python
from swing.web.view_models.dashboard import build_dashboard, build_hyp_recs_section
```

Update the response return (lines 602-608) to include the new chunk:

```python
    return HTMLResponse(Markup(
        f'{row_html}'
        f'<div id="status-strip" hx-swap-oob="true">{status_strip_html}</div>'
        f'<section id="watchlist-top5" hx-swap-oob="true">'
        f'{watchlist_section_html}'
        f'</section>'
        f'{hyp_recs_section_html}'
    ))
```

Note: the partial RENDERS its own `<section id="hypothesis-recommendations" hx-swap-oob="true">` outer element when `oob=True`, so we do NOT wrap it again here (unlike `#watchlist-top5` whose partial is heading+table only). String-appending the rendered partial is correct.

- [ ] **Step 4: Run the four tests to verify they pass**

Run: `python -m pytest tests/web/routes/test_trades_entry.py -k "hyp_recs_origin_success_emits or hyp_recs_origin_success_excludes or watchlist_origin_success_does_not or hyp_recs_origin_error_path" -v`

Expected: all four tests PASS.

- [ ] **Step 5: Run the full fast suite**

Run: `python -m pytest -m "not slow" -q 2>&1 | tail -5`

Expected: 1304 passed (1294 baseline + 1 [Task 1] + 1 [Task 2] + 1 [Task 3] + 3 [Task 4] + 4 [Task 5]), 1 skipped, 8 deselected. Trust pytest output — count drift is acceptable.

- [ ] **Step 6: Commit**

```bash
git add swing/web/routes/trades.py tests/web/routes/test_trades_entry.py
git commit -m "feat(web): Task 5 — entry_post emits #hypothesis-recommendations OOB on origin=hyp-recs"
```

- [ ] **Step 7: Observable-verification**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 5' | head -5
```

Expected: at least one line ending in `Task 5 — entry_post emits #hypothesis-recommendations OOB on origin=hyp-recs`.

- [ ] **Step 8: Manual smoke verification (frontend changes — per CLAUDE.md UI-changes rule)**

Per the project's UI-changes convention: start the dev server and exercise the trade-entry flow in a browser before declaring the task complete.

```bash
swing web  # starts FastAPI + HTMX dashboard on 127.0.0.1:8080
```

In the browser:
1. With seeded hyp-recs visible, click the per-row Enter button on a recommendation.
2. Submit the entry form (success path).
3. Verify visually:
   - The form `<tr>` is replaced by the new open-positions row IN the open-positions table (not inside hyp-recs `<tbody>`).
   - The hyp-recs panel rebuilds in place, no longer showing the just-traded ticker.
   - Status-strip and watchlist-top5 update as before.
4. Repeat with an "expansion 'Take this trade'" submission (per dispatch brief §5 watch item 6 — multi-path-ingestion).
5. Repeat once with a watchlist-origin entry to confirm hyp-recs panel does NOT refresh on watchlist trades (existing behavior preserved).

If any step misbehaves, surface in the executing-plans return report — do NOT silently expand scope.

---

## Self-review

**Spec coverage (against dispatch brief):**

- §2 R1 M1 fix locked decision (option (a) symmetric OOB-refresh) → Tasks 3, 4, 5.
- §2 R1 M2 fix locked decision (factor shared helper, preserve 2-step fallback, add `id DESC`) → Tasks 1, 2.
- §3 A. Helper name + signature → resolved: `latest_evaluation_run_id(conn) -> int | None`, the existing helper. Documented in Pre-flight context.
- §3 B. `id DESC` tiebreaker preservation → Task 1.
- §3 C. Standalone-eval fallback policy → preserved (Task 2 inherits the existing 2-step fallback by routing through `latest_evaluation_run_id`).
- §3 D. Test surface for R1 M1 (4 discriminating tests) → Task 5 four-test bundle.
- §3 E. Test surface for R1 M2 → Task 1 (`id DESC`), Task 2 (standalone-eval fallback).
- §3 F. Discriminating-test discipline (sentinel pair) → `TESTAPLUS` ticker reserved across Tasks 2–5; CC-pivot sentinel pair (FOO/BAR @ $24.13/$26.98) explicitly NOT reused for these tests.
- §4 Acceptance criteria 1–9 → Per-task TDD ✓, discriminating-test sanity-check sentence ✓, sequential single-subagent ✓, observable-verification grep step ✓, 4-tier flat numbering ✓, R1 M2 helper extraction first ✓, R1 M1 fix tasks second ✓, test count baseline pinned ✓, plan output target path ✓.
- §5 Adversarial review watch items 1–8 → all addressed in task bodies (1: partial reuse; 2: helper signature consistency via `latest_evaluation_run_id`; 3: standalone-eval fallback regression test; 4: `id DESC` is a strict refinement; 5: discriminating test pinning OOB-marker pair; 6: multi-path-ingestion → smoke-verification step covers Enter button + Take-this-trade; 7: rebuild-after-record_entry ordering preserved [list_open_trades read after record_entry persistence]; 8: behavior-equivalence test in Task 2).

**Placeholder scan:** All steps contain actual code or commands. The fixture builder names (`_seed_completed_pipeline_with_aplus_candidate`, `seed_hyp_recs_with_traded_ticker_fixture`) are concrete contract names — the implementer must locate the canonical helpers in the existing test suite (Task 1 step 1 has the search command). If no canonical fixture exists, the test bodies show the SQL/Python the fixture must produce.

**Type consistency:** `build_hyp_recs_section` signature gains `exclude_tickers: Iterable[str] = ()` in Task 3 and is consumed by Task 5; spelling matches across both tasks. The partial's `oob` kwarg in Task 4 is consumed by Task 5's render call. `latest_evaluation_run_id(conn) -> int | None` shape preserved across Tasks 1–2.

**Cross-task wiring:** Task 5 imports `build_hyp_recs_section` (introduced in Task 3 with the kwarg), passes the `oob=True` flag (introduced in Task 4). Order is correct: Tasks 1, 2, 3, 4 land before Task 5.

---

## Open questions for orchestrator triage

None at plan-authoring time. The brief's locked decisions §2 are fully implementable as written. The implementation does require a small additional change (Task 3's `exclude_tickers` kwarg) to make the brief's option (a) language ("the just-traded ticker is removed from recommendations") structurally true — the matcher operates on candidates, not trades, so without this kwarg the just-traded ticker would still surface in the rebuilt section. This is an implementation-correctness adjustment within the locked decision's intent, not a re-design.

If during executing-plans the implementer discovers that Task 5's smoke-verification step reveals the just-traded ticker briefly flickers (race between the OOB section render and the operator's perception), surface that in the executing-plans return report — it would be a follow-up dispatch concern, not Phase 2 scope.
