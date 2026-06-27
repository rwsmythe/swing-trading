# Orchestrator handoff — 2026-05-22 AM (post-T2.SB6c writing-plans MERGE; pre-housekeeping + pre-executing-plans-brief)

You are taking over as orchestrator for the Swing Trading project at the **post-T2.SB6c-writing-plans-merge + pre-housekeeping + pre-executing-plans-brief-drafting** breakpoint. Context-limit transition from prior orchestrator instance.

**main HEAD AT HANDOFF**: `e26bb0a` (T2.SB6c writing-plans merge --no-ff; pushed to origin).

**WORKING DIRECTORY**: `c:\Users\rwsmy\swing-trading`

**CRITICAL FIRST TASKS** (in order):
1. Read this brief end-to-end + `CLAUDE.md` + `docs/orchestrator-context.md` "Currently in-flight work" section + `docs/phase13-t2-sb6c-writing-plans-return-report.md` end-to-end.
2. **Execute post-merge housekeeping bundle** (CLAUDE.md current state + 4 NEW gotchas + phase3e-todo new top entry + orchestrator-context Prior demote + archive-split if needed; per `feedback_orchestrator_performs_merge.md` BINDING memory).
3. **Draft + commit executing-plans dispatch brief** at `docs/phase13-t2-sb6c-executing-plans-dispatch-brief.md` with §1.5.4 WilsonCI surfacing amendment (per operator decision captured below at §3.2).
4. **Provide inline implementer dispatch prompt** to operator per `feedback_always_provide_inline_dispatch_prompt.md`.

---

## §0 Critical bootstrap framing (memory entries; ALL BINDING)

- `feedback_pause_means_pause.md`
- `feedback_worktree_cli_invocation.md` — `python -m swing.cli` from worktree cwd, NOT bare `swing`
- `feedback_time_estimates_overstated.md` — divide by 3-5x for operator-paced wall-clock
- `feedback_orchestrator_qa_implementer_product.md` — QA every implementer product against reality on disk; do NOT merely summarize self-report
- `feedback_orchestrator_performs_merge.md` — merge + push + post-merge housekeeping = orchestrator action; do NOT ask "shall I merge"
- `feedback_orchestrator_vs_implementer_execution.md` — default to implementer-dispatch for context budget
- `feedback_always_provide_inline_dispatch_prompt.md` — every brief gets inline dispatch prompt as fenced code block
- `feedback_commit_brief_before_inline_prompt.md` — commit brief BEFORE providing inline prompt
- `feedback_regression_test_arithmetic.md`
- **`project_phase13_t4_sb_pause_for_list_additions.md` — SCHEDULED PAUSE AFTER T2.SB6c executing-plans SHIPS + housekeeping** (NOT T2.SB6c writing-plans — that's docs-only). Operator-supplied usability triage items required BEFORE T4.SB dispatch brief commissioning per spec §7.3 5-field template.

**Operator dispatches implementers themselves** (durable). Orchestrator drafts brief + provides inline dispatch prompt as fenced code block.

**NO Claude co-author footer**. Cumulative streak **~360+ commits ZERO trailer drift** through T2.SB6c writing-plans merge `e26bb0a`. Cite per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15) in every commit message.

---

## §1 Cumulative state at handoff

### Test + schema baseline
- **5559 fast tests** / 2 skipped / 0 failed (main HEAD `e26bb0a`; UNCHANGED since T2.SB6b SHIPPED at `6ec989e`; brainstorming + writing-plans phases were docs-only)
- Ruff clean (0 E501) / **schema v20** UNCHANGED (v20 LOCKED streak ENDS at T-A.6c.1 executing-plans landing)
- ZERO new Schwab API calls
- **~360+ cumulative ZERO `Co-Authored-By` trailer drift** through this merge

### Recent commits on main (last 8)

| SHA | Purpose |
|---|---|
| `e26bb0a` | Merge T2.SB6c writing-plans --no-ff (1820-line plan + 197-line return report; 7 implementer commits + 1 merge) |
| `c9bd715` | T2.SB6c writing-plans dispatch brief AMENDMENT (post-S2-S8 operator-witnessed gates) — added §1.5.1 + §1.5.2 |
| `7297a2b` | T2.SB6c writing-plans dispatch brief (original) |
| `043a5bc` | T2.SB6c brainstorming post-merge housekeeping |
| `fb177e3` | Merge T2.SB6c brainstorming --no-ff (659-line spec + 188-line return report) |
| `5ca64c3` | T2.SB6c brainstorming dispatch brief |
| `2dd90fe` | T2.SB6b post-merge housekeeping |
| `6ec989e` | Merge T2.SB6b --no-ff (closed-loop routes + Theme 1 chart integration + Deficiency 1 fold-in) |

