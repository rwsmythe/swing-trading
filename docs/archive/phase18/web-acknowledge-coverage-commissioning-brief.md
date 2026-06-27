# Commissioning Brief — Web Simple-Acknowledge Coverage for Plain-Unresolved Discrepancies

**Commissioned by:** CHARC (Tool Development Director)
**Date:** 2026-06-18
**Status:** COMMISSIONED — **QUEUED behind the OOF-buy cash-coherence arc** (do NOT dispatch until that arc merges). No inline dispatch prompt yet.
**Tripwires crossed:** **NONE.** No schema, no new module/package, no `swing/trades` or `swing/data` carve-out (it only CALLS the existing `resolve_discrepancy`), no new dependency, no new standing process. Web-layer only → dispatches WITHOUT a CHARC §3 pass; the orchestrator self-certifies "no tripwire crossed" in the plan. **One caveat (see §2):** if writing-plans finds the `acknowledged_immaterial` transition needs a schema/CHECK change for any added type, THAT is a §3 tripwire → STOP and route to CHARC.

---

## §0 — The gap (operator-surfaced 2026-06-18, CHARC-confirmed on disk)

The web resolve window `/reconcile/discrepancy/{id}/resolve` handles only TWO shapes (`swing/web/routes/reconcile.py:306-350`):
1. **Orphan** — `untracked_broker_position` with `trade_id IS NULL` → a simple acknowledge form (18-H.6.1).
2. **Tier-2 ambiguity** — `resolution == 'pending_ambiguity_resolution'` + non-null `ambiguity_kind` → the choice-menu / custom-JSON resolution form.

A plain-`unresolved` discrepancy that is NEITHER — e.g. `cash_movement_mismatch` (the live "id 72"; the recurring monthly-deposit mismatch) or `equity_delta` (now routed to `unresolved` by the limbo fix `006a0571`, explicitly so it is operator-cleanable) — falls through to a **409 with a MISLEADING message** ("no longer in pending_ambiguity_resolution state" — it was NEVER in that state). The GUI surfaces these discrepancies (banner + drill-downs) but **cannot clear them**; the operator must drop to the CLI (`swing journal discrepancy resolve <id> --resolution acknowledged_immaterial`). This arc closes that loop — notably completing the limbo fix, which made `equity_delta` cleanable-as-unresolved but left no GUI path to clear it.

---

## §1 — Verified grounding (CHARC, on disk)

- The two-branch gating + the 409 dead-end: `swing/web/routes/reconcile.py:306-350` (GET) and `:714-840` (POST).
- **The simple-acknowledge pattern ALREADY EXISTS** and is reusable: `_is_orphan_discrepancy` (`:157-162`), `_render_orphan_acknowledge_form` (`:165-203`) + `ReconcileOrphanAcknowledgeVM` + `reconcile_orphan_acknowledge.html.j2`, and the POST clears via `resolve_discrepancy(resolution="acknowledged_immaterial", resolution_reason=… or None, resolved_by="operator_web", require_current_resolution=disc.resolution)` (`:732-753`).
- `resolve_discrepancy` is the generic manual resolver (`swing/trades/reconciliation.py`); the CLI `discrepancy resolve` (`swing/cli.py:3070-3110`) exposes `acknowledged_immaterial` for ANY discrepancy and is the proof the resolver handles `unresolved → acknowledged_immaterial` for non-orphan types. FK presence is irrelevant to `acknowledged_immaterial` (it resolves by `discrepancy_id`).
- `MATERIAL_BY_TYPE` (`swing/trades/reconciliation.py:99-114`): the material=0 advisory types are `cash_movement_mismatch`, `sector_tamper`, `snapshot_mismatch`, `equity_delta`; the rest are material=1.

---

## §2 — Design contract

**Generalize the orphan branch into a simple-acknowledge branch.** Replace the orphan-only predicate with a `_is_simple_acknowledgeable_discrepancy(disc)` over an explicit **type allowlist** (see §3), preserving the orphan case. For an allowlisted `unresolved` (or legacy `pending_ambiguity_resolution`, per the existing Codex-R2 widening) row, render the simple acknowledge form (reuse `reconcile_orphan_acknowledge.html.j2`, generalizing its orphan-specific wording, OR a thin sibling template — writing-plans call) and POST → `resolve_discrepancy → acknowledged_immaterial` (the exact orphan POST path, `:732-753`, with its TOCTOU/race ladder preserved).

**Additive / guard-only:** the tier-2 ambiguity branch and every existing match/emit path are byte-unchanged; this only ADDS coverage for the allowlisted types that today hit the 409.

**Fix the misleading 409:** for a NON-allowlisted, non-tier-2 unresolved discrepancy, the error copy must stop claiming "no longer in pending_ambiguity_resolution state" (it never was). Render an honest message (e.g. "this discrepancy type is not web-acknowledgeable; resolve via the CLI").

