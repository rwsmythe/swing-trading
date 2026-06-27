# Phase 4 Cleanup-Remainder Bundle — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute the implementation plan at `docs/superpowers/plans/2026-04-30-phase4-cleanup-remainder-plan.md` (commit `6f548e1`; 6 Codex rounds [5 substantive + R6 verification clean] → NO_NEW_CRITICAL_MAJOR). Ship Phase 4 of the post-2026-04-28 operator sequence via 12 sequential tasks. The plan IS the spec; this dispatch is plan-faithful execution.

**Expected duration:** 12 tasks + 2-4 Codex rounds via `copowers:executing-plans` wrapper = ~8-12 hours of work, paced to operator pacing.

**Dispatch type:** `copowers:executing-plans` (wraps `superpowers:subagent-driven-development` with adversarial Codex review post-execution). Single-subagent dispatch.

**Pre-vetted depth:** plan went through 5 substantive writing-plans Codex rounds + 1 verification round (R6 clean). 18 Major findings caught + resolved at writing-plans phase. Plan-rigor compounded heavily — executing-plans Codex rounds should be modest (2-3 typical).

---

## §0 Read first

1. **The plan:** `docs/superpowers/plans/2026-04-30-phase4-cleanup-remainder-plan.md` (commit `6f548e1`) — THE CANONICAL SCOPE. Read all of it before invoking the executing-plans skill. The plan supersedes the writing-plans brief in case of any divergence (4 brief-vs-reality discrepancies were resolved in the plan; see Appendix A).

2. **`docs/phase4-cleanup-remainder-writing-plans-brief.md`** — historical reference. Plan §"Goal" + per-task bodies supersede where they differ.

3. **`CLAUDE.md`** — particularly:
   - **HTMX OOB-swap partial drift** — relevant to Task 9 (`<tbody>`-shape check supplementing `<thead>` byte-equivalence on `/hyp-recs/refresh`).
   - **External-API empty-result transient** (just-added 2026-04-30) — context for Task 8 (parallel cold-start test).
   - **HTMX `<tr>`-leading makeFragment gotcha** — context for the multi-rebuild drift Task 12.

4. **`docs/orchestrator-context.md`** — read these sections:
   - §"Currently in-flight work" — current state at HEAD; this dispatch is Phase 4.
   - §"Binding conventions" — 4-tier commit-message convention; observable-verification grep ERE form; ruff baseline 91; no-amend; no Claude footer.
   - §"Anti-patterns" — particularly mid-session scope expansion; vacuous regression tests; brief drafting drift.
   - §"Lessons captured" — read entire section. Particularly relevant:
     - **Bug-class durability vs scope-of-closure** (2026-04-29) — DIRECTLY applicable; this dispatch IS the durable closure of Bug 7.
     - **Helper-internal anchoring of side-effecting boundaries** (2026-04-30) — relevant to Task 1's helper extension.
     - **Multi-path-ingestion** (2026-04-29) — directly applicable to the 7 inline-query site migrations.
     - **MAX_ROUNDS-vs-NO_NEW_CRITICAL_MAJOR** (2026-04-29) — verification round if final round had findings.
     - **External-API empty-result transient** (2026-04-30) — relevant to Task 8.

5. **`docs/phase3e-todo.md`** §"From Session 2 (watchlist sort-by-tags)" + §"2026-04-29 production-verification investigation dispatch follow-up" + §"2026-04-30 OHLCV archive Phase 3 follow-up" — backlog source for the 5 cleanup items.

6. **Precedent executing-plans briefs:**
   - `docs/sector-industry-capture-executing-plans-brief.md` (Phase 1).
   - `docs/hyp-recs-trade-prep-expansion-executing-plans-brief.md` (Phase 2 main).
   - `docs/hyp-recs-success-path-fix-executing-plans-brief.md` (Phase 2 cleanup).
   - `docs/ohlcv-archive-consolidation-executing-plans-brief.md` (Phase 3).

If any file path doesn't resolve, surface in return report — do NOT silently proceed against a stale path.

---

## §0 Skill posture

