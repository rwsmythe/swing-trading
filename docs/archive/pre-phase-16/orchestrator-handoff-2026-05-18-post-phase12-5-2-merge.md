# Orchestrator handoff — 2026-05-18 (post-Phase-12.5-#2-merge; Phase 12.5 #3 commissioning queued)

You are taking over as orchestrator for the Swing Trading project at the **post-Phase-12.5-#2-merge + post-housekeeping** breakpoint. Outgoing orchestrator handed off due to **context-window pressure ahead of drafting the Phase 12.5 #3 brainstorm dispatch brief** (~300-400 line deliverable better executed with fresh window — mirrors the prior 2026-05-17 handoff pattern exactly). Phase 12.5 #2 executing-plans merged 2026-05-18 at `0cecf28`; post-merge housekeeping at `61ed9bc` (committed atomically with this brief). Your first major deliverable: **draft Phase 12.5 #3 brainstorm dispatch brief + inline implementer-dispatch prompt**.

**HOUSEKEEPING COMPLETED 2026-05-18 by outgoing orchestrator** (per orchestrator-context.md §"Session-end checklist" — outgoing-owned):
- `CLAUDE.md` status-line PARAGRAPH — appended Phase 12.5 #2 executing-plans SHIPPED entry at `0cecf28`.
- `docs/phase3e-todo.md` — Phase 12.5 #2 executing-plans SHIPPED entry above writing-plans predecessor.
- `docs/orchestrator-context.md` — §"Currently in-flight work" updated with post-Phase-12.5-#2-merge state + Phase 12.5 #3 dispatch readiness.

## ⚠ Critical bootstrap framing

**claude-mem may still be DISABLED** for the operator's evaluation window (started 2026-05-10). Auto-memory dir (`~/.claude/projects/c--Users-rwsmy-swing-trading/memory/MEMORY.md` + linked files) IS still loaded.

**3 memory entries banked 2026-05-17 PM** (load-bearing for this orchestrator; inherited from prior handoff):
- `feedback_pause_means_pause.md` — when operator says pause, STOP all forward motion immediately, even items appearing independently confirmed.
- `feedback_worktree_cli_invocation.md` — at worktree-side gates, `swing` routes to editable-install path NOT worktree code. Use `python -m swing.cli` from worktree cwd.
- `feedback_time_estimates_overstated.md` — orchestrator wall-clock estimates are 3-5x too long; divide naive estimates by 3-5x.

**Operator dispatches implementers themselves** (per durable preference). Orchestrator drafts brief + provides inline dispatch prompt as fenced code block.

**Always provide an inline dispatch prompt** with every brief.

**Commit brief BEFORE inline dispatch prompt.**

**One command at a time on production writes; inline-batched OK on reads/tests.**

**NO Claude co-author footer.** Cumulative streak now ~163+ commits ZERO drift across Phase 11/12/post-Phase-12/Phase-12.5 chains via explicit citation in dispatch prompts. **Pattern is durable. DO NOT regress.**

**Once operator-witnessed gate passes, integration merge is orchestrator action.**

