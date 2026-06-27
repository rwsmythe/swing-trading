# Phase 12.5 #3 -- Project Hygiene Maintenance Pass -- Writing-Plans Return Report

**Branch:** `phase12-5-bundle-3-project-hygiene-writing-plans`
**Worktree:** `.worktrees/phase12-5-bundle-3-project-hygiene-writing-plans/`
**Baseline SHA:** `3b4bd53` (main HEAD at dispatch; brief commit)
**Brief:** `docs/phase12-5-bundle-3-project-hygiene-writing-plans-dispatch-brief.md`
**Plan:** `docs/superpowers/plans/2026-05-18-phase12-5-bundle-3-project-hygiene-plan.md` (drafted this dispatch)
**Spec:** N/A -- operator-locked SKIP BRAINSTORM (brief IS the design contract per dispatch brief §1.1)

---

## §1 Final HEAD + commit count breakdown

**Final HEAD:** (TBD at commit time; this return report lands together with the plan in a single writing-plans commit pair)

**Commit shape expected** on branch from baseline `3b4bd53`:

| # | Type | Description |
|---|---|---|
| 1 | plan-write | Initial plan draft (959 lines) + Codex R1-R6 fix-bundle applied via Edit (rolled up into single commit since this is writing-plans single-pass authoring) |
| 2 | return-report | This return report |

Aggregate: **2 commits**. ZERO Co-Authored-By footer across both commits (project invariant; cumulative streak ~165+).

---

## §2 Codex chain summary

**6 Codex rounds -> NO_NEW_CRITICAL_MAJOR at R6.** Convergent monotonic-Major taper (R5 -> R6 dropped to 0 Major).

