# Phase 12.5 #1 — OQ-F Multi-Leg Tier-1 Auto-Redirect — Executing-plans Return Report

**Status:** SHIPPED on branch `phase12-5-bundle-1-oqf-executing-plans`. Pending operator-witnessed gate (6 surfaces per plan §H) + orchestrator integration merge.

**Final HEAD:** `ebb05a8` (16 commits on top of baseline `d9ac13c`).

---

## 1. Final HEAD on branch + commit count breakdown

`ebb05a8` on `phase12-5-bundle-1-oqf-executing-plans`. 16 commits = 11 task-impl + 2 task-review-fixes + 1 T-1.2 cross-bundle-pin follow-up + 2 Codex-fix.

| # | SHA | Stem | Origin |
|---|---|---|---|
| 1 | `85186a0` | T-1.1 predicate + recipe synthesizer | task-impl |
| 2 | `33b0bdc` | T-1.1 review-fix (dead helper + reason text split) | task-review-fix |
| 3 | `2dcd7d3` | T-1.2 classifier integration | task-impl |
| 4 | `644b8d1` | T-1.2 review-fix (dead test scaffolding) | task-review-fix |
| 5 | `c89e3da` | T-1.3 executions on Pass-2 candidate dicts | task-impl |
| 6 | `bde6d70` | T-1.4 override-kwargs + validator + InvalidOverrideComboError | task-impl |
| 7 | `3a4b7c3` | T-1.2 cross-bundle pin follow-up (`tests/integration/test_phase12_bundle_c_cross_bundle_pin.py`) | regression-fix |
| 8 | `02657ee` | T-1.6 sandbox short-circuit | task-impl |
| 9 | `c2a950e` | T-1.5 pivot + backfill auto-redirect dispatch + slow E2E | task-impl |
| 10 | `e06a448` | T-1.7 count_recent_multi_leg_auto_corrections | task-impl |
| 11 | `070bbc1` | T-1.8 BaseLayoutVM retrofit across 17 VMs | task-impl |
| 12 | `63161ce` | T-1.9 base.html.j2 banner block | task-impl |
| 13 | `17e4cb1` | T-1.10 --resolved-by CLI filter | task-impl |
| 14 | `6cef015` | T-1.11 canary + briefing.md +1 line | task-impl |
| 15 | `fd6bb1b` | Codex R1 fix (slow E2E 3-leg + T-1.7 helper) | Codex-fix |
| 16 | `ebb05a8` | Codex R2 fix (action preservation + unreachable sandbox infra deletion) | Codex-fix |

Note: T-1.6 was committed BEFORE T-1.5 (lines 8 + 9 above) per dispatch decision — T-1.5's pivot-loop + backfill catch ladders reference T-1.6's `_SandboxAutoRedirectShortCircuit` sentinel; landing the sentinel first avoids fake-skipping tests. Plan §A T-1.5 dependency note explicitly permits this ordering.

---

## 2. Codex round chain

| Round | Critical | Major | Minor | Verdict |
|-------|----------|-------|-------|---------|
| R1 | 0 | 3 | 1 | ISSUES_FOUND |
| R2 | 1 | 1 | 0 | ISSUES_FOUND |
| R3 | 0 | 1 | 1 | ISSUES_FOUND |
| R4 | 0 | 0 | 1 | **NO_NEW_CRITICAL_MAJOR** |

**Cumulative:** 1 Critical + 5 Major + 3 Minor across 4 rounds. **All Critical + Major dispositioned.**

**Convergent shape:** R1→R2 spike on Critical (R2 surfaced the `_handle_split_into_partials` action-preservation bug — a pre-existing latent defect in Sub-bundle C.C's handler that Phase 12.5 #1's auto-redirect newly exposed by routing close-fill discrepancies through the same path). R2→R3→R4 monotonic Major taper.

---

## 3. Test count delta + ruff baseline + schema version