### Phase 13 dispatch sequence remaining
```
T2.SB6c executing-plans dispatch (the work this handoff sets up) → T2.SB6c executing-plans SHIPPED → housekeeping → [PAUSE FOR OPERATOR LIST ADDITIONS per project_phase13_t4_sb memory] → T4.SB closer
```

**10 of 11 Phase 13 sub-bundles SHIPPED**: T1.SB0 + T2.SB1 + T3.SB1 + T2.SB2 + T2.SB3 + T3.SB2 + T2.SB4 + T2.SB5 + T3.SB3 + T2.SB6a/b. **2 remaining**: T2.SB6c executing-plans + T4.SB.

---

## §2 What just shipped (T2.SB6c writing-plans-phase artifacts)

### §2.1 Plan + return report

| Artifact | Path | Lines | Purpose |
|---|---|---|---|
| Plan | `docs/superpowers/plans/2026-05-21-phase13-t2-sb6c-v21-schema-and-closure-plan.md` | 1820 | 5-task decomposition T-A.6c.1..T-A.6c.5 per OQ-10 affirmed; §A-§J done criteria; §1.5 amendments encoded at §C.3 + §C.4 + §G.2 + §G.3 |
| Return report | `docs/phase13-t2-sb6c-writing-plans-return-report.md` | 197 | Codex chain shape (R6 NO_NEW_CRITICAL_MAJOR after 6 rounds; 1 CRITICAL + 16 MAJOR + 4 MINOR all RESOLVED; zero ACCEPT-WITH-RATIONALE); per-expansion verdicts; 4 NEW gotchas banked |

### §2.2 Codex chain shape

| Round | Verdict | Crit/Maj/Min |
|---|---|---|
| R1 | ISSUES_FOUND | 1/4/1 (R1 CRITICAL: SQL skeleton `pe.evaluation_id` vs canonical `pe.id`; Gap B.6 referenced non-existent `pattern_exemplars.weather_state_at_labeling`) |
| R2 | ISSUES_FOUND | 0/5/1 |
| R3 | ISSUES_FOUND | 0/3/2 |
| R4 | ISSUES_FOUND | 0/2/0 |
| R5 | ISSUES_FOUND | 0/2/0 |
| R6 | **NO_NEW_CRITICAL_MAJOR** | 0/0/0 |

ALL 21 cumulative findings RESOLVED in-place; ZERO ACCEPT-WITH-RATIONALE.

### §2.3 26th cumulative C.C lesson #6 validation — NOTABLE

First-run application of ALL 7 expansions AT WRITING-PLANS PHASE.

| Expansion | Verdict |
|---|---|
| #1 hardcoded-duplicate audit | CLEAN |
| #2 brief-vs-spec source-of-truth | CLEAN |
| #3 schema-CHECK-vs-semantic-contract | CLEAN |
| **#4 SQL skeleton column verification** (NEW refinement from T2.SB6c brainstorm) | **PARTIAL FAIL** — pre-Codex missed 3 column-correctness defects (`pe.evaluation_id`; `pattern_exemplars.weather_state_at_labeling`; `current_stage` Phase-13-vs-Phase-8 module attribution); R1-R3 caught all 3 |
| #5 cross-section spec inventory grep | CLEAN |
| **#6 content-completeness audit** (FIRST RUN at writing-plans phase) | CLEAN |
| **#7 cross-row semantic audit** (FIRST RUN at writing-plans phase) | **PARTIAL FAIL** — scope audit ≠ aggregation UNIT audit; R2-R4 caught 3 unit-mismatch defects |

