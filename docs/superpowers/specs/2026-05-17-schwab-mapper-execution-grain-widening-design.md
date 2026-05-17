# Post-Phase-12 Schwab Mapper Execution-Grain Widening + T-B.7 `/schwab/status` + Housekeeping — Design Spec

**Status:** brainstorm (this doc). Successor: `copowers:writing-plans` decomposition into per-task acceptance criteria + per-sub-bundle execution plans.

**Date:** 2026-05-17.

**Dispatch brief:** `docs/post-phase12-schwab-mapper-execution-grain-widening-brainstorm-dispatch-brief.md` (committed on `main` at `71b9b51`).

**Mission:** Design the standalone post-Phase-12 architectural bundle that (a) closes the V1 Schwab limit-vs-fill defect family empirically falsified at Phase 12 Sub-sub-bundle C.D operator-witnessed gate (2026-05-17, CVGI + LION), (b) lands the Phase 12 Sub-bundle B deferred `/schwab/status` web counterpart, and (c) folds in two cheap housekeeping micro-fixes. Schema stays at v19; no new migrations.

**Predecessors consumed (read-only):**

- Phase 11 Sub-bundle B (`SchwabOrderResponse` dataclass; `map_orders_to_fill_candidates`; `run_schwab_reconciliation` comparator skeleton).
- Phase 11 Sub-bundle D (`swing schwab status` CLI; briefing.md "Schwab integration: degraded" banner; sandbox short-circuit gating; `surface='cli'` audit-row convention).
- Phase 12 Sub-bundle A (env-var cascade for `SCHWAB_CLIENT_ID` + `SCHWAB_CLIENT_SECRET`; tokens DB self-healing rename).
- Phase 12 Sub-bundle B (cfg-cascade for `client_id` + `client_secret`; web `/schwab/setup` Outcome B manual token exchange; nav-link from `/config`).
- Phase 12 Sub-sub-bundle C.A/B/C/D (auto-correct reconciliation pivot; classifier + validator-shim; reconciliation_corrections schema v18→v19; tier-2 CLI surface; Phase 10 banner widening to include `pending_ambiguity_resolution`).

**Phase boundary:** schema v19 (locked at C.A). NO `0020_*.sql` migration in this bundle.

---

## §0 Glossary (terms-of-art used by this spec)

- **Order-grain data:** Schwab API fields at the order-envelope level (`order.price`, `order.stopPrice`, `order.status`). Limit price OR stop trigger; NOT the price at which the order was actually filled.
- **Execution-grain data:** Schwab API fields nested inside `orderActivityCollection[].executionLegs[]`. Each leg carries `legId`, `price` (actual execution price), `quantity` (leg fill quantity), `mismarkedQuantity`, `instrumentId`, and `time` (ISO 8601). One FILLED order can have multiple execution legs when the broker filled the order across multiple price points (partial fills consolidated under one order id).
- **VWAP (volume-weighted average price):** `sum(leg.price * leg.quantity) / sum(leg.quantity)` across an order's execution legs. The single-number aggregation the journal-fill compares against when an order's legs were filled at multiple prices.
- **`Pass-1 tier-1`:** classifier emission of tier-1 (auto-correct) for `entry_price_mismatch` / `close_price_mismatch` discrepancies whose source payload meets the deterministic shape (Sub-bundle C spec §4.3.1 Shape A or Shape B). Under V1, Pass-1 tier-1 fed `order.price` as the corrected value — empirically falsified 2026-05-17.
- **`Pass-2 tier-1-FORBIDDEN`:** classifier prohibition on emitting tier-1 for `unmatched_open_fill` / `unmatched_close_fill` discrepancies. Under V1 (Sub-bundle C.B spec §8.4 LOCK), the prohibition applied uniformly because the only data the classifier had was order-grain. V2 widening enables a CONDITIONAL lift for execution-grain matches.
- **Sandbox short-circuit:** Phase 11 discipline (CLAUDE.md gotcha) — under `cfg.integrations.schwab.environment == 'sandbox'`, Schwab API calls + `schwab_api_calls` audit rows fire, but no domain-row writes (`account_equity_snapshots`, `reconciliation_runs`, `reconciliation_corrections`, journal mutations) occur.
- **Source-ladder source:** `'schwab_api'` vs `'manual'` vs `'tos'`. The `account_equity_snapshots.source_artifact_path` / `reconciliation_runs.source` / `reconciliation_corrections` rows carry this tag.

---

## §1 Locked decisions (operator-decided; do NOT re-litigate)

### §1.1 Execution price IS the truth for fill-grain reconciliation

Schwab API exposes execution-grain data via `orderActivityCollection[].executionLegs[].price`. The V1 mapper at `swing/integrations/schwab/mappers.py:148-242` reads ONLY the order-grain `order.price` (with `stopPrice` fall-back). Empirically falsified twice on 2026-05-17 at Phase 12 Sub-sub-bundle C.D operator-witnessed gate (CVGI $5.30 limit vs $5.2244 execution = $0.0756 delta; LION $12.75 limit vs $12.6999 execution = $0.0501 delta). The architectural fix is the V2 mapper widening to surface execution-leg data.

**Operator lock:** execution-grain price is truth; classifier + comparator MUST consume it when available.

### §1.2 `stop_mismatch` architecture is SOUND — do NOT propose changes there

The `_find_working_stop_for_ticker` path at `swing/trades/schwab_reconciliation.py` compares journal `current_stop` (operator-set trigger) vs Schwab `stopPrice` (operator-set trigger on WORKING-only orders). Both sides are trigger thresholds — apples-to-apples. The limit-vs-fill defect is fill-grain ONLY; stop-trigger compare stays on `order.stopPrice` / `order.price` (the V1 mapper fields stay load-bearing for trigger comparison).

**Operator lock:** `stop_mismatch` comparator unchanged; only `entry_price_mismatch` / `close_price_mismatch` / `unmatched_open_fill` / `unmatched_close_fill` paths consume execution-grain data.

### §1.3 Schema MUST stay at v19

V2 mapper widening fits in package-level dataclass extensions + existing `actual_value_json` envelope. No new tables; no new columns; no migration. If this brainstorm surfaces a need for schema change, STOP — escalate to orchestrator per C.A return report lesson #7 + 2026-05-15 commit `657b8a0` lesson.

**Operator lock:** `EXPECTED_SCHEMA_VERSION` stays at 19 throughout; no `0020_*.sql`.

### §1.4 Audit-trail integrity preserved — historical `reconciliation_corrections` left as-is

Correction chains at `correction_id ∈ {3, 4}` (CVGI) + `{5, 6}` (LION) + `{1, 2}` (C.C T-C.11 test) recorded V1's WRONG `schwab_said_value_json` (the limit, not the execution). These chain heads are FORENSIC RECORDS of what V1 saw — do NOT propose retroactive UPDATE / DELETE. OQ-G operator-decided: leave-as-is + document.

**Operator lock:** no retroactive rewriting of `reconciliation_corrections`.

### §1.5 Multi-leg VWAP for V1 Pass-1; per-leg `multi_partial_vs_consolidated` auto-redirect for Pass-2 is V2

**Codex R1 M#4 clarification — two distinct cases:**

- **Pass-1 (`entry_price_mismatch` / `close_price_mismatch`) — single-leg AND multi-leg VWAP both eligible for tier-1.** When `len(executionLegs) >= 1` AND `sum(executionLegs[].quantity) == journal.quantity` (within tolerance) AND a single Schwab order matched the journal fill, the V1 comparator uses VWAP (degenerate-to-single-leg when N=1) as the execution-grain price; comparator emits Shape C `entry_price_mismatch` / `close_price_mismatch` when VWAP diverges from journal `f.price` outside `price_tolerance`. Classifier emits tier-1 with `correction_target={'price': VWAP}` for both single-leg AND multi-leg cases. The walkthrough at §10.4 (50@$10.00 + 50@$10.20 VWAP=$10.10) is BINDING for multi-leg Pass-1 tier-1.
- **Pass-2 (`unmatched_open_fill` / `unmatched_close_fill`) — only single-leg single-matched-Schwab-order eligible for tier-1 LIFT.** When no Schwab order matched the journal fill by `(ticker, quantity)` tuple, the classifier's existing `_classify_unmatched_fill_shared` may have multiple candidate Schwab records to consider. V2 LIFTS Pass-2-tier-1-FORBIDDEN ONLY for the simplest case: exactly ONE matching Schwab order with `len(executions) == 1` AND quantity-match exact AND date-match exact. ANY other Pass-2 case (multi-match-within-window; multi-leg-fill-vs-journal-single-entry; partial-match) stays tier-2. The auto-redirect from tier-2 `multi_partial_vs_consolidated` → tier-1 `split_into_partials` for the multi-Schwab-order-summing-to-journal case is DEFERRED to OQ-F V2 follow-up dispatch.

**Operator lock:**

- V1 Pass-1 multi-leg VWAP tier-1 ALLOWED.
- V1 Pass-2 LIFT scope is single-leg single-matched-order ONLY.
- Pass-2 multi-leg auto-redirect deferred V2.

### §1.6 Magnitude is NOT the axis (Sub-bundle C inheritance)

Per Sub-bundle C §1.1 lock #3: NO magnitude-based thresholds. The decision axis is **determinism** (can the classifier confidently disposition without operator input?) NOT delta size. V2 mapper widening preserves this — e.g., NO "only execute tier-1 when `delta < $1.00`" gating.

**Operator lock:** the tier-1 / tier-2 boundary is determinism-driven; tolerance window is a separate per-comparison parameter (`price_tolerance`; see §6.2 OQ-C lock).

---

## §2 Current state recap (binding empirical evidence)

### §2.1 Production state at dispatch time (2026-05-17 post-`bd1a62b`)

After the C.D operator-witnessed gate cleanup:

