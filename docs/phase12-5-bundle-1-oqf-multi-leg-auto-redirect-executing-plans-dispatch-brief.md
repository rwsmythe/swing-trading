# Phase 12.5 #1 — OQ-F Multi-Leg Tier-1 Auto-Redirect — Executing-plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Phase 12.5 #1 of the Schwab reconciliation auto-correct V2 follow-up arc via `copowers:executing-plans`. Plan is `docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md` (1230 lines). All per-task acceptance criteria + tests + commit shapes are in the plan; this dispatch brief is a worktree-config + scope wrapper, NOT a duplicate spec.

**Expected duration:** ~6-10 hr implementation + ~2-4 hr Codex chain + 4-6 surface operator-witnessed gate. Total **~2-3 days operator-paced** (calibrated 3-5x per `feedback_time_estimates_overstated.md`). Phase 12.5 #1 closes the **OQ-F multi-leg tier-1 auto-redirect** V2 follow-up from post-Phase-12 mapper-widening spec §6.6 — when a Pass-2 `unmatched_*_fill` discrepancy carries multi-leg execution data that aligns within tolerance, the classifier auto-redirects to a tier-1-shape correction via the existing `_handle_split_into_partials` registry entry; operator never sees the manual `multi_partial_vs_consolidated` menu for these cases.

**Skill posture:**
- Invoke `copowers:executing-plans` against the plan path (`PLAN_PATH=docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md`).
- The skill wraps `superpowers:subagent-driven-development` + adversarial Codex review.
- Adversarial review runs after all 11 tasks land. Expected **3-5 Codex rounds** (matches Phase 12 Sub-bundle C.C 3 rounds for mid-complexity scope; post-Phase-12 Sub-bundle 2 + Sub-sub-bundle C.B precedent for service-API-extension scope). Rounds may compress because the plan absorbed 5 rounds of Codex review at writing-plans time + ZERO ACCEPT-WITH-RATIONALE banked + R1 Critical #1 (backfill consumer wiring) + R1 Major #1-#4 already addressed in-plan.

---

## §0 Inputs

### §0.1 Plan

- **PLAN_PATH:** `docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md` (1230 lines; Codex R1-R5 convergence with all findings closed; ZERO ACCEPT-WITH-RATIONALE; ZERO Critical post-R1; LOCKED at `6349486`; merged to main at `2e8b10a`).
- **Plan §A** lines 56-694: Self-contained per-task spec with TDD checkboxes (`- [ ]`) for T-1.1 .. T-1.11.
- **Plan §C** lines 708-754: Canonical files-touched roster with grep anchors verified at plan-drafting time.
- **Plan §D** lines 757-783: 14 LOCKed decisions verbatim.
- **Plan §F** lines 808-839: 25 binding invariants F1-F25 (6 NEW F20-F25 surfaced during Codex chain rounds 1-4).
- **Plan §G** lines 842-1035: Per-task acceptance-criteria narrative for the 3 tasks spanning multiple files/layers (T-1.4 + T-1.5 + T-1.8).
- **Plan §H** lines 1038-1091: 6-surface operator-witnessed gate plan.
- **Plan §I** lines 1094-1109: Cross-bundle pins (all consumer-side reads of SHIPPED surfaces).
- **Plan §K** lines 1124-1153: Refined per-task LOC + test projection.
- **Plan §M** lines 1178-1204: 18 forward-binding lessons (12 inherited + 6 NEW L-W1..L-W6).
- **Plan §Z** lines 1213-1226: 12 V2 candidates banked.

### §0.2 Spec

- **SPEC_PATH:** `docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md` (1236 lines; 7 Codex rounds; ZERO ACCEPT-WITH-RATIONALE — cleanest brainstorm chain in project history; LOCKED at `a1582c0`).
- **Read for §1 architectural shape** (predicate + recipe synthesis at classifier layer; sandbox short-circuit at inner; banner advisory only at base-layout; CLI filter in-bundle) + **§2 4 operator-locks** (auto-redirect ON; all-match-within-tolerance; reuse `apply_tier2_resolution` with overrides; banner advisory only) + **§4 predicate sub-conditions** (6 conditions; per-leg consistency; VWAP) + **§5 ClassificationResult.auto_redirect_recipe field shape** + **§7 service API parameter naming + sandbox short-circuit + savepoint discipline** + **§10 discriminating-example walkthroughs** (Cases A-J).

### §0.3 Writing-plans return report