- **INVOKE** `copowers:executing-plans` — wraps `superpowers:subagent-driven-development` with adversarial Codex review post-execution.
- **DO NOT INVOKE** `superpowers:brainstorming`, `copowers:brainstorming`, `superpowers:writing-plans`, or `copowers:writing-plans`. The plan is locked. Re-litigation is out of scope. If a plan task appears impossible to implement as written, STOP and surface in return report via §8 escape hatch; do NOT silently re-design.
- **DO** invoke adversarial Codex review per `copowers:executing-plans` standard cycle. Iterate to `NO_NEW_CRITICAL_MAJOR`. Round budget: ~2-3 typical (plan went through 5 substantive writing-plans rounds + R6 verification clean). **Per the chart-pattern flag-v1 Phase 7 induced-bug pattern + 2026-04-29 hyp-recs writing-plans MAX_ROUNDS lesson:** if the final round produces findings that resolve, run ONE additional verification round to confirm clean before terminating. Do NOT stop at MAX_ROUNDS with active findings.
- **Single-subagent dispatch** per the 12-phase ZERO-rogue track record. NO parallel-subagent dispatch at the task level. Subagent role-partitioning WITHIN a task is collision-safe.

---

## §1 Strategic context

**This dispatch ships Phase 4 cleanup-remainder bundle** — closes durable Bug 7 mixed-anchor family + 4 smaller follow-ups deferred from Phase 1, 2, and 3. Per the just-captured "Bug-class durability vs scope-of-closure" lesson (2026-04-29), the durable fix is centralization at chokepoint via two-helper-per-contract pattern.

**Sequencing.** Phase 4 of the 6-phase post-2026-04-28 sequence. Phase 5 (configuration page) follows. Hypothesis_label web-form gap (just-captured 2026-04-30) queues as Phase 4.5 standalone OR rolls into Phase 5 — operator decides post-Phase-4-ship.

---

## §2 V1 Scope (per plan; LOCKED)

The plan IS the canonical scope source-of-truth. Plan §"V1 Scope" + §"Tasks" enumerate the work. Execute as written.

**12 plan tasks per plan:**

**Bug 7 durable closure (Tasks 1-6):**
1. **Task 1:** Helper foundation. `PipelineRunBinding` extended with `action_session_date` (additive); per-helper unit tests EXERCISE the existing `id DESC` tiebreaker (tied-finished_ts / tied-run_ts states). Both helpers (`latest_completed_pipeline_run`, `latest_evaluation_run_id`) are at HEAD with the right names per writing-plans Q-A discovery.
2. **Tasks 2-5:** 4 file-scoped migrations (7 inline-query sites total per writing-plans Q-B classification; one site `dashboard.py:601` intentionally NOT migrated — in-flight-state read with `ORDER BY started_ts DESC`):
   - Task 2: `dashboard.py` migrations (3 sites: today_decisions/classifications, last_pipeline_ts, stale_banner) — all pipeline-bound contract.
   - Task 3: `watchlist.py` migrations (DUAL-CONTRACT: classifications via `latest_completed_pipeline_run` pipeline-bound; candidates via `latest_evaluation_run_id` with-fallback).
   - Task 4: `trades.py:133` (pipeline-bound) + `cli.py:456` (pipeline-bound).
   - Task 5: `routes/pipeline.py:316` (with-fallback).
3. **Task 6:** Global structural-guard test — regex covering table aliases + `_strip_python_line_comments` helper for false-positive defense (per writing-plans Q-C TWO-test strategy).

**Other follow-ups (Tasks 7-12):**

4. **Task 7:** `research/parity/run.py:178` `_CountingPriceFetcher` rewrite for new archive directory shape + smoke test for runtime call-site at line 331. Step 8 stages a threshold-divergence-risk follow-up to `phase3e-todo.md` in the same commit.
5. **Task 8:** Parallel cold-start test with today-aligned archive (true zero-yfinance via full-module `yfinance` MagicMock + `mock_calls == []` assertion).
6. **Task 9:** `<tbody>`-shape check supplementing `<thead>` byte-equivalence in `test_refresh_route_renders_drift_equivalent_html_to_full_page`.
7. **Task 10:** Non-equal-priority sort-neutrality fixture in `tests/web/test_view_models/test_hyp_recs_sort_neutrality.py` (corrected path per Q-B; reverse-alphabetical discriminator).
8. **Task 11:** Lift `_seed_watchlist_and_candidate` to `tests/web/conftest.py` (only ONE file uses the named helper per Q-B; corrected example transformation).
9. **Task 12:** Multi-rebuild drift behavior-pin — `NotImplementedError` placeholder + concrete monkeypatch recipe via `swing.web.routes.trades.build_dashboard` + `threading.Event` coordination. **SKIP FALLBACK EXPLICITLY FORBIDDEN per Codex disposition** — pin actual behavior; don't dodge.

