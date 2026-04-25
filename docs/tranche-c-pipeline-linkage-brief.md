# Tranche C — Pipeline-Linkage Bundle Implementer Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Add structural foreign-key linkage between `pipeline_runs` and `evaluation_runs` plus a persisted per-run chart-target table. Eliminates two chart-scope drift modes documented in the Session 2 design spec §4, fixes Bug 7 (today_decisions vs chart-scope mixed-anchors), and enables the `insufficient-data` chart-reason split (Session 2 spec §8 deferred item).
**Expected duration:** 6–10 hours. Split contingency pre-authorized on T5.
**Prepared:** 2026-04-24 by orchestrator instance.

---

## 0. Read first

1. `CLAUDE.md` — project conventions, Phase isolation rule (this session needs explicit carve-out for `swing/data/`, `swing/pipeline/`, `swing/web/`), TDD discipline, conventional-commits + no-amend + no-Claude-co-author rules. Note especially the gotchas around HTMX OOB-swap partial drift, base-layout VM coverage, and the `os.replace` cross-device failure (relevant if any output goes to a non-DB location).
2. `docs/superpowers/specs/2026-04-23-tranche-b-ops-session-1-design.md` §4 — chart-unavailable resolver design, particularly the "Linking eval_run_id to the pipeline run — best-effort heuristic" subsection (the heuristic this session replaces with structural linkage) and §8 "Pipeline-linkage bundle" deferred item.
3. `docs/Bugs.txt` Bug 7 — today_decisions shows tickers not in chart-scope's A+ set; preliminary diagnosis: mixed as-of anchors. This session fixes it structurally.
4. `swing/data/migrations/` — existing migration files. Most recent is `0005`. New migration `0006` lands in this session.
5. `swing/pipeline/runner.py` — the pipeline orchestrator. `_step_evaluate` and `_step_charts` are the load-bearing methods.
6. `swing/data/repos/pipeline.py` — pipeline-runs repo functions.
7. `swing/data/repos/recommendations.py` — `list_for_session` is what the dashboard's today_decisions reads.
8. `swing/web/chart_scope.py` — the resolver this session restructures (current heuristic-based linkage gets replaced with FK lookup + heuristic fallback for legacy rows).
9. `swing/web/view_models/dashboard.py` — `build_dashboard` calls `list_for_session` and the chart-scope resolver. Today_decisions construction (~line 259-263) and chart-scope resolver wiring both touched.
10. `docs/phase3e-todo.md` — current operational backlog. The "Tranche B-ops deferred items" section's "Pipeline-linkage bundle" entry is what this session implements.

**Skill posture.**
- Do NOT invoke `copowers:brainstorming` or `copowers:writing-plans`. The design is well-specified across the spec §4 + §8 + this brief.
- Invoke `superpowers:test-driven-development` for every code commit. Schema changes get migration tests; pipeline changes get pipeline-runner tests; web changes get VM + template tests.
- Invoke `superpowers:verification-before-completion` before declaring done.
- After all code commits land, invoke `copowers:adversarial-critic` per §7. **Adversarial review is standing convention for code-shipping sessions.**

---

## 1. Strategic context (compressed)

The Session 2 design spec (commits `971ad36..HEAD` from B-ops session 1) introduced a chart-scope resolver that linked the pipeline's chart targets to the evaluation run via a best-effort heuristic SQL query (`SELECT id FROM evaluation_runs WHERE data_asof_date = :pipeline.data_asof_date AND run_ts <= :pipeline.finished_ts ORDER BY run_ts DESC LIMIT 1`). The heuristic was correct for normal operation but could pick the wrong eval row in a documented race case (operator runs `swing eval` standalone mid-pipeline). Spec §4 documented this as accepted-with-rationale, with the structural fix flagged for a future "pipeline-linkage bundle" session in §8. **This is that session.**

