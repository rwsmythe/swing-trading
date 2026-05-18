# Phase 12.5 #2 Web Tier-2 Discrepancy-Resolution — Brainstorm Return Report

**Audience:** Orchestrator (fresh Claude Code instance receiving the worktree handoff).
**Author:** Phase 12.5 #2 brainstorm implementer subagent.
**Date:** 2026-05-18.
**Brief:** `docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-brainstorm-dispatch-brief.md` (commit `d642175`).
**Spec doc:** `docs/superpowers/specs/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-design.md` (commit `a166eea`).

---

## §1 Final HEAD on branch + commit count breakdown

**Branch:** `phase12-5-bundle-2-web-tier2-brainstorm` (worktree at `.worktrees/phase12-5-bundle-2-web-tier2-brainstorm/`).
**HEAD:** `a166eea29e76e9a4223febf3494a73b9d4ad4874`.
**Base commit (origin/main at fork):** `d642175` (brief).

**Commit count: 2 on top of base.**

| SHA | Type | Subject (1-line) |
|-----|------|------------------|
| `119141a` | spec-draft | initial 16-section spec; 4 operator pre-locks baked verbatim; 679 lines; pre-Codex review caught 3 issues all resolved inline (BaseLayoutVM banner_resolve_link inheritance; hidden-anchor TOCTOU; CLI helper-extraction scope-creep) |
| `a166eea` | spec-codex-fix | R1-R6 amendments; 6 Codex rounds NO_NEW_CRITICAL_MAJOR; +73 / -31 lines net; final 721 lines |

**Co-Authored-By footer drift:** ZERO across both commits. Project-cumulative streak ~135+ preserved.

---

## §2 Codex round chain (R1-R6 summary table + convergent shape; finding-count taper)

| Round | Critical | Major | Minor | Verdict | Notes |
|-------|----------|-------|-------|---------|-------|
| R1 | 0 | 5 | 3 | ISSUES_FOUND | Foundational pass; surfaced hidden-anchor-vs-audit-fields contradiction (M1) + 303-fallback-under-strict-mode (M2) + banner-selector-vs-count-set (M3) + literal-naming-of-surface-attribution (M4 — ACCEPTED with rationale) + parametric-choice-validation underspecification (M5) |
| R2 | 0 | 3 | 2 | ISSUES_FOUND | CLI/web byte-identical correction test unimplementable (M1) + banner_resolve_link dashboard-only-vs-shared-banner (M2) + §11.6 walkthrough contradicts §4.2 (M3) |
| R3 | 0 | 3 | 2 | ISSUES_FOUND | BaseLayoutVM-inheritance assumption wrong (M1; 13 legacy VMs carry standalone fields per `swing/web/view_models/schwab.py:29-33` precedent) + 13-surfaces inventory undercount (M2) + GET route conn.close() implicit (M3) |
| R4 | 0 | 1 | 3 | ISSUES_FOUND | Broad grep matches comments+tests+templates (M1) — split into Pass A (field-decl regex) + Pass B (call-site regex) |
| R5 | 0 | 1 | 2 | ISSUES_FOUND | Retrofit test plan only verifies new VM not legacy retrofitted VMs (M1) — added introspection test enumerating Pass A VMs |
| R6 | 0 | 0 | 2 | **NO_NEW_CRITICAL_MAJOR** | Convergence; both Minors are advisory historical-attribution prose; accepted |

