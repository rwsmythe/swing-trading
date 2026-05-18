# Phase 12.5 #3 — Project Hygiene Maintenance Pass — Executing-plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Phase 12.5 #3 of the Phase 12.5 arc via `copowers:executing-plans`. Plan is `docs/superpowers/plans/2026-05-18-phase12-5-bundle-3-project-hygiene-plan.md` (1101 lines). All per-task acceptance criteria + commit shapes + per-bucket dispositions are in the plan; this dispatch brief is a worktree-config + scope wrapper, NOT a duplicate spec. Phase 12.5 #3 is a **maintenance pass with minimal architectural surface** — 5 scope items (CLAUDE.md+orchestrator-context+phase3e-todo archive-split + V2.1 §VII.F amendment batch + Phase 8 walkthrough failing-test triage + Ruff 18 E501 cleanup + Phase 12.5 #1 plan §H.4 amendment).

**Expected duration:** ~3-5 hr implementation + ~1-2 hr Codex chain + 4-surface operator-witnessed gate. Total **~1-2 days operator-paced** (calibrated 3-5x per `feedback_time_estimates_overstated.md`; scope is smaller than Phase 12.5 #1/#2 because most tasks are text-edit + Ruff cleanup). Schema v19 UNCHANGED LOCK end-to-end.

**Skill posture:**
- Invoke `copowers:executing-plans` against the plan path (`PLAN_PATH=docs/superpowers/plans/2026-05-18-phase12-5-bundle-3-project-hygiene-plan.md`).
- The skill wraps `superpowers:subagent-driven-development` + adversarial Codex review.
- Adversarial review runs after all 7 tasks land. Expected **2-4 Codex rounds** (smaller than Phase 12.5 #1/#2's 4-5 rounds because architectural surface is minimal; writing-plans already absorbed 6 rounds with ZERO ACCEPT-WITH-RATIONALE on Majors). ZERO ACCEPT-WITH-RATIONALE on Majors expected (matches Phase 12.5 arc clean-record streak).

---

## §0 Inputs

### §0.1 Plan

- **PLAN_PATH:** `docs/superpowers/plans/2026-05-18-phase12-5-bundle-3-project-hygiene-plan.md` (1101 lines; 6 Codex rounds; ZERO ACCEPT-WITH-RATIONALE on Majors; ZERO Critical findings; LOCKED at `fb27be2`; merged to main).
- **Plan §A** task decomposition: 7 tasks T-3.1..T-3.7. Self-contained per-task spec with acceptance criteria + commit message stems.
- **Plan §C** task-ordering rationale (T-3.7 FIRST since smallest + de-risks downstream; archive-splits LAST since they alter narrative-memory artifacts).
- **Plan §D** locked decisions roll-up (2 operator-locks: skip-brainstorm + amend-text-only for item #5).
- **Plan §E** projected test delta (~+0 to ~+5 fast tests; ~+50-200 LOC text moves).
- **Plan §F** pre-flight grep verifications + escalation rules + scope-cap notes (Phase 8 triage HARD STOP at Bucket C; schema v19 STOP-and-escalate).
- **Plan §G** per-task acceptance-criteria narrative (binding contracts).
- **Plan §H** 4-surface operator-witnessed gate plan.
- **Plan §I** cross-bundle invariants (none expected; document the negative; ZERO Co-Authored-By footer + schema v19 + Ruff post-cleanup target).
- **Plan §J** operator-witnessed gate plan.
- **Plan §K** V2 candidates banked.
- **Plan §L** V2.1 §VII.F amendments banked (Phase 12.5 #1 §H.4 + Phase 12.5 #2 A1/A2/A3 + any new surfaced).
- **Plan §M** forward-binding lessons L-X1..L-X5 for executing-plans inheritance.

### §0.2 Spec

- **NONE.** Per operator-lock §1.1, Phase 12.5 #3 SKIPS brainstorm. Brief + plan are the design contracts.

### §0.3 Writing-plans return report

- **RETURN_REPORT_PATH:** `docs/phase12-5-bundle-3-project-hygiene-writing-plans-return-report.md` (205 lines; committed at `63f1943`).
- **Read for §2** Codex chain (6 rounds; monotonic Major taper 4→3→3→1→1→0) + **§7** V2 candidates + **§8** V2.1 §VII.F amendments banked + **§9** 4 NEW forward-binding lessons L-W1..L-W4 (Bucket-classification math; pre-write gate pattern; brief-baseline-vs-fresh-baseline drift; ASCII-only invariant scope discipline) + **§12** Phase 8 walkthrough triage finding summary (plan-author expectation: most likely Bucket A trivial fixture drift).

### §0.4 Project state at dispatch time

- **HEAD on `main`:** `10d4c76` (post-merge housekeeping commit; merge of writing-plans worktree at `fb27be2` + housekeeping). Resolve via `git rev-parse main` at worktree-creation time.
- **Test count:** **4847 fast passing on main** + 3 pre-existing failures (`tests/integration/test_phase8_pipeline_walkthrough.py` — the T-3.5 targets) + 5 skipped (4 pre-existing + 1 Phase 12.5 #2 cross-bundle pin). Verified at brief drafting time.
- **Ruff baseline:** **18 E501 errors** unchanged across Phase 11 + Phase 12 + post-Phase-12 + Phase 12.5 #1 + #2 chains. T-3.6 cleans these to ZERO. NO new violations introduced by any task.
- **Schema version:** **v19** (LOCKED since Phase 12 Sub-sub-bundle C.A; F1 LOCK preserved through plan §F). **Phase 12.5 #3 MAY NOT widen schema** (plan §F.2 escalation rule).
- **Production state:** 4-6 pending-ambiguity discrepancies (54-57+; operator continues dispositioning per C.D-cleanup precedent). Phase 12.5 #3 does NOT touch production data.
- **Worktree husks:** 7+ pending operator's cleanup-script pass (3 Phase 12.5 #1 + 1 finviz-fix + 3 Phase 12.5 #2); NOT blocking executing-plans dispatch. Phase 12.5 #3 adds 1 new (this executing-plans worktree).

### §0.5 Phase 12.5 #3 scope (7 tasks per plan §A; dispatch order LOCKED)

| Task | Title | Files (illustrative; plan §A locks) |
|---|---|---|
| **T-3.7** | Amend Phase 12.5 #1 plan §H.4 + spec §9.3 S4 + spec §5 line 104 — banner clears immediately on tier-3 override per shipped helper SQL semantic (NOT "stays present") | MODIFY `docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md:1071` + `docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md:104,940`; index in T-3.4 master inventory |
| **T-3.5** | Phase 8 walkthrough failing-test triage — diagnose root cause + classify as Bucket A (trivial fixture fix) / Bucket B (small runner-side adjustment) / **Bucket C (HARD STOP — requires operator approval BEFORE skip-pattern + standalone-dispatch entry)** | INVESTIGATE `tests/integration/test_phase8_pipeline_walkthrough.py` + dependent code; bucket-dependent file scope |
| **T-3.6** | Ruff 18 E501 cleanup — per-violation fix using `Edit` (not `Write`) per L-X3 LOCK; ASCII preservation on runtime-path string literals per L-W4 LOCK; ZERO `# noqa` without binding rationale | MODIFY 18 file:line sites across `swing/` per plan §A.6 step 2 18-row roster |
| **T-3.4** | V2.1 §VII.F amendment inventory at NEW `docs/v2-1-section-7f-amendments-2026-05-18.md` with canonical 33-file return-report grouped roster + grep supplement; ZERO modifications to spec/plan docs in T-3.4 diff (those happen at T-3.7) | NEW `docs/v2-1-section-7f-amendments-2026-05-18.md` |
| **T-3.1** | CLAUDE.md status-line archive-split — move oldest SHIPPED entries before 2026-05-12-inclusive to NEW companion file; PROCEED_WITH_WRITE count gate at 15-30 active-retain band; archive pointer at line 4-5 of CLAUDE.md | MODIFY `CLAUDE.md` + NEW `docs/CLAUDE.md-archive.md` (or fold into existing archive companion per plan §A.1 final decision) |
| **T-3.2** | `docs/phase3e-todo.md` archive-split — SHIPPED-only predicate + pre-write roster gate; archive ordering audit; pointer at TOP of active doc | MODIFY `docs/phase3e-todo.md` + APPEND `docs/phase3e-todo-archive.md` |
| **T-3.3** | `docs/orchestrator-context.md` archive-split — pre-flight roster + **operator review BEFORE script-write**; pointers at TOPs of cap-drifting sections ("Currently in-flight work" + "Lessons captured") | MODIFY `docs/orchestrator-context.md` + APPEND `docs/orchestrator-context-archive.md` |

**Dispatch order:** T-3.7 → T-3.5 → T-3.6 → T-3.4 → T-3.1 → T-3.2 → T-3.3. **CRITICAL ORDERING per plan §C**: T-3.7 ships FIRST since smallest + de-risks downstream. Archive-splits LAST since they alter narrative-memory artifacts (post-completion verification benefits from stable narrative).

**Cross-bundle dependencies:** NONE. Phase 12.5 #3 is consumer-side text edits only; no other in-progress code consumes these artifacts during execution.

**Module boundaries (BINDING — preserve discipline per plan §C.3):**
- T-3.7 touches DOCS ONLY (Phase 12.5 #1 plan + spec). NO code touched.
- T-3.5 file scope DEPENDS ON BUCKET classification:
  - **Bucket A**: monkeypatch wiring in `tests/integration/test_phase8_pipeline_walkthrough.py` OR test fixture. ~1-3 LOC fix.
  - **Bucket B**: small runner-side adjustment in `swing/pipeline/` or similar. ~5-15 LOC fix.
  - **Bucket C**: `@pytest.mark.skip(reason=...)` decorators on 3 tests + standalone-dispatch entry in `docs/phase3e-todo.md`. NO production code touched. **REQUIRES OPERATOR APPROVAL BEFORE Step 3b artifact change** (HARD STOP gate per plan §A T-3.5 Step 3 + L-X2 LOCK).
- T-3.6 touches Ruff E501 sites in `swing/` ONLY (per 18-row roster). NO test files.
- T-3.4 creates ONE new doc file. NO other modifications.
- T-3.1 + T-3.2 + T-3.3 each touch ONE active doc + ONE archive companion. Pre-write `PROCEED_WITH_WRITE = False` gate per L-W2 LOCK.

---

## §1 Critical project conventions — DO NOT regress

1. **NO `Co-Authored-By: Claude` footer** on ANY commit. Cumulative streak ~165+ commits ZERO drift across Phase 11/12/post-Phase-12/Phase-12.5 chains. Plan §I F2 + every commit stem in §A cites suppression. **Explicit suppression citation in this dispatch is the discipline.**
2. **Use `python -m swing.cli`** at worktree-side gates (NOT bare `swing` which routes to editable-install path; per `feedback_worktree_cli_invocation.md` durable).
3. **ASCII-only on runtime CLI paths** (`print()` / `click.echo()` / `sys.stdout.write()`) — Windows cp1252 stdout encoder gotcha. Documentation freely uses em-dashes + § glyphs per plan §A T-3.7 + L-W4 LOCK. T-3.6 ASCII preservation contract: when line-wrapping E501 violations, do NOT introduce non-ASCII to runtime-path code.
4. **Schema v19 UNCHANGED LOCK** — F1 + F5 + T-3.5 STOP-and-escalate rule. If any task surfaces a schema need, STOP + escalate to operator (Phase 9 Sub-bundle A + Phase 12.5 #1 plan §F escalation precedent).
5. **Pre-Codex orchestrator-side review** before invoking `copowers:adversarial-critic` — dispatch a focused reviewer subagent with plan §1 (operator-locks) + §A (per-task) + §F (escalation rules) as anchors; ask for deviation list ≤300 words. C.C lesson #6 BINDING (validated 7x cumulatively).

---

## §2 Worktree setup

From project root `c:/Users/rwsmy/swing-trading`:

```bash
git fetch origin
git rev-parse main                                          # expect 10d4c76 (housekeeping HEAD)
git worktree add .worktrees/phase12-5-bundle-3-project-hygiene-executing-plans \
    -b phase12-5-bundle-3-project-hygiene-executing-plans main
cd .worktrees/phase12-5-bundle-3-project-hygiene-executing-plans
python -m pytest -m "not slow" -q -n auto 2>&1 | tail -5    # expect 4847 fast pass + 3 pre-existing failures + 5 skipped
ruff check swing/ --select E501 --statistics | tail -3      # expect 18 E501
```

Branch matches cleanup-script regex `phase\d+[-_]` for operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass post-merge.

---

## §3 Operator-pairing points (runtime; NOT pre-merge)

Two runtime operator-pairing points are pre-encoded in the plan:

### §3.1 T-3.5 Bucket C HARD STOP (plan §A T-3.5 Step 3)

If diagnosis classifies the 3 failing tests as **Bucket C** (skip-pattern with rationale; NOT a clean code fix), implementer **STOPS** before writing the `@pytest.mark.skip` decorators + phase3e-todo standalone-dispatch entry. Operator approves the skip-pattern semantic + rationale text BEFORE Step 3b artifact change. Plan-author expectation per return report §12: most likely **Bucket A** (trivial fixture drift; `archive returned None` suggests `read_or_fetch_archive` monkeypatch path drift). Bucket C is unlikely-but-possible escalation path.

### §3.2 T-3.3 pre-flight roster review (plan §A T-3.3 Step 1)

Implementer enumerates the candidate "Currently in-flight work" narrative entries + "Lessons captured" entries proposed for archive migration + presents the roster to operator for review **BEFORE** executing the script-write. Defense against archiving load-bearing entries (e.g., entries cross-referenced from elsewhere in the project). Plan-author pre-flight `PROCEED_WITH_WRITE = False` gate per L-W2 LOCK.

These are RUNTIME interactions, NOT pre-merge decisions. Implementer pauses + asks operator at the precise step.

---

## §4 Operator-witnessed gate (4 surfaces per plan §H)

Run AFTER all 7 tasks land + Codex chain converges + adversarial-critic verdict is NO_NEW_CRITICAL_MAJOR:

- **S1** inline pytest+ruff+per-task post-conditions: `python -m pytest -m "not slow" -q -n auto` returns expected count (Bucket A/B: 4847 pass / 5 skipped / 0 fail; Bucket C: 4847 pass / 8 skipped / 0 fail per plan §A T-3.5 acceptance) + `ruff check swing/ --select E501 --statistics` returns 0 (T-3.6 acceptance LOCK).
- **S2** visual verification of archive-split boundaries: operator scrolls active CLAUDE.md + phase3e-todo + orchestrator-context + verifies retained entries are coherent + archive pointers resolve.
- **S3** V2.1 §VII.F amendment doc readability + cross-reference accuracy: operator opens `docs/v2-1-section-7f-amendments-2026-05-18.md` + spot-checks 3-5 amendment rows resolve correctly to source documents.
- **S4** Phase 12.5 #1 plan §H.4 + spec §9.3 S4 + spec §5 line-104 amendment verification: grep for `AMENDMENT (Phase 12.5 #3` returns 3 hits across 2 files; amendment text accurately describes shipped helper SQL semantic.

Operator-paced; ONE COMMAND AT A TIME on archive-split tasks since they alter narrative-memory artifacts.

---

## §5 If you get stuck

- **Schema need surfaces**: STOP + escalate (plan §F.2 escalation rule).
- **Phase 8 triage reveals deeper architectural issue beyond Bucket C scope**: STOP + escalate (plan §F.3 scope-cap).
- **V2.1 §VII.F amendment collation reveals an amendment that contradicts operator decision OR shipped-spec invariant**: STOP + escalate (plan §F.4).
- **Codex pushes back on operator-locks at plan §1 (skip-brainstorm; amend-text-only)**: HOLD THE LINE — operator-locked 2026-05-18 (per writing-plans Codex chain precedent — R1-R6 did not push back).
- **Codex pushes back on Ruff cleanup approach**: review per-violation rationale in plan §A T-3.6 + escalate if conflict.
- **Archive-split boundary selection has no clean default**: propose 2-3 candidates with tradeoffs + ask operator at task-execution time (plan §F.5).
- **Ruff cleanup uncovers code paths where line-wrap would change behavior**: document the violation + propose `# noqa: E501` with rationale (plan §A T-3.6 fallback path).
- **DO NOT propose new architectural surfaces** within Phase 12.5 #3 scope.
- **DO NOT add `Co-Authored-By` footer** to any commit message (project invariant; ~165+ commits cumulative).
- **Pre-Codex orchestrator-side review (NEW C.C lesson #6 — BINDING)**: before invoking `copowers:adversarial-critic`, dispatch focused reviewer subagent with plan §1 + §A + §F as anchors; ask deviation list ≤300 words.

---

## §6 Return report shape

After Codex chain converges + before final commit, draft a return report at `docs/phase12-5-bundle-3-project-hygiene-executing-plans-return-report.md` mirroring Phase 12.5 #2 executing-plans return report format:

1. Final HEAD on branch + commit count breakdown.
2. Codex round chain (R1-RN summary table + convergent shape; finding-count taper).
3. Per-task delivery summary (T-3.1..T-3.7).
4. Codex Major findings ACCEPTED with rationale (if any). Expectation: ZERO ACCEPT-WITH-RATIONALE.
5. V2 candidates banked (any surfaced).
6. V2.1 §VII.F amendments banked (Phase 12.5 #3 own + any new surfaced during executing-plans Codex chain).
7. **Phase 8 walkthrough triage finding**: bucket disposition + root cause analysis + operator-approval reference if Bucket C lands.
8. **T-3.4 amendment inventory location + row count + Phase 12.5 #1+#2 cross-reference verification**.
9. Forward-binding lessons for future maintenance dispatches.
10. CLAUDE.md status-line refresh draft text (orchestrator paste-in).
11. Schema impact verdict (v19 UNCHANGED expected).
12. Test-count delta + Ruff post-cleanup count.
13. Worktree teardown status.

---

## §7 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES — branch `phase12-5-bundle-3-project-hygiene-executing-plans` (matches cleanup-script regex `phase\d+[-_]`). Worktree directory `.worktrees/phase12-5-bundle-3-project-hygiene-executing-plans/`.
- **Model:** defer to harness default.
- **Expected duration:** ~3-5 hr implementation + ~1-2 hr Codex chain. Total ~1-2 days operator-paced (per `feedback_time_estimates_overstated.md` calibration; smaller scope than Phase 12.5 #1/#2).

---

*End of brief. Phase 12.5 #3 executing-plans dispatch — 7 tasks single-sub-bundle ship; 2 operator-locks pre-baked (skip-brainstorm + amend-text-only); 2 runtime operator-pairing points (T-3.5 Bucket C HARD STOP + T-3.3 pre-flight roster review); 4-surface gate; 2-4 Codex round expectation; ZERO ACCEPT-WITH-RATIONALE expected. OUTPUT: project-hygiene maintenance pass shipped + 18 ruff cleared + Phase 8 triage closed + V2.1 §VII.F amendment inventory + archive-splits across CLAUDE.md + phase3e-todo + orchestrator-context. CLOSES Phase 12.5 arc.*
