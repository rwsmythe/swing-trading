# Commissioning Brief — 19-F: orphan-tolerant discrepancy resolution (the unresolvable cash-review nag)

**From:** CHARC. **To:** the Phase-19 orchestrator. **Arc:** 19-F ([`phase19-scope-charc.md`](phase19-scope-charc.md)). **Committed:** 2026-07-04 HST. **Demand:** operator 2026-07-02 — a dashboard "cash review" badge unresolvable via CLI or GUI.
**Diagnosis COMPLETE (CHARC read-only live-DB triage 2026-07-03 — verified, not inferred):** the badge is lit by discrepancy **73** (`cash_movement_mismatch`, `pending_ambiguity_resolution`, `schwab_returned_no_match`, created 06-19, expected `372.48 withdraw 2026-06-15`) which references **`cash_movement_id=5` — a row RD raw-DELETED 2026-06-21** in the D19 double-debit correction. The delete removed the movement but not the pending discrepancy; no supported path resolves a discrepancy whose subject row is gone. **NOT D16** (exonerated — no re-emit pattern; D16 stays WATCH, out of scope). The month-end deposit auto-ingested cleanly (movement 7, run 68) — recon is otherwise healthy.
**§3 verdict: CARVE-OUT tripwire (`swing/trades/schwab_reconciliation.py`) → this brief embeds the CHARC architecture pass. GO with conditions F1–F4 (§2). NO schema expected (v31) — see F2.**

## §0 References (CHARC-verified on disk)

- **The badge predicate:** `swing/web/view_models/dashboard.py:71-95` `_compute_cash_coherence_badge` — TRUE when ANY `cash_movement_mismatch` with `resolution='pending_ambiguity_resolution'` exists (any run, no age limit); `:54-68` `_first_pending_cash_resolve_link_path` → `/reconcile/discrepancy/{id}/resolve`.
- **The resolve path:** `swing/web/routes/reconcile.py` (the resolve GET/POST + the `reconcile_discrepancy_resolve_error.html.j2` error surface at `:105-127`); `swing/trades/schwab_reconciliation.py:~705-770` — the loader mapping `cash_movement_id → cash_movements row`, documented "Returns ``None`` for…" a missing row; `resolve_discrepancy` (terminal resolutions incl. `acknowledged_immaterial`; clears `ambiguity_kind` in the same UPDATE).
- **Live evidence:** `reconciliation_discrepancies` row 73; `cash_movements` ids {1,2,3,4,6,7} — 5 ABSENT; the CLI tier-2 path (`get_choice_menu(ambiguity_kind)` / the per-choice `requires_custom_value` contract).
- D19's close record (charter §4) — the raw-delete interim doctrine that MAKES this recur.

## §1 The fix (shape settled; mechanics at writing-plans)

An **orphan-tolerant TERMINAL resolution**: when a discrepancy's referenced `cash_movement` no longer exists, the resolve flow (web AND CLI tier-2) recognizes the orphan state and offers/permits a terminal resolution with an explicit orphan-marked `resolution_reason`, instead of failing. Resolving 73 through this SUPPORTED path — not a raw UPDATE — is the arc's live witness: the badge clears.

**Step 1 of the plan (mandatory): reproduce the exact live failure** against discrepancy 73 READ-ONLY (drive the GET/POST + the CLI path) and pin WHERE each surface fails today (error template? 500? refused choice?) — the plan's fix section cites the reproduced failure, not an assumption.

## §2 CHARC architecture pass — conditions (binding)

- **F1 — append-only/audit discipline:** the resolution is a SELECT-then-UPDATE of the existing discrepancy row per the established resolve semantics (never REPLACE/DELETE — the INSERT-OR-REPLACE gotcha); the orphan state lands in `resolution_reason` (+ the audit envelope where applicable) so the trail says WHY it was resolved subject-less.
- **F2 — NO schema:** use the EXISTING `resolution` enum (e.g. `operator_resolved_ambiguity` or `acknowledged_immaterial` — cross-check the CHECK constraint BEFORE prescribing, the #11 gotcha; the plan picks the semantically honest value) + a free-text orphan reason. If the plan concludes a CHECK-enum widening is genuinely required, that IS a schema tripwire → STOP and route back to CHARC (do not self-certify past it).
- **F3 — the fix is the MECHANISM, not a one-time patch:** any future raw-delete orphan (the D19 interim doctrine keeps raw-delete as the only manual-row removal, so recurrence is expected) resolves through the same path. Detection stays as-is (the badge lighting on a pending orphan is CORRECT — it demands an operator decision; the fix makes the decision POSSIBLE, it does not auto-resolve).
- **F4 — scope:** `swing/trades/schwab_reconciliation.py` (the carve-out) + the reconcile web route/VM/template + the CLI tier-2 path + tests. No other `swing/trades`/`swing/data` file; the badge predicate (`dashboard.py`) UNTOUCHED (it is correct).

## §3 Discriminating tests

- **Seeding discipline:** the orphaned-pending fixture is planted via RAW production-shape INSERT (a discrepancy referencing a nonexistent `cash_movement_id`) — the 18-B.1 lesson: tests of DETECTION/handling of bad pre-existing state bypass the write path.
- Orphaned pending → the resolve surface OFFERS the terminal path (web + CLI) → resolution persists with the orphan reason → the badge predicate returns False (write-then-read round trip).
- Non-orphan pending (movement EXISTS) → the flow is byte-identical to today (the no-regression lock).
- Idempotency: resolving an already-resolved orphan → the terminal-state idempotent return (the SELECT-first-before-validation ordering gotcha).

## §4 Gates

1. **RD plan-stage review, LIGHT** (audit-trail semantics of resolving-against-a-deleted-subject; measurement note: resolving the discrepancy changes NO ledger row — `current_equity` is already correct post-D19; this is bookkeeping legibility).
2. review-strong + codex-auto-review; suite + ruff + merged-head no-false-green.
3. **BINDING operator witness — the LIVE HEAL:** the operator resolves discrepancy 73 through the new path in the real GUI (HTMX browser-only failure surfaces — the hx-headers/HX-Redirect gotcha family applies to any new form) and the cash-review badge disappears from the dashboard. The original complaint clearing IS the acceptance.
4. The ORCHESTRATOR posts the return report to `charc,rd` AFTER its QA.

## §5 Sizing + dispatch recommendation

Small. CHARC recommendation: **writing-plans `implementer-opus-high`**, **executing `implementer-opus-high`** (a `swing/trades` carve-out + an HTMX form surface — gotcha density over size). Orchestrator selects + announces.
