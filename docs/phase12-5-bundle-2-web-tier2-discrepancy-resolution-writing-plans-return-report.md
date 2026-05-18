# Phase 12.5 #2 Web Tier-2 Discrepancy-Resolution Surface — Writing-Plans Return Report

**Phase:** writing-plans
**Branch:** `phase12-5-bundle-2-web-tier2-writing-plans`
**Date:** 2026-05-18
**Dispatch brief:** `docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-writing-plans-dispatch-brief.md` (commit `b4d08a6` on main)
**Locked spec:** `docs/superpowers/specs/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-design.md` (721 lines; brainstorm SHIPPED at `ac6eb88`)

---

## §1 Final HEAD + commit count breakdown

**Final HEAD on branch:** `3079154`

**6 commits on branch (above `origin/main` HEAD `b4d08a6`):**

| # | SHA | Subject |
|---|-----|---------|
| 1 | `64aa76f` | docs(phase12-5-2-web-tier2-plan): single-sub-bundle decomposition draft (1075 lines) |
| 2 | `917d819` | docs(phase12-5-2-web-tier2-plan): pre-Codex review fixes |
| 3 | `58fa842` | docs(phase12-5-2-web-tier2-plan): R1 Codex fixes — 3 Major + 4 Minor resolved |
| 4 | `61034ff` | docs(phase12-5-2-web-tier2-plan): R2 Codex fixes — 2 Major + 3 Minor resolved |
| 5 | `d15b38c` | docs(phase12-5-2-web-tier2-plan): R3 Codex fixes — 1 Major + 4 Minor resolved |
| 6 | `3079154` | docs(phase12-5-2-web-tier2-plan): R4 Minors resolved (chain converged NO_NEW_CRITICAL_MAJOR) |

**ZERO `Co-Authored-By` footer drift across all 6 commits.** ZERO `--no-verify`. ZERO `--amend`. Each commit message signed by `git config user.name = "Reid Smythe"`. Project-cumulative footer-suppression streak now ~145+ commits across Phase 11 + Phase 12 + Phase 12.5 arcs.

---

## §2 Codex chain summary + convergent shape

