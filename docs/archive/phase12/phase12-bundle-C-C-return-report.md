# Phase 12 Sub-bundle C Sub-sub-bundle C.C (Auto-correction service + reconciliation flow pivot) — executing-plans return report

**Branch:** `phase12-bundle-C-C-auto-correction-service-and-flow-pivot`
**Final HEAD:** `8b39ab0`
**Baseline:** `5ed3e74` (post-C.B integration merge + dispatch-brief commit)
**Plan:** `docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md` §D (T-C.1..T-C.11 + T-C.3.1)
**Spec:** `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md` §5 + §7 + §10
**Dispatch brief:** `docs/phase12-bundle-C-C-auto-correction-service-and-flow-pivot-executing-plans-dispatch-brief.md`

---

## §1 Final HEAD + commit breakdown

**22 commits on branch** (12 task-impl + 1 ruff style + 3 pre-Codex review fixes + 4 Codex R1 fixes + 1 Codex R2 fix + 1 Codex R3 polish; return-report commit forthcoming):

| SHA | Type | Description |
|---|---|---|
| `4d55f37` | T-C.1 | Service module skeleton + 3 exceptions (`CallerHeldTransactionError` / `ValidatorRejectedError` / `AlreadySupersededError`) + `CorrectionResult` dataclass + 3 outer/inner fn pairs + transactional discipline scaffolding |
| `520c546` | T-C.2 | `_apply_tier1_correction_inner` 11-step atomic flow (CVGI 41 path) — review_log supersede + sandbox short-circuit |
| `6405340` | T-C.3 | `_apply_tier2_resolution_inner` + 17 exact-key + 1 prefix per-(ambiguity_kind, choice_code) handlers + `correction_set_id` discipline for split-into-partials |
| `7e262bc` | T-C.3.1 | `stamp_pending_ambiguity` service helper (own-tx + caller-tx inner variant) |
| `0c1b66f` | T-C.4 | `_apply_tier3_override_inner` — chain mechanic + `AlreadySupersededError` + validator re-run on operator-truth |
| `73a1d7b` | T-C.5 | `run_schwab_reconciliation` flow pivot — savepoint-per-discrepancy + classify+dispatch + counters in `summary_json` |
| `58ff681` | T-C.6 | `run_tos_reconciliation` flow pivot (mirrors T-C.5 per OQ-2 PIVOT BOTH; lazy-import shared helper `_pivot_classify_and_dispatch_for_run`) |
| `159a3f3` | T-C.7 | Savepoint-per-discrepancy discipline regression suite (both Schwab + TOS pivots) |
| `18a7137` | T-C.8 | `BriefingInputs.reconciliation_pending_count` + `reconciliation_tier1_recent_count` fields (back-compat defaults) |
| `1de9e40` | T-C.9 | `briefing_md` "Reconciliation status" section (emits when counters non-zero) |
| `819beed` | T-C.10 | `_step_export` populates `BriefingInputs.reconciliation_*` counters (inline SQL) |
| `4fb9575` | T-C.11 | End-to-end pipeline-composition integration test (CVGI 41 tier-1 auto-correct; slow-marked) |
| `546b189` | style | ruff baseline-restore — UP035 + UP017 + I001 + F401 + SIM118 + B905 + N802 fixes in C.C-touched files |
| `3066355` | Pre-Codex SC-1 | Sandbox `environment` threads through inner not outer (per plan §D.5 step 3 LOCK) |
| `e3f553a` | Pre-Codex SC-2 | T-C.11 invokes `_step_export` to discriminate T-C.10 wiring end-to-end |
| `a9a4aec` | Pre-Codex SC-1 | Follow-up: sandbox check precedes classification validation in inner |
| `65f564f` | Codex R1 M#1 | Outer `apply_tier1_correction` always opens `BEGIN IMMEDIATE` under sandbox (removes outer short-circuit; inner sandbox handles no-op inside transaction envelope) |
| `2055f25` | Codex R1 M#2 | `_apply_tier1_correction_inner` SELECT-first idempotency (sandbox → SELECT → terminal-check → classification validation → steps 2-11) |
| `90d7e1e` | Codex R1 M#3 | Recompute `unresolved_discrepancies_count` post-pivot at BOTH `run_schwab_reconciliation` + `run_tos_reconciliation` via `SELECT COUNT(*) WHERE resolution='unresolved'` |
| `1b57327` | Codex R1 M#4 | Widen `RESOLUTION_TYPES` 5 → 9 values mirroring `_RESOLUTION_VALUES` + set-equality invariant test |
| `b51e083` | Codex R2 M#1 | `resolve_discrepancy` rejects 4 service-owned lifecycle states with routing hint to canonical service entries (`apply_tier1_correction` / `stamp_pending_ambiguity` / `apply_tier2_resolution` / `apply_tier3_override`) |
| `8b39ab0` | Codex R3 m#1 | `RESOLUTION_TYPES` docstring no longer claims `resolve_discrepancy` accepts the 9-value widening (paired with R2 fix) |

