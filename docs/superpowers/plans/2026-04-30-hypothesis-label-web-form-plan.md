# Phase 4.5 — Hypothesis-Label Web-Form Gap — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Close the gap where every web-form trade entry persists `hypothesis_label = NULL` despite the CLI having full pre-fill machinery since 2026-04-25 — by extracting the matcher helper, resolving the label at form-render time, threading it through the POST handler and soft-warn round-trip, and pinning the behavior with discriminating tests.

**Architecture:** Resolve at form-render via the existing CLI matcher chain (`latest_evaluation_run_id` → `fetch_candidates_for_run` → `match_candidate_to_hypotheses` → `prioritize_recommendations` → `prioritized[0].suggested_label_descriptive`); render as hidden input + read-only display row in the entry form (no operator-edit affordance in V1); thread through POST → `EntryRequest` → `record_entry`'s existing `canonicalize_hypothesis_label`; preserve through soft-warn confirm round-trip via `form_values`. No schema migration, no dataclass change to `EntryRequest`/`Trade` (both already carry `hypothesis_label`); pure web-side wiring. Mirrors the sector/industry capture (Phase 1 Task 6/7) precedent at smaller scope.

**Tech Stack:** Python 3.14, FastAPI/Starlette, Jinja2, HTMX 2.x, SQLite (WAL), pytest.

---

## Brief / spec reference

Binding spec: [`docs/phase4.5-hypothesis-label-web-form-writing-plans-brief.md`](../../phase4.5-hypothesis-label-web-form-writing-plans-brief.md).

Operator-locked decisions (brief §2; **DO NOT re-litigate during execution**):

1. Resolve at form-render via existing CLI matcher logic (cross-surface consistency with dashboard).
2. Helper extraction: `swing/cli.py:_lookup_active_recommendation_label` → `swing/recommendations/hypothesis_prefill.py:lookup_active_recommendation_label` (public; both CLI and web VM import).
3. Read-only display in V1; **no override surface** (no editable input).
4. Snapshot-at-entry-surface (ToCToU fix): resolve at form-render only; persist AS-IS via `EntryRequest.hypothesis_label`. Do NOT re-resolve at submit. Re-render paths re-build the VM via `build_entry_form_vm` (deterministic on DB state).
5. Soft-warn round-trip preserves the label AS-IS via `form_values["hypothesis_label"]`.
6. Empty-string semantics: `Form("")` at the route boundary; route coerces `"" → None` before passing to `EntryRequest`; `record_entry` calls `canonicalize_hypothesis_label` (empty-or-whitespace → `None` → `NULL`).
7. Display row position: between the industry block and the rationale block in `trade_entry_form.html.j2`.
8. Display when unmatched: `<span>(none)</span>`; hidden input value `""`. No "auto-filled" decoration.

---

## Baseline pin

- **HEAD:** `ec93af2` (verified clean tree at dispatch).
- **Fast suite:** 1366 passed, 1 skipped (`python -m pytest -m "not slow" -q`).
- **Expected post-Task-4:** 1376 passed (10 new tests across 4 tasks: T1=2, T2=2, T3=2, T4=4).
- **Ruff baseline:** 91 errors in `swing/`. Don't introduce new violations; don't fix the baseline incidentally.

## Matcher output for the seed fixture (load-bearing constant)

The plan's discriminating tests assert against the EXACT canonical label the matcher emits for the seeded A+ candidate. Reading `swing/recommendations/hypothesis.py:180-205`:

```python
def _descriptive_label(candidate, hypothesis_name) -> str:
    non_pass = sorted(_non_pass_criterion_names(candidate))
    if non_pass: suffix = f"; failed: {', '.join(non_pass)}"
    else:        suffix = ""
    if hypothesis_name == H_CAPITAL_BLOCKED and candidate.bucket == "skip":
        bucket_disp = "skip; capital-blocked"
    else:
        bucket_disp = candidate.bucket
    return f"{hypothesis_name} ({bucket_disp}){suffix}"
```

For the seed `INSERT INTO candidates (... bucket='aplus' ...)` with no failing-criteria column populated, the matcher chain produces:

```
H_APLUS_BASELINE                  = "A+ baseline"
candidate.bucket                  = "aplus"
_non_pass_criterion_names(...)    = empty set    (no failed criteria stored)
bucket_disp                       = "aplus"
suffix                            = ""           (empty non_pass)
suggested_label_descriptive       = "A+ baseline (aplus)"
```

`canonicalize_hypothesis_label("A+ baseline (aplus)")` returns the string unchanged (already NFC-normal; no Cf/Cc; single-spaced).

**Throughout the plan, the constant `EXPECTED_HYPOTHESIS_LABEL = "A+ baseline (aplus)"` is the discriminating-test target for matcher-driven assertions.** A snapshot-trust test (Task 4 test 1) uses a DIFFERENT unique non-matcher string to prove the route does not re-resolve at submit time.

---

## File map

**Create:**
- `swing/recommendations/hypothesis_prefill.py` — public `lookup_active_recommendation_label` helper (lifted from `swing/cli.py:339-395`).
- `tests/recommendations/test_hypothesis_prefill.py` — unit tests for the helper.
- `tests/web/test_view_models/test_trade_entry_form_hypothesis.py` — VM-level tests.
- `tests/web/test_routes/test_trade_entry_hypothesis_thread.py` — POST-level integration tests.

**Modify:**
- `swing/cli.py` — remove the local helper at lines 339-395; replace the call site at line 491 with `lookup_active_recommendation_label(...)`; add `from swing.recommendations.hypothesis_prefill import lookup_active_recommendation_label`.
- `swing/web/view_models/trades.py` — extend `TradeEntryFormVM` with `hypothesis_label: str | None = None`; resolve inside `build_entry_form_vm`'s `with conn:` block (before `conn.close()` at line 177).
- `swing/web/templates/partials/trade_entry_form.html.j2` — add hypothesis row between line 53 (`<input type="hidden" name="industry">`) and line 55 (`<label>Rationale</label>`).
- `swing/web/routes/trades.py` — add `hypothesis_label: str = Form("")` parameter to `entry_post`; pass through to `EntryRequest` with `or None` coercion; add `"hypothesis_label": hypothesis_label,` to `form_values` in soft-warn path.

**Reference (DO NOT modify):**
- `swing/trades/entry.py:80-241` — `EntryRequest` already has `hypothesis_label: str | None = None` (line 94); `record_entry` already calls `canonicalize_hypothesis_label(req.hypothesis_label)` (line 201).
- `swing/data/models.py:77` — `Trade.hypothesis_label` already persists.
- `swing/data/repos/trades.py` — already SELECTs/INSERTs `hypothesis_label`.
- `tests/cli/test_cli_trade_entry_hypothesis_prefill.py` — canonical CLI prefill test patterns (template for unit-test seeding).

---

## Hand-constructed test-site enumeration (Phase 4 Task 1 lesson)

Per brief §4.4, document `TradeEntryFormVM` test-site exposure surface before extending the dataclass. Performed via:

```bash
grep -rn "TradeEntryFormVM(" tests/
```

**Result:** zero hand-constructed `TradeEntryFormVM(...)` instances in tests. Existing references are import statements or `isinstance(...)` checks only:

- `tests/web/test_view_models/test_trades.py:14` — import only.
- `tests/web/test_view_models/test_trades.py:44` — `isinstance(vm, TradeEntryFormVM)` only.
- `tests/web/test_view_models/test_trade_entry_form_classification.py:1` — module docstring reference only.
- `tests/web/test_routes/test_hyp_recs_expand_route.py:781` — comment only.

Adding a default-valued field `hypothesis_label: str | None = None` does not break any existing test (no constructor argument list to update). Refactor scope for Task 2 dataclass extension: zero test-side fixups.

---

## Conventions (binding)

- **Branch:** `main`. No feature branches.
- **TDD:** failing test first → run-fail → minimal implementation → run-pass → commit. One red-green cycle per logical change. **No `--no-verify`. No amending. No Claude co-author footer.**
- **Commit-message convention (4-tier; orchestrator-context "Binding conventions"):**
  - Task implementations: `feat(area): Task X.Y — <description>` (or `refactor(area):` for the helper-extraction commit).
  - Codex review-fix commits: `fix(area): Codex R<N> Major <M> — <description>`.
  - Internal-Codex within-task: `fix(area): Codex R<N> Major <M> (internal) — <description>`.
  - Internal code-review: `fix(area): code-review I<N> — <description>`.
  - Format-only cleanup (ruff, comment, whitespace): no task ID — e.g. `style(area): ruff cleanup`.
- **Observable-verification subject-only grep** (run BEFORE each task implementation commit to detect rogue duplicates from earlier subagent activity):
  ```bash
  git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'
  ```
  - `-E` is REQUIRED (BRE chokes on `+`).
  - POSIX `[0-9]` is REQUIRED for digit class (no Perl `\d`).
  - Substitute `X.Y` per task. Expected output: empty before the new commit; one matching subject line after.
- **Effective-contract trace (brief §4.11; Phase 4 R1 M1 lesson 2026-04-30).** The empty-string-→-NULL semantic chain is load-bearing. Trace:
  ```
  hypothesis_label = ""  in Form (boundary)
    → entry_post coerces:  hypothesis_label or None  →  None  (route-layer defense-in-depth)
    → EntryRequest.hypothesis_label = None
    → record_entry: canonicalize_hypothesis_label(None) returns None  (entry.py:149-150)
    → Trade.hypothesis_label = None
    → SQLite NULL persisted on the trades row.
  ```
  And for a matching ticker:
  ```
  hypothesis_label = "<canonical-label-from-matcher>"  in Form
    → entry_post: "<label>" or None  →  "<label>"
    → EntryRequest.hypothesis_label = "<label>"
    → record_entry: canonicalize_hypothesis_label("<label>") returns canonicalized form
    → Trade.hypothesis_label = canonical persisted on the trades row.
  ```
  Brief §4.11 requires this trace to be load-bearing for the "no-match → NULL" guarantee. **Task 4 tests both branches empirically (Test 4.1 for matching ticker; Test 4.2 for non-matching).**

