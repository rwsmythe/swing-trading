# Phase 9 Sub-bundle A — executing-plans dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Sub-bundle A (schema + risk_policy foundation) of the Phase 9 implementation plan via `copowers:executing-plans`. Plan is `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` §D (lines 304-1515; 8 tasks T-A.0 … T-A.7). All per-task acceptance criteria + tests + commit shapes are in the plan; this dispatch brief is a worktree-config + scope wrapper, NOT a duplicate spec.

**Expected duration:** ~12-16 hr implementation + ~2-4 hr Codex convergence. Total ~14-20 hr. Sub-bundle A is the largest of the 5 sub-bundles (bottom of dependency stack; lands the full migration + 5 new tables + 2 ALTER ADDs + foundational service layer).

**Skill posture:**
- Invoke `copowers:executing-plans` against the plan path scoped to Sub-bundle A (`PLAN_PATH=docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md`, `SCOPE=Sub-bundle A (T-A.0..T-A.7 only)`).
- The skill wraps `superpowers:subagent-driven-development` + adversarial Codex review.
- Adversarial review runs after all 8 tasks land. Expected 3-5 Codex rounds (matches Phase 8 daily-management executing-plans precedent at 5 rounds for similar schema-foundation scope).

---

## §0 Inputs

### §0.1 Plan
- **PLAN_PATH:** `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` (2257 lines; Codex R5 confirmation; LOCKED).
- **Sub-bundle A section:** §D (lines 304-1515). Self-contained per-task spec with TDD checkboxes (`- [ ]`).
- **Plan §A resolved-during-planning items:** read all 17 items at lines 13-216 BEFORE starting tasks. Several are BINDING for Sub-bundle A (especially §A.0 migration filename `0017_*`; §A.0.1 column count 34; §A.5/§A.5.1 `swing/config.py:load()` purity contract; §A.11 `now_ms` helper at `swing/data/datetime_helpers.py`).
- **Plan §B file-map:** lines 218-282. Enumerates all 27 new files + 9 modified files; Sub-bundle A creates ~8 new files + modifies 4 files.