**CHECK-legality (writing-plans MUST verify):** confirm the `unresolved → acknowledged_immaterial` transition is permitted by the migration-0031 cross-column CHECK for EACH added type with NO schema change (the orphan path needed an `ambiguity_kind`-clearing UPDATE to satisfy it; the added types have `ambiguity_kind=NULL` already, so it should be clean — but verify per type). **If any type needs a schema/CHECK change → §3 tripwire → STOP + route to CHARC.**

---

## §3 — The acknowledge type allowlist (LOCKED — operator 2026-06-21)

**The discrepancy types that get the simple web acknowledge form (operator-locked):**
- **IN (V1 — the two recurring GUI dead-ends):** `cash_movement_mismatch`, `equity_delta`. (`equity_delta` is the one the limbo fix routes to `unresolved` expecting an operator acknowledge — adding it here completes that loop with a GUI path.)
- **KEEP:** `untracked_broker_position` (already orphan-acknowledged — unchanged).
- **DEFERRED (NOT V1):** `sector_tamper`, `snapshot_mismatch` — same material=0 advisory rationale but rarer; add later ONLY if a GUI dead-end on them ever bites.
- **OUT (V1):** the six material=1 mismatch types (`close_price_mismatch`, `stop_mismatch`, `position_qty_mismatch`, `unmatched_open_fill`, `unmatched_close_fill`, `entry_price_mismatch`) — real reconciliation issues that warrant a genuine resolution, NOT a one-click "immaterial" dismiss; keep them CLI / tier-2 only.

Rationale: the material=0 boundary is the principled line between "advisory drift the operator acknowledges" and "you should actually reconcile this." **The implementer builds EXACTLY the two IN types (plus the existing orphan branch) as an explicit enumerated allowlist constant — NOT "all material=0", NOT a `MATERIAL_BY_TYPE`-derived set** (so a future material=0 type isn't silently auto-acknowledgeable).

---

## §4 — Test obligations

- The allowlisted types render the simple acknowledge form (GET) instead of a 409 — one assertion per included type.
- POST → `resolve_discrepancy → acknowledged_immaterial`; the row reaches terminal state; HTMX 204 + `HX-Redirect` (the F5 LOCK shape) and the non-HTMX 303 fallback both covered.
- A NON-allowlisted, non-tier-2 unresolved type still returns the error page, but with the corrected (non-misleading) copy — assert the new message, assert it does NOT claim "no longer in pending_ambiguity_resolution".
- The tier-2 ambiguity path + the orphan path are byte-unchanged (regression assertions on both).
- TOCTOU/race ladder preserved (the concurrent-resolve 409 + the `require_current_resolution` anchor).
- Operator browser gate (HTMX form work is browser-binding per CLAUDE.md): the embedded form carries `hx-headers '{"HX-Request":"true"}'`; success is 204 + `HX-Redirect`; the redirect target exists.
- ASCII-only user-facing strings (the Windows cp1252 gotcha).

---

## §5 — Gates

- **Codex review-strong** (gpt-5.5/high) to CONVERGENCE + **codex-auto-review** (production web code).
- **Operator §5.10 browser live-witness — BINDING** (HTMX form work; witness: open the resolve drill-down for a real/seeded `cash_movement_mismatch` and an `equity_delta`, acknowledge each, confirm it clears; confirm a material=1 type still shows the corrected error copy, not the misleading one).
- NOT measurement-core → RD QA is not merge-blocking here (RD FYI only).
- Before-review full-suite run + `ruff check swing/` clean.

---

## §6 — Out of scope / interactions

- **NOT** the durable-acknowledge / re-emit-suppression (that is D16, a `swing/trades` matcher concern). This arc only adds the GUI acknowledge PATH; if a row re-emits next run (a new id), the operator re-acknowledges — now cheaply via the GUI. Orthogonal; both valuable; D16 would make the acknowledge durable.
- **OOF-buy arc:** independent layer; the OOF self-reconcile removes the OOF-driven `cash_movement_mismatch` entirely, but the monthly-deposit one remains → this arc's GUI path still earns its keep. **Queued behind the OOF arc** to avoid concurrent reconcile-area churn and keep one arc in flight.

---

## §7 — Return report

The **ORCHESTRATOR** posts the return report to `charc` AFTER its QA gate (RD FYI optional — not measurement-core). The implementer reports to its orchestrator in chat; never to a director inbox (`feedback_implementer_never_posts_to_directors`; CHARC §5.6).

---

## §8 — Dispatch model + effort recommendation

- **writing-plans → `implementer-opus-high`** — settled design, bounded web-layer scope (lighter than the OOF arc's xhigh; the design ambiguity is the §3 allowlist, which the operator pins at dispatch).
- **executing → `implementer-opus-high`** — multi-file web change (route + VM + template + tests) with real care but no measurement-chain stakes. (Select + announce per `docs/implementer-dispatch-recipe.md`.)

---

## §9 — Queue position

**Queued behind the OOF-buy cash-coherence arc** (`docs/oof-buy-command-commissioning-brief.md`, `27a0347f`). Dispatch the writing-plans phase of THIS arc only after the OOF arc merges + the operator confirms the §3 allowlist. Until then this brief is a parked tracker.
