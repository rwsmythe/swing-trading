# Phase 3e — Chart-Pattern Flag-V1: Phase 5 Execution Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Execute **Phase 5 ONLY** (Task 5.0a Phase 2 carve-out extension + Tasks 5.1 through 5.6) of the chart-pattern flag-v1 implementation plan via `copowers:executing-plans`. Land the dataclass annotation retype (`PipelinePatternClassification.pole_start_date` etc. annotation `str | None` → `date | None`); extend `EntryRequest` with 4 chart_pattern fields + snapshot-at-entry-surface ToCToU pattern; extend `TradeEntryFormVM` with cache resolution; render the Chart Pattern section in the trade-entry form template (algo display + override dropdown); wire POST handler to read new form fields and build EntryRequest with snapshot; add CLI `--chart-pattern-operator` flag with cached-only refusal gate. Stop at the Phase 5 checkpoint — do NOT proceed to Phase 6 or beyond.
**Expected duration:** ~1-2 sessions (~7 tasks: Task 5.0a + Tasks 5.1-5.6).
**Output:** Phase 5 commits landed on `main`; fast suite green; trade-entry form (web + CLI) now displays algo classification when present and persists operator override on submit; `record_entry` persists snapshot AS-IS (no re-resolve); CLI cached-only refusal gate symmetric with form's stub gate; adversarial Codex review on the combined Phase 5 diff reaches `NO_NEW_CRITICAL_MAJOR`.

---

## §0 Read first

In this order:

1. **`docs/superpowers/plans/2026-04-26-chart-pattern-flag-v1-plan.md`** — THE plan. Phase 5 is at lines 3118-3937 (Tasks 5.1 through 5.6). Read Phase 5 in full; skim Phases 1-4 (lines 36-3117) for context; do NOT execute later phases.
2. **`docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`** — the source-of-truth design. Phase 5 implements spec §3.6 (trade-entry form + ToCToU snapshot pattern + operator override + CLI parity).
3. **`docs/orchestrator-context.md`** — project framing, recent decisions (especially the 2026-04-26 Phase 4 triage decisions: subject-only grep refinement, scope-deviation acceptance pattern, base-layout 5-VM rule scope), Binding conventions (3-tier commit-message convention), most-recent lessons captured (especially sort-coupling test vacuousness extension, single-subagent-vindication, observable-verification grep refinement, downstream-test scope-acceptance pattern, base-layout 5-VM rule scope).
4. **`CLAUDE.md`** at repo root — gotchas, conventions. **Phase 5 touches `swing/web/`** (TradeEntryFormVM extension + form template + POST handler), **`swing/trades/entry.py`** (EntryRequest extension + record_entry snapshot persistence), **`swing/cli.py`** (CLI flag + refusal gate), AND **`swing/data/models.py`** for Task 5.0a (Phase 2 carve-out extension; annotation retype only). Especially relevant gotchas: Starlette TemplateResponse signature, HTMX OOB-swap partial drift (use `{% include %}`), TestClient lifespan for `app.state.price_fetch_executor`. **Note: base-layout 5-VM rule does NOT apply** for Phase 5's new fields — they're consumer-scoped to `TradeEntryFormVM` (entry form only); `base.html.j2` doesn't reference them.
5. **`docs/phase3e-todo.md`** — particularly the "2026-04-26 chart-pattern flag-v1 Phase 4 → Phase 5 handoff items" section at the bottom for design points and Task 5.0a fix specification.
6. **`docs/phase3e-chart-pattern-phase4-execution-brief.md`** (briefly) — context for the Phase 4 dispatch discipline that Phase 5 inherits + extends.

---

## §0 Skill posture

**INVOKE:**

- `copowers:executing-plans` — wraps `superpowers:subagent-driven-development` with adversarial Codex review on the combined Phase 5 diff after task commits land. Iterates rounds to `NO_NEW_CRITICAL_MAJOR`.

**DO NOT INVOKE:**

