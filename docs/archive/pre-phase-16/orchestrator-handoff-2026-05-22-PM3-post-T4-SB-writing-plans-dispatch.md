# Orchestrator handoff — 2026-05-22 PM #3 (post-T4.SB-brainstorming-merge + T4.SB-writing-plans-DISPATCHED + pre-writing-plans-handback)

You are taking over as orchestrator for the Swing Trading project at the **post-T4.SB-brainstorming-merge + writing-plans dispatched + pre-writing-plans-handback** breakpoint. Context-limit transition from prior orchestrator instance (which exited at 22% remaining context after dispatching the writing-plans implementer per operator direction).

**main HEAD AT HANDOFF**: `4690933` (T4.SB writing-plans dispatch brief committed + pushed). Pending: this handoff-brief commit itself, which becomes the new HEAD before you read this.

**WORKING DIRECTORY**: `c:\Users\rwsmy\swing-trading`

**CRITICAL FIRST TASKS** (in order):
1. Read this brief end-to-end + `CLAUDE.md` line 3 + `docs/orchestrator-context.md` "Currently in-flight work" section.
2. **Wait for operator to deliver T4.SB writing-plans implementer handback** (not yet shipped at this handoff write-time). Operator dispatches the writing-plans implementer per inline prompt at chat 2026-05-22 PM #2 (provided in chat by prior orchestrator just before this handoff).
3. **On handback**: QA the implementer product per `feedback_orchestrator_qa_implementer_product` BINDING memory + merge + housekeeping + draft executing-plans dispatch brief + provide inline prompt.
4. **Be context-aware**: T4.SB executing-plans will be the LARGEST T4.SB dispatch (6 tasks; substantial scope). You MAY need to author another handoff brief BEFORE executing-plans handback to a Turn C orchestrator. Plan accordingly.

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
- `project_phase13_t4_sb_pause_for_list_additions.md` — **RESOLVED 2026-05-22 PM** (7 operator-supplied triage items locked; brainstorming SHIPPED + 18 OQs operator-triaged + writing-plans dispatched). Memory may stay as historical record; no further pause-blocking.

**Operator dispatches implementers themselves** (durable). Orchestrator drafts brief + provides inline dispatch prompt as fenced code block.

**NO Claude co-author footer**. Cumulative streak **~378+ commits ZERO trailer drift** through T4.SB brainstorming housekeeping `f7dec0e` + writing-plans brief `4690933`. Cite per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15) in every commit message.

---

## §1 Cumulative state at handoff

### Test + schema baseline
- **5670 fast tests** / 2 skipped / 0 failed (main HEAD at handoff; UNCHANGED since T2.SB6c executing-plans SHIPPED at `f30ceed`; T4.SB brainstorming + writing-plans dispatch are docs-only)
- Ruff clean (0 E501) / **schema v21** UNCHANGED (T4.SB SHOULD NOT change schema per spec §A.2 LOCK)
- ZERO new Schwab API calls (L2 LOCK preserved through Phase 13)
- **~378+ cumulative ZERO `Co-Authored-By` trailer drift** through these dispatches

### Recent commits on main (last 8)

