# Phase 12.5 #2 — Web Tier-2 Discrepancy-Resolution Surface — Executing-plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Phase 12.5 #2 of the Schwab reconciliation V2 follow-up arc via `copowers:executing-plans`. Plan is `docs/superpowers/plans/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-plan.md` (1082 lines). All per-task acceptance criteria + tests + commit shapes are in the plan; this dispatch brief is a worktree-config + scope wrapper, NOT a duplicate spec.

**Expected duration:** ~6-10 hr implementation + ~2-4 hr Codex chain + 6-surface operator-witnessed gate. Total **~2-3 days operator-paced** (calibrated 3-5x per `feedback_time_estimates_overstated.md`). Phase 12.5 #2 ships the **web counterpart** to the existing `swing journal discrepancy show-ambiguity` + `resolve-ambiguity` CLI surface — dedicated `GET/POST /reconcile/discrepancy/{id}/resolve` form page with pre-resolution context section + choice-menu rendering + custom-value input + HX-Redirect to `/dashboard?reconcile_resolved={correction_id}` on success. CLI surface UNCHANGED. Schema v19 UNCHANGED.

**Skill posture:**
- Invoke `copowers:executing-plans` against the plan path (`PLAN_PATH=docs/superpowers/plans/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-plan.md`).
- The skill wraps `superpowers:subagent-driven-development` + adversarial Codex review.
- Adversarial review runs after all 11 tasks land. Expected **3-5 Codex rounds** (matches Phase 12 Sub-bundle C.C 3 rounds + Phase 12.5 #1 executing-plans 4 rounds + post-Phase-12 Sub-bundle 2 3 rounds for single-sub-bundle web-route scope). Rounds should compress because the plan absorbed 5 Codex rounds + 1 R5 confirmation + ZERO ACCEPT-WITH-RATIONALE + R1 M#1+M#2 architectural defects already addressed in-plan (stub-then-extend reorder + Branch 14a/14b race fix).

---

## §0 Inputs

### §0.1 Plan

- **PLAN_PATH:** `docs/superpowers/plans/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-plan.md` (1082 lines; 5 Codex rounds + R5 confirmation; ZERO ACCEPT-WITH-RATIONALE; ZERO Critical findings; LOCKED at `9220dac`; merged to main).
- **Plan §A** task decomposition: 11 tasks T-2.1..T-2.11. Self-contained per-task spec with TDD checkboxes.
- **Plan §C** canonical files-touched roster with grep anchors verified at plan-drafting time.
- **Plan §D** 12 LOCKed decisions verbatim (4 spec §2 operator-locks + 8 §16 ACCEPTED at brainstorm defaults).
- **Plan §F** 21 binding invariants F1-F21.
- **Plan §G** per-task acceptance-criteria narrative for tasks spanning multiple files/layers.
- **Plan §H** 6-surface operator-witnessed gate plan.
- **Plan §I** cross-bundle pins (consumer-side reads of SHIPPED Sub-bundle C.C+C.D + Phase 12.5 #1 + Sub-bundle B surfaces).
- **Plan §J** 3 V2.1 §VII.F amendment candidates banked (J1 builder kwarg + J2 ValueError 14a/14b split + J3 parametric valid_choices).
- **Plan §K** refined per-task LOC + test projection.
- **Plan §M** 13 forward-binding lessons (8 inherited from brainstorm + 5 NEW L-W1..L-W5).
- **Plan §Z** 13 V2 candidates banked from spec §15.

### §0.2 Spec

- **SPEC_PATH:** `docs/superpowers/specs/2026-05-18-phase12-5-bundle-2-web-tier2-discrepancy-resolution-design.md` (721 lines; 6 Codex rounds; 1 ACCEPT-WITH-RATIONALE banked R1 M#4; LOCKED at `ac6eb88`).
- **Read for §3 module touch list** (14 surfaces verified) + **§4 route handler design** (GET + POST) + **§5 VM design + builder** + **§6 template design** (context section + form section) + **§7 per-discrepancy-type context-render helpers** + **§8 error handling + edge cases** + **§9 surface attribution** (`'operator_web'` via free-TEXT `resolved_by`) + **§10 banner + dashboard entry-point integration** + **§11 discriminating-example walkthroughs**.
- **Plan SUPERSEDES SPEC** per L-W4 LOCK on conflicts surfaced during writing-plans Codex chain (R2 M#2 fix). Spec §J2 + §J3 banked as V2.1 §VII.F amendments — treat plan as binding.

### §0.3 Writing-plans return report

- **RETURN_REPORT_PATH:** `docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-writing-plans-return-report.md` (232 lines; commit `6c913ac`).
- **Read for §2** Codex chain (5 rounds + R5 confirmation; monotonic Major taper 3→2→1→0→0) + **§7** V2 candidates + **§8** forward-binding lessons (13 total = 8 inherited + 5 NEW L-W1..L-W5) + **§10** sub-bundle decomposition recommendation + **§12** Codex-chain insight summary (R1 M#1 task-ordering + R1 M#2 race + R2 M#2 spec-out-of-sync).

### §0.4 Project state at dispatch time

- **HEAD on `main`:** `<latest-after-orchestrator-commits>` (resolve via `git rev-parse main` at worktree-creation time after this brief lands). Brief commit lands at HEAD+1 pre-dispatch.
- **Test count:** **4712 fast passing on main** + 3 pre-existing failures (`tests/integration/test_phase8_pipeline_walkthrough.py` — unchanged since Phase 8; banked under Phase 12.5 #3 maintenance dispatch) + 5 skipped. Verified at brief drafting time.
- **Ruff baseline:** **18 E501 errors** unchanged across Phase 11 + Phase 12 + post-Phase-12 + Phase 12.5 #1 + Phase 12.5 #2 brainstorm + writing-plans chains. Plan MUST NOT introduce new E501.
- **Schema version:** **v19** (LOCKED since Phase 12 Sub-sub-bundle C.A; verified §13.1 + brainstorm §14 audit; F1 LOCK preserved through plan; F19 plan-author schema additions escalation rule was NOT triggered during writing-plans). **Phase 12.5 #2 MAY NOT widen schema** (plan §F F1 + escalation rule).
- **Production discrepancy state:** 2 NEW Pass-1 `unmatched_open_fill` discrepancies from Phase 12.5 #1 S3 (DHC #52 + VSAT #53) STILL pending operator dispositioning per C.D-gate-cleanup convention. These DO surface on `/dashboard` banner as "2 unresolved material" — useful S3 gate fixture for Phase 12.5 #2 (banner-link navigation pre-condition). Plus 4 additional Tier-2 pending from runs #67 + #68 (same DHC + VSAT family re-emerged). Total pending-ambiguity row count: **6**.
- **Production refresh-token clock:** expires ~2026-05-24T06:40:00+00:00. **Operator may need to re-auth before S3 production gate** if dispatch slips past expiry.
- **Production-write classifier soft-block awareness:** S4 (successful POST) + S5 (banner-clears) gate surfaces are production-writes against operator's REAL DB. Operator pre-authorizes via gate-path AskUserQuestion or plain-chat "yes" if Claude Code's production-write classifier soft-blocks. **DO NOT proceed without explicit operator authorization per-invocation** (per NEW C.D-arc lesson #2).
- **Worktree husks:** 5 pending operator's cleanup-script pass (`phase12-5-bundle-1-oqf-brainstorm` + `-writing-plans` + `-executing-plans` + `phase12-5-finviz-inbox-auto-fetch-fix` + `phase12-5-bundle-2-web-tier2-brainstorm` + post-merge a 6th `-writing-plans` worktree); NOT blocking executing-plans dispatch.

### §0.5 Phase 12.5 #2 scope (11 tasks per plan §A)

| Task | Title | Files (illustrative; plan §A locks) |
|---|---|---|
| **T-2.1** | `_parse_parametric_pick_count` helper in `swing/web/view_models/reconcile.py` (DUPLICATES CLI regex per §1.2 #7 LOCK) | NEW `swing/web/view_models/reconcile.py` + NEW test |
| **T-2.2** | `ReconcileDiscrepancyResolveVM` dataclass + per-discrepancy-type context render helpers | MODIFY `swing/web/view_models/reconcile.py` + NEW test |
| **T-2.3** | VM builder `build_reconcile_discrepancy_resolve_vm(conn, discrepancy_id)` | MODIFY `swing/web/view_models/reconcile.py` + NEW test |
| **T-2.4** | NEW `reconcile_discrepancy_resolve.html.j2` template (context + form + 12-line inline `<script>`; ASCII-only) | NEW template + NEW test |
| **T-2.5** | `GET /reconcile/discrepancy/{id}/resolve` route handler + **stub 2 error-template branches** per R1 M#1 stub-then-extend reorder | NEW `swing/web/routes/reconcile.py` + 2 error templates + NEW test |
| **T-2.6** | `POST /reconcile/discrepancy/{id}/resolve` route handler + **extend 3 more error-template branches inline** per R1 M#1 + **Branch 14 split into 14a (400) + 14b (409)** per R1 M#2 race fix | MODIFY `swing/web/routes/reconcile.py` + 3 more error templates + NEW test (incl. concurrent-resolve race regression test) |
| **T-2.7** | `BaseLayoutVM.banner_resolve_link: str \| None = None` field addition + retrofit across 13 standalone-field VMs + 21 callsite Pass B populations | MODIFY `swing/web/view_models/metrics/shared.py:BaseLayoutVM` + 13 standalone VMs + 21 builder/route callsites |
| **T-2.8** | Banner template + helper integration in `base.html.j2` + **retrofit completeness audit** (discriminating test runs Pass A grep at test time per R5 LOCK) | MODIFY `swing/web/templates/base.html.j2` + NEW test |
| **T-2.9** | Banner first-pending helper `select_first_pending_ambiguity_discrepancy_id(conn) -> int \| None` (ORDER BY ASC per §1.2 #6 LOCK; reuses `count_unresolved_material`'s active+closed trade-set per R1 LOCK) | MODIFY `swing/web/view_models/reconcile.py` + NEW test |
| **T-2.10** | Polish-only — error-path template polish + accessibility + minor cleanups (T-2.5/T-2.6 already shipped error templates green per R1 M#1 reorder) | MODIFY 5 error templates + NEW test |
| **T-2.11** | E2E + integration tests (CLI/web parity test + happy path + error paths + slow E2E `test_phase12_5_bundle_2_web_tier2_happy_path.py`) | NEW integration test files |

**Dispatch order:** T-2.1 → T-2.2 → T-2.3 → T-2.4 → T-2.5 → T-2.6 → T-2.7 → T-2.8 → T-2.9 → T-2.10 → T-2.11. **CRITICAL ORDERING per R1 M#1 LOCK**: T-2.5 + T-2.6 ship green standalone (each task with its own error-template branches working end-to-end); T-2.10 polishes ALREADY-SHIPPED templates (NOT new template introduction). **DO NOT REORDER** without explicit acceptance-criteria adjustment.

**Cross-bundle dependencies:** Phase 12.5 #2 CONSUMES Sub-bundle C.A schema (v19; no new tables; existing `resolved_by` free-TEXT column accepts `'operator_web'`) + Sub-bundle C.B `ClassificationResult` (no new fields) + Sub-bundle C.C `apply_tier2_resolution` + `_apply_tier2_resolution_inner` + 12 `_handle_*` registry + `resolved_by_override` kwarg (existing; just consume with new value `'operator_web'`) + Sub-bundle C.D `swing journal discrepancy show-ambiguity` + `resolve-ambiguity` CLI commands (UNCHANGED; parity comparison fixture) + Phase 10 banner predicate widening + Phase 12.5 #1 `recent_multi_leg_auto_correction_count` (PRE-EXISTING base-layout pattern; plan extends with NEW `banner_resolve_link`) + Sub-bundle B `SchwabSetupVM` + `SchwabStatusVM` + `SchwabSetupErrorVM` base-layout retrofit (1:1 route format reference) + Sub-bundle B `apply_overrides(cfg)` discipline + Sub-bundle B HX-Headers + HX-Redirect + 204 + atomic-mutation pattern.

**Module boundaries (BINDING — preserve discipline per plan §C.3):**
- `swing/web/view_models/reconcile.py`: NEW module. `_parse_parametric_pick_count` helper (T-2.1) + `ReconcileDiscrepancyResolveVM` dataclass + per-type render helpers (T-2.2) + builder (T-2.3) + `select_first_pending_ambiguity_discrepancy_id` helper (T-2.9). Pure functions + dataclass + DB read helpers; NO writes; NO transaction management.
- `swing/web/routes/reconcile.py`: NEW module. GET handler (T-2.5) + POST handler (T-2.6). Owns route-level error handling; calls service-layer `apply_tier2_resolution`.
- `swing/web/templates/reconcile_discrepancy_resolve.html.j2`: NEW template (T-2.4) extending `base.html.j2`. Context section + form section + 12-line inline `<script>` for custom-value toggle.
- `swing/web/templates/reconcile_discrepancy_resolve_errors/*.html.j2`: NEW 5 error templates (T-2.5+T-2.6 ship green stubs; T-2.10 polishes).
- `swing/web/view_models/metrics/shared.py:BaseLayoutVM`: MODIFY — add `banner_resolve_link: str | None = None` field (T-2.7).
- 13 standalone-field VMs: MODIFY — add `banner_resolve_link: str | None = None` field per Pass A grep retrofit (T-2.7).
- 21 builder/route callsites: MODIFY — populate `banner_resolve_link` from `select_first_pending_ambiguity_discrepancy_id` per Pass B grep retrofit (T-2.7).
- `swing/web/templates/base.html.j2`: MODIFY — render `banner_resolve_link` when populated (T-2.8).
- Surfaces explicitly NOT touched (UNCHANGED LOCK per plan §C.3): `apply_tier2_resolution` service entry signature; CLI commands (`show-ambiguity` + `resolve-ambiguity`); classifier; multi-leg auto-redirect banner (Phase 12.5 #1); `/schwab/setup` + `/schwab/status` routes (Sub-bundle B); `_compute_execution_price` / `_resolve_match_quantity` / `_is_execution_bearing_candidate` (Sub-bundle 1); schema (v19 LOCKED).

### §0.6 BINDING contracts from plan §D (DO NOT re-litigate)

The 12 LOCKs at plan §D. Verbatim summary:

**4 operator-locks from spec §2.1-§2.4 (brainstorm pre-locks):**
1. **Dedicated form page** `GET/POST /reconcile/discrepancy/{id}/resolve`. NOT inline HTMX swap; NOT 2-step list-page.
2. **HX-Redirect to `/dashboard?reconcile_resolved={correction_id}`** on POST success. 204 + HX-Redirect header; NOT 303 swap-target.
3. **CLI preservation AS-IS**. `swing journal discrepancy show-ambiguity` + `resolve-ambiguity` UNCHANGED. Distinguishability via `resolved_by IN ('operator', 'operator_web')`.
4. **Pre-resolution context section** ABOVE choice menu. Per-discrepancy-type render helpers.

**8 §16 LOCKS accepted at brainstorm defaults (locked 2026-05-18 post-brainstorm-merge):**
5. **Banner navigation target** — link to FIRST pending-ambiguity discrepancy resolve form.
6. **First-pending selector ORDER BY** — `discrepancy_id ASC` (oldest first; diverges from CLI's DESC).
7. **Dashboard per-discrepancy list** — NOT in V1; banked V2.
8. **HX-Redirect query-string token** — include `?reconcile_resolved={correction_id}`.
9. **HX-Redirect alternate target** — uniform `/dashboard`; per-type targets banked V2.
10. **JS posture** — 12-line inline `<script>` for custom-value toggle; custom-value fieldset always rendered; server enforces requirement.
11. **`_parse_parametric_pick_count` helper location** — NEW private function in `swing/web/view_models/reconcile.py` DUPLICATES regex byte-for-byte from `cli.py:2291`; CLI body UNCHANGED.
12. **6-surface gate** — S1 inline pytest + ruff; S2 banner-link navigation; S3 form-render with context; S4 successful POST + HX-Redirect; S5 banner-clears post-resolve; S6 CLI/web parity end-to-end.

### §0.7 21 binding invariants F1-F21 (plan §F)

Encoded as project-wide CONTRACTS. Each invariant has a discriminating regression test pattern. Implementer MUST validate every task respects all 21.

**Schema + back-compat (F1-F6):** F1 ZERO new schema; F2 ZERO change to `apply_tier1_correction` external surface; F3 ZERO change to `apply_tier2_resolution` default behavior (legacy CLI back-compat); F4 ZERO change to determinism principle; F5 NO `Co-Authored-By` footer; F6 NO `--no-verify`.

**Spec §1.2 operator-locks (F7-F12):** F7 banner navigation = first-pending; F8 ORDER BY discrepancy_id ASC; F9 no V1 dashboard per-discrepancy list; F10 HX-Redirect query token included; F11 12-line inline JS; F12 CLI body UNCHANGED.

**Transactional + HTMX discipline (F13-F18):** F13 SAVEPOINT-per-discrepancy preserved at service layer; F14 service-layer `with conn:` owns transaction (POST handler does NOT); F15 HTMX trinity (HX-Headers propagation + 204+HX-Redirect not 303 + target route verified); F16 `... or None` for nullable text columns; F17 server-stamped `resolved_by='operator_web'` at handler entry (NOT operator-supplied); F18 hidden `ambiguity_kind_at_render` state anchor for TOCTOU defense.

**Retrofit + ASCII discipline (F19-F21):** F19 BaseLayoutVM-inheritance is asymmetric (13 standalone VMs need explicit retrofit; grep at test time pattern); F20 ASCII-only templates; F21 retrofit completeness is a discriminating test (Pass A grep + Pass B grep).

### §0.8 13 forward-binding lessons (plan §M)

**8 inherited from brainstorm return report §8:**
1. Brief-conjecture-vs-actual-schema gap → grep verify any column reference.
2. BaseLayoutVM-inheritance is asymmetric (13 existing VMs DO NOT inherit; carry standalone fields).
3. Hidden state anchors distinct from hidden audit fields (Phase 9 D vs Phase 8 gotcha families).
4. OriginGuard strict-vs-non-strict shapes 303-fallback reachability.
5. Banner-link targets MUST derive from canonical banner-count helper.
6. Audit-row parity tests use semantic-shape projection (excluding identity/time/source fields), not byte-identical comparison.
7. Grep-driven audits split by intent (Pass A field-declaration vs Pass B call-site).
8. Retrofit completeness is a discriminating test (grep at test time).

**5 NEW writing-plans-surfaced lessons L-W1..L-W5:**
- **L-W1** (R1 M#1): Stub-then-extend ordering for shared templates — when multiple tasks add branches to the same shared error-template surface, the FIRST task creates the template with stubs for its branches; LATER tasks extend the stub with their branches inline. Discriminating-test pattern: each task ships green standalone (test invokes the task's own branches; template doesn't error on stub-branch absence).
- **L-W2** (R1 M#2): Service `ValueError` requires re-read disambiguation in concurrent-write callers — when a service-layer raises `ValueError` for both "input invalid" AND "state changed under you" cases, the caller MUST re-read state from a fresh connection to disambiguate (400 if input invalid; 409 if state changed). Discriminating-test pattern: planted concurrent-resolve race with separate-connection + commit semantics; assert 409 (NOT 400) when state changed mid-request.
- **L-W3** (R3): F# cross-reference accuracy audit at sealing time — when plan-author cites invariants across sections (e.g., "per F11"), Codex chain MUST verify every cross-reference points to the correct F#. Discriminating-test pattern: plan-author runs grep audit on `F\d+` references + asserts every match points to a defined invariant at §F.
- **L-W4** (R2 M#2): Spec-out-of-sync requires explicit "Plan supersedes" notes + §J amendment banking — when plan diverges from spec during Codex chain (e.g., R1 fix changes a spec-locked surface), plan MUST explicitly say "Plan supersedes spec §X" + bank as V2.1 §VII.F amendment so executing-plans implementer treats plan as binding without spec rewrite.
- **L-W5** (R4): Late VM-validator additions risk breaking already-green callers — when a task introduces a new `__post_init__` validator on a VM, the validator MUST be additive (default-None-pass) OR the task MUST also update every existing caller. Discriminating-test pattern: late validator addition + run full test suite + assert ZERO regressions.

### §0.9 Test + LOC projection (plan §K)

Per plan §K:
- **~+81 fast tests** projected (+1 race regression from R1 M#2; was +80 pre-Codex).
- **1 slow E2E test** at `tests/integration/test_phase12_5_bundle_2_web_tier2_happy_path.py`.
- **~+970 production LOC + ~+1145 test LOC = ~+2115 total LOC**.

Final main HEAD post-Phase-12.5-#2-merge: **~4793 fast tests** (4712 baseline + ~81 new).

---

## §1 Worktree + binding conventions

### §1.1 Worktree

- **Branch:** `phase12-5-bundle-2-web-tier2-executing-plans`
- **Worktree directory:** `.worktrees/phase12-5-bundle-2-web-tier2-executing-plans/`
- **BASELINE_SHA:** current main HEAD (resolve via `git rev-parse main` at worktree-creation time after this brief lands; expected `9220dac` plus orchestrator housekeeping commits).
- **Branch naming:** matches cleanup-script `phase\d+[-_]` regex.

### §1.2 Marker-file workflow

- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all 11 tasks land + tests GREEN + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits

- Conventional prefixes per plan §A commit message stems:
  - `feat(web): _parse_parametric_pick_count helper (Phase 12.5 #2 T-2.1)`
  - `feat(web): ReconcileDiscrepancyResolveVM + per-type context helpers (Phase 12.5 #2 T-2.2)`
  - `feat(web): build_reconcile_discrepancy_resolve_vm builder (Phase 12.5 #2 T-2.3)`
  - `feat(web): reconcile_discrepancy_resolve.html.j2 template (Phase 12.5 #2 T-2.4)`
  - `feat(web): GET /reconcile/discrepancy/{id}/resolve route + 2 stub error templates (Phase 12.5 #2 T-2.5)`
  - `feat(web): POST /reconcile/discrepancy/{id}/resolve route + 3 inline error templates + Branch 14a/14b race fix (Phase 12.5 #2 T-2.6)`
  - `feat(web): BaseLayoutVM.banner_resolve_link + 13-VM Pass A retrofit + 21-callsite Pass B retrofit (Phase 12.5 #2 T-2.7)`
  - `feat(web): banner_resolve_link rendering in base.html.j2 + retrofit completeness audit (Phase 12.5 #2 T-2.8)`
  - `feat(web): select_first_pending_ambiguity_discrepancy_id helper (Phase 12.5 #2 T-2.9)`
  - `feat(web): error-template polish + accessibility (Phase 12.5 #2 T-2.10)`
  - `test(integration): Phase 12.5 #2 CLI/web parity + slow E2E happy path (Phase 12.5 #2 T-2.11)`
  - `fix(phase12-5-2): Codex RN <severity> #N — <description>` for Codex fixes
- **NO `Co-Authored-By` footer on ANY commit** (per F5; ~147+ cumulative ZERO drift streak preserved across Phase 11/12/post-Phase-12/Phase-12.5 chains). Subagent context starts isolated; the Bash tool's default footer template is NOT authoritative for this project — CLAUDE.md is. **DO NOT add `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>` (or any other Co-Authored-By footer attributing the AI assistant) to ANY commit message.** This dispatch MUST NOT regress.
- **NO `--no-verify`** (per F6); **NO `--amend`** (prefer `git add <specific-files>` over `git add -A`).
- **TDD:** failing test first, minimal implementation, pass, commit. Per-task `- [ ]` checkboxes in plan §A mark per-step boundaries.

### §1.4 Branch isolation + ownership

- Commits on branch only; no push to origin from worktree until Phase 12.5 #2 integration commit (post-Codex-convergence).
- **Implementer (you) owns:** task-family TDD commits → marker-file removal → pre-Codex orchestrator-style review (NEW C.C lesson #6) → adversarial-critic → return report at `docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-executing-plans-return-report.md`.
- **Operator owns:** witnessed verification gate (§3 surfaces below — 6 surfaces per plan §H).
- **Orchestrator owns:** integration merge to main + post-merge housekeeping + Phase 12.5 #3 dispatch commissioning.

### §1.5 Verify command

PowerShell from inside worktree:

```powershell
git log --oneline HEAD~20..HEAD
python -m pytest -m "not slow" -q -n auto
python -m pytest -m slow tests/integration/test_phase12_5_bundle_2_web_tier2_happy_path.py -v
ruff check swing/ --statistics
python -c "from swing.web.view_models.reconcile import _parse_parametric_pick_count, ReconcileDiscrepancyResolveVM, build_reconcile_discrepancy_resolve_vm, select_first_pending_ambiguity_discrepancy_id; print('reconcile module OK')"
python -c "from swing.web.routes.reconcile import resolve_get, resolve_post; print('reconcile routes OK')"
python -c "from swing.web.view_models.metrics.shared import BaseLayoutVM; import dataclasses; assert 'banner_resolve_link' in [f.name for f in dataclasses.fields(BaseLayoutVM)]; print('BaseLayoutVM.banner_resolve_link OK')"
python -m swing.cli journal discrepancy resolve-ambiguity --help  # CLI surface UNCHANGED check
```

**IMPORTANT — worktree CLI invocation discipline** (per `feedback_worktree_cli_invocation.md`): `swing` routes to editable-install path NOT worktree code. ALWAYS use `python -m swing.cli` from worktree cwd when verifying worktree-side CLI changes.

---

## §2 Adversarial review (Codex)

Invoked automatically by `copowers:executing-plans` after all 11 tasks land + tests GREEN + after the pre-Codex orchestrator-side review (NEW C.C lesson #6 — BINDING; absorbs LOCK divergences pre-Codex; saved findings on EVERY recent dispatch since C.C).

**Expected chain shape:** 3-5 substantive Codex rounds. Plan absorbed 5 rounds + 1 R5 confirmation + ZERO ACCEPT-WITH-RATIONALE + R1 M#1+M#2 architectural defects already addressed in-plan. Execution rounds should converge faster than writing-plans (matches Phase 12 C.C 5→3 round compression precedent).

**Adversarial review watch items (Phase 12.5 #2-specific):**

1. **F1 ZERO new schema LOCK** + **F19 plan-author schema additions escalation rule**. If Codex surfaces a need for schema element NOT in plan §A + spec §3, implementer MUST STOP + escalate to orchestrator BEFORE adding inline.
2. **F5 NO `Co-Authored-By` footer**. ~147+ cumulative ZERO drift across Phase 11/12/post-Phase-12/Phase-12.5 chains. Implementer MUST verify pre-merge that EVERY commit message lacks the footer.
3. **F12 CLI body UNCHANGED**. T-2.1 helper DUPLICATES regex byte-for-byte from `cli.py:2291`; CLI body NEVER modified. Discriminating test: byte-equivalence assertion across both code paths.
4. **F15 HTMX trinity** — `hx-headers='{"HX-Request": "true"}'` propagation; 204 + HX-Redirect (NOT 303); HX-Redirect target `/dashboard?reconcile_resolved=<id>` route-registered.
5. **F16 `... or None` for nullable text columns** — `resolution_reason` + `custom_value` form inputs feed nullable CHECK-constrained schema columns; use `... or None` NOT `... or ""`.
6. **F17 server-stamped `resolved_by='operator_web'`** — at handler entry, NOT operator-supplied via hidden form input. Discriminating test: tampered hidden-input `resolved_by` field MUST be IGNORED.
7. **F18 hidden state anchor `ambiguity_kind_at_render` for TOCTOU defense** (Phase 9 D R2 M#1 LOCK + spec §6 R1 LOCK). Discriminating test: simulated mid-request state-change (operator/CLI resolves the discrepancy concurrently) → handler rejects with 409.
8. **F19 BaseLayoutVM-inheritance asymmetry** + **F21 retrofit completeness as discriminating test** (R3 + R5 LOCKs). T-2.7 retrofit covers 13 standalone VMs + 21 callsites via grep-driven Pass A + Pass B; T-2.8 test re-runs Pass A grep at test time + asserts every matching VM has `banner_resolve_link` field; NOT hard-coded class list.
9. **L-W1 stub-then-extend ordering** (R1 M#1). T-2.5 + T-2.6 each ship green standalone (test invokes the task's own error-template branches; template doesn't error on stub-branch absence). T-2.10 polishes ALREADY-SHIPPED templates.
10. **L-W2 service `ValueError` re-read disambiguation** (R1 M#2). T-2.6 POST handler catches `ValueError` from `apply_tier2_resolution`; re-reads discrepancy state from fresh connection; routes to 14a (400 if re-read confirms pending) OR 14b (409 if re-read shows terminal state). Discriminating test pinned via separate-connection + commit semantics.
11. **L-W5 late VM-validator additions** (R4 LOCK). T-2.7 `__post_init__` validator on `BaseLayoutVM.banner_resolve_link` field must be additive (default-None-pass); all 13 standalone VMs + 21 callsites must still pass.
12. **Sentinel-leak audit pattern** (Phase 12 Sub-bundle B precedent). T-2.4 template renders `actual_value_json` content; sentinel-leak test asserts ZERO sensitive data in rendered HTML.
13. **F20 ASCII-only templates** (CLAUDE.md cp1252 gotcha + Phase 12.5 #1 F12 inheritance). NO non-ASCII glyphs in `reconcile_discrepancy_resolve.html.j2` OR error templates OR banner template extension in `base.html.j2`.
14. **NO behavioral changes to non-touched surfaces** (plan §C.3 LOCK). Especially: `apply_tier2_resolution` service entry UNCHANGED; CLI commands UNCHANGED; classifier UNCHANGED; `/schwab/setup` + `/schwab/status` UNCHANGED; multi-leg auto-redirect banner (Phase 12.5 #1) UNCHANGED; schema UNCHANGED.
15. **Pre-Codex orchestrator-side review** (NEW C.C lesson #6 — BINDING per plan §K): before invoking `copowers:adversarial-critic`, dispatch a focused reviewer subagent with plan §A acceptance criteria + brief §0.6 BINDING contracts + brief §0.7 F1-F21 invariants + brief §0.8 13 lessons as anchors; ask for a deviation list ≤600 words.

---

## §3 Operator-witnessed verification gate (6 surfaces per plan §H)

Per plan §H.1-§H.6 (matches spec §17.1 LOCK and §1.2 #12 operator-lock):

| Surface | Type | Acceptance |
|---|---|---|
| **S1** | Inline `pytest -m "not slow" -q -n auto` + ruff + slow E2E | ALL fast tests pass (target ~4793 = 4712 baseline + ~81 new). 3 pre-existing `phase8 walkthrough` failures unchanged; no other failures. Ruff baseline 18 E501 UNCHANGED. Slow E2E `test_phase12_5_bundle_2_web_tier2_happy_path.py` PASSES. |
| **S2** | Banner-link navigation | Start `swing web --port 8081` worktree-side. Visit `/dashboard` (production state has 6 pending-ambiguity discrepancies). Assert banner text contains an `<a>` link to the resolve form for the OLDEST pending-ambiguity discrepancy (`ORDER BY discrepancy_id ASC`). Click link → navigates to `/reconcile/discrepancy/{id}/resolve`. |
| **S3** | Form-render with context | Inspect rendered `/reconcile/discrepancy/{id}/resolve` page. Assert pre-resolution context section renders discrepancy_type + ambiguity_kind + journal-side value + Schwab-side value + delta per spec §7 mapping for the seeded discrepancy_type (DHC `unmatched_open_fill` or similar). Assert all menu items from `get_choice_menu(ambiguity_kind)` render with `requires_custom_value` markers + recommended badge where applicable. Assert ZERO console errors. ASCII-only template content (codepoint < 128). |
| **S4** | Successful POST + HX-Redirect | Submit a `keep_journal_as_is` resolution (no custom payload required) on disc #52 (DHC). Assert 204 response + `HX-Redirect: /dashboard?reconcile_resolved={correction_id}` header. Browser navigates. Assert `reconciliation_corrections` row inserted with `applied_by='operator'` + `correction_action='operator_resolved_ambiguity'`. Assert `reconciliation_discrepancies.resolved_by='operator_web'` (NOT `'operator'` — distinguishability per LOCK #3). **PRODUCTION WRITE** — operator pre-authorizes per-invocation per C.D-arc lesson #2. |
| **S5** | Banner-clears post-resolve | After S4 resolution, dashboard banner count drops by 1 (from 6 → 5 pending-ambiguity OR similar). Banner link target updates to next-oldest pending-ambiguity discrepancy. If no other pending-ambiguity rows exist, banner suppressed entirely. **PRODUCTION-STATE READ** (no further mutation needed). |
| **S6** | CLI/web parity | Separately resolve a second seeded discrepancy via CLI: `python -m swing.cli journal discrepancy resolve-ambiguity <id> --choice keep_journal_as_is --reason 'test'` on disc #53 (VSAT). Query: `SELECT discrepancy_id, resolved_by FROM reconciliation_discrepancies WHERE discrepancy_id IN (52, 53)`. Assert: disc #52 `resolved_by='operator_web'` (web path); disc #53 `resolved_by='operator'` (CLI path). Audit-row parity test uses semantic-shape projection (excludes identity/time/source fields per spec §13 R2 LOCK). **PRODUCTION WRITE** — operator pre-authorizes. |

**Gate session budget:** 6 surfaces. Medium-sized gate. **Operator-paired-gate driving — ONE COMMAND AT A TIME on production writes** (per handoff brief §0 LOCK); inline-batched OK on read-only surfaces.

**Production-write classifier soft-block awareness at S4+S6**: dispatch is production-writes from Claude Code's classifier perspective. Operator pre-authorizes via gate-path AskUserQuestion OR plain-chat "yes" PER INVOCATION (C.D-arc lesson #2).

**Production state post-gate:** banner count reduced from 6 → 4 (DHC #52 + VSAT #53 resolved via gate; 4 remaining DHC + VSAT family from runs #67 + #68 still pending — operator continues dispositioning per C.D-cleanup precedent). **Phase 12.5 #2 ship adds web surface; production state changes through operator gate use.**

---

## §4 OUT OF SCOPE (do not do)

- **Schema additions or migrations** — F1 + F19 escalation rule.
- **Override of any §0.6 LOCK** — all 12 operator-locked.
- **Web Tier-3 override surface** — V2 candidate banked §15.3.
- **Web Tier-1 auto-correct undo surface** — V2 candidate banked §15.4.
- **`/reconcile/pending` list page** — V2 candidate banked §15.5.
- **Audit-chain show page** — V2 candidate banked §15.1.
- **Success toast renderer on `/dashboard?reconcile_resolved={id}`** — V2 candidate banked §15.2; query token IS included per LOCK #4 but dashboard does NOT consume V1.
- **CLI helper extraction / DRY refactor** — V2 candidate banked §15.13. Plan T-2.1 DUPLICATES regex byte-for-byte.
- **Pipeline-active exclusion on Tier-2** — V2 candidate banked §15.6.
- **Explicit `surface` column V2 migration** — V2 candidate banked §15.7.
- **CLAUDE.md / orchestrator-context archive-splits** — Phase 12.5 #3 scope.
- **Phase 8 walkthrough failing-test triage** — Phase 12.5 #3 scope.
- **Ruff 18 E501 cleanup** — Phase 12.5 #3 scope.
- **Phase 12.5 #1 architectural inconsistency** (plan §H.4 tier-3-override-no-clear semantic vs shipped helper SQL) — Phase 12.5 #3 scope.
- **V2 candidates** (per spec §15; 13 banked items) — do NOT in-scope any.
- **Behavioral changes to non-touched existing surfaces** — Sub-bundle C.C+C.D + Phase 12.5 #1 + Sub-bundle B shipped surfaces UNCHANGED.

---

## §5 Return report shape

After all 11 tasks land + Codex chain converges + before final return-report commit, draft a return report at `docs/phase12-5-bundle-2-web-tier2-discrepancy-resolution-executing-plans-return-report.md` (mirroring Phase 12.5 #1 return-report shape):

1. Final HEAD on branch + commit count breakdown (11 task-impl + N Codex-fix + 1 return-report).
2. Codex round chain (R1-RN summary table + convergent shape; finding-count taper).
3. Test count delta + ruff baseline + schema version delta (v19 UNCHANGED expected per F1).
4. Operator-witnessed verification surfaces (PENDING orchestrator-driven gate; 6 surfaces per plan §H).
5. Per-task deviations from plan (if any) with rationale + V2.1 §VII.F amendment candidates banked.
6. Codex Major findings ACCEPTED with rationale (if any). **Target: ZERO ACCEPT-WITH-RATIONALE** matching Phase 12.5 #2 brainstorm + writing-plans clean-record streak.
7. Watch items for orchestrator (V2 candidates surfaced; Phase 12.5 #3 dispatch readiness).
8. Worktree teardown status.
9. Per-task disposition LOCKS.
10. Forward-binding lessons for future bundles (especially Phase 12.5 #3 + Phase 13).
11. CLAUDE.md status-line refresh draft text for orchestrator paste-in at integration-merge time.
12. Composition-surface verification (`^def ` grep on touched modules).
13. Pre-existing LOCK regression evidence (`apply_tier2_resolution` external surface UNCHANGED; CLI surface UNCHANGED; Phase 12.5 #1 banner UNCHANGED; Sub-bundle B routes UNCHANGED).
14. F1-F21 invariants verification matrix.
15. 13 forward-binding lessons consumption verification (8 inherited + 5 NEW L-W1..L-W5 each addressed in implementation).

---

## §6 Dispatch metadata

- **Subagent type:** `general-purpose` (full tool surface needed).
- **Foreground vs background:** foreground (default).
- **Worktree:** YES — per §1.1.
- **Model:** defer to harness default.
- **Expected duration:** ~6-10 hr implementation + ~2-4 hr Codex chain + 6-surface operator-witnessed gate. Total **~2-3 days operator-paced**.

---

## §7 If you get stuck

- If plan §A binding contracts conflict with what spec §1-§13 says, **plan wins** per L-W4 + plan §J amendments ("Plan supersedes spec" notes).
- If a Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly in return report. **Target: ZERO ACCEPT-WITH-RATIONALE** matching Phase 12.5 #2 brainstorm + writing-plans precedent.
- If you need a schema element NOT in plan §A + spec §3, **STOP + escalate** (F1 + F19 plan-author schema additions escalation rule).
- DO NOT propose new architectural surfaces within Phase 12.5 #2 scope (§4 lock).
- DO NOT modify CLI body (F12 + LOCK #11 + §4 lock).
- DO NOT add `Co-Authored-By` footer to any commit message (F5 + §1.3; ~147+ cumulative ZERO drift).
- DO NOT propose web Tier-3 override surface within Phase 12.5 #2 scope (§4 lock; V2 candidate).
- DO NOT propose dashboard per-discrepancy list within Phase 12.5 #2 scope (LOCK #7; V2 candidate).
- DO NOT propose success toast consumer on `/dashboard?reconcile_resolved={id}` within Phase 12.5 #2 scope (LOCK #8 includes query token only; dashboard does NOT consume V1; V2 candidate).
- DO NOT propose schema additions within Phase 12.5 #2 scope (§4 lock).
- If you encounter a Phase 7/8/9/10/11/12/12.5-#1 lesson that conflicts with a Phase 12.5 #2 implementation proposal, the prior-phase lesson wins (validated by ship-experience). Surface the conflict as a constraint.
- If Codex pushes back on **L-W1 stub-then-extend ordering** (e.g., "but landing all error templates in T-2.10 is cleaner..."), HOLD THE LINE — the LOCK is plan §A T-2.5/T-2.6/T-2.10 reorder + R1 M#1 fix at writing-plans time. T-2.5 + T-2.6 MUST ship green standalone; T-2.10 polishes ALREADY-SHIPPED templates.
- If Codex pushes back on **L-W2 service ValueError re-read disambiguation** (e.g., "but uniform 400 is simpler..."), HOLD THE LINE — the LOCK is plan §A T-2.6 Branch 14a/14b split + R1 M#2 fix at writing-plans time. POST-service `ValueError` MUST re-read state from fresh connection; routes 400 (if input invalid) vs 409 (if state changed).
- If Codex pushes back on **F12 CLI surface UNCHANGED** (e.g., "but extracting the helper would be DRY..."), HOLD THE LINE — the LOCK is plan §A T-2.1 + LOCK #11 + brainstorm OUT-OF-SCOPE preservation. T-2.1 DUPLICATES regex byte-for-byte from `cli.py:2291`. DRY consolidation banked as V2 candidate §15.13.
- If Codex pushes back on **F18 hidden state anchor `ambiguity_kind_at_render`** (e.g., "but the POST handler already validates the discrepancy state..."), HOLD THE LINE — the LOCK is plan §A T-2.4/T-2.6 + spec §6 R1 LOCK + Phase 9 D R2 M#1 precedent. Concurrent-resolve race requires hidden state anchor + re-read disambiguation; both are required defenses.
- **Pre-Codex orchestrator-side review (NEW C.C lesson #6 — BINDING)**: before invoking `copowers:adversarial-critic`, dispatch a focused reviewer subagent with plan §A acceptance criteria + brief §0.6 BINDING contracts + brief §0.7 F1-F21 invariants + brief §0.8 13 lessons as anchors; ask for a deviation list ≤600 words. Cheap; absorbs LOCK divergences pre-Codex; saved findings on EVERY recent dispatch.

---

## §8 Operator-paired gate notes

Phase 12.5 #2's 6-surface gate is medium-sized (matches Phase 12.5 #1 + Sub-bundle 1+2 + C.C 4-7-surface mid-cycle precedents). Plan for an operator-paired session:

- **No mid-dispatch operator pause required** — Phase 12.5 #2 is fully synthetic-fixture-driven; no operator interaction needed during implementation phase.
- **Production refresh-token clock** — expires ~2026-05-24T06:40; verify TTL > 1hr at S4 pre-check; operator re-auths via `/schwab/setup` web form OR `swing schwab setup` CLI if needed.
- **Production state for gate** — 6 pending-ambiguity discrepancies already in production (carry-over from Phase 12.5 #1 S3 NEW discreps DHC #52 + VSAT #53 + 4 more re-emerged from runs #67 + #68). Gate consumes these as natural fixtures — no synthetic plant needed for S2/S3/S5.
- **Production-write classifier soft-block** — S4 + S6 are production-writes; operator pre-authorizes via gate-path AskUserQuestion OR plain-chat "yes" PER INVOCATION (C.D-arc lesson #2).
- **One command at a time** — per operator preference; orchestrator sends ONE command per turn, waits for output, verifies, sends next.
- **Worktree-side web server** — S2/S3/S4/S5 use `swing web --port 8081` (NOT 8080); stop the server when gate done.
- **Operator-architectural-pushback STOP-and-recover** — if S4+S6 surface architectural divergences (e.g., audit row shape mismatch beyond expected `resolved_by` distinguishability), STOP, investigate, recover (C.D-arc lesson #1). NOT push-through.
- **Post-gate state** — DHC #52 + VSAT #53 resolved (banner count 6 → 4). 4 remaining pending-ambiguity discreps stay; operator continues dispositioning post-merge per C.D-cleanup precedent.

---

*End of brief. Phase 12.5 #2 executing-plans dispatch — 11 tasks T-2.1..T-2.11; 12 operator-locks encoded (4 spec §2 + 8 §16 ACCEPTED at brainstorm defaults); 21 binding invariants F1-F21 enforced; 13 forward-binding lessons (8 inherited + 5 NEW L-W1..L-W5); schema v19 UNCHANGED; ~+81 fast tests + 1 slow E2E + ~+970 production LOC projection. Codex chain projected 3-5 rounds. Expected duration ~2-3 days operator-paced including 6-surface operator-witnessed gate.*