---

## Sequencing + partitioning

Single subagent, sequential execution. No parallel-agent collision risk. Tasks ordered so each builds on the prior:

1. **Task 1** — helper extraction (refactor; pure code-move + import-flip; no behavior change).
2. **Task 2** — VM extension (depends on Task 1's public helper).
3. **Task 3** — template render (depends on Task 2's VM field).
4. **Task 4** — POST handler thread + soft-warn round-trip + ToCToU snapshot-trust + rationale-fail re-render preservation (depends on Task 3's hidden input being emitted).

(Per Codex R1 Major 4: tests-only "Task 5" eliminated; its content folded into Task 4 so per-task TDD discipline holds — every test RED before the task's impl, GREEN after.)

---

## Task 1: Helper extraction (`swing/recommendations/hypothesis_prefill.py`)

**Files:**
- Create: `swing/recommendations/hypothesis_prefill.py`
- Modify: `swing/cli.py` (remove helper at lines 339-395; add import; update call site at line 491)
- Create: `tests/recommendations/test_hypothesis_prefill.py`

**Discriminating-test sanity check:** *"Would these tests fail if the implementation never actually called the new code?"* — Yes. Test 1.1 asserts EXACT equality with the matcher's deterministic output `"A+ baseline (aplus)"`; if the helper short-circuited, returned a different field (`suggested_label_short`), picked a different prioritized index, or formatted the bucket-suffix differently, this assertion fails (Codex R1 Major 3 fix: not prefix-match). Test 1.2 asserts `None` for a ticker with no candidate row; if the helper falsely returned a label from another ticker (cursor-iteration bug), the assertion fails. Test 1.3 (existing CLI test re-run) catches regression in the CLI's import path post-extraction.

**Multi-path audit (brief §5.4):** Post-Task-1, the function has TWO consumers — `swing/cli.py` (existing) and (in Task 2) `swing/web/view_models/trades.py` (new). Verify no other file imports `_lookup_active_recommendation_label` BEFORE removing it: `grep -rn "_lookup_active_recommendation_label" .` should return only the cli.py definition+call (and brief/plan/test reference text). Pre-dispatch verification confirmed no external importers of the underscore-prefixed form.

- [ ] **Step 1: Verify pre-Task-1 baseline**

```bash
git log --oneline -1
python -m pytest -m "not slow" -q 2>&1 | tail -3
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 1\.'
```

Expected:
- HEAD = `ec93af2` (or the latest commit on `main` if the brief commit moved).
- Fast suite: 1366 passed, 1 skipped.
- Subject-only grep: empty (no prior Task 1.x commits).

- [ ] **Step 2: Write the failing unit tests**

Create `tests/recommendations/test_hypothesis_prefill.py`:

```python
"""Unit tests for swing.recommendations.hypothesis_prefill.

Lifted helper from swing/cli.py:_lookup_active_recommendation_label
(pre-Phase-4.5) to swing/recommendations/hypothesis_prefill.py.
Public name; both CLI and web VM consume it.

Test seed pattern mirrors tests/cli/test_cli_trade_entry_hypothesis_prefill.py
so the helper-side and CLI-side tests exercise identical fixture shape.
"""
from __future__ import annotations

from pathlib import Path

import tomllib
from click.testing import CliRunner

from swing.cli import main
from swing.data.db import connect
from swing.recommendations.hypothesis_prefill import (
    lookup_active_recommendation_label,
)
from tests.cli.test_cli_eval import _minimal_config


def _setup(tmp_path: Path) -> Path:
    project = tmp_path / "project"
    project.mkdir()
    home = tmp_path / "home"
    home.mkdir()
    cfg = _minimal_config(project, home)
    runner = CliRunner()
    runner.invoke(main, ["--config", str(cfg), "db-migrate"])
    return cfg


def _seed_aplus_pipeline(cfg_path: Path, ticker: str) -> None:
    """Seed a complete pipeline run with one A+ candidate for `ticker`."""
    cfg_data = tomllib.loads(cfg_path.read_text())
    db_path = Path(cfg_data["paths"]["db_path"])
    conn = connect(db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20"),
            )
            eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                   close, pivot, initial_stop, rs_method)
                   VALUES (?, ?, 'aplus', 180.0, 181.0, 170.0, 'universe')""",
                (eval_id, ticker),
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00',
                           'scheduled', '2026-04-17', '2026-04-20',
                           'complete', 'tok', ?)""",
                (eval_id,),
            )
    finally:
        conn.close()


def test_lookup_active_recommendation_label_returns_exact_matcher_label(
    tmp_path: Path,
):
    """Discriminating: with an A+ candidate seeded for AAPL, the helper
    returns EXACTLY the matcher's suggested_label_descriptive output.

    Per Codex R1 Major 3, exact-equality (not prefix-match) catches
    wrong-label bugs WITHIN the same hypothesis family — e.g. a regression
    that returned `suggested_label_short`, picked the wrong prioritized
    index, or formatted the bucket-suffix differently.

    For the seed fixture (bucket='aplus', no failing criteria), the
    matcher chain produces "A+ baseline (aplus)" deterministically — see
    "Matcher output for the seed fixture" near the top of this plan.
    The plan's load-bearing constant.

    Sanity: if the helper short-circuited (wrong table query), forgot
    the prioritizer step, returned the wrong field, or read from a
    stale evaluation_run_id, this exact-equality assertion fails.
    """
    cfg = _setup(tmp_path)
    _seed_aplus_pipeline(cfg, ticker="AAPL")

    cfg_data = tomllib.loads(cfg.read_text())
    db_path = Path(cfg_data["paths"]["db_path"])
    conn = connect(db_path)
    try:
        label = lookup_active_recommendation_label(
            conn, ticker="AAPL", starting_equity=1200.0,
        )
    finally:
        conn.close()

    # Exact-equality with the matcher's deterministic output for this
    # fixture. NOT a prefix match — the matcher's full descriptive
    # label is the contract.
    assert label == "A+ baseline (aplus)", (
        f"helper must return exact matcher output; got {label!r}"
    )


def test_lookup_active_recommendation_label_returns_None_for_non_matching(
    tmp_path: Path,
):
    """Degenerate: ticker has no candidate row → helper returns None.
    Preserves the no-match → NULL persistence guarantee (downstream
    record_entry → canonicalize_hypothesis_label semantic).

    Sanity: if the helper falsely returned the label from another
    ticker (cursor-iteration bug, missing ticker filter), this
    assertion would fail.
    """
    cfg = _setup(tmp_path)
    _seed_aplus_pipeline(cfg, ticker="AAPL")  # AAPL exists; ZZZ does not.

    cfg_data = tomllib.loads(cfg.read_text())
    db_path = Path(cfg_data["paths"]["db_path"])
    conn = connect(db_path)
    try:
        label = lookup_active_recommendation_label(
            conn, ticker="ZZZ", starting_equity=1200.0,
        )
    finally:
        conn.close()

    assert label is None
```

Note: the test file directory `tests/recommendations/` may not exist — create it with an empty `__init__.py` if pytest discovery requires (the repo follows a flat-package convention; verify by checking `tests/recommendations/` after Step 4 of this task).

- [ ] **Step 3: Run tests to verify FAIL**

```bash
python -m pytest tests/recommendations/test_hypothesis_prefill.py -v
```

Expected: `ImportError: cannot import name 'lookup_active_recommendation_label' from 'swing.recommendations.hypothesis_prefill'` (module does not yet exist).

- [ ] **Step 4: Create the new module by lifting from cli.py**

Create `swing/recommendations/hypothesis_prefill.py`:

```python
"""Public helper for resolving the active hypothesis recommendation label
for a given ticker — used by both the CLI (`swing trade entry` pre-fill)
and the web entry form (Phase 4.5 hypothesis-label web-form gap closure).

Frontend brief §0 + §4.3: the matcher's ``suggested_label_descriptive``
starts with the canonical hypothesis name (case-insensitive). Passing it
through unchanged preserves that prefix so future tripwire/progress
aggregation attributes the trade correctly. Determinism: the matcher +
prioritizer + per-ticker dedup are pure functions on (registry,
candidates, progress); re-running yields the same label — needed by the
brief §5 watch item on pre-fill stability.

Cross-surface consistency (adversarial review R1 Major 1 from the CLI's
original implementation): use the SAME evaluation_run id the dashboard
binds candidates to. If the operator sees a recommendation on the
dashboard for ticker X, the CLI/web-form for X must pre-fill the same
label.

Imports of ``swing.web.view_models.dashboard`` happen inside the function
body (not at module top) so this module stays import-cheap and avoids
any future circular-import risk if dashboard.py grows imports of its own.
"""
from __future__ import annotations

import sqlite3


def lookup_active_recommendation_label(
    conn: sqlite3.Connection, *, ticker: str, starting_equity: float,
) -> str | None:
    """Return the suggested hypothesis label for ``ticker`` from the latest
    completed pipeline run's active hypothesis match, or ``None`` if there
    is no run / no candidate / no match.
    """
    from swing.data.repos.candidates import fetch_candidates_for_run
    from swing.data.repos.hypothesis import list_hypotheses
    from swing.recommendations.hypothesis import (
        match_candidate_to_hypotheses,
        prioritize_recommendations,
    )
    from swing.web.view_models.dashboard import (
        build_recommendation_progress,
        latest_evaluation_run_id,
    )

    eval_id = latest_evaluation_run_id(conn)
    if eval_id is None:
        return None
    candidates = fetch_candidates_for_run(conn, eval_id)
    cand = next((c for c in candidates if c.ticker == ticker), None)
    if cand is None:
        return None

    registry = list_hypotheses(conn)
    matches = match_candidate_to_hypotheses(cand, registry=registry)
    if not matches:
        return None

    _, progress_summaries = build_recommendation_progress(
        conn, registry, starting_equity=starting_equity,
    )
    prioritized = prioritize_recommendations(
        matches, registry=registry, progress=progress_summaries,
    )
    if not prioritized:
        return None
    return prioritized[0].suggested_label_descriptive
```

If `tests/recommendations/` does not yet exist, create the directory and an empty `__init__.py`:

```bash
mkdir -p tests/recommendations
touch tests/recommendations/__init__.py
```

- [ ] **Step 5: Update cli.py to import from the new module + remove the local helper**

Edit `swing/cli.py`:

**5a.** Remove lines 339-395 (the entire `def _lookup_active_recommendation_label(...)` definition through `return prioritized[0].suggested_label_descriptive`).

**5b.** Replace the call at line 491:

Find:
```python
        if hypothesis is None:
            prefilled = _lookup_active_recommendation_label(
                conn, ticker=ticker.upper(),
                starting_equity=cfg.account.starting_equity,
            )
```

Replace with:
```python
        if hypothesis is None:
            prefilled = lookup_active_recommendation_label(
                conn, ticker=ticker.upper(),
                starting_equity=cfg.account.starting_equity,
            )
```

**5c.** Add import. Locate the existing top-level imports in `swing/cli.py` (the alphabetized block near the top of the file). Add:

```python
from swing.recommendations.hypothesis_prefill import lookup_active_recommendation_label
```

If the helper-import is preferred lazy (matching the existing in-function import style in `trade_entry_cmd`), add it inside the function body just before the `if hypothesis is None:` block instead. Either is acceptable; module-top is cleaner. **Choose module-top.**

- [ ] **Step 6: Verify no orphaned references remain**

```bash
grep -rn "_lookup_active_recommendation_label" swing/ tests/
```

Expected: zero matches (the underscore-prefixed name is fully removed; the new public name `lookup_active_recommendation_label` is the only form referenced).

- [ ] **Step 7: Run new + existing tests to verify GREEN**

```bash
python -m pytest tests/recommendations/test_hypothesis_prefill.py -v
python -m pytest tests/cli/test_cli_trade_entry_hypothesis_prefill.py -v
```

Expected:
- New unit tests: 2 passed.
- Existing CLI prefill tests: 5 passed (unchanged behavior post-extraction; brief §5.5 acceptance criterion).

If either fails, the helper move is incorrect — investigate before continuing.

- [ ] **Step 8: Run the full fast suite**

```bash
python -m pytest -m "not slow" -q
```

Expected: 1368 passed, 1 skipped (1366 baseline + 2 new tests).

- [ ] **Step 9: Verify ruff baseline preserved**

```bash
ruff check swing/ 2>&1 | tail -5
```

Expected: 91 errors (no change vs baseline; the helper move doesn't introduce new violations).

- [ ] **Step 10: Observable-verification grep + commit**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 1\.'
```

Expected: empty (no prior Task 1.x commit; this is the first task).

```bash
git add swing/recommendations/hypothesis_prefill.py swing/cli.py \
        tests/recommendations/__init__.py tests/recommendations/test_hypothesis_prefill.py
git commit -m "$(cat <<'EOF'
refactor(recommendations): Task 1.1 — extract lookup_active_recommendation_label to swing/recommendations/hypothesis_prefill.py

Phase 4.5 prep: hypothesis prefill helper moves from swing/cli.py
(underscore-prefixed) to a public module so the upcoming web entry-form
VM (Task 2) can import it alongside the CLI. No behavior change; CLI
prefill tests still green.
EOF
)"
```

Re-run the grep to confirm:

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 1\.'
```

Expected: one matching line — `refactor(recommendations): Task 1.1 — extract lookup_active_recommendation_label to swing/recommendations/hypothesis_prefill.py`.

---

## Task 2: VM extension (`TradeEntryFormVM` + `build_entry_form_vm`)

**Files:**
- Modify: `swing/web/view_models/trades.py` (extend dataclass; resolve in `build_entry_form_vm`)
- Create: `tests/web/test_view_models/test_trade_entry_form_hypothesis.py`

**Discriminating-test sanity check:** *"Would these tests fail if the implementation never actually called the new code?"* — Yes. Test 2.1 seeds an A+ candidate for AAPL and asserts `vm.hypothesis_label == "A+ baseline (aplus)"` (exact equality, per Codex R1 Major 3); if `build_entry_form_vm` never called the new helper (or always wrote None), the assertion fails. Test 2.2 seeds NO candidate for ZZZ and asserts `vm.hypothesis_label is None`; if the helper falsely cross-resolved from AAPL's row, the assertion fails.

**Compounding-confound check (brief §4.3, §5.1):** the discriminating test in 2.1 asserts the EXACT label `"A+ baseline (aplus)"` — structurally unique to "the matcher chain ran end-to-end against the seeded candidate AND the VM passed it through unchanged." There is no default/fallback value the VM could produce that coincidentally equals this string — the only path producing it is `prioritize_recommendations(...).suggested_label_descriptive` for an aplus-bucket candidate with no failing criteria. Bug-present (`vm.hypothesis_label = None` because the new helper-call line is missing) → assertion fails. Bug (VM transformed/truncated) → assertion fails. Correct → assertion passes.

- [ ] **Step 1: Verify pre-Task-2 baseline**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 2\.'
python -m pytest -m "not slow" -q 2>&1 | tail -3
```

Expected:
- Subject-only grep: empty.
- Fast suite: 1368 passed, 1 skipped.

- [ ] **Step 2: Write the failing VM-level tests**

Create `tests/web/test_view_models/test_trade_entry_form_hypothesis.py`:

```python
"""Phase 4.5 — TradeEntryFormVM.hypothesis_label resolution.

build_entry_form_vm resolves the active hypothesis recommendation label
at form-render time via lookup_active_recommendation_label (snapshot-
at-entry-surface; ToCToU fix per spec §3.6 / Phase 5 lesson). The
resolved value flows through a hidden form field to the POST handler
in Task 4 and persists AS-IS via record_entry.

Test seed pattern mirrors tests/cli/test_cli_trade_entry_hypothesis_prefill.py.
"""
from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock

from swing.data.db import connect


def _seed_aplus_pipeline(db_path, ticker: str) -> None:
    conn = connect(db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20"),
            )
            eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                   close, pivot, initial_stop, rs_method)
                   VALUES (?, ?, 'aplus', 180.0, 181.0, 170.0, 'universe')""",
                (eval_id, ticker),
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00',
                           'scheduled', '2026-04-17', '2026-04-20',
                           'complete', 'tok', ?)""",
                (eval_id,),
            )
    finally:
        conn.close()


def test_build_entry_form_vm_populates_exact_matcher_label_when_recommendation_exists(
    seeded_db,
):
    """Discriminating (per Codex R1 Major 3): with an A+ candidate seeded
    for AAPL, the VM carries hypothesis_label EXACTLY equal to the
    matcher's deterministic output "A+ baseline (aplus)" — the constant
    pinned at the top of this plan. Exact-equality (not prefix-match)
    catches a class of bugs where the VM transforms or truncates the
    label between helper-return and dataclass-construct.

    Sanity: if build_entry_form_vm never calls
    lookup_active_recommendation_label (e.g. the new resolution line is
    missing or guarded behind an unreachable branch), the field stays
    at its dataclass default (None) and this exact-equality assertion
    fails.
    """
    from swing.web.view_models.trades import build_entry_form_vm
    cfg, _ = seeded_db
    _seed_aplus_pipeline(cfg.paths.db_path, ticker="AAPL")

    cache = MagicMock()
    cache.get_many.return_value = {}
    vm = build_entry_form_vm(
        ticker="AAPL", cfg=cfg, cache=cache, executor=MagicMock(),
    )

    assert vm.hypothesis_label == "A+ baseline (aplus)", (
        f"VM must carry exact matcher label; got {vm.hypothesis_label!r}"
    )


def test_build_entry_form_vm_returns_None_hypothesis_label_when_no_candidate(
    seeded_db,
):
    """Degenerate: ticker has no candidate row in the latest evaluation
    → vm.hypothesis_label is None. Preserves the no-match → empty
    persistence guarantee for off-pipeline trade entries.

    Sanity: if the helper falsely cross-resolved from another ticker's
    row (cursor-iteration bug), this assertion would fail.
    """
    from swing.web.view_models.trades import build_entry_form_vm
    cfg, _ = seeded_db
    _seed_aplus_pipeline(cfg.paths.db_path, ticker="AAPL")

    cache = MagicMock()
    cache.get_many.return_value = {}
    vm = build_entry_form_vm(
        ticker="ZZZ", cfg=cfg, cache=cache, executor=MagicMock(),
    )

    assert vm.hypothesis_label is None
```

- [ ] **Step 3: Run tests to verify FAIL**

```bash
python -m pytest tests/web/test_view_models/test_trade_entry_form_hypothesis.py -v
```

Expected: `AttributeError: 'TradeEntryFormVM' object has no attribute 'hypothesis_label'` (the field does not yet exist on the dataclass).

- [ ] **Step 4: Add the field to `TradeEntryFormVM`**

Edit `swing/web/view_models/trades.py`. Find the `pipeline_finished_at` field at line 93 (the last field in the dataclass):

```python
    pipeline_finished_at: str | None = None
```

Add immediately after:

```python
    # Phase 4.5 — Hypothesis recommendation label resolved at form-render
    # time via swing.recommendations.hypothesis_prefill. Snapshot-at-
    # entry-surface (ToCToU fix per spec §3.6 / Phase 5 lesson): the
    # value flows through a hidden form field to the POST handler and
    # persists AS-IS via record_entry's canonicalize_hypothesis_label
    # boundary. None when the ticker has no active recommendation in
    # the latest evaluation run — template renders "(none)" display
    # and emits an empty hidden input value.
    hypothesis_label: str | None = None
```

- [ ] **Step 5: Resolve the label inside `build_entry_form_vm`**

In the same file, find the `with conn:` block in `build_entry_form_vm` (starts at line 118). Locate the closing of the candidate-row read at line 175 (`cand_initial_stop = cand_row[3]`). Add the hypothesis resolution INSIDE the `with conn:` block but BEFORE `finally:` at line 176, so the connection is open when the helper queries.

Find:
```python
            if sector_eval_id is not None:
                cand_row = conn.execute(
                    """SELECT sector, industry, pivot, initial_stop FROM candidates
                       WHERE evaluation_run_id = ? AND ticker = ?""",
                    (sector_eval_id, ticker),
                ).fetchone()
                if cand_row is not None:
                    cand_sector = cand_row[0] or ""
                    cand_industry = cand_row[1] or ""
                    cand_pivot = cand_row[2]
                    cand_initial_stop = cand_row[3]
    finally:
        conn.close()
```

Replace with:
```python
            if sector_eval_id is not None:
                cand_row = conn.execute(
                    """SELECT sector, industry, pivot, initial_stop FROM candidates
                       WHERE evaluation_run_id = ? AND ticker = ?""",
                    (sector_eval_id, ticker),
                ).fetchone()
                if cand_row is not None:
                    cand_sector = cand_row[0] or ""
                    cand_industry = cand_row[1] or ""
                    cand_pivot = cand_row[2]
                    cand_initial_stop = cand_row[3]
            # Phase 4.5 — resolve active hypothesis recommendation label
            # at form-render (snapshot-at-entry-surface). Same matcher
            # chain the CLI uses (swing/cli.py:trade_entry_cmd via the
            # extracted helper) — cross-surface consistency: dashboard
            # recommendation, CLI prefill, and form prefill all converge
            # on the same suggested label. None when the ticker has no
            # active recommendation; template renders "(none)" + empty
            # hidden input value.
            from swing.recommendations.hypothesis_prefill import (
                lookup_active_recommendation_label,
            )
            resolved_hypothesis_label = lookup_active_recommendation_label(
                conn, ticker=ticker,
                starting_equity=cfg.account.starting_equity,
            )
    finally:
        conn.close()
```

Then locate the `return TradeEntryFormVM(...)` literal at line 258. Add `hypothesis_label=resolved_hypothesis_label,` to the constructor call. Find the existing `pipeline_finished_at=...` line:

```python
        pipeline_finished_at=(
            pipeline_finished_at if coerced_origin == "hyp-recs" else None
        ),
    )
```

Replace with:
```python
        pipeline_finished_at=(
            pipeline_finished_at if coerced_origin == "hyp-recs" else None
        ),
        hypothesis_label=resolved_hypothesis_label,
    )
