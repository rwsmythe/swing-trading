# Phase 9 — writing-plans dispatch brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Convert the Phase 9 (Risk_Policy + Reconciliation Depth) brainstorm spec into an executable implementation plan via `copowers:writing-plans`. The skill wraps `superpowers:writing-plans` + adversarial Codex MCP review. Output is a single plan file (per the writing-plans convention) that the orchestrator subsequently dispatches via `copowers:executing-plans` — typically as multiple sub-bundles given Phase 9's schema + lifecycle complexity.

**Expected duration:** ~4-6 hr planning + ~2-3 hr Codex convergence. Total ~6-9 hr (matches Phase 8 writing-plans + Phase 8 V1 polish writing-plans precedent).

---

## §0 Inputs

### §0.1 Spec
- **SPEC_PATH:** `docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md`
- **Spec status:** Codex R1 (8M/5m) → R2 (6M/3m) → R3 (4M/3m) → R4 (0C/0M/3m, NO_NEW_CRITICAL_MAJOR) → R5 (0/0/0 confirmation). Convergent chain shipped 2026-05-06 at `31ee51c`. 1090 lines.
- **Spec produces** (per §1.1): five new tables (`risk_policy`, `reconciliation_runs`, `reconciliation_discrepancies`, `hypothesis_status_history`, `account_equity_snapshots`); modifications to two shipped tables (`trades` adds `risk_policy_id_at_lock`; `review_log` — see §5.1 of spec for the JOIN-side surface, no column add); capture cadence (§4); lifecycle integration with Phase 6/7/8 (§5); TOS-reconciliation-depth bundle subsumption (§6); sector/industry tamper hardening (§7); Schwab API Phase A coordination boundary (§8); migration strategy v16 → v17 (§9); open questions for orchestrator triage (§10); Phase 10 hand-off (§11).
- **Spec deliberately does NOT produce** (per §1.2): migration SQL drafts; code drafts; task decomposition into dispatches (← THAT IS WRITING-PLANS' JOB); Schwab API library evaluation; Schwab API auth design; fractional-shares schema; `trade.entry_date` datetime promotion; Phase 10 dashboard layer.

### §0.2 Project state at dispatch time
- **HEAD on `main`:** `88c7d6b` (post-3e.8-Bundle-3-ship housekeeping).
- **Test count:** 2328 fast (1 skipped); 3 pre-existing failures on `tests/integration/test_phase8_pipeline_walkthrough.py` ("archive returned None"; NOT related to Phase 9 scope).
- **Ruff baseline:** 18 (E501 only).
- **Schema version:** v16 (Phase 8 daily_management shipped). Phase 9 bumps v16 → v17.
- **3e.8 advisory-expansion arc CLOSED:** Bundles 1+2+3 shipped 2026-05-11 (advisory parity + 3 sell-side rules + 2 maturity/M.2 rules); 11-rule advisory surface; 6 composition sites.

### §0.3 Bundle 1+2+3 lessons inherited (BINDING for Phase 9 writing-plans)
The following Codex-caught lessons banked at `docs/phase3e-todo.md` "2026-05-11 V2 watch items + lessons banked" sections are forward-binding:

1. **6-site composition-surface enumeration via `^def` grep, NOT memory-enumerate.** Phase 9 introduces multiple new services (risk_policy CRUD; reconciliation_runs orchestration; hypothesis_status_history append; account_equity_snapshots manual capture). Plan must enumerate ALL call sites for each service via definition-scoped grep when surfacing acceptance criteria.

2. **Price-independent vs price-dependent split (advisory-degradation pattern).** `compute_price_independent_suggestions` is the canonical pattern. Phase 9's metric surfaces (e.g., live `risk_policy` read at dashboard render) are DB-sourced, NOT PriceCache-dependent — classify accordingly if Phase 10 hand-off (§11.1) touches advisory composition.

4. **`__post_init__` validator pattern for new dataclasses** (Bundle 2 R3 Major #1 + Bundle 3 mirror). Phase 9's `risk_policy` is a candidate for a dataclass mirror with same NaN/inf/out-of-range rejection if exposed via cfg-layer.

5. **Service-layer `with conn:` opens its own transaction — do NOT call from inside outer single-transaction.** Phase 9's reconciliation flow may compose multiple side-effects (insert run + insert discrepancies + emit material-to-review notice). MUST call repo-level functions, not service-level wrappers (per CLAUDE.md gotcha + Phase 8 Codex R3→R4 cascade). Plan MUST enumerate the transaction boundary contract per service.

6. **SQLite `executescript()` issues implicit COMMIT.** Phase 9's v16→v17 migration runs through the canonical migration runner (`swing/data/db.py:_apply_migration`); same discipline as Phase 7+8.

7. **`INSERT OR REPLACE` is DELETE+INSERT, NOT UPDATE.** Phase 9's append-only `hypothesis_status_history` MUST use SELECT-then-UPDATE-or-INSERT (or pure INSERT for new transitions) per CLAUDE.md gotcha; NEVER REPLACE on tables with FK-referenced PKs (Phase 8 lesson 2026-05-06).

8. **Session-anchor read/write mismatch.** Phase 9's `reconciliation_runs.period_end` semantics + `account_equity_snapshots.snapshot_date` are session-anchored; plan must enumerate `last_completed_session(now)` vs `action_session_for_run(now)` for each read site. Spec §10.1 + §10.6 reference this directly.

9. **For any V1 single-operator form with hidden audit fields, default to SERVER-STAMPING at handler entry.** Phase 9's V1 CLI surface for `risk_policy` editing (§10.5) and account_equity_snapshot capture should follow this — `created_at` / `effective_from` server-stamped, not operator-supplied.

### §0.4 Open questions disposition

Spec §10 enumerates 6 open questions. Writing-plans MAY default to brainstorm recommendations OR surface a divergence:

| Question | Brainstorm recommendation | Writing-plans posture |
|---|---|---|
| §10.1 reconciliation_run period_end for account-state pulls | `last_completed_session(now)`; operator override | Defer to Schwab Phase A; Phase 9 ships TOS-CSV path only. |
| §10.2 sector_tamper hard-gate elevation trigger | Operator-decision; advisory in V1; defer field add | Lock V1 advisory disposition; flag V2 follow-up. |
| §10.3 reconciliation_runs retention | Retain all forever | Accept. |
| §10.4 hypothesis_status_history seed effective_from | `hypothesis_registry.created_at` (locked in §3.4.1) | Accept locked position. |
| §10.5 V1 CLI surface for risk_policy editing | Per-field CLI; bulk + web deferred to V2 | Writing-plans codifies. |
| §10.6 reconciliation_run period_end vs source artifact date | Operator-passed via CLI flag; default last-fill-date | Writing-plans codifies CLI default. |

**Plan posture:** if writing-plans agrees with all brainstorm recommendations, document acceptance per question in the plan §A (resolved-during-planning) section. If divergence on any question, surface it explicitly with rationale.

---

## §1 Output

### §1.1 Plan file
- **PLAN_PATH:** `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md`
- **Format:** mirrors prior plan files (e.g., `docs/superpowers/plans/2026-05-06-phase8-daily-management-plan.md`):
  - Goal + Architecture + Tech Stack header
  - §A Resolved-during-planning (empirical-audit findings; spec ambiguity disposition)
  - §B-onward: Per-task breakdown with checkbox-tracked steps (`- [ ]`)
  - Per-task: acceptance criteria, suggested tests, suggested commit shape, watch items
  - §J Cross-references + grep verifications

### §1.2 Plan task decomposition expectation

Phase 9 scope is LARGE (5 tables + 2 cross-cutting modifications + migration + lifecycle integration + tamper hardening). Writing-plans anticipated to decompose into **3-5 sub-bundles** for executing-plans dispatch:

**Suggested decomposition (non-binding; writing-plans makes the final call):**

- **Sub-bundle A — risk_policy + migration foundation.** Schema sketch §3.1 → migration `0017_phase9_risk_policy.sql`; new `swing/data/repos/risk_policy.py`; cfg-toml seed at `policy_id=1`; CLI per-field UPDATE (§10.5); read surface for `risk_policy.is_active=1`. Bumps v16 → v17. (~12-16 hr.)
- **Sub-bundle B — reconciliation_runs + reconciliation_discrepancies + TOS-CSV reconciliation depth.** Schema sketches §3.2 + §3.3; new `swing/data/repos/reconciliation.py`; TOS-CSV ingestion service extension; `material_to_review` classification + `MATERIAL_BY_TYPE` lookup. (~14-18 hr.)
- **Sub-bundle C — hypothesis_status_history + account_equity_snapshots.** Schema sketches §3.4 + §3.5; append-only history triggers (or service-layer enforcement per §3.4.1); snapshot CLI capture; integration with Phase 8's `position_capital_utilization_pct`. (~10-14 hr.)
- **Sub-bundle D — sector/industry tamper hardening + trades.risk_policy_id_at_lock stamp.** Route-layer rejection mirroring chart_pattern hardening (commits `117dc97` + `2b9d6f3`); trades-table column add + Phase 7 lock-time stamp wire. (~6-10 hr.)
- **Sub-bundle E (optional consolidation) — final polish + Phase 10 hand-off prep.** Cross-cutting wire-through; final integration tests; cfg-toml seed migration. (~4-8 hr.)

Writing-plans MAY recommend a different decomposition (e.g., fewer larger bundles, or different ordering). Plan should explain decomposition rationale + flag any cross-bundle dependencies.

---

## §2 Worktree + binding conventions

### §2.1 Worktree
- **Branch:** `phase9-writing-plans`
- **Worktree directory:** `.worktrees/phase9-writing-plans/`
- **BASELINE_SHA:** `88c7d6b` (current main HEAD).
- **Worktree branching point:** current HEAD of `main` at worktree-creation time (resolve via `git rev-parse main`; expected the brief commit SHA after this brief lands).

### §2.2 Marker-file workflow
- After worktree creation: `New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active`
- After plan + Codex chain converges + before final commit: `Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active`

### §2.3 Commits
- Conventional prefix:
  - `docs(phase9): Phase 9 writing-plans — <description>` for the plan file
  - `docs(phase9): Phase 9 writing-plans — Codex RN fix — <description>` for Codex-driven plan refinements
- **NO Claude co-author footer**, **NO `--no-verify`**, **NO `--amend`**.
- Final commit: the plan file at `docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md`.

### §2.4 Branch isolation + ownership
- Commits on branch only; no push to origin from worktree.
- **Implementer (you) owns:** copowers:writing-plans invocation → Codex iteration → plan commit → return report.
- **Orchestrator owns:** plan triage + integration merge to main + executing-plans dispatch commissioning (one or more bundles).

### §2.5 Verify command (basic; the writing-plans skill handles full Codex review)
```powershell
# After plan landed:
git log --oneline HEAD~5..HEAD
git diff --stat HEAD~1..HEAD
ls docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md
```

---

## §3 Skill posture + adversarial review

- **Invoke `copowers:writing-plans`** (NOT `superpowers:writing-plans` directly — the copowers wrapper handles Codex review automatically).
- Skill inputs:
  - `SPEC_PATH=docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md`
  - `PLAN_PATH=docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md`
  - `BASELINE_SHA=88c7d6b`
- **Expected Codex chain:** 3-5 rounds (matches Phase 8 writing-plans pattern: 2 Codex rounds + Phase 7 Sub-A 3 rounds; Phase 9 spec complexity sits between).
- Iterate per-round fixes as `docs(phase9): Phase 9 writing-plans — Codex RN fix — ...` commits.
- Terminate at NO_NEW_CRITICAL_MAJOR.

### §3.1 Codex value-add concentration

Adversarial review for writing-plans typically catches:
- **Schema-spec divergence** — plan's task-spec column lists differ from spec §3.x in subtle ways (missing column, wrong CHECK, wrong default seed).
- **Migration-runner discipline gaps** — plan misses `executescript()` discipline or PRAGMA foreign_keys=OFF gating.
- **Cross-table FK ordering** — plan creates `reconciliation_discrepancies` before `reconciliation_runs` (FK target absent).
- **Migration filename / number collision** — Phase 8 plan hit this in Codex R1 Critical #1 (§A.0 of `2026-05-06-phase8-daily-management-plan.md`); verify Phase 9 filename is `0017_*` not `0016_*` (which is Phase 8's; current EXPECTED_SCHEMA_VERSION = 16).
- **Lifecycle-integration boundary** — plan-task acceptance criteria omits Phase 7 state-transition discipline or Phase 8 daily_management cross-link.
- **CLI flag defaults** — plan codifies wrong default for `--period-end` per §10.6.
- **Hypothesis status history seed effective_from policy** — plan diverges from spec §10.4 + §3.4.1.
- **Sector tamper hardening route-layer integration** — plan's task-spec misses route-layer rejection (chart_pattern hardening precedent).

### §3.2 Plan task decomposition Codex check

Codex should specifically verify:
- Each new table has its own dedicated task family (no half-mixed schema work).
- Each repo function has explicit acceptance criteria (CRUD shapes; transaction boundary; SELECT-then-UPDATE-or-INSERT for UPSERT cases).
- Each service has explicit transaction-ownership contract (caller-controlled at repo layer; transaction-owning at service layer; reject-caller-held-tx at any new single-transaction service).
- TOS-CSV reconciliation extension's existing fill-matching path is referenced + reused (per spec §6 subsumption mapping).

---

## §4 Return report shape

After Codex chain converges + plan committed on worktree branch, draft a return report at `docs/phase9-writing-plans-return-report.md` (mirroring `docs/3e8-bundle-3-return-report.md` shape but writing-plans-flavored):

1. Final HEAD on branch.
2. Commit count breakdown (plan-write + Codex-fix).
3. Codex round chain (e.g., "R1 0/X/Y → R2 ... → Rn NO_NEW_CRITICAL_MAJOR").
4. Plan task decomposition rationale (number of sub-bundles, ordering, cross-bundle dependencies).
5. §10 open-questions disposition (per question: accept-brainstorm-recommendation OR diverge-with-rationale).
6. Codex Major findings ACCEPTED with rationale (if any).
7. §A resolved-during-planning summary (empirical findings discovered during writing-plans).
8. Watch items for orchestrator (anything the orchestrator must lock before executing-plans dispatch).
9. Worktree teardown status (expected ACL-locked husk per Phase 6/7/8/Bundles-1+2+3 pattern; will be the 6th husk in the current batch).

---

## §5 First-step paste-ready prompt for the implementer

```
You are taking over to draft the Phase 9 (Risk_Policy + Reconciliation Depth) implementation plan for swing-trading.

WORKING DIRECTORY (after worktree creation): c:\Users\rwsmy\swing-trading\.worktrees\phase9-writing-plans
BRANCH: phase9-writing-plans
BASELINE_SHA: 88c7d6b  (per dispatch brief §2.1; this is the Codex baseline = HEAD of main BEFORE this brief commit)
WORKTREE-BRANCHING-POINT: current HEAD of main at worktree-creation time (resolve via `git rev-parse main`)

The Codex diff (88c7d6b → worktree HEAD) will include one or more doc-only commits (the dispatch brief + plan + Codex fixes). All harmless; Codex evaluates the PLAN content against the SPEC.

Step 0 — Create the worktree:
  cd c:\Users\rwsmy\swing-trading
  $base = git rev-parse main
  git worktree add .worktrees\phase9-writing-plans -b phase9-writing-plans $base
  New-Item -ItemType File c:\Users\rwsmy\swing-trading\.copowers-subagent-active

Step 1 — Read the dispatch brief end-to-end from the worktree:
  docs/phase9-writing-plans-dispatch-brief.md

Step 2 — Read the Phase 9 brainstorm spec end-to-end:
  docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md
  (1090 lines; Codex R5 confirmation; locked schema sketches + cadence + lifecycle + open questions §10)

Step 3 — Read binding conventions:
  - CLAUDE.md (gotchas + project conventions; "Lessons captured" + recent gotcha promotions are forward-binding)
  - docs/orchestrator-context.md (orchestrator-role framing; binding conventions)
  - docs/phase3e-todo.md sections "2026-05-11 V2 watch items + lessons banked from 3e.8 Bundle 2 ship" + "2026-05-11 V2 watch items + lessons banked from 3e.8 Bundle 3 ship" (Bundles 1+2+3 lessons; FORWARD-BINDING per §0.3 of this dispatch brief)

Step 4 — Verify worktree state:
  git rev-parse HEAD                       # expect current main HEAD (typically the dispatch brief commit)
  git status                               # expect clean
  python -m pytest -m "not slow" -q        # expect baseline GREEN (2328 passed, 1 skipped; 3 pre-existing fails in tests/integration/test_phase8_pipeline_walkthrough.py NOT regressions)
  cat swing/data/db.py | grep EXPECTED_SCHEMA_VERSION   # expect 16

Step 5 — Pre-plan recon (orchestrator-applied lessons from Bundle 2+3):
  grep -rn "^def " swing/data/repos/        # enumerate existing repo functions; Phase 9 adds new repos under same pattern
  grep -rn "with conn:" swing/trades/       # enumerate Phase 7+8 transactional services (DO NOT call from inside outer txn)
  grep -rn "executescript" swing/data/      # enumerate migration runner discipline sites
  grep -rn "INSERT OR REPLACE\|REPLACE INTO" swing/data/   # confirm zero usage post-Phase-8 gotcha
  Capture any divergences from the spec's design assumptions; surface in plan §A.

Step 6 — Invoke copowers:writing-plans (the skill wraps superpowers:writing-plans + Codex review):
  - SPEC_PATH: docs/superpowers/specs/2026-05-06-phase9-risk-policy-reconciliation-design.md
  - PLAN_PATH: docs/superpowers/plans/2026-05-11-phase9-risk-policy-reconciliation-plan.md
  - BASELINE_SHA: 88c7d6b

Step 7 — Iterate Codex rounds + land plan-refinement commits until NO_NEW_CRITICAL_MAJOR. Expected 3-5 rounds.

Step 8 — Draft return report at docs/phase9-writing-plans-return-report.md per dispatch brief §4. Commit it.

Step 9 — Remove-Item c:\Users\rwsmy\swing-trading\.copowers-subagent-active + signal orchestrator. Orchestrator triages the plan + commissions executing-plans (typically multiple bundles per §1.2 decomposition).

DO NOT:
  - Push to origin from inside the worktree
  - Merge to main (orchestrator action)
  - Use --amend or --no-verify
  - Add Claude co-author footer to commits
  - Skip the marker-file removal before final signal
  - Skip the Step 5 pre-plan grep recon (Bundles 2+3 lesson)
  - Write any code drafts (migration SQL, services, repos) — those are executing-plans territory, NOT writing-plans
  - Diverge from spec §3 schema sketches without explicit Codex justification in plan §A
  - Re-litigate spec §1 strategic context (accepted as binding per spec §1.2)
  - Add Schwab API code or auth design (out of Phase 9 scope per spec §1.2 + §1.6)
  - Bundle this with Phase 10 (Phase 9 ships first per locked sequencing 8 → 9 → 10)
```

---

## §6 Dispatch metadata

- **Brief author:** Orchestrator session 2026-05-11 (post-3e.8-Bundle-3-ship).
- **Brief commit:** `<filled-in-after-commit>`.
- **Brief HEAD context:** `88c7d6b` on main (post-3e.8-Bundle-3-ship housekeeping).
- **Worktree path (binding):** `.worktrees/phase9-writing-plans/`.
- **Baseline test count:** 2328 fast (1 skipped); 3 pre-existing failures on `tests/integration/test_phase8_pipeline_walkthrough.py` NOT regressions.
- **Baseline ruff count:** 18 (E501 only).
- **Spec status:** Codex R1-R4 + R5 confirmation; shipped 2026-05-06 at `31ee51c`; 1090 lines; LOCKED.
- **Expected plan size:** 1000-1500 lines (mirrors Phase 8 plan + Phase 7 Sub-A scale; Phase 9 spec is larger so plan will be too).
- **Expected sub-bundle count for executing-plans dispatch:** 3-5 (orchestrator-decision after plan triage).
- **Next per locked sequencing 8 → 9 → 10:** Phase 9 plan ships → orchestrator dispatches Sub-bundle A → ... → Sub-bundle N → Phase 10 writing-plans.

---

## §7 Lessons forward-bound from prior dispatches (CRITICAL — DO NOT skip)

Re-emphasized from §0.3 because the Codex chain on Phase 9 writing-plans WILL test whether the plan respects these:

| Lesson | Bundle source | Phase 9 application |
|---|---|---|
| Composition surface enumeration via `^def` grep | Bundle 2+3 | Plan must grep new repo/service signature definitions; not memory-enumerate. |
| Price-independent vs price-dependent advisory split | Bundle 3 | Phase 10 hand-off note (§11) — plan need not deeply integrate but should flag the pattern. |
| `__post_init__` validator pattern | Bundle 2+3 | If risk_policy gets cfg-layer dataclass mirror, apply pattern. |
| Service-layer `with conn:` opens its own transaction | Phase 8 | Plan MUST enumerate transaction-ownership contract per new service; reject-caller-held-tx for single-transaction services. |
| `executescript()` discipline | Phase 7 hotfix | Plan inherits via `swing/data/db.py:_apply_migration`; no carve-out. |
| `INSERT OR REPLACE` is DELETE+INSERT not UPDATE | Phase 8 gotcha 2026-05-06 | Append-only hypothesis_status_history MUST use INSERT (or SELECT-then-UPDATE-or-INSERT for UPSERT cases). |
| Session-anchor read/write mismatch | Phase 8 polish bundle 2026-05-09 | Plan must enumerate `last_completed_session(now)` vs `action_session_for_run(now)` per session-keyed column. |
| Server-stamping hidden audit fields | Phase 8 R2.M2 + R3.M2 + R4.M2 | risk_policy `created_at` / `effective_from` MUST be server-stamped. |
| Migration filename collision check | Phase 8 plan §A.0 (Codex R1 Critical #1) | Plan §A MUST verify migration filename `0017_*` matches `EXPECTED_SCHEMA_VERSION = 16 → 17`. |

All of these are FAILURE-MODE-CATALOGUED. The Codex chain will catch any plan omission against this list; the implementer's pre-plan grep recon (Step 5) is the structural defense.