---

## §3 Binding conventions (excerpts; full per orchestrator-context.md)

NON-NEGOTIABLE across all task implementations:

1. **Branch:** `main`. No feature branches. No `--no-verify`. No amending; new commits to fix.
2. **No Claude co-author footer.** Plain conventional-commits messages only.
3. **4-tier commit-message convention:**
   - Task implementation: `feat(<area>): Task N — <description>` (flat numbering per chart-scope-policy-v2 + sector + hyp-recs + OHLCV precedents).
   - Codex review-fix: `fix(<area>): Codex R<round> Major <id> — <description>`.
   - Internal-Codex within-task: append `(internal)` qualifier.
   - Internal code-review: `fix(<area>): code-review I<id> — <description>`.
   - Format-only cleanup: no task ID required.
4. **Observable-verification subject-only grep BEFORE each task commit:**
   ```
   git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task <N>'
   ```
   ERE flag REQUIRED. Cross-plan grep aliasing is expected (per the sector + hyp-recs + OHLCV precedents). Disambiguate within THIS dispatch's chain by commit subject.
5. **TDD discipline (per task):** failing test first → minimal implementation → passing test → commit. One red-green cycle per logical change. **For migration tasks 2-5: TWO-test strategy per Q-C** — source-level RED-phase test drives the per-task TDD; behavioral standalone-eval-only-state contract test pins the contract semantics.
6. **Discriminating-test discipline (HARD requirement per plan task bodies):**
   - **Tasks 2-5 (migrations):** behavioral test must construct standalone-eval-only state (no completed pipeline_runs). Vacuous test that doesn't exercise this state would mask the contract distinction.
   - **Task 6 (structural-guard):** regex must catch inline `pipeline_runs WHERE state='complete'` queries OUTSIDE the two helpers. False-positive defense via `_strip_python_line_comments` MUST be present (the regex would catch comment-mentions otherwise; vacuous test that fires on a comment is non-discriminating).
   - **Task 8 (cold-start):** TRUE zero-yfinance — mock yfinance MODULE-level (NOT just `yf.download`) AND assert `mock_calls == []` AT END. Vacuous test that mocks only `yf.download` would still satisfy the existing weakness.
   - **Task 10 (sort-neutrality):** non-equal-priority fixture with reverse-alphabetical discriminator. Vacuous fixture (alphabetical tiebreak masks priority_hint distinction) would be a discriminating-test failure per the chart-pattern flag-v1 Phase 4 ticker-symmetry-vacuousness lesson.
   - **Task 12 (drift behavior-pin):** `threading.Event` coordination must construct a real mid-POST-pipeline-run scenario; SKIP FALLBACK is forbidden. Vacuous test that skips when threading is unavailable would not pin behavior.
7. **Ruff baseline 91 errors** unchanged. Tasks must NOT introduce new violations.
8. **Test discipline:** `python -m pytest -m "not slow" -q` is the fast suite; must stay green throughout.

---

## §4 Adversarial review watch items (for Codex during executing-plans cycle)

These are the high-likelihood failure modes Codex should specifically check post-execution. Pre-empt by self-checking BEFORE each task commit:

1. **Per-site contract correctness** per writing-plans Q-B classification. Each migrated site must consume the helper that matches its UX contract (with-fallback for surfaces that need standalone-eval-only-state rendering; pipeline-bound for surfaces that should be absent absent pipeline data).

2. **Standalone-eval-only-state behavioral test coverage** — Tasks 2-5. Each migrated site's behavioral test constructs no-completed-pipeline-runs state and asserts site-specific expected behavior. Codex will check that the test setup is genuinely standalone-eval-only (no `pipeline_runs WHERE state='complete'` rows; matters that `latest_evaluation_run_id` returns the standalone eval id while `latest_completed_pipeline_run` returns None).

3. **Structural-guard regex correctness** — Task 6. Regex must exclude the intentionally-non-target `dashboard.py:601` `last_pipeline_state` site (which uses `ORDER BY started_ts DESC` not `finished_ts DESC`). False-positive defense via `_strip_python_line_comments` AND must catch table-aliased queries (e.g., `pr.state = 'complete'` not just literal `pipeline_runs.state`).

