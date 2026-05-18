# Phase 12.5 #2 — Web Tier-2 Discrepancy-Resolution Surface — Writing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance dispatched as the Phase 12.5 #2 writing-plans implementer. No prior conversation context.

**Mission:** Produce an implementation plan for the web Tier-2 discrepancy-resolution surface — decomposing the locked spec at `docs/superpowers/specs/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-design.md` into a single executing-plans dispatch with 11 tasks + per-task acceptance criteria + discriminating-test patterns + files-touched + tests-added projection + commit message stems. **12 operator-locked decisions** are pre-baked (4 from spec §2.1-§2.4 + 8 from §16 accepted at brainstorm defaults per operator-orchestrator scope conversation 2026-05-18 post-merge). Writing-plans surfaces remaining open implementation questions via Codex chain.

**Brief:** `docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-writing-plans-dispatch-brief.md` (this file).

**Sequencing:** Phase 12.5 #2 brainstorm SHIPPED 2026-05-18 at `ac6eb88` (6 Codex rounds NO_NEW_CRITICAL_MAJOR; 1 ACCEPT-WITH-RATIONALE banked R1 M#4 surface attribution naming; ZERO Critical findings; 721-line spec). Writing-plans dispatch (this) produces the plan; executing-plans dispatch ships the code; operator-witnessed gate runs after executing-plans converges. Phase 12.5 #3 (project hygiene maintenance pass) follows Phase 12.5 #2. Phase 13 (4 themes + new T1.SB0 OhlcvCache→_step_charts prerequisite) gated on Phase 12.5 close.

