# `build_watchlist` Mixed-Anchor Fix — Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Close the last surface of the mixed-anchor bug class (Bug 7 family). `build_watchlist` in `swing/web/view_models/watchlist.py` still binds its `candidates_by_ticker` (which feeds flag tags + criteria for the standalone `/watchlist` page) via "latest evaluation_run by run_ts," not via `pipeline_runs.evaluation_run_id`. Same disease that today_decisions, candidates_by_ticker on the dashboard, and `_step_export` had pre-Tranche-C; the FK now exists, this surface just hasn't been migrated. One small commit (TDD), one adversarial review pass, done.
**Expected duration:** ~45–75 minutes.
**Prepared:** 2026-04-25 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions; the **Phase isolation** invariant (`swing/data/` and `swing/trades/` are read-only), conventional commits, no-amend, no `--no-verify`, no Claude co-author footer.
2. `swing/web/view_models/watchlist.py` — the file you're editing. Read end-to-end (151 lines). Note that `build_watchlist_expanded` at lines 77–150 ALREADY implements the proper FK-binding pattern (post-Tranche-C). Your fix mirrors that pattern in the simpler `build_watchlist` function above it.
3. `swing/web/view_models/dashboard.py` lines 95–181 — the canonical template for this fix. Read it carefully; the `pipeline_eval_row` lookup + `candidates_by_ticker` binding at lines 107–181 is the exact shape your edit needs to take in `build_watchlist`.
4. `tests/web/test_view_models/test_dashboard_t4_candidates_eval_scoping.py` — the canonical regression-test template. Your watchlist regression test mirrors this structure.
5. `docs/orchestrator-context.md` — orchestrator handoff file. Skim §"Recent decisions and framings" and §"Anti-patterns to avoid" — particularly the "Vacuous regression tests" and "Drafting briefs that reference 'uncommitted' files" entries.

**Skill posture.**
- DO invoke `superpowers:verification-before-completion` before declaring done.
- DO invoke `copowers:adversarial-critic` after the fix commit lands. Standing convention; even small commits get one adversarial pass. Iterate to `NO_NEW_CRITICAL_MAJOR`; fix any findings in a NEW commit per no-amend rule.
- Do NOT invoke `copowers:brainstorming` or `copowers:writing-plans` — scope is fully specified by this brief.

---

## 1. Strategic context (compressed)

The mixed-anchor bug class has now been closed on three surfaces in Tranche C:

| Surface | Commit | What it bound to |
|---|---|---|
| `today_decisions` (dashboard recommendations) | `a4b94a4` | `pipeline_runs.evaluation_run_id` |
| Dashboard `candidates_by_ticker` (flag tags) | `1cfc117` (Major 2) | `pipeline_runs.evaluation_run_id` |
| `_step_export` briefing recommendations | `1cfc117` (Major 1) | `pipeline_runs.evaluation_run_id` |
| `build_watchlist_expanded` (criteria panel) | `4678398` (chart-scope resolver fix) | `pipeline_runs.evaluation_run_id` (via heuristic linkage) |

