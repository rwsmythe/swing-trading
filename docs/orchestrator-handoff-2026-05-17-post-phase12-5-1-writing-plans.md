# Orchestrator handoff — 2026-05-17 PM (post-Phase-12.5-#1-writing-plans-merge + post-housekeeping; executing-plans dispatch brief drafting queued)

You are taking over as orchestrator for the Swing Trading project at the **post-Phase-12.5-#1-writing-plans-merge + post-housekeeping** breakpoint. Outgoing orchestrator handed off due to context-window pressure ahead of drafting the executing-plans dispatch brief (a substantial ~300-400 line deliverable that's better executed with a fresh window). Phase 12.5 #1 writing-plans merged 2026-05-17 at `2e8b10a`; housekeeping at `de9724f`. Your first major deliverable: **draft executing-plans dispatch brief + inline implementer-dispatch prompt for Phase 12.5 #1**.

**HOUSEKEEPING COMPLETED 2026-05-17 PM by outgoing orchestrator** (per orchestrator-context.md §"Session-end checklist" + §"How to update this file" — outgoing-owned). Updated:
- `CLAUDE.md` status-line PARAGRAPH — appended Phase 12.5 #1 writing-plans SHIPPED entry at `2e8b10a`.
- `docs/phase3e-todo.md` — Phase 12.5 #1 writing-plans SHIPPED entry at top (above brainstorm SHIPPED entry).
- `docs/orchestrator-context.md` — §"Currently in-flight work" updated with post-writing-plans state + executing-plans dispatch readiness + this handoff note.

## ⚠ Critical bootstrap framing

**claude-mem may still be DISABLED** for the operator's evaluation window (started 2026-05-10). Auto-memory dir (`~/.claude/projects/c--Users-rwsmy-swing-trading/memory/MEMORY.md` + linked files) IS still loaded.

**3 memory entries banked 2026-05-17 PM** (load-bearing for this orchestrator; inherited from prior handoff):
- `feedback_pause_means_pause.md` — when operator says pause, STOP all forward motion immediately, even items appearing independently confirmed.
- `feedback_worktree_cli_invocation.md` — at worktree-side gates, `swing` routes to editable-install path, NOT worktree code. Use `python -m swing.cli` from worktree cwd.
- `feedback_time_estimates_overstated.md` — orchestrator wall-clock estimates are 3-5x too long; divide naive estimates by 3-5x.

**Operator dispatches implementers themselves** (per durable preference). Orchestrator drafts brief + provides inline dispatch prompt as fenced code block.

**Always provide an inline dispatch prompt** with every brief.

**Commit brief BEFORE inline dispatch prompt.**

**One command at a time on production writes; inline-batched OK on reads/tests.**

**NO Claude co-author footer.** Phase 12 C.B precedent + post-Phase-12 brainstorm/writing-plans/Sub-bundle-1/Sub-bundle-1.5/Sub-bundle-2/Phase-12.5-#1-brainstorm/Phase-12.5-#1-writing-plans chains ALL held the line via explicit citation in dispatch prompts (~95+ commits with ZERO drift). Pattern is durable. **DO NOT regress.**

**Once operator-witnessed gate passes, integration merge is orchestrator action.**

## Step 1 — Read these in order

1. **This brief end-to-end** — captures writing-plans ship outcome + executing-plans dispatch readiness.

2. **`docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md`** — the LOCKED plan (1230 lines). **THIS IS THE PRIMARY DISPATCH SUBSTRATE.** Read end-to-end. Especially: §A (T-1.1..T-1.11 task decomposition + acceptance criteria); §C (files-touched roster post-R5 audit); §D (14 locked decisions verbatim); §F (25 binding invariants F1-F25); §G (per-task acceptance criteria narrative); §H (operator-witnessed gate plan); §L (scaffold for executing-plans dispatch brief); §M (18 forward-binding lessons).

3. **`docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-writing-plans-return-report.md`** — writing-plans return report. Especially: §1 commit breakdown; §2 Codex round chain (R1 1C/4M/1m → R5 sealed); §5 Codex Major findings dispositions; §7 18 forward-binding lessons (12 inherited + 6 NEW L-W1..L-W6); §10 composition-surface verification (post-R5 audit-list).

4. **`docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md`** — locked brainstorm spec (1236 lines). Read for context on 4 operator-locks (§2) + 7 brainstorm-locks (§15.A) + 12 V2 candidates (§14).

5. **`docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-writing-plans-dispatch-brief.md`** — the writing-plans dispatch brief that produced the plan. Reference for the brief-format precedent.

