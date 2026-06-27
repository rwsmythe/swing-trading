# Phase 12.5 #3 — Project Hygiene Maintenance Pass — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 12.5 #3 writing-plans implementer. No prior conversation context.

**Mission:** Produce an implementation plan for the **Phase 12.5 #3 project hygiene maintenance pass** — a 5-item bundle decomposing into a single executing-plans dispatch with per-task acceptance criteria + discriminating-test patterns + files-touched + test projection + commit message stems. **2 operator-locks** are pre-baked (item #5 disposition + dispatch shape). Writing-plans surfaces remaining implementation questions via Codex chain. **Skip brainstorm** — Phase 12.5 #3 is mechanical/text-edit work with minimal architectural surface; direct writing-plans dispatch (operator decision 2026-05-18 post-Phase-12.5-#2-merge).

**Brief:** `docs/phase12-5-bundle-3-project-hygiene-writing-plans-dispatch-brief.md` (this file).

**Sequencing:** Phase 12.5 #2 (Web Tier-2 discrepancy-resolution surface) SHIPPED 2026-05-18 at `0cecf28` (5 Codex rounds NO_NEW_CRITICAL_MAJOR; ZERO ACCEPT on Majors; +135 fast tests; 6-surface gate ALL PASS; Sub-bundle B T-B.7 PROMISE FULFILLED). Phase 12.5 #3 is the LAST Phase 12.5 dispatch before Phase 13 commission. Schema v19 UNCHANGED expected end-to-end (mechanical/text-edit + 1 small text amendment).

