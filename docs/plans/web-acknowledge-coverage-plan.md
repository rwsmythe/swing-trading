# Implementation plan — web simple-acknowledge coverage for plain-unresolved discrepancies (Phase-18)

**Status:** writing-plans deliverable (PLAN-ONLY — NO production code, NO tests committed). **Spec / settled design:** `docs/web-acknowledge-coverage-commissioning-brief.md` (committed `4db593f5`; the type allowlist LOCKED at `ab8fd39f`; the CHARC-verified §1 grounding + §3 LOCKED allowlist + §4 test obligations + §5 gates). **Lane:** CHARC — web-layer only; it only CALLS the existing public `resolve_discrepancy`; NO `swing/trades` or `swing/data` carve-out, NO schema. **Author:** writing-plans implementer (`implementer-opus-high`). **Date:** 2026-06-20. **Worktree base:** `main` HEAD `34fc5a63`.

The design is SETTLED by the brief — this plan grounds it on disk and lays out the TDD task breakdown + the discriminating tests with pre/post arithmetic; it does NOT re-open the design.

---

## 0. BLOCKING OPEN QUESTIONS for CHARC

**NONE.** The load-bearing Step-3 conditional (the migration-0031 cross-column CHECK admits `unresolved -> acknowledged_immaterial` for BOTH `cash_movement_mismatch` AND `equity_delta` with NO schema/CHECK change) **PASSED** — see §3. Every brief §0/§1/§2 grounding fact re-grounded clean on disk; line numbers drifted (the brief was authored against an earlier `main`; this plan re-anchors them). The grounding turned up **one MATERIAL strengthening OBSERVATION** (Appendix A, O1): the misleading "no longer in pending_ambiguity_resolution state" copy is **hardcoded in the template** (`reconcile_discrepancy_resolve_error.html.j2:11`) in addition to the two Python handler messages — so the honest-copy fix needs a NEW `error_kind` with its own template branch, not merely editing the Python message strings (the `already_resolved` template branch ignores `vm.error_message`). This is within the authorized web-layer scope (a new free-string `error_kind` value + a new template `{% elif %}` branch — no schema, no enum CHECK); it is NOT a §0 blocker, but it is the single fact that, if missed by the executing implementer, would leave the misleading copy partially live. The authorized scope (web route + VM + template + tests, calling the existing public `resolve_discrepancy`) is sufficient to implement the full settled design.

---

## 1. Overview + the settled design (restated)

**Problem (brief §0).** The web resolve window `GET/POST /reconcile/discrepancy/{id}/resolve` handles exactly TWO shapes:
1. **Orphan** — `untracked_broker_position` with `trade_id IS NULL` (`_is_orphan_discrepancy`) -> a simple acknowledge form (18-H.6.1).
2. **Tier-2 ambiguity** — `resolution == 'pending_ambiguity_resolution'` + non-null `ambiguity_kind` -> the choice-menu / custom-JSON resolution form.

A plain-`unresolved` discrepancy that is NEITHER — e.g. `cash_movement_mismatch` (the live "id 72" recurring monthly-deposit mismatch) or `equity_delta` (routed to `unresolved` by the limbo fix `006a0571` so it is operator-cleanable) — falls through to the tier-2 state guard (`reconcile.py:331-350` GET, `:820-840` POST) and gets a **409 with a MISLEADING message** ("no longer in pending_ambiguity_resolution state" — it was NEVER in that state). The GUI surfaces these discrepancies (banner + drill-downs) but cannot clear them; the operator must drop to the CLI. This arc closes that loop — notably completing the limbo fix, which made `equity_delta` cleanable-as-unresolved but left no GUI path to clear it.

**Settled design (brief §2/§3).** Generalize the orphan acknowledge branch into a **simple-acknowledge branch** governed by an **EXPLICIT ENUMERATED ALLOWLIST CONSTANT**:

```python
# swing/web/routes/reconcile.py — NEW module-level constant.
# Explicit enumerated allowlist (NOT "all material=0", NOT MATERIAL_BY_TYPE-derived)
# so a FUTURE material=0 type is never silently auto-acknowledgeable.
_SIMPLE_ACKNOWLEDGEABLE_TYPES: frozenset[str] = frozenset(
    {"cash_movement_mismatch", "equity_delta"}
)
```

