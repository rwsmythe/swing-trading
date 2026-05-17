# Post-Phase-12 Schwab Mapper Execution-Grain Widening + T-B.7 `/schwab/status` + Housekeeping — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use `copowers:executing-plans` (wraps `superpowers:subagent-driven-development`) to implement this plan task-by-task across **two sequential executing-plans dispatches** (Sub-bundle 1 first; Sub-bundle 2 after Sub-bundle 1 ships). Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Land the architectural fix that closes the V1 Schwab limit-vs-fill defect family empirically falsified at Phase 12 Sub-sub-bundle C.D operator-witnessed gate (CVGI + LION 2026-05-17), ship the deferred T-B.7 `/schwab/status` web counterpart for the Schwab integration arc, and fold in three housekeeping micro-fixes atomically.

**Architecture:** Sub-bundle 1 extends `SchwabOrderResponse` with optional `executions: list[SchwabExecutionLeg] | None`, widens `map_orders_to_fill_candidates` to populate it from `orderActivityCollection[].executionLegs[]`, adds `_compute_execution_price` + `_resolve_match_quantity` helpers, switches the comparator price+quantity match to execution-grain (Path B tier-2 `unsupported` sentinel fall-through when not), and widens both Pass-1 classifier sub-classifiers with NEW Shape C predicate `source_keys == {"price"} | _EXECUTION_AUDIT_KEYS` emitting tier-1 with `correction_target={'price': X}` (Pass-2 stays tier-2-always V1; Path B sentinel recognition only). Sub-bundle 2 adds `GET /schwab/status` read-only web counterpart mirroring `swing schwab status` CLI 1:1 with `apply_overrides(cfg)` discipline, retargets `POST /schwab/setup` HX-Redirect, registers `/config` nav-link. Schema stays at v19; no migrations.

**Tech Stack:** Python 3.14, Click CLI, SQLite, FastAPI + HTMX + Jinja2, pytest + pytest-xdist + pytest-recording (vcrpy), schwabdev SDK.

---

## Table of contents

- §A.0 Pre-verifications against shipped code
- §A Sub-bundle 1 tasks (T-1.0 … T-1.13)
- §B Sub-bundle 2 tasks (T-2.0 … T-2.6)
- §C Cross-bundle pins
- §D Locked decisions roll-up
- §E Test projection
- §F Cassette runbook
- §G Cassette acceptance criteria
- §H Per-sub-bundle operator-witnessed gate plan
- §I Open questions for orchestrator triage
- §Z V2 candidates banked

---

## §A.0 Pre-verifications against shipped code (executed at plan-drafting time)

Per brief §0.5. Executed at HEAD `5c40286` (2026-05-16). Outcomes pin into per-task acceptance criteria below.

| # | Verification target | Outcome |
|---|---|---|
| 1 | `swing/integrations/schwab/mappers.py:148-242` mapper body | ✓ lines 223-230 read `price_raw = _opt(raw, "price")` with `stopPrice` fall-back. Lines 192-217 already handle missing/non-list/empty `orderLegCollection` via skip-with-warning. Lines 232-241 construct `SchwabOrderResponse(...)` with 8 positional args. |
| 2 | `swing/integrations/schwab/models.py:132-203` `SchwabOrderResponse` | ✓ 8 fields; `__post_init__` rejects unknown statuses/instructions/order_types. V2 extension preserves 8-positional backward compat by adding `executions` at field tail. |
| 3 | `swing/trades/schwab_reconciliation.py:639-718` comparator | ✓ Line 658 quantity compare; lines 663-689 emit `unmatched_open_fill`/`unmatched_close_fill` with synthetic `field_name="fill_match"`; line 693 price compare; lines 698-718 emit `entry_price_mismatch`/`close_price_mismatch` with `field_name="price"` + `delta_text=f"${...:+.2f}"`. **V2 switch targets: lines 658 + 693.** |
| 4 | `swing/trades/reconciliation_classifier.py:711-880` `_classify_unmatched_fill_shared` | ✓ `direction: str` param ('open'/'close') for reason rendering. Lines 728-746 Pass-1 no-payload branch → tier-2 `unsupported`. **V2 adds ONLY Path B `execution_unavailable=true` sentinel branch BEFORE existing logic; V1 Pass-2-tier-1-FORBIDDEN LOCK preserved uniformly.** |
| 5 | `swing/trades/reconciliation_classifier.py:96-538` `_classify_entry_price_mismatch` + `:1107-1130` `_classify_close_price_mismatch` | ✓ entry: Shape A (`{price}` only) + Shape B (full match-tuple). close: tier-2-always V1 with `noqa: ARG001` on both params. **V2 adds NEW Shape C branch to BOTH classifiers BEFORE existing predicates; legacy paths preserved.** |
| 6 | `swing/web/routes/schwab.py:193+249` `/schwab/setup` GET+POST | ✓ Sub-bundle B routing pattern; POST uses `apply_overrides(request.app.state.cfg)` at line 254. **Sub-bundle 2 follows same shape.** |
| 7 | `swing/cli_schwab.py:1416-1459` `swing schwab status` | ✓ `--environment` Click option + `apply_overrides(ctx.obj["config"])` at line 1440 + `env = (environment or cfg.integrations.schwab.environment).lower()` at 1441. Output via `render_status(...)` at 1449. **`SchwabStatusVM` mirrors `render_status` 1:1.** |
| 8 | base.html.j2 + Phase 10 T-E.3 base-layout VM banner pin | ✓ 10 existing base-layout VMs carry `unresolved_material_discrepancies_count: int`. SchwabSetupVM precedent in `swing/web/view_models/schwab.py:76`. **SchwabStatusVM MUST carry the field + populate via `_fetch_unresolved_material_count(cfg.paths.db_path)`.** |
| 9 | Current `POST /schwab/setup` HX-Redirect target | ✓ `/config?schwab_setup=ok`. **Sub-bundle 2 retargets to `/schwab/status` while RETAINING `/config?schwab_setup=ok` consumer as passive no-op per Codex R1 m#2 LOCK.** |
| 10 | `swing/web/templates/config.html.j2:58-60` "External integrations" section | ✓ `<h2>External integrations</h2>` + `<a href="/schwab/setup">...</a>`. **Sub-bundle 2 adds SECOND `<a href="/schwab/status">...</a>` in same section.** |
| 11 | Schwab API spec at `reference/schwab-api/account-specification.md:1792` `executionLegs[]` shape | ✓ each entry has `activityType` + `executionType` + `quantity` + `orderRemainingQuantity` + `executionLegs[]` with `legId`/`price`/`quantity`/`mismarkedQuantity`/`instrumentId`/`time`. Matches `SchwabExecutionLeg` per spec §4.1. Multiple worked-example confirmations at lines 524, 635, 763, 905, 1041, 1731. |
| 12 | `tests/conftest.py:88-110` `vcr_config` + cassette infra | ✓ `filter_headers=['authorization','cookie','set-cookie']` + `filter_query_parameters` + `filter_post_data_parameters`. Finviz precedent at `tests/integrations/cassettes/test_finviz_api/*.yaml`. **Sub-bundle 1 T-1.0 extends `vcr_config` with Schwab-specific filter additions per §F.** |

### §A.0.1 Brief-vs-shipped-code deviations flagged

- **D1 — `swing journal discrepancy show-correction <id>` subcommand does NOT exist.** Spec §8.3 references it; `swing/cli.py` has `show` (line 2172), `show-ambiguity` (line 2208), `override-correction` (line 2626). **Plan resolution:** T-1.12 adds NEW `show-correction` subcommand (parallel to `show`) reading from `reconciliation_corrections` via `get_correction` helper; addendum lands as the subcommand's Click `help=` epilog. The addendum ALSO appears in `override-correction --help` epilog for breadth via shared module-level constant `_HISTORICAL_CORRECTION_NOTE`.
- **D2 — CVGI date typo (§8.1) is a confirmed no-op.** `grep -n "2026-04-27" CLAUDE.md` returns 0 matches at plan-drafting time. T-1.11 ships as no-op-with-note-in-commit.

---

## §A Sub-bundle 1 — V2 mapper widening + classifier consumer + comparator + housekeeping (FOLDED)

**Scope:** the architectural fix. Surfaces execution-grain data; switches comparator price+quantity match; widens Pass-1 classifiers with NEW Shape C predicate; preserves V1 Pass-2 tier-2-always LOCK except Path B sentinel recognition; folds 3 housekeeping micro-fixes.

**Dispatch order:** cassette session (operator-paired; §F) → Sub-bundle 1 executing-plans dispatch → integration merge.

**Total tasks: 14** (T-1.0 … T-1.13). **Projected test delta: +50-100 fast tests.**

---

### Task T-1.0 — Cassette runbook + sanitization filter spec (DOCS ONLY; ships ahead of cassette session)

**Files:**
- Create: `docs/runbooks/schwab-cassette-recording.md` (~150-200 lines)
- Modify: `tests/conftest.py` (extend `vcr_config` with Schwab-specific filter entries; ~15-25 line diff)

**Acceptance criteria:**