**Convergent shape:** monotonic Major taper 5 → 3 → 3 → 1 → 1 → 0. ZERO Critical findings entire chain. R6 invoked under operator-override past default MAX_ROUNDS=5 (Phase 12.5 #1 brainstorm 7-round + Phase 10 writing-plans 6-round precedent for clean-shape overrides).

**Cumulative finding disposition:**
- 14 Major findings raised across R1-R5: 13 resolved with code-content fixes + 1 ACCEPT-WITH-RATIONALE (R1 M#4 surface attribution literal naming).
- 14 Minor findings raised across R1-R6: 12 resolved with code-content fixes + 2 advisory (R6 m1+m2).
- 0 Critical findings entire chain.

---

## §3 Spec line count

**Final: 721 lines.**

Brief target was ~500-800. Started at 679 lines pre-Codex; R1-R6 amendments added net +42 lines (mostly §3 retrofit pattern expansion + §13.3 test-pattern row additions + §4.2 step-3 branch enumeration). Within target.

Section breakdown (per spec):
- §0 Glossary (~10 lines)
- §1 Architecture overview (~10 lines)
- §2 4 pre-locked operator decisions (~22 lines including R1 M#4 rationale addendum)
- §3 Module touch list (~20 lines after Pass A/B expansion)
- §4 Route handler design (~70 lines including GET + POST + try/finally + 7-step branch enumeration)
- §5 VM design + builder function (~85 lines)
- §6 Template design (~125 lines including Jinja sketch + field-discipline contract)
- §7 Per-discrepancy-type render helpers (~35 lines)
- §8 Error handling + edge cases (~45 lines including 14-row error catalog)
- §9 Surface attribution (~30 lines including validate_override_combo interaction)
- §10 Banner + dashboard entry-point integration (~40 lines)
- §11 13 discriminating-example walkthroughs (~50 lines)
- §12 Sub-bundle decomposition (~25 lines; 11-task table)
- §13 Test fixture strategy (~35 lines including 9-row test pattern table)
- §14 Schema impact analysis (~25 lines)
- §15 13 V2 candidates banked (~30 lines)
- §16 8 operator decision items pending (~25 lines)
- §17 6-surface operator-witnessed gate plan (~15 lines)

---

## §4 Pre-locked operator decisions verbatim verification

All 4 brief §1 operator-pre-locks preserved verbatim in spec §2.1-§2.4:

| Lock | Spec section | Verbatim binding | Status |
|------|--------------|------------------|--------|
| D1: Dedicated form page `/reconcile/discrepancy/{id}/resolve` | §2.1 | "NOT inline HTMX swap. NOT 2-step list-page → form." | ✅ Verbatim |
| D2: HX-Redirect to `/dashboard` on success | §2.2 | "NOT 'stay on form with success banner'. NOT HX-Redirect to /reconcile/correction/{id}/show." | ✅ Verbatim |
| D3: Keep CLI + web; surface distinguishable in audit | §2.3 | CLI keeps AS-IS (no deprecation); web stamps `resolved_by_override='operator_web'`; distinguishability via `resolved_by IN ('operator', 'operator_web')` | ✅ Verbatim with R1 M#4 ACCEPT-WITH-RATIONALE addendum |
| D4: Pre-resolution context section ABOVE choice menu | §2.4 | "NOT minimal-form (no pre-context section). NOT full audit chain link to /reconcile/correction/{id}/show." | ✅ Verbatim |

**No re-litigation across 6 Codex rounds.** Codex never challenged a pre-lock; all challenges were on derivative architecture (which Codex correctly attacked).

---

## §5 §3 Open Questions: surfaced / resolved / deferred-to-operator

| # | Brief §3 OQ | Disposition | Spec section |
|---|------|-------------|--------------|
| 1 | Banner navigation target (first / list / docs) | RECOMMENDED first-pending | §10.1 + §16.1 |
| 2 | Dashboard per-discrepancy entry-point | RECOMMENDED NOT in V1; banked V2 §15.5 | §10.2 + §16.3 |
| 3 | HX-Redirect query-string success token | RECOMMENDED include `?reconcile_resolved={id}`; V1 dashboard non-consumer | §10.3 + §16.4 |
| 4 | HX-Redirect alternate target | RECOMMENDED uniform `/dashboard`; per-type banked V2 §15.9 | §10.4 + §16.5 |
| 5 | `surface='web'` schema CHECK widening | **CORRECTED CONJECTURE** — schema v19 UNCHANGED; `reconciliation_corrections` has NO `surface` column; attribution via `resolved_by` free-TEXT | §9 + §14 |
| 6 | Per-discrepancy-type context-render helpers | 11 concrete renderers + generic fallback | §7 |
| 7 | JS for conditional custom-value | RECOMMENDED 12-line inline `<script>`; server enforces requirement | §6 + §16.6 |
| 8 | Validation 400 re-render shape | RECOMMENDED preserve filled values via `prior_*` VM fields + `error_band_field_hint` | §5.1 + §8.3 |
| 9 | Test fixture strategy | RECOMMENDED pure TestClient + DB seeding (no Schwab cassettes) | §13 |
| 10 | Operator-witnessed gate surface count | RECOMMENDED 6 surfaces (S1 inline + S2 banner-nav + S3 form-render + S4 POST + S5 banner-clears + S6 CLI/web parity) | §16.8 + §17 |

**8 operator-decision items pending in §16** for orchestrator triage post-merge — all carry brainstorm-recommended defaults; operator may countermand without re-brainstorm.

---

## §6 Codex Major findings ACCEPTED with rationale

**1 finding, single ACCEPT:**

- **R1 M#4 — surface attribution literal naming.** Codex argued brief §1.3 wording "surface='cli' vs 'web'" implied those literals appear in a column. Disposition: brief author's phrasing is **meta-prose describing distinguishability**, NOT a schema constraint. The shipped distinguishability uses `resolved_by IN ('operator', 'operator_web')` (CLI keeps pre-existing `'operator'` default per brief §4 OUT-OF-SCOPE preservation lock on CLI surface; web stamps `'operator_web'`). Renaming CLI default to `'cli'` would be a behavioral change to a non-touched surface. V2 candidate §15.10 banks a possible explicit `surface` column on `reconciliation_corrections` if operator wants stricter naming.

**Pattern check vs precedent:** Phase 12.5 #1 brainstorm banked 0 ACCEPTs. Phase 12 Sub-bundle C.A banked 1 ACCEPT. Phase 9 Sub-bundle A banked 2 ACCEPTs. Phase 12.5 #2 banking 1 is mid-range — distinguished by the ACCEPT being purely meta-prose-vs-literal-interpretation (no engineering compromise).

---

## §7 Cumulative V2 candidates banked

13 V2 candidates in spec §15:

1. `/reconcile/correction/{id}/show` audit-chain page (HX-Redirect target candidate).
2. One-time success toast renderer on `/dashboard?reconcile_resolved={id}`.
3. Web Tier-3 override surface.
4. Web Tier-1 auto-correct undo surface.
5. `/reconcile/pending` list page (multi-row enumerator).
6. `reconcile_resolved` toast renderer (V2 dashboard consumer of #5's query param).
7. Pipeline-active exclusion on web Tier-2 path (mirrors `SchwabPipelineActiveError`).
8. `schwab_api_call_id` form input on web (operator-supplied back-link).
9. Per-discrepancy-type HX-Redirect targets (`/metrics/capital-friction` post-snapshot, `/trades/{id}` post-fill, etc.).
10. Explicit `surface` column on `reconciliation_corrections` (v19 → v20 migration).
11. Inline HTMX swap UX (operator §1.1 LOCK rejection candidate — banked for future reconsideration).
12. Centralized JS for conditional custom-value input (`static/reconcile.js`).
13. DRY `parse_parametric_pick_count` helper consolidation (move from web VM to `swing/trades/reconciliation_ambiguity_choices.py` + CLI refactor + behavioral-equivalence regression preserved).

**None require V2.1 §VII.F amendment** (no methodology-reference correction; no doctrine drift).

---

## §8 Forward-binding lessons for writing-plans dispatch

1. **Brief-conjecture-vs-actual-schema gap.** Brief §2.7 conjectured `surface='web'` CHECK widening for `reconciliation_corrections`; the table has NO `surface` column. Writing-plans phase MUST `grep -n` the actual migration files for any column the brief references — do NOT trust brief language about schema constraints without grep verification. Phase 12 Sub-bundle C.A precedent (column-count drift in spec §3.1) is a sibling lesson.

2. **BaseLayoutVM-inheritance assumption is wrong for legacy VMs.** Phase 10 introduced `BaseLayoutVM` as a mixin for the NEW metrics-page family; the existing 13 base-layout VMs (DashboardVM / PipelineVM / JournalVM / SchwabSetupVM / etc.) carry the base-layout fields as STANDALONE dataclass fields per the "Local minimal base-layout fields" pattern documented at `swing/web/view_models/schwab.py:29-33`. Any retrofit that adds a base-layout field MUST touch BOTH BaseLayoutVM AND each non-inheriting VM individually. Codex R3 M#1 catch.

3. **Form-render hidden anchors are distinct from hidden audit fields.** Phase 8 R2.M2 + R3.M2 + R4.M2 introduced the "default to server-stamping at handler entry; remove hidden audit fields" rule. Phase 9 D R2/R3 introduced the "form-render-emitted hidden anchor for TOCTOU defense" rule. The two rules SHARE the technical pattern (`<input type="hidden">`) but apply to ORTHOGONAL field categories (audit metadata vs state anchors). Future plans MUST distinguish them or operator-facing review will mark a true state-anchor as a Phase-8-gotcha-violation. Codex R1 M#1 catch.

4. **OriginGuard strict vs non-strict mode shapes the 303-fallback branch.** Strict mode (production deployment per `swing/web/app.py` convention) rejects non-HX-Request POSTs with 403 BEFORE the handler runs; the 303 branch is unreachable under strict mode but IS reachable under non-strict mode via same-Origin/Referer headers. Sub-bundle B `/schwab/setup:451` keeps the 303 branch for parity; Phase 12.5 #2 mirrors that byte-for-byte. Future plans MUST NOT delete the 303 fallback as "unreachable" — it is reachable in non-strict mode. Codex R1 M#2 catch.

5. **Banner-link target MUST be derived from the banner-count set.** Phase 10 + Phase 12 Sub-bundle C.D banner predicates use `count_unresolved_material` which JOINs through trade-state (active + closed-canonical only; excludes orphan-trade-id rows). A naive `WHERE resolution = 'pending_ambiguity_resolution'` query is a STRICT SUPERSET and would point the banner link to a discrepancy NOT in the displayed count. Future plans that derive navigation targets from filtered subsets MUST verify against the existing canonical helper before introducing a new query. Codex R2 M#3 catch.

6. **Test-pattern: byte-identical row comparison is unimplementable; use semantic-shape projection.** Identity / time / source-row fields ALWAYS differ between two independent resolutions. Tests asserting "row equality modulo column X" must explicitly project to a normalized comparison shape excluding `correction_id` / `discrepancy_id` / `affected_row_id` / `applied_at` / `correction_set_id` / `reconciliation_run_id` / `schwab_api_call_id` / `superseded_by_correction_id`. Future audit-row-parity tests across surfaces MUST adopt this pattern. Codex R2 M#1 catch.

7. **Grep-driven audits split by intent.** Codex R3-R4 caught that a single broad `grep` matches comments + tests + template reads; the implementer's correct audit is TWO PASSES: (Pass A) field declarations via `field: type = default` pattern; (Pass B) call-site population via `function_name(` pattern. Each pass has a distinct retrofit action. Future plans that say "audit all X sites" MUST specify the grep pattern + the action per match.

8. **Retrofit completeness audit is a discriminating test, not a checklist.** Future regressions land when a new VM is added without retrofitting. T-2.8's grep-at-test-time pattern (assert every VM with `unresolved_material_discrepancies_count` also has `banner_resolve_link`) is the canonical cross-bundle pin technique. Future plans MUST add similar audit tests when a retrofit spans multiple files. Codex R5 M#1 catch.

---

## §9 CLAUDE.md status-line refresh draft text

Append at end of the Phase 12.5 #1 status-line block:

```
**Phase 12.5 #2 brainstorm SHIPPED 2026-05-18** at `a166eea` (worktree branch
`phase12-5-bundle-2-web-tier2-brainstorm`; 2 implementer commits = 1 draft +
1 R1-R6 amendments; **6 Codex rounds → NO_NEW_CRITICAL_MAJOR** convergent
monotonic-Major taper (R1 0C/5M/3m → R2 0C/3M/2m → R3 0C/3M/2m → R4 0C/1M/3m
→ R5 0C/1M/2m → R6 0C/0M/2m); **ZERO Critical findings entire chain**; **1
ACCEPT-WITH-RATIONALE banked** (R1 M#4 surface attribution literal naming —
brief §1.3 "surface='cli' vs 'web'" wording is meta-prose; CLI keeps pre-
existing `'operator'` default per brief §4 OUT-OF-SCOPE preservation lock;
web stamps `'operator_web'`; distinguishability via `resolved_by IN
('operator', 'operator_web')`); ZERO Co-Authored-By footer drift across 2
commits (~137+ project-cumulative streak preserved); 721-line spec at
`docs/superpowers/specs/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-
resolution-design.md` (within 500-800 brief target). **Schema v19 UNCHANGED**
— §14 corrects brief §2.7 conjecture that `reconciliation_corrections`
needed `surface` CHECK widening; the table has NO `surface` column; surface
attribution achieved via existing `resolved_by_override='operator_web'`
kwarg on `apply_tier2_resolution` (free-TEXT column; no CHECK constraint).
**4 operator pre-locks** baked verbatim (§2.1-§2.4): dedicated form page
`GET/POST /reconcile/discrepancy/{id}/resolve`; HX-Redirect to `/dashboard`
on success with `?reconcile_resolved={correction_id}` query token; CLI
preservation AS-IS with distinguishable `resolved_by` attribution; pre-
resolution context section ABOVE choice menu mirroring CLI
`show-ambiguity` UX 1:1. **Hidden state anchor pattern** added per Phase 9
D R2/R3 TOCTOU-defense gotcha — `ambiguity_kind_at_render` hidden form
input validates against current `disc.ambiguity_kind` at POST time.
**Banner-link retrofit across ALL grep-audited base-layout surfaces** —
new helper `fetch_first_pending_ambiguity_resolve_link_path` populated at
every existing `count_unresolved_material` callsite (13 surfaces baseline;
grep at task time drives actual count). **13 V2 candidates banked at §15**
(audit-chain show page; toast renderer; web Tier-3 override; web Tier-1
undo; `/reconcile/pending` list page; pipeline-active exclusion; explicit
`surface` column V2 migration; etc.). **8 operator-decision items pending
at §16** for orchestrator triage post-merge (all carry brainstorm-
recommended defaults). **8 forward-binding lessons** for writing-plans
(brief-conjecture-vs-schema gap; BaseLayoutVM inheritance asymmetry; hidden
state anchor vs hidden audit fields; OriginGuard strict-vs-non-strict 303
fallback; banner-link from canonical count helper; semantic-shape vs byte-
identical row comparison; grep-driven audit split-by-intent; retrofit
completeness audit pattern). Single sub-bundle recommended (11 tasks; ~+45-
75 fast tests + 1 slow E2E projected; 3-5 Codex rounds expected for
executing-plans). **Writing-plans dispatch UNBLOCKED.**
```

---

## §10 Sub-bundle decomposition recommendation

**Recommended: SINGLE sub-bundle.**

Justification (per spec §12):
- Scope ≈ 11 tasks (T-2.1 through T-2.11).
- ~+45-75 fast tests projected (within Phase 9/10/12 sub-bundle precedent).
- 1 slow E2E test (T-2.10).
- No schema migration (Codex-verified §14).
- No cross-bundle dependencies (consumer-side of Sub-bundle C.A-D + Phase 12.5 #1; all upstream surfaces shipped).
- Service-layer `apply_tier2_resolution` UNCHANGED (web passes `resolved_by_override='operator_web'` through existing kwarg).
- Single dispatch keeps the retrofit-discipline atomic across BaseLayoutVM + 13 standalone VMs + base.html.j2 template + all banner-populating routes — splitting introduces cross-bundle pins for no gain.

Alternative decomposition considered + rejected:
- 12.5-2A (core route + VM + template + service consumer) + 12.5-2B (banner_resolve_link retrofit + dashboard polish) — rejected because the retrofit-completeness audit (T-2.8) is a single discriminating test; splitting forces an inter-bundle skip-then-unskip pattern that adds complexity without scope-isolation benefit.

**Writing-plans expected duration: ~3-5 Codex rounds + ~90-150 min spec→plan elaboration.**

**Executing-plans expected duration: ~6-10 hours operator-paced + 3-5 Codex rounds.**

---

## §11 Schema impact verdict (v19 unchanged OR v20 migration required + rationale)

**Schema v19 UNCHANGED.**

**Rationale (per spec §14):** the dispatch brief §2.7 conjectured `reconciliation_corrections.surface` CHECK widening (mirroring Sub-bundle B's banked V2 candidate). Verification at brainstorm time (read of `swing/data/migrations/0019_phase12_bundle_c_auto_correct_reconciliation.sql:39-70`) confirms `reconciliation_corrections` has NO `surface` column. The column-set is: `correction_id`, `discrepancy_id`, `correction_action`, `correction_choice`, `affected_table`, `affected_row_id`, `field_name`, `pre_correction_value_json`, `source_canonical_value_json`, `applied_value_json`, `operator_truth_value_json`, `applied_at`, `applied_by`, `correction_set_id`, `superseded_by_correction_id`, `risk_policy_id_at_correction`, `schwab_api_call_id`, `reconciliation_run_id`, `correction_reason`, `notes`. No surface attribution column.

The brief author's "`surface='cli'` vs `'web'`" wording is meta-prose describing distinguishability requirements; the actual shipped distinguishability uses `reconciliation_discrepancies.resolved_by` (free TEXT; no CHECK constraint). Web stamps `'operator_web'` via existing `resolved_by_override` kwarg; CLI keeps default `'operator'`. **ZERO schema work.** ZERO new `_SURFACE_VALUES` constant. ZERO new dataclass validator. ZERO new migration.

V2 candidate §15.10 banks an explicit `surface` column on `reconciliation_corrections` (v19 → v20) if operator wants stricter naming; deferred V1.

The schema-CHECK + Python-constant + dataclass-validator paired discipline gotcha (CLAUDE.md) does NOT apply because nothing widens.

`schwab_api_calls.surface` CHECK (`('pipeline', 'cli')`) is UNAFFECTED — web Tier-2 form does NOT call Schwab API.

---

## §12 Composition-surface verification

The spec covers all consumed surfaces:

| Surface | Verified | Spec section |
|---------|----------|--------------|
| Service `apply_tier2_resolution(conn, *, discrepancy_id, choice_code, operator_custom_payload, operator_reason, ...)` signature | Read `swing/trades/reconciliation_auto_correct.py:328-390` | §4.2 step 4 |
| `_validate_override_combo` invariants (auto_applied XOR auto_correction_action; auto_resolved_by requires pair; triple only valid under split_into_partials) | Read `swing/trades/reconciliation_auto_correct.py:_validate_override_combo` | §9.2 (verified `resolved_by_override='operator_web'` passes — none of 3 invariants fire) |
| Exceptions: `CallerHeldTransactionError`, `ValidatorRejectedError`, `AlreadySupersededError`, `InvalidOverrideComboError` | Read `swing/trades/reconciliation_auto_correct.py` exception classes | §8.1 catch-ladder |
| `get_choice_menu(ambiguity_kind)` → `list[ChoiceMenuItem]` PURE | Read `swing/trades/reconciliation_ambiguity_choices.py:254-268` | §5.3 + §7 |
| `ChoiceMenuItem` fields: `code`, `description`, `requires_custom_value`, `recommended`, `expected_payload_shape_description` | Read same file | §5.3 |
| CLI `show-ambiguity` + `resolve-ambiguity` UX | Read `swing/cli.py:2222-2549` | §4 + §6 mirror 1:1 |
| Sub-bundle B `/schwab/setup` HTMX + HX-Redirect + try/finally + apply_overrides + base-layout VM banner pin patterns | Read `swing/web/routes/schwab.py:218-451` | §4.1 + §4.2 mirror byte-for-byte |
| BaseLayoutVM 7-field contract | Read `swing/web/view_models/metrics/shared.py:28-71` | §0 + §5.1 |
| BaseLayoutVM-inheritance asymmetry (legacy VMs carry standalone fields) | Grep confirmed across DashboardVM / PipelineVM / JournalVM / SchwabSetupVM | §3 |
| `count_unresolved_material(conn)` JOINs through trade-state (active + closed-non-terminal) | Read `swing/metrics/discrepancies.py:38-48` | §10.1 + §3 helper retrofit |
| Schema v19 `reconciliation_corrections` 20-column LOCK | Read `swing/data/migrations/0019_phase12_bundle_c_auto_correct_reconciliation.sql:39-70` | §14 |
| `schwab_api_calls.surface` CHECK enum `('pipeline', 'cli')` | Read `swing/data/migrations/0018_schwab_integration.sql:32` | §14.2 (UNAFFECTED) |
| OriginGuard strict vs non-strict modes | Read `swing/web/middleware/origin_guard.py:21-59` | §4.2 step 6 + §11.10 |
| CLAUDE.md gotcha family (HTMX, ASCII-only, ... or None, with-conn, base-layout retrofit, hidden anchor TOCTOU, SAVEPOINT) | Read CLAUDE.md Gotchas section | Cited throughout §4, §6, §8 |

---

## §13 Worktree teardown status

* **Branch:** `phase12-5-bundle-2-web-tier2-brainstorm` ALIVE on local worktree. NOT pushed to origin (brainstorm-only — orchestrator decides push timing).
* **Worktree directory:** `.worktrees/phase12-5-bundle-2-web-tier2-brainstorm/` PRESENT on disk. Matches cleanup-script regex `phase\d+[-_]` (operator-paired cleanup pass post-merge).
* **Marker file `c:/Users/rwsmy/swing-trading/.copowers-subagent-active`:** DELETED at end-of-dispatch (brief §3 setup requirement satisfied — verified absent via `ls -la` post-rm).
* **`/tmp/.copowers-session-12c79f8b1263.json`:** WRITTEN by adversarial-critic skill (1 review entry; verdict=`approved`; rounds=6; reviewed_at_commit=`a166eea`).
* **Return report:** at `docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-brainstorm-return-report.md` (this document) on branch HEAD (will be committed by orchestrator OR by next subagent on the same branch; not committed by THIS implementer to preserve the spec-only HEAD shape).

**Recommended orchestrator next actions:**

1. Review the spec (`docs/superpowers/specs/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-design.md`) at commit `a166eea`.
2. Review the 8 operator-decision items in §16 + 13 V2 candidates in §15.
3. Commit this return report on the branch (suggested message: `docs(phase12-5-2-web-tier2-spec): brainstorm return report — 6 Codex rounds NO_NEW_CRITICAL_MAJOR; 1 ACCEPT-WITH-RATIONALE banked; schema v19 UNCHANGED; writing-plans dispatch UNBLOCKED`).
4. Decide: merge to main directly (operator-witnessed gate is for executing-plans phase; brainstorm-merge is mechanical) OR consult operator first on §16 decision items.
5. Refresh `CLAUDE.md` status-line per §9 above.
6. Update `docs/phase3e-todo.md` Phase 12.5 RESCOPED entry to mark #2-brainstorm SHIPPED.
7. Update `docs/orchestrator-context.md` current-state pointer.
8. Dispatch writing-plans phase against the brainstorm-locked spec (anticipated 3-5 Codex rounds).
9. After writing-plans merge, dispatch executing-plans (anticipated 3-5 Codex rounds + 6-surface operator-witnessed gate).

**Phase 12.5 #2 writing-plans dispatch UNBLOCKED.**

---

*End of return report. Phase 12.5 #2 brainstorm CLOSED. 721-line spec at `docs/superpowers/specs/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-design.md` (HEAD `a166eea`). 4 operator pre-locks baked verbatim. 6 Codex rounds NO_NEW_CRITICAL_MAJOR. 1 ACCEPT-WITH-RATIONALE banked. Schema v19 UNCHANGED. 13 V2 candidates banked. 8 operator-decision items pending. 8 forward-binding lessons for writing-plans. ZERO Co-Authored-By footer drift.*
