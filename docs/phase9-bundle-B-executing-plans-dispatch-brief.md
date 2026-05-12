# Phase 9 Sub-bundle B — executing-plans dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Sub-bundle B (reconciliation depth) of the Phase 9 implementation plan via `copowers:executing-plans`. Plan is `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` §E (lines 1516+; 9 tasks T-B.0 … T-B.8). All per-task acceptance criteria + tests + commit shapes are in the plan; this dispatch brief is a worktree-config + scope wrapper + a small set of brief-side corrections informed by Sub-bundle A's landing, NOT a duplicate spec.

**Expected duration:** ~14-18 hr implementation + ~1.5-3 hr Codex convergence. Total ~15-21 hr. Sub-bundle B is the second-largest sub-bundle (lots of reconciliation discrepancy detection + tos_import refactor + CLI surface), but the schema was already landed atomically in T-A.1 so the surface explored here is narrower than Sub-bundle A's foundation work.

**Skill posture:**
- Invoke `copowers:executing-plans` against the plan path scoped to Sub-bundle B (`PLAN_PATH=docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md`, `SCOPE=Sub-bundle B (T-B.0..T-B.8 only)`).
- The skill wraps `superpowers:subagent-driven-development` + adversarial Codex review.
- Adversarial review runs after all 9 tasks land. Expected **3-4 Codex rounds** (per Sub-bundle A return report §10 hand-off note: "consumer-side bundles should converge faster than Sub-bundle A's 5-round schema-foundation chain").

---

## §0 Inputs

### §0.1 Plan
- **PLAN_PATH:** `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` (2257 lines; Codex R5 confirmation; LOCKED at `a0c7223`).
- **Sub-bundle B section:** §E (lines 1516-1776). Self-contained per-task spec with TDD checkboxes (`- [ ]`).
- **Plan §A resolved-during-planning items:** lines 13-216 — several BINDING for Sub-bundle B (§A.2 reconciliation-service module placement + tos_import.py refactor scope; §A.2.1 failure-path preservation semantics; §A.2.2 CLI rename + alias; §A.8 NO `INSERT OR REPLACE`; §A.10 server-stamping discipline).
- **Plan §B file-map:** lines 218-282. Enumerates new files for Sub-bundle B (`swing/data/repos/reconciliation.py`, `swing/trades/reconciliation.py`, + tests + fixture CSVs).
- **Plan §C decomposition (line 290):** Sub-bundle B depends on Sub-bundle A (migration landed; risk_policy + reconciliation_runs + reconciliation_discrepancies tables exist). NO migration edits in Bundle B.
- **Plan §I watch items (lines 2116-2140):** cross-bundle invariants the executing-plans dispatcher MUST verify (items 1-13 all apply; items 3, 5, 6, 7, 10, 11 are Bundle-B-specific bindings).