**Expected duration:** ~60-120 min plan-write + 3-5 adversarial Codex rounds. Scope is narrow: single-sub-bundle decomposition of an already-locked spec (schema v19 UNCHANGED; bounded surface — 1 GET + 1 POST route + 1 VM module + 2 templates + base-layout retrofit). Plan line target: **~500-800 lines** (smaller than Phase 12.5 #1's 1230 because no schema work + Sub-bundle B precedent provides 1:1 route format reference + 8 §16 items already operator-accepted).

**Skill posture:**
- Invoke `copowers:writing-plans` skill against this brief + the locked spec.
- `copowers:writing-plans` wraps `superpowers:writing-plans` + adversarial Codex review.
- Output is a plan doc at `docs/superpowers/plans/<YYYY-MM-DD>-phase12-5-bundle-2-web-tier2-discrepancy-resolution-plan.md`.

---

## §0 Read first

In this order:

1. **`docs/superpowers/specs/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-design.md`** — operator-LOCKED + Codex-ratified spec (721 lines; 6 rounds NO_NEW_CRITICAL_MAJOR; 1 ACCEPT-WITH-RATIONALE banked). **THIS IS THE PRIMARY SPEC SUBSTRATE.** Read end-to-end. §2 operator-locks (4 binding clauses); §3 module touch list (14 surfaces verified); §4 route handler design (GET + POST); §5 VM design + builder; §6 template design (context section + form section); §7 per-discrepancy-type context-render helpers; §8 error handling + edge cases; §9 surface attribution (`'operator_web'` via free-TEXT `resolved_by`); §10 banner + dashboard entry-point integration; §11 discriminating-example walkthroughs; §12 sub-bundle decomposition (single sub-bundle; 11 tasks T-2.1..T-2.11); §13 test fixture strategy; §14 schema impact (v19 UNCHANGED — brief §2.7 conjecture corrected); §15 V2 candidates (13 banked); §16 operator decision items (8 items — NOW LOCKED per §1.2 below); §17 operator-witnessed gate plan (6 surfaces).
2. **`docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-brainstorm-return-report.md`** — brainstorm return report (297 lines). Especially §8 forward-binding lessons (8 items beyond spec §15 to inherit); §9 CLAUDE.md status-line refresh draft text; §10 sub-bundle decomposition recommendation; §11 schema impact verdict; §12 composition-surface verification (14 surfaces).
3. **`docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-brainstorm-dispatch-brief.md`** — the brainstorm dispatch brief (`d642175`). Read for context on the 4 operator-pre-locks that drove the spec design.
4. **`docs/phase12-5-bundle-1-oqf-multi-leg-auto-redirect-writing-plans-dispatch-brief.md`** — Phase 12.5 #1 writing-plans dispatch brief (`5c988d2`; 242 lines). Read as PLAN-BRIEF FORMAT REFERENCE — closest scope precedent (single-sub-bundle decomposition; 11 tasks; bounded surface).
5. **`docs/superpowers/plans/2026-05-17-phase12-5-bundle-1-oqf-multi-leg-auto-redirect-plan.md`** — Phase 12.5 #1 plan (1230 lines). Read for PLAN FORMAT REFERENCE. Especially §A (task decomposition format); §C (canonical files-touched roster + grep anchors); §D (locked decisions roll-up); §E (test patterns + naming convention); §F (invariants F1-F25 format); §G (per-task acceptance-criteria narrative); §H (operator-witnessed gate plan). Mirror this format.
6. **`docs/superpowers/plans/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-plan.md`** — Sub-bundle C plan (large; secondary plan format reference; multi-sub-bundle arc).
7. **`swing/web/routes/schwab.py`** — Phase 12 Sub-bundle B `/schwab/setup` POST route — **THIS IS THE PRIMARY ROUTE-HANDLER FORMAT REFERENCE.** Plan's GET/POST handlers mirror this 1:1.
8. **`swing/web/routes/trades.py`** — Phase 6 `/reviews/{id}/complete` POST route + Phase 8 `/trades/{id}/exit` form (alternative format reference; longer form-input handling).
9. **`swing/web/templates/schwab_setup.html.j2`** — Phase 12 Sub-bundle B setup template + Phase 12 Sub-bundle B `/schwab/status` template format. Plan's `reconcile_discrepancy_resolve.html.j2` template extends `base.html.j2` + mirrors form + error-rendering patterns.
10. **`swing/web/view_models/schwab.py`** + **`swing/web/view_models/metrics/shared.py:BaseLayoutVM`** — base-layout VM contract + Phase 12.5 #1's `recent_multi_leg_auto_correction_count` field (just shipped) + Phase 10 T-E.3 retrofit pattern. **CRITICAL** per spec §3 verified at brainstorm: 13 existing base-layout VMs DO NOT inherit `BaseLayoutVM` — they carry standalone fields. New `banner_resolve_link` field requires BOTH adding to `BaseLayoutVM` AND grep-driven retrofit across the 13 standalone VMs.
11. **`swing/cli.py`** — `swing journal discrepancy show-ambiguity` + `resolve-ambiguity` command bodies — **THIS IS THE PRIMARY UX SUBSTRATE.** Web form mirrors their UX 1:1 (operator-locked §2.3).
12. **`swing/trades/reconciliation_ambiguity_choices.py`** — `get_choice_menu(ambiguity_kind)` returns `list[ChoiceMenuItem]`. **THIS IS THE BINDING CHOICE-MENU CONTRACT.** Web form renders one option per item with `title` + `description` + `requires_custom_value` flag.
13. **`swing/trades/reconciliation_auto_correct.py:apply_tier2_resolution`** — service-layer entry. Web POST handler calls this with `resolved_by_override='operator_web'` (per spec §9).
14. **`swing/web/middleware/origin_guard.py`** — OriginGuard strict-mode HX-Headers requirement. **CRITICAL BROWSER-ONLY FAILURE SURFACE** per CLAUDE.md HTMX trinity gotcha.
15. **`CLAUDE.md` Gotchas section** — full read. Especially: HTMX form-driven endpoints (HX-Request propagation + HX-Redirect-vs-303 + HX-Redirect target verification); `... or None` for nullable text columns; SERVER-STAMPING for hidden audit fields; `base.html.j2 is shared`; `Service-layer with conn:` discipline; SAVEPOINT-per-discrepancy; classifier purity; cp1252 stdout encoder (ASCII-only banner text); session-anchor read/write mismatch; sentinel-leak audit; Pass-2-tier-1-FORBIDDEN family (V2-RESOLVED for Pass-1 per Sub-bundle 1 ship); reconciliation flow pivot SAVEPOINT-per-discrepancy.
16. **`docs/orchestrator-context.md`** sections "Currently in-flight work" + "Lessons captured" — ~140+ cumulative forward-binding lessons inherited.

---

## §1 Pre-locked decisions (DO NOT re-litigate)

### §1.1 4 operator-locks from spec §2.1-§2.4 (brainstorm pre-locks BAKED VERBATIM in spec)

1. **Dedicated form page** `GET /reconcile/discrepancy/{id}/resolve` + `POST /reconcile/discrepancy/{id}/resolve` (spec §2.1). NOT inline HTMX swap; NOT 2-step list-page. Plan inherits.
2. **HX-Redirect to `/dashboard?reconcile_resolved={correction_id}`** on successful POST (spec §2.2). 204 + `HX-Redirect` header per Phase 5 R1 M2 LOCK; NOT 303 swap-target; NOT stay-on-form. Plan inherits.
3. **CLI preservation AS-IS** (spec §2.3). Existing `swing journal discrepancy show-ambiguity` + `resolve-ambiguity` commands UNCHANGED. Both surfaces share `apply_tier2_resolution` service-layer entry. Distinguishability via `resolved_by IN ('operator', 'operator_web')` per R1 M#4 LOCK (spec §9). Plan inherits.
4. **Pre-resolution context section** ABOVE choice menu (spec §2.4). Renders discrepancy_type + ambiguity_kind + journal-side value + Schwab-side value + delta. Per-discrepancy-type render helpers (spec §7 cascade analysis). Plan inherits.

### §1.2 8 operator-decision items from spec §16 — ALL ACCEPTED at brainstorm defaults (locked 2026-05-18 post-merge per operator-orchestrator scope conversation)

5. **Banner navigation target** (§16.1 + spec §10.1) — LOCK: link to FIRST pending-ambiguity discrepancy resolve form when one exists; render count text WITHOUT link when count > 0 but ZERO pending-ambiguity rows exist.
6. **First-pending selector ORDER BY** (§16.2 + spec §10.1) — LOCK: `discrepancy_id ASC` (oldest first). Diverges from `list-pending-ambiguities` CLI which uses `DESC`. Rationale: "oldest needs attention next" matches operator's FIFO inclination on banner-driven workflow.
7. **Dashboard per-discrepancy list** (§16.3 + spec §10.2) — LOCK: NOT in V1; banked as §15.5 V2 candidate.
8. **HX-Redirect query-string token** (§16.4 + spec §10.3) — LOCK: include `?reconcile_resolved={correction_id}`; dashboard does NOT consume V1 (operator may add a one-time success toast V2).
9. **HX-Redirect alternate target** (§16.5 + spec §10.4) — LOCK: uniform `/dashboard`; per-type targets banked §15.9 V2 candidate.
10. **JS posture for custom-value toggle** (§16.6 + spec §6) — LOCK: 12-line inline `<script>` in the template; custom-value fieldset always rendered; JS is UX nicety only. Server enforces requirement.
11. **`_parse_parametric_pick_count` helper location** (§16.7 + spec §5.4) — LOCK: NEW private module-level function in `swing/web/view_models/reconcile.py` that DUPLICATES the regex byte-for-byte from `cli.py:2291`. CLI surface stays AS-IS per spec §2.3 OUT-OF-SCOPE preservation lock. Discriminating regression test plants the same `resolution_reason` text in both code paths and asserts byte-identical N. DRY consolidation banked as V2 candidate §15.13.
12. **Operator-witnessed gate surface count** (§16.8 + spec §17.1) — LOCK: 6 surfaces (S1 inline pytest + ruff; S2 banner-link navigation; S3 form-render with context; S4 successful POST + HX-Redirect; S5 banner-clears post-resolve; S6 CLI/web parity end-to-end). S7 (error path) covered by tests; can be promoted to operator gate if any concerns surface.

**All 12 locks are BINDING.** Plan MUST encode these verbatim. Codex chain MUST NOT re-litigate.

---

## §2 Plan decomposition target (single sub-bundle ship)

Spec §12 recommends **single-sub-bundle ship** with 11 tasks T-2.1..T-2.11. Plan operationalizes this:

### §2.1 11-task projection (per spec §12 + brainstorm return report §10)

| Task | Title | Files (illustrative; plan §A locks) | Tests projected |
|---|---|---|---|
| T-2.1 | `_parse_parametric_pick_count` helper in `swing/web/view_models/reconcile.py` (duplicates CLI regex per §1.2 #7 LOCK) | NEW `swing/web/view_models/reconcile.py` (module) + NEW `tests/web/test_reconcile_parametric_pick_count.py` | ~5 |
| T-2.2 | `ReconcileDiscrepancyResolveVM` dataclass + per-discrepancy-type context render helpers (per spec §5 + §7) | MODIFY `swing/web/view_models/reconcile.py` + NEW `tests/web/test_reconcile_resolve_vm.py` | ~10 |
| T-2.3 | VM builder `build_reconcile_discrepancy_resolve_vm(conn, discrepancy_id)` (per spec §5) | MODIFY `swing/web/view_models/reconcile.py` + NEW `tests/web/test_reconcile_resolve_vm_builder.py` | ~8 |
| T-2.4 | NEW `reconcile_discrepancy_resolve.html.j2` template (context + form + 12-line inline `<script>`; ASCII-only) | NEW `swing/web/templates/reconcile_discrepancy_resolve.html.j2` + NEW `tests/web/test_reconcile_resolve_template.py` | ~6 |
| T-2.5 | `GET /reconcile/discrepancy/{id}/resolve` route handler (per spec §4.1; 404/409 error templates) | NEW `swing/web/routes/reconcile.py` (or extend existing) + NEW `tests/web/test_reconcile_resolve_get_route.py` | ~7 |
| T-2.6 | `POST /reconcile/discrepancy/{id}/resolve` route handler (per spec §4.2; form parsing + validation + `apply_tier2_resolution` call with `resolved_by_override='operator_web'`; 204 + HX-Redirect) | MODIFY `swing/web/routes/reconcile.py` + NEW `tests/web/test_reconcile_resolve_post_route.py` | ~8 |
| T-2.7 | `BaseLayoutVM.banner_resolve_link: str \| None = None` field addition (per spec §10.1 + R3 LOCK on BaseLayoutVM-inheritance asymmetry: must add BOTH to BaseLayoutVM AND to 13 standalone-field VMs via grep-driven retrofit) | MODIFY `swing/web/view_models/metrics/shared.py:BaseLayoutVM` + ALL 13+ base-layout-mounted VMs + populate at all builders | ~10 |
| T-2.8 | Banner template + helper integration in `base.html.j2` (banner_resolve_link rendered when populated; retrofit completeness audit per R5 LOCK — discriminating test runs Pass A grep at test time + asserts every matching VM has banner_resolve_link) | MODIFY `swing/web/templates/base.html.j2` + NEW `tests/web/test_base_layout_banner_resolve_link.py` | ~8 |
| T-2.9 | Banner first-pending helper (per spec §10.1 + §1.2 #5 + #6 LOCKs — discriminating test pins `ORDER BY discrepancy_id ASC`; reuses `count_unresolved_material`'s active+closed trade-set per R1 LOCK) | NEW `swing/web/view_models/reconcile.py` helper `select_first_pending_ambiguity_discrepancy_id(conn) -> int | None` + NEW test | ~6 |
| T-2.10 | Error path templates (400 validator-rejected + 404 not-found + 409 already-resolved-or-superseded + 500 service-error; per spec §8) | NEW `swing/web/templates/reconcile_discrepancy_resolve_errors/*.html.j2` (4 templates) + NEW `tests/web/test_reconcile_resolve_error_paths.py` | ~6 |
| T-2.11 | E2E + integration tests (CLI/web parity test + happy path + error paths + slow E2E `test_phase12_5_bundle_2_web_tier2_happy_path.py`) | NEW `tests/integration/test_phase12_5_bundle_2_web_tier2_happy_path.py` (slow-marked) + NEW `tests/integration/test_phase12_5_bundle_2_cli_web_parity.py` | ~5 + 1 slow |

**Total projection**: ~+79 fast tests + 1 slow E2E (~+80 net) + ~+450 LOC (production + tests).

Note: above projection is slightly higher than spec §12's `~+45-75 fast tests` band. Plan §A SHALL refine task boundaries + acceptance criteria + discriminating-test patterns (Codex chain may decompose differently).

### §2.2 Plan §C SHALL design cross-bundle pin (single-bundle dispatch; cross-bundle pin is to existing surfaces)

- Sub-bundle C.D shipped surfaces: read-only consumers of `apply_tier2_resolution` + `reconciliation_ambiguity_choices.get_choice_menu` + `swing journal discrepancy resolve-ambiguity` CLI (parity comparison).
- Phase 12.5 #1 shipped: `recent_multi_leg_auto_correction_count` field on BaseLayoutVM (newly-existing pattern; plan extends with `banner_resolve_link`).
- Phase 12 Sub-bundle B shipped: `/schwab/setup` route + HX-Redirect + atomic-mutation discipline (1:1 route format reference).

### §2.3 Plan §D+ SHALL enumerate

- §C canonical files-touched roster + grep anchors (per Phase 12.5 #1 plan §C format).
- §D locked decisions roll-up (12 locks from §1 above; verbatim).
- §E test patterns + discriminating-test naming convention.
- §F invariants F1-F2N (mirror Phase 12.5 #1 plan §F format; expect ~15-25 invariants for this dispatch).
- §G per-task acceptance criteria narrative for any task spanning multiple files/layers (T-2.7 + T-2.8 + T-2.9 candidates).
- §H operator-witnessed gate plan (6 surfaces per §1.2 #12 LOCK).
- §I cross-bundle pins (single-bundle; pins to shipped surfaces).
- §J V2.1 §VII.F amendment candidates banked during planning (default empty; populate during Codex chain if any surface).
- §K test + LOC projections (refined per-task; matches §2.1 above).
- §L dispatch brief skeleton (orchestrator hand-off for executing-plans).
- §M forward-binding lessons for executing-plans (8 inherited from brainstorm return report §8 + N NEW writing-plans-surfaced).
- §N open questions for orchestrator triage (scaffold; default empty).
- §Z V2 candidates banked (mirrored from spec §15; 13 items).

---

## §3 Adversarial review (Codex)

Invoked automatically by `copowers:writing-plans` after plan draft + before final commit.

**Expected chain shape:** 3-5 substantive Codex rounds (matches Phase 12.5 #1 writing-plans 5 rounds; brainstorm already absorbed 6 Codex rounds + ZERO Critical + only 1 ACCEPT-WITH-RATIONALE; plan should converge faster).

**Adversarial review watch items (Phase 12.5 #2 writing-plans-specific):**

1. **F1 ZERO new schema LOCK** (spec §14). Plan task T-2.6 uses existing `resolved_by_override` kwarg on `apply_tier2_resolution`; NO new column; NO migration. Codex verifies `grep -rn "0020" swing/data/migrations/` returns 0 matches.
2. **CLI surface preservation discipline** (spec §2.3 LOCK + §1.2 #7 LOCK). T-2.1 helper DUPLICATES regex byte-for-byte from `cli.py:2291`; CLI body UNCHANGED. Discriminating test asserts byte-identical N from both code paths against the same input.
3. **BaseLayoutVM-inheritance asymmetry discipline** (spec §3 R3 LOCK). T-2.7 adds `banner_resolve_link` field to BOTH `BaseLayoutVM` AND to all 13+ standalone-field VMs via grep-driven retrofit (Pass A grep for field declaration + Pass B grep for call-site population). Discriminating test (T-2.8) runs Pass A grep at test time + asserts every matching VM has `banner_resolve_link` field; pre-emption pattern per R5 LOCK.
4. **Banner navigation discipline** (§1.2 #5 + #6 LOCKs). T-2.9 helper uses `ORDER BY discrepancy_id ASC` (NOT `DESC` per CLI); reuses `count_unresolved_material`'s active+closed trade-set per R1 LOCK (NOT a separate query); discriminating test pins both.
5. **HTMX trinity discipline** (Phase 5 R1 M1+M2 + Phase 6 I3 LOCKs). T-2.4 template includes `hx-headers='{"HX-Request": "true"}'`; T-2.6 returns 204 + HX-Redirect (NOT 303); HX-Redirect target `/dashboard?reconcile_resolved=<id>` is route-registered.
6. **`... or None` for nullable text columns** (Phase 6 I3 family). T-2.6 form input `resolution_reason` + `custom_value` feed nullable CHECK-constrained schema columns; plan uses `... or None` NOT `... or ""`.
7. **Server-stamping for hidden audit fields** (Phase 8 R2/3/4 LOCK). T-2.6 stamps `resolved_by_override='operator_web'` at handler entry (NOT operator-supplied; NOT hidden form input). Discriminating test asserts tampered hidden-input `resolved_by` is IGNORED.
8. **Hidden state anchor for TOCTOU defense** (Phase 9 D R2 M#1 LOCK; spec §6 R1 LOCK). T-2.4 template includes `ambiguity_kind_at_render` hidden form anchor; T-2.6 verifies anchor matches current discrepancy state; rejects with 409 if mismatch.
9. **Service-layer `with conn:` discipline** (CLAUDE.md gotcha). T-2.6 POST handler does NOT open its own transaction; service-layer `apply_tier2_resolution` owns BEGIN IMMEDIATE / COMMIT / ROLLBACK.
10. **Pipeline-active exclusion** (Sub-bundle C.C `_check_pipeline_not_running`). T-2.6 inherits service-layer pipeline-active check; surfaces as 409 if pipeline running per spec §15.6 V2 banking note (NOT necessarily new in V1 — verify shipped service-layer behavior).
11. **Sentinel-leak audit pattern** (Phase 12 Sub-bundle B precedent). T-2.4 template renders `actual_value_json` content; sentinel-leak test asserts ZERO sensitive data in rendered HTML.
12. **ASCII-only template text** (CLAUDE.md cp1252 gotcha + Phase 12.5 #1 F12). T-2.4 + T-2.8 + T-2.10 templates use ASCII only.
13. **`Co-Authored-By` footer suppression** (project invariant). ZERO drift across ~140+ commits cumulative. Explicit citation in dispatch prompt.
14. **6-surface gate planning** (§1.2 #12 LOCK). Plan §H enumerates each surface + acceptance criterion verbatim.
15. **Audit-row parity test discipline** (spec §13 R2 LOCK). T-2.11 CLI/web parity test uses semantic-shape projection (excludes identity/time/source-row fields), NOT byte-identical comparison.
16. **Retrofit completeness as discriminating test** (R5 LOCK + brainstorm forward-binding lesson #8). T-2.8 test re-runs Pass A grep at test time + asserts every matching VM has `banner_resolve_link` (NOT hard-coded class list).

---

## §4 Deliverable shape

**Plan document at `docs/superpowers/plans/<YYYY-MM-DD>-phase12-5-bundle-2-web-tier2-discrepancy-resolution-plan.md`** (mirror Phase 12.5 #1 plan format):

- §0 Plan overview + cross-references to spec sections
- §1 Operator-locked decisions roll-up (verbatim from spec §2 + §16; 12 locks total)
- §A Task list (T-2.1 .. T-2.11; per-task scope + acceptance criteria + discriminating tests + files-touched + test projection + commit message stem)
- §B Pre-conditions + worktree state
- §C Canonical files-touched roster (grep anchors verified at plan-drafting time)
- §D Locked decisions roll-up
- §E Test patterns + discriminating-test naming convention
- §F Invariants F1-F2N (non-negotiable contracts; expect ~15-25 invariants)
- §G Per-task acceptance criteria narrative for any task spanning multiple files/layers
- §H Operator-witnessed gate plan (6 surfaces per §1.2 #12 LOCK)
- §I Cross-bundle pins (single-bundle; pins to shipped Sub-bundle C.D + Phase 12.5 #1 + Sub-bundle B surfaces)
- §J V2.1 §VII.F amendment candidates banked
- §K Test + LOC projections refined (~+80 fast tests + 1 slow E2E + ~+450 LOC)
- §L Dispatch brief skeleton (orchestrator hand-off for executing-plans)
- §M Forward-binding lessons for executing-plans (8 inherited + N NEW)
- §N Open questions for orchestrator triage (scaffold)
- §Z V2 candidates banked (13 from spec §15)

**Target line count: ~500-800 lines.**

**Commit message stem:** `docs(phase12-5-2-web-tier2-plan): single-sub-bundle decomposition — <N> Codex rounds → NO_NEW_CRITICAL_MAJOR convergent (R1 ... → R<N> ...)`.

---

## §5 OUT OF SCOPE (do not design)

- **Schema additions** — spec §14 LOCK v19 unchanged. Plan-author schema additions escalation rule (per Phase 9 Sub-bundle A return report lesson #7 + spec §16 lesson #3). If plan author surfaces schema need, STOP + escalate.
- **Override of §1 operator-locks** — all 12 (4 spec §2 + 8 §16) are BINDING; do NOT re-litigate.
- **Web Tier-3 override surface** — V2 candidate banked §15.3; separate dispatch.
- **Web Tier-1 auto-correct undo surface** — V2 candidate banked §15.4; separate dispatch.
- **`/reconcile/pending` list page** — V2 candidate banked §15.5; separate dispatch.
- **Audit-chain show page** — V2 candidate banked §15.1; separate dispatch.
- **Success toast renderer on `/dashboard?reconcile_resolved={id}`** — V2 candidate banked §15.2; query token is included per §1.2 #8 LOCK but dashboard does NOT consume V1.
- **Pipeline-active exclusion on Tier-2** — V2 candidate banked §15.6; verify shipped service-layer behavior in plan §C and DO NOT modify.
- **Explicit `surface` column V2 migration** — V2 candidate banked §15.7.
- **CLI helper extraction / DRY refactor** — V2 candidate banked §15.13. Plan T-2.1 DUPLICATES regex byte-for-byte.
- **CLAUDE.md / orchestrator-context archive-splits** — Phase 12.5 #3 scope.
- **Phase 8 walkthrough failing-test triage** — Phase 12.5 #3 scope.
- **Ruff 18 E501 cleanup** — Phase 12.5 #3 scope.
- **Phase 12.5 #1 architectural inconsistency** (plan §H.4 tier-3-override-no-clear semantic vs shipped helper SQL) — Phase 12.5 #3 scope.
- **V2 candidates** (per spec §15; 13 banked items) — do NOT in-scope any; document banked-V2 list in plan §Z.
- **Behavioral changes to non-touched existing surfaces** — Sub-bundle C.C + C.D shipped surfaces UNCHANGED. Especially: `apply_tier2_resolution` service entry (only the `resolved_by_override` kwarg path is consumed; no signature change); CLI commands UNCHANGED; classifier UNCHANGED; banner advisory (Phase 12.5 #1) UNCHANGED.

---

## §6 If you get stuck

- If plan needs a schema element NOT in spec §14 (v19 UNCHANGED LOCK), **STOP + escalate** (Phase 9 Sub-bundle A lesson #7 inheritance).
- If Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag in plan + return report.
- If Codex pushes back on §1 operator-locks (12 binding clauses), HOLD THE LINE — operator-locked at scope conversation 2026-05-18 post-brainstorm-merge.
- If a Codex round surfaces a Sub-bundle C.C + C.D + Phase 12.5 #1 architectural concern (e.g., `apply_tier2_resolution` signature change needed for `resolved_by_override='operator_web'`), STOP + escalate — these surfaces are LOCKED unchanged per spec §3.
- If `_parse_parametric_pick_count` regex changes are needed beyond duplication, BANK as V2 candidate §15.13 + flag in plan + return report (do NOT change CLI body per §1.2 #7 LOCK).
- If `banner_resolve_link` field needs to be conditional per discrepancy state, BANK as V2 candidate (out-of-scope for V1 per §1.2 #5 LOCK — banner links to first pending; absent when zero).
- If plan-author surfaces a need for V2.1 §VII.F amendment, BANK in plan §J + return report.
- DO NOT propose new architectural surfaces within Phase 12.5 #2 plan scope.
- DO NOT add `Co-Authored-By` footer to any commit message (per project invariant; ZERO drift across ~140+ commits cumulative).
- **Pre-Codex orchestrator-side review (NEW C.C lesson #6 — BINDING)**: before invoking `copowers:adversarial-critic`, dispatch a focused reviewer subagent with §1 + §2 + §3 binding contracts as anchors; ask for deviation list ≤300 words. Cheap; absorbed LOCK divergences pre-Codex on Phase 12 C.C + C.D + Sub-bundle 1 + Phase 12.5 #1 brainstorm.

---

## §7 Return report shape

After Codex chain converges + before final commit, draft a return report at `docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-writing-plans-return-report.md`:

1. Final HEAD on branch + commit count breakdown.
2. Codex round chain (R1-RN summary table + convergent shape; finding-count taper).
3. Plan line count.
4. 12 operator-locks verbatim verification.
5. Per-task acceptance criteria summary.
6. Codex Major findings ACCEPTED with rationale (if any). Expectation: ZERO ACCEPT-WITH-RATIONALE (matches brainstorm clean-record streak modulo R1 M#4).
7. V2 candidates banked (per spec §15 + any new surfaced in writing-plans Codex chain).
8. Forward-binding lessons for executing-plans dispatch (8 inherited from brainstorm + N NEW).
9. CLAUDE.md status-line refresh draft text.
10. Schema impact verdict (v19 UNCHANGED expected; escalate if surfaced).
11. Composition-surface verification (`^def ` grep on touched modules confirming public-surface scope).
12. Worktree teardown status.

---

## §8 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES — branch `phase12-5-bundle-2-web-tier2-writing-plans` (matches cleanup-script regex `phase\d+[-_]`). Worktree directory `.worktrees/phase12-5-bundle-2-web-tier2-writing-plans/`.
- **Model:** defer to harness default.
- **Expected duration:** ~60-120 min plan-write + ~30-60 min Codex chain. Total ~2-3 hours operator-paced (per `feedback_time_estimates_overstated.md` calibration).

---

*End of brief. Phase 12.5 #2 writing-plans dispatch — 12 operator-locks pre-baked; single-sub-bundle decomposition target; ~500-800 line plan; 3-5 Codex round expectation. OUTPUT: plan doc that executing-plans phase decomposes into 11 tasks for the final code-ship. Schema v19 UNCHANGED end-to-end.*