**Pre-Codex orchestrator-side review (NEW C.C lesson #6) — BINDING.** Before invoking `copowers:adversarial-critic` in any executing-plans/writing-plans/brainstorm dispatch, dispatch a focused reviewer subagent with binding contracts as anchors; ask for deviation list ≤300-600 words. Validated 4x cumulatively (C.C + C.D + Phase 12.5 #1 + Phase 12.5 #2 E1 lesson absorbing 1 Major-class finding pre-chain).

## Step 1 — Read these in order

1. **This brief end-to-end** — captures Phase 12.5 #2 ship outcome + Phase 12.5 #3 dispatch readiness.

2. **`docs/phase3e-todo.md`** — Phase 12.5 #2 SHIPPED entry at top + Phase 12.5 #1 SHIPPED + Phase 12.5 RESCOPED entry + Phase 13 scope-brainstorm IN PROGRESS. **Phase 12.5 #3 scope was operator-locked 2026-05-17** as 5 items (per CLAUDE.md status-line): (a) CLAUDE.md+orchestrator-context archive-split; (b) V2.1 §VII.F amendment batch (now ~30+ pending including Phase 12.5 #2's NEW A1+A2+A3); (c) Phase 8 walkthrough failing-test triage; (d) Ruff 18 E501 cleanup; (e) Phase 12.5 #1 architectural inconsistency (plan §H.4 tier-3-override-no-clear semantic vs shipped helper SQL).

3. **`CLAUDE.md` status-line** — currently includes Phase 12.5 #2 executing-plans SHIPPED entry at `0cecf28`. **Cap-drift compounding** (~60+ entries vs ~30 cap; Phase 12.5 #3 absorbs the archive-split).

4. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Lessons captured" — current-state pointer + ~50+ cumulative forward-binding lessons in the active section; older lessons in `docs/orchestrator-context-archive.md`.

5. **`docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-executing-plans-return-report.md`** — Phase 12.5 #2 return report. Especially §1 commit breakdown (17 commits incl. orchestrator-inline gate-fix `25f4554`); §6 5 NEW forward-binding lessons L-E1..L-E5; §13 cross-bundle dependency closure (Sub-bundle B T-B.7).

6. **`docs/superpowers/specs/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-design.md`** + **`docs/superpowers/plans/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-plan.md`** — Phase 12.5 #2 spec (721 lines) + plan (1082 lines). Read for Phase 12.5 #3 scoping references on web-route shape + base-layout VM retrofit pattern.

7. **`docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-brainstorm-dispatch-brief.md`** — Phase 12.5 #1 brainstorm dispatch brief (339 lines; closest format precedent for Phase 12.5 #3 brainstorm brief if you draft one).

8. **`docs/phase13-scope-brainstorm.md`** — Phase 13 scope-brainstorm (operator-locked 2026-05-17 + amended 2026-05-18 with T1.SB0 OhlcvCache→_step_charts prerequisite). Phase 12.5 #3 is the LAST Phase 12.5 dispatch before Phase 13 commission.

## Step 2 — Standard bootstrap verification

```bash
git log --oneline -10                       # expect post-merge HEAD
git status                                  # expect clean
git worktree list                           # expect main + 6 husks pending operator cleanup
python -m pytest -m "not slow" -q -n auto | tail -5   # expect ~4847 fast + 3 pre-existing phase8 walkthrough failures + 5 skipped
ruff check swing/ --statistics | tail -3    # expect 18 E501
```

Expected state on main HEAD `0cecf28+housekeeping`:
- **Phase 12.5 #2 SHIPPED** (17 commits; ZERO ACCEPT-WITH-RATIONALE on Majors; ZERO Co-Authored-By footer drift; +135 fast tests).
- **Production state**: 4 pending-ambiguity discreps remaining (54+55+56+57 DHC+VSAT family); banner count 4 (down from 6 pre-gate).
- **6 worktree husks** pending operator cleanup-script pass (3 Phase 12.5 #1 + 1 finviz-fix + 2 Phase 12.5 #2 brainstorm + writing-plans + 1 new executing-plans).

## Step 3 — Current state + Phase 12.5 #3 dispatch readiness

### §3.1 Phase 12.5 #3 scope LOCK (operator-locked 2026-05-17)

Per phase3e-todo Phase 12.5 RESCOPED entry — Phase 12.5 #3 is the **project hygiene maintenance pass**:

1. **CLAUDE.md + orchestrator-context archive-split** — status-line at ~60+ entries vs ~30 cap; Phase 12.5 #3 splits older SHIPPED entries to `docs/phase3e-todo-archive.md` companion + bumps cap if needed.
2. **V2.1 §VII.F amendment batch** — ~30+ pending amendments across all prior Phase 9/10/11/12/12.5 dispatches (some explicit; some banked at return reports). Phase 12.5 #2 added A1+A2+A3 = 3 NEW.
3. **Phase 8 walkthrough failing-test triage** — 3 pre-existing `tests/integration/test_phase8_pipeline_walkthrough.py` failures unchanged since Phase 8 ship; banked at every gate since C.A. Phase 12.5 #3 investigates root cause + fixes OR documents as accepted-as-is.
4. **Ruff 18 E501 cleanup** — long-standing 18 E501 errors carried across all dispatches. Phase 12.5 #3 mechanical cleanup OR ratchet-up via `noqa` + add to baseline tracking.
5. **Phase 12.5 #1 architectural inconsistency** — plan §H.4 tier-3-override-no-clear semantic vs shipped helper SQL (banner clears immediately when override flips `resolved_by` from `auto_tier1_multi_leg`). Phase 12.5 #3 either amends plan/spec text OR ships a code fix to preserve banner mid-window.

### §3.2 Phase 12.5 #3 dispatch shape options

Two reasonable structures the brainstorm can lock:

**Option A — Single brainstorm + plan + executing dispatch (mirrors Phase 12.5 #1 + #2):**
- Brainstorm (~500-800 line spec; 3-5 Codex rounds): scopes the 5-item maintenance pass + decomposes into sub-bundles if needed.
- Writing-plans (~500-800 line plan; 3-5 Codex rounds): per-task acceptance criteria + test projection.
- Executing-plans (3-5 Codex rounds): ship.

**Option B — Skip brainstorm; go straight to writing-plans (low-architectural-risk maintenance):**
- Phase 12.5 #3 items are mostly mechanical/text-edit operations + 1 small code fix (item #5 if code-fix path chosen).
- Architectural ambiguity is LOW relative to Phase 12.5 #1 (multi-leg auto-redirect; substantive architecture) or Phase 12.5 #2 (web Tier-2 surface; new routes).
- Direct writing-plans dispatch with operator-pre-locks on the 5 items + execution-plans dispatch follows.

**Recommendation**: ask operator which structure. If item #5 is locked at "amend plan/spec text only" then Option B is right; if it's "ship a code fix" then Option A's brainstorm could be useful to scope the code change.

### §3.3 Cap-drift maintenance specifics (item #1 details)

- `CLAUDE.md` status-line: ~60+ entries. Cap targets in `docs/orchestrator-context.md` §"Maintenance: retention discipline" suggest ~30 entries active + rest in archive.
- `docs/phase3e-todo.md` active section grew with Phase 12.5 #1 SHIPPED + finviz-fix SHIPPED + Phase 12.5 #2 brainstorm/writing-plans/executing-plans SHIPPED entries (5 new active entries this session).
- `docs/orchestrator-context.md` §"Currently in-flight work" has prior-state preservation pattern (each new entry preserves the prior state below for historical context); growing 200-300 line per major dispatch.
- Archive companion files exist: `docs/phase3e-todo-archive.md` + `docs/orchestrator-context-archive.md` per CLAUDE.md "Archive companion (2026-05-05)" + `Retention discipline + archive-split trigger documented in docs/orchestrator-context.md §"Maintenance: retention discipline"`.

### §3.4 Operator-pending items pre-Phase-12.5-#3-dispatch

- **`cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass — 6 worktree husks**:
  - `.worktrees/phase12-5-bundle-1-oqf-brainstorm/`
  - `.worktrees/phase12-5-bundle-1-oqf-writing-plans/`
  - `.worktrees/phase12-5-bundle-1-oqf-executing-plans/`
  - `.worktrees/phase12-5-finviz-inbox-auto-fetch-fix/`
  - `.worktrees/phase12-5-bundle-2-web-tier2-brainstorm/`
  - `.worktrees/phase12-5-bundle-2-web-tier2-writing-plans/`
  - `.worktrees/phase12-5-bundle-2-web-tier2-executing-plans/` (7th, just from this session)
- All match cleanup-script regex `phase\d+[-_]`. Operator-paced; NOT orchestrator-blocking.
- **4 pending-ambiguity discreps** (54+55+56+57; DHC+VSAT `unmatched_open_fill` family from runs #67+#68) — operator continues dispositioning via `swing journal discrepancy resolve-ambiguity` CLI OR the new web `/reconcile/discrepancy/{id}/resolve` surface (just shipped via Phase 12.5 #2). Per C.D-cleanup precedent: `acknowledge` per Pass-1 Pass-2-tier-1-FORBIDDEN-V2-deferred family.
- **Schwab refresh-token clock** healthy (expires ~2026-05-24T06:40). Routine `/schwab/setup` re-auth.

## Step 4 — Operator preferences (durable; carry over)

- Implementer-dispatch is the default.
- Once gate passes, integration merge is orchestrator action (do NOT ask "shall I merge").
- Worktree-isolated dispatch briefs MUST specify `.worktrees/<branch>/` path explicitly.
- Implementer runs adversarial-critic via `copowers:executing-plans` (or `copowers:writing-plans` / `copowers:brainstorming`) wrapper.
- AskUserQuestion preferred for design decisions; "Other" option provided automatically.
- Always provide inline dispatch prompt with every brief.
- Commit brief BEFORE inline prompt.
- Operator-paired-gate driving — ONE COMMAND AT A TIME on production writes; inline-batched OK on reads/tests.
- Explicit `Co-Authored-By` footer suppression in dispatch prompts (durable; passive CLAUDE.md inheritance insufficient).
- Pre-Codex orchestrator-side review for executing-plans/writing-plans/brainstorm dispatches (NEW C.C lesson #6 — BINDING; validated 4x cumulatively).
- **Pause means pause** (`feedback_pause_means_pause.md` durable).
- **Worktree CLI invocation**: `python -m swing.cli` from worktree cwd, NOT `swing` (`feedback_worktree_cli_invocation.md` durable).
- **Time estimates 3-5x too long** — divide naive estimate by 3-5x for operator-paced wall-clock.
- **Outgoing orchestrator owns session-end housekeeping** per orchestrator-context.md self-documented usage.

## Step 5 — Cumulative streaks to preserve

- **ZERO `Co-Authored-By` footer drift**: ~163+ commits cumulative across Phase 11/12/post-Phase-12/Phase-12.5 chains. Streak is durable; explicit citation in dispatch prompts is the discipline. DO NOT regress.
- **ZERO ACCEPT-WITH-RATIONALE on Majors** since Phase 12.5 #1 brainstorm: clean across Phase 12.5 #1 brainstorm + writing-plans + executing-plans + Phase 12.5 #2 brainstorm (1 banked R1 M#4 surface attribution; pseudo-clean — see CLAUDE.md status-line for nuance) + writing-plans + executing-plans (1 Minor accepted as advisory; clean on Majors).
- **Schema v19 UNCHANGED** since Phase 12 Sub-sub-bundle C.A 2026-05-15: 3+ Phase 12.5 dispatches consumer-side-only. F1 LOCK preserved every dispatch. Phase 12.5 #3 expected to also preserve (mechanical/text-edit + 1 small code fix).
- **Ruff 18 E501** baseline carried across all dispatches; Phase 12.5 #3 item #4 may finally clear this.

## Step 6 — Pending operator-action items (NOT orchestrator-blocking)

- **Worktree husks** pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass (7 worktrees enumerated in §3.4).
- **4 pending-ambiguity discreps** to disposition (now resolvable via web OR CLI surface; Phase 12.5 #2 just shipped operator's preferred web surface).
- **Schwab refresh-token clock**: healthy (expires ~2026-05-24T06:40). Routine re-auth via `/schwab/setup` if hitting Schwab API endpoints.
- **~30+ V2.1 §VII.F amendments cumulative pending** (Phase 12.5 #3 maintenance pass absorbs).

## Do NOT

- Re-litigate Phase 12.5 #1 + #2 outcomes (both SHIPPED + merged).
- Re-litigate Phase 12.5 scope (3 items; locked).
- Re-litigate Phase 13 scope (4 themes / 10 sub-bundles + T1.SB0 OhlcvCache prerequisite; locked at `docs/phase13-scope-brainstorm.md` §0.5 + 2026-05-18 amendment).
- Dispatch Phase 12.5 #3 before drafting + committing the brief + providing inline prompt.
- Skip the explicit Co-Authored-By footer suppression citation in dispatch prompts.
- Run any new production-write actions without explicit operator pre-authorization.

## Step 7 — Suggested orchestrator flow (your first session)

1. Read this brief end-to-end + Phase 12.5 #2 executing-plans return report + Phase 12.5 #1 brainstorm dispatch brief precedent (Step 1 reading order).
2. Run Step 2 bootstrap verification.
3. **Ask operator: Option A (full brainstorm + writing-plans + executing-plans for Phase 12.5 #3) OR Option B (skip brainstorm; go straight to writing-plans)** per §3.2 above.
4. If Option A: draft Phase 12.5 #3 brainstorm dispatch brief at `docs/phase12-5-bundle-3-project-hygiene-brainstorm-dispatch-brief.md` (~300-400 lines; mirror Phase 12.5 #1 brainstorm brief precedent).
5. If Option B: draft Phase 12.5 #3 writing-plans dispatch brief directly (~200-300 lines; reference the 5 operator-locked scope items at §3.1 above).
6. Commit + push brief.
7. Provide inline implementer-dispatch prompt for Phase 12.5 #3 first phase (brainstorm OR writing-plans) as fenced code block.
8. Operator commissions implementer.

---

*End of handoff brief. Post-Phase-12.5-#2-merge orchestrator transition. Main HEAD `0cecf28+housekeeping`; 5 Phase 12.5 dispatches CLOSED in this session arc (Phase 12.5 #1 + finviz-fix + Phase 12.5 #2 brainstorm + writing-plans + executing-plans); production state clean (4 pending-ambiguity discreps for operator dispositioning); Phase 12.5 #3 dispatch brief drafting UNBLOCKED — your first major deliverable. Operator-paced.*
