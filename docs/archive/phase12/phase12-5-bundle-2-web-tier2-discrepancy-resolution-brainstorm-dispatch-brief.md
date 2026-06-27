# Phase 12.5 #2 — Web Tier-2 Discrepancy-Resolution Surface — Brainstorm Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 12.5 #2 brainstorm implementer. No prior conversation context.

**Mission:** Produce a design spec for the **web counterpart** to the existing `swing journal discrepancy show-ambiguity` + `resolve-ambiguity` CLI surface (Sub-bundle C.D ship). Today operators resolve tier-2 ambiguities EXCLUSIVELY via CLI (`show-ambiguity <id>` to inspect + `resolve-ambiguity <id> --choice <code> --custom-value <X> --reason <text>` to commit). Phase 12.5 #2 adds the web counterpart — a dedicated form-render page per discrepancy at `GET /reconcile/discrepancy/{id}/resolve` + POST handler that calls the same `apply_tier2_resolution` service-layer entry. Operator has pre-locked 4 high-level architectural decisions (§1 below); your job is to design the COMPLETE architectural surface around those decisions + surface remaining open questions via Codex chain.

**Brief:** `docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-brainstorm-dispatch-brief.md` (this file).

**Sequencing:** Phase 12.5 #1 (OQ-F multi-leg tier-1 auto-redirect) CLOSED 2026-05-18 (integration merge `6109261`; finviz-inbox-auto-fetch-fix mid-dispatch `7a84942`; post-merge housekeeping `bb5ac23`). Phase 12.5 #2 (this dispatch) ships SECOND. Phase 12.5 #3 (Project hygiene maintenance pass) follows. Phase 13 (4 themes; chart pattern recognition + auto-fill + usability + T1.SB0 OhlcvCache→`_step_charts` prerequisite) gated on Phase 12.5 close.