- `copowers:writing-plans` / `superpowers:writing-plans` — plan is settled.
- `copowers:brainstorming` / `superpowers:brainstorming` — design is settled.
- `superpowers:executing-plans` directly — use the copowers wrapper for adversarial review per project standing convention.
- `superpowers:using-git-worktrees` — explicitly NOT required for Phase 5 (operator decision 2026-04-26 post-Phase-4: single-subagent + observable-verification approach was vindicated by Phase 4 ZERO-rogue outcome; continue brief discipline; worktree isolation reserved as fallback for new failure modes).

The execution wrapper drives task-by-task implementation per the plan's TDD discipline, then runs Codex review on the cumulative Phase 5 diff. Fix findings as new commits (no amending).

---

## §1 Scope (Phase 5 ONLY + Task 5.0a Phase 2 carve-out extension)

**EXECUTE these tasks (in plan order; Task 5.0a FIRST as prerequisite):**

- **Task 5.0a** — **Dataclass annotation retype** in `swing/data/models.py`. Phase 2 carve-out extension; Phase 5 prerequisite. See §2 below for the fix specification.
- **Task 5.1** — `EntryRequest` gains 4 new fields (operator + resolved-at-surface snapshot: `chart_pattern_algo`, `chart_pattern_algo_confidence`, `chart_pattern_operator`, `chart_pattern_classification_pipeline_run_id`); `record_entry` persists snapshot AS-IS (no re-resolve); canonicalizes operator label via shared helper.
- **Task 5.2** — `TradeEntryFormVM` gains 4 chart_pattern fields; `build_entry_form_vm` resolves cache row at entry-surface (the form-render boundary).
- **Task 5.3** — Trade-entry form template: "Chart pattern" section (algo display + override dropdown); reusable partial `partials/trade_entry_chart_pattern_section.html.j2`.
- **Task 5.4** — POST `/trades/entry` handler reads new form fields and builds `EntryRequest` with snapshot.
- **Task 5.5** — CLI `--chart-pattern-operator` flag + refusal gate when no cached classification.
- **Task 5.6** — Phase 5 checkpoint (validation; fast suite green; ruff clean).

**DO NOT EXECUTE (out of scope; STOP here):**

- Phase 6 (chart overlay painting: actual `fill_betweenx` / pole-flag bands / algo-pivot segment / title annotation)
- Phase 7 (integration tests + operator-labeled fixtures)
- ANY modification to `swing/data/` BEYOND Task 5.0a (the annotation retype is the only Phase 2 carve-out extension; no `swing/data/repos/`, no migrations, no other models.py changes)
- ANY modification to `swing/pipeline/`, `swing/rendering/`, `swing/evaluation/`

If Phase 5 reveals a problem that requires touching out-of-scope code, STOP and surface to orchestrator under "OPEN QUESTIONS" in the return report.

**In-scope-by-extension (per scope-deviation acceptance pattern, 2026-04-26):** Downstream tests of files modified by Task 5.0a OR by Phase 5's `swing/trades/entry.py` extension are naturally in-scope. If Task 5.0a's annotation change breaks downstream test assertions (e.g., type-check assertions on `pole_start_date`), fix them as part of Task 5.0a or the Phase 5 task that surfaced them. Brief explicitly authorizes: tests in `tests/data/`, `tests/trades/`, `tests/web/`, `tests/cli/` that consume the modified types or signatures.

---

## §2 Task 5.0a specification (Phase 2 carve-out extension)

**Context.** Phase 4 Task 4.0a fixed `_row_to_classification` to parse anchor dates as `date` objects at runtime, but the `PipelinePatternClassification` dataclass annotation in `swing/data/models.py:274` still says `str | None`. Type-vs-runtime drift. Phase 5's `build_entry_form_vm` and Phase 6's chart overlay painting both use `isinstance(cls.pole_start_date, date)` checks; the annotation should match runtime.

**Files (single Phase 2 carve-out extension):**

- Modify: `swing/data/models.py` (the `PipelinePatternClassification` dataclass — annotations only)
- Modify: any test file that asserts on the type annotation (likely none; runtime tests already pass post Task 4.0a)

