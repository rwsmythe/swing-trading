# Phase 7 Sub-B — Services + CLI + Journal Predicate Rewrites — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Sub-B of `docs/superpowers/plans/2026-05-04-phase7-trade-lifecycle-state-machine-plan.md` end-to-end. Sub-A SHIPPED 2026-05-04 on worktree branch `phase7-sub-a-schema` (HEAD `78c7005`); Sub-B chains from Sub-A's HEAD per operator-decided chained-branch posture (binding-green-gate-vs-carve-out conflict resolution). Sub-C is the final dispatch in the chain; integration `git merge --no-ff phase7-sub-c-web` to main happens only after Sub-C ships.

**Scope:** Sub-B only (Tasks B.1-B.9 = 9 tasks per plan §5). Owns service-layer rewrites (entry/exit/stop_adjust/review services); CLI predicate + display + new-options rewrites; journal predicate rewrites (stats.py, flags.py, analyze.py, tos_import.py); shim removal trigger at T4. Sub-C (web view models + templates + state-badge partial + entry-form expansion + operator-witnessed browser verification gate) is a SEPARATE FUTURE dispatch.

**Expected duration:** ~4-7 hours including 2-4 Codex rounds. ~50 expected new tests (per plan §5 estimate; per Phase 6 lesson "test-count-projections-bias-high" the actual count may run higher; that's acceptable IF discriminating-test discipline justifies it).

**Dispatch type:** **Direct invocation of `superpowers:subagent-driven-development` followed by `copowers:adversarial-critic`** (NOT the `copowers:executing-plans` wrapper). Worktree isolation + global PreToolUse Codex-blocking hook both in effect — see §0 Skill posture for the 7-step workflow. Same pattern as Phase 6 + Phase 5 + Sub-A executing-plans dispatches.

---

## §0 Read first

Read these in order before executing:

1. **`docs/superpowers/plans/2026-05-04-phase7-trade-lifecycle-state-machine-plan.md`** — THE PLAN. ~4172 lines. Source of truth for task partitioning, per-task acceptance criteria, test specifications, file paths. Pay particular attention to:
   - **§0** sub-dispatch ordering, worktree posture, BASELINE_SHAs, marker-file workflow.
   - **§1** vocabulary lists (CONFIRMED 2026-05-04; values embedded in migration 0014 CHECK enums; do NOT re-litigate).
   - **§2.1** status→state per-call-site predicate rewrite mapping. Sub-B T1-T9 owns rewrites where the §2.1 column shows "Sub-B T1/T6/T7/T9". Sub-A entries are LANDED on the chained branch already; Sub-C entries are NOT yet — leave those for Sub-C.
   - **§2.3** broadened grep refresh — re-run at dispatch time + after every Sub-B task to catch any plan-time-missed call sites.
   - **§3** carve-out enumeration; Sub-B's subset.
   - **§5** Sub-B task list (B.1-B.9): entry validator/origin/atomic-fill (T1-T3); exit (T4 — also shim removal trigger); stop-adjust (T5); review (T6); CLI options/display (T7); journal predicate rewrites (T9).
   - **§7** test strategy + +150-250 wide band (across all of Phase 7; Sub-B's projected ~50).
   - **§8** done criteria + return report format.

2. **`docs/superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md`** — the spec the plan implements. ~1069 lines. The plan is the implementation contract; if the plan's task body diverges from the spec, the plan wins. Surface any irreconcilable divergence in your return report; do NOT silently re-design.

3. **`docs/phase7-sub-a-schema-executing-plans-brief.md`** — Sub-A's executing-plans brief. Sub-A landed schema migration 0014 + repos + state service + origin + derived_metrics + 4-fixture preservation invariant + in-flight migration of VIR/DHC/CC/YOU. Sub-B builds on that foundation.

4. **`docs/phase7-trade-lifecycle-state-machine-writing-plans-brief.md`** — the writing-plans brief that drove the plan. Locked decisions (§2), open-questions-resolved-in-plan (§3), 21 adversarial-review watch items (§5).

5. **`docs/phase7-trade-lifecycle-state-machine-brainstorm-brief.md`** — the brainstorm brief that drove the spec. §2 hard-conflict escape carries forward to executing-plans (see §8 below).

6. **`CLAUDE.md`** at repo root — gotchas to pre-empt. Sub-B touches CLI + services + journal (no web). Active gotchas for Sub-B:
   - **`os.replace` cross-device-link** — applies to atomic-write paths if any new file-write helpers added; backups stay on same volume.
   - **`pipeline_runs` ORDER BY mask** — applies if journal predicate rewrites touch evaluation_runs aggregation queries.
   - **Python `... or ""` vs `... or None` for nullable CHECK columns** (2026-05-04 gotcha) — applies to entry service form-fallback paths if any nullable text column with CHECK enum gets a fallback. Use `... or None` per the binding pattern.
   - **HTMX gotchas + base-layout VM rule** — Sub-B does NOT touch web; skip these. Sub-C will handle.
   - **TestClient lifespan** — Sub-B does NOT touch web routes; skip.

7. **`docs/orchestrator-context.md`** — focus on:
   - §"Currently in-flight work" — Phase 7 row reflects Sub-A SHIPPED on worktree + chained-branch posture for Sub-B/Sub-C.
   - §"Binding conventions" — 4-tier commit-message convention; subject-only ERE grep observable verification; no-amend; no Claude footer; ruff baseline 80 (carried forward from Sub-A); worktree+editable-install verify-command convention; no-main-commits-during-in-flight-dispatch (lesson 2026-05-04).
   - §"Lessons captured" — particularly the **Phase 7 Sub-A** lessons just captured 2026-05-04:
     - **Binding green gate at sub-dispatch boundary is impossible if cross-cutting predicate rewrites are deferred to later sub-dispatches.** Sub-B's done criteria gate is **partial-suite-green** (Sub-A-owned + Sub-B-owned tests GREEN; Sub-C-owned tests may still be RED until Sub-C ships); NOT full-suite-green at end of Sub-B.
     - **SQLite `executescript()` rollback discipline.** Sub-A's migration runner now wraps `executescript`+`commit` in try/except with rollback. Sub-B inherits this pattern; any new schema-touching path follows it.
     - **Backup-gate condition tightness.** Sub-A's backup gate fires only when `current_version == 13 AND target >= 14`. Sub-B does NOT add new schema migrations; the backup gate is preserved untouched.
     - Plus Phase 7 brainstorm lessons: state-bearing entity validation distinguishes operation enforcement from data invariant; status→state predicate rewrite is NOT uniform substitution.

8. **Production DB state verification** — at dispatch time, run from MAIN's working tree (NOT Sub-B's worktree) to confirm production hasn't drifted:
   ```python
   import sqlite3, os
   conn = sqlite3.connect(os.path.expanduser("~/swing-data/swing.db"))
   for ticker in ('VIR', 'DHC', 'CC', 'YOU'):
       trade = conn.execute("SELECT id, ticker, status, entry_date, entry_price, initial_shares, hypothesis_label FROM trades WHERE ticker = ?", (ticker,)).fetchone()
       print(f'{ticker}: {trade}')
   print('exits:', conn.execute("SELECT * FROM exits").fetchall())
   print('schema_version:', conn.execute("SELECT * FROM schema_version").fetchall())
   ```
   Expected: 4 trades (VIR closed+reviewed; DHC + CC + YOU open) + 1 exit (VIR's) + **schema_version=13** (Sub-A NOT yet merged to main per chained-branch posture). If state diverges (e.g., 5 trades, schema=14), STOP and surface in return report — Sub-A's worktree was supposed to keep main untouched until final integration.

9. **Sub-A worktree state verification** — confirm Sub-A worktree is intact:
   ```bash
   git worktree list
   ```
   Expected output includes `.worktrees/phase7-sub-a-schema  78c7005 [phase7-sub-a-schema]`. If Sub-A worktree is missing or HEAD differs from `78c7005`, STOP and surface — the chained-branch posture requires Sub-A worktree intact for Sub-B's branch to chain from.

If any file path above doesn't resolve, verify via `Glob`/`Grep` before executing the plan task.

---

## §0 Skill posture (7-step workflow — execute in order)

**Step 1 — Create chained worktree from Sub-A's HEAD.** INVOKE `superpowers:using-git-worktrees` to create an isolated worktree on a NEW branch `phase7-sub-b-services` based on **Sub-A's branch HEAD `78c7005`** (NOT main HEAD).

The git command for the chained-branch posture:

```bash
git worktree add -b phase7-sub-b-services .worktrees/phase7-sub-b-services phase7-sub-a-schema
```

This creates `phase7-sub-b-services` branch starting from Sub-A's HEAD; the new worktree at `.worktrees/phase7-sub-b-services/` will see Sub-A's 14 commits already landed. All your work commits onto `phase7-sub-b-services` and stacks on top of Sub-A's commits.

REQUIRED per `superpowers:subagent-driven-development` skill docs AND per orchestrator-context binding-convention 2026-05-02 (worktree isolation default for any plan with >5 task commits OR substantial schema changes; Sub-B inherits from Sub-A which hits both).

**Step 2 — Activate the Codex-blocking marker.** From within the worktree: `touch .copowers-subagent-active`. This activates the global PreToolUse hook (`~/.claude/hooks/block-copowers-during-subagent.sh`, registered in `~/.claude/settings.json`) which physically blocks subagent invocation of `copowers:adversarial-critic`, `copowers:review`, `mcp__plugin_copowers_codex__codex`, `mcp__plugin_copowers_codex__codex-reply`. Hook is harness-level and cannot be bypassed by subagent reasoning.

**Step 3 — Invoke subagent-driven-development DIRECTLY** (NOT via `copowers:executing-plans` wrapper):

- **INVOKE** `superpowers:subagent-driven-development` and execute Tasks B.1-B.9 per the plan. Subagents will physically be unable to invoke Codex/copowers review while the marker is active.
- **DO NOT INVOKE** `copowers:executing-plans` — bundles both phases without marker management.
- **DO NOT INVOKE** `copowers:adversarial-critic`, `copowers:review`, `mcp__plugin_copowers_codex__codex`, or `mcp__plugin_copowers_codex__codex-reply` from within subagent dispatches. Hook blocks; explicit prohibition is belt-and-suspenders.
- **DO NOT INVOKE** `superpowers:brainstorming` / `copowers:brainstorming` — design is locked at spec `c926f01`.
- **DO NOT INVOKE** `copowers:writing-plans` / `superpowers:writing-plans` — plan is locked at `251cc35`. If you find a plan task is impossible to implement as written, STOP and surface in the return report; do NOT silently re-plan.

**Step 4 — Remove marker.** After all subagent-driven-development tasks complete + final code reviewer approves: `rm .copowers-subagent-active`. Verify: `ls .copowers-subagent-active` → `No such file`.

**Step 5 — Invoke Codex adversarial review.** INVOKE `copowers:adversarial-critic` directly with:
- `PHASE`: `executing-plans`
- `SPEC_PATH`: `docs/phase7-sub-b-services-executing-plans-brief.md` (this brief)
- `PLAN_PATH`: `docs/superpowers/plans/2026-05-04-phase7-trade-lifecycle-state-machine-plan.md`
- `BASELINE_SHA`: `78c7005` (Sub-A worktree HEAD = Sub-B's chained baseline; review covers all Sub-B worktree commits since this base)

Iterate Codex rounds to `NO_NEW_CRITICAL_MAJOR`. Internal-Codex pre-emption (commit message qualifier `(internal)`) is encouraged; saves orchestrator-Codex round budget. Expect 2-4 rounds.

**Step 6 — Verification gate (PARTIAL-SUITE green; NOT full-suite green).** Sub-B does NOT close all of Phase 7's RED tests — Sub-C (web view models, templates) is a separate future dispatch and its tests stay RED until Sub-C ships. Verification for Sub-B:
- **Sub-A-owned tests**: REMAIN GREEN (no regressions to schema/repos/state-machine layer; verify by re-running tests for `tests/data/`, `tests/trades/test_state.py`, `tests/trades/test_origin.py`, `tests/trades/test_derived_metrics.py`, `tests/data/test_migration_0014.py`, etc. that Sub-A added).
- **Sub-B-owned tests**: GREEN (entry/exit/stop_adjust/review service tests; CLI tests touched by predicate rewrites; journal stats/flags/analyze/tos_import tests).
- **Sub-C-owned tests**: MAY STILL BE RED — that's expected and is Sub-C's job to close. Document the count in the return report.
- **No NEW production-code paths broken** beyond what Sub-A's shims already broke. Sub-B's shim removals (T4) replace shimmed APIs with real-fills consumers in journal/CLI/services; web (Sub-C territory) keeps its existing references — track via per-task test-delta accounting.
- Test count delta: ~+50 new (vs plan §5 estimate; bias-high acceptable).
- Ruff baseline ≤80 (current at chained-baseline `78c7005`).

**Step 7 — Prepare next-dispatch handoff (NO MERGE TO MAIN).** Sub-B does NOT merge to main per the chained-branch posture. Surface in the return report:
- Sub-B worktree branch HEAD SHA (this becomes Sub-C's chained baseline).
- Sub-C pre-conditions checklist (vocabulary already locked; production DB still at v13; Sub-C dispatches from `phase7-sub-b-services`).
- Worktree merge command for the FINAL integration is at end of Sub-C, not here.

---

## §1 Strategic context (compressed)

Phase 7 ships the trade lifecycle state machine + Fills first-class. Sub-A landed the data-layer foundation (schema migration + state service + Fills repo + in-flight VIR/DHC/CC/YOU migration). Sub-B is the service + CLI + journal layer that consumes Sub-A's foundation: entry/exit/stop_adjust/review services rewritten to route through state.py state service; CLI commands updated for new pre-trade fields + state-aware display + new-options; journal stats/flags/analyze/tos_import predicate rewrites for the dropped `trades.status` column.

**Why Sub-B second:** Sub-C (web/UX) consumes Sub-B's service layer (web routes call `record_entry()`, `record_exit()`, etc.). Shipping Sub-B as a discrete chained dispatch with partial-suite-green at end means Sub-C can dispatch from a clean Sub-B base without inheriting half-written service work.

**What ships in this dispatch (per plan §5):**

- **`swing/trades/entry.py`** rewrite (T1-T3): atomic trade+entry-fill+pre_trade_locked_at flow; route through `swing/trades/state.py:state_transition()` for the implicit `entered → managing` transition; `MissingPreTradeFieldsException` gate validates required pre-trade fields per spec §10.1; `EntryPath` enum on `EntryRequest` per spec §10.4; `derive_trade_origin()` from `swing/trades/origin.py` consumed at entry time. Also: defensive docstring on `swing/data/repos/trades.py:insert_trade_with_event()` warning callers MUST follow up with entry-fill insert (R2 Minor 1 from Sub-A return; deferred to Sub-B T1 per operator decision).
- **`swing/trades/exit.py`** rewrite (T4 — also shim removal trigger): consume `swing/data/repos/fills.py:insert_fill_with_event()` directly; route exit transitions through state service (`managing → closed` for full exit; `managing → partial_exited` for partial); same-day stop-out as atomic double-transition (`entered → managing → closed`) per spec §3.2. **Begin shim deletion**: `_ExitLikeRow` NamedTuple shim + `Exit` class stub progressively removable as exit service no longer needs them. Full deletion completes at Sub-C T1 (web view models — final consumer); Sub-B T4 commits the FIRST removal step (exit service migration to fills consumer).
- **`swing/trades/stop_adjust.py`** rewrite (T5): predicate rewrite (active-trade filter `state IN ('entered','managing','partial_exited')`); route first-stop-trigger through state service (`entered → managing` if first stop-adjust on a freshly-entered trade); existing `update_stop_with_event` repo helper integrated.
- **`swing/trades/review.py`** rewrite (T6): predicate rewrite (closed-but-not-reviewed `state == 'closed'` only — must reject already-reviewed `state == 'reviewed'`; per spec §5.2 + Phase 7 brainstorm lesson "naïve `state IN ('closed','reviewed')` would let already-reviewed trades through review again"); route review transition through state service (`closed → reviewed`).
- **`swing/cli.py`** updates (T7): predicate rewrites at lines noted in plan §2.1 (cli.py:1008 review-precondition; cli.py:588 display); new CLI options for pre-trade fields per plan §5 T7 (premortem inputs; thesis fields; emotional_state multi-select; manual_entry_confidence radio-equivalent CLI arg).
- **`swing/journal/stats.py`** + **`swing/journal/flags.py`** + **`swing/journal/analyze.py`** + **`swing/journal/tos_import.py`** predicate rewrites (T9): closed-or-reviewed predicate (`state IN ('closed','reviewed')`); analyze.py display passes `trade.state` instead of `trade.status`; tos_import.py reads from fills repo (not exits table — also part of shim deletion).

**Production DB at brief-draft time (HEAD `ae63f4b` on main; Sub-A worktree HEAD `78c7005`):** schema_version=13 unchanged on production DB (Sub-A NOT merged); 4 trades (VIR closed+reviewed; DHC + CC + YOU open) + 1 exit (VIR's). Operator's trade workflows continue working through this dispatch (Sub-B is on chained worktree branch; main untouched).

**Test baseline:** 1450 fast tests passed at Sub-A worktree HEAD `78c7005` (217 failed + 20 errors are Sub-B/Sub-C territory). Plan projects ~+50 tests in Sub-B → ~1500 fast tests post-Sub-B (some shim-driven RED tests close as Sub-B rewrites land; some web RED tests stay RED for Sub-C). Ruff baseline ≤80.

---

## §2 Locked decisions (DO NOT re-litigate)

All design decisions locked in spec at `c926f01` + writing-plans brief §2 + plan §1-§7 + Sub-A executing-plans brief §2. Plan implements them as written; do NOT re-design. If a locked decision is impossible to implement as the plan specifies, STOP and surface in the return report.

Notable Sub-B-relevant locked decisions (NOT exhaustive — read spec + plan):

- **5-state minimal:** `entered → managing → partial_exited → closed → reviewed`. Unidirectional graph (no `partial_exited → managing`); same-day stop-out = `entered → managing → closed` atomic double-transition.
- **`status` DROPPED entirely** in Sub-A. Sub-B's predicate rewrites (per plan §2.1) replace status-based queries with state-based predicates per the 4 operation categories (active-trade / closed-but-not-reviewed / closed-or-reviewed / write-paths-eliminated).
- **Vocabulary CONFIRMED 2026-05-04** (catalyst-9 / emotional_state-8 / event_type-7) — values embedded in migration 0014 CHECK enums; entry service forms must validate against these enums with `... or None` for nullable text fallback.
- **Operation-contextual validation** (spec §3.5.1): entry service calls `validate_for_operation(EntryCreate, ...)` BEFORE `state_transition(...)`. State service does NOT call validate (per spec — separated concerns; Sub-A R1 Major 1 ACCEPTED with this rationale). Sub-B wires validate at call sites.
- **Pre-trade gate (`MissingPreTradeFieldsException`):** NOT force-bypassable. Single source of truth in `record_entry()`. Wraps the validate_for_operation call.
- **`trade_origin` derivation:** `derive_trade_origin(candidate, entry_path)` from `swing/trades/origin.py` (Sub-A T7). 5-bucket × 4-entry-path → 4-value enum mapping. Frozen-at-entry per `hypothesis_label` precedent.
- **Phase 9 deferred:** portfolio_heat / consecutive_loss / drawdown_breaker checks NOT in Sub-B. Schema accommodates (drawdown circuit breaker stays opt-in disabled via Phase 9-future Risk_Policy).
- **Aggregate denormalization on `trades`** (Sub-A T4 + T8): `current_size REAL NOT NULL` + `current_avg_cost REAL` + `last_fill_at TEXT` recomputed by `swing/data/repos/fills.py:insert_fill_with_event` after every fill insert. Sub-B's exit service consumes this — the fill insert triggers recompute; exit service doesn't recompute manually.
- **Multi-entry-fill authoritative selector** (spec §4.3.1): V1 service-layer constraint is single entry fill per trade; Sub-B's entry service enforces this.
- **Shim removal trigger at Sub-B T4** (operator decision 2026-05-04): exit service rewrite begins shim deletion. Sub-B T9 continues (journal/tos_import). Sub-C T1 finishes (web view models). Each task's commit message notes which shim component is deleted at that step.
- **R2 Minor 1 deferral handled at Sub-B T1** (operator decision 2026-05-04): `record_entry()` wires the atomic trade+entry-fill+pre_trade_locked_at flow. `insert_trade_with_event()` gets a defensive docstring warning callers MUST follow up with `insert_fill_with_event()` (otherwise `current_size=0`, `current_avg_cost=NULL`, `last_fill_at=NULL` — the R2 Minor 1 failure mode).
- **Chained-branch posture** (operator decision 2026-05-04): Sub-B does NOT merge to main. Sub-B's HEAD becomes Sub-C's chained baseline. Final integration merge happens at end of Sub-C.
- **No-main-commits-during-in-flight-dispatch** (lesson 2026-05-04). Orchestrator holds main edits while this dispatch is in-flight; exception only for verified-non-overlapping pure-docs edits with operator awareness.

**Hard-conflict escape:** if a locked decision genuinely BLOCKS Sub-B implementation (not merely creates tension — actually blocks), pause the dispatch, send an interim outbrief describing the conflict, standby for an orchestrator path-forward brief. This is the only relitigation channel; surfacing the conflict in the final return report is too late. (Same pattern as brainstorm + writing-plans + Sub-A executing-plans briefs.)

---

## §3 Scope

### In scope (this dispatch)

Execute plan Tasks B.1-B.9 (9 tasks). Sub-B scope per plan §5:

- **B.1** Entry service rewrite: atomic trade+entry-fill+pre_trade_locked_at flow; `MissingPreTradeFieldsException` gate; `EntryPath` enum on EntryRequest; trade_origin derivation; defensive docstring on `insert_trade_with_event`.
- **B.2** EntryPath enum threading through entry-call-sites (CLI + web ROUTES NOT TOUCHED — those are Sub-C; CLI binding only here).
- **B.3** Premortem + thesis field plumbing through entry service.
- **B.4** Exit service rewrite + shim removal step 1 (`_ExitLikeRow` removal at minimum; Exit stub stays alive for Sub-C consumers; `insert_exit_with_event` stub stays alive for any remaining callers in Sub-C).
- **B.5** Stop-adjust service: predicate rewrite + first-stop-trigger state transition.
- **B.6** Review service: predicate rewrite + `closed → reviewed` transition.
- **B.7** CLI display + new options: cli.py:1008 review-precondition; cli.py:588 display; new pre-trade-field CLI options per plan §5 T7.
- **B.8** (placeholder per plan; check actual task list).
- **B.9** Journal predicate rewrites: stats.py + flags.py + analyze.py + tos_import.py per plan §2.1 mapping. Includes tos_import migration from `exits` table reads to fills repo reads (further shim removal step).

### Out of scope (explicitly NOT this dispatch)

- **Re-litigating any locked decision** in spec / writing-plans brief / plan §1-§3 / Sub-A brief §2. Hard-conflict escape applies if a locked decision genuinely BLOCKS implementation — see §8.
- **Sub-A territory** — schema migration; repos/trades.py + repos/fills.py; state.py / origin.py / derived_metrics.py services; backup-runner discipline; preservation invariant fixtures; in-flight migration. ALREADY SHIPPED on chained-base; do NOT re-touch (any modification regresses Sub-A's binding-green-gate-equivalent for its scope).
- **Sub-C territory** — web routes; view models; templates; HTMX UX; operator-witnessed browser verification gate. Sub-C consumes Sub-B's service layer; cannot ship until Sub-B's services exist; reverse-deferred until Sub-B ships.
- **Phase 8 territory** — Daily_Management snapshots, MFE/MAE precision via OHLCV, In-Trade Review workflow.
- **Phase 9 territory** — Risk_Policy entity, Reconciliation_Run + Reconciliation_Discrepancy framework, drawdown circuit breaker activation.
- **Edit-after-lock UI** — schema fully supports via `trade_events.event_type='pre_trade_edit'`; UI ships V2.
- **Modifying `swing/web/`** — read-only for Sub-B; route + VM + template updates are Sub-C.
- **Full shim deletion at Sub-B T4** — only the components that exit service no longer needs (`_ExitLikeRow`); Exit class stub stays for Sub-C consumers; full deletion at Sub-C T1.
- **Adding new schema migrations** — Sub-A landed 0014; Sub-B does NOT bump schema. Any new field needs ought to surface as a hard-conflict escape (§8); the spec didn't anticipate it.

---

## §4 Binding conventions

- **Worktree isolation:** all work commits within the dispatch's isolated worktree (per §0 Step 1) — `phase7-sub-b-services` branch chained from `phase7-sub-a-schema`. DO NOT commit directly to `main`.
- **Marker-file management:** `touch .copowers-subagent-active` BEFORE Step 3; `rm` AFTER Step 3 / BEFORE Step 5. Binding.
- **Commits — 4-tier conventional:**
  - Task implementation: `feat(<area>): Task B.X — <subject>`.
  - Codex review-fix: `fix(<area>): Codex R<N> <severity> <id> — <subject>`.
  - Internal-Codex (within-task): append `(internal)` qualifier.
  - Internal code-review fix: `fix(<area>): code-review I<N> — <subject>`.
  - Format-only cleanup (ruff): no task ID prefix.
- **Subject-only ERE grep observable verification** before EVERY task implementation commit:
  ```
  git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task B\.X'
  ```
  Empty output for THIS phase's task ID → safe to proceed. STOP IMMEDIATELY and surface in return report if a duplicate appears for the same Task ID within THIS dispatch's commits.
- **NO OVERWRITING LANDED-TASK COMMITS:** before each task, verify prior task's commit is present AND read the landed file to understand the existing API. If existing API is wrong per your reading, **STOP** and surface; do NOT silently rewrite.
- **NO REGRESSING SUB-A's COMMITS:** Sub-A's 14 commits are landed on the chained base. Sub-B may CONSUME those APIs (entry/exit/stop_adjust/review services consume `state.py`, `origin.py`, `derived_metrics.py`, `fills.py`); Sub-B may NOT modify them. If Sub-A's API needs adjusting for Sub-B, surface as hard-conflict escape (§8) — do NOT silently modify Sub-A's files.
- **TDD:** write failing test → run → see fail → minimal implementation → run → see pass → commit, per task. Plan task text already specifies the failing test FIRST in each task body.
- **Discriminating-test discipline (binding):** every test specifies EXACT field + EXACT pre-fix expected value + EXACT post-fix expected value. "Illustrative" / TODO placeholders are vacuous tests; reject at internal review per Phase 7 plan-authoring lesson 2026-05-04.
- **Ruff baseline ≤80** (carried forward from Sub-A `78c7005`). New code MUST NOT increase baseline. `ruff check swing/` after each task to verify.
- **No-amend.** Every commit is a NEW commit. Codex/code-review fixes are their own commits.
- **No `--no-verify`, no `--no-gpg-sign`, no Claude co-author footer.**
- **Shim removal discipline (T4 + T9):** each shim component deletion is in its own commit with an explicit message (`refactor(trades): T4 — remove _ExitLikeRow shim (replaced by direct fills consumer)`; `refactor(journal): T9 — migrate tos_import to fills repo (drop exits table read)`). Shim components removed in Sub-B vs left for Sub-C must be enumerated in the return report.

---

## §5 Adversarial review watch items (for the post-dispatch Codex round)

The orchestrator-side `copowers:adversarial-critic` invocation (Step 5) covers these. Internal-Codex pre-emption is encouraged; pre-empt these in particular:

- **Atomic entry flow correctness** (T1). `record_entry()` MUST insert trade row + entry fill + set `pre_trade_locked_at` in a single transaction. Test: insert fails midway (e.g., fills repo raises) → trade row is NOT persisted (rollback verified).
- **`MissingPreTradeFieldsException` gate** (T1). Validates EVERY required pre-trade field per spec §10.1 + plan §5 T1. NOT force-bypassable. Discriminating test per missing-field path.
- **Operation-contextual validation** (T1, T6). Entry uses `EntryCreate` operation; review uses `transition_reviewed` operation. State service does NOT call validate; service layer wires it. Reviewer flags inverted call order (state_transition called BEFORE validate_for_operation).
- **Review precondition `state == 'closed'` ONLY** (T6). NOT `state IN ('closed','reviewed')` — would let already-reviewed trades through review again (per Phase 7 brainstorm lesson). Discriminating test: trade with `state='reviewed'` → review attempt rejected with appropriate error.
- **Stop-adjust first-stop-trigger transition** (T5). Trade in `state='entered'` + first stop adjust → transitions to `state='managing'`. Trade already in `state='managing'` + subsequent stop adjust → stays `state='managing'`. Discriminating test for both paths.
- **Exit service same-day stop-out atomic double-transition** (T4). Trade entered today + stop hit today → `entered → managing → closed` in single operation. Discriminating test asserts intermediate `managing` state was passed through (not just final `closed` state).
- **Exit service partial vs full exit** (T4). Partial exit (shares < current_size) → `state='partial_exited'`; full exit (shares == current_size) → `state='closed'`. Discriminating tests for both.
- **Aggregate recompute consistency after exit** (T4). After partial exit, `current_size` decremented; `current_avg_cost` unchanged (entry weighted average preserved); `last_fill_at` updated to exit fill datetime. Verified via `swing/data/repos/fills.py:_recompute_aggregates` (Sub-A T4 implementation).
- **Predicate rewrite per §2.1 mapping** (T7 + T9). Each rewrite preserves semantic purpose (active-trade / closed-but-not-reviewed / closed-or-reviewed / write-paths). Reviewer flags any rewrite that inverts semantics (e.g., review-precondition gets `state IN ('closed','reviewed')` predicate — would re-allow already-reviewed trades).
- **Shim deletion progression** (T4 + T9). `_ExitLikeRow` deleted at T4 (exit service no longer consumes); Exit class stub + `insert_exit_with_event` stub PRESERVED at end of Sub-B (web consumers still reference; Sub-C T1 finishes deletion). Reviewer verifies the boundary.
- **`tos_import.py` migration to fills** (T9). Reads from `swing/data/repos/fills.py:list_fills_for_trade()` filtered to `action != 'entry'` (analogue of `list_exits_for_trade`); writes during reconciliation insert to fills (with `action='exit'` for full close-fill matches). Discriminating test: post-migration, tos_import reconciliation correctly identifies VIR's exit fill (NOT the entry fill).
- **CLI new pre-trade-field options** (T7). Each new CLI option (premortem inputs, thesis fields, emotional_state multi-select, manual_entry_confidence radio-equivalent) has its required-vs-optional disposition consistent with plan §5 T7 + spec §10.1. Discriminating test per option.
- **No web file modifications** (out-of-scope discipline). Reviewer verifies `git diff phase7-sub-a-schema..HEAD -- swing/web/` is empty (or only docs-only / non-functional changes if any).
- **No regressions to Sub-A's tests**. All `tests/data/`, `tests/trades/test_state.py`, `tests/trades/test_origin.py`, `tests/trades/test_derived_metrics.py`, `tests/data/test_migration_0014.py` etc. that Sub-A added MUST remain GREEN. Discriminating regression check at end of every task.
- **Ruff baseline preserved** (≤80 carried from Sub-A).
- **Discriminating-test gate applied to every test in Sub-B.** Reviewer flags "illustrative" or TODO placeholders.

---

## §6 Done criteria

The Sub-B executing-plans dispatch is done when ALL of the following hold:

- [ ] All 9 plan tasks (B.1-B.9) committed on the chained worktree branch.
- [ ] Subject-only ERE grep verification clean (no duplicate Task B.X commits).
- [ ] **PARTIAL-suite green**: Sub-A tests + Sub-B tests GREEN. Sub-C tests may still be RED. Document the exact RED-test count in the return report — this becomes Sub-C's starting point.
- [ ] Sub-A test count maintained or grown (no regressions).
- [ ] Ruff baseline ≤80 (no increase from chained-baseline `78c7005`).
- [ ] No web file modifications (`git diff phase7-sub-a-schema..HEAD -- swing/web/` empty or non-functional only).
- [ ] Shim removal progression: `_ExitLikeRow` deleted at T4; tos_import migrated off exits table reads at T9; Exit class stub + `insert_exit_with_event` stub PRESERVED for Sub-C consumers.
- [ ] R2 Minor 1 deferral handled at T1 (defensive docstring on `insert_trade_with_event`; atomic flow at `record_entry()`).
- [ ] Marker file removed (`ls .copowers-subagent-active` → No such file).
- [ ] Codex `copowers:adversarial-critic` round reached `NO_NEW_CRITICAL_MAJOR`.
- [ ] **NO MERGE TO MAIN** — chained-branch posture. Surface Sub-C pre-conditions + chained-baseline SHA in return report.

---

## §7 Return report format

Final message to orchestrator (via operator) MUST include:

```
DISPATCH: Phase 7 Sub-B (services + CLI + journal predicate rewrites)
WORKTREE BRANCH: phase7-sub-b-services
WORKTREE PATH: C:/Users/rwsmy/swing-trading/.worktrees/phase7-sub-b-services
CHAINED-BASELINE_SHA: 78c7005 (Sub-A worktree HEAD)
HEAD: <Sub-B HEAD SHA>

TASK COMMITS (9):
  <commit list, B.1 through B.9>

CODE-REVIEW FIX COMMITS:
  <commit list>

CODEX FIX COMMITS:
  <commit list>

INTERNAL-CODEX FIX COMMITS (qualifier (internal)):
  <commit list>

CODEX ADVERSARIAL ROUNDS: <N>; FINAL VERDICT: NO_NEW_CRITICAL_MAJOR

TEST DELTA:
  baseline (78c7005):  1450 passed, 217 failed, 20 errors, 1 skipped
  post-dispatch:       <N> passed, <N> failed (Sub-C territory), <N> errors, <N> skipped
  Sub-A tests preserved: <count of Sub-A's tests still passing> (regression check)
  Sub-B tests added:     <+N> (vs ~+50 plan estimate; bias-high acceptable)
  Sub-C-territory tests still RED: <N> (this is Sub-C's starting point)

RUFF DELTA:
  baseline:      80 errors at 78c7005
  post-dispatch: <N>

WEB-FILE MODIFICATION CHECK:
  git diff phase7-sub-a-schema..HEAD -- swing/web/  →  <empty / non-functional only>

SHIM REMOVAL PROGRESSION:
  _ExitLikeRow:                  DELETED in <commit SHA> (T4)
  Exit class stub:               PRESERVED (Sub-C T1 territory)
  insert_exit_with_event stub:   PRESERVED (Sub-C T1 territory)
  exits table read in tos_import: MIGRATED to fills repo in <commit SHA> (T9)

R2 MINOR 1 DEFERRAL HANDLED:
  insert_trade_with_event docstring: <commit SHA> (T1)
  atomic record_entry flow:          <commit SHA> (T1)

PRODUCTION DB STATE CHECK (run at dispatch start):
  schema_version: 13 (Sub-A NOT merged; chained-branch posture preserved)
  4 trades (VIR/DHC/CC/YOU) + 1 exit (VIR's) — unchanged

ADVERSARIAL FINDINGS (each with disposition):
  R1: <count critical / major / minor>
    - <finding>: FIXED in commit <SHA> / ACCEPTED with rationale: <text>
  R2: ...

LESSONS WORTH CAPTURING (process insights from this dispatch):
  - <bullet list>

OPEN QUESTIONS FOR ORCHESTRATOR:
  - <any blocker or unresolved framing issue>

SUB-C PRE-CONDITIONS (relayed for next dispatch):
  - Sub-C BASELINE_SHA: <Sub-B HEAD SHA>
  - Sub-C worktree branch: phase7-sub-c-web (chained from phase7-sub-b-services)
  - Sub-C owns: web routes + view models + templates + state-badge partial + entry-form expansion (7 fieldset sections per spec §11.1) + shim full-deletion (Exit class stub + insert_exit_with_event stub) + operator-witnessed browser verification gate
  - Sub-C's done criteria gate is FULL-SUITE-GREEN (this is the integration gate)
  - Final integration merge after Sub-C ships green: git checkout main && git merge --no-ff phase7-sub-c-web

NO MERGE COMMAND THIS DISPATCH:
  Sub-B does NOT merge to main per chained-branch posture. Sub-B HEAD becomes Sub-C's chained baseline.
```

---

## §8 If you get stuck

- **If a plan task requires re-designing the spec or plan,** invoke the §2 hard-conflict escape (carries forward from brainstorm + writing-plans + Sub-A briefs): pause the dispatch, send an interim outbrief describing the conflict, standby for orchestrator path-forward. Do NOT relitigate the spec OR plan in the dispatch.
- **If the production DB state at empirical-audit time differs from §0 #8 expected state** (e.g., 5 trades exist; schema_version != 13; Sub-A merged unexpectedly), STOP IMMEDIATELY. Do NOT proceed with task implementation. Surface to orchestrator — chained-branch posture requires production stays at v13 until final integration.
- **If Sub-A worktree is missing or HEAD differs from `78c7005`,** STOP — the chained branch can't form correctly. Surface to orchestrator immediately.
- **If a Sub-A API needs adjusting for Sub-B** (e.g., state service signature inadequate; fills repo helper missing a needed query), STOP. Do NOT silently modify Sub-A's files. Surface as hard-conflict escape — orchestrator decides whether to add a Sub-A bridge commit on the worktree OR add to Sub-B's scope (with explicit modification of Sub-A's file justified in plan-deviation note).
- **If shim removal at T4 breaks Sub-C-territory tests** unexpectedly (beyond the already-RED 217 + 20), investigate whether the shim component is still needed — either keep it alive longer (push deletion to a later Sub-B task) OR document the new RED test as Sub-C's responsibility.
- **If Codex review surfaces a finding that contradicts a locked decision,** apply receiving-code-review discipline. Verify the finding against the spec + plan + Sub-A brief FIRST. If finding is correct AND locked decision is wrong, escalate via §2 hard-conflict escape. If finding is wrong, document why it's rejected with rationale.
- **If the empirical audit broadened-grep refresh (per plan §2.3) finds new call sites not in the plan §2.1 mapping,** add to the appropriate sub-dispatch task's scope (Sub-B if §2.1 category matches Sub-B's territory; otherwise hand-off to Sub-C via return report). Do NOT silently expand Sub-B scope into Sub-C territory.
- **If Codex round produces 0/0/0 advisory only,** trust the empirical evidence. NO_NEW_CRITICAL_MAJOR is the gate; you may stop after a clean round.

---

## §9 Anti-patterns specific to this dispatch

These have caused real problems in past sessions; resist:

- **Drifting into Sub-C scope.** Sub-B is service + CLI + journal layer only. Web routes, view models, templates, state-badge partial, entry-form expansion are Sub-C. The §2.1 plan mapping makes this explicit; respect the boundary.
- **Modifying Sub-A files.** Sub-A's `swing/data/repos/`, `swing/trades/state.py`, `swing/trades/origin.py`, `swing/trades/derived_metrics.py`, `swing/data/repos/fills.py`, `swing/data/migrations/0014_*.sql`, `swing/data/db.py` migration runner — all LANDED on chained base; consume their APIs, do NOT modify. Surface as hard-conflict escape if modification needed.
- **Re-litigating locked decisions.** Spec at `c926f01` + plan at `251cc35` + Sub-A brief decisions burned context settling these. Don't reopen.
- **Silent merging to main.** Chained-branch posture forbids merging Sub-B to main. Final integration is at Sub-C end. If you see a temptation to merge Sub-B early to "clear the worktree," STOP — the chained posture is intentional and operator-decided.
- **Full shim deletion at Sub-B T4.** Exit class stub + `insert_exit_with_event` stub stay alive for Sub-C consumers. Only `_ExitLikeRow` (internal helper to exit service) deletes at T4. Full deletion is at Sub-C T1.
- **"Illustrative" / TODO placeholders in tests.** Per Phase 7 plan-authoring lesson — plan tasks already specify EXACT values; if you find one that doesn't, treat as a plan bug + surface in return report.
- **Cross-cutting tests that span sub-dispatches.** A test that exercises end-to-end Sub-B → Sub-C path is NOT Sub-B's scope. Sub-B tests stop at the service + CLI + journal layer; integration tests live in Sub-C.
- **Regex-replace status→state.** Per §2.1 + Phase 7 brainstorm lesson — predicate rewrites are NOT uniform substitution; each call-site classifies into one of 4 operation categories with the appropriate rewrite.
- **Skipping the broadened-grep refresh.** Plan §2.3 specifies running grep at dispatch time AND after every Sub-B task to catch any plan-time-missed call sites. NOT optional.
- **Bumping schema version mid-Sub-B.** Sub-A landed migration 0014; Sub-B does NOT add another migration. Any schema change need surfaces as hard-conflict escape.
- **Adding new web routes / templates / view models.** All web work is Sub-C. If a CLI-only task accidentally requires web file changes, surface as hard-conflict escape.

---

## §10 Closing note

Sub-B is the service + CLI + journal layer for Phase 7. It consumes Sub-A's data-layer foundation and prepares Sub-C's web/UX layer with a stable service API. The plan is detailed; the spec is locked; Sub-A's foundation is in place; chained-branch posture is binding.

When done, return the structured report and stop. The orchestrator triages the result + decides when to commission Sub-C. NO MERGE TO MAIN this dispatch — the integration merge happens after Sub-C closes the suite to full green.
