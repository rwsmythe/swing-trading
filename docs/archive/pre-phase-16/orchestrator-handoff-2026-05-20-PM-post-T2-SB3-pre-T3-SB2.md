# Orchestrator handoff — 2026-05-20 PM (post-T2.SB3 SHIPPED + housekeeping; pre-T3.SB2 dispatch)

You are taking over as orchestrator for the Swing Trading project at the **post-T2.SB3-SHIPPED + housekeeping + pre-T3.SB2-dispatch** breakpoint. Clean state; ZERO in-flight orchestrator work. Outgoing orchestrator handed off at 28% context budget after shipping 5 sub-bundles in one session.

**main HEAD AT HANDOFF**: `368784f` (T2.SB3 post-merge housekeeping; pushed to origin).

**WORKING DIRECTORY**: `c:\Users\rwsmy\swing-trading`

**CRITICAL FIRST TASK**: Commission T3.SB2 dispatch brief (exit auto-fill via Schwab Trader API; 5 tasks per plan §G.5). See §2.

---

## §0 Critical bootstrap framing

**Memory entries inherited (all BINDING; load-bearing across recent handoffs)**:
- `feedback_pause_means_pause.md` — when operator says pause, STOP all forward motion immediately.
- `feedback_worktree_cli_invocation.md` — `python -m swing.cli` from worktree cwd, NOT bare `swing`.
- `feedback_time_estimates_overstated.md` — orchestrator wall-clock estimates 3-5x too long; divide by 3-5x for operator-paced.
- `feedback_orchestrator_qa_implementer_product.md` — orchestrator MUST QA every implementer product before merge; verify against reality on disk; don't merely summarize self-report. **BINDING** (now validated 18x+ cumulatively across Phase 12 + 12.5 + 13 arcs).
- `feedback_orchestrator_performs_merge.md` — merge + push + post-merge housekeeping = orchestrator action; do NOT ask "shall I merge".
- `feedback_orchestrator_vs_implementer_execution.md` — default to implementer-dispatch for context budget; orchestrator-inline only for orchestration work.
- `feedback_always_provide_inline_dispatch_prompt.md` — every brief gets an inline dispatch prompt as fenced code block.
- `feedback_commit_brief_before_inline_prompt.md` — commit the brief BEFORE providing inline prompt.
- `feedback_regression_test_arithmetic.md` — when specifying tests in orchestrator briefs, compute values under both pre-fix and post-fix paths.

**Operator dispatches implementers themselves** (durable). Orchestrator drafts brief + provides inline implementer-dispatch prompt as fenced code block.

**NO Claude co-author footer.** Cumulative streak **~263+ commits ZERO trailer drift** through T2.SB3 housekeeping. Pattern is DURABLE. DO NOT regress. Explicit citation in commit messages required:

