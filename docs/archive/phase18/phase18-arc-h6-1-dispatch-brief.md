# 18-H.6.1 — `untracked_broker_position` attribution (banner + clear + sensible state) — CHARC dispatch brief

**Author:** CHARC. **Date:** 2026-06-16. **Phase 18, 18-H bug container.** Follow-up to 18-H.6 (merged `<TBD>`; the V1 visibility was confirmed narrower than at-a-glance at the operator recon live-witness — the SPCX orphan landed in `pending_ambiguity_resolution`, unbannered + permanently uncleanable).

**TRIPWIRE — this brief IS the CHARC §3 architecture pass.** Crossing: a **`swing/trades` + `swing/data` carve-out** (the resolve/classify machinery + a new repo reader). **NO new schema on the recommended design** (the resolver reuses an existing `RESOLUTION_TYPES` value — see §3.2; a new resolution value would be a schema sub-decision → STOP-and-flag to CHARC, condition C2). Conditions C1–C4 binding.

## 1. The gap (CHARC-verified on disk + the live witness)
18-H.6 V1 emits the orphan correctly (proven live: SPCX, 2 sh, $411.90), but the orphan row (all-FK-null, `trade_id NULL`) then:
- **is excluded from the material banner/count** — `count_unresolved_material` (`metrics/discrepancies.py:38`) + the banner-link helpers (`:51`,`:85`) call `list_unresolved_material_for_active/closed_trades`, which **JOIN on the `trades` row** → orphans excluded by construction (`:71-72`);
- **is swept into `pending_ambiguity_resolution`** by `_pivot_classify_and_dispatch_for_run` (`schwab_reconciliation.py:542`) → `classify_discrepancy` → `_stamp_pending_ambiguity_inner` (no handler for the new type → the ambiguity bucket) — the wrong state (an orphan is not a fill-matching ambiguity);
- **is permanently unclearable** — the FK-requiring resolve path raises on the all-FK-null orphan, so it lingers forever (the live ID 68 stays even after the operator journals SPCX).

## 2. The three parts
1. **Banner/count inclusion** — count orphan (`trade_id NULL`) unresolved-material rows in `count_unresolved_material` + the banner set, so the topbar material banner reflects them (the at-a-glance visibility the Phase-18 theme wants).
2. **No-FK-safe terminal resolver** — make the resolve path clear an all-FK-null orphan (it currently raises). Reuse an existing `RESOLUTION_TYPES` value (C2).
3. **Sensible state, not the tier-2 limbo** — route `untracked_broker_position` so it stays **`unresolved`** (a real unaddressed finding) rather than being stamped `pending_ambiguity_resolution` by the classify/dispatch pivot.

## 3. The build (architecture; the implementer grounds the exact impl sites — the witness-evidenced mechanisms in §1 are the starting points)

### 3.1 Part 1 — banner/count
Add a repo reader (e.g. `list_unresolved_material_orphans(conn)` — `trade_id IS NULL AND material_to_review=1 AND resolution='unresolved'`) in `swing/data/repos/reconciliation.py`; UNION it into `count_unresolved_material` + `list_pending_ambiguities_in_banner_set`/the banner-link path in `swing/metrics/discrepancies.py`. The existing trade-JOINed helpers stay UNCHANGED (normal discrepancies byte-identical — C1).

### 3.2 Part 2 — resolver (the one design call)
Make the resolve path (`resolve_discrepancy`, `reconciliation.py:548`, + the CLI `cli_schwab.py` + the web `/reconcile/discrepancy/{id}/resolve` route) FK-null-safe for an orphan. **DESIGN (CHARC, recommended): REUSE `acknowledged_immaterial`** as the terminal resolution for an operator-acknowledged orphan — semantically "I know about this untracked position; stop flagging it" — which **avoids a 4th Phase-18 migration**. **C2: if reuse proves semantically wrong / infeasible** (e.g. a distinct `orphan_acknowledged` value is genuinely needed), **STOP-and-flag to CHARC** — that converts the arc to schema-touching (a new `RESOLUTION_TYPES` value + the #11 trio + a migration 0032), a sub-decision for CHARC + the operator, NOT an implementer call.

### 3.3 Part 3 — state
Route `untracked_broker_position` past the `_pivot_classify_and_dispatch_for_run` ambiguity stamping (in `reconciliation_classifier.py`/`schwab_reconciliation.py`) so it remains `unresolved`. The classify/dispatch behavior for every OTHER type stays byte-identical (C1).

## 4. §3 binding conditions + carve-out scope
- **C1 — additive/non-regressing:** normal (trade-attributed) discrepancies' count/banner/resolve/classify behavior is **byte-identical**; only the orphan (`trade_id NULL`) path is added/changed.
- **C2 — no new schema (reuse the resolution value); STOP-and-flag if a new value is needed** (→ CHARC schema sub-decision).
- **C3 — the orphan end-state:** `unresolved` → banners (Part 1) → clearable via the FK-null-safe resolver (Part 2); after the operator journals the position, it resolves cleanly (no lingering cruft).
- **C4 — sandbox/production:** the read-path (count/banner) + the manual resolver are not sandbox-gated domain mutations; verify the orphan resolver mirrors the existing `resolve_discrepancy` posture (no new contamination surface).
- **Carve-out (CHARC-authorized):** `swing/trades/{reconciliation.py, reconciliation_classifier.py, schwab_reconciliation.py}` + `swing/data/repos/reconciliation.py`. In-scope-but-not-lock-restricted: `swing/metrics/discrepancies.py`, `swing/cli_schwab.py`, the web reconcile route. The read-only default returns after.

## 5. Tests (distinguishing — `feedback_regression_test_arithmetic`)
- Orphan counts toward `count_unresolved_material` + appears in the banner set (pre-fix: 0/excluded — distinguishing).
- Post-recon the orphan is `unresolved`, NOT `pending_ambiguity_resolution` (pre-fix: pending_ambiguity).
- The resolver clears an all-FK-null orphan both-ways (raises pre-fix; resolves post-fix; the row reaches the terminal resolution); a normal discrepancy's resolve path is byte-identical.
- The banner/count for normal trade-attributed discrepancies is unchanged (the C1 additive lock).

## 6. Gates
- **review-strong** (repo-access, binding) to convergence + **codex-auto-review** (repo-access, matched-HIGH). Save each round's response; verify Reviewer A effort=high.
- **§5.10 operator live-witness (binding — the SPCX orphan is real):** re-run the recon (or against the existing orphan) — the `untracked_broker_position` now (a) **counts toward the material banner**, (b) is **`unresolved`** (not pending_ambiguity), (c) is **clearable via the resolver**; and after the operator journals SPCX the orphan **resolves cleanly** (the ID 68 successor does not linger).
- Merged-head no-false-green fast suite + `ruff check swing/`. No RD merge-block (operational recon).

## 7. Locks / return
- Carve-out scoped to §4; read-only default returns after. No new schema (C2). Conventional commits, **ZERO `Co-Authored-By`**, no `--no-verify`.
- The IMPLEMENTER reports to the ORCHESTRATOR in chat; the ORCHESTRATOR posts the return to charc AFTER its QA.

**Cell:** `implementer-opus-high` (touches the resolve/classify machinery across several files; real-judgment, but settled-design + schema-free on the recommended path; opus-max only if the C2 schema sub-decision fires).