1. Runbook covers 4 minimum order types per OQ-E LOCK + the stretch STOP_LIMIT FIRED. Per-type: operator workflow (place + fill in TOS/Schwab Mobile; run `swing schwab fetch --orders --environment production --days 30`; verify cassette captures `orderActivityCollection[].executionLegs[]`).
2. Sanitization filter spec extends `tests/conftest.py:88-110` `vcr_config` mirroring §F.3 — `filter_headers` adds Schwab custom headers; `filter_query_parameters` adds `accountNumber`/`accountHash`; `filter_post_data_parameters` adds OAuth params; `before_record_response` callable scrubs `accountNumber`/`accountHash` + 32+ hex / 24+ base64 token-shape regex.
3. Storage path locked: `tests/integrations/cassettes/schwab/<test-name>.yaml`.
4. Staleness recovery runbook (per §F.4).
5. Cross-references CLAUDE.md "Schwab cassette runbook is V2 PLANNED" gotcha; notes this dispatch shifts bar to cassette-required.
6. **Operator-actionability test:** runbook reads end-to-end as self-contained operator commands.

**Tests added:** 0 (docs-only).

**Commit message stem:** `docs(schwab-cassette): runbook + vcr_config Schwab filter extensions (T-1.0)`.

---

### Task T-1.1 — `SchwabExecutionLeg` dataclass NEW + `__post_init__` validators

**Files:**
- Modify: `swing/integrations/schwab/models.py` (add `SchwabExecutionLeg` `@dataclass(frozen=True)` before `SchwabOrderResponse`)
- Create: `tests/integrations/test_schwab_execution_leg.py`

**Acceptance criteria:**

Per spec §4.1. Frozen dataclass with 6 fields: `leg_id: int`, `price: float`, `quantity: float`, `mismarked_quantity: float | None`, `instrument_id: int | None`, `time: str`. `__post_init__` invariants:

- `leg_id` is `int` not bool; `>= 0`.
- `price` is `int|float` not bool; `math.isfinite()`; `> 0`.
- `quantity` is `int|float` not bool; `math.isfinite()`; `> 0`.
- `mismarked_quantity`: if non-None, `int|float` not bool; `math.isfinite()`; `>= 0`.
- `instrument_id`: if non-None, `int` not bool; `>= 0`.
- `time` is non-empty `str`.

**Discriminating tests (12 cases):** valid construction; reject zero price / negative price / non-finite price / zero quantity / bool-as-price / bool-as-quantity / empty time / negative leg_id; mismarked_quantity None accepted; mismarked_quantity negative rejected; frozen dataclass refuses attribute reassignment.

**TDD flow:** write failing tests → verify ImportError → implement → verify pass → commit.

**Tests added:** 12.

**Commit message stem:** `feat(schwab): SchwabExecutionLeg dataclass + __post_init__ validators (T-1.1)`.

---

### Task T-1.2 — `SchwabOrderResponse.executions` field extension + tri-valued semantics

**Files:**
- Modify: `swing/integrations/schwab/models.py` (add `executions: list[SchwabExecutionLeg] | None = None` at field tail + extend `__post_init__`)
- Modify: `tests/integrations/test_schwab_models.py`

**Acceptance criteria:**

Per spec §4.2 + §4.4. `executions` added as OPTIONAL field with `None` default — preserves 8-positional backward compat. `__post_init__` extension:

```python
if self.executions is not None:
    if not isinstance(self.executions, list):
        raise ValueError(f"SchwabOrderResponse.executions must be list or None; got {type(self.executions).__name__}")
    for i, leg in enumerate(self.executions):
        if not isinstance(leg, SchwabExecutionLeg):
            raise ValueError(f"SchwabOrderResponse.executions[{i}] must be SchwabExecutionLeg; got {type(leg).__name__}")
```

Tri-valued semantics: `None` (data not available) vs `[]` (Schwab confirmed no executions) vs `[leg, ...]` (one or more legs).

**Discriminating tests (8 cases):** default `executions is None`; empty list accepted; non-empty list accepted; non-list rejected; non-leg element rejected; 8-positional backward compat (no `executions=` kw); frozen reassignment rejected; pre-existing validator (unknown status) still rejects.

**Tests added:** 8.

**Commit message stem:** `feat(schwab): SchwabOrderResponse.executions tri-valued field (T-1.2)`.

---

### Task T-1.3 — `map_orders_to_fill_candidates` body extension + mapper coherence-check

**Files:**
- Modify: `swing/integrations/schwab/mappers.py` (insert after line 230 + before `out.append(SchwabOrderResponse(...))` at line 232)
- Modify: `tests/integrations/test_schwab_mappers.py`

**Acceptance criteria (per spec §4.3 + §5.3 mapper-coherence rule):**

1. Extract `order_activities = _opt(raw, "orderActivityCollection", None)`.
2. Extract `filled_quantity = _opt(raw, "filledQuantity")` (cast to float or None).
3. If `order_activities` is not a list OR is empty → `executions = None`.
4. Iterate `order_activities`: non-dict activity → log warning + skip; non-`EXECUTION` activityType → skip silently; per leg: non-dict → log warning + skip; dataclass validator raises → log warning + skip (defense-in-depth per spec §4.3).
5. After collecting legs: if `executions_list` empty → `executions = None`.
6. **Coherence check** (spec §5.3): if non-empty AND `filled_quantity is not None` AND `abs(sum(l.quantity for l in executions_list) - filled_quantity) >= 1e-9` → log WARNING (with order_id + observed sum + filled_quantity) + set `executions = None`. Otherwise `executions = executions_list`.
7. Pass `executions=executions` to `SchwabOrderResponse(...)`.

**Plan-author lock:** `filled_quantity` field is NOT added to `SchwabOrderResponse` — derived implicitly at mapper coherence-check time + discarded. Comparator uses `_resolve_match_quantity` helper for `sum(legs.quantity)`. Minimizes surface area + preserves 8-positional backward compat.

**Discriminating tests (14 cases):**

1. V1 backward compat — no `orderActivityCollection` → `executions=None`.
2. Empty `orderActivityCollection` (present but `[]`) → `executions=None` (mapper normalises empty → None).
3. Non-`EXECUTION` activityType → skipped silently; if all activities filtered → `executions=None`.
4. Single EXECUTION + single leg → 1-element list.
5. Multi-leg → list preserves leg order.
6. Coherence check legitimate partial fill (`order.quantity=200, filledQuantity=100, legs=[{qty:100}]`) → `executions` preserved.
7. Coherence check malformed leg totals (`order.quantity=100, filledQuantity=100, legs=[{qty:60},{qty:50}]`) → `executions=None` + WARNING log.
8. Defensive parsing — non-dict activity entry → skip + warn.
9. Defensive parsing — non-dict leg → skip + warn.
10. Defensive parsing — leg fails dataclass validator → drop leg + warn; remaining legs preserved if coherence check passes.
11. Multiple EXECUTION activity entries (broker split across activities) → legs collected.
12. `orderActivityCollection` is non-list (e.g., string) → silent fall-through; `executions=None`.
13. `SchwabOrderResponse.price` field preserved unchanged from V1 (load-bearing).
14. NO `filledQuantity` field present → permissive (treat legs as authoritative); no coherence-check fire.

**Tests added:** 14.

**Commit message stem:** `feat(schwab): mapper extracts orderActivityCollection.executionLegs + coherence-check (T-1.3)`.

---

### Task T-1.4 — `_compute_execution_price` helper

**Files:**
- Modify: `swing/trades/schwab_reconciliation.py` (add helper near other reconciliation helpers; do NOT relocate to sibling module)
- Create: `tests/trades/test_compute_execution_price.py`

**Acceptance criteria (per spec §5.1):**

```python
def _compute_execution_price(so: SchwabOrderResponse) -> float | None:
    """Spec §5.1: single-leg → leg.price; multi-leg → VWAP across legs;
    None/empty → None (caller's responsibility to fall through)."""
    if so.executions is None or not so.executions:
        return None
    if len(so.executions) == 1:
        return so.executions[0].price
    total_qty = sum(leg.quantity for leg in so.executions)
    if total_qty <= 0:
        return None  # defensive
    return sum(leg.price * leg.quantity for leg in so.executions) / total_qty
```

Pure function — no DB, no logging. Defensive `total_qty <= 0` guard is belt-and-suspenders (dataclass validator rejects `qty <= 0` at construction).

**Discriminating tests (10 cases):**

1. `None` executions → `None`.
2. Empty executions → `None`.
3. Single leg → leg price.
4. Two-leg VWAP equal quantities (50@10.00 + 50@10.20 → 10.10).
5. Three-leg VWAP unequal quantities (33@10.00 + 33@10.10 + 34@10.20 → ≈10.10058...).
6. VWAP commutative over leg order.
7. Pure function — no side effects on input `so` (idempotent invocations preserve `so.executions`).
8. High-quantity sub-cent precision (1000-share leg @ 5.2244 within 1e-12).
9. Matches §10.1 CVGI walkthrough (5.2244 × 100 → 5.2244).
10. Matches §10.2 LION walkthrough (12.6999 × 100 → 12.6999).

**Tests added:** 10.

**Commit message stem:** `feat(schwab-recon): _compute_execution_price helper (T-1.4)`.