```

- [ ] **Step 6: Run tests to verify GREEN**

```bash
python -m pytest tests/web/test_view_models/test_trade_entry_form_hypothesis.py -v
```

Expected: 2 passed.

- [ ] **Step 7: Run the existing VM tests to confirm no regression**

```bash
python -m pytest tests/web/test_view_models/ -v
```

Expected: all passing (no regressions on `test_trades.py`, `test_trade_entry_form_classification.py`, etc.).

- [ ] **Step 8: Run the full fast suite**

```bash
python -m pytest -m "not slow" -q
```

Expected: 1370 passed, 1 skipped (1368 + 2 new tests).

- [ ] **Step 9: Observable-verification grep + commit**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 2\.'
```

Expected: empty.

```bash
git add swing/web/view_models/trades.py \
        tests/web/test_view_models/test_trade_entry_form_hypothesis.py
git commit -m "$(cat <<'EOF'
feat(web): Task 2.1 — TradeEntryFormVM gains hypothesis_label; build_entry_form_vm resolves at form-render

Phase 4.5: VM carries the snapshot-at-entry-surface label. Resolution
happens inside the existing with-conn block via the public
lookup_active_recommendation_label helper extracted in Task 1. None
for off-pipeline tickers; canonical hypothesis-prefix string for
A+ matches.
EOF
)"
```

