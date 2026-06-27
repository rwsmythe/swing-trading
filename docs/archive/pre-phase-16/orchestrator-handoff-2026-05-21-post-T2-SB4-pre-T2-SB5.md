# Orchestrator handoff — 2026-05-21 (post-T2.SB4 SHIPPED + housekeeping; pre-T2.SB5 dispatch)

You are taking over as orchestrator for the Swing Trading project at the **post-T2.SB4-SHIPPED + housekeeping + pre-T2.SB5-dispatch** breakpoint. Clean state; ZERO in-flight orchestrator work. Outgoing orchestrator handed off after shipping **2 sub-bundles + 1 hotfix + 2 housekeeping passes** in one session.

**main HEAD AT HANDOFF**: `c44aebd` (T2.SB4 post-merge housekeeping; pushed to origin).

**WORKING DIRECTORY**: `c:\Users\rwsmy\swing-trading`

**CRITICAL FIRST TASK**: Commission T2.SB5 dispatch brief (template matching DTW + composite scoring; 6 tasks per plan §G.7; 120s/run benchmark gate per spec §5.7). See §2.

---

## §0 Critical bootstrap framing

**Memory entries inherited (all BINDING; load-bearing across recent handoffs)**:
- `feedback_pause_means_pause.md` — when operator says pause, STOP all forward motion immediately.
- `feedback_worktree_cli_invocation.md` — `python -m swing.cli` from worktree cwd, NOT bare `swing`.
- `feedback_time_estimates_overstated.md` — orchestrator wall-clock estimates 3-5x too long; divide by 3-5x for operator-paced.
- `feedback_orchestrator_qa_implementer_product.md` — orchestrator MUST QA every implementer product before merge; verify against reality on disk; don't merely summarize self-report. **BINDING** (now validated 20x+ cumulatively across Phase 12 + 12.5 + 13 arcs).
- `feedback_orchestrator_performs_merge.md` — merge + push + post-merge housekeeping = orchestrator action; do NOT ask "shall I merge".
- `feedback_orchestrator_vs_implementer_execution.md` — default to implementer-dispatch for context budget; orchestrator-inline only for orchestration work.
- `feedback_always_provide_inline_dispatch_prompt.md` — every brief gets an inline dispatch prompt as fenced code block.
- `feedback_commit_brief_before_inline_prompt.md` — commit the brief BEFORE providing inline prompt.
- `feedback_regression_test_arithmetic.md` — when specifying tests in orchestrator briefs, compute values under both pre-fix and post-fix paths.
- `project_phase13_t4_sb_pause_for_list_additions.md` — **scheduled pause AFTER Phase 13 T2.SB6 ships + housekeeping**; operator will add to T4.SB usability triage list BEFORE T4.SB brief commissioned. Surface a pause in the orchestrator update at the T2.SB6 SHIPPED + housekeeping boundary.

**Operator dispatches implementers themselves** (durable). Orchestrator drafts brief + provides inline implementer-dispatch prompt as fenced code block.

**NO Claude co-author footer.** Cumulative streak **~295+ commits ZERO trailer drift** through T2.SB4 housekeeping. Pattern is DURABLE. DO NOT regress. Explicit citation in commit messages required:

> Per fresh forward-binding lesson #7 (Phase 12 Sub-sub-bundle C.B 2026-05-15): do NOT add `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (or any other Co-Authored-By footer attributing the AI assistant) to ANY commit message.