**Expected duration:** ~90-150 min brainstorm + 3-5 adversarial Codex rounds. Scope is bounded — read-only routes + 1 POST handler + 1 template + 1 VM + base-layout retrofit + service-layer consumer (no new service entries). Spec line target: **~500-800 lines** (smaller than Phase 12.5 #1's 1236 because pre-locks are tighter + service layer is fully shipped).

**Skill posture:**
- Invoke `copowers:brainstorming` skill against this brief.
- `copowers:brainstorming` wraps `superpowers:brainstorming` + adversarial Codex review.
- Output is a spec doc at `docs/superpowers/specs/<date>-phase12-5-bundle-2-web-tier2-discrepancy-resolution-design.md`.

---

## §0 Read first

In this order:

1. **`swing/cli.py`** — current `swing journal discrepancy show-ambiguity` + `resolve-ambiguity` command bodies (Sub-bundle C.D ship). **THIS IS THE PRIMARY UX SUBSTRATE.** Locate `discrepancy_show_ambiguity_cmd` + `discrepancy_resolve_ambiguity_cmd`; the web form mirrors their UX 1:1.
2. **`swing/trades/reconciliation_ambiguity_choices.py`** — `get_choice_menu(ambiguity_kind)` returns `list[ChoiceMenuItem]` per ambiguity_kind. Each `ChoiceMenuItem` carries `choice_code`, `title`, `description`, `requires_custom_value: bool`. **THIS IS THE BINDING CHOICE-MENU CONTRACT.** Web form renders one option per item with title + description + custom-value input shown/hidden per the flag.
3. **`swing/trades/reconciliation_auto_correct.py:apply_tier2_resolution`** — service-layer entry. Web POST handler calls this with `surface='web'` (per Phase 12 Sub-bundle B precedent for surface attribution in audit rows). **THIS IS THE WEB→SERVICE BOUNDARY.**
4. **`swing/web/routes/schwab.py`** — Phase 12 Sub-bundle B's `/schwab/setup` POST route precedent. Mirrors the HTMX form + HX-Headers + HX-Redirect + OriginGuard discipline + atomic-mutation + 204 + success-redirect pattern. **THIS IS THE PRIMARY ROUTE-HANDLER FORMAT REFERENCE.**
5. **`swing/web/routes/trades.py`** — Phase 6 `/reviews/{id}/complete` POST route precedent + Phase 8 `/trades/{id}/exit` form. Alternative format reference; longer form-input handling.
6. **`swing/web/view_models/schwab.py:SchwabSetupVM`** + **`swing/web/view_models/metrics/shared.py:BaseLayoutVM`** — base-layout VM contract + Phase 12.5 #1's `recent_multi_leg_auto_correction_count` field (just shipped) + Phase 10 T-E.3 retrofit pattern.
7. **`swing/web/templates/schwab_setup.html.j2`** + **`swing/web/templates/base.html.j2`** — Phase 12 Sub-bundle B's setup template precedent + base layout. Phase 12.5 #2 form template will extend `base.html.j2` + reuse the form-input + error-rendering patterns.
8. **`swing/web/middleware/origin_guard.py`** — OriginGuard strict-mode HX-Headers requirement. **CRITICAL BROWSER-ONLY FAILURE SURFACE** (per CLAUDE.md "HTMX form-driven endpoints" gotcha): embedded forms MUST carry `hx-headers='{"HX-Request": "true"}'` OR `OriginGuard` rejects with 403 on submit.
9. **`docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md`** — Sub-bundle C brainstorm spec, especially §6.2.1 `multi_partial_vs_consolidated` ChoiceMenu definition + per-choice `requires_custom_value` contract; §7 `apply_tier2_resolution` service-layer contract; §8.4 Pass-2-tier-1-FORBIDDEN (preserve V2 LIFT scope — Phase 12.5 #2 is consumer-side only).
10. **`docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md`** §I.3 — V2 candidate banking note for the web Tier-2 surface (the genesis of this dispatch).
11. **`CLAUDE.md` Gotchas section** — especially: `HTMX form-driven endpoints have two browser-only failure surfaces` (HX-Request propagation + HX-Redirect-vs-303); `HX-Redirect target route must be verified to exist`; `For any V1 single-operator form with hidden audit fields, default to SERVER-STAMPING at handler entry`; `base.html.j2 is shared — new vm.foo field requires adding to EVERY base-layout VM`; `Python ... or "" idiom collides with SQL CHECK-constraint nullability`; `Service-layer with conn: opens its own transaction — DO NOT call from inside an outer single-transaction`.
12. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Lessons captured" — ~135+ cumulative forward-binding lessons inherited.
13. **`docs/phase3e-todo.md`** Phase 12.5 RESCOPED entry (operator-locked 2026-05-17) — scope summary of Phase 12.5 #1 + #2 + #3.

---

## §1 Pre-locked operator decisions (OPERATOR-LOCKED 2026-05-18; DO NOT re-litigate)

Per orchestrator-operator scope conversation 2026-05-18 (4-question AskUserQuestion batch post-Phase-12.5-#1-merge):

### §1.1 Decision 1 — Page UX shape: dedicated form page `GET /reconcile/discrepancy/{id}/resolve` linked from banner + dashboard (operator-locked)

NOT inline HTMX swap on dashboard; NOT 2-step list-page → form. Direct entry-point: clicking the unresolved-material banner (or a per-discrepancy 'Resolve' button on dashboard rows) navigates to the dedicated form page. Form POST → HX-Redirect to dashboard (per Decision 2).

**Locked rationale:**
- CLI-symmetric: matches `swing journal discrepancy show-ambiguity <id>` + `resolve-ambiguity <id>` 1:1 (one URL ≈ one CLI invocation; one form ≈ one resolution).
- Matches existing project route patterns: Phase 6 `/reviews/{id}/complete`, Phase 8 `/trades/{id}/exit`, Phase 12 Sub-bundle B `/schwab/setup` — all dedicated form pages with HX-Redirect on success.
- Avoids the "dashboard-becomes-form-heavy under multiple unresolved discrepancies" risk of inline HTMX swap.
- Lower-friction than 2-step list-page navigation given operator typically arrives via banner click (already knows which discrepancy to resolve).

**Brainstorm SHALL design:**
- Exact URL shape (`/reconcile/discrepancy/{id}/resolve` recommended; verify no collision with existing routes).
- Entry-point link locations: banner (linked to the FIRST pending-ambiguity discrepancy? OR to a `/reconcile/pending` list? OR to documentation?) + dashboard per-discrepancy row ('Resolve' button or link).
- Whether dashboard exposes a per-discrepancy view (e.g., the existing `unresolved_material_discrepancies_count` banner currently has NO per-discrepancy drill-down on dashboard; this dispatch may add one OR defer to a separate dispatch).
- Banner navigation target: if banner counts 2 unresolved-material discrepancies, does clicking go to (a) a list page enumerating them, (b) the OLDEST one's resolve form, or (c) documentation?

**DO NOT design HTMX inline swap.** Operator rejected. **DO NOT design 2-step list-page navigation.** Operator rejected.

### §1.2 Decision 2 — HX-Redirect target on POST: back to `/dashboard` (operator-locked)

Successful POST → service writes correction → 204 + HX-Redirect to `/dashboard`. Operator sees the dashboard with the just-resolved discrepancy removed from the unresolved-material banner count + the new correction reflected in Phase 10 metric counters.

**Locked rationale:**
- Matches Phase 12 Sub-bundle B `/schwab/setup` precedent (204 + HX-Redirect to `/config?schwab_setup=ok`).
- Standard back-to-source pattern for banner-driven workflows.
- Lighter-touch than "stay on form with success banner" — operator's typical post-resolution action is to move to next pending discrepancy OR continue daily-loop work; landing on dashboard surfaces the next action naturally.

**Brainstorm SHALL design:**
- Optional query-string success token: `HX-Redirect: /dashboard?reconcile_resolved=<correction_id>` so dashboard can render a one-time success toast (mirror `/config?schwab_setup=ok` pattern from Sub-bundle B). Or NO token if dashboard doesn't need to surface the toast.
- Error-path response shape: validator rejection / discrepancy not found / discrepancy already terminal → HTTP 400 / 404 / 409 with operator-friendly error template (mirror Sub-bundle B's 5 distinct error paths).
- Whether HX-Redirect target should land on Phase 10 metrics dashboard `/metrics/discrepancies` (or equivalent) INSTEAD of `/dashboard` — brainstorm may surface this as an OPEN QUESTION for operator review.

**DO NOT design "stay on form with success banner" pattern.** Operator rejected. **DO NOT design HX-Redirect to `/reconcile/correction/{id}/show`.** Operator rejected (V2 candidate banked).

### §1.3 Decision 3 — CLI counterpart preservation: keep both CLI + web; no deprecation (operator-locked)

Existing `swing journal discrepancy show-ambiguity` + `resolve-ambiguity` CLI commands stay AS-IS. Web is the operator-friendlier interactive surface; CLI stays canonical for scripted/automated flows. Both surfaces share the SAME service-layer entry (`apply_tier2_resolution`).

**Locked rationale:**
- Audit-trail forensic-honesty: `reconciliation_corrections` row carries `surface='cli'` vs `surface='web'` distinguishably (per Phase 12 Sub-bundle B + Sub-bundle 2 `surface='cli'` precedent — V2 widen to include `'web'` enum value may be needed; verify at brainstorm).
- No regression risk for any operator's scripted workflows.
- Lower-touch deprecation path: zero CLI behavioral changes.

**Brainstorm SHALL design:**
- `surface='web'` audit-row attribution: does `reconciliation_corrections` schema CHECK constraint already permit `'web'`? **VERIFY AT BRAINSTORM** — check `swing/data/migrations/0019_*.sql` CHECK enum (Sub-bundle B noted "`surface='cli'` at v18 per CHECK constraint" + banked widening as V2.1 §VII.F amendment). If CHECK constraint excludes `'web'` → schema v19 → v20 migration required (matches Phase 9 Sub-bundle A `_RESOLUTION_VALUES` paired-discipline gotcha).
- Service-layer `apply_tier2_resolution` may or may not accept a `surface` kwarg currently — verify at brainstorm.

**DO NOT design CLI deprecation banner.** Operator rejected. **DO NOT design CLI removal.** Operator rejected.

### §1.4 Decision 4 — Audit-trail surfacing on resolve page: pre-resolution context section (operator-locked)

Form page renders a "pre-resolution context" section ABOVE the choice menu, showing:
- Discrepancy type (e.g., `unmatched_open_fill`, `entry_price_mismatch`, `multi_partial_vs_consolidated`).
- Ambiguity kind (e.g., `unsupported`, `multi_partial_vs_consolidated`).
- Journal-side value (current `fills.price` or `fills.quantity` etc. depending on discrepancy_type).
- Schwab-side value (from `actual_value_json` per spec §3 emission contract).
- Delta (computed; numeric or descriptive depending on type).

Same context information that `swing journal discrepancy show-ambiguity <id>` CLI surfaces today.

**Locked rationale:**
- Operator's natural workflow on banner-driven entry: arrive at form fresh (without prior CLI investigation) → need context to pick correct choice.
- Mirrors CLI `show-ambiguity` UX 1:1.
- Heavier than minimal (just-the-form) but materially-useful; lighter than full audit chain (which would require post-submit drill-down to /reconcile/correction/{id}/show — V2 surface banked per Decision 2).
- Resolution-reason text area + choice menu + custom-value inputs all below the context section.

**Brainstorm SHALL design:**
- Exact context section template shape (table? definition list? key/value pairs?).
- Per-discrepancy-type context-render helpers (some types have richer context than others; `entry_price_mismatch` has price-side semantics; `unmatched_open_fill` has order-match semantics).
- How `actual_value_json` is unpacked for display (parse JSON; render type-appropriate format; handle missing keys gracefully).
- Whether to render the `resolution_reason` text (Sub-bundle C.B emits a multi-line reason per discrepancy) — recommended YES; operator should see classifier's emission reason.

**DO NOT design minimal CLI-symmetric form (no pre-context section).** Operator rejected. **DO NOT design full audit chain link to /reconcile/correction/{id}/show.** V2 candidate banked.

---

## §2 Architectural surface for the brainstorm to design

Given §1's 4 pre-locked decisions, the brainstorm spec MUST design + Codex-review the following:

### §2.1 Route handler shape

**`GET /reconcile/discrepancy/{id}/resolve`** — form-render endpoint.
- 404 if discrepancy_id doesn't exist.
- 409 if discrepancy is NOT in `pending_ambiguity_resolution` resolution state (any terminal state → display "already resolved" error template).
- Render VM populated with: discrepancy context (per §1.4) + `get_choice_menu(ambiguity_kind)` choice list + base-layout VM banner field (`unresolved_material_discrepancies_count` + `recent_multi_leg_auto_correction_count` etc.).
- Form fields: choice radio buttons + per-choice custom-value input (conditionally shown via JS based on `requires_custom_value`) + resolution-reason text area.

**`POST /reconcile/discrepancy/{id}/resolve`** — submission handler.
- Form parsing: `choice_code` (required), `custom_value` (optional; required for choices with `requires_custom_value=True`), `resolution_reason` (required).
- Validation: `choice_code` is in `[c.choice_code for c in get_choice_menu(ambiguity_kind)]`; custom_value present if required.
- Call `apply_tier2_resolution(conn, discrepancy_id=id, choice_code=choice_code, operator_custom_payload=parsed_payload_from_custom_value, operator_reason=resolution_reason, surface='web')` (verify exact signature at brainstorm).
- On success: 204 + HX-Redirect to `/dashboard` (or `/dashboard?reconcile_resolved=<correction_id>` per §1.2 brainstorm question).
- On error: typed HTTP response per error class (400 validator-rejected; 404 not-found; 409 already-resolved-or-superseded; 500 service-error).

### §2.2 View model shape

**`ReconcileDiscrepancyResolveVM`** (suggested name):
- Inherits `BaseLayoutVM` (gets banner fields + theme + nav for free).
- Fields:
  - `discrepancy_id: int`
  - `discrepancy_type: str`
  - `ambiguity_kind: str`
  - `journal_side_label: str` (e.g., "Journal price")
  - `journal_side_value: str` (rendered for display)
  - `schwab_side_label: str` (e.g., "Schwab price")
  - `schwab_side_value: str` (rendered for display)
  - `delta_label: str` (e.g., "Delta")
  - `delta_value: str` (rendered for display; may be "—" for non-numeric types)
  - `resolution_reason_from_classifier: str` (Sub-bundle C.B's emitted reason)
  - `choices: list[ChoiceFormItem]` (rendered from `get_choice_menu(ambiguity_kind)`; each item has `code`, `title`, `description`, `requires_custom_value: bool`, `custom_value_placeholder: str | None`)
  - `form_action: str` (= `/reconcile/discrepancy/{id}/resolve`)
- All fields populated by a builder function `build_reconcile_discrepancy_resolve_vm(conn, discrepancy_id) -> ReconcileDiscrepancyResolveVM`.

### §2.3 Template shape

**`reconcile_discrepancy_resolve.html.j2`** (suggested filename; under `swing/web/templates/`):
- `{% extends "base.html.j2" %}` (per CLAUDE.md base-layout VM gotcha; inherits banner block).
- Pre-resolution context section: definition-list rendering per §1.4.
- Form section: HTML form with `hx-headers='{"HX-Request": "true"}'` (CLAUDE.md HX-Request propagation gotcha) + radio-button per choice + conditional custom-value input + resolution-reason textarea + submit button.
- Submit handler: `hx-post="/reconcile/discrepancy/{{ vm.discrepancy_id }}/resolve"` → 204 + HX-Redirect to `/dashboard`.
- ASCII-only template text (CLAUDE.md cp1252 gotcha; Phase 12.5 #1 F12 inheritance).

### §2.4 Base-layout VM retrofit

**Per CLAUDE.md `base.html.j2 is shared` gotcha:** since `ReconcileDiscrepancyResolveVM` extends `BaseLayoutVM`, the new VM automatically inherits all base-layout fields (Phase 10 T-E.3 5 fields + Phase 12.5 #1's `recent_multi_leg_auto_correction_count` = 6 fields currently). Phase 12.5 #2 does NOT add new base-layout fields.

**However**, the dashboard entry-point button ('Resolve' link on per-discrepancy rows) may require a new `DashboardVM` field for the list of pending-ambiguity discrepancies — TBD at brainstorm (per §1.1 open question about dashboard per-discrepancy view).

### §2.5 OriginGuard + HTMX failure surface pre-emption

Per CLAUDE.md gotchas:
1. **`hx-headers='{"HX-Request": "true"}'`** on the embedded form (Phase 5 R1 M1 LOCK).
2. **204 + HX-Redirect** on success (NOT 303 + swap-target; Phase 5 R1 M2 LOCK).
3. **HX-Redirect target route exists** (Phase 6 I3 LOCK; verify `/dashboard` is registered).
4. **`... or None` for nullable text columns** if any form input feeds nullable CHECK-constrained schema columns (Phase 6 I3 family).

Sub-bundle B's `/schwab/setup` is the canonical 1:1 precedent for these 4 disciplines. Mirror it.

### §2.6 Error handling + edge cases

Brainstorm enumerates error paths + per-error response shape:
- **Discrepancy not found** (404 + error template).
- **Discrepancy already in terminal state** (409 + error template surfacing the existing `resolved_by` + `resolution`).
- **Discrepancy resolution-changed mid-request** (TOCTOU; concurrent CLI invocation; 409 + retry hint).
- **Choice not in menu for this ambiguity_kind** (400 + form re-render with error highlight).
- **Custom-value required but missing** (400 + form re-render with error highlight on custom-value input).
- **Custom-value present but parses to invalid type** (400 + form re-render).
- **Validator rejection at service layer** (400 + form re-render with validator-error text).
- **Service-layer transaction conflict** (500 + retry hint).
- **Pipeline-active exclusion** (per Sub-bundle C.C `_check_pipeline_not_running` discipline; service raises → 409 + retry hint).

### §2.7 Surface attribution: `surface='web'` audit row

Per §1.3: `reconciliation_corrections.surface` schema CHECK constraint MUST permit `'web'`. **VERIFY AT BRAINSTORM** by inspecting `swing/data/migrations/0019_*.sql` CHECK enum. If `'web'` is NOT permitted:
- Schema v19 → v20 migration required (CHECK enum widen to `('pipeline', 'cli', 'web')` OR similar).
- Migration MUST land atomically with the Python-side constant widening per CLAUDE.md schema-CHECK + Python-constant + dataclass-validator paired-discipline gotcha.
- Phase 12 Sub-bundle B return report already banked this as V2.1 §VII.F amendment candidate.

If `'web'` IS already permitted (schema permissive): no migration; web handler just passes `surface='web'` to service.

### §2.8 Sub-bundle decomposition

**Brainstorm proposes** (likely single sub-bundle; verify scope):
- Phase 12.5 #2: route handler + VM + template + dashboard entry-point retrofit + (conditional) schema migration. **~8-12 tasks; ~+30-60 fast tests + 1-2 slow E2E**.

OR if scope expands (Phase 10 dashboard per-discrepancy view; richer pre-context per-type helpers; etc.):
- 12.5-2A: core route + VM + template + service consumer (~6-10 tasks).
- 12.5-2B: dashboard entry-point + per-type context helpers + polish (~4-8 tasks).

**Brainstorm SHALL lock** a recommended decomposition with sub-bundle count + test projection + Codex-round projection.

---

## §3 Open questions (Codex-rounds SHOULD surface answers)

Brainstorm Codex chain SHOULD enumerate + design (operator decision pending at brainstorm-output time):

1. **Banner navigation target** (per §1.1) — banner click → first pending discrepancy resolve form OR list page OR documentation? Recommended: first pending (matches "fix-the-thing-the-banner-says-needs-fixing" flow).
2. **Dashboard per-discrepancy entry-point** (per §1.1) — does dashboard need a per-discrepancy list with 'Resolve' buttons? OR does banner-click-to-first-pending suffice for V2? If list needed, schema/VM impact analysis.
3. **HX-Redirect query-string token** (per §1.2) — `?reconcile_resolved=<correction_id>` for dashboard success toast? OR no token?
4. **HX-Redirect alternate target** (per §1.2) — should some discrepancy types redirect to Phase 10 metrics dashboard `/metrics/discrepancies` (or equivalent) INSTEAD of `/dashboard`?
5. **`surface='web'` schema CHECK widening** (per §2.7) — verify CHECK enum permits `'web'`; if not, schema v19 → v20 migration scope + bundle into Phase 12.5 #2 OR defer to Phase 12.5 #3.
6. **Per-discrepancy-type context-render helpers** (per §1.4 + §2.2) — how many distinct render shapes are needed? `entry_price_mismatch` / `close_price_mismatch` share price-side semantics; `unmatched_open_fill` / `unmatched_close_fill` share order-match semantics; `multi_partial_vs_consolidated` is its own shape; `stop_mismatch` is its own shape; `position_qty_mismatch` is its own shape; `cash_movement_mismatch` is its own shape; etc.
7. **JS for conditional custom-value input** — minimal JS to toggle custom-value visibility per choice, OR pure HTMX `hx-show`/`hx-trigger` pattern, OR static "always show all custom-value inputs (operator picks the one that matters)"?
8. **Validation re-render shape on 400** — re-render the form with error highlight + preserve filled values? Mirror Sub-bundle B's 5 error templates?
9. **Test fixture strategy** — TestClient + cassette OR pure TestClient + monkeypatched service? (TestClient lifespan discipline per CLAUDE.md gotcha.)
10. **Operator-witnessed gate surface count** — likely 5-7 surfaces (S1 fast/ruff + S2 entry-point click navigation + S3 form-render with context + S4 successful POST + HX-Redirect + S5 banner-clears post-resolve + optional S6 error path + optional S7 CLI parity).

---

## §4 OUT OF SCOPE (do not design)

- **Schema additions beyond §2.7 `surface='web'` CHECK widening** — Phase 12.5 #3 maintenance pass absorbs anything else (per phase3e-todo Phase 12.5 RESCOPED entry).
- **HTMX inline-swap UX** — Decision 1 rejected by operator; dedicated form page locked.
- **2-step list-page → form navigation** — Decision 1 rejected by operator.
- **"Stay on form with success banner"** — Decision 2 rejected by operator.
- **HX-Redirect to `/reconcile/correction/{id}/show`** — Decision 2 rejected; V2 candidate banked.
- **CLI deprecation banner OR CLI removal** — Decision 3 rejected by operator.
- **Minimal CLI-symmetric form (no pre-context section)** — Decision 4 rejected by operator.
- **Full audit chain link to `/reconcile/correction/{id}/show`** — Decision 4 rejected; V2 candidate banked.
- **Web Tier-3 override surface** — separate V2 surface beyond Phase 12.5 scope.
- **Web Tier-1 auto-correct undo surface** — separate V2 surface.
- **Pass-2 LIFT beyond Phase 12.5 #1's locked scope** — V2 follow-up.
- **CLAUDE.md / orchestrator-context archive-splits** — Phase 12.5 #3 scope.
- **Phase 8 walkthrough failing-test triage** — Phase 12.5 #3 scope.
- **Ruff 18 E501 cleanup** — Phase 12.5 #3 scope.
- **Phase 12.5 #1 architectural inconsistency** (plan §H.4 tier-3-override-no-clear semantic vs shipped helper SQL) — Phase 12.5 #3 scope.
- **Phase 13 chart-pattern detection** — Phase 13 scope.
- **OhlcvCache → `_step_charts` wiring (T1.SB0 prerequisite)** — Phase 13 scope (operator-directed amendment 2026-05-18).
- **Behavioral changes to non-touched existing surfaces** — Phase 12.5 #2 is consumer-side of Sub-bundle C.A-D + Phase 12.5 #1 ships. Especially: `apply_tier2_resolution` service entry UNCHANGED (only the `surface='web'` kwarg path may need a small addition); CLI commands UNCHANGED; classifier UNCHANGED; banner advisory (Phase 12.5 #1) UNCHANGED.

---

## §5 Adversarial review (Codex)

Invoked automatically by `copowers:brainstorming` after the spec draft + before final commit.

**Expected chain shape:** 3-5 substantive Codex rounds (matches Phase 12.5 #1 brainstorm's 7-round chain at lower bound; matches Sub-bundle 2 / Sub-sub-bundle C.A's 2-3-round chains at midpoint; scope is bounded by §1's operator-locks).

**Adversarial review watch items (Phase 12.5 #2-specific):**

1. **CLI parity discipline** — web POST path MUST produce identical `reconciliation_corrections` row shape as CLI POST path (modulo `surface='cli'` vs `surface='web'`). Discriminating test: parametrize per choice; assert CLI + web produce equivalent correction rows.
2. **HX-Headers propagation** (Phase 5 R1 M1 LOCK) — embedded form carries `hx-headers='{"HX-Request": "true"}'`; OriginGuard strict-mode passes.
3. **HX-Redirect on success** (Phase 5 R1 M2 LOCK) — 204 + `HX-Redirect: /dashboard`; not 303 swap-target.
4. **HX-Redirect target exists** (Phase 6 I3 LOCK) — `/dashboard` route registered; explicit test or assertion.
5. **`... or None` for nullable text columns** (Phase 6 I3 family) — `resolution_reason` and `custom_value` form inputs feed nullable CHECK-constrained columns; verify `... or None` not `... or ""`.
6. **Server-stamping for hidden audit fields** (Phase 8 R2.M2+R3.M2+R4.M2 LOCK) — `surface='web'` is server-stamped at handler entry NOT operator-supplied; same discipline for any session-anchor timestamps.
7. **Schema-CHECK + Python-constant + dataclass-validator paired discipline** (CLAUDE.md gotcha) — if `surface='web'` widening requires schema migration, all 3 surfaces land in 1 atomic commit.
8. **Base-layout VM retrofit** (Phase 10 T-E.3 + Phase 12.5 #1 F23 LOCK) — `ReconcileDiscrepancyResolveVM` extends `BaseLayoutVM`; banner fields inherited; introspection test asserts field presence.
9. **Service-layer `with conn:` discipline** (CLAUDE.md gotcha) — POST handler does NOT open its own transaction; service-layer entry owns BEGIN/COMMIT.
10. **Pipeline-active exclusion** (Sub-bundle C.C `_check_pipeline_not_running`) — POST handler inherits service-layer pipeline-active check; surfaces as 409 if pipeline running.
11. **Sentinel-leak audit pattern** — web template renders `actual_value_json` content; sentinel-leak test asserts ZERO sensitive data in rendered HTML (template-rendering audit per Phase 12 Sub-bundle B precedent).
12. **`Co-Authored-By` footer suppression** (project invariant) — explicit citation in dispatch prompts; ~135+ cumulative ZERO drift streak.
13. **ASCII-only template text** (CLAUDE.md cp1252 gotcha + Phase 12.5 #1 F12) — no non-ASCII glyphs in any rendered output.
14. **Determinism for context section** — pre-resolution context renders identical strings on identical discrepancy_id (no time-of-day-sensitive content; no random sort).

---

## §6 Deliverable shape

**Spec document at `docs/superpowers/specs/<YYYY-MM-DD>-phase12-5-bundle-2-web-tier2-discrepancy-resolution-design.md`** (mirror Phase 12.5 #1 spec format):

- §0 Glossary
- §1 Architecture overview
- §2 Pre-locked operator decisions (the 4 from §1 above; verbatim binding clauses)
- §3 Module touch list
- §4 Route handler design (GET + POST)
- §5 VM design + builder function
- §6 Template design (context section + form section)
- §7 Per-discrepancy-type context-render helpers (cascade analysis per §3 #6 open question)
- §8 Error handling + edge cases
- §9 Surface attribution (`surface='web'` schema impact + service-layer wiring)
- §10 Banner + dashboard entry-point integration
- §11 Discriminating-example walkthroughs (5-10 cases covering pass + fail + edge paths)
- §12 Sub-bundle decomposition (single OR 2A/2B)
- §13 Test fixture strategy (TestClient discipline + cassette/monkeypatch tradeoff)
- §14 Schema impact analysis (v19 unchanged OR v19 → v20)
- §15 V2 candidates banked
- §16 Operator decision items pending (anything Codex chain surfaces)

**Target line count: ~500-800 lines** (smaller than Phase 12.5 #1's 1236 because service layer is fully shipped + pre-locks are tighter + Sub-bundle B precedent provides 1:1 route format reference).

**Commit message stem:** `docs(phase12-5-2-web-tier2-spec): brainstorm — <N> Codex rounds → NO_NEW_CRITICAL_MAJOR convergent (R1 ... → R<N> ...)`.

---

## §7 If you get stuck

- If the architectural shape proposed at §2 conflicts with operator §1 LOCKs, the operator LOCKs WIN.
- If §1 LOCKs ARE the source of conflict (e.g., dedicated-form-page UX surface drift creates a design hole), SURFACE the conflict as an Open Question (§3 above) for operator review.
- If a Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly in spec + return report.
- If you need a schema element NOT in §2.7 `surface='web'` widening, **STOP + escalate** (any schema additions beyond §2.7 must route through orchestrator).
- If Codex pushes back on the dedicated-form-page UX, HOLD THE LINE — §1.1 operator-lock.
- If Codex pushes back on the back-to-dashboard HX-Redirect target, HOLD THE LINE — §1.2 operator-lock.
- If Codex pushes back on CLI preservation (e.g., "but CLI duplicates web UX..."), HOLD THE LINE — §1.3 operator-lock.
- If Codex pushes back on pre-resolution context section (e.g., "but minimal-form is simpler..."), HOLD THE LINE — §1.4 operator-lock.
- DO NOT propose schema additions within Phase 12.5 #2 scope beyond §2.7 widening (escalation rule).
- DO NOT add `Co-Authored-By` footer to ANY commit message (project invariant; ~135+ cumulative ZERO drift streak; CLAUDE.md governs).
- DO NOT propose web Tier-3 override surface within Phase 12.5 #2 scope (§4 lock; V2 candidate).
- DO NOT propose web Tier-1 auto-correct undo surface within Phase 12.5 #2 scope (§4 lock; V2 candidate).
- DO NOT propose Phase 12.5 #3 maintenance pass items within Phase 12.5 #2 scope (§4 lock).

---

## §8 Return report shape

After Codex chain converges + before final commit, draft a return report at `docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-brainstorm-return-report.md`:

1. Final HEAD on branch + commit count breakdown.
2. Codex round chain (R1-RN summary table + convergent shape; finding-count taper).
3. Spec line count.
4. Pre-locked operator decisions verbatim verification.
5. §3 Open Questions: which surfaced + which Codex resolved + which deferred to operator review.
6. Codex Major findings ACCEPTED with rationale (if any).
7. Cumulative V2 candidates banked.
8. Forward-binding lessons for writing-plans dispatch.
9. CLAUDE.md status-line refresh draft text.
10. Sub-bundle decomposition recommendation (single sub-bundle OR 2A/2B).
11. Schema impact verdict (v19 unchanged OR v20 migration required + rationale).
12. Composition-surface verification.
13. Worktree teardown status.

---

## §9 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES — branch `phase12-5-bundle-2-web-tier2-brainstorm` (matches cleanup-script regex `phase\d+[-_]`). Worktree directory `.worktrees/phase12-5-bundle-2-web-tier2-brainstorm/`.
- **Model:** defer to harness default.
- **Expected duration:** ~90-150 min brainstorm + ~30-90 min Codex chain. Total ~2.5 hours operator-paced.

---

*End of brief. Phase 12.5 #2 brainstorm dispatch — 4 operator-locked decisions pre-baked; architectural surface bounded by Sub-bundle B + Sub-bundle C.C+D precedents; ~500-800 line spec target; 3-5 Codex round expectation. OUTPUT: design spec for web Tier-2 discrepancy-resolution surface that writing-plans phase can decompose into a single executing-plans dispatch.*
