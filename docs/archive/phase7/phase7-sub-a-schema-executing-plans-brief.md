# Phase 7 Sub-A — Schema + Repos + State Service — Executing-Plans Dispatch Brief

**Audience:** Fresh Claude Code instance with no prior conversation context.

**Mission:** Execute Sub-A of `docs/superpowers/plans/2026-05-04-phase7-trade-lifecycle-state-machine-plan.md` end-to-end. The plan is committed on `main` after 4 Codex rounds reaching `NO_NEW_CRITICAL_MAJOR` in the writing-plans dispatch (commit chain `18bb35e..251cc35`); design decisions are locked at spec `c926f01` (3 brainstorm rounds NO_NEW_CRITICAL_MAJOR) and plan-task partitioning is fixed.

**Scope:** Sub-A only (Tasks A.0-A.10 = 11 tasks). Sub-B (services + CLI + journal predicate rewrites) and Sub-C (web + UX) are SEPARATE future dispatches. Default ordering is serial A→B→C; Sub-A delivers schema migration + repos + state-machine service + origin/derived_metrics services + test-fixture refactor + in-flight VIR/DHC/CC migration. At end-of-Sub-A: full fast suite green; T6 is binding green gate.

**Expected duration:** ~5-8 hours including 2-4 Codex rounds. ~87 expected new tests (per plan §4 estimate; per Phase 6 lesson "test-count-projections-bias-high" the actual count may run higher; that's acceptable IF discriminating-test discipline justifies it).

**Dispatch type:** **Direct invocation of `superpowers:subagent-driven-development` followed by `copowers:adversarial-critic`** (NOT the `copowers:executing-plans` wrapper). Worktree isolation + global PreToolUse Codex-blocking hook both in effect — see §0 Skill posture for the 7-step workflow. Same pattern as Phase 6 + Phase 5 re-dispatch (canonical references: `docs/phase6-post-trade-review-executing-plans-brief.md`, `docs/phase5-configuration-page-executing-plans-brief.md`).

---

## §0 Read first

Read these in order before executing:

1. **`docs/superpowers/plans/2026-05-04-phase7-trade-lifecycle-state-machine-plan.md`** — THE PLAN. Source of truth for task partitioning, per-task acceptance criteria, test specifications, file paths. ~4172 lines; budget 60-90 minutes for thorough read. Pay particular attention to:
   - **§0** sub-dispatch ordering, worktree posture, BASELINE_SHAs, marker-file workflow.
   - **§1** vocabulary lists (CONFIRMED 2026-05-04 per operator reply; values embedded in migration 0014 CHECK enums; do NOT re-litigate).
   - **§2.1** status→state per-call-site predicate rewrite mapping (25+ enumerated lines, 4 categories). Sub-A T6 owns the mechanical rewrites where the §2.1 column shows "Sub-A T6"; Sub-B/Sub-C entries are NOT this dispatch's scope — leave for Sub-B/Sub-C.
   - **§2.3** broadened grep refresh — re-run at dispatch time + after every Sub-A task to catch any plan-time-missed call sites.
   - **§3** carve-out enumeration (~45 files; Sub-A's subset).
   - **§4** Sub-A task list (T0 fixture refactor → T1 backup runner → T2 migration 0014 → T3 models → T4 fills repo → T5 state service → T6 repos rewrite [binding green gate] → T7 origin → T8 derived_metrics → T9 4-fixture preservation invariant → T10 in-flight VIR/DHC/CC migration).
   - **§7** test strategy + +150-250 wide band (across all of Phase 7; Sub-A's projected ~87).
   - **§8** done criteria + return report format.

2. **`docs/superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md`** — the spec the plan implements. ~1069 lines. The plan is the implementation contract; if the plan's task body diverges from the spec, the plan wins (writing-plans review reconciled them). Surface any irreconcilable divergence in your return report; do NOT silently re-design.

3. **`docs/phase7-trade-lifecycle-state-machine-writing-plans-brief.md`** — the brief that drove the plan. Locked decisions (§2), open-questions-resolved-in-plan (§3), 21 adversarial-review watch items (§5). The plan IMPLEMENTS this brief; if you find a divergence, the plan wins.

4. **`docs/phase7-trade-lifecycle-state-machine-brainstorm-brief.md`** — the brainstorm brief that drove the spec. §2 hard-conflict escape carries forward to executing-plans (see §8 below).

5. **`CLAUDE.md`** at repo root — gotchas to pre-empt. Sub-A is data-layer only (no web, no CLI), so HTMX gotchas + base-layout VM rule do NOT apply this dispatch. Active gotchas for Sub-A:
   - **`Connection.backup()` API for WAL-mode SQLite** (line 370 lesson). T1 backup runner uses SQLite-native methods only; `shutil.copy2` explicitly REJECTED (spec §12.1 binding).
   - **`os.replace` cross-device-link** — temp files for atomic-replace must live in dest dir; backups should be on the same volume as `~/swing-data/swing.db`.
   - **`pipeline_runs` ORDER BY mask** — irrelevant to Sub-A but applies to journal predicate rewrites (Sub-B); skip for Sub-A.
   - **Python `... or ""` vs `... or None` for nullable CHECK columns** (2026-05-04 gotcha) — applies to T6 INSERT helpers if any nullable text column with CHECK enum gets a fallback. Use `... or None` per the binding pattern.
   - **TestClient lifespan** — irrelevant to Sub-A (no web routes); skip.

6. **`docs/orchestrator-context.md`** — focus on:
   - §"Currently in-flight work" — Phase 7 row reflects this dispatch's status.
   - §"Binding conventions" — 4-tier commit-message convention; subject-only ERE grep observable verification; no-amend; no Claude footer; ruff baseline 80 (current at HEAD `88f9fac`); worktree+editable-install verify-command convention; no-main-commits-during-in-flight-dispatch (lesson 2026-05-04).
   - §"Anti-patterns to avoid".
   - §"Lessons captured" — particularly the **Phase 7 cycle** lessons:
     - State-bearing entity validation must distinguish operation enforcement from data invariant (T6 + T9 + T10 must encode operations, not state-invariant claims).
     - Status→state predicate rewrite is not uniform substitution (T6 follows the §2.1 per-line mapping; do NOT regex-replace).
     - Operational discipline operationalized in code, not stated in spec text (T1 backup-runner discipline is binding code, not just a comment).
     - Plan-authoring is its own bug surface (cross-section consistency drift; per-line "verify at task time" looseness — both pre-empted by the locked plan, but if you find one Codex will catch it; expect 2-4 plan-fix rounds).
     - "Illustrative" / TODO placeholders are vacuous tests in disguise (every Sub-A test specifies EXACT field + pre-fix value + post-fix value).

7. **Production DB state verification** — at dispatch time, run:
   ```python
   import sqlite3, os
   conn = sqlite3.connect(os.path.expanduser("~/swing-data/swing.db"))
   for ticker in ('VIR', 'DHC', 'CC', 'YOU'):
       trade = conn.execute("SELECT id, ticker, status, entry_date, entry_price, initial_shares, hypothesis_label FROM trades WHERE ticker = ?", (ticker,)).fetchone()
       print(f'{ticker}: {trade}')
   print('exits:', conn.execute("SELECT * FROM exits").fetchall())
   print('schema_version:', conn.execute("SELECT * FROM schema_version").fetchall())
   ```
   Confirm **4 trades** (VIR closed+reviewed; DHC + CC + YOU open) + 1 exit (VIR's) + schema_version=13 (post-Phase-6). **Update 2026-05-04 (post-writing-plans / pre-Sub-A):** operator entered a 4th trade YOU between writing-plans dispatch and Sub-A dispatch — a hypothesis-1 (A+ baseline) entry on 2026-05-04. T10 fixture + migration UPDATEs adjusted in lockstep per plan's "re-verify at task time" NOTE. If state diverges from this 4-trade expected (e.g., 5 trades, exits added, schema != 13), STOP and surface in return report — plan T10 migration UPDATE depends on these exact values.

8. **`swing/data/migrations/`** — confirm next migration is `0014_*.sql` (last is `0013_phase6_post_trade_review.sql`); plan Task A.2 ships the single 0014 migration with all schema changes in one transaction.

If any file path above doesn't resolve, verify via `Glob`/`Grep` before executing the plan task.

---

## §0 Skill posture (7-step workflow — execute in order)

**Step 1 — Create isolated worktree.** INVOKE `superpowers:using-git-worktrees` to create an isolated worktree on a new branch (suggested: `phase7-sub-a-schema`) from base `main` HEAD `251cc35` (verify before invocation via `git rev-parse main`; should match Sub-A baseline). All work commits onto the worktree branch. REQUIRED per `superpowers:subagent-driven-development` skill docs AND per orchestrator-context binding-convention 2026-05-02 (worktree isolation default for any plan with >5 task commits OR substantial schema changes; Sub-A hits both).

**Step 2 — Activate the Codex-blocking marker.** From within the worktree: `touch .copowers-subagent-active`. This activates the global PreToolUse hook (`~/.claude/hooks/block-copowers-during-subagent.sh`, registered in `~/.claude/settings.json`) which physically blocks subagent invocation of `copowers:adversarial-critic`, `copowers:review`, `mcp__plugin_copowers_codex__codex`, `mcp__plugin_copowers_codex__codex-reply`. Hook is harness-level and cannot be bypassed by subagent reasoning.

**Step 3 — Invoke subagent-driven-development DIRECTLY** (NOT via `copowers:executing-plans` wrapper):

- **INVOKE** `superpowers:subagent-driven-development` and execute Tasks A.0-A.10 per the plan. Subagents will physically be unable to invoke Codex/copowers review while the marker is active.
- **DO NOT INVOKE** `copowers:executing-plans` — bundles both phases without marker management.
- **DO NOT INVOKE** `copowers:adversarial-critic`, `copowers:review`, `mcp__plugin_copowers_codex__codex`, or `mcp__plugin_copowers_codex__codex-reply` from within subagent dispatches. Hook blocks; explicit prohibition is belt-and-suspenders.
- **DO NOT INVOKE** `superpowers:brainstorming` / `copowers:brainstorming` — design is locked at spec `c926f01`.
- **DO NOT INVOKE** `copowers:writing-plans` / `superpowers:writing-plans` — plan is locked at `251cc35`. If you find a plan task is impossible to implement as written, STOP and surface in the return report; do NOT silently re-plan.

**Step 4 — Remove marker.** After all subagent-driven-development tasks complete + final code reviewer approves: `rm .copowers-subagent-active`. Verify: `ls .copowers-subagent-active` → `No such file`.

**Step 5 — Invoke Codex adversarial review.** INVOKE `copowers:adversarial-critic` directly with:
- `PHASE`: `executing-plans`
- `SPEC_PATH`: `docs/phase7-sub-a-schema-executing-plans-brief.md` (this brief; per copowers convention this is the spec for the dispatch)
- `PLAN_PATH`: `docs/superpowers/plans/2026-05-04-phase7-trade-lifecycle-state-machine-plan.md`
- `BASELINE_SHA`: `251cc35` (main HEAD at Sub-A worktree creation time; review covers all worktree commits since base)

Iterate Codex rounds to `NO_NEW_CRITICAL_MAJOR`. Internal-Codex pre-emption (commit message qualifier `(internal)`) is encouraged; saves orchestrator-Codex round budget. Expect 2-4 rounds.

**Step 6 — Verification gate.** Sub-A is data-layer only — NO operator-witnessed browser gate (that's Sub-C end-of-dispatch). Verification for Sub-A:
- Full fast suite green (`python -m pytest -m "not slow" -q`); test count delta within band (~+87 expected; bias-high acceptable).
- Migration 0014 idempotent (re-run produces no-op; covered by plan tests).
- Backup-runner integrity checks all pass for the migration backup.
- VIR/DHC/CC migrated to expected (state, pre_trade_locked_at, trade_origin) values per plan §4 T10.
- 4-fixture preservation invariant test gate green (singleton/multi-date/same-date/notes-merged).
- Ruff baseline ≤80 (current at HEAD `88f9fac`).

**Step 7 — Prepare worktree merge to `main`.** Surface the merge command + worktree cleanup in the return report; the operator executes the merge after final review.

---

## §1 Strategic context (compressed)

Phase 7 ships the trade lifecycle state machine + Fills first-class — the structural backbone of the journal v1.2 incorporation roadmap. Sub-A is the data-layer foundation: schema migration introducing the state column + Fills table + ~28 new trade columns, repo refactor consuming the new schema, state-machine service + origin/derived_metrics services, test-fixture refactor, and in-flight migration of the 3 production trades (VIR/DHC/CC) to the new state space.

**Why Sub-A first:** Sub-B (services/CLI) and Sub-C (web/UX) consume Sub-A's repo + service layer. Shipping Sub-A as a discrete dispatch with binding green gate at T6 means Sub-B can dispatch from a clean main without inheriting half-written schema work.

**What ships in this dispatch (per plan §4):**

- **Schema migration `0014`** (single transaction): drop `trades.status`; add `state TEXT NOT NULL CHECK (state IN ('entered','managing','partial_exited','closed','reviewed')) DEFAULT 'entered'`; add `pre_trade_locked_at TEXT`; add `trade_origin TEXT NOT NULL CHECK (trade_origin IN ('pipeline_aplus','pipeline_watch_hyp_recs','pipeline_watch_manual','manual_off_pipeline')) DEFAULT 'manual_off_pipeline'`; add ~25 new pre-trade fields (18 thesis kept + 4 premortem + 3 aggregate + others per spec); add `current_size REAL NOT NULL`, `current_avg_cost REAL`, `last_fill_at TEXT`. Drop `exits` table after migrating to `fills` (4-action enum). Recreate Migration 0004 partial unique index against new state predicate. Backfill VIR/DHC/CC with FIRM values per plan §4 T10.
- **Backup-runner discipline** (`swing/data/db.py`): SQLite-native `Connection.backup()` to timestamped path; 4 binding integrity checks (PRAGMA integrity_check on backup; expected-table set; row-count parity for migrated tables; size advisory).
- **`swing/data/models.py`**: Trade dataclass refactored — drop `status`; add `state` + ~28 new columns. New `Fill` dataclass.
- **`swing/data/repos/fills.py`** NEW: insert/list/aggregate-recompute helpers; `insert_fill_with_event` audit-via-trade_events.
- **`swing/data/repos/trades.py`**: state-aware INSERT/SELECT/UPDATE; status removed from all queries; binding green gate at T6.
- **`swing/trades/state.py`** NEW: state-machine service. `state_transition(conn, trade_id, target_state, ...)` is the single write-path for state changes. Per-operation validation (entry_create / transition_managing/partial_exited/closed / transition_reviewed) per spec §3.5.1.
- **`swing/trades/origin.py`** NEW: `derive_trade_origin(candidate, entry_path, ...)` — 5-bucket × 4-entry-path → 4-value enum mapping per spec §10.4.
- **`swing/trades/derived_metrics.py`** NEW: aggregate recompute helpers (`current_size`, `current_avg_cost`, `last_fill_at` from fills).
- **9 test fixture files refactored** (T0): `tests/data/test_repos_trades.py`, `tests/data/test_db_v3.py`, `tests/data/test_models.py`, `tests/pipeline/test_runner.py`, `tests/pipeline/test_runner_chart_targets.py`, `tests/cli/test_cli_advisory.py`, `tests/cli/test_cli_trade_analyze.py`, `tests/research/parity/test_fetcher.py`, `tests/trades/test_equity.py`.
- **4-fixture preservation invariant test gate** (T9): singleton, multi-date, same-date multi-exit, notes-merged.
- **In-flight migration of VIR/DHC/CC** (T10) with verify-via-pytest tests asserting exact backfilled values.

**Production DB at brief-draft time (HEAD `88f9fac`):** VIR (closed; reviewed; `realized_R_if_plan_followed≈0`; derived `mistake_cost_R=0.33`) + DHC (open; entry 2026-04-27 @ $7.58 × 39 shares; `pipeline_watch_hyp_recs` FIRM) + CC (open; entry 2026-04-30 @ $26.97 × 5 shares; `pipeline_watch_hyp_recs` FIRM). 1 exit row (VIR's). Schema version 13 (post-Phase-6).

**Test baseline:** 1587 fast tests passed, 1 skipped at HEAD `251cc35`. Plan projects ~+87 tests in Sub-A → ~1674 fast tests post-Sub-A. Ruff baseline ≤80.

---

## §2 Locked decisions (DO NOT re-litigate)

All design decisions locked in `docs/superpowers/specs/2026-05-04-phase7-trade-lifecycle-state-machine-design.md` (spec) + `docs/phase7-trade-lifecycle-state-machine-writing-plans-brief.md` §2 (writing-plans brief) + plan §1-§7 (executing plan). Plan implements them as written; do NOT re-design. If a locked decision is impossible to implement as the plan specifies, STOP and surface in the return report.

Notable Sub-A-relevant locked decisions (NOT exhaustive — read spec + plan):

- **5-state minimal:** `entered → managing → partial_exited → closed → reviewed`. NO `planned/triggered/canceled`.
- **Unidirectional graph:** no `partial_exited → managing` (no pyramiding). Same-day stop-out = `entered → managing → closed` atomic double-transition.
- **`status` DROPPED entirely** in this Sub-A dispatch. T6 is binding green gate — all tests pass after status is gone.
- **Vocabulary CONFIRMED 2026-05-04** (operator reply: "vocab confirmed"):
  - `catalyst` 9 values: `earnings_driven`, `guidance_change`, `corporate_action`, `sector_rotation`, `macro_event`, `sympathy_move`, `product_news`, `technical_only`, `other`.
  - `emotional_state_pre_trade` 8 values (multi-select, JSON-list): `calm`, `confident`, `anxious`, `fomo`, `revenge`, `hopeful`, `doubtful`, `distracted`.
  - `event_type` 7 values (conditional on `event_risk_present=1`): `earnings`, `fed_meeting`, `cpi_release`, `economic_data`, `product_announcement`, `legal_ruling`, `other`.
- **Migration 0014 single transaction** (per spec §13.1).
- **Migration runner backup discipline** (spec §12.1): SQLite-native ONLY (`Connection.backup()` / `VACUUM INTO`); `shutil.copy2` explicitly REJECTED.
- **4-fixture preservation invariant** (spec §4.4.1): singleton, multi-date, same-date multi-exit, notes-merged. EXACT expected backfilled fills row contents per plan T9.
- **Multi-entry-fill authoritative selector** (spec §4.3.1): `ORDER BY fill_datetime ASC, fill_id ASC LIMIT 1`. V1 service-layer constraint is single entry fill; the trade-level reader contract pre-locked.
- **Aggregate denormalization on `trades`:** `current_size REAL NOT NULL` + `current_avg_cost REAL` + `last_fill_at TEXT`. Recomputed by `swing/data/repos/fills.py:insert_fill_with_event` after every fill insert.
- **Operation-contextual validation** (spec §3.5.1): `entry_create` enforces full required set; `transition_managing/partial_exited/closed` triggers suffice; `transition_reviewed` enforces Phase 6 review-completion fields only; legacy rows exempt by NULLABLE schema.
- **VIR/DHC/CC/YOU migration FIRM values** per plan §4 T10 (4 trades — YOU added 2026-05-04 between writing-plans and Sub-A dispatch):
  - VIR: `state='reviewed'`, `pre_trade_locked_at='2026-04-20T16:00:00'`, `trade_origin='manual_off_pipeline'`.
  - DHC: `state='managing'`, `pre_trade_locked_at='2026-04-27T16:00:00'`, `trade_origin='pipeline_watch_hyp_recs'`.
  - CC: `state='managing'`, `pre_trade_locked_at='2026-04-30T16:00:00'`, `trade_origin='pipeline_watch_hyp_recs'`.
  - YOU: `state='managing'`, `pre_trade_locked_at='2026-05-04T16:00:00'`, `trade_origin='pipeline_aplus'` (ticker YOU; entry 2026-05-04 @ $56.29 × 2 shares; bucket=`aplus` confirmed in candidates table action_session 2026-05-04 + present in daily_recommendations as `today_decision`; rationale='aplus-setup' in trade_events; hypothesis_label='A+ baseline (aplus)').
- **Worktree isolation: REQUIRED.** Per binding convention 2026-05-02. Plan §0 specifies setup; this brief reiterates §0 Step 1.
- **No-main-commits-during-in-flight-dispatch** (lesson 2026-05-04). Orchestrator holds main edits while this dispatch is in-flight; exception only for verified-non-overlapping pure-docs edits with operator awareness.

---

## §3 Scope

### In scope (this dispatch)

Execute plan Tasks A.0-A.10 (11 tasks). Sub-A scope per plan §4:

- **A.0** Test fixture refactor across 9 identified files (broadened-grep refresh at task start to catch any plan-time-missed call sites).
- **A.1** Backup-runner discipline in `swing/data/db.py`: SQLite-native; 4 integrity checks; pre-migration backup gate.
- **A.2** Migration `0014` single transaction (status drop; state add; pre_trade_locked_at add; trade_origin add; ~25 new fields; aggregate cols; fills table; exits drop; Migration 0004 partial unique index recreate against state predicate).
- **A.3** `swing/data/models.py` Trade dataclass + Fill dataclass.
- **A.4** `swing/data/repos/fills.py` NEW.
- **A.5** `swing/trades/state.py` NEW state-machine service.
- **A.6** `swing/data/repos/trades.py` rewrite to state-aware (binding green gate — full fast suite passes).
- **A.7** `swing/trades/origin.py` NEW.
- **A.8** `swing/trades/derived_metrics.py` NEW.
- **A.9** 4-fixture preservation invariant test gate.
- **A.10** In-flight VIR/DHC/CC migration backfill + verify-via-pytest tests.

### Out of scope (explicitly NOT this dispatch)

- **Re-litigating any locked decision** in spec / writing-plans brief / plan §1-§3. Hard-conflict escape applies if a locked decision genuinely BLOCKS implementation — see §8.
- **Sub-B territory** — services refactor (entry/exit/stop_adjust/review services); CLI changes; journal predicate rewrites (stats.py, flags.py, analyze.py, tos_import.py); `MissingPreTradeFieldsException` gate wiring. Plan §5.
- **Sub-C territory** — web routes; view models; templates; HTMX UX; operator-witnessed browser verification gate. Plan §6.
- **Phase 8 territory** — Daily_Management snapshots, MFE/MAE precision via OHLCV, In-Trade Review workflow.
- **Phase 9 territory** — Risk_Policy entity, Reconciliation_Run + Reconciliation_Discrepancy framework, drawdown circuit breaker activation (schema accommodates; activation deferred).
- **Edit-after-lock UI** — schema fully supports via `trade_events.event_type='pre_trade_edit'`; UI ships V2.
- **Modifying `swing/journal/`** — read-only for Sub-A; predicate rewrites are Sub-B T9.
- **Modifying `swing/web/`** — read-only for Sub-A; route + VM + template updates are Sub-C.
- **Modifying `swing/cli.py` beyond what plan §2.1 explicitly assigns to Sub-A T6** — predicate rewrites in CLI are Sub-B T7.

---

## §4 Binding conventions

- **Worktree isolation:** all work commits within the dispatch's isolated worktree (per §0 Step 1). Worktree branch is the integration branch; merge to `main` at end-of-dispatch via `--no-ff` if there are docs commits ahead of base, else `--ff-only`. DO NOT commit directly to `main`.
- **Marker-file management:** `touch .copowers-subagent-active` BEFORE Step 3; `rm` AFTER Step 3 / BEFORE Step 5. Binding.
- **Commits — 4-tier conventional:**
  - Task implementation: `feat(<area>): Task A.X — <subject>`.
  - Codex review-fix: `fix(<area>): Codex R<N> <severity> <id> — <subject>`.
  - Internal-Codex (within-task): append `(internal)` qualifier.
  - Internal code-review fix: `fix(<area>): code-review I<N> — <subject>`.
  - Format-only cleanup (ruff): no task ID prefix.
- **Subject-only ERE grep observable verification** before EVERY task implementation commit:
  ```
  git log -E --pretty='%s' --grep='^[a-z]+\([a-z]+\): Task A\.X'
  ```
  Empty output for THIS phase's task ID → safe to proceed. STOP IMMEDIATELY and surface in return report if a duplicate appears for the same Task ID within THIS dispatch's commits.
- **NO OVERWRITING LANDED-TASK COMMITS:** before each task, verify prior task's commit is present AND read the landed file to understand the existing API. If existing API is wrong per your reading, **STOP** and surface; do NOT silently rewrite.
- **TDD:** write failing test → run → see fail → minimal implementation → run → see pass → commit, per task. Plan task text already specifies the failing test FIRST in each task body.
- **Discriminating-test discipline (binding):** every test specifies EXACT field + EXACT pre-fix expected value + EXACT post-fix expected value. "Illustrative" / TODO placeholders are vacuous tests; reject at internal review per Phase 7 plan-authoring lesson 2026-05-04.
- **Ruff baseline ≤80** (current at HEAD `88f9fac`/`251cc35`). New code MUST NOT increase baseline. `ruff check swing/` after each task to verify.
- **No-amend.** Every commit is a NEW commit. Codex/code-review fixes are their own commits.
- **No `--no-verify`, no `--no-gpg-sign`, no Claude co-author footer.**
- **Backup-runner discipline (binding code, not stated):** T1 introduces `Connection.backup()` invocation in `swing/data/db.py`'s migration runner. Backup MUST exist + pass PRAGMA integrity_check before migration SQL runs. Per spec §12.1 + Phase 7 brainstorm lesson "operationalized in code, not stated in spec text."

---

## §5 Adversarial review watch items (for the post-dispatch Codex round)

The orchestrator-side `copowers:adversarial-critic` invocation (Step 5) covers these. Internal-Codex pre-emption is encouraged; pre-empt these in particular:

- **Migration 0014 atomicity.** Single transaction wrapping all changes. Partial-failure should leave DB at version 13 (rolled back) — never at intermediate state.
- **Backup precedes migration.** T1 backup-runner MUST run before T2 migration applies; verify in test (corrupt the backup → migration aborts pre-DDL).
- **4-fixture preservation invariant complete.** All 4 fixtures (singleton/multi-date/same-date/notes-merged) green in T9. No skipped fixture.
- **State-machine all-transition-paths enumeration.** Every allowed transition + every rejected transition has a test in T5 (state service). 5 states × 5 = 25 cells; 6 allowed + 5 self-loops + 14 rejected = 25 cells covered.
- **Per-operation validation correctness** (spec §3.5.1). T5 + T6 encode operations, NOT state-invariant claims. Legacy rows exempt by NULLABLE schema (T10 verifies).
- **Status→state predicate rewrite per §2.1 mapping.** T6 follows the per-line mapping; no regex-replace; each rewrite preserves semantic purpose (active-trade / closed-but-not-reviewed / closed-or-reviewed / write-paths).
- **Fills repo aggregate-recompute correctness** (T4 + T8). After EVERY fill insert (entry / trim / exit / stop), `current_size` / `current_avg_cost` / `last_fill_at` reflect canonical values. Discriminating tests for each action.
- **Multi-entry-fill authoritative selector test** (spec §4.3.1). Trade with hypothetical 2+ entry fills (test fixture only — V1 service-layer disallows; selector contract pre-locks for Phase 9) resolves to the one with min `(fill_datetime, fill_id)`. Discriminating test in T4.
- **VIR/DHC/CC backfill exact-value verification** (T10). Three discriminating tests asserting EXACT (state, pre_trade_locked_at, trade_origin) post-migration.
- **Ruff baseline preserved** (≤80).
- **Plan §2.1 entries marked "Sub-A T6" all rewritten;** entries marked "Sub-B T1/T6/T7/T9" or "Sub-C T1/T2/T7" left UNCHANGED. Reviewer flags unauthorized cross-sub-dispatch work.
- **Trade dataclass `status` property removed** entirely (not deprecation-warning-shimmed); test fixtures + test bodies all migrated to `state` per T0.
- **Migration runner integrity checks all 4 wired** (PRAGMA integrity_check; expected-table set; row-count parity; size advisory). Each has a discriminating test.
- **Discriminating-test gate applied to every test in Sub-A.** Reviewer flags "illustrative" or TODO placeholders.

---

## §6 Done criteria

The Sub-A executing-plans dispatch is done when ALL of the following hold:

- [ ] All 11 plan tasks (A.0-A.10) committed on the worktree branch.
- [ ] Subject-only ERE grep verification clean (no duplicate Task A.X commits).
- [ ] Full fast suite green: `python -m pytest -m "not slow" -q` passes; test count ~+87 (bias-high acceptable IF discriminating-test discipline justifies).
- [ ] Ruff baseline ≤80: `ruff check swing/` shows ≤80 warnings.
- [ ] Migration 0014 idempotent (re-run is no-op; covered by plan tests).
- [ ] Backup-runner integrity checks all pass for the migration backup.
- [ ] VIR/DHC/CC migrated to FIRM values per §2 (verify-via-pytest tests in T10).
- [ ] 4-fixture preservation invariant test gate green.
- [ ] Marker file removed (`ls .copowers-subagent-active` → No such file).
- [ ] Codex `copowers:adversarial-critic` round reached `NO_NEW_CRITICAL_MAJOR`.
- [ ] Worktree merge command + cleanup steps surfaced in return report (operator executes merge).

---

## §7 Return report format

Final message to orchestrator (via operator) MUST include:

```
DISPATCH: Phase 7 Sub-A (schema + repos + state service)
WORKTREE BRANCH: phase7-sub-a-schema (or whatever was used)
BASELINE_SHA: 251cc35
TASK COMMITS: <commit list, A.0 through A.10>
CODEX FIX COMMITS: <commit list, R1+/R2+/etc.>
CODE-REVIEW FIX COMMITS: <commit list>
INTERNAL-CODEX FIX COMMITS: <commit list, qualifier (internal)>

CODEX ADVERSARIAL ROUNDS: <N>; FINAL VERDICT: NO_NEW_CRITICAL_MAJOR

TEST DELTA:
- baseline: 1587 fast tests at 251cc35
- post-dispatch: <N> fast tests
- new: +<N> (vs ~+87 plan estimate)

RUFF DELTA:
- baseline: ≤80 at 251cc35
- post-dispatch: <N>

DB MIGRATION VERIFICATION:
- backup created at: <path>; PRAGMA integrity_check: ok
- 4 integrity checks all pass: <listed>
- migration 0014 applied; schema version: 14
- VIR: state=<>, pre_trade_locked_at=<>, trade_origin=<>
- DHC: state=<>, pre_trade_locked_at=<>, trade_origin=<>
- CC: state=<>, pre_trade_locked_at=<>, trade_origin=<>

PRESERVATION INVARIANT TEST GATE: 4/4 fixtures green
- singleton: <pass/fail>
- multi-date: <pass/fail>
- same-date multi-exit: <pass/fail>
- notes-merged: <pass/fail>

ADVERSARIAL FINDINGS (each with disposition):
- R1: <count critical / major / minor>
  - <finding>: FIXED in commit <SHA> / ACCEPTED with rationale: <text>
- R2: ...

LESSONS WORTH CAPTURING (process insights from this dispatch):
- <bullet list>

OPEN QUESTIONS FOR ORCHESTRATOR:
- <any blocker or unresolved framing issue>

WORKTREE MERGE COMMAND (operator-executed):
- git checkout main && git pull && git merge --no-ff phase7-sub-a-schema -m "Merge phase7-sub-a-schema into main"
  (or --ff-only if no docs commits on main since baseline)

SUB-B PRE-CONDITIONS (relayed for next dispatch):
- Sub-B BASELINE_SHA: <main HEAD post-merge>
- Sub-B starts from clean state-machine + repos + fills layer
- Vocabulary already locked (no checkpoint for Sub-B)
```

---

## §8 If you get stuck

- **If a plan task requires re-designing the spec or plan,** invoke the §2 hard-conflict escape (carries forward from brainstorm + writing-plans briefs): pause the dispatch, send an interim outbrief describing the conflict, standby for orchestrator path-forward. Do NOT relitigate the spec OR plan in the dispatch.
- **If the production DB state at empirical-audit time differs from §0 #7 expected state** (e.g., 4 trades exist; an exit is missing; schema_version != 13), STOP IMMEDIATELY. Do NOT proceed with T2 migration. Surface to orchestrator for backfill/cleanup before resuming.
- **If T6 binding green gate fails** (some test breaks after status drop that the plan didn't anticipate), STOP and surface. Do NOT silently rewrite Sub-B/Sub-C scope to make the gate pass.
- **If the 4-fixture preservation invariant test (T9) fails for a fixture the plan specifies as expected-passing,** STOP — this means migration 0014's backfill is wrong; surface to orchestrator before patching mid-flight (could cascade into in-flight migration corruption for VIR/DHC/CC).
- **If Codex review surfaces a finding that contradicts a locked decision,** apply receiving-code-review discipline. Verify the finding against the spec + plan FIRST. If finding is correct AND locked decision is wrong, escalate via §2 hard-conflict escape. If finding is wrong, document why it's rejected with rationale.
- **If the empirical audit broadens-grep refresh (per plan §2.3) finds new call sites not in the plan §2.1 mapping,** add to the appropriate sub-dispatch task's scope (Sub-A T6 if §2.1 category matches; otherwise hand-off to Sub-B/Sub-C via return report). Do NOT silently expand Sub-A scope into Sub-B/Sub-C territory.
- **If Codex round produces 0/0/0 advisory only,** trust the empirical evidence. NO_NEW_CRITICAL_MAJOR is the gate; you may stop after a clean round even if you wonder whether you missed something.

---

## §9 Anti-patterns specific to this dispatch

These have caused real problems in past sessions; resist:

- **Drifting into Sub-B/Sub-C scope.** Sub-A is data-layer only. CLI / web / journal / services-beyond-state-and-origin-and-derived-metrics are Sub-B/Sub-C. The §2.1 plan mapping makes this explicit; respect the boundary.
- **Re-litigating locked decisions.** Spec at `c926f01` + plan at `251cc35` burned context settling these. Don't reopen; use the §8 hard-conflict escape if blocked.
- **Silent migration retries.** If T2 migration fails, the worktree is in an unknown state. STOP, restore the backup, surface to orchestrator. Do NOT attempt to "fix forward" without orchestrator awareness.
- **"Illustrative" / TODO placeholders in tests.** Per Phase 7 plan-authoring lesson — plan tasks already specify EXACT values; if you find one that doesn't, treat as a plan bug + surface in return report.
- **Cross-cutting tests that span sub-dispatches.** A test that exercises end-to-end Sub-A → Sub-B → Sub-C path is NOT Sub-A's scope. Sub-A tests stop at the repo + state-service layer; integration tests live in Sub-C.
- **`shutil.copy2` for backups.** Spec §12.1 explicitly REJECTS this. Use `Connection.backup()`.
- **Regex-replace status→state.** Per §2.1 + Phase 7 brainstorm lesson — predicate rewrites are NOT uniform substitution; each call-site classifies into one of 4 operation categories with the appropriate rewrite.
- **Skipping the broadened-grep refresh.** Plan §2.3 specifies running `grep -rn "trades\.status\|t\.status\|status='open'\|status='closed'" swing/ tests/` at dispatch time AND after every Sub-A task to catch any plan-time-missed call sites. NOT optional.
- **Over-eager schema cleanup.** Sub-A drops `status` and `exits` per plan; do NOT additionally drop `notes` columns or other Phase 6 fields you happen to think are unused. Out-of-scope schema work is forbidden.

---

## §10 Closing note

Sub-A is the data-layer foundation for Phase 7. Get the schema migration + state machine + Fills repo right; Sub-B + Sub-C build on it. The plan is detailed; the spec is locked; the vocabulary is confirmed. The implementer's job is to execute carefully, verify rigorously, and surface ambiguity rather than silently resolve it.

When done, return the structured report and stop. The orchestrator triages the result + decides when to commission Sub-B (or whether Sub-B + Sub-C parallelize from Sub-A merge).