Re-run the grep to confirm one matching subject line.

---

## Task 3: Template render (`trade_entry_form.html.j2`)

**Files:**
- Modify: `swing/web/templates/partials/trade_entry_form.html.j2` (insert hypothesis row between industry block and rationale block)
- Add tests to: `tests/web/test_routes/test_trades_route.py` (extend existing GET-form test patterns)

**Discriminating-test sanity check:** *"Would these tests fail if the implementation never rendered the new template row?"* — Yes. Test 3.1 GETs the form for AAPL (with seeded A+ candidate) and asserts the response body contains `'name="hypothesis_label" value="A+ baseline (aplus)"'` (exact-value substring per Codex R1 Major 3) AND `">A+ baseline (aplus)<"` (the read-only display span); if the template row is missing OR the wrong VM field is referenced, the assertion fails. Test 3.2 GETs the form for ZZZ (no candidate) and asserts the response contains `name="hypothesis_label"` with `value=""` AND the `(none)` display text; if the template row is missing OR the `or "(none)"` Jinja filter is wrong, the assertion fails.

**Effective-contract verification (brief §4.11):** Test 3.1 verifies the hidden input is emitted with the canonical label flowing through Jinja's `value=` attribute escaping. Test 3.2 verifies the empty-string-default contract at the template layer (matches the `Form("")` default in Task 4).

- [ ] **Step 1: Verify pre-Task-3 baseline**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 3\.'
python -m pytest -m "not slow" -q 2>&1 | tail -3
```

Expected:
- Subject-only grep: empty.
- Fast suite: 1370 passed, 1 skipped.

- [ ] **Step 2: Write the failing template-level tests**

Append to `tests/web/test_routes/test_trades_route.py`:

```python


# Phase 4.5 — hypothesis_label template render tests.

def _seed_aplus_pipeline_for_route_test(db_path, ticker: str) -> None:
    """Same seed pattern as tests/web/test_view_models/test_trade_entry_form_hypothesis.py."""
    from swing.data.db import connect
    conn = connect(db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20"),
            )
            eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                   close, pivot, initial_stop, rs_method)
                   VALUES (?, ?, 'aplus', 180.0, 181.0, 170.0, 'universe')""",
                (eval_id, ticker),
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00',
                           'scheduled', '2026-04-17', '2026-04-20',
                           'complete', 'tok', ?)""",
                (eval_id,),
            )
    finally:
        conn.close()


def test_entry_form_renders_exact_hypothesis_label_in_hidden_input(
    seeded_db, monkeypatch,
):
    """Discriminating (per Codex R1 Major 3): GET /trades/entry/form?ticker=AAPL
    renders the hypothesis_label hidden input with EXACTLY the matcher's
    canonical output `"A+ baseline (aplus)"` — full label string, not
    a prefix.

    Sanity: if the template row is missing entirely, the hidden-input
    substring assertion fails. If the template emits the wrong field
    (e.g. `vm.hypothesis_label_short` if such a field were ever added),
    the exact-value substring fails.
    """
    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache

    cfg, cfg_path = seeded_db
    _seed_aplus_pipeline_for_route_test(cfg.paths.db_path, ticker="AAPL")
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=AAPL")
    assert r.status_code == 200
    assert 'name="hypothesis_label"' in r.text, (
        "template must render the hypothesis_label hidden input"
    )
    # Exact-value substring assertion. The matcher emits
    # "A+ baseline (aplus)" verbatim for the seed fixture; the template
    # must emit it verbatim into the hidden-input value attribute.
    assert 'name="hypothesis_label" value="A+ baseline (aplus)"' in r.text, (
        "hidden input must carry exact matcher label "
        f'"A+ baseline (aplus)"; response excerpt: {r.text[:500]!r}'
    )
    # Visible read-only display row also carries the exact label.
    assert ">A+ baseline (aplus)<" in r.text, (
        "visible display row must show the exact matcher label "
        "(in a span between > and <)"
    )


def test_entry_form_renders_none_display_when_label_unresolved(
    seeded_db, monkeypatch,
):
    """Degenerate: GET form for a ticker with no candidate row renders
    `(none)` in the read-only display + an empty value="" hidden input.

    Sanity: if the template uses `vm.hypothesis_label` directly without
    the `or "(none)"` filter, this assertion would fail (Jinja would
    emit `None`-as-empty-string, not the literal `(none)` token).
    """
    from fastapi.testclient import TestClient
    from swing.web.app import create_app
    from swing.web.price_cache import PriceCache

    cfg, cfg_path = seeded_db
    # No candidate seeded for ZZZ — vm.hypothesis_label resolves to None.
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {})

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r = client.get("/trades/entry/form?ticker=ZZZ")
    assert r.status_code == 200
    assert 'name="hypothesis_label"' in r.text
    # Empty hidden-input value when label is None.
    assert 'name="hypothesis_label" value=""' in r.text, (
        "unresolved label must produce empty hidden-input value"
    )
    # Visible read-only display falls back to "(none)".
    assert "(none)" in r.text, (
        "template must render (none) display when vm.hypothesis_label is None"
    )