Bug 7 (added 2026-04-24) is the operator-observed manifestation of the same mixed-anchor problem in a different surface: today_decisions on the dashboard reads from `daily_recommendations` via `list_for_session`, which uses its own session-date filter rather than binding to the current pipeline's eval. Same disease, different surface.

The structural fix is to add `evaluation_run_id` as a foreign key column on `pipeline_runs` and persist the pipeline's chart-target ticker set as a new table `pipeline_chart_targets`. Both today_decisions and the chart-scope resolver then bind via these structural references, eliminating both drift modes at their source.

The session also implements the `insufficient-data` chart-reason split (spec §8 deferred item) by persisting per-ticker `chart_status` on the new chart-targets table, distinguishing "fetcher_failed" from "too_few_bars" for any ticker whose chart was attempted but didn't produce a PNG.

---

## 2. Scope — 5 tasks (+ T5 early-return valve)

| # | Task | Closes |
|---|------|--------|
| T1 | Migration `0006`: `pipeline_runs.evaluation_run_id` FK + `pipeline_chart_targets` table with per-ticker `chart_status` | Schema |
| T2 | Pipeline runner writes `evaluation_run_id` and `pipeline_chart_targets` rows during `_step_evaluate` and `_step_charts` | Pipeline |
| T3 | Web chart-scope resolver uses `pipeline_chart_targets` (heuristic fallback retained for legacy rows pre-migration) | Web — eliminates chart-scope drift mode A (eval-linkage race) |
| T4 | Today_decisions binds via `evaluation_run_id` from current pipeline run | Web — fixes Bug 7 |
| T5 | Chart-reason split: distinguish `fetcher_failed` vs `too_few_bars` using new `chart_status` field | Web — closes spec §8 chart-reason split deferred item |

### Pre-authorized early-return valve on T5

T5 is structurally adjacent (uses the same `pipeline_chart_targets.chart_status` column added in T1) but functionally independent of T2-T4. **If after completing T1-T4 the session has gone long enough (>8 hours wall-clock), ship T1-T4 plus adversarial review on those four, and leave T5 for a thin follow-up session.** This is explicitly authorized.

Signal that the valve should be used: T1-T4 adversarial review surfaces substantive findings absorbing >45 min of fix time; OR data-migration backfill testing reveals edge cases that consume implementer attention.

### Explicitly out of scope

- Any modification to the existing chart-scope resolver heuristic for legacy (pre-migration) `pipeline_runs` rows — keep heuristic as fallback, do NOT delete it. Old runs without the new FK still need to render correctly.
- Any change to historical `pipeline_runs` data backfill beyond setting `evaluation_run_id = NULL` (the FK column accepts NULL for legacy rows; the resolver uses heuristic fallback when NULL).
- Any change to `swing/recommendations/build.py` (recommendations layer) or `swing/evaluation/` (evaluation layer). Pipeline writes the FK; recommendations + eval don't change.
- Any change to the existing chart-scope resolver's six rendered-message states. The resolver's INPUT mechanism changes (FK lookup vs heuristic); the OUTPUT message strings stay verbatim.
- Any new ranking logic, advisory rules, or pipeline step changes beyond the FK + chart-target writes.
- Candidate-sparsity diagnostic work (separate parallel session).

If you find yourself wanting to refactor the resolver's message strings, the pipeline orchestrator's overall structure, or the chart-step's fetch logic, **stop and flag in the return report**. Tranche C bundle is structural-fix scope only.

### Phase 2 carve-out

This session crosses the CLAUDE.md Phase isolation rule for `swing/trades/` and `swing/data/` consumed-read-only-during-Phase-3. **Carve-out is hereby pre-authorized for:**

- `swing/data/migrations/0006_*.sql` (T1)
- `swing/data/repos/pipeline.py` (T2 — write FK + chart_targets)
- `swing/data/repos/recommendations.py` (T4 — `list_for_session` may need to accept `evaluation_run_id` filter parameter)
- `swing/data/models.py` (T1 — new dataclass for `PipelineChartTarget` if introduced)

