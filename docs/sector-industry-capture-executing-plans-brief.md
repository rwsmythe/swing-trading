# Sector/Industry Capture + Display — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute the implementation plan at `docs/superpowers/plans/2026-04-28-sector-industry-capture-plan.md`. Ship V1 of sector/industry capture + display via 9 sequential implementation tasks + 1 verification task (Tasks 1–10). The plan IS the spec; this dispatch is plan-faithful execution.

**Expected duration:** 9 sequential implementation tasks + verification task + 3-5 Codex rounds via `copowers:executing-plans` wrapper = ~6-10 hours of work, parallelizable to operator pacing.

**Dispatch type:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development` with adversarial Codex review post-execution). Single-subagent dispatch.

---

## §0 Read first

Read these in order before starting Task 1:

1. **The plan:** `docs/superpowers/plans/2026-04-28-sector-industry-capture-plan.md` — THE CANONICAL SCOPE. 2,406 lines; read all of it before invoking the executing-plans skill. The plan was authored via a `copowers:writing-plans` cycle (4 Codex rounds, terminating `NO_NEW_CRITICAL_MAJOR`); it supersedes the writing-plans brief in case of any divergence.
2. **`docs/sector-industry-capture-writing-plans-brief.md`** — historical reference for design-decision context. Plan §"Goal" + §"V1 Scope" supersede where they differ.
3. **`CLAUDE.md`** — project conventions, gotchas, invariants. Note especially the test-count drift gotcha (trust pytest output, not plan-pinned counts), the base-layout 5-VM rule (plan-verified does NOT apply to this dispatch), and the discriminating-test failure modes documented in CLAUDE.md gotchas.
4. **`docs/orchestrator-context.md`** — read these sections:
   - §"Currently in-flight work" (current state at HEAD; sector dispatch is Phase 1 of a 6-phase sequence)
   - §"Binding conventions" (4-tier commit-message convention; observable-verification ERE-grep form; ruff baseline 91; no-amend rule; no Claude co-author footer; subject-only grep regex with `-E` flag and POSIX `[0-9]` digit class)
   - §"Anti-patterns to avoid" (vacuous regression tests; mid-session scope expansion; brief drafting drift; bug-fix investigation that tests plausible mechanisms instead of operator's actual reproduction)
   - §"Lessons captured" (read entire section — multiple lessons apply to this dispatch; particularly: discriminating-test discipline; compounding-confound class; canonical-template references win over prose count assertions; subsequent-phase tests can surface earlier-phase contract bugs; manual visual verification is required for rendering work)
5. **`docs/phase3e-todo.md`** §"2026-04-28 sector/industry capture + display" — backlog context. Plan implements this section.

If any file path doesn't resolve, surface in return report — do NOT silently proceed against a stale path.

---

## §0 Skill posture

- **INVOKE** `copowers:executing-plans` — wraps `superpowers:subagent-driven-development` with adversarial Codex review post-execution. The wrapper skill handles the Codex cycle internally; do not invoke `copowers:adversarial-critic` separately.
- **DO NOT INVOKE** `superpowers:brainstorming`, `copowers:brainstorming`, `superpowers:writing-plans`, or `copowers:writing-plans`. The plan is locked. Re-litigation is out of scope. If a plan task appears impossible to implement as written, STOP and surface in return report via §6 escape hatch; do NOT silently re-design.
- **DO** invoke adversarial Codex review per `copowers:executing-plans` standard cycle. Iterate to `NO_NEW_CRITICAL_MAJOR`. Round budget: ~3-5 typical for a plan that already had 4 writing-plans Codex rounds (plan-rigor compounds; executing-plans rounds should be modest).
- **Single-subagent dispatch** per the 8-phase ZERO-rogue track record (chart-pattern flag-v1 Phases 4-7 + Tier-1 mathtext + Tier-2 #2/#3 + chart-scope-policy-v2 writing-plans + chart-scope-policy-v2 executing-plans). NO parallel-subagent dispatch at the task level. Subagent role-partitioning WITHIN a task (e.g., implementer + internal-code-reviewer + internal-Codex-fix-implementer) is collision-safe per the Phase 6 lesson; only task-level partitioning is the binding constraint.

---

## §1 Strategic context

**This dispatch closes a data-flow gap.** Finviz CSV ingestion validates Sector + Industry columns at `swing/pipeline/finviz_schema.py:12` but the values are dropped before persistence. Per orchestrator-context.md lines 156-157 the framework PRESUMES sector analysis happens during operator decision; until this ships, operator looks up sector externally per ticker.

**Sequencing context.** This dispatch is Phase 1 of a 6-phase post-2026-04-28 sequence: sector → hyp-recs trade-prep expansion → OHLCV archive → noise queue → configuration page → Tier-3 design. The hyp-recs trade-prep expansion brainstorm (Phase 2) consumes the captured field WITHOUT any data-plumbing rework — `swing/web/view_models/dashboard.py:552-581` already reads from `candidates_by_ticker` per the plan's File Map.

---

## §2 V1 Scope (operator-confirmed 2026-04-28; LOCKED)

**3-of-4 display surfaces** per plan + orchestrator confirmation post-writing-plans return report:

1. **Watchlist row expansion** (Task 8).
2. **Trade entry form** (Task 6 — read-only display rows + hidden inputs).
3. **Open positions row** (Task 9 — informational `<th>` + cell additions).

**Hyp-recs row expansion DEFERRED** to the future hyp-recs trade-prep expansion brainstorm dispatch (Phase 2 of operator sequence). The data IS captured by Tasks 2 + 4 (`Candidate` dataclass + dashboard VM read site at `swing/web/view_models/dashboard.py:552-581`); the deferred expansion will wire up the display surface without any data-plumbing rework. **Do NOT add a column-based hyp-recs display in this dispatch** even if it seems trivial — that scope was deliberately moved to Phase 2 to avoid two surface-touching dispatches on overlapping templates. Adversarial Codex review may flag the absent hyp-recs display surface; respond ACCEPTED-with-rationale citing this brief §2 + plan deferral note.

**All 9 implementation tasks (1–9) plus the verification task (10) are in scope.** Plan §"V1 Scope" + §"File Map" enumerate them.

---

## §3 Binding conventions (excerpts; full per orchestrator-context.md)

These are NON-NEGOTIABLE across all task implementations:

1. **Branch:** `main`. No feature branches. No `--no-verify`. No amending; create new commits to fix.
2. **No Claude co-author footer.** Plain conventional-commits messages only.
3. **4-tier commit-message convention** (per orchestrator-context Binding conventions):
   - Task implementation: `feat(area): Task N — <description>` (the plan uses flat `Task N` numbering per chart-scope-policy-v2 precedent; do NOT use `Task N.M`)
   - Codex review-fix: `fix(area): Codex R<round> Major <id> — <description>`
   - Internal-Codex within-task: append `(internal)` qualifier — `fix(area): Codex R1 Major 1 (internal) — <description>`
   - Internal code-review: `fix(area): code-review I<id> — <description>`
   - Format-only cleanup: no task ID required
4. **Observable-verification subject-only grep BEFORE each task implementation commit:**
   ```
   git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task <N>'
   ```
   Note: `-E` flag is REQUIRED (BRE chokes on `+`); POSIX `[0-9]` for digit class if matching round IDs. Plan §"Per-Task Observable-Verification Subject-Only Grep" specifies the exact regex per task. Include the grep output in the commit body before the implementation commit lands.
5. **TDD discipline (per task):** failing test first → minimal implementation → passing test → commit. One red-green cycle per logical change.
6. **Discriminating-test discipline (HARD requirement per plan §"Compounding-Confound + Discriminating-Test Discipline"):**
   - Hard-coded "Technology" / "Software" sector/industry defaults are FORBIDDEN as discriminators.
   - Tests must use sector + industry values that are visually distinct from any plausible default and from each other across rows (plan recommends `"Healthcare" / "Biotechnology"` and `"Energy" / "Oil & Gas E&P"`).
   - Mocked candidate fixtures must populate sector + industry to KNOWN non-empty values that DIFFER from any test-helper default.
   - For each task with a discriminating assertion, the implementer MUST mentally verify "would this test fail if the implementation never actually called the new code?" before committing the test. Per Phase 4 + chart-scope-policy-v2 lessons: discriminating arithmetic on paper is insufficient; empirically verify the discriminator by temporarily disabling the keyed-on element and re-running the test.
7. **Ruff baseline 91 errors** (pre-existing in legacy code; documented in orchestrator-context Binding conventions). Tasks must NOT introduce new violations; do NOT incidentally fix the baseline.
8. **Test discipline:** `python -m pytest -m "not slow" -q` is the fast suite; must stay green throughout. Slow suite is not required for this dispatch.
9. **Phase isolation:** plan-authorized scope only. The plan touches `swing/data/` (migration + models + repos) AND `swing/trades/` (entry.py for sector/industry plumbing) — both are explicit Phase 2 carve-outs justified by plan §"V1 Scope". Do NOT extend scope to other Phase 2 territory absent explicit operator authorization.

---

## §4 Adversarial review watch items (for Codex during executing-plans cycle)

These are the high-likelihood failure modes Codex should specifically check post-execution. Pre-empt by self-checking BEFORE each task commit:

1. **Discriminating-test vacuousness on sector/industry assertions.** Per plan §"Compounding-Confound" discipline, tests must use sector/industry values that diverge across rows AND from any plausible fallback. Hard-coded "Technology" defaults that match a test-helper default = vacuous test. Codex will likely surface this if it occurs.
2. **Migration 0012 default-empty-string preservation.** The migration adds `NOT NULL DEFAULT ''` columns. Existing INSERTs that omit sector/industry must continue to succeed (covered by plan Task 1 test). Verify no existing code silently filters on `sector IS NULL` (there shouldn't be any, but check).
3. **Snapshot-at-entry-surface ToCToU pattern compliance.** Per spec §3.6 + Phase 5 lesson. The candidate's sector at form-render time is what gets persisted; do NOT re-resolve at submit-time. Mirror the `chart_pattern_*` precedent. Plan Task 6 specifies the pattern; verify implementation matches.
4. **CLI auto-resolution failure mode.** Per plan Task 7, when a candidate row doesn't exist for the entered ticker (e.g., off-pipeline trade), persist empty strings + log a warning (graceful degradation; matches `hypothesis_label` free-text behavior). Verify the test discriminates between "candidate exists, sector populated" vs "no candidate, empty string" branches per Codex R2 Major fix in plan history.
5. **Soft-warn confirm round-trip preserves sector/industry** per plan Task 6 + Phase 5 lesson "Codex's contextual advantage at finding cross-feature interactions." The soft-warn confirm path re-renders the form with `form_values` dict; if sector/industry aren't serialized into that dict, the second-submit silently drops them. Plan Task 6 should already address this; verify implementation matches.
6. **Open-positions colspan alignment** per plan Task 9 + Codex R3 Major. New `<th>Sector</th>` + `<th>Industry</th>` change column count from N to N+2; the open-positions-expanded `colspan` must update in lockstep. Plan calls this out; verify implementation matches.
7. **Sort-neutrality structurally guaranteed** per plan §"Sort-key NOT touched". Sector/industry are decorative-only fields; do NOT enter any sort or prioritization tuple. Codex may flag the absence as oversight; respond ACCEPTED-with-rationale citing the chart-pattern flag-v1 R1 M2 lesson + plan rationale.
8. **Hyp-recs row expansion absence** per §2 above. Codex will likely flag the data being captured but not displayed. Respond ACCEPTED-with-rationale citing this brief §2 + plan deferral note + operator confirmation.

---

## §5 Done criteria

- All 10 plan tasks complete (9 implementation + 1 verification).
- Each task implementation commit follows the 4-tier convention with observable-verification grep output in commit body.
- Final fast-test count documented and reconciled against plan's projection (test baseline pinned at HEAD `ba2b252` was 1203 fast tests; plan §"Test Count Projection" should give the expected post-dispatch number).
- Adversarial Codex review reaches `NO_NEW_CRITICAL_MAJOR`.
- All commits pushed to `origin/main`.
- Operator-runnable migration: `swing db-migrate` applies migration 0012 cleanly to operator's production DB. (Implementer ships migration code; operator runs `db-migrate` post-dispatch; orchestrator triages return report and gives operator the green-light to migrate.)
- Return report posted per §6.

---

## §6 Return report format

Post as final message:

```
## Sector/Industry Capture — Executing-Plans Return Report

