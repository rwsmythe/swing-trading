# Implementation Plan — 19-F: orphan-tolerant discrepancy resolution

**Arc:** 19-F. **Brief:** [`docs/cash-review-orphan-resolve-19f-commissioning-brief.md`](cash-review-orphan-resolve-19f-commissioning-brief.md).
**Type:** writing-plans (this document is the deliverable; NO implementation code ships in this dispatch).
**Base:** `main` @ `02583d2e` (worktree `.worktrees/19f-cash-orphan-resolve`).
**Schema:** v31 — **NO migration** (see §2 F2 cross-check). **No `swing/data`/`swing/trades` file touched except the F4 carve-out `swing/trades/schwab_reconciliation.py`.**

---

## RD + CHARC rulings (folded 2026-07-04)

- **RD plan-stage (LIGHT): PASS.** Measurement confirmed -- resolving disc 73 changes NO ledger row (post-D19 `current_equity` already correct; pure bookkeeping legibility). Audit-trail semantics satisfy RD's stake (terminal `acknowledged_immaterial` via the pre-existing `resolve_discrepancy`; orphan-marked reason naming the missing `{table} id={rid}`). The live-heal GUI witness is binding as planned.
- **CHARC: Task D CONFIRMED IN SCOPE** (F4's "the CLI tier-2 path") -- keep it. The premise nuance is accepted + owned on CHARC's record (correction-of-record: "no SUPPORTED tier-2 path handles an FK-orphan + the GUI is broken"). The ungated `discrepancy resolve` design gap landed as CHARC debt-register **D22** (candidate fix = a pending-state gate; adjudicate at a lull / Phase-19 close) -- correctly OUT of 19-F scope.

## §0. The demand + the one-line fix

A dashboard **cash-review badge** (operator complaint 2026-07-02) is lit by **reconciliation discrepancy 73** and cannot be cleared through the GUI resolve form nor the CLI `resolve-ambiguity` (tier-2) surface. Discrepancy 73 references `cash_movement_id=5`, a row RD **raw-DELETED 2026-06-21** in the D19 double-debit correction. The tier-2 resolve path loads the referenced ledger row to snapshot its pre-correction value and **raises** when the row is gone. The fix: recognize the **FK-orphan** state (a discrepancy whose referenced subject row no longer exists) at both resolve surfaces and route it to a **terminal `acknowledged_immaterial` resolution** carrying an orphan-marked `resolution_reason`, instead of the FK-requiring tier-2 resolver.

---

## §1. PLAN STEP 1 — the reproduced live failure (DONE, read-only)

Reproduced 2026-07-04 against a **copy** of the live DB (`~/swing-data/swing.db` → scratch; the live DB was never written). Live discrepancy 73 (read-only SELECT):

```
discrepancy_id   = 73
run_id           = 62
discrepancy_type = 'cash_movement_mismatch'
trade_id/fill_id = None / None
cash_movement_id = 5            # ABSENT from cash_movements {1,2,3,4,6,7}
field_name       = 'net_amount'
expected_value_json = {"amount": 372.48, "date": "2026-06-15", "kind": "withdraw"}
actual_value_json   = {"matched": null}
resolution       = 'pending_ambiguity_resolution'
ambiguity_kind   = 'schwab_returned_no_match'
resolution_reason= 'cash_movement_mismatch on (cash_movement_id=5): no matching cash movement ...'
created_at       = '2026-06-19T21:07:27.837'
schema_version   = 31
```

**Where each surface fails TODAY (reproduced, not assumed):**

1. **Web GET** `/reconcile/discrepancy/73/resolve` — **SUCCEEDS** and renders the misleading tier-2 form.
   - Not the untracked-broker orphan branch (`_is_orphan_discrepancy` → False; type is `cash_movement_mismatch`, not `untracked_broker_position`).
   - Not the simple-acknowledge branch (`swing/web/routes/reconcile.py:447-451`): the gate requires `disc.ambiguity_kind is None`, but disc 73 has `ambiguity_kind='schwab_returned_no_match'` → SKIPPED.
   - Falls through the tier-2 pending gate (`:459-462`) → `build_reconcile_discrepancy_resolve_vm` (`swing/web/view_models/reconcile.py:729`). The builder reads only the persisted JSON envelopes (never the `cash_movements` table) → **renders the form offering `mark_unmatched` + `operator_truth`** (verified: `vm.choices == ['mark_unmatched','operator_truth']`). Both are dead ends.

2. **Web POST** `/reconcile/discrepancy/73/resolve` (choice `mark_unmatched`) — **FAILS, 400 loop.**
   - Route (`swing/web/routes/reconcile.py:1349`) calls `apply_tier2_resolution(...)` → `_handle_mark_unmatched` → `_handle_no_mutation_audit` (`reconciliation_auto_correct.py:1729`) → `_resolve_affected_target(disc)` returns `("cash_movements", 5)` (`:1340`) → `_read_journal_value(conn,"cash_movements",5,"net_amount")` (`:1363`) → `SELECT amount FROM cash_movements WHERE id=5` → `row is None` → **`ValueError("cash_movements row id=5 not found while reading pre-correction value")`** (`:1387-1391`).
   - Route catches the `ValueError` (`:1430`), re-reads on a fresh conn → still `pending_ambiguity_resolution` (no concurrent writer) → NOT the 409 branch → `_render_form_with_error(error_band_message=str(exc))` → **HTTP 400 re-render of the same tier-2 form with a red error band `"cash_movements row id=5 not found while reading pre-correction value"`**. The row stays pending (BEGIN IMMEDIATE rolled back); the badge stays lit; every re-submit repeats. Endless loop. (`operator_truth` fails identically — `_handle_multi_field_correction` also reads the missing row.)

3. **CLI** `swing journal discrepancy resolve-ambiguity 73 --choice mark_unmatched --reason ...` — **FAILS, exit 2.**
   - Same `apply_tier2_resolution` → same `ValueError`, caught at `swing/cli.py:3183` → `click.UsageError(str(e))` → **exit code 2, stderr `"Error: cash_movements row id=5 not found while reading pre-correction value"`** (reproduced via `CliRunner`).

**Fix shape validated end-to-end on the copy** (see §4): `resolve_discrepancy(conn, discrepancy_id=73, resolution='acknowledged_immaterial', resolution_reason=<orphan marker>, require_current_resolution='pending_ambiguity_resolution')` → resolution becomes `acknowledged_immaterial`, `ambiguity_kind` cleared to `NULL` (cross-column CHECK satisfied), badge clause-1 pending count `1 → 0` → badge clears.

### §1.1 PREMISE FINDING — STOP-and-consider for the orchestrator (blunt call-out)

The brief/diagnosis says the badge is "unresolvable via CLI **or** GUI." **That overstates the CLI half.** There is a SECOND CLI command — `swing journal discrepancy resolve` (`swing/cli.py:3542`, distinct from `resolve-ambiguity`) — that calls `resolve_discrepancy` **directly with no pending-state gate**. Reproduced on the copy:

```
$ swing journal discrepancy resolve 73 --resolution acknowledged_immaterial --reason "subject row deleted in D19"
Discrepancy 73 resolved: resolution=acknowledged_immaterial      # exit 0
# -> resolution='acknowledged_immaterial', ambiguity_kind=None
```

So an operator ALREADY has a working CLI escape hatch today (it just isn't the tier-2 `resolve-ambiguity` command, and nothing surfaces it for this row — the dashboard badge links to the GUI resolve form, not this command). Consequences for scope:
- The **GUI is genuinely broken** and is the operator's actual complaint; the §4-brief BINDING gate is a live GUI heal. The GUI fix is load-bearing and unaffected by this finding.
- The **CLI `resolve-ambiguity` fix is UX-consistency polish**, not the sole unblock — a slightly-different-command CLI path already works.
- **Orchestrator decision requested (STOP-and-ask):** keep the CLI `resolve-ambiguity` orphan-awareness in scope (recommended — an operator who reaches for the tier-2 command deserves a clean terminal path, not `"row id=5 not found"`), OR descope the CLI change and rely on the existing `discrepancy resolve` command. This plan includes the `resolve-ambiguity` change (§3.C) but marks it as the orchestrator's call.
- Adjacent observation (NOT in scope, flagged only): `discrepancy resolve` has no pending-state gate, so it can terminally resolve ANY `pending_ambiguity_resolution` row (orphan or legitimate tier-2) without going through the choice menu or emitting a correction row. That is a pre-existing design gap, out of scope here; noted for CHARC.

---

## §2. Design + the CHARC F1–F4 conditions

### The mechanism: an FK-orphan predicate (F3)

Add one public helper to the **F4 carve-out** `swing/trades/schwab_reconciliation.py` — the single mechanism that recognizes ANY raw-delete orphan (D19's interim doctrine keeps raw-delete as the only manual row removal, so recurrence across `cash_movements`/`fills`/`trades` is expected):

```python
def orphaned_affected_target(
    conn: sqlite3.Connection, disc: Any,
) -> tuple[str, int] | None:
    """Return (table, row_id) of a discrepancy's referenced FK subject row when
    that row NO LONGER EXISTS (a raw-delete orphan, e.g. D19's cash_movement_id=5),
    else None.

    Mirrors reconciliation_auto_correct._resolve_affected_target precedence
    (fill_id -> cash_movement_id -> trade_id) so it names the EXACT row the
    tier-2 resolver would fail to read. (Note: the real _resolve_affected_target
    RAISES on all-NULL FKs -- the account_equity_snapshots fallback in its
    docstring is not in the code; irrelevant here because this helper returns
    None for all-NULL, ceding those rows to their own branches.) Returns None
    when:
      - no FK is set (all-NULL: equity_delta / snapshot_mismatch / the
        source-direction missing_journal_row rows -> handled by their own
        branches, NOT FK-orphans), OR
      - the referenced FK row EXISTS (a live tier-2 row -> must reach the
        tier-2 form unchanged; the no-regression lock).
    """
    if disc.fill_id is not None:
        table, rid, col = "fills", int(disc.fill_id), "fill_id"
    elif disc.cash_movement_id is not None:
        table, rid, col = "cash_movements", int(disc.cash_movement_id), "id"
    elif disc.trade_id is not None:
        table, rid, col = "trades", int(disc.trade_id), "id"
    else:
        return None
    exists = conn.execute(
        f"SELECT 1 FROM {table} WHERE {col} = ?", (rid,)
    ).fetchone()
    return None if exists is not None else (table, rid)
```

- The `table`/`col` values come from a CLOSED internal set (never operator input) — the f-string interpolation is safe (same discipline as `_read_journal_value`).
- **Cannot hijack a live tier-2 row**: if the FK row exists → returns None → the row reaches the tier-2 form exactly as today. This is the structural guarantee behind the §3 no-regression lock.

### F1 — append-only / audit discipline (HONORED)

The resolution is a **SELECT-then-UPDATE** of the existing discrepancy row via the pre-existing `resolve_discrepancy` (`swing/trades/reconciliation.py:568`), which under `BEGIN IMMEDIATE` re-reads the row, then `repo.update_discrepancy_resolution(...)` (a plain `UPDATE`, never `REPLACE`/`DELETE` — the INSERT-OR-REPLACE gotcha is avoided; NO new PK, NO child-row cascade). The orphan state lands in `resolution_reason`:

```
"orphan-resolved (subject row gone): {table} id={row_id} no longer exists "
"(raw-deleted; e.g. D19 double-debit correction). {operator_reason}"
```

`resolution_reason` is therefore ALWAYS non-empty for an orphan (system marker + optional operator text) so the audit trail explicitly says WHY the row was resolved subject-less. No correction row is emitted (there is no journal mutation) — the discrepancy row's `resolution` / `resolution_reason` / `resolved_by` / `resolved_at` ARE the audit envelope, exactly as the existing untracked-orphan + simple-acknowledge branches do.

### F2 — NO schema; existing enum (HONORED, cross-checked)

**Chosen `resolution` value: `acknowledged_immaterial`.** Cross-check against the CURRENT (migration `0031`) constraints (the #11 gotcha — verified on disk, not assumed):

- `resolution` CHECK enum (`0031_untracked_broker_position.sql:55-60`) includes `'acknowledged_immaterial'` → **no widening**.
- Cross-column CHECK (`:71-83`): `acknowledged_immaterial` is NOT in the pending set, so it requires `ambiguity_kind IS NULL`. `resolve_discrepancy` clears `ambiguity_kind` in the SAME UPDATE when the existing row has one (`clear_ambiguity_kind = existing.ambiguity_kind is not None`, `reconciliation.py:662`) → the transition `(schwab_returned_no_match, pending) → (NULL, acknowledged_immaterial)` **satisfies the cross-column CHECK** (verified live on the copy).
- `acknowledged_immaterial ∈ _MANUAL_RESOLVE_ALLOWED_RESOLUTIONS` and **∉ `_SERVICE_OWNED_RESOLUTIONS`** (verified live) → it is settable through `resolve_discrepancy`.

**Why NOT `operator_resolved_ambiguity`** (the brief's other candidate): it IS service-owned (`operator_resolved_ambiguity ∈ _SERVICE_OWNED_RESOLUTIONS`, verified live) → `resolve_discrepancy` REJECTS it (`reconciliation.py:612`); setting it would require `apply_tier2_resolution` — the exact FK-requiring path that fails on the orphan. It also keeps `ambiguity_kind` non-null (pending-set member), leaving the row in a semi-pending shape. `acknowledged_immaterial` is both the mechanically-clean AND semantically-honest choice, and it is the value the existing orphan / simple-ack branches already use for the analogous "cannot route through tier-2" cases (consistency).

**NO CHECK-enum widening is required → NO schema tripwire is hit.** (If, during execution, a reviewer argues a widening is needed, that IS a schema tripwire → STOP and route back to CHARC. This plan asserts, with the live cross-check above, that it is not.)

### F3 — mechanism, not a one-time patch (HONORED)

`orphaned_affected_target` keys on "referenced FK row missing," not on discrepancy 73 / not on `cash_movement_mismatch` specifically. Any future raw-delete orphan (a deleted `fills`/`trades`/`cash_movements` row referenced by a pending or unresolved discrepancy) resolves through the SAME path. **Detection stays as-is** — the badge predicate (`dashboard.py:71-95`) is UNTOUCHED; the badge lighting on a pending orphan is CORRECT (it demands an operator decision); the fix makes the decision POSSIBLE, it does not auto-resolve.

### F4 — scope (HONORED)

Touched: `swing/trades/schwab_reconciliation.py` (the carve-out — the predicate) + `swing/web/routes/reconcile.py` + `swing/web/view_models/reconcile.py` (reused VM, no new class strictly required — see §3.B) + optionally one template touch (§3.B) + `swing/cli.py` (the `resolve-ambiguity` command, pending the §1.1 decision) + tests. **NOT touched:** `swing/trades/reconciliation.py` (`resolve_discrepancy` used AS-IS), `swing/trades/reconciliation_auto_correct.py`, any other `swing/trades`/`swing/data` file, and the badge predicate in `dashboard.py`.

---

## §3. The implementation tasks (TDD, one red→green→commit each)

**Test-seeding discipline (BINDING for every task below).** The dangling-FK orphan fixture MUST be raw-INSERTed with **`PRAGMA foreign_keys = OFF`** on the seeding connection. Rationale (verified against live data + migration `0031`): `cash_movement_id` carries `ON DELETE SET NULL`, so the live orphan state — disc 73 STILL holding `cash_movement_id=5` after row 5's deletion — can only exist because the raw delete ran with FK enforcement OFF; and an FK-ON connection would REJECT an INSERT of a discrepancy referencing a nonexistent `cash_movement_id`. `sqlite3.connect` defaults FK OFF, but the app's `connect`/`open_connection` may enable it — tests seeding the corrupt state must be explicit. (The subsequent resolve is verified to succeed even under `PRAGMA foreign_keys=ON` — the `resolve_discrepancy` UPDATE does not touch the FK column, so SQLite does not re-validate it; confirmed live on the copy.)

Ordering note for BOTH web handlers: the new FK-orphan branch is inserted **immediately after the untracked-broker orphan branch and BEFORE the simple-acknowledge branch**. Rationale: the untracked-orphan branch is disjoint (all-FK-null); the simple-ack branch requires `ambiguity_kind IS NULL` + a live row, so for the badge-lighting case (a PENDING cash orphan, `ambiguity_kind` set) it does not fire anyway — but placing FK-orphan first guarantees the orphan-marked reason wins whenever the subject is genuinely gone, and cannot regress a live simple-ack row (that row's FK exists → predicate returns None). The tier-2 pending gate stays last.

### Task A — the FK-orphan predicate (carve-out)
`swing/trades/schwab_reconciliation.py`: add `orphaned_affected_target` (§2). Export it (module `__all__` if present, else public name).
- **Test** (`tests/trades/test_schwab_reconciliation_orphan.py` or the existing schwab_reconciliation test module): raw-INSERT a discrepancy referencing a nonexistent `cash_movement_id` → predicate returns `("cash_movements", <id>)`; a discrepancy referencing an EXISTING `cash_movement_id` → returns `None`; an all-FK-null discrepancy → `None`; a fill-orphan and a trade-orphan → the right `(table,id)`. (Seed the orphan via RAW `conn.execute` INSERT — the 18-B.1 bypass-the-write-path discipline: this tests DETECTION of pre-existing bad state, not the write path.)

### Task B — web GET: offer the terminal path for FK-orphans
`swing/web/routes/reconcile.py` GET handler. After the untracked-orphan branch (`:416-440`), before the simple-ack branch (`:447`), add:

```python
orphan_target = orphaned_affected_target(conn, disc)   # local import per the established pattern
if orphan_target is not None:
    if disc.resolution not in _FK_ORPHAN_CLEARABLE_RESOLUTIONS:   # {'unresolved','pending_ambiguity_resolution'}
        return _render_error(..., status_code=409, error_kind="already_resolved", ...)
    return _render_fk_orphan_acknowledge_form(request, disc, orphan_target, ...)
```

- **Reuse `ReconcileSimpleAcknowledgeVM` + `reconcile_simple_acknowledge.html.j2`** (it already carries `heading`/`explanation`/`ticker`/`delta_text`/`prior_resolution_reason`/`error_band_message` and is HTMX-correct — `hx-post` + `hx-headers '{"HX-Request":"true"}'` + `hx-target`). Add a thin `_render_fk_orphan_acknowledge_form` helper that builds the SAME VM with **orphan-specific `heading`/`explanation`** prose (ASCII-only per the cp1252 gotcha), e.g. heading `"Resolve orphaned discrepancy"`, explanation `"The referenced {table} row (id={rid}) no longer exists (it was manually deleted, e.g. the D19 double-debit correction). The tier-2 choices need that row, so acknowledge here to clear the finding to acknowledged_immaterial."` No new VM class and no schema — keeps the locked simple-ack path byte-unchanged (do NOT mutate `_render_simple_acknowledge_form` or `_SIMPLE_ACK_PROSE`). The template's hardcoded CLI-parity line (`swing journal discrepancy resolve {id} --resolution acknowledged_immaterial`) is ACCURATE for the orphan path (that command genuinely resolves an orphan — the §1.1 premise finding) so reuse is safe; no template edit required.
- **Test** (`tests/web/`): raw-INSERT the orphan pending row (disc-73-shape: `cash_movement_mismatch`, `pending_ambiguity_resolution`, `ambiguity_kind='schwab_returned_no_match'`, `cash_movement_id` = a nonexistent id) → `GET` returns 200 with the acknowledge form (assert `data-simple-acknowledge-form="true"` present, and NO tier-2 choice-menu markers). A NON-orphan pending row (existing `cash_movement_id`, or the `unmatched_open_fill` tier-2 shape with a live `fill_id`) → GET renders the tier-2 form **byte-identical to today** (the no-regression lock).

### Task C — web POST: apply the terminal resolution
`swing/web/routes/reconcile.py` POST handler. In the mirrored position (after the untracked-orphan POST branch `:867-971`, before the simple-ack POST branch `:979`), add the FK-orphan branch. It mirrors the simple-ack POST block (established near-duplicate pattern in this file) EXCEPT the `resolution_reason` is the orphan marker:

```python
orphan_target = orphaned_affected_target(conn, disc)
if orphan_target is not None:
    if disc.resolution not in _FK_ORPHAN_CLEARABLE_RESOLUTIONS:
        return _render_error(..., 409, "already_resolved", ...)
    table, rid = orphan_target
    from swing.trades.reconciliation import DiscrepancyResolutionStateError, resolve_discrepancy
    orphan_reason = _compose_orphan_reason(table, rid, resolution_reason)   # marker + optional operator text
    try:
        resolve_discrepancy(
            conn, discrepancy_id=discrepancy_id,
            resolution="acknowledged_immaterial",
            resolution_reason=orphan_reason,          # ALWAYS non-empty (marker present)
            resolved_by="operator_web",               # F2 LOCK surface attribution
            require_current_resolution=disc.resolution,   # TOCTOU close (mirrors orphan/simple-ack)
        )
    except sqlite3.OperationalError as exc: ...        # 503 db_unavailable (transient-only)
    except DiscrepancyResolutionStateError: ...        # 409 already_resolved (concurrent winner)
    except ValueError as exc: ...                      # 400 re-render the ack form with the error band
    redirect_target = f"/dashboard?reconcile_resolved=disc-{discrepancy_id}"
    if request.headers.get("HX-Request") == "true":
        return Response(status_code=204, headers={"HX-Redirect": redirect_target})
    return RedirectResponse(url=redirect_target, status_code=303)
```

- Reuse `_FK_ORPHAN_CLEARABLE_RESOLUTIONS = frozenset({"unresolved","pending_ambiguity_resolution"})` (a new module constant, mirroring `_ORPHAN_CLEARABLE_RESOLUTIONS`).
- **HTMX contract (browser-only gotcha family):** success = `204` + `HX-Redirect`; non-HTMX = `303`. The reused template already carries `hx-headers '{"HX-Request":"true"}'`. The redirect target `/dashboard` is a registered route (verify in the test).
- **Tests** (`tests/web/`):
  - **Round-trip / write-then-read:** raw-INSERT the orphan pending row → `POST` (HX-Request) → 204 + `HX-Redirect: /dashboard?reconcile_resolved=disc-<id>`; re-read the row → `resolution='acknowledged_immaterial'`, `ambiguity_kind IS NULL`, `resolution_reason` starts with the orphan marker + names the missing `{table} id={rid}`; then assert `_compute_cash_coherence_badge(conn)` returns `False` (for a DB whose ONLY badge-trigger was this row). Compute the assertion under both pre-fix (400 loop) and post-fix (204 + resolved) so the test distinguishes.
  - **Idempotency (SELECT-first-before-validation):** a SECOND POST on the now-`acknowledged_immaterial` orphan (row still missing → predicate still returns `(table,id)`) → `disc.resolution` not in the clearable set → **409 `already_resolved`** (no re-mutation, no 500). The GET on the same terminal orphan → 409 too.
  - **No-regression:** a live (non-orphan) pending tier-2 row → POST behaves byte-identical to today (routes to `apply_tier2_resolution`, emits a correction, 204).

### Task D — CLI `resolve-ambiguity` orphan-awareness  *(scope pending §1.1 orchestrator decision)*
`swing/cli.py:discrepancy_resolve_ambiguity_cmd`. Detect the orphan and short-circuit to the terminal resolution (symmetric with the web + the existing `discrepancy resolve` command). **Placement (LOAD-BEARING):** the orphan short-circuit must run AFTER `get_discrepancy` (`:3041`) but **BEFORE the existing `d.ambiguity_kind is None` guard (`:3046-3054`)** — that guard rejects any `ambiguity_kind IS NULL` row, so an `unresolved` FK-orphan (a raw-deleted fill/trade referenced by an `unresolved`, ambiguity_kind-null discrepancy) would be wrongly rejected if the guard fired first. Running the orphan short-circuit before the guard keeps the CLI clearable set `{unresolved, pending_ambiguity_resolution}` symmetric with the web. (disc 73 is pending with `ambiguity_kind` set, so the guard would not fire for it anyway — but the mechanism must handle unresolved orphans too.)

```python
from swing.trades.schwab_reconciliation import orphaned_affected_target
orphan_target = orphaned_affected_target(conn, d)
if orphan_target is not None:
    table, rid = orphan_target
    from swing.trades.reconciliation import resolve_discrepancy
    resolve_discrepancy(
        conn, discrepancy_id=discrepancy_id,
        resolution="acknowledged_immaterial",
        resolution_reason=_compose_orphan_reason(table, rid, reason),
        resolved_by="operator",
        require_current_resolution=d.resolution,
    )
    click.echo(
        f"resolved orphan discrepancy {discrepancy_id} (referenced {table} "
        f"id={rid} no longer exists) to acknowledged_immaterial"
    )
    return
```

- **`--choice` handling (guard ordering is LOAD-BEARING).** For an orphan the tier-2 choices are inapplicable (mirrors the web, which shows no choice menu). Relax `--choice` from `required=True` to `required=False`. Making it optional is safe ONLY if EVERY `choice_code` dereference is guarded — verified against live code:
  - The service-owned-value check (`swing/cli.py:3021-3024`) ALREADY None-guards (`choice_code is not None and choice_code.strip()...`) — safe when omitted.
  - The menu-dispatch block (`:3070-3103`: `choice_code.startswith(...)` / `choice_code in static_codes`) does NOT None-guard — it would `AttributeError`/mis-branch on `None`.
  So place the flow as: (1) service-owned check (unchanged, already None-safe) → (2) `conn` open + `get_discrepancy` → (3) **orphan short-circuit** (`orphaned_affected_target` → terminal resolve + return; BEFORE the `d.ambiguity_kind is None` guard per the placement note above) → (4) the existing `d.ambiguity_kind is None` guard (non-orphans only) → (5) **non-orphan guard** `if choice_code is None: raise click.UsageError("--choice is required")` → (6) the existing menu-dispatch block. This keeps the NON-orphan contract byte-identical (still exits 2 when `--choice` is omitted) while an orphan resolves with just `--reason`. `--reason` stays `required=True`. (Alternative if the orchestrator prefers zero signature churn: keep `--choice required=True`, validate it against the menu, but route to the orphan terminal resolver — noted, not preferred, because it forces the operator to type a moot choice.)
- Keep the `field_name == 'missing_journal_row'` source-direction path unchanged: those rows are all-FK-null → `orphaned_affected_target` returns None → they route to `apply_source_direction_resolution` exactly as today.
- **Tests** (`tests/cli/` or `tests/`): via `CliRunner` against a raw-INSERTed orphan pending row → orphan short-circuit resolves to `acknowledged_immaterial` (exit 0, echo names the missing `{table} id={rid}`, `ambiguity_kind` cleared, orphan-marked reason persisted). A NON-orphan pending row → the menu/`apply_tier2_resolution` path is byte-identical to today (assert a live `mark_unmatched` still emits a correction + resolves to `operator_resolved_ambiguity`). Omitting `--choice` on a NON-orphan → UsageError exit 2 (contract preserved). ALREADY-resolved orphan → `require_current_resolution` raises `DiscrepancyResolutionStateError` → surfaced as `ClickException`/`UsageError` (idempotent-return; no re-mutation). Also test an **UNRESOLVED FK-orphan** (ambiguity_kind NULL — e.g. a raw-deleted fill referenced by an unresolved discrepancy) → the orphan short-circuit resolves it (proving it is NOT rejected by the `d.ambiguity_kind is None` guard — the placement lock).

### Task E — the shared orphan-reason composer
A small pure helper `_compose_orphan_reason(table, rid, operator_reason) -> str` (marker + optional operator text). Place it where both the web route and the CLI can import it WITHOUT crossing the F4 scope — recommend it live alongside `orphaned_affected_target` in `swing/trades/schwab_reconciliation.py` (the carve-out) so both surfaces single-source it. Pure, ASCII-only.

---

## §4. Live fix-shape validation already performed (evidence for the plan)

On a copy of the live DB (read-only w.r.t. the original), the exact `resolve_discrepancy(... acknowledged_immaterial ..., require_current_resolution='pending_ambiguity_resolution')` call against disc 73:
- resolution `pending_ambiguity_resolution → acknowledged_immaterial`; `ambiguity_kind schwab_returned_no_match → NULL` (cross-column CHECK satisfied, no CHECK violation raised);
- orphan-marked `resolution_reason` persisted;
- badge clause-1 pending count `1 → 0` → `_compute_cash_coherence_badge` clears.
Enum membership verified live: `acknowledged_immaterial ∈ _MANUAL_RESOLVE_ALLOWED_RESOLUTIONS`, `∉ _SERVICE_OWNED_RESOLUTIONS`; `operator_resolved_ambiguity ∈ _SERVICE_OWNED_RESOLUTIONS`.

---

## §5. Gates (per brief §4)

1. **RD plan-stage review, LIGHT** — audit-trail semantics of resolving against a deleted subject; measurement note: resolving the discrepancy changes NO ledger row (`current_equity` is already correct post-D19) — pure bookkeeping legibility.
2. **Executing gates:** `review-strong` + `codex-auto-review`; full fast suite green BEFORE the review; `ruff check swing/`; merged-head no-false-green re-run.
3. **BINDING operator witness — the LIVE HEAL:** the operator resolves discrepancy 73 through the new GUI path in a real browser (the HTMX `hx-headers`/`HX-Redirect`/`204`-not-`303` family applies) and the dashboard cash-review badge disappears. The complaint clearing IS the acceptance.
4. The ORCHESTRATOR posts the return report to `charc,rd` AFTER its QA.

## §6. Risks / notes

- **§1.1 premise finding** — an existing `discrepancy resolve` CLI escape hatch already clears disc 73; the CLI portion (Task D) is UX-consistency, not the sole unblock. Orchestrator decides Task D's inclusion.
- **No-regression lock** rests entirely on `orphaned_affected_target` returning `None` for a live FK row; Task A + the Task B/C/D no-regression tests pin it.
- **Idempotency** rests on the clearable-resolution gate (SELECT-first) + `require_current_resolution` (atomic TOCTOU close under `BEGIN IMMEDIATE`).
- **No schema, no new dependency, no migration.** If execution surfaces a genuine CHECK-enum-widening need, that is a schema tripwire → STOP and route to CHARC.