`swing/trades/` is NOT touched in this session. If the implementer finds it would help to touch trades/, that's a scope-creep flag — surface in return report rather than expanding.

---

## 3. Binding conventions

- **Branch:** `main`.
- **Commits:** conventional-commits. No Claude co-author footer. No `--no-verify`. No amending.
- **TDD:** failing test first, minimal impl, pass, commit. One cycle per logical change.
- **Tests:** fast suite green after every commit. Baseline going in: 634 passing.
- **Ruff:** no new violations beyond baseline 81.
- **Migration discipline:** new migrations are append-only and never alter existing migrations. Migration `0006` adds new columns and tables; does not modify migration `0005` or earlier. Backfill of existing `pipeline_runs` rows sets `evaluation_run_id = NULL` (legacy rows; resolver uses heuristic fallback for these).
- **DB location:** `%USERPROFILE%/swing-data/swing.db` per CLAUDE.md invariant. Migration runs against this; ensure the migration mechanism handles this path.

---

## 4. Task specifications

### T1 — Migration `0006`: schema additions

**File:** `swing/data/migrations/0006_pipeline_chart_linkage.sql` (or matching naming convention from `0005`)

**Schema changes:**

```sql
-- Add evaluation_run_id FK to pipeline_runs
ALTER TABLE pipeline_runs ADD COLUMN evaluation_run_id INTEGER REFERENCES evaluation_runs(id);

-- New table: per-pipeline-run chart-target tickers + status
CREATE TABLE pipeline_chart_targets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pipeline_run_id INTEGER NOT NULL REFERENCES pipeline_runs(id),
    ticker TEXT NOT NULL,
    source TEXT NOT NULL CHECK (source IN ('aplus', 'near_proximity')),
    chart_status TEXT NOT NULL CHECK (chart_status IN ('ok', 'fetcher_failed', 'too_few_bars', 'pending')),
    UNIQUE (pipeline_run_id, ticker)
);

CREATE INDEX idx_pipeline_chart_targets_run ON pipeline_chart_targets(pipeline_run_id);
```

**Notes:**
- `evaluation_run_id` is nullable. Legacy `pipeline_runs` rows from before this migration have NULL; chart-scope resolver uses heuristic fallback for those.
- `pipeline_chart_targets.source` distinguishes A+ tickers from near-proximity tickers (matches the spec §4 "Scope resolver — approximate match to `_step_charts`" subdivision).
- `chart_status` allows the resolver to distinguish `fetcher_failed` from `too_few_bars` for T5. `'pending'` is the initial value when a ticker is identified as a chart target but the chart step hasn't yet attempted it; `'ok'` means PNG written successfully.
- Unique constraint on `(pipeline_run_id, ticker)` prevents duplicate target rows for the same ticker in one run.

**Tests:** `tests/data/test_migrations_0006.py` (or whatever the existing migration-test naming pattern is — check existing tests for `0005` and match):
- Migration applies cleanly against a fresh DB.
- Migration applies cleanly on top of `0005` against a populated DB (with existing pipeline_runs rows getting NULL evaluation_run_id).
- Legacy pipeline_runs row insert still works (no NOT NULL constraint on evaluation_run_id).
- New pipeline_runs row insert with evaluation_run_id works.
- pipeline_chart_targets insert works with valid source + status; rejects invalid values per CHECK constraints.
- Unique constraint enforced on (pipeline_run_id, ticker).

**Commit message:**

```
feat(data): migration 0006 — pipeline_runs.evaluation_run_id FK + pipeline_chart_targets table

Adds structural linkage between pipeline_runs and evaluation_runs (replacing
the heuristic eval-linkage query in chart_scope resolver) and persisted
per-run chart-target tickers with status, enabling chart-reason split
(fetcher_failed vs too_few_bars).

Legacy pipeline_runs rows get evaluation_run_id = NULL; chart_scope
resolver retains heuristic fallback for these. New code paths require
the FK to be populated.
```

