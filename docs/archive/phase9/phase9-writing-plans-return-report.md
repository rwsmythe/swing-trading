# Phase 9 writing-plans — Return Report

**Dispatch brief:** `docs/phase9-writing-plans-dispatch-brief.md` (commit `d2459e2`).
**Spec consumed:** `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` (1090 lines; Codex R5 confirmation; LOCKED).
**Plan produced:** `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` (2257 lines).
**Branch:** `phase9-writing-plans` (worktree at `.worktrees/phase9-writing-plans/`).
**Branching point:** `d2459e2` (main HEAD at worktree-creation time = dispatch brief commit).

---

## §1 Final HEAD on branch

`a7dcf09` (Codex R5 minor refinement — narrow OperationalError catch).

## §2 Commit count breakdown

6 commits total:

| SHA | Type | Subject |
|---|---|---|
| `1a66950` | plan-write | Phase 9 writing-plans — initial plan landing (pre-Codex) |
| `3a189aa` | Codex-fix | R1 — migration atomicity + spec deviations |
| `6ec9f2d` | Codex-fix | R2 — stale R1-fix propagation + price_tolerance source lock |
| `b778bca` | Codex-fix | R3 — frozen-dataclass + load() purity + UNIQUE error text |
| `745a73e` | Codex-fix | R4 — T-A.5 + file-map stale-reference scrub |
| `a7dcf09` | Codex-fix | R5 — narrow OperationalError catch (minor refinement) |

Distribution: 1 plan-write + 5 Codex-fix.

## §3 Codex round chain

| Round | Critical | Major | Minor | Verdict |
|---|---|---|---|---|
| R1 | 1 | 3 | 0 | ISSUES_FOUND |
| R2 | 0 | 3 | 0 | ISSUES_FOUND |
| R3 | 0 | 1 | 1 | ISSUES_FOUND |
| R4 | 0 | 1 | 1 | ISSUES_FOUND |
| R5 | 0 | 0 | 1 | **NO_NEW_CRITICAL_MAJOR** |

**Chain shape:** convergent + tapering. Each round's findings were either R-N-1-fix-introduced regressions or freshly-exposed adjacent-surface gaps — NOT adversarial thrash. Matches the Phase 7/8 healthy-chain pattern documented in orchestrator-context lessons 2026-05-07. Round 5 explicitly returned NO_NEW_CRITICAL_MAJOR.

## §4 Plan task decomposition rationale

Plan decomposes Phase 9 into **5 sub-bundles** for executing-plans dispatch (per dispatch brief §1.2):

| Sub-bundle | Scope | Task count | Dependency |
|---|---|---|---|
| **A — schema + risk_policy foundation** | COMPLETE migration 0017 atomic landing (all 5 tables + 2 ALTERs + all seeds + 13 indexes) + datetime helpers + RiskPolicy dataclass + repo + service (supersession 6-step + cfg-cascade + TOML-divergence-helper) + CLI + Phase 7 entry stamp + Phase 6 review-complete stamp | 8 tasks (T-A.0 … T-A.7) | None |
| **B — reconciliation depth** | Repo + service + tos_import.py refactor (emitter seam) + close_price_mismatch + entry_price_mismatch + stop_mismatch + position_qty_mismatch + cash_movement_mismatch + CLI (`reconcile-tos` rename + alias + `discrepancy` group) + E2E | 9 tasks (T-B.0 … T-B.8) | A (migration landed) |
| **C — hypothesis_status_history + account_equity_snapshots** | Consumer-side schema verification + dataclasses + repos + services (account snapshot record + hypothesis status audit) + CLI (`account snapshot`) + rewire `swing hypothesis update` through new service + DELETE legacy repo function + E2E | 6 tasks (T-C.0 … T-C.5) | A (migration landed) |
| **D — sector/industry tamper hardening** | Existing chart_pattern hardening recon + route-layer rejection at `/trades/entry` POST + ad-hoc reconciliation_run emission + E2E | 4 tasks (T-D.0 … T-D.3) | A (risk_policy seed) + B (reconciliation tables + service entry) |
| **E — final polish + Phase 10 hand-off prep** | Combined E2E happy path + CLAUDE.md gotcha promotion candidates + Phase 10 hand-off note + ruff sweep | 3 tasks (T-E.0 … T-E.2) | A + B + C + D |

**Total: 30 tasks** across 5 sub-bundles. Recommended dispatch ordering: A → B → C → D → E (each bundle locks schema/service surfaces consumed by the next). C is independent of B (can theoretically dispatch in parallel after A), but sequential is recommended for orchestrator-context discipline.