---

### Task T-1.5 — `_resolve_match_quantity` helper

**Files:**
- Modify: `swing/trades/schwab_reconciliation.py` (add alongside `_compute_execution_price`)
- Create: `tests/trades/test_resolve_match_quantity.py`

**Acceptance criteria (per spec §5.3):**

```python
def _resolve_match_quantity(so: SchwabOrderResponse) -> float:
    """Spec §5.3 Codex R1 M#2: execution-grain sum when executions populated;
    order-grain fall-back otherwise. Preserves match correctness under partial-fill."""
    if so.executions:
        return sum(leg.quantity for leg in so.executions)
    return so.quantity
```

**Discriminating tests (5 cases):**

1. No executions → returns `so.quantity`.
2. Empty executions → returns `so.quantity`.
3. Single leg → returns leg quantity.
4. Multi leg → returns sum.
5. Partial fill (`order.quantity=200`, `executions=[leg @50.0]`) → returns 100 NOT 200 (Codex R1 M#2 binding).

**Tests added:** 5.

**Commit message stem:** `feat(schwab-recon): _resolve_match_quantity helper (T-1.5)`.

---

### Task T-1.6 — Comparator price-path switch + Path B `execution_unavailable=true` sentinel emit

**Files:**
- Modify: `swing/trades/schwab_reconciliation.py:693-718` (replace V1 price compare with `_compute_execution_price` + Path B sentinel emit BEFORE; widen `actual_value_json` shape to Shape C key-set `{"price", "execution_legs", "schwab_order_id", "schwab_order_price"}`; widen `delta_text` precision from `:+.2f` to `:+.4f`)
- Modify: `tests/trades/test_schwab_reconciliation.py`

**Acceptance criteria (per spec §5.2 + §6.1 OQ-A Path B LOCK):**

Replace V1 line-693 branch with:

```python
so = schwab_filled[match_idx]
execution_price = _compute_execution_price(so)
if execution_price is None:
    # OQ-A Path B: execution-grain unavailable → tier-2 `unsupported` via
    # unmatched_*_fill + execution_unavailable=true sentinel.
    dtype = "unmatched_open_fill" if f.action == "entry" else "unmatched_close_fill"
    _emit(..., discrepancy_type=dtype, field_name="fill_match",
          expected_value_json=json.dumps({"qty": float(f.quantity), "price": float(f.price), "action": f.action}, sort_keys=True),
          actual_value_json=json.dumps(
              {"matched": None, "execution_unavailable": True,
               "schwab_order_id": so.order_id, "schwab_order_price": so.price},
              sort_keys=True))
    continue
if abs(execution_price - float(f.price)) > price_tolerance:
    dtype = "entry_price_mismatch" if f.action == "entry" else "close_price_mismatch"
    _emit(..., discrepancy_type=dtype, field_name="price",
          expected_value_json=json.dumps({"price": float(f.price)}, sort_keys=True),
          actual_value_json=json.dumps(
              {"price": execution_price,
               "execution_legs": [{"leg_id": leg.leg_id, "price": leg.price,
                                   "quantity": leg.quantity, "time": leg.time}
                                  for leg in so.executions],
               "schwab_order_id": so.order_id, "schwab_order_price": so.price},
              sort_keys=True),
          delta_text=f"${execution_price - float(f.price):+.4f} (schwab execution minus journal)")
```

**Existing filter at line 641 preserved** (`getattr(o, "price", None) is not None` already excludes orders lacking `price` from the candidate pool, so the Path B branch executes only for orders with `price` populated but `executions=None`/`[]` — covers older orders pre-execution-grain + sandbox responses + mapper coherence-check collapse case).

**Shape C contract:** `actual_value_json` key-set is EXACTLY `{"price", "execution_legs", "schwab_order_id", "schwab_order_price"}` — classifier's NEW Shape C predicate at T-1.8 matches. Audit keys (`execution_legs` + `schwab_order_id` + `schwab_order_price`) are observational ONLY at classifier; `correction_target` carries `{'price': <execution_price>}` (Shape A-equivalent).

**Naming note (R3 m#2):** `schwab_order_price` (NOT `schwab_limit_price`) — covers MKT (`None`) / STOP (trigger) / LIMIT (limit) order_types gracefully.

**Discriminating tests (10 cases):**

1. Spec §10.1 CVGI single-leg within tolerance ($5.23 vs $5.2244 → delta 0.0056 < 0.01) → NO emit.
2. Spec §10.2 LION single-leg within tolerance ($12.70 vs $12.6999 → delta 0.0001) → NO emit.
3. Spec §10.4 multi-leg VWAP within tolerance ($10.10 vs VWAP=10.10) → NO emit.
4. Spec §10.3 legitimate typo outside tolerance ($10.00 vs $10.25) → Shape C emit with `actual_value_json` keys == `{"price", "execution_legs", "schwab_order_id", "schwab_order_price"}` + `delta_text` 4-decimal-precision (`$+0.2500 (schwab execution minus journal)`).
5. Spec §10.5 Path B `execution_unavailable=true` sentinel → `unmatched_open_fill` (NOT `entry_price_mismatch`) with sentinel in `actual_value_json`.
6. Path B does NOT double-emit when quantity-mismatch already fired at matching step.
7. Spec §10.6 OQ-D FIRED STOP uses execution-grain not trigger (STOP, `price=$5.00`, `executions=[leg @4.95]`; journal records $4.95 → NO emit; journal records $5.00 → `close_price_mismatch` with `execution_price=4.95`).
8. `close_price_mismatch` Shape C emit with audit keys (mirrors T-1.8 widening).
9. Sandbox short-circuit preserved (env=sandbox → no domain-row writes regardless of Path B trigger).
10. `delta_text` precision 4dp covers CVGI $0.0056 + LION $0.0001 sub-cent debugging signal (not rounded to $0.01 / $0.00).

**Tests added:** 10.

**Commit message stem:** `feat(schwab-recon): comparator switches to execution-grain VWAP + Path B sentinel emit (T-1.6)`.

---

### Task T-1.7 — Comparator quantity-match switch

**Files:**
- Modify: `swing/trades/schwab_reconciliation.py:658` (replace `so.quantity` with `_resolve_match_quantity(so)`)
- Modify: `tests/trades/test_schwab_reconciliation.py`

**Acceptance criteria (per spec §5.3 Codex R1 M#2):**

Replace:

```python
if abs(so.quantity - float(f.quantity)) > price_tolerance:
    continue  # not a match
```

with:

```python
if abs(_resolve_match_quantity(so) - float(f.quantity)) > price_tolerance:
    continue  # Codex R1 M#2 — execution-grain quantity-match
```

**Discriminating tests (4 cases):**

1. Partial fill matches via legs sum NOT order.quantity (`order.quantity=200`, `executions sum=100`; journal `qty=100` → matches).
2. Full fill match unchanged from V1 (executions sum == order.quantity).
3. `executions=None` falls back to `so.quantity` (V1 behavior preserved).
4. Partial fill with no match still emits `unmatched_open_fill` (`order.quantity=200`, `executions=[50]`; journal `qty=100` → no match → `unmatched_open_fill`).

**Tests added:** 4.

**Commit message stem:** `feat(schwab-recon): comparator quantity-match consumes execution-grain when available (T-1.7)`.

---

### Task T-1.8 — Shape C predicate at Pass-1 classifiers + audit-key persistence contract

**Files:**
- Modify: `swing/trades/reconciliation_classifier.py` (add `_EXECUTION_AUDIT_KEYS` + `_SHAPE_C_EXPECTED_KEYS` module constants; add Shape C branch to `_classify_entry_price_mismatch` BEFORE existing Shape A; add Shape C branch to `_classify_close_price_mismatch` BEFORE the tier-2-always V1 fall-through)
- Modify: `tests/trades/test_reconciliation_classifier.py`

**Acceptance criteria (per spec §3.2 + §5.2 + §10.3-§10.6):**

Module-level constants:

```python
_EXECUTION_AUDIT_KEYS = frozenset({"execution_legs", "schwab_order_id", "schwab_order_price"})
_SHAPE_C_EXPECTED_KEYS = frozenset({"price"}) | _EXECUTION_AUDIT_KEYS
```

`_classify_entry_price_mismatch` widening — insert Shape C branch after `isinstance(source_payload, Mapping)` guard (~line 201), BEFORE existing Shape A check:

```python
source_keys = frozenset(source_payload.keys())
if source_keys == _SHAPE_C_EXPECTED_KEYS:
    price = source_payload.get("price")
    if isinstance(price, (int, float)) and not isinstance(price, bool) and math.isfinite(float(price)):
        return ClassificationResult(
            tier=1, ambiguity_kind=None,
            correction_target={"price": float(price)},
            correction_reason=(f"entry_price_mismatch on (ticker={discrepancy.ticker!r}, "
                               f"fill_id={discrepancy.fill_id}): Schwab execution-grain price "
                               f"${float(price):.4f}; auto-correct to execution."),
            candidate_choices=None)
```

`_classify_close_price_mismatch` widening — remove `noqa: ARG001` markers + insert Shape C branch BEFORE existing tier-2-always return:

```python
if isinstance(source_payload, Mapping):
    source_keys = frozenset(source_payload.keys())
    if source_keys == _SHAPE_C_EXPECTED_KEYS:
        price = source_payload.get("price")
        if isinstance(price, (int, float)) and not isinstance(price, bool) and math.isfinite(float(price)):
            return ClassificationResult(tier=1, ambiguity_kind=None,
                correction_target={"price": float(price)},
                correction_reason=(f"close_price_mismatch on (ticker={ticker!r}, "
                                   f"trade_id={trade_id}): Schwab execution-grain price "
                                   f"${float(price):.4f}; auto-correct to execution."),
                candidate_choices=None)
# Fall through to existing tier-2-always V1 behavior
```

**Audit-key persistence contract (R2 M#2):** classifier does NOT copy `execution_legs`/`schwab_order_id`/`schwab_order_price` into `correction_reason` (which would balloon the string). Audit keys live in discrepancy row's persisted `actual_value_json` column (written by comparator at T-1.6 `_emit` time) — queryable via `SELECT json_extract(actual_value_json, '$.execution_legs') FROM reconciliation_discrepancies WHERE id=?`.

**Pass-2 NOT widened at T-1.8.** `_classify_unmatched_fill_shared` handled at T-1.9.

**Discriminating tests (12 cases):**

1. `_EXECUTION_AUDIT_KEYS` constant value asserted (frozenset of 3 strings).
2. `_classify_entry_price_mismatch` Shape A `{price}` preserved → tier-1 (Sub-bundle C.B contract).
3. `_classify_entry_price_mismatch` Shape B full match-tuple preserved → tier-1.
4. `_classify_entry_price_mismatch` Shape C audit-bearing → tier-1 with `correction_target={'price': X}`.
5. `_classify_entry_price_mismatch` Shape C `correction_reason` SHORT (< 500 chars; does NOT stringify `execution_legs[]` array).
6. Shape C audit-key persistence — discriminating SQL `SELECT json_extract(actual_value_json, '$.execution_legs') FROM reconciliation_discrepancies WHERE id=?` returns non-NULL JSON-array.
7. Mixed/partial Shape C (e.g., `{price, execution_legs}` only) → tier-2 `unsupported` (strict-set predicate preserved per spec §11 watch item #19 determinism).
8. `_classify_close_price_mismatch` Shape C → tier-1 (spec §3.2 + §10.6 OQ-D walkthrough).
9. `_classify_close_price_mismatch` Shape A-only (legacy) → tier-2 `unknown_schwab_subtype` (V1 fall-through preserved; OHLCV-snapshot future consumer compat).
10. `_classify_close_price_mismatch` mixed/partial Shape C → tier-2.
11. **Pass-2 sanity — `unmatched_open_fill` with audit-shape `actual_value_json` STILL tier-2** (V1 LIFT scope = Pass-1 only; T-1.9 covers Path B sentinel recognition separately; this test pins NO Pass-2 LIFT regression).
12. Sub-bundle C.B 6-case Pass-2-tier-1-FORBIDDEN parametrized test STILL passes post-T-1.8 (regression smoke).

**Tests added:** 12.

**Commit message stem:** `feat(schwab-classifier): Shape C predicate for entry/close_price_mismatch (T-1.8)`.

---

### Task T-1.9 — `_classify_unmatched_fill_shared` Path B sentinel recognition (V1 Pass-2 stays tier-2-always)

**Files:**
- Modify: `swing/trades/reconciliation_classifier.py:711` `_classify_unmatched_fill_shared` (add Path B sentinel branch BEFORE existing logic)
- Modify: `tests/trades/test_reconciliation_classifier.py`

**Acceptance criteria (per spec §5.2 + §6.1 OQ-A LOCK):**

After line 727, BEFORE existing Pass-1-or-no-payload branch, insert:

```python
if isinstance(source_payload, Mapping) and source_payload.get("execution_unavailable") is True:
    schwab_order_id = source_payload.get("schwab_order_id", "<unknown>")
    schwab_order_price = source_payload.get("schwab_order_price")
    price_text = (f"${float(schwab_order_price):.4f}"
                  if isinstance(schwab_order_price, (int, float))
                     and not isinstance(schwab_order_price, bool)
                  else "(price unavailable)")
    return ClassificationResult(
        tier=2, ambiguity_kind="unsupported", correction_target=None,
        correction_reason=(f"unmatched_{direction}_fill on (ticker={ticker!r}, "
                           f"fill_id={fill_id}): Schwab order {schwab_order_id} "
                           f"(order_price={price_text}) found but no execution-grain "
                           f"data available; please disposition manually per broker "
                           f"statement (LIFT deferred OQ-F V2)"),
        candidate_choices=None)
```

**Discriminating tests (5 cases):**

1. Path B sentinel for `unmatched_open_fill` → tier-2 `unsupported` + reason contains 'execution-grain' or 'execution_unavailable'.
2. Path B sentinel for `unmatched_close_fill` — same shape.
3. Path B sentinel reason includes `schwab_order_id` for operator-actionability.
4. Legacy Pass-1 no-payload path → still tier-2 `unsupported` (V1 behavior unchanged; preserves the existing branch at line 728).
5. Pass-2 list-shape payload (n>=2) → still routes through V1 logic (tier-2 `multi_match_within_window` etc.) — Sub-bundle C.B 6-case Pass-2-tier-1-FORBIDDEN parametrized test MUST still PASS post-T-1.9 (no V1 LIFT regression).

**Tests added:** 5.

**Commit message stem:** `feat(schwab-classifier): Path B execution_unavailable sentinel recognition (T-1.9)`.

---

### Task T-1.10 — CLAUDE.md `Pass-2-tier-1-FORBIDDEN` gotcha amendment (V1 RESOLVED for Pass-1; Pass-2 stays V1 tier-2-always)

**Files:**
- Modify: `CLAUDE.md` (locate `Pass-2-tier-1-FORBIDDEN` gotcha; insert "V2 RESOLVED" top section)

**Acceptance criteria (per spec §8.2):**

1. Locate gotcha via `grep -n "Pass-2-tier-1-FORBIDDEN\|limit-vs-fill" CLAUDE.md`.
2. Insert "V2 RESOLVED for Pass-1" top section per spec §8.2 verbatim shape — references `<DATE-OF-SUB-BUNDLE-1-MERGE>` (executing-plans phase fills at commit time), spec doc path, mapper extension + comparator line + classifier Shape C, Pass-2 remains tier-2-always V1 with Path B sentinel as only new branch, OQ-F V2 LIFT deferral cite.
3. V1 historical context preserved BELOW new top section verbatim (CVGI + LION 2026-05-17 falsification + 3 orchestrator-inline gate-fix instances + Pass-2-FORBIDDEN family).
4. Spec path + commit chain referenced (initial `8c1e5cb` through Codex-R5 `dda8730`).
5. Explicitly distinguishes Pass-1 (V2-RESOLVED) vs Pass-2 (V1 tier-2-always; LIFT V2-DEFERRED).
6. No other CLAUDE.md gotcha touched.
7. Operator reviews at gate S6.

**Atomic-vs-separate commit:** plan-author RECOMMENDS T-1.10 land as STANDALONE commit immediately AFTER T-1.9 to preserve per-task commit granularity (Phase 9/10/12 precedent). Implementer chooses; integration merge captures both shapes for `git log -p CLAUDE.md`.

**Tests added:** 0 (docs-only).

**Commit message stem:** `docs(claude+gotcha): Pass-2-tier-1-FORBIDDEN amended — V2-RESOLVED for Pass-1 (T-1.10)`.

---

### Task T-1.11 — CVGI date typo verification + no-op-with-note (housekeeping §8.1)

**Files:**
- (Conditional) Modify: `CLAUDE.md` if typo found

**Acceptance criteria:**

1. Verification grep: `grep -n "2026-04-27" CLAUDE.md` + `grep -n "CVGI.*2026-04" CLAUDE.md`.
2. Branch on result:
   - 0 matches AND no CVGI April-27 date present → T-1.11 NO-OP. Note in T-1.10 commit message OR final integration-merge commit: "CVGI date typo verification: 0 matches for '2026-04-27' in CLAUDE.md at ship time; T-1.11 no-op-with-note".
   - Matches found → identify offending line + edit to replace with `2026-05-08` per brief §2.6 + commit separately.

**Tests added:** 0.

**Commit message stem (if non-no-op):** `docs(claude): correct CVGI entry-date attribution (T-1.11)`.

---

### Task T-1.12 — NEW `swing journal discrepancy show-correction <id>` CLI subcommand + generic ID-free addendum (per spec §8.3 OQ-G + brief D1)

**Files:**
- Modify: `swing/cli.py` (add `_HISTORICAL_CORRECTION_NOTE` module constant + new `discrepancy_group.command("show-correction")` block + epilog on `override-correction` help text)
- Create: `tests/cli/test_discrepancy_show_correction.py`

**Brief deviation note:** per §A.0.1 D1, spec references non-existing `show-correction` subcommand. Plan adds NEW subcommand AS PART OF this dispatch.

**Acceptance criteria (per spec §8.3 + R1 M#8 + R2 M#3 + R3 m#1 LOCK):**

`_HISTORICAL_CORRECTION_NOTE` constant — verbatim text per spec §8.3:

> "Note: reconciliation_corrections rows recorded PRIOR to the V2 mapper widening (swing/integrations/schwab/mappers.py extension to surface orderActivityCollection[].executionLegs[]; design doc: docs/superpowers/specs/2026-05-17-schwab-mapper-execution-grain-widening-design.md) carry ORDER-grain prices in schwab_said_value_json — the V1 mapper read order.price (LIMIT for buy/sell, trigger for stops), NOT the actual execution price. For any correction chain you are reviewing: the chain head's operator_truth_value_json (when the chain head's resolution is 'operator_overridden') is the AUTHORITATIVE truth; intermediate "Schwab said" values from V1-era rows may reflect order-grain limits. From the V2 widening's ship forward, schwab_said_value_json carries EXECUTION-grain prices via the new SchwabExecutionLeg dataclass."

GENERIC + ID-FREE: no operator-local correction IDs cited; no hardcoded ship-date boundary.

New subcommand `show-correction <correction_id>` reads from `reconciliation_corrections` via `get_correction(conn, correction_id)` (existing helper from C.A/C.B/C.C); renders the 17 columns analogous to existing `discrepancy show` block.

`override-correction` Click `help=` epilog ALSO appends `_HISTORICAL_CORRECTION_NOTE` for breadth.

**Discriminating tests (8 cases):**

1. `show-correction --help` exits 0; carries "show-correction" or "CORRECTION_ID" text.
2. `show-correction --help` includes addendum text ("V2 mapper widening", "execution-grain", "operator_truth_value_json" substrings).
3. `show-correction --help` no operator-local correction IDs cited (no "correction_id=1..7", "rows 1-6", "correction_ids 1-6" substrings).
4. `show-correction --help` cites spec path verbatim.
5. `override-correction --help` ALSO includes addendum text (breadth).
6. `show-correction <existing_id>` smoke renders row (`correction_id: N` in output; exit 0).
7. `show-correction 99999` (not found) → exit non-zero + "not found" in stderr/output.
8. `_HISTORICAL_CORRECTION_NOTE` constant single-source-of-truth ("V2 mapper widening" substring present).

**Tests added:** 8.

**Commit message stem:** `feat(cli): journal discrepancy show-correction + generic historical addendum (T-1.12)`.

---

### Task T-1.13 — End-to-end integration test against cassette-recorded 4 order types

**Files:**
- Create: `tests/integration/test_phase12_post_schwab_mapper_widening_e2e.py`
- Consumes cassettes at `tests/integrations/cassettes/schwab/` (produced by operator-paired cassette session per §F)

**Acceptance criteria:**

5 tests using `@pytest.mark.vcr` covering 4 minimum order types + 1 legitimate-typo Shape C scenario. Each test asserts:

1. Comparator emit shape (no false-positive for matched-execution-price cases; 1 Shape C discrepancy for legitimate-typo case).
2. Classifier disposition (tier-1 with execution-grain `correction_target` for legitimate-typo case).
3. Audit-key persistence on discrepancy row via `SELECT json_extract(actual_value_json, '$.execution_legs') FROM reconciliation_discrepancies WHERE id=?` returns non-NULL JSON.

**Test list:**

1. `test_e2e_limit_buy_no_false_positive` (LIMIT BUY cassette; journal records exec price; NO emit).
2. `test_e2e_limit_sell_no_false_positive` (LIMIT SELL; NO emit).
3. `test_e2e_stop_fired_no_false_positive` (FIRED STOP; execution price ≠ trigger; journal records exec → NO emit).
4. `test_e2e_market_buy_no_false_positive` (MARKET BUY; verify executionLegs surface for MKT).
5. `test_e2e_legitimate_typo_emits_shape_c_tier_1` (synthetic typo: journal records WRONG price → Shape C emit + tier-1 classification + audit-key persistence).

**Tests added:** 5.

**Commit message stem:** `test(schwab-recon): end-to-end cassette-driven 4-order-types integration test (T-1.13)`.

---

## §B Sub-bundle 2 — T-B.7 `/schwab/status` web counterpart

**Scope:** the deferred Phase 12 Sub-bundle B T-B.7 task. Read-only web counterpart to `swing schwab status` CLI; new template extending `base.html.j2`; nav-link from `/config`; retargets `POST /schwab/setup` HX-Redirect.

**Dispatch order:** AFTER Sub-bundle 1 ships.

**Total tasks: 7** (T-2.0 … T-2.6). **Projected test delta: +20-40 fast tests.**

---

### Task T-2.0 — `SchwabStatusVM` view-model + base-layout VM banner pin

**Files:**
- Modify: `swing/web/view_models/schwab.py` (add `SchwabCallSummary` + `SchwabStatusVM` dataclasses)
- Modify: `tests/web/test_view_models/test_schwab.py`

**Acceptance criteria (per spec §7.1):**

`SchwabCallSummary` frozen dataclass: `started_ts: str`, `endpoint: str`, `status: str` (∈ {'success','auth_failed','rate_limited','error'}), `http_status: int | None`, `error_excerpt: str | None`.

`SchwabStatusVM` frozen dataclass mirroring CLI `swing schwab status` output 1:1:
- `session_date: str`
- `environment: Literal['production', 'sandbox']`
- `state: Literal['CONFIGURED', 'PROVISIONAL', 'NOT_CONFIGURED']`
- `tokens_db_path: str`
- `refresh_token_expires_at: str | None`
- `refresh_token_days_remaining: int | None`
- `refresh_token_severity: Literal['ok', 'warn', 'error']`
- `recent_calls: list[SchwabCallSummary]`
- `last_success_at: str | None`
- `last_failure_at: str | None`
- `degraded_banner_active: bool`
- `nav_back_to_config_url: str = "/config"`
- **Base-layout fields (Phase 10 T-E.3 inheritance):** `stale_banner: str | None = None`, `price_source_degraded: bool = False`, `price_source_degraded_until: str | None = None`, `ohlcv_source_degraded: bool = False`, `unresolved_material_discrepancies_count: int = 0`.

`__post_init__` validates env ∈ {production, sandbox}; state ∈ {CONFIGURED, PROVISIONAL, NOT_CONFIGURED}; severity ∈ {ok, warn, error}; `unresolved_material_discrepancies_count >= 0`; `recent_calls` is list of `SchwabCallSummary`.

**Discriminating tests (10 cases):**

1. Valid construction; base-layout fields default-initialized.
2. Invalid environment ('banana') rejected.
3. Invalid state rejected.
4. Invalid severity rejected.
5. Negative `unresolved_material_discrepancies_count` rejected.
6. `recent_calls` non-list rejected.
7. `recent_calls` list-of-non-SchwabCallSummary rejected.
8. `SchwabCallSummary` smoke construction valid.
9. `SchwabCallSummary` unknown status rejected.
10. Frozen — `vm.state = 'X'` raises `AttributeError`. `nav_back_to_config_url` defaults to "/config".

**Tests added:** 10.

**Commit message stem:** `feat(schwab-vm): SchwabStatusVM + SchwabCallSummary view-model (T-2.0)`.

---

### Task T-2.1 — `GET /schwab/status` route + `apply_overrides(cfg)` discipline + query-param override

**Files:**
- Modify: `swing/web/routes/schwab.py` (add `GET /schwab/status` handler)
- Create: `tests/web/test_routes/test_schwab_status.py`

**Acceptance criteria (per spec §7.1 + Codex R1 M#6 LOCK):**

Route handler:

```python
@router.get("/schwab/status", response_class=HTMLResponse)
async def schwab_status_get(request: Request, environment: str | None = None) -> HTMLResponse:
    cfg = apply_overrides(request.app.state.cfg)
    if environment is not None:
        if environment not in ("production", "sandbox"):
            return HTMLResponse(f"Invalid environment {environment!r}; must be 'production' or 'sandbox'", status_code=400)
        env = environment
    else:
        env = (cfg.integrations.schwab.environment or "production").lower()
    db_path = cfg.paths.db_path
    unresolved_count = _fetch_unresolved_material_count(db_path)
    session_date = action_session_for_run(datetime.now()).isoformat()
    vm = build_schwab_status_vm(cfg=cfg, env=env, db_path=db_path,
                                 session_date=session_date, unresolved_count=unresolved_count)
    return templates.TemplateResponse(request, "schwab_status.html.j2", {"vm": vm})
```

`build_schwab_status_vm` helper lives in `swing/web/view_models/schwab.py`; consults same data as CLI `render_status` (recent-calls via `swing/data/repos/schwab_api_calls.py`; tokens DB metadata + refresh-token TTL via shared helper). Implementer extracts shared helpers if needed for CLI/web parity.

**Discriminating tests (10 cases):**

1. Route registered in app.routes (Phase 6 I3 inheritance check).
2. GET renders template (status 200 + 'Schwab integration status' substring).
3. Default environment from cfg (no `?environment=` param + cfg env=sandbox → page renders sandbox).
4. `?environment=production` overrides cfg sandbox default.
5. `?environment=sandbox` overrides cfg production default.
6. `?environment=banana` → 400.
7. `apply_overrides` invoked once per request (monkeypatch spy on `apply_overrides`).
8. Base-layout banner field populated (plant 1 material discrepancy; assert response renders banner count = 1; Phase 10 T-E.3 retrofit).
9. POST returns 405 (V1 read-only).
10. `HX-Request` header present has no special handling (smoke: GET with + without HX-Request both 200).

**Tests added:** 10.

**Commit message stem:** `feat(web): GET /schwab/status route + apply_overrides discipline (T-2.1)`.

---

### Task T-2.2 — `schwab_status.html.j2` template

**Files:**
- Create: `swing/web/templates/schwab_status.html.j2`
- Modify: `tests/web/test_templates/test_schwab_status.py` (template smoke tests via TestClient)

**Acceptance criteria (per spec §7.1 + §7.2 + §7.6):**

Template extends `base.html.j2`. Renders all VM fields with color-coded state badge (CONFIGURED=green, PROVISIONAL=yellow, NOT_CONFIGURED=red), refresh-token countdown with severity styling, recent-calls table, environment switcher (`?environment=production` / `?environment=sandbox` links), re-auth link to `/schwab/setup` when state != CONFIGURED OR severity != 'ok'. Inherits Phase 10 unresolved-material-discrepancies banner via base.html.j2 (VM populates field; no template handling).

**Discriminating tests (8 cases):**

1. Template extends base layout (response contains nav from base.html.j2).
2. State CONFIGURED → green indicator (class="state-ok" or state="ok" attr).
3. State PROVISIONAL → warn indicator.
4. State NOT_CONFIGURED → error indicator.
5. Refresh-token TTL countdown ("Refresh token" + "days" substring).
6. Recent-calls table present (`<table>` + endpoint column).
7. Environment switcher links (`?environment=production` + `?environment=sandbox`).
8. Re-auth link `/schwab/setup` present when PROVISIONAL.

**Tests added:** 8.

**Commit message stem:** `feat(web): schwab_status.html.j2 template + 3-state renderer (T-2.2)`.

---

### Task T-2.3 — `/config` "External integrations" nav-link to `/schwab/status` + regression test

**Files:**
- Modify: `swing/web/templates/config.html.j2:58-60` (add SECOND `<a>` in External integrations section)
- Modify: `tests/web/test_routes/test_config.py`

**Acceptance criteria:**

```html
<h2>External integrations</h2>
<ul>
    <li><a href="/schwab/setup">Set up / re-authorize Schwab OAuth →</a></li>
    <li><a href="/schwab/status">View Schwab integration status →</a></li>
</ul>
```

**Discriminating tests (3 cases):**

1. `/config` response contains `href="/schwab/status"` + "Schwab integration status" or "Schwab status" text.
2. `/schwab/setup` nav-link preserved (no regression).
3. `/schwab/status` target route registered in app.routes (Phase 6 I3 inheritance).

**Tests added:** 3.

**Commit message stem:** `feat(web): /config nav-link to /schwab/status (T-2.3)`.

---

### Task T-2.4 — `POST /schwab/setup` HX-Redirect retarget to `/schwab/status` + `/config?schwab_setup=ok` consumer retention

**Files:**
- Modify: `swing/web/routes/schwab.py` (change HX-Redirect target in POST success path)
- Modify: `tests/web/test_routes/test_schwab_setup.py`

**Acceptance criteria (per spec §7.3 + Codex R1 m#2 LOCK):**

In `POST /schwab/setup` success path, change `HX-Redirect: /config?schwab_setup=ok` → `HX-Redirect: /schwab/status`. **Do NOT** remove `/config` page's tolerance for `?schwab_setup=ok` query-param (passive no-op consumer retained one release window for stale browser tabs/bookmarks).

**Discriminating tests (3 cases):**

1. Successful POST → 204 + `HX-Redirect: /schwab/status` header (NOT `/config?schwab_setup=ok`).
2. `/config?schwab_setup=ok` query-param still renders 200 (tolerated silently).
3. `/schwab/status` target registered (HX-Redirect target route check).

**Tests added:** 3.

**Commit message stem:** `feat(web): retarget /schwab/setup HX-Redirect to /schwab/status (T-2.4)`.

---

### Task T-2.5 — HTMX trinity preservation regression test

**Files:**
- Modify: `tests/web/test_routes/test_schwab_status.py`

**Acceptance criteria (per spec §7.5):**

3 regression tests pinning HTMX gotcha trinity (HX-Request propagation; HX-Redirect-vs-303-swap; HX-Redirect-target-unrouted):

1. HX-Request propagation N/A for read-only GET (smoke: GET with + without HX-Request both 200).
2. `/schwab/setup` POST HX-Redirect target (`/schwab/status`) registered.
3. OriginGuard strict-mode allows read-only GET (smoke).

**Tests added:** 3.

**Commit message stem:** `test(web): HTMX trinity regression coverage for /schwab/status (T-2.5)`.

---

### Task T-2.6 — OQ-D applicability test for `/schwab/status`

**Files:**
- Modify: `tests/web/test_routes/test_schwab_status.py`

**Acceptance criteria (per spec §7.4):**

`/schwab/status` is read-only V1; no reconciliation actions; no FIRED-stop-specific handling at this layer. Discriminating test: assert recent-calls table cells contain NO order_type-specific strings (LIMIT/MARKET/STOP/STOP_LIMIT/FIRED) leaking into the status page (operator sees raw API call status only).

**Tests added:** 1.

**Commit message stem:** `test(web): /schwab/status inherits CLI semantics 1:1 (T-2.6)`.

---

## §C Cross-bundle pins

### §C.1 Sub-bundle 1 → Sub-bundle 2

- Sub-bundle 2 `SchwabStatusVM` populates `unresolved_material_discrepancies_count` via same `_fetch_unresolved_material_count(db_path)` helper at `swing/web/routes/schwab.py:266`. Phase 10 T-E.3 retrofit pattern; banner predicate widened per Phase 12 Sub-sub-bundle C.D to include `'pending_ambiguity_resolution'` (inherited transitively).
- Sub-bundle 1 REDUCES false-positive `entry_price_mismatch`/`close_price_mismatch` emissions. Sub-bundle 2's banner field typically renders `0` post-Sub-bundle-1-ship; gate S5 confirms.

### §C.2 Cassette session → Sub-bundle 1

- HARD PREREQ per spec §6.5 + brief §0.6 OQ-E LOCK.
- Cassettes ship at `tests/integrations/cassettes/schwab/test_e2e_<order_type>.yaml` covering 4 minimum + stretch.
- T-1.13 e2e integration test consumes the cassettes.

### §C.3 Sub-bundle 1 housekeeping → CLAUDE.md gotcha review

- T-1.10 amendment REVIEWED by operator at gate S6.
- Text completeness: preserves V1 historical context (CVGI + LION 2026-05-17 falsification + 3 orchestrator-inline gate-fix instances + Pass-2-FORBIDDEN family); adds NEW V2-RESOLVED top-section; references V2 dispatch + spec + commit chain.

### §C.4 NO behavioral changes to NON-touched existing surfaces (brief §5 watch item #19)

- `stop_mismatch` comparator at `swing/trades/schwab_reconciliation.py:_find_working_stop_for_ticker` UNCHANGED (spec §1.2 lock #2).
- `SchwabOrderResponse.price` field UNCHANGED (load-bearing for stop trigger + Path A fall-back + sandbox fixtures + audit-log redaction).
- Sandbox short-circuit gating UNCHANGED.
- Schema v19 UNCHANGED.
- Existing tier-1/tier-2 conventions (Sub-bundle C.B determinism principle, `ClassificationResult`, validator chain, auto-correct service surface) UNCHANGED.
- Existing CLI surface (`swing journal discrepancy {list,show,resolve,...}` + `swing journal reconcile-backfill`) UNCHANGED except for ADDITIVE `show-correction` subcommand + `override-correction` help epilog (T-1.12).
- `_classify_close_price_mismatch` tier-2 fall-through PRESERVED for non-Shape-C payloads.
- Sub-bundle C.B Pass-2 6-case parametrized test MUST still PASS post-Sub-bundle-1 (T-1.8 + T-1.9 discriminating tests pin this).

### §C.5 Plan-author schema additions surfaced during writing-plans → ESCALATE

Per Phase 9 Sub-bundle A return report lesson #7 + Phase 12 Sub-sub-bundle C.A T-A.2 + C.B forward-binding lessons. **Plan author confirms NONE surfaced during plan drafting.** Schema stays at v19.

---

## §D Locked decisions roll-up

### §D.1 Spec §13 25-item LOCKED inheritance

| # | Spec §13 LOCK | Plan posture |
|---|---|---|
| 1 | §1.1 Execution price IS truth | T-1.3 + T-1.4 + T-1.6 implement; T-1.13 cassette E2E binds |
| 2 | §1.2 `stop_mismatch` UNCHANGED | §C.4 lock |
| 3 | §1.3 Schema stays v19 | §C.5 escalation rule; NONE surfaced |
| 4 | §1.4 Audit-trail integrity preserved | T-1.12 generic addendum; OQ-G operator-decided |
| 5 | §1.5 V1 LIFT = Pass-1 only | T-1.8 widens Pass-1; T-1.9 ONLY Path B sentinel for Pass-2 |
| 6 | §1.6 Magnitude NOT the axis | T-1.8 Shape C strict-set predicate; T-1.6 tolerance unchanged |
| 7-9 | §3.1-§3.3 architectural shape + touch list + no-change list | tasks match scope; no extra modules; §C.4 lock |
| 10 | §4.1 `SchwabExecutionLeg` invariants | T-1.1 (12 tests; all 6 invariants) |
| 11 | §4.2 tri-valued executions | T-1.2 (8 tests; None/[]/list) |
| 12-13 | §4.3-§4.4 mapper defensive parsing + backward compat | T-1.3 (14 tests) + T-1.2 8-positional test |
| 14 | §5.1 `_compute_execution_price` | T-1.4 (10 tests) |
| 15 | §5.2 comparator switch + Shape C audit-key contract | T-1.6 (10 tests) + T-1.8 audit-key persistence test |
| 16 | §5.3 quantity-grain switch + mapper coherence-check | T-1.5 + T-1.7 + T-1.3 |
| 17 | §6.1 OQ-A Path B | T-1.6 sentinel emit + T-1.9 recognition |
| 18 | §6.2 OQ-B VWAP V1 | T-1.4 VWAP; T-1.13 multi-leg cassette |
| 19 | §6.3 OQ-C `price_tolerance=0.01` retained | NOT changed; T-1.6 reuses existing |
| 20 | §6.4 OQ-D Path A | T-1.6 + T-1.8 close_price_mismatch Shape C; T-1.13 STOP FIRED |
| 21 | §6.5 OQ-E cassette-required | §F runbook + §G acceptance + brief §0.6 LOCK |
| 22 | §6.6 OQ-F V2 deferral | NO task; banked §Z |
| 23 | §6.7 OQ-G leave-as-is + generic CLI | T-1.12 implements |
| 24 | §7.1-§7.6 T-B.7 web counterpart | T-2.0..T-2.6 (38 tests) |
| 25 | §8.1-§8.3 housekeeping | T-1.10 + T-1.11 + T-1.12 (folded into Sub-bundle 1) |

### §D.2 Brief §0.3 operator decisions (BINDING)

- **OQ-E cassette-required default** — §F runbook + §G acceptance; HARD PREREQ for Sub-bundle 1 executing-plans dispatch.
- **Sequential 1 → 2 ordering** — §A first; §B second.
- **Sub-bundle 3 fold into Sub-bundle 1** — T-1.10 + T-1.11 + T-1.12 inside Sub-bundle 1.

### §D.3 Plan-author additional locks

- **D1 deviation:** T-1.12 adds NEW `show-correction` subcommand (spec referenced non-existing CLI).
- **`filled_quantity` derivation:** mapper coherence-check uses `filled_quantity` at mapper time + discards; NO new field on `SchwabOrderResponse` (writing-plans choice per spec §5.3 "writing-plans decides").
- **`surface='cli'` for `/schwab/status` audit attributions** per Sub-bundle B precedent (V2 `surface='web'` widening banked §Z).
- **T-1.10 commit shape:** atomic-with-code OR standalone-immediately-after-T-1.9; implementer chooses.

---

## §E Test projection

- **Sub-bundle 1:** T-1.0 (0) + T-1.1 (12) + T-1.2 (8) + T-1.3 (14) + T-1.4 (10) + T-1.5 (5) + T-1.6 (10) + T-1.7 (4) + T-1.8 (12) + T-1.9 (5) + T-1.10 (0) + T-1.11 (0) + T-1.12 (8) + T-1.13 (5) = **93 per-task projection**. Lower bound +40 (test collapse during impl); upper bound +100 (Phase 9/10/12 overshoot precedent). **Plan locks +50-100 fast tests.**
- **Sub-bundle 2:** T-2.0 (10) + T-2.1 (10) + T-2.2 (8) + T-2.3 (3) + T-2.4 (3) + T-2.5 (3) + T-2.6 (1) = **38 per-task projection**. **Plan locks +20-40 fast tests.**
- **Cumulative across Sub-bundle 1 + 2: +70-140 fast tests** (above brief §2.4 projection of +45-90; matches overshoot precedent at midline).
- **Final main HEAD post-arc-merge: ~4433-4503 fast tests** (was ~4363).

---

## §F Cassette runbook (HARD PREREQ for Sub-bundle 1; drafted in T-1.0)

### §F.1 Order types requiring cassette coverage

Per spec §6.5 OQ-E LOCK + brief §0.6:

1. **LIMIT BUY** — operator's predominant; CVGI fill_id=9 family.
2. **LIMIT SELL** — operator's predominant exit; LION fill_id=15 family.
3. **STOP FIRED** — FIRED stop with `executionLegs[]` populated; tests OQ-D Path A.
4. **MARKET BUY** — rare; verifies `executionLegs[]` field surfaces for MKT.

**Stretch:** STOP_LIMIT FIRED — verifies dual-tier `price` vs `stopPrice` vs `executionLegs[].price` shape.

### §F.2 Operator-paired recording session workflow

Pre-conditions: valid Schwab refresh-token (re-auth via `/schwab/setup` or CLI if expired); historical filled orders covering 4 types within last 30 days; `pytest-recording` dev dep installed.

Steps:

1. Verify production tokens DB: `swing schwab status --environment production` → CONFIGURED.
2. Record cassettes in `new_episodes` mode:
   ```powershell
   $env:VCR_RECORD = "new_episodes"
   pytest tests/integration/test_phase12_post_schwab_mapper_widening_e2e.py -v --record-mode=new_episodes
   ```
   Cassettes land at `tests/integrations/cassettes/schwab/test_e2e_<order_type>.yaml`.
3. Operator inspects each cassette via `git diff` for sensitive-field leakage:
   - `accountNumber` → `<account>` (or sanitization placeholder).
   - `accountHash` → sanitized.
   - `client_id` / `client_secret` / `access_token` / `refresh_token` / `code` → absent or `<masked>`.
4. Commit sanitized cassettes:
   ```bash
   git add tests/integrations/cassettes/schwab/
   git commit -m "test(schwab-cassette): record 4 order types for Sub-bundle 1"
   ```
5. Verify cassette replay:
   ```powershell
   $env:VCR_RECORD = "none"
   pytest tests/integration/test_phase12_post_schwab_mapper_widening_e2e.py -v
   ```
   Expected: all 5 PASS via replay.

### §F.3 Sanitization filter spec (extends `tests/conftest.py:88-110` `vcr_config`)

```python
@pytest.fixture(scope="session")
def vcr_config():
    return {
        "filter_headers": [
            "authorization", "cookie", "set-cookie",
            "schwab-client-correl-id", "schwab-client-channel",
            "schwab-client-customerid",
        ],
        "filter_query_parameters": [
            "auth", "accountNumber", "accountHash",
        ],
        "filter_post_data_parameters": [
            "client_id", "client_secret", "refresh_token",
            "access_token", "code",
        ],
        "before_record_response": _sanitize_schwab_response_body,
    }


def _sanitize_schwab_response_body(response):
    """Scrub accountNumber/accountHash + 32+ hex / 24+ base64 token-shape
    substrings from response body bytes. Per Phase 11 D redaction pattern."""
    import re
    body_bytes = response["body"].get("string", b"")
    if not body_bytes:
        return response
    body_text = body_bytes.decode("utf-8", errors="replace")
    body_text = re.sub(r'("accountNumber"\s*:\s*)"[^"]+?"', r'\1"<account>"', body_text)
    body_text = re.sub(r'("accountHash"\s*:\s*)"[^"]+?"', r'\1"<hash>"', body_text)
    body_text = re.sub(r'\b[a-f0-9]{32,}\b', '<hex-token>', body_text, flags=re.IGNORECASE)
    body_text = re.sub(r'\b[A-Za-z0-9+/=]{24,}={0,2}\b', '<base64-token>', body_text)
    response["body"]["string"] = body_text.encode("utf-8")
    return response
```

### §F.4 Staleness recovery runbook

When Schwab API drifts:

1. Identify drift: cassette-driven test fails with `SchwabSchemaParityError` / `KeyError` / `AttributeError` on previously-mapped field.
2. Refresh tokens: `swing schwab logout && swing schwab setup` (CLI OR web form).
3. Re-record cassettes (§F.2 step 2).
4. Operator diffs old vs new (sanitized fields excluded); inspects breaking changes.
5. Breaking change → follow-up dispatch updates mapper/comparator/classifier for new shape.

---

## §G Cassette acceptance criteria (per T-1.0 + T-1.13)

1. **Mapper byte-for-byte verification:** per cassette, `SchwabOrderResponse` mapping output asserted byte-for-byte (snapshot test). `executions` non-None for all 4 minimum types.
2. **`SchwabExecutionLeg` dataclass shape validates:** mapper does NOT raise during cassette replay; all legs construct via `__post_init__`.
3. **Comparator + classifier paths exercised:** each test fires `run_schwab_reconciliation` against tmp DB seeded with journal fill matching cassette's order; asserts (a) no false-positive emit when journal matches execution within tolerance; (b) Shape C tier-1 emit when journal records WRONG price; (c) Path B sentinel emit when cassette explicitly lacks `orderActivityCollection`.
4. **Sanitization invariant:** automated post-test scan asserts cassettes contain NO substring matching `accountNumber=\d{8,}` OR `accountHash=[a-f0-9]{32,}` OR `client_secret=`. Test fails build if sanitization breaks.
5. **Storage path:** all cassettes under `tests/integrations/cassettes/schwab/`.
6. **VCR config inheritance:** session-scoped `vcr_config` from `tests/conftest.py`; no per-test override needed unless test-specific.

---

## §H Per-sub-bundle operator-witnessed gate plan

### §H.1 Sub-bundle 1 gate (7-9 surfaces; production-write at S3+S4)

- **S1 — Inline test suite:** `pytest -m "not slow" -q -n auto` GREEN at ~4413-4493 fast (worktree-side; +50-130 net). 3 pre-existing phase8 walkthrough failures unchanged. Ruff `swing/` reports 18 E501 unchanged.
- **S2 — Cassette-driven mapper test PASS:** `pytest tests/integration/test_phase12_post_schwab_mapper_widening_e2e.py -v`. 5 tests PASS (4 order types + legitimate-typo Shape C).
- **S3 — PRODUCTION DRY-RUN reconciliation:** `swing journal reconcile-backfill --dry-run` against operator's production DB. Expected: NO new false-positive `entry_price_mismatch`/`close_price_mismatch` for CVGI/LION/future-fills. Operator pre-authorizes via plain-chat per Phase 12 C.D NEW lesson #2 (production-write classifier soft-block fires per-invocation).
- **S4 — PRODUCTION APPLY (OPTIONAL):** `swing journal reconcile-backfill --apply`. Operator's choice. If applied, verify no false-positive emit; `reconciliation_run` completes; `summary_json` counters zero or expected-non-zero.
- **S5 — Phase 10 dashboard banner count = 0** (unchanged; production clean post-merge).
- **S6 — CLAUDE.md gotcha amendment text reviewed by operator** (T-1.10). Confirms V2-RESOLVED top-section + V1 historical context + spec path + commit chain references.
- **S7 — `show-correction` CLI generic help-text addendum manually invoked + operator-acceptance:**
  ```bash
  swing journal discrepancy show-correction --help
  swing journal discrepancy override-correction --help
  swing journal discrepancy show-correction 1
  ```
  Operator verifies addendum text accuracy.
- **S8 — Ruff:** `ruff check swing/` reports 18 E501 unchanged.
- **S9 — (OPTIONAL) Spot-check production `schwab_api_calls` audit log + cassette consumption pattern.**

**Gate-pass criterion:** S1+S2+S3+S5+S6+S7+S8 must PASS; S4 + S9 optional. Orchestrator records explicit "S<N> PASS" per surface in return report.

### §H.2 Sub-bundle 2 gate (4-5 surfaces; web-driven via Chrome MCP)

- **S1 — Inline test suite:** `pytest -m "not slow" -q -n auto` GREEN at ~4453-4533 fast (worktree-side; +20-40 from Sub-bundle 1 baseline). Ruff 18 unchanged.
- **S2 — Chrome MCP `/schwab/status`:** renders production state + 3-state badge + refresh-token TTL countdown + audit summary table + environment switcher links + ZERO console errors.
- **S3 — Chrome MCP `/config`:** "External integrations" shows BOTH nav-links; click `/schwab/status` → navigates correctly + renders per S2.
- **S4 — `/schwab/setup` POST + HX-Redirect to `/schwab/status`:** operator pastes fresh callback URL; browser HX-redirects to `/schwab/status` (NOT `/config?schwab_setup=ok`); tokens DB updated; page renders refreshed TTL. (Conditional on operator wanting to re-auth at gate time; T-A.2 self-healing covers stale tokens.)
- **S5 — Ruff `swing/` reports 18 E501 unchanged.**

**Gate-pass criterion:** S1+S2+S3+S5 must PASS; S4 conditional.

---

## §I Open questions for orchestrator triage

**None.** All decisions LOCKED per spec §13 (25 items) + brief §0.3 (operator decisions) + plan-author additional locks (§D.3). No escalation past spec or brief disposition.

---

## §Z V2 candidates banked (NOT this dispatch; documented for future triage)

1. **OQ-F V2 follow-up — Multi-leg tier-1 auto-redirect** (`split_into_partials` auto-emit when confidence high; requires cascade analysis: confidence threshold + classifier dispatch state + auto-correct handler + CLI surface + operator-decided UX). Spec §6.6.
2. **Per-row `engine_version` metadata column on `reconciliation_corrections`** (requires schema v20; out of scope §1.3). Would enable per-row context-rendering in `show-correction` help instead of generic addendum. Spec §8.3.
3. **`/config?schwab_setup=ok` hard removal** (passive no-op retained one release window per Codex R1 m#2). Spec §7.3.
4. **Per-leg audit surfacing for tier-2 outside-tolerance VWAP** (currently one tier-1 emit per outside-tolerance VWAP; per-leg detail in `actual_value_json.execution_legs` audit-only). Spec §9.2.
5. **Schwab cassette runbook elevation** (currently V2-PLANNED per Phase 11 D gotcha; this dispatch ships runbook as part of Sub-bundle 1 cassette session — V2 candidate is first-class doc + scale order types + automate cassette-staleness detection in CI).
6. **`surface='web'` CHECK enum widening** (requires schema v20). Sub-bundle B + 2 use `surface='cli'` per Sub-bundle B precedent.
7. **schwabdev SDK version pin + extended compat test** (Sub-bundle B V2).
8. **Schwab token encryption-at-rest** via schwabdev `encryption=<key>` (Sub-bundle B V2).
9. **OQ-G per-row engine_version on reconciliation_corrections** for per-row context-rendering on `show-correction` (requires schema v20).
10. **Schwab API rate-limit cassette coverage** (recording 429 + 503 + auth_failed for exception-path testing).
11. **Fill auto-population at trade-entry time** (broader sub-bundle; spec §1.6 OUT-OF-SCOPE).
12. **Web Tier-2 discrepancy-resolution surface** (Sub-bundle C plan §I.3 V2; not this dispatch).
13. **Pass-2 LIFT scope** (single-leg single-matched-order tier-1 auto-redirect AND multi-leg `split_into_partials`; spec §6.6 V2 follow-up).

---

## §Self-review

**Spec coverage check:**

- §1.1-§1.6 operator-locked constraints → §C.4 + §D.1 items 1-6.
- §2.1-§2.3 current state recap + defect chain → T-1.13 cassette E2E + T-1.6 CVGI/LION walkthrough tests.
- §3.1-§3.3 target architecture → T-1.1+T-1.2+T-1.3+T-1.4+T-1.6+T-1.8+T-1.9.
- §4.1 `SchwabExecutionLeg` invariants → T-1.1 (12 tests; all 6 invariants).
- §4.2 tri-valued executions → T-1.2 (8 tests; None/[]/list).
- §4.3 mapper defensive parsing → T-1.3 (14 tests).
- §4.4 backward compat → T-1.2 8-positional + T-1.3 V1-no-orderActivity case.
- §5.1 `_compute_execution_price` → T-1.4 (10 tests).
- §5.2 comparator path + Shape C audit-key contract → T-1.6 (10 tests) + T-1.8 audit-key persistence test.
- §5.3 quantity-grain + mapper coherence-check → T-1.5 + T-1.7 + T-1.3.
- §6.1-§6.7 OQs → §D.1 items 17-23.
- §7.1-§7.6 T-B.7 web counterpart → T-2.0..T-2.6 (38 tests).
- §8.1-§8.3 housekeeping → T-1.10 + T-1.11 + T-1.12.
- §10.1-§10.6 walkthroughs → T-1.6 CVGI+LION+multi-leg+Path B+FIRED stop tests + T-1.13 cassette E2E + T-1.8 close_price_mismatch Shape C.
- §11 adversarial-watch items → addressed at task acceptance criteria level.

**Placeholder scan:** plan contains intentional `<DATE-OF-SUB-BUNDLE-1-MERGE>` forward-reference at T-1.10 step 2 (executing-plans phase fills at commit time). No other placeholders.

**Type consistency:** `_EXECUTION_AUDIT_KEYS` (frozenset of 3 strings) consistent T-1.6 + T-1.8 + T-1.13. `SchwabExecutionLeg` fields consistent across §A + §F + §G. `Shape C` predicate `source_keys == _SHAPE_C_EXPECTED_KEYS` consistent. `actual_value_json` key-set `{"price", "execution_legs", "schwab_order_id", "schwab_order_price"}` consistent T-1.6 emit shape + T-1.8 classifier predicate.

---

*End of plan. Sub-bundle 1 first (architectural; 14 tasks; +50-100 fast tests; cassette session HARD PREREQ); Sub-bundle 2 after (web counterpart; 7 tasks; +20-40 fast tests); total +70-140 fast tests; schema unchanged at v19; 4-5 Codex rounds expected.*
