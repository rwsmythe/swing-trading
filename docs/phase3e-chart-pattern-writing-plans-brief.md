# Phase 3e — Chart-Pattern Flag-V1: Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.
**Mission:** Convert the operator-approved spec at `docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md` into an executable phased TDD implementation plan via `copowers:writing-plans`. Produce the plan, get adversarial Codex review on it, stop. Do NOT execute the plan; that is a future, separate dispatch.
**Expected duration:** ~1-2 hours (plan drafting + 2-5 rounds of Codex review on the plan).
**Output:** A plan document (location and naming per the writing-plans skill's conventions) committed to `main`, with adversarial verdict `NO_NEW_CRITICAL_MAJOR`.

---

## §0 Read first

In this order:

1. **`docs/orchestrator-context.md`** — project framing, copowers workflow, anti-patterns, lessons-captured (especially the 6 lessons from the 2026-04-26 chart-pattern brainstorm). Pay attention to: operator-drives discipline, Phase 2 isolation, no `--no-verify`, no amending, no Claude co-author footer.
2. **`docs/superpowers/specs/2026-04-26-chart-pattern-flag-v1-design.md`** — THE canonical spec for this implementation. Treat as source-of-truth for what to build. The spec passed 5 adversarial Codex rounds; the design questions are settled. Your plan executes this spec, NOT a re-design.
3. **`CLAUDE.md`** at repo root — gotchas, conventions. Especially: OHLCV fetch scope rule (and how the spec respects it), OhlcvCache breaker, base-layout shared VM gotcha (any new VM field needs adding to ALL base-layout VMs — `DashboardVM`, `PipelineVM`, `JournalVM`, `WatchlistVM`, `PageErrorVM`), HTMX OOB-swap partial drift, yfinance API regression patterns, mid-run `started_ts` ordering trap.
4. **`docs/phase3e-chart-pattern-brainstorm-brief.md`** — the brainstorm dispatch brief that produced the spec. Useful for understanding scope-rationale and why specific design decisions landed where they did.
5. **`docs/superpowers/specs/`** (browse) — examples of past spec docs for any patterns the spec leaves under-specified. Match conventions.

**Optional reference (do NOT treat as binding):**

- `docs/qullamaggie-mcp-capabilities.md` — the qullamaggie MCP server is connected and may be useful for clarifying the flag_pattern definition during plan drafting (e.g., `get_setup_criteria('flag_pattern')`). Reference-only per V2.1 §VII.F; the spec's geometric gates are the binding definition.

---

## §0 Skill posture

**INVOKE:**

- `copowers:writing-plans` — this brief's primary skill. The wrapper handles plan drafting, internal completeness review, and adversarial Codex review on the plan.

**DO NOT INVOKE (V1 STOP after plan is reviewed):**

- `copowers:executing-plans` / `superpowers:executing-plans` / `superpowers:subagent-driven-development` — execution is NOT part of this dispatch. Orchestrator will triage the plan and operator decides when to commission an execution dispatch.
- `superpowers:test-driven-development` — no code in this dispatch (TDD discipline applies during EXECUTION, not plan drafting).
- `copowers:brainstorming` / `superpowers:brainstorming` — design is settled. Do NOT re-litigate spec decisions in the plan-drafting flow.

The writing-plans skill produces a phased plan with explicit task ordering, acceptance criteria per phase, and TDD discipline baked in. Follow the skill's conventions for plan structure.

---

## §1 What's already locked (do NOT re-litigate during planning)

The spec encodes operator-set design decisions that are settled. The plan's job is to sequence the implementation, not to revisit any of these:

### From operator-set scope (six locked constraints, spec §1.1):

1. One pattern only: `flag_pattern`.
2. Display + persist on trades + confidence; production scoring/bucketing UNTOUCHED.
3. Compute timing: pipeline-time on chart-scope tickers (extends `_step_charts`).
4. Display surface: watchlist rows + trade-entry form + chart overlay.
5. Trade-entry consumption: cached-only; no out-of-scope manual-trade fallback.
6. Operator override: algo and operator stored separately on trade row; 4 columns total.

### From spec design decisions (settled across 5 adversarial rounds):

- Algorithm: rule-based geometric, deterministic search over (M, N) ∈ [5,30] × [5,21]; ALL 11 detection gates required for `detected=True` (listed in spec §3.1.3).
- Confidence: `min(four continuous-gate clearances)` on [0.0, 1.0]; framing is "geometric clearance score, NOT calibrated probability."
- Display threshold: `cfg.web.flag_pattern_display_threshold` configurable, default 0.0 (permissive at V1).
- Pipeline integration: extend `_step_charts` per-ticker loop, share in-hand OHLCV, per-ticker fenced write in same `lease.fenced_write()` as chart_target update. Classifier exception → cache row with `pattern=NULL`, components_json with `"error"` key.
- Persistence: migration 0009 (cache table), migration 0010 (4 columns on trades). Repo-layer cross-column constraint on trades; row-level CHECK on cache table.
- Watchlist: parallel `pattern_tags` VM field; `_sort_watchlist` byte-for-byte UNCHANGED.
- Operator override UI: dropdown {Accept algo / flag / none / other(text)}; default = Accept algo → NULL persisted; `other` canonicalized like `hypothesis_label` (NFC + control-byte stripping).
- CLI: `swing trade entry --chart-pattern-operator` mirrors form's stub gate; refuses for tickers without cached classification (per locked-constraint #5).
- Cache resolution at entry-surface ONCE; `record_entry` persists captured snapshot AS-IS (no re-resolve at submit) — ToCToU-aware design per R3 fixes.
- `pipeline_run_id` audit anchor persisted on trade row (R4 fix).
- Chart overlay: `render_chart` gains optional `pattern_overlay: PatternOverlay | None = None` kwarg; existing candidate-pivot hline preserved.
- Tests: 3 layers — unit (synthetic, discriminating-test pairs), integration (≥15 committed labeled fixtures: 8 flags + 7 non-flags spanning rejection cases), slow (deferred to backlog). Operator is the SOLE labeler; CSV is literal yfinance pull (no hand-edit); fixtures immutable (retire+replace, never edit-in-place).

If any of these surfaces a contradiction or impossibility during plan drafting, STOP. Do NOT re-design. Surface to orchestrator under "OPEN QUESTIONS FOR ORCHESTRATOR" in the return report.

---

## §2 What the plan MUST contain

The writing-plans skill drives the plan structure. Use its conventions. Beyond the skill's defaults, the plan MUST:

### Phase ordering

The spec has natural phasing. Suggested (verify with skill's conventions):

1. **Phase 1 — Algorithm core.** Pure-function `classify_flag` in `swing/evaluation/patterns/flag_classifier.py`; result dataclass; unit tests against synthetic data covering each gate (discriminating-test pairs). Zero dependencies on swing/data, swing/web. Can be developed in isolation.
2. **Phase 2 — Persistence layer (Phase 2 carve-out).** Migration 0009 (cache table); migration 0010 (4 trade columns); `pattern_classifications` repo; trade-repo extension threading new columns + repo-layer cross-column ValueError. Migrations apply cleanly; tests cover the NULL semantics matrix and the cross-column invariants.
3. **Phase 3 — Pipeline integration.** Extend `_step_charts` to call classifier per-ticker, write classification row in same fenced transaction as chart_target update; classifier-exception handling per spec §3.3; pipeline-level logging. Integration tests cover happy path + classifier-exception path.
4. **Phase 4 — Watchlist + dashboard read paths.** Add `pattern_tags` parallel VM field; render in templates; **VERIFY `_sort_watchlist` is byte-for-byte UNCHANGED** (sort-neutrality regression test). Behavioral parity-vector test confirms sort-neutrality.
5. **Phase 5 — Trade-entry form + CLI.** Form section for chart pattern (algo display + override dropdown); CLI flag with stub-gate refusal for out-of-scope tickers; cache resolution at entry-surface; EntryRequest extension; record_entry persists snapshot AS-IS.
6. **Phase 6 — Chart overlay.** `render_chart` gains `pattern_overlay` kwarg; pole/flag bands + algo-pivot horizontal segment + title annotation; existing candidate-pivot hline preserved.
7. **Phase 7 — Integration test suite.** ≥15 committed labeled OHLCV fixtures in `tests/evaluation/patterns/fixtures/`; integration tests across all 7 non-flag rejection cases + 8 flags spanning detection space.

(Phase numbering is suggested; the skill may prefer different boundaries. Whatever phasing emerges, ensure each phase ends in a green-fast-suite checkpoint.)

### Each phase MUST include

- **Pre-conditions:** what must be true (DB state, code state, tests green) before the phase begins.
- **TDD task ordering:** failing test → minimal implementation → see pass → commit. One red-green cycle per logical change. Spec § references for each task's acceptance criteria.
- **Per-task acceptance criteria:** how the implementer knows the task is done (verbatim test pass, specific behavior verified).
- **Phase-end checkpoint:** what to verify before declaring the phase complete (fast suite green, no new ruff violations, specific behaviors confirmed via manual trigger if applicable).
- **Phase-2 carve-out justification per file** (for Phase 2 of the implementation): which file in `swing/data/` is touched, why, and how it respects the carve-out boundary (CLAUDE.md: "during Phase 3 work, `swing/trades/` and `swing/data/` are read-only unless an explicit carve-out is granted in the brief").

### Test-strategy specifics (from spec §4)

- Layer 1 unit tests: discriminating-test pairs at every continuous threshold + new flag_floor_holds gate + classifier-error pattern=NULL + best-attempted ranking determinism.
- Layer 2 integration tests: ≥15 labeled fixtures (8 flag + 7 non-flag spanning rejection cases). Fixtures live in `tests/evaluation/patterns/fixtures/`. Spec §4.2 has the labeling protocol — operator is sole labeler; rubric = §3.1.3 + reference image; CSV is literal yfinance pull; fixtures immutable.
- Layer 3 slow tests: DEFERRED to backlog (do NOT include in V1 implementation; documented as deferred in spec §4.3).
- Sort-neutrality regression test: behavioral parity-vector fixture (NOT brittle `inspect.getsource` source-stability check per R2 m2).
- Compounding-confound test: deletes `_pattern_tags` call and asserts row order unchanged (per 2026-04-26 lesson on vacuous tests).

### Schema-migration specifics

- Migrations 0009 and 0010 land sequentially.
- 0009 creates `pipeline_pattern_classifications` table with row-level CHECK `pattern_state_consistency`. CREATE TABLE; no `swing/data/migrations/0009_*.sql` may be skipped.
- 0010 ALTERs `trades` to add 4 columns; FK on `chart_pattern_classification_pipeline_run_id` declared but enforcement depends on PRAGMA foreign_keys = ON (spec §3.2.2 has the nuance — preserve the qualifier in the migration comment).
- Migration tests verify both forward (apply on baseline DB) and idempotency (re-run is no-op). Schema_version updated to 10 by 0010.

---

## §3 Conventions

### Plan document

- Location and naming: per `copowers:writing-plans` / `superpowers:writing-plans` conventions. (Likely `docs/superpowers/plans/YYYY-MM-DD-chart-pattern-flag-v1-plan.md`.)
- Cross-reference spec sections explicitly per task (e.g., "implements spec §3.1.4 confidence formula").
- Commit the plan when done. Conventional-commit message: `docs(plans): chart-pattern flag-v1 implementation plan`.

### Commits during plan-drafting work

- **No Claude co-author footer.** No `--no-verify`. No amending.
- Conventional-commits: `docs(plans):`, `docs(specs):` for spec follow-ups (none expected; spec is settled).
- Each adversarial review fix lands as a NEW commit, not amend.

### Tests

- Plan must explicitly call for `python -m pytest -m "not slow" -q` to be green at every phase boundary.
- Plan must explicitly forbid introducing new ruff violations; baseline is 81 errors per CLAUDE.md.

---

## §4 Adversarial review (handled by copowers wrapper)

The `copowers:writing-plans` wrapper automatically invokes Codex MCP review on the resulting plan. The wrapper iterates rounds until `NO_NEW_CRITICAL_MAJOR`. Pass these specific watch items to Codex:

- **Spec fidelity.** Does the plan implement every settled spec design decision without re-litigation? Any deviation from the spec is a finding (unless the spec contains an internal contradiction the plan is resolving).
- **Locked-constraint preservation.** All six operator-set constraints (spec §1.1) preserved in the plan. Specifically: production scoring/bucketing UNTOUCHED; `_sort_watchlist` byte-for-byte UNCHANGED; cached-only consumption gate on both form AND CLI; algo+operator separate fields with audit anchor.
- **Phase ordering correctness.** Earlier phases produce no fragments that consumers would see (e.g., Phase 1 algorithm shipping before Phase 2 persistence is fine because no consumer touches it; Phase 4 watchlist render shipping before Phase 3 pipeline integration would render empty tags — order check).
- **TDD discipline.** Every implementation task is preceded by a failing-test task. No "implement and write tests after" sequencing.
- **Discriminating tests.** Any test the plan specifies must produce a different outcome under post-fix code than under pre-fix code (per `feedback_regression_test_arithmetic` memory). Vacuous tests are findings.
- **Compounding-confound failure mode** (per 2026-04-26 lesson): when a test asserts on a primary key, would temporarily disabling the keyed-on element still pass the test? If so, vacuous test.
- **Phase 2 carve-out enumeration.** For Phase 2 of the implementation (the persistence-layer phase touching `swing/data/`), every file modified is enumerated with justification.
- **CLAUDE.md gotcha respect.** New VM fields added to ALL base-layout VMs (`DashboardVM`, `PipelineVM`, `JournalVM`, `WatchlistVM`, `PageErrorVM`); HTMX OOB-swap partials use `{% include %}` not hand-duplicated markup; `started_ts DESC` ordering does not mask in-flight rows.
- **Cache invariant correctness.** Pipeline-cached classifications bind to `pipeline_runs.evaluation_run_id` (Bug-7-family anchor); no fallback to "latest by computed_at" anywhere.
- **Operator-confirmation gates.** No operator-confirmation gates needed (this is plan drafting, not bug-fix investigation; design is operator-approved).
- **Test sample-size feasibility.** ≥15 labeled fixtures requires operator labeling time. Plan must scope this realistically (operator is the sole labeler per spec §4.2; cannot be implementer-labeled). If the plan implies the implementer fabricates the labels, that's a critical finding.
- **Migration sequencing safety.** 0009 and 0010 land in order; idempotency tested; no schema regressions to lower numbers.
- **Cross-column constraint enforcement.** Spec §3.2.2 specifies repo-layer enforcement on trades; schema-layer hardening is V2. Plan must NOT silently promote schema-layer enforcement to V1 (would require CREATE-COPY-DROP-RENAME migration, which is not in V1 scope).

---

## §5 Done criteria

The plan-drafting dispatch is done when:

- [ ] Plan doc exists at the writing-plans-skill-conventional location, committed to `main`.
- [ ] Plan covers all V1 deliverables in spec §1.2 (algorithm, migrations, pipeline integration, watchlist, trade-entry form, CLI, chart overlay, tests).
- [ ] Plan respects all six locked constraints in spec §1.1.
- [ ] Adversarial Codex review reached `NO_NEW_CRITICAL_MAJOR`.
- [ ] Plan does NOT include execution; execution is a future, separate dispatch.
- [ ] Plan does NOT re-design any spec decision.

---

## §6 Return report format

Final message to orchestrator (via operator) MUST include:

```
PLAN: <path-to-plan-doc>
COMMIT: <SHA>
ADVERSARIAL ROUNDS: <N>; FINAL VERDICT: NO_NEW_CRITICAL_MAJOR

PHASE SUMMARY:
- Phase 1: <name + 1-line scope>
- Phase 2: <name + 1-line scope>
- ...

ESTIMATED EXECUTION SESSIONS: <N> (gate at end of each phase to fast-suite green checkpoint)

ADVERSARIAL FINDINGS (each with disposition):
- <finding>: FIXED in commit <SHA> / ACCEPTED with rationale: <text>

OPEN QUESTIONS FOR ORCHESTRATOR:
- <any spec contradiction surfaced; otherwise "None">

LESSONS WORTH CAPTURING (process insights from this plan-drafting):
- <bullet list, if any>
```

---

## §7 If you get stuck

- **Spec-internal contradictions.** Surface in return report under "OPEN QUESTIONS FOR ORCHESTRATOR." Do NOT resolve unilaterally; do NOT amend the spec. The orchestrator handles spec amendments via a separate brainstorm-amendment dispatch if needed.
- **Codex finding contradicts spec.** Apply receiving-code-review discipline. If finding is correct AND spec is wrong, surface to orchestrator. If finding is wrong, document why with rationale.
- **TDD ordering uncertainty.** When in doubt about whether a task is failing-test-first or implementation-first, check the writing-plans skill conventions; default to failing-test-first.
- **Phase boundary uncertainty.** When unsure if a logical change should split into multiple phases or stay together, use the "fast suite green" criterion: if a partial implementation can leave the suite green at a checkpoint, it can be its own phase.
- **Spec scope uncertainty.** If the spec leaves something explicitly DEFERRED, the plan does NOT include it. Document as out-of-V1-scope in plan.

---

## §8 Anti-patterns specific to this plan-drafting

- **Re-designing spec decisions.** The 5-round adversarial arc settled the design. Re-litigation in plan drafting wastes context and risks introducing inconsistencies between spec and plan.
- **Sneaking V2 features into V1.** Spec §1.3 enumerates what V1 does NOT ship. Plan must NOT include those.
- **Implicit Phase 2 carve-outs.** Every file modified in `swing/data/` or `swing/trades/` MUST be enumerated with justification (per CLAUDE.md isolation rule). Spec §5 has the carve-out list; plan must reproduce or reference it explicitly.
- **Test-after-implementation sequencing.** TDD discipline is RIGID. Failing test → see fail → minimal impl → see pass → commit. One cycle per logical change.
- **Vacuous regression tests.** Per `feedback_regression_test_arithmetic` memory and 2026-04-26 compounding-confound lesson, every regression test must produce different outcomes under pre-fix vs post-fix code; assertion on primary-key behaviors must be empirically verified by deleting the keyed-on element and confirming the test now fails.
- **Skipping the operator-labeling time for fixtures.** Spec §4.2 requires the OPERATOR to label fixtures, not the implementer. Plan must scope this realistically; operator labeling time is part of execution, not implementer-time.