```

- [ ] **Step 3: Run tests to verify FAIL**

```bash
python -m pytest tests/web/test_routes/test_trades_route.py::test_entry_form_renders_hidden_hypothesis_label_input_when_resolved tests/web/test_routes/test_trades_route.py::test_entry_form_renders_none_display_when_label_unresolved -v
```

Expected: both fail. The most likely failure mode is `assert 'name="hypothesis_label"' in r.text` returning False because the template row hasn't been added.

- [ ] **Step 4: Edit the template**

Edit `swing/web/templates/partials/trade_entry_form.html.j2`. Find the industry block (lines 51-54):

```jinja
      <div><label>Industry:</label>
        <span>{{ vm.industry or "—" }}</span>
        <input type="hidden" name="industry" value="{{ vm.industry }}">
      </div>
      <div><label>Rationale &#9733;</label>
```

Replace with (insert the hypothesis block between industry and rationale):

```jinja
      <div><label>Industry:</label>
        <span>{{ vm.industry or "—" }}</span>
        <input type="hidden" name="industry" value="{{ vm.industry }}">
      </div>
      <div><label>Hypothesis:</label>
        <span>{{ vm.hypothesis_label or "(none)" }}</span>
        <input type="hidden" name="hypothesis_label" value="{{ vm.hypothesis_label or '' }}">
      </div>
      <div><label>Rationale &#9733;</label>
```

- [ ] **Step 5: Run tests to verify GREEN**

```bash
python -m pytest tests/web/test_routes/test_trades_route.py::test_entry_form_renders_hidden_hypothesis_label_input_when_resolved tests/web/test_routes/test_trades_route.py::test_entry_form_renders_none_display_when_label_unresolved -v
```

Expected: 2 passed.

- [ ] **Step 6: Run the full fast suite**

```bash
python -m pytest -m "not slow" -q
```

Expected: 1372 passed, 1 skipped (1370 + 2 new tests).

- [ ] **Step 7: Observable-verification grep + commit**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 3\.'
```

Expected: empty.

```bash
git add swing/web/templates/partials/trade_entry_form.html.j2 \
        tests/web/test_routes/test_trades_route.py
git commit -m "$(cat <<'EOF'
feat(web): Task 3.1 — trade_entry_form template renders hypothesis row + hidden input

Phase 4.5: read-only display row between industry and rationale blocks.
Hidden input value="" + visible "(none)" when vm.hypothesis_label is
None; canonical-prefix label otherwise. Mirrors sector/industry pattern;
no edit affordance per locked decision §3.
EOF
)"
```

Re-run the grep to confirm one matching subject line.

---

## Task 4: POST handler thread + soft-warn round-trip + ToCToU snapshot-trust + re-render preservation (`entry_post`)

**Files:**
- Modify: `swing/web/routes/trades.py` (add Form param at `entry_post`; pass to `EntryRequest`; add to `form_values` in soft-warn path)
- Create: `tests/web/test_routes/test_trade_entry_hypothesis_thread.py`

(Per Codex R1 Major 4: this task absorbs what was originally a separate "Task 5: regression-pin tests." TDD-disciplined RED-tests-drive-impl: **Tests 4.1 and 4.3 are RED before Task 4's impl edits and GREEN after** — those two drive the per-task TDD red-green cycle. **Tests 4.2 and 4.4 are regression pins that are already-GREEN-after-Task-3** because they exercise no Task-4-specific impl change: 4.2 verifies the no-match → NULL contract that holds even when `EntryRequest.hypothesis_label` defaults to None; 4.4 verifies the rationale-fail re-render path which routes through `build_entry_form_vm` + template (both shipped by Tasks 2 + 3). Co-locating them in Task 4 is thematic grouping, NOT a TDD claim about them. Per Codex R2 Major 1: the plan's effective behavior is 2 RED + 2 GREEN pre-Task-4-impl, 4 GREEN post-Task-4-impl. This is internally consistent and accurately stated.)

**The plan uses a load-bearing constant for the snapshot-trust test:**

```python
SNAPSHOT_TEST_LABEL = "Phase 4.5 snapshot test label - matcher does not emit this string"
```

This string is structurally unique — the matcher's `suggested_label_descriptive` for ANY (registry, candidate) shape begins with one of `"A+ baseline"`, `"Near-A+ defensible: extension test"`, `"Sub-A+ VCP-not-formed"`, or `"Capital-blocked: smaller-position test"` (per `swing/recommendations/hypothesis.py:48-51`). The snapshot test label is plain ASCII, single-spaced, no Cf/Cc characters; `canonicalize_hypothesis_label` returns it unchanged.

**Discriminating-test sanity check:** *"Would these tests fail if the implementation never threaded the value through OR if the route silently re-resolved at submit instead of trusting the snapshot?"* — Yes.

- **Test 4.1 (snapshot-trust persistence; per Codex R1 Major 2 + Major 3).** POSTs `/trades/entry` for AAPL (which has a seeded A+ recommendation; matcher would emit `"A+ baseline (aplus)"`) with `hypothesis_label=SNAPSHOT_TEST_LABEL` (operator-supplied snapshot that the matcher would NEVER emit). Asserts the persisted `Trade.hypothesis_label` equals `SNAPSHOT_TEST_LABEL` exactly. Three-way discrimination:
  - Bug A (no Form param / no thread): persisted = NULL → fails.
  - Bug B (route re-resolves at submit, ignoring snapshot): persisted = `"A+ baseline (aplus)"` ≠ SNAPSHOT_TEST_LABEL → fails.
  - Bug C (route truncates / re-canonicalizes destructively): persisted ≠ SNAPSHOT_TEST_LABEL → fails.
  - Fix: persisted = SNAPSHOT_TEST_LABEL → passes.

- **Test 4.2 (no-match → NULL; effective-contract pin; brief §4.11).** POSTs `/trades/entry` for ZZZ (no candidate row) with `hypothesis_label=""`. Asserts persisted `Trade.hypothesis_label` is `NULL`. Empirically verifies the empty-string-→-`None`-→-`NULL` chain through the route boundary's `or None` coercion + `record_entry`'s `canonicalize_hypothesis_label`. Note: this test does NOT discriminate "thread vs no-thread" by itself (both bug-present-no-thread and bug-fixed-thread persist NULL on a no-match POST); its purpose is to PIN the no-match contract going forward and catch a regression where a future change persisted a non-NULL placeholder (e.g., empty string `""` instead of `NULL`).

- **Test 4.3 (soft-warn round-trip via fragment-faithful resubmit; per Codex R1 Major 1).** Sets up enough open positions to trip soft-warn. POSTs `/trades/entry` for AAPL with `hypothesis_label=SNAPSHOT_TEST_LABEL`. Asserts the response is a soft-warn confirm fragment. **Parses the fragment's hidden inputs verbatim** (regex over `<input type="hidden" name="..." value="...">` tags) — does NOT hand-craft the second POST. Submits `force=true` plus the fragment-derived hidden-input dict. Asserts the persisted `Trade.hypothesis_label` equals `SNAPSHOT_TEST_LABEL`.
  - Bug (`form_values` omits `hypothesis_label`): the confirm fragment emits no hidden input for the field; the fragment-parsed second POST submits with no `hypothesis_label` key; the persisted value is NULL → fails.
  - The fragment-faithful approach catches a class of bugs where the field IS in `form_values` but is misspelled (e.g. `"hypothesis"` not `"hypothesis_label"`): the hand-crafted `hypothesis_label=SNAPSHOT_TEST_LABEL` second POST would mask the misspelling; the fragment-parsed POST replays whatever names the server emits, exposing the bug.

- **Test 4.4 (rationale-fail re-render preservation).** POSTs `/trades/entry` with `rationale=other` and no `notes` (T4 contract violation). Asserts response is 400 + re-rendered form, AND the re-render carries `name="hypothesis_label" value="A+ baseline (aplus)"` exactly. Verifies the `_rerender_entry_form_with_error` path's call to `build_entry_form_vm` re-resolves the matcher deterministically and the new VM field flows through the template.
  - Bug (build_entry_form_vm regresses on the resolution): re-render's hidden input value is empty or stale → fails.
  - Bug (re-render path stops calling build_entry_form_vm): re-render lacks the field entirely → fails.

**Compounding-confound check (brief §4.3, §5.1):** Test 4.1's `SNAPSHOT_TEST_LABEL` is structurally unique — no matcher output, registry default, fallback, or tiebreaker produces this exact string. The persisted-equals-submitted assertion is unambiguous. Test 4.4's `"A+ baseline (aplus)"` is the matcher's deterministic output for the seed fixture; same uniqueness argument as Tasks 2 + 3.

**Watch item — soft-warn round-trip vacuousness (brief §5.2):** Test 4.3's structure REQUIRES (a) parsing the actual confirm-fragment hidden inputs (Codex R1 Major 1 fix), (b) the second-submit-then-DB-inspection chain. A weaker test that only asserted "the hidden input appears in the first response" would pass with `form_values` populated but Form param missing. A weaker test that hand-crafted the second POST would pass even if the soft-warn fragment misspelled the field name. **Both the fragment-parse AND the post-force-submit DB inspection are load-bearing.**

