# Phase 9 Sub-bundle C — executing-plans dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Sub-bundle C (hypothesis_status_history + account_equity_snapshots) of the Phase 9 implementation plan via `copowers:executing-plans`. Plan is `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` §F (lines 1779+; 6 tasks T-C.0 … T-C.5) plus one Sub-bundle C-specific cross-bundle integration task (equity_delta emit wiring into Bundle B's service; see §0.5 #5 below). All per-task acceptance criteria + tests + commit shapes are in the plan; this dispatch brief is a worktree-config + scope wrapper + a small set of brief-side corrections informed by Sub-bundle A + B's landings, NOT a duplicate spec.

**Expected duration:** ~6-9 hr implementation + ~1-2 hr Codex convergence. Total ~7-11 hr. Sub-bundle C is the smallest of the consumer-side bundles — 6 tasks against 2 tables (hypothesis_status_history + account_equity_snapshots) + a cross-bundle equity_delta wiring task on Bundle B's service.

**Skill posture:**
- Invoke `copowers:executing-plans` against the plan path scoped to Sub-bundle C (`PLAN_PATH=docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md`, `SCOPE=Sub-bundle C (T-C.0..T-C.5 + cross-bundle equity_delta wiring per §0.5 #5)`).
- The skill wraps `superpowers:subagent-driven-development` + adversarial Codex review.
- Adversarial review runs after all tasks land. Expected **3-4 Codex rounds** (consumer-side bundle precedent per Sub-bundle B's 5-round chain at slightly larger scope).

---

## §0 Inputs

### §0.1 Plan
- **PLAN_PATH:** `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` (2257 lines; Codex R5 confirmation; LOCKED at `a0c7223`).
- **Sub-bundle C section:** §F (lines 1779-1948). Self-contained per-task spec with TDD checkboxes (`- [ ]`).
- **Plan §A resolved-during-planning items:** lines 13-216 — several BINDING for Sub-bundle C (§A.1 hypothesis-status audit service module placement; §A.1.1 disposition for legacy `update_hypothesis_status`; §A.7 in-flight production hypothesis_registry state; §A.8 NO `INSERT OR REPLACE`; §A.9 session-anchor read/write predicate alignment; §A.10 server-stamping discipline; §A.11 `now_ms` helper).
- **Plan §B file-map:** lines 218-282. Enumerates new files for Sub-bundle C (`swing/data/repos/hypothesis_status_history.py`, `swing/data/repos/account_equity_snapshots.py`, `swing/trades/hypothesis.py`, `swing/trades/account_equity_snapshots.py`, + tests).
- **Plan §C decomposition (line 292):** Sub-bundle C depends on Sub-bundle A (migration landed; hypothesis_status_history seeded; account_equity_snapshots table exists). Independent of Sub-bundle B. NO migration edits.
- **Plan §I watch items (lines 2116-2140):** cross-bundle invariants the executing-plans dispatcher MUST verify (items 1-13 all apply; items 4, 5, 6, 7, 8, 10, 11 are Bundle-C-specific bindings).

### §0.2 Spec
- **SPEC_PATH:** `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` (1090 lines; LOCKED at `31ee51c`).
- **Read for §3.4 hypothesis_status_history column list (7 cols) + §3.4.1 append-on-status-update service semantics (BINDING — single-write-path discipline; noop_identity sentinel; 8-step transactional sequence).**
- **Read §3.5 account_equity_snapshots column list (8 cols) + UPSERT semantics per (snapshot_date, source) + source-ladder precedence (schwab_api > tos_csv > manual) + back-recorded flag.**
- **Read §4.3 hypothesis_status_history append cadence + §4.4 account_equity_snapshots manual cadence.**
- **Read §3.3.1 expected_value/actual_value JSON shape for `equity_delta` discrepancy type (BINDING for the cross-bundle integration in §0.5 #5).**
- **Read §10.4 hypothesis seed effective_from = created_at + §10.6 reconciliation period_end default.**

### §0.3 Project state at dispatch time
- **HEAD on `main`:** `932584a` at brief-commit time (post-Sub-bundle-B-merge `e96834a` + housekeeping). After this brief commits, the worktree-branching-point is the brief commit SHA.
- **Test count:** **2610 fast (1 skipped); 3 pre-existing failures** on `tests/integration/test_phase8_pipeline_walkthrough.py` ("archive returned None"). NOT regressions; NOT Bundle-C-introduced. Banked for separate triage.
- **Ruff baseline:** **18 (E501 only).** Unchanged from Sub-bundle A + B baseline.
- **Schema version:** **v17 (Phase 9 Sub-bundle A migration; consumer-side at v17 since 2026-05-12).** Production DB at `%USERPROFILE%/swing-data/swing.db` already has all 5 Phase 9 tables + 2 ALTER ADD columns + risk_policy seed + hypothesis_status_history seed rows + account_equity_snapshots empty table + indexes. **Sub-bundle C does NOT bump the schema_version.**
- **Active risk_policy:** `policy_id=4` (max_account_risk_per_trade_pct=0.75 inherited from S3 test). Sub-bundle C tests SHOULD NOT depend on a specific policy_id; instead query `read_active_policy(conn)` from `swing/trades/risk_policy.py`.
- **Production reconciliation_runs:** 1 row (run_id=1, state=completed, source=tos_csv) from Sub-bundle B operator-witnessed gate; 5 `acknowledged_immaterial` discrepancies. NOT touched by Bundle C.
- **Production hypothesis_registry:** 4 rows (seeded by migration 0008). Each has a matching hypothesis_status_history row from migration 0017's seed.
- **Production account_equity_snapshots:** 0 rows (operator hasn't recorded any yet). Bundle C's CLI lets operator start.
- **Worktree husks pending operator cleanup-script:** 5 (3e8-bundle-3 + phase9-bundle-A + phase9-bundle-B + phase9-writing-plans + polish-2026-05-10). Does NOT block dispatch.

### §0.4 Sub-bundle C scope (6 plan tasks + 1 cross-bundle integration task)

Per plan §F + the equity_delta cross-bundle integration banked from Sub-bundle B return report §6 + §10 #5:

| Task | Title | Key files |
|---|---|---|
| **T-C.0** | Consumer-side schema verification (hypothesis_status_history + account_equity_snapshots; partial-unique indexes; FK CASCADE on hypothesis_status_history.hypothesis_id → hypothesis_registry.id) | NEW `tests/data/test_phase9_audit_tables_schema_verification.py` |
| **T-C.1** | hypothesis_status_history seed verification (one row per existing hypothesis_registry; effective_to IS NULL; effective_from = strftime('%Y-%m-%dT00:00:00.000', registry.created_at) per spec §3.4.1 R3 Major #2) | NEW `tests/data/test_phase9_hypothesis_seed_verification.py` |
| **T-C.2** | account_equity_snapshots repo + service + CLI (`swing account snapshot --equity --date --notes`; source-ladder precedence; back-recorded flag; SELECT-then-UPDATE-or-INSERT for upsert) | MODIFY `swing/data/models.py`; NEW `swing/data/repos/account_equity_snapshots.py`; NEW `swing/trades/account_equity_snapshots.py`; MODIFY `swing/cli.py` + tests |
| **T-C.3** | hypothesis_status_history repo (insert + update_close_open_interval + get_current_status + list_history_for_hypothesis + list_all_history) | MODIFY `swing/data/models.py`; NEW `swing/data/repos/hypothesis_status_history.py` + tests |
| **T-C.4** | hypothesis status audit service + CLI rewire + DELETE legacy repo function (8-step transactional sequence; noop_identity sentinel; ImportError test post-DELETE) | NEW `swing/trades/hypothesis.py`; MODIFY `swing/data/repos/hypothesis.py` (DELETE `update_hypothesis_status`); MODIFY `swing/cli.py` + tests |
| **T-C.5** | E2E integration test for Sub-bundle C scope (account snapshot + hypothesis status audit + identity transition + back-recorded flag) | MODIFY `tests/integration/test_phase9_end_to_end.py` |
| **T-C.6** **(NEW; cross-bundle from Bundle B §10 #5)** | equity_delta discrepancy emit wiring into Bundle B's `run_tos_reconciliation` | MODIFY `swing/trades/reconciliation.py` (Bundle B file; explicit Sub-bundle C carve-out per plan §10 #5); MODIFY `swing/journal/tos_import.py` (add `extract_account_summary_net_liq` parser for source-side equity); + tests |

**Cross-bundle dependencies:** depends on Sub-bundle A (migration landed; hypothesis_status_history seeded; account_equity_snapshots table exists) + Sub-bundle B (`run_tos_reconciliation` service + `reconciliation_runs.account_equity_*` columns at v17 + `MATERIAL_BY_TYPE["equity_delta"] = 0` constant). Independent of Sub-bundle D/E. **NO migration edits.**

### §0.5 BINDING contracts from plan §A + Sub-bundle A/B landings (DO NOT re-litigate)

1. **Migration 0017 is LOCKED + FROZEN.** Sub-bundle C DOES NOT modify it. All schema columns + indexes + seed rows are in place at branch HEAD. `EXPECTED_SCHEMA_VERSION = 17` is in `swing/data/db.py`. Sub-bundle C ships repo + service + CLI on top. Discriminating watch item: brief reviewer MUST run `grep -E "^EXPECTED_SCHEMA_VERSION" swing/data/db.py` + verify it still returns `17` at branch HEAD post-Bundle-C.

2. **Single-write-path discipline for hypothesis status: DELETE legacy `swing/data/repos/hypothesis.py:update_hypothesis_status`** (per plan §A.1 + §A.1.1). The CLI handler `hypothesis_update_cmd` is rewired in T-C.4 to call the new service `swing/trades/hypothesis.py:update_hypothesis_status_with_audit`. Discriminating regression test (plan T-C.4.2): `with pytest.raises(ImportError): from swing.data.repos.hypothesis import update_hypothesis_status`. The grep `! grep -n "^def update_hypothesis_status" swing/data/repos/hypothesis.py` post-T-C.4 returns success (no match).

3. **Hypothesis service follows Phase 7+8+A+B transactional discipline (reject caller-held tx; own BEGIN IMMEDIATE / COMMIT / ROLLBACK; reject-don't-auto-detect).** Per `swing/trades/risk_policy.py:supersede_active_policy` + `swing/trades/reconciliation.py:run_tos_reconciliation` codified pattern. New service `swing/trades/hypothesis.py:update_hypothesis_status_with_audit` MUST raise `CallerHeldTransactionError` (or equivalent — mirror Bundle B's naming) at entry if `conn.in_transaction == True`. Discriminating regression test asserts the rejection.

4. **NoOpIdentityTransition sentinel** per spec §3.4.1 R3 Minor #1 + plan §A.1 step 4. When `current_status == new_status` AT THE TIME OF LOCK (post-BEGIN IMMEDIATE SELECT), function ROLLBACKs + returns `"noop_identity"` literal. NOT raised as exception. CLI renders as INFO (`info: hypothesis VIR already paused`), NOT ERROR. Discriminating test pattern (plan T-C.4.1): synthetic identity-transition call returns `"noop_identity"` AND no new history row inserted AND no exception raised.

5. **NEW TASK T-C.6 — equity_delta cross-bundle integration with Bundle B's service** (banked from Sub-bundle B return report §6 + §10 #5). Bundle C wires the equity_delta discrepancy emit into Bundle B's `run_tos_reconciliation` service after T-C.2's account_equity_snapshots service is available. Specifically:

   - Add `extract_account_summary_net_liq(csv_text) -> float | None` to `swing/journal/tos_import.py`. Parses the TOS Account Summary section's net-liq column (per spec §3.5 + observation from operator's real-world export `thinkorswim/2026-05-12-AccountStatement.csv` "Account Summary" section).
   - Inside `swing/trades/reconciliation.py:run_tos_reconciliation`, AFTER the existing emitter loop + BEFORE `update_run_completed`: compute (a) source-side equity from `extract_account_summary_net_liq`, (b) journal-side equity from `account_equity_snapshots.get_latest_snapshot_on_or_before(period_end)`. If BOTH available, populate `account_equity_journal_dollars` + `account_equity_source_dollars` + `equity_delta_dollars = source - journal` on the `update_run_completed` call. If `abs(equity_delta_dollars) > <threshold>`, EMIT `equity_delta` discrepancy via the existing emitter (single row per run; run-grain).
   - **Threshold:** Bundle C-locked at `$10.00` (the cleanest round-number that exceeds typical accrued-interest + nominal fee variance; operator override path via CLI `--equity-delta-threshold` flag deferred to V2). Discriminating boundary test: `delta = $9.99` → NO emit; `delta = $10.00` → NO emit (strict greater-than per existing Bundle B convention); `delta = $10.01` → EMIT.
   - **Tests:** new `tests/journal/test_account_summary_net_liq_extraction.py` (parser correctness; missing-section returns None; numeric format variants) + extend `tests/trades/test_reconciliation_service.py` with `test_equity_delta_emit_when_both_sides_available` + `test_equity_delta_not_emit_when_journal_missing` + `test_equity_delta_boundary_at_threshold`.
   - **Bundle B's existing tests** MUST continue to pass — equity_delta path is additive; non-equity-equipped fixtures + the operator's real-world export (which lacks a recorded snapshot) MUST NOT emit equity_delta discrepancies. Discriminating regression test: re-run Bundle B's test_phase9_end_to_end with no account_equity_snapshots present + assert exactly 4 discrepancies (Bundle B's 4 types) + zero equity_delta rows.

6. **Account-equity-snapshots service follows transactional discipline.** New service `swing/trades/account_equity_snapshots.py:record_snapshot` MUST reject caller-held tx + own BEGIN IMMEDIATE / COMMIT / ROLLBACK. Defaults `snapshot_date` to `last_completed_session(now())` per plan §A.9 (backward-looking; mirror of weather lookup writer-side discipline). Discriminating Saturday-night test (plan T-C.2 step 16): invoke `swing account snapshot --equity 1300` with frozen-time Saturday evening; assert `snapshot_date` resolved to Friday's date.

7. **Source-ladder precedence on `get_latest_snapshot_on_or_before` (per spec §3.5 + plan §B file map):** `schwab_api` > `tos_csv` > `manual` for same `snapshot_date`. `with_provenance=True` returns `(winner, suppressed_rows)` per spec §3.5 R4 Minor #3. Discriminating test pattern (plan T-C.2): insert all 3 sources with same date; assert `schwab_api` row wins + suppressed list shape correct.

8. **NO `INSERT OR REPLACE` anywhere in Bundle C.** Plan §A.8 baseline. account_equity_snapshots UPSERT uses SELECT-then-UPDATE-or-INSERT preserving PK (per spec §3.5 R3 Major #1 + CLAUDE.md gotcha). hypothesis_status_history is append-only — closing UPDATE on `effective_to` of prior open row + INSERT new row. Discriminating watch item: `grep -rn "INSERT OR REPLACE\|REPLACE INTO" swing/` post-Bundle-C returns zero matches.

9. **Repo functions do NOT call `conn.commit()`** (Finviz I1 lesson — codified in plan §I item #5 + Bundle A + B preserved). Caller controls transaction scope. New `swing/data/repos/account_equity_snapshots.py` + `swing/data/repos/hypothesis_status_history.py` follow the convention. Discriminating watch item: `grep -rn "conn.commit()" swing/data/repos/account_equity_snapshots.py swing/data/repos/hypothesis_status_history.py` returns zero matches.

10. **`__post_init__` validators on `AccountEquitySnapshot` + `HypothesisStatusHistory` dataclasses.** Per plan §I item #7 + Bundle 2/3 pattern + Bundle A/B precedent. Reject NaN/inf on REAL fields (`equity_dollars`); reject invalid enum values for `source` ('manual' / 'tos_csv' / 'schwab_api') + `status` (mirrors hypothesis_registry enum); reject `effective_to < effective_from` when both non-NULL on hypothesis_status_history. Discriminating tests verify each rejection path.

11. **CLI server-stamping discipline preserved at handler entry** (per plan §A.10): `account_equity_snapshots.recorded_at` server-stamped; `account_equity_snapshots.snapshot_date` operator-supplied OR default `last_completed_session(now())`; `hypothesis_status_history.effective_from` / `effective_to` / `recorded_at` server-stamped. CLI is operator-trusted (no tampering surface); the server-stamping discipline carries as design hygiene.

12. **NO new HTMX form-driven surfaces in Bundle C.** CLI + service + repo only. V2-deferred web forms (account snapshot history; hypothesis status history) are Phase 10+ territory per spec §11. Phase 5 HTMX gotchas not relevant for Bundle C.

13. **Bundle B Account Order History parser-gap is NOT Bundle C scope** (banked as Bundle E polish task in `docs/phase3e-todo.md` 2026-05-12 entry). Bundle C MUST NOT touch `swing/journal/tos_import.py:extract_stop_orders` or related stop-detection logic. **Bundle C DOES touch `swing/journal/tos_import.py` for the new `extract_account_summary_net_liq` parser (per T-C.6); that's a SEPARATE section + helper.**

14. **Bundle B's reconciliation service modification scope** (per §0.5 #5 T-C.6): Bundle C MAY modify `swing/trades/reconciliation.py:run_tos_reconciliation` to wire the equity_delta path. This is an explicit cross-bundle carve-out from the otherwise-locked Bundle B service surface — justified by the deferred ACCEPT-WITH-RATIONALE in Bundle B's return report §6. Bundle C MUST NOT modify any other Bundle B service entry point (e.g., `resolve_discrepancy`, dedup tuple shape, MATERIAL_BY_TYPE lookup). The widening to equity_delta adds NEW behavior — does NOT replace existing behavior.

### §0.6 Sub-bundle A + B landed surfaces (FORWARD-BOUND)

Sub-bundle A merged at `6c8f3a9` + housekeeping at `2219ab5`. Sub-bundle B merged at `e96834a` + housekeeping at `932584a`. Sub-bundle C builds on:

- **Sub-bundle A's `swing/trades/risk_policy.py`** canonical service-layer entry points.
- **Sub-bundle A's `swing/data/datetime_helpers.py:now_ms` + `validate_ms_iso`** — used by all Phase 9 services + repos.
- **Sub-bundle A's `CallerHeldTransactionError`** exception type — Bundle C mirrors at its services (per Bundle B precedent: Bundle B defines its own in `swing/trades/reconciliation.py` paralleling Sub-bundle A's; Bundle C can do the same).
- **Sub-bundle B's `swing/trades/reconciliation.py:run_tos_reconciliation`** — Bundle C's T-C.6 wires equity_delta into this service.
- **Sub-bundle B's `swing/trades/reconciliation.py:MATERIAL_BY_TYPE`** — `MATERIAL_BY_TYPE["equity_delta"] = 0` (material=0; equity_delta does NOT surface in canonical queries; the column denominator-mismatch is informational).
- **Sub-bundle B's `swing/trades/reconciliation.py:DISCREPANCY_TYPES`** — `equity_delta` is already in the tuple (Sub-bundle A's CHECK enum on `reconciliation_discrepancies.discrepancy_type` + Bundle B's constant).
- **Sub-bundle B's CLI `swing journal discrepancy {list,show,resolve}`** — Bundle C does NOT add new discrepancy CLI surfaces.
- **`tests/conftest.py` test fixtures** establishing a v17 DB + Bundle A + B fixtures. Bundle C tests inherit.

### §0.7 Sub-bundle A + B lessons FORWARD-BINDING

Per Sub-bundle A return report §7 watch items + Sub-bundle B return report §7 + CLAUDE.md gotcha promotions at `de10601`:

- **CLAUDE.md gotcha (banked 2026-05-12): Phase 9 ratification helper single-fire semantics.** Bundle C tests MUST NOT call `ratify_seed_from_cfg_on_v17_landing` (single-fire; Sub-bundle A tests already exercise it). If a Bundle C test fixture needs a fresh policy, use `seed_initial_policy(conn, cfg)` (idempotent — no-ops if active policy exists).
- **CLAUDE.md gotcha (banked 2026-05-12): All four cascade emitters MUST do no-op-skip check.** Bundle C does NOT add a new cascade emitter (no TOML mirror surface).
- **CLAUDE.md gotcha (banked 2026-05-12): Tests exercising `write_user_overrides` MUST monkeypatch USERPROFILE + HOME.** Bundle C tests that invoke any CLI which touches the cfg-cascade path MUST `monkeypatch.setenv("USERPROFILE", str(tmp))` + `monkeypatch.setenv("HOME", str(tmp))` BEFORE the test invokes the write path. Defensive: ALWAYS monkeypatch in any Bundle C CLI test fixture.
- **Sub-bundle B lesson: Bundle B's `MATERIAL_BY_TYPE` is authoritative at INSERT time** (Codex R1 M#2 fix at `573051f`). Caller-supplied `material_to_review` hint is IGNORED; service forces `MATERIAL_BY_TYPE[dtype]`. Bundle C's equity_delta emit (T-C.6) MUST follow the same pattern: pass via emitter without caller-supplied material; the service-internal lookup applies.
- **Sub-bundle B lesson: within-run dedup tuple shape** `(trade_id, type, field_name, ticker, fill_id, cash_movement_id, payload_disambiguator)`. Bundle C's equity_delta emit has `trade_id=None, fill_id=None, cash_movement_id=None`; tuple identity is `(None, "equity_delta", None, None, None, None, <payload-hash-or-None>)`. Within-run dedup naturally guarantees one equity_delta per run (since the run computes it once).
- **Sub-bundle B lesson: period_end defaults to max fill date in CSV** when caller omits (Codex R4 M#1). Bundle C's `get_latest_snapshot_on_or_before` consumes `period_end` from Bundle B's service path; that default still applies.

### §0.8 Sub-bundle B Account Order History parser-gap finding (operator-witnessed gate; FORWARD-BINDING for OPERATOR ACTION ITEMS)

Operator-witnessed gate on Sub-bundle B surfaced 5 false-positive `stop_mismatch` discrepancies because Bundle B's parser per spec §6.2 looks narrowly for `STP` order_type, missing the multi-line `MKT GTC WORKING` + continuation `<price> STP STD` group structure actually used by Schwab/TOS exports.

**Bundle C action:** NONE — banked as Bundle E polish task per operator instruction. Bundle C MUST NOT attempt the parser fix. Cross-reference: `docs/phase3e-todo.md` 2026-05-12 entry "Phase 9 Sub-bundle E polish: Account Order History multi-line parser gap." Operator's 4 sample exports at `thinkorswim/*.csv` are the Bundle E test corpus, NOT Bundle C scope.

**Bundle C's T-C.6 equity_delta integration uses the Account Summary section** of the same TOS export — a DIFFERENT section (after Account Order History + Account Trade History + Equities + Profits and Losses) per the export structure observed at line 114+ of `thinkorswim/2026-05-12-AccountStatement.csv`. Net-liq is the binding column. No interaction with the broken stop-detection logic.

---

## §1 Worktree + binding conventions

### §1.1 Worktree
- **Branch:** `phase9-bundle-C-hypothesis-and-equity`
- **Worktree directory:** `.worktrees/phase9-bundle-C-hypothesis-and-equity/` (project convention per CLAUDE.md + Sub-bundle A/B precedent).
- **BASELINE_SHA:** `932584a` (post-Sub-bundle-B-merge + housekeeping; HEAD of main BEFORE this brief commits).
- **Worktree branching point:** current HEAD of `main` at worktree-creation time (resolve via `git rev-parse main`; expected the dispatch-brief commit SHA after this brief lands).
- The Codex diff (`932584a` → worktree HEAD) will include one doc-only commit (this dispatch brief). Harmless; Codex evaluates the IMPLEMENTATION against the PLAN scoped to Sub-bundle C + T-C.6.

### §1.2 Marker-file workflow
- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all tasks land + tests GREEN + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits
- Conventional prefix:
  - `test(data): T-C.0 — <description>` for schema verification (test-only commit)
  - `test(data): T-C.1 — <description>` for hypothesis seed verification (test-only commit)
  - `feat(trades): T-C.2 — <description>` for account_equity_snapshots repo + service + CLI
  - `feat(data): T-C.3 — <description>` for hypothesis_status_history repo
  - `feat(trades): T-C.4 — <description>` for hypothesis status audit service + CLI rewire + DELETE legacy
  - `test(integration): T-C.5 — <description>` for E2E test
  - `feat(trades,journal): T-C.6 — <description>` for equity_delta cross-bundle wiring
  - `fix(area): Codex RN Major #X (internal) — <description>` for Codex-driven fixes
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.
- **TDD:** failing test first, minimal implementation, pass, commit. Per-task `- [ ]` checkboxes in plan §F mark per-step boundaries.
- **Prefer `git add <specific-files>` over `git add -A`** — Phase 8 R1 Critical 1 lesson banked 2026-05-07. Never use `git add -A` or `git add .`.

### §1.4 Branch isolation + ownership
- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** task-family TDD commits → marker-file removal → adversarial-critic → return report.
- **Operator owns:** witnessed verification gate (§3 surfaces below).
- **Orchestrator owns:** integration merge to main + post-merge housekeeping + Sub-bundle D dispatch commissioning.

### §1.5 Verify command
PowerShell from inside worktree (per Phase 5 editable-install lesson 2026-05-02 + Sub-bundle A/B precedent):
```powershell
$env:PYTHONPATH = "."; python -m swing.cli <command>
```
(Bundle C has no web surface — verify command only needed for CLI invocations against the worktree code. Pytest from worktree works without the PYTHONPATH prefix.)

---

## §2 Adversarial review (Codex)

### §2.1 Setup (IMPLEMENTER runs this)

After ALL task-family commits land + tests GREEN at branch HEAD:

1. `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
2. Invoke `copowers:adversarial-critic` with:
   - `PHASE`: `phase9-bundle-C-hypothesis-and-equity`
   - `SPEC_PATH`: `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md`
   - `PLAN_PATH`: `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` (Codex scopes to §F Sub-bundle C + the §0.5 #5 T-C.6 cross-bundle integration carve-out from this brief)
   - `BASELINE_SHA`: `932584a`
3. Iterate rounds until **NO_NEW_CRITICAL_MAJOR**.
4. Per-round fixes commit as `fix(area): Codex RN Major #X (internal) — <description>`.
5. Expected convergence: **3-4 rounds**. Bundle C scope is narrower than B (6+1 tasks vs B's 9; smaller code surface; no parser refactor); B converged in 5 rounds with R5 confirmation.

### §2.2 Codex value-add concentration

Adversarial review for Sub-bundle C typically catches:
- **NoOpIdentityTransition not properly sentinel-returning** — if R2 reads current status from outside the BEGIN IMMEDIATE lock, race conditions allow stale comparisons.
- **`update_hypothesis_status` not actually deleted from repo** — ImportError test would catch but pre-test grep is the brief-side discipline.
- **Caller-held-transaction rejection missing on either hypothesis or account_equity_snapshots services** — discriminating test must exist for each.
- **Source-ladder precedence inversion or tie-breaking gap** — same-day rows with all three sources should always return `schwab_api`; missing source falls through to next-priority.
- **Saturday-night discriminating test missing or wrong** — writer-side session anchor must match the predicate (`last_completed_session`, NOT `action_session_for_run`).
- **`__post_init__` validator gaps** on dataclasses — NaN/inf rejection + enum validation + cross-field invariants.
- **T-C.6 equity_delta path not gated on BOTH sides available** — emit when journal-side or source-side is None creates false discrepancies.
- **T-C.6 boundary-condition gap on `$10.00` threshold** — strict-greater-than vs greater-than-or-equal off-by-one.
- **T-C.6 modifies `MATERIAL_BY_TYPE` or `DISCREPANCY_TYPES` constants** (must NOT — already in place at Bundle B; equity_delta MUST already be in the tuple).
- **Within-run dedup not preserving the new equity_delta tuple shape** — Bundle B's emitter uses a 7-tuple; equity_delta's All-None tuple form must work + run-grain emission means dedup is naturally single-row.

---

## §3 Operator-witnessed verification surfaces

After NO_NEW_CRITICAL_MAJOR. Per plan §F intro (4 surfaces) + the new T-C.6 cross-bundle integration:

- **S1 — Post-B-merge baseline.** Operator confirms current main HEAD includes Sub-bundle B's merge + housekeeping + brief commits. Runs `python -m pytest -m "not slow" -q` from worktree; verifies baseline GREEN. Runs `swing config policy show` from worktree; verifies active policy_id (4) prints with 34 fields.
- **S2 — Consumer-side schema verification.** Operator runs `python -m pytest tests/data/test_phase9_audit_tables_schema_verification.py tests/data/test_phase9_hypothesis_seed_verification.py -v`; verifies tests PASS against the v17 schema. Specifically: hypothesis_status_history seed rows = 4 (one per existing hypothesis_registry row); account_equity_snapshots is empty.
- **S3 — account_equity_snapshots CLI.** Operator runs `swing account snapshot --equity 1300 --notes "operator gate S3"` from worktree; verifies row persisted at today's `last_completed_session` date. Then runs `swing account snapshot --equity 1400 --date 2026-04-01 --notes "back-record gate test"`; verifies upsert + `is_back_recorded=1` flag set (gap > 7 days from current session).
- **S4 — hypothesis status audit.** Operator runs `swing hypothesis update --hypothesis <name> --status paused --reason "operator gate S4"` from worktree; verifies history row inserted + prior `effective_to` closed + registry status updated. Re-runs the same command (identity transition); verifies INFO message "already paused" + NO new history row.
- **S5 — Read-path: source-ladder precedence.** Operator runs a small Python REPL or test invocation against the worktree to verify `get_latest_snapshot_on_or_before(asof=today)` returns the manual snapshot recorded in S3 (since no schwab_api or tos_csv snapshots exist; precedence falls through to manual).
- **S6 — T-C.6 equity_delta cross-bundle integration.** Operator runs `swing journal reconcile-tos --csv-path <operator's-tos-export> --period-end <date> --notes "operator gate S6 equity_delta"` from worktree against the same real-world export used in Sub-bundle B gate (`thinkorswim/2026-05-12-AccountStatement.csv`). Verifies (a) the reconciliation_run is run #2 (Bundle B left run #1); (b) if `abs(source_net_liq - manual_snapshot_equity) > $10`, an `equity_delta` discrepancy emits; otherwise NO equity_delta row. (c) `reconciliation_runs` row's `account_equity_journal_dollars` + `account_equity_source_dollars` + `equity_delta_dollars` columns populated (NOT NULL).
- **S7 — pytest + ruff.** From worktree: `python -m pytest -m "not slow" -q` GREEN; `ruff check swing/ --statistics` shows 18 (E501 only).

**Expected test count delta:** +60 to +95 fast tests (T-C.0..T-C.5 + T-C.6; plan §J.3 projection for C was 50-75; T-C.6 adds ~10-20 more). Bias toward high end of range per Sub-bundle A + B overshoot precedents.

**Expected ruff baseline:** 18 (no change).

**Production-write classifier soft-block awareness:** S3-S4 + S6 are production writes. If the orchestrator-driven invocation is classifier-blocked, the orchestrator will surface back to the operator with a plain-chat confirmation request. This does NOT affect the implementer; it's an orchestrator-side gating concern.

---

## §4 Return report shape

After operator-gate PASS, draft return report at `docs/phase9-bundle-C-return-report.md` (mirroring `docs/phase9-bundle-B-return-report.md` shape):

1. Final HEAD on branch.
2. Commit count breakdown (task-impl per T-C.X + T-C.6 + Codex-fix + operator-gate-fix).
3. Codex round chain.
4. Test count delta + ruff baseline delta.
5. Operator-gate surface results (S1-S7).
6. Per-task deviations from the plan (especially any T-C.6 deviations from the brief).
7. Codex Major findings ACCEPTED with rationale (target: zero or one — Sub-bundle B landed one; Sub-bundle A landed two; trend is toward zero).
8. Watch items surfaced but not acted on (for Sub-bundles D/E to absorb OR for orchestrator-context capture).
9. Worktree teardown status (expected ACL-locked husk).
10. Composition-surface verification: `^def update_hypothesis_status_with_audit` + `^def record_snapshot` + `^def extract_account_summary_net_liq` enumeration.
11. Hand-off notes for Sub-bundle D dispatch (Bundle C → D enables D's ad-hoc reconciliation_run for sector_tamper since D consumes the now-fully-wired reconciliation surface).

---

## §5 First-step paste-ready prompt for the implementer

```
You are taking over as implementer for the swing-trading phase9-bundle-C-hypothesis-and-equity dispatch.

WORKING DIRECTORY (after worktree creation): c:\Users\rwsmy\swing-trading\.worktrees\phase9-bundle-C-hypothesis-and-equity
BRANCH: phase9-bundle-C-hypothesis-and-equity
BASELINE_SHA: 932584a  (per dispatch brief §1.1; HEAD of main BEFORE the brief commit; post-Sub-bundle-B-merge + housekeeping)
WORKTREE-BRANCHING-POINT: current HEAD of main at worktree-creation time (resolve via `git rev-parse main`)

The Codex diff (932584a → worktree HEAD) will include one doc-only commit (this dispatch brief). Harmless; Codex evaluates the IMPLEMENTATION against the PLAN scoped to Sub-bundle C + the §0.5 #5 T-C.6 cross-bundle integration.

Step 0 — Create the worktree:
  cd c:\Users\rwsmy\swing-trading
  $base = git rev-parse main
  git worktree add .worktrees\phase9-bundle-C-hypothesis-and-equity -b phase9-bundle-C-hypothesis-and-equity $base
  New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active

Step 1 — Read the dispatch brief end-to-end from the worktree:
  docs/phase9-bundle-C-executing-plans-dispatch-brief.md

Step 2 — Read the plan §A (resolved-during-planning, lines 13-216) + §B (file map, lines 218-282) + §C (decomposition, lines 284-302) + §F (Sub-bundle C, lines 1779-1948) end-to-end:
  docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md
  Skim §I (cross-bundle invariants, lines 2116-2140) + §J.2 (grep-verification commands).

Step 3 — Read the spec (focus on §3.4 hypothesis_status_history; §3.4.1 append cadence + service contract; §3.5 account_equity_snapshots + source ladder; §3.3.1 equity_delta JSON shape; §4.3 + §4.4 cadence; §10.4 + §10.6):
  docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md

Step 4 — Read binding conventions + Sub-bundle A + B landings:
  - CLAUDE.md (gotchas; project conventions; 3 NEW gotchas from Sub-bundle A landing at de10601 are forward-binding for Bundle C; Bundle B's Sub-bundle B SHIPPED entry has critical context on transactional discipline + dedup tuple shape)
  - docs/orchestrator-context.md (orchestrator-role framing; 2 NEW lessons from Sub-bundle A landing at de10601)
  - docs/phase9-bundle-A-return-report.md (§7 watch items + §10 hand-off — Sub-bundle A's service-layer canonical entry points + transactional-discipline contracts FORWARD-BIND to Bundle C)
  - docs/phase9-bundle-B-return-report.md (§6 equity_delta ACCEPT-WITH-RATIONALE + §10 hand-off notes #1-#8 + §11 operator-side action items — equity_delta wiring is YOUR T-C.6 scope)
  - docs/phase3e-todo.md (Bundle E polish task at 2026-05-12 entry — Account Order History parser gap is NOT Bundle C scope; touch nothing in `extract_stop_orders` or related)
  - docs/phase9-writing-plans-dispatch-brief.md §0.3 + §7 (9-lesson catalog FORWARD-BINDING)

Step 5 — Verify worktree state:
  git rev-parse HEAD                                          # expect current main HEAD (typically the dispatch brief commit)
  git status                                                  # expect clean
  python -m pytest -m "not slow" -q                           # expect baseline GREEN (2610 passed, 1 skipped; 3 pre-existing fails NOT regressions)
  python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"   # expect 17

Step 6 — Pre-implementation grep recon (Bundle 2+3 + Sub-bundle A + B lesson applied):
  grep -rn "^def " swing/data/repos/                          # enumerate existing repo patterns (especially swing/data/repos/risk_policy.py + swing/data/repos/reconciliation.py — your transactional templates)
  grep -rn "with conn:" swing/trades/                         # enumerate existing transactional services
  grep -rn "INSERT OR REPLACE\|REPLACE INTO" swing/           # confirm zero usage (plan §A.8 baseline)
  grep -rn "conn.commit()" swing/data/repos/                  # confirm zero usage (Finviz I1 lesson)
  grep -rn "CallerHeldTransactionError\|in_transaction" swing/trades/risk_policy.py swing/trades/reconciliation.py    # locate Sub-bundle A + B's transactional-rejection patterns to mirror
  grep -rn "^def update_hypothesis_status" swing/data/repos/hypothesis.py    # confirm the legacy function exists (you'll DELETE it in T-C.4)
  grep -rn "^def run_tos_reconciliation\|^MATERIAL_BY_TYPE\|^DISCREPANCY_TYPES" swing/trades/reconciliation.py    # locate Bundle B's service entry + constants
  grep -A 50 "CREATE TABLE hypothesis_status_history" swing/data/migrations/0017_*.sql    # verify 7-column count for T-C.0 assertion target
  grep -A 50 "CREATE TABLE account_equity_snapshots" swing/data/migrations/0017_*.sql     # verify 8-column count for T-C.0 assertion target
  grep "WAIT TRG\|MKT.*GTC.*WORKING\|STP.*STD" thinkorswim/*.csv | head -10  # familiarize with real-world structure (operator's 4 sample exports); the Account Order History gap is BUNDLE E, NOT C
  ls swing/data/migrations/                                   # confirm 0017 is the only Phase 9 migration + no 0018 attempt during dispatch (BINDING — Bundle C does NOT modify migrations)
  Capture divergences from plan assumptions; surface in return report §6.

Step 7 — Invoke copowers:executing-plans (the skill wraps superpowers:subagent-driven-development + adversarial Codex review):
  - PHASE: phase9-bundle-C-hypothesis-and-equity
  - SPEC_PATH: docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md
  - PLAN_PATH: docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md
  - BASELINE_SHA: 932584a
  - SCOPE: Sub-bundle C only (tasks T-C.0 through T-C.5 in plan §F) PLUS T-C.6 cross-bundle equity_delta wiring per dispatch brief §0.5 #5.

Step 8 — TDD per task: failing test → minimal implementation → pass → commit. Per-task `- [ ]` checkboxes in plan §F mark per-step boundaries. T-C.6 is NEW (not in plan); follow brief §0.5 #5 for acceptance criteria.

Step 9 — After ALL tasks land + GREEN, run adversarial review per dispatch brief §2.1. Iterate Codex rounds until NO_NEW_CRITICAL_MAJOR. Expected 3-4 rounds.

Step 10 — Draft return report at docs/phase9-bundle-C-return-report.md per dispatch brief §4. Commit it.

Step 11 — Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active + signal orchestrator. Orchestrator drives §3 witnessed verification gate; orchestrator handles integration merge; orchestrator dispatches Sub-bundle D next.

DO NOT:
  - Push to origin from inside the worktree
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer to commits
  - Skip the marker-file removal before invoking copowers
  - Skip the Step 6 pre-implementation grep recon (Bundle 2+3 + Sub-bundle A + B lesson)
  - Modify migration 0017 in any way (Bundle C is consumer-side only; atomicity BINDING per Sub-bundle A landing)
  - Bump EXPECTED_SCHEMA_VERSION beyond 17 (Bundle C does NOT advance the schema)
  - Add cross-bundle code BEYOND the §0.5 #5 T-C.6 carve-out (no sector_tamper logic; that's Bundle D)
  - Add UPDATE schema_version statements
  - Use INSERT OR REPLACE or REPLACE INTO anywhere
  - Call conn.commit() inside new repo functions (caller controls transaction scope)
  - Auto-detect caller-held transactions in new services (reject; don't accommodate)
  - Touch Bundle B's parser code for stop_mismatch / Account Order History (banked as Bundle E polish per phase3e-todo.md 2026-05-12 entry; NOT Bundle C scope)
  - Modify Bundle B's MATERIAL_BY_TYPE / DISCREPANCY_TYPES / RESOLUTION_TYPES constants (already in place)
  - Diverge from plan §A locked decisions without explicit Codex justification
  - Use `git add -A` or `git add .` (per Phase 8 R1 Critical 1 lesson; stage specific files)
```

---

## §6 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-12 (post-Sub-bundle-B-merge + housekeeping).
- **Brief commit:** `<filled-in-after-commit>`.
- **Brief HEAD context:** `932584a` on main (post-Sub-bundle-B-merge + housekeeping).
- **Worktree path (binding):** `.worktrees/phase9-bundle-C-hypothesis-and-equity/`.
- **Baseline test count:** 2610 fast (1 skipped); 3 pre-existing failures NOT regressions.
- **Baseline ruff count:** 18 (E501 only).
- **Plan status:** SHIPPED 2026-05-11 at `a0c7223`; 2257 lines; 30 tasks; Codex R5 confirmation.
- **Sub-bundle A status:** SHIPPED 2026-05-12 at `6c8f3a9`.
- **Sub-bundle B status:** SHIPPED 2026-05-12 at `e96834a`; 7-surface operator-witnessed gate PASS; 1 ACCEPT-WITH-RATIONALE (equity_delta deferred — this brief's T-C.6 wires it).
- **Expected post-dispatch test count:** ~2670-2705 (+60-95; T-C.0..T-C.5 + T-C.6).
- **Expected post-dispatch ruff count:** 18 (no change).
- **Expected schema version post-Bundle-C:** 17 (UNCHANGED; Bundle C is consumer-side only).
- **Sub-bundle D dispatch dependency:** C's hypothesis + account_equity services + T-C.6 equity_delta wiring must merge to main + orchestrator-witnessed gate PASS before D can dispatch. Sub-bundle D consumes Bundle B's reconciliation_runs ad-hoc `source='system_audit'` emission for sector_tamper rejection.
- **Phase 9 arc remaining:** A ✓ → B ✓ → C (this dispatch) → D → E. Then Phase 10 writing-plans.