**Plan executed:** docs/superpowers/plans/2026-04-28-sector-industry-capture-plan.md (commit b2ab6fa)
**Commit chain:** <first SHA> → <last SHA> on origin/main
**Total commits:** N (M task implementations + K review-fix commits + L cleanup)
**Codex rounds:** N rounds, terminating at NO_NEW_CRITICAL_MAJOR
**Fast-test count:** <count> at HEAD <SHA> (delta: +N from baseline 1203)
**Migration version:** 0012 (committed; not yet applied to production DB — operator will run swing db-migrate)

**Tasks completed:**
1. <Task 1 summary + commit SHA>
2. <Task 2 summary + commit SHA>
... (per task)

**Codex findings dispositioned:**
- R1: <count> Critical, <count> Major, <count> Minor — <breakdown>
- R2: ...
... (per round)

**Operator-action items:**
- Run `swing db-migrate` against production DB to apply migration 0012.
- Operator-witnessed verification of sector/industry display on the 4 implementing surfaces (watchlist expansion, trade entry form, open positions row, plus the 3-of-4 confirmation that hyp-recs displays as before with no sector/industry).

**Open questions for orchestrator triage:**
- <any items the implementer flagged as needing operator/orchestrator decision>

**Recommended next dispatch:** Phase 2 of operator sequence — hyp-recs trade-prep expansion brainstorm.
```

---

## §7 If you get stuck

- **If a plan task appears impossible to implement as written:** STOP, surface in return report. Do NOT silently re-design. Examples: a precedent file path doesn't resolve at runtime; an assertion the plan specifies is structurally impossible; a fixture pattern the plan references doesn't exist.
- **If a precedent file path doesn't resolve:** Use `Glob` / `Grep` to find the actual current path. The plan was pinned at HEAD `ba2b252` which was 4 commits ago at dispatch time — file paths should be stable but verify if any task seems off.
- **If Codex round count exceeds 5 without convergence:** STOP, surface in return report with the unresolved finding. Do NOT iterate indefinitely.
- **If discriminating-test sanity check reveals vacuousness on a primary-key assertion:** STOP, restructure the test setup to invert the symmetry per Phase 4 lesson, then resume. This is plan-quality investment worth the time.
- **If you find a scope-deviation opportunity** (e.g., a refactor that would make Task X cleaner but isn't in the plan): SURFACE in return report as a follow-up; do NOT in-line-implement. Per orchestrator-context anti-pattern: "Mid-session scope expansion."

---

## Appendix A: Plan-history awareness

The plan went through 4 writing-plans Codex rounds before this dispatch. Major findings already addressed:

- R1 M1-5: schema migration test pattern; CLI no-candidate test split; goal/scope text normalization; latest_evaluation_run_id helper adoption; column-based hyp-recs deferral.
- R2 M1-2: incremental v11→v12 migration test; CLI discriminating-test split.
- R3 M1-2: pytest -k filter widening; expected-test-count arithmetic; commit-message body templates.
- R4: clean.

Plan-history is durable in `docs/superpowers/plans/2026-04-28-sector-industry-capture-plan.md` commit chain (`ac685bb` → `46d8c55` → `0d1c16b` → `b2ab6fa`). Implementer should NOT re-iterate on resolved findings; if a Codex round in THIS dispatch raises a finding that already has a plan-history fix, cite the plan and the fix commit, then proceed.

## Appendix B: Cross-import precedent (informational)

Plan Task 6 + Task 7 use `latest_evaluation_run_id()` from `swing.web.view_models.dashboard` from non-web call-sites (CLI). This is the second cross-import (first was `_lookup_active_recommendation_label` from hypothesis pre-fill). Captured as a noise-queue follow-up: "Factor non-web utility helpers out of `swing.web.view_models.dashboard` once 3+ cross-imports exist." This dispatch should NOT factor the helper — that's a separate small refactor dispatch when the noise queue runs.