> Per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15): do NOT add `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (or any other Co-Authored-By footer attributing the AI assistant) to ANY commit message.

**Pre-Codex orchestrator-side review (C.C lesson #6) — BINDING. 18x cumulative CLEAN through T2.SB3.** 19th validation expected at T3.SB2 + downstream dispatches.

**Size-check trigger discipline** at `docs/orchestrator-context.md` §"Maintenance: retention discipline" §"Size-check trigger at housekeeping-commit time". Soft thresholds:
- CLAUDE.md line 3: >2,000 chars → trim back.
- orchestrator-context.md "Prior state" sub-sections: >10 retained → archive oldest.
- orchestrator-context.md "Lessons captured": >40 entries → migrate oldest 5-10.
- phase3e-todo.md SHIPPED entries: >25 retained → archive-split.

**Prior state count post-this-housekeeping is 10 (at cap).** Next housekeeping demote will trigger archive-split.

---

## §1 Read these in order

1. **This brief end-to-end** — captures session-arc summary + T2.SB3 SHIPPED outcomes + T3.SB2 dispatch readiness.

2. **`CLAUDE.md`** line 3 (status line) — current state reflects HEAD `368784f` (T2.SB3 housekeeping); 5257 fast / 0 ruff E501 / schema v20 / production ZERO open discrepancies; T3.SB2 dispatch UNBLOCKED.

3. **`docs/phase3e-todo.md`** top entry — T2.SB3 SHIPPED with full 14-commit chain + Codex chain shape + S2/S3 gate results + 3 forward-binding lessons + 2 NEW V2 candidates banked.

4. **`docs/orchestrator-context.md`** — "Currently in-flight work" current state + 10 Prior states + "Lessons captured" + "Maintenance: retention discipline".

5. **`docs/phase13-t2-sb3-return-report.md`** (on main; merged from worktree) — 290-line T2.SB3 final return report; §4 lists 3 forward-binding lessons for T3.SB2/T2.SB4 inheritance.

6. **Plan §G.5 T3.SB2 dispatch sequence** at `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` lines 1736-1880 (estimate) — exit auto-fill 5-task scope.

7. **Phase 13 T3.SB1 dispatch brief + return report** at `docs/phase13-t3-sb1-*.md` — T3.SB1's Schwab integration discipline + 4 ACCEPT-WITH-RATIONALE banks; T3.SB2 inherits the discipline verbatim (entry → exit symmetry).

---

## §2 ⚠ CRITICAL FIRST TASK — Commission T3.SB2 dispatch brief

### §2.1 Scope

**T3.SB2 = Exit auto-fill via Schwab Trader API at trade-exit form-render time.** Per plan §G.5; 5 tasks; sequenced AFTER T2.SB3 per plan §H.1 dispatch sequence. Mirror-symmetric to T3.SB1 (entry auto-fill) which shipped at `48c6bc6` per OQ-12 Option E concurrent dispatch.

**Branch**: `phase13-t3-sb2-exit-auto-fill`. Branches from main HEAD `368784f` at dispatch time.

### §2.2 Inherited forward-binding obligations

**From T2.SB3 return report §4 (banked at `368784f` housekeeping)** — T3.SB2 inherits 3 lessons verbatim:
1. **`EvalRunResolutionError` typed-exception precedent** — any step that DERIVES asof_date from a pipeline-run anchor (NOT wall-clock) inherits the pattern: raise on missing/malformed via `_resolve_eval_run_action_session_date(conn, eval_run_id)`; defensive best-effort wrapper catches + skips. **T3.SB2 exit auto-fill MUST honor this when deriving exit-anchor session_date** (e.g., for OHLCV bar query at exit time; for audit-row stamping).
2. **Bar-clipping discipline at detector entry** — applies to any exit-time bar-consuming logic: clip `bars` to `bars.index <= exit_anchor_date` BEFORE downstream extraction. Symmetric to detector clip pattern shipped at T-A.3.4 cup_with_handle.
3. **Two-pass-then-reconcile-then-serialize architectural pattern** — applies if T3.SB2 emits multiple rows with cross-row dependencies (likely N/A for exit auto-fill since exit is per-fill, but verify at recon).

**From T3.SB1 return report (entry-side precedent; T3.SB2 inherits Schwab integration discipline verbatim)**:
- `apply_overrides(cfg)` at handler entry
- `resolve_credentials_env_or_prompt(allow_prompt=False)` BINDING (form-render-time prompts would block HTTP handler)
- `construct_authenticated_client(cfg, environment, client_id, client_secret)` 4-arg signature
- `trader.get_account_orders(surface='trade_exit')` — surface CHECK already widened at v20 to include `trade_exit` per T2.SB1 T-A.1.1 migration
- HTMX gotcha trinity (hx-headers propagation + HX-Redirect target registered + success-path 204 + HX-Redirect not 303-swap)
- Base-layout VM banner pin
- Sandbox + DEGRADED + PROVISIONAL short-circuits BEFORE Schwab client construction
- Hidden anchor 4-tier rejection ladder + `claimed_auto_fill` anti-forgery gate
- Recovery form anchor-clear discipline on 400 responses
- Schema-version-aware INSERT for newly-widened columns (already covered at T3.SB1 via `swing/data/repos/fills.py:51-53`)

**From T2.SB1 forward-binding lesson #8 (still V2-bankable)**:
- Cup-with-handle rounded-vs-V hard gate — N/A for T3.SB2 (exit auto-fill doesn't run detectors).

### §2.3 Cross-bundle pin un-skip schedule at T3.SB2

Per plan §H.3, T3.SB2 merge un-skips:
- `test_v20_migration.py:907` — "Cross-bundle pin per plan G.1 T-A.1.1 — un-skip at T3.SB2 merge (verifies fill_origin enum fully populated through T3.SB1 + T3.SB2 entry/exit auto-fill paths)"

T3.SB2 closer MUST remove the `@pytest.mark.skip` decorator at this line per LOCK precedent (T-A.3.9 cross-bundle pin un-skip is the canonical example from T2.SB3).

### §2.4 Brief drafting workflow

Mirror the T2.SB3 brief shape (`docs/phase13-t2-sb3-detectors-batch1-dispatch-brief.md`; 241 lines):

1. **§1 Scope summary** — brief intro + inheritance from T2.SB3 + T3.SB1 forward-binding lessons.
2. **§2 Per-task acceptance criteria** — 5 tasks T-B.2.1 through T-B.2.5 (or naming per plan §G.5 verbatim).
3. **§3 Files in scope** — likely modify: `swing/web/routes/trades.py` (extend `/trades/{id}/exit/form` GET + POST with auto-fill) + `swing/trades/exit_auto_fill.py` (NEW service module; mirror entry_auto_fill.py shape) + `swing/web/templates/partials/trade_exit_form.html.j2` (NEW or extend) + `swing/web/view_models/trades.py` (extend ExitFormVM with auto-fill anchor fields).
4. **§4 Watch items** — Schwab integration discipline (T3.SB1 verbatim) + `EvalRunResolutionError` precedent + bar-clipping + cross-bundle pin un-skip + cumulative process discipline.
5. **§5 Done criteria** — S1 inline (pytest + ruff + schema + trailer + Codex NO_NEW_CRITICAL_MAJOR) + S2 operator-paired (browser exercise of `/trades/{id}/exit/form` with Schwab auto-fill).
6. **§6 LOCKs** — branch base `368784f` + ZERO DB writes inside exit_auto_fill service (if applicable) + NO INSERT OR REPLACE on `fills` writes + cross-bundle pin un-skip BINDING.
7. **§7 Reference materials** — plan §G.5 + T3.SB1 dispatch brief + T3.SB1 return report + CLAUDE.md gotchas (HTMX trinity + hidden anchor 4-tier rejection + recovery form anchor-clear).
8. **§8 Post-dispatch housekeeping checklist** — CLAUDE.md line 3 refresh + phase3e-todo entry + orchestrator-context refresh + archive-split (Prior count is 10 at cap; demote will trigger).
9. **§9 Forward-binding to T2.SB4 + T2.SB5** — what T3.SB2 surfaces lessons-wise.

**Brief target length**: ~250-300 lines. T3.SB2 is mid-sized (5 tasks) — smaller than T2.SB3 (9 tasks); brief should be tighter.

### §2.5 Commit + push + inline prompt

After drafting:
1. `git add docs/phase13-t3-sb2-exit-auto-fill-dispatch-brief.md`
2. `git commit -m "docs(phase13): T3.SB2 exit auto-fill dispatch brief\n\n[body]\n\nPer fresh forward-binding lesson #7 ..."`
3. Verify empty trailer
4. `git push origin main`
5. Provide inline implementer dispatch prompt as fenced code block for operator copy/paste (per `feedback_always_provide_inline_dispatch_prompt`).

---

## §3 Session-arc summary (this 2026-05-20 session)

**5 sub-bundles SHIPPED this session** across 12 commits to origin/main:

| # | Sub-bundle | Merge SHA | Codex chain | C.C lesson #6 | Notable |
|---|---|---|---|---|---|
| 1 | T2.SB1 (dev-time labeling infra + v20 schema + T-A.1.7 corpus) | `b00597c` | 3 rounds R2 NO_NEW_CRITICAL_MAJOR + R3 CLEAN | 16th | Schema v20 LANDED at T-A.1.1 (`4cfd5f2`); concurrent with T3.SB1 per OQ-12 Option E |
| 2 | T3.SB1 (entry auto-fill via Schwab Trader API) | `48c6bc6` | 5 rounds R5 NO_NEW_CRITICAL_MAJOR with 4 TECHNICALLY SOUND ACCEPT banks | 14th | Branched off T2.SB1's T-A.1.1 SHA |
| 3 | T2.SB2 (foundation primitives) + T-PT9 (Phase-9 calendar-drift fix) | `c15633d` | 2 rounds R2 NO_NEW_CRITICAL_MAJOR with 3 TECHNICALLY SOUND ACCEPT banks | 17th | T-PT9 closed 2 pre-existing Phase-9 failures; `is_back_recorded` LOCK L3 UNTOUCHED |
| 4 | (housekeeping commits between merges: `2746bbb` + `71739ed`) | — | — | — | 9 CLAUDE.md gotchas added at `2746bbb`; `is_back_recorded` mis-framing RETRACTED at `71739ed` |
| 5 | T2.SB3 (detectors batch 1: VCP + flat_base + cup_with_handle + drift_logging + `_step_pattern_detect`) | `e3d34a9` | 5 rounds R5 NO_NEW_CRITICAL_MAJOR with 1 TECHNICALLY SOUND ACCEPT bank | 18th | Cross-bundle pin un-skip CONFIRMED; S2 + S3 gates PASS (orchestrator-driven gold corpus cross-check) |

**Test baseline progression**: 4939 (pre-session) → 5092 (post-T2.SB1) → 5149 (post-T3.SB1) → 5183 (post-T2.SB2+T-PT9) → 5257 (post-T2.SB3) = +318 cumulative across session.

**Schema progression**: v19 → v20 (LANDED at T-A.1.1 `4cfd5f2` during T2.SB1; UNCHANGED since).

**Operator decisions resolved this session**:
- ✅ T2.SB1 + T3.SB1 S2/S3 gates PASS
- ✅ Phase-9 TZ-drift fix → batched with T2.SB2 as T-PT9
- ✅ T-A.1.6 Deficiency 1 → folded into T2.SB6 as new task T-A.6.6b
- ✅ Metrics-dashboard hooked-up audit → folded into T4.SB as new task T-D.6b
- ✅ T2.SB2 S2 gate PASS
- ✅ T2.SB3 S2 + S3 gates PASS

**4 NEW V2 candidates banked across the session**:
- `swing data fetch <ticker>` convenience CLI wrapping `OhlcvCache.get_or_fetch` for ad-hoc operator data (banked at T2.SB2 housekeeping)
- R5 stale-comments at `swing/pipeline/runner.py:1510-1519` (banked at T2.SB3 housekeeping; advisory only)
- Cup-with-handle criterion_2 sub-condition investigation (banked at T2.SB3 housekeeping from S3 gold corpus finding: COST + MSFT cup_depth IN spec range but criterion_2 fails algorithmically)
- Multi-anchor candidate window iteration per pattern_class (banked at T2.SB3 return report §6.4)

---

## §4 Phase 13 dispatch sequence forward state

Per plan §H.1 dispatch sequence + this session's shipments:

```
T1.SB0 ✅ → T2.SB1 ∥ T3.SB1 ✅✅ → T2.SB2 ✅ → T2.SB3 ✅ → T3.SB2 (NEXT) → T2.SB4 → T2.SB5 → T3.SB3 → T2.SB6 → T4.SB → CLOSED
                                                          [HERE]