### T2 — Pipeline runner writes FK + chart_targets

**Files:**
- `swing/pipeline/runner.py` — `_step_evaluate` writes `evaluation_run_id` to the current `pipeline_runs` row immediately after the eval row is created. `_step_charts` writes `pipeline_chart_targets` rows for each ticker in scope (A+ + near-proximity) and updates `chart_status` per ticker as the chart step processes.
- `swing/data/repos/pipeline.py` — new helper functions: `set_evaluation_run_id(conn, pipeline_run_id, evaluation_run_id)` and `insert_chart_target(conn, ...)` and `update_chart_target_status(conn, ...)`.
- `swing/data/models.py` — new dataclass `PipelineChartTarget` if needed (may not be necessary if the repo functions take primitive args).

**Behavioral details:**
- `_step_evaluate` should set `evaluation_run_id` on the pipeline_runs row in the SAME transaction as the eval-row insert if possible. If the lease-fencing pattern doesn't allow that, do it immediately after with a small follow-up update — there's no race because the lease guarantees only one runner is active.
- `_step_charts` builds the same A+ + near-proximity set the existing logic computes (per spec §4 "Scope resolver" subdivision). For each ticker, insert a `pipeline_chart_targets` row with `chart_status='pending'` BEFORE the chart attempt. After the attempt (success, fetcher error, or too-few-bars skip), update to `'ok' | 'fetcher_failed' | 'too_few_bars'` accordingly.
- Failure modes in `_step_charts` (fetcher exception, MIN_BARS check) currently `continue` silently per spec §4 "Deferred resolution — §8". With the new persistence, they get categorized as `'fetcher_failed'` or `'too_few_bars'` respectively. **Behavioral change:** these used to be silent; now they're recorded. Operator-visible only via T5's chart-reason split, but the data is persisted regardless of T5 shipping.

**Tests:** `tests/pipeline/test_runner.py` (or extend existing test file for `_step_evaluate` / `_step_charts`):
- After `_step_evaluate` runs, the pipeline_runs row has `evaluation_run_id` populated.
- After `_step_charts` runs, pipeline_chart_targets has one row per ticker in scope (A+ + near-proximity), with status reflecting actual chart-step outcome.
- Fetcher exception → `chart_status='fetcher_failed'` for that ticker.
- Insufficient bars → `chart_status='too_few_bars'`.
- Successful PNG write → `chart_status='ok'`.
- Lease/transaction interaction tested: if the lease is revoked mid-step, partial chart_targets writes don't corrupt state.

**Commit message:**

```
feat(pipeline): persist evaluation_run_id and chart_targets during pipeline run

_step_evaluate now writes evaluation_run_id to the current pipeline_runs row
immediately after creating the eval row. _step_charts now writes
pipeline_chart_targets rows for each ticker in scope (A+ + near-proximity)
with chart_status updated as the chart step processes (pending → ok |
fetcher_failed | too_few_bars).

Fetcher errors and insufficient-bars skips are now recorded structurally
rather than silently continuing. Operator-visible chart-reason refinement
ships in T5.
```

### T3 — Web chart-scope resolver uses pipeline_chart_targets

**Files:**
- `swing/web/chart_scope.py` — `resolve_chart_scope()` (or whatever the helper name is) replaces the heuristic eval-linkage query with a direct lookup against `pipeline_chart_targets`. Heuristic fallback retained for cases where the latest pipeline_run has `evaluation_run_id IS NULL` (legacy row).
- `tests/web/test_chart_scope.py` — extend to cover the new direct-lookup path; preserve existing heuristic-path tests as fallback-coverage.

