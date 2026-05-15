# Phase 12 Sub-bundle C — writing-plans dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Convert the Phase 12 Sub-bundle C (auto-correct journal-from-Schwab reconciliation) brainstorm spec into an executable implementation plan via `copowers:writing-plans`. The skill wraps `superpowers:writing-plans` + adversarial Codex MCP review. Output is a single plan file (per writing-plans convention) that the orchestrator subsequently dispatches via `copowers:executing-plans` as **4 sub-sub-bundle dispatches** (C.A → C.B → C.C → C.D) per spec §12 decomposition.

**Expected duration:** ~5-9 hr planning + ~3-5 hr Codex convergence. Total ~8-14 hr (matches Phase 9 writing-plans precedent: 5 Codex rounds + 2257-line plan; Phase 10 writing-plans precedent: 6 Codex rounds + 2008-line plan; Sub-bundle C scope is mid-range between the two — substantial architectural pivot + 4 sub-sub-bundles + 39 cumulative forward-binding lessons inheritance). Plan line target: **~2200–2900 lines**.

---

## §0 Inputs

### §0.1 Spec

- **SPEC_PATH:** `docs/superpowers/specs/2026-05-15-phase12-bundle-C-auto-correct-reconciliation-design.md`
- **Spec status:** Codex R1-R8 substantive + R9 confirmation → NO_NEW_CRITICAL_MAJOR at HEAD `d682c25` on main. **1444 lines.** 10 commits in spec chain (`e72daf1` initial + 9 Codex-fix rounds through `d682c25`).
- **Spec produces** (per §1.1): a locked schema set (§3 — 1 new table `reconciliation_corrections` + 1 new column `reconciliation_discrepancies.ambiguity_kind` + 1 widening of `reconciliation_discrepancies.resolution` CHECK enum 5→9 values + 1 new column `review_log.superseded_by_correction_id` + 1 widening of `trade_events.event_type` CHECK enum + 1 new column `schwab_api_calls.linked_correction_id` + schema_version v18→v19); locked classifier shape (§4 — pure function + per-discrepancy-type sub-classifiers + determinism principle + validator-respecting downgrade rule); locked auto-correction service architecture (§5 — module + transactional discipline + idempotency); locked Tier-2 CLI surface (§6 — V1 only, per-`ambiguity_kind` resolution choices); locked reconciliation flow pivot (§7 — both `run_schwab_reconciliation` AND `run_tos_reconciliation`); locked backfill path (§8 — operator-initiated CLI + dry-run default + explicit `--apply` + idempotency); locked lifecycle integration (§9 — Phase 6 review_log freezing RETAIN-and-mark-superseded; Phase 7 fills.reconciliation_status unchanged V1; Phase 8 daily_management snapshots RETAIN as historical; Phase 9 reconciliation_runs state machine unchanged); 3 discriminating-example walkthroughs (§10 — CVGI 41 + DHC 39 + VSAT 40); locked migration strategy (§11 — atomic single-file 0019); 4 sub-sub-bundle decomposition (§12 — C.A/C.B/C.C/C.D with cross-bundle dependencies); explicit OUT-OF-SCOPE statement on fill auto-population at trade-entry time (§13 — separate future sub-bundle); 15 open questions for orchestrator triage (§14); writing-plans hand-off section (§15).
- **Spec deliberately does NOT produce** (per §1.2): migration SQL drafts, code drafts, sub-sub-bundle task-decomposition into per-task acceptance criteria, re-litigation of §1.3 binding constraints. **THAT IS WRITING-PLANS' JOB.**

### §0.2 Project state at dispatch time