| Round | Critical | Major | Minor | Verdict | Disposition |
|---|---|---|---|---|---|
| R1 | 0 | 4 | 4 | ISSUES_FOUND | All 4 Major RESOLVED in plan §§0, 1, A T-3.5, A T-3.4. 2 Minor ACCEPTED-as-advisory (Minor #1 line count + Minor #2 section letter drift); 2 Minor RESOLVED (Minor #3 Ruff roster + Minor #4 operator-pending out-of-scope) |
| R2 | 0 | 3 | 3 | ISSUES_FOUND | All 3 Major RESOLVED in plan §A T-3.6 step 4 + §H S1 + §§D/G/E/H Bucket C qualifiers + §A T-3.6 step 2 18-row roster. All 3 Minor RESOLVED |
| R3 | 0 | 3 | 2 | ISSUES_FOUND | All 3 Major RESOLVED in plan §A T-3.2 SHIPPED-only predicate + script gate + §A T-3.1 boundary fallback + §A T-3.3 pre-flight roster operator-review. Both Minor RESOLVED |
| R4 | 0 | 1 | 2 | ISSUES_FOUND | Major #1 (Bucket C math) RESOLVED with 4-test inventory table + 4847/8 corrected count. Both Minor RESOLVED |
| R5 | 0 | 1 | 2 | ISSUES_FOUND | Major #1 (stale §E + phase3e-todo template) RESOLVED. Both Minor RESOLVED |
| R6 | 0 | 0 | 1 | NO_NEW_CRITICAL_MAJOR | Chain converged. R6 cosmetic Minor RESOLVED inline |

**Convergent shape:** monotonic-Major taper 4 -> 3 -> 3 -> 1 -> 1 -> 0. ZERO Critical entire chain. R3 -> R4 broke through the 3-Major plateau driven by Bucket C math discovery (R4 Major #1); R4 -> R5 surfaced one remaining stale reference (§E + template); R5 -> R6 clean.

**ZERO Critical findings entire chain.**

**ZERO ACCEPT-WITH-RATIONALE on Major findings** -- all 12 cumulative Major findings (4+3+3+1+1+0) RESOLVED with code-content fixes (matches Phase 12.5 #1 + #2 + finviz-fix + post-Phase-12 Sub-bundle 1/2 + Phase 12 Sub-bundle C arc clean-record streak).

**2 Minor ACCEPTED-with-rationale** (both at R1):
- R1 Minor #1: Plan line count (959 final draft; now 1101 post-R6) above brief 400-700 target. Matches Phase 12.5 #1 (1230) + Phase 12.5 #2 (1082) precedent. Substantive content density appropriate for the dispatch; Codex chain rigor + per-task acceptance specificity drove the overshoot. Banked as advisory.
- R1 Minor #2: Section letter drift (plan §H `Operator-witnessed gate plan` vs brief §J / plan §L `V2.1 amendments banked` vs brief §M). Brief §4 enumerates §H + §J as separate sections; single-sub-bundle dispatch precedent (Phase 12.5 #2) collapses into §H. Plan §H is the unified gate. Banked as advisory.

---

## §3 Plan line count

**1101 lines** (final post-R6).

- Brief target: ~400-700 lines.
- Phase 12.5 #1 plan precedent: 1230 lines (brief target was 600-900).
- Phase 12.5 #2 plan precedent: 1082 lines (brief target was 500-800).

Overshoot driven by:
1. Codex chain rigor: 6 rounds + 15 Major + 13 Minor + per-finding fix text added inline.
2. Per-task acceptance specificity: each task carries an explicit acceptance bullet list + per-bucket disposition tables.
3. Full 18-row Ruff E501 roster banked verbatim (R2 Minor #3 fix).
4. Full 33-file return-report grouped roster banked verbatim (R1 Major #4 fix).
5. Full 4-test Phase 8 walkthrough inventory table banked verbatim (R4 Major #1 fix).
6. Detailed bash script templates for the 3 archive-split tasks (T-3.1 + T-3.2 + T-3.3).

Banked as advisory per R1 Minor #1.

---

## §4 2 operator-locks verbatim verification

- **§1.1 SKIP BRAINSTORM** -- encoded verbatim in plan §1.1 + §0 (no spec doc created; brief is the design contract). Codex R1 + R2 prompts cited this lock; no Codex pushback.
- **§1.2 AMEND PLAN/SPEC TEXT ONLY for item #5** -- encoded verbatim in plan §1.2 + §A T-3.7. T-3.7 scope is text-only (3 amendment sites: Phase 12.5 #1 plan §H.4 line 1071 + spec §9.3 S4 line 940 + spec §5 line 104 table cell). ZERO code-fix path designed. Codex chain did not push back on this lock.
- Additional durable locks preserved: §1.3 Schema v19 UNCHANGED (T-3.5 escalation rule + plan §F.2); §1.4 ZERO Co-Authored-By footer (every commit stem in §A cites suppression; §I F2; §J restated).

---

## §5 Per-task acceptance criteria summary

| Task | Acceptance contract | Codex coverage |
|---|---|---|
| T-3.7 | 3 grep hits for "AMENDMENT (Phase 12.5 #3" across 2 files; ZERO code touched; amendment text accurately describes shipped helper SQL (`rd.resolved_by = 'auto_tier1_multi_leg'` query semantic) | R1 audited; PASS |
| T-3.5 | Bucket A/B: 4847 pass / 5 skipped / 0 fail; Bucket C (operator-approved skip-pattern): 4847 pass / 8 skipped / 0 fail; HARD STOP requiring operator approval BEFORE Step 3b artifact change | R3 + R4 + R5 hardened; PASS |
| T-3.6 | `ruff check swing/ --select E501` returns 0 (BINDING); global `--statistics` non-E501 unchanged from pre-T-3.6 baseline; ZERO `# noqa` without rationale; ASCII preservation on runtime-path string literals | R2 + R5 hardened; PASS |
| T-3.4 | Master inventory doc exists; ZERO duplication; T-3.7 + Phase 12.5 #2 A1/A2/A3 indexed; canonical 33 return-report grouped roster enumerated; ZERO modifications to spec/plan docs in T-3.4 diff | R1 + R3 hardened; PASS |
| T-3.1 | `CLAUDE.md` line 3 reduced from 143,843 to ~40-50k chars; new `docs/CLAUDE.md-archive.md` companion; archive pointer at line 4-5; PROCEED_WITH_WRITE count gate (15-30 active-retain band) | R3 + R4 hardened; PASS |
| T-3.2 | `docs/phase3e-todo.md` line-count toward 1500-2500; SHIPPED-only predicate + pre-write roster gate; archive ordering audit; pointer at TOP of active doc | R3 + R5 hardened; PASS |
| T-3.3 | `docs/orchestrator-context.md` line-count toward 400-500; pre-flight roster + operator review BEFORE script-write; pointers at TOPs of cap-drifting sections | R3 hardened; PASS |

---

## §6 Codex Major findings ACCEPTED with rationale

**ZERO** Major findings ACCEPTED-with-rationale. All 12 cumulative Major findings (R1: 4 + R2: 3 + R3: 3 + R4: 1 + R5: 1 + R6: 0) RESOLVED with code-content fixes.

**2 Minor ACCEPTED-with-rationale** (both at R1; both advisory; banked per §2 above):
- R1 Minor #1: plan line count above brief target -- precedent matches Phase 12.5 #1/#2 overshoot.
- R1 Minor #2: section letter drift (§H vs §J + §L vs §M) -- collapsed-gate single-sub-bundle precedent from Phase 12.5 #2.

---

## §7 V2 candidates banked

From plan §K + Codex chain:

| ID | Candidate | Source | Notes |
|---|---|---|---|
| V-3.5.A | Standalone Phase 8 walkthrough fix dispatch (if Bucket C lands) | T-3.5 disposition | banked at phase3e-todo per §F.3 |
| V-3.4.A | Promote amendment inventory entries to V2.1 §VII.F methodology revision proposal | T-3.4 | operator action; protocol-routed |
| V-3.1.A | CLAUDE.md gotchas section archive-split (separate concern; growing) | brief §5 OUT OF SCOPE note + plan §F | future maintenance pass when section cap drifts |
| V-3.4.B | Convert amendment inventory to machine-parseable YAML/JSON | T-3.4 | useful if orchestrator automation grows |

ZERO NEW V2 candidates surfaced during Codex chain rounds 1-6 beyond what was banked at plan-write time.

---

## §8 V2.1 §VII.F amendments banked

This dispatch's own amendments (per plan §L; chained into T-3.4 inventory):

| ID | Site | Summary | Status |
|---|---|---|---|
| **A-12.5.H4-banner-clears** (NEW; T-3.7 sub-target) | Phase 12.5 #1 plan §H.4 line 1071 + spec §9.3 S4 line 940 + spec §5 line 104 | Banner clears immediately on tier-3 override per shipped helper SQL (NOT "stays present"); operator-accepted semantic | superseded inline at T-3.7 (when executing-plans ships); indexed at T-3.4 |
| **A-12.5.2.A1** (Phase 12.5 #2 R-R §7) | Phase 12.5 #2 plan §C.1 | Class-name drift in `trades.py` + `schwab.py:558` (4 names mis-labeled; line numbers correct) | indexed at T-3.4 |
| **A-12.5.2.A2** (Phase 12.5 #2 R-R §7) | Phase 12.5 #2 plan §K | Test projection +81 fast tests vs actual +135 (parametrize-granularity overshoot precedent) | indexed at T-3.4 |
| **A-12.5.2.A3** (Phase 12.5 #2 R-R §7) | Phase 12.5 #2 plan §A T-2.2 | Acceptance count "14 fields" for `ReconcilePreResolutionContext` vs spec §5.2 actual 15 | indexed at T-3.4 |

**Cumulative pending V2.1 §VII.F amendments approaching Phase 12.5 #3 execution: ~30+** (chronological across Phase 9 + 10 + 11 + 12 + 12.5; T-3.4 will collate the canonical inventory).

ZERO NEW amendments surfaced during this writing-plans Codex chain that weren't already banked from prior dispatches.

---

## §9 Forward-binding lessons for executing-plans dispatch

From plan §M (5 NEW L-X1..L-X5) plus 4 NEW Codex-chain-surfaced lessons (L-W1..L-W4 in this return report):

### From plan §M (already encoded in plan):

- **L-X1**: When a plan/spec amendment is text-only across 3+ sites, sequence the sites left-to-right (smallest first) + commit ALL sites in ONE commit so the V2.1 §VII.F amendment ID resolves to a single SHA.
- **L-X2**: Phase 8 walkthrough triage requires Bucket classification BEFORE code changes -- surface the bucket disposition in the commit message stem.
- **L-X3**: Ruff E501 cleanup must use `Edit` (not `Write`) per-site to keep diff to ~1-3 lines per violation.
- **L-X4**: Archive-split boundary selection MUST be deterministic AND operator-reproducible (document in BOTH commit message stem AND archive-companion's heading).
- **L-X5**: V2.1 §VII.F amendment inventory doc is a READ-MOSTLY artifact -- optimize for grep-ability (every amendment row carries a hash + 1-sentence summary + source pointer).

### NEW Codex-chain-surfaced (R1-R6):

- **L-W1**: **Bucket-classification math requires explicit test-inventory table.** R4 Major #1 caught a 3-fail/1-pass file having its skip-set + expected-count math computed inconsistently across the plan (Step 3b said "4 tests SKIPPED"; §E projected "4844 pass / 9 skipped"; both wrong). Pattern: when authoring a partial-skip-set plan task, include a per-test inventory table with file-line + current status + per-bucket action; compute expected counts FROM the table (NOT from memory or rough estimates).
- **L-W2**: **Pre-write gate pattern for archive-split scripts** (T-3.1 + T-3.2 + T-3.3 all converged on this after R3 + R4). Any script that mutates an archive companion file MUST have an inline `PROCEED_WITH_WRITE = False` (or equivalent stdout-summary-then-raise) so the implementer reviews the roster BEFORE the write fires. Saves a round of "oops, archived wrong section" recovery. Particularly important for archive-split tasks because the source file is part of the project's narrative memory.
- **L-W3**: **Brief-baseline-vs-fresh-baseline drift verification** (R1 + the worktree-side fresh pytest run). The dispatch brief stated "actual is 4851" but the worktree fresh baseline was 4847. Plan-author MUST verify against fresh `pytest -m "not slow"` baseline at plan-write time AND use that figure as authoritative across §E projections + §H gate criteria. Brief figures can drift between brief-write and plan-write.
- **L-W4**: **ASCII-only invariant scope discipline** (R1 Major #1 + R2 Minor #1 + R3 ASCII-alignment cleanup). The brief said "ASCII-only on new text"; CLAUDE.md Gotchas section scopes this to RUNTIME CODE PATHS (`print()` / `click.echo()` / `sys.stdout.write()`). Documentation (markdown plans, specs, return reports, commit messages) uses em-dashes + `§` glyphs freely across the project. Plan author MUST explicitly disambiguate this scope at §D + §I + per-task acceptance to prevent Codex false-positive flags on documentation glyphs.

---

## §10 CLAUDE.md status-line refresh draft text (orchestrator paste-in)

For orchestrator paste-in at integration-merge time, after the existing 2026-05-18 Phase 12.5 #2 SHIPPED entry:

> **Phase 12.5 #3 writing-plans SHIPPED 2026-05-18** at `<MERGE-SHA>` (integration merge of `phase12-5-bundle-3-project-hygiene-writing-plans` via `--no-ff`; 2 commits = 1 plan-draft + 1 return-report; **6 Codex rounds -> NO_NEW_CRITICAL_MAJOR** convergent monotonic-Major taper (R1 0C/4M/4m -> R2 0C/3M/3m -> R3 0C/3M/2m -> R4 0C/1M/2m -> R5 0C/1M/2m -> R6 0C/0M/1m; operator-override past default MAX_ROUNDS=5 at R6 per Phase 12.5 #1 + #2 brainstorm precedent given clean convergent shape); ZERO Critical findings entire chain; **ZERO ACCEPT-WITH-RATIONALE on Major findings** (all 12 cumulative Major resolved with code-content fixes; matches Phase 12.5 #1 + #2 arc clean-record streak); 2 Minor accepted as advisory (line count overshoot + section-letter drift); ZERO Co-Authored-By footer drift across 2 commits (~165+ project-cumulative streak preserved); 1101-line plan at `docs/superpowers/plans/2026-05-18-phase12-5-bundle-3-project-hygiene-plan.md` (above 400-700 brief target by ~400 lines -- matches Phase 12.5 #1 1230 / #2 1082 overshoot precedent driven by Codex chain rigor + per-task acceptance specificity + 18-row Ruff roster + 33-file return-report grouped roster + 4-test Phase 8 walkthrough inventory all banked verbatim). **7 tasks T-3.1..T-3.7** single-sub-bundle decomposition (T-3.7 plan/spec amendment -> T-3.5 Phase 8 triage with 3-bucket HARD-STOP-at-Bucket-C discipline -> T-3.6 Ruff 18 E501 cleanup with full 18-row roster + ASCII-preservation contract -> T-3.4 V2.1 §VII.F amendment inventory at NEW `docs/v2-1-section-7f-amendments-2026-05-18.md` with canonical 33-file return-report grouped roster + grep supplement -> T-3.1 CLAUDE.md status-line archive-split with boundary 2026-05-12-inclusive + PROCEED_WITH_WRITE count gate -> T-3.2 phase3e-todo archive-split with SHIPPED-only predicate + pre-write roster gate -> T-3.3 orchestrator-context archive-split with pre-flight roster + operator review BEFORE script-write). **2 operator-locks preserved verbatim** (skip-brainstorm; amend-text-only for item #5 -- NO code fix to preserve banner mid-window per shipped helper SQL). **Schema v19 UNCHANGED LOCK** preserved (F1; F5; T-3.5 STOP-and-escalate rule). **4-surface operator-witnessed gate plan**: S1 inline pytest + ruff + per-task post-conditions; S2 visual verification of archive-split boundaries; S3 V2.1 §VII.F amendment doc readability + cross-reference accuracy; S4 Phase 12.5 #1 plan §H.4 + spec §9.3 S4 + spec §5 line-104 amendment verification. **4 NEW forward-binding lessons L-W1..L-W4 banked at return report §9** for executing-plans inheritance (Bucket-classification math requires explicit test-inventory table; pre-write gate pattern for archive-split scripts; brief-baseline-vs-fresh-baseline drift verification; ASCII-only invariant scope discipline). **Executing-plans dispatch UNBLOCKED** post operator-paired plan review.

---

## §11 Schema impact verdict

**v19 UNCHANGED** (F1 LOCK preserved end-to-end through Codex chain).

- T-3.1/T-3.2/T-3.3: doc-only edits; ZERO schema touch.
- T-3.4: new doc file; ZERO schema touch.
- T-3.5: bucket-dependent; Buckets A/B touch only fixture OR runner Python; Bucket C touches only test decorators + phase3e-todo entry; ZERO schema touch in any bucket per scope cap §F.3.
- T-3.6: Ruff line-wraps in `swing/`; ZERO schema files in scope.
- T-3.7: doc-only amendment to 3 sites; ZERO schema touch.

If any task surfaces a schema need during execution, STOP + escalate per §F.2 escalation rule (matches Phase 9 Sub-bundle A + Phase 12.5 #1 plan §F escalation precedent).

---

## §12 Phase 8 walkthrough triage finding summary

T-3.5 in this plan defers Phase 8 walkthrough disposition to executing-plans task execution time. **Plan-author's expectation** (NOT a binding contract; banked as advisory only):

- Most likely: **Bucket A** (trivial test-fixture drift in `synthetic_pipeline_env` monkeypatch wiring). The CLAUDE.md banked failure description ("archive returned None") suggests a `read_or_fetch_archive` monkeypatch path drift, plausibly fixed by updating the monkeypatch target.
- Possible: **Bucket B** (small runner-side adjustment if `_step_daily_management` lazy-import path drifted under a recent refactor).
- Unlikely but possible: **Bucket C** requiring HARD STOP + operator approval for skip-pattern OR alternative disposition.

Pre-existing failure inventory verified at plan-write time via worktree-side `pytest -m "not slow" -q -n auto`:
- 3 failures (NOT 4): test_phase8_pipeline_emits_snapshots_for_open_trades_only (line 196) + test_phase8_pipeline_second_same_day_run_upserts (line 258) + test_phase8_pipeline_run_id_is_pipeline_runs_id_not_evaluation_runs_id (line 415 -- the "Codex R1 discriminator").
- 1 passing in the same file: test_phase8_pipeline_record_event_log_after_run_links_correctly (line 329).

Plan §A T-3.5 Step 3b table encodes this inventory verbatim per R4 Major #1 LOCK.

---

## §13 Worktree teardown status

- Worktree branch `phase12-5-bundle-3-project-hygiene-writing-plans` is intact + ready for integration merge to `main`.
- Plan doc at `docs/superpowers/plans/2026-05-18-phase12-5-bundle-3-project-hygiene-plan.md` (1101 lines).
- Return report at `docs/phase12-5-bundle-3-project-hygiene-writing-plans-return-report.md` (this file).
- Codex session state at `.copowers-session-<repo-hash>.json` (auto-managed by `copowers:adversarial-critic`).
- On-disk worktree at `.worktrees/phase12-5-bundle-3-project-hygiene-writing-plans/` pending operator's cleanup-script `-DeregisterFirst` pass post-merge (branch matches cleanup-script regex `phase\d+[-_]`).

---

*End of return report. Phase 12.5 #3 writing-plans dispatch CLOSED. Operator-paired plan review UNBLOCKED. Executing-plans dispatch ready to commission after operator approves plan + drafts dispatch brief + provides inline implementer-dispatch prompt. 2 commits / 6 Codex rounds / ZERO ACCEPT-WITH-RATIONALE on Major / ZERO Co-Authored-By footer drift / schema v19 UNCHANGED / 4847 fast baseline preserved.*