**5 substantive Codex rounds + 1 confirmation round (R5) → NO_NEW_CRITICAL_MAJOR convergent monotonic-Major taper.** Pre-Codex orchestrator-side review absorbed 3 Major + 2 Minor before R1 (BINDING per brief §6 + NEW Phase 12 C.C lesson #6).

| Round | C | M | m | Verdict | Notes |
|-------|---|---|---|---------|-------|
| Pre-Codex review | 0 | 3 | 2 | n/a (orchestrator-side) | 3M (VM field count 19→18, helper count 11→10, builder kwarg vs spec divergence) + 2m (banner-glyph carve-out wording, db-connection pattern asymmetry) |
| R1 | 0 | 3 | 4 | ISSUES_FOUND | M (task-ordering T-2.10 vs T-2.5/T-2.6; ValueError race vs handler payload split; stale "11 per-type" line 99); m (5 F-cross-ref errors; 16-vs-17 branches; parametric valid_choices omits parametric codes; hx-headers exact-substring brittle) |
| R2 | 0 | 2 | 3 | ISSUES_FOUND | M (T-2.6 template-branch sequencing follow-up; spec-vs-plan supersession); m (parametric-order phrasing; race-test mock pattern; F4 stale test name) |
| R3 | 0 | 1 | 4 | ISSUES_FOUND | M (T-2.10 __post_init__ tightening would break T-2.5/T-2.6 green paths); m (stale T-2.5 note; §C roster stale "11 per-type" + error-template T-2.10 NEW marking; §C routes-touched contradiction; "pure read-only consumer" phrasing) |
| R4 | 0 | 0 | 4 | **NO_NEW_CRITICAL_MAJOR** | m (T-2.10 error_kind constants without call-site consumers; §C "__post_init__ polish" stale; T-2.10 commit-message stem; VM "pure" claim) |
| R5 (confirmation) | 0 | 0 | 0 | **NO_NEW_CRITICAL_MAJOR** | CLEAN SEAL — empty C/M/m lists |

**Convergent shape:** Major findings tapered 3 → 2 → 1 → 0 → 0 across R1-R5 (monotonic decreasing). **ZERO Critical findings entire chain.** **ZERO ACCEPT-WITH-RATIONALE banked.**

**Aggregate finding-count:** 6 Major + 15 Minor surfaced across 4 substantive rounds; ALL 6 Major resolved with code-content fixes; ALL 15 Minor absorbed pre-seal. Cleanest writing-plans chain shape since Phase 12.5 #1 writing-plans (5 rounds, 1 Critical + 12 Major + 8 Minor, ZERO ACCEPT-WITH-RATIONALE).

---

## §3 Plan line count

**1082 lines** at sealed HEAD. Above the brief §1 target band of 500-800 by ~280 lines; reasonable given the 30-file retrofit footprint (Pass A grep 14 declaration sites + Pass B grep 21 call sites) requires deep §C/§G/§A enumeration. Comparable to Phase 12.5 #1 plan's 1230-line precedent (which had schema-unchanged + 11-task + 13-VM-retrofit shape close to this dispatch).

---

## §4 12 operator-locks verbatim verification

All 12 binding clauses encoded verbatim at plan §D:

| # | LOCK | Source | Plan section |
|---|------|--------|--------------|
| 1 | Dedicated form page `GET\|POST /reconcile/discrepancy/{id}/resolve` | spec §2.1 / brief §1.1 #1 | §D.1 #1; T-2.5; T-2.6; §A handler flow |
| 2 | HX-Redirect to `/dashboard?reconcile_resolved={correction_id}` on success (204 + header NOT 303) | spec §2.2 / brief §1.1 #2 | §D.1 #2; T-2.6 step 7; F5 LOCK |
| 3 | CLI counterpart preservation AS-IS; surface attribution via `resolved_by IN ('operator', 'operator_web')` | spec §2.3 / brief §1.1 #3 | §D.1 #3; §C.3 UNCHANGED roster; F2 + F3 LOCKs |
| 4 | Pre-resolution context section ABOVE choice menu | spec §2.4 / brief §1.1 #4 | §D.1 #4; T-2.2 + T-2.4 |
| 5 | Banner navigation = link to FIRST pending-ambiguity discrepancy resolve form | spec §16.1 / brief §1.2 #5 | §D.2 #5; T-2.8 + T-2.9; spec §10.1 |
| 6 | First-pending selector ORDER BY = `discrepancy_id ASC` (oldest-first; diverges from CLI DESC) | spec §16.2 / brief §1.2 #6 | §D.2 #6; T-2.9 helper |
| 7 | NO V1 dashboard per-discrepancy list (V2-banked §15.5) | spec §16.3 / brief §1.2 #7 | §D.2 #7; §Z #5 |
| 8 | HX-Redirect query-string token `?reconcile_resolved={correction_id}` INCLUDED (informational; dashboard does NOT consume V1) | spec §16.4 / brief §1.2 #8 | §D.2 #8; T-2.6 step 7 |
| 9 | Uniform `/dashboard` HX-Redirect target (per-type targets V2-banked §15.9) | spec §16.5 / brief §1.2 #9 | §D.2 #9; T-2.6 step 7; §Z #9 |
| 10 | JS posture = 12-line inline `<script>` for custom-value toggle; fieldset always rendered | spec §16.6 / brief §1.2 #10 | §D.2 #10; T-2.4; F9 LOCK |
| 11 | `_parse_parametric_pick_count` helper DUPLICATED in web VM (CLI surface UNCHANGED) | spec §16.7 / brief §1.2 #11 | §D.2 #11; T-2.1; §C.3 UNCHANGED roster |
| 12 | 6-surface operator-witnessed gate (S1 pytest+ruff+slow E2E; S2 banner-link; S3 form-render; S4 POST+HX-Redirect; S5 banner-clears; S6 CLI/web parity) | spec §16.8 / brief §1.2 #12 | §D.2 #12; §H operator-witnessed gate plan verbatim |

**Result: 12/12 operator-locks verbatim-encoded in plan §D.** ZERO LOCK divergences in the integrated plan. Codex chain did NOT re-litigate any of the 12; the chain focused on operationalization correctness + downstream consistency + spec-vs-plan delta banking.

---

## §5 Per-task acceptance criteria summary

| Task | Title | Files (NEW/MOD) | Tests projected |
|------|-------|------------------|------------------|
| T-2.1 | `_parse_parametric_pick_count` helper (PURE; duplicates `cli.py:2291` regex byte-for-byte) | NEW `swing/web/view_models/reconcile.py` (module skeleton) + NEW `tests/web/test_reconcile_parametric_pick_count.py` | 5 |
| T-2.2 | 3 frozen dataclasses (`ReconcileDiscrepancyResolveVM` 18 fields + `ReconcilePreResolutionContext` 14 fields + `ReconcileChoiceFormItem` 6 fields) + 10 per-discrepancy-type render helpers + generic fallback | MOD `swing/web/view_models/reconcile.py` + NEW `tests/web/test_reconcile_resolve_vm.py` | 12 |
| T-2.3 | `build_reconcile_discrepancy_resolve_vm(conn, discrepancy_id, *, prior_*, error_band_*)` builder | MOD `swing/web/view_models/reconcile.py` + NEW `tests/web/test_reconcile_resolve_vm_builder.py` | 8 |
| T-2.4 | NEW `reconcile_discrepancy_resolve.html.j2` template (context + form + 12-line inline JS; `hx-headers` + hidden anchor; ASCII-only NEW text) | NEW template + NEW `tests/web/test_reconcile_resolve_template.py` | 6 |
| T-2.5 | `GET /reconcile/discrepancy/{id}/resolve` handler + minimal stub of error template (2 branches) + `ReconcileDiscrepancyErrorVM` | NEW `swing/web/routes/reconcile.py` + MOD `swing/web/app.py` (router include) + NEW error template stub + MOD VM module (error VM) + NEW `tests/web/test_reconcile_resolve_get_route.py` | 7 |
| T-2.6 | `POST /reconcile/discrepancy/{id}/resolve` handler (18-branch catch-ladder with 14a/14b race split) + EXTEND error template (3 remaining branches) | MOD `swing/web/routes/reconcile.py` + MOD error template + NEW `tests/web/test_reconcile_resolve_post_route.py` | 9 |
| T-2.7 | `BaseLayoutVM.banner_resolve_link: str \| None = None` + 13-VM standalone retrofit (Pass A grep enumeration) | MOD `swing/web/view_models/metrics/shared.py` + 13 modified VMs across 9 files + NEW `tests/web/test_base_layout_vm_banner_resolve_link.py` | 10 |
| T-2.8 | `base.html.j2` banner-link integration (wrap count in `<a>` when populated) + retrofit completeness audit (Pass A grep at test time) | MOD `swing/web/templates/base.html.j2` + NEW `tests/web/test_base_layout_banner_resolve_link.py` | 8 |
| T-2.9 | `list_pending_ambiguities_in_banner_set` + `fetch_first_pending_ambiguity_resolve_link_path` helpers + Pass B retrofit threads `banner_resolve_link` into VM constructors at 21 call sites (20 Pattern A conn-shape + 1 Pattern B db_path-shape sibling helper) | MOD `swing/metrics/discrepancies.py` + MOD 12 files with 21 callsites + NEW `tests/metrics/test_discrepancies_first_pending_ambiguity.py` + NEW per-route population regression test | 6 + per-route |
| T-2.10 | Error template POLISH (a11y attrs + footer consistency + per-branch `data-error-kind` discriminator) + per-branch coverage tests | MOD error template + MOD VM module (docstring only) + NEW `tests/web/test_reconcile_resolve_error_paths.py` | 6 |
| T-2.11 | Slow E2E `test_phase12_5_bundle_2_web_tier2_happy_path` + CLI/web parity test (semantic-shape projection per spec §13.3 R2 LOCK) + XSS-escape audit + forbidden-sentinel absence audit + cycle-checklist additions | NEW `tests/integration/test_phase12_5_bundle_2_web_tier2_happy_path.py` (slow) + NEW `tests/integration/test_phase12_5_bundle_2_cli_web_parity.py` + NEW `tests/web/test_reconcile_resolve_xss_and_sentinel_audit.py` + MOD `docs/cycle-checklist.md` | 5 + 1 slow |

**Total projection: ~+81 fast tests + 1 slow E2E + ~+970 production LOC + ~+1145 test LOC.**

---

## §6 Codex Major findings ACCEPTED with rationale

**ZERO ACCEPT-WITH-RATIONALE banked.** All 6 Major findings across R1-R3 resolved with code-content fixes. Matches Phase 12.5 #1 writing-plans clean-record streak + brainstorm's clean-record streak modulo R1 M#4 (which was banked at brainstorm, not at this dispatch).

---

## §7 V2 candidates banked

**13 V2 candidates** at plan §Z verbatim from spec §15 (no new V2 candidates surfaced during writing-plans Codex chain):

1. `/reconcile/correction/{id}/show` audit-chain page
2. One-time success toast on `/dashboard?reconcile_resolved={id}`
3. Web Tier-3 override surface
4. Web Tier-1 auto-correct undo surface
5. `/reconcile/pending` list page
6. `reconcile_resolved` toast renderer (sibling of #2)
7. Pipeline-active exclusion on web Tier-2 path
8. `schwab_api_call_id` form input on web
9. Per-discrepancy-type HX-Redirect targets
10. Explicit `surface` column on `reconciliation_corrections` (v19 → v20 migration)
11. Inline HTMX swap UX (rejected V1 per operator-LOCK §1.1 #1)
12. JS for conditional custom-value input → move to `static/reconcile.js`
13. DRY `_parse_parametric_pick_count` helper (consolidate into `swing/trades/reconciliation_ambiguity_choices`)

**3 V2.1 §VII.F amendment candidates banked at plan §J** (NEW from Codex chain):

- **J1** (banked at pre-Codex review): spec §5.4 builder signature should enumerate `prior_ambiguity_kind_at_render` kwarg.
- **J2** (Codex R1 M#2 + R2 M#2): spec §4.2 step 5 + §8.1 14th row + §8.2 race semantics should be amended to enumerate the 14a (400) + 14b (409) split for the POST-service `ValueError` disposition.
- **J3** (Codex R1 m#3 + R2 m#1): spec §4.2 step 3f no-match branch should enumerate parametric-pick inclusion in `valid_choices` for `multi_match_within_window` ambiguity_kind.

---

## §8 Forward-binding lessons for executing-plans dispatch

**8 lessons INHERITED from brainstorm return report §8** (encoded at plan §M):

1. Brief-conjecture-vs-actual-schema gap → grep verify at brainstorm/plan time.
2. BaseLayoutVM-inheritance is asymmetric (13 existing VMs DO NOT inherit; carry standalone fields).
3. Hidden state anchors are DISTINCT from hidden audit fields (server-stamp audit fields; form-render hidden anchors for TOCTOU defense).
4. OriginGuard strict-vs-non-strict 303-fallback shapes (204 + HX-Redirect under HTMX; 303 RedirectResponse under non-HTMX same-origin).
5. Banner-link targets derive from canonical helper used by banner count.
6. Audit-row parity tests use semantic-shape projection.
7. Grep-driven audits split by intent (Pass A field-declaration vs Pass B call-site population).
8. Retrofit completeness is a discriminating test (runs grep at test time; not hard-coded class list).

**5 NEW lessons surfaced during writing-plans Codex chain** (to bank at executing-plans dispatch brief §M):

L-W1. **Stub-then-extend ordering for shared templates.** When task A renders a template branch that task B owns, the template needs an initial stub at task A — OR task B must add the branch at the same commit as the rendering call. Don't defer template branches to a later task than the calling code. (Codex R1 M#1 + R2 M#1 family.)

L-W2. **Service `ValueError` requires re-read disambiguation in concurrent-write callers.** If the route's re-render-on-400 path has preconditions that the service's pre-check enforces (e.g., resolution=pending), a `ValueError` raised by the service indicating "precondition violated" cannot be 400-rendered without re-checking the precondition first — otherwise the operator gets an internal-error loop. Pattern: catch ValueError; re-read; if precondition still holds → 400; else → 409. (Codex R1 M#2.)

L-W3. **`F#` cross-reference accuracy across §A acceptance criteria + §F invariant table is non-trivial.** Plans with 21+ invariants need a final F#-citation sweep before sealing. Symptom: 5 cross-ref errors at R1 m#1 + 1 at R3. Fix: include F#-mapping audit in the self-review checklist; OR migrate to anchor links the markdown renderer validates. (Codex R1 m#1 + R3 m#3.)

L-W4. **Spec text out of sync with plan fixes requires explicit "Plan supersedes spec" notes + §J amendment banking.** When Codex chain fixes introduce plan-vs-spec divergences (e.g., new branch behavior; widened error path), the spec sections referenced as authoritative locks become STALE for an executing-plans implementer reading them in isolation. Pattern: bank V2.1 §VII.F amendment in §J + add "Plan supersedes spec" note at the relevant §A acceptance. (Codex R2 M#2.)

L-W5. **Late VM-validator additions risk breaking already-green callers.** Adding `__post_init__` tightening or new contract requirements to a dataclass that earlier tasks already consume is a regression vector — every prior call site is exempt from the new contract without an audit. Pattern: validator changes land at the SAME task as every call site is audited, OR are deferred V2. (Codex R3 M#1.)

---

## §9 CLAUDE.md status-line refresh draft text

```
**Phase 12.5 #2 writing-plans SHIPPED 2026-05-18** at `<integration-merge-SHA-PENDING>` (integration merge of `phase12-5-bundle-2-web-tier2-writing-plans` via `--no-ff`; 6 plan-branch commits = 1 initial draft + 1 pre-Codex review + 4 Codex-fix; **5 substantive Codex rounds + 1 R5 confirmation → NO_NEW_CRITICAL_MAJOR** convergent monotonic-Major taper (Pre-Codex 3M/2m absorbed orchestrator-side → R1 0C/3M/4m → R2 0C/2M/3m → R3 0C/1M/4m → R4 0C/0M/4m → R5 0C/0M/0m CLEAN SEAL); **ZERO Critical findings** entire chain; **ZERO ACCEPT-WITH-RATIONALE banked** — all 6 Major + 15 Minor resolved with code-content fixes (matches Phase 12.5 #1 writing-plans + Sub-bundle C.D + post-Phase-12 1/1.5/2 + Phase 12.5 #1 brainstorm + Phase 12.5 #2 brainstorm clean-record precedents); ZERO Co-Authored-By footer drift across 6 commits (~145+ project-cumulative streak preserved); 1082-line plan at `docs/superpowers/plans/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-plan.md` (above 800-line brief target — driven by 30-file retrofit footprint enumeration in §C). **R1 M#1 highest-value catch**: T-2.5/T-2.6 would have shipped with route handlers rendering an error template that T-2.10 was supposed to create later; stub-then-extend reorder (T-2.5 stubs 2 branches; T-2.6 extends 3 more inline; T-2.10 polish-only) makes every task green-ship-standalone. **R1 M#2 second-highest-value catch**: POST-service `ValueError` was uniformly mapped to 400 + re-render — but the race case (operator A submits while CLI resolves the same discrepancy) would have looped through a builder with `resolution='pending_ambiguity_resolution'` precondition + cascaded an internal-error response; branch 14 split into 14a (400 if re-read confirms pending) + 14b (409 if re-read shows terminal state). Single-sub-bundle decomposition LOCKED: 11 tasks T-2.1..T-2.11; **12 pre-baked operator-locks** (4 spec §2 + 8 §16) verbatim-encoded at §D; **21 binding invariants F1-F21** at §F; **18 dispatch-supplied lessons forward-binding** for executing-plans (8 inherited from brainstorm + 5 NEW writing-plans-surfaced L-W1..L-W5 + 5 prior project-cumulative invariants). Backfill / route ordering issues resolved (T-2.5 stubs + T-2.6 extends + T-2.10 polish; same-commit-as-route template branches). **Schema v19 UNCHANGED** (verified §F1 + plan §J banks only text-level §VII.F amendments). Net projection: **~+81 fast tests + 1 slow E2E + ~+970 production LOC** (above spec §12 upper band of 75; matches Phase 9/10/12 overshoot precedent). 13 V2 candidates banked verbatim from spec §15; 3 V2.1 §VII.F amendments banked at §J (J1 builder kwarg + J2 ValueError split + J3 parametric valid_choices). **Executing-plans dispatch UNBLOCKED.**
```

---

## §10 Schema impact verdict

**Schema v19 UNCHANGED end-to-end.** Plan §F invariant F1 LOCK preserved. `reconciliation_corrections` has NO `surface` column (verified at brainstorm via direct read of migration 0019); surface attribution achieved via existing free-TEXT `reconciliation_discrepancies.resolved_by` column with NEW value `'operator_web'` (no schema CHECK widening; no Python constant; no dataclass validator). ZERO migration work. `EXPECTED_SCHEMA_VERSION` stays at 19. Plan-author schema escalation rule (F20) NOT triggered.

---

## §11 Composition-surface verification

Plan §C canonical roster covers all touched surfaces. New `def`-level public functions planned (not yet implemented; executing-plans dispatch will land them):

**`swing/web/view_models/reconcile.py` (NEW):**
- `_parse_parametric_pick_count(resolution_reason: str | None) -> int` (private; T-2.1)
- `build_reconcile_discrepancy_resolve_vm(conn, discrepancy_id, *, prior_*, error_band_*) -> ReconcileDiscrepancyResolveVM` (public; T-2.3)
- `_render_pre_resolution_context(disc) -> ReconcilePreResolutionContext` (private dispatch; T-2.2)
- 10 private `_render_pre_resolution_context_<discrepancy_type>` helpers (T-2.2)
- Generic fallback `_render_pre_resolution_context_generic` (T-2.2)
- 4 frozen dataclasses: `ReconcileDiscrepancyResolveVM` (18 fields), `ReconcilePreResolutionContext` (14 fields), `ReconcileChoiceFormItem` (6 fields), `ReconcileDiscrepancyErrorVM` (T-2.5)

**`swing/web/routes/reconcile.py` (NEW):**
- `reconcile_discrepancy_resolve_form(request, discrepancy_id) -> Response` (GET; T-2.5)
- `reconcile_discrepancy_resolve_post(request, discrepancy_id) -> Response` (POST; T-2.6)

**`swing/metrics/discrepancies.py` (MOD):**
- `list_pending_ambiguities_in_banner_set(conn) -> list[ReconciliationDiscrepancy]` (public; T-2.9)
- `fetch_first_pending_ambiguity_resolve_link_path(conn) -> str | None` (public; T-2.9)

**`swing/web/view_models/metrics/shared.py:BaseLayoutVM` (MOD):**
- NEW field `banner_resolve_link: str | None = None` (T-2.7)

**`swing/web/templates/`** — 2 new templates (resolve form + error template) + 1 modified template (base.html.j2 banner-link integration).

**13 base-layout VMs across 9 files** gain `banner_resolve_link` field per T-2.7 Pass A grep retrofit.

**21 call sites across 12 files** thread `banner_resolve_link` into VM constructors per T-2.9 Pass B grep retrofit.

Composition-surface scope verified at plan-drafting via Pass A grep (14 declaration sites; 1 inherit + 13 standalone) + Pass B grep (21 call sites). Executing-plans implementer re-audits at task start per plan §A T-2.7 + T-2.9 acceptance.

---

## §12 Worktree teardown status

Worktree at `.worktrees/phase12-5-bundle-2-web-tier2-writing-plans/` retained pending operator post-merge cleanup pass.

Branch name `phase12-5-bundle-2-web-tier2-writing-plans` matches the cleanup-script regex `phase\d+[-_]` per the post-Phase-10 infra-bundle T-2 cleanup-script `-DeregisterFirst` pass. Husk teardown ACL-locked per existing project precedent; will be cleared on the next operator-paired `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` invocation.

Subagent-active marker `c:\Users\rwsmy\swing-trading\.copowers-subagent-active` to be removed by this writing-plans return-report step.

---

## §13 (BONUS) Executing-plans dispatch UNBLOCKED checklist

- [x] Plan committed at branch HEAD `3079154` (5 substantive Codex rounds + 1 R5 confirmation; NO_NEW_CRITICAL_MAJOR sealed).
- [x] 12 operator-locks verbatim-encoded (§D).
- [x] 21 invariants F1-F21 (§F).
- [x] 3 V2.1 §VII.F amendments banked (§J).
- [x] 13 V2 candidates mirrored (§Z).
- [x] 6-surface operator-witnessed gate plan (§H).
- [x] Pass A grep (14 sites) + Pass B grep (21 sites) verified (§C.4 + §C.5).
- [x] Return report drafted (this file).
- [ ] Operator review.
- [ ] Operator-decided: dispatch executing-plans phase OR pause.
- [ ] If dispatch: orchestrator constructs executing-plans dispatch brief per plan §L skeleton + supplies the 18-lesson forward-binding catalog (§M).

**Operator decides whether to dispatch executing-plans phase AFTER operator-witnessed plan review.**

---

*End of return report. Phase 12.5 #2 writing-plans dispatch CLOSED. Branch `phase12-5-bundle-2-web-tier2-writing-plans` ready for operator-paired integration merge.*