**Expected duration:** ~60-120 min plan-write + 2-4 adversarial Codex rounds. Scope is narrow: text-edit + collation + 1 small failing-test triage + Ruff cleanup. Plan line target: **~400-700 lines** (smaller than Phase 12.5 #1/#2 plans because architectural surface is minimal).

**Skill posture:**
- Invoke `copowers:writing-plans` skill against this brief.
- `copowers:writing-plans` wraps `superpowers:writing-plans` + adversarial Codex review.
- Output is a plan doc at `docs/superpowers/plans/<YYYY-MM-DD>-phase12-5-bundle-3-project-hygiene-plan.md`.

---

## §0 Read first

In this order:

1. **`docs/orchestrator-handoff-2026-05-18-post-phase12-5-2-merge.md`** — the orchestrator handoff brief. Especially §3.1 (5 Phase 12.5 #3 scope items operator-locked) + §3.2 (dispatch shape — Option B selected) + §3.3 (cap-drift specifics) + §3.4 (operator-pending items).
2. **`CLAUDE.md` status-line PARAGRAPH** — the giant single-paragraph status string at the top of CLAUDE.md (~60+ SHIPPED entries chronologically). **This is the primary artifact for item #1 archive-split.** Cap target: ~30 active entries (per `docs/orchestrator-context.md` §"Maintenance: retention discipline"). Writing-plans decides exact split boundary + commits to a target count.
3. **`docs/phase3e-todo.md`** — Cross-Phase Operational Backlog active file. Especially the Phase 12.5 #2 + #1 + finviz-fix SHIPPED entries at top. Item #1 also archive-splits this file (with `docs/phase3e-todo-archive.md` companion).
4. **`docs/phase3e-todo-archive.md`** — existing archive companion. **Read end-to-end to absorb the existing archive structure** (format precedent for new entries migrating in).
5. **`docs/orchestrator-context.md`** — Especially §"Currently in-flight work" (the nested narrative state with prior-state preservation pattern — growing 200-300 lines per major dispatch) + §"Lessons captured" (~52 entries; cap target ~30) + §"Maintenance: retention discipline" (cap targets + archive-split trigger doc).
6. **`docs/orchestrator-context-archive.md`** — existing archive companion. **Read to absorb existing structure** (format precedent).
7. **`docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md` §H.4** — **THIS IS THE PRIMARY TARGET for item #5 amendment.** The plan §H.4 wording claims tier-3-override would leave the banner present + count unchanged; shipped helper SQL queries `rd.resolved_by = 'auto_tier1_multi_leg'` directly, so `apply_tier3_override` flipping parent disc `resolved_by` to `'operator'` clears the banner immediately. Reasonable operator semantic; plan wording is imprecise.
8. **`docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md`** — Phase 12.5 #1 spec. Search for any §H.4 cross-references or banner-clears semantic that mirrors the plan's wording; amend matching sections in same commit.
9. **`docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-executing-plans-return-report.md` §5+§13** — Phase 12.5 #2 return report. Surfaces 3 NEW V2.1 §VII.F amendments (A1 plan §C.1 class-name drift + A2 plan §K projection +81 vs actual +135 + A3 plan §A T-2.2 acceptance 14-vs-15 fields drift).
10. **`tests/integration/test_phase8_pipeline_walkthrough.py`** — the 3 pre-existing failing tests for item #3 triage. Read the test bodies + recent failures to diagnose root cause. Failure list from baseline:
    - `test_phase8_pipeline_emits_snapshots_for_open_trades_only`
    - `test_phase8_pipeline_second_same_day_run_upserts`
    - `test_phase8_pipeline_run_id_is_pipeline_runs_id_not_evaluation_runs_id`
    Banked failure description across multiple SHIPPED entries: "archive returned None" — pre-existing on main HEAD `622c669` (Phase 7 ship); NOT caused by any Phase 8/9/10/11/12 work.
11. **Ruff 18 E501 enumeration** — run `ruff check swing/ --select E501` to list all 18 line-too-long violations. Item #4 either fixes each (line-wrap / refactor / `# noqa: E501` with rationale) OR documents as accepted-as-is with rationale.
12. **`docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-writing-plans-dispatch-brief.md`** — Phase 12.5 #1 writing-plans dispatch brief (242 lines; format precedent for THIS brief).
13. **`docs/superpowers/plans/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-plan.md`** — Phase 12.5 #2 plan (1082 lines; READ FOR PLAN-FORMAT REFERENCE for §A/§B/§C/§D/§F/§G/§H/§J structure). Mirror this format but shorter (Phase 12.5 #3 has fewer tasks).
14. **`CLAUDE.md` Gotchas section** — full read. Especially: cp1252 stdout encoder (ASCII-only any new text touched); `Co-Authored-By` footer suppression invariant.
15. **`docs/orchestrator-context.md` §"Lessons captured"** — cumulative forward-binding lessons. Plan author SHOULD enumerate which lessons might apply to Phase 12.5 #3 work.

---

## §1 Pre-locked operator decisions (DO NOT re-litigate)

### §1.1 Dispatch shape — SKIP BRAINSTORM (operator-locked 2026-05-18)

Per orchestrator-operator scope conversation 2026-05-18 post-Phase-12.5-#2-merge: Phase 12.5 #3 is low-architectural-risk maintenance. Direct writing-plans → executing-plans dispatch. Brainstorm phase OMITTED.

**Brainstorm-skip implications:**
- NO design spec at `docs/superpowers/specs/...phase12-5-3...`.
- NO `§15.A brainstorm-locks` to inherit.
- Plan author drafts §A task decomposition DIRECTLY from this brief + the 5 scope items.
- Architectural ambiguity surfaces during Codex chain (not pre-resolved by brainstorm).

### §1.2 Item #5 disposition — AMEND PLAN/SPEC TEXT ONLY (operator-locked 2026-05-18)

Phase 12.5 #1 plan §H.4 tier-3-override-no-clear semantic vs shipped helper SQL: **amend plan §H.4 wording + bank as V2.1 §VII.F amendment**. NO code fix to preserve banner mid-window. Shipped behavior (banner clears immediately when override flips parent disc `resolved_by` from `auto_tier1_multi_leg`) is the operator-accepted semantic; only the plan text needs correction.

**Plan author SHALL design** at item #5 task:
- Exact wording amendment for plan §H.4 (supersedes prior claim).
- Whether spec §8 or §10 carries a mirrored wording that needs amendment (verify via grep at plan-write time).
- Inline supersession note format (e.g., `> AMENDMENT (Phase 12.5 #3 at <SHA>): banner clears immediately when tier-3 override flips parent discrepancy resolved_by; prior claim that banner persists with count unchanged is incorrect per shipped helper SQL.`).
- V2.1 §VII.F amendment banking in the plan §J amendments list AND in Phase 12.5 #3 plan's own §J amendments list (forward-pointer).

**DO NOT design code fix path** — operator rejected this.

### §1.3 Schema v19 UNCHANGED LOCK (carries from Phase 12.5 #1 + #2)

Phase 12.5 #3 is mechanical/text-edit + Ruff cleanup + Phase 8 test triage. No schema work expected. Plan author SHALL preserve schema v19 LOCK via plan §F. If item #3 (Phase 8 triage) surfaces a need for schema work, **STOP + escalate** (Phase 9 Sub-bundle A precedent + Phase 12.5 #1 plan §F escalation rule).

### §1.4 ZERO Co-Authored-By footer drift (durable project invariant)

Cumulative streak ~163+ commits across Phase 11/12/post-Phase-12/Phase-12.5 chains. Plan author SHALL preserve via explicit citation in commit message stems. Executing-plans dispatch prompt SHALL include explicit suppression citation.

---

## §2 Plan decomposition target (single sub-bundle ship)

Phase 12.5 #3 is a SINGLE sub-bundle ship (no need for sub-decomposition; 5 items are coordinable in one executing-plans dispatch). Plan operationalizes this:

### §2.1 ~7-9 task projection (plan §A SHALL refine)

| Task | Scope | Files (illustrative; plan §A locks) | Tests projected |
|---|---|---|---|
| T-3.1 | CLAUDE.md status-line archive-split — move oldest N SHIPPED entries to archive companion | MODIFY `CLAUDE.md` (move ~30+ oldest SHIPPED entries to separate sentence-level/line-level chunks at archive) + NEW or MODIFY `docs/CLAUDE.md-archive.md` (or fold into `docs/orchestrator-context-archive.md` — plan author decides) | ~0 (text-only) |
| T-3.2 | `docs/phase3e-todo.md` archive-split — move oldest SHIPPED entries to `docs/phase3e-todo-archive.md` | MODIFY `docs/phase3e-todo.md` + APPEND `docs/phase3e-todo-archive.md` | ~0 |
| T-3.3 | `docs/orchestrator-context.md` archive-split — move oldest "Currently in-flight work" narratives + "Lessons captured" entries to `docs/orchestrator-context-archive.md` | MODIFY `docs/orchestrator-context.md` + APPEND `docs/orchestrator-context-archive.md` | ~0 |
| T-3.4 | V2.1 §VII.F amendment batch — collate ~30+ pending amendments from all prior dispatches' return reports + write single amendment doc OR inline supersession notes per source doc (plan author decides format) | NEW `docs/v2-1-section-7f-amendments-2026-05-18.md` (or similar) OR INLINE patches to each affected spec/plan doc | ~0 to ~3 (if any amendment changes test-relevant text) |
| T-3.5 | Phase 8 walkthrough failing-test triage — investigate the 3 pre-existing failures + decide fix-or-document | INVESTIGATE `tests/integration/test_phase8_pipeline_walkthrough.py` + potentially MODIFY `swing/pipeline/runner.py` or test file with fix OR ADD `@pytest.mark.skip(reason=...)` with rationale + `phase3e-todo.md` ticket | ~+0 (fix preserves count) or ~-3 if skipped + new test pin (~+1) |
| T-3.6 | Ruff 18 E501 cleanup — enumerate + fix each line-too-long violation (line-wrap / refactor / `# noqa: E501` with rationale) | MODIFY 18 line-numbered sites across `swing/` (plan §A.6 enumerates via `ruff check swing/ --select E501`) | ~0 to a few (if any line-wrap changes affect inline string literals) |
| T-3.7 | Phase 12.5 #1 plan §H.4 amendment — amend plan §H.4 wording + cross-check spec §8/§10 for mirrored wording | MODIFY `docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md` + possibly MODIFY `docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md` | ~0 |
| T-3.8 | Operator-witnessed gate plan — define ~3-5 surfaces (S1 inline pytest+ruff after all changes; S2 visual verification of archive-split boundaries; S3 V2.1 §VII.F amendment doc readability + cross-reference accuracy; S4 Ruff statistic check; S5 if any code change in T-3.5: Phase 8 walkthrough test status) | (gate plan only) | n/a |
| T-3.9 | Return report draft (mirror Phase 12.5 #2 return report shape) | NEW `docs/phase12-5-bundle-3-project-hygiene-executing-plans-return-report.md` | n/a |

**Total projection:** ~+0 to ~+5 fast tests (most tasks are text-edit zero-test-delta) + 0 slow E2E + ~+50-200 LOC across moves (large LINE COUNT but most is MOVED text, not new content).

**Plan §A SHALL refine** task boundaries + acceptance criteria + discriminating-test patterns (Codex chain may decompose differently or merge tasks).

### §2.2 Plan §B cross-bundle pins (none expected; single-bundle dispatch with no cross-bundle dependencies)

Phase 12.5 #3 consumes nothing from prior sub-bundles' code (consumer-side only on text artifacts). Plan §B documents "NO cross-bundle pins — text-edit + Ruff cleanup + Phase 8 test triage do NOT consume in-progress Phase code surfaces."

### §2.3 Plan §C+ SHALL enumerate

- §C task ordering (e.g., T-3.7 plan-amendment FIRST since it's small + de-risks downstream changes; OR T-3.4 amendment-batch FIRST since it collates outputs all other tasks reference; plan author decides).
- §D locked decisions roll-up (2 locks from §1 above + reference to ZERO-footer-drift + schema-v19-unchanged invariants).
- §E projected test delta (~+0 to ~+5 fast tests; ~+50-200 LOC moves).
- §F escalation rules (if Codex surfaces schema need → STOP + escalate; if T-3.5 Phase 8 triage reveals a deeper architectural issue requiring code-fix beyond a clean diagnose+fix → STOP + escalate per operator-pace-respect lesson).
- §G per-task acceptance criteria (mirror Phase 12.5 #2 plan §G structure; binding contracts).
- §H per-sub-bundle gate plan (3-5 surfaces; mirror prior gate budgets but shorter scope).
- §I cross-bundle invariants (Codex chain MAY surface; plan author enumerates).
- §J operator-witnessed gate plan (specific surfaces: S1 pytest + S2-S4 visual + S5 ruff).
- §K V2 candidates banked.
- §L V2.1 §VII.F amendments banked (this dispatch's own; chain Phase 12.5 #1 § J3 + Phase 12.5 #2 §J A1+A2+A3 + any new surfaced).

---

## §3 Adversarial review (Codex)

Invoked automatically by `copowers:writing-plans` after plan draft + before final commit.

**Expected chain shape:** 2-4 substantive Codex rounds (scope is smaller than Phase 12.5 #1/#2 plans; brainstorm-skip means plan absorbs more architectural-surface review but the architectural surface is minimal). ZERO ACCEPT-WITH-RATIONALE expected (matches Phase 12.5 #1 + #2 + finviz-fix arc precedent).

**Adversarial review watch items (Phase 12.5 #3 writing-plans-specific; pass as targeted prompts to `copowers:adversarial-critic`):**

1. **Archive-split boundary selection** — T-3.1/T-3.2/T-3.3 need DETERMINISTIC boundary selection (e.g., "move all entries dated before 2026-05-XX" OR "move all entries before <SHA>"). Plan §A specifies the exact boundary; Codex verifies it preserves ALL active references (search incoming xrefs to status-line entries; ensure none get orphaned in the archive split). Plan §F documents the pre-flight grep verification.
2. **`Co-Authored-By` footer suppression** — project invariant (~163+ commits cumulative). Plan §A specifies explicit citation in commit message stems for EVERY task.
3. **V2.1 §VII.F amendment batch format** — plan author chooses between (a) single amendment doc + cross-reference table OR (b) inline supersession notes per affected spec/plan doc OR (c) hybrid. Plan §A.4 locks the format; Codex verifies operator can later route any single amendment to the source-of-truth correction protocol (V2.1 §VII.F is the methodology-correction protocol per CLAUDE.md "Source-of-truth methodology references...").
4. **Phase 8 walkthrough triage scope discipline** — T-3.5 MUST NOT expand into a broader Phase 8 refactor. If diagnosis reveals a SIMPLE fix, ship it; if it reveals a DEEPER architectural issue, document the diagnosis + bank as standalone-dispatch V2 candidate + accept the 3 tests as `@pytest.mark.skip(reason="...")` with rationale. Plan §F documents the scope-cap.
5. **Ruff 18 E501 cleanup per-violation rationale** — for each fixed violation, plan §A.6 specifies WHETHER it's line-wrapped vs refactored vs `# noqa: E501`'d (with rationale). Codex verifies no `# noqa` is added without binding rationale per violation.
6. **Plan §H.4 amendment wording accuracy** — T-3.7 amendment text MUST accurately describe the shipped helper SQL behavior (`rd.resolved_by = 'auto_tier1_multi_leg'` direct query) AND the operator-accepted semantic (banner clears immediately on override). Codex verifies the amendment text matches shipped code.
7. **Cross-document drift detection** — if T-3.4 amendment batch surfaces an amendment that ITSELF surfaces a further drift (e.g., A1 class-name drift might require renaming a class in a non-touched spec section), plan §F documents the discovery-scope-cap (drift cascade must be in-scope of T-3.4 OR explicitly out-of-scope).
8. **Archive companion file format consistency** — T-3.1/T-3.2/T-3.3 MUST preserve the existing archive companion file structure (read `docs/phase3e-todo-archive.md` + `docs/orchestrator-context-archive.md` to absorb format). Plan §F documents the format-precedent verification.
9. **Test-count baseline accuracy** — plan §E projects test-delta. Baseline at handoff is 4851 fast pass (handoff said 4847; actual is 4851 — slight drift). Plan author SHALL verify against fresh `pytest -m "not slow"` baseline at plan-write time, not handoff-doc claim.
10. **Operator-witnessed gate surface count** — Phase 12.5 #3 gate surfaces are smaller scope than Phase 12.5 #1/#2 (which had 6+ surfaces). Plan §H targets 3-5 surfaces; Codex verifies coverage per task.
11. **NO Phase 12.5 #3 scope creep into Phase 13** — Phase 13 scope LOCKED at `docs/phase13-scope-brainstorm.md` §0.5; Phase 12.5 #3 maintenance pass does NOT in-scope Phase 13 work. Plan §F documents the scope-boundary.

---

## §4 Deliverable shape

**Plan document at `docs/superpowers/plans/<YYYY-MM-DD>-phase12-5-bundle-3-project-hygiene-plan.md`** (mirror Phase 12.5 #2 plan format; shorter):

- §0 Plan overview + cross-references to brief
- §1 Operator-locked decisions roll-up (2 locks from §1 above; verbatim)
- §A Task list (T-3.1 .. T-3.9; per-task scope + acceptance criteria + discriminating tests + files-touched + test projection + commit message stem)
- §B Cross-bundle pins (none expected; document the negative)
- §C Task ordering rationale
- §D Locked decisions roll-up
- §E Test projection (~+0 to ~+5 fast tests; ~+50-200 LOC moves)
- §F Pre-flight grep verifications + escalation rules + scope-cap notes
- §G Per-task acceptance criteria narrative (binding contracts)
- §H Per-sub-bundle gate plan (3-5 surfaces; specific acceptance criteria)
- §I Cross-bundle invariants (ZERO Co-Authored-By footer drift; schema v19 unchanged; Ruff post-cleanup target)
- §J Operator-witnessed gate plan
- §K If you get stuck (mirror prior briefs §7 patterns)
- §L V2 candidates banked (any deferred from this dispatch's investigation)
- §M V2.1 §VII.F amendments banked (Phase 12.5 #1's plan §H.4 amendment + Phase 12.5 #2's A1/A2/A3 + any new surfaced)

**Target line count: ~400-700 lines.**

**Commit message stem:** `docs(phase12-5-3-project-hygiene-plan): single-sub-bundle decomposition — <N> Codex rounds → NO_NEW_CRITICAL_MAJOR convergent (R1 ... → R<N> ...)`.

---

## §5 OUT OF SCOPE (do not design)

- **New features** — Phase 12.5 #3 is maintenance-pass-only.
- **Schema additions** — schema v19 LOCK preserved.
- **Code fix for item #5** — operator-locked at amend-text-only.
- **Phase 8 refactor beyond a clean fix-or-document for the 3 failing tests** — if diagnosis reveals deeper architectural issue, accept-with-rationale + bank as V2 standalone-dispatch.
- **Phase 13 work** — Phase 13 scope LOCKED at `docs/phase13-scope-brainstorm.md` §0.5; out of Phase 12.5 #3 scope.
- **Operator-pending items** (cleanup-script `-DeregisterFirst` pass + 4 pending-ambiguity discrep dispositioning + Schwab refresh-token re-auth) — operator-paced; NOT orchestrator-blocking; NOT in writing-plans scope.
- **Ruff cleanup of OTHER violation classes** — only the 18 E501 are operator-tagged for cleanup; non-E501 violations stay banked.
- **Lessons captured promotion to active section** — beyond the archive-split of OLDEST entries, plan does NOT promote new lessons to "Lessons captured" active section (lessons banked at return reports + phase3e-todo entries stay there).
- **CLAUDE.md gotchas section archive-split** — separate concern; CLAUDE.md gotchas grow with project but archive trigger is per-section-cap (this dispatch may visit but not in-scope unless plan author proposes + Codex approves).
- **2 CLAUDE.md gotcha promotion candidates from Sub-bundle 2 ship** (read-time re-redactor discipline + tokens_db_path masking pattern) — banked in CLAUDE.md status-line; if plan author wants to fold into item #1 archive-split work, OK; otherwise stays banked. Plan §F documents the disposition.

---

## §6 If you get stuck

- If Codex surfaces a NEW schema need (Phase 12.5 #3 should NOT have any), **STOP + escalate**.
- If Codex pushes back on the brainstorm-skip + direct writing-plans posture, HOLD THE LINE — operator-locked 2026-05-18.
- If Codex pushes back on item #5 amend-text-only disposition, HOLD THE LINE — operator-locked 2026-05-18.
- If T-3.5 Phase 8 triage reveals an architectural issue beyond a clean fix-or-document, **STOP + escalate**.
- If T-3.4 V2.1 §VII.F amendment collation reveals an amendment that contradicts operator decision OR shipped-spec invariant, **STOP + escalate**.
- If T-3.1/T-3.2/T-3.3 archive-split boundary selection has no clean default, propose 2-3 candidates with tradeoffs + ask operator at writing-plans-output review.
- If T-3.6 Ruff cleanup uncovers code paths where line-wrap would change behavior (unlikely; E501 is whitespace-only typically), document the violation + propose `# noqa: E501` with rationale.
- If plan-author surfaces a need for V2.1 §VII.F amendment beyond the 4 items already enumerated (Phase 12.5 #1 §H.4 + Phase 12.5 #2 A1/A2/A3), bank in plan §M + return report §6.
- DO NOT propose new architectural surfaces within Phase 12.5 #3 plan scope.
- DO NOT add `Co-Authored-By` footer to any commit message (per project invariant; ~163+ commits cumulative; explicit citation in commit message stem).
- **Pre-Codex orchestrator-side review (NEW C.C lesson #6 — BINDING)**: before invoking `copowers:adversarial-critic`, dispatch a focused reviewer subagent with §1 + §2 binding contracts + the 5 scope items as anchors; ask for deviation list ≤300 words. Cheap; absorbed LOCK divergences pre-Codex on Phase 12 C.C + C.D + Sub-bundle 1 + Phase 12.5 #1 brainstorm + Phase 12.5 #2 brainstorm + writing-plans + executing-plans (validated 7x cumulatively).

---

## §7 Return report shape

After Codex chain converges + before final commit, draft a return report at `docs/phase12-5-bundle-3-project-hygiene-writing-plans-return-report.md`:

1. Final HEAD on branch + commit count breakdown.
2. Codex round chain (R1-RN summary table + convergent shape; finding-count taper).
3. Plan line count.
4. 2 operator-locks verbatim verification.
5. Per-task acceptance criteria summary.
6. Codex Major findings ACCEPTED with rationale (if any). Expectation: ZERO ACCEPT-WITH-RATIONALE (matches Phase 12.5 #1 + #2 arc).
7. V2 candidates banked (any surfaced in plan or Codex chain).
8. V2.1 §VII.F amendments banked (Phase 12.5 #1 §H.4 + Phase 12.5 #2 A1/A2/A3 + any new).
9. Forward-binding lessons for executing-plans dispatch.
10. CLAUDE.md status-line refresh draft text (very short — Phase 12.5 #3 maintenance pass).
11. Schema impact verdict (v19 UNCHANGED expected).
12. Phase 8 walkthrough triage finding summary (item #3 disposition).
13. Worktree teardown status.

---

## §8 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES — branch `phase12-5-bundle-3-project-hygiene-writing-plans` (matches cleanup-script regex `phase\d+[-_]`). Worktree directory `.worktrees/phase12-5-bundle-3-project-hygiene-writing-plans/`.
- **Model:** defer to harness default.
- **Expected duration:** ~60-120 min plan-write + ~30-60 min Codex chain. Total ~1.5-3 hours operator-paced (per `feedback_time_estimates_overstated.md` calibration; divide naive estimate by 3-5x).

---

*End of brief. Phase 12.5 #3 writing-plans dispatch — 2 operator-locks pre-baked (skip-brainstorm + amend-text-only); 5 scope items decomposed into ~7-9 tasks; single-sub-bundle ship; ~400-700 line plan target; 2-4 Codex round expectation; ZERO ACCEPT-WITH-RATIONALE expected. OUTPUT: plan doc that executing-plans phase decomposes into the project hygiene maintenance ship.*