- **RETURN_REPORT_PATH:** `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-writing-plans-return-report.md` (255 lines; commit `543a839`).
- **Read for §2** Codex chain (5 rounds; R1 1C+4M+1m → R5 sealed) + **§7** 18 forward-binding lessons (12 inherited + 6 NEW L-W1..L-W6) + **§10** composition-surface verification (post-R5 audit-list) + **§12** Codex-chain insight summary (R1 Critical #1 architectural gap + R1 Major #1-#4 surface drift).

### §0.4 Project state at dispatch time

- **HEAD on `main`:** `151d572` (post-handoff). Brief commit lands at HEAD+1 pre-dispatch.
- **Test count:** **4579 fast passing on main** + 3 pre-existing failures (`tests/integration/test_phase8_pipeline_walkthrough.py` — unchanged since Phase 8; banked under Phase 12.5 #3 maintenance dispatch) + 1 skipped. Verified inline at brief drafting time.
- **Ruff baseline:** **18 E501 errors** (unchanged across Phase 11 + Phase 12 + post-Phase-12 Sub-bundles 1+1.5+2 + Phase 12.5 #1 brainstorm + writing-plans). Plan MUST NOT introduce new E501.
- **Schema version:** **v19** (LOCKED since Phase 12 Sub-sub-bundle C.A 2026-05-15; verified §13.1 audit + F1 invariant; F19 plan-author schema additions escalation rule was NOT triggered during writing-plans). **Phase 12.5 #1 MAY NOT widen schema** (plan §F F1 + F19 escalation rule).
- **Production discrepancy state:** ZERO unresolved-material (all 7 from C.D gate dispositioned in terminal states + all C.D gate state preserved through Sub-bundle 1/1.5/2 chain). Phase 10 dashboard banner count=0. **Phase 12.5 #1 ship makes multi-leg fills auto-corrected (operator never sees manual menu for these); existing tier-1/tier-2 production paths UNAFFECTED**.
- **Production refresh-token clock:** expires ~2026-05-22T17:05:00+00:00 (~5 days remaining at brief drafting time; safe through expected dispatch wall-clock). **Operator may need to re-auth via `/schwab/setup` web form OR `swing schwab setup` CLI before S3 production fetch gate surface if dispatch slips.**
- **Production-write classifier soft-block awareness:** S3 production fetch + S4 banner-plant gate surfaces are production-writes against operator's REAL DB. Operator pre-authorizes via gate-path AskUserQuestion or plain-chat "yes" if Claude Code's production-write classifier soft-blocks. **DO NOT proceed without explicit operator authorization per-invocation** (NEW C.D-arc lesson #2: production-write classifier soft-block fires PER-INVOCATION even after AskUserQuestion authorization).
- **Worktree husks:** 2 pending operator's cleanup-script pass (`phase12-5-bundle-1-oqf-brainstorm/` + `phase12-5-bundle-1-oqf-writing-plans/`); NOT blocking executing-plans dispatch.

### §0.5 Phase 12.5 #1 scope (11 tasks per plan §A)

| Task | Title | Files (illustrative; plan §A locks) |
|---|---|---|
| **T-1.1** | `_multi_leg_auto_redirect_predicate` + `_synthesize_split_into_partials_recipe` pure helpers + module-level constants | MODIFY `swing/trades/reconciliation_classifier.py` + NEW `tests/trades/test_reconciliation_classifier_multi_leg_predicate.py` |
| **T-1.2** | `ClassificationResult.auto_redirect_recipe` field + integration in `_classify_unmatched_fill_shared` (`n>=2` AND `n=1` reclassification branches) | MODIFY `swing/trades/reconciliation_classifier.py` + 2 NEW test files |
| **T-1.3** | Pass-2 candidate-dict emit-shape extension (`_orders_to_classifier_payload` + F24 dict-branch normalization) | MODIFY `swing/trades/reconciliation_backfill.py` + NEW test file |
| **T-1.4** | `apply_tier2_resolution` override-kwarg parameterization + `_validate_override_combo` helper + `InvalidOverrideComboError` typed exception | MODIFY `swing/trades/reconciliation_auto_correct.py` (13+ functions) + NEW test file |
| **T-1.5** | **Pivot-loop + backfill auto-redirect dispatch** consuming `auto_redirect_recipe` + 3 new `BackfillSummary` counters + `format_summary_block` renderer extension. **Codex R1 Critical #1 LOCK: backfill is OPERATIONAL firing site; initial pivot is defensive future-proofing** | MODIFY `swing/trades/schwab_reconciliation.py` + `swing/trades/reconciliation_backfill.py` + 2 NEW test files (includes slow E2E test on backfill consumer per F20) |
| **T-1.6** | Sandbox short-circuit in `_apply_tier2_resolution_inner` gated on `applied_by_override == 'auto'` + `_SandboxAutoRedirectShortCircuit` sentinel | MODIFY `swing/trades/reconciliation_auto_correct.py` + NEW test file |
| **T-1.7** | `count_recent_multi_leg_auto_corrections` helper (COUNT(DISTINCT discrepancy_id); window=`'most_recent_run'` V1 LOCK) | MODIFY `swing/metrics/discrepancies.py` + NEW test file |
| **T-1.8** | `BaseLayoutVM.recent_multi_leg_auto_correction_count` + retrofit across **all** base-layout-mounted VMs (TEMPLATE-MOUNT enumeration per F23; ≥17 VMs across 17 files) | MODIFY `swing/web/view_models/metrics/shared.py` + 17 VM files + NEW test file |
| **T-1.9** | `base.html.j2` banner block (ASCII-only per F12) citing CLI filter verbatim | MODIFY `swing/web/templates/base.html.j2` + NEW test file |
| **T-1.10** | `swing journal discrepancy list --resolved-by <value>` CLI filter | MODIFY `swing/cli.py` + NEW test file |
| **T-1.11** | Empty-executions canary observability + briefing.md +1 line `- Multi-leg auto-redirects applied this run: K` per F22 | MODIFY `swing/trades/reconciliation_classifier.py` + `swing/pipeline/runner.py` + `swing/rendering/briefing.py` + `swing/rendering/briefing_md.py` + 2 NEW test files |

**Dispatch order:** T-1.1 → T-1.2 → T-1.3 → T-1.4 → T-1.5 → T-1.6 → T-1.7 → T-1.8 → T-1.9 → T-1.10 → T-1.11. Parallelizable opportunities (executing-plans may bundle if convenient): T-1.3 + T-1.7 can land before T-1.4; T-1.10 is independent of T-1.5-T-1.8. **DO NOT REORDER** without explicit acceptance-criteria adjustment.

**Cross-bundle dependencies:** Phase 12.5 #1 CONSUMES Sub-bundle C.A schema (v19; CHECK enums + cross-column CHECK already permit Phase 12.5 #1 values) + Sub-bundle C.B `ClassificationResult` dataclass + `classify_discrepancy` dispatch + sub-classifier registry + Sub-bundle C.C `apply_tier2_resolution` + `_apply_tier2_resolution_inner` + `_handle_*` registry + `_pivot_classify_and_dispatch_for_run` SAVEPOINT discipline + Sub-bundle C.D `swing journal discrepancy list` CLI + Phase 10 banner predicate widening + Sub-bundle 1 `SchwabExecutionLeg` + `SchwabOrderResponse.executions` field + Sub-bundle 1.5 `_has_non_placeholder_leg` canary helper precedent + Sub-bundle 2 `SchwabSetupVM` + `SchwabStatusVM` + `SchwabSetupErrorVM` base-layout retrofit + Phase 10 T-E.3 17-VM retrofit pattern.

**Module boundaries (BINDING — preserve discipline):**
- `swing/trades/reconciliation_classifier.py`: PURE classifier layer. Predicate + recipe synthesizer pure; no DB / API / logging side-effects (T-1.11 canary `logger.warning` is the ONE documented exception). NO transaction management. Per F14.
- `swing/trades/reconciliation_backfill.py`: Pass-2 backfill orchestrator. `_orders_to_classifier_payload` (T-1.3 dataclass→dict seam) + `_handle_pass_2` (T-1.5 OPERATIONAL firing site) + `run_backfill` (T-1.5 counter wiring) + `format_summary_block` (T-1.5 renderer extension).
- `swing/trades/reconciliation_auto_correct.py`: Service layer. `apply_tier2_resolution` outer + `_apply_tier2_resolution_inner` (T-1.4 override-kwarg parameterization + T-1.6 sandbox short-circuit) + 12 `_handle_*` helpers + `_build_tier2_correction` + `_flip_discrepancy_to_resolved_ambiguity` + NEW `_validate_override_combo` helper + NEW `InvalidOverrideComboError` typed exception.
- `swing/trades/schwab_reconciliation.py`: `_pivot_classify_and_dispatch_for_run` (T-1.5 defensive future-proofing branch + outer-catch ladder reorder; docstring caveat for `InvalidOverrideComboError`).
- `swing/metrics/discrepancies.py`: Pure read helper. `count_recent_multi_leg_auto_corrections` (T-1.7).
- `swing/web/view_models/**`: Base-layout VM retrofit (T-1.8; TEMPLATE-MOUNT enumeration per F23). ≥17 VMs touched across 17 files.
- `swing/web/templates/base.html.j2`: Banner block insertion (T-1.9; ASCII-only per F12).
- `swing/cli.py`: `discrepancy_list_cmd` `--resolved-by` filter (T-1.10).
- `swing/pipeline/runner.py` + `swing/rendering/briefing*.py`: Per-run counter + briefing.md +1 line (T-1.11; F22 verbatim wording "this run").

### §0.6 BINDING contracts from plan §D (DO NOT re-litigate)

The 14 LOCKs at plan §D lines 757-783. Verbatim summary:

**Operator-locks (spec §2.1-§2.4 + §15.B):**
1. **Auto-redirect posture = ON** (spec §2.1). V1 ships enabled. T-1.2 emits `auto_redirect_recipe` when predicate fires.
2. **Confidence threshold = all-match-within-tolerance** (spec §2.2). Predicate sub-conditions 3+5+6 enforce qty-sum + VWAP-journal-align + per-leg-consistency. Single outlier → tier-2.
3. **Auto-correct handler shape = reuse `apply_tier2_resolution(choice_code='split_into_partials', resolved_by='auto_tier1_multi_leg', applied_by_override='auto', correction_action_override='auto_applied', operator_custom_payload=synthesized_payload)`** (spec §2.3). NO dedicated `apply_tier1_split_into_partials_auto` handler.
4. **Operator-facing UX = banner advisory only** (spec §2.4). NO dedicated `/metrics/auto-redirects` review page V1.
5. **`price_tolerance = $0.01` absolute LOCK** (spec §15.B #1). NO `max($0.01, abs(journal_price) * 0.001)` proportional override. Operator's $1-$70 universe; proportional override is V2 candidate.
6. **`qty_tolerance` asymmetry preserved: predicate=1e-9 / handler=1e-6** (spec §15.B #2). Predicate stricter than handler is safe by construction; do NOT touch `_handle_split_into_partials`'s `qty_tolerance = 1e-6` at line 1680.
7. **NO defensive cap on N legs V1** (spec §15.B #3). Schwab supports arbitrary leg count; production evidence so far is zero multi-leg orders; mapper-coherence-check filters pathological cases upstream.

**Brainstorm-locks (spec §15.A; Codex chain resolved):**
8. **§6.5 n=1 single-order multi-leg path via `ambiguity_kind` reclassification** (Codex R1 M2). Predicate fires on n=1 with `len(executions) >= 2`; classifier reclassifies `ambiguity_kind` from `'unknown_schwab_subtype'` to `'multi_partial_vs_consolidated'` to satisfy cross-column CHECK pairing AND route through the EXISTING `_TIER2_HANDLERS[('multi_partial_vs_consolidated', 'split_into_partials')]` registry entry. NO new handler key.
9. **§8.6 `--resolved-by <value>` CLI filter — LOCKED IN-BUNDLE at T-1.10** (Codex R1 M5). Banner template (T-1.9) cites it; both land in the same integration merge.
10. **§7.6 sandbox short-circuit gated-on-`applied_by_override == 'auto'`** (Codex R1 M3) + SAVEPOINT ROLLBACK pattern. Manual operator path under sandbox still proceeds (operators can test manual menu in sandbox).
11. **§7.4 service API parameter naming** (Codex R1 M4 + R3 M1 + R3 M2) — `operator_custom_payload` (existing kwarg; preserves verbatim) + 3 NEW override kwargs (`applied_by_override`, `correction_action_override`, `resolved_by_override`). Positional `conn` first arg preserved.
12. **§11.2 briefing.md +1 line for `tier1_multi_leg_redirected_count` when > 0** (Codex R2 M1 — LOGICAL semantics via `COUNT(DISTINCT discrepancy_id)`). Wording is **"applied this run"** verbatim per F22 (NOT "last 7 days" — that's the legacy `reconciliation_tier1_recent_count` window).
13. **§12.3 canary observability for empty-executions case** — `~+5 LOC + 1 test` in T-1.11 predicate (Sub-bundle 1.5 canary precedent).
14. **`resolved_by` is free TEXT** (spec §13.3 + brainstorm return report §5 #7) — NO `_RESOLVED_BY_VALUES` Python constant exists; no constant introduced in plan; no schema CHECK widening. Plan §F invariant F7 pins.

### §0.7 25 binding invariants F1-F25 (plan §F lines 808-839)

Encoded as project-wide CONTRACTS. Each invariant has a discriminating regression test pattern (per plan §F table). Implementer MUST validate every task respects all 25.

**Schema + back-compat (F1-F6):** F1 ZERO new schema; F2 ZERO change to `apply_tier1_correction` external surface; F3 ZERO change to `apply_tier2_resolution` default behavior (legacy back-compat); F4 ZERO change to determinism principle (pure predicate); F5 NO `Co-Authored-By` footer on ANY commit; F6 NO `--no-verify`.

**Spec §15.B operator-locks (F7-F10):** F7 `resolved_by` is free TEXT; F8 qty_tolerance asymmetry predicate=1e-9 / handler=1e-6; F9 `price_tolerance = $0.01` absolute; F10 NO defensive cap on N legs.

**Surface + UI (F11-F12):** F11 All base-layout VMs MUST inherit `recent_multi_leg_auto_correction_count` field; F12 Banner template text MUST be ASCII-only (Windows cp1252 gotcha).

**Transactional discipline (F13-F18):** F13 SAVEPOINT-per-discrepancy preserved at flow-pivot; F14 Classifier purity preserved (canary `logger.warning` is the ONE exception); F15 Hybrid-row invariant (`applied_by='auto'` + `correction_action='auto_applied'` + `correction_choice='split_into_partials'` valid IFF parent `resolved_by='auto_tier1_multi_leg'`); F16 Exception specificity ordering (`InvalidOverrideComboError` catch FIRST + re-raises per F21; generic `ValueError` catch second per spec §7.5 fresh-savepoint fallback); F17 Sandbox short-circuit lives in inner not outer (C.C lesson #2 carry-forward); F18 Counter ROW-vs-LOGICAL semantics (`COUNT(DISTINCT discrepancy_id)`).

**Escalation discipline (F19):** Plan-author schema additions escalation. If Codex review surfaces a need for schema addition, STOP + escalate to orchestrator BEFORE encoding.

**NEW writing-plans-surfaced invariants (F20-F25):** F20 Auto-redirect dispatch wired in BOTH initial-pivot AND backfill (R1 Critical #1 — backfill is operational firing site); F21 `InvalidOverrideComboError` propagates out of pivot loop AND backfill orchestrator (R1 Major #1 + spec §7.4 R4 M2 LOCK + lesson #11); F22 Briefing.md per-run counter wording is "applied this run" verbatim (R1 Major #2 + spec §11.2 LOCK); F23 VM retrofit scope is TEMPLATE-MOUNT not field-presence (R1 Major #3 + spec §3 + §16 lesson #6); F24 `_orders_to_classifier_payload` dict-branch normalizes absent `executions` key to `None` (R1 Major #4 — cassette/replay-vs-production shape contract); F25 Predicate consumes dict-shaped executions only (R1 minor #1 — dataclass→dict conversion owned by T-1.3 at backfill→classifier seam).

### §0.8 18 forward-binding lessons (plan §M lines 1178-1204)

**12 inherited from brainstorm return report §8** (verbatim per plan §M):
1. Recipe-field discipline.
2. Override-parameter threading.
3. Free-text vs CHECK-enum columns.
4. Cross-column CHECK invariants.
5. Sandbox short-circuit ALWAYS in inner.
6. Helper invocation completeness across base-layout VMs.
7. ASCII-only banner text.
8. Counter ROW-vs-LOGICAL semantics.
9. Validate override combos BEFORE state mutation.
10. Shape-aware terminal-state idempotency.
11. Exception specificity ordering in catch blocks.
12. Positional-vs-keyword signature audit at writing-time.

**6 NEW writing-plans-surfaced lessons** (L-W1 … L-W6 per plan §M + writing-plans return report §7):
- **L-W1 (R1 Critical #1):** Dispatcher pattern + recipe consumption — enumerate EVERY dispatcher consumer. Initial pivot's source_payload derivation matters; if it returns None for unmatched sentinel, dispatcher there is dead-code; operational consumer lives ELSEWHERE.
- **L-W2 (R1 Major #1):** Spec-locked exception-propagation contracts MUST be encoded as catch-ladder ordering in plan tasks, NOT as "PLAN DECISION" overrides aligned with adjacent graceful-degradation.
- **L-W3 (R1 Major #2):** Spec-locked rendering text MUST be verbatim-asserted in tests; don't lift adjacent patterns (e.g., "last 7 days" from neighbor) without re-checking the new lock.
- **L-W4 (R1 Major #3):** Retrofit scope predicates MUST be enumerated by canonical mechanism (template-mount), NOT proxy field-presence on prior banner field.
- **L-W5 (R1 Major #4):** Helper functions producing normalized dicts MUST emit a stable key-set across ALL input branches (no permissive dict-passthrough; closes cassette-vs-production shape drift).
- **L-W6 (R1 minor #1):** Conversion seams (dataclass→dict at module boundary) MUST be owned by ONE task with clear contract; consumer tests should not duck-type both shapes.

**Codex-chain-surfaced additional insights** (writing-plans return report §7; not promoted to numbered lessons but worth executing-plans awareness):
- **Per-service-write pipeline-exclusion recheck pattern** — any new flow with ≥2 own-tx service writes MUST recheck `_check_pipeline_not_running` BEFORE EACH write (existing canonical pattern at `reconciliation_backfill.py:745-751 + 966-974 + 1033-1036`).
- **Stamp-success tracking before fallback dispatch** — wrap 2-step service sequence in try/except + track `stamp_succeeded` boolean so catch handler knows whether step 1 succeeded.
- **Counter wiring + CLI renderer parity** — new `BackfillSummary` counters MUST also be threaded through `format_summary_block` (T-1.5 includes; Codex R4 Major #1 fix).

### §0.9 Test + LOC projection (plan §K)

Per plan §K:
- **~+102 fast tests** projected (per-task: T-1.1 ~17 + T-1.2 ~14 + T-1.3 ~5 + T-1.4 ~12 + T-1.5 ~14 + T-1.6 ~6 + T-1.7 ~7 + T-1.8 ~9 + T-1.9 ~5 + T-1.10 ~4 + T-1.11 ~9).
- **1 slow E2E test** at `tests/trades/test_backfill_auto_redirect_dispatch.py::test_e2e_phase12_5_1_full_flow_through_backfill_to_banner_count` (per F20 — slow E2E on operational firing site, NOT pivot loop).
- **~+435 production LOC + ~+670 test LOC = ~+1105 total LOC** projected.

Final main HEAD post-Phase-12.5-#1-merge: **~4681 fast tests** (was 4579 + ~102 new). Matches Phase 9/10/12 overshoot precedent at midline; actual likely **+100-140 fast tests upper bound**.

---

## §1 Worktree + binding conventions

### §1.1 Worktree

- **Branch:** `phase12-5-bundle-1-oqf-executing-plans`
- **Worktree directory:** `.worktrees/phase12-5-bundle-1-oqf-executing-plans/`
- **BASELINE_SHA:** `151d572` (current main HEAD pre-brief-commit; resolve via `git rev-parse main` at worktree-creation time after this brief lands).
- **Branch naming intent:** `phase12-5-bundle-1-oqf-executing-plans` matches the cleanup-script `phase\d+[-_]` regex (verified at `cleanup-locked-scratch-dirs.ps1:156`); operator's `-DeregisterFirst` pass cleans cleanly post-merge.

### §1.2 Marker-file workflow

- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- Marker stays present through implementation + Codex chain + pre-adversarial-critic orchestrator-side review.
- After all 11 tasks land + tests GREEN + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits

- Conventional prefixes per plan §A commit message stems:
  - `feat(reconciliation): add multi-leg auto-redirect predicate + recipe synthesis helpers (Phase 12.5 #1 T-1.1)`
  - `feat(reconciliation): emit auto_redirect_recipe on multi-leg unmatched_*_fill classifier paths (Phase 12.5 #1 T-1.2)`
  - `feat(reconciliation): include executions[] on Pass-2 candidate dicts for multi-leg auto-redirect (Phase 12.5 #1 T-1.3)`
  - `feat(reconciliation): parameterize apply_tier2_resolution with override kwargs + shared validator (Phase 12.5 #1 T-1.4)`
  - `feat(reconciliation): pivot-loop auto-redirect dispatch on classifier recipe (Phase 12.5 #1 T-1.5)`
  - `feat(reconciliation): sandbox short-circuit on auto-redirect path in _apply_tier2_resolution_inner (Phase 12.5 #1 T-1.6)`
  - `feat(metrics): add count_recent_multi_leg_auto_corrections helper (Phase 12.5 #1 T-1.7)`
  - `feat(web): retrofit recent_multi_leg_auto_correction_count across base-layout VMs (Phase 12.5 #1 T-1.8)`
  - `feat(web): add multi-leg auto-correction banner to base layout (Phase 12.5 #1 T-1.9)`
  - `feat(cli): add --resolved-by filter to swing journal discrepancy list (Phase 12.5 #1 T-1.10)`
  - `feat(pipeline,briefing): multi-leg auto-redirect canary + briefing.md +1 line (Phase 12.5 #1 T-1.11)`
  - `fix(phase12-5-1): Codex RN <severity> #N — <description>` for Codex-driven fixes
- **NO Claude co-author footer** (per F5; CLAUDE.md "No Claude co-author footer" convention + Phase 12 Sub-bundle C.B-D arc + post-Phase-12 Sub-bundles 1/1.5/2 + Phase 12.5 #1 brainstorm + writing-plans chains ALL held the line via explicit citation in dispatch prompts; **~95+ cumulative commits ZERO drift**). Subagent context starts isolated; the Bash tool's default footer template is NOT authoritative for this project — CLAUDE.md is. **DO NOT add `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (or any other Co-Authored-By footer attributing the AI assistant) to ANY commit message.** This dispatch MUST NOT regress.
- **NO `--no-verify`** (per F6), **NO `--amend`** (per CLAUDE.md binding conventions: prefer `git add <specific-files>` over `git add -A`).
- **TDD:** failing test first, minimal implementation, pass, commit. Per-task `- [ ]` checkboxes in plan §A mark per-step boundaries.

### §1.4 Branch isolation + ownership

- Commits on branch only; no push to origin from worktree until Phase 12.5 #1 integration commit (post-Codex-convergence).
- **Implementer (you) owns:** task-family TDD commits → marker-file removal → pre-Codex orchestrator-style review (NEW C.C lesson #6) → adversarial-critic → return report at `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-executing-plans-return-report.md`.
- **Operator owns:** witnessed verification gate (§3 surfaces below — 6 surfaces per plan §H).
- **Orchestrator owns:** integration merge to main + post-merge housekeeping + Phase 12.5 #2 dispatch commissioning.

### §1.5 Verify command

PowerShell from inside worktree:

```powershell
git log --oneline HEAD~20..HEAD
python -m pytest -m "not slow" -q -n auto
python -m pytest -m slow tests/trades/test_backfill_auto_redirect_dispatch.py::test_e2e_phase12_5_1_full_flow_through_backfill_to_banner_count -v   # T-1.5 slow E2E
ruff check swing/ --statistics
python -c "from swing.trades.reconciliation_classifier import _multi_leg_auto_redirect_predicate, _synthesize_split_into_partials_recipe; print('predicate + synthesizer OK')"
python -c "from swing.trades.reconciliation_classifier import ClassificationResult; r = ClassificationResult(tier=2, ambiguity_kind='unsupported', correction_target=None, correction_reason='x'); assert r.auto_redirect_recipe is None; print('CR.auto_redirect_recipe default OK')"
python -c "from swing.trades.reconciliation_auto_correct import apply_tier2_resolution, _validate_override_combo, InvalidOverrideComboError, _SandboxAutoRedirectShortCircuit; print('service overrides OK')"
python -c "from swing.metrics.discrepancies import count_recent_multi_leg_auto_corrections; print('metric helper OK')"
python -m swing.cli journal discrepancy list --resolved-by auto_tier1_multi_leg --help
```

**IMPORTANT — worktree CLI invocation discipline (per `feedback_worktree_cli_invocation.md`):** `swing` routes to editable-install path NOT worktree code. ALWAYS use `python -m swing.cli` from worktree cwd when verifying worktree-side CLI changes.

---

## §2 Adversarial review (Codex)

Invoked automatically by `copowers:executing-plans` after all 11 tasks land + tests GREEN + after the pre-Codex orchestrator-side review (C.C lesson #6 — implementer MUST do an explicit dispatched-reviewer-subagent pass BEFORE invoking adversarial-critic; cheap; absorbs LOCK divergences pre-Codex; saved 1-2 Codex rounds on C.C + 2 absorbed Majors on C.D + 1 absorbed Major + 1 absorbed Minor pre-Codex; saved 1-2 absorbed findings on Sub-bundle 1; saved 2-3 absorbed findings on Phase 12.5 #1 brainstorm).

**Expected chain shape:** 3-5 substantive Codex rounds. Plan §A absorbed 5 rounds of Codex review at writing-plans time + ZERO ACCEPT-WITH-RATIONALE banked + 1 Critical + 12 Major + 8 distinct Minor all resolved with code-content fixes. Execution rounds should converge faster than writing-plans (matches Sub-bundle C.B → C.C 5→3 round compression precedent).

**Adversarial review watch items (Phase 12.5 #1-specific; pass as targeted prompts to `copowers:adversarial-critic`):**

1. **F20 — Backfill is OPERATIONAL firing site** (R1 Critical #1 lesson). Pivot-loop dispatch is defensive future-proofing; backfill `_handle_pass_2` + `run_backfill` orchestrator + `format_summary_block` renderer is the actual operator-facing path. Discriminating test: slow E2E at `tests/trades/test_backfill_auto_redirect_dispatch.py::test_e2e_phase12_5_1_full_flow_through_backfill_to_banner_count` plants multi-leg fixture + invokes `_handle_pass_2(dry_run=False, environment='production', ...)` + asserts full state cascade (4 correction rows + parent discrepancy in `operator_resolved_ambiguity` with `resolved_by='auto_tier1_multi_leg'` + `count_recent_multi_leg_auto_corrections(conn) == 1` + `BackfillOutcome.outcome == 'tier1_multi_leg_auto_redirected'` + per-run briefing counter increment).
2. **F21 — `InvalidOverrideComboError` propagates out of pivot loop AND backfill orchestrator** (R1 Major #1). Catch ladder MUST be `except InvalidOverrideComboError: raise` FIRST + generic `except Exception as e:` SECOND. The `_pivot_classify_and_dispatch_for_run` line-429 docstring `"never raises out"` is intentionally violated for the developer-bug case; docstring caveat MUST be added. Discriminating test: `test_pivot_loop_auto_redirect_invalid_override_combo_propagates_out` + `test_pivot_loop_outer_catch_ladder_invalid_override_first_generic_second` — plant `ValidatorRejectedError` (subclass of `ValueError` but NOT `InvalidOverrideComboError`) → counter `tier_errored_count == 1`; no propagation. Then plant `InvalidOverrideComboError` → propagates out.
3. **F22 — Briefing.md per-run counter wording verbatim "applied this run"** (R1 Major #2). Discriminating test: `test_briefing_md_emits_multi_leg_line_when_count_gt_zero` asserts substring `"- Multi-leg auto-redirects applied this run: 3"` verbatim. NOT "(last 7 days)" (that's the legacy `reconciliation_tier1_recent_count` window).
4. **F23 — VM retrofit scope is TEMPLATE-MOUNT not field-presence** (R1 Major #3). Discriminating test: `test_every_base_layout_template_renders_vm_with_recent_multi_leg_field` enumerates VMs by `{% extends "base.html.j2" %}` template grep, NOT by `unresolved_material_discrepancies_count` field presence. Catches `AccountSnapshotFormVM` which inherits via `BaseLayoutVM`.
5. **F24 — `_orders_to_classifier_payload` dict-branch normalizes absent `executions` key to `None`** (R1 Major #4). Discriminating test: `test_orders_to_classifier_payload_dict_input_without_executions_key_normalized_to_none` — pre-converted dict lacking `'executions'` key → output dict has `'executions': None` injected.
6. **F25 + L-W6 — Conversion seam owned by T-1.3** (R1 minor #1). Predicate consumes dict-shaped executions only; `SchwabExecutionLeg` dataclass → plain dict conversion happens at `_orders_to_classifier_payload`. Discriminating test: `test_predicate_consumes_dict_shaped_executions_only` — predicate test fixtures use dict-form ONLY; no dataclass passthrough.
7. **F1 + F19 — Schema v19 UNCHANGED LOCK + plan-author schema additions escalation rule.** If Codex surfaces a need for schema element NOT in plan §A + spec §3, implementer MUST STOP + escalate to orchestrator BEFORE adding inline. Cost of bank-after-write: 2-3 cascade-cleanup rounds. Discriminating test: `grep -rn "0020" swing/data/migrations/` returns 0 matches.
8. **F5 — NO `Co-Authored-By` footer on ANY commit.** Per project invariant + ~95+ cumulative ZERO drift across Phase 11/12/post-Phase-12/Phase-12.5-brainstorm/writing-plans chains. Implementer MUST verify pre-merge that EVERY commit message lacks the footer; if any commit drifts, orchestrator-side interactive rebase reword is the recovery (per C.B R1 fix-bundle precedent at writing-plans return report §1).
9. **F8 — qty_tolerance asymmetry preserved**. `swing/trades/reconciliation_auto_correct.py:1680` `qty_tolerance = 1e-6` UNCHANGED. New module-level constant `_MULTI_LEG_QTY_TOLERANCE = 1e-9` in T-1.1.
10. **F9 — `_MULTI_LEG_PRICE_TOLERANCE = 0.01` absolute** (NO `max(...)` override path). Constant only.
11. **F10 — NO defensive cap on N legs.** T-1.1 acceptance: predicate test includes 5 legs; no `MAX_LEGS_PER_ORDER` constant.
12. **F11 + F23 — `BaseLayoutVM.recent_multi_leg_auto_correction_count` retrofit across all base-layout VMs.** Per plan §G.3 narrative; ≥17 VMs. Discriminating test: `test_every_vm_with_unresolved_material_field_also_has_recent_multi_leg_field` introspects via `dataclasses.fields(VMClass)`. Defense-in-depth complement to template-mount test.
13. **F12 — Banner template text ASCII-only** (Windows cp1252 gotcha + CLAUDE.md gotcha). Discriminating test: `test_base_layout_multi_leg_banner_ascii_only` — `assert all(ord(c) < 128 for c in rendered_banner_text)`.
14. **F14 — Classifier purity preserved.** Predicate + recipe synthesizer pure; no DB / API / logging side-effects (T-1.11 canary `logger.warning` is the ONE documented exception with `ticker` kwarg threading).
15. **F15 — Hybrid-row invariant enforced by `_validate_override_combo`.** Auto-redirect overrides REQUIRE `choice_code='split_into_partials'`. Discriminating test: full override-combo test matrix at T-1.4.
16. **F17 — Sandbox short-circuit lives in inner not outer** (C.C lesson #2). Discriminating test: `test_apply_tier2_resolution_inner_sandbox_short_circuits_on_auto_override_combo`. Sandbox short-circuit fires AFTER `_validate_override_combo` AND AFTER `_select_discrepancy` (SELECT-first-idempotency contract preserved).
17. **F18 — `COUNT(DISTINCT discrepancy_id)`** for any multi-leg counter (T-1.7 + T-1.11). Discriminating: plant 1 multi-leg discrepancy with 4 correction rows (1 anchor + 3 partials) → returns 1, NOT 4.
18. **Cassette-vs-production shape parity** (NEW from L-W5 + F24). Synthetic test fixtures plant production-emitter shapes byte-for-byte (no permissive duck-typing). Pre-empt cassette-vs-production drift via `_orders_to_classifier_payload` dict-branch normalization + per-test-fixture explicit `executions=None` annotation.
19. **Windows cp1252 stdout encoder pre-emption** (C.D gate-fix #1+#3 family). NEW CLI output at T-1.10 `--resolved-by` filter MUST NOT contain non-ASCII glyphs OR rely on `swing/cli.py` entry's UTF-8 stdout reconfigure as defense-in-depth.
20. **NO behavioral changes to NON-touched existing surfaces** (plan §C.3 LOCK). Especially: `apply_tier1_correction` external surface UNCHANGED; `swing/integrations/schwab/mappers.py` + `swing/integrations/schwab/models.py` UNCHANGED; `swing/web/routes/schwab.py` UNCHANGED; `swing/data/migrations/0019_*.sql` UNCHANGED; `swing/trades/reconciliation_ambiguity_choices.py` operator menu UNCHANGED.

---

## §3 Operator-witnessed verification gate (6 surfaces per plan §H)

Per plan §H.1-§H.6:

| Surface | Type | Acceptance |
|---|---|---|
| **S1** | Inline `pytest -m "not slow" -q -n auto` + ruff + slow E2E | ALL fast tests pass (target ~4681 = 4579 baseline + ~102 new). 3 pre-existing `phase8 walkthrough` failures acknowledged (banked under Phase 12.5 #3); no other failures. **Ruff baseline 18 E501 UNCHANGED**. Slow E2E `python -m pytest -m slow tests/trades/test_backfill_auto_redirect_dispatch.py::test_e2e_phase12_5_1_full_flow_through_backfill_to_banner_count` PASSES. |
| **S2** | Synthetic-fixture predicate matrix walk-through | `python -c "from swing.trades.reconciliation_classifier import _multi_leg_auto_redirect_predicate, _synthesize_split_into_partials_recipe; ..."` exercising 5-8 spec §10 cases (Case A n=1 multi-leg fires; Case C per-leg outlier declines; Case E VWAP-journal misalign; Case I N=2 candidates × multi-leg each). Each fixture produces expected predicate result + (when fires) expected recipe shape per spec §10. Determinism spot-check × 10 invocations + assert byte-for-byte identical `ClassificationResult` via frozen dataclass equality. **MAY BE SKIPPED-with-test-coverage if T-1.1 + T-1.2 + T-1.4 fast tests cover every case** (per plan §H.6 polish-bundle-2026-05-10 precedent). |
| **S3** | Production fetch end-to-end | `python -m swing.cli schwab fetch --orders --environment production` from executing-plans worktree (per `feedback_worktree_cli_invocation.md`). **Negative-sense pass criterion** (MOST LIKELY per Sub-bundle 1.5 30-day production sample showing ZERO multi-leg fills): NO multi-leg auto-redirect fires; emitted `reconciliation_run` has `tier1_multi_leg_auto_redirected_count = 0`; banner does NOT appear; ZERO false-positive auto-redirects on non-multi-leg cases. **Alternative outcome** (if operator's production has accumulated a multi-leg fill): auto-redirect fires; counter > 0; banner appears. **Sandbox cross-check (optional):** re-run with `--environment sandbox` + verify sandbox short-circuit fires (audit row written to `schwab_api_calls`; ZERO journal mutation). **Production-write classifier soft-block:** EXPECT BLOCKS PER-INVOCATION per NEW C.D-arc lesson #2; operator pre-authorizes per turn. |
| **S4** | Banner UI plant + clear | `swing web --port 8081 &` from executing-plans worktree. Plant: synthetic multi-leg auto-correction via direct SQL fixture (mirror C.D banner-fires gate pattern; UPDATE `reconciliation_discrepancies` SET `resolved_by='auto_tier1_multi_leg'` + plant fresh `reconciliation_runs` row with `state='completed'`). `curl -s http://127.0.0.1:8081/ \| grep -c 'class="reconciliation-auto-redirect-banner"'` → count > 0; banner text matches spec §8.3 verbatim; ASCII-only. **Banner-clears test:** insert fresh `reconciliation_run` row with `state='completed'` AND zero auto-redirected corrections → curl again → banner count drops to 0 (clears semantic per spec §8.4 LOCK). **Tier-3 override does NOT clear the banner mid-window** — invoke `apply_tier3_override` on the auto-redirected chain head + assert banner STILL present + count unchanged (per spec §9.3 S4 R4 Minor 2 + R5 Minor 1 LOCK). **Cleanup:** revert planted state to operator-acknowledged form per C.D gate-cleanup precedent. |
| **S5** | CLI `--resolved-by` filter | `python -m swing.cli journal discrepancy list --resolved-by auto_tier1_multi_leg` (when planted state from S4 exists) → returns planted multi-leg row(s). **Negative test:** `--resolved-by nonexistent_value` → `"(no discrepancies)"`. **Compose test:** `--resolved-by auto_tier1_multi_leg --material` → returns multi-leg rows that also have `material_to_review=1`. |
| **S6** | Briefing.md +1 line | Run pipeline: `python -m swing.cli pipeline run` (under planted S4 state). Inspect: `cat exports/<action_session_date>/briefing.md \| grep -A 5 "## Reconciliation status"`. **Pass (when count > 0):** section contains new `- Multi-leg auto-redirects applied this run: K` line (verbatim per F22; wording is "this run" NOT "last 7 days"); K matches planted count on latest completed reconciliation_run. **Pass (when count == 0; default production state):** section either absent (all 3 counters 0) OR present without new line (other counters > 0). **MAY BE SKIPPED-with-test-coverage if T-1.11's `test_briefing_md_emits_multi_leg_line_when_count_gt_zero` covers the assertion** (per plan §H.6). |

**Gate session budget:** 6 surfaces. Medium-sized gate (smaller than C.D's 10-surface headline; matches Sub-bundle 1 + 2 + C.C 4-7-surface mid-cycle precedents). Operator-paired-gate driving — ONE COMMAND AT A TIME on production writes (per handoff brief §0 LOCK); inline-batched OK on read-only surfaces.

**Production-write classifier soft-block awareness at S3+S4:** dry-run + apply + banner-plant against production DB are production-writes from Claude Code's classifier perspective (audit-row writes count; SQL fixture insert counts). Operator pre-authorizes via gate-path AskUserQuestion OR plain-chat "yes" if classifier soft-blocks. **EXPECT BLOCKS PER-INVOCATION** per NEW C.D-arc lesson #2.

**Production state post-gate:** ZERO unresolved-material discrepancies preserved; banner count restored to 0 after S4 cleanup. **Production state CLEAN.** No false-positive multi-leg auto-redirects going forward (architectural fix landed end-to-end via 11 tasks).

---

## §4 OUT OF SCOPE (do not do)

- **Schema additions or migrations** — F1 + F19 escalation rule. If implementer encounters a need for schema element NOT in plan §A + spec §3, STOP + escalate to orchestrator BEFORE adding inline.
- **Override of any §0.6 LOCK** — all 14 decisions are operator-locked + brainstorm-locked + writing-plans-Codex-locked. Re-litigation is NOT permitted within executing-plans scope.
- **Re-litigation of plan §A acceptance criteria** — all per-task LOCKs via writing-plans Codex R5 convergence; do NOT re-open.
- **Pass-1 widening or `apply_tier1_correction` external-surface modification** — F2. Pass-1 stays Pass-1.
- **Sub-bundle C.B Shape A + Shape B predicate modifications** — UNCHANGED. Only Shape C-equivalent multi-leg recipe synthesis added.
- **Sub-bundle 1+1.5 mapper/executions field modifications** — UNCHANGED. Only consumer-side read at `_orders_to_classifier_payload`.
- **`/schwab/status` + `/schwab/setup` web routes** — UNCHANGED. Sub-bundle 2 surfaces preserved (T-1.8 retrofits `SchwabSetupVM` + `SchwabStatusVM` + `SchwabSetupErrorVM` for the new field only).
- **Dedicated `/metrics/auto-redirects` review page** — operator rejected V1 per §0.6 #4 (spec §2.4 LOCK + §14 #3 V2 candidate).
- **`_RESOLVED_BY_VALUES` Python constant formalization** — F7 + spec §14 #6 + §13.3 V2.1 §VII.F amendment V2.
- **Defensive cap on N legs** — F10 + §0.6 #7 + spec §14 #5 V2.
- **Other tier-2 ambiguity_kinds auto-redirect** — spec §14 #12 V2. Phase 12.5 #1 LIFT scope = `multi_partial_vs_consolidated` ONLY.
- **Schwab cassette recording for multi-leg fill** — spec §14 #4 V2; operator-paired session; defer until production multi-leg fill surfaces.
- **Behavioral changes to non-touched surfaces** — plan §C.3 LOCK. Especially: `apply_tier1_correction` UNCHANGED; `swing/integrations/schwab/mappers.py` + `swing/integrations/schwab/models.py` UNCHANGED; `swing/web/routes/schwab.py` UNCHANGED; `swing/data/migrations/0019_*.sql` UNCHANGED; `swing/trades/reconciliation_ambiguity_choices.py` operator menu UNCHANGED.
- **Phase 12.5 #2 work** — Web Tier-2 discrepancy-resolution surface is Phase 12.5 #2 scope; separate executing-plans dispatch after Phase 12.5 #1 ships.
- **Phase 12.5 #3 work** — Project hygiene maintenance pass (CLAUDE.md+orchestrator-context archive-split + V2.1 §VII.F amendment batch + Phase 8 walkthrough failing-test triage + Ruff 18 E501 cleanup); separate dispatch.

---

## §5 Return report shape

After all 11 tasks land + Codex chain converges + before final return-report commit, draft a return report at `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-executing-plans-return-report.md` (mirroring `docs/phase12-bundle-C-D-return-report.md` + `docs/post-phase12-schwab-mapper-bundle-1-return-report.md` shape):

1. Final HEAD on branch + commit count breakdown (11 task-impl + N Codex-fix + 1 return-report).
2. Codex round chain (R1-RN summary table + convergent shape; finding-count taper).
3. Test count delta + ruff baseline delta + schema version delta (**v19 unchanged** — Phase 12.5 #1 touches no schema per F1).
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate; 6 surfaces per plan §H).
5. Per-task deviations from plan (if any) with rationale + V2.1 §VII.F amendment candidates banked.
6. Codex Major findings ACCEPTED with rationale (if any). **Target: ZERO ACCEPT-WITH-RATIONALE** matching Phase 12.5 #1 brainstorm + writing-plans clean-record precedent + Sub-bundle 1+1.5+2 clean-record streak.
7. Watch items for orchestrator (V2 candidates surfaced; Phase 12.5 #2 dispatch readiness).
8. Worktree teardown status.
9. Per-task disposition LOCKS (any task-level decisions worth banking).
10. Forward-binding lessons for future bundles (especially Phase 12.5 #2 + #3).
11. CLAUDE.md status-line refresh draft text for orchestrator paste-in at integration-merge time (mirror writing-plans return report §8 draft shape).
12. Composition-surface verification: `^def ` grep on `swing/trades/reconciliation_classifier.py` + `swing/trades/reconciliation_auto_correct.py` + `swing/trades/reconciliation_backfill.py` + `swing/metrics/discrepancies.py` confirming public surface matches plan §A acceptance criteria.
13. Pre-existing Phase 7 + 8 + 9 + 10 + 11 + 12 LOCK regression evidence (`apply_tier1_correction` external surface UNCHANGED; Sub-bundle C.B Shape A + Shape B preserved; mapper/executions UNCHANGED; `/schwab/status` + `/schwab/setup` UNCHANGED).
14. F1-F25 invariants verification matrix (each invariant + per-invariant evidence of preservation).
15. 18 forward-binding lessons consumption verification (12 inherited + 6 NEW L-W1..L-W6 each addressed in implementation).

---

## §6 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES — per §1.1.
- **Model:** defer to harness default.
- **Expected duration:** ~6-10 hr implementation + ~2-4 hr Codex chain + 6-surface operator-witnessed gate. Total **~2-3 days operator-paced** (calibrated 3-5x per `feedback_time_estimates_overstated.md`).

---

## §7 If you get stuck

- If plan §A binding contracts conflict with what spec §1-§13 says, **plan wins** (writing-plans Codex R5 chain ratified plan §A; spec is upstream input).
- If a Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly in return report. **Target: ZERO ACCEPT-WITH-RATIONALE** matching Phase 12.5 #1 brainstorm + writing-plans + Sub-bundle 1+1.5+2 precedent.
- If you need a schema element NOT in plan §A + spec §3, **STOP + escalate** (F1 + F19 plan-author schema additions escalation rule; bank-after-write costs 2-3 cascade-cleanup rounds).
- DO NOT propose new classifier sub-classifiers within Phase 12.5 #1 scope (§4 lock; only `_classify_unmatched_fill_shared` widening permitted).
- DO NOT propose web Tier-2 surface within Phase 12.5 #1 scope (§4 lock; Phase 12.5 #2 candidate).
- DO NOT propose schema additions within Phase 12.5 #1 scope (§4 lock; F1 + F19 escalation rule family).
- DO NOT add `Co-Authored-By` footer to any commit message (per §1.3 + F5; ~95+ cumulative ZERO drift; **DO NOT regress**).
- DO NOT propose Pass-1 widening or `apply_tier1_correction` external-surface modification (F2 + §4 lock).
- DO NOT propose `_RESOLVED_BY_VALUES` Python constant (F7 + §0.6 #14; brief-writer error caught at brainstorm).
- DO NOT propose `max(...)` proportional override on `price_tolerance` (F9 + §0.6 #5; spec §15.B #1 LOCK).
- DO NOT propose defensive cap on N legs (F10 + §0.6 #7).
- DO NOT propose dedicated `apply_tier1_split_into_partials_auto` handler (§0.6 #3; reuse `apply_tier2_resolution` with overrides).
- If you encounter a Phase 7/8/9/10/11/12-A/12-B/12-C-A/12-C-B/12-C-C/12-C-D/post-Phase-12-Sub-bundle-1/1.5/2 lesson that conflicts with a Phase 12.5 #1 implementation proposal, the prior-phase lesson wins (validated by ship-experience). Surface the conflict as a constraint.
- If Codex pushes back on **F20 — Backfill is OPERATIONAL firing site** LOCK (e.g., "but pivot loop could synthesize source_payload via different path..."), HOLD THE LINE — the LOCK is plan §F20 + R1 Critical #1 fix at writing-plans time. Initial pivot's `_extract_source_payload` returns None for `unmatched_*_fill` sentinels; recipe can ONLY be emitted via the backfill Pass-2 path where `_orders_to_classifier_payload` builds list-shape `source_payload` from freshly-fetched Schwab orders with execution-grain data.
- If Codex pushes back on **F21 — `InvalidOverrideComboError` propagates** LOCK (e.g., "but graceful-degradation contract should absorb..."), HOLD THE LINE — the LOCK is plan §F21 + spec §7.4 R4 M2 LOCK + lesson #11. Developer-bug fail-fast is intentional; absorbed into graceful-degradation hides the bug-detection signal.
- If Codex pushes back on **F22 — "applied this run" wording** LOCK (e.g., "but adjacent line uses 'last 7 days'..."), HOLD THE LINE — the LOCK is plan §F22 + spec §11.2 LOCK + R1 Major #2 fix. The new counter is per-run; legacy tier-1 line is 7-day window; different semantics.
- If Codex pushes back on **F23 — TEMPLATE-MOUNT retrofit scope** LOCK (e.g., "field-presence proxy is simpler..."), HOLD THE LINE — the LOCK is plan §F23 + R1 Major #3 fix. Field-presence misses `AccountSnapshotFormVM` which inherits via `BaseLayoutVM` without explicit field declaration.
- If Codex pushes back on **F24 — dict-branch `executions` normalization** LOCK (e.g., "passthrough is sufficient..."), HOLD THE LINE — the LOCK is plan §F24 + R1 Major #4 fix. Cassette/replay fixtures pre-Phase-12.5 #1 lack `executions` keys; absent normalization causes cassette-vs-production shape contract drift.
- If Codex pushes back on **F25 + L-W6 — dict-only predicate contract** LOCK (e.g., "predicate could accept dataclass for convenience..."), HOLD THE LINE — the LOCK is plan §F25 + L-W6 + R1 minor #1 fix. Conversion seam owned by ONE task (T-1.3) at backfill→classifier boundary; predicate purity preserved.
- **Pre-Codex orchestrator-side review (NEW C.C lesson #6 — BINDING)**: before invoking `copowers:adversarial-critic`, dispatch a focused reviewer subagent with the plan §A acceptance criteria + brief §0.6 BINDING contracts + brief §0.7 F1-F25 invariants + brief §0.8 18 lessons as anchors; ask for a deviation list ≤600 words. Cheap; absorbs LOCK divergences pre-Codex; saved 1-2 Codex rounds on C.C + 2 absorbed Majors on C.D + 1 absorbed Major + 1 absorbed Minor on Sub-bundle 1 + 2 absorbed findings on Phase 12.5 #1 brainstorm + 2 absorbed findings on writing-plans. **Apply explicitly here.**

---

## §8 Operator-paired gate notes

Phase 12.5 #1's 6-surface gate is medium-sized (matches Sub-bundle 1+2 + C.C 4-7-surface mid-cycle precedents). Plan for an operator-paired session:

- **No mid-dispatch operator pause required** (unlike post-Phase-12 Sub-bundle 1's cassette session — Phase 12.5 #1 is fully synthetic-fixture-driven; no operator interaction needed during implementation phase).
- **Production refresh-token clock** — expires ~2026-05-22T17:05; verify TTL > 1hr at S3 pre-check; operator re-auths via `/schwab/setup` web form OR `swing schwab setup` CLI if needed.
- **Production-write classifier soft-block** — S3 fetch + S4 banner-plant are production-writes from classifier perspective; operator pre-authorizes via gate-path AskUserQuestion OR plain-chat "yes" PER INVOCATION (C.D-arc lesson #2).
- **One command at a time** — per operator preference (handoff brief §0 LOCK); orchestrator sends ONE command per turn, waits for output, verifies, sends next.
- **Worktree-side web server** — S4 uses `swing web --port 8081` (NOT 8080); stop the server when S4 done.
- **S2 + S6 are CANDIDATES for SKIPPED-with-test-coverage** — operator's preference at gate-time. If T-1.1 + T-1.2 + T-1.4 fast tests cover S2 cases AND T-1.11's `test_briefing_md_emits_multi_leg_line_when_count_gt_zero` covers S6, may skip without scope contortion (matches polish-bundle-2026-05-10 precedent).
- **Operator-architectural-pushback STOP-and-recover** — if S3+S4 surface architectural divergences (e.g., unexpected reconciliation_discrepancies emit; unexpected banner behavior under tier-3 override), STOP, investigate, recover (C.D-arc lesson #1). NOT push-through.
- **S4 cleanup discipline** — banner-plant inserts synthetic SQL state; revert via UPDATE rollback OR `apply_tier3_override` chain head OR re-resolve as `acknowledged_immaterial` per C.D gate-cleanup precedent. Production state MUST be restored to ZERO unresolved-material discrepancies post-gate.

---

*End of brief. Phase 12.5 #1 executing-plans dispatch — 11 tasks T-1.1 .. T-1.11; 14 pre-locked decisions encoded; 25 binding invariants F1-F25 enforced; 18 forward-binding lessons (12 inherited + 6 NEW L-W1..L-W6); schema v19 UNCHANGED; ~+102 fast tests + 1 slow E2E + ~+435 LOC projection. Codex chain projected 3-5 rounds. Expected duration ~2-3 days operator-paced including 6-surface operator-witnessed gate.*