- All 7 previously-unresolved-material reconciliation discrepancies are in terminal states. Banner count = 0.
- CVGI `fills.fill_id=9` price = $5.23 (operator's actual TOS Net Price = $5.2244; journal stored from memory as $5.23; correction chain `correction_id=3` auto-applied wrong $5.30 → `correction_id=4` tier-3 override-back to $5.23).
- LION `fills.fill_id=15` price = $12.70 (operator's actual TOS Net Price = $12.6999; journal stored from memory as $12.70; correction chain `correction_id=5` auto-applied wrong $12.75 → `correction_id=6` tier-3 override-back to $12.70).
- 6 historical `reconciliation_corrections` rows (ids 1-6) record V1's order-grain `schwab_said_value_json` — preserved per §1.4 lock.

### §2.2 Defect chain (V1 limit-vs-fill family)

1. **Mapper** (`swing/integrations/schwab/mappers.py:223-230`): extracts `order.price` only; falls back to `order.stopPrice` for STOP-family orders. Does NOT extract `orderActivityCollection[].executionLegs[]`.
2. **Dataclass** (`swing/integrations/schwab/models.py:132-203`): `SchwabOrderResponse` has 8 fields (order_id, status, enter_time, instrument_symbol, instruction, quantity, order_type, price). No execution-leg field.
3. **Comparator** (`swing/trades/schwab_reconciliation.py:693`): compares journal `f.price` (execution) vs Schwab `so.price` (limit/stop). False-positive `entry_price_mismatch` / `close_price_mismatch` whenever LIMIT ≠ EXECUTION.
4. **Classifier** (`swing/trades/reconciliation_classifier.py:_classify_entry_price_mismatch` & `_classify_unmatched_fill_shared`): given a tier-1-shaped Shape-A persisted-JSON payload, classifier emits tier-1 with `correction_target = {'price': <so.price>}` — the LIMIT, not the EXECUTION. Auto-correct service (`apply_tier1_correction`) writes the wrong value. Pass-2-tier-1-FORBIDDEN LOCK explicitly prohibits tier-1 emission for unmatched-fill discrepancies because the order-grain data is unreliable; the V2 widening makes execution-grain data reliable enough to LIFT this LOCK conditionally.
5. **Operator workflow at V1**: after `reconcile-backfill --apply` writes a tier-1 auto-correct, operator audits each affected fill against TOS Net Price column and uses `swing journal discrepancy override-correction <id> --custom-value '{"price": X.XX}'` to write a tier-3 chain head with operator-truth.

### §2.3 Phase 11 Sub-bundle B gate-fix #1 + C.D gate-fix #2 precedent

Existing CLAUDE.md gotcha "schwabdev camelCase kwarg discipline" — every wrapper around schwabdev `Client.*` MUST pin the kwarg signature via `inspect.signature` discriminating tests. V2 mapper widening does NOT add new `Client.*` calls (the existing `Client.account_orders` call already returns `orderActivityCollection`), so this discipline is inherited but not re-tested for new entry points.

Existing CLAUDE.md gotcha "synthetic-fixture-vs-production-emitter shape drift" — C.D gate-fix #2 caught a case where test fixtures used `field_name='price'` (a real column) but production emitted `field_name='fill_match'` (a synthetic label). V2 widening MUST pin its test fixtures to production payload shapes — in particular, the new `executionLegs[]` extraction MUST be exercised against a CASSETTE-RECORDED Schwab response (operator-paired session per OQ-E), not only against a hand-rolled fixture.

---

## §3 Target architecture (V2)

### §3.1 Architectural shape

V2 mapper widening introduces ONE new package-level dataclass + ONE optional field on an existing dataclass + ONE mapper-body extension. The comparator + classifier consume the new field; everything else stays on the V1 contract.

```
Schwab API JSON                             V2 mapper                                      V2 comparator + classifier
─────────────────                           ──────────                                      ───────────────────────────
"orderActivityCollection": [                map_orders_to_fill_candidates(...)             schwab_reconciliation.py:693
  {                                          → SchwabOrderResponse(                          if so.executions:
    "executionLegs": [                          ...,                                            execution_price = _vwap(so.executions)
      { "legId": 0, "price": 5.2244,           executions=[                                  else:
        "quantity": 100, "time": ... }          SchwabExecutionLeg(                            # OQ-A Path B: tier-2 `unsupported`
    ]                                              leg_id=0, price=5.2244, qty=100, ...      reconciliation_classifier.py
  }                                            ]                                              for unmatched_open_fill /
]                                            )                                                unmatched_close_fill:
                                                                                                if so.executions and matched_tuple:
                                                                                                   tier=1 (LIFT FORBIDDEN)
                                                                                                else:
                                                                                                   tier=2 (preserve LOCK)
```

### §3.2 Module touch list

| Module | Change |
|---|---|
| `swing/integrations/schwab/models.py` | Add `SchwabExecutionLeg` frozen dataclass + `executions: list[SchwabExecutionLeg] \| None = None` field on `SchwabOrderResponse`. |
| `swing/integrations/schwab/mappers.py` | Extend `map_orders_to_fill_candidates` to extract `orderActivityCollection[].executionLegs[]` per order; assemble `SchwabExecutionLeg` instances; assign to `SchwabOrderResponse.executions`. |
| `swing/trades/schwab_reconciliation.py` | Add `_compute_execution_price(so) -> float \| None` helper (single-leg → leg price; multi-leg → VWAP; absent → None) AND a `_resolve_match_quantity(so) -> float` helper that prefers execution-grain `sum(legs.quantity)` over order-grain `so.quantity` when executions present (closes Codex R1 M#2 fill-vs-order quantity-grain divergence). Replace `so.price` at line 693 with `_compute_execution_price(so)`; the OQ-A Path B lock at §6.1 routes the `None` case to `unmatched_*_fill` with `execution_unavailable=true` sentinel (not Path A fall-back). Same change for the entry_price + close_price comparator paths. Quantity-match step at line 658 switches to `_resolve_match_quantity(so)` (Codex R1 M#2 fix). |
| `swing/trades/reconciliation_classifier.py` | Widen `_classify_entry_price_mismatch` Shape A predicate to recognize a NEW **Shape C — execution-grain audit-bearing**: `source_keys == {"price"} \| _EXECUTION_AUDIT_KEYS` where `_EXECUTION_AUDIT_KEYS = {"execution_legs", "schwab_order_id", "schwab_limit_price"}`; classifier emits tier-1 with `correction_target={'price': <price>}` (audit keys ignored for correction-value purposes; preserved in audit row via `_pivot_classify_and_dispatch_for_run` envelope). Add equivalent Shape C branch to `_classify_close_price_mismatch` (currently tier-2-always per spec §4.3.6 — V2 widens for execution-grain payloads with the same Shape C predicate; preserves the legacy V1 OHLCV-snapshot tier-2 path as a fall-through for pre-V2 close_price_mismatch emits with no execution-grain audit keys). Inside `_classify_unmatched_fill_shared` (consumed by `_classify_unmatched_open_fill` + `_classify_unmatched_close_fill`), recognize an `execution_unavailable=true` sentinel in `actual_value_json` (Path B); emit tier-2 `unsupported` with explanatory reason. **Do NOT** lift Pass-2-tier-1-FORBIDDEN in V1 for unmatched-fill cases — Pass-1 price-mismatch with Shape C is the only LIFT scope (multi-leg auto-redirect at tier-2 → tier-1 deferred to OQ-F V2). |
| `swing/web/routes/schwab.py` | Add `GET /schwab/status` route (read-only). Default environment SOURCES from `cfg.integrations.schwab.environment` after `apply_overrides(cfg)` (mirrors `swing schwab status` CLI semantics); `?environment=` query-param OVERRIDES the cfg default (Codex R1 M#6 fix — preserves "CLI semantics 1:1" lock at §7.4). |
| `swing/web/view_models/schwab.py` | Add `SchwabStatusVM` mirroring CLI's per-environment 3-state output. |
| `swing/web/templates/schwab_status.html.j2` | New template extending `base.html.j2`; inherits Phase 10 T-E.3 banner discipline. |
| `swing/web/templates/config.html.j2` (or partial) | Add `/schwab/status` nav-link under "External integrations" section (mirrors B-`7b75d4a` precedent for `/schwab/setup`). |
| `swing/web/routes/schwab.py` (B path) | Retarget `POST /schwab/setup` success `HX-Redirect: /config?schwab_setup=ok` → `HX-Redirect: /schwab/status` once T-B.7 lands. |
| `CLAUDE.md` | Amend `Pass-2-tier-1-FORBIDDEN` gotcha to mark V2-RESOLVED; correct CVGI date attribution if present (§2.6 housekeeping). |
| `docs/phase3e-todo.md` | Add entry on historical `reconciliation_corrections` leave-as-is + bank V2 follow-up candidates (multi-leg auto-redirect; further mapper widening). |

### §3.3 What does NOT change

- `_find_working_stop_for_ticker` (stop_mismatch trigger comparator — §1.2 lock).
- `SchwabOrderResponse.price` field — stays load-bearing for stop trigger comparison + audit + sandbox-environment fixtures. The new `executions` field is ADDITIVE.
- Sandbox short-circuit gating — V2 mapper widening still fires under sandbox (mapper is pure-function; no I/O), but the auto-correct service path is unchanged and short-circuits at the inner per CLAUDE.md "outer-tx transactional discipline" gotcha.
- Schema (v19; §1.3 lock).
- Existing tier-1 vs tier-2 conventions (Sub-bundle C.B determinism principle, classifier output dataclass, validator chain, auto-correct service surface).
- Existing CLI surface (`swing journal discrepancy {list,show,resolve,…}` + `swing journal reconcile-backfill`).

---

## §4 `SchwabExecutionLeg` + `SchwabOrderResponse` extension

### §4.1 `SchwabExecutionLeg` dataclass (NEW)

Sketch (illustrative — implementation lives in writing-plans):

```
@dataclass(frozen=True)
class SchwabExecutionLeg:
    """One execution leg from Schwab's orderActivityCollection[].executionLegs[]."""

    leg_id: int                      # Schwab "legId"
    price: float                     # actual execution price; > 0; finite
    quantity: float                  # leg fill quantity; > 0; finite
    mismarked_quantity: float | None # Schwab "mismarkedQuantity"; nullable
    instrument_id: int | None        # Schwab "instrumentId"; nullable
    time: str                        # ISO 8601 string; non-empty
```

**Invariants (`__post_init__`)**:

- `leg_id` is `int` (not bool); ≥ 0.
- `price` is `float | int` (not bool); `math.isfinite(price)`; `price > 0`.
- `quantity` is `float | int` (not bool); `math.isfinite(quantity)`; `quantity > 0`.
- `mismarked_quantity`: if non-None, `float | int` (not bool); `math.isfinite()`; `>= 0`.
- `instrument_id`: if non-None, `int` (not bool); `>= 0`.
- `time` is non-empty `str` (raw ISO 8601; per-bar timezone normalization is OUT OF SCOPE V1).

**Rationale (Sub-bundle C.B forward-binding lesson #5):** shape predicate tightening at construction time pre-empts cascade Codex rounds — every Schwab API field gets a discriminating validator.

### §4.2 `SchwabOrderResponse.executions` field (NEW; OPTIONAL)

Add: `executions: list[SchwabExecutionLeg] | None = None` (default None for backward compat). Tri-valued semantics:

- `None` — execution-grain data was not available at mapper time. Per OQ-E, this happens for (a) older orders missing `orderActivityCollection`; (b) WORKING/CANCELED/REJECTED/etc. orders that never filled; (c) sandbox responses that lack the field; (d) defensive fall-back when the mapper rejects a malformed `orderActivityCollection`.
- `[]` (empty list) — `orderActivityCollection` was present but contained ZERO `EXECUTION` activityType entries OR ZERO `executionLegs[]` across all entries. Practically the same as `None` from the comparator's perspective, but distinguished for audit observability ("Schwab confirmed no executions" vs "we never asked / the field was malformed").
- `[leg, ...]` (non-empty list) — one or more execution legs. Single-leg = simple direct compare; multi-leg = VWAP comparator path.

**Rationale for tri-valued (None vs [] vs list[leg]):** Codex R1 family — distinguishing "data not available" from "data was empty" preserves observability. Comparator + classifier branch on `if so.executions` (truthy → use; falsy/None → fall-back).

**`__post_init__` additions on `SchwabOrderResponse`:**

- If `executions` is not None: must be `list`; each element must be `SchwabExecutionLeg` instance; if non-empty, mass coherence pre-check is the COMPARATOR's responsibility (NOT validator's) because invalid Schwab data is observable rather than rejectable — Codex R3 family discipline ("when validators are too strict at the boundary, real-world drift causes the whole pipeline to fail"; mapper logs warning + sets `executions=None` rather than raising).

### §4.3 Mapper extension (`map_orders_to_fill_candidates`)

For each Schwab order dict, BEFORE the `out.append(SchwabOrderResponse(...))` (i.e., AFTER the V1 `price` extraction at line 224-230):

```
order_activities = _opt(raw, "orderActivityCollection", None)
executions: list[SchwabExecutionLeg] | None = None
if isinstance(order_activities, list) and order_activities:
    executions = []
    for j, activity in enumerate(order_activities):
        if not isinstance(activity, dict):
            _log.warning(
                "map_orders_to_fill_candidates: order %s activity[%d] "
                "non-dict; skipping", order_id, j,
            )
            continue
        if _opt(activity, "activityType", "") != "EXECUTION":
            continue
        legs_raw = _opt(activity, "executionLegs", [])
        if not isinstance(legs_raw, list):
            _log.warning(
                "map_orders_to_fill_candidates: order %s activity[%d] "
                "executionLegs non-list; skipping", order_id, j,
            )
            continue
        for k, leg_raw in enumerate(legs_raw):
            if not isinstance(leg_raw, dict):
                _log.warning(
                    "map_orders_to_fill_candidates: order %s activity[%d]"
                    "[%d] non-dict leg; skipping", order_id, j, k,
                )
                continue
            try:
                executions.append(SchwabExecutionLeg(
                    leg_id=int(_opt(leg_raw, "legId", 0) or 0),
                    price=float(_require(leg_raw, "price", ctx=f"order {order_id} leg")),
                    quantity=float(_require(leg_raw, "quantity", ctx=f"order {order_id} leg")),
                    mismarked_quantity=(
                        float(leg_raw["mismarkedQuantity"])
                        if "mismarkedQuantity" in leg_raw
                        and leg_raw["mismarkedQuantity"] is not None
                        else None
                    ),
                    instrument_id=(
                        int(leg_raw["instrumentId"])
                        if "instrumentId" in leg_raw
                        and leg_raw["instrumentId"] is not None
                        else None
                    ),
                    time=str(_opt(leg_raw, "time", "")),
                ))
            except (ValueError, TypeError, SchwabSchemaParityError) as exc:
                # Mapper-level defensive: rather than failing the entire
                # orders fetch on one malformed leg, log + drop the leg.
                # Audit signature_hash continues to be shape-derived per
                # Sub-bundle B precedent.
                _log.warning(
                    "map_orders_to_fill_candidates: order %s activity[%d]"
                    "[%d] rejected by SchwabExecutionLeg validator: %s; "
                    "skipping", order_id, j, k, type(exc).__name__,
                )
                continue
    if not executions:  # all activities/legs filtered out
        executions = None
```

**Rationale (defensive parsing):** mirrors the V1 mapper's existing "skip-with-warning" discipline for missing `orderLegCollection` (lines 201-217). The mapper preserves audit observability via `_log.warning` but does NOT raise — preserving Phase 11 Sub-bundle B's "single bad row doesn't fail the whole fetch" contract. Codex R1 candidate finding: "What if the WHOLE response's `orderActivityCollection` is malformed (e.g., a string)?" — handled by the `isinstance(order_activities, list) and order_activities` guard; the order still gets a `SchwabOrderResponse` with `executions=None` and the comparator falls through per OQ-A.

### §4.4 Backward compat preserved

- Existing call sites of `SchwabOrderResponse(...)` (8-positional-arg form OR keyword form) continue to work; `executions` has a `None` default.
- Existing tests that construct fixtures without `executions=` keyword continue to pass; the comparator falls through per OQ-A.
- Existing `SchwabOrderResponse.price` field continues to be load-bearing for `stop_mismatch` comparator (trigger comparison; §1.2 lock) AND for the OQ-A Path A fall-back path in the fill-grain comparator AND for sandbox-environment fixtures that lack `orderActivityCollection` AND for audit-log redaction (the field is referenced by `__str__` of `SchwabOrderResponse` if such is added in V2 logging).

---

## §5 Comparator path (`swing/trades/schwab_reconciliation.py`)

### §5.1 `_compute_execution_price` helper

NEW pure-function helper (placed near other reconciliation helpers in the same file OR in a sibling module if writing-plans prefers):

```
def _compute_execution_price(
    so: SchwabOrderResponse,
) -> float | None:
    """Return execution-grain price for a Schwab order, or None if unavailable.

    Single-leg → leg.price.
    Multi-leg → VWAP across legs.
    Empty / None executions → None (caller's responsibility to fall through).
    """
    if so.executions is None or not so.executions:
        return None
    if len(so.executions) == 1:
        return so.executions[0].price
    total_qty = sum(leg.quantity for leg in so.executions)
    if total_qty <= 0:
        return None  # defensive; should not happen given dataclass validator
    return sum(leg.price * leg.quantity for leg in so.executions) / total_qty
```

**Rationale:**

- Pure function (no DB, no logging) — testable in isolation.
- Defensive `total_qty <= 0` guard catches the (theoretical) edge case where every leg has `quantity=0` (dataclass validator rejects `quantity <= 0` at construction, so this is belt-and-suspenders).
- Tie-breaking is not needed (VWAP is order-independent over commutative arithmetic).
- Floating-point precision: standard IEEE-754 double-precision (binary fractions — values like $5.2244 are NOT representable exactly, but the represented float is well within `price_tolerance=0.01`). Codex R1 m#1 fix: prior wording said "exactly" which is technically wrong for binary floats; corrected to "sufficiently precise for tolerance." CVGI 100-share single-leg case: stored leg.price ≈ 5.2244 + 1e-16 noise → comparison to 5.23 ≈ delta 0.0056 ± 1e-16 → well under `0.01`. LION analogous. A 2-leg case at 50@$10.00 + 50@$10.20 → VWAP ≈ $10.10 ± 1e-15. A 3-leg case at 33@$10.00 + 33@$10.10 + 34@$10.20 → VWAP ≈ $10.10058… — within `price_tolerance=0.01` of journal's likely $10.10 entry. Catastrophic float precision is not a concern at the magnitudes the project operates in.

### §5.2 Comparator path switch (price comparator)

At `swing/trades/schwab_reconciliation.py:693`, replace:

```
if abs(so.price - float(f.price)) > price_tolerance:
```

with (Path B per OQ-A lock at §6.1):

```
execution_price = _compute_execution_price(so)
if execution_price is None:
    # OQ-A Path B: execution-grain unavailable → emit tier-2 `unsupported`
    # for this fill, NOT a tier-1-shaped entry_price_mismatch / close_price_mismatch.
    _emit(
        conn,
        run_id=run_id,
        discrepancy_type=(
            "unmatched_open_fill" if f.action == "entry"
            else "unmatched_close_fill"  # NB: same discrepancy_type as the
            # quantity-mismatch case; distinguished by actual_value_json
            # carrying the "execution_unavailable" sentinel so the classifier
            # emits tier-2 `unsupported` rather than tier-2 multi-record-match.
        ),
        field_name="fill_match",
        counters=counters,
        dedup_seen=dedup_seen,
        ticker=t.ticker,
        trade_id=t.id,
        fill_id=f.fill_id,
        expected_value_json=json.dumps(
            {"qty": float(f.quantity), "price": float(f.price), "action": f.action},
            sort_keys=True,
        ),
        actual_value_json=json.dumps(
            {"matched": None, "execution_unavailable": True,
             "schwab_order_id": so.order_id, "schwab_limit_price": so.price},
            sort_keys=True,
        ),
    )
    continue
if abs(execution_price - float(f.price)) > price_tolerance:
    dtype = (
        "entry_price_mismatch" if f.action == "entry"
        else "close_price_mismatch"
    )
    _emit(
        conn,
        run_id=run_id,
        discrepancy_type=dtype,
        field_name="price",
        counters=counters,
        dedup_seen=dedup_seen,
        ticker=t.ticker,
        trade_id=t.id,
        fill_id=f.fill_id,
        expected_value_json=json.dumps(
            {"price": float(f.price)}, sort_keys=True,
        ),
        actual_value_json=json.dumps(
            {"price": execution_price,
             "execution_legs": [
                 {"leg_id": leg.leg_id, "price": leg.price,
                  "quantity": leg.quantity, "time": leg.time}
                 for leg in so.executions
             ],
             "schwab_order_id": so.order_id,
             "schwab_limit_price": so.price},
            sort_keys=True,
        ),
        delta_text=(
            f"${execution_price - float(f.price):+.4f} "
            f"(schwab execution minus journal)"
        ),
    )
```

**Notes:**

- **Shape C contract (BINDING; Codex R1 C#1 fix).** The Pass-1 `entry_price_mismatch` / `close_price_mismatch` emit at the inner branch produces `actual_value_json` with EXACTLY the key-set `{"price", "execution_legs", "schwab_order_id", "schwab_limit_price"}` — recognized at the classifier as **Shape C — execution-grain audit-bearing** (see `_EXECUTION_AUDIT_KEYS` constant per §3.2 module touch list). The Shape C predicate at the classifier sits ALONGSIDE the existing Shape A (`{"price"}`-only) + Shape B (full match-tuple) predicates per Sub-bundle C.B spec §4.3.1 — it does NOT replace them; Sub-bundle C.B tier-1 emission contracts stay intact for any caller still emitting Shape A. Audit keys (`execution_legs` + `schwab_order_id` + `schwab_limit_price`) are observational ONLY at the classifier; the `correction_target` field carries `{'price': <execution_price>}` (Shape A-equivalent) so the downstream `apply_tier1_correction` service writes a single-field price-only correction (Sub-bundle C.C contract preserved). Implementer dispatch MUST add a discriminating test: plant a Shape C payload + assert classifier returns `tier=1`, `correction_target={'price': X}`, AND the audit keys are present in the `ClassificationResult.correction_reason` substring (proof they were observed but not actioned).
- **Production-emitter-shape-through-classifier-audit-helper coverage** (Codex R1 M#5 fix). The Path B `unmatched_*_fill` emit with `execution_unavailable=true` sentinel MUST be exercised via discriminating test through the FULL production pipeline: `_emit` → `classify_discrepancy` → `_handle_no_mutation_audit` → `swing journal discrepancy show-ambiguity` CLI rendering. This pre-empts the C.D gate-fix #2 family (synthetic-fixture-vs-production-emitter shape drift). At least 3 tests: (a) classifier returns `tier=2 ambiguity_kind='unsupported'`; (b) audit-helper handles the `field_name='fill_match'` + `actual_value_json.execution_unavailable=true` combination without column-read raise; (c) CLI menu surfaces the operator-actionable choices (mark_unmatched, operator_truth, custom).
- `delta_text` precision widened from `:+.2f` to `:+.4f` per OQ-C inheritance (execution-grain operates at 4dp; cent-precision delta_text would round CVGI's $0.0056 to $0.01 + LION's $0.0001 to $0.00, losing the operator's debugging signal).
- The `execution_unavailable` Path B branch emits the same `unmatched_*_fill` discrepancy_type as the quantity-mismatch case, BUT carries a `"execution_unavailable": True` sentinel in `actual_value_json` that the classifier consumes to emit tier-2 `unsupported` rather than tier-2 multi-record-match. This avoids inventing a new schema-locked discrepancy_type — the existing enum stays unchanged.
- An ALTERNATIVE Path B emit shape (proposed at OQ-A's alternative path, considered + rejected): emit `entry_price_mismatch` with `actual_value_json.execution_unavailable=true`. Rejected because the classifier would interpret that as a Shape B match-tuple miss and may emit tier-2 `unsupported` with a confusing reason string. Routing through `unmatched_*_fill` is more semantically honest ("we found the order but cannot match prices").

### §5.3 Quantity-match comparator switches to execution-grain when available (Codex R1 M#2 fix)

The `if abs(so.quantity - float(f.quantity)) > price_tolerance` at line 658 is the matching-step (find a Schwab order for this journal fill). **V2 changes the matching-step to consume execution-grain quantity when `so.executions` is populated.**

Rationale (Codex R1 M#2 + M#3): Schwab's order envelope distinguishes `quantity` (original order size), `filledQuantity` (actual filled quantity), and `remainingQuantity` (unfilled). For partial-then-canceled orders (`status='CANCELED'` with `filledQuantity > 0`) AND multi-execution-leg orders, the AUTHORITATIVE quantity for journal-fill matching is the SUM OF EXECUTION-LEG QUANTITIES — NOT `order.quantity`. Continuing to use `so.quantity` for matching would silently mis-fail-match against journal partial-fill entries.

**`_resolve_match_quantity` helper (NEW):**

```
def _resolve_match_quantity(so: SchwabOrderResponse) -> float:
    """Return the quantity for journal-fill matching: execution-grain
    sum when executions populated; order-grain fall-back otherwise.

    Codex R1 M#2 fix — preserves match correctness under partial-fill
    scenarios where order.quantity > sum(executions.quantity).
    """
    if so.executions:
        return sum(leg.quantity for leg in so.executions)
    return so.quantity
```

Comparator at line 658 changes:

```
if abs(_resolve_match_quantity(so) - float(f.quantity)) > price_tolerance:
    continue  # not a match
```

**Distinguishing malformed leg totals from legitimate partial fills (Codex R1 M#3 fix):**

A LEGITIMATE partial fill is recognizable via Schwab API contract:

- `order.status` ∈ {`'FILLED'` (fully filled, possibly multi-leg), `'CANCELED'` (partially-then-canceled if `filledQuantity > 0`), `'REPLACED'` (similar)}.
- `sum(executionLegs[].quantity) == order.filledQuantity` (legs sum to broker-reported filled quantity, which may be < `order.quantity` for partial cases).

A MALFORMED leg total is recognizable by:

- `sum(executionLegs[].quantity)` does NOT equal `order.filledQuantity` (drift between activity-collection and order envelope).
- OR `order.filledQuantity == 0` despite `len(executionLegs) > 0` (invalid Schwab response).

**Mapper coherence-check rule:**

- The mapper extracts BOTH `order.quantity` AND `order.filledQuantity` (NEW field `filled_quantity: float | None = None` on `SchwabOrderResponse`); writing-plans phase decides whether to surface `filledQuantity` as a separate field OR derive it implicitly from `sum(legs.quantity)`.
- If executions are present AND `abs(sum(legs.quantity) - order.filledQuantity) < 1e-9`, mapper preserves `executions=[...]` (legitimate, even if partial).
- If executions are present AND `abs(sum(legs.quantity) - order.filledQuantity) >= 1e-9`, mapper logs WARNING + sets `executions=None` (malformed — defensive collapse). Comparator falls through Path B per §6.1.
- Discriminating tests: (a) legitimate partial-fill fixture (`order.quantity=200, filledQuantity=100, legs=[{qty:100}]`) — mapper preserves executions; comparator matches journal `quantity=100`; (b) malformed-leg-total fixture (`order.quantity=100, filledQuantity=100, legs=[{qty:60}, {qty:50}]`) — mapper logs WARNING + sets `executions=None`; comparator falls through Path B.

---

## §6 Open questions for orchestrator triage (locked dispositions)

Per Phase 9/10/12 brainstorm pattern. Each OQ gets a recommendation-with-rationale + binding-vs-deferrable disposition.

### §6.1 OQ-A — Backward-compat fall-through path

**Question:** When `orderActivityCollection` is missing/empty (older orders, exotic order types, sandbox responses, edge cases), comparator + classifier behavior is one of:

- **Path A — Order-level fall-back:** comparator uses `so.price` (order-grain) when `so.executions is None`; classifier emits tier-2 `unsupported` for unmatched-fill discrepancies (V1 LOCK preserved for non-execution-grain data) BUT tier-1 emission for entry_price/close_price discrepancies still consumes order-grain → re-introduces the SAME limit-vs-fill defect the V2 widening exists to close.
- **Path B — Tier-2 `unsupported` emit:** comparator + classifier both treat absence of execution-grain data as "cannot deterministically resolve" → tier-2 with `ambiguity_kind='unsupported'` + explanatory `correction_reason`. Operator dispositions per real broker-statement consultation.

**Recommendation (LOCKED): Path B.** Rationale:

- Preserves Sub-bundle C.B spec §4.4 determinism principle verbatim — when in doubt, tier-2.
- Path A re-introduces the V1 defect family the V2 widening exists to close. Even if "rare edge cases", the operator-locked architectural framing at §1.1 is "execution price IS truth" — falling back to limit price contradicts the framing.
- Operator workflow remains coherent: tier-2 `unsupported` surfaces the discrepancy with explanatory text ("Schwab order found but no execution-grain data available — please disposition manually per broker statement"). Operator's existing tier-2 CLI workflow (Phase 12 C.D `swing journal discrepancy show-ambiguity` + `resolve-ambiguity`) handles this with no additional surface.
- Discriminating tests required for BOTH paths regardless of locked pick — writing-plans phase emits coverage for both so a future operator-decided pivot to Path A is a config flag away (NOT a code rewrite).

**Disposition: BINDING.** Spec §5.2 comparator path emits tier-2 `unsupported` via `unmatched_*_fill` discrepancy_type + `execution_unavailable=true` sentinel in `actual_value_json`.

### §6.2 OQ-B — Multi-leg journal-fill mapping (VWAP vs leg-by-leg audit)

**Question:** When a Schwab order has `len(executionLegs) >= 2` (multi-leg fill), comparator behavior is one of:

- **Path A — VWAP comparator:** single tier-1 emission with weighted-average price as `correction_target.price`.
- **Path B — Leg-by-leg audit surfacing:** emit one discrepancy per leg; classifier auto-redirects tier-2 `multi_partial_vs_consolidated` → tier-1 `split_into_partials` if confidence-threshold met.

**Recommendation (LOCKED): Path A (VWAP) for V1.** Rationale:

- Simpler — single-number comparison matches the existing comparator surface.
- Matches the operator's existing mental model: TOS's "Net Price" column is itself a VWAP aggregate (TOS displays one row per order, not per leg). The journal's single `fills.price` entry is the operator's "memory of the avg fill" — comparing against VWAP is apples-to-apples.
- Per-leg auditing is **V2 candidate** banked at OQ-F. Auto-redirect tier-2 `multi_partial_vs_consolidated` → tier-1 `split_into_partials` requires further analysis (confidence threshold, classifier dispatch state machine, JSON envelope shape for multi-row split, etc.).

**Disposition: BINDING.** V1 = VWAP comparator. V2 candidate = leg-by-leg audit (deferred to follow-up dispatch).

**Adversarial-watch:** if VWAP-vs-journal delta exceeds `price_tolerance` AND legs themselves are widely-distributed, the V1 emit STILL surfaces the tier-1 discrepancy (operator-actionable). The risk of hiding a "Schwab filled outside the spread" anomaly under a VWAP avg is real but secondary — Phase 8 maturity-stage advisories + manual review catch this. Spec V2 candidate enumerates this clearly.

### §6.3 OQ-C — Tolerance window for execution-grain

**Question:** With execution-leg data at 4dp precision, retain `price_tolerance=0.01` (cent) OR tighten to `0.001` (mil)?

**Recommendation (LOCKED): retain `price_tolerance=0.01`.** Rationale:

- Empirical evidence at hand (2 historical correction chains):
  - CVGI: `abs($5.23 - $5.2244) = $0.0056` — under cent tolerance, NO discrepancy emit. **Correct behavior** (sub-cent rounding tolerated).
  - LION: `abs($12.70 - $12.6999) = $0.0001` — under cent tolerance, NO discrepancy emit. **Correct behavior** (sub-cent rounding tolerated).
- Tightening to `0.001` would surface BOTH cases as discrepancies — false-positives from broker-side sub-cent rounding noise. Operator workflow burden increases without information gain.
- The V1 `price_tolerance=0.01` was already operator-tuned (Phase 11 Sub-bundle B); execution-grain data does not change the operator's actionable-threshold preference.
- Cent-precision is appropriate for the journal's data-entry grain (operator types decimals to 2dp; sub-cent precision is broker-internal).

**Adversarial-watch:** if a future operator decides to widen the tolerance (e.g., to `$0.02` for slippage tolerance), the parameter is already config-surfaced via `cfg.integrations.schwab.reconciliation.price_tolerance` (Phase 11 Sub-bundle B). V2 widening does not need to expose new config; just consume existing.

**Disposition: BINDING.** `price_tolerance=0.01` retained.

### §6.4 OQ-D — FIRED-stop handling

**Question:** When a stop order FILLS (status transitions `WORKING` → `FILLED`), comparator behavior is one of:

- **Path A — Mirror entry-fill discipline:** the FIRED stop's fill record uses `executionLegs[].price` for `close_price_mismatch` evaluation (same VWAP comparator path as buy/sell fills).
- **Path B — Defer / keep stop-trigger comparison:** continue to compare on `order.stopPrice` for FIRED stops; do not switch to execution-leg.

**Recommendation (LOCKED): Path A (mirror entry-fill discipline).** Rationale:

- When a stop FIRES, the journal's "exit fill price" is what the operator records — this IS an execution price, not a trigger. Schwab's `order.price` for a FIRED STOP order might be the stop trigger (still the original trigger value) OR the actual execution price (broker-side post-fill update); the API is not deterministic across SDK versions per OQ-E.
- `executionLegs[].price` for a FIRED stop is the ACTUAL execution price (slippage from trigger included). This is what the journal SHOULD compare against.
- Without this, a FIRED stop with trigger=$5.00 but executed-at-$4.95 (gap-down) would either silently NOT emit (Path B comparing $5.00 vs $4.95 trigger-vs-execution mismatch) OR mis-emit `close_price_mismatch` against the trigger. Neither is operator-actionable.
- `stop_mismatch` for WORKING stops still uses `order.stopPrice` per §1.2 — only the FIRED transition switches paths.

**Discriminating test:** plant a Schwab fixture with `order.status='FILLED'`, `order.orderType='STOP'`, `order.price=5.00`, `executionLegs=[{price:4.95, quantity:100}]`; assert comparator computes `execution_price=4.95` + emits `close_price_mismatch` if journal stored `5.00`.

**Adversarial-watch:** A subtle case is the STOP-LIMIT order type. When a STOP-LIMIT fires, the limit at which it can fill may be different from the trigger AND from the actual execution. The mapper extracts `executionLegs[].price` uniformly regardless of order_type — this is the right behavior (executions are executions). The order_type field stays on the `SchwabOrderResponse` for audit observability only.

**Disposition: BINDING.** Path A. Spec §5.2 comparator switch applies uniformly to all FILLED orders regardless of `order_type`.

### §6.5 OQ-E — Schwab API field-shape verification (cassette-recording prerequisite)

**Question:** Schwab API spec at `reference/schwab-api/account-specification.md:1791-1792` documents the `executionLegs[]` shape. Verify field-shape reliability empirically across order types (LMT, MKT, STOP, STOP_LIMIT).

**Recommendation (LOCKED): REQUIRE cassette-recording in operator-paired session BEFORE executing-plans dispatch.**

Rationale:

- Operator's production order history is predominantly LIMIT BUY/SELL. Coverage across MKT, STOP, STOP_LIMIT is unverified empirically.
- The mapper's defensive parsing handles missing/malformed fields, but a CASSETTE-driven test exercises against actual production wire format — pre-empting the C.D gate-fix #2 family (synthetic-fixture-vs-production-emitter shape drift).
- Cassette-recording IS Schwab-specific work (existing Schwab gotcha "Schwab cassette runbook is V2 PLANNED — V1 ships mock-based tests only" — this bundle CAN keep the V1 posture, but cassettes are STRONGLY RECOMMENDED for the new code).

**Order types requiring cassette coverage at minimum:**

1. **LIMIT BUY** (operator's predominant; CVGI shape).
2. **LIMIT SELL** (operator's predominant; LION exit shape).
3. **STOP FIRED** (FIRED stop with executionLegs populated; tests OQ-D Path A).
4. **MARKET BUY** (rare; verify executionLegs surface for the MKT-typed fills).

Stretch: STOP_LIMIT FIRED (rare; verify dual-tier price-vs-trigger field shape).

**Cassette-recording session scope (writing-plans phase trigger):**

- Operator runs `swing schwab fetch --orders --environment production --days 30` against their production tokens (refresh-token TTL window permitting).
- Save sanitized cassette under `tests/integrations/cassettes/schwab/orders-fired-stop.yaml` (etc.) — sanitize accountNumber + accountHash + Authorization header via pytest-recording filter list.
- Writing-plans phase produces the cassette runbook + sanitization filter spec.

**Codex R1 M#7 LOCK — decision authority + minimum shippable fallback:**

- **Decision authority:** the **operator** (during writing-plans Codex review handoff to operator gate) decides between (a) cassette-required and (b) mocked-only fallback. Writing-plans phase frames the choice with risk-table; orchestrator routes the explicit operator decision into the executing-plans dispatch brief §0 LOCK.
- **Default (in absence of operator preference):** cassette-REQUIRED for Sub-bundle 1 ship. Rationale: avoids C.D gate-fix #2 family (synthetic-fixture-vs-production-emitter shape drift) which already cost orchestrator-inline fixes 3 times in Phase 12 arc.
- **Fallback (when operator selects mocked-only):** Sub-bundle 1 ships with mocked tests + explicit RISK ACCEPTANCE banked at `docs/phase3e-todo.md` ("Schwab cassette recording session — RISK ACCEPTED at <date>; observed-shape-drift mitigation is operator-witnessed gate review of first production reconciliation_run #N after Sub-bundle 1 ships"). Operator-witnessed gate at Sub-bundle 1 ship-time becomes the de-facto shape-drift detector. Subsequent V2 cassette dispatch removes the risk.
- **Hard gate (regardless of cassette state):** the operator-witnessed gate at Sub-bundle 1 ship MUST exercise reconciliation against the operator's actual production Schwab data — not a dev sandbox — so any field-shape drift would surface in real reconciliation_run output BEFORE the bundle is marked closed. The C.D gate's S2/S3a/S3b/S4a/S4b/S5/S6a/S6b/S7 pattern (Phase 12 Sub-sub-bundle C.D ship 2026-05-17) provides the precedent for the gate surfaces this dispatch will need.

**Disposition: DEFERRABLE to writing-plans phase (operator-decision-routed; not orchestrator-decided).** This brainstorm enumerates the order types + locks the decision rule; writing-plans phase produces the runbook and routes the operator's pick.

### §6.6 OQ-F — Tier-1 auto-redirect from tier-2 `multi_partial_vs_consolidated`

**Question:** With execution-grain data, when N Schwab orders cumulatively sum to journal qty AND each order's VWAP aligns with journal price within tolerance, classifier could auto-emit tier-1 instead of tier-2 `multi_partial_vs_consolidated`. Ship in V1 or defer V2?

**Recommendation (LOCKED): DEFER to V2 follow-up dispatch.** Rationale:

- Auto-redirect requires further analysis:
  - **Confidence threshold:** does it require ALL N VWAPs to match within tolerance? Or does it tolerate one outlier? Per spec §4.4 determinism principle, "all-match-within-tolerance" is the only defensible threshold — but this means a single outlier-leg flips the classifier to tier-2.
  - **Cascade to classifier dispatch states:** introducing auto-redirect from tier-2 `multi_partial_vs_consolidated` requires a new classifier dispatch state (e.g., tier-1 `split_into_partials_auto_correct`) + a new auto-correct service handler + a new test surface + a new operator-facing CLI output.
  - **Operator-decided UX:** the operator's current workflow handles tier-2 `multi_partial_vs_consolidated` via CLI menu (`split_into_partials` choice with operator-supplied `--custom-value`). Auto-redirect short-circuits this — operator may PREFER the manual review for multi-leg cases as a sanity check.
- V1 mapper widening LIFTS Pass-2-tier-1-FORBIDDEN ONLY for single-leg matched-tuple cases (the most common). Multi-leg LIFT is V2 scope.

**Disposition: DEFERRABLE (V2 follow-up dispatch candidate).** Spec banks this at the V2 candidates list (§9.2) + does NOT design it.

### §6.7 OQ-G — Historical audit-row leave-as-is (operator-decided)

**Question:** The 6 historical `reconciliation_corrections` rows (correction_ids 1-6) recorded V1's WRONG `schwab_said_value_json` (limit-prices not execution-prices). Leave-as-is + document, OR rewrite retroactively?

**Operator decision: leave-as-is + document.** Brainstorm enumerates the 2 rejected alternatives:

- **Alternative #1: UPDATE `schwab_said_value_json` retroactively.** Rejected because:
  - Violates §1.4 lock (audit-trail integrity preserved).
  - Requires re-fetching historical Schwab orders within refresh-token-TTL constraints (7-day window; some historical orders may already be past the TTL).
  - Executing-plans Codex would catch as a deferred-truth-rewrite violation (audit-row stability is a binding invariant per Phase 6 forensic-honesty discipline).
  - Even if rewritten, the `correction_set_id` chain heads (correction_ids 4+6) already record correct operator-truth values via `operator_truth_value_json` — the WRONG intermediate "Schwab said" rows are honest about what V1 emitted.
- **Alternative #2: DELETE-and-resimulate.** Rejected because:
  - Same audit-trail violation as Alternative #1, plus loses the forensic trail of "V1 saw X; operator-overrode to Y".
  - Resimulation under V2 mapper would emit DIFFERENT discrepancies (the CVGI + LION cases would emit NO discrepancies under V2). The historical correction chains would have NO antecedent rows to attach to — an architectural mismatch.

**Disposition: BINDING (operator-decided).** Spec §10.3 documents the historical chains' forensic-honesty disposition.

---

## §7 T-B.7 `/schwab/status` web counterpart

### §7.1 Route + view-model + template

**Route** (NEW in `swing/web/routes/schwab.py`):

- `GET /schwab/status` — read-only; query-param `?environment=production` or `?environment=sandbox` OVERRIDES the effective cfg default. **Codex R1 M#6 LOCK**: when no query-param is supplied, the route sources `effective_environment = apply_overrides(cfg).integrations.schwab.environment` — mirrors the `swing schwab status` CLI default (see `swing/cli_schwab.py:1421-1441`) so an operator configured for sandbox does NOT see production state by accident. A no-arg URL `/schwab/status` therefore renders whichever environment the operator's cfg/env-var cascade resolves to.
- HTMX-friendly: HX-Request header processing inherited from app-level middleware; no form POST in V1.
- Inherits `apply_overrides(cfg)` discipline at the route handler (Sub-bundle B forward-binding lesson #6) — without it, cfg-tier credentials don't resolve through this endpoint AND the default environment selection breaks.

**View-model** (NEW class `SchwabStatusVM` in `swing/web/view_models/schwab.py`):

Fields (mirror CLI `swing schwab status` output 1:1):

- `environment: Literal['production', 'sandbox']`
- `state: Literal['CONFIGURED', 'PROVISIONAL', 'NOT_CONFIGURED']`
- `tokens_db_path: str` (display-only, masked if path contains user-profile prefix)
- `refresh_token_expires_at: str | None` (ISO 8601; None if NOT_CONFIGURED)
- `refresh_token_days_remaining: int | None`
- `refresh_token_severity: Literal['ok', 'warn', 'error']` — 'warn' if ≤24h; 'error' if ≤2h; per Sub-bundle D gotcha
- `recent_calls: list[SchwabCallSummary]` — last 5 `schwab_api_calls` rows (status + endpoint + http_status + started_ts; redacted error_message excerpt)
- `last_success_at: str | None`
- `last_failure_at: str | None`
- `degraded_banner_active: bool` — mirrors briefing.md "Schwab integration: degraded" predicate per spec §3.4.4 (most-recent `schwab_api_calls.status != 'success'`)
- `unresolved_material_discrepancies_count: int` — required for Phase 10 T-E.3 base-layout VM banner inheritance
- `nav_back_to_config_url: str = "/config"` — link back

**Template** (NEW `swing/web/templates/schwab_status.html.j2`):

- `{% extends "base.html.j2" %}`.
- Renders state banner (color-coded green/yellow/red per `state`).
- Renders refresh-token TTL countdown with severity styling.
- Renders recent-calls table.
- Renders link to `/schwab/setup` ("Re-authenticate") if state is PROVISIONAL or NOT_CONFIGURED OR if `refresh_token_severity != 'ok'`.
- Inherits Phase 10 unresolved-material-discrepancies banner from `base.html.j2` (no special handling required; VM populates the field).

### §7.2 Nav-link discoverability

Add link to `/schwab/status` from `/config` page's "External integrations" section — mirrors the Sub-bundle B orchestrator-inline gate-fix `7b75d4a` precedent that added `/schwab/setup` link. Single anchor tag; minimal template diff.

### §7.3 `/schwab/setup` HX-Redirect retargeting

Once T-B.7 lands, the `POST /schwab/setup` success path retargets from `HX-Redirect: /config?schwab_setup=ok` to `HX-Redirect: /schwab/status`. This means:

- Updating ONE line in `swing/web/routes/schwab.py` POST handler.
- Updating ONE test in `tests/web/test_routes/test_schwab_setup.py` (or wherever the redirect assertion lives).
- HX-Redirect target route registered check (Phase 6 I3 gotcha) — covered by route registration in T-B.7.
- Existing `/config?schwab_setup=ok` query-param consumer pattern: **RETAINED as a passive no-op landing for ONE release window** (Codex R1 m#2 fix — safer than aggressive deletion when stale browser tabs/bookmarks may still send the param). The `/config` route already tolerates unknown query-params; the consumer that surfaces "✓ Schwab setup OK" message can stay or be silently dropped — writing-plans phase decides. Hard removal is banked as a follow-up housekeeping V2 task in `docs/phase3e-todo.md` after one release cycle has demonstrated zero stale-tab traffic.

### §7.4 OQ-D applicability — does web status need FIRED-stop awareness?

`/schwab/status` is READ-ONLY V1 — no reconciliation actions taken from this page. Recent-calls summary shows raw API call status (success / auth_failed / rate_limited / error) which is order-type-agnostic. FIRED-stop handling is a reconciliation-comparator concern (§5.2) — not a status-page concern.

**Lock:** `/schwab/status` inherits CLI semantics 1:1; no special FIRED-stop handling.

### §7.5 HTMX trinity preservation

- **HX-Request propagation:** N/A — V1 is read-only GET; no embedded forms.
- **HX-Redirect-vs-303-swap:** N/A — V1 is read-only GET; no POST → redirect.
- **HX-Redirect-target-unrouted:** the `/schwab/setup` retarget to `/schwab/status` MUST verify target route is registered (Phase 6 I3 gotcha; writing-plans adds discriminating test asserting `/schwab/status` exists in app routes).

### §7.6 Sandbox environment branch in `/schwab/status`

The status page handles `?environment=sandbox` by:

- Loading tokens from `schwab-tokens.sandbox.db` (not production).
- Mirroring CLI's `swing schwab status --environment sandbox` output verbatim.
- Recent-calls table filters to `schwab_api_calls.environment = 'sandbox'`.
- No domain-row writes (consistent with sandbox short-circuit gating; the status page is READ-ONLY anyway).

A simple environment-switcher link on the page (`?environment=production` / `?environment=sandbox`) gives the operator a UX toggle without leaving the page.

---

## §8 Housekeeping micro-fixes

### §8.1 CLAUDE.md status-line CVGI date attribution

The brief §2.6 cites a typo `2026-04-27` → `2026-05-08` for CVGI's entry date attribution. **Verification at brainstorm time:** `grep -n "2026-04-27" CLAUDE.md` returns ZERO matches. Two possibilities:

1. The typo was already silently corrected upstream of dispatch (e.g., during the 4 NEW C.D-arc lesson promotions at `4bab6ee`).
2. The typo is stated in a different form (e.g., relative date attribution, or in a slightly different sentence).

**Disposition for writing-plans:**

- **Step 1:** writing-plans phase verifies presence by reviewing `git log --all --oneline -- CLAUDE.md | head -30` for any commit in the C.D + post-housekeeping window mentioning the CVGI entry-date attribution. If a date discrepancy persists, locate via more targeted grep (e.g., search for `CVGI` within 200 chars of `2026-04` substring).
- **Step 2:** if confirmed typo: edit CLAUDE.md to replace the offending date attribution with `2026-05-08`.
- **Step 3:** if no typo present: writing-plans no-ops the §8.1 task and notes the corrective-already-applied state in the return report.

The spec deliverable is **the diff intent + the verification step**; writing-plans + executing-plans produce the actual edit (or no-op).

### §8.2 CLAUDE.md `Pass-2-tier-1-FORBIDDEN` gotcha amendment

Current state (per CLAUDE.md): the gotcha was AMENDED at commit `4bab6ee` to cover BOTH Pass-1 AND Pass-2 limit-vs-fill families. The current text describes V1 LIMIT-vs-EXECUTION defect family AS UNRESOLVED at V1.

V2 amendment adds a top section "V2 RESOLVED" referencing this spec + the V2 mapper widening dispatch:

```
**V2 RESOLVED (<date-of-Sub-bundle-1-ship>, post-Phase-12):** the Pass-1 + Pass-2 limit-vs-fill defect family
is RESOLVED by the V2 mapper widening (`swing/integrations/schwab/mappers.py` extension to
surface `orderActivityCollection[].executionLegs[]` per `docs/superpowers/specs/2026-05-17-
schwab-mapper-execution-grain-widening-design.md`). The mapper now exposes execution-grain
prices; the comparator at `swing/trades/schwab_reconciliation.py:693` compares execution
VWAP not order limit; the classifier conditionally LIFTS Pass-2-tier-1-FORBIDDEN for
single-leg matched-tuple cases with execution-grain data available. **Historical V1 context
retained below for archaeology**: ...
```

The V1 historical context is preserved verbatim — operators reading the gotcha understand WHY the architecture changed.

Writing-plans phase produces the exact edit; executing-plans phase commits it at Sub-bundle 1 (alongside the mapper landing) for atomic correctness — the gotcha amendment lands the same commit as the V2 code so a `git log -p CLAUDE.md` shows the architectural transition cleanly.

### §8.3 Historical audit-row leave-as-is documentation (OQ-G)

**`docs/phase3e-todo.md` entry** (NEW; folded into Sub-bundle 3 housekeeping or 1):

```markdown
### Historical `reconciliation_corrections` rows (correction_ids 1-6) — V1 limit-vs-fill forensic record

Recorded 2026-05-17 (post-Phase-12 mapper-widening brainstorm; operator-decided OQ-G leave-as-is).

The 6 historical `reconciliation_corrections` rows recorded by Phase 12 Sub-sub-bundle C.C
(correction_ids 1-2 from T-C.11 test) + Sub-sub-bundle C.D (correction_ids 3-4 CVGI; 5-6
LION; chain heads at 4 + 6 carry operator-truth values via `operator_truth_value_json`)
recorded V1's WRONG `schwab_said_value_json` (order-limit price, NOT execution price). These
rows are PRESERVED AS-IS per audit-trail integrity invariant (Phase 6 forensic-honesty
discipline + spec §1.4 operator lock).

**Why preserved:** the rows are FORENSIC RECORDS of what V1 saw and emitted. The chain
heads (correction_ids 4 + 6) record correct operator-truth values; future readers can chase
the chain and see "V1 said X; operator overrode to Y" — exactly the audit-trail this
project's `reconciliation_corrections` table exists to provide.

**Why NOT rewriting:** would violate audit-trail integrity invariant; requires re-fetching
historical Schwab orders within refresh-token-TTL constraints; resimulation under V2 mapper
would emit DIFFERENT discrepancies (the V2 cases emit NONE for CVGI + LION).

**Forward-looking:** any new reconciliation_corrections rows emitted from V2-mapper-widening-ship
forward (Sub-bundle 1 ship date; filled at executing-plans phase) will carry EXECUTION-grain
prices in `schwab_said_value_json`.

**Operator-facing surfacing (Codex R1 M#8 fix — prevents future operator confusion when inspecting historical chains):**

To avoid surprise when an operator runs `swing journal discrepancy show-correction <id>` against a V1-emitted historical row OR reads the audit log, Sub-bundle 1 ALSO ships a small CLI-help-text addendum on the `show-correction` subcommand (or equivalent operator-facing surface; writing-plans phase selects the exact insertion point):

```
Note: correction_ids 1-6 (emitted 2026-05-16 + 2026-05-17 prior to V2 mapper widening) carry
ORDER-grain prices in schwab_said_value_json (V1 mapper read order.price; LIMIT for buy/sell,
trigger for stops). The chain heads (correction_ids 4, 6) carry CORRECT operator-truth values
via operator_truth_value_json. From correction_id 7 onward, schwab_said_value_json reflects
EXECUTION-grain prices per the V2 mapper widening at
docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md.
```

The exact correction_id boundary (7) is filled at executing-plans phase against production state at ship-time. NO row mutations involved — purely a documentation surface; preserves §1.4 audit-trail integrity lock.
```

**Rationale for `docs/phase3e-todo.md` location:** the project uses this file for cross-phase backlog + retention notes. The historical-leave-as-is entry is a forensic-honesty note that future operators may want to surface when investigating the chain heads.

### §8.4 Spec deliverable scope

Spec §8 enumerates the 3 housekeeping micro-fixes + their intended landing surfaces. Writing-plans phase produces per-edit acceptance criteria + executing-plans phase commits them. NO actual edits to CLAUDE.md / phase3e-todo.md are produced in the spec.

---

## §9 Sub-bundle decomposition recommendation

### §9.1 Tentative shape (writing-plans refines)

Three sub-bundles, with dispatch ordering and cross-bundle dependencies:

#### Sub-bundle 1 — V2 mapper widening + classifier consumer + comparator + back-compat fall-through (ARCHITECTURAL HEADLINE)

**Scope:**

- `SchwabExecutionLeg` dataclass (NEW).
- `SchwabOrderResponse.executions` field extension.
- `map_orders_to_fill_candidates` body extension.
- `_compute_execution_price` comparator helper.
- `run_schwab_reconciliation` comparator path switch (Path B per OQ-A).
- `_classify_unmatched_fill_shared` + `_classify_entry_price_mismatch` classifier-branch addition (LIFT Pass-2-tier-1-FORBIDDEN for execution-grain matched-tuple).
- `_compute_execution_price` discriminating tests (single-leg + multi-leg VWAP + None-fall-through + edge cases).
- CVGI + LION end-to-end discriminating walkthrough tests (§10).
- Cassette-recording prerequisite per OQ-E (operator-paired session at writing-plans phase).
- CLAUDE.md gotcha amendment for Pass-2-tier-1-FORBIDDEN V2-RESOLVED (per §8.2).

**Expected dispatch:** standalone executing-plans implementer dispatch; 3-5 Codex rounds expected (architectural; convergent chain shape per Sub-bundle C precedent).

**Projected test delta:** +30-60 fast tests (mapper extension + dataclass + helper + comparator + classifier + walkthroughs).

#### Sub-bundle 2 — T-B.7 `/schwab/status` web counterpart

**Scope:**

- New `GET /schwab/status` route.
- New `SchwabStatusVM` view-model.
- New `swing/web/templates/schwab_status.html.j2` template.
- Nav-link addition to `/config` page.
- `POST /schwab/setup` `HX-Redirect` retarget from `/config?schwab_setup=ok` to `/schwab/status`.
- HTMX-trinity discipline (Phase 6 I3 target-unrouted regression test).
- Sandbox/production environment switcher.

**Expected dispatch:** standalone executing-plans implementer dispatch; can be PARALLELIZED with Sub-bundle 1 (no shared modules). 2-3 Codex rounds expected (read-only web; minimal logic).

**Projected test delta:** +15-30 fast tests (route + VM + template smoke + nav-link + HX-Redirect target route registration check).

#### Sub-bundle 3 — Housekeeping (optionally folded into Sub-bundle 1)

**Scope:**

- CLAUDE.md status-line CVGI date verification + correction-if-needed (§8.1).
- `docs/phase3e-todo.md` leave-as-is forensic-record entry (§8.3).
- Pass-2-tier-1-FORBIDDEN amendment may FOLD into Sub-bundle 1 ship for atomic correctness (per §8.2).

**Expected dispatch:** smallest; can be folded into Sub-bundle 1 OR run as docs-only commit. Writing-plans phase decides — current recommendation is **fold into Sub-bundle 1** (the gotcha amendment ships atomically with the code it describes; the phase3e-todo entry can ship in either; the CVGI date verification can ship in either).

**Projected test delta:** 0 fast tests (docs-only).

### §9.2 V2 follow-up candidates (banked; NOT this dispatch)

The brainstorm explicitly defers (per §1.6 + OQ-F):

- **Multi-leg tier-1 auto-redirect** (`split_into_partials` auto-emit when classifier confidence is high). Requires cascade analysis: confidence threshold, classifier dispatch state for `tier-1-multi-leg-split`, auto-correct service handler `_apply_split_into_partials`, CLI surface, operator-decided UX. Future operator-paired dispatch.
- **Per-leg audit surfacing for tier-2** (when VWAP-vs-journal delta is OUTSIDE tolerance, additionally surface per-leg discrepancies so operator sees "Schwab filled outside spread" anomalies). Currently V1 ships one tier-1 emit per outside-tolerance VWAP comparison; per-leg detail lives in `actual_value_json.execution_legs` (audit-only).
- **Fill auto-population at trade-entry** (the broader sub-bundle banked at Sub-bundle C §1.6). Out of scope here.
- **Web Tier-2 discrepancy-resolution surface** (Sub-bundle C plan §I.3 V2). NOT this dispatch.
- **Schwab cassette runbook** (currently V2-PLANNED per Schwab gotcha). May ship as part of Sub-bundle 1 cassette-recording session OR remain V2 banked depending on writing-plans phase decision.

### §9.3 Cross-bundle dependency graph

```
                   (Sub-bundle 1)                  (Sub-bundle 2)
                ┌─────────────────────┐          ┌──────────────────┐
   main HEAD ─→ │ V2 mapper widening  │          │ /schwab/status   │
                │ + classifier + comp │          │ web counterpart  │
                │ + comparator        │          │                  │
                │ + gotcha amendment  │          │                  │
                └──────────┬──────────┘          └────────┬─────────┘
                           │                              │
                           └──────────┐    ┌──────────────┘
                                      ▼    ▼
                              (Sub-bundle 3, optional)
                              ┌─────────────────────┐
                              │ phase3e-todo entry  │
                              │ + CVGI date verify  │
                              └─────────────────────┘
                                       │
                                       ▼
                                  Bundle CLOSED
```

**Sub-bundle 1 and 2 are PARALLELIZABLE** — no shared modules, no shared schema (schema unchanged), no shared test surfaces (except the global Phase 10 banner discipline which both inherit independently). Operator can dispatch them in either order or simultaneously. Recommended: dispatch **Sub-bundle 1 FIRST** (architectural headline; longer; higher Codex round count) so Sub-bundle 2 can land any post-merge polish observations.

**Sub-bundle 3 ships last** (or folded into 1).

### §9.4 Expected duration estimates

- Sub-bundle 1 writing-plans + executing-plans: ~6-12hr wall-clock (mapper extension + dataclass + helper + comparator + classifier + 30-60 tests + cassette session if pursued + 3-5 Codex rounds).
- Sub-bundle 2 writing-plans + executing-plans: ~2-4hr wall-clock (read-only web; 15-30 tests + 2-3 Codex rounds).
- Sub-bundle 3 writing-plans + executing-plans (if standalone): ~1hr wall-clock (docs-only; 0 tests; 1 Codex round).

Total bundle estimate: ~9-17hr wall-clock spread across operator-paired sessions for cassette recording + executing-plans dispatches.

---

## §10 Discriminating examples — CVGI + LION end-to-end walkthroughs (BINDING)

This section walks the 2 historical correction chains through the V2 mapper + comparator + classifier, asserting expected behavior. These walkthroughs are BINDING test acceptance criteria for writing-plans Sub-bundle 1.

### §10.1 CVGI walkthrough (fill_id=9; correction chain 3+4)

**Journal state (current):**

- `fills.fill_id=9`: ticker=CVGI, action='entry', quantity=100.0, price=$5.23 (operator-typed-from-memory; corrected to $5.23 post-tier-3-override at correction_id=4 chain head).
- Trade open, lock-time risk parameters intact.

**Schwab order (Sub-bundle 1 V2 mapper output):**

- order_id='<schwab-id-9>'
- status='FILLED'
- instrument_symbol='CVGI'
- instruction='BUY'
- quantity=100.0
- order_type='LIMIT'
- price=$5.30 (LIMIT — V1 mapper value; V2 still extracts as fall-back)
- executions=[`SchwabExecutionLeg(leg_id=0, price=5.2244, quantity=100.0, mismarked_quantity=None, instrument_id=<id>, time='<iso>')`]

**Mapper expected output:** `SchwabOrderResponse(..., price=5.30, executions=[SchwabExecutionLeg(..., price=5.2244, quantity=100, ...)])`.

**Comparator expected output (`run_schwab_reconciliation`):**

1. Find Schwab order matching (ticker='CVGI', qty=100) — match.
2. `_compute_execution_price(so)` = `so.executions[0].price` (single-leg) = `5.2244`.
3. `abs(5.2244 - 5.23) = 0.0056`.
4. `0.0056 < price_tolerance (0.01)` — **NO discrepancy emit**.

**Classifier expected output:** N/A (no discrepancy emitted at all; nothing to classify; Shape C predicate at classifier never invoked because comparator's tolerance gate short-circuits before emit).

**Net result:** CVGI's fill silently passes reconciliation. NO tier-1 wrong-correct ($5.30) emitted. NO operator workflow burden. NO new `reconciliation_corrections` rows.

**Contrast with V1 behavior:** V1 comparator emitted `entry_price_mismatch` with `actual_value_json={"price": 5.30}`; classifier emitted tier-1; auto-correct service wrote fills.price=$5.30 (WRONG); operator pushback caught + tier-3 override-back to $5.23. **The entire correction-chain-3-to-4 lifecycle is eliminated under V2.**

### §10.2 LION walkthrough (fill_id=15; correction chain 5+6)

**Journal state (current):**

- `fills.fill_id=15`: ticker=LION, action='entry', quantity=100.0, price=$12.70 (operator-typed-from-memory; corrected to $12.70 post-tier-3-override at correction_id=6 chain head).

**Schwab order (V2 mapper output):**

- order_id='<schwab-id-15>'
- status='FILLED'
- instrument_symbol='LION'
- instruction='BUY'
- quantity=100.0
- order_type='LIMIT'
- price=$12.75 (LIMIT — fall-back)
- executions=[`SchwabExecutionLeg(leg_id=0, price=12.6999, quantity=100.0, ...)`]

**Comparator expected output:**

1. Find Schwab order matching (ticker='LION', qty=100) — match.
2. `_compute_execution_price(so)` = `12.6999`.
3. `abs(12.6999 - 12.70) = 0.0001`.
4. `0.0001 < 0.01` — **NO discrepancy emit**.

**Net result:** LION's fill silently passes reconciliation. NO tier-1 wrong-correct ($12.75) emitted. NO operator workflow burden.

**Contrast with V1 behavior:** V1 comparator emitted `entry_price_mismatch`; classifier emitted tier-1; auto-correct wrote fills.price=$12.75 (WRONG); operator override-back to $12.70 via correction_id=6 chain head. **Entire correction-chain-5-to-6 lifecycle eliminated under V2.**

### §10.3 Hypothetical legitimate-discrepancy walkthrough

To prove V2 still catches legitimate discrepancies, walk a synthetic example:

**Journal state:** `fills.fill_id=99`: ticker=ACME, quantity=100, price=$10.00.
**Schwab order:** executions=[`SchwabExecutionLeg(price=10.25, quantity=100, ...)`].
**Comparator:**

1. Match (ACME, 100).
2. `execution_price = 10.25`.
3. `abs(10.25 - 10.00) = 0.25`.
4. `0.25 > 0.01` — emit `entry_price_mismatch` with `actual_value_json={"price": 10.25, "execution_legs": [{leg_id: 0, price: 10.25, quantity: 100, time: ...}], "schwab_order_id": "...", "schwab_limit_price": <limit>}`.

**Classifier:** receives **Shape C** payload (Codex R1 C#1 fix — the key-set is `{"price", "execution_legs", "schwab_order_id", "schwab_limit_price"}` = `{"price"} | _EXECUTION_AUDIT_KEYS`; classifier's Shape C predicate at `_classify_entry_price_mismatch` matches; emits tier-1 with `correction_target={'price': 10.25}` — audit keys observational only); LEGITIMATE auto-correct.

**Net result:** legitimate operator typo ($10.00 typed, actually filled at $10.25) is correctly auto-corrected by V2. Tier-1 emission is now SAFE because it's grounded in execution-grain data.

### §10.4 Hypothetical multi-leg walkthrough (VWAP)

**Journal state:** `fills.fill_id=100`: ticker=XYZ, quantity=100, price=$10.10.
**Schwab order:** executions=[`SchwabExecutionLeg(leg_id=0, price=10.00, quantity=50)`, `SchwabExecutionLeg(leg_id=1, price=10.20, quantity=50)`].
**Comparator:**

1. Match (XYZ, 100) (so.quantity = 100 = sum of legs).
2. `execution_price = (10.00*50 + 10.20*50) / 100 = $10.10`.
3. `abs(10.10 - 10.10) = 0.0`.
4. `0.0 < 0.01` — **NO discrepancy emit**.

Variant: journal `fills.fill_id=101`: price=$10.00 (operator typed first-leg price).
**Comparator:**

1. Match.
2. `execution_price = $10.10` (VWAP).
3. `abs(10.10 - 10.00) = 0.10` > `0.01` — emit `entry_price_mismatch` with `actual_value_json.price=10.10` + `execution_legs=[{leg_id:0, price:10.00, qty:50, ...}, {leg_id:1, price:10.20, qty:50, ...}]`.

**Classifier:** **Shape C** payload (key-set `{"price", "execution_legs", "schwab_order_id", "schwab_limit_price"}`); emits tier-1 with `correction_target={'price': 10.10}` (LEGITIMATE auto-correct).

**Net result:** multi-leg VWAP comparison correctly catches operator's "ignored split fill" typo. Note: Pass-1 multi-leg tier-1 IS allowed under §1.5 lock — the V1 deferral applies only to Pass-2 (`unmatched_*_fill`) multi-Schwab-order summing-to-journal-qty cases.

### §10.5 Hypothetical execution-unavailable walkthrough (OQ-A Path B)

**Journal state:** `fills.fill_id=102`: ticker=ZZZ, quantity=100, price=$8.00.
**Schwab order:** `orderActivityCollection=None` (no execution data — older order OR sandbox response).
**Mapper output:** `SchwabOrderResponse(..., price=$8.00, executions=None)`.
**Comparator:**

1. Match (ZZZ, 100).
2. `_compute_execution_price(so) = None`.
3. Path B: emit `unmatched_open_fill` with `actual_value_json={"matched": None, "execution_unavailable": True, "schwab_order_id": "...", "schwab_limit_price": 8.00}`.

**Classifier (`_classify_unmatched_fill_shared`):** sees `actual_value_json.execution_unavailable == True` sentinel; emits tier-2 with `ambiguity_kind='unsupported'` + `correction_reason='unmatched_open_fill: Schwab order found (order_id=..., limit_price=$8.00) but no execution-grain data available; please disposition manually per broker statement'`.

**Net result:** operator sees tier-2 discrepancy with clear reason; uses tier-2 CLI menu (`mark_unmatched` / `operator_truth` / etc.) per Phase 12 Sub-sub-bundle C.D workflow.

### §10.6 Hypothetical FIRED-stop walkthrough (OQ-D)

**Journal state:** `fills.fill_id=103`: ticker=WWW, action='exit', quantity=100, price=$4.95 (operator records actual exit fill at $4.95 after stop fired with $0.05 slippage from trigger).
**Schwab order:**

- order_id='<schwab-id-stop>'
- status='FILLED' (stop fired)
- order_type='STOP'
- price=$5.00 (the stop trigger — `order.price` field for STOP-family)
- executions=[`SchwabExecutionLeg(price=4.95, quantity=100, ...)`]

**Mapper output:** `SchwabOrderResponse(..., price=5.00, executions=[SchwabExecutionLeg(price=4.95, quantity=100, ...)])`.

**Comparator:**

1. Match (WWW, 100) — found.
2. `_compute_execution_price(so) = $4.95`.
3. `abs(4.95 - 4.95) = 0.0` — **NO discrepancy emit**.

**Net result:** FIRED stop correctly compared on EXECUTION price (not trigger). Slippage absorbed correctly because operator's journal-side $4.95 matches Schwab's execution $4.95.

**Variant:** journal `fills.fill_id=104`: price=$5.00 (operator records the TRIGGER, not actual execution).
**Comparator:** `abs(4.95 - 5.00) = 0.05` > `0.01` — emit `close_price_mismatch` with `actual_value_json={"price": 4.95, "execution_legs": [{"leg_id":0, "price":4.95, "quantity":100, "time": "..."}], "schwab_order_id": "<id>", "schwab_limit_price": 5.00}` (the EXECUTION).
**Classifier:** **Shape C** payload routed through `_classify_close_price_mismatch` widened Shape C branch (Codex R1 M#1 fix per §3.2 module touch list — the existing V1 tier-2-always close-price classifier gets a Shape C branch alongside the legacy OHLCV-snapshot tier-2 path); tier-1 emit with `correction_target={'price': 4.95}`; auto-correct service writes `fills.price=4.95`. CORRECT outcome — operator-typed-from-trigger gets corrected to actual execution price.

**Cross-OQ note:** §6.4 OQ-D Path A lock + §3.2 module touch list together require WIDENING `_classify_close_price_mismatch` to honor Shape C payloads emitted by the V2 comparator. The legacy tier-2-always V1 path (no source_payload consulted; see `swing/trades/reconciliation_classifier.py:1107-1127`) survives as a fall-through for any future close_price_mismatch emitter that does NOT carry the Shape C audit keys (e.g., a hypothetical OHLCV-snapshot-driven close-price reconciliation). Discriminating tests: (a) Shape C payload → tier-1 with execution-grain `correction_target`; (b) Shape A-only payload (legacy emitter) → tier-2 unknown_schwab_subtype (V1 behavior preserved).

---

## §11 Adversarial review watch items (Codex round prompts)

For each round, pass these as targeted prompts to `copowers:adversarial-critic`:

1. **§1.1-§1.6 operator-locked constraints integrity.** Spec respects all 6 operator locks. If any recommendation appears to weaken them, flag — do NOT relax.
2. **§10.1 + §10.2 discriminating examples worked end-to-end.** CVGI + LION historical chains each walked through proposed V2 mapper + classifier + comparator with input payload + expected output + assertion. Coverage check: does V2 design avoid emitting false-positive discrepancies for these historical chains?
3. **Determinism principle preservation** (Sub-bundle C.B spec §4.4). When in doubt, classify as tier-2 (NOT tier-1). Audit §5 + §6.1 (OQ-A Path B lock) for false-positive-tier-1 risk under multi-leg + sandbox + missing-orderActivityCollection edge cases.
4. **OQ-A backward-compat coverage.** Path B locked, but discriminating tests required for the Path A behavior too (so a future operator pivot is a config flag away, not a code rewrite). Spec MUST cover both via writing-plans-phase tests.
5. **OQ-B multi-leg VWAP correctness.** Worked example §10.4 walks 50@$10.00 + 50@$10.20 → VWAP=$10.10. Discriminating test asserts both no-emit (journal=$10.10) AND emit (journal=$10.00).
6. **OQ-C tolerance window sensitivity.** With `price_tolerance=0.01`, CVGI $0.0056 + LION $0.0001 both fall under tolerance. Any operator-decided tighter tolerance is a config change. Spec MUST anchor the pick to empirical evidence (CVGI + LION sub-cent rounding).
7. **OQ-D FIRED-stop discipline.** Comparator switches uniformly to execution-grain for FIRED orders regardless of `order_type` (LMT/MKT/STOP/STOP_LIMIT). §10.6 walks this. Discriminating test plants FIRED-STOP fixture + asserts execution-leg path.
8. **OQ-E cassette-recording prerequisite.** §6.5 enumerates 4 minimum order types (LMT BUY, LMT SELL, STOP FIRED, MKT BUY) + 1 stretch (STOP_LIMIT FIRED). Writing-plans phase triggers operator-paired session.
9. **OQ-F deferral rationale.** §6.6 enumerates cascade analysis required for V2 auto-redirect. V1 LIFTS LOCK ONLY for single-leg matched-tuple. Multi-leg auto-redirect deferred.
10. **OQ-G leave-as-is rationale.** §6.7 enumerates 2 rejected alternatives + rationales. §8.3 documents the disposition for forward readers.
11. **T-B.7 HTMX discipline.** §7.5 confirms HTMX trinity preserved (read-only V1; HX-Redirect target route registration check inherits Phase 6 I3 gotcha precedent). §7.3 retargets `/schwab/setup` success path.
12. **NO new schema integrity check.** Spec proposes NO `CREATE TABLE` / `ALTER TABLE` / `0020_*.sql`. V2 fits in package-level dataclass extension + existing `actual_value_json` envelope.
13. **Sub-bundle decomposition cleanliness** (§9). 3 sub-bundles enumerated with parallelizability + cross-bundle dependencies + dispatch ordering + projected test deltas. No circular deps.
14. **Brief-premise empirical-verification.** Spec assertions about shipped-code state (mapper at lines 175-242; classifier at 155-215; comparator at 693) verified against actual code reads at brainstorm time. Schwab API field-shape claim at OQ-E is the deferred verification (cassette-recording prerequisite).
15. **~46 cumulative forward-binding lessons inheritance integrity.**
    - Sub-bundle C.B forward-binding lesson #7 (Co-Authored-By footer EXPLICIT suppression) — spec authored without footer; commit message in brief §4 prescribes the same.
    - Sub-bundle C.D 4 NEW lessons banked at 2026-05-17 (operator-pushback STOP-and-recover; production-write classifier soft-block per-invocation; orchestrator-inline gate-fix durable pattern; Pass-1 limit-vs-fill defect family extension). This spec IS the response to lesson #4.
    - Sub-bundle C.B forward-binding lesson #5 (shape predicate tightening) — applied to `SchwabExecutionLeg.__post_init__` (§4.1) + mapper defensive parsing (§4.3).
    - Sub-bundle B forward-binding lesson #6 (`apply_overrides(cfg)` discipline at Schwab entry points) — `/schwab/status` route handler inherits (§7.1).
    - HTMX gotcha trinity — preserved via §7.5.
16. **Pass-2-tier-1-FORBIDDEN gotcha amendment text** (§8.2) completeness — V1 historical context preserved + V2-RESOLVED top section + spec reference.
17. **Convergent-chain expectation.** Codex round count 4-6; convergent shape — fix-introduced regression vs adversarial-thrash distinction documented in return report.
18. **§1.6 fill-auto-population-at-entry scope clarity.** Spec acknowledges scope; identifies clean layering interfaces; flags V2-decision-foreclosure if any. Does NOT design fill auto-population.
19. **Audit trail JSON shape evolution** (§5.2). The `actual_value_json` now carries a NEW **Shape C** key-set `{"price", "execution_legs", "schwab_order_id", "schwab_limit_price"}` (Codex R1 C#1 LOCK). Classifier MUST gain a Shape C predicate alongside existing Shape A (`{"price"}` set-equality) + Shape B (full match-tuple). Existing Shape A consumers are UNAFFECTED (no caller emits the new keys without the V2 mapper widening branch). Discriminating test required: Shape A payload → tier-1 (preserved); Shape C payload → tier-1 (new branch); mixed/partial Shape C (e.g., `price` + `execution_legs` only) → tier-2 `unsupported` (predicate strictness preserved).
20. **Sandbox short-circuit preservation.** V2 mapper widening runs as pure function regardless of environment. Auto-correct service path under sandbox short-circuits at inner per CLAUDE.md "outer-tx transactional discipline" gotcha. Spec §3.3 confirms this — no spec change here, but Codex audits.
21. **Close_price_mismatch classifier widening (Codex R1 M#1 LOCK).** The existing `_classify_close_price_mismatch` at `swing/trades/reconciliation_classifier.py:1107-1127` is tier-2-always V1. Sub-bundle 1 ADDS a Shape C branch (mirrors the Pass-1 `_classify_entry_price_mismatch` widening). Legacy V1 tier-2 path survives for non-Shape-C payloads (preserves backward compat with any future OHLCV-snapshot-driven close-price emitter). Discriminating tests: Shape C → tier-1; Shape A or other → tier-2 unknown_schwab_subtype.
22. **Quantity-grain switch at comparator matching step (Codex R1 M#2 + M#3 LOCK).** §5.3 widens the line-658 quantity matcher to prefer execution-grain `sum(legs.quantity)` when executions populated. Mapper coherence-check distinguishes legitimate partial fills (execution sum == filledQuantity) from malformed leg totals (execution sum != filledQuantity) — only the malformed case collapses to `executions=None`. Both `quantity` AND `filledQuantity` extracted from Schwab order envelope per spec lines 478-480; new `filled_quantity` field on `SchwabOrderResponse` OR derived implicitly (writing-plans selects).
23. **Production-emitter-shape-through-classifier-audit-helper coverage (Codex R1 M#5 LOCK).** §5.2 Path B emit AND §10.5 walkthrough require END-TO-END test through `_emit` → `classify_discrepancy` → `_handle_no_mutation_audit` → CLI `show-ambiguity`. Pre-empts C.D gate-fix #2 family.
24. **`/schwab/status` default-environment from cfg (Codex R1 M#6 LOCK).** §7.1 sources from `apply_overrides(cfg).integrations.schwab.environment`; query-param overrides. Mirrors CLI semantics.
25. **Cassette gating decision authority (Codex R1 M#7 LOCK).** §6.5 operator-decided at writing-plans phase; default cassette-required for Sub-bundle 1 ship; mocked-only fallback with operator RISK ACCEPTANCE banked at `docs/phase3e-todo.md` + operator-witnessed gate becomes de-facto shape-drift detector.
26. **Operator-facing historical-correction-chain note (Codex R1 M#8 LOCK).** §8.3 adds CLI-help-text addendum on `show-correction` subcommand to surface "correction_ids 1-6 carry V1 order-grain; 7+ carry V2 execution-grain" without mutating rows. Preserves §1.4 audit-trail integrity.

---

## §12 If you get stuck (writing-plans handoff notes)

- If a Schwab API cassette session cannot be scheduled with the operator within writing-plans phase, writing-plans pivots Sub-bundle 1 to "mocked-only tests V1; cassettes V2-banked" with explicit risk-acceptance + retention follow-up.
- If `SchwabExecutionLeg` validator surfaces a real-world Schwab payload variant rejected at construction time, the mapper's defensive parsing (§4.3) silently drops the leg + logs warning — NO RAISE. The order still gets a `SchwabOrderResponse` with non-None `executions` containing only the legs that passed validation, OR `executions=None` if all legs were rejected.
- If the operator wishes to re-litigate OQ-A (Path A vs B), the spec writing-plans phase MUST surface the question to orchestrator BEFORE encoding tests; default lock is Path B per §6.1.
- If `_compute_execution_price` arithmetic precision is flagged (float roundoff), writing-plans phase emits a discriminating test asserting VWAP precision at >1000 share quantity + sub-cent leg prices. Standard double-precision floats are sufficient for the project's magnitude range (max position ~$100K equity).
- If T-B.7 web counterpart sub-bundle reveals a missing CLI/web parity item (e.g., the CLI prints recent-call summary in 2-column table; web should mirror), align via test fixture comparison.
- If §8.1 CVGI date typo verification surfaces NO existing typo, writing-plans no-ops the task + notes in return report.

---

## §13 Spec self-review notes (inline)

- **No "TBD" / "TODO" / placeholders** — all sections complete. (Two forward-references remain explicitly bracketed for executing-plans phase to fill: §8.2 `<date-of-Sub-bundle-1-ship>` for the gotcha amendment; §8.3 correction_id boundary "7" subject to production state at ship time.)
- **No internal contradictions** — §1.5 multi-leg VWAP lock consistent with §5.1 + §6.2 + §10.4 (Codex R1 M#4 amendment clarifies Pass-1 vs Pass-2 case split). §1.4 audit-trail preserved consistent with §6.7 + §8.3. §1.2 stop_mismatch unchanged consistent with §3.3 + §6.4 (FIRED-stop is fill-grain not trigger-grain — §10.6 walkthrough binds the close_price_mismatch Shape C path). §3.2 module touch list classifier branching keyed to Shape C predicate (Codex R1 C#2 amendment — no `execution_price` field-name mismatch).
- **Scope:** focused single-spec, decomposed at §9 into 3 sub-bundles (one architectural; one web; one housekeeping). Ready for writing-plans.
- **Ambiguity:** §5.2 Path B emit shape (`unmatched_*_fill` discrepancy_type + `execution_unavailable` sentinel) is the only place where the shape choice is materially ambiguous — explicitly enumerated as a design choice with rejected-alternative rationale + Codex R1 M#5 production-emitter-shape coverage requirement.
- **Line count:** ~1010 lines post-Codex-R1 fixes (within brief target 600-1000 by a thin margin; growth driven by 2 Critical + 6 Major + 2 Minor R1 fix-text inserts at §3.2 / §5.2 / §5.3 / §6.5 / §7.1 / §8.3 / §10.3 / §10.4 / §10.6 / §11 / §13).
- **Empirical anchoring:** CVGI + LION walkthroughs grounded in actual production correction chains (correction_ids 3+4 + 5+6) — verifiable in operator's `~/swing-data/swing.db` `reconciliation_corrections` table.
- **Codex R1 resolutions in-tree:** all 2 Critical (Shape C predicate + classifier-field-name consistency) + 6 Major (close_price classifier widening; quantity-grain switch; malformed-leg distinction; multi-leg Pass-1-vs-Pass-2 clarity; production-shape coverage; environment default; cassette gating; historical surfacing) + 2 Minor (float wording; query-param consumer retention) RESOLVED with code-content fixes. ZERO ACCEPT-WITH-RATIONALE.

---

*End of spec. Standalone post-Phase-12 dispatch; 8 operator-approved items (5 architectural + 1 web follow-up + 2 housekeeping + OQ-G operator-decision). Schema unchanged (v19). Decomposition into 3 sub-bundles for writing-plans phase. CVGI + LION historical chains worked end-to-end (§10.1 + §10.2). 6 OQs locked at §6 (5 binding + 1 deferrable to writing-plans phase).*