**Fix specification:**

In `swing/data/models.py`, change the four anchor-date field annotations on `PipelinePatternClassification` from `str | None` to `date | None`:

```python
# Before (line 274 area):
pole_start_date: str | None
pole_end_date: str | None
flag_start_date: str | None
flag_end_date: str | None

# After:
pole_start_date: date | None
pole_end_date: date | None
flag_start_date: date | None
flag_end_date: date | None
```

Add `from datetime import date` to the imports if not already present.

**Tests:**

- TDD: failing test first asserting `cls.pole_start_date.__annotations__` (or equivalent introspection) returns `date | None`, then implement.
- Discriminating-test discipline: pre-fix returns `str | None`; post-fix returns `date | None`. The test must distinguish.
- Compounding-confound: verify the annotation actually changed by attempting to instantiate `PipelinePatternClassification(pole_start_date="2026-04-26", ...)` and asserting type-check tools (or runtime `isinstance` if the implementation chooses to enforce) flag the violation. (Note: Python's runtime doesn't enforce dataclass field annotations by default; the test may need to use `typing.get_type_hints()` or similar introspection to verify the annotation is correct.)
- Round-trip: insert a classification with `date(2026, 4, 26)`; read it back; assert `cls.pole_start_date == date(2026, 4, 26)` AND the field's annotation is `date | None`.

**Commit message:** `fix(data): Task 5.0a — retype PipelinePatternClassification anchor-date annotations to date|None (Phase 2 carve-out extension; Phase 4 handoff item)`

This is a one-task fix; Task 5.0a is committed standalone (not bundled with Task 5.1 or any later Phase 5 task) so the carve-out extension is auditable.

---

## §3 Locked constraints + Phase 1-4 handoff items

The spec's six locked constraints (spec §1.1) and the plan's settled design decisions are binding. Phase 5 in particular must respect:

### Snapshot-at-entry-surface ToCToU pattern (binding spec §3.6)

- **Cache resolution happens ONCE at entry-surface (form/CLI), not at submit.** `build_entry_form_vm` resolves the classification row when rendering the form; the resolved values flow through hidden form fields to POST handler; `EntryRequest` carries the snapshot; `record_entry` persists what's passed AS-IS.
- **NO re-resolve at submit.** `record_entry` does NOT call `get_classification(...)` again. The temporal gap between form render and submit is the ToCToU window the spec deliberately closes.
- **`pipeline_run_id` audit anchor persisted on trade row.** The 4th column added by Phase 2 migration 0010 (`chart_pattern_classification_pipeline_run_id`); Phase 5 populates it from the snapshot.
- **Hidden-field tampering accepted as residual V1 risk.** Per spec §3.6 threat model: "operator-claimed input from a hidden form field, not server-verified." Acceptable for personal-use single-operator scope. V2 hardening = re-resolve + validate.

### Operator override surface (binding spec §3.6)

- **Dropdown {Accept algo / flag / none / other(text)}.** Default = Accept algo → NULL persisted (`chart_pattern_operator IS NULL`).
- **Free-text "other" path canonicalized like `hypothesis_label`** (NFC normalization + control-byte stripping). Reuse the existing canonicalization helper from `swing/trades/entry.py` (likely `canonicalize_hypothesis_label` or similar; verify with `grep`).
- **Out-of-scope tickers: "Not classified" stub, override surface hidden in V1.** Form does NOT display the override dropdown for tickers without a cached classification row.

### CLI cached-only refusal gate (binding locked-constraint #5)

- `swing trade entry --chart-pattern-operator <value>` MUST refuse for tickers without cached classification. Symmetric with form's stub gate (per Phase 1 brainstorm Codex R1 C1 fix; documented in spec §3.6).
- Refusal returns a non-zero exit code with explicit error message: `"Cannot override chart pattern for <ticker>: no cached classification (out-of-chart-scope or pipeline-run-stale)"` or similar.
- CLI does NOT do its own cache-fetch fallback. Symmetric refusal across entry surfaces.