- [ ] **Step 1: Verify pre-Task-4 baseline**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 4\.'
python -m pytest -m "not slow" -q 2>&1 | tail -3
```

Expected:
- Subject-only grep: empty.
- Fast suite: 1372 passed, 1 skipped.

- [ ] **Step 2: Write the failing integration tests**

Create `tests/web/test_routes/test_trade_entry_hypothesis_thread.py`:

```python
"""Phase 4.5 — POST /trades/entry threads hypothesis_label through to
record_entry; ToCToU snapshot-trust; soft-warn confirm round-trip
preserves the snapshot AS-IS through fragment-faithful resubmit;
rationale-fail re-render preserves resolved label.

Discriminating tests use a UNIQUE non-matcher SNAPSHOT_TEST_LABEL so
three-way discrimination is observable:
  - bug A (no thread):           persisted = NULL
  - bug B (route re-resolves):   persisted = matcher's "A+ baseline (aplus)"
  - bug C (form_values omits / misspells in soft-warn): NULL after force
  - fix:                         persisted = SNAPSHOT_TEST_LABEL
"""
from __future__ import annotations

import re
from datetime import datetime
from pathlib import Path

from fastapi.testclient import TestClient

from swing.data.db import connect
from swing.data.models import Trade, WatchlistEntry
from swing.data.repos.trades import insert_trade_with_event
from swing.data.repos.watchlist import upsert_watchlist_entry
from swing.web.app import create_app
from swing.web.price_cache import PriceCache, PriceSnapshot

# Phase 4.5 — load-bearing constant for snapshot-trust discrimination.
# Plain ASCII, single-spaced, no Cf/Cc → canonicalize_hypothesis_label
# returns it unchanged. Distinct from any matcher output (matcher labels
# always begin with one of "A+ baseline" / "Near-A+ defensible: extension
# test" / "Sub-A+ VCP-not-formed" / "Capital-blocked: smaller-position
# test"). See plan §"Matcher output for the seed fixture".
SNAPSHOT_TEST_LABEL = (
    "Phase 4.5 snapshot test label - matcher does not emit this string"
)


def _seed_aplus_pipeline(db_path: Path, ticker: str) -> None:
    conn = connect(db_path)
    try:
        with conn:
            cur = conn.execute(
                """INSERT INTO evaluation_runs
                   (run_ts, data_asof_date, action_session_date, finviz_csv_path,
                    tickers_evaluated, aplus_count, watch_count, skip_count,
                    excluded_count, error_count,
                    rs_universe_version, rs_universe_hash)
                   VALUES (?, ?, ?, NULL, 1, 1, 0, 0, 0, 0, 'v1', 'h1')""",
                ("2026-04-17T21:49:00", "2026-04-17", "2026-04-20"),
            )
            eval_id = cur.lastrowid
            conn.execute(
                """INSERT INTO candidates (evaluation_run_id, ticker, bucket,
                   close, pivot, initial_stop, rs_method)
                   VALUES (?, ?, 'aplus', 180.0, 181.0, 170.0, 'universe')""",
                (eval_id, ticker),
            )
            conn.execute(
                """INSERT INTO pipeline_runs
                   (started_ts, finished_ts, trigger, data_asof_date,
                    action_session_date, state, lease_token,
                    evaluation_run_id)
                   VALUES ('2026-04-17T21:49:00', '2026-04-17T21:55:00',
                           'scheduled', '2026-04-17', '2026-04-20',
                           'complete', 'tok', ?)""",
                (eval_id,),
            )
    finally:
        conn.close()


def _read_persisted_hypothesis_label(db_path: Path, ticker: str) -> str | None:
    """Read the most-recent trade row for ticker; return its
    hypothesis_label (or None if no row)."""
    conn = connect(db_path)
    try:
        row = conn.execute(
            "SELECT hypothesis_label FROM trades WHERE ticker = ? "
            "ORDER BY id DESC LIMIT 1",
            (ticker,),
        ).fetchone()
        return row[0] if row is not None else None
    finally:
        conn.close()


def _parse_hidden_inputs(html: str) -> dict[str, str]:
    """Extract every <input type="hidden" name="..." value="..."> tag
    into a dict. Mirrors what a real browser would submit for the form
    that contains the parsed fragment (Codex R1 Major 1: the soft-warn
    round-trip MUST replay the server's actual hidden-input names, not
    a hand-crafted set that masks misspellings).

    Coupling acknowledgment (Codex R2 Minor 1): the regex pins the
    expected Jinja2 emission shape — `type="hidden"` first, then
    `name="..."`, then `value="..."`, double-quoted, single ASCII
    space between attributes. soft_warn_confirm.html.j2 emits exactly
    this shape (see lines 32-36 of that template). If a future template
    change reorders attributes or switches quoting, this helper will
    silently miss inputs and the round-trip test will fail with a
    confusing "missing key" error rather than a clean signal. That is
    an acceptable maintenance cost for V1 — the alternative is parsing
    HTML with a real DOM library, which adds a test dependency that
    isn't justified at this scope. Document this coupling near
    soft_warn_confirm.html.j2 if a reviewer asks; do not add a
    backwards-compatibility shim here.
    """
    return dict(re.findall(
        r'<input\s+type="hidden"\s+name="([^"]+)"\s+value="([^"]*)"',
        html,
    ))


def test_post_entry_snapshot_trust_persists_operator_submitted_label(
    seeded_db, monkeypatch,
):
    """Discriminating snapshot-trust (per Codex R1 Major 2 + Major 3).

    POST with hypothesis_label=SNAPSHOT_TEST_LABEL (a string the
    matcher would never emit) for AAPL (which has an active A+
    recommendation; matcher would emit "A+ baseline (aplus)" if
    re-resolved at submit time). Persisted value MUST equal the
    operator-submitted snapshot, NOT the matcher's current output.

    Three-way discrimination:
    - Bug A (no Form param / no thread): persisted = NULL → fails.
    - Bug B (route re-resolves at submit): persisted = "A+ baseline
      (aplus)" ≠ SNAPSHOT_TEST_LABEL → fails.
    - Fix: persisted = SNAPSHOT_TEST_LABEL → passes.
    """
    cfg, cfg_path = seeded_db
    _seed_aplus_pipeline(cfg.paths.db_path, ticker="AAPL")
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=180.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r_post = client.post("/trades/entry", data={
            "ticker": "AAPL",
            "entry_date": "2026-04-15",
            "entry_price": "180.0",
            "shares": "1",
            "initial_stop": "170.0",
            "rationale": "aplus-setup",
            "hypothesis_label": SNAPSHOT_TEST_LABEL,
            "sector": "",
            "industry": "",
            "origin": "watchlist",
        }, headers={"HX-Request": "true"})
        assert r_post.status_code in (200, 201, 302), r_post.text

    persisted = _read_persisted_hypothesis_label(cfg.paths.db_path, "AAPL")
    assert persisted == SNAPSHOT_TEST_LABEL, (
        "snapshot-at-entry-surface contract: persisted hypothesis_label "
        f"must equal the operator-submitted snapshot exactly; got {persisted!r}"
    )