### §0.2 Spec
- **SPEC_PATH:** `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md` (1090 lines; LOCKED at `31ee51c`).
- **Read for §3.1 risk_policy column list (BINDING — 34 columns; plan §A.0.1 corrects spec's brainstorm-miscount "28").**
- **Read §1 + §2 + §9 for background; §3 for schema sketches; §4 for capture cadence; §5 for lifecycle integration with Phase 6/7/8.**

### §0.3 Project state at dispatch time
- **HEAD on `main`:** `700337d` (post-Phase-9-writing-plans-ship housekeeping).
- **Test count:** 2328 fast (1 skipped); 3 pre-existing failures on `tests/integration/test_phase8_pipeline_walkthrough.py` ("archive returned None"; NOT related to Phase 9 scope).
- **Ruff baseline:** 18 (E501 only).
- **Schema version:** v16 (Phase 8 daily_management shipped). Sub-bundle A bumps v16 → v17 in T-A.1 via migration `0017_phase9_risk_policy_and_reconciliation.sql`.
- **3 worktree husks pending operator cleanup-script:** 3e8-bundle-3 + polish-bundle-2026-05-10 + phase9-writing-plans.

### §0.4 Sub-bundle A scope (8 tasks)

Per plan §C decomposition table + §D detail:

| Task | Title | Files |
|---|---|---|
| **T-A.0** | Datetime helpers (`now_ms` + `validate_ms_iso`) | NEW `swing/data/datetime_helpers.py` + tests |
| **T-A.1** | COMPLETE migration 0017 atomic landing | NEW `swing/data/migrations/0017_phase9_risk_policy_and_reconciliation.sql` + 2 test files |
| **T-A.2** | RiskPolicy dataclass (frozen) | NEW `swing/data/models.py` extension + tests |
| **T-A.3** | risk_policy repo (CRUD) | NEW `swing/data/repos/risk_policy.py` + tests |
| **T-A.4** | risk_policy service (supersession 6-step + cfg-cascade + TOML-divergence-helper) | NEW `swing/trades/risk_policy.py` + tests |
| **T-A.5** | Phase 5 config page cfg-mirror cascade extension | MODIFY `swing/web/routes/config.py` + tests |
| **T-A.6** | CLI surface (`swing config policy {show, set, import-from-toml, history}`) | MODIFY `swing/cli.py` + tests |
| **T-A.7** | Phase 7 entry stamp + Phase 6 review-complete stamp | MODIFY `swing/trades/entry.py` + `swing/data/repos/review_log.py` + tests |

**Cross-bundle dependencies:** NONE — Sub-bundle A is bottom of dependency stack. B/C/D/E all depend on A's migration.

**Migration atomicity (BINDING per Codex R1 Critical #1):** the SINGLE migration file `0017_*.sql` lands ALL 5 new tables + 2 ALTER ADDs + risk_policy seed + hypothesis_status_history seed rows + indexes ATOMICALLY in T-A.1. Sub-bundles B/C/D/E DO NOT modify the migration; they ship code that consumes the schema. `UPDATE schema_version SET version = 17` happens at the END of the migration file. `EXPECTED_SCHEMA_VERSION = 17` is bumped in T-A.1.

### §0.5 BINDING contracts from plan §A (DO NOT re-litigate)

1. **Migration filename: `0017_phase9_risk_policy_and_reconciliation.sql`** (plan §A.0). Backup file: `swing-pre-phase9-migration-<ISO>.db`.
2. **risk_policy has 34 columns** (plan §A.0.1; spec text "28" is brainstorm miscount). All DDL + dataclass + tests assert 34.
3. **`swing/config.py:load()` REMAINS PURE** — no DB read, no signature change (plan §A.5.1). Divergence check via new helper `check_and_reconcile_toml_divergence(conn, cfg) -> tuple[Config, dict | None]` using `dataclasses.replace` (Config is frozen). Invoked at TWO post-`ensure_schema` hooks: CLI entry + web app lifespan. `swing db-migrate` explicitly SKIPS.
4. **Reconciliation failure-path PRESERVES run row + UPDATEs state='failed'** (plan §A.2.1; spec §3.3.3). NOT a Sub-bundle A concern but the contract is BINDING for B.
5. **Single-write-path for hypothesis status: DELETE legacy `swing/data/repos/hypothesis.py:update_hypothesis_status`** (plan §A.1). NOT a Sub-bundle A concern; sub-bundle C lands the deletion. Plan §A.1 is informational here.
6. **risk_policy supersession 6-step sequence** (plan §A.5; per spec §4.1; per Phase 8 R2 dual-column lesson): predecessor `is_active=0` BEFORE successor row INSERT; `superseded_by_policy_id` set AFTER successor row INSERT. Plan T-A.4 codifies.
7. **Phase 7 + Phase 8 transactional discipline FORWARD-BOUND**: new risk_policy service rejects caller-held transactions at entry (per Phase 8 R4 M1 lesson). Discriminating regression test `test_save_policy_rejects_caller_held_transaction` (plan T-A.4 codifies).
8. **Phase 5 HTMX form discipline at T-A.5**: preserve `hx-headers='{"HX-Request": "true"}'` propagation on embedded form + `HX-Redirect` success-path response. Operator-witnessed browser verification gate is BINDING for T-A.5.

### §0.6 Bundle 2+3 lessons FORWARD-BINDING

Per Phase 9 writing-plans dispatch brief §0.3 + §7 (9-lesson catalog at `docs/phase9-writing-plans-dispatch-brief.md`); plan integrates all into per-task acceptance criteria. Codex will test plan adherence. The most BINDING for Sub-bundle A:

- **`__post_init__` validator pattern** for `RiskPolicy` dataclass (mirrors Bundle 2 R3 Major #1 NaN/inf/out-of-range rejection).
- **Service-layer `with conn:` opens its own transaction** — risk_policy service rejects caller-held tx (no auto-detect).
- **`executescript()` issues implicit COMMIT** — migration runner discipline inherited via `swing/data/db.py:_apply_migration` (`283d4fa` hotfix).
- **NO `INSERT OR REPLACE`** on hypothesis_status_history or any FK-referenced table (Phase 8 gotcha 2026-05-06; plan §A.8 confirmed zero usage in `swing/`).
- **Server-stamping hidden audit fields** — risk_policy `created_at` / `effective_from` MUST be server-stamped at handler entry; T-A.6 CLI handler stamps; T-A.5 web route preserves Phase 5 server-stamping.
- **Migration filename collision check** — plan §A.0 verifies `0017_*` is next; sub-bundle B/C/D do NOT modify migrations.

---

## §1 Worktree + binding conventions

### §1.1 Worktree
- **Branch:** `phase9-bundle-A-risk-policy-foundation`
- **Worktree directory:** `.worktrees/phase9-bundle-A-risk-policy-foundation/`
- **BASELINE_SHA:** `700337d` (current main HEAD; post-Phase-9-writing-plans-ship housekeeping).
- **Worktree branching point:** current HEAD of `main` at worktree-creation time (resolve via `git rev-parse main`; expected the dispatch-brief commit SHA after this brief lands).

### §1.2 Marker-file workflow
- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After all 8 tasks land + tests GREEN + before invoking adversarial-critic: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §1.3 Commits
- Conventional prefix:
  - `feat(data): T-A.0 — <description>` for datetime helpers
  - `feat(data): T-A.1 — <description>` for migration 0017
  - `feat(data): T-A.2/A.3 — <description>` for dataclass + repo
  - `feat(trades): T-A.4 — <description>` for service
  - `feat(web): T-A.5 — <description>` for Phase 5 config page extension
  - `feat(cli): T-A.6 — <description>` for CLI surface
  - `feat(trades,web): T-A.7 — <description>` for entry + review-complete stamps
  - `test(...)` for test-only commits
  - `fix(area): Codex RN Major #X (internal) — <description>` for Codex-driven fixes
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.
- **TDD:** failing test first, minimal implementation, pass, commit. Per-task `- [ ]` checkboxes in plan §D mark per-step boundaries.

### §1.4 Branch isolation + ownership
- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** task-family TDD commits → marker-file removal → adversarial-critic → return report.
- **Operator owns:** witnessed verification gate (§3 surfaces below).
- **Orchestrator owns:** integration merge to main + post-merge housekeeping + Sub-bundle B dispatch commissioning.

### §1.5 Verify command
PowerShell from inside worktree:
```powershell
$env:PYTHONPATH = "."; python -m swing.cli web
```

---

## §2 Adversarial review (Codex)

### §2.1 Setup (IMPLEMENTER runs this)

After ALL 8 task-family commits land + tests GREEN at branch HEAD:

1. `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
2. Invoke `copowers:adversarial-critic` with:
   - `PHASE`: `phase9-bundle-A-risk-policy-foundation`
   - `SPEC_PATH`: `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md`
   - `PLAN_PATH`: `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md` (Codex scopes to §D Sub-bundle A; rest of plan is informational context)
   - `BASELINE_SHA`: `700337d`
3. Iterate rounds until **NO_NEW_CRITICAL_MAJOR**.
4. Per-round fixes commit as `fix(area): Codex RN Major #X (internal) — <description>`.
5. Expected convergence: **3-5 rounds** (matches Phase 8 daily-management executing-plans precedent at 5 rounds for similar schema-foundation scope).

### §2.2 Codex value-add concentration

Adversarial review for Sub-bundle A typically catches:
- **Migration column-count drift** — Codex validates 34 columns per plan §A.0.1.
- **Migration atomicity** — Codex validates all 5 tables + 2 ALTERs + seeds in ONE file; `UPDATE schema_version SET version = 17` at END only.
- **`load()` purity gap** — if any code path on the CLI / web side calls `load()` with a connection arg, Codex flags.
- **Supersession 6-step ordering** — if predecessor `is_active=0` happens AFTER successor INSERT, Codex flags.
- **Caller-held-transaction rejection** — discriminating test must exist for `save_policy`.
- **Frozen-dataclass discipline** — `RiskPolicy` MUST be frozen; mutation via `dataclasses.replace`.
- **`now_ms` bind-once pattern** — if `datetime.utcnow()` is called twice in one INSERT path, Codex flags (plan §A.11).
- **Session-anchor read/write predicate alignment** — if any new read predicate uses `action_session_for_run(now())` against a writer that stamps `last_completed_session(now())`, Codex flags (CLAUDE.md gotcha).

---

## §3 Operator-witnessed verification surfaces

After NO_NEW_CRITICAL_MAJOR:

- **S1 — Pre-migration baseline.** Operator runs `swing db-migrate --check` from worktree; verifies current_version=16, pending=0 (or expected post-T-A.1 state). Verifies `python -m pytest -m "not slow" -q` GREEN.
- **S2 — Post-migration policy show.** Operator runs `swing db-migrate` then `swing config policy show`; verifies seed policy_id=1 prints with all 34 fields from `swing.config.toml` cascaded.
- **S3 — Policy supersession.** Operator runs `swing config policy set --field max_account_risk_per_trade_pct --value 0.75 --notes "operator test"`; verifies new policy_id=2 created; policy_id=1 has `is_active=0` + `superseded_by_policy_id=2`. Discriminating CLI output renders the supersession audit.
- **S4 — Phase 7 entry stamp.** Operator navigates to `/trades/entry`, creates a new test trade; verifies the new `trades` row has `risk_policy_id_at_lock=2` (the currently active policy).
- **S5 — Phase 6 review-complete stamp.** Operator navigates to a review-eligible trade's `/reviews/{id}/complete`, completes the review; verifies the `review_log` row has `risk_policy_id_at_review_completion=2`.
- **S6 — pytest + ruff.** From worktree: `python -m pytest -m "not slow" -q` GREEN; `ruff check swing/ --statistics` shows ≤18 (no new violations).

**Expected test count delta:** +40 to +80 fast tests (T-A.0..T-A.7; depends on Codex defensive-hardening cycles per Bundle 2+3 precedent).
**Expected ruff baseline:** 18 (no change) or lower if imports clean up.

---

## §4 Return report shape

After operator-gate PASS, draft return report at `docs/phase9-bundle-A-return-report.md` (mirroring `docs/3e8-bundle-3-return-report.md` shape):

1. Final HEAD on branch.
2. Commit count breakdown (task-impl per T-A.X + Codex-fix + operator-gate-fix).
3. Codex round chain (e.g., "R1 0/X/Y → R2 ... → Rn NO_NEW_CRITICAL_MAJOR").
4. Test count delta + ruff baseline delta.
5. Operator-gate surface results (S1-S6).
6. Per-task deviations from the plan (if any).
7. Codex Major findings ACCEPTED with rationale (target: zero, matching Phase 9 writing-plans precedent).
8. Watch items surfaced but not acted on (for Sub-bundles B/C/D/E to absorb).
9. Worktree teardown status (expected ACL-locked husk).
10. Composition-surface verification (NOT applicable for Sub-bundle A — no advisory composition surfaces touched; advisory rules are independent of risk_policy).

---

## §5 First-step paste-ready prompt for the implementer

```
You are taking over as implementer for the swing-trading phase9-bundle-A-risk-policy-foundation dispatch.

WORKING DIRECTORY (after worktree creation): c:\Users\rwsmy\swing-trading\.worktrees\phase9-bundle-A-risk-policy-foundation
BRANCH: phase9-bundle-A-risk-policy-foundation
BASELINE_SHA: 700337d  (per dispatch brief §1.1; this is the Codex baseline = HEAD of main BEFORE this brief commit)
WORKTREE-BRANCHING-POINT: current HEAD of main at worktree-creation time (resolve via `git rev-parse main`)

The Codex diff (700337d → worktree HEAD) will include one doc-only commit (this dispatch brief). Harmless; Codex evaluates the IMPLEMENTATION against the PLAN scoped to Sub-bundle A.

Step 0 — Create the worktree:
  cd c:\Users\rwsmy\swing-trading
  $base = git rev-parse main
  git worktree add .worktrees\phase9-bundle-A-risk-policy-foundation -b phase9-bundle-A-risk-policy-foundation $base
  New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active

Step 1 — Read the dispatch brief end-to-end from the worktree:
  docs/phase9-bundle-A-executing-plans-dispatch-brief.md

Step 2 — Read the plan §A (resolved-during-planning, lines 13-216) + §D (Sub-bundle A, lines 304-1515) end-to-end:
  docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md
  Skim §B (file map, lines 218-282) + §C (decomposition, lines 284-302) for cross-bundle context.

Step 3 — Read the spec end-to-end (focus on §3 schema sketches + §4 capture cadence + §5 lifecycle integration):
  docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md
  Use the spec column list at §3.1 as the BINDING artifact for 34-column risk_policy; spec text "28" is brainstorm-miscount.

Step 4 — Read binding conventions:
  - CLAUDE.md (gotchas + project conventions; ALL recent gotcha promotions are forward-binding)
  - docs/orchestrator-context.md (orchestrator-role framing; binding conventions)
  - docs/phase9-writing-plans-dispatch-brief.md §0.3 + §7 (9-lesson catalog FORWARD-BINDING)

Step 5 — Verify worktree state:
  git rev-parse HEAD                                          # expect current main HEAD (typically the dispatch brief commit)
  git status                                                  # expect clean
  python -m pytest -m "not slow" -q                           # expect baseline GREEN (2328 passed, 1 skipped; 3 pre-existing fails NOT regressions)
  python -c "from swing.data.db import EXPECTED_SCHEMA_VERSION; print(EXPECTED_SCHEMA_VERSION)"   # expect 16

Step 6 — Pre-implementation grep recon (Bundle 2+3 lesson applied):
  grep -rn "^def " swing/data/repos/                          # enumerate existing repo patterns
  grep -rn "with conn:" swing/trades/                         # enumerate existing transactional services (do NOT call from inside outer txn)
  grep -rn "INSERT OR REPLACE\|REPLACE INTO" swing/data/      # confirm zero usage (plan §A.8 baseline)
  grep -rn "swing.config.load\|config.load(" swing/           # enumerate all load() call sites (T-A.5 + T-A.6 hook design)
  Capture divergences from plan assumptions; surface in return report.

Step 7 — Invoke copowers:executing-plans (the skill wraps superpowers:subagent-driven-development + adversarial Codex review):
  - PHASE: phase9-bundle-A-risk-policy-foundation
  - SPEC_PATH: docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md
  - PLAN_PATH: docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md
  - BASELINE_SHA: 700337d
  - SCOPE: Sub-bundle A only (tasks T-A.0 through T-A.7 in plan §D); skim §A+§B+§C for context.

Step 8 — TDD per task: failing test → minimal implementation → pass → commit. Per-task `- [ ]` checkboxes in plan §D mark per-step boundaries.

Step 9 — After ALL 8 tasks land + GREEN, run adversarial review per dispatch brief §2.1. Iterate Codex rounds until NO_NEW_CRITICAL_MAJOR. Expected 3-5 rounds.

Step 10 — Draft return report at docs/phase9-bundle-A-return-report.md per dispatch brief §4. Commit it.

Step 11 — Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active + signal orchestrator. Orchestrator drives §3 witnessed verification gate; orchestrator handles integration merge; orchestrator dispatches Sub-bundle B next.

DO NOT:
  - Push to origin from inside the worktree
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer to commits
  - Skip the marker-file removal before invoking copowers
  - Skip the Step 6 pre-implementation grep recon (Bundle 2+3 lesson)
  - Modify the migration file AFTER T-A.1 lands it (atomicity is BINDING)
  - Add cross-bundle code (no reconciliation services; no hypothesis status history service; no account_equity_snapshots service — those are B/C territory)
  - Add UPDATE schema_version statements outside the T-A.1 migration file
  - Call `swing/config.py:load()` with a `conn` parameter (purity contract; plan §A.5.1)
  - Skip the `swing db-migrate` SKIP discipline for the TOML divergence helper (plan §A.5.1 BINDING)
  - Diverge from plan §A locked decisions without explicit Codex justification
  - Re-litigate spec §3 schema sketches (LOCKED at brainstorm time; column LIST is binding artifact)
```

---

## §6 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-11 (post-Phase-9-writing-plans-ship).
- **Brief commit:** `<filled-in-after-commit>`.
- **Brief HEAD context:** `700337d` on main (post-Phase-9-writing-plans-ship housekeeping).
- **Worktree path (binding):** `.worktrees/phase9-bundle-A-risk-policy-foundation/`.
- **Baseline test count:** 2328 fast (1 skipped); 3 pre-existing failures on `tests/integration/test_phase8_pipeline_walkthrough.py` NOT regressions.
- **Baseline ruff count:** 18 (E501 only).
- **Plan status:** SHIPPED 2026-05-11 at `a0c7223`; 2257 lines; 30 tasks; Codex R5 confirmation; 17 §A items + 13 §I watch items.
- **Expected post-dispatch test count:** ~2368-2408 (+40-80; Sub-bundle A is the foundation; subsequent bundles drive the projected +200-320 arc-total).
- **Expected post-dispatch ruff count:** 18 (no change) or lower.
- **Expected schema version post-T-A.1:** 17 (v16 → v17 atomic single-file landing in T-A.1).
- **Sub-bundle B dispatch dependency:** A's migration must merge to main + production DB at v17 before B can dispatch. Orchestrator commissions B after operator-witnessed gate PASS + integration merge.
- **Phase 9 arc total:** Sub-bundles A+B+C+D+E expected ~50-80 hr implementation + Codex; Sub-bundle A is ~14-20 hr (largest).
