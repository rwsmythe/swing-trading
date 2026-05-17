# Phase 12.5 #1 — OQ-F Multi-Leg Tier-1 Auto-Redirect — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `copowers:executing-plans` (wraps `superpowers:subagent-driven-development`) to implement this plan task-by-task in a SINGLE executing-plans dispatch. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Ship the V2 follow-up from post-Phase-12 mapper-widening spec §6.6 — when a Pass-2 `unmatched_*_fill` discrepancy carries multi-leg execution data that aligns within tolerance, the classifier auto-redirects to a tier-1-shape correction via the existing `_handle_split_into_partials` registry entry. The operator never sees the manual `multi_partial_vs_consolidated` menu for these cases.

**Architecture:** Three layers, single sub-bundle. (1) Classifier: extend `ClassificationResult` with `auto_redirect_recipe: Mapping[str, Any] | None = None`; widen `_classify_unmatched_fill_shared` `n>=2` AND `n=1` branches (the n=1 path reclassifies `ambiguity_kind` to `multi_partial_vs_consolidated` when `len(executions) >= 2`) to compute the multi-leg predicate (qty sum + VWAP + per-leg consistency, all-match-within-$0.01) and synthesize the recipe. (2) Service: parameterize `apply_tier2_resolution` outer + `_apply_tier2_resolution_inner` + `_build_tier2_correction` + every `_handle_*` helper with three new optional kwargs (`applied_by_override` / `correction_action_override` / `resolved_by_override`) defaulting to None (back-compat); add a shared `_validate_override_combo` helper + typed `InvalidOverrideComboError` (subclass of `ValueError`) enforcing the hybrid-row invariant; add sandbox short-circuit gated on `applied_by_override=='auto'` at the inner via `_SandboxAutoRedirectShortCircuit` exception + SAVEPOINT ROLLBACK. (3) Surfaces: pivot-loop branch consuming the recipe; `BaseLayoutVM.recent_multi_leg_auto_correction_count` retrofit across all base-layout VMs; banner block in `base.html.j2` citing the in-bundle `swing journal discrepancy list --resolved-by auto_tier1_multi_leg` CLI filter; briefing.md +1 line when the per-run counter > 0; canary observability hook for empty-executions case.

**Tech Stack:** Python 3.14, SQLite, Click CLI, FastAPI + HTMX + Jinja2, schwabdev SDK (consumer only — no SDK calls in this plan), pytest + pytest-xdist.

**Schema:** v19 **UNCHANGED LOCK** (spec §13.1 audit verified — corrections + discrepancies CHECK enums + cross-column CHECK + free-TEXT `resolved_by` already accommodate). NO migration in this plan. NO `0020_*.sql`.

---

## Table of contents

- §0 Plan overview + cross-references
- §A Task list (T-1.1 … T-1.11) — per-task scope + acceptance + tests + commit
- §B Pre-conditions + worktree state
- §C Files touched (canonical roster + grep anchors)
- §D Locked decisions roll-up (14 binding clauses, verbatim attribution)
- §E Test patterns + discriminating-test naming convention
- §F Invariants (non-negotiable contracts spanning multiple tasks)
- §G Per-task acceptance-criteria narrative (deeper-than-§A treatment for tasks that span multiple files)
- §H Operator-witnessed gate plan (6 surfaces)
- §I Cross-bundle pins (single-bundle dispatch; consumer of shipped Sub-bundle 1 + 1.5 + 2 surfaces)
- §J V2.1 §VII.F amendment candidates banked during planning (scaffold)
- §K Test + LOC projections (refined per-task summing to spec §9.2 + return report §10)
- §L Dispatch brief skeleton (orchestrator hand-off for executing-plans)
- §M Forward-binding lessons for executing-plans (scaffold; populated post-Codex)
- §N Open questions for orchestrator triage (scaffold; default empty)
- §Z V2 candidates banked (mirrored from spec §14)

---

## §0 Plan overview + cross-references

| Anchor | Location |
|---|---|
| Locked spec (1236 lines) | `docs/superpowers/specs/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-design.md` |
| Writing-plans dispatch brief | `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-writing-plans-dispatch-brief.md` (commit `5c988d2`) |
| Brainstorm return report (12 forward-binding lessons) | `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-brainstorm-return-report.md` |
| Brainstorm dispatch brief | `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-brainstorm-dispatch-brief.md` (commit `37b584d`) |
| Post-Phase-12 mapper-widening spec §6.6 OQ-F (predecessor) | `docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md` |
| Sub-bundle C plan (format reference) | `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` |
| Post-Phase-12 mapper-widening plan (format reference; closer scope) | `docs/superpowers/plans/2026-05-17-schwab-mapper-execution-grain-widening-plan.md` |

**Scope intent:** the brainstorm consumed 7 Codex rounds + ZERO ACCEPT-WITH-RATIONALE → the spec is exhaustively locked. The plan's job is **to operationalize the locked design**, NOT to re-derive it. Codex review on this plan should converge in 3-5 rounds because most architectural decisions are spec-locked.

**Cross-bundle position:** Phase 12.5 #1 is bracketed by Phase 12.5 #2 (web Tier-2 surface — separate dispatch) and Phase 12.5 #3 (project-hygiene maintenance pass — separate dispatch). Phase 12 Sub-bundle C (`reconciliation_classifier.py` + `reconciliation_auto_correct.py` + `reconciliation_backfill.py`) + post-Phase-12 Sub-bundle 1/1.5/2 (`schwab_reconciliation.py` comparator + `swing/integrations/schwab/models.py` `SchwabExecutionLeg`) are SHIPPED upstream surfaces — this plan is a pure read-only consumer.

---

## §A Task list

**Decomposition** — 11 tasks (T-1.1 … T-1.11) for a single executing-plans dispatch. Ordering is dependency-driven. Each task ends with a tiny commit; do not batch.

### Task T-1.1 — `_multi_leg_auto_redirect_predicate` + `_synthesize_split_into_partials_recipe` helpers (pure)

**Files:**
- Modify: `swing/trades/reconciliation_classifier.py` (add two module-level private functions near the top, before the `_classify_entry_price_mismatch` sub-classifier at line 125; new module-level constant `_MULTI_LEG_PRICE_TOLERANCE = 0.01`).
- Test: `tests/trades/test_reconciliation_classifier_multi_leg_predicate.py` (NEW)

**Acceptance:**