`build_watchlist` (the standalone `/watchlist` page's main read) is the last surface still using the legacy `SELECT id FROM evaluation_runs ORDER BY run_ts DESC LIMIT 1` query at line 50. This is observably stale-anchored: if the operator runs the pipeline at 06:00, then runs `swing eval` standalone at 14:00, the `/watchlist` page renders flag tags from the 14:00 standalone eval, not from the pipeline's own eval. That breaks the cross-surface invariant every other Tranche-C fix established (all UI surfaces bind to the same "what the pipeline charted" anchor).

**No production-incident is forcing this fix.** It's the last item from a closed bug class, deferred per scope discipline during Tranche C and queued in `docs/phase3e-todo.md` "Tranche C deferred items (2026-04-25)." Doing it now closes the class durably.

---

## 2. Scope — single fix, single test, one commit

### In scope

- One edit to `swing/web/view_models/watchlist.py` — replace the `SELECT id FROM evaluation_runs ORDER BY run_ts DESC LIMIT 1` query at line 50 with the `pipeline_runs.evaluation_run_id`-binding pattern from dashboard.py lines 107–114 + 173–181.
- One new test file `tests/web/test_view_models/test_watchlist_eval_scoping.py` — regression test that verifies `build_watchlist` binds via `pipeline_runs.evaluation_run_id` when populated, falls back to latest-eval when no pipeline FK exists.
- One conventional commit landing both. Adversarial review afterwards in a separate commit if fixes are needed.

### Out of scope

- Any modification to `build_watchlist_expanded` (already correct).
- Any modification to `swing/data/`, `swing/trades/`, `swing/pipeline/` (Phase 2 carve-out NOT granted).
- Any other read-path migration. If you discover another surface with the legacy pattern, FLAG in the return report — do NOT silently expand scope.
- Any test reorganization or refactor beyond adding the new test file.
- Any documentation edits beyond what the commit message captures.

---

## 3. Binding conventions

- **Branch:** `main`. No feature branch.
- **Commits:** conventional. **No Claude co-author footer. No `--no-verify`. No amending.** If a hook fails, fix the issue and commit anew.
- **TDD:** failing test first → see fail → minimal implementation → see pass → commit.
- **Tests:** `python -m pytest -m "not slow" -q` must stay green. Current baseline 721 passing on `main` (per `25a796e`).
- **Ruff:** `ruff check swing/` baseline is 81 errors (pre-existing). Don't introduce new violations; don't try to fix the baseline incidentally.
- **Phase isolation:** Touch `swing/web/view_models/watchlist.py` ONLY. No carve-out for `swing/data/` or `swing/trades/` is granted.

---

## 4. Task specification

### 4.1 Failing test first

Create `tests/web/test_view_models/test_watchlist_eval_scoping.py`. Mirror the structure of `tests/web/test_view_models/test_dashboard_t4_candidates_eval_scoping.py` — read that file first to understand the fixture setup pattern.

The test must distinguish pre-fix from post-fix behavior. Setup must satisfy:

1. Insert two evaluation_runs:
   - `E1` (older `run_ts`) with `TICKER_X` in its candidates carrying flag-relevant criteria values (e.g., a passing trend_template and VCP, so `_flag_tags` produces a non-empty tuple — say `("TT✓", "VCP✓")`).
   - `E2` (newer `run_ts`) with `TICKER_X` ABSENT from its candidates (or with criteria values that produce a DIFFERENT non-empty `_flag_tags` tuple — e.g., `("VCP✓",)` only).
2. Insert a `pipeline_runs` row with `state='complete'`, `evaluation_run_id=E1`. (E1 is the pipeline's own eval; E2 is a later standalone eval.)
3. Insert a `watchlist_entries` row for `TICKER_X` (active; `removed_at IS NULL`).

**Pre-fix behavior** (current code, line 50): `build_watchlist` queries `MAX(run_ts) FROM evaluation_runs` → gets `E2` → `candidates_by_ticker[TICKER_X]` is missing OR has E2's criteria → `flag_tags[TICKER_X]` is empty OR `("VCP✓",)`.

**Post-fix behavior**: `build_watchlist` reads `pipeline_runs.evaluation_run_id` → gets `E1` → `candidates_by_ticker[TICKER_X]` has E1's criteria → `flag_tags[TICKER_X]` is `("TT✓", "VCP✓")`.

Assertion: `vm.flag_tags[TICKER_X] == ("TT✓", "VCP✓")` (or whichever non-empty tuple E1's criteria produce). This assertion fails under pre-fix code and passes under post-fix code. **Verify the arithmetic by running the test against the unmodified watchlist.py first** — you should see the failure mode explicitly, not just "test fails." The assertion's distinguishing power is the entire point per `feedback_regression_test_arithmetic.md`.

Add a second test for the fallback path: no `pipeline_runs` row exists (or only legacy NULL-FK rows exist) → `build_watchlist` falls back to `MAX(run_ts) FROM evaluation_runs`. This mirrors `test_dashboard_t4_candidates_eval_scoping.py`'s legacy-fallback test.

### 4.2 Minimal implementation

Edit `swing/web/view_models/watchlist.py`. Replace lines 50–53 with the equivalent of dashboard.py's lines 107–114 + 173–181 pattern:

```python
pipeline_eval_row = conn.execute(
    """SELECT evaluation_run_id FROM pipeline_runs
       WHERE state = 'complete'
       ORDER BY finished_ts DESC LIMIT 1"""
).fetchone()
pipeline_eval_id = pipeline_eval_row[0] if pipeline_eval_row else None
candidates: list[Candidate] = []
if pipeline_eval_id is not None:
    candidates = fetch_candidates_for_run(conn, pipeline_eval_id)
else:
    row = conn.execute(
        "SELECT id FROM evaluation_runs ORDER BY run_ts DESC LIMIT 1"
    ).fetchone()
    if row is not None:
        candidates = fetch_candidates_for_run(conn, row[0])
```

Add a one-sentence comment above the block explaining the binding (mirror dashboard.py:166–172's comment style): the watchlist VM's `candidates_by_ticker` (and `flag_tags` it feeds) binds to the pipeline's own eval to keep cross-surface anchor consistency with today_decisions / chart-scope.

Run `python -m pytest tests/web/test_view_models/test_watchlist_eval_scoping.py -q` → both tests pass.

Run the full fast suite: `python -m pytest -m "not slow" -q` → 723 passing (721 baseline + 2 new tests). If anything else breaks, investigate before commit; do NOT commit a regression.

### 4.3 Commit

```
fix(web): build_watchlist binds via evaluation_run_id

Closes the last mixed-anchor surface from the Bug 7 family. The
standalone /watchlist page's candidates_by_ticker (and the flag_tags
it feeds) now reads from pipeline_runs.evaluation_run_id when populated,
falling back to latest-eval only for legacy NULL-FK rows or fresh
installs. Brings build_watchlist into line with build_dashboard
(commit 1cfc117 Major 2) and build_watchlist_expanded (commit 4678398).

Cross-surface anchor invariant: every read-only UI surface that joins
candidates by ticker now binds to the pipeline's OWN eval, not to the
most-recently-started eval that may belong to a post-pipeline standalone
`swing eval` invocation.

Phase 3 web layer; no Phase 2 carve-out required.
```

(Adjust commit body wording if you find better phrasing; keep the structural points.)

---

## 5. Adversarial review

After the commit lands, invoke `copowers:adversarial-critic` on the diff (single commit, small surface). Iterate to `NO_NEW_CRITICAL_MAJOR`. Specific watch items:

- Has any other surface in `swing/web/view_models/` retained the legacy `MAX(run_ts) FROM evaluation_runs` pattern? Run `grep -rn "ORDER BY run_ts DESC LIMIT 1" swing/web/` to enumerate; flag any survivors in the return report (do NOT fix in this commit — out of scope per §2; capture for a follow-up).
- Does the new test correctly assert the distinguishing condition? Verify by running it against pre-fix code (revert the implementation file, leave the test file in place) and confirming the test FAILS. Then restore the fix.
- Does the test fixture correctly reflect production data shapes? `evaluation_runs` requires real columns (`data_asof_date`, `run_ts`, etc.); `pipeline_runs` requires the `evaluation_run_id` FK column added in migration 0006. Use `swing.data.db.connect` to get a properly-migrated connection; do not assume fresh schema.
- Is there any hidden case where `pipeline_runs.evaluation_run_id` could be populated but the referenced eval has been deleted? (Schema has FK ON DELETE behavior — verify what migration 0006 specifies; if it's CASCADE we're fine; if it's SET NULL we're fine; if it's RESTRICT then deletion is blocked structurally.) Document the resolved understanding in the adversarial review reply.

If adversarial review finds any major-severity issues, fix in a NEW commit (no amend). If adversarial review finds minor issues only, address in the same follow-up commit OR ACCEPT-with-rationale per discipline.

---

## 6. Done criteria

- New file `tests/web/test_view_models/test_watchlist_eval_scoping.py` exists and passes.
- `swing/web/view_models/watchlist.py:50` no longer contains the legacy `MAX(run_ts)` query.
- Both happy-path and fallback-path test cases pass.
- Fast suite: 723 passing (721 baseline + 2 new). No new failures.
- Ruff: no new violations on the touched file.
- Conventional commit on `main` (no amend, no co-author).
- Adversarial review pass landed (separate commit if any fixes); verdict `NO_NEW_CRITICAL_MAJOR`.
- Return report produced per §7.

---

## 7. Return report format

```
## build_watchlist mixed-anchor fix — return report

### Commits landed
- <SHA1> fix(web): build_watchlist binds via evaluation_run_id
- <SHA2> (if any) fix(web): address adversarial review finding for build_watchlist fix

### Tests
- Before: 721 passing (baseline from 25a796e)
- After: <N> passing, 0 failing (fast suite). New tests: 2.

### Adversarial review verdict
- <NO_NEW_CRITICAL_MAJOR | findings summary if any>

### Other read-paths surveyed
- `grep -rn "ORDER BY run_ts DESC LIMIT 1" swing/web/` results: <list any survivors>
- Were any additional mixed-anchor surfaces discovered? <yes/no; if yes, list>

### Deviations from brief
- <Empty if none. List any judgment calls and their rationale.>

### Open questions for orchestrator
- <Empty if none.>
```

---

## 8. If you get stuck

- If the test fixture won't construct cleanly (e.g., `pipeline_runs` insert fails on a missing column), check that migration 0006 has been applied to your test DB — `swing.data.db.connect` runs migrations automatically; your test should use that, not raw `sqlite3.connect`.
- If pre-fix code unexpectedly produces the same flag_tags as post-fix in your test setup, the fixture isn't distinguishing the two evals strongly enough. Increase the divergence: add a criterion that DEFINITELY produces a different flag (e.g., make E1's TICKER_X bucket `aplus` and E2's TICKER_X bucket `bplus`, then assert `flag_tags` reflects the bucket). Verify by mental execution of `_flag_tags` on both branches before running.
- If you discover the fix needs to touch `swing/data/` or `swing/pipeline/`, STOP and flag in the return report. The brief scoped this as web-layer-only; if that scope is wrong, the orchestrator needs to know.
- If `copowers:adversarial-critic` raises a finding that requires expanding scope (e.g., "this same pattern exists in three other files"), fix in a follow-up commit IF the new files are also web-layer view models; otherwise flag in return report and let the orchestrator scope the next session.