4. **Watchlist DUAL-CONTRACT** — Task 3. Both helpers consumed in the same file for different concerns (classifications pipeline-bound; candidates with-fallback). Codex will check that the migration doesn't accidentally cross-contract.

5. **Cold-start true zero-yfinance** — Task 8. Mock yfinance MODULE-level AND assert no `mock_calls`. Vacuous variant that mocks `yf.download` only would still satisfy under existing weakness.

6. **Drift behavior-pin actually pins behavior** — Task 12. `threading.Event` coordination + `monkeypatch` of `swing.web.routes.trades.build_dashboard`. Skip fallback explicitly forbidden. Test must FAIL under any deviation from pinned behavior; vacuous test that always passes would not pin.

7. **Multi-path-ingestion lesson coverage** — Tasks 2-5. All 7 sites migrated; structural-guard at Task 6 enforces invariant durably. Vacuous coverage that misses any site means future inline-query reintroduction would not be caught.

8. **Helper extension additivity** — Task 1. `PipelineRunBinding` extended with `action_session_date` MUST NOT break existing callers. Codex will check backward-compat.

9. **research/parity rewrite** — Task 7. New `_CountingPriceFetcher` works against per-ticker parquet + meta JSON archive shape. Test exercises meta-staleness check, not just file existence.

10. **Cross-plan grep aliasing** per binding conventions. Disambiguate within THIS dispatch's chain; note in return report.

---

## §5 Done criteria

- All 12 plan tasks complete.
- Each task implementation commit follows the 4-tier convention with observable-verification grep output in commit body.
- Final fast-test count documented and reconciled against plan's projection (test baseline pinned at HEAD `8c7049b` was 1342 fast tests; plan projects ~1360 post-dispatch).
- Adversarial Codex review reaches `NO_NEW_CRITICAL_MAJOR` with verification round if final round had findings.
- All commits pushed to `origin/main`.
- Operator-runnable: `swing pipeline run` continues to work end-to-end; dashboard renders correctly in standalone-eval-only state (post-Task-2 surfaces correctly handle the fallback contract); Bug 7 durable closure verified via the structural-guard test.
- Return report posted per §6.

---

## §6 Return report format

Post as final message:

```
## Phase 4 Cleanup-Remainder — Executing-Plans Return Report

**Plan executed:** docs/superpowers/plans/2026-04-30-phase4-cleanup-remainder-plan.md (commit 6f548e1)
**Commit chain:** <first SHA> → <last SHA> on origin/main
**Total commits:** N (M task implementations + K Codex review-fixes + L cleanup)
**Codex rounds:** N rounds, terminating at NO_NEW_CRITICAL_MAJOR (with verification round if applicable)
**Fast-test count:** <count> at HEAD <SHA> (delta: +N from baseline 1342)

**Tasks completed:**
1. Task 1 — Helper foundation + id DESC exercise (commit <SHA>)
2. Task 2 — dashboard.py migrations (3 sites pipeline-bound) (commit <SHA>)
3. Task 3 — watchlist.py DUAL-CONTRACT migrations (commit <SHA>)
4. Task 4 — trades.py + cli.py migrations (commit <SHA>)
5. Task 5 — routes/pipeline.py migration (commit <SHA>)
6. Task 6 — Global structural-guard test (commit <SHA>)
7. Task 7 — research/parity rewrite + Step 8 todo follow-up (commit <SHA>)
8. Task 8 — Parallel cold-start true zero-yfinance test (commit <SHA>)
9. Task 9 — <tbody>-shape check (commit <SHA>)
10. Task 10 — Non-equal-priority sort-neutrality fixture (commit <SHA>)
11. Task 11 — Lift _seed_watchlist_and_candidate to conftest (commit <SHA>)
12. Task 12 — Multi-rebuild drift behavior-pin (commit <SHA>)

**Codex findings dispositioned:**
- R1: <count> Critical, <count> Major, <count> Minor — <breakdown>
- R2: ...
... (per round)

**Operator-action items:**
- (Optional) Run `swing pipeline run`; verify dashboard renders correctly.
- (Optional) Verify Bug 7 durable closure via the structural-guard test (one-shot pytest run); if a future contributor adds an inline `pipeline_runs WHERE state='complete'` outside the helpers, the test fails.

**Open questions for orchestrator triage:**
- <any items the implementer flagged as needing operator/orchestrator decision>

**Recommended next step:** operator-paced; Phase 5 (configuration page) is the next sequence item. Hypothesis_label web-form gap (Phase 4.5 standalone follow-up) is queued; operator decides whether to dispatch before Phase 5 or roll into it.
```