- **Test count:** 4360 (baseline `d9ac13c`) → **4705 fast passing** at HEAD (**+345 net**). 4 pre-existing failures — 3 `tests/integration/test_phase8_pipeline_walkthrough.py` + 1 `tests/integrations/test_schwab_setup_cli.py::test_setup_auth_failure_audit_status_and_sentinel_redaction` — **all verified pre-existing on baseline `d9ac13c` via git-checkout-and-run; NOT introduced by Phase 12.5 #1**. 5 skipped. Above projection (~+102) by ~3× — matches Phase 9/10/12 overshoot precedent. (The 4th failure was intermittently surfaced in Phase 12 Sub-sub-bundle C.A return report as "now resolved"; it appears flaky.)
- **Slow E2E:** `tests/trades/test_backfill_auto_redirect_dispatch.py::test_e2e_phase12_5_1_full_flow_through_backfill_to_banner_count` PASS.
- **Ruff baseline:** 18 E501 UNCHANGED.
- **Schema version:** v19 UNCHANGED. F1 LOCK preserved end-to-end. F19 plan-author schema additions escalation rule NOT triggered.

---

## 4. Operator-witnessed verification surfaces

PENDING orchestrator-driven gate (6 surfaces per plan §H + dispatch brief §3):

| Surface | Type | Status |
|---|---|---|
| S1 | Inline pytest + ruff + slow E2E | PENDING |
| S2 | Synthetic-fixture predicate matrix walk-through | PENDING (candidate for SKIPPED-with-test-coverage per polish-bundle-2026-05-10 precedent — T-1.1 + T-1.2 + T-1.4 fast tests cover every spec §10 case) |
| S3 | Production fetch end-to-end (`python -m swing.cli schwab fetch --orders --environment production`) | PENDING |
| S4 | Banner UI plant + clear (synthetic SQL fixture; curl `/`) | PENDING |
| S5 | CLI `--resolved-by` filter (`python -m swing.cli journal discrepancy list --resolved-by auto_tier1_multi_leg`) | PENDING |
| S6 | Briefing.md +1 line (`python -m swing.cli pipeline run` + grep) | PENDING (candidate for SKIPPED-with-test-coverage — T-1.11's `test_briefing_md_emits_multi_leg_line_when_count_gt_zero` covers the assertion) |

Production refresh-token clock expires ~2026-05-22T17:05 (~5 days remaining at brief drafting time; safe through gate). Operator re-auths via `/schwab/setup` web form OR `swing schwab setup` CLI if needed. Production-write classifier soft-block expected per-invocation on S3+S4 per NEW C.D-arc lesson #2.

---

## 5. Per-task deviations from plan with rationale + V2.1 §VII.F amendment candidates

### V2.1 §VII.F amendment candidates banked (1 NEW)

1. **Plan §A T-1.5.B + §F drift after Codex R2 Major #1 deletion.**
   - **Source:** Codex R2 Major #1 — established that `auto_redirect_skipped_sandbox` outcome path is structurally unreachable because `_pass_2_dispatch` short-circuits sandbox BEFORE classification per Sub-bundle C.D §9.7 LOCK.
   - **Plan references to amend:**
     - Plan §A T-1.5.B line 263 — list of 3 new BackfillSummary counters mentions `auto_redirect_skipped_sandbox`; should be reduced to 2 (`tier1_multi_leg_auto_redirected` + `projection_auto_redirect` only).
     - Plan §A T-1.5.B line 402 (acceptance #3 "Sandbox no-mutation") — describes the deleted pre-check path; should be removed or rewritten to note the real sandbox flow short-circuits in `_pass_2_dispatch`.
     - Plan §A T-1.5.B line 408 (acceptance #9 "BackfillSummary counter wiring") — references "3 NEW counter fields"; should be "2 NEW counter fields".
   - **Resolution at executing-plans:** deleted unreachable infrastructure at `ebb05a8`. T-1.6 service-layer `_SandboxAutoRedirectShortCircuit` + pivot-loop `sandbox_auto_redirect_skipped_count` PRESERVED per F20 + spec §7.6 LOCK (those live on reachable defensive future-proofing paths in the pivot loop, NOT the deleted-as-unreachable backfill paths).
   - **V2.1 §VII.F maintenance pass:** straightforward 3-line plan amendment.

### Per-task deviations (non-amendment)

- **T-1.1 deviation:** per-leg outlier reason cites the WORST outlier (max abs-delta) instead of first-walked. Acceptable per spec §5.4 forensic-transparency intent + matches the test fixture's `"leg #3"` substring assertion. No amendment needed.
- **T-1.2 deviation:** `candidate_choices` swap added on n=1 reclassification path (not enumerated in plan §A but required for cross-column CHECK + operator-facing menu consistency once `ambiguity_kind` flips to `multi_partial_vs_consolidated`). Routes through existing `_candidate_choices_multi_partial_vs_consolidated` helper — NO new handler key. Plan-author oversight; not worth banking as amendment.
- **T-1.3 deviation:** added 7th test (`test_orders_to_classifier_payload_multi_order_mix_dict_and_dataclass`) beyond plan's 6 — defense-in-depth F24 list-level invariant pin. Harmless.
- **T-1.4 deviation:** new `_read_discrepancy_resolved_by` helper added next to `_select_discrepancy` (rather than widening `_DiscrepancyInfo` dataclass); new private constant `_AUTO_REDIRECT_RESOLVED_BY = 'auto_tier1_multi_leg'` (single-literal naming alias, NOT an allowlist — F7 preserved). `_handle_split_into_partials` return shape — `CorrectionResult.correction_action` now reads `effective_correction_action` (was hardcoded `'operator_resolved_ambiguity'`) so the auto-redirect path's `CorrectionResult` carries `'auto_applied'` end-to-end per F15. All acceptable.
- **T-1.5 deviation:** Codex R1 Major #1 + #2 surfaced gaps in initial slow E2E (3 rows vs 4; direct SQL vs T-1.7 helper); fixed at `fd6bb1b`. Codex R2 Major #1 surfaced unreachable `auto_redirect_skipped_sandbox` infrastructure; deleted at `ebb05a8` (banked as V2.1 §VII.F amendment candidate above).
- **T-1.6 deviation:** ordered BEFORE T-1.5 in commit graph (per dispatch decision; plan permits via dependency note). T-1.6 commit `02657ee` + T-1.5 commit `c2a950e`.
- **T-1.8 deviation:** retrofitted 18 VM types (17 view_model files + base.html.j2 retrofit) — plan §A enumerated 17 files; the canonical TEMPLATE-MOUNT survey produced 18 VM types across 17 view_model files (3 SchwabVMs + 4 TradesVMs collapsed into 2 files). All actually-required surfaces covered.
- **T-1.11 deviation:** added 2 extra tests (`test_briefing_md_renders_section_when_only_multi_leg_count_nonzero` + `test_build_briefing_view_model_threads_new_counter`) beyond plan's 9 — defense-in-depth predicate-widening + VM-builder-seam pins. Harmless. `BriefingViewModel` lives in `swing/rendering/view_models.py` (not `swing/rendering/briefing.py` as plan suggested) — corrected location, no impact.
- **Codex R2 fix scope expansion (`ebb05a8`):** fixed a Sub-bundle C.C pre-existing latent defect (`_handle_split_into_partials` hardcoded `action="entry"` would corrupt close-fill cases). Auto-redirect significantly widened exposure since it fires WITHOUT operator review. Fix is at the handler (not just the auto-redirect path), so the manual-menu path is also now safe for close-fill split_into_partials. Two discriminating regression tests added (close-fill preserves 'exit'; open-fill preserves 'entry').

---

## 6. Codex Major findings ACCEPTED with rationale

**1 ACCEPT-WITH-RATIONALE banked** — falls 1 short of brief's ZERO ACCEPT-WITH-RATIONALE target.

1. **R1 Major #3 — "Banner text doesn't render F22 verbatim 'applied this run' wording."** Disposition: **FALSE POSITIVE — accepted with rationale (not a real defect).**
   - **Rationale:** F22 in plan §F (lines 808-839) governs BRIEFING.md per-run counter wording ONLY ("Briefing.md per-run counter wording is 'applied this run' verbatim per spec §11.2 LOCK"). The banner template at `base.html.j2` has its OWN spec-§8.3 + plan §A T-1.9 lines 599-601 wording ("`{N} multi-leg auto-correction{s} in most recent reconciliation run. Review via swing journal discrepancy list --resolved-by auto_tier1_multi_leg`"). Two distinct surfaces with two distinct lock'd wordings; both correct per their respective spec sections. Codex's finding was surfaced by my round-1 priority-anchor text being imprecise (I extended F22 to "both surfaces" when F22 is briefing-only).
   - **Cause:** orchestrator-side imprecision in the pre-Codex priority-anchor synthesis; not a code or design defect.
   - **No code change needed.** Both surfaces verified verbatim-correct: briefing emits `"- Multi-leg auto-redirects applied this run: K"` at `swing/rendering/briefing_md.py:108-111`; banner emits "in most recent reconciliation run" at `swing/web/templates/base.html.j2:117-121`.

---

## 7. Watch items for orchestrator

### V2 candidates surfaced

1. **Schwab cassette recording for multi-leg fill** — spec §14 #4 V2; operator-paired session; defer until production multi-leg fill surfaces. Until then, the T-1.6 sandbox short-circuit + the deleted backfill sandbox infrastructure remain unreachable in V1.
2. **Loosen Sub-bundle C.D §9.7 LOCK** to allow sandbox cassette replay through `_pass_2_dispatch` → would re-enable an `auto_redirect_skipped_sandbox` outcome path (if re-introduced). Defer until cassette infrastructure lands.
3. **Close-fill backfill slow E2E fixture** — R3 Minor #1. Close-fill backfill goes through the SAME service handler as open-fill (no separate handler key); slow E2E covers open-fill; close-fill structural symmetry is enforced by Codex R2 Critical fix at the handler + the two new regression tests. V2 hardening if close-fill production case surfaces.
4. **Defensive `isinstance(executions, list)` guard in predicate** — R1 Minor #1. F24/F25/L-W6 contract enforces dict-form executions upstream; predicate scalar-type guard is defensive hardening for test-internal fixtures only. V2 polish.

### Phase 12.5 #2 readiness

Phase 12.5 #2 (web Tier-2 discrepancy-resolution surface) dispatch UNBLOCKED. Consumes:
- `apply_tier2_resolution` outer surface (no change; override kwargs default-None preserve legacy behavior per F3).
- `_handle_*` registry (no change; back-compat preserved).
- BackfillSummary + format_summary_block (no change).
- T-1.7 metric helper (no change).
- BaseLayoutVM retrofit (no change; Phase 12.5 #2's new web tier-2 form VM inherits the field automatically).
- Banner + CLI filter (no change).

### Phase 12.5 #3 readiness

Phase 12.5 #3 (project hygiene maintenance pass) NOW HAS:
- 1 NEW V2.1 §VII.F amendment candidate (this report §5).
- 5 NEW gotcha promotion candidates banked at the orchestrator's discretion (see §9).

---

## 8. Worktree teardown status

- **Branch:** `phase12-5-bundle-1-oqf-executing-plans` — local + tracking origin.
- **Worktree:** `.worktrees/phase12-5-bundle-1-oqf-executing-plans/` — present + intact; HEAD `ebb05a8`.
- **Marker file:** `.copowers-subagent-active` — REMOVED before adversarial-critic invocation (per dispatch brief §1.2).
- **Pending:** operator's `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass post-integration-merge. Branch matches cleanup-script regex `phase\d+[-_]` per dispatch brief §1.1.
- **Husks pending operator cleanup:** 3 (this branch + 2 prior brainstorm/writing-plans worktrees from Phase 12.5 #1 chain).

---

## 9. Per-task disposition LOCKS

Task-level decisions worth banking:

- **T-1.1 outlier-reason discipline:** worst-outlier (max abs-delta) is the project-locked attribution form for forensic-transparency reasons (spec §5.4). Future predicates that emit per-element decline reasons should adopt this.
- **T-1.4 single-literal naming alias pattern:** `_AUTO_REDIRECT_RESOLVED_BY: str = 'auto_tier1_multi_leg'` is a single-literal `str` (NOT an allowlist set/frozenset). Future readability aliases for free-TEXT enum values should follow this pattern to avoid F7-style scope drift.
- **T-1.5 dispatch ordering:** T-1.6 can land BEFORE T-1.5 when the dependency runs "child catches parent's exception class". Plan-numbered ordering is logical-architectural; commit-ordering can deviate when compile-and-test sequencing demands.
- **T-1.8 TEMPLATE-MOUNT retrofit completeness:** the canonical mechanism is template-extension grep, NOT field-presence on prior banner fields. Future base-layout VM retrofits should use the F23 introspection test pattern.
- **Codex R2 Critical fix scope:** when a fix addresses a pre-existing defect surfaced by the new work (here, `_handle_split_into_partials` action-preservation bug surfaced by Phase 12.5 #1's auto-redirect routing close-fill discrepancies through the handler), the fix lands AT THE HANDLER (not just the new-work caller) — benefits all callers + matches the failure-mode site.

---

## 10. Forward-binding lessons for future bundles

**1 NEW lesson surfaced during this dispatch (L-X1):**

- **L-X1 (Codex R2 Critical):** When extending an existing handler's reach via auto-routing (e.g., auto-redirect through `_handle_split_into_partials`), AUDIT the handler for hardcoded values that were "safe" under the prior narrow-routing assumption. The handler may have been correct for the original call path (manual operator-resolved menu picks the right cases) but unsafe for the wider auto-routed call path. Discriminating test pattern: route the new auto-path through the handler with EACH supported parent-shape (open-fill AND close-fill; new + canceled; etc.), assert each preserves shape-specific invariants. Future dispatches that extend a service handler's reach via auto-routing should do this audit upfront.

**12 inherited from brainstorm + 6 NEW from writing-plans (L-W1..L-W6 per plan §M) — all consumed during executing-plans:**

- L-W1 (R1 Critical #1 writing-plans): Dispatcher pattern + recipe consumption — enumerate every dispatcher consumer. Honored at T-1.5 (BOTH initial-pivot AND backfill wired per F20).
- L-W2 (R1 Major #1 writing-plans): Spec-locked exception-propagation contracts encoded as catch-ladder ordering, not graceful-degradation alignment. Honored at T-1.5 (`except InvalidOverrideComboError: raise` FIRST per F16+F21).
- L-W3 (R1 Major #2 writing-plans): Spec-locked rendering text verbatim-asserted in tests. Honored at T-1.11 (`"applied this run"` substring assertion).
- L-W4 (R1 Major #3 writing-plans): Retrofit scope by canonical mechanism (template-mount), not proxy field-presence. Honored at T-1.8 (F23 TEMPLATE-MOUNT introspection test).
- L-W5 (R1 Major #4 writing-plans): Helper functions emit stable key-set across all input branches. Honored at T-1.3 (F24 dict-branch normalization).
- L-W6 (R1 minor #1 writing-plans): Conversion seam owned by ONE task at module boundary. Honored at T-1.3 (`_orders_to_classifier_payload` is the sole dataclass→dict seam; predicate consumes dict-only per F25).

---

## 11. CLAUDE.md status-line refresh draft text (for orchestrator paste-in at integration-merge time)

> **Phase 12.5 #1 (OQ-F multi-leg tier-1 auto-redirect) SHIPPED 2026-05-17** at `<MERGE_SHA>` (integration merge of `phase12-5-bundle-1-oqf-executing-plans` via `--no-ff`; 16 commits = 11 task-impl + 2 review-fixes + 1 cross-bundle-pin follow-up + 2 Codex-fix; **4 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent shape (R1 0C/3M/1m → R2 1C/1M/0m → R3 0C/1M/1m → R4 0C/0M/1m); **1 ACCEPT-WITH-RATIONALE banked** (R1 M#3 banner-vs-briefing wording false-positive — F22 governs briefing.md only, banner uses spec §8.3); +345 fast tests (4360 → 4705 main HEAD); ruff 18 E501 unchanged; schema v19 unchanged. **First V2 follow-up from post-Phase-12 mapper-widening spec §6.6 OQ-F shipped** — when Pass-2 `unmatched_*_fill` discrepancy carries multi-leg execution data that aligns within tolerance, the classifier auto-redirects to a tier-1-shape correction via the existing `_handle_split_into_partials` registry entry; operator never sees the manual `multi_partial_vs_consolidated` menu for these cases. New `_multi_leg_auto_redirect_predicate` + `_synthesize_split_into_partials_recipe` pure helpers (spec §4.3 6 sub-conditions; F25 dict-only contract); new `auto_redirect_recipe` field on `ClassificationResult`; new `_validate_override_combo` + `InvalidOverrideComboError(ValueError)` + 3 override kwargs threaded through `apply_tier2_resolution` family; new `_SandboxAutoRedirectShortCircuit` sentinel + sandbox short-circuit in `_apply_tier2_resolution_inner`; new `count_recent_multi_leg_auto_corrections` metric helper (COUNT(DISTINCT) per F18); banner block on base.html.j2 + `--resolved-by` CLI filter (in-bundle per spec §8.6 LOCK); briefing.md `## Reconciliation status` gains "Multi-leg auto-redirects applied this run: K" verbatim per F22; canary `logger.warning` on empty-executions case per spec §12.3. Codex R2 surfaced a Sub-bundle C.C latent defect (`_handle_split_into_partials` hardcoded `action="entry"` would have corrupted close-fill discrepancies via the new auto-routing path; fixed at handler with 2 discriminating regression tests + benefits manual operator-resolved menu path too) AND deleted unreachable `auto_redirect_skipped_sandbox` backfill infrastructure (collides with Sub-bundle C.D §9.7 LOCK upstream — T-1.6 service-layer + pivot-loop counter preserved per F20 + spec §7.6 LOCK). 1 V2.1 §VII.F amendment candidate banked (plan §A T-1.5.B 3-line drift after Codex R2 Major #1 deletion). 1 new forward-binding lesson L-X1 (handler-extension audit pattern when auto-routing widens a handler's reach). 6-surface operator-witnessed gate PENDING orchestrator-driven post-merge.

---

## 12. Composition-surface verification

`grep "^def "` + `^class` on touched modules confirms public + private surfaces match plan §A acceptance:

| Surface | Location | Plan §A task |
|---|---|---|
| `_multi_leg_auto_redirect_predicate` | `swing/trades/reconciliation_classifier.py:150` | T-1.1 |
| `_synthesize_split_into_partials_recipe` | `swing/trades/reconciliation_classifier.py:282` | T-1.1 |
| `_MULTI_LEG_PRICE_TOLERANCE`, `_MULTI_LEG_QTY_TOLERANCE` constants | `swing/trades/reconciliation_classifier.py:130-131` | T-1.1 |
| `ClassificationResult.auto_redirect_recipe` | `swing/trades/reconciliation_classifier.py` (6th field) | T-1.2 |
| `_orders_to_classifier_payload` (extended) | `swing/trades/reconciliation_backfill.py:433` | T-1.3 |
| `class InvalidOverrideComboError(ValueError)` | `swing/trades/reconciliation_auto_correct.py:92` | T-1.4 |
| `class _SandboxAutoRedirectShortCircuit(Exception)` | `swing/trades/reconciliation_auto_correct.py:105` (`noqa: N818` — spec-locked sentinel name) | T-1.6 |
| `_validate_override_combo` | `swing/trades/reconciliation_auto_correct.py:237` | T-1.4 |
| `_AUTO_REDIRECT_SANCTIONED_CHOICE_CODE` constant | `swing/trades/reconciliation_auto_correct.py:164` | T-1.4 |
| `_AUTO_REDIRECT_RESOLVED_BY` constant | `swing/trades/reconciliation_auto_correct.py:171` | T-1.4 |
| `_read_discrepancy_resolved_by` | `swing/trades/reconciliation_auto_correct.py:1036` | T-1.4 |
| `BackfillSummary` 2 new counters | `swing/trades/reconciliation_backfill.py:222-223` | T-1.5 |
| Pivot-loop branch | `swing/trades/schwab_reconciliation.py:525-647` | T-1.5 |
| Pivot-loop 2 new counters | `swing/trades/schwab_reconciliation.py:444-445` | T-1.5 |
| `_handle_pass_2` recipe consumption | `swing/trades/reconciliation_backfill.py:797+` | T-1.5 |
| `_format_pass_2_line` outcome annotation | `swing/trades/reconciliation_backfill.py:566+` | T-1.5 |
| `count_recent_multi_leg_auto_corrections` | `swing/metrics/discrepancies.py:83` | T-1.7 |
| `BaseLayoutVM.recent_multi_leg_auto_correction_count` | `swing/web/view_models/metrics/shared.py:57` | T-1.8 |
| Banner block | `swing/web/templates/base.html.j2:117-121` | T-1.9 |
| `--resolved-by` Click option | `swing/cli.py:2065-2073` | T-1.10 |
| Predicate canary | `swing/trades/reconciliation_classifier.py:198-204` | T-1.11 |
| `BriefingInputs.reconciliation_tier1_multi_leg_redirected_count` | `swing/rendering/briefing.py:90` | T-1.11 |
| `BriefingViewModel.reconciliation_tier1_multi_leg_redirected_count` | `swing/rendering/view_models.py:151` | T-1.11 |
| `## Reconciliation status` block extension | `swing/rendering/briefing_md.py:111-118` | T-1.11 |

---

## 13. Pre-existing LOCK regression evidence

- `apply_tier1_correction` external surface UNCHANGED (F2): `git diff d9ac13c..HEAD -- swing/trades/reconciliation_auto_correct.py` shows no signature change to `apply_tier1_correction`.
- Sub-bundle C.B Shape A + Shape B classifier preserved: T-1.2 added a NEW Shape C-equivalent path (multi-leg auto-redirect recipe) without touching Shape A (persisted-JSON-only `{'price'}`) or Shape B (full match-tuple).
- Sub-bundle 1 + 1.5 mapper / `SchwabExecutionLeg` / `SchwabOrderResponse.executions` UNCHANGED: T-1.3 only READS from `o.executions` at `_orders_to_classifier_payload`; no model changes.
- `/schwab/status` + `/schwab/setup` web routes UNCHANGED: T-1.8 retrofitted `SchwabSetupVM` + `SchwabStatusVM` + `SchwabSetupErrorVM` for the NEW field via builder population in `swing/web/routes/schwab.py:241,303,525` (FIELD added, business logic unchanged).
- Sub-bundle C.C `apply_tier2_resolution` legacy default behavior preserved (F3): all 3 new override kwargs default to None; pre-existing call sites work byte-for-byte. T-1.4's `test_apply_tier2_resolution_legacy_default_path_no_overrides_writes_operator_shape` pins this.
- `_handle_split_into_partials` action-preservation fix (Codex R2 Critical fix at `ebb05a8`) is a PRE-EXISTING defect inherited from Sub-bundle C.C; the fix benefits BOTH the new auto-redirect path AND the existing manual operator-resolved menu path. Two discriminating regression tests added.

---

## 14. F1-F25 invariants verification matrix

| Invariant | Status | Evidence |
|---|---|---|
| F1 ZERO new schema | ✓ | `EXPECTED_SCHEMA_VERSION == 19` unchanged; no `0020_*.sql`. |
| F2 ZERO change to `apply_tier1_correction` external surface | ✓ | Signature unchanged in diff. |
| F3 ZERO change to `apply_tier2_resolution` default behavior | ✓ | `test_apply_tier2_resolution_legacy_default_path_no_overrides_writes_operator_shape`. |
| F4 ZERO change to determinism principle | ✓ | Predicate is pure; T-1.1 includes determinism spot-check. |
| F5 NO `Co-Authored-By` footer | ✓ | `git log --format=%B d9ac13c..HEAD \| grep -c "Co-Authored-By"` → 0 across all 16 commits. |
| F6 NO `--no-verify` | ✓ | Process discipline — no commit invoked with `--no-verify`. |
| F7 `resolved_by` is free TEXT | ✓ | `grep -rn "_RESOLVED_BY_VALUES" swing/` → 0 matches. `_AUTO_REDIRECT_RESOLVED_BY` is single-literal `str` alias, NOT allowlist. |
| F8 qty_tolerance asymmetry preserved | ✓ | `_MULTI_LEG_QTY_TOLERANCE = 1e-9` (T-1.1); `_handle_split_into_partials` `qty_tolerance = 1e-6` UNCHANGED. |
| F9 `_MULTI_LEG_PRICE_TOLERANCE = 0.01` absolute | ✓ | Literal constant; no `max(...)` proportional override path. |
| F10 NO defensive cap on N legs | ✓ | T-1.1 test `test_predicate_fires_on_n_eq_2_with_multi_leg_each_5_total` covers 5 legs; no `MAX_LEGS_PER_ORDER` constant. |
| F11 All base-layout VMs inherit new field | ✓ | T-1.8 `test_every_subclass_of_base_layout_vm_inherits_recent_multi_leg_field` + `test_every_vm_with_unresolved_material_field_also_has_recent_multi_leg_field`. |
| F12 Banner ASCII-only | ✓ | T-1.9 `test_base_layout_multi_leg_banner_ascii_only` asserts `all(ord(c) < 128 for c in banner)`. |
| F13 SAVEPOINT-per-discrepancy preserved | ✓ | T-1.5 pivot-loop branch reuses outer `sp_name`; §7.5 fallback uses fresh `correction_fallback_sp_{id}`. |
| F14 Classifier purity preserved | ✓ | T-1.1 + T-1.2 helpers are pure; T-1.11 canary `logger.warning` is the ONE documented exception (per spec §12.3). |
| F15 Hybrid-row invariant | ✓ | T-1.4 `effective_*` triple computed ONCE + applied uniformly to N+1 rows + parent flip; `_validate_override_combo` rejects partial-auto combos. |
| F16 Exception specificity ordering | ✓ | T-1.5 catch ladder: `_SandboxAutoRedirectShortCircuit` first; `InvalidOverrideComboError: raise` second; `(ValidatorRejectedError, ValueError)` third with §7.5 fresh-savepoint fallback. |
| F17 Sandbox short-circuit in INNER not outer | ✓ | T-1.6 fires in `_apply_tier2_resolution_inner` at Step 2.6; outer only threads `environment` kwarg. |
| F18 Counter ROW-vs-LOGICAL semantics | ✓ | T-1.7 uses `COUNT(DISTINCT discrepancy_id)`; slow E2E asserts 1 logical redirect from 4 correction rows. |
| F19 Plan-author schema additions escalation | ✓ | NOT triggered (schema v19 unchanged throughout). |
| F20 Auto-redirect dispatch in BOTH consumers | ✓ | T-1.5 wires both pivot-loop (defensive future-proofing) AND backfill `_handle_pass_2` (operational firing site); slow E2E exercises backfill end-to-end. |
| F21 `InvalidOverrideComboError` propagates | ✓ | Pivot loop + backfill orchestrator both have `except InvalidOverrideComboError: raise` FIRST in catch ladder per F16. |
| F22 Briefing wording "applied this run" verbatim | ✓ | T-1.11 `test_briefing_md_emits_multi_leg_line_when_count_gt_zero` asserts verbatim substring; `swing/rendering/briefing_md.py:111-118` emits literal. |
| F23 VM retrofit by TEMPLATE-MOUNT | ✓ | T-1.8 `test_every_base_layout_template_renders_vm_with_recent_multi_leg_field` enumerates by `{% extends "base.html.j2" %}` grep. |
| F24 `_orders_to_classifier_payload` dict-branch normalizes absent `executions` to None | ✓ | T-1.3 `test_orders_to_classifier_payload_dict_input_without_executions_key_normalized_to_none`. |
| F25 Predicate consumes dict-shaped executions only | ✓ | T-1.1 `test_predicate_consumes_dict_shaped_executions_only`; no `SchwabExecutionLeg` import in `reconciliation_classifier.py`. |

---

## 15. 18 forward-binding lessons consumption verification

**12 inherited from brainstorm return report §8 (all consumed):**

1. Recipe-field discipline — `auto_redirect_recipe=None` default preserves all existing emit paths (T-1.2).
2. Override-parameter threading with verbatim-existing default values (T-1.4 — all 3 new kwargs default to None).
3. Free-text vs CHECK-enum columns (F7 — no `_RESOLVED_BY_VALUES` constant introduced).
4. Cross-column CHECK invariants — `(ambiguity_kind, resolution)` pairing honored in T-1.2 n=1 reclassification + T-1.4 step 1.5 secondary check.
5. Sandbox short-circuit ALWAYS in inner (F17 — T-1.6 in `_apply_tier2_resolution_inner`).
6. Helper invocation completeness across base-layout VMs (T-1.8 — 18 VM types covered via TEMPLATE-MOUNT introspection).
7. ASCII-only banner text (F12 — T-1.9 ASCII-only test).
8. Counter ROW-vs-LOGICAL semantics (F18 — T-1.7 COUNT(DISTINCT) + T-1.11 distinct-semantics test).
9. Validate override combos BEFORE state mutation (T-1.4 step 0 `_validate_override_combo` runs BEFORE `_select_discrepancy`).
10. Shape-aware terminal-state idempotency (T-1.4 step 2.5 — auto-redirect override against manual-resolved terminal raises).
11. Exception specificity ordering in catch blocks (F16 — T-1.5 catch ladder + F21 InvalidOverrideComboError propagation).
12. Positional-vs-keyword signature audit at writing-time (T-1.2 `ClassificationResult.auto_redirect_recipe` field added as LAST positional arg; field-order pin test).

**6 NEW writing-plans-surfaced (L-W1..L-W6) — all consumed (see §10 above for evidence).**

**1 NEW executing-plans-surfaced lesson (L-X1) — see §10 above.**

---

*End of return report. Phase 12.5 #1 executing-plans dispatch — 11 tasks T-1.1..T-1.11 SHIPPED at `ebb05a8`; 16 commits = 11 task-impl + 2 review-fixes + 1 cross-bundle-pin follow-up + 2 Codex-fix; 4 Codex rounds → NO_NEW_CRITICAL_MAJOR; 1 Critical + 5 Major + 3 Minor dispositioned (1 ACCEPT-WITH-RATIONALE banked as false-positive); +345 fast tests; schema v19 unchanged; ruff 18 E501 unchanged. 1 V2.1 §VII.F amendment candidate banked. 1 new forward-binding lesson (L-X1). 6-surface operator-witnessed gate PENDING orchestrator-driven post-merge.*