6. **`docs/post-phase12-schwab-mapper-bundle-1-execution-grain-widening-executing-plans-dispatch-brief.md`** — POST-PHASE-12 SUB-BUNDLE 1 EXECUTING-PLANS DISPATCH BRIEF (closest format precedent for the brief you'll draft; 350 lines; ZERO ACCEPT-WITH-RATIONALE outcome). Read for brief-structure reference.

7. **`docs/post-phase12-schwab-mapper-bundle-2-schwab-status-web-counterpart-executing-plans-dispatch-brief.md`** — Sub-bundle 2 executing-plans dispatch brief (292 lines; alternative brief-format precedent; smaller scope).

8. **`CLAUDE.md` status line** — currently includes Phase 12.5 #1 writing-plans SHIPPED entry at `2e8b10a`. **Cap-drift compounding** (~55 entries vs ~30 cap; Phase 12.5 #3 maintenance pass absorbs the archive-split).

9. **`docs/phase3e-todo.md`** top entries — Phase 12.5 #1 writing-plans SHIPPED at top + brainstorm SHIPPED + Phase 12.5 RESCOPED + Phase 13 scope-brainstorm IN PROGRESS.

10. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Lessons captured" — current-state pointer + ~52+ cumulative forward-binding lessons.

## Step 2 — Standard bootstrap verification

```bash
git log --oneline -10                       # expect de9724f at HEAD
git status                                  # expect clean
git worktree list                           # expect main + phase12-5-bundle-1-oqf-brainstorm + phase12-5-bundle-1-oqf-writing-plans husks pending cleanup
python -m pytest -m "not slow" -q -n auto | tail -5   # expect ~4575 fast + 3 pre-existing phase8 walkthrough failures + 5 skipped
ruff check swing/ --statistics | tail -3    # expect 18 E501
python -c "from swing.trades.reconciliation_classifier import classify_discrepancy, ClassificationResult; print('classifier OK')"
python -c "from swing.trades.reconciliation_auto_correct import apply_tier2_resolution; print('service OK')"
python -c "from swing.trades.reconciliation_backfill import _handle_pass_2, run_backfill, format_summary_block; print('backfill OK')"
```

Expected state on main HEAD `de9724f`:
- **Phase 12.5 #1 writing-plans SHIPPED** (1230-line plan; ZERO ACCEPT-WITH-RATIONALE; ZERO Critical post-R1; ZERO footer drift).
- **Production state CLEAN** — ZERO unresolved-material discrepancies; banner count=0; ~4575 fast tests.
- **2 worktree husks** pending cleanup (`phase12-5-bundle-1-oqf-brainstorm/` + `phase12-5-bundle-1-oqf-writing-plans/`).

## Step 3 — Current state + executing-plans dispatch readiness

### §3.1 Plan §A 11-task decomposition (LOCKED)

Per plan §A (verify exact task names + acceptance criteria at plan read-time):
- **T-1.1**: `auto_redirect_recipe` field on `ClassificationResult` (default None)
- **T-1.2**: Multi-leg auto-redirect predicate (qty alignment + VWAP + per-leg consistency)
- **T-1.3**: Classifier state emission via predicate + recipe synthesis + `_orders_to_classifier_payload` helper in reconciliation_backfill.py (R3 Major #2 fix — payload conversion seam)
- **T-1.4**: Payload synthesis from `SchwabExecutionLeg[]` to `split_into_partials` payload
- **T-1.5**: `apply_tier2_resolution` override kwargs (`applied_by_override` + `correction_action_override` + `resolved_by_override`) + BOTH dispatch consumers (initial pivot + backfill `_handle_pass_2` + `run_backfill` orchestrator + `format_summary_block` renderer + `BackfillOutcome` + `BackfillSummary` per R1 Critical #1)
- **T-1.6**: Reconciliation flow-pivot dispatch of auto-redirect state
- **T-1.7**: Sandbox short-circuit at inner gated on `applied_by_override=='auto'`
- **T-1.8**: Banner field on base-layout VM + helper function + ASCII-only template text
- **T-1.9**: briefing.md +1 line for `tier1_multi_leg_redirected_count` when > 0
- **T-1.10**: `--resolved-by <value>` CLI filter on `swing journal discrepancy list` (free TEXT per F23)
- **T-1.11**: Canary observability for empty-executions case (Sub-bundle 1.5 precedent)

### §3.2 14 pre-locked decisions inherited from spec + writing-plans

Encode VERBATIM in dispatch brief §0.5 (or equivalent BINDING contracts section):
- 4 spec §2.1-§2.4 operator-locks (auto-redirect ON; all-match-within-tolerance; reuse `apply_tier2_resolution` with overrides; banner advisory only)
- 3 spec §15.B operator-locks (price_tolerance=$0.01 absolute; qty_tolerance asymmetry preserved; NO N-legs cap V1)
- 7 spec §15.A brainstorm-locks (n=1 multi-leg path via ambiguity_kind reclassification; --resolved-by CLI filter IN-BUNDLE at T-1.10; sandbox short-circuit gated; service API uses `operator_custom_payload` + new override kwargs; briefing.md +1 line; canary observability; resolved_by free TEXT)

### §3.3 25 binding invariants F1-F25

Per plan §F. 19 inherited + 6 NEW F20-F25 surfaced this dispatch:
- F20+F21: backfill-consumer wiring (both consumers MUST be wired per R1 Critical #1)
- F22: service API override-parameter contracts (default values preserve verbatim existing-behavior for manual-tier-2 path)
- F23: dataclass→dict boundary ownership (ONE task owns; consumer tests don't duck-type both shapes)
- F24: helper-function key-set stability (`_orders_to_classifier_payload` emits stable keys across ALL input branches)
- F25: spec-locked rendering text verbatim-asserted in tests (e.g., briefing.md line wording; banner template text)

### §3.4 18 forward-binding lessons in plan §M

12 inherited from brainstorm spec §16 + brainstorm return report §8 + 6 NEW writing-plans-surfaced L-W1..L-W6:
- L-W1 (R1 Critical #1): Dispatcher pattern + recipe consumption — enumerate EVERY dispatcher consumer; initial pivot's source_payload derivation matters; if it returns None for unmatched sentinel, the dispatcher in that path is dead-code; operational consumer lives ELSEWHERE.
- L-W2 (R1 Major #1): Spec-locked exception-propagation contracts MUST be encoded as catch-ladder ordering in plan tasks, NOT as "PLAN DECISION" overrides.
- L-W3 (R1 Major #2): Spec-locked rendering text MUST be verbatim-asserted in tests; don't lift adjacent patterns without checking the new lock.
- L-W4 (R1 Major #3): Retrofit scope predicates MUST be enumerated by canonical mechanism (template-mount), NOT proxy field-presence.
- L-W5 (R1 Major #4): Helper functions producing normalized dicts MUST emit stable key-set across ALL input branches.
- L-W6 (R1 minor #1): Conversion seams (dataclass→dict at module boundary) MUST be owned by ONE task with clear contract.

### §3.5 Executing-plans dispatch brief drafting (YOUR FIRST MAJOR DELIVERABLE)

Target output: `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-executing-plans-dispatch-brief.md` (mirror Sub-bundle 1 executing-plans dispatch brief at `e2a11bf` shape; target ~300-400 lines).

Key elements to cover:
1. **Mission + duration estimate** (calibrated 3-5x per `feedback_time_estimates_overstated.md`): ~6-10 hr implementation + ~2-4 hr Codex chain + 4-6 surface operator-witnessed gate. Total **~2-3 days operator-paced**.
2. **§0 Inputs**: plan + brainstorm spec + writing-plans return report references; project state baselines (test count + ruff + schema); 11-task scope summary; 14 pre-locked decisions; 18 forward-binding lessons; 25 binding invariants F1-F25.
3. **§1 Worktree + binding conventions**: branch `phase12-5-bundle-1-oqf-executing-plans` (matches `phase\d+[-_]` regex); worktree `.worktrees/phase12-5-bundle-1-oqf-executing-plans/`; marker-file workflow; commit conventions per plan §A commit message stems; **NO Co-Authored-By footer**; TDD per task.
4. **§2 Adversarial review (Codex)**: 3-5 rounds projected per plan §A.0; watch items per plan §F invariants + plan §M lessons.
5. **§3 Operator-witnessed verification gate**: 4-6 surfaces per plan §H (S1 pytest + S2 production schwab fetch via `swing schwab fetch --orders` worktree-side + S3 banner field visibility + S4 briefing.md line + S5 ruff).
6. **§4 OUT OF SCOPE**: per plan §L + spec §14 V2 candidates (12 banked).
7. **§5 Return report shape**: mirror Sub-bundle 1 return report shape.
8. **§6 Dispatch metadata**: subagent-type, foreground, worktree YES, model defer-to-default.
9. **§7 If you get stuck**: schema escalation rule; HOLD-THE-LINE list (operator-locks; brainstorm-locks); pre-Codex orchestrator review discipline.

### §3.6 Operator-locked scope downstream of Phase 12.5 #1

Per phase3e-todo Phase 12.5 RESCOPED entry:
- Phase 12.5 #1 (THIS dispatch) — OQ-F multi-leg tier-1 auto-redirect
- Phase 12.5 #2 — Web Tier-2 discrepancy-resolution surface (Sub-bundle C plan §I.3 V2 candidate)
- Phase 12.5 #3 — Project hygiene maintenance pass (CLAUDE.md+orchestrator-context archive-split + V2.1 §VII.F amendment batch + Phase 8 walkthrough failing-test triage + Ruff 18 E501 cleanup)

Phase 13 scope LOCKED pending Phase 12.5 close.

## Step 4 — Operator preferences (durable; carry over)

- Implementer-dispatch is the default.
- Once gate passes, integration merge is orchestrator action (do NOT ask "shall I merge").
- Worktree-isolated dispatch briefs MUST specify `.worktrees/<branch>/` path explicitly.
- Implementer runs adversarial-critic via `copowers:executing-plans` wrapper.
- AskUserQuestion preferred for design decisions; "Other" option provided automatically.
- Always provide inline dispatch prompt with every brief.
- Commit brief BEFORE inline prompt.
- Operator-paired-gate driving — ONE COMMAND AT A TIME on production writes; inline-batched OK on reads/tests.
- Explicit `Co-Authored-By` footer suppression in dispatch prompts (durable; passive CLAUDE.md inheritance insufficient).
- Pre-Codex orchestrator-side review for executing-plans dispatches (NEW C.C lesson #6 — saved 1-2 Codex rounds on C.C + C.D + Sub-bundle 1 + Phase 12.5 #1 brainstorm).
- **Pause means pause** (`feedback_pause_means_pause.md` durable).
- **Worktree CLI invocation**: `python -m swing.cli` from worktree cwd, NOT `swing` (`feedback_worktree_cli_invocation.md` durable).
- **Time estimates 3-5x too long** — divide naive estimate by 3-5x for operator-paced wall-clock.
- **Outgoing orchestrator owns session-end housekeeping** per orchestrator-context.md self-documented usage.

## Step 5 — Cap-drift maintenance pass note

`CLAUDE.md` status line at ~55 entries vs ~30 cap; `orchestrator-context.md` active "Lessons captured" section growing past retention discipline cap. **Phase 12.5 #3 maintenance pass will handle the full archive-split**; until then, default-conservative — keep fresh lessons in active.

## Step 6 — Pending operator-action items (NOT orchestrator-blocking)

- **Worktree husks** pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass:
  - `.worktrees/phase12-5-bundle-1-oqf-brainstorm/` (from prior dispatch; still present)
  - `.worktrees/phase12-5-bundle-1-oqf-writing-plans/` (NEW; just merged)
- **Schwab refresh-token clock**: issued 2026-05-15T17:05; expires ~2026-05-22T17:05 (~3-4 days remaining at handoff). NOT blocking until executing-plans S3 production fetch surface — by then operator may need to re-auth.
- **17+ V2.1 §VII.F amendments cumulative pending** (Phase 12.5 #3 maintenance pass absorbs; ZERO new from Phase 12.5 #1 writing-plans).

## Do NOT

- Re-litigate Phase 12.5 #1 brainstorm or writing-plans outcomes (both merged).
- Re-litigate Phase 12.5 scope (3 items; locked).
- Re-litigate Phase 13 scope (4 themes / 10 sub-bundles; locked at `docs/phase13-scope-brainstorm.md` §0.5).
- Re-litigate 14 pre-locked decisions in the executing-plans dispatch brief.
- Re-litigate 25 binding invariants F1-F25.
- Dispatch executing-plans before drafting + committing the brief + providing inline prompt.
- Skip the explicit Co-Authored-By footer suppression citation in the dispatch prompt.
- Run any new production-write actions without explicit operator pre-authorization.

## Step 7 — Suggested orchestrator flow (your first session)

1. Read this brief end-to-end + the plan + return report + Sub-bundle 1 dispatch brief precedent (Step 1 reading order).
2. Run Step 2 bootstrap verification.
3. Draft executing-plans dispatch brief at `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-executing-plans-dispatch-brief.md` per §3.5 scope. Target ~300-400 lines; mirror Sub-bundle 1 brief structure.
4. Commit + push brief.
5. Provide inline implementer-dispatch prompt for Phase 12.5 #1 executing-plans as fenced code block (per durable preference).
6. Operator commissions executing-plans implementer.

---

*End of handoff brief. Post-Phase-12.5-#1-writing-plans-merge orchestrator transition. Main HEAD `de9724f`; production state clean; executing-plans dispatch brief drafting UNBLOCKED — your first major deliverable. Operator-paced.*