**Behavioral details:**
- New lookup path: when latest completed `pipeline_runs` row has non-NULL `evaluation_run_id`, query `pipeline_chart_targets WHERE pipeline_run_id = :id AND ticker = :ticker` to determine scope. If a row exists → ticker is in scope (chart_status determines the rendered message). If no row → ticker is out of scope (`out-of-scope` reason).
- Fallback path: when latest completed `pipeline_runs` row has NULL `evaluation_run_id` (legacy), use the existing heuristic exactly as before. No code deletion, just an `if pipeline_run.evaluation_run_id is not None: <new path> else: <existing heuristic>` branch.
- The six rendered-message states (None / no-run / engine-missing / pipeline-failed / out-of-scope / insufficient-data) stay verbatim. T3 changes the INPUT (how scope is determined) not the OUTPUT (message strings).
- Drift mode A (eval-linkage race) is structurally eliminated for new pipeline runs. Drift mode B (top-N watchlist proximity recomputed at render time) is also structurally eliminated because the resolver no longer recomputes proximity — it reads what was actually persisted.

**Tests:** for both pre-migration (heuristic) and post-migration (FK-backed) paths:
- Each of the six chart-reason states fires correctly.
- Standalone-eval race case (the historical drift mode): with FK populated, resolver picks the pipeline's eval, not a later standalone eval. Regression test for the drift mode A.
- Watchlist-proximity drift case: resolver returns the persisted target set, not a recomputed live one. Regression test for the drift mode B.
- Legacy row (evaluation_run_id IS NULL) still resolves via heuristic.

**Commit message:**

```
fix(web): chart-scope resolver uses pipeline_chart_targets when available

Replaces the heuristic eval-linkage query with direct lookup against the
new pipeline_chart_targets table when the latest pipeline_run has
evaluation_run_id populated. Heuristic fallback retained for legacy rows
without the FK.

Eliminates both chart-scope drift modes documented in spec §4:
- A. Eval-linkage race (standalone swing eval mid-pipeline)
- B. Watchlist-proximity recomputation drift

Six rendered-message states unchanged; the resolver's INPUT changes,
not its OUTPUT.
```

### T4 — Today_decisions binds via evaluation_run_id (Bug 7 fix)

**Files:**
- `swing/data/repos/recommendations.py` — `list_for_session` (or equivalent) gets an optional `evaluation_run_id` parameter. When provided, filter recommendations to only those from that eval. When not provided, retain existing session-date behavior for backward compat.
- `swing/web/view_models/dashboard.py` — `build_dashboard` passes the current pipeline run's `evaluation_run_id` to `list_for_session` when constructing today_decisions.
- `tests/data/test_repos_recommendations.py` and `tests/web/test_view_models/test_dashboard.py` — extend.

**Behavioral details:**
- Today_decisions now reads recommendations from the SAME eval that the chart-scope resolver uses. If a ticker is in today_decisions, it's also in pipeline_chart_targets (because today_decisions only includes A+ tickers, all of which the pipeline charts). Bug 7's reported symptom (SLDB in today_decisions but reported as out-of-scope by chart-scope resolver) becomes structurally impossible.
- Legacy pipeline runs (NULL evaluation_run_id): today_decisions falls back to existing session-date filter behavior. Same pattern as T3's fallback.
- This is a behavioral change for the standalone-eval-mid-pipeline race case, similar to spec §4's drift mode A. Pre-fix: today_decisions might show recommendations from a later standalone eval. Post-fix: today_decisions shows the pipeline's eval. Document inline with a brief comment citing Bug 7.

**Tests:**
- Bug 7 regression: build a fixture pipeline run + standalone eval (later timestamp, same date) where the standalone eval differs in A+ set; assert today_decisions reflects the pipeline's eval, not the standalone.
- Cross-consistency: today_decisions tickers ⊆ pipeline_chart_targets tickers (A+ subset). Assert this invariant in a separate test.
- Legacy fallback: pipeline_runs row with NULL evaluation_run_id renders today_decisions via existing session-date filter.

**Commit message:**