---

## §7 If you get stuck

- **If a plan task appears impossible to implement as written:** STOP, surface in return report. Do NOT silently re-design.
- **If a precedent file path doesn't resolve:** Use `Glob` / `Grep` to find the actual current path. Plan was authored at HEAD `8c7049b`; should be stable.
- **If Codex round count exceeds 5 without convergence:** STOP, surface in return report with the unresolved finding. Do NOT iterate indefinitely.
- **If the final Codex round produces findings that resolve:** run ONE verification round to confirm clean before terminating.
- **If discriminating-test sanity check reveals vacuousness:** STOP, restructure the test setup, then resume.
- **If Task 12 multi-rebuild drift reveals current behavior IS BROKEN:** surface in return report; operator decides whether to escalate to fix scope OR pin and defer (default: pin and defer per the plan's locked decision).
- **If a per-site contract classification (Q-B) appears wrong at execution time** (e.g., the behavioral test reveals the chosen contract produces wrong UX): STOP, surface; operator decides whether to re-classify the site OR proceed with the plan's classification.

---

## Appendix A: Plan-history awareness

The plan went through 5 substantive writing-plans Codex rounds + 1 verification round before this dispatch. **18 Major findings** caught + resolved at writing-plans phase. Notable categories:

- **R1+R2:** TDD red-phase missing across multiple migration tasks; helper-call-capture unsound; non-existent constant references.
- **R3:** Source-level lint not behavioral discriminator → forced TWO-test strategy (source-level + behavioral).
- **R4:** Wrong hooks; missing kwargs; non-discriminating CLI test.
- **R5:** Behaviorally-unpinned site; CLI test admittedly non-discriminating → DROPPED.
- **R6 verification:** clean.

Plan-history is durable in `docs/superpowers/plans/2026-04-30-phase4-cleanup-remainder-plan.md` commit chain. Implementer should NOT re-iterate on resolved findings; if a Codex round in THIS dispatch raises a finding that already has a plan-history fix, cite the plan + the fix commit, then proceed.

**4 brief-vs-reality discoveries** resolved in plan §"Brief vs reality discoveries":
1. Inline-query site count is 8 (not 5); 1 intentionally non-target.
2. Sort-neutrality test path is `tests/web/test_view_models/test_hyp_recs_sort_neutrality.py`.
3. `_seed_watchlist_and_candidate` exists in only ONE file.
4. Both helpers ALREADY have `id DESC` tiebreaker.

Brief asserted state without grep-verifying at draft time. Implementer correctly resolved each.

---

## Appendix B: Cross-references

- **Plan:** `docs/superpowers/plans/2026-04-30-phase4-cleanup-remainder-plan.md` (commit `6f548e1`).
- **Writing-plans brief:** `docs/phase4-cleanup-remainder-writing-plans-brief.md`.
- **Just-shipped Phase 3:** `docs/superpowers/plans/2026-04-29-ohlcv-archive-consolidation-plan.md` (commit `00aa6f4`); commit chain `0a5d2d9 → 3335d6c` on origin/main.
- **Bug 7 history:** orchestrator-context.md "Recent decisions" 2026-04-25 + Phase 2 hyp-recs trade-prep R1 M2 + Phase 2 hyp-recs success-path-fix plan + this dispatch (durable closure).
- **Bug-class durability vs scope-of-closure lesson** (orchestrator-context.md 2026-04-29) — directly applicable.
- **Helper-internal anchoring lesson** (orchestrator-context.md 2026-04-30) — relevant to Task 1.
- **Multi-path-ingestion lesson** (orchestrator-context.md 2026-04-29) — Tasks 2-5.
- **External-API empty-result transient lesson** (orchestrator-context.md 2026-04-30) — Task 8 context.
- **Hypothesis_label web-form gap follow-up** (phase3e-todo.md 2026-04-30) — Phase 4.5 standalone OR Phase 5 inline; operator decides post-Phase-4.