**Pre-Codex orchestrator-side review (C.C lesson #6) — BINDING. 20x cumulative validations CLEAN through T2.SB4.** 21st validation expected at T2.SB5 with **BOTH scope expansions BINDING**:

1. **Expansion #1** (banked at T3.SB2 hotfix `cf3c489`): when widening a constant mirrored elsewhere, **grep `swing/` for redundant hardcoded copies** of the OLD tuple/enum/set + add discriminating tests that exercise each downstream consumer with the new values through the production code path (NOT mocked at a higher boundary).
2. **Expansion #2** (banked at T2.SB4 R1 M1 lesson): **cross-check dispatch brief prescriptions against spec source-of-truth at cited sections.** The T2.SB4 dispatch brief sketched the wrong cap for DBW geometric_score; pre-Codex review reading the brief alone wouldn't catch the spec divergence at §5.8 line 718 + §10.5 line 1325 — Codex caught it at R1 M1 + R2 Critical #1 cascade. Pre-Codex review templates SHOULD include "verify dispatch brief prescriptions against spec source-of-truth at the cited section" as a binding step.

**Size-check trigger discipline** at `docs/orchestrator-context.md` §"Maintenance: retention discipline" §"Size-check trigger at housekeeping-commit time". Soft thresholds:
- CLAUDE.md line 3: >2,000 chars → trim back.
- orchestrator-context.md "Prior state" sub-sections: >10 retained → archive oldest.
- orchestrator-context.md "Lessons captured": >40 entries → migrate oldest 5-10.
- phase3e-todo.md SHIPPED entries: >25 retained → archive-split.

**Prior state count post-this-housekeeping is 10 (at cap).** Next housekeeping demote will trigger archive-split (same shape as 3 prior splits in 2026-05-20+21).

---

## §1 Read these in order

1. **This brief end-to-end** — captures session-arc summary + T2.SB4 SHIPPED outcomes + T2.SB5 dispatch readiness.

2. **`CLAUDE.md`** line 3 (status line) — current state reflects HEAD `c44aebd` (T2.SB4 housekeeping); 5376 fast / 0 ruff E501 / schema v20 / production ZERO open discrepancies; 5-detector V1 set COMPLETE per L2 LOCK; T2.SB5 dispatch UNBLOCKED.

3. **`docs/phase3e-todo.md`** top entry — T2.SB4 SHIPPED with full 13-commit chain + Codex chain shape (5 rounds + 1 RESOLVED Critical) + S2 PASS + S3 disposition + 4 NEW gotchas + 7 NEW V2 candidates + 4 forward-binding lessons for T2.SB5/T3.SB3/T2.SB6 inheritance.

4. **`docs/orchestrator-context.md`** — "Currently in-flight work" current state + 10 Prior states + "Lessons captured" + "Maintenance: retention discipline".

5. **`docs/phase13-t2-sb4-return-report.md`** (on main; merged from worktree) — full T2.SB4 return report; §7 lists 4 forward-binding lessons for T2.SB5/T3.SB3/T2.SB6 inheritance + §10 documents 20th C.C lesson #6 BANKED CLEAN with scope-expanded discipline.

6. **Plan §G.7 T2.SB5 dispatch sequence** at `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` lines ~1973-2050 (estimate) — template matching DTW + composite scoring 6-task scope.

7. **Phase 13 T2.SB4 dispatch brief + return report** at `docs/phase13-t2-sb4-*.md` — T2.SB4's detector-batch + cross-bundle-pin-extension + 1 RESOLVED Critical patterns; T2.SB5 inherits 5-detector substrate verbatim (consumes their geometric_score for composite blending per spec §5.8).

8. **Phase 13 T3.SB2 hotfix at `cf3c489`** at `docs/phase13-t3-sb2-return-report.md` + `swing/integrations/schwab/trader.py:527` — the surface-guard hotfix that established C.C lesson #6 Expansion #1; T2.SB5 inherits the grep-for-hardcoded-duplicates discipline (any constant T2.SB5 widens/extends MUST grep `swing/` for downstream hardcoded copies).

---

## §2 ⚠ CRITICAL FIRST TASK — Commission T2.SB5 dispatch brief

### §2.1 Scope

**T2.SB5 = Template matching DTW (Sakoe-Chiba band) + composite scoring per spec §5.7 + §5.8 + OQ-4 + 120s/run benchmark gate.** Per plan §G.7; 6 tasks; sequenced AFTER T2.SB4 per plan §H.1 dispatch sequence (5-detector substrate now COMPLETE).

**Branch**: `phase13-t2-sb5-template-matching`. Branches from main HEAD `c44aebd` at dispatch time.

### §2.2 Inherited forward-binding obligations

**From T2.SB4 return report §7 (banked at `c44aebd` housekeeping)** — T2.SB5 inherits 4 lessons:

1. **Evidence-tier vs composite-tier score cap distinction LOCKED** — T2.SB5 introduces composite_score formula per spec §5.7 + §5.8 weighted blend. T2.SB5 MUST: (a) enumerate evidence-tier upper bounds for each of 5 detectors (DBW 1.10 with undercut bonus; others 1.0); (b) verify the composite blend correctly consumes evidence-tier + clamps to [0.0, 1.0]; (c) validate downstream `_composite_score_histogram` consumes the CLAMPED composite (not raw evidence). The T2.SB4 R2 Critical #1 fix at `runner.py:1677` is the canonical reference; T2.SB5 MUST NOT regress.
2. **Bounded backward-slice search discipline** — T2.SB5 template matching may add similar backward-search algorithms (e.g., matching template windows against historical bars); bound the search window by spec's max-duration constraints + add discriminating tests at boundary.
3. **DBW anchor_date contract via `anchor_reason.startswith("zigzag_pivot")`** — T2.SB5's template matching consumes `CandidateWindow` for each of 5 detectors; if template matching depends on `anchor_date` semantic (NOT just window extent), enforce the mode tag check explicitly.
4. **Pre-Codex review must cross-check spec source-of-truth against dispatch brief sketches** — **BINDING for T2.SB5 pre-Codex review**. When the T2.SB5 brief sketches the composite formula or DTW band parameters, the pre-Codex review MUST grep spec §5.7 + §5.8 BINDING text and verify byte-fidelity. The T2.SB4 R1 M1 / R2 Critical #1 cascade demonstrates the cost of skipping this step.

**From T2.SB3 + T2.SB4 detector substrate** (5-detector V1 set COMPLETE):
- All 5 detectors (vcp + flat_base + cup_with_handle + high_tight_flag + double_bottom_w) emit `<Detector>Evidence` dataclasses with `geometric_score` + `structural_evidence_json` fields per L2 LOCK. T2.SB5 consumes these via `pattern_evaluations` table (T-A.1.1 v20 schema; UNCHANGED).
- `pattern_evaluations.template_match_score` column was planted at T-A.1.1 with NULL pre-T2.SB5 — un-skip at T2.SB5 will populate it.
- `_pattern_detect_registry()` at runner.py is the 5-detector authoritative; do NOT widen further in T2.SB5 (template matching is a separate pipeline step OR an extension of `_step_pattern_detect` per plan §G.7 recon).

**From T3.SB2 hotfix forensic** (banked at `cf3c489` + `9899bda` housekeeping):
- The surface-guard scope-expansion discipline applied CLEAN at T2.SB4 (grep returned ZERO duplicates). For T2.SB5, if introducing a NEW constant (e.g., DTW band width tuple, template type enum, composite formula weights), apply the SAME discipline — grep `swing/` for hardcoded duplicates + verify downstream consumers.

### §2.3 Cross-bundle pin un-skip schedule at T2.SB5

Per plan §H.3 (verify before writing brief):
- `test_pattern_evaluations_template_match_score_persistable` (planted at T2.SB3 T-A.3.6; un-skips at T2.SB5) — verify the column accepts float values post-T2.SB5 implementation.
- `test_pattern_exemplars_schema_shape_invariant` (planted at T-A.1.1; un-skips at T2.SB3 + T2.SB5) — verify status; may have been un-skipped at T2.SB3 closer (verify via grep before brief).

T2.SB5 closer MUST handle un-skips per LOCK precedent (T-A.3.9 T2.SB3 cross-bundle pin un-skip + T-A.4.7 T2.SB4 cross-bundle pin extensions are the canonical examples).

### §2.4 Brief drafting workflow

Mirror the T2.SB4 brief shape (`docs/phase13-t2-sb4-detectors-batch2-dispatch-brief.md`; 235 lines):

1. **§1 Scope summary** — brief intro + inheritance from T2.SB4 + T2.SB3 + T-A.1.1 forward-binding lessons.
2. **§2 Per-task acceptance criteria** — 6 tasks per plan §G.7 verbatim.
3. **§3 Files in scope** — likely: NEW `swing/patterns/template_matching.py` (DTW + Sakoe-Chiba band) + NEW `swing/patterns/composite_scoring.py` OR extension to existing modules (verify at brief recon) + modify `swing/pipeline/runner.py:_step_pattern_detect` (extend to compute composite_score + template_match_score per row) + 2+ test files.
4. **§4 Watch items** — composite cap discipline (BOTH evidence + composite tiers documented) + DTW band parameter LOCKs per spec §5.7 + 120s/run benchmark gate + cross-bundle pin un-skip + cumulative process discipline (BOTH C.C lesson #6 expansions BINDING).
5. **§5 Done criteria** — S1 inline (pytest + ruff + schema + trailer + Codex NO_NEW_CRITICAL_MAJOR + 120s/run benchmark PASS on operator hardware) + S2 operator-paired (`python -m swing.cli pipeline run` against operator's pool; verifies template_match_score column populates) + S3 cross-check (visual on a known historical setup against benchmark wall-clock).
6. **§6 LOCKs** — branch base `c44aebd` + ZERO schema changes (v20 LOCKED) + composite cap discipline per T2.SB4 R2 C1 + 120s/run benchmark per spec §5.7 + cross-bundle pin un-skips BINDING.
7. **§7 Reference materials** — plan §G.7 + spec §5.7 + §5.8 + T2.SB4 dispatch brief + T2.SB4 return report + CLAUDE.md gotchas (evidence-tier vs composite-tier + bounded backward-slice + bar-clipping).
8. **§8 Post-dispatch housekeeping checklist** — CLAUDE.md line 3 refresh + phase3e-todo entry + orchestrator-context refresh + archive-split (Prior count is 10 at cap; demote will trigger).
9. **§9 Forward-binding to T3.SB3 + T2.SB6** — what T2.SB5 surfaces lessons-wise.

**Brief target length**: ~250-300 lines (mid-sized 6-task sub-bundle; tighter than T2.SB3's 9-task brief but covers a benchmark gate that adds discipline weight).

### §2.5 Commit + push + inline prompt

After drafting:
1. `git add docs/phase13-t2-sb5-template-matching-dispatch-brief.md`
2. `git commit -m "docs(phase13): T2.SB5 template matching DTW + composite scoring dispatch brief\n\n[body]\n\nPer fresh forward-binding lesson #7 ..."`
3. Verify empty trailer
4. `git push origin main`
5. Provide inline implementer dispatch prompt as fenced code block for operator copy/paste (per `feedback_always_provide_inline_dispatch_prompt`).

---

## §3 Session-arc summary (this 2026-05-20+21 session)

**2 sub-bundles + 1 hotfix + 2 housekeeping passes SHIPPED this session** across 32 commits to origin/main (post-cb88329 handoff):

| # | Sub-bundle / event | Merge SHA | Codex chain | C.C lesson #6 | Notable |
|---|---|---|---|---|---|
| 1 | T3.SB2 (exit auto-fill via Schwab Trader API; SELL-side mirror of T3.SB1 with multi-partial-exit via `candidates_map` envelope) | `7059945` | 5 rounds R5 NO_NEW_CRITICAL_MAJOR | 19th BANKED-WITH-CAVEAT | First operator-witnessed S2 caught critical production defect (surface-guard) that 5 Codex rounds + slow E2E missed |
| 2 | Hotfix: `_call_endpoint` surface guard widening (3 sites; 2 discriminating tests) | `cf3c489` | (in-house surgical fix; no separate Codex chain) | (housekeeping discipline expansion: grep-for-hardcoded-duplicates) | Closes Critical T3.SB1+T3.SB2 production blocker (0 trade_entry + 0 trade_exit audit rows for ~1 day post-T3.SB1 ship) |
| 3 | T3.SB2 housekeeping + script tracking | `9899bda` + `be38c17` | — | — | 4 NEW gotchas banked; orchestrator-context archive-split; convert_books_pdf_to_md.py tracked |
| 4 | T2.SB4 (HTF + DBW detectors; completes 5-detector V1 set; pipeline 3→5 extension) | `3b28d92` | 5 rounds R5 NO_NEW_CRITICAL_MAJOR with **1 RESOLVED Critical** | 20th BANKED CLEAN with scope-expanded discipline | First RESOLVED Critical in Phase 13 arc (R2 C1 composite cap to prevent DBW 1.10 evidence poisoning drift_logging histogram) |
| 5 | T2.SB4 housekeeping | `c44aebd` | — | — | 4 NEW gotchas banked; orchestrator-context archive-split; 5-detector V1 set COMPLETE per L2 LOCK |

**Test baseline progression**: 5257 (pre-session) → 5326 (post-T3.SB2 merge) → 5328 (post-hotfix) → 5376 (post-T2.SB4) = +119 cumulative across session.

**Schema progression**: v20 UNCHANGED throughout.

**Operator decisions resolved this session**:
- ✅ T3.SB2 S2-S5 gates PASS post-hotfix via Claude-in-Chrome browser automation
- ✅ Hotfix Option A approved (in-place surgical edit; no separate dispatch)
- ✅ S3 test fill_id=20 cleanup approved (DELETE + restore current_size; pre-S3 baseline restored)
- ✅ `convert_books_pdf_to_md.py` tracked
- ✅ T2.SB4 dispatch approved (next per plan §H.1)
- ✅ T2.SB4 S2 + S3 disposition: S2 PASS via orchestrator-driven probe; S3 algorithmic coverage via fast E2E + visual cross-check DEFERRED to operator-paired session

**8 NEW CLAUDE.md gotchas banked across the session**:
- T3.SB2 (3): `selected_X_audit_id` is AUDIT TRAIL not DEDUPE KEY; price-precision parity template-vs-POST; `extended.pop` for envelope keys that may not apply
- Hotfix (1): Schema-CHECK widening MUST audit ALL Python-side surface guards across the repo
- T2.SB4 (4): Evidence-tier vs composite-tier score cap distinction; bounded backward-slice search for anchor-relative detectors; DBW anchor_date contract via `anchor_reason.startswith("zigzag_pivot")`; pre-Codex review must cross-check spec source-of-truth against dispatch brief sketches

**17 V2 candidates banked across the session** (10 at T3.SB2 + 7 at T2.SB4) + 2 V2.1 §VII.F amendments banked at T2.SB4 (operator-paced decisions).

---

## §4 Phase 13 dispatch sequence forward state

Per plan §H.1 dispatch sequence + this session's shipments:

```
T1.SB0 ✅ → T2.SB1 ∥ T3.SB1 ✅✅ → T2.SB2 ✅ → T2.SB3 ✅ → T3.SB2+hotfix ✅ → T2.SB4 ✅ → T2.SB5 (NEXT) → T3.SB3 → T2.SB6 → [PAUSE FOR LIST ADDITIONS] → T4.SB → CLOSED
                                                                                            [HERE]
```

**7 of 11 sub-bundles SHIPPED** (+ T1.SB0 gate-fix + T3.SB2 hotfix as bonus events); 4 remaining (T2.SB5 + T3.SB3 + T2.SB6 + T4.SB).

**5-detector V1 set COMPLETE per L2 LOCK** — pattern detection substrate is feature-complete for V1. T2.SB5 (template matching) + T2.SB6 (closed-loop + charts) now layer on top.

**Estimated test deltas remaining** (per plan projections):
- T2.SB5: +50-80 fast tests + 1 slow (template matching DTW + 120s benchmark)
- T3.SB3: +40-70 (review auto-fill consuming OhlcvCache)
- T2.SB6: +100-150 (closed-loop surface + Theme 1 annotated charts; 8 tasks including T-A.6.6b Deficiency 1 fold-in)
- T4.SB: +50-80 (usability triage + Q4 close-tracking + T-D.6b metrics-audit; 8 tasks + operator-added items pre-dispatch)

**Phase 13 close projection**: ~5550-5750 fast tests post-T4.SB closer (refined from prior 5500-5800 estimate given T2.SB3/T2.SB4 actuals trending toward lower-bound).

---

## §5 Cumulative streaks to preserve

- **ZERO Co-Authored-By footer trailer drift**: ~295+ commits cumulative through T2.SB4 housekeeping. ABSOLUTELY DO NOT regress. Explicit citation in commit messages + dispatch prompts is the discipline.
- **ZERO Critical findings ESCAPING the Codex chain across full Phase 13 arc to date**. T3.SB1 R1 had 1 Critical (ACCEPT-WITH-RATIONALE V1 threat model; banked V2). T2.SB4 R2 had 1 Critical (RESOLVED via composite cap fix at runner.py:1677). T3.SB2 hotfix `cf3c489` closed a production-discovered Critical (surface-guard) that the Codex chain MISSED — the post-hotfix scope expansion #1 is the discipline upgrade.
- **Schema v20 LANDED at T-A.1.1**; unchanged since (4 sub-bundles + 1 hotfix later).
- **20x cumulative C.C lesson #6 validation banked through T2.SB4** (19 CLEAN + 1 BANKED-WITH-CAVEAT post-T3.SB2 hotfix forensic). **BOTH scope expansions BINDING for 21st validation at T2.SB5**.
- **5-detector V1 set COMPLETE per L2 LOCK** — milestone reached at T2.SB4 merge.
- **Pre-Codex orchestrator-side review BINDING**: 21st+ validation expected at every new dispatch.

---

## §6 Operator-pending items (NOT orchestrator-blocking)

- **Worktree husks pending operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass**: `.worktrees/phase13-t2-sb4-detectors-batch2` (the only one remaining; T3.SB2 husk was cleaned up between sub-bundles per operator's earlier confirmation).
- **Schwab refresh-token clock**: per the orchestrator's last `swing schwab status` check 2026-05-20T18:14 — refresh-token valid until `2026-05-24T06:40` (~2d 12h remaining at handoff; **renewal due soon**). Operator runs `swing schwab status --environment production` to check; renew via `/schwab/setup` web OR `swing schwab logout` → `swing schwab setup` CLI when ≤24h remaining.
- **S3 visual cross-check on HTF + DBW historical setups DEFERRED** from T2.SB4 housekeeping (T-A.1.7 corpus lacks embedded OHLCV bars for HTF/DBW exemplars; orchestrator-driven fetch not undertaken). Operator-paired browser-paired session to validate detector verdicts against subjective assessment on known prior setups; not blocking T2.SB5 dispatch but informs §10.4 + §10.5 calibration confidence.
- **17 V2 candidates banked across T3.SB2 + T2.SB4** (in phase3e-todo entries):
  - 10 from T3.SB2 chain (hidden-anchor V2 hardening; VM inheritance refactor; Schwab Trader lookback widening; execution timestamp in dedupe tuple; provenance-stamping helper extraction; client-side JS rebinding; soft-warn duplicate fallback; cassette runbook live-recording; "Reset to Schwab values" button; dedupe-vs-operator-typed-historical gap)
  - 7 from T2.SB4 chain (§10.5 worked-example arithmetic; Plan §G.6 stale DBW summary; DBW `_RECENT_STAGE_VALUES` consolidation; foundation primitive `volume_trend_through_swings` consolidation; HTF empirical calibration; DBW undercut bonus distribution; multi-anchor candidate window iteration)
- **2 V2.1 §VII.F amendments banked at T2.SB4** (operator decision):
  - §10.5 worked-example arithmetic inconsistency (center_peak=$23 → 60% retracement is inconsistent; recommend $24.00)
  - Plan §G.6 line 2671 stale DBW summary update ("undercut bonus + geometric_score capped at 1.0" → "geometric_score 1.10; composite capped at 1.0")
- **Production state**: ZERO open discrepancies; baseline 5376 fast / 0 ruff E501 / schema v20.

---

## §7 Suggested first session flow

1. Read this brief + CLAUDE.md line 3 + phase3e-todo top entry + T2.SB4 return report end-to-end.
2. Read plan §G.7 T2.SB5 task list end-to-end at `docs/superpowers/plans/2026-05-18-phase13-charts-patterns-autofill-usability-plan.md` (find via `grep -n "G\.7\|T2\.SB5\|template matching"`).
3. Read T2.SB4 dispatch brief + return report for detector-batch discipline + 1 RESOLVED Critical context (composite cap at runner.py:1677 is the canonical reference for T2.SB5's composite scoring implementation).
4. Read spec §5.7 + §5.8 (template matching + composite scoring sections) end-to-end — **CROSS-CHECK ANY DISPATCH BRIEF PRESCRIPTIONS AGAINST SPEC SOURCE-OF-TRUTH per C.C lesson #6 Expansion #2 BINDING**.
5. **Draft T2.SB5 dispatch brief** (~250-300 lines) at `docs/phase13-t2-sb5-template-matching-dispatch-brief.md`. Mirror T2.SB4 brief structure (§1 scope + §2 per-task + §3 files + §4 watch items + §5 done criteria + §6 LOCKs + §7 reference + §8 post-dispatch + §9 forward-binding).
6. Commit brief + push (NO Co-Authored-By footer; cite discipline).
7. Provide inline implementer dispatch prompt as fenced code block for operator copy/paste (per `feedback_always_provide_inline_dispatch_prompt`).
8. Await implementer return.
9. On return: QA against reality on disk + run pre-Codex orchestrator-side review (21st cumulative C.C lesson #6 BINDING with BOTH expansions: grep-for-hardcoded-duplicates + cross-check-brief-vs-spec) + drive S2 + S3 operator-paired gates + merge + post-merge housekeeping.

---

## §8 Do NOT

- Re-litigate T2.SB4 outcomes (SHIPPED + Codex-closed + S2 PASS + S3 disposition + housekeeping committed).
- Skip pre-Codex orchestrator-side review at T2.SB5 or any future dispatch (C.C lesson #6 BINDING + BOTH scope expansions BINDING).
- Add Co-Authored-By footer to ANY commit (~295+ streak).
- Touch the v20 migration semantics (locked).
- Modify the T-A.1.7 corpus at `data/phase13-t2-sb1-corpus/*` (operator-validated as-is).
- Address the 17 V2 candidates banked this session OR the 2 V2.1 §VII.F amendments in T2.SB5 scope (separate V2/amendment dispatches; operator decision pending).
- Skip size-check pre-flight before housekeeping (Prior state count is 10 at cap; archive-split WILL fire at next demote).
- Push without verifying empty Co-Authored-By trailer on the commit.
- Dispatch T4.SB without operator's added items (`project_phase13_t4_sb_pause_for_list_additions` memory BINDING; the pause is between T2.SB6 SHIPPED + housekeeping and T4.SB brief commissioning).

---

## §9 Quick-reference SHA roster

| Item | SHA |
|---|---|
| main HEAD at handoff | `c44aebd` (T2.SB4 housekeeping) |
| T2.SB4 merge | `3b28d92` |
| T2.SB4 dispatch brief | `af2ed5b` |
| convert_books_pdf_to_md.py tracked | `be38c17` |
| T3.SB2 + hotfix housekeeping | `9899bda` |
| T3.SB2 hotfix (_call_endpoint surface guard) | `cf3c489` |
| T3.SB2 merge | `7059945` |
| T3.SB2 dispatch brief | `7dd8264` |
| Prior handoff brief | `cb88329` |
| T2.SB3 merge | `e3d34a9` |
| T-A.1.1 v20 migration (schema-landing SHA; OQ-12 Option E branch-base for T3.SB1) | `4cfd5f2` |
| Post-handoff (after T2.SB5 brief commit) | `<new SHA from your brief commit>` |

---

## §10 Forward-binding lessons surfaced this session (8 cumulative; carry forward into T2.SB5 brief + future)

1. **`selected_X_audit_id` is an AUDIT TRAIL, not a DEDUPE KEY** (T3.SB2 R2 M3) — dedupe MUST key off "what was persisted" (envelope's top-level field), not "what operator picked" (selected_candidate_X_id).
2. **Price-precision parity between template render + POST-time float comparison** (T3.SB2 R4 M2) — compare with `round(anchor, N) != round(submitted, N)` where N matches template's display precision.
3. **`extended.pop(key, None)` for envelope keys that may not apply** (T3.SB2 R4 M1) — POP stale defaults rather than leave them; downstream dedupe falls through correctly.
4. **Schema-CHECK widening MUST audit ALL Python-side surface guards across the repo** (T3.SB2 hotfix `cf3c489`) — **C.C lesson #6 Expansion #1 BINDING**; grep `swing/` for hardcoded duplicates of any widened constant.
5. **Evidence-tier vs composite-tier score cap distinction** (T2.SB4 R1 M1 + R2 C1 + R3 M1 lesson family) — allow evidence-tier to reach spec upper bound (e.g., DBW 1.10); clamp composite-tier at spec composite cap (e.g., 1.0); validate downstream histograms consume CLAMPED composite NOT raw evidence.
6. **Bounded backward-slice search for anchor-relative detectors** (T2.SB4 R2 M2) — bound search window by spec max-duration constraints.
7. **DBW anchor_date contract via `anchor_reason.startswith("zigzag_pivot")`** (T2.SB4 R1 M2) — detectors consuming `CandidateWindow` MUST check mode tag to determine `anchor_date` semantic.
8. **Pre-Codex review must cross-check spec source-of-truth against dispatch brief sketches** (T2.SB4 R1 M1 lesson) — **C.C lesson #6 Expansion #2 BINDING**; pre-Codex review templates SHOULD include "verify dispatch brief prescriptions against spec source-of-truth at the cited section" as a binding step.

**Plus inherited from prior sessions** (banked at `368784f` + `c15633d` + `2746bbb` + earlier housekeepings; 22+ cumulative forward-binding lessons across the Phase 13 arc to date).

---

## §11 Pre-Codex orchestrator-side review (C.C lesson #6 BINDING) — 21st expected at T2.SB5 with BOTH scope expansions binding

Implementer dispatches focused reviewer subagent with brief's §3 file-scope + §4 watch items + §5 done criteria + §6 LOCKs as anchors BEFORE invoking Codex MCP. Verdict captured in return report. 20 prior cumulative validations (19 CLEAN + 1 BANKED-WITH-CAVEAT post-T3.SB2 surface-guard miss); discipline durably effective + has expanded twice this session.

**BOTH scope expansions BINDING for 21st validation at T2.SB5:**

1. **Expansion #1 (T3.SB2 hotfix `cf3c489`)**: when widening a constant mirrored elsewhere in the codebase, grep `swing/` for redundant hardcoded copies of the OLD value tuple AND verify each downstream consumer is widened consistently. Anchor: `_SCHWAB_API_SURFACE_VALUES` widening missed 3 of 4 Python-side guards at T-A.1.1; Codex chain + slow E2E + cross-bundle pin all MISSED the duplication; operator-witnessed S2 caught.

2. **Expansion #2 (T2.SB4 R1 M1 lesson)**: cross-check dispatch brief prescriptions against spec source-of-truth at cited sections. Anchor: T2.SB4 dispatch brief sketched "DBW geometric_score = min(base + bonus, 1.0)" but spec §5.8 line 718 + §10.5 line 1325 BINDING text was 1.10 evidence cap with composite at 1.0; pre-Codex review reading brief alone wouldn't catch the divergence; Codex caught at R1 M1 + R2 Critical #1 cascade.

T2.SB5 pre-Codex review MUST apply both expansions explicitly (in addition to the base scope) + cite in the implementer return report's §10 (Pre-Codex orchestrator-side review section).

---

*End of handoff brief. Post-T2.SB4-SHIPPED + housekeeping + pre-T2.SB5-dispatch orchestrator transition. T2.SB5 = template matching DTW + composite scoring; 6 tasks per plan §G.7; inherits 5-detector substrate (V1 set COMPLETE per L2 LOCK) + composite cap discipline from T2.SB4 R2 C1 + BOTH C.C lesson #6 scope expansions BINDING (grep-for-hardcoded-duplicates + cross-check-brief-vs-spec). ~295+ cumulative ZERO Co-Authored-By footer drift streak preserved. 20x cumulative C.C lesson #6 BANKED (19 CLEAN + 1 BANKED-WITH-CAVEAT); 21st expected at T2.SB5 with scope-expanded discipline. Operator-paced.*