```

**5 of 11 sub-bundles SHIPPED** (+ T1.SB0 gate-fix as bonus); 6 remaining.

**Estimated test deltas remaining** (per plan projections):
- T3.SB2: +40-70 fast tests (exit auto-fill; similar shape to T3.SB1's +67)
- T2.SB4: +60-100 (detectors batch 2: HTF + DBW; smaller than T2.SB3's 3-detector batch)
- T2.SB5: +50-80 (template matching DTW + 120s benchmark)
- T3.SB3: +40-70 (review auto-fill consuming OhlcvCache)
- T2.SB6: +100-150 (closed-loop surface + Theme 1 annotated charts; 8 tasks including T-A.6.6b Deficiency 1 fold-in)
- T4.SB: +50-80 (usability triage + Q4 close-tracking + T-D.6b metrics-audit; 8 tasks)

**Phase 13 close projection**: ~5500-5800 fast tests post-T4.SB closer (was 5500-5940 pre-session; closer projection refined down by ~150 given T2.SB3 actuals).

---

## §5 Cumulative streaks to preserve

- **ZERO Co-Authored-By footer trailer drift**: ~263+ commits cumulative through T2.SB3 housekeeping. ABSOLUTELY DO NOT regress. Explicit citation in commit messages + dispatch prompts is the discipline.
- **ZERO Critical findings across full Phase 13 arc to date** (T1.SB0 gate-fix + T2.SB1 + T3.SB1 + T2.SB2 + T-PT9 + T2.SB3 — all Codex chains). T3.SB1's R1 had 1 Critical (V1 threat model ACCEPT-WITH-RATIONALE for hidden-anchor JSON transport; banked V2).
- **Schema v20 LANDED at T-A.1.1**; unchanged since.
- **18x cumulative C.C lesson #6 validation CLEAN through T2.SB3**. 19th expected at T3.SB2.
- **Pre-Codex orchestrator-side review BINDING**: 19th+ validation expected at every new dispatch.

---

## §6 Operator-pending items (NOT orchestrator-blocking)

- **Worktree husks pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass**: `phase13-t2-sb1-dev-time-labeling-infra` + `phase13-t3-sb1-entry-auto-fill` + `phase13-t2-sb2-foundation-primitives` + `phase13-t2-sb3-detectors-batch1` (4 husks; all merged and ready for cleanup).
- **Untracked `scripts/convert_books_pdf_to_md.py`** (carried across multiple handoffs; operator-decision-pending; not blocking).
- **Untracked `tmp/phase13-labeling/`** in T2.SB1 worktree (operator's T-A.1.7 paired-session artifacts; preserved for fixture provenance; not blocking).
- **Schwab refresh-token clock**: per the orchestrator's last `swing schwab status` check 2026-05-20T16:00 — refresh-token valid until `2026-05-24T06:40` (~3d 4h remaining at handoff). Operator runs `swing schwab status --environment production` to check; renew via `/schwab/setup` web OR `swing schwab logout` → `swing schwab setup` CLI when ≤24h remaining.
- **2 NEW V2 candidates banked at T2.SB3 housekeeping** (need operator-paced V2 dispatch decision):
  - R5 stale-comments at `swing/pipeline/runner.py:1510-1519` — could fold into T4.SB usability triage closer
  - Cup-with-handle criterion_2 sub-condition investigation — could fold into T2.SB5 template-matching OR T2.SB6 closed-loop
- **Production state**: ZERO open discrepancies; baseline 5257 fast / 0 ruff E501 / schema v20.

---

## §7 Suggested first session flow

1. Read this brief + CLAUDE.md line 3 + phase3e-todo top entry + T2.SB3 return report end-to-end.
2. Read plan §G.5 T3.SB2 task list end-to-end at `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` (find via `grep -n "G\.5\|T3\.SB2\|exit auto-fill"`).
3. Read T3.SB1 dispatch brief + return report for Schwab integration discipline inheritance.
4. **Draft T3.SB2 dispatch brief** (~250-300 lines) at `docs/phase13-t3-sb2-exit-auto-fill-dispatch-brief.md`. Mirror T2.SB3 brief structure (§1 scope + §2 per-task + §3 files + §4 watch items + §5 done criteria + §6 LOCKs + §7 reference + §8 post-dispatch + §9 forward-binding).
5. Commit brief + push (NO Co-Authored-By footer; cite discipline).
6. Provide inline implementer dispatch prompt as fenced code block for operator copy/paste (per `feedback_always_provide_inline_dispatch_prompt`).
7. Await implementer return.
8. On return: QA against reality on disk + run pre-Codex orchestrator-side review (19th cumulative C.C lesson #6) + drive S2 operator-paired gate + merge + post-merge housekeeping.

---

## §8 Do NOT

- Re-litigate T2.SB3 outcomes (SHIPPED + Codex-closed + S2/S3 PASS + housekeeping committed).
- Skip pre-Codex orchestrator-side review at T3.SB2 or any future dispatch (C.C lesson #6 BINDING).
- Add Co-Authored-By footer to ANY commit (~263+ streak).
- Touch the v20 migration semantics (locked).
- Modify the T-A.1.7 corpus at `data/phase13-t2-sb1-corpus/*` (operator-validated as-is).
- Address the 2 NEW V2 candidates banked this housekeeping (R5 stale-comments + cup criterion_2 sub-condition) in T3.SB2 scope (separate V2 dispatches; operator decision pending).
- Skip size-check pre-flight before housekeeping (Prior state count is 10 at cap; archive-split WILL fire at next demote).
- Push without verifying empty Co-Authored-By trailer on the commit.

---

## §9 Quick-reference SHA roster

| Item | SHA |
|---|---|
| main HEAD at handoff | `368784f` (T2.SB3 housekeeping) |
| T2.SB3 merge | `e3d34a9` |
| T2.SB3 dispatch brief | `798fc68` |
| T2.SB2+T-PT9 housekeeping | `71739ed` |
| T2.SB2+T-PT9 merge | `c15633d` |
| T2.SB2 dispatch brief | `4da4ad2` |
| T2.SB1+T3.SB1 housekeeping | `2746bbb` |
| T3.SB1 merge | `48c6bc6` |
| T2.SB1 merge | `b00597c` |
| T-A.1.1 v20 migration (schema-landing SHA; OQ-12 Option E branch-base for T3.SB1) | `4cfd5f2` |
| T1.SB0 gate-fix merge | `d772f23` |
| Post-handoff (after T3.SB2 brief commit) | `<new SHA from your brief commit>` |

---

## §10 Forward-binding lessons surfaced this session (5 cumulative; carry forward into T3.SB2 brief + future)

1. **`EvalRunResolutionError` typed-exception precedent** (T2.SB3) — any step deriving asof_date from pipeline-run anchor (NOT wall-clock) inherits this pattern.
2. **Bar-clipping discipline at detector entry** (T2.SB3) — clip `bars` to `bars.index <= candidate_window.end_date` BEFORE downstream extraction.
3. **Two-pass-then-reconcile-then-serialize architectural pattern** (T2.SB3) — for steps emitting multiple rows with cross-row dependencies.
4. **CWD-vs-pip-editable sys.path precedence** (orchestrator S2 gate forensic) — `python -m swing.cli` with CWD=worktree puts `''` at sys.path[0]; this beats pip-editable .pth's project-root path. Verified at T2.SB3 S2 via `swing.pipeline.runner.__file__ + hasattr(r, '_step_pattern_detect')`. Useful for any future worktree-based pre-merge verification.
5. **`current_stage` short-circuits to "undefined" when conn=None inside detectors** (T2.SB3 S3 finding) — ad-hoc probe scripts that bypass the pipeline MUST pass a real sqlite3 conn + monkeypatch `current_stage` at module-level if testing detector verdict semantics. Useful for any future detector S3 cross-checks.

**Plus inherited from T2.SB1 + T3.SB1 chains** (banked at `2746bbb` + `c15633d` housekeepings; 13 cumulative forward-binding lessons across the Phase 13 arc to date).

---

## §11 Pre-Codex orchestrator-side review (C.C lesson #6 BINDING) — 19th expected at T3.SB2

Implementer dispatches focused reviewer subagent with brief's §3 file-scope + §4 watch items + §5 done criteria + §6 LOCKs as anchors BEFORE invoking Codex MCP. Verdict captured in return report. 18 prior cumulative validations CLEAN; durably effective.

---

*End of handoff brief. Post-T2.SB3-SHIPPED + housekeeping + pre-T3.SB2-dispatch orchestrator transition. T3.SB2 = exit auto-fill via Schwab Trader API; 5 tasks per plan §G.5; inherits Schwab integration discipline from T3.SB1 + 3 forward-binding lessons from T2.SB3 (EvalRunResolutionError + bar-clipping + two-pass-reconcile-serialize). ~263+ cumulative ZERO Co-Authored-By footer drift streak preserved. 18x cumulative C.C lesson #6 BANKED CLEAN; 19th expected at T3.SB2. Operator-paced.*