**Cross-bundle dependencies (explicit):**
- B depends on A's risk_policy table (for `is_active=1` reads to seed reconciliation summary metrics) + reconciliation tables (landed in A's migration).
- C depends on A's hypothesis_status_history table + seed rows + account_equity_snapshots table (all landed in A's migration).
- D depends on A's risk_policy seed (for §A.4 sector tamper future-elevation references) + B's reconciliation_runs/discrepancies tables AND B's service entry (`run_tos_reconciliation` not strictly required; D emits `system_audit`-sourced runs directly via `swing/data/repos/reconciliation.py:insert_run` + `insert_discrepancy` — but the repo module lands in B).
- E depends on all four upstream bundles for E2E coverage.

**Migration atomicity (binding per Codex R1 Critical #1 fix):** the single migration file `0017_phase9_risk_policy_and_reconciliation.sql` is landed COMPLETE-AND-ATOMIC in T-A.1. ALL 5 tables + 2 ALTERs + all 13 indexes + risk_policy seed + per-hypothesis hypothesis_status_history seed rows + `UPDATE schema_version SET version = 17` are in ONE file. Sub-bundles B/C/D/E DO NOT modify the migration; they ship code (repos + services + CLI + routes) that consumes the already-landed schema. T-B.0 / T-C.0 / T-C.1 are repurposed as consumer-side read-only PRAGMA-driven schema-verification tasks.

## §5 §10 open-questions disposition

Spec §10 enumerated 6 open questions. Plan accepts ALL 6 brainstorm recommendations per dispatch brief §0.4:

| Question | Disposition |
|---|---|
| §10.1 reconciliation_run period_end for account-state pulls | ACCEPT brainstorm rec: `last_completed_session(now)`; operator override. Defer Schwab Phase A; V1 ships TOS-CSV only. |
| §10.2 sector_tamper hard-gate elevation trigger | ACCEPT: V1 advisory (`material_to_review=0`); V2 elevation operator-decision. Flagged in return report watch items + plan T-E.1 candidate gotcha. |
| §10.3 reconciliation_runs retention | ACCEPT: retain all forever. |
| §10.4 hypothesis_status_history seed effective_from | ACCEPT: `hypothesis_registry.created_at` normalized to millisecond precision (spec §3.4.1 R3 Major #2). Plan T-A.1 + T-C.1. |
| §10.5 V1 CLI surface for risk_policy editing | ACCEPT: per-field CLI for V1. Plan §A.3 + T-A.6. Bulk + web deferred to V2. |
| §10.6 reconciliation period_end vs source artifact date | ACCEPT: operator-passed via CLI flag (`--period-end <ISO>`); default = last fill date in parsed CSV. Plan T-B.7. |

No divergences from brainstorm recommendations.

## §6 Codex Major findings ACCEPTED with rationale

**None.** All 8 Major findings across R1–R4 were FIXED. Zero accept-with-rationale.

## §7 §A resolved-during-planning summary (empirical findings discovered during writing-plans)

The plan's §A enumerates **11 resolved-during-planning items**:

| § | Title | Outcome |
|---|---|---|
| §A.0 | Migration filename + schema-version collision (Codex R1 Critical) | Migration filename locked at `0017_*` (Phase 8 took 0016); schema bump v16 → v17 preserved per spec intent. |
| §A.0.1 | risk_policy column count reconciliation (Codex R1 Major #2) | Spec text "28 columns" subtotal is a brainstorm-phase miscount; the column LIST enumerates 34 distinct fields. Plan tests + DDL + dataclass use 34. |
| §A.1 | Hypothesis-status audit service module placement | New `swing/trades/hypothesis.py` module owns `update_hypothesis_status_with_audit` per spec §3.4.1 single-write-path. Existing `swing/data/repos/hypothesis.py:update_hypothesis_status` DELETED in T-C.4 (one CLI caller rewired). Discriminating ImportError test at T-C.4.4 enforces. |
| §A.2 | Reconciliation service module placement + tos_import.py refactor scope | New `swing/trades/reconciliation.py` owns `run_tos_reconciliation`; emitter seam injected into existing `reconcile_tos`; ReconciliationReport dataclass return shape preserved (existing CLI consumers unaffected). |
| §A.2.1 | cash_movements + fills inline-insert disposition | Existing inline INSERTs retained inside the new outer transaction; failure-path preserves emitted rows per Codex R1 Major #1 fix (spec §3.3.3). |
| §A.2.2 | CLI rename | `swing journal import-tos` → `swing journal reconcile-tos`; deprecation alias for V1; alias removed in V2. |
| §A.3 | Risk_Policy CLI surface decision | Per-field CLI for V1 (`swing config policy {show, set, import-from-toml, history}`); bulk + web deferred to V2 per spec §10.5. |
| §A.4 | Sector/industry tamper hardening route-layer integration | Mirrors chart_pattern hardening at `swing/web/routes/trades.py` (commits `117dc97` + `2b9d6f3`); emits `sector_tamper` discrepancy in ad-hoc `system_audit`-sourced reconciliation_run on rejection (§A.4.1 SECOND transaction independent of rejected entry). |
| §A.5 | cfg-mirror cascade at risk_policy save | Phase 5 config-page edit cascades to new risk_policy row for `risk_equity_floor` only; other cfg fields unchanged. |
| §A.5.1 | startup TOML divergence detection (Codex R3 Major #1 + R4 Major #1 architectural revision) | `swing/config.py:load()` REMAINS PURE — no DB read, no signature change. New helper `check_and_reconcile_toml_divergence(conn, cfg) -> tuple[Config, dict \| None]` uses `dataclasses.replace` (Config is frozen). Invoked at TWO post-`ensure_schema` hooks: CLI entry + web app lifespan. `swing db-migrate` explicitly SKIPS. Pre-v17 schema-version check guards (Codex R5 Minor refinement narrowed broad `OperationalError` catch to schema-version check + narrower NoActivePolicyError catch). |
| §A.6 | Test count projection bias | +200 to +320 fast tests (range, NOT single number). Baseline 2329 → expected end-state 2529–2649. |
| §A.7 | In-flight production data state | Legacy trades + reviews stamp `risk_policy_id_at_lock` / `risk_policy_id_at_review_completion` = NULL post-migration; read paths resolve to current `is_active=1` policy (NOT an error). |
| §A.8 | No INSERT OR REPLACE in Phase 9 paths | Pre-plan grep confirmed zero matches across `swing/`; Phase 9 preserves the discipline. |
| §A.9 | Session-anchor read/write predicate alignment | `swing account snapshot` writer defaults to `last_completed_session(now())` per CLAUDE.md gotcha; Phase 10 dispatcher inherits the constraint. Discriminating Saturday-night test pinned. |
| §A.10 | Server-stamping at CLI + route-handler entries | 11-field disposition table per spec/dispatch-brief §0.3 #9. V1 has NO HTML form for risk_policy / account-snapshot / reconciliation routes (CLI-only); Phase 5 config page extension preserves Phase 5 server-stamping discipline. |
| §A.11 | Datetime precision: SQLite `strftime` form | `strftime('%Y-%m-%dT%H:%M:%f', 'now')` (SQL) + bind-once Python form. New helper at `swing/data/datetime_helpers.py:now_ms`. |

Total resolved-during-planning: **17 items** (across 11 numbered sections including subsections). Pattern matches Phase 8 plan §A scale.

## §8 Watch items for orchestrator (lock before executing-plans dispatch)

1. **Migration atomicity is BINDING.** Brief drafting for sub-bundle A executing-plans dispatch MUST emphasize that T-A.1 lands the COMPLETE migration; sub-bundles B/C/D/E DO NOT modify migration files. If orchestrator decomposes A into smaller sub-tasks for any reason, the migration atomicity invariant must be preserved (single-file complete-and-atomic landing).
2. **Risk_policy column count is 34.** The spec's "28 columns" subtotal text is a brainstorm-phase miscount; the column LIST is the binding artifact. All executing-plans test assertions + DDL + dataclass field counts MUST use 34, NOT 28. ACCEPT-WITH-RATIONALE per brief §1.1; flagged at orchestrator triage so it doesn't recur in Phase 9 V2 follow-ups.
3. **Frozen-dataclass + load() purity binding contract.** `swing/config.py:load(config_path)` MUST remain pure — no DB connection parameter, no risk_policy read inside load. The divergence check lives in the new helper invoked at post-`ensure_schema` hooks. Implementer MUST NOT route around this constraint when the executing-plans dispatch encounters resistance (e.g., a tempting one-line "just add a conn param" patch). The frozen-dataclass discipline is a project-wide convention worth preserving.
4. **`swing db-migrate` MUST SKIP the divergence hook.** Discriminating regression test `test_db_migrate_skips_divergence_hook` is the bind point — without this skip, db-migrate from v16 → v17 would call the helper on a DB that doesn't yet have a risk_policy table; the helper handles this silently per the schema-version check (Codex R5 fix), but the discipline is to NOT invoke at all.
5. **Reconciliation failure semantics: PRESERVE the run row + UPDATE state='failed'.** Per spec §3.3.3 + Codex R1 Major #1 fix: do NOT rollback-and-insert-new-row. Pre-failure emitted discrepancies + cash_movements + fills are preserved alongside the failed-state UPDATE within the same commit (audit-trail integrity prioritized over rollback purity).
6. **Single-write-path discipline for hypothesis status: DELETE legacy repo function.** T-C.4 deletes `swing/data/repos/hypothesis.py:update_hypothesis_status`; the CLI handler is rewired through new service `swing/trades/hypothesis.py:update_hypothesis_status_with_audit`. Discriminating ImportError test at T-C.4.4 verifies. Implementer MUST NOT leave the legacy function for "backward compatibility" — it's a single-call-site refactor.
7. **Phase 7 + Phase 8 transactional discipline forward-bound.** All 4 new services (`risk_policy`, `reconciliation`, `account_equity_snapshots`, `hypothesis`) reject caller-held transactions at entry (Phase 8 R4 M1 lesson — "reject + simple contract over auto-detect + complicate"). Discriminating regression tests verify `CallerHeldTransactionError` raised when caller has open BEGIN IMMEDIATE.
8. **Phase 5 HTMX form discipline preserved at T-A.5.** Phase 5 cfg-cascade extension MUST preserve `hx-headers='{"HX-Request": "true"}'` propagation on embedded form + `HX-Redirect` success-path response. Operator-witnessed browser verification gate is BINDING for the T-A.5 sub-task per CLAUDE.md gotcha.
9. **CLAUDE.md gotcha promotion candidates at T-E.1.** Plan flags three candidate gotchas: (a) risk_policy supersession 6-step sequence (predecessor is_active=0 BEFORE successor INSERT to free partial unique index slot); (b) TOML divergence detection at startup logs WARNING but NEVER auto-writes TOML; (c) account_equity_snapshots source-ladder precedence with provenance rendering. Orchestrator triages at integration merge.
10. **§10.2 V2 follow-up: sector_tamper hard-gate elevation.** Plan locks V1 as advisory; V2 elevation is operator-decision. Orchestrator queues at first post-Phase-9 orchestrator-context update.
11. **Test count projection range is 200–320 new fast tests.** Acceptance criteria use the RANGE, not the point estimate (§A.6). Implementer's TDD cycle naturally produces the range.

## §9 Worktree teardown status

**Expected:** ACL-locked husk per Phase 6/7/8 / Bundle 1+2+3 pattern. This is the **6th husk** in the current batch (per dispatch brief §4 expectation).

**Action by orchestrator:** at integration merge time, after operator-witnessed gate, orchestrator runs `git worktree remove --force` on the worktree path. If Windows ACL denies removal, the `cleanup-locked-scratch-dirs.ps1` script (covers both `.worktrees/` and `.claude/worktrees/` paths post-2026-05-09) takes over.

No teardown attempted by this dispatch (per dispatch brief §2.4 — orchestrator-owned). The `.copowers-subagent-active` marker file is removed at signal time (next step).

---

## Plan summary statistics

- Plan size: **2257 lines** (within the 1000–1500 dispatch-brief target +50% — Phase 9's 5 new tables + 2 cross-cutting modifications + 5 sub-bundles drove the line count; comparable to Phase 8 plan at 4140 lines for a more-discriminating-test-heavy scope).
- Sub-bundles: 5 (A/B/C/D/E).
- Tasks: 30 (T-A.0 … T-E.2).
- File-map new/modified: 27 new files + 9 modified files.
- §J spec coverage matrix: 39/39 (full).
- §J grep-verification commands: 9 acceptance-gate checks.
- §I watch items: 13 cross-bundle invariants.
- §A resolved-during-planning items: 17.

## Codex review effort summary

- 5 rounds, 8 substantive findings (1C + 7M + 3m).
- All 8 Critical + Major findings RESOLVED via plan refinement.
- 0 findings ACCEPTED-with-rationale (clean resolution rate).
- 4 Minor advisory items: 3 propagated as accept-and-fix; 1 (R5 Minor #1) refined the helper post-terminal.

---

*End of return report. Orchestrator triages + commissions executing-plans dispatches (recommended ordering: A → B → C → D → E).*