- **HEAD on `main`:** `effb995` (post-lesson-banking from Sub-bundle C brainstorm + push). Brief commit will land at HEAD+1 pre-dispatch.
- **Test count:** **3862 fast passing on main** + 4 pre-existing failures (3 phase8 walkthrough + 1 schwab_setup_cli sentinel — see §0.5 below) + 1 skipped. Verified inline at brief drafting time post-Sub-bundle-B-merge.
- **Ruff baseline:** **18** (E501 only; unchanged across Phase 11 + Phase 12 Sub-bundle A + B).
- **Schema version:** **v18.** Locked since Phase 11 Sub-bundle A T-A.7 at 2026-05-14. Sub-bundle B was consumer-side; Sub-bundle C.A migration brings v18 → v19.
- **Phase 12 Sub-bundle A + B SHIPPED.** Sub-bundle A `123d27a` (operational-pain mini-bundle: env vars + setup self-healing + pipeline env-var wiring + cleanup-script regex). Sub-bundle B `b09eb06` + orchestrator-inline gate-fix `7b75d4a` (web-UI-friendliness: credentials-in-file cfg-cascade + web OAuth paste-back form Outcome B + `/schwab/setup` nav link on `/config`).
- **Production discrepancy state:** 3 unresolved-material (39 DHC + 40 VSAT + 41 CVGI from pipeline #63 reconciliation_run #10) + 30 resolved historical (mostly `acknowledged_immaterial` from operator's manual triage sweep during 11 + 12A gates). LEFT UNRESOLVED BY DESIGN pending Sub-bundle C ship. Phase 10 dashboard banner currently shows "3 unresolved" — accurate state.
- **Production refresh-token clock:** fresh 7-day clock issued 2026-05-15T17:05:00+00:00 (during Sub-bundle B S5 gate); expires 2026-05-22T17:05:00+00:00. Operator may need to re-auth before Sub-bundle C.D gate if gate session lands after that date.

### §0.3 Operator-resolved open questions (BINDING for plan)

Spec §14 enumerates 15 OQs with spec recommendations. The 5 orchestrator-decision-pending OQs are resolved as follows (post-brainstorm triage 2026-05-15):

| OQ | Question | Operator-resolved disposition |
|---|---|---|
| **OQ-2** | Pivot scope: Schwab only OR both Schwab + TOS-CSV? | **ACCEPT spec default: pivot BOTH.** Per-discrepancy-type sub-classifiers handle source-specific nuance internally. |
| **OQ-4** | `multi_partial_vs_consolidated` default highlighted choice | **ACCEPT spec-revised default: `keep_journal_as_is`.** Operator-confirmed after VWAP + V1-mapper-coverage walkthrough. V2 mapper widening (expose `orderActivityCollection[].executionLegs[]` for auto-VWAP tier-1 redirect) banked as the **next-architectural-dispatch slot** post-C.D ship (see §0.6). |
| **OQ-5** | Backfill: auto-fire at C.D ship OR explicit operator invocation? | **ACCEPT spec default: EXPLICIT operator invocation only.** C.D ship-time gate plays operator-witnessed walkthrough role for 39/40/41; beyond that, backfill is operator-on-demand only. Avoids surprising production state mutation post-merge. |
| **OQ-7** | Phase 10 dashboard banner predicate widening (include `pending_ambiguity_resolution`) | **ACCEPT spec default: in C.D scope** (NOT follow-up dispatch). Update Phase 10 `discrepancies.py` helper + retrofit 10 base-layout VM consumers from Phase 10 Sub-bundle E within C.D. Banner correctly increments when DHC/VSAT land in pending state during C.D gate S4; clears to ZERO after S6+S7 dispositions. Slight C.D scope expansion (10 VM retrofits) accepted. |
| **OQ-8** | Tier-3 override CLI: confirmation prompt? | **ACCEPT spec default: confirmation prompt by default + `--force` flag for non-interactive.** Mirrors `cleanup-locked-scratch-dirs.ps1 -DeregisterFirst` precedent. |

**LOCKED-in-spec (no orchestrator action needed; track only):**

| OQ | Disposition | Locked at |
|---|---|---|
| OQ-1 | NEW dedicated `reconciliation_corrections` table (vs `event_log` extension) | spec §3.1.0 |
| OQ-3 | Tier-2 CLI-only V1 (web V2 deferred) | spec §6.1 |
| OQ-13 | Sandbox short-circuit semantics: under sandbox, auto-correction is no-op | spec §9.7 |
| OQ-14 | Validator chain composed from NEW shim module `swing/trades/reconciliation_validators.py` | spec §5.5 |

**Writing-plans decides (defer to plan author):**

| OQ | Spec recommendation | Plan posture |
|---|---|---|
| OQ-6 | `correction_set_id` mechanic: inline two-step INSERT-then-UPDATE | Writing-plans verifies + locks at task grain. |
| OQ-9 | `__delete__`/`__insert__` sentinels in `field_name` (vs separate join table) | Writing-plans verifies + locks at task grain. |
| OQ-12 | Cross-column CHECK at schema time: schema-defended | Writing-plans verifies SQLite syntax under runner; locks. |
| OQ-15 | Tier-3 override on already-superseded chain: REJECT | Writing-plans confirms + locks CLI rejection wording. |

**V2-banked / informational (no action this dispatch):**

| OQ | Disposition |
|---|---|
| OQ-10 | Schwab API response body caching for backfill replay — V2 candidate. Banked. |
| OQ-11 | Brief enumeration mismatches against shipped schema (resolution + reconciliation_status enums) — informational; spec uses shipped schema; brief-empirical-verification lesson family. |

### §0.4 Forward-binding lessons inherited (BINDING for plan)

**39 cumulative lessons** inheritance through Sub-bundle C writing-plans:
- Phase 11 Schwab arc: 5 A + 7 B + 5 C + 0 D = **17 lessons**
- Phase 12 Sub-bundle A: 5 lessons
- Phase 12 Sub-bundle B: 12 lessons (return report §10)
- Phase 12 Sub-bundle C brainstorm: 5 NEW lessons (orchestrator-context.md `effb995`)

The 5 NEW Sub-bundle C brainstorm lessons (`effb995`) are particularly load-bearing for writing-plans:

1. **9-substantive-round chain new project high-water mark.** Architectural-pivot brainstorms have more wording-precision surface than schema-design brainstorms. **Writing-plans budget: 5-7 rounds (substantial plan; convergent chain expected).**
2. **Brainstorm-time composition-source claims need empirical verification BEFORE spec encoding.** Apply to writing-plans-time: plan §A pre-verification lists each shipped surface the plan composes over + grep-verifies callable shapes.
3. **Persisted-JSON-tier-1 vs re-fetched-tier-1 asymmetry.** V1 mapper limitation forces tier-2 for Pass-2 re-fetches. Plan §A locks the §8.4 Pass-2-tier-1-FORBIDDEN treatment; V2 mapper widening explicitly OUT-OF-SCOPE (next-architectural-dispatch).
4. **Synthetic-fixture-only acceptance test for production-write-contract surfaces.** C.D gate's `--custom-value` contract acceptance test uses isolated-DB synthetic-fixture pathway, NOT production DHC/VSAT cases. Plan §A.D.gate-section locks this verbatim per spec §15.5 C.D-gate LOCKED revised mechanic.
5. **Brief enumeration of shipped CHECK enums needs empirical verification against migration files.** Apply to writing-plans-time: plan §A pre-verification greps `swing/data/migrations/0017_*.sql` + `0014_*.sql` to confirm `reconciliation_discrepancies.resolution` 5-value enum + `fills.reconciliation_status` 5-value enum + `trade_events.event_type` current enum BEFORE drafting migration 0019 widening SQL.

**Phase 12 Sub-bundle B's 12 forward-binding lessons** (return report §10) — particularly relevant:

- **Lesson #6 `apply_overrides()` discipline at Schwab entry points** — project-wide invariant candidate. Sub-bundle C's auto-correction service that constructs `schwabdev.Client(...)` directly (if any) inherits. If C.C composes over `swing/integrations/schwab/trader.py` + `marketdata.py` without direct Client construction, lesson banks for V2.
- **Lesson #7 `parse_qs` vs `unquote` for OAuth code parsing** — N/A for Sub-bundle C (no OAuth handling).
- **Lesson #8 Atomic file-write fsync discipline** — applies to any new file write in C.A migration runner + C.D backfill output (if any file-based artifacts shipped).
- **Lesson #9 Real-SDK compat regression test pattern** — applies if Sub-bundle C composes over schwabdev's private API (NOT expected V1; banked).
- **Lesson #10 Cross-bundle base-layout VM pin discipline** — every new VM extending `base.html.j2` populates `unresolved_material_discrepancies_count`. Phase 10 Sub-bundle E T-E.3 pinned; OQ-7 widens the predicate to include `pending_ambiguity_resolution`. Plan §C.D explicitly retrofits 10 base-layout VMs.
- **Lesson #11 HTMX gotcha trinity** — N/A V1 (CLI-only Tier-2 surface per OQ-3 lock); banks for V2 web surface.
- **Lesson #12 Sub-bundle A T-A.3 implementer gap pre-emption pattern** — for any new entry point that threads credentials through multiple call sites, route-level integration test MUST mock the service + assert EXACT cascade-resolved values were threaded. Sub-bundle C.C `run_schwab_reconciliation` pivot is the canonical equivalent; plan §A locks integration tests for both `run_schwab_reconciliation` AND `run_tos_reconciliation` call sites.

### §0.5 Brief-vs-shipped-schema empirical verification (pre-drafting checklist)

Per Lesson #5 above + §14.OQ-11. Writing-plans implementer MUST `grep -E "CHECK.*IN.*\(" swing/data/migrations/00{14,17,18}_*.sql` at plan-drafting time to verify the following shipped CHECK enum shapes BEFORE drafting migration 0019:

1. **`reconciliation_discrepancies.resolution`** — current 5 values: `('journal_corrected', 'source_treated_canonical', 'manual_override', 'unresolved', 'acknowledged_immaterial')`. Spec §3.2 widens to 9 values adding `('auto_corrected_from_schwab', 'pending_ambiguity_resolution', 'operator_resolved_ambiguity', 'operator_overridden')`.
2. **`fills.reconciliation_status`** — current 5 values: `('unreconciled', 'reconciled_match', 'reconciled_discrepancy', 'reconciled_discrepancy_resolved', 'manual_override')`. Spec §9.2 leaves UNCHANGED V1.
3. **`trade_events.event_type`** — current values verified at plan-drafting time. Spec §3.5 adds 1 new value: `'reconciliation_auto_correct'`. Plan migration 0019 widens the CHECK enum.
4. **`schwab_api_calls`** schema — current shape verified for `linked_*_id` FK precedent (Phase 11 Sub-bundle A T-A.7). Spec §1.5 + §3.6 adds 1 new FK column: `linked_correction_id`.

### §0.6 V2 mapper widening + auto-VWAP — OUT OF SCOPE for Sub-bundle C (operator-confirmed next-architectural-dispatch)

Per operator OQ-4 triage 2026-05-15 (Option C confirmation): expanding the V1 Schwab mapper at `swing/integrations/schwab/trader.py` to expose `orderActivityCollection[].executionLegs[]` (and the corresponding auto-VWAP tier-1 redirect path in the classifier) is the **next-architectural-dispatch slot** post-Sub-bundle-C.D ship. NOT Sub-bundle C scope.

**Writing-plans MUST NOT:**
- Propose mapper widening within any Sub-bundle C sub-sub-bundle scope.
- Propose auto-VWAP classifier sub-classifier path within Sub-bundle C scope.
- Propose any code change to `swing/integrations/schwab/trader.py:_parse_order_response()` (or equivalent) within Sub-bundle C scope.

**Writing-plans MUST:**
- Bank the V2 mapper widening dispatch as an explicit phase3e-todo entry in plan §Z (or equivalent housekeeping section).
- Ensure all C.B classifier + C.D backfill paths fall through cleanly when `executionLegs` is unavailable (per the §8.4 Pass-2-tier-1-FORBIDDEN lock — spec already encodes this; plan reaffirms).

---

## §1 Strategic context (brief-author-distilled)

### §1.1 Four operator-locked architectural constraints (BINDING)

Per spec §1.3 (operator-locked; do NOT re-litigate; writing-plans inherits):

1. **Schwab data IS truth.** When Schwab API responses are available + the call succeeded, journal converges TO Schwab.
2. **Three-tier resolution model.** Tier 1 unambiguous auto-correct (most common; ZERO operator involvement). Tier 2 ambiguity surfaced for operator decision (type-specific resolution choices). Tier 3 rare operator override of an applied tier-1 correction (audit chain preserves three-value history).
3. **Magnitude is the WRONG axis.** Determinism is the axis. NO magnitude-based auto-vs-surface threshold gates.
4. **`acknowledged_immaterial` back-compat preserved.** Existing 30 resolved discrepancies in production stay valid (no backfill rewriting). New discrepancies use new enum values (`auto_corrected_from_schwab` / `pending_ambiguity_resolution` / `operator_resolved_ambiguity` / `operator_overridden`).

### §1.2 Sub-sub-bundle decomposition (per spec §12)

| Sub-sub-bundle | Scope | Dependencies | Ships before |
|---|---|---|---|
| **C.A — Foundation** | Migration 0019 (1 new table `reconciliation_corrections` + 1 new column `ambiguity_kind` + 1 widening `resolution` enum + 1 new column `review_log.superseded_by_correction_id` + 1 widening `trade_events.event_type` enum + 1 new column `schwab_api_calls.linked_correction_id` + schema_version v18→v19); minimal repos + tests; ZERO behavioral changes to existing surfaces. | None (foundation). | C.B/C/D. |
| **C.B — Classifier + validator shim** | NEW `swing/trades/reconciliation_validators.py` shim module (4 callable predicates mirroring Phase 7 fills schema invariants); NEW classifier module with per-discrepancy-type sub-classifiers + determinism principle + validator-respecting downgrade; pure logic; no journal mutations; +discriminating tests against 39/40/41 fixtures. | C.A schema. | C.C/D. |
| **C.C — Auto-correction service + reconciliation flow pivot** | NEW service module owning BEGIN IMMEDIATE / COMMIT / ROLLBACK + reject-caller-held-tx contract + validator chain + audit emission + idempotency; refactor `run_schwab_reconciliation` AND `run_tos_reconciliation` from "emit + wait" to "classify + dispatch + apply" pivot; surface-aware (pipeline + cli + sandbox short-circuit); +integration tests against simulated reconciliation runs. | C.A schema + C.B classifier. | C.D. |
| **C.D — Tier-2 CLI surface + backfill + Phase 10 banner predicate widening** | NEW `swing journal discrepancy show-ambiguity` + `resolve-ambiguity --choice <code> [--custom-value JSON] [--reason ...]` + `override-correction --truth JSON --reason ...` + `swing journal reconcile-backfill [--dry-run] [--apply] [--ticker ...]` CLI surfaces; per-(`ambiguity_kind`, choice_code) handler architecture; tier-3 override workflow; Phase 10 `discrepancies.py` helper + 10 base-layout VM mixin predicate widening to include `pending_ambiguity_resolution` (OQ-7); cycle-checklist + CLAUDE.md gotcha additions; operator-witnessed gate against production 39/40/41. | C.A + C.B + C.C. | (CLOSES Sub-bundle C) |

### §1.3 Plan-output shape expectations

Per spec §15 hand-off:

- §15.1: 13 BINDING items writing-plans inherits as locked from spec (re-enumerated in plan §A with task-level acceptance criteria).
- §15.2: 15 §14.OQ items triaged per plan posture (spec recommendation OR escalate).
- §15.3: 8 pre-verifications writing-plans does against shipped code BEFORE drafting per-task acceptance criteria.
- §15.4: 10 forward-binding lessons for executing-plans dispatches.
- §15.5: per-sub-sub-bundle operator-witnessed gate plan (C.A 4 surfaces; C.B 3 surfaces; C.C 4 surfaces; C.D 10 surfaces — the C.D gate is the big one).

Plan should be **single-file output** at `docs/superpowers/plans/<YYYY-MM-DD>-phase12-bundle-C-auto-correct-reconciliation-plan.md`, ~2200-2900 lines. Per-sub-sub-bundle task grain locked; per-task acceptance criteria locked; per-task projected test deltas locked; cross-sub-sub-bundle dependencies enumerated.

---

## §2 Plan scope (what writing-plans produces)

### §2.1 Per-sub-sub-bundle task decomposition

For each of C.A / C.B / C.C / C.D, plan §A enumerates:

- Task list with task IDs (T-C.A.0 ... T-C.A.N / T-C.B.0 ... / etc.).
- Per-task scope (1-2 paragraphs).
- Per-task acceptance criteria (numbered list).
- Per-task discriminating-test patterns (mirror spec §10 walkthroughs where applicable).
- Per-task files-touched list.
- Per-task tests-added projection.
- Per-task commit message stem.
- Per-task ordering within sub-sub-bundle (when tasks have intra-sub-bundle dependencies).

### §2.2 Cross-sub-sub-bundle dependencies

Plan §B enumerates cross-bundle pins: classifier interfaces (C.B exposes; C.C consumes); audit-row shapes (C.A defines; C.C populates); VM mixin signatures (C.A schema underpins; C.D retrofits). For each pin: pin-test name + skip decoration if pin is forward-binding (un-skip at consumer-bundle landing).

### §2.3 Per-sub-sub-bundle operator-witnessed gate plan

Plan §C enumerates per-sub-sub-bundle gate surfaces inheriting spec §15.5:

- C.A 4 surfaces: pytest pass + db-migrate fresh + db-migrate prod-snapshot + ruff unchanged.
- C.B 3 surfaces: pytest pass + classifier against 39/40/41 fixtures emitting expected ClassificationResult shapes + ruff unchanged.
- C.C 4 surfaces: pytest pass + simulated reconciliation run end-to-end (graceful degradation tested) + sandbox short-circuit + ruff unchanged.
- **C.D 10 surfaces (the big one):** pytest pass + reconcile-backfill --dry-run output projection matrix + --apply --ticker CVGI (auto-correct) + --apply --ticker DHC/VSAT (pending_ambiguity) + show-ambiguity 39 + **resolve-ambiguity payload-contract acceptance test via synthetic-fixture-only isolated-DB pathway** (Lesson #4 above; spec §15.5 LOCKED revised mechanic) + show-ambiguity 40 + resolve-ambiguity 40 per operator's real disposition + Phase 10 dashboard banner clears + ruff unchanged + cycle-checklist + CLAUDE.md gotcha additions.

### §2.4 Migration 0019 SQL drafting

Plan §D drafts the full migration 0019 SQL with:

- Atomic single-file landing (per spec §11 LOCK; Phase 9 Sub-bundle A T-A.1 precedent; Phase 11 Sub-bundle A T-A.7 precedent).
- BEGIN IMMEDIATE / COMMIT discipline (per `swing/data/db.py:_apply_migration` Phase 7 hotfix `283d4fa` discipline).
- Backup gate ON `current_version == 18 AND target >= 19` only (Phase 7 Sub-A I1 lesson).
- Test fixture PRAGMA `foreign_keys=ON` discipline (Phase 7 hotfix `283d4fa` lesson).
- Cross-column CHECK between `ambiguity_kind` and `resolution` per OQ-12 spec recommendation.
- 5 schema deltas:
  1. CREATE TABLE `reconciliation_corrections` (19 columns per spec §3.1).
  2. ALTER TABLE `reconciliation_discrepancies` ADD COLUMN `ambiguity_kind` TEXT NULL CHECK + cross-column CHECK with `resolution`.
  3. ALTER TABLE `reconciliation_discrepancies` widening `resolution` CHECK enum 5 → 9 values (table-rebuild required for CHECK widening in SQLite; preserves existing 30+ rows; PRAGMA foreign_keys=OFF discipline during rebuild per Phase 7 hotfix).
  4. ALTER TABLE `review_log` ADD COLUMN `superseded_by_correction_id` INTEGER NULL FK → `reconciliation_corrections(correction_id)` ON DELETE SET NULL.
  5. ALTER TABLE `trade_events` widening `event_type` CHECK enum +`'reconciliation_auto_correct'` value (table-rebuild required).
  6. ALTER TABLE `schwab_api_calls` ADD COLUMN `linked_correction_id` INTEGER NULL FK → `reconciliation_corrections(correction_id)` ON DELETE SET NULL.
  7. UPDATE `swing/data/db.py:EXPECTED_SCHEMA_VERSION` constant from 18 → 19.

### §2.5 Test projection

Plan §E projects total test delta. Spec §12 projects:
- C.A: +35..+55 fast tests
- C.B: +50..+90 fast tests
- C.C: +60..+120 fast tests
- C.D: +80..+150 fast tests
- **Sub-bundle C cumulative: +225..+415 fast tests** (matches Phase 9 arc +503 fast tests / Phase 10 arc +494 fast tests precedent for arc-scale dispatches).

Per the Sub-bundle A/B overshoot precedent (+35 actual vs +25 projected for A; +66 actual vs +18-28 projected for B), actual likely lands in upper half of projection. **Plan §E should explicitly note: actual test delta likely +250..+450** based on overshoot pattern across 4 sub-sub-bundles.

### §2.6 V2 candidates explicitly carried forward

Plan §Z (or housekeeping section) enumerates V2 candidates banked from Sub-bundle C brainstorm + Sub-bundle C writing-plans drafting:

1. **V2 mapper widening + auto-VWAP classifier path** (operator-locked next-architectural-dispatch per OQ-4 Option C; mandatory carry-forward).
2. **`fills.reconciliation_status` widening** (spec §9.2 V1 lock; bank V2 candidate per spec §14.OQ-1 second-paragraph rationale).
3. **Web Tier-2 surface** (OQ-3 V1 CLI-only lock; bank V2).
4. **`schwab_api_calls.surface='auto_correct'` enum widening** (spec recommendation uses `'cli'` V1; bank V2 distinct surface enum).
5. **Schwab API response body caching for backfill replay** (spec §14.OQ-10 V2; bank).
6. **Refactor reconciliation_validators shim into repo modules** (spec §14.OQ-14 V2 candidate; promote validators to first-class on `swing/data/repos/*.py`).
7. **Sandbox-friendly preview mode for auto-correction** (spec §14.OQ-13 V2 candidate; banked).

---

## §3 OUT OF SCOPE (do not do)

- **Migration 0019 SQL drafting beyond what spec §11 specifies.** Plan implements; does not redesign schema sketch.
- **Code drafting.** Plan provides per-task acceptance criteria; does NOT write code.
- **Re-litigating spec §1.3 binding constraints** — accepted as given. Operator-locked.
- **V2 mapper widening** (§0.6 lock + operator-confirmed Option C).
- **Fill auto-population at trade-entry time** (spec §1.7 + §13 explicit OUT-OF-SCOPE; separate future sub-bundle).
- **Re-deriving 39 cumulative forward-binding lessons** — accept as given; plan §0.4 inheritance.
- **Web Tier-2 surface** (OQ-3 V1 CLI-only lock).

---

## §4 Binding conventions

- **Branch:** `main`. Single commit OR landing+fixes split per Phase 9 + Phase 10 writing-plans precedent.
- **Commit message:** `docs(phase12): Phase 12 Sub-bundle C auto-correct reconciliation writing-plans plan`. No Claude co-author footer. No `--no-verify`. No amending.
- **Plan format:** mirror `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` (Phase 9 writing-plans canonical) or `docs/superpowers/plans/2026-05-13-phase10-metrics-dashboard-plan.md` (Phase 10 canonical). Section-numbered; locked decisions called out explicitly with rationale; per-task acceptance criteria explicit; per-sub-sub-bundle gate plan explicit.
- **Plan line target:** ~2200–2900 lines (per Phase 9 / Phase 10 precedent for arc-scale plans).
- **Adversarial review:** mandatory; iterate to `NO_NEW_CRITICAL_MAJOR`. **Budget 5-7 rounds** (substantial plan; convergent chain expected per lesson #1 above on architectural-pivot brainstorms; writing-plans likely slightly fewer rounds than brainstorm since spec is already locked).

---

## §5 Adversarial review watch items (writing-plans-phase specific)

For Codex rounds — pass these as targeted prompts to `copowers:adversarial-critic`:

1. **Spec §15.1 13-item BINDING inheritance integrity.** Plan §A enumerates each item + maps to per-task acceptance criteria. No item silently dropped or relaxed.
2. **Spec §15.2 OQ resolutions honored.** OQ-2/4/5/7/8 operator-resolved per §0.3 BINDING; OQ-1/3/6/9/12/13/14/15 LOCKED-in-spec disposition preserved; OQ-10/11 V2-banked.
3. **Spec §15.3 8 pre-verifications completed BEFORE plan drafting.** Plan §A enumerates each pre-verification + verbatim grep results. Especially: `executescript()` wrapper + `run_tos_reconciliation` + `run_schwab_reconciliation` exact module locations + `_construct_pipeline_schwab_client(cfg)` location + `swing journal discrepancy` CLI group + Phase 10 `discrepancies.py` helper + `swing/data/repos/fills.py` validator absence verification (Lesson #2 above; LOCKED in spec §14.OQ-14).
4. **Migration 0019 atomicity.** All 6 schema deltas under one atomic `executescript()` invocation with BEGIN IMMEDIATE / COMMIT; backup gate ON `pre_version == 18 AND post_version >= 19` only; PRAGMA foreign_keys=OFF during table-rebuilds; test fixture PRAGMA foreign_keys=ON to mirror production.
5. **CHECK enum widening table-rebuild discipline.** Both `reconciliation_discrepancies.resolution` widening + `trade_events.event_type` widening require SQLite table-rebuild (SQLite does NOT support `ALTER TABLE ... DROP/ADD CHECK` directly). Plan §D enumerates the rebuild SQL + preserves all existing rows.
6. **Audit-row write discipline.** Every `reconciliation_corrections` INSERT happens within the auto-correction service's BEGIN IMMEDIATE / COMMIT envelope; never from caller-held transaction (Phase 8 lesson family).
7. **Idempotency contract.** Auto-correction service re-invocation on same discrepancy_id is no-op (resolution_action already set; audit table prevents double-write via UNIQUE constraint OR app-layer guard). Plan §A locks the exact mechanic.
8. **Failure-mode V1 graceful-degradation contract.** Classifier OR auto-correction service raise → reconciliation falls through to "emit-only" Phase 9 behavior + log WARNING. Pipeline NEVER crashes. Per Phase 11 forward-binding lesson #2 (broaden the catch at pipeline boundary).
9. **Sub-bundle A T-A.3 implementer gap pre-emption (Lesson #12 inheritance).** Plan §A.C tasks MANDATE route-level integration tests for both `run_schwab_reconciliation` AND `run_tos_reconciliation` pivot callsites; mock the service + assert EXACT cascade-resolved credential values are threaded through.
10. **`apply_overrides` discipline at Schwab entry points (Lesson #6 inheritance).** If C.C composes over `schwabdev.Client(...)` construction directly (vs reusing `_construct_pipeline_schwab_client`), plan §A enumerates `apply_overrides(cfg)` at the new entry point + discriminating regression test.
11. **Phase 10 base-layout VM retrofit completeness (OQ-7).** Plan §A.D enumerates all 10 base-layout VMs to retrofit + each gets a discriminating test asserting banner predicate widens correctly. The Phase 10 Sub-bundle E T-E.3 cross-bundle pin remains un-skipped post-Sub-bundle-C.D.
12. **Synthetic-fixture-only payload-contract acceptance test (Lesson #4 inheritance).** Plan §A.D gate-section step S6 verbatim per spec §15.5 LOCKED revised mechanic. Production DHC/VSAT dispositions per operator's REAL data without contortion; payload-contract surface exercised via isolated synthetic-fixture DB.
13. **`tomli_w.dump` comment-stripping** (Sub-bundle B inheritance) — N/A for Sub-bundle C (no user-config.toml write paths expected V1; banks if any new CLI surfaces touch user-config.toml).
14. **USERPROFILE+HOME monkeypatch discipline** — applies to any new test fixture exercising paths under `~/swing-data/`. Per CLAUDE.md gotcha. Plan §A enumerates monkeypatch fixture for any C.A/C.B/C.C/C.D test that touches USERPROFILE-resolved paths.
15. **Datetime impedance + lexicographic ordering** (Phase 7 Sub-B lesson family) — `reconciliation_corrections.applied_at` TEXT format LOCKED per spec §3.1 to naive-UTC ISO with millisecond precision; plan §A validator policy.
16. **Per-row policy stamping (Phase 8 R1 M5 lesson)** — `reconciliation_corrections.risk_policy_id_at_correction` populated at service write-time per spec §3.1 + Codex R1 Major #3 nullable+SET-NULL fix. Plan §A locks the per-row stamp.
17. **Backup-on-every-rebuild discipline.** Both table-rebuilds (resolution enum + trade_events enum) preserve existing rows; backup gate fires at correct schema-version boundary.
18. **Operator-actionability test.** Each operator-facing surface (C.D CLI commands) answers: "what action does the operator take?" Each command's help text + error messages + usage examples are operator-actionable.
19. **Brief-premise empirical-verification (Lesson #5 inheritance).** Plan §A pre-verification list greps shipped migrations BEFORE locking CHECK enum widening shapes. Any divergence between spec §3 and shipped schema is FLAGGED in plan §A as a brief-vs-shipped-schema deviation (per §14.OQ-11 carried forward).

---

## §6 Done criteria

1. Plan at `docs/superpowers/plans/<YYYY-MM-DD>-phase12-bundle-C-auto-correct-reconciliation-plan.md` covering §2.1–§2.6.
2. Per-sub-sub-bundle task decomposition (4 sub-sub-bundles C.A/C.B/C.C/C.D; ~20-35 tasks total estimated; writing-plans refines).
3. Each task has: scope + acceptance criteria + discriminating-test patterns + files-touched + tests-added projection + commit message stem.
4. §15.5 per-sub-sub-bundle gate plan (4 + 3 + 4 + 10 = 21 gate surfaces total).
5. §15.3 pre-verifications all completed against shipped code with verbatim grep results in plan §A.
6. Writing-plans went through ≥3 Codex rounds reaching `NO_NEW_CRITICAL_MAJOR` (target 5-7 rounds per architectural-pivot brainstorm lesson).
7. Single commit OR landing+fixes split: `docs(phase12): Phase 12 Sub-bundle C auto-correct reconciliation writing-plans plan` (+ optional `docs(phase12): Phase 12 Sub-bundle C plan — Codex R1-R<N> fixes`).
8. Return report covers items in §7.

---

## §7 Return report format

```
## Return report — Phase 12 Sub-bundle C writing-plans

### Plan location
`docs/superpowers/plans/<YYYY-MM-DD>-phase12-bundle-C-auto-correct-reconciliation-plan.md` ({line count} lines)
Commits on main:
- {sha} `docs(phase12): Phase 12 Sub-bundle C auto-correct reconciliation writing-plans plan` (initial)
- (optional) {sha} `docs(phase12): Phase 12 Sub-bundle C plan — Codex R1-R<N> fixes` (post-review)

### Codex review history
- R1: {C/M/m findings; verdict; FIXED/ACCEPTED counts}
- R2: ...
- ...
- Final verdict: NO_NEW_CRITICAL_MAJOR

### Three highest-leverage planning decisions
1. ...
2. ...
3. ...

### Per-sub-sub-bundle task count + projected test deltas
- C.A: {N} tasks; +{X}..+{Y} fast tests
- C.B: {N} tasks; +{X}..+{Y} fast tests
- C.C: {N} tasks; +{X}..+{Y} fast tests
- C.D: {N} tasks; +{X}..+{Y} fast tests
- Cumulative: +{X}..+{Y} fast tests; matches §0.4 lesson #1 + spec §12 projection

### §15.2 OQ disposition triage outcomes
[Per-OQ plan-author posture; default-recommendation-accepted vs orchestrator-escalated]

### §15.3 pre-verification outcomes (all 8 + Sub-bundle C brainstorm lesson #5 additions)
[Per-pre-verification: grep result + verbatim shipped surface confirmed OR divergence flagged]

### Brief-vs-shipped-schema deviations flagged (per §14.OQ-11 carry-forward)
- ...

### Sub-sub-bundle dispatch order locked
C.A → C.B → C.C → C.D
With per-bundle cross-bundle pins enumerated

### Operator-witnessed gate plan summary (per §15.5)
- C.A: 4 surfaces
- C.B: 3 surfaces
- C.C: 4 surfaces
- C.D: 10 surfaces (the big one)

### V2 candidates banked (per §2.6)
- ...

### Open questions for orchestrator triage (if any escalated past spec §14)
- ...

### Forward-binding lessons for executing-plans dispatches (per §15.4)
- ...
```

---

## §8 If you get stuck

- If spec §1.3 binding constraints conflict with a planning approach, §1.3 wins; flag as open question.
- If a Codex round produces a finding you can't disposition without orchestrator input, ACCEPT-with-rationale + flag explicitly in plan's "open questions" section + return report.
- If the plan exceeds ~2900 lines, re-scope OR split into multiple plan files (one per sub-sub-bundle).
- DO NOT propose mapper widening within Sub-bundle C scope (§0.6 lock).
- DO NOT propose fill auto-population at trade-entry within Sub-bundle C scope (spec §13 lock).
- DO NOT propose web Tier-2 surface within Sub-bundle C scope (OQ-3 lock).
- If you encounter a Phase 7/8/9/10/11/12-A/12-B brainstorm lesson that conflicts with a Sub-bundle C planning proposal, the prior-phase lesson wins (validated by ship-experience). Surface the conflict as a planning constraint.
- If you find yourself proposing a magnitude-based threshold, STOP — §1.1 lock #3 violated.