def test_post_entry_persists_NULL_for_non_matching_ticker(
    seeded_db, monkeypatch,
):
    """Effective-contract pin (brief §4.11). Empty-string-→-None-→-NULL
    chain through the route boundary's `or None` coercion plus
    record_entry's canonicalize_hypothesis_label.

    Note: this test does NOT discriminate "thread vs no-thread" (both
    bug-present and bug-fixed persist NULL on a no-match POST). Its
    purpose is to PIN the no-match contract going forward and catch a
    regression where future code persisted a non-NULL placeholder
    (e.g., persisted "" instead of NULL).
    """
    cfg, cfg_path = seeded_db
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "ZZZ": PriceSnapshot(
                ticker="ZZZ", price=100.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r_post = client.post("/trades/entry", data={
            "ticker": "ZZZ",
            "entry_date": "2026-04-15",
            "entry_price": "100.0",
            "shares": "1",
            "initial_stop": "90.0",
            "rationale": "vcp-breakout",
            "hypothesis_label": "",
            "sector": "",
            "industry": "",
            "origin": "watchlist",
        }, headers={"HX-Request": "true"})
        assert r_post.status_code in (200, 201, 302), r_post.text

    persisted = _read_persisted_hypothesis_label(cfg.paths.db_path, "ZZZ")
    assert persisted is None, (
        f"non-matching ticker must persist NULL hypothesis_label; got {persisted!r}"
    )


def test_post_entry_soft_warn_round_trip_via_fragment_faithful_resubmit(
    seeded_db, monkeypatch,
):
    """Discriminating soft-warn round-trip (per Codex R1 Major 1 +
    Major 2). With soft_warn_open exceeded:

    1. First POST submits hypothesis_label=SNAPSHOT_TEST_LABEL.
    2. Server returns the soft-warn confirm fragment.
    3. Test PARSES the fragment's hidden inputs (does NOT hand-craft);
       this catches misspellings or omissions of any field name.
    4. Test submits the parsed dict + force=true.
    5. Asserts persisted == SNAPSHOT_TEST_LABEL.

    Bug A (form_values omits hypothesis_label): fragment lacks the
    hidden input; parsed dict has no `hypothesis_label` key; second POST
    submits without it; route's `Form("")` default → `or None` → NULL
    persisted → fails.
    Bug B (form_values misspells the key): fragment emits
    name="hypothesis" (not "hypothesis_label"); the route's Form param
    receives the default ""; persisted = NULL → fails. (Hand-crafted
    second POST would mask this; fragment-faithful resubmit exposes it.)
    Bug C (route re-resolves at submit): persisted = "A+ baseline
    (aplus)" ≠ SNAPSHOT_TEST_LABEL → fails.
    Fix: persisted = SNAPSHOT_TEST_LABEL → passes.
    """
    cfg, cfg_path = seeded_db
    _seed_aplus_pipeline(cfg.paths.db_path, ticker="AAPL")

    # Trip soft-warn (default soft_warn_open=4) by seeding 4 unrelated
    # open trades.
    conn = connect(cfg.paths.db_path)
    try:
        with conn:
            for t in ("MSFT", "NVDA", "AMD", "TSLA"):
                insert_trade_with_event(
                    conn,
                    Trade(
                        id=None, ticker=t, entry_date="2026-04-10",
                        entry_price=100.0, initial_shares=1,
                        initial_stop=90.0, current_stop=90.0,
                        status="open",
                        watchlist_entry_target=None,
                        watchlist_initial_stop=None,
                        notes=None,
                    ),
                    event_ts="2026-04-10T09:30:00",
                )
    finally:
        conn.close()

    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=180.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        # First POST → soft-warn confirm fragment.
        r_first = client.post("/trades/entry", data={
            "ticker": "AAPL",
            "entry_date": "2026-04-15",
            "entry_price": "180.0",
            "shares": "1",
            "initial_stop": "170.0",
            "rationale": "aplus-setup",
            "hypothesis_label": SNAPSHOT_TEST_LABEL,
            "sector": "",
            "industry": "",
            "origin": "watchlist",
        }, headers={"HX-Request": "true"})
        assert r_first.status_code == 200
        # Pre-flight: confirm fragment carries the operator's snapshot
        # AS-IS in a hidden input named exactly "hypothesis_label".
        assert (
            f'name="hypothesis_label" value="{SNAPSHOT_TEST_LABEL}"'
            in r_first.text
        ), (
            "soft-warn confirm fragment must emit hypothesis_label hidden "
            f"input with snapshot value; first response: {r_first.text!r}"
        )

        # Fragment-faithful resubmit (Codex R1 Major 1): parse the
        # fragment's hidden inputs verbatim; submit them + force=true.
        # This is what a real browser does when the operator clicks
        # "Submit anyway" on the confirm form.
        fragment_data = _parse_hidden_inputs(r_first.text)
        assert fragment_data.get("hypothesis_label") == SNAPSHOT_TEST_LABEL, (
            f"fragment must carry hypothesis_label key; got {fragment_data!r}"
        )
        fragment_data["force"] = "true"

        r_second = client.post(
            "/trades/entry", data=fragment_data,
            headers={"HX-Request": "true"},
        )
        assert r_second.status_code in (200, 201, 302), r_second.text

    persisted = _read_persisted_hypothesis_label(cfg.paths.db_path, "AAPL")
    assert persisted == SNAPSHOT_TEST_LABEL, (
        "post-force-submit DB row MUST carry the operator's snapshot "
        f"(soft-warn round-trip preservation); got {persisted!r}"
    )


def test_post_entry_rationale_fail_re_render_preserves_resolved_label(
    seeded_db, monkeypatch,
):
    """Re-render preservation (brief §3.E final bullet). A rationale-
    validation failure (rationale='other' without notes) returns 400 +
    re-rendered form. The rebuild path calls build_entry_form_vm,
    which re-resolves the matcher deterministically; the response must
    carry name="hypothesis_label" value="A+ baseline (aplus)" exactly.

    Bug (build_entry_form_vm regressed on resolution): re-render's
    hidden-input value is empty or stale → fails.
    Bug (re-render path stops calling build_entry_form_vm): re-render
    lacks the field entirely → fails.

    Note: this test does not depend on Task 4's Form-param edits to
    pass — the rationale-fail path runs before the EntryRequest
    construction. After Task 3 the test would already pass; we co-locate
    it in Task 4 for thematic grouping with the other POST-level
    integration tests (per Codex R1 Major 4 consolidation).
    """
    cfg, cfg_path = seeded_db
    _seed_aplus_pipeline(cfg.paths.db_path, ticker="AAPL")
    monkeypatch.setattr(PriceCache, "get_many",
        lambda self, tickers, deadline_seconds, *, executor=None: {
            "AAPL": PriceSnapshot(
                ticker="AAPL", price=180.0, asof=datetime.now(),
                is_stale=False, source="live",
            ),
        })

    app = create_app(cfg, cfg_path)
    with TestClient(app) as client:
        r_fail = client.post("/trades/entry", data={
            "ticker": "AAPL",
            "entry_date": "2026-04-15",
            "entry_price": "180.0",
            "shares": "1",
            "initial_stop": "170.0",
            "rationale": "other",
            # notes intentionally omitted → triggers T4 contract failure.
            "hypothesis_label": SNAPSHOT_TEST_LABEL,  # arbitrary input value
            "sector": "",
            "industry": "",
            "origin": "watchlist",
        }, headers={"HX-Request": "true"})
        assert r_fail.status_code == 400, r_fail.text
        # Re-render's hidden input carries the matcher-RE-RESOLVED label
        # (NOT the operator's submitted SNAPSHOT_TEST_LABEL). The
        # rationale-fail path goes through build_entry_form_vm, which
        # re-resolves deterministically; per snapshot-at-entry-surface
        # decision §2.4, this re-resolve is correct because the DB state
        # has not changed and the matcher is pure.
        assert (
            'name="hypothesis_label" value="A+ baseline (aplus)"'
            in r_fail.text
        ), (
            "rationale-fail re-render must carry matcher-resolved label "
            f"in hidden input; response: {r_fail.text!r}"
        )
```

- [ ] **Step 3: Run tests to verify FAIL**

```bash
python -m pytest tests/web/test_routes/test_trade_entry_hypothesis_thread.py -v
```

Expected: **2 fail, 2 pass**.
- 4.1 (snapshot-trust persistence) **FAILS**: `entry_post` lacks the `hypothesis_label` Form param → FastAPI silently drops the unknown field; `EntryRequest.hypothesis_label = None` (dataclass default); persisted as NULL ≠ SNAPSHOT_TEST_LABEL.
- 4.2 (no-match → NULL) **PASSES** pre-impl: the route already persists NULL when `EntryRequest.hypothesis_label = None`. This is the regression-pin test that explicitly acknowledges in its docstring that it is non-discriminating "thread vs no-thread" — its purpose is to PIN the no-match contract going forward.
- 4.3 (soft-warn round-trip) **FAILS**: confirm fragment's `form_values` dict doesn't yet include `hypothesis_label`; the pre-flight assertion `f'name="hypothesis_label" value="{SNAPSHOT_TEST_LABEL}"' in r_first.text` fails.
- 4.4 (rationale-fail re-render) **PASSES** pre-impl, given Task 3 GREEN: the rationale-fail path goes through `build_entry_form_vm` (which Task 2 extended) + the template (which Task 3 extended); the route's missing `Form("")` param is irrelevant because the rationale check fires before EntryRequest construction. This test is co-located in Task 4 for thematic grouping; it is NOT a Task-4-driven RED test.

**Summary: 2 RED tests drive Task 4's impl (4.1 and 4.3); 2 already-GREEN regression pins (4.2 and 4.4) co-locate here. Post-Task-4-impl: all 4 GREEN.**

- [ ] **Step 4: Add `hypothesis_label` Form param to `entry_post`**

Edit `swing/web/routes/trades.py`. Find the `entry_post` signature at line 228 — specifically the `industry: str = Form(""),` line at line 255:

```python
    sector: str = Form(""),
    industry: str = Form(""),
    # Task 8 (R4-Major-1) — origin discriminator survives POST round-trips.
```

Replace with:

```python
    sector: str = Form(""),
    industry: str = Form(""),
    # Phase 4.5 — hypothesis_label snapshot from hidden form field
    # populated by build_entry_form_vm at form-render time (snapshot-
    # at-entry-surface ToCToU pattern). Default "" so existing form
    # submitters (CLI tests; bare cURL) keep working. Empty-string is
    # coerced to None at the EntryRequest construction site below;
    # record_entry's canonicalize_hypothesis_label persists NULL.
    hypothesis_label: str = Form(""),
    # Task 8 (R4-Major-1) — origin discriminator survives POST round-trips.
```

- [ ] **Step 5: Pass `hypothesis_label` to `EntryRequest`**

In the same file, find the `EntryRequest(...)` literal at line 360. The existing fields end with `industry=industry,`:

```python
    req = EntryRequest(
        ticker=ticker.upper(),
        entry_date=entry_date,
        entry_price=entry_price,
        shares=shares,
        initial_stop=initial_stop,
        watchlist_entry_target=watchlist_target,
        watchlist_initial_stop=watchlist_stop,
        notes=notes,
        rationale=rationale,
        event_ts=datetime.now().isoformat(timespec="seconds"),
        chart_pattern_operator=cp_operator_value,
        chart_pattern_algo=cp_algo_value,
        chart_pattern_algo_confidence=cp_conf_value,
        chart_pattern_classification_pipeline_run_id=cp_anchor_value,
        sector=sector,
        industry=industry,
    )
```

Replace with:

```python
    req = EntryRequest(
        ticker=ticker.upper(),
        entry_date=entry_date,
        entry_price=entry_price,
        shares=shares,
        initial_stop=initial_stop,
        watchlist_entry_target=watchlist_target,
        watchlist_initial_stop=watchlist_stop,
        notes=notes,
        rationale=rationale,
        event_ts=datetime.now().isoformat(timespec="seconds"),
        # Phase 4.5 — empty-string-to-None coercion at the route boundary.
        # record_entry's canonicalize_hypothesis_label also handles
        # empty/whitespace-only → None, but explicit boundary coercion
        # documents the contract.
        hypothesis_label=hypothesis_label or None,
        chart_pattern_operator=cp_operator_value,
        chart_pattern_algo=cp_algo_value,
        chart_pattern_algo_confidence=cp_conf_value,
        chart_pattern_classification_pipeline_run_id=cp_anchor_value,
        sector=sector,
        industry=industry,
    )
```

- [ ] **Step 6: Add `hypothesis_label` to soft-warn `form_values`**

In the same file, find the `form_values = { ... }` dict in the `SoftWarnError` block (line 413). The existing dict ends with `"open_count": actual_open,` then `"soft_warn"`, `"hard_cap"`. Add the field next to `sector`/`industry` per brief §3.D:

Find:
```python
                # Task 6 — sector/industry must round-trip through the
                # soft-warn confirm so the force=true resubmit persists
                # the original snapshot AS-IS. soft_warn_confirm.html.j2
                # iterates form_values with an exclusion list; adding
                # these keys auto-emits hidden inputs.
                "sector": sector,
                "industry": industry,
                # Task 8 (R4-Major-1) — origin must round-trip through the
```

Replace with:
```python
                # Task 6 — sector/industry must round-trip through the
                # soft-warn confirm so the force=true resubmit persists
                # the original snapshot AS-IS. soft_warn_confirm.html.j2
                # iterates form_values with an exclusion list; adding
                # these keys auto-emits hidden inputs.
                "sector": sector,
                "industry": industry,
                # Phase 4.5 — hypothesis_label must round-trip through
                # the soft-warn confirm so the force=true resubmit
                # persists the SAME label the operator saw at first
                # submit. Without this entry, soft_warn_confirm.html.j2
                # would emit no hidden input for the field, the second
                # POST's hypothesis_label would default to "", and the
                # persisted Trade.hypothesis_label would be NULL —
                # silently dropping the snapshot. Multi-path-data-
                # ingestion lesson 2026-04-29.
                "hypothesis_label": hypothesis_label,
                # Task 8 (R4-Major-1) — origin must round-trip through the
```

- [ ] **Step 7: Run tests to verify GREEN**

```bash
python -m pytest tests/web/test_routes/test_trade_entry_hypothesis_thread.py -v
```

Expected: 4 passed (the 2 originally-RED tests now GREEN; the 2 always-GREEN regression-pin tests still GREEN).

- [ ] **Step 8: Run the existing trade-entry route tests to confirm no regression**

```bash
python -m pytest tests/web/test_routes/test_trades_route.py tests/web/test_routes/test_trade_entry_chart_pattern.py tests/web/test_trades_integration.py -v
```

Expected: all passing.

- [ ] **Step 9: Run the full fast suite**

```bash
python -m pytest -m "not slow" -q
```

Expected: 1376 passed, 1 skipped (1372 + 4 new tests).

- [ ] **Step 9b: Verify ruff baseline preserved**

```bash
ruff check swing/ 2>&1 | tail -5
```

Expected: 91 errors (no change vs baseline).

- [ ] **Step 9c: Multi-path-data-ingestion full-path audit (brief §5.4)**

```bash
grep -rn "hypothesis_label" swing/ | grep -v "^Binary file"
```

Confirm the writers to `trades.hypothesis_label` are exhaustively:

1. `swing/cli.py` — `swing trade entry` CLI (existing pre-Phase-4.5 path).
2. `swing/web/routes/trades.py` — `entry_post` (NEW Phase-4.5 path).
3. `swing/trades/entry.py:201` — `record_entry` calls `canonicalize_hypothesis_label` at the persistence boundary; `EntryRequest.hypothesis_label` is the only input.
4. `swing/data/repos/trades.py` — repo writers persist `Trade.hypothesis_label` AS-IS.

Reference-only readers (`swing/journal/review.py`, `swing/journal/analyze.py`, `swing/web/view_models/dashboard.py`) consume the field but don't write it. This audit closes brief §5.4.

- [ ] **Step 10: Observable-verification grep + commit**

```bash
git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 4\.'
```

Expected: empty.

```bash
git add swing/web/routes/trades.py \
        tests/web/test_routes/test_trade_entry_hypothesis_thread.py
git commit -m "$(cat <<'EOF'
feat(web): Task 4.1 — entry_post threads hypothesis_label through EntryRequest + soft-warn round-trip + ToCToU snapshot-trust

Phase 4.5: Form("") param at the route boundary; empty-string-to-None
coercion before EntryRequest; record_entry's canonicalize_hypothesis_label
applies NFC + control-byte rules. Soft-warn form_values dict gains
hypothesis_label so soft_warn_confirm.html.j2 auto-emits the hidden
input on the force=true resubmit (multi-path-data-ingestion discipline).

Tests cover four contracts: (a) snapshot-at-entry-surface trust —
operator-submitted snapshot persists AS-IS, route does not re-resolve;
(b) no-match → NULL effective contract; (c) soft-warn round-trip via
fragment-faithful resubmit (parses confirm-fragment hidden inputs
verbatim, catches misspellings/omissions); (d) rationale-fail re-render
preserves matcher-resolved label via build_entry_form_vm rebuild.
EOF
)"
```

Re-run the grep to confirm one matching subject line.

---

(Task 5 from the original plan was eliminated per Codex R1 Major 4. Its 2 regression-pin tests are now Tests 4.2 and 4.4 above, co-located in Task 4 for thematic grouping. Per-task TDD discipline holds: every test in Task 4 is RED-or-already-GREEN before the task's impl lands; all 4 are GREEN after.)

---

## Self-review checklist (run before declaring plan complete)

Per writing-plans skill:

**1. Spec coverage:** Brief §3.E enumerates 9-10 discriminating tests. Mapping (post-Codex-R1 consolidation: Task 5 eliminated; Task 4 absorbed its 2 tests):
- (a) lookup_active_recommendation_label returns exact label for matching → Task 1 test 1 ✓
- (b) lookup_active_recommendation_label returns None for non-matching → Task 1 test 2 ✓
- (c) build_entry_form_vm populates exact label for matching → Task 2 test 1 ✓
- (d) build_entry_form_vm returns None for non-matching → Task 2 test 2 ✓
- (e) Form template renders hidden input with exact label → Task 3 test 1 ✓
- (f) Form template renders (none) display → Task 3 test 2 ✓
- (g) POST persists operator-submitted snapshot (snapshot-trust; ToCToU) → Task 4 test 1 ✓ (strengthened per Codex R1 M2 from prefix-match canonical-label to a unique non-matcher snapshot label)
- (h) POST persists NULL for non-matching → Task 4 test 2 ✓
- (i) POST soft-warn round-trip preserves snapshot AS-IS via fragment-faithful resubmit → Task 4 test 3 ✓ (strengthened per Codex R1 M1 from hand-crafted resubmit to fragment-parsed resubmit)
- (j) Re-render preservation: rationale-fail preserves matcher-resolved label → Task 4 test 4 ✓

10/10 specified tests covered.

Brief §3.A-D (helper extraction; VM extension; template render; POST handler thread; soft-warn round-trip): all covered by Tasks 1-4 production-code edits.

Brief §3 V1 out-of-scope: nothing in the plan touches V2-deferred items (manual override surface, pre-fill banner, historical backfill, broader helper extraction, performance optimization, briefing template).

**2. Placeholder scan:** Grep'd for "TBD"/"TODO"/"implement later"/"add appropriate"/"similar to Task" in the plan body — none present. Every code block contains the actual content.

**3. Type consistency:** `lookup_active_recommendation_label` signature `(conn, *, ticker: str, starting_equity: float) -> str | None` is consistent across Task 1 (definition + import in cli.py + Task 2 import in trades.py + tests). `vm.hypothesis_label` field name is consistent across Task 2 (dataclass), Task 3 (Jinja template), Task 4 (Form param + EntryRequest field), and tests. `EntryRequest.hypothesis_label` matches the existing field at `swing/trades/entry.py:94`.

**4. Risk surface verification:** Pre-dispatch baseline confirmed:
- HEAD `ec93af2`, clean tree.
- 1366 passed, 1 skipped.
- Helper at `swing/cli.py:339`, no external importers (underscore-prefixed).
- `base.html.j2` does NOT reference `hypothesis_label` — 5-VM rule does NOT apply (brief §5.7 watch item resolved).
- `EntryRequest.hypothesis_label` exists at `swing/trades/entry.py:94`.
- `Trade.hypothesis_label` exists at `swing/data/models.py:77`.
- `record_entry` calls `canonicalize_hypothesis_label` at `swing/trades/entry.py:201`.
- No hand-constructed `TradeEntryFormVM(...)` test sites — adding a default-valued field is risk-free for test fixups.

---

## Execution Handoff

Plan complete and saved to `docs/superpowers/plans/2026-04-30-hypothesis-label-web-form-plan.md`. Two execution options:

**1. Subagent-Driven (recommended)** — Dispatch a fresh subagent per task; review between tasks; fast iteration. Recommended for this plan because each task ships a discrete, independently-verifiable behavior.

**2. Inline Execution** — Execute tasks in this session using executing-plans; batch execution with checkpoints for review.

Operator: when ready to execute, dispatch `copowers:executing-plans` against this plan path.