| SHA | Purpose |
|---|---|
| (TBD) | Orchestrator handoff brief (this file's commit) |
| `4690933` | T4.SB writing-plans dispatch brief + 4 §1.5 amendments |
| `f7dec0e` | Post-T4.SB-brainstorming housekeeping bundle |
| `4299340` | Merge T4.SB brainstorming --no-ff (1045-line spec + 205-line return report; 7 implementer commits) |
| `e75f743` | T4.SB brainstorming dispatch brief + triage list operator-confirmed fields |
| `6e3ed06` | Banked A+-like-indicators applied-research question |
| `a213d9e` | Banked T4.SB triage item 7 (metrics wiring audit) |
| `b496036` | Banked 4 NEW T4.SB triage items 3-6 from operator post-S2-S11 input |

### Phase 13 dispatch sequence remaining
```
T4.SB brainstorming SHIPPED (4299340) → T4.SB writing-plans DISPATCHED (Turn A; this orchestrator) → writing-plans implementer ships → Turn B (YOU; this handoff target): QA + merge + housekeeping + draft executing-plans brief + inline prompt → T4.SB executing-plans implementer ships → Turn C (maybe separate from B): QA + merge + housekeeping + gates + Phase 13 FULLY CLOSED marker + post-T4.SB triage meeting
```

**11 of 11 Phase 13 sub-bundles SHIPPED through T2.SB6c**; T4.SB brainstorming SHIPPED (advances closer arc; does NOT yet flip Phase 13 to fully closed). T4.SB writing-plans + executing-plans remain. Phase 13 FULLY CLOSED marker fires at T-T4.SB.6 executing-plans SHIPPED per spec §K.

---

## §2 What just shipped (T4.SB brainstorming + writing-plans dispatch this orchestrator session)

### §2.1 T4.SB brainstorming SHIPPED at `4299340`

- **Spec**: `docs/superpowers/specs/2026-05-22-phase13-t4-sb-closer-design.md` (1045 lines; 13 sections §A-§M)
- **Return report**: `docs/phase13-t4-sb-brainstorm-return-report.md` (205 lines)
- **7-commit dispatch**: 1 initial spec + 4 Codex MCP fix bundles + 1 R5 MINOR closure + 1 return report
- **Codex chain converged R5 NO_NEW_CRITICAL_MAJOR after 5 rounds** (ZERO CRITICAL entire chain; 17 MAJOR ALL RESOLVED; 10 MINOR with 9 RESOLVED + 1 advisory closed)
- **28th cumulative C.C lesson #6 validation NOTABLE** (Expansion #7 PARTIAL FAIL on architecture-location wrong-module placement; NEW Expansion #10 CANDIDATE banked)
- **17 MAJOR findings clustered across 5 thematic sub-categories** → all 5 → NEW Expansion #10 candidate (see CLAUDE.md gotcha #14)
- **14 V1 simplifications banked with V2 dependency cited** per return report §4.1

### §2.2 18 OQs operator-locked 2026-05-22 PM #2

Operator concurred on the 15 OQs at orchestrator recommendations + supplied 3 specific decisions:
- **OQ-1.3 + OQ-1.4 SCOPE EXPANSION**: parameter-sweep sensitivity harness under `research/harness/aplus_sensitivity/` (NOT snapshot diagnostic; NOT production placement)
- **OQ-5.4**: Option A LOCKED (dashboard reader binds to one pipeline_run anchor; JIT writes match anchor)
- **OQ-CL.2**: DEFERRED until T-T4.SB.1 sensitivity harness ships its output; T-T4.SB.6 closer ships triage-agenda artifact stub

### §2.3 T4.SB writing-plans dispatch brief at `4690933`

- **Brief**: `docs/phase13-t4-sb-writing-plans-dispatch-brief.md` (295 lines)
- **Sections**: §0 read first + §1 OQ dispositions verbatim + §1.5 (4 amendments) + §2 scope inheritance + §3 watch items + §4 done criteria + §5 references + §6 NON-scope + §7 post-writing-plans handback
- **4 §1.5 amendments**:
  - §1.5.1 — OQ-1.3 sensitivity harness expansion (data source: persisted candidate_criteria; sweep ~10-20 variables × 5-7 points; output: sensitivity matrix CSV + markdown analysis; test budget bumped to ~30-40)
  - §1.5.2 — OQ-CL.2 deferred-until-diagnostic disposition (triage-agenda artifact at `docs/phase13-closer-next-phase-triage.md`)
  - §1.5.3 — OQ-5.4 Option A LOCKED (dashboard anchors at one pipeline_run; JIT writes match)
  - §1.5.4 — OQ-1.4 research-branch placement (paired with §1.5.1; `research/harness/aplus_sensitivity/` mirroring earnings_proximity precedent)

### §2.4 Inline implementer dispatch prompt provided in chat 2026-05-22 PM #2 (Turn A final action)

The inline prompt is in the chat history at the orchestrator-side message just before this handoff. Operator pastes into fresh Claude Code session to start the writing-plans implementer.

---

## §3 What YOU (Turn B orchestrator) MUST do on writing-plans handback

### §3.1 QA pass against reality on disk (per `feedback_orchestrator_qa_implementer_product`)

Verify implementer claims via direct inspection:
- `git log` writing-plans branch — verify ~6-9 commits expected (1 plan + 2-5 Codex fix bundles + 1 return report)
- ZERO `Co-Authored-By` trailer across all branch commits (use `git log <baseSHA>..<branchHEAD> --format="%h | %(trailers:key=Co-Authored-By,valueonly)"`)
- Plan file exists at expected path + has all 12 sections §A-§L per brief §4 done criteria
- Schema v21 UNCHANGED (docs-only branch should not touch swing/data/ migrations or models)
- Baseline 5670 fast tests UNCHANGED (docs-only branch should not change tests)
- Return report exists at `docs/phase13-t4-sb-writing-plans-return-report.md` per brief §7

### §3.2 Merge per `feedback_orchestrator_performs_merge` BINDING memory

```bash
git merge --no-ff phase13-t4-sb-writing-plans -m "$(cat <<'EOF'
Merge phase13-t4-sb-writing-plans into main: T4.SB writing-plans SHIPPED

T4.SB writing-plans SHIPPED -- SECOND sub-bundle of the Phase 13
closer arc. Plan at docs/superpowers/plans/2026-05-22-phase13-t4-sb
-closer-plan.md (or operator-paired-named equivalent). Return report
at docs/phase13-t4-sb-writing-plans-return-report.md.

<implementer's commit chain summary>

<Codex chain shape>

<29th cumulative C.C lesson #6 validation verdict>

<NEW gotchas if any>

<V1 simplifications banked>

Schema v21 UNCHANGED through writing-plans phase (docs only); baseline
5670 fast tests UNCHANGED; ZERO new Schwab API calls (L2 LOCK
preserved); ruff clean (0 E501).

ZERO Co-Authored-By footer trailer drift across all <N> branch commits
+ this merge commit (~<count>+ project-cumulative streak preserved).

Phase 13 sub-bundle ship count: 11 of 11 SHIPPED; T4.SB writing-plans
SHIPPED THIS pass advances the closer arc; T-T4.SB.6 executing-plans
SHIPPED still pending to fully close Phase 13.
EOF
)"
```

Then `git push origin main`.

### §3.3 Post-merge housekeeping bundle (4 files; cumulative precedent)

1. **CLAUDE.md line 3 refresh** — T4.SB brainstorming SHIPPED → T4.SB writing-plans SHIPPED at `<new merge SHA>`. Cite 29th cumulative C.C lesson #6 validation result + any NEW gotchas banked at writing-plans phase. **Watch line-3 size**: this orchestrator session compacted line 3 from 9750 to 5461 chars; preserve compact format; demote previous T4.SB-brainstorming verbose details to brief predecessor reference.
2. **CLAUDE.md NEW gotchas if any** — depending on Codex findings at writing-plans phase. Expansion #10 candidate was banked at brainstorming; expansion may be confirmed BINDING at 29th validation. New gotchas would append after gotcha #14 in CLAUDE.md.
3. **docs/phase3e-todo.md** NEW top entry for T4.SB writing-plans SHIPPED with full Codex chain + per-expansion verdict + V1 simplifications + forward action sequence.
4. **docs/orchestrator-context.md** current state refresh + Prior demote (T4.SB brainstorming current → Prior #1) + archive-split per size-check trigger. **Run `grep -c "^### Prior state" docs/orchestrator-context.md` first** to confirm count (was 10 post-T4.SB-brainstorming housekeeping; demote brings to 11; archive oldest).
5. **docs/orchestrator-context-archive.md** new appendix containing archived oldest Prior verbatim.
6. **Commit housekeeping bundle + push**. ZERO `Co-Authored-By` footer; cite cumulative discipline.

### §3.4 Draft T4.SB executing-plans dispatch brief at `docs/phase13-t4-sb-executing-plans-dispatch-brief.md`

Cover (12 sections):
- §0 Read first (plan at new merge SHA is PRIMARY substrate; brainstorming spec at `f7dec0e`; writing-plans return report; CLAUDE.md gotchas; `research/phase-0-tasks.md` for T-T4.SB.1 research-branch coordination)
- §1 18 OQs locked verbatim per Turn A operator triage (per writing-plans brief §1)
- §1.5 Amendments inherited from writing-plans brief (§1.5.1-§1.5.4) — REFERENCE; already encoded in plan. If executing-plans phase surfaces NEW amendments (e.g., operator decisions during plan-write Codex cycles), encode as §1.5.5+.
- §2 Scope inheritance from plan (6-task decomposition T-T4.SB.1..T-T4.SB.6; concurrent dispatch graph per plan §H)
- §3 Watch items — pre-Codex 7-expansion + 4 NEW refinements (Expansion #4 SQL-column + Expansion #8 SQL aggregation UNIT + Expansion #9 form-render anchor lifecycle + Expansion #10 architecture-location) BINDING for 30th cumulative validation
- §4 Per-task summary (REFERENCE; plan §G is BINDING substrate)
- §5 Done criteria for executing-plans output (6 task commits + 0-5 Codex fix bundles + 1 return report; baseline 5670 → ~5730-5830 fast + 1 fast E2E)
- §6 References
- §7 NON-scope
- §8 Post-executing-plans handback (Turn C orchestrator: QA + merge + housekeeping + gates + Phase 13 FULLY CLOSED marker + post-T4.SB triage)

### §3.5 Commit brief BEFORE inline prompt per `feedback_commit_brief_before_inline_prompt` BINDING

Then provide inline implementer dispatch prompt per `feedback_always_provide_inline_dispatch_prompt`. Fenced code block; operator copy/pastes into fresh implementer session. Cite:
- New plan at the post-merge HEAD SHA
- Brainstorming spec at `f7dec0e`
- Writing-plans brief at `4690933`
- All 18 OQ dispositions + 4 §1.5 amendments BINDING
- 6-task decomposition + concurrent dispatch graph from plan §H
- Pre-Codex 7-expansion + 4 NEW refinements + 14 cumulative gotchas BINDING for 30th validation

### §3.6 Context budget watch

T4.SB executing-plans is the LARGEST T4.SB dispatch (6 tasks; substantial scope including investigation harness + cosmetic fixes + architectural rewrite). When executing-plans handback arrives, the QA + merge + housekeeping work will be context-heavy. If your remaining context is below ~30% when executing-plans handback arrives:

**Author another orchestrator handoff brief** at `docs/orchestrator-handoff-<date>-PM-N-post-T4-SB-writing-plans-merge-pre-executing-plans-handback.md` for a Turn C orchestrator. Encode:
- Current main HEAD post-writing-plans housekeeping
- What's been shipped through Turn B
- Pending: executing-plans implementer dispatch + their return
- Turn C tasks: QA + merge + housekeeping + operator-witnessed gates + Phase 13 FULLY CLOSED marker per spec §K + post-T4.SB triage meeting (OQ-CL.2 deferred decision per §1.5.2 amendment)

The orchestrator shift convention: **fire the shift between major phases of the dispatch chain** to keep context fresh for downstream QA + housekeeping work.

---

## §4 Operator-pending items (NOT orchestrator-blocking; surface in operator update post-merge)

- **T4.SB writing-plans operator-witnessed gate** if any (typically none for docs-only writing-plans phase)
- **Worktree husks**: `.worktrees/phase13-t4-sb-brainstorming` (post-Turn A merge) + `.worktrees/phase13-t4-sb-writing-plans` (post-Turn B merge). Operator runs `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` when convenient.
- **Schwab refresh-token clock**: renew via `swing schwab logout` → `swing schwab setup` when ≤24h remaining
- **post-T4.SB-SHIPPED operator-paired triage meeting**: OQ-CL.2 deferred decision (Phase 14 trigger / Applied Research focus / idle monitoring) — agenda artifact at `docs/phase13-closer-next-phase-triage.md` shipped at T-T4.SB.6 closer

---

## §5 Cumulative streaks to preserve

- **ZERO `Co-Authored-By` footer trailer drift**: ~378+ commits cumulative through `4690933`. ABSOLUTELY DO NOT regress. Explicit citation required in commit messages.
- **C.C lesson #6 cumulative validations**: 22x CLEAN through T3.SB3 + 23rd-27th NOTABLE through T2.SB6 arc + 28th NOTABLE T4.SB brainstorming. **29th expected at T4.SB writing-plans handback** with all 7 expansions + 4 NEW refinements (#4 + #8 + #9 + #10) + 6 NEW gotchas (#9-#14) BINDING.
- **Schema v21 LOCKED**: through Phase 13 closer arc per spec §A.2 LOCK.
- **ZERO new Schwab API calls** (L2 LOCK preserved through Phase 13).
- **5670 fast tests baseline** — UNCHANGED through brainstorming + writing-plans phases (docs only).

---

## §6 Quick-reference SHA roster (post-T4.SB-writing-plans-dispatch)

| Item | SHA |
|---|---|
| main HEAD at this handoff write-time | `4690933` (T4.SB writing-plans dispatch brief) |
| Handoff brief commit (this file) | TBD on commit |
| Post-T4.SB-brainstorming housekeeping | `f7dec0e` |
| T4.SB brainstorming merge | `4299340` |
| T4.SB brainstorming dispatch brief | `e75f743` |
| Banked applied-research question | `6e3ed06` |
| Banked T4.SB triage item 7 | `a213d9e` |
| Banked T4.SB triage items 3-6 | `b496036` |
| CLAUDE.md 3-stale-facts fix | `722378a` |
| T2.SB6c executing-plans merge | `f30ceed` |
| Schema v21 landing | `7ee5a4a` (T-A.6c.1 within T2.SB6c) |

---

## §7 Suggested first session flow (Turn B)

When operator returns with T4.SB writing-plans handback summary:

1. Read this brief end-to-end
2. Read `CLAUDE.md` line 3 (current state at HEAD `4690933` or later if a Turn-A wrap commit landed)
3. Read `docs/phase13-t4-sb-writing-plans-dispatch-brief.md` at `4690933` (Turn A's product; primary substrate for QA)
4. Operator delivers the return report path + commit chain summary
5. QA the implementer product per §3.1 above (file:line + Codex chain verdict + cumulative gotcha citations)
6. Merge per §3.2 + housekeeping per §3.3
7. Draft executing-plans dispatch brief per §3.4
8. Commit brief + provide inline prompt per §3.5
9. Context-budget check per §3.6 — if context is below ~30% when executing-plans handback arrives, author Turn C handoff brief before letting context exhaust

Estimated wall-clock: ~1-2 hours orchestrator-paced for the full Turn B sequence (QA + merge + housekeeping + executing-plans brief drafting).

---

## §8 Do NOT

- Commission Phase 14 — deferred per §1.5.2 amendment until T-T4.SB.1 sensitivity harness ships its output
- Modify the brainstorming spec or writing-plans brief in-place — amendments go in the executing-plans dispatch brief as §1.5.5+ sections (mirroring T2.SB6c precedent)
- Add Co-Authored-By footer to ANY commit (~378+ streak)
- Re-litigate the 18 OQ dispositions — operator locked all 18 + 4 amendments 2026-05-22 PM #2
- Skip pre-Codex orchestrator-side review at executing-plans phase (30th cumulative validation expected with all 7 expansions + 4 NEW refinements + 6 NEW gotchas BINDING)
- Skip size-check pre-flight before housekeeping
- Push without verifying empty Co-Authored-By trailer on commits

---

*End of orchestrator handoff brief. Post-T4.SB-brainstorming-merge + T4.SB-writing-plans-DISPATCHED transition. Next orchestrator (Turn B): wait for writing-plans handback → execute §3.1-§3.6 → consider context-budget Turn-C handoff if needed. ~378+ cumulative ZERO Co-Authored-By trailer drift preserved through this handoff write-time. T4.SB closer arc IN-FLIGHT; Phase 13 FULLY CLOSED marker fires at T-T4.SB.6 executing-plans SHIPPED per spec §K + §1.5.2 amendment.*