**2 NEW expansion-discipline lessons banked for 27th cumulative validation at T2.SB6c executing-plans**:
1. **Expansion #4 refinement BINDING continues** — manual grep-against-migrations necessary but insufficient; V2 candidate = SQL-skeleton-extraction + sqlite-fixture-compile gate as process automation
2. **NEW Expansion #8 candidate (BANKED)**: per-aggregation-function UNIT audit on SQL skeletons — enumerate per-COUNT/SUM/GROUP-BY the counting unit; whether DISTINCT is needed; whether LIMIT applies at correct unit. Discriminating test pattern: cardinality-multiplied row fixtures.

### §2.4 4 NEW gotchas banked at writing-plans phase (per return report §7 #9-#12)

These MUST be added to `CLAUDE.md` during housekeeping (next step §4.1):

9. **SQL aggregation UNIT audit (NEW Expansion #8 candidate)** — for any GROUP BY / COUNT / SUM in a SQL skeleton, pre-Codex review MUST enumerate (a) what unit the function is counting (trades / evaluations / candidates); (b) whether DISTINCT is needed to prevent JOIN-cardinality inflation; (c) whether LIMIT applies at the correct unit. Pre-empt: writing-plans §5 watch item enumerates this per-SQL-skeleton.

10. **Existing-field reuse audit** — when extending a dataclass, FIRST grep for existing fields matching the planned-new-field shape. R4 MAJOR #2 caught `PatternOutcomeRow.reached_1r_n + _ci + hit_stop_n + _ci` fields ALREADY exist (populated as None per T2.SB6b V1 simplification); the plan claimed NEW `*_pct` fields which would have created field-duplication. Pre-empt: `Grep "_n: int | None\|_ci: " <dataclass module>` before claiming new fields.

11. **Template-rendering surface audit** — when populating existing-but-None fields, verify the template's render path explicitly. R5 MAJOR #2 caught `PatternOutcomeRow._ci` fields populated but NOT rendered by `swing/web/templates/metrics/pattern_outcomes.html.j2:35-45` (only the ratio renders). Plan claimed "no template edit needed" without verifying. Pre-empt: for any V1 STUB → LIVE transition, read template + enumerate which dataclass fields render + which are persisted-but-not-rendered.

12. **`date.fromisoformat()` discipline for cross-type-boundary calls** — when calling Python helper requiring `date` type from a column that stores TEXT ISO format, the conversion MUST be EXPLICIT at the call site. R3 MAJOR #2 caught `current_stage(conn, ticker, asof_date)` requires `date` but `pattern_evaluations.window_end_date` is TEXT. Pre-empt: cite conversion explicitly + add malformed-input discriminating test.

### §2.5 8 V1 simplifications + V2 candidates banked (closure-committed per dispatch intent)

Per return report §6 — these are pre-existing arc-residual items OR new operator-paired V2 decisions; NO new V1 STUBs introduced by T2.SB6c executing-plans:

1. Existing pre-v21 trades persist `candidate_id = NULL` + `pattern_evaluation_id = NULL` (OQ-1 LOCK; V2 enrichment if surfaced)
2. Multi-pattern_class trade backlink = single anchor (V2 many-to-many `trade_pattern_evaluations` link table)
3. Volume profile fetch-on-cache-miss accepted (OQ-14 LOCK; V2 `get_cached_only` variant)
4. Backup-gate strict-equality skips backup on multi-version jump (V2 `--enforce-stepwise` flag)
5. `pattern_evaluations.candidate_id` direct column (V2 schema dispatch if Phase 13.5+ needs)
6. Phase 6 `chart_pattern_algo` enum disjoint from Phase 13 detector enum (V2 schema migration)
7. Path C labeler_evidence_json backfill (V2 Path A labeler subagent emit contract widening for FRESH exemplars labeled post-T2.SB6c)
8. **Gap B.5 metric tile V1 display = ratio-only + `_ci` populated-but-not-rendered** — **OPERATOR DECISION 2026-05-22 AM: ADD WilsonCI surfacing to T-A.6c.4 scope via §1.5.4 amendment in executing-plans dispatch brief.** Closes the V1 simplification entirely; ZERO V2 banking for this row. See §3.2 below for the amendment scope.
9. Gap B.1 trend-template state V1 returns `'stage_2' | 'undefined'` per `current_stage` wrapper at `swing/patterns/foundation.py:745` (V2 full Weinstein 4-stage labeling)

---

## §3 Operator-paired decisions captured (BINDING for next orchestrator)

### §3.1 14 OQs from T2.SB6c brainstorming spec §7 — ALL AFFIRMED VERBATIM 2026-05-21 PM #5
Operator concurred with all brainstorm-recommended dispositions en bloc; spec §7 dispositions BINDING for writing-plans + executing-plans phases. No re-triage required.

### §3.2 Gap B.5 WilsonCI surfacing — OPERATOR DECISION 2026-05-22 AM
**Decision: ADD WilsonCI surfacing to T-A.6c.4 scope via executing-plans dispatch brief §1.5.4 amendment.** Source: AskUserQuestion 2026-05-22 AM by prior orchestrator post-merge of T2.SB6c writing-plans.

**Amendment scope** for §1.5.4 in executing-plans dispatch brief:
- **Extend** `swing/web/templates/metrics/pattern_outcomes.html.j2:35-45` to render `{n: 12, Wilson CI 0.43-0.91}` alongside the ratio, matching Phase 10 honesty.wilson_ci convention.
- **~2-3 additional tests at T-A.6c.4**: template render test (Wilson CI visible) + render-with-CI test (correct format string per Phase 10 convention) + suppression-at-n<5 test (suppression marker still fires).
- **Closes the V1 simplification entirely**; ZERO V2 banking for the WilsonCI row in §2.5 above.
- **Bump test count projection**: ~92-95 → ~94-98 fast tests at T-A.6c.4 + 1 fast E2E.
- **Cumulative process gotcha banking**: this closure is itself a manifestation of NEW gotcha #11 (template-rendering surface audit). The Codex R5 MAJOR #2 caught the rendering gap during writing-plans; operator-paired triage decided to CLOSE it at executing-plans rather than V2-bank it.

The amendment mirrors the §1.5.1 + §1.5.2 amendment pattern from the writing-plans dispatch brief (committed at `c9bd715`).

### §3.3 PAUSE-FOR-LIST-ADDITIONS for T4.SB still binding
Per `project_phase13_t4_sb_pause_for_list_additions` memory: T4.SB closer dispatch BLOCKED on operator's added usability triage items per spec §7.3 5-field structured template (Issue title / Surface / Frequency / Severity / Operator framing / Proposed resolution). Surfaces at T2.SB6c executing-plans SHIPPED + housekeeping boundary.

---

## §4 What the next orchestrator MUST do (in order)

### §4.1 Post-merge housekeeping bundle (4 files; standard cumulative precedent)

1. **CLAUDE.md line 3 refresh** — T2.SB6c brainstorming SHIPPED → T2.SB6c writing-plans SHIPPED at `e26bb0a`. Cite 26th cumulative C.C lesson #6 validation NOTABLE + 4 NEW gotchas banked + 8 V1 simplifications with closure-committed disposition.

2. **CLAUDE.md 4 NEW gotchas appended** (per §2.4 above):
   - SQL aggregation UNIT audit (NEW Expansion #8 candidate)
   - Existing-field reuse audit before claiming new dataclass fields
   - Template-rendering surface audit before claiming "no template edit needed"
   - `date.fromisoformat()` discipline for cross-type-boundary calls

3. **docs/phase3e-todo.md** new top entry for T2.SB6c writing-plans SHIPPED with full Codex chain + per-expansion verdict + 4 NEW gotchas + 8 V1 simplifications + Gap B.5 WilsonCI operator decision + executing-plans dispatch UNBLOCKED.

4. **docs/orchestrator-context.md** current state refresh + Prior demote (T2.SB6c brainstorming current → Prior #1) + archive-split per size-check trigger (Prior count should be at 10 currently; demote brings to 11; archive oldest container). Run `grep -c "^### Prior state" docs/orchestrator-context.md` first to confirm count.

5. **docs/orchestrator-context-archive.md** new appendix containing the archived oldest Prior verbatim.

6. **Commit housekeeping bundle + push**. Conventional message; ZERO `Co-Authored-By` footer; cite the discipline per cumulative precedent.

### §4.2 Executing-plans dispatch brief drafting

Create `docs/phase13-t2-sb6c-executing-plans-dispatch-brief.md` covering:

- **§0 Status + read first** (plan at `e26bb0a` is PRIMARY substrate; return report; CLAUDE.md cumulative gotchas)
- **§1 OQ affirmations** (all 14 affirmed verbatim per §3.1; spec §7 dispositions BINDING)
- **§1.5 Amendments**:
  - §1.5.1 + §1.5.2 inherited from writing-plans brief amendment (chart_renders write-through + labeler backfill) — already encoded in plan §C.3 + §C.4; reference rather than re-encode.
  - **§1.5.3** chart_renders backfill amendment (REFERENCE from writing-plans brief amendment at `c9bd715`).
  - **NEW §1.5.4 Gap B.5 WilsonCI surfacing** per §3.2 above: add template extension to T-A.6c.4 scope; ~2-3 additional tests; closes V1 simplification entirely; ZERO V2 banking.
- **§2 Scope inheritance from plan** — concurrent dispatch T-A.6c.1+2+3 (per OQ-10 LOCK); sequential T-A.6c.4 + T-A.6c.5; ~94-98 fast tests + 1 fast E2E projected post-§1.5.4 amendment.
- **§3 Watch items + cumulative discipline** — pre-Codex 7-expansion discipline + 2 NEW refinements from writing-plans banking (#4 SQL-column verification refinement; #8 candidate SQL aggregation UNIT audit) BINDING for 27th validation; the 4 NEW gotchas from §2.4 above BINDING.
- **§4 Per-task summary** — reference plan §G.1..§G.5; do NOT re-encode (plan is BINDING substrate).
- **§5 Done criteria** for executing-plans output (5 task commits + 0-3 Codex fix bundles + 1 return report; baseline 5559 → ~5651-5654 fast + 1 fast E2E expected per plan §F.3 + §1.5.4 bump).
- **§6 References**.
- **§7 NON-scope**.
- **§8 Post-executing-plans handback** (orchestrator-side merge + housekeeping + PAUSE-FOR-LIST-ADDITIONS surface).

**Commit brief BEFORE inline prompt** (per `feedback_commit_brief_before_inline_prompt`).

### §4.3 Provide inline implementer dispatch prompt

Per `feedback_always_provide_inline_dispatch_prompt`. Fenced code block; operator copy/pastes into fresh implementer session. The prompt should:
- Reference the executing-plans dispatch brief at the new commit SHA
- Reference the plan at `e26bb0a`
- Enumerate the §1.5 amendments (especially the NEW §1.5.4 WilsonCI surfacing)
- Cite all 14 OQ affirmations VERBATIM
- Cite the 4 NEW gotchas + 2 NEW expansion-discipline refinements BINDING for 27th cumulative validation
- Cite the 5-task decomposition with concurrent dispatch T-A.6c.1+2+3 + sequential T-A.6c.4 + T-A.6c.5
- Cite the cross-bundle pin row 12 planted at T-A.6c.1 + un-skip at T-A.6c.5

---

## §5 Operator-pending items (NOT orchestrator-blocking)

- **T2.SB6b S2-S8 operator-paired browser gates from prior session** — operator already ran the gates with prior orchestrator; findings drove the §1.5.1 + §1.5.2 amendments. Once T2.SB6c executing-plans ships, re-run S2-S8 to verify the closures land.
- **Worktree husks** — multiple from recent dispatches:
  - `.worktrees/phase13-t2-sb6-closed-loop-surface` (T2.SB6a)
  - `.worktrees/phase13-t2-sb6b-closed-loop-routes` (T2.SB6b)
  - `.worktrees/phase13-t2-sb6c-v21-closure-brainstorm` (T2.SB6c brainstorming)
  - `.worktrees/phase13-t2-sb6c-writing-plans` (T2.SB6c writing-plans; just merged)
  - Operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` when convenient
- **Schwab refresh-token clock** — last operator check showed ~1d remaining at handoff (expires ~2026-05-24T06:40); renew via `swing schwab logout` → `swing schwab setup` when ≤24h
- **T4.SB usability triage list** — PAUSE-FOR-LIST-ADDITIONS binding; required before T4.SB dispatch brief commissioning per spec §7.3 5-field template

---

## §6 Cumulative streaks to preserve

- **ZERO `Co-Authored-By` footer trailer drift**: ~360+ commits cumulative through T2.SB6c writing-plans merge. ABSOLUTELY DO NOT regress. Explicit citation required in commit messages.
- **C.C lesson #6 cumulative validations**: 22x CLEAN through T3.SB3 + 23rd NOTABLE T2.SB6a + 24th NOTABLE T2.SB6b + 25th NOTABLE T2.SB6c brainstorming + 26th NOTABLE T2.SB6c writing-plans. 27th expected at T2.SB6c executing-plans with all 7 expansions + 2 NEW refinements + 4 NEW gotchas BINDING.
- **Schema v20 LANDED at T-A.1.1**; UNCHANGED since (12+ sub-bundles). v20 LOCKED streak ENDS at T-A.6c.1 executing-plans landing.
- **ZERO new Schwab API calls** through Theme 2 + chart surface work (preserved per L2 LOCK).
- **5559 fast tests baseline** — UNCHANGED through brainstorming + writing-plans phases (docs only).

---

## §7 Quick-reference SHA roster

| Item | SHA |
|---|---|
| main HEAD at handoff | `e26bb0a` (T2.SB6c writing-plans merge) |
| T2.SB6c writing-plans merge | `e26bb0a` |
| T2.SB6c writing-plans brief amendment | `c9bd715` (post-S2-S8 gates) |
| T2.SB6c writing-plans brief (original) | `7297a2b` |
| T2.SB6c brainstorming post-merge housekeeping | `043a5bc` |
| T2.SB6c brainstorming merge | `fb177e3` |
| T2.SB6c brainstorming dispatch brief | `5ca64c3` |
| T2.SB6b post-merge housekeeping | `2dd90fe` |
| T2.SB6b merge | `6ec989e` |
| T2.SB6a housekeeping | `040455b` |
| T2.SB6a merge | `340f868` |

---

## §8 Suggested first session flow (next orchestrator)

1. Read this brief end-to-end
2. Read `CLAUDE.md` line 3 (current state at HEAD `e26bb0a`)
3. Read `docs/phase13-t2-sb6c-writing-plans-return-report.md` end-to-end (key sections: §5 per-expansion verdict; §7 4 NEW gotchas banked)
4. Read `docs/orchestrator-context.md` "Currently in-flight work" — current state reflects T2.SB6c brainstorming SHIPPED; needs refresh to T2.SB6c writing-plans
5. Read `docs/phase13-t2-sb6c-writing-plans-dispatch-brief.md` (the amended brief at `c9bd715`) — especially §1.5 amendments inherited into the plan
6. Execute housekeeping (per §4.1 above)
7. Commit housekeeping + push
8. Draft executing-plans dispatch brief with §1.5.4 WilsonCI surfacing amendment (per §3.2 + §4.2 above)
9. Commit brief
10. Provide inline implementer dispatch prompt to operator

Estimated wall-clock: ~30-60 min orchestrator-paced (housekeeping is straightforward; executing-plans brief is mostly references-to-plan + amendment encoding).

---

## §9 Do NOT

- Commission T4.SB dispatch without operator's added items (`project_phase13_t4_sb_pause_for_list_additions` BINDING)
- Re-execute writing-plans phase — it's DONE; the plan at `e26bb0a` is BINDING substrate
- Modify the plan in-place — amendments go in the executing-plans dispatch brief as §1.5.X sections (mirroring writing-plans brief amendment precedent at `c9bd715`)
- Add Co-Authored-By footer to ANY commit (~360+ streak)
- Re-litigate the 14 OQ dispositions — operator affirmed all VERBATIM 2026-05-21 PM #5
- Re-litigate the Gap B.5 WilsonCI decision — operator picked "ADD to T-A.6c.4 scope" 2026-05-22 AM
- Skip pre-Codex orchestrator-side review at executing-plans phase (27th cumulative validation expected with all 7 expansions + 2 NEW refinements + 4 NEW gotchas BINDING)
- Skip size-check pre-flight before housekeeping
- Push without verifying empty Co-Authored-By trailer on commits

---

*End of orchestrator handoff brief. Post-T2.SB6c-writing-plans-merge + pre-housekeeping + pre-executing-plans-brief-drafting transition. Next orchestrator: execute housekeeping per §4.1 → draft executing-plans dispatch brief with §1.5.4 WilsonCI surfacing amendment per §4.2 → provide inline implementer dispatch prompt per §4.3. ~360+ cumulative ZERO Co-Authored-By trailer drift preserved through this handoff commit. PAUSE-FOR-LIST-ADDITIONS for T4.SB still binding post-T2.SB6c executing-plans SHIPPED + housekeeping boundary.*