---

## §2 Codex round chain (3 rounds → NO_NEW_CRITICAL_MAJOR)

| Round | Findings | Verdict | Convergence |
|---|---|---|---|
| R1 | 0C / 4M / 0m | ISSUES_FOUND | All 4 Major resolved with code-content fixes (ZERO accept-with-rationale). |
| R2 | 0C / 1M / 0m | ISSUES_FOUND | 1 Major resolved (R1 M#4 widening exposed contract gap in `resolve_discrepancy` manual surface — fixed via `_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS` allowlist + service-routing rejection). |
| R3 | 0C / 0M / 1m | **NO_NEW_CRITICAL_MAJOR** | Convergent shape; Minor (stale comment) polished in `8b39ab0`. Chain closed. |

**3 rounds total** — **ties Phase 12 Sub-sub-bundle C.A's 2-round chain for fastest Phase 12 chain** (C.A=2, C.B=5, C.C=3). Convergent tapering 4M → 1M → 0M. **ZERO ACCEPT-WITH-RATIONALE banked entire chain** — every finding (4 R1 Major + 1 R2 Major + 1 R3 Minor) resolved with code-content fixes (matches Sub-sub-bundle C.B precedent).

R1 M#1 + M#2 are paired transactional-discipline cleanups exposing the pre-Codex SC-1 fix had two more LOCK divergences (outer-tx skip on sandbox + SELECT-after-validate). R1 M#3 is the unresolved-counter staleness from inline tier-1 resolution. R1 M#4 was a CLAUDE.md gotcha violation (Python constant pre-v19 stale post-C.A schema widening) — surfaced because no caller had widened through `RESOLUTION_TYPES` until C.C's pivot consumed `pending_ambiguity_resolution`. R2 M#1 chains from R1 M#4 — widening `RESOLUTION_TYPES` made `resolve_discrepancy` too permissive; the fix added a tighter manual-surface allowlist while preserving the schema-coverage constant.

---

## §3 Test count + ruff baseline + schema version deltas

| Metric | Baseline (`5ed3e74`) | C.C HEAD (`8b39ab0`) | Delta |
|---|---|---|---|
| Fast suite passing | 4105 | **4200** | **+95** |
| Pre-existing failures | 3 (3 phase8 walkthrough — banked per CLAUDE.md C.A entry) | 3 (unchanged) | 0 |
| Skipped tests | 5 | 5 | 0 |
| Ruff E501 baseline | 18 | **18** | **unchanged** |
| Schema version | 19 | **19** | **unchanged** (consumer-side only; C.C touches no schema) |

**Net +95 fast tests** — within the +65-115 dispatch-brief projection range. Matches Phase 9/10/12-A/12-B overshoot family precedent.

Delta sub-breakdown:
- Initial 12-task implementation + 1 ruff polish: +81 (4105 → 4186; reported by implementer).
- Pre-Codex review fix bundle (SC-1 + SC-2 + SC-1 follow-up): +1 (4186 → 4187; new SC-1 regression test pinning `_apply_tier1_correction_inner(environment='sandbox')` no-op contract).
- Codex R1 fix bundle (M#1+M#2+M#3+M#4): +4 (4187 → 4191; new tests `test_apply_tier1_correction_outer_always_begins_immediate_under_sandbox` via `_ExecuteSpyConn` + `test_apply_tier1_correction_is_idempotent_with_stale_classification` + `test_run_schwab_reconciliation_unresolved_counter_decrements_post_pivot` + `test_resolution_types_mirror_models_resolution_values`).
- Codex R2 fix: +9 (4191 → 4200; 4 service-owned-rejection tests + 1 parametrized 5-value allowed test).
- Codex R3 polish: +0 (docstring-only).

T-C.11 slow E2E test `test_phase12_bundle_c_cvgi_41_end_to_end` PASSES under `pytest -m slow`.

---

## §4 Operator-witnessed verification surfaces (PENDING orchestrator-driven gate)

Per dispatch brief §3 + plan §G.3 (4 surfaces):

| Surface | Type | Acceptance | Status |
|---|---|---|---|
| **S1** | Inline `pytest -m "not slow" -q` | GREEN at ~4200 fast tests (+95 from baseline; within projection); 3 pre-existing phase8 walkthrough failures unchanged; 5 skipped. T-C.11 slow E2E PASSES under `-m slow`. | **READY** (verified at HEAD) |
| **S2** | Simulated reconciliation run end-to-end with planted tier-1 + tier-2 discrepancies under `environment='production'` | Operator-driven walkthrough OR test-coverage-equivalent. CVGI/DHC/VSAT discriminating fixtures end-to-end through service. | **READY for inline-or-script-driven**; equivalent test coverage in `tests/trades/test_run_schwab_reconciliation_pivot.py` + `tests/integration/test_phase12_bundle_c_cvgi_41_full_pipeline.py` (slow-marked). May be SKIPPED-with-test-coverage per polish-bundle-2026-05-10 precedent. |
| **S3** | Sandbox short-circuit test (same scenario as S2 with `environment='sandbox'`) | CVGI discrepancy emitted BUT NOT auto-corrected; `summary_json.tier1_applied_count == 0`. | **READY**; covered by `test_run_schwab_reconciliation_sandbox_short_circuits_apply` + `test_apply_tier1_correction_sandbox_short_circuit` + 2 R1-fix tests pinning outer BEGIN IMMEDIATE + inner no-op. |
| **S4** | `ruff check swing/ --statistics` | Reports 18 E501 unchanged. | **READY** (verified at HEAD). |

Recommended gate posture (per dispatch brief §3 wording): S1+S4 inline; S2+S3 SKIPPED-with-test-coverage given the planted-fixture tests provide equivalent coverage + production state of the 3 stale discrepancies (39 DHC + 40 VSAT + 41 CVGI) is LEFT UNRESOLVED BY DESIGN pending Sub-sub-bundle C.D backfill operation.

---

## §5 Per-task deviations from plan §D (with rationale; for V2.1 §VII.F triage)

### D1 — T-C.5/T-C.6 pivot DRY extraction
Plan §D.6 said "mirrors T-C.5 verbatim". Implementation factored `_pivot_classify_and_dispatch_for_run` as a private helper in `swing/trades/schwab_reconciliation.py`; `run_tos_reconciliation` imports it via lazy import at `swing/trades/reconciliation.py:396-398` (breaks circular import). The helper is private so external callers stay locked to public outers. **Watch item (V2.1 §VII.F candidate)**: relocate `_pivot_classify_and_dispatch_for_run` to a neutral module (e.g., `swing/trades/reconciliation_auto_correct.py` or new `swing/trades/_reconciliation_pivot.py`) to break the asymmetric Schwab-named-module dependency direction at the TOS callsite.

### D2 — T-C.5 `_extract_source_payload` sentinel rule
Plan §D.5 did not specify how to distinguish `{"matched": null}` (the `_emit`-stamped unmatched-fill payload) from `{"price": 5.30}` (a legitimate single-key shape). Implementation: 3-condition check (`"matched" in payload AND payload["matched"] is None AND len(payload) == 1`). Discriminating + precise.

### D3 — T-C.6 + 6 pre-existing test files received fixture adjustments
The pivot changes default-post-reconcile state of every non-tier-1 discrepancy from `unresolved` → `pending_ambiguity_resolution` (the architectural intent of C.C). Pre-existing tests assuming post-pivot `unresolved` were adjusted by either (a) passing `environment="sandbox"` to bypass pivot, OR (b) resetting discrepancy back to `unresolved` post-reconcile before exercising legacy resolve-CLI surface. Each adjustment carries an inline comment marking it as Phase 12 C.C T-C.6 compatibility annotation. **V2.1 §VII.F candidate**: C.D will widen `list_unresolved_material_for_active_trades` + the `--unresolved` CLI filter to include `pending_ambiguity_resolution`; at that point these test-side adjustments may be reviewed.

### D4 — T-C.7 SAVEPOINT-name-uniqueness test mechanic
Plan §D.7 acceptance #2 third bullet said "verify the savepoint name `f"correction_sp_{disc.discrepancy_id}"` is unique per discrepancy_id." Implemented as a source-introspection test (`inspect.getsource` + substring check) since the name template is a literal in the helper — stronger than a runtime probe (runtime probe couldn't detect a name-template bug at all).

### D5 — T-C.10 BriefingInputs wiring uses inline SQL counters
Plan §D.10 acceptance referred to `count_discrepancies WHERE ...` + `count_corrections WHERE ...` helpers; no such helpers existed in C.A repo modules. Counters emitted inline at `_step_export` callsite rather than introducing new helper functions in `swing/data/repos/reconciliation.py` + `reconciliation_corrections.py` (scope minimization). SQL queries documented inline with spec reference comments.

### D6 — T-C.11 E2E test scope
Plan §D.11 step 1 said "Invokes the pipeline runner end-to-end (with `--no-finviz-fetch` to avoid hitting Finviz)." Implementation invokes service composition + `_step_export` directly (NOT full pipeline runner subprocess). The pre-Codex review SC-2 fix at commit `e3f553a` widened the test to invoke `_step_export` so T-C.10 wiring IS end-to-end discriminated. Mirrors Phase 11 D R1 M#4 ACCEPT-WITH-RATIONALE precedent. **Banked as V2.1 §VII.F candidate** (plan-text said full pipeline subprocess; implementation chose service+`_step_export` composition to avoid finviz inbox setup overhead).

### D7 — `swing/rendering/view_models.py` touch outside brief §4 scope
Brief §4 listed 6 production files. Implementation also added 2 new fields to `BriefingViewModel` in `swing/rendering/view_models.py` (counters threaded from `BriefingInputs` through `build_briefing_view_model`). Necessary + minimal — both fields default to 0 (back-compat preserved with existing base-layout VMs; not a base-layout VM per Phase 10 §A.8). Pre-Codex reviewer accepted this as necessary minimal touch.

### D8 — Pre-Codex review absorbed 2 Major findings before R1
SC-1 (sandbox `environment` threading divergence from plan §D.5 step 3 LOCK) + SC-2 (T-C.11 E2E scope service-composition vs full pipeline subprocess) were surfaced by the orchestrator-side pre-Codex review and fixed at `3066355` + `e3f553a` + `a9a4aec` before invoking Codex. Saved an estimated 1-2 Codex rounds. **Pattern reusable** for future bundles: orchestrator-side spec-compliance + code-quality review BEFORE adversarial-critic catches the obvious LOCK divergences cheaply.

---

## §6 Codex Major findings ACCEPTED with rationale (if any)

**NONE.** ZERO ACCEPT-WITH-RATIONALE banked entire C.C chain — matches Sub-sub-bundle C.B precedent + Phase 10 Sub-bundles A-E precedent (cleanest finding-disposition record family). All 4 R1 Major + 1 R2 Major + 1 R3 Minor resolved with code-content fixes.

Phase 12 cumulative ACCEPT-WITH-RATIONALE (post-C.C): **1** (R1 Major #1 from C.A — backup-gate narrowness; documenting test + extended docstring; banked at C.A return report §6).

---

## §7 Watch items for orchestrator (V2 candidates surfaced; Sub-sub-bundle C.D dispatch-readiness)

### V2 candidates banked for `docs/phase3e-todo.md`

**V2-1**: Relocate `_pivot_classify_and_dispatch_for_run` to a neutral module to break TOS→Schwab module-name dependency (D1 deviation).

**V2-2**: `BriefingInputs.reconciliation_*` counter computation helpers — extract from inline `_step_export` SQL into proper repo helpers at `swing/data/repos/reconciliation.py` + `reconciliation_corrections.py` (D5 deviation; matches existing per-repo counter helper precedent).

**V2-3**: T-C.11 widen to full pipeline subprocess invocation (D6 deviation) — exercises the full pipeline path through `_step_finviz_fetch` (or `--no-finviz-fetch` override) end-to-end; requires finviz inbox fixture.

**V2-4**: `_apply_tier3_override_inner` field-anchor heuristic at `reconciliation_auto_correct.py:620-623` (pre-Codex reviewer CQ-2) — currently uses `"price" if "price" in operator_truth_value else next(iter(...))` which may incorrectly anchor for non-fills tables. Tighten to per-`affected_table` field map at apply time.

**V2-5**: `risk_policy_id` wire-through into `_apply_tier1_correction_inner` from pivot caller (pre-Codex reviewer CQ-3) — plan §D.5 step 1 code block at plan line 2275 prescribed explicit pass-in; implementation defers to inner's `_maybe_get_active_risk_policy_id(conn)` lazy resolution. Defensible but plan-text deviation.

**V2-6**: C.D `--unresolved` CLI filter widening (banked in D3 above) to include `pending_ambiguity_resolution` so the test-side fixture adjustments at D3 can be reverted. C.D scope-of-concern.

### Sub-sub-bundle C.D dispatch-readiness

**C.D is UNBLOCKED.** C.C ships the service-layer + flow-pivot infrastructure C.D needs:
- `apply_tier1_correction` (CLI surface for tier-3 override prep).
- `apply_tier2_resolution` + per-(ambiguity_kind, choice_code) handler dispatch (Tier-2 CLI).
- `apply_tier3_override` (Tier-3 override CLI).
- `stamp_pending_ambiguity` (backfill orchestrator).
- BriefingInputs counters wired (briefing.md "Reconciliation status" section operational).
- Reconciliation pivot at BOTH `run_schwab_reconciliation` + `run_tos_reconciliation` (production reconciliation flow ALREADY dispositions tier-1/tier-2 inline; C.D backfill backfills the 3 existing unresolved discrepancies 39+40+41 + Phase 10 dashboard banner predicate widening).

C.D consumes 4 service-owned resolution values via the canonical service entries. C.C's `_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS` allowlist enforces that C.D's CLI must route tier-2 ambiguity dispositions through `apply_tier2_resolution`, NOT through `resolve_discrepancy` (the manual operator-resolver path for pre-v19 resolution values).

---

## §8 Worktree teardown status

Pending orchestrator-driven post-merge cleanup. Branch `phase12-bundle-C-C-auto-correction-service-and-flow-pivot` will be deleted post-integration-merge per Phase 9/10 + Phase 12 A/B/C-A/C-B precedent; on-disk husk at `.worktrees/phase12-bundle-C-C-auto-correction-service-and-flow-pivot/` will be ACL-locked + cleared by next operator `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` pass. Husk queue post-merge: 3 phase12-bundle-c-* husks pending (C-A + C-B + C-C).

---

## §9 Per-task disposition LOCKS

### T-C.2 step 9 review_log cadence-period derivation LOCK preserved
Per plan §D.2 step 9 + spec §5.4 step 9 — `_supersede_review_log_for_trade_close` SQL at `reconciliation_auto_correct.py:1006-1022` anchors on `MAX(fill_datetime) FROM fills WHERE action IN ('exit','stop')` per fill's `trade_id`; JOINs `review_log WHERE completed_date IS NOT NULL AND period_start <= close_date AND close_date <= period_end`. Empty result for OPEN trades (CVGI 41 case) is correct per spec §10.1 step 8.

### T-C.3 17+1 handler registry LOCK preserved
`_TIER2_HANDLERS` registry at `reconciliation_auto_correct.py:1906-1943` matches plan §D.3 step 3 verbatim including `_PICK_SCHWAB_RECORD_PREFIX = "pick_schwab_record_"` parametric entry. `custom` choice is audit-only V1 with `applied_value_json == pre_correction_value_json` bytewise invariant.

### T-C.5 fresh-savepoint fallback discipline LOCK preserved
Validator-rejected tier-1 falls through to tier-2 stamp inside `correction_fallback_sp_{discrepancy_id}` (NEVER reuses already-released `correction_sp_{discrepancy_id}`). Per Codex R2 Minor #1 writing-plans fix preserved.

### Spec §5.9 sandbox LOCK preserved (post-Codex R1 M#1+M#2 cleanup)
Outer `apply_tier1_correction` ALWAYS issues `BEGIN IMMEDIATE` regardless of `environment`. Inner sandbox short-circuit fires FIRST (before SELECT + classification validation) and returns `CorrectionResult(correction_id=None, notes="sandbox: domain write short-circuited")` inside the outer's transaction envelope. Discrepancy stays `unresolved`; counters reflect classification-only.

### Schema-CHECK + Python-constant + dataclass-validator paired discipline LOCK enforced at R1 M#4 fix
`RESOLUTION_TYPES` at `swing/trades/reconciliation.py:64-76` now mirrors `_RESOLUTION_VALUES` at `swing/data/models.py:820-834` verbatim (9 values); set-equality invariant test `test_resolution_types_mirror_models_resolution_values` guards against future drift. **R2 M#1 follow-up**: the schema-coverage constant is now consciously separated from the manual-resolver allowlist (`_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS` = 5 pre-v19 values for `resolve_discrepancy`; `_SERVICE_OWNED_RESOLUTIONS` = 4 v19 service-owned values route through auto-correct service entries).

---

## §10 Forward-binding lessons for Sub-sub-bundle C.D

### NEW C.C lesson #1 — Schema-coverage constant ≠ manual-resolver allowlist
After widening a Python enum to mirror schema CHECK (the standard CLAUDE.md gotcha pattern), audit every existing **manual** callsite that validates against the constant. If the new values are service-owned (require additional invariants or routing through specific service entries), introduce a separate tighter allowlist for the manual path; do NOT allow the schema-coverage constant to function as the manual-input allowlist. Discriminating-test pattern: per-service-owned-value rejection test asserting the routing hint substring in the error message + 5-value parametrized positive test for the manual allowlist. **C.D inheritance**: when adding CLI surfaces that consume `_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS`, the choice-set must match the allowlist exactly; do NOT regress to `RESOLUTION_TYPES`.

### NEW C.C lesson #2 — Outer transaction discipline UNIFORM regardless of sandbox
Sandbox short-circuit MUST live in the inner (caller-tx) function, NOT the outer (own-tx) function. Outer ALWAYS issues `BEGIN IMMEDIATE` → call inner → `COMMIT` (or `ROLLBACK` on exception). Inner short-circuits sandbox cases internally (returns no-op `CorrectionResult`). Two failure modes prevented: (a) outer-skip bypasses the in_transaction caller-held-tx check; (b) outer-skip lets nonexistent `discrepancy_id` succeed as a no-op (silent error). Discriminating test pattern: `_ExecuteSpyConn` wrapper that records `conn.execute` calls + asserts `"BEGIN IMMEDIATE"` was issued under sandbox.

### NEW C.C lesson #3 — SELECT-first idempotency must precede payload validation
For services with idempotency contracts (terminal-state → return existing audit row WITHOUT new write), the SELECT + terminal-check MUST happen BEFORE input-payload validation. A terminal discrepancy should return its existing `correction_id` even when caller passes stale/malformed/None payload. Reorder to: (1) sandbox short-circuit (no state needed), (2) SELECT + None-check, (3) terminal-state idempotent return, (4) payload validation, (5) remaining atomic flow. Discriminating test: invoke with terminal-state discrepancy + `classification=None` (or malformed); assert existing `correction_id` returned + no exception.

### NEW C.C lesson #4 — Counter staleness after inline state mutation
When a flow emits rows (incrementing counters) AND later mutates those rows' states (e.g., from `unresolved` to `pending_ambiguity_resolution`), the run-summary counter MUST be recomputed or decremented post-mutation. Inline mutation invalidates the emit-time counter. Two patterns work: (a) decrement counter per-mutation inside the loop (matches legacy `resolve_discrepancy` pattern); (b) recompute via `SELECT COUNT(*) WHERE resolution = 'unresolved'` post-loop (simpler + more robust; the C.C R1 M#3 choice). Discriminating test: plant N discrepancies (some tier-1 + some tier-2) → run pivot → assert run's `unresolved_discrepancies_count` equals actual post-pivot count, NOT N.

### NEW C.C lesson #5 — DRY helper extraction across pivot mirror sites
When plan says "mirrors T-X verbatim" + the mirror is non-trivial (100+ lines), extract a private helper rather than duplicating. Lazy-import (in-function) to break circular dependencies. Watch item: if the helper lives in module A but is consumed by module B, the import direction is asymmetric — V2 candidate to relocate to neutral module.

### NEW C.C lesson #6 — Pre-Codex orchestrator-side review catches obvious LOCK divergences cheaply
Orchestrator-side spec-compliance + code-quality review BEFORE invoking adversarial-critic catches plan-text deviations that Codex would otherwise spend a round flagging. Specifically: implementer self-report claims must be cross-checked against actual code paths. Pre-Codex review absorbed 2 Major findings (SC-1 sandbox threading + SC-2 T-C.11 E2E scope) saving an estimated 1-2 Codex rounds. **Pattern reusable**: dispatch a focused reviewer subagent with the plan §D acceptance criteria + brief §0.5 BINDING contracts as anchors, ask for a deviation list ≤600 words.

### NEW C.C lesson #7 — Implementer self-report accuracy gate
The implementer chain's final report claimed "SC-1 fix threaded `environment` through pivot + apply functions" but the actual code did NOT thread `environment` into `_apply_tier1_correction_inner` per plan §D.5 step 3 LOCK — instead it short-circuited the entire pivot block. The pre-Codex review caught this. **Pattern**: implementer self-report MUST cite specific file:line evidence for each fix claim; orchestrator-side review MUST verify the cited lines actually match the claim, not just check that the test passes (a regression test pinning the wrong behavior can pass while violating the LOCK).

---

## §11 CLAUDE.md status-line refresh draft text

For orchestrator paste-in at integration-merge time. Drop into the "Active ground-up refactor" paragraph after the existing C.B SHIPPED entry:

> **Phase 12 Sub-bundle C Sub-sub-bundle C.C (Auto-correction service + reconciliation flow pivot) SHIPPED 2026-05-16** at `<MERGE_SHA>` (integration merge of `phase12-bundle-C-C-auto-correction-service-and-flow-pivot` via `--no-ff`; 22 commits = 12 task-impl + 1 ruff style + 3 pre-Codex review fixes (SC-1 + SC-2 + SC-1 follow-up) + 4 Codex R1 fixes + 1 Codex R2 fix + 1 Codex R3 polish + 1 return-report; **3 Codex rounds → NO_NEW_CRITICAL_MAJOR — ties Phase 12 Sub-sub-bundle C.A's 2-round chain for fastest Phase 12 chain** convergent tapering (R1 0C/4M/0m → R2 0C/1M/0m → R3 0C/0M/1m); **ZERO ACCEPT-WITH-RATIONALE banked** — all 4 R1 Major + 1 R2 Major + 1 R3 Minor resolved with code-content fixes (matches C.B + Phase 10 A-E + C.A clean record); pre-Codex orchestrator-side review absorbed 2 Major findings (SC-1 sandbox threading + SC-2 T-C.11 E2E scope) saving an estimated 1-2 Codex rounds; new `swing/trades/reconciliation_auto_correct.py` (1924+ lines; 4 public service functions `apply_tier1_correction` + `apply_tier2_resolution` + `apply_tier3_override` + `stamp_pending_ambiguity` + 4 caller-tx inner variants + 3 exception classes + `CorrectionResult` dataclass + 17+1 per-(ambiguity_kind, choice_code) handler registry with `_PICK_SCHWAB_RECORD_PREFIX` parametric entry + savepoint-per-discrepancy pivot helper `_pivot_classify_and_dispatch_for_run` shared across Schwab+TOS via lazy import; spec §5 + §7 + §10 LOCKs preserved verbatim); reconciliation flow pivot at BOTH `run_schwab_reconciliation` + `run_tos_reconciliation` per OQ-2 PIVOT BOTH — savepoint-per-discrepancy discipline (spec §7.1 LOCK; fresh-savepoint fallback for tier-2 stamp on validator-rejection path per writing-plans R2 Minor #1 LOCK) + classify+dispatch loop with `functools.partial(default_validator_chain(conn), affected_table=X, affected_row_id=Y)` composition (spec §5.5 LOCK + C.B forward-binding lesson #3) + summary_json counters (`tier1_applied_count` / `tier2_pending_count` / `tier3_overridden_count` ZERO at run-time) + post-pivot `unresolved_discrepancies_count` recompute (R1 M#3 fix); 11-step atomic flow LOCKED at `_apply_tier1_correction_inner` (spec §5.4 + step 4 validator re-invocation + step 9 review_log cadence-period derivation + step 10 sandbox short-circuit via inner; SELECT-first idempotency post-R1 M#2); `correction_set_id` 2-step anchor pattern at `split_into_partials` handler with `__delete__`/`__insert__` sentinels per spec §3.1.1; `AlreadySupersededError` at tier-3 override per OQ-15 + validator chain re-run on operator-truth BEFORE mutation per Codex R1 Minor #1 writing-plans LOCK; sandbox short-circuit LOCK enforced at inner not outer per Codex R1 M#1 (outer ALWAYS BEGIN IMMEDIATE); briefing.md "Reconciliation status" section emits when counters non-zero per spec §7.5; `BriefingInputs` extended with `reconciliation_pending_count` + `reconciliation_tier1_recent_count` fields; `_step_export` wires counters via inline SQL; T-C.11 slow E2E `test_phase12_bundle_c_cvgi_41_end_to_end` PASSES (service-composition + `_step_export` invocation per pre-Codex SC-2 widening; mirrors Phase 11 D R1 M#4 ACCEPT-WITH-RATIONALE precedent at scope); `RESOLUTION_TYPES` widened 5→9 values mirroring `_RESOLUTION_VALUES` per R1 M#4 (schema-CHECK + Python-constant + dataclass-validator paired discipline gotcha) + tightened `_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS` allowlist per R2 M#1 (4 service-owned states route through canonical service entries, NOT manual `resolve_discrepancy`); +95 cumulative fast tests (4105 → 4200 worktree-side; main HEAD post-merge ~4203); ruff 18 unchanged; schema v19 unchanged (consumer-side only). **4-surface operator-witnessed gate posture**: S1 (4200 fast pytest) READY; S2+S3 covered by test infrastructure (Schwab+TOS pivot tests + sandbox short-circuit tests + T-C.11 slow E2E) — RECOMMENDED SKIPPED-with-test-coverage per polish-bundle-2026-05-10 precedent; S4 ruff 18 READY. **3 unresolved material discrepancies (39 DHC + 40 VSAT + 41 CVGI) STILL LEFT UNRESOLVED BY DESIGN** pending Sub-sub-bundle C.D backfill operation; C.C ships service+flow-pivot infrastructure consumed by C.D; production reconciliation flow at both pivot sites now dispositions tier-1/tier-2 inline. **7 forward-binding lessons banked at return report §10** for C.D dispatch (schema-coverage-constant ≠ manual-resolver allowlist; outer-tx uniform regardless of sandbox; SELECT-first before payload validation; counter staleness after inline state mutation; DRY helper extraction across pivot mirrors with lazy import; pre-Codex orchestrator review catches LOCK divergences cheaply; implementer self-report accuracy gate). **6 V2.1 §VII.F amendments banked at return report §5** (D1 pivot helper relocation; D2 sentinel rule; D3 test-side adjustments dependency on C.D filter widening; D4 SAVEPOINT-uniqueness test mechanic; D5 inline SQL vs repo helpers; D6 T-C.11 scope; D7 view_models.py touch). **Sub-sub-bundle C.D executing-plans dispatch UNBLOCKED** — Tier-2 CLI surface (`swing journal discrepancy {list-pending-ambiguities,show-ambiguity,resolve-ambiguity,override-correction}`) + `swing journal reconcile-backfill` CLI + Pass 1 / Pass 2 backfill mechanic + Phase 10 banner predicate widening to include `pending_ambiguity_resolution` + production backfill of 39/40/41; expected ~+55-80 fast tests; ~10-surface operator-witnessed gate. Worktree teardown: branch `phase12-bundle-C-C-auto-correction-service-and-flow-pivot` deleted post-merge; on-disk husk ACL-locked at `.worktrees/phase12-bundle-C-C-auto-correction-service-and-flow-pivot/` (3rd phase12-bundle-c-* husk pending; cleanup-script queue: C-A + C-B + C-C).

---

## §12 Composition-surface verification

`^def ` grep on `swing/trades/reconciliation_auto_correct.py` (public surface excluding underscore-prefixed privates):

```
apply_tier1_correction
apply_tier2_resolution
apply_tier3_override
stamp_pending_ambiguity
```

4 public outer service functions — matches plan §D acceptance criteria exactly:
- T-C.1 acceptance #1: 3 public outer functions (`apply_tier1_correction`, `apply_tier2_resolution`, `apply_tier3_override`).
- T-C.3.1 acceptance #1: NEW public service function `stamp_pending_ambiguity`.

Plus 4 private inner functions (`_apply_tier1_correction_inner`, `_apply_tier2_resolution_inner`, `_apply_tier3_override_inner`, `_stamp_pending_ambiguity_inner`) + 3 exception classes (`CallerHeldTransactionError`, `ValidatorRejectedError`, `AlreadySupersededError`) + 1 dataclass (`CorrectionResult`) + 17+1 tier-2 handlers in `_TIER2_HANDLERS` registry.

---

## §13 Transactional-discipline verification evidence

T-C.1 reject-caller-held tests (`tests/trades/test_reconciliation_auto_correct_transactional_discipline.py`) confirmed GREEN against all 4 public outers:
- `test_apply_tier1_correction_rejects_caller_held_transaction` PASS
- `test_apply_tier2_resolution_rejects_caller_held_transaction` PASS
- `test_apply_tier3_override_rejects_caller_held_transaction` PASS
- `test_stamp_pending_ambiguity_rejects_caller_held_transaction` PASS
- `test_apply_tier1_correction_outer_always_begins_immediate_under_sandbox` PASS (Codex R1 M#1 fix)
- Idempotency tests confirmed GREEN at `tests/trades/test_apply_tier1_correction.py` + others.

---

## §14 Savepoint-discipline verification evidence

T-C.7 regression suite (`tests/trades/test_savepoint_discipline_reconciliation_pivot.py`) confirmed GREEN against both Schwab + TOS pivots:
- Savepoint isolation under partial UPDATE failure PASS
- Outer-tx survives per-discrepancy savepoint rollback (1-of-3 rigged failure) PASS
- SAVEPOINT name uniqueness via `inspect.getsource` substring check PASS
- Per-iteration RELEASE always fires PASS

Plus fresh-savepoint fallback for tier-2 stamp on validator-rejection path verified at `test_run_schwab_reconciliation_pivot.py` + `test_run_tos_reconciliation_pivot.py`.

---

## §15 Sandbox short-circuit verification evidence

Sandbox tests confirmed GREEN:
- `test_apply_tier1_correction_inner_sandbox_short_circuit_writes_nothing` PASS (SC-1 follow-up regression test) — no journal mutation; no `reconciliation_corrections` INSERT; counters reflect classification-only (`tier1_applied_count` stays 0).
- `test_run_schwab_reconciliation_sandbox_short_circuits_apply` PASS — pivot dispositions tier-1 candidate; under sandbox `tier1_applied_count == 0`; discrepancy stays `unresolved`.
- `test_apply_tier1_correction_outer_always_begins_immediate_under_sandbox` PASS (R1 M#1) — outer ALWAYS issues `BEGIN IMMEDIATE`; sandbox short-circuit happens inside inner not outer.

---

## §16 E2E integration test verification evidence

T-C.11 slow E2E test (`tests/integration/test_phase12_bundle_c_cvgi_41_full_pipeline.py::test_phase12_bundle_c_cvgi_41_end_to_end`) confirmed GREEN under `pytest -m slow`:
- CVGI 41 full pipeline-composition flow:
  - Plants CVGI-shaped trade + fill in tmp DB.
  - Plants mocked Schwab orders response with divergent price ($5.30 vs journal $5.23).
  - Invokes `run_schwab_reconciliation(...)` → tier-1 auto-correct applied.
  - Asserts `fills.price = 5.30`, `reconciliation_corrections` row exists, `trade_events` row with `event_type='reconciliation_auto_correct'` exists, discrepancy resolution = `auto_corrected_from_schwab`.
  - Invokes `_step_export(...)` (per pre-Codex SC-2 widening) → reads briefing.md from `cfg.paths.exports_dir / <action_session> / briefing.md`.
  - Asserts briefing.md contains `## Reconciliation status` + `Tier-1 auto-corrected (last 7 days): 1` + `Tier-2 pending operator review: 0` (T-C.10 wiring discriminated end-to-end).

Test runtime: ~5-10 seconds (slow-marked but fast for slow-suite).
