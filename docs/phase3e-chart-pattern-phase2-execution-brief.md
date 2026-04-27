# Phase 3e — Chart-Pattern Flag-V1: Phase 2 Execution Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Execute **Phase 2 ONLY** (Tasks 2.1 through 2.9) of the chart-pattern flag-v1 implementation plan via `copowers:executing-plans`. Land migrations 0009 + 0010, the `pattern_classifications` repo, the `Trade` dataclass extension, repo-layer cross-column ValueError invariants, and the threading of 4 new columns through every `trades` read path. Stop at the Phase 2 checkpoint — do NOT proceed to Phase 3 or beyond.
**Expected duration:** ~1 session (~9 tasks per writing-plans implementer's estimate).
**Output:** Phase 2 commits landed on `main`; schema_version = 10; fast suite green; new tests cover the cache-table NULL-semantics matrix + the trade-row cross-column invariants; adversarial Codex review on the combined Phase 2 diff reaches `NO_NEW_CRITICAL_MAJOR`.

---

## §0 Read first

In this order:

1. **`docs/superpowers/plans/2026-04-26-chart-pattern-flag-v1-plan.md`** — THE plan. Phase 2 is at lines 953-1900 (Tasks 2.1 through 2.9). Read Phase 2 in full; skim Phase 1 (lines 36-952) for the algorithm context that Phase 2 persists; do NOT execute later phases.
2. **`docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`** — the source-of-truth design. Phase 2 implements spec §3.2 (persistence), particularly §3.2.1 (migration 0009 cache table + row-level CHECK), §3.2.2 (migration 0010 trade chart_pattern columns + NULL semantics matrix), §3.2.3 (repo layer + confidence persistence rule). The spec was settled across 5 adversarial Codex rounds; this plan executes it without re-design.
3. **`docs/orchestrator-context.md`** — project framing, lessons captured (especially the Phase 1 lessons added 2026-04-26: synthetic-fixture parameter-mapping, cfg-injection sensitivity tests, reference-enumeration patterns, batched-implementation TDD acceptable when documented). Phase 2's most relevant lessons: Bug-7 mixed-anchor family (`pipeline_runs.evaluation_run_id` discipline), schema-vs-repo-layer guarantees, audit-anchors-must-be-persisted.
4. **`CLAUDE.md`** at repo root — gotchas, conventions. **Phase 2 IS a Phase 2 carve-out per CLAUDE.md isolation rule.** The plan's §"Phase 2 carve-outs" table at line 4346 enumerates exactly which `swing/data/` files are touched and why; respect that boundary.
5. **`docs/phase3e-todo.md`** — particularly the "2026-04-26 chart-pattern flag-v1 Phase 1 → Phase 2 handoff items" section at the bottom for design points that emerged from Phase 1.
6. **`docs/phase3e-chart-pattern-phase1-execution-brief.md`** (briefly) — context for the Phase 1 ground state.

---

## §0 Skill posture

**INVOKE:**

- `copowers:executing-plans` — wraps `superpowers:subagent-driven-development` with adversarial Codex review on the combined Phase 2 diff after task commits land. Iterates rounds to `NO_NEW_CRITICAL_MAJOR`.

**DO NOT INVOKE:**

- `copowers:writing-plans` / `superpowers:writing-plans` — plan is settled.
- `copowers:brainstorming` / `superpowers:brainstorming` — design is settled.
- `superpowers:executing-plans` directly — use the copowers wrapper for adversarial review per project standing convention ("Adversarial review on every code-shipping session").

The execution wrapper drives task-by-task implementation per the plan's TDD discipline, then runs Codex review on the cumulative Phase 2 diff. Fix findings as new commits (no amending).

---

## §1 Scope (Phase 2 ONLY)

**EXECUTE these tasks (in order, per plan):**

- Task 2.1 — Bump `EXPECTED_SCHEMA_VERSION` constant (8 → 10)
- Task 2.2 — Migration 0009: `pipeline_pattern_classifications` table (cache table; row-level CHECK `pattern_state_consistency`)
- Task 2.3 — Migration 0010: trade chart_pattern columns + commit the migration trio (4 columns, audit anchor, FK reference)
- Task 2.4 — `PipelinePatternClassification` dataclass
- Task 2.5 — `pattern_classifications` repo + tests (`insert_classification`, `get_classification`, `list_classifications_for_run`)
- Task 2.6 — `Trade` dataclass: 4 new fields (mirrors `hypothesis_label` precedent at `models.py:69`)
- Task 2.7 — `insert_trade_with_event` writes 4 new columns + repo-layer cross-column ValueError (3 explicit invalid combinations refused)
- Task 2.8 — Thread 4 new columns through every `trades` read path + `_row_to_trade` (6 SELECT statements per the carve-out table)
- Task 2.9 — Phase 2 checkpoint (fast suite green; v10 schema; 5 carve-out files committed)

**DO NOT EXECUTE (out of scope; STOP here):**

- Phase 3 (pipeline integration: extending `_step_charts`, `render_chart` kwarg)
- Phase 4 (watchlist / dashboard read paths: VM extension, sort-neutrality regression test)
- Phase 5 (trade-entry form + CLI)
- Phase 6 (chart overlay painting)
- Phase 7 (integration tests + operator-labeled fixtures)
- ANY modification to `swing/web/`, `swing/pipeline/`, `swing/rendering/`, `swing/cli.py`
- ANY modification to `swing/trades/` other than what's in the carve-out table (the carve-out for Phase 2 covers ONLY `swing/data/`; `swing/trades/entry.py` is Phase 5 territory)

If Phase 2 reveals a problem that requires touching out-of-scope code, STOP and surface to orchestrator under "OPEN QUESTIONS" in the return report.

---

## §2 Locked constraints + Phase 1 → Phase 2 handoff items

The spec's six locked constraints (spec §1.1) and the plan's settled design decisions are binding. Phase 2 in particular must respect:

### Persistence schema (spec §3.2)

- **Migration 0009** creates `pipeline_pattern_classifications` table with row-level CHECK `pattern_state_consistency` enforcing the three-way state shape (`pattern='flag' iff confidence IS NOT NULL` AND `pattern=NULL iff classifier-error semantics`). This CHECK is FREE because it's a CREATE TABLE.
- **Migration 0010** ALTERs `trades` to add 4 columns: `chart_pattern_algo` (TEXT, CHECK IN ('none', 'flag') OR NULL), `chart_pattern_algo_confidence` (REAL, CHECK 0.0-1.0 OR NULL), `chart_pattern_operator` (TEXT, unconstrained for V1 vocabulary capture), `chart_pattern_classification_pipeline_run_id` (INTEGER REFERENCES pipeline_runs(id)).
- **Cross-column invariant** on `trades` is enforced at the **repo layer** (`insert_trade_with_event` raises `ValueError` for invalid combinations). Schema-layer hardening for `trades` is V2 (CREATE-COPY-DROP-RENAME migration). Tests must verify the repo refuses each of 3 invalid combinations INDEPENDENTLY of any schema CHECK.
- **NULL semantics** per spec §3.2.2:
  - `chart_pattern_algo='flag', confidence=0.78, pipeline_run_id=15`: cache row had `pattern='flag'`; full classification + audit anchor.
  - `chart_pattern_algo='none', confidence=NULL, pipeline_run_id=15`: cache row had `pattern='none'`; evaluated-no-detect with audit anchor.
  - `chart_pattern_algo=NULL, confidence=NULL, pipeline_run_id=NULL`: NO cache row OR cache row had `pattern=NULL` (classifier error). Trade-row collapses both cases into "not classified."
  - `chart_pattern_operator='flag'` (or any text): operator override, takes precedence in analysis.
- **Joint-NULL invariants** (spec §3.2.2):
  - `chart_pattern_algo IS NOT NULL ⟺ chart_pattern_classification_pipeline_run_id IS NOT NULL`
  - `chart_pattern_algo='flag' ⟺ chart_pattern_algo_confidence IS NOT NULL`
  - `chart_pattern_algo='none' ⟹ chart_pattern_algo_confidence IS NULL`

### Phase 1 → Phase 2 handoff items (per `docs/phase3e-todo.md`)

- **`components_json` schema design point.** Phase 1's `_evaluate_candidate` returns 11 raw measurements. Spec §3.1.1 lists additional EXAMPLE keys (4 clearances + 3 SMA-at-flag-start values) that are NOT currently populated. **Phase 2 design decision:** extend Phase 1's `_evaluate_candidate` to also populate clearances + SMAs (cheap; already computed inside helpers). **Recommendation: extend.** SMA values become unrecoverable once raw bars aren't persisted alongside, and clearances enable retroactive analysis. This requires a small modification to `swing/evaluation/patterns/flag_classifier.py` to include the additional keys in the returned `components` dict; tests in `tests/evaluation/patterns/test_flag_classifier.py` should be extended to assert their presence + correctness. **This is in-scope for Phase 2** as it's a persistence-layer prerequisite (the cache table's `components_json` column is the consumer).
- **(M=5, N=5) literal fallback in `flag_classifier.py`.** Retained but unreachable under MIN_BARS=36. Documented inline. Spec §3.1.2 step 4 cleanup landed in commit `5d7dab2` (housekeeping). Phase 2 should NOT design persistence around the (5,5) fallback case — it cannot be reached.
- **Pure-function discipline verified** — Phase 2 can safely depend on `classify_flag(bars)` not mutating `bars`.

### Repo-layer enforcement requirements (Task 2.7 + 2.8)

- `insert_trade_with_event` writes the 4 new columns AND validates the cross-column invariant via `_validate_chart_pattern_invariant` (or equivalent). Three explicit `pytest.raises(ValueError)` test cases:
  1. `algo='flag'` without `confidence` (raises).
  2. `algo='none'` with `confidence` (raises).
  3. `algo` set without `pipeline_run_id` audit anchor (raises).
- Six SELECT statements in `swing/data/repos/trades.py` (per the plan's enumeration in §"Phase 2 carve-outs") thread the 4 new columns; `_row_to_trade` consumes them.

### Bug-7-family anchor discipline

- The cache table is read by future Phase 4 code via `pipeline_runs.evaluation_run_id → pipeline_run_id`. Phase 2 itself does NOT do these reads (no consumer yet), but the schema MUST support them. Verify the foreign key column placement and the row-level CHECK enable the Phase 4 read pattern without modification.

If anything in Phase 2 conflicts with the spec or the locked constraints, STOP and surface to orchestrator. Do NOT redesign.

---

## §3 Conventions

- **Branch:** `main`. No feature branches.
- **TDD discipline (rigid):** failing test → run to see RED → minimal implementation → run to see GREEN → commit. One red-green cycle per logical change. Per-task commit boundaries per the plan. **Phase 2's tasks are mostly schema and repo work — strict TDD applies cleanly here (unlike Phase 1's batched gate implementation).** No batched-implementation pattern needed.
- **Commits:** Conventional Commits (`feat(data):`, `feat(repos):`, `test(data):`, etc.). **No Claude co-author footer. No `--no-verify`. No amending — every fix is a NEW commit.**
- **Discriminating-test discipline:** every test must produce a different outcome under post-fix code than under pre-fix code (per `feedback_regression_test_arithmetic` memory). For migration tests: assert specific schema state (column presence, CHECK constraint enforcement); for repo tests: assert specific behavior (which columns are written, which invariants raise).
- **Compounding-confound discipline (per 2026-04-26 lesson):** for any test asserting on a primary key behavior, also include a "delete the keyed-on element and confirm the test now fails differently" check.
- **Tests:** `python -m pytest -m "not slow" -q` MUST be green at the Phase 2 checkpoint. Plan does NOT require it green between every task, but Task 2.9 checkpoint is mandatory. Baseline at start of Phase 2: 1029 fast tests.
- **Ruff:** baseline 81 errors per CLAUDE.md. Phase 2 must NOT introduce new violations. Run `ruff check swing/data/` and `ruff check swing/evaluation/patterns/` after Task 2.8 and before Task 2.9 commit.
- **Migration tests:** verify migrations apply cleanly on a baseline DB (forward) AND that re-application is idempotent (no errors on second apply). Schema_version updated to 10 by 0010.
- **Phase 2 carve-out justification:** every modified or new file in `swing/data/` MUST appear in the plan's §"Phase 2 carve-outs" table. If you find yourself touching a file not in that table, STOP — it's out of scope.

---

## §4 Adversarial review (handled by copowers wrapper)

The `copowers:executing-plans` wrapper invokes Codex MCP review on the combined Phase 2 diff after Task 2.9 lands. Pass these specific watch items:

- **Spec fidelity.** Migrations match spec §3.2.1 + §3.2.2 column types, CHECK constraints, FK reference (per spec §3.2.2's nuance about FK enforcement depending on PRAGMA foreign_keys = ON). Repo layer matches spec §3.2.3.
- **Plan fidelity.** Tasks executed in plan order; no skipped tasks; no tasks added beyond the plan.
- **TDD integrity.** Each implementation commit has a preceding failing-test commit. No "implement first, test after."
- **Cross-column invariant enforcement.** Three explicit `pytest.raises(ValueError)` test cases for the trade-row cross-column invariant. **Each test must verify the repo refuses the invariant violation INDEPENDENTLY of any schema CHECK** (since the schema doesn't enforce the cross-column rule). Use direct sqlite3 INSERT in test setup to construct an invariant-violating row and assert the repo's read path doesn't choke (or assert `insert_trade_with_event` refuses at write time per the spec).
- **NULL semantics matrix coverage.** Tests cover all 5 trade-row NULL combinations from spec §3.2.2 + the 3 cache-table NULL combinations. Each test discriminating: pre-fix (no new columns) vs post-fix (4 new columns) flips the test outcome.
- **Discriminating tests (per `feedback_regression_test_arithmetic`).** For migration idempotency: post-fix re-application must be a no-op (assert specific behavior); pre-fix re-application would error (assert specific error). For schema_version bump: post-fix Task 2.1 migration brings DB from version 8 to version 10; pre-fix would fail.
- **Compounding-confound on cross-column invariant** (per 2026-04-26 lesson): if you delete the `_validate_chart_pattern_invariant` call from `insert_trade_with_event`, the test should now FAIL — not pass for a different reason (e.g., schema CHECK happening to refuse). If schema CHECK happens to catch one of the three invalid combinations and the repo-layer test passes regardless of the validate call, the test is vacuous.
- **`_row_to_trade` threading correctness.** All 6 SELECT statements include the 4 new columns in their column lists; `_row_to_trade` consumes them in the same order. A schema migration adding columns at the end of `trades` shifts column indexes — verify Position-Sensitive consumers (sqlite3 row indexing) don't break.
- **Schema migration test pattern.** Migration tests apply both forward (on baseline) AND verify no-op on second apply. Don't skip the second-apply test.
- **`components_json` extension (Phase 1 → Phase 2 handoff).** If Phase 2 extends `_evaluate_candidate` to populate clearances + SMAs (recommended per §2 above), tests in `tests/evaluation/patterns/test_flag_classifier.py` extend to assert their presence + correctness. The `components_json` column in `pipeline_pattern_classifications` should be tested with a representative row that includes all 4 clearances + 3 SMAs + 11 raw measurements (~18 keys total).
- **Out-of-scope creep.** No modification to `swing/trades/`, `swing/web/`, `swing/pipeline/`, `swing/rendering/`, `swing/cli.py`. Plan's §"Phase 2 carve-outs" table at line 4346 is the binding boundary.

---

## §5 Done criteria

Phase 2 execution is done when ALL of the following hold:

- [ ] All 9 tasks (2.1 through 2.9) have landed commits on `main`.
- [ ] `python -m pytest -m "not slow" -q` green (full fast suite); baseline + new tests on cache repo + migrations + cross-column invariants.
- [ ] Migrations 0009 and 0010 apply cleanly on a baseline DB; re-application is idempotent.
- [ ] `schema_version = 10` after migrations apply.
- [ ] `ruff check swing/data/ swing/evaluation/patterns/` clean (no new violations).
- [ ] Cross-column invariants enforced at repo layer with 3 explicit `pytest.raises(ValueError)` tests.
- [ ] All 6 trade-table SELECT statements thread the 4 new columns; `_row_to_trade` consumes them.
- [ ] `pipeline_pattern_classifications` cache table exists with row-level CHECK `pattern_state_consistency` enforced; tests verify the CHECK refuses invalid combinations.
- [ ] If `_evaluate_candidate` was extended to populate clearances + SMAs (recommended): tests assert presence + correctness; `components_json` schema test uses a representative ~18-key row.
- [ ] Adversarial Codex review on combined Phase 2 diff reaches `NO_NEW_CRITICAL_MAJOR`.
- [ ] Phase 2 implementation does NOT touch `swing/web/`, `swing/pipeline/`, `swing/rendering/`, `swing/cli.py`, OR `swing/trades/` (the latter is Phase 5 territory).

---

## §6 Return report format

Final message to orchestrator (via operator) MUST include:

```
PHASE: 2 (Persistence layer) of chart-pattern flag-v1 plan
COMMIT CHAIN: <first SHA>..<last SHA> (N commits)
FAST SUITE: 1029 → <new count> tests (Δ +<count>)
SCHEMA: 8 → 10 (migrations 0009 + 0010 applied)
ADVERSARIAL ROUNDS: <N>; FINAL VERDICT: NO_NEW_CRITICAL_MAJOR

TASKS COMPLETED:
- Task 2.1 — <one-line summary, commit SHA>
- Task 2.2 — <one-line summary, commit SHA>
- ... (all 9 tasks)

PERSISTENCE SUMMARY:
- Cache table: pipeline_pattern_classifications (CHECK pattern_state_consistency enforced)
- Trade columns added: chart_pattern_algo, chart_pattern_algo_confidence, chart_pattern_operator, chart_pattern_classification_pipeline_run_id (audit anchor)
- Cross-column invariants enforced at repo layer: <3 cases>
- components_json schema: <11-key minimum / extended with clearances + SMAs / other>
- All 6 trade SELECT paths threaded: <list affected functions>

ADVERSARIAL FINDINGS (each with disposition):
- <finding>: FIXED in commit <SHA> / ACCEPTED with rationale: <text>

OPEN QUESTIONS FOR ORCHESTRATOR:
- <any plan/spec contradiction surfaced; otherwise "None">

LESSONS WORTH CAPTURING (process insights from execution):
- <bullet list, if any>

PHASE 2 → PHASE 3 HANDOFF NOTES:
- <anything Phase 3 implementer needs to know that isn't in the plan>
```

---

## §7 If you get stuck

- **Plan/spec contradictions.** Surface in return report under "OPEN QUESTIONS." Do NOT amend the plan or spec; do NOT re-design.
- **TDD ordering uncertainty.** Failing-test-first. Phase 2's tasks are schema + repo, so per-task TDD applies cleanly (no batched-implementation deviation needed).
- **Codex finding contradicts plan.** Apply receiving-code-review discipline. If finding correct AND plan wrong, surface to orchestrator. If finding wrong, document why with rationale.
- **Out-of-scope pull.** If a Phase 2 task seems to require touching out-of-scope code (Phase 3-7 territory), STOP. Surface as "OPEN QUESTIONS." Do NOT silently expand scope.
- **Migration error during testing.** SQLite migrations are tricky. If `ALTER TABLE` fails in a way the spec doesn't anticipate, document the exact error + the SQLite version + the failing statement; surface to orchestrator.
- **Cross-column invariant test passes for wrong reason.** Per the compounding-confound check (R1 lesson 2): delete `_validate_chart_pattern_invariant` from `insert_trade_with_event` and re-run; if the test still passes, it's vacuous.

---

## §8 Anti-patterns specific to this execution

- **Scope creep into Phase 3 / Phase 4 / Phase 5.** The cache table has no consumer yet at end of Phase 2; the trade columns have no UI surface yet. That is correct. Adding even small "while I'm here" consumer wiring is out of scope.
- **Schema-layer enforcement on trades cross-column invariant.** Spec explicitly defers this to V2 (CREATE-COPY-DROP-RENAME migration is heavyweight). Phase 2 enforces ONLY at repo layer with explicit residual-risk acknowledgment. Do NOT silently promote to schema layer.
- **Skipping migration idempotency test.** Both 0009 and 0010 must have second-apply tests asserting no-op behavior. Migration drift is silent in production until it bites; idempotency tests catch it.
- **Cache-table key schema deviation.** Spec §3.2.1 keys on `(pipeline_run_id, ticker)`. The plan's Phase 4 read pattern depends on this key. Do NOT change to a synthetic primary key + UNIQUE constraint without operator approval — even if it's semantically equivalent.
- **`chart_pattern_operator` CHECK constraint.** Spec §3.2.2 leaves it unconstrained TEXT (R1 M5 ACCEPTED rationale: V1 vocabulary capture). Do NOT add a CHECK constraint here. V2 may formalize.
- **Batched-implementation TDD (the Phase 1 deviation).** Phase 2's tasks are schema + repo + dataclass + threading — not tightly coupled like Phase 1's algorithm. Strict per-task TDD applies cleanly here. Do NOT use Phase 1's batched-implementation pattern for Phase 2.
- **Vacuous regression tests.** Per the 2026-04-26 lessons: every test must produce different outcomes pre-fix vs post-fix; for compounding-confound, deleting the keyed-on element must change test behavior.
- **Skipping the components_json extension recommendation.** If Phase 2 declines the components_json extension (i.e., keeps the 11-key minimum), document the rationale explicitly in the return report. SMA values become unrecoverable; defer-rationale must explain the tradeoff.