```
fix(web): today_decisions binds via evaluation_run_id (Bug 7)

Today_decisions now reads recommendations from the same eval the
chart-scope resolver uses, eliminating the mixed-anchor inconsistency
where today_decisions could show a ticker that chart-scope reports as
out-of-scope (Bug 7 symptom). Structurally enforced via the new
evaluation_run_id FK on pipeline_runs.

Legacy pipeline_runs rows (NULL FK) fall back to existing session-date
filter behavior. Cross-consistency invariant added: today_decisions
tickers ⊆ pipeline_chart_targets tickers (A+ subset).
```

### T5 — Chart-reason split: fetcher_failed vs too_few_bars (early-return valve eligible)

**Files:**
- `swing/web/chart_scope.py` — extend the `insufficient-data` reason resolution to read `chart_status` from `pipeline_chart_targets` and distinguish `fetcher_failed` vs `too_few_bars`. Two new message strings.
- `swing/web/templates/partials/watchlist_expanded.html.j2` — template render handles the two new states.
- `swing/web/view_models/watchlist.py` (or wherever the chart-reason VM field lives) — add the two new state values.
- Tests: extend chart-scope and template tests to cover the two new states.

**New message strings (append to existing five-state set):**

| `chart_reason` | Rendered message |
|---|---|
| `fetcher_failed` | `Chart unavailable — yfinance fetch failed for this ticker at last pipeline run.` |
| `too_few_bars` | `Chart unavailable — insufficient historical bars for this ticker at last pipeline run.` |