- New module-level constants `_MULTI_LEG_PRICE_TOLERANCE: float = 0.01` and `_MULTI_LEG_QTY_TOLERANCE: float = 1e-9` defined at top of `reconciliation_classifier.py` with explanatory comment citing spec §4.4 (operator §15.B #1 + #2 locks).
- New pure function `_multi_leg_auto_redirect_predicate(*, candidates: list[Mapping[str, Any]], journal_qty: float, journal_price: float, price_tolerance: float = _MULTI_LEG_PRICE_TOLERANCE) -> tuple[bool, str | None]` implements all 6 sub-conditions per spec §4.3:
    1. Every candidate has non-empty `executions` list (returns `(False, "...")` with the offending `order_id` in the reason).
    2. `len(all_executions) >= 2`.
    3. `sum(leg.quantity)` matches `journal_qty` within `1e-9` (predicate-stricter-than-handler asymmetry per spec §15.B #2 LOCK).
    4. Every leg's `price` and `quantity` are numeric (not `bool`), finite (`math.isfinite`), positive.
    5. `abs(VWAP - journal_price) <= price_tolerance` ($0.01 absolute).
    6. Per-leg consistency: `abs(leg.price - VWAP) <= price_tolerance` for every leg.
- Returns `(True, None)` only when ALL sub-conditions hold. Reason text on failure cites which sub-condition + the failing numeric values to aid forensic transparency (spec §5.4 correction_reason chain).
- New pure function `_synthesize_split_into_partials_recipe(candidates: list[Mapping[str, Any]]) -> Mapping[str, Any]` returns the `auto_redirect_recipe` dict per spec §6.1 with `choice_code='split_into_partials'`, `resolved_by='auto_tier1_multi_leg'`, `applied_by_override='auto'`, `correction_action_override='auto_applied'`, and the `payload` list built from per-leg `{qty: float(leg.quantity), price: float(leg.price), fill_datetime: str(leg.time)}` dicts. PRE-CONDITION (documented in docstring): caller MUST have invoked the predicate first.
- Both functions are pure: no DB, no API, no logging side-effects, no transaction management. They consume `Mapping` shapes (duck-typed for `SchwabExecutionLeg` instances and plain dicts).
- Both functions are at module scope — `from typing import Mapping` import (already present at line 14) is reused.

**Tests added (~17):**

- `test_predicate_fires_on_n_eq_1_with_3_legs_aligned` — Case A numerics: n=1 with executions=[100@5.30, 50@5.31, 50@5.30], journal_qty=200, journal_price=5.3025 → `(True, None)`.
- `test_predicate_fires_on_n_eq_2_with_1_leg_each` — Case B numerics: 2 candidates each with 1 leg, journal at the VWAP → `(True, None)`.
- `test_predicate_fires_on_n_eq_2_with_multi_leg_each_5_total` — Case I numerics → `(True, None)`.
- `test_predicate_declines_on_per_leg_outlier` — Case C: leg #3 at $5.34 outlier vs VWAP → `(False, reason)`; reason contains `"leg #3"` substring and the outlier price + VWAP delta.
- `test_predicate_declines_on_qty_sum_mismatch` — sum != journal_qty → `(False, reason)`; reason cites `"sum(executed qty)"`.
- `test_predicate_declines_on_vwap_journal_misalign` — Case E: VWAP $7.505 vs journal $7.55 → `(False, reason)`; reason cites `"VWAP"` + `"journal"` + delta.
- `test_predicate_declines_on_missing_executions_on_one_candidate` — Case F: candidate #2 `executions=None` → `(False, reason)`; reason cites `"order_id"` + `"no execution legs"`.
- `test_predicate_declines_on_empty_executions_on_one_candidate` — `executions=[]` empty list → `(False, reason)` at sub-condition 1 (canary path; see T-1.11).
- `test_predicate_declines_on_bool_price_defensive` — Case G: `leg.price=True` → `(False, reason)`; reason cites `"not numeric"`.
- `test_predicate_declines_on_nan_price_defensive` — Case H: `leg.price=float('nan')` → `(False, reason)`; reason cites `"not positive finite"`.
- `test_predicate_declines_on_negative_price_defensive` — `leg.price=-5.30` → `(False, reason)`.
- `test_predicate_declines_on_zero_qty_defensive` — `leg.quantity=0.0` → `(False, reason)`.
- `test_predicate_declines_on_insufficient_total_legs` — n=1 candidate with `executions=[1 leg only]` → `(False, reason)` at sub-condition 2 (`< 2` legs).
- `test_predicate_handles_schwab_execution_leg_instances_via_duck_typing` — pass actual `SchwabExecutionLeg` instances (not dicts) — must work via `.get('quantity')` substitute (use dict-form). NOTE: spec §4.1 lists candidates as `list[Mapping]`; ensure helpers consume `.get()` accessors; if SchwabExecutionLeg lacks `.get`, the comparator at T-1.3 is responsible for dict-conversion. Discriminating: test asserts a plain-dict synthetic input works end-to-end.
- `test_synthesize_recipe_shape_matches_spec_6_1` — predicate True → recipe dict has all 5 expected keys + payload is a list of N partial dicts with `{qty, price, fill_datetime}` keys.
- `test_synthesize_recipe_payload_preserves_iso_time_string` — `leg.time='2026-05-15T14:30:00+00:00'` → `payload[i]['fill_datetime'] == '2026-05-15T14:30:00+00:00'` (str preserved verbatim).
- `test_synthesize_recipe_payload_iteration_order_matches_concatenated_executions` — N=2 candidates with [3 legs] + [2 legs] → payload has 5 entries in concatenation order.

**Commit message stem:** `feat(reconciliation): add multi-leg auto-redirect predicate + recipe synthesis helpers (Phase 12.5 #1 T-1.1)`

**Dependencies:** none (pure helpers).

---

### Task T-1.2 — `ClassificationResult.auto_redirect_recipe` field + integration in `_classify_unmatched_fill_shared`

**Files:**
- Modify: `swing/trades/reconciliation_classifier.py:45-64` `ClassificationResult` dataclass — add `auto_redirect_recipe: Mapping[str, Any] | None = None` field per spec §5.1.
- Modify: `swing/trades/reconciliation_classifier.py:770-949` `_classify_unmatched_fill_shared` — extend the `n=1` branch (line 862) AND the `n>=2 AND qty matches` branch (line 894) per spec §5.4 + §6.5.
- Test: `tests/trades/test_reconciliation_classifier_auto_redirect_emission.py` (NEW)
- Test: `tests/trades/test_reconciliation_classifier_pre_existing_emit_paths_recipe_none.py` (NEW) — regression pin that ALL pre-existing emit paths return `auto_redirect_recipe=None`.

**Acceptance:**

- `ClassificationResult` dataclass gains `auto_redirect_recipe: Mapping[str, Any] | None = None` as the LAST field (preserves positional construction for any pre-existing call sites — discriminating test pins this).
- `_classify_unmatched_fill_shared` `n>=2` branch (currently at line 894): immediately BEFORE the `return ClassificationResult(tier=2, ambiguity_kind='multi_partial_vs_consolidated', ...)` statement (line 899), call the predicate using `source_payload` as candidates + `journal_row['price']` as journal_price. If predicate fires, synthesize recipe + thread into the `ClassificationResult(...)` return. If predicate declines, append the reject reason to `correction_reason` (parenthetical "(multi-leg auto-redirect: declined ({reason}))") and pass `auto_redirect_recipe=None`.
- `_classify_unmatched_fill_shared` `n=1` branch (currently at line 862, emits `unknown_schwab_subtype`): inspect `source_payload[0].get('executions')`. If `len(executions) >= 2` AND the predicate fires on a synthetic single-candidate `[source_payload[0]]` list AND `journal_row` is non-None, **RECLASSIFY** `ambiguity_kind` from `'unknown_schwab_subtype'` to `'multi_partial_vs_consolidated'` AND emit `auto_redirect_recipe`. Otherwise fall through to existing `unknown_schwab_subtype` emit with `auto_redirect_recipe=None`. (Spec §6.5 LOCK; satisfies cross-column CHECK pair `operator_resolved_ambiguity` ↔ ambiguity_kind `multi_partial_vs_consolidated`.)
- `journal_row` may be `None` (per existing code paths). Guard with `if journal_row is None or journal_row.get('price') is None: pass without recipe synthesis` (defensive; predicate would otherwise raise on a `.get('price')` None pass).
- All pre-existing branches (no-payload sentinel at line 826; `n=0` schwab_returned_no_match at line 849; `n>=2` qty-mismatch multi_match_within_window at line 921; defensive scalar/non-list shape at line 937) **MUST** emit `auto_redirect_recipe=None` (which is the dataclass default — no code change needed beyond ensuring the new field is the last positional arg).

**Tests added (~14):**

- `test_classification_result_auto_redirect_recipe_defaults_to_none` — construct `ClassificationResult(tier=2, ambiguity_kind='unsupported', correction_target=None, correction_reason='x')` → assert `result.auto_redirect_recipe is None`.
- `test_classification_result_auto_redirect_recipe_field_is_last_positional_arg` — instantiate with all positional args ending in recipe; pin field-order in the dataclass.
- `test_unmatched_fill_shared_n_ge_2_predicate_fires_emits_recipe` — plant `source_payload=[2 candidates, each with executions=[1 leg]]`, `journal_qty=150`, `journal_price=7.505` (Case B) → `result.auto_redirect_recipe` non-None + `ambiguity_kind == 'multi_partial_vs_consolidated'`.
- `test_unmatched_fill_shared_n_ge_2_per_leg_outlier_recipe_none_reason_cites_outlier` — Case C → recipe=None + reason substring `"leg #3"`.
- `test_unmatched_fill_shared_n_eq_1_with_multi_leg_reclassifies_ambiguity_kind` — Case A: n=1 with `len(executions)=3` aligned → `ambiguity_kind == 'multi_partial_vs_consolidated'` (NOT `'unknown_schwab_subtype'`) + recipe non-None.
- `test_unmatched_fill_shared_n_eq_1_with_single_leg_preserves_unknown_schwab_subtype` — n=1 with `len(executions)=1` (or `executions=None`) → ambiguity_kind stays `'unknown_schwab_subtype'` + recipe=None (preserves backward-compat).
- `test_unmatched_fill_shared_n_eq_1_with_multi_leg_predicate_declines_keeps_unknown_schwab_subtype` — n=1 with `len(executions)=3` but per-leg outlier → ambiguity_kind stays `'unknown_schwab_subtype'` + recipe=None + reason cites outlier (this is the n=1 fallback-when-predicate-fails branch).
- `test_unmatched_fill_shared_no_payload_sentinel_recipe_none` — Pass-1 input `source_payload=None` (line 826 branch) → recipe=None.
- `test_unmatched_fill_shared_matched_null_sentinel_recipe_none` — `source_payload={'matched': None}` → recipe=None.
- `test_unmatched_fill_shared_n_eq_0_schwab_returned_no_match_recipe_none` — `source_payload=[]` → recipe=None.
- `test_unmatched_fill_shared_n_ge_2_qty_mismatch_multi_match_within_window_recipe_none` — Case D: n=2 with sum != journal_qty → multi_match_within_window emit + recipe=None (no regression).
- `test_unmatched_fill_shared_defensive_scalar_shape_recipe_none` — `source_payload=42` → recipe=None.
- `test_unmatched_fill_shared_n_ge_2_journal_row_none_no_synthesis` — predicate-eligible payload but `journal_row=None` → recipe=None (defensive guard).
- `test_unmatched_fill_shared_n_ge_2_journal_row_missing_price_no_synthesis` — `journal_row={'quantity': 100}` (no 'price' key) → recipe=None (defensive guard).

**Commit message stem:** `feat(reconciliation): emit auto_redirect_recipe on multi-leg unmatched_*_fill classifier paths (Phase 12.5 #1 T-1.2)`

**Dependencies:** T-1.1.

---

### Task T-1.3 — Pass-2 candidate-dict emit-shape extension (`_orders_to_classifier_payload`)

**Files:**
- Modify: `swing/trades/reconciliation_backfill.py:433-469` `_orders_to_classifier_payload` — extend each emitted dict with an `'executions'` key sourced from `getattr(o, 'executions', None)` (which is `list[SchwabExecutionLeg] | None` per Sub-bundle 1 `swing/integrations/schwab/models.py:274`); pre-convert each `SchwabExecutionLeg` to a plain dict so the classifier predicate's `Mapping`-only contract holds.
- Test: `tests/trades/test_reconciliation_backfill_orders_to_classifier_payload_executions.py` (NEW)

**Acceptance:**

- The non-dict branch (line 459) of `_orders_to_classifier_payload` is extended with one additional key:
    ```python
    "executions": (
        [
            {
                "leg_id": leg.leg_id,
                "price": leg.price,
                "quantity": leg.quantity,
                "time": leg.time,
            }
            for leg in (o.executions or [])
        ]
        if getattr(o, "executions", None) is not None
        else None
    ),
    ```
- For the dict branch (line 456-458, pre-converted shape from cassette/replay): leave UNCHANGED — caller already has the shape. (Note: future cassette tests for multi-leg cases will provide dicts that already include `executions` keys; the dict branch is permissive by design.)
- The new `executions` key is `None` when `o.executions is None` (V1 mapper path / sandbox path / mapper-coherence-check collapse case per Sub-bundle 1.5 lesson) AND `[]` is preserved as `[]` (empty list — separate canary path from None per T-1.11).
- No other key shape changes — `order_id`, `status`, `enter_time`, `instrument_symbol`, `instruction`, `quantity`, `order_type`, `price` keys preserved verbatim.

**Tests added (~5):**

- `test_orders_to_classifier_payload_includes_executions_key_when_present` — `SchwabOrderResponse(executions=[SchwabExecutionLeg(...), SchwabExecutionLeg(...)])` → output dict has `'executions'` key with 2 entries, each a plain dict with `leg_id`/`price`/`quantity`/`time` keys.
- `test_orders_to_classifier_payload_executions_key_is_none_when_absent` — `SchwabOrderResponse(executions=None)` → output dict has `'executions': None`.
- `test_orders_to_classifier_payload_executions_key_is_empty_list_when_explicitly_empty` — `SchwabOrderResponse(executions=[])` → output dict has `'executions': []` (preserves separation between None and [] for canary observability — T-1.11).
- `test_orders_to_classifier_payload_dict_input_passes_through_unchanged` — pre-converted dict including an `'executions': [...]` key flows through verbatim.
- `test_orders_to_classifier_payload_other_keys_preserved` — assert all 8 pre-existing keys (`order_id`, `status`, `enter_time`, `instrument_symbol`, `instruction`, `quantity`, `order_type`, `price`) still emitted alongside the new `executions` key.

**Commit message stem:** `feat(reconciliation): include executions[] on Pass-2 candidate dicts for multi-leg auto-redirect (Phase 12.5 #1 T-1.3)`

**Dependencies:** none (independent — but T-1.5 flow-pivot dispatch requires this data to be present).

---

### Task T-1.4 — `apply_tier2_resolution` override-kwarg parameterization + shared validator + typed exception

**Files:**
- Modify: `swing/trades/reconciliation_auto_correct.py:210` `apply_tier2_resolution` outer signature — add three optional kwargs: `applied_by_override: str | None = None`, `correction_action_override: str | None = None`, `resolved_by_override: str | None = None`.
- Modify: `swing/trades/reconciliation_auto_correct.py:540` `_apply_tier2_resolution_inner` signature — same three kwargs; thread through to handler dispatch.
- Modify: `swing/trades/reconciliation_auto_correct.py:1209` `_build_tier2_correction` signature — accept `applied_by: str = 'operator'` + `correction_action_param` (already a required param renamed for clarity if needed) overriding the hard-coded `"operator"` on line 1239.
- Modify: every `_handle_*` helper (lines 1268-1948 — covers `_handle_no_mutation_audit`, `_handle_single_field_correction`, `_handle_multi_field_correction`, `_handle_keep_journal_as_is`, `_handle_consolidate_using_operator_vwap`, `_handle_split_into_partials`, `_handle_custom_audit_only`, `_handle_mark_unmatched`, `_handle_acknowledge`, `_handle_operator_truth`, `_handle_operator_alternative`, `_handle_pick_schwab_record_n`) — accept the three override kwargs (kwargs-only); thread through to `_build_tier2_correction`. Each `_handle_*` updates `_flip_discrepancy_to_resolved_ambiguity` calls (line 1250) to also accept + pass `resolved_by` override.
- Modify: `swing/trades/reconciliation_auto_correct.py:1250-1265` `_flip_discrepancy_to_resolved_ambiguity` — accept `resolved_by: str = 'operator'` kwarg; substitute the literal `"operator"` on line 1263 with the parameter.
- Modify: `swing/trades/reconciliation_auto_correct.py` — add new module-level helper `_validate_override_combo` + new typed exception `InvalidOverrideComboError(ValueError)` per spec §7.3.1.a. Place the helper before `apply_tier2_resolution` (around line 200) so it is visible to all callers. Call the helper at the TOP of `_apply_tier2_resolution_inner` BEFORE any DB read/write (per spec §7.6.1 + §7.3.1.a Codex R4 M1 LOCK).
- Modify: same module — add post-SELECT secondary invariant check inside `_apply_tier2_resolution_inner` AFTER `_select_discrepancy` (line 563), enforcing the §7.3.1.a R5 M1 + R6 M1 LOCK rules: (a) `resolved_by_override == 'auto_tier1_multi_leg'` requires `disc.ambiguity_kind == 'multi_partial_vs_consolidated'`; (b) `resolved_by_override == 'auto_tier1_multi_leg'` against a TERMINAL-resolution discrepancy requires `disc.resolved_by == 'auto_tier1_multi_leg'` (shape-aware idempotency guard; raises if a manual operator-resolved chain head is being re-invoked with auto override combo).
- Test: `tests/trades/test_apply_tier2_resolution_override_kwargs.py` (NEW)

**Acceptance:**

- New module-level constant `_AUTO_REDIRECT_SANCTIONED_CHOICE_CODE = 'split_into_partials'` defined per spec §7.3.1.a R5 M1 LOCK.
- New typed exception class `InvalidOverrideComboError(ValueError)` at module-level with docstring citing spec §7.3.1 + the "developer-bug signal" classification (not a data fall-back; pivot loop MUST NOT catch).
- New private helper `_validate_override_combo(*, choice_code: str, applied_by_override: str | None, correction_action_override: str | None, resolved_by_override: str | None) -> None` implements all 4 invariants:
    1. If `applied_by_override == 'auto'` OR `correction_action_override == 'auto_applied'`, then `resolved_by_override` MUST equal `'auto_tier1_multi_leg'` — else raise.
    2. If `resolved_by_override == 'auto_tier1_multi_leg'`, then `applied_by_override` MUST equal `'auto'` AND `correction_action_override` MUST equal `'auto_applied'` — else raise.
    3. If `resolved_by_override == 'auto_tier1_multi_leg'`, then `choice_code` MUST equal `_AUTO_REDIRECT_SANCTIONED_CHOICE_CODE` (`'split_into_partials'`) — else raise.
- `apply_tier2_resolution(conn, *, discrepancy_id, choice_code, operator_custom_payload=None, operator_reason, risk_policy_id=None, schwab_api_call_id=None, applied_by_override=None, correction_action_override=None, resolved_by_override=None)` — three new kwargs default to `None` (preserves all existing call sites verbatim).
- `_apply_tier2_resolution_inner` calls `_validate_override_combo(...)` as step 0 BEFORE `_select_discrepancy`. Step 1: SELECT. Step 1.5 (NEW): post-SELECT secondary invariant check. Step 2 (existing): terminal-state idempotent return (per existing line 565). Step 2.5 (NEW): shape-aware terminal-state idempotency guard per R6 M1 LOCK — raises `InvalidOverrideComboError` if `resolved_by_override == 'auto_tier1_multi_leg'` AND `disc.resolution` is terminal AND `disc.resolved_by != 'auto_tier1_multi_leg'`. Step 3-N: existing.
- `_build_tier2_correction` `applied_by` parameter defaults to `'operator'`. When `applied_by_override='auto'` flows from the pivot loop, the parameter is `'auto'`. Same for `correction_action`: defaults to `'operator_resolved_ambiguity'`; override flows through.
- All 12 `_handle_*` helpers accept the three override kwargs (kwargs-only) and pass them through to `_build_tier2_correction` calls (typically one or two per handler). For `_handle_split_into_partials`, the N+1 correction rows (1 anchor + N partials) MUST all carry the same override values per spec §1 hybrid-row invariant.
- `_flip_discrepancy_to_resolved_ambiguity(conn, *, discrepancy_id, resolution_reason, resolved_by: str = 'operator')` — new `resolved_by` kwarg defaults to `'operator'`; substituted into the UPDATE statement at line 1263.
- Schema CHECK enums are NOT touched (per spec §13.1 audit verification + spec §7.3). NO migration.

**Tests added (~12):**

- `test_validate_override_combo_accepts_legacy_default_none_triple` — all three None → no raise.
- `test_validate_override_combo_accepts_full_auto_redirect_triple` — `('auto', 'auto_applied', 'auto_tier1_multi_leg')` + `choice_code='split_into_partials'` → no raise.
- `test_validate_override_combo_raises_on_partial_auto_missing_resolved_by` — `applied_by_override='auto', correction_action_override='auto_applied', resolved_by_override=None` → raises `InvalidOverrideComboError`; error message cites all three kwarg values.
- `test_validate_override_combo_raises_on_partial_auto_resolved_by_operator` — mismatched intent → raises (Codex R5 M1).
- `test_validate_override_combo_raises_on_resolved_by_auto_but_applied_by_none` — symmetric guard (Codex R4 M1).
- `test_validate_override_combo_raises_on_resolved_by_auto_choice_code_not_split_into_partials` — `('auto', 'auto_applied', 'auto_tier1_multi_leg')` with `choice_code='keep_journal_as_is'` → raises (R5 M1 binding to sanctioned handler).
- `test_invalid_override_combo_error_is_value_error_subclass` — `issubclass(InvalidOverrideComboError, ValueError) is True` (pin for exception-specificity ordering).
- `test_apply_tier2_resolution_legacy_default_path_no_overrides_writes_operator_shape` — plant a pending_ambiguity_resolution discrepancy + `apply_tier2_resolution(conn, discrepancy_id=X, choice_code='split_into_partials', operator_custom_payload=[3 partials], operator_reason='manual')` (no overrides) → resulting correction rows ALL have `applied_by='operator'` + `correction_action='operator_resolved_ambiguity'`; parent discrepancy `resolved_by='operator'`.
- `test_apply_tier2_resolution_auto_redirect_triple_writes_hybrid_shape` — plant pending_ambiguity_resolution + invoke with the three overrides + `choice_code='split_into_partials'` → N+1 correction rows ALL have `applied_by='auto'` + `correction_action='auto_applied'`; parent discrepancy `resolved_by='auto_tier1_multi_leg'`.
- `test_apply_tier2_resolution_raises_on_mismatched_intent_combo` — plant + invoke with `applied_by_override='auto', resolved_by_override='operator'` → `InvalidOverrideComboError` raised.
- `test_apply_tier2_resolution_raises_on_auto_against_manual_operator_resolved_terminal` — plant a discrepancy in terminal `operator_resolved_ambiguity` with `resolved_by='operator'` + invoke with auto-redirect overrides → `InvalidOverrideComboError` raised (R6 M1 shape-aware idempotency).
- `test_apply_tier2_resolution_idempotent_return_on_auto_against_auto_terminal` — plant a discrepancy in terminal `operator_resolved_ambiguity` with `resolved_by='auto_tier1_multi_leg'` + invoke with auto-redirect overrides → existing correction_id returned (idempotent path; no raise; shape matches).

**Commit message stem:** `feat(reconciliation): parameterize apply_tier2_resolution with override kwargs + shared validator (Phase 12.5 #1 T-1.4)`

**Dependencies:** none (additive parameterization; pre-existing tests continue to pass with default-None kwargs).

---

### Task T-1.5 — Pivot-loop branch consuming `auto_redirect_recipe` + new counter

**Files:**
- Modify: `swing/trades/schwab_reconciliation.py:418-538` `_pivot_classify_and_dispatch_for_run` — add a new branch BETWEEN the existing `if classification.tier == 1:` (line 471) and the existing `else:` tier-2 stamp (line 517) for `elif classification.tier == 2 and classification.auto_redirect_recipe is not None:` per spec §7.4.
- Test: `tests/trades/test_pivot_loop_auto_redirect_dispatch.py` (NEW)

**Acceptance:**

- New branch at `_pivot_classify_and_dispatch_for_run` recognizes `classification.auto_redirect_recipe is not None`:
    1. Validate the override combo via `_validate_override_combo(...)` BEFORE any mutation (defense-in-depth; matches §7.3.1.a R5 M2 LOCK; recipe-author bug surfaces here as well as at service-layer entry).
    2. Inside the active `correction_sp_{discrepancy_id}` SAVEPOINT (already opened at line 448): call `_stamp_pending_ambiguity_inner(conn, discrepancy_id=disc.discrepancy_id, ambiguity_kind=classification.ambiguity_kind, resolution_reason=classification.correction_reason)` (matches existing call shape at line 520 — Codex R2 M2 confirms current signature accepts `allow_pending_update` default but here we want the default-False path; specific kwarg-only invocation).
    3. Call `_apply_tier2_resolution_inner(conn, discrepancy_id=disc.discrepancy_id, choice_code=recipe['choice_code'], operator_custom_payload=recipe['payload'], operator_reason=f"multi-leg auto-redirect: {classification.correction_reason}", applied_by_override=recipe['applied_by_override'], correction_action_override=recipe['correction_action_override'], resolved_by_override=recipe['resolved_by'], risk_policy_id=None, schwab_api_call_id=schwab_api_call_id, environment=environment)`. (T-1.6 adds `environment` kwarg to `_apply_tier2_resolution_inner`; this branch passes it from `_pivot_classify_and_dispatch_for_run`'s existing `environment` parameter at line 424.)
    4. On success: `conn.execute(f"RELEASE SAVEPOINT {sp_name}")` + `counters['tier1_multi_leg_auto_redirected_count'] += 1` (NEW counter; `setdefault(...)` at function entry — see counter init below).
    5. On `_SandboxAutoRedirectShortCircuit` exception (T-1.6 introduces): `conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")` + `conn.execute(f"RELEASE SAVEPOINT {sp_name}")` + `counters['sandbox_auto_redirect_skipped_count'] += 1` + log.warning citing discrepancy_id; discrepancy state ends in `'unresolved'` (the stamp was rolled back).
    6. On `InvalidOverrideComboError` (subclass of `ValueError`): the SAVEPOINT rolls back via the catch at line 529 (`except Exception as e: ROLLBACK TO SAVEPOINT + RELEASE + counters['tier_errored_count'] += 1`). Discriminating test ensures the developer-bug signal propagates to log.warning + counter increment WITHOUT being absorbed as a tier-2 stamp (which would HIDE the bug). NOTE: per spec §7.4 R4 M2 LOCK + lesson #11, the developer-bug error class should re-raise out, but the pivot-loop's existing graceful-degradation `except Exception` catch at line 529 will absorb. **PLAN DECISION** (consistent with existing graceful-degradation pattern at line 529): we log+counter-increment but do NOT propagate out — this matches the documented "never raises out" contract on `_pivot_classify_and_dispatch_for_run` at line 429. The developer-bug is surfaced via the `tier_errored_count` counter increment + WARN log; T-1.4 service-layer tests catch the bug at unit-test time. Discriminating test pattern documents this trade-off explicitly.
    7. On `ValidatorRejectedError` OR other `ValueError`: same existing catch-all path (line 529) increments `tier_errored_count`. The fall-back stamp-as-pending path of the tier-1 branch (line 487-516) does NOT apply here because the auto-redirect started from a tier-2 classification — the SAVEPOINT rollback simply preserves the discrepancy as `'unresolved'`.
- Counter init at function entry (line 432-434): add `counters.setdefault("tier1_multi_leg_auto_redirected_count", 0)` and `counters.setdefault("sandbox_auto_redirect_skipped_count", 0)`.
- `_pivot_classify_and_dispatch_for_run` signature UNCHANGED otherwise (no new kwargs; `environment` already present at line 424).

**Tests added (~10):**

- `test_pivot_loop_auto_redirect_recipe_present_dispatches_apply_tier2_resolution_inner` — plant a discrepancy + supply schwab_orders with multi-leg shape → assert classifier emits recipe; service is invoked with the three override kwargs; counter `tier1_multi_leg_auto_redirected_count == 1`; parent discrepancy ends in `operator_resolved_ambiguity` with `resolved_by='auto_tier1_multi_leg'`.
- `test_pivot_loop_auto_redirect_recipe_absent_falls_through_to_tier2_stamp` — plant tier-2 multi_match_within_window (no recipe) → existing stamp path fires; `tier2_pending_count == 1`; new counter stays 0.
- `test_pivot_loop_auto_redirect_invalid_override_combo_logs_warning_increments_tier_errored_count` — plant a synthetic state where the recipe's overrides are mismatched (test-fixture monkeypatches the classifier to return a malformed recipe) → log.warning fires; `tier_errored_count == 1`; discrepancy ends in `'unresolved'` (SAVEPOINT rolled back).
- `test_pivot_loop_auto_redirect_sandbox_short_circuit_rolls_back_stamp` — invoke with `environment='sandbox'` + multi-leg fixture → `sandbox_auto_redirect_skipped_count == 1`; `tier1_multi_leg_auto_redirected_count == 0`; discrepancy ends in `'unresolved'` (NOT `pending_ambiguity_resolution`); no correction rows for this discrepancy.
- `test_pivot_loop_auto_redirect_validator_rejected_falls_back_to_unresolved` — plant a recipe whose synthesized payload would trip `_handle_split_into_partials`'s `qty_tolerance=1e-6` check (e.g., manually monkeypatch the recipe with a malformed payload) → `tier_errored_count == 1`; discrepancy ends in `'unresolved'`.
- `test_pivot_loop_auto_redirect_writes_n_plus_1_correction_rows_all_hybrid_shape` — multi-leg fixture with 3 legs → `reconciliation_corrections` has 4 rows (1 anchor + 3 partials); all 4 have `applied_by='auto'` + `correction_action='auto_applied'`; parent discrepancy has `resolved_by='auto_tier1_multi_leg'`.
- `test_pivot_loop_auto_redirect_counter_setdefault_idempotent` — invoke pivot loop twice on the same `counters` dict — counter doesn't get re-zeroed; cumulative count is correct.
- `test_pivot_loop_auto_redirect_counter_keys_present_even_on_empty_run` — invoke with zero discrepancies → counters dict carries `tier1_multi_leg_auto_redirected_count: 0` and `sandbox_auto_redirect_skipped_count: 0` keys.
- `test_pivot_loop_tier1_pass_1_path_unaffected_by_phase_12_5_1_changes` — regression: plant entry_price_mismatch tier-1 → existing path fires; counters dict has `tier1_applied_count: 1` and `tier1_multi_leg_auto_redirected_count: 0`.
- `test_pivot_loop_n_eq_1_multi_leg_reroute_e2e` — Case A end-to-end through pivot loop: plant discrepancy + `source_payload=[1 candidate with 3 legs]` → ambiguity_kind reclassified to `multi_partial_vs_consolidated` AND auto-redirect fires + 4 correction rows.

**Commit message stem:** `feat(reconciliation): pivot-loop auto-redirect dispatch on classifier recipe (Phase 12.5 #1 T-1.5)`

**Dependencies:** T-1.1 + T-1.2 + T-1.3 + T-1.4 (consumes all of them); T-1.6 for the environment kwarg threading (executing-plans may bundle T-1.5 + T-1.6 into one commit if convenient, but acceptance/tests overlap is documented separately).

---

### Task T-1.6 — Sandbox short-circuit in `_apply_tier2_resolution_inner` gated on `applied_by_override == 'auto'`

**Files:**
- Modify: `swing/trades/reconciliation_auto_correct.py:540` `_apply_tier2_resolution_inner` signature — add `environment: str = 'production'` kwarg.
- Modify: `swing/trades/reconciliation_auto_correct.py:210` `apply_tier2_resolution` outer — also add `environment: str = 'production'` and thread through to inner.
- Modify: `swing/trades/reconciliation_auto_correct.py` — add new module-level `class _SandboxAutoRedirectShortCircuit(Exception)` (NOT a `ValueError` subclass; semantic-distinct sentinel) per spec §7.6.1 LOCK.
- Modify: `_apply_tier2_resolution_inner` body — after `_validate_override_combo(...)` and AFTER `_select_discrepancy(...)` (so the SELECT-first-idempotency contract is honored per C.C lesson #3) but BEFORE handler dispatch (line 590): if `applied_by_override == 'auto' AND environment == 'sandbox'`, log.warning citing the discrepancy_id + raise `_SandboxAutoRedirectShortCircuit(discrepancy_id)`.
- Test: `tests/trades/test_apply_tier2_resolution_sandbox_short_circuit.py` (NEW)

**Acceptance:**

- `environment: str = 'production'` kwarg threaded through both outer + inner. Default preserves all existing call sites (which pass no `environment` arg).
- Sandbox short-circuit fires ONLY when `applied_by_override == 'auto'` (auto-redirect path) AND `environment == 'sandbox'`. Manual operator path (no overrides) under sandbox still proceeds — operators can test manual menu in sandbox.
- Short-circuit raises `_SandboxAutoRedirectShortCircuit` AFTER `_validate_override_combo` AND `_select_discrepancy` (developer-bug guard still fires + SELECT-first-idempotency contract honored per C.C lesson #3) BEFORE the handler dispatch.
- Pivot-loop catches the exception (T-1.5 step 5) + rolls back the SAVEPOINT (which undoes the `_stamp_pending_ambiguity_inner` stamp that immediately preceded the inner call).

**Tests added (~6):**

- `test_apply_tier2_resolution_inner_sandbox_short_circuits_on_auto_override_combo` — invoke inner with `environment='sandbox'` + auto-redirect override triple → raises `_SandboxAutoRedirectShortCircuit`; log.warning fires.
- `test_apply_tier2_resolution_inner_production_no_short_circuit_on_auto_override_combo` — invoke inner with `environment='production'` + auto-redirect override triple → no raise; proceeds to handler.
- `test_apply_tier2_resolution_inner_sandbox_manual_path_no_short_circuit` — invoke inner with `environment='sandbox'` + NO overrides (None default) → no raise; proceeds to handler (manual operator can test menu under sandbox).
- `test_apply_tier2_resolution_inner_sandbox_short_circuit_after_select` — short-circuit fires AFTER `_select_discrepancy` (verify by passing nonexistent discrepancy_id under sandbox + auto-redirect overrides → raises `ValueError`/`StopIteration` from SELECT-first idempotency, NOT `_SandboxAutoRedirectShortCircuit`).
- `test_apply_tier2_resolution_inner_sandbox_short_circuit_after_validate_override_combo` — short-circuit fires AFTER `_validate_override_combo` (verify by passing mismatched combo under sandbox → raises `InvalidOverrideComboError` first).
- `test_sandbox_auto_redirect_short_circuit_is_not_value_error_subclass` — pin `not issubclass(_SandboxAutoRedirectShortCircuit, ValueError)` so the pivot loop's `except (ValidatorRejectedError, ValueError)` catch at the tier-1 branch does NOT absorb the sentinel.

**Commit message stem:** `feat(reconciliation): sandbox short-circuit on auto-redirect path in _apply_tier2_resolution_inner (Phase 12.5 #1 T-1.6)`

**Dependencies:** T-1.4 (override kwargs must exist).

---

### Task T-1.7 — `_fetch_recent_multi_leg_auto_correction_count` helper

**Files:**
- Create: `swing/metrics/discrepancies.py` — add new module-level function `count_recent_multi_leg_auto_corrections(conn: sqlite3.Connection, *, window: Literal['most_recent_run'] = 'most_recent_run') -> int` per spec §8.2.
- Modify: `swing/metrics/discrepancies.py` — pre-existing `count_unresolved_material(conn)` function stays put at line 37 (Phase 10 T-A.7.1 surface; do NOT touch). The new function is additive.
- Test: `tests/metrics/test_discrepancies_count_recent_multi_leg_auto_corrections.py` (NEW)

**Acceptance:**

- New function `count_recent_multi_leg_auto_corrections(conn, *, window='most_recent_run') -> int`:
    1. Read `latest_completed_run_id` via `SELECT run_id FROM reconciliation_runs WHERE state = 'completed' ORDER BY finished_ts DESC, run_id DESC LIMIT 1`. (Deterministic tiebreaker per Phase 10 lesson #26.)
    2. If no row, return 0.
    3. `SELECT COUNT(DISTINCT rd.discrepancy_id) FROM reconciliation_corrections rc JOIN reconciliation_discrepancies rd ON rc.discrepancy_id = rd.discrepancy_id WHERE rc.reconciliation_run_id = ? AND rd.resolved_by = ?` with params `(latest_run_id, 'auto_tier1_multi_leg')` per spec §8.2 (Codex R2 M1 LOGICAL semantics — NOT row-level — to avoid double-counting the N+1 rows from `_handle_split_into_partials`).
    4. Return `int(row[0])`.
- The `window` parameter is `Literal['most_recent_run']` V1 LOCK (per spec §8.4); V2 widens to additional values (banked §Z #1 + #2). The current implementation IGNORES the parameter beyond the type-narrowing; documented in the docstring.
- Function docstring cites spec §8.2 + §14 V2 candidates + Phase 10 lesson #26 (deterministic tiebreaker).

**Tests added (~7):**

- `test_count_recent_multi_leg_auto_corrections_returns_zero_when_no_runs` — empty `reconciliation_runs` table → 0.
- `test_count_recent_multi_leg_auto_corrections_returns_zero_when_no_completed_runs` — only `state='running'` rows → 0.
- `test_count_recent_multi_leg_auto_corrections_counts_distinct_discrepancies` — plant 1 multi-leg discrepancy with 4 correction rows (1 anchor + 3 partials, all `resolved_by='auto_tier1_multi_leg'` on the parent discrepancy) on the latest completed run → returns 1 (NOT 4).
- `test_count_recent_multi_leg_auto_corrections_ignores_prior_runs` — plant a multi-leg auto-correction on run #1 (completed) + ZERO on run #2 (completed, later finished_ts) → returns 0 (banner clears on next run per §8.4 LOCK).
- `test_count_recent_multi_leg_auto_corrections_ignores_manual_split_into_partials` — plant `resolved_by='operator'` split correction on the latest run → returns 0.
- `test_count_recent_multi_leg_auto_corrections_ignores_tier1_pass_1_corrections` — plant `resolved_by='auto'` (Pass-1 entry_price_mismatch auto-correct) → returns 0.
- `test_count_recent_multi_leg_auto_corrections_tiebreaks_on_run_id_descending` — plant two completed runs with identical `finished_ts` → uses the one with higher `run_id` (deterministic tiebreaker per Phase 10 lesson #26).

**Commit message stem:** `feat(metrics): add count_recent_multi_leg_auto_corrections helper (Phase 12.5 #1 T-1.7)`

**Dependencies:** none.

---

### Task T-1.8 — `BaseLayoutVM.recent_multi_leg_auto_correction_count` + retrofit across all base-layout VMs

**Files:**
- Modify: `swing/web/view_models/metrics/shared.py:47` `BaseLayoutVM` — add `recent_multi_leg_auto_correction_count: int = 0` field.
- Modify: ALL VMs across `swing/web/view_models/` that already carry `unresolved_material_discrepancies_count` (per Phase 10 T-E.3 retrofit + Sub-bundle C.D retrofit precedent). Grep anchor: `grep -rn "unresolved_material_discrepancies_count: int" swing/web/view_models/` — at plan-drafting time this matches 17 distinct files (see §C inventory). Each file: add the new field as a sibling default-0 field, and update the constructor/builder to populate from `count_recent_multi_leg_auto_corrections(conn)`.
- The 17 files (verified via grep at plan-drafting time):
    1. `swing/web/view_models/config.py:50` (`ConfigPageVM` per Phase 10 lesson §E1) + builder at `:132`
    2. `swing/web/view_models/dashboard.py:353` (`DashboardVM`) + builder at `:1266`
    3. `swing/web/view_models/error.py:24` (`PageErrorVM`) — no explicit builder; default-0 only (matches existing pattern)
    4. `swing/web/view_models/journal.py:111` + builder at `:144`
    5. `swing/web/view_models/metrics/capital_friction.py:99` (builder only — extends `BaseLayoutVM`)
    6. `swing/web/view_models/metrics/deviation_outcome.py:94`
    7. `swing/web/view_models/metrics/hypothesis_progress_card.py:423`
    8. `swing/web/view_models/metrics/identification_funnel.py:77`
    9. `swing/web/view_models/metrics/index.py:94` (umbrella navigator)
    10. `swing/web/view_models/metrics/maturity_stage.py:73`
    11. `swing/web/view_models/metrics/process_grade_trend.py:494`
    12. `swing/web/view_models/metrics/tier_comparison.py`
    13. `swing/web/view_models/metrics/trade_process_card.py`
    14. `swing/web/view_models/pipeline.py` (PipelineVM)
    15. `swing/web/view_models/schwab.py:77` (`SchwabSetupVM`) + `:222` (`SchwabStatusVM`) + `:535` (`SchwabSetupErrorVM`) — three VMs in one file
    16. `swing/web/view_models/trades.py:662` (`ReviewVM`) + `:755` (`CadenceCompleteVM`) + `:769` (`ReviewsPendingVM`) + `:911` (`TradeDetailVM`) — four VMs in one file
    17. `swing/web/view_models/watchlist.py` (`WatchlistVM`)
- Note: `swing/web/view_models/account.py` does NOT currently carry `unresolved_material_discrepancies_count` per grep at plan-drafting time. If the implementer's grep finds this gap (i.e., account.py templates extend `base.html.j2`), retrofit it too — defense-in-depth per the Phase 10 lesson E2 ("plan §H named 6; implementation added 4 more whose templates extend base.html.j2"). Discriminating test enumerates ALL VMs by introspection (see test below).
- Test: `tests/web/test_base_layout_vm_recent_multi_leg_field.py` (NEW)

**Acceptance:**

- `BaseLayoutVM.recent_multi_leg_auto_correction_count: int = 0` field added with default; `__post_init__` (existing at line 58) extended with `if self.recent_multi_leg_auto_correction_count < 0: raise ValueError(...)` validation (matches existing pattern at line 58).
- Every base-layout VM dataclass that carries `unresolved_material_discrepancies_count: int = 0` ALSO carries `recent_multi_leg_auto_correction_count: int = 0` (same default, same negative-rejection invariant if `__post_init__` exists).
- Every VM constructor/builder that calls `count_unresolved_material(conn)` ALSO calls `count_recent_multi_leg_auto_corrections(conn)` and passes the value as `recent_multi_leg_auto_correction_count=...`.
- Discriminating regression test pattern: introspect every VM class in `swing/web/view_models/*.py` + `swing/web/view_models/metrics/*.py` that already has `unresolved_material_discrepancies_count` as a field; assert `recent_multi_leg_auto_correction_count` is also a field.

**Tests added (~9):**

- `test_base_layout_vm_has_recent_multi_leg_field` — field exists on `BaseLayoutVM` with default 0.
- `test_base_layout_vm_rejects_negative_recent_multi_leg_count` — instantiate with `recent_multi_leg_auto_correction_count=-1` → `ValueError`.
- `test_every_vm_with_unresolved_material_field_also_has_recent_multi_leg_field` — introspect every dataclass via `dataclasses.fields(VMClass)`; if `'unresolved_material_discrepancies_count'` in field names, assert `'recent_multi_leg_auto_correction_count'` in field names. This is the LOCK pin per spec §16 lesson #6 (helper invocation completeness).
- `test_dashboard_vm_populates_recent_multi_leg_field` — build_dashboard fixture with planted multi-leg corrections → VM carries non-zero count.
- `test_dashboard_vm_recent_multi_leg_defaults_to_zero_when_no_runs` — empty DB → VM carries 0.
- `test_config_page_vm_populates_recent_multi_leg_field` — analogous to dashboard.
- `test_schwab_setup_vm_populates_recent_multi_leg_field` — analogous.
- `test_metrics_index_vm_populates_recent_multi_leg_field` — umbrella navigator surface.
- `test_review_vm_populates_recent_multi_leg_field` — `swing/web/view_models/trades.py:629` `ReviewVM` surface.

**Commit message stem:** `feat(web): retrofit recent_multi_leg_auto_correction_count across base-layout VMs (Phase 12.5 #1 T-1.8)`

**Dependencies:** T-1.7.

---

### Task T-1.9 — `base.html.j2` banner block (ASCII-only)

**Files:**
- Modify: `swing/web/templates/base.html.j2` — add new `{% if vm.recent_multi_leg_auto_correction_count > 0 %}` block IMMEDIATELY after the existing `unresolved_material_discrepancies_count` banner block.
- Test: `tests/web/test_base_html_multi_leg_banner.py` (NEW)

**Acceptance:**

- New banner block per spec §8.3:
    ```jinja
    {% if vm.recent_multi_leg_auto_correction_count > 0 %}
      <div class="reconciliation-auto-redirect-banner" data-banner-count="{{ vm.recent_multi_leg_auto_correction_count }}">
        {{ vm.recent_multi_leg_auto_correction_count }} multi-leg auto-correction{{ 's' if vm.recent_multi_leg_auto_correction_count != 1 else '' }} in most recent reconciliation run. Review via <code>swing journal discrepancy list --resolved-by auto_tier1_multi_leg</code>.
      </div>
    {% endif %}
    ```
- Banner text is ASCII-only: NO em-dash (use `-`), NO arrows (use `->`), NO unicode glyphs. Per CLAUDE.md Windows cp1252 gotcha + spec §16 lesson #7. Discriminating test asserts: `assert all(ord(c) < 128 for c in rendered_html)` for the banner block.
- `data-banner-count="{{ count }}"` HTML attribute is the discriminating test marker (NOT the rendered text — which contains the count too, but the attribute is a stable selector).
- Banner block does NOT supersede the existing `unresolved_material_discrepancies_count` banner; both render side-by-side per spec §2.4 + §8.4.

**Tests added (~5):**

- `test_base_layout_multi_leg_banner_renders_when_count_gt_zero` — VM with count=3 → rendered HTML contains `class="reconciliation-auto-redirect-banner"` + `data-banner-count="3"` + CLI command verbatim.
- `test_base_layout_multi_leg_banner_absent_when_count_zero` — VM with count=0 → rendered HTML does NOT contain the class.
- `test_base_layout_multi_leg_banner_singular_form_when_count_one` — count=1 → banner text contains `1 multi-leg auto-correction in` (no plural 's').
- `test_base_layout_multi_leg_banner_plural_form_when_count_gt_one` — count=2 → banner text contains `2 multi-leg auto-corrections in`.
- `test_base_layout_multi_leg_banner_ascii_only` — count=3 → assert every codepoint in the rendered banner substring `< 128` (sentinel-leak audit family pattern per spec §8.5).

**Commit message stem:** `feat(web): add multi-leg auto-correction banner to base layout (Phase 12.5 #1 T-1.9)`

**Dependencies:** T-1.7 + T-1.8.

---

### Task T-1.10 — `swing journal discrepancy list --resolved-by <value>` CLI filter

**Files:**
- Modify: `swing/cli.py:2055-2107` `discrepancy_list_cmd` — add `--resolved-by` Click option per spec §8.6.
- Test: `tests/cli/test_discrepancy_list_resolved_by_filter.py` (NEW)

**Acceptance:**

- New Click option: `@click.option("--resolved-by", type=str, default=None, help="Filter to a specific resolved_by value (e.g., 'auto_tier1_multi_leg' for multi-leg auto-corrections).")`.
- Function signature gains `resolved_by` kwarg: `def discrepancy_list_cmd(ctx, unresolved, material, trade_id, limit, resolved_by):`.
- New WHERE-clause condition: `if resolved_by is not None: where.append("resolved_by = ?"); params.append(resolved_by)`.
- The filter is composable with existing `--unresolved`, `--material`, `--trade-id` filters (per spec §8.6).
- The `resolved_by` column is free TEXT per spec §13.2; no enum validation at CLI layer (operator can pass any string; missing values return 0 rows naturally). Discriminating test pattern: pass a never-emitted value like `'nonexistent_value'` → returns "(no discrepancies)" without raising.

**Tests added (~4):**

- `test_discrepancy_list_resolved_by_auto_tier1_multi_leg_returns_matching_rows` — plant 2 discrepancies with `resolved_by='auto_tier1_multi_leg'` + 1 with `resolved_by='operator'` → CLI filter returns 2 rows.
- `test_discrepancy_list_resolved_by_no_match_returns_empty_with_friendly_message` — filter with `resolved_by='nonexistent_value'` → stdout contains `"(no discrepancies)"`.
- `test_discrepancy_list_resolved_by_composable_with_unresolved_filter` — plant 1 unresolved + `resolved_by='auto_tier1_multi_leg'` (impossible state, but tests the AND composition; in practice, auto_tier1_multi_leg always pairs with `operator_resolved_ambiguity` resolution per the hybrid invariant) — verify the filter syntax. Realistic combo: filter by both `--unresolved` and a resolved_by value returns 0 (no unresolved rows have a resolved_by value).
- `test_discrepancy_list_resolved_by_composable_with_material_filter` — plant `material_to_review=1` + `resolved_by='auto_tier1_multi_leg'` → filter returns the row.

**Commit message stem:** `feat(cli): add --resolved-by filter to swing journal discrepancy list (Phase 12.5 #1 T-1.10)`

**Dependencies:** none (independent; banner template (T-1.9) cites this filter — both land in the same integration merge per spec §8.6 LOCK).

---

### Task T-1.11 — Empty-executions canary observability + briefing.md +1 line

**Files:**
- Modify: `swing/trades/reconciliation_classifier.py` — extend `_multi_leg_auto_redirect_predicate` (T-1.1) to emit a `logger.warning` line when a candidate dict has `executions=[]` (empty list, NOT None) AND the predicate declines at sub-condition 1 — per spec §12.3 + Sub-bundle 1.5 canary precedent. (~+5 LOC inside the predicate.)
- Modify: `swing/pipeline/runner.py:1668-1686` — extend the existing `reconciliation_pending_count` + `reconciliation_tier1_recent_count` block with a new SQL counter `reconciliation_tier1_multi_leg_redirected_count` reading from `reconciliation_corrections rc JOIN reconciliation_discrepancies rd ON ...` filtered by `applied_at >= cutoff_iso AND rd.resolved_by = 'auto_tier1_multi_leg'` (COUNT(DISTINCT rd.discrepancy_id) for LOGICAL semantics per spec §11.2 + lesson #8).
- Modify: `swing/rendering/briefing.py:71-80` `BriefingInputs` — add new field `reconciliation_tier1_multi_leg_redirected_count: int = 0`.
- Modify: `swing/rendering/briefing.py:241-280` `build_briefing_view_model` — thread the new field through to the returned `BriefingViewModel` (add to constructor at line 267-270).
- Modify: `swing/rendering/briefing.py` — `BriefingViewModel` (search for the dataclass) — add the new field with the same shape.
- Modify: `swing/rendering/briefing_md.py:87-110` — extend the `## Reconciliation status` block to add a new line `- Multi-leg auto-redirected (last 7 days): K` IMMEDIATELY before the existing `- Tier-1 auto-corrected (last 7 days):` line. The section's outer predicate at line 95 (`if pending > 0 or tier1_recent > 0:`) is widened to `if pending > 0 or tier1_recent > 0 or tier1_multi_leg_redirected > 0:` per spec §11.2 LOCK (line emits ONLY when K > 0; the section itself emits when ANY of the three counters > 0).
- Modify: `swing/pipeline/runner.py:1750-1773` `BriefingInputs(...)` construction — thread the new counter through.
- Test: `tests/trades/test_multi_leg_predicate_empty_executions_canary.py` (NEW)
- Test: `tests/pipeline/test_briefing_multi_leg_redirected_count.py` (NEW)

**Acceptance:**

- Predicate canary: when ANY candidate's `executions` value is exactly the empty list `[]` (NOT None — that's the "absent" case), the predicate emits `logger.warning("multi-leg predicate declined for ticker=%s order_id=%s: executions list is empty (canary)", ticker, order_id)` before returning `(False, ...)`. The reason text returned to the classifier is unchanged from the existing sub-condition 1 reason; the canary is observability-only (~+5 LOC).
- The classifier passes `ticker` through to the predicate — UPDATE: predicate signature gains optional `ticker: str | None = None` kwarg (kwarg-only, defaults to None for back-compat with T-1.1 tests). The classifier sub-classifier passes `ticker=discrepancy.ticker` when invoking the predicate.
- Briefing.md emits a new line `- Multi-leg auto-redirected (last 7 days): K` IMMEDIATELY before the existing tier-1 line per spec §11.2 — but ONLY when K > 0 (per spec §11.2 LOCK + lesson #8).
- The `## Reconciliation status` SECTION emits when ANY of the three counters is > 0 (widened predicate at line 95).
- `reconciliation_tier1_multi_leg_redirected_count` SQL uses `COUNT(DISTINCT rd.discrepancy_id)` semantics per lesson #8 (NOT `COUNT(*)` — would inflate by N+1 rows per logical redirect).

**Tests added (~9):**

- `test_predicate_logs_warning_when_executions_is_empty_list_canary` — invoke predicate with candidate `{'executions': []}` + capture caplog → WARNING record with substring `"executions list is empty (canary)"` AND substring of the passed ticker.
- `test_predicate_no_warning_when_executions_is_none` — `{'executions': None}` → no canary warning (this is the "absent" case, expected for V1 mapper / sandbox / mapper-coherence-check paths).
- `test_predicate_no_warning_when_executions_has_legs` — `{'executions': [leg, leg]}` → no canary warning.
- `test_briefing_inputs_has_new_counter_field` — `dataclasses.fields(BriefingInputs)` includes `'reconciliation_tier1_multi_leg_redirected_count'`.
- `test_briefing_view_model_has_new_counter_field` — same on `BriefingViewModel`.
- `test_briefing_md_emits_multi_leg_line_when_count_gt_zero` — `BriefingViewModel(...)` with `reconciliation_tier1_multi_leg_redirected_count=3` + other counters=0 → output contains `"## Reconciliation status"` AND `"- Multi-leg auto-redirected (last 7 days): 3"`.
- `test_briefing_md_omits_multi_leg_line_when_count_zero` — count=0 + pending=2 → output contains `"## Reconciliation status"` BUT does NOT contain `"Multi-leg auto-redirected"` substring.
- `test_briefing_md_omits_section_entirely_when_all_three_counters_zero` — all 0 → output does NOT contain `"## Reconciliation status"` (preserves existing predicate behavior).
- `test_runner_reconciliation_tier1_multi_leg_redirected_count_distinct_semantics` — plant 1 multi-leg discrepancy with 4 correction rows (1 anchor + 3 partials, `resolved_by='auto_tier1_multi_leg'`) within the 7-day window → counter == 1 (NOT 4).

**Commit message stem:** `feat(pipeline,briefing): multi-leg auto-redirect canary + briefing.md +1 line (Phase 12.5 #1 T-1.11)`

**Dependencies:** T-1.1 (predicate signature ticker kwarg).

---

### (No T-1.12 + E2E slow test)

Per spec §9.2, the projection includes "1 slow E2E test" beyond the 11 fast-test tasks. **PLAN DECISION:** the E2E test is bundled into T-1.5's test file as a `@pytest.mark.slow` test exercising the full flow through `_pivot_classify_and_dispatch_for_run` end-to-end against an in-memory schema-v19 SQLite with planted Schwab order fixtures. Single integration test: `test_e2e_phase12_5_1_full_flow_through_pivot_loop_to_banner_count` — plants a `reconciliation_run` row + multi-leg discrepancy + invokes the pivot loop + asserts the full state cascade (4 correction rows + parent discrepancy in `operator_resolved_ambiguity` with `resolved_by='auto_tier1_multi_leg'` + `count_recent_multi_leg_auto_corrections(conn) == 1`).

This avoids creating a separate T-1.12 with only 1 test + matches Sub-bundle C.D precedent of bundling slow E2E with the closest task.

---

## §B Pre-conditions + worktree state

- **BASELINE_SHA:** `5c988d2` (current `main` HEAD with the writing-plans dispatch brief committed).
- **WORKTREE:** `.worktrees/phase12-5-bundle-1-oqf-writing-plans/` (this dispatch's worktree; the executing-plans dispatch will create a fresh `phase12-5-bundle-1-oqf-executing` worktree).
- **BRANCH:** `phase12-5-bundle-1-oqf-writing-plans` (this dispatch). Executing-plans branch: `phase12-5-bundle-1-oqf-executing` (recommended; matches cleanup-script regex `phase\d+[-_]`).
- **Schema:** v19, UNCHANGED through Sub-bundle 1 + 1.5 + 2 chain (verified spec §13.1 audit). Plan does NOT touch `swing/data/migrations/`.
- **Fast-test baseline:** ~4575 fast tests on `main` HEAD (post Sub-bundle 2 ship `690aed0`); add 3 pre-existing `phase8 walkthrough` failures (acknowledged + tracked under Phase 12.5 #3 maintenance pass). Plan-projected post-ship: ~4660 (4575 + 85 new tests).
- **Ruff baseline:** 18 E501 (per Sub-bundle 2 ship); plan MUST NOT introduce new E501 violations. Ruff baseline must remain 18.
- **Operator-locks already loaded (BINDING):** spec §2.1-§2.4 (4 operator-locks) + spec §15.B #1-#3 (3 operator-locks; locked 2026-05-17 post-brainstorm-merge) + spec §15.A 1-7 (7 brainstorm-locks); see §D below for the verbatim roll-up.

---

## §C Files touched (canonical roster)

### §C.1 Production code (touched by tasks; grep anchors verified at plan-drafting time)

| File | Lines (current HEAD) | Touched by task |
|---|---|---|
| `swing/trades/reconciliation_classifier.py` | 45-64 `ClassificationResult`; 770-949 `_classify_unmatched_fill_shared` | T-1.1 + T-1.2 + T-1.11 |
| `swing/trades/reconciliation_backfill.py` | 433-469 `_orders_to_classifier_payload` | T-1.3 |
| `swing/trades/reconciliation_auto_correct.py` | 210 `apply_tier2_resolution`; 540 `_apply_tier2_resolution_inner`; 1209 `_build_tier2_correction`; 1250 `_flip_discrepancy_to_resolved_ambiguity`; 1268-1948 every `_handle_*` helper | T-1.4 + T-1.6 |
| `swing/trades/schwab_reconciliation.py` | 418-538 `_pivot_classify_and_dispatch_for_run` | T-1.5 |
| `swing/metrics/discrepancies.py` | new function alongside `count_unresolved_material` at line 37 | T-1.7 |
| `swing/web/view_models/metrics/shared.py` | 28+ `BaseLayoutVM` | T-1.8 |
| `swing/web/view_models/*.py` + `swing/web/view_models/metrics/*.py` (17 files; see §A T-1.8 enumeration) | every dataclass with `unresolved_material_discrepancies_count` + every builder that populates it | T-1.8 |
| `swing/web/templates/base.html.j2` | banner block insertion site | T-1.9 |
| `swing/cli.py` | 2055-2107 `discrepancy_list_cmd` | T-1.10 |
| `swing/pipeline/runner.py` | 1668-1686 reconciliation counter block; 1750-1773 BriefingInputs construction | T-1.11 |
| `swing/rendering/briefing.py` | 71-80 `BriefingInputs`; 241-280 `build_briefing_view_model`; new field on `BriefingViewModel` | T-1.11 |
| `swing/rendering/briefing_md.py` | 87-110 `## Reconciliation status` section | T-1.11 |

### §C.2 New test files

| File | Touched by task |
|---|---|
| `tests/trades/test_reconciliation_classifier_multi_leg_predicate.py` | T-1.1 |
| `tests/trades/test_reconciliation_classifier_auto_redirect_emission.py` | T-1.2 |
| `tests/trades/test_reconciliation_classifier_pre_existing_emit_paths_recipe_none.py` | T-1.2 |
| `tests/trades/test_reconciliation_backfill_orders_to_classifier_payload_executions.py` | T-1.3 |
| `tests/trades/test_apply_tier2_resolution_override_kwargs.py` | T-1.4 |
| `tests/trades/test_pivot_loop_auto_redirect_dispatch.py` | T-1.5 (includes the slow E2E test) |
| `tests/trades/test_apply_tier2_resolution_sandbox_short_circuit.py` | T-1.6 |
| `tests/metrics/test_discrepancies_count_recent_multi_leg_auto_corrections.py` | T-1.7 |
| `tests/web/test_base_layout_vm_recent_multi_leg_field.py` | T-1.8 |
| `tests/web/test_base_html_multi_leg_banner.py` | T-1.9 |
| `tests/cli/test_discrepancy_list_resolved_by_filter.py` | T-1.10 |
| `tests/trades/test_multi_leg_predicate_empty_executions_canary.py` | T-1.11 |
| `tests/pipeline/test_briefing_multi_leg_redirected_count.py` | T-1.11 |

### §C.3 Surfaces explicitly NOT touched (UNCHANGED LOCK per spec §3)

- `swing/integrations/schwab/mappers.py` — V2 mapper UNCHANGED (Sub-bundle 1+1.5 ship).
- `swing/integrations/schwab/models.py` — `SchwabExecutionLeg` + `SchwabOrderResponse` UNCHANGED.
- Within `swing/trades/schwab_reconciliation.py`: helpers `_compute_execution_price` + `_resolve_match_quantity` + `_is_execution_bearing_candidate` + Path B sentinel emit UNCHANGED. T-1.5 narrowly touches `_pivot_classify_and_dispatch_for_run` only.
- `swing/web/routes/schwab.py` (`/schwab/status` + `/schwab/setup`) UNCHANGED.
- `swing/data/migrations/0019_*.sql` UNCHANGED (and no `0020_*.sql` introduced).
- `swing/trades/reconciliation_ambiguity_choices.py` — operator menu UNCHANGED (menu still surfaces for tier-2 cases where predicate declines).

---

## §D Locked decisions roll-up (14 binding clauses, verbatim attribution)

All decisions below are **BINDING**. Codex chain MUST NOT re-litigate. Plan §G acceptance criteria encode them verbatim.

### §D.1 Operator-locks from spec §2 (brief §1.1-§1.4 + spec §2.1-§2.4)

1. **Auto-redirect posture = ON** (spec §2.1). V1 ships enabled. Classifier MUST emit `auto_redirect_recipe` when predicate fires. (Encoded: T-1.2.)
2. **Confidence threshold = all-match-within-tolerance** (spec §2.2). Predicate sub-conditions 3, 5, 6 enforce qty-sum + VWAP-journal-align + per-leg-consistency. Single outlier → tier-2. (Encoded: T-1.1.)
3. **Auto-correct handler shape = reuse `apply_tier2_resolution(choice_code='split_into_partials', resolved_by='auto_tier1_multi_leg', applied_by_override='auto', correction_action_override='auto_applied', operator_custom_payload=synthesized_payload)`** (spec §2.3). NO dedicated `apply_tier1_split_into_partials_auto` handler. (Encoded: T-1.4 + T-1.5 + recipe shape in T-1.1.)
4. **Operator-facing UX = banner advisory only** (spec §2.4). NO dedicated `/metrics/auto-redirects` review page. Base-layout VM banner + CLI filter. (Encoded: T-1.7 + T-1.8 + T-1.9 + T-1.10.)

### §D.2 Operator-locks from spec §15.B (locked 2026-05-17 post-brainstorm-merge per brief §1.5)

5. **`price_tolerance = $0.01` absolute LOCK** (spec §15.B #1). NO `max($0.01, abs(journal_price) * 0.001)` override. Operator's universe is $1-$70 stocks; proportional override is V2 candidate. Encoded as module-level constant `_MULTI_LEG_PRICE_TOLERANCE = 0.01` in T-1.1; no override path.
6. **`qty_tolerance` asymmetry preserved: predicate=1e-9 / handler=1e-6** (spec §15.B #2). Predicate stricter than handler is safe by construction; do NOT touch `_handle_split_into_partials`'s `qty_tolerance = 1e-6` at `swing/trades/reconciliation_auto_correct.py:1680`. Encoded as module-level constant `_MULTI_LEG_QTY_TOLERANCE = 1e-9` in T-1.1.
7. **NO defensive cap on N legs V1** (spec §15.B #3). Schwab supports arbitrary leg count; production evidence so far is zero multi-leg orders; mapper-coherence-check filters pathological cases upstream. Plan does NOT introduce `MAX_LEGS_PER_ORDER` constant. V2 candidate banked.

### §D.3 Brainstorm-locks from spec §15.A (Codex chain resolved)

8. **§6.5 n=1 single-order multi-leg path** — LOCKED via `ambiguity_kind` reclassification at the n=1 branch (Codex R1 M2 fix). Predicate fires on n=1 with `len(executions) >= 2`; classifier reclassifies `ambiguity_kind` from `'unknown_schwab_subtype'` to `'multi_partial_vs_consolidated'` to satisfy cross-column CHECK pairing AND route through the EXISTING `_TIER2_HANDLERS[('multi_partial_vs_consolidated', 'split_into_partials')]` registry entry. NO new handler key. Encoded: T-1.2 n=1 reclassification branch.
9. **§8.6 `--resolved-by <value>` CLI filter — LOCKED IN-BUNDLE at T-1.10** (Codex R1 M5 fix). Banner template (T-1.9) cites it; both land in the same integration merge.
10. **§7.6 sandbox short-circuit gated-on-auto-redirect** (Codex R1 M3 fix) — gated on `applied_by_override == 'auto'` (NOT environment alone) + SAVEPOINT ROLLBACK pattern. Manual operator path under sandbox proceeds. Encoded: T-1.6.
11. **§7.4 service API parameter naming** (Codex R1 M4 + R3 M1 + R3 M2 fix) — `operator_custom_payload` (existing kwarg; preserves verbatim) + 3 NEW override kwargs (`applied_by_override`, `correction_action_override`, `resolved_by_override`). Positional `conn` first arg preserved. Encoded: T-1.4.
12. **§11.2 briefing.md +1 line for `tier1_multi_leg_redirected_count` when > 0** (Codex R2 M1 fix — LOGICAL semantics via `COUNT(DISTINCT discrepancy_id)`). Encoded: T-1.11.
13. **§12.3 canary observability for empty-executions case** — `~+5 LOC + 1 test` (Sub-bundle 1.5 canary precedent). Encoded: T-1.11.
14. **`resolved_by` is free TEXT** (spec §13.3 + brainstorm return report §5 #7) — NO `_RESOLVED_BY_VALUES` Python constant exists (brief §2.4 writer error caught at brainstorm); no constant introduced in plan; no schema CHECK widening. Plan §F invariant pins this.

---

## §E Test patterns + discriminating-test naming convention

### §E.1 Naming convention

`test_<surface>_<scenario>_<expected_outcome>`. Examples:
- `test_predicate_fires_on_n_eq_2_with_1_leg_each` — surface=predicate; scenario=N=2 single-leg-each; outcome=fires.
- `test_apply_tier2_resolution_raises_on_mismatched_intent_combo` — surface=service entry; scenario=mismatched override combo; outcome=raises typed exception.
- `test_pivot_loop_auto_redirect_sandbox_short_circuit_rolls_back_stamp` — surface=pivot loop; scenario=sandbox short-circuit; outcome=stamp rolled back.

### §E.2 Discriminating-test discipline (lifted from Sub-bundle C plan + Phase 10 lessons)

- **Exact substring match for verbatim-locked strings.** When the plan locks a verbatim string (e.g., banner template text, briefing.md section heading), test asserts the substring via `assert "the locked text" in rendered_output`. Discriminating: the test FAILS if the string is paraphrased.
- **Counter assertion uses COUNT(DISTINCT) semantics** (per lesson #8). Tests for `count_recent_multi_leg_auto_corrections` + briefing counter MUST plant N+1 correction rows (1 anchor + N partials from `_handle_split_into_partials`) and assert the result is 1, NOT N+1.
- **Override-combo test matrix** (T-1.4): tabulate every 4-tuple `(applied_by_override, correction_action_override, resolved_by_override, choice_code)` ∈ valid combos × invalid combos; assert `_validate_override_combo` raises vs returns as documented.
- **`ClassificationResult.auto_redirect_recipe is None` regression pin** (T-1.2): exhaustive test that constructs every pre-existing classifier emit path's fixture + asserts `result.auto_redirect_recipe is None`. Discriminating: catches any future emit-path that accidentally synthesizes a recipe.
- **Field-introspection discipline** (T-1.8): use `dataclasses.fields(VMClass)` to enumerate fields; assert new field present on EVERY base-layout VM (NOT just the listed ones).
- **ASCII-only banner pin** (T-1.9): `assert all(ord(c) < 128 for c in banner_text)`. Cumulative coverage for spec §16 lesson #7.
- **Slow integration test marker** (T-1.5 E2E): `@pytest.mark.slow` so the fast suite (`pytest -m "not slow" -q`) does NOT pick it up; explicit `pytest -m slow` invocation runs it (matches Phase 9 + 10 + 12 precedents).
- **caplog capture** for canary observability (T-1.11): `caplog.set_level(logging.WARNING, logger='swing.trades.reconciliation_classifier')`; assert WARNING record present + content matches.

---

## §F Invariants (non-negotiable contracts spanning multiple tasks)

These are LOCK invariants that survive across T-1.1 through T-1.11. Codex review MUST validate every task respects all of them.

| # | Invariant | Source | Discriminating regression test pattern |
|---|---|---|---|
| F1 | **ZERO new schema.** Schema v19 unchanged; no `0020_*.sql`; no CHECK enum widening. | Spec §13.1 + §15.B #3 + plan-author schema escalation rule | Codex chain confirms via `grep -rn "0020" swing/data/migrations/` returns 0 matches. |
| F2 | **ZERO change to `apply_tier1_correction` external surface.** Spec §5 boundary preserved; Pass-1 auto-correct stays Pass-1. | Spec §1 architectural lift scope | `grep -n "def apply_tier1_correction" swing/trades/reconciliation_auto_correct.py` shows unchanged signature. |
| F3 | **ZERO change to existing `apply_tier2_resolution` default behavior.** All pre-existing call sites (operator CLI; future web tier-2 surface) work identically with default-None override kwargs. | Spec §7.1 + brainstorm forward-binding lesson #2 | T-1.4 includes `test_apply_tier2_resolution_legacy_default_path_no_overrides_writes_operator_shape` regression pin. |
| F4 | **ZERO change to determinism principle.** Predicate is pure; same inputs → same outputs; no time-dependent or random behavior. | Spec §4.4 inheritance | T-1.1 includes determinism spot-check via running the same fixture × 100 invocations + asserting byte-for-byte identical results. |
| F5 | **NO `Co-Authored-By` footer on ANY commit.** Per project invariant + brainstorm chain ZERO drift across 7 commits + Phase 12 Sub-bundle C chain ZERO drift. | CLAUDE.md "No Claude co-author footer" convention | Brief explicit prompt suppression at executing-plans dispatch time + verify-pre-merge orchestrator rebase check. |
| F6 | **NO `--no-verify`.** All commits hit pre-commit hooks. | CLAUDE.md conventions | N/A — process discipline. |
| F7 | **`resolved_by` is free TEXT.** No new Python constant; no schema CHECK widening. | Spec §13.3 + brainstorm return report §5 #7 | T-1.4 acceptance criterion: `grep -n "_RESOLVED_BY_VALUES" swing/` returns 0 matches. |
| F8 | **qty_tolerance asymmetry preserved: predicate=1e-9 / handler=1e-6.** | Spec §15.B #2 | T-1.4 acceptance: `swing/trades/reconciliation_auto_correct.py:1680` `qty_tolerance = 1e-6` UNCHANGED. T-1.1 acceptance: `_MULTI_LEG_QTY_TOLERANCE = 1e-9`. |
| F9 | **`price_tolerance = $0.01` absolute** (no override path). | Spec §15.B #1 | T-1.1 acceptance: `_MULTI_LEG_PRICE_TOLERANCE = 0.01` (constant; no `max(...)` override). |
| F10 | **NO defensive cap on N legs.** | Spec §15.B #3 | T-1.1 acceptance: predicate test `test_predicate_fires_on_n_eq_2_with_multi_leg_each_5_total` includes 5 legs; no `MAX_LEGS_PER_ORDER` constant. |
| F11 | **All base-layout VMs MUST inherit `recent_multi_leg_auto_correction_count`.** Per Phase 10 T-E.3 retrofit precedent + CLAUDE.md `base.html.j2` gotcha. | Spec §3 module touch list + spec §16 lesson #6 | T-1.8 includes the introspection test `test_every_vm_with_unresolved_material_field_also_has_recent_multi_leg_field`. |
| F12 | **Banner template text MUST be ASCII-only.** Windows cp1252 gotcha. | Spec §8.3 + §16 lesson #7 + CLAUDE.md cp1252 gotcha | T-1.9 includes `test_base_layout_multi_leg_banner_ascii_only`. |
| F13 | **SAVEPOINT-per-discrepancy preserved at flow-pivot.** No SAVEPOINT semantics change in `_pivot_classify_and_dispatch_for_run`. | Sub-bundle C.C R2 Minor #1 LOCK + spec §7.5 LOCK | T-1.5 acceptance: SAVEPOINT/RELEASE pattern preserved + `_SandboxAutoRedirectShortCircuit` triggers ROLLBACK TO + RELEASE. |
| F14 | **Classifier purity preserved.** Predicate + recipe synthesizer pure; no DB / API / logging side-effects (canary `logger.warning` in T-1.11 is the ONE exception). | CLAUDE.md "Classifier is a PURE function" gotcha | T-1.1 acceptance: predicate signature accepts only Mapping + scalars; no `conn`. |
| F15 | **Hybrid-row invariant** (`applied_by='auto'` + `correction_action='auto_applied'` + `correction_choice='split_into_partials'`) is valid IFF parent `resolved_by='auto_tier1_multi_leg'`. Enforced by `_validate_override_combo`. | Spec §7.3.1 BINDING + Codex R3 M2 LOCK | T-1.4 includes the full override-combo test matrix. |
| F16 | **Exception specificity ordering.** `InvalidOverrideComboError` (subclass of `ValueError`) catch comes FIRST and re-raises (where applicable per T-1.5 plan decision); generic `ValueError` catch second. | Spec §7.4 R4 M2 LOCK + lesson #11 | T-1.5 includes `test_pivot_loop_auto_redirect_invalid_override_combo_logs_warning_increments_tier_errored_count`. |
| F17 | **Sandbox short-circuit lives in inner not outer.** C.C lesson #2 carry-forward. | Spec §7.6.1 + lesson #5 | T-1.6 includes `test_apply_tier2_resolution_inner_sandbox_short_circuits_on_auto_override_combo`. |
| F18 | **Counter ROW-vs-LOGICAL semantics.** `COUNT(DISTINCT discrepancy_id)` for any "auto-correction count" metric. | Spec §11.2 + lesson #8 | T-1.7 + T-1.11 include planted-N+1-rows tests asserting count == 1. |
| F19 | **Plan-author schema additions escalation.** If Codex review surfaces a need for schema addition, STOP + escalate to orchestrator BEFORE encoding in plan. | Phase 9 Sub-bundle A return report lesson #7 + spec §16 lesson #3 | Plan author cites this lock at §F19; Codex chain verifies via plan inspection. |

---

## §G Per-task acceptance-criteria narrative

Most acceptance criteria are encoded inline in §A. This section deepens the criteria for the 3 tasks that span multiple files OR multiple architectural layers:

### §G.1 T-1.4 narrative (override kwarg threading)

The parameterization touches 13+ functions in `swing/trades/reconciliation_auto_correct.py`. The signature pattern for every `_handle_*` helper:

```python
def _handle_<choice>(
    conn,
    *,
    disc,
    choice_code,
    operator_custom_payload,
    operator_reason,
    risk_policy_id,
    schwab_api_call_id,
    # NEW IN PHASE 12.5 #1:
    applied_by_override: str | None = None,
    correction_action_override: str | None = None,
    resolved_by_override: str | None = None,
):
    ...
    # In the body, when constructing _build_tier2_correction:
    correction = _build_tier2_correction(
        ...,
        applied_by=applied_by_override if applied_by_override else "operator",
        correction_action=correction_action_override if correction_action_override else "operator_resolved_ambiguity",
        ...,
    )
    # In the body, when invoking _flip_discrepancy_to_resolved_ambiguity:
    _flip_discrepancy_to_resolved_ambiguity(
        conn,
        discrepancy_id=disc.discrepancy_id,
        resolution_reason=...,
        resolved_by=resolved_by_override if resolved_by_override else "operator",
    )
```

**Per-handler audit checklist** (executing-plans implementer MUST verify each `_handle_*` propagates correctly):
- `_handle_no_mutation_audit` — 1 correction row; thread overrides.
- `_handle_single_field_correction` — 1 correction row; thread.
- `_handle_multi_field_correction` — N field corrections; thread to each.
- `_handle_keep_journal_as_is` — 1 no-mutation correction row; thread.
- `_handle_consolidate_using_operator_vwap` — 1 correction row; thread.
- `_handle_split_into_partials` — **N+1 correction rows** (1 deletion-anchor + N partial-insertion rows); thread overrides to ALL rows.
- `_handle_custom_audit_only` — 1 correction row; thread.
- `_handle_mark_unmatched` — 1 no-mutation correction row; thread.
- `_handle_acknowledge` — 1 no-mutation correction row; thread.
- `_handle_operator_truth` — 1 correction row; thread.
- `_handle_operator_alternative` — 1 correction row; thread.
- `_handle_pick_schwab_record_n` — 1 correction row; thread.

**Test pattern per handler** (skip the test if a handler's invocation is functionally untouched by the auto-redirect path — only `_handle_split_into_partials` is exercised by auto-redirect, but T-1.4's `test_apply_tier2_resolution_legacy_default_path_no_overrides_writes_operator_shape` is parametrized across all handlers to verify the default-None back-compat invariant).

### §G.2 T-1.5 narrative (pivot-loop branch surgery)

The current `_pivot_classify_and_dispatch_for_run` has a clear branch structure at line 471 (`if classification.tier == 1:` ... line 517 `else:` tier-2 stamp). The new branch goes BETWEEN:

```python
if classification.tier == 1:
    # ... existing Pass-1 tier-1 auto-correct path ...
elif classification.tier == 2 and classification.auto_redirect_recipe is not None:
    # NEW IN PHASE 12.5 #1: multi-leg auto-redirect path.
    recipe = classification.auto_redirect_recipe
    try:
        # Defense-in-depth: validate override combo BEFORE any mutation.
        _validate_override_combo(
            choice_code=recipe["choice_code"],
            applied_by_override=recipe["applied_by_override"],
            correction_action_override=recipe["correction_action_override"],
            resolved_by_override=recipe["resolved_by"],
        )
        _stamp_pending_ambiguity_inner(
            conn,
            discrepancy_id=disc.discrepancy_id,
            ambiguity_kind=classification.ambiguity_kind or "multi_partial_vs_consolidated",
            resolution_reason=classification.correction_reason,
        )
        _apply_tier2_resolution_inner(
            conn,
            discrepancy_id=disc.discrepancy_id,
            choice_code=recipe["choice_code"],
            operator_custom_payload=recipe["payload"],
            operator_reason=f"multi-leg auto-redirect: {classification.correction_reason}",
            applied_by_override=recipe["applied_by_override"],
            correction_action_override=recipe["correction_action_override"],
            resolved_by_override=recipe["resolved_by"],
            risk_policy_id=None,
            schwab_api_call_id=schwab_api_call_id,
            environment=environment,
        )
        conn.execute(f"RELEASE SAVEPOINT {sp_name}")
        counters["tier1_multi_leg_auto_redirected_count"] += 1
    except _SandboxAutoRedirectShortCircuit:
        conn.execute(f"ROLLBACK TO SAVEPOINT {sp_name}")
        conn.execute(f"RELEASE SAVEPOINT {sp_name}")
        counters["sandbox_auto_redirect_skipped_count"] += 1
        log.warning(
            "auto-redirect short-circuited under sandbox for discrepancy %d",
            disc.discrepancy_id,
        )
        # The outer `try: ... except Exception` at line 529 is NOT re-entered;
        # we've already cleaned up the savepoint. Loop continues to next disc.
else:
    # Existing tier-2 stamp path (unchanged).
    _stamp_pending_ambiguity_inner(
        conn,
        discrepancy_id=disc.discrepancy_id,
        ambiguity_kind=classification.ambiguity_kind or "unsupported",
        resolution_reason=classification.correction_reason,
    )
    conn.execute(f"RELEASE SAVEPOINT {sp_name}")
    counters["tier2_pending_count"] += 1
```

The outer `except Exception as e:` at line 529 catches `InvalidOverrideComboError` (which subclasses `ValueError` → `Exception`) and `ValidatorRejectedError`. The branch sequence preserves graceful-degradation contract at line 429.

**Counter init pattern at line 432:**
```python
counters.setdefault("tier1_applied_count", 0)
counters.setdefault("tier2_pending_count", 0)
counters.setdefault("tier_errored_count", 0)
counters.setdefault("tier1_multi_leg_auto_redirected_count", 0)
counters.setdefault("sandbox_auto_redirect_skipped_count", 0)
```

### §G.3 T-1.8 narrative (≥17 VM retrofit)

The retrofit MUST cover every dataclass that has `unresolved_material_discrepancies_count` (T-1.7 helper consumer). The pattern per VM:

```python
@dataclass(frozen=True)
class FooVM(BaseLayoutVM):
    # ... existing fields ...
    unresolved_material_discrepancies_count: int = 0
    # NEW IN PHASE 12.5 #1:
    recent_multi_leg_auto_correction_count: int = 0
```

Builder pattern:
```python
def build_foo(conn, ...) -> FooVM:
    unresolved = count_unresolved_material(conn)
    recent_multi_leg = count_recent_multi_leg_auto_corrections(conn)  # NEW
    return FooVM(
        ...,
        unresolved_material_discrepancies_count=unresolved,
        recent_multi_leg_auto_correction_count=recent_multi_leg,  # NEW
    )
```

**Defense-in-depth introspection test** (mirrors Phase 10 lesson E2):

```python
def test_every_vm_with_unresolved_material_field_also_has_recent_multi_leg_field():
    import importlib
    import pkgutil
    import dataclasses
    import swing.web.view_models
    
    mod_paths = [
        f"swing.web.view_models.{name}"
        for _, name, _ in pkgutil.iter_modules(swing.web.view_models.__path__)
    ]
    mod_paths.extend([
        f"swing.web.view_models.metrics.{name}"
        for _, name, _ in pkgutil.iter_modules(swing.web.view_models.metrics.__path__)
    ])
    
    for mod_path in mod_paths:
        mod = importlib.import_module(mod_path)
        for attr_name in dir(mod):
            attr = getattr(mod, attr_name)
            if dataclasses.is_dataclass(attr) and not isinstance(attr, type):
                continue  # instance, not class
            if not (dataclasses.is_dataclass(attr) and isinstance(attr, type)):
                continue
            field_names = {f.name for f in dataclasses.fields(attr)}
            if "unresolved_material_discrepancies_count" in field_names:
                assert "recent_multi_leg_auto_correction_count" in field_names, (
                    f"VM class {mod_path}.{attr_name} has "
                    f"unresolved_material_discrepancies_count but is MISSING "
                    f"recent_multi_leg_auto_correction_count. Per Phase 10 "
                    f"T-E.3 retrofit precedent + CLAUDE.md base.html.j2 "
                    f"gotcha — every base-layout VM must carry both fields."
                )
```

This test catches `account.py` if it later gains the field, and any future VM that adds `unresolved_material_discrepancies_count` without the sibling — defense-in-depth per spec §16 lesson #6.

---

## §H Operator-witnessed gate plan (6 surfaces)

Per spec §9.3 + dispatch brief §3 projection.

### §H.1 S1 — Inline pytest + ruff baseline

- Run: `pytest -m "not slow" -q` from the executing-plans worktree root.
- Pass criterion: ALL fast tests pass (target ~4660 = 4575 baseline + ~85 new). 3 pre-existing `phase8 walkthrough` failures acknowledged (banked under Phase 12.5 #3 maintenance dispatch); no other failures.
- Run: `ruff check swing/`.
- Pass criterion: ruff baseline 18 E501 UNCHANGED (per spec invariant + post-Phase-12 Sub-bundle 2 ship baseline).
- Run: `pytest -m slow tests/trades/test_pivot_loop_auto_redirect_dispatch.py::test_e2e_phase12_5_1_full_flow_through_pivot_loop_to_banner_count`.
- Pass criterion: slow E2E test PASS.

### §H.2 S2 — Synthetic-fixture predicate matrix walk-through

- Approach: `python -c "from swing.trades.reconciliation_classifier import _multi_leg_auto_redirect_predicate, _synthesize_split_into_partials_recipe; ..."` exercising 5-8 distinct fixtures (subset of §10 cases A-J from the spec).
- Plant fixtures: Case A (n=1 multi-leg fires), Case C (per-leg outlier declines), Case E (VWAP-journal misalign), Case I (N=2 candidates × multi-leg each).
- Pass criterion: each fixture produces the expected predicate result + (when fires) the expected recipe shape per spec §10. Determinism spot-check via running each fixture × 10 invocations + asserting byte-for-byte identical `ClassificationResult` via frozen dataclass equality.

### §H.3 S3 — Production fetch end-to-end

- Run: `python -m swing.cli schwab fetch --orders --environment production` from the executing-plans worktree (per `feedback_worktree_cli_invocation.md`).
- Expected outcome (most likely per Sub-bundle 1.5 30-day production sample showing ZERO multi-leg fills): NO multi-leg auto-redirect fires; emitted `reconciliation_run` has `tier1_multi_leg_auto_redirected_count = 0`; banner does NOT appear. **Negative-sense pass criterion:** ZERO false-positive auto-redirects on non-multi-leg cases (existing Pass-1 tier-1 + Pass-2 tier-2 paths fire as pre-existing logic).
- Alternative outcome (if operator's production has accumulated a multi-leg fill): auto-redirect fires; counter > 0; banner appears on dashboard.
- Sandbox cross-check (optional): re-run with `--environment sandbox` + verify sandbox short-circuit fires (audit row written to `schwab_api_calls`; ZERO journal mutation).

### §H.4 S4 — Banner UI

- Run: `swing web --port 8081 &` from the executing-plans worktree.
- Plant: insert a synthetic multi-leg auto-correction via direct SQL fixture (mirror the Sub-bundle C.D banner-fires gate pattern). UPDATE `reconciliation_discrepancies` set `resolved_by='auto_tier1_multi_leg'` on an existing discrepancy + plant a fresh `reconciliation_runs` row with `state='completed'` referencing the corrections.
- curl: `curl -s http://127.0.0.1:8081/ | grep -c 'class="reconciliation-auto-redirect-banner"'`.
- Pass: count > 0; banner text matches spec §8.3 verbatim; ASCII-only (no high codepoints in the snippet).
- Banner-clears test: insert a fresh `reconciliation_run` row with `state='completed'` AND zero auto-redirected corrections in it → curl again → banner count drops to 0 (clears semantic per spec §8.4 LOCK).
- Tier-3 override does NOT clear the banner mid-window — invoke `apply_tier3_override` on the auto-redirected chain head + assert banner STILL present + count unchanged (per spec §9.3 S4 Codex R4 Minor 2 + R5 Minor 1 LOCK).
- Cleanup: revert the planted state to operator-acknowledged form per Phase 12 Sub-bundle C.D gate-cleanup precedent.

### §H.5 S5 — CLI `--resolved-by` filter

- Run: `swing journal discrepancy list --resolved-by auto_tier1_multi_leg`.
- Pass (when planted state from S4 exists): returns the planted multi-leg row(s).
- Negative test: `swing journal discrepancy list --resolved-by nonexistent_value` → "(no discrepancies)".
- Compose test: `swing journal discrepancy list --resolved-by auto_tier1_multi_leg --material` → returns multi-leg rows that also have `material_to_review=1`.

### §H.6 S6 — Briefing.md +1 line

- Run pipeline: `python -m swing.cli pipeline run` from worktree (under the planted S4 state).
- Inspect: `cat exports/<action_session_date>/briefing.md | grep -A 5 "## Reconciliation status"`.
- Pass (when count > 0): the section contains the new `- Multi-leg auto-redirected (last 7 days): K` line; K matches the planted count.
- Pass (when count == 0; default production state): the section either absent (all 3 counters 0) OR present without the new line (other counters > 0).

**SKIPPED gate surfaces** (per polish-bundle-2026-05-10 precedent + spec §9.3 budget):
- S2 may be SKIPPED-with-test-coverage if T-1.1 + T-1.2 + T-1.4 fast tests cover every case enumerated in §H.2.
- S6 may be SKIPPED-with-test-coverage if T-1.11's `test_briefing_md_emits_multi_leg_line_when_count_gt_zero` covers the assertion.

---

## §I Cross-bundle pins (single-bundle dispatch; consumer of shipped surfaces)

Phase 12.5 #1 is a single-sub-bundle dispatch with NO upstream pin to land — all cross-bundle dependencies are CONSUMER-side reads of already-shipped surfaces:

| Pin source | Pin target | Status |
|---|---|---|
| Sub-bundle C.A (`354b6c0`) | Schema v19 + cross-column CHECK on `reconciliation_discrepancies` + `reconciliation_corrections.applied_by`/`correction_action` CHECK enums | SHIPPED; spec §13.1 verifies all already-permit Phase 12.5 #1 values |
| Sub-bundle C.B (`aacd1cd`) | `ClassificationResult` dataclass + `classify_discrepancy` dispatch + sub-classifier registry | SHIPPED; T-1.2 EXTENDS the dataclass (additive default-None field) |
| Sub-bundle C.C (`0b9d253`) | `apply_tier2_resolution` outer/inner + `_handle_*` registry + `_pivot_classify_and_dispatch_for_run` SAVEPOINT discipline | SHIPPED; T-1.4 + T-1.5 + T-1.6 EXTEND signatures |
| Sub-bundle C.D (`bd1a62b`) | `swing journal discrepancy list` CLI + Phase 10 banner predicate widening to `pending_ambiguity_resolution` | SHIPPED; T-1.10 EXTENDS the CLI with `--resolved-by` filter |
| Sub-bundle 1 (`120c992`) | `SchwabExecutionLeg` + `SchwabOrderResponse.executions` field on mapper + comparator switch to execution-grain + Path B sentinel | SHIPPED; T-1.3 reads `o.executions` |
| Sub-bundle 1.5 (`a7c1016`) | `_has_non_placeholder_leg` canary helper precedent + filledQuantity=0 early-exit gate | SHIPPED; T-1.11 mirrors the canary discipline |
| Sub-bundle 2 (`690aed0`) | `SchwabSetupVM` + `SchwabStatusVM` + `SchwabSetupErrorVM` base-layout retrofit (5-field) | SHIPPED; T-1.8 EXTENDS these three VMs in `swing/web/view_models/schwab.py` |
| Phase 10 T-E.3 | 17 base-layout VMs (BaseLayoutVM mixin pattern) | SHIPPED; T-1.8 EXTENDS all of them |

**No new cross-bundle pin tests** required (all upstream surfaces are already SHIPPED on `main` — pinning is implicit via consumption).

---

## §J V2.1 §VII.F amendment candidates banked during planning (scaffold)

This section is **EMPTY at plan-drafting time**. Populated during the writing-plans Codex chain if any spec-text deviations surface. (Plan-drafting deviations would otherwise route through Phase 12.5 #3 maintenance dispatch.)

Per the brainstorm return report §11, ONE spec amendment is already pending V2.1 §VII.F routing:
- **Brief §2.4 amendment** — brief referenced extending `_RESOLVED_BY_VALUES` Python constant; no such constant exists in the codebase. `resolved_by` is free TEXT both at schema layer + Python passthrough. Spec §13.3 LOCKS this; plan §D #14 + §F invariant F7 carry forward.

Additional amendments may be banked during the Codex chain.

---

## §K Test + LOC projections (refined per-task)

| Task | LOC (production) | LOC (tests) | Fast tests | Slow tests |
|---|---|---|---|---|
| T-1.1 | ~+90 (helpers + constants) | ~+100 | ~17 | — |
| T-1.2 | ~+30 (field + classifier branches) | ~+80 | ~14 | — |
| T-1.3 | ~+10 (executions key) | ~+30 | ~5 | — |
| T-1.4 | ~+120 (parameterization + validator + exception) | ~+90 | ~12 | — |
| T-1.5 | ~+50 (pivot-loop branch) | ~+80 | ~10 + 1 slow | 1 |
| T-1.6 | ~+15 (sandbox short-circuit) | ~+40 | ~6 | — |
| T-1.7 | ~+30 (helper) | ~+40 | ~7 | — |
| T-1.8 | ~+15 (1 LOC × ~17 VMs) | ~+50 | ~9 | — |
| T-1.9 | ~+5 (banner block) | ~+30 | ~5 | — |
| T-1.10 | ~+15 (CLI filter) | ~+30 | ~4 | — |
| T-1.11 | ~+25 (canary + briefing line) | ~+50 | ~9 | — |
| **TOTAL** | **~+405** | **~+620** | **~98** | **1** |

**Net projection:** ~+405 production LOC + ~+620 test LOC = ~+1025 LOC; ~98 fast tests + 1 slow E2E test.

**Variance from spec §9.2 projection (~+320 LOC + ~+85 fast tests + 1 slow E2E):** plan is HIGHER on both axes. Causes:
- T-1.4 LOC inflation: spec projected ~+40 LOC but the parameterization touches 12 `_handle_*` helpers + a new validator helper + a typed exception class. Inflation absorbed by per-handler threading work.
- Tests above projection: the introspection-based defense-in-depth pattern in T-1.8 + the override-combo matrix in T-1.4 + the canary observability in T-1.11 each add ~3-5 tests beyond the spec's nominal projection.
- This matches the Phase 9 / 10 / 12 overshoot precedent ("+85-130 projected → +139 actual" at C.B; "+65-115 projected → +95 actual" at C.C; "+85 projected → ~98 actual" here).

**Schema impact:** v19 UNCHANGED (LOCK per spec §13.1). NO migration files.

**Codex chain projection (writing-plans phase):** 3-5 rounds expected. Brainstorm absorbed 7 rounds + ZERO ACCEPT-WITH-RATIONALE → spec is exhaustively locked → plan should converge faster.

**Codex chain projection (executing-plans phase):** 3-5 rounds (matches Sub-bundle 2 + C.D precedent for single-sub-bundle execution).

---

## §L Dispatch brief skeleton (orchestrator hand-off for executing-plans)

The executing-plans dispatch brief at `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-executing-plans-dispatch-brief.md` SHALL include:

1. **§0 Read first** — links to spec + brainstorm return report + this plan + Sub-bundle C plan (for format reference) + CLAUDE.md gotchas section.
2. **§1 Pre-locked decisions** — verbatim quote of plan §D's 14 LOCKs.
3. **§2 Task list** — references plan §A T-1.1 .. T-1.11 (dispatch order: T-1.1 → T-1.2 → T-1.3 → T-1.4 → T-1.5 → T-1.6 → T-1.7 → T-1.8 → T-1.9 → T-1.10 → T-1.11). Parallelizable: T-1.3 + T-1.7 can land before T-1.4; T-1.10 is independent of T-1.5-T-1.8.
4. **§3 Pre-flight verifications** — grep anchors per plan §C; assert (a) schema_version == 19; (b) `_RESOLVED_BY_VALUES` constant absent (`grep -rn "_RESOLVED_BY_VALUES" swing/` returns 0); (c) `apply_tier2_resolution` signature has 7 kwargs currently (validates T-1.4 baseline); (d) `_orders_to_classifier_payload` does NOT currently include `executions` key (validates T-1.3 baseline); (e) `BaseLayoutVM` lacks `recent_multi_leg_auto_correction_count` field (validates T-1.8 baseline).
5. **§4 Adversarial review watch items** — mirror spec §15 Codex watch items + plan §F invariants F1-F19 + the 12 forward-binding lessons from the brainstorm return report §8.
6. **§5 Operator-witnessed gate plan** — references plan §H (6 surfaces).
7. **§6 OUT OF SCOPE** — schema additions (per F1 + F19 escalation rule); ANY override of §D locks; phase 12.5 #2 web Tier-2 surface; phase 12.5 #3 maintenance pass; V2 candidates (spec §14 + plan §Z).
8. **§7 If you get stuck** — mirror brainstorm-brief §7 + plan §F19 escalation rule.
9. **§8 Return report shape** — final HEAD + commit count breakdown; Codex chain summary; gate verdict per surface; banked V2.1 §VII.F amendments; forward-binding lessons; CLAUDE.md status-line draft text; schema impact verdict (v19 UNCHANGED expected); composition-surface verification (`^def ` grep on touched modules); worktree teardown status.

**Commit message stem** (after Codex chain converges + plan commit lands):
```
docs(phase12-5-1-oqf-plan): single-sub-bundle decomposition — N Codex rounds → NO_NEW_CRITICAL_MAJOR; 14 pre-locked decisions encoded; schema v19 unchanged; ~+85/+320 projections
```

---

## §M Forward-binding lessons for executing-plans (scaffold)

Empty at plan-drafting. Populated post-Codex-chain with discovered lessons. Likely candidates inherited from brainstorm return report §8:
- Recipe-field discipline.
- Override-parameter threading.
- Free-text vs CHECK-enum columns.
- Cross-column CHECK invariants.
- Sandbox short-circuit ALWAYS in inner.
- Helper invocation completeness across base-layout VMs.
- ASCII-only banner text.
- Counter ROW-vs-LOGICAL semantics.
- Validate override combos BEFORE state mutation.
- Shape-aware terminal-state idempotency.
- Exception specificity ordering in catch blocks.
- Positional-vs-keyword signature audit at writing-time.

---

## §N Open questions for orchestrator triage (scaffold; default empty)

If the writing-plans Codex chain surfaces undecidable scope items requiring orchestrator escalation per F19, log them here. Default empty.

---

## §Z V2 candidates banked (mirrored from spec §14)

1. **Banner predicate window — 7-day rolling** (spec §14 #1). V2 widens helper signature with `window='rolling_7_day'` branch.
2. **Banner predicate window — persists-until-acknowledged** (spec §14 #2). Requires new `recent_auto_redirect_acknowledged_at` persistence column.
3. **Dedicated `/metrics/auto-redirects` review page** (spec §14 #3). Operator rejected V1.
4. **Schwab cassette recording for multi-leg fill** (spec §14 #4). Operator-paired session; defer until production multi-leg fill surfaces.
5. **Defensive cap on N legs** (spec §14 #5 + §15.B #3).
6. **`_RESOLVED_BY_VALUES` Python constant formalization** (spec §14 #6 + §13.3 V2.1 §VII.F amendment).
7. **Promote `auto_redirect_recipe` to typed dataclass** (spec §14 #7).
8. **Per-leg `mismarked_quantity` consumption** (spec §14 #8).
9. **Operator-acknowledged-clear surface** — CLI subcommand `swing journal reconciliation acknowledge-redirects` (spec §14 #9).
10. **Predicate-on-n=1 LOCKED IN V1** (spec §14 #10; promoted from V2 to V1 LOCK at brainstorm — see plan §D #8).
11. **Audit trail surfacing in `show-correction` epilog** (spec §14 #11). V2 polish.
12. **Other tier-2 ambiguity_kinds auto-redirect candidates** (spec §14 #12). `multi_match_within_window` with single-execution-bearing record could become auto-redirect at V2 reusing plan §A T-1.1 + T-1.2 helpers.

---

*End of plan. Phase 12.5 #1 writing-plans dispatch — 14 operator+brainstorm-locks pre-baked; single-sub-bundle decomposition; 11 tasks T-1.1 .. T-1.11; schema v19 UNCHANGED; ~+85 fast tests + 1 slow E2E + ~+320 LOC projection. Codex chain projected 3-5 rounds. Executing-plans dispatch UNBLOCKED after Codex chain converges + plan commit lands.*