### Phase 5 task partitioning + sequential dependencies

Phase 5's tasks have natural dependencies:

- **Task 5.0a is independent** (Phase 2 carve-out fix; standalone first commit).
- **Task 5.1** (EntryRequest extension + record_entry snapshot persistence) is mostly independent but consumes Task 5.0a's `date | None` annotation for type-correctness of any date-typed snapshot fields.
- **Task 5.2** (TradeEntryFormVM extension + build_entry_form_vm cache resolution) depends on Task 5.0a (date-typed cache fields) and the existence of the cache table from Phase 2.
- **Task 5.3** (form template Chart Pattern section) depends on Task 5.2 (consumes the VM's new fields).
- **Task 5.4** (POST handler reads new form fields, builds EntryRequest) depends on Task 5.1 + Task 5.3.
- **Task 5.5** (CLI flag + refusal gate) depends on Task 5.1 (EntryRequest extension; CLI builds same request type).
- **Task 5.6** (checkpoint) depends on all prior.

**Recommended partitioning:** ONE subagent handles Task 5.0a → Task 5.1 → Task 5.2 → Task 5.3 → Task 5.4 → Task 5.5 → Task 5.6 sequentially. Phase 4 vindicated single-subagent dispatch; ZERO rogue duplicates produced.

### Bug-7-family anchor discipline

- `build_entry_form_vm`'s cache resolution MUST bind to `pipeline_runs.evaluation_run_id → pipeline_run_id`. Use the existing `latest_evaluation_run_id` helper (or extract one if it doesn't exist as such) — Phase 4 established the single-round-trip `SELECT id, evaluation_run_id` pattern; Phase 5 mirrors it.
- DO NOT read "latest classification by computed_at" as a fallback — that re-introduces mixed-anchor risk.

### Phase 1-4 handoff items

- **Pure-function discipline verified for Phase 1.** `classify_flag(bars)` does NOT mutate input; not directly relevant to Phase 5 but preserves design consistency.
- **Repo-layer cross-column invariant** on `trades` (4 cases enforced in Phase 2): Phase 5's `record_entry` inherits this guarantee; any invalid combination of (algo, confidence, operator, anchor) at insert raises `ValueError`. Test Task 5.1's snapshot persistence against this invariant.
- **`PipelinePatternClassification` dataclass: 18-key `components_json`** (11 raw + 4 clearances + 3 SMAs at flag_start) — Phase 5 doesn't consume `components_json` directly; it consumes top-level fields like `pattern`, `confidence`, `pivot`, anchor dates.
- **Per spec §3.3, classifier-error rows have `pattern=NULL` AND `components_json` carrying `"error"` key.** Phase 5's form display logic (and CLI refusal gate) MUST handle classifier-error rows correctly: treat them as "not classified" (no override surface; CLI refuses). Don't display "flag (NULL)" or similar artifact.
- **Shared seed helper at `tests/web/test_view_models/_pattern_classification_seed.py`** (leading-underscore opts out of pytest collection). Reuse `seed_pipeline_with_classification`, `add_active_watchlist_row`, `delete_all_classifications` for Phase 5 tests.

If anything in Phase 5 conflicts with the spec or the locked constraints, STOP and surface to orchestrator. Do NOT redesign.

---

## §4 Subagent task partitioning + observable verification (BINDING — operator decisions through 2026-04-26)

**Background.** Phase 2 surfaced subagent-driven-development self-collision; Phase 3 added disjoint-task-partitioning brief discipline; Phase 4 added observable verification (subagent must include `git log --grep` output in commit body); Phase 4 vindicated the approach (ZERO rogue duplicates). Phase 5 inherits the discipline + the 2026-04-26 grep refinement.

### Required partitioning rules