The previous `insufficient-data` state collapses into one of these two for new pipeline runs. For legacy runs (NULL FK, heuristic fallback), `insufficient-data` remains as the catch-all (heuristic can't distinguish).

**Tests:**
- Each of the two new states fires with the correct message when the persisted `chart_status` matches.
- Legacy run with no `chart_status` data falls back to `insufficient-data`.

**Commit message:**

```
feat(web): chart-reason split — distinguish fetcher_failed vs too_few_bars

Closes spec §8 chart-reason split deferred item. Reads chart_status from
pipeline_chart_targets to distinguish yfinance fetch failures from
insufficient-bar-history skips. Legacy runs without chart_status data
fall back to the existing insufficient-data catch-all state.
```

---

## 5. Adversarial review (after T1-T4, optionally T5)

Run on combined diff:

```bash
git diff <C2-from-housekeeping-SHA-or-current-main>..HEAD -- swing/
```

Invoke `copowers:adversarial-critic`. Iterate to `NO_NEW_CRITICAL_MAJOR`.

**Watch items the reviewer is likely to probe:**

- **Migration backwards compatibility.** Does the migration apply cleanly on a populated DB? Does the legacy-fallback branch in the resolver actually exercise correctly (i.e., did anyone test the heuristic path post-migration)?
- **Transaction semantics.** Does `_step_evaluate` write `evaluation_run_id` atomically with the eval-row insert? If the pipeline crashes mid-step, are pipeline_chart_targets rows orphaned?
- **Lease interaction.** Does the lease-revocation pattern handle the new `pipeline_chart_targets` writes correctly? Specifically: if the lease is revoked between writes, do partial target rows get cleaned up or do they leak?
- **Cross-VM coverage.** Per CLAUDE.md gotcha, base-layout VMs (DashboardVM, PipelineVM, JournalVM, WatchlistVM, PageErrorVM) must all have any new field with safe defaults. T3-T5 may add VM fields — check all five.
- **Template-duplication gotcha.** Per CLAUDE.md gotcha, HTMX OOB-swap partials and full-page renders must use the same `{% include %}`. T5 modifies the watchlist_expanded partial; check both render paths.
- **Bug 7 regression test actually distinguishes pre-fix from post-fix behavior.** Per `memory/feedback_regression_test_arithmetic.md`, vacuous tests are real risk. The implementer should construct a fixture where pre-fix code WOULD produce wrong today_decisions and post-fix code produces correct ones.
- **Legacy row handling under T4.** Today_decisions on a legacy pipeline run (NULL FK) must not crash and must produce the same output as pre-T4 code did.

Fix findings in a new commit per the no-amend rule. ACCEPTED-with-rationale findings documented in the return report.

---

## 6. Done criteria

- T1, T2, T3, T4 shipped (T5 either shipped or early-return valve invoked + flagged).
- Fast suite green after every commit. New tests added per task. Final count: 634 + new-test-count.
- No new ruff violations.
- Migration `0006` applies cleanly on a fresh DB and on the operator's existing populated DB.
- Adversarial review verdict: `NO_NEW_CRITICAL_MAJOR`.
- Bug 7 regression test added and passing.
- Return report produced.

---

## 7. Return report format

```
## Tranche C pipeline-linkage bundle return report

### T5 early-return valve
<"Not invoked." OR "Invoked after T4. Rationale: <brief>. T5 deferred to thin follow-up.">

### Commits landed
- <SHA> feat(data): migration 0006 — pipeline_runs.evaluation_run_id FK + pipeline_chart_targets    (T1)
- <SHA> feat(pipeline): persist evaluation_run_id and chart_targets during pipeline run               (T2)
- <SHA> fix(web): chart-scope resolver uses pipeline_chart_targets when available                     (T3)
- <SHA> fix(web): today_decisions binds via evaluation_run_id (Bug 7)                                 (T4)
- <SHA> feat(web): chart-reason split — distinguish fetcher_failed vs too_few_bars                    (T5 — if shipped)
- <SHA> fix(...): address Tranche C adversarial-review findings                                       (review fixes — if needed)

### Tests
- Before: 634 passing, 0 failing.
- After: <N> passing, 0 failing. New tests: <M> across migration, pipeline, web, repo layers.
- Bug 7 regression test: name + pass status.

### Migration applied
- Fresh DB: clean apply ✓ / failure mode <X>.
- Operator's existing DB: clean apply ✓ / failure mode <X> (run against `~/swing-data/swing.db`).

### Cross-VM base-layout coverage
- Base-layout VMs touched: <list>. Each gained <field> with safe default <value>.

### Adversarial review — summary
- Rounds: <N>
- Base SHA: <pre-T1 SHA>
- Thread ID: <Codex MCP>
- Findings: <N> critical / <N> major / <N> minor
- FIXED: <short summary>
- ACCEPTED-with-rationale: <short summary>
- Verdict: NO_NEW_CRITICAL_MAJOR at Round <N>

### Behavioral changes documented
<For T4: today_decisions on standalone-eval-mid-pipeline runs now shows pipeline's eval, not standalone's. For T2: fetcher exceptions and insufficient-bar skips now persist chart_status records (previously silent continues).>

### Items flagged but not done (scope discipline)
<Any adjacent observations.>

### Open questions for orchestrator
<Empty if none.>
```

---

## 8. If you get stuck

- If a migration test reveals that the operator's existing DB has data inconsistencies that block clean apply (e.g., orphaned pipeline_runs rows), flag in return report and propose a data-cleanup migration as separate follow-up. Don't expand the migration scope mid-session.
- If `_step_evaluate` and `_step_charts` interact with the lease in ways that make atomic FK writes hard, document the constraint and use a follow-up update with a comment explaining why. Lease semantics > FK-atomicity preferences.
- If the chart-scope resolver's existing test fixtures don't easily extend to cover the new FK path, write new fixtures rather than mutating existing ones — keep the heuristic-path tests untouched as fallback coverage.
- If you discover that some other `recommendations.list_*` function has the same mixed-anchor bug as `list_for_session`, flag it but do NOT fix it in this session. Bug-7-class issues in other surfaces are follow-up work.
- If the T5 chart-reason split surfaces edge cases (e.g., a ticker has both `fetcher_failed` and `too_few_bars` events recorded across re-runs), pick the most recent and document the choice. State machine is INTENDED to update in place; the most-recent value wins.