### §0.2 Spec
- **SPEC_PATH:** `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` (1090 lines; LOCKED at `31ee51c`).
- **Read for §3.2 reconciliation_runs column list (BINDING — 19 columns; see §0.5 #1 below for the brainstorm-miscount correction).**
- **Read §3.3 reconciliation_discrepancies column list (BINDING — 19 columns; see §0.5 #1).**
- **Read §3.3.1 expected_value / actual_value JSON shapes per discrepancy type (BINDING — emitter must produce these shapes).**
- **Read §3.3.2 material_to_review classification + operator-override semantics.**
- **Read §3.3.3 single-transaction emit (BINDING — failure-path preservation; see §0.5 #3).**
- **Read §4.2 reconciliation cadence + CLI semantics.**
- **Read §5.1 canonical queries for active-trade alerts + closed-trade re-review attention (BINDING — Bundle B's `list_unresolved_material_for_active_trades` + `list_unresolved_material_for_closed_trades`).**
- **Read §6.1–§6.5 discrepancy-detection details + tos_import.py refactor target.**

### §0.3 Project state at dispatch time
- **HEAD on `main`:** `de10601` at brief-commit time (post-Sub-bundle-A-merge + housekeeping + gotcha promotions). After this brief commits, the worktree-branching-point is the brief commit SHA.
- **Test count:** **2462 fast (1 skipped); 3 pre-existing failures** on `tests/integration/test_phase8_pipeline_walkthrough.py` ("archive returned None"). NOT regressions; NOT Bundle-B-introduced. Banked for separate triage.
- **Ruff baseline:** **18 (E501 only).** Unchanged from Sub-bundle A baseline.
- **Schema version:** **v17 (Phase 9 Sub-bundle A migration landed in production at 2026-05-12T08:18:10Z).** Production DB at `%USERPROFILE%/swing-data/swing.db` already has all 5 Phase 9 tables + 2 ALTER ADD columns + risk_policy seed + hypothesis_status_history seed rows + indexes. Sub-bundle B does NOT bump the schema_version.
- **Active risk_policy:** `policy_id=4` (max_account_risk_per_trade_pct=0.75 inherited from S3 test; capital_floor_constant_dollars=7500 reverted from S2.bis test). Sub-bundle B tests SHOULD NOT depend on a specific policy_id; instead query `read_active_policy(conn)` from `swing/trades/risk_policy.py` (the canonical service-layer entry point).
- **Worktree husks pending operator cleanup-script:** 4 (3e8-bundle-3 + phase9-bundle-A + phase9-writing-plans + polish-2026-05-10). Does NOT block dispatch.

### §0.4 Sub-bundle B scope (9 tasks)

Per plan §C decomposition table + §E detail:

| Task | Title | Key files |
|---|---|---|
| **T-B.0** | Consumer-side schema verification (reconciliation_runs + reconciliation_discrepancies present at v17; FK CASCADE + FK SET NULL behaviors; CHECK enums) | NEW `tests/data/test_phase9_reconciliation_schema_verification.py` |
| **T-B.1** | Reconciliation dataclasses + repo (CRUD + two-read pattern + canonical queries) | MODIFY `swing/data/models.py` (add `ReconciliationRun`, `ReconciliationDiscrepancy` dataclasses); NEW `swing/data/repos/reconciliation.py` + tests |
| **T-B.2** | TOS-import refactor — extract emitter seam (preserves `ReconciliationReport` return shape) | MODIFY `swing/journal/tos_import.py` + tests |
| **T-B.3** | TOS-import extension — `close_price_mismatch` + `entry_price_mismatch` detection (per spec §6.1) | MODIFY `swing/journal/tos_import.py` + tests + fixture CSVs |
| **T-B.4** | TOS-import extension — `stop_mismatch` detection (Account Order History parsing per spec §6.2) | MODIFY `swing/journal/tos_import.py` + tests + fixture CSVs |
| **T-B.5** | TOS-import extension — `position_qty_mismatch` detection (Equities section parsing per spec §6.3) | MODIFY `swing/journal/tos_import.py` + tests + fixture CSVs |
| **T-B.6** | TOS-import extension — `cash_movement_mismatch` + service orchestration (`swing/trades/reconciliation.py`) | MODIFY `swing/journal/tos_import.py`; NEW `swing/trades/reconciliation.py` + tests |
| **T-B.7** | CLI surface — `swing journal reconcile-tos` (RENAME from `import-tos` + deprecation alias) + `swing journal discrepancy {list,show,resolve}` group | MODIFY `swing/cli.py` + tests |
| **T-B.8** | E2E reconciliation integration test | NEW `tests/integration/test_phase9_end_to_end.py` (Bundle-B scope) |

**Cross-bundle dependencies:** depends on Sub-bundle A (migration landed; risk_policy + reconciliation_runs + reconciliation_discrepancies tables exist). Independent of Sub-bundles C/D/E. NO MIGRATION EDITS.

### §0.5 BINDING contracts from plan §A + Sub-bundle A landing (DO NOT re-litigate)

1. **Column counts — CORRECTED FROM PLAN TEXT.** Plan §B file map + §E task acceptance criteria use stale brainstorm-miscount subtotals "17 cols" for reconciliation_runs and "18 cols" for reconciliation_discrepancies. **Migration 0017 actually creates 19 cols + 19 cols** (verified by reading `swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql` at branch HEAD). The column LIST is the binding artifact; the subtotals are wrong. **T-B.0 schema verification tests MUST assert 19 + 19, NOT 17 + 18.** Banked from Sub-bundle A return report §7 item #6. Pattern complement to Sub-bundle A's risk_policy 28-vs-34 reconciliation.

2. **Migration 0017 is LOCKED + FROZEN.** Sub-bundle B DOES NOT modify it. All 5 new tables + 2 ALTER ADDs + all indexes + all seed rows are in place at branch HEAD. `EXPECTED_SCHEMA_VERSION = 17` is in `swing/data/db.py`. Sub-bundle B ships repo + service + CLI on top of the existing schema. Discriminating watch item: brief reviewer MUST run `grep -rn "^EXPECTED_SCHEMA_VERSION" swing/data/db.py` + verify it still returns `EXPECTED_SCHEMA_VERSION = 17` at branch HEAD post-Bundle-B; if any task accidentally bumps it to 18, that's a Critical Codex finding.

3. **Reconciliation failure-path PRESERVES the run row + UPDATEs `state='failed'`** (NOT rollback-new-row). Per spec §3.3.3 + plan §A.2.1. The failure-path catches the exception INSIDE the same outer transaction; UPDATEs the existing reconciliation_runs row's `state='failed', finished_ts=now, error_message=str(e)`; emits a COMMIT. Discrepancies + cash_movements + fills inline-inserted PRIOR to the failure are PRESERVED (audit-trail integrity prioritized over rollback purity). Discriminating regression test (T-B.6, plan §E Step 16): inject a synthetic exception AFTER emitter has fired for ≥1 discrepancy; assert (a) reconciliation_runs row PRESENT with `state='failed'` (NOT absent), (b) `error_message` populated, (c) discrepancies emitted prior to failure ARE PRESERVED, (d) `conn.in_transaction == False` post-call.

4. **Reconciliation service follows Phase 7+8 transactional discipline (reject caller-held tx; own BEGIN IMMEDIATE / COMMIT / ROLLBACK; reject-don't-auto-detect).** Per the `in_transaction` anti-pattern lesson codified at Sub-bundle A's `supersede_active_policy` + `seed_initial_policy` (canonical examples in `swing/trades/risk_policy.py`). New service `swing/trades/reconciliation.py:run_tos_reconciliation` MUST raise `CallerHeldTransactionError` (or equivalent — mirror Sub-bundle A's naming) at entry if `conn.in_transaction == True`. Discriminating regression test asserts the rejection.

5. **CLI rename: `swing journal import-tos` → `swing journal reconcile-tos`; V1 deprecation alias retained; alias removed in V2.** Per plan §A.2.2 + spec §4.2 wording. The deprecation alias prints a stderr WARNING ("deprecated; use `swing journal reconcile-tos` instead") + dispatches to the new service. Discriminating test (plan T-B.7) verifies BOTH invocations route to the same service.

6. **`tos_import.py` refactor preserves the existing `ReconciliationReport` dataclass return shape.** Existing CLI consumers (`swing journal import-tos`) MUST work unchanged during transition. Per plan §A.2 + T-B.2 acceptance criteria. The refactored signature: `def reconcile_tos(conn, csv_text, *, run_id: int | None = None, emitter: Callable[..., int] | None = None) -> ReconciliationReport`. When `run_id` + `emitter` are None, behavior matches pre-refactor (regression-clean). When provided, each detected discrepancy is forwarded via `emitter(discrepancy_type=<type>, ..., run_id=run_id) -> int` (returning the inserted discrepancy_id).

7. **5 new discrepancy types beyond the 5 already in the CHECK enum:**
   - **NEW in B:** `close_price_mismatch` (T-B.3), `entry_price_mismatch` (T-B.3), `stop_mismatch` (T-B.4), `position_qty_mismatch` (T-B.5), `cash_movement_mismatch` (T-B.6).
   - **Pre-existing in CHECK enum:** `sector_tamper` (Bundle D), `snapshot_mismatch` (Bundle C territory), plus 3 reserved (verify via `grep "CHECK (discrepancy_type IN" swing/data/migrations/0017_*.sql` at worktree branching point).
   - Bundle B emits the 5 NEW types. The CHECK enum is already in place; Bundle B's emitter MUST produce exactly these type strings (spelled identically; trailing `_mismatch` suffix per spec §3.3 + §6.1-§6.4).

8. **`material_to_review` classification at INSERT time via `MATERIAL_BY_TYPE` lookup + operator-override.** Per spec §3.3.2 + plan T-B.6. Constant `MATERIAL_BY_TYPE: dict[str, int]` lives in `swing/trades/reconciliation.py` with 10 entries (the 5 NEW + 5 pre-existing types). Emitter consults the lookup at INSERT time; CLI `swing journal discrepancy resolve` allows operator override per spec §3.3.2 (V1 allows `--material 0/1` override flag). Discriminating tests verify (a) emitter writes correct `material_to_review` from lookup; (b) CLI resolve with `--material` override updates the row.

9. **Within-run dedup via in-memory set (per spec §5.1 R3 Major #4 fix).** Per plan T-B.6 acceptance criteria. The emitter MUST track `(trade_id, discrepancy_type, field_name)` tuples within a single reconciliation_run + skip duplicates. Cross-run dedup is explicitly NOT done (re-running reconciliation is a legitimate audit workflow). Discriminating test: a CSV that would emit two identical discrepancies in one run produces exactly one row in reconciliation_discrepancies.

10. **`source_artifact_sha256` computed at run-start** (plan T-B.6). Read the CSV file, SHA256 the bytes, store the hex digest in `reconciliation_runs.source_artifact_sha256`. The `count_runs_for_artifact_sha256(conn, sha256)` advisory (plan T-B.1) enables re-run detection but does NOT auto-skip — operator decides.

11. **`price_tolerance` LOCKED for V1 at 0.01 USD (default `reconcile_tos` parameter at `swing/journal/tos_import.py:326`).** Per plan T-B.3 Codex R2 Major #3 fix. NO new cfg field added in Phase 9. NO `risk_policy.scratch_epsilon_R * entry_price` derivation in V1 (scratch_epsilon is R-unit threshold for win/loss classification, NOT price-tolerance dollars). Strict greater-than convention at `swing/journal/tos_import.py:365` preserved: exact match (delta = 0) → no emit; within tolerance (delta = 0.005) → no emit; at boundary (delta = 0.01) → no emit; outside tolerance (delta = 0.02) → emit. Same convention applies to `stop_mismatch` (T-B.4).

12. **Bundle D's `sector_tamper` emission is SEPARATE from Bundle B's service.** Bundle B introduces `run_tos_reconciliation` for TOS-CSV reconciliation; Bundle D's ad-hoc `system_audit` reconciliation_run for sector/industry tamper rejection is a SEPARATE call site (separate transaction; emits via the repo `insert_run` + `insert_discrepancy` directly, NOT through the new service). Bundle B's service ONLY handles `source='tos_csv'` runs. Discriminating watch item: brief reviewer confirms that `swing/trades/reconciliation.py:run_tos_reconciliation` does NOT contain any sector/industry logic.

13. **NO `INSERT OR REPLACE` anywhere in Bundle B.** Plan §A.8 baseline. Reconciliation `resolution` UPDATE on existing rows uses UPDATE only. Run row UPDATE-to-completed / UPDATE-to-failed uses UPDATE only. Discriminating watch item: `grep -rn "INSERT OR REPLACE\|REPLACE INTO" swing/` post-Bundle-B returns zero matches.

14. **Repo functions do NOT call `conn.commit()`** (Finviz I1 lesson — codified in plan §I item #5). Caller controls transaction scope. New `swing/data/repos/reconciliation.py` follows the convention. Discriminating watch item: `grep -rn "conn.commit()" swing/data/repos/reconciliation.py` returns zero matches.

15. **`__post_init__` validators on `ReconciliationRun` + `ReconciliationDiscrepancy` dataclasses.** Per plan §I item #7 + Bundle 2/3 pattern. Reject NaN/inf on REAL fields; reject invalid enum values for `state` (running / completed / failed) + `discrepancy_type` + `resolution`; reject `finished_ts < started_ts` when both non-NULL. Discriminating tests in `tests/data/test_reconciliation_repo.py` verify each rejection path.

16. **No new HTMX form-driven surfaces in Bundle B.** Bundle B is CLI + service + repo only. The V2-deferred web form for reconciliation runs is Phase 10+ territory per spec §11.2. Phase 5 HTMX gotchas (HX-Request propagation + HX-Redirect success-path) are NOT relevant for Bundle B.

17. **Server-stamping discipline preserved at CLI handler entry** (per plan §A.10): `reconciliation_runs.started_ts` + `finished_ts` server-stamped; `reconciliation_runs.period_end` operator-supplied OR derived from last-fill-date; `reconciliation_discrepancies.created_at` + `resolved_at` server-stamped; `resolved_by='operator'` hardcoded V1. NO hidden form inputs in CLI (CLI is always operator-trusted; the server-stamping discipline carries forward as design hygiene, not adversarial defense).

### §0.6 Sub-bundle A landed surface (FORWARD-BOUND)

Sub-bundle A merged at `6c8f3a9` + housekeeping at `2219ab5` + handoff brief at `b3cab6c` + gotcha promotions at `de10601`. Sub-bundle B builds on:

- **`swing/trades/risk_policy.py` canonical service-layer entry points:** `supersede_active_policy`, `read_active_policy`, `seed_initial_policy`, `ratify_seed_from_cfg_on_v17_landing`, `check_and_reconcile_toml_divergence`. Use these (or the repo CRUD in `swing/data/repos/risk_policy.py`) rather than direct SQL.
- **`swing/data/datetime_helpers.py:now_ms` + `validate_ms_iso`.** New reconciliation service + repo + dataclasses use `now_ms()` for all server-stamped TEXT datetime columns. Per plan §A.11 + Sub-bundle A T-A.0.
- **`CallerHeldTransactionError`** (or equivalent — verify exact name at `swing/trades/risk_policy.py`). Bundle B's reconciliation service mirrors this exception type.
- **`tests/conftest.py` test fixtures** that establish a v17 DB with seed policy + seed hypothesis_status_history rows. Bundle B tests inherit these fixtures.

### §0.7 Sub-bundle A lessons FORWARD-BINDING

Per Sub-bundle A return report §7 watch items + §11 operator-side action items + CLAUDE.md gotcha promotions banked at `de10601`:

- **CLAUDE.md gotcha (NEW 2026-05-12): Phase 9 ratification helper single-fire semantics.** Not directly invoked in Bundle B, but Bundle B tests MUST NOT call `ratify_seed_from_cfg_on_v17_landing` from inside test setup (it's single-fire; Sub-bundle A tests already exercise it). If a Bundle B test fixture needs a fresh policy, use `seed_initial_policy(conn, cfg)` (idempotent — no-ops if active policy exists).
- **CLAUDE.md gotcha (NEW 2026-05-12): All four cascade emitters MUST do no-op-skip check.** Bundle B does NOT add a new cascade emitter (no new TOML mirror surface). If any Bundle B task accidentally adds one, brief reviewer flags as a Codex Critical.
- **CLAUDE.md gotcha (NEW 2026-05-12): Tests exercising `write_user_overrides` MUST monkeypatch USERPROFILE + HOME.** Bundle B tests that invoke any CLI that touches the cfg-cascade path (mostly Bundle B does NOT — but if T-B.7 CLI tests touch a path that calls `apply_overrides()`, this applies). Defensive: if any Bundle B test uses `subprocess.run(["swing", ...])` or invokes the CLI runner against a tmp-DB, ALWAYS `monkeypatch.setenv("USERPROFILE", str(tmp))` AND `monkeypatch.setenv("HOME", str(tmp))` before invocation.
- **Orchestrator-context lesson (NEW 2026-05-12): Production-write classifier soft-block under auto-mode.** When the operator-witnessed gate (§3 below) invokes a production write — `swing journal reconcile-tos --csv-path <real-data>` — the classifier may soft-block. Workaround: orchestrator surfaces back to operator + requests plain-chat "yes" confirmation. Implementer does NOT encounter this (runs in worktree against fixture CSVs).
- **Orchestrator-context lesson (NEW 2026-05-12): `tomli_w.dump` comment-stripping.** Not relevant for Bundle B's scope (no TOML writes).

### §0.8 Bundle 2+3 + Sub-bundle A lessons FORWARD-BINDING

Per the 9-lesson catalog at `docs/phase9-writing-plans-dispatch-brief.md` §0.3 + §7 + Sub-bundle A's confirmed-relevant subset:

- **`__post_init__` validator pattern** for `ReconciliationRun` + `ReconciliationDiscrepancy` dataclasses (mirrors Bundle 2 R3 Major #1 NaN/inf/out-of-range rejection + Sub-bundle A's `RiskPolicy` validator).
- **Service-layer transaction discipline** — Bundle B's `run_tos_reconciliation` rejects caller-held tx, owns BEGIN IMMEDIATE / COMMIT / ROLLBACK, mirrors Sub-bundle A's `supersede_active_policy` contract.
- **NO `INSERT OR REPLACE`** on `reconciliation_discrepancies` resolution UPDATE or `reconciliation_runs` UPDATE-to-completed (Phase 8 gotcha 2026-05-06; plan §A.8 baseline).
- **Server-stamping at CLI handler entry** — Bundle B server-stamps `started_ts`, `finished_ts`, `created_at`, `resolved_at`, `resolved_by` per §A.10.
- **Composition-surface enumeration via `^def` grep, not memory-enumerate.** Per Bundle 3 V2 lesson banked 2026-05-11. Each new service function has its call sites enumerated via `grep -rn "^def run_tos_reconciliation\|^def resolve_discrepancy" swing/` (returns exactly one match per function — the definition; brief reviewer cross-references against any call sites mentioned in plan text).
- **Empirical-verification of brief assertions about column-vs-derived state.** This brief's §0.5 #1 corrected the plan's 17/18 column counts to actual 19/19 — implementer MUST verify by running the schema-verification PRAGMA query at T-B.0 BEFORE writing the test assertion target.

---

## §1 Worktree + binding conventions

### §1.1 Worktree
- **Branch:** `phase9-bundle-B-reconciliation-depth`
- **Worktree directory:** `.worktrees/phase9-bundle-B-reconciliation-depth/` (project convention per CLAUDE.md + Sub-bundle A precedent; matches cleanup-locked-scratch-dirs.ps1 target).
- **BASELINE_SHA:** `de10601` (post-Sub-bundle-A-merge + housekeeping + handoff brief + gotcha promotions; the HEAD of main BEFORE this brief commits).
- **Worktree branching point:** current HEAD of `main` at worktree-creation time (resolve via `git rev-parse main`; expected the dispatch-brief commit SHA after this brief lands).
- The Codex diff (`de10601` → worktree HEAD) will include one doc-only commit (this dispatch brief). Harmless; Codex evaluates the IMPLEMENTATION against the PLAN scoped to Sub-bundle B.

### §1.2 Marker-file workflow
- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all 9 tasks land + tests GREEN + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits
- Conventional prefix:
  - `test(data): T-B.0 — <description>` for schema-verification test (test-only commit)
  - `feat(data): T-B.1 — <description>` for dataclasses + repo
  - `refactor(journal): T-B.2 — <description>` for tos_import emitter seam
  - `feat(journal): T-B.3/B.4/B.5 — <description>` for discrepancy-detection extensions
  - `feat(trades): T-B.6 — <description>` for service orchestration + cash_movement_mismatch
  - `feat(cli): T-B.7 — <description>` for CLI surface
  - `test(integration): T-B.8 — <description>` for E2E test (test-only commit)
  - `fix(area): Codex RN Major #X (internal) — <description>` for Codex-driven fixes
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.
- **TDD:** failing test first, minimal implementation, pass, commit. Per-task `- [ ]` checkboxes in plan §E mark per-step boundaries.
- **Prefer `git add <specific-files>` over `git add -A`** — Phase 8 R1 Critical 1 lesson banked 2026-05-07. Stray files like `.copowers-subagent-active` MUST NOT be staged. Never use `git add -A` or `git add .`.

### §1.4 Branch isolation + ownership
- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** task-family TDD commits → marker-file removal → adversarial-critic → return report.
- **Operator owns:** witnessed verification gate (§3 surfaces below).
- **Orchestrator owns:** integration merge to main + post-merge housekeeping + Sub-bundle C dispatch commissioning.

### §1.5 Verify command
PowerShell from inside worktree (per Phase 5 editable-install lesson 2026-05-02 + Sub-bundle A precedent):
```powershell
$env:PYTHONPATH = "."; python -m swing.cli web
```
(Bundle B has no web surface — verify command only needed if implementer wants to exercise existing routes against a worktree copy for any sanity check. Pytest from worktree works without the PYTHONPATH prefix because pytest uses cwd-based discovery.)

---

## §2 Adversarial review (Codex)

### §2.1 Setup (IMPLEMENTER runs this)

After ALL 9 task-family commits land + tests GREEN at branch HEAD:

1. `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
2. Invoke `copowers:adversarial-critic` with:
   - `PHASE`: `phase9-bundle-B-reconciliation-depth`
   - `SPEC_PATH`: `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md`
   - `PLAN_PATH`: `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` (Codex scopes to §E Sub-bundle B; rest of plan is informational context)
   - `BASELINE_SHA`: `de10601`
3. Iterate rounds until **NO_NEW_CRITICAL_MAJOR**.
4. Per-round fixes commit as `fix(area): Codex RN Major #X (internal) — <description>`.
5. Expected convergence: **3-4 rounds** (per Sub-bundle A return report §10 hand-off note: consumer-side bundles converge faster than schema-foundation chains).

### §2.2 Codex value-add concentration

Adversarial review for Sub-bundle B typically catches:
- **Failure-path semantics drift** — if `run_tos_reconciliation` accidentally rolls back the run row on exception instead of UPDATEing state='failed', Codex flags as Critical (spec §3.3.3 + plan §A.2.1 binding).
- **Caller-held-transaction rejection missing** — discriminating test must exist for `run_tos_reconciliation` + `resolve_discrepancy`.
- **`__post_init__` validator gaps** — NaN/inf rejection + enum validation + `finished_ts >= started_ts` cross-field.
- **Within-run dedup gap** — if the emitter doesn't track `(trade_id, type, field_name)` tuples, duplicate runs against the same fixture CSV produce >1 row per discrepancy.
- **Boundary-condition gap on price_tolerance** — strict-greater-than vs greater-than-or-equal-to off-by-one.
- **MATERIAL_BY_TYPE lookup gap** — if a new type is added without updating the lookup, the emitter writes `material_to_review=NULL` instead of the spec-correct value.
- **CLI alias deprecation warning gap** — if `swing journal import-tos` doesn't print stderr WARNING, the V1 backwards-compatibility path silently succeeds without the operator-visible signal.
- **Two-read pattern gap on `list_recent_runs`** — if the query order-by leaks the in-flight `started_ts DESC` row when `finished_ts IS NULL`, the dashboard "last completed" timestamp shows NULL (CLAUDE.md gotcha; banked 2026-04 era).
- **`sha256` empty-file edge case** — empty CSV produces hex `e3b0c44298fc...`; advisory + run row should still persist (operator decides re-run); ZeroDivisionError or other crash on empty input is a Major.
- **`expected_value_json` / `actual_value_json` schema drift from spec §3.3.1** — Codex cross-checks JSON shape against spec table per type.

---

## §3 Operator-witnessed verification surfaces

After NO_NEW_CRITICAL_MAJOR. Per plan §E intro (6 surfaces):

- **S1 — Post-A-merge baseline.** Operator confirms current main HEAD includes Sub-bundle A's merge + housekeeping + brief commits. Runs `python -m pytest -m "not slow" -q` from worktree; verifies baseline + Bundle-B-added tests GREEN. Runs `swing config policy show` from worktree; verifies active policy_id (currently 4) prints correctly + 34 fields enumerated.
- **S2 — Consumer-side schema verification.** Operator runs `python -m pytest tests/data/test_phase9_reconciliation_schema_verification.py -v` from worktree; verifies T-B.0 tests PASS against the v17 schema already landed in production. (Implementer-side; operator re-runs as sanity check.)
- **S3 — End-to-end reconcile-tos happy path.** Operator runs `swing journal reconcile-tos --csv-path <sample-csv> --period-end 2026-05-12 --notes "operator gate test"` from worktree; verifies `reconciliation_runs` row persisted with `state='completed'`, summary fields populated, source_artifact_sha256 set. Discrepancy rows persisted for any detected mismatches.
- **S4 — Deliberate-mismatch CSV.** Operator runs reconcile-tos against a fixture CSV with deliberate price/stop/qty mismatches; verifies the discrepancy types are correctly classified (close_price_mismatch + entry_price_mismatch + stop_mismatch + position_qty_mismatch as applicable). Operator runs `swing journal discrepancy list` from worktree; verifies the discrepancy rows enumerate with material_to_review + delta_text + resolution=unresolved.
- **S5 — Discrepancy resolution.** Operator runs `swing journal discrepancy resolve <id> --resolution journal_corrected --reason "verified against tos export"` from worktree; verifies the row's `resolution`, `resolution_reason`, `resolved_at`, `resolved_by` updated. Runs `swing journal discrepancy show <id>` to confirm.
- **S6 — Canonical queries.** Operator runs `swing journal discrepancy list --unresolved --material` from worktree; verifies the active-trade alert set matches `list_unresolved_material_for_active_trades` query semantics per spec §5.1 CANONICAL #1. Same against `list_unresolved_material_for_closed_trades` (spec §5.1 CANONICAL #2) via either CLI flag or repo-direct test.
- **S7 — pytest + ruff.** From worktree: `python -m pytest -m "not slow" -q` GREEN; `ruff check swing/ --statistics` shows ≤18 (no new violations).

**Expected test count delta:** +80 to +120 fast tests (T-B.0..T-B.8; plan §J.3 projection; Sub-bundle A overshoot to +134 vs projection +40-80 suggests Bundle B may also land high; bias toward the high end of range under Codex-driven defensive-hardening).

**Expected ruff baseline:** 18 (no change) or lower if imports clean up.

**Production-write classifier soft-block awareness (per orchestrator-context lesson banked 2026-05-12):** S3-S5 are production writes. If the orchestrator-driven invocation is classifier-blocked, the orchestrator will surface back to the operator with a plain-chat confirmation request. This does NOT affect the implementer; it's an orchestrator-side gating concern.

---

## §4 Return report shape

After operator-gate PASS, draft return report at `docs/phase9-bundle-B-return-report.md` (mirroring `docs/phase9-bundle-A-return-report.md` shape):

1. Final HEAD on branch.
2. Commit count breakdown (task-impl per T-B.X + Codex-fix + operator-gate-fix).
3. Codex round chain (e.g., "R1 0/X/Y → R2 ... → Rn NO_NEW_CRITICAL_MAJOR").
4. Test count delta + ruff baseline delta.
5. Operator-gate surface results (S1-S7).
6. Per-task deviations from the plan (if any; the plan §E text has known column-count drift §0.5 #1 above + any other discoveries during dispatch).
7. Codex Major findings ACCEPTED with rationale (target: zero, matching Sub-bundle A's discipline + Phase 9 writing-plans precedent).
8. Watch items surfaced but not acted on (for Sub-bundles C/D/E to absorb OR for orchestrator-context capture).
9. Worktree teardown status (expected ACL-locked husk).
10. Composition-surface verification: enumerate the new service functions + their call sites; verify the `^def` grep returns exactly one match per function definition.

Forward-looking notes for Sub-bundle C dispatch (one extra section relative to Sub-bundle A's report):
11. **Hand-off notes for Sub-bundle C:** confirm reconciliation_runs + reconciliation_discrepancies are consumed correctly; flag any service-layer contracts (`MATERIAL_BY_TYPE`, `DISCREPANCY_TYPES`, etc.) that Bundle C/D might import or override; confirm `swing/trades/hypothesis.py` placement decision (NEW module per plan §A.1) is unchanged by Bundle B work.

---

## §5 First-step paste-ready prompt for the implementer

```
You are taking over as implementer for the swing-trading phase9-bundle-B-reconciliation-depth dispatch.

WORKING DIRECTORY (after worktree creation): c:\Users\rwsmy\swing-trading\.worktrees\phase9-bundle-B-reconciliation-depth
BRANCH: phase9-bundle-B-reconciliation-depth
BASELINE_SHA: de10601  (per dispatch brief §1.1; HEAD of main BEFORE this brief commit; post-Sub-bundle-A-merge + housekeeping + gotcha promotions)
WORKTREE-BRANCHING-POINT: current HEAD of main at worktree-creation time (resolve via `git rev-parse main`)

The Codex diff (de10601 → worktree HEAD) will include one doc-only commit (this dispatch brief). Harmless; Codex evaluates the IMPLEMENTATION against the PLAN scoped to Sub-bundle B.

Step 0 — Create the worktree:
  cd c:\Users\rwsmy\swing-trading
  $base = git rev-parse main
  git worktree add .worktrees\phase9-bundle-B-reconciliation-depth -b phase9-bundle-B-reconciliation-depth $base
  New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active

Step 1 — Read the dispatch brief end-to-end from the worktree:
  docs/phase9-bundle-B-executing-plans-dispatch-brief.md

Step 2 — Read the plan §A (resolved-during-planning, lines 13-216) + §B (file map, lines 218-282) + §C (decomposition, lines 284-302) + §E (Sub-bundle B, lines 1516-1776) end-to-end:
  docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md
  Skim §I (cross-bundle invariants, lines 2116-2140) + §J.2 (grep-verification commands, lines 2192-2225) for executing-plans acceptance gate.

Step 3 — Read the spec (focus on §3.2 + §3.3 column lists; §3.3.1 JSON shapes per type; §3.3.2 material classification; §3.3.3 single-transaction emit; §4.2 cadence + CLI; §5.1 canonical queries; §6.1-§6.5 discrepancy-detection details):
  docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md

Step 4 — Read binding conventions + Sub-bundle A landing:
  - CLAUDE.md (gotchas + project conventions; 3 NEW gotchas from Sub-bundle A landing at de10601 are forward-binding for Bundle B)
  - docs/orchestrator-context.md (orchestrator-role framing; binding conventions; 2 NEW lessons from Sub-bundle A landing at de10601)
  - docs/phase9-bundle-A-return-report.md (§7 watch items + §10 hand-off notes — Sub-bundle A's service-layer canonical entry points + transactional-discipline contracts FORWARD-BIND to Bundle B)
  - docs/phase9-writing-plans-dispatch-brief.md §0.3 + §7 (9-lesson catalog FORWARD-BINDING)

Step 5 — Verify worktree state:
  git rev-parse HEAD                                          # expect current main HEAD (typically the dispatch brief commit)
  git status                                                  # expect clean
  python -m pytest -m "not slow" -q                           # expect baseline GREEN (2462 passed, 1 skipped; 3 pre-existing fails NOT regressions)
  python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"   # expect 17

Step 6 — Pre-implementation grep recon (Bundle 2+3 lesson applied + Sub-bundle A confirmed):
  grep -rn "^def " swing/data/repos/                          # enumerate existing repo patterns (especially swing/data/repos/risk_policy.py — your transactional template)
  grep -rn "with conn:" swing/trades/                         # enumerate existing transactional services (do NOT call from inside outer txn)
  grep -rn "INSERT OR REPLACE\|REPLACE INTO" swing/           # confirm zero usage (plan §A.8 baseline)
  grep -rn "conn.commit()" swing/data/repos/                  # confirm zero usage (Finviz I1 lesson — your repo MUST inherit)
  grep -rn "CallerHeldTransactionError\|in_transaction" swing/trades/risk_policy.py    # locate Sub-bundle A's transactional-rejection pattern to mirror
  grep -A 50 "CREATE TABLE reconciliation_runs" swing/data/migrations/0017_*.sql      # verify 19-column count for T-B.0 assertion target (NOT plan's stale 17)
  grep -A 50 "CREATE TABLE reconciliation_discrepancies" swing/data/migrations/0017_*.sql  # verify 19-column count (NOT plan's stale 18)
  ls swing/data/migrations/                                   # confirm 0017 present + no 0018 attempt during dispatch (BINDING — Bundle B does NOT modify migrations)
  Capture divergences from plan assumptions; surface in return report §6.

Step 7 — Invoke copowers:executing-plans (the skill wraps superpowers:subagent-driven-development + adversarial Codex review):
  - PHASE: phase9-bundle-B-reconciliation-depth
  - SPEC_PATH: docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md
  - PLAN_PATH: docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md
  - BASELINE_SHA: de10601
  - SCOPE: Sub-bundle B only (tasks T-B.0 through T-B.8 in plan §E); skim §A+§B+§C+§I for context.

Step 8 — TDD per task: failing test → minimal implementation → pass → commit. Per-task `- [ ]` checkboxes in plan §E mark per-step boundaries.

Step 9 — After ALL 9 tasks land + GREEN, run adversarial review per dispatch brief §2.1. Iterate Codex rounds until NO_NEW_CRITICAL_MAJOR. Expected 3-4 rounds.

Step 10 — Draft return report at docs/phase9-bundle-B-return-report.md per dispatch brief §4. Commit it.

Step 11 — Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active + signal orchestrator. Orchestrator drives §3 witnessed verification gate; orchestrator handles integration merge; orchestrator dispatches Sub-bundle C next.

DO NOT:
  - Push to origin from inside the worktree
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer to commits
  - Skip the marker-file removal before invoking copowers
  - Skip the Step 6 pre-implementation grep recon (Bundle 2+3 + Sub-bundle A lesson)
  - Modify migration 0017 in any way (Bundle B is consumer-side only; atomicity BINDING per Sub-bundle A landing)
  - Bump EXPECTED_SCHEMA_VERSION beyond 17 (Bundle B does NOT advance the schema)
  - Add cross-bundle code (no hypothesis_status_history service; no account_equity_snapshots service; no sector_tamper logic in `run_tos_reconciliation` — those are Sub-bundles C/D territory)
  - Add UPDATE schema_version statements
  - Use INSERT OR REPLACE or REPLACE INTO anywhere
  - Call conn.commit() inside new repo functions (caller controls transaction scope)
  - Auto-detect caller-held transactions in new services (reject; don't accommodate)
  - Add new TOML mirror writes (no new cascade emitters in Bundle B; the 4 existing ones are locked at Sub-bundle A)
  - Diverge from plan §A locked decisions without explicit Codex justification
  - Re-litigate spec §3.2/§3.3 schema sketches (LOCKED at brainstorm time; migration 0017 is the binding artifact; column COUNTS are 19/19 NOT plan's stale 17/18)
  - Use `git add -A` or `git add .` (per Phase 8 R1 Critical 1 lesson; stage specific files)
```

---

## §6 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-12 (post-Sub-bundle-A-merge + housekeeping + gotcha promotions).
- **Brief commit:** `<filled-in-after-commit>`.
- **Brief HEAD context:** `de10601` on main (post-Sub-bundle-A-merge + housekeeping + handoff brief + gotcha promotions).
- **Worktree path (binding):** `.worktrees/phase9-bundle-B-reconciliation-depth/`.
- **Baseline test count:** 2462 fast (1 skipped); 3 pre-existing failures on `tests/integration/test_phase8_pipeline_walkthrough.py` NOT regressions.
- **Baseline ruff count:** 18 (E501 only).
- **Plan status:** SHIPPED 2026-05-11 at `a0c7223`; 2257 lines; 30 tasks; Codex R5 confirmation; 17 §A items + 13 §I watch items.
- **Sub-bundle A status:** SHIPPED 2026-05-12 at `6c8f3a9`; 12 commits = 8 task-impl + 4 Codex-fix; 5 Codex rounds NO_NEW_CRITICAL_MAJOR; ZERO Critical findings; 7-surface operator-witnessed gate PASS; production DB at schema_version 17; active policy_id=4.
- **Expected post-dispatch test count:** ~2542-2582 (+80-120; Bundle B is the second-largest sub-bundle; Codex-driven defensive-hardening may push higher per Sub-bundle A's +134 overshoot precedent).
- **Expected post-dispatch ruff count:** 18 (no change).
- **Expected schema version post-Bundle-B:** 17 (UNCHANGED; Bundle B is consumer-side only).
- **Sub-bundle C dispatch dependency:** B's reconciliation service + repo must merge to main + orchestrator-witnessed gate PASS before C can dispatch. Sub-bundle C consumes A's hypothesis_status_history + account_equity_snapshots tables (separate from Bundle B's reconciliation surfaces).
- **Phase 9 arc remaining:** A ✓ → B (this dispatch) → C → D → E. Then Phase 10 writing-plans.