For an allowlisted `unresolved` (or legacy `pending_ambiguity_resolution`, mirroring the orphan branch's existing `_ORPHAN_CLEARABLE_RESOLUTIONS` widening) row, render the simple acknowledge form and POST -> `resolve_discrepancy -> acknowledged_immaterial` (the EXACT orphan POST path, `reconcile.py:732-818`, with its TOCTOU/`require_current_resolution` race ladder preserved). The existing orphan case (`untracked_broker_position`, `trade_id IS NULL`) stays UNCHANGED — it keeps its own branch + its own wording.

**Additive / guard-only:** the tier-2 ambiguity branch and every non-allowlisted path stay byte-unchanged; this only ADDS coverage for the two allowlisted types that today hit the misleading 409.

**Fix the misleading copy (GET + POST):** for a NON-allowlisted, non-tier-2 unresolved discrepancy (an unresolved row whose type is not in the allowlist AND is not the orphan AND is not pending-ambiguity — e.g. a material=1 `stop_mismatch` left `unresolved`), the error copy must stop claiming "no longer in pending_ambiguity_resolution state" (it never was). Render an HONEST message via a NEW `error_kind` (`not_web_acknowledgeable`) whose template branch says, e.g., "This discrepancy type is not web-acknowledgeable; resolve it via the CLI." See O1 — the misleading copy is hardcoded in the template, so the fix is a new error_kind + new template branch, NOT just a Python message edit.

**Template decision (brief leaves this to writing-plans): a THIN SIBLING template `reconcile_simple_acknowledge.html.j2`.** Justification: the existing `reconcile_orphan_acknowledge.html.j2` hardcodes orphan-specific prose (title "Acknowledge untracked broker position", heading "Untracked broker position", and the "The broker holds this position but the journal has no matching open trade. Journal the position..." paragraph — lines 2/5/14-18). Generalizing it in place would require threading 3+ wording fields through `ReconcileOrphanAcknowledgeVM` and conditionalizing the orphan template, churning the orphan path (which the brief locks byte-unchanged). A thin sibling template (the same type-agnostic form body — `hx-headers`, the optional-reason textarea, the submit button — with allowlist-appropriate wording driven by a VM `heading`/`explanation` field) keeps the orphan template + VM byte-unchanged and avoids the orphan-path regression risk. The sibling reuses the same `ReconcileOrphanAcknowledgeVM`-shaped data (a new sibling VM `ReconcileSimpleAcknowledgeVM`, or a `heading`/`explanation`-parameterized reuse — executing's call; §4 Task 2). The shared form markup (the `hx-headers='{"HX-Request": "true"}'` + `204`/`HX-Redirect` POST contract) is identical to the orphan form by construction.

---

## 2. Grounded code facts (re-grounded on disk 2026-06-20, worktree base `main` HEAD `34fc5a63`)

All line numbers are from the worktree base; the brief's `~:` anchors drifted (the brief was authored against an earlier `main`). The executing implementer re-grounds before editing.

### 2.1 The GET two-branch gating + the misleading 409 — `swing/web/routes/reconcile.py`

`reconcile_discrepancy_resolve_form` (GET, `:206-...`):
- **Orphan branch** at `:306-330`: `if _is_orphan_discrepancy(disc):` -> if `disc.resolution not in _ORPHAN_CLEARABLE_RESOLUTIONS` (`{"unresolved","pending_ambiguity_resolution"}`, `:152-154`) -> 409 `already_resolved` (`:308-323`); else `_render_orphan_acknowledge_form(...)` (`:324-330`).
- **Tier-2 state guard (the dead-end)** at `:331-350`: `if disc.resolution != "pending_ambiguity_resolution" or disc.ambiguity_kind is None:` -> `_render_error(..., status_code=409, error_kind="already_resolved", error_message="Discrepancy {id} is no longer in pending_ambiguity_resolution state.", ...)` (`:335-350`). **This is the misleading site #1 (GET).** A plain-unresolved `cash_movement_mismatch`/`equity_delta` hits THIS guard today.
- **Happy tier-2 path** at `:351-...`: `build_reconcile_discrepancy_resolve_vm(conn, discrepancy_id)` + render `reconcile_discrepancy_resolve.html.j2`.

### 2.2 The POST two-branch gating + the orphan resolve path + the misleading 409 — `swing/web/routes/reconcile.py`

`reconcile_discrepancy_resolve_post` (POST, `:584-...`):
- **Orphan branch** at `:714-818`: `if _is_orphan_discrepancy(disc):` -> 409 if terminal (`:715-731`); else import + call `resolve_discrepancy(conn, discrepancy_id=..., resolution="acknowledged_immaterial", resolution_reason=(resolution_reason or None), resolved_by="operator_web", require_current_resolution=disc.resolution)` (`:737-753`) inside a catch-ladder:
  - `sqlite3.OperationalError` (transient) -> 503 `db_unavailable` (`:754-769`);
  - `DiscrepancyResolutionStateError` -> 409 `already_resolved` race (`:770-792`);
  - `ValueError` (concurrent DELETE) -> re-render acknowledge form 400 with error band (`:793-809`);
  - success -> `redirect_target = "/dashboard?reconcile_resolved=disc-{id}"`; if `HX-Request == "true"` -> `Response(status_code=204, headers={"HX-Redirect": redirect_target})`; else `RedirectResponse(url=redirect_target, status_code=303)` (`:810-818`). **This is the exact 204+HX-Redirect / 303-fallback shape the simple-acknowledge POST reuses.**
- **Tier-2 state guard (the dead-end)** at `:820-840`: `if disc.resolution != "pending_ambiguity_resolution" or disc.ambiguity_kind is None:` -> `_render_error(..., 409, error_kind="already_resolved", error_message="Discrepancy {id} is no longer in pending_ambiguity_resolution state.", ...)`. **This is the misleading site #2 (POST).**

### 2.3 `_is_orphan_discrepancy` + `_render_orphan_acknowledge_form` + the VM + the template

- `_is_orphan_discrepancy(disc)` (`:157-162`): `discrepancy_type == "untracked_broker_position" and trade_id is None`. UNCHANGED by this arc; the simple-acknowledge branch adds a SIBLING predicate `_is_simple_acknowledgeable_discrepancy(disc)` checking `discrepancy_type in _SIMPLE_ACKNOWLEDGEABLE_TYPES` (it does NOT subsume the orphan; the orphan keeps its own branch + wording).
- `_render_orphan_acknowledge_form(...)` (`:165-203`): builds `ReconcileOrphanAcknowledgeVM` + renders `reconcile_orphan_acknowledge.html.j2` via `request.app.state.templates.TemplateResponse(request, "<name>", {"vm": vm}, status_code=...)` (the Starlette 1.0 signature). The simple-acknowledge branch adds a SIBLING renderer `_render_simple_acknowledge_form(...)` building the sibling VM + rendering the sibling template (same signature).
- `ReconcileOrphanAcknowledgeVM` (`swing/web/view_models/reconcile.py:962-1037`): 8 standalone base-layout fields + page fields (`discrepancy_id`, `form_action`, `ticker`, `delta_text`, `created_at`, `run_id`, `prior_resolution_reason`, `error_band_message`); `__post_init__` validates `session_date` non-empty, counts >= 0, `banner_resolve_link` shape, `discrepancy_id > 0`, and `form_action == f"/reconcile/discrepancy/{discrepancy_id}/resolve"` byte-for-byte. The fields are type-AGNOSTIC; only the template prose is orphan-specific. The sibling VM mirrors this shape (+ a `heading`/`explanation` field, or executing reuses this VM and parameterizes the template — §4 Task 2).
- `reconcile_orphan_acknowledge.html.j2`: the form carries `hx-headers='{"HX-Request": "true"}'` (`:33`) -> OriginGuard-safe; the orphan-specific prose is `:2` (title), `:5` (heading), `:14-18` (explanation), `:19-20` (CLI parity). The form body (`:29-49`) is type-agnostic. The sibling template clones the form body with allowlist-appropriate wording.

### 2.4 `resolve_discrepancy` — the generic manual resolver — `swing/trades/reconciliation.py:568`

- Signature (`:568-577`): `resolve_discrepancy(conn, *, discrepancy_id, resolution, resolution_reason=None, resolved_by=..., require_current_resolution: str | None = None, ...)`.
- `require_current_resolution` TOCTOU anchor (`:643-652`): raises `DiscrepancyResolutionStateError` if `existing.resolution != require_current_resolution` under the write transaction (BEGIN IMMEDIATE).
- `ambiguity_kind` clearing (`:652-671`): `clear_ambiguity_kind = existing.ambiguity_kind is not None` — for a row ALREADY at `ambiguity_kind NULL` (which `cash_movement_mismatch` + `equity_delta` always are when `unresolved`) the extra clear is a **harmless no-op**. So reusing the exact orphan POST path is fully compatible; the simple-acknowledge types need NO ambiguity_kind handling beyond what `resolve_discrepancy` already does. The CLI `discrepancy resolve` (`swing/cli.py`) exposes `acknowledged_immaterial` for ANY type and is the proof the resolver handles `unresolved -> acknowledged_immaterial` for non-orphan types. FK presence is irrelevant to `acknowledged_immaterial` (it resolves by `discrepancy_id`).

### 2.5 `MATERIAL_BY_TYPE` — `swing/trades/reconciliation.py:99-114`

The material=0 advisory types are `cash_movement_mismatch` (0), `sector_tamper` (0), `snapshot_mismatch` (0), `equity_delta` (0); the rest are material=1 (`close_price_mismatch`, `stop_mismatch`, `position_qty_mismatch`, `unmatched_open_fill`, `unmatched_close_fill`, `entry_price_mismatch`, `untracked_broker_position`). **The enumerated-not-derived discriminator (brief §3, locked):** `sector_tamper` and `snapshot_mismatch` are material=0 but NOT in the V1 allowlist — a `MATERIAL_BY_TYPE`-derived set would WRONGLY include them. The §4 enumerated-not-derived test (DISCR) uses `sector_tamper` (or `snapshot_mismatch`) to PROVE the allowlist is an explicit constant. `stop_mismatch` (material=1) is the non-allowlisted error-copy test type.

### 2.6 The error VM + the error template — `swing/web/view_models/reconcile.py:841-945` + `swing/web/templates/reconcile_discrepancy_resolve_error.html.j2`

- `ReconcileDiscrepancyErrorVM.error_kind` is a FREE string (`__post_init__:938-941` only rejects empty) — a NEW `error_kind` value (`not_web_acknowledgeable`) is purely additive (NO enum CHECK, NO schema).
- The error template (`:1-41`) branches on `vm.error_kind`: `not_found` (`:5-8`), `already_resolved` (`:9-17` — **hardcodes** "is no longer in pending_ambiguity_resolution state" at `:11`, IGNORING `vm.error_message`), `anchor_mismatch`, `service_error`, `db_unavailable`, generic `else`. **O1: because the `already_resolved` branch hardcodes the misleading prose, the honest-copy fix MUST add a NEW `{% elif vm.error_kind == 'not_web_acknowledgeable' %}` branch with the honest wording.** Routing the non-allowlisted-unresolved case to `not_web_acknowledgeable` leaves `already_resolved` byte-unchanged (genuinely terminal-state tier-2 rows still get it — correctly, since a resolved tier-2 row IS no longer pending).

### 2.7 The migration-0031 cross-column CHECK — `swing/data/migrations/0031_untracked_broker_position.sql:71-83`

See §3 (the Step-3 load-bearing verification). The CHECK is type-AGNOSTIC.

---

## 3. Step-3 verification — the migration-0031 CHECK admits the transition (the load-bearing premise)

**RESULT: PASS for BOTH `cash_movement_mismatch` AND `equity_delta`, with NO schema/CHECK change. NO §3 tripwire crossed.**

The migration-0031 cross-column CHECK (`0031_untracked_broker_position.sql:71-83`) on the rebuilt `reconciliation_discrepancies` table:

```sql
CHECK (
    (ambiguity_kind IS NULL
        AND resolution NOT IN ('pending_ambiguity_resolution','operator_resolved_ambiguity'))
    OR
    (ambiguity_kind IS NOT NULL
        AND resolution IN ('pending_ambiguity_resolution','operator_resolved_ambiguity'))
)
```

For the target transition `unresolved -> acknowledged_immaterial` with `ambiguity_kind = NULL`:
- **Branch 1** requires `ambiguity_kind IS NULL` (TRUE for both types when `unresolved`) AND `resolution NOT IN ('pending_ambiguity_resolution','operator_resolved_ambiguity')`. `acknowledged_immaterial` is NOT in that forbidden set, so branch 1 is **SATISFIED**.
- `acknowledged_immaterial` is a valid `resolution` enum value (the `resolution` CHECK at `:55-60` lists it).
- The CHECK references ONLY `ambiguity_kind` + `resolution` — it is **type-agnostic** (it does not mention `discrepancy_type`), so the verdict is identical for `cash_movement_mismatch` and `equity_delta` (and any type).

**Per-type confirmation that `ambiguity_kind` is NULL for these rows:** `cash_movement_mismatch` and `equity_delta` are emitted with `ambiguity_kind = NULL` (they are not tier-2 ambiguities) and `MATERIAL_BY_TYPE` marks them advisory (`reconciliation.py:103,109`). The cross-column CHECK forbids a non-NULL `ambiguity_kind` paired with a non-pending resolution, so any `unresolved` row of these types MUST already have `ambiguity_kind = NULL` (the only way it could be `unresolved` and pass the CHECK). The orphan path's `ambiguity_kind`-clearing UPDATE is therefore UNNECESSARY for the allowlisted types — and `resolve_discrepancy` handles it anyway (`reconciliation.py:662`: `clear_ambiguity_kind = existing.ambiguity_kind is not None` -> for an already-NULL row, no-op). **No schema change, no CHECK change, no migration is needed.** This confirms the brief §2 caveat resolves clean and the "no tripwire" premise holds.

---

## 4. Per-task breakdown (TDD-first)

**Task structure (executing phase).** Three production touches, each red->green->commit. Tests are built from the REAL route path (Starlette `TestClient` against the real app, real seeded DB rows via the production INSERT path) — never values hand-built to satisfy the premise. Each test states its PRE/POST arithmetic so it provably DISTINGUISHES (memory `feedback_regression_test_arithmetic`).

- **Task 1** — the allowlist constant + the `_is_simple_acknowledgeable_discrepancy` predicate (a pure, self-contained unit) — tested by the predicate unit + the enumerated-not-derived discriminator (DISCR).
- **Task 2** — the GET + POST simple-acknowledge branches + the sibling template/VM + the honest-copy `not_web_acknowledgeable` error_kind (GET + POST) — tested by GET-FORM (per IN type), POST-CLEAR (204/HX-Redirect + 303), COPY-FIX, TOCTOU, and the byte-unchanged regressions (ORPHAN-REG, TIER2-REG).
- **Task 3** — the honest-copy template branch (`not_web_acknowledgeable`) — folded into Task 2's COPY-FIX test (the template branch + the route routing land together so the test sees the honest message end-to-end).

(The executing implementer MAY merge Task 2 + Task 3 into one commit since the COPY-FIX test exercises both the route routing and the template branch end-to-end; the order above is the dependency order: the allowlist constant is the shared primitive.)

### Test GET-FORM — allowlisted types render the simple acknowledge form on GET (one assertion per IN type)

**Intent (brief §4 bullet 1):** each allowlisted type renders the simple acknowledge form instead of a 409.

**Fixture:** seed an `unresolved` `cash_movement_mismatch` row (and, in a parametrized sibling, an `unresolved` `equity_delta` row) with `ambiguity_kind = NULL`, `trade_id` non-null-or-null (irrelevant — not the orphan type), via the production discrepancy INSERT path. `GET /reconcile/discrepancy/{id}/resolve`.

**Assertions + pre/post arithmetic:**
- POST-fix: status 200; the response body carries the sibling acknowledge form marker (e.g. `data-simple-acknowledge-form="true"`) AND `hx-headers='{"HX-Request": "true"}'` AND the form `action="/reconcile/discrepancy/{id}/resolve"`; the body does NOT contain "no longer in pending_ambiguity_resolution".
- PRE-fix arithmetic: WITHOUT the simple-acknowledge GET branch, an `unresolved` `cash_movement_mismatch` falls through to the tier-2 state guard (`:331-350`) -> 409 + the misleading `already_resolved` page -> the form marker is ABSENT and "no longer in pending_ambiguity_resolution" is PRESENT -> the assertion FAILS. POST-fix the branch renders the form -> PASSES. **Distinguishes** the new branch.
- Parametrize over `{cash_movement_mismatch, equity_delta}` so EACH IN type has its own assertion (brief §4 "one assertion per included type").

### Test POST-CLEAR — POST -> resolve_discrepancy -> acknowledged_immaterial; terminal state; 204+HX-Redirect AND 303 fallback

**Intent (brief §4 bullet 2):** the POST clears the row to `acknowledged_immaterial`; the HTMX `204` + `HX-Redirect` shape AND the non-HTMX `303` fallback are both covered; the HX-Redirect target route exists.

**Fixture:** seed an `unresolved` `cash_movement_mismatch` (and parametrized `equity_delta`). Two arms:
- **HTMX arm:** `POST .../resolve` with header `HX-Request: true` (and the OriginGuard-satisfying headers a TestClient HTMX submit needs). Assert: status `204`; response header `HX-Redirect == "/dashboard?reconcile_resolved=disc-{id}"`; the row's `resolution` is now `acknowledged_immaterial` (re-read via `get_discrepancy`); `resolved_by == "operator_web"`. Assert the HX-Redirect target `/dashboard` is in `app.routes` (OR a second `GET /dashboard` returns 200) — the HX-Redirect-target-must-exist gotcha.
- **Non-HTMX arm:** `POST .../resolve` WITHOUT `HX-Request` -> status `303`; `Location` header == the same redirect target; the row reaches `acknowledged_immaterial`.

**Pre/post arithmetic:** PRE-fix the POST falls through to the tier-2 state guard (`:820-840`) -> 409, the row stays `unresolved` (NOT cleared) -> the terminal-state assertion FAILS. POST-fix the simple-acknowledge POST branch clears it -> PASSES. **Distinguishes** the new POST branch. (The 204-vs-303 split mirrors the orphan path `:813-818` verbatim — reused, not re-implemented.)

### Test COPY-FIX — non-allowlisted, non-tier-2 unresolved type returns the CORRECTED copy

**Intent (brief §4 bullet 3):** a NON-allowlisted, non-tier-2 unresolved type still returns the error page but with the corrected (honest) copy — assert the new message AND assert it does NOT contain "no longer in pending_ambiguity_resolution".

**Fixture:** seed an `unresolved` `stop_mismatch` (material=1; NOT in the allowlist, NOT the orphan, NOT pending-ambiguity — `ambiguity_kind = NULL`). Exercise BOTH GET and POST.

**Assertions + pre/post arithmetic:**
- POST-fix (GET): status 409 (or the chosen honest status — keep 409 for "exists but not actionable here"); `data-error-kind="not_web_acknowledgeable"`; the body contains the honest sentence (e.g. "not web-acknowledgeable" + a "resolve via the CLI" pointer); the body does NOT contain "no longer in pending_ambiguity_resolution".
- POST-fix (POST): same — the POST routes the non-allowlisted-unresolved case to the same honest `not_web_acknowledgeable` error_kind.
- PRE-fix arithmetic: WITHOUT the routing change, the `stop_mismatch` unresolved row hits the tier-2 state guard -> `error_kind="already_resolved"` -> the template `:11` hardcoded "no longer in pending_ambiguity_resolution state" -> the "does NOT contain" assertion FAILS. POST-fix it routes to `not_web_acknowledgeable` -> PASSES. **Distinguishes** the copy fix. (O1: the fix is the new error_kind + the new template branch — editing the Python message string alone would NOT fix it because `already_resolved`'s template branch ignores `vm.error_message`.)
- **Genuinely-terminal tier-2 row still gets `already_resolved` (regression arm):** a tier-2 row whose `resolution` IS terminal (e.g. `operator_resolved_ambiguity` with a cleared ambiguity_kind, or `journal_corrected`) still routes to `already_resolved` with the unchanged copy — proving the honest copy is scoped to the unresolved-non-allowlisted case, not a blanket replacement.

### Test DISCR — the ENUMERATED-not-derived discriminator

**Intent (brief §4 bullet 4):** a material=0 type NOT in the allowlist (`sector_tamper` or `snapshot_mismatch`) does NOT get the simple acknowledge form — proving the allowlist is an explicit constant, not a `MATERIAL_BY_TYPE`-derived set.

**Fixture:** seed an `unresolved` `sector_tamper` row (material=0 per `MATERIAL_BY_TYPE`, but NOT in `_SIMPLE_ACKNOWLEDGEABLE_TYPES`). `GET .../resolve` (and POST).

**Assertions + pre/post arithmetic:**
- POST-fix: status 409; `data-error-kind="not_web_acknowledgeable"` (the honest copy — it IS unresolved-non-allowlisted); the body does NOT carry the simple acknowledge form marker.
- The DISCRIMINATING value: if the implementer (wrongly) derived the allowlist from `MATERIAL_BY_TYPE` (all material=0), `sector_tamper` WOULD get the form -> the "no form marker" assertion FAILS. With the explicit `frozenset({"cash_movement_mismatch","equity_delta"})`, `sector_tamper` is excluded -> PASSES. **Distinguishes** an enumerated constant from a derived set. (Also assert `snapshot_mismatch` in a parametrized sibling for completeness.)

### Test TOCTOU — the race ladder preserved (concurrent-resolve 409 + the require_current_resolution anchor)

**Intent (brief §4 bullet on TOCTOU):** the simple-acknowledge POST preserves the orphan path's TOCTOU/`require_current_resolution` race ladder.

**Fixture:** seed an `unresolved` `cash_movement_mismatch`. Simulate a concurrent resolve: after the route's pre-flight read but before its `resolve_discrepancy` call, the row's `resolution` flips to a terminal state (the established technique — monkeypatch/patch the resolver to raise `DiscrepancyResolutionStateError`, OR pre-resolve the row out-of-band so `require_current_resolution=disc.resolution` no longer matches). The simple-acknowledge POST passes `require_current_resolution=disc.resolution` (mirroring the orphan path `:752`).

**Assertions + pre/post arithmetic:**
- The POST catches `DiscrepancyResolutionStateError` -> 409 `already_resolved` (the race disposition, mirroring orphan `:770-792`); the row is NOT double-resolved (its `resolution`/`resolved_by` reflect the FIRST winner, not `operator_web`).
- PRE-fix arithmetic (a buggy impl that OMITS `require_current_resolution`): the second resolve would silently overwrite the winner's audit metadata + return 204 -> the "row reflects the first winner" assertion FAILS. WITH the anchor it raises -> 409 -> PASSES. **Distinguishes** the preserved race ladder.

### Test ORPHAN-REG — the orphan path is byte-unchanged

**Intent (brief §4 bullet 5):** the orphan path is byte-unchanged (regression assertion).

**Fixture:** seed an `unresolved` `untracked_broker_position` orphan (`trade_id IS NULL`). GET + POST.

**Assertions:** GET renders the ORPHAN acknowledge form (`data-orphan-acknowledge-form="true"` / "Untracked broker position" heading) — NOT the new sibling template; POST clears it to `acknowledged_immaterial` exactly as today (204+HX-Redirect / 303). This proves `_is_orphan_discrepancy` still wins its own branch and the orphan template/VM are untouched. (The simple-acknowledge branch is ADDED AFTER the orphan branch and tests a DISJOINT type set, so the orphan path is provably unaffected.)

### Test TIER2-REG — the tier-2 ambiguity path is byte-unchanged

**Intent (brief §4 bullet 5):** the tier-2 ambiguity path is byte-unchanged (regression assertion).

**Fixture:** seed a `pending_ambiguity_resolution` row with a non-null `ambiguity_kind` (e.g. `multi_match_within_window`). GET + (optionally) POST.

**Assertions:** GET renders the tier-2 resolve form (`build_reconcile_discrepancy_resolve_vm` path — the choice menu) exactly as today; it does NOT route to the simple-acknowledge branch (the simple-acknowledge predicate checks `discrepancy_type`, and a pending-ambiguity row of an allowlisted type would still need `ambiguity_kind IS NULL` to reach the simple branch — BUT a pending row has `ambiguity_kind NOT NULL`, so it correctly stays tier-2). **Branch-ordering LOCK (executing):** the simple-acknowledge GET/POST branch MUST gate on the SAME clearable-resolution + null-ambiguity_kind shape the orphan branch uses (allowlisted type AND `ambiguity_kind IS NULL` AND resolution in the clearable set) so a pending-ambiguity row of an allowlisted type (if one ever existed) is NOT hijacked away from the tier-2 form. Assert a pending-ambiguity `cash_movement_mismatch`-shaped row (ambiguity_kind set) still renders the tier-2 form, not the simple form.

### Live-DB-shape + encoding discipline (brief §5.10 + Windows cp1252)

- **ASCII-only user-facing strings:** the new honest-copy message ("This discrepancy type is not web-acknowledgeable; resolve it via the CLI." — no em-dash, no glyphs) and the sibling template prose are ASCII (the Windows cp1252 `UnicodeEncodeError` gotcha; `capsys`/`TestClient` hide it). Written ASCII-clean by construction.
- **Operator §5.10 browser live-witness — BINDING** (HTMX form work): open the resolve drill-down for a real/seeded `cash_movement_mismatch` and an `equity_delta`, acknowledge each, confirm it clears; confirm a material=1 type (`stop_mismatch`) shows the corrected error copy, not the misleading one. (TestClient cannot catch the browser-only HTMX failure surfaces — the `hx-headers`/OriginGuard 403 + the `204`+`HX-Redirect`-vs-303 swap; the operator browser gate is binding per CLAUDE.md.)

### Acceptance (executing)

- Tests GET-FORM, POST-CLEAR, COPY-FIX, DISCR, TOCTOU, ORPHAN-REG, TIER2-REG green; the FULL fast suite green (`python -m pytest -m "not slow" -q`) BEFORE the Codex review (recipe §2: review converges on a green diff).
- `ruff check swing/` clean.
- The §4/§5 traceability table (§5) honored on disk; the tripwire self-certification (§6) holds.

---

## 5. §4 / §5 traceability table (the CHARC QA checklist)

| brief obligation | plan task | plan test | how it distinguishes / honored-on-disk |
| --- | --- | --- | --- |
| §4 allowlisted types render the form on GET (one assertion per IN type) | Task 1 + 2 | GET-FORM (parametrized) | PRE: tier-2 guard -> 409 misleading; POST: simple form rendered. Parametrized over `{cash_movement_mismatch, equity_delta}`. |
| §4 POST -> resolve_discrepancy -> acknowledged_immaterial; terminal state; 204+HX-Redirect AND 303; HX-Redirect target exists | Task 2 | POST-CLEAR (HTMX + non-HTMX arms) | reuses the orphan POST shape (`reconcile.py:737-818`); row re-read == `acknowledged_immaterial`, `resolved_by="operator_web"`; `/dashboard` asserted in `app.routes`. |
| §4 non-allowlisted non-tier-2 unresolved -> corrected copy; NOT "no longer in pending_ambiguity_resolution" | Task 2 + 3 | COPY-FIX (GET + POST + terminal-tier2 regression arm) | O1: new `error_kind="not_web_acknowledgeable"` + new template branch (the `already_resolved` branch hardcodes the misleading text, ignoring `vm.error_message`). |
| §4 ENUMERATED-not-derived (material=0 non-allowlisted type does NOT get the form) | Task 1 | DISCR (`sector_tamper`/`snapshot_mismatch`) | explicit `frozenset` excludes material=0 `sector_tamper`; a `MATERIAL_BY_TYPE`-derived set would include it -> the no-form assertion distinguishes. |
| §4 tier-2 path + orphan path byte-unchanged (regression) | Task 2 | TIER2-REG + ORPHAN-REG | disjoint type sets + branch-ordering LOCK (allowlist AND `ambiguity_kind IS NULL`); orphan keeps its own branch/template/VM. |
| §4 TOCTOU/race ladder preserved (concurrent-resolve 409 + require_current_resolution) | Task 2 | TOCTOU | `require_current_resolution=disc.resolution` mirrors orphan `:752`; `DiscrepancyResolutionStateError` -> 409. |
| §4/§5 embedded form carries `hx-headers '{"HX-Request":"true"}'` | Task 2 | GET-FORM | the sibling form clones the orphan form's `hx-headers` (`reconcile_orphan_acknowledge.html.j2:33`); asserted on the rendered attribute. |
| §4 ASCII-only user-facing strings | Task 2/3 | (by construction) | honest-copy message + sibling prose ASCII (cp1252 gotcha). |
| §2 CHECK-legality verified per type (no schema/CHECK change) | (§3) | — | migration-0031 CHECK type-agnostic; branch 1 admits `acknowledged_immaterial` + `ambiguity_kind NULL` for both types. |
| §5 Codex review-strong to convergence + codex-auto-review (production web code) | (executing) | — | §7 executing spec: review-strong repo-access to `NO_NEW_CRITICAL_MAJOR` + codex-auto-review matched-high. |
| §5 operator §5.10 browser live-witness BINDING | (executing) | — | §7: seeded `cash_movement_mismatch` + `equity_delta` -> acknowledge -> clears; `stop_mismatch` shows corrected copy. |
| §5 RD FYI only (NOT merge-blocking) | (executing) | — | not measurement-core; RD FYI per brief §5. |
| §5 before-review full-suite + `ruff check swing/` clean | (executing) | — | §4 acceptance + recipe §2. |

---

## 6. Tripwire self-certification

| tripwire | crossed? | disposition |
| --- | --- | --- |
| New schema / migration | **NO** | §3 verified the migration-0031 cross-column CHECK already admits `unresolved -> acknowledged_immaterial` for both allowlisted types (type-agnostic CHECK; branch 1 satisfied). Schema stays v31. |
| New module / package under `swing/` | **NO** | a new module-level constant + sibling predicate/renderer in the EXISTING `swing/web/routes/reconcile.py`; a sibling VM in the EXISTING `swing/web/view_models/reconcile.py`; a new template file (`reconcile_simple_acknowledge.html.j2`) — a template is not a Python module/package. |
| New external dependency | **NO** | — |
| New standing process | **NO** | a web route is operator-invoked — not a pipeline step / daemon / scheduled job. |
| Phase-isolation carve-out (`swing/trades` / `swing/data`) | **NO** | the route only CALLS the existing public `resolve_discrepancy` (`swing/trades/reconciliation.py:568`); `swing/trades` + `swing/data` are consumed READ-ONLY (no edit). All edits are web-layer (`swing/web/routes/`, `swing/web/view_models/`, `swing/web/templates/`). |

**NO tripwire crossed** (conditional on §3 PASS, which held). Web-layer only; it CALLS the existing public `resolve_discrepancy`; NO schema, NO new module/package, NO new dependency, NO new standing process, NO `swing/trades`/`swing/data` carve-out. **No §0 BLOCKING question.** If executing discovers the design needs schema or a carve-out, it STOPS and surfaces it to CHARC via the orchestrator (recipe §5) — it does NOT bake it in.

**File list (production, executing):**
- `swing/web/routes/reconcile.py` — `_SIMPLE_ACKNOWLEDGEABLE_TYPES` constant + `_is_simple_acknowledgeable_discrepancy` predicate + `_render_simple_acknowledge_form` renderer + the GET branch (after the orphan branch, before the tier-2 guard) + the POST branch (after the orphan branch, before the tier-2 guard, reusing the orphan resolve path's catch-ladder) + the honest-copy `not_web_acknowledgeable` routing for the non-allowlisted-unresolved case (GET + POST).
- `swing/web/view_models/reconcile.py` — a sibling `ReconcileSimpleAcknowledgeVM` (mirroring `ReconcileOrphanAcknowledgeVM` + a `heading`/`explanation` field), OR a `heading`/`explanation` reuse of the orphan VM (executing's call; the orphan VM stays byte-unchanged either way).
- `swing/web/templates/reconcile_simple_acknowledge.html.j2` — the thin sibling form (clone of the orphan form body with allowlist-appropriate wording; same `hx-headers` + `204`/`HX-Redirect` contract).
- `swing/web/templates/reconcile_discrepancy_resolve_error.html.j2` — a NEW `{% elif vm.error_kind == 'not_web_acknowledgeable' %}` branch with the honest wording (the `already_resolved` branch stays byte-unchanged).
- **Tests (executing):** extend `tests/web/` reconcile-resolve test module(s) (mirror the existing orphan + tier-2 resolve tests' `TestClient` patterns + the production discrepancy INSERT seeding). The executing implementer picks the exact module split to match the repo's `tests/web/` layout.

Default `swing/trades` + `swing/data` read-only posture is preserved (no carve-out).

---

## 7. Executing-phase spec (baked in from brief §5 + §8)

- **Cell:** `implementer-opus-high` (brief §8 — multi-file web change [route + VM + template + tests] with real care but no measurement-chain stakes).
- **Review (executing, BINDING gate):** `review-strong` (gpt-5.5/high) with **REPO ACCESS** — production web code: the new branches' correctness depends on the surrounding GET/POST handler structure, the orphan branch ordering, the `resolve_discrepancy` race ladder, and the error template's branch set (all UN-changed neighbors), so the reviewer MUST read beyond the diff (recipe §3 18-H.4 repo-access note). Run to `NO_NEW_CRITICAL_MAJOR`; the 5-round cap is suspended; **NEVER tier down.** PLUS **`codex-auto-review`** (gating, repo-access, matched-HIGH effort — `codex exec review --commit <pre-review-sha> -c model_reasoning_effort=high`) as the complementary second eye on production code; a B `major`/`[P1]` is adjudicated + resolved-or-cited before merge.
- **RD:** FYI-ONLY (NOT measurement-core, NOT merge-blocking — brief §5). The orchestrator may FYI RD after its own QA; the implementer NEVER posts.
- **Operator §5.10 live-witness — BINDING (HTMX form work):** open the resolve drill-down for a real/seeded `cash_movement_mismatch` and an `equity_delta`, acknowledge each, confirm it clears; confirm a material=1 type (`stop_mismatch`) shows the corrected error copy, not the misleading one.
- **Convergence transcript:** the executing Codex `NO_NEW_CRITICAL_MAJOR` transcript -> a TRACKED `docs/reviews/web-acknowledge-coverage-executing-codex-findings.md`.
- **Commit discipline:** BARE git from the worktree cwd (never `git -C`); ZERO `Co-Authored-By`; conventional commits carrying the task id; before-review full-suite + `ruff check swing/` clean (recipe §2).
- **Base:** then-current `main`; the orchestrator rebases the branch + runs the merged-head no-false-green suite (the cross-arc seeding-regression net).

---

## 8. Explicitly OUT of scope

- **D16 durable-acknowledge / re-emit-suppression** — a `swing/trades` matcher concern (brief §6). This arc only adds the GUI acknowledge PATH; if a row re-emits next run (a new id), the operator re-acknowledges — now cheaply via the GUI. Orthogonal; both valuable; D16 would make the acknowledge durable.
- **The DEFERRED `sector_tamper` / `snapshot_mismatch`** — same material=0 advisory rationale but rarer (brief §3 DEFERRED); add later ONLY if a GUI dead-end on them ever bites. The DISCR test uses them precisely to PROVE they are excluded today.
- **The six material=1 mismatch types** (`close_price_mismatch`, `stop_mismatch`, `position_qty_mismatch`, `unmatched_open_fill`, `unmatched_close_fill`, `entry_price_mismatch`) — real reconciliation issues warranting a genuine resolution, NOT a one-click "immaterial" dismiss; keep them CLI / tier-2 only (brief §3 OUT). They now get the HONEST `not_web_acknowledgeable` copy on the unresolved-non-actionable path instead of the misleading one.
- **Any measurement-chain touch** — the `equity_delta`/`cash_movement_mismatch` emit logic, the `MATERIAL_BY_TYPE` materiality, the `resolve_discrepancy` resolver internals. SHIPPED + correct; this arc only adds a GUI acknowledge PATH that CALLS the existing resolver.
- **Generalizing the orphan template in place** — declined (§1 template decision); the thin sibling template keeps the orphan path byte-unchanged.

---

## Appendix A — grounding observations (re-grounded on disk; do NOT re-open the settled design)

Every brief §0/§1/§2 grounding fact re-grounded on `main` HEAD `34fc5a63`; the brief's `~:` line anchors drifted (the brief was authored against an earlier `main`) — this plan re-anchors them. Confirmed:
- GET two-branch gating: orphan `:306-330`, tier-2 state guard `:331-350` (brief `~:306` / `~:332-341`). The misleading copy at `:340-341`. ✓
- POST orphan path `:714-818` (brief `~:714`); `resolve_discrepancy(..., resolution="acknowledged_immaterial", ..., require_current_resolution=disc.resolution)` at `:737-753` (brief `~:740-752`); POST misleading 409 at `:820-840` (brief `~:822-831`). ✓
- `_is_orphan_discrepancy` `:157-162` (brief `~:157`) ✓; `_render_orphan_acknowledge_form` `:165-203` ✓; `ReconcileOrphanAcknowledgeVM` `view_models/reconcile.py:962-1037` ✓; `reconcile_orphan_acknowledge.html.j2` (`hx-headers` at `:33`) ✓.
- `MATERIAL_BY_TYPE` `reconciliation.py:99-114` ✓ (material=0: `cash_movement_mismatch`, `sector_tamper`, `snapshot_mismatch`, `equity_delta`).
- migration-0031 cross-column CHECK `0031_untracked_broker_position.sql:71-83` ✓ (§3 PASS).
- `resolve_discrepancy` `reconciliation.py:568`; `require_current_resolution` `:577,:643-652`; `clear_ambiguity_kind = existing.ambiguity_kind is not None` `:662` ✓.

The MATERIAL strengthening OBSERVATION (does NOT cross a binding gate or the authorized scope; does NOT re-open the design):

1. **O1 (load-bearing) — the misleading copy is HARDCODED in the template, not just the Python handler.** `reconcile_discrepancy_resolve_error.html.j2:11` renders "Discrepancy {id} is no longer in pending_ambiguity_resolution state." literally under the `already_resolved` branch, IGNORING `vm.error_message`. The two Python sites (`reconcile.py:340-341` GET, `:830-831` POST) build a matching `error_message`, but the `already_resolved` template branch does not surface it. **Consequence:** editing only the Python message string would NOT fix the displayed copy — the honest-copy fix MUST add a NEW `error_kind="not_web_acknowledgeable"` value (free string; no enum CHECK — `view_models/reconcile.py:938-941` only rejects empty) + a NEW `{% elif vm.error_kind == 'not_web_acknowledgeable' %}` template branch, and route the non-allowlisted-unresolved case to it (GET + POST). The genuinely-terminal tier-2 case keeps `already_resolved` (correctly — a resolved tier-2 row IS no longer pending). The COPY-FIX test's "does NOT contain 'no longer in pending_ambiguity_resolution'" assertion is what catches a Python-only fix that left the template branch untouched. (Strengthens the plan; stays within web-layer scope.)

This observation makes the plan's COPY-FIX test stronger (it pins the template-branch fix, not just a Python message edit) — it is NOT used to relax a binding condition or re-open the settled design.