1. **Each task assigned to exactly one subagent.** Multiple tasks per subagent allowed; task sets across agents MUST be DISJOINT.
2. **Pre-task verification.** Before starting any task's implementation, the assigned subagent MUST verify the task's deliverable does NOT already exist (grep for the function/class/import; read the relevant file). Abort + report if it does.
3. **Sequential dependencies (Phase 5 specifically).** See §3 above. Recommended partitioning: ONE subagent handles all Phase 5 tasks sequentially.
4. **Commit-message conventions** (formalized 2026-04-26):
   - **Task implementation commits** MUST include task ID: `feat(area): Task X.Y — <description>`.
   - **Adversarial review-fix commits** SHOULD include round + finding ID: `fix(area): Codex R1 Major 2 — <description>`.
   - **Format-only cleanup commits** (ruff, comment, whitespace) no task ID needed.

### Observable verification (refined 2026-04-26)

5. **Subagent MUST include subject-only grep output in the commit body BEFORE each task implementation commit:**

   ```
   $ git log --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task X.Y'
   ```

   This is the **subject-only refinement** (operator decision 2026-04-26 post-Phase-4) — anchors to conventional-commit `<type>(<area>): Task X.Y` subject prefix; eliminates forward-reference false positives that surfaced in Phase 4 when commit bodies cross-referenced future task IDs in narrative prose.

   If the grep returns ANY existing commits, the subagent MUST NOT commit that task (abort and report). Codex review will check the commit body for this evidence; absence is a finding.

   Example commit body format:
   ```
   Task 5.1 — EntryRequest gains 4 new fields + record_entry snapshot persistence

   Pre-commit verification:
   $ git log --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task 5.1'
   (no output — Task 5.1 not yet implemented)

   <rest of commit message>
   ```

### Watch items for adversarial review

- **Duplicate task implementations** (two commits with overlapping task IDs OR redundant content for the same plan task).
- **Missing pre-task verification evidence in commit body** per rule 5 above. Codex will flag absent grep output.
- **Mixed-task commits.**
- **Scratch directory pollution.** Use `pytest --basetemp=<gitignored-relative-dir>`. Document any Windows-ACL-blocked dirs.
- **Sort-coupling test vacuousness** (per 2026-04-26 lesson extension). Phase 5 doesn't have sort-coupling concerns directly, but discriminating-test discipline applies broadly.

---

## §5 Conventions

- **Branch:** `main`. No feature branches.
- **TDD discipline (rigid):** failing test → run to see RED → minimal implementation → run to see GREEN → commit. One red-green cycle per logical change. Per-task commit boundaries per the plan. Phase 5's tasks are integration-style — strict per-task TDD applies cleanly.
- **Commit-message conventions** (per §4 rule 4 above).
- **Discriminating-test discipline:** every test must produce a different outcome under post-fix code than under pre-fix code (per `feedback_regression_test_arithmetic` memory and the 2026-04-26 lesson extensions). Especially relevant: **log-line and format assertions use exact-equality, NOT substring matching**; **architectural-separation tests must be invertible-setup-discriminating** (per 2026-04-26 sort-coupling extension).
- **Compounding-confound discipline:** for any test asserting on a primary key behavior, also include a "delete the keyed-on element and confirm the test now fails differently" check.
- **Tests:** `python -m pytest -m "not slow" -q` MUST be green at the Phase 5 checkpoint. Plan does NOT require it green between every task, but Task 5.6 checkpoint is mandatory. Baseline at start of Phase 5: 1102 fast tests.
- **Ruff:** baseline 81 errors per CLAUDE.md. Phase 5 must NOT introduce new violations in `swing/web/`, `swing/trades/`, `swing/cli.py`, or `swing/data/`. Run `ruff check swing/web/ swing/trades/ swing/cli.py swing/data/` after Task 5.5 and before Task 5.6 commit.
- **Phase 5 scope boundary:** every modified file MUST be in `swing/web/`, `swing/trades/entry.py` (Task 5.1), `swing/cli.py` (Task 5.5), `swing/data/models.py` (Task 5.0a only), OR `tests/web/`, `tests/trades/`, `tests/cli/`, `tests/data/`. **Downstream tests of Task 5.0a's modified file are in-scope by extension** (per scope-acceptance pattern 2026-04-26).
- **Scratch directory hygiene.** Use `pytest --basetemp=.tmp-phase5/` to direct scratch to a project-gitignored location (add `.tmp-phase5/` to `.gitignore` first; this is the brief §5 hygiene corollary). Clean up after each task's test cycle. Document any Windows-ACL-blocked dirs in return report.
- **Base-layout 5-VM rule does NOT apply.** Phase 5's new fields are on `TradeEntryFormVM` (consumer-scoped to entry form); `base.html.j2` doesn't reference them. Per 2026-04-26 lesson: don't blanket-require the 5-VM rule unless `base.html.j2` is actually being touched.

