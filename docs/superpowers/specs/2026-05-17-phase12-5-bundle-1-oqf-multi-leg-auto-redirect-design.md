# Phase 12.5 #1 — OQ-F Multi-Leg Tier-1 Auto-Redirect — Design

**Status:** Brainstorm spec. Inputs from operator-locked 2026-05-17 4-question batch (brief §1). Codex review pending.

**Substrate:** Post-Phase-12 mapper-widening arc closed 2026-05-17 (Sub-bundle 1 `120c992` + 1.5 `a7c1016` + 2 `690aed0`). V2 mapper now emits execution-grain `SchwabExecutionLeg[]` on real production data. Pass-1 entry/close_price_mismatch tier-1 auto-correct is V2-RESOLVED. Pass-2 unmatched_*_fill is V1 tier-2-always (Pass-2-tier-1-FORBIDDEN LOCK). **The remaining V2 follow-up is OQ-F: when a tier-2 `multi_partial_vs_consolidated` discrepancy carries multi-leg execution data that aligns within tolerance, classifier auto-redirects to a tier-1-shape auto-correct via the `split_into_partials` handler.**

**Brief:** `docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-brainstorm-dispatch-brief.md` (commit `37b584d`).

---

## §0 Glossary

- **Auto-redirect** — classifier+dispatcher decision: when the multi-leg predicate holds, finalize the discrepancy via a service mutation BYPASSING the operator menu, NO operator manual review.
- **Multi-leg execution data** — `SchwabOrderResponse.executions: list[SchwabExecutionLeg] | None` populated with `len >= 2` legs (Sub-bundle 1 T-1.1 dataclass).
- **VWAP alignment** — `sum(leg.price * leg.quantity) / sum(leg.quantity) ≈ journal price` within `price_tolerance=0.01`.
- **Per-leg consistency** — every individual leg's price is within `price_tolerance` of the order VWAP (single outlier flips to tier-2).
- **`price_tolerance`** — `$0.01` (LOCK; spec §4.4 determinism principle inheritance from Sub-bundle C.B; mirrors Shape A/B numeric guard discipline).
- **`split_into_partials` payload** — list of N partial-fill dicts each carrying `{qty, price, fill_datetime}` per Sub-bundle C plan §C.6 + `swing/trades/reconciliation_ambiguity_choices.py:_PARTIAL_PAYLOAD_SHAPE`.
- **`resolved_by` string** — free-TEXT column on `reconciliation_discrepancies` (NO schema CHECK). NEW value `'auto_tier1_multi_leg'` introduced this dispatch to distinguish auto-redirect from manual `split_into_partials` (`'operator'`) and from Pass-1 auto-correct (`'auto'`).
- **Banner advisory** — read-only badge on every base-layout-mounted page surfacing the count of multi-leg auto-corrections from the most-recent `reconciliation_run`. V1 LOCK: window = most-recent run; clears on next run. V2 window alternatives (7-day rolling / persists-until-acknowledged) banked at §14.
- **Flow-pivot loop** — `_pivot_classify_and_dispatch_for_run` in `swing/trades/schwab_reconciliation.py:418` (lazy-imported by `swing/trades/reconciliation.py:471` for the TOS reconciliation path); shared between Schwab + TOS reconciliation per Sub-bundle C.C; iterates discrepancies under SAVEPOINT-per-discrepancy discipline. (Codex R2 minor 2 — corrected from R1's stale `reconciliation_auto_correct.py` reference.)

---

## §1 Architecture overview

**One-paragraph thesis.** When a reconciliation comparator emits an `unmatched_open_fill` / `unmatched_close_fill` discrepancy whose matched Schwab order carries `>=2` `SchwabExecutionLeg[]` (or N>=2 candidate orders whose execution legs collectively meet the predicate) AND the legs collectively VWAP-align with the journal's consolidated fill price within `$0.01` AND every individual leg's price is within `$0.01` of the VWAP, the V1 manual `multi_partial_vs_consolidated` menu surface is BYPASSED: the classifier synthesizes the `split_into_partials` payload from the execution legs, the flow-pivot loop dispatches via `apply_tier2_resolution(conn, discrepancy_id=..., choice_code='split_into_partials', operator_custom_payload=synthesized, operator_reason=..., applied_by_override='auto', correction_action_override='auto_applied', resolved_by_override='auto_tier1_multi_leg', environment=..., ...)`, and the dashboard surfaces a banner advisory citing the auto-correction count for operator vigilance/trust-calibration. (Kwarg name per Codex R3 minor 2 LOCK — `operator_custom_payload`, not `payload`.)

**Architectural lift.** Pass-2 entry/close `_classify_unmatched_fill_shared` previously emitted ONLY `multi_partial_vs_consolidated` tier-2 (per spec §4.3.2/§4.3.3 + §8.4 Pass-2-tier-1-FORBIDDEN). Sub-bundle 1 widened the comparator to surface execution-grain data via Path B sentinel `execution_unavailable=true` when execution legs are absent — but tier-1 lift on multi-leg-PRESENT cases was deferred to V2 (spec §6.6 OQ-F V2). This dispatch ships that V2 lift.

**Boundary discipline.**

- **Classifier purity invariant** (CLAUDE.md gotcha "Classifier is a PURE function"): the classifier consumes pre-fetched payload + journal row; it does NOT call the auto-correct service, does NOT write the DB, does NOT manage transactions. The classifier RETURNS a `ClassificationResult` carrying a NEW optional field `auto_redirect_recipe: Mapping[str, Any] | None` (see §5.1). The flow-pivot loop reads the recipe and dispatches via the service layer.
- **Service-layer enforcement** (Sub-bundle C.C C.B forward-binding lesson #1): the auto-correct service re-validates the synthesized payload through `default_validator_chain` before mutation. The classifier's predicate is necessary but not sufficient.
- **`apply_tier2_resolution` reuse** (operator §1.3 LOCK): the flow-pivot loop invokes the existing tier-2 handler registry entry for `("multi_partial_vs_consolidated", "split_into_partials")` — minimum new code path. The handler does the DELETE+INSERT chain via `_handle_split_into_partials`. The auto-vs-manual distinction lives in:
  - `discrepancy.resolved_by = 'auto_tier1_multi_leg'` (NEW free-TEXT value; no schema CHECK). NOTE: the `_handle_split_into_partials` handler currently hardcodes `applied_by='operator'` + `correction_action='operator_resolved_ambiguity'` at `_build_tier2_correction` AND on every per-partial sub-correction row (Codex R1 M4 verified). T-1.4 parameterizes these as overrides that propagate through outer → inner → `_build_tier2_correction` → every `_handle_*` callsite (N+1 correction rows for split_into_partials inherit `applied_by='auto'` + `correction_action='auto_applied'` when overrides supplied).
  - `reconciliation_corrections.applied_by = 'auto'` (CHECK enum already permits — see §7.3 for handler parameterization).
  - `reconciliation_corrections.correction_action = 'auto_applied'` (CHECK enum already permits — see §7.3).
- **Banner advisory surface** (operator §1.4 LOCK): dashboard banner only; NO dedicated `/metrics/auto-redirects` review page; existing CLI surface `show-correction <id>` carries the per-row drill-down load. NEW CLI filter `swing journal discrepancy list --resolved-by <value>` (T-1.10) ships IN-BUNDLE — banner cites it verbatim — so the surface exists at ship time (LOCK per Codex R1 M5).

**Schema impact verdict.** Schema v19 UNCHANGED. Cross-column CHECK on `reconciliation_discrepancies` (resolution + ambiguity_kind pairing) is satisfied by the natural transition path described in §7.2. NO `0020_*.sql` migration this bundle. (See §13 for the full schema audit.)

---

## §2 Pre-locked operator decisions (BINDING; verbatim from brief §1)

### §2.1 Decision 1 — Auto-redirect posture: ON

When V2 mapper exposes multi-leg execution data AND the predicate (§4) holds, classifier auto-emits tier-1-shape auto-correct bypassing the operator menu. **DO NOT design alternatives.**

Rationale (LOCKED): same justification that makes Pass-1 tier-1 auto-correct safe (Sub-bundle 1 ship) makes multi-leg tier-1 auto-correct safe; multi-leg fills are uncommon (Sub-bundle 1.5 30-day production had zero) but WILL occur and the auto-redirect streamlines operator's daily flow; tier-3 `override-correction` provides reversibility per Sub-bundle C.C precedent.

### §2.2 Decision 2 — Confidence threshold: all-match-within-tolerance

Every execution leg's price must match within `price_tolerance=$0.01` of the order VWAP (per-leg consistency); journal price must match the VWAP within `price_tolerance`. Single outlier-leg flips classifier to tier-2 `multi_partial_vs_consolidated` operator menu. **DO NOT design majority-rule or strict-single alternatives.**

Rationale (LOCKED): spec §4.4 determinism principle; defensible + predictable; tier-2 is the safe fall-back.

### §2.3 Decision 3 — Auto-correct handler shape: reuse `apply_tier2_resolution(choice_code='split_into_partials')`

Classifier synthesizes the payload that an operator's manual `split_into_partials` choice would produce; flow-pivot loop invokes Sub-bundle C.C `apply_tier2_resolution(discrepancy_id, choice_code='split_into_partials', payload=synthesized, resolved_by='auto_tier1_multi_leg', ...)`. **DO NOT design dedicated new handler `apply_tier1_split_into_partials_auto`.**

Rationale (LOCKED): minimum new code; audit-trail forensic-honesty preserved (operator sees identical correction shape whether auto OR manual); architectural lesson — pure-function classifier + service-layer enforcement keeps the architecture clean.

**Brainstorm-locked sub-design** (§7 below):

- Emit-tier-2-state + flow-pivot-dispatches pattern (preserves classifier-is-pure invariant; brief §1.3 RECOMMENDED).
- Classifier output gains optional `auto_redirect_recipe` field on `ClassificationResult` (frozen dataclass; defaults to `None`).
- Flow-pivot loop branches on `auto_redirect_recipe is not None` BEFORE the default `stamp_pending_ambiguity` path.
- `apply_tier2_resolution` parameterized with `applied_by` + `correction_action` overrides (NO schema change; CHECK enums already permit both required values).

### §2.4 Decision 4 — Operator-facing UX: banner advisory only

Dashboard renders banner advisory when one or more multi-leg auto-corrections fire in a configurable window. **DO NOT design a dedicated `/metrics/auto-redirects` review page** (V2 candidate banked at §14).

Rationale (LOCKED): operator wants visibility (vigilance + trust calibration); banner is cheap per Phase 10 T-E.3 + Sub-bundle 2 base-layout VM banner pin precedent; drill-down via existing CLI + Phase 10 metrics dashboard.

**Brainstorm-locked sub-design** (§8 below):

- New `BaseLayoutVM` field `recent_multi_leg_auto_correction_count: int = 0` + helper `_fetch_recent_multi_leg_auto_correction_count(conn, window_predicate)`.
- Predicate window LOCKED V1: **most-recent reconciliation_run** (Option A; matches Phase 10 banner precedent; clears automatically on next run; simplest semantics). Banner clears semantics: clears when next reconciliation_run completes (Option A; per banner-clears-on-fresh-run lock). 7-day rolling + persists-until-acknowledged V2 candidates banked at §14.
- Template emits compact `<div class="reconciliation-auto-redirect-banner">N multi-leg auto-corrections in most recent reconciliation run. Review via <code>swing journal discrepancy list --resolved-by auto_tier1_multi_leg</code>.</div>` when count > 0. (NO non-ASCII glyphs in banner text per CLAUDE.md Windows cp1252 gotcha — see §8.3 + §16 lesson #7.)
- Banner does NOT supersede existing `unresolved_material_discrepancies_count` banner — both render side-by-side; semantically distinct.

---

## §3 Module touch list

Implementation surface is bounded by §2 operator-locks. **NO mapper or comparator touched** (Sub-bundle 1 + 1.5 + 2 shipped surfaces UNCHANGED).

| File | Change kind | Scope |
|---|---|---|
| `swing/trades/reconciliation_classifier.py` | **Modify**: extend `ClassificationResult` with `auto_redirect_recipe: Mapping[str, Any] \| None = None`; widen `_classify_unmatched_fill_shared` `n>=2` branch AND `n=1` branch (per §6.5 lock) to compute predicate (§4) + emit recipe when satisfied. The `n=1` branch reclassifies `ambiguity_kind` to `'multi_partial_vs_consolidated'` (NOT `unknown_schwab_subtype`) when `len(executions) >= 2` AND qty-aligns to journal — this satisfies the cross-column CHECK pairing + lets the existing tier-2 handler registry serve the auto-redirect path. | ~+90 LOC (predicate + helper + recipe synthesis + n=1 rerouting). |
| `swing/trades/reconciliation_auto_correct.py` | **Modify**: parameterize `apply_tier2_resolution` outer + `_apply_tier2_resolution_inner` + `_build_tier2_correction` + EVERY `_handle_*` helper signature (per Codex R1 M4 — all currently hardcode `applied_by='operator'` + `correction_action='operator_resolved_ambiguity'`; auto-redirect needs overrides to propagate through N+1 sub-correction rows for `_handle_split_into_partials`) with `applied_by_override: str \| None = None` + `correction_action_override: str \| None = None` + `resolved_by_override: str \| None = None`. Add sandbox short-circuit branch in `_apply_tier2_resolution_inner` gated on `applied_by_override == 'auto'` (per §7.6.1) with SAVEPOINT ROLLBACK-on-short-circuit so the discrepancy returns to `unresolved` rather than persisting `pending_ambiguity_resolution` (per Codex R1 M3). | ~+120 LOC (parameterization + sandbox + audit). |
| `swing/trades/schwab_reconciliation.py` | **Modify** (per Codex R1 M1 audit correction): `_pivot_classify_and_dispatch_for_run` LIVES HERE at line 418 (NOT in `reconciliation_auto_correct.py` — CLAUDE.md text was misleading; `reconciliation.py:471` lazy-imports). Extend the loop to recognize `classification.auto_redirect_recipe` + branch via `apply_tier2_resolution` with overrides. Also EXTEND comparator emit shape (Pass-2 candidate dicts at `unmatched_*_fill` emit site) to add `executions: list[dict] \| None` key — additive shape extension that the predicate sub-condition 1 consumes; legacy callsites with `executions` absent emit `multi_match_within_window` per pre-existing logic. The Sub-bundle 1+1.5 surfaces `_compute_execution_price` / `_resolve_match_quantity` / `_is_execution_bearing_candidate` / Path B sentinel emit remain UNCHANGED — the executions key extension is on the EMITTED CANDIDATE DICT, not those helpers. | ~+60 LOC (pivot-loop branching + comparator emit-shape extension). |
| `swing/cli.py` | **Modify** (per Codex R1 M5): add `--resolved-by <value>` filter to `swing journal discrepancy list`. Banner template (§8.3) cites it verbatim; the filter MUST ship in this bundle. | ~+15 LOC + 3 tests. |
| `swing/web/view_models/metrics/shared.py` | **Modify** `BaseLayoutVM`: add `recent_multi_leg_auto_correction_count: int = 0` field. | ~+1 LOC. |
| `swing/web/view_models/discrepancies.py` (or equivalent helper module) | **NEW** helper `_fetch_recent_multi_leg_auto_correction_count(conn, *, window: Literal['most_recent_run']='most_recent_run') -> int`. Reads `reconciliation_corrections JOIN reconciliation_discrepancies` filtered by `resolved_by='auto_tier1_multi_leg'` + `reconciliation_run_id == latest_completed_run_id`. | ~+30 LOC + tests. |
| `swing/web/view_models/dashboard.py` + `journal.py` + `pipeline.py` + `error.py` + `config.py` + `account.py` + `schwab.py` (SchwabSetupVM + SchwabStatusVM + SchwabSetupErrorVM) + `watchlist.py` + `trades.py` (ReviewVM + CadenceCompleteVM + ReviewsPendingVM + TradeDetailVM + others mounting base.html.j2) + `metrics/*.py` (all `BaseLayoutVM` subclasses) | **Modify**: every VM mounting `base.html.j2` populates the new field via the helper. Per CLAUDE.md gotcha — new `vm.foo` field requires adding to EVERY base-layout VM. | ~+1 LOC per VM × ≥13 VMs. |
| `swing/web/templates/base.html.j2` | **Modify**: render banner when `vm.recent_multi_leg_auto_correction_count > 0`. Single `{% if %}` block. | ~+5 LOC. |
| `tests/trades/test_reconciliation_classifier.py` | **NEW** tests for multi-leg predicate + auto_redirect_recipe synthesis (~5-10 discriminating cases per §10). | ~+150 LOC. |
| `tests/trades/test_reconciliation_auto_correct.py` | **NEW** tests for `apply_tier2_resolution` parameterized overrides + flow-pivot loop auto-redirect branch. | ~+100 LOC. |
| `tests/web/test_view_models_base_layout.py` | **NEW** tests for the helper + every retrofitted VM populates the field. | ~+50 LOC. |
| `tests/web/test_dashboard_banner.py` | **NEW** integration: plant a multi-leg auto-correction + assert banner fires; revert + assert banner clears. | ~+30 LOC. |

**Surfaces NOT touched** (consumer-side only):

- `swing/integrations/schwab/mappers.py` (mapper) — UNCHANGED.
- `swing/integrations/schwab/models.py` (`SchwabExecutionLeg` + `SchwabOrderResponse`) — UNCHANGED.
- Within `swing/trades/schwab_reconciliation.py` (which IS touched per Codex R1 M1): the helper functions `_compute_execution_price` + `_resolve_match_quantity` + `_is_execution_bearing_candidate` + the Path B `execution_unavailable=true` sentinel emit are UNCHANGED. The touched scope is narrowly (a) `_pivot_classify_and_dispatch_for_run` branching to recognize the recipe + (b) the comparator emit site that builds Pass-2 candidate dicts now adds `executions` key.
- `swing/web/routes/schwab.py` (`/schwab/status` + `/schwab/setup`) — UNCHANGED.
- `swing/data/migrations/0019_*.sql` (CHECK enums + cross-column CHECK) — UNCHANGED.
- `swing/trades/reconciliation_ambiguity_choices.py` (operator menu) — UNCHANGED (menu still surfaces for tier-2 cases where predicate fails).

---

## §4 Multi-leg auto-redirect predicate

### §4.1 Inputs

The predicate runs WITHIN `_classify_unmatched_fill_shared` (after the `n >= 2` branch establishes `len(source_payload) >= 2` for the Pass-2 list-shape). For Pass-1 inputs (`source_payload=None` or `{"matched": null}`), the predicate is N/A — there is no execution data to evaluate.

**Required inputs at classifier time** (pre-fetched by the comparator):

1. `source_payload: list[Mapping]` — N candidate Schwab orders. Each carries `order_id`, `quantity` (order-level), `price` (order-level limit/stop trigger; possibly `None` for MARKET). **NEW FOR PHASE 12.5 #1:** each candidate also carries `executions: list[Mapping] | None` (the execution-leg slice mapped from `SchwabExecutionLeg`) — see §4.2 below for the binding extension to the comparator's emit shape.
2. `journal_row: Mapping` — `{"price": consolidated_price, "quantity": consolidated_qty, "ticker": str, ...}` — already pre-fetched.

### §4.2 Comparator emit-shape extension (Sub-bundle 1 carry-forward)

Sub-bundle 1's comparator at `swing/trades/schwab_reconciliation.py` already invokes `_compute_execution_price(so)` and `_resolve_match_quantity(so)`. For `unmatched_*_fill` Pass-2 emit (where `source_payload` is the list of N candidates), the **comparator MUST extend each list element to carry `executions: list[dict] | None`** alongside the existing `order_id` + `quantity` + `price` keys.

**Binding contract:** each candidate dict in the Pass-2 list shall carry:
```
{
  "order_id": str,
  "quantity": float,            # order-level
  "price": float | None,        # order-level limit/stop
  "executions": [               # NEW; from SchwabExecutionLeg[]; None if absent
    {
      "leg_id": int,
      "price": float,           # execution-grain
      "quantity": float,        # execution-grain
      "time": str,              # ISO 8601
    }, ...
  ] | None,
}
```

This is the **ONLY** comparator-side change in Phase 12.5 #1. It's a structural shape extension (additive); pre-existing single-element-list shape compatibility preserved (legacy callers with `executions` absent still emit `multi_match_within_window` per existing logic — see §6.5).

**Codex review item:** is this extension in-scope or does it belong in a separate writing-plans dispatch? Brainstorm SHOULD lock as in-scope (the brief §4 binds "ZERO behavioral changes to non-touched existing surfaces — Sub-bundle 1+1.5+2 surfaces UNCHANGED"). The extension adds a new KEY to the existing emit shape but DOES NOT alter classification of existing N-element cases without execution data. See §11 for cascade analysis on existing tests.

### §4.3 Predicate (deterministic; no I/O; pure)

Pseudo-code (Python-equivalent):

```python
def _multi_leg_auto_redirect_predicate(
    *,
    candidates: list[Mapping],  # N >= 2 Schwab order candidates
    journal_qty: float,
    journal_price: float,
    price_tolerance: float = 0.01,
) -> tuple[bool, str | None]:
    """Returns (predicate_holds: bool, reject_reason: str | None).
    
    reject_reason is None when predicate_holds is True; otherwise carries
    a short human-readable rationale citing the failed sub-condition
    (used in classifier's correction_reason for forensic transparency).
    """
    
    # Sub-condition 1: ALL candidates carry execution data.
    all_executions: list[Mapping] = []
    for cand in candidates:
        execs = cand.get("executions")
        if not isinstance(execs, list) or len(execs) == 0:
            return (False, f"candidate order_id={cand.get('order_id')!r} has no execution legs")
        all_executions.extend(execs)
    
    if len(all_executions) < 2:
        # Defensive: N>=2 candidates each with >=1 leg means >=2 legs total.
        # If we end up here, something is off — drop to tier-2 manual menu.
        return (False, f"only {len(all_executions)} execution legs across {len(candidates)} candidates")
    
    # Sub-condition 2: total executed qty matches journal qty (within 1e-9).
    total_qty = sum(float(leg["quantity"]) for leg in all_executions)
    if abs(total_qty - journal_qty) > 1e-9:
        return (False, f"sum(executed qty)={total_qty} != journal qty={journal_qty}")
    
    # Sub-condition 3: every leg has positive finite price + quantity (defensive double-check
    # post-mapper __post_init__).
    for i, leg in enumerate(all_executions):
        p = leg.get("price")
        q = leg.get("quantity")
        if not isinstance(p, (int, float)) or isinstance(p, bool):
            return (False, f"leg #{i+1}: price not numeric ({type(p).__name__})")
        if not math.isfinite(float(p)) or p <= 0:
            return (False, f"leg #{i+1}: price not positive finite ({p!r})")
        if not isinstance(q, (int, float)) or isinstance(q, bool):
            return (False, f"leg #{i+1}: quantity not numeric ({type(q).__name__})")
        if not math.isfinite(float(q)) or q <= 0:
            return (False, f"leg #{i+1}: quantity not positive finite ({q!r})")
    
    # Sub-condition 4: compute VWAP across ALL legs (combined order set).
    vwap = sum(float(leg["price"]) * float(leg["quantity"]) for leg in all_executions) / total_qty
    
    # Sub-condition 5: journal price aligns with VWAP within price_tolerance.
    if abs(vwap - float(journal_price)) > price_tolerance:
        return (False, f"VWAP=${vwap:.4f} vs journal=${journal_price:.4f}; delta=${abs(vwap-journal_price):.4f} > tolerance=${price_tolerance}")
    
    # Sub-condition 6: every individual leg's price within price_tolerance of VWAP
    # (per-leg consistency check per §2.2 operator-lock).
    for i, leg in enumerate(all_executions):
        if abs(float(leg["price"]) - vwap) > price_tolerance:
            return (False, f"leg #{i+1} price=${float(leg['price']):.4f} outlier vs VWAP=${vwap:.4f}; delta=${abs(float(leg['price'])-vwap):.4f} > tolerance=${price_tolerance}")
    
    return (True, None)
```

### §4.4 Determinism + floating-point edge cases

**Determinism (spec §4.4 inheritance):** all numeric comparisons use stable Python `float` arithmetic with explicit `1e-9` epsilon for quantity-sum equality (matching `_handle_split_into_partials` line 1681 `qty_tolerance = 1e-6` — see Codex review item §15.4) and `$0.01` for price comparisons. Inputs are normalized: any `int` is `float()`-coerced; `bool` rejected (Python `bool` is subclass of `int`); NaN/inf rejected via `math.isfinite()`.

**Codex review item (§15.1):** the per-leg consistency check uses `abs(leg.price - VWAP) <= tolerance`. For N legs at near-identical prices the VWAP is approximately the leg price; OK. For pathological cases (e.g., N=3 with prices `[5.30, 5.30, 5.32]` qty `[100, 100, 100]` → VWAP=5.3067; delta to leg 3 = $0.0133 → outlier → tier-2). This is the operator-locked behavior per §2.2.

**Edge cases enumerated:**

- **Opposite-direction prices on legs** (impossible per `SchwabExecutionLeg.__post_init__` validator: `price > 0` LOCK). Sub-condition 3 defensively double-checks.
- **Zero-quantity legs** (impossible per dataclass validator: `quantity > 0` LOCK). Sub-condition 3 defensively double-checks.
- **`mismarked_quantity` field** — NOT consumed by predicate. It's informational on the dataclass; not threaded into the synthesized payload. (§6.3 confirms `split_into_partials` payload doesn't accept this field.)
- **Mismatched leg timestamps** — predicate does NOT compare timestamps to journal `fill_datetime`. Sub-bundle 1's comparator already validated the order matched the journal fill on (ticker, date, qty); the legs inherit that validation. Per-leg timestamps are PASSED THROUGH to the synthesized payload (§6.2) for audit.
- **N=2 vs N=20+ legs** — predicate handles arbitrarily many; no defensive cap V1. (§15.7 banks "defensive cap" as Codex review item.)
- **Mixed-status candidates** (e.g., one CANCELED + one FILLED summing to journal qty) — Sub-bundle 1.5 `_is_execution_bearing_candidate` already includes CANCELED-with-`filledQuantity>0` partials. Predicate consumes the result without re-checking status.

---

## §5 Classifier dispatch state design

### §5.1 `ClassificationResult` extension

`ClassificationResult` (frozen dataclass at `swing/trades/reconciliation_classifier.py:45`) gains ONE new optional field:

```python
@dataclass(frozen=True)
class ClassificationResult:
    tier: int
    ambiguity_kind: str | None
    correction_target: dict[str, Any] | None
    correction_reason: str
    candidate_choices: list[dict[str, Any]] | None = None
    # NEW IN PHASE 12.5 #1:
    auto_redirect_recipe: Mapping[str, Any] | None = None
```

**Contract:** `auto_redirect_recipe` is `None` for ALL existing classifier output shapes. ONLY the multi-leg auto-redirect path populates this field. When non-None, the recipe is a dict:

```
{
    "choice_code": "split_into_partials",          # binding: always this value V1
    "payload": [                                    # synthesized partial-fill list
        {"qty": float, "price": float, "fill_datetime": str},
        ...
    ],
    "resolved_by": "auto_tier1_multi_leg",          # binding: always this value V1
    "applied_by_override": "auto",                  # passed to apply_tier2_resolution
    "correction_action_override": "auto_applied",   # passed to apply_tier2_resolution
}
```

**Why a recipe dict rather than a typed dataclass?** V1 simplicity. The recipe carries DATA + PARAMETERS used by the flow-pivot loop's `apply_tier2_resolution` invocation. A typed dataclass would force coupling between the classifier module and the auto-correct service module's parameter set. The free-dict shape with explicit binding contract is brief §1.3-compliant ("minimum new code"). (§15.8 banks "promote recipe to dataclass" as V2 candidate if reuse patterns emerge.)

### §5.2 Tier emission shape

**LOCKED:** the classifier still emits `tier=2`, `ambiguity_kind='multi_partial_vs_consolidated'`, `correction_target=None`, `candidate_choices=<menu>` IDENTICALLY to current behavior. ONLY `auto_redirect_recipe` distinguishes the auto-redirect-eligible case.

**Rationale:** the classifier is a PURE function (CLAUDE.md gotcha). Emitting tier=1 with a multi-row payload would violate the classifier's tier-1-emits-single-field-correction_target contract (used by `_apply_tier1_correction_inner` which performs a single-column UPDATE). The multi-row DELETE+INSERT chain belongs in `_handle_split_into_partials`. The recipe field signals "tier-2 shape, but a default tier-2 stamp is INAPPROPRIATE — dispatch via the named handler instead."

**Discriminating analysis:** under what dispatcher state does the recipe NOT fire?
- Validator-respecting downgrade (`validator_chain` parameter; classifier dispatcher at lines 1539-1566): does NOT run on tier-2 emit. The recipe survives the dispatcher.
- Caller `validator_chain` is OPTIONAL; when None, no validation runs at classifier time. The recipe still emits.
- Flow-pivot loop reads the recipe, then RE-validates the synthesized payload via `default_validator_chain` BEFORE mutation (§7.4 below). This is the defense-in-depth re-invocation per C.B forward-binding lesson #2.

### §5.3 Why not emit tier=1 with ambiguity_kind=None?

Considered + rejected. Two problems:
1. **`_apply_tier1_correction_inner` calls `_handle_single_field_correction`** (single-column UPDATE). The multi-leg case needs DELETE + N INSERTs + `_recompute_aggregates`. Routing through tier-1 would require either (a) a new tier-1 multi-row handler (= brief §1.3 REJECTED "dedicated new handler `apply_tier1_split_into_partials_auto`") OR (b) parameterizing `apply_tier1_correction` to recognize a multi-row correction_target shape (more invasive than parameterizing `apply_tier2_resolution`).
2. **Audit-row attribution** — tier-1's resolution `'auto_corrected_from_schwab'` is paired with `ambiguity_kind IS NULL` per cross-column CHECK. The discrepancy emit-time ambiguity_kind was `'multi_partial_vs_consolidated'` (tier-2). Transitioning to `auto_corrected_from_schwab` requires explicitly NULLing ambiguity_kind, which loses the forensic shape of "this WAS a multi-partial ambiguity that we auto-resolved." Sticking with `operator_resolved_ambiguity` (tier-2's resolution) preserves the audit-trail shape "the system applied the operator-equivalent split_into_partials resolution."

### §5.4 Recipe synthesis call-site

Inside `_classify_unmatched_fill_shared`, immediately AFTER the existing `n >= 2 AND sum(qty) == journal_qty` branch (line 894 of classifier) emits the `multi_partial_vs_consolidated` ClassificationResult, the predicate (§4.3) runs:

```python
# ... existing emit block for multi_partial_vs_consolidated ...
predicate_holds, reject_reason = _multi_leg_auto_redirect_predicate(
    candidates=source_payload,
    journal_qty=journal_qty,
    journal_price=float(journal_row["price"]),  # required at multi_partial branch
)
recipe = (
    _synthesize_split_into_partials_recipe(source_payload)
    if predicate_holds else None
)
# correction_reason carries forensic transparency in BOTH cases:
correction_reason = (
    f"... (multi-leg auto-redirect: {'fires' if predicate_holds else f'declined ({reject_reason})'}) ..."
)
return ClassificationResult(
    tier=2,
    ambiguity_kind="multi_partial_vs_consolidated",
    correction_target=None,
    correction_reason=correction_reason,
    candidate_choices=_candidate_choices_multi_partial_vs_consolidated(),
    auto_redirect_recipe=recipe,
)
```

The reject_reason is INCLUDED in the correction_reason string for operator forensic transparency (so when the operator examines a multi-partial discrepancy that was NOT auto-redirected, the reason tells them why — e.g., "VWAP $5.31 vs journal $5.30; delta $0.01 OK but leg #3 outlier $5.34"). This is consistent with Sub-bundle C.B's correction_reason forensic discipline.

---

## §6 Payload synthesis design

### §6.1 Synthesis function shape

```python
def _synthesize_split_into_partials_recipe(
    candidates: list[Mapping],
) -> Mapping[str, Any]:
    """Build the auto_redirect_recipe payload from N Schwab candidates.
    
    PRE-CONDITION: caller has run _multi_leg_auto_redirect_predicate(...)
    and received (True, None). Function trusts inputs are validated.
    """
    all_legs: list[Mapping] = []
    for cand in candidates:
        all_legs.extend(cand["executions"])
    
    payload = [
        {
            "qty": float(leg["quantity"]),
            "price": float(leg["price"]),
            "fill_datetime": str(leg["time"]),  # ISO 8601 from SchwabExecutionLeg.time
        }
        for leg in all_legs
    ]
    
    return {
        "choice_code": "split_into_partials",
        "payload": payload,
        "resolved_by": "auto_tier1_multi_leg",
        "applied_by_override": "auto",
        "correction_action_override": "auto_applied",
    }
```

### §6.2 Per-leg → partial-fill mapping

| SchwabExecutionLeg field | partial-fill payload key | Notes |
|---|---|---|
| `leg.quantity` | `qty` | float; matches `_handle_split_into_partials` expectation |
| `leg.price` | `price` | float; matches expectation |
| `leg.time` | `fill_datetime` | ISO 8601 string (Sub-bundle 1 T-1.1 dataclass invariant `non-empty str`); `_handle_split_into_partials` parses as `str(item['fill_datetime'])`. |
| `leg.leg_id` | (not threaded) | informational; would balloon payload without journal-side consumer |
| `leg.instrument_id` | (not threaded) | informational; same |
| `leg.mismarked_quantity` | (not threaded) | informational; not a journal-side journal field |

### §6.3 Validator-chain compatibility

The synthesized payload passes through `_handle_split_into_partials`'s existing `parsed_partials` validation (lines 1607-1644):
- `qty` numeric + positive + finite ✓ (mapper `__post_init__` already ensured)
- `price` numeric + positive + finite ✓ (same)
- `fill_datetime` non-empty str ✓ (same)
- `partials_qty_sum` matches original journal fill `quantity` within `qty_tolerance=1e-6` ✓ (predicate sub-condition 2 ensured this with `1e-9` tolerance; STRICTER than `_handle_split_into_partials`'s `1e-6` — see §15.4).

**No new validator extension needed.** The validator-chain is a no-op for the multi-row tier-2 path because `_handle_split_into_partials` performs its OWN per-partial validation inline. The outer `default_validator_chain` is invoked at the flow-pivot dispatch (§7.4) but for the split_into_partials handler the chain is composed as a no-op (`split_into_partials` validation is intrinsic to the handler).

### §6.4 N=2 small case vs N=20+ large case

V1 imposes NO defensive cap. Sub-bundle 1 mapper-coherence-check ALREADY rejects malformed leg lists at construction time. The split_into_partials handler tolerates arbitrary N within reasonable memory bounds. Production observation: Sub-bundle 1.5 30-day sample had ZERO multi-leg fills; N=2-5 is the realistic operational range.

(§15.7 — Codex may surface defensive cap; brainstorm recommends no V1 cap based on production-data evidence.)

### §6.5 Single-order multi-leg case — `n=1` rerouting (LOCKED)

The classifier's existing `n=1` branch at line 862 emits `unknown_schwab_subtype` (Pass-2 single-match path). Sub-bundle 1.5 production data confirmed single-leg orders work cleanly through Pass-1 (Shape A/B classifier paths) WITHOUT entering Pass-2 (matching succeeded via journal price). The `n=1` branch is reached ONLY when Pass-1 found NO match (different ticker/date/qty) AND Pass-2 found exactly one candidate Schwab order in the match window.

**LOCKED per Codex R1 M2** (brainstorm-locked, no operator-decision-pending status — moved out of §15):

For `n=1` with execution data PRESENT (a single Schwab order with multi-leg fills summing to the journal qty), the classifier RECLASSIFIES the ambiguity_kind from `'unknown_schwab_subtype'` to `'multi_partial_vs_consolidated'` BEFORE emitting the result. This:

- Satisfies the cross-column CHECK pairing (resolution `operator_resolved_ambiguity` ↔ ambiguity_kind `multi_partial_vs_consolidated`).
- Routes the dispatch through the EXISTING `_TIER2_HANDLERS[("multi_partial_vs_consolidated", "split_into_partials")]` registry entry — NO new handler key needed (which would violate brief §1.3 LOCK).
- Preserves the predicate gating: the n=1 case is auto-redirected ONLY when `len(executions) >= 2` AND qty-aligns AND VWAP-aligns AND per-leg-consistency (same predicate as n>=2 case; §4.3 sub-conditions apply uniformly).
- Predicate failure on n=1 with multi-leg falls back to the existing `unknown_schwab_subtype` emit (preserves backward-compat for non-multi-leg n=1 cases).

**Discriminating regression test (T-1.1):** plant a single Schwab order with `len(executions)=3` summing to journal qty + VWAP aligned → assert `ambiguity_kind='multi_partial_vs_consolidated'` (NOT `unknown_schwab_subtype`) + `auto_redirect_recipe` present.

**Cross-references:** §10 Case A is the n=1 walkthrough — it exercises this rerouting. The brief §1.3 LOCK "DO NOT design dedicated new handler `apply_tier1_split_into_partials_auto`" is preserved (no new handler key; existing key reused via ambiguity_kind reclassification).

---

## §7 Auto-correct service integration

### §7.1 `apply_tier2_resolution` parameterization

The outer `apply_tier2_resolution` (currently line 210 in `swing/trades/reconciliation_auto_correct.py`) gains two optional parameters with default values matching current operator-path behavior:

```python
# Codex R3 M1 LOCK — preserve the existing positional-conn signature ordering;
# the current shipped code (reconciliation_auto_correct.py:210) takes
# `conn` as the first positional arg, followed by keyword-only parameters.
def apply_tier2_resolution(
    conn: sqlite3.Connection,
    *,
    discrepancy_id: int,
    choice_code: str,
    operator_custom_payload: Any = None,
    operator_reason: str,
    risk_policy_id: int | None = None,
    schwab_api_call_id: int | None = None,
    environment: str = "production",
    # NEW IN PHASE 12.5 #1:
    applied_by_override: str | None = None,           # 'auto' for auto-redirect; None means manual operator path
    correction_action_override: str | None = None,    # 'auto_applied' for auto-redirect; None means 'operator_resolved_ambiguity' default
    resolved_by_override: str | None = None,          # 'auto_tier1_multi_leg' for auto-redirect; None means 'operator' default
) -> CorrectionResult:
    ...
```

The inner `_apply_tier2_resolution_inner` + `_build_tier2_correction` + every `_handle_*` helper threads these overrides through with the same positional-conn ordering. Default callers (the existing CLI `resolve-ambiguity` path) pass None and get verbatim existing behavior.

### §7.2 Discrepancy state transition

Auto-redirect requires the discrepancy be in `resolution='pending_ambiguity_resolution'` BEFORE `apply_tier2_resolution` runs (per existing guard at `_apply_tier2_resolution_inner` line 568). The flow-pivot loop's auto-redirect branch performs a 2-step in a SAVEPOINT:

1. `_stamp_pending_ambiguity_inner(conn, discrepancy_id, ambiguity_kind='multi_partial_vs_consolidated', ...)` — transitions to `pending_ambiguity_resolution`. This is the SAME path as the operator menu would trigger.
2. `_apply_tier2_resolution_inner(conn, discrepancy_id=..., choice_code='split_into_partials', operator_custom_payload=recipe['payload'], operator_reason='multi-leg auto-redirect: ...', applied_by_override='auto', correction_action_override='auto_applied', resolved_by_override='auto_tier1_multi_leg', environment=environment, ...)` — finalizes the journal mutation. (Codex R3 minor 2 LOCK — kwarg is `operator_custom_payload`, not `payload`.)

Final state:
- `discrepancy.resolution = 'operator_resolved_ambiguity'` (per existing handler discipline)
- `discrepancy.ambiguity_kind = 'multi_partial_vs_consolidated'` (cross-column CHECK satisfied)
- `discrepancy.resolved_by = 'auto_tier1_multi_leg'` (NEW string; free-TEXT column; no CHECK)
- `correction_action = 'auto_applied'` (override; CHECK enum already permits)
- `applied_by = 'auto'` (override; CHECK enum already permits)
- New `correction_set_id` anchoring the DELETE-anchor + N INSERT-sentinel rows per `_handle_split_into_partials` discipline.

### §7.3 Cross-column CHECK + corrections-CHECK invariant audit

**Schema `reconciliation_discrepancies` cross-CHECK** (migration 0019 lines 135-147):
```
(ambiguity_kind IS NULL AND resolution NOT IN ('pending_ambiguity_resolution', 'operator_resolved_ambiguity'))
OR
(ambiguity_kind IS NOT NULL AND resolution IN ('pending_ambiguity_resolution', 'operator_resolved_ambiguity'))
```

Final state has `ambiguity_kind = 'multi_partial_vs_consolidated'` (NOT NULL) + `resolution = 'operator_resolved_ambiguity'` (in pair). **CHECK satisfied.** ✓

**Schema `reconciliation_corrections` CHECKs:**
- `correction_action IN ('auto_applied', 'operator_resolved_ambiguity', 'operator_overridden')`. Override value `'auto_applied'` is in the enum. ✓
- `applied_by IN ('auto', 'operator')`. Override value `'auto'` is in the enum. ✓

**ZERO schema modifications required.**

### §7.3.1 Service-layer hybrid-row invariant (Codex R3 M2 LOCK)

The combination `correction_action='auto_applied'` + `applied_by='auto'` + `correction_choice='split_into_partials'` is a NEW row shape that did not exist pre-Phase-12.5 #1. Pre-existing assumptions in `reconciliation_auto_correct.py` + tests:

- Tier-1 auto-correct path (Pass-1 auto-redirect for `entry_price_mismatch` / `close_price_mismatch`) wrote `correction_action='auto_applied'` + `applied_by='auto'` + `correction_choice IS NULL` (single-field update; no menu choice involved).
- Tier-2 operator-driven path wrote `correction_action='operator_resolved_ambiguity'` + `applied_by='operator'` + `correction_choice` set to one of the §6.2.1 menu choices.

Phase 12.5 #1 introduces a HYBRID shape: `correction_action='auto_applied'` (auto) + `applied_by='auto'` + `correction_choice='split_into_partials'` (was previously only a manual operator choice).

**BINDING invariant (LOCKED):** the hybrid shape is valid IF AND ONLY IF the parent `reconciliation_discrepancies.resolved_by = 'auto_tier1_multi_leg'`. Any other `resolved_by` value paired with this hybrid shape signals a service-layer bug (e.g., misuse of the override parameters via direct CLI invocation). Writing-plans phase MUST:

- Add a discriminating regression test asserting the hybrid shape is rejected at service-layer when invoked WITHOUT the auto-redirect path (e.g., operator CLI passing `--correction-action-override auto_applied --applied-by-override auto`). The CLI surface MUST NOT expose these override parameters; they are service-layer-internal kwargs.
- Update any pre-existing test or comment that asserts "auto_applied implies correction_choice IS NULL" → narrow the assertion to "auto_applied with correction_choice IS NULL implies a tier-1 entry/close_price_mismatch correction" + add the hybrid case as a separate assertion family.
- Document the invariant in `reconciliation_auto_correct.py` module-level docstring + at `_TIER2_HANDLERS` registry comment.

**§7.3.1.a Guard placement (Codex R4 M1 LOCK — shared helper called by BOTH outer + inner):**

The override-combo invariant guard MUST live in a shared helper called at the TOP of `_apply_tier2_resolution_inner` (before any state mutation) so the pivot-loop's direct call to the inner is gated. The outer `apply_tier2_resolution` already calls the inner inside its `with conn:` envelope, so it inherits the same guard via composition. Implementation:

```python
class InvalidOverrideComboError(ValueError):
    """Auto-redirect override kwargs are internally inconsistent.

    Raised when override kwarg combinations imply the hybrid auto-tier-1
    row shape but the resolved_by override is not 'auto_tier1_multi_leg'.
    This is a service-layer / developer-bug signal — NOT a data
    classification fall-back. The pivot loop SHOULD NOT catch this; let
    it propagate so the run fails fast with an explicit attribution.
    """


def _validate_override_combo(
    *,
    applied_by_override: str | None,
    correction_action_override: str | None,
    resolved_by_override: str | None,
) -> None:
    auto_like = (
        applied_by_override == "auto"
        or correction_action_override == "auto_applied"
    )
    if auto_like and resolved_by_override != "auto_tier1_multi_leg":
        raise InvalidOverrideComboError(
            f"hybrid auto-tier-1 row shape requires "
            f"resolved_by_override='auto_tier1_multi_leg'; got "
            f"applied_by_override={applied_by_override!r}, "
            f"correction_action_override={correction_action_override!r}, "
            f"resolved_by_override={resolved_by_override!r}"
        )
    # Symmetry: resolved_by_override='auto_tier1_multi_leg' implies the
    # other two MUST be set to the auto-redirect values.
    if (
        resolved_by_override == "auto_tier1_multi_leg"
        and (applied_by_override != "auto" or correction_action_override != "auto_applied")
    ):
        raise InvalidOverrideComboError(
            f"resolved_by_override='auto_tier1_multi_leg' requires "
            f"applied_by_override='auto' AND "
            f"correction_action_override='auto_applied'; got "
            f"applied_by_override={applied_by_override!r}, "
            f"correction_action_override={correction_action_override!r}"
        )


def _apply_tier2_resolution_inner(conn, *, ...):
    # Codex R4 M1 LOCK — guard fires inside the inner (shared by all
    # callers; outer + pivot-loop direct).
    _validate_override_combo(
        applied_by_override=applied_by_override,
        correction_action_override=correction_action_override,
        resolved_by_override=resolved_by_override,
    )
    # ... continue with SELECT-first idempotency + sandbox short-circuit
    # + handler dispatch ...
```

**Discriminating regression test pattern (T-1.4):**
- Test A: invoke `apply_tier2_resolution(conn, discrepancy_id=X, choice_code='split_into_partials', applied_by_override='auto', correction_action_override='auto_applied', resolved_by_override='auto_tier1_multi_leg', ...)` against a `pending_ambiguity_resolution` discrepancy → assert N+1 correction rows ALL carry the hybrid shape + parent discrepancy.resolved_by='auto_tier1_multi_leg'.
- Test B: invoke same with ALL three overrides OMITTED (legacy default; per signature defaults of `None` per Codex R4 minor 1 fix) → assert N+1 rows carry the legacy operator shape; resolved_by='operator'. No hybrid.
- Test C: invoke same with `applied_by_override='auto'` BUT `resolved_by_override='operator'` (mismatched intent) → service-layer raises `InvalidOverrideComboError` (subclass of `ValueError`). The pivot loop MUST NOT catch this specific exception; the run fails-fast.
- Test D: invoke with `resolved_by_override='auto_tier1_multi_leg'` BUT `applied_by_override` omitted (None) → service-layer raises `InvalidOverrideComboError` (symmetric guard).
- Test E (pivot-loop test): plant a synthetic recipe with mismatched override values → assert the pivot loop's `except ValueError` clause re-raises `InvalidOverrideComboError` (does NOT downgrade to manual tier-2 stamp; the run fails-fast).

### §7.4 Flow-pivot loop branching

`_pivot_classify_and_dispatch_for_run` (lives at `swing/trades/schwab_reconciliation.py:418`; lazy-imported by `swing/trades/reconciliation.py:471` for the TOS path — Codex R1 M1 + R2 minor 2 audit) is extended:

```python
def _pivot_classify_and_dispatch_for_run(conn, run_id, environment, ...):
    for disc in fetch_discrepancies_for_run(conn, run_id):
        with savepoint(f"correction_sp_{disc.discrepancy_id}"):
            try:
                source_payload, journal_row = _fetch_for_classifier(disc, ...)
                classification = classify_discrepancy(
                    disc,
                    source_payload=source_payload,
                    journal_row=journal_row,
                    validator_chain=functools.partial(
                        default_validator_chain(conn),
                        affected_table=disc.affected_table,
                        affected_row_id=disc.affected_row_id,
                    ),
                )
                
                if classification.tier == 1:
                    # Existing Pass-1 tier-1 auto-correct path; UNCHANGED.
                    _apply_tier1_correction_inner(conn, discrepancy_id=disc.discrepancy_id, ...)
                    counters["tier1_applied_count"] += 1
                
                elif classification.tier == 2 and classification.auto_redirect_recipe is not None:
                    # NEW IN PHASE 12.5 #1: multi-leg auto-redirect path.
                    recipe = classification.auto_redirect_recipe
                    
                    # Step 1: stamp pending_ambiguity_resolution.
                    # Codex R2 minor 1 — _stamp_pending_ambiguity_inner does
                    # NOT accept candidate_choices (current signature is
                    # discrepancy_id + ambiguity_kind + resolution_reason +
                    # allow_pending_update). Remove the stale kwarg.
                    _stamp_pending_ambiguity_inner(
                        conn,
                        discrepancy_id=disc.discrepancy_id,
                        ambiguity_kind=classification.ambiguity_kind,
                        resolution_reason=classification.correction_reason,
                    )
                    
                    # Step 2: dispatch via apply_tier2_resolution with overrides.
                    # NOTE: defense-in-depth validator re-invocation happens INSIDE
                    # _handle_split_into_partials (intrinsic validation per §6.3).
                    _apply_tier2_resolution_inner(
                        conn,
                        discrepancy_id=disc.discrepancy_id,
                        choice_code=recipe["choice_code"],
                        operator_custom_payload=recipe["payload"],
                        operator_reason=f"multi-leg auto-redirect: {classification.correction_reason}",
                        applied_by_override=recipe["applied_by_override"],
                        correction_action_override=recipe["correction_action_override"],
                        resolved_by_override=recipe["resolved_by"],
                        risk_policy_id=...,
                        schwab_api_call_id=...,
                    )
                    counters["tier1_multi_leg_auto_redirected_count"] += 1  # NEW counter
                
                elif classification.tier == 2:
                    # Existing tier-2 path: stamp pending_ambiguity_resolution for operator review.
                    _stamp_pending_ambiguity_inner(conn, ...)
                    counters["tier2_pending_count"] += 1
            
            except InvalidOverrideComboError:
                # Codex R4 M2 LOCK — developer-bug signal; DO NOT downgrade
                # to manual tier-2 stamp. Re-raise so the run fails-fast and
                # the integration merge cannot proceed without the bug being
                # surfaced + fixed in writing-plans / executing-plans.
                raise
            except (ValidatorRejectedError, ValueError) as e:
                # Data-rejection / validator-rejection fall-back per §7.5.
                # ValueError here is the GENERIC catch — distinct from
                # InvalidOverrideComboError (subclass of ValueError) which
                # was caught above by exception specificity ordering.
                _stamp_pending_ambiguity_inner(conn, ...)
                counters["tier2_pending_count"] += 1
                logger.warning(
                    "multi-leg auto-redirect declined for discrepancy_id=%s: %s",
                    disc.discrepancy_id, e,
                )
```

### §7.5 Fallback on validator failure or handler exception

If `_apply_tier2_resolution_inner` raises (e.g., validator rejection on edge case the predicate missed; `_handle_split_into_partials` raises due to bad data shape), the SAVEPOINT rolls back the auto-redirect partial state. The except clause RE-RUNS just the stamp step (in a fresh savepoint) leaving the discrepancy in `pending_ambiguity_resolution` for operator manual review. This mirrors C.C's R2 Minor #1 LOCK (fresh-savepoint fallback for tier-2 stamp on validator-rejection path).

**Discriminating test (§12):** plant a multi-leg case where the synthesized payload's `qty` sums correctly per predicate but `_handle_split_into_partials`'s intrinsic validator rejects (e.g., zero `qty_tolerance` violation); assert discrepancy is in `pending_ambiguity_resolution` post-pivot + counter is `tier2_pending_count` not `tier1_multi_leg_auto_redirected_count`.

### §7.6 Sandbox short-circuit inheritance

Per CLAUDE.md gotcha + C.C lesson #2: sandbox short-circuit MUST live in the inner (caller-tx) function, NOT outer. The existing `_apply_tier2_resolution_inner` does NOT currently sandbox-short-circuit (only `_apply_tier1_correction_inner` does — per the existing tier-1-only-domain-write story). For Phase 12.5 #1's auto-redirect path, sandbox short-circuit IS REQUIRED because the auto-redirect DOES write journal rows in production.

**§7.6.1 LOCKED pattern (Codex R1 M3 + R2 M2 fix — SAVEPOINT ROLLBACK discipline + explicit `environment` threading):**

Add sandbox short-circuit to `_apply_tier2_resolution_inner` GATED ON `applied_by_override == 'auto'` (auto-redirect path only; manual operator path proceeds — operators on sandbox can still test the manual menu). The short-circuit pattern preserves the discrepancy's pre-pivot state via SAVEPOINT ROLLBACK.

**Codex R2 M2 LOCK — `environment` threading:** the existing `_apply_tier2_resolution_inner` signature does NOT carry `environment`. T-1.4 + T-1.6 EXPLICITLY add `environment: str = 'production'` to the inner signature AND thread it from both (a) the public outer `apply_tier2_resolution` (which already accepts `environment`) AND (b) the pivot-loop callers at `_pivot_classify_and_dispatch_for_run` (currently in `schwab_reconciliation.py:418`). The pivot loop reads `environment` from its own caller-supplied parameter — schwab_reconciliation already passes environment through the run.

```python
def _apply_tier2_resolution_inner(
    conn,
    *,
    discrepancy_id,
    choice_code,
    operator_custom_payload=None,
    operator_reason,
    risk_policy_id=None,
    schwab_api_call_id=None,
    # NEW IN PHASE 12.5 #1:
    applied_by_override=None,
    correction_action_override=None,
    resolved_by_override=None,
    environment="production",          # NEW; explicit kwarg per Codex R2 M2
):
    # SELECT discrepancy first (per Sub-bundle C.C lesson #3 SELECT-first idempotency)
    disc = _select_discrepancy(conn, discrepancy_id)
    
    # NEW: sandbox short-circuit gated on auto-redirect path.
    if applied_by_override == "auto" and environment == "sandbox":
        # Caller MUST roll back the savepoint to undo the prior
        # _stamp_pending_ambiguity_inner mutation. Raise the typed
        # exception; the pivot-loop SAVEPOINT ROLLBACK contract (per
        # §7.5) handles the actual rollback.
        logger.warning(
            "auto-redirect short-circuit under sandbox for discrepancy_id=%s "
            "(applied_by_override='auto'); SAVEPOINT will be rolled back",
            discrepancy_id,
        )
        raise _SandboxAutoRedirectShortCircuit(discrepancy_id)
    
    # ... existing flow ...
```

**Pivot-loop call-site update (T-1.5 LOCKED):**

```python
# Inside _pivot_classify_and_dispatch_for_run(conn, ..., environment, ...):
_apply_tier2_resolution_inner(
    conn,
    discrepancy_id=disc.discrepancy_id,
    choice_code=recipe["choice_code"],
    operator_custom_payload=recipe["payload"],
    operator_reason=f"multi-leg auto-redirect: {classification.correction_reason}",
    applied_by_override=recipe["applied_by_override"],
    correction_action_override=recipe["correction_action_override"],
    resolved_by_override=recipe["resolved_by"],
    risk_policy_id=...,
    schwab_api_call_id=...,
    environment=environment,           # Codex R2 M2 — thread explicitly
)
```

**Discriminating test pattern (Case J)** — must instantiate `_apply_tier2_resolution_inner` (NOT the outer `apply_tier2_resolution`) inside a caller-tx context with `environment='sandbox'` + `applied_by_override='auto'` + assert the typed exception is raised. The outer `apply_tier2_resolution` is exercised by separate manual-tier-2 sandbox tests verifying the manual path is NOT short-circuited.

**Pivot-loop branch handling** (§7.4 extension):

```python
try:
    with savepoint(f"correction_sp_{disc.discrepancy_id}"):
        _stamp_pending_ambiguity_inner(conn, ...)
        _apply_tier2_resolution_inner(conn, ..., applied_by_override='auto')
        counters["tier1_multi_leg_auto_redirected_count"] += 1
except _SandboxAutoRedirectShortCircuit:
    # SAVEPOINT rolled back; discrepancy returns to 'unresolved'.
    # NO counter increment + NO banner trigger (banner queries
    # reconciliation_corrections WHERE reconciliation_run_id = latest;
    # nothing was written).
    counters["sandbox_auto_redirect_skipped_count"] += 1  # NEW counter
    logger.warning("sandbox auto-redirect skipped for discrepancy_id=%s", disc.discrepancy_id)
```

**Updated Case J expectations** (§10):
- Discrepancy resolution AFTER the pivot: `'unresolved'` (NOT `'pending_ambiguity_resolution'`; the SAVEPOINT rolled back the stamp).
- `reconciliation_corrections` rows for this discrepancy: ZERO.
- Banner count for the run: ZERO.
- `counters["sandbox_auto_redirect_skipped_count"]` for the run: 1.

**Why use exception + SAVEPOINT ROLLBACK rather than early-return** (alternative considered):

Early-return from `_apply_tier2_resolution_inner` would leave the `_stamp_pending_ambiguity_inner` stamp committed (per the SAVEPOINT release on successful function return). The exception path is the cleanest pattern to ROLLBACK the savepoint atomically. Codex R1 M3 LOCK.

**Alternative considered + rejected** (short-circuit ALL tier-2 in sandbox): would prevent operator sandbox testing of the manual menu surface; brainstorm prefers the gated approach.

---

## §8 Banner advisory design

### §8.1 `BaseLayoutVM` field

In `swing/web/view_models/metrics/shared.py:28` (`BaseLayoutVM`), add:

```python
@dataclass
class BaseLayoutVM:
    # ... existing fields ...
    recent_multi_leg_auto_correction_count: int = 0
```

Per CLAUDE.md gotcha "base.html.j2 is shared": every base-layout VM gets the new field via inheritance (when VM extends `BaseLayoutVM`) OR explicit retrofit (when VM does NOT subclass — see §3 module touch list for the ≥13 VMs).

### §8.2 Predicate window LOCK + helper

```python
def _fetch_recent_multi_leg_auto_correction_count(
    conn: sqlite3.Connection,
    *,
    window: Literal["most_recent_run"] = "most_recent_run",
) -> int:
    """Return count of multi-leg auto-corrections in the most-recent completed
    reconciliation_run. Returns 0 when no completed run exists.
    
    Window: 'most_recent_run' (V1 LOCK; clears when next run completes).
    V2 candidates: 'rolling_7_day', 'since_last_acknowledged' (banked §14).
    """
    row = conn.execute(
        "SELECT run_id FROM reconciliation_runs "
        "WHERE state = 'completed' "
        "ORDER BY finished_ts DESC, run_id DESC LIMIT 1"
    ).fetchone()
    if row is None:
        return 0
    latest_run_id = row[0]
    
    # Codex R2 M1 fix: use COUNT(DISTINCT rd.discrepancy_id) because
    # _handle_split_into_partials writes N+1 correction rows per logical
    # auto-redirect (1 deletion-anchor + N partial-insertion rows). A
    # naive COUNT(*) would inflate the banner count and similarly inflate
    # any briefing.md / metrics consumers that aggregate "auto-correction
    # count" semantics. The banner counts LOGICAL corrections (one per
    # discrepancy), not correction ROWS.
    count_row = conn.execute(
        "SELECT COUNT(DISTINCT rd.discrepancy_id) "
        "FROM reconciliation_corrections rc "
        "JOIN reconciliation_discrepancies rd "
        "ON rc.discrepancy_id = rd.discrepancy_id "
        "WHERE rc.reconciliation_run_id = ? "
        "AND rd.resolved_by = ?",
        (latest_run_id, "auto_tier1_multi_leg"),
    ).fetchone()
    return int(count_row[0]) if count_row else 0
```

**Deterministic tiebreaker** (`run_id DESC`) per Phase 10 lesson #26.

### §8.3 Template render

In `swing/web/templates/base.html.j2`, immediately AFTER the existing unresolved-material-discrepancies banner block:

```jinja
{% if vm.recent_multi_leg_auto_correction_count > 0 %}
  <div class="reconciliation-auto-redirect-banner" data-banner-count="{{ vm.recent_multi_leg_auto_correction_count }}">
    {{ vm.recent_multi_leg_auto_correction_count }} multi-leg auto-correction{{ 's' if vm.recent_multi_leg_auto_correction_count != 1 else '' }} in most recent reconciliation run. Review via <code>swing journal discrepancy list --resolved-by auto_tier1_multi_leg</code>.
  </div>
{% endif %}
```

**No emoji + no non-ASCII glyphs** per CLAUDE.md Windows-cp1252-stdout gotcha (banner text flows through curl/grep gate verification — keep ASCII-safe). The `data-banner-count` CSS attribute is the discriminating test marker.

### §8.4 Banner-clears semantics

V1 LOCK: clears when next reconciliation_run completes (Option A from brief §1.4). When the next pipeline run fires `_pivot_classify_and_dispatch_for_run` against a fresh run, the helper now queries against the new `latest_run_id` — auto-redirects on the previous run no longer count. Banner auto-clears.

**This is by-design + intentional.** Operator vigilance is over the MOST RECENT run; older auto-corrections are still queryable via CLI but don't carry the banner.

(§14 banks V2 alternatives.)

### §8.5 Sentinel-leak audit

The banner template reads from `reconciliation_corrections` and `reconciliation_discrepancies` — both already gate `error_message` and `expected_value_json` content through Sub-bundle 2's read-time re-redactor discipline (per CLAUDE.md "Read-time re-redactor" gotcha banked). The auto-redirect counter is a scalar aggregate (`COUNT(DISTINCT discrepancy_id)` per §8.2 — Codex R3 minor 1 LOCK) — no string content surfaces. ZERO sensitive data emission risk. Sentinel-leak audit test: `tests/web/test_dashboard_banner.py` plants a known sentinel substring in a correction row's `correction_reason` + asserts the banner does NOT contain the substring (only the count).

### §8.6 CLI surface availability — LOCKED IN-BUNDLE per Codex R1 M5

The banner template cites `swing journal discrepancy list --resolved-by auto_tier1_multi_leg`. This filter DOES NOT currently exist on the `discrepancy list` subcommand (verified via grep). **LOCKED IN-BUNDLE:** T-1.10 lands the `--resolved-by <value>` filter on `swing/cli.py` in this bundle. The banner template will NEVER ship before the CLI filter — both ride the same integration merge.

Implementation (T-1.10): add `--resolved-by <value>` click option to the existing `discrepancy list` subcommand; threads through to `list_discrepancies` (Phase 9 Sub-bundle B repo helper) as an additional WHERE-clause; ~+15 LOC + 3 tests (filter matches, filter no-match, filter combined with --material).

No schema impact (column `resolved_by` already exists; free TEXT; no CHECK). No additional repo helper needed (existing helper accepts a WHERE clause). Composable with existing `--resolved` / `--unresolved` / `--material` filters.

---

## §9 Sub-bundle decomposition

### §9.1 Recommendation: single sub-bundle (Phase 12.5 #1, no internal split)

The scope is bounded:
- ~+220 LOC across 2 production files (classifier + auto-correct service) + ~+50 LOC across ≥13 VMs (1 line each) + ~+30 LOC helper + ~+5 LOC template + ~+15 LOC CLI filter.
- ~+50-80 fast tests (predicate matrix + payload synthesis + handler parameterization + flow-pivot branching + banner integration + CLI filter).
- 3-4 Codex rounds expected (matches Sub-bundle 1.5 + 2 chain shapes).
- ZERO schema changes (per §13 audit).
- 4-5 operator-witnessed gate surfaces (per §9.3).

Internal split would impose cross-bundle pin discipline (per Sub-bundle A → E precedent) WITHOUT meaningful test-isolation benefit. Skip the split.

### §9.2 Task decomposition (writing-plans-phase consumes; brainstorm pre-locks the count)

| Task | Scope | LOC | Tests | Dependencies |
|---|---|---|---|---|
| T-1.1 | Predicate + recipe synthesis helpers | ~+90 | ~+20 | — |
| T-1.2 | `ClassificationResult.auto_redirect_recipe` field + integration in `_classify_unmatched_fill_shared` | ~+30 | ~+10 | T-1.1 |
| T-1.3 | Comparator emit-shape extension (each Pass-2 candidate carries `executions`) | ~+30 | ~+8 (verifies Sub-bundle 1's emit-shape backward-compat) | — |
| T-1.4 | `apply_tier2_resolution` parameterization (`applied_by_override` + `correction_action_override` + `resolved_by_override`) | ~+40 | ~+8 | — |
| T-1.5 | Flow-pivot loop auto-redirect branch + counter | ~+50 | ~+10 | T-1.1, T-1.2, T-1.4 |
| T-1.6 | Sandbox short-circuit gating in `_apply_tier2_resolution_inner` | ~+10 | ~+4 | T-1.4 |
| T-1.7 | `_fetch_recent_multi_leg_auto_correction_count` helper | ~+30 | ~+6 | — |
| T-1.8 | `BaseLayoutVM` field + retrofit across ≥13 VMs | ~+15 (1 LOC × ≥13) | ~+13 (one per VM verifies default 0) | T-1.7 |
| T-1.9 | `base.html.j2` template render + sentinel audit | ~+10 | ~+5 | T-1.8 |
| T-1.10 | CLI `--resolved-by <value>` filter on `swing journal discrepancy list` | ~+15 | ~+3 | — |
| T-1.11 | E2E integration test: plant multi-leg fixture → pipeline run → assert auto-redirect + banner + CLI list filter | ~+0 (test only) | ~+1 slow-marked | T-1.5, T-1.7, T-1.10 |

**Total: ~+320 LOC + ~+85 fast tests + 1 slow E2E test.** Within Sub-bundle 1.5 + 2 precedent ranges.

### §9.3 Operator-witnessed gate surfaces (5)

- **S1:** Inline pytest (`pytest -m "not slow" -q`) + ruff (E501 baseline 18) + slow E2E test. PASS = all tests + ruff unchanged.
- **S2:** Synthetic-fixture predicate matrix walk-through via `python -c` — plant 5-8 distinct fixtures (per §10) + assert classifier returns expected `auto_redirect_recipe` shape.
- **S3:** Production fetch — `python -m swing.cli schwab fetch --orders` against operator's production tokens. Either (a) production data contains a multi-leg case → auto-redirect fires + banner appears OR (b) no multi-leg case in current window → assert backward-compat negative sense (NO false-positive tier-1 auto-corrections on non-multi-leg cases). Sub-bundle 1.5 30-day production sample suggests (b) is the likely outcome at gate time.
- **S4:** Banner UI — `swing web --port 8081` + curl `/dashboard` HTML → grep for `class="reconciliation-auto-redirect-banner"`. PASS = present when count > 0; absent when count == 0. **Banner-clears trigger (Codex R4 minor 2 LOCK)**: V1 helper queries `COUNT(DISTINCT discrepancy_id)` for `resolved_by='auto_tier1_multi_leg'` filtered by `reconciliation_run_id == latest_completed_run_id`. The banner clears EXCLUSIVELY when the NEXT reconciliation_run completes (a new run becomes the latest; auto-redirects from the prior run no longer counted in the window). **Tier-3 override does NOT clear the banner mid-window** — `apply_tier3_override` writes a new correction row + supersedes the prior chain head but does NOT rewrite the parent `discrepancy.resolved_by`. The auto-redirect IS audit-recorded; the banner reflects "the system applied N auto-corrections this run" regardless of subsequent operator override. This is by-design + intentional (preserves vigilance signal). Discriminating test plants a multi-leg auto-correction → curls dashboard → grep banner present → invokes tier-3 override on the chain head → curls again → grep banner STILL present + count unchanged. The next reconciliation_run completion flips the helper's `latest_run_id` → banner clears.
- **S5:** CLI filter — `swing journal discrepancy list --resolved-by auto_tier1_multi_leg` returns the auto-redirected rows.

### §9.4 Codex round projection

3-4 rounds expected:
- **R1:** structural critiques (parameter-override threading; corrections-CHECK invariant audit; cross-column CHECK satisfaction; sentinel-leak audit).
- **R2:** predicate edge cases (e.g., negative-direction legs; pathological tolerance cases; n=1-with-multi-leg single-order case from §6.5).
- **R3:** banner-window semantics + retrofit completeness (every VM populated; helper invocation sites).
- **R4 (if needed):** any minor polish or test discrimination tightening.

Less than Sub-bundle C's 9 rounds because §1 LOCKs bound the architectural surface.

---

## §10 Discriminating-example walkthroughs

**Case A — single-order multi-leg, predicate fires (n=1, len(executions)=3); reachable via Pass-1-failure-by-date-or-qty:**

**Reachability scenario (Codex R2 M3 LOCK):** Pass-1 must EMIT an `unmatched_*_fill` discrepancy for the n=1 reroute path to be reached. This requires Pass-1 to find NO match. Concrete realistic scenarios:

- (a) Operator typed journal `fill_datetime='2026-05-10'` but actual Schwab execution date is `'2026-05-11'` (operator typo or timezone-rollover edge). Pass-1's (ticker, date, qty) match-tuple fails on date → emit `unmatched_open_fill` with `actual_value_json={"matched": null}` (per existing Sub-bundle 1.5 emit shape).
- (b) Operator typed journal `quantity=200` but actual Schwab `filledQuantity` is `198` due to operator estimation rounding. Pass-1's qty match fails → emit `unmatched_open_fill`.
- (c) Operator typed journal `ticker='YOU'` but actual Schwab ticker code was `'YOU.X'` (extended-hours convention). Pass-1's ticker match fails → emit `unmatched_open_fill`.
- (d) Sub-bundle 1 mapper-coherence-check rejection silently dropped Schwab's `executions` field for ALL Pass-1 candidates → Pass-1 falls back to order-grain logic per Path B sentinel → emits `unmatched_open_fill` despite the journal price aligning with execution VWAP. Pass-2 re-fetches with fresh window → finds the same Schwab order (now executions populated post-Sub-bundle-1.5 fix) → n=1 reroute kicks in.

For Case A's specific numerics:
- Schwab: 1 order, FILLED LIMIT, executions=[(qty=100, $5.30), (qty=50, $5.31), (qty=50, $5.30)].
- Journal: consolidated fill qty=200 @ $5.305 (BUT one of scenarios (a)-(d) caused Pass-1 to fail).
- Pass-2 widens match window → finds 1 candidate Schwab order.
- Predicate fires:
  - n=1 with `len(executions)=3 >= 2` → triggers §6.5 reroute path.
  - total_qty=200 ✓ matches journal qty=200.
  - VWAP = (100*5.30 + 50*5.31 + 50*5.30) / 200 = $5.3025 (NOTE: corrected from prior version's 5.305 typo) → journal aligned within $0.01 ✓.
  - All 3 legs within $0.01 of VWAP ✓.
- Classifier output: tier=2, ambiguity_kind RECLASSIFIED from `'unknown_schwab_subtype'` (default for n=1) to `'multi_partial_vs_consolidated'`, auto_redirect_recipe={choice_code='split_into_partials', payload=[3 partials], resolved_by='auto_tier1_multi_leg', applied_by_override='auto', correction_action_override='auto_applied'}.

**Discriminating regression test:** plant the Pass-2 fixture EXPLICITLY (don't synthesize via Pass-1 invocation — that's E2E test scope at T-1.11). Test fixture supplies `source_payload=[{order_id, quantity=200, price=$5.30, executions=[3 legs]}]` + journal_row + assert classifier output shape.

**Case B — multi-order single-leg-each, predicate fires (n=2, len=1+1 = 2 legs):**

- Schwab: 2 orders, each FILLED LIMIT, leg=[(qty=75, $7.50)] and [(qty=75, $7.51)].
- Journal: consolidated fill qty=150 @ $7.505.
- Predicate: total_qty=150 ✓; VWAP = (75*7.50 + 75*7.51) / 150 = 7.505 ✓; both legs within $0.01 of VWAP ✓.
- Result: auto-redirect fires; payload=[2 partials at $7.50 and $7.51].

**Case C — VWAP aligns but per-leg outlier (predicate DECLINES):**

- Schwab: 3 legs at prices $5.30, $5.30, $5.34, qty=100 each.
- Journal: qty=300 @ $5.313 (VWAP).
- Predicate: total_qty=300 ✓; VWAP=5.313; journal $5.313 aligns ✓; BUT leg #3 delta to VWAP = $0.027 > $0.01 → DECLINE.
- Result: tier=2, no recipe (auto_redirect_recipe=None); falls back to manual `multi_partial_vs_consolidated` operator menu. correction_reason carries "leg #3 outlier" rationale.

**Case D — qty sum mismatch (predicate DECLINES):**

- Schwab: 2 legs summing to qty=180.
- Journal: consolidated qty=200.
- Predicate: total_qty=180 != journal 200 → DECLINE at sub-condition 2.
- Result: classifier emits existing `multi_match_within_window` (this branch is REACHED only when qty matches at the n>=2 branch; if qty doesn't match the classifier already emits multi_match_within_window per existing line 921-933 logic). Predicate is not reached in this case — pre-existing flow. NO regression.

**Case E — VWAP aligns within tolerance but journal price doesn't (predicate DECLINES):**

- Schwab: 2 legs at $7.50 + $7.51, qty=75 each, VWAP=$7.505.
- Journal: $7.55.
- Predicate: VWAP-journal delta = $0.045 > $0.01 → DECLINE at sub-condition 5.
- Result: tier=2 manual menu; reason cites "VWAP $7.505 vs journal $7.55; delta $0.045 > $0.01 tolerance."

**Case F — execution data absent on one candidate (predicate DECLINES):**

- Schwab: 2 candidates; first has executions=[(qty=100, $5.30)]; second has executions=None.
- Predicate: sub-condition 1 DECLINES on candidate #2 ("no execution legs").
- Result: tier=2 manual menu. Reason cites the absence.

**Case G — boolean-as-numeric leg field (predicate DECLINES, defensive):**

- Synthetic fixture (production cannot emit this per dataclass `__post_init__` validator):
- Single leg with `price=True` (Python bool — subclass of int).
- Predicate: sub-condition 3 DECLINES via `isinstance(leg.price, bool)` reject.
- Result: tier=2 manual menu. (Defensive coverage; will not surface in production but pins the guard.)

**Case H — NaN/inf leg price (predicate DECLINES, defensive):**

- Synthetic fixture: leg.price = float("nan").
- Predicate: sub-condition 3 DECLINES via `math.isfinite()` reject.
- Result: tier=2 manual menu.

**Case I — N=2 candidates each with multi-leg, all-match-within-tolerance (predicate fires; large N):**

- Schwab: 2 orders; order #1 has 3 legs at $5.30/$5.31/$5.30, qty 100/50/50; order #2 has 2 legs at $5.31/$5.30, qty 100/100.
- All 5 legs combined: total_qty=400; VWAP = (100*5.30 + 50*5.31 + 50*5.30 + 100*5.31 + 100*5.30) / 400 = (530+265.5+265+531+530)/400 = 2121.5/400 = $5.30375.
- Journal: qty=400 @ $5.30375.
- Predicate: all-match within $0.01 ✓.
- Result: auto-redirect fires; payload=[5 partials].

**Case J — sandbox env (predicate satisfied but write short-circuited; SAVEPOINT rolls back stamp per §7.6.1 LOCK):**

- Same input as Case A.
- `environment='sandbox'` flag passed to flow-pivot loop.
- Predicate fires; recipe synthesized; pivot-loop stamps `pending_ambiguity_resolution` inside SAVEPOINT; `_apply_tier2_resolution_inner` invoked with `applied_by_override='auto'`.
- Inner function raises `_SandboxAutoRedirectShortCircuit(discrepancy_id)` immediately after SELECT-first idempotency check (per §7.6.1 LOCK).
- SAVEPOINT rolls back — the pending_ambiguity_resolution stamp is UNDONE.
- Discriminating asserts: post-pivot `discrepancy.resolution = 'unresolved'` (NOT 'pending_ambiguity_resolution'); NO journal mutation; ZERO correction rows for this discrepancy; banner count for the run = 0; `counters["sandbox_auto_redirect_skipped_count"] == 1`; WARNING log emitted citing the discrepancy_id.

---

## §11 Cascade analysis

### §11.1 Downstream consumers of `resolved_by='auto_tier1_multi_leg'`

| Consumer | Touch needed | Notes |
|---|---|---|
| Phase 10 dashboard banner (`unresolved_material_discrepancies_count`) | **NO** | Banner counts `material_to_review=1 AND resolution='unresolved'` — auto-redirected discrepancies are in `operator_resolved_ambiguity` state, hence NOT counted. Pre-existing logic unchanged. |
| Phase 12 Sub-bundle C.D `pending_ambiguity_resolution` banner widening | **NO** | Same logic — auto-redirected discrepancies skip the `pending_ambiguity_resolution` terminal state (they pass through it transiently within the SAVEPOINT). |
| Briefing.md "Reconciliation status" section | **MAYBE** | Counter `tier1_applied_count` and `tier2_pending_count` exist per Sub-bundle C.C. Phase 12.5 #1 adds `tier1_multi_leg_auto_redirected_count` counter — briefing should surface this separately. Brainstorm recommends: yes, +1 line per run summary block. ~+10 LOC `_step_export`. |
| `swing journal discrepancy show-correction <id>` epilog | **NO** | Already renders the canonical correction-row fields. The auto-vs-manual distinction surfaces via `applied_by` + `resolved_by`. Operator reads from the rendered values. |
| `swing journal discrepancy list` default filters | **NO**, **plus +1 new filter** | New `--resolved-by <value>` filter per §8.6. |
| Phase 10 metrics dashboard | **NO** | Auto-corrections feed the existing reconciliation_corrections counters used in capital-friction + funnel surfaces; auto-redirect rows aggregate identically to manual rows. |
| Existing tests for `unmatched_open_fill` + `unmatched_close_fill` classifier | **MUST RE-PASS** | None of the existing tests plant `executions` keys on Pass-2 candidates → predicate sub-condition 1 declines → existing branch behavior preserved. ZERO false-positive auto-redirects from existing test fixtures. |
| Sub-bundle 1 + 1.5 tests for mapper + comparator | **NO touch** | T-1.3 extends emit shape; cassette + hand-rolled tests for the comparator's Pass-2 emit may need `executions` key added or stay backward-compat depending on whether they assert specific emit shape. Brainstorm recommends: ADD `executions=None` to existing Pass-2 emit fixtures (preserves predicate sub-condition 1 decline). |

### §11.2 Briefing.md format change

Sub-bundle C.C extended `BriefingInputs` with `reconciliation_pending_count` + `reconciliation_tier1_recent_count`. Phase 12.5 #1 extends with a third counter:

```
BriefingInputs.reconciliation_tier1_multi_leg_redirected_count: int = 0
```

`_step_export` emits a new "auto-redirected" line in the Reconciliation status section when count > 0:

```
Reconciliation status:
- N tier-1 auto-corrections applied this run.
- M tier-2 ambiguity discrepancies pending operator review.
- K multi-leg auto-redirects applied this run.
```

**Counter semantics (Codex R2 M1 — LOGICAL not ROW-level):** `K` is `COUNT(DISTINCT discrepancy_id)` for `resolved_by='auto_tier1_multi_leg'` rows in this run. `_step_export`'s inline SQL uses the same `COUNT(DISTINCT)` pattern as §8.2 to avoid double-counting `_handle_split_into_partials`'s N+1 correction rows.

**Forward-binding lesson family (§16 #8):** any new metric/counter aggregating reconciliation_corrections rows MUST decide ROW-level vs LOGICAL semantics at writing-plans time. The `_handle_split_into_partials` N+1-rows-per-logical-correction shape is a recurring trap. Default to `COUNT(DISTINCT discrepancy_id)` for "auto-correction count" semantics; use `COUNT(*)` only when the metric INTENTIONALLY counts rows (e.g., total writes per run).

### §11.3 Existing test forward-compatibility

The classifier's `_classify_unmatched_fill_shared` already handles list-shaped `source_payload` with N >= 2 via the existing branch. Phase 12.5 #1 ADDS a new branch BEFORE the existing tier-2 emit returns. The existing branch's `ClassificationResult` shape is preserved (with `auto_redirect_recipe=None` default). Tests asserting `result.tier == 2 and result.ambiguity_kind == 'multi_partial_vs_consolidated'` still pass.

Discriminating regression: a test asserting `result.auto_redirect_recipe is None` for a fixture WITHOUT `executions` keys MUST land in T-1.2.

---

## §12 Test fixture strategy

### §12.1 Hand-rolled synthetic fixtures (PRIMARY V1)

Per brief §2.6 Option C, recommend hand-rolled fixtures covering the 10 cases in §10. Test file `tests/trades/test_reconciliation_classifier_multi_leg_redirect.py`:

- Case A (n=1 multi-leg) → expected: recipe present + 3 partials.
- Case B (n=2 single-leg-each) → expected: recipe present + 2 partials.
- Case C (per-leg outlier) → expected: recipe=None + reason cites outlier.
- Case D (qty sum mismatch) → expected: existing multi_match_within_window emit, recipe=None.
- Case E (VWAP-journal misalign) → expected: recipe=None + reason cites VWAP delta.
- Case F (missing executions on candidate) → expected: recipe=None + reason cites missing legs.
- Case G (bool-as-numeric leg) → expected: recipe=None (defensive).
- Case H (NaN price leg) → expected: recipe=None (defensive).
- Case I (large N=5 across 2 orders) → expected: recipe present + 5 partials.
- Case J (sandbox env) → expected: service short-circuits.

### §12.2 Cassette opportunity reserved V2

Sub-bundle 1.5 30-day production sample had ZERO multi-leg fills. Recording a Schwab cassette for a multi-leg case requires the operator to actually execute a multi-leg fill in production. When that occurs, the writing-plans phase OR a follow-up dispatch records the cassette under `tests/integrations/cassettes/schwab/orders-multi-leg-fill.yaml` (operator-paired session; sanitization filter list per Sub-bundle 1 + 1.5 precedent).

Until then, hand-rolled fixtures cover the 10 cases above. **Synthetic-fixture-vs-production-emitter shape drift** (C.D lesson) mitigation: T-1.3 ensures comparator emit shape includes `executions` key; T-1.5's slow E2E test exercises the FULL flow through service composition with hand-rolled fixtures planted in `reconciliation_discrepancies` + `reconciliation_corrections`.

### §12.3 Canary observability hook (Sub-bundle 1.5 lesson #3 inheritance)

Mirror `_has_non_placeholder_leg(activities)` canary helper pattern: when the predicate DECLINES with a reason like "executions absent" but the candidate dict has `executions=[]` empty-list shape (Schwab returned zero legs intentionally), emit a WARN log line so operator can spot anomalous shapes. ~+5 LOC + 1 test.

---

## §13 Schema impact analysis

### §13.1 Verdict: schema v19 UNCHANGED

**Audit complete:**

| Schema element | Current state | Phase 12.5 #1 need | Migration required? |
|---|---|---|---|
| `reconciliation_discrepancies.resolution` CHECK enum (9 values) | Includes `operator_resolved_ambiguity` | Final state | NO |
| `reconciliation_discrepancies.ambiguity_kind` CHECK enum (7 values) | Includes `multi_partial_vs_consolidated` | Final state | NO |
| `reconciliation_discrepancies` cross-column CHECK | Pairs `operator_resolved_ambiguity` + non-NULL ambiguity_kind | Satisfied by final state | NO |
| `reconciliation_discrepancies.resolved_by` | Free TEXT (no CHECK) | New value `'auto_tier1_multi_leg'` | NO (free text) |
| `reconciliation_corrections.applied_by` CHECK enum | `('auto', 'operator')` | `'auto'` for auto-redirect | NO (already permits) |
| `reconciliation_corrections.correction_action` CHECK enum | `('auto_applied', 'operator_resolved_ambiguity', 'operator_overridden')` | `'auto_applied'` for auto-redirect | NO (already permits) |
| `trade_events.event_type` CHECK enum | Includes `reconciliation_auto_correct` | Emitted by `_handle_split_into_partials` already | NO |
| Any other schema element | — | — | NO |

**ESCALATION RULE per brief §4 OUT-OF-SCOPE not triggered.** This bundle ships schema v19 unchanged.

### §13.2 Python-constant audit

Per CLAUDE.md gotcha "Schema-coverage Python constant is NOT necessarily the manual-input allowlist":

- `_RESOLUTION_VALUES` (Python-side; in `swing/data/repos/reconciliation.py` or similar) — `grep` found NO matches for `_RESOLVED_BY_VALUES` (the brief §2.4 reference was incorrect — no such constant exists). `resolved_by` is free TEXT both at schema layer + Python passthrough. NO Python constant widening needed.
- `_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS` (Sub-bundle C.C R2 M#1 lock) — does NOT include `operator_resolved_ambiguity`. The auto-redirect path does NOT go through the manual `resolve_discrepancy` CLI surface — it routes through `apply_tier2_resolution`. The `_MANUAL_RESOLVE_ALLOWED_RESOLUTIONS` lock is preserved unchanged.
- `RESOLUTION_TYPES` (Phase 9 Sub-bundle B) — covers all 9 resolution values. NO Python-side change needed.

### §13.3 Brief §2.4 deviation

Brief §2.4 referenced extending `_RESOLVED_BY_VALUES` enum. **This constant DOES NOT EXIST in the codebase as of HEAD `37b584d`.** The brief writer presumably referenced an analogue from the schema enum widening discipline. Spec preserves the brief's intent (introduce a NEW `'auto_tier1_multi_leg'` distinguishable string) without inventing a new Python constant. If writing-plans / executing-plans phases decide to formalize a Python constant `_RESOLVED_BY_VALUES` for the 3-value enum (`'auto', 'operator', 'auto_tier1_multi_leg'`) plus dataclass validator + tests, that's a polish addition NOT blocking V1 ship.

**Spec amendment candidate (§15):** clarify brief §2.4 to reflect that resolved_by is free-text + no Python constant exists. Banked for orchestrator V2.1 §VII.F amendment routing.

---

## §14 V2 candidates banked

1. **Banner predicate window — 7-day rolling.** Operator may want to see multi-leg auto-corrections across the recent week, not just the most-recent run. V2 widens helper signature with `window='rolling_7_day'` branch.
2. **Banner predicate window — persists-until-acknowledged.** Requires `recent_auto_redirect_acknowledged_at` persistence column. Defer V2.
3. **Dedicated `/metrics/auto-redirects` review page.** Operator rejected V1 (brief §1.4). V2 candidate if operator workflow shifts.
4. **Schwab cassette recording for multi-leg fill.** Operator-paired; deferred until production multi-leg fill surfaces.
5. **Defensive cap on N legs.** Brainstorm recommends no V1 cap; V2 could add a configurable max (e.g., 50 legs) for memory hygiene.
6. **`_RESOLVED_BY_VALUES` Python constant formalization.** Spec amendment to brief §2.4. If writing-plans wants to land a 3-value enum + validator, V2 polish.
7. **Promote `auto_redirect_recipe` to typed dataclass.** If V2 reuse patterns emerge (e.g., other tier-2 → tier-1 auto-redirects for other ambiguity_kinds), formalize.
8. **Per-leg `mismarked_quantity` consumption.** V2 if Schwab API surfaces meaningful mismark accounting; V1 ignores.
9. **Operator-acknowledged-clear surface.** CLI subcommand `swing journal reconciliation acknowledge-redirects` to clear banner before next run. V2.
10. **Predicate runs on n=1 with multi-leg single-order case** — §6.5 design item. Brainstorm recommends YES at V1; Codex review confirms.
11. **Audit trail surfacing in show-correction epilog.** When operator runs `show-correction <id>` against an auto-redirect chain head, render an explicit "multi-leg auto-redirect" banner-style label. V2 polish.
12. **Other tier-2 ambiguity_kinds auto-redirect candidates.** `multi_match_within_window` with single-execution-bearing record could become auto-redirect at V2. Pattern reuses §5.1 recipe field.

---

## §15 Operator decision items + Codex-confirmation triage

Per Codex R1 Minor 2 — split into LOCKED-by-this-brainstorm (Codex resolved or moot post-fix) vs STILL-OPEN (operator may override at writing-plans handoff).

### §15.A LOCKED by this brainstorm (Codex chain resolved)

These items reached design closure in Round 1 + the in-tree fixes; writing-plans inherits the locks.

- **§6.5 n=1 single-order multi-leg path** — LOCKED YES via ambiguity_kind reclassification at the n=1 branch (Codex R1 M2 fix). See §6.5 binding contract.
- **§8.6 `--resolved-by <value>` CLI filter** — LOCKED IN-BUNDLE at T-1.10 (Codex R1 M5 fix). Banner template cites it; both land together.
- **§7.6 sandbox short-circuit gating granularity** — LOCKED gated-on-auto-redirect (Codex R1 M3 fix). See §7.6.1 SAVEPOINT ROLLBACK pattern.
- **§7.4 service API parameter naming** — LOCKED to `operator_custom_payload` (existing kwarg) + new `applied_by_override` / `correction_action_override` / `resolved_by_override` overrides (Codex R1 M4 fix). See §7.1.
- **§11.2 briefing.md format change** — LOCKED YES; +1 line per run for `tier1_multi_leg_redirected_count` when > 0. See §11.2.
- **§12.3 canary observability for empty-executions case** — LOCKED YES; ~+5 LOC + 1 test (Sub-bundle 1.5 canary precedent).
- **§13.3 Brief §2.4 amendment** — LOCKED + amendment banked (no `_RESOLVED_BY_VALUES` constant exists; resolved_by is free TEXT; brief writer error).

### §15.B Still open (operator may override at writing-plans handoff)

These are advisory items where brainstorm proposes a default but operator-decision-routing remains in V1 scope.

1. **§4.4 floating-point tolerance threshold.** `price_tolerance=$0.01` LOCK per spec §4.4 inheritance. Operator may override toward `max($0.01, abs(journal_price) * 0.001)` for higher-priced stocks. Brainstorm default: LOCK $0.01 absolute.
2. **§6.3 `qty_tolerance` mismatch.** Predicate uses `1e-9`; `_handle_split_into_partials` uses `1e-6`. Strictness asymmetry is safe (predicate stricter than handler). Brainstorm default: LOCK predicate=1e-9.
3. **Defensive cap on N legs** (§6.4 + §14 #5). Brainstorm default: NO cap V1 (production evidence supports unbounded; mapper-coherence-check already prevents pathological shapes). Operator may impose cap (e.g., 50) for memory hygiene.

---

## §16 Forward-binding lessons for writing-plans phase

Following Sub-bundle 1 + 1.5 + 2 forward-binding lesson tradition:

1. **Recipe-field discipline.** When extending classifier output with new optional fields that drive dispatcher behavior, default to `None` AND provide explicit acceptance criterion: existing tests pass without modification (recipe=None default for all pre-existing emit paths). Discriminating regression: assert `auto_redirect_recipe is None` on all pre-existing fixture outputs.
2. **Override parameter threading.** When parameterizing existing service-layer functions (apply_tier2_resolution gains 3 new kwargs), default values MUST preserve verbatim existing-behavior. Writing-plans tests assert no regression on the manual-tier-2 path WITHOUT supplying the new kwargs.
3. **Free-text columns vs CHECK enum columns.** `resolved_by` is free TEXT (no schema CHECK) — adding new values doesn't require migration. `applied_by` IS CHECK-enumerated — verify enum already permits before adding new value. Pattern: pre-flight `grep -n CHECK` on the migration SQL for every new string value.
4. **Cross-column CHECK invariants.** Schema 0019's `(ambiguity_kind, resolution)` pairing — every transition through service-layer code MUST satisfy. Discriminating test: assert post-transition state passes the CHECK explicitly via a `CHECK` probe (or equivalent SQL).
5. **Sandbox short-circuit ALWAYS in inner.** C.C lesson #2 carry-forward. Sandbox-gating for the auto-redirect path lives in `_apply_tier2_resolution_inner` GATED on `applied_by_override == 'auto'`.
6. **Helper invocation completeness.** Every `BaseLayoutVM` subclass (and every retrofit VM not subclassing) MUST populate the new field. Grep + retrofit test discipline per Phase 10 T-E.3 + Sub-bundle 2 precedent.
7. **ASCII-only banner text.** CLAUDE.md Windows cp1252 gotcha — banner text in `base.html.j2` uses ASCII only. NO em-dash, no arrows, no glyphs. Discriminating: curl + grep gate verification works deterministically.

---

## §17 Spec line count + delivery checklist

Target: ~750-900 lines per brief §6. Actual final at commit: TBD post-Codex.

Delivery checklist:
- [x] §0 Glossary written.
- [x] §1 Architecture overview written.
- [x] §2 Operator-locks verbatim binding clauses written.
- [x] §3 Module touch list written.
- [x] §4 Predicate design written.
- [x] §5 Classifier dispatch state design written.
- [x] §6 Payload synthesis design written.
- [x] §7 Auto-correct service integration written.
- [x] §8 Banner advisory design written.
- [x] §9 Sub-bundle decomposition written.
- [x] §10 10 discriminating walkthrough cases written.
- [x] §11 Cascade analysis written.
- [x] §12 Test fixture strategy written.
- [x] §13 Schema impact verdict written (v19 UNCHANGED LOCK).
- [x] §14 V2 candidates banked (12 items).
- [x] §15 Operator decision items (8 items).
- [x] §16 Forward-binding lessons (7 items).
- [ ] Codex adversarial chain → NO_NEW_CRITICAL_MAJOR convergence.

---

*End of brainstorm spec. Codex review pending.*