---

## §6 Adversarial review (handled by copowers wrapper)

The `copowers:executing-plans` wrapper invokes Codex MCP review on the combined Phase 5 diff after Task 5.6 lands. Pass these specific watch items:

- **Spec fidelity.** Phase 5 implements spec §3.6 verbatim — snapshot-at-entry-surface ToCToU pattern; cache resolution ONCE at entry-surface; `record_entry` persists snapshot AS-IS; CLI cached-only refusal gate symmetric with form stub gate; operator override dropdown {Accept algo / flag / none / other(text)}; free-text "other" canonicalized.
- **Plan fidelity.** Tasks executed in plan order (Task 5.0a FIRST as prerequisite); no skipped tasks; no tasks added beyond the plan + Task 5.0a; commit messages follow §4 rule 4 conventions.
- **ToCToU correctness.** Verify `record_entry` does NOT call `get_classification(...)` (or equivalent re-resolve). The temporal gap between form render and submit is the ToCToU window deliberately closed by spec §3.6.
- **CLI parity gate.** Test verifies CLI `--chart-pattern-operator <value>` for an out-of-scope ticker exits non-zero with explicit error message; does NOT silently allow.
- **Hidden form-field tampering threat model.** Spec §3.6 explicitly accepts this as residual V1 risk; verify the implementation comment / docstring acknowledges the trade-off (don't add server-side re-validation that contradicts the spec).
- **Observable verification (per §4 rule 5).** Each task implementation commit body contains the subject-only grep output. Absence is a finding.
- **Discriminating tests.** Per `feedback_regression_test_arithmetic` (extended 2026-04-26 with sort-coupling generalization): every test must produce different outcomes pre-fix vs post-fix. Vacuous tests are findings.
- **Compounding-confound.** For invariant tests (especially the cross-column ValueError tests inherited from Phase 2): if you delete the validation call, the test must fail (per 2026-04-26 lesson). Schema-layer FK constraints must NOT mask repo-layer ValueError tests (per Phase 2 lesson on PRAGMA foreign_keys=ON).
- **Bug-7-family anchor discipline.** `build_entry_form_vm` binds to `pipeline_runs.evaluation_run_id → pipeline_run_id` (single-round-trip pattern). NO `MAX(run_ts)` patterns; NO "latest by computed_at" fallback.
- **HTMX OOB-swap partial drift.** New `partials/trade_entry_chart_pattern_section.html.j2` must be used via `{% include %}` from BOTH the full-page render and any OOB-swap render path; no hand-duplicated markup.
- **Out-of-scope creep.** No modification to `swing/pipeline/`, `swing/rendering/`, `swing/evaluation/`, OR any `swing/data/` file other than `models.py` (Task 5.0a annotation-only).
- **Task 5.0a annotation completeness.** All 4 anchor-date fields retyped; `from datetime import date` added if needed; round-trip test verifies runtime + annotation alignment.
- **Classifier-error row handling.** Form display logic for tickers with `pattern=NULL` cache rows (classifier-error) treats them as "not classified"; no `flag (NULL)` artifact in UI; CLI refusal gate fires.

---

## §7 Done criteria

Phase 5 execution is done when ALL of the following hold:

- [ ] Task 5.0a + all Phase 5 tasks (5.1 through 5.6) have landed commits on `main`.
- [ ] Each task implementation commit message follows §4 rule 4 conventions; commit body contains §4 rule 5 observable verification evidence (subject-only grep output).
- [ ] No duplicate task implementations; no mixed-task commits.
- [ ] `python -m pytest -m "not slow" -q` green (full fast suite); baseline + new tests on Task 5.0a annotation + EntryRequest extension + record_entry snapshot persistence + TradeEntryFormVM extension + form template rendering + POST handler + CLI flag.
- [ ] `ruff check swing/web/ swing/trades/ swing/cli.py swing/data/` clean (no new violations).
- [ ] Trade-entry form (web) displays Chart Pattern section with algo classification + override dropdown for tickers WITH cached classification; "Not classified" stub for tickers WITHOUT.
- [ ] Trade-entry form submission persists snapshot AS-IS to trade row (algo + confidence + operator + audit anchor).
- [ ] CLI `swing trade entry --chart-pattern-operator <value>` works for tickers WITH cached classification; refuses with non-zero exit + explicit error message for tickers WITHOUT.
- [ ] No scratch pytest directories left in repo root (or any blocked dirs documented for orchestrator-side cleanup).
- [ ] Adversarial Codex review on combined Phase 5 diff reaches `NO_NEW_CRITICAL_MAJOR`.
- [ ] Phase 5 implementation does NOT touch `swing/pipeline/`, `swing/rendering/`, `swing/evaluation/`, OR any `swing/data/` file other than `models.py` (Task 5.0a annotation-only).

---

## §8 Return report format

Final message to orchestrator (via operator) MUST include:

```
PHASE: 5 (Trade-entry form + CLI) of chart-pattern flag-v1 plan
COMMIT CHAIN: <first SHA>..<last SHA> (N commits)
FAST SUITE: 1102 → <new count> tests (Δ +<count>)
ADVERSARIAL ROUNDS: <N>; FINAL VERDICT: NO_NEW_CRITICAL_MAJOR

TASKS COMPLETED:
- Task 5.0a — Annotation retype (Phase 2 carve-out extension), commit SHA
- Task 5.1 — EntryRequest extension + record_entry snapshot persistence, commit SHA
- Task 5.2 — TradeEntryFormVM extension + build_entry_form_vm cache resolution, commit SHA
- Task 5.3 — Form template Chart Pattern section, commit SHA
- Task 5.4 — POST handler reads new fields + builds EntryRequest with snapshot, commit SHA
- Task 5.5 — CLI flag + refusal gate, commit SHA
- Task 5.6 — Phase 5 checkpoint, commit SHA

PARTITIONING DISCIPLINE OUTCOME:
- Subagent count: <N>
- Task assignments: <list which tasks went to which subagent>
- Collisions detected: <none / list any with details>
- Pre-task deliverable-existence checks: <how many fired; how many aborted>
- Observable verification (per §4 rule 5 subject-only grep): <how many task commits included grep output; any false positives observed?>
- Scratch directories: <cleaned / list any remaining + ACL state>

TRADE-ENTRY INTEGRATION SUMMARY:
- EntryRequest extension: <fields added; snapshot semantics>
- record_entry snapshot persistence: <verify NO re-resolve; AS-IS persistence>
- TradeEntryFormVM extension: <fields added; cache resolution at form-render boundary>
- Form template Chart Pattern section: <algo display + override dropdown sample>
- POST handler: <new fields read; EntryRequest built with snapshot>
- CLI flag: <refusal gate behavior; sample error message>
- Operator-visible UI changes: <screenshot or prose description>

ADVERSARIAL FINDINGS (each with disposition):
- <finding>: FIXED in commit <SHA> / ACCEPTED with rationale: <text>

OPEN QUESTIONS FOR ORCHESTRATOR:
- <any plan/spec contradiction surfaced; otherwise "None">

LESSONS WORTH CAPTURING (process insights from execution):
- <bullet list, including any partitioning-discipline observations>

PHASE 5 → PHASE 6 HANDOFF NOTES:
- <anything Phase 6 (chart overlay painting) implementer needs to know that isn't in the plan>
```

---

## §9 If you get stuck

- **Plan/spec contradictions.** Surface in return report under "OPEN QUESTIONS." Do NOT amend the plan or spec; do NOT re-design.
- **TDD ordering uncertainty.** Failing-test-first. Phase 5's tasks are integration-style — strict per-task TDD applies cleanly.
- **Codex finding contradicts plan.** Apply receiving-code-review discipline. If finding correct AND plan wrong, surface to orchestrator. If finding wrong, document why with rationale.
- **Out-of-scope pull.** If a Phase 5 task seems to require touching out-of-scope code (Phase 6-7 territory or `swing/data/` beyond Task 5.0a), STOP. Surface as "OPEN QUESTIONS." Do NOT silently expand scope. Downstream tests of Task 5.0a's modified file ARE in-scope by extension.
- **Subagent collision detected mid-execution.** STOP, surface to orchestrator immediately. Document the collision details (task ID, subagent IDs, commit SHAs, redundancy nature, pre-commit grep output that should have caught it). Per §4: if Phase 5 collides despite the partitioning + observable verification, the orchestrator will escalate to worktree isolation in Phase 6+.
- **ToCToU concern.** If implementation seems to require `record_entry` re-resolving cache (e.g., for "consistency" or "freshness"), STOP. Spec §3.6 deliberately uses snapshot-at-entry-surface; re-resolve at submit re-opens the ToCToU window. Surface to orchestrator if you believe the spec is wrong.
- **Override canonicalization helper.** If you can't find the existing `canonicalize_hypothesis_label` (or equivalent) helper in `swing/trades/entry.py`, grep for it broadly (`grep -rn canonicalize swing/`); reuse the existing pattern; don't reimplement.

---

## §10 Anti-patterns specific to this execution

- **Scope creep into Phase 6 / Phase 7.** Phase 6 paints the chart overlay; Phase 7 adds integration tests + operator-labeled fixtures. Adding even small "while I'm here" wiring for those is out of scope.
- **Re-resolving cache in `record_entry`.** Spec §3.6 deliberately uses snapshot-at-entry-surface. Re-resolve at submit re-opens the ToCToU window.
- **Skipping Task 5.0a.** Phase 5 prerequisite. Without the annotation retype, Phase 5's downstream type checks on `cls.pole_start_date` will be `str` at the type-checker level even though runtime is `date`. Phase 6 will trip on the same.
- **Bundling Task 5.0a with Task 5.1 or other Phase 5 tasks in one commit.** Phase 2 carve-out extension MUST be auditable as a standalone commit per §2 (mirrors Phase 4 Task 4.0a pattern).
- **Touching `swing/data/` beyond `models.py`.** Task 5.0a is the SINGLE Phase 2 carve-out extension authorized for Phase 5; annotation-only. Any other `swing/data/` modification is out of scope.
- **Missing observable verification (per §4 rule 5).** EVERY task implementation commit body MUST contain the subject-only grep output. Codex will flag missing evidence.
- **CLI silently allows out-of-scope tickers.** Spec § locked-constraint #5 + Phase 1 brainstorm Codex R1 C1: CLI MUST refuse symmetrically with form stub gate. No silent fall-back.
- **Mixed-anchor mistakes.** Bind to `pipeline_runs.evaluation_run_id → pipeline_run_id` via single-round-trip query. Bug-7 family.
- **Hand-duplicated template markup.** New Chart Pattern section partial uses `{% include %}` for OOB-swap-safe partials.
- **Reimplementing canonicalization.** Reuse the existing `canonicalize_hypothesis_label` (or equivalent) helper.
- **Substring-match assertions.** Per the 2026-04-26 lessons: form-rendering + log-line + format assertions use exact-equality. Substring matching almost never distinguishes pre-fix from post-fix.
- **Vacuous architectural-separation tests** (per 2026-04-26 sort-coupling lesson). If a Phase 5 test claims "X does NOT influence Y," mentally simulate the SPECIFIC bug: is there an output value where bug AND correct behavior coincidentally agree? If so, INVERT the setup so the bug's output diverges.
